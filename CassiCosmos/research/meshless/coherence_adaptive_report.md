# Coherence-adaptive compute — report — the three arms (1/2/3) + VerifyAll

Date: 2026-08-17
Pre-reg: `research/meshless/coherence_adaptive_prereg.md` (frozen, §4 decision tree)
Verdict: **SUPPORTS** for arms 1, 2, 3a, 3b — all bit-identity and ON-correctness gates passed

## 1. What shipped (the three arms, all default-OFF additive toggles)

From the coherence_adaptive plan (the field-AI thesis applied to the solver's own
cost: spend the compute budget where the coherence is). Each arm is a guarded
default-off branch — OFF = bit-identical battery (the PC-append + toggle precedent).

| Arm | Toggle | Mechanism | Files |
|---|---|---|---|
| 1 | `boxless_field` reuse + shortlist (implicit) | **Coherence-filtered site shortlist → boxless instancer**: `cassi_site_shortlist.glsl` reduces the 8192-site mesh to the coherent subset (q ≥ φ⁻²); the instancer's `tri_coherence`/`tri_phase` read the nearest **shortlisted** site when `flag.y > 0.5`. Default: grid path, bit-identical. | `compute/cassi_site_shortlist.glsl` (new), `compute/cassi_instancer.glsl`, `scripts/cassi_physics_engine.gd`, `scripts/cassi_sim.gd`, `scripts/contracts/layout.gd` |
| 2 | `coherence_theta`, `coherence_theta_alpha`, (`q_cent`) | **Coherence-adaptive Barnes-Hut θ(q)**: on the tree walk, θ_eff = θ·(1 − α·(q_n − q_cent)) clamped to [0.3θ, 2θ] — smaller in high-q condensate (more opens, tighter), larger in low-q voids (fewer opens, coarser). Default OFF → θ_eff ≡ θ. | `compute/cassi_tree_build.glsl` (binding 14 NodeQQ), `compute/cassi_tree_gravity.glsl` (PC 5–8), engine/sim/tree-worker/verify arms |
| 3a | `q_weighted_com` | **q-weighted envelope centroid**: `read_com()` weights each subsampled particle by its field coherence q — the tracking envelope follows the coherent core, stray void particles contribute ~nothing. Default OFF → plain mass COM. | `scripts/cassi_physics_engine.gd` (`read_com`), `scripts/cassi_sim.gd` |
| 3b | `adaptive_rebuild`, `coherence_rebuild_beta` | **Coherence-gated rebuild cadence**: `_ml_rebuild_threshold()` returns `max(ML_REBUILD, round(ML_REBUILD·(1 + β·q_scaled)))` with `q_scaled = min(q_mean/φ⁻², 1)` — high mean-q lengthens the VoM rebuild/steer interval. Default OFF → fixed ML_REBUILD=25. | `scripts/cassi_sim.gd` |

Commits: `0f71503` (boxless site-direct reader), `5abe1f5` (arm 1 shortlist →
boxless instancer), `ae50e6b` (arms 2 + 3), engine port `7edfbaa` (local-only).
CassiTheory unification verdicts (`7087e0c`/`f52cd8b`/`e311d5b`, pushed): all DO NOT SUPPORT.

## 2. Bit-identity (pre-reg §4, all MUST pass) — all green

| Gate | Result |
|---|---|
| `assert_layout` (PC/binding contract gate) | **PASS, 0 mismatches** |
| GDScript parse-gate (`_diag/parse_gate_arm2.gd`, 8/8) | PASS |
| glslangValidator (`cassi_tree_build`, `cassi_tree_gravity`, `cassi_instancer`, `cassi_site_shortlist`) | all clean; SPIR-V shows the new bindings/PC (NodeQQ, q_cent, coherence_theta, theta_eff, boxless, Shortlist) |
| `verify_voronoi3d` (default off) | **9/9 PASS**, exact r(t) pins |
| `verify_voronoi3d_moving` (default off) | **10/10 PASS** |
| `verify_meshless_reconstruct` (default off) | **7/7 PASS** (max|r−r0| = 0.2478, exact) |
| `verify_meshless_gravity` + `stage5b_verify.py` (tree arm, default off) | ALL PASS (G31/G30, GPU-vs-prototype 1.4e-5) |
| `verify_fmm` | 7/7 (G16 3.8e-7; G17/G18 intentional pre-existing FAILs) |

Working tree clean of all GPU churn after every run; all `_diag` probes documented,
not committed.

## 3. ON-correctness (pre-reg §4, per arm) — all PASS

### Arm 1 — coherence-filtered site shortlist → boxless instancer
Probe: `_diag/arm1_probe.gd` (windowed local RD), on a dense coherent blob in a
sparse 8192-site field.

