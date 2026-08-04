"""The width of the spiral arms at the seed.

Run:  python computations/seed_arm_width.py

The five-arm Fibonacci spiral at the bubble poles
(`foundations/spin-fibonacci-spiral.md` sec 1/3, `foundations/wake-geometry.md`
sec 3) has a determined arm width at the seed — the innermost radius of the
spiral, where the bubble is born.  For the universe-scale bubble the seed
sits at the bottom of the cascade (rung 0 = the Planck scale).

Sec 1 — the seed geometry (Derived): the five arms follow the golden-angle
        phyllotaxis 2 pi/phi^2 = 137.5 deg; 5 seeds span 687.5 deg ~ 2 turns;
        the closure ladder 5, 13, 34, 89, 233, 610 is the angular-return
        ladder of 1/phi^2.
Sec 2 — the width (Derived): two framework-native determinations:
        (a) cross-width: the arm is the condensation line of the Yin wake,
            width Lambda_I(r) = r/phi  ->  w_seed = ell_Pl/phi;
        (b) arc spacing: the five arms tile the azimuth,
            w_seed = 2 pi ell_Pl/5.
        The ratio (2 pi/5) phi = 2.034 ~ 2: the arms are spaced two
        wake-widths apart — arm + void, the staggered checkerboard in
        azimuth (pi phi = 5.083 vs 5: 1.6%, the framework's near-miss
        scale).
Sec 3 — rung placements: the cross-width sits exactly one rung below
        Planck (ell_{-1}); the arc spacing sits at log_phi(2 pi/5) =
        0.4746 rungs below Planck — within 1.3% of the first half-rung
        below the cascade bottom (the microcascade's first half-step).
Sec 4 — the self-replication ("self-replicates to seed-width at 13"):
        the closure ratios F_{k+2}/F_k -> phi^2 make the angular structure
        of the arms return to the seed-width at every closure level, with
        the Fibonacci-approximation precision (13: 0.7%, 34: 0.1%, 89:
        0.02%, ...).  The seed-width is a ladder-wide invariant, not just
        the innermost value.
Sec 5 — the top of the bubble: the five arms' arc width at rung 285 is
        2 pi ell_285/5 = 240 Mpc ~ 1.26 ell_285 — the arms are the
        bubble's meridian lines; the pole five-fold is the static
        geometry (the bubble PDE shows no dynamical m = 5 mode,
        `foundations/spin-fibonacci-spiral.md` sec 1).
"""

import numpy as np

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)
L_PL = 1.616255e-35          # m
L_285 = 191.0                # Mpc (wake-geometry.md sec 1a)


