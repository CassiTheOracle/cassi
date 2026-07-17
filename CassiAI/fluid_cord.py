#!/usr/bin/env python3
"""FluidCord — Single-field PDE for byte-sequence prediction.

Training matches generation: mask source positions with small noise,
predict tokens at masked positions using PDE-propagated field states.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from _chakra_utils import PHI_INV
from multi_scale_byte import ByteEmbedder
from single_field_pde import SingleFieldPDE


class FluidCord(nn.Module):
    """Byte-sequence prediction via single-field PDE.

    Masked source training: random positions get small-noise source.
    The readout predicts tokens only at those positions, forcing the PDE
    to propagate information from visible to masked positions.

    Args:
        N: Number of spatial positions.
        d: Field dimension per position.
        V: Vocabulary size (256 for bytes).
        byte_embed_dim: Byte embedding dimension.
        mask_ratio: Fraction of source positions to mask during training.
    """

    def __init__(self,
                 N: int = 128,
                 d: int = 128,
                 V: int = 256,
                 byte_embed_dim: int = 64,
                 mask_ratio: float = 0.5,
                 **kwargs):
        super().__init__()
        self.N = N
        self.d = d
        self.V = V
        self.mask_ratio = mask_ratio

        self.embedder = ByteEmbedder(d_out=d, byte_embed_dim=byte_embed_dim)
        self.embed_to_imag = nn.Linear(d, d)
        nn.init.normal_(self.embed_to_imag.weight, std=0.02)
        nn.init.zeros_(self.embed_to_imag.bias)

        self.pde = SingleFieldPDE(d=d)

        self.readout_head = nn.Linear(2 * d, V)
        nn.init.normal_(self.readout_head.weight, std=0.02)
        nn.init.zeros_(self.readout_head.bias)

        # ── Sinusoidal position embeddings (precomputed) ──
        pos = torch.arange(N).float().unsqueeze(1)  # [N, 1]
        dim_range = torch.arange(d).float().unsqueeze(0)  # [1, d]
        freq = 1.0 / (10000.0 ** (dim_range / d))  # [1, d]
        pos_emb = torch.sin(pos * freq)  # [N, d]
        self.register_buffer("pos_embedding", pos_emb)

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        """Embed bytes as paired-real source [B, N, d, 2].
        Pure content — no position info. Position is added at readout.
        """
        B, N = x.shape
        emb = self.embedder(x)
        imag = torch.tanh(self.embed_to_imag(emb))
        return torch.stack([emb, imag], dim=-1)

    def readout_positions(self, psi: torch.Tensor) -> torch.Tensor:
        """Decode logits from [B, N, d, 2] field with position info.

        Position embedding added at readout time so the PDE processes
        pure content. The readout sees both propagated field content
        and where it is in space.
        """
        B, N = psi.shape[:2]
        pos = self.pos_embedding[:N].unsqueeze(0).unsqueeze(-1)  # [1, N, d, 1]
        psi_with_pos = psi + pos  # add position to both real+imag
        flat = psi_with_pos.reshape(B, N, -1)
        return self.readout_head(F.layer_norm(flat, [2 * self.d]))

    def training_loss(self,
                      x: torch.Tensor,
                      T: float = 1.0,
                      dt: float = 0.2) -> Tuple[torch.Tensor, Dict]:
        """Masked source training: predict tokens at noisy-masked positions.

        The PDE must propagate information from visible positions to
        masked positions — the same skill needed during generation.
        """
        B, N = x.shape

        source = self.embed(x)

        # Mask with small noise (not exact zeros — PDE backward unstable at 0)
        mask = torch.rand(B, N, device=x.device) < self.mask_ratio
        source_masked = source.clone()
        source_masked[mask] = torch.randn_like(source_masked[mask]) * 0.01

        psi = self.pde.forward(source_masked, T=T, dt=dt)

        # CE only at masked positions (shifted by 1 for next-token)
        logits = self.readout_positions(psi[:, :-1])
        pred_mask = mask[:, :-1]

        if pred_mask.sum() == 0:
            pred_mask = torch.ones(B, N - 1, dtype=torch.bool, device=x.device)

        logits_masked = logits[pred_mask]
        target_masked = x[:, 1:][pred_mask]
        ce = F.cross_entropy(logits_masked, target_masked)

        with torch.no_grad():
            rho = psi.pow(2).sum(dim=-1)
            E = (rho ** 2 / (rho + PHI_INV ** 2)).mean()

        info = {
            "loss": ce.item(),
            "ce": ce.item(),
            "E_mean": E.item(),
        }
        return ce, info

    @torch.no_grad()
    def generate(self,
                 seed: Optional[torch.Tensor] = None,
                 max_new: int = 64,
                 temp: float = 0.8,
                 top_p: float = 0.9,
                 T: float = 1.0,
                 dt: float = 0.2) -> torch.Tensor:
        """Generate by seeding the PDE and reading out next positions."""
        device = next(self.parameters()).device
        V = self.V

        if seed is None or seed.numel() == 0:
            seed = torch.randint(0, V, (1,), device=device)
        seed = seed.to(device).long()
        L = seed.numel()

        if L + max_new > self.N:
            max_new = self.N - L

        source = torch.zeros(1, self.N, self.d, 2, device=device)
        source[:, :L] = self.embed(seed.unsqueeze(0))

        psi = self.pde.forward(source, T=T, dt=dt)
        logits = self.readout_positions(psi[:, L:L + max_new])
        logits = logits[0] / max(temp, 1e-6)

        if top_p < 1.0:
            for row in range(logits.size(0)):
                s, si = torch.sort(logits[row], descending=True)
                cum = torch.cumsum(F.softmax(s, dim=-1), dim=-1)
                remove = cum > top_p
                remove[1:] = remove[:-1].clone()
                remove[0] = False
                logits[row, si[remove]] = -float('inf')

        probs = F.softmax(logits, dim=-1)
        bad = ~torch.isfinite(probs).all(dim=-1) | (probs.sum(dim=-1) == 0)
        if bad.any():
            probs[bad] = torch.ones(V, device=device) / V
        return torch.multinomial(probs, 1).squeeze(-1)

    def forward(self, x: torch.Tensor, T: float = 1.0,
                dt: float = 0.2) -> torch.Tensor:
        source = self.embed(x)
        psi = self.pde.forward(source, T=T, dt=dt)
        return self.readout_positions(psi)
