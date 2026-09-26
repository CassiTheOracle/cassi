# Native particle–field sphere experiment

**Status: measured.** All 25 registered arms completed and passed raw-state integrity checks. The native-discretization concentration effect is **SUPPORTS** at all three radii. The bounded-sphere hypothesis is **CONTRADICTS** in every arm, disturbance recovery is **CONTRADICTS** in all four disturbance arms, and the R=9 spatial-robustness requirement is not met.

## What the experiment establishes

With physical matter and radiation disabled, evolving the existing field changes the particle dynamics substantially: the core is more concentrated than with the same initial field held fixed, and its final half-mass radius is less displaced by the registered outward kick. These are measured finite-time particle–field effects, not a demonstrated stellar equilibrium. A concentrated core coexists with a spreading envelope. All 25 arms exceed the allowed mass fraction outside the finite field tile.

The experiment does not establish a star, nuclear burning, thermodynamic pressure support, luminosity, a solar surface, spontaneous spherical-symmetry formation, or a persistent helix. A sphere was supplied initially. The field-dependent concentration is not spatially robust under the registered coarse/native check, and the early collapsing cores reach scales close to the force softening.

- [Frozen design](native_sphere_prereg.md) and [machine-readable specification](native_sphere_spec.json).
- [Complete raw campaign and source manifest](../../_diag/native_sphere_20260915d/campaign.json).
- [Independent analysis](../../_diag/native_sphere_20260915d/analysis.json), [raw-geometry crosscheck](../../_diag/native_sphere_20260915d/independent_crosscheck.json), and [verifier firing evidence](../../_diag/native_sphere_20260915d/verifier_firing.json).

![Measured native-sphere primary trajectories](../../_diag/native_sphere_20260915d/native_spheres.png)

The figure plots the actual 12 primary trajectories. Shading marks the registered final window; the dotted line is the 2% field-domain exit limit. Seed 1 is 20260915 and seed 2 is 20260916. It is not an illustrative orbit or a particle-rendering screenshot. The generated PNG was visually inspected; its six panels and labels fit the canvas.

## Design and execution

The isolated windowed local-RenderingDevice harness uses the current real engine and shaders, not a CPU replacement or new PDE. Each cold sphere contains 8,192 equal-mass particles with total mass 1,000, zero initial velocity, no imposed spin, and initial radius R=12, 9, or 6. Positions use the registered deterministic sampler (implementation stream seed: seed + 0x504F5349), are centered on their sample COM, and are rescaled to maximum radius R. Native seeded EY/EI initialization supplies independent uniform draws in [-0.01,0.01], with zero field momenta.

Common settings are a fixed cube with half-extents 15, fixed center, grid_N=64 for topology rasterization, ML_N1=16 (2×16³=8,192 sites), G_N=1 without river calibration, softening 0.75, and tree theta 0.5. Every accepted step makes a one-step engine request with a refreshed tree; eight requests per UI iteration are not an eight-step cached-tree request. Physical matter, radiation, merging, black holes, catalog feedback, imposed radial source, winding, rotation-stress and optional dissipative sectors are off. The existing deposited-mass source remains on except in its explicit ablation.

Post-initialization mesh geometry is frozen separately within each arm. A checked probe-local engine variant suppresses subsequent local mesh rebuilds; the native field and force operators remain intact. Evolving and frozen arms retain the same particle/field initial bytes. Independent GPU mesh construction is not bit-identical between launches; its measured variability is retained below.

All arms run to code time 32. Ordinary dt=0.02 gives 1,600 steps; half-dt arms use 3,200 steps. Sampling is every 0.2 code-time units, with before/after kick observations at t=16. The final window 24≤t≤32 contains 41 observations per arm. The fixed mass and different radii change the initial density and collapse timescale; these are not dynamically rescaled copies sampled after an equal number of dynamical times.

The 25-arm allocation is 12 primary comparisons, four kicks, two half-timestep controls, two doubled-particle controls, two coarse-site controls, two coefficient ablations, and one exact-config repeat. The coarse ML_N1=8 arm has 1,024 sites; its c2 and mass_scale multipliers are 0.25 and 0.125 to preserve the native16 nominal coefficients. It is not equivalent to unmodified native8, and it is not an asymptotic-convergence test. ML_N1=32 was excluded before execution because its ordinary adjacency allocation and dispatch shape were unsafe; no such run was attempted.

