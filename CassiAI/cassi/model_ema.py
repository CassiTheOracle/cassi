"""ModelEMA — Exponential moving average of model parameters.

Maintains a shadow copy of parameters with EMA decay. The EMA weights are
typically more stable and generalize better than the raw training weights.
Only tracks learnable parameters, not buffers (which may be batch-dependent).

Implementation uses direct parameter data copies instead of state_dict
round-trips. This avoids large allocations and ROCm synchronization stalls
that were observed when apply/restore cloned the full model state.
"""

import torch


class ModelEMA:
    """Exponential moving average of model parameters.

    Args:
        model: nn.Module to track
        decay: EMA decay rate (default 0.9999)
        device: where to store the shadow copy
    """

    def __init__(self, model, decay=0.9999, device=None):
        self.decay = max(0.0, min(1.0, float(decay)))
        self.device = device
        self._shadow_applied = False

        # Build shadow parameter dict (only parameters, not buffers)
        self.params = {}
        with torch.no_grad():
            for name, p in model.named_parameters():
                if p.requires_grad:
                    target_device = device if device is not None else p.device
                    self.params[name] = p.detach().clone().to(target_device)

    def update(self, model):
        """One EMA update step."""
        with torch.no_grad():
            one_minus_decay = 1.0 - self.decay
            for name, p in model.named_parameters():
                if p.requires_grad and name in self.params:
                    target_device = self.device if self.device is not None else p.device
                    model_p = p.detach().to(target_device)
                    self.params[name].mul_(self.decay).add_(model_p, alpha=one_minus_decay)

    def state_dict(self):
        return {
            'decay': self.decay,
            'params': {k: v.detach().clone() for k, v in self.params.items()},
        }

    def load_state_dict(self, state_dict):
        if not isinstance(state_dict, dict):
            raise TypeError(f"ModelEMA.load_state_dict expects dict, got {type(state_dict)}")
        if 'params' not in state_dict:
            raise KeyError("ModelEMA state_dict missing 'params' key")
        self.decay = max(0.0, min(1.0, float(state_dict.get('decay', self.decay))))
        loaded = state_dict['params']
        for name in list(self.params):
            if name in loaded:
                target_device = self.device if self.device is not None else self.params[name].device
                self.params[name] = loaded[name].detach().clone().to(target_device)

    def apply_shadow(self, model):
        """Copy EMA weights into model (use before validation/save).

        Stores raw weights so they can be restored.
        """
        if self._shadow_applied:
            return
        self._raw_state = {}
        with torch.no_grad():
            for name, p in model.named_parameters():
                if p.requires_grad and name in self.params:
                    self._raw_state[name] = p.data.detach().clone()
                    p.data.copy_(self.params[name].to(p.device))
        self._shadow_applied = True

    def restore(self, model):
        """Restore model's raw training weights after validation."""
        if not self._shadow_applied or self._raw_state is None:
            return
        with torch.no_grad():
            for name, p in model.named_parameters():
                if name in self._raw_state:
                    p.data.copy_(self._raw_state[name].to(p.device))
        self._shadow_applied = False
        self._raw_state = None
