"""Cassi-native optimizer: φ-damped Adam with per-chakra Qi gating.

Design principles:
  - β₁ = φ⁻¹ ≈ 0.618 (φ-damped momentum, not arbitrary 0.9)
  - β₂ = φ⁻² ≈ 0.382 (φ-damped velocity, not arbitrary 0.999)
  - Per-chakra Qi-gated learning rates: wrong chakras learn faster
  - Qi-normalized gradients: damp updates during low-surprise windows
  - Chakra Qi accumulates with φ-damped IIR (same as field Qi)
"""

import math
import torch

PHI = 1.618033988749895
PHI_INV = 0.618033988749895


class CassiOptimizer:
    """φ-damped Adam with 13 per-chakra optimizer states.

    Each chakra's embed_proj slice gets its own momentum/velocity buffers
    and its own Qi-gated learning rate. The shared byte_embed uses the
    mean Qi across all chakras.

    Parameters
    ----------
    embed_proj_params : list of 13 nn.Parameter
        Per-chakra projection matrices [128, 128] each.
    byte_embed_param : nn.Parameter
        Shared byte embedding matrix [256, 128].
    lr : float
        Base learning rate (will be Qi-modulated per chakra).
    """

    def __init__(self, embed_proj_params, byte_embed_param, lr=0.001):
        self.beta1 = PHI_INV           # φ⁻¹ ≈ 0.618 — φ-damped momentum
        self.beta2 = PHI_INV * PHI_INV # φ⁻² ≈ 0.382 — φ-damped velocity
        self.base_lr = lr
        self.eps = 1e-8

        self.embed_proj_params = list(embed_proj_params)
        self.byte_embed_param = byte_embed_param

        # Per-chakra momentum and velocity buffers
        self.m = [torch.zeros_like(p) for p in self.embed_proj_params]
        self.v = [torch.zeros_like(p) for p in self.embed_proj_params]
        self.m_be = torch.zeros_like(self.byte_embed_param)
        self.v_be = torch.zeros_like(self.byte_embed_param)

        # Per-chakra Qi accumulators (φ-damped IIR, matches field Qi dynamics)
        self.chakra_qi = torch.zeros(13, device=self.embed_proj_params[0].device)
        self.step_count = 0

    def step(self, chakra_correctness):
        """Apply φ-damped Adam update with per-chakra Qi gating.

        Parameters
        ----------
        chakra_correctness : torch.Tensor [13]
            softmax_c[target] for each chakra — how well each chakra
            predicted the target byte (1.0 = perfect, ~0.004 = random).
            Chakra Qi = 1 - correctness: wrong chakras get high Qi → learn more.
        """
        self.step_count += 1

        # ── Update per-chakra Qi accumulators (φ-damped IIR) ──
        qi_instant = 1.0 - chakra_correctness  # [13]
        qi_instant = torch.clamp(qi_instant, 0.01, 1.0)  # floor to prevent stall
        self.chakra_qi = PHI_INV * self.chakra_qi + (1.0 - PHI_INV) * qi_instant

        # Bias correction for φ-damped moments
        bc1 = 1.0 - self.beta1 ** self.step_count
        bc2 = 1.0 - self.beta2 ** self.step_count

        for c in range(13):
            p = self.embed_proj_params[c]
            if p.grad is None:
                continue

            grad = p.grad

            # ── Qi-gated learning rate ──
            # High Qi (wrong) → lr up to 2× base; low Qi (correct) → lr near base
            qi_c = self.chakra_qi[c].item()
            lr_c = self.base_lr * (1.0 + qi_c)

            # ── Qi-normalized gradient ──
            # Damp updates during low-surprise windows to prevent overfitting
            qi_norm = math.sqrt(1.0 + qi_c * qi_c)
            grad_scaled = grad / qi_norm

            # ── φ-damped Adam update ──
            self.m[c] = self.beta1 * self.m[c] + (1.0 - self.beta1) * grad_scaled
            self.v[c] = self.beta2 * self.v[c] + (1.0 - self.beta2) * (grad_scaled ** 2)

            m_hat = self.m[c] / bc1
            v_hat = self.v[c] / bc2

            p.data -= lr_c * m_hat / (torch.sqrt(v_hat) + self.eps)

        # ── byte_embed update: mean Qi across all chakras ──
        if self.byte_embed_param.grad is not None:
            mean_qi = self.chakra_qi.mean().item()
            lr_be = self.base_lr * (1.0 + mean_qi)

            qi_norm_be = math.sqrt(1.0 + mean_qi * mean_qi)
            grad_be = self.byte_embed_param.grad / qi_norm_be

            self.m_be = self.beta1 * self.m_be + (1.0 - self.beta1) * grad_be
            self.v_be = self.beta2 * self.v_be + (1.0 - self.beta2) * (grad_be ** 2)

            m_hat_be = self.m_be / bc1
            v_hat_be = self.v_be / bc2

            self.byte_embed_param.data -= lr_be * m_hat_be / (torch.sqrt(v_hat_be) + self.eps)

    def get_chakra_lr_multipliers(self):
        """Return per-chakra learning rate multipliers for monitoring."""
        return 1.0 + self.chakra_qi

    def zero_grad(self):
        for p in self.embed_proj_params:
            if p.grad is not None:
                p.grad.zero_()
        if self.byte_embed_param.grad is not None:
            self.byte_embed_param.grad.zero_()
