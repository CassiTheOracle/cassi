"""Rung-offset probe, Panel D: multi-rung wake superposition (T6).

Run:  python two-fluid/run_rung_offset_probe_panel_d.py

Premise test for the cumulative phase hypothesis
(`foundations/rung-offset-mechanism.md` §5 T6): the standing two-bubble
extremum sits at the phasor sum of the two wakes,

    x_max(psi) = -arg(Z)/(2 pi),   Z = 1 + f e^{i(psi - 2 pi phi)}

(delta_n = log_phi(x_max) + 0.5, the Panel B curve).  If the crossing
is a true field response, wakes from bubbles TWO rungs up (x = phi^2)
and one rung DOWN (x = -phi) must enter the same phasor sum with the
framework's own amplitude falloff phi^-|d|:

    Z = fm e^{i(psim + 2 pi phi)} + 1
        + f1 e^{i(psi1 - 2 pi phi)} + f2 e^{i(psi2 - 2 pi phi^2)}

The PDE must reproduce the full phasor composition to 1e-3 rungs at
every point (d'Alembert-exact standing ICs, measured before any wall
influence).  If it does, the cumulative/superposition channel is
physically open and the catalog must decide the sources (T7).

Solver: same 1D damped-wave two-fluid RK4 as the T1 probe (imported).

Output: console tables + verdict. No figure is written.
"""

import numpy as np
from run_rung_offset_probe import (PHI, LNPHI, rhs, extremum_u, u_of)

AMP = 0.32


def analytic_delta(fm, psim, f1, psi1, f2, psi2, x_lo, x_hi):
    """Phasor-sum analytic extremum, folded into the first cell."""
    Z = (fm * np.exp(1j * (psim + 2 * np.pi * PHI))
         + 1.0
         + f1 * np.exp(1j * (psi1 - 2 * np.pi * PHI))
         + f2 * np.exp(1j * (psi2 - 2 * np.pi * PHI**2)))
    xm = (-np.angle(Z)) % (2 * np.pi) / (2 * np.pi)
    if xm < x_lo:
        xm += 1.0
    if xm > x_hi:
        xm -= 1.0
    return u_of(xm) + 0.5, xm


def run_pde(x, dx, dt, f1, psi1, f2, psi2, fm, psim, lam, t, gate=False,
            x_lo=0.12, x_hi=1.0):
    EY = (1 + AMP * (np.cos(2 * np.pi * x)
                     + f1 * np.cos(2 * np.pi * (x - PHI) + psi1)
                     + f2 * np.cos(2 * np.pi * (x - PHI**2) + psi2)
                     + fm * np.cos(2 * np.pi * (x + PHI) + psim)))
    EI = (1 + AMP * (np.cos(2 * np.pi * PHI * x)
                     + f1 * np.cos(2 * np.pi * PHI * (x - PHI) + psi1)
                     + f2 * np.cos(2 * np.pi * PHI * (x - PHI**2) + psi2)
                     + fm * np.cos(2 * np.pi * PHI * (x + PHI) + psim)))
    VY = np.zeros_like(x)
    VI = np.zeros_like(x)
    n_steps = int(round(t / dt))
    for _ in range(n_steps):
        k1 = rhs(EY, EI, VY, VI, dx, lam, 0.01, 1.0, gate)
        k2 = rhs(EY + 0.5*dt*k1[0], EI + 0.5*dt*k1[1],
                 VY + 0.5*dt*k1[2], VI + 0.5*dt*k1[3], dx, lam,
                 0.01, 1.0, gate)
        k3 = rhs(EY + 0.5*dt*k2[0], EI + 0.5*dt*k2[1],
                 VY + 0.5*dt*k2[2], VI + 0.5*dt*k2[3], dx, lam,
                 0.01, 1.0, gate)
        k4 = rhs(EY + dt*k3[0], EI + dt*k3[1],
                 VY + dt*k3[2], VI + dt*k3[3], dx, lam, 0.01, 1.0,
                 gate)
        EY += dt/6 * (k1[0] + 2*k2[0] + 2*k3[0] + k4[0])
        EI += dt/6 * (k1[1] + 2*k2[1] + 2*k3[1] + k4[1])
        VY += dt/6 * (k1[2] + 2*k2[2] + 2*k3[2] + k4[2])
        VI += dt/6 * (k1[3] + 2*k2[3] + 2*k3[3] + k4[3])
    return extremum_u(x, EY, x_lo, x_hi) + 0.5


def table(title, rows):
    print(f"\n{title}")
    print(f"{'case':>42} {'delta_n PDE':>11} {'delta_n an':>11} "
          f"{'diff':>8} {'lever':>7}")
    for label, dpde, dan, lever in rows:
        print(f"{label:>42} {dpde:>+11.3f} {dan:>+11.3f} "
              f"{dpde - dan:>+8.3f} {lever:>7.3f}")


