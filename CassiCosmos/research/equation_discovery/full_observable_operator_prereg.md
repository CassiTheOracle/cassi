# Full-Observable Field Operator Invention Pre-registration

## Status

Frozen before generating or reading acceleration from the four reserved 2026-09-19 holdout worlds. All trajectories used by the earlier radial and typed-operator campaigns are disclosed development evidence. The four new output directories named below do not exist when this protocol is frozen.

## Question

Can the persistent Cassi field use the complete target-independent physical environment recoverable from the canonical trajectory recorder to construct a regime-aware collective acceleration law that transfers across new scale, geometry, and live-field conditions?

The target remains a reduced collective law. It cannot replace the microscopic meshless force equation without a later full-state force comparison.

## Causal evidence boundary

Every feature is computed from the current sample's recorded position, velocity, particle mass, clock, and declared engine configuration. No feature may use the centered acceleration target, a future sample, a fitted residual, hidden-holdout ranking, an arm identity, or an analysis verdict. The target remains the centered velocity difference divided by the arm acceleration scale.

The source recorder provides deterministic tracer identity, `vec4` position/mass, `vec4` velocity/radial velocity, accepted-step clocks, and the complete registered engine configuration. The runtime reconstructs neighborhood geometry and kinematics transiently; it persists no adaptive feature cache or learned sidecar.

## Dimensionless scales

For each arm,

\[
R_0=\operatorname{median}_i |\mathbf r_i(t_0)|,\qquad
V_0=\sqrt{M/R_0},\qquad
A_0=M/R_0^2,
\]

using live deterministic tracers and the declared total mass. The normalized variables are `q = |r|/R0`, `u = v/V0`, and `tau = t V0/R0`. Softening, cell width, cluster radius, and cluster separation are divided by `R0`.

## Complete observable alphabet

The field receives 31 scalar atoms. `one`, `q`, signed radial speed, speed, and transverse speed retain their previous definitions. The additional target-independent atoms are:

1. dimensionless time;
2. particle mass relative to initial mean tracer mass;
3. softening ratio;
4. minimum grid-cell-width ratio;
5. cluster-radius ratio;
6. cluster-separation ratio;
7. live-field flag;
8. enclosed tracer-mass fraction;
9. enclosed mean density `m_enc / ((4 pi / 3) q^3)`;
10. sixteenth-neighbor radius;
11. local sixteenth-neighbor density;
12. local-to-enclosed density contrast;
13. softened potential proxy `m_enc / sqrt(q^2 + eps^2)`;
14. particle-accessible specific field-energy proxy `0.5 |u|^2 - m_enc / sqrt(q^2 + eps^2)`;
15. enclosed orbital-frequency proxy `sqrt(m_enc / (q^3 + eps^3))`;
16. virial ratio `|u|^2 q / (m_enc + eps)`;
17. specific angular-momentum magnitude `q |u_perp|`;
18. local velocity dispersion;
19. local velocity coherence, the neighbor mean-speed divided by RMS speed;
20. local mean radial flow;
21. dimensionless velocity divergence;
22. symmetric-traceless strain magnitude;
23. vorticity magnitude;
24. radial strain;
25. dimensionless log-density-gradient magnitude;
26. dimensionless coherence-gradient magnitude.

Neighborhood quantities use a deterministic Euclidean `k = 16` nearest-neighbor set over all live recorded tracers at the same clock sample. Velocity gradients are least-squares fits of neighbor velocity differences to neighbor position differences with a fixed `1e-9` dimensionless ridge. Density and coherence gradients use the same geometry and ridge. Empty or rank-deficient neighborhoods are invalid; they are never silently replaced by learned values.

The six vector frames are radial, flow, transverse velocity, orbital normal, negative density gradient, and coherence gradient. A zero-norm frame produces the zero vector and cannot acquire support through a fitted coefficient.

## Typed construction

Canonical scalar trees use the 31 atoms and the registered unary operations `abs`, `signed_square`, `signed_sqrt`, `signed_log1p`, `inv1p_abs`, `exp_neg_abs`, and `tanh`, plus commutative multiplication and division by one plus an absolute denominator. Every intermediate value is clipped to `[-1e6, 1e6]`; any nonfinite result invalidates the candidate.

For each of the six vector frames:

1. the root field selects one seed from all 31 atoms;
2. only that selected seed may reproduce;
3. the mutation family contains the parent, its seven unary descendants, and its products and stabilized quotients with eleven registered environment atoms: `q`, `speed`, `enclosed_mass`, `local_density`, `density_contrast`, `field_energy`, `velocity_dispersion`, `velocity_coherence`, `divergence`, `shear`, and `coherence_gradient`;
4. the root field selects one descendant.

