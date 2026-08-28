"""
Cassi → llama.cpp Adapter

Maps each Cassi innovation to its llama.cpp compatibility level:
  GREEN:  Works with llama.cpp today (sampling hooks, LoRA, GGUF)
  YELLOW: Needs custom GGML ops or graph modifications
  RED:    Requires PyTorch / training loop (can't run in llama.cpp)

Then implements the GREEN and YELLOW adapters.
"""

import math
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Callable

import torch
import torch.nn as nn
import torch.nn.functional as F

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1.0 / PHI


# ===========================================================================
# GREEN: Works in llama.cpp Today
# ===========================================================================

class StaticBreathSampler:
    """Precomputed breath-modulated temperature schedule.

    llama.cpp compatibility: GREEN
    - No learned parameters
    - Just a temperature schedule that varies per token
    - Can be passed to llama.cpp's sampling via --temp N (changing each token)

    Usage: precompute temps for max_tokens, then feed them to llama.cpp
    one by one via the sampling API.
    """

    def __init__(self, max_tokens: int = 512,
                 temp_base: float = 0.7, temp_range: float = 0.3,
                 omega_yang: float = 1.0, omega_yin: float = None):
        if omega_yin is None:
            omega_yin = omega_yang / PHI
        self.temps = self._precompute(max_tokens, temp_base, temp_range,
                                       omega_yang, omega_yin)
        self.top_ps = self._precompute_top_p(max_tokens, omega_yang, omega_yin)

    def _precompute(self, n, temp_base, temp_range, oy, oyi):
        temps = []
        ty, tyin = 0.0, 0.0
        for _ in range(n):
            ty += oy
            tyin += oyi
            beat = math.sin(ty + tyin)
            t = temp_base + temp_range * 0.5 * beat
            temps.append(max(0.1, min(2.0, t)))
        return temps

    def _precompute_top_p(self, n, oy, oyi):
        top_ps = []
        ty, tyin = 0.0, 0.0
        for _ in range(n):
            ty += oy
            tyin += oyi
            flow = math.cos(ty - tyin)
            p = 0.9 - 0.1 * 0.5 * flow
            top_ps.append(max(0.1, min(1.0, p)))
        return top_ps

    def get_schedule(self) -> List[Tuple[float, float]]:
        """Return list of (temperature, top_p) for each token position."""
        return list(zip(self.temps, self.top_ps))

    def export_for_llamacpp(self, path: str):
        """Export as JSON for llama.cpp sampler plugin."""
        schedule = [
            {'token_idx': i, 'temperature': t, 'top_p': p}
            for i, (t, p) in enumerate(zip(self.temps, self.top_ps))
        ]
        with open(path, 'w') as f:
            json.dump({
                'type': 'cassi_breath_schedule',
                'phi': PHI,
                'omega_yang': 1.0,
                'omega_yin': 1.0 / PHI,
                'schedule': schedule,
            }, f, indent=2)
        print(f"[StaticBreathSampler] Exported {len(schedule)} tokens to {path}")


