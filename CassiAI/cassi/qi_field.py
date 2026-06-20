"""QiField — Complex self-predicting Qi wave field.

The field ψ ∈ ℂ^(B×N×d) is stored as real/imag pairs.  Yang = Re(ψ),
Yin = Im(ψ), and Qi Q = |ψ|²·|ε|² emerges from the prediction gap.

Key design choices:
- Complex ψ-field, persistent Qi-field, φ-damped IIR spine.
- Prediction operator P[ψ] is interference from transceiver neurons per chakra
  plus a tiny learned residual.
- Qi obeys the continuity equation: persistent memory, saturating source,
  super-linear sink, and pressure-gradient advection.
- Qi shapes ψ only through the self-awareness controller (alpha/gamma/rho/
  perturb/m_self), not by direct forcing.
- Structural calm/arousal around PHI_INV is hard-coded; controller learns
  small deltas via CE + a tiny homeostasis regularizer.
"""

import math
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cord import PHI, PHI_INV
from cassi.breath import Breath
from cassi.self_awareness_controller import SelfAwarenessController, CtrlOutputs
from cassi.transceiver_neuron import ComplexTransceiverNeuron
from cassi.glial_homeostasis import GlialHomeostasis
from cassi.pattern_memory import QiPatternMemory
from cassi.multi_scale_byte import MultiScaleByteEmbedder



class ChakraResidual(nn.Module):
    """Tiny learned residual predictor per chakra."""

    def __init__(self, d_c: int):
        super().__init__()
        hidden = max(16, 4 * d_c)
        self.net = nn.Sequential(
            nn.Linear(d_c, hidden),
            nn.GELU(),
            nn.Linear(hidden, d_c),
        )

    def forward(self, psi_c: torch.Tensor) -> torch.Tensor:
        return self.net(psi_c)


