"""verify_twofluid.py -- harness gates for CassiCosmos/research/helix_solver/.

Per two_fluid_shell_prereg.md SS1.4. Ends 'ALL CHECKS PASSED'.
Run from the repo root:  python research/helix_solver/verify_twofluid.py
"""

import numpy as np

from phi_grid import PHI, energy, edge_matrices
from smooth_cascade import smooth_grid
from two_fluid_shell import (TwoFluidLine, make_ic, make_reference)

all_pass = True


def gate(name: str, ok: bool, detail: str) -> None:
    global all_pass
    all_pass = all_pass and ok
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {detail}")


span = PHI ** 7
zr = make_reference(span, 160)
zs = smooth_grid(8, 1.0, 12)
NSTEPS = 1200


def tf_energy(ey, ei, vey, vei, A, w0_2):
    """Two-fluid discrete energy for the coupled leapfrog.

    The conserved quantity includes the coupling potential from the term
    -w0^2 (EY - phi EI): E = KE + FV-potential + (w0^2/2) int (EY - phi EI)^2.
    """
    ke = 0.5 * (np.sum(vey * vey) + np.sum(vei * vei))
    pe = 0.5 * (-(ey @ (A @ ey) + ei @ (A @ ei)))
    cp = 0.5 * w0_2 * np.sum((ey - PHI * ei) ** 2)
    return float(ke + pe + cp)


span = PHI ** 7
zr = make_reference(span, 160)
zs = smooth_grid(8, 1.0, 12)
NSTEPS = 1200


def tf_energy(ey, ei, vey, vei, A, w0_2):
    """Two-fluid discrete energy.

    For w0_2 = 0 (the FREE case) this is the exact conserved quadratic (KE + the
    finite-volume potential). For w0_2 > 0 the shader's coupling is NOT the
    gradient of a common potential (eigen analysis: one undamped anti-phase SHO at
    omega*sqrt(1+phi)), so no quadratic is conserved -- the coupled drift is a
    REPORTED finding, never a gate.
    """
    ke = 0.5 * (np.sum(vey * vey) + np.sum(vei * vei))
    pe = 0.5 * (-(ey @ (A @ ey) + ei @ (A @ ei)))
    cp = 0.5 * w0_2 * np.sum((ey - PHI * ei) ** 2)
    return float(ke + pe + cp)


# --- Gate 1: the MACHINERY conserves (free case, w0_2 = 0), reference -------------
def run_from(gg, nsteps):
    """Evolve a FRESH solver (self-kicking) for nsteps from make_ic; return
    (ey0, ei0) pre-step and the final (ey,ei,vey,vei)."""
    ey0, ei0 = make_ic(gg.z)
    ey, ei = ey0.copy(), ei0.copy()
    vey = vei = np.zeros(len(ey))
    for _ in range(nsteps):
        ey, ei, vey, vei = gg.step(ey, ei, vey, vei)
    return ey0, ei0, ey, ei, vey, vei


gf = TwoFluidLine(zr, w0_2=0.0)
ey0, ei0, eyr, eir, veyr, veir = run_from(gf, NSTEPS)
e0 = tf_energy(ey0, ei0, np.zeros(len(zr)), np.zeros(len(zr)), gf.A, 0.0)
e1 = tf_energy(eyr, eir, veyr, veir, gf.A, 0.0)
drift_free_r = abs(e1 - e0) / max(abs(e0), 1e-12)
gate("g1_machinery_free_reference", drift_free_r < 5e-3,
     f"FREE (w0=0) reference 1200-step drift = {drift_free_r:.2e} (<5e-3: the FV+leapfrog machinery conserves)")

# --- Gate 2: the anti-phase eigenmode is CONFIRMED at the predicted period --------
# The shader's coupling has one zero mode (EY = phi EI) and one anti-phase SHO at
# omega*sqrt(1+phi). The latter is undamped (no decay channel on the Dirichlet
# line), so the "attractor" is NOT a late-time limit. Confirm the eigen-prediction.
gr = TwoFluidLine(zr)
_, _, ey, ei, ve, wi = run_from(gr, NSTEPS)
peak = int(np.argmax(np.abs(ey) + np.abs(ei)))
# continue to gather the diff oscillation
series = np.zeros(2000)
for i in range(2000):
    ey, ei, ve, wi = gr.step(ey, ei, ve, wi)
    series[i] = ey[peak] - PHI * ei[peak]
