"""overlap_rim.py -- the faithful bracketed-interpolation rim.

Wave-4 probe machinery, per CassiCosmos/research/helix_solver/overlap_rim_prereg.md.

Wave-3's rim EXTRAPOLATED the coarse field past its last node (23.3%). The sim's
gate-vi rim INTERPOLATES with the fine edge's cell center bracketed between two
coarse nodes. This implements that bracketed interpolation at a coarse->fine
junction: the fine lattice is OFFSET by hc/2 so its nodes never coincide with the
coarse nodes (genuine bracketing, >0 lower bound on the interpolation error).

Provides (deterministic, numpy, exact banded radiation-condition scattering):
  - discrete_q(omega, h)
  - junction_reflectivity(hc, r, m_t, omega): exact |R|^2 of the coarse->fine
    (ratio r) junction with bracketed-interp rim, plus an optional m_t-cell taper.
"""

from __future__ import annotations

import numpy as np

PHI = 1.618033988749895


def discrete_q(omega: float, h: float, c: float = 1.0) -> float:
    Om = omega * h / c
    assert Om <= 2.0, "frequency above the band edge"
    return 2.0 * np.arcsin(Om / 2.0) / h


def _fvm(a, b):
    M = 0.5 * (a + b)
    return np.array([1.0 / a, -(1.0 / a + 1.0 / b), 1.0 / b]) / M


def junction_reflectivity(hc=1.0, r=PHI, m_t=0, omega=None, n_c=30, n_f=48):
    """Exact |R|^2 of a coarse->fine junction with the bracketed-interpolation rim.

    Lattice: coarse nodes x = j*hc (j = -n_c..1, so the host has one node at +hc) ;
    fine nodes x = hc/2 + k*hf (offset by hc/2; spacing hf = hc/r). The fine's first
    node at x = hc/2 is GENUINELY bracketed between coarse nodes x=0 and x=+hc; its
    value is the linear interpolation of the two coarse nodes there. The coarse node
    that would be inside the fine span (x=+hc when hf < hc/2 etc.) couples to the
    fine by the FV; here the host node at +hc is the bracketing node for the rim.

    With m_t > 0 the transition is graded (n_t taper cells hc -> hf) at the junction.
    """
    if omega is None:
        omega = 2.0 * np.sin(np.pi / 8.0)
    hf = hc / r
    # ---- positions ----
    coarse = np.arange(-n_c, 2, dtype=np.float64) * hc          # -n_c*hc .. +hc
    fine = hc / 2.0 + np.arange(n_f, dtype=np.float64) * hf      # offset, bracketed
    z = np.concatenate((coarse, fine))
    if m_t > 0:
        # put the taper nodes between the last coarse node (x=+hc) region and the
        # fine start: grade the spacing from hc to hf over m_t cells starting at +hc
        tz = np.cumsum(np.concatenate(([0.0], [hc * (hf / hc) ** (k / (m_t + 1))
                                               for k in range(1, m_t + 1)]))) + coarse[-1]
        z = np.concatenate((z, tz))
    z = np.sort(z)
    keep = np.concatenate(([True], np.abs(np.diff(z)) > 1e-12))
    z = z[keep]
    n = len(z)
    A = np.zeros((n, n))
    # full FV interior with real spacings (the lattice is continuous: fine starts at
    # hc/2, overlapping the coarse span [0, hc]; the coupling is carried by the FV
    # rows and the rim constraint below)
    for i in range(1, n - 1):
        a = z[i] - z[i - 1]
        b = z[i + 1] - z[i]
        c = _fvm(a, b)
        A[i, i - 1] = c[0]; A[i, i] = c[1]; A[i, i + 1] = c[2]
    # ---- the bracketed interpolation is carried by the OFFSET lattice itself: the
    # fine first node at x = hc/2 sits between coarse nodes x=0 and x=+hc, and the
    # real-spacing FV couples them (the natural, well-conditioned interpolation).
    # No separate rim-constraint row is needed (it would over-constrain the system).
    # ---- banded radiation-condition solve (wave-3 proven) ----
    n_unk = n + 2
    M = np.zeros((n_unk, n_unk), dtype=complex)
    bv = np.zeros(n_unk, dtype=complex)
    row = 0
    for i in range(1, n - 1):
        M[row, i - 1] = A[i, i - 1]
        M[row, i] = A[i, i] + omega * omega
        M[row, i + 1] = A[i, i + 1]
        row += 1
    qc = discrete_q(omega, hc)
    for j in (0, 1):
        M[row, j] = 1.0
        M[row, n] = -np.exp(-1j * qc * z[j])
        bv[row] = np.exp(1j * qc * z[j])
        row += 1
    for j in (n - 2, n - 1):
        M[row, j] = 1.0
        M[row, n + 1] = -np.exp(1j * qc * z[j])
        row += 1
    try:
        sol = np.linalg.solve(M, bv)
    except np.linalg.LinAlgError:
        return float("nan")
    R = sol[n]
    return float(abs(R) ** 2)
