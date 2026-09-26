# Particle-shape radial-layer probe (multi-IC)

## Status: Frozen—September 10, 2026

## 1. Question

The live scene shows a particle cloud that settles into a three-layer sphere for
several different initial shapes. This probe asks whether that layered radial
structure is a general outcome of the particle dynamics for structurally
different initial conditions, or whether it is specific to particular shapes or
to the presentation layer.

This probe measures the particle dynamics only. It records the raw particle
positions and velocities from the default-off trajectory recorder while the
engine steps the site-native tree force arm. The field is held at the attractor
initialization for the whole run, so the experiment isolates the particle
response under a fixed, nearly uniform force prefactor. The field's autonomous
evolution, the fluid-to-matter collapse pathway, particle identity, and any
claim that the simulated particles are physical elementary particles are outside
this probe's scope. The presentation layer is not measured here; it renders the
same particle buffers this probe reads.

## 2. Why the single-condition result is not the answer

A layered structure in one initial condition does not establish a general
attractor. The registered shell/ancestry probe steps one initial condition
(nested shells) under the Plummer reference arm, whose force is a fixed analytic
softened point mass summed over the cluster records written at initialization:
the particles are test particles in a static external potential, and the
recorded structure is their turning-point caustic pattern. The production scene
does not run that arm. It runs the site-native tree arm with mutual gravity, at
rest, with the field initialized at the attractor. The comparison below varies
the initial condition inside the production force configuration.

## 3. Frozen configuration

Physics (identical for every arm):

- `gridless_physics = true` (the engine then runs the meshless site topology
  with tree gravity, gravity mode 5, mutual gravity),
- `field_attractor_init = true`, `freeze_field = true`, `source_strength = 0`,
- `initial_motion = At rest` (index 1) and `initial_arrangement = Ring` (index 0)
  for every arm, matching the main scene's initial-motion export,
- `N_particles = 8192`, `initial_total_mass = 1000`, `cluster_radius = 25`,
  `box_scale = 1`, `window_center = (0,0,0)`,
- `dt = 0.001`, `softening = 0.1`, `xi = 17.94427191`, `seed = 20260910`,
- particle merge disabled, black holes disabled, dual grid off,
- tree cadence 1 (the engine default): the tree is rebuilt every submitted job,
  and a tree job is capped at 8 steps, so the force is refreshed at least every
  8 accepted steps.

Recorder (identical for every arm): 4096 tracers, samples every 4096 accepted
steps in a 256-slot ring, 65536-slot event capacity. Horizon: 1,000,000 accepted
steps for every arm (245 stored samples).

Arms (only the initial shape index varies):

| Arm | `--ic` | Shape | Output directory |
|---|---|---|---|
| A0 | 2 | Uniform sphere | `res://_diag/matter_formation/attractor_ic2` |
| A1 | 3 | Spiral disc | `res://_diag/matter_formation/attractor_ic3` |
| A2 | 5 | Pearl ring | `res://_diag/matter_formation/attractor_ic5` |
| A3 | 7 | Double helix | `res://_diag/matter_formation/attractor_ic7` |
| A4 | 8 | Filament web | `res://_diag/matter_formation/attractor_ic8` |
| A5 | 10 | Folded sheet | `res://_diag/matter_formation/attractor_ic10` |
| A6 | 11 | Trefoil cloud | `res://_diag/matter_formation/attractor_ic11` |
| A7 | 6 | Nested shells (reference) | `res://_diag/matter_formation/attractor_ic6` |

Command template (one arm; windowed, never `--headless`):

```
Godot_v4.7.1-stable_mono_win64_console.exe --path . \
  res://scenes/verify_trajectory_probe.tscn -- \
  --mode=shell --recorder=on --ic=<IC> --arrangement=0 --motion=1 \
  --gridless=on --gravity=5 --field-attractor-init=on \
  --particles=8192 --tracers=4096 --sample-stride=4096 --sample-capacity=256 \
  --event-capacity=65536 --merge-cadence=64 --dt=0.001 --steps=1000000 \
  --batch-steps=64 --batches-per-frame=8 --timeout-sec=1800 \
  --out-dir=res://_diag/matter_formation/attractor_ic<IC>
```

`--timeout-sec=1800` is a hang guard only: a run that trips it is a runtime
failure and is repaired and rerun with the same frozen inputs.

`research/matter_formation/run_trajectory_attractor_arms.sh` runs the table
sequentially and is the registered invocation.

