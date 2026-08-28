"""triaxial3d_feed_probe.py -- wave 9: source-feed (Q1a/Q1b) and Poisson-gravity (Q2) probes.

Per triaxial3d_feed_prereg.md. Deterministic, numpy, matrix-free (never a dense N^3 x N^3
operator). Runs the SIM's real fully-periodic (phi, 1, phi^2) 19-point anisotropic two-fluid
operator from the physically-round seed, and asks whether (Q1a) the sustained TSC mass-deposit
feedback, (Q1b) the source_strength field-gain, or (Q2) the field's own Poisson-gravity
self-coupling (g=1) converts the wave-8 PROLATE bubble (sigma_x/z ~ 0.329) toward the doctrine's
OBLATE reference (sigma_x/z ~ 2.510; sigma_x/y ~ 1.618). Honest Reported Negatives are
deliverables.

Run from the repo root:  python research/helix_solver/triaxial3d_feed_probe.py
"""

import numpy as np

from phi_grid import PHI
import triaxial3d as t3

N = 64
SIM = (PHI, 1.0, PHI * PHI)          # the sim's box-extent cell sizes (phi, 1, phi^2)
TRACE = (200, 600, 1200, 1800, 2400) # step counts traced (wave-8 convention)
DT = 0.02
SOURCE_STRENGTH = 0.5                # live-sim source_strength (main.tscn)
G_N = 1.0                            # IC-consistent scale (total; see prereg S1.3)
EXTENT = tuple(x * 32.0 for x in SIM)  # half-box extents; L_i = 2*extent_i; h_i = extent_i/(N/2)
HALFN = N / 2.0
PHI_INV2 = 0.3819660112501051        # phi^-2 (q denominator, cassi_nbody_gravity.glsl)
CLAMP_HI = 0.72                      # pi/rho upper clamp

# ---------------------------------------------------------------------------
# Q2 Poisson: the engine's exact spectral solve  nabla^2 Phi = rho,
# Phi_hat = -rho_hat / k^2, k = 0 nulled,  k_i = 2*pi*kx_i / L_i,  L_i = 2*extent_i.
# ---------------------------------------------------------------------------

def make_poisson(extent):
    """Return solve(rho)->Phi for the periodic (phi,1,phi^2) box (deterministic)."""
    kx_int = np.fft.fftfreq(N) * N               # cyclic labels: 0..N/2-1, -N/2..-1
    # physical wavenumbers k_i = 2*pi*kx_i / L_i, L_i = 2*extent_i  (cassi_poisson.glsl k2_of_cell)
    kw = [2.0 * np.pi * kx_int / (2.0 * extent[a]) for a in range(3)]
    k2 = (kw[0][:, None, None] ** 2
          + kw[1][None, :, None] ** 2
          + kw[2][None, None, :] ** 2)
    k2[0, 0, 0] = 1.0                            # avoid 0/0 at k=0 (mode nulled in solve below)

    def solve(rho):
        rho_hat = np.fft.fftn(rho)
        phi_hat = -rho_hat / k2
        phi_hat[0, 0, 0] = 0.0                    # k = 0 nulled (mean of Phi unphysical)
        return np.fft.ifftn(phi_hat).real
    return solve


def grad_phi(phi, h):
    """3-point cell-centered central-difference gradient of Phi (the engine's grad_pass,
    gradient_order=2). Returns (gx, gy, gz), each the derivative along array axis 0/1/2."""
    hx, hy, hz = h
    gx = (np.roll(phi, 1, 0) - np.roll(phi, -1, 0)) / (2.0 * hx)
    gy = (np.roll(phi, 1, 1) - np.roll(phi, -1, 1)) / (2.0 * hy)
    gz = (np.roll(phi, 1, 2) - np.roll(phi, -1, 2)) / (2.0 * hz)
    return gx, gy, gz


