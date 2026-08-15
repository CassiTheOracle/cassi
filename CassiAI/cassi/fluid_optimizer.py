#!/usr/bin/env python3
"""FluidOptimizer — Qi-driven learning rate for FluidCord.

Eliminates the learning rate hyperparameter by coupling it to the field's
own state (Qi density) via the architecture's φ-scaling.

Two modes:
    FluidLRScheduler  — Qi-modulated AdamW (safe, recommended)
    FluidOptimizer    — Pure unit-norm + Qi damping (experimental)

The scheduler replaces `--lr` and manual LR schedules. It uses AdamW
internally (β₁=0.9, β₂=0.999, ε=1e-8) and only modulates the effective LR:
    lr = σ₀ · φ⁻¹/√t · 1/(1+Q̄)
where σ₀ = 0.02 matches the model's parameter init scale.
"""

import math
from typing import Optional

import torch
import torch.optim
from torch.optim import Optimizer

from cassi._chakra_utils import PHI, PHI_INV


class FluidLRScheduler:
    """Qi-modulated learning rate scheduler for AdamW.

    Eliminates the learning rate hyperparameter. Uses the field's Qi density
    as the sole feedback signal — no LR, no schedule, no warmup to tune.

    Decay:         φ⁻¹/√t       (Robbins-Monro with φ-damping)
    Qi damping:    1/(1+Q̄)      (high field energy → smaller steps)
    Init scale:    σ₀ = 0.02    (matches architecture's init_std)

    Usage:
        opt = torch.optim.AdamW(model.parameters())
        scheduler = FluidLRScheduler(opt)
        ...
        loss, info = model.training_loss(x)
        loss.backward()
        scheduler.step(qi_mean=info['qi_mean'])  # before opt.step()
        opt.step()
    """

    def __init__(self, optimizer: torch.optim.Optimizer,
                 default_lr: float = 1e-3):
        self.optimizer = optimizer
        self.default_lr = default_lr
        self.step_count = 0
    def step(self, qi_mean: float = 0.0):
        """Update LR: AdamW default (1e-3) with φ-damping and Qi modulation.

        lr = 1e-3 × φ⁻¹ / (1 + Q̄)

        No schedule — Qi IS the schedule. High field energy → smaller steps,
        low field energy → larger steps. φ⁻¹ provides mild conservative bias.
        """
        self.step_count += 1
        lr = self.default_lr * PHI_INV / (1.0 + qi_mean)
        for group in self.optimizer.param_groups:
            group['lr'] = lr

    def state_dict(self):
        return {'step_count': self.step_count}

    def load_state_dict(self, state_dict):
        self.step_count = state_dict['step_count']


class FluidUnitNormOptimizer(Optimizer):
    """Experimental: pure unit-norm gradients + Qi damping.

    Uses per-parameter unit-norm gradients without Adam's momentum or
    second-moment scaling.  Considerably more aggressive than the scheduler
    approach above — the `g/‖g‖` normalization discards curvature information
    that Adam's v̂ provides.

    Suitable for the 6 PDE logits (where the physics coupling makes sense)
    but not recommended as the sole optimizer for embedder/readout weights
    without thorough validation.

    Usage:
        opt = FluidUnitNormOptimizer(model.parameters())
        ...
        opt.step(qi_mean=info['qi_mean'])
    """

    def __init__(self, params, init_std: float = 0.02, eps: float = 1e-12):
        defaults = dict(init_std=init_std, eps=eps)
        super().__init__(params, defaults)
        self.step_count = 0

    @torch.no_grad()
    def step(self, closure=None, qi_mean: float = 0.0):
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        self.step_count += 1
        t = float(self.step_count)

        for group in self.param_groups:
            sigma0 = group['init_std']
            eps = group['eps']

            for p in group['params']:
                if p.grad is None:
                    continue
                g = p.grad
                g_norm = g.norm()
                if g_norm < eps:
                    continue
                g_unit = g / g_norm
                lr = sigma0 * PHI_INV / math.sqrt(t) / (1.0 + qi_mean)
                p.add_(-lr * g_unit)

        return loss
