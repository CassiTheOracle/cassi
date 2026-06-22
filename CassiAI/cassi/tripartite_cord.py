#!/usr/bin/env python3
"""
TripartiteCord — unified Cord/Brain/Mind coupled dynamical system.

Replaces the composed QiField → SelfAwarenessController → Breath → QiDynamics →
ControllerModulation pipeline with a single coupled complex field Ψ with direct
BrainStep coupling, emergent breath, and analytical constraint forces.

No imports from cassi.qi_field, cassi.self_awareness_controller, cassi.breath,
or cassi._field_modules.controller_mod — no circular dependencies.
No classical MLP anywhere.

Architecture:
    Ψ = [ψ_real, ψ_imag]  ∈ ℂ^(B×N×d)     — complex field (sole persistent state)
    IIR: h1/h2/h1_im/h2_im                 — position-form recurrence history
    Brain: brain_h [max_bs, n_shells, D]   — per-shell damped wave accumulators
    Scalars: Q_ema, Q_trend, Q_bar_pos     — Qi EMA scalars (not field buffers)

Each forward step:
    Breath → IIR → PatternMemory → Prediction → Qi (curvature) →
    Brain → ConstraintForces → Feedback → Yin↔Yang Couple →
    Glial Homeostasis → Breath Rotation → Complex RMSNorm
"""

import math
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV, phi_chakra_widths, chakra_offsets
from cassi._chakra_iir import ChakraIIRBank
from cassi._field_modules import PredictionOperator
from cassi.pattern_memory import QiPatternMemory
from cassi.multi_scale_byte import MultiScaleByteEmbedder
from cassi.brain_step import BrainStep


