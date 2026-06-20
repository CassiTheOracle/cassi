"""
Transceiver Brain — φ-damped coupled oscillator network.

Spine generates carrier wave. Brain neurons receive, filter (φ-damped IIR),
and transmit back into shared field. No weight matrices between neurons.
Communication is wave-mediated interference.

Three φ-mechanisms:
  1. Pole magnitude fixed at ρ = 1/φ (prevents seizure)
  2. Field decay + coupling at 1/φ (creates φ² equilibrium)
  3. Frequencies φ-spaced (prevents mode-locking)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
PHI = (1 + 5**0.5) / 2
PHI_INV = 1.0 / PHI


class TransceiverNeuron(nn.Module):
    """Single neuron: receives from field, φ-damped IIR, transmits back.

    Pole magnitude is FIXED at ρ = 1/φ ≈ 0.618.
    Only the frequency (pole angle θ) is learned.

    Phase 1: Stateless (single-step). For sequence mode, state can be added.
    """

    def __init__(self, width, theta_init=0.5):
        super().__init__()
        self.width = width
        self.rho = PHI_INV

        # Learned frequency (pole angle)
        self.theta = nn.Parameter(torch.tensor([float(theta_init)]))

        # Feedforward coefficients
        self.b0 = nn.Parameter(torch.randn(1) * 0.1)
        self.b1 = nn.Parameter(torch.randn(1) * 0.1)

        # Transmission gain
        self.emit_gain = nn.Parameter(torch.zeros(1))

        # Persistent IIR state [B, width]
        self.register_buffer('h', torch.zeros(1, width))
        self.register_buffer('h_prev', torch.zeros(1, width))

    def reset_state(self, batch_size, device=None):
        """Reset persistent state for a new batch/sequence."""
        if device is None:
            device = self.h.device
        self.h = torch.zeros(batch_size, self.width, device=device)
        self.h_prev = torch.zeros(batch_size, self.width, device=device)

    def forward(self, received):
        """received: [B, width]"""
        B = received.shape[0]
        if self.h.shape[0] != B:
            self.reset_state(B, received.device)

        # IIR with φ-damped poles: z = ρ·e^(±iθ)
        a1 = 2 * self.rho * torch.cos(self.theta)
        a2 = -self.rho ** 2
        b0 = torch.sigmoid(self.b0)
        b1 = torch.sigmoid(self.b1)

        h_new = a1 * self.h + a2 * self.h_prev + b0 * received + b1 * received

        # Persistent inference state, not backpropped through time.
        self.h_prev = self.h.detach()
        self.h = h_new.detach()


        # Transmit with φ-damped coupling (Kuramoto: K_eff = K/φ)
        tx = torch.sigmoid(self.emit_gain) * PHI_INV * torch.tanh(h_new)
        return tx




class GlialHomeostasis(nn.Module):
    """Soft homeostatic regulator — senses global field energy and injects
    compensating inhibition to prevent slow creep toward blowup.

    Target energy: E_target = φ² (the natural Yang-dominant equilibrium)
    Regulation: field ← field - gain · (E - E_target) · field
    """

    def __init__(self, target_energy=None, gain=0.05):
        super().__init__()
        if target_energy is None:
            target_energy = PHI ** 2
        self.target = target_energy
        self.gain = gain

    def forward(self, field):
        """field: [B, D]"""
        # Per-sample energy (mean squared amplitude)
        energy = field.pow(2).mean(dim=-1, keepdim=True)  # [B, 1]
        excess = energy - self.target
        # Soft negative feedback: push field toward target energy
        # Only acts when excess > 0 (energy above target)
        inhibition = self.gain * torch.relu(excess) * field
        return field - inhibition



class MetaPlasticityNeuron(nn.Module):
    """IIR-filtered LR modulation from Qi (field-space prediction error).

    Reads qi_energy, qi_bias, qi_trend, field_energy, freq_spread and outputs
    lr_modulation \u2208 [0.5, 2.0] via sigmoid-scaled IIR transmission.

    Parameters are initialized randomly; the IIR dynamics provide temporal
    smoothing. Gradient-based learning requires a meta-learning phase (not
    integrated in the current single-step training loop).
    """
    def __init__(self, input_width=6):
        super().__init__()
        self.rho = PHI_INV
        self.theta = nn.Parameter(torch.tensor([0.5]))
        self.b0 = nn.Parameter(torch.randn(1) * 0.1)
        self.b1 = nn.Parameter(torch.randn(1) * 0.1)
        self.emit_gain = nn.Parameter(torch.zeros(1))
        self.in_proj = nn.Linear(5, input_width)
        self.register_buffer('h', torch.zeros(1, input_width))
        self.register_buffer('h_prev', torch.zeros(1, input_width))

    def reset_state(self, batch_size, device=None):
        if device is None:
            device = self.h.device
        w = self.in_proj.out_features
        self.h = torch.zeros(batch_size, w, device=device)
        self.h_prev = torch.zeros(batch_size, w, device=device)

    def forward(self, qi_energy, qi_bias, qi_trend, field_energy, freq_spread):
        """All inputs: float scalars. Returns [B] lr_modulation."""
        def _t(v):
            return torch.tensor([float(v)], device=self.h.device)
        x = torch.cat([
            _t(qi_energy), _t(qi_bias), _t(qi_trend),
            _t(field_energy), _t(freq_spread)
        ]).unsqueeze(0)  # [1, 5]
        if self.h.shape[0] > 1:
            x = x.expand(self.h.shape[0], -1)
        x = self.in_proj(x)

        a1 = 2 * self.rho * torch.cos(self.theta)
        a2 = -self.rho ** 2
        b0 = torch.sigmoid(self.b0)
        b1 = torch.sigmoid(self.b1)

        h_new = a1 * self.h + a2 * self.h_prev + b0 * x + b1 * x
        self.h_prev = self.h.detach()
        self.h = h_new.detach()

        tx = torch.sigmoid(self.emit_gain) * PHI_INV * torch.tanh(h_new)
        lr_mod = torch.sigmoid(tx.mean(dim=-1)) * 1.5 + 0.5  # [B] in [0.5, 2.0]
        return lr_mod


class TransceiverBrain(nn.Module):
    """Collection of φ-damped transceiver neurons sharing a wave field.

    Field self-organizes to φ² equilibrium:
        field(t+1) = (1/φ)·field(t) + spine(t) + (1/φ)·Σ transmissions(t)
    At steady state: field = spine · φ²

    Phase 2: + soft homeostasis (glial regulator)
    """

    def __init__(self, D=1040, n_neurons=128, spine_widths=None,
                 use_homeostasis=True, homeo_gain=0.05):
        super().__init__()
        self.D = D
        self.n_neurons = n_neurons
        self.rho = PHI_INV
        self.use_homeostasis = use_homeostasis

        if spine_widths is None:
            spine_widths = [1, 2, 3, 5, 8, 14, 22, 36, 58, 94, 152, 246, 399]
        self.spine_widths = spine_widths
        self.n_chakras = len(spine_widths)

        # Build cumulative offsets for fast slicing
        offsets = [0]
        for w in spine_widths[:-1]:
            offsets.append(offsets[-1] + w)
        self.register_buffer('ch_offsets', torch.tensor(offsets, dtype=torch.long))

        # Assign neurons to chakras with φ-spaced frequencies
        self.neuron_chakra = []
        self.neurons = nn.ModuleList()
        for i in range(n_neurons):
            c = i % self.n_chakras
            w = spine_widths[c]
            # φ-spaced frequencies, wrapped to keep angles reasonable
            theta_init = 0.1 * (PHI ** (i % 8))
            self.neuron_chakra.append(c)
            self.neurons.append(TransceiverNeuron(width=w, theta_init=theta_init))

        # Glial homeostasis
        if use_homeostasis:
            self.homeostasis = GlialHomeostasis(target_energy=PHI**2, gain=homeo_gain)

        # Persistent field state [B, D]
        self.register_buffer('field', torch.zeros(1, D))
        self.field_clamp = 50.0

        # Readout: decode field → prediction residual.
        # Single linear layer + tanh — no hidden layers, no ReLU.
        self.readout = nn.Sequential(
            nn.Linear(D, 1024),
        )

        # ── Qi infrastructure ──
        # Yang/Yin chakra partition for qi bias computation.
        # Yang = chakras 0–6 (narrow/fast bands), Yin = chakras 7–12 (wide/slow bands).
        yang_start = int(self.ch_offsets[0].item())
        yang_end   = int(self.ch_offsets[6].item()) + spine_widths[6]
        yin_start  = int(self.ch_offsets[7].item())
        yin_end    = int(self.ch_offsets[12].item()) + spine_widths[12]
        self.register_buffer('qi_yang_slice', torch.tensor([yang_start, yang_end], dtype=torch.long))
        self.register_buffer('qi_yin_slice',  torch.tensor([yin_start,  yin_end],  dtype=torch.long))

        # Meta-plasticity: learns LR modulation from Qi (field-space prediction error)
        self.meta_plasticity = MetaPlasticityNeuron(input_width=6)

        # Qi energy tracking (persistent across steps, reset per epoch)
        self.register_buffer('_qi_energy', torch.zeros(1))
        self.register_buffer('_qi_bias', torch.zeros(1))
        self.register_buffer('_qi_energy_ema', torch.zeros(1))
        self.register_buffer('_prev_qi_energy_ema', torch.zeros(1))

    def _get_slice(self, c):
        """Return (start, end) for chakra c."""
        s = int(self.ch_offsets[c].item())
        e = s + self.spine_widths[c]
        return s, e

    def reset_state(self, batch_size=None):
        """Reset field and all neuron states for a new batch/sequence."""
        if batch_size is None:
            batch_size = 1
        device = self.field.device
        self.field = torch.zeros(batch_size, self.D, device=device)
        for n in self.neurons:
            n.reset_state(batch_size, device)
        self.meta_plasticity.reset_state(batch_size, device)

    def reset(self):
        """Backward-compatible alias."""
        self.reset_state(1)

    def forward(self, spine_repr, use_neurons=True, target=None):
        """
        spine_repr: [B, D] or [B, T, D] — carrier wave from spine
        target: [B, 1024] or [B, T, 1024] (optional) — ground truth for Qi computation
        Returns: prediction residual [B, 1024] or [B, T, 1024]
        """
        if spine_repr.dim() == 2:
            return self._step(spine_repr, use_neurons=use_neurons, target=target)
        if spine_repr.dim() == 3:
            outs = []
            for t in range(spine_repr.shape[1]):
                tgt = target[:, t] if target is not None else None
                outs.append(self._step(spine_repr[:, t], use_neurons=use_neurons, target=tgt))
            return torch.stack(outs, dim=1)
        raise ValueError(f"Expected [B,D] or [B,T,D], got {spine_repr.shape}")

    def _compute_qi_bias(self, qi):
        """Ratio of qi energy in yang (high-freq, chakras 0–6) vs total.

        qi: [B, D] — field-space prediction error
        Returns: scalar tensor — 0 = all yin, 1 = all yang
        """
        ys, ye = self.qi_yang_slice[0].item(), self.qi_yang_slice[1].item()
        ys2, ye2 = self.qi_yin_slice[0].item(), self.qi_yin_slice[1].item()
        yang_energy = qi[:, ys:ye].pow(2).mean()
        yin_energy  = qi[:, ys2:ye2].pow(2).mean()
        return (yang_energy / (yang_energy + yin_energy + 1e-8)).detach()

    def _step(self, spine_repr, use_neurons=True, target=None):
        """Single transceiver step.

        Forward (Yang): field updates with spine+transmissions, readout predicts.
        Reverse (Yin): if target given, error backprojects into field space as Qi,
                       and Yin correction contracts field toward correct state.
        """
        B = spine_repr.shape[0]
        if self.field.shape[0] != B:
            self.reset_state(B)

        field = self.rho * self.field + spine_repr

        if use_neurons:
            tx_accum = torch.zeros_like(field)
            for i, neuron in enumerate(self.neurons):
                c = self.neuron_chakra[i]
                s, e = self._get_slice(c)
                tx = neuron(field[:, s:e])
                tx_accum[:, s:e] = tx_accum[:, s:e] + self.rho * tx
            field = field + tx_accum

        if self.use_homeostasis:
            field = self.homeostasis(field)

        field = field.clamp(-self.field_clamp, self.field_clamp)

        # Persistent inference state — stored detached (no BPTT).
        self.field = field.detach()

        # ── Forward readout (Yang) ──
        residual = self.readout(self.field)
        prediction = torch.tanh(residual)

        # ── Reverse pathway (Yin): Qi from field-space prediction error ──
        if target is not None:
            with torch.no_grad():
                error = prediction - target                     # [B, 1024]
                # Backproject error into field space: [B,1024] @ [1024,D] = [B,D]

                qi = torch.matmul(error, self.readout[0].weight)  # [B, D]

                # Yin correction: φ⁻² gain so Yang leads by φ²
                qi_gain = PHI_INV ** 2
                self.field = self.field - qi_gain * qi
                self._qi_energy = qi.pow(2).mean()
                self._qi_bias = self._compute_qi_bias(qi)

            # Qi energy EMA (trend tracking)
            self._prev_qi_energy_ema.copy_(self._qi_energy_ema)
            self._qi_energy_ema.mul_(0.9).add_(0.1 * self._qi_energy)
        return prediction


    def get_field_stats(self):
        """Return energy statistics of the field."""
        if self.field.numel() == 0:
            return {'mean': 0.0, 'std': 0.0, 'max': 0.0, 'energy': 0.0}
        return {
            'mean': self.field.mean().item(),
            'std': self.field.std().item(),
            'max': self.field.abs().max().item(),
            'energy': self.field.pow(2).mean().item(),
        }

    def get_neuron_freqs(self):
        """Return current neuron frequencies in Hz (arbitrary units)."""
        return [float(n.theta.item()) for n in self.neurons]

    @property
    def lr_modulation(self):
        """Current LR modulation from meta-plasticity neuron.

        Reads qi energy, bias, trend + field energy + frequency spread,
        passes through the meta-plasticity IIR neuron.
        Returns: float in [0.5, 2.0]

        NOTE: advances the meta-plasticity IIR state on every access.
        Call once per optimizer step.
        """
        qi_trend = (self._qi_energy_ema - self._prev_qi_energy_ema).item()
        qi_energy_val = self._qi_energy.item()
        qi_bias_val = self._qi_bias.item()
        field_energy = self.field.pow(2).mean().item()
        if len(self.neurons) > 1:
            thetas = torch.stack([n.theta for n in self.neurons])
            freq_spread = thetas.std().item()
        else:
            freq_spread = 0.0
        return self.meta_plasticity(
            qi_energy_val, qi_bias_val, qi_trend, field_energy, freq_spread
        ).mean().item()

    @property
    def qi_state(self):
        """Derived Qi state label (for logging).

        State transitions from qi_energy and qi_trend:
          fire  — high error, rising   (peak learning)
          wood  — high error, falling  (exploration)
          metal — low error, rising    (purification)
          water — low error, falling   (consolidation)
          earth — otherwise            (harmony)
        """
        e = self._qi_energy.item()
        trend = (self._qi_energy_ema - self._prev_qi_energy_ema).item()
        if e > 0.1 and trend > 0.01:  return 'fire'
        if e > 0.1 and trend < -0.01: return 'wood'
        if e < 0.02 and trend > 0.01: return 'metal'
        if e < 0.02 and trend < -0.01: return 'water'
        return 'earth'
