"""ResonantIIR — Phi-damped IIR optimizer.

Replaces AdamW with a resonant filter applied to gradients.
Uses the same IIR grammar as CordPhysics: phi-damped, theta-tuned,
recurrence. Memory footprint depends on configuration:

- order=1, non-adaptive: 1 state/param
- order=1, adaptive:     2 states/param (same as AdamW)
- order=2, non-adaptive: 2 states/param (same as AdamW)
- order=2, adaptive:     3 states/param

Two operating modes:
- order=2: second-order resonant filter (m_prev, m_prev2)
- order=1: first-order IIR / EMA (m_prev only)

Optional adaptive mode adds AdamW-style per-parameter variance scaling.

Core update (non-adaptive, order=2):
    m_t = b0 * g_t + a1 * m_{t-1} + a2 * m_{t-2}
    p_{t+1} = p_t - lr * m_t - wd * p_t

    a1 =  2 * phi_damp * cos(theta)
    a2 = -(phi_damp)^2

Core update (order=1):
    m_t = b0 * g_t + a1 * m_{t-1}
    a1 = phi_damp
    b0 = 1 - phi_damp

Adaptive update:
    v_t = beta2 * v_{t-1} + (1 - beta2) * g_t^2
    p_{t+1} = p_t - lr * m_t / (sqrt(v_t) + eps) - wd * p_t

Neuroplasticizer modulation:
    - lr_scale: multiplies effective learning rate
    - theta_shift: shifts resonance frequency (order=2 only)
    - reset_state: zeroes momentum history (pulse onset)
"""

import math
import torch
from torch.optim.optimizer import Optimizer

from cassi.cord import PHI_INV


