"""triaxial3d_particle_probe.py -- wave 10: particle-nbody gravity on the sim's (phi,1,phi^2) box.

Per triaxial3d_particle_prereg.md. Deterministic, matrix-free, seeded (no RNG in the physics).
Tests the engine's PARTICLE-gravity sector (the last untested one): a physically-round collisionless
particle cloud in the fully-periodic (phi,1,phi^2) box, under
  - A: no gravity (free-streaming control; must stay round),
  - B: engine gravity g=1, pi/rho = 1:  a = -G_N * grad(Phi),  Phi from the TSC-deposited density,
  - C: full composition: a = -G_N * (pi/rho) * grad(Phi) with pi/rho sampled from the evolving
       two-fluid field (wave-8 machinery) at each particle; the field evolves with the shader's
       always-on 0.001*rho_mass coupling; source_strength = 0.
Asks whether the particle sector imprints OBLATE (z-compressed) structure (sigma_x/z rising from
1.00 toward the doctrine band 1.8-3.2), and whether the particle-driven mass deforms the field
coherence bubble. Honest CONTRADICTS are deliverables.

Measurement frame: TRUE engine frame -- axis0 = x (phi-extent), axis1 = y, axis2 = z (phi^2-extent);
"round" = sigma_x/z = 1.000, "oblate" = sigma_x/z > 1. The arm-C field is also cross-referenced
with triaxial3d.sigma3 (the wave-8/9 transposed labeling).

Run from the repo root:  python research/helix_solver/triaxial3d_particle_probe.py
"""

import numpy as np

from phi_grid import PHI
import triaxial3d as t3
from triaxial3d_feed_probe import make_poisson, grad_phi, N, SIM, EXTENT, G_N, DT, CLAMP_HI

NP = 32768                         # particle count (frozen)
SIGMA0 = 0.08 * N                  # physical seed radius (matches seed_bubble3d)
RNG_SEED = 42                      # fixed RNG seed (initial positions only)
TRACE = (200, 600, 1200, 1800, 2400)
HALFN = N / 2.0
EXTENT_ARR = np.array(EXTENT)      # per-axis half-extents (phi,1,phi^2)*32
H_ARR = np.array(SIM)              # per-axis cell sizes (phi,1,phi^2)
BOX_W = 2.0 * EXTENT_ARR           # full box width per axis (torus period L_i)


# ---------------------------------------------------------------------------
# Particle seed (physically round: isotropic Gaussian in physical coordinates)
# ---------------------------------------------------------------------------

def seed_particles(np_=NP, sigma0=SIGMA0, rng_seed=RNG_SEED):
    """Positions (np_,3) in PHYSICAL coordinates (axis0=x=phi-ext, axis2=z=phi^2-ext),
    isotropic Gaussian sigma0, zero velocities."""
    rng = np.random.default_rng(rng_seed)
    p = rng.normal(0.0, sigma0, size=(np_, 3))
    return p, np.zeros_like(p)


def physical_to_cell(p):
    """Physical position -> continuous cell coords in [0, N) per axis."""
    return p / H_ARR[None, :] + HALFN


def wrap_physical(p):
    """Wrap physical positions into [-extent, extent) per axis."""
    return (p + EXTENT_ARR[None, :]) % BOX_W[None, :] - EXTENT_ARR[None, :]


def particle_sigma(p):
    """Per-axis std of physical positions -> (sx, sy, sz) (axis0=x, axis2=z)."""
    return p[:, 0].std(), p[:, 1].std(), p[:, 2].std()


# ---------------------------------------------------------------------------
# TSC deposit (cassi_mass_deposit.glsl 27-cell separable quadratic B-spline)
# ---------------------------------------------------------------------------

def tsc_weights(f):
    """1D TSC weights (wm, w0, wp) for fractional offset f in [0,1)."""
    wm = 0.5 * (0.5 - f) ** 2
    wp = np.where(f < 0.5, 0.5 * (0.5 + f) ** 2, 0.75 - (1.0 - f) ** 2)
    w0 = np.where(f < 0.5, 0.75 - f ** 2, 0.5 * (1.5 - f) ** 2)
    return wm, w0, wp


