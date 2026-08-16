"""xcheck_timedomain.py -- the ground-truth arbiter for the naive-join reflectivity gap.

wave-2's transfer-march gave 0.658% for the single phi-node; the wave-3 matrix
scattering gives 0.063%. This runs the REAL evolving M-weighted leapfrog on the
coupled operator with a monochromatic source and reads the standing-wave ratio
in the coarse region -- the physics, no scattering assumptions.

Run:  python research/helix_solver/xcheck_timedomain.py
"""

import numpy as np
from rim_coupling import coupled_operator, discrete_q, PHI


def run_swr(coupling, m_t=0):
    hc = 1.0
    hf = hc / PHI
    omega = 2.0 * np.sin(np.pi / 8.0)
    z, A = coupled_operator(hc, hf, coupling, m_t)
    N = len(z)
    h = np.diff(z)
    junc = int(np.argmax(np.abs(np.diff(h)))) + 1  # first spacing change
    dt = 0.12 * np.min(h)
    src = 6
    spr = int(0.85 * N)
    sponge = np.ones(N)
    for i in range(N):
        if i >= spr:
            sponge[i] = 0.5 ** ((i - spr) / 8.0)
    per = 2 * np.pi / omega
    u = np.zeros(N)
    v = np.zeros(N)
    t = 0.0
    for _ in range(int(8 * per / dt)):
        u[src] = np.sin(omega * t); v = v + dt * (A @ u); u = u + dt * v; u *= sponge; t += dt
    lo, hi = src + 2, junc - 3
    peak = np.zeros(hi - lo); trough = np.full(hi - lo, 1e30)
    for _ in range(int(10 * per / dt)):
        u[src] = np.sin(omega * t); v = v + dt * (A @ u); u = u + dt * v; u *= sponge; t += dt
        seg = u[lo:hi]
        peak = np.maximum(peak, seg); trough = np.minimum(trough, seg)
    amp = (peak - trough) / 2.0
    swr = np.max(amp) / np.maximum(np.min(amp), 1e-12)
    R = (swr - 1) / (swr + 1)
    return R * R * 100


for mt in (0, 2, 12):
    print(f"time-domain |R|^2  coupling='naive' m_t={mt}: {run_swr('naive', mt):.4f}%")
print()
# matrix values for comparison
from rim_coupling import coupled_operator as co, scattering_reflectivity as sr
hc, hf, om = 1.0, 1.0 / PHI, 2.0 * np.sin(np.pi / 8.0)
for mt in (0, 2, 12):
    z, A = co(hc, hf, "naive", mt)
    print(f"matrix     |R|^2  coupling='naive' m_t={mt}: {sr(z, A, hc, hf, om)*100:.4f}%")

