"""xcheck_taper.py -- the well-posed case: does the taper agree across methods?

The bare phi-ratio junction reflectivity is coupling-defined in the discrete FV
operator (matrix 0.06%, time-domain 9.9-16%, wave-2 march 0.66% -- a 250x spread,
itself the finding). The TAPER is a smooth, unambiguously-defined transition, so it
should agree across methods. This cross-checks matrix vs time-domain for the taper.

Run:  python research/helix_solver/xcheck_taper.py
"""

import numpy as np
from rim_coupling import coupled_operator as co, scattering_reflectivity as sr, PHI

hc, hf, om = 1.0, 1.0 / PHI, 2.0 * np.sin(np.pi / 8.0)


def td_reflectivity(coupling, m_t):
    z, A = co(hc, hf, coupling, m_t)
    N = len(z)
    h = np.diff(z)
    junc = int(np.argmax(np.abs(np.diff(h)))) + 1
    dt = 0.1 * np.min(h)
    src = 8
    spr = int(0.8 * N)
    sponge = np.ones(N)
    for i in range(N):
        if i >= spr:
            sponge[i] = 0.5 ** ((i - spr) / 6.0)
    per = 2 * np.pi / om
    u, v, t = np.zeros(N), np.zeros(N), 0.0
    for _ in range(int(10 * per / dt)):
        u[src] = np.sin(om * t); v = v + dt * (A @ u); u = u + dt * v; u *= sponge; t += dt
    lo, hi = src + 2, max(junc - 4, src + 3)
    peak = np.zeros(hi - lo); trough = np.full(hi - lo, 1e30)
    for _ in range(int(14 * per / dt)):
        u[src] = np.sin(om * t); v = v + dt * (A @ u); u = u + dt * v; u *= sponge; t += dt
        seg = u[lo:hi]
        peak = np.maximum(peak, seg); trough = np.minimum(trough, seg)
    amp = (peak - trough) / 2.0
    swr = np.max(amp) / max(np.min(amp), 1e-12)
    R = (swr - 1) / (swr + 1)
    return R * R * 100


for mt in (0, 2, 12):
    z, A = co(hc, hf, "taper", mt)
    matrix = sr(z, A, hc, hf, om) * 100
    td = td_reflectivity("taper", mt)
    print(f"taper m_t={mt:2d}:  matrix |R|^2 = {matrix:.4f}%   time-domain |R|^2 = {td:.4f}%")
