#!/usr/bin/env python3
"""OnlineCord — fully online, self-supervised PDE via Qi-driven local learning.

No backward passes, no optimiser, no training/eval split, no next-token prediction.
Ingests bytes one at a time, learns from every byte via Qi-driven local rules.

Qi = M·q = MSE(psi_before, psi_curr) — the field's self-surprise at each byte.
The model maintains Qi homeostasis: if surprised too much, dampen; if too bored, excite.

Learning rules (all local, no autograd):
  1. ByteEmbedder row: Hebbian (strength proportional to Qi)
  2. PDE coefficients: homeostatic (each responds to Qi + sensitivity)
  3. Breath phase: shifts with Qi (surprise modulates breathing rhythm)
"""

from __future__ import annotations

from typing import List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from _chakra_utils import PHI_INV
from multi_scale_byte import ByteEmbedder
from single_field_pde import SingleFieldPDE


class OnlineCord(nn.Module):
    """Fully online PDE that learns via Qi-driven local rules.

    No backward passes, no optimiser. Ingests one byte at a time.

    Args:
        d: Field dimension per position.
        N: Ring buffer length (spatial positions).
        V: Vocabulary size (256 for bytes).
        byte_embed_dim: Byte embedding dimension.
        lr: Global learning rate (multiplied per-rule below).
        qi_target: Target Qi level for homeostasis.
        E_target: Target field energy level.
        G_target: Target spatial gradient level.
        NL_target: Target nonlinear coupling level.
        dt: PDE time step.
    """

    def __init__(self,
                 d: int = 128,
                 N: int = 128,
                 V: int = 256,
                 byte_embed_dim: int = 64,
                 lr: float = 0.01,
                 qi_target: float = 0.1,
                 E_target: float = 0.2,
                 G_target: float = 0.01,
                 NL_target: float = 0.05,
                 dt: float = 0.2):
        super().__init__()
        self.d = d
        self.N = N
        self.V = V
        self.lr = lr
        self.qi_target = qi_target
        self.E_target = E_target
        self.G_target = G_target
        self.NL_target = NL_target
        self.dt = dt

        # ── Byte embedder → source ──
        self.embedder = ByteEmbedder(d_out=d, byte_embed_dim=byte_embed_dim)
        self.embed_to_imag = nn.Linear(d, d)
        nn.init.normal_(self.embed_to_imag.weight, std=0.02)
        nn.init.zeros_(self.embed_to_imag.bias)

        # ── PDE (fixed coefficients for reservoir dynamics) ──
        self.pde = SingleFieldPDE(d=d)

        # ── Persistent field state (ring buffer, never reset) ──
        self.register_buffer("psi", torch.zeros(1, N, d, 2))
        self.register_buffer("step_count", torch.tensor(0, dtype=torch.long))
        self.register_buffer("last_qi", torch.tensor(0.0))

        # ── Breath phase ──
        self.register_buffer("breath_phase", torch.tensor(0.0))

    # ── Embedding ──

    def _embed(self, byte_t: torch.Tensor) -> torch.Tensor:
        """Embed one byte as paired-real source [1, 1, d, 2]."""
        emb = self.embedder(byte_t)  # [1, 1, d]
        imag = torch.tanh(self.embed_to_imag(emb))
        return torch.stack([emb, imag], dim=-1)

    def _all_embeddings(self) -> torch.Tensor:
        """Return [V, d] all byte embeddings for generation similarity search."""
        idx = torch.arange(self.V, device=self.psi.device).unsqueeze(0)
        return self.embedder(idx).squeeze(0)

    # ── Local helpers for Qi homeostasis ──

    def _field_energy(self, psi: torch.Tensor) -> torch.Tensor:
        """E = mean squared magnitude per position."""
        return psi.pow(2).mean()

    def _field_gradient(self, psi: torch.Tensor) -> torch.Tensor:
        """G = mean spatial gradient magnitude."""
        grad = torch.zeros_like(psi[..., 0])
        grad[:, 1:-1] = (psi[:, 2:, :, 0] - psi[:, :-2, :, 0]) / 2.0
        return grad.pow(2).mean()

    def _field_nonlinearity(self, psi: torch.Tensor) -> torch.Tensor:
        """NL = mean deviation from identity (how nonlinear)."""
        rho = psi.pow(2).sum(dim=-1)
        return (rho ** 2 / (rho + PHI_INV ** 2)).mean()

    # ── Ingest (the core learning step) ──

    @torch.no_grad()
    def ingest(self,
               byte: int,
               learn: bool = True,
               target_byte: Optional[int] = None) -> float:
        """Process one byte and (optionally) learn from it via local rules.

        Args:
            byte: The byte to ingest [0, 255].
            learn: If True, update weights via Qi-driven local rules.
            target_byte: Optional. If given, Qi is computed relative to this
                         target byte's effect (used during generation).

        Returns:
            qi: The computed Qi (self-surprise) value.
        """
        device = self.psi.device
        byte_t = torch.tensor([[byte]], device=device, dtype=torch.long)

        # ── 1. Save old state ──
        psi_before = self.psi.detach().clone()  # [1, N, d, 2]

        # ── 2. Embed byte ──
        source = self._embed(byte_t)  # [1, 1, d, 2]

        # ── 3. Slide ring buffer, inject source ──
        self.psi = torch.roll(self.psi, shifts=-1, dims=1)
        self.psi[:, -1:] = source

        # ── 4. Integrate PDE one step ──
        self.psi = self.pde.forward(self.psi, T=self.dt, dt=self.dt)

        # ── 5. Compute Qi = M·q ──
        # M = magnitude of change
        delta = self.psi - psi_before
        M = delta.pow(2).mean()

        # q = charge (direction): correlation between before/after
        corr = (self.psi * psi_before).sum()
        eps = 1e-8
        norm_product = (self.psi.pow(2).sum() + eps) * (psi_before.pow(2).sum() + eps)
        q = corr / norm_product.sqrt().clamp_min(eps)
        q = q.clamp(-1.0, 1.0)

        qi = M * q  # signed self-surprise
        self.last_qi = qi.detach().clone()

        # ── 6. Optional: target-aware Qi gap ──
        if target_byte is not None and learn:
            target_t = torch.tensor([[target_byte]], device=device, dtype=torch.long)
            target_source = self._embed(target_t)
            # Simulate what field would look like with target instead
            test_psi = psi_before.clone()
            test_psi[:, -1:] = target_source
            test_psi = self.pde.forward(test_psi, T=self.dt, dt=self.dt)
            delta_target = test_psi - psi_before
            M_target = delta_target.pow(2).mean()
            qi_target_sim = M_target * q  # same charge, different magnitude
            qi = qi_target_sim  # use the target-aware Qi instead
            qi = qi.detach().clone()

        # ── 7. Local weight updates (no autograd) ──
        if learn:
            dQi = (qi - self.qi_target).clamp(-1.0, 1.0)

            # 7a. ByteEmbedder row update (Hebbian)
            emb_error = source - psi_before[:, -1:]
            # emb_error: [1, 1, d, 2] → average over last dim → [1, 1, d]
            emb_error_real = emb_error[..., 0]  # [1, 1, d]
            row = self.embedder.byte_embed.weight[byte]
            # The embedding row affects the output through embedder → proj → d
            proj = self.embedder.proj.weight  # [d, byte_embed_dim]
            d_emb = (emb_error_real.squeeze() @ proj) * torch.sign(dQi)
            row.data += self.lr * 0.02 * d_emb

            # 7b. PDE coefficients — Qi homeostasis
            E = self._field_energy(self.psi)
            G = self._field_gradient(self.psi)
            NL = self._field_nonlinearity(self.psi)

            # Each coefficient has a sensitivity term: (X - X_target) approximates ∂Qi/∂θ
            nu_sens = (E - self.E_target).clamp(-0.5, 0.5)
            chi_sens = (G - self.G_target).clamp(-0.5, 0.5)
            g_sens = (NL - self.NL_target).clamp(-0.5, 0.5)

            # Qi homeostasis: if Qi > target, dampen the coefficient (reduce)
            # If Qi < target, excite the coefficient (increase)
            lr_pde = self.lr * 0.1
            self.pde.nu_logit.data += lr_pde * dQi * nu_sens
            self.pde.chi_logit.data -= lr_pde * dQi * chi_sens * 0.5
            self.pde.g_logit.data -= lr_pde * dQi * g_sens * 0.3
            # Clamp PDE coefficients to prevent runaway
            self.pde.nu_logit.data.clamp_(-5.0, 5.0)
            self.pde.chi_logit.data.clamp_(-5.0, 5.0)
            self.pde.g_logit.data.clamp_(-5.0, 5.0)

            # 7c. Breath phase
            self.breath_phase += self.lr * 0.1 * dQi
            self.breath_phase = self.breath_phase % (2 * 3.14159)

            # 7d. Anneal Qi target toward base level
            self.qi_target = max(0.05, self.qi_target - 1e-5)

        self.step_count += 1
        return qi.item()

    # ── Generation ──

    @torch.no_grad()
    def generate(self,
                 seed: Optional[List[int]] = None,
                 max_new: int = 64,
                 temp: float = 0.8) -> List[int]:
        """Generate bytes by embedding-similarity field-state query.

        Compares the field state at the newest position to all byte
        embeddings without running the PDE for each candidate.
        """
        if seed:
            for b in seed:
                self.ingest(b, learn=False)

        all_embs = self._all_embeddings()  # [V, d]
        generated = []
        psi_snapshot = self.psi.detach().clone()

        for _ in range(max_new):
            # Use field state at the newest position only
            field_state = psi_snapshot[..., 0]  # [1, N, d]
            latest = field_state[:, -1]         # [1, d]

            # Cosine similarity to all byte embeddings
            sim = F.normalize(latest, dim=-1) @ F.normalize(all_embs, dim=-1).T  # [1, V]
            probs = F.softmax(sim[0] / max(temp, 1e-6), dim=-1)

            # Fallback for numeric stability
            if not torch.isfinite(probs).all() or probs.sum() == 0:
                probs = torch.ones(self.V, device=self.psi.device) / self.V

            byte = torch.multinomial(probs, 1).item()
            generated.append(byte)

            # Advance field state with chosen byte (no gradient)
            chosen_t = torch.tensor([[byte]], device=self.psi.device, dtype=torch.long)
            chosen_source = self._embed(chosen_t)
            psi_snapshot = torch.roll(psi_snapshot, shifts=-1, dims=1)
            psi_snapshot[:, -1:] = chosen_source
            psi_snapshot = self.pde.forward(psi_snapshot, T=self.dt, dt=self.dt)

        # Restore real field to snapshot
        self.psi = psi_snapshot
        return generated

    # ── Forward (compatibility for shape exploration) ──

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Process a batch of bytes for shape testing only."""
        source = self._embed(x)
        # Inject at end, slide
        for b in range(x.shape[1]):
            self.psi = torch.roll(self.psi, shifts=-1, dims=1)
            self.psi[:, -1:] = source[:, b:b+1]
            self.psi = self.pde.forward(self.psi, T=self.dt, dt=self.dt)
        return self._field_energy(self.psi).unsqueeze(0)
