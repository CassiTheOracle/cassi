"""triaxial3d.py -- the full-3D oblate triaxial spheroid two-fluid probing machinery.

Wave 6, per triaxial3d_prereg.md. The sim's EXACT 3D 19-point anisotropic periodic
Laplacian (cassi_two_fluid.glsl lap_ey_at) as a MATRIX-FREE np.roll stencil — the
uniform-Cartesian-grid composition of the axial (waves 1-4) and transverse
(waves 5a/5a-followup) operators. The phi-arm uses physical cell sizes
h = (phi, 1, 1/phi) (x=Yang, y=Yin, z=string): the doctrine's oblate-triaxial
spheroid geometry. The symmetric control uses h = (1,1,1).

Provides (deterministic, numpy):
  - lap3d(u, N, h): the 3D 19-point anisotropic Laplacian (matrix-free).
  - TwoFluid3D: the two-fluid leapfrog with the half-kick staggered start.
  - seed_bubble3d(N, h, amp) -> (EY, EI) symmetric co-located 3D Gaussians.
  - sigma3(rho, N, h) -> (sx, sy, sz) second moments with physical scaling.
  - slice_edge(rho, N, h, theta) -> the bias-free edge ratio on the peak-z Yin-Yin...
    (the x,y plane through the peak), reusing edge_proxy.edge_ratio.
Run: import triaxial3d (no CLI side effects).
"""

from __future__ import annotations

import numpy as np
from math import isfinite

from phi_grid import PHI
import edge_proxy as ep

OMEGA2 = 20.0
C = 1.0
DT = 0.02
N = 64


# --- the sim's exact 3D 19-point anisotropic Laplacian (matrix-free) -------------

def lap_weights(h):
    """The shader's per-axis and face-diagonal weights for cell sizes h=(hx,hy,hz).

    Returns (ax, ay, az, bxy, bxz, byz) exactly as cassi_two_fluid.glsl:
      h02 = min(h)^2;  b_xy = (1/3) h02/(hx^2+hy^2);  ... ;  a_x = h02/hx^2 - 2(b_xy+b_xz).
    """
    hx, hy, hz = h
    h02 = min(h) ** 2
    bxy = (1.0 / 3.0) * h02 / (hx * hx + hy * hy)
    bxz = (1.0 / 3.0) * h02 / (hx * hx + hz * hz)
    byz = (1.0 / 3.0) * h02 / (hy * hy + hz * hz)
    ax = h02 / (hx * hx) - 2.0 * (bxy + bxz)
    ay = h02 / (hy * hy) - 2.0 * (bxy + byz)
    az = h02 / (hz * hz) - 2.0 * (bxz + byz)
    return ax, ay, az, bxy, bxz, byz


def lap3d(u):
    """The 3D 19-point stencil applied per the shader (u an (N,N,N) float array)."""
    N = u.shape[0]
    h = (PHI, 1.0, 1.0 / PHI)   # NOTE: lap3d always uses the phi-arm h; the control
    ax, ay, az, bxy, bxz, byz = lap_weights(h)
    e = u
    axis_x = np.roll(u, 1, 0) + np.roll(u, -1, 0) - 2.0 * e
    axis_y = np.roll(u, 1, 1) + np.roll(u, -1, 1) - 2.0 * e
    axis_z = np.roll(u, 1, 2) + np.roll(u, -1, 2) - 2.0 * e
    fd_xy = (np.roll(np.roll(u, 1, 0), 1, 1) + np.roll(np.roll(u, -1, 0), 1, 1)
             + np.roll(np.roll(u, 1, 0), -1, 1) + np.roll(np.roll(u, -1, 0), -1, 1) - 4.0 * e)
    fd_xz = (np.roll(np.roll(u, 1, 0), 1, 2) + np.roll(np.roll(u, -1, 0), 1, 2)
             + np.roll(np.roll(u, 1, 0), -1, 2) + np.roll(np.roll(u, -1, 0), -1, 2) - 4.0 * e)
    fd_yz = (np.roll(np.roll(u, 1, 1), 1, 2) + np.roll(np.roll(u, -1, 1), 1, 2)
             + np.roll(np.roll(u, 1, 1), -1, 2) + np.roll(np.roll(u, -1, 1), -1, 2) - 4.0 * e)
    return ax * axis_x + ay * axis_y + az * axis_z + bxy * fd_xy + bxz * fd_xz + byz * fd_yz


