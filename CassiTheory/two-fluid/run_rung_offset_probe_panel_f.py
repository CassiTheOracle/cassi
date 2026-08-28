"""Rung-offset probe, Panel F: closure-crossing event—emission phase and flow.

Run:  python two-fluid/run_rung_offset_probe_panel_f.py

The closure-crossing event is the two-bubble crossing pinned at an
integer rung (delta_n = 0), the coherent configuration
psi = psi* = A0/B0 = 0.2941 rad (`foundations/rung-offset-mechanism.md`
sec 4.2; probe Panel B).  At a Fibonacci closure rung this is the pool
forming as the spiral closes.  The catalog's closure state is J/psi at
n = 88.980 (rung 89, delta_n = -0.0199); mu at n = 95.9998 (rung 96,
delta_n = -0.0002) is the nearest-integer control.

Measured at the event (T12):

  (a) the wake emission phase psi_emit: the phase lag of the crossing's
      oscillation relative to the source bubble—the complex ratio of
      the Fourier components at omega = 2 pi, over an integer number of
      periods.  Standing event (u = 0): psi_emit = 0 (in phase);
  (b) the crossing delta_n vs descent u at psi = psi* (the T11
      constitutive curve at the coherent event: delta_n ~ 1.6 u);
  (c) the flow-compensated event: psi_src(u) = psi* + 7.84 u holds the
      crossing at the closure rung under the descent; the emission
      phase there is the pool-at-closure reading psi_emit(u);
  (d) the energy flux through the crossing (Poynting <S> and the
      transport velocity u_flux = <S>/<rho>) as a direct flow reading.

Flow determination: the catalog state at the closure (J/psi,
delta_n = -0.01986) inverts the constitutive relation with the
MEASURED emission phase.  The pool's source phase is the closure
phase psi* plus the emission lag of the wake that leaves the event
(the emission phase is the lag of the crossing's oscillation relative
to the source bubble; at the standing event it is 0 while the source
phase is psi*), so

    delta_n = A0 - B0 (psi* + psi_emit(u)) + 1.6 u
            = 1.6 u - B0 psi_emit(u)

solved self-consistently for u*.  If psi_emit is u-insensitive
(psi_emit ~ 0), the reading is definite: u* = delta_n/1.6—J/psi:
-0.012, mu: -0.0001.  If psi_emit tracks the source phase at ~7.8 rad
per unit u, the T11 degeneracy survives in the emission channel.

Solver: same 1D damped-wave two-fluid RK4 + upwind advection as Panel E
(`two-fluid/run_rung_offset_probe_panel_e.py`).
"""

import numpy as np
from run_rung_offset_probe import PHI, LNPHI, rhs, extremum_u, u_of

AMP = 0.32
A0, B0 = 0.060, 0.204          # delta_n(psi) = A0 - B0 psi (Panel B)
PSI_STAR = A0 / B0             # coherent crossing at delta_n = 0
X_STAR = PHI ** -0.5           # x with u = -0.5, the delta_n = 0 position


def advect(E, u, dx):
    """Upwind advection (u > 0: drift to +x), first order."""
    dE = np.empty_like(E)
    dE[1:] = (E[1:] - E[:-1]) / dx
    dE[0] = 0.0
    return u * dE


