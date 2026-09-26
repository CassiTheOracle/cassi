#!/usr/bin/env python3
"""Twist-chi axial scratch layer: phase-current vorticity conversion coupling.

TS6 generation-leg candidate of `hypotheses/two-strand-five-channel-matter-
organization.md` sec 3.2 (E5), with the axial curl component.  The canonical
solver is imported read-only; this module subclasses ExpandingTwoFluid3DGPU
and layers the smallest parity-odd conversion coupling onto the returned RHS:

    J      = ey grad(ei) - ei grad(ey)        (derived R^2 grad(theta))
    g      = d_y J_z - d_z J_y                (axial component; see note)
    conv_s = -lam (1-q) eps (1 - chi_ax g / J_scale)
           = conv + T,   T = +lam chi_ax (1-q) eps g / J_scale

Component/sign note (the correction).  The canonical solver's wavenumber
arrays are cyclically labeled: self.kz, self.ky, self.kx =
torch.meshgrid(k, k, k, indexing='ij') assigns the axis-0 wavenumber to
self.kz and the axis-2 wavenumber to self.kx, so the solver's label frame
is (x, y, z) = (grid axis 2, grid axis 1, grid axis 0) and its _grad
helper returns [fx, fy, fz] = [d/d(axis 2), d/d(axis 1), d/d(axis 0)].
The TS6 helix (helix_init of run_two_strand_twist_probe) winds about the
box z axis = grid axis 2 = the solver's x direction.  The prior layer
(`scratch_twist_chi.py`) computed (curl J)_z in the solver frame, the
component along grid axis 0 -- box-frame -(curl J)_x, a transverse
component.  This layer computes the axial component, (curl J)_x in the
solver frame:

    g = d_y J_z - d_z J_y  (solver labels)
      = d_{axis 1} J_{axis 0} - d_{axis 0} J_{axis 1}
      = -(curl J)_z in box labels.

The minus sign relative to the box-frame axial component is explicit:
with this g the coupling reads conv -> -lam (1 - chi_ax g / J_scale)
(1-q) eps, i.e. chi_ax multiplies -(curl J)_{box z}; the TS6 sketch's
chi_circ (which multiplies +(curl J)_{box z}) equals -chi_ax under this
convention.  chi_ax sweeps both signs in the ramp; the convention is
recorded, not fitted.

Parity structure: g is even under the box midplane reflection z -> -z
(the pseudovector component perpendicular to the mirror plane), so the
coupled system is exactly mirror-symmetric under (chi_ax, omega0) ->
(chi_ax, -omega0): the ramp's mirror identity dTw(chi, -w0) =
-dTw(chi, +w0) is an exact-symmetry check at grid accuracy.  The
chi-flip identity dTw(-chi, +w0) = -dTw(chi, +w0) is not forced by any
symmetry; it is the empirical generation-linearity test.  The term
vanishes at the phi-attractor (eps = 0 => J = 0 pointwise), is quadratic
in the imbalance there (attractor Jacobian unchanged), and is per-cell
antisymmetric in ey/ei (exact mass neutrality of the conv pair).

chi_ax = 0 returns super().rhs() verbatim: the canonical path executes
with zero extra operations (bit-for-bit no-op by construction).

J_scale: run constant.  None => computed once on the first rhs evaluation
(which sees the t = 0 init fields) as max over the box of |g|.

Run:  python two-fluid/run_twist_chi_axial_ramp.py   (the validation runner)
"""

import numpy as np
import torch

from cassi_two_fluid_3d_gpu import ExpandingTwoFluid3DGPU, PHI

__all__ = ['TwistChiAxialLayer']


class TwistChiAxialLayer(ExpandingTwoFluid3DGPU):
    """ExpandingTwoFluid3DGPU + flagged parity-odd axial conversion coupling."""

    def __init__(self, *args, chi_ax=0.0, J_scale=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.chi_ax = float(chi_ax)
        self.J_scale = J_scale

    def _curlAxial(self, ey_hat, ei_hat, ey, ei):
        """Axial phase-current curl, (curl J)_x in the solver label frame.

        Solver labels: x = grid axis 2 (the TS6 helix axis), y = axis 1,
        z = axis 0 (the canonical k arrays are cyclically assigned).
        g = d_y J_z - d_z J_y = d_{axis 1} J_{axis 0} - d_{axis 0} J_{axis 1}
          = -(curl J)_z in box labels.  See the module docstring.

        J = ey grad ei - ei grad ey = R^2 grad(theta), R^2 = ey^2 + ei^2.
        """
        gey = self._grad(ey_hat)
        gei = self._grad(ei_hat)
        Jz = ey * gei[2] - ei * gey[2]      # J along solver z = grid axis 0
        Jy = ey * gei[1] - ei * gey[1]      # J along solver y = grid axis 1
        return (torch.fft.ifftn(1j * self.ky * torch.fft.fftn(Jz)).real
                - torch.fft.ifftn(1j * self.kz * torch.fft.fftn(Jy)).real)

    def rhs(self, u_hat, ey_hat, ei_hat):
        out = super().rhs(u_hat, ey_hat, ei_hat)
        if self.chi_ax == 0.0:
            # canonical path, zero extra operations: bit-for-bit no-op
            return out
        rhs_u_hat, rhs_ey_hat, rhs_ei_hat = out
        ey = torch.fft.ifftn(ey_hat).real
        ei = torch.fft.ifftn(ei_hat).real
        g = self._curlAxial(ey_hat, ei_hat, ey, ei)
        if self.J_scale is None:
            # t = 0 run constant (first rhs call sees the init fields)
            self.J_scale = float(g.abs().max())
        _, one_minus_q = self.compute_q_field(ey, ei)  # 'five' gate, as in rhs()
        eps = ey - PHI * ei
        T = self.lam * self.chi_ax * one_minus_q * eps * g / self.J_scale
        T_hat = torch.fft.fftn(T) * self.dealias
        rhs_ey_hat = rhs_ey_hat + T_hat
        rhs_ei_hat = rhs_ei_hat - T_hat
        return rhs_u_hat, rhs_ey_hat, rhs_ei_hat


if __name__ == "__main__":
    print("TwistChiAxialLayer: layer module only; run "
          "two-fluid/run_twist_chi_axial_ramp.py for the validation suite.")
