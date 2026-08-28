#!/usr/bin/env python3
"""Twist-chi scratch layer: parity-odd phase-current vorticity coupling.

TS6 generation-leg candidate of `hypotheses/two-strand-five-channel-matter-
organization.md` sec 3.2 (E5).  The canonical solver is imported read-only;
this module subclasses ExpandingTwoFluid3DGPU and layers the smallest
parity-odd conversion coupling onto the returned RHS:

    J      = ey grad(ei) - ei grad(ey)        (derived R^2 grad(theta))
    g      = d_z J_y - d_y J_z                 (solver-frame curl component,
                                               see frame note below)
    conv_s = -lam (1-q) eps (1 - chi_circ g / J_scale)
           = conv + T,   T = +lam chi_circ (1-q) eps g / J_scale

Frame note: the canonical solver's wavenumber arrays are cyclically labeled
(self.kz, self.ky, self.kx = torch.meshgrid(k, k, k) assigns the axis-0
wavenumber to self.kz and the axis-2 wavenumber to self.kx).  The layer uses
the solver's _grad helpers verbatim, so the computed g is the curl component
along grid axis 0 -- in box-frame labeling -(curl J)_x -- rather than the
axial (curl J)_z of the TS6 sketch.  The term remains parity-odd (any curl
component flips under handedness reversal) and vanishes at the phi-attractor
(J = 0 pointwise), so the validation verdicts are measurements of this
component; the axial-component variant is the pending follow-up.

chi_circ = 0 returns super().rhs() verbatim: the canonical path executes with
zero extra operations (bit-for-bit no-op by construction).  The term is
parity-odd (flips under handedness reversal), vanishes at the phi-attractor
(pointwise eps = 0 => J = 0), is quadratic in the imbalance there (attractor
Jacobian unchanged), and is per-cell antisymmetric in ey/ei (exact mass
neutrality of the conv pair).

J_scale: run constant.  None => computed once on the first rhs evaluation
(which sees the t = 0 init fields) as max over the box of |g|.
Measured value on all three probe inits (N = 48): 6.75556293e-02.

Run:  python two-fluid/run_twist_chi_ramp.py   (the validation runner)
"""

import numpy as np
import torch

from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI

__all__ = ['TwistChiLayer']


class TwistChiLayer(ExpandingTwoFluid3DGPU):
    """ExpandingTwoFluid3DGPU + flagged parity-odd conversion coupling."""

    def __init__(self, *args, chi_circ=0.0, J_scale=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.chi_circ = float(chi_circ)
        self.J_scale = J_scale

    def _curlJz(self, ey_hat, ei_hat, ey, ei):
        """(curl J)_z in physical space, spectral gradients (solver _grad
        convention; the same hat-to-gradient path rhs() uses for advection).

        J = ey grad ei - ei grad ey = R^2 grad(theta), R^2 = ey^2 + ei^2.
        """
        gey = self._grad(ey_hat)
        gei = self._grad(ei_hat)
        Jx = ey * gei[0] - ei * gey[0]
        Jy = ey * gei[1] - ei * gey[1]
        return (torch.fft.ifftn(1j * self.kx * torch.fft.fftn(Jy)).real
                - torch.fft.ifftn(1j * self.ky * torch.fft.fftn(Jx)).real)

    def rhs(self, u_hat, ey_hat, ei_hat):
        out = super().rhs(u_hat, ey_hat, ei_hat)
        if self.chi_circ == 0.0:
            # canonical path, zero extra operations: bit-for-bit no-op
            return out
        rhs_u_hat, rhs_ey_hat, rhs_ei_hat = out
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        g = self._curlJz(ey_hat, ei_hat, ey, ei)
        if self.J_scale is None:
            # t = 0 run constant (first rhs call sees the init fields)
            self.J_scale = float(g.abs().max())
        _, one_minus_q = self.compute_q_field(ey, ei)  # 'five' gate, as in rhs()
        eps = ey - PHI * ei
        T = self.lam * self.chi_circ * one_minus_q * eps * g / self.J_scale
        T_hat = torch.fft.fftn(T) * self.dealias
        rhs_ey_hat = rhs_ey_hat + T_hat
        rhs_ei_hat = rhs_ei_hat - T_hat
        return rhs_u_hat, rhs_ey_hat, rhs_ei_hat


if __name__ == "__main__":
    print("TwistChiLayer: layer module only; run "
          "two-fluid/run_twist_chi_ramp.py for the validation suite.")
