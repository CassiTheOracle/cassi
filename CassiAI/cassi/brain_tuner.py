#!/usr/bin/env python3
"""
BrainTuner — per-step parameter modulator (replaces BrainStep).

Outputs parameter *modulations* (Δρ, Δθ, Δγ, Δα) that tune the ResonantField's
damping, frequency, chakra-diffusion, and spatial-coupling coefficients.
The brain modulates parameters rather than injecting field perturbations.

Architecture is identical to BrainStep (shell geometry, Fibonacci depth,
radial coupling, damped recurrence), but output heads map to 4 modulation
types per shell.
"""

import math
from typing import Dict, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV


class BrainTuner(nn.Module):
    """Parameter modulator for the resonant field.

    Same spherical shell architecture as BrainStep.  Manages its own
    persistent damped-wave state buffer internally.
    """

    def __init__(self, d: int, n_shells: int = 7, D: int = 588,
                 fib_dropout: float = 0.0, max_batch_size: int = 256):
        super().__init__()
        self.d, self.n_shells, self.D_total = d, n_shells, D
        self.fib_dropout = fib_dropout
        self.max_batch_size = max_batch_size

        # Shell geometry
        R_0 = 1.0
        r_c = torch.tensor([R_0 * PHI ** c for c in range(1, n_shells + 1)])
        self.register_buffer('r_c', r_c)
        self.register_buffer('k_c', math.pi / self.r_c)

        # Dimension allocation
        raw_dims = self.r_c / self.r_c.sum()
        dims = (raw_dims * D).long()
        dims[-1] += D - dims.sum()
        self.D_c = dims.tolist()
        self.D_max = max(self.D_c)

        # Input projection per shell
        self.W_input = nn.ParameterList([
            nn.Parameter(torch.randn(2 * d, self.D_c[c]) * 0.02 / math.sqrt(2 * d))
            for c in range(n_shells)])
        self.b_input = nn.ParameterList([
            nn.Parameter(torch.zeros(self.D_c[c])) for c in range(n_shells)])

        # Damping
        gamma_0 = math.log(PHI)
        gamma_scaled = gamma_0 * (R_0 / self.r_c)
        self.log_gamma_c = nn.Parameter(torch.log(gamma_scaled.clamp(min=0.01)))

        # Learnable radial coupling
        C_init = torch.zeros(n_shells, n_shells)
        for i in range(n_shells):
            for j in range(n_shells):
                C_init[i, j] = (1.0 if i == j else
                    (min(r_c[i].item(), r_c[j].item()) / max(r_c[i].item(), r_c[j].item())) ** 2)
        self.C = nn.Parameter(C_init)

        # Breath modulation
        self.alpha_breath = nn.Parameter(torch.zeros(n_shells))
        self.beta_heart = nn.Parameter(torch.zeros(n_shells))

        # Fibonacci depth
        fib = [1, 1]
        while len(fib) < n_shells:
            fib.append(fib[-1] + fib[-2])
        self.fib_layers = fib[:n_shells]
        fib_cumsum = [0]
        for i in range(n_shells - 1):
            fib_cumsum.append(fib_cumsum[-1] + self.fib_layers[i])
        self.register_buffer('fib_idx', torch.tensor(fib_cumsum, dtype=torch.long))

        self.W_fib, self.b_fib = nn.ParameterList(), nn.ParameterList()
        for c in range(n_shells):
            dc = self.D_c[c]
            for _ in range(self.fib_layers[c]):
                self.W_fib.append(nn.Parameter(torch.randn(dc, dc) * 0.02 / math.sqrt(dc)))
                self.b_fib.append(nn.Parameter(torch.zeros(dc)))

        # Output heads: 4 modulations × W_proj[D_c[c], 1]
        self.W_rho = nn.ParameterList([
            nn.Parameter(torch.randn(self.D_c[c], 1) * 0.02) for c in range(n_shells)])
        self.W_theta = nn.ParameterList([
            nn.Parameter(torch.randn(self.D_c[c], 1) * 0.02) for c in range(n_shells)])
        self.W_gamma = nn.ParameterList([
            nn.Parameter(torch.randn(self.D_c[c], 1) * 0.02) for c in range(n_shells)])
        self.W_alpha = nn.ParameterList([
            nn.Parameter(torch.randn(self.D_c[c], 1) * 0.02) for c in range(n_shells)])
        # Shell offset indices (precomputed for coupling)
        shell_off = []
        _off = 0
        for c in range(n_shells):
            shell_off.append(_off)
            _off += self.D_c[c]
        self.register_buffer('_shell_off', torch.tensor(shell_off, dtype=torch.long))
        # Persistent damped-wave state
        self.register_buffer('brain_h', torch.zeros(max_batch_size, n_shells, self.D_max))


    def reset_state(self) -> None:
        self.brain_h.zero_()

    def _expand_brain_h(self, B: int) -> None:
        if B > self.brain_h.shape[0]:
            self.register_buffer('brain_h', torch.zeros(
                B, self.n_shells, self.D_max, device=self.brain_h.device, dtype=self.brain_h.dtype))

    @staticmethod
    def shell_to_chakra(shell_mods: torch.Tensor, C: int = 13) -> torch.Tensor:
        """Linearly interpolate [B, n_shells] or [n_shells] → [B, C] or [C]."""
        n_s = shell_mods.shape[-1]
        shell_idx = torch.linspace(0, n_s - 1, n_s, device=shell_mods.device)
        chakra_idx = torch.linspace(0, n_s - 1, C, device=shell_mods.device)
        if shell_mods.dim() == 1:
            return torch.stack([_lerp(shell_mods, shell_idx, ci) for ci in chakra_idx])
        B = shell_mods.shape[0]
        return torch.stack([_lerp(shell_mods[b], shell_idx, chakra_idx) for b in range(B)])

    def forward(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                yang: float, yin: float) -> Dict[str, torch.Tensor]:
        """One brain step → parameter modulations.

        Manages own persistent brain_h state buffer internally.

        Args:
            psi_real: [B, d] field real (mean-pooled over N).
            psi_imag: [B, d] field imag (mean-pooled over N).
            yang: scalar breath phase.
            yin: scalar heartbeat phase.

        Returns dict with delta_rho, delta_theta, delta_gamma, delta_alpha [B, n_s].
        """
        B = psi_real.shape[0]
        dev = psi_real.device
        n_s = self.n_shells

        psi = torch.cat([psi_real, psi_imag], dim=-1)  # [B, 2d]

        # Per-shell projection
        psi_padded = torch.zeros(B, n_s, self.D_max, device=dev, dtype=psi.dtype)
        for c in range(n_s):
            psi_padded[:, c, :self.D_c[c]] = psi @ self.W_input[c] + self.b_input[c]

        # Breath modulation
        alpha_t = torch.tanh(self.alpha_breath)
        beta_t = torch.tanh(self.beta_heart)
        mod_c = (1.0 + alpha_t * yang) * (1.0 + beta_t * yin)

        # Damped recurrence + Fibonacci depth
        brain_h = self.brain_h[:B].detach().clone()
        brain_h_next = torch.zeros_like(brain_h)
        h_deep_list = []
        for c in range(n_s):
            dc = self.D_c[c]
            damp = torch.exp(-torch.exp(self.log_gamma_c[c]).clamp(min=0.05))
            h_prev = brain_h[:, c, :dc]
            h_new = damp * h_prev + (1.0 - damp) * psi_padded[:, c, :dc] * mod_c[c]
            brain_h_next[:, c, :dc] = h_new
            h_deep = h_new
            fib_start = int(self.fib_idx[c])
            for ld in range(self.fib_layers[c]):
                h_deep = F.softplus(h_deep @ self.W_fib[fib_start + ld]
                                    + self.b_fib[fib_start + ld]) + 0.01
            h_deep_list.append(h_deep)

        # Store next state
        with torch.no_grad():
            self.brain_h[:B].copy_(brain_h_next.detach())

        # Radial coupling — vectorized O(n_s²), no dense [D_sum, D_sum] allocation
        C_soft = F.softmax(self.C, dim=-1)  # [n_s, n_s]
        h_all = torch.cat(h_deep_list, dim=-1)  # [B, D_sum]
        h_coupled = torch.zeros_like(h_all)
        for src in range(self.n_shells):
            off_src = int(self._shell_off[src])
            dc_src = self.D_c[src]
            for tgt in range(self.n_shells):
                w = C_soft[tgt, src]  # from src (col) to tgt (row) — matches W_couple[off_tgt+t, off_src+t]
                off_tgt = int(self._shell_off[tgt])
                k = min(dc_src, self.D_c[tgt])
                if k > 0:
                    h_coupled[:, off_tgt:off_tgt + k] += w * h_all[:, off_src:off_src + k]

        # Output heads: 4 modulations
        delta_rho = torch.zeros(B, n_s, device=dev, dtype=psi.dtype)
        delta_theta = torch.zeros(B, n_s, device=dev, dtype=psi.dtype)
        delta_gamma = torch.zeros(B, n_s, device=dev, dtype=psi.dtype)
        delta_alpha = torch.zeros(B, n_s, device=dev, dtype=psi.dtype)
        off = 0
        for c in range(n_s):
            h_c = h_coupled[:, off:off + self.D_c[c]]
            delta_rho[:, c] = (h_c @ self.W_rho[c]).squeeze(-1)
            delta_theta[:, c] = (h_c @ self.W_theta[c]).squeeze(-1)
            delta_gamma[:, c] = (h_c @ self.W_gamma[c]).squeeze(-1)
            delta_alpha[:, c] = (h_c @ self.W_alpha[c]).squeeze(-1)
            off += self.D_c[c]

        return {'delta_rho': delta_rho, 'delta_theta': delta_theta,
                'delta_gamma': delta_gamma, 'delta_alpha': delta_alpha}


def _lerp(vals: torch.Tensor, idx: torch.Tensor, query: torch.Tensor) -> torch.Tensor:
    """Piecewise linear interpolation."""
    is_scalar = query.dim() == 0
    if is_scalar:
        query = query.unsqueeze(0)
    search = torch.searchsorted(idx, query).clamp(1, len(vals) - 1)
    i0, i1 = search - 1, search
    t = (query - idx[i0]) / (idx[i1] - idx[i0] + 1e-8)
    result = vals[i0] + t * (vals[i1] - vals[i0])
    return result[0] if is_scalar else result
