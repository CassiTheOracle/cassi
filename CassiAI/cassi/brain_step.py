#!/usr/bin/env python3
"""
BrainStep — per-step damped wave processor for 3D spherical shell geometry.

Replaces Spine3D's sequence-based cumsum with a per-position first-order
damped recurrence that maintains persistent state across steps.

Seven concentric shells at golden-section radii each carry a damped wave
accumulator that updates one step at a time:

    brain_h_next_c = damp_c * brain_h_c + (1 - damp_c) * psi_c * breath_mod

Each shell then applies Fibonacci-depth softplus processing, radial coupling,
and projects back to the field dimension d.

Architecture:
    psi (real + imag) → per-shell projection → damped recurrence →
    Fibonacci depth → radial coupling → output projection → dpsi

Signature:
    forward(psi_real, psi_imag, yang, yin, brain_h) → (dpsi_real, dpsi_imag, brain_h_next)
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Tuple

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1 / PHI


class BrainStep(nn.Module):
    """Per-step damped wave processor for spherical shell geometry.

    Operates on ONE position at a time with persistent damped-wave state,
    replacing Spine3D's cumsum over L positions.

    Args:
        d: field dimension (must match TripartiteCord's d).
        n_shells: number of concentric spherical shells (default 7).
        D: total brain dimensions across all shells (default 588).
        fib_dropout: dropout probability for Fibonacci depth layers (default 0.0).
        max_batch_size: maximum batch size for persistent buffers (default 256).
    """

    def __init__(
        self,
        d: int,
        n_shells: int = 7,
        D: int = 588,
        fib_dropout: float = 0.0,
        max_batch_size: int = 256,
    ):
        super().__init__()
        self.d = d
        self.n_shells = n_shells
        self.D_total = D
        self.fib_dropout = fib_dropout
        self.max_batch_size = max_batch_size

        # ═══ SHELL GEOMETRY ═══
        # Radii: r_c = R_0 · φ^c, c = 1..7
        R_0 = 1.0
        r_c = torch.tensor([R_0 * PHI ** c for c in range(1, n_shells + 1)])
        self.register_buffer('r_c', r_c)  # [n_shells] — shell radii

        # Wavenumbers: k_c = π / r_c (spherical standing wave condition)
        self.register_buffer('k_c', math.pi / self.r_c)

        # ═══ DIMENSION ALLOCATION ═══
        # D_c ∝ r_c (linear), same as Spine3D
        raw_dims = self.r_c / self.r_c.sum()
        dims = (raw_dims * D).long()
        dims[-1] += D - dims.sum()
        self.D_c = dims.tolist()  # per-shell dimension list
        D_max = max(self.D_c)
        self.D_max = D_max
        dim_cumsum = torch.tensor(self.D_c).cumsum(0)
        self.register_buffer('dim_splits', dim_cumsum)

        # ═══ INPUT PROJECTION ═══
        # Project psi [B, 2d] → per-shell coefficients [B, D_c[c]]
        # W_input[c]: [2d, D_c[c]]
        self.W_input = nn.ParameterList([
            nn.Parameter(torch.randn(2 * d, self.D_c[c]) * 0.02 / math.sqrt(2 * d))
            for c in range(n_shells)
        ])
        self.b_input = nn.ParameterList([
            nn.Parameter(torch.zeros(self.D_c[c])) for c in range(n_shells)
        ])

        # ═══ DAMPING ═══
        # Per-shell damping: γ_c = γ_0 · (r_0 / r_c)  → larger radius = lower damping
        # Init: γ_0 = ln(φ) ≈ 0.481 → damp_0 = 1/φ ≈ 0.618
        gamma_0 = math.log(PHI)
        gamma_scaled = gamma_0 * (R_0 / self.r_c)
        self.log_gamma_c = nn.Parameter(torch.log(gamma_scaled.clamp(min=0.01)))

        # ═══ RADIAL GEOMETRIC COUPLING ═══
        # M_geom[i,j] = spread * cos(k_i * dr)
        M_geom = torch.zeros(n_shells, n_shells)
        for i in range(n_shells):
            for j in range(n_shells):
                if i != j:
                    dr = self.r_c[i] - self.r_c[j]
                    phase = self.k_c[i] * dr
                    spread = self.r_c[j] / self.r_c[i] if j < i else self.r_c[i] / self.r_c[j]
                    M_geom[i, j] = spread * torch.cos(phase)
        self.register_buffer('M_geom', M_geom)

        # ═══ LEARNABLE RADIAL COUPLING ═══
        C_init = torch.zeros(n_shells, n_shells)
        for i in range(n_shells):
            for j in range(n_shells):
                if i == j:
                    C_init[i, j] = 1.0
                else:
                    r_min = min(self.r_c[i].item(), self.r_c[j].item())
                    r_max = max(self.r_c[i].item(), self.r_c[j].item())
                    C_init[i, j] = (r_min / r_max) ** 2
        self.C = nn.Parameter(C_init)

        # ═══ BREATH MODULATION ═══
        self.alpha_breath = nn.Parameter(torch.zeros(n_shells))
        self.beta_heart = nn.Parameter(torch.zeros(n_shells))

        # ═══ FIBONACCI DEPTH ═══
        # Each shell gets F_c internal processing layers (Fibonacci sequence).
        # Crown has 13 layers; root has 1 layer.
        fib = [1, 1]
        while len(fib) < n_shells:
            fib.append(fib[-1] + fib[-2])
        self.fib_layers = fib[:n_shells]

        # Precompute cumulative Fibonacci indices
        fib_cumsum = [0]
        for i in range(n_shells - 1):
            fib_cumsum.append(fib_cumsum[-1] + self.fib_layers[i])
        self.register_buffer('fib_idx', torch.tensor(fib_cumsum, dtype=torch.long))

        self.W_fib = nn.ParameterList()
        self.b_fib = nn.ParameterList()
        for c in range(n_shells):
            dc = self.D_c[c]
            fc = self.fib_layers[c]
            for _l in range(fc):
                self.W_fib.append(nn.Parameter(
                    torch.randn(dc, dc) * 0.02 / math.sqrt(dc)))
                self.b_fib.append(nn.Parameter(torch.zeros(dc)))

        # ═══ OUTPUT PROJECTION ═══
        # Per-shell projection from D_c[c] → 2d (concatenated real+imag)
        self.W_output = nn.ParameterList([
            nn.Parameter(torch.randn(self.D_c[c], 2 * d) * 0.02 / math.sqrt(self.D_c[c]))
            for c in range(n_shells)
        ])
        self.b_output = nn.ParameterList([
            nn.Parameter(torch.zeros(2 * d)) for c in range(n_shells)
        ])

        # ═══ PERSISTENT STATE ═══
        # Per-shell damped wave accumulators [max_batch_size, n_shells, D_max]
        self.register_buffer(
            'brain_h',
            torch.zeros(max_batch_size, n_shells, self.D_max)
        )

    # ── State Management ──

    @torch.no_grad()
    def reset_state(self) -> None:
        """Zero all persistent damped wave accumulators."""
        self.brain_h.zero_()

    def _expand_brain_h(self, B: int) -> None:
        """Resize brain_h buffer to accommodate batch size B."""
        if B > self.brain_h.shape[0]:
            dev = self.brain_h.device
            dtype = self.brain_h.dtype
            self.register_buffer(
                'brain_h',
                torch.zeros(B, self.n_shells, self.D_max, device=dev, dtype=dtype)
            )

    # ── Forward ──

    def forward(
        self,
        psi_real: torch.Tensor,
        psi_imag: torch.Tensor,
        yang: float,
        yin: float,
        brain_h: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """Process one position through the spherical brain.

        Args:
            psi_real: [B, d] real part of field input.
            psi_imag: [B, d] imaginary part of field input.
            yang: scalar breath phase (yang, ~1.0).
            yin: scalar heartbeat phase (yin, ~φ⁻¹).
            brain_h: [B, n_shells, D_max] current damped wave state.

        Returns:
            dpsi_real: [B, d] real part of field update.
            dpsi_imag: [B, d] imaginary part of field update.
            brain_h_next: [B, n_shells, D_max] updated damped wave state.
        """
        B = psi_real.shape[0]
        dev = psi_real.device
        n_s = self.n_shells

        # ═══ 1. Concatenate real + imag ═══
        psi = torch.cat([psi_real, psi_imag], dim=-1)  # [B, 2d]

        # ═══ 2. Per-shell projection ═══
        # psi_c = psi @ W_input[c] + b_input[c] → [B, D_c[c]], pad to D_max
        psi_padded = torch.zeros(B, n_s, self.D_max, device=dev, dtype=psi.dtype)
        for c in range(n_s):
            dc = self.D_c[c]
            psi_c = psi @ self.W_input[c] + self.b_input[c]  # [B, dc]
            psi_padded[:, c, :dc] = psi_c

        # ═══ 3. Breath modulation per shell ═══
        # mod_c = (1 + tanh(alpha_c) * yang) * (1 + tanh(beta_c) * yin)
        alpha = torch.tanh(self.alpha_breath)   # [n_s]
        beta = torch.tanh(self.beta_heart)      # [n_s]
        mod_c = (1.0 + alpha * yang) * (1.0 + beta * yin)  # [n_s]

        # ═══ 4. Damped recurrence per shell ═══
        gamma_c = torch.exp(self.log_gamma_c).clamp(min=0.05)  # [n_s]
        damp_c = torch.exp(-gamma_c)                           # [n_s]

        brain_h_next = torch.zeros_like(brain_h)
        h_deep_list = []
        for c in range(n_s):
            dc = self.D_c[c]
            damp = damp_c[c]
            mod = mod_c[c]

            # State slice from brain_h [B, n_s, D_max]
            h_prev = brain_h[:, c, :dc]          # [B, dc]
            psi_c = psi_padded[:, c, :dc]        # [B, dc]

            # Damped update: replace cumsum with per-step recurrence
            h_new = damp * h_prev + (1.0 - damp) * psi_c * mod  # [B, dc]

            # Store next state
            brain_h_next[:, c, :dc] = h_new

            # ═══ 5. Fibonacci depth per shell ═══
            h_deep = h_new  # [B, dc]
            fib_start = self.fib_idx[c]
            for ld in range(self.fib_layers[c]):
                wi = self.W_fib[fib_start + ld]
                bi = self.b_fib[fib_start + ld]
                h_deep = F.softplus(h_deep @ wi + bi) + 0.01
                # Fibonacci dropout: deeper layers drop more, training only
                if self.training and self.fib_dropout > 0 and ld < self.fib_layers[c] - 1:
                    drop_p = self.fib_dropout * (ld + 1) / self.fib_layers[c]
                    h_deep = F.dropout(h_deep, p=drop_p)

            h_deep_list.append(h_deep)

        # ═══ 6. Radial coupling (block-diagonal) ═══
        C_soft = F.softmax(self.C, dim=-1)  # [n_s, n_s]
        # Build block-diagonal coupling matrix [D, D]
        D_sum = sum(self.D_c)
        W_couple = torch.zeros(D_sum, D_sum, device=dev, dtype=psi.dtype)
        off_i = 0
        for i in range(n_s):
            di = self.D_c[i]
            off_j = 0
            for j in range(n_s):
                dj = self.D_c[j]
                w = C_soft[i, j]
                k = min(di, dj)
                if k > 0:
                    idx = torch.arange(k, device=dev)
                    W_couple[off_j + idx, off_i + idx] = w
                off_j += dj
            off_i += di

        # Concatenate all shells → [B, D] and apply coupling
        h_all = torch.cat(h_deep_list, dim=-1)  # [B, D]
        h_coupled = h_all @ W_couple            # [B, D]

        # ═══ 7. Output projection ═══
        # Sum over shells of (h_coupled_c @ W_output[c] + b_output[c]) → [B, 2d]
        dpsi = torch.zeros(B, 2 * self.d, device=dev, dtype=psi.dtype)
        off = 0
        for c in range(n_s):
            dc = self.D_c[c]
            h_c = h_coupled[:, off:off + dc]            # [B, dc]
            dpsi = dpsi + (h_c @ self.W_output[c] + self.b_output[c])
            off += dc

        # ═══ 8. Split real/imag ═══
        dpsi_real = dpsi[:, :self.d]
        dpsi_imag = dpsi[:, self.d:]

        return dpsi_real, dpsi_imag, brain_h_next
