"""smooth_cascade.py -- the axial design-law machinery for the ultimate Cassi solver.

Wave-2 probe machinery, per CassiCosmos/research/helix_solver/smooth_cascade_prereg.md.

Provides (deterministic, numpy-only, no time stepping):
  - discrete_q(omega, h): the in-band discrete wavenumber from the FV dispersion.
  - scattering_reflectivity(hc, total_ratio, m, omega): the EXACT reflectivity of
    an m-cell exponential taper across a total spacing ratio, via the transfer-matrix
    march of the discrete Helmholtz operator.
  - smooth_grid(K, z0, m): the smooth-cascade grid (rung lattice z0*phi^k sub-resolved
    by an m-cell geometric taper per rung; the rung endpoints preserved exactly).
  - per_rung_group(z, q0): the wave-1 Q2 group-velocity factor |sin q/q| per rung,
    on a subdivided grid (the cascade-preservation stat, prereg Q2).
  - WaveGrid is imported from phi_grid for the conservation + determinism gates.
"""

from __future__ import annotations

import numpy as np

from phi_grid import PHI, WaveGrid

# ---------------------------------------------------------------------------
# discrete dispersion and wavenumbers
# ---------------------------------------------------------------------------

def discrete_q(omega: float, h: float, c: float = 1.0) -> float:
    """The in-band discrete wavenumber q >= 0 from omega = c (2/h) sin(q h / 2)."""
    Omega = omega * h / c
    assert Omega <= 2.0, "frequency above the band edge (no propagating mode)"
    return 2.0 * np.arcsin(Omega / 2.0) / h


# ---------------------------------------------------------------------------
# the exact scattering reflectivity of a spacing taper
# ---------------------------------------------------------------------------

def _march_node(u_next, u_cur, h_minus, h_plus, omega, c):
    """The FV Helmholtz at node i: (A u)_i = -(omega/c)^2 u_i, giving u_{i-1}.

    With h_- = left spacing, h_+ = right spacing, M = (h_-+h_+)/2:
    u_{i-1} = h_- * [ u_i (1/h_+ + 1/h_- - (omega/c)^2 M) - u_{i+1}/h_+ ].
    """
    M = 0.5 * (h_minus + h_plus)
    om2 = (omega / c) ** 2
    return h_minus * (u_cur * (1.0 / h_plus + 1.0 / h_minus - om2 * M) - u_next / h_plus)


def scattering_reflectivity(hc: float, total_ratio: float, m: int, omega: float,
                            c: float = 1.0) -> float:
    """Exact reflectivity of an m-cell exponential taper across total_ratio.

    Grid: n_c coarse cells (hc) -> m taper cells (hc * r^j, r = total_ratio^(1/m))
          -> n_f fine cells (hf = hc * total_ratio). A unit outgoing fine mode is
    marched left across the whole grid; the resulting coarse-end state is matched
    to A e^{iq_c z} + B e^{-iq_c z} to give R = |B/A|^2. Deterministic, O(N).
    """
    r = total_ratio ** (1.0 / m) if m > 0 else total_ratio
    n_c = 24          # coarse cells
    n_f = 12          # fine cells
    # spacings along the grid
    h = []
    h += [hc] * n_c
    if m > 0:
        for j in range(m):
            h.append(hc * r ** j)
    hf = hc * total_ratio
    h += [hf] * n_f
    # node positions
    z = np.concatenate(([0.0], np.cumsum(h)))
    N = len(z)
    # fine-region outgoing mode (unit amplitude)
    qf = discrete_q(omega, hf, c)
    # state at the two rightmost nodes
    u_next = np.exp(1j * qf * (z[N - 1] - z[0]))
    u_cur = np.exp(1j * qf * (z[N - 2] - z[0]))
    # march LEFT from node N-2 down to node 1 (u_cur = value at node i+1, etc.)
    # node i uses h_- = h[i-1], h_+ = h[i]; we march decreasing i.
    for i in range(N - 2, 0, -1):
        h_minus = h[i - 1]
        h_plus = h[i]
        u_prev = _march_node(u_next, u_cur, h_minus, h_plus, omega, c)
        u_next, u_cur = u_cur, u_prev
    # after the loop u_cur = u_1, u_next = u_2 (we matched nodes 2,1)
    u1 = u_cur
    u2 = u_next
    # match to A e^{iq_c z} + B e^{-iq_c z} at nodes 1 and 2
    qc = discrete_q(omega, hc, c)
    s1 = np.exp(1j * qc * hc)       # e^{iq_c z_1}, z_1 = hc (relative phase), z_2 = 2hc
    t1 = np.exp(-1j * qc * hc)
    s2 = np.exp(1j * qc * 2 * hc)
    t2 = np.exp(-1j * qc * 2 * hc)
    # solve [s1 t1; s2 t2] [A; B] = [u1; u2]
    det = s1 * t2 - t1 * s2
    A = (u1 * t2 - t1 * u2) / det
    B = (s1 * u2 - u1 * s2) / det
    gamma = abs(B / A) ** 2
    return float(gamma)


# ---------------------------------------------------------------------------
# the smooth-cascade grid (rung lattice preserved under subdivision)
# ---------------------------------------------------------------------------

def smooth_grid(K: int, z0: float, m: int) -> np.ndarray:
    """The rung lattice z0*phi^k, sub-resolved by an m-cell geometric taper per rung.

    Within rung segment [phi^k, phi^(k+1)] the per-cell spacing ratio is
    r = phi^(1/m), so the segment's m cells run z0*phi^k * r^j. The endpoints
    land on the phi^k exactly.
    """
    if m == 0:
        return z0 * PHI ** np.arange(K, dtype=np.float64)
    cells = []
    for k in range(K - 1):
        zk = z0 * PHI ** k
        zk1 = z0 * PHI ** (k + 1)
        r = PHI ** (1.0 / m)
        for j in range(m):
            cells.append(zk * r ** j)
    cells.append(z0 * PHI ** (K - 1))
    return np.asarray(cells, dtype=np.float64)


# ---------------------------------------------------------------------------
# the cascade-preservation stat (wave-1 Q2 on a subdivided grid, prereg Q2)
# ---------------------------------------------------------------------------

def per_rung_group(z: np.ndarray, q0: float, m: int) -> list:
    """The local discrete group-velocity factor |sin q/q| at each RUNG BOUNDARY.

    q grows by the local per-cell ratio relative to the rung-0 spacing; the factor
    is evaluated at the node just at each phi^k boundary (node index k*m).
    """
    h = np.diff(z)
    h0 = h[0]
    factors = []
    positions = []
    K = 8
    for k in range(K):
        idx = k * m if m > 0 else k
        if idx >= len(z) - 1:
            break
        hk = min(h[idx], h[-1])
        qk = q0 * (hk / h0)
        if qk > np.pi:
            gf = 0.0
        else:
            gf = abs(np.sin(qk) / qk) if qk > 1e-12 else 1.0
        factors.append(gf)
        positions.append(float(PHI ** k))
    return positions, factors
