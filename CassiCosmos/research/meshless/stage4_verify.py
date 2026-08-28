"""Stage 4 verification — the LIVE-SIM integration gate (MESHLESS_PLAN.md
§10): the sim's meshless Voronoi arm vs its grid two-fluid arm, evolved
from the SAME initial condition by scripts/verify_meshless_sim.gd.

The reconstruction fix (AREPO-style per-cell LINEAR reconstruction in the
raster — the "square-ripples" fix) changed what arm B's grid output means:
the rendered field is now a reconstructed interpolant, no longer the raw
piecewise-constant cell averages. The physics-identity gate must therefore
compare the two arms at the CELL-AVERAGE level, not through the
reconstruction:

  G9  the GRID arm's mean-deviation trajectory breathes at
      OMEGA = sqrt(omega0^2 (1+phi)) (2%)
  G10 the MESHLESS arm's trajectory breathes at OMEGA (2%)
  G11 PHYSICS IDENTITY — arm B's PIECEWISE-CONSTANT grid field (built from
      its per-site cell-averaged psi + JFA labels, i.e. the cell averages
      on the grid) vs arm A's grid field (L2 < 2%). This is the honest
      cell-average cross-solver gate: the same comparison the old code made
      when the raster WAS piecewise-constant, so the gate's meaning and its
      2% threshold are unchanged.
  G12' RECONSTRUCTED-field L2 — arm B's actual rendered (reconstructed)
      field vs arm A, reported SEPARATELY with its own honest threshold
      (L2 < 8%). The reconstructed field carries additional error beyond
      the physics: the Green-Gauss gradient (exact only for linear fields,
      first-order on the real rippled field) plus the JFA site sampling.
      It is a rendering-fidelity diagnostic, NOT the physics gate.
  G12 no NaN/Inf in either field.

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

    # -- physics identity: arm B's CELL-AVERAGE grid field (piecewise-
    # constant over its Voronoi cells), built from the per-site psi + labels.
    psi_y_b = np.frombuffer(base64.b64decode(d["psi_y_b_b64"]), dtype="<f4")
    labels_b = np.frombuffer(base64.b64decode(d["labels_b_b64"]), dtype="<i4")
    pc_b = psi_y_b[labels_b.astype(np.int64) % len(psi_y_b)]

    l2_pc = float(np.linalg.norm(pc_b - ey_a) / np.linalg.norm(ey_a))
    g11 = l2_pc < 0.02
    print("[G11] physics identity (cell-average pc field vs grid arm): L2 = %.4f"
          % l2_pc)

    # -- rendered (reconstructed) field, honest separate diagnostic.
    l2_recon = float(np.linalg.norm(ey_b - ey_a) / np.linalg.norm(ey_a))
    g_recon = l2_recon < 0.08
    print("[G12'] reconstructed (rendered) field vs grid arm: L2 = %.4f  (threshold 0.08)"
          % l2_recon)

    # band-limited agreement (the resolved modes, k <= 8): diagnostic only.
    kf = np.fft.fftfreq(N) * N
    k = np.sqrt(kf[:, None, None] ** 2 + kf[None, :, None] ** 2
                + kf[None, None, :] ** 2)
    band = (k <= 8.0) & (k > 0.0)
    a_h = np.fft.fftn(ey_a.reshape(N, N, N))
    pc_h = np.fft.fftn(pc_b.reshape(N, N, N))
    b_h = np.fft.fftn(ey_b.reshape(N, N, N))
    l2_pc_b = float(np.linalg.norm((pc_h - a_h)[band]) / np.linalg.norm(a_h[band]))
    l2_b = float(np.linalg.norm((b_h - a_h)[band]) / np.linalg.norm(a_h[band]))
    print("[diag] band L2 (pc) = %.4f  band L2 (reconstructed) = %.4f" % (l2_pc_b, l2_b))
    ic_dev = (ic_ey - PHI * ic_ei).mean()
    print("[IC] mean deviation of the shared IC: %.6e" % ic_dev)
    nan = bool(np.isnan(ey_a).any() or np.isinf(ey_a).any()
               or np.isnan(ey_b).any() or np.isinf(ey_b).any())
    g12 = not nan
    g9 = abs(breath_a - OMEGA) / OMEGA < 0.02
    g10 = abs(breath_b - OMEGA) / OMEGA < 0.02


    for name, ok in [("G9 grid arm breather", g9),
                     ("G10 meshless arm breather", g10),
                     ("G11 physics identity (cell-average)", g11),
                     ("G12' reconstructed (diagnostic)", g_recon),
                     ("G12 no NaN", g12)]:
        print("[%s] %s" % ("PASS" if ok else "FAIL", name))
    allok = g9 and g10 and g11 and g12
    print("RESULT: %s" % ("ALL PASS" if allok else "FAILURES PRESENT"))
    # G12' is reported but NOT a hard gate (it is a rendering-fidelity
    # diagnostic); a pass requires the physics gates (G9/G10/G11) + no NaN.
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
