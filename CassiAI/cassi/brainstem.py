"""Brainstem — Bottleneck, Qi acupuncturist, and field conductor.

The brainstem sits between the spine (raw resonant field) and the brain
(expanded cognitive space). It:
  1. Reads the spine's field state
  2. Diagnoses the Five Qi States
  3. Modulates spine dynamics (theta, damping, Yang/Yin gain)
  4. Compresses field → bottleneck representation for the brain
  5. Detects pulses (stagnation → emergency learning)

Dimension flow: Spine(D) → Brainstem(D_stem=D//φ) → Brain(D_brain=D×φ)
"""

import math
import torch
import torch.nn as nn

from cassi.cord import PHI, PHI_INV
from cassi.breath import Breath


# ---------------------------------------------------------------------------
# Qi State Machine — Five States of Qi
# ---------------------------------------------------------------------------

class QiStateMachine:
    """Diagnose Qi state from (energy, bias, harmony) and apply modulatory profiles.

    The five states trace a cycle driven by breath and energy dynamics:
        Water → Wood → Fire → Earth → Metal → Water
    """

    PROFILES = {
        'water': {
            'lr_fast': 0.05, 'phi_fast': 0.95,
            'yang_gain': 0.3, 'yin_gain': 1.2,
            'gate': False, 'ns_boost': -2,
            'arousal_thresh': 0.05,
            'description': 'restoration/consolidation',
        },
        'wood': {
            'lr_fast': 0.4, 'phi_fast': 0.75,
            'yang_gain': 0.9, 'yin_gain': 0.7,
            'gate': True, 'ns_boost': 0,
            'arousal_thresh': 0.2,
            'description': 'exploration/emergence',
        },
        'fire': {
            'lr_fast': 1.0, 'phi_fast': 0.5,
            'yang_gain': 1.3, 'yin_gain': 0.3,
            'gate': True, 'ns_boost': +2,
            'arousal_thresh': 0.5,
            'description': 'peak activity/learning',
        },
        'earth': {
            'lr_fast': 0.6, 'phi_fast': 0.65,
            'yang_gain': 1.0, 'yin_gain': 1.0,
            'gate': True, 'ns_boost': 0,
            'arousal_thresh': 0.3,
            'description': 'harmony/stability',
        },
        'metal': {
            'lr_fast': 0.2, 'phi_fast': 0.85,
            'yang_gain': 0.6, 'yin_gain': 1.0,
            'gate': True, 'ns_boost': -1,
            'arousal_thresh': 0.15,
            'description': 'purification/consolidation',
        },
    }

    def __init__(self, energy_low=0.2, energy_high=0.8, bias_thresh=0.5,
                 harmony_thresh=0.3, balance_width=0.15):
        self.energy_low = energy_low
        self.energy_high = energy_high
        self.bias_thresh = bias_thresh
        self.harmony_thresh = harmony_thresh
        self.balance_width = balance_width
        self._state_ema = None  # EMA of recent state indices for hysteresis

    def compute(self, yang_norm, yin_norm, qi_energy, breath):
        """Diagnose current Qi state.

        Args:
            yang_norm: scalar, norm of Yang workspace
            yin_norm:  scalar, norm of Yin workspace
            qi_energy: scalar, total Qi energy (sum of qi_fluid)
            breath:    dict from Breath.step()

        Returns:
            state_name: one of 'water', 'wood', 'fire', 'earth', 'metal'
        """
        energy = (yang_norm + yin_norm) / 2.0
        total = yang_norm + yin_norm + 1e-8
        bias = yang_norm / total
        harmony = torch.tanh(qi_energy)

        # Earth = harmonized center (override regardless of energy)
        if harmony > self.harmony_thresh and abs(bias - 0.5) < self.balance_width:
            return 'earth'

        # Energy-based quadrants
        if energy < self.energy_low:
            return 'water' if bias < self.bias_thresh else 'wood'
        elif energy > self.energy_high:
            return 'fire' if bias > self.bias_thresh else 'metal'

        # Breath-driven transitions
        flow = breath.get('flow', 1.0)
        return 'wood' if flow > 0 else 'metal'

    def get_profile(self, state_name):
        return self.PROFILES[state_name]


# ---------------------------------------------------------------------------
# Brainstem
# ---------------------------------------------------------------------------

