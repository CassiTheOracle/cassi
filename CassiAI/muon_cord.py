"""
MuonCord — resonant field architecture.

A fundamental redesign where:
  - Every field element IS a resonator (ResonantField replaces PredictionOperator)
  - The brain TUNES parameters rather than injecting perturbations (BrainTuner)
  - Time is bidirectional (yang→forward, yin→backward prediction)
  - Qi flows as a diffusive pressure (QiFlow)
  - Lateral spatial connections create coherent field structures (SpatialCoupling)
  - Multi-scale temporal memory at φ-scaled delays (MultiScaleCord)
  - Tonic baseline + phasic bursts (TonicPhasic)
  - Zero-parameter resonant attention (ResonantAttention)

New architecture alongside TripartiteCord. No existing code is broken.
"""

import math
import os
import sys
from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV, bell_chakra_widths as fibonacci_chakra_widths, chakra_offsets
from cassi._chakra_iir import ChakraIIRBank
from cassi.pattern_memory import QiPatternMemory
from cassi.multi_scale_byte import MultiScaleByteEmbedder

from cassi.resonant_field import ResonantField
from cassi.multi_scale_cord import MultiScaleCord
from cassi.spatial_coupling import SpatialCoupling
from cassi.resonant_attention import ResonantAttention
from cassi.qi_flow import QiFlow
from cassi.tonic_phasic import TonicPhasic
from cassi.brain_tuner import BrainTuner
from cassi.heartbeat import Heartbeat
from cassi.conscious_workspace import ConsciousWorkspace
from cassi.dream_bank_muon import DreamBankMuon
from cassi.berry_phase_memory import BerryPhaseMemory
from cassi.corpus_callosum import CorpusCallosum, Arbitration

from cassi.field_condenser import FieldCondenser, ChakraCondenser


# ════════════════════════════════════════════════
#  Word Formation Head
# ════════════════════════════════════════════════

