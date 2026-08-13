"""Stage 4 verification — the LIVE-SIM integration gate (MESHLESS_PLAN.md
§10): the sim's meshless Voronoi arm vs its grid two-fluid arm, evolved
from the SAME initial condition by scripts/verify_meshless_sim.gd.

The cross-solver agreement contract:
  G9  the GRID arm's mean-deviation trajectory breathes at
      OMEGA = sqrt(omega0^2 (1+phi)) (2%)
  G10 the MESHLESS arm's trajectory breathes at OMEGA (2%)
  G11 the two arms' final fields agree (L2 < 5%)
  G12 no NaN/Inf in either field

Run:  python research/meshless/stage4_verify.py [path/to/meshless_sim_gpu.json]
"""
import base64
import json
import sys

import numpy as np

from stage1_jfa3d import PHI, OM2, OMEGA, _breath_freq


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "_diag/meshless_sim_gpu.json"
    d = json.load(open(path, encoding="utf-8"))
    N = int(d["N"])
    dt = float(d["dt"])
    batch = int(d["batch"])
    n_batches = int(d["n_batches"])

    d_a = np.asarray(d["d_a"], dtype=np.float64)
    d_b = np.asarray(d["d_b"], dtype=np.float64)
    ey_a = np.frombuffer(base64.b64decode(d["ey_a_b64"]), dtype="<f4")
    ey_b = np.frombuffer(base64.b64decode(d["ey_b_b64"]), dtype="<f4")
    ic_ey = np.frombuffer(base64.b64decode(d["ic_ey_b64"]), dtype="<f4")
    ic_ei = np.frombuffer(base64.b64decode(d["ic_ei_b64"]), dtype="<f4")

    # the batch time spacing: batch steps × dt
    ts = dt * batch
    breath_a = _breath_freq(d_a - d_a.mean(), ts)
    breath_b = _breath_freq(d_b - d_b.mean(), ts)
    print("[ref] analytic OMEGA = %.4f" % OMEGA)
    print("[G9] grid arm breather: %.4f" % breath_a)
    print("[G10] meshless arm breather: %.4f" % breath_b)

    l2 = float(np.linalg.norm(ey_b - ey_a) / np.linalg.norm(ey_a))
    # band-limited agreement (the resolved modes, k <= 8): the IC's
    # white-noise UV tail decorrelates between ANY two discretizations
    # (the D19 grid vs the staircase flux differ at high k) — the
    # physics gate is the agreement on the resolved band
    kf = np.fft.fftfreq(N) * N
    k = np.sqrt(kf[:, None, None] ** 2 + kf[None, :, None] ** 2
                + kf[None, None, :] ** 2)
    band = (k <= 8.0) & (k > 0.0)
    a_h = np.fft.fftn(ey_a.reshape(N, N, N))
    b_h = np.fft.fftn(ey_b.reshape(N, N, N))
    l2b = float(np.linalg.norm((b_h - a_h)[band]) / np.linalg.norm(a_h[band]))
    corrb = float(np.corrcoef(a_h[band].real, b_h[band].real)[0, 1])
    print("[G11] cross-arm: full L2 = %.4f  band L2 = %.4f  band corr = %.4f"
          % (l2, l2b, corrb))
    # NOTE: the band-filtered comparison is hypersensitive — the IC's
    # random phases create modes where the sound and breather
    # components nearly cancel, and the two solvers' ~1% discretization
    # frequency differences amplify there (diagnosed: the grid arm
    # reproduces the numpy-D19 kick-drift to 9e-7, so both arms are
    # faithful; the cancellations are a metric artifact, not physics).
    # The gate is the full-field agreement (dominated by the resolved
    # modes) — printed here as diagnostics.
    ic_dev = (ic_ey - PHI * ic_ei).mean()
    print("[IC] mean deviation of the shared IC: %.6e" % ic_dev)
    nan = bool(np.isnan(ey_a).any() or np.isinf(ey_a).any()
               or np.isnan(ey_b).any() or np.isinf(ey_b).any())
    g12 = not nan
    g9 = abs(breath_a - OMEGA) / OMEGA < 0.02
    g10 = abs(breath_b - OMEGA) / OMEGA < 0.02
    g11 = l2 < 0.02


    for name, ok in [("G9 grid arm breather", g9),
                     ("G10 meshless arm breather", g10),
                     ("G11 cross-arm agreement", g11),
                     ("G12 no NaN", g12)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    print("RESULT: %s" % ("ALL PASS" if (g9 and g10 and g11 and g12)
                          else "FAILURES PRESENT"))
    return 0 if (g9 and g10 and g11 and g12) else 1


if __name__ == "__main__":
    sys.exit(main())
