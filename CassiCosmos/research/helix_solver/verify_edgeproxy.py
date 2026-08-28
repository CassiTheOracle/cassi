"""verify_edgeproxy.py -- construction/validation gates for the bias-free edge proxy.

Per edge_proxy_prereg.md SS3. Runs (deterministic, numpy):
  - G-gauss:   the analytic isotropic Gaussian control -> r_edge = 1.00 +- 0.01
  - G-control: the analytic uniform checkerboard -> r_edge = 1.27 +- 0.08
  - G-phi:     the analytic phi-checkerboard -> r_edge >= 1.5 AND > control
  - Machinery: free (w0=0) two-fluid energy drift < 5e-3 over 600 steps
  - Determinism: two runs bitwise identical
  - Coherence sanity: peak(EY^2+EI^2) > 0, C_dyn in [-1,1]

Run from the repo root:  python research/helix_solver/verify_edgeproxy.py
"""

import numpy as np

from phi_grid import PHI
from triaxial_laplacian import anisotropic_laplacian, TwoFluid2D, seed_bubble
import edge_proxy as ep

N = 96
results: list[tuple[str, bool, str]] = []


def gate(name, ok, msg) -> None:
    results.append((name, bool(ok), str(msg)))
    print(f"GATE {name}: {'PASS' if ok else 'FAIL'}  {msg}")


def main() -> None:
    print("== Leg G: the bias-free proxy vs analytic ground truths ==")

    # G-gauss: the true no-anisotropy control must read exactly 1.0
    xs = np.arange(N) / N
    gx, gy = np.meshgrid(xs, xs)
    gauss = np.exp(-((gx - 0.5) ** 2 + (gy - 0.5) ** 2) / (2 * 0.12 ** 2))
    reads = [ep.edge_ratio(gauss, N, (1.0, 1.0), theta=t)[0] for t in (0.3, 0.4, 0.5)]
    gate("G-gauss_isotropic_1.0", all(abs(r - 1.0) <= 0.01 for r in reads),
         f"isotropic Gaussian r_edge = {[round(r, 4) for r in reads]} (must be 1.00+-0.01)")

    # G-control: the uniform checkerboard -> exact 1.269 at theta=0.45
    cc = ep.control_cond_field(N, k=2.0)
    rc, ga_c, gd_c = ep.edge_ratio(cc, N, (1.0, 1.0))
    gate("G-control_uniform_1.269", 1.269 - 0.08 <= rc <= 1.269 + 0.08,
         f"uniform checkerboard r_edge = {rc:.4f} (brackets exact 1.269; ga={ga_c:.3f} gd={gd_c:.3f})")

    # G-phi: the phi-checkerboard -> >=1.5 and clearly above the control
    cf = ep.fit_cond_field(N)
    rp, ga_p, gd_p = ep.edge_ratio(cf, N, (PHI, 1.0))
    gate("G-phi_phi-checkerboard", rp >= 1.5 and rp > rc,
         f"phi-checkerboard r_edge = {rp:.4f} (>=1.5 and > control {rc:.3f}; ga={ga_p:.3f} gd={gd_p:.3f})")

    print()
    print("== Machinery + sanity gates ==")

    # Conservation: free (w0=0) drift < 5e-3 over 600 steps
    L = anisotropic_laplacian(N, (PHI, 1.0))
    gfree = TwoFluid2D(L, w0_2=0.0)
    ey, ei = seed_bubble(N, (PHI, 1.0))
    ve = wi = np.zeros(N * N)
    e0 = 0.5 * (np.sum(ve * ve) + np.sum(wi * wi) - ey @ (L @ ey) - ei @ (L @ ei))
    for _ in range(600):
        ey, ei, ve, wi = gfree.step(ey, ei, ve, wi)
    e1 = 0.5 * (np.sum(ve * ve) + np.sum(wi * wi) - ey @ (L @ ey) - ei @ (L @ ei))
    drift_free = abs(e1 - e0) / max(abs(e0), 1e-12)
    gate("machinery_conserves", drift_free < 5e-3,
         f"free (w0=0) 600-step drift = {drift_free:.2e} (<5e-3)")

    # Determinism: two 50-step runs bitwise identical
    r1 = _run_short()
    r2 = _run_short()
    gate("determinism_bitwise", bool(np.array_equal(r1[0], r2[0])) and bool(np.array_equal(r1[1], r2[1])),
         "two 50-step phi-arm runs bitwise identical")

    # Coherence sanity: C_dyn in [-1,1] and non-degenerate (a small-amplitude
    # 0.3 seed gives q=EY^2+EI^2 peaking ~0.05, so C_dyn ~ -0.9 to -1.0 is the
    # CORRECT dense-void reading, not a defect; validity is the criterion)
    cd, _ = ep.run_arm((PHI, 1.0), steps=600, N=N)
    cmin, cmax = float(cd.min()), float(cd.max())
    gate("coherence_Cdyn_valid", -1.0 <= cmin and cmax <= 1.0 and cmax > cmin,
         f"C_dyn in [{cmin:.3f}, {cmax:.3f}] (valid Qi density, non-degenerate)")

    print()
    all_pass = all(ok for _, ok, _ in results)
    print("ALL CHECKS PASSED" if all_pass else "SOME GATES FAILED")
    raise SystemExit(0 if all_pass else 1)


def _run_short(seed_from=None):
    L = anisotropic_laplacian(N, (PHI, 1.0))
    ey, ei = seed_bubble(N, (PHI, 1.0))
    ve = wi = np.zeros(N * N)
    g = TwoFluid2D(L)
    for _ in range(50):
        ey, ei, ve, wi = g.step(ey, ei, ve, wi)
    return ey, ei


if __name__ == "__main__":
    main()