class ResonantIIR(Optimizer):
    """Resonant IIR optimizer with phi-damped gradient filtering.

    Args:
        params: iterable of parameters to optimize
        lr: learning rate (default: 2e-4)
        weight_decay: L2 penalty (default: 0.01)
        theta: resonance angle in radians (default: π/4); used only for order=2
        phi_damp: damping factor, must be in (0, 1) (default: PHI_INV ≈ 0.618)
        b0: feedforward gain on current gradient. If None, computed for unit DC gain.
        order: 1 or 2 (default 2). Order-1 is a first-order EMA-style IIR and
               supports adaptive mode with only 2 states total.
        adaptive: if True, include a per-parameter variance estimate (AdamW-style).
        beta2: EMA decay for variance in adaptive mode (default: 0.999)
        eps: denominator stability in adaptive mode (default: 1e-8)
    """

    def __init__(self, params, lr=2e-4, weight_decay=0.01,
                 theta=math.pi / 4.0, phi_damp=PHI_INV, b0=None,
                 order=2, adaptive=False, beta2=0.999, eps=1e-8):
        if lr < 0.0:
            raise ValueError(f"Invalid lr: {lr}")
        if weight_decay < 0.0:
            raise ValueError(f"Invalid weight_decay: {weight_decay}")
        if not (0.0 < phi_damp < 1.0):
            raise ValueError(f"phi_damp must be in (0,1), got {phi_damp}")
        if order not in (1, 2):
            raise ValueError(f"order must be 1 or 2, got {order}")
        if not (0.0 <= beta2 < 1.0):
            raise ValueError(f"beta2 must be in [0,1), got {beta2}")
        theta = float(theta)
        theta = max(0.05, min(math.pi - 0.05, theta))

        if order == 2:
            a1_tmp = 2.0 * phi_damp * math.cos(theta)
            a2_tmp = -(phi_damp ** 2)
            if b0 is None:
                b0 = max(1.0 - a1_tmp - a2_tmp, 1e-3)
            else:
                b0 = float(b0)
                if b0 <= 0:
                    raise ValueError(f"b0 must be positive, got {b0}")
        else:
            a1_tmp = phi_damp
            a2_tmp = 0.0
            if b0 is None:
                b0 = 1.0 - phi_damp
            else:
                b0 = float(b0)
                if b0 <= 0:
                    raise ValueError(f"b0 must be positive, got {b0}")

        defaults = dict(lr=lr, weight_decay=weight_decay,
                        theta=theta, phi_damp=phi_damp, b0=b0,
                        order=int(order), adaptive=bool(adaptive),
                        beta2=float(beta2), eps=float(eps))
        super().__init__(params, defaults)

    def _compute_coeffs(self, group):
        """Compute IIR coefficients from hyperparameters."""
        phi = group['phi_damp']
        theta = group['theta']
        if group['order'] == 2:
            a1 = 2.0 * phi * math.cos(theta)
            a2 = -(phi ** 2)
        else:
            a1 = phi
            a2 = 0.0
        b0 = group['b0']
        return a1, a2, b0

    @torch.no_grad()
    def step(self, closure=None, neuro_modulation=None):
        """Performs a single optimization step.

        Args:
            closure: A closure that reevaluates the model and returns the loss.
            neuro_modulation: dict with optional keys:
                - 'lr_scale' (float): multiplier on effective LR
                - 'theta_shift' (float): added to theta for this step
                - 'reset_state' (bool): if True, zero all momentum history
        """
        loss = None
        if closure is not None:
            with torch.enable_grad():
                loss = closure()

        if neuro_modulation is None:
            neuro_modulation = getattr(self, '_neuro_modulation', None)

        neuro = neuro_modulation or {}
        lr_scale = float(neuro.get('lr_scale', 1.0))
        theta_shift = float(neuro.get('theta_shift', 0.0))
        reset_state = bool(neuro.get('reset_state', False))

        for group in self.param_groups:
            lr = group['lr'] * lr_scale
            wd = group['weight_decay']
            theta = group['theta'] + theta_shift
            theta = max(0.05, min(math.pi - 0.05, theta))
            order = group['order']
            adaptive = group['adaptive']
            beta2 = group['beta2']
            eps = group['eps']

            a1, a2, b0 = self._compute_coeffs({**group, 'theta': theta})

            for p in group['params']:
                if p.grad is None:
                    continue

                grad = p.grad
                if grad.is_sparse:
                    raise RuntimeError("ResonantIIR does not support sparse gradients")

                state = self.state[p]
                if len(state) == 0:
                    state['m_prev'] = torch.zeros_like(p)
                    if order == 2:
                        state['m_prev2'] = torch.zeros_like(p)
                    if adaptive:
                        state['v'] = torch.zeros_like(p)
                        state['step'] = 0

                m_prev = state['m_prev']
                m_prev2 = state.get('m_prev2', None)

                if reset_state:
                    m_prev.zero_()
                    if m_prev2 is not None:
                        m_prev2.zero_()
                    if adaptive:
                        state['v'].zero_()
                        state['step'] = 0

                # Weight decay (decoupled, like AdamW)
                if wd != 0:
                    p.mul_(1.0 - lr * wd)

                # Compute filtered gradient m_t into a workspace.
                if order == 2:
                    # Reuse m_prev2 as output; clone it first because we need
                    # the original m_{t-2} for the recurrence.
                    saved_m2 = m_prev2.clone(memory_format=torch.preserve_format)
                    m_new = m_prev2
                    m_new.copy_(m_prev).mul_(a1).add_(grad, alpha=b0).add_(saved_m2, alpha=a2)
                    del saved_m2
                else:
                    # Order 1: overwrite m_prev in place to avoid allocating
                    # a new tensor the size of the parameter.
                    m_new = m_prev
                    m_new.mul_(a1).add_(grad, alpha=b0)

                if adaptive:
                    state['step'] = state.get('step', 0) + 1
                    step_t = state['step']
                    v = state['v']
                    v.mul_(beta2).addcmul_(grad, grad, value=1.0 - beta2)
                    bias_correction = 1.0 - beta2 ** step_t
                    # Compute adaptive denominator in a fresh tensor; this is
                    # unavoidable for correctness because we must keep raw v.
                    denom = v.sqrt().div_(math.sqrt(bias_correction)).add_(eps)
                    p.addcdiv_(m_new, denom, value=-lr)
                else:
                    p.add_(m_new, alpha=-lr)

                # Advance history
                if order == 2:
                    state['m_prev'] = m_new
                    # m_prev2 already holds the previous m_prev via the swap
                    # ...actually no, we need to save old m_prev into m_prev2.
                    # m_new is m_prev2 buffer. We need m_prev2 = old_m_prev.
                    # But we overwrote m_prev2 with m_new. We lost old_m_prev2
                    # but we saved it as saved_m2 which we already deleted.
                    # Wait, we need m_prev2 to hold m_prev (the old m_{t-1}).
                    # We can just swap references.
                    state['m_prev2'] = m_prev

        return loss

    def load_spine_coeffs(self, spine):
        """Couple optimizer coefficients to a CordPhysics spine's IIR params.

        Reads the mean fwd_theta, fwd_b0 across chakras and uses them
        as the optimizer's theta and b0. Call after load_spine().
        """
        with torch.no_grad():
            theta = torch.sigmoid(spine.fwd_theta).mean().item() * math.pi
            b0 = torch.sigmoid(spine.fwd_b0).mean().item()
        for group in self.param_groups:
            group['theta'] = theta
            if group['b0'] is not None:
                group['b0'] = b0
        print(f"[ResonantIIR] Coupled to spine: theta={theta:.4f}, b0={b0:.4f}")