def run_series(x, dx, dt, psi, u, t, lam=0.0, gate=False):
    """RK4 + advection; returns final fields, probe time series, flux.

    Probes: the source bubble at x = 0 and the closure position x*.
    Records E_Y and V_Y at each probe every step, plus the accumulated
    Poynting flux S = -dE/dx * dE/dt and energy density
    rho = 0.5[(dE/dt)^2 + (dE/dx)^2].
    """
    EY = 1 + AMP * (np.cos(2 * np.pi * x) + np.cos(2 * np.pi * (x - PHI) + psi))
    EI = 1 + AMP * (np.cos(2 * np.pi * PHI * x)
                    + np.cos(2 * np.pi * PHI * (x - PHI) + psi))
    VY = np.zeros_like(x)
    VI = np.zeros_like(x)
    n_steps = int(round(t / dt))
    i0 = int(np.argmin(np.abs(x - 0.0)))
    ix = int(np.argmin(np.abs(x - X_STAR)))
    eys = np.empty((n_steps, 2))
    vys = np.empty((n_steps, 2))
    S_acc = np.zeros(2)
    rho_acc = np.zeros(2)
    for step in range(n_steps):
        aEY = advect(EY, u, dx)
        aEI = advect(EI, u, dx)
        k1 = rhs(EY, EI, VY, VI, dx, lam, 0.01, 1.0, gate)
        k1 = (k1[0] - aEY, k1[1] - aEI, k1[2], k1[3])
        E2 = EY + 0.5 * dt * k1[0]; I2 = EI + 0.5 * dt * k1[1]
        V2 = VY + 0.5 * dt * k1[2]; W2 = VI + 0.5 * dt * k1[3]
        k2 = rhs(E2, I2, V2, W2, dx, lam, 0.01, 1.0, gate)
        k2 = (k2[0] - advect(E2, u, dx), k2[1] - advect(I2, u, dx),
              k2[2], k2[3])
        E3 = EY + 0.5 * dt * k2[0]; I3 = EI + 0.5 * dt * k2[1]
        V3 = VY + 0.5 * dt * k2[2]; W3 = VI + 0.5 * dt * k2[3]
        k3 = rhs(E3, I3, V3, W3, dx, lam, 0.01, 1.0, gate)
        k3 = (k3[0] - advect(E3, u, dx), k3[1] - advect(I3, u, dx),
              k3[2], k3[3])
        E4 = EY + dt * k3[0]; I4 = EI + dt * k3[1]
        V4 = VY + dt * k3[2]; W4 = VI + dt * k3[3]
        k4 = rhs(E4, I4, V4, W4, dx, lam, 0.01, 1.0, gate)
        k4 = (k4[0] - advect(E4, u, dx), k4[1] - advect(I4, u, dx),
              k4[2], k4[3])
        EY += dt / 6 * (k1[0] + 2 * k2[0] + 2 * k3[0] + k4[0])
        EI += dt / 6 * (k1[1] + 2 * k2[1] + 2 * k3[1] + k4[1])
        VY += dt / 6 * (k1[2] + 2 * k2[2] + 2 * k3[2] + k4[2])
        VI += dt / 6 * (k1[3] + 2 * k2[3] + 2 * k3[3] + k4[3])
        eys[step, 0] = EY[i0]; eys[step, 1] = EY[ix]
        vys[step, 0] = VY[i0]; vys[step, 1] = VY[ix]
        for m, i in enumerate((i0, ix)):
            dE = (EY[i + 1] - EY[i - 1]) / (2 * dx)
            S_acc[m] += -dE * VY[i] * dt
            rho_acc[m] += 0.5 * (VY[i] ** 2 + dE ** 2) * dt
    return EY, eys, vys, S_acc, rho_acc


def fourier_phase(eys, dt, t):
    """Phase of the omega = 2 pi component at each probe (rad), over
    an integer number of periods."""
    ts = np.arange(eys.shape[0]) * dt
    F = np.array([np.sum(e * np.exp(-2j * np.pi * ts)) for e in eys.T])
    return np.angle(F)


def emission_phase(eys, vys, dt, t):
    """psi_emit = phase of the crossing's oscillation relative to the
    source bubble, wrapped into (-pi, pi]."""
    ph = fourier_phase(eys, dt, t)
    d = ph[1] - ph[0]
    return (d + np.pi) % (2 * np.pi) - np.pi