def deposit(cell_coords, mass):
    """Scatter per-particle mass into rho (N,N,N) via the 27-cell TSC kernel (periodic)."""
    rho = np.zeros((N, N, N))
    i0 = np.floor(cell_coords[:, 0]).astype(np.int64)
    j0 = np.floor(cell_coords[:, 1]).astype(np.int64)
    k0 = np.floor(cell_coords[:, 2]).astype(np.int64)
    fx = cell_coords[:, 0] - i0
    fy = cell_coords[:, 1] - j0
    fz = cell_coords[:, 2] - k0
    wxm, wx0, wxp = tsc_weights(fx)
    wym, wy0, wyp = tsc_weights(fy)
    wzm, wz0, wzp = tsc_weights(fz)
    wx = (wxm, wx0, wxp)
    wy = (wym, wy0, wyp)
    wz = (wzm, wz0, wzp)
    offs = (-1, 0, 1)
    for a in range(3):
        for b in range(3):
            for c in range(3):
                ii = (i0 + offs[a]) % N
                jj = (j0 + offs[b]) % N
                kk = (k0 + offs[c]) % N
                w = mass * (wx[a] * wy[b] * wz[c])
                np.add.at(rho, (ii, jj, kk), w)
    return rho


# ---------------------------------------------------------------------------
# Trilinear sampler (periodic)
# ---------------------------------------------------------------------------

def trilinear_sample(field, cell_coords):
    """Sample field (N,N,N) at cell coords (M,3) -> (M,) values, periodic."""
    fl = np.floor(cell_coords)
    i0 = fl[:, 0].astype(np.int64) % N
    j0 = fl[:, 1].astype(np.int64) % N
    k0 = fl[:, 2].astype(np.int64) % N
    fx = cell_coords[:, 0] - fl[:, 0]
    fy = cell_coords[:, 1] - fl[:, 1]
    fz = cell_coords[:, 2] - fl[:, 2]
    i1 = (i0 + 1) % N
    j1 = (j0 + 1) % N
    k1 = (k0 + 1) % N
    c000 = field[i0, j0, k0]; c100 = field[i1, j0, k0]
    c010 = field[i0, j1, k0]; c110 = field[i1, j1, k0]
    c001 = field[i0, j0, k1]; c101 = field[i1, j0, k1]
    c011 = field[i0, j1, k1]; c111 = field[i1, j1, k1]
    c00 = c000 * (1 - fx) + c100 * fx
    c10 = c010 * (1 - fx) + c110 * fx
    c01 = c001 * (1 - fx) + c101 * fx
    c11 = c011 * (1 - fx) + c111 * fx
    c0 = c00 * (1 - fy) + c10 * fy
    c1 = c01 * (1 - fy) + c11 * fy
    return c0 * (1 - fz) + c1 * fz


# ---------------------------------------------------------------------------
# Field sigma in the TRUE engine frame (axis0=x=phi, axis2=z=phi^2)
# ---------------------------------------------------------------------------

def field_sigma_physical(rho):
    """True-frame second moments of |rho|: axis0=x (h[0]=phi), axis1=y (h[1]=1),
    axis2=z (h[2]=phi^2). Returns (sx, sy, sz)."""
    m = np.abs(rho)
    tot = m.sum()
    gi = np.arange(N)
    g0 = gi[:, None, None]        # axis0
    g1 = gi[None, :, None]        # axis1
    g2 = gi[None, None, :]        # axis2
    c = HALFN
    x = (g0 - c) * H_ARR[0]
    y = (g1 - c) * H_ARR[1]
    z = (g2 - c) * H_ARR[2]
    mx = (x * m).sum() / tot
    my = (y * m).sum() / tot
    mz = (z * m).sum() / tot
    sx = np.sqrt(((x - mx) ** 2 * m).sum() / tot)
    sy = np.sqrt(((y - my) ** 2 * m).sum() / tot)
    sz = np.sqrt(((z - mz) ** 2 * m).sum() / tot)
    return sx, sy, sz


