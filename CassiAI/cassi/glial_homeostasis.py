"""Glial homeostasis: a simple energy-contraction operator.

Glial cells maintain the field's total energy close to a target by softly
contracting regions whose local energy exceeds the target. This is purely a
homeostatic pressure — it does not amplify low-energy regions.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple

from cassi.cord import PHI


class GlialHomeostasis(nn.Module):
    """Soft energy clamp that pulls field energy toward a target.

    Args:
        target_energy: target mean squared magnitude (defaults to PHI**2).
        gain: contraction strength applied to excess energy (default 0.05).
    """

    def __init__(self, target_energy: float = None, gain: float = 0.05):
        super().__init__()
        if target_energy is None:
            target_energy = PHI ** 2
        self.target_energy = target_energy
        self.gain = gain

    def forward(self, field_real: torch.Tensor,
                field_imag: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply glial contraction.

        Args:
            field_real/field_imag: [..., width] real/imag field components.

        Returns:
            contracted real/imag tensors of the same shape.
        """
        energy = (field_real ** 2 + field_imag ** 2).mean(dim=-1, keepdim=True)
        excess = F.relu(energy - self.target_energy)

        factor = (1.0 - self.gain * excess).clamp(0.0, 1.0)
        out_real = factor * field_real
        out_imag = factor * field_imag
        return out_real, out_imag
