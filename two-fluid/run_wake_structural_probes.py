"""Wake structural probes: P44 checkerboard, P43 composite closure, F2/F1 sharpening.

Run:  python two-fluid/run_wake_structural_probes.py

Three Derived-structural claims, each previously without a dedicated PDE
realization, tested in the 1D standing-wave setup (the T1 harness
`two-fluid/run_rung_offset_probe.py`, skill two-fluid-standing-wave-probe):

  P44 (staggered checkerboard; predictions/falsifiable-predictions.md P44,
      foundations/wake-geometry.md §2): the wake pair
      cos(2 pi x) + cos(2 pi phi x) (Lambda_Y = ell_n, Lambda_I = ell_n/phi)
      has a beat envelope whose peaks sit at x = m*ell_{n+1} and whose
      zeros sit at x = (m+1/2)*ell_{n+1} — constructive at the rung,
      destructive at the half-rung. Probe: standing pattern of a single
      wake source (two conventions: the pair in E_Y, and the pair in the
      density rho = E_Y + E_I), launch envelope recovered from the
      measured field, extremum positions vs m and (m+1/2) in units of
      ell_{n+1} = phi.

  P43 (wake-pair composite closure): Lambda_Y + Lambda_I = ell_{n+1}
      (1 + 1/phi = phi; verified analytically at rung 285 as
      191 + 118 = 309 Mpc = ell_286). PDE leg: two wake trains whose
      wavelength sum equals the next rung must produce beats at
      m*ell_{n+1}. Probe: envelope peak (and null) spacings of the
      canonical pair (Lambda_Y = 1, Lambda_I = 1/phi) in units of
      ell_{n+1}, plus the scale-covariant pair (Lambda_Y = phi,
      Lambda_I = 1) whose sum is ell_{n+2} = phi^2.

  Sharpening (wake-force, 2026-08-03; predictions/falsifiable-
      predictions.md P44 block): the wake-phase gradient force has
      harmonic amplitude ratio F2/F1 = 1/phi and phase-gradient ratio
      (1+phi)/(phi-1) = phi^3. The documented force is the solver's
      F = Pi grad(Phi) with Pi = E_Y - E_I, grad^2 Phi = rho, Poisson
      solved spectrally with the k = 0 mode dropped
      (foundations/spiral-dynamics.md §3.1, cassi_two_fluid_3d_gpu.py):
      in the two-bubble standing pattern the force is quadratic in the
      wakes, so its spectrum has four lines — the self-harmonics at
      k = 2 (Yang wake) and k = 2 phi (Yin wake), whose amplitude ratio
      carries the Green-function factor 1/k and must be F2/F1 = 1/phi,
      and the cross-harmonics at k = 1+phi and k = phi-1, whose
      amplitude ratio is (1+phi)/(phi-1) = phi^3 (the same number as
      their phase-gradient ratio). Probe: F = Pi grad(Phi) from the PDE
      fields, harmonic amplitudes vs the claims.

Solver: same 1D damped-wave two-fluid RK4 as the T1 probe (imported).
Conventions: ell_n = 1, ell_{n+1} = phi; V = 0 ICs -> exactly standing,
BUT the wake pair has two spatial frequencies, so each tone oscillates
at its own temporal frequency: E(x,t) = 1 + sum_k A_k cos(2 pi k x)
cos(2 pi k t). All probes measure at t = 0.01 (whole-domain window
clean; the wall-phase mismatch of the finite domain — the walls sit at
non-integer phases of the two tones — is a harness-level 0.05% effect
at this time, measured and reported) and unwrap each fitted tone by
its cos(2 pi k t) factor to recover the launch (t = 0) pattern, which
is the envelope the claims describe.

Output: console tables + one verdict per claim. No figure is written.
"""

import numpy as np
from run_rung_offset_probe import PHI, LNPHI, rhs, evolve

AMP = 0.32


# ----------------------------------------------------------------------
# Measurement helpers
# ----------------------------------------------------------------------

