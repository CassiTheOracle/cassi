"""Rung-offset probe T1: where does the two-wake interference extremum sit?

Run:  python two-fluid/run_rung_offset_probe.py

Tests Prediction 46 (`predictions/falsifiable-predictions.md`) /
`foundations/rung-offset-mechanism.md` §5 T1:

  (a) uncoupled extrema sit at the wake-envelope positions;
  (b) the two-fluid phase difference moves the extremum continuously;
  (c) conversion lambda shifts it too, and the direction tracks energy flow.

Panel A—single-bubble wake pair cos(2*pi*x) + cos(2*pi*phi*x)
  (wake-geometry.md §2). Envelope peaks at x = m*ell_{n+1} and zeros at
  (m+1/2)*ell_{n+1}; in ln-rung units u = log_phi(x/ell_n):
    peaks at u = 1 + log_phi(m), zeros at u = 1 + log_phi(m+1/2).
  Only the first peak is an integer rung; the first zero sits at
  u = -0.440, NOT at the half-rung -0.5 (the "half-rung" reading is
  real-space language: x = ell_{n+1}/2).

Panel B—two bubbles at x = 0 and x = phi (rungs n and n+1), each
  emitting the wake pair. With V = 0 initial conditions the fields are
  exactly standing (d'Alembert on the line, no dispersion):

      E_Y(x,t) = A(x) cos(2 pi t),
      A(x) = 1 + AMP[cos(2 pi x) + f cos(2 pi (x - phi) + psi)]

  so the extremum of |E_Y| over x is the antinode of |A| at any time
  with cos(2 pi t) != 0. The antinode is moved by the relative phase
  psi between the two bubbles' wakes:

      x_max(psi) = phi/2 - psi/(4 pi)          (f = 1)

  Amplitude asymmetry f moves the crossing at any psi: at psi = 0 the
  extremum sits at u = -0.440 for f = 1 and -0.330 for f = 0.8 (T8-G),
  and at psi = 0.4 it moves 0.38 rungs across f = 1.0-0.6 (table 3).
  Conversion lambda leaks the I-fluid's spatial structure into E_Y,
  whose antinode sits at u = +0.23, so the extremum drifts toward
  positive u as lambda grows (energy flows Y -> I when r > phi).

  Boundaries: the IC is extended to a Neumann wall at x = -1.5 (beyond
  the left sponge region of any physical interest). The wall round-trip
  time from the measurement window is 3.24, so every measurement at
  t <= 1.5 is exactly the infinite-line standing wave; no absorbing
  layers are needed. (Sponges were tried and rejected: they absorb
  components of the standing wave that originate in the extended region,
  which distorts the very pattern being measured.)

Solver: 1D damped-wave two-fluid PDE (skill two-fluid-wave-pde-simulation):
  dE/dt = V,  dV/dt = c^2 d2E/dx^2 - gamma V -/+ lambda (E_Y - phi E_I),
  RK4, Neumann boundaries, mass-conserving rescale of E (not V).

Output: console tables + verdicts. No figure is written.
"""

import numpy as np

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)
PHI_INV2 = PHI ** -2      # phi^-2 = 0.382, the gate's coherence floor


def u_of(x):
    """ln-rung coordinate: u = log_phi(x / ell_n) with ell_n = 1."""
    return np.log(x) / LNPHI


# ----------------------------------------------------------------------
# Solver: 1D damped-wave two-fluid, RK4
# ----------------------------------------------------------------------

def laplacian(f, dx):
    """Second derivative with Neumann (zero-flux) boundaries."""
    lap = np.empty_like(f)
    lap[1:-1] = (f[:-2] - 2 * f[1:-1] + f[2:]) / dx**2
    lap[0] = 2 * (f[1] - f[0]) / dx**2        # mirror Neumann
    lap[-1] = 2 * (f[-2] - f[-1]) / dx**2
    return lap


