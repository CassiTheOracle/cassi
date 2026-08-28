"""verify_rim.py -- harness gates for CassiCosmos/research/helix_solver/.

Per rim_coupling_prereg.md SS1.4 + the measurement amendment (the exact matrix
scattering is the pre-registered statistic). Ends 'ALL CHECKS PASSED'.
Run from the repo root:  python research/helix_solver/verify_rim.py
"""

import numpy as np

from phi_grid import PHI, WaveGrid, energy, make_uniform_grid
from rim_coupling import (coupled_operator, scattering_reflectivity, discrete_q)

all_pass = True


def gate(name: str, ok: bool, detail: str) -> None:
    global all_pass
    all_pass = all_pass and ok
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {detail}")


hc, hf = 1.0, 1.0 / PHI
omega = 2.0 * np.sin(np.pi / 8.0)     # q_c h_c = pi/4 resolved

# --- Gate 1: no-defect (ratio 1) -> machine zero (the matrix solve is exact) -----
z, A = coupled_operator(hc, hc, "naive")
g0 = scattering_reflectivity(z, A, hc, hc, omega)
gate("g1_no_defect", g0 < 1e-12, f"ratio-1 reflectivity = {g0:.1e} (machine zero, exact solve)")

# --- Gate 2: the bare phi-junction is a documented coupling value (not wave-2's number)
z, A = coupled_operator(hc, hf, "naive")
g_naive = scattering_reflectivity(z, A, hc, hf, omega)
gate("g2_naive_pos", 0.0 < g_naive < 0.01,
     f"naive-join (matrix exact) reflectivity = {g_naive*100:.4f}% (coupling-defined; 0.06% < 1% — the rim makes it well-defined)")

# --- Gate 3: each coupling returns a finite, well-defined value (operator is nonsingular)
for name, coup in (("rim", "rim"), ("taper2", "taper"), ("taper12", "taper")):
    mt = 12 if name == "taper12" else (2 if name == "taper2" else 0)
    z, A = coupled_operator(hc, hf, coup, mt)
    g = scattering_reflectivity(z, A, hc, hf, omega)
    gate(f"g3_{name}", 0.0 <= g <= 1.0, f"coupling {coup} m_t={mt}: finite reflectivity {g*100:.4f}%")

# --- Gate 4: conservation + determinism on the coupled grid ----------------------
z, A = coupled_operator(hc, hf, "taper", 6)
gu = WaveGrid(z)
gu.A = A                                   # use the coupled operator in the stepper
gu.set_dt(0.05 * np.min(np.diff(z)))
zc = z[3]
sig = 3.0 * np.min(np.diff(z))
u = np.exp(-((z - zc) ** 2) / (2 * sig * sig))
v = -gu.D1 @ u
u[0] = u[-1] = v[0] = v[-1] = 0.0
e0 = energy(u, v, gu)
u, v = gu.run(u, v, 200)
drift = abs(energy(u, v, gu) - e0) / e0
gate("g4_conservation", drift < 5e-2, f"200-step relative energy drift = {drift:.2e} (<5e-2)")
u1, v1 = gu.run(u.copy(), v.copy(), 50)
u2, v2 = gu.run(u.copy(), v.copy(), 50)
gate("g4_determinism", bool(np.array_equal(u1, u2)) and bool(np.array_equal(v1, v2)),
     "two 50-step runs bitwise identical")

print()
print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
raise SystemExit(0 if all_pass else 1)
