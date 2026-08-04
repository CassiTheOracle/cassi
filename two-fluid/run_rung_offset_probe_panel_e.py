"""Rung-offset probe, Panel E: descent flow — does the energy pool move?

Run:  python two-fluid/run_rung_offset_probe_panel_e.py

Tests the descent picture (`foundations/rung-offset-mechanism.md` §5
T11): gravity as gradient descent down the spiral — the energy flows
down the cascade and pools where it deposits.  A slow initial velocity
does NOT produce a slow drift (the wave equation has one speed c = 1;
(E0, -v E0') splits into fast movers), so the descent must be modeled
as explicit advection of the two-fluid state:

    dE/dt = V - u dE/dx,   dV/dt = c^2 lap(E) - gamma V + conv

with u the descent speed (u = 0 restores the T1 standing probe).
Questions:

  (a) the advection transports the pattern: the crossing at fixed t
      moves by u t (sanity);
  (b) the pooled energy deposit D(x) = int(|EY|^2 - |EY(0)|^2): does
      its peak move away from the standing crossing as u grows?
  (c) the gated conversion deposit int (1-q) eps dt: peak vs u;
  (d) the deposit profile's asymmetry (skew) — the descent's genuine
      pattern-relative effect — peak vs centroid;
  (e) at finite phase psi, the deposit peak vs the standing curve.

If the deposit peak is u-independent in the pattern frame, the descent
carries the pattern but does not position the pool: delta_n is set by
the phase alone.  If the peak shifts with u, the descent is a new dial
and the catalog offsets can read as per-rung descent speeds.
"""

import numpy as np
from run_rung_offset_probe import PHI, LNPHI, rhs, extremum_u, u_of

AMP = 0.32
PHI_INV2 = PHI ** -2


def gate_openness(EY, EI):
    M_qi = (EY + EI) ** 2
    eps_sq = (EY - PHI * EI) ** 2
    return (PHI_INV2 + eps_sq) / (M_qi + PHI_INV2 + eps_sq + 1e-30)


def envelope(x, f, psi):
    return 1 + AMP * (np.cos(2 * np.pi * x)
                      + f * np.cos(2 * np.pi * (x - PHI) + psi))


def advect(E, u, dx):
    """Upwind advection (u > 0: drift to +x), first order."""
    dE = np.empty_like(E)
    dE[1:] = (E[1:] - E[:-1]) / dx
    dE[0] = 0.0
    return u * dE


def run(x, dx, dt, f, psi, lam, u, t, gate=False, n_rec_steps=None):
    EY = envelope(x, f, psi)
    EI = 1 + AMP * (np.cos(2 * np.pi * PHI * x)
                    + f * np.cos(2 * np.pi * PHI * (x - PHI) + psi))
    VY = np.zeros_like(x)
    VI = np.zeros_like(x)
    n_steps = int(round(t / dt))
    rec = n_rec_steps or 0
    E2rec = np.zeros_like(x)
    convrec = np.zeros_like(x)
    for step in range(n_steps):
        aEY = advect(EY, u, dx)
        aEI = advect(EI, u, dx)
        k1 = rhs(EY, EI, VY, VI, dx, lam, 0.01, 1.0, gate)
        k1 = (k1[0] - aEY, k1[1] - aEI, k1[2], k1[3])
        E2 = EY + 0.5*dt*k1[0]; I2 = EI + 0.5*dt*k1[1]
        V2 = VY + 0.5*dt*k1[2]; W2 = VI + 0.5*dt*k1[3]
        k2 = rhs(E2, I2, V2, W2, dx, lam, 0.01, 1.0, gate)
        k2 = (k2[0] - advect(E2, u, dx), k2[1] - advect(I2, u, dx),
              k2[2], k2[3])
        E3 = EY + 0.5*dt*k2[0]; I3 = EI + 0.5*dt*k2[1]
        V3 = VY + 0.5*dt*k2[2]; W3 = VI + 0.5*dt*k2[3]
        k3 = rhs(E3, I3, V3, W3, dx, lam, 0.01, 1.0, gate)
        k3 = (k3[0] - advect(E3, u, dx), k3[1] - advect(I3, u, dx),
              k3[2], k3[3])
        E4 = EY + dt*k3[0]; I4 = EI + dt*k3[1]
        V4 = VY + dt*k3[2]; W4 = VI + dt*k3[3]
        k4 = rhs(E4, I4, V4, W4, dx, lam, 0.01, 1.0, gate)
        k4 = (k4[0] - advect(E4, u, dx), k4[1] - advect(I4, u, dx),
              k4[2], k4[3])
        EY += dt/6 * (k1[0] + 2*k2[0] + 2*k3[0] + k4[0])
        EI += dt/6 * (k1[1] + 2*k2[1] + 2*k3[1] + k4[1])
        VY += dt/6 * (k1[2] + 2*k2[2] + 2*k3[2] + k4[2])
        VI += dt/6 * (k1[3] + 2*k2[3] + 2*k3[3] + k4[3])
        if step >= n_steps - rec:
            E2rec += EY ** 2 * dt
            convrec += gate_openness(EY, EI) * (EY - PHI * EI) * dt
    return EY, E2rec, convrec