def div_vec(fx, fy, fz, h):
    """3-point periodic central-difference divergence of a vector field (matches grad_phi)."""
    hx, hy, hz = h
    dx = (np.roll(fx, 1, 0) - np.roll(fx, -1, 0)) / (2.0 * hx)
    dy = (np.roll(fy, 1, 1) - np.roll(fy, -1, 1)) / (2.0 * hy)
    dz = (np.roll(fz, 1, 2) - np.roll(fz, -1, 2)) / (2.0 * hz)
    return dx + dy + dz


class GravityTwoFluid3D:
    """TwoFluid3D + the frozen scalar Poisson-gravity self-coupling (prereg S1.3).

    Bit-identical to t3.TwoFluid3D when G_N == 0 (verified by G-determinism/control anchors).
    The two-fluid is SCALAR: the engine's vector body force a = -G_N*(pi/rho)*grad(Phi) couples
    through the momentum-continuity combination as the scalar source
        S_grav = +G_N * div( m * grad(Phi) ),   m = rho * clamp((EY-EI)/rho, 0, 0.72),
    with Phi the spectral solve of nabla^2 Phi = |EY+EI| (k=0 nulled). S_grav is added half to
    EY's acceleration and half to EI's, so the total charge rho = EY+EI receives S_grav.
    """

    def __init__(self, h, w0_2=t3.OMEGA2, c=t3.C, dt=t3.DT, g_n=G_N, extent=EXTENT):
        self.h = tuple(float(x) for x in h)
        self.lap = t3.make_lap(self.h)
        self.w0_2 = float(w0_2)
        self.c = float(c)
        self.dt = float(dt)
        self.g_n = float(g_n)
        self._solve = make_poisson(tuple(float(x) for x in extent))
        self._kicked = False

    def gravity_source(self, ey, ei):
        """The scalar S_grav; returns 0.0 (no-op) when g_n == 0."""
        if self.g_n == 0.0:
            return 0.0
        rho = ey + ei
        rho_source = np.abs(rho)
        phi = self._solve(rho_source)
        gx, gy, gz = grad_phi(phi, self.h)
        with np.errstate(divide="ignore", invalid="ignore"):
            pi_over_rho = np.where(np.abs(rho) < 1e-6, 0.0,
                                   np.clip((ey - ei) / rho, 0.0, CLAMP_HI))
        m = rho * pi_over_rho
        return self.g_n * div_vec(m * gx, m * gy, m * gz, self.h)

    def kick(self, ey, ei, vey, vei):
        half = 0.5 * self.dt
        diff = ey - PHI * ei
        s = self.gravity_source(ey, ei)
        aey = self.c * self.c * self.lap(ey) - self.w0_2 * diff + 0.5 * s
        aei = self.c * self.c * self.lap(ei) + self.w0_2 * diff + 0.5 * s
        return vey + half * aey, vei + half * aei

    def step(self, ey, ei, vey, vei):
        dt = self.dt
        if not self._kicked:
            vey, vei = self.kick(ey, ei, vey, vei)
            self._kicked = True
        diff = ey - PHI * ei
        s = self.gravity_source(ey, ei)
        aey = self.c * self.c * self.lap(ey) - self.w0_2 * diff + 0.5 * s
        aei = self.c * self.c * self.lap(ei) + self.w0_2 * diff + 0.5 * s
        vey = vey + dt * aey
        vei = vei + dt * aei
        ey = ey + dt * vey
        ei = ei + dt * vei
        return ey, ei, vey, vei


# ---------------------------------------------------------------------------
# Q1a: the TSC mass deposit (cassi_mass_deposit.glsl 27-cell separable B-spline)
# ---------------------------------------------------------------------------

def tsc_deposit(N=N, h=SIM, sig_phys_frac=0.08, total_mass=1.0):
    """A physically-round Gaussian mass cloud at the box center, scattered through the exact
    TSC B-spline kernel ([0.125, 0.75, 0.125] 1D weights at f=0, separable, partition of unity).
    Returns the deposited rho_mass (total mass = total_mass)."""
    gz, gy, gx = np.mgrid[0:N, 0:N, 0:N]
    c = N / 2.0
    w = sig_phys_frac * N
    hx, hy, hz = h
    x = (gx - c) * hx
    y = (gy - c) * hy
    z = (gz - c) * hz
    m = np.exp(-(x * x + y * y + z * z) / (2.0 * w * w))
    m = m / m.sum() * total_mass
    for ax in range(3):
        m = 0.75 * m + 0.125 * (np.roll(m, 1, ax) + np.roll(m, -1, ax))
    return m


