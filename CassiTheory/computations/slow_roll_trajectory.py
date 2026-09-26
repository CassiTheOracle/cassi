#!/usr/bin/env python3
"""
Slow-Roll Trajectory Test for the Qi-Gate Inflation Claim (C4)
==============================================================

Runs, for the first time, the Qi-gate slow-roll ODE trajectory across the
inflationary window (cascade steps 20-60) and asks whether it reproduces the
closed-form CMB predictions of `cosmology/inflation-from-cascade.md`:

    n_s = 1 - 2*phi^-1/N_e = 0.9691   (N_e = 40, gate-corrected; 1.0 sigma from Planck)
    r   ~ phi^-12 = 0.0031            (Mapped per the Fit-Status Ledger; the doc's
                                       own §4 formulas evaluate to 0.0557, 2e-7, 0.142)

Ledger status (`parameter-inventory.md` §10, C4 rows): (1) the slow-roll ODE
trajectory of the gate across steps 20-60 has never been run; (2) the e-fold
window is flagged ("40 rungs = 19.25 e-folds by the ladder's own formula");
(3) the r exponent is Mapped - no doc formula reproduces phi^-12.

System (doc's own equations, `cosmology/inflation-from-cascade.md` §2):

    Gate openness (the inflaton):
        g(eps) = (phi^-2 + eps^2) / (phi^2 + phi^-2 + eps^2),   eps = |r - phi^-1|
    Hubble rate:
        H  proportional to  lambda * g(eps)      (H ~ lambda (1-q), doc §2)
    Single-field slow roll (standard dictionary, Liddle-Lyth / Baumann;
    the doc's closed form n_s = 1 - 2/N_eff is the quadratic-potential
    result of this same dictionary):
        V proportional to g,      d(eps)/dN = -V'/V = -g'/g
        eps_H = -d ln H/dN = (g'/g)^2
        eta_H = eps_H - (1/2) d ln eps_H / dN
        n_s   = 1 + 2 eta_H - 4 eps_H  =  1 - 2 eps_H - d ln eps_H/dN
        r     = 16 eps_H
    Inflation ends where slow roll breaks, max(eps_V, |eta_V|) = 1
    (the doc's own timeline gives "eps = eta ~ 1" at inflation end).

Step -> e-fold mapping (`inflation-from-cascade.md` §1, and the ledger flag):
    Doc convention:   N_e = ln(ell_60/ell_20)/ln phi = 60 - 20 = 40 "e-folds";
                      1 cascade step counts as 1 e-fold; the scale factor grows
                      by phi^40 over the window.
    Physical e-folds: N = ln(a_60/a_20) = 40 ln phi = 19.25  (a step is ln phi
                      e-folds; the ledger's "40 rungs = 19.25 e-folds").
    CMB scales exit at step 40 (doc §1 table) = 20 doc-e-folds / 9.625 physical
    e-folds before the end at step 60.  Both conventions are evaluated.

No parameter is fitted: the end (slow-roll break, "step ~60") and the CMB-exit
anchor (step 40) fix the trajectory; the closed-form numbers are compared to
the trajectory output, not used as targets.

Usage: python computations/slow_roll_trajectory.py
Writes the same text to computations/slow_roll_trajectory_results.txt.

Refs:
  - cosmology/inflation-from-cascade.md (C4 claim, gate, N_e, pinch at r = phi^-1)
  - computations/ns_gate_correction.py (closed n_s form; N_e = 40 convention)
  - parameter-inventory.md §10 (ledger rows for C4: Mapped flags)
"""

import numpy as np

PHI = (1.0 + np.sqrt(5.0)) / 2.0
PHI_INV = 1.0 / PHI
A = PHI ** -2                # phi^-2
B = PHI ** 2 + PHI ** -2     # phi^2 + phi^-2 = 3 exactly
D = 2.0 * (B - A)            # 2(B - A) = 2 phi^2

NS_OBS, NS_ERR = 0.9649, 0.0042          # Planck 2018 (TT,TE,EE+lowE+lensing)
R_PHI12 = PHI ** -12                     # the claimed phi^-12 = 0.0031
R_BOUND = 0.032                          # Planck 2018 (BK18) 95% CL (cosmology-from-phi.md §2.3)
R_BOUND_DOC = 0.036                      # bound as quoted in inflation-from-cascade.md §4

