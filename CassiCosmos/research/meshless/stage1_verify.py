"""Stage 1b verification — the GPU state dump (scripts/verify_voronoi3d.gd)
against the exact 3D spectral reference, computed from the SAME dumped
ICs. This is the cross-tool counterpart of stage1_jfa3d.py's gates, now
pinned to the actual Godot GLSL implementation:

  G0 GPU JFA mislabel rate vs the exact KDTree assignment (< 2%)
  G1 breather frequency of the GPU r(t) vs OMEGA = sqrt(om2 (1+phi)) (< 2%)
  G2 GPU r(t) vs the exact reference trajectory (< 5%)
  G3 rasterized GPU snapshot L2 vs the exact reference (< 5%)
  G4 spectrum correlation in the power band (> 0.95)

Run:  python research/meshless/stage1_verify.py [path/to/voronoi3d_gpu.json]
"""
import base64
import json
import sys

import numpy as np
from scipy.spatial import cKDTree

from stage1_jfa3d import OM2, PHI, TWO_PI, OMEGA, Spectral3D, _band_corr, _breath_freq


def _blob(d, key, dtype):
    return np.frombuffer(base64.b64decode(d[key]), dtype=dtype)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "_diag/voronoi3d_gpu.json"
    d = json.load(open(path, encoding="utf-8"))
    N = int(d["N"])
    L = float(d["L"])
    dt = float(d["dt"])
    n_steps = int(d["n_steps"])
    n_sites = int(d["n_sites"])

    sites = _blob(d, "sites_b64", "<f4").reshape(-1, 4)[:, :3].astype(np.float64)
    labels = _blob(d, "labels_b64", "<i4").reshape(N, N, N)
    ey0 = _blob(d, "ey0_b64", "<f4").reshape(N, N, N).astype(np.float64)
    ei0 = _blob(d, "ei0_b64", "<f4").reshape(N, N, N).astype(np.float64)
    psi_f = _blob(d, "psi_y_b64", "<f4").astype(np.float64)
    r_gpu = np.asarray(d["r"], dtype=np.float64)

    print("sites=%d  labels: %d distinct, %d unlabeled" % (
        n_sites, len(np.unique(labels)), int((labels < 0).sum())))

    # G0 — GPU JFA vs the exact KDTree assignment (same definition:
    # nearest site to each cell center)
    cc = (np.mgrid[0:N, 0:N, 0:N].astype(np.float64) + 0.5) * (L / N)
    cc_flat = np.stack([cc[0].ravel(), cc[1].ravel(), cc[2].ravel()], axis=1)
    exact = cKDTree(sites).query(cc_flat)[1].reshape(N, N, N)
    mislabel = float((labels != exact).mean())
    print("[G0] GPU JFA mislabel rate: %.4f" % mislabel)

    # exact-in-time reference from the dumped ICs
    spec = Spectral3D(N, L)
    t_out = np.arange(0.0, n_steps * dt + dt, dt)
    r_spec, d_spec, ey_spec, _ = spec.solve(ey0, ei0, t_out)
    print("[ref] spectral breather frequency: %.4f (analytic %.4f)"
          % (_breath_freq(d_spec, dt), OMEGA))

    # GPU final state rasterized piecewise-constant per cell
    raster = psi_f[labels]
    l2 = float(np.linalg.norm(raster - ey_spec) / np.linalg.norm(ey_spec))
    r_err = float(np.max(np.abs(r_gpu - r_spec)) / np.abs(r_spec.mean()))
    breath_gpu = _breath_freq(r_gpu - r_gpu.mean(), dt)
    p_spec = np.abs(np.fft.fftn(ey_spec - ey_spec.mean())) ** 2
    p_vor = np.abs(np.fft.fftn(raster - raster.mean())) ** 2
    kf = np.fft.fftfreq(N) * N
    k = np.sqrt(kf[:, None, None] ** 2 + kf[None, :, None] ** 2
                + kf[None, None, :] ** 2)
    corr = _band_corr(p_spec.ravel(), p_vor.ravel(), k.ravel())
    print("[gpu] L2=%.4f  max|r err|=%.4f  breath=%.4f  corr=%.4f"
          % (l2, r_err, breath_gpu, corr))

    g0 = mislabel < 0.02
    g1 = abs(breath_gpu - OMEGA) / OMEGA < 0.02
    g2 = r_err < 0.05
    g3 = l2 < 0.05
    g4 = corr > 0.95
    print("---- gate ----")
    for name, ok in [("G0 GPU JFA mislabel", g0),
                     ("G1 breather freq", g1),
                     ("G2 r(t) trajectory", g2),
                     ("G3 snapshot L2", g3),
                     ("G4 spectrum", g4)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (g0 and g1 and g2 and g3 and g4)
                          else "FAILURES PRESENT"))
    return 0 if (g0 and g1 and g2 and g3 and g4) else 1


if __name__ == "__main__":
    sys.exit(main())