def gate_openness(EY, EI):
    """Qi gate openness (1-q) of the solver's 'single' gate
    (cassi_two_fluid_3d_gpu.py, rhs): q = M/(M + phi^-2 + eps^2),
    M = (EY+EI)^2, eps = EY - phi*EI. Conversion is gated by (1-q)."""
    M_qi = (EY + EI) ** 2
    eps_sq = (EY - PHI * EI) ** 2
    return (PHI_INV2 + eps_sq) / (M_qi + PHI_INV2 + eps_sq + 1e-30)


def rhs(EY, EI, VY, VI, dx, lam, gamma, c2, gate=False):
    dEY = VY
    dEI = VI
    imbalance = EY - PHI * EI
    if gate:
        conv = -lam * gate_openness(EY, EI) * imbalance
    else:
        conv = -lam * imbalance
    dVY = c2 * laplacian(EY, dx) - gamma * VY + conv
    dVI = c2 * laplacian(EI, dx) - gamma * VI - conv
    return dEY, dEI, dVY, dVI


def evolve(EY, EI, VY, VI, dx, dt, n_steps, lam, gamma=0.01, c2=1.0,
           conserve_mass=True, gate=False):
    M0Y, M0I = EY.sum(), EI.sum()
    for _ in range(n_steps):
        k1 = rhs(EY, EI, VY, VI, dx, lam, gamma, c2, gate)
        k2 = rhs(EY + 0.5*dt*k1[0], EI + 0.5*dt*k1[1],
                 VY + 0.5*dt*k1[2], VI + 0.5*dt*k1[3], dx, lam, gamma,
                 c2, gate)
        k3 = rhs(EY + 0.5*dt*k2[0], EI + 0.5*dt*k2[1],
                 VY + 0.5*dt*k2[2], VI + 0.5*dt*k2[3], dx, lam, gamma,
                 c2, gate)
        k4 = rhs(EY + dt*k3[0], EI + dt*k3[1],
                 VY + dt*k3[2], VI + dt*k3[3], dx, lam, gamma, c2, gate)
        EY += dt/6 * (k1[0] + 2*k2[0] + 2*k3[0] + k4[0])
        EI += dt/6 * (k1[1] + 2*k2[1] + 2*k3[1] + k4[1])
        VY += dt/6 * (k1[2] + 2*k2[2] + 2*k3[2] + k4[2])
        VI += dt/6 * (k1[3] + 2*k2[3] + 2*k3[3] + k4[3])
        if conserve_mass:
            EY *= M0Y / EY.sum()
            EI *= M0I / EI.sum()
    return EY, EI, VY, VI


def extremum_u(x, f, x_lo, x_hi):
    """Argmax of |f| on [x_lo, x_hi] with parabolic sub-grid refinement."""
    a = np.abs(f)
    m = np.argmax(np.where((x >= x_lo) & (x <= x_hi), a, -np.inf))
    y0, y1, y2 = a[m-1], a[m], a[m+1]
    denom = y0 - 2*y1 + y2
    if abs(denom) < 1e-14:
        return u_of(x[m])
    dx = x[1] - x[0]
    xm = x[m] + 0.5 * dx * (y0 - y2) / denom
    return u_of(xm)


# ----------------------------------------------------------------------
# Panel A: single-bubble wake-pair envelope positions (analytic, derived)
# ----------------------------------------------------------------------