LN_PHI = np.log(PHI)                     # physical e-folds per cascade step
N_WINDOW_DOC = 40.0                      # doc e-folds in steps 20-60 (60 - 20)
N_WINDOW_PHYS = N_WINDOW_DOC * LN_PHI    # 19.25 physical e-folds

OUT_LINES = []


def out(s=""):
    print(s)
    OUT_LINES.append(s)


# ----------------------------------------------------------------------------
# Gate and slow-roll dictionary
# ----------------------------------------------------------------------------

def gate(eps):
    """Qi-gate openness (1-q) at distance eps = |r - phi^-1| from the pinch."""
    return (A + eps ** 2) / (B + eps ** 2)


def gp_g(eps):
    """g'/g for V = g (eps), ' = d/deps."""
    return 2.0 * eps * (B - A) / ((B + eps ** 2) * (A + eps ** 2))


def dln_gp_g(eps):
    """d/deps ln(g'/g)."""
    return 1.0 / eps - 2.0 * eps / (B + eps ** 2) - 2.0 * eps / (A + eps ** 2)


def eta_V(eps):
    """Potential slow-roll eta = V''/V for V = g."""
    g2 = 2.0 * (B - A) * (B - 3.0 * eps ** 2) / (B + eps ** 2) ** 3
    return g2 / gate(eps)


def eps_H(eps):
    """Hubble slow-roll eps_H = -d ln H/dN = (g'/g)^2 along the ODE."""
    return gp_g(eps) ** 2


def dln_epsH_dN(eps):
    """d ln eps_H / dN along the ODE (deps/dN = -g'/g)."""
    return 2.0 * dln_gp_g(eps) * (-gp_g(eps))


def eta_H(eps):
    return eps_H(eps) - 0.5 * dln_epsH_dN(eps)


def ns_of(eps):
    """n_s = 1 + 2 eta_H - 4 eps_H = 1 - 2 eps_H - d ln eps_H/dN."""
    return 1.0 + 2.0 * eta_H(eps) - 4.0 * eps_H(eps)


def r_of(eps):
    """r = 16 eps_H."""
    return 16.0 * eps_H(eps)


def d_eps_dN(eps):
    """Gate slow-roll ODE: deps/dN = -g'/g  (eps decreases toward the pinch)."""
    return -gp_g(eps)


# ----------------------------------------------------------------------------
# End of inflation: slow-roll break, max(eps_V, |eta_V|) = 1
# ----------------------------------------------------------------------------

# eta_V is decreasing in eps on [0.5, 0.8]; root where eta_V = 1
lo, hi = 0.5, 0.8
for _ in range(200):
    mid = 0.5 * (lo + hi)
    if eta_V(mid) > 1.0:
        lo = mid
    else:
        hi = mid
EPS_END = 0.5 * (lo + hi)
GATE_END = gate(EPS_END)
R_END = PHI_INV + EPS_END          # pinch-side value (Yang branch; |eps| identical on either side)

# ----------------------------------------------------------------------------
# Analytic e-fold integral (verification target for the RK4 integration)
#   dN/deps = -(B+eps^2)(A+eps^2) / (2(B-A) eps)
# ----------------------------------------------------------------------------

def dN_analytic(eps1):
    """Physical e-folds from eps1 (eps1 > EPS_END) down to EPS_END."""
    return (A * B * np.log(eps1 / EPS_END)
            + (A + B) * (eps1 ** 2 - EPS_END ** 2) / 2.0
            + (eps1 ** 4 - EPS_END ** 4) / 4.0) / D


def eps_at_dN(target):
    """Invert dN_analytic: eps whose distance from the end is `target` e-folds."""
    a, b = EPS_END, 40.0
    for _ in range(200):
        m = 0.5 * (a + b)
        if dN_analytic(m) < target:
            a = m
        else:
            b = m
    return 0.5 * (a + b)


# ----------------------------------------------------------------------------
# RK4 integration backward from the end (tau = -N: e-folds before the end)
# ----------------------------------------------------------------------------

NB_MAX = 40.0
N_STEPS = 40000
H = NB_MAX / N_STEPS
tau = np.linspace(0.0, NB_MAX, N_STEPS + 1)
eps_traj = np.empty_like(tau)
eps_traj[0] = EPS_END
for i in range(N_STEPS):
    e = eps_traj[i]
    k1 = gp_g(e)
    k2 = gp_g(e + 0.5 * H * k1)
    k3 = gp_g(e + 0.5 * H * k2)
    k4 = gp_g(e + H * k3)
    eps_traj[i + 1] = e + H * (k1 + 2.0 * k2 + 2.0 * k3 + k4) / 6.0


