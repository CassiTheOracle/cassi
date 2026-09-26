# Native Cassi sphere: compactness and field-feedback experiment

Status: preregistered before GPU execution. This is a bounded native-dynamics experiment, not a solar model or a nuclear-physics test.

## Question and scope

Carina observes sun-like spheres in ordinary CassiCosmos; physical-matter mode is OFF because she reports approximately eight steps per second. This experiment asks whether the existing particle/site-field equations sustain a resolved, bounded spherical configuration and whether evolving field feedback changes its concentration or response to a disturbance relative to the same frozen initial field. A sphere is present in the initial condition: formation of spherical symmetry from arbitrary geometry is not an outcome.

No physical matter, supplied radiation, nuclear terms, black holes, merging, rotation-stress sector, radial heater, imposed helix or winding coupling is enabled. No production source, scene, user configuration or default is changed. The sole implementation is an isolated windowed local-RenderingDevice probe using the existing engine and shaders.

The machine-readable authority is `native_sphere_spec.json` in this directory. It fixes every arm and criterion. The campaign copies and hashes this preregistration, the spec, the runner, engine variants, source dependencies and imported shader/SPIR-V identities before execution. A harness repair may be made only to execute the registered inputs or restore accurate observation; attempts and errors remain in separate directories. Outcomes never select new parameters or stopping times.

## Operators and interpretation

Native site state is EY, EI and their scalar conjugate momenta. Define rho_field=EY+EI, epsilon=EY-phi*EI, and q=rho_field^2/(rho_field^2+phi^-2+epsilon^2). q is dimensionless coherence, not thermodynamic temperature, pressure, luminosity, or particle mass density. The field uses CSR graph-Laplacian kicks, +/-20*epsilon conversion, and the existing deposited-mass source. Setting source_strength=0 removes only the radial source; the native mass source remains active.

The tree gathers m_site=deposited_particle_mass+max(rho_field*site_volume,0) and weights this by 1+(phi^6-1)*q. Target forces also depend on the clamped local (EY-EI)/(EY+EI) chord ratio. Particle mass, deposited mass, positive field gravitating mass, and chord-weighted tree mass are separate observables. This source-driven model does not provide a demonstrated conserved thermodynamic or nuclear energy ledger. Particle kinetic energy and instantaneous force work are diagnostics, not a conserved total energy claim.

The local engine normally moves/rebuilds its site mesh; production global-RD stepping does not execute that local rebuild. All registered arms use fixed post-initialization site geometry. A source-checked probe-local engine variant changes only mesh_rebuild_due() to return false after the normal initial topology has been built. The ordinary field/force dispatches remain intact. freeze_field=true skips the field evolution/commit passes while mass deposition, derived field quantities and particle gravity continue. Frozen EY/EI/momenta must remain byte-identical; a nonzero evolving-field change must be measured before interpreting its comparison.

## Initial condition and common settings

- Code units only; no SI solar mapping.
- One uniformly sampled sphere with equal numerical particle masses; no net velocity, no imposed rotation or inward/outward flow. Position RNG seeds 20260915 and 20260916. Subtract sample COM and rescale to exact maximum radius R. Finite sampling is the initial asymmetry.
- Total particle mass 1000, 8192 particles, radii R=12,9,6 in one common cube with half-extents (15,15,15), origin fixed. Particle resolution arm uses 16384 particles at the same mass and seed.
- Native field initialization: deterministic independent uniform EY/EI draws in [-0.01,0.01], zero field momenta; preserve the engine's seeded initializer. No phase or spatial pattern is imposed.
- grid_N=64 (topology raster), native ML_N1=16 and 8192 sites, gravity G_N=1 without river calibration, tree softening length 0.75, tree theta=0.5, tree rebuilt/refreshed every accepted step. Requests are one step, avoiding the engine's eight-step tree-cache batching confound.
- dt=0.02, final code time 32, 1600 accepted steps. Half-step arms use dt=0.01 and 3200 steps. All snapshots occur at code-time multiples of 0.2, including 0 and 32, with an additional post-kick snapshot at time 16 in perturbed arms. Final-window statistics use 24<=t<=32.
- Physical matter/radiation, field-particle catalog, particle merging, black holes, source_strength, winding_coupling, all optional dissipative/rotation terms and adaptive field/COM switches are explicitly off. The site-native tree path is the force authority; frozen/evolving comparison does not substitute analytic Plummer gravity.

The smallest sphere has only about four characteristic site spacings per radius. Features near that scale or the 0.75 softening scale are unresolved. The particle force has open boundaries; the native field operator uses minimum-image edge displacement on its finite site graph. No isolated-continuum or solar-surface interpretation is inferred from this finite domain.

## Exact arms

