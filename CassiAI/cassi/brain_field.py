"""BrainField — Expanded resonant field for cognitive processing.

A slower, larger CordPhysics-like module that operates on the brainstem's
compressed bottleneck representation. It maintains its own persistent IIR state
and updates every K spine steps.

Dimension: D_brain = D × φ (expanded from spine)
Timescale: every K spine steps (K = 2 or 3)
Dynamics: slower theta frequencies than spine
"""

import math
import torch
import torch.nn as nn

from cassi.cord import PHI, PHI_INV


class BrainField(nn.Module):
    """Slower resonant field for cognitive processing.

    Args:
        D_stem: brainstem bottleneck dimension
        D_brain: brain dimension (default int(D_stem * PHI))
        K: update every K spine steps (default 2)
    """

    def __init__(self, D_stem, D_brain=None, K=2):
        super().__init__()
        self.D_stem = D_stem
        self.D_brain = D_brain if D_brain is not None else int(D_stem * PHI)
        self.K = K
        self._step_counter = 0

        # Project from bottleneck to brain dimension
        self.in_proj = nn.Sequential(
            nn.Linear(D_stem, self.D_brain),
            nn.LayerNorm(self.D_brain),
        )
        # Small init so brain field starts near zero
        for m in self.in_proj.modules():
            if isinstance(m, nn.Linear):
                nn.init.uniform_(m.weight, -0.01, 0.01)
                nn.init.zeros_(m.bias)

        # Brain has fewer but wider chakras than spine
        # Same 13 chakras, φ-scaled, sum to D_brain
        raw = [PHI ** c for c in range(13)]
        total_raw = sum(raw)
        self.widths = [max(1, round(self.D_brain * r / total_raw)) for r in raw]
        self.widths[-1] += self.D_brain - sum(self.widths)
        self.C = len(self.widths)

        # Precompute offsets
        self._offsets = []
        offset = 0
        for w in self.widths:
            self._offsets.append((offset, offset + w))
            offset += w

        # Per-chakra IIR frequencies — initialized slower than spine
        self.fwd_theta = nn.Parameter(torch.randn(self.C))
        self.rev_theta = nn.Parameter(torch.randn(self.C))

        # Per-chakra gains
        self.fwd_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.fwd_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))
        self.rev_b0 = nn.Parameter(0.1 * torch.randn(self.C))
        self.rev_b1 = nn.Parameter(-0.5 + 0.1 * torch.randn(self.C))

        # Fusion + output
        self.fusion = nn.Linear(self.D_brain * 2, self.D_brain, bias=False)
        self._init_theta()

        # Persistent IIR state
        self.register_buffer('h1', torch.zeros(1, self.D_brain))
        self.register_buffer('h2', torch.zeros(1, self.D_brain))
        self.register_buffer('x1', torch.zeros(1, self.D_brain))
        self.register_buffer('field_state', torch.zeros(1, self.D_brain))

    def _init_theta(self):
        """Initialize theta with slower frequencies than spine."""
        theta_max = 1.5  # slower than spine's 2.5
        for c in range(self.C):
            theta_c = theta_max * (PHI ** (-c))
            y = theta_c / math.pi
            y = max(0.001, min(0.999, y))
            param = math.log(y / (1.0 - y))
            self.fwd_theta.data[c] = param
            self.rev_theta.data[c] = param

    def reset_state(self, batch_size):
        """Reset all persistent brain field buffers."""
        device = self.h1.device
        self.h1 = torch.zeros(batch_size, self.D_brain, device=device)
        self.h2 = torch.zeros(batch_size, self.D_brain, device=device)
        self.x1 = torch.zeros(batch_size, self.D_brain, device=device)
        self.field_state = torch.zeros(batch_size, self.D_brain, device=device)
        self._step_counter = 0

    def step(self, compressed):
        """One IIR step on brain field.

        Args:
            compressed: [B, D_stem] from brainstem
        Returns:
            field_state: [B, D_brain]
        """
        B = compressed.shape[0]
        x_new = self.in_proj(compressed)  # [B, D_brain]

        # Per-chakra forward IIR
        h_new_parts = []
        for c in range(self.C):
            start, end = self._offsets[c]
            x_c = x_new[:, start:end]

            theta = torch.sigmoid(self.fwd_theta[c]) * math.pi
            a1 = 2.0 * PHI_INV * torch.cos(theta)
            a2 = -(PHI_INV) ** 2
            b0 = torch.sigmoid(self.fwd_b0[c])
            b1 = torch.sigmoid(self.fwd_b1[c])
            sf = b0 + b1 + 1e-8
            b0, b1 = b0 / sf, b1 / sf

            # Clone to avoid in-place modification corrupting autograd graph
            h1_c = self.h1[:, start:end].clone()
            h2_c = self.h2[:, start:end].clone()
            x1_c = self.x1[:, start:end].clone()

            h_new_c = b0 * x_c + b1 * x1_c + a1 * h1_c + a2 * h2_c

            # Update IIR state (reconstruct full tensor to avoid in-place)
            new_h1 = self.h1.clone()
            new_h2 = self.h2.clone()
            new_x1 = self.x1.clone()
            new_h2[:, start:end] = h1_c
            new_h1[:, start:end] = h_new_c
            new_x1[:, start:end] = x_c
            self.h2 = new_h2
            self.h1 = new_h1
            self.x1 = new_x1

            h_new_parts.append(h_new_c)

        h_new = torch.cat(h_new_parts, dim=-1)
        self.field_state = self.fusion(torch.cat([x_new, h_new * 0.5], dim=-1)) + x_new

        return self.field_state

    def maybe_step(self, compressed):
        """Step only every K calls. Between steps, field decays naturally.

        Args:
            compressed: [B, D_stem] from brainstem
        Returns:
            field_state: [B, D_brain] (updated or decayed)
        """
        self._step_counter += 1
        if self._step_counter % self.K == 0:
            return self.step(compressed)
        else:
            # Natural decay between updates
            self.field_state = self.field_state * PHI_INV
            return self.field_state
