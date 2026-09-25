# Field Operator Invention Pre-registration

## Status

Frozen before implementation executes any acceleration measurement from the reserved scene-calibrated holdouts. The earlier radial-equation campaign and all of its Gaussian and `attractor_ic*` trajectories are development evidence for this campaign. The four reserved arms have been inspected only for recorder shape, configuration, `status = OK`, `domain_status = BOUNDED`, and zero mass drift.

## Question

Can the persistent Cassi field construct a typed equation from recursively composed observables and vector frames, rather than selecting powers from a human radial list, and can that construction predict genuinely new CassiCosmos worlds better than registered human reductions?

The target remains a reduced collective law. No result from this protocol can replace the microscopic meshless N-body equation without a later full-force-state comparison.

## Evidence split

Qualifying arms must have trajectory schema `cassi.trajectory-probe.v1`, `status = OK`, `domain_status = BOUNDED`, no recorder overflow, finite arrays, strictly increasing sample time, and relative mass error at most `1e-9`.

Development fit, first 60% of centered-difference samples:

- `energy_gaussian_s20260910_v0p0`, `v0p5`, `v1p0`, and `v2p0`;
- `attractor_ic2`, `attractor_ic5`, `attractor_ic6`, `attractor_ic7`, and `attractor_ic10`.

Development validation:

- the remaining 40% of those nine arms;
- all samples from `energy_gaussian_s20260911_v0p0`, `v0p5`, `v1p0`, and `v2p0`.

Fresh hidden structural holdout, unavailable until the final field selection record exists:

- `attractor_scene_calibrated/G3`;
- `attractor_scene_calibrated/G6`;
- `attractor_scene_calibrated/GC2`;
- `attractor_scene_calibrated/GL3`.

These holdouts jointly change mass and length scale, geometry, cluster count, and frozen-versus-live field state. Every metadata and binary source is SHA-256 bound in the final receipt.

## Registered observations and coordinates

Acceleration is the centered velocity difference. Live finite tracer indices congruent to zero modulo 16 are retained; radius must exceed `1e-9` after centering on the receipt's `window_center`.

Each arm receives scales derived without looking at acceleration:

\[
R_0=\operatorname{median}_i |\mathbf r_i(t_0)|,\qquad
V_0=\sqrt{M/R_0},\qquad
A_0=M/R_0^2.
\]

The primitive dimensionless observations are

\[
q=|\mathbf r|/R_0,\quad
u_r=(\mathbf v\cdot\hat{\mathbf r})/V_0,\quad
s=|\mathbf v|/V_0,\quad
s_\perp=|\mathbf v-(\mathbf v\cdot\hat{\mathbf r})\hat{\mathbf r}|/V_0.
\]

The target is `a/A0`. These scales use only the initial observed geometry and declared mass; no target-derived normalization is allowed.

## Typed construction language

The host provides a fixed interpreter and validity bounds, not a ranked equation list. Scalar terms are recursively typed trees over the atoms `one`, `q`, `radial_speed`, `speed`, and `transverse_speed`. Registered unary constructors are `abs`, `signed_square`, `signed_sqrt`, `signed_log1p`, `inv1p_abs`, `exp_neg_abs`, and `tanh`. Registered binary constructors are `multiply` and `divide_one_plus_abs`. Every intermediate value is finite-clipped to `[-1e6, 1e6]`; a candidate that requires replacement of a nonfinite value is invalid.

A scalar tree may inhabit one of four vector frames:

1. `radial`: `r_hat`;
2. `flow`: `v/V0`;
3. `transverse`: the non-radial component of `v/V0`;
4. `normal`: `r_hat` crossed with the transverse velocity.

The resulting vector term is multiplied by `A0` only when rendered back in physical units. Fitted coefficients are global across arms.

## Field-owned recursive construction

Candidate identities are content hashes of canonical typed trees. The field sees only opaque identity, development score, cost, and measured development evidence.

1. **Seed phase:** for each vector frame, the field selects among the fixed 25 shallow scalar trees: five atoms; six transforms of `q`; four transforms of signed radial speed; and five transforms each of speed and transverse speed.
2. **Mutation phase:** the selected seed in each frame becomes a parent. Its deterministic typed neighborhood contains the parent, seven unary constructions, multiplication by each atom, division by one plus the absolute value of each atom, and multiplication by each registered transform of `q`. The field selects one descendant per frame. No unselected tree can become a parent.
3. **Synthesis phase:** the field selects among the four evolved single terms, all six two-frame pairs, and the registered human comparators. Coefficients are ordinary least-squares projections fitted once on development-fit evidence.

This is construction lineage, not exhaustive host search: every non-control final term descends from a field-selected parent, and every selection/outcome is retained in the canonical root field.

The score minimized at every phase is arm-balanced validation NRMSE plus `0.005` per fitted term plus `0.001` per typed-tree node. Field priority is `1 - score`.

## Registered human comparisons

The human reduced comparators are:

- inverse-square radial: `-r_hat/q^2` with fitted global coefficient;
- harmonic radial: `q*r_hat` with fitted global coefficient;
- the prior radial support: the fitted pair `q^0.75*r_hat + q*r_hat`.

Human controls participate in the final selection. They do not seed or mutate the invented lineage.

## Classification

After selection and only then holdout disclosure:

- `HUMAN_EQUIVALENT`: the selected final program is a registered human comparator or its holdout prediction cosine with one is at least `0.999`.
- `ALIEN_OPERATOR_LAW`: the selected program descends from field construction, uses a non-human frame or recursive scalar operator, has cosine below `0.999` to every human comparator, improves mean holdout NRMSE by at least 5% over the best comparator, and is no more than 10% relatively worse on any holdout arm.
- `ALIEN_REGIME_DESCRIPTION`: the program is structurally and semantically different and has holdout mean NRMSE below `0.85`, but misses the superiority condition.
- `UNSUPPORTED_INVENTION`: required holdout evidence is unavailable or selected holdout mean NRMSE is at least `0.85`.

No unfamiliar syntax alone establishes a new law.

## Controls and stopping rule

Before the single campaign invocation:

- synthetic harmonic acceleration must select the harmonic comparator with NRMSE at most `1e-10`;
- synthetic linear drag must select a flow-frame constant term with NRMSE at most `1e-10`;
- synthetic normal acceleration must select a normal-frame constant term with NRMSE at most `1e-10`;
- a synthetic radial-plus-flow world must select the corresponding two-term support with NRMSE at most `1e-10`;
- canonicalization must identify alpha-equivalent trees and the semantic-equivalence control must report cosine at least `0.999999999999`;
- removing a selected seed or mutation lineage record, mutating a tree, coefficient, split, source hash, or holdout classification must make the independent verifier fail.

The final runner is invoked once after calibration and metadata-only preflight succeed. It writes `CassiFI/_diag/alien-equation-discovery/receipt.json`. A runtime exception before receipt assembly is an instrument failure and issues no scientific classification; it does not authorize changed evidence, grammar, score, thresholds, or holdouts.