**Executed:** 43,200 accepted steps and 4,029 raw snapshots; all 25 process exits were zero, no watchdog timed out, and every run retained its 97-item source closure. The sum of recorded arm runtimes is 965.745 seconds, or approximately 44.73 steps per recorded second across these mixed fixtures and their observation overhead. This is not a production-scene performance benchmark. Production engine sources, scenes, user settings and defaults were not changed.

## Concentration effect

The registered statistic is median over the final window of (R50_evolving − R50_frozen)/R, evaluated at matched times. It is a paired median, not necessarily the difference of the two separately reported medians. Negative values mean a more concentrated evolving-field core. Percentages below are fractions of the **initial radius R**, not percentage reductions relative to the frozen R50.

| Initial radius | Seed 1 | Seed 2 | Registered contribution verdict |
|---|---:|---:|---|
| 12 | -24.61% | -26.76% | SUPPORTS at the native discretization |
| 9 | -18.14% | -18.03% | SUPPORTS at the native discretization |
| 6 | -6.24% | -19.64% | SUPPORTS at the native discretization |

The exact-config R=9 evolving repeat gives a signed paired discrepancy of -0.4478% of R, with absolute noise estimate 0.4478%. This is below the 1% repeat ceiling. All three comparisons have the same effect sign across seeds, both effects exceed 5% of R, and the first-seed effects exceed three times the normalized repeat discrepancy. One repeat and two seeds provide the registered check, not a confidence interval or broad population claim.

### Discretization sensitivity

These rows compare final-window median R50 with the corresponding native R=9, first-seed control. The tolerance is an absolute difference ≤10% of R in every row before claiming resolution robustness.

| Control variation | Median R50 difference / R | Registered result |
|---|---:|---|
| `r9_dynamic_s20260915_dt_half` | -6.915% | Within 10% limit |
| `r9_dynamic_s20260915_particles_double` | -1.016% | Within 10% limit |
| `r9_dynamic_s20260915_sites_coarse` | -13.437% | FAILS 10% limit |
| `r9_frozen_s20260915_dt_half` | -0.308% | Within 10% limit |
| `r9_frozen_s20260915_particles_double` | 0.051% | Within 10% limit |
| `r9_frozen_s20260915_sites_coarse` | 2.328% | Within 10% limit |

Five of six checks are within the limit. The evolving coarse-site result differs by 13.437% of R and fails it. **The measured concentration effect must therefore remain a discretization-dependent observation.** Only R=9 has these controls; no resolution-robust claim is available for R=6 or R=12. Halving dt also changes evolving R50 by 6.915% of R, so passing that deliberately bounded check is not evidence of negligible timestep error. The initialization-acceleration difference described below further prevents interpreting it as an isolated truncation-error estimate.

## Containment, shape and all 25 dispositions

The frozen bounded-sphere criterion requires, at every final-window observation: at least 95% of particle mass inside 2R about the instantaneous COM; at most 2% outside the fixed field cube; R90≥3×0.75; max(R90)/min(R90)≤1.5 over the window; and shape-axis ratio c/a≥0.6. This is finite-window retention and shape, not a binding-energy theorem.

All 25 verdicts are **CONTRADICTS**. The domain condition fails in 25 arms, retention inside 2R in 19, and shape in one. The final-window R90/softening and breathing checks pass in all 25. Rows give separate final-window medians, minima and maxima; R90 ranges are in code units. Failure names refer to the conditions above.