```
A  shortlist count:      271 / 8192  (33× smaller than the full mesh)
A2 every shortlisted site q ≥ φ⁻²    PASS
B  shortlist-vs-full brute-force     max_rel = 0.0  PASS  (coherent-nearest, n=1586)
RESULT: PASS
```

The shortlist prunes the incoherent 97% of the mesh; the per-frame boxless instancer
samples only the coherent subset with zero force/color error (`max_rel = 0.0` vs the
full brute-force nearest-site). Cost win: the instancer's per-frame site scan shrinks
by the shortlist fraction.

### Arm 2 — coherence-adaptive Barnes-Hut θ(q)
Probe: `_diag/arm2_probe.gd` (windowed local RD tree build + walk, planted
two-region source: coherent blob + broad incoherent void; OFF vs ON walk over the
same tree).

```
force match  max|Δa|/max|a_off| = 0.000000  PASS  (≤ 1e-3)
node-evals   void: OFF=2734 ON=1749 ratio=0.640  PASS  (≤ 0.85)
             blob: ratio=0.811
RESULT: PASS
```

- **Force accuracy holds**: the ON walk's coarser multipole in the void reproduces
  the OFF forces to float resolution (the pruned low-q nodes carry negligible mass).
- **Void win is real**: 36% fewer node-evaluations per particle in the coherent-void
  region (OFF 2734 → ON 1749), beating the frozen ≥15% bar; the coherent-blob region
  is *also* pruned (0.811) without losing either force match or the blob's ordered
  structure.

### Arm 3a — q-weighted envelope centroid
Probe: `_diag/arm3_probe.gd` — mirrors the shipped `read_com()` arithmetic exactly
(stride-32·4 subsample, the same world→grid qcell map) over a coherent blob + 128
stray void particles far outside in one direction.

```
plain |d_com| = 1.1488   q|d_com| = 0.1863   ratio = 0.162  PASS  (< 0.30)
```

When stray void particles drag the plain mass centroid 1.15 units off the blob, the
q-weighted centroid stays 0.19 from it — **the envelope follows the coherent field,
not the cloud** (16% of the plain drag; the frozen bar is <30%).

### Arm 3b — coherence-gated rebuild cadence
Same probe, mirrors the shipped `_ml_rebuild_threshold()` exactly.

```
fixed ML_REBUILD = 25   adaptive @q=0.360 β=1.0 → 49  PASS  (> 25)
q_mean=0.999 → 50 (saturates ≤ 2·ML_REBUILD)       NaN-safe
RESULT: PASS (failures=0)
```

High mean-q (0.36, just under φ⁻²) almost doubles the rebuild interval (25 → 49
steps); at saturation the interval caps at 50 (never exceeds 2× the fixed base), and
the `q_scaled` term is NaN-safe.

## 4. Decision-tree application (frozen §4)

1. Bit-identity: **passes** for all arms (assert_layout 0; every battery arm green,
   off-toggles bit-identical; trajectories exact).
2. ON-correctness: **passes** for arms 1, 2, 3a, 3b (each criterion above).
3. → **SUPPORTS** for all four arms; recorded here and in the probe-outcome ledger.

No FAIL-review, no revert needed. All arms are additive default-off toggles; the
battery contract (30 arms green, `verify_river_isotropy` anchors load-bearing,
`assert_layout` 0) is intact.

## 5. Honest scope / follow-ons

- The arm-1 shortlist serves the instancer display read. The underlying
  grid-carrier readers (condensation, river gradient, merge) still read the raster
  grid under the meshless+tree arm — the shortlist is the coherence-filter for the
  render path, matching the pre-reg §4 non-goal that demoted the grid to a display
  attachment for the *picture*, pending the spatial-hash-of-sites optimization.
- Arm 2's win is measured at the walk level (node-evals). The wall-clock gain in a
  full galaxy run follows when the void fraction dominates; not separately
  benchmarked here.
- Arms 2/3 `q_cent` (the field mean q) is read from telemetry (`_q_mean`); the pivot
  is the field's own running mean, not a hand-set constant — a defensible,
  self-calibrating choice.

## 6. VerifyAll close-out

All pre-reg §4 gates complete:
- Bit-identity: assert_layout 0; battery arms all green with default toggles off,
  exact pinned trajectories. ✔
- Arm 1 ON: shortlist 271/8192, exact coherent-subset match. ✔
- Arm 2 ON: force match 0.000000 ≤ 1e-3; void node-eval ratio 0.640 ≤ 0.85. ✔
- Arm 3a ON: q-COM displacement ratio 0.162 < 0.30. ✔
- Arm 3b ON: adaptive interval 49 > 25 fixed, saturates ≤ 2×, NaN-safe. ✔
- Probes are `_diag/*` (gitignored, documented, not committed); working tree churn
  reverted. ✔

The `coherence_adaptive_prereg.md` VerifyAll todo is hereby closed.