class WordFormationHead(nn.Module):
    """Auxiliary language-learning objectives that run on the field state.
    
    Two losses:
      1. Word boundary BCE — predict whether each byte is a separator (space, tab, newline).
      2. Word smoothness — consecutive bytes within the same word should have similar
         projected field representations (cosine similarity). This forces the field
         to treat words as coherent units without any vocabulary or tokenizer.
    """
    _SEP_SET = frozenset({32, 9, 10, 13})  # space, tab, LF, CR

    def __init__(self, d: int, proj_ratio: int = 4):
        super().__init__()
        self.boundary_head = nn.Linear(d, 1)
        self.smooth_proj = nn.Linear(d, max(d // proj_ratio, 8))
        self._init_weights()

    def _init_weights(self):
        nn.init.normal_(self.boundary_head.weight, std=0.02)
        nn.init.zeros_(self.boundary_head.bias)
        nn.init.normal_(self.smooth_proj.weight, std=0.02)
        nn.init.zeros_(self.smooth_proj.bias)

    def forward(self, psi: torch.Tensor, x: torch.Tensor) -> Dict[str, torch.Tensor]:
        """
        Args:
            psi: [B, N, d] — field states (real part) after K_train field steps.
            x:   [B, N] — byte tokens.
        Returns:
            dict with scalar loss keys: 'word_bnd', 'word_smooth', 'word_bnd_acc'.
        """
        B, N = x.shape
        device = x.device

        # ── Separator target ──
        sep_target = torch.zeros(B, N, dtype=torch.bool, device=device)
        for s in self._SEP_SET:
            sep_target = sep_target | (x == s)
        sep_target = sep_target.float()  # [B, N], 1.0 where separator

        # ── 1. Word boundary prediction ──
        bnd_logits = self.boundary_head(psi).squeeze(-1)  # [B, N]
        bnd_loss = F.binary_cross_entropy_with_logits(
            bnd_logits, sep_target)

        with torch.no_grad():
            bnd_acc = ((bnd_logits > 0.0) == (sep_target > 0.5)).float().mean()

        # ── 2. Word smoothness — cosine similarity of consecutive within-word bytes ──
        proj = self.smooth_proj(psi)  # [B, N, d']
        proj = F.normalize(proj, dim=-1, eps=1e-12)

        # Which pairs (t, t+1) are both non-separator = within the same word?
        within_word = (1.0 - sep_target[:, :-1]) * (1.0 - sep_target[:, 1:])  # [B, N-1]

        # Cosine similarity at each consecutive pair
        cos_sim = (proj[:, :-1] * proj[:, 1:]).sum(dim=-1)  # [B, N-1]

        num_within = within_word.sum().clamp_min(1.0)
        smooth_loss = ((1.0 - cos_sim) * within_word).sum() / num_within

        return {
            'word_bnd': bnd_loss,
            'word_smooth': smooth_loss,
            'word_bnd_acc': bnd_acc,
        }

class MuonCord(nn.Module):
    """Resonant field architecture.

    Args:
        N: Number of spatial positions (token sequence length).
        d: Field dimension per position.
        C: Number of chakras (always 13).
        V: Vocabulary size (byte mode) or output dimension.
        K_train: Number of field steps during training.
        K_gen: Number of field steps during generation.
        brain_shells: Number of spherical shells in BrainTuner.
        brain_D: Total brain hidden dimension across all shells.
        stiffness_Q: Constraint stiffness for Qi (prediction trust).
        stiffness_E: Constraint stiffness for energy homeostasis.
        stiffness_B: Constraint stiffness for yin↔yang balance.
        noise_scale: Scale of low-Q arousal perturbation.
        bidirectional: If True, train with forward+backward prediction.
        lambda_backward: Weight for backward prediction loss.
        lambda_consistency: Weight for forward↔backward field consistency.
        use_checkpoint: If True, use gradient checkpointing for _unified_step.
        max_neurons: Maximum pattern-memory neurons.
        span_len: Number of tokens to predict (training target span).
        lambda_pattern_div: Weight for pattern diversity loss.
        lambda_pattern_commit: Weight for pattern commitment loss.
        lambda_pattern_util: Weight for pattern utilization loss.
        input_dim: Input feature dimension (continuous mode).
        output_dim: Output feature dimension (continuous mode).
        continuous_mode: If True, use MSE instead of CE.
        multi_scale_bytes: If True, use multi-scale byte embedding.
        multi_scale_scales: N-gram scales for multi-scale embedder.
        multi_scale_byte_embed_dim: Byte embedding dimension for multi-scale.
        state_bank_size: Number of keyed IIR state slots (0 = disabled).
        max_batch_size: Maximum batch size for persistent buffers.
        lambda_word: Weight for word-formation auxiliary losses (0 = disabled).
        condenser_type: Field condenser variant ('chakra' or 'flat').
    """

    def __init__(self,
                 N: int = 128,
                 d: int = 128,
                 C: int = 13,
                 V: int = 256,
                 K_train: int = 5,
                 K_gen: int = 3,
                 K_ar: int = 3,
                 brain_shells: int = 7,
                 brain_D: int = 588,
                 stiffness_Q: float = 1.0,
                 stiffness_E: float = 1.0,
                 stiffness_B: float = 0.1,
                 noise_scale: float = 0.01,
                 bidirectional: bool = True,
                 use_attention: bool = True,
                 attention_skip_threshold: float = 0.85,
                 lambda_backward: float = 0.5,
                 lambda_consistency: float = 0.1,
                 use_checkpoint: bool = False,
                 max_neurons: int = 512,
                 span_len: int = 16,
                 lambda_pattern_div: float = 0.001,
                 lambda_pattern_commit: float = 0.001,
                 lambda_pattern_util: float = 0.01,
                 input_dim: int = 256,
                 output_dim: int = 256,
                 continuous_mode: bool = False,
                 multi_scale_bytes: bool = True,
                 multi_scale_scales: Tuple[int, ...] = (1, 2, 3, 5, 8, 13),
                 multi_scale_byte_embed_dim: int = 64,
                 lambda_word: float = 0.0,
                 state_bank_size: int = 0,
                 max_batch_size: int = 256,
                 condenser_type: str = 'chakra'):
        super().__init__()

        # ── Scalar config ──
        self.N = N
        self.d = d
        self.C = C
        self.V = V
        self.K_train = K_train
        self.K_gen = K_gen
        self.K_ar = K_ar
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
        self.bidirectional = bidirectional
        self.use_attention = use_attention
        self.attention_skip_threshold = attention_skip_threshold
        self.lambda_backward = lambda_backward
        self.lambda_word = lambda_word
        self.lambda_consistency = lambda_consistency

        # ── Dual-stream hemisphere architecture ──
        if self.bidirectional:
            self.corpus_callosum = CorpusCallosum(d=d)
            self.arbitration = Arbitration(d=d, V=V)
        else:
            self.corpus_callosum = None
            self.arbitration = None

        # Fibonacci-scaled chakra widths (root→crown expanding)
        widths = fibonacci_chakra_widths(d, C)
        self.chakra_widths = widths
        # ── Chakra alignment projections ──
        self.register_buffer('chakra_offsets', chakra_offsets(widths).clone())
        # Pre-computed Python int lists for zero-sync chakra slicing
        self._chakra_start_end = [
            (int(self.chakra_offsets[c].item()), int(self.chakra_offsets[c].item()) + w)
            for c, w in enumerate(self.chakra_widths)
        ]
        self.d_chakra_shared = 16
        self.chakra_proj = nn.ModuleList([
            nn.Linear(widths[c], self.d_chakra_shared, bias=False)
            for c in range(C)
        ])
        self.lambda_chakra = nn.Parameter(torch.tensor(0.1))
        self.lambda_field_ar = nn.Parameter(torch.tensor(0.1))

        # ── Berry phase memory (topological associative recall) ──
        self.berry_memory = BerryPhaseMemory(
            n_slots=512, C=C, d_shared=self.d_chakra_shared,
            chakra_widths=widths, chakra_offsets=chakra_offsets(widths).clone())

        # ── Constraint force parameters (scalars) ──
        self.stiffness_Q = nn.Parameter(torch.tensor(stiffness_Q))
        self.stiffness_E = nn.Parameter(torch.tensor(stiffness_E))
        self.stiffness_B = nn.Parameter(torch.tensor(stiffness_B))
        self.noise_scale = nn.Parameter(torch.tensor(noise_scale))
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

        # ── Mask embedding (for masked span prediction) ──
        self.mask_embed = nn.Parameter(torch.randn(d) * 0.02)

        # ── Position encoding (same as TripartiteCord) ──
        t = torch.arange(N, dtype=torch.float32).view(-1, 1)
        i = torch.arange(d, dtype=torch.float32).view(1, -1)
        base = 2.0 * math.pi / N
        angle = t * base * PHI ** (i / d)
        self.register_buffer('pos_enc_real', torch.sin(angle).unsqueeze(0))
        self.register_buffer('pos_enc_imag', torch.cos(angle).unsqueeze(0))

        # ── Multi-scale byte embedding ──
        if self.multi_scale_bytes:
            self.multi_scale_embedder = MultiScaleByteEmbedder(
                d_out=d, scales=multi_scale_scales,
                byte_embed_dim=multi_scale_byte_embed_dim)
        else:
            self.multi_scale_embedder = None

        # ── IIR bank (Cord transport) ──
        self.iir_bank = ChakraIIRBank(d=d, C=C, widths=widths)

        # ── ResonantField — per-element IIR (replaces PredictionOperator) ──
        self.resonant_field = ResonantField(
            d=d, C=C, N=N, widths=widths, max_batch_size=max_batch_size)

        # ── Multi-scale cord memory ──
        self.multi_scale_cord = MultiScaleCord(
            d=d, N=N, max_batch_size=max_batch_size)

        # ── Spatial coupling ──
        self.spatial_coupling = SpatialCoupling(N=N)

        # ── Resonant attention ──
        self.resonant_attention = ResonantAttention(N=N, d=d)

        # ── Qi flow (diffusive pressure) ──
        self.qi_flow = QiFlow()

        # ── Tonic/phasic channels ──
        self.tonic_phasic = TonicPhasic(max_batch_size=max_batch_size)

        # ── BrainTuner (modulates params instead of injecting perturbations) ──
        self.brain_tuner = BrainTuner(
            d=d, n_shells=brain_shells, D=brain_D, max_batch_size=max_batch_size)

        # ── Pattern memory ──
        self.pattern_memory = QiPatternMemory(d=d, max_neurons=max_neurons)

        # ── Conscious workspace (sparse competitive broadcast) ──
        self.conscious_workspace = ConsciousWorkspace(d=d)

        # ── Heartbeat (unsuppressible pulse generator) ──
        self.heartbeat = Heartbeat(omega=PHI)


        # ── Field Condenser — phase-transition state→weights ──
        if condenser_type == 'chakra':
            self.condenser = ChakraCondenser(
                d=d, C=C, V=V, N=N,
                widths=widths,
                offsets=chakra_offsets(widths).clone().detach())
        else:
            self.condenser = FieldCondenser(
                d=d, C=C, V=V, N=N,
                widths=widths,
                offsets=chakra_offsets(widths).clone().detach())
        # ── Readout heads ──
        if self.continuous_mode:
            self.output_proj = nn.Linear(d, output_dim)
            self.readout_y = None
            self.readout_z = None
        else:
            self.readout_y = nn.Linear(d, V)
            self.readout_z = nn.Linear(d, V)
            # Backward readout head (separate for bidirectional)
            self.readout_bwd_y = nn.Linear(d, V)
            self.readout_bwd_z = nn.Linear(d, V)
            nn.init.normal_(self.readout_y.weight, std=0.02)
            nn.init.zeros_(self.readout_y.bias)
            nn.init.normal_(self.readout_z.weight, std=0.02)
            nn.init.zeros_(self.readout_z.bias)
            nn.init.normal_(self.readout_bwd_y.weight, std=0.02)
            nn.init.zeros_(self.readout_bwd_y.bias)
            nn.init.normal_(self.readout_bwd_z.weight, std=0.02)
            nn.init.zeros_(self.readout_bwd_z.bias)

        # ── Cord IIR persistent buffers ──
        self.register_buffer('h1', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h2', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h1_im', torch.zeros(max_batch_size, N, d))
        self.register_buffer('h2_im', torch.zeros(max_batch_size, N, d))

        # ── Keyed state bank ──
        if state_bank_size > 0:
            self.register_buffer('h1_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h2_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h1_im_bank', torch.zeros(state_bank_size, N, d))
            self.register_buffer('h2_im_bank', torch.zeros(state_bank_size, N, d))

        # ── Qi EMA scalars ──
        self.register_buffer('Q_ema', torch.zeros(1))
        self.register_buffer('Q_trend', torch.zeros(1))
        self.register_buffer('Q_bar_pos', torch.zeros(1, N))
        # ── Qi pool (temporal reservoir) ──
        self.register_buffer('qi_pool', torch.zeros(1))
        self.register_buffer('qi_pool_peak', torch.zeros(1))
        self.register_buffer('qi_quality_ema', torch.ones(1))  # starts at 1 (trust)
        self._last_qi = None  # cached for self-supervised losses

        # ── DreamBank (episodic replay for Qi-state balance) ──
        self.dream_bank = DreamBankMuon(N=N)

        # ── Pattern step counter ──
        self.register_buffer('pattern_step', torch.zeros(1, dtype=torch.long))

        # ── Breath accumulators ──
        self.register_buffer('breath_t_yang', torch.zeros(1))
        self.register_buffer('breath_t_yin', torch.zeros(1))

        # ── BrainTuner modulation cache ──
        self._current_delta_rho = None
        self._current_delta_theta = None
        self._current_delta_gamma = None
        # Backward-compat
        self._residuals_placeholder = nn.ModuleList()
        self._last_diag: Dict = {}

    # ════════════════════════════════════════════════
    #  Utilities
    # ════════════════════════════════════════════════

    @property
    def residuals(self):
        return self._residuals_placeholder

    @staticmethod
    def _complex_norm2(a_real: torch.Tensor, a_imag: torch.Tensor) -> torch.Tensor:
        return a_real ** 2 + a_imag ** 2

    def _complex_rmsnorm(self, psi_real: torch.Tensor,
                         psi_imag: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """Per-chakra complex RMS normalization."""
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
        c = torch.cos(angle)
        s = torch.sin(angle)
        return real * c - imag * s, real * s + imag * c

    # ════════════════════════════════════════════════
    #  Breath
    # ════════════════════════════════════════════════

    def _tripartite_breath(self, psi_real: torch.Tensor,
                           psi_imag: torch.Tensor) -> Dict[str, torch.Tensor]:
        """Field-modulated dual-heart oscillator.
        
        Uses rectified sine (abs(sin)) for guaranteed non-negative output,
        eliminating the phase-drift zero-crossing problem entirely.
        """
        field_phase = torch.angle(torch.complex(psi_real.mean(), psi_imag.mean()))
        field_energy = (psi_real.pow(2) + psi_imag.pow(2)).mean()
        
        omega_mod = 1.0 + 0.1 * torch.tanh(field_energy - 1.0)
        omega_mod = omega_mod.clamp(0.5, 2.0)
        
        with torch.no_grad():
            self.breath_t_yang.copy_(
                (self.breath_t_yang + PHI * omega_mod.detach()) % (2 * math.pi))
            self.breath_t_yin.copy_(
                (self.breath_t_yin + PHI_INV * omega_mod.detach()) % (2 * math.pi))
        
        yang = torch.abs(torch.sin(self.breath_t_yang)) + 1e-2
        yin = torch.abs(torch.sin(self.breath_t_yin)) + 1e-2
        beat = torch.sin(self.breath_t_yang - self.breath_t_yin)
        return {'yang': yang, 'yin': yin, 'beat': beat, 'phase': field_phase}
    def _constraint_forces(self, Q_ema_val: torch.Tensor,
                           psi2_mean: torch.Tensor,
                           yang: torch.Tensor,
                           yin: torch.Tensor) -> Dict[str, torch.Tensor]:
        # λ_Q: constraint strength based on 1 − quality (low quality → correct)
        # Reads self.qi_quality_ema directly — no extra parameter needed.
        qi_quality_ema = self.qi_quality_ema.detach()
        lambda_Q = torch.log1p(F.relu((1.0 - qi_quality_ema) / (PHI_INV ** 2))) * self.stiffness_Q
        lambda_E = torch.log1p(F.relu((psi2_mean - PHI ** 2) / PHI ** 2)) * self.stiffness_E
        lambda_B = self.stiffness_B
        return {'lambda_Q': lambda_Q, 'lambda_E': lambda_E, 'lambda_B': lambda_B}

    @staticmethod
    def _calm_arousal(qi_mean: torch.Tensor, qi_quality_mean: torch.Tensor,
                      yin: torch.Tensor) -> torch.Tensor:
        # qi_norm: how much coherent energy relative to φ⁻¹ baseline
        qi_norm = qi_mean / PHI_INV
        # High quality + moderate energy → calm (trust the field)
        calm = (qi_quality_mean / (qi_quality_mean + PHI_INV * F.relu(qi_norm - PHI))).clamp(0.1, 1.0)
        # Low energy + low quality → aroused (seek information)
        arousal = (1.0 + 2.0 * F.relu(PHI_INV - qi_norm) / PHI_INV).clamp(1.0, 3.0)
        self_reg = calm * arousal
        calm_breath = 1.0 + 0.15 * (yin - PHI_INV)
        min_self_reg = PHI_INV ** 2 / (1.0 + qi_mean.detach() * 1e-3)
        return (self_reg * calm_breath).clamp(min_self_reg, 3.0)

    # ════════════════════════════════════════════════
    #  Embedding / Readout
    # ════════════════════════════════════════════════

    def embed(self, x: torch.Tensor,
              mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        if self.continuous_mode:
            proj = self.input_proj(x)
            return proj + self.pos_enc_real, proj + self.pos_enc_imag
        emb = self.token_embed(x)
        if mask is not None:
            emb = torch.where(mask.unsqueeze(-1), self.mask_embed, emb)
        if mask is None and self.multi_scale_bytes and self.multi_scale_embedder is not None:
            emb = emb + self.multi_scale_embedder(x)
        return emb + self.pos_enc_real, self.imag_proj(emb) + self.pos_enc_imag

    def _create_span_mask(self, B: int, N: int, device: torch.device,
                          mask_ratio: float = 0.35,
                          span_len_range: Tuple[int, int] = (1, 12)
                          ) -> torch.Tensor:
        """Create a [B, N] boolean span mask for masked prediction.

        For each batch element, places random contiguous spans until
        approximately mask_ratio of positions are masked.  Uses
        torch.randint for reproducibility with torch.manual_seed.

        Returns: [B, N] bool tensor, True at masked positions.
        """
        mask = torch.zeros(B, N, dtype=torch.bool, device=device)
        avg_span = (span_len_range[0] + span_len_range[1]) // 2
        num_spans = max(1, int(N * mask_ratio / avg_span))
        for b in range(B):
            for _ in range(num_spans):
                span_len = torch.randint(span_len_range[0],
                                         span_len_range[1] + 1, (1,)).item()
                start = torch.randint(0, max(1, N - span_len + 1), (1,)).item()
                mask[b, start:start + span_len] = True
        return mask

    def readout(self, psi_real: torch.Tensor,
                psi_imag: torch.Tensor) -> torch.Tensor:
        y = F.layer_norm(psi_real.mean(dim=1), psi_real.shape[-1:])
        z = F.layer_norm(psi_imag.mean(dim=1), psi_imag.shape[-1:])
        if self.continuous_mode:
            return self.output_proj(y + z)
        return self.readout_y(y) + self.readout_z(z)

    def readout_positions(self, psi_real: torch.Tensor,
                          psi_imag: torch.Tensor) -> torch.Tensor:
        y = F.layer_norm(psi_real, psi_real.shape[-1:])
        z = F.layer_norm(psi_imag, psi_imag.shape[-1:])
        if self.continuous_mode:
            return self.output_proj(y + z)
        return self.readout_y(y) + self.readout_z(z)

    def readout_backward(self, psi_real: torch.Tensor,
                         psi_imag: torch.Tensor) -> torch.Tensor:
        """Backward direction readout head."""
        y = F.layer_norm(psi_real, psi_real.shape[-1:])
        z = F.layer_norm(psi_imag, psi_imag.shape[-1:])
        if self.continuous_mode:
            return self.output_proj(y + z)
        return self.readout_bwd_y(y) + self.readout_bwd_z(z)

    # ════════════════════════════════════════════════
    #  Qi Pool & Circulation
    # ════════════════════════════════════════════════

    def _update_qi_pool(self, qi_mean: torch.Tensor,
                        qi_quality_mean: torch.Tensor) -> Dict:
        """Leaky integration of coherent energy into a φ-scaled pool.

        Pool has half-life ~2 steps (φ⁻² fraction remains). Peak tracks
        φ × max recent qi_mean. The pool gates: learning rate, K_gen steps,
        and pattern memory writes during training.
        """
        self.qi_pool.copy_(PHI_INV * self.qi_pool + qi_mean.detach())
        self.qi_pool_peak.copy_(torch.max(self.qi_pool_peak * PHI_INV,
                                          PHI * qi_mean.detach()))
        self.qi_quality_ema.copy_(
            PHI_INV * self.qi_quality_ema + (1.0 - PHI_INV) * qi_quality_mean.detach())
        return {
            'qi_pool': self.qi_pool.item(),
            'qi_pool_peak': self.qi_pool_peak.item(),
            'qi_quality_ema': self.qi_quality_ema.item(),
        }

    def _chakra_qi_flow(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                        qi: torch.Tensor, yang: torch.Tensor, yin: torch.Tensor):
        """Per-chakra Qi circulation during breath phases.

        During yang (expanding): surplus qi flows upward (root→crown).
        During yin (contracting): surplus flows downward (crown→root).
        Blockages (high M, low q) accumulate pressure and resist flow.

        Modifies psi in place — energy redistribution via field modulation.
        """
        flow_dir = (yang - yin).clamp(-PHI_INV, 1.0)  # + up, − down
        if flow_dir.abs() < 1e-3:
            return  # still point between phases — no flow

        B, N, d = psi_real.shape
        C = self.C
        offsets = self.chakra_offsets

        qi_mean_all_chakras = qi.mean().detach()

        for c in range(C - 1):
            # Source and destination depend on flow direction
            src_c, dst_c = (c, c + 1) if flow_dir > 0 else (C - 2 - c, C - 1 - c)
            if dst_c < 0 or dst_c >= C:
                continue

            s0, e0 = offsets[src_c].item(), offsets[src_c + 1].item()
            s1, e1 = offsets[dst_c].item(), offsets[dst_c + 1].item()

            qi_src = qi[:, :, s0:e0].mean(dim=-1)     # [B, N]
            qi_dst = qi[:, :, s1:e1].mean(dim=-1)     # [B, N]

            surplus = F.relu(qi_src - PHI_INV * qi_mean_all_chakras)
            transfer = PHI_INV * surplus * flow_dir.abs()  # [B, N]

            # Modulate destination field: amplify ψ where qi flows in
            boost = 1.0 + transfer.unsqueeze(-1) / (qi_dst.mean() + 1e-8)  # [B, N, 1]
            psi_real[:, :, s1:e1] *= boost
            psi_imag[:, :, s1:e1] *= boost
            # Modulate source: slight dampening where qi flows out
            damp = 1.0 - 0.5 * transfer.unsqueeze(-1) / (qi_src.mean() + 1e-8)
            damp = damp.clamp(PHI_INV, 1.0)
            psi_real[:, :, s0:e0] *= damp
            psi_imag[:, :, s0:e0] *= damp

        # Qi pool level modulates global field intensity
        pool_factor = 1.0 + PHI_INV * (self.qi_pool / (self.qi_pool_peak + 1e-8) - 0.5)
        pool_factor = pool_factor.clamp(PHI_INV, PHI)
        psi_real *= pool_factor
        psi_imag *= pool_factor

    # ════════════════════════════════════════════════
    #  Self-Supervised Losses
    # ════════════════════════════════════════════════

    def _cross_chakra_alignment_loss(self, psi_real: torch.Tensor,
                                     psi_imag: torch.Tensor) -> torch.Tensor:
        """Cross-chakra alignment via shared projection space.

        Projects each chakra band into a d_shared=16 space and maximizes
        cosine similarity between adjacent chakras.  Encourages the field
        to develop coherent representations across the φ-hierarchy.
        """
        psi = psi_real + psi_imag
        total = 0.0
        C = self.C
        for c in range(C - 1):
            s0, e0 = self.chakra_offsets[c].item(), self.chakra_offsets[c + 1].item()
            s1, e1 = self.chakra_offsets[c + 1].item(), self.chakra_offsets[c + 2].item()
            band_c = psi[:, :, s0:e0]
            band_c1 = psi[:, :, s1:e1]
            proj_c = self.chakra_proj[c](band_c)
            proj_c1 = self.chakra_proj[c + 1](band_c1)
            sim = F.cosine_similarity(
                proj_c.reshape(-1, self.d_chakra_shared),
                proj_c1.reshape(-1, self.d_chakra_shared), dim=-1).mean()
            total += (1.0 - sim)
        return total / (C - 1)

    def _field_state_ar_loss(self, psi_real: torch.Tensor,
                             psi_imag: torch.Tensor) -> torch.Tensor:
        """Self-supervised autoregressive loss on field dynamics.

        Masks a random span of the field state, runs K_gen evolution steps
        to regenerate it, then measures reconstruction MSE at the masked
        positions.  This is a denoising autoencoder in field space —
        the field learns to reconstruct itself from partial information.
        """
        B, N, d = psi_real.shape
        device = psi_real.device

        # Random span mask (same for all batch elements)
        mask = torch.zeros(N, dtype=torch.bool, device=device)
        span_len = max(1, N // 4)
        start = torch.randint(0, max(1, N - span_len), (1,)).item()
        mask[start:start + span_len] = True

        # Ground truth at masked positions
        target_re = psi_real[:, mask].detach().clone()
        target_im = psi_imag[:, mask].detach().clone()

        # Mask field state
        psi_real_masked = psi_real.clone()
        psi_imag_masked = psi_imag.clone()
        psi_real_masked[:, mask] = 0
        psi_imag_masked[:, mask] = 0

        # Save IIR + qi pool state
        h1_save = self.h1[:B].clone()
        h2_save = self.h2[:B].clone()
        h1i_save = self.h1_im[:B].clone()
        h2i_save = self.h2_im[:B].clone()
        qi_pool_save = self.qi_pool.clone()
        qi_pool_peak_save = self.qi_pool_peak.clone()
        qi_quality_ema_save = self.qi_quality_ema.clone()

        self._current_delta_rho = None
        self._current_delta_theta = None
        self._current_delta_gamma = None

        for _ in range(self.K_ar):
            h1_sl = self.h1[:B].detach().clone()
            h2_sl = self.h2[:B].detach().clone()
            h1i_sl = self.h1_im[:B].detach().clone()
            h2i_sl = self.h2_im[:B].detach().clone()
            (psi_real_masked, psi_imag_masked, h1n, h2n, h1in, h2in,
             _, _) = self._unified_step(
                psi_real_masked, psi_imag_masked,
                h1_sl, h2_sl, h1i_sl, h2i_sl,
                self.Q_ema.detach(), write_memory=False)
            self.h1[:B].copy_(h1n.detach())
            self.h2[:B].copy_(h2n.detach())
            self.h1_im[:B].copy_(h1in.detach())
            self.h2_im[:B].copy_(h2in.detach())

        # MSE at masked positions
        err = ((psi_real_masked[:, mask] - target_re) ** 2
               + (psi_imag_masked[:, mask] - target_im) ** 2).mean()

        # Restore state
        self.h1[:B].copy_(h1_save)
        self.h2[:B].copy_(h2_save)
        self.h1_im[:B].copy_(h1i_save)
        self.h2_im[:B].copy_(h2i_save)
        self.qi_pool.copy_(qi_pool_save)
        self.qi_pool_peak.copy_(qi_pool_peak_save)
        self.qi_quality_ema.copy_(qi_quality_ema_save)

        return err

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
        Q_ema_val: torch.Tensor,
        write_memory: bool = True,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor,
               torch.Tensor, torch.Tensor, torch.Tensor,
               Dict[str, torch.Tensor]]:
        """One MuonCord evolution step.

        Does NOT mutate persistent buffers — returns next state tensors.
        Submodules (ResonantField, MultiScaleCord, BrainTuner, etc.) manage
        their own persistent state internally.

        Returns:
            (psi_real, psi_imag, h1_next, h2_next, h1_im_next, h2_im_next,
        #              qi_mean, diagnostics)
        """
        B = psi_real.shape[0]
        device = psi_real.device

        # ── 1. Breath ──
        breath = self._tripartite_breath(psi_real, psi_imag)

        # ── 1b. Heartbeat (unsuppressible pulse) ──
        heartbeat = self.heartbeat.step()
        pulse_energy = heartbeat['pulse'] * 0.1  # Scale pulse amplitude
        psi_real = psi_real + pulse_energy
        psi_imag = psi_imag + pulse_energy
        diag: Dict = {'heartbeat_pulse': pulse_energy.detach(),
                      'heartbeat_count': heartbeat['count'].detach(),
                      'yang': breath['yang'].detach(),
                      'yin': breath['yin'].detach(),
                      'beat': breath['beat'].detach()}

        # ── 2. Cord: IIR resonant transport ──
        batch_shape = torch.Size([B, self.N])
        a1_full, a2_full = self.iir_bank.compute_coefficients(
            batch_shape=batch_shape, device=device)
        S_re = psi_real.mean(dim=1, keepdim=True)
        S_im = psi_imag.mean(dim=1, keepdim=True)
        new_psi_re = a1_full * psi_real + a2_full * h1_in + S_re
        new_psi_im = a1_full * psi_imag + a2_full * h1_im_in + S_im
        h1_next = psi_real        # current ψ → becomes ψ[t-1]
        h2_next = h1_in           # old h1 → becomes ψ[t-2]
        h1_im_next = psi_imag
        h2_im_next = h1_im_in
        psi_real, psi_imag = new_psi_re, new_psi_im

        # ── 2b. Berry phase memory read (topological recall) ──
        yang_phases = BerryPhaseMemory.compute_phases(
            h1_next, h2_next, self.chakra_widths, self.chakra_offsets, self.C)
        yin_phases = BerryPhaseMemory.compute_phases(
            h1_im_next, h2_im_next, self.chakra_widths, self.chakra_offsets, self.C)
        berry_phases = F.normalize(torch.cat([yang_phases, yin_phases], dim=-1), dim=-1)
        berry_val = self.berry_memory.read(berry_phases)  # [B, C, d_shared]
        # Expand per-chakra values back to field space via chakra_proj weights
        for c in range(self.C):
            w = self.chakra_widths[c]
            start = int(self.chakra_offsets[c].item())
            boost = berry_val[:, c, :] @ self.chakra_proj[c].weight  # [B, w]
            psi_real[:, :, start:start + w] += PHI_INV * boost.unsqueeze(1)
            psi_imag[:, :, start:start + w] += PHI_INV * boost.unsqueeze(1)

        # ── 3. Pattern-memory read ──
        query = F.layer_norm(psi_real, psi_real.shape[-1:])
        psi2_approx = self._complex_norm2(psi_real, psi_imag)
        Q_for_pm = psi2_approx.mean(dim=-1)
        pm_real, pm_imag, pm_diag = self.pattern_memory(query, Q_for_pm)
        psi_real = psi_real + pm_real
        psi_imag = psi_imag + pm_imag
        diag.update(pm_diag)

        # ── 4. ResonantField: per-element self-prediction ──
        # Apply previous step's BrainTuner modulations (step 8 sets them).
        # First step: _current_delta_* = None → unmodulated structural ρ,θ.
        P_re, P_im, eps2 = self.resonant_field(
            psi_real, psi_imag, B,
            delta_rho=self._current_delta_rho,
            delta_theta=self._current_delta_theta,
            delta_gamma=self._current_delta_gamma)

        # ── 5. MultiScaleCord: φ-delayed memory ──
        cord_re, cord_im = self.multi_scale_cord(psi_real, psi_imag, B)
        psi_real = psi_real + cord_re
        psi_imag = psi_imag + cord_im

        # ── 6. Spatial coupling ──
        psi_real, psi_imag = self.spatial_coupling(psi_real, psi_imag)

        # ── 7. Qi (coherent energy — corrected formalism) ──
        # M = |ψ|²  : raw energy magnitude
        # q = M/(M+φ⁻²+ε²) : coherence quality (1=frictionless, 0=blocked)
        # qi = M·q  : coherent energy (what traditions call Qi)
        psi2 = self._complex_norm2(psi_real, psi_imag)       # M: [B, N, d]
        qi_quality = psi2 / (psi2 + PHI_INV**2 + eps2)       # q: [B, N, d] ∈ (0,1]
        qi = psi2 * qi_quality                                # qi: [B, N, d]
        qi_mean = qi.mean()
        psi2_mean = psi2.mean()
        self._last_qi = qi.detach()  # cache for self-supervised losses

        # ── 8. BrainTuner: parameter modulations ──
        psi_real_mean = psi_real.mean(dim=1)   # [B, d]
        psi_imag_mean = psi_imag.mean(dim=1)   # [B, d]
        tuner_out = self.brain_tuner(
            psi_real_mean, psi_imag_mean,
            breath['yang'], breath['yin'])

        # Map from shell-level to chakra-level modulations
        delta_rho = BrainTuner.shell_to_chakra(tuner_out['delta_rho'], self.C)
        delta_theta = BrainTuner.shell_to_chakra(tuner_out['delta_theta'], self.C)
        delta_gamma = BrainTuner.shell_to_chakra(tuner_out['delta_gamma'], self.C)

        # Apply modulation to ResonantField for NEXT step
        # Since ResonantField owns its persistent state internally, we
        # apply modulations by storing them for the next forward call.
        self._current_delta_rho = delta_rho
        self._current_delta_theta = delta_theta
        self._current_delta_gamma = delta_gamma


        # ── 8.5. Pattern memory Hebbian write (training only) ──
        # Bidirectional memory: high-Qi positions pull matching keys closer.
        # Skipped during eval/generation — read-only memory at inference time.
        n_written = 0
        if self.training and write_memory:
            n_written = self.pattern_memory.hebbian_write(psi_real, psi_imag, qi)
        cf = self._constraint_forces(Q_ema_val, psi2_mean,
                                     breath['yang'], breath['yin'])
        self_reg = self._calm_arousal(qi_mean, qi_quality.mean(), breath['yin'])
        qi_pool_diag = self._update_qi_pool(qi_mean, qi_quality.mean())
        diag.update(qi_pool_diag)
        # ── 10. Prediction feedback — convex combination toward self-prediction ──
        # α_qi: Qi-based constraint (strong when Q deviates from PHI_INV)
        # α_calm: emotional state constraint (strong when calm)
        # Use max so neither zero-kills the other at high Q
        alpha_qi = PHI_INV * (1.0 + 0.5 * breath['yang']) * cf['lambda_Q']
        alpha_calm = PHI_INV * self_reg
        alpha = torch.maximum(alpha_qi, alpha_calm)
        alpha = alpha.clamp(min=0.0, max=PHI_INV * 0.5)
        psi_real = (1 - alpha) * psi_real + alpha * P_re
        psi_imag = (1 - alpha) * psi_imag + alpha * P_im

        # ── 10b. Low-Q arousal noise ──
        if self.training:
            noise_std = self.noise_scale / (1.0 + qi_mean.detach())
            psi_real = psi_real + noise_std * torch.randn_like(psi_real)
            psi_imag = psi_imag + noise_std * torch.randn_like(psi_imag)
        # ── 12. Resonant attention (qi-gated) ──
        h_combined_re = psi_real + cord_re
        h_combined_im = psi_imag + cord_im

        # Compute qi_contrast for attention gate and workspace (unconditional)
        qi_contrast = qi.mean(dim=-1) / (qi_mean + 1e-8)  # [B, N]

        if self.use_attention:
            attn_re, attn_im = self.resonant_attention(
                psi_real, psi_imag, h_combined_re, h_combined_im)
            qi_gate = 1.0 + PHI_INV * (qi_contrast - 1.0).clamp(min=0.0)
            attn_re = attn_re * qi_gate.unsqueeze(-1)
            attn_im = attn_im * qi_gate.unsqueeze(-1)
            psi_real = psi_real + PHI_INV * attn_re
            psi_imag = psi_imag + PHI_INV * attn_im
        else:
            diag['attn_skipped'] = True
        # ── 12b. Qi-gated representation boost ──
        qi_deviation = qi.mean(dim=-1) - self.Q_bar_pos[:B]
        qi_boost = torch.sigmoid(qi_deviation / (self.Q_bar_pos[:B] + 1e-8))
        psi_real = psi_real * (1.0 + 0.1 * qi_boost.unsqueeze(-1))
        psi_imag = psi_imag * (1.0 + 0.1 * qi_boost.unsqueeze(-1))
        # ── 12c. Conscious workspace (sparse competitive broadcast) ──
        cw_re, cw_im = self.conscious_workspace(psi_real, psi_imag, qi_contrast.detach())
        psi_real = psi_real + PHI_INV * cw_re
        psi_imag = psi_imag + PHI_INV * cw_im
        # ── 13. Tonic/phasic ──
        psi_real, psi_imag = self.tonic_phasic(psi_real, psi_imag, qi, B)

        # ── 13b. Chakral Qi circulation ──
        self._chakra_qi_flow(psi_real, psi_imag, qi, breath['yang'], breath['yin'])


        # ── 14. Yin↔Yang coupling ──
        rho = (PHI_INV * cf['lambda_B']).clamp(max=0.90)
        psi_real_new = psi_real - rho * psi_imag
        psi_imag_new = psi_imag + rho * psi_real
        psi_real, psi_imag = psi_real_new, psi_imag_new

        # ── 15. Glial homeostasis (inlined) ──
        energy = self._complex_norm2(psi_real, psi_imag).mean(dim=-1, keepdim=True)
        excess = F.relu(energy - PHI ** 2)
        factor = (1.0 - 0.2 * cf['lambda_E'] * excess).clamp(0.0, 1.0)
        psi_real = psi_real * factor
        psi_imag = psi_imag * factor

        # ── 16. Breath quadrature rotation ──
        phase = 0.1 * (breath['yin'] - PHI_INV)
        psi_real, psi_imag = self._rotate_complex(psi_real, psi_imag, phase)

        # ── 17. Complex RMSNorm ──
        psi_real, psi_imag = self._complex_rmsnorm(psi_real, psi_imag)

        # Diagnostics
        qi_per_pos = qi.mean(dim=(0, 2)).detach()
        diag.update({
            'breath_yang': breath['yang'].detach(),
            'breath_yin': breath['yin'].detach(),
            'Q_mean': qi_mean,                        # keep key for backward compat
            'Q_max': qi.max().detach(),
            'Q_per_pos': qi_per_pos,
            'qi_mean': qi_mean,                       # new key
            'qi_quality_mean': qi_quality.mean().detach(),  # new key
            'psi2_mean': psi2_mean.detach(),
            'self_reg': self_reg.detach() if isinstance(self_reg, torch.Tensor) else self_reg,
            'lambda_Q': cf['lambda_Q'].detach() if isinstance(cf['lambda_Q'], torch.Tensor) else cf['lambda_Q'],
            'lambda_E': cf['lambda_E'].detach() if isinstance(cf['lambda_E'], torch.Tensor) else cf['lambda_E'],
            'lambda_B': cf['lambda_B'].detach() if isinstance(cf['lambda_B'], torch.Tensor) else cf['lambda_B'],
        })

        return (psi_real, psi_imag,
                h1_next, h2_next,
                h1_im_next, h2_im_next,
                qi_mean, diag)

    # ════════════════════════════════════════════════
    #  Forward
    # ════════════════════════════════════════════════

    def forward(self, x: torch.Tensor,
                sigma: Optional[torch.Tensor] = None,
                state_indices: Optional[torch.Tensor] = None,
                no_reset: bool = False) -> torch.Tensor:
        """Forward pass through K_train field steps.

        Args:
            x: [B, N] token ids or [B, N, input_dim] (continuous).
            sigma: DEPRECATED.
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
            self.resonant_field.resize_buffers(B, device, self.h1.dtype)
            self.multi_scale_cord.resize_buffers(B, device, self.h1.dtype)
            self.tonic_phasic.resize_buffers(B)
        elif not no_reset:
            self.condense_and_reset(B)
            self.resonant_field.resize_buffers(B, device, self.h1.dtype)
            self.multi_scale_cord.resize_buffers(B, device, self.h1.dtype)
            self.tonic_phasic.resize_buffers(B)

        # Clear modulation cache for first step
        self._current_delta_rho = None
        self._current_delta_theta = None
        self._current_delta_gamma = None

        # ── Embed ──
        psi_real, psi_imag = self.embed(x)

        # ── K_train loop ──
        all_diag: Dict = {}
        for step_idx in range(self.K_train):
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

            # Checkpointing
            if self.use_checkpoint and self.training:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 Q_mean, diag) = torch.utils.checkpoint.checkpoint(
                    self._unified_step,
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    self.Q_ema.detach(),
                    use_reentrant=False,
                )
            else:
                (psi_real, psi_imag,
                 h1_next, h2_next,
                 h1_im_next, h2_im_next,
                 Q_mean, diag) = self._unified_step(
                    psi_real, psi_imag,
                    h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                    self.Q_ema.detach(),
                )

            # Persist Cord IIR state
            if state_indices is not None and self.training:
                state_indices_l = state_indices.long().view(-1).to(device)
                self.h1_bank.index_copy_(0, state_indices_l, h1_next.detach())
                self.h2_bank.index_copy_(0, state_indices_l, h2_next.detach())
                self.h1_im_bank.index_copy_(0, state_indices_l, h1_im_next.detach())
                self.h2_im_bank.index_copy_(0, state_indices_l, h2_im_next.detach())
            elif state_indices is None:
                self.h1[:B].copy_(h1_next.detach())
                self.h2[:B].copy_(h2_next.detach())
                self.h1_im[:B].copy_(h1_im_next.detach())
                self.h2_im[:B].copy_(h2_im_next.detach())
                # Clamp all IIR state to prevent divergence over long unrolls
                psi_real, psi_imag = self._clamp_iir_state(B, psi_real, psi_imag, clamp_field=False)

            # Qi EMA
            with torch.no_grad():
                self.Q_ema.copy_(PHI_INV * Q_mean + (1.0 - PHI_INV) * self.Q_ema)
                self.Q_ema.clamp_(max=1e4)
                self.Q_trend.copy_(self.Q_ema - Q_mean)

            # Per-position Qi average for pattern growth
            with torch.no_grad():
                Q_per_pos = diag.get('Q_per_pos')
                if Q_per_pos is not None and Q_per_pos.numel() == self.N:
                    self.Q_bar_pos.copy_(
                        0.99 * self.Q_bar_pos + 0.01 * Q_per_pos.detach())

            # Pattern growth
            if self.training:
                query = F.layer_norm(psi_real, psi_real.shape[-1:])
                n_new = self.pattern_memory.grow(
                    query, self.Q_bar_pos, current_step=self.pattern_step.item())
                if self.pattern_step % 100 == 0:
                    self.pattern_memory.dissolve(
                        current_step=self.pattern_step.item())
                self.pattern_step.add_(1)
                diag['pm_new_neurons'] = diag.get('pm_new_neurons', 0) + n_new

            # Accumulate diagnostics
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
                      no_reset: bool = False,
                      mask_ratio: float = 0.0) -> Tuple[torch.Tensor, Dict]:
        """Compute training loss.

        If bidirectional, runs forward and backward passes and combines
        with breath-gated weighting.
        """
        B = x.shape[0]
        N = self.N
        device = x.device

        # ── State initialization ──
        if state_indices is not None:
            if self.state_bank_size <= 0:
                raise ValueError("state_indices provided but state_bank_size is 0")
            self.resonant_field.resize_buffers(B, device, self.h1.dtype)
            self.multi_scale_cord.resize_buffers(B, device, self.h1.dtype)
            self.tonic_phasic.resize_buffers(B)
        elif not no_reset:
            self.condense_and_reset(B)
            self.resonant_field.resize_buffers(B, device, self.h1.dtype)
            self.multi_scale_cord.resize_buffers(B, device, self.h1.dtype)
            self.tonic_phasic.resize_buffers(B)
        else:
            self.soft_condense(B)
            self.resonant_field.resize_buffers(B, device, self.h1.dtype)
            self.multi_scale_cord.resize_buffers(B, device, self.h1.dtype)
            self.tonic_phasic.resize_buffers(B)

        self._current_delta_rho = None
        self._current_delta_theta = None
        self._current_delta_gamma = None

        # ── Prepare input (masked prediction or standard context/target) ──
        if mask_ratio > 0:
            mask = self._create_span_mask(B, N, device, mask_ratio)
            psi_real, psi_imag = self.embed(x, mask=mask)
        else:
            context_len = max(1, N - self.span_len)
            if self.span_len >= N:
                context_len = N // 2
            context = x[:, :context_len]
            target = x[:, context_len:]
            if context.shape[1] < N:
                last_token = context[:, -1:].expand(B, N - context_len)
                context = torch.cat([context, last_token], dim=1)
            psi_real, psi_imag = self.embed(context)

        all_diag: Dict = {}
        for step_idx in range(self.K_train):
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

            (psi_real, psi_imag,
             h1_next, h2_next,
             h1_im_next, h2_im_next,
             qi_mean, diag) = self._unified_step(
                psi_real, psi_imag,
                h1_slice, h2_slice, h1_im_slice, h2_im_slice,
                self.Q_ema.detach())

            # Persist Cord IIR state
            if state_indices is not None and self.training:
                state_indices_l = state_indices.long().view(-1).to(device)
                self.h1_bank.index_copy_(0, state_indices_l, h1_next.detach())
                self.h2_bank.index_copy_(0, state_indices_l, h2_next.detach())
                self.h1_im_bank.index_copy_(0, state_indices_l, h1_im_next.detach())
                self.h2_im_bank.index_copy_(0, state_indices_l, h2_im_next.detach())
            elif state_indices is None:
                self.h1[:B].copy_(h1_next.detach())
                self.h2[:B].copy_(h2_next.detach())
                self.h1_im[:B].copy_(h1_im_next.detach())
                self.h2_im[:B].copy_(h2_im_next.detach())
                # Clamp all IIR state to prevent divergence over long unrolls
                psi_real, psi_imag = self._clamp_iir_state(B, psi_real, psi_imag, clamp_field=False)

            with torch.no_grad():
                self.Q_ema.copy_(PHI_INV * qi_mean + (1.0 - PHI_INV) * self.Q_ema)
                self.Q_trend.copy_(self.Q_ema - qi_mean)

            with torch.no_grad():
                Q_per_pos = diag.get('Q_per_pos')
                if Q_per_pos is not None and Q_per_pos.numel() == self.N:
                    self.Q_bar_pos.copy_(
                        0.99 * self.Q_bar_pos + 0.01 * Q_per_pos.detach())

            if self.training:
                query = F.layer_norm(psi_real, psi_real.shape[-1:])
                n_new = self.pattern_memory.grow(
                    query, self.Q_bar_pos, current_step=self.pattern_step.item())
                if self.pattern_step % 100 == 0:
                    self.pattern_memory.dissolve(current_step=self.pattern_step.item())
                self.pattern_step.add_(1)
                diag['pm_new_neurons'] = diag.get('pm_new_neurons', 0) + n_new

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
            if isinstance(val, torch.Tensor) and val.ndim == 0:
                all_diag[key] = val.item()

        # ── Cross-entropy loss ──
        logits = self.readout_positions(psi_real, psi_imag)
        if mask_ratio > 0:
            ce_fwd = F.cross_entropy(logits[mask], x[mask])
            all_diag['ce_masked'] = ce_fwd.item()
            all_diag['mask_count'] = mask.sum().item()
        else:
            ce_fwd = F.cross_entropy(
                logits[:, context_len:, :].reshape(-1, self.V),
                target.reshape(-1))

        loss = ce_fwd


        # ── Self-supervised losses (training only) ──
        if self.training:
            chakra_loss = self._cross_chakra_alignment_loss(psi_real, psi_imag)
            all_diag['chakra_loss'] = chakra_loss.item()
            loss = loss + self.lambda_chakra * chakra_loss

            if self.qi_quality_ema.item() < 0.9:
                ar_loss = self._field_state_ar_loss(psi_real, psi_imag)
                all_diag['field_ar_loss'] = ar_loss.item()
                loss = loss + self.lambda_field_ar * ar_loss
            else:
                all_diag['field_ar_loss'] = 0.0

        # ── DreamBank episodic store (training only) ──
        if self.training:
            qi_mean_val = all_diag.get('qi_mean', 0.0)
            qi_quality_val = all_diag.get('qi_quality_mean', 0.5)
            # Store a random batch element (not just element 0)
            batch_idx = torch.randint(0, B, (1,)).item() if B > 0 else 0
            self.dream_bank.store(x[batch_idx], qi_mean_val, qi_quality_val, ce_fwd.item())

            # Periodic replay from under-represented Qi state
            if self.dream_bank.should_replay():
                replay_x, replay_elem = self.dream_bank.sample_replay()
                if replay_x is not None and replay_elem is not None:
                    # Replay forward pass in eval mode to skip bidirectional + self-supervised
                    was_training = self.training
                    self.eval()
                    with torch.no_grad():
                        r_loss, r_info = self.training_loss(
                            replay_x, mask_ratio=0.0)
                    if was_training:
                        self.train()
                    loss = loss + self.dream_bank.replay_weight * r_loss
                    all_diag['replay_loss'] = r_loss.item()
                    all_diag['replay_element'] = replay_elem

        # ── Berry phase memory write (training only) ──
        if self.training:
            # Compute Berry phases from final IIR state and store
            yang_phases = BerryPhaseMemory.compute_phases(
                self.h1[:B], self.h2[:B], self.chakra_widths, self.chakra_offsets, self.C)
            yin_phases = BerryPhaseMemory.compute_phases(
                self.h1_im[:B], self.h2_im[:B], self.chakra_widths, self.chakra_offsets, self.C)
            berry_key = F.normalize(torch.cat([yang_phases, yin_phases], dim=-1).mean(dim=0), dim=-1)
            # Compress current field into per-chakra representation
            berry_val = torch.zeros(self.C, self.d_chakra_shared, device=psi_real.device)
            for c in range(self.C):
                start = int(self.chakra_offsets[c].item())
                w = self.chakra_widths[c]
                band = psi_real[:, :, start:start + w].mean(dim=(0, 1))  # [w]
                berry_val[c] = band[:self.d_chakra_shared] if w >= self.d_chakra_shared else \
                    F.pad(band, (0, self.d_chakra_shared - w))
            self.berry_memory.write(berry_key, berry_val)

        # ── Bidirectional losses ──
        # ── Bidirectional / Dual-stream losses ──
        if self.training and self.bidirectional and not self.continuous_mode and mask_ratio == 0:
            # Save forward state
            h1_save, h2_save = self.h1[:B].clone(), self.h2[:B].clone()
            h1i_save, h2i_save = self.h1_im[:B].clone(), self.h2_im[:B].clone()
            Q_ema_save = self.Q_ema.clone()
            qi_pool_save = self.qi_pool.clone()
            qi_pool_peak_save = self.qi_pool_peak.clone()
            qi_quality_ema_save = self.qi_quality_ema.clone()

            # ── Yin stream: K_train steps on reversed sequence ──
            x_rev = torch.flip(x, dims=[1])
            psi_yi_re, psi_yi_im = self.embed(x_rev)

            # Yang stream: reuse forward psi directly (no redundant evolution).
            # The forward pass already ran K_train steps — one more adds little.
            psi_yg_re, psi_yg_im = psi_real.clone(), psi_imag.clone()

            self._current_delta_rho = None
            self._current_delta_theta = None
            self._current_delta_gamma = None

            for _ in range(self.K_train):
                h1_sl = self.h1[:B].detach().clone()
                h2_sl = self.h2[:B].detach().clone()
                h1i_sl = self.h1_im[:B].detach().clone()
                h2i_sl = self.h2_im[:B].detach().clone()
                (psi_yi_re, psi_yi_im, h1n, h2n, h1in, h2in,
                 _, _) = self._unified_step(
                    psi_yi_re, psi_yi_im,
                    h1_sl, h2_sl, h1i_sl, h2i_sl,
                    self.Q_ema.detach(), write_memory=False)
                self.h1[:B].copy_(h1n.detach())
                self.h2[:B].copy_(h2n.detach())
                self.h1_im[:B].copy_(h1in.detach())
                self.h2_im[:B].copy_(h2in.detach())
                psi_yi_re, psi_yi_im = self._clamp_iir_state(B, psi_yi_re, psi_yi_im, clamp_field=False)

                # Corpus callosum: streams exchange compressed perspectives
                if self.corpus_callosum is not None:
                    cc_yg, cc_yi = self.corpus_callosum.exchange(psi_yg_re, psi_yi_re)
                    psi_yg_re = psi_yg_re + PHI_INV * cc_yg
                    psi_yi_re = psi_yi_re + PHI_INV * cc_yi

            # ── Readout both streams ──
            logits_yg = self.readout_positions(psi_yg_re, psi_yg_im)
            logits_yi = self.readout_positions(psi_yi_re, psi_yi_im)

            # ── Arbitration merges per-vocab-dim trust weights ──
            if self.arbitration is not None:
                yang_weight = self.arbitration(psi_yg_re, psi_yi_re)  # [B, V]
                yg_w = yang_weight.unsqueeze(1)  # [B, 1, V]
                logits_dual = yg_w * logits_yg + (1.0 - yg_w) * logits_yi

                target_rev_prefix = torch.flip(x[:, :context_len], dims=[1])
                target_bwd = target_rev_prefix[:, :self.span_len] if self.span_len < self.N else target_rev_prefix[:, :self.N // 2]
                ce_dual = F.cross_entropy(
                    logits_dual[:, context_len:, :].reshape(-1, self.V),
                    target_bwd.reshape(-1))

                breath_yang = torch.sin(self.breath_t_yang)
                breath_yin = torch.sin(self.breath_t_yin)
                yang_gate = torch.sigmoid((breath_yang - 0.3) / 0.1)
                yin_gate = torch.sigmoid((-breath_yin - 0.3) / 0.1)
                loss = yang_gate * loss + yin_gate * self.lambda_backward * ce_dual

                psi_yi_unflip_re = torch.flip(psi_yi_re, dims=[1])
                psi_yi_unflip_im = torch.flip(psi_yi_im, dims=[1])
                consistency = ((psi_yg_re - psi_yi_unflip_re) ** 2
                               + (psi_yg_im - psi_yi_unflip_im) ** 2).mean()
                loss = loss + self.lambda_consistency * consistency

                all_diag['ce_dual'] = ce_dual.detach().item()
                all_diag['yang_weight_mean'] = yang_weight.mean().detach().item()
                all_diag['consistency'] = consistency.detach().item()

            # Restore forward state
            self.h1[:B].copy_(h1_save)
            self.h2[:B].copy_(h2_save)
            self.h1_im[:B].copy_(h1i_save)
            self.h2_im[:B].copy_(h2i_save)
            self.Q_ema.copy_(Q_ema_save)
            self.qi_pool.copy_(qi_pool_save)
            self.qi_pool_peak.copy_(qi_pool_peak_save)
            self.qi_quality_ema.copy_(qi_quality_ema_save)

        all_diag['ce_loss'] = ce_fwd.item()
        all_diag['loss'] = loss.item()
        all_diag['Q_mean'] = all_diag.get('Q_mean', 0.0)  # backward compat — now qi_mean

        return loss, all_diag

    # ════════════════════════════════════════════════
    #  Generation
    # ════════════════════════════════════════════════

    @torch.no_grad()
    def generate_autoregressive(self, seed: torch.Tensor, max_new: int = 128,
                                temp: float = 0.8, K_init: Optional[int] = None,
                                repetition_penalty: float = 1.2,
                                rep_window: int = 8,
                                top_k: Optional[int] = None,
                                ngram_block_size: int = 0) -> torch.Tensor:
        """Generate bytes autoregressively."""
        if K_init is None:
            K_init = self.K_gen
        device = seed.device
        self.eval()
        self.reset_iir_state()
        self.resonant_field.resize_buffers(1, device, self.h1.dtype)
        self.multi_scale_cord.resize_buffers(1, device, self.h1.dtype)
        self.tonic_phasic.resize_buffers(1)
        self._current_delta_rho = None
        self._current_delta_theta = None
        self._current_delta_gamma = None

        # Ensure seed is 1D [L]
        if seed.ndim > 1:
            seed = seed.squeeze(0)
        L = seed.numel()
        if L < self.N:
            pad = seed[-1:].expand(self.N - L)
            window = torch.cat([seed, pad])
        else:
            window = seed[-self.N:]
        batch = window.unsqueeze(0)

        # Settle
        psi_real, psi_imag = self.embed(batch)
        for _ in range(K_init):
            h1_sl = self.h1[:1].detach().clone()
            h2_sl = self.h2[:1].detach().clone()
            h1i_sl = self.h1_im[:1].detach().clone()
            h2i_sl = self.h2_im[:1].detach().clone()
            (psi_real, psi_imag, h1n, h2n, h1in, h2in,
             _, _) = self._unified_step(
                psi_real, psi_imag, h1_sl, h2_sl, h1i_sl, h2i_sl,
                self.Q_ema.detach())
            self.h1[:1].copy_(h1n)
            self.h2[:1].copy_(h2n)
            self.h1_im[:1].copy_(h1in)
            self.h2_im[:1].copy_(h2in)

        # Generate
        generated = []
        window_list = list(window.tolist())
        for _ in range(max_new):
            batch = torch.tensor(window_list, dtype=torch.long, device=device).unsqueeze(0)
            psi_real, psi_imag = self.embed(batch)
            h1_sl = self.h1[:1].detach().clone()
            h2_sl = self.h2[:1].detach().clone()
            h1i_sl = self.h1_im[:1].detach().clone()
            h2i_sl = self.h2_im[:1].detach().clone()
            (psi_real, psi_imag, h1n, h2n, h1in, h2in,
             _, _) = self._unified_step(
                psi_real, psi_imag, h1_sl, h2_sl, h1i_sl, h2i_sl,
                self.Q_ema.detach())
            self.h1[:1].copy_(h1n)
            self.h2[:1].copy_(h2n)
            self.h1_im[:1].copy_(h1in)
            self.h2_im[:1].copy_(h2in)

            logits = self.readout_positions(psi_real, psi_imag)[0, -1, :] / max(temp, 1e-6)

            if generated and repetition_penalty != 1.0:
                for b in set(generated[-rep_window:]):
                    logits[b] /= repetition_penalty
            if ngram_block_size > 0 and len(generated) >= ngram_block_size - 1:
                recent = generated[-rep_window:]
                prefix = generated[-(ngram_block_size - 1):] if ngram_block_size > 1 else []
                for tok in range(self.V):
                    for i in range(len(recent) - ngram_block_size + 1):
                        if tuple(recent[i:i + ngram_block_size]) == tuple(prefix + [tok]):
                            logits[tok] = -float('inf')
                            break
            if top_k is not None and top_k > 0:
                v, _ = torch.topk(logits, min(top_k, self.V))
                logits[logits < v[-1]] = -float('inf')

            next_byte = torch.multinomial(F.softmax(logits, dim=-1), 1).item()
            generated.append(next_byte)
            window_list.pop(0)
            window_list.append(next_byte)

        return torch.tensor(generated, dtype=torch.long, device=device)

    @torch.no_grad()
    def generate_parallel(self, seed: torch.Tensor, max_len: int = 128,
                          temp: float = 0.8, K_init: Optional[int] = None,
                          top_k: Optional[int] = None) -> torch.Tensor:
        """Generate bytes in parallel — one field evolution, all positions at once.

        Instead of N sequential autoregressive steps, we seed the first L
        positions with known bytes and zero-fill the rest, then evolve the
        full field for K steps.  Spatial coupling and self-prediction
        propagate information from the seed across the empty positions.
        Readout once, sample all new positions.
        """
        if K_init is None:
            K_init = self.K_gen
        device = seed.device
        self.eval()
        self.reset_iir_state()
        self.resonant_field.resize_buffers(1, device, self.h1.dtype)
        self.multi_scale_cord.resize_buffers(1, device, self.h1.dtype)
        self.tonic_phasic.resize_buffers(1)
        self._current_delta_rho = None
        self._current_delta_theta = None
        self._current_delta_gamma = None

        L = seed.numel()
        N = self.N
        if L >= max_len:
            return seed[:max_len]

        # Always build a full N-position window — the field operates on N.
        # Positions beyond max_len are masked to byte 0 (NUL).
        window = seed.new_zeros(N, dtype=torch.long)
        window[:L] = seed[:L]
        batch = window.unsqueeze(0)

        # Embed + settle
        psi_real, psi_imag = self.embed(batch)
        h1_sl = self.h1[:1].detach().clone()
        h2_sl = self.h2[:1].detach().clone()
        h1i_sl = self.h1_im[:1].detach().clone()
        h2i_sl = self.h2_im[:1].detach().clone()
        q_ema = self.Q_ema.detach().clone()
        # ── Clamping guard ──
        # HSA 0x1016 crash occurs during generation at d=256 when 50 unrolled
        # _unified_step calls (K_gen default) let IIR state accumulate unbounded
        # NaN/Inf, which propagates into multinomial/softmax kernels and triggers
        # a hardware exception. Clamp to [-max_val, +max_val] after every step
        # and reset to zero on NaN/Inf detection. K_gen default lowered from 50
        # to 3 (matching K_train); override via --k-gen.

        max_val = 10.0 * F.softplus(self.field_scale)
        for step in range(K_init):
            (psi_real, psi_imag,
             h1_sl, h2_sl, h1i_sl, h2i_sl,
             Q_mean, _) = self._unified_step(
                psi_real, psi_imag,
                h1_sl, h2_sl, h1i_sl, h2i_sl, q_ema)
            # Ripple: structured exploration after half the settling steps
            if step >= K_init // 2 and self.qi_quality_ema.item() < 0.8:
                rip_re, rip_im = self._compute_ripple(
                    psi_real, psi_imag, probe_scale=0.01)
                psi_real = psi_real + 0.062 * rip_re
                psi_imag = psi_imag + 0.062 * rip_im
            q_ema = PHI_INV * Q_mean + (1.0 - PHI_INV) * q_ema
            # NaN/Inf safety: detect and reset if IIR state goes non-finite
            if not torch.isfinite(Q_mean) or not torch.isfinite(h1_sl).all() \
                    or not torch.isfinite(h2_sl).all() or not torch.isfinite(h1i_sl).all() \
                    or not torch.isfinite(h2i_sl).all():
                # Reset all IIR state to zero
                h1_sl = torch.zeros_like(h1_sl)
                h2_sl = torch.zeros_like(h2_sl)
                h1i_sl = torch.zeros_like(h1i_sl)
                h2i_sl = torch.zeros_like(h2i_sl)
                for name in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                             'x_prev_real', 'x_prev_imag'):
                    getattr(self.resonant_field, name)[:1].zero_()
                for k in range(self.multi_scale_cord.K):
                    for comp in ('re', 'im'):
                        getattr(self.multi_scale_cord, f'h_{comp}_{k}')[:1].zero_()
                self.tonic_phasic.psi_tonic_re[:1].zero_()
                self.tonic_phasic.psi_tonic_im[:1].zero_()
            else:
                # Clamp IIR state to prevent unbounded accumulation
                h1_sl = h1_sl.clamp(-max_val, max_val)
                h2_sl = h2_sl.clamp(-max_val, max_val)
                h1i_sl = h1i_sl.clamp(-max_val, max_val)
                h2i_sl = h2i_sl.clamp(-max_val, max_val)
                for name in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                             'x_prev_real', 'x_prev_imag'):
                    getattr(self.resonant_field, name)[:1].clamp_(-max_val, max_val)
                for k in range(self.multi_scale_cord.K):
                    for comp in ('re', 'im'):
                        getattr(self.multi_scale_cord, f'h_{comp}_{k}')[:1].clamp_(-max_val, max_val)
                self.tonic_phasic.psi_tonic_re[:1].clamp_(-max_val, max_val)
                self.tonic_phasic.psi_tonic_im[:1].clamp_(-max_val, max_val)


        # Final safety net: replace any remaining NaN/Inf in field state before readout
        psi_real = torch.nan_to_num(psi_real, nan=0.0, posinf=max_val, neginf=-max_val)
        psi_imag = torch.nan_to_num(psi_imag, nan=0.0, posinf=max_val, neginf=-max_val)

        # Readout all positions at once
        logits_all = self.readout_positions(psi_real, psi_imag)[0]  # [N, V]
        logits_all = logits_all / max(temp, 1e-6)

        # Sample positions beyond the seed, up to max_len
        generated = window.clone()
        sample_end = min(max_len, N)
        for pos in range(L, sample_end):
            logits = logits_all[pos]
            if top_k is not None and top_k > 0:
                v, _ = torch.topk(logits, min(top_k, self.V))
                logits[logits < v[-1]] = -float('inf')
            probs = F.softmax(logits, dim=-1)
            generated[pos] = torch.multinomial(probs, 1)

        return generated[:max_len]

    # ════════════════════════════════════════════════
    #  State Management
    # ════════════════════════════════════════════════

    def reset_iir_state(self) -> None:
        """Clear only IIR state buffers, preserving running statistics.
        
        Resets: h1/h2/h1_im/h2_im (IIR traces), submodule IIR state.
        Preserves: Q_ema, Q_trend, Q_bar_pos, qi_ema, breath phase (learned statistics).
        """
        self.h1.zero_()
        self.h2.zero_()
        self.h1_im.zero_()
        self.h2_im.zero_()
        if self.state_bank_size > 0:
            self.h1_bank.zero_()
            self.h2_bank.zero_()
            self.h1_im_bank.zero_()
            self.h2_im_bank.zero_()
        # Reset submodule IIR state only
        self.resonant_field.reset_state()
        self.multi_scale_cord.reset_state()
        self.tonic_phasic.reset_state()
        # Clear modulation cache
        self._current_delta_rho = None
        self._current_delta_theta = None
        self._current_delta_gamma = None

    def reset_state(self) -> None:
        """Clear all persistent field and brain state (full reset).
        
        Use sparingly — this wipes learned running statistics.
        Prefer reset_iir_state() for normal batch boundaries.
        """
        self.reset_iir_state()
        # Also reset running statistics
        self.Q_ema.zero_()
        self.Q_trend.zero_()
        self.Q_bar_pos.zero_()
        self.pattern_memory.qi_ema.zero_()
        self.breath_t_yang.zero_()
        self.breath_t_yin.zero_()
        self.brain_tuner.reset_state()
        self.heartbeat.reset()
    def _clamp_iir_state(self, B: int, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                         clamp_field: bool = True) -> Tuple[torch.Tensor, torch.Tensor]:
        """Clamp all IIR state to prevent NaN/Inf divergence over long unrolls.

        Covers: field state (psi_real, psi_imag), cord IIR (h1/h2/h1_im/h2_im),
        ResonantField persistent buffers, MultiScaleCord delay lines,
        and TonicPhasic tonic buffers.
        
        Args:
            B: batch size
            psi_real, psi_imag: field state tensors
            clamp_field: if True, also clamp psi_real/psi_imag (set False during training
                        to preserve gradient flow through field state)
        """
        max_val = (10.0 * F.softplus(self.field_scale.detach())).item()
        # Field state
        if clamp_field:
            psi_real = psi_real.clamp(-max_val, max_val)
            psi_imag = psi_imag.clamp(-max_val, max_val)
        else:
            # Training mode: soft-clamp with tanh to prevent unbounded growth
            # while preserving differentiable gradient flow
            psi_real = max_val * torch.tanh(psi_real / max_val)
            psi_imag = max_val * torch.tanh(psi_imag / max_val)
        # Cord IIR
        with torch.no_grad():
            self.h1[:B].clamp_(-max_val, max_val)
            self.h2[:B].clamp_(-max_val, max_val)
            self.h1_im[:B].clamp_(-max_val, max_val)
            self.h2_im[:B].clamp_(-max_val, max_val)
            # ResonantField
            for name in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                         'x_prev_real', 'x_prev_imag'):
                getattr(self.resonant_field, name)[:B].clamp_(-max_val, max_val)
            # MultiScaleCord delay lines
            for k in range(self.multi_scale_cord.K):
                for comp in ('re', 'im'):
                    getattr(self.multi_scale_cord, f'h_{comp}_{k}')[:B].clamp_(-max_val, max_val)
            # TonicPhasic
            self.tonic_phasic.psi_tonic_re[:B].clamp_(-max_val, max_val)
            self.tonic_phasic.psi_tonic_im[:B].clamp_(-max_val, max_val)
            # NaN/Inf guard: reset to zero if any tensor is non-finite
            if not torch.isfinite(psi_real).all() or not torch.isfinite(psi_imag).all():
                psi_real = torch.zeros_like(psi_real)
                psi_imag = torch.zeros_like(psi_imag)
                self.h1[:B].zero_(); self.h2[:B].zero_()
                self.h1_im[:B].zero_(); self.h2_im[:B].zero_()
                for name in ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                             'x_prev_real', 'x_prev_imag'):
                    getattr(self.resonant_field, name)[:B].zero_()
                for k in range(self.multi_scale_cord.K):
                    for comp in ('re', 'im'):
                        getattr(self.multi_scale_cord, f'h_{comp}_{k}')[:B].zero_()
                self.tonic_phasic.psi_tonic_re[:B].zero_()
                self.tonic_phasic.psi_tonic_im[:B].zero_()
        return psi_real, psi_imag

    def _evolve_one_step(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                         q_ema: torch.Tensor, clamp_field: bool = True
                         ) -> Tuple[torch.Tensor, torch.Tensor]:
        """One evolution step with IIR state persistence and clamping.

        Clones IIR state (h1/h2/h1_im/h2_im), calls _unified_step, copies
        results back to persistent buffers, and clamps to prevent divergence.

        Intended for inference generation — the training path manages state
        differently (state bank, gradients on field state).

        Args:
            psi_real, psi_imag: [1, N, d] field state.
            q_ema: Scalar Q EMA tensor (from self.Q_ema.detach()).
            clamp_field: Whether to hard-clamp field state (True for readout,
                        False for seed accumulation to preserve amplitude).

        Returns:
            (psi_real, psi_imag) after step + clamp.
        """
        h1_sl = self.h1[:1].detach().clone()
        h2_sl = self.h2[:1].detach().clone()
        h1i_sl = self.h1_im[:1].detach().clone()
        h2i_sl = self.h2_im[:1].detach().clone()
        (psi_real, psi_imag,
         h1n, h2n, h1in, h2in,
         _, _) = self._unified_step(
            psi_real, psi_imag,
            h1_sl, h2_sl, h1i_sl, h2i_sl, q_ema)
        self.h1[:1].copy_(h1n)
        self.h2[:1].copy_(h2n)
        self.h1_im[:1].copy_(h1in)
        self.h2_im[:1].copy_(h2in)
        return self._clamp_iir_state(1, psi_real, psi_imag,
                                     clamp_field=clamp_field)

    @torch.no_grad()
    def _compute_ripple(self, psi_real: torch.Tensor, psi_imag: torch.Tensor,
                        probe_scale: float = 0.01) -> Tuple[torch.Tensor, torch.Tensor]:
        """Compute the Cord's resonant sensitivity direction.

        Runs _unified_step on the field and on a slightly-noised copy.
        The difference is the "ripple" — directions the Cord is actually
        sensitive to. Concentrates exploration where the model has structure.

        Args:
            psi_real, psi_imag: [1, N, d] field state.
            probe_scale: std of the probe noise.

        Returns:
            ripple_re, ripple_im: [1, N, d] normalized sensitivity direction.
        """
        h1_sl = self.h1[:1].detach().clone()
        h2_sl = self.h2[:1].detach().clone()
        h1i_sl = self.h1_im[:1].detach().clone()
        h2i_sl = self.h2_im[:1].detach().clone()
        # Save qi pool state (ripple probes mutate persistent qi buffers)
        qi_pool_save = self.qi_pool.clone()
        qi_peak_save = self.qi_pool_peak.clone()
        qi_qual_save = self.qi_quality_ema.clone()

        # Clean pass
        pr_c, pi_c, _, _, _, _, _, _ = self._unified_step(
            psi_real, psi_imag, h1_sl, h2_sl, h1i_sl, h2i_sl,
            self.Q_ema.detach(), write_memory=False)

        # Noised pass
        noise = torch.randn_like(psi_real) * probe_scale
        pr_n, pi_n, _, _, _, _, _, _ = self._unified_step(
            psi_real + noise, psi_imag + noise,
            h1_sl, h2_sl, h1i_sl, h2i_sl,
            self.Q_ema.detach(), write_memory=False)

        # Restore qi pool state
        self.qi_pool.copy_(qi_pool_save)
        self.qi_pool_peak.copy_(qi_peak_save)
        self.qi_quality_ema.copy_(qi_qual_save)

        # Ripple = difference in response, normalized
        ripple_re = pr_n - pr_c
        ripple_im = pi_n - pi_c
        norm = (ripple_re.pow(2) + ripple_im.pow(2)).sum(dim=-1, keepdim=True).sqrt().clamp_min(1e-8)
        return ripple_re / norm, ripple_im / norm

    @torch.no_grad()
    def _sample_with_penalties(self, logits: torch.Tensor,
                               generated: list,
                               repetition_penalty: float = 1.0,
                               rep_window: int = 8,
                               ngram_block_size: int = 0,
                               top_k: Optional[int] = None) -> int:
        """Apply penalties to [V] logits and sample one token.

        Mutates logits in place — caller should pass a slice/view that
        won't be reused, or clone() before calling.

        Args:
            logits: [V] logit tensor (should already be temperature-scaled).
            generated: List of tokens generated so far (for penalty context).

        Returns:
            Sampled token index (int).
        """
        if repetition_penalty != 1.0 and generated:
            for b in set(generated[-rep_window:]):
                logits[b] /= repetition_penalty
        if ngram_block_size > 0 and len(generated) >= ngram_block_size - 1:
            recent = generated[-rep_window:]
            prefix = generated[-(ngram_block_size - 1):] if ngram_block_size > 1 else []
            for tok in range(self.V):
                for i in range(len(recent) - ngram_block_size + 1):
                    if tuple(recent[i:i + ngram_block_size]) == tuple(prefix + [tok]):
                        logits[tok] = -float('inf')
                        break
        if top_k is not None and top_k > 0:
            v, _ = torch.topk(logits, min(top_k, self.V))
            logits[logits < v[-1]] = -float('inf')
        return torch.multinomial(F.softmax(logits, dim=-1, dtype=torch.float32), 1).item()

    @torch.no_grad()
    def _condense(self, B: int, hard_reset: bool = True) -> None:
        """Condense accumulated field state into weight deltas.
        
        The IIR traces (h1, h2, h1_im, h2_im) carry history across batches.
        We project accumulated experience into gradient-free weight updates.
        
        hard_reset=True: clear IIR state after condensation (batch boundary).
        hard_reset=False: apply φ⁻¹ dampening instead — preserves field
                          continuity while solidifying patterns into weights.
        
        Scale is φ⁻¹ / (1 + |h1|):
          Large state → small step (safety); fresh state → large step (learning).
        """
        h1_norm = self.h1[:B].norm()
        if h1_norm < 0.1:
            return
        
        deltas = self.condenser(
            self.h1[:B], self.h2[:B],
            self.h1_im[:B], self.h2_im[:B])
        
        scale = PHI_INV / (1.0 + h1_norm.item())
        
        # ── Readout weights (Band 1) ──
        if self.readout_y is not None:
            self.readout_y.weight.data.add_(scale * deltas['readout_y.weight'].unsqueeze(0))
            self.readout_z.weight.data.add_(scale * deltas['readout_z.weight'].unsqueeze(0))
            self.readout_bwd_y.weight.data.add_(scale * deltas['readout_bwd_y.weight'].unsqueeze(0))
            self.readout_bwd_z.weight.data.add_(scale * deltas['readout_bwd_z.weight'].unsqueeze(0))
        
        # ── Pattern memory seeds (Band 2) ──
        pm = self.pattern_memory
        if pm.born.any():
            born_idx = torch.nonzero(pm.born, as_tuple=False).view(-1)
            util = pm.usage[born_idx].float() / (pm.age[born_idx].float() + 1.0)
            best = born_idx[util.argmax()]
        else:
            unborn = torch.nonzero(~pm.born, as_tuple=False).view(-1)
            if unborn.numel() == 0:
                unborn = torch.tensor([0], device=pm.born.device)
            best = unborn[0]
        
        pm.keys.data[best] = pm.keys.data[best] + scale * deltas['pattern_key']
        pm.values_real.data[best] = pm.values_real.data[best] + scale * deltas['pattern_val_re']
        pm.values_imag.data[best] = pm.values_imag.data[best] + scale * deltas['pattern_val_im']
        if not pm.born[best]:
            pm.born.data[best] = True
            pm.birth_step.data[best] = self.pattern_step
        pm.usage.data[best] += 1
        
        # ── Scalar homeostasis (Band 4) ──
        dh = deltas['homeo'] * scale
        self.stiffness_Q.data.add_(dh[0])
        self.stiffness_E.data.add_(dh[1])
        self.stiffness_B.data.add_(dh[2])
        self.field_scale.data.add_(dh[3])
        self.noise_scale.data.add_(dh[4])
        self.qi_flow.beta_logit.data.add_(dh[5])
        self.qi_flow.eta_logit.data.add_(dh[6])
        
        # ── State management ──
        if hard_reset:
            self.reset_iir_state()
        else:
            dampen = PHI_INV
            self.h1[:B].data.mul_(dampen)
            self.h2[:B].data.mul_(dampen)
            self.h1_im[:B].data.mul_(dampen)
            self.h2_im[:B].data.mul_(dampen)
    
    @torch.no_grad()
    def condense_and_reset(self, B: int) -> None:
        """Condense and hard-reset IIR state (standard batch boundary)."""
        self._condense(B, hard_reset=True)
    
    @torch.no_grad()
    def soft_condense(self, B: int) -> None:
        """Condense without reset — dampen instead (continuous field mode)."""
        self._condense(B, hard_reset=False)


    # ════════════════════════════════════════════════
    #  Checkpoint Compatibility
    # ════════════════════════════════════════════════

    def _normalize_state_dict(self, state_dict, initialized_keys=None, verbose=False):
        """Normalize checkpoints — adapted from TripartiteCord."""
        def _log(msg):
            if verbose:
                print(f'  [normalize] {msg}')

        # Drop stale keys from older architectures
        stale_prefixes = ['transceivers', 'cross_chakra', 'residuals',
                          'controller', 'qi_dynamics', 'ctrl_mod',
                          'breath', 'Q_field', 'cord', 'cord_history',
                          'prediction', 'brain_step', 'brain.brain_h']
        for prefix in stale_prefixes:
            for key in list(state_dict.keys()):
                if key.startswith(prefix + '.') or key == prefix:
                    del state_dict[key]
                    _log(f'dropped stale key {key}')

        # Resize Cord IIR buffers
        for key in ('h1', 'h2', 'h1_im', 'h2_im'):
            if key in state_dict and hasattr(self, key):
                old, target = state_dict[key], getattr(self, key)
                if tuple(old.shape) != tuple(target.shape):
                    new = target.data.clone()
                    new[:min(old.shape[0], target.shape[0])] = old[:min(old.shape[0], target.shape[0])]
                    state_dict[key] = new
                    _log(f'resized {key}')

        # Resize state bank buffers
        for key in ('h1_bank', 'h2_bank', 'h1_im_bank', 'h2_im_bank'):
            if key in state_dict and hasattr(self, key):
                old, target = state_dict[key], getattr(self, key)
                if tuple(old.shape) != tuple(target.shape):
                    new = target.data.clone()
                    new[:min(old.shape[0], target.shape[0])] = old[:min(old.shape[0], target.shape[0])]
                    state_dict[key] = new
                    _log(f'resized {key}')

        # Pattern memory buffers
        pm_buffer_names = QiPatternMemory.get_checkpoint_buffer_names()
        for buf_name in pm_buffer_names:
            key = f'pattern_memory.{buf_name}'
            if key in state_dict and hasattr(self.pattern_memory, buf_name):
                old, target = state_dict[key], getattr(self.pattern_memory, buf_name)
                if tuple(old.shape) != tuple(target.shape):
                    new = target.data.clone()
                    new[:min(old.shape[0], target.shape[0])] = old[:min(old.shape[0], target.shape[0])]
                    state_dict[key] = new
                    _log(f'resized PM {key}')

        # Drop transient PM buffers with shape mismatch
        for key in list(state_dict.keys()):
            if key == 'pattern_memory.qi_ema' and hasattr(self, 'pattern_memory'):
                if key in state_dict:
                    target = self.pattern_memory.qi_ema
                    if tuple(state_dict[key].shape) != tuple(target.shape):
                        del state_dict[key]
                        _log(f'dropped transient PM buffer {key}')


        # Resize submodule persistent buffers (batch dimension)
        submodule_buffers = {
            'resonant_field': ('h_real', 'h_imag', 'h_prev_real', 'h_prev_imag',
                               'x_prev_real', 'x_prev_imag'),
            'multi_scale_cord': ('h_re_0', 'h_im_0', 'h_re_1', 'h_im_1',
                                 'h_re_2', 'h_im_2', 'h_re_3', 'h_im_3',
                                 'h_re_4', 'h_im_4'),
            'tonic_phasic': ('psi_tonic_re', 'psi_tonic_im'),
            'brain_tuner': ('brain_h',),
        }
        for mod_name, buf_names in submodule_buffers.items():
            for buf_name in buf_names:
                key = f'{mod_name}.{buf_name}'
                if key in state_dict:
                    # Traverse to find target buffer
                    parts = key.split('.')
                    target = self
                    for p in parts:
                        target = getattr(target, p)
                    if tuple(state_dict[key].shape) != tuple(target.shape):
                        new = target.data.clone()
                        n_b = min(state_dict[key].shape[0], target.shape[0])
                        new[:n_b] = state_dict[key][:n_b]
                        state_dict[key] = new
                        _log(f'resized {key} to {tuple(new.shape)}')
        # Reset transient state buffers that can accumulate overflow
        # from pre-damping-fix checkpoints. These are EMA accumulators
        # and running statistics that are safe to zero-initialize.
        reset_buffers = {
            'tonic_phasic.psi_tonic_re': 'zeros_like',
            'tonic_phasic.psi_tonic_im': 'zeros_like',
            'pattern_memory.qi_mean': 0.0,
            'pattern_memory.qi_std': 1.0,
        }
        for key, default in reset_buffers.items():
            if key in state_dict:
                # Access the target buffer to get its shape
                parts = key.split('.')
                target = self
                for p in parts:
                    target = getattr(target, p)
                if isinstance(default, str) and default == 'zeros_like':
                    state_dict[key] = torch.zeros_like(target.data)
                else:
                    state_dict[key] = torch.full_like(target.data, default)
                _log(f'reset {key} to default')

        # Step 1: Drop tensors with shape mismatches (architecture changed).
        # Must run BEFORE missing-init so dropped keys get reinitialized.
        n_shape_mismatch = 0
        all_params = dict(self.named_parameters())
        all_bufs = dict(self.named_buffers())
        for key in list(state_dict.keys()):
            target = all_params.get(key)
            if target is None:
                target = all_bufs.get(key)
            if target is not None and tuple(state_dict[key].shape) != tuple(target.shape):
                _log(f'shape mismatch {key}: ckpt {tuple(state_dict[key].shape)} '
                     f'vs model {tuple(target.shape)}')
                del state_dict[key]
                n_shape_mismatch += 1
        if n_shape_mismatch:
            _log(f'dropped {n_shape_mismatch} shape-mismatched tensors (will reinitialize)')

        # Step 1b: Override stale offset/width-derived buffers.
        # These are deterministically computed from self.chakra_widths — old
        # checkpoint values from a different width layout will be wrong even if
        # their shape matches. Always replace with the current live value.
        n_overridden = 0
        for key in list(state_dict.keys()):
            if ('offsets' in key or 'ch_offsets' in key or 'chakra_id' in key) and key in all_bufs:
                current = all_bufs[key]
                if not torch.equal(state_dict[key], current):
                    state_dict[key] = current.clone()
                    n_overridden += 1
        if n_overridden:
            _log(f'overrode {n_overridden} stale offset buffer(s)')
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
            if name in state_dict:
                continue
            # Check if this buffer is non-persistent at its owning submodule level.
            # Non-persistent buffers (registered with persistent=False) are regenerated
            # by forward passes and must NOT be added here — they'd cause 'unexpected key'
            # errors in load_state_dict since they don't appear in state_dict().
            parts = name.split('.')
            if len(parts) > 1:
                parent = self
                for p in parts[:-1]:
                    parent = getattr(parent, p)
                buf_short = parts[-1]
                if buf_short in parent._non_persistent_buffers_set:
                    continue
            else:
                if name in self._non_persistent_buffers_set:
                    continue
            state_dict[name] = buf.data.clone()
            initialized_keys.add(name)
            n_missing_buffers += 1
        if n_missing_params or n_missing_buffers:
            _log(f'initialized {n_missing_params} missing param(s) and '
                 f'{n_missing_buffers} missing buffer(s)')

        return state_dict

    def load_state_dict(self, state_dict, strict=False, assign=False):
        initialized = set()
        state_dict = self._normalize_state_dict(state_dict, initialized_keys=initialized,
                                                verbose=False)
        missing, unexpected = super().load_state_dict(state_dict, strict=strict, assign=assign)
        if initialized:
            print(f'Initialized {len(initialized)} missing tensors from defaults')
        if unexpected:
            print(f'Dropped {len(unexpected)} unexpected tensors from checkpoint')
        return missing, unexpected


# ════════════════════════════════════════════════
#  Smoke test
# ════════════════════════════════════════════════

if __name__ == '__main__':
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    m = MuonCord(N=4, d=64, brain_shells=3, brain_D=64, max_batch_size=8).to(device)
    x = torch.randint(0, 256, (2, 4)).to(device)
    loss, info = m.training_loss(x, no_reset=False)
    assert torch.isfinite(loss), f"Loss is not finite: {loss}"
    loss.backward()
    print('MuonCord smoke tests passed.')
    print(f"  Loss: {loss.item():.4f}")
    print(f"  Q_mean: {info.get('Q_mean', 'N/A')}")
    print(f"  Params: {sum(p.numel() for p in m.parameters()):,}")
