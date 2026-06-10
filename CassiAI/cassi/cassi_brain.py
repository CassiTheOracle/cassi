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
import torch.nn.functional as F

from cassi.cord import CordPhysics, PHI, PHI_INV
from cassi.brainstem import Brainstem
from cassi.brain_field import BrainField
from cassi.multimodal_brain import ChangepointDetector, SoulVector
from cassi.berry_brain import BerryMemory
from cassi.qi_cycle import QiCycle
from cassi.temporal_readout import TemporalResonanceReadout


class InternalObserver(nn.Module):
    """Metacognitive self-model: learns what every internal variable means.

    Builds a compressed snapshot of full system state, encodes to an embedding,
    and predicts the next snapshot.  Outputs variable-importance weights and
    confidence.  Operates like a slow (Yin) observer that watches the fast
    (Yang) subsystems.
    """

    def __init__(self, D_brain, D_stem, n_chakras=13):
        super().__init__()
        self.D_brain = D_brain
        self.D_stem = D_stem

        # Project each component to a manageable dimension before concat
        self.proj = nn.ModuleDict({
            'brain_state':  nn.Linear(D_brain, 64),
            'workspace_fwd': nn.Linear(D_brain, 64),
            'workspace_rev': nn.Linear(D_brain, 64),
            'conscious':    nn.Linear(D_brain, 64),
            'compressed':   nn.Linear(D_stem, 32),
            'meta_repr':    nn.Linear(D_brain, 32),
            'field_energy': nn.Linear(n_chakras, n_chakras),
        })
        n_scalars = 13
        self.scalar_proj = nn.Linear(n_scalars, n_scalars)

        snap_dim = 64 * 4 + 32 * 2 + n_chakras + n_scalars  # = 346
        emb_dim = 128

        # Encoder: snapshot -> embedding
        self.encoder = nn.Sequential(
            nn.Linear(snap_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Linear(256, emb_dim),
            nn.LayerNorm(emb_dim),
        )

        # Predictor: embedding -> predicted next embedding (autoencoder for now)
        self.predictor = nn.Sequential(
            nn.Linear(emb_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Linear(256, emb_dim),
        )

        # Heads
        self.importance_head = nn.Linear(emb_dim, 8)
        self.confidence_head = nn.Linear(emb_dim, 1)

        # Projection to inject observer embedding into conscious state
        self.injection_proj = nn.Linear(emb_dim, D_brain)

        # Slow EMA of observer state (Yin observer)
        self.register_buffer('observer_ema', torch.zeros(emb_dim))
        self.ema_decay = 0.99

    def build_snapshot(self, brain_state, workspace_fwd, workspace_rev, conscious,
                       compressed, meta_repr, field_energy, scalars):
        """Flatten internal state into a fixed-size snapshot vector."""
        parts = [
            self.proj['brain_state'](brain_state),      # [B, 64]
            self.proj['workspace_fwd'](workspace_fwd),    # [B, 64]
            self.proj['workspace_rev'](workspace_rev),    # [B, 64]
            self.proj['conscious'](conscious),            # [B, 64]
            self.proj['compressed'](compressed),          # [B, 32]
            self.proj['meta_repr'](meta_repr),            # [B, 32]
            self.proj['field_energy'](field_energy),      # [B, 13]
            self.scalar_proj(scalars),                    # [B, 13]
        ]
        return torch.cat(parts, dim=-1)  # [B, 346]

    def forward(self, snapshot):
        emb = self.encoder(snapshot)  # [B, 128]

        # Slow EMA update
        with torch.no_grad():
            self.observer_ema.copy_(
                self.ema_decay * self.observer_ema +
                (1 - self.ema_decay) * emb.mean(dim=0)
            )

        pred_emb = self.predictor(emb)  # [B, 128]
        importance = torch.sigmoid(self.importance_head(emb))  # [B, 8]
        confidence = torch.sigmoid(self.confidence_head(emb))  # [B, 1]

        return {
            'embedding': emb,
            'predicted_embedding': pred_emb,
            'importance': importance,
            'confidence': confidence,
            'observer_ema': self.observer_ema.clone(),
        }


class ConsciousDynamics(nn.Module):
    """Imagination engine: predicts next conscious state without full forward pass.

    Small network that learns the dynamics of consciousness:
        conscious_{t+1} = f(conscious_t, breath, qi_energy, observer_emb)

    This enables planning, daydreaming, and rapid simulation.
    """

    def __init__(self, D_brain, observer_emb=128):
        super().__init__()
        self.D_brain = D_brain
        hidden = max(256, D_brain // 16)
        input_dim = D_brain + 3 + 1 + observer_emb  # conscious + breath + qi + observer

        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Linear(hidden, hidden),
            nn.LayerNorm(hidden),
            nn.GELU(),
            nn.Linear(hidden, D_brain),
            nn.LayerNorm(D_brain),
        )

    def forward(self, conscious, breath_yang, breath_yin, breath_beat,
                qi_energy, observer_emb):
        """Predict next conscious state.

        Args:
            conscious:     [B, D_brain]
            breath_yang:   [B] or scalar
            breath_yin:    [B] or scalar
            breath_beat:   [B] or scalar
            qi_energy:     [B] or scalar
            observer_emb:  [B, observer_emb]
        Returns:
            conscious_next: [B, D_brain]
        """
        B = conscious.shape[0]
        device = conscious.device

        def _ensure_tensor(x):
            if not isinstance(x, torch.Tensor):
                x = torch.tensor(x, device=device, dtype=conscious.dtype)
            # Flatten to 1D and ensure length B
            x = x.reshape(-1)
            if x.shape[0] == 1:
                x = x.expand(B)
            elif x.shape[0] != B:
                # If it's some other size, just take mean and broadcast
                x = x.mean().unsqueeze(0).expand(B)
            return x.unsqueeze(-1)  # [B, 1]

        breath_yang = _ensure_tensor(breath_yang)
        breath_yin  = _ensure_tensor(breath_yin)
        breath_beat = _ensure_tensor(breath_beat)
        qi_energy   = _ensure_tensor(qi_energy)

        x = torch.cat([conscious, breath_yang, breath_yin, breath_beat,
                       qi_energy, observer_emb], dim=-1)
        return self.net(x)


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

    # Tunable constants extracted from magic numbers
    DEFAULT_CLAMP_THRESHOLD = 10.0
    DEFAULT_MEMORY_READOUT_SCALE = 0.05
    DEFAULT_PURIFICATION_CONFIDENCE = 0.5
    DEFAULT_HYSTERESIS = 3

    def __init__(self, D=1040, D_stem=None, D_brain=None,
                 use_changepoint=True, use_soul=True, use_memory=True,
                 K=2, byte_mode=False,
                 clamp_threshold=DEFAULT_CLAMP_THRESHOLD,
                 memory_readout_scale=DEFAULT_MEMORY_READOUT_SCALE,
                 purification_confidence=DEFAULT_PURIFICATION_CONFIDENCE,
                 hysteresis=DEFAULT_HYSTERESIS,
                 horizons=(1,)):
        super().__init__()
        self.D = D
        # Scaled-up architecture: D_stem preserves spine dimensionality (2:1 compression
        # of concatenated field_state+qi_fluid), D_brain is doubled for more capacity.
        self.D_stem = D_stem if D_stem is not None else D
        self.D_brain = D_brain if D_brain is not None else int(D * PHI * 2)
        self.use_changepoint = use_changepoint
        self.use_soul = use_soul
        self.use_memory = use_memory
        self.K = K
        self.horizons = tuple(horizons)
        self.n_horizons = len(self.horizons)
        self.clamp_threshold = clamp_threshold
        self.memory_readout_scale = memory_readout_scale
        self.purification_confidence = purification_confidence

        # ── Tier 1: Spine ──
        self.spine = CordPhysics(D=D, byte_mode=byte_mode)

        # ── Tier 2: Brainstem ──
        self.brainstem = Brainstem(D=D, D_stem=self.D_stem)

        # ── Qi Cycle Conductor ──
        self.qi_cycle = QiCycle(brainstem_qi=self.brainstem.qi, hysteresis=hysteresis)

        # ── Tier 3: Brain ──
        self.brain_field = BrainField(D_stem=self.D_stem, D_brain=self.D_brain, K=K)
        # Note: we do NOT subscribe brain_field/soul to qi_cycle here.
        # Forward() explicitly calls set_qi_profile() to avoid double propagation.
        # DreamBank (if used) is subscribed externally in train_multimodal.py.

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
            # Qi embedding for memory keying
            self.qi_embed = nn.Embedding(5, 4)
            nn.init.xavier_uniform_(self.qi_embed.weight)
            self.qi_index = {'water': 0, 'wood': 1, 'fire': 2, 'earth': 3, 'metal': 4}

            # ── P1.3: Berry memory projections (compress to 52-dim key / 39-dim value) ──
            self.berry_key_field_proj = nn.Linear(13, 13)
            self.berry_key_compressed_proj = nn.Linear(self.D_stem, 16)
            self.berry_key_conscious_proj = nn.Linear(self.D_brain, 15)
            self.berry_key_context_proj = nn.Linear(6, 4)
            self.berry_key_residual = nn.Linear(self.D_brain, 4)
            self.berry_value_proj = nn.Linear(self.D_brain, 39)
            self.berry_memory = BerryMemory(
                key_dim=52,
                value_dim=39,
                n_slots=4096,
            )
            self.memory_proj = nn.Linear(39, 1024)

        # Final prediction readout: temporal resonance bands
        # Brain state is decomposed into φ-scaled temporal bands.
        # Each band decodes a prediction at its natural timescale;
        # soft period matching maps bands to target horizons.
        self.readout = TemporalResonanceReadout(
            D_brain=self.D_brain,
            n_scales=6,
            output_dim=1024,
            horizons=self.horizons,
        )

        # Learnable residual scale — sigmoid-bounded [0,1] for stability
        self.readout_scale = nn.Parameter(torch.zeros(1))

        # Step counter for brain field
        self._step_counter = 0

        # ── P0.1: Dual workspace buffers (Yang-dominant prospective / Yin retrospective) ──
        # Plain attributes (not buffers) so they persist across batches and are
        # not clobbered by state_dict().  Lazily resized via _ensure_workspace().
        self._workspace_fwd = None
        self._workspace_rev = None

        # ── P1.1: Meta-cord self-referential loop ──
        # Meta-cord observes workspace history + its own previous outputs.
        self._meta_history = None
        # Small meta-cord with bottleneck: compress 8 timesteps through narrow hidden layer
        meta_hidden = max(128, self.D_brain // 32)
        self.meta_cord = nn.Sequential(
            nn.Linear(self.D_brain * 8, meta_hidden),
            nn.LayerNorm(meta_hidden),
            nn.GELU(),
            nn.Linear(meta_hidden, self.D_brain),
            nn.LayerNorm(self.D_brain),
        )

        # ── Internal Observer: learns what every variable means ──
        self.observer = InternalObserver(D_brain=self.D_brain, D_stem=self.D_stem)
        self.dynamics = ConsciousDynamics(D_brain=self.D_brain, observer_emb=128)

        # Previous-batch dynamics output for true temporal prediction loss
        self._prev_predicted_next_conscious = None

        # ── Process trajectory buffer (rolling) ──
        # Stores the last N internal states for dynamical-context memory.
        # Not a register_buffer so it persists across batches but is not
        # part of the checkpoint (reconstructed from continued operation).
        self._trajectory_capacity = 16
        self._process_trajectory = []  # list of dicts

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
        """Reset all persistent state across all tiers.

        P0.3: Qi-fluid persists across observations (awareness accumulates).
        Workspace buffers are zeroed (per-sample processing state).
        """
        # ── P0.3: Preserve qi_fluid before spine resets it ──
        old_qi = None
        if hasattr(self.spine, 'qi_fluid'):
            old_qi = self.spine.qi_fluid.detach().clone()

        self.spine.reset_state(batch_size)
        self.brainstem.reset_state(batch_size)
        self.brain_field.reset_state(batch_size)
        self._step_counter = 0

        # Restore qi_fluid with resize (zero-pad new slots, truncate if smaller)
        if old_qi is not None and hasattr(self.spine, 'qi_fluid'):
            old_b = old_qi.shape[0]
            new = torch.zeros(batch_size, self.spine.qi_fluid.shape[1],
                              device=old_qi.device, dtype=old_qi.dtype)
            copy_b = min(old_b, batch_size)
            new[:copy_b] = old_qi[:copy_b]
            self.spine.qi_fluid = new

        if self.use_changepoint:
            if hasattr(self.changepoint, 'reset'):
                self.changepoint.reset()

        # NOTE: workspace buffers are NO LONGER zeroed here.
        # They persist across batches so the model can learn temporal coherence.
        # The training loop still calls reset_state() per batch to reset
        # spine/brainstem/brain_field, but workspace/meta-history carry forward.

    # Alias for training loop compatibility
    reset_workspace = reset_state

    def _ensure_workspace(self, B, device):
        """Lazy allocation of workspace buffers that persist across batches."""
        if self._workspace_fwd is None or self._workspace_fwd.shape[0] < B:
            self._workspace_fwd = torch.zeros(B, self.D_brain, device=device)
            self._workspace_rev = torch.zeros(B, self.D_brain, device=device)
            self._meta_history = torch.zeros(B, 4, self.D_brain, device=device)
        elif self._workspace_fwd.device != device:
            self._workspace_fwd = self._workspace_fwd.to(device)
            self._workspace_rev = self._workspace_rev.to(device)
            self._meta_history = self._meta_history.to(device)

    def forward(self, x, byte_mode=None, return_info=False, return_workspace=False,
                force_qi_state=None, **kwargs):
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

        # Ensure workspace buffers exist and are on the right device
        self._ensure_workspace(B, device)

        # ── Spine: process 4-frame input ──
        if byte_mode is None:
            byte_mode = self.spine.byte_mode

        if byte_mode:
            if hasattr(self.spine, 'byte_encoder'):
                field = self.spine.byte_encoder.encode_sequence(x, T=4)
            else:
                field = x  # fall back if no byte encoder available
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
            # Only update Qi history on the last frame — avoids polluting the
            # energy history with per-frame transients (energy grows across frames)
            update_qi_hist = (t == 3)
            # step() updates persistent IIR state; we don't need gradients through
            # state transitions — the spine params already get gradients from forward()
            with torch.no_grad():
                field_state = self.spine.step(psi[:, t, :], brainstem_gate=gate, **modulation)
            # Brainstem reads and modulates for next step
            stem_info = self.brainstem.step(self.spine, update_qi_history=update_qi_hist)
            modulation = {
                'theta_shift': stem_info['theta_shift'],
                'damp_scale': stem_info['damp_scale'],
                'yang_gain': stem_info['yang_gain'],
                'yin_gain': stem_info['yin_gain'],
                'phi_fast_scale': stem_info.get('phi_fast_scale', 1.0),
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

        # ── P0.1: Dual workspace update ──
        # Yang leads by φ in the prospective workspace (weights new information higher)
        # Yin provides tension in the retrospective workspace (preserves memory)
        # Workspace persists across batches; we update via in-place copy.
        # Wrap in no_grad so the persistent state never accumulates a computation graph.
        w_fwd = self._workspace_fwd[:B]  # view into persistent buffer
        w_rev = self._workspace_rev[:B]
        new_fwd = (PHI_INV ** 2 * w_fwd + PHI_INV * brain_state)
        new_rev = (PHI_INV * w_rev + PHI_INV ** 2 * new_fwd)
        with torch.no_grad():
            w_fwd.copy_(new_fwd)
            w_rev.copy_(new_rev)

        # ── P0.2: Consciousness as cooperation, not conflict ──
        # Yang leads, Yin provides form.  Subtraction (fwd - rev) makes them enemies.
        conscious = PHI_INV * w_fwd + PHI_INV ** 2 * w_rev

        # Brain activity contribution to surprise (cognitive effort = unexpected input)
        brain_activity = brain_state.norm(dim=-1).mean() / math.sqrt(self.D_brain)
        surprise = raw_surprise + brain_activity * 0.5

        # Disappointment = specifically negative deviations (outcome worse than expected)
        energy_disappointment = torch.relu(self._energy_ema - energy_mean)
        qi_disappointment = torch.relu(self._qi_ema - qi_mean)
        yang_disappointment = torch.relu(self._yang_ema - yang_mean)

        disappointment = energy_disappointment + qi_disappointment * 0.5 + yang_disappointment * 0.3

        # Update EMAs AFTER computing surprise/disappointment so they represent
        # the expectation for the NEXT sample
        with torch.no_grad():
            self._energy_ema.copy_(0.95 * self._energy_ema + 0.05 * energy_mean)
            self._qi_ema.copy_(0.95 * self._qi_ema + 0.05 * qi_mean)
            self._yang_ema.copy_(0.95 * self._yang_ema + 0.05 * yang_mean)
            self._yin_ema.copy_(0.95 * self._yin_ema + 0.05 * yin_mean)
            self._surprise_ema.copy_(0.95 * self._surprise_ema + 0.05 * surprise)
            self._disappointment_ema.copy_(0.95 * self._disappointment_ema + 0.05 * disappointment)

        # ── P1.1: Meta-cord self-referential loop ──
        # Meta-cord observes workspace + its own previous output
        workspace_history = torch.stack([
            w_fwd, w_rev, conscious, brain_state,
        ], dim=1)  # [B, 4, D_brain]
        m_hist = self._meta_history[:B]  # view into persistent buffer
        self_referential_input = torch.cat([
            workspace_history,
            m_hist,  # [B, 4, D_brain]
        ], dim=1)  # [B, 8, D_brain]
        # Flatten for MLP: [B, 8 * D_brain]
        meta_input = self_referential_input.view(B, -1)
        meta_repr = self.meta_cord(meta_input)  # [B, D_brain]
        # Update meta-cord history (rolling buffer) in-place
        with torch.no_grad():
            m_hist[:, :-1, :].copy_(m_hist[:, 1:, :])
            m_hist[:, -1, :].copy_(F.normalize(meta_repr, dim=-1))
        # Meta-cord contributes to conscious state (subtle self-referential boost)
        conscious = conscious + PHI_INV ** 3 * meta_repr

        # ── Qi Cycle: determine authoritative Qi state ──
        # QiCycle considers spine state, disappointment, changepoint, and bank pressure
        cp_triggered = False
        changepoint_confidence = 0.0
        if force_qi_state is not None:
            # Replay override: use forced state without broadcasting transition
            valid_states = {'water', 'wood', 'fire', 'earth', 'metal'}
            if force_qi_state not in valid_states:
                raise ValueError(f"Invalid force_qi_state: {force_qi_state!r}. Must be one of {valid_states}")
            qi_state = force_qi_state
            stem_info['state'] = qi_state
            stem_info['profile'] = self.brainstem.qi.get_profile(qi_state)
        else:
            if self.use_changepoint:
                cp_input = brain_state.mean(dim=0, keepdim=True)
                cp_triggered, changepoint_confidence = self.changepoint.update(
                    cp_input, qi_state=stem_info['state']
                )

            qi_state = self.qi_cycle.step(
                yang_norm=self.spine.yang.norm(dim=-1).mean(),
                yin_norm=self.spine.yin.norm(dim=-1).mean(),
                qi_energy=self.spine.qi_fluid.sum(dim=-1).mean(),
                breath=stem_info['breath'],
                changepoint_confidence=changepoint_confidence,
            )

            # Override brainstem state with conductor's decision
            stem_info['state'] = qi_state
            stem_info['profile'] = self.brainstem.qi.get_profile(qi_state)

        # Recompute phi_fast_scale from authoritative QiCycle profile
        # (the brainstem's original diagnosis may differ from QiCycle's decision)
        profile = stem_info['profile']
        baseline_phi = self.brainstem.qi.PROFILES['earth']['phi_fast']
        phi_fast = profile.get('phi_fast', baseline_phi)
        phi_fast_scale = phi_fast / baseline_phi
        phi_fast_scale = max(0.5, min(2.0, phi_fast_scale))
        stem_info['phi_fast_scale'] = phi_fast_scale

        # Propagate Qi profile to all Qi-aware subsystems
        # (necessary for force_qi_state replay where QiCycle doesn't broadcast)
        if self.use_soul:
            self.soul.set_qi_profile(profile)
        if hasattr(self.brain_field, 'set_qi_profile'):
            self.brain_field.set_qi_profile(profile)

        # ── Cognitive modules ──
        info = {
            'qi_state': stem_info['state'],
            'arousal': stem_info['arousal'],
            'theta_shift': stem_info['theta_shift'],
            'chakra_attention': stem_info['chakra_attention'],
            'phi_fast_scale': stem_info.get('phi_fast_scale', 1.0),
            'qi_transition_count': getattr(self.qi_cycle, '_transition_count', 0),
        }
        if cp_triggered:
            info['changepoint'] = True
            info['changepoint_confidence'] = changepoint_confidence

        # ── Changepoint-Metal Purification Circuit ──
        # High-confidence changepoint triggers Metal state which purifies context:
        # 1. Clears Soul EMA (prevents outdated beliefs from corrupting new context)
        # 2. Resets BrainField convergence (allows fresh adaptation)
        if cp_triggered and changepoint_confidence > self.purification_confidence:
            if self.use_soul:
                self.soul.vector.zero_()
                self.soul.count.zero_()
            if hasattr(self.brain_field, 'reset_state'):
                self.brain_field.reset_state(B)
            info['purified'] = True
        else:
            info['purified'] = False

        if self.use_soul:
            self.soul.update(conscious.mean(dim=0))
            conscious = self.soul.inject(conscious)
            info['soul_vector'] = self.soul.vector.detach().clone()

        # ── Conscious norm clamp (stability guard) ──
        conscious_norm = conscious.norm(dim=-1, keepdim=True)
        info['conscious_norm_raw'] = conscious_norm.mean().item()
        if conscious_norm.max() > self.clamp_threshold:
            scale_clamp = self.clamp_threshold / conscious_norm.clamp(min=self.clamp_threshold)
            conscious = conscious * scale_clamp
            info['conscious_clamped'] = True
        else:
            info['conscious_clamped'] = False

        # ── Internal Observer: learns what every variable means ──
        # Build snapshot from all internal state variables
        observer_scalars = torch.stack([
            surprise.expand(B) if isinstance(surprise, torch.Tensor) else torch.full((B,), float(surprise), device=device),
            disappointment.expand(B) if isinstance(disappointment, torch.Tensor) else torch.full((B,), float(disappointment), device=device),
            torch.zeros(B, device=device),  # qi_ratio placeholder (computed later)
            torch.zeros(B, device=device),  # memory_attn placeholder
            torch.full((B,), float(info.get('phi_fast_scale', 1.0)), device=device),
            torch.full((B,), float(changepoint_confidence), device=device),
            w_fwd.norm(dim=-1),
            w_rev.norm(dim=-1),
            brain_state.norm(dim=-1),
            compressed.norm(dim=-1),
            self._meta_history[:B].norm(dim=-1).mean(dim=-1),
            torch.zeros(B, device=device),  # yang_weight placeholder
            torch.zeros(B, device=device),  # disagreement placeholder
        ], dim=-1)  # [B, 13]

        snapshot = self.observer.build_snapshot(
            brain_state=brain_state,
            workspace_fwd=w_fwd,
            workspace_rev=w_rev,
            conscious=conscious,
            compressed=compressed,
            meta_repr=meta_repr,
            field_energy=self.spine.field_energy,
            scalars=observer_scalars,
        )
        observation = self.observer(snapshot)

        # Inject observer embedding into conscious state
        # The model now "knows that it knows"
        observer_injection = self.observer.injection_proj(observation['embedding'])
        conscious = conscious + 0.05 * observer_injection

        # ── Conscious Dynamics: predict next conscious state ──
        predicted_next_conscious = self.dynamics(
            conscious=conscious,
            breath_yang=stem_info['breath']['yang'],
            breath_yin=stem_info['breath']['yin'],
            breath_beat=stem_info['breath'].get('beat', 0.0),
            qi_energy=self.spine.qi_fluid.sum(dim=-1).mean(),
            observer_emb=observation['embedding'],
        )

        # Store for self-predictive loss in training loop
        info['observer_embedding'] = observation['embedding']
        info['observer_predicted_emb'] = observation['predicted_embedding']
        info['observer_importance'] = observation['importance']
        info['observer_confidence'] = observation['confidence']
        info['predicted_next_conscious'] = predicted_next_conscious
        info['prev_predicted_next_conscious'] = (
            self._prev_predicted_next_conscious[:B]
            if self._prev_predicted_next_conscious is not None
            else None
        )

        # ── Brain readout (always active, ensures gradients flow) ──
        # Readout operates on the φ-weighted conscious state, not raw brain_state
        pred_brain, readout_info = self.readout(conscious)
        # sigmoid-bounded scale [0, 1] — naturally prevents runaway contribution
        scale = torch.sigmoid(self.readout_scale)
        pred = scale * pred_brain

        # Spine contributes fully to horizon 1 (the immediate next frame).
        pred[:, 0] = pred[:, 0] + pred_spine

        # ── Process trajectory recording ──
        # Capture this step's internal state for dynamical-context memory.
        with torch.no_grad():
            traj_step = {
                'conscious': conscious.detach().clone(),
                'workspace_fwd': w_fwd.detach().clone(),
                'workspace_rev': w_rev.detach().clone(),
                'qi_fluid': self.spine.qi_fluid.detach().clone(),
                'field_energy': self.spine.field_energy.detach().clone(),
                'surprise': surprise.item() if isinstance(surprise, torch.Tensor) else float(surprise),
                'disappointment': disappointment.item() if isinstance(disappointment, torch.Tensor) else float(disappointment),
            }
            self._process_trajectory.append(traj_step)
            if len(self._process_trajectory) > self._trajectory_capacity:
                self._process_trajectory.pop(0)

        # ── Memory read ──
        if self.use_memory:
            breath = stem_info['breath']
            breath_vec = torch.tensor([
                breath['yang'].item(), breath['yin'].item()
            ], device=device).unsqueeze(0).expand(B, -1)

            qi_idx = torch.tensor(
                [self.qi_index.get(stem_info['state'], 3)],
                device=device
            )
            qi_vec = self.qi_embed(qi_idx).expand(B, -1)  # [B, 4]

            # P1.3: Compress components to 52-dim key via learned projections
            key_field = self.berry_key_field_proj(self.spine.field_energy)           # [B, 13]
            key_compressed = self.berry_key_compressed_proj(compressed)              # [B, 16]
            key_conscious = self.berry_key_conscious_proj(conscious)                 # [B, 15]
            context = torch.cat([breath_vec, qi_vec], dim=-1)                        # [B, 6]
            key_context = self.berry_key_context_proj(context)                       # [B, 4]
            key_residual = self.berry_key_residual(brain_state)                      # [B, 4]
            key = torch.cat([
                key_field, key_compressed, key_conscious, key_context, key_residual,
            ], dim=-1)  # [B, 52]

            if self.berry_memory._n_filled > 0:
                retrieved, attn = self.berry_memory.query(key, temperature=0.1)
                pred_memory = self.memory_proj(retrieved)
                # Memory contributes only to horizon 1 (immediate prediction)
                pred[:, 0] = pred[:, 0] + self.memory_readout_scale * pred_memory
                info['memory_attn'] = attn.mean().item()

            # M4: Batch write to Berry memory (replace per-sample loop)
            if stem_info['state'] in {'earth', 'metal'} and self.training:
                with torch.no_grad():
                    value = self.berry_value_proj(conscious)  # [B, 39]
                    self.berry_memory.write(key.detach(), value.detach(), mode='ema')

        # Neuroplasticizer modulation for optimizer
        stem_info['surprise'] = surprise.item() if isinstance(surprise, torch.Tensor) else float(surprise)
        stem_info['disappointment'] = disappointment.item() if isinstance(disappointment, torch.Tensor) else float(disappointment)
        info['neuro_modulation'] = self.brainstem.get_neuro_modulation(stem_info)

        # Training loop compatibility keys
        info['conscious'] = conscious
        info.update(readout_info)
        info['surprise'] = surprise
        info['disappointment'] = disappointment
        info['mean_harmony'] = torch.tensor(stem_info['arousal'], device=device)
        info['qi_arousal'] = stem_info['arousal']
        # ── φ-balance regularisation (prevents Yang/Yin drift) ──
        # Workspace balance: forward ≈ retrospective (ratio → 1.0)
        w_fwd_norm = w_fwd.norm(dim=-1).mean()
        w_rev_norm = w_rev.norm(dim=-1).mean()
        workspace_balance_loss = 0.005 * ((w_fwd_norm / (w_rev_norm + 1e-8) - 1.0) ** 2)

        # Conscious balance: Yang-component / Yin-component → φ
        yang_comp_norm = (PHI_INV * w_fwd).norm(dim=-1).mean()
        yin_comp_norm = (PHI_INV ** 2 * w_rev).norm(dim=-1).mean()
        conscious_balance_loss = 0.005 * ((yang_comp_norm / (yin_comp_norm + 1e-8) - PHI) ** 2)

        phi_balance_loss = workspace_balance_loss + conscious_balance_loss
        info['phi_balance_loss'] = phi_balance_loss
        info['qi_energy_bonus'] = torch.tensor(0.0, device=device)

        # ── Sparsity regularisation ──
        l1_sparsity = 0.001 * conscious.abs().mean()
        info['sparsity_loss'] = l1_sparsity

        # ── Chakra entropy (specialist diversity for observability) ──
        field_energy = self.spine.field_energy  # [B, C]
        energy_probs = F.softmax(field_energy, dim=-1)
        chakra_entropy = -(energy_probs * torch.log(energy_probs + 1e-8)).sum(dim=-1).mean()
        info['chakra_entropy'] = chakra_entropy

        info['weights'] = stem_info['chakra_attention']

        # Observability keys for CassiMetrics
        info['workspace_fwd'] = w_fwd
        info['workspace_rev'] = w_rev
        info['qi_fluid'] = self.spine.qi_fluid
        info['energy'] = self.spine.field_energy
        yang_norm = w_fwd.norm(dim=-1).mean()
        yin_norm = w_rev.norm(dim=-1).mean()
        info['qi_ratio'] = (yang_norm / (yin_norm + 1e-8)).item()
        info['harmony'] = torch.tensor(stem_info['arousal'], device=device)

        # Breath metrics
        breath = stem_info.get('breath', {})
        for k in ['breath_yang', 'breath_yin', 'beat', 'flow', 'phase_diff', 'freq_ratio', 'pulse_active']:
            info[k] = breath.get(k, 0.0)

        # Process trajectory summary (for observability and future trajectory losses)
        info['trajectory_length'] = len(self._process_trajectory)
        if self._process_trajectory:
            info['trajectory_surprise'] = self._process_trajectory[-1].get('surprise', 0.0)
            info['trajectory_disappointment'] = self._process_trajectory[-1].get('disappointment', 0.0)

        # Store dynamics prediction for next batch's temporal loss
        with torch.no_grad():
            self._prev_predicted_next_conscious = predicted_next_conscious.detach().clone()

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

    def temporal_regularization_loss(self):
        """Regularization for temporal resonance readout."""
        if hasattr(self.readout, 'regularization_loss'):
            return self.readout.regularization_loss()
        return torch.tensor(0.0)

    def state_dict(self, *args, **kwargs):
        """Include all persistent buffers in checkpoint."""
        return super().state_dict(*args, **kwargs)

    def load_state_dict(self, state_dict, strict=True):
        """Load state dict with shape filtering and Qi-aware migration."""
        model_state = self.state_dict()
        filtered = {}
        for k, v in state_dict.items():
            if k in model_state:
                if v.shape == model_state[k].shape:
                    filtered[k] = v
                elif 'berry_memory.keys' in k and len(v.shape) == 2:
                    # Migrate memory keys: old shape [n_slots, old_key_dim] -> new [n_slots, new_key_dim]
                    old_dim = v.shape[1]
                    new_dim = model_state[k].shape[1]
                    if new_dim == old_dim + 4:
                        # Old migration: pad with zeros for qi_embed dims
                        padding = torch.zeros(v.shape[0], 4, dtype=v.dtype, device=v.device)
                        filtered[k] = torch.cat([v, padding], dim=1)
                        print(f"[CassiBrain] Migrated {k}: {v.shape} -> {filtered[k].shape} (padded qi_embed dims)")
                    elif old_dim > new_dim:
                        # New migration: old huge key (~3384) -> new compact key (52)
                        # Project old key dimensions down via PCA-style truncation
                        # Keep first new_dim columns (they contain the most variance in random init)
                        filtered[k] = v[:, :new_dim]
                        print(f"[CassiBrain] Migrated {k}: {v.shape} -> {filtered[k].shape} (truncated from huge key)")
                    else:
                        print(f"[CassiBrain] Skipping {k}: checkpoint {v.shape} vs model {model_state[k].shape}")
                else:
                    print(f"[CassiBrain] Skipping {k}: checkpoint {v.shape} vs model {model_state[k].shape}")
            else:
                if strict:
                    print(f"[CassiBrain] Missing key: {k}")
        # qi_embed will be randomly initialized if not in checkpoint — this is correct
        # for cold-start Qi keying (it will learn from training)
        return super().load_state_dict(filtered, strict=False)