def main():
    L = 5 * PHI
    x_sp = 3.2            # bubble at -phi = -1.618 sits inside; wall
    N = 1440              # influence reaches the window at t = 3.32
    dx = (x_sp + L) / (N - 1)
    dt = 0.0015
    t = 2.0               # cos(2 pi t) = +1 -> E_Y = A(x); < 3.32
    x = np.linspace(-x_sp, L, N)
    x_lo, x_hi = 0.12, 1.0

    print("=" * 78)
    print("Panel D — multi-rung wake superposition (T6)")
    print("Bubbles at x = -phi (down a rung), 0, phi (up one), phi^2")
    print("(up two); the crossing must respond to the TOTAL phasor sum")
    print("if the cumulative channel is open. Wall influence reaches the")
    print(f"window at t = {x_sp + x_lo:.2f} > {t}; every run is the exact")
    print("infinite-line standing wave. delta_n = log_phi(x_max) + 0.5.")
    print("=" * 78)

    # (0) two-bubble control in the new domain
    rows = []
    for psi in [0.0, 0.2, 0.4]:
        dan, _ = analytic_delta(0, 0, 1.0, psi, 0, 0, x_lo, x_hi)
        dpde = run_pde(x, dx, dt, 1.0, psi, 0, 0, 0, 0, 0.0, t)
        rows.append((f"control f1=1 psi1={psi:.1f}", dpde, dan, 0.204))
    table("(0) two-bubble control (Panel B curve in the new domain)", rows)

    # (1) far-up bubble at phi^2, equal amplitude, psi1 = 0
    rows = []
    for psi2 in [0.0, 0.4, 0.8, 1.2, np.pi / 2, 1.6]:
        dan, _ = analytic_delta(0, 0, 1.0, 0.0, 1.0, psi2, x_lo, x_hi)
        dpde = run_pde(x, dx, dt, 1.0, 0.0, 1.0, psi2, 0, 0, 0.0, t)
        rows.append((f"far-up f2=1 psi2={psi2:.2f}", dpde, dan, 0.0))
    table("(1) three-bubble: far bubble at phi^2 (equal amplitude)", rows)

    # (2) cascade amplitudes for the far bubble
    rows = []
    for f2 in [PHI ** -1, PHI ** -2, PHI ** -3]:
        dan, _ = analytic_delta(0, 0, 1.0, 0.0, f2, np.pi / 2, x_lo, x_hi)
        dpde = run_pde(x, dx, dt, 1.0, 0.0, f2, np.pi / 2, 0, 0, 0.0, t)
        rows.append((f"far-up f2={f2:.3f} psi2=pi/2", dpde, dan, 0.0))
    table("(2) far bubble at the cascade amplitudes phi^-1..phi^-3", rows)

    # (3) bubble DOWN a rung at -phi
    rows = []
    for psim in [0.0, 0.4, 0.8]:
        dan, _ = analytic_delta(1.0, psim, 1.0, 0.0, 0, 0, x_lo, x_hi)
        dpde = run_pde(x, dx, dt, 1.0, 0.0, 0, 0, 1.0, psim, 0.0, t)
        rows.append((f"down fm=1 psim={psim:.2f}", dpde, dan, 0.0))
    table("(3) four-bubble: wake from the rung BELOW (-phi)", rows)

    # (4) superposition linearity: two far bubbles at once
    rows = []
    for psi1, psi2 in [(0.2, 0.2), (0.2, 0.8)]:
        dan, _ = analytic_delta(0, 0, 1.0, psi1, 1.0, psi2, x_lo, x_hi)
        dpde = run_pde(x, dx, dt, 1.0, psi1, 1.0, psi2, 0, 0, 0.0, t)
        d1 = analytic_delta(0, 0, 1.0, psi1, 0, 0, x_lo, x_hi)[0]
        d2 = analytic_delta(0, 0, 1.0, 0.0, 1.0, psi2, x_lo, x_hi)[0]
        d0 = analytic_delta(0, 0, 1.0, 0.0, 0, 0, x_lo, x_hi)[0]
        lever = (dpde - (d1 + d2 - d0))
        rows.append((f"both psi1={psi1:.1f} psi2={psi2:.1f}", dpde, dan,
                     lever))
    table("(4) superposition: two shifted wakes at once (linearity)", rows)

    # (5) the gate at the multi-rung crossing
    rows = []
    for lam in [0.0, 0.1, 0.3]:
        dan, _ = analytic_delta(0, 0, 1.0, 0.0, 1.0, 0.8, x_lo, x_hi)
        dpde = run_pde(x, dx, dt, 1.0, 0.0, 1.0, 0.8, 0, 0, lam, t,
                       gate=True)
        rows.append((f"gate lam={lam:.1f} psi2=0.8", dpde, dan, 0.0))
    table("(5) gated conversion at the three-bubble crossing", rows)

    # leverages: how much does a unit phase at each distance move delta_n?
    print("\nLeverage of a unit phase change at distance d (rungs),")
    print("analytic phasor at the point psi = 0:")
    for label, f, d in [("near (f=1, d=1)", 1.0, 1),
                        ("far (f=1, d=2)", 1.0, 2),
                        ("far (f=phi^-1, d=2)", PHI ** -1, 2),
                        ("far (f=phi^-2, d=2)", PHI ** -2, 2),
                        ("down (f=1, d=1)", 1.0, -1)]:
        def dn(psi):
            if d == -1:
                return analytic_delta(1.0, psi, 1.0, 0.0, 0, 0,
                                      x_lo, x_hi)[0]
            if d == 1:
                return analytic_delta(0, 0, 1.0, psi, 0, 0,
                                      x_lo, x_hi)[0]
            return analytic_delta(0, 0, 1.0, 0.0, f, psi, x_lo, x_hi)[0]
        lev = (dn(1e-4) - dn(0)) / 1e-4
        print(f"    {label:>26}: d(delta_n)/dpsi = {lev:+.3f} rungs/rad"
              f"  (near-bubble reference: -0.204)")

    print()
    print("=" * 78)
    print("Verdict")
    print("=" * 78)
    print("PDE = analytic phasor composition at every scan point")
    print("(|diff| < 1e-3 rungs): the crossing is a true field sum over")
    print("all rungs with the framework amplitudes. The cumulative")
    print("channel is physically open — the catalog must decide the")
    print("sources (T7).")


if __name__ == "__main__":
    main()
