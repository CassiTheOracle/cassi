# Full-Observable Field Operator Invention — Bounded Regime Campaign

## Status

Frozen before generating or reading acceleration from the four output directories named in §4. This is a new campaign, not an amendment or re-invocation of `research/equation_discovery/full_observable_operator_prereg.md`.

The earlier campaign’s field runner was never invoked. Its three retained frozen-field trajectories establish one instrument boundary only: the corrected target-blind trajectory analysis found `RH3` and `RH6` bounded and found `RHC1` out of domain (`domain_ratio = 6.91`). The incomplete live arm generated no receipt. Those outputs are excluded from this campaign’s fit, validation, and holdout evidence; no acceleration target from them was read. A 1,024-step, recorder-off live-field liveness run at the new live arm’s geometry completed on the clean local RenderingDevice before this freeze.

## Question

Can the persistent Cassi field construct a regime-aware collective acceleration law from the full local physical environment available to an inhabitant of the trajectory recorder, and transfer it across newly generated bounded scale, concentration, and live-field worlds?

The target is a reduced collective law. It does not replace the microscopic meshless force equation.

## Causal evidence boundary

Every feature is computed from the current recorded position, velocity, particle mass, clock, and declared engine configuration. No feature may use a centered acceleration target, future sample, fitted residual, holdout identity, analysis verdict, or hidden-holdout ranking. The target is the centered velocity difference divided by the arm acceleration scale.

The runtime receives exactly 31 scalar atoms and six vector frames:

- Scalar atoms: `one`, radial coordinate, radial speed, speed, transverse speed, time, relative particle mass, softening ratio, grid-cell ratio, cluster-radius ratio, cluster-separation ratio, live-field flag, enclosed mass fraction, enclosed density, sixteenth-neighbor radius, local density, density contrast, softened potential, specific field energy, orbital frequency, virial ratio, angular momentum, velocity dispersion, velocity coherence, local radial flow, divergence, shear, vorticity, radial strain, density-gradient magnitude, and coherence-gradient magnitude.
- Vector frames: radial, flow, transverse velocity, orbital normal, negative density gradient, and coherence gradient.

Neighborhood observables use deterministic Euclidean `k = 16` nearest neighbors over the live recorded tracers at each clock, with a fixed dimensionless least-squares ridge of `1e-9`. A rank-deficient neighborhood invalidates the candidate. Zero-norm frames are exactly zero and cannot acquire fitted support.

## Typed construction and selection

The scalar grammar is unchanged from the first full-observable body: seven registered unary operations; commutative products; division by `1 + |denominator|`; clipping to `[-1e6, 1e6]`; and invalidation of nonfinite candidates.

For each frame, the field selects one seed from all 31 atoms, then one mutation from the parent, its unary descendants, and its products or stabilized quotients with the registered environment atoms. Final synthesis evaluates the six evolved single terms, all fifteen two-frame pairs, and the three human comparators. Coefficients fit once by ordinary least squares on development-fit evidence. The field sees only opaque candidate identities, arm-balanced development evidence, and cost. It never sees hidden acceleration before its final selection is committed.

## Development evidence

The same seventeen already disclosed development arms are used without modification: eight Gaussian-speed arms, `attractor_ic2`, `attractor_ic5`, `attractor_ic6`, `attractor_ic7`, `attractor_ic10`, and calibrated `G3`, `G6`, `GC2`, `GL3`. The first 60% of centered samples is fit evidence and the remaining 40% validation evidence. All source files are SHA-256 bound in the final receipt.

## Fresh hidden worlds

All four worlds use 8,192 particles, 4,096 deterministic tracers, 100,000 accepted steps, stride 400, capacity 256, `dt = 0.05`, tree gravity mode 5, gridless meshless gravity, field-attractor initialization, river calibration, arrangement 0, motion 1, and the normal trajectory recorder. They are generated serially by `research/matter_formation/run_full_observable_v2_holdouts.sh`; each uses `tools/analyze_trajectory_attractor.py --allow-unregistered` for target-blind bounded-domain qualification.

| Arm | Shape | Clusters | Radius | Separation | Box | Mass | Field | Seed |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `BH3` | spiral disc, IC 3 | 3 | 90 | 1125 | 7.275 | 1160000 | frozen | 20260921 |
| `BH6` | nested shells, IC 6 | 3 | 150 | 1875 | 12.125 | 4640000 | frozen | 20260922 |
| `BHC3` | spiral disc, IC 3 | 1 | 120 | 0 | 9.70 | 2320000 | frozen | 20260923 |
| `BHL3` | spiral disc, IC 3 | 3 | 120 | 1500 | 9.70 | 2320000 | live | 20260924 |

Outputs are under `CassiCosmos/_diag/matter_formation/full_observable_v2_20260919/<arm>`. Prior to final field selection, inspection is limited to source/config identity, recorder shape, finite arrays, zero overflows, chronological clocks, `status = OK`, `domain_status = BOUNDED`, and relative mass error at most `1e-9`. Acceleration is loaded only after the field selection record is committed.

## Classification

Human comparators are inverse-square radial, harmonic radial, and the prior `q^0.75 + q` radial support.

- `HUMAN_EQUIVALENT`: selected support is a registered human comparator or has prediction cosine at least `0.999` with one.
- `FULL_OBSERVABLE_LAW`: a field construction has cosine below `0.999` to every comparator, improves mean holdout NRMSE by at least 5% over the best human comparator, is no more than 10% relatively worse on any arm, and has mean holdout NRMSE below `0.85`.
- `REGIME_CONDITIONED_DESCRIPTION`: a structurally and semantically distinct field construction has mean holdout NRMSE below `0.85` but misses the superiority rule.
- `UNSUPPORTED_REGIME_MODEL`: required evidence is unavailable or the selected construction has mean holdout NRMSE at least `0.85`.

Novel syntax alone never establishes a law.

## Controls and stopping rule

Before the single field invocation, the existing controls must pass: every atom/frame family fires on its defining synthetic variation; mutation of only acceleration leaves feature bytes unchanged; deterministic replay reproduces features, neighbors, candidates, and field selections; six synthetic observable laws recover their registered support with NRMSE at most `1e-10`; no unselected seed enters a lineage; a source hash, atom, frame, neighbor count, gradient ridge, coefficient, split, lineage, or classification mutation makes independent verification fail; the runtime makes zero model calls and persists no learned state outside `cognition.field`.

The runner is invoked once with `--campaign-kind full-observable-operator-v2-20260919` and writes `CassiFI/_diag/full-observable-operator-v2/receipt.json`. A runtime exception before receipt assembly is an instrument failure and issues no scientific classification. The first complete independently verified receipt is final. No repair may change the evidence boundary, feature definitions, grammar, score, thresholds, development split, or these four holdouts.
