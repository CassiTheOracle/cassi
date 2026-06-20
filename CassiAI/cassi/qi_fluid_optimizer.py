"""
QiFluidOptimizer — Gradient optimization via the QiFluid principle.

Each parameter's gradient stream is treated as a 1-element resonant field:
  - IIR momentum (φ-damped, like CordPhysics)
  - Self-prediction: the optimizer predicts the next gradient from momentum
  - Qi = |g|² · |g − ĝ|²  — surprise density
  - Qi-modulated learning: high surprise → explore, low surprise → exploit

Memory: 2 states per parameter (same as AdamW)
  1. m : IIR momentum buffer [same shape as param]
  2. g_hat : predicted gradient [same shape as param]

Core update:
    m_t  = φ⁻¹ · m_{t-1} + (1−φ⁻¹) · g_t
    ĝ_t  = β  · m_{t-1}                       (self-prediction)
    ε_t  = g_t − ĝ_t                           (prediction error)
    Q_t  = g_t² · ε_t²                         (Qi density, per-element)
    α_t  = clamp(α_base + α_scale · Q_t)      (Qi-modulated LR factor)
    θ_t  = θ_{t-1} − lr · α_t · m_t − wd · θ  (parameter update)

Where β starts at φ⁻¹ and adapts online via EMA of g/m ratio.
"""

import math
import torch
from torch.optim.optimizer import Optimizer

PHI = (1 + 5 ** 0.5) / 2
PHI_INV = 1 / PHI