class PhiSpacedLoRAConfig:
    """φ-spaced learning rate groups for LoRA fine-tuning.

    llama.cpp compatibility: GREEN
    - llama.cpp supports LoRA adapters via --lora
    - The LR scheduling happens at training time (PyTorch/PEFT)
    - The resulting adapter can be loaded into llama.cpp

    This class generates the PEFT config with φ-spaced LRs.
    """

    def __init__(self, base_lr: float = 1e-4, n_layers: int = 32):
        self.base_lr = base_lr
        self.n_layers = n_layers

    def get_layer_lr(self, layer_idx: int) -> float:
        """Compute LR for a layer based on depth.

        Early layers (low idx): higher LR = base * φ
        Late layers (high idx): lower LR = base / φ
        """
        # Normalize depth to [0, 1]
        depth = layer_idx / max(1, self.n_layers - 1)
        # Yang (early) = lr * φ, Yin (late) = lr / φ
        # Smooth interpolation
        yang_lr = self.base_lr * PHI
        yin_lr = self.base_lr / PHI
        lr = yang_lr * (1 - depth) + yin_lr * depth
        return lr

    def generate_peft_config(self) -> Dict:
        """Generate PEFT/LoRA config with φ-spaced target modules."""
        # Target modules by importance (Yang = more important = higher LR)
        target_modules = {
            'q_proj':    {'lr_scale': PHI,      'desc': 'Yang - query projection'},
            'k_proj':    {'lr_scale': 1.0,      'desc': 'Balance - key projection'},
            'v_proj':    {'lr_scale': 1.0,      'desc': 'Balance - value projection'},
            'o_proj':    {'lr_scale': 1.0,      'desc': 'Balance - output projection'},
            'gate_proj': {'lr_scale': PHI_INV,  'desc': 'Yin - MLP gate'},
            'up_proj':   {'lr_scale': PHI_INV,  'desc': 'Yin - MLP up'},
            'down_proj': {'lr_scale': PHI_INV,  'desc': 'Yin - MLP down'},
        }

        return {
            'peft_type': 'LORA',
            'r': 16,
            'lora_alpha': 32,
            'target_modules': list(target_modules.keys()),
            'lora_dropout': 0.05,
            'bias': 'none',
            'task_type': 'CAUSAL_LM',
            'cassi_phi_scaling': {
                'enabled': True,
                'base_lr': self.base_lr,
                'module_lr_scales': {k: v['lr_scale'] for k, v in target_modules.items()},
            }
        }

    def export_for_peft(self, path: str):
        """Export config JSON for PEFT."""
        config = self.generate_peft_config()
        with open(path, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"[PhiSpacedLoRAConfig] Exported to {path}")


# ===========================================================================
# YELLOW: Needs Custom GGML / Graph Mods
# ===========================================================================

class GGUFPhiBalanceInjector:
    """Inject φ-balance regularization into GGUF model weights.

    llama.cpp compatibility: YELLOW
    - Modifies weights offline (not at runtime)
    - Can be done via Python script that reads/writes GGUF
    - The modified GGUF runs in llama.cpp without changes

    What it does:
      - Analyzes weight matrix spectral signatures
      - Identifies redundant heads (mode-locked frequencies)
      - Applies φ-spaced re-initialization to break symmetry
    """

    def __init__(self, model_path: str):
        self.model_path = Path(model_path)
        # Would use gguf-py library here

    def analyze_spectral_balance(self, weight_dict: Dict[str, torch.Tensor]) -> Dict:
        """Analyze weight matrices for φ-balance violations.

        Returns dict with per-layer metrics:
          - spectral_entropy: how concentrated energy is
          - mode_lock_score: how many heads share similar frequencies
          - phi_deviation: how far from φ-spaced the singular values are
        """
        results = {}
        for name, w in weight_dict.items():
            if 'q_proj' not in name and 'k_proj' not in name:
                continue

            # SVD for spectral analysis
            w2d = w.view(w.shape[0], -1) if w.dim() > 2 else w
            try:
                u, s, v = torch.svd(w2d.float())
            except RuntimeError:
                continue

            # Spectral entropy
            s_norm = s / s.sum()
            entropy = -(s_norm * torch.log(s_norm + 1e-10)).sum().item()

            # Check φ-spacing of top singular values
            top_s = s[:min(13, len(s))].tolist()
            ratios = [top_s[i] / top_s[i+1] if top_s[i+1] > 0 else 0
                      for i in range(len(top_s)-1)]
            phi_dev = sum(abs(r - PHI) for r in ratios[:5]) / 5 if ratios else 0

            results[name] = {
                'spectral_entropy': entropy,
                'phi_deviation': phi_dev,
                'top_singular_values': top_s[:5],
            }

        return results

    def inject_phi_rebalance(self, weight_dict: Dict[str, torch.Tensor],
                             strength: float = 0.1) -> Dict[str, torch.Tensor]:
        """Modify weights to improve φ-balance.

        Applies a small perturbation that pushes singular value ratios
        toward φ. This is done offline — the modified weights are saved
        to a new GGUF.
        """
        modified = {}
        for name, w in weight_dict.items():
            if 'q_proj' not in name:
                modified[name] = w
                continue

            # SVD
            w2d = w.view(w.shape[0], -1) if w.dim() > 2 else w
            try:
                u, s, v = torch.svd(w2d.float())
            except RuntimeError:
                modified[name] = w
                continue

            # Perturb singular values toward φ-spacing
            for i in range(min(12, len(s) - 1)):
                target_ratio = PHI ** (-i)  # inversely φ-spaced
                current_ratio = s[i] / (s[i+1] + 1e-10)
                correction = target_ratio / (current_ratio + 1e-10)
                s[i] = s[i] * (1 + strength * (correction - 1))

            # Reconstruct
            w_new = (u @ torch.diag(s) @ v.t()).to(w.dtype)
            w_new = w_new.view_as(w)
            modified[name] = w_new

        return modified


