"""triaxial_laplacian.py -- the phi-ellipsoid vs symmetric transverse Laplacian.

Wave-5a probe machinery, per CassiCosmos/research/helix_solver/triaxial_prereg.md.

Two 2D transverse operators (the Yang-Yin plane) with the SIM'S OWN anisotropic
19-point finite-volume stencil (cassi_two_fluid.glsl lap_ey_at): the phi-ellipsoid
arm uses per-axis weights with aspect (hx, hy) ∝ (phi, 1); the symmetric control
uses the uniform aspect. A Gaussian bubble is evolved by the two-fluid wave and
the emergent shape (sigma ratios), edge-steepness anisotropy (1.70) and radial
ring ladder (0.618/0.786) are measured.

Provides (deterministic, numpy):
  - anisotropic_laplacian(N, aspect): the FV 9-point 2D operator with the sim's
    per-axis weights, reduced from the 19-point to the 2D Yang-Yin plane.
  - TwoFluid2D: the two-fluid leapfrog on the 2D operator.
  - sigma_ratios(rho), edge_anisotropy(rho), ring_ladder_probe(rho): the measures.
"""

from __future__ import annotations

import numpy as np

PHI = 1.618033988749895
THETA = 0.45          # the condensation threshold (bubble-edge-geometry.md SS1.2)


def anisotropic_laplacian(N, aspect):
    """The 2D finite-volume Laplacian with the sim's anisotropic per-axis weights.

    aspect = (hx, hy) per-axis cell sizes. Weights (the 19-point's 2D reduction,
    matching cassi_two_fluid.glsl): b = (1/3) h0^2/(hx^2+hy^2), a_i = h0^2/hi^2 - 2b,
    h0 = min(hx,hy). Periodic boundaries.
    """
    hx, hy = aspect
    h0 = min(hx, hy)
    h02 = h0 * h0
    b = (1.0 / 3.0) * h02 / (hx * hx + hy * hy)
    ax = h02 / (hx * hx) - 2.0 * b
    ay = h02 / (hy * hy) - 2.0 * b
    L = np.zeros((N * N, N * N))
    for j in range(N):
        for i in range(N):
            id = j * N + i
            ip = j * N + (i + 1) % N
            im = j * N + (i - 1) % N
            jp = ((j + 1) % N) * N + i
            jm = ((j - 1) % N) * N + i
            L[id, ip] += ax
            L[id, im] += ax
            L[id, jp] += ay
            L[id, jm] += ay
            # face diagonals (the 19-point's fd_xy in 2D -> the b weights)
            d1 = ((j + 1) % N) * N + (i + 1) % N
            d2 = ((j + 1) % N) * N + (i - 1) % N
            d3 = ((j - 1) % N) * N + (i + 1) % N
            d4 = ((j - 1) % N) * N + (i - 1) % N
            for d in (d1, d2, d3, d4):
                L[id, d] += b
            L[id, id] = -(2 * ax + 2 * ay + 4 * b)
    return L


class TwoFluid2D:
    """Two-fluid wave on the 2D operator: d2 psi = c^2 L psi -/+ w0^2 (EY - phi EI)."""

    def __init__(self, L, w0_2=20.0, c=1.0):
        self.L = L
        self.w0_2 = w0_2
        self.c = c
        self.N = int(np.sqrt(L.shape[0]))
        self.dt = 0.02
        self._kicked = False

    def step(self, ey, ei, vey, vei):
        dt = self.dt
        if not self._kicked:
            # apply the half-step velocity kick once (the genuinely 2nd-order start)
            vey, vei = self.kick(ey, ei, vey, vei)
            self._kicked = True
        diff = ey - PHI * ei
        aey = self.c * self.c * (self.L @ ey) - self.w0_2 * diff
        aei = self.c * self.c * (self.L @ ei) + self.w0_2 * diff
        vey = vey + dt * aey
        vei = vei + dt * aei
        ey = ey + dt * vey
        ei = ei + dt * vei
        return ey, ei, vey, vei

    def kick(self, ey, ei, vey, vei):
        """Half a step of acceleration ONTO the velocities (the staggered start)."""
        half = 0.5 * self.dt
        diff = ey - PHI * ei
        vey = vey + half * (self.c * self.c * (self.L @ ey) - self.w0_2 * diff)
        vei = vei + half * (self.c * self.c * (self.L @ ei) + self.w0_2 * diff)
        return vey, vei