def peak_pos(x, prof, x_lo, x_hi):
    """Position (delta_n) of the |profile| extremum in the window."""
    a = np.abs(prof)
    m = np.argmax(np.where((x >= x_lo) & (x <= x_hi), a, -np.inf))
    y0, y1, y2 = a[m-1], a[m], a[m+1]
    denom = y0 - 2*y1 + y2
    if abs(denom) < 1e-14:
        return u_of(x[m]) + 0.5
    dx = x[1] - x[0]
    xm = np.clip(x[m] + 0.5 * dx * (y0 - y2) / denom, x_lo, x_hi)
    return u_of(xm) + 0.5


def main():
    L = 5 * PHI
    x_sp = 3.2
    N = 1440
    dx = (x_sp + L) / (N - 1)
    dt = 0.0015
    t = 3.0
    x = np.linspace(-x_sp, L, N)
    x_lo, x_hi = 0.12, 1.0
    m_win = (x >= x_lo) & (x <= x_hi)

    print("=" * 78)
    print("Panel E — descent flow (advection speed u): does the pool")
    print("move with the gradient flow?  dE/dt = V - u dE/dx;")
    print(f"u = 0 restores the standing probe; t = {t} (< wall "
          f"influence {x_sp + x_lo:.2f})")
    print("=" * 78)

    # (0) sanity: advection transports the pattern (following window)
    print("\n(0) pattern transport at fixed t = 3, lambda = 0")
    print("    (window follows the drift; expected crossing +u t):")
    print(f"   {'u':>6} {'crossing':>10} {'expected':>10}")
    for u in [0.0, 0.05, 0.1, 0.2]:
        EY, _, _ = run(x, dx, dt, 1.0, 0.0, 0.0, u, t)
        uc = extremum_u(x, EY, x_lo + u * t, x_hi + u * t)
        exp = u_of(0.809 + u * t)
        print(f"   {u:>6.2f} {uc:>+10.3f} {exp:>+10.3f}")

    # A uniformly drifting pattern deposits as a box-convolution of its
    # local profile: the deposit peak sits at the MID-DRIFT position,
    # x = 0.809 + u t/2 (symmetric local profile).  The descent
    # positions the pool iff the measured peak deviates from that.
    exp_peak = lambda u: u_of(0.809 + u * t / 2) + 0.5

    # (1) energy deposit peak vs u (psi = 0)
    print(f"\n(1) energy deposit D(x) = int(|EY|^2 - |EY(0)|^2), "
          f"t in [0, {t}], lambda = 0, psi = 0:")
    print(f"   {'u':>6} {'deposit peak':>13} {'mid-drift exp':>14} "
          f"{'pattern-rel':>12}")
    for u in [0.0, 0.05, 0.1, 0.2]:
        _, E2rec, _ = run(x, dx, dt, 1.0, 0.0, 0.0, u, t,
                          n_rec_steps=int(round(t / dt)))
        D = E2rec - (envelope(x, 1.0, 0.0) ** 2) * t
        pk = peak_pos(x, D, x_lo, x_hi + u * t)
        exp = exp_peak(u)
        print(f"   {u:>6.2f} {pk:>+13.3f} {exp:>+14.3f} "
              f"{pk - exp:>+12.3f}")

    # (2) gated conversion deposit peak vs u (psi = 0)
    print(f"\n(2) gated conversion deposit int (1-q) eps dt, "
          f"lambda = 0.3, psi = 0:")
    print(f"   {'u':>6} {'deposit peak':>13} {'mid-drift exp':>14} "
          f"{'pattern-rel':>12}")
    for u in [0.0, 0.05, 0.1, 0.2]:
        _, _, convrec = run(x, dx, dt, 1.0, 0.0, 0.3, u, t, gate=True,
                            n_rec_steps=int(round(t / dt)))
        pk = peak_pos(x, convrec, x_lo, x_hi + u * t)
        exp = exp_peak(u)
        print(f"   {u:>6.2f} {pk:>+13.3f} {exp:>+14.3f} "
              f"{pk - exp:>+12.3f}")

    # (3) descent + finite phase
    print(f"\n(3) gated conversion deposit, lambda = 0.3, psi = 0.4:")
    print(f"   {'u':>6} {'deposit peak':>13} {'mid-drift exp':>14} "
          f"{'pattern-rel':>12}")
    for u in [0.0, 0.05, 0.1, 0.2]:
        _, _, convrec = run(x, dx, dt, 1.0, 0.4, 0.3, u, t, gate=True,
                            n_rec_steps=int(round(t / dt)))
        pk = peak_pos(x, convrec, x_lo, x_hi + u * t)
        # mid-drift position of the psi = 0.4 crossing: 0.809 - psi/4pi
        x0 = 0.809 - 0.4 / (4 * np.pi)
        exp = u_of(x0 + u * t / 2) + 0.5
        lin = 0.060 - 0.204 * 0.4
        print(f"   {u:>6.2f} {pk:>+13.3f} {exp:>+14.3f} "
              f"{pk - exp:>+12.3f}  (standing curve {lin:+.3f})")

    print()
    print("=" * 78)
    print("Verdict")
    print("=" * 78)
    print("If the deposit peaks are u-independent, the descent carries")
    print("the pattern but does not position the pool: delta_n is set by")
    print("the phase alone and the descent reading is empty. If they")
    print("drift with u, the descent is a new dial for delta_n.")


if __name__ == "__main__":
    main()
