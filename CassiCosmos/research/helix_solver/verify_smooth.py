"""verify_smooth.py -- harness gates for CassiCosmos/research/helix_solver/.

Per smooth_cascade_prereg.md SS1.4. Ends 'ALL CHECKS PASSED'.
Run from the repo root:  python research/helix_solver/verify_smooth.py
"""

import numpy as np

from phi_grid import PHI, WaveGrid, energy, make_uniform_grid
from smooth_cascade import (discrete_q, scattering_reflectivity, smooth_grid)

all_pass = True


def gate(name: str, ok: bool, detail: str) -> None:
    global all_pass
    all_pass = all_pass and ok
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {detail}")


K = 8
Z0 = 1.0
zc_ = 1.0  # hc for the scattering grid

# --- Gate 1: rung-lattice preservation under the m=12 taper -------------------
m = 12
z_smooth = smooth_grid(K, Z0, m)
ok = True
details = []
for k in range(K):
    target = PHI ** k
    idx = k * m
    err = abs(z_smooth[idx] - target)
    ok = ok and err < 1e-13
    details.append(abs(err))
gate("g1_rung_lattice", ok, f"max rung-endpoint deviation = {max(details):.2e} (<1e-13)")

# --- Gate 2: taper per-cell ratio = phi^(1/m) ----------------------------------
h = np.diff(z_smooth)
r_mid = h[1] / h[0]           # per-cell ratio inside a rung segment
r_end = h[m] / h[m - 1]       # across a rung boundary (also phi^(1/m))
gate("g2_taper_ratio",
     abs(r_mid - PHI ** (1 / m)) < 1e-12 and abs(r_end - PHI ** (1 / m)) < 1e-12,
     f"per-cell ratio inside = {r_mid:.6f}, across rung = {r_end:.6f} (phi^(1/12) = {PHI**(1/m):.6f})")

# --- Gate 3: scattering-machinery self-consistency + the bare single-node step -----
omega = 2.0 * np.sin(np.pi / 8.0) / zc_      # q_c h_c = pi/4 resolved mode
# (a) no defect -> machine zero (the march is exact)
g0 = scattering_reflectivity(zc_, 1.0, 0, omega)
# (b) the bare single-node phi step (interior cell junction)
gamma_bare = scattering_reflectivity(zc_, PHI, 0, omega)
# (c) a 1-cell taper is the same single node; a 2-cell taper is the anti-reflection case
g1 = scattering_reflectivity(zc_, PHI, 1, omega)
g2 = scattering_reflectivity(zc_, PHI, 2, omega)
gate("g3_no_defect", g0 < 1e-12, f"ratio-1 reflectivity = {g0:.1e} (machine zero, march exact)")
gate("g3_bare_single_node", 0.005 < gamma_bare < 0.008,
     f"bare phi single-node reflectivity = {gamma_bare*100:.4f}% (the operator's true interior value; wave-1's 23.61% was the two-medium boundary)")
gate("g3_taper_cancels", abs(g1 - gamma_bare) < 1e-9 and g2 < gamma_bare * 0.5,
     f"m=1 == single node ({g1*100:.4f}%); m=2 halves it ({g2*100:.4f}%) — graded-index cancellation begins")
# the fine-side mode is in-band (full transmission regime)
qf = discrete_q(omega, zc_ * PHI)
gate("g3_fine_band", qf / 1.0 > 0, f"fine-side mode propagates (q_f = {qf:.3f} in-band)")

# --- Gate 4: conservation + determinism on the smooth grid ----------------------
gu = WaveGrid(z_smooth)
gu.set_dt(0.05 * np.min(np.diff(z_smooth)))
zc = z_smooth[len(z_smooth) // 2]
sig = 3.0 * np.min(np.diff(z_smooth))
u = np.exp(-((z_smooth - zc) ** 2) / (2 * sig * sig))
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
