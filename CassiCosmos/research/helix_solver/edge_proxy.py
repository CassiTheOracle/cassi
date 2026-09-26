"""edge_proxy.py -- the bias-free edge-steepness proxy and its two legs.

Wave-5a-followup, per edge_proxy_prereg.md. The doctrine's 1.70 edge-steepness
ratio (bubble-edge-geometry.md SS2.2) is a property of the condensation field's
gradient, NOT of the Laplacian, and is independent of the threshold level:
    |grad C|_axial / |grad C|_diag = sqrt(4 phi^2/(1+phi^2)) ~ 1.70.

The former wave-5a "arc-proxy" (arc-length-to-cross on a fixed-angle ray) was
withdrawn as biased (its symmetric control read 0.54, not ~1). This replaces it
with the FULL gradient magnitude |grad f| evaluated at the crossing of a COMMON
level f=theta on the axial (Yin, +y) and diagonal (+45deg) rays -- using both
partial derivatives, which is what removes the ray-arc bias.

Two legs:
  - Leg G (ground truth): the analytic condensation field
        C(x,y) = cos(2 pi x / LY) cos(2 pi y / LI),  LI = LY/phi,
    must reproduce 1.70 (machinery validation); the uniform-wavenumber control
    must reproduce 1.0.
  - Leg D (dynamical): the two-fluid evolved field's coherence proxy
        C_dyn = 2 (EY^2 + EI^2) - 1
    measured on the phi-ellipsoid vs symmetric arms.

Deterministic, numpy-only. import edge_proxy.
"""

from __future__ import annotations

import numpy as np

from triaxial_laplacian import anisotropic_laplacian, TwoFluid2D, seed_bubble

PHI = 1.618033988749895
THETA = 0.45          # the doctrine's calibrated condensation threshold fraction


# --- the bias-free gradient-at-crossing proxy -------------------------------

def edge_ratio(f, N, aspect, theta=THETA):
    """The bias-free edge-steepness ratio |grad f|_axial / |grad f|_diag.

    f is a 2D (N,N) array on the [0,1)x[0,1) grid (the doctrine's condensation
    field or C_dyn). The PHYSICAL gradient field grad f = (df/dx_phys,
    df/dy_phys) is computed once with central differences and the physical
    cell scales (dx = aspect_x/N, dy = aspect_y/N). The axial (Yin, +y) and the
    diagonal (the doctrine's path to the NEIGHBOR SADDLE at (LY/4, LI/4), at
    atan(aspect_y/aspect_x) from Yang) roots of f = theta*f_peak are located by
    bisection, and the physical |grad f| is read at each crossing (bilinear of
    the gradient field). Using BOTH partial derivatives removes the ray-arc
    bias of the withdrawn proxy.
    """
    N = int(N)
    g = np.asarray(f, dtype=float)
    cy, cx = np.unravel_index(np.argmax(g), g.shape)
    cy, cx = int(cy), int(cx)
    gpeak = float(g[cy, cx])
    thr = theta * gpeak
    if thr <= 0:
        return float("nan"), float("nan"), float("nan")
    # physical cell scales
    dx_phys = aspect[0] / N
    dy_phys = aspect[1] / N
    # central-difference partial derivatives in CELL units, converted to physical
    dg_dy = np.zeros_like(g)
    dg_dx = np.zeros_like(g)
    dg_dy[1:-1, :] = (g[2:, :] - g[:-2, :]) / 2.0
    dg_dy[0, :] = (g[1, :] - g[-1, :]) / 2.0
    dg_dy[-1, :] = (g[0, :] - g[-2, :]) / 2.0
    dg_dx[:, 1:-1] = (g[:, 2:] - g[:, :-2]) / 2.0
    dg_dx[:, 0] = (g[:, 1] - g[:, -1]) / 2.0
    dg_dx[:, -1] = (g[:, 0] - g[:, -2]) / 2.0
    dg_dy /= dy_phys
    dg_dx /= dx_phys
    # the doctrine's edge STEepness is the directional derivative along each path
    # (bubble-edge-geometry.md SS2.2: |dC/ds|_diag = 1/2 sqrt(a^2+b^2) sqrt(1-C^2)),
    # i.e. grad C . s_hat, NOT the full normal magnitude |grad C| (which over-reads
    # the diagonal because it adds the cross-derivative). gm holds the two
    # partials; the directional derivative is composed at the crossing below.

    def cross_root(vx, vy):
        # locate the first crossing of f = thr along the physical ray from the
        # center, by advancing then bisecting; return |grad f| (bilinear of gm)
        # at the crossing.
        s = 0.0
        ds = 0.5 * min(dx_phys, dy_phys)
        prev_s = 0.0
        prev = g[cy, cx]
        while s < 1.0:
            x = cx + vx * s / dx_phys
            y = cy + vy * s / dy_phys
            if not (0 <= x < N - 1 and 0 <= y < N - 1):
                break
            v = bilinear(g, N, x, y)
            if np.isfinite(v) and v < thr and prev >= thr:
                # bisect between prev_s and s
                lo, hi = prev_s, s
                for _ in range(24):
                    mid = 0.5 * (lo + hi)
                    xm = cx + vx * mid / dx_phys
                    ym = cy + vy * mid / dy_phys
                    vm = bilinear(g, N, xm, ym)
                    if vm is None or np.isnan(vm):
                        break
                    if vm > thr:
                        lo = mid
                    else:
                        hi = mid
                xc = cx + vx * lo / dx_phys
                yc = cy + vy * lo / dy_phys
                # directional derivative along s_hat = grad f . s_hat
                dir_deriv = bilinear(dg_dx, N, xc, yc) * vx + bilinear(dg_dy, N, xc, yc) * vy
                return abs(dir_deriv)
            if np.isfinite(v):
                prev = v
                prev_s = s
            s += ds
        return float("nan")

    ga = cross_root(0.0, 1.0)      # axial (Yin) -> toward void
    # the diagonal toward the neighbor saddle at (LY/4, LI/4): physical
    # direction atan(aspect_y/aspect_x) from Yang toward Yin
    psi = np.arctan2(aspect[1], aspect[0])
    gd = cross_root(np.cos(psi), np.sin(psi))
    if np.isfinite(ga) and np.isfinite(gd) and ga > 1e-12 and gd > 1e-12:
        return ga / gd, ga, gd
    return float("nan"), ga, gd