class TripartiteCord(nn.Module):
    """Unified Cord→Brain→Mind coupled dynamical system.

    One nn.Module where Cord, Brain, and Mind are projections of a single
    unified state Ψ, not separately-designed modules. All dynamics derive
    from one variational principle rather than sequential sub-steps.

    Args:
        N: Number of spatial positions (token sequence length).
        d: Field dimension per position.
        C: Number of chakras (always 13).
        V: Vocabulary size (byte mode) or output dimension.
        K_train: Number of field steps during training.
        K_gen: Number of field steps during generation.
        brain_shells: Number of spherical shells in BrainStep.
        brain_D: Total brain hidden dimension across all shells.
        brain_scale: Coupling strength for brain perturbation.
        stiffness_Q: Constraint stiffness for Qi (prediction trust).
        stiffness_E: Constraint stiffness for energy homeostasis.
        stiffness_B: Constraint stiffness for yin↔yang balance.
        noise_scale: Scale of low-Q arousal perturbation.
        use_checkpoint: If True, use gradient checkpointing for _unified_step.
        max_neurons: Maximum number of pattern-memory neurons.
        span_len: Number of tokens to predict (training loss target span).
        lambda_pattern_div: Weight for pattern diversity loss.
        lambda_pattern_commit: Weight for pattern commitment loss.
        lambda_pattern_util: Weight for pattern utilization loss.
        input_dim: Input feature dimension (continuous mode).
        output_dim: Output feature dimension (continuous mode).
        continuous_mode: If True, use regression (MSE) instead of CE.
        multi_scale_bytes: If True, use multi-scale byte embedding.
        multi_scale_scales: N-gram scales for multi-scale embedder.
        multi_scale_byte_embed_dim: Byte embedding dimension for multi-scale.
        state_bank_size: Number of keyed IIR state slots (0 = disabled).
        max_batch_size: Maximum batch size for persistent buffers.
    """
    def __init__(self,
                 N: int = 128,
                 d: int = 128,
                 C: int = 13,
                 V: int = 256,
                 K_train: int = 5,
                 K_gen: int = 50,
                 brain_shells: int = 7,
                 brain_D: int = 588,
                 brain_scale: float = 0.1,
                 stiffness_Q: float = 1.0,
                 stiffness_E: float = 1.0,
                 stiffness_B: float = 0.1,
                 noise_scale: float = 0.01,
                 use_checkpoint: bool = False,
                 max_neurons: int = 512,
                 span_len: int = 16,
                 lambda_pattern_div: float = 0.001,
                 lambda_pattern_commit: float = 0.001,
                 lambda_pattern_util: float = 0.01,
                 input_dim: int = 256,
                 output_dim: int = 256,
                 continuous_mode: bool = False,
                 multi_scale_bytes: bool = False,
                 multi_scale_scales: Tuple[int, ...] = (1, 2, 3, 5, 8, 13),
                 multi_scale_byte_embed_dim: int = 64,
                 state_bank_size: int = 0,
                 max_batch_size: int = 256):
        super().__init__()

        # ── Scalar config ──
        self.N = N
        self.d = d
        self.C = C
        self.V = V
        self.K_train = K_train
        self.K_gen = K_gen
        self.max_batch_size = max_batch_size
        self.use_checkpoint = use_checkpoint
        self.span_len = span_len
        self.lambda_pattern_div = lambda_pattern_div
        self.lambda_pattern_commit = lambda_pattern_commit
        self.lambda_pattern_util = lambda_pattern_util
        self.input_dim = input_dim
        self.output_dim = output_dim
        self.continuous_mode = continuous_mode
        self.multi_scale_bytes = multi_scale_bytes
        self.multi_scale_scales = multi_scale_scales
        self.multi_scale_byte_embed_dim = multi_scale_byte_embed_dim
        self.state_bank_size = state_bank_size

        # φ-scaled chakra widths
        widths = phi_chakra_widths(d, C)
        self.chakra_widths = widths

        # ── Constraint force parameters (scalars) ──
        self.stiffness_Q = nn.Parameter(torch.tensor(stiffness_Q))
        self.stiffness_E = nn.Parameter(torch.tensor(stiffness_E))
        self.stiffness_B = nn.Parameter(torch.tensor(stiffness_B))
        self.noise_scale = nn.Parameter(torch.tensor(noise_scale))
        self.brain_scale = nn.Parameter(torch.tensor(brain_scale))
        self.field_scale = nn.Parameter(torch.tensor(1.0))

        # ── Token embedding / input projection ──
        if self.continuous_mode:
            self.input_proj = nn.Linear(input_dim, d)
            self.token_embed = None
            self.imag_proj = None
        else:
            self.input_proj = None
            self.token_embed = nn.Embedding(V, d)
            nn.init.normal_(self.token_embed.weight, std=0.02)
            self.imag_proj = nn.Linear(d, d, bias=False)

        # ── Position encoding (same math as QiField) ──
        t = torch.arange(N, dtype=torch.float32).view(-1, 1)
        i = torch.arange(d, dtype=torch.float32).view(1, -1)
        base = 2.0 * math.pi / N
        k = torch.round(PHI ** (i * 2.0 / d) * N / (2.0 * math.pi))
        k = torch.clamp(k, min=1)
        k = k.squeeze(0)
        for j in range(1, d):
            if k[j] <= k[j - 1]:
                k[j] = k[j - 1] + 1
        freqs = k.view(1, -1) * base
        if d > 1:
            assert freqs.min() > 0, "position encoding frequencies must be positive"
            assert freqs.unique().numel() == d, "position encoding frequencies must be distinct"
        phases = t * freqs
        is_even = (i.long() % 2 == 0)
        pos_real = torch.where(is_even, torch.sin(phases), torch.cos(phases))
        pos_imag = torch.where(is_even, torch.cos(phases), -torch.sin(phases))
        self.register_buffer('pos_enc_real', pos_real.unsqueeze(0))
        self.register_buffer('pos_enc_imag', pos_imag.unsqueeze(0))

        # ── Chakra offsets (for diagnostics) ──
        offsets_list = chakra_offsets(self.chakra_widths)
        self.register_buffer('chakra_offsets', offsets_list)

        # ── IIR bank (owns per-chakra theta, chakra_id mapping) ──
        self.iir_bank = ChakraIIRBank(d=d, C=C, widths=self.chakra_widths)

        # ── Prediction operator (owns transceivers, cross_chakra) ──
        self.prediction = PredictionOperator(
            d=d, C=C, widths=self.chakra_widths, N=N,
        )
        self.transceivers = self.prediction.transceivers
        self.cross_chakra = self.prediction.cross_chakra

        # ── Pattern memory ──
        self.max_neurons = max_neurons
        self.pattern_memory = QiPatternMemory(d=d, max_neurons=max_neurons)

        # ── Brain step (per-step 3D spherical processor) ──
        self.brain = BrainStep(d=d, n_shells=brain_shells, D=brain_D,
                               max_batch_size=max_batch_size)

        # ── Optional multi-scale byte embedder ──
        if self.multi_scale_bytes:
            self.multi_scale_embedder = MultiScaleByteEmbedder(
                d_out=d,
                scales=multi_scale_scales,
                byte_embed_dim=multi_scale_byte_embed_dim,
            )
        else:
            self.multi_scale_embedder = None

        # ── Readout ──
        if self.continuous_mode:
            self.output_proj = nn.Linear(d, output_dim)
            self.readout_y = None
            self.readout_z = None
        else:
            self.output_proj = None
            self.readout_y = nn.Linear(d, V)
            self.readout_z = nn.Linear(d, V)
            nn.init.normal_(self.readout_y.weight, std=0.02)
            nn.init.normal_(self.readout_z.weight, std=0.02)
            nn.init.zeros_(self.readout_y.bias)
            nn.init.zeros_(self.readout_z.bias)

        # ── Persistent IIR state buffers [max_batch_size, N, d] ──
        # Position-form recurrence history. h1 = psi[t-1], h2 = psi[t-2] for
        # the real part; h1_im/h2_im for the imaginary part (independent IIR).
        self.register_buffer('h1', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h2', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h1_im', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h2_im', torch.zeros(max_batch_size, N, d))

        # Optional keyed per-sample IIR state bank.
        if state_bank_size > 0:
            self.register_buffer('h1_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h2_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h1_im_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h2_im_bank', torch.zeros(state_bank_size, N, d))

        # ── Persistent scalar buffers ──
        self.register_buffer('Q_ema', torch.zeros(1))
        self.register_buffer('Q_trend', torch.zeros(1))
        self.register_buffer('pattern_step', torch.zeros(1, dtype=torch.long))
        self.register_buffer('Q_bar_pos', torch.zeros(1, N))

        # ── Breath phase accumulators (field-modulated oscillators) ──
        # Baseline frequencies: ω_yang = φ, ω_yin = φ⁻¹.
        # The field's aggregate phase modulates the rate, not the phase directly,
        # so the φ²:1 beat is structural and the field speeds/slows it.
        self.register_buffer('breath_t_yang', torch.zeros(1))
        self.register_buffer('breath_t_yin', torch.zeros(1))

        # Backward-compat: external code that iterates model.residuals gets nothing.
        self._residuals_placeholder = nn.ModuleList()

    # ════════════════════════════════════════════════
    #  Utilities
    # ════════════════════════════════════════════════

    @property
    def residuals(self):
        """Backward-compat property. Returns an empty ModuleList.
        The residual MLP has been removed (classical ML is not allowed).
        """
        return self._residuals_placeholder

    @staticmethod
    def _complex_norm2(a_real: torch.Tensor, a_imag: torch.Tensor) -> torch.Tensor:
        """Squared magnitude of a complex tensor."""
        return a_real ** 2 + a_imag ** 2

    def _complex_rmsnorm(self, psi_real: torch.Tensor,
                         psi_imag: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Per-chakra complex RMS normalization (same math as QiField)."""
        mag2 = self._complex_norm2(psi_real, psi_imag)
        scale = torch.zeros_like(mag2)
        off = 0
        for c in range(self.C):
            dc = self.chakra_widths[c]
            band = mag2[:, :, off:off + dc]
            mean_band = band.mean(dim=-1, keepdim=True).clamp_min(1e-12)
            scale[:, :, off:off + dc] = 1.0 / torch.sqrt(mean_band)
            off += dc
        scale = scale * self.field_scale
        return psi_real * scale, psi_imag * scale

    @staticmethod
    def _rotate_complex(real: torch.Tensor, imag: torch.Tensor,
                        angle: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Rotate a complex tensor by angle (in radians)."""
        c = torch.cos(angle)
        s = torch.sin(angle)
        return real * c - imag * s, real * s + imag * c

    # ════════════════════════════════════════════════
    #  Emergent Breath
    # ════════════════════════════════════════════════

    def _tripartite_breath(self, psi_real: torch.Tensor,
                           psi_imag: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Field-modulated dual-heart oscillator.

        Independent phase accumulators advance at baseline ω_yang=φ, ω_yin=φ⁻¹
        per tick.  The field's aggregate phase provides a small frequency
        modulation (±10%) so the field can speed or slow its own rhythm.
        The φ²:1 beat is structural — it exists even when Qi→0.

        Accumulation is detached to match the original Breath module semantics:
        the breath carrier wave has no learnable parameters and its phase
        does not carry gradient.

        Returns:
            dict with 'yang', 'yin', 'beat' (scalars) and 'phase' (scalar rad).
        """
        # Field phase modulates frequency (not phase directly)
        field_phase = torch.angle(torch.complex(psi_real.mean(), psi_imag.mean()))
        omega_mod = 1.0 + 0.1 * torch.tanh(field_phase)  # ±10% modulation

        # Accumulate at φ and φ⁻¹ rates (detached — carrier is not learned)
        with torch.no_grad():
            self.breath_t_yang.copy_(
                (self.breath_t_yang + PHI * omega_mod.detach()) % (2 * math.pi))
            self.breath_t_yin.copy_(
                (self.breath_t_yin + PHI_INV * omega_mod.detach()) % (2 * math.pi))

        yang = torch.sin(self.breath_t_yang)
        yin = torch.sin(self.breath_t_yin)
        beat = torch.sin(self.breath_t_yang - self.breath_t_yin)
        return {'yang': yang, 'yin': yin, 'beat': beat, 'phase': field_phase}

    # ════════════════════════════════════════════════
    #  Constraint Forces (replaces SelfAwarenessController MLP)
    # ════════════════════════════════════════════════

    def _constraint_forces(self, Q_ema_val: torch.Tensor,
                           psi2_mean: torch.Tensor,
                           yang: torch.Tensor,
                           yin: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Compute analytical constraint forces from Qi and energy.

        Returns scalar dict with lambda_Q, lambda_E, lambda_B.
        """
        # Prediction trust: how much to believe the self-prediction
        lambda_Q = F.softplus((Q_ema_val - PHI_INV) / PHI_INV) * self.stiffness_Q

        # Energy homeostasis: how strongly to contract excess energy
        lambda_E = F.softplus((psi2_mean - PHI ** 2) / PHI ** 2) * self.stiffness_E

        # Balance: yin↔yang structural coupling strength (placeholder)
        lambda_B = self.stiffness_B

        return {'lambda_Q': lambda_Q, 'lambda_E': lambda_E, 'lambda_B': lambda_B}

    # ════════════════════════════════════════════════
    #  Calm / Arousal (phi-scaled self-regulation)
    # ════════════════════════════════════════════════

    @staticmethod
    def _calm_arousal(Q_mean: torch.Tensor,
                      yin: torch.Tensor) -> torch.Tensor:
        """Phi-scaled calm↔arousal regulation.

        Same math as QiField's structural_self_reg (deduplicated here).
        Returns a scalar self-regulation factor in [φ⁻², 3.0].
        """
        q_norm = Q_mean / PHI_INV
        excess = F.relu(q_norm - PHI_INV)
        calm = PHI_INV / (PHI_INV + excess)
        deficit = F.relu(PHI_INV - q_norm)
        arousal = (1.0 + 2.0 * deficit / PHI_INV).clamp(1.0, 3.0)
        self_reg = calm * arousal
        calm_breath = 1.0 + 0.15 * (yin - PHI_INV)
        self_reg = (self_reg * calm_breath).clamp(PHI_INV ** 2, 3.0)
        return self_reg

    # ════════════════════════════════════════════════
    #  Unified Step
    # ════════════════════════════════════════════════

    def _unified_step(
        self,
        psi_real: torch.Tensor,
        psi_imag: torch.Tensor,
        h1_in: torch.Tensor,
        h2_in: torch.Tensor,
        h1_im_in: torch.Tensor,
        h2_im_in: torch.Tensor,
        brain_h: torch.Tensor,
        Q_ema_val: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor,
               torch.Tensor, torch.Tensor, torch.Tensor,
               torch.Tensor, Dict[str, torch.Tensor]]:
        """One unified evolution step — IIR, PatternMemory, Prediction, Brain,
        Constraint forces, Yin↔Yang coupling, Glial, Rotate, RMSNorm.

        Does NOT mutate persistent buffers — returns next state tensors.

        Args:
            psi_real: [B, N, d] current field real.
            psi_imag: [B, N, d] current field imaginary.
            h1_in: [B, N, d] IIR h1 (psi[t-1]) for real part.
            h2_in: [B, N, d] IIR h2 (psi[t-2]) for real part.
            h1_im_in: [B, N, d] IIR h1 for imaginary part.
            h2_im_in: [B, N, d] IIR h2 for imaginary part.
            brain_h: [B, n_shells, D_max] brain state.
            Q_ema_val: [1] scalar Qi EMA value.

        Returns:
            (psi_real, psi_imag, h1_next, h2_next, h1_im_next, h2_im_next,
             brain_h_next, Q_mean, diagnostics)
        """
        B = psi_real.shape[0]
        device = psi_real.device

        # ── 1. Breath from aggregate field phase ──
        breath = self._tripartite_breath(psi_real, psi_imag)

        # ── 2. Cord: IIR resonant transport ──
        batch_shape = torch.Size([B, self.N])
        a1_full, a2_full = self.iir_bank.compute_coefficients(
            batch_shape=batch_shape, device=device,
        )
        S_re = psi_real.mean(dim=1, keepdim=True)   # [B, 1, d]
        S_im = psi_imag.mean(dim=1, keepdim=True)   # [B, 1, d]
        # Position-form: IIR replaces psi
        new_psi_re = a1_full * psi_real + a2_full * h1_in + S_re
        new_psi_im = a1_full * psi_imag + a2_full * h1_im_in + S_im
        # State update for next step
        h1_next = psi_real      # current psi[t] → becomes psi[t-1] next step
        h2_next = h1_in         # old h1 (psi[t-1]) → becomes psi[t-2] next step
        h1_im_next = psi_imag
        h2_im_next = h1_im_in
        psi_real, psi_imag = new_psi_re, new_psi_im

        # ── 3. Pattern-memory read ──
        query = F.layer_norm(psi_real, psi_real.shape[-1:])
        # Approximate Qi from current psi2 (no persistent Q_field)
        psi2_approx = self._complex_norm2(psi_real, psi_imag)
        Q_for_pm = psi2_approx.mean(dim=-1)  # [B, N]
        pm_real, pm_imag, pm_diag = self.pattern_memory(query, Q_for_pm)
        psi_real = psi_real + pm_real
        psi_imag = psi_imag + pm_imag

        # ── 4. Prediction ──
        P_re, P_im, eps2, _ = self.prediction(psi_real, psi_imag)

        # ── 5. Qi (Ricci curvature — computed fresh, no persistent Q_field) ──
        psi2 = self._complex_norm2(psi_real, psi_imag)   # [B, N, d]
        Q = psi2 * eps2                                   # [B, N, d]
        Q_mean = Q.mean()
        psi2_mean = psi2.mean()

        # ── 6. Brain coupling ──
        # BrainStep operates per-position [B, d]; mean-pool over N.
        psi_real_mean = psi_real.mean(dim=1)   # [B, d]
        psi_imag_mean = psi_imag.mean(dim=1)   # [B, d]
        dpsi_br, dpsi_bi, brain_h_next = self.brain(
            psi_real_mean, psi_imag_mean,
            breath['yang'], breath['yin'],
            brain_h,
        )
        # Broadcast brain perturbation back to all N positions
        dpsi_br = dpsi_br.unsqueeze(1)   # [B, 1, d]
        dpsi_bi = dpsi_bi.unsqueeze(1)   # [B, 1, d]

        # ── 7. Constraint forces ──
        cf = self._constraint_forces(Q_ema_val, psi2_mean,
                                     breath['yang'], breath['yin'])
        self_reg = self._calm_arousal(Q_mean, breath['yin'])

        # ── 8. Prediction feedback with breath modulation ──
        alpha = PHI_INV * (1.0 + 0.5 * breath['yang']) * cf['lambda_Q'] * self_reg
        psi_real = psi_real + alpha * P_re + self.brain_scale * dpsi_br
        psi_imag = psi_imag + alpha * P_im + self.brain_scale * dpsi_bi

        # ── 8b. Low-Q arousal noise (explores when predictions are poor) ──
        if self.training:
            noise_std = self.noise_scale / (1.0 + Q_mean.detach())
            psi_real = psi_real + noise_std * torch.randn_like(psi_real)
            psi_imag = psi_imag + noise_std * torch.randn_like(psi_imag)

        # ── 9. Yin↔Yang coupling ──
        rho = (PHI_INV * cf['lambda_B']).clamp(max=0.90)
        psi_real_new = psi_real - rho * psi_imag
        psi_imag_new = psi_imag + rho * psi_real
        psi_real, psi_imag = psi_real_new, psi_imag_new

        # ── 10. Glial homeostasis (inlined) ──
        energy = self._complex_norm2(psi_real, psi_imag).mean(dim=-1, keepdim=True)
        excess = F.relu(energy - PHI ** 2)
        factor = (1.0 - 0.05 * cf['lambda_E'] * excess).clamp(0.0, 1.0)
        psi_real = psi_real * factor
        psi_imag = psi_imag * factor

        # ── 11. Breath quadrature rotation ──
        phase = 0.1 * (breath['yin'] - PHI_INV)
        psi_real, psi_imag = self._rotate_complex(psi_real, psi_imag, phase)

        # ── 12. Complex RMSNorm ──
        psi_real, psi_imag = self._complex_rmsnorm(psi_real, psi_imag)

        # Diagnostics
        # Per-position Qi for pattern memory growth [N]
        Q_per_pos = Q.mean(dim=(0, 2)).detach()  # [N]
        diagnostics = {
            'Q_mean': Q_mean,
            'Q_max': Q.max(),
            'Q_per_pos': Q_per_pos,
            'psi2_mean': psi2_mean,
            'self_reg': self_reg,
            'lambda_Q': cf['lambda_Q'],
            'lambda_E': cf['lambda_E'],
            'lambda_B': cf['lambda_B'],
            'breath_yang': breath['yang'],
            'breath_yin': breath['yin'],
            'breath_beat': breath['beat'],
            'breath_phase': breath['phase'],
        }
        if pm_diag:
            diagnostics.update(pm_diag)

        return (psi_real, psi_imag, h1_next, h2_next,
                h1_im_next, h2_im_next, brain_h_next, Q_mean, diagnostics)

    # ════════════════════════════════════════════════
    #  Embed / Readout
    # ════════════════════════════════════════════════

    def embed(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Token/input embedding → psi_real, psi_imag [B, N, d]."""
        if self.continuous_mode:
            proj = self.input_proj(x)
            return proj + self.pos_enc_real, proj + self.pos_enc_imag
        else:
            emb = self.token_embed(x)
            if self.multi_scale_bytes and self.multi_scale_embedder is not None:
                emb = emb + self.multi_scale_embedder(x)
            return emb + self.pos_enc_real, self.imag_proj(emb) + self.pos_enc_imag

    def readout(self, psi_real: torch.Tensor,
                psi_imag: torch.Tensor) -> torch.Tensor:
        """Pooled readout: logits [B, V] or vectors [B, output_dim]."""
        y = psi_real.mean(dim=1)
        z = psi_imag.mean(dim=1)
        y = F.layer_norm(y, y.shape[-1:])
        z = F.layer_norm(z, z.shape[-1:])
        if self.continuous_mode:
            return self.output_proj(y + z)
        return self.readout_y(y) + self.readout_z(z)

    def readout_positions(self, psi_real: torch.Tensor,
                          psi_imag: torch.Tensor) -> torch.Tensor:
        """Per-position readout: logits [B, N, V] or vectors [B, N, output_dim]."""
        y = F.layer_norm(psi_real, psi_real.shape[-1:])
        z = F.layer_norm(psi_imag, psi_imag.shape[-1:])
        if self.continuous_mode:
            return self.output_proj(y + z)
        return self.readout_y(y) + self.readout_z(z)

    # ════════════════════════════════════════════════
    #  Forward
    # ════════════════════════════════════════════════

    def forward(self, x: torch.Tensor,
                sigma: Optional[torch.Tensor] = None,
                state_indices: Optional[torch.Tensor] = None,
                no_reset: bool = False) -> torch.Tensor:
        """Forward pass through K_train field steps.

        Args:
            x: [B, N] token ids (byte mode) or [B, N, input_dim] (continuous).
            sigma: DEPRECATED — accepted for interface compatibility.
            state_indices: Optional [B] keyed IIR bank indices.
            no_reset: If True, preserve field state across calls.

        Returns:
            logits [B, V] or prediction [B, output_dim].
        """
        B = x.shape[0]
        device = x.device

        # ── State initialization ──
        if state_indices is not None:
            if self.state_bank_size <= 0:
                raise ValueError("state_indices provided but state_bank_size is 0")
            for t in self.transceivers:
                if t.h_real.shape[0] != B:
                    t.reset_state(B, device)
        elif not no_reset:
            self.reset_state()
            for t in self.transceivers:
                t.reset_state(B, device)
        else:
            for t in self.transceivers:
                if t.h_real.shape[0] != B:
                    self._resize_transceiver_buffers(t, B)

        # ── Embed ──
        psi_real, psi_imag = self.embed(x)

        # ── K_train loop ──
        all_diag: Dict[str, torch.Tensor] = {}
        for _ in range(self.K_train):
            # Slice IIR state for this batch
            if state_indices is not None:
                state_indices_l = state_indices.long().view(-1).to(device)
                h1_slice = self.h1_bank[state_indices_l].detach().clone()
                h2_slice = self.h2_bank[state_indices_l].detach().clone()
                h1_im_slice = self.h1_im_bank[state_indices_l].detach().clone()
                h2_im_slice = self.h2_im_bank[state_indices_l].detach().clone()
            else:
                h1_slice = self.h1[:B].detach().clone()
                h2_slice = self.h2[:B].detach().clone()
                h1_im_slice = self.h1_im[:B].detach().clone()
                h2_im_slice = self.h2_im[:B].detach().clone()

            brain_h_slice = self.brain.brain_h[:B].detach().clone()

            if self.use_checkpoint and self.training:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 brain_h_next, Q_mean, diag) = torch.utils.checkpoint.checkpoint(
                    self._unified_step,
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    brain_h_slice, self.Q_ema.detach(),
                    use_reentrant=False,
                )
            else:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 brain_h_next, Q_mean, diag) = self._unified_step(
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    brain_h_slice, self.Q_ema.detach(),
                )

            # ── Persist state ──
            if state_indices is not None:
                if self.training:
                    state_indices_l = state_indices.long().view(-1).to(device)
                    self.h2_bank.index_copy_(0, state_indices_l, h2_next.detach())
                    self.h1_bank.index_copy_(0, state_indices_l, h1_next.detach())
                    self.h2_im_bank.index_copy_(0, state_indices_l, h2_im_next.detach())
                    self.h1_im_bank.index_copy_(0, state_indices_l, h1_im_next.detach())
            else:
                self.h2[:B].copy_(h2_next.detach())
                self.h1[:B].copy_(h1_next.detach())
                self.h2_im[:B].copy_(h2_im_next.detach())
                self.h1_im[:B].copy_(h1_im_next.detach())

            # Brain state
            self.brain.brain_h[:B].copy_(brain_h_next.detach())

            # Qi EMA and trend (scalar, no gradient buffer)
            with torch.no_grad():
                self.Q_ema.copy_(PHI_INV * Q_mean + (1.0 - PHI_INV) * self.Q_ema)
                self.Q_trend.copy_(self.Q_ema - Q_mean)

            # Diagnostics accumulation
            for key, val in diag.items():
                if isinstance(val, torch.Tensor) and val.numel() > 1:
                    all_diag[key] = val
                else:
                    all_diag[key] = all_diag.get(key, 0.0) + val if key in all_diag else val

        # Average accumulated scalars
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if not (isinstance(val, torch.Tensor) and val.numel() > 1):
                all_diag[key] = val / self.K_train
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, torch.Tensor) and val.ndim == 0:
                all_diag[key] = val.item()

        logits = self.readout(psi_real, psi_imag)
        self._last_diag = all_diag
        return logits

    # ════════════════════════════════════════════════
    #  Training Loss
    # ════════════════════════════════════════════════

    def training_loss(self, x: torch.Tensor,
                      y: Optional[torch.Tensor] = None,
                      state_indices: Optional[torch.Tensor] = None,
                      no_reset: bool = False) -> Tuple[torch.Tensor, Dict]:
        """Compute training loss.

        Args:
            x: [B, N] token ids (byte mode) or [B, N, input_dim] (continuous).
            y: [B, output_dim] target (continuous mode only).
            state_indices: Optional [B] keyed IIR bank indices.
            no_reset: If True, preserve field state across calls.

        Returns:
            (loss, diagnostics dict).
        """
        if self.continuous_mode:
            return self._training_loss_continuous(x, y, state_indices=state_indices,
                                                  no_reset=no_reset)

        B, N = x.shape
        device = x.device

        # ── State initialization ──
        if state_indices is not None:
            if self.state_bank_size <= 0:
                raise ValueError("state_indices provided but state_bank_size is 0")
            for t in self.transceivers:
                if t.h_real.shape[0] != B:
                    t.reset_state(B, device)
        elif not no_reset:
            self.reset_state()
            for t in self.transceivers:
                t.reset_state(B, device)
        else:
            for t in self.transceivers:
                if t.h_real.shape[0] != B:
                    self._resize_transceiver_buffers(t, B)

        # ── Split context/target ──
        context_len = max(1, N - self.span_len)
        if self.span_len >= N:
            context_len = N // 2
        context = x[:, :context_len]
        target = x[:, context_len:]

        # Pad context to length N by repeating the last token.
        if context.shape[1] < N:
            last_token = context[:, -1:].expand(B, N - context_len)
            context = torch.cat([context, last_token], dim=1)

        # ── Embed ──
        psi_real, psi_imag = self.embed(context)

        # ── K_train loop ──
        all_diag: Dict[str, torch.Tensor] = {}
        last_pm_diag: Dict = {}
        for _ in range(self.K_train):
            if state_indices is not None:
                state_indices_l = state_indices.long().view(-1).to(device)
                h1_slice = self.h1_bank[state_indices_l].detach().clone()
                h2_slice = self.h2_bank[state_indices_l].detach().clone()
                h1_im_slice = self.h1_im_bank[state_indices_l].detach().clone()
                h2_im_slice = self.h2_im_bank[state_indices_l].detach().clone()
            else:
                h1_slice = self.h1[:B].detach().clone()
                h2_slice = self.h2[:B].detach().clone()
                h1_im_slice = self.h1_im[:B].detach().clone()
                h2_im_slice = self.h2_im[:B].detach().clone()

            brain_h_slice = self.brain.brain_h[:B].detach().clone()

            if self.use_checkpoint and self.training:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 brain_h_next, Q_mean, diag) = torch.utils.checkpoint.checkpoint(
                    self._unified_step,
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    brain_h_slice, self.Q_ema.detach(),
                    use_reentrant=False,
                )
            else:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 brain_h_next, Q_mean, diag) = self._unified_step(
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    brain_h_slice, self.Q_ema.detach(),
                )

            # Persist state
            if state_indices is not None:
                if self.training:
                    state_indices_l = state_indices.long().view(-1).to(device)
                    self.h2_bank.index_copy_(0, state_indices_l, h2_next.detach())
                    self.h1_bank.index_copy_(0, state_indices_l, h1_next.detach())
                    self.h2_im_bank.index_copy_(0, state_indices_l, h2_im_next.detach())
                    self.h1_im_bank.index_copy_(0, state_indices_l, h1_im_next.detach())
            else:
                self.h2[:B].copy_(h2_next.detach())
                self.h1[:B].copy_(h1_next.detach())
                self.h2_im[:B].copy_(h2_im_next.detach())
                self.h1_im[:B].copy_(h1_im_next.detach())

            self.brain.brain_h[:B].copy_(brain_h_next.detach())

            with torch.no_grad():
                self.Q_ema.copy_(PHI_INV * Q_mean + (1.0 - PHI_INV) * self.Q_ema)
                self.Q_trend.copy_(self.Q_ema - Q_mean)

            # Running per-position Qi average for pattern growth
            with torch.no_grad():
                Q_per_pos = diag.get('Q_per_pos')
                if Q_per_pos is not None and Q_per_pos.numel() == self.N:
                    self.Q_bar_pos.copy_(
                        0.99 * self.Q_bar_pos + 0.01 * Q_per_pos.detach()
                    )

            # Pattern growth (training only, every step)
            if self.training:
                query = F.layer_norm(psi_real, psi_real.shape[-1:])
                n_new = self.pattern_memory.grow(
                    query, self.Q_bar_pos, current_step=self.pattern_step.item())
                if self.pattern_step % 100 == 0:
                    n_dissolved = self.pattern_memory.dissolve(
                        current_step=self.pattern_step.item())
                self.pattern_step.add_(1)
                diag['pm_new_neurons'] = diag.get('pm_new_neurons', 0) + n_new

            # Diagnostics
            for key, val in diag.items():
                if isinstance(val, torch.Tensor) and val.numel() > 1:
                    all_diag[key] = val
                else:
                    all_diag[key] = all_diag.get(key, 0.0) + val if key in all_diag else val
            last_pm_diag = {k: v for k, v in diag.items() if k.startswith('pm_')}

        # Average diagnostics
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if not (isinstance(val, torch.Tensor) and val.numel() > 1):
                all_diag[key] = val / self.K_train
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, torch.Tensor) and val.numel() == 1:
                all_diag[key] = val.item() if val.ndim == 0 else val.squeeze().item()

        # ── Cross-entropy loss ──
        logits = self.readout_positions(psi_real, psi_imag)  # [B, N, V]
        ce_loss = F.cross_entropy(
            logits[:, context_len:, :].reshape(-1, self.V),
            target.reshape(-1),
        )

        # ── Pattern-utilization auxiliary losses ──
        pattern_div_loss = torch.tensor(0.0, device=device)
        pattern_commit_loss = torch.tensor(0.0, device=device)
        pattern_util_loss = torch.tensor(0.0, device=device)
        if last_pm_diag:
            entropy = last_pm_diag.get('pm_usage_entropy', 0.0)
            if isinstance(entropy, (int, float)):
                entropy = torch.tensor(float(entropy), device=device)
            pattern_div_loss = -entropy
            commit = last_pm_diag.get('pm_commit_loss', 0.0)
            if isinstance(commit, (int, float)):
                commit = torch.tensor(float(commit), device=device)
            pattern_commit_loss = commit
            born_ratio = last_pm_diag.get('pm_born_ratio', 0.0)
            if isinstance(born_ratio, (int, float)):
                born_ratio = torch.tensor(float(born_ratio), device=device)
            pattern_util_loss = (born_ratio - 0.5).pow(2)

        loss = ce_loss \
            + self.lambda_pattern_div * pattern_div_loss \
            + self.lambda_pattern_commit * pattern_commit_loss \
            + self.lambda_pattern_util * pattern_util_loss

        all_diag['ce_loss'] = ce_loss.item()
        all_diag['pattern_div_loss'] = pattern_div_loss.item()
        all_diag['pattern_commit_loss'] = pattern_commit_loss.item()
        all_diag['pattern_util_loss'] = pattern_util_loss.item()
        all_diag['loss'] = loss.item()

        return loss, all_diag

    def _training_loss_continuous(self, x: torch.Tensor,
                                  y: Optional[torch.Tensor] = None,
                                  state_indices: Optional[torch.Tensor] = None,
                                  no_reset: bool = False) -> Tuple[torch.Tensor, Dict]:
        """MSE regression loss for continuous-field inputs."""
        B, N, _ = x.shape
        device = x.device

        if state_indices is not None:
            if self.state_bank_size <= 0:
                raise ValueError("state_indices provided but state_bank_size is 0")
            for t in self.transceivers:
                if t.h_real.shape[0] != B:
                    t.reset_state(B, device)
        elif not no_reset:
            self.reset_state()
            for t in self.transceivers:
                t.reset_state(B, device)
        else:
            for t in self.transceivers:
                if t.h_real.shape[0] != B:
                    self._resize_transceiver_buffers(t, B)

        psi_real, psi_imag = self.embed(x)

        all_diag: Dict[str, torch.Tensor] = {}
        for _ in range(self.K_train):
            if state_indices is not None:
                state_indices_l = state_indices.long().view(-1).to(device)
                h1_slice = self.h1_bank[state_indices_l].detach().clone()
                h2_slice = self.h2_bank[state_indices_l].detach().clone()
                h1_im_slice = self.h1_im_bank[state_indices_l].detach().clone()
                h2_im_slice = self.h2_im_bank[state_indices_l].detach().clone()
            else:
                h1_slice = self.h1[:B].detach().clone()
                h2_slice = self.h2[:B].detach().clone()
                h1_im_slice = self.h1_im[:B].detach().clone()
                h2_im_slice = self.h2_im[:B].detach().clone()

            brain_h_slice = self.brain.brain_h[:B].detach().clone()

            if self.use_checkpoint and self.training:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 brain_h_next, Q_mean, diag) = torch.utils.checkpoint.checkpoint(
                    self._unified_step,
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    brain_h_slice, self.Q_ema.detach(),
                    use_reentrant=False,
                )
            else:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 brain_h_next, Q_mean, diag) = self._unified_step(
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    brain_h_slice, self.Q_ema.detach(),
                )

            if state_indices is not None:
                if self.training:
                    state_indices_l = state_indices.long().view(-1).to(device)
                    self.h2_bank.index_copy_(0, state_indices_l, h2_next.detach())
                    self.h1_bank.index_copy_(0, state_indices_l, h1_next.detach())
                    self.h2_im_bank.index_copy_(0, state_indices_l, h2_im_next.detach())
                    self.h1_im_bank.index_copy_(0, state_indices_l, h1_im_next.detach())
            else:
                self.h2[:B].copy_(h2_next.detach())
                self.h1[:B].copy_(h1_next.detach())
                self.h2_im[:B].copy_(h2_im_next.detach())
                self.h1_im[:B].copy_(h1_im_next.detach())

            self.brain.brain_h[:B].copy_(brain_h_next.detach())

            with torch.no_grad():
                self.Q_ema.copy_(PHI_INV * Q_mean + (1.0 - PHI_INV) * self.Q_ema)
                self.Q_trend.copy_(self.Q_ema - Q_mean)

            for key, val in diag.items():
                if isinstance(val, torch.Tensor) and val.numel() > 1:
                    all_diag[key] = val
                else:
                    all_diag[key] = all_diag.get(key, 0.0) + val if key in all_diag else val

        for key in list(all_diag.keys()):
            val = all_diag[key]
            if not (isinstance(val, torch.Tensor) and val.numel() > 1):
                all_diag[key] = val / self.K_train
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, torch.Tensor) and val.numel() == 1:
                all_diag[key] = val.item() if val.ndim == 0 else val.squeeze().item()

        pred = self.readout(psi_real, psi_imag)  # [B, output_dim]
        if y is not None:
            mse_loss = F.mse_loss(pred, y)
        else:
            mse_loss = torch.tensor(0.0, device=device)

        with torch.no_grad():
            mae_loss = F.l1_loss(pred, y) if y is not None else torch.tensor(0.0, device=device)

        loss = mse_loss

        all_diag['mse_loss'] = mse_loss.item()
        all_diag['mae_loss'] = mae_loss.item()
        all_diag['loss'] = loss.item()
        all_diag['Q_mean'] = all_diag.get('Q_mean', 0.0)

        return loss, all_diag

    # ════════════════════════════════════════════════
    #  State Management
    # ════════════════════════════════════════════════

    def reset_state(self) -> None:
        """Clear all persistent field and brain state."""
        self.h1.zero_()
        self.h2.zero_()
        self.h1_im.zero_()
        self.h2_im.zero_()
        if self.state_bank_size > 0:
            self.h1_bank.zero_()
            self.h2_bank.zero_()
            self.h1_im_bank.zero_()
            self.h2_im_bank.zero_()
        self.Q_ema.zero_()
        self.Q_trend.zero_()
        self.Q_bar_pos.zero_()
        self.pattern_step.zero_()
        self.pattern_memory.qi_ema.zero_()
        self.breath_t_yang.zero_()
        self.breath_t_yin.zero_()
        self.brain.reset_state()

    @staticmethod
    def _resize_transceiver_buffers(transceiver: nn.Module, new_B: int) -> None:
        """Resize a transceiver's persistent IIR buffers to new_B rows."""
        for buf_name in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                         'x_prev_real', 'x_prev_imag'):
            old = getattr(transceiver, buf_name)
            old_B = old.shape[0]
            if old_B == new_B:
                continue
            new = torch.zeros(new_B, *old.shape[1:], dtype=old.dtype, device=old.device)
            n_copy = min(old_B, new_B)
            new[:n_copy] = old[:n_copy]
            setattr(transceiver, buf_name, new)

    # ════════════════════════════════════════════════
    #  Autoregressive Generation
    # ════════════════════════════════════════════════

    @torch.no_grad()
    def generate_autoregressive(self, seed: torch.Tensor, max_new: int = 128,
                                temp: float = 0.8, K_init: Optional[int] = None,
                                repetition_penalty: float = 1.2,
                                rep_window: int = 8,
                                top_k: Optional[int] = None,
                                ngram_block_size: int = 0) -> torch.Tensor:
        """Autoregressively generate a byte sequence from a seed.

        The field is settled on the seed, then new bytes are sampled one at a
        time from the last-position readout logits as the window slides forward.

        Args:
            seed: [L] byte ids on the model's device, L ≤ N.
            max_new: Number of new bytes to generate.
            temp: Sampling temperature (lower = more deterministic).
            K_init: Number of field settling steps on the seed (default self.K_gen).
            repetition_penalty: Divide logits for recently generated bytes (>1.0
                penalizes, <1.0 boosts; 1.0 disables).
            rep_window: Number of recent generated bytes considered for penalty.
            top_k: If given, keep only the top-k logits (None/0 = disabled).
            ngram_block_size: If > 0, block tokens that would complete an n-gram
                present in the last `rep_window` generated bytes.

        Returns:
            [max_new] tensor of byte ids.
        """
        if K_init is None:
            K_init = self.K_gen
        device = seed.device

        self.eval()
        self.reset_state()
        for t in self.transceivers:
            t.reset_state(1, device)

        if seed.numel() == 0:
            seed = torch.randint(0, self.V, (1,), device=device)

        # ── Settle on seed ──
        # Pad seed to length N (repeat last token) so the field can develop
        # context across all N positions.
        L = seed.numel()
        if L < self.N:
            pad = seed[-1:].expand(self.N - L)
            window = torch.cat([seed, pad])  # [N]
        else:
            window = seed[-self.N:]  # [N]

        batch = window.unsqueeze(0)  # [1, N]
        for _ in range(K_init):
            _ = self.forward(batch, no_reset=True)

        # ── Autoregressive loop ──
        generated = []
        window_list = list(window.tolist())

        for _ in range(max_new):
            # One unified step on the current window, then per-position logits
            # from the last position.
            batch = torch.tensor(window_list, dtype=torch.long,
                                device=device).unsqueeze(0)
            psi_real, psi_imag = self.embed(batch)

            h1_sl = self.h1[:1].detach().clone()
            h2_sl = self.h2[:1].detach().clone()
            h1i_sl = self.h1_im[:1].detach().clone()
            h2i_sl = self.h2_im[:1].detach().clone()
            bh_sl = self.brain.brain_h[:1].detach().clone()

            (psi_real, psi_imag, h1n, h2n, h1in, h2in,
             bhn, _, _) = self._unified_step(
                psi_real, psi_imag, h1_sl, h2_sl, h1i_sl, h2i_sl,
                bh_sl, self.Q_ema.detach())
            self.h1[:1].copy_(h1n)
            self.h2[:1].copy_(h2n)
            self.h1_im[:1].copy_(h1in)
            self.h2_im[:1].copy_(h2in)
            self.brain.brain_h[:1].copy_(bhn)

            logits = self.readout_positions(psi_real, psi_imag)[0, -1, :]
            logits = logits / max(temp, 1e-6)

            # Repetition penalty
            if generated and repetition_penalty != 1.0:
                for b in set(generated[-rep_window:]):
                    logits[b] /= repetition_penalty
            if ngram_block_size > 0 and len(generated) >= ngram_block_size - 1:
                recent = generated[-rep_window:]
                prefix = (generated[-(ngram_block_size - 1):]
                          if ngram_block_size > 1 else [])
                for tok in range(self.V):
                    ngram = tuple(prefix + [tok])
                    for i in range(len(recent) - ngram_block_size + 1):
                        if tuple(recent[i:i + ngram_block_size]) == ngram:
                            logits[tok] = -float('inf')
                            break

            # Top-k filtering.
            if top_k is not None and top_k > 0:
                k = min(top_k, self.V)
                v, _ = torch.topk(logits, k)
                logits[logits < v[-1]] = -float('inf')

            probs = F.softmax(logits, dim=-1)
            next_byte = torch.multinomial(probs, num_samples=1).item()
            generated.append(next_byte)

            # Slide window: drop oldest token, append new.
            window_list.pop(0)
            window_list.append(next_byte)
            window = torch.tensor(window_list, dtype=torch.long, device=device)
            batch = window.unsqueeze(0)  # [1, N]

        return torch.tensor(generated, dtype=torch.long, device=device)

    # ════════════════════════════════════════════════
    #  Checkpoint Compatibility
    # ════════════════════════════════════════════════

    def _normalize_state_dict(self, state_dict: Dict[str, torch.Tensor],
                              initialized_keys: Optional[set] = None,
                              verbose: bool = False) -> Dict[str, torch.Tensor]:
        """Convert old checkpoints to the current architecture.

        Handles:
        - stale alias keys (transceivers.→prediction.transceivers.)
        - stale residuals.* keys
        - stale controller.* keys (from old checkpoints loaded into TripartiteCord)
        - transceiver persistent buffers whose batch dim changed
        - IIR buffers h1/h2/h1_im/h2_im whose shape changed
        - keyed state bank buffers
        - pattern memory long-term and transient buffers
        - missing parameters/buffers initialized from defaults
        """
        def _log(msg):
            if verbose:
                print(f'  [normalize] {msg}')

        # Drop stale alias keys
        alias_prefixes = {
            'transceivers': 'prediction.transceivers',
            'cross_chakra': 'prediction.cross_chakra',
        }
        for alias, target in alias_prefixes.items():
            for key in list(state_dict.keys()):
                if key.startswith(alias + '.') or key == alias:
                    target_key = key.replace(alias, target, 1)
                    if target_key in state_dict:
                        del state_dict[key]
                        if verbose:
                            print(f'  [normalize] removed stale alias {key} (shadowed by {target_key})')

        # Drop stale residuals.* keys
        for key in list(state_dict.keys()):
            if key.startswith('residuals.') or key == 'residuals':
                del state_dict[key]
                if verbose:
                    print(f'  [normalize] dropped stale residuals key {key} (MLP removed)')

        # Drop stale controller.* keys (no controller in TripartiteCord)
        n_ctrl_dropped = 0
        for key in list(state_dict.keys()):
            if key.startswith('controller.') or key == 'controller':
                del state_dict[key]
                n_ctrl_dropped += 1
        if n_ctrl_dropped:
            _log(f'dropped {n_ctrl_dropped} stale controller key(s)')

        # Drop stale qi_dynamics.* keys
        n_qi_dropped = 0
        for key in list(state_dict.keys()):
            if key.startswith('qi_dynamics.') or key == 'qi_dynamics':
                del state_dict[key]
                n_qi_dropped += 1
        if n_qi_dropped:
            _log(f'dropped {n_qi_dropped} stale qi_dynamics key(s)')

        # Drop stale ctrl_mod.* and breath.* keys
        for prefix in ('ctrl_mod.', 'ctrl_mod', 'breath.', 'breath'):
            for key in list(state_dict.keys()):
                if key.startswith(prefix):
                    del state_dict[key]

        # Drop stale Q_field key (no persistent Q_field in TripartiteCord)
        if 'Q_field' in state_dict:
            del state_dict['Q_field']
            _log('dropped stale Q_field buffer (recomputed from psi)')

        # Drop stale cord path keys
        for key in list(state_dict.keys()):
            if (key.startswith('prediction.cord.') or key == 'prediction.cord'
                    or key.startswith('cord.') or key == 'cord'
                    or key == 'cord_pos_scale' or key.startswith('cord_pos_scale.')
                    or key == 'cord_history' or key.startswith('cord_history.')):
                del state_dict[key]

        # Resize transceiver persistent buffers
        n_tx_resized = 0
        for key in list(state_dict.keys()):
            parts = key.split('.')
            if (len(parts) >= 2 and parts[-1] in (
                'h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                'x_prev_real', 'x_prev_imag'
            ) and 'transceivers' in parts):
                old = state_dict[key]
                param = self
                for part in parts:
                    param = getattr(param, part)
                target_shape = tuple(param.shape)
                if old.shape != target_shape:
                    new = param.data.clone()
                    min_b = min(old.shape[0], target_shape[0])
                    min_w = min(old.shape[1], target_shape[1])
                    new[:min_b, :min_w] = old[:min_b, :min_w]
                    state_dict[key] = new
                    n_tx_resized += 1
        if n_tx_resized:
            _log(f'resized {n_tx_resized} transceiver buffer(s)')

        # Resize IIR buffers h1/h2/h1_im/h2_im
        for key in ('h1', 'h2', 'h1_im', 'h2_im'):
            if key in state_dict:
                if not hasattr(self, key):
                    del state_dict[key]
                    _log(f'dropped stale buffer {key} (not in current model)')
                    continue
                old = state_dict[key]
                target = getattr(self, key)
                if tuple(old.shape) != tuple(target.shape):
                    new = target.data.clone()
                    min_b = min(old.shape[0], target.shape[0])
                    min_n = min(old.shape[1], target.shape[1])
                    min_d = min(old.shape[2], target.shape[2])
                    new[:min_b, :min_n, :min_d] = old[:min_b, :min_n, :min_d]
                    state_dict[key] = new
                    _log(f'resized {key} from {tuple(old.shape)} to {tuple(target.shape)}')

        # Resize keyed state banks
        for key in ('h1_bank', 'h2_bank', 'h1_im_bank', 'h2_im_bank'):
            if key in state_dict:
                if not hasattr(self, key):
                    del state_dict[key]
                    _log(f'dropped stale buffer {key} (no state bank in current model)')
                    continue
                old = state_dict[key]
                target = getattr(self, key)
                if tuple(old.shape) != tuple(target.shape):
                    new = target.data.clone()
                    min_b = min(old.shape[0], target.shape[0])
                    min_n = min(old.shape[1], target.shape[1])
                    min_d = min(old.shape[2], target.shape[2])
                    new[:min_b, :min_n, :min_d] = old[:min_b, :min_n, :min_d]
                    state_dict[key] = new
                    _log(f'resized {key} from {tuple(old.shape)} to {tuple(target.shape)}')

        # Resize brain_h buffer
        if 'brain.brain_h' in state_dict:
            old = state_dict['brain.brain_h']
            target = self.brain.brain_h
            if tuple(old.shape) != tuple(target.shape):
                new = target.data.clone()
                min_b = min(old.shape[0], target.shape[0])
                min_s = min(old.shape[1], target.shape[1])
                min_d = min(old.shape[2], target.shape[2])
                new[:min_b, :min_s, :min_d] = old[:min_b, :min_s, :min_d]
                state_dict['brain.brain_h'] = new
                _log(f'resized brain.brain_h from {tuple(old.shape)} to {tuple(target.shape)}')

        # Pattern memory: resize long-term buffers
        pm_buffer_names = QiPatternMemory.get_checkpoint_buffer_names()
        n_pm_resized = 0
        for buf_name in pm_buffer_names:
            key = f'pattern_memory.{buf_name}'
            if key not in state_dict:
                continue
            if not hasattr(self.pattern_memory, buf_name):
                del state_dict[key]
                _log(f'dropped stale PM buffer {key}')
                continue
            old = state_dict[key]
            target = getattr(self.pattern_memory, buf_name)
            if tuple(old.shape) != tuple(target.shape):
                new = target.data.clone()
                n_dim = len(old.shape)
                if n_dim == 1:
                    n = min(old.shape[0], target.shape[0])
                    new[:n] = old[:n]
                elif n_dim == 2:
                    n0 = min(old.shape[0], target.shape[0])
                    n1 = min(old.shape[1], target.shape[1])
                    new[:n0, :n1] = old[:n0, :n1]
                state_dict[key] = new
                n_pm_resized += 1
        if n_pm_resized:
            _log(f'resized {n_pm_resized} pattern memory buffer(s)')

        # Resize pattern memory parameters
        n_pm_params_resized = 0
        for pm_param_name in ('keys', 'values_real', 'values_imag'):
            key = f'pattern_memory.{pm_param_name}'
            if key not in state_dict:
                continue
            if not hasattr(self.pattern_memory, pm_param_name):
                del state_dict[key]
                _log(f'dropped stale PM param {key}')
                continue
            old = state_dict[key]
            target = getattr(self.pattern_memory, pm_param_name)
            if tuple(old.shape) != tuple(target.shape):
                new = target.data.clone()
                n_dim = len(old.shape)
                if n_dim == 1:
                    n = min(old.shape[0], target.shape[0])
                    new[:n] = old[:n]
                elif n_dim == 2:
                    n0 = min(old.shape[0], target.shape[0])
                    n1 = min(old.shape[1], target.shape[1])
                    new[:n0, :n1] = old[:n0, :n1]
                state_dict[key] = new
                n_pm_params_resized += 1
        if n_pm_params_resized:
            _log(f'resized {n_pm_params_resized} pattern memory parameter(s)')

        # Drop transient PM buffers with shape mismatch
        for key in list(state_dict.keys()):
            if key == 'pattern_memory.qi_ema':
                param = self
                for part in key.split('.'):
                    param = getattr(param, part)
                if tuple(state_dict[key].shape) != tuple(param.shape):
                    del state_dict[key]
                    _log(f'dropped transient PM buffer {key} (shape mismatch)')

        # Initialize missing new parameters/buffers from defaults
        if initialized_keys is None:
            initialized_keys = set()
        n_missing_params = 0
        n_missing_buffers = 0
        for name, param in self.named_parameters():
            if name not in state_dict:
                state_dict[name] = param.data.clone()
                initialized_keys.add(name)
                n_missing_params += 1
        for name, buf in self.named_buffers():
            if name not in state_dict:
                state_dict[name] = buf.data.clone()
                initialized_keys.add(name)
                n_missing_buffers += 1
        if n_missing_params or n_missing_buffers:
            _log(f'initialized {n_missing_params} missing param(s) and '
                 f'{n_missing_buffers} missing buffer(s) from defaults')

        return state_dict

    def load_state_dict(self, state_dict: Dict[str, torch.Tensor],
                        strict: bool = False, assign: bool = False):
        """Load checkpoint with normalization and transient state reset."""
        initialized = set()
        state_dict = self._normalize_state_dict(state_dict, initialized_keys=initialized,
                                                verbose=True)
        missing, unexpected = super().load_state_dict(state_dict, strict=strict, assign=assign)
        if initialized:
            print(f'Initialized {len(initialized)} missing tensors from defaults '
                  f'(new buffers/parameters)')
        if unexpected:
            print(f'Dropped {len(unexpected)} unexpected tensors from checkpoint '
                  f'(stale architecture)')
        # Reset transient pattern-memory and scalar statistics
        self.pattern_memory.qi_ema.zero_()
        self.Q_bar_pos.zero_()
        self.Q_ema.zero_()
        self.Q_trend.zero_()
        return missing, unexpected


# ════════════════════════════════════════════════
#  Smoke test
# ════════════════════════════════════════════════

if __name__ == '__main__':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    m = TripartiteCord(N=4, d=64).to(device)
    x = torch.randint(0, 256, (2, 4)).to(device)
    loss, info = m.training_loss(x)
    assert torch.isfinite(loss), f"Loss is not finite: {loss}"
    loss.backward()
    print('TripartiteCord smoke tests passed.')
    print(f"  Loss: {loss.item():.4f}")
    print(f"  Q_mean: {info.get('Q_mean', 'N/A')}")
    print(f"  Params: {sum(p.numel() for p in m.parameters()):,}")
