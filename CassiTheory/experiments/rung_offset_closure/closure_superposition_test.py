"""Multi-rung closure superposition test T8.

Run:  python experiments/rung_offset_closure/closure_superposition_test.py

The crossing responds to the total phasor sum of all rungs (T6,
`two-fluid/run_rung_offset_probe_panel_d.py`).  If each bubble's
emission phase is anchored by its last closure event,

    psi_r = omega_0 (r - c(r)) mod 2 pi,
    c(r) = last Fibonacci closure {5, 13, 34, 89, 233, 610} at or below r,
    omega_0 = 2 pi phi ln phi = 4.89 rad/rung (self-similar wake advance),

then the crossing position in every cell is predicted with zero free
parameters:

    Z_n = sum_r A_{r-n} e^{i(psi_r - 2 pi phi^{r-n})}
    crossing_n = (-arg Z_n / 2 pi) mod 1

Amplitudes: A_0 = A_+/-1 = 1 (adjacent bubbles equal, translation
invariance, the probe baseline) and A_d = phi^{-(|d|-1)} for |d| >= 2
(probe Panel D measurements).  The prediction for cell n is the
crossing position mod 1; the residual against each state is the mod-1
distance to its fractional rung position.  The two-bubble coherent
offset +0.060 is a constant mod-1 shift and drops out of the test.

Null: shuffled fractional offsets (same rung positions, same closure
structure).  Variants: omega_0 fixed at the framework value; omega
free over [0, 2 pi) (search-corrected); naive amplitudes phi^-|d|;
closure set extended with {26, 285}.
"""

import numpy as np
from catalog_psi_map import (MASSES, signed_delta, A0, B0, PHI, LNPHI,
                             M_PL)

OMEGA_0 = 2 * np.pi * PHI * LNPHI        # 4.89 rad/rung
CLOSURES = np.array([5, 13, 34, 89, 233, 610], dtype=float)
CLOSURES_EXT = np.sort(np.append(CLOSURES, [26.0, 285.0]))


def emission_phases(rungs, omega, closures):
    """psi_r = omega (r - c(r)) mod 2 pi."""
    c = np.array([closures[closures <= r].max() for r in rungs])
    return omega * (rungs - c) % (2 * np.pi)


def crossing_profile(omega, closures, naive_amp=False, r_lo=66, r_hi=122,
                     causal=None):
    """Crossing position mod 1 for every cell n in [80, 108).

    causal: None = all rungs (standing IC, every wake present); 'n+1' =
    only wakes emitted at rungs <= n+1 (the cascade builds upward; the
    crossing forms when the cell-top bubble condenses); 'n' = rungs
    <= n only.
    """
    rungs = np.arange(r_lo, r_hi)
    psi = emission_phases(rungs, omega, closures)
    cells = np.arange(80, 109)
    d = rungs[None, :] - cells[:, None]         # (cells, rungs)
    if causal is None:
        mask = np.ones_like(d, dtype=bool)
    elif causal == "n+1":
        mask = d <= 1
    elif causal == "n":
        mask = d <= 0
    else:
        raise ValueError(causal)
    if naive_amp:
        A = np.where(d == 0, 1.0, PHI ** (-np.abs(d)))
    else:
        A = np.where(np.abs(d) <= 1, 1.0, PHI ** (-(np.abs(d) - 1)))
    ang = psi[None, :] - 2 * np.pi * PHI ** d   # (cells, rungs)
    Z = (np.where(mask, A, 0.0) * np.exp(1j * ang)).sum(axis=1)
    return (-np.angle(Z) / (2 * np.pi)) % 1.0


def mod1_dist(a, b):
    d = np.abs((a - b) % 1.0)
    return np.minimum(d, 1.0 - d)


def residual(cross, states):
    """Mean mod-1 distance of the states' fractional rung positions to
    the predicted crossing of their cell."""
    cell = np.array([s["m_cell"] for s in states])
    frac = np.array([s["frac"] for s in states])
    return mod1_dist(cross[cell - 80], frac).mean()


def build_states(fracs):
    states = []
    for name, (m, _) in sorted(MASSES.items(),
                               key=lambda kv: np.log(M_PL / kv[1][0])):
        n = np.log(M_PL / m) / LNPHI
        frac = fracs[name] if name in fracs else n % 1.0
        delta = signed_delta(frac)
        states.append(dict(name=name, n=n, m_cell=int(np.floor(n)),
                           frac=frac, psi=(A0 - delta) / B0, delta=delta))
    return states


