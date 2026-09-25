# Full-Observable Field Operator Invention — Zero-Response-Safe Campaign

## Status

Frozen before creating the four V4 output directories and after the V3 executor stopped before receipt assembly. V3 produced no receipt or scientific classification: its inherited 17-arm development score required a per-arm NRMSE for `GL3`, whose disclosed centered-acceleration target has exactly zero energy. The executor correctly rejected the undefined denominator before it loaded a V3 holdout. Excluding that arm changes the development evidence, so V4 is a new protocol rather than a repair or re-invocation of V3.

## Question

Can the persistent Cassi field construct a regime-aware collective acceleration law from the complete local target-independent trajectory environment available in a recorder, then transfer it into newly generated bounded scale, concentration, and live-field worlds?

## Observable language

Each candidate receives 31 target-independent scalar atoms: `one`, radial coordinate, radial speed, speed, transverse speed, time, relative particle mass, softening ratio, grid-cell ratio, cluster-radius ratio, cluster-separation ratio, live-field flag, enclosed mass fraction, enclosed density, sixteenth-neighbor radius, local density, density contrast, softened potential, specific field energy, orbital frequency, virial ratio, angular momentum, velocity dispersion, velocity coherence, local radial flow, divergence, shear, vorticity, radial strain, density gradient, and coherence gradient.

The six frames are radial, flow, transverse velocity, orbital normal, negative density gradient, and coherence gradient. Neighborhood quantities use deterministic Euclidean `k = 16` nearest neighbors across live tracers at the same clock and a fixed dimensionless least-squares ridge of `1e-9`. Rank-deficient neighborhoods invalidate a candidate. Zero-norm frames are zero.

Features may use only the current sample’s recorded position, velocity, particle mass, clock, and declared engine configuration. They may not use a centered acceleration target, future sample, residual, holdout identity, analysis verdict, or holdout rank. The target is the centered velocity difference divided by each arm’s acceleration scale.

The grammar is fixed: registered unary operations `abs`, `signed_square`, `signed_sqrt`, `signed_log1p`, `inv1p_abs`, `exp_neg_abs`, and `tanh`; commutative multiplication; division by one plus an absolute denominator; clipping to `[-1e6, 1e6]`; and nonfinite invalidation. For each frame, the field selects one seed from all 31 atoms and one descendant among its parent, unary descendants, and products or stabilized quotients with the eleven registered environment companions. It then selects from the six evolved one-term equations, their fifteen two-term combinations, and the three human comparators. Every selection is written through `cognition.field`; no model call or learned sidecar is permitted.

## Development evidence

The fixed development set is the sixteen disclosed arms with nonzero centered-acceleration energy: the eight Gaussian-speed arms, `attractor_ic2`, `attractor_ic5`, `attractor_ic6`, `attractor_ic7`, `attractor_ic10`, `G3`, `G6`, and `GC2`. `GL3` is retained as a documented stationary calibration boundary but is not development evidence because its zero target makes per-arm NRMSE mathematically undefined. The first 60% of centered samples is fit evidence and the remaining 40% validation evidence. Every source file is SHA-256 bound in the final receipt.

## Fresh hidden worlds

The four outputs below are generated strictly serially by `research/matter_formation/run_full_observable_v4_holdouts.sh`. Each uses 8,192 particles, 4,096 deterministic tracers, 100,000 accepted steps, stride 400, capacity 256, `dt = 0.05`, tree gravity mode 5, gridless meshless gravity, field-attractor initialization, river calibration, arrangement 0, motion 1, and the normal recorder. Target-blind qualification uses `tools/analyze_trajectory_attractor.py --allow-unregistered`.

| Arm | Shape | Clusters | Radius | Separation | Box | Mass | Field | Seed |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `DH3` | Spiral disc | 3 | 90 | 1125 | 7.275 | 1,160,000 | frozen | 20260929 |
| `DH6` | Nested shells | 3 | 150 | 1875 | 12.125 | 4,640,000 | frozen | 20260930 |
| `DHC3` | Spiral disc | 1 | 120 | 0 | 9.70 | 2,320,000 | frozen | 20261001 |
| `DHL3` | Spiral disc | 3 | 120 | 1500 | 9.70 | 2,320,000 | live | 20261002 |

Outputs live at `CassiCosmos/_diag/matter_formation/full_observable_v4_20260919/<arm>`. Before final field selection, inspection may read only source/config identity, finite arrays, zero recorder overflow, chronological clocks, `status = OK`, `domain_status = BOUNDED`, and relative mass error no greater than `1e-9`. Acceleration is loaded only after selection is committed.

## Classification

Human comparators are inverse-square radial, harmonic radial, and prior `q^0.75 + q` radial support.

- `HUMAN_EQUIVALENT`: selected support is a comparator or has prediction cosine at least `0.999` with one.
- `FULL_OBSERVABLE_LAW`: field construction is below `0.999` cosine to every comparator, improves mean holdout NRMSE by at least 5% over the best comparator, is at most 10% relatively worse on every arm, and has mean holdout NRMSE below `0.85`.
- `REGIME_CONDITIONED_DESCRIPTION`: structurally and semantically distinct construction has mean NRMSE below `0.85` but misses the superiority rule.
- `UNSUPPORTED_REGIME_MODEL`: required evidence is unavailable or selected construction has mean NRMSE at least `0.85`.

Novel syntax alone is not a law.

## Controls and stopping rule

Before the one field invocation: all atom/frame families must fire on synthetic support; acceleration-only mutation leaves feature digests unchanged; deterministic replay reproduces features, neighbors, candidates, and field choices; six synthetic observable laws recover with NRMSE at most `1e-10`; every V4 development arm must have finite strictly positive target energy in both fit and validation splits; no unselected seed enters a lineage; mutations of source hash, atom, frame, neighbor count, gradient ridge, coefficient, split, lineage, or classification fail independent verification; the runtime makes zero model calls and persists no learned state outside `cognition.field`.

Run `run_cassi_full_observable_invention.py` once with `--campaign-kind full-observable-operator-v4-20260919`, writing `CassiFI/_diag/full-observable-operator-v4/receipt.json`. A runtime failure before receipt assembly yields no scientific classification. The first complete independently verified receipt is final. No change may alter evidence, grammar, score, thresholds, split, or these worlds.
