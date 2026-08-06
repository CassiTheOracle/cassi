"""Lattice-frame mass test T9: masses as lattice sub-multiples.

Run:  python experiments/rung_offset_closure/lattice_mass_test.py

The bubble lattice is the frame: a condensation at rung n sits at an
envelope node or void (`foundations/bubble-lattice-fabric.md`; probe
Panel A positions).  In rung units:

    nodes:  n = j + log_phi(k)     ->  m = m_j / k   (k = 1, 2, 3, ...)
    voids:  n = j + log_phi(k+1/2) ->  m = m_j / (k + 1/2)
        (k = 0, 1, 2, ...; equivalently m = m_j / k with k half-integer)

i.e. masses are small-integer or half-integer sub-multiples of rung
masses m_j = M_Pl / phi^j.  The position set mod 1 is

    P(kmax) = {log_phi(k) mod 1 : k = 1..kmax}
            U {log_phi(k+1/2) mod 1 : k = 0..kmax-1}

which is DENSE: with 2*kmax positions in [0,1) the mean nearest
distance is ~1/(4*kmax), so every null catalog must carry the SAME
position set.  Tests:

  1. mean s (distance to nearest lattice position) vs same-density
     null, kmax = 2..16, with the search over kmax corrected by
     Monte Carlo.
  2. per-state (j, k, m_pred) decomposition at kmax = 12—the
     mass-frame reading of each state.
  3. idealized-grid (integers + half-integers) vs lattice sharpness.
  4. node/void classification of the sharp placements (sector edges
     at voids, interior states at nodes?).

The uniform baseline is the null: with a dense ruler, any catalog
looks sharp; only a mean-s below the same-density null counts.
"""

import numpy as np
from catalog_psi_map import (MASSES, signed_delta, A0, B0, PHI, LNPHI,
                             M_PL)

EDGE = ["pi", "p", "n", "d", "e", "tau"]
INTERIOR = ["mu", "J/psi", "D", "Sigma", "Z"]


def lattice_positions(kmax):
    pos = {}
    for k in range(1, kmax + 1):
        pos[(np.log(k) / LNPHI) % 1.0] = ("node", k)
    for k in range(0, kmax):
        pos[(np.log(k + 0.5) / LNPHI) % 1.0] = ("void", k + 0.5)
    return np.array(sorted(pos)), pos


def circ_dist1(a, b):
    d = np.abs((a - b) % 1.0)
    return np.minimum(d, 1.0 - d)


def build_states(fracs):
    states = []
    for name, (m, _) in sorted(MASSES.items(),
                               key=lambda kv: np.log(M_PL / kv[1][0])):
        n = np.log(M_PL / m) / LNPHI
        frac = fracs[name] if name in fracs else n % 1.0
        states.append(dict(name=name, m=m, n=n, frac=frac,
                           m_cell=int(np.floor(n))))
    return states


