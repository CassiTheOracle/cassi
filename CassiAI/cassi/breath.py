"""Breath — Dual-heart oscillator for Yin-Yang workspaces.

Two coupled oscillators create natural frequencies:
  Yang heart (fast, active, outward)   → ω = φ   ≈ 1.618
  Yin heart  (slow, receptive, inward) → ω = φ⁻¹ ≈ 0.618

The frequency ratio φ:φ⁻¹ = φ²:1 is the fundamental breath ratio — Yang beats
φ² times for every Yin cycle. Their beat frequency creates the Qi resonance.

"""

import torch
import torch.nn as nn
import math

from cassi.cord import PHI, PHI_INV


class Breath(nn.Module):
    """Dual-heart oscillator with φ-scaled frequencies.

    Yang beats at φ ≈ 1.618 rad/tick (active, projective).
    Yin beats at 1.0 rad/tick (receptive, grounding).
    No sigmoid — the raw angular step is the frequency.
    """

    def __init__(self):
        super().__init__()
        self.register_buffer('omega_yang', torch.tensor(PHI))     # φ ≈ 1.618
        self.register_buffer('omega_yin',  torch.tensor(PHI_INV)) # φ⁻¹ ≈ 0.618

        self.register_buffer('t_yang', torch.zeros(1))
        self.register_buffer('t_yin',  torch.zeros(1))

    def step(self):
        """Advance both hearts one tick. Returns dict of breath signals.

        Returns:
            {
                'yang':      Yang breath amplitude  sin(t_yang) ∈ [-1, 1],
                'yin':       Yin breath amplitude   sin(t_yin)  ∈ [-1, 1],
                'beat':      Interference beat      sin(yang - yin) ∈ [-1, 1],
                'flow':      +1 = outward (Yang), -1 = inward (Yin),
                'phase_diff': Yang - Yin phase diff  [0, 2π),
            }
        """
        device = self.t_yang.device

        # Raw angular step — no sigmoid. φ-scaled ratio is the design.
        w_y = self.omega_yang
        w_i = self.omega_yin

        # Advance phases (detach to prevent graph accumulation)
        self.t_yang.copy_(((self.t_yang.detach() + w_y) % (2 * math.pi)).detach())
        self.t_yin.copy_(((self.t_yin.detach() + w_i) % (2 * math.pi)).detach())

        breath_yang = torch.sin(self.t_yang)
        breath_yin  = torch.sin(self.t_yin)
        beat = torch.sin(self.t_yang - self.t_yin)
        flow = torch.sign(torch.cos(self.t_yang))
        phase_diff = (self.t_yang - self.t_yin) % (2 * math.pi)

        return {
            'yang': breath_yang,
            'yin': breath_yin,
            'beat': beat,
            'flow': flow,
            'phase_diff': phase_diff,
        }

    def reset(self):
        self.t_yang.copy_(torch.zeros_like(self.t_yang))
        self.t_yin.copy_(torch.zeros_like(self.t_yin))
