#!/usr/bin/env python3
"""
Spine3D — 3D spherical shell chakra system.

Seven concentric shells at golden-section radii process 3D input through
the damped wave equation in spherical geometry. Each shell captures
a different angular resolution (spherical harmonic bandwidth).

The core recurrence is the same as 1D:
    qi_c[t] = damp_c · qi_c[t-1] + (1-damp_c) · ψ_c[t]

But the geometry is 3D: shells instead of points, radial coupling with
1/r² decay, dimensions proportional to shell surface area.

Architecture:
    3D input → per-shell projection → qi recurrence → coupling → output

Adapted for cassi: uses PHI/PHI_INV from cassi.cord, register_buffer for
persistent state, and optional modulation args for top-down coupling.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import Any, Dict, Optional

from cassi.cord import PHI, PHI_INV


class Spine3D(nn.Module):
    """3D spherical spine with 7 chakra shells.

    Args:
        D: total dimensions across all shells (default 588).
        n_shells: number of concentric shells (default 7).
        input_dim: dimension of input feature vector per token (default 96 = nw).
    """

    def __init__(self, n_shells=7, input_dim=96, D=588, fib_layers=None, fib_dropout=0.0,
                 cord_width=None):
        super().__init__()
        self.D = D
        self.n_shells = n_shells
        self.input_dim = input_dim
        self.fib_dropout = fib_dropout
        if cord_width is None:
            cord_width = max(1, input_dim // 4)
        self.cord_width = cord_width

        # ═══ SHELL GEOMETRY ═══
        # Radii: r_c = R_0 · φ^c, c = 1..7
        R_0 = 1.0
        r_c = torch.tensor([R_0 * PHI ** c for c in range(1, n_shells + 1)])
        self.register_buffer('r_c', r_c)  # [7] — shell radii

        # Wavenumbers: k_c = π / r_c (spherical standing wave condition)
        self.register_buffer('k_c', math.pi / self.r_c)

        # ═══ DIMENSION ALLOCATION ═══
        # D_c ∝ r_c (linear in radius for v1, rather than r_c²)
        # This gives ~φ^c scaling, gentler than φ^{2c}
        raw_dims = self.r_c / self.r_c.sum()
        dims = (raw_dims * D).long()
        dims[-1] += D - dims.sum()
        self.D_c = dims.tolist()
        dim_cumsum = torch.tensor(self.D_c).cumsum(0)
        self.register_buffer('dim_splits', dim_cumsum)

        # ═══ INPUT PROJECTION ═══
        # Project global wavelength amps → per-shell coefficients
        self.W_input = nn.ParameterList([
            nn.Parameter(torch.randn(input_dim, self.D_c[c]) * 0.02 / math.sqrt(input_dim))
            for c in range(n_shells)
        ])
        self.b_input = nn.ParameterList([
            nn.Parameter(torch.zeros(self.D_c[c])) for c in range(n_shells)
        ])

        # ═══ DAMPING ═══
        # Per-shell damping (outer shells damp slower — longer memory)
        # γ_c = γ_0 · (r_0 / r_c)  →  larger radius = lower damping
        # Init: γ_0 = ln(φ) ≈ 0.481 → damp_0 = 1/φ ≈ 0.618
        gamma_0 = math.log(PHI)
        gamma_scaled = gamma_0 * (R_0 / self.r_c)
        self.log_gamma_c = nn.Parameter(torch.log(gamma_scaled.clamp(min=0.01)))

        # ═══ RADIAL INTERFERENCE ═══
        # Precompute static geometry part: M_geom[i,j] = spread * cos(k*dr)
        # Forward: M_intf = C.detach() * M_geom  (C is trainable)
        M_geom = torch.zeros(n_shells, n_shells)
        for i in range(n_shells):
            for j in range(n_shells):
                if i != j:
                    dr = self.r_c[i] - self.r_c[j]
                    phase = self.k_c[i] * dr
                    spread = self.r_c[j] / self.r_c[i] if j < i else self.r_c[i] / self.r_c[j]
                    M_geom[i, j] = spread * torch.cos(phase)
        self.register_buffer('M_geom', M_geom)

        # ═══ RADIAL COUPLING ═══
        # Learnable coupling matrix C[i][j] for energy transfer
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

        # ═══ RECONSTRUCTION DECODER ═══
        # Self-supervised: can we reconstruct psi_in from qi?
        self.W_recon = nn.ParameterList([
            nn.Parameter(torch.randn(self.D_c[c], input_dim) * 0.02 / math.sqrt(self.D_c[c]))
            for c in range(n_shells)
        ])
        self.b_recon = nn.ParameterList([
            nn.Parameter(torch.zeros(input_dim)) for c in range(n_shells)
        ])

        # ═══ FIBONACCI DEPTH ═══
        # Each shell gets F_c internal processing layers.
        # Crown has 13 layers for deep nested concepts.
        # Root has 1 layer for raw pattern matching.
        if fib_layers is not None:
            self.fib_layers = fib_layers
        else:
            # Auto-generate from Fibonacci: [1, 1, 2, 3, 5, 8, 13, 21, ...]
            fib = [1, 1]
            while len(fib) < n_shells:
                fib.append(fib[-1] + fib[-2])
            self.fib_layers = fib[:n_shells]

        # Precompute cumulative Fibonacci indices for forward pass
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

        # ═══ INITIAL STATE ═══
        self.h0 = nn.Parameter(torch.zeros(1, D))
        # === CORD BUS INTERFACE (the conduit) ===
        self.bus_to_input = nn.Linear(cord_width, input_dim)
        self.shells_to_bus = nn.Linear(D, cord_width)
        nn.init.normal_(self.bus_to_input.weight, std=0.02 / math.sqrt(cord_width))
        nn.init.zeros_(self.bus_to_input.bias)
        nn.init.normal_(self.shells_to_bus.weight, std=0.02 / math.sqrt(D))
        nn.init.zeros_(self.shells_to_bus.bias)

        # Use interference by default; set False for text-only.
        self.use_interference = True

    def forward(self, psi_in, breath_seq=None, heartbeat_seq=None, return_diag=False,
                damping_offset=None, breath_offset=None, coupling_scale=None,
                breath_module: Optional[Any] = None):
        """Forward pass through the 3D spine (vectorized).

        Args:
            psi_in: [B, L, input_dim] input tokens/features.
            breath_seq: [L] optional external breath rhythm (default: 29-step sine).
            heartbeat_seq: [L] optional external heartbeat rhythm.
            return_diag: if True, include detailed diagnostics.
            damping_offset: [n_shells] added to log_gamma_c before exp (None = no-op).
            breath_offset: [n_shells] added to alpha_breath before tanh (None = no-op).
            coupling_scale: [n_shells, n_shells] multiplied with C before softmax
                           (None = no-op). Centered at 1.0.
            breath_module: Optional[Breath]-like module. When provided, the brain
                           reads its CURRENT phase (yang → breath_seq,
                           yin → heartbeat_seq) without calling step(). This
                           keeps the brain's heart in sync with the mind's
                           when MindBrainField passes `self.mind.breath`.
                           Default None uses static 29/1.2 sine waves.
        """
        B, L, _ = psi_in.shape
        dev = psi_in.device
        n_s = self.n_shells
        D_max = max(self.D_c)  # max dimension across shells

        # ═══ RHYTHMS ═══
        T_breath = 29.0
        if breath_module is not None:
            # Live breath coupling: use the breath module's CURRENT phase.
            # The Mind's field_step is the master clock — we do NOT call
            # step() here, we just read the current phase. This keeps the
            # brain's heart in sync with the mind's.
            phase_yang = breath_module.t_yang.detach()
            omega_yang = breath_module.omega_yang.detach()
            phase_yin = breath_module.t_yin.detach()
            omega_yin = breath_module.omega_yin.detach()
            t = torch.arange(L, device=dev, dtype=psi_in.dtype)
            breath_seq = torch.sin(phase_yang + omega_yang * t)
            heartbeat_seq = 0.5 + 0.5 * torch.sin(phase_yin + omega_yin * t)
        else:
            if breath_seq is None:
                t = torch.arange(L, device=dev, dtype=psi_in.dtype)
                breath_seq = torch.sin(2 * math.pi * t / T_breath)
            if heartbeat_seq is None:
                t = torch.arange(L, device=dev, dtype=psi_in.dtype)
                heartbeat_seq = 0.5 + 0.5 * torch.sin(2 * math.pi * t / 1.2)
        # ═══ BATCHED PER-SHELL PROJECTION ═══
        # Project psi_in → [B, L, n_s, D_max] padded
        psi_in_flat = psi_in.reshape(B * L, self.input_dim)
        psi_padded = torch.zeros(B, L, n_s, D_max, device=dev, dtype=psi_in.dtype)
        for c in range(n_s):
            dc = self.D_c[c]
            psi_c = psi_in_flat @ self.W_input[c] + self.b_input[c]
            psi_padded[:, :, c, :dc] = psi_c.reshape(B, L, dc)

        # ═══ RADIAL INTERFERENCE (M_intf = C.detach() * M_geom) ═══
        if getattr(self, 'use_interference', True):
            M_intf = self.C.detach() * self.M_geom  # C provides amplitude, geometry provides phase
            psi_intf = psi_padded + torch.einsum('bljd,ij->blid', psi_padded, M_intf)
        else:
            psi_intf = psi_padded

        # ═══ DAMPING (per-shell, can't vectorize due to different damp rates) ═══
        if damping_offset is not None:
            gamma_c = torch.exp(self.log_gamma_c + damping_offset.to(dev)).clamp(min=0.05)
        else:
            gamma_c = torch.exp(self.log_gamma_c).clamp(min=0.05)  # [n_s]
        damp_c = torch.exp(-gamma_c)

        # Breath/heartbeat modulation [L, n_s]
        if breath_offset is not None:
            alpha = torch.tanh(self.alpha_breath + breath_offset.to(dev))
        else:
            alpha = torch.tanh(self.alpha_breath)
        beta = torch.tanh(self.beta_heart)
        mod_c = ((1.0 + alpha.unsqueeze(0) * breath_seq.unsqueeze(-1)) *
                 (1.0 + beta.unsqueeze(0) * heartbeat_seq.unsqueeze(-1)))  # [L, n_s]

        # ═══ CUMSUM (per-shell, still loop but each is GPU-heavy cumsum) ═══
        h0_flat = self.h0.expand(B, self.D).clone()
        h_all = torch.zeros(B, L, self.D, device=dev, dtype=psi_in.dtype)
        t_arr = torch.arange(L, device=dev, dtype=psi_in.dtype)

        off = 0
        for c in range(n_s):
            dc = self.D_c[c]
            damp = damp_c[c]
            mod = mod_c[:, c:c + 1]  # [L, 1]
            psi_c = psi_intf[:, :, c, :dc] * mod.unsqueeze(0)

            damp_pow = damp ** t_arr
            z = psi_c / damp_pow.unsqueeze(0).unsqueeze(-1).clamp(min=1e-10)
            h_c = damp_pow.unsqueeze(0).unsqueeze(-1) * (
                h0_flat[:, off:off + dc].unsqueeze(1) + torch.cumsum(z, dim=1)
            )
            # Fibonacci depth: F_c internal processing layers
            fib_idx = self.fib_idx[c]  # use precomputed buffer
            h_deep = h_c.reshape(B * L, dc)
            for ld in range(self.fib_layers[c]):
                wi = self.W_fib[fib_idx + ld]
                bi = self.b_fib[fib_idx + ld]
                h_deep = F.softplus(h_deep @ wi + bi) + 0.01
                # Fibonacci dropout: deeper layers drop more, only during training
                if self.training and self.fib_dropout > 0 and ld < self.fib_layers[c] - 1:
                    drop_p = self.fib_dropout * (ld + 1) / self.fib_layers[c]
                    h_deep = F.dropout(h_deep, p=drop_p)
            h_c = h_deep.reshape(B, L, dc)
            h_all[:, :, off:off + dc] = h_c.to(h_all.dtype)
            off += dc

        # ═══ RADIAL COUPLING (block-diagonal, element-wise equivalent) ═══
        if coupling_scale is not None:
            C_scaled = self.C * coupling_scale.to(dev)
            C_soft = F.softmax(C_scaled, dim=-1)
        else:
            C_soft = F.softmax(self.C, dim=-1)
        W_couple = torch.zeros(self.D, self.D, device=dev, dtype=h_all.dtype)
        off_i = 0
        for i in range(n_s):
            di = self.D_c[i]
            off_j = 0
            for j in range(n_s):
                dj = self.D_c[j]
                w = C_soft[i, j]
                k = min(di, dj)  # number of elements that actually couple
                if k > 0:
                    # Set DIAGONAL of each block, not entire block
                    idx = torch.arange(k, device=dev)
                    W_couple[off_j + idx, off_i + idx] = w.to(W_couple.dtype)
                off_j += dj
            off_i += di
        h_coupled = h_all @ W_couple

        # ═══ ENERGY DENSITY + FLATTEN TO DIAGNOSTIC (per-shell) ═══
        qi_energy = torch.zeros(B, L, n_s, device=dev)
        qi_all = h_coupled + 0.1 * torch.tanh(h_coupled)
        off = 0
        for c in range(n_s):
            dc = self.D_c[c]
            h_c = h_coupled[:, :, off:off + dc]  # [B, L, dc]
            e_c = h_c.pow(2).sum(dim=-1) / max(dc, 1)  # [B, L]
            qi_energy[:, :, c] = e_c / (e_c + 1.0)
            off += dc

        # Energy flow: P[i,j] = C[i,j] * (e_j - e_i)
        e_all = qi_energy  # [B, L, n_s]
        P_flow = C_soft.unsqueeze(0).unsqueeze(0) * (e_all.unsqueeze(-1) - e_all.unsqueeze(-2))
        net_power = P_flow.sum(dim=-1)  # [B, L, n_s]

        # ═══ FLUID QI: harmony + breath-gated yang/yin (fused per-shell) ═══
        harmony_qi = torch.zeros(B, L, n_s, device=dev)
        off = 0
        for c in range(n_s):
            dc = self.D_c[c]
            qi_c = qi_all[:, :, off:off + dc]
            psi_c = psi_intf[:, :, c, :dc]

            psi_norm = psi_c.norm(dim=-1, keepdim=True)
            qi_norm = qi_c.norm(dim=-1, keepdim=True).clamp(min=1e-8)
            yang_c = psi_norm / qi_norm
            yin_c = gamma_c[c].view(1, 1, 1)
            harmony_c = torch.tanh(yang_c - yin_c)
            harmony_qi[:, :, c:c + 1] = yang_c * torch.sigmoid(harmony_c * 3.0)
            off += dc

        # ═══ WAVE RECONSTRUCTION (fused into same loop) ═══
        psi_recon = torch.zeros(B * L, self.input_dim, device=dev, dtype=qi_all.dtype)
        off = 0
        for c in range(n_s):
            dc = self.D_c[c]
            qi_c = qi_all[:, :, off:off + dc].reshape(B * L, dc)
            psi_recon = psi_recon + qi_c @ self.W_recon[c] + self.b_recon[c]
            off += dc

        # ═══ DIAGNOSTICS ═══
        out = {'qi_all': qi_all, 'harmony_qi': harmony_qi,
               'qi_energy': qi_energy, 'psi_recon': psi_recon,
               'net_power': net_power}
        if return_diag:
            out['diag'] = {
                'gamma_mean': gamma_c.mean().item(),
                'radii': self.r_c.tolist(),
                'dims': self.D_c,
                'coupling': C_soft.detach().cpu().tolist(),
                'harmony_mean': harmony_qi.mean().item(),
                'energy_mean': qi_energy.mean().item(),
                'power_mean': net_power.abs().mean().item(),
            }

        return out

    def receive_bus(self, bus_signal: torch.Tensor,
                    breath_module: Optional[Any] = None) -> Dict[str, torch.Tensor]:
        """Conduit entry point: receive bus signal from CordBus, return brain response.

        The bus signal `[B, N, cord_width]` is the formal "P[psi] compressed to
        the conduit width" from section 10.1 of the Qi-Fluid formalism. This
        method projects it to the brain's input_dim, runs the existing forward
        (zero new physics), and projects qi_all back to cord_width.

        Args:
            bus_signal: [B, N, cord_width] from CordBus.ascend.
            breath_module: optional shared Breath module.

        Returns:
            Dict with all forward() outputs PLUS 'bus_response': [B, N, cord_width].
        """
        z = self.bus_to_input(bus_signal)                 # [B, N, input_dim]
        out = self.forward(z, breath_module=breath_module)
        out['bus_response'] = self.shells_to_bus(out['qi_all'])  # [B, N, cord_width]
        return out
