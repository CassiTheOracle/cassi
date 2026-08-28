#!/usr/bin/env python3
"""
Qwen3.5-4B + Full Cassi Integration

Combines all Cassi architectural motifs into a unified inference pipeline:
  1. Breath          — dual-heart oscillator modulates temperature
  2. Berry Memory    — topological associative memory (geometric keying)
  3. Qi-Fluid        — running coherence between current and past states
  4. Chakra Tracker  — energy distribution across 13 φ-scaled layer groups
  5. Observer        — confidence/importance/next-token head
  6. Specialist Ensemble — 5 competitive sparse output heads
  7. Neuroplasticizer — stuckness detection + reset pulse
  8. Harmony Gate    — Qi-modulated blending of all logit sources

VRAM: ~9 GB total (base 8.8 GB + Cassi modules ~0.3 GB)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import os
import json
import math
import time
import gc
import sys
from collections import deque
from transformers import AutoTokenizer, AutoConfig
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForConditionalGeneration
from safetensors.torch import load_file
sys.path.insert(0, ".")
from cassi.residual_kv_cache import ResidualKVCacheWrapper
from cassi.cord_observer import CordObserver

PHI = (1 + 5**0.5) / 2
PHI_INV = 1 / PHI
LOCAL_MODEL_DIR = "qwen_models/Qwen3.5-4B"
DEVICE = "cuda"
DTYPE = torch.bfloat16

# ═══════════════════════════════════════════════════════════════════════════════
# Cassi Modules
# ═══════════════════════════════════════════════════════════════════════════════

class BreathModule:
    """Dual-heart Yin-Yang oscillator with learnable frequencies."""

    def __init__(self, omega_yang=0.15, omega_yin=None):
        self.omega_yang = omega_yang
        self.omega_yin = omega_yin or omega_yang / PHI
        self.reset()

    def reset(self):
        self.t_yang = 0.0
        self.t_yin = 0.0
        self.beat_history = deque(maxlen=16)

    def step(self):
        self.t_yang += self.omega_yang
        self.t_yin += self.omega_yin
        yang = math.sin(self.t_yang)
        yin = math.sin(self.t_yin)
        # Beat = product (constructive interference)
        beat = yang * yin
        self.beat_history.append(beat)
        return yang, yin, beat

    def get_temp_scale(self, base_temp=0.8):
        """Inhale (yang↑) → explore (higher T). Exhale (yin↑) → commit (lower T)."""
        yang, yin, _ = self.step()
        # Yang expansive → raise temp; Yin contractive → lower temp
        return base_temp + 0.12 * yang - 0.06 * yin

    def freq_ratio(self):
        return self.omega_yang / max(self.omega_yin, 1e-9)


class BerryMemory(nn.Module):
    """Fixed-slot topological memory keyed by cosine similarity."""

    def __init__(self, d_model, n_slots=512):
        super().__init__()
        self.n_slots = n_slots
        self.d_model = d_model
        # Keys and values live as parameters so they save in checkpoints
        self.register_buffer("keys", torch.randn(n_slots, d_model) * 0.01)
        self.register_buffer("values", torch.randn(n_slots, d_model) * 0.01)
        self.register_buffer("counts", torch.zeros(n_slots))
        self.register_buffer("ages", torch.zeros(n_slots))

    def store(self, hidden):
        """Store hidden state. Update most similar slot, or least-used."""
        sims = F.cosine_similarity(hidden.unsqueeze(0), self.keys, dim=-1)
        best_idx = sims.argmax()
        if sims[best_idx] > 0.92:
            # Update existing slot (moving average)
            self.keys[best_idx] = 0.9 * self.keys[best_idx] + 0.1 * hidden.detach()
            self.values[best_idx] = 0.9 * self.values[best_idx] + 0.1 * hidden.detach()
            self.counts[best_idx] += 1
        else:
            # Evict oldest least-used slot
            score = self.counts * 0.3 - self.ages * 0.7
            idx = score.argmin()
            self.keys[idx] = hidden.detach()
            self.values[idx] = hidden.detach()
            self.counts[idx] = 1
            self.ages[idx] = 0
        self.ages += 1

    def retrieve(self, hidden, k=5):
        """Return retrieved value vector and mean similarity (hit quality)."""
        sims = F.cosine_similarity(hidden.unsqueeze(0), self.keys, dim=-1)
        topk = sims.topk(k)
        if topk.values.max() < 0.5:
            return None, 0.0  # No meaningful match
        weights = F.softmax(topk.values / 0.1, dim=-1)
        retrieved = (weights.unsqueeze(-1) * self.values[topk.indices]).sum(dim=0)
        return retrieved, topk.values.mean().item()


class QiFluid(nn.Module):
    """Running exponential mean of hidden states; coherence = cosine similarity."""

    def __init__(self, d_model, momentum=PHI_INV):
        super().__init__()
        self.momentum = momentum
        self.register_buffer("running_mean", torch.zeros(d_model))
        self.register_buffer("initialized", torch.tensor(0, dtype=torch.bool))

    def update(self, hidden):
        if not self.initialized:
            self.running_mean.copy_(hidden.detach())
            self.initialized.fill_(True)
        else:
            self.running_mean = self.momentum * self.running_mean + (1 - self.momentum) * hidden.detach()
        coherence = F.cosine_similarity(hidden, self.running_mean, dim=-1)
        # Map coherence to [0, 1] with some headroom
        return (coherence + 1) / 2

    def reset(self):
        self.running_mean.zero_()
        self.initialized.fill_(False)


class ChakraTracker:
    """
    Map 32 layers → 13 chakras with φ-scaled grouping.
    Lower chakras = fewer layers (slower), upper = more layers (faster).
    """

    CHAKRA_NAMES = [
        "Root", "Sacral", "SolarPlexus", "Heart", "Throat",
        "ThirdEye", "Crown", "Bindu", "Kalas", "Soma",
        "Guru", "SahasraraCore", "Transcendent"
    ]

    # 13 groups summing to 32 layers
    LAYER_GROUPS = [
        (0, 1),      # Root        (2)
        (2, 3),      # Sacral      (2)
        (4, 5),      # SolarPlexus (2)
        (6, 7),      # Heart       (2)
        (8, 10),     # Throat      (3)
        (11, 13),    # ThirdEye    (3)
        (14, 16),    # Crown       (3)
        (17, 19),    # Bindu       (3)
        (20, 22),    # Kalas       (3)
        (23, 24),    # Soma        (2)
        (25, 26),    # Guru        (2)
        (27, 28),    # Sahasrara   (2)
        (29, 31),    # Transcendent(3)
    ]

    def track(self, hidden_states):
        """
        hidden_states: tuple of tensors from all layers + embedding.
        Returns dict with energies per chakra and aggregate metrics.
        """
        # Skip embedding (index 0), use layer outputs
        layer_hiddens = hidden_states[1:]
        energies = []
        for start, end in self.LAYER_GROUPS:
            group = layer_hiddens[start:end + 1]
            # Mean L2 norm across layers in group, averaged over tokens
            norms = [h.float().norm(dim=-1).mean().item() for h in group]
            energies.append(sum(norms) / len(norms))

        total = sum(energies) + 1e-9
        ratios = [e / total for e in energies]
        entropy = -sum(r * math.log(r + 1e-9) for r in ratios)
        max_ratio = max(ratios)
        dominant = self.CHAKRA_NAMES[ratios.index(max_ratio)]

        return {
            "energies": energies,
            "ratios": ratios,
            "entropy": entropy,
            "dominant": dominant,
            "max_ratio": max_ratio,
        }


# ObserverHead replaced by CordObserver (imported from cassi.cord_observer)

class SpecialistEnsemble(nn.Module):
    """
    5 competitive sparse heads. Each is a slim bottleneck projection to vocab.
    A φ-temperature softmax gate decides specialist weights dynamically.
    """

    def __init__(self, d_model, vocab_size, n_specialists=5, bottleneck=64):
        super().__init__()
        self.n_specialists = n_specialists
        self.specialists = nn.ModuleList([
            nn.Sequential(
                nn.Linear(d_model, bottleneck),
                nn.GELU(),
                nn.Linear(bottleneck, vocab_size, bias=False),
            )
            for _ in range(n_specialists)
        ])
        # Initialize specialists to near-zero (small perturbations initially)
        for spec in self.specialists:
            nn.init.xavier_uniform_(spec[0].weight, gain=0.05)
            nn.init.zeros_(spec[0].bias)
            nn.init.xavier_uniform_(spec[2].weight, gain=0.05)

        self.gate = nn.Linear(d_model, n_specialists)
        nn.init.xavier_uniform_(self.gate.weight, gain=0.1)
        nn.init.zeros_(self.gate.bias)

    def forward(self, hidden):
        # hidden: [D]
        biases = torch.stack([spec(hidden) for spec in self.specialists], dim=0)  # [N, V]
        gates = F.softmax(self.gate(hidden) / PHI, dim=-1)  # [N]
        combined = (gates.unsqueeze(-1) * biases).sum(dim=0)  # [V]
        return combined, gates


class Neuroplasticizer:
    """
    Detects 'rigidity' — when generation becomes repetitive or low-entropy.
    Triggers a reset pulse: clears Qi, resets Breath, boosts temperature.
    """

    def __init__(self, rigidity_threshold=0.65, entropy_window=16):
        self.threshold = rigidity_threshold
        self.entropy_window = entropy_window
        self.recent_entropies = deque(maxlen=entropy_window)
        self.recent_tokens = deque(maxlen=32)
        self.ngram_counts = {}
        self.pulse_active = False
        self.pulse_remaining = 0

    def update(self, token_id, entropy):
        self.recent_entropies.append(entropy)
        self.recent_tokens.append(token_id)

        # Detect repetition via 4-gram counts
        tokens = list(self.recent_tokens)
        if len(tokens) >= 4:
            gram = tuple(tokens[-4:])
            self.ngram_counts[gram] = self.ngram_counts.get(gram, 0) + 1

        # Compute rigidity score
        if len(self.recent_entropies) >= 8:
            ent_mean = sum(self.recent_entropies) / len(self.recent_entropies)
            ent_std = (sum((e - ent_mean) ** 2 for e in self.recent_entropies) / len(self.recent_entropies)) ** 0.5
            # Low entropy + low variance = rigid
            repetition_score = max(self.ngram_counts.values()) / max(len(self.ngram_counts), 1)
            rigidity = (1 - math.tanh(ent_mean)) * 0.5 + (1 - math.tanh(ent_std * 3)) * 0.3 + repetition_score * 0.2
        else:
            rigidity = 0.0

        if self.pulse_active:
            self.pulse_remaining -= 1
            if self.pulse_remaining <= 0:
                self.pulse_active = False

        if rigidity > self.threshold and not self.pulse_active:
            self.pulse_active = True
            self.pulse_remaining = 8  # 8 tokens of elevated exploration
            self.ngram_counts.clear()
            return True, rigidity

        return False, rigidity

    def get_boost(self):
        """Returns temperature multiplier during pulse."""
        return 1.4 if self.pulse_active else 1.0

    def reset(self):
        self.recent_entropies.clear()
        self.recent_tokens.clear()
        self.ngram_counts.clear()
        self.pulse_active = False
        self.pulse_remaining = 0


class HarmonyGate(nn.Module):
    """
    Qi-modulated blending of all logit sources.

    Legacy mode: inputs converted to probability space before blending.
    Residual mode: Cassi components output logit-space residuals added to base.
    """

    def __init__(self, d_model, vocab_size, residual=False):
        super().__init__()
        self.residual = residual
        # Small learnable scalars for adaptive blending
        self.qi_scale = nn.Parameter(torch.tensor(1.0))
        self.conf_scale = nn.Parameter(torch.tensor(1.0))
        # Project retrieved Berry hidden state to logit space
        self.berry_head = nn.Linear(d_model, vocab_size, bias=False)
        nn.init.xavier_uniform_(self.berry_head.weight, gain=0.05)

    def forward(self, base_logits, obs_logits, berry_bias, spec_bias, qi, conf):
        """
        All logit inputs: [V]. qi, conf: scalars in [0,1].
        Returns blended logits [V].
        """
        if berry_bias is not None:
            berry_logits = self.berry_head(berry_bias)
        else:
            berry_logits = None

        # Compute weights from Qi and confidence
        w_base = 0.5 + 0.5 * qi * conf  # 0.5 → 1.0
        w_obs = (1 - conf) * 0.15       # down-weighted untrained observer
        w_berry = (1 - qi) * 0.05       # memory is subtle
        w_spec = 0.05                   # untrained specialists = gentle noise

        total = w_base + w_obs + w_berry + w_spec
        w_base /= total
        w_obs /= total
        w_berry /= total
        w_spec /= total

        if self.residual:
            # Logit-space residual: base + weighted component corrections
            out = base_logits
            if obs_logits is not None:
                out = out + w_obs * obs_logits
            if spec_bias is not None:
                out = out + w_spec * spec_bias
            if berry_logits is not None:
                out = out + w_berry * berry_logits
            blended_logits = out
        else:
            # Probability-space blending (legacy)
            base_p = F.softmax(base_logits, dim=-1)
            obs_p = F.softmax(obs_logits, dim=-1) if obs_logits is not None else base_p
            berry_p = F.softmax(berry_logits, dim=-1) if berry_logits is not None else base_p
            spec_p = F.softmax(spec_bias, dim=-1) if spec_bias is not None else base_p

            blended_p = w_base * base_p + w_obs * obs_p + w_berry * berry_p + w_spec * spec_p
            blended_logits = torch.log(blended_p + 1e-10)

        return blended_logits, {
            "w_base": float(w_base), "w_obs": float(w_obs),
            "w_berry": float(w_berry), "w_spec": float(w_spec),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Cassi-Augmented Model Wrapper
# ═══════════════════════════════════════════════════════════════════════════════

class CassiAugmentedModel(nn.Module):
    def __init__(self, base_model, use_kv_compress=False, kv_budget_ratio=0.5, residual=False,
                 observer_bottleneck_dim=None, observer_low_rank=None):
        super().__init__()
        self.base = base_model
        self.residual = residual
        d_model = base_model.config.text_config.hidden_size
        vocab_size = base_model.config.text_config.vocab_size

        self.breath = BreathModule()
        self.berry = BerryMemory(d_model, n_slots=512)
        self.qi = QiFluid(d_model)
        self.chakra = ChakraTracker()
        self.observer = CordObserver(d_model, vocab_size, D=1040,
                                     bottleneck_dim=observer_bottleneck_dim,
                                     low_rank=observer_low_rank)
        self.specialists = SpecialistEnsemble(d_model, vocab_size, n_specialists=5, bottleneck=64)
        self.neuro = Neuroplasticizer()
        self.harmony = HarmonyGate(d_model, vocab_size, residual=residual)

        # Boundary-condition-residual KV cache compression
        self.use_kv_compress = use_kv_compress
        if use_kv_compress:
            n_layers = base_model.config.text_config.num_hidden_layers
            self.kv_compressor = ResidualKVCacheWrapper(
                num_layers=n_layers,
                budget_ratio=kv_budget_ratio,
            )
        else:
            self.kv_compressor = None

        self.to(DEVICE).to(torch.float32)
        self.eval()

    def reset_state(self):
        """Reset all mutable Cassi state between prompts."""
        self.breath.reset()
        self.qi.reset()
        self.neuro.reset()
        self.observer.reset_buffer()
        # Reset berry memory usage statistics (keys/values persist as learned memory)
        self.berry.counts.zero_()
        self.berry.ages.zero_()
        # NOTE: KV cache compressor disabled (Qwen3.5 uses hybrid attention)

    def generate_cassi(self, tok, prompt, max_new=64, base_temp=0.8, store_results=None, obs_boost=1.0, spec_boost=1.0):
        """
        Full Cassi-augmented generation loop.
        Returns (text, metadata_dict).
        obs_boost/spec_boost scale observer/specialist residuals (diagnostic).
        """
        inputs = tok(prompt, return_tensors="pt").to(DEVICE)
        input_ids = inputs["input_ids"][0].tolist()
        past_key_values = None
        self.reset_state()

        metas = []
        t0 = time.time()

        for step_idx in range(max_new):
            ids = torch.tensor(
                [input_ids] if past_key_values is None else [[input_ids[-1]]],
                device=DEVICE,
            )

            with torch.no_grad():
                out = self.base(
                    input_ids=ids,
                    past_key_values=past_key_values,
                    use_cache=True,
                    output_hidden_states=True,
                )
                # NOTE: KV cache compression disabled for Qwen3.5 because it uses
                # hybrid attention (LinearAttentionLayer with conv/recurrent states,
                # not standard key/value tensors). Boundary-condition-residual
                # compression is applicable to standard KV-cache architectures.

            base_logits = out.logits[0, -1, :].float()
            hidden = out.hidden_states[-1][0, -1, :].float()
            past_key_values = out.past_key_values

            # ── 1. Observer ──
            conf, imp, obs_logits = self.observer(hidden)
            conf_val = conf.item() if conf.numel() == 1 else conf.mean().item()
            imp_val = imp.item() if imp.numel() == 1 else imp.mean().item()

            # ── 2. Qi-Fluid ──
            qi_coherence = self.qi.update(hidden)
            qi_val = qi_coherence.item() if isinstance(qi_coherence, torch.Tensor) else qi_coherence

            # ── 3. Berry Memory ──
            berry_bias, berry_hit = self.berry.retrieve(hidden, k=5)
            if berry_bias is not None:
                berry_bias = berry_bias.float()

            # ── 4. Specialists ──
            spec_bias, spec_gates = self.specialists(hidden)
            spec_bias = spec_bias.float()

            # ── 5. Chakra Tracker ──
            chakra = self.chakra.track(out.hidden_states)

            # ── 6. Neuroplasticizer ──
            entropy = -(F.softmax(base_logits, dim=-1) * F.log_softmax(base_logits, dim=-1)).sum().item()
            triggered, rigidity = self.neuro.update(input_ids[-1], entropy)
            if triggered:
                self.breath.reset()
                self.qi.reset()

            # ── 7. Breath ──
            temp = self.breath.get_temp_scale(base_temp)
            temp *= self.neuro.get_boost()

            # ── 8. Harmony Gate ──
            if obs_logits is not None:
                obs_logits = obs_logits.float() * obs_boost
            if spec_bias is not None:
                spec_bias = spec_bias * spec_boost
            blended_logits, weights = self.harmony(
                base_logits, obs_logits, berry_bias, spec_bias, qi_val, conf_val
            )

            # ── 9. Sample ──
            probs = F.softmax(blended_logits / max(temp, 0.1), dim=-1)
            token = torch.multinomial(probs, num_samples=1).item()

            # ── 10. Store in Berry Memory ──
            self.berry.store(hidden)

            input_ids.append(token)

            meta = {
                "step": step_idx,
                "token": tok.decode([token]),
                "temp": temp,
                "conf": conf_val,
                "imp": imp_val,
                "qi": qi_val,
                "berry_hit": berry_hit,
                "rigidity": rigidity,
                "pulse": self.neuro.pulse_active,
                "dominant_chakra": chakra["dominant"],
                "chakra_entropy": chakra["entropy"],
                **weights,
            }
            metas.append(meta)

            if token == tok.eos_token_id:
                break

        dt = time.time() - t0
        text = tok.decode(input_ids, skip_special_tokens=True)

        summary = {
            "text": text,
            "tokens_generated": len(metas),
            "speed_tok_s": len(metas) / max(dt, 1e-6),
            "avg_temp": sum(m["temp"] for m in metas) / len(metas),
            "avg_conf": sum(m["conf"] for m in metas) / len(metas),
            "avg_imp": sum(m["imp"] for m in metas) / len(metas),
            "avg_qi": sum(m["qi"] for m in metas) / len(metas),
            "avg_rigidity": sum(m["rigidity"] for m in metas) / len(metas),
            "pulses_triggered": sum(1 for m in metas if m["pulse"]),
            "dominant_chakras": [m["dominant_chakra"] for m in metas],
            "chakra_entropy": [m["chakra_entropy"] for m in metas],
            "weights_history": {k: [m[k] for m in metas] for k in ["w_base", "w_obs", "w_berry", "w_spec"]},
        }

        if store_results is not None:
            store_results["cassi_full"] = summary

        return text, summary


# ═══════════════════════════════════════════════════════════════════════════════
# Baseline Generators (for comparison)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_standard(model, tok, prompt, max_new=64, temperature=0.8):
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    t0 = time.time()
    with torch.no_grad():
        out = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=True,
            temperature=temperature,
            pad_token_id=tok.eos_token_id,
        )
    dt = time.time() - t0
    text = tok.decode(out[0], skip_special_tokens=True)
    return text, max_new / max(dt, 1e-6)


def generate_breath_only(model, tok, prompt, max_new=64, temperature=0.8):
    breath = BreathModule()
    inputs = tok(prompt, return_tensors="pt").to(DEVICE)
    input_ids = inputs["input_ids"][0].tolist()
    past = None
    t0 = time.time()
    for _ in range(max_new):
        ids = torch.tensor([input_ids] if past is None else [[input_ids[-1]]], device=DEVICE)
        with torch.no_grad():
            out = model(input_ids=ids, past_key_values=past, use_cache=True)
        logits = out.logits[0, -1, :]
        past = out.past_key_values
        temp = breath.get_temp_scale(temperature)
        probs = F.softmax(logits / max(temp, 0.1), dim=-1)
        token = torch.multinomial(probs, num_samples=1).item()
        input_ids.append(token)
        if token == tok.eos_token_id:
            break
    dt = time.time() - t0
    return tok.decode(input_ids, skip_special_tokens=True), len(input_ids) / max(dt, 1e-6)


# ═══════════════════════════════════════════════════════════════════════════════
# Model Loading
# ═══════════════════════════════════════════════════════════════════════════════

def load_base_model():
    print(f"Loading Qwen3.5-4B from {LOCAL_MODEL_DIR} ...")
    config = AutoConfig.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True)
    with torch.device("meta"):
        model = Qwen3_5ForConditionalGeneration(config)

    with open(os.path.join(LOCAL_MODEL_DIR, "model.safetensors.index.json")) as f:
        index = json.load(f)

    shards = sorted(set(index["weight_map"].values()))
    for shard_name in shards:
        sd = load_file(os.path.join(LOCAL_MODEL_DIR, shard_name), device="cuda:0")
        model.load_state_dict(sd, strict=False, assign=True)
        del sd
        torch.cuda.empty_cache()

    for name, param in list(model.named_parameters()):
        if param.is_meta:
            path, p = name.rsplit(".", 1)
            m = model.get_submodule(path)
            setattr(m, p, nn.Parameter(torch.empty_like(param, device="cuda:0"), requires_grad=param.requires_grad))
    for name, buf in list(model.named_buffers()):
        if buf.is_meta:
            path, b = name.rsplit(".", 1)
            m = model.get_submodule(path)
            setattr(m, b, torch.empty_like(buf, device="cuda:0"))

    for name, mod in model.named_modules():
        if hasattr(mod, "inv_freq") and hasattr(mod, "compute_default_rope_parameters"):
            inv, scale = mod.compute_default_rope_parameters(mod.config, device="cuda:0")
            mod.inv_freq = inv
            mod.original_inv_freq = inv.clone()
            mod.attention_scaling = scale

    model.tie_weights()
    for p in model.parameters():
        p._is_hf_initialized = True
    for b in model.buffers():
        b._is_hf_initialized = True

    model.eval()
    print(f"Base model ready. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
    return model


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--kv-compress", action="store_true", help="Use boundary-condition-residual KV cache compression")
    parser.add_argument("--kv-budget", type=float, default=0.5, help="KV cache budget ratio (0.5 = keep 50%%)")
    parser.add_argument("--checkpoint", type=str, default=None, help="Path to trained Cassi checkpoint")
    parser.add_argument("--prompt", type=str, default="The golden ratio appears in nature", help="Generation prompt")
    parser.add_argument("--residual", action="store_true", help="Use residual logit mode (Cassi components correct base model)")
    parser.add_argument("--observer-bottleneck-dim", type=int, default=None,
                        help="Bottleneck dim before CordObserver field projection")
    parser.add_argument("--observer-low-rank", type=int, default=None,
                        help="Rank for low-rank CordObserver logit projection")
    parser.add_argument("--max-new-tokens", type=int, default=64, help="Number of tokens to generate")
    parser.add_argument("--temperature", type=float, default=0.8, help="Sampling temperature")
    parser.add_argument("--obs-boost", type=float, default=1.0, help="Scale observer residual logits (diagnostic)")
    parser.add_argument("--spec-boost", type=float, default=1.0, help="Scale specialist residual logits (diagnostic)")
    args = parser.parse_args()

    base_model = load_base_model()
    tok = AutoTokenizer.from_pretrained(LOCAL_MODEL_DIR, trust_remote_code=True, use_fast=True)
    prompt = args.prompt
    results = {"prompt": prompt, "kv_compress": args.kv_compress, "kv_budget": args.kv_budget}

    max_new = args.max_new_tokens
    temperature = args.temperature

    # ── Standard baseline ──
    print("=" * 70)
    print("BASELINE: Standard generation")
    print("=" * 70)
    text, speed = generate_standard(base_model, tok, prompt, max_new=max_new, temperature=temperature)
    print(f"Speed: {speed:.1f} tok/s")
    print(f"Output:\n{text}\n")
    results["standard"] = {"text": text, "speed": speed}

    # ── Breath-only baseline ──
    print("=" * 70)
    print("BASELINE: Breath-only generation")
    print("=" * 70)
    text, speed = generate_breath_only(base_model, tok, prompt, max_new=max_new, temperature=temperature)
    print(f"Speed: {speed:.1f} tok/s")
    print(f"Output:\n{text}\n")
    results["breath_only"] = {"text": text, "speed": speed}

    # ── Full Cassi ──
    print("=" * 70)
    print("CASSI FULL: All components combined")
    print("=" * 70)
    cassi = CassiAugmentedModel(base_model, use_kv_compress=args.kv_compress, kv_budget_ratio=args.kv_budget,
                                residual=args.residual,
                                observer_bottleneck_dim=args.observer_bottleneck_dim,
                                observer_low_rank=args.observer_low_rank)
    if args.checkpoint:
        print(f"Loading checkpoint: {args.checkpoint}")
        ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
        # Detect observer-only checkpoint (no 'observer.' prefix)
        if not any(k.startswith("observer.") for k in ckpt.keys()):
            ckpt = {f"observer.{k}": v for k, v in ckpt.items()}
        # Filter out base model weights (already loaded, frozen, huge)
        ckpt = {k: v for k, v in ckpt.items() if not k.startswith("base.")}
        missing, unexpected = cassi.load_state_dict(ckpt, strict=False)
        if missing:
            print(f"  Missing keys: {len(missing)}")
        if unexpected:
            print(f"  Unexpected keys: {len(unexpected)}")
        print("Checkpoint loaded.")
    print(f"Cassi modules ready. VRAM: {torch.cuda.memory_allocated() / 1e9:.2f} GB")
    if args.kv_compress:
        print(f"KV compression enabled (budget={args.kv_budget:.0%})")

    text, summary = cassi.generate_cassi(tok, prompt, max_new=max_new, base_temp=temperature, store_results=results, obs_boost=args.obs_boost, spec_boost=args.spec_boost)
    print(f"Speed: {summary['speed_tok_s']:.1f} tok/s")
    print(f"Avg temp: {summary['avg_temp']:.3f}")
    print(f"Avg confidence: {summary['avg_conf']:.3f}")
    print(f"Avg importance: {summary['avg_imp']:.3f}")
    print(f"Avg Qi: {summary['avg_qi']:.3f}")
    print(f"Avg rigidity: {summary['avg_rigidity']:.3f}")
    print(f"Pulses triggered: {summary['pulses_triggered']}")
    ch_entropy = sum(summary['chakra_entropy']) / len(summary['chakra_entropy'])
    print(f"Chakra entropy: {ch_entropy:.3f}")
    wh = summary['weights_history']
    print(f"Weight averages: base={sum(wh['w_base'])/len(wh['w_base']):.3f} "
          f"obs={sum(wh['w_obs'])/len(wh['w_obs']):.3f} "
          f"berry={sum(wh['w_berry'])/len(wh['w_berry']):.3f} "
          f"spec={sum(wh['w_spec'])/len(wh['w_spec']):.3f}")
    print(f"Output:\n{text}\n")

    # ── Second prompt (to test Berry memory retention) ──
    prompt2 = "Explain how the golden ratio relates to the Fibonacci sequence"

    print("=" * 70)
    print("BASELINE: Standard generation on prompt 2")
    print("=" * 70)
    text2_std, speed2 = generate_standard(base_model, tok, prompt2, max_new=max_new, temperature=temperature)
    print(f"Speed: {speed2:.1f} tok/s")
    print(f"Output:\n{text2_std}\n")

    print("=" * 70)
    print("CASSI FULL: Second prompt (memory should retain context)")
    print("=" * 70)
    text2, summary2 = cassi.generate_cassi(tok, prompt2, max_new=max_new, base_temp=temperature, store_results=results, obs_boost=args.obs_boost, spec_boost=args.spec_boost)
    print(f"Speed: {summary2['speed_tok_s']:.1f} tok/s")
    print(f"Avg Qi: {summary2['avg_qi']:.3f}")
    print(f"Pulses: {summary2['pulses_triggered']}")
    print(f"Output:\n{text2}\n")
    path = "experiments/qwen_4b_cassi_full_results.json"
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Saved results to {path}")


if __name__ == "__main__":
    main()