def eps_rk4_at_dN(target):
    """eps from the RK4 grid at `target` e-folds before the end."""
    idx = int(round(target / H))
    return eps_traj[idx]


# ============================================================================
# REPORT
# ============================================================================

out("=" * 78)
out("  SLOW-ROLL TRAJECTORY TEST: QI-GATE INFLATION (C4)")
out("=" * 78)
out()
out("Claim under test (cosmology/inflation-from-cascade.md, ledger C4):")
out("  n_s = 1 - 2*phi^-1/N_e = 0.9691  (N_e = 40; Planck 0.9649 +- 0.0042, 1.0 sigma)")
out("  r   ~ phi^-12 = 0.0031            (Mapped; the doc's own formulas fail)")
out("Gap: the gate slow-roll ODE trajectory across steps 20-60 has never been run.")
out()

# ----------------------------------------------------------------------------
out("-- SECTION 1: STEP -> E-FOLD MAPPING (from the inflation doc, stated) --")
out()
out("  Doc convention (inflation-from-cascade.md sec 1):")
out("    N_e = ln(ell_60/ell_20)/ln phi = 60 - 20 = 40 'e-folds';")
out("    1 cascade step = 1 e-fold;  scale factor grows by phi^40.")
out("  Physical e-folds (ladder's own formula, ledger flag):")
out("    1 step = ln phi e-folds = 0.4812;  window = 40 ln phi = %.2f e-folds" % N_WINDOW_PHYS)
out("  CMB scales exit at step 40 (doc table, sec 1):")
out("    doc convention:  20 e-folds before the end (step 60)")
out("    physical:        %.3f e-folds before the end" % (20.0 * LN_PHI))
out()

# ----------------------------------------------------------------------------
out("-- SECTION 2: SYSTEM AND END CONDITION --")
out()
out("  Gate (doc sec 2):  g(eps) = (phi^-2 + eps^2)/(phi^2 + phi^-2 + eps^2),")
out("                     eps = |r - phi^-1|;  H proportional to lambda*g")
out("  Slow-roll ODE:     deps/dN = -g'/g  (standard single-field dictionary;")
out("                     the doc's closed form n_s = 1 - 2/N_eff is the")
out("                     quadratic-potential result of the same dictionary)")
out("  Dictionary:        eps_H = -d ln H/dN = (g'/g)^2")
out("                     eta_H = eps_H - (1/2) d ln eps_H/dN")
out("                     n_s = 1 + 2 eta_H - 4 eps_H = 1 - 2 eps_H - d ln eps_H/dN")
out("                     r   = 16 eps_H")
out("  End of inflation:  slow-roll break max(eps_V, |eta_V|) = 1 (eta_V binds):")
out("                     eps_end = %.4f  (r = %.4f, pinch at r = %.4f)" % (EPS_END, R_END, PHI_INV))
out("                     gate at end (1-q) = %.4f (doc closure value 0.127 is" % GATE_END)
out("                     approached only asymptotically at the exact pinch)")
out("                     doc timeline check: 'eps = eta ~ 1' at inflation end")
out("                       eps_V(end) = %.3f,  eta_V(end) = %.3f" % (0.5 * eps_H(EPS_END), eta_V(EPS_END)))
out()

# ----------------------------------------------------------------------------
out("-- SECTION 3: VERIFICATION OF THE NUMERICS --")
out()

# RK4 vs analytic integral
errs = []
for target in [1.0, 2.0, 5.0, 9.625, 19.25, 20.0, 30.0, 40.0]:
    e_rk4 = eps_rk4_at_dN(target)
    e_an = eps_at_dN(target)
    errs.append(abs(e_rk4 - e_an) / e_an)
    out("  dN = %6.3f:  eps(RK4) = %.6f   eps(analytic) = %.6f   rel.err = %.2e"
        % (target, e_rk4, e_an, errs[-1]))
out("  Max relative error RK4 vs analytic integral: %.2e" % max(errs))

# eps_H from finite differences of ln H along the trajectory vs analytic form
fd_err = []
for i in range(1, N_STEPS):
    # tau = N_b = e-folds before the end, d tau/dN = -1, so
    # eps_H = -d ln H/dN = +d ln g/d tau
    e_fd = (np.log(gate(eps_traj[i + 1])) - np.log(gate(eps_traj[i - 1]))) / (2.0 * H)
    e_an = eps_H(eps_traj[i])
    fd_err.append(abs(e_fd - e_an) / e_an)
