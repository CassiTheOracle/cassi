"""verify_phi_grid.py -- harness gates for CassiCosmos/research/helix_solver/.

Per prereg SS1.4 + the stencil amendment (finite-volume operator). Ends
'ALL CHECKS PASSED'. Run from the repo root:
    python research/helix_solver/verify_phi_grid.py
"""

import numpy as np

from phi_grid import (PHI, WaveGrid, energy, make_phi_grid, make_uniform_grid)

K = 8
Z0 = 1.0
Z_K = PHI ** (K - 1)   # span [1.0, phi^7]
N_U = 100

all_pass = True


def gate(name: str, ok: bool, detail: str) -> None:
    global all_pass
    all_pass = all_pass and ok
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {detail}")


# --- Gate 1: phi-ratio exactness + the uniform arm spans [z0, zK] -------------
zphi = make_phi_grid(K, Z0)
ratio_err = np.max(np.abs(np.diff(zphi) - PHI * np.roll(np.diff(zphi), 1))[1:])
zu = make_uniform_grid(Z0, Z_K, N_U)
gate("g1A_phi_ratio", ratio_err < 1e-12, f"max |h_k - phi*h_{'{k-1}'}| = {ratio_err:.2e}")
gate("g1B_uniform_span",
     abs(zu[0] - Z0) < 1e-15 and abs(zu[-1] - Z_K) < 1e-15,
     f"uniform arm [{zu[0]:.6f}, {zu[-1]:.6f}] == [{Z0}, {Z_K:.4f}]")
gate("g1C_uniform_finer_than_h0", np.min(np.diff(zu)) < (PHI - 1.0),
     f"uniform dz = {np.min(np.diff(zu)):.4f} < h0 = {PHI - 1.0:.4f}")

# --- Gate 2: the finite-volume operator invariants (stencil amendment) --------
for name, z in (("phi", zphi), ("uniform", zu)):
    g = WaveGrid(z)
    # (i) symmetry under M: A^T M == M A
    symm = np.max(np.abs(g.A.T @ g.M - g.M @ g.A))
    gate(f"g2_{name}_Msym", symm < 1e-9, f"max |A^T M - M A| = {symm:.2e}")
    # (ii) M positive definite with correct volumes
    m = np.diag(g.M)
    ok_m = (m > 0).all() and abs(m[0] - 0.5 * (z[1] - z[0])) < 1e-12 \
        and abs(m[-1] - 0.5 * (z[-1] - z[-2])) < 1e-12
    gate(f"g2_{name}_Mdef", ok_m, f"M>0; ends = half-cells")
    # (iii) smooth-residual: A sin z ~= -sin z in the RESOLVED interior (h <= pi/2;
    #      sin z is aliased once the local spacing exceeds ~half a wavelength)
    s = np.sin(z)
    res = g.A @ s + s
    h = np.diff(z)
    resolved = (np.concatenate(([h[0]], h)) <= 0.5 * np.pi)[1:-1]
    maxim = np.max(np.abs(res[1:-1][np.where(resolved)[0]] if resolved.any() else res[1:-1]))
    gate(f"g2_{name}_smooth", maxim < 0.5,
         f"max |A sin z + sin z| (resolved interior) = {maxim:.3f}")

# --- Gate 3: conservation of the finite-volume energy (stencil amendment) ----
# uniform arm at dt = 0.05 min_h; phi arm at dt = 0.1 h0, IC resolved in the fine band
gu = WaveGrid(zu)
gu.set_dt(0.05 * np.min(np.diff(zu)))
zc = zu[len(zu) // 2]
sig = 1.0
u = np.exp(-((zu - zc) ** 2) / (2 * sig * sig))
v = -gu.D1 @ u
u[0] = u[-1] = v[0] = v[-1] = 0.0
assert abs(u[0]) + abs(u[-1]) < 1e-12
e0 = energy(u, v, gu)
u, v = gu.run(u, v, 200)
drift_u = abs(energy(u, v, gu) - e0) / e0
gate("g3_uniform", drift_u < 1e-3, f"200-step relative energy drift = {drift_u:.2e} (<1e-3)")
u_uni_snap, v_uni_snap = u.copy(), v.copy()   # snapshot for the g4 determinism pair

gp = WaveGrid(zphi)
gp.set_dt(0.1 * (PHI - 1.0))
sig = 3.0 * (PHI - 1.0)
zc = 1.2
u = np.exp(-((zphi - zc) ** 2) / (2 * sig * sig))
v = -gp.D1 @ u
u[0] = u[-1] = v[0] = v[-1] = 0.0
e0 = energy(u, v, gp)
u, v = gp.run(u, v, 200)
drift_p = abs(energy(u, v, gp) - e0) / e0
gate("g3_phi", drift_p < 5e-2, f"200-step relative energy drift = {drift_p:.2e} (<5e-2)")

# --- Gate 4: determinism ------------------------------------------------------
g4u1, g4v1 = gu.run(u_uni_snap.copy(), v_uni_snap.copy(), 50)
g4u2, g4v2 = gu.run(u_uni_snap.copy(), v_uni_snap.copy(), 50)
gate("g4_determinism", bool(np.array_equal(g4u1, g4u2)) and bool(np.array_equal(g4v1, g4v2)),
     "two 50-step runs bitwise identical")

print()
print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
raise SystemExit(0 if all_pass else 1)
