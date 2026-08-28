# θ-sweep of the per-node density-aware law vs the per-source closure — pre-registered probe

Status: PRE-REGISTERED (frozen before the probe run)
Date: 2026-08-16

## Question

The current per-node density-aware law (`eps2_node = eps2 + W^(2/3)` on every
accepted node, `cassi_tree_gravity.glsl:123/146/167`, commit `4ce2912`) makes
the GPU tree deviate from the per-source density-aware direct sum at θ=0.5
(G17 median 0.985, dense 8192 config). The re-scope decision for the G17/G18
gates hinges on whether that deviation **vanishes as θ→0** (the tree becomes
all-leaves, so its law should converge to the per-source closure) and at
which θ it crosses the frozen 1e-2 threshold.

## Frozen sweep

θ ∈ {0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.05} (log-ish), the SAME dense
8192 config (`_diag/fmm_gpu.json`, read exactly as `stage5_verify.py` does:
N=8192, phi/phi6 from dump, eps2=1e-6, leaf_cap=1, max_levels=14; positions
`src[0:3]` stride 8, mass=1, ey `src[4]`, ei `src[5]`, weights
`w = m·g` via `chord_weight_from_field`). The CURRENT per-node law walk
(probe-local 'current' mode, `leafsoft_probe._walk(mode='current')`, which
reproduces the GPU to 3.8e-7) evaluated at each θ vs the per-source
density-aware direct sum `direct_force(pos, pos, w, eps2=1e-6,
density_aware=True)`. Median relative error at each θ, same keep-set
convention as `stage5_verify.py` (`|direct| > 1e-4·median(|direct|)`).
Quadrupole ON.

## Frozen statistics

- `median_err(θ)` for each θ in the sweep.
- The crossing `θ*` = smallest θ (or interpolated) where
  `median_err(θ) ≤ 1e-2` (the frozen G17 threshold). Report θ* or
  "no crossing in sweep range".
- If no crossing at θ=0.05, extend the sweep to θ ∈ {0.02, 0.01} to expose
  the convergence trend toward float precision.

## Frozen decision tree

- **SUPPORTS re-scope-to-smaller-θ**: θ* exists at θ ≥ 0.1 (a practical
  frozen θ where the old G17 claim still holds under the new law).
- **SUPPORTS convergence-as-such**: no θ* ≥ 0.1 crossing, but the deviation
  is monotone-decreasing toward float precision as θ→0 (extended sweep shows
  the trend) — the θ→0 limit converges to the per-source closure.
- **CONTRADICTS**: the deviation does NOT vanish as θ→0 (the law's θ→0 limit
  differs from the per-source closure — a deeper finding about the
  aggregate-node residual: capped coincident leaves soften by W^(2/3) where
  the per-source sum softens by Σ w_s^(2/3), so they cannot coincide even at
  θ→0 if such cells exist).

## Files

- Prereg: `research/meshless/theta_sweep_prereg.md` (this file, before run).
- Probe: `research/meshless/theta_sweep_probe.py` (numpy, deterministic,
  reuses the existing local walk machinery from `leafsoft_probe._walk`).
- Output: stdout table + report; no gate/threshold/existing-file changes.