class QiField(nn.Module):
    """Complex QiField with transceiver prediction and persistent Qi dynamics."""

    def __init__(self, N: int = 128, d: int = 128, C: int = 13, V: int = 256,
                 K_train: int = 10, K_gen: int = 50, M: int = 2048,
                 self_aware: bool = True,
                 ctrl_hidden_dim: int = 64,
                 ctrl_loss_weight: float = 0.01,
                 lambda_homeo: float = 0.001,
                 lambda_breath_gating: float = 0.0,
                 lambda_smooth: float = 0.0,
                 lambda_balance: float = 0.0,
                 lambda_center: float = 0.0,
                 n_neurons: int = 13,
                 homeo_gain: float = 0.05,
                 qi_rho: float = PHI_INV,
                 sink_gamma: float = PHI_INV,
                 use_fused_kernels: bool = True,
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
        self.N = N
        self.d = d
        self.max_batch_size = max_batch_size
        self.C = C
        self.V = V
        self.K_train = K_train
        self.K_gen = K_gen
        self.M = M
        self.self_aware = self_aware
        self.lambda_homeo = lambda_homeo
        self.ctrl_hidden_dim = ctrl_hidden_dim
        self.ctrl_loss_weight = ctrl_loss_weight
        self.qi_rho = qi_rho
        self.sink_gamma = sink_gamma
        self.qi_eps0_log = nn.Parameter(torch.zeros(1))
        self.use_fused_kernels = use_fused_kernels
        self.use_checkpoint = use_checkpoint
        self.span_len = span_len
        self.lambda_pattern_div = lambda_pattern_div
        self.lambda_pattern_commit = lambda_pattern_commit
        self.lambda_pattern_util = lambda_pattern_util

        self.input_dim = input_dim
        self.output_dim = output_dim
        self.continuous_mode = continuous_mode

        # φ-scaled chakra widths
        raw = [PHI ** c for c in range(C)]
        total_raw = sum(raw)
        widths = [max(1, round(d * r / total_raw)) for r in raw]
        while sum(widths) > d:
            widths[max(range(C), key=lambda i: widths[i])] -= 1
        while sum(widths) < d:
            widths[max(range(C), key=lambda i: widths[i])] += 1
        self.chakra_widths = widths

        # Embedding: split into real/imag parts
        if self.continuous_mode:
            self.input_proj = nn.Linear(input_dim, d)
            self.token_embed = None
            self.imag_proj = None
        else:
            self.input_proj = None
            self.token_embed = nn.Embedding(V, d)
            nn.init.normal_(self.token_embed.weight, std=0.02)
            self.imag_proj = nn.Linear(d, d, bias=False)
        t = torch.arange(N, dtype=torch.float32).view(-1, 1)
        i = torch.arange(d, dtype=torch.float32).view(1, -1)
        base = 2.0 * math.pi / N
        k = torch.round(PHI ** (i * 2.0 / d) * N / (2.0 * math.pi))
        # Ensure N-periodic frequencies are strictly positive and distinct.
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
        # Persistent field state. Shape [1, N, d] and expanded per batch.
        # The per-batch-slot IIR buffers h1/h2 below provide a fallback when no
        # keyed state bank is active; with state_bank_size > 0, h1_bank/h2_bank
        # hold keyed IIR state per sample.
        self.register_buffer('psi_real', torch.zeros(1, N, d))
        self.register_buffer('psi_imag', torch.zeros(1, N, d))
        self.register_buffer('Q_field', torch.zeros(1, N, d))

        # Per-batch-slot IIR fallback persists across training steps (when not
        # reset). Shape [max_batch_size, N, d] so each slot can carry its own
        # IIR history across contiguous sequences. For randomly sampled
        # independent windows, use reset_state() every batch to avoid
        # cross-sample contamination.
        self.register_buffer('h1', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h2', torch.zeros(max_batch_size, N, d))

        # Optional keyed per-sample IIR state bank.
        self.state_bank_size = state_bank_size
        if state_bank_size > 0:
            self.register_buffer('h1_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h2_bank', torch.zeros(state_bank_size, N, d))

        offsets = [0]
        for c in range(C):
            offsets.append(offsets[-1] + self.chakra_widths[c])
        self.register_buffer('chakra_offsets', torch.tensor(offsets, dtype=torch.int32))
        self.register_buffer('chakra_id',
                             torch.repeat_interleave(torch.arange(C), torch.tensor(widths)))

        # Learnable IIR frequencies
        theta_init = torch.zeros(C)
        for c in range(C):
            ratio = max(0.001, min(0.999, PHI_INV ** c))
            theta_init[c] = math.log(ratio / (1.0 - ratio))
        self.theta = nn.Parameter(theta_init)

        # Transceiver prediction bank (one per chakra)
        self.transceivers = nn.ModuleList([
            ComplexTransceiverNeuron(width=self.chakra_widths[c],
                                     theta_init=0.1 * (PHI ** (c % 8)))
            for c in range(C)
        ])
        self.residuals = nn.ModuleList([
            ChakraResidual(self.chakra_widths[c]) for c in range(C)
        ])

        # Glial homeostasis and breath
        self.glial = GlialHomeostasis(target_energy=PHI ** 2, gain=homeo_gain)
        self.breath = Breath()

        self.field_scale = nn.Parameter(torch.tensor(1.0))

        # Controller
        if self_aware:
            self.controller = SelfAwarenessController(C=C, hidden_dim=ctrl_hidden_dim)
        else:
            self.controller = None

        # Pattern-memory neuron bank
        self.max_neurons = max_neurons
        self.pattern_memory = QiPatternMemory(d=d, max_neurons=max_neurons)

        # Optional φ-scaled multi-scale byte embedder
        self.multi_scale_bytes = multi_scale_bytes
        self.multi_scale_scales = multi_scale_scales
        self.multi_scale_byte_embed_dim = multi_scale_byte_embed_dim
        if self.multi_scale_bytes:
            self.multi_scale_embedder = MultiScaleByteEmbedder(
                d_out=d,
                scales=multi_scale_scales,
                byte_embed_dim=multi_scale_byte_embed_dim,
            )
        else:
            self.multi_scale_embedder = None

        # Readout
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

        self.register_buffer('Q_ema', torch.zeros(1))
        self.register_buffer('Q_trend', torch.zeros(1))
        self.register_buffer('pattern_step', torch.zeros(1, dtype=torch.long))
        self.register_buffer('Q_bar_pos', torch.zeros(1, N))

    def _normalize_state_dict(self, state_dict, initialized_keys=None):
        """Convert old checkpoints to the current architecture.

        Handles:
        - controller.prev_outputs buffer size change (30 -> 2*C+2)
        - removed controller.head_beta_legacy / head_delta_legacy weights
        - missing qi_eps0_log (new learnable source scale)
        - transceiver persistent buffers whose batch dim changed (old checkpoints
          often have batch_size=32 because the model was reset before saving)
        """
        # Resize transceiver persistent buffers to the current shape.
        for key in list(state_dict.keys()):
            if key.startswith('transceivers.') and key.split('.')[-1] in (
                'h_real', 'h_imag', 'h_prev_real', 'h_prev_imag', 'x_prev_real', 'x_prev_imag'
            ):
                old = state_dict[key]
                param = self
                for part in key.split('.'):
                    param = getattr(param, part)
                target_shape = tuple(param.shape)
                if old.shape != target_shape:
                    new = param.data.clone()
                    min_b = min(old.shape[0], target_shape[0])
                    min_w = min(old.shape[1], target_shape[1])
                    new[:min_b, :min_w] = old[:min_b, :min_w]
                    state_dict[key] = new

        # Resize per-sample IIR buffers from old [1, N, d] or [B, N, d] to
        # current [max_batch_size, N, d], preserving as much history as fits.
        for key in ('h1', 'h2'):
            if key in state_dict:
                if not hasattr(self, key):
                    del state_dict[key]
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

        # Resize keyed IIR state banks from old [bank_size, N, d] to current.
        for key in ('h1_bank', 'h2_bank'):
            if key in state_dict:
                if not hasattr(self, key):
                    del state_dict[key]
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
        new_shape = 2 * self.C + 2
        if 'controller.prev_outputs' in state_dict:
            old = state_dict['controller.prev_outputs']
            if old.shape != torch.Size([new_shape]):
                new = torch.zeros(new_shape, dtype=old.dtype, device=old.device)
                n = min(old.numel(), new.numel())
                new[:n] = old[:n]
                state_dict['controller.prev_outputs'] = new

        # Remove legacy controller heads that no longer exist.
        for key in list(state_dict.keys()):
            if 'controller.head_beta_legacy' in key or 'controller.head_delta_legacy' in key:
                del state_dict[key]

        # Drop transient buffers whose shape depends on runtime dimensions (e.g. N)
        # so strict loading falls back to the freshly initialized buffer.
        for key in list(state_dict.keys()):
            if key in ('pattern_memory.qi_ema',):
                param = self
                for part in key.split('.'):
                    param = getattr(param, part)
                if tuple(state_dict[key].shape) != tuple(param.shape):
                    del state_dict[key]
        # Initialize missing new parameters/buffers from defaults.
        if initialized_keys is None:
            initialized_keys = set()
        for name, param in self.named_parameters():
            if name not in state_dict:
                state_dict[name] = param.data.clone()
                initialized_keys.add(name)
        for name, buf in self.named_buffers():
            if name not in state_dict:
                state_dict[name] = buf.data.clone()
                initialized_keys.add(name)

        return state_dict

    def load_state_dict(self, state_dict, strict=False, assign=False):
        initialized = set()
        state_dict = self._normalize_state_dict(state_dict, initialized_keys=initialized)
        missing, unexpected = super().load_state_dict(state_dict, strict=strict, assign=assign)
        if initialized:
            print(f'Initialized {len(initialized)} missing tensors from defaults (new buffers/parameters)')
        if unexpected:
            print(f'Dropped {len(unexpected)} unexpected tensors from checkpoint (stale architecture)')
        # Reset transient pattern-memory statistics so the new run starts fresh.
        self.pattern_memory.qi_ema.zero_()
        self.Q_bar_pos.zero_()
        return missing, unexpected


    # ═══════════════════ Utilities ═══════════════════

    def _decompose_chakras(self, psi_real, psi_imag):
        re_parts, im_parts = [], []
        off = 0
        for c in range(self.C):
            dc = self.chakra_widths[c]
            re_parts.append(psi_real[:, :, off:off + dc])
            im_parts.append(psi_imag[:, :, off:off + dc])
            off += dc
        return re_parts, im_parts

    def _compose_chakras(self, re_parts, im_parts):
        return torch.cat(re_parts, dim=-1), torch.cat(im_parts, dim=-1)

    @staticmethod
    def _complex_norm2(a_real, a_imag):
        return a_real ** 2 + a_imag ** 2

    def _complex_rmsnorm(self, psi_real, psi_imag):
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
    def _rotate_complex(real, imag, angle):
        c = torch.cos(angle)
        s = torch.sin(angle)
        return real * c - imag * s, real * s + imag * c

    # ═══════════════════ Prediction operator ═══════════════════

    def predict(self, psi_real, psi_imag):
        re_parts, im_parts = self._decompose_chakras(psi_real, psi_imag)
        pred_re, pred_im = [], []

        for c in range(self.C):
            psi_c_re = re_parts[c]
            psi_c_im = im_parts[c]
            B, N, dc = psi_c_re.shape

            mean_re = psi_c_re.mean(dim=1, keepdim=True)
            mean_im = psi_c_im.mean(dim=1, keepdim=True)

            tx_re, tx_im = self.transceivers[c](mean_re.squeeze(1), mean_im.squeeze(1))
            tx_re = tx_re.unsqueeze(1).expand(-1, N, -1)
            tx_im = tx_im.unsqueeze(1).expand(-1, N, -1)

            pred_re.append(psi_c_re + tx_re + self.residuals[c](psi_c_re))
            pred_im.append(psi_c_im + tx_im + self.residuals[c](psi_c_im))

        P_re, P_im = self._compose_chakras(pred_re, pred_im)
        eps2 = self._complex_norm2(psi_real - P_re, psi_imag - P_im)
        return P_re, P_im, eps2

    # ═══════════════════ Qi dynamics ═══════════════════

    def _advect(self, Q_transport, p):
        """Pressure-gradient advection on the spatial Qi field.

        Uses the forward-difference pressure gradient and an upwind flux
        consistent with the continuity equation ∂Q/∂t + ∇·(Q·v_Q) = ... .
        Returns the *advective increment* v_Q * upwind so the caller can
        subtract it directly.
        """
        grad_p = torch.roll(p, shifts=-1, dims=1) - p
        v_Q = -PHI_INV * grad_p
        v_Q = v_Q.clamp(-1.0, 1.0)
        Q_spatial = Q_transport.mean(dim=-1, keepdim=True)
        v_Q = v_Q.unsqueeze(-1)
        Q_left = torch.roll(Q_spatial, shifts=1, dims=1)
        Q_right = torch.roll(Q_spatial, shifts=-1, dims=1)
        upwind = torch.where(v_Q > 0, Q_spatial - Q_left, Q_right - Q_spatial)
        advection = v_Q * upwind
        return advection, v_Q.squeeze(-1)

    def qi_step(self, psi_real, psi_imag, P_re, P_im, Q_transport):
        eps2 = self._complex_norm2(psi_real - P_re, psi_imag - P_im)
        psi2 = self._complex_norm2(psi_real, psi_imag)
        eps0_sq = F.softplus(self.qi_eps0_log) + 1e-6
        source = (PHI_INV ** 2) * torch.tanh(eps2 / eps0_sq) * psi2
        sink = self.sink_gamma * Q_transport

        p = eps2.mean(dim=-1, keepdim=True).squeeze(-1)
        advection, v_Q = self._advect(Q_transport, p)
        Q_new = self.qi_rho * Q_transport + source - sink - advection
        return Q_new.clamp(min=0.0), p

    # ═══════════════════ Structural self-regulation ═══════════════════

    def structural_self_reg(self, Q_mean, m_self, breath):
        q_norm = Q_mean / PHI_INV
        excess = F.relu(q_norm - PHI_INV)
        calm = PHI_INV / (PHI_INV + excess)
        deficit = F.relu(PHI_INV - q_norm)
        arousal = (1.0 + 2.0 * deficit / PHI_INV).clamp(1.0, 3.0)
        self_reg = calm * arousal
        yin = breath['yin']
        calm_breath = 1.0 + 0.15 * (yin - PHI_INV)
        self_reg = (self_reg * calm_breath).clamp(PHI_INV ** 2, 3.0)
        m = m_self.mean() if m_self.numel() > 1 else m_self
        return self_reg * m.clamp(0.5, 2.0)

    def _field_step_pre_ctrl(self, h1, h2, psi_real, psi_imag, Q_field, breath):
        """IIR, pattern-memory read, prediction, and Qi update.

        Called from field_step; may be wrapped in gradient checkpointing.
        Does NOT mutate persistent buffers.
        """
        B = psi_real.shape[0]

        # φ-damped IIR (out-of-place, vectorized over d)
        h1_seq = h1[:B]
        h2_seq = h2[:B]
        theta_sig_full = torch.sigmoid(self.theta)[self.chakra_id]
        a1_full = 2.0 * PHI_INV * torch.cos(theta_sig_full)
        a2_full = -(PHI_INV ** 2)
        # Per-sample input mean so each sequence's IIR tracks its own history.
        inp_re = psi_real.mean(dim=1, keepdim=True)
        inp_im = psi_imag.mean(dim=1, keepdim=True)
        h1_new = a1_full * h1_seq + a2_full * h2_seq + inp_re
        h1_new_im = a1_full * h1_seq + a2_full * h2_seq + inp_im
        psi_real = psi_real + h1_new
        psi_imag = psi_imag + h1_new_im
        h1_next = h1_new
        h2_next = h1_seq

        # Pattern-memory read (before prediction so residuals shape ψ)
        query = F.layer_norm(psi_real, psi_real.shape[-1:])
        Q_for_pm = Q_field.mean(dim=-1)  # [B, N]
        pm_real, pm_imag, pm_diag = self.pattern_memory(query, Q_for_pm)
        psi_real = psi_real + pm_real
        psi_imag = psi_imag + pm_imag

        # Prediction operator
        P_re, P_im, eps2 = self.predict(psi_real, psi_imag)

        # Update Qi field
        Q_field, p = self.qi_step(psi_real, psi_imag, P_re, P_im, Q_field)

        return psi_real, psi_imag, Q_field, P_re, P_im, h1_next, h2_next, p.mean(), pm_diag

    def _field_step_transform(self, psi_real, psi_imag, Q_field, P_re, P_im, breath, ctrl):
        """Controller-driven transformations and normalization.

        Called from field_step; may be wrapped in gradient checkpointing.
        Does NOT mutate persistent buffers.
        """
        B = psi_real.shape[0]
        device = psi_real.device
        yang = breath['yang'].expand(B, 1, 1)
        yin = breath['yin'].expand(B, 1, 1)

        if ctrl is not None:
            alpha_ctrl = ctrl.alpha.view(B, 1, 1).clamp(0.5, 2.0)
            gamma_ctrl = ctrl.gamma.view(B, 1, 1).clamp(0.5, 2.0)
            rho_ctrl = ctrl.rho.view(B, 1, 1).clamp(0.5, 2.0)
            m_self = ctrl.m_self.clamp(0.5, 2.0)
        else:
            alpha_ctrl = gamma_ctrl = rho_ctrl = torch.ones(B, 1, 1, device=device)
            m_self = torch.ones(B, device=device)

        q_mean = Q_field.mean()
        self_reg_factor = self.structural_self_reg(q_mean, m_self, breath)

        # Breath-modulated prediction feedback
        alpha_breath = 1.0 + 0.5 * yang
        alpha = PHI_INV * alpha_breath * alpha_ctrl * self_reg_factor
        psi_real = psi_real + alpha * P_re
        psi_imag = psi_imag + alpha * P_im

        # Yin↔Yang structural coupling
        rho = (PHI_INV * rho_ctrl * self_reg_factor).clamp(max=0.90)
        psi_real_new = psi_real - rho * psi_imag
        psi_imag_new = psi_imag + rho * psi_real
        psi_real, psi_imag = psi_real_new, psi_imag_new

        # Glial homeostasis
        gain = self.glial.gain * gamma_ctrl.clamp(0.5, 2.0)
        energy = self._complex_norm2(psi_real, psi_imag).mean(dim=-1, keepdim=True)
        excess = F.relu(energy - self.glial.target_energy)
        factor = (1.0 - gain * excess).clamp(0.0, 1.0)
        psi_real = psi_real * factor
        psi_imag = psi_imag * factor

        # Breath quadrature rotation
        phase = 0.1 * (yin - PHI_INV)
        psi_real, psi_imag = self._rotate_complex(psi_real, psi_imag, phase)

        # Complex RMSNorm
        psi_real, psi_imag = self._complex_rmsnorm(psi_real, psi_imag)

        return psi_real, psi_imag, Q_field, q_mean, self_reg_factor

    # ═══════════════════ Field step ═══════════════════

    def field_step(self, psi_real, psi_imag, Q_field, breath,
                   ctrl: Optional[CtrlOutputs] = None,
                   state_indices: Optional[torch.Tensor] = None):
        B = psi_real.shape[0]
        device = psi_real.device
        if state_indices is not None:
            state_indices = state_indices.long().view(-1).to(device)

        # Core computation #1: IIR through Qi update.  Clone the persistent IIR
        # buffers before passing them in so the in-place .copy_() updates below
        # do not invalidate views saved for theta gradients, and so gradient
        # checkpointing (if used later) sees the correct previous-step state.
        if state_indices is not None:
            if self.state_bank_size <= 0:
                raise ValueError("state_indices provided but state_bank_size is 0")
            h1_in = self.h1_bank[state_indices].detach().clone()
            h2_in = self.h2_bank[state_indices].detach().clone()
        else:
            h1_in = self.h1[:B].detach().clone()
            h2_in = self.h2[:B].detach().clone()
        (psi_real, psi_imag, Q_field, P_re, P_im,
         h1_next, h2_next, p_mean, pm_diag) = self._field_step_pre_ctrl(
            h1_in, h2_in, psi_real, psi_imag, Q_field, breath)

        # Update IIR persistent state.  h2 must be copied before h1.
        if state_indices is not None:
            if self.training:
                self.h2_bank.index_copy_(0, state_indices, h2_next.detach())
                self.h1_bank.index_copy_(0, state_indices, h1_next.detach())
        else:
            self.h2[:B].copy_(h2_next.detach())
            self.h1[:B].copy_(h1_next.detach())

        # Running per-position Qi average for pattern growth.
        self.Q_bar_pos.copy_(0.99 * self.Q_bar_pos + 0.01 * Q_field.mean(dim=(0, 2)))

        # Neurogenesis / dissolution (training only)
        n_new = 0
        n_dissolved = 0
        if self.training:
            query = F.layer_norm(psi_real, psi_real.shape[-1:])
            n_new = self.pattern_memory.grow(query, self.Q_bar_pos,
                                             current_step=self.pattern_step.item())
            if self.pattern_step % 100 == 0:
                n_dissolved = self.pattern_memory.dissolve(current_step=self.pattern_step.item())
            self.pattern_step.add_(1)

        pm_diag['pm_new_neurons'] = n_new
        pm_diag['pm_dissolved'] = n_dissolved

        # Controller: kept outside the checkpointed region because its forward
        # mutates the persistent recurrent buffer self.controller.h_ctrl.
        if ctrl is None and self.controller is not None:
            q_per_chakra = self._qi_per_chakra(Q_field)
            q_trend = self.Q_trend.to(device).expand(B)
            yz_ratio = self._yang_yin_ratio(psi_real, psi_imag)
            field_energy = self._complex_norm2(psi_real, psi_imag).mean(dim=(1, 2))
            ctrl = self.controller(q_per_chakra,
                                   q_trend=q_trend,
                                   y_over_z_ratio=yz_ratio,
                                   field_energy=field_energy,
                                   breath=breath)

        if ctrl is not None:
            perturb_ctrl = ctrl.perturb.view(B, 1, 1).clamp(0.0, 0.1)
        else:
            perturb_ctrl = torch.zeros(B, 1, 1, device=device)

        # Core computation #2: controller-driven transformations.
        if self.use_checkpoint and self.training:
            psi_real, psi_imag, Q_field, q_mean, self_reg_factor = torch.utils.checkpoint.checkpoint(
                self._field_step_transform,
                psi_real, psi_imag, Q_field, P_re, P_im, breath, ctrl,
                use_reentrant=False,
            )
        else:
            psi_real, psi_imag, Q_field, q_mean, self_reg_factor = self._field_step_transform(
                psi_real, psi_imag, Q_field, P_re, P_im, breath, ctrl)

        # Low-Q arousal perturbation (kept outside checkpoint so the same
        # random noise is not regenerated during the backward recomputation).
        if self.training and q_mean < PHI_INV / 2.0:
            psi_real = psi_real + perturb_ctrl * torch.randn_like(psi_real)
            psi_imag = psi_imag + perturb_ctrl * torch.randn_like(psi_imag)

        # Diagnostic EMAs
        with torch.no_grad():
            self.Q_ema.copy_(0.99 * self.Q_ema + 0.01 * q_mean)
            self.Q_trend.copy_(self.Q_ema - q_mean)

        diagnostics = {'Q_mean': q_mean, 'Q_max': Q_field.max(), 'p_mean': p_mean,
                       'self_reg': self_reg_factor}
        if pm_diag:
            diagnostics.update(pm_diag)
        if ctrl is not None:
            diagnostics.update(ctrl.diagnostics)
        return psi_real, psi_imag, Q_field, diagnostics

    def _qi_per_chakra(self, Q_field):
        B, N, d = Q_field.shape
        # [d, B*N]: each column is one (batch, position) pair, rows are d features.
        flat = Q_field.permute(2, 0, 1).reshape(d, -1)
        lengths = torch.tensor(self.chakra_widths, device=Q_field.device, dtype=torch.int64)
        # [C, B*N]: per-chakra mean across the d dimension for each (b, n).
        per_c = torch.segment_reduce(flat, 'mean', lengths=lengths)
        # Average over positions N to match the original mean(dim=(1, 2)).
        return per_c.transpose(0, 1).view(B, N, self.C).mean(dim=1)

    def _yang_yin_ratio(self, psi_real, psi_imag):
        y = psi_real.pow(2).mean(dim=(1, 2))
        z = psi_imag.pow(2).mean(dim=(1, 2)).clamp_min(1e-12)
        return y / z

    # ═══════════════════ Public API ═══════════════════

    def reset_state(self):
        """Clear all persistent field state."""
        self.psi_real = torch.zeros_like(self.psi_real)
        self.psi_imag = torch.zeros_like(self.psi_imag)
        self.Q_field = torch.zeros_like(self.Q_field)
        self.h1 = torch.zeros_like(self.h1)
        self.h2 = torch.zeros_like(self.h2)
        if self.state_bank_size > 0:
            self.h1_bank.zero_()
            self.h2_bank.zero_()
        self.Q_ema = torch.zeros_like(self.Q_ema)
        self.Q_trend = torch.zeros_like(self.Q_trend)
        if self.controller is not None:
            self.controller.reset_state()
        self.breath.reset()
        self.pattern_memory.qi_ema.zero_()

    def embed(self, x):
        if self.continuous_mode:
            # x: [B, N, input_dim] float -> [B, N, d]
            proj = self.input_proj(x)
            return proj + self.pos_enc_real, proj + self.pos_enc_imag
        else:
            emb = self.token_embed(x)
            if self.multi_scale_bytes and self.multi_scale_embedder is not None:
                emb = emb + self.multi_scale_embedder(x)
            return emb + self.pos_enc_real, self.imag_proj(emb) + self.pos_enc_imag

    def readout(self, psi_real, psi_imag):
        """Pooled readout: logits [B, V] in byte mode, vectors [B, output_dim] in continuous mode."""
        y = psi_real.mean(dim=1)
        z = psi_imag.mean(dim=1)
        y = F.layer_norm(y, y.shape[-1:])
        z = F.layer_norm(z, z.shape[-1:])
        if self.continuous_mode:
            return self.output_proj(y + z)
        return self.readout_y(y) + self.readout_z(z)

    def readout_positions(self, psi_real, psi_imag):
        """Per-position readout: logits [B, N, V] in byte mode, vectors [B, N, output_dim] in continuous mode."""
        y = F.layer_norm(psi_real, psi_real.shape[-1:])
        z = F.layer_norm(psi_imag, psi_imag.shape[-1:])
        if self.continuous_mode:
            return self.output_proj(y + z)
        return self.readout_y(y) + self.readout_z(z)


    def forward(self, x, sigma=None,
               state_indices: Optional[torch.Tensor] = None,
               no_reset: bool = False):
        B = x.shape[0]
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
                    t.h_real = t.h_real[:1].expand(B, -1).clone()
                    t.h_imag = t.h_imag[:1].expand(B, -1).clone()
                    t.h_prev_real = t.h_prev_real[:1].expand(B, -1).clone()
                    t.h_prev_imag = t.h_prev_imag[:1].expand(B, -1).clone()
                    t.x_prev_real = t.x_prev_real[:1].expand(B, -1).clone()
                    t.x_prev_imag = t.x_prev_imag[:1].expand(B, -1).clone()

        psi_real, psi_imag = self.embed(x)
        Q_field = self.Q_field.expand(B, -1, -1).clone()

        all_diag = {}
        for _ in range(self.K_train):
            breath = self.breath.step()
            psi_real, psi_imag, Q_field, diag = self.field_step(
                psi_real, psi_imag, Q_field, breath,
                state_indices=state_indices)
            for key, val in diag.items():
                if isinstance(val, torch.Tensor) and val.numel() > 1:
                    # Variable-shape tensors (e.g. p_k) are kept from the last step only.
                    all_diag[key] = val
                else:
                    all_diag[key] = all_diag.get(key, 0.0) + val

        for key in list(all_diag.keys()):
            val = all_diag[key]
            if not (isinstance(val, torch.Tensor) and val.numel() > 1):
                all_diag[key] = val / self.K_train
        # Convert scalar tensors to Python scalars for logging.
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, torch.Tensor) and val.ndim == 0:
                all_diag[key] = val.item()

        logits = self.readout(psi_real, psi_imag)
    def training_loss(self, x, y=None,
                      state_indices: Optional[torch.Tensor] = None,
                      no_reset: bool = False):
        if self.continuous_mode:
            return self._training_loss_continuous(x, y, state_indices=state_indices,
                                                  no_reset=no_reset)

        B, N = x.shape
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
            # no_reset: resize transceiver buffers if batch size changed,
            # but preserve existing state values where possible.
            for t in self.transceivers:
                if t.h_real.shape[0] != B:
                    dev = t.h_real.device
                    t.h_real = t.h_real[:1].expand(B, -1).clone()
                    t.h_imag = t.h_imag[:1].expand(B, -1).clone()
                    t.h_prev_real = t.h_prev_real[:1].expand(B, -1).clone()
                    t.h_prev_imag = t.h_prev_imag[:1].expand(B, -1).clone()
                    t.x_prev_real = t.x_prev_real[:1].expand(B, -1).clone()
                    t.x_prev_imag = t.x_prev_imag[:1].expand(B, -1).clone()

        context_len = max(1, N - self.span_len)
        if self.span_len >= N:
            context_len = N // 2
        context = x[:, :context_len]
        target = x[:, context_len:]

        # Pad context to length N so embeddings align with position encodings.
        if context.shape[1] < N:
            pad = torch.zeros(B, N - context_len, dtype=torch.long, device=device)
            context = torch.cat([context, pad], dim=1)

        psi_real, psi_imag = self.embed(context)
        Q_field = self.Q_field.expand(B, -1, -1).clone()

        all_diag = {}
        ctrl_losses = []
        last_pm_diag = {}
        for _ in range(self.K_train):
            breath = self.breath.step()
            psi_real, psi_imag, Q_field, diag = self.field_step(
                psi_real, psi_imag, Q_field, breath,
                state_indices=state_indices)
            for key, val in diag.items():
                if isinstance(val, torch.Tensor) and val.numel() > 1:
                    # Variable-shape tensors (e.g. p_k) are kept from the last step only.
                    all_diag[key] = val
                else:
                    all_diag[key] = all_diag.get(key, 0.0) + val
            last_pm_diag = {k: v for k, v in diag.items() if k.startswith('pm_')}
            if self.controller is not None and self.lambda_homeo > 0:
                ctrl_losses.append(self.controller.compute_homeo_loss(
                    diag['Q_mean'], weight=self.lambda_homeo))

        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, (int, float)) or (isinstance(val, torch.Tensor) and val.numel() == 1):
                all_diag[key] = val / self.K_train
        # Convert scalar tensors to Python scalars for logging.
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, torch.Tensor) and val.ndim == 0:
                all_diag[key] = val.item()

        logits = self.readout_positions(psi_real, psi_imag)  # [B, N, V]
        ce_loss = F.cross_entropy(logits[:, context_len:, :].reshape(-1, self.V),
                                  target.reshape(-1))

        # Pattern-utilization auxiliary losses (use last field-step diagnostics).
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
        if ctrl_losses:
            homeo_loss = torch.stack(ctrl_losses).mean()
            loss = loss + homeo_loss
            all_diag['homeo_loss'] = homeo_loss.item()

        all_diag['ce_loss'] = ce_loss.item()
        all_diag['pattern_div_loss'] = pattern_div_loss.item()
        all_diag['pattern_commit_loss'] = pattern_commit_loss.item()
        all_diag['pattern_util_loss'] = pattern_util_loss.item()
        all_diag['loss'] = loss.item()
        all_diag['ctrl_aux_loss'] = all_diag.get('homeo_loss', 0.0)
        all_diag['ctrl_alpha'] = all_diag.get('ctrl_alpha', 1.0)
        all_diag['ctrl_beta'] = all_diag.get('ctrl_beta', 0.0)
        all_diag['ctrl_delta'] = all_diag.get('ctrl_delta', 0.0)
        return loss, all_diag

    def _training_loss_continuous(self, x, y,
                                  state_indices: Optional[torch.Tensor] = None,
                                  no_reset: bool = False):
        """MSE regression loss for continuous-field inputs.

        Args:
            x: [B, N, input_dim] float input frames.
            y: [B, output_dim] float target frame.
            state_indices: optional keyed IIR bank indices [B].
            no_reset: if True, preserve field state across calls.
        Returns:
            (loss, diagnostics) with loss scalar and diagnostics dict.
        """
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
                    t.h_real = t.h_real[:1].expand(B, -1).clone()
                    t.h_imag = t.h_imag[:1].expand(B, -1).clone()
                    t.h_prev_real = t.h_prev_real[:1].expand(B, -1).clone()
                    t.h_prev_imag = t.h_prev_imag[:1].expand(B, -1).clone()
                    t.x_prev_real = t.x_prev_real[:1].expand(B, -1).clone()
                    t.x_prev_imag = t.x_prev_imag[:1].expand(B, -1).clone()

        psi_real, psi_imag = self.embed(x)
        Q_field = self.Q_field.expand(B, -1, -1).clone()

        all_diag = {}
        ctrl_losses = []
        for _ in range(self.K_train):
            breath = self.breath.step()
            psi_real, psi_imag, Q_field, diag = self.field_step(
                psi_real, psi_imag, Q_field, breath,
                state_indices=state_indices)
            for key, val in diag.items():
                if isinstance(val, torch.Tensor) and val.numel() > 1:
                    # Variable-shape tensors are kept from the last step only.
                    all_diag[key] = val
                else:
                    all_diag[key] = all_diag.get(key, 0.0) + val
            if self.controller is not None and self.lambda_homeo > 0:
                ctrl_losses.append(self.controller.compute_homeo_loss(
                    diag['Q_mean'], weight=self.lambda_homeo))

        for key in list(all_diag.keys()):
            val = all_diag[key]
            if not (isinstance(val, torch.Tensor) and val.numel() > 1):
                all_diag[key] = val / self.K_train
        for key in list(all_diag.keys()):
            val = all_diag[key]
            if isinstance(val, torch.Tensor) and val.ndim == 0:
                all_diag[key] = val.item()

        pred = self.readout(psi_real, psi_imag)  # [B, output_dim]
        mse_loss = F.mse_loss(pred, y)
        with torch.no_grad():
            mae_loss = F.l1_loss(pred, y)

        loss = mse_loss
        if ctrl_losses:
            homeo_loss = torch.stack(ctrl_losses).mean()
            loss = loss + homeo_loss
            all_diag['homeo_loss'] = homeo_loss.item()

        all_diag['mse_loss'] = mse_loss.item()
        all_diag['mae_loss'] = mae_loss.item()
        all_diag['loss'] = loss.item()
        all_diag['Q_mean'] = all_diag.get('Q_mean', 0.0)
        all_diag['pm_active'] = all_diag.get('pm_active', 0)
        return loss, all_diag

    def _step_continuous(self, input_frames: torch.Tensor,
                         state_indices: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """Single-frame atomic field step for continuous inputs.

        Args:
            input_frames: [B, L, input_dim] float, with B == 1 and L <= self.N.
            state_indices: optional keyed IIR bank indices [B].
        Returns:
            (pred, diagnostics) where pred has shape [B, output_dim].
        """
        if input_frames.dim() == 2:
            input_frames = input_frames.unsqueeze(0)
        B, L, _ = input_frames.shape
        if B != 1:
            raise ValueError(f"step() only supports batch size 1; got {B}")
        device = input_frames.device
        if L > self.N:
            input_frames = input_frames[:, -self.N:]
            L = self.N

        # Right-align: pad on the left so the last input frame maps to position N-1.
        if L < self.N:
            pad = torch.zeros(B, self.N - L, self.input_dim, device=device)
            full_frames = torch.cat([pad, input_frames], dim=1)
        else:
            full_frames = input_frames

        psi_real = self.psi_real.expand(B, -1, -1).clone()
        psi_imag = self.psi_imag.expand(B, -1, -1).clone()
        Q_field = self.Q_field.expand(B, -1, -1).clone()

        emb_real, emb_imag = self.embed(full_frames)
        psi_real[:, -L:, :] = emb_real[:, -L:, :]
        psi_imag[:, -L:, :] = emb_imag[:, -L:, :]

        breath = self.breath.step()
        psi_real, psi_imag, Q_field, diag = self.field_step(
            psi_real, psi_imag, Q_field, breath,
            state_indices=state_indices)

        self.psi_real.copy_(psi_real.detach())
        self.psi_imag.copy_(psi_imag.detach())
        self.Q_field.copy_(Q_field.detach())

        pred = self.readout_positions(psi_real, psi_imag)[:, -1, :]  # [B, output_dim]
        return pred, diag
    def step(self, input_ids: torch.Tensor,
             state_indices: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, Dict[str, Any]]:
        """Single-token (or short-span) atomic field step.

        The persistent field state is right-aligned: the rightmost token in
        `input_ids` is placed at position N-1 (the newest position, matching
        training where position 0 is oldest and position N-1 is newest). The
        readout therefore returns logits/vectors for position N-1.

        Args:
            input_ids: [B, L] in byte mode, [B, L, input_dim] in continuous mode,
                with B == 1 and L <= self.N. Embeddings are assigned (not added)
                to the persistent field state at positions N-L:N-1, one field step
                is run, and logits/vectors for position N-1 are returned.
            state_indices: optional keyed IIR bank indices [B].

        Returns:
            (logits/pred, diagnostics) where logits has shape [B, V] in byte mode
            and pred has shape [B, output_dim] in continuous mode.
        """
        if self.continuous_mode:
            return self._step_continuous(input_ids, state_indices=state_indices)

        if input_ids.dim() == 1:
            input_ids = input_ids.unsqueeze(0)
        B, L = input_ids.shape
        if B != 1:
            raise ValueError(f"step() only supports batch size 1; got {B}")
        device = input_ids.device
        if L > self.N:
            input_ids = input_ids[:, -self.N:]
            L = self.N

        # Right-align: pad on the left so the last input token maps to position N-1.
        if L < self.N:
            pad = torch.zeros(B, self.N - L, dtype=torch.long, device=device)
            full_ids = torch.cat([pad, input_ids], dim=1)
        else:
            full_ids = input_ids

        # Ensure persistent buffers match batch size (B == 1).
        # Persistent buffers are cloned before the in-place slice assignment
        # below; removing .clone() would alias the buffer and corrupt the
        # autograd graph if step() is ever called with gradients enabled.
        psi_real = self.psi_real.expand(B, -1, -1).clone()
        psi_imag = self.psi_imag.expand(B, -1, -1).clone()
        Q_field = self.Q_field.expand(B, -1, -1).clone()

        emb_real, emb_imag = self.embed(full_ids)
        # Assign current input as the field content for these positions.
        psi_real[:, -L:, :] = emb_real[:, -L:, :]
        psi_imag[:, -L:, :] = emb_imag[:, -L:, :]

        breath = self.breath.step()
        psi_real, psi_imag, Q_field, diag = self.field_step(
            psi_real, psi_imag, Q_field, breath,
            state_indices=state_indices)

        # Persist state for single-batch generation.
        self.psi_real.copy_(psi_real.detach())
        self.psi_imag.copy_(psi_imag.detach())
        self.Q_field.copy_(Q_field.detach())

        logits = self.readout_positions(psi_real, psi_imag)[:, -1, :]
        return logits, diag

    @torch.no_grad()
    def generate_rollout(self, seed: torch.Tensor, max_new: int = 1,
                         K_init: Optional[int] = None,
                         state_indices: Optional[torch.Tensor] = None) -> torch.Tensor:
        """Autoregressively rollout continuous frames from a seed.

        Args:
            seed: [B, seed_len, input_dim] float frames on the model's device.
            max_new: Number of frames to predict.
            K_init: Number of settling steps on the seed (default self.K_gen).
            state_indices: optional keyed IIR bank indices [B].
        Returns:
            [B, max_new, output_dim] predicted frames.
        """
        if K_init is None:
            K_init = self.K_gen
        if seed.dim() == 2:
            seed = seed.unsqueeze(0)
        B, _, _ = seed.shape
        device = seed.device
        self.eval()

        generated = []
        for b in range(B):
            idx = None
            if state_indices is not None:
                if self.state_bank_size <= 0:
                    raise ValueError("state_indices provided but state_bank_size is 0")
                idx = state_indices[b:b + 1]
            else:
                self.reset_state()
                for t in self.transceivers:
                    t.reset_state(1, device)

            window = seed[b:b + 1]  # [1, seed_len, input_dim]
            for _ in range(K_init):
                _, _ = self._step_continuous(window, state_indices=idx)

            preds = []
            for _ in range(max_new):
                # Use the last seed/predicted frame as the next input.
                next_input = window[:, -1:, :]
                pred, _ = self._step_continuous(next_input, state_indices=idx)
                preds.append(pred)
                window = torch.cat([window, pred.unsqueeze(1)], dim=1)
                if window.shape[1] > self.N:
                    window = window[:, -self.N:]
            generated.append(torch.stack(preds, dim=1))  # [1, max_new, output_dim]

        return torch.cat(generated, dim=0)

    def generate_autoregressive(self, seed: torch.Tensor, max_new: int = 128,
                                temp: float = 0.8, K_init: Optional[int] = None,
                                repetition_penalty: float = 1.2,
                                rep_window: int = 8,
                                top_k: Optional[int] = None,
                                ngram_block_size: int = 0) -> torch.Tensor:
        """Autoregressively generate a byte sequence from a seed.

        Args:
            seed: [seed_len] byte ids on the model's device.
            max_new: Number of new bytes to generate.
            temp: Sampling temperature.
            K_init: Number of settling steps on the seed (default self.K_gen).
            repetition_penalty: Divide logits for recently generated bytes.
            rep_window: Number of recent bytes to penalize.
            top_k: If given, keep only the top-k logits (0/None = disabled).
            ngram_block_size: If > 0, block tokens that would repeat an n-gram
                within the last `rep_window` generated bytes.
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

        seed_batch = seed.unsqueeze(0)
        for _ in range(K_init):
            _, _ = self.step(seed_batch)

        window = seed.clone()
        generated = []
        for _ in range(max_new):
            logits, _ = self.step(window[-1:].unsqueeze(0))
            logits = logits.squeeze(0) / max(temp, 1e-6)

            # Repetition penalty on the last `rep_window` generated bytes.
            if generated and repetition_penalty != 1.0:
                recent = set(generated[-rep_window:])
                for b in recent:
                    logits[b] /= repetition_penalty

            # N-gram blocking: prevent completing a repeated n-gram.
            if ngram_block_size > 0 and len(generated) >= ngram_block_size - 1:
                recent = generated[-rep_window:]
                prefix = generated[-(ngram_block_size - 1):] if ngram_block_size > 1 else []
                for t in range(self.V):
                    ngram = tuple(prefix + [t])
                    blocked = False
                    for i in range(len(recent) - ngram_block_size + 1):
                        if tuple(recent[i:i + ngram_block_size]) == ngram:
                            blocked = True
                            break
                    if blocked:
                        logits[t] = -float('inf')

            # Top-k filtering.
            if top_k is not None and top_k > 0:
                k = min(top_k, self.V)
                v, _ = torch.topk(logits, k)
                logits[logits < v[-1]] = -float('inf')

            probs = F.softmax(logits, dim=-1)
            next_byte = torch.multinomial(probs, num_samples=1).item()
            generated.append(next_byte)

            if window.numel() < self.N:
                window = torch.cat([window, torch.tensor([next_byte], device=device)])
            else:
                window = torch.cat([window[1:], torch.tensor([next_byte], device=device)])

        return torch.tensor(generated, dtype=torch.long, device=device)

    @torch.no_grad()
    def generate(self, seq_len: int = 128, temp: float = 0.8,
                 K: Optional[int] = None, device: Optional[torch.device] = None):
        """Legacy wrapper around autoregressive generation."""
        if device is None:
            device = self.psi_real.device
        seed_len = max(1, self.N // 8)
        seed = torch.randint(0, self.V, (seed_len,), device=device)
        return self.generate_autoregressive(seed, max_new=seq_len, temp=temp,
                                            K_init=K)


# Backward-compatible alias
QiFieldV2 = QiField
if __name__ == '__main__':
    import os, sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    import torch
    m = QiField(N=4, d=64, continuous_mode=True, input_dim=1024, output_dim=1024)
    x = torch.randn(2, 4, 1024)
    y = torch.randn(2, 1024)
    loss, info = m.training_loss(x, y)
    assert torch.isfinite(loss), f'non-finite loss: {loss}'
    loss.backward()
    for name, p in m.named_parameters():
        if p.grad is not None:
            assert torch.isfinite(p.grad).all(), f'non-finite grad in {name}'
    # Byte mode sanity check.
    m2 = QiField(N=8, d=64)
    x2 = torch.randint(0, 256, (2, 8))
    loss2, info2 = m2.training_loss(x2)
    assert torch.isfinite(loss2), f'non-finite byte loss: {loss2}'
    # Keyed state-bank persistence sanity check.
    m3 = QiField(N=4, d=64, continuous_mode=True, input_dim=1024,
                 output_dim=1024, state_bank_size=100)
    x_a = torch.randn(1, 4, 1024)
    y_a = torch.randn(1, 1024)
    x_b = torch.randn(1, 4, 1024)
    y_b = torch.randn(1, 1024)
    loss_a, _ = m3.training_loss(x_a, y_a, state_indices=torch.tensor([0]))
    bank_after_a = m3.h1_bank[0].clone()
    loss_b, _ = m3.training_loss(x_b, y_b, state_indices=torch.tensor([1]))
    bank_after_b = m3.h1_bank[1].clone()
    assert torch.isfinite(loss_a) and torch.isfinite(loss_b)
    assert not torch.allclose(bank_after_a, bank_after_b), \
        "keyed state bank entries should differ after different inputs"
    # Index 0 should retain its state, not be overwritten by index 1.
    assert torch.allclose(m3.h1_bank[0], bank_after_a), \
        "keyed state bank entry 0 was corrupted by writing entry 1"
    print('QiField smoke tests passed.')
