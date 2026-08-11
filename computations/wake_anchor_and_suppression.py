"""Wake-anchor ratio and per-rung suppression: what the two-fluid dynamics give.

Run:  python computations/wake_anchor_and_suppression.py

Two audit questions, both about whether a 1/phi ratio is DERIVED from the
two-fluid wave dynamics or selected/calibrated by the framework's principles.

Section A - the wake anchors (foundations/wake-geometry.md sec 1):
  The wake pair has Lambda_Y = ell_n and Lambda_I = ell_n/phi, i.e. the
  Yin wavenumber k_I = phi k_Y.  Three dispersion facts are measured:

  A1. Eigenmodes of the linearized two-fluid wave system:
      d2E_Y = c^2 d2E_Y - lam(1-q)(E_Y - phi E_I)
      d2E_I = c^2 d2E_I + (lam/phi)(1-q)(E_Y - phi E_I)
      -> in-phase mode  (E_Y = phi E_I):  w^2 = c^2 k^2   (the rho mode)
      -> anti-phase mode(E_Y = -phi E_I): w^2 = c^2 k^2 + 2 lam (1-q)
                                            (the eps = E_Y - phi E_I mode)
      A single-frequency string (one motion) excites both modes at the
      SAME frequency w; the emitted wavelength ratio is
          Lambda_eps / Lambda_rho = 1 / sqrt(1 - 2 lam (1-q) / w^2)
      measured at the rung tones w = 2 pi and w = 2 pi phi with the
      framework's lam = 0.1.

  A2. The canonical standing wave (the T1 harness wake pair
      cos(2 pi x) + cos(2 pi phi x)): envelope beat period
      2 pi/(k_I - k_Y) = phi (in ell_n units) = ell_{n+1}, null spacing
      pi/(k_I - k_Y) = phi/2, and the tone wavelengths 1 and 1/phi.
      Measured from a short RK4 evolution (imported harness).

  A3. The driven emission: a Gaussian source oscillating at frequency w
      drives BOTH fluids (the string's single motion); the radiated
      wavelengths of rho = E_Y + E_I and eps = E_Y - phi E_I are measured
      away from the source.  This is the emission picture's direct answer
      to "where does k_I = phi k_Y come from".

  Verdict: the beat structure of the wake pair (given the pair) is exact
  and measured; the RATIO itself does not emerge from the linearized
  dispersion (it is ~1.003, not phi); it is selected by de-resonance +
  closure + nesting (the Yin wake is the previous rung's Yang wake,
  Lambda_I^(n) = ell_{n-1}, an identity of the ladder).

Section B - the per-rung suppression factor (cascade-suppression-formula.md
  sec 1/4):  d_i^signal ~ phi^-1 per rung.  Three candidates:

  B1. Impedance transmission across a rung boundary with impedance ratio
      phi: T = 2 sqrt(Z1 Z2)/(Z1 + Z2) = 2 phi^{-3/2} ~ 0.9717 (amplitude),
      power 4 phi^{-3} ~ 0.944, amplitude reflection (phi-1)/(1+phi) =
      phi^{-3} ~ 0.236.  None equal phi^-1 = 0.618.
  B2. The kinetic-vs-conversion ratio asserted in sec 4 ("the kinetic
      term at each rung is O(phi) relative to the conversion term"):
      measured at the rung scale, kinetic = c^2 k^2 = 4 pi^2 and
      conversion = lam (1-q), so conversion/kinetic = lam/4 pi^2 ~ 0.0025
      at lam = 0.1 - two and a half orders below phi^-1.  The assertion
      does not hold at the rung-wave scale.
  B3. The attractor Yang fraction: r/(1+r) at r = phi = phi/(1+phi) =
      phi^-1 EXACTLY (parameter-inventory ledger row 500/453).  The
      per-rung factor is the fraction of the two-fluid amplitude that
      sits in the Yang (propagating) channel at the fixed point - the
      framework's own attractor ratio, not a crossing amplitude.

  Verdict: no crossing model yields phi^-1; the per-rung factor is the
  attractor Yang fraction (exact identity) and remains the definitional
  calibration of the suppression formula.

Output: console tables + verdicts.  No figure is written.
"""