out("  eps_H finite-difference check (max rel.err over trajectory): %.2e"
    % max(fd_err))
out()

# ----------------------------------------------------------------------------
out("-- SECTION 4: TRAJECTORY ACROSS THE INFLATIONARY WINDOW (steps 20-60) --")
out()
out("  Columns: Nb = physical e-folds before the end; step = 60 - Nb/ln(phi);")
out("           dN_doc = doc-convention e-folds before the end (steps);")
out("           eps = |r - phi^-1|;  g = (1-q);  eps_H, eta_H;  n_s;  r = 16 eps_H")
out("  (slow-roll dictionary breaks down within ~2 e-folds of the end;")
out("   those rows are marked *)")
out()
out("  %6s %8s %8s %8s %8s %9s %9s %9s %10s"
    % ("Nb", "step", "dN_doc", "eps", "g", "eps_H", "eta_H", "n_s", "r"))
rows = [0.0, 0.5, 1.0, 2.0, 3.0, 5.0, 7.5, 9.625, 12.5, 15.0, 17.5, 19.25,
        20.0, 25.0, 30.0, 35.0, 40.0]
for nb in rows:
    e = eps_at_dN(nb)
    broken = nb < 2.0
    star = " *" if broken else "  "
    out("  %6.3f %8.2f %8.2f %8.4f %8.4f %9.4e %9.4f %9.4f %10.4e%s"
        % (nb, 60.0 - nb / LN_PHI, nb / LN_PHI, e, gate(e), eps_H(e), eta_H(e),
           ns_of(e), r_of(e), star))
out()

# ----------------------------------------------------------------------------
out("-- SECTION 5: THE TWO ANCHOR POINTS --")
out()

def report_anchor(label, nb):
    e = eps_at_dN(nb)
    gv = gate(e)
    eH, eTa = eps_H(e), eta_H(e)
    ns, r = ns_of(e), r_of(e)
    out("  %s (step %.1f, dN_doc = %.1f):" % (label, 60.0 - nb / LN_PHI, nb / LN_PHI))
    out("    eps = %.4f   g = (1-q) = %.4f" % (e, gv))
    out("    eps_H = %.4e   eta_H = %+.4f" % (eH, eTa))
    out("    n_s = %.4f   r = 16 eps_H = %.4f" % (ns, r))
    out("    n_s vs claimed 0.9691: %.4f (off by %.4f)" % (ns, ns - 0.9691))
    out("    n_s vs Planck 0.9649+-0.0042: %+.1f sigma" % ((ns - NS_OBS) / NS_ERR))
    out("    r vs phi^-12 = %.4f: ratio %.2f   |  vs bound r < %.3f: %s"
        % (R_PHI12, r / R_PHI12, R_BOUND, "EXCLUDED" if r > R_BOUND else "within"))
    return e, ns, r

e_doc40, ns_doc40, r_doc40 = report_anchor(
    "step 40, N_e = 40 read literally as physical e-folds", 20.0)
e_phy40, ns_phy40, r_phy40 = report_anchor(
    "step 40, doc's own step count (20 steps = 9.625 physical e-folds)", 9.625)
out()

# ----------------------------------------------------------------------------
out("-- SECTION 6: WHERE DO THE CLOSED-FORM NUMBERS LIVE ON THE TRAJECTORY? --")
out()

def eps_for_ns(target):
    a, b = 1.0, 20.0
    for _ in range(200):
        m = 0.5 * (a + b)
        if ns_of(m) < target:
            a = m
        else:
            b = m
    return 0.5 * (a + b)


def eps_for_r(target):
    a, b = 1.0, 40.0
    for _ in range(200):
        m = 0.5 * (a + b)
        if r_of(m) > target:
            a = m
        else:
            b = m
    return 0.5 * (a + b)


e_ns = eps_for_ns(0.9691)
e_r = eps_for_r(R_PHI12)
for label, e in [("n_s = 0.9691", e_ns), ("r = phi^-12", e_r)]:
    nb = dN_analytic(e)
    out("  %s occurs at eps = %.3f:" % (label, e))
    out("    %8.1f physical e-folds before the end" % nb)
    out("    %8.1f doc-e-folds (steps) before the end  -> step %.1f"
        % (nb / LN_PHI, 60.0 - nb / LN_PHI))
    out("    (window: steps 20-60; CMB exit at step 40 -> %.1f physical / 20 doc e-folds)"
        % (9.625))
    if label.startswith("n_s"):
        out("    r at that point = %.4f  (%.2f x phi^-12)" % (r_of(e), r_of(e) / R_PHI12))
    else:
        out("    n_s at that point = %.4f  (%+.1f sigma from Planck)"
            % (ns_of(e), (ns_of(e) - NS_OBS) / NS_ERR))
    out()