| Arm | Median R50/R | Minimum inside 2R (%) | Maximum outside cube (%) | R90 min–max | Minimum c/a | Failed conditions |
|---|---:|---:|---:|---:|---:|---|
| `r12_dynamic_s20260915` | 0.511 | 89.93 | 12.40 | 17.616–24.171 | 0.798 | retained, domain |
| `r12_frozen_s20260915` | 0.757 | 98.06 | 3.63 | 11.678–11.764 | 0.837 | domain |
| `r9_dynamic_s20260915` | 0.593 | 89.69 | 9.14 | 14.569–18.427 | 0.792 | retained, domain |
| `r9_frozen_s20260915` | 0.774 | 95.08 | 4.82 | 9.100–10.931 | 0.914 | domain |
| `r6_dynamic_s20260915` | 0.740 | 87.81 | 5.04 | 11.658–13.403 | 0.695 | retained, domain |
| `r6_frozen_s20260915` | 0.806 | 87.92 | 8.31 | 11.528–15.009 | 0.734 | retained, domain |
| `r12_dynamic_s20260916` | 0.486 | 91.47 | 10.47 | 16.514–20.749 | 0.774 | retained, domain |
| `r12_frozen_s20260916` | 0.754 | 97.16 | 4.74 | 11.982–12.198 | 0.861 | domain |
| `r9_dynamic_s20260916` | 0.597 | 89.94 | 9.05 | 14.840–18.124 | 0.877 | retained, domain |
| `r9_frozen_s20260916` | 0.777 | 91.64 | 8.29 | 13.118–16.002 | 0.760 | retained, domain |
| `r6_dynamic_s20260916` | 0.707 | 89.18 | 4.25 | 10.830–12.478 | 0.561 | retained, domain, spherical |
| `r6_frozen_s20260916` | 0.910 | 78.26 | 14.42 | 18.827–25.485 | 0.672 | retained, domain |
| `r9_dynamic_s20260915_kick` | 0.601 | 89.56 | 9.20 | 14.961–18.414 | 0.805 | retained, domain |
| `r9_frozen_s20260915_kick` | 0.864 | 95.06 | 4.75 | 10.852–12.868 | 0.914 | domain |
| `r9_dynamic_s20260916_kick` | 0.589 | 90.19 | 9.06 | 14.890–17.803 | 0.884 | retained, domain |
| `r9_frozen_s20260916_kick` | 0.896 | 91.25 | 8.64 | 13.356–16.267 | 0.769 | retained, domain |
| `r9_dynamic_s20260915_dt_half` | 0.524 | 91.15 | 7.89 | 13.845–16.803 | 0.768 | retained, domain |
| `r9_dynamic_s20260915_particles_double` | 0.583 | 90.66 | 8.28 | 14.147–17.216 | 0.851 | retained, domain |
| `r9_dynamic_s20260915_sites_coarse` | 0.459 | 94.93 | 4.47 | 11.084–12.587 | 0.748 | retained, domain |
| `r9_frozen_s20260915_dt_half` | 0.771 | 95.35 | 4.70 | 8.989–10.425 | 0.917 | domain |
| `r9_frozen_s20260915_particles_double` | 0.775 | 95.24 | 4.87 | 8.991–10.543 | 0.895 | domain |
| `r9_frozen_s20260915_sites_coarse` | 0.798 | 85.45 | 14.48 | 21.433–26.638 | 0.618 | retained, domain |
| `r9_dynamic_s20260915_no_mass_source` | 1.290 | 61.65 | 36.08 | 43.099–59.256 | 0.913 | retained, domain |
| `r9_dynamic_s20260915_no_conversion` | 0.785 | 83.84 | 14.98 | 19.274–28.097 | 0.760 | retained, domain |
| `r9_dynamic_s20260915_repeat` | 0.594 | 89.65 | 9.23 | 14.824–18.430 | 0.794 | retained, domain |

All 25 per-arm summary.json and profiles.json files are retained alongside their receipt.json in the raw campaign. Profiles contain twelve radial shells with particle mass per geometric shell volume, separately volume-weighted field observables, and deposited site mass. A small R50 does not imply a contained outer envelope: the evolving primary arms have only about 87.8–91.5% inside 2R at their least-retained final-window sample.

The final-window R90 criterion does not resolve every earlier core. Across the six evolving primary arms, the minimum sampled R50 is 0.815–1.235 code units, only 1.09–1.65 softening lengths and below the characteristic 1.875 site spacing. The strong early collapse is therefore not evidence of a resolved continuum central object.

## Disturbance response

At t=16 the registered outward kick has nominal speed 0.2560750636, with its mass-weighted mean removed. All four kicks landed: positions were unchanged at the kick, and the measured velocity increments agree with the prescribed operation to maximum component error below 2.75×10^-7. The table reports the actual kinetic-energy change including its cross term with pre-existing velocity, not just the positive kick-only energy.

| Perturbed arm | Final median R50 difference / R | Measured kick RMS | Actual kinetic-energy change | Recovery verdict |
|---|---:|---:|---:|---|
| `r9_dynamic_s20260915_kick` | 0.813% | 0.255412 | 84.642 | CONTRADICTS |
| `r9_frozen_s20260915_kick` | 8.942% | 0.256048 | 22.161 | CONTRADICTS |
| `r9_dynamic_s20260916_kick` | -0.723% | 0.255058 | 93.527 | CONTRADICTS |
| `r9_frozen_s20260916_kick` | 11.879% | 0.255612 | 42.504 | CONTRADICTS |