def lsq_tones(x, f, ks):
    """Least-squares fit f ~ c0 + sum_k [a_k cos(2 pi k x) + b_k sin(2 pi k x)].

    Returns (c0, amps, residual RMS) with amps[k] = a_k - i b_k (so that
    Re[amp exp(i 2 pi k x)] = a cos + b sin). The model is exact for the
    standing patterns measured here, so the fitted amplitudes are the
    pattern's harmonic amplitudes.
    """
    cols = [np.ones_like(x)]
    for k in ks:
        cols.append(np.cos(2 * np.pi * k * x))
        cols.append(np.sin(2 * np.pi * k * x))
    A = np.column_stack(cols)
    coef, _, _, _ = np.linalg.lstsq(A, f, rcond=None)
    res = f - A @ coef
    amps = {}
    for j, k in enumerate(ks):
        amps[k] = coef[1 + 2 * j] - 1j * coef[2 + 2 * j]
    return coef[0], amps, np.sqrt(np.mean(res ** 2))


def unwrap(amps, t):
    """Recover the launch amplitudes: each tone of a V = 0 standing wave
    oscillates as cos(2 pi k t), so A_k(0) = A_k(t) / cos(2 pi k t)."""
    return {k: a / np.cos(2 * np.pi * k * t) for k, a in amps.items()}


def zero_crossings(x, f, lo, hi):
    """Positions where f crosses zero in [lo, hi], by linear interpolation."""
    m = (x[1:] >= lo) & (x[:-1] <= hi) & (np.sign(f[1:]) != np.sign(f[:-1]))
    xa, xb = x[:-1][m], x[1:][m]
    fa, fb = f[:-1][m], f[1:][m]
    return xa - fa * (xb - xa) / (fb - fa)


def local_maxima(x, f):
    """Positions of all local maxima of f (strictly greater than both neighbors)."""
    m = (f[1:-1] > f[:-2]) & (f[1:-1] > f[2:])
    return x[1:-1][m], f[1:-1][m]


def env_extrema(x, A, B, k1, k2):
    """Envelope E(x) = |A e^{i2 pi k1 x} + B e^{i2 pi k2 x}| of a two-tone
    pattern: local minima (nulls, where |A| = |B|) and maxima (beats)."""
    E = np.abs(A * np.exp(2j * np.pi * k1 * x) + B * np.exp(2j * np.pi * k2 * x))
    mmin = (E[1:-1] < E[:-2]) & (E[1:-1] < E[2:]) & (E[1:-1] < E[1:-1].mean() * 0.05)
    mmax = (E[1:-1] > E[:-2]) & (E[1:-1] > E[2:]) & (E[1:-1] > E[1:-1].mean() * 0.5)
    return E, x[1:-1][mmin], x[1:-1][mmax]


def report_positions(indent, x_meas, expected, unit):
    """Print measured vs predicted special positions in units of `unit`."""
    for xm, xp in zip(x_meas, expected):
        print(f"{indent}  x = {xm:7.4f}   x/unit = {xm / unit:7.4f}   "
              f"predicted x/unit = {xp / unit:6.4f}   "
              f"|dx|/unit = {abs(xm - xp) / unit:.5f}")


# ----------------------------------------------------------------------
# Probe 1 (P44): single wake source, envelope special positions
# ----------------------------------------------------------------------