## 4. Measurements

Per arm, from the receipt and the raw arrays only (the same reader and the same
fail-closed checks the registered analyzer uses for a `shell` receipt):

1. tracer radius about the window center for every stored sample, live and
   finite tracers only;
2. per-sample median radius `r50`;
3. the late window is every stored sample at or above 75% of the accepted step
   count (about 61 samples at the registered horizon);
4. the normalized radial profile: `u = r / r50(sample)` per sample, 48 bins over
   `u ∈ [0, 3]`, each sample contributing its share of live tracers per bin
   divided by the bin width; the profile `P(u)` is the mean over late-window
   samples;
5. ridges of `P`: a bin is a local maximum when it exceeds both neighbors; its
   key saddle is the higher of the two nearest running minima reached before a
   bin whose value is at least the peak's value; the ridge prominence ratio is
   the peak value divided by the key-saddle value;
6. shell ridges: local maxima with prominence ratio at least 1.25 and
   `u ∈ [0.1, 2.5]`; a repeated peak in adjacent bins counts once;
7. sphericity at the final sample from the tracer inertia tensor: sorted
   semi-axis ratios `sqrt(λ2/λ1)` and `sqrt(λ3/λ1)`;
8. concentration diagnostics: `r50`, `r90`, and the late-window mean of
   `r90 / r50`; initial support radius of the arm; initial-versus-final live
   count and total mass.

Descriptive additions (no effect on any verdict): the `r50` series over the late
window reported as mean, standard deviation, minimum and maximum, which measures
how much the cloud is radially breathing in the late state; the per-sample ridge
count over the late window reported as minimum, median and maximum; and the
final-sample ridge count. These distinguish a persistent instantaneous layer
structure from a structure that appears only when the display accumulates the
last 45% of previous frames, which the live scene does.

One further descriptive addition, made before the app-fidelity arms ran and
reported for the primary arms as well: an epoch timeline that averages
consecutive samples in groups of eight and applies the same ridge rule to each
group, so the shell structure is followed across the whole run at about a fifth
of the single-sample profile noise. It answers when a layer structure exists and
whether its radii stay put, which the late-window mean alone cannot show. Its
ridge significances are reported as the peak-minus-saddle difference in units of
the propagated profile standard error.

A second descriptive addition: a radial phase-space stream count in the
band `u ∈ [0.3, 1.6]` of the final samples. A caustic shell is a fold of the
radial phase-space sheet, so inside a shell the tracers split into streams with
distinct `|v_r|` while a relaxed single cloud fills one broad band. For each of
nine radial bins the `|v_r|` distribution is passed through a Gaussian kernel
density estimate with a bandwidth of 0.15 times the band rms speed and a mode
floor at one tenth of the peak; the same count on half-normal draws of the same
size and bandwidth supplies the single-stream null, and a bin counts as an excess
bin when it exceeds the 95th percentile of that null (128 replicates). Against
synthetic two- and three-stream populations the estimator resolves streams that
are at least about 0.5 rms speeds apart and carry at least a third of the band
mass, and merges closer ones; the null never produces a spurious mode at the
tracer counts used here. This is a mechanism diagnostic and is reported
separately from the frozen ridge statistic.

Cross-arm: for each arm the ridge list is matched greedily against the
reference arm's ridge list; a match is a ridge pair within `|Δu| ≤ 0.15`, each
ridge used once.

Verdict vocabulary: `SUPPORTS`, `DOES NOT EMERGE`, `INCONCLUSIVE` for the
general-structure claim, and a per-arm `SHELL_SUPPORTS` / `SHELL_DOES_NOT_EMERGE`
for the arm's own late profile.

## 5. Decision rules

- Structural failure in an arm (missing or truncated artifact, nonfinite value,
  ring or event overflow, mass closure error above `1e-4` relative, receipt that
  does not record the frozen configuration): that arm is `FAIL` and is excluded
  from the verdict.
- Fewer than six qualifying arms: overall `INCONCLUSIVE`.
- Per arm: at least two shell ridges: `SHELL_SUPPORTS`; otherwise
  `SHELL_DOES_NOT_EMERGE` (a valid negative result).
- Overall `SUPPORTS` the general layered structure when at least six of the
  eight arms show at least two shell ridges and at least four arms share at
  least two ridge positions with the reference arm.
- Overall `DOES NOT EMERGE` when at most four arms show at least two shell
  ridges.