def make_lap(h):
    """Return a Laplacian function bound to the given aspect h=(hx,hy,hz)."""
    ax, ay, az, bxy, bxz, byz = lap_weights(h)
    def _lap(u):
        e = u
        a_x = np.roll(u, 1, 0) + np.roll(u, -1, 0) - 2.0 * e
        a_y = np.roll(u, 1, 1) + np.roll(u, -1, 1) - 2.0 * e
        a_z = np.roll(u, 1, 2) + np.roll(u, -1, 2) - 2.0 * e
        fd_xy = (np.roll(np.roll(u, 1, 0), 1, 1) + np.roll(np.roll(u, -1, 0), 1, 1)
                 + np.roll(np.roll(u, 1, 0), -1, 1) + np.roll(np.roll(u, -1, 0), -1, 1) - 4.0 * e)
        fd_xz = (np.roll(np.roll(u, 1, 0), 1, 2) + np.roll(np.roll(u, -1, 0), 1, 2)
                 + np.roll(np.roll(u, 1, 0), -1, 2) + np.roll(np.roll(u, -1, 0), -1, 2) - 4.0 * e)
        fd_yz = (np.roll(np.roll(u, 1, 1), 1, 2) + np.roll(np.roll(u, -1, 1), 1, 2)
                 + np.roll(np.roll(u, 1, 1), -1, 2) + np.roll(np.roll(u, -1, 1), -1, 2) - 4.0 * e)
        return (ax * a_x + ay * a_y + az * a_z
                + bxy * fd_xy + bxz * fd_xz + byz * fd_yz)
    return _lap


# --- the two-fluid wave -----------------------------------------------------------

class TwoFluid3D:
    """The sim's two-fluid PDE on the given 3D periodic Laplacian.

    d2 EY/dt2 = c^2 L EY - w0^2 (EY - phi EI);  d2 EI/dt2 = c^2 L EI + w0^2 (EY - phi EI).
    Leapfrog with the half-kick staggered start (genuinely 2nd-order). Deterministic.
    """

    def __init__(self, h, w0_2=OMEGA2, c=C, dt=DT):
        self.h = tuple(float(x) for x in h)
        self.lap = make_lap(self.h)
        self.w0_2 = float(w0_2)
        self.c = float(c)
        self.dt = float(dt)
        self._kicked = False

    def kick(self, ey, ei, vey, vei):
        half = 0.5 * self.dt
        diff = ey - PHI * ei
        aey = self.c * self.c * self.lap(ey) - self.w0_2 * diff
        aei = self.c * self.c * self.lap(ei) + self.w0_2 * diff
        return vey + half * aey, vei + half * aei

    def step(self, ey, ei, vey, vei):
        dt = self.dt
        if not self._kicked:
            vey, vei = self.kick(ey, ei, vey, vei)
            self._kicked = True
        diff = ey - PHI * ei
        aey = self.c * self.c * self.lap(ey) - self.w0_2 * diff
        aei = self.c * self.c * self.lap(ei) + self.w0_2 * diff
        vey = vey + dt * aey
        vei = vei + dt * aei
        ey = ey + dt * vey
        ei = ei + dt * vei
        return ey, ei, vey, vei


# --- the seed and measures --------------------------------------------------------

def seed_bubble3d(N, h, amp=0.3, sig_phys_frac=0.08):
    """A single PHYSICALLY-ISOTROPIC 3D Gaussian; EY and EI co-located (EI = phi^-1 EY).

    The same physical width w = sig_phys_frac*N on every axis, so the seed's cell-space
    widths differ per axis (w/h_i) to cancel the aspect: ANY emergent sigma anisotropy is
    then purely the operator's effect, not the seed's (the honest discriminator).
    """
    gz, gy, gx = np.mgrid[0:N, 0:N, 0:N]
    c = N / 2.0
    w = sig_phys_frac * N
    hx, hy, hz = h
    x_phys = (gx - c) * hx
    y_phys = (gy - c) * hy
    z_phys = (gz - c) * hz
    e = amp * np.exp(-(x_phys * x_phys + y_phys * y_phys + z_phys * z_phys) / (2.0 * w * w))
    return e, e * (1.0 / PHI)


def sigma3(rho, h):
    """Second moments of |rho| on the 3D grid -> (sx, sy, sz) physically scaled."""
    N = rho.shape[0]
    m = np.abs(rho)
    tot = m.sum()
    gz, gy, gx = np.mgrid[0:N, 0:N, 0:N]
    mx = (gx * m).sum() / tot
    my = (gy * m).sum() / tot
    mz = (gz * m).sum() / tot
    sx = np.sqrt(((gx - mx) ** 2 * m).sum() / tot) * h[0]
    sy = np.sqrt(((gy - my) ** 2 * m).sum() / tot) * h[1]
    sz = np.sqrt(((gz - mz) ** 2 * m).sum() / tot) * h[2]
    return sx, sy, sz


def slice_edge(rho, h, theta=0.45):
    """The bias-free edge ratio on the z-slice through the peak (the Yang-Yin plane).

    Reuses edge_proxy.edge_ratio on the 2D (x,y) slice at the peak-z, with the in-plane
    aspect (h[0], h[1]). Returns (ratio, ga, gd) or (nan,..) if no clean crossing.
    """
    g = np.abs(rho)
    flat = int(np.argmax(g))
    N = g.shape[0]
    k = flat % N                       # the peak-z plane index
    plane = g[:, :, k]                 # the Yang-Yin slice through the peak
    return ep.edge_ratio(plane, N, (h[0], h[1]), theta=theta)