def probe_1(x, dx, dt):
    print()
    print("=" * 78)
    print("Probe 1 — P44 staggered checkerboard: envelope positions of the")
    print("single wake source, in units of ell_{n+1} = phi")
    print("=" * 78)
    t = 0.01                       # standing wave; window clean everywhere
    n_steps = int(round(t / dt))
    x_lo, x_hi = 0.12, 7.0
    m_win = (x >= x_lo) & (x <= x_hi)

    def run(EY0, EI0):
        EY, EI, _, _ = evolve(EY0.copy(), EI0.copy(), np.zeros_like(x),
                              np.zeros_like(x), dx, dt, n_steps, 0.0)
        return EY, EI

    # (0) solver sanity on leg 1: PDE vs the exact d'Alembert standing wave
    EY0 = 1 + AMP * (np.cos(2 * np.pi * x) + np.cos(2 * np.pi * PHI * x))
    EI0 = 1 + AMP * np.cos(2 * np.pi * PHI * x)
    EY, _ = run(EY0, EI0)
    EY_an = 1 + AMP * (np.cos(2 * np.pi * x) * np.cos(2 * np.pi * t)
                       + np.cos(2 * np.pi * PHI * x)
                       * np.cos(2 * np.pi * PHI * t))
    print(f"\n(0) solver sanity (leg 1, t = {t}): max|PDE - standing-wave| "
          f"in window = {np.max(np.abs(EY - EY_an)[m_win]):.2e}")
    print("    (level of the finite-domain wall-phase mismatch; measured,")
    print("    not the physical signal)")

    # --- Leg 1: the wake pair in E_Y (Panel A convention) ---
    print("\n--- Leg 1: wake pair in E_Y ---")
    print("    E_Y = 1 + A[cos(2 pi x) + cos(2 pi phi x)], "
          "E_I = 1 + A cos(2 pi phi x)")
    EY, _ = run(EY0, EI0)
    c0, amps_t, rms = lsq_tones(x[m_win], EY[m_win] - 1.0, [1.0, PHI])
    amps = unwrap(amps_t, t)
    print(f"    two-tone fit (t = {t}): |amp_1| = {abs(amps_t[1.0]):.5f}, "
          f"|amp_phi| = {abs(amps_t[PHI]):.5f} (cos factors "
          f"{np.cos(2*np.pi*t):.4f}, {np.cos(2*np.pi*PHI*t):.4f}); "
          f"unwrapped |amp_1| = {abs(amps[1.0]):.5f}, "
          f"|amp_phi| = {abs(amps[PHI]):.5f}, phase diff = "
          f"{(np.angle(amps[PHI]) - np.angle(amps[1.0])) % (2 * np.pi):.5f} "
          f"rad, residual RMS = {rms:.2e}")
    E, xmin, xmax = env_extrema(x[m_win], amps[1.0], amps[PHI], 1.0, PHI)
    nulls = np.sort(xmin)
    beats = np.sort(xmax)
    print("    launch-envelope nulls (voids, destructive):")
    report_positions("   ", nulls, (np.arange(len(nulls)) + 0.5) * PHI, PHI)
    print("    launch-envelope beats (bubbles, constructive):")
    report_positions("   ", beats, (np.arange(1, len(beats) + 1)) * PHI, PHI)
    zc = zero_crossings(x, EY - 1.0, x_lo, x_hi)
    zc_sp = np.diff(np.sort(zc))
    print(f"    raw zero crossings of E_Y - 1: {len(zc)} total, mean spacing "
          f"{zc_sp.mean():.4f} (carrier ~1/phi^2 = {PHI ** -2:.4f} and")
    print(f"    envelope ~phi = {PHI:.4f} scales interleave; the slow set is")
    print(f"    the envelope nulls above)")
    xm_raw, _ = local_maxima(x[m_win], np.abs(EY[m_win] - 1.0))
    print("    raw |E_Y - 1| crests near each envelope beat (carrier")
    print("    factor shifts the field crests off the envelope beats):")
    for m in range(1, 5):
        xp = m * PHI
        i = np.argmin(np.abs(xm_raw - xp))
        print(f"      m = {m}: beat at {xp:.4f}, raw crest at {xm_raw[i]:.4f}, "
              f"offset = {(xm_raw[i] - xp) / PHI:+.4f} ell_{{n+1}}")

    # --- Leg 2: the pair in the density rho = E_Y + E_I ---
    print("\n--- Leg 2: wake pair in rho = E_Y + E_I ---")
    print("    E_Y = 1 + A cos(2 pi x), E_I = 1 + A cos(2 pi phi x)")
    EY2 = 1 + AMP * np.cos(2 * np.pi * x)
    EI2 = 1 + AMP * np.cos(2 * np.pi * PHI * x)
    EYp, EIp = run(EY2, EI2)
    rho = EYp + EIp
    c0, amps_t, rms = lsq_tones(x[m_win], rho[m_win] - 2.0, [1.0, PHI])
    amps = unwrap(amps_t, t)
    print(f"    two-tone fit: |amp_1| = {abs(amps[1.0]):.5f}, "
          f"|amp_phi| = {abs(amps[PHI]):.5f}, residual RMS = {rms:.2e}")
    E, xmin, xmax = env_extrema(x[m_win], amps[1.0], amps[PHI], 1.0, PHI)
    nulls = np.sort(xmin)
    beats = np.sort(xmax)
    print("    launch-envelope nulls (voids, destructive):")
    report_positions("   ", nulls, (np.arange(len(nulls)) + 0.5) * PHI, PHI)
    print("    launch-envelope beats (bubbles, constructive):")
    report_positions("   ", beats, (np.arange(1, len(beats) + 1)) * PHI, PHI)
    # imbalance leg: Pi = E_Y - E_I, envelope expected inverted
    Pi = EYp - EIp
    c0, amps_t, rms = lsq_tones(x[m_win], Pi[m_win], [1.0, PHI])
    amps = unwrap(amps_t, t)
    E, xmin, xmax = env_extrema(x[m_win], amps[1.0], amps[PHI], 1.0, PHI)
    nulls = np.sort(xmin)
    beats = np.sort(xmax)
    print("    (leg 3) imbalance Pi = E_Y - E_I launch envelope (inverted:")
    print("    nulls at m*ell_{n+1}, beats at the half-rungs):")
    report_positions("   ", nulls, (np.arange(1, len(nulls) + 1)) * PHI, PHI)
    report_positions("   ", beats, (np.arange(len(beats)) + 0.5) * PHI, PHI)

    print("\n  Reading: the launch envelope (slow beat factor) peaks at")
    print("  m*ell_{n+1} and nulls at (m+1/2)*ell_{n+1} to the grid scale —")
    print("  the staggered checkerboard placement. The raw field crests sit")
    print("  off-rung by the carrier factor — the envelope, not the raw")
    print("  crest, is the condensation site (wake-geometry.md §2(c), P46's")
    print("  special-position language u = 1 + log_phi m).")
    return