class QiFluidOptimizer(Optimizer):
    """QiFluid gradient optimizer with self-prediction and Qi-driven LR.

    Args:
        params: iterable of parameters to optimize
        lr: base learning rate (default: 3e-4)
        weight_decay: decoupled weight decay (default: 0.01)
        rho: IIR momentum damping (default: PHI_INV ≈ 0.618)
        alpha_base: minimum LR multiplier (default: 0.5 — "exploit" floor)
        alpha_scale: Qi → LR scaling (default: 1.0)
        alpha_max: maximum LR multiplier (default: 5.0 — "explore" ceiling)
        beta_init: initial self-prediction gain (default: PHI_INV)
        beta_lr: learning rate for online β adaptation (default: 0.001)
        eps: numerical stability (default: 1e-8)
    """

    def __init__(self, params, lr=3e-4, weight_decay=0.01,
                 rho=PHI_INV, alpha_base=1.0, alpha_scale=1.0,
                 alpha_max=3.0, beta_init=PHI_INV, beta_lr=0.001,
                 eps=1e-8):
        if lr < 0.0:
            raise ValueError(f"Invalid lr: {lr}")
        if weight_decay < 0.0:
            raise ValueError(f"Invalid weight_decay: {weight_decay}")
        if not (0.0 < rho < 1.0):
            raise ValueError(f"rho must be in (0,1), got {rho}")
        if alpha_scale < 0.0:
            raise ValueError(f"alpha_scale must be non-negative: {alpha_scale}")
        if alpha_max < alpha_base:
            raise ValueError(f"alpha_max ({alpha_max}) < alpha_base ({alpha_base})")

        defaults = dict(lr=lr, weight_decay=weight_decay, rho=rho,
                        alpha_base=alpha_base, alpha_scale=alpha_scale,
                        alpha_max=alpha_max, beta_init=beta_init,
                        beta_lr=beta_lr, eps=eps)
        super().__init__(params, defaults)

        # Per-group running statistics (for diagnostics)
        self._group_stats = []

    @torch.no_grad()
    def step(self, closure=None):
        """Performs a single QiFluid optimization step.

        On each call, for every parameter:
        1. IIR-filter the gradient (φ-damped momentum)
        2. Self-predict: what gradient did we expect?
        3. Compute Qi = surprise density
        4. Modulate effective LR by Qi
        5. Apply update with decoupled weight decay
        """
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        stats = []

        for group in self.param_groups:
            lr = group['lr']
            wd = group['weight_decay']
            rho = group['rho']
            alpha_base = group['alpha_base']
            alpha_scale = group['alpha_scale']
            alpha_max = group['alpha_max']
            beta_lr = group['beta_lr']
            eps = group['eps']

            group_qi_sum = 0.0
            group_n = 0

            for p in group['params']:
                if p.grad is None:
                    continue

                grad = p.grad
                state = self.state[p]

                # ── Lazy state init ──
                if len(state) == 0:
                    state['m'] = torch.zeros_like(p)          # momentum
                    state['g_hat'] = torch.zeros_like(p)      # predicted gradient
                    state['beta'] = group['beta_init']        # scalar predictor gain

                m = state['m']
                g_hat = state['g_hat']
                beta = state['beta']

                # ── 1. IIR momentum: m_t = ρ·m_{t-1} + (1−ρ)·g_t ──
                m.mul_(rho).add_(grad, alpha=1.0 - rho)

                # ── 2. Self-prediction: ĝ_t = β·m_{t-1} (using old m) ──
                # g_hat already holds β·m_{t-1} from previous step.
                # We'll store β·m_t for next step AFTER the update.

                # ── 3+4. Qi-modulated LR (fused, single scratch buffer) ──
                # Compute α = clamp(α_base + α_scale · clamp(g²·(g−ĝ)², max=1/α_scale), max=α_max)
                # Reuse g_hat as scratch (will be overwritten in step 7), allocate
                # one temporary for grad². Original: 6 allocations → 1.
                g_hat.neg_().add_(grad)          # g_hat = ε = grad − g_hat_old
                g_hat.pow_(2)                    # g_hat = ε²
                scratch = torch.empty_like(grad)
                torch.square(grad, out=scratch)  # scratch = grad²
                g_hat.mul_(scratch)              # g_hat = qi = ε² · grad²
                g_hat.clamp_(max=1.0 / max(alpha_scale, eps))
                g_hat.mul_(alpha_scale).add_(alpha_base)
                g_hat.clamp_(max=alpha_max)
                # g_hat now holds per-element α; will be overwritten in step 7
                alpha = g_hat  # alias for readability

                # ── 5. Decoupled weight decay ──
                if wd != 0:
                    p.mul_(1.0 - lr * wd)

                # ── 6. Parameter update ──
                # θ = θ − lr · α · m̂  where m̂ is RMS-normalized momentum.
                # Without normalization, parameters with small gradients (IIR
                # rho, gates) move orders of magnitude slower than readout
                # layers, preventing learned dynamics from adapting.
                # RMS normalization makes updates scale-invariant like AdamW:
                # |m̂| ≈ 1 regardless of gradient magnitude.
                m_rms = scratch.copy_(m).pow_(2).mean().sqrt() + eps
                p.addcmul_(m, alpha, value=-lr / m_rms)
                # ── Diagnostics (capture α mean before g_hat is overwritten) ──
                group_qi_sum += alpha.mean().item()

                # ── 7. Update self-predictor ──
                # Adapt β online: move toward g/m ratio when momentum is non-zero.
                # β_new = β − β_lr * (ε · sign(m))  — gradient of |ε|² w.r.t. β
                # But simpler: β = EMA(g_norm / m_norm) with decay 0.99
                m_norm = m.norm()
                g_norm = grad.norm()
                if m_norm > eps:
                    ratio = g_norm / m_norm
                    beta = 0.99 * beta + 0.01 * ratio.item()
                    beta = max(0.01, min(beta, 10.0))
                state['beta'] = beta

                # Store prediction for next step: ĝ_{t+1} = β·m_t
                g_hat.copy_(m).mul_(beta)

                group_n += 1

            if group_n > 0:
                stats.append({
                    'Q_mean': group_qi_sum / group_n,
                    'beta': state.get('beta', group['beta_init']),
                })

        self._group_stats = stats
        return loss

    def qi_stats(self):
        """Return Qi diagnostics from the last step."""
        if not self._group_stats:
            return {'Q_mean': 0.0, 'Q_max': 0.0}
        q_means = [s['Q_mean'] for s in self._group_stats]
        return {
            'Q_mean': sum(q_means) / len(q_means),
            'Q_max': max(q_means),
        }