import sys
import os
import numpy as np

PHI = (1 + 5**0.5) / 2
LNPHI = np.log(PHI)
LAM = 0.1                 # PDE conversion rate, lambda = 1/(2w), w = 5
C2 = 1.0                  # wave speed squared, probe units
GAMMA = 0.01              # wave damping, probe units

# ----------------------------------------------------------------------
# A1. Linearized eigenmodes of the two-fluid wave system
# ----------------------------------------------------------------------

def eigenmode_ratio(w, lam=LAM, omq=1.0):
    """Lambda_eps / Lambda_rho for a single-frequency source: the anti-phase
    (eps) mode has w^2 = c^2 k^2 + 2 lam (1-q); the in-phase (rho) mode has
    w^2 = c^2 k^2.  At common w:
        k_eps/k_rho = sqrt(1 - 2 lam (1-q)/w^2),
        Lambda_eps/Lambda_rho = 1 / sqrt(1 - 2 lam (1-q)/w^2).
    """
    return 1.0 / np.sqrt(1.0 - 2.0 * lam * omq / w**2)


def a1():
    print("=" * 78)
    print("A1 - linearized eigenmodes: single-frequency emission ratio")
    print("=" * 78)
    print(f"  lam = {LAM}, c = 1, gate open (1-q) = 1 and attractor "
          f"(1-q) = phi^-2/3")
    omq_att = PHI**-2 / 3.0
    for w, label in [(2 * np.pi, "Yang tone w = 2 pi (k = 1)"),
                     (2 * np.pi * PHI, "Yin tone w = 2 pi phi (k = phi)")]:
        for omq, gl in [(1.0, "gate open"), (omq_att, "attractor")]:
            r = eigenmode_ratio(w, omq=omq)
            print(f"    {label:34s} {gl:9s}: "
                  f"Lambda_eps/Lambda_rho = {r:.6f}   "
                  f"(phi = {PHI:.6f}, phi^-1 = {PHI**-1:.6f})")
    r = eigenmode_ratio(2 * np.pi)
    print(f"\n  Decisive number: at the Yang tone with lam = {LAM} and the")
    print(f"  gate open, the anti-phase (conversion) wake is emitted at")
    print(f"  {r - 1:.6f} relative correction to the rung scale - NOT the")
    print(f"  sub-rung scale phi^-1 - 1 = {PHI**-1 - 1:.3f}.  The conversion")
    print(f"  mass 2 lam = {2*LAM:.2f} is ~{2*LAM/(2*np.pi)**2:.4f} of the")
    print(f"  tone frequency-squared: the dispersion does not select the")
    print(f"  sub-rung scale.")
    return r


# ----------------------------------------------------------------------
# A2. Canonical standing wave: beat and extremum spacings
# ----------------------------------------------------------------------

