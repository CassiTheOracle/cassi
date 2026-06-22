#!/usr/bin/env python3
"""
QiFlow — diffusive Qi pressure that drives the field.

Qi is computed pointwise as |ψ|²·|ψ − P[ψ]|², but it does not stay still.
It diffuses (spreads from high-Q to low-Q regions via the heat equation) and
the resulting pressure gradient pushes the field:

    Q_flow = Q + η · ∇²Q
    F_qi[i] = −(Q_flow[i+1] − Q_flow[i−1]) / 2
    ψ ← ψ + β · F_qi · P

High-surprise (high-Q) regions radiate pressure that pushes nearby field
elements to explore.  Low-Q regions are pulled toward the mean.
"""

from typing import Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F


class QiFlow(nn.Module):
    """Qi diffusion and pressure forces.

    Two learnable scalars:
        η (diffusion rate): how fast Qi spreads (softplus-activated).
        β (force coupling): how strongly pressure pushes the field.
    """

    def __init__(self):
        super().__init__()
        self.eta_logit = nn.Parameter(torch.tensor(0.1))
        self.beta_logit = nn.Parameter(torch.tensor(-4.0))

    def forward(self, Q: torch.Tensor,
                psi_real: torch.Tensor, psi_imag: torch.Tensor,
                P_re: torch.Tensor, P_im: torch.Tensor
                ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Apply Qi pressure forces to the field.

        Args:
            Q: [B, N, d] pointwise Qi.
            psi_real: [B, N, d] field real.
            psi_imag: [B, N, d] field imag.
            P_re: [B, N, d] prediction real.
            P_im: [B, N, d] prediction imag.

        Returns:
            psi_real_out, psi_imag_out: [B, N, d] field after Qi force.
        """
        eta = F.softplus(self.eta_logit)
        beta = F.softplus(self.beta_logit)

        # Mean over d for spatial diffusion (Qi is a scalar field per position)
        Q_pos = Q.mean(dim=-1)  # [B, N]

        # Discrete Laplacian over N: ∇²Q[i] = Q[i+1] + Q[i-1] - 2·Q[i]
        # Natural boundary conditions (zero gradient at edges)
        Q_laplacian = torch.zeros_like(Q_pos)
        Q_laplacian[:, 1:-1] = (Q_pos[:, 2:] + Q_pos[:, :-2]
                                - 2.0 * Q_pos[:, 1:-1])
        # Boundary: first and last positions have only one neighbor
        Q_laplacian[:, 0] = Q_pos[:, 1] - Q_pos[:, 0]
        Q_laplacian[:, -1] = Q_pos[:, -2] - Q_pos[:, -1]

        # Diffusion: Q_flow = Q + η · ∇²Q
        Q_flow = Q_pos + eta * Q_laplacian  # [B, N]

        # Pressure gradient: F[i] = −(Q_flow[i+1] − Q_flow[i-1]) / 2
        F_qi = torch.zeros_like(Q_flow)
        F_qi[:, 1:-1] = -(Q_flow[:, 2:] - Q_flow[:, :-2]) / 2.0
        # Zero gradient at boundaries (no pressure at edges)
        # F_qi[:, 0] = 0  (implicitly zero)

        # Broadcast back to d: F[i,d] = F[i]
        F_qi = F_qi.unsqueeze(-1)  # [B, N, 1]

        # Apply: ψ ← ψ + β · F · P
        # Pressure pushes IN THE DIRECTION of P (modulated prediction feedback)
        psi_real = psi_real + beta * F_qi * P_re
        psi_imag = psi_imag + beta * F_qi * P_im

        return psi_real, psi_imag
