"""CuriosityEngine — Phase 8 curiosity-driven curriculum.

The model chooses what to learn next based on prediction error and
metacognitive signals. High error + high curiosity → sample more of that
modality. Qi energy acts as temperature: Fire=explore, Water=exploit.
"""

import math
import warnings
from collections import deque
from typing import Dict, List, Optional

import torch
import torch.nn.functional as F


class CuriosityEngine:
    """Adaptive curriculum based on prediction error and curiosity.

    Tracks a rolling window of per-modality validation metrics and emits
    sampling probabilities. Higher error → higher sampling weight.
    Temperature is derived from Qi state / energy:
      - high temperature (Fire) → more uniform, exploratory
      - low temperature (Water) → peaked on worst-performing modality
    """

    def __init__(self, modalities: List[str], window_size: int = 5,
                 min_weight: float = 0.05, temperature_default: float = 1.0):
        if not modalities:
            raise ValueError("CuriosityEngine requires at least one modality")
        self.modalities = list(dict.fromkeys(modalities))  # preserve order, remove dups
        self.window_size = max(1, int(window_size))
        self.min_weight = max(0.0, float(min_weight))
        self.temperature_default = max(1e-3, float(temperature_default))
        self._history = {m: deque(maxlen=self.window_size) for m in self.modalities}
        self._curiosity = {m: 0.0 for m in self.modalities}

    def update(self, modality: str, error: float, curiosity: Optional[float] = None):
        """Record a validation/training error for a modality."""
        if modality not in self._history:
            warnings.warn(f"CuriosityEngine: unknown modality '{modality}', known={self.modalities}")
            return
        self._history[modality].append(float(error))
        if curiosity is not None:
            self._curiosity[modality] = 0.9 * self._curiosity[modality] + 0.1 * float(curiosity)

    def compute_weights(self, temperature: Optional[float] = None) -> Dict[str, float]:
        """Return sampling weights for each modality.

        Weights are proportional to softmax(error / temperature).
        """
        temperature = self.temperature_default if temperature is None else max(float(temperature), 1e-3)

        scores = []
        for m in self.modalities:
            errs = list(self._history[m])
            if errs:
                score = sum(errs) / len(errs)
            else:
                score = 1.0  # default to moderate curiosity for unseen modalities
            # Add curiosity bonus (bounded to prevent runaway scaling)
            curiosity_bonus = min(max(self._curiosity[m], 0.0), 1.0)
            score = score * (1.0 + curiosity_bonus)
            scores.append(score)

        scores_t = torch.tensor(scores, dtype=torch.float32)
        weights_t = F.softmax(scores_t / temperature, dim=0)
        weights = {m: float(w) for m, w in zip(self.modalities, weights_t.tolist())}

        # Enforce minimum weight so no modality is fully starved
        if self.min_weight > 0.0:
            for m in weights:
                weights[m] = max(weights[m], self.min_weight)
            total = sum(weights.values())
            if total > 0.0:
                for m in weights:
                    weights[m] /= total

        return weights

    def state_dict(self) -> Dict:
        return {
            'modalities': self.modalities,
            'window_size': self.window_size,
            'min_weight': self.min_weight,
            'temperature_default': self.temperature_default,
            'history': {m: list(v) for m, v in self._history.items()},
            'curiosity': dict(self._curiosity),
        }

    def load_state_dict(self, state: Dict):
        if not isinstance(state, dict):
            raise TypeError(f"CuriosityEngine.load_state_dict expects dict, got {type(state)}")
        modalities = list(state.get('modalities', self.modalities))
        if not modalities:
            raise ValueError("Loaded state contains no modalities")
        self.modalities = modalities
        self.window_size = int(state.get('window_size', self.window_size))
        self.min_weight = float(state.get('min_weight', self.min_weight))
        self.temperature_default = max(1e-3, float(state.get('temperature_default', self.temperature_default)))
        self._history = {m: deque(state.get('history', {}).get(m, []), maxlen=self.window_size)
                         for m in self.modalities}
        loaded_curiosity = state.get('curiosity', {}) or {}
        self._curiosity = {m: float(loaded_curiosity.get(m, 0.0))
                           for m in self.modalities}

    def qi_temperature(self, qi_state: Optional[str], qi_energy: float) -> float:
        """Map Qi state + energy to sampling temperature.

        Returns:
            float > 0: higher = more exploratory
        """
        base = {
            'water': 0.5,   # exploit: focus on worst modality
            'metal': 0.7,
            'earth': 1.0,   # balanced
            'wood':  1.3,
            'fire':  2.0,   # explore: more uniform sampling
        }.get(qi_state if qi_state is not None else 'earth', 1.0)
        # High Qi energy → amplify temperature
        energy_factor = 1.0 + math.tanh(float(qi_energy) / 10.0)
        return base * energy_factor