# ---------------------------------------------------------------------------
# Gravity-grid build + force (the engine's lagged-grid cached-acc KDK)
# ---------------------------------------------------------------------------

def build_gravity_grid(p, mass, solve):
    """deposit -> Poisson -> gradient. Returns (cell, rho, gx, gy, gz)."""
    cell = physical_to_cell(p)
    rho = deposit(cell, mass)
    phi = solve(rho)
    gx, gy, gz = grad_phi(phi, SIM)
    return cell, rho, gx, gy, gz


def force_from_grid(p_target, gx, gy, gz, g_n, pi_over_rho=None):
    """Sample the (pre-built) grid gradient at p_target; scale by -G_N * pi_over_rho.

    SIGN: triaxial3d_feed_probe.grad_phi returns the BACKWARD difference
    (phi[i-1]-phi[i+1])/(2h) = -grad(Phi) (its companion div_vec is also backward, so the two
    cancel inside wave-9's divergence-based source -- but here we use the gradient ALONE). The
    engine's attractive force is a = -G_N * grad(Phi) = +G_N * grad_phi(...); hence the + sign.
    pi_over_rho: None (arm B -> 1.0) or an (M,) array (arm C)."""
    cell = physical_to_cell(p_target)
    ax = trilinear_sample(gx, cell)
    ay = trilinear_sample(gy, cell)
    az = trilinear_sample(gz, cell)
    a = +g_n * np.stack([ax, ay, az], axis=1)
    if pi_over_rho is not None:
        a = a * pi_over_rho[:, None]
    return a


def pi_over_rho_field(ey, ei, cell):
    """pi/rho = clamp((EY-EI)/(EY+EI), 0, 0.72) sampled from the field at cell coords."""
    ey_s = trilinear_sample(ey, cell)
    ei_s = trilinear_sample(ei, cell)
    rho_f = ey_s + ei_s
    return np.where(np.abs(rho_f) < 1e-6, 0.0, np.clip((ey_s - ei_s) / rho_f, 0.0, CLAMP_HI))


# ---------------------------------------------------------------------------
# Arm runners
# ---------------------------------------------------------------------------

def run_arm_a(trace=TRACE):
    """Free-streaming control: no gravity, zero velocity -> positions fixed."""
    p, _v = seed_particles()
    out = []
    for t in trace:
        sx, sy, sz = particle_sigma(p)
        out.append((t, sx / sy, sx / sz))
    return out


def run_arm_b(trace=TRACE, g_n=G_N):
    """Particle self-gravity, g=1, pi/rho=1: a = -G_N * grad(Phi), lagged-grid KDK."""
    solve = make_poisson(EXTENT)
    p, v = seed_particles()
    mass = np.full(NP, 1.0 / NP)

    cell, rho, gx, gy, gz = build_gravity_grid(p, mass, solve)
    peak0 = float(rho.max())
    acc = force_from_grid(p, gx, gy, gz, g_n)

    out = []
    last = 0
    for target in trace:
        for _ in range(target - last):
            cell, rho, gx, gy, gz = build_gravity_grid(p, mass, solve)
            v_half = v + acc * (0.5 * DT)
            p_new = wrap_physical(p + v_half * DT)
            a_new = force_from_grid(p_new, gx, gy, gz, g_n)
            v_new = v_half + a_new * (0.5 * DT)
            p, v, acc = p_new, v_new, a_new
        last = target
        sx, sy, sz = particle_sigma(p)
        peak = float(deposit(physical_to_cell(p), mass).max())
        out.append((target, peak / peak0, sx / sy, sx / sz))
    return out