def a2():
    """Wake pair cos(2 pi x) + cos(2 pi phi x) in the T1 harness: envelope
    beat period 2 pi/(k_I - k_Y) = phi, null spacing pi/(k_I - k_Y) = phi/2,
    tone wavelengths 1 and 1/phi.  Short RK4 evolution, extremum spacing."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    os.pardir, "two-fluid"))
    from run_rung_offset_probe import evolve

    print("=" * 78)
    print("A2 - canonical wake-pair standing wave: extremum spacings")
    print("=" * 78)
    L = 5 * PHI
    x_sp = 1.5
    N = 1216
    dt = 0.0015
    x = np.linspace(-x_sp, L, N)
    dx = x[1] - x[0]
    AMP = 0.32
    t = 0.01
    n_steps = int(round(t / dt))

    EY0 = 1 + AMP * (np.cos(2 * np.pi * x) + np.cos(2 * np.pi * PHI * x))
    EI0 = 1 + AMP * np.cos(2 * np.pi * PHI * x)
    EY, EI, _, _ = evolve(EY0.copy(), EI0.copy(), np.zeros_like(x),
                          np.zeros_like(x), dx, dt, n_steps, 0.0)
    # unwrap each tone by its cos(2 pi k t) factor (V = 0 standing wave)
    cY_t = np.cos(2 * np.pi * t)
    cI_t = np.cos(2 * np.pi * PHI * t)
    print(f"  t = {t}: cos factors {cY_t:.4f} (k=1), {cI_t:.4f} (k=phi)")
    # least-squares tones of E_Y - 1 and E_I - 1
    def tones(f):
        cols = [np.ones_like(x)]
        for k in (1.0, PHI):
            cols += [np.cos(2 * np.pi * k * x), np.sin(2 * np.pi * k * x)]
        A = np.column_stack(cols)
        coef, *_ = np.linalg.lstsq(A, f, rcond=None)
        amps = {}
        for j, k in enumerate((1.0, PHI)):
            amps[k] = (coef[1 + 2*j] - 1j * coef[2 + 2*j]) / \
                np.cos(2 * np.pi * k * t)
        return amps

    aY = tones(EY - 1.0)
    aI = tones(EI - 1.0)
    print(f"  E_Y tones (unwrapped): |amp_1| = {abs(aY[1.0]):.5f}, "
          f"|amp_phi| = {abs(aY[PHI]):.5f}")
    print(f"  E_I tones (unwrapped): |amp_1| = {abs(aI[1.0]):.5f}, "
          f"|amp_phi| = {abs(aI[PHI]):.5f}")

    # envelope of the composite E_Y: |A e^{i2pix} + B e^{i2pi phi x}|
    E = np.abs(aY[1.0] * np.exp(2j * np.pi * x)
               + aY[PHI] * np.exp(2j * np.pi * PHI * x))
    mmin = (E[1:-1] < E[:-2]) & (E[1:-1] < E[2:])
    mmax = (E[1:-1] > E[:-2]) & (E[1:-1] > E[2:])
    xmin = np.sort(x[1:-1][mmin])
    xmax = np.sort(x[1:-1][mmax])
    # keep the window [0.12, 7.0] as the harness does
    xmin = xmin[(xmin > 0.12) & (xmin < 7.0)]
    xmax = xmax[(xmax > 0.12) & (xmax < 7.0)]
    print(f"  envelope nulls at x = {np.array2string(xmin, precision=4)}")
    print(f"    null spacing / phi = "
          f"{np.array2string(np.diff(xmin) / PHI, precision=5)}  "
          f"(predicted 1.0; the beat-to-null distance is the half-period")
    print(f"    pi/(k_I - k_Y) = phi/2 = {PHI / 2:.5f})")
    print(f"  envelope beats at x = {np.array2string(xmax, precision=4)}")
    print(f"    beat spacing / phi = "
          f"{np.array2string(np.diff(xmax) / PHI, precision=5)}  "
          f"(predicted 1.0)")
    # tone wavelengths: successive extrema of each tone
    def tone_extrema(k):
        f = np.cos(2 * np.pi * k * x)
        m = (f[1:-1] > f[:-2]) & (f[1:-1] > f[2:])
        return x[1:-1][m]
    mY = tone_extrema(1.0)
    mI = tone_extrema(PHI)
    mY = mY[(mY > 0.1) & (mY < 7.0)]
    mI = mI[(mI > 0.1) & (mI < 7.0)]
    print(f"  Yang tone (k=1) crest spacing = {np.diff(mY).mean():.5f} "
          f"(= Lambda_Y = 1)")
    print(f"  Yin tone (k=phi) crest spacing = {np.diff(mI).mean():.5f} "
          f"(= Lambda_I = 1/phi = {PHI**-1:.5f})")
    print(f"  Lambda_Y/Lambda_I = {np.diff(mY).mean() / np.diff(mI).mean():.6f} "
          f"vs phi = {PHI:.6f}")
    print(f"  beat period 2 pi/(k_I - k_Y) = phi = {PHI:.5f} = ell_{{n+1}};")
    print(f"  the Yin tone's own wavelength 2 pi/k_I = 1/phi is the tone,")
    print(f"  not the beat - the ratio 1/phi is an identity once")
    print(f"  k_I = phi k_Y is given.")
    return


# ----------------------------------------------------------------------
# A3. Driven emission: what a single-frequency string actually radiates
# ----------------------------------------------------------------------

def a3():
    """Gaussian source oscillating at frequency w drives both fluids (one
    string motion).  Measure the radiated wavelengths of rho = E_Y + E_I
    and eps = E_Y - phi E_I away from the source."""
    print("=" * 78)
    print("A3 - driven emission: wavelengths radiated by one frequency")
    print("=" * 78)

    L = 12.0
    N = 2400
    dx = L / N
    dt = 0.002
    x = np.linspace(-L / 2, L / 2, N)
    tmax = 6.0
    n_steps = int(round(tmax / dt))
    w = 2 * np.pi                     # Yang-tone frequency, probe units
    sigma = 0.10

    def lap(f):
        out = np.empty_like(f)
        out[1:-1] = (f[:-2] - 2 * f[1:-1] + f[2:]) / dx**2
        out[0] = 2 * (f[1] - f[0]) / dx**2        # mirror Neumann
        out[-1] = 2 * (f[-2] - f[-1]) / dx**2
        return out

    def step(EY, EI, VY, VI, t, src_amp, lam, gamma, c2, antisym):
        dEY = VY
        dEI = VI
        imbalance = EY - PHI * EI
        conv = -lam * imbalance
        s = src_amp * np.exp(-0.5 * (x / sigma) ** 2) * np.cos(w * t)
        if antisym:
            # the conversion's own pattern: Yang grows as Yin shrinks
            sY, sI = s, -s
        else:
            # the string's coherent motion: both fluids driven together
            sY, sI = s, s
        dVY = c2 * lap(EY) - gamma * VY + conv + sY
        dVI = c2 * lap(EI) - gamma * VI - conv + sI
        return dEY, dEI, dVY, dVI

    def evolve_driven(lam, antisym):
        EY = np.ones_like(x)
        EI = np.ones_like(x)
        VY = np.zeros_like(x)
        VI = np.zeros_like(x)
        t = 0.0
        amp = 1.0
        for _ in range(n_steps):
            k1 = step(EY, EI, VY, VI, t, amp, lam, GAMMA, C2, antisym)
            k2 = step(EY + .5*dt*k1[0], EI + .5*dt*k1[1], VY + .5*dt*k1[2],
                      VI + .5*dt*k1[3], t + .5*dt, amp, lam, GAMMA, C2,
                      antisym)
            k3 = step(EY + .5*dt*k2[0], EI + .5*dt*k2[1], VY + .5*dt*k2[2],
                      VI + .5*dt*k2[3], t + .5*dt, amp, lam, GAMMA, C2,
                      antisym)
            k4 = step(EY + dt*k3[0], EI + dt*k3[1], VY + dt*k3[2],
                      VI + dt*k3[3], t + dt, amp, lam, GAMMA, C2, antisym)
            EY += dt/6 * (k1[0] + 2*k2[0] + 2*k3[0] + k4[0])
            EI += dt/6 * (k1[1] + 2*k2[1] + 2*k3[1] + k4[1])
            VY += dt/6 * (k1[2] + 2*k2[2] + 2*k3[2] + k4[2])
            VI += dt/6 * (k1[3] + 2*k2[3] + 2*k3[3] + k4[3])
            t += dt
        return EY, EI

    for lam in (0.0, LAM):
        # symmetric drive -> the rho (in-phase) eigenmode
        EY, EI = evolve_driven(lam, antisym=False)
        rho = EY + EI - 2.0
        # anti-symmetric drive -> the eps (anti-phase) eigenmode
        EY2, EI2 = evolve_driven(lam, antisym=True)
        eps = EY2 - PHI * EI2
        # measure wavelengths in [2.0, 5.5] (radiated zone, clear of the
        # source and the boundaries: wavefront at c t = 6); the eps field
        # oscillates around a non-zero mean (background 1 - phi and the
        # drive-induced offset), so subtract the window mean first and
        # cross-check with a windowed FFT
        def wavelength(f, lo, hi):
            mw = (x >= lo) & (x <= hi)
            g = f[mw]
            g = g - g.mean()
            sgn = np.sign(g)
            zc = np.where(sgn[1:] != sgn[:-1])[0]
            if len(zc) > 1:
                l_cross = 2.0 * float(np.diff(zc).mean()) * dx
            else:
                l_cross = float("nan")
            Nw = g.size
            spec = np.abs(np.fft.rfft(g * np.hanning(Nw)))
            kk = np.fft.rfftfreq(Nw, d=dx)
            i = int(np.argmax(spec[1:])) + 1
            y0, y1, y2 = spec[i-1], spec[i], spec[i+1]
            dk = 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2) if \
                abs(y0 - 2 * y1 + y2) > 1e-14 else 0.0
            kpeak = kk[i] + dk * kk[1]
            return l_cross, 1.0 / kpeak
        sr, srf = wavelength(rho, 2.0, 5.5)
        se, sef = wavelength(eps, 2.0, 5.5)
        lr = 2 * np.pi / w
        print(f"\n  lam = {lam}: source frequency w = {w:.4f} "
              f"(free wavelength 2 pi/w = {lr:.4f})")
        print(f"    rho channel (in-phase, symmetric drive): wavelength = "
              f"{sr:.5f} (FFT {srf:.5f})")
        print(f"    eps channel (anti-phase, anti-symmetric drive): "
              f"wavelength = {se:.5f} (FFT {sef:.5f}); ratio to rho = "
              f"{se / sr:.5f} (FFT {sef / srf:.5f})")
        if lam == 0.0:
            print(f"    (lam = 0 control: both eigenmodes radiate at the")
            print(f"     free wavelength - ratio 1.000)")
        else:
            r = eigenmode_ratio(w)
            print(f"    predicted eps/rho ratio = {r:.5f} "
                  f"(2 lam/w^2 = {2*lam/w**2:.5f}); phi^-1 = {PHI**-1:.5f},")
            print(f"    phi^2 = {PHI**2:.5f}.  The emission does NOT produce")
            print(f"    the sub-rung scale.")
    print(f"\n  Reading: with the framework's lam = {LAM} the conversion")
    print(f"  mass barely perturbs the radiated wavelengths (ratio ~1.003);")
    print(f"  a single-frequency string does not emit a phi-scaled Yin")
    print(f"  wake at linear order.  The 1/phi of the anchors is not in")
    print(f"  the dispersion; it is the cascade's own inter-rung ratio")
    print(f"  (Lambda_I^(n) = ell_{{n-1}}), selected by de-resonance and the")
    print(f"  composite closure 1 + 1/phi = phi.")
    return


# ----------------------------------------------------------------------
# B. Per-rung suppression candidates
# ----------------------------------------------------------------------

def b():
    print("=" * 78)
    print("B - per-rung suppression d ~ phi^-1: crossing-model candidates")
    print("=" * 78)

    # B1. impedance transmission across a rung boundary, Z2/Z1 = phi
    T = 2 * np.sqrt(PHI) / (1 + PHI)          # 2 sqrt(Z1 Z2)/(Z1+Z2)
    T_pow = 4 * PHI / (1 + PHI) ** 2          # power transmission
    R = (PHI - 1) / (1 + PHI)                 # amplitude reflection
    R_pow = R ** 2
    print(f"\n  B1. impedance step Z2/Z1 = phi (one rung):")
    print(f"      amplitude transmission T = 2 sqrt(phi)/(1+phi) = "
          f"2 phi^-3/2 = {T:.6f}   (phi^-1 = {PHI**-1:.6f})")
    print(f"      power transmission = 4 phi/(1+phi)^2 = 4 phi^-3 = "
          f"{T_pow:.6f}")
    print(f"      amplitude reflection r = (phi-1)/(1+phi) = phi^-3 = "
          f"{R:.6f};  power reflection = {R_pow:.6f}")
    print(f"      None equal phi^-1 = 0.618.  (The impedance picture is")
    print(f"      the wrong tool: a phi impedance step transmits ~97%,")
    print(f"      not 62%.)")

    # B2. kinetic vs conversion at the rung scale (the sec-4 assertion)
    kY = 2 * np.pi
    kinetic = C2 * kY ** 2
    conv = LAM
    print(f"\n  B2. 'the kinetic term at each rung is O(phi) relative to")
    print(f"      the conversion term' (sec 4 assertion), measured at the")
    print(f"      rung scale (c = 1, ell_n = 1, k = 2 pi):")
    print(f"      kinetic c^2 k^2 = {kinetic:.4f}, conversion lam = {conv}")
    print(f"      conversion/kinetic = {conv / kinetic:.6f} (gate open)")
    print(f"      vs phi^-1 = {PHI**-1:.6f}: the assertion is false by")
    print(f"      ~2.5 orders at the rung-wave scale.  The kinetic term")
    print(f"      dominates the conversion term by ~{kinetic / conv:.0f}x.")
    omq_att = PHI**-2 / 3.0
    print(f"      gated (attractor, 1-q = phi^-2/3): "
          f"{conv * omq_att / kinetic:.6f}")

    # B3. the attractor Yang fraction
    yf = PHI / (1 + PHI)
    print(f"\n  B3. attractor Yang fraction r/(1+r) at r = phi:")
    print(f"      phi/(1+phi) = phi/phi^2 = phi^-1 = {yf:.10f}  EXACT")
    print(f"      (fixed point E_Y = phi E_I; ledger rows 500/453).  The")
    print(f"      per-rung factor is the fixed point's amplitude split:")
    print(f"      the Yang (propagating) channel carries fraction phi^-1")
    print(f"      of the doublet at each rung.  This is the defensible")
    print(f"      in-framework expression of the per-rung factor; it is")
    print(f"      the definitional calibration of the suppression formula")
    print(f"      (postulate-level, like ell_n), not a crossing amplitude.")
    print(f"\n  Verdict: no crossing model (impedance, gate, de-resonance")
    print(f"  window) yields phi^-1 exactly; the per-rung factor stands as")
    print(f"  the attractor Yang fraction - exact identity, definitional")
    print(f"  calibration, stated plainly.")
    return


def main():
    print("=" * 78)
    print("Wake-anchor ratio and per-rung suppression verification")
    print(f"phi = {PHI:.10f}, lam = {LAM}, c = 1, ell_n = 1")
    print("=" * 78)
    a1()
    a2()
    a3()
    b()
    print("\n" + "=" * 78)
    print("Verdicts")
    print("=" * 78)
    print("A1/A3: the linearized two-fluid dispersion emits the anti-phase")
    print("  (conversion) wake at ~1.003 Lambda_Y with lam = 0.1 - the 1/phi")
    print("  ratio is NOT in the dispersion.  The wake pair's beat structure")
    print("  (A2) is exact: envelope period phi = ell_{n+1}, nulls at the")
    print("  half-period, tones at 1 and 1/phi.  The ratio is selected by")
    print("  de-resonance + composite closure + nesting (the Yin wake is")
    print("  the previous rung's Yang wake, ell_{n-1}).")
    print("B: the per-rung phi^-1 is not produced by any crossing model;")
    print("  it is the attractor Yang fraction phi/(1+phi) = phi^-1, the")
    print("  definitional calibration of the suppression formula.")


if __name__ == "__main__":
    main()
