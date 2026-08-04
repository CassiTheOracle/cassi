"""Cumulative phase test T7: is the rung-offset field a multi-rung sum?

Run:  python experiments/rung_offset_closure/cumulative_phase_test.py

Panel D (`two-fluid/run_rung_offset_probe_panel_d.py`) verified the
physical premise: the crossing responds to the TOTAL phasor sum of
wakes from every rung (up AND down) with the framework amplitudes, PDE
= analytic to 1e-3 rungs.  The open question is whether the catalog's
offsets actually carry that cumulative structure.  Two tests:

  V. Variogram: if psi accumulates cumulatively in rung space, the
     circular distance between states' phases grows with their rung
     separation; if each rung's phase is independent, it is flat.
     Null: same rung positions, shuffled fractional offsets.

  M. Self-consistent mean field: the emission phase of the bubble at
     integer rung m responds to the emission of every other rung,

        psi_m = arg sum_{m' != m} D_{m'} phi^-|m-m'| e^{i(psi_{m'} + w0 (m'-m))}

     with D_m = catalog state count at rung m (the integer part of the
     mass positions; the fractional offsets are the prediction target,
     so the two data slices are independent) and w0 = 2 pi phi ln phi
     the framework's self-similar phase advance.  Cell phase:
     psi_cell(m) = psi_{m+1} - psi_m, compared against the catalog's
     implied psi via circular distance.  Null: shuffled offsets.

Variants: w0 = 0 (no propagation phase); one-sided kernel (wakes from
below only); log-compressed sources log(1 + D_m).
"""

import numpy as np
from catalog_psi_map import (MASSES, signed_delta, A0, B0, PHI, LNPHI,
                             M_PL)

OMEGA_0 = 2 * np.pi * PHI * LNPHI        # 4.89 rad/rung


def circ_dist(a, b):
    d = np.abs((a - b) % (2 * np.pi))
    return np.minimum(d, 2 * np.pi - d)


def build_states(fracs):
    """States from catalog masses, with given fractional offsets."""
    states = []
    for name, (m, _) in sorted(MASSES.items(),
                               key=lambda kv: np.log(M_PL / kv[1][0])):
        n = np.log(M_PL / m) / LNPHI
        delta = signed_delta(fracs[name] if name in fracs else n % 1.0)
        states.append(dict(name=name, n=n, m_cell=int(np.floor(n)),
                           psi=(A0 - delta) / B0, delta=delta))
    return states


def variogram(states):
    """Spearman rho between rung separation and circular psi distance."""
    ds, cs = [], []
    for i in range(len(states)):
        for j in range(i + 1, len(states)):
            ds.append(states[j]["n"] - states[i]["n"])
            cs.append(circ_dist(states[i]["psi"], states[j]["psi"]))
    ds, cs = np.array(ds), np.array(cs)
    rx = np.argsort(np.argsort(ds)) - (len(ds) - 1) / 2
    ry = np.argsort(np.argsort(cs)) - (len(cs) - 1) / 2
    rho = (rx * ry).sum() / np.sqrt((rx**2).sum() * (ry**2).sum())
    return rho, ds, cs


def mean_field(states, n_iter=120, omega=OMEGA_0, one_sided=False,
               log_sources=False):
    """Self-consistent emission phases on integer rungs 80..109."""
    rungs = np.arange(80, 110)
    D = np.array([sum(1 for s in states if s["m_cell"] == m)
                  for m in rungs], dtype=float)
    if log_sources:
        D = np.log1p(D)
    psi = np.zeros_like(rungs)
    for _ in range(n_iter):
        psi_new = np.zeros_like(rungs)
        for k, m in enumerate(rungs):
            d = rungs - m
            mask = d != 0
            if one_sided:
                mask &= d > 0
            if not mask.any():
                continue
            A = D[mask] * PHI ** (-np.abs(d[mask]))
            ph = psi[mask] + omega * d[mask]
            psi_new[k] = np.angle((A * np.exp(1j * ph)).sum())
        drift = np.max(np.abs(psi_new - psi))
        psi = psi_new
    # cell phase: relative emission phase of the two bounding bubbles
    cell = {}
    for k, m in enumerate(rungs[:-1]):
        dphi = ((psi[k + 1] - psi[k] + np.pi) % (2 * np.pi)) - np.pi
        cell[m] = dphi
    return cell, drift