def arm_b_positions(nsteps):
    """Final particle positions after nsteps of arm-B gravity (for the determinism gate)."""
    solve = make_poisson(EXTENT)
    p, v = seed_particles()
    mass = np.full(NP, 1.0 / NP)
    cell, rho, gx, gy, gz = build_gravity_grid(p, mass, solve)
    acc = force_from_grid(p, gx, gy, gz, G_N)
    for _ in range(nsteps):
        cell, rho, gx, gy, gz = build_gravity_grid(p, mass, solve)
        v_half = v + acc * (0.5 * DT)
        p_new = wrap_physical(p + v_half * DT)
        a_new = force_from_grid(p_new, gx, gy, gz, G_N)
        v_new = v_half + a_new * (0.5 * DT)
        p, v, acc = p_new, v_new, a_new
    return p


def run_arm_c(trace=TRACE, g_n=G_N):
    """Full composition: particle force uses pi/rho sampled from the evolving two-fluid field;
    the field evolves via wave-8 machinery + the 0.001*rho_mass coupling (source_strength=0)."""
    solve = make_poisson(EXTENT)
    p, v = seed_particles()
    mass = np.full(NP, 1.0 / NP)

    gf = t3.TwoFluid3D(SIM)
    ey, ei = t3.seed_bubble3d(N, SIM)
    vey = vei = np.zeros_like(ey)
    dt2 = gf.dt * gf.dt

    # warm-up (the engine updates the field BEFORE the nbody force)
    cell, rho, gx, gy, gz = build_gravity_grid(p, mass, solve)
    peak0 = float(rho.max())
    ey, ei, vey, vei = gf.step(ey, ei, vey, vei)
    ey = ey + 0.001 * rho * dt2
    ei = ei + 0.000707 * rho * dt2
    pi = pi_over_rho_field(ey, ei, cell)
    acc = force_from_grid(p, gx, gy, gz, g_n, pi)

    out = []
    last = 0
    for target in trace:
        for _ in range(target - last):
            cell, rho, gx, gy, gz = build_gravity_grid(p, mass, solve)
            # field step (engine order: PDE after Poisson, before the nbody force)
            ey, ei, vey, vei = gf.step(ey, ei, vey, vei)
            ey = ey + 0.001 * rho * dt2
            ei = ei + 0.000707 * rho * dt2
            # particle KDK (lagged grid gradient; pi/rho from the UPDATED field at p_new)
            v_half = v + acc * (0.5 * DT)
            p_new = wrap_physical(p + v_half * DT)
            pi = pi_over_rho_field(ey, ei, physical_to_cell(p_new))
            a_new = force_from_grid(p_new, gx, gy, gz, g_n, pi)
            v_new = v_half + a_new * (0.5 * DT)
            p, v, acc = p_new, v_new, a_new
        last = target
        sx, sy, sz = particle_sigma(p)
        fpx, fpy, fpz = field_sigma_physical(ey + ei)
        s3x, s3y, s3z = t3.sigma3(ey + ei, SIM)
        peak = float(deposit(physical_to_cell(p), mass).max())
        out.append((target, peak / peak0, sx / sy, sx / sz,
                    fpx / fpz, fpx / fpy, s3x / s3z))
    return out


def run_field_baseline(trace=TRACE):
    """Wave-9 field-only control (wave-8 machinery, no particles) -- the arm-C comparison
    baseline for the field bubble's shape."""
    g = t3.TwoFluid3D(SIM)
    ey, ei = t3.seed_bubble3d(N, SIM)
    ve = wi = np.zeros_like(ey)
    out = []
    last = 0
    for target in trace:
        for _ in range(target - last):
            ey, ei, ve, wi = g.step(ey, ei, ve, wi)
        last = target
        rho = ey + ei
        fx, fy, fz = field_sigma_physical(rho)
        s3x, s3y, s3z = t3.sigma3(rho, SIM)
        out.append((target, fx / fz, fx / fy, s3x / s3z))
    return out