- Overall `INCONCLUSIVE` when exactly five arms show at least two shell ridges,
  or when at least six arms have ridges but the sharing rule fails.
- The sphericity and concentration diagnostics are reported, not gated.
- Additional initial shapes may be added later under the same frozen
  configuration, statistic, and thresholds, before their receipts exist. No
  threshold, arm, horizon, seed, or initial-motion change is permitted after the
  first qualifying receipt. A runtime failure is repaired and the same arm rerun
  with the same frozen inputs.

### App-fidelity arms (registered before their receipts exist)

The live scene does not seed one cloud. `scenes/main.tscn` sets
`num_clusters = 3` and `cluster_separation = 1500` with the default ring
arrangement, so every shape the scene offers is generated as three same-sized
components with independent finite-sample realizations, placed on a ring of
radius 1500 at rest. Their common orientation is therefore seen from three
different directions relative to the ring centre, and the finite-sample and
tidal asymmetries split the infall phases. The sim then scales `box_scale` up so
the whole arrangement fits, which lands near 9.5 for the shapes below. The shape
control textures each component; it does not change the arrangement.
The scene also runs `dt = 0.05`,
refreshes its tree every 200 jobs (about 500 steps of frozen acceleration at the
measured 2.5 steps per job), and leaves the site field running.

The arms below reproduce that configuration inside the probe so the layer
question can be asked of the scene's own macro geometry instead of a single
cloud. They do not enter the primary verdict.

The app-fidelity set is a scene-control battery. It has no aggregate
general-structure decision rule; each arm is reported for its recorded
configuration, radial profile, and scope validity.

| Arm | Shape | Components | Separation | Box | Field | Steps | Stride |
|---|---|---|---|---|---|---|---|
| A3 | Spiral disc (3) | 3 (ring) | 1500 | 9.70 | frozen | 100,000 | 400 |
| A6 | Nested shells (6) | 3 (ring) | 1500 | 9.70 | frozen | 100,000 | 400 |
| C1 | Spiral disc (3) | 1 | 0 | 0.78 | frozen | 100,000 | 400 |
| C2 | Spiral disc (3) | 1 | 0 | 9.70 | frozen | 100,000 | 400 |
| L3 | Spiral disc (3) | 3 (ring) | 1500 | 9.70 | live | 100,000 | 400 |

All five run `dt = 0.05`, tree cadence 250 with two-step jobs (the scene's
roughly 500 steps between force refreshes), `cluster_radius = 120`,
`initial_radius_fraction = 1` (the scene's default, which fixes the geometry
fit), `initial_motion = At rest`, `field_attractor_init = true`,
`initial_total_mass = 2,320,000` (the scene's Salpeter mass sum at its default
particle count), 8192 particles, and 4096 tracers. `A3` and `A6` are the scene's
macroscopic initial condition for two different shapes; `C1` is a single blob at
the same physical size in a box that just contains it; `C2` is that same single
blob inside the scene's large box, which isolates the scene's softening ratio
(the tree softening is five percent of the box extent, so the scene softens each
blob at about two thirds of its radius); `L3` repeats `A3` with the site field
running, which is the closest reproduction of the live scene this harness
reaches. The remaining differences from the live scene are the particle count
(8192 against the scene's default 2.5 million, which makes the arms less
collisional and therefore less layered than the scene, not more), the fixed
window (the scene refits its window and box to the structure every two seconds,
which moves its softening during the collapse), and, for four of the five, field
liveness.

Each registered box value sits above the engine's own geometry fit for that
configuration, so the fit never enlarges it and the recorded `box_scale` equals
the registered value: the fit lands at about 9.5 for the ring with either shape
and at about 0.76 for the single blob at `cluster_radius = 120`. The four
large-box arms therefore share one box, which is what makes `A3` against `C2` a
comparison of component count alone and `C1` against `C2` a comparison of box
scale alone.

Projected priorities if the battery cannot run to completion in one pass:
`A3`, `C1`, `C2`, `A6`, `L3`.

`--tree-cadence`, `--clusters`, `--separation`, `--total-mass`, `--box-scale`,
`--cluster-radius`, `--radius-fraction`, and `--freeze-field` are probe options
that the primary arms do not pass; the primary receipts record no
`tree_cadence` key because they run the engine default of 1.

## 6. The live scene's own initial condition