The evolving-field half-mass radii end within approximately 0.81% and 0.72% of R of their unperturbed counterparts; frozen cases differ by 8.94% and 11.88%. This supports the descriptive statement that concentration is less displaced by this kick when the field evolves. It does **not** pass the registered recovery hypothesis: the evolving cases still fail containment, while the frozen cases additionally miss the 5% radius-recovery limit. No claim of whole-object healing or stable self-regulation follows.

## Source ledger and ablations

The native quantities are rho_field=EY+EI, epsilon=EY−phi×EI, and q=rho_field²/(rho_field²+phi^-2+epsilon²). q is not temperature and rho_field is not conserved particle mass density. A tree source has deposited particle mass + max(rho_field×site_volume,0), followed by chord weight 1+(phi^6−1)q. The target chord ratio is separately clamped by the existing force path. For a source coefficient C, the native deposited-mass forcing is C×m_site/V_site, so its volume-weighted sum is C×deposited_mass. The unweighted sum must not be called an extensive conserved source.

The following are R=9, seed-1 endpoints at t=32, except R50/R, which is the final-window median. Conserved particle mass remains exactly 1,000 in every row. The positive field and chord-weighted masses are not additional conserved particle mass or a nuclear-energy ledger.

| Arm | Median R50/R | Deposited particle mass | Positive field mass | Chord-weighted tree mass | Volume-weighted q | Particle kinetic energy |
|---|---:|---:|---:|---:|---:|---:|
| `r9_dynamic_s20260915` | 0.593 | 947.88 | 3038.58 | 6252.84 | 0.032185 | 10502.28 |
| `r9_frozen_s20260915` | 0.774 | 953.25 | 90.32 | 1046.80 | 0.000176 | 870.63 |
| `r9_dynamic_s20260915_no_mass_source` | 1.290 | 639.16 | 59.28 | 699.53 | 0.000083 | 3076.63 |
| `r9_dynamic_s20260915_no_conversion` | 0.785 | 904.54 | 2913.41 | 5807.72 | 0.029659 | 8722.95 |

Removing the existing mass source increases median R50 by 69.762% of initial R relative to the evolving baseline. Removing conversion increases it by 19.258%. The baseline positive field-source mass grows from 90.318 to 3,038.581, while the mass-source-off endpoint has only 59.275. These comparisons establish sensitivity to the existing source and conversion operators in this fixture; they do not establish nuclear reactions or a conserved thermodynamic energy supply. Conversion changes the dynamics even though its removal leaves substantial positive field-source mass.

Deposited mass decreases when particles leave the finite field tile; the particles themselves remain in the arrays with conserved total mass. The force path has open particle boundaries, while the native field graph uses its finite-domain/minimum-image operator. This is a material interpretation limit, not evidence that numerical particle mass vanished. The misleading engine snapshot name pot was not treated as gravitational potential; this probe does not use it to invent total or binding energy.

## Phase, angular flow and guards

Phase is atan2(EI,EY), with the registered amplitude floor 0.001 and adjacent-increment alias-risk threshold pi/2. Its principal increments are not a topological winding number. Representative first-seed R=9 diagnostics are:

| Arm | Eligible temporal site pairs | Alias-risk pairs | Continuous nonaliased sites | Mean adjacent angular-bin direction cosine | Final angular-bin coherence |
|---|---:|---:|---:|---:|---:|
| `r9_dynamic_s20260915` | 1,290,708 | 93,859 (7.27%) | 1/8192 | 0.634 | 0.107 |
| `r9_frozen_s20260915` | 1,302,240 | 0 (0.00%) | 8139/8192 | 0.436 | 0.239 |
| `r9_dynamic_s20260915_no_mass_source` | 1,235,812 | 371,242 (30.04%) | 0/8192 | 0.677 | 0.123 |
| `r9_dynamic_s20260915_no_conversion` | 1,290,314 | 30,520 (2.37%) | 64/8192 | 0.737 | 0.124 |

