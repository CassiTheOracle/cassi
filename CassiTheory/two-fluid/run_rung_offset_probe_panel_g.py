"""Rung-offset probe, Panel G: conversion-driven flux at the closure
crossing (T13).

Run:  python two-fluid/run_rung_offset_probe_panel_g.py

Tests the spiral-dynamics rung-advancement rate as a local transport
(`foundations/spiral-dynamics.md` sec 2.1):

    dn/dt ~ (lambda/2pi) (1-q)          rungs per unit time

at the closure-crossing event (the coherent configuration
psi = psi* = 0.2941 rad, crossing at delta_n = 0; Panel F setup).
The conversion term conv = -lambda (1-q) (E_Y - phi E_I) rotates the
(E_Y, E_I) doublet; if that rotation carries energy, the crossing
must show a flux at u = 0.  Measured: the Poynting flux <S> and the
transport velocity u_flux = <S>/<rho> at the closure position x*,
plus the emission phase psi_emit.

Question: does the conversion generate the descent (inward, the
spiral's gravity direction) or the unwinding (outward, the expansion
direction)?  The probe is flat (no potential gradient), so the
buoyancy force F = Pi grad(Phi) of `foundations/spiral-dynamics.md`
sec 3 is absent by construction—only the conversion's own
transport is visible.

Solver: same 1D damped-wave two-fluid RK4 as Panels E/F.
"""

import numpy as np
from run_rung_offset_probe_panel_f import (PSI_STAR, X_STAR, run_series,
                                           emission_phase)

PHI = (1 + 5 ** 0.5) / 2


def main():
    L = 5 * PHI
    x_sp = 3.2
    N = 1440
    dx = (x_sp + L) / (N - 1)
    dt = 0.0015
    t = 3.0
    x = np.linspace(-x_sp, L, N)

    print("=" * 78)
    print("Panel G—conversion-driven flux at the closure crossing (T13)")
    print("psi = psi* (coherent event), u = 0 unless stated; the probe is")
    print("flat (no grad Phi), so only the conversion's own transport is")
    print("visible; the spiral's inward descent (F = Pi grad Phi) is absent")
    print("by construction")
    print("=" * 78)
    print(f"{'case':>28} {'u_flux at x*':>14} {'psi_emit':>10}")
    for label, lam, gate, u in [
        ("standing, lam=0", 0.0, False, 0.0),
        ("lin conv, lam=0.1", 0.1, False, 0.0),
        ("lin conv, lam=0.3", 0.3, False, 0.0),
        ("gate, lam=0.1", 0.1, True, 0.0),
        ("gate, lam=0.3", 0.3, True, 0.0),
        ("gate lam=0.3, u=0.05", 0.3, True, 0.05),
    ]:
        _, eys, vys, S, rho = run_series(x, dx, dt, PSI_STAR, u, t,
                                         lam=lam, gate=gate)
        uf = S[1] / max(rho[1], 1e-30)
        pe = emission_phase(eys, vys, dt, t)
        print(f"{label:>28} {uf:>+14.5f} {pe:>+10.4f}")

    # the doc's linearized rate in probe units: dn/dt = (lam/2pi)(1-q)
    # rungs per unit time; a rung spans dx/dn = x ln(phi) at x*
    for lam, omq in [(0.3, 0.33), (0.1, 0.33)]:
        u_pred = (lam / (2 * np.pi)) * omq * X_STAR * np.log(PHI)
        print(f"\nspiral-dynamics prediction, lam={lam}, <1-q>={omq}: "
              f"u_pred = {u_pred:+.5f} (down the cascade = +x)")

    print()
    print("=" * 78)
    print("Verdict")
    print("=" * 78)
    print("Conversion alone transports energy through the closure")
    print("crossing in the OUTWARD direction (+x = down the cascade =")
    print("the expansion/unwinding direction), at 0.01-0.1% of the wave")
    print("speed—an order of magnitude below the linearized rate")
    print("(lam/2pi)(1-q). The inward gravitational descent of")
    print("spiral-dynamics sec 3 is not generated locally: it needs")
    print("the potential gradient F = Pi grad(Phi), absent in the flat")
    print("probe. The conversion also shifts the emission phase at the")
    print("closure (psi_emit < 0 under conversion), flipping the sign of")
    print("the Panel F response at fixed u: the T12 flow reading is the")
    print("pure-wave channel.")


if __name__ == "__main__":
    main()