The scene that shows the layered sphere does not seed one cloud, so the shape
control alone cannot change its macroscopic initial condition. `scenes/main.tscn`
sets `num_clusters = 3` and `cluster_separation = 1500`, and leaves the
arrangement at its default, which is the ring layout of component centers. In
`scripts/cassi_particle_initial_conditions.gd`, the ring layout places one center
per cluster on a circle of radius `cluster_separation`, the particle stream is
split evenly across those centers, and every shape's own radius is its
dimensionless shape factor times `cluster_radius`. The scene leaves
`cluster_radius` at the simulation default of 120 and `initial_motion` at
`At rest`, so the default nested-shell run starts as three same-sized
components with support about `1.24 × cluster_radius` (roughly 148 units), at
rest, on a ring of radius 1500. Other shapes use their own dimensionless
support factors; for the app-fidelity Spiral disc and Nested shells arms those
factors are about 1.08 and 1.24. Their independent finite-sample realizations
and placement in the shared potential break the symmetry: the three components
feed infall streams with distinct phases, and folds in those streams can appear
as three distinct caustic shells.
The shape control textures each component; it does not change how many there are
or where they are.

Two further scene defaults shape what follows. `initial_total_mass` is zero,
which leaves the per-particle Salpeter masses in place, so the default 2.5
million particles carry about 2.32 million mass units. And
`_fit_initial_condition_to_domain` raises `box_scale` from 5 to about 9.5 so the
ring fits inside the site window, which puts the box extent at about 1708 and
the tree softening, fixed at five percent of the extent, at about 85. That
softening is two thirds of a blob's radius, so the blobs are individually soft
and their mutual gravity dominates. The scene refreshes the per-particle tree
force every 200 jobs through `_tree_local_cadence`, which at the scene's
roughly 2.5 steps per job leaves each force estimate in place for about 500
steps.

The shapes differ, so the blobs differ in internal texture and in the number of
particles they hold at a given radius, and the observed recurrence of three
radial layers across shapes is consistent with a fixed three-blob macroscopic
initial condition rather than with a shape-driven attractor. The primary and
app-fidelity arms separate those two readings: the primary arms vary the shape
of a single cloud, and the app-fidelity arms vary the component count at the
scene's own geometry.

The display path is also fixed. The scene runs the sim in its default
`Particles` mode, so the observatory renders the particle positions directly as
billboards and the volume pass deposits the same particle buffer into its grid
(`source_mode` 0 of `scripts/cassi_observatory_volume.gd`); the inline field is
the volume source only in the sim's field mode. Two short accumulators sit on
the volume image: the sim's presentation volume history at weight 0.45, about
two frames of memory, and the observatory post's clamped temporal resolve at
weight 0.92, about twelve frames, which never includes the particle layer.
Both suppress per-frame sampling noise in the ray march. They can preserve a
short-lived trail of a moving band, but they cannot create a band at a radius
never occupied by particle samples. Persistent shells therefore require a
dynamical source in the particle trajectory; the display path can only smooth
or briefly trail it.

## 7. Calibrated scene follow-up (registered before execution)

The live scene sets `river_calibrate_gn = true`, while the app-fidelity probe
configuration above leaves that normalization at the engine default. At the
registered app mass and timestep, this omission sends particles into the
engine's open-world region, where radial profiles no longer describe the
configured scene box. The follow-up below adds the live calibration control as
a separate battery; it does not change the frozen primary or app-fidelity
arms.

All five arms use the app-fidelity values in §5 with
`river_calibrate_gn = true`, 8192 particles, 4096 tracers, `dt = 0.05`,
100,000 accepted steps, stride 400, batch size 2, tree cadence 250,
`cluster_radius = 120`, `initial_total_mass = 2,320,000`,
`initial_radius_fraction = 1`, and `field_attractor_init = true`. The output
root is `_diag/matter_formation/attractor_scene_calibrated/`.

| Arm | Shape | Components | Box | Field | Output |
|---|---|---:|---:|---|---|
| G3 | Spiral disc (3) | 3 | 9.70 | frozen | `G3` |
| G6 | Nested shells (6) | 3 | 9.70 | frozen | `G6` |
| GC1 | Spiral disc (3) | 1 | 0.78 | frozen | `GC1` |
| GC2 | Spiral disc (3) | 1 | 9.70 | frozen | `GC2` |
| GL3 | Spiral disc (3) | 3 | 9.70 | live | `GL3` |

