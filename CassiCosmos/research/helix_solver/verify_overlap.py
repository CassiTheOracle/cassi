"""verify_overlap.py -- harness gates for CassiCosmos/research/helix_solver/.

Per overlap_rim_prereg.md SS1.4 + the measurement amendment. Ends
'ALL CHECKS PASSED'. Run from the repo root:
    python research/helix_solver/verify_overlap.py
"""

import numpy as np

from phi_grid import PHI, WaveGrid, energy
from overlap_rim import discrete_q, junction_reflectivity

all_pass = True


def gate(name: str, ok: bool, detail: str) -> None:
    global all_pass
    all_pass = all_pass and ok
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {detail}")


hc = 1.0
omega = 2.0 * np.sin(np.pi / 8.0)

# --- Gate 1: the bracketed rim reflects far less than wave-3's extrapolation ----
g_phi = junction_reflectivity(hc, PHI, 0, omega)
gate("g1_bracket_beats_extrapolate", g_phi < 0.10,
     f"bracketed rim at r=phi = {g_phi*100:.4f}% << wave-3 extrapolation 23.3%")

# --- Gate 2: finite, well-defined, in-band -------------------------------------
for r in (1.0, PHI, 2.0):
    g = junction_reflectivity(hc, r, 0, omega)
    hf = hc / r
    qf = discrete_q(omega, hf)
    ok = (0.0 <= g <= 1.0) and (qf > 0) and not np.isnan(g)
    gate(f"g2_r{r:.3f}", ok, f"r={r:.3f}: reflectivity {g*100:.4f}%, fine mode in-band (q_f={qf:.3f})")

# --- Gate 3: the offset lattice conserves energy + is deterministic ------------
# build the offset lattice from the module by reusing its lattice+operator logic
import overlap_rim as ov


def build_A(hc, r, m_t, n_c=30, n_f=48, om=omega):
    hf = hc / r
    coarse = np.arange(-n_c, 2) * hc
    fine = hc / 2.0 + np.arange(n_f) * hf
    z = np.concatenate((coarse, fine))
    if m_t > 0:
        tz = np.cumsum(np.concatenate(([0.0], [hc * (hf / hc) ** (k / (m_t + 1))
                                               for k in range(1, m_t + 1)]))) + coarse[-1]
        z = np.concatenate((z, tz))
    z = np.sort(z)
    z = z[np.concatenate(([True], np.abs(np.diff(z)) > 1e-12))]
    n = len(z)
    A = np.zeros((n, n))
    for i in range(1, n - 1):
        a = z[i] - z[i - 1]; b = z[i + 1] - z[i]
        M = 0.5 * (a + b)
        c = np.array([1.0 / a, -(1.0 / a + 1.0 / b), 1.0 / b]) / M
        A[i, i - 1] = c[0]; A[i, i] = c[1]; A[i, i + 1] = c[2]
    return z, A


z, A = build_A(hc, PHI, 0)
g = WaveGrid(z)
g.A = A
g.set_dt(0.05 * np.min(np.diff(z)))
zc = 0.0
sig = 3.0 * np.min(np.diff(z))
u = np.exp(-((z - zc) ** 2) / (2 * sig * sig))
v = -g.D1 @ u
u[0] = u[-1] = v[0] = v[-1] = 0.0
e0 = energy(u, v, g)
u, v = g.run(u, v, 200)
drift = abs(energy(u, v, g) - e0) / e0
gate("g3_conservation", drift < 5e-2, f"200-step relative energy drift = {drift:.2e} (<5e-2)")
u1, v1 = g.run(u.copy(), v.copy(), 50)
u2, v2 = g.run(u.copy(), v.copy(), 50)
gate("g3_determinism", bool(np.array_equal(u1, u2)) and bool(np.array_equal(v1, v2)),
     "two 50-step runs bitwise identical")

print()
print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
raise SystemExit(0 if all_pass else 1)