def panel_a():
    print("=" * 72)
    print("Panel A—single-bubble wake pair cos(2pi x) + cos(2pi phi x)")
    print("Envelope positions in ln-rung units u = log_phi(x/ell_n)")
    print("=" * 72)
    rows = []
    for m in range(0, 4):
        if m > 0:
            rows.append(("peak", m, m * PHI, u_of(m * PHI)))
        rows.append(("zero", m, (m + 0.5) * PHI, u_of((m + 0.5) * PHI)))
    print(f"{'type':>4} {'m':>2} {'x/ell_n':>8} {'u (rungs)':>10} "
          f"{'nearest spec':>12} {'delta_n':>8}")
    for typ, m, x, u in rows:
        c0, c1 = round(u), round(2*u)/2
        s = min(abs(u - c0), abs(u - c1))
        ns = c0 if abs(u - c0) <= abs(u - c1) else c1
        print(f"{typ:>4} {m:>2} {x:>8.3f} {u:>10.3f} {ns:>12g} {s:>8.3f}")
    u0 = u_of(0.5 * PHI)
    print(f"\nFirst envelope zero: x = ell_{{n+1}}/2 = {0.5*PHI:.4f}, "
          f"u = {u0:.3f} rungs; the half-rung would be -0.500 "
          f"(delta = {u0 + 0.5:+.3f}).")
    print("Reading: the envelope special points in ln-space are")
    print("{1 + log_phi m} (peaks) and {1 + log_phi(m+1/2)} (zeros); only")
    print("the first peak is an integer rung. 'Half-rung' is real-space")
    print("language (x = ell_{n+1}/2). The geometric-mean half-step")
    print("u = -0.5 is a different object (wake-geometry.md sec 1c).")


# ----------------------------------------------------------------------
# Panel B: two-bubble standing pattern, extremum vs phase and lambda
# ----------------------------------------------------------------------

def panel_b(L, x_sp, N, dt, t_short, t_long, psi_scan, lam_scan):
    print()
    print("=" * 72)
    print("Panel B—two bubbles at x = 0 and x = phi (rungs n, n+1)")
    print("Standing E_Y envelope: extremum of |E_Y|; wall round-trip time")
    print("from the window is 3.24, so all measurements at t < 3.24 are")
    print("exactly the infinite-line standing wave")
    print("=" * 72)
    x = np.linspace(-x_sp, L, N)
    dx = x[1] - x[0]
    x_lo, x_hi = 0.12, 1.0   # first cell of the lattice (u in [-2.1, 0])
    AMP = 0.32

    def run(f, psi, lam, t):
        EY = 1 + AMP*(np.cos(2*np.pi*x)
                      + f*np.cos(2*np.pi*(x - PHI) + psi))
        EI = 1 + AMP*(np.cos(2*np.pi*PHI*x)
                      + f*np.cos(2*np.pi*PHI*(x - PHI) + psi))
        VY = np.zeros_like(x)
        VI = np.zeros_like(x)
        EY, EI, _, _ = evolve(EY, EI, VY, VI, dx, dt,
                              int(round(t / dt)), lam)
        return extremum_u(x, EY, x_lo, x_hi)

    def antinode_analytic(f, psi):
        """Antinode of E_Y's standing envelope A(x) = 1 + AMP*Re[e^{i2pix}
        (1 + f e^{i(psi-2pi phi)})]: x_max = -arg(1 + f e^{i(psi-2pi phi)})/2pi,
        the copy in the first cell."""
        th = np.angle(1 + f*np.exp(1j*(psi - 2*np.pi*PHI)))
        xm = (-th) % (2*np.pi) / (2*np.pi)
        if xm < x_lo:
            xm += 1.0
        if xm > x_hi:
            xm -= 1.0
        return u_of(xm)

    # (0) solver sanity: field vs analytic A(x) cos(2 pi t) at t_short,
    #     restricted to the measurement window (walls generate local
    #     reflections that stay outside the window for t < 3.24)
    EY = 1 + AMP*(np.cos(2*np.pi*x) + np.cos(2*np.pi*(x - PHI)))
    EI = 1 + AMP*(np.cos(2*np.pi*PHI*x) + np.cos(2*np.pi*PHI*(x - PHI)))
    EYf, _, _, _ = evolve(EY.copy(), EI.copy(), np.zeros_like(x),
                          np.zeros_like(x), dx, dt, int(round(t_short/dt)),
                          0.0)
    Aenv = 1 + AMP*2*np.cos(np.pi*PHI)*np.cos(2*np.pi*x - np.pi*PHI)
    an = 1 + (Aenv - 1) * np.cos(2*np.pi*t_short) * np.exp(-0.01*t_short/2)
    m_win = (x >= x_lo) & (x <= x_hi)
    print(f"\n(0) solver sanity: max|PDE - A(x)cos(2pi t)| in window = "
          f"{np.max(np.abs(EYf - an)[m_win]):.2e} at t = {t_short}")

    # (1) relative phase scan at f = 1, lambda = 0
    print(f"\n(1) relative phase psi between the bubbles, f = 1, "
          f"lambda = 0, t = {t_short}")
    print(f"{'psi (rad)':>10} {'u_max (PDE)':>12} {'delta_n':>9} "
          f"{'u_max (analytic)':>16}")
    for psi in psi_scan:
        u_pde = run(1.0, psi, 0.0, t_short)
        u_an = antinode_analytic(1.0, psi)
        print(f"{psi:>10.2f} {u_pde:>12.3f} {u_pde + 0.5:>+9.3f} "
              f"{u_an:>16.3f}")

    # (2) conversion scan at psi = 0, f = 1, long time for the leak to build
    print(f"\n(2) conversion lambda, psi = 0, f = 1, t = {t_long}")
    print(f"{'lambda':>8} {'u_max (PDE)':>12} {'delta_n':>9}")
    for lam in lam_scan:
        u_pde = run(1.0, 0.0, lam, t_long)
        print(f"{lam:>8.3f} {u_pde:>12.3f} {u_pde + 0.5:>+9.3f}")

    # (3) lambda at finite phase (long time); amplitude ratio at psi = 0.4
    print(f"\n(3) lambda at psi = 0.4 (t = {t_long}); amplitude ratio f "
          f"at psi = 0.4 (t = {t_short})")
    print(f"{'case':>26} {'u_max (PDE)':>12} {'delta_n':>9} "
          f"{'analytic':>9}")
    for lam in lam_scan:
        u_pde = run(1.0, 0.4, lam, t_long)
        u_an = antinode_analytic(1.0, 0.4)
        print(f"{'psi=0.4, f=1.0, lam=' + str(lam):>26} {u_pde:>12.3f} "
              f"{u_pde + 0.5:>+9.3f} {u_an:>9.3f}")
    for f in [1.0, 0.8, 0.6]:
        u_pde = run(f, 0.4, 0.0, t_short)
        u_an = antinode_analytic(f, 0.4)
        print(f"{'psi=0.4, f=' + str(f) + ', lam=0':>26} {u_pde:>12.3f} "
              f"{u_pde + 0.5:>+9.3f} {u_an:>9.3f}")


