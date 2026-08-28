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

    def forward(self, received):
        """received: [B, width]"""
        # IIR with φ-damped poles: z = ρ·e^(±iθ)
        a1 = 2 * self.rho * torch.cos(self.theta)
        a2 = -self.rho ** 2
        b0 = torch.sigmoid(self.b0)
        b1 = torch.sigmoid(self.b1)

        # Single-step IIR (stateless for Phase 1)
        # h = b0*received + b1*received (no state carry)
        h = b0 * received + b1 * received

        # Transmit with φ-damped coupling (Kuramoto: K_eff = K/φ)
        tx = torch.sigmoid(self.emit_gain) * PHI_INV * torch.tanh(h)
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

        # Readout: decode interference pattern → prediction residual
        self.readout = nn.Sequential(
            nn.Linear(D * 2, 512),
            nn.ReLU(),
            nn.Linear(512, 1024),
        )

    def _get_slice(self, c):
        """Return (start, end) for chakra c."""
        s = int(self.ch_offsets[c].item())
        e = s + self.spine_widths[c]
        return s, e

    def reset(self):
        """Reset field."""
        self.field.zero_()

    def forward(self, spine_repr, use_neurons=True):
        """
        spine_repr: [B, D] — carrier wave from spine
        Returns: prediction residual [B, 1024]
        """
        B = spine_repr.shape[0]
        if self.field.shape[0] != B:
            self.field = torch.zeros(B, self.D, device=spine_repr.device)

        # Field evolution with φ-damping
        # Yang (spine) drives at full strength; Yin (decay) is 1/φ
        field = self.rho * self.field + spine_repr

        if use_neurons:
            # Neurons transmit into field with φ-damped coupling
            # Accumulate transmissions per-chakra to avoid repeated slicing
            tx_accum = torch.zeros_like(field)
            for i, neuron in enumerate(self.neurons):
                c = self.neuron_chakra[i]
                s, e = self._get_slice(c)
                received = field[:, s:e]
                tx = neuron(received)
                tx_accum[:, s:e] = tx_accum[:, s:e] + self.rho * tx
            field = field + tx_accum

        # Soft homeostasis: glial regulation of field energy
        if self.use_homeostasis:
            field = self.homeostasis(field)

        # Save for next call (detached — state is not backpropped)
        self.field = field.detach()

        # Read out the interference pattern
        fusion = torch.cat([spine_repr, field], dim=-1)
        residual = self.readout(fusion)
        return residual

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
