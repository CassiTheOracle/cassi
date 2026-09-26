"""QiCycle — Global Qi state conductor.

Centralizes Qi diagnosis and broadcasts transitions to subscribers.
Prevents state flicker via hysteresis (N consecutive diagnoses required).
"""

from collections import deque


class QiCycle:
    """Global Qi state conductor. Owns the cycle, broadcasts transitions."""

    STATES = ['water', 'wood', 'fire', 'earth', 'metal']

    def __init__(self, brainstem_qi, hysteresis=3):
        self.state = 'earth'
        self._pending_state = 'earth'
        self._pending_count = 0
        self._hysteresis = hysteresis
        self._history = deque(maxlen=100)
        self._subscribers = []
        self._brainstem_qi = brainstem_qi
        self._transition_count = 0

    def subscribe(self, obj):
        """Register an object with set_qi_profile(profile) method."""
        if hasattr(obj, 'set_qi_profile'):
            self._subscribers.append(obj)

    def step(self, yang_norm, yin_norm, qi_energy, breath,
             dream_bank_pressure=None, changepoint_confidence=0.0):
        """Diagnose next state and broadcast if changed.

        Args:
            yang_norm: scalar, norm of Yang workspace
            yin_norm: scalar, norm of Yin workspace
            qi_energy: scalar, total Qi energy
            breath: dict from Breath.step()
            dream_bank_pressure: dict of per-bank fill ratios
            changepoint_confidence: float, changepoint detection confidence

        Returns:
            state_name: current Qi state after hysteresis
        """
        dream_bank_pressure = dream_bank_pressure or {}

        # Base diagnosis from brainstem logic
        # update_history=False because brainstem.step() already updated history
        # on the representative frame. QiCycle should not double-count.
        new_state = self._brainstem_qi.compute(
            yang_norm, yin_norm, qi_energy, breath, update_history=False
        )

        # System-level overrides
        if dream_bank_pressure.get('water', 0) > 0.5:
            new_state = 'water'
        elif changepoint_confidence > 0.8:
            # High-confidence changepoint → Metal (purification) regardless of base state
            new_state = 'metal'
        elif dream_bank_pressure.get('metal', 0) > 0.8:
            new_state = 'metal'

        # Hysteresis: require N consecutive diagnoses before transitioning
        if new_state == self._pending_state:
            self._pending_count += 1
        else:
            self._pending_state = new_state
            self._pending_count = 1

        if self._pending_count >= self._hysteresis and new_state != self.state:
            self._transition(self.state, new_state)

        self._history.append(self.state)
        return self.state

    def _transition(self, old, new):
        self.state = new
        self._transition_count += 1
        profile = self._brainstem_qi.get_profile(new)
        profile['state'] = new  # embed state name for subscribers
        for sub in self._subscribers:
            sub.set_qi_profile(profile)

    @property
    def profile(self):
        """Current Qi profile (lr_fast, yang_gain, etc.)."""
        p = self._brainstem_qi.get_profile(self.state)
        p['state'] = self.state
        return p