# --- the measures (the doctrine anchors) ---

def sigma_ratios(rho, N, aspect):
    """Gaussian-fitted widths of rho; returns (sx, sy) and the ratio sx/sy."""
    # fit a 2D Gaussian: widths from the second moments of the magnitude
    g = rho.reshape(N, N)
    gy, gx = np.mgrid[0:N, 0:N]
    m = np.abs(g)
    tot = m.sum()
    mx = (gx * m).sum() / tot
    my = (gy * m).sum() / tot
    sx = np.sqrt(((gx - mx) ** 2 * m).sum() / tot)
    sy = np.sqrt(((gy - my) ** 2 * m).sum() / tot)
    sx_phys = sx * aspect[0]
    sy_phys = sy * aspect[1]
    return sx_phys, sy_phys, sx_phys / sy_phys


def edge_anisotropy(rho, N, aspect):
    """edge-steepness ratio: axial (toward void) vs diagonal (toward neighbor).

    Walk two rays from the seed center (the Yin axis; the diagonal) at a fixed
    PHYSICAL arc-length step (identical on both, both arms), bilinearly
    interpolated, and locate the first crossing of the C = theta condensation
    contour. The edge steepness = 1 / (physical arc-length to the contour).
    The same sampling on both directions removes the discretization bias.
    """
    g = np.abs(rho).reshape(N, N)
    ctr = np.unravel_index(np.argmax(g), g.shape)
    cy, cx = ctr
    peak = g[cy, cx]
    thr = THETA * peak

    def bilinear(x, y):
        x0 = int(np.floor(x)); y0 = int(np.floor(y))
        if not (0 <= x0 < N - 1 and 0 <= y0 < N - 1):
            return float("nan")
        fx, fy = x - x0, y - y0
        return (g[y0, x0] * (1 - fx) * (1 - fy) + g[y0, x0 + 1] * fx * (1 - fy)
                + g[y0 + 1, x0] * (1 - fx) * fy + g[y0 + 1, x0 + 1] * fx * fy)

    def arc_to_contour(vx, vy):
        # vx,vy are PHYSICAL unit direction; physical step ds
        ds = 0.5
        s = ds
        prev = g[cy, cx]
        while s < 3.0 * N * max(aspect):
            # physical position -> cell coords
            x = cx + vx * s / aspect[0]
            y = cy + vy * s / aspect[1]
            v = bilinear(x, y)
            if v < thr and prev >= thr:
                # interpolate the exact crossing arc-length
                f = (prev - thr) / max(prev - v, 1e-9)
                return s - ds + f * ds
            prev = v if not np.isnan(v) else prev
            s += ds
        return float("nan")

    a_arc = arc_to_contour(0.0, 1.0)          # Yin axis (contracted, steep)
    d_arc = arc_to_contour(0.7071, 0.7071)    # diagonal (toward neighbor)
    if np.isfinite(a_arc) and np.isfinite(d_arc) and a_arc > 0 and d_arc > 0:
        a_edge = 1.0 / a_arc
        d_edge = 1.0 / d_arc
        return a_edge, d_edge, d_arc / a_arc   # axial/diag steepness ratio
    return float("nan"), float("nan"), float("nan")


# a Gaussian bubble + phi-relaxed ground state
def seed_bubble(N, aspect, amp=0.3):
    gy, gx = np.mgrid[0:N, 0:N]
    cx, cy = N / 2, N / 2
    # a RADIALLY SYMMETRIC seed (EI centered on EY, no diagonal offset): the operator
    # alone must imprint the anisotropy (the offset seed biased the theta-contour measure)
    sx_c = sy_c = 0.08 * N
    ey = amp * np.exp(-((gx - cx) ** 2) / (2 * sx_c ** 2) - ((gy - cy) ** 2) / (2 * sy_c ** 2))
    ei = amp * 0.618 * np.exp(-((gx - cx) ** 2) / (2 * sx_c ** 2)
                              - ((gy - cy) ** 2) / (2 * sy_c ** 2))
    return ey.ravel(), ei.ravel()
