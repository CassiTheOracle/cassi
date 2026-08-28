#!/usr/bin/env python3
"""CubicCord — 3D grid PDE for universal byte-stream learning.

Encodes a window of bytes as a 3D grid (H×W×D), processes with a 3D PDE,
and predicts tokens at masked voxel positions. The grid preserves the
shape of the input data across all three dimensions.

Architecture:
    Bytes → GridReshape → ByteEmbedder → 3D PDE → Readout per cell
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from _chakra_utils import PHI_INV
from multi_scale_byte import ByteEmbedder
from pde_cube import PDECube


class CubicCord(nn.Module):
    """Universal byte-sequence model via 3D grid PDE.

    Encodes N bytes as H×W×D grid (N = H*W*D).
    The 3D PDE processes the grid and propagates information
    across all three spatial dimensions.

    Training: mask voxels with noise, predict at masked positions.
    Generation: seed voxels propagate through the PDE volume.

    Args:
        grid_shape: (H, W, D) dimensions of the cubic grid.
        d: Field dimension per voxel.
        V: Vocabulary size (256 for bytes).
        byte_embed_dim: Byte embedding dimension.
        mask_ratio: Fraction of grid cells to mask during training.
    """

    def __init__(self,
                 grid_shape: Tuple[int, int, int] = (16, 16, 16),
                 d: int = 128,
                 V: int = 256,
                 byte_embed_dim: int = 64,
                 mask_ratio: float = 0.5,
                 **kwargs):
        super().__init__()
        self.grid_shape = grid_shape
        self.H, self.W, self.D = grid_shape
        self.N = self.H * self.W * self.D  # total bytes per window
        self.d = d
        self.V = V
        self.mask_ratio = mask_ratio

        # ── Byte embedder → source ──
        self.embedder = ByteEmbedder(d_out=d, byte_embed_dim=byte_embed_dim)
        self.embed_to_imag = nn.Linear(d, d)
        nn.init.normal_(self.embed_to_imag.weight, std=0.02)
        nn.init.zeros_(self.embed_to_imag.bias)

        # ── 3D PDE ──
        self.pde = PDECube(d=d)

        # ── Readout: per-voxel linear decoder ──
        self.readout_head = nn.Linear(2 * d, V)
        nn.init.normal_(self.readout_head.weight, std=0.02)
        nn.init.zeros_(self.readout_head.bias)

    # ── Byte-grid conversion ──

    def _bytes_to_grid(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Reshape flat byte sequence [B, N] to [B, H, W, D].

        Pads or truncates to N = H*W*D.
        """
        B, N = x.shape
        if N < self.N:
            x = F.pad(x, (0, self.N - N), value=0)
        x = x[:, :self.N]
        return x.reshape(B, self.H, self.W, self.D)

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        """Embed flat bytes as paired-real 3D grid [B, H, W, D, d, 2]."""
        grid = self._bytes_to_grid(x)      # [B, H, W, D]
        flat = grid.reshape(-1, self.N)     # [B, N] flattened grid
        emb = self.embedder(flat)           # [B, N, d]
        imag = torch.tanh(self.embed_to_imag(emb))
        source = torch.stack([emb, imag], dim=-1)  # [B, N, d, 2]
        return source.reshape(-1, self.H, self.W, self.D, self.d, 2)

    def readout_positions(self, psi: torch.Tensor) -> torch.Tensor:
        """Decode logits from [B, H, W, D, d, 2] field."""
        flat = psi.reshape(psi.shape[0], -1, 2 * self.d)  # [B, N, 2*d]
        return self.readout_head(F.layer_norm(flat, [2 * self.d]))

    # ── Training loss (masked source) ──

    def training_loss(self,
                      x: torch.Tensor,
                      T: float = 1.0,
                      dt: float = 0.2) -> Tuple[torch.Tensor, Dict]:
        """Masked source training in 3D.

        1. Embed bytes as 3D grid
        2. Mask random voxels with small noise
        3. 3D PDE propagates from visible to masked voxels
        4. CE only at masked positions
        """
        B, N = x.shape

        # 1. Embed as 3D grid
        source = self.embed(x)  # [B, H, W, D, d, 2]

        # 2. Mask with noise
        H, W, D = self.H, self.W, self.D
        mask = torch.rand(B, H, W, D, device=x.device) < self.mask_ratio
        source_masked = source.clone()
        noise = torch.randn_like(source_masked) * 0.01
        source_masked = torch.where(
            mask.unsqueeze(-1).unsqueeze(-1), noise, source_masked)

        # 3. 3D PDE
        psi = self.pde.forward(source_masked, T=T, dt=dt)

        # 4. CE at masked voxels (next-position prediction)
        # Flatten spatial dims for readout
        mask_flat = mask.reshape(B, -1)  # [B, N]
        logits = self.readout_positions(psi)  # [B, N, V]
        pred_mask = mask_flat

        if pred_mask.sum() == 0:
            pred_mask = torch.ones(B, N, dtype=torch.bool, device=x.device)

        logits_masked = logits[pred_mask]
        target_masked = x[pred_mask]
        ce = F.cross_entropy(logits_masked, target_masked)

        # 5. Diagnostics
        with torch.no_grad():
            rho = psi.pow(2).sum(dim=-1)
            E = (rho ** 2 / (rho + PHI_INV ** 2)).mean()

        info = {"loss": ce.item(), "ce": ce.item(), "E_mean": E.item()}
        return ce, info

    # ── Generation ──

    def forward(self, x: torch.Tensor, T: float = 1.0,
                dt: float = 0.2) -> torch.Tensor:
        """Full forward pass: embed → 3D PDE → readout."""
        source = self.embed(x)
        psi = self.pde.forward(source, T=T, dt=dt)
        return self.readout_positions(psi)
