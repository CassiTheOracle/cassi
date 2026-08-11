"""Spinor doublet structure: the half-angle convention unification.

Run:  python computations/spin_doublet_half_angle.py

Verifies the unified SO(2) convention between
`foundations/spin-fibonacci-spiral.md` and
`consciousness/chakras-as-cascade-bubbles.md`:

  - Single-component phase:  Theta advances 2 pi per cascade rung (the
    spin doc's asserted pitch convention, Theta = 2 pi n).
  - Doublet internal phase:  the physical state (Psi_Y, Psi_I) carries the
    half-angle Theta/2, so its internal phase advances pi per rung and its
    full SO(2) cycle spans 2 rungs (the chakra doc's P_parallel = 2).
  - Spinor property: under a single-component 2 pi rotation (one rung) the
    doublet changes sign; under 4 pi (two rungs) it returns to itself.

The two statements are the same convention seen from the single-component
vs the doublet viewpoint.

Sec 1—the sign flip (Derived, conditional on the pitch convention +
       the doublet postulate).
Sec 2—the chakra-node arithmetic (13 nodes at 2-rung spacing, steps
       142-166, 24-rung span of the 26-rung window).
"""

import numpy as np

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)


def doublet(theta, r=1.0):
    """The Yang/Yin doublet carrying the half-angle."""
    return np.array([np.sqrt(r) * np.exp(1j * theta / 2),
                     np.sqrt(1.0 / r) * np.exp(1j * theta / 2)])


def main():
    print("=" * 74)
    print("Spinor doublet structure: half-angle convention")
    print("=" * 74)

    # ------------------------------------------------------------------
    # Sec 1: the sign flip under a single-component 2 pi rotation
    # ------------------------------------------------------------------
    print("\n-- Sec 1  THE SIGN FLIP (one rung flips the doublet) --")
    r = 2.0  # a Yang-dominant ratio; the argument is r-independent
    th = 1.234  # arbitrary phase
    psi = doublet(th, r)
    psi_pi = doublet(th + np.pi, r)          # doublet internal phase + pi
    psi_2pi = doublet(th + 2 * np.pi, r)     # single-component 2 pi = 1 rung
    psi_4pi = doublet(th + 4 * np.pi, r)     # single-component 4 pi = 2 rungs

    # single component is single-valued under 2 pi
    comp = np.exp(1j * th)
    print(f"  single component:      e^{{i(theta+2pi)}} / e^{{i theta}} ="
          f" {np.exp(1j * (th + 2 * np.pi)) / comp:.6f}  (single-valued)")
    # the doublet's internal phase advances pi per rung (half-angle)
    print(f"  doublet internal phase per rung:  pi = {np.pi:.6f} rad;"
          f" full cycle 2 rungs = {2 * np.pi:.6f} rad")
    # the pair changes sign after the single-component 2 pi = one rung
    flip = np.exp(-1j * (2 * np.pi)) * psi_2pi / psi
    print(f"  Psi(Theta+2pi)/Psi(Theta)  = {flip[0]:.6f} (one rung:"
          f" the pair flips sign, spinor anti-periodicity)")
    # ... and returns after 4 pi = two rungs
    back = np.exp(-1j * (4 * np.pi)) * psi_4pi / psi
    print(f"  Psi(Theta+4pi)/Psi(Theta)  = {back[0]:.6f} (two rungs:"
          f" full SO(2) cycle of the doublet, P_parallel = 2)")
    # consistency: the pi internal advance IS the single-component 2 pi
    print(f"  check: Psi(Theta+2pi) == -Psi(Theta):"
          f" {np.allclose(psi_2pi, -psi)}")
    print(f"  check: Psi(Theta+4pi) == +Psi(Theta):"
          f" {np.allclose(psi_4pi, psi)}")
    print(f"  check: Psi(Theta+pi)  == -Psi(Theta+3pi):"
          f" {np.allclose(psi_pi, -doublet(th + 3 * np.pi, r))}")

    # ------------------------------------------------------------------
    # Sec 2: the chakra-node arithmetic (P_parallel = 2, steps 142-166)
    # ------------------------------------------------------------------
    print("\n-- Sec 2  THE 13 NODES (26-rung human window, 2-rung spacing) --")
    nodes = [142 + 2 * k for k in range(13)]
    print(f"  nodes: {nodes[0]} + 2k, k = 0..12 -> {nodes}")
    print(f"  count = (166 - 142)/2 + 1 = {len(nodes)}")
    print(f"  span = 166 - 142 = {max(nodes) - min(nodes)} rungs"
          f" (24 of the 26-rung window 142-168)")
    print(f"  phi^26 = {PHI**26:.4e}  (cell -> body scale ratio,"
          f" section 3.1 of the chakra doc)")
    print(f"  phi^24 = {PHI**24:.4e}  (13 nodes spanning 24 rungs,"
          f" section 8.3 of the chakra doc)")
    # spin values as doublet winding: s = (internal phase advance)/2 pi
    for s, dn in [(0, 0), (0.5, 1), (1, 2), (2, 4)]:
        print(f"  s = {s:>4}: doublet internal phase pi*{dn} ="
              f" {np.pi * dn:.1f} rad over {dn} rung(s) of single-component"
              f" phase 2 pi each")


if __name__ == "__main__":
    main()