def main():
    rng = np.random.default_rng(11)
    names = sorted(MASSES, key=lambda k: np.log(M_PL / MASSES[k][0]))
    base = {name: (np.log(M_PL / MASSES[name][0]) / LNPHI) % 1.0
            for name in names}
    states = build_states(base)
    psis = np.array([s["psi"] for s in states])

    print("=" * 74)
    print("T7 — cumulative phase: is the offset field a multi-rung sum?")
    print(f"catalog: {len(states)} states, n in "
          f"[{states[0]['n']:.2f}, {states[-1]['n']:.2f}]")
    print("=" * 74)

    # ---- V. variogram
    rho, ds, cs = variogram(states)
    bins = [(lo, lo + 3) for lo in range(0, 27, 3)]
    print(f"\nV. variogram: Spearman rho(separation, circ-dist(psi)) = "
          f"{rho:+.3f}")
    print("   binned mean circular distance (rad):")
    for lo, hi in bins:
        m = (ds >= lo) & (ds < hi)
        if m.sum():
            print(f"     d in [{lo:>2},{hi:>2}) rungs: {cs[m].mean():.3f} "
                  f"({m.sum()} pairs)")
    null_rho = []
    for _ in range(2000):
        fr = {name: rng.uniform(0, 1) for name in names}
        st = build_states(fr)
        null_rho.append(variogram(st)[0])
    null_rho = np.array(null_rho)
    p_v = (null_rho >= rho).mean()
    print(f"   null (2000 shuffled-offset catalogs): rho = "
          f"{null_rho.mean():+.3f} +/- {null_rho.std():.3f}, "
          f"p(cumulative growth) = {p_v:.3f}")

    # ---- M. mean-field fixed point
    print("\nM. self-consistent mean field (sources = state density D_m):")
    for label, kw in [("w0 = 2 pi phi ln phi (two-sided)",
                       dict(omega=OMEGA_0)),
                      ("w0 = 0 (no propagation phase)",
                       dict(omega=0.0)),
                      ("one-sided (wakes from below only)",
                       dict(omega=OMEGA_0, one_sided=True)),
                      ("log sources, two-sided",
                       dict(omega=OMEGA_0, log_sources=True))]:
        cell, drift = mean_field(states, **kw)
        resid = np.array([circ_dist(s["psi"], cell[s["m_cell"]])
                          for s in states])
        r_obs = resid.mean()
        null = []
        for _ in range(400):
            fr = {name: rng.uniform(0, 1) for name in names}
            st = build_states(fr)
            cell_n, _ = mean_field(st, **kw)
            r_n = np.mean([circ_dist(s["psi"], cell_n[s["m_cell"]])
                           for s in st])
            null.append(r_n)
        null = np.array(null)
        p_m = (null <= r_obs).mean()
        print(f"   {label:>38}: residual {r_obs:.3f} vs null "
              f"{null.mean():.3f} +/- {null.std():.3f}, p = {p_m:.3f} "
              f"(fixed-point drift {drift:.2e})")
    print("\n   the null shuffles the fractional offsets only: the rung")
    print("   density profile D_m and the phase window are untouched.")

    # per-cell audit for the physically motivated one-sided model:
    # predicted cell phase vs observed state phases
    cell1, _ = mean_field(states, omega=OMEGA_0, one_sided=True)
    from collections import defaultdict
    obs = defaultdict(list)
    for s in states:
        obs[s["m_cell"]].append(s)
    print("\n   one-sided model, per-cell audit (predicted vs observed):")
    print(f"   {'cell':>5} {'pred psi':>9} {'obs mean':>9}")
    for m in sorted(cell1):
        if m in obs:
            ps = [s["psi"] for s in obs[m]]
            print(f"   {m:>5} {cell1[m]:>+9.2f} {np.mean(ps):>+9.2f}"
                  f"  ({len(ps)} states)")

    # ---- summary line
    print("\nVerdict: see doc T7 — the superposition premise is verified")
    print("(Panel D); whether the catalog's offsets carry the cumulative")
    print("structure is decided by the p-values above.")


if __name__ == "__main__":
    main()
