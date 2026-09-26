# θ-sweep of the per-node density-aware law vs the per-source closure — report

Status: VERDICT = SUPPORTS convergence-as-such
Date: 2026-08-16
Prereg: `research/meshless/theta_sweep_prereg.md` (frozen before the run)
Probe: `research/meshless/theta_sweep_probe.py` (numpy, deterministic, reuses
the local 'current' walk from `leafsoft_probe` that reproduces the GPU to 3.8e-7)

## θ table (median relative error, current per-node law vs per-source
density-aware direct, dense 8192 config from `_diag/fmm_gpu.json`)

| θ | median_err | < 1e-2 ? |
|---|---|---|
| 0.50 | 9.857e-01 | no |
| 0.40 | 9.759e-01 | no |
| 0.30 | 9.628e-01 | no |
| 0.25 | 9.411e-01 | no |
| 0.20 | 9.007e-01 | no |
| 0.15 | 8.264e-01 | no |
| 0.10 | 6.694e-01 | no |
| 0.05 | 3.347e-01 | no |
| 0.02 | 3.480e-02 | no |
| 0.01 | 3.813e-03 | YES |
| 0.005 | 4.645e-04 | YES (informational extension) |
| 0.001 | 1.284e-04 | YES (informational extension) |

## Crossing

`θ* = 0.01` is the smallest swept θ where `median_err ≤ 1e-2`. **No crossing
at any θ ≥ 0.1** — even θ=0.1 gives median 0.67, and θ=0.05 still 0.33.

## Verdict (frozen decision tree)

**SUPPORTS convergence-as-such.** The deviation is **monotone-decreasing
toward float precision as θ→0** and the θ→0 limit converges to (very near)
the per-source closure: 0.985 @ 0.5 → 0.33 @ 0.05 → 0.0348 @ 0.02 →
3.8e-3 @ 0.01 → 4.6e-4 @ 0.005 → 1.3e-4 @ 0.001. The tree becomes all-leaves
at small θ, so the per-node law degenerates to the per-source closure.

The re-scope shape is therefore **NOT freeze-G17-at-a-practical-θ**: there is
no θ ≥ 0.1 at which the old G17 claim (tree ≈ direct at 1e-2) holds under the
new law. It is **certify-convergence**: G17's "tree ≈ direct sum" assertion
is a property of θ under the aggregate-node law, certifiable only at θ ≤ 0.01.

## Residual floor (mechanism, informational)

The tree has **2469 max-depth-capped multi-source leaves** (W median ≈ 32,
max 619) among 10646 leaves. At small θ these are opened down to by the walk
and soften by the AGGREGATE `W^(2/3)` (current law), whereas the per-source
direct softens each member by `Σ w_s^(2/3)`. This aggregate-vs-per-source
difference is an irreducible residual that persists as θ→0 — but it is ~1e-4
at θ=0.001, three orders below the frozen threshold. It explains why the
convergence approaches ~1e-4 (the capped-cell floor) rather than exact float
roundoff, yet it is far below any practical gate bound.

## One-line re-scope recommendation

Certify-convergence: G17/G18 under the current per-node density-aware law
hold only as θ→0 (θ* ≈ 0.01, floor ~1e-4) — re-scope the gates to certify the
θ→0 convergence (or document G17 as θ-conditional at the sim's θ=0.5), rather
than freezing the tree≈direct assertion at any practical θ ≥ 0.1, where it
fails under the new law.

No gate, threshold, or existing file was changed; the shader was not touched;
the sweep is deterministic and re-runnable.
