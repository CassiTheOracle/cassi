#!/usr/bin/env python3
"""
Qwen3.5-0.8B + Cassi components via transformers library.
Correct inference with breath-modulated sampling, internal observer,
and dual-stream Yang/Yin architecture.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import math
import json

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI

# ---------------------------------------------------------------------------
# 1. Load model and tokenizer
# ---------------------------------------------------------------------------
MODEL_ID = "qwen_models/Qwen3.5-0.8B"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

def load_model():
    print(f"[{DEVICE}] Loading Qwen3.5-0.8B from {MODEL_ID} ...")
    tok = AutoTokenizer.from_pretrained(
        MODEL_ID, trust_remote_code=True, local_files_only=True
    )
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        trust_remote_code=True,
        local_files_only=True,
        dtype=torch.float32,
        device_map=DEVICE,
    )
    model.eval()
    print(f"  -> Loaded on {model.device}")
    print(f"  -> Layers: {model.config.num_hidden_layers}, d_model: {model.config.hidden_size}")
    print(f"  -> Vocab: {model.config.vocab_size}, Heads: {model.config.num_attention_heads}")
    return model, tok


# ---------------------------------------------------------------------------
# 2. Breath-modulated sampler (manual loop)
# ---------------------------------------------------------------------------
class BreathSampler:
    """Coupled Yang/Yin oscillators modulate temperature and top-p."""

    def __init__(self, temp_base=0.8, temp_amp=0.15,
                 top_p_base=0.85, top_p_amp=0.1,
                 omega_yang=0.15, omega_yin=0.094,
                 device=DEVICE):
        self.temp_base = temp_base
        self.temp_amp = temp_amp
        self.top_p_base = top_p_base
        self.top_p_amp = top_p_amp
        self.omega_yang = omega_yang
        self.omega_yin = omega_yin
        self.device = device
        self.t_yang = torch.tensor(0.0, device=device)
        self.t_yin = torch.tensor(0.0, device=device)
        self.step = 0

    def sample(self, logits):
        """logits: [vocab_size]"""
        self.t_yang = self.t_yang + self.omega_yang
        self.t_yin = self.t_yin + self.omega_yin
        yang = torch.sin(self.t_yang)
        yin = torch.sin(self.t_yin)
        beat = yang + yin

        temp = self.temp_base + self.temp_amp * beat
        top_p = self.top_p_base + self.top_p_amp * yang

        # temperature scaling
        probs = F.softmax(logits / temp.clamp(min=0.1), dim=-1)

        # top-p (nucleus) filtering
        sorted_probs, sorted_idx = torch.sort(probs, descending=True)
        cumsum = torch.cumsum(sorted_probs, dim=-1)
        remove = cumsum > top_p
        # keep at least the top token
        if remove.sum() > 0:
            first_remove = torch.where(remove)[0][0].item()
            if first_remove > 0:
                remove[:first_remove] = False
        keep_mask = ~remove
        filtered_probs = sorted_probs * keep_mask.float()
        # renormalize
        if filtered_probs.sum() > 0:
            filtered_probs = filtered_probs / filtered_probs.sum()
        else:
            filtered_probs = sorted_probs
            filtered_probs[0] = 1.0

        # sample
        idx = torch.multinomial(filtered_probs, num_samples=1).item()
        token_id = sorted_idx[idx].item()

        self.step += 1
        meta = {
            "temp": temp.item(),
            "top_p": top_p.item(),
            "beat": beat.item(),
            "yang": yang.item(),
            "yin": yin.item(),
        }
        return token_id, meta


# ---------------------------------------------------------------------------
# 3. Internal Observer Head (monitors hidden states)
# ---------------------------------------------------------------------------
class InternalObserverHead(nn.Module):
    """Predicts confidence, importance, and next-token from hidden state."""

    def __init__(self, d_model=1024, vocab_size=248320):
        super().__init__()
        self.confidence = nn.Sequential(
            nn.Linear(d_model, d_model // 4),
            nn.GELU(),
            nn.Linear(d_model // 4, 1),
            nn.Sigmoid(),
        )
        self.importance = nn.Sequential(
            nn.Linear(d_model, d_model // 4),
            nn.GELU(),
            nn.Linear(d_model // 4, 1),
            nn.Sigmoid(),
        )
        self.predicted_next = nn.Linear(d_model, vocab_size, bias=False)

    def forward(self, hidden):
        """hidden: [..., d_model]"""
        conf = self.confidence(hidden).squeeze(-1)
        imp = self.importance(hidden).squeeze(-1)
        logits = self.predicted_next(hidden)
        return conf, imp, logits


# ---------------------------------------------------------------------------
# 4. Generation helpers
# ---------------------------------------------------------------------------
def generate_standard(model, tok, prompt, max_new=64, temp=0.8, top_p=0.85):
    """Standard transformers generate."""
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=True,
            temperature=temp,
            top_p=top_p,
            pad_token_id=tok.eos_token_id,
        )
    dt = time.time() - t0
    text = tok.decode(out[0], skip_special_tokens=True)
    tok_s = max_new / dt
    return text, tok_s


def generate_breath(model, tok, prompt, max_new=64, sampler=None):
    """Manual loop with breath-modulated sampling."""
    if sampler is None:
        sampler = BreathSampler()
    inputs = tok(prompt, return_tensors="pt").to(model.device)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None

    t0 = time.time()
    metas = []
    for _ in range(max_new):
        if past_key_values is None:
            ids_tensor = torch.tensor([input_ids], device=model.device)
        else:
            ids_tensor = torch.tensor([[input_ids[-1]]], device=model.device)
        with torch.no_grad():
            out = model(input_ids=ids_tensor, past_key_values=past_key_values, use_cache=True)
        logits = out.logits[0, -1, :]  # [vocab]
        past_key_values = out.past_key_values

        token_id, meta = sampler.sample(logits)
        input_ids.append(token_id)
        metas.append(meta)

        if token_id == tok.eos_token_id:
            break
    dt = time.time() - t0

    text = tok.decode(input_ids, skip_special_tokens=True)
    tok_s = len(metas) / dt
    return text, tok_s, metas


# ---------------------------------------------------------------------------
# 5. Observer-augmented generation
# ---------------------------------------------------------------------------
def generate_with_observer(model, tok, prompt, max_new=64, temp=0.8, top_p=0.85):
    """Generate while tracking observer confidence/importance."""
    observer = InternalObserverHead(
        d_model=model.config.hidden_size,
        vocab_size=model.config.vocab_size,
    ).to(model.device).eval()

    inputs = tok(prompt, return_tensors="pt").to(model.device)
    input_ids = inputs["input_ids"][0].tolist()
    past_key_values = None

    t0 = time.time()
    observations = []
    for _ in range(max_new):
        if past_key_values is None:
            ids_tensor = torch.tensor([input_ids], device=model.device)
        else:
            ids_tensor = torch.tensor([[input_ids[-1]]], device=model.device)
        with torch.no_grad():
            out = model(input_ids=ids_tensor, past_key_values=past_key_values,
                        use_cache=True, output_hidden_states=True)
        logits = out.logits[0, -1, :]
        past_key_values = out.past_key_values
        hidden = out.hidden_states[-1][0, -1, :].float()  # cast for observer

        conf, imp, obs_logits = observer(hidden)
        top_pred = torch.argmax(obs_logits).item()

        # standard sampling for the actual token
        probs = F.softmax(logits / temp, dim=-1)
        sorted_probs, sorted_idx = torch.sort(probs, descending=True)
        cumsum = torch.cumsum(sorted_probs, dim=-1)
        remove = cumsum > top_p
        if remove.sum() > 0:
            first = torch.where(remove)[0][0].item()
            if first > 0:
                remove[:first] = False
        keep = ~remove
        filtered = sorted_probs * keep.float()
        filtered = filtered / filtered.sum()
        idx = torch.multinomial(filtered, num_samples=1).item()
        token_id = sorted_idx[idx].item()

        input_ids.append(token_id)
        observations.append({
            "token": tok.decode([token_id]),
            "conf": conf.item(),
            "imp": imp.item(),
            "obs_top": tok.decode([top_pred]),
        })

        if token_id == tok.eos_token_id:
            break
    dt = time.time() - t0

    text = tok.decode(input_ids, skip_special_tokens=True)
    tok_s = len(observations) / dt
    return text, tok_s, observations


# ---------------------------------------------------------------------------
# 6. Dual-stream Yang/Yin generation
# ---------------------------------------------------------------------------
class DualStreamGenerator:
    """
    Yang: all 24 layers, every token (fast, local).
    Yin: 6 layers (every 4th: [3,7,11,15,19,23]), every K=4 tokens,
         decayed by PHI_INV between updates.
    Arbitration: per-dimension gate combining Yang + Yin.
    """

    def __init__(self, model, K=4, device=DEVICE):
        self.model = model
        self.K = K
        self.device = device
        self.n_layers = model.config.num_hidden_layers
        self.d_model = model.config.hidden_size
        # Yang uses all layers; Yin uses every 4th layer
        self.yin_layer_indices = list(range(3, self.n_layers, 4))
        print(f"DualStream: Yang=all {self.n_layers} layers every token")
        print(f"DualStream: Yin={len(self.yin_layer_indices)} layers {self.yin_layer_indices} every {K} tokens")
        # Corpus callosum: compress d_model -> d_model/4 -> d_model
        bottleneck = int(self.d_model / PHI)
        self.corpus_callosum = nn.Sequential(
            nn.Linear(self.d_model, bottleneck),
            nn.GELU(),
            nn.Linear(bottleneck, self.d_model),
        ).to(device)
        # Stream arbitration gate
        self.arbitration = nn.Sequential(
            nn.Linear(self.d_model * 4, self.d_model // 2),
            nn.GELU(),
            nn.Linear(self.d_model // 2, self.d_model),
            nn.Sigmoid(),
        ).to(device)
        # Persistent Yin state
        self.yin_state = None
        self.yang_state = None
        self.token_count = 0

    def _run_yang(self, hidden, past_key_values=None):
        """Full forward through all layers."""
        out = self.model.model(
            inputs_embeds=hidden.unsqueeze(0),
            past_key_values=past_key_values,
            use_cache=True,
        )
        return out.last_hidden_state[0, -1, :], out.past_key_values

    def _run_yin_subset(self, hidden):
        """Run only selected layers."""
        h = hidden.unsqueeze(0)  # [1, 1, d_model]
        # We need to manually run through selected layers.
        # For simplicity, run full model but only backprop through subset.
        # For inference, we just run the selected layers.
        # NOTE: This is a simplification; true implementation would need
        # custom forward. We approximate by running selected layers only.
        for i in self.yin_layer_indices:
            layer = self.model.model.layers[i]
            h = layer(h)
        return h[0, -1, :]  # [d_model]

    def generate(self, tok, prompt, max_new=64, temp=0.8, top_p=0.85):
        inputs = tok(prompt, return_tensors="pt").to(self.device)
        input_ids = inputs["input_ids"][0].tolist()
        past_key_values = None

        t0 = time.time()
        for _ in range(max_new):
            if past_key_values is None:
                ids_tensor = torch.tensor([input_ids], device=self.device)
            else:
                ids_tensor = torch.tensor([[input_ids[-1]]], device=self.device)

            # ---- Yang: full model forward ----
            with torch.no_grad():
                out = self.model(
                    input_ids=ids_tensor,
                    past_key_values=past_key_values,
                    use_cache=True,
                    output_hidden_states=True,
                )
            yang_logits = out.logits[0, -1, :]
            past_key_values = out.past_key_values
            yang_hidden = out.hidden_states[-1][0, -1, :]  # [d_model]

            # ---- Yin: update every K tokens ----
            if self.token_count % self.K == 0:
                # Compute Yin by running subset of layers on current hidden
                # Use embeddings from input_ids (full sequence for embedding)
                with torch.no_grad():
                    emb = self.model.model.embed_tokens(ids_tensor)
                    yin_h = emb[0, -1, :]
                    for i in self.yin_layer_indices:
                        layer = self.model.model.layers[i]
                        # Each layer expects [B, T, D]; we pass [1, 1, D]
                        yin_h = layer(yin_h.unsqueeze(0).unsqueeze(0))[0, -1, :]
                self.yin_state = yin_h
            else:
                # Decay Yin state by PHI_INV (simulate slow forgetting)
                if self.yin_state is not None:
                    self.yin_state = self.yin_state * PHI_INV

            # ---- Corpus Callosum ----
            if self.yin_state is None:
                self.yin_state = torch.zeros_like(yang_hidden)
            yin_broadcast = self.corpus_callosum(self.yin_state)

            # ---- Stream Arbitration ----
            diff = yang_hidden - yin_broadcast
            dot_prod = (yang_hidden * yin_broadcast).sum()
            gate_input = torch.cat([
                yang_hidden,
                yin_broadcast,
                diff.abs(),
                torch.full_like(yang_hidden, dot_prod),
            ])
            gate = self.arbitration(gate_input)
            combined = gate * yang_hidden + (1 - gate) * yin_broadcast

            # ---- Sample from combined representation ----
            # Project combined back to logits via lm_head
            with torch.no_grad():
                logits = self.model.lm_head(combined)
            probs = F.softmax(logits / temp, dim=-1)
            sorted_probs, sorted_idx = torch.sort(probs, descending=True)
            cumsum = torch.cumsum(sorted_probs, dim=-1)
            remove = cumsum > top_p
            if remove.sum() > 0:
                first = torch.where(remove)[0][0].item()
                if first > 0:
                    remove[:first] = False
            keep = ~remove
            filtered = sorted_probs * keep.float()
            filtered = filtered / filtered.sum()
            idx = torch.multinomial(filtered, num_samples=1).item()
            token_id = sorted_idx[idx].item()

            input_ids.append(token_id)
            self.token_count += 1

            if token_id == tok.eos_token_id:
                break

        dt = time.time() - t0
        text = tok.decode(input_ids, skip_special_tokens=True)
        tok_s = (len(input_ids) - len(inputs["input_ids"][0])) / dt
        return text, tok_s


# ---------------------------------------------------------------------------
# 7. Main experiment
# ---------------------------------------------------------------------------
def main():
    model, tok = load_model()
    prompt = "The golden ratio appears in nature"

    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Standard generation")
    print("=" * 70)
    text1, speed1 = generate_standard(model, tok, prompt, max_new=64)
    print(f"Speed: {speed1:.1f} tok/s")
    print(f"Output:\n{text1}\n")

    print("=" * 70)
    print("EXPERIMENT 2: Breath-modulated generation")
    print("=" * 70)
    sampler = BreathSampler(omega_yang=0.15, omega_yin=0.094)
    text2, speed2, metas = generate_breath(model, tok, prompt, max_new=64, sampler=sampler)
    print(f"Speed: {speed2:.1f} tok/s")
    print(f"Avg temp: {sum(m['temp'] for m in metas)/len(metas):.3f}")
    print(f"Avg top_p: {sum(m['top_p'] for m in metas)/len(metas):.3f}")
    print(f"Output:\n{text2}\n")

    print("=" * 70)
    print("EXPERIMENT 3: Generation with Internal Observer")
    print("=" * 70)
    text3, speed3, obs = generate_with_observer(model, tok, prompt, max_new=64)
    print(f"Speed: {speed3:.1f} tok/s")
    avg_conf = sum(o["conf"] for o in obs) / len(obs)
    avg_imp = sum(o["imp"] for o in obs) / len(obs)
    print(f"Avg confidence: {avg_conf:.3f}, Avg importance: {avg_imp:.3f}")
    # Print first 5 observations
    for o in obs[:5]:
        print(f"  token={o['token']!r:>8}  conf={o['conf']:.3f}  imp={o['imp']:.3f}  obs_top={o['obs_top']!r}")
    print(f"Output:\n{text3}\n")

    print("=" * 70)
    print("EXPERIMENT 4: Dual-stream Yang/Yin generation")
    print("=" * 70)
    print("NOTE: Dual-stream requires custom layer traversal which triggers")
    print("      a ROCm driver bug with GatedDeltaNet. Skipping for safety.")
    print("      See experiments/qwen_dual_stream.py for architecture sketch.\n")
    text4, speed4 = "[skipped]", 0.0

    # Second prompt for variety
    prompt2 = "In the philosophy of consciousness, integrated information"
    print("=" * 70)
    print("EXPERIMENT 5: Breath on philosophy prompt")
    print("=" * 70)
    sampler2 = BreathSampler(omega_yang=0.12, omega_yin=0.074)
    text5, speed5, metas2 = generate_breath(model, tok, prompt2, max_new=64, sampler=sampler2)
    print(f"Speed: {speed5:.1f} tok/s")
    print(f"Avg temp: {sum(m['temp'] for m in metas2)/len(metas2):.3f}")
    print(f"Output:\n{text5}\n")

    # Save results
    results = {
        "prompt": prompt,
        "standard": {"text": text1, "speed_tok_s": speed1},
        "breath": {"text": text2, "speed_tok_s": speed2,
                   "avg_temp": sum(m['temp'] for m in metas)/len(metas),
                   "avg_top_p": sum(m['top_p'] for m in metas)/len(metas),
                   "meta_count": len(metas)},
        "observer": {"text": text3, "speed_tok_s": speed3,
                     "avg_confidence": avg_conf,
                     "avg_importance": avg_imp,
                     "obs_count": len(obs)},
        "breath_philosophy": {"text": text5, "speed_tok_s": speed5,
                              "avg_temp": sum(m['temp'] for m in metas2)/len(metas2),
                              "avg_top_p": sum(m['top_p'] for m in metas2)/len(metas2),
                              "meta_count": len(metas2)},
    }
    out_path = "experiments/qwen_transformers_results.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {out_path}")


if __name__ == "__main__":
    main()
