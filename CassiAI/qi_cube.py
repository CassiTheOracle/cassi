#!/usr/bin/env python3
"""QiCube — 3D grid PDE with Qi-driven local learning.

Combines:
  1. 3D grid encoding (16×16×16 = 4096 bytes per window)
  2. Qi-driven local updates (no backward, no optimizer)
  3. Sliding windows with temporal coherence

Qi = self-surprise of the field when processing a new window.
The model maintains persistent field state across sliding windows.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from _chakra_utils import PHI_INV
from multi_scale_byte import ByteEmbedder
from pde_cube import PDECube


class QiCube(nn.Module):
    """3D grid PDE with Qi-driven local learning.

    Processes bytes in 3D windows (H×W×D grid per window).
    Maintains persistent field state across sliding windows.
    Updates weights via Qi homeostasis (no backward, no optimizer).

    Args:
        grid_shape: (H, W, D) — dimensions of the 3D grid.
        d: Field dimension per voxel.
        V: Vocabulary size (256 for bytes).
        byte_embed_dim: Byte embedding dimension.
        lr: Global learning rate.
        qi_target: Target Qi level for homeostasis.
        E_target: Target field energy.
        dt: PDE time step.
        stride: Window slide stride (bytes).
    """

    def __init__(self,
                 grid_shape: Tuple[int, int, int] = (16, 16, 16),
                 d: int = 128,
                 V: int = 256,
                 byte_embed_dim: int = 64,
                 lr: float = 0.01,
                 qi_target: float = 0.1,
                 E_target: float = 0.2,
                 dt: float = 0.2,
                 stride: int = 512):
        super().__init__()
        self.H, self.W, self.D = grid_shape
        self.grid_size = self.H * self.W * self.D
        self.d = d
        self.V = V
        self.lr = lr
        self.qi_target = qi_target
        self.E_target = E_target
        self.dt = dt
        self.stride = stride

        # ── Byte embedder → source per voxel ──
        self.embedder = ByteEmbedder(d_out=d, byte_embed_dim=byte_embed_dim)
        self.embed_to_imag = nn.Linear(d, d)
        nn.init.normal_(self.embed_to_imag.weight, std=0.02)
        nn.init.zeros_(self.embed_to_imag.bias)

        # ── 3D PDE ──
        self.pde = PDECube(d=d)

        # ── Readout: predict next window from field state ──
        self.readout_head = nn.Linear(d, V)
        nn.init.normal_(self.readout_head.weight, std=0.02)
        nn.init.zeros_(self.readout_head.bias)
        # ── Persistent field state (kept across sliding windows) ──
        self.register_buffer("psi_prev", torch.zeros(1, 1, 1, 1, d, 2))
        self.register_buffer("step_count", torch.tensor(0, dtype=torch.long))
        self.register_buffer("last_qi", torch.tensor(0.0))
        self.register_buffer("breath_phase", torch.tensor(0.0))
        self.register_buffer("readout_correct", torch.tensor(0, dtype=torch.long))
        self.register_buffer("readout_total", torch.tensor(0, dtype=torch.long))

    # ── Byte-grid conversion ──

    def _bytes_to_grid(self, data: bytes,
                       offset: int) -> torch.Tensor:
        """Extract a 3D grid of bytes starting at offset.

        Returns [1, H, W, D] tensor of byte ids.
        """
        window = data[offset:offset + self.grid_size]
        if len(window) < self.grid_size:
            window = window + b'\x00' * (self.grid_size - len(window))
        grid = torch.tensor(list(window), dtype=torch.long).reshape(
            1, self.H, self.W, self.D)
        return grid

    def _embed_grid(self, grid: torch.Tensor) -> torch.Tensor:
        """Embed a 3D byte grid as paired-real [1, H, W, D, d, 2].

        The grid is flattened, embedded per byte, then reshaped.
        """
        B, H, W, D = grid.shape
        flat = grid.reshape(B, -1)  # [1, N]
        emb = self.embedder(flat)   # [1, N, d]
        imag = torch.tanh(self.embed_to_imag(emb))
        source = torch.stack([emb, imag], dim=-1)  # [1, N, d, 2]
        return source.reshape(1, H, W, D, self.d, 2)

    def _all_embeddings(self) -> torch.Tensor:
        """Return [V, d] all byte embeddings for generation."""
        idx = torch.arange(self.V, device=self.psi_prev.device).unsqueeze(0)
        return self.embedder(idx).squeeze(0)

    # ── Qi helpers ──

    def _field_energy(self, psi: torch.Tensor) -> torch.Tensor:
        return psi.pow(2).mean()

    def _field_gradient_mag(self, psi: torch.Tensor) -> torch.Tensor:
        """Mean spatial gradient magnitude across the 3D grid."""
        grad_h = psi[:, 1:] - psi[:, :-1]
        grad_w = psi[:, :, 1:] - psi[:, :, :-1]
        grad_d = psi[:, :, :, 1:] - psi[:, :, :, :-1]
        gh = grad_h.pow(2).mean()
        gw = grad_w.pow(2).mean()
        gd = grad_d.pow(2).mean()
        return (gh + gw + gd) / 3.0

    def _field_nonlinearity(self, psi: torch.Tensor) -> torch.Tensor:
        rho = psi.pow(2).sum(dim=-1)
        return (rho ** 2 / (rho + PHI_INV ** 2)).mean()

    # ── Qi computation ──

    def _compute_qi(self, psi_before: torch.Tensor,
                    psi_after: torch.Tensor) -> torch.Tensor:
        """Qi = M·q — signed self-surprise of the field.

        M = MSE(psi_before, psi_after) — magnitude of change
        q = normalized correlation — direction of change (aligned=+, opposed=-)

        Positive Qi: field was excited by new content (pattern amplification)
        Negative Qi: field was suppressed by new content (pattern mismatch)
        """
        delta = psi_after - psi_before
        M = delta.pow(2).mean()

        corr = (psi_after * psi_before).sum()
        eps = 1e-8
        norm_product = (psi_after.pow(2).sum() + eps) * (psi_before.pow(2).sum() + eps)
        q = corr / norm_product.sqrt().clamp_min(eps)
        q = q.clamp(-1.0, 1.0)

        return M * q

    # ── Local weight updates (no autograd) ──

    def _local_update(self,
                      source: torch.Tensor,
                      psi: torch.Tensor,
                      qi: torch.Tensor,
                      next_byte: int | None = None):
        """Qi-driven local updates + readout delta rule."""
        dQi = qi - self.qi_target

        # 1. ByteEmbedder row update (Hebbian)
        emb = source[..., 0]
        if self.psi_prev.numel() > 1:
            emb_error = emb - self.psi_prev[..., 0]
            flat_error = emb_error.reshape(-1, self.d).mean(dim=0)
            proj = self.embedder.proj.weight
            d_emb = (flat_error @ proj) * torch.sign(dQi)
            self.embedder.byte_embed.weight.data += self.lr * 0.1 * d_emb.unsqueeze(0)

        # 2. PDE coefficients — Qi homeostasis
        E = self._field_energy(psi)
        G = self._field_gradient_mag(psi)
        NL = self._field_nonlinearity(psi)
        nu_sens = (E - self.E_target).clamp(-0.5, 0.5)
        chi_sens = (G - 0.005).clamp(-0.5, 0.5)
        g_sens = (NL - 0.05).clamp(-0.5, 0.5)
        lr_pde = self.lr * 1.0
        self.pde.nu_logit.data += lr_pde * dQi * nu_sens
        self.pde.chi_logit.data -= lr_pde * dQi * chi_sens * 0.5
        self.pde.g_logit.data -= lr_pde * dQi * g_sens * 0.3
        self.pde.nu_logit.data.clamp_(-5.0, 5.0)
        self.pde.chi_logit.data.clamp_(-5.0, 5.0)
        self.pde.g_logit.data.clamp_(-5.0, 5.0)

        # 3. Breath phase
        self.breath_phase += self.lr * 0.1 * dQi
        self.breath_phase = self.breath_phase % (2 * 3.14159)

        # 4. Anneal Qi target
        self.qi_target = max(0.05, self.qi_target - 1e-4)

        # 5. Readout prediction — delta rule (local, no backward)
        if next_byte is not None:
            field_state = psi[..., 0].mean(dim=(1, 2, 3))  # [1, d]
            logits = self.readout_head(field_state)  # [1, V]
            probs = F.softmax(logits[0], dim=-1)
            target = F.one_hot(torch.tensor(next_byte, device=psi.device),
                               num_classes=self.V).float()
            # Delta rule: w -= lr * outer(error, field)
            error = probs - target  # [V]
            # w -= lr * outer(error, field)
            self.readout_head.bias.data -= self.lr * 0.5 * error
            # Track accuracy: max-prob at correct class
            if probs.argmax() == target.argmax():
                self.readout_correct += 1
            self.readout_total += 1
    # ── Core: ingest a 3D window ──

    @torch.no_grad()
    def ingest_window(self,
                      data: bytes,
                      offset: int,
                      learn: bool = True,
                      next_byte: int | None = None) -> float:
        """Process one 3D window of bytes and optionally learn.

        Args:
            data: Full byte sequence.
            offset: Start position for this window.
            learn: If True, update weights via Qi-driven rules.

        Returns:
            qi: Self-surprise value for this window.
        """
        device = self.psi_prev.device

        # 1. Extract and embed 3D grid
        grid = self._bytes_to_grid(data, offset).to(device)
        source = self._embed_grid(grid)  # [1, H, W, D, d, 2]

        # 2. Save state before (if previous state exists)
        if self.psi_prev.numel() > 1 and self.psi_prev.shape[1] == self.H:
            psi_before = self.psi_prev.detach().clone()
        else:
            psi_before = source.detach().clone()

        # 3. Run 3D PDE from source
        psi = self.pde.forward(source, T=self.dt * 5, dt=self.dt)

        # 4. Compute Qi
        qi = self._compute_qi(psi_before, psi)
        self.last_qi = qi.detach().clone()

        # 5. Local updates
        if learn:
            self._local_update(source, psi, qi, next_byte=next_byte)

        # 6. Save field state for next window
        self.psi_prev = psi.detach().clone()
        self.step_count += 1

        return qi.item()

    # ── Generation ──

    @torch.no_grad()
    def generate(self,
                 data: bytes,
                 seed_offset: int,
                 seed_len: int = 64,
                 max_new: int = 256,
                 temp: float = 0.8) -> bytes:
        """Generate bytes by seeding the field and querying it.

        Seeds the 3D field with known bytes, then generates by
        finding which byte's embedding best matches the field state.
        """
        H, W, D = self.H, self.W, self.D
        device = self.psi_prev.device

        # 1. Ingest seed windows (no learn) to prime the field
        current_offset = seed_offset
        while current_offset < seed_offset + seed_len:
            self.ingest_window(data, current_offset, learn=False)
            current_offset += self.stride
        # Generate via nearest-embedding query
        all_embs = self._all_embeddings()
        generated = bytearray()

        for _ in range(max_new):
            field_state = self.psi_prev[..., 0].mean(dim=(1, 2, 3))
            sim = F.normalize(field_state, dim=-1) @ F.normalize(all_embs, dim=-1).T
            probs = F.softmax(sim[0] / max(temp, 1e-6), dim=-1)
            if not torch.isfinite(probs).all() or probs.sum() == 0:
                probs = torch.ones(self.V, device=device) / self.V
            byte = torch.multinomial(probs, 1).item()
            generated.append(byte)
            mock_data = data + bytes(generated)
            self.ingest_window(mock_data, current_offset + len(generated) - 1,
                               learn=False)

        return bytes(generated)

    # ── Forward (compatibility) ──

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Process a batch of bytes for testing."""
        source = self._embed_grid(x.reshape(1, -1).reshape(1, self.H, self.W, self.D))
        psi = self.pde.forward(source, T=self.dt * 5, dt=self.dt)
        return self._field_energy(psi).unsqueeze(0)