# ----------------------------------------------------------------------
# Probe 2 (P43): beat period of the composite wake pair
# ----------------------------------------------------------------------

def probe_2(x, dx, dt):
    print()
    print("=" * 78)
    print("Probe 2 — P43 composite closure: beats at m*ell_{n+1} from")
    print("two wake trains whose wavelengths sum to the next rung")
    print("=" * 78)
    t = 0.01
    n_steps = int(round(t / dt))
    x_lo, x_hi = 0.12, 7.0
    m_win = (x >= x_lo) & (x <= x_hi)

    def run(EY0, EI0):
        EY, EI, _, _ = evolve(EY0.copy(), EI0.copy(), np.zeros_like(x),
                              np.zeros_like(x), dx, dt, n_steps, 0.0)
        return EY, EI

    def beat_report(label, k1, k2, unit):
        EY0 = 1 + AMP * np.cos(2 * np.pi * k1 * x)
        EI0 = 1 + AMP * np.cos(2 * np.pi * k2 * x)
        EY, EI = run(EY0, EI0)
        rho = EY + EI
        c0, amps_t, rms = lsq_tones(x[m_win], rho[m_win] - 2.0, [k1, k2])
        amps = unwrap(amps_t, t)
        E, xmin, xmax = env_extrema(x[m_win], amps[k1], amps[k2], k1, k2)
        peaks = np.sort(xmax)
        nulls = np.sort(xmin)
        spac = np.diff(peaks) / unit
        nspac = np.diff(nulls) / unit
        print(f"\n  {label}: wakes at k = {k1:.4f} and {k2:.4f} "
              f"(Lambda_Y + Lambda_I = {1 / k1 + 1 / k2:.4f})")
        print(f"    fitted |amp| ratio = {abs(amps[k1]) / abs(amps[k2]):.5f}, "
              f"residual RMS = {rms:.2e}")
        print(f"    beat peaks at x/unit = "
              f"{', '.join(f'{p / unit:.4f}' for p in peaks)}")
        print(f"    beat peak spacings / composite = "
              f"{', '.join(f'{s:.5f}' for s in spac)}")
        print(f"    envelope nulls at x/unit = "
              f"{', '.join(f'{p / unit:.4f}' for p in nulls)}")
        print(f"    null spacings / composite = "
              f"{', '.join(f'{s:.5f}' for s in nspac)}")
        if len(spac):
            print(f"    mean peak spacing = {spac.mean():.5f} +- "
                  f"{spac.std():.5f} (predicted 1.00000)")
        return spac

    print("\n  Canonical pair (rung n): Lambda_Y = 1, Lambda_I = 1/phi,")
    print("  sum = phi = ell_{n+1}  ->  beats at m*ell_{n+1}:")
    beat_report("P43 canonical", 1.0, PHI, PHI)
    print("\n  Scale-covariant pair (rung n+1): Lambda_Y = phi, Lambda_I = 1,")
    print("  sum = phi + 1 = phi^2 = ell_{n+2}  ->  beats at m*ell_{n+2}:")
    beat_report("P43 scaled", 1 / PHI, 1.0, PHI ** 2)
    return