def make_gain_profiles(N=N, source_strength=SOURCE_STRENGTH):
    """The Q1b field-gain profiles: g_ey (centered) and g_ei (offset at (0.7,0.8,0.6)*halfn),
    as the shader's source_ey/source_ei field-gain part (source_strength * exp(-4 r2))."""
    halfn = N / 2.0
    i = np.arange(N)
    di = (i - halfn) / halfn
    r2 = di[:, None, None] ** 2 + di[None, :, None] ** 2 + di[None, None, :] ** 2
    g_ey = source_strength * np.exp(-4.0 * r2)
    dox = (i - 0.7 * halfn) / halfn
    doy = (i - 0.8 * halfn) / halfn
    doz = (i - 0.6 * halfn) / halfn
    r2_off = dox[:, None, None] ** 2 + doy[None, :, None] ** 2 + doz[None, None, :] ** 2
    g_ei = source_strength * 0.707 * np.exp(-4.0 * r2_off)
    return g_ey, g_ei


# ---------------------------------------------------------------------------
# Arm runners
# ---------------------------------------------------------------------------

def trace_control(h=SIM, trace=TRACE):
    """Pure wave-8 case (TwoFluid3D). MUST reproduce sigma_x/z ~ 0.329 at t=2400."""
    g = t3.TwoFluid3D(h)
    ey, ei = t3.seed_bubble3d(N, h)
    ve = wi = np.zeros_like(ey)
    p0 = float((ey + ei).max())
    out = []
    last = 0
    for target in trace:
        for _ in range(target - last):
            ey, ei, ve, wi = g.step(ey, ei, ve, wi)
        last = target
        rho = ey + ei
        sx, sy, sz = t3.sigma3(rho, g.h)
        out.append((target, rho.max() / p0, sx / sy, sx / sz))
    return out


def trace_feed(h=SIM, trace=TRACE, rho_mass=None, gain=None):
    """TwoFluid3D + per-step field injection (after the leapfrog, as the shader's ey_new).

    rho_mass != None -> Q1a deposit feedback: EY += 0.001*rho_mass*dt^2, EI += 0.000707*rho_mass*dt^2.
    gain == (g_ey, g_ei) -> Q1b field-gain: EY += g_ey*dt^2, EI += g_ei*dt^2.
    """
    g = t3.TwoFluid3D(h)
    ey, ei = t3.seed_bubble3d(N, h)
    ve = wi = np.zeros_like(ey)
    p0 = float((ey + ei).max())
    dt2 = g.dt * g.dt
    out = []
    last = 0
    for target in trace:
        for _ in range(target - last):
            ey, ei, ve, wi = g.step(ey, ei, ve, wi)
            if rho_mass is not None:
                ey = ey + 0.001 * rho_mass * dt2
                ei = ei + 0.000707 * rho_mass * dt2
            if gain is not None:
                ey = ey + gain[0] * dt2
                ei = ei + gain[1] * dt2
        last = target
        rho = ey + ei
        sx, sy, sz = t3.sigma3(rho, g.h)
        out.append((target, rho.max() / p0, sx / sy, sx / sz))
    return out


def trace_gravity(h=SIM, trace=TRACE, g_n=G_N):
    """GravityTwoFluid3D (Poisson self-coupling)."""
    g = GravityTwoFluid3D(h, g_n=g_n)
    ey, ei = t3.seed_bubble3d(N, h)
    ve = wi = np.zeros_like(ey)
    p0 = float((ey + ei).max())
    out = []
    last = 0
    for target in trace:
        for _ in range(target - last):
            ey, ei, ve, wi = g.step(ey, ei, ve, wi)
        last = target
        rho = ey + ei
        sx, sy, sz = t3.sigma3(rho, g.h)
        out.append((target, rho.max() / p0, sx / sy, sx / sz))
    return out


