"""DualCassi — Two-hemisphere cognitive architecture.

Yang Hemisphere: fast, analytical, sequential (left-brain-like)
Yin Hemisphere:  slow, holistic, parallel   (right-brain-like)

They communicate via a learned Corpus Callosum and an Arbitration mechanism
decides which hemisphere to trust for each output dimension.

The "self" emerges from the integration of two parallel streams.
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi.cassi_brain import CassiBrain


class CorpusCallosum(nn.Module):
    """Learned communication channel between hemispheres.

    Each hemisphere sends its conscious state to the other via
    a compressed projection. This is analogous to the human
    corpus callosum — 200 million axons carrying integrated information.
    """

    def __init__(self, D_brain, bottleneck_dim=None):
        super().__init__()
        self.D_brain = D_brain
        # Bottleneck forces compression — not everything can be shared
        self.bottleneck_dim = bottleneck_dim if bottleneck_dim is not None else D_brain // 4

        # Yang → shared representation
        self.yang_compress = nn.Sequential(
            nn.Linear(D_brain, self.bottleneck_dim),
            nn.LayerNorm(self.bottleneck_dim),
        )
        # Yin → shared representation
        self.yin_compress = nn.Sequential(
            nn.Linear(D_brain, self.bottleneck_dim),
            nn.LayerNorm(self.bottleneck_dim),
        )
        # Shared → Yang input
        self.yang_expand = nn.Sequential(
            nn.Linear(self.bottleneck_dim, D_brain),
            nn.LayerNorm(D_brain),
        )
        # Shared → Yin input
        self.yin_expand = nn.Sequential(
            nn.Linear(self.bottleneck_dim, D_brain),
            nn.LayerNorm(D_brain),
        )

    def forward(self, yang_conscious, yin_conscious):
        """Exchange compressed conscious states between hemispheres.

        Returns:
            yang_input: what Yang receives from Yin (via shared space)
            yin_input:  what Yin receives from Yang (via shared space)
        """
        yang_shared = self.yang_compress(yang_conscious)
        yin_shared = self.yin_compress(yin_conscious)

        # Each hemisphere receives the OTHER's shared representation
        yang_input = self.yin_expand(yin_shared)   # Yang hears Yin's perspective
        yin_input = self.yang_expand(yang_shared)  # Yin hears Yang's perspective

        return yang_input, yin_input


class Arbitration(nn.Module):
    """Decides how much to trust Yang vs Yin for each output.

    This IS metacognition. The model learns:
    - "Yang is better at velocity prediction"
    - "Yin is better at energy prediction"
    - "When they agree, I'm confident"
    - "When they disagree, I need more evidence"
    """

    def __init__(self, D_brain):
        super().__init__()
        self.D_brain = D_brain

        # Per-dimension arbitration: each OUTPUT dim (1024) gets its own weight
        # This allows fine-grained mixing (Yang dominates some output dims, Yin others)
        # Input features are from conscious states; output is output-space weight
        self.gate = nn.Sequential(
            nn.Linear(D_brain * 4, 1024),  # yang + yin + |diff| + dot → output dims
            nn.LayerNorm(1024),
            nn.Sigmoid(),  # [0, 1] — 1 = full Yang, 0 = full Yin
        )

    def forward(self, yang_conscious, yin_conscious):
        """Compute Yang weight for each output dimension.

        Uses four signals:
        - yang_conscious: Yang's perspective
        - yin_conscious:  Yin's perspective
        - abs_diff:       |Yang - Yin| — disagreement magnitude
        - dot_prod:       Yang · Yin   — agreement direction
        """
        abs_diff = (yang_conscious - yin_conscious).abs()
        dot_prod = (yang_conscious * yin_conscious).sum(dim=-1, keepdim=True).expand_as(yang_conscious)

        features = torch.cat([
            yang_conscious,
            yin_conscious,
            abs_diff,
            dot_prod,
        ], dim=-1)

        yang_weight = self.gate(features)  # [B, D_brain]
        return yang_weight


class CassiHemisphere(nn.Module):
    """One hemisphere of a dual-Cassi system.

    Wraps a CassiBrain with hemispheric specialization:
    - Yang: fast (BrainField K=1), exploratory, detail-oriented
    - Yin:  slow (BrainField K=4), consolidative, pattern-oriented
    """

    SPECIALIZATIONS = {
        'yang': {
            'brain_field_k': 1,       # Fire — fastest updates
            'memory_readout_scale': 0.03,  # rely more on computation
            'hysteresis': 2,          # quick Qi transitions
            'description': 'fast, analytical, sequential',
        },
        'yin': {
            'brain_field_k': 4,       # Metal — slowest updates
            'memory_readout_scale': 0.08,  # rely more on memory
            'hysteresis': 5,          # slow Qi transitions
            'description': 'slow, holistic, pattern-oriented',
        },
    }

    def __init__(self, D=1040, D_stem=None, D_brain=None,
                 specialization='yang',
                 use_changepoint=True, use_soul=True, use_memory=True,
                 byte_mode=True, multi_scale_bytes=False, horizons=(1,)):
        super().__init__()
        self.specialization = specialization
        self.spec = self.SPECIALIZATIONS[specialization]
        self.horizons = horizons

        # Build the underlying brain with hemispheric parameters
        self.brain = CassiBrain(
            D=D,
            D_stem=D_stem,
            D_brain=D_brain,
            use_changepoint=use_changepoint,
            use_soul=use_soul,
            use_memory=use_memory,
            byte_mode=byte_mode,
            multi_scale_bytes=multi_scale_bytes,
            memory_readout_scale=self.spec['memory_readout_scale'],
            hysteresis=self.spec['hysteresis'],
            horizons=horizons,
        )

    def forward(self, x, return_info=False, return_workspace=False, **kwargs):
        return self.brain(x, return_info=return_info,
                         return_workspace=return_workspace, **kwargs)

    def reset_state(self, batch_size):
        self.brain.reset_state(batch_size)

    @property
    def D_brain(self):
        return self.brain.D_brain


class DualCassi(nn.Module):
    """Dual-hemisphere cognitive architecture.

    Two independent Cassi instances (Yang + Yin) communicate via
    a learned Corpus Callosum. An Arbitration mechanism integrates
    their outputs into a unified prediction.

    The "self" is not in either hemisphere — it is in the
    arbitration mechanism that integrates them.
    """

    def __init__(self, D=1040, D_stem=None, D_brain=None,
                 use_changepoint=True, use_soul=True, use_memory=True,
                 byte_mode=True, multi_scale_bytes=False,
                 corpus_bottleneck=None, use_two_fluid=False,
                 horizons=(1,)):
        super().__init__()
        self.D = D
        self._D_stem = D_stem
        self._D_brain = D_brain
        self.horizons = tuple(horizons)
        self.n_horizons = len(self.horizons)

        # Two hemispheres
        # Two hemispheres
        self.yang = CassiHemisphere(
            D=D, D_stem=D_stem, D_brain=D_brain,
            specialization='yang',
            use_changepoint=use_changepoint,
            use_soul=use_soul,
            use_memory=use_memory,
            byte_mode=byte_mode,
            multi_scale_bytes=multi_scale_bytes,
            horizons=horizons,
        )
        self.yin = CassiHemisphere(
            D=D, D_stem=D_stem, D_brain=D_brain,
            specialization='yin',
            use_changepoint=use_changepoint,
            use_soul=use_soul,
            use_memory=use_memory,
            byte_mode=byte_mode,
            multi_scale_bytes=multi_scale_bytes,
            horizons=horizons,
        )

        # Communication channel
        actual_D_brain = self.yang.D_brain
        self.corpus_callosum = CorpusCallosum(actual_D_brain, corpus_bottleneck)

        # Metacognitive arbitration
        self.arbitration = Arbitration(actual_D_brain)

        # Unified readout: per-horizon refinement of blended hemisphere predictions.
        # Each hemisphere outputs [B, n_horizons, 1024]; we apply the same
        # per-horizon MLP to refine the arbitration-blended result.
        self.unified_readout = nn.Sequential(
            nn.LayerNorm(1024),
            nn.Linear(1024, 1024),
        )

        # Disagreement tracking for metacognition
        self.register_buffer('_disagreement_ema', torch.zeros(1))
        self.register_buffer('_yang_weight_ema', torch.zeros(1))

    def forward(self, x, return_info=False, return_workspace=False,
                force_qi_state=None, force_qi_state_yang=None, force_qi_state_yin=None,
                **kwargs):
        """Dual-hemisphere forward pass.

        Args:
            x: input bytes [B, seq_len]
            force_qi_state: optionally force BOTH hemispheres' Qi state
            force_qi_state_yang: optionally force Yang Qi state only
            force_qi_state_yin:  optionally force Yin Qi state only

        Returns:
            output: unified prediction [B, 1024]
            info: dict with hemisphere states, arbitration, disagreement
        """
        B = x.shape[0]

        # Allow generic force_qi_state to apply to both hemispheres
        if force_qi_state is not None:
            if force_qi_state_yang is None:
                force_qi_state_yang = force_qi_state
            if force_qi_state_yin is None:
                force_qi_state_yin = force_qi_state

        # Parallel processing
        yang_out, yang_info = self.yang(
            x, return_info=True, return_workspace=return_workspace,
            force_qi_state=force_qi_state_yang,
            **kwargs
        )
        yin_out, yin_info = self.yin(
            x, return_info=True, return_workspace=return_workspace,
            force_qi_state=force_qi_state_yin,
            **kwargs
        )

        # Extract conscious states
        yang_conscious = yang_info.get('conscious',
            yang_info.get('brain_state', torch.zeros(B, self.yang.D_brain, device=x.device)))
        yin_conscious = yin_info.get('conscious',
            yin_info.get('brain_state', torch.zeros(B, self.yin.D_brain, device=x.device)))

        # Corpus callosum communication
        yang_input, yin_input = self.corpus_callosum(yang_conscious, yin_conscious)

        # Arbitration: how much to trust Yang vs Yin
        yang_weight = self.arbitration(yang_conscious, yin_conscious)

        # Blend outputs per-dimension
        # yang_out/yin_out are [B, n_horizons, 1024] (n_horizons=1 for single-horizon)
        # yang_weight is [B, 1024] — broadcast across horizons
        w = yang_weight.unsqueeze(1)  # [B, 1, 1024]
        blended = w * yang_out + (1.0 - w) * yin_out  # [B, n_horizons, 1024]
        output = self.unified_readout(blended)  # [B, n_horizons, 1024]

        # Unified conscious state: arbitration-weighted blend of hemispheres
        # This is what the "self" experiences — the integrated consciousness
        unified_conscious = yang_weight.mean(dim=-1, keepdim=True) * yang_conscious + \
                           (1.0 - yang_weight.mean(dim=-1, keepdim=True)) * yin_conscious

        # Metacognitive signals
        disagreement = (yang_out - yin_out).norm(dim=-1).mean()
        yang_weight_mean = yang_weight.mean()

        # Update EMAs
        with torch.no_grad():
            self._disagreement_ema = 0.95 * self._disagreement_ema + 0.05 * disagreement
            self._yang_weight_ema = 0.95 * self._yang_weight_ema + 0.05 * yang_weight_mean

        if return_info or return_workspace:
            info = {
                # Unified keys for backward compatibility with training loop
                'conscious': unified_conscious,
                'state': yang_info.get('qi_state', 'unknown'),  # primary state = Yang's
                'workspace_fwd': yang_info.get('workspace_fwd'),
                'workspace_rev': yang_info.get('workspace_rev'),
                'surprise': yang_info.get('surprise', 0.0),
                'disappointment': yang_info.get('disappointment', 0.0),
                'harmony': yang_info.get('harmony', None),
                # Observer / Dynamics (propagate from Yang hemisphere)
                'observer_embedding': yang_info.get('observer_embedding'),
                'observer_predicted_emb': yang_info.get('observer_predicted_emb'),
                'observer_importance': yang_info.get('observer_importance'),
                'observer_confidence': yang_info.get('observer_confidence'),
                'predicted_next_conscious': yang_info.get('predicted_next_conscious'),
                'prev_predicted_next_conscious': yang_info.get('prev_predicted_next_conscious'),
                'memory_attn': yang_info.get('memory_attn'),
                'weights': yang_info.get('weights'),
                'energy': yang_info.get('energy'),
                'chakra_entropy': yang_info.get('chakra_entropy'),
                'phi_balance_loss': yang_info.get('phi_balance_loss'),
                'sparsity_loss': yang_info.get('sparsity_loss'),
                'qi_energy_bonus': yang_info.get('qi_energy_bonus'),
                'trajectory_length': yang_info.get('trajectory_length', 0),
                'trajectory_surprise': yang_info.get('trajectory_surprise', 0.0),
                'trajectory_disappointment': yang_info.get('trajectory_disappointment', 0.0),
                # Dual-specific keys
                'yang': yang_info,
                'yin': yin_info,
                'yang_weight': yang_weight_mean.item(),
                'yang_weight_per_dim': yang_weight,
                'disagreement': disagreement.item(),
                'disagreement_ema': self._disagreement_ema.item(),
                'yang_weight_ema': self._yang_weight_ema.item(),
                'corpus_yang_input': yang_input.norm().item(),
                'corpus_yin_input': yin_input.norm().item(),
                'yang_qi': yang_info.get('state', 'unknown'),
                'yin_qi': yin_info.get('state', 'unknown'),
            }
            return output, info
        return output

    def reset_state(self, batch_size):
        """Reset both hemispheres for a new batch."""
        self.yang.reset_state(batch_size)
        self.yin.reset_state(batch_size)

    def reset_workspace(self, batch_size):
        """Alias for reset_state (training script compatibility)."""
        self.reset_state(batch_size)

    @property
    def trainable_params(self):
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    @property
    def spine(self):
        """Proxy to Yang's spine (primary spine for training script compatibility)."""
        return self.yang.brain.spine

    def load_spine(self, path):
        """Load spine weights into both hemispheres."""
        self.yang.brain.load_spine(path)
        self.yin.brain.load_spine(path)

    def save_spine(self, path):
        """Save spine weights (Yang's spine is representative)."""
        self.yang.brain.save_spine(path)

    def freeze_spine(self):
        """Freeze spine parameters in both hemispheres."""
        self.yang.brain.freeze_spine()
        self.yin.brain.freeze_spine()

    def unfreeze_spine(self):
        """Unfreeze spine parameters in both hemispheres."""
        self.yang.brain.unfreeze_spine()
        self.yin.brain.unfreeze_spine()

    @property
    def qi_cycle(self):
        """Proxy to Yang's qi_cycle (primary for training script)."""
        return self.yang.brain.qi_cycle

    @property
    def soul(self):
        """Proxy to Yang's soul (primary for training script)."""
        return self.yang.brain.soul

    @property
    def changepoint(self):
        """Proxy to Yang's changepoint (primary for training script)."""
        return self.yang.brain.changepoint

    @property
    def berry_memory(self):
        """Proxy to Yang's berry_memory (primary for training script)."""
        return self.yang.brain.berry_memory

    @property
    def brain_field(self):
        """Proxy to Yang's brain_field (primary for training script)."""
        return self.yang.brain.brain_field

    @property
    def D_stem(self):
        return self.yang.brain.D_stem

    @property
    def D_brain(self):
        return self.yang.brain.D_brain

    def temporal_regularization_loss(self):
        """Sum temporal regularization from both hemispheres."""
        return self.yang.brain.temporal_regularization_loss() + \
               self.yin.brain.temporal_regularization_loss()

    def summary(self):
        """Print architecture summary."""
        yang_params = sum(p.numel() for p in self.yang.parameters() if p.requires_grad)
        yin_params = sum(p.numel() for p in self.yin.parameters() if p.requires_grad)
        corpus_params = sum(p.numel() for p in self.corpus_callosum.parameters())
        arb_params = sum(p.numel() for p in self.arbitration.parameters())
        unified_params = sum(p.numel() for p in self.unified_readout.parameters())

        total = yang_params + yin_params + corpus_params + arb_params + unified_params

        return {
            'yang_params': yang_params,
            'yin_params': yin_params,
            'corpus_callosum_params': corpus_params,
            'arbitration_params': arb_params,
            'unified_readout_params': unified_params,
            'total_trainable': total,
        }