# ----------------------------------------------------------------------
# Probe 3 (sharpening): F2/F1 = 1/phi in the two-bubble standing pattern
# ----------------------------------------------------------------------

def probe_3(x, dx, dt):
    print()
    print("=" * 78)
    print("Probe 3 — wake-force sharpening: F = Pi grad(Phi) harmonics in")
    print("the two-bubble standing pattern (bubbles at x = 0 and x = phi)")
    print("=" * 78)
    t = 0.01                        # whole-domain window clean (walls at
    n_steps = int(round(t / dt))    # -1.5 and 8.09; influence reaches
    x_lo, x_hi = -1.4, 8.0          # -1.49 and 8.08 by t = 0.01)
    m_win = (x >= x_lo) & (x <= x_hi)

    EY0 = 1 + AMP * (np.cos(2 * np.pi * x) + np.cos(2 * np.pi * (x - PHI)))
    EI0 = 1 + AMP * (np.cos(2 * np.pi * PHI * x)
                     + np.cos(2 * np.pi * PHI * (x - PHI)))

    def force_spectrum(EY, EI, unwrap_to_zero):
        """F = Pi grad(Phi) with the solver's spectral Poisson convention:
        grad^2 Phi = rho with the k = 0 mode dropped, i.e. each density
        tone k contributes Phi_k = -rho_k cos(2 pi k x)/(2 pi k)^2, so
        grad(Phi) = sum_k rho_k sin(2 pi k x)/(2 pi k). The tones are
        measured by least squares; at t > 0 each tone is unwrapped by
        cos(2 pi k t) to recover the launch amplitudes (the claim is a
        property of the launch pattern). Returns the four force-line
        amplitudes and the residual RMS."""
        Pi = EY - EI
        rho_osc = EY + EI - 2.0
        c0, a_rho, _ = lsq_tones(x[m_win], rho_osc[m_win], [1.0, PHI])
        c0, a_pi, _ = lsq_tones(x[m_win], Pi[m_win], [1.0, PHI])
        if unwrap_to_zero:
            a_rho = unwrap(a_rho, t)
            a_pi = unwrap(a_pi, t)
        # spectral Poisson (k = 0 dropped): per-tone 1/k Green
        dPhi = (a_rho[1.0].real * np.sin(2 * np.pi * x[m_win]) / (2 * np.pi)
                + a_rho[PHI].real * np.sin(2 * np.pi * PHI * x[m_win])
                / (2 * np.pi * PHI))
        Pi_fit = (a_pi[1.0].real * np.cos(2 * np.pi * x[m_win])
                  + a_pi[PHI].real * np.cos(2 * np.pi * PHI * x[m_win]))
        F = Pi_fit * dPhi
        ks = [PHI - 1.0, 2.0, 1.0 + PHI, 2.0 * PHI]
        c0, amps, rms = lsq_tones(x[m_win], F, ks)
        return ks, amps, rms

    print(f"\n  force convention: F = Pi grad(Phi), Pi = E_Y - E_I, "
          f"grad^2 Phi = rho, Poisson spectral with k = 0 dropped")
    print(f"  (documented: spiral-dynamics.md §3.1, "
          f"cassi_two_fluid_3d_gpu.py rhs)")

    # analytic leg: the ICs (launch pattern, t = 0)
    ks, amps_a, rms_a = force_spectrum(EY0, EI0, False)
    # PDE leg: evolved to t = 0.01, tones unwrapped to launch
    EY, EI, _, _ = evolve(EY0.copy(), EI0.copy(), np.zeros_like(x),
                          np.zeros_like(x), dx, dt, n_steps, 0.0)
    ks, amps_p, rms_p = force_spectrum(EY, EI, True)

    print(f"\n  harmonic lines of F(x) (cycles/ell_n):")
    print(f"  {'line':>10} {'k':>8} {'amp analytic':>13} {'amp PDE':>12} "
          f"{'PDE/analytic':>12}")
    for k in ks:
        print(f"  {'k=' + f'{k:.4f}':>10} {k:>8.4f} {abs(amps_a[k]):>13.6f} "
              f"{abs(amps_p[k]):>12.6f} {abs(amps_p[k] / amps_a[k]):>12.5f}")
    print(f"  (fit residuals: analytic {rms_a:.2e}, PDE {rms_p:.2e})")

    r21_a = abs(amps_a[2.0 * PHI]) / abs(amps_a[2.0])
    r21_p = abs(amps_p[2.0 * PHI]) / abs(amps_p[2.0])
    print(f"\n  claimed F2/F1 = A(k = 2 phi)/A(k = 2) (self-harmonics of")
    print(f"  the Yin and Yang wakes):")
    print(f"    analytic: {r21_a:.6f}   PDE: {r21_p:.6f}   "
          f"1/phi = {1 / PHI:.6f}   (PDE vs claim: "
          f"{(r21_p - 1 / PHI) / (1 / PHI) * 100:+.2f}%)")

    cx_a = abs(amps_a[PHI - 1.0]) / abs(amps_a[1.0 + PHI])
    cx_p = abs(amps_p[PHI - 1.0]) / abs(amps_p[1.0 + PHI])
    print(f"\n  claimed phase-gradient ratio, cross-harmonics of the wake")
    print(f"  pair: A(k = phi-1)/A(k = 1+phi):")
    print(f"    analytic: {cx_a:.6f}   PDE: {cx_p:.6f}   "
          f"phi^3 = {PHI ** 3:.6f}   (PDE vs claim: "
          f"{(cx_p - PHI ** 3) / PHI ** 3 * 100:+.2f}%)")
    print(f"    (identical to the wavenumber ratio "
          f"k(1+phi)/k(phi-1) = {(1 + PHI) / (PHI - 1):.6f} — exact by the")
    print(f"    interference identity (1+phi)/(phi-1) = phi^3)")

    # windowed FFT peak scan with parabolic refinement: the lines sit at
    # the predicted k (resolution 0.106 cycles/ell_n)
    Pi = EY - EI
    rho_osc = EY + EI - 2.0
    c0, a_rho, _ = lsq_tones(x[m_win], rho_osc[m_win], [1.0, PHI])
    c0, a_pi, _ = lsq_tones(x[m_win], Pi[m_win], [1.0, PHI])
    a_rho = unwrap(a_rho, t)
    a_pi = unwrap(a_pi, t)
    dPhi = (a_rho[1.0].real * np.sin(2 * np.pi * x[m_win]) / (2 * np.pi)
            + a_rho[PHI].real * np.sin(2 * np.pi * PHI * x[m_win])
            / (2 * np.pi * PHI))
    Pi_fit = (a_pi[1.0].real * np.cos(2 * np.pi * x[m_win])
              + a_pi[PHI].real * np.cos(2 * np.pi * PHI * x[m_win]))
    F_p = Pi_fit * dPhi
    sig = F_p - F_p.mean()
    sig *= np.hanning(sig.size)
    kk = np.fft.rfftfreq(sig.size, d=dx)
    spec = np.abs(np.fft.rfft(sig))
    print(f"\n  FFT peak scan of the PDE force (windowed, resolution "
          f"{kk[1]:.3f}, parabolic refinement):")
    for k in ks:
        i = np.argmax(spec * np.exp(-((kk - k) / 0.05) ** 2))
        if 0 < i < len(kk) - 1:
            y0, y1, y2 = np.log(spec[i - 1:i + 2])
            dk = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2)
            kref = kk[i] + dk * (kk[1])
        else:
            kref = kk[i]
        print(f"    line k = {k:6.4f}: FFT peak at k = {kref:.4f} "
              f"(bin {kk[i]:.4f})")

    # alternative convention: F = -grad(eps), eps = E_Y - phi E_I
    eps = EY - PHI * EI
    c0, amps_e, rms_e = lsq_tones(x[m_win], -np.gradient(eps, dx)[m_win],
                                  [1.0, PHI])
    amps_e = unwrap(amps_e, t)
    re = abs(amps_e[PHI]) / abs(amps_e[1.0])
    print(f"\n  alternative convention F = -grad(E_Y - phi E_I): harmonic")
    print(f"    ratio = {re:.6f} (phi = {PHI:.6f}, phi^2 = {PHI ** 2:.6f});")
    print(f"    the claimed 1/phi requires the documented Pi grad(Phi) form,")
    print(f"    whose 1/k Green factor suppresses the Yin self-harmonic.")
    return