Each listed angular-flow comparison has 7,632 valid adjacent bin pairs. The bins are the registered 48 azimuthal bins, each requiring at least 16 particles; these diagnostic directional correlations are not a strand detector. The all-site unwrapped phase aggregate is unavailable in every listed case because amplitude coverage or alias requirements fail, including the frozen case's low-amplitude sites. Frozen authoritative fields are nevertheless exactly unchanged. No helix, winding or solar-granulation verdict is inferred.

Native telemetry is sampled at the last accepted step before observation refresh, not integrated over every accepted step. Across 4,025 distinct arm/time records (four duplicate kick-boundary records excluded), field_pi_sat_hi and field_pi_sat_lo are zero. In contrast, field_rho_guard_hits is nonzero in 2,989 records (maximum 15,467), and rho_guard_hits in 2,780 (maximum 9,954). Sampled pi_sat_hi_frac and pi_sat_lo_frac are nonzero in 3,218 and 3,767 records, reaching 0.48755 and 0.74121. These distinct native counters are not interchangeable, counts can cover multiple dispatches, and **the trajectory is not guard/clamp-free**. Sampled zeros do not establish absence of events between observations.

## Integrity and non-vacuity evidence

The independent analyzer verified stored and decoded hashes, dtypes/shapes, finite authoritative arrays, runtime mode flags, chronology and accepted-step source identity, fixed within-arm geometry/volumes, positive cell volumes, CSR structure, and the field/source equations. It also reversed each declared probe-local source substitution and recovered the canonical engine text exactly.

- 56,706 blob declarations checked; 37,979 unique blobs hashed within their respective arms (not a global cross-arm deduplication claim).
- 50 endpoint CSR checks, with zero empty rows. Topology is initialized before t=0 and remains fixed within each accepted arm.
- 30,697,472 site-snapshot comparisons **per equation channel** for q, epsilon, source mass and source weight; zero tolerance violations. Maximum q error is 1.365×10^-8 and epsilon error 2.716×10^-9. Maximum source-coordinate discrepancy is 4.769×10^-7; source mass/weight checks use float32-scaled arithmetic tolerances.
- Particle mass relative drift is zero in the stored float32 particle-mass arrays. All 25 particle and deposition paths changed; all 14 evolving arms changed all four authoritative field roles; all 11 frozen arms preserved authoritative and derived field bytes exactly.
- A separate raw-array script, which does not import the analyzer, measured 9,068,544 particle records across all 1,025 final-window frames. Its 9,419 numerical comparisons had zero mismatches; maximum R90 difference was 7.11×10^-15. It independently checked quantile radii using partition rather than the analyzer's weighted sorting, shape using singular values rather than covariance eigenvalues, retention, the bounded verdicts, and the paired concentration/control statistics.
- A deliberately corrupted compressed copy was rejected by SHA/size validation. A single real q entry was then increased by 0.02, consistently recompressed and re-hashed in a scratch copy: the complete arm analyzer returned INCONCLUSIVE with exactly one q violation at step 0, over 1,318,912 attempted site comparisons. Original raw artifacts were unchanged and scratch copies were removed. The firing receipt binds the final analyzer source hash.

### Independent-launch initialization variability

[The initial-pair audit](../../_diag/native_sphere_20260915d/initial_pair_audit.json) records 120 exact required hash comparisons across 15 same-size pairs: initial particle positions/masses, velocities, EY/EI, both field momenta, q and epsilon all match. GPU-built site coordinates and derived acceleration need not be bit-identical between independent launches, and site volumes sometimes differ by one raster voxel exchanged between two cells.

Across those pairs the maximum site-coordinate change is 2.861×10^-5 code units; differing volumes change by 0.1029968262, with positive volumes and unchanged total domain volume. Most paired initial acceleration differences are small, but the evolving half-dt arm has 203 particles with a component difference above 10^-3, and a maximum difference of 2.5344374. Its cause is not established here. That control is not a perfectly isolated timestep-error measurement. The exact-config repeat measures a combined initialization/execution discrepancy, not a separate proof that mesh variability is negligible in every arm.

The initial analyzer incorrectly imposed cross-launch byte identity on acceleration and geometry as well as the preregistered particle/field state. It stopped before issuing campaign conclusions. That extra, unregistered requirement was removed; all differing identities remain in the analysis and audit, and within-arm geometry constancy remains mandatory. The final analysis and firing checks were rerun. No simulation data, physics inputs, thresholds or run stopping rules were changed in response to the scientific outcomes.

### Excluded setup attempts

