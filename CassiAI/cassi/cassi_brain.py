"""CassiBrain — Three-tier architecture: Spine → Brainstem → BrainField.

Replaces the monolithic brain hierarchy with clean tier separation:
  1. Spine (CordPhysics): persistent resonant field
  2. Brainstem: Qi State Machine + bottleneck compression
  3. BrainField: expanded cognitive space

Cognitive modules (Changepoint, Soul, Memory) operate on brain_field_state.
"""

import math
import torch
import torch.nn as nn

from cassi.cord import CordPhysics, PHI, PHI_INV
from cassi.brainstem import Brainstem
from cassi.brain_field import BrainField
from cassi.multimodal_brain import ChangepointDetector, SoulVector
from cassi.berry_brain import BerryMemory


class CassiBrain(nn.Module):
    """Unified three-tier Cassi brain.

    Args:
        D: spine dimension (default 1040)
        D_stem: brainstem bottleneck (default D // φ)
        D_brain: brain dimension (default int(D × φ))
        use_changepoint: enable changepoint detection
        use_soul: enable soul vector
        use_memory: enable berry memory
        K: brain field update frequency (default 2)
    """

    def __init__(self, D=1040, D_stem=None, D_brain=None,
                 use_changepoint=True, use_soul=True, use_memory=True,
                 K=2, byte_mode=False):
        super().__init__()
        self.D = D
        self.D_stem = D_stem if D_stem is not None else int(D / PHI)
        self.D_brain = D_brain if D_brain is not None else int(D * PHI)
        self.use_changepoint = use_changepoint
        self.use_soul = use_soul
        self.use_memory = use_memory
        self.K = K

        # ── Tier 1: Spine ──
        self.spine = CordPhysics(D=D, byte_mode=byte_mode)

        # ── Tier 2: Brainstem ──
        self.brainstem = Brainstem(D=D, D_stem=self.D_stem)

        # ── Tier 3: Brain ──
        self.brain_field = BrainField(D_stem=self.D_stem, D_brain=self.D_brain, K=K)

        # Cognitive modules operate on brain_field_state
        if self.use_changepoint:
            self.changepoint = ChangepointDetector(
                threshold=0.5,
                window_size=5,
                dim=self.D_brain,
            )
        if self.use_soul:
            self.soul = SoulVector(dim=self.D_brain, ema_decay=0.99)
        if self.use_memory:
            # Rich memory key: energy + compressed + brain + breath
            key_dim = 13 + self.D_stem + self.D_brain + 2
            self.berry_memory = BerryMemory(
                key_dim=key_dim,
                value_dim=self.D_brain,
                n_slots=4096,
            )
            self.memory_proj = nn.Linear(self.D_brain, 1024)

        # Final prediction readout: from brain field state
        # LayerNorm normalizes brain_state before readout so small weights
        # produce small outputs regardless of brain_state scale
        self.readout = nn.Sequential(
            nn.LayerNorm(self.D_brain),
            nn.Linear(self.D_brain, 1024),
        )
        # Small init so brain residual starts near zero (spine dominates initially)
        for m in self.readout.modules():
            if isinstance(m, nn.Linear):
                nn.init.uniform_(m.weight, -0.01, 0.01)
                nn.init.zeros_(m.bias)

        # Learnable residual scale — starts at zero, grows as brain learns
        self.brain_scale = nn.Parameter(torch.zeros(1))

        # Step counter for brain field
        self._step_counter = 0

        # ── Surprise & Disappointment tracking ──
        # EMA buffers for computing prediction-error-style surprise from
        # internal dynamics (field energy, qi fluid, yang/yin balance).
        self.register_buffer('_energy_ema', torch.tensor(0.0))
        self.register_buffer('_qi_ema', torch.tensor(0.0))
        self.register_buffer('_yang_ema', torch.tensor(0.0))
        self.register_buffer('_yin_ema', torch.tensor(0.0))
        self.register_buffer('_surprise_ema', torch.tensor(0.0))
        self.register_buffer('_disappointment_ema', torch.tensor(0.0))

    def reset_state(self, batch_size):
        """Reset all persistent state across all tiers."""
        self.spine.reset_state(batch_size)
        self.brainstem.reset_state(batch_size)
        self.brain_field.reset_state(batch_size)
        self._step_counter = 0
        if self.use_changepoint:
            if hasattr(self.changepoint, 'reset'):
                self.changepoint.reset()

    # Alias for training loop compatibility
    reset_workspace = reset_state

    def forward(self, x, byte_mode=None, return_info=False, return_workspace=False, **kwargs):
        """Process one batch of input through the three-tier architecture.

        For training compatibility, this processes 4-frame input like the
        original CordPhysics.forward(). It calls spine.forward() internally
        and then runs the brainstem + brain on the resulting field state.

        Args:
            x: [B, 4, 1024] (or [B, 1024] in byte_mode)
            byte_mode: override spine byte_mode
            return_info: return dict of metrics
            return_workspace: alias for return_info (training loop compat)

        Returns:
            pred: [B, 1024]
            info: dict (if return_info=True or return_workspace=True)
        """
        return_info = return_info or return_workspace
        B = x.shape[0]
        device = x.device

        # Reset state for new batch
        self.reset_state(B)

        # ── Spine: process 4-frame input ──
        if byte_mode is None:
            byte_mode = self.spine.byte_mode

        if byte_mode:
            field = self.spine.byte_encoder.encode_sequence(x, T=4)
        else:
            field = x

        # Use spine's original forward for prediction (high-quality, fwd+rev IIR)
        pred_spine = self.spine.forward(field, byte_mode=False)

        # Process step-by-step with brainstem feedback loop
        psi = self.spine.in_proj(field)  # [B, 4, D]
        modulation = {}
        stem_info = None
        for t in range(4):
            # Enable fast weight update on last step (when we have stable state)
            gate = (t == 3)
            # step() updates persistent IIR state; we don't need gradients through
            # state transitions — the spine params already get gradients from forward()
            with torch.no_grad():
                field_state = self.spine.step(psi[:, t, :], brainstem_gate=gate, **modulation)
            # Brainstem reads and modulates for next step
            stem_info = self.brainstem.step(self.spine)
            modulation = {
                'theta_shift': stem_info['theta_shift'],
                'damp_scale': stem_info['damp_scale'],
                'yang_gain': stem_info['yang_gain'],
                'yin_gain': stem_info['yin_gain'],
            }

        compressed = stem_info['compressed']

        # ── Surprise & Disappointment computation ──
        # These are computed from internal dynamics since we don't have
        # ground-truth targets inside forward(). They serve as differentiable
        # signals for the Qi state machine and memory gating.
        with torch.no_grad():
            energy_mean = self.spine.field_energy.mean()
            qi_mean = self.spine.qi_fluid.mean()
            yang_mean = self.spine.yang.norm(dim=-1).mean()
            yin_mean = self.spine.yin.norm(dim=-1).mean()

        # Surprise = total deviation from expectation (magnitude)
        # Use OLD EMA values (expectation from before this sample)
        energy_surprise = (energy_mean - self._energy_ema).abs()
        qi_surprise = (qi_mean - self._qi_ema).abs()
        yang_surprise = (yang_mean - self._yang_ema).abs()
        yin_surprise = (yin_mean - self._yin_ema).abs()

        # Raw surprise before brain_state contribution
        raw_surprise = energy_surprise + qi_surprise * 0.5 + yang_surprise * 0.3 + yin_surprise * 0.3

        # ── BrainField: slower cognitive processing ──
        brain_state = self.brain_field.maybe_step(compressed)

        # Brain activity contribution to surprise (cognitive effort = unexpected input)
        brain_activity = brain_state.norm(dim=-1).mean() / math.sqrt(self.D_brain)
        surprise = raw_surprise + brain_activity * 0.5

        # Disappointment = specifically negative deviations (outcome worse than expected)
        # Based on neuroscience: dopaminergic neurons encode negative RPE.
        # In our dynamics: dropping energy, dropping qi, dropping yang = disappointment.
        energy_disappointment = torch.relu(self._energy_ema - energy_mean)  # energy dropped
        qi_disappointment = torch.relu(self._qi_ema - qi_mean)              # qi dropped
        yang_disappointment = torch.relu(self._yang_ema - yang_mean)        # yang dropped

        disappointment = energy_disappointment + qi_disappointment * 0.5 + yang_disappointment * 0.3

        # Update EMAs AFTER computing surprise/disappointment so they represent
        # the expectation for the NEXT sample
        with torch.no_grad():
            self._energy_ema = 0.95 * self._energy_ema + 0.05 * energy_mean
            self._qi_ema = 0.95 * self._qi_ema + 0.05 * qi_mean
            self._yang_ema = 0.95 * self._yang_ema + 0.05 * yang_mean
            self._yin_ema = 0.95 * self._yin_ema + 0.05 * yin_mean
            self._surprise_ema = 0.95 * self._surprise_ema + 0.05 * surprise
            self._disappointment_ema = 0.95 * self._disappointment_ema + 0.05 * disappointment

        # ── Disappointment → Qi state override ──
        # High disappointment forces Water state (restoration/consolidation)
        # reflecting the neuroscientific finding that disappointment triggers
        # withdrawal and energy conservation circuits.
        disappointment_threshold = self._disappointment_ema * 1.5 + 0.1
        if disappointment.item() > disappointment_threshold:
            stem_info['state'] = 'water'
            stem_info['profile'] = self.brainstem.qi.get_profile('water')
            # Reduce arousal to promote restoration
            stem_info['arousal'] = stem_info['arousal'] * 0.5

        # ── Cognitive modules ──
        info = {
            'qi_state': stem_info['state'],
            'arousal': stem_info['arousal'],
            'theta_shift': stem_info['theta_shift'],
            'chakra_attention': stem_info['chakra_attention'],
        }

        if self.use_changepoint:
            cp_input = brain_state.mean(dim=0, keepdim=True)
            if self.changepoint.update(cp_input):
                info['changepoint'] = True
                # Force Metal state for consolidation after changepoint
                stem_info['state'] = 'metal'

        # Ensure info reflects the final state after all overrides
        info['qi_state'] = stem_info['state']
        info['arousal'] = stem_info['arousal']

        if self.use_soul:
            self.soul.update(brain_state.mean(dim=0))
            brain_state = self.soul.inject(brain_state)
            info['soul_vector'] = self.soul.vector.detach().clone()

        # ── Brain readout (always active, ensures gradients flow) ──
        pred_brain = self.readout(brain_state)
        # brain_scale starts at 0, grows via softplus → smooth gating
        scale = torch.nn.functional.softplus(self.brain_scale) * 0.1
        pred = pred_spine + scale * pred_brain

        # ── Memory read ──
        if self.use_memory:
            # Build rich key
            breath = stem_info['breath']
            breath_vec = torch.tensor([
                breath['yang'].item(), breath['yin'].item()
            ], device=device).unsqueeze(0).expand(B, -1)

            key = torch.cat([
                self.spine.field_energy,      # [B, 13]
                compressed,                    # [B, D_stem]
                brain_state,                   # [B, D_brain]
                breath_vec,                    # [B, 2]
            ], dim=-1)

            if self.berry_memory.n_filled.item() > 0:
                retrieved, attn = self.berry_memory.query(key, temperature=0.1)
                pred_memory = self.memory_proj(retrieved)
                pred = pred + 0.05 * pred_memory
                info['memory_attn'] = attn.mean().item()

            # Memory write: gate by surprise (high surprise = uncertain state, don't encode)
            # Also gate by disappointment (very disappointed = something wrong, don't encode)
            surprise_threshold = self._surprise_ema * 1.3 + 0.1
            disappointment_threshold = self._disappointment_ema * 1.5 + 0.05
            should_encode = (
                surprise.item() < surprise_threshold and
                disappointment.item() < disappointment_threshold and
                self.training
            )
            if should_encode:
                with torch.no_grad():
                    value = brain_state.mean(dim=0, keepdim=True)
                    self.berry_memory.write(key[0:1], value, mode='ema')

        # Neuroplasticizer modulation for optimizer
        # Pass surprise/disappointment so brainstem can modulate LR
        stem_info['surprise'] = surprise.item() if isinstance(surprise, torch.Tensor) else float(surprise)
        stem_info['disappointment'] = disappointment.item() if isinstance(disappointment, torch.Tensor) else float(disappointment)
        info['neuro_modulation'] = self.brainstem.get_neuro_modulation(stem_info)

        # Training loop compatibility keys
        # Return LayerNorm-normalized brain_state for coherence loss
        # (raw brain_state has norm ~40 which creates huge coherence loss)
        info['conscious'] = self.readout[0](brain_state) if isinstance(self.readout, nn.Sequential) else brain_state
        info['surprise'] = surprise
        info['disappointment'] = disappointment
        info['mean_harmony'] = torch.tensor(stem_info['arousal'], device=device)
        info['qi_arousal'] = stem_info['arousal']
        info['phi_balance_loss'] = torch.tensor(0.0, device=device)
        info['qi_energy_bonus'] = torch.tensor(0.0, device=device)
        info['weights'] = stem_info['chakra_attention']  # per-chakra salience = specialist weights

        # Observability keys for CassiMetrics (map new architecture → old metric names)
        info['workspace_fwd'] = self.spine.yang
        info['workspace_rev'] = self.spine.yin
        info['qi_fluid'] = self.spine.qi_fluid
        info['energy'] = self.spine.field_energy
        yang_norm = self.spine.yang.norm(dim=-1).mean()
        yin_norm = self.spine.yin.norm(dim=-1).mean()
        info['qi_ratio'] = (yang_norm / (yin_norm + 1e-8)).item()
        info['harmony'] = torch.tensor(stem_info['arousal'], device=device)

        # Breath metrics
        breath = stem_info.get('breath', {})
        for k in ['breath_yang', 'breath_yin', 'beat', 'flow', 'phase_diff', 'freq_ratio', 'pulse_active']:
            info[k] = breath.get(k, 0.0)

        if return_info:
            return pred, info
        return pred

    def load_spine(self, path):
        """Load spine weights from checkpoint (training loop compatibility)."""
        ck = torch.load(path, map_location=self.spine.h1.device, weights_only=False)
        if isinstance(ck, dict) and 'model' in ck:
            ck = ck['model']
        # Strip _orig_mod. prefix from torch.compile wrapped models
        if any(k.startswith('_orig_mod.') for k in ck.keys()):
            ck = {k.replace('_orig_mod.', ''): v for k, v in ck.items()}
        # If checkpoint is a full model (keys prefixed with 'spine.'), extract spine weights
        spine_keys = [k for k in ck.keys() if k.startswith('spine.')]
        if spine_keys:
            ck = {k.replace('spine.', ''): v for k, v in ck.items() if k.startswith('spine.')}
        missing, unexpected = self.spine.load_state_dict(ck, strict=False)
        if missing and not all(k.startswith('byte_encoder') for k in missing):
            print(f"[CassiBrain.load_spine] Warning: missing keys: {missing}")
        if unexpected:
            print(f"[CassiBrain.load_spine] Warning: unexpected keys: {unexpected}")

    def freeze_spine(self):
        """Freeze spine parameters."""
        for p in self.spine.parameters():
            p.requires_grad = False

    def unfreeze_spine(self):
        """Unfreeze spine parameters."""
        for p in self.spine.parameters():
            p.requires_grad = True

    def state_dict(self, *args, **kwargs):
        """Include all persistent buffers in checkpoint."""
        return super().state_dict(*args, **kwargs)

    def load_state_dict(self, state_dict, strict=True):
        """Load state dict with shape filtering for compatibility."""
        model_state = self.state_dict()
        filtered = {}
        for k, v in state_dict.items():
            if k in model_state:
                if v.shape == model_state[k].shape:
                    filtered[k] = v
                else:
                    print(f"[CassiBrain] Skipping {k}: checkpoint {v.shape} vs model {model_state[k].shape}")
            else:
                if strict:
                    print(f"[CassiBrain] Missing key: {k}")
        return super().load_state_dict(filtered, strict=False)
