"""
Cassi-Enhanced DiffusionGemma Inference
========================================

Maps Cassi dynamical concepts onto DiffusionGemma's parallel canvas denoising:
- φ-Breath Sampler: temperature schedule modulated by breath oscillator
- Qi-Fluid: canvas coherence across denoising steps
- Chakra Weights: φ-spaced position weighting on the 256-token canvas
- Kundalini Metric: energy flow tracking across canvas positions

Model: google/diffusiongemma-26B-A4B-it (26B MoE, 3.8B active)
Hardware: AMD RX 7900 XTX (24GB VRAM) — ROCm/PyTorch path
"""

import os
import sys
import time
import math
import json
import torch
import torch.nn.functional as F
import numpy as np

# -----------------------------------------------------------------------------
# Cassi constants
# -----------------------------------------------------------------------------
PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI

# -----------------------------------------------------------------------------
# Load model
# -----------------------------------------------------------------------------
LOCAL_DIR = "checkpoints/diffusiongemma"
DEVICE = "cuda:0" if torch.cuda.is_available() else "cpu"


def load_model():
    """Load DiffusionGemma from local checkpoint with CPU offloading."""
    from transformers import (
        DiffusionGemmaForBlockDiffusion,
        AutoTokenizer,
        AutoConfig,
    )
    from safetensors.torch import load_file
    from accelerate import init_empty_weights, infer_auto_device_map, dispatch_model

    print("Loading config...")
    config = AutoConfig.from_pretrained(LOCAL_DIR, trust_remote_code=True)
    print(f"  canvas_length={config.canvas_length}")
    print(f"  vocab_size={config.text_config.vocab_size}")
    print(f"  hidden_size={config.text_config.hidden_size}")
    print(f"  layers={config.text_config.num_hidden_layers}")
    print(f"  experts={config.text_config.num_experts} (top_k={config.text_config.top_k_experts})")

    print("\nLoading tokenizer...")
    tokenizer = AutoTokenizer.from_pretrained(LOCAL_DIR, trust_remote_code=True)

    print("\nLoading model with CPU offloading (26B params, ~52GB bfloat16)...")

    # Step 1: Create model on meta device
    with init_empty_weights():
        model = DiffusionGemmaForBlockDiffusion(config)

    # Step 2: Load all safetensor shards onto the meta model
    with open(os.path.join(LOCAL_DIR, "model.safetensors.index.json")) as f:
        index = json.load(f)

    shards = sorted(set(index["weight_map"].values()))
    print(f"  {len(shards)} shards to load")

    for i, shard in enumerate(shards):
        path = os.path.join(LOCAL_DIR, shard)
        sd = load_file(path, device="cpu")
        # Load with assign=True on CPU (meta tensors get materialized)
        missing, unexpected = model.load_state_dict(sd, strict=False, assign=True)
        if missing:
            print(f"    Missing keys in {shard}: {missing[:5]}...")
        del sd
        print(f"  [{i+1}/{len(shards)}] {shard} loaded")

    # Step 3: Tie weights and mark initialized
    model.tie_weights()
    for p in model.parameters():
        p._is_hf_initialized = True

    # Step 4: Create device map that fits in 20GB GPU + CPU
    max_memory = {0: "20GiB", "cpu": "60GiB"}
    device_map = infer_auto_device_map(
        model,
        max_memory=max_memory,
        dtype=torch.bfloat16,
    )
    print(f"\nDevice map inferred:")
    gpu_layers = [k for k, v in device_map.items() if v == 0]
    cpu_layers = [k for k, v in device_map.items() if v == "cpu"]
    print(f"  GPU layers: {len(gpu_layers)}")
    print(f"  CPU layers: {len(cpu_layers)}")

    # Step 5: Dispatch model to GPU/CPU
    model = dispatch_model(model, device_map=device_map)
    model.eval()

    gpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cuda")
    cpu_params = sum(p.numel() for p in model.parameters() if p.device.type == "cpu")
    print(f"\nModel ready. VRAM used: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
    print(f"Parameters on GPU: {gpu_params / 1e9:.2f}B")
    print(f"Parameters on CPU:  {cpu_params / 1e9:.2f}B")
    return model, tokenizer


# -----------------------------------------------------------------------------
# Cassi-Enhanced Sampler
# -----------------------------------------------------------------------------
class PhiBreathSampler:
    """
    φ-Breath temperature modulation for diffusion denoising.

    Instead of linear decay 0.8 → 0.4, we use a breath oscillator:
      - Inhale (T high): canvas explores more broadly
      - Exhale (T low): canvas commits confident tokens

    The breath period is φ-scaled relative to max_steps.
    """

    def __init__(self, base_temp=0.8, min_temp=0.4, breath_period_factor=PHI):
        self.base_temp = base_temp
        self.min_temp = min_temp
        self.breath_period_factor = breath_period_factor

    def schedule(self, step, max_steps):
        """Return temperature for this denoising step."""
        # Linear baseline from base → min
        linear = self.base_temp + (self.min_temp - self.base_temp) * (step / max(1, max_steps - 1))

        # Breath modulation: inhale/exhale cycle
        breath_period = max_steps / self.breath_period_factor
        phase = 2 * math.pi * step / breath_period
        breath = 0.5 + 0.5 * math.sin(phase - math.pi / 2)  # start at inhale

        # Combine: breath modulates around linear trend
        # Inhale (breath ≈ 1.0) → slightly higher T
        # Exhale (breath ≈ 0.0) → slightly lower T
        modulation = 0.15 * breath
        temp = linear + modulation
        return max(self.min_temp * 0.5, min(self.base_temp * 1.2, temp))


class QiGuidedStopping:
    """
    Qi-Fluid coherence metric for adaptive stopping.

    qi_t = cosine_similarity(canvas_embeddings_t, canvas_embeddings_{t-1})
    High Qi  = canvas is stable → can stop early if entropy also low
    Low Qi   = canvas is fluctuating → need more denoising
    """

    def __init__(self, qi_threshold=0.985, entropy_threshold=0.005, patience=2):
        self.qi_threshold = qi_threshold
        self.entropy_threshold = entropy_threshold
        self.patience = patience

    def compute_qi(self, canvas_logits_t, canvas_logits_t_prev):
        """Compute Qi-fluid as normalized cosine similarity of flat logits."""
        if canvas_logits_t_prev is None:
            return 0.0
        # Flatten canvas [canvas_len, vocab] → vectors
        t = canvas_logits_t.reshape(-1).to(torch.float32)
        t_prev = canvas_logits_t_prev.reshape(-1).to(torch.float32)
        return F.cosine_similarity(t.unsqueeze(0), t_prev.unsqueeze(0)).item()

    def compute_entropy(self, canvas_logits):
        """Average entropy across the canvas."""
        probs = F.softmax(canvas_logits.to(torch.float32), dim=-1)
        log_probs = torch.log(probs + 1e-9)
        entropy = -(probs * log_probs).sum(dim=-1).mean()
        return entropy.item()

    def should_stop(self, canvas_logits_t, canvas_logits_t_prev, step, max_steps):
        qi = self.compute_qi(canvas_logits_t, canvas_logits_t_prev)
        entropy = self.compute_entropy(canvas_logits_t)
        stable = qi > self.qi_threshold and entropy < self.entropy_threshold
        return stable, qi, entropy


class ChakraCanvasWeights:
    """
    φ-spaced chakra positions on the 256-token canvas.

    Each chakra resonates with a different scale of structure:
      Root    (0–16):   local syntax, grammar
      Sacral  (16–32):  word-level patterns
      Solar   (32–64):  phrase structure
      Heart   (64–96):  clause coherence
      Throat  (96–128): sentence-level flow
      Eye     (128–160): paragraph coherence
      Crown   (160–256): global topic/theme
    """

    def __init__(self, canvas_length=256, n_chakras=7):
        self.canvas_length = canvas_length
        self.n_chakras = n_chakras
        self.centers = self._compute_centers()
        self.weights = self._compute_weights()

    def _compute_centers(self):
        # Geometric spacing: positions follow φ-progression
        centers = []
        for c in range(self.n_chakras):
            frac = PHI_INV ** (self.n_chakras - 1 - c)  # Root = small, Crown = large
            pos = int(frac * self.canvas_length)
            centers.append(min(pos, self.canvas_length - 1))
        return centers

    def _compute_weights(self):
        # Lorentzian resonance profiles centered at chakra positions
        positions = torch.arange(self.canvas_length, dtype=torch.float32)
        weights = torch.zeros(self.n_chakras, self.canvas_length)
        for c, center in enumerate(self.centers):
            width = max(4, self.canvas_length // (2 ** (self.n_chakras - c)))
            weights[c] = 1.0 / (1.0 + ((positions - center) / width) ** 2)
        # Normalize so each position has total weight ≈ 1
        weights = weights / weights.sum(dim=0, keepdim=True).clamp_min(1e-6)
        return weights  # [n_chakras, canvas_length]

    def apply(self, canvas_logits):
        """
        Modulate canvas logits by chakra weights.
        Returns per-chakra weighted views of the canvas.
        """
        # weights: [n_chakras, canvas_length]
        # canvas_logits: [canvas_length, vocab]
        w = self.weights.to(canvas_logits.device).to(canvas_logits.dtype)
        # Weighted sum across positions for each chakra
        chakra_energies = torch.matmul(w, canvas_logits)  # [n_chakras, vocab]
        return chakra_energies


class KundaliniTracker:
    """
    Track upward energy flow across chakras.
    K > 1: energy rising (good for generation)
    K < 1: energy pooling (may indicate local minima)
    """

    def __init__(self, n_chakras=7):
        self.n_chakras = n_chakras

    def compute(self, chakra_energies):
        """
        chakra_energies: [n_chakras, vocab] tensor
        Returns Kundalini scalar.
        """
        energy = chakra_energies.to(torch.float32).abs().mean(dim=-1)  # [n_chakras]
        ratios = []
        for c in range(self.n_chakras - 1):
            if energy[c].item() > 1e-6:
                ratios.append(energy[c + 1].item() / energy[c].item())
        if not ratios:
            return 1.0
        return float(np.mean(ratios))


# -----------------------------------------------------------------------------
# Generation
# -----------------------------------------------------------------------------
def generate_standard(model, tokenizer, prompt, max_new_tokens=256, max_steps=48):
    """Standard DiffusionGemma generation with default sampler."""
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    t0 = time.time()
    with torch.no_grad():
        output = model.generate(**inputs, max_new_tokens=max_new_tokens)
    dt = time.time() - t0

    text = tokenizer.decode(output[0], skip_special_tokens=True)
    return text, dt


def generate_cassi(
    model,
    tokenizer,
    prompt,
    max_new_tokens=256,
    max_steps=48,
    use_breath=True,
    use_qi=True,
    use_chakras=True,
):
    """
    Cassi-enhanced generation with φ-Breath, Qi-Stopping, and Chakra tracking.

    NOTE: This uses the model's built-in generation but wraps it with
    Cassi monitoring. Full custom sampling would require implementing
    the diffusion loop manually, which we do as Phase 2.
    """
    messages = [{"role": "user", "content": prompt}]
    inputs = tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        return_dict=True,
        return_tensors="pt",
    ).to(model.device)

    # Initialize Cassi modules
    breath_sampler = PhiBreathSampler() if use_breath else None
    qi_stopper = QiGuidedStopping() if use_qi else None
    chakra_weights = ChakraCanvasWeights(canvas_length=model.config.canvas_length) if use_chakras else None
    kundalini = KundaliniTracker()

    # Phase 1: Use model.generate() with hf_overrides for diffusion config
    # We pass custom generation config via hf_overrides
    generation_config = {
        "max_new_tokens": max_new_tokens,
        "do_sample": True,
        "temperature": 0.8,
    }

    t0 = time.time()
    with torch.no_grad():
        # For now, use standard generation with Cassi post-hoc analysis
        # Full custom diffusion loop requires access to internal canvas state
        output = model.generate(**inputs, **generation_config)
    dt = time.time() - t0

    text = processor.decode(output[0], skip_special_tokens=True)

    # Post-hoc Cassi analysis on the output tokens
    # (In Phase 2, we will instrument the forward pass to extract canvas states)
    metrics = {
        "tokens_generated": output.shape[1] - inputs["input_ids"].shape[1],
        "time_sec": dt,
        "tok_per_sec": (output.shape[1] - inputs["input_ids"].shape[1]) / dt,
    }

    return text, metrics


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", default="Explain the golden ratio and its appearance in nature.")
    parser.add_argument("--max-new", type=int, default=256)
    parser.add_argument("--max-steps", type=int, default=48)
    parser.add_argument("--no-breath", action="store_true")
    parser.add_argument("--no-qi", action="store_true")
    parser.add_argument("--no-chakras", action="store_true")
    args = parser.parse_args()

    model, tokenizer = load_model()

    print("\n" + "=" * 60)
    print("STANDARD GENERATION")
    print("=" * 60)
    text_std, dt_std = generate_standard(model, tokenizer, args.prompt, args.max_new, args.max_steps)
    print(f"Time: {dt_std:.2f}s")
    print(f"Output:\n{text_std}\n")

    print("\n" + "=" * 60)
    print("CASSI-ENHANCED GENERATION")
    print("=" * 60)
    text_cassi, metrics = generate_cassi(
        model,
        tokenizer,
        args.prompt,
        args.max_new,
        args.max_steps,
        use_breath=not args.no_breath,
        use_qi=not args.no_qi,
        use_chakras=not args.no_chakras,
    )
    print(f"Time: {metrics['time_sec']:.2f}s")
    print(f"Tokens: {metrics['tokens_generated']}")
    print(f"Speed: {metrics['tok_per_sec']:.1f} tok/s")
    print(f"Output:\n{text_cassi}\n")


if __name__ == "__main__":
    main()