out("  Consequence: the closed-form pair (n_s = 0.9691, r = phi^-12) does not")
out("  coexist on the trajectory (they sit ~53 and ~135 physical e-folds before")
out("  the end, respectively) and both live far outside the 20-60 window;")
out("  neither is the trajectory's output at the CMB-exit anchor (step 40).")
out()

# ----------------------------------------------------------------------------
out("-- SECTION 7: TOTAL E-FOLDS THE ODE ACTUALLY PRODUCES --")
out()
out("  Total physical e-folds from an 'open gate' start to the slow-roll break:")
for g_target in [0.90, 0.95, 0.99]:
    eps_start = np.sqrt((g_target * B - A) / (1.0 - g_target))
    nb = dN_analytic(eps_start)
    out("    start at (1-q) = %.2f (eps = %.2f):  N_total = %.1f physical e-folds"
        % (g_target, eps_start, nb))
    out("        = %.0f doc-e-folds (steps); doc's claim: N_e = 40 (window 20-60)"
        % (nb / LN_PHI))
out()
out("  The window 20-60 spans %.2f physical e-folds (40 steps); the doc's N_e = 40" % N_WINDOW_PHYS)
out("  is the step count, and the trajectory needs a start at (1-q) ~ 0.91 to hit")
out("  40 doc-e-folds - an arbitrary 'mostly open' threshold, not a derived value.")
out()

# ----------------------------------------------------------------------------
out("-- SECTION 8: SUMMARY VERDICT --")
out()
out("  1. Mapping: the doc counts 1 cascade step as 1 e-fold (N_e = 40 over")
out("     steps 20-60); the ladder's own formula gives 40 ln(phi) = %.2f physical" % N_WINDOW_PHYS)
out("     e-folds. Both conventions are used above; the ODE is per physical e-fold.")
out()
out("  2. n_s at CMB exit (step 40): %.4f (N_e = 40 literal) / %.4f (step count)," % (ns_doc40, ns_phy40))
out("     vs claimed 0.9691 and Planck 0.9649 +- 0.0042 (%+.1f / %+.1f sigma)." % ((ns_doc40 - NS_OBS) / NS_ERR, (ns_phy40 - NS_OBS) / NS_ERR))
out("     NOT reproduced: the gate trajectory at step 40 is far more red-tilted.")
out()
out("  3. r at CMB exit (step 40): %.4f (N_e = 40 literal) / %.4f (step count)," % (r_doc40, r_phy40))
out("     vs phi^-12 = %.4f.  %s: EXCLUDED by Planck (r < %.3f)." % (R_PHI12, "Both values", R_BOUND))
out("     The trajectory does not produce phi^-12 anywhere in the window; the")
out("     doc's own §4 formulas fail as well (0.0557, 2e-7, 0.142 - ledger row).")
out("     The r = phi^-12 exponent is confirmed Mapped: no derivation produces it.")
out()
out("  4. The closed form n_s = 1 - 2 phi^-1/N_e = 0.9691 corresponds on this")
out("     trajectory to CMB exit ~53 physical e-folds before the end (before step 20),")
out("     not at step 40; r = phi^-12 would need ~135 physical e-folds (step < 0).")
out()
out("  5. Total e-folds from the open gate: ~33 (at (1-q) = 0.9) to ~3300")
out("     (at (1-q) = 0.99); N_e = 40 is a threshold choice, not a derived count.")
out()
out("  VERDICT: the gate slow-roll trajectory does NOT reproduce n_s = 0.9691 or")
out("  r = phi^-12 at the CMB-exit anchor; with the doc's own formulas the honest")
out("  step-40 values are (n_s, r) ~ (%.3f, %.3f) for N_e = 40 read literally and" % (ns_doc40, r_doc40))
out("  (%.3f, %.3f) under the doc's own step count - n_s ~ 12-36 sigma from" % (ns_phy40, r_phy40))
out("  Planck and r excluded by the current bound.  Consistent with the ledger:")
out("  C4's numbers are Mapped.")
out()
out("=" * 78)
out("  Computation complete.")
out("=" * 78)

with open("computations/slow_roll_trajectory_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(OUT_LINES) + "\n")