def main():
    rng = np.random.default_rng(23)
    names = sorted(MASSES, key=lambda k: np.log(M_PL / MASSES[k][0]))
    base = {name: (np.log(M_PL / MASSES[name][0]) / LNPHI) % 1.0
            for name in names}
    states = build_states(base)

    print("=" * 74)
    print("T8—multi-rung closure superposition")
    print("emission phases psi_r = omega (r - c(r)) mod 2 pi; the site")
    print("responds to the total phasor sum (T6); zero free parameters")
    print("at omega_0 = 2 pi phi ln phi = %.3f" % OMEGA_0)
    print("=" * 74)

    # (0) fixed-omega model: per-cell audit + residual
    cross = crossing_profile(OMEGA_0, CLOSURES)
    r_obs = residual(cross, states)
    print(f"\n(0) omega_0 fixed, Fibonacci closures:")
    print(f"    mean mod-1 residual = {r_obs:.3f} rungs "
          f"(uniform baseline 0.250)")
    print("    per-cell predicted crossing vs observed states:")
    from collections import defaultdict
    obs = defaultdict(list)
    for s in states:
        obs[s["m_cell"]].append(s)
    for m in sorted(obs):
        names_c = ", ".join(f"{s['name']}({s['frac']:.2f})"
                            for s in obs[m])
        print(f"      cell {m:>3}: crossing {cross[m - 80]:.3f} | "
              f"{names_c}")

    # nulls for the fixed model
    null = []
    for _ in range(2000):
        fr = {name: rng.uniform(0, 1) for name in names}
        null.append(residual(cross, build_states(fr)))
    null = np.array(null)
    p0 = (null <= r_obs).mean()
    print(f"    null (2000 shuffled-offset catalogs): "
          f"{null.mean():.3f} +/- {null.std():.3f}, p = {p0:.3f}")

    # (1) free omega, search-corrected
    omegas = np.arange(0, 2 * np.pi, 2 * np.pi / 300)
    print(f"\n(1) free omega scan [{omegas[0]:.2f}, {2*np.pi:.2f}), "
          f"search-corrected:")
    best_r = np.inf
    best_om = None
    for om in omegas:
        r = residual(crossing_profile(om, CLOSURES), states)
        if r < best_r:
            best_r, best_om = r, om
    null1 = []
    for _ in range(300):
        fr = {name: rng.uniform(0, 1) for name in names}
        st = build_states(fr)
        b = np.inf
        for om in omegas:
            r = residual(crossing_profile(om, CLOSURES), st)
            if r < b:
                b = r
        null1.append(b)
    null1 = np.array(null1)
    p1 = (null1 <= best_r).mean()
    print(f"    best omega = {best_om:.3f} rad/rung, residual = "
          f"{best_r:.3f}")
    print(f"    null (300 catalogs, same search): {null1.mean():.3f} "
          f"+/- {null1.std():.3f}, p = {p1:.3f}")
    print(f"    candidates: 2 pi ln phi = 3.024, 2 pi/phi = 3.883, "
          f"2 pi/phi^2 = 2.400,")
    print(f"    2 pi phi ln phi = {OMEGA_0:.3f}, 3 pi/10 = 0.942")

    # (2) naive amplitudes
    cross_n = crossing_profile(OMEGA_0, CLOSURES, naive_amp=True)
    r2 = residual(cross_n, states)
    null2 = []
    for _ in range(1000):
        fr = {name: rng.uniform(0, 1) for name in names}
        null2.append(residual(cross_n, build_states(fr)))
    null2 = np.array(null2)
    print(f"\n(2) naive amplitudes phi^-|d|, omega_0 fixed: "
          f"residual {r2:.3f}, p = {(null2 <= r2).mean():.3f}")

    # (3) extended closure set {.., 26, 285}
    cross_e = crossing_profile(OMEGA_0, CLOSURES_EXT)
    r3 = residual(cross_e, states)
    null3 = []
    for _ in range(1000):
        fr = {name: rng.uniform(0, 1) for name in names}
        null3.append(residual(cross_e, build_states(fr)))
    null3 = np.array(null3)
    print(f"(3) closures extended with 26, 285, omega_0 fixed: "
          f"residual {r3:.3f}, p = {(null3 <= r3).mean():.3f}")

    # (4) sharp-set spotlight: J/psi (cell 88) and muon (cell 96)
    print("\n(4) spotlight on the sharp placements:")
    for name in ["J/psi", "mu"]:
        s = next(x for x in states if x["name"] == name)
        pred = cross[s["m_cell"] - 80]
        print(f"    {name:>6}: frac {s['frac']:.3f}, predicted crossing "
              f"{pred:.3f}, mod-1 distance {mod1_dist(s['frac'], pred):.3f}")

    # (5) causal truncation: the crossing forms when the cell-top bubble
    #     condenses; wakes from rungs above n+1 have not been emitted yet
    print("\n(5) causal truncation (wakes only from rungs <= n+1):")
    for causal in ["n+1", "n"]:
        cross_c = crossing_profile(OMEGA_0, CLOSURES, causal=causal)
        r_c = residual(cross_c, states)
        null_c = []
        for _ in range(1000):
            fr = {name: rng.uniform(0, 1) for name in names}
            null_c.append(residual(cross_c, build_states(fr)))
        null_c = np.array(null_c)
        best_rc, best_omc = np.inf, None
        for om in omegas:
            r = residual(crossing_profile(om, CLOSURES, causal=causal),
                         states)
            if r < best_rc:
                best_rc, best_omc = r, om
        null1c = []
        for _ in range(200):
            fr = {name: rng.uniform(0, 1) for name in names}
            st = build_states(fr)
            b = np.inf
            for om in omegas:
                b = min(b, residual(crossing_profile(om, CLOSURES,
                                                     causal=causal), st))
            null1c.append(b)
        null1c = np.array(null1c)
        print(f"    r <= n+{causal[1:] if causal != 'n' else 0}: fixed "
              f"omega_0 residual {r_c:.3f} "
              f"(p = {(null_c <= r_c).mean():.3f}); free omega best "
              f"{best_omc:.3f} -> {best_rc:.3f} "
              f"(p = {(null1c <= best_rc).mean():.3f})")

    print("\nVerdict: see doc T8—null if the p-values are large; the")
    print("closure-anchored emission phases then do not drive the sum.")


if __name__ == "__main__":
    main()
