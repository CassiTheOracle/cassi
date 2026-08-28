"""Closure-phase test: does delta_n track the wake phase since the last closure?

Run:  python experiments/rung_offset_closure/closure_phase_test.py

Tests the connection proposed in `foundations/rung-offset-mechanism.md`
§5 T1(d): the fractional rung offset delta_n of an observable is the
two-fluid phase lag psi at that scale, delta_n(psi) = 0.060 - 0.204 psi
(PDE-verified, run_rung_offset_probe.py Panel B), and psi is the phase
accumulated by the wake emitted at the last closure level:

    psi = omega * (n - c_last) mod 2 pi

with closure levels C = {5, 13, 34, 89, 233, 610} (Fibonacci convergents
of 1/phi^2, wake-geometry.md sec 3b). The zero-parameter omega from the
self-similar wake (Yin wavelength ell/phi at scale ell):

    omega_0 = 2 pi * phi * ln(phi) = 4.890 rad/rung

Tests:
  A. closure-distance correlation: is delta_n (or the special-point
     residual s) correlated with d = n - c_below?  Spearman + Monte Carlo.
  B. zero-parameter phase model: residuals of the observed fractional
     positions against the predicted crossings, vs the uniform baseline
     (mean 0.25), Monte Carlo p-value.
  C. free-omega scan: best omega over [0, 2 pi], with the significance
     corrected for the search (null = random catalogs, best-omega mean
     residual).
  D. the Yukawa-ladder leptons (tau, mu, e) against closures
     {5, 13, 26, 34}—the electron sits 0.03 rungs from the 26 = 2x13
     closure half-step.

The null is the honest baseline: a uniform catalog has mean circular
residual 0.25 against any fixed prediction curve, and a free-omega search
always improves it; significance must be measured against random catalogs.
"""

import numpy as np

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)
M_PL = 1.220890e19          # GeV
V0_SQRT2 = 246.0 / 2**0.5   # GeV, the Yukawa-ladder reference

# Full PDG catalog, M_Pl mass ladder (from rung-offset-mechanism.md sec 3)
MASSES = {
    "t": 172.69, "H": 125.25, "Z": 91.1876, "W": 80.369,
    "Upsilon": 9.46030, "B_c": 6.27447, "Lambda_b": 5.6196,
    "B_s": 5.36688, "B": 5.27934, "b": 4.18, "psi(2S)": 3.68610,
    "J/psi": 3.0969, "Lambda_c": 2.28646, "D_s": 1.96835, "D": 1.86484,
    "tau": 1.77686, "Omega": 1.67245, "Xi*": 1.5318, "Sigma*": 1.3837,
    "Xi": 1.31486, "c": 1.27, "Delta": 1.232, "Sigma": 1.192642,
    "Lambda": 1.115683, "phi": 1.019461, "eta'": 0.95778, "n": 0.939565,
    "p": 0.938272, "omega": 0.78265, "rho": 0.77526, "eta": 0.547862,
    "K": 0.493677, "pi": 0.13957039, "mu": 0.1056583755, "s": 0.093,
    "d": 0.00467, "u": 0.00216, "e": 0.00051099895,
}
LEPTON_MASSES = {"tau": 1.77686, "mu": 0.1056583755, "e": 0.00051099895}

CLOSURES_FIB = np.array([5, 13, 34, 89, 233, 610], dtype=float)
CLOSURES_EXT = np.sort(np.append(CLOSURES_FIB, [26.0, 285.0]))

A0, B0 = 0.060, 0.204          # delta_n(psi) = A0 - B0 psi (probe, Panel B)
OMEGA_0 = 2 * np.pi * PHI * LNPHI   # 4.890 rad/rung, self-similar wake


def n_of(m):
    return np.log(M_PL / m) / LNPHI


def circular_dist(a, b):
    d = np.abs((a - b) % 1.0)
    return np.minimum(d, 1.0 - d)


def closure_below(n, closures):
    return closures[closures < n].max()


def predicted_frac(n, c, omega):
    """Predicted fractional position of the crossing for a state at rung n
    whose last closure sits at c, under phase lag psi = omega*(n-c) mod 2pi."""
    d = n - c
    psi = (omega * d) % (2 * np.pi)
    return (A0 - B0 * psi) % 1.0


def mean_residual(ns, cs, omegas):
    """Mean circular residual of the catalog against predicted crossings,
    minimized over the omega grid (search-aware best)."""
    best = np.inf
    for omega in omegas:
        preds = np.array([predicted_frac(n, c, omega)
                          for n, c in zip(ns, cs)])
        r = circular_dist(np.array(ns) % 1.0, preds).mean()
        best = min(best, r)
    return best


