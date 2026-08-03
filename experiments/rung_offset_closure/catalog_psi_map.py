"""Apply the rung-offset mechanism to the full 38-state catalog.

Run:  python experiments/rung_offset_closure/catalog_psi_map.py

The mechanism (foundations/rung-offset-mechanism.md sec 4.2, PDE-verified
in two-fluid/run_rung_offset_probe.py Panel B):

    delta_n(psi) = 0.060 - 0.204 psi     (psi = relative wake phase, rad)

Applying it to the whole catalog: every state's signed residual delta_n
(inverts to) an implied wake phase lag psi = (0.060 - delta_n)/0.204 at
that scale. This script produces the full map and tests it for structure:

  R1. circular uniformity of psi (Rayleigh + Monte Carlo)
  R2. self-similar phase advance: psi(n) = psi_0 + omega*n mod 2 pi
      (free-omega circular-linear fit; significance against random
      catalogs doing the same search)
  R3. quantization: psi clustered at multiples of a base angle
      (free base + offset; named candidates tested individually)
  R4. the sector-edge pattern: edge states (pi, p, n, d) vs the sharp
      interior set (mu, J/psi, D, Sigma, Z) — do they separate in psi?

Uncertainties: mass errors -> delta_n errors -> psi errors; the
light-quark rows carry huge psi errors (scheme-dependent MS-bar masses),
so the map is only well-constrained for ~30 of the 38 states.
"""

import csv
import numpy as np

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)
M_PL = 1.220890e19          # GeV
A0, B0 = 0.060, 0.204       # delta_n(psi) = A0 - B0*psi

# (mass GeV, PDG uncertainty GeV)
MASSES = {
    "t": (172.69, 0.30), "H": (125.25, 0.17), "Z": (91.1876, 0.0021),
    "W": (80.369, 0.013), "Upsilon": (9.46030, 0.00026),
    "B_c": (6.27447, 0.00029), "Lambda_b": (5.6196, 0.0017),
    "B_s": (5.36688, 0.00019), "B": (5.27934, 0.00012),
    "b": (4.18, 0.03), "psi(2S)": (3.68610, 0.00013),
    "J/psi": (3.0969, 0.0001), "Lambda_c": (2.28646, 0.00014),
    "D_s": (1.96835, 0.00007), "D": (1.86484, 0.00005),
    "tau": (1.77686, 0.00012), "Omega": (1.67245, 0.00029),
    "Xi*": (1.5318, 0.0013), "Sigma*": (1.3837, 0.0016),
    "Xi": (1.31486, 0.00020), "c": (1.27, 0.02),
    "Delta": (1.232, 0.002), "Sigma": (1.192642, 0.000024),
    "Lambda": (1.115683, 0.000006), "phi": (1.019461, 0.000016),
    "eta'": (0.95778, 0.00006), "n": (0.939565421, 3.5e-8),
    "p": (0.938272089, 4.0e-8), "omega": (0.78265, 0.00012),
    "rho": (0.77526, 0.00023), "eta": (0.547862, 0.000017),
    "K": (0.493677, 0.000016), "pi": (0.13957039, 1.8e-7),
    "mu": (0.1056583755, 2.3e-9), "s": (0.093, 0.008),
    "d": (0.00467, 0.00048), "u": (0.00216, 0.00049),
    "e": (0.00051099895, 0.0),
}
EDGE = ["pi", "p", "n", "d"]          # sector-edge set (M_Pl ladder)
INTERIOR = ["mu", "J/psi", "D", "Sigma", "Z"]  # sharp interior set


def n_of(m):
    return np.log(M_PL / m) / LNPHI


def signed_delta(frac):
    """Signed distance from the nearest special point (integer or
    half-integer rung), in [-0.5, +0.5]; ties go to the integer."""
    d_int = frac - round(frac)
    d_half = frac - (np.floor(frac) + 0.5)
    return d_int if abs(d_int) <= abs(d_half) else d_half


def circ_dist(a, b):
    d = np.abs((a - b) % (2 * np.pi))
    return np.minimum(d, 2 * np.pi - d)


