"""QiField — Complex self-predicting Qi wave field.

The field ψ ∈ ℂ^(B×N×d) is stored as real/imag pairs.  Yang = Re(ψ),
Yin = Im(ψ), and Qi evolves via the continuity equation (recurrent source-sink dynamics with saturating source, super-linear sink, and pressure-gradient advection) in QiDynamics.  Formally: Q_{t+1} = ρ·Q_t + φ⁻²·tanh(ε²/ε₀²)·ψ² − γ·Q_t − ∇·(Q·v_Q).  Diagnostics track Q_mean and Q_max.

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
from cassi._chakra_utils import phi_chakra_widths, chakra_offsets, chakra_id_tensor
from cassi._chakra_iir import ChakraIIRBank
from cassi._field_state import FieldState
from cassi._field_modules import PredictionOperator, QiDynamics, ControllerModulation


class QiField(nn.Module):
    """Complex QiField with transceiver prediction and persistent Qi dynamics.

    The model uses a φ-damped IIR field per chakra (via the transceivers)
    with cross-chakra mixing. No classical MLP is present in the architecture.
    """
    def __init__(self, N: int = 128, d: int = 128, C: int = 13, V: int = 256,
                 K_train: int = 5, K_gen: int = 50, M: int = 2048,
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
                 max_batch_size: int = 256,
    ):
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
        self.qi_rho = qi_rho   # stored for reference; actual Parameter lives on qi_dynamics
        self.sink_gamma = sink_gamma
        self.initial_qi_rho = qi_rho   # saved for QiDynamics post-init
        self.initial_sink_gamma = sink_gamma
        self.use_fused_kernels = use_fused_kernels
        self.use_checkpoint = use_checkpoint
        self.span_len = span_len
        self.lambda_pattern_div = lambda_pattern_div
        self.lambda_pattern_commit = lambda_pattern_commit
        self.lambda_pattern_util = lambda_pattern_util

        self.input_dim = input_dim
        self.output_dim = output_dim
        self.continuous_mode = continuous_mode
        # φ-scaled chakra widths (canonical: _chakra_utils.phi_chakra_widths)
        widths = phi_chakra_widths(d, C)
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
        # Separate IIR state for the imaginary part — the real and imaginary
        # components of the complex field have independent temporal memory
        # (per the formalism's complex field representation).
        self.register_buffer('h1_im', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h2_im', torch.zeros(max_batch_size, N, d))

        # Optional keyed per-sample IIR state bank.
        self.state_bank_size = state_bank_size
        if state_bank_size > 0:
            self.register_buffer('h1_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h2_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h1_im_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h2_im_bank', torch.zeros(state_bank_size, N, d))

        offsets_list = chakra_offsets(self.chakra_widths)
        self.register_buffer('chakra_offsets', offsets_list, persistent=False)
        # IIR bank (owns per-chakra theta, chakra_id mapping)
        self.iir_bank = ChakraIIRBank(d=d, C=C, widths=self.chakra_widths)
        # Prediction operator (owns transceivers, cross_chakra)
        self.prediction = PredictionOperator(
            d=d, C=C, widths=self.chakra_widths, N=N,
        )
        # (No self.residuals alias — the residual MLP has been removed.)
        self.transceivers = self.prediction.transceivers
        self.cross_chakra = self.prediction.cross_chakra

        # Qi dynamics (owns qi_eps0_log, sink_gamma, qi_rho)
        self.qi_dynamics = QiDynamics(d=d, qi_rho=self.initial_qi_rho, sink_gamma=self.initial_sink_gamma)
        self.qi_eps0_log = self.qi_dynamics.qi_eps0_log      # alias for backward compat
        self.sink_gamma = self.qi_dynamics.sink_gamma          # alias for backward compat
        self.qi_rho = self.qi_dynamics.qi_rho                  # alias for backward compat

        # Controller modulation (owns glial, field_scale)
        self.ctrl_mod = ControllerModulation(d=d, has_glial=(homeo_gain > 0), glial_gain=homeo_gain)
        self.glial = self.ctrl_mod.glial if hasattr(self.ctrl_mod, 'glial') else None
        self.field_scale = self.ctrl_mod.field_scale
        self.breath = Breath()


        # Controller
        if self_aware:
            self.controller = SelfAwarenessController(C=C, hidden_dim=ctrl_hidden_dim)
        else:
            self.controller = None
        # Backward-compat: external code (e.g., train_mind_brain.py) iterates
        # `model.residuals[c].parameters()`. The residual MLP has been removed
        # (classical ML is not allowed in the model architecture), so this
        # property returns an empty list of empty modules. Callers that try
        # to read .parameters() get nothing — the loop is a no-op.
        self._residuals_placeholder = nn.ModuleList()

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

    def _normalize_state_dict(self, state_dict, initialized_keys=None, verbose: bool = False):
        """Convert old checkpoints to the current architecture.

        Handles:
        - controller.prev_outputs buffer size change (30 -> 2*C+2)
        - removed controller.head_beta_legacy / head_delta_legacy weights
        - missing qi_eps0_log (new learnable source scale)
        - transceiver persistent buffers whose batch dim changed
        - pattern memory long-term buffers (usage, age, born, key_ema, etc.)
          whose max_neurons dim may have changed
        - pattern memory transient buffers (qi_ema) whose shape depends on N
        - dropped stale prediction.cord.*, cord.*, cord_pos_scale, cord_history
          keys from old checkpoints (cord path removed)
        """
        def _log(msg):
            if verbose:
                print(f'  [normalize] {msg}')

        # Remove stale alias keys that shadow submodule paths
        # (e.g., 'transceivers.X.Y' is an alias for 'prediction.transceivers.X.Y').
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
        # Migrate root-level qi_eps0_log → qi_dynamics.qi_eps0_log
        # (parameter moved into submodule during refactoring)
        if 'qi_eps0_log' in state_dict and 'qi_dynamics.qi_eps0_log' not in state_dict:
            state_dict['qi_dynamics.qi_eps0_log'] = state_dict.pop('qi_eps0_log')
            _log('migrated qi_eps0_log → qi_dynamics.qi_eps0_log')
        # Drop stale 'residuals.*' keys from old checkpoints — the residual
        # MLP has been removed (classical ML is not allowed). The keys are
        # not aliased anywhere in the current model.
        for key in list(state_dict.keys()):
            if key.startswith('residuals.') or key == 'residuals':
                del state_dict[key]
                if verbose:
                    print(f'  [normalize] dropped stale residuals key {key} (MLP removed)')
        # Drop stale 'prediction.cord.*', 'cord.*', 'cord_pos_scale', 'cord_history'
        # keys from old checkpoints — the cord path has been removed from
        # PredictionOperator. The keys are not aliased anywhere in the current model.
        n_cord_dropped = 0
        for key in list(state_dict.keys()):
            if key.startswith('prediction.cord.') or key == 'prediction.cord':
                del state_dict[key]
                n_cord_dropped += 1
            elif key.startswith('cord.') or key == 'cord':
                del state_dict[key]
                n_cord_dropped += 1
            elif key == 'cord_pos_scale' or key.startswith('cord_pos_scale.'):
                del state_dict[key]
                n_cord_dropped += 1
            elif key == 'cord_history' or key.startswith('cord_history.'):
                del state_dict[key]
                n_cord_dropped += 1
        if n_cord_dropped:
            _log(f'dropped {n_cord_dropped} stale cord key(s) (cord path removed)')
        # Resize transceiver persistent buffers to the current shape.
        # Handles both 'transceivers.' and 'prediction.transceivers.' prefixes.
        n_tx_resized = 0
        for key in list(state_dict.keys()):
            parts = key.split('.')
            if len(parts) >= 2 and parts[-1] in (
                'h_real', 'h_imag', 'h_prev_real', 'h_prev_imag', 'x_prev_real', 'x_prev_imag'
            ) and 'transceivers' in parts:
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

        # Resize per-sample IIR buffers h1/h2.
        for key in ('h1', 'h2'):
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

        # Resize keyed IIR state banks h1_bank/h2_bank.
        for key in ('h1_bank', 'h2_bank'):
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

        # Resize controller.prev_outputs if shape changed.
        new_shape = 2 * self.C + 2
        if 'controller.prev_outputs' in state_dict:
            old = state_dict['controller.prev_outputs']
            if old.shape != torch.Size([new_shape]):
                new = torch.zeros(new_shape, dtype=old.dtype, device=old.device)
                n = min(old.numel(), new.numel())
                new[:n] = old[:n]
                state_dict['controller.prev_outputs'] = new
                _log(f'resized controller.prev_outputs from {tuple(old.shape)} to ({new_shape},)')

        # Remove legacy controller heads that no longer exist.
        legacy_removed = 0
        for key in list(state_dict.keys()):
            if 'controller.head_beta_legacy' in key or 'controller.head_delta_legacy' in key:
                del state_dict[key]
                legacy_removed += 1
        if legacy_removed:
            _log(f'dropped {legacy_removed} legacy controller head(s)')

        # Pattern memory: resize long-term buffers, drop transient ones.
        from cassi.pattern_memory import QiPatternMemory
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

        # Resize pattern memory parameters (keys, values_real, values_imag)
        # whose shape depends on max_neurons.
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

        # Drop transient per-sequence PM buffers.
        for key in list(state_dict.keys()):
            if key == 'pattern_memory.qi_ema':
                param = self
                for part in key.split('.'):
                    param = getattr(param, part)
                if tuple(state_dict[key].shape) != tuple(param.shape):
                    del state_dict[key]
                    _log(f'dropped transient PM buffer {key} (shape mismatch)')

        # Initialize missing new parameters/buffers from defaults.
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
            _log(f'initialized {n_missing_params} missing param(s) and {n_missing_buffers} missing buffer(s) from defaults')

        return state_dict

    def load_state_dict(self, state_dict, strict=False, assign=False):
        initialized = set()
        state_dict = self._normalize_state_dict(state_dict, initialized_keys=initialized, verbose=True)
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

    def predict(self, psi_real, psi_imag, use_residual: bool = True):
        """Delegate to self.prediction. Returns (P_re, P_im, eps2)."""
        P_re, P_im, eps2, _ = self.prediction(
            psi_real, psi_imag,
            use_residual=use_residual,
        )
        return P_re, P_im, eps2

    def qi_step(self, psi_real, psi_imag, P_re, P_im, Q_transport):
        """Delegate to self.qi_dynamics. Returns (Q_new, p_mean)."""
        eps2 = self._complex_norm2(psi_real - P_re, psi_imag - P_im)
        Q_new, p_mean, _ = self.qi_dynamics(
            psi_real, psi_imag, Q_transport, P_re, P_im, eps2=eps2,
        )
        return Q_new, p_mean

    def structural_self_reg(self, Q_mean, m_self, breath):
        """Delegate to self.ctrl_mod.structural_self_reg."""
        yin = breath['yin']
        m = m_self.mean() if m_self.numel() > 1 else m_self
        return self.ctrl_mod.structural_self_reg(Q_mean, m, breath_yin=yin)

    def _field_step_pre_ctrl(self, h1, h2, h1_im, h2_im,
                             psi_real, psi_imag, Q_field, breath,
                             use_residual: bool = True):
        """IIR, pattern-memory read, prediction, and Qi update.

        The IIR is POSITION-FORM per the formalism section 2.1:
          psi[t+1] = a1 * psi[t] + a2 * psi[t-1] + S[t]
        The IIR REPLACES psi (does not add to it). The real and imaginary
        components have independent IIR state (h1/h2 for real, h1_im/h2_im
        for imaginary).

        Called from field_step; may be wrapped in gradient checkpointing.
        Does NOT mutate persistent buffers.
        """
        B = psi_real.shape[0]

        # phi-damped IIR — position-form (formalism section 2.1).
        # compute_coefficients broadcasts a1/a2 to [B, N, d] so each position
        # gets its own per-chakra coefficient (the ChakraIIRBank owns per-chakra theta).
        a1_full, a2_full = self.iir_bank.compute_coefficients(
            batch_shape=torch.Size([B, psi_real.shape[1]]),
            device=psi_real.device,
        )
        # External source: spatial mean of current field
        S_re = psi_real.mean(dim=1, keepdim=True)   # [B, 1, d]
        S_im = psi_imag.mean(dim=1, keepdim=True)   # [B, 1, d]
        # Position-form: IIR replaces psi, doesn't add to it
        h1_re_in = h1[:B]     # psi[t-1] for real part
        h1_im_in = h1_im[:B]  # psi[t-1] for imaginary part (independent)
        new_psi_re = a1_full * psi_real + a2_full * h1_re_in + S_re
        new_psi_im = a1_full * psi_imag + a2_full * h1_im_in + S_im
        # State update: h1 = psi[t], h2 = psi[t-1] (for next step)
        h1_re_next = psi_real
        h2_re_next = h1_re_in
        h1_im_next = psi_imag
        h2_im_next = h1_im_in
        psi_real, psi_imag = new_psi_re, new_psi_im

        # Pattern-memory read (before prediction so residuals shape psi)
        query = F.layer_norm(psi_real, psi_real.shape[-1:])
        Q_for_pm = Q_field.mean(dim=-1)  # [B, N]
        pm_real, pm_imag, pm_diag = self.pattern_memory(query, Q_for_pm)
        psi_real = psi_real + pm_real
        psi_imag = psi_imag + pm_imag

        # Prediction operator
        P_re, P_im, eps2 = self.predict(psi_real, psi_imag, use_residual=use_residual)

        # Update Qi field
        Q_field, p = self.qi_step(psi_real, psi_imag, P_re, P_im, Q_field)

        return (psi_real, psi_imag, Q_field, P_re, P_im,
                h1_re_next, h2_re_next, h1_im_next, h2_im_next,
                p.mean(), pm_diag)

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

    def _field_step_with_ctrl(self, psi_real, psi_imag, Q_field, P_re, P_im,
                              breath, q_per_chakra, q_trend, yz_ratio, field_energy,
                              ctrl_passed=None, prev_hidden=None):
        """Controller call + transform, combined for gradient checkpointing.

        Does NOT mutate self.controller.h_ctrl. The caller must call
        self.controller._update_h_ctrl(ctrl.h_next) after the checkpoint
        boundary to persist the new hidden state.

        When ctrl_passed is provided (from an external caller like the K_train
        loop), the controller is NOT recomputed — ctrl_passed is used directly.
        """
        B = psi_real.shape[0]
        device = psi_real.device
        if ctrl_passed is not None:
            ctrl = ctrl_passed
        elif self.controller is not None and q_per_chakra is not None:
            ctrl = self.controller(q_per_chakra,
                                   q_trend=q_trend,
                                   y_over_z_ratio=yz_ratio,
                                   field_energy=field_energy,
                                   breath=breath,
                                   prev_hidden=prev_hidden)
        else:
            ctrl = None
        if ctrl is not None:
            perturb_ctrl = ctrl.perturb.view(B, 1, 1).clamp(0.0, 0.1)
        else:
            perturb_ctrl = torch.zeros(B, 1, 1, device=device)
        psi_real, psi_imag, Q_field, q_mean, self_reg_factor = self._field_step_transform(
            psi_real, psi_imag, Q_field, P_re, P_im, breath, ctrl)
        return psi_real, psi_imag, Q_field, q_mean, self_reg_factor, ctrl, perturb_ctrl

    # ═══════════════════ Field step ═══════════════════

    def field_step(self, psi_real, psi_imag, Q_field, breath,
                   ctrl: Optional[CtrlOutputs] = None,
                   state_indices: Optional[torch.Tensor] = None,
                   use_residual: bool = True):
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
            h1_im_in = self.h1_im_bank[state_indices].detach().clone()
            h2_im_in = self.h2_im_bank[state_indices].detach().clone()
        else:
            h1_in = self.h1[:B].detach().clone()
            h2_in = self.h2[:B].detach().clone()
            h1_im_in = self.h1_im[:B].detach().clone()
            h2_im_in = self.h2_im[:B].detach().clone()
        (psi_real, psi_imag, Q_field, P_re, P_im,
         h1_re_next, h2_re_next, h1_im_next, h2_im_next,
         p_mean, pm_diag) = self._field_step_pre_ctrl(
            h1_in, h2_in, h1_im_in, h2_im_in,
            psi_real, psi_imag, Q_field, breath,
            use_residual=use_residual)

        # Update IIR persistent state. h2 must be copied before h1.
        if state_indices is not None:
            if self.training:
                self.h2_bank.index_copy_(0, state_indices, h2_re_next.detach())
                self.h1_bank.index_copy_(0, state_indices, h1_re_next.detach())
                self.h2_im_bank.index_copy_(0, state_indices, h2_im_next.detach())
                self.h1_im_bank.index_copy_(0, state_indices, h1_im_next.detach())
        else:
            self.h2[:B].copy_(h2_re_next.detach())
            self.h1[:B].copy_(h1_re_next.detach())
            self.h2_im[:B].copy_(h2_im_next.detach())
            self.h1_im[:B].copy_(h1_im_next.detach())
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

        # Core computation #2: controller-driven transformations.
        if ctrl is None and self.controller is not None:
            # Compute controller inside the checkpoint (no buffer mutation).
            q_per_chakra = self._qi_per_chakra(Q_field)
            q_trend = self.Q_trend.to(device).expand(B)
            yz_ratio = self._yang_yin_ratio(psi_real, psi_imag)
            field_energy = self._complex_norm2(psi_real, psi_imag).mean(dim=(1, 2))
            # Snapshot h_ctrl before the checkpoint so the controller forward
            # reads a frozen copy, not the mutable buffer (which would be
            # updated after the checkpoint and cause gradient corruption during
            # backward recomputation).
            h_ctrl_snapshot = self.controller.h_ctrl.detach().clone().unsqueeze(0).expand(B, -1)

            if self.use_checkpoint and self.training:
                psi_real, psi_imag, Q_field, q_mean, self_reg_factor, ctrl, perturb_ctrl = \
                    torch.utils.checkpoint.checkpoint(
                        self._field_step_with_ctrl,
                        psi_real, psi_imag, Q_field, P_re, P_im, breath,
                        q_per_chakra, q_trend, yz_ratio, field_energy,
                        None, h_ctrl_snapshot,
                        use_reentrant=False,
                    )
            else:
                psi_real, psi_imag, Q_field, q_mean, self_reg_factor, ctrl, perturb_ctrl = \
                    self._field_step_with_ctrl(
                        psi_real, psi_imag, Q_field, P_re, P_im, breath,
                        q_per_chakra, q_trend, yz_ratio, field_energy,
                        None, h_ctrl_snapshot)

            # Persist h_ctrl OUTSIDE the checkpoint (buffer mutation breaks grad flow)
            if ctrl is not None and ctrl.h_next is not None:
                self.controller._update_h_ctrl(ctrl.h_next)
        else:
            # Use pre-computed ctrl (from K_train loop) or run with no controller.
            if ctrl is not None:
                perturb_ctrl = ctrl.perturb.view(B, 1, 1).clamp(0.0, 0.1)
            else:
                perturb_ctrl = torch.zeros(B, 1, 1, device=device)
            if self.use_checkpoint and self.training:
                psi_real, psi_imag, Q_field, q_mean, self_reg_factor = \
                    torch.utils.checkpoint.checkpoint(
                        self._field_step_transform,
                        psi_real, psi_imag, Q_field, P_re, P_im, breath, ctrl,
                        use_reentrant=False,
                    )
            else:
                psi_real, psi_imag, Q_field, q_mean, self_reg_factor = \
                    self._field_step_transform(
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

    @staticmethod
    def _resize_transceiver_buffers(transceiver, new_B: int) -> None:
        """Resize a transceiver's persistent IIR buffers to new_B rows.

        Copies existing rows and zero-fills new rows. Never broadcasts
        (the old expand().clone() pattern gave all new rows the same
        state as row 0, which is a bug for independent batch samples).
        """
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

    def _yang_yin_ratio(self, psi_real, psi_imag):
        y = psi_real.pow(2).mean(dim=(1, 2))
        z = psi_imag.pow(2).mean(dim=(1, 2)).clamp_min(1e-12)
        return y / z
    # ═══════════════════ Public API ═══════════════════

    @property
    def residuals(self):
        """Backward-compat property. Returns the (now-empty) residuals list.

        The ChakraResidual MLPs have been removed (classical ML is not
        allowed in the model architecture). External code that iterates
        `model.residuals[c].parameters()` will get no parameters back —
        the loop is a no-op. Set .grad to None gracefully.
        """
        return self._residuals_placeholder

    def reset_state(self):
        """Clear all persistent field state."""
        state = FieldState.from_buffers(self)
        state.zero_()
        self.h1_im.zero_()
        self.h2_im.zero_()
        if self.state_bank_size > 0:
            self.h1_bank.zero_()
            self.h2_bank.zero_()
            self.h1_im_bank.zero_()
            self.h2_im_bank.zero_()
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
                    self._resize_transceiver_buffers(t, B)

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
        return logits
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
                    self._resize_transceiver_buffers(t, B)

        context_len = max(1, N - self.span_len)
        if self.span_len >= N:
            context_len = N // 2
        context = x[:, :context_len]
        target = x[:, context_len:]

        # Pad context to length N by repeating the last context token.
        # Zero-fill provides no signal; the last token gives the field a
        # meaningful "carry-forward" boundary condition.
        if context.shape[1] < N:
            last_token = context[:, -1:].expand(B, N - context_len)
            context = torch.cat([context, last_token], dim=1)

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
                    self._resize_transceiver_buffers(t, B)

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