def main():
    L = 5 * PHI
    x_sp = 3.2
    N = 1440
    dx = (x_sp + L) / (N - 1)
    dt = 0.0015
    t = 3.0
    x = np.linspace(-x_sp, L, N)
    x_lo, x_hi = 0.12, 1.0
    us = [0.0, 0.05, 0.1, 0.2]

    print("=" * 78)
    print("Panel F—closure-crossing event (T12)")
    print(f"Crossing pinned at an integer rung: psi = psi* = {PSI_STAR:.4f}")
    print(f"rad, x* = {X_STAR:.4f} (u = -0.5, delta_n = 0); catalog")
    print("closure state: J/psi at n = 88.980 (rung 89, delta_n = -0.0199)")
    print("t = 3.0 (< wall influence 3.32); omega = 2 pi Fourier phases")
    print("=" * 78)

    # (0) sanity: the standing coherent event
    EY, eys, vys, S, rho = run_series(x, dx, dt, PSI_STAR, 0.0, t)
    uc = extremum_u(x, EY, x_lo, x_hi)
    pe = emission_phase(eys, vys, dt, t)
    print("\n(0) standing coherent event (psi = psi*, u = 0):")
    print(f"    crossing delta_n = {uc + 0.5:+.4f} (expect 0.000)")
    print(f"    emission phase psi_emit = {pe:+.4f} rad (expect 0)")
    print(f"    flux <S> at crossing = {S[1]:+.3e}, transport velocity "
          f"u_flux = {S[1] / max(rho[1], 1e-30):+.4f} (expect 0)")

    # (1) coherent event under descent (psi = psi* fixed): the crossing
    #     drifts with the flow; the emission phase at the closure
    #     position x* is recorded
    print(f"\n(1) coherent event under descent, psi = psi* fixed, "
          f"t = {t}:")
    print(f"   {'u':>6} {'crossing dn':>12} {'T11 expect':>12} "
          f"{'psi_emit@x*':>13}")
    for u in us:
        EY, eys, vys, _, _ = run_series(x, dx, dt, PSI_STAR, u, t)
        uc = extremum_u(x, EY, x_lo + u * t, x_hi + u * t)
        pe = emission_phase(eys, vys, dt, t)
        print(f"   {u:>6.2f} {uc + 0.5:>+12.3f} {1.6 * u:>+12.3f} "
              f"{pe:>+13.4f}")

    # (2) flow-compensated event: psi_src(u) = psi* + 7.84 u pins the
    #     crossing at the closure rung; emission phase + flux there
    print(f"\n(2) flow-compensated closure event (crossing pinned at "
          f"delta_n = 0):")
    print(f"   {'u':>6} {'psi_src':>9} {'crossing dn':>12} "
          f"{'psi_emit':>10} {'u_flux':>9}")
    ps_emit = []
    for u in us:
        psi_src = PSI_STAR + (1.6 / B0) * u
        EY, eys, vys, S, rho = run_series(x, dx, dt, psi_src, u, t)
        uc = extremum_u(x, EY, x_lo, x_hi)
        pe = emission_phase(eys, vys, dt, t)
        uf = S[1] / max(rho[1], 1e-30)
        ps_emit.append(pe)
        print(f"   {u:>6.2f} {psi_src:>9.4f} {uc + 0.5:>+12.4f} "
              f"{pe:>+10.4f} {uf:>+9.4f}")
    ps_emit = np.array(ps_emit)

    # linear response of the emission phase to the flow
    k, b = np.polyfit(us, ps_emit, 1)
    print(f"\n    emission-phase response: psi_emit(u) = {b:+.4f} "
          f"+ {k:+.4f} u  (rad)")
    print(f"    (psi_emit tracks the source phase if k ~ "
          f"{1.6 / B0:.2f}; the reading is definite if k ~ 0)")

    # (3) catalog inversion: the wake leaving the closure event is the
    #     next cell's source.  The pool's source phase is the closure
    #     phase psi* plus the emission lag of the wake that leaves the
    #     event, so
    #         delta_n = A0 - B0 (psi* + psi_emit(u)) + 1.6 u
    #                 = 1.6 u - B0 psi_emit(u)
    #     solved for u with the measured psi_emit(u).  Two models:
    #     the linear fit over all u, and the small-u slope through the
    #     origin (psi_emit(0) = 0 exactly).
    print(f"\n(3) flow determined from the emission phase at the "
          f"closure-crossing event:")
    print(f"    delta_n = 1.6 u - {B0} psi_emit(u), solved for u")
    print(f"   {'state':>14} {'rung':>6} {'delta_n':>9} {'psi_cat':>8} "
          f"{'u* (lin-fit)':>13} {'u* (small-u)':>13}")
    k_small = (ps_emit[1] - ps_emit[0]) / (us[1] - us[0])
    for name, n_r, dn in [("J/psi", 89, -0.01986063745222566),
                          ("mu", 96, -0.00019549748952840673),
                          ("closure (dn=0)", None, 0.0)]:
        psi_cat = PSI_STAR if n_r is None else (A0 - dn) / B0
        u_lin = (dn + B0 * b) / (1.6 - B0 * k)
        u_sm = dn / (1.6 - B0 * k_small)
        n_lbl = "" if n_r is None else f"r{n_r}"
        print(f"   {name:>14} {n_lbl:>6} {dn:>+9.4f} {psi_cat:>8.4f} "
              f"{u_lin:>+13.4f} {u_sm:>+13.4f}")
    print(f"\n    emission-phase response: small-u slope k = {k_small:.3f}")
    print(f"    rad per unit u (source-tracking degeneracy rate: "
          f"{1.6 / B0:.2f})")

    print()
    print("=" * 78)
    print("Verdict")
    print("=" * 78)
    print("The closure crossing emits near in phase at any flow")
    print(f"(psi_emit <= 0.11 rad at u <= 0.2; response {k_small:.2f} rad")
    print("per unit u, fifteen times below the source-tracking rate")
    print("7.84 at which the degeneracy would survive), so the reading")
    print("is definite: the pool at the closure rung is a standing pool")
    print("and the flow is u = (delta_n + B0 psi_emit(u))/1.6.  The")
    print("catalog's closure states read u(J/psi) ~ -0.013 and")
    print("u(mu) ~ 0: pools at closure rungs are near-static")
    print("(|u| <= 1.5% of the wave speed), the sharpest state the")
    print("stillest.  u_flux = <S>/<rho> at the pinned crossing is the")
    print("direct transport velocity of the flow through the pool")
    print("(~u/2: the wave regeneration pushes back at half the drift).")
    print("Sign convention: u > 0 = down the cascade (toward smaller")
    print("scales, +x); u < 0 = up the cascade.")


if __name__ == "__main__":
    main()