The follow-up reports the same normalized radial ridge statistic and
phase-space stream diagnostic. It also reports the maximum live tracer radius
divided by the configured largest box half-extent. An arm is `BOUNDED` when
that ratio stays at or below 2 throughout the stored trajectory; an arm above
that limit is `OUT_OF_DOMAIN`, and its ridges are not used for a scene-fidelity
mechanism claim. This boundedness label is a numerical validity condition, not
an additional shell threshold.

The calibrated follow-up is a scene-fidelity diagnostic. It has no aggregate
mechanism decision rule; its summary uses `verdict = NOT_DEFINED` and reports
per-arm boundedness and shell fields. The primary six-of-eight criterion is
outside this follow-up's scope.


## 8. Evidence retention

Each arm writes `receipt.json`, `tracer_ids.bin`, `sample_steps.bin`,
`history_pos.bin`, `history_vel.bin`, `events.bin`, `initial_tracers.bin`, and
`final_tracers.bin` under its output directory, with the derived
`analysis.json` next to them, plus one `attractor_summary.json` holding the
per-arm measurements, the cross-arm matching, and the printed verdict. Raw
arrays are diagnostic artifacts; none of them is copied into a paper as
physical evidence without an independent analysis and an explicit scope
statement.

## 9. Results

### 9.1 Primary single-cloud battery

The eight single-cloud arms all pass the registered structural checks. Every
late-window mean profile has one ridge, so zero of eight arms meet the
two-ridge arm criterion and no ridge pair matches the nested-shell reference.
The frozen overall result is `DOES NOT EMERGE` (`qualifying_arms = 8`,
`arms_with_ridges = 0`, `matched_arms = 0`).

The epoch timeline shows short-lived profile complexity rather than a
persistent three-ridge state. The number of 8-sample epochs with at least two
ridges is 0/31 for IC2, 10/31 for IC3, 2/31 for IC5, 1/31 for IC7, 2/31 for
IC8, 1/31 for IC10, 1/31 for IC11, and 0/31 for IC6. The final radial
phase-space diagnostic has a median of one mode in every arm; its excess-bin
fraction ranges from 0 to 0.042. These measurements rule out a shape-general
single-cloud late attractor under the frozen statistic.

### 9.2 App-fidelity controls

All five app-fidelity receipts complete with the registered control inputs.
The calibration control is absent from these receipts: the live scene sets
`river_calibrate_gn = true`, while the probe invocation used the engine
default. Applying the extent diagnostic gives `OUT_OF_DOMAIN` for every arm:
the maximum-radius-to-box ratios are 3649.68 (A3), 3618.99 (A6), 28268.89
(C1), 4879.23 (C2), and 3287.15 (L3). The corresponding radial profiles
contain the raw `SHELL_SUPPORTS` labels for A3 and C2, but those labels are
outside the configured scene domain and carry no mechanism evidence. The
app-fidelity summary is therefore `NOT_DEFINED` as a mechanism verdict, with
five qualifying receipts and zero bounded arms.

### 9.3 Calibrated scene follow-up

The five calibrated receipts all complete with `river_calibrate_gn = true`
and 37 frozen configuration keys verified. Four arms are bounded: G3 and G6
have extent ratios 0.93, GC2 has 0.07, and GL3 has 0.93. GC1 is
`OUT_OF_DOMAIN` with a ratio of 107.42 even under the calibration control.
Each arm's late-window mean profile has one ridge; none of the four bounded
arms meets the two-ridge criterion. The follow-up summary is
`NOT_DEFINED` by registration, with `qualifying_arms = 5`, `bounded_arms = 4`,
`out_of_domain_arms = 1`, and `bounded_arms_with_ridges = 0`.

The final phase-space diagnostic does not provide a uniform three-stream
signature: G3 and G6 have one mode with zero excess fraction, GC2 has a
two-mode final diagnostic with excess fraction 0.408 and a one-mode
mid-window diagnostic with excess fraction 0.139, and GL3 has no eligible
stream slots because its radial-speed band is empty. These final-window
measurements do not sample the event-time fold that is visible in the live
scene.

The live scene observation is a three-component collapse: three blobs share an
asymmetric potential, their infall streams acquire distinct phases, and the
resulting folds appear as three caustic shells. This motivates a scene-specific
collapse hypothesis. The shell count is an event-time property of the
multi-component trajectory. The single-cloud battery does not reproduce it, and
the calibrated 8192-particle probe does not establish a persistent three-ridge
late radial profile. A quantitative event-time shell and component-phase
measurement remains for a separate probe.