Final synthesis contains the six evolved single terms, all fifteen two-frame pairs, and the three registered human comparators. Global coefficients are fitted once by ordinary least squares on development-fit evidence. Selection minimizes arm-balanced validation NRMSE plus `0.005` per term and `0.001` per typed-tree node. The field receives only opaque candidate identity, measured development evidence, and cost. It receives no hidden target.

## Development evidence

All seventeen qualifying arms from the previous campaigns are now development evidence:

- eight Gaussian speed arms: seeds `20260910` and `20260911`, each at speeds `0`, `0.5`, `1`, and `2`;
- `attractor_ic2`, `attractor_ic5`, `attractor_ic6`, `attractor_ic7`, and `attractor_ic10`;
- calibrated `G3`, `G6`, `GC2`, and `GL3`.

The first 60% of centered samples is development fit. The remaining 40% is development validation. Every raw and metadata source is SHA-256 bound.

## Fresh hidden worlds

The following worlds are generated only after this document is frozen. Each uses 8,192 particles, 4,096 deterministic tracers, 100,000 accepted steps, stride 400, capacity 256, `dt = 0.05`, tree gravity mode 5, gridless meshless gravity, field-attractor initialization, river calibration, arrangement 0, motion 1, and seed `20260919` unless stated otherwise.

| Arm | Shape | Clusters | Radius | Separation | Box | Mass | Field | Seed |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `RH3` | spiral disc, IC 3 | 3 | 90 | 1125 | 7.275 | 1160000 | frozen | 20260919 |
| `RH6` | nested shells, IC 6 | 3 | 150 | 1875 | 12.125 | 4640000 | frozen | 20260919 |
| `RHC1` | spiral disc, IC 3 | 1 | 120 | 0 | 1.17 | 2320000 | frozen | 20260920 |
| `RHL3` | spiral disc, IC 3 | 3 | 120 | 1500 | 9.70 | 2320000 | live | 20260920 |

Outputs are under `CassiCosmos/_diag/matter_formation/regime_holdout_20260919/<arm>`. Before final field selection, inspection is limited to recorder shape, source/config identity, `status = OK`, `domain_status = BOUNDED`, finite arrays, zero overflow, chronological clocks, and relative mass error at most `1e-9`. Hidden acceleration is loaded only after the canonical final selection record exists.

## Registered comparisons and classification

The human comparators remain inverse-square radial, harmonic radial, and the prior `q^0.75 + q` radial support.

After hidden disclosure:

- `HUMAN_EQUIVALENT`: the selected support is a registered human comparator or has prediction cosine at least `0.999` with one.
- `FULL_OBSERVABLE_LAW`: a field-constructed program has cosine below `0.999` to every human comparator, improves mean holdout NRMSE by at least 5% over the best human comparator, is no more than 10% relatively worse on any holdout arm, and has mean holdout NRMSE below `0.85`.
- `REGIME_CONDITIONED_DESCRIPTION`: a structurally and semantically distinct field construction has mean holdout NRMSE below `0.85` but misses the superiority rule.
- `UNSUPPORTED_REGIME_MODEL`: required evidence is unavailable or the selected constructed program has mean holdout NRMSE at least `0.85`.

Novel syntax alone never establishes a law.

## Controls

Before the single campaign invocation:

1. all 31 atoms must be finite and nonconstant where their defining synthetic fixture varies;
2. changing positions, velocities, masses, clock, softening, grid scale, cluster scale, or live-field state must fire the corresponding observable family;
3. mutating only the acceleration target must leave every feature digest unchanged;
4. deterministic replay must reproduce feature bytes, nearest-neighbor identities, candidate identities, and field choices exactly;
5. synthetic laws over enclosed mass, field energy, divergence, strain, density-gradient frame, and coherence-gradient frame must recover their registered support with NRMSE at most `1e-10`;
6. no unselected seed may enter a mutation or synthesis lineage;
7. mutating an atom, frame, neighbor count, gradient ridge, coefficient, split, source hash, selection record, or classification must make the independent verifier fail;
8. the live runtime must make zero model calls and persist no learned state outside `cognition.field`.

## Stopping rule

After calibration and metadata-only holdout qualification, the runner is invoked once and writes `CassiFI/_diag/full-observable-operator/receipt.json`. A runtime exception before receipt assembly is an instrument failure and issues no scientific classification. A repair may restore execution or replay already-retained field choices, but may not change evidence, feature definitions, grammar, score, thresholds, or holdouts. The first complete independently verified receipt is final.
