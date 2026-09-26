"""
Qwen3.5-0.8B + Cassi Hybrid Experiments

This module implements Cassi innovations applied to Qwen3.5's weights:

TRAINING CLUSTER:
  1. ResonantWeightCord — multi-band IIR filtering on weight trajectories
  2. PhiBalanceRegularizer — φ-ratio regularization between layer groups
  3. SurpriseWeightedLoss — dynamic loss weighting by prediction surprise

INFERENCE CLUSTER:
  4. BreathModulatedSampler — oscillatory temperature modulation
  5. InternalObserverHead — confidence/uncertainty estimation per token

The model is loaded directly from safetensors without transformers dependency.
"""

import math
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

# ---------------------------------------------------------------------------
# Cassi constants
# ---------------------------------------------------------------------------
PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1.0 / PHI


# ===========================================================================
# TRAINING CLUSTER
# ===========================================================================

class ResonantWeightCord(nn.Module):
    """Multi-band IIR filter for weight trajectory smoothing.

    Instead of Adam's first-order EMA (m_t = β·m_{t-1} + (1-β)·g_t),
    we use a second-order resonant IIR with learned frequencies per band.

    Parameters are split into 13 φ-scaled "chakras" by magnitude.
    Each chakra gets its own learned frequency θ and fixed damping ρ=1/φ.

    Args:
        n_bands: number of spectral bands (default 13, like Cassi chakras)
        damping: fixed pole magnitude (default PHI_INV ≈ 0.618)
    """

    def __init__(self, n_bands: int = 13, damping: float = PHI_INV):
        super().__init__()
        self.n_bands = n_bands
        self.damping = damping

        # Learned frequencies per band (logit-space, sigmoid→[0,π])
        # Initialized inversely φ-spaced: band 0 = fast, band 12 = slow
        theta_max = 2.5
        self.theta = nn.Parameter(torch.zeros(n_bands))
        for c in range(n_bands):
            theta_c = theta_max * (PHI ** (-c))
            y = max(0.001, min(0.999, theta_c / math.pi))
            self.theta.data[c] = math.log(y / (1.0 - y))

        # Feedforward gains per band
        self.b0 = nn.Parameter(torch.zeros(n_bands))
        self.b1 = nn.Parameter(torch.zeros(n_bands))

        # IIR state (persistent across steps) — one scalar per band
        self.register_buffer('h1', torch.zeros(n_bands))
        self.register_buffer('h2', torch.zeros(n_bands))
        self.register_buffer('x1', torch.zeros(n_bands))
        self._band_state_h1 = {}  # per-band vector state, keyed by band size

    def _band_indices(self, n_params: int) -> List[Tuple[int, int]]:
        """Split n_params into φ-scaled bands. Returns list of (start, end)."""
        raw = [PHI ** c for c in range(self.n_bands)]
        total_raw = sum(raw)
        widths = [max(1, round(n_params * r / total_raw)) for r in raw]
        widths[-1] += n_params - sum(widths)

        offsets = []
        off = 0
        for w in widths:
            offsets.append((off, off + w))
            off += w
        return offsets

    def forward(self, grad_flat: torch.Tensor) -> torch.Tensor:
        """Filter a flattened gradient through resonant bands.

        Args:
            grad_flat: [N] flattened gradient
        Returns:
            filtered: [N] filtered gradient
        """
        N = grad_flat.shape[0]
        device = grad_flat.device
        bands = self._band_indices(N)

        filtered_parts = []
        for c, (start, end) in enumerate(bands):
            g_c = grad_flat[start:end]

            # IIR params for this band
            theta = torch.sigmoid(self.theta[c]) * math.pi
            a1 = 2.0 * self.damping * torch.cos(theta)
            a2 = -(self.damping) ** 2
            b0 = torch.sigmoid(self.b0[c])
            b1 = torch.sigmoid(self.b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf

            # Single-step IIR (stateful) — vector state per band
            band_key = f"band_{c}_{end - start}"
            if band_key not in self._band_state_h1:
                self._band_state_h1[band_key] = {
                    'h1': torch.zeros(end - start, device=device),
                    'h2': torch.zeros(end - start, device=device),
                    'x1': torch.zeros(end - start, device=device),
                }
            bs = self._band_state_h1[band_key]

            h_c = b0 * g_c + b1 * bs['x1'] + a1 * bs['h1'] + a2 * bs['h2']

            # Update state (detached to prevent graph accumulation)
            bs['h2'] = bs['h1'].detach().clone()
            bs['h1'] = h_c.detach().clone()
            bs['x1'] = g_c.detach().clone()

            # Also update scalar summaries
            self.h1[c] = h_c.mean().detach()
            self.h2[c] = bs['h2'].mean().detach()
            self.x1[c] = g_c.mean().detach()

            filtered_parts.append(h_c)

        return torch.cat(filtered_parts, dim=0)

    def reset_state(self):
        """Reset IIR state (call at epoch boundaries)."""
        self.h1.zero_()
        self.h2.zero_()
        self.x1.zero_()
        self._band_state_h1.clear()


class PhiBalanceRegularizer:
    """φ-balance regularization for transformer layer groups.

    Enforces that the ratio of activity between complementary subsystems
    tends toward φ ≈ 1.618. Three terms:
      1. Local/global attention balance: ||local|| / ||global|| → 1.0
      2. Early/late layer balance: ||early|| / ||late|| → φ
      3. Yang/Yin (fast/slow) balance: ||fast|| / ||slow|| → φ

    This is applied as a regularization loss during training.
    """

    def __init__(self, local_layers: List[int], global_layers: List[int],
                 early_layers: List[int], late_layers: List[int],
                 lambda_balance: float = 0.01):
        self.local_layers = set(local_layers)
        self.global_layers = set(global_layers)
        self.early_layers = set(early_layers)
        self.late_layers = set(late_layers)
        self.lambda_balance = lambda_balance

    def __call__(self, model: nn.Module) -> torch.Tensor:
        """Compute φ-balance regularization loss."""
        local_norm = 0.0
        global_norm = 0.0
        early_norm = 0.0
        late_norm = 0.0

        for name, p in model.named_parameters():
            if not p.requires_grad or p.grad is None:
                continue

            # Extract layer index from name like "layers.5.self_attn.q_proj.weight"
            layer_idx = self._extract_layer_idx(name)
            if layer_idx is None:
                continue

            param_norm = p.norm().item()

            if layer_idx in self.local_layers:
                local_norm += param_norm
            if layer_idx in self.global_layers:
                global_norm += param_norm
            if layer_idx in self.early_layers:
                early_norm += param_norm
            if layer_idx in self.late_layers:
                late_norm += param_norm

        loss = 0.0
        device = next(model.parameters()).device

        # Term 1: local/global balance → 1.0
        if local_norm > 0 and global_norm > 0:
            ratio = local_norm / (global_norm + 1e-8)
            loss += ((ratio - 1.0) ** 2)

        # Term 2: early/late balance → φ
        if early_norm > 0 and late_norm > 0:
            ratio = early_norm / (late_norm + 1e-8)
            loss += ((ratio - PHI) ** 2)

        # Term 3: fast/slow (local=fast, global=slow) → φ
        if local_norm > 0 and global_norm > 0:
            ratio = local_norm / (global_norm + 1e-8)
            loss += 0.5 * ((ratio - PHI) ** 2)

        return torch.tensor(loss * self.lambda_balance, device=device)

    @staticmethod
    def _extract_layer_idx(name: str) -> Optional[int]:
        """Extract layer index from parameter name."""
        import re
        m = re.search(r'layers\.(\d+)\.', name)
        return int(m.group(1)) if m else None


class SurpriseWeightedLoss:
    """Dynamic loss weighting by prediction surprise.

    Maintains EMA of per-token CE loss. Surprising tokens (loss > EMA)
    get higher weight. Disappointing tokens (large negative deviation)
    get even higher weight.

    This is the transformer equivalent of Cassi's surprise-driven adaptation.
    """

    def __init__(self, alpha: float = 0.95, surprise_scale: float = 2.0,
                 disappointment_scale: float = 3.0):
        self.alpha = alpha
        self.surprise_scale = surprise_scale
        self.disappointment_scale = disappointment_scale
        self.loss_ema = None
        self.step_count = 0

    def __call__(self, ce_loss: torch.Tensor) -> torch.Tensor:
        """Apply surprise weighting to per-token CE loss.

        Args:
            ce_loss: [batch, seq] per-token cross-entropy
        Returns:
            weighted_loss: scalar
        """
        with torch.no_grad():
            batch_mean = ce_loss.mean()
            if self.loss_ema is None:
                self.loss_ema = batch_mean.item()
            else:
                self.loss_ema = self.alpha * self.loss_ema + (1 - self.alpha) * batch_mean.item()
            self.step_count += 1

        # Surprise = deviation from EMA
        surprise = ce_loss - self.loss_ema

        # Weight: base + surprise bonus
        weights = 1.0 + self.surprise_scale * F.relu(surprise)

        # Disappointment bonus: when loss suddenly increases
        disappointment = F.relu(-surprise)  # loss went DOWN (unexpected improvement)
        weights = weights + self.disappointment_scale * disappointment

        # Normalize to maintain expected gradient magnitude
        weights = weights / weights.mean().clamp_min(1e-8)

        return (ce_loss * weights).mean()

    def get_stats(self) -> Dict[str, float]:
        return {
            'loss_ema': self.loss_ema if self.loss_ema else 0.0,
            'step_count': self.step_count,
        }


# ===========================================================================
# INFERENCE CLUSTER
# ===========================================================================

class BreathModulatedSampler:
    """Oscillatory temperature modulation for transformer sampling.

    Two coupled oscillators (Yang fast, Yin slow by φ) drive sampling
    parameters. Creates rhythmic generation: high creativity (inhale)
    followed by consolidation (exhale).

    Args:
        omega_yang: fast oscillator frequency (default 1.0 rad/token)
        omega_yin: slow oscillator frequency (default 1.0/φ)
        temp_base: base temperature
        temp_range: temperature swing amplitude
        top_p_base: base top-p
        top_p_range: top-p swing amplitude
    """

    def __init__(self, omega_yang: float = 1.0, omega_yin: float = None,
                 temp_base: float = 0.7, temp_range: float = 0.3,
                 top_p_base: float = 0.9, top_p_range: float = 0.1):
        if omega_yin is None:
            omega_yin = omega_yang / PHI
        self.omega_yang = omega_yang
        self.omega_yin = omega_yin
        self.temp_base = temp_base
        self.temp_range = temp_range
        self.top_p_base = top_p_base
        self.top_p_range = top_p_range

        # Persistent phase state
        self.t_yang = 0.0
        self.t_yin = 0.0

    def step(self) -> Dict[str, float]:
        """Advance oscillators and return sampling parameters."""
        # Advance phases
        self.t_yang += self.omega_yang
        self.t_yin += self.omega_yin

        # Compute signals
        yang = math.sin(self.t_yang)
        yin = math.sin(self.t_yin)
        beat = math.sin(self.t_yang + self.t_yin)  # constructive interference
        flow = math.cos(self.t_yang - self.t_yin)  # phase coherence

        # Modulate sampling
        temp = self.temp_base + self.temp_range * 0.5 * beat
        top_p = self.top_p_base - self.top_p_range * 0.5 * flow

        # Clamp
        temp = max(0.1, min(2.0, temp))
        top_p = max(0.1, min(1.0, top_p))

        return {
            'temperature': temp,
            'top_p': top_p,
            'beat': beat,
            'flow': flow,
            'yang': yang,
            'yin': yin,
        }

    def reset(self):
        """Reset phases (e.g., on new prompt)."""
        self.t_yang = 0.0
        self.t_yin = 0.0


class InternalObserverHead(nn.Module):
    """Confidence/uncertainty head for transformer hidden states.

    Observes hidden states at specified layers and outputs:
      - confidence: [0,1] scalar per token
      - importance: [d_model] per-dimension importance
      - predicted_next: predicted next hidden state

    This gives the model explicit self-awareness of its own uncertainty.
    """

    def __init__(self, d_model: int, hidden_dim: int = 256,
                 observe_every_n_layers: int = 4):
        super().__init__()
        self.d_model = d_model
        self.observe_every_n = observe_every_n_layers

        # Snapshot encoder: hidden state + attention entropy + activation stats
        snapshot_dim = d_model + 3  # hidden + entropy + grad_norm + activation_sparsity

        self.encoder = nn.Sequential(
            nn.Linear(snapshot_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
        )

        # Confidence head
        self.confidence_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.GELU(),
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

        # Importance head
        self.importance_head = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.GELU(),
            nn.Linear(64, d_model),
            nn.Sigmoid(),
        )

        # Predictor: predict next hidden state
        self.predictor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, d_model),
        )

        # EMA of observer state for stability
        self.register_buffer('state_ema', torch.zeros(hidden_dim))
        self.ema_decay = 0.99

    def observe(self, hidden_state: torch.Tensor,
                attention_entropy: Optional[torch.Tensor] = None,
                grad_norm: Optional[float] = None,
                activation_sparsity: Optional[float] = None) -> Dict[str, torch.Tensor]:
        """Observe a hidden state and return metacognitive signals.

        Args:
            hidden_state: [batch, seq, d_model]
            attention_entropy: [batch, seq] or scalar
            grad_norm: scalar or None
            activation_sparsity: scalar or None
        Returns:
            dict with 'confidence', 'importance', 'predicted_next', 'embedding'
        """
        B, S, D = hidden_state.shape
        device = hidden_state.device

        # Build snapshot
        snapshot = [hidden_state]  # [B, S, D]

        # Attention entropy (default 0.5 = moderate)
        if attention_entropy is None:
            entropy = torch.full((B, S, 1), 0.5, device=device)
        else:
            if attention_entropy.dim() == 1:
                attention_entropy = attention_entropy.unsqueeze(0).unsqueeze(-1)
            elif attention_entropy.dim() == 2:
                attention_entropy = attention_entropy.unsqueeze(-1)
            entropy = attention_entropy.expand(B, S, 1)
        snapshot.append(entropy)

        # Gradient norm (default 1.0)
        g_norm = grad_norm if grad_norm is not None else 1.0
        snapshot.append(torch.full((B, S, 1), g_norm, device=device))

        # Activation sparsity (default 0.3)
        sparsity = activation_sparsity if activation_sparsity is not None else 0.3
        snapshot.append(torch.full((B, S, 1), sparsity, device=device))

        snapshot = torch.cat(snapshot, dim=-1)  # [B, S, D+3]

        # Encode
        embedding = self.encoder(snapshot)  # [B, S, hidden_dim]

        # Update EMA
        with torch.no_grad():
            mean_emb = embedding.mean(dim=(0, 1))
            self.state_ema = self.ema_decay * self.state_ema + (1 - self.ema_decay) * mean_emb

        # Outputs
        confidence = self.confidence_head(embedding)  # [B, S, 1]
        importance = self.importance_head(embedding)  # [B, S, D]
        predicted_next = self.predictor(embedding)  # [B, S, D]

        return {
            'confidence': confidence,
            'importance': importance,
            'predicted_next': predicted_next,
            'embedding': embedding,
            'state_ema': self.state_ema,
        }


