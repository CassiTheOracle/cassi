"""ControllerModulation — controller-driven modulation, normalization, and breath coupling.

Owns:
- field scaling parameter (field_scale) for per-chakra complex RMSNorm
- optional GlialHomeostasis submodule
- structural_self_reg: phi-scaled Qi self-regulation

Applies alpha/gamma/rho/perturb/m_self transforms from the SelfAwarenessController.

This is the exact computation from QiField._field_step_transform (lines 642-692),
minus the prediction-feedback step (alpha * P_re/alpha * P_im) which belongs to
PredictionOperator in the decomposed architecture.

No imports from cassi.qi_field.
"""

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F

from cassi._chakra_utils import PHI, PHI_INV, phi_chakra_widths
from cassi.glial_homeostasis import GlialHomeostasis
from cassi.self_awareness_controller import CtrlOutputs


class ControllerModulation(nn.Module):
    """Controller-driven modulation: structural coupling, glial homeostasis,
    breath rotation, and per-chakra complex RMSNorm.

    Args:
        d: field dimension.
        C: number of chakras (default 13).
        has_glial: whether to include the GlialHomeostasis submodule. When
            True, the glial energy contraction is applied in forward.
    """

    def __init__(self, d: int, C: int = 13, has_glial: bool = False, glial_gain: float = 0.05):
        super().__init__()
        self.d = d
        self.C = C
        self.chakra_widths = phi_chakra_widths(d, C)
        assert sum(self.chakra_widths) == d, (
            f"chakra widths sum to {sum(self.chakra_widths)}, expected {d}"
        )

        # Per-chakra RMS scaling parameter (same as QiField.field_scale).
        self.field_scale = nn.Parameter(torch.tensor(1.0))

        # Optional glial homeostasis submodule.
        self.has_glial = has_glial
        if has_glial:
            self.glial = GlialHomeostasis(target_energy=PHI ** 2, gain=glial_gain)

    # ── Static helpers ──

    @staticmethod
    def _complex_norm2(
        a_real: torch.Tensor, a_imag: torch.Tensor
    ) -> torch.Tensor:
        """Squared magnitude of a complex tensor.

        Args:
            a_real, a_imag: tensors of the same shape.

        Returns:
            Element-wise squared magnitude: a_real^2 + a_imag^2.
        """
        return a_real ** 2 + a_imag ** 2

    @staticmethod
    def _rotate_complex(
        real: torch.Tensor,
        imag: torch.Tensor,
        angle: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Rotate a complex number (real + i*imag) by *angle* radians.

        Follows the standard rotation formula:
            out_real = real * cos(angle) - imag * sin(angle)
            out_imag = real * sin(angle) + imag * cos(angle)

        Args:
            real: [*] real component.
            imag: [*] imaginary component.
            angle: [*] broadcastable to real/imag.

        Returns:
            (rotated_real, rotated_imag) same shape as input.
        """
        c = torch.cos(angle)
        s = torch.sin(angle)
        return real * c - imag * s, real * s + imag * c

    # ── Per-chakra complex RMSNorm ──

    def _complex_rmsnorm(
        self,
        psi_real: torch.Tensor,
        psi_imag: torch.Tensor,
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """Per-chakra RMS normalization on a complex field.

        Each chakra band is normalized independently by its own RMS, then
        scaled by the global ``field_scale`` parameter.  This is equivalent
        to QiField._complex_rmsnorm.

        Args:
            psi_real, psi_imag: [B, N, d] wavefunction components.

        Returns:
            (psi_real, psi_imag) with per-chakra RMS set to field_scale.
        """
        mag2 = self._complex_norm2(psi_real, psi_imag)
        scale = torch.zeros_like(mag2)
        off = 0
        for c in range(self.C):
            dc = self.chakra_widths[c]
            band = mag2[:, :, off:off + dc]
            mean_band = band.mean(dim=-1, keepdim=True).clamp_min(1e-12)
            scale[:, :, off:off + dc] = 1.0 / torch.sqrt(mean_band)
            off += dc
        scale = scale * self.field_scale
        return psi_real * scale, psi_imag * scale

    # ── Structural self-regulation ──

    def structural_self_reg(
        self,
        Q_mean: torch.Tensor,
        m_self: torch.Tensor,
        breath_yin: torch.Tensor,
    ) -> torch.Tensor:
        r"""$\varphi$-damped self-regulation factor from Qi and breath.

        Same computation as QiField.structural_self_reg.  Maps Q relative to
        $\varphi^{-1}$ into a [calm, arousal] product that stays near 1 when
        Qi is balanced, rises with deficit (arousal), and falls with excess
        (calm).  Breath modulates the factor through *yin*.

        Args:
            Q_mean: scalar mean Qi density.
            m_self: [B] self-regulation actuator from the controller.
            breath_yin: [B] or scalar yin component of the breath carrier.

        Returns:
            Scalar self-regulation factor in [$\varphi^{-2}$, 3.0].
        """
        q_norm = Q_mean / PHI_INV
        excess = F.relu(q_norm - PHI_INV)
        calm = PHI_INV / (PHI_INV + excess)
        deficit = F.relu(PHI_INV - q_norm)
        arousal = (1.0 + 2.0 * deficit / PHI_INV).clamp(1.0, 3.0)
        self_reg = calm * arousal

        calm_breath = 1.0 + 0.15 * (breath_yin - PHI_INV)
        self_reg = (self_reg * calm_breath).clamp(PHI_INV ** 2, 3.0)

        m = m_self.mean() if m_self.numel() > 1 else m_self
        return self_reg * m.clamp(0.5, 2.0)

    # ── Forward ──

    def forward(
        self,
        psi_real: torch.Tensor,
        psi_imag: torch.Tensor,
        Q_field: torch.Tensor,
        P_re: torch.Tensor,
        P_im: torch.Tensor,
        ctrl: Optional[CtrlOutputs] = None,
        breath: Optional[Dict[str, torch.Tensor]] = None,
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """Apply controller-driven modulation, normalization, and breath coupling.

        The pipeline is:
            1. Clamp controller actuators (alpha, gamma, rho, m_self).
            2. Compute structural self-regulation from Q_mean and breath.
            3. Prediction feedback: ``psi += alpha * P``.
            4. Yin--Yang Lie-bracket rotation (``rho``).
            5. Glial energy contraction (if ``has_glial``).
            6. Breath quadrature rotation.
            7. Per-chakra complex RMSNorm.

        Args:
            psi_real: [B, N, d] real part of the field wavefunction.
            psi_imag: [B, N, d] imaginary part of the field wavefunction.
            Q_field: [B, N, d] Qi density (pass-through, used for diagnostics).
            P_re, P_im: [B, N, d] prediction — added to ψ with alpha modulation.
            ctrl: Controller outputs from ``SelfAwarenessController``.
                When ``None``, all actuators default to 1.0 (no modulation).
            breath: Dict with keys ``'yang'``, ``'yin'``.  When ``None``,
                breath modulation is disabled (zeros).

        Returns:
            psi_real, psi_imag: [B, N, d] modulated field.
            Q_field: [B, N, d] unchanged Qi density (pass-through).
            q_mean: scalar mean Qi (for the parent's diagnostic EMAs).
            diag: dict with diagnostics keys.
        """
        B = psi_real.shape[0]
        device = psi_real.device

        # ── Expand breath tensors ──
        if breath is not None:
            yang = breath['yang'].expand(B, 1, 1)
            yin = breath['yin'].expand(B, 1, 1)
        else:
            yang = torch.ones(B, 1, 1, device=device)
            yin = torch.ones(B, 1, 1, device=device)

        # ── Clamp controller actuators ──
        if ctrl is not None:
            alpha_ctrl = ctrl.alpha.view(B, 1, 1).clamp(0.5, 2.0)
            gamma_ctrl = ctrl.gamma.view(B, 1, 1).clamp(0.5, 2.0)
            rho_ctrl = ctrl.rho.view(B, 1, 1).clamp(0.5, 2.0)
            m_self = ctrl.m_self.clamp(0.5, 2.0)
        else:
            alpha_ctrl = gamma_ctrl = rho_ctrl = torch.ones(B, 1, 1, device=device)
            m_self = torch.ones(B, device=device)

        # ── Qi diagnostics ──
        q_mean = Q_field.mean()
        self_reg_factor = self.structural_self_reg(q_mean, m_self, breath_yin=yin)

        # ── Prediction feedback (alpha-modulated) ──
        alpha_breath = 1.0 + 0.5 * yang
        alpha = PHI_INV * alpha_breath * alpha_ctrl * self_reg_factor
        psi_real = psi_real + alpha * P_re
        psi_imag = psi_imag + alpha * P_im

        # ── Yin--Yang structural coupling (Lie-bracket rotation) ──
        rho = (PHI_INV * rho_ctrl * self_reg_factor).clamp(max=0.90)
        psi_real_new = psi_real - rho * psi_imag
        psi_imag_new = psi_imag + rho * psi_real
        psi_real, psi_imag = psi_real_new, psi_imag_new

        # ── Glial homeostasis (optional) ──
        if self.has_glial:
            gain = self.glial.gain * gamma_ctrl.clamp(0.5, 2.0)
            energy = self._complex_norm2(psi_real, psi_imag).mean(dim=-1, keepdim=True)
            excess = F.relu(energy - self.glial.target_energy)
            factor = (1.0 - gain * excess).clamp(0.0, 1.0)
            psi_real = psi_real * factor
            psi_imag = psi_imag * factor

        # ── Breath quadrature rotation ──
        phase = 0.1 * (yin - PHI_INV)
        psi_real, psi_imag = self._rotate_complex(psi_real, psi_imag, phase)

        # ── Per-chakra complex RMSNorm ──
        psi_real, psi_imag = self._complex_rmsnorm(psi_real, psi_imag)

        # ── Diagnostics ──
        diag: Dict[str, torch.Tensor] = {
            'q_mean': q_mean.detach(),
            'self_reg_factor': self_reg_factor.detach(),
        }
        if ctrl is not None:
            diag['alpha'] = ctrl.alpha.detach()
            diag['gamma'] = ctrl.gamma.detach()
            diag['rho'] = ctrl.rho.detach()
            diag['m_self'] = ctrl.m_self.detach()

        return psi_real, psi_imag, Q_field, q_mean, diag