def bilinear(g, N, x, y):
    x0 = int(np.floor(x)); y0 = int(np.floor(y))
    if not (0 <= x0 < N - 1 and 0 <= y0 < N - 1):
        return float("nan")
    fx, fy = x - x0, y - y0
    return (g[y0, x0] * (1 - fx) * (1 - fy) + g[y0, x0 + 1] * fx * (1 - fy)
            + g[y0 + 1, x0] * (1 - fx) * fy + g[y0 + 1, x0 + 1] * fx * fy)


# --- Leg G: the analytic condensation fields --------------------------------

def cond_field(N, kx, ky):
    """C(x,y) = cos(kx x) cos(ky y) on the [0,1)x[0,1) grid -> (N,N)."""
    xs = np.arange(N) / N
    gx, gy = np.meshgrid(xs, xs)
    return np.cos(2 * np.pi * kx * gx) * np.cos(2 * np.pi * ky * gy)


def fit_cond_field(N):
    """The doctrine's phi-ellipsoid condensation field with LY = 0.5 (a clean
    half-domain fit), LI = LY/phi. kx = 2/LY, ky = 2/LI -> ky = phi kx."""
    kx = 2.0 / 0.5           # a wavelength LY = 0.5 (one full period across half)
    ky = PHI * kx
    return cond_field(N, kx * 0.5, ky * 0.5)


def control_cond_field(N, k=2.0):
    """The uniform-wavenumber (symmetric) control: kx = ky -> no anisotropy."""
    return cond_field(N, k * 0.5, k * 0.5)


# --- Leg D: the dynamical two-fluid arms ------------------------------------

def run_arm(aspect, steps=600, N=96):
    """Evolve the two-fluid wave from a symmetric Gaussian bubble; return
    C_dyn = 2(EY^2+EI^2) - 1 reshaped (N,N) and the aspect."""
    L = anisotropic_laplacian(N, aspect)
    ey, ei = seed_bubble(N, aspect)
    ve = wi = np.zeros(N * N)
    g = TwoFluid2D(L)
    for _ in range(steps):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    rho = ey * ey + ei * ei
    c_dyn = 2.0 * rho.reshape(N, N) - 1.0
    return c_dyn, aspect


if __name__ == "__main__":
    # quick self-check: the analytic fit must ~1.70, the control ~1.0
    N = 96
    cf = fit_cond_field(N)
    cc = control_cond_field(N)
    r_fit, ga, gd = edge_ratio(cf, N, (PHI, 1.0))
    r_ctl, ga_c, gd_c = edge_ratio(cc, N, (1.0, 1.0))
    print(f"  Leg G phi-fit:      edge ratio = {r_fit:.3f} (aim 1.70), |g|_a={ga:.3f} |g|_d={gd:.3f}")
    print(f"  Leg G control:      edge ratio = {r_ctl:.3f} (aim 1.00), |g|_a={ga_c:.3f} |g|_d={gd_c:.3f}")
