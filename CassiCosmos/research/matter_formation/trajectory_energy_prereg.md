# Gaussian radial layers across energy and seed

## Status: Frozen—September 10, 2026

## 1. Question

Can a single Gaussian cloud with no shell geometry develop persistent radial layers as its initial kinetic-energy scale changes, and how sensitive is that outcome to the finite-sample seed?

The probe tests the dynamical hypothesis suggested by the live presentation: a radial layer may be a transient fold produced by collapse, rebound, and phase mixing, with the accessible pattern set by the initial energy and microscopic realization. It measures particle trajectories under the production tree-force configuration. It does not identify simulated particles with physical atoms or elementary particles, and it does not test the fluid-to-matter conversion pathway.

## 2. Registered implementation

The existing passive trajectory recorder samples the authoritative particle position and velocity buffers after accepted engine steps. The existing radial analyzer computes the normalized late-time profile, ridge prominence, epoch timeline, concentration, sphericity, and radial phase-space stream diagnostic. The probe adds one command-line input, `--speed`, which is recorded as `initial_speed` and passed to the existing initial-condition motion constructor. No solver, merge, field, or presentation code changes are part of the measurement.

The configuration uses the Gaussian shape and a single component. The Gaussian sampler has no prescribed shell count or shell radii. Every arm uses the same shape settings, force configuration, timestep, horizon, tracer selection, and analysis thresholds; only the deterministic seed and the initial inward speed vary.

## 3. Frozen controls and arms

Physics shared by every arm:

- `initial_condition = Gaussian` (index 1), `initial_arrangement = Single` (index 2), `initial_motion = Inward` (index 4);
- `gridless_physics = true`, `gravity_mode = 5`, mutual tree gravity, `field_attractor_init = true`, `freeze_field = true`, `source_strength = 0`, `river_calibrate_gn = false`;
- `N_particles = 8192`, `tracers = 4096`, `initial_total_mass = 1000`, `cluster_radius = 25`, `box_scale = 1`, `dt = 0.001`, `xi = \varphi^6`, `softening = 0.1`;
- merge, black holes, dual grid, and event production disabled; tree cadence 1;
- 100,000 accepted steps, batches of 64, eight batches per frame, samples every 400 steps, 256 history slots, and a 65,536-record event buffer.

`initial_speed` is the magnitude passed to the inward motion constructor. Speed zero is the at-rest control; it generates the same zero velocity field as the explicit at-rest choice while keeping the motion selector fixed across the factorial arms. The speed levels are an ordered kinetic-energy scale, not a claim that the total conserved energy is known from the tracer receipt.

| Arm family | Seed | Speed | Output directory |
|---|---:|---:|---|
| V0 | 20260910 | 0.0 | `res://_diag/matter_formation/energy_gaussian_s20260910_v0p0` |
| V05 | 20260910 | 0.5 | `res://_diag/matter_formation/energy_gaussian_s20260910_v0p5` |
| V1 | 20260910 | 1.0 | `res://_diag/matter_formation/energy_gaussian_s20260910_v1p0` |
| V2 | 20260910 | 2.0 | `res://_diag/matter_formation/energy_gaussian_s20260910_v2p0` |
| R0 | 20260911 | 0.0 | `res://_diag/matter_formation/energy_gaussian_s20260911_v0p0` |
| R05 | 20260911 | 0.5 | `res://_diag/matter_formation/energy_gaussian_s20260911_v0p5` |
| R1 | 20260911 | 1.0 | `res://_diag/matter_formation/energy_gaussian_s20260911_v1p0` |
| R2 | 20260911 | 2.0 | `res://_diag/matter_formation/energy_gaussian_s20260911_v2p0` |

The receipt must contain every frozen input, the accepted-step count, finite/live counters, and all raw trajectory files. A missing, truncated, nonfinite, overflowing, or mass-inconsistent artifact is a runtime `FAIL` for that arm and is excluded from the scientific comparison.

## 4. Measurements

For each qualifying arm, the analyzer reports:

1. the late-window radial profile in 48 bins of `u = r/r50`, averaged over the final quarter of stored samples;
2. local radial ridges with the existing prominence threshold of 1.25, restricted to `0.1 <= u <= 2.5`;
3. the per-sample ridge-count series and eight-sample epoch timeline, which distinguish an instantaneous layer from a persistent late profile;
4. `r50`, `r90/r50`, sphericity, finite/live counts, and mass closure;
5. the final and mid-window radial phase-space stream diagnostic;
6. the recorded seed, motion index, speed, and the controlled kinetic scale `v^2`. The speed is the prescribed magnitude in the inward constructor; the scan does not infer a conserved total energy from the sampled tracer state.