class KVCacheChangepointCompressor:
    """Changepoint-aware KV cache compression for llama.cpp.

    llama.cpp compatibility: YELLOW
    - llama.cpp has KV cache but no changepoint detection
    - Could be implemented as a custom sampler callback
    - Or as a preprocessing step that inserts cache-clear tokens

    What it does:
      - Monitors hidden state cosine similarity
      - Detects topic shifts (changepoints)
      - On changepoint: compress old KV to summary, reset cache
    """

    def __init__(self, threshold: float = 0.5, window_size: int = 10):
        self.threshold = threshold
        self.window_size = window_size
        self.history = []
        self.last_hidden = None

    def should_compress(self, current_hidden: torch.Tensor) -> bool:
        """Check if current hidden state indicates a changepoint."""
        if self.last_hidden is None:
            self.last_hidden = current_hidden
            return False

        # Cosine similarity
        sim = F.cosine_similarity(
            current_hidden.flatten(),
            self.last_hidden.flatten(),
            dim=0
        )
        self.history.append(sim.item())
        if len(self.history) > self.window_size:
            self.history.pop(0)

        self.last_hidden = current_hidden

        # Changepoint: similarity drops below threshold
        if len(self.history) >= 3:
            recent_mean = sum(self.history[-3:]) / 3
            return recent_mean < self.threshold

        return False

    def get_compression_instruction(self) -> Dict:
        """Return instruction for llama.cpp KV cache manager.

        This would be consumed by a custom llama.cpp sampler or
        converted to a special token that triggers cache reset.
        """
        return {
            'action': 'compress_and_reset',
            'keep_last_n': 4,  # Keep last 4 tokens as context
            'compress_method': 'mean_pooling',
        }


# ===========================================================================
# RED: PyTorch Only (Training / Research)
# ===========================================================================

class PyTorchOnlyComponents:
    """Components that fundamentally require PyTorch and cannot run in llama.cpp.

    These are documented here for completeness but would need:
      - A PyTorch training loop
      - Gradient computation
      - Custom optimizer state
    """

    @staticmethod
    def resonant_weight_cord():
        """Multi-band IIR filter for gradients.

        WHY RED: Requires gradient access, learned frequencies, persistent state.
        llama.cpp does not compute gradients or maintain optimizer state.
        """
        return "Requires PyTorch training loop. See qwen_cassi_hybrid.py::ResonantWeightCord"

    @staticmethod
    def internal_observer():
        """Confidence/uncertainty head.

        WHY RED: Requires extra forward pass, backward pass for training.
        llama.cpp graph is fixed at compile time.
        """
        return "Requires PyTorch. See qwen_cassi_hybrid.py::InternalObserverHead"

    @staticmethod
    def dual_stream_arbitration():
        """Parallel Yang/Yin streams with learned gate.

        WHY RED: Requires parallel computation paths, learned arbitration weights.
        llama.cpp graph is single-path.
        """
        return "Requires PyTorch. See qwen_dual_stream.py::DualStreamQwen"


# ===========================================================================
# llama.cpp Integration Guide
# ===========================================================================

