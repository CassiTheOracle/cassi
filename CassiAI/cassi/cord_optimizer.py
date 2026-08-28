#!/usr/bin/env python3
"""
CordOptimizer — φ-damped IIR momentum optimizer.

Inspired by Cassi's CordPhysics IIR spine: a single second-order resonant
filter with damping ρ = PHI_INV. For parameter updates, we use a first-order
EMA (momentum) with the same φ-scaled decay.

Replaces AdamW's two states (exp_avg, exp_avg_sq) with one IIR momentum.
Cuts optimizer state memory by 50%.

Update rule:
    m_t = ρ · m_{t-1} + (1 − ρ) · g_t
    θ_t = θ_{t-1} − lr · m_t − lr · wd · θ_{t-1}

Where ρ = 1/φ ≈ 0.618.  This is equivalent to SGD with momentum β = ρ.
"""

import torch
from torch.optim.optimizer import Optimizer

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1 / PHI


class CordOptimizer(Optimizer):
    """
    Args:
        params: iterable of parameters to optimize
        lr: learning rate (default: 2e-4)
        rho: IIR damping / momentum decay (default: PHI_INV ≈ 0.618)
        weight_decay: decoupled weight decay (default: 0.01)
    """

    def __init__(self, params, lr=2e-4, rho=PHI_INV, weight_decay=0.01):
        if lr < 0.0:
            raise ValueError(f"Invalid learning rate: {lr}")
        if rho < 0.0 or rho > 1.0:
            raise ValueError(f"Invalid rho: {rho}")
        if weight_decay < 0.0:
            raise ValueError(f"Invalid weight_decay: {weight_decay}")

        defaults = dict(lr=lr, rho=rho, weight_decay=weight_decay)
        super().__init__(params, defaults)

    @torch.no_grad()
    def step(self, closure=None):
        """Performs a single optimization step."""
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        for group in self.param_groups:
            lr = group["lr"]
            rho = group["rho"]
            wd = group["weight_decay"]

            for p in group["params"]:
                if p.grad is None:
                    continue

                grad = p.grad
                state = self.state[p]

                # Lazy state init
                if len(state) == 0:
                    state["momentum"] = torch.zeros_like(p)

                m = state["momentum"]

                # IIR filter on gradient: m_t = ρ·m_{t-1} + (1−ρ)·g_t
                m.mul_(rho).add_(grad, alpha=1 - rho)

                # Decoupled weight decay
                if wd != 0:
                    p.mul_(1 - lr * wd)

                # Parameter update
                p.add_(m, alpha=-lr)

        return loss