Three separately retained setup campaigns are excluded from all scientific statistics; their failures were not accepted as stable spheres:

| Directory suffix | Completed run records | Counterexample | Disposition |
|---|---:|---|---|
| [a](../../_diag/native_sphere_20260915a/invalidation.json) | 8 | Initial local topology remap collapsed independent fields to one value; first-seed frozen particles were byte-static with zero kinetic energy. | EXCLUDED_INITIALIZATION_FAILURE |
| [b](../../_diag/native_sphere_20260915b/invalidation.json) | 19 | Site 578 had zero volume and no CSR neighbors. | EXCLUDED_TOPOLOGY_INITIALIZATION_FAILURE |
| [c](../../_diag/native_sphere_20260915c/invalidation.json) | 2 | Tree world-source positions were stale relative to current tile sites; maximum mismatch 2.1586819. | EXCLUDED_INITIAL_SOURCE_GEOMETRY_FAILURE |

The isolated harness now defers initial boxless rebuilding until the native scatter/JFA labels are established, invokes the native topology rebuild, restores the unchanged native seeded field initializer after remapping, and publishes current tile sites into the existing world-source buffer using the production coordinate transform. These operations occur before t=0; accepted dynamics use boxless_field=true. Initial topology generation is 2, not a claim that only one setup rebuild occurred. No production source was repaired or changed. Failed raw receipts and logs remain preserved; the two then-active a/b attempts were stopped as setup failures, not on appealing physical outcomes.

## Reproduction and artifact identity

Run from CassiCosmos. The launcher uses one windowed GPU runtime at a time; do not overlap it with another simulation or stop the user's editor. A new physics campaign must use a new output directory. The accepted data live under _diag/native_sphere_20260915d; this concrete location supersedes only the illustrative output-path template in the preregistration, not any scientific input.

```text
python tools/run_native_sphere.py --out _diag/native_sphere_NEW
python research/stellar_cells/native_sphere_analyze.py _diag/native_sphere_20260915d
python _diag/native_sphere_20260915d/raw_geometry_crosscheck.py _diag/native_sphere_20260915d
python research/stellar_cells/native_sphere_plot.py _diag/native_sphere_20260915d
```

The reusable code is [probe_native_sphere.gd](../../scripts/probe_native_sphere.gd), [the isolated scene](../../scenes/probe_native_sphere.tscn), [run_native_sphere.py](../../tools/run_native_sphere.py), [native_sphere_analyze.py](native_sphere_analyze.py), and [native_sphere_plot.py](native_sphere_plot.py). Source variants, executed commands, per-arm receipts, source hashes and lossless arrays are retained in the campaign. The raw crosscheck script is retained with its receipt in that campaign rather than added as a project test suite.

| Artifact | SHA-256 |
|---|---|
| Registered preregistration | `334ccb2feee3914ad37ebe1f883ec41e930baa640707304a18267276cd5040fd` |
| Registered source specification | `dba85f2e5d95c85d2b3ae5aa3eb2e4e74747af0c7d6ab332ade0ecc1439836ae` |
| Canonical engine | `f85f8659ac17d5f137f250c0a5bb0a27aee16928f8341f75be3cf6c39bb09dba` |
| Probe | `479dedf6326bd80c32ac9c042eec84bc33545316a0ef14d3c18a39a943e36528` |
| Launcher | `f93a3325f05b723b77e96c931a3af6adf8a28697f73470eecc5b7c3d8c1d556e` |
| Campaign manifest | `ee0efbf296e6d7791c11ea3f8907355da381110c0de8a270ed93f4e2d3e2b881` |
| Final analyzer | `b43549517a196692c6a18ecc6dabe4a09ed3208ec02c42b413c5c7bf5891e63b` |
| Analysis JSON | `bd415420078368393d6d9a0fcc51d1bdd60e77cde45b77bc8d09b331994eb9fa` |
| Independent raw crosscheck script | `4840adef2ed1195bfeb01b966cbdbed47f712a69d0dc76dc65205f322ba1ca5f` |
| Figure | `1f0642e37ef95a5c284807498ad73e7f5fe1efbccd27bf9a56b7402bb56416eb` |

All conclusions above are bounded by the registered code-unit fixture and t=32 window. The next discriminating investigation would separate finite-domain containment from core concentration while preserving spatial resolution, then establish a safe finer spatial check. These measurements provide no basis to add a nuclear interpretation to the existing visual spheres.