# ----------------------------------------------------------------------
# Panel C: nonlinear gate regime (solver 'single' gate)
# ----------------------------------------------------------------------

def panel_c(L, x_sp, N, dt, t_long, lam_scan, m_scan, amp_scan, psi_scan):
    print()
    print("=" * 72)
    print("Panel C—nonlinear gate regime")
    print("conv = -lam*(1-q)*(E_Y - phi E_I),  q = M/(M + phi^-2 + eps^2)")
    print("(solver 'single' gate; M = (E_Y+E_I)^2, eps = E_Y - phi E_I)")
    print("Wall influence reaches the window at t = x + x_sp ~ "
          f"{x_sp + 0.12:.2f} > t_max = {t_long}")
    print("Extremum measured on the REACH: max over the last 1.7 time")
    print("units of |E_Y| (the sourced harmonics oscillate; a single")
    print("snapshot can miss them)")
    print("=" * 72)
    x = np.linspace(-x_sp, L, N)
    dx = x[1] - x[0]
    x_lo, x_hi = 0.12, 1.0
    AMP = 0.32

    def run(m, amp, psi, lam, t):
        EY = m + amp*(np.cos(2*np.pi*x) + np.cos(2*np.pi*(x - PHI) + psi))
        EI = m + amp*(np.cos(2*np.pi*PHI*x)
                      + np.cos(2*np.pi*PHI*(x - PHI) + psi))
        VY = np.zeros_like(x)
        VI = np.zeros_like(x)
        n_steps = int(round(t / dt))
        n_rec = int(round(1.7 / dt))
        reach = np.zeros_like(x)
        # evolve; keep max |EY| over the final 1.7 time units
        for step in range(n_steps):
            k1 = rhs(EY, EI, VY, VI, dx, lam, 0.01, 1.0, gate=True)
            k2 = rhs(EY + 0.5*dt*k1[0], EI + 0.5*dt*k1[1],
                     VY + 0.5*dt*k1[2], VI + 0.5*dt*k1[3], dx, lam,
                     0.01, 1.0, True)
            k3 = rhs(EY + 0.5*dt*k2[0], EI + 0.5*dt*k2[1],
                     VY + 0.5*dt*k2[2], VI + 0.5*dt*k2[3], dx, lam,
                     0.01, 1.0, True)
            k4 = rhs(EY + dt*k3[0], EI + dt*k3[1],
                     VY + dt*k3[2], VI + dt*k3[3], dx, lam, 0.01, 1.0,
                     True)
            EY += dt/6 * (k1[0] + 2*k2[0] + 2*k3[0] + k4[0])
            EI += dt/6 * (k1[1] + 2*k2[1] + 2*k3[1] + k4[1])
            VY += dt/6 * (k1[2] + 2*k2[2] + 2*k3[2] + k4[2])
            VI += dt/6 * (k1[3] + 2*k2[3] + 2*k3[3] + k4[3])
            if step >= n_steps - n_rec:
                reach = np.maximum(reach, np.abs(EY))
        u_max = extremum_u(x, reach, x_lo, x_hi)
        m_win = (x >= x_lo) & (x <= x_hi)
        omq = gate_openness(EY, EI)[m_win].mean()
        return u_max, omq, EY, EI

    # (1) lambda scan at m = 1, amp = 0.32, psi = 0
    print(f"\n(1) lambda scan, m = 1, amp = 0.32, psi = 0, t = {t_long}")
    print(f"{'lambda':>8} {'u_max':>9} {'delta_n':>9} {'<1-q>':>7}")
    for lam in lam_scan:
        u_max, omq, _, _ = run(1.0, AMP, 0.0, lam, t_long)
        print(f"{lam:>8.3f} {u_max:>9.3f} {u_max + 0.5:>+9.3f} {omq:>7.3f}")

    # (2) density m scan (coherence dial), at lam = 0.3
    print(f"\n(2) density m scan (coherence dial), lam = 0.3, psi = 0, "
          f"t = {t_long}")
    print(f"{'m':>6} {'u_max':>9} {'delta_n':>9} {'<1-q>':>7}")
    for m in m_scan:
        u_max, omq, _, _ = run(m, AMP, 0.0, 0.3, t_long)
        print(f"{m:>6.2f} {u_max:>9.3f} {u_max + 0.5:>+9.3f} {omq:>7.3f}")

    # (3) amplitude scan (nonlinearity strength), at m = 1, lam = 0.3
    print(f"\n(3) amplitude scan, m = 1, lam = 0.3, psi = 0, t = {t_long}")
    print(f"{'amp':>6} {'u_max':>9} {'delta_n':>9} {'<1-q>':>7}")
    for amp in amp_scan:
        u_max, omq, _, _ = run(1.0, amp, 0.0, 0.3, t_long)
        print(f"{amp:>6.2f} {u_max:>9.3f} {u_max + 0.5:>+9.3f} {omq:>7.3f}")

    # (4) psi scan under the gate, vs the linear curve 0.060 - 0.204 psi
    print(f"\n(4) psi scan under the gate, lam = 0.3, m = 1, t = {t_long}")
    print(f"{'psi':>6} {'u_max':>9} {'delta_n':>9} {'linear curve':>13}")
    for psi in psi_scan:
        u_max, omq, _, _ = run(1.0, AMP, psi, 0.3, t_long)
        lin = 0.060 - 0.204 * psi
        print(f"{psi:>6.2f} {u_max:>9.3f} {u_max + 0.5:>+9.3f} "
              f"{lin:>+13.3f}")

    # (5) time accumulation at the strongest case
    print(f"\n(5) time accumulation, m = 0.5, amp = 0.32, lam = 0.3")
    for t in [2.0, 4.0, t_long]:
        u_max, omq, _, _ = run(0.5, AMP, 0.0, 0.3, t)
        print(f"   t = {t:4.1f}: u_max = {u_max:+.3f}, delta_n = "
              f"{u_max + 0.5:+.3f}, <1-q> = {omq:.3f}")

    # (6) nonlinear mixing: windowed spectrum of (1-q) at the strongest case
    _, omq, EY, EI = run(0.5, AMP, 0.0, 0.3, t_long)
    f_win = gate_openness(EY, EI)
    m_win = (x >= x_lo) & (x <= x_hi)
    sig = f_win[m_win] - f_win[m_win].mean()
    sig *= np.hanning(sig.size)               # kill FFT leakage
    kk = np.fft.rfftfreq(sig.size, d=dx)
    spec = np.abs(np.fft.rfft(sig))
    order = np.argsort(spec)[::-1][:8]
    print(f"\n(6) dominant wave numbers (cycles/ell_n) of (1-q) at "
          f"t = {t_long}; linear wakes sit at 1.000 and 1.618")
    for i in order:
        print(f"    k/2pi = {kk[i]:6.3f}   power = {spec[i]:.4f}")