def best_phase_advance(psis, ns, omegas):
    """psi_i ~ psi_0 + omega*n_i mod 2pi: best omega, psi_0, residual."""
    best = (None, None, np.inf)
    for omega in omegas:
        phi = (psis - omega * ns) % (2 * np.pi)
        R = np.abs(np.exp(1j * phi).mean())
        r = 1.0 - R
        if r < best[2]:
            best = (omega, float(np.angle(np.exp(1j*phi).mean())), r)
    return best


def main():
    rng = np.random.default_rng(42)
    names = sorted(MASSES, key=lambda k: n_of(MASSES[k][0]))
    rows = []
    for name in names:
        m, dm = MASSES[name]
        n = n_of(m)
        dn_mass = (dm / m) / LNPHI          # mass-driven rung error
        frac = n % 1.0
        delta = signed_delta(frac)
        psi = (A0 - delta) / B0             # mechanism applied
        dpsi = dn_mass / B0
        special = round(frac) if abs(delta - (frac - round(frac))) <= 1e-12 \
            else np.floor(frac) + 0.5
        rows.append(dict(name=name, m=m, n=n, frac=frac, delta=delta,
                         psi=psi, dpsi=dpsi, s=abs(delta), special=special))
    ns = np.array([r["n"] for r in rows])
    psis = np.array([r["psi"] for r in rows])
    dpsis = np.array([r["dpsi"] for r in rows])

    print("=" * 78)
    print("Rung-offset mechanism applied to the full 38-state catalog")
    print("psi = (0.060 - delta_n)/0.204 for every state; dpsi from PDG mass errors")
    print("=" * 78)
    print(f"{'state':>10} {'m (GeV)':>11} {'n':>8} {'delta_n':>8} "
          f"{'psi':>7} {'dpsi':>7}  special")
    for r in rows:
        print(f"{r['name']:>10} {r['m']:11.5g} {r['n']:8.3f} "
              f"{r['delta']:+8.3f} {r['psi']:7.2f} {r['dpsi']:7.2f}  "
              f"{r['special']:.1f}")
    print(f"\npsi coverage: mean {np.mean(psis):.2f} rad, "
          f"std {np.std(psis):.2f}; states with dpsi < 0.3: "
          f"{(dpsis < 0.3).sum()}/38")

    with open("experiments/rung_offset_closure/catalog_psi_map.csv", "w",
              newline="") as f:
        w = csv.DictWriter(f, fieldnames=["name", "m", "n", "frac", "delta",
                                          "psi", "dpsi", "s", "special"])
        w.writeheader()
        for r in rows:
            w.writerow(r)

    # ---- Structure tests with the CORRECT null ----
    # The catalog's frac is ~uniform; the special points (integer and
    # half-integer rungs) fold that into a triangular delta_n window
    # [-0.25, +0.25] and hence a triangular psi window
    # [(A0-0.25)/B0, (A0+0.25)/B0] = [-0.93, +1.52].  A uniform-frac
    # catalog already gives R ~ 0.77 on psi; every p-value below is
    # measured against THAT null, not against a uniform circle.

    def psi_from_fracs(fracs):
        return np.array([(A0 - signed_delta(f % 1.0)) / B0 for f in fracs])

    # R1. circular concentration vs the triangular-window null
    R = np.abs(np.exp(1j*psis).mean())
    null_r1 = []
    for _ in range(2000):
        fracs_n = rng.uniform(0, 1, len(ns))
        psis_n = psi_from_fracs(fracs_n)
        null_r1.append(np.abs(np.exp(1j*psis_n).mean()))
    null_r1 = np.array(null_r1)
    p_r1 = (null_r1 >= R).mean()
    print(f"\nR1. circular concentration of psi: R = {R:.3f}")
    print(f"    null (uniform frac -> triangular window, 2000 catalogs): "
          f"mean {null_r1.mean():.3f} +/- {null_r1.std():.3f}, p = {p_r1:.3f}")

    # R2. self-similar phase advance psi(n) = psi_0 + omega n (mod 2 pi),
    #     search-corrected against the triangular-window null
    omegas = np.arange(0, 2*np.pi, 2*np.pi/2000)
    om_b, psi0_b, r_b = best_phase_advance(psis, ns, omegas)
    null_r2 = []
    for _ in range(400):
        ns_n = rng.uniform(ns.min(), ns.max(), len(ns))
        psis_n = psi_from_fracs(rng.uniform(0, 1, len(ns)))
        null_r2.append(best_phase_advance(psis_n, ns_n, omegas)[2])
    null_r2 = np.array(null_r2)
    p_r2 = (null_r2 <= r_b).mean()
    print(f"\nR2. self-similar phase advance psi(n) = psi_0 + omega n "
          f"(mod 2 pi):")
    print(f"    best omega = {om_b:.3f} rad/rung, psi_0 = {psi0_b:.3f} rad, "
          f"residual = {r_b:.3f}")
    print(f"    null (uniform frac, 400 catalogs, same search): "
          f"mean {null_r2.mean():.3f} +/- {null_r2.std():.3f}, p = {p_r2:.3f}")
    print("    candidates: 2 pi ln phi = 3.024, 2 pi/phi = 3.883, "
          "2 pi/phi^2 = 2.400,")
    print("    2 pi phi ln phi = 4.892, 3 pi/10 = 0.942")

    # R3. quantization at named base angles (the free-q scan is
    #     degenerate: q -> 0 fits any clustered window, so it is dropped)
    print("\nR3. quantization at named base angles (offset optimized):")
    for label, qc in [("2 pi/phi^2 (137.5 deg)", 2*np.pi/PHI**2),
                      ("3 pi/10 (54 deg)", 3*np.pi/10),
                      ("2 pi/5 (72 deg)", 2*np.pi/5),
                      ("pi/phi (111.2 deg)", np.pi/PHI),
                      ("2 pi ln phi (173.2 deg)", 2*np.pi*LNPHI),
                      ("2 pi/phi^3 (85.0 deg)", 2*np.pi/PHI**3),
                      ("2 pi/phi^4 (52.5 deg)", 2*np.pi/PHI**4)]:
        best = np.inf
        for phi0 in np.linspace(0, qc, 61, endpoint=False):
            k = np.round((psis - phi0) / qc)
            best = min(best, circ_dist(psis, phi0 + k*qc).mean())
        null = []
        for _ in range(400):
            psis_n = psi_from_fracs(rng.uniform(0, 1, len(ns)))
            b = np.inf
            for phi0 in np.linspace(0, qc, 61, endpoint=False):
                k = np.round((psis_n - phi0) / qc)
                b = min(b, circ_dist(psis_n, phi0 + k*qc).mean())
            null.append(b)
        null = np.array(null)
        print(f"    {label:>22}: residual {best:.3f}, p = {(null <= best).mean():.3f}")

    # R4. sector-edge vs interior separation in psi
    ps_e = [r["psi"] for r in rows if r["name"] in EDGE]
    ps_i = [r["psi"] for r in rows if r["name"] in INTERIOR]
    print(f"\nR4. sector-edge vs interior separation in psi:")
    print(f"    edge {EDGE}:     psi = " + ", ".join(f"{p:.2f}" for p in ps_e))
    print(f"    interior {INTERIOR}: psi = "
          + ", ".join(f"{p:.2f}" for p in ps_i))
    print("    (the doc's sharp-set selection already fixes edge->half,")
    print("     interior->integer; the question is whether psi separates)")

    # R5. the sharp set's psi band (descriptive)
    sharp = [r for r in rows if r["name"] in EDGE + INTERIOR]
    ps_s = [r["psi"] for r in sharp]
    print(f"\nR5. sharp placements ({len(sharp)} states): psi in "
          f"[{min(ps_s):.2f}, {max(ps_s):.2f}] rad")
    print(f"    coherent crossing sits at psi* = A0/B0 = {A0/B0:.3f} rad "
          f"(delta_n = 0); the band is")
    print("    the selection criterion in psi units — descriptive, not a test")

    # check: does the edge set prefer half-integers over the whole catalog?
    half_edge = sum(1 for r in rows if r["name"] in EDGE
                    and r["special"] % 1.0 > 0)
    half_all = sum(1 for r in rows if r["special"] % 1.0 > 0)
    print(f"\n    half-rung nearest-special count: edge {half_edge}/4, "
          f"catalog {half_all}/38 "
          f"(uniform expectation ~19/38)")


if __name__ == "__main__":
    main()