class Brainstem(nn.Module):
    """Active bottleneck between spine and brain.

    Args:
        D: spine dimension
        D_stem: bottleneck dimension (default D // φ)
        n_specialists: number of specialist voices (default 13 = chakras)
    """

    def __init__(self, D=1040, D_stem=None, n_specialists=13):
        super().__init__()
        self.D = D
        self.D_stem = D_stem if D_stem is not None else int(D / PHI)
        self.n_specialists = n_specialists

        # Breath conductor
        self.breath = Breath()

        # Qi State Machine
        self.qi = QiStateMachine()

        # Chakra attention: which frequency bands are salient?
        self.chakra_attn = nn.Sequential(
            nn.Linear(n_specialists, n_specialists // 2),
            nn.ReLU(),
            nn.Linear(n_specialists // 2, n_specialists),
        )

        # Homeostasis: learned per-chakra energy target scale
        self.homeo_scale = nn.Parameter(torch.ones(1))

        # Theta modulation: attention → frequency shift
        self.theta_mod = nn.Sequential(
            nn.Linear(D, D // 4),
            nn.ReLU(),
            nn.Linear(D // 4, 1),
        )

        # Damping modulation: regulation → damping scale
        self.damp_mod = nn.Sequential(
            nn.Linear(D, D // 4),
            nn.ReLU(),
            nn.Linear(D // 4, 1),
        )

        # Compression: spine field + qi_fluid → bottleneck
        self.compress = nn.Sequential(
            nn.Linear(D * 2, self.D_stem),
            nn.LayerNorm(self.D_stem),
        )
        # Small init so brainstem starts near zero
        for m in self.compress.modules():
            if isinstance(m, nn.Linear):
                nn.init.uniform_(m.weight, -0.01, 0.01)
                nn.init.zeros_(m.bias)

        # EMA state (persistent)
        self.register_buffer('focus', torch.zeros(1, D))
        self.register_buffer('regulation', torch.zeros(1, D))
        self.register_buffer('arousal', torch.zeros(1))
        self.register_buffer('focus_history', torch.zeros(20))  # for pulse detection
        self.register_buffer('_focus_idx', torch.zeros(1, dtype=torch.long))

    def reset_state(self, batch_size):
        """Reset all persistent brainstem buffers."""
        device = self.focus.device
        self.focus = torch.zeros(batch_size, self.D, device=device)
        self.regulation = torch.zeros(batch_size, self.D, device=device)
        self.arousal = torch.zeros(batch_size, device=device)
        # focus_history and _focus_idx are batch-independent
        self.focus_history.zero_()
        self._focus_idx.zero_()
        self.breath.reset()

    def _detect_pulse(self):
        """Detect stagnation in focus history → trigger emergency learning."""
        if self._focus_idx.item() < 20:
            return False
        recent = self.focus_history[-20:]
        rigidity = recent.std()
        return rigidity < 0.01

    def step(self, spine):
        """One brainstem step: read spine, diagnose, modulate, compress.

        Args:
            spine: CordPhysics instance with persistent state populated

        Returns:
            dict with keys:
                'compressed': [B, D_stem] — bottleneck for brain
                'state':      Qi state name
                'profile':    modulatory profile dict
                'arousal':    scalar arousal signal
                'theta_shift': frequency offset for spine
                'damp_scale': damping scale for spine
                'yang_gain':  Yang workspace gain
                'yin_gain':   Yin workspace gain
                'chakra_attention': [B, C] — per-chakra salience
        """
        B = spine.field_state.shape[0]
        device = spine.field_state.device

        # ── 1. Advance breath ──
        breath = self.breath.step()

        # ── 2. Diagnose Qi state ──
        yang_norm = spine.yang.norm(dim=-1).mean()
        yin_norm = spine.yin.norm(dim=-1).mean()
        qi_energy = spine.qi_fluid.sum(dim=-1).mean()
        state_name = self.qi.compute(yang_norm, yin_norm, qi_energy, breath)

        # Pulse override: stagnation → force Fire
        if self._detect_pulse():
            state_name = 'fire'

        profile = self.qi.get_profile(state_name)

        # ── 3. Update EMAs ──
        field_flat = spine.field_state.view(B, -1)
        self.focus = PHI_INV * self.focus + PHI_INV ** 2 * field_flat
        self.regulation = PHI_INV * self.regulation + PHI_INV ** 2 * field_flat.abs()

        # Update focus history for pulse detection
        focus_scalar = field_flat.norm(dim=-1).mean()
        idx = int(self._focus_idx.item()) % 20
        self.focus_history[idx] = focus_scalar
        self._focus_idx += 1

        # ── 4. Chakra attention + homeostasis ──
        # Attention: which chakras are salient?
        chakra_attention = torch.softmax(
            self.chakra_attn(spine.field_energy), dim=-1
        )  # [B, C]

        # Homeostasis: suppress overactive, boost underactive
        energy_target = spine.field_energy.mean(dim=0, keepdim=True)  # [1, C]
        energy_dev = spine.field_energy - energy_target  # [B, C]
        homeo_gain = torch.sigmoid(-energy_dev * self.homeo_scale)  # [B, C]

        # Apply per-chakra modulation to spine workspaces
        new_yang = spine.yang.clone()
        new_yin = spine.yin.clone()
        for c in range(spine.C):
            start, end = spine._offsets[c]
            attn_c = chakra_attention[:, c:c+1]
            homeo_c = homeo_gain[:, c:c+1]
            # Yang boosted by attention, Yin by (1-attention)
            new_yang[:, start:end] = spine.yang[:, start:end] * attn_c * homeo_c
            new_yin[:, start:end] = spine.yin[:, start:end] * (1.0 - attn_c) * homeo_c
        spine.yang = new_yang
        spine.yin = new_yin

        # ── 5. Compute modulatory signals ──
        theta_shift = torch.tanh(self.theta_mod(self.focus)).mean().item() * 0.3
        damp_scale = 1.0 + 0.2 * torch.tanh(self.damp_mod(self.regulation)).mean().item()

        # Arousal from Qi energy + breath beat
        arousal = torch.tanh(qi_energy / 10.0) + 0.1 * breath['beat']
        self.arousal = PHI_INV * self.arousal + PHI_INV ** 2 * arousal

        # Breath-modulated gains
        yang_gain = profile['yang_gain'] * (1.0 + 0.1 * breath['yang'].item())
        yin_gain = profile['yin_gain'] * (1.0 + 0.1 * breath['yin'].item())

        # ── 6. Apply spine modulation ──
        # Note: spine.step() was already called by the caller before brainstem.step()
        # The modulation here affects the NEXT spine step
        # We return the signals so the caller can pass them to spine.step() next iteration

        # ── 7. Compress for brain ──
        compressed = self.compress(
            torch.cat([spine.field_state, spine.qi_fluid], dim=-1)
        )  # [B, D_stem]

        return {
            'compressed': compressed,
            'state': state_name,
            'profile': profile,
            'arousal': self.arousal.mean().item(),
            'theta_shift': theta_shift,
            'damp_scale': damp_scale,
            'yang_gain': yang_gain,
            'yin_gain': yin_gain,
            'chakra_attention': chakra_attention.detach(),
            'breath': breath,
        }

    def get_neuro_modulation(self, spine_info):
        """Return neuroplasticizer modulation for the wave optimizer.

        Called by the training loop after brainstem.step().
        """
        profile = spine_info.get('profile', {})
        state = spine_info.get('state', 'earth')
        surprise = spine_info.get('surprise', 0.0)
        disappointment = spine_info.get('disappointment', 0.0)

        modulation = {
            'lr_scale': 1.0,
            'theta_shift': spine_info.get('theta_shift', 0.0),
            'reset_state': False,
        }

        # Pulse: boost LR + reset
        if state == 'fire' and self._detect_pulse():
            modulation['lr_scale'] = 2.0
            modulation['reset_state'] = True

        # Qi-state LR modulation
        modulation['lr_scale'] *= profile.get('lr_fast', 0.6) / 0.6

        # Surprise modulation: high surprise → exploratory higher LR
        # (the brain should learn faster from unexpected events)
        if surprise > 0.5:
            modulation['lr_scale'] *= 1.2
        elif surprise > 1.0:
            modulation['lr_scale'] *= 1.5

        # Disappointment modulation: high disappointment → conservative lower LR
        # (don't reinforce failures; consolidate instead)
        if disappointment > 0.3:
            modulation['lr_scale'] *= 0.8
        elif disappointment > 0.6:
            modulation['lr_scale'] *= 0.5

        return modulation