def main():
    rng = np.random.default_rng(42)
    names = sorted(MASSES, key=lambda k: n_of(MASSES[k]))
    ns = np.array([n_of(MASSES[k]) for k in names])
    fracs = ns % 1.0
    # signed offset from the nearest special point (integer or half-integer)
    s_signed = np.array([min(f - round(f), f - round(2*f)/2,
                             key=abs) for f in fracs])
    s_abs = np.abs(s_signed)

    print("=" * 72)
    print("Closure-phase test: delta_n vs wake phase since the last closure")
    print("Catalog: 38 states, n = log_phi(M_Pl/m), n in [%.2f, %.2f]"
          % (ns.min(), ns.max()))
    print("=" * 72)

    for label, closures in [("Fibonacci {5,13,34,89,233,610}",
                             CLOSURES_FIB),
                            ("extended {.., 26, 285}", CLOSURES_EXT)]:
        cs = np.array([closure_below(n, closures) for n in ns])
        ds = ns - cs
        print(f"\n--- Closure set: {label} ---")

        # A. closure-distance correlation (no phase model)
        rho_s, p_s = spearman(ds, s_signed)
        rho_a, p_a = spearman(ds, s_abs)
        print(f"A. Spearman rho(distance-from-closure, delta_n)  = "
              f"{rho_s:+.3f} (p={p_s:.3f})")
        print(f"   Spearman rho(distance-from-closure, |delta_n|) = "
              f"{rho_a:+.3f} (p={p_a:.3f})")
        print("   (null: no monotone relation; a phase-reset model would")
        print("    show |delta_n| growing with distance)")

        # B. zero-parameter phase model
        r0 = circular_dist(fracs, np.array(
            [predicted_frac(n, c, OMEGA_0) for n, c in zip(ns, cs)])).mean()
        print(f"B. zero-parameter model (omega_0 = 2 pi phi ln phi = "
              f"{OMEGA_0:.3f}): mean residual = {r0:.3f} "
              f"(uniform baseline 0.250)")
        # Monte Carlo null for the fixed-omega residual
        null = []
        for _ in range(1500):
            ns_n = rng.uniform(ns.min(), ns.max(), len(ns))
            cs_n = np.array([closure_below(n, closures) for n in ns_n])
            r = circular_dist(ns_n % 1.0, np.array(
                [predicted_frac(n, c, OMEGA_0) for n, c in zip(ns_n, cs_n)])).mean()
            null.append(r)
        null = np.array(null)
        p_b = (null <= r0).mean()
        print(f"   Monte Carlo p (1500 uniform catalogs) = {p_b:.3f} "
              f"(null mean {null.mean():.3f} +/- {null.std():.3f})")

        # C. free-omega search, significance corrected for the search
        omegas = np.arange(0, 2*np.pi, 0.002)
        best_r = mean_residual(ns, cs, omegas)
        # best omega (report)
        best_om, best_om_r = None, np.inf
        for omega in omegas:
            r = circular_dist(fracs, np.array(
                [predicted_frac(n, c, omega) for n, c in zip(ns, cs)])).mean()
            if r < best_om_r:
                best_om, best_om_r = omega, r
        null_c = []
        for _ in range(300):
            ns_n = rng.uniform(ns.min(), ns.max(), len(ns))
            cs_n = np.array([closure_below(n, closures) for n in ns_n])
            null_c.append(mean_residual(ns_n, cs_n, omegas))
        null_c = np.array(null_c)
        p_c = (null_c <= best_r).mean()
        print(f"C. free-omega search: best omega = {best_om:.3f} rad/rung, "
              f"mean residual = {best_r:.3f}")
        print(f"   null (300 catalogs, same search): mean {null_c.mean():.3f} "
              f"+/- {null_c.std():.3f}, p = {p_c:.3f}")
        print(f"   candidate omega values: 2 pi/phi^2 = {2*np.pi/PHI**2:.3f}, "
              f"2 pi ln phi = {2*np.pi*LNPHI:.3f}, 2 pi/phi = "
              f"{2*np.pi/PHI:.3f}, 2 pi phi ln phi = {OMEGA_0:.3f}")

        # per-state residuals under the best omega
        print(f"   worst states under best omega:")
        preds = np.array([predicted_frac(n, c, best_om)
                          for n, c in zip(ns, cs)])
        rs = circular_dist(fracs, preds)
        for i in np.argsort(rs)[::-1][:6]:
            print(f"     {names[i]:>10}: n = {ns[i]:7.3f}, frac = "
                  f"{fracs[i]:.3f}, residual = {rs[i]:.3f}")

    # D. Yukawa-ladder leptons
    print("\n--- D. Yukawa-ladder leptons (n = log_phi((v0/sqrt2)/m)) ---")
    closures_y = np.array([5, 13, 26, 34])
    for name, m in LEPTON_MASSES.items():
        n = np.log(V0_SQRT2 / m) / LNPHI
        c = closure_below(n, closures_y)
        d = n - c
        print(f"   {name:>3}: n = {n:.3f}, closure {c:.0f} (d = {d:.2f}), "
              f"frac = {n % 1:.3f}")
    print("   the electron sits 0.47 rungs above the 26 = 2x13 closure,")
    print("   0.03 rungs from the 26.5 half-step: with omega ~ 0.94 it")
    print("   carries psi = 0.44 rad -> delta_n = -0.030, the observed value.")


def spearman(x, y):
    rx = np.argsort(np.argsort(x))
    ry = np.argsort(np.argsort(y))
    rx = rx - rx.mean()
    ry = ry - ry.mean()
    denom = np.sqrt((rx**2).sum() * (ry**2).sum())
    rho = (rx * ry).sum() / denom if denom > 0 else 0.0
    n = len(x)
    t = rho * np.sqrt((n - 2) / max(1 - rho**2, 1e-12))
    from math import erf
    p = 2 * (1 - 0.5 * (1 + erf(abs(t) / np.sqrt(2))))
    return rho, p


if __name__ == "__main__":
    main()
