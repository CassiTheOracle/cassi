# Site-Target Gravity and Persistent-Refit Preregistration

**Date:** 2026-08-31  
**Status:** FROZEN BEFORE THE FIRST CANDIDATE RUN  
**Scope:** Default-off site-target evaluation and persistent tree refit in the gridless `CassiPhysicsEngine` path. The existing particle-target tree remains the control.

## Question

Can the existing open-boundary quadrupole tree become materially cheaper without changing its source law by:

1. evaluating the gravity field at the 8,192 moving Voronoi sites instead of every particle, then sampling the owning site's value during KDK; and
2. retaining Morton order and node topology while sites are stationary, refreshing only live source weights and node moments?

The Yang/Yin double-helix mathematics is not a gravity law in this probe. Its density-plane current may be tested later only as an approximation diagnostic, and only if the live spatial-winding eligibility gate passes.

## Frozen implementation arms

- **Control P:** current per-particle tree targets, full structural build on every tree job.
- **Arm S:** site targets, full structural build on every tree job.
- **Arm SR:** site targets plus persistent topology; full build only after the mesh topology generation changes, otherwise source refresh plus one moments pass.

All new controls default OFF. OFF must preserve the current buffer sizes, shader branches, dispatch order, and output bytes.

## Baseline accounting

The current full tree build records 123 dispatches:

- two counter/root initialization dispatches;
- one live-site gather dispatch;
- 91 bitonic sort stages;
- 28 split/commit dispatches (14 levels times two);
- one moments dispatch.

The subsequent gravity walk is separate. These counts are code-path facts, not timings. Historical CPU/probe figures in the existing meshless reports are context only and are not accepted as current GPU performance evidence.

## Frozen data and timing protocol

The focused local-RenderingDevice probe uses one deterministic snapshot and one tree for both target arms.

- Accuracy population: the verifier's live particle snapshot and all 8,192 sites.
- Performance population: 262,144 deterministic target positions for Control P versus all 8,192 site positions for Arm S.
- Each timed dispatch sequence receives three warmups and eleven measured repetitions.
- Each repetition is submitted and synchronized independently; elapsed wall microseconds are recorded around `submit()` plus `sync()`.
- P and S order alternates by repetition.
- Report median and raw samples. The synchronized wall median is the primary timing statistic.
- No production-speed claim is allowed from target-count arithmetic alone.

## G61 — Site-target force fidelity

For each live particle, compare Control P's tree gradient at its exact position against Arm S's gradient at the Euclidean-nearest live site. Exclude only comparisons whose Control P norm is below `1e-8`; report the excluded count.

**PASS iff all hold:**

1. global median relative vector error `<= 1.0e-2`;
2. global 99th-percentile relative vector error `<= 5.0e-2`;
3. median relative error in the top coherence quartile `<= 1.0e-2`;
4. median relative error in the top deposited-mass quartile `<= 1.0e-2`; and
5. opposite-direction fraction (dot product `< 0`) `<= 1.0e-3`.

If nearest-site sampling fails, the only permitted follow-up in this probe is an existing-neighbor interpolation or local tidal reconstruction, registered as a new amendment before it runs. Thresholds do not move.

## G62 — Site-target walk cost

**PASS iff:**

1. Arm S synchronized median walk time is `<= 0.25 *` Control P median walk time on the frozen 262,144-target performance population; and
2. Arm S produces finite gradients for every site.

The theoretical target ratio is reported but is not a gate result.

## G63 — Persistent-refit identity and cost

With site positions fixed, apply one deterministic change to live mass and Yang/Yin values. Compare:

- **fresh:** a complete 123-dispatch rebuild followed by a site walk;
- **refit:** the retained sorted hierarchy, one source-refresh dispatch, one moments dispatch, and a site walk.

**PASS iff all hold:**

1. source ordering is byte-identical;
2. active node count and node ranges are byte-identical;
3. site-gradient output is byte-identical; and
4. median synchronized refit preparation time is `<= 0.25 *` the fresh-build preparation median.

Any site-position or topology-generation change must force the next job through the complete build before its walk.

## G64 — Engine stability and off-state identity

A focused windowed engine scene runs the gridless path with Arm SR enabled through initialization, at least one full topology-generation transition, and at least 32 completed physics steps.

**PASS iff:**

1. step counter reaches the stopping point;
2. positions, velocities, accelerations, site values, and tree gradients remain finite;
3. the tree records at least one full build and at least one refit;
4. a topology-generation change is followed by another full build; and
5. the feature-OFF verifier and the complete battery retain their existing verdicts.

## G65 — Helix eligibility stopping rule

No flow-aware opening code is implemented unless a fresh live topology observation under the accepted SR arm finds, in each of three consecutive registered snapshots:

- at least three nonzero integer-winding rings;
- winding fraction `>= 0.05`; and
- maximum closure residual `<= 1.0e-5`.

Synthetic helical input alone cannot pass eligibility. Failure of G65 is a completed negative result and stops the helix implementation branch.

