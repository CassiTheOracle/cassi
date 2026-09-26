#!/usr/bin/env python3
"""Qi-gravity strain-sensitivity scenario under the optional saturation chord.

Run:  python experiments/cassi_physics/cassi_gw_q_bound.py   (from repo root)

Evaluates prediction row 17 of `predictions/falsifiable-predictions.md` (§4
Gravity) under the optional saturation-chord branch

    G_eff/G_N = 1 + (phi**6 - 1) * q.

The endpoint coefficient is fixed by G_eff/G_N = 1 at q = 0 and
G_eff/G_N = phi**6 at q = 1. The resulting bound is conditional on this
Qi-gravity closure and on the declared strain-precision input; the canonical
two-fluid PDE does not supply a spacetime metric or waveform model.

Under this branch, the assumed inspiral strain ratio is

    h/h_GR = G_eff/G_N = 1 + (phi**6 - 1) * q_binary.

For a supplied fractional strain sensitivity eps_h, the algebraic scenario
gives

    q_binary < eps_h / (phi**6 - 1).

The script declares eps_h = 0.10 and 0.05 as illustrative sensitivity inputs.
They are not traced here to an event-level likelihood or published
amplitude-only bound.

Context inputs:
    d_L   = 40 Mpc         luminosity distance
    M_c   = 1.188 M_sun    chirp mass
    eps_h = 0.10, 0.05     illustrative fractional strain sensitivities
"""

import math


# --- Framework constants ---------------------------------------------------
PHI = (1.0 + math.sqrt(5.0)) / 2.0  # golden ratio
PHI6 = PHI ** 6                     # phi**6 = 17.9443: saturation ceiling
DELTA = PHI6 - 1.0                  # (phi**6 - 1) = 16.9443: chord coefficient

# --- Declared scenario inputs ----------------------------------------------
D_L_MPC = 40.0     # contextual luminosity distance (Mpc)
M_C = 1.188        # contextual chirp mass (solar masses)
EPS_H = 0.10       # illustrative fractional strain sensitivity
EPS_H_TIGHT = 0.05 # illustrative tighter sensitivity


def strain_ratio_chord(q):
    """h/h_GR = 1 + (phi**6 - 1) * q—the adopted chord law."""
    return 1.0 + DELTA * q


def q_bound(eps, coeff=DELTA):
    """Map a supplied fractional sensitivity to q under the chord closure."""
    return eps / coeff


def main():
    print("=" * 74)
    print("QI-GRAVITY STRAIN-SENSITIVITY SCENARIO—OPTIONAL CHORD CLOSURE")
    print("=" * 74)

    # (a) Modified-GR strain ratio under the adopted chord law
    print("\n(a) Strain ratio under the optional saturation-chord branch")
    print("    h/h_GR = 1 + (phi**6 - 1) * q_binary")
    print(f"    phi = {PHI:.10f}   phi**6 = {PHI6:.4f}   (phi**6 - 1) = {DELTA:.4f}")
    print("    The coefficient pins the q=0 GR endpoint and q=1 phi**6 endpoint.")
    for q in (0.53, 0.61, 1.0):
        print(f"    q = {q:<4}:  h/h_GR = 1 + {DELTA:.4f} * {q} = {strain_ratio_chord(q):7.3f}")

    # (b) Declared sensitivity scenario
    print("\n(b) Declared strain-sensitivity inputs")
    print(f"    Context: GW170817 at d_L = {D_L_MPC:.0f} Mpc, chirp mass M_c = {M_C:.3f} M_sun")
    print(f"    eps_h = {EPS_H:.2f} and {EPS_H_TIGHT:.2f} are illustrative inputs.")
    print("    This script does not source an event-level amplitude likelihood.")
    # Context only: GR inspiral strain amplitude at f = 100 Hz (quadrupole
    # formula). The bound below uses only the strain RATIO, so h_GR cancels.
    G, C, M_SUN, MPC = 6.67430e-11, 2.99792458e8, 1.98892e30, 3.085677581e22
    f = 100.0  # Hz, LIGO band center
    h_gr = (4.0 / (D_L_MPC * MPC)) * (G * M_C * M_SUN / C ** 2) ** (5.0 / 3.0) \
        * (math.pi * f / C) ** (2.0 / 3.0)
    print(f"    context: h_GR(f = 100 Hz) ~ {h_gr:.2e} (quadrupole formula; ratio cancels)")

    # (c) The bound: q_binary < eps_h / (phi**6 - 1)
    print("\n(c) Bound: q_binary < eps_h / (phi**6 - 1)")
    q10 = q_bound(EPS_H)
    q05 = q_bound(EPS_H_TIGHT)
    print(f"    eps_h = 0.10:  q_binary < 0.10 / {DELTA:.4f} = {q10:.4e}  ~  5.9e-3")
    print(f"    eps_h = 0.05:  q_binary < 0.05 / {DELTA:.4f} = {q05:.4e}  ~  2.95e-3")
    print("    Conditional interval for the two declared precision inputs:")
    print(f"      eps_h = 0.10 -> q_binary < {q10:.4e}")
    print(f"      eps_h = 0.05 -> q_binary < {q05:.4e}")

    # (d) Interpretation limits
    print("\n(d) Interpretation limits")
    print("    The canonical two-fluid PDE supplies neither a spacetime metric")
    print("    nor a binary-environment q profile.")
    print("    The numbers above are sensitivity conversions for the optional")
    print("    chord closure, not observational constraints.")

    print("\n" + "=" * 74)
    print("SCENARIO RESULT: eps_h = 0.10 maps to")
    print(f"q_binary < {q10:.4e} under h/h_GR = 1 + (phi**6-1)*q.")
    print("A sourced waveform likelihood and metric closure are required before")
    print("this becomes a GW170817 bound.")
    print("=" * 74)


if __name__ == '__main__':
    main()