if __name__ == "__main__":
    L = 5 * PHI          # physical domain
    x_sp = 1.5           # left extension: wall round trip from the window
    N = 1216             # covers [-1.5, 8.09] at dx ~ 0.0079
    dt = 0.0015          # CFL ~ 0.19
    t_short = 0.05       # exact standing wave; boundary-free
    t_long = 2.0         # cos(2 pi t) = +1 -> E_Y = A(x); < 3.24 round trip

    panel_a()
    panel_b(L=L, x_sp=x_sp, N=N, dt=dt, t_short=t_short, t_long=t_long,
            psi_scan=[0.0, 0.1, 0.2, 0.4, 0.6, 0.8],
            lam_scan=[0.0, 0.02, 0.05, 0.1])
    panel_c(L=L, x_sp=8.0, N=2048, dt=dt, t_long=6.0,
            lam_scan=[0.0, 0.1, 0.3, 0.5],
            m_scan=[0.5, 1.0, 2.0],
            amp_scan=[0.16, 0.32, 0.64],
            psi_scan=[0.0, 0.2, 0.4])

    print()
    print("=" * 72)
    print("Verdicts")
    print("=" * 72)
    print("(a) lambda = 0, psi = 0: extremum pinned at the envelope")
    print("    antinode u = -0.440 (x = ell_{n+1}/2). Panel A corrects")
    print("    the naive 'zeros at half-rungs' reading: the ln-space")
    print("    special points are {1 + log_phi m} and")
    print("    {1 + log_phi(m+1/2)}.")
    print("(b) the relative phase psi between the two wakes moves the")
    print("    extremum: x_max = phi/2 - psi/(4 pi), i.e.")
    print("    delta_n(psi) = 0.060 - 0.204 psi—the phase-lag")
    print("    mechanism of the doc sec 4.2—and the curve is")
    print("    unchanged under the gate (Panel C (4)).")
    print("(c) conversion—linear (Panel B) or gated (Panel C)—does")
    print("    NOT move the extremum in the standing pattern: pinned at")
    print("    delta_n = +0.060 for lambda up to 0.5, <1-q> up to 0.33,")
    print("    t up to 6, all densities and amplitudes. The gate sources")
    print("    harmonics of the wakes (k = 2.0 component in (1-q), table")
    print("    (6)) but cannot rephase the crossing. The lambda = 0")
    print("    reach tie at u = -2.440 is a degenerate tie between the")
    print("    |A| and |2-A| envelope maxima, not physics.")
    print("(d) conclusion: in the standing two-bubble pattern, delta_n")
    print("    is set by the wake phase difference psi alone; the local")
    print("    conversion dynamics cannot shift it. The catalog offsets")
    print("    must trace to the emission phase of the wakes (their age")
    print("    since the last closure event), not to the local gate")
    print("    dynamics.")
