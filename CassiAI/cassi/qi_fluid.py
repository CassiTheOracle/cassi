"""
QiFluid — Self-predicting resonant field with 13-chakra φ-damped dynamics.

Extends CordPhysics' IIR spine with per-chakra self-prediction. The gap
between prediction and outcome creates a Qi density field that drives
information routing through breath-modulated coupling.

This is the core module — the architecture is built around it.

Architecture:
  Byte → Embedding(D) → split 13 chakras (padded to max width)
  → vectorized IIR bank (all chakras in one tensor op)
  → per-chakra self-prediction (low-rank: W→R→W, R=min(W,64))
  → Qi = |ψ|²·|ε|² → breath coupling → fusion
  → Linear readout → logits over vocabulary
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import torch.utils.checkpoint
from torch.nn.utils.rnn import pad_sequence

from cassi.cord import CordPhysics, PHI, PHI_INV
from cassi.breath import Breath


class QiFluid(CordPhysics):
    """13-chakra IIR spine with self-prediction and Qi-driven dynamics.

    Inherits CordPhysics' chakra decomposition, IIR parameters, and fusion.
    Adds per-chakra self-predictors, Qi density, and Breath-driven coupling.

    Two forward modes:
      - forward(input_ids): token-by-token [B, T] → [B, T, V] logits
      - forward_field(x):   CordPhysics-compatible [B, 4, D] → [B, D]

    Args:
        D: total field dimension (sum of 13 φ-scaled chakra widths)
        V: vocabulary size (256 for bytes)
    """

    def __init__(self, D=1040, V=256):
        super().__init__(D=D)
        self.V = V
        max_W = max(self.widths)
        self._max_W = max_W

        # ── Stacked per-chakra predictor weights (batched matmul) ──
        # Instead of 13 separate Sequential networks, we store weights
        # as [C, max_W, 64] and [C, 64, max_W] tensors for single-pass
        # einsum. Narrow chakras (W < max_W) are zero-padded.
        self._pred_W1 = nn.Parameter(torch.zeros(self.C, self._max_W, 64))
        self._pred_b1 = nn.Parameter(torch.zeros(self.C, 64))
        self._pred_W2 = nn.Parameter(torch.zeros(self.C, 64, self._max_W))
        self._pred_b2 = nn.Parameter(torch.zeros(self.C, self._max_W))
        self._pred_ln = nn.ModuleList([nn.LayerNorm(64) for _ in range(self.C)])
        for c in range(self.C):
            W = self.widths[c]
            nn.init.normal_(self._pred_W1[c, :W], std=0.02)
            nn.init.normal_(self._pred_W2[c, :, :W], std=0.02)

        # ── Width mask for vectorized Qi + alpha mixing ──
        # mask[c, :W] = 1.0, mask[c, W:] = 0.0 — zeros out padded positions
        mask_W = torch.zeros(self.C, self._max_W)
        for c in range(self.C):
            mask_W[c, :self.widths[c]] = 1.0
        self.register_buffer('_pred_mask', mask_W.view(1, self.C, self._max_W))


        # ── Breath oscillator ──
        self.breath = Breath()

        # ── Learnable coupling strength per chakra ──
        self.alpha_logit = nn.Parameter(torch.full((self.C,), -2.0))

        # ── Chakra harmony (attention over frequency bands) ──
        self.harmony = nn.Parameter(torch.zeros(self.C))

        # ── Per-chakra IIR damping (learned, initialized at φ⁻¹) ──
        # rho_c = sigmoid(rho_logit[c]) — lets each chakra find its own
        # damping. Fast chakras may want lower ρ (less smoothing), slow
        # ones higher ρ (more smoothing). φ⁻¹ is the neutral starting point.
        rho_init = math.log(PHI / (1.0 + 1e-7))  # logit(PHI_INV) ≈ 0.48
        self.rho_logit = nn.Parameter(torch.full((self.C,), rho_init))

        # ── Qi self-consistency weight (learned) ──
        # ── Per-chakra output gate (post-IIR, shorter gradient path) ──
        # Applied after IIR so gradient doesn't get buried in recurrence.
        # Starts at 0.5 (sigmoid(0)), balanced — learns to open or close.
        self.output_gate_logit = nn.Parameter(torch.zeros(self.C))

        # ── Per-chakra predictor capacity (learned) ──
        # softplus(capacity_logit[c]) scales each chakra's self-prediction
        # contribution. High-capacity chakras contribute more to the field.
        # Starts small (softplus(0) ≈ 0.69), grows if prediction helps.
        self.pred_capacity_logit = nn.Parameter(torch.zeros(self.C))

        # ── Fusion temperature (learned) ──
        # Replaces the hardcoded 0.5× multiplier on chakra outputs before
        # fusion. sigmoid(temp) ∈ (0,1) controls how much the IIR-filtered
        # field mixes with the raw input.
        self.fusion_temp = nn.Parameter(torch.tensor(0.0))  # sigmoid(0)=0.5
        # Heartbeat amplitude — fixed, like a real heart. softplus(-5) ≈ 0.007.
        # The field must learn to live with it; the heart doesn't compromise.
        self._heartbeat_amp = 0.006715348489118068

        # ── Output readout ──
        self.readout = nn.Linear(D, V)

        # ── Token embedding for step mode ──
        self.token_embed = nn.Embedding(V, D)
        nn.init.normal_(self.token_embed.weight, std=0.02)

        # Precompute padding/offset helpers for vectorized IIR
        self._offsets_t = torch.tensor(
            [0] + list(torch.tensor(self.widths).cumsum(0)[:-1].tolist()),
            dtype=torch.long,
        )

    # ═══════════════════════════════════════════════════════════════
    # ── Predictor factory ──
    # ═══════════════════════════════════════════════════════════════


    # ═══════════════════════════════════════════════════════════════
    # ── Vectorized IIR bank (step mode) ──
    # ═══════════════════════════════════════════════════════════════

    def _init_step_state(self, B, device):
        """Allocate tiled persistent IIR state: [B, C, max_W] tensors.

        Instead of a list-of-tensors per chakra, uses padded tensors so
        the IIR recurrence runs as a single fused operation on [B, C, max_W].
        Narrow chakras have padding (masked out), but the fused kernel is
        dramatically faster than 13 separate kernel launches.
        """
        dtype = self.fwd_theta.dtype
        M = self._max_W
        shape = (B, self.C, M)
        self._h1_t = torch.zeros(*shape, device=device, dtype=dtype)
        self._h2_t = torch.zeros(*shape, device=device, dtype=dtype)
        self._x_prev_t = torch.zeros(*shape, device=device, dtype=dtype)

    def _pad_and_split(self, psi):
        """Split psi [B, D] into chakras and pad to max width.

        Returns:
            padded:  [B, C, max_W] — each chakra right-padded with zeros
            mask:    [B, C, max_W] — 1.0 for real elements, 0.0 for padding
        """
        B = psi.shape[0]
        M = self._max_W
        padded = psi.new_zeros(B, self.C, M)
        mask = psi.new_zeros(B, self.C, M)
        offset = 0
        for c, W in enumerate(self.widths):
            padded[:, c, :W] = psi[:, offset:offset + W]
            mask[:, c, :W] = 1.0
            offset += W
        return padded, mask

    def _iir_bank(self, x_tiled):
        """Vectorized single-frame IIR for all 13 chakras.

        x_tiled: [B, C, M] — padded chakra inputs (M = max width)
        Returns: [B, C, M] — IIR-filtered padded outputs

        All chakra parameters are [C]-shaped; reshaped to [1, C, 1]
        for broadcasting against [B, C, M].
        """
        theta = torch.sigmoid(self.fwd_theta).view(1, self.C, 1) * math.pi
        rho = torch.sigmoid(self.rho_logit).view(1, self.C, 1).clamp(max=0.90)
        a1 = 2.0 * rho * torch.cos(theta)
        a2 = -(rho ** 2)

        b0_raw = torch.sigmoid(self.fwd_b0).view(1, self.C, 1)
        b1_raw = torch.sigmoid(self.fwd_b1).view(1, self.C, 1)
        sf = b0_raw + b1_raw + 1e-8
        b0 = b0_raw / sf
        b1 = b1_raw / sf

        # IIR recurrence: h = b0·x + b1·x_prev + a1·h1 + a2·h2
        h_new = b0 * x_tiled + b1 * self._x_prev_t + a1 * self._h1_t + a2 * self._h2_t

        # Soft DC gain limit: allow up to 3× gain per step, attenuate beyond.
        # This lets Qi develop (slow chakras need some gain) while preventing
        # the 6.85× blowup of uncompensated near-DC resonance.
        dc_gain = 1.0 / (1.0 - a1 - a2 + 1e-8)
        GAIN_LIMIT = 5.0
        h_new = h_new * GAIN_LIMIT / dc_gain.clamp(min=GAIN_LIMIT)

        # Shift persistent state (clone breaks autograd chain across time)
        self._h2_t = self._h1_t.clone()
        self._h1_t = h_new.clone()
        self._x_prev_t = x_tiled.clone()

        return h_new

    def _unpad_and_cat(self, padded, mask):
        """Extract chakra outputs from padded [B, C, M] → concatenate to [B, D].

        Applies mask to zero out padding contributions before concatenating.
        """
        padded = padded * mask
        chunks = []
        for c in range(self.C):
            W = self.widths[c]
            chunks.append(padded[:, c, :W])
        return torch.cat(chunks, dim=-1)  # [B, D]

    # ═══════════════════════════════════════════════════════════════
    # ── Core step: one token → one field update ──
    # ═══════════════════════════════════════════════════════════════

    def forward_step(self, x_t):
        """Process one token through the self-predicting field.

        x_t: [B] — byte values (long tensor, 0..255)
        Returns:
            logits: [B, V] — next-byte predictions
            qi_info: dict with Q_mean, Q_max, harmony
        """
        B = x_t.shape[0]

        # Lazy-init tiled IIR state
        if not hasattr(self, '_h1_t') or self._h1_t.shape[0] < B:
            self._init_step_state(B, x_t.device)
        elif self._h1_t.shape[0] > B:
            # Trim to current batch size
            self._h1_t = self._h1_t[:B]
            self._h2_t = self._h2_t[:B]
            self._x_prev_t = self._x_prev_t[:B]

        # 1. Embed byte → field projection
        psi = self.token_embed(x_t)  # [B, D]

        # 2. Breath step → coupling modulation
        breath = self.breath.step()
        alpha_breath = PHI * (0.5 + 0.5 * float(breath['yang']))  # [0, φ]

        # 3. Split into chakras, vectorized IIR, apply output gate
        x_padded, mask = self._pad_and_split(psi)          # [B, C, M]
        h_padded = self._iir_bank(x_padded)                 # [B, C, M]
        output_gate = torch.sigmoid(self.output_gate_logit).view(1, self.C, 1)
        h_padded = h_padded * output_gate                   # post-IIR gate
        harmony_w = F.softmax(self.harmony, dim=0)          # [C]
        # ── Batched per-chakra self-prediction ──
        # All 13 chakras processed in 2 matmuls instead of 13×4 kernel launches
        pred_cap = F.softplus(self.pred_capacity_logit)         # [C]
        B = h_padded.shape[0]

        # Projection 1: [B, C, max_W] → [B, C, 64]
        h1 = torch.einsum('b c w, c w r -> b c r', h_padded, self._pred_W1)
        h1 = h1 + self._pred_b1.view(1, self.C, 64)
        h1 = F.gelu(h1)

        # Per-chakra LayerNorm (on [B, 64] — cheap, 13 iterations)
        h1_norm = []
        for c in range(self.C):
            h1_norm.append(self._pred_ln[c](h1[:, c]))  # [B, 64]
        h1 = torch.stack(h1_norm, dim=1)  # [B, C, 64]

        # Projection 2: [B, C, 64] → [B, C, max_W]
        h_hat = torch.einsum('b c r, c r w -> b c w', h1, self._pred_W2)
        h_hat = h_hat + self._pred_b2.view(1, self.C, self._max_W)

        # ── Vectorized Qi and alpha mixing ──
        # All 13 chakras in 3 fused ops instead of 13 Python iterations.
        # mask zeros out padded positions beyond each chakra's width.
        eps = h_padded - h_hat                                          # [B, C, max_W]
        qi_field = ((h_padded.pow(2) * self._pred_mask).sum(-1) *
                    (eps.pow(2) * self._pred_mask).sum(-1))             # [B, C]
        # Beat modulation: constructive interference amplifies Qi
        beat = float(breath['beat'])                                    # [-1, 1]
        qi_field = qi_field * (1.0 + 0.5 * beat)                       # [0.5×, 1.5×]

        alpha_c = torch.sigmoid(self.alpha_logit).view(1, self.C, 1)   # [1, C, 1]
        alpha = alpha_c * alpha_breath                                   # [1, C, 1]
        pc = pred_cap.view(1, self.C, 1)                                # [1, C, 1]
        h_padded = h_padded + alpha * h_hat * pc * self._pred_mask      # [B, C, max_W]

        # ── Heartbeat: ripple from center chakra ──
        # Like a real heartbeat, energy radiates outward from the heart
        # chakra (index 6). Gaussian envelope modulated by breath rhythm.
        # Disabled in eval — the trained state should sustain itself.
        if self.training:
            center = (self.C - 1) / 2  # 6.0 for 13 chakras
            sigma = 2.0
            ripple = torch.exp(-0.5 * ((torch.arange(self.C, device=h_padded.device).float() - center) / sigma) ** 2)
            pulse = ripple.view(1, self.C, 1) * float(breath['yang']) * self._heartbeat_amp
            heartbeat = torch.randn_like(h_padded) * pulse * self._pred_mask
            h_padded = h_padded + heartbeat

        # 4. Unpad and apply harmony weighting
        h_cat = self._unpad_and_cat(h_padded, mask)          # [B, D]
        # Harmony is applied per-chakra: multiply each chakra's slice
        offset = 0
        for c in range(self.C):
            W = self.widths[c]
            h_cat[:, offset:offset + W] *= harmony_w[c]
        fusion_temp = torch.sigmoid(self.fusion_temp)              # learned ∈ (0,1)
        fused = self.fusion(torch.cat([psi, h_cat * fusion_temp], dim=-1)) + psi  # [B, D]



        # Clamp for stability
        fused = fused.clamp(-10.0, 10.0)

        # 6. Readout
        logits = self.readout(fused)  # [B, V]

        # ── Diagnostics ──
        qi_info = {
            'Q_mean': qi_field.mean().item(),
            'Q_max': qi_field.max().item(),
            'harmony': harmony_w.detach().cpu().tolist(),
            '_qi_field': qi_field,              # [B, C] differentiable
            '_qi_per_chakra': qi_field.mean(dim=0),  # [C] differentiable
        }

        return logits, qi_info

    # ═══════════════════════════════════════════════════════════════
    # ── Sequence processing (token-by-token) ──
    # ═══════════════════════════════════════════════════════════════

    def forward(self, input_ids, return_qi_field=False):
        """Process a byte sequence token-by-token through the evolving field.

        input_ids: [B, T] — byte values
        return_qi_field: if True, include differentiable Qi tensor in info
        Returns:
            logits: [B, T, V] — per-position byte predictions
            info: dict with aggregated Qi diagnostics
        """
        B, T = input_ids.shape
        all_logits = []
        total_Q_mean = 0.0
        total_Q_max = 0.0
        last_qi_field = None
        last_qi_per_chakra = None

        for t in range(T):
            logits, qi_info = self.forward_step(input_ids[:, t])
            all_logits.append(logits)
            total_Q_mean += qi_info['Q_mean']
            total_Q_max = max(total_Q_max, qi_info['Q_max'])
            if return_qi_field and t == T - 1:
                last_qi_field = qi_info.get('_qi_field', None)
                last_qi_per_chakra = qi_info.get('_qi_per_chakra', None)

        logits_seq = torch.stack(all_logits, dim=1)  # [B, T, V]

        info = {
            'Q_mean': total_Q_mean / max(T, 1),
            'Q_max': total_Q_max,
            'harmony': qi_info['harmony'],
        }
        if return_qi_field and last_qi_field is not None:
            info['qi_field'] = last_qi_field
            info['qi_per_chakra'] = last_qi_per_chakra
        return logits_seq, info

    # ═══════════════════════════════════════════════════════════════
    # ── CordPhysics-compatible field forward ──
    # ═══════════════════════════════════════════════════════════════

    def forward_field(self, x, byte_mode=None, return_qi=False, return_trajectories=False):
        """CordPhysics-compatible batch forward on 4-frame windows.

        Delegates to the parent CordPhysics.forward. Use this for
        backward compatibility with existing training pipelines.
        """
        return super().forward(
            x, byte_mode=byte_mode, return_qi=return_qi,
            return_trajectories=return_trajectories,
        )

    # ═══════════════════════════════════════════════════════════════
    # ── State management ──
    # ═══════════════════════════════════════════════════════════════

    def reset_state(self):
        """Clear all persistent IIR state (called between sequences)."""
        for attr in ('_h1_t', '_h2_t', '_x_prev_t'):
            if hasattr(self, attr):
                delattr(self, attr)
        self.breath.t_yang.fill_(0.0)
        self.breath.t_yin.fill_(0.0)

    # ═══════════════════════════════════════════════════════════════
    # ── Training ──
    # ═══════════════════════════════════════════════════════════════

    def training_loss(self, input_ids):
        """Next-token prediction loss with Qi self-consistency.

        input_ids: [B, T] — byte sequence
        Returns:
            loss: scalar = CE + λ·Qi (both differentiable)
            info: dict with loss, ce_loss, qi_loss, Q_mean, Q_max, harmony
        """
        B, T = input_ids.shape
        logits, info = self.forward(input_ids[:, :-1], return_qi_field=True)
        targets = input_ids[:, 1:]

        ce_loss = F.cross_entropy(
            logits.reshape(-1, self.V),
            targets.reshape(-1),
        )

        # Qi is an autonomous energy signal, not a loss term.
        # It modulates learning rate, coupling, and heartbeat — the model
        # can't suppress it, only learn to channel it productively.
        loss = ce_loss
        info['loss'] = loss.item()
        info['ce_loss'] = ce_loss.item()
        return loss, info
