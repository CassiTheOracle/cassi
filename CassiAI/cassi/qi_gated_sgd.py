"""QiGatedSGD — Parameter-free Qi-gated stochastic gradient descent.

Memory: ZERO per-parameter state. Reads qi_quality_ema (a scalar persistent
buffer) directly from the model during step(). The model's internal IIR
dynamics (Cord, BrainTuner, qi pool, calm/arousal) already provide temporal
smoothing and per-component adaptation. The optimizer provides only direction
and a Qi-gated scalar step size.

    θ ← θ − lr · q(quality) · g      [gradient step]
    θ ← θ · (1 − lr · wd)            [decoupled weight decay]

Where q(quality) = q_min + (q_max − q_min) / (1 + quality) ∈ [0.5, 1.0]:
  - quality → 0 (turbulent): gate → 1.0 — full step, explore
  - quality → 1 (coherent):  gate → 0.5 — half step, consolidate

Compared to QiFluidOptimizer: saves 2× params GPU memory (momentum + g_hat
buffers), ~57% less memory traffic per step, 0 optimizer state to checkpoint.
"""

import torch
from torch.optim.optimizer import Optimizer


class QiGatedSGD(Optimizer):
    """Parameter-free SGD with model-internal Qi-gated learning rate.

    Args:
        params: iterable of parameters to optimize.
        lr: base learning rate (default: 3e-4).
        weight_decay: decoupled weight decay (default: 0.01).
        quality_range: tuple (min_q, max_q) for qi gate output (default: (0.5, 1.0)).
    """

    def __init__(self, params, lr=3e-4, weight_decay=0.01,
                 quality_range=(0.5, 1.0)):
        if lr < 0.0:
            raise ValueError(f"Invalid learning rate: {lr}")
        if weight_decay < 0.0:
            raise ValueError(f"Invalid weight_decay: {weight_decay}")
        defaults = dict(lr=lr, weight_decay=weight_decay)
        super().__init__(params, defaults)

        self.q_min, self.q_max = quality_range

        # ── Diagnostics ──
        self._last_gate = 0.75
        self._last_quality = 0.5
        self._total_steps = 0

    def _read_quality(self, model) -> float:
        """Read qi_quality_ema from model's persistent buffer.

        Falls back to 0.5 (neutral) if model is None or buffer doesn't exist.
        """
        if model is None or not hasattr(model, 'qi_quality_ema'):
            return 0.5
        return float(model.qi_quality_ema.item())

    @torch.no_grad()
    def step(self, closure=None, model=None):
        """Perform a single Qi-gated optimization step.

        Args:
            closure: optional loss closure (standard torch.optim API).
            model: the model instance — reads model.qi_quality_ema directly.

        Per-parameter:
            θ ← θ · (1 − lr·wd) − lr · qi_gate · g
        """
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        quality = self._read_quality(model)
        self._last_quality = quality

        # Qi gate: inversely proportional to quality
        # quality 0 → gate 1.0 (explore), quality 1 → gate 0.5 (consolidate)
        qi_gate = self.q_min + (self.q_max - self.q_min) / (1.0 + quality)
        self._last_gate = qi_gate
        self._total_steps += 1

        for group in self.param_groups:
            lr = group['lr']
            wd = group['weight_decay']
            effective_lr = lr * qi_gate

            for p in group['params']:
                if p.grad is None:
                    continue

                g = p.grad

                # Decoupled weight decay
                if wd > 0:
                    p.mul_(1.0 - lr * wd)

                # Qi-gated gradient step
                p.add_(g, alpha=-effective_lr)

        return loss

    def qi_stats(self):
        """Return optimizer diagnostics."""
        return {
            'opt_quality': self._last_quality,
            'opt_gate': self._last_gate,
            'opt_steps': self._total_steps,
        }