def verdict(name, arm_final_xz, control_final_xz, arm_final_pk, control_final_pk):
    """The frozen decision tree (prereg S2). A deterministic sigma_x/z <= 0.6 is a definitive
    no-material-rise negative (the floor guards against UNMEASURABLE shape, which cannot arise in
    a no-RNG run); the 10% amplitude floor is therefore reported as a caveat flag, not the primary
    verdict -- see the prereg's amended-rule note and the report's floor-calibration disclosure.
    """
    floor_flag = ("  [amplitude-floor caveat: peak/peak0 < 0.10 "
                  f"(control {control_final_pk:.3f})]") if arm_final_pk < 0.10 else ""
    if not np.isfinite(arm_final_xz) or not np.isfinite(arm_final_pk):
        return "INCONCLUSIVE (non-finite field)"
    if control_final_xz > 0.6:
        return "INCONCLUSIVE (control failed to reproduce the wave-8 prolate anchor <=0.6)"
    if arm_final_xz >= 1.0:
        band = " [in 1.8-3.2]" if 1.8 <= arm_final_xz <= 3.2 else ""
        return f"SUPPORTS{band}{floor_flag}"
    return f"CONTRADICTS / DOES NOT EMERGE{floor_flag}"


def main() -> None:
    print("== wave 9: source-feed (Q1a/Q1b) and Poisson-gravity (Q2) on the sim's (phi,1,phi^2) operator ==")
    print(f"  reference lines (NOT gates): sigma_x/z = 2.510 (unverified Python-PDE), "
          f"sigma_x/y = {PHI:.3f}; wave-8 prolate baseline sigma_x/z = 0.329, sigma_x/y = 0.842")
    print(f"  pins: N={N}, dt={DT}, omega0^2={t3.OMEGA2}, c={t3.C}, h=(phi,1,phi^2), 2400 steps, "
          f"round seed; Q1a source_strength=0.0 (deposit only), Q1b source_strength={SOURCE_STRENGTH}, "
          f"Q2 G_N={G_N} (g=1)")

    control = trace_control()

    print("\n  (control) pure wave-8 case (no feed, no gravity):")
    for t, pk, rxy, rxz in control:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")

    rho_mass = tsc_deposit()
    print(f"\n  (Q1a) TSC mass-deposit feedback (0.001*rho_mass*dt^2 on EY, 0.000707*rho_mass*dt^2 on EI):")
    q1a = trace_feed(rho_mass=rho_mass)
    for t, pk, rxy, rxz in q1a:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")

    g_ey, g_ei = make_gain_profiles()
    print(f"\n  (Q1b) source_strength field-gain ({SOURCE_STRENGTH} centered EY, 0.707*{SOURCE_STRENGTH} offset EI):")
    q1b = trace_feed(gain=(g_ey, g_ei))
    for t, pk, rxy, rxz in q1b:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")

    print(f"\n  (Q2) Poisson-gravity self-coupling (g=1, G_N={G_N}):")
    q2 = trace_gravity()
    for t, pk, rxy, rxz in q2:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")

    # --- frozen verdicts (prereg S2) ----------------------------------------
    c_xz = control[-1][3]
    c_pk = control[-1][1]
    print()
    print("== frozen verdicts (primary statistic sigma_x/z @ t=2400) ==")
    print(f"  control sigma_x/z @2400 = {c_xz:.3f} (wave-8 anchor ~0.329; prolate <= 0.6), "
          f"peak/p0 = {c_pk:.3f}")
    for name, arm in (("Q1a", q1a), ("Q1b", q1b), ("Q2", q2)):
        v = verdict(name, arm[-1][3], c_xz, arm[-1][1], c_pk)
        print(f"  {name}: sigma_x/z @2400 = {arm[-1][3]:.3f}  (sigma_x/y = {arm[-1][2]:.3f}, "
              f"peak/p0 = {arm[-1][1]:.3f})  ->  {v}")
    print("done")


if __name__ == "__main__":
    main()