The existing shell criterion is descriptive: at least two late-profile ridges means `SHELL_SUPPORTS`; fewer means `SHELL_DOES_NOT_EMERGE`. This criterion is applied without changing its threshold or binning.

The energy comparison is reported in two layers. First, each arm keeps its own shell verdict. Second, the factorial table reports the speed-group median and seed-to-seed spread for ridge count, ridge positions, late ridge persistence, and the controlled kinetic scale `v^2`. A speed effect is called `SUPPORTS` only if both seeds show a qualifying two-ridge late profile at the same nonzero speed and the speed-group profile differs from its own zero-speed control by at least one ridge position within `|Delta u| > 0.15`; otherwise the result is `DOES NOT EMERGE` for this registered scan. If a required arm fails structurally, the comparison is `INCONCLUSIVE` rather than repaired by changing the arm set.

Seed sensitivity is reported separately. A condition is `seed-stable` when both seed arms have the same shell verdict and their ridge lists can be greedily matched within `|Delta u| <= 0.15`; disagreement is `seed-sensitive` and is evidence for realization-dependent dynamics, not a failed run.

## 5. Decision boundary and scope

The scan supports an energy-conditioned shell mechanism at the tested scale only when the registered two-seed, nonzero-speed criterion passes. It reports `DOES NOT EMERGE` when all qualifying nonzero speed groups fail that criterion. It reports `INCONCLUSIVE` when any required arm is structurally invalid or the two seeds disagree in a way that prevents the comparison.

A positive result would motivate a longer horizon and a broader energy/phase-space sweep. A negative result would constrain the energy-only explanation; it would not rule out multi-component caustics, live-field forcing, or event-time layers in the production scene. The scan does not promote a visual shell count into an atomic-shell claim.

## 6. Evidence retention

The raw receipt and binary arrays remain under each registered output directory. The independent summary is written to `_diag/matter_formation/energy_gaussian_summary.json`, with one per-arm `analysis.json` beside the raw arrays. The summary records the preregistration path, frozen arm table, structural statuses, radial metrics, controlled speed scales, seed matching, and the registered verdict.

## 7. Results

All eight registered arms completed with exit code 0 and passed the independent structural analysis. Each receipt contains 100,000 accepted steps, 251 stored samples, 4,096 tracers, 8,192 live particles at both endpoints, zero event or sample overflow, and zero relative mass error. Every arm remained within the configured domain, with maximum-radius ratios from 1.167 to 1.490.

The late-window mean radial profile has one ridge in every arm, so every arm returns `SHELL_DOES_NOT_EMERGE` under the preregistered two-ridge criterion. The instantaneous late-window ridge count also remains one. The epoch timeline does show intermittent complexity: across 32 eight-sample epochs, the number with at least two ridges is 8–12 per arm. That complexity is lost in the late-window mean rather than forming a persistent layered profile. The final phase-space diagnostic has a median of one radial-velocity mode in all arms; its excess-bin fraction reaches 0.139 in the speed-2.0 arm with seed 20260910.

| Speed | `v^2` | Seed 20260910: `r50` / ridge | Seed 20260911: `r50` / ridge |
|---:|---:|---:|---:|
| 0.0 | 0.00 | 8.024 / 0.781 | 8.874 / 0.781 |
| 0.5 | 0.25 | 8.411 / 0.781 | 8.976 / 0.656 |
| 1.0 | 1.00 | 8.778 / 0.781 | 9.446 / 0.656 |
| 2.0 | 4.00 | 9.430 / 0.719 | 10.159 / 0.719 |

The seed pairs are `seed-stable` under the registered ridge-match tolerance for every speed. The speed changes the late median radius and the amount of intermittent epoch structure, while the averaged radial state retains one ridge. No nonzero speed group satisfies the two-seed shell criterion, so the registered scan returns `DOES NOT EMERGE`.

This result constrains an energy-only explanation for persistent three-layer structure in a single Gaussian cloud under the fixed tree force, frozen attractor field, and 100,000-step horizon. It leaves open event-time caustics in multi-component collapse, live-field forcing, longer relaxation horizons, and other initial-motion families.
