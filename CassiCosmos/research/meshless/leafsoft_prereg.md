# Leaf-only density-aware softening — pre-registered numpy probe

Status: PRE-REGISTERED (frozen before the probe run)
Date: 2026-08-16

## Question

Applying density-aware softening `eps2_node = eps2 + W^(2/3)` to **every
accepted node** (current GPU law, `cassi_tree_gravity.glsl:123/146/167`,
commit `4ce2912`) makes the tree's effective force law θ-dependent: far-field
accepted **internal** nodes carry a large aggregate W, so their `W^(2/3)`
suppresses them, and the tree no longer approximates the direct O(N²) sum
(G17 median 0.985 at θ=0.5 in the dense 8192 config).

**Hypothesis:** applying the density-aware softening **only to leaves**
(`childCount == 0` nodes — which includes max-depth-capped cells holding
coincident sources) while internal accepted nodes keep the global `eps2`
restores θ-consistency (tree ≈ direct sum again at the frozen thresholds)
while **preserving the two-body-heating protection**, because the heavy
capped cells that motivated `4ce2912` are themselves leaves.

## Arm definition (frozen)

The leaf-only force law:

    eps2_node = eps2 + W^(2/3)   iff  is_leaf   (childCount == 0)
    eps2_node = eps2            otherwise

applied to **both** the monopole and quadrupole accept paths, mirroring the
shader's leaf test (`ccount == 0`, `cassi_tree_gravity.glsl:131`) and its
softening placement (`:146` monopole `R² = ds2 + eps2_node`, `:167`
quadrupole `R²q = ds2 + eps2_node`). Geometric walk acceptance (contains /
`half/sep > θ` opening, leaf-is-exact, self-exclusion) unchanged.

- Configuration: the identical 8192-source dump
  `_diag/fmm_gpu.json`, read exactly as `stage5_verify.py` does:
  N=8192, θ=0.5, eps2=1e-6, leaf_cap=1, max_levels=14. Positions `src[0:3]`
  at stride 8, mass `src[3]`=1, ey `src[4]`, ei `src[5]`; weights
  `w = m·g` via `chord_weight_from_field(ey, ei)` (phi, phi6 from dump).
- Quadrupole path ON (`quad=True`).
- Reference trees built with `stage5_fmm.BHOctree` on the SAME points with
  `g=g`, `eps2=1e-6`, `max_depth=14`, `leaf_cap=1`.

## Statistics (frozen)

For the leaf-only tree `a_leaf` vs the density-aware direct sum
`a_direct = direct_force(pos, pos, w, eps2=1e-6, density_aware=True)`
(the θ→0 / fully-resolved per-source limit, identical to the failing G17/G18
reference):

- **G17** median relative error `|a_leaf − a_direct| / |a_direct|` over the
  `|a_direct| > 1e-4·median(|a_direct|)` keep set: **threshold ≤ 1e-2**.
- **G18** self-exclusion spot-check on the same residual: median ≤ 0.01 **and**
  99.9th percentile ≤ 0.5.

Both thresholds are the frozen G17/G18 thresholds from `stage5_verify.py`,
**unchanged**. Informational (NOT gated): median/99th of the leaf-only tree vs
the GPU dump forces, and of the current per-node law tree vs direct (the
known-failing baseline), for completeness.

## Decision tree (frozen)

- **SUPPORTS** — leaf-only restores both G17 (median ≤ 1e-2) and G18
  (median ≤ 0.01, p999 ≤ 0.5) to their frozen thresholds: the tree
  approximates the direct sum again, so the shader change is warranted.
- **CONTRADICTS** — leaf-only does not restore G17 and G18 to their frozen
  thresholds.
- **INCONCLUSIVE** — ambiguous (e.g. G17 passes but G18 fails, or a threshold
  lands within float noise of its bound).

## Analytic heating-protection check (reported, not gated)

State from the code path, not a simulation: under leaf-only, does the
`W^(2/3)` term survive exactly on the heavy coincident-source cells (max-depth
capped leaves, W ≫ 1) that caused the two-body heating `4ce2912` fixed? Concretely:
the capped cell with coincident/distinct-close sources is a leaf (`ccount == 0`),
so leaf-only applies `eps2 + W^(2/3)` to it — the protection term is preserved
on exactly those cells. Internal (non-leaf) nodes — which `4ce2912`'s commit
message says are NOT where the heating came from (the heating was single-pair
near-field kicks in the dense core, dominated by small/leaf cells) — fall back
to global `eps2`. Verdict stated from the shader/builder code path.

## Files

- Prereg: `research/meshless/leafsoft_prereg.md` (this file, written before run).
- Probe: `research/meshless/leafsoft_probe.py` (numpy, deterministic; implements
  the leaf-only walk locally against `stage5_fmm.BHOctree`; does not modify
  `stage5_fmm.py`, `stage5_verify.py`, `stage5b_verify.py`, or the shader).
- Output: stdout trace + this report; no other files.
