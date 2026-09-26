"""rim_coupling.py -- the two-medium boundary machinery for the ultimate Cassi solver.

Wave-3 probe machinery, per CassiCosmos/research/helix_solver/rim_coupling_prereg.md.

Provides (deterministic, numpy-only, exact matrix scattering, no time stepping):
  - discrete_q(omega, h): in-band discrete wavenumber (FINITE-VOLUME dispersion).
  - coupled_operator(hc, hf, coupling, m_t): the combined finite-volume operator on
    a coarse->fine grid; 'coupling' is 'naive' | 'rim' | 'taper'.
      naive : a single junction node (the wave-2 continuous-grid 0.658% reference).
      rim   : the junction flux reads a linearly-interpolated coarse value (the sim's
              gate-vi rim error, 1D).
      taper : + m_t graded intermediate nodes (the wave-2 anti-reflection transition).
  - scattering_reflectivity(op, z, hc, hf, omega): the EXACT |R|^2 via a banded
    radiation-condition solve (unit incident coarse plane wave, outgoing fine).
"""

from __future__ import annotations

import numpy as np

PHI = 1.618033988749895


def discrete_q(omega: float, h: float, c: float = 1.0) -> float:
    """In-band discrete wavenumber q >= 0 from omega = c (2/h) sin(q h / 2)."""
    Om = omega * h / c
    assert Om <= 2.0, "frequency above the band edge (no propagating mode)"
    return 2.0 * np.arcsin(Om / 2.0) / h


def _fvm(h_left, h_right):
    """FV stencil coeffs at a node with left spacing a=h_left, right b=h_right:
    (A u)_i = comb.[u_{i-1},u_i,u_{i+1}].  A = -M^-1 B^T W B, M=(a+b)/2."""
    a, b = h_left, h_right
    M = 0.5 * (a + b)
    return np.array([1.0 / a, -(1.0 / a + 1.0 / b), 1.0 / b]) / M   # [u_{i-1},u_i,u_{i+1}]


def _taper_spacings(hc, hf, m_t):
    """m_t graded intermediate spacings from hc to hf (geometric), plus the two caps."""
    if m_t == 0:
        return [hc, hf]
    r = (hf / hc) ** (1.0 / (m_t + 1))
    sp = [hc * r ** i for i in range(1, m_t + 2)]
    return sp


def coupled_operator(hc, hf, coupling="naive", m_t=0):
    """The combined FV operator on a coarse(0..C) | fine(F..) grid, boundary at a junction.

    Returns (z, A): z = node positions, A = the (N x N) operator. The junction rows
    depend on 'coupling':
      naive : a single junction node with h_-=hc, h_+=hf   (wave-2's continuous grid).
      rim   : the junction flux reads a LINEARLY INTERPOLATED coarse value at the far
              fine boundary position (the sim's gate-vi rim, 1D); one extra ghost
              coupling is resolved into the coarse boundary row.
      taper : the rim PLUS m_t graded intermediate nodes (smooth anti-reflection).
    """
    n_c = 28          # coarse cells
    n_f = 16          # fine cells
    if coupling == "taper":
        # taper: hc -> hf over m_t graded cells between the two uniform regions
        sp_mid = _taper_spacings(hc, hf, m_t)
        spacings = [hc] * n_c + sp_mid + [hf] * n_f
    else:
        spacings = [hc] * n_c + [hf] * n_f
    z = np.concatenate(([0.0], np.cumsum(spacings)))
    N = len(z)
    A = np.zeros((N, N))
    # interior nodes: standard FV (naive join is the default everywhere)
    for i in range(1, N - 1):
        a = z[i] - z[i - 1]
        b = z[i + 1] - z[i]
        c = _fvm(a, b)
        A[i, i - 1] = c[0]; A[i, i] = c[1]; A[i, i + 1] = c[2]
    if coupling == "rim":
        # The junction is between coarse node i0 = n_c (last coarse) and fine node i0+1.
        # The rim: the fine boundary node's "coarse neighbor" is the LINEAR INTERPOLATION
        # of the coarse field at the fine boundary position, not the raw coarse node.
        i0 = n_c
        # coarse-side spacings
        a_coarse = hc
        b_fine = hf
        # replace the junction flux so the fine node reads a linearly-interpolated
        # coarse value: at position x = z[i0+1] (one fine cell in), the coarse field
        # interpolated from the two coarse nodes (i0-1, i0) is
        #   u_int = (coarse slope) * (z[i0+1]-z[i0]) + u[i0]
        # Implement as an extra coupling row: the fine boundary node i0+1's stencil
        # uses (u_int - u[i0+1])/hf with u_int from u[i0-1], u[i0].
        s = (z[i0 + 1] - z[i0]) / hc      # fractional position of the fine node within the last coarse cell
        # u_int = u[i0] + s*(u[i0] - u[i0-1]);  flux = (u[i0+1] - u_int)/hf
        # FV row for the fine boundary node i0+1 (h_- = hf to u_int, h_+ = hf):
        A[i0 + 1, i0 + 1] = -(2.0 / hf) / hf     # diagonal (2/hf from -1/hf -1/hf)
        A[i0 + 1, i0] = (1.0 / hf) * (1 + s) / hf
        A[i0 + 1, i0 - 1] = -(1.0 / hf) * s / hf
        A[i0 + 1, i0 + 2] = (1.0 / hf) / hf
        # the coarse boundary node i0 reads the fine node by cell-average (restriction):
        # flux to the right = (u[i0+1] - u[i0])/hf (unchanged) - keep the default row.
    return z, A


def scattering_reflectivity(z, A, hc, hf, omega, c=1.0):
    """Exact |R|^2 for the coupled operator A under unit coarse incidence.

    Unknowns: all N node values + (R, T). Equations: FV Helmholtz (A u = -(om/c)^2 u)
    at interior nodes, plus plane-wave radiation at the two far ends.
    """
    N = len(z)
    qc = discrete_q(omega, hc, c)
    qf = discrete_q(omega, hf, c)
    # radiation at the coarse far end (nodes 0,1): u_j = e^{iq_c z_j} + R e^{-iq_c z_j}
    # radiation at the fine   far end (nodes N-2,N-1): u_j = T e^{iq_f z_j}
    om2 = (omega / c) ** 2
    n = N + 2
    M = np.zeros((n, n), dtype=complex)
    rhs = np.zeros(n, dtype=complex)
    row = 0
    # interior FV Helmholtz
    for i in range(1, N - 1):
        cst = A[i, i - 1], A[i, i], A[i, i + 1]
        M[row, i - 1] = cst[0]
        M[row, i] = cst[1] - (0 - om2)   # A u = +om2 u form -> (A - om2 I)u = 0
        M[row, i + 1] = cst[2]
        row += 1
    # coarse radiation nodes 0,1
    for j in (0, 1):
        M[row, j] = 1.0
        M[row, N] = -np.exp(-1j * qc * z[j])   # the R coefficient
        rhs[row] = np.exp(1j * qc * z[j])       # the incident
        row += 1
    # fine radiation nodes N-2, N-1
    for j in (N - 2, N - 1):
        M[row, j] = 1.0
        M[row, N + 1] = -np.exp(1j * qf * z[j])  # the T coefficient
        row += 1
    sol = np.linalg.solve(M, rhs)
    R = sol[N]
    return float(abs(R) ** 2)