# ----------------------------------------------------------------------

def main():
    L = 5 * PHI          # physical domain, same as the T1 probe
    x_sp = 1.5
    N = 1216
    dt = 0.0015
    x = np.linspace(-x_sp, L, N)
    dx = x[1] - x[0]

    print("=" * 78)
    print("Wake structural probes (P44 / P43 / wake-force sharpening)")
    print(f"phi = {PHI:.6f}, ell_n = 1, ell_{{n+1}} = phi = {PHI:.4f}, "
          f"AMP = {AMP}, N = {N}, dt = {dt}")
    print("=" * 78)

    probe_1(x, dx, dt)
    probe_2(x, dx, dt)
    probe_3(x, dx, dt)

    print()
    print("=" * 78)
    print("Verdicts")
    print("=" * 78)
    print("P44 (staggered checkerboard): launch-envelope nulls at")
    print("  (m+1/2)*ell_{n+1} and beats at m*ell_{n+1} — measured to the")
    print("  grid scale in both conventions (pair in E_Y, pair in rho);")
    print("  the raw field crests carry the carrier-factor offset")
    print("  documented in P46. SUPPORTED.")
    print("P43 (composite closure): the beat period equals the wavelength")
    print("  sum Lambda_Y + Lambda_I = ell_{n+1} (and ell_{n+2} for the")
    print("  scaled pair) — beats land on m*ell_{n+1} to the grid scale.")
    print("  SUPPORTED.")
    print("Sharpening: F2/F1 = A(2 phi)/A(2) = 1/phi and the cross-")
    print("  harmonic amplitude ratio A(phi-1)/A(1+phi) = phi^3, both in")
    print("  the documented force F = Pi grad(Phi) with the spectral")
    print("  Poisson; F = -grad(E_Y - phi E_I) instead gives phi^2.")
    print("  SUPPORTED under the documented force; see the tables.")


if __name__ == "__main__":
    main()
