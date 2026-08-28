# Site-native field and force path — current report

Date: 2026-08-19
Pre-reg: `research/meshless/gridless_physics_prereg.md`
Design: `research/meshless/boxless_field_design.md`

## 1. Production contract

The shipped decoupled scenes use `gridless_physics = true`. The authoritative physics state is a moving set of `2 × ML_N1³` Voronoi sites, not an `N³` raster:

- site positions in tile coordinates plus a world-space mirror;
- dual field amplitudes `psi_y`, `psi_i` and momenta `pi_y`, `pi_i`;
- site volume, aggregate site mass, CSR offsets/neighbors;
- site gradients, graph Laplacians, coherence `q`, and defect `epsilon`;
- the site telemetry buffer and topology generation/status.

The first `n_sites` entries of each field/momentum buffer are authoritative. A packed second half is the race-free next-state buffer. The graph field dispatch writes only that second half; a subsequent commit dispatch copies it into the authoritative half. This keeps every CSR row on one time slice without introducing a grid resource or a descriptor expansion.

`cassi_meshless_topology_worker.gd` still uses a bounded JFA/hash accelerator to build site geometry and CSR adjacency. That grid is a topology accelerator only: it is not the field state, source density, force carrier, condensation state, or telemetry source.

## 2. Physics chain

Each site-native step is ordered on one compute list with barriers:

1. fixed-point particle-to-site mass deposition through the published spatial hash;
2. site-field reset, CSR graph evolution, packed next-state commit, and derived `grad/lap/q/epsilon` recomputation;
3. deterministic three-pass site condensation when enabled (candidate clear, atomic mass selection, slot-owner finalization);
4. site BH integration against the same site state;
5. site n-body warmup/KDK force using site lookup, tree gradients, and site mass;
6. existing particle tree momentum/reduction passes.

The tree build binds the world-space site mirror and site mass. Its adaptive root is computed in the same world coordinate system, including the home-window translation. Field mass forcing uses site aggregate mass with site-volume normalization and the existing per-mass coupling; no raster cell volume or raster field read is required.

Gridless setup rejects `cascade_level=true` rather than accepting a silent no-op. Gridless setup also fails closed if decoupled startup/reinitialization cannot create the site engine; it never re-enters the inline raster chain.

## 3. Mass, condensation, and BH details

Particle mass is accumulated with four base-2^8 fixed-point digit columns per site. Atomic digit additions are carry-safe for dense site occupancy; conversion to float occurs in a separate pass. The site mass buffer therefore cannot wrap at the one-uint 65,536-unit boundary.

Condensation uses a selection/finalization split. A transient candidate key is selected atomically per modulo-15 slot, then one slot owner scans the site list after a dispatch barrier, applies a lowest-site-index tie break, and publishes the paired world position/mass record. Existing live BH records remain when no qualifying current site exists.

BH header refresh writes only the 64-byte header. Live BH records are not overwritten by per-frame host initialization, so site condensation, BH integration, and accretion persist across frames.

## 4. Consumers migrated

The gridless branches now serve:

- field evolution and derived gradients/coherence;
- particle mass deposition and source forcing;
- tree and analytic/heuristic site gravity;
- condensation and BH integration;
- force and field telemetry, with separate field guard/cap slots;
- `read_com`, snapshots, and telemetry readback;
- `cassi_synth.gd` site meter;
- `cassi_survey.gd` site payload export;
- the SimUI falsification meter, using volume-weighted site fields;
- render query, q-histogram, instancing, and site-volume topology consumers.

The meshless UI toggle is locked on for gridless scenes. Level swapping is rejected for gridless scenes because its file format is raster-specific.

## 5. Compatibility boundary

Raster buffers and legacy branches remain allocated/available for explicit compatibility and verification scenes. They are not initialized as field state by gridless engine setup and are not read by the production site-native step chain. The legacy inline solver, raster diagnostics, raster field workbench, and `cassi_mind_engine.gd` remain separate compatibility/sidecar programs with their existing grid contracts; none is selected by the shipped site-native main scenes.

The render-topology worker continues to use its bounded geometry accelerator. Removing that accelerator would be a separate renderer-topology change, not a physics-state migration.

## 6. Verification contract

The focused `verify_gridless_physics.tscn` gate passed on the RX 7900 XTX after the final site readback-count fix (`gridless-site-gate-v14`, exit 0). Its fixed-seed receipt included topology `[1, 105614, 0, 8192]`, aggregate site mass `2351.526261` matching the particle mass sum `2351.526254`, nonzero acceleration, snapshot generation `1`, and a condensed BH slot mass `0.935136`.

The gate checks, from live buffers:

- topology generation/status and site count;
- finite bounded `q` and positive site volumes;
- nonzero aggregate site mass after carry-safe hash deposition;
- nonzero particle acceleration;
- positive finite site-condensed BH mass;
- snapshot generation and volume-weighted telemetry.

The normal Godot battery remains the regression contract for compatibility scenes. The focused site gate and the full battery must both be run after shader/engine changes; a green legacy battery alone does not establish site-native physics. The final 33-arm run included `verify_gridless_physics` at arm 7 and passed every site-native and survey arm (`32/33` overall); the sole failure was the nondeterministic `verify_gravity_modes` timing-only cost check (`57/58` functional checks), while a standalone rerun of that arm exited 0.
