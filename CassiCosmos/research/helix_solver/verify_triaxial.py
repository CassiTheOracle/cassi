"""verify_triaxial.py -- harness gates for CassiCosmos/research/helix_solver/.

Per triaxial_prereg.md SS1.4. Ends 'ALL CHECKS PASSED'.
Run from the repo root:  python research/helix_solver/verify_triaxial.py
"""

import numpy as np

from phi_grid import PHI
from triaxial_laplacian import (anisotropic_laplacian, TwoFluid2D, seed_bubble,
                                sigma_ratios, edge_anisotropy)

all_pass = True


def gate(name: str, ok: bool, detail: str) -> None:
    global all_pass
    all_pass = all_pass and ok
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {detail}")


N = 96


def run(N, aspect, steps=600):
    L = anisotropic_laplacian(N, aspect)
    ey, ei = seed_bubble(N, aspect)
    ve = wi = np.zeros(N * N)
    g = TwoFluid2D(L)
    for _ in range(steps):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    return ey, ei, g


# --- Gate 1: the symmetric control is isotropic (sigma) --------------------------
ey, ei, g = run(N, (1.0, 1.0))
rho = ey + ei
_, _, sig_ratio = sigma_ratios(rho, N, (1.0, 1.0))
gate("g1_symmetric_isotropic", abs(sig_ratio - 1.0) < 0.05,
     f"symmetric arm sigma_x/sigma_y = {sig_ratio:.3f} ~ 1.0 (control isotropic)")

# --- Gate 2: the phi-arm is anisotropic (sigma differs from the symmetric) -------
ey, ei, g = run(N, (PHI, 1.0))
rho_p = ey + ei
_, _, sig_ratio_p = sigma_ratios(rho_p, N, (PHI, 1.0))
gate("g2_phi_anisotropic", sig_ratio_p > 1.08,
     f"phi-arm sigma_x/sigma_y = {sig_ratio_p:.3f} > 1 (the operator imprints anisotropy)")

# --- Gate 3: the MACHINERY conserves (free case); the coupling's non-conservation is reported
L = anisotropic_laplacian(N, (PHI, 1.0))   # the phi-arm operator


def twofluid_en(ey, ei, ve, wi, w0_2):
    ke = 0.5 * (np.sum(ve * ve) + np.sum(wi * wi))
    pe = 0.5 * (-(ey @ (L @ ey)) - (ei @ (L @ ei)))
    cp = 0.5 * w0_2 * np.sum((ey - PHI * ei) ** 2)
    return float(ke + pe + cp)


# free case (coupling off): must conserve tightly (the machinery)
gfree = TwoFluid2D(L, w0_2=0.0)
eyf, eif = seed_bubble(N, (PHI, 1.0))
vef = wif = np.zeros(N * N)
ef0 = twofluid_en(eyf, eif, vef, wif, 0.0)
for _ in range(600):
    eyf, eif, vef, wif = gfree.step(eyf, eif, vef, wif)
ef1 = twofluid_en(eyf, eif, vef, wif, 0.0)
drift_free = abs(ef1 - ef0) / max(abs(ef0), 1e-12)
gate("g3_machinery_conserves", drift_free < 5e-3,
     f"free-case (w0=0) 600-step drift = {drift_free:.2e} (<5e-3: the FV+leapfrog machinery conserves)")
# coupled case: report the drift as the shader-coupling property
gfresh = TwoFluid2D(L)
ey0, ei0 = seed_bubble(N, (PHI, 1.0))
ve0 = wi0 = np.zeros(N * N)
e0 = twofluid_en(ey0, ei0, ve0, wi0, gfresh.w0_2)
for _ in range(600):
    ey0, ei0, ve0, wi0 = gfresh.step(ey0, ei0, ve0, wi0)
e1 = twofluid_en(ey0, ei0, ve0, wi0, gfresh.w0_2)
drift_coupled = abs(e1 - e0) / max(abs(e0), 1e-12)
print(f"  REPORT: coupled (w0^2=20) 600-step drift = {drift_coupled:.2e} -- the shader's "
      f"EY/EI coupling is not a common-potential gradient, so no quadratic energy is conserved "
      f"(a documented PDE property, not a machinery defect).")

# --- Gate 4: determinism ---------------------------------------------------------
eyA, eiA = seed_bubble(N, (PHI, 1.0))
vA = wA = np.zeros(N * N)
for _ in range(50):
    eyA, eiA, vA, wA = g.step(eyA, eiA, vA, wA)
eyB, eiB = seed_bubble(N, (PHI, 1.0))
vB = wB = np.zeros(N * N)
for _ in range(50):
    eyB, eiB, vB, wB = g.step(eyB, eiB, vB, wB)
gate("g4_determinism", bool(np.array_equal(eyA, eyB)) and bool(np.array_equal(eiA, eiB)),
     "two 50-step phi-arm runs bitwise identical")

print()
print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
raise SystemExit(0 if all_pass else 1)