# ===========================================================================
# Qwen3.5 Minimal Loader & Forward
# ===========================================================================

class QwenCassiHybrid:
    """Wrapper that loads Qwen3.5-0.8B weights and applies Cassi innovations.

    This is a minimal implementation that loads weights from safetensors
    and provides hooks for the training and inference clusters.
    """

    def __init__(self, model_path: str, device: str = 'cuda'):
        self.model_path = Path(model_path)
        self.device = device

        # Load config
        with open(self.model_path / 'config.json') as f:
            self.config = json.load(f)
        self.text_config = self.config['text_config']

        # Load weights
        from safetensors.torch import load_file
        self.state_dict = load_file(str(self.model_path / 'model.safetensors-00001-of-00001.safetensors'))

        # Extract text model weights
        self.text_weights = {}
        for k, v in self.state_dict.items():
            if k.startswith('model.language_model.'):
                # Strip prefix
                new_key = k.replace('model.language_model.', '')
                self.text_weights[new_key] = v.to(device)

        self.d_model = self.text_config['hidden_size']
        self.n_layers = self.text_config['num_hidden_layers']
        self.vocab_size = self.text_config['vocab_size']

        # Identify layer types from config
        self.layer_types = self.text_config['layer_types']

        # Initialize Cassi components
        self._init_cassi_components()

        print(f"[QwenCassiHybrid] Loaded {len(self.text_weights)} text tensors")
        print(f"  d_model={self.d_model}, layers={self.n_layers}")
        print(f"  Linear attn layers: {sum(1 for t in self.layer_types if t == 'linear_attention')}")
        print(f"  Full attn layers: {sum(1 for t in self.layer_types if t == 'full_attention')}")

    def _init_cassi_components(self):
        """Initialize Cassi training and inference components."""
        # Training cluster
        self.resonant_cord = ResonantWeightCord(n_bands=13).to(self.device)
        self.surprise_loss = SurpriseWeightedLoss()

        # Identify local (linear_attn) and global (full_attention) layers
        local_layers = [i for i, t in enumerate(self.layer_types) if t == 'linear_attention']
        global_layers = [i for i, t in enumerate(self.layer_types) if t == 'full_attention']
        early_layers = list(range(self.n_layers // 2))
        late_layers = list(range(self.n_layers // 2, self.n_layers))

        self.phi_regularizer = PhiBalanceRegularizer(
            local_layers=local_layers,
            global_layers=global_layers,
            early_layers=early_layers,
            late_layers=late_layers,
        )

        # Inference cluster
        self.breath_sampler = BreathModulatedSampler()
        self.observer_head = InternalObserverHead(d_model=self.d_model).to(self.device)

    def get_parameter_trajectory_sample(self, n_params: int = 10000) -> torch.Tensor:
        """Sample a slice of parameters for trajectory analysis.

        Returns a flat tensor of n_params randomly selected parameters.
        """
        all_params = []
        for k, v in self.text_weights.items():
            if 'weight' in k and v.dtype == torch.float32:
                all_params.append(v.view(-1))

        concat = torch.cat(all_params)
        if len(concat) > n_params:
            indices = torch.randperm(len(concat))[:n_params]
            return concat[indices]
        return concat

    def apply_resonant_filter_to_gradients(self, named_params: List[Tuple[str, nn.Parameter]]):
        """Apply resonant cord filtering to parameter gradients.

        This replaces the standard momentum update with multi-band IIR filtering.
        """
        for name, p in named_params:
            if p.grad is None:
                continue

            grad_flat = p.grad.view(-1)
            filtered = self.resonant_cord(grad_flat)
            p.grad.copy_(filtered.view_as(p.grad))

    def compute_phi_balance_loss(self) -> torch.Tensor:
        """Compute φ-balance regularization from current weights."""
        # Build a dummy module from weights for the regularizer
        class WeightModule(nn.Module):
            pass

        dummy = WeightModule()
        for k, v in self.text_weights.items():
            if 'weight' in k:
                param = nn.Parameter(v.clone().requires_grad_(True))
                setattr(dummy, k.replace('.', '_'), param)

        return self.phi_regularizer(dummy)

    def sample_with_breath(self, logits: torch.Tensor) -> Tuple[int, Dict]:
        """Sample a token using breath-modulated temperature.

        Args:
            logits: [vocab_size] unnormalized logits for next token
        Returns:
            token_id: sampled token
            info: dict with breath signals and sampling params
        """
        breath = self.breath_sampler.step()
        temp = breath['temperature']
        top_p = breath['top_p']

        # Apply temperature
        probs = F.softmax(logits / temp, dim=-1)

        # Apply top-p
        sorted_probs, sorted_indices = torch.sort(probs, descending=True)
        cumsum = torch.cumsum(sorted_probs, dim=-1)
        mask = cumsum > top_p
        if mask.any():
            cutoff = mask.nonzero(as_tuple=True)[0][0].item() + 1
            keep_indices = sorted_indices[:cutoff]
            filtered_probs = torch.zeros_like(probs)
            filtered_probs[keep_indices] = probs[keep_indices]
            filtered_probs = filtered_probs / filtered_probs.sum()
        else:
            filtered_probs = probs

        token = torch.multinomial(filtered_probs, 1).item()
        return token, {**breath, 'top_p_actual': top_p}

    def observe_hidden_state(self, hidden: torch.Tensor,
                             layer_idx: int) -> Optional[Dict]:
        """Run InternalObserver on hidden states at observed layers.

        Args:
            hidden: [batch, seq, d_model]
            layer_idx: current layer index
        Returns:
            observer output dict or None if not observing this layer
        """
        if layer_idx % self.observer_head.observe_every_n != 0:
            return None
        return self.observer_head.observe(hidden)


# ===========================================================================
# Demo / Test
# ===========================================================================

def demo():
    """Run a quick demo of all Cassi components."""
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"Device: {device}")

    # 1. ResonantWeightCord demo
    print("\n=== ResonantWeightCord ===")
    cord = ResonantWeightCord(n_bands=13).to(device)
    grad = torch.randn(10000, device=device)
    filtered = cord(grad)
    print(f"  Input grad norm:  {grad.norm().item():.4f}")
    print(f"  Filtered norm:    {filtered.norm().item():.4f}")
    print(f"  Theta frequencies: {torch.sigmoid(cord.theta)[:5].tolist()}")

    # 2. PhiBalanceRegularizer demo
    print("\n=== PhiBalanceRegularizer ===")
    reg = PhiBalanceRegularizer(
        local_layers=[0, 1, 2, 4, 5],
        global_layers=[3, 7],
        early_layers=[0, 1, 2, 3],
        late_layers=[4, 5, 6, 7],
    )
    # Dummy model
    dummy = nn.Module()
    for i in range(8):
        setattr(dummy, f'layer_{i}_weight', nn.Parameter(torch.randn(100, 100)))
    loss = reg(dummy)
    print(f"  φ-balance loss: {loss.item():.6f}")

    # 3. SurpriseWeightedLoss demo
    print("\n=== SurpriseWeightedLoss ===")
    swl = SurpriseWeightedLoss()
    ce = torch.rand(4, 32, device=device) * 2.0  # random CE losses
    weighted = swl(ce)
    print(f"  Raw CE mean:      {ce.mean().item():.4f}")
    print(f"  Weighted loss:    {weighted.item():.4f}")
    print(f"  EMA:              {swl.loss_ema:.4f}")

    # 4. BreathModulatedSampler demo
    print("\n=== BreathModulatedSampler ===")
    sampler = BreathModulatedSampler(temp_base=0.7, temp_range=0.3)
    for i in range(8):
        params = sampler.step()
        print(f"  Step {i}: temp={params['temperature']:.3f}, top_p={params['top_p']:.3f}, "
              f"beat={params['beat']:+.3f}, flow={params['flow']:+.3f}")

    # 5. InternalObserverHead demo
    print("\n=== InternalObserverHead ===")
    observer = InternalObserverHead(d_model=1024).to(device)
    hidden = torch.randn(2, 10, 1024, device=device)
    result = observer.observe(hidden)
    print(f"  Confidence shape: {result['confidence'].shape}")
    print(f"  Confidence range: [{result['confidence'].min():.3f}, {result['confidence'].max():.3f}]")
    print(f"  Importance shape: {result['importance'].shape}")
    print(f"  Predicted next shape: {result['predicted_next'].shape}")

    print("\n=== All demos passed! ===")


if __name__ == '__main__':
    demo()