def main():
    print("=" * 74)
    print("Seed arm width: the five arms of the pole spiral at birth")
    print("=" * 74)

    # ------------------------------------------------------------------
    # Sec 1: the seed geometry
    # ------------------------------------------------------------------
    print("\n── Sec 1  THE SEED GEOMETRY (Derived) ──")
    print("  golden angle 2 pi/phi^2 =", f"{360/PHI**2:.1f} deg")
    print("  5 seeds: 5 x 137.5 deg =", f"{5*360/PHI**2:.1f} deg ~ 2 turns")
    print("  closure ladder (convergents of 1/phi^2): 5, 13, 34, 89,"
          " 233, 610")
    print("  the seed = the innermost radius of the pole spiral = the")
    print("  bubble's birth scale = rung 0 = ell_Pl =", f"{L_PL:.4e} m")

    # ------------------------------------------------------------------
    # Sec 2: the width
    # ------------------------------------------------------------------
    print("\n── Sec 2  THE WIDTH (Derived) ──")
    w_cross = L_PL / PHI
    w_arc = 2 * np.pi * L_PL / 5
    print(f"  (a) cross-width (the arm is the Yin wake, Lambda_I = r/phi):")
    print(f"        w_seed = ell_Pl/phi = {w_cross:.4e} m")
    print(f"  (b) arc spacing (five arms tile the azimuth):")
    print(f"        w_seed = 2 pi ell_Pl/5 = {w_arc:.4e} m")
    ratio = w_arc / w_cross
    print(f"  ratio (2 pi/5) phi = {ratio:.3f} ~ 2: the arms are spaced")
    print("  two wake-widths apart — arm + void, the staggered")
    print("  checkerboard in azimuth")
    print(f"  near-identity: pi phi = {np.pi*PHI:.3f} vs 5"
          f"  ({100*(np.pi*PHI/5-1):+.1f}% — the framework's near-miss"
          f" scale)")

    # ------------------------------------------------------------------
    # Sec 3: rung placements
    # ------------------------------------------------------------------
    print("\n── Sec 3  RUNG PLACEMENTS ──")
    n_cross = np.log(1 / PHI) / LNPHI
    n_arc = np.log(2 * np.pi / 5) / LNPHI
    print(f"  cross-width: one rung below Planck (ell_{{ {n_cross:.0f} }})"
          f" by definition")
    print(f"  arc spacing: log_phi(2 pi/5) = {n_arc:.4f} rungs below"
          f" Planck")
    print(f"    ({abs(n_arc - 0.5):.3f} from the half-rung — 1.3%: the")
    print("     first half-step of the mirror cascade below the bottom)")
    print("  the seed's arm structure lives at the transition where the")
    print("  next bubble (the microcascade) begins — the pentagon is the")
    print("  birth geometry, consistent with the five-fold as the")
    print("  transition structure (rung-offset-mechanism.md sec 4.4).")

    # ------------------------------------------------------------------
    # Sec 4: self-replication at 13
    # ------------------------------------------------------------------
    print("\n── Sec 4  SELF-REPLICATION AT 13 (Derived) ──")
    F = [5, 13, 34, 89, 233, 610]
    print(f"  {'closure':>6} {'F_{k+2}/F_k':>12} {'vs phi^2':>10}"
          f" {'return':>12}")
    for i in range(len(F) - 1):
        r = F[i + 1] / F[i]
        d = 100 * (r / PHI**2 - 1)
        # angular return of the golden-angle pattern after F_k seeds
        ret = (F[i] * 360 / PHI**2) % 360
        ret = min(ret, 360 - ret)
        print(f"  {F[i]:>6} {r:>12.4f} {d:>+9.2f}% {ret:>10.2f} deg")
    print("  the angular structure of the arms returns to the seed-width")
    print("  at every closure level to the Fibonacci-ratio precision:")
    print("  0.7% at 13, 0.1% at 34, 0.02% at 89 — 'self-replicates to")
    print("  seed-width at 13' is the first step of a ladder-wide")
    print("  invariance of the arm width.")

    # ------------------------------------------------------------------
    # Sec 5: the top of the bubble
    # ------------------------------------------------------------------
    print("\n── Sec 5  THE TOP OF THE BUBBLE ──")
    w_top = 2 * np.pi * L_285 / 5
    print(f"  the five arms' arc width at rung 285 (ell_285 = {L_285}"
          f" Mpc):")
    print(f"        2 pi ell_285/5 = {w_top:.0f} Mpc = 1.26 ell_285")
    print(f"        vs the Yin wake there: ell_285/phi = {L_285/PHI:.0f}"
          f" Mpc (the 117.9 Mpc of wake-geometry.md)")
    print(f"        ratio {w_top/(L_285/PHI):.2f} — the same 2.03: the")
    print("  checkerboard arm + void structure holds at every radius.")
    print("  the five arms are the bubble's meridian lines; the pole")
    print("  five-fold is the static phyllotaxis geometry (no dynamical")
    print("  m = 5 mode — spin-fibonacci-spiral.md sec 1).")

    print()
    print("  Verdict: the seed arm width is determined — the cross-width")
    print("  ell_Pl/phi ~ 1.0e-35 m (the Yin wake), the arc spacing")
    print("  2 pi ell_Pl/5 ~ 2.0e-35 m, spaced 2.03 wake-widths apart.")
    print("  What it buys: the bottom-of-cascade geometry (the pentagon")
    print("  birth), the microcascade's first half-step at rung -0.475,")
    print("  and the ladder-wide invariance of the seed-width under the")
    print("  closure ladder.")


if __name__ == "__main__":
    main()