def main() -> None:
    print("== wave 10: particle-nbody gravity on the sim's (phi,1,phi^2) box ==")
    print(f"  reference lines (NOT gates): sigma_x/z=2.510, sigma_x/y=1.618 (unverified Python-PDE)")
    print(f"  pins: N={N}, N_p={NP}, sigma0={SIGMA0:.2f}, G_N={G_N}, g=1, dt={DT}, 2400 steps, "
          f"cold (zero-velocity) physically-round cloud, rng_seed={RNG_SEED}")

    a = run_arm_a()
    print("\n  (A) free-streaming control (no gravity; must stay round):")
    for t, rxy, rxz in a:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}")
    a_round = all(0.95 <= rxz <= 1.05 and 0.95 <= rxy <= 1.05 for _, rxy, rxz in a)

    print(f"\n  (B) engine gravity g=1, pi/rho=1 (a = -G_N*grad(Phi)):")
    b = run_arm_b()
    for t, pk, rxy, rxz in b:
        print(f"      t={t:>5}: sigma_x/y={rxy:.3f}  sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}")

    base = run_field_baseline()
    print("\n  (field baseline) wave-9 field-only control (no particles):")
    for t, f_xz, f_xy, s3_xz in base:
        print(f"      t={t:>5}: true sigma_x/z={f_xz:.3f}  true sigma_x/y={f_xy:.3f}  sigma3_x/z={s3_xz:.3f}")

    print(f"\n  (C) full composition (pi/rho from the two-fluid field; field + 0.001*rho_mass):")
    c = run_arm_c()
    for t, pk, rxy, rxz, f_xz, f_xy, s3_xz in c:
        print(f"      t={t:>5}: part sigma_x/y={rxy:.3f}  part sigma_x/z={rxz:.3f}  peak/p0={pk:.3f}  "
              f"| field sigma_x/z={f_xz:.3f} (sigma3={s3_xz:.3f})  field sigma_x/y={f_xy:.3f}")

    print()
    print("== frozen verdicts (primary statistic sigma_x/z @ t=2400) ==")
    a_xz = a[-1][2]
    print(f"  (A) control sigma_x/z @2400 = {a_xz:.3f} (round guard: {'PASS' if a_round else 'FAIL'})")

    # Q1: arm B (particle self-gravity) vs round. SUPPORTS requires entry into the doctrine band
    # 1.8-3.2; anything below (stays ~round or prolate) is CONTRADICTS (no material oblate rise).
    b_xz = b[-1][3]
    if not np.isfinite(b_xz):
        v1 = "INCONCLUSIVE (non-finite field)"
    elif not a_round:
        v1 = "INCONCLUSIVE (control failed the roundness guard)"
    elif b_xz >= 1.8:
        v1 = "SUPPORTS [1.8-3.2 band]"
    else:
        v1 = f"CONTRADICTS (no material oblate rise; sigma_x/z={b_xz:.3f} vs round control {a_xz:.3f})"
    print(f"  B: particle sigma_x/z @2400 = {b_xz:.3f}  (sigma_x/y={b[-1][2]:.3f}, "
          f"peak/p0={b[-1][1]:.3f})  ->  {v1}")

    # Q2: arm C field bubble (true frame sigma_x/z, tuple index 4) vs the field-only baseline.
    base_xz = base[-1][1]
    f_xz = c[-1][4]
    if not np.isfinite(f_xz):
        v2 = "INCONCLUSIVE (non-finite field)"
    elif not a_round:
        v2 = "INCONCLUSIVE (control failed the roundness guard)"
    elif f_xz >= 1.8:
        v2 = "SUPPORTS [1.8-3.2 band]"
    elif f_xz > base_xz + 0.1:
        v2 = f"CONTRADICTS (below the 1.8 band; rose {base_xz:.3f}->{f_xz:.3f} but not to 1.8)"
    else:
        v2 = f"CONTRADICTS (no material rise; {f_xz:.3f} vs field-only baseline {base_xz:.3f})"
    print(f"  C: field sigma_x/z @2400 = {f_xz:.3f} (true frame; sigma3={c[-1][6]:.3f}; "
          f"field-only baseline true={base_xz:.3f})  ->  {v2}")
    print(f"     C particle cloud sigma_x/z @2400 = {c[-1][3]:.3f} (vs B = {b_xz:.3f})")
    print("done")


if __name__ == "__main__":
    main()