def main():
    rng = np.random.default_rng(31)
    names = sorted(MASSES, key=lambda k: np.log(M_PL / MASSES[k][0]))
    base = {name: (np.log(M_PL / MASSES[name][0]) / LNPHI) % 1.0
            for name in names}
    states = build_states(base)
    fracs = np.array([s["frac"] for s in states])

    print("=" * 76)
    print("T9—lattice-frame masses: m = m_j/k (k integer or half-integer)")
    print("positions {log_phi(k), log_phi(k+1/2)} mod 1; the null must")
    print("carry the same position density (mean nearest ~ 1/(4 kmax))")
    print("=" * 76)

    # (1) kmax scan, same-density null, search-corrected
    kmaxs = range(2, 17)
    p_scan = []
    print("\n(1) kmax scan (same-density null, 4000 draws each):")
    print(f"   {'kmax':>4} {'Npos':>4} {'mean s':>8} {'null':>9} "
          f"{'p':>6}")
    for kmax in kmaxs:
        pos, _ = lattice_positions(kmax)
        s = circ_dist1(fracs[:, None], pos[None, :]).min(axis=1)
        obs = s.mean()
        null = []
        for _ in range(4000):
            f = rng.uniform(0, 1, len(fracs))
            sn = circ_dist1(f[:, None], pos[None, :]).min(axis=1)
            null.append(sn.mean())
        null = np.array(null)
        p = (null <= obs).mean()
        p_scan.append(p)
        print(f"   {kmax:>4} {len(pos):>4} {obs:>8.4f} "
              f"{null.mean():>7.4f}+/-{null.std():.4f} {p:>6.3f}")
    p_scan = np.array(p_scan)
    # search correction over the kmax scan
    best_k = kmaxs[np.argmin(p_scan)]
    null_minp = []
    for _ in range(400):
        f = rng.uniform(0, 1, len(fracs))
        ps = []
        for kmax in kmaxs:
            pos, _ = lattice_positions(kmax)
            sn = circ_dist1(f[:, None], pos[None, :]).min(axis=1)
            null = []
            for _ in range(60):
                f2 = rng.uniform(0, 1, len(fracs))
                sn2 = circ_dist1(f2[:, None], pos[None, :]).min(axis=1)
                null.append(sn2.mean())
            null = np.array(null)
            ps.append((null <= sn.mean()).mean())
        null_minp.append(np.min(ps))
    null_minp = np.array(null_minp)
    print(f"\n   best kmax = {best_k} (p = {p_scan.min():.3f}); "
          f"search-corrected over the scan: "
          f"p = {(null_minp <= p_scan.min()).mean():.3f}")

    # (2) per-state decomposition at kmax = 12
    kmax = 12
    pos, plabels = lattice_positions(kmax)
    print(f"\n(2) per-state lattice decomposition (kmax = {kmax}, "
          f"{len(pos)} positions):")
    print(f"   {'state':>10} {'frac':>6} {'pos':>6} {'type':>5} {'k':>5} "
          f"{'j':>4} {'m_j/k (GeV)':>13} {'m (GeV)':>10} {'resid':>7}")
    rows = []
    for s in states:
        d = circ_dist1(s["frac"], pos)
        i = int(np.argmin(d))
        pval = pos[i]
        typ, k = plabels[pval]
        full = np.log(k) / LNPHI          # k integer (node) or
                                          # half-integer (void): the
                                          # position IS log_phi(k) mod 1
        j = int(round(s["n"] - full))
        m_pred = M_PL / PHI ** j / k      # m = m_j / k for both types
        resid = abs(m_pred - s["m"]) / s["m"] * 100
        rows.append((s, pval, typ, k, j, m_pred, resid))
        print(f"   {s['name']:>10} {s['frac']:6.3f} {pval:6.3f} "
              f"{typ:>5} {k:>5.1f} {j:>4} {m_pred:>13.4g} "
              f"{s['m']:>10.4g} {resid:>6.1f}%")
    # how many states land within X% of their lattice mass—both the
    # observed and the null must use the SAME threshold in RUNG units
    # (a mass residual of 1% corresponds to s = log_phi(1.01) = 0.0207
    # rungs, which is the MAXIMUM s for 24 positions—so a 1% mass
    # threshold counts everything; the honest thresholds are smaller)
    s_all = circ_dist1(fracs[:, None], pos[None, :]).min(axis=1)
    print(f"\n   tail counts vs the same-density null "
          f"({len(pos)} positions, 4000 draws; thresholds in rungs):")
    for th_m in [0.005, 0.01, 0.02]:
        th_s = np.log(1 + th_m) / LNPHI
        hit = (s_all <= th_s).sum()
        nullc = []
        for _ in range(4000):
            f = rng.uniform(0, 1, len(fracs))
            sn = circ_dist1(f[:, None], pos[None, :]).min(axis=1)
            nullc.append((sn <= th_s).sum())
        nullc = np.array(nullc)
        z = (hit - nullc.mean()) / nullc.std()
        print(f"   within {100*th_m:.1f}% (s <= {th_s:.4f}): "
              f"{hit}/38 vs null {nullc.mean():.1f} +/- {nullc.std():.1f} "
              f"(z = {z:+.2f}, p = {(nullc >= hit).mean():.3f})")

    # (3) idealized grid vs lattice sharpness
    print("\n(3) idealized grid {0, 1/2} vs lattice (kmax = 12):")
    s_ideal = circ_dist1(fracs[:, None], np.array([0.0, 0.5])).min(axis=1)
    s_lat = circ_dist1(fracs[:, None], pos[None, :]).min(axis=1)
    better = (s_lat < s_ideal).sum()
    print(f"   mean s: idealized {s_ideal.mean():.4f} -> lattice "
          f"{s_lat.mean():.4f}; {better}/38 states sharper under the "
          f"lattice")

    # (4) node/void classification of sharp placements
    print("\n(4) sharp placements (lattice residual < 2%) and their type:")
    sharp = sorted([r for r in rows if r[6] < 2.0], key=lambda r: r[6])
    for s, pval, typ, k, j, m_pred, resid in sharp[:12]:
        tag = ""
        if s["name"] in EDGE:
            tag = " [edge]"
        if s["name"] in INTERIOR:
            tag = " [interior]"
        print(f"   {s['name']:>10}: {typ} k = {k:>4.1f}, j = {j:>3}, "
              f"residual {resid:5.2f}%{tag}")
    n_edge = sum(1 for r in sharp if r[0]["name"] in EDGE)
    print(f"   edges among the sharp set: {n_edge}/{sum(1 for r in sharp)}")
    print("   (descriptive: the catalog's edge/interior labels were")
    print("    defined on the idealized grid, not selected here)")

    print("\nVerdict: the lattice sub-multiple law is a mass-frame")
    print("restatement of the envelope positions; the catalog is")
    print("uniform against the same-density null, and only individual")
    print("placements carry weight.")


if __name__ == "__main__":
    main()