## G66 — Conditional equal-budget flow diagnostic

Only if G65 passes, aggregate

`J_d = E_Y * grad(E_I) - E_I * grad(E_Y)`

without changing source mass or the force law. Compare the existing `q`-only opening criterion against `q + J_d` at matched mean node interactions on double-helix, straight-filament, vortex, spherical-cluster, shuffled-field, and live snapshots.

**PASS iff** the `q + J_d` arm lowers median force error by at least 10% on the registered helical/live winding cases, changes median force error by no more than 2% on every non-helical control, and does not increase 99th-percentile error on any case.

## Decision tree

1. Run G61 and G62 for Arm S.
2. If either fails, record `REJECT` for nearest-site site-target gravity and stop before persistent refit production wiring.
3. If both pass, implement and run G63.
4. If G63 passes, run G64 and the complete battery with all new features OFF by default.
5. Only an accepted SR arm may proceed to G65.
6. G65 failure stops the helix branch with no production helix code.
7. G66 alone may authorize a default-off flow-aware opening arm; it never authorizes a new gravitational force term.

## Amendment A — registered after nearest-site rejection, before interpolation evaluation

The frozen nearest-site Arm S returned median relative gradient error
`1.298e-1`, 99th-percentile error `3.951e-1`, and synchronized walk ratio
`0.7570`; G61 and G62 therefore reject nearest-site sampling. The timing is
submission-latency dominated at the registered 262,144-target control size.

The preregistration explicitly permits an existing-neighbor interpolation or
local tidal reconstruction after this result. The following deterministic
ladder is frozen before evaluating either candidate:

1. **A1 — eight-neighbor inverse-distance interpolation.** For each particle,
   use its eight Euclidean-nearest sites with weights
   `1 / max(distance_squared, 1e-12)`, normalized to sum one.
2. **A2 — local affine/tidal reconstruction.** Only if A1 fails G61, fit each
   acceleration component over the sixteen Euclidean-nearest sites using the
   basis `[1, dx, dy, dz]` centered on the nearest site and an ordinary
   least-squares solve, then evaluate that affine field at the particle.

Each candidate is compared to the same exact-position particle-target
gradient and the original G61 thresholds do not move. Stop at the first
candidate that passes. If neither passes, site-target gravity is rejected.

These offline Euclidean neighborhoods diagnose the attainable interpolation
accuracy. A production implementation may use the already-published Voronoi
CSR neighbors only after verifying that its result independently passes the
same G61 metrics.

G62 is amended only to remove synchronized submission latency from the
primary statistic. A second timing population of 2,097,152 particle targets
versus 8,192 site targets is registered, with three warmups and eleven
alternating repetitions. G62 PASS requires the site-target median to be
`<= 0.25 *` the particle-target median on that population. The original
262,144-target samples remain reported.

## Amendment B — registered after interpolation rejection, before refit work

On the frozen follow-up snapshot, A1 returned median/99th errors
`1.359e-1 / 4.180e-1`; A2 returned `7.585e-2 / 2.231e-1`. Both fail G61.
The amended 2,097,152-target timing returned a site/control ratio `0.2297`,
which passes G62, but cost cannot rescue the failed force contract.
Site-target gravity is therefore `REJECT`; its production toggle and shader
index branch are removed rather than retained as dormant weight.

Persistent topology refit is independent of the rejected target sampling:
the particle-target control repeatedly rebuilds an unchanged site hierarchy.
The remaining experiment is therefore narrowed to **Arm PR**:

- keep the existing per-particle tree target and gradient buffer unchanged;
- perform a complete structural build after every topology-generation change;
- otherwise refresh live sorted source records and run one moments pass before
  the unchanged per-particle walk.

G63 keeps its frozen identity and `<= 0.25` preparation-cost thresholds, but
the compared gradient is the existing per-particle output. G64 runs Arm PR,
not SR. An accepted PR arm may proceed to G65; a failed PR arm stops there.

## Amendment C — G63 outcome and stopping decision

The registered persistent-refit probe changed mass and both Yang/Yin source
values while holding site positions fixed. Source order, active-node count,
per-particle gradient bytes, and gradient finiteness matched the fresh build.
Active node-range bytes did not match.

The eleven synchronized preparation samples were:

- fresh 123-dispatch build: `[4508, 4292, 4433, 4617, 4641, 4419, 4469, 4199, 4427, 4257, 4471]` microseconds, median `4433`;
- two-dispatch refit: `[1911, 1924, 1962, 1977, 1974, 1843, 2015, 1721, 1957, 1695, 2019]` microseconds, median `1957`;
- refit/fresh median ratio: `0.441462`.

G63 is `FAIL`: node-range identity fails and the timing ratio exceeds the
frozen `0.25` ceiling. Arm PR is `REJECT`. The production configuration and
dispatch branch are removed; mode 11 remains reachable only from the focused
research verifier so the negative result is reproducible.

The decision tree stops before G64. PR is not an accepted arm, so G65 is
ineligible and no flow-aware opening code is implemented. G66 is not run.