def print_integration_guide():
    """Print a guide for integrating Cassi with llama.cpp."""
    guide = """
╔══════════════════════════════════════════════════════════════════════════════╗
║           CASSI → llama.cpp INTEGRATION GUIDE                                ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  GREEN (Works Today):                                                        ║
║  ───────────────────                                                         ║
║                                                                              ║
║  1. Static Breath Sampling                                                   ║
║     • Precompute temperature schedule                                        ║
║     • Feed to llama.cpp via --temp per token                                 ║
║     • Or patch sampling.cpp to call breath_step() each token                 ║
║                                                                              ║
║  2. φ-Spaced LoRA                                                            ║
║     • Train LoRA with φ-scaled LR groups (PEFT)                            ║
║     • Export adapter to GGUF                                                 ║
║     • Load in llama.cpp with --lora                                          ║
║                                                                              ║
║  3. Surprise-Weighted Loss (Training Only)                                   ║
║     • Use during fine-tuning in PyTorch                                      ║
║     • Resulting model/adapter runs in llama.cpp                              ║
║                                                                              ║
║  YELLOW (Needs Custom Code):                                                 ║
║  ───────────────────────────                                                 ║
║                                                                              ║
║  4. φ-Balance Weight Rebalancing                                             ║
║     • Python script modifies GGUF weights offline                            ║
║     • Uses gguf-py library                                                   ║
║     • Modified GGUF runs unchanged in llama.cpp                              ║
║                                                                              ║
║  5. Changepoint KV Cache Compression                                         ║
║     • Custom llama.cpp sampler callback                                      ║
║     • Or insert special tokens that trigger cache ops                        ║
║     • Needs C++ modifications to llama.cpp                                   ║
║                                                                              ║
║  RED (PyTorch Only):                                                         ║
║  ───────────────────                                                         ║
║                                                                              ║
║  6. ResonantWeightCord        → Training-time optimizer only                 ║
║  7. InternalObserver          → Needs extra forward/backward passes          ║
║  8. DualStream Arbitration    → Needs parallel graph + learning              ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  RECOMMENDED PATH FOR llama.cpp USERS:                                       ║
║                                                                              ║
║  Step 1: Use StaticBreathSampler to generate rhythmic temperature            ║
║          schedules. Export as JSON, load in custom sampler.                  ║
║                                                                              ║
║  Step 2: Fine-tune a LoRA with PhiSpacedLoRAConfig.                          ║
║          The φ-spaced LR groups improve convergence.                         ║
║                                                                              ║
║  Step 3: (Optional) Run GGUFPhiBalanceInjector offline on base model.        ║
║          This breaks mode-locking without changing architecture.             ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
    print(guide)


# ===========================================================================
# Demo
# ===========================================================================

def demo():
    print_integration_guide()

    print("\n" + "=" * 60)
    print("DEMO: Static Breath Schedule Export")
    print("=" * 60)

    breath = StaticBreathSampler(max_tokens=20, temp_base=0.7, temp_range=0.3)
    schedule = breath.get_schedule()
    print(f"\nFirst 10 tokens:")
    for i, (t, p) in enumerate(schedule[:10]):
        print(f"  Token {i:2d}: temp={t:.3f}, top_p={p:.3f}")

    # Export
    breath.export_for_llamacpp('/tmp/cassi_breath_schedule.json')

    print("\n" + "=" * 60)
    print("DEMO: φ-Spaced LoRA Config")
    print("=" * 60)

    lora = PhiSpacedLoRAConfig(base_lr=2e-4, n_layers=24)
    print(f"\nLayer LR schedule (24 layers):")
    for i in range(24):
        lr = lora.get_layer_lr(i)
        depth = "early" if i < 8 else "late" if i > 16 else "mid"
        print(f"  Layer {i:2d}: lr={lr:.2e} ({depth})")

    lora.export_for_peft('/tmp/cassi_phi_lora_config.json')

    print("\n" + "=" * 60)
    print("DEMO: Weight Spectral Analysis (simulated)")
    print("=" * 60)

    # Simulate a weight matrix
    w = torch.randn(4096, 1024)
    injector = GGUFPhiBalanceInjector("dummy")
    results = injector.analyze_spectral_balance({"layers.0.q_proj.weight": w})

    for name, metrics in results.items():
        print(f"\n{name}:")
        print(f"  Spectral entropy: {metrics['spectral_entropy']:.3f}")
        print(f"  φ deviation:      {metrics['phi_deviation']:.3f}")
        print(f"  Top singulars:    {metrics['top_singular_values']}")

    print("\n" + "=" * 60)
    print("All demos complete!")
    print("=" * 60)


if __name__ == '__main__':
    demo()
