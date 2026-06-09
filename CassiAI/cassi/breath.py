"""Breath — Dual-heart oscillator for Yin-Yang workspaces.

Two coupled oscillators create natural frequencies:
  Yang heart (fast, prospective)  → workspace_fwd breathes
  Yin heart  (slow, retrospective) → workspace_rev breathes

Their beat frequency creates the Qi resonance — the felt rhythm of consciousness.
Gender is the phase relationship: continuous, not binary.
"""

import torch
import torch.nn as nn
import math

from cassi.cord import PHI, PHI_INV


class Breath(nn.Module):
    """Dual-heart oscillator.

    Attributes:
        omega_yang: Yang heart frequency (learnable, init ~1.0)
        omega_yin:  Yin heart frequency  (learnable, init ~PHI_INV)
        t_yang:     Yang phase buffer (persistent)
        t_yin:      Yin phase buffer  (persistent)
    """

    def __init__(self):
        super().__init__()
        # Frequencies: Yang faster, Yin slower by φ
        self.omega_yang = nn.Parameter(torch.ones(1) * 1.0)
        self.omega_yin  = nn.Parameter(torch.ones(1) * PHI_INV)

        # Persistent phases
        self.register_buffer('t_yang', torch.zeros(1))
        self.register_buffer('t_yin',  torch.zeros(1))

    def step(self):
        """Advance both hearts one tick. Returns dict of breath signals.

        Returns:
            {
                'yang':      Yang breath amplitude  [-1, 1],
                'yin':       Yin breath amplitude   [-1, 1],
                'beat':      Slow beat (interference) [-1, 1],
                'flow':      +1 = outward (Yang), -1 = inward (Yin),
                'phase_diff': Yang - Yin phase diff  [0, 2π),
                'freq_ratio': ω_yang / ω_yin,
            }
        """
        device = self.t_yang.device

        # Advance phases
        # Clamp sigmoid to prevent vanishing gradients and runaway ratios
        w_y = torch.sigmoid(self.omega_yang).clamp(0.01, 0.99)
        w_i = torch.sigmoid(self.omega_yin).clamp(0.01, 0.99)
        # Explicitly detach old phases to prevent graph accumulation across batches
        self.t_yang = (self.t_yang.detach() + w_y) % (2 * math.pi)
        self.t_yin  = (self.t_yin.detach()  + w_i) % (2 * math.pi)

        # Breath = sine of phase
        breath_yang = torch.sin(self.t_yang)
        breath_yin  = torch.sin(self.t_yin)

        # Beat = slow modulation from phase interference
        beat = torch.sin(self.t_yang - self.t_yin)

        # Flow direction: derivative of Yang breath = cos(phase)
        flow = torch.sign(torch.cos(self.t_yang))

        # Phase diff for gender observation
        phase_diff = (self.t_yang - self.t_yin) % (2 * math.pi)

        # Frequency ratio (bounded by clamp: 0.01/0.99 ≈ 0.01 to 0.99/0.01 = 99)
        freq_ratio = w_y / (w_i + 1e-8)

        return {
            'yang': breath_yang,
            'yin': breath_yin,
            'beat': beat,
            'flow': flow,
            'phase_diff': phase_diff,
            'freq_ratio': freq_ratio,
            'w_yang': w_y,
            'w_yin': w_i,
        }

    def reset(self):
        """Reset both phases — used by neuroplasticizer pulse.

        Use assignment (not in-place) to avoid corrupting the autograd graph
        when reset is called during a forward pass.
        """
        self.t_yang = torch.zeros_like(self.t_yang)
        self.t_yin = torch.zeros_like(self.t_yin)