1. Twelve primary runs: each of three radii x two seeds x evolving/frozen field.
2. Four disturbance runs: R=9, both seeds and both field modes; at t=16 add outward radial velocity 0.05*sqrt(phi^-3*1000/9), then subtract the kick's mass-weighted mean. Identical position state is retained; particle workbench commit plus query/mass/tree/cache invalidation occurs at the accepted boundary. The matching undisturbed primary arm is the control.
3. Two timestep checks: R=9, first seed, both field modes, dt halved, matched final time and sample times.
4. Two particle-resolution checks: R=9, first seed, both field modes, 16384 particles, unchanged total particle mass.
5. Two spatial checks: R=9, first seed, both modes, ML_N1=8 (1024 sites) compared to native16. To compare the same nominal continuum coefficients, the probe-local coarse variant multiplies its c2 by (8/16)^2 and its mass_scale by (8/16)^3; these retain native16 c2 and mass_scale rather than silently changing wave speed and source strength with site count. This is a coarse-to-native resolution check, not proof of asymptotic convergence. grid_N remains 64. A proposed ML_N1=32 arm is excluded before execution because its 512 MiB adjacency and >2 million x-axis clear workgroups exceed the ordinary dispatch shape; no unsafe run or new topology algorithm is introduced.
6. Two source/operator ablations: R=9, first seed, evolving field, respectively mass_scale=0 or omega2=0. Each changes only that one existing coefficient in a hashed probe-local source variant. All other primary parameters remain unchanged. These identify source-driven or conversion-dependent effects; no nuclear interpretation follows.
7. One exact-config repeat of first-seed R=9 evolving field, to measure nondeterministic execution variation.

Total: 25 runs. No arm is selected after seeing another's outcome.

## Raw observations and checks

Each accepted sample stores lossless little-endian GPU arrays, file SHA-256 and counts: particle position/mass, velocity, acceleration; tile-local site positions; EY/EI and momenta; q, epsilon, site volumes, deposited mass; current tree source records/weights. Static arrays may share content-addressed files. CSR offsets/neighbors and solved gradients/Laplacians are captured at least at initialization and final time. Tree-source timestamps are explicit: refresh observations at a fixed accepted boundary without advancing the field or particles. Geometry/topology status, operator sample counts, native clamp counters, active mode flags and execution counts are recorded. Missing/empty CSR, wrong site count, disabled evolution or inconsistent source/step identity cannot pass silently.

Independent Python analysis checks hashes, shapes, chronology, finite arrays, particle mass conservation, q/epsilon equations, positive site volumes, topology readiness, frozen-state exactness and matched initial particle/field bytes. It recomputes:

- COM-centered mass-weighted R10/R50/R90, fractions inside R and 2R, domain-exit fraction, shape tensor axis ratios and bulk COM drift;
- radial/tangential velocity moments, particle kinetic energy and angular momentum;
- twelve radial bins in r/R: particle mass per geometric shell volume, separately volume-weighted q/epsilon/rho_field and deposited site mass;
- positive field-source mass and chord-weighted source mass, without confusing either with conserved particle mass;
- realized phase increments atan2(EI,EY) with low-amplitude and alias-risk coverage. This is temporal phase motion, not topological winding or helix persistence;
- radial breathing amplitude and finite-sample angular-bin tangential-flow coherence/persistence. Attractive projections are not evidence of a strand.

## Frozen criteria and verdicts

Integrity: finite complete records, exact requested end time/steps, particle mass relative drift <=1e-6, q/epsilon absolute discrepancy <=2e-6 (relative tolerance 2e-5 for large epsilon), valid positive-volume topology, frozen EY/EI/pi exactness, and matching primary/control initial bytes. Invalid, incomplete or numerically unstable arms are INCONCLUSIVE.

Bounded resolved sphere: at every final-window sample >=95% of particle mass is within 2R, outside-domain mass <=2%, R90>=3*tree_softening, final-window max(R90)/min(R90)<=1.5, and shape c/a>=0.6. This is finite-window retention and shape, not a theorem of gravitational binding. Passing means SUPPORTS bounded resolved sphere in this fixture; otherwise CONTRADICTS that criterion within this window, unless integrity/resolution makes it INCONCLUSIVE.

Field contribution: compare median final-window (R50_evolving-R50_frozen)/R. A contribution is SUPPORTS only if both seeds give the same sign and absolute value >=0.05, and first-seed effect exceeds three times the exact-repeat effect. Repeat discrepancy >0.01R makes the attribution INCONCLUSIVE. Half-step, particle-count and coarse/native differences in median R50/R must each be <=0.10 before calling the effect resolution-robust. Failing these checks restricts it to a discretization-dependent observation. Otherwise no >=5% concentration effect is CONTRADICTS this thresholded hypothesis, not proof of zero influence.

Disturbance recovery: difference in final-window median R50 between perturbed and unperturbed arm <=0.05R and the perturbed arm meets bounded-sphere criteria. Record the immediate velocity change and its measured kinetic energy, and compare both field modes; recovery cannot pass on a kick that did not land.

Ablations, radial profiles, breathing, phase and angular-flow metrics are reported quantitatively; no additional discovery threshold, solar granulation, spontaneous helix, thermodynamic, nuclear or CMD-image claim is introduced after the fact. Phase alias risk or insufficient angular-bin occupancy makes the corresponding structure diagnostic unavailable rather than zero.

Stopping: fixed t=32 per arm. Safety stops are nonfinite authoritative state, max absolute EY/EI>1e6, max particle distance>1e6R, setup failure, invalid topology or 900 seconds wall time per arm. No early stopping on an appealing sphere; no extending a failed/negative arm. Failed attempts are retained and excluded from complete-arm verdicts. A source change during execution invalidates the affected source identity and requires a clearly separated, same-spec retry, not mixed receipts.

## Outputs

Campaign artifacts under `_diag/stellar_cells/native_sphere_<UTC stamp>/`; failed attempts remain there. Independent `analysis.json`, an execution/source manifest and a measured report in this directory link the raw receipts. The report includes exact active modes, all 25 dispositions, source/version and static-geometry qualifications, measured throughput, limitations and the narrow verdicts above.
