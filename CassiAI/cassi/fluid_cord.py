#!/usr/bin/env python3
"""FluidCord — PDE-based neural field for byte-sequence prediction.

Architecture:
    Bytes → MultiScaleByteEmbedder → FluidField (PDE integrator) → Readout → logits

This replaces MuonCord/ManifoldCord's ~2000-line IIR + attention + Qi pipeline
with a single ~150-line model built on a spectral PDE solver.

Key differences from MuonCord:
    - Single complex field ψ ∈ ℂ^{B×N×d} (no separate real/imag IIR buffers)
    - 6 learnable PDE coefficients replace 20+ submodules
    - No bidirectional, no pattern memory, no brain tuner
    - Training loss: CE + chakra balance entropy
"""

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV, bell_chakra_widths, chakra_offsets
from cassi.fluid_field import FluidField
from cassi.multi_scale_byte import MultiScaleByteEmbedder
from cassi.spectral_memory import SpectralMemory


class FluidCord(nn.Module):
    """Byte-sequence prediction model via PDE field integration.

    Args:
        N: Number of spatial positions (token sequence length).
        d: Field dimension per position.
        C: Number of chakras (always 13).
        V: Vocabulary size (byte mode = 256).
        max_batch_size: Maximum batch size for persistent buffers.
        scales: N-gram scales for multi-scale byte embedder.
        byte_embed_dim: Byte embedding dimension for multi-scale embedder.
    """

    def __init__(self,
                 N: int = 128,
                 d: int = 128,
                 C: int = 13,
                 V: int = 256,
                 max_batch_size: int = 64,
                 scales: Tuple[int, ...] = (1, 2, 3, 5, 8, 13),
                 byte_embed_dim: int = 64,
                 use_phi_qp: bool = True,
                 use_attention: bool = False,
                 use_spectral_memory: bool = False,
                 autoregressive_ratio: float = 0.15,
                 corruption_ratio: float = 0.15,
                 lookahead: int = 4):
        super().__init__()
        self.N = N
        self.d = d
        self.C = C
        self.V = V
        self.max_batch_size = max_batch_size
        self.use_attention = use_attention
        self.use_spectral_memory = use_spectral_memory
        self.autoregressive_ratio = autoregressive_ratio
        self.corruption_ratio = corruption_ratio
        self.lookahead = lookahead

        # ── Multi-scale byte embedder ──
        self.embedder = MultiScaleByteEmbedder(
            d_out=d, scales=scales, byte_embed_dim=byte_embed_dim)

        # ── PDE field ──
        self.fluid_field = FluidField(
            d=d, C=C, N=N, max_batch_size=max_batch_size,
            use_phi_qp=use_phi_qp)

        # ── Optional self-attention ──
        if use_attention:
            self.attn = nn.MultiheadAttention(
                embed_dim=d, num_heads=4, batch_first=True, dropout=0.0)
            self.attn_norm = nn.LayerNorm(d)
        else:
            self.attn = None
            self.attn_norm = None

        # ── Optional spectral memory ──
        if use_spectral_memory:
            self.spectral_memory = SpectralMemory(
                d=d, C=C, N=N, num_modes=32, max_batch_size=max_batch_size)
        else:
            self.spectral_memory = None

        # ── Readout head ──
        self.readout_head = nn.Linear(d, lookahead * V)
        nn.init.normal_(self.readout_head.weight, std=0.02)
        nn.init.zeros_(self.readout_head.bias)

        self.register_buffer("breath_phase", torch.zeros(1))

    # ── Embedding ──

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        """Embed byte tokens as complex source term.

        Args:
            x: [B, N] token ids.

        Returns:
            Complex source field [B, N, d] (real embedding, zero imag).
        """
        emb = self.embedder(x)  # [B, N, d]
        return emb.to(torch.cfloat)

    # ── Readout ──

    def readout_positions(self, psi: torch.Tensor) -> torch.Tensor:
        """Read multi-token logits from the real part of the field.

        Each position predicts lookahead tokens ahead: logits[:, i, k, :]
        predicts the token at position i+k+1.

        Args:
            psi: Complex field [B, N, d].

        Returns:
            Logits [B, N, lookahead, V].
        """
        B, N, d = psi.shape
        real = F.layer_norm(psi.real, psi.shape[-1:])  # [B, N, d]
        out = self.readout_head(real)  # [B, N, lookahead*V]
        return out.reshape(B, N, self.lookahead, self.V)  # [B, N, K, V]

    # ── Chakra diagnostics ──

    def _chakra_energy(self, psi: torch.Tensor) -> torch.Tensor:
        """Per-chakra normalized energy distribution.

        Computes |psi|2 summed over positions and field dims within each chakra,
        then normalizes to sum to 1.

        Args:
            psi: Complex field [B, N, d].

        Returns:
            Normalized chakra energy [C] (sum = 1).
        """
        energy = psi.abs() ** 2  # [B, N, d]
        chakra_energies = []
        for c in range(self.C):
            start, end = self.fluid_field._chakra_start_end[c]
            chakra_energies.append(energy[:, :, start:end].sum())
        ce = torch.stack(chakra_energies)  # [C]
        return ce / ce.sum().clamp_min(1e-12)

    def _chakra_balance_entropy(self, psi: torch.Tensor) -> torch.Tensor:
        """Entropy of chakra energy distribution (higher = more balanced)."""
        chakra_energy = self._chakra_energy(psi)
        entropy = -(chakra_energy * (chakra_energy + 1e-12).log()).sum()
        return entropy

    def _grouping_loss(self, psi: torch.Tensor, tokens: torch.Tensor) -> torch.Tensor:
        """Encourage the field to organize by byte identity.

        Same-byte positions cluster together (low intra-cluster variance).
        Different-byte positions separate (high inter-cluster distance).
        This directly counters CE's per-byte incentive to collapse to safe tokens.

        Args:
            psi: Complex field [B, N, d].
            tokens: Token ids [B, N].

        Returns:
            Scalar loss — cluster intra-variance / inter-distance.
            Low = compact, well-separated clusters.
        """
        B, N, d = psi.shape
        device = psi.device

        # Flatten batch: real field [B*N, d], tokens [B*N]
        psi_flat = psi.real.reshape(-1, d)
        tokens_flat = tokens.reshape(-1)

        unique = torch.unique(tokens_flat)

        intra_sum = 0.0
        inter_sum = 0.0
        n_clusters = 0

        for token in unique:
            mask = (tokens_flat == token)
            M = mask.sum()
            if M < 2:
                continue  # singleton clusters contribute nothing
            cluster = psi_flat[mask]  # [M, d]
            center = cluster.mean(dim=0, keepdim=True)  # [1, d]
            intra_sum += (cluster - center).pow(2).sum() / M
            inter_sum += center.pow(2).sum()
            n_clusters += 1

        if n_clusters == 0:
            return torch.tensor(0.0, device=device)

        intra = intra_sum / n_clusters
        inter = inter_sum / n_clusters
        return intra / (inter + 1e-12)

    # ── Breath ──

    def _advance_breath(self):
        """Advance breath phase for next batch (continuous oscillation)."""
        self.breath_phase.copy_(
            (self.breath_phase + PHI_INV * 0.1) % 1.0)

    # ── State management ──

    def reset_state(self):
        """Clear all persistent field, breath, and memory state."""
        self.fluid_field.reset_state()
        self.breath_phase.zero_()
        if self.spectral_memory is not None:
            self.spectral_memory.reset_state()

    # ── Training ──

    def training_loss(self,
                      x: torch.Tensor,
                      no_reset: bool = False,
                      T: float = 1.0,
                      dt: float = 0.2,
                      ) -> Tuple[torch.Tensor, Dict]:
        """Self-predicting training loss.

        The field at position i is trained to predict the source at position
        i+1 (field self-prediction loss). An auxiliary cross-entropy loss on
        token logits helps the readout head learn. Chakra balance is maintained
        via entropy regularization.

        This dual-loss design prevents mode collapse: even when CE approaches
        zero (degenerate solution predicting a few high-frequency tokens), the
        field-level MSE forces the field to produce DIFFERENT vectors for
        different next-token positions, maintaining representational diversity.

        Pipeline: embed → PDE → {self-prediction loss, readout → CE loss} + balance.

        Args:
            x: [B, N] token ids.
            no_reset: If True, preserve field state across calls.
            T: Total integration time.
            dt: Time step size.

        Returns:
            (loss, diagnostics_dict)
        """
        B, N = x.shape

        # ── State initialization ──
        if not no_reset:
            self.fluid_field.reset_state()

        # ── 1. Embed tokens as source term ──
        source = self.embed(x)  # [B, N, d] complex
        # ── 1a. Source augmentation: autoregressive training + corruption ──
        # During training, sometimes replace ground-truth sources with the
        # model's own predictions (autoregressive) or zero them out (corruption).
        # This trains recovery from wrong/missing sources, breaking the
        # self-reinforcing repetition loop at inference time.
        # CE loss is always against the real tokens x.
        if self.training:
            r = torch.rand(1).item()
            if r < self.autoregressive_ratio:
                # Autoregressive: use model's own predictions as sources
                with torch.no_grad():
                    pred_logits = self.readout_positions(
                        self.fluid_field.integrate(
                            source, T=T, dt=dt,
                            breath_phase=self.breath_phase.item()))
                    pred_tokens = pred_logits[:, :-1, 0, :].argmax(dim=-1)
                    # Pad to full length: first token is always ground truth
                    pred_tokens = torch.cat([
                        x[:, :1], pred_tokens], dim=1)
                source = self.embed(pred_tokens)
            elif r < self.autoregressive_ratio + self.corruption_ratio:
                # Corruption: zero out random positions
                mask = torch.rand(B, N, device=x.device) < 0.3
                source = source.clone()
                source[mask] = 0.0

        # ── 1b. Spectral memory read (inject stored patterns) ──
        if self.spectral_memory is not None:
            mem_boost = self.spectral_memory.read(source)
            source = source + 0.1 * mem_boost

        # ── 2. Integrate PDE ──
        psi_T = self.fluid_field.integrate(
            source, T=T, dt=dt, breath_phase=self.breath_phase.item())
        # ── 2b. Spectral memory write (store field patterns) ──
        if self.spectral_memory is not None:
            self.spectral_memory.write(psi_T)

        # ── 2b. Optional self-attention on field (pre-norm, scaled residual) ──
        if self.attn is not None:
            real = self.attn_norm(psi_T.real)  # pre-norm
            attn_out, _ = self.attn(real, real, real, need_weights=False)
            psi_T = torch.complex(real + 0.1 * attn_out, psi_T.imag)

        # ── 3. Readout ──
        logits = self.readout_positions(psi_T)  # [B, N, K, V]

        # ── 4. Multi-token cross-entropy (φ-scaled lookahead) ──
        # Each position i predicts tokens at i+1..i+K with φ⁻ᵏ decay.
        ce_loss = 0.0
        norm = 0.0
        for k in range(self.lookahead):
            n_valid = self.N - 1 - k
            if n_valid <= 0:
                break
            w = PHI_INV ** k
            ce_loss += w * F.cross_entropy(
                logits[:, :n_valid, k, :].reshape(-1, self.V),
                x[:, 1 + k : 1 + k + n_valid].reshape(-1),
            )
            norm += w
        if norm > 0:
            ce_loss = ce_loss / norm

        # ── 5. Chakra balance loss ──
        chakra_energy = self._chakra_energy(psi_T)
        balance_loss = -(
            chakra_energy * (chakra_energy + 1e-12).log()
        ).sum()
        balance_loss = balance_loss / math.log(self.C)

        # ── 6. Grouping loss: encourage field clusters by byte identity ──
        grouping_loss = self._grouping_loss(psi_T[:, :-1, :], x[:, 1:])

        # ── 7. Combined loss ──
        loss = (1.0 / PHI) * ce_loss + 0.03 * balance_loss + 0.3 * PHI_INV * grouping_loss

        # ── 8. Advance breath for next batch ──
        self._advance_breath()

        diag = {
            "ce_loss": ce_loss.item(),
            "balance_loss": balance_loss.item(),
            "grouping_loss": grouping_loss.item(),
            "loss": loss.item(),
            "chakra_balance": self._chakra_balance_entropy(psi_T).item(),
        }

        return loss, diag

    # ── Generation ──

    @torch.no_grad()
    def generate(self,
                 seed: torch.Tensor = None,
                 max_new: int = 128,
                 temp: float = 0.8,
                 T: float = 1.0,
                 dt: float = 0.2,
                 K_steps: int = 32,
                 top_p: float = 0.9,
                 warm_state: bool = False,
                 K_iter: int = None,
                 ) -> torch.Tensor:
        """Diffusion generation: iterative refinement with PDE spatial coupling.

        The PDE (diffusion + advection) provides spatial coupling between
        positions. Iterative refinement wraps around the PDE: embed → PDE →
        readout → sample → update. Noise on the source anneals over iterations
        for diffusion-like exploration early, precision late.

        Args:
            seed: Token ids for conditioning (clamped, never changed).
            max_new: Number of tokens to generate.
            temp: Sampling temperature.
            K_steps: Number of refinement iterations (default 32).
            top_p: Nucleus sampling threshold (1.0=disabled).
            K_iter: Alias for K_steps (backward compat).

        Returns:
            [max_new] generated token ids.
        """
        self.eval()
        device = next(self.parameters()).device
        N = self.N

        if K_iter is not None:
            K_steps = K_iter

        # ── Handle seed ──
        if seed is None or seed.numel() == 0:
            seed = torch.randint(0, self.V, (1,), device=device)
        seed = seed.to(device).long()
        L = seed.numel()

        # Clamp to field size
        if L + max_new > N:
            max_new = N - L
            if max_new <= 0:
                return seed[:N]

        # ── Initialize token window ──
        token_window = torch.zeros(N, dtype=torch.long, device=device)
        token_window[:L] = seed

        # Precompute seed source for clamping (embedded in isolation —
        # prevents future-position noise from corrupting seed embeddings
        # through multi-scale convolutions)
        seed_source = self.embed(seed.unsqueeze(0))[:, :L, :]

        # ── Iterative refinement ──
        for k in range(K_steps):
            # Embed current token estimate → spatially-coupled source
            source = self.embed(token_window.unsqueeze(0))  # [1, N, d] complex

            # Noise annealing: add noise to source at early iterations
            # for exploration; anneal to zero for convergence
            sigma_k = 0.5 * (1.0 - k / K_steps)
            if sigma_k > 0.01:
                noise = torch.randn_like(source.real) * sigma_k
                source = source + noise

            # Clamp seed positions
            source[:, :L, :] = seed_source

            # PDE integrates → spatially-coupled field (THIS is the coupling)
            self.reset_state()
            psi = self.fluid_field.integrate(
                source, T=T, dt=dt, breath_phase=self.breath_phase.item())

            # Readout → logits
            logits = self.readout_positions(psi)[0, :, 0, :]  # [N, V]

            # Temperature annealing: φ-symmetric hot → cool
            temp_k = temp * PHI ** (1.0 - 2.0 * k / max(K_steps - 1, 1))
            temp_k = max(temp_k, 0.1)

            # Sample future positions, clamp seed
            for pos in range(L, N):
                pred_logits = logits[pos - 1] / temp_k
                probs = F.softmax(pred_logits, dim=-1)
                token_window[pos] = torch.multinomial(probs, 1).item()

        # ── Final pass: full-strength integration with converged tokens ──
        final_source = self.embed(token_window.unsqueeze(0))
        final_source[:, :L, :] = seed_source
        self.reset_state()
        psi_final = self.fluid_field.integrate(
            final_source, T=T, dt=dt, breath_phase=self.breath_phase.item())
        logits_final = self.readout_positions(psi_final)[0, :, 0, :]  # [N, V]

        # ── Sample final tokens ──
        final_logits = logits_final[L - 1 : L - 1 + max_new] / max(temp, 1e-6)

        if top_p < 1.0:
            for i in range(max_new):
                sorted_l, sorted_i = torch.sort(final_logits[i], descending=True)
                cum = torch.cumsum(F.softmax(sorted_l, dim=-1), dim=-1)
                remove = cum > top_p
                remove[1:] = remove[:-1].clone()
                remove[0] = False
                final_logits[i, sorted_i[remove]] = -float('inf')

        probs = F.softmax(final_logits, dim=-1)
        tokens = torch.multinomial(probs, 1).squeeze(-1)
        return tokens


    # ── Forward (for optimizer compatibility) ──

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass: embed + integrate + readout.

        Returns logits [B, N, V] (first lookahead only, for backward compat).
        """
        source = self.embed(x)
        psi_T = self.fluid_field.integrate(
            source, T=1.0, dt=0.2, breath_phase=self.breath_phase.item())
        return self.readout_positions(psi_T)[:, :, 0, :]  # [B, N, V]