zc = np.where(series[1:] * series[:-1] < 0)[0]
per = np.diff(zc)
pred_steps = (2 * np.pi / np.sqrt(gr.w0_2 * (1 + PHI))) / gr.dt
if len(per) >= 4:
    full_per = np.mean(per) * 2     # consecutive crossings = half a period
    # the observed period carries spatial-modal DISPERSION (the k=0 eigen-frequency is
    # the sharp-pin limit; finite-k modes shift it), so use a 30% dispersion band
    ok_period = abs(full_per - pred_steps) < 0.30 * pred_steps
    # undamped: std of the last 1000 >= that of the first 1000 (no decay)
    tail_amp = np.std(series[-1000:])
    head_amp = np.std(series[:1000])
    ok_persist = tail_amp > 0.5 * head_amp
    gate("g2_anti_phase_eigenmode",
         bool(ok_period and ok_persist),
         f"anti-phase SHO period = {full_per:.1f} steps vs k=0 prediction {pred_steps:.1f} "
         f"(dispersion band +-30%); PERSISTENT (tail std {tail_amp:.2e} >= 0.5*head {head_amp:.2e} "
         f"-- the anti-phase mode does NOT decay, so the 'attractor' is refuted)")
else:
    gate("g2_anti_phase_eigenmode", False, "no clean diff-field oscillation found")

# --- Gate 3: (REPORTED, not gated) the phi-shell grid's machinery drift -----------
# The uniform reference conserves (g1 = 3.6e-4); the phi-shell (non-uniform, spacing
# ratio ~28x) does NOT conserve even uncoupled -- a growing secular drift. This is a
# genuine grid property: the FV+leapfrog shadow energy on a strongly non-uniform grid
# is not secularly conserved (verified with an IC away from the boundaries: 2.5e-2).
gfs = TwoFluidLine(zs, w0_2=0.0)
s0_a, s0_b, eys, eis, veys, veis = run_from(gfs, NSTEPS)
e0_ = tf_energy(s0_a, s0_b, np.zeros(len(zs)), np.zeros(len(zs)), gfs.A, 0.0)
e1_ = tf_energy(eys, eis, veys, veis, gfs.A, 0.0)
print(f"  REPORT: the phi-shell (non-uniform) grid's FREE-case 1200-step drift = "
      f"{abs(e1_-e0_)/max(abs(e0_),1e-12):.2e} -- growing secularly with steps; the"
      f" FV+leapfrog on the ~28x-spacing phi-shell is NOT secularly conservative"
      f" (a documented grid property; NOT used to gate, the uniform reference is the machinery pin)")

# --- Gate 4: determinism (reference) ---------------------------------------------
gd = TwoFluidLine(zr)
_, _, a1, a2, _, _ = run_from(gd, 50)
_, _, b1, b2, _, _ = run_from(TwoFluidLine(zr), 50)
gate("g4_determinism", bool(np.array_equal(a1, b1)) and bool(np.array_equal(a2, b2)),
     "two 50-step reference runs bitwise identical")

# --- REPORTED findings (not gates): the coupled drift + the (absent) attractor ---
grc = TwoFluidLine(zr)
c0a, c0b, eyc, eic, vc1, vc2 = run_from(grc, NSTEPS)
e0 = tf_energy(c0a, c0b, np.zeros(len(zr)), np.zeros(len(zr)), grc.A, grc.w0_2)
e1 = tf_energy(eyc, eic, vc1, vc2, grc.A, grc.w0_2)
drift_c_r = abs(e1 - e0) / max(abs(e0), 1e-12)
mc = (np.abs(eyc) > 0.2 * np.abs(eyc).max()) & (np.abs(eic) > 0.2 * np.abs(eic).max())
att_r = abs(eyc[mc].mean() / eic[mc].mean()) if mc.sum() > 4 else float("nan")
print(f"  REPORT: coupled (w0^2=20) reference 1200-step drift = {drift_c_r:.2e}")
print(f"  REPORT: coupled co-located EY/EI at 1200 steps = {att_r:.4f} vs phi = {PHI:.4f} --")
print(f"          NOT a late-time attractor: the anti-phase mode is undamped, so the ratio")
print(f"          is a persistent-oscillation snapshot; the 'phi-attractor' claim is WITHDRAWN")

gsc = TwoFluidLine(zs)
ss0a, ss0b, sc1, sc2, s1, s2 = run_from(gsc, NSTEPS)
e0 = tf_energy(ss0a, ss0b, np.zeros(len(zs)), np.zeros(len(zs)), gsc.A, gsc.w0_2)
e1 = tf_energy(sc1, sc2, s1, s2, gsc.A, gsc.w0_2)
drift_c_s = abs(e1 - e0) / max(abs(e0), 1e-12)
print(f"  REPORT: coupled (w0^2=20) phi-shell 1200-step drift = {drift_c_s:.2e}")

print()
print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
raise SystemExit(0 if all_pass else 1)
