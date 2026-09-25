# Full-Observable Field Operator Invention — Clean-GPU Campaign

## Status

Frozen before creating the four output directories in §4 and after confirming no `Godot_v4.7.1-stable_mono_win64.exe` process holds the GPU. This is a fresh campaign. It does not amend or re-invoke the earlier `full_observable_operator_prereg.md` or `full_observable_operator_v2_prereg.md` bodies.

The original body stopped before field selection because `RHC1` was out of domain. The v2 candidate trajectories are retained as instrument evidence only: its live arm ran concurrently with the user mind engine and was stopped before producing a receipt. No acceleration target was read from either stopped campaign, and neither body emitted a full-observable selection or classification.

## Question

Can the persistent Cassi field construct a regime-aware collective acceleration law from the complete local target-independent environment available in a trajectory recorder, then transfer it into newly generated bounded scale, concentration, and live-field worlds?

This is a reduced collective law, not a replacement for the microscopic meshless force equation.

## Observable language

Each candidate receives 31 target-independent scalar atoms: `one`, radial coordinate, radial speed, speed, transverse speed, time, relative particle mass, softening ratio, grid-cell ratio, cluster-radius ratio, cluster-separation ratio, live-field flag, enclosed mass fraction, enclosed density, sixteenth-neighbor radius, local density, density contrast, softened potential, specific field energy, orbital frequency, virial ratio, angular momentum, velocity dispersion, velocity coherence, local radial flow, divergence, shear, vorticity, radial strain, density-gradient magnitude, and coherence-gradient magnitude.

The six frames are radial, flow, transverse velocity, orbital normal, negative density gradient, and coherence gradient. Neighborhood quantities use deterministic Euclidean `k = 16` nearest neighbors across live tracers at the same clock and a fixed dimensionless least-squares ridge of `1e-9`. Rank-deficient neighborhoods invalidate a candidate. Zero-norm frames are zero.

Features may use only the current sample’s recorded position, velocity, particle mass, clock, and declared engine configuration. They may not use a centered acceleration target, future sample, residual, holdout identity, analysis verdict, or holdout rank. The target is the centered velocity difference divided by each arm’s acceleration scale.

The grammar is the fixed full-observable grammar: registered unary operations `abs`, `signed_square`, `signed_sqrt`, `signed_log1p`, `inv1p_abs`, `exp_neg_abs`, and `tanh`; commutative multiplication; division by one plus an absolute denominator; clipping to `[-1e6, 1e6]`; and nonfinite invalidation. For each frame, the field selects one seed from all 31 atoms and one descendant among its parent, unary descendants, and products or stabilized quotients with the eleven registered environment companions. It then selects among six evolved single terms, fifteen two-frame pairs, and three human comparators. Coefficients are fitted once on development-fit evidence. The field sees only opaque candidate identity, arm-balanced development evidence, and cost before its final selection record is committed.

## Development evidence

The fixed development set is the seventeen already disclosed arms: eight Gaussian-speed arms, `attractor_ic2`, `attractor_ic5`, `attractor_ic6`, `attractor_ic7`, `attractor_ic10`, `G3`, `G6`, `GC2`, and `GL3`. The first 60% of centered samples is fit evidence and the remaining 40% validation evidence. Every source file is SHA-256 bound in the final receipt.

## Fresh hidden worlds

The four outputs below are generated strictly serially by `research/matter_formation/run_full_observable_v3_holdouts.sh`. Each uses 8,192 particles, 4,096 deterministic tracers, 100,000 accepted steps, stride 400, capacity 256, `dt = 0.05`, tree gravity mode 5, gridless meshless gravity, field-attractor initialization, river calibration, arrangement 0, motion 1, and the normal recorder. Target-blind qualification uses `tools/analyze_trajectory_attractor.py --allow-unregistered`.

| Arm | Shape | Clusters | Radius | Separation | Box | Mass | Field | Seed |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `CH3` | spiral disc, IC 3 | 3 | 90 | 1125 | 7.275 | 1160000 | frozen | 20260925 |
| `CH6` | nested shells, IC 6 | 3 | 150 | 1875 | 12.125 | 4640000 | frozen | 20260926 |
| `CHC3` | spiral disc, IC 3 | 1 | 120 | 0 | 9.70 | 2320000 | frozen | 20260927 |
| `CHL3` | spiral disc, IC 3 | 3 | 120 | 1500 | 9.70 | 2320000 | live | 20260928 |

Outputs live at `CassiCosmos/_diag/matter_formation/full_observable_v3_20260919/<arm>`. Before final field selection, inspection may read only source/config identity, finite arrays, zero recorder overflow, chronological clocks, `status = OK`, `domain_status = BOUNDED`, and relative mass error no greater than `1e-9`. Acceleration is loaded only after selection is committed.

## Classification

Human comparators are inverse-square radial, harmonic radial, and prior `q^0.75 + q` radial support.

- `HUMAN_EQUIVALENT`: selected support is a comparator or has prediction cosine at least `0.999` with one.
- `FULL_OBSERVABLE_LAW`: field construction is below `0.999` cosine to every comparator, improves mean holdout NRMSE by at least 5% over the best comparator, is at most 10% relatively worse on every arm, and has mean holdout NRMSE below `0.85`.
- `REGIME_CONDITIONED_DESCRIPTION`: structurally and semantically distinct construction has mean NRMSE below `0.85` but misses the superiority rule.
- `UNSUPPORTED_REGIME_MODEL`: required evidence is unavailable or selected construction has mean NRMSE at least `0.85`.

Novel syntax alone is not a law.

## Controls and stopping rule

Before the one field invocation: all atom/frame families must fire on synthetic support; acceleration-only mutation leaves feature digests unchanged; deterministic replay reproduces features, neighbors, candidates, and field choices; six synthetic observable laws recover with NRMSE at most `1e-10`; no unselected seed enters a lineage; mutations of source hash, atom, frame, neighbor count, gradient ridge, coefficient, split, lineage, or classification fail independent verification; the runtime makes zero model calls and persists no learned state outside `cognition.field`.

Run `run_cassi_full_observable_invention.py` once with `--campaign-kind full-observable-operator-v3-20260919`, writing `CassiFI/_diag/full-observable-operator-v3/receipt.json`. A runtime failure before receipt assembly is an instrument failure and yields no scientific classification. The first complete independently verified receipt is final. No change may alter evidence, grammar, score, thresholds, split, or these worlds.
