# Physical radiation: thermal state, material closures and spectral observation

## Status: P0/P1 and bounded supplied-material engine implemented; native coupling staged

Scientific, Observatory and Cinematic remain the supported production appearances, with Observatory's simulation-unit optics documented in [the Observatory design](observatory_design.md). The P0/P1 spectral path now observes an explicitly prescribed material snapshot without changing solver state. A separate default-off `CassiRadiationEngine` owns a bounded homogeneous-affine material/radiation control state and advances only on accepted physics steps.

The coupled control establishes the state, lifecycle and numerical seams needed by later physical providers, but it is not a native Cosmos material identification or an Observatory coupled source. The user-visible physical mode remains unavailable until a qualified native material adapter, conservative spatial transport and the corresponding source publication exist. Production defaults are unchanged.

## 1. Decisions

1. **Keep physics and observation separate.** Only the physics engine may change thermal energy, material populations or radiation energy/momentum. A camera pass cannot cool a cell. Hiding the interface, changing appearance, recording a still, or reducing optical quality cannot change physical evolution.
2. **Ship a complete one-way preview before enabling feedback.** It uses explicitly prescribed material data or qualified reference snapshots. It may display standard radiation physics under supplied assumptions, but does not claim that the native solver generated its temperature or spectrum.
3. **Store energy; obtain temperature from the material law.** A conservative thermal state contains internal energy and a material identity. Temperature is an equation-of-state result with declared units, not a renamed coherence, mass, velocity or heat-ledger channel.
4. **Use frequency groups at the physics boundary.** This matches the emerging Theory radiation specification. Band count and boundaries are data, not three hard-coded RGB channels. Frequency-integrated quantities, monochromatic densities and display RGB are distinct types in the specification.
5. **Make material physics replaceable at one explicit interface.** Start with one local closure implementation and its data bundle. Do not build a general plugin marketplace, remote service, expression interpreter or per-cell GDScript callback system.
6. **Keep the radiation transport method distinct from the material closure.** Changing opacity or emission laws should not require changing the camera. Changing angular transport, polarization or moving-medium assumptions may require a new solver capability and state version.
7. **Use canonical geometry and generation identities.** The optical reconstruction is disposable. It cannot become the authoritative material mesh because its resolution, bounds and cadence are camera/quality dependent.
8. **Reject unsupported claims and states explicitly.** Missing calibration, incompatible topology, an unsupported species model or a missing radiation component disables the requested physical mode with a reason. There is no silent fallback to warm RGB while continuing to label the output physical.

## 2. Current implementation and theory boundaries

### 2.1 Repository integration map

| Existing surface | Observed role | Upgrade boundary |
|---|---|---|
| `scripts/cassi_physics_engine.gd` | Authoritative standalone/site-native engine; production shares the renderer-owned RD; the local-RD path hosts the optional supplied-material `CassiRadiationEngine` | Retain accepted-step/fence ownership while adding a separately qualified native material adapter and spatial transport |
| `scripts/cassi_sim.gd` | Composition root, render mirrors, configuration and engine integration | Route model configuration and read-only publications; do not put a second thermal solver in `_process` |
| `scripts/cassi_observatory.gd` | Appearance controller, source selection, frame preparation and settings | Select an observation source; retain existing style values 0/1/2 and public appearance methods |
| `scripts/cassi_observatory_volume.gd` | Renderer-owned reconstruction and camera-volume work | Retain legacy optics; consume spectral coefficients/snapshots through a separate spectral backend |
| `scripts/cassi_observatory_post.gd` | Shared HDR composition, exposure, temporal processing and bloom | Accept an explicitly tagged complete spectral-camera result without reapplying legacy foreground/background emission |
| `compute/cassi_observatory_density_reconstruct.glsl` | Particle mass per optical cell volume, or a source-dependent optical site/grid reconstruction | These channels are not calibrated material density, temperature or frequency-dependent opacity |
| `compute/cassi_observatory_volume.glsl` | RGB sources and scalar extinction; cumulative scalar camera-depth tau | Do not reinterpret its `rgba32f` density or `r32f` tau as spectral state |
| `shaders/particle_billboard_observatory.gdshader` | Prescribed point colour, mass-based flux allocation and scalar depth attenuation | Retain for legacy optics; do not give physical emitters this colour or extinction by default |
| `scripts/sim_ui.gd` | Existing Visuals/Appearance and camera/capture controls | Reuse the PARAMS/component conventions and manual-first camera ownership |
| `scripts/cassi_presentation_capture.gd`, `scripts/main_recorder.gd`, `record.ps1` | PNG/sequence/Movie Maker capture | Add matched model/source/camera provenance and optional linear scientific output |

The production path is site-native, uses a finite moving window, and does not wrap escaped particles to the opposite wall. The canonical engine mesh, the optical cache and the camera-depth grid are three different discretizations. Current publication and reinitialization code must be followed rather than inferred from an old decoupled-worker design. [Production and capture overview](../../TECHNICAL_GUIDE.md).

`CassiObservatory._prepare_frame` increments its `source_epoch` while playing, even if no new physics step was executed. That render invalidation counter is not a physical-step identity. The bounded coupled engine instead publishes its own accepted-step, physical-time, state/reset epoch and immutable model/unit/group identities. Observatory does not consume that publication as a coupled source while the native prerequisites remain unavailable.

The code audit identifies concrete prerequisites for the material adapter:

- `CassiSim._decoupled_start_engine` supplies `rd_global=true`, `owns_rd=false`. `CassiPhysicsEngine.finish_setup`, `record_pending_steps` and `CassiSim._decoupled_poll_and_render` are the production setup/recording boundaries; `run_steps` is a local-RD standalone path. A worker-local device must not be introduced into production by following a stale comment.
- `CassiPhysicsEngine._init_site_volumes_direct` fills `_ml_vol` with uniform box-volume/site-count weights. These are not measured Voronoi or material volumes. P2 must qualify their physical interpretation or supply an engine-owned material discretization with a conservative mapping to the canonical state. A finite-volume radiation solver additionally needs consistent shared-face flux geometry, not just a neighbor list.
- `publish_render_query`, `service_render_topology` and `_apply_render_topology` have separate query/topology generations. Despite its name, the topology worker supplies CSR connectivity consumed by `cassi_site_physics.glsl`; its readiness/overflow/generation checks are relevant to physical updates. Repositioning sites with the window is not already a conservative thermal/radiation remap.
- `_rotation_dispatches` owns the existing rotation exchange step. Its rotation-grid cells are a different indexing/geometry domain from the canonical sites and optical cache. A heat transfer between these domains needs conservative weights and a step identity, never coincident array indices.
- The gridless `readback_snapshot` result currently includes site fields/volumes, `t` and topology generation, but no executed-step count or complete rotation/thermal state. The Field Particles branch has a different schema. Neither a generic snapshot name nor a rendered frame proves full checkpoint coverage.

### 2.2 What the Theory work supplies

The [thermal feasibility model, section 7](../../../CassiTheory/turbulence/cassi-fluid-feasibility.md#7-selected-reacting-capillary-and-thermal-fluid) is a separate, constant-density incompressible reacting-capillary model with state `(u,c,T)`. Its [fixed thermal specification](../../../CassiTheory/computations/cassi-fluid-thermodynamics-prereg.md) supplies rotational velocity, entropy, viscosity, conductivity, number-density normalization and irreversible constitutive choices. Its successful energy/entropy checks qualify those selected equations. They do not establish a native Cosmos temperature, Kelvin calibration, compressible material law or optical spectrum.

The completed [radiative-material closure](../../../CassiTheory/turbulence/cassi-radiative-material-closure.md) is the equation source for this upgrade: conditional Planck/Kirchhoff emission, absorption and scattering, frequency-group moments, M1 closure, paired four-momentum exchange, entropy identities, slab transfer and an implicit thermal source solve. Its [comprehensive specification](../../../CassiTheory/computations/cassi-radiative-material-prereg.md) and [source-subcycling qualification](../../../CassiTheory/computations/cassi-radiative-material-qualification-prereg.md) define the numerical evidence to import.

The paper records 33/34 passing comprehensive checks, retaining a **FAIL** for the backward-Euler accuracy target at benchmark `dt=0.01`. The separate source-subcycling qualification passes 9/9 at the refined schedule; `dt=0.001` meets the original benchmark accuracy target. These are different receipts, not an all-green comprehensive run or a universal safe timestep. The radiative derivation is available; the implementation must preserve its source-accuracy and physical-scope qualifications.

The remaining scientific inputs are explicit in the paper's sections 12 and 17: a physical material/unit map, EOS or heat capacity, opacity and any species/ionization/line data. A controlled constant-density material can use supplied heat capacity and direct per-length coefficients without deriving a mass-opacity map first. Native Cosmos coupling, compressible material dynamics, conservative spatial radiation transport, the general velocity-gradient/aberration P4c regime, stellar source energetics and physical unresolved emitters still need their respective implementation and qualification.

Conditional gauge/Maxwell compatibility is possible future coupling context. It does not identify the live density fields with a radiating electromagnetic material. No stage below requires pretending that this identification has already been derived.

### 2.3 Coherence notation

The raw `FieldQ` buffer stores `EY*EY + EI*EI`. The native bounded gate mirrored in `compute/cassi_nbody_gravity.glsl` and `compute/cassi_instancer.glsl` is

$$
q_{\rm live}=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2},
\qquad \rho=E_Y+E_I,\qquad \varepsilon=E_Y-\varphi E_I.
$$

For $\rho>0$, defining $c=E_Y/\rho$ and $c_*=\varphi/(1+\varphi)$ gives the exact algebraic relation

$$
\varepsilon=\rho(1+\varphi)(c-c_*),
\qquad
q_{\rm live}=
\frac{\rho^2}
{\rho^2+\varphi^{-2}+\rho^2(1+\varphi)^2(c-c_*)^2}.
$$

The selected thermal specification instead fixes the reference-normalized total density $\rho_{\rm ref}$ and defines

$$
\varepsilon_{\rm th}=\rho_{\rm ref}(1+\varphi)(c-c_*),
\qquad
q_{\rm th}=
\frac{\rho_{\rm ref}^2}
{\rho_{\rm ref}^2+\varphi^{-2}+\varepsilon_{\rm th}^2}.
$$

Its dimensional statement restores the reference-density term as $\varphi^{-2}\rho_*^2$. Consequently, equality between $q_{\rm live}$ and $q_{\rm th}$ requires an adapter to establish $\rho=\rho_{\rm ref}$ and a common nondimensional/reference-density convention. The live variable-density fields do not establish those conditions, so only the $\varepsilon$ substitution is presently derived. Treat it as an initialization or diagnostic candidate, not a native thermal-gate identity. It does not determine thermal energy, chemical abundances, temperature or emissivity. Domain checks also matter: the thermal model requires positive temperature and $0<c<1$; signed renderer inputs must not be forced into that domain by absolute values or clipping.

The existing Observatory cache's A channel also is source-dependent: `cassi_voronoi_optical_payload.glsl` supplies bounded coherence for the site route, whereas `cassi_observatory_density_inline.glsl` deposits a clamped field-amplitude quantity for its inline route. Do not infer a universal material quantity from that channel. The new material snapshot supplies its own explicit source kind, meanings and validity rules.

The optional rotation heat ledger also is not a temperature. `scripts/cassi_sim.gd` explicitly documents its absent thermal/pressure return path. A future thermal adapter must consume a qualified energy-transfer increment exactly once, with units and a matching source debit, rather than repeatedly treating an accumulated ledger as newly generated heat.

`compute/cassi_rotation_stress.glsl`, `solve_exchange`, accumulates `spin_heat[id].w += heat`; `apply_exchange` applies the paired matter impulse. If a qualified adapter transfers that heat into material internal energy, the cumulative diagnostic may remain, but it is not added a second time to the physical energy total. Spatial mapping, reset/replay identity and the realized mechanical work must all be included in qualification.

Do not drive same-step heating from CPU `telemetry[1]` or `_rotation_snapshot`: production readback is deliberately throttled through `mirror_publish_cadence` (default 8). The coupled path needs a GPU-local accepted-step transfer/publication, or an explicitly lagged exchange with its own qualification. A delayed aggregate cannot reconstruct missing spatial or intervening-step energy transfers.

### 2.4 What completion means

| Target | Now supplied by Theory | Remaining work |
|---|---|---|
| Controlled radiative capillary fluid | Conditional constant-density thermal model and the completed LTE/M1 radiative closure | Choose explicit units, heat capacity, per-length material coefficients and initial/boundary states; implement and qualify the GPU evolution |
| Radiation coupled to the current native world | Radiation source and transport equations at their stated scope | Establish the native material/energy/volume map, persistent thermal/radiation state, accepted-step transactions, conservative geometry changes and full integration checks |
| Realistic compressible gas, nebulae or stars | The closure identifies the needed EOS, population and luminosity interfaces | Add mass continuity, compressible pressure/work, EOS/internal energy, applicable ionization/level populations and opacity data; give sustained emitters a physical energy source |
| Material predictions derived entirely from Cassi | Conditional thermal/radiative identities and possible gauge-sector context | Derive the physical material, charge/current, opacity and species correspondence; external tables remain valid supplied inputs for a conditional simulation |

No further fundamental radiation derivation is required to start a complete implementation of the selected conditional material. Supplied material data is an explicit model choice. It does not make the native world or an arbitrary astrophysical regime complete automatically.

## 3. User-facing modes and ownership

Keep **appearance**, **observation source** and **physical dynamics** independent.

| Selection | Data source | May mutate the engine? | Required label |
|---|---|---|---|
| Existing Scientific / simulation-unit optics | Existing live state and palettes | No | Scientific quantities / simulation-unit optics |
| Prescribed spectral preview | A declared material profile or replayed reference snapshot, optionally placed on a frozen/live geometry snapshot | No | Prescribed material; one-way spectral preview |
| Observation of coupled radiation | A complete, qualified engine publication | Observation: no; separately enabled physical solver: yes | Material/closure identity, calibration and approximation scope |

- **Visuals → Appearance** keeps Scientific/Observatory/Cinematic. Add an observation-source choice, source readiness and a compact model/units badge. Selecting an observation source never enables physical feedback.
- **Simulation → Material & radiation** owns the explicit coupled-mode configuration. Changing the material law, physical unit mapping, authoritative mesh or dynamical frequency groups requires validated state migration or a full model restart. It is not an appearance change.
- Prescribed preview parameters are stored separately from physical initial conditions. Saving/loading appearance must not import thermal energy or enable coupled dynamics.
- Switching to Scientific or hiding spectral output does not stop a running coupled solver. Conversely, turning coupled dynamics off must not discard radiation energy mid-run: require an explicit restart or a separately qualified state conversion.
- The first spectral material is a continuous emitting/absorbing volume. Existing simulation particles are not automatically stars or photons. Optional particle tracers remain diagnostic overlays, excluded from photometry.
- Unresolved physical point emitters become available only when a material provider supplies their spectral luminosity and its physical energy destination. No mass-only stellar-temperature rule or arbitrary point/diffuse fraction is inherited.
- Keep camera framing, follow mode, saved views, exposure and shutter ownership unchanged. Invalid spectral input produces an explicit unavailable state, not a stale physical-looking frame without an age/error label.

## 4. Data and closure interfaces

These are proposed semantic contracts, not new code or frozen GPU binding layouts. Use the project's existing packed-array/RID and Dictionary-at-frame-boundary conventions. Freeze exact byte layouts in the implementing shader headers and a focused preregistration before dispatching them.

### 4.1 Model bundle

A local `RadiativeModel` bundle contains:

- `schema_version`, `model_id`, `model_revision`, source/data hashes, equation references and qualification scope;
- material assumptions, required state components, validity ranges and supported capabilities;
- a `UnitMap`, immutable `SpectralGrid`, coefficients/tables or selected compiled kernels;
- interpolation and extrapolation rules, numerical precision, table error bounds and data licenses;
- separate provenance for derived identities, supplied constitutive laws, external measurements and calibration choices.

Unknown major versions, nonfinite data, unsupported capabilities or missing required components are rejected before GPU allocation. Out-of-range queries return a documented error; no hidden extrapolation or silent zero emissivity. Importing a bundle never executes arbitrary downloaded code. Theory implementations produce reference data/fixtures; Godot uses vetted local kernels or tables, not Python calls in a frame loop.

### 4.2 Physical units

`UnitMap` declares length in metres per simulation length, time in seconds per physical simulation time, mass in kilograms per simulation mass, and the thermal/material normalization. Derive mechanical energy, power, velocity, volume and density units consistently. Different numerical reference scales are allowed only with explicit conversions to the same physical budget. A chosen temperature normalization must agree with the equation of state and energy scales; `T_*`, the entropy reference, does not by itself calibrate kelvin.

The physical light speed maps to `c_gamma_sim = c_gamma_SI * time_unit / length_unit`. Opacity multiplies physical path length. Radiance density per Hz is not radiance integrated over a band; wavelengths shown in nm must be converted consistently using `nu = c_gamma/lambda` and the appropriate Jacobian.

The interface quantities below are specified in SI for unambiguous interchange. GPU buffers use an explicitly identified nondimensional representation derived from the same `UnitMap`, with conversions at the validated boundary. This avoids unnecessarily mixing astronomical positions, tiny opacities and large light speeds in FP32 arithmetic. Radiance, flux and energy-density scales are derived consistently; runtime data must never be guessed to be SI or simulation units from the field name.

The closure's section 14 chooses radiation energy-density scale `e_rad0 = a_R*T0^4` and flux scale `c_gamma*e_rad0`. This is compatible with mechanical energy scale `U0 = M0*L0^2/t0^2` when the ratio `e_rad0*L0^3/U0` is retained in exchanges and budgets. Do not confuse an energy-density normalization with total energy, or add independently normalized material and radiation values without those weights.

A preview may use an explicitly supplied physical calibration. Its label and capture receipt retain that provenance. The native model cannot receive a derived/calibrated label merely because a convenient scale produces visible rather than infrared emission.

### 4.3 Material snapshot and authoritative state

A `MaterialSnapshot` identifies:

- producer and snapshot schema; immutable model, unit-map and group-layout hashes;
- reset/state epoch, executed physics step, physical time and integration interval;
- canonical element IDs, topology/geometry generations, element volumes and coordinate frame/origin;
- mass or physical number content, momentum/velocity and thermal/internal energy;
- species/population arrays only when actually represented by the material model;
- optional composition/field inputs with explicit meaning; a validity mask and provenance/readiness status.

Conservative material storage uses **extensive quantities** per canonical element: mass, species numbers and internal energy. Temperature and intensive density are reconstructed through the EOS and current volume. Remapping interpolated temperature directly is forbidden because it does not conserve energy.

Build the observation cache from evaluated canonical emission/absorber quantities. Preserve integrated group emissive power under deposition and remap; do not average temperature first and then evaluate the nonlinear Planck law. Conservative power deposition does not prove accurate transmission through unresolved clumps, so spatial convergence remains a separate requirement.

The first prescribed preview can instead supply validated temperature/density arrays and a declared material law, because it has no dynamical conservation claim. Such a snapshot carries `coupling = prescribed`, cannot be restored as a coupled checkpoint and is never used to debit the native heat ledger.

A qualified live adapter must establish canonical element identity, physical volume, material density/inertia, EOS, initial thermal state, transport, pressure/work coupling and boundary exchange. Optical-site opacity and optical cell volume cannot substitute for this work. The existing constant-density periodic reference does not automatically qualify variable-density moving/open-window production dynamics.

### 4.4 MaterialClosure interface

One closure implementation exposes three batch operations conceptually:

1. **Describe requirements and domain.** State schema, supported geometry/material regimes, units, groups, species, frame convention and qualification.
2. **Evaluate thermodynamics.** Convert extensive state and volume to temperature, pressure and required constitutive derivatives. Account explicitly for excitation/ionization energy when populations exist.
3. **Evaluate radiative coefficients and population/source terms.** Produce group emissivity, absorption and scattering information from material state, and radiation state when the model requires it.

Use structure-of-arrays GPU storage and a small typed control header. No Dictionary allocation or virtual GDScript call per cell. Cache tables and uniform sets until their identities change. The initial provider is a prescribed LTE absorber/emitter with declared coefficients; no chemical composition is invented from `c`.

| Quantity | Meaning and units |
|---|---|
| `T_K` | Material temperature in kelvin after the declared EOS/calibration |
| `j_g` | Emissivity integrated over frequency group `g`, W m^-3 sr^-1 |
| `alpha_a_g`, `alpha_s_g` | Absorption and scattering coefficients, m^-1 |
| `phase_g` | Normalized scattering phase-function description; isotropic initially |
| `E_LTE_g` | Equilibrium radiation energy density in the group, J m^-3 |
| `L_g` when supported | Unresolved emitter luminosity, W, with a unique physical emitter ID |

For constant-within-group LTE absorption, require `j_g = alpha_a_g * c_gamma * E_LTE_g / (4*pi)`. A future frequency-varying model must declare its emission, absorption and transport means; one average opacity cannot silently serve all three. Non-LTE models provide population evolution and emissivity explicitly rather than being forced to satisfy LTE Kirchhoff emission.

### 4.5 Frequency groups and radiation state

`SpectralGrid` contains ordered frequency boundaries in Hz, integration/reconstruction conventions, group identity and coverage. Bolometric energy must include out-of-visible-band emission: use explicitly integrated low/high-frequency tails or a declared, bounded truncation error. Do not lose infrared/UV cooling because the camera cannot see it. Tail bounds are represented semantically; do not feed infinities into generic GPU arithmetic.

Initial continuum-preview qualification considers 16, 32 and 64 visible groups over the CIE observer interval, with two bolometric tails. Select the smallest layout that passes the frozen colour/energy controls; if none passes, stop and change the registered discretization before further claims. Frequency edges are the ordered transforms of the visible wavelength edges. This is a design schedule, not a measured accuracy or performance result. Physical group layout stays fixed for a run; frame-time adaptation cannot change it.

For fixed frequency edges, the LTE group fractions depend on temperature. Evaluate `E_LTE_g(T)` or its qualified table at each required source stage; do not freeze the initial fractions while material heats/cools. The colour and power checks include a temperature sweep across group boundaries.

For the M1 engine implementation, `RadiationState` carries `E_g` (J m^-3) and `F_g` (W m^-2), with `P_g` supplied by the selected angular closure. Enforce `E_g >= 0` and `|F_g| <= c_gamma*E_g` through the qualified numerical method. Reject invalid input instead of clipping it into apparent realizability. Store/remap `E_g*V` and the corresponding radiation momentum extensively.

The transport descriptor declares physical/reference frame, light speed, angular closure, spatial discretization, boundary conditions and time integration. M1 does not resolve crossing beams; a future angular solver is a different capability, not an undocumented tweak to opacity. The stationary reference source does not qualify moving-medium transport.

The completed closure's section 7 distinguishes bolometric covariance from fixed-bin moving transport. Record the frequency frame and treatment of frequency-boundary terms in the transport descriptor. Velocity gradients Doppler-shift radiation across fixed lab-frame group edges; applying a gray four-force independently to each fixed bin does not include that transport. Group sums, boosted-LTE behavior and cross-bin energy fluxes need independent reference controls before enabling the moving multigroup capability.

### 4.6 Publication and lifetime

A publication is a coherent immutable bundle of material, coefficient and radiation views for one accepted state step and matching geometry/model identities. Bind borrowed RIDs only on their owning RenderingDevice. Never pair interpolated particle positions with a mismatched canonical thermal state without a separately qualified, explicitly labelled reconstruction.

The engine advances host counters while recording GPU commands. Treat such counters as ordered-work identities, not independent proof of GPU completion. Same-device consumers follow the command/barrier dependency; CPU captures/checkpoints wait for the corresponding completed publication before pairing pixels or arrays with metadata. Do not introduce a full GPU wait/readback into every interactive frame.

- Production global RD: record work on the existing render-thread-owned chain; never manually submit/sync the global device.
- Local-RD verification: create/use the device on its owning worker; extract shader SPIR-V before worker use; submit/sync only the local device.
- CPU/file transfers carry packed data and metadata, never device-specific RIDs.
- Reset, reinit, topology replacement and shutdown invalidate consumers before freeing source buffers. Release uniform sets before resources, and join the owning worker before freeing its device.
- A new model, unit map, spectral layout, reset/topology identity, camera cut or incompatible projection invalidates observation history. Normal successive physical steps are not the same event as a reset.
- Explicitly implement/test spectral source-identity rejection; existing packed source/site epoch fields are not proof that the legacy shaders use them to reject history. Required material/geometry readiness must be checked at the physics boundary as well as the observer.
- Checkpoints include all adaptive thermal, population and radiation components plus model/units/group/boundary identities. A partial checkpoint cannot silently resume coupled mode.

## 5. Two separate transport paths

### 5.1 One-way observation

The preview consumes a material snapshot and produces an image. No cooling, forces, population evolution or radiation-energy accumulation occurs in `CassiObservatory`, its volume backend, a compositor callback or a material shader.

Start with emission plus absorption. For a homogeneous segment and group, evaluate

$$
I_{g,\mathrm{out}}=I_{g,\mathrm{in}}e^{-\tau_g}
 + \frac{j_g}{\alpha_g^{\rm a}}(1-e^{-\tau_g}),
\qquad \tau_g=\alpha_g^{\rm a}\Delta s,
$$

with the continuous zero-opacity limit `I_out = I_in + j_g*ds` and cancellation-safe small-tau evaluation. LTE reduces the source function to the group-integrated Planck radiance. Physical boundary illumination is a declared spectral input; the procedural RGB background is not automatically a radiative boundary.

Add scattering only with an explicit incoming-radiation source and angular approximation. The current six-direction RGB sweeps remain a legacy approximation. They are not relabelled as a full spectral scattering field. In the first coupled isotropic-scattering observation, the scatter source can use the published group energy density; anisotropic scattering requires an additional qualified angular reconstruction/solver.

An observation pass is not the physical radiation evolution. A frozen-state formal solution may assume quasi-static light transport. Record that approximation; rapidly changing scenes require a qualified time-dependent/retarded observation method before claiming that scope. Radiation moments are not uniquely a camera image.

### 5.2 Conservative evolution

Only enable this after the live material adapter and the transport backend pass their own qualification. At an accepted physical step:

1. Establish canonical geometry, volumes and any conservative material/radiation remap.
2. Advance the qualified material transport/mechanical terms and record their physical work/heat destinations.
3. Evaluate the material closure at the required integrator stages; subcycle/solve radiation with the declared physical timestep and boundary fluxes.
4. Apply each radiation/material exchange once as a **paired transaction** from the same stage state. Radiation energy/momentum gain is the material total-energy/momentum loss.
5. Recover thermal energy through the EOS after accounting for kinetic and excitation/ionization changes; solve the coupled source consistently rather than applying a temperature floor.
6. Finish the accepted step, reduce bounded diagnostics, and publish complete same-step state.

The selected material integrator determines splitting/order; a draw frame does not. The completed closure supplies a stationary gray backward-Euler reference and a source-subcycling qualification. Its coarse-step accuracy failure demonstrates that positivity, stability and conserved energy alone are insufficient. Use source error control/subcycling and transport CFL control as separate requirements; neither the benchmark `dt=0.001` nor its static source proof qualifies an arbitrary moving update.

Radiation momentum is `F_g/c_gamma^2` per volume. Giving matter momentum changes its kinetic energy; a momentum-only kick with unchanged radiation energy generally fails moving-frame energy accounting. Use the qualified paired source, including work terms and the stated nonrelativistic/relativistic approximation. Do not infer full radiation hydrodynamics from a rest-frame elastic-scattering test.

For a closed qualified material/radiation subsystem, track its total energy and momentum. For the open tracking window, retain incoming/outgoing material, radiative, mechanical-work and remap fluxes explicitly. Boundary loss is not deletion. Native gravitational/field work that lacks a qualified energy correspondence is reported as an unresolved coupling term, not hidden inside a claimed closed total. The current native-force boundary in the Theory feasibility document remains a blocker to a broader conservation claim.

Use physical `c_gamma` initially. An impractical light-crossing timestep is a measured limitation: pause/reject that physical configuration or use the declared physics timestep/subcycling budget. Do not change light speed from the quality controller. Any future reduced-speed-of-light approximation needs a separate model identity and its own equilibrium, force, diffusion and timing qualification.

## 6. Spectral camera and GPU cost

### 6.1 Replace spectral sources, retain the camera finish

Keep the legacy backend intact. A new `CassiSpectralVolume` consumes the proposed coefficient/snapshot interface and returns a **complete sensor-radiance result**, including its declared spectral boundary. The existing post controller receives an explicit composition kind: legacy point-plus-volume, or complete spectral-camera image. The latter must not add legacy warm particle light or the procedural RGB sky a second time.

Integrate spectra before converting to XYZ and linear display RGB. Use the [CIE 1931 2-degree observer data](https://cie.co.at/datatable/cie-1931-colour-matching-functions-2-degree-observer), 360–830 nm at 1 nm spacing, with a fixed photometric normalization and an explicitly recorded RGB transform/white point. The official metadata names SHA-256 `fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1` and CC BY-SA 4.0; verify the actual downloaded table, retain attribution/license and the metadata when importing it. These are external observer data, not Cassi predictions.

The group reconstruction used for XYZ must match the spectral integration convention. Preserve the Hz-to-wavelength Jacobian. Finite groups do not recover arbitrary unresolved lines: line providers require line-aware group placement or another resolved spectral basis, followed by new accuracy qualification.

Exposure, fixed/adaptive exposure, bloom, gamut mapping and shutter are camera/display operations. Preserve the existing single output colour conversion and keep UI outside the post stage. Save pre-exposure linear radiance/XYZ for quantitative checks. Never normalize each source spectrum to white, or use an automatic white balance as a material-temperature mapping. A scalar alpha is not a general representation of wavelength-dependent transmission.

Negative components produced by an out-of-gamut linear RGB transform are a display-representation issue, distinct from negative physical spectral radiance. Preserve the raw radiometric/XYZ result and apply the declared display gamut mapping; do not change the material spectrum to make every intermediate RGB component positive.

### 6.2 Point sources and double counting

The first spectral path renders material-volume radiation and can show non-emissive diagnostic tracers separately. Retain all simulated particles; their count is not a light-source count.

A future unresolved-emitter capability supplies `L_g`, support/position and emitter identity. Its luminosity is deposited/rendered once, with spectral extinction to its own depth, normalized PSF and the correct distance/solid-angle response. If a source is split between point and volume representations, weights sum to one per group and emitter. Absorption/energy feedback is computed once in the physical solver, never from how many fragments happened to be visible. A physical line/stellar material provider must not inherit the legacy `point_fraction`, `reference_mass` brightness normalization or RGB spectrum.

### 6.3 Bounded storage and cadence

Do not allocate one spectral state per one of the 2.5 million rendering particles unless those particles truly are material elements in the qualified model. Use canonical material elements; the observation cache is a derived lower-resolution representation. Preallocate bounded structure-of-arrays buffers, reuse them by generation, and avoid full frame/field CPU readbacks in normal operation.

Design arithmetic illustrates the main trap (not measured allocation): at 64^3 cells and 18 groups, four FP32 coefficient channels use **72 MiB**; ping-pong `E_g,F_g` uses **144 MiB**, excluding material/geometry/scratch. Copying the current 640×360×64 camera-depth tau texture once per group would cost **1,012.5 MiB** by itself.

Therefore the first spectral camera streams a bounded group batch through ray integration and accumulates XYZ/HDR; it does not keep a full per-group, per-depth screen-space tau atlas. Reuse world-space coefficient storage. A later point-emitter path must qualify its spectral column algorithm and memory bound rather than resurrecting that atlas unnoticed.

Before each allocation, compute total bytes including ping-pong, remap, shadow/transport scratch and existing renderer usage. Reject unsupported physical layouts with an explicit required/available budget. Display-quality reductions may change optical cache resolution, rays, samples and pixel resolution only. They cannot coarsen the authoritative thermal/radiation mesh, alter species, change physical groups, drop physics steps or turn off absorption.

## 7. Persistence, capture and reproducibility

Extend the existing capture helper rather than adding another recorder. Each spectral still/sequence/movie has a sidecar containing:

- source mode and physical/prescribed/approximation label;
- model, data, unit-map, observer and group-layout identities/hashes;
- executed step/time, material/radiation/geometry publication IDs and reconstruction ages;
- actual camera transform, FOV, dimensions, exposure, white point, output transform and shutter interval;
- physical boundary illumination, relevant model assumptions and any unavailable component;
- actual filenames, frame counts, sampled simulation times and dropped-frame information;
- optional pre-display linear image or spectral samples with units, not a PNG relabelled as raw radiometry.

Capture metadata and pixels must come from the same published frame. Freeze/pin the relevant publication during a supersampled still and restore interactive state on every path. A sequence may have gaps in filenames; enumerate actual files and validate their contents. Movie Maker cadence, runtime window dimensions and encoded viewport dimensions remain separate quantities. A finite shutter integrates physical radiance over its declared interval; the existing velocity-footprint approximation must remain labelled until qualified for variable luminosity and extinction.

Physical checkpoints persist the full canonical state described in section 4, independent of appearance presets. World-agent Apply/Undo, resets, scene reinitialization, merges, accretion and changes of authoritative topology must either include every new state component or explicitly reject the operation in coupled mode. Rendering a saved camera view does not restore physics.

## 8. Implementation sequence and dependencies

These milestones define accepted native capabilities. P0/P1 are implemented. The retained bounded supplied-material engine exercises selected P3/P4 state and operator seams without satisfying the native P2 prerequisite or promoting P3/P4. Freeze each remaining case, statistic, tolerance and stopping rule in a focused preregistration before scientific/GPU experiments. Existing accepted Theory controls are reused only at their qualified scope; new native adapters are qualified separately.

| Milestone | Complete deliverable | Prerequisite / exit condition |
|---|---|---|
| **P0 — contracts and reference inputs** | Local model/snapshot descriptors, unit validation, spectral-grid/observer assets with provenance, and a real reference loader for prescribed material snapshots | Existing Theory sources and official observer data inspected; CPU analytic controls and rejection cases pass |
| **P1 — one-way spectral observation** | Working emission/absorption volume, complete-image compositor mode, source selector, explicit preview labels, raw linear output and capture sidecars | P0; analytic slab/continuum colours, read-only parity, live geometry/source switching and actual screenshots pass |
| **P2 — live material correspondence** | A declared native-to-material adapter with physical units, canonical mass/volume/EOS, initial thermal state, transport/work budget and restart/remap/checkpoint semantics | Independent numerical/physical qualification; no assumption that the periodic incompressible reference already covers the moving native domain |
| **P3 — engine thermal state** | Default-off simulation-owned thermal state and qualified transport/work exchange, complete publication, lifecycle and persistence | P2; stationary/shear/conduction/conversion controls where applicable, canonical remap/boundary accounting and native off-parity pass |
| **P4 — coupled radiation** | Grouped transport plus conservative material/radiation energy and momentum exchange, stiff source integration, boundary fluxes, and observation of the accepted live state | Qualified radiative source/transport scope and P3; finite-step budget, realizability, frame-independence and full configured battery pass |
| **P5 — richer and derived material providers** | Imported qualified Cassi coefficients or species/non-LTE/line models, plus unresolved emitters or richer angular transport when their declared capabilities require them | Provider-specific reference fixtures, units/material mapping, coverage and convergence tests; no automatic promotion of scope |

P0/P1 do not require a Cassi microscopic spectrum derivation. P2 remains independent of the camera implementation; its absence does not justify inventing a native temperature. The supplied-material engine does not turn its homogeneous control into evidence of native physical closure. A calibrated standard-physics provider can be a useful supported model; P5 is an additional scientific capability, not a prerequisite for declaring that external-input model accurately.

P4 has ordered subdeliveries:

1. **P4a: bolometric coupled transport and covariant exchange**, within the declared material approximation. This is the first moving energy/momentum integration; a gray radiation field does not contain a transported visible spectrum.
2. **P4b: stationary/material-rest-frame multigroup transport**, including temperature-dependent LTE fractions, groupwise energy exchange and a spectral observation of that qualified state.
3. **P4c: moving multigroup transport**, including the required Doppler/frequency-space boundary terms, spectral-frame conversions and qualification across the declared velocity/optical-depth regime (`beta*tau`).

The frozen [`CR-G0–CR-G8` schedule](coupled_radiation_engine_prereg.md) qualifies the homogeneous ideal-monatomic-gas control implemented by `scripts/cassi_radiation_engine.gd` and `compute/cassi_radiation_coupled.glsl`. Its extensive material/group state, isotropic-affine work and frequency shift, implicit LTE energy exchange, accepted-step batching, checkpoint identity, fail-closed setup and teardown pass 86/86 focused checks. This receipt does not qualify a native P2 adapter, spatial P4b transport, the general P4c regime, a plasma/atomic provider, radiation momentum transport or physical point emitters.

Until P4c is qualified, a moving gray run may expose thermal material to the prescribed spectral observer, but the output is labelled a spectral reconstruction from material, not the evolved multigroup radiation spectrum. PR-G9 includes boosted equilibrium, radiation crossing frequency-group edges, conservative group sums and spectral/time refinement for P4c.

### 8.1 Component ownership

The focused components now have these responsibilities:

| Component | Responsibility |
|---|---|
| `scripts/cassi_radiative_material.gd` | Validate prescribed and coupled supplied-material bundles, units, group metadata, immutable hashes and explicit capability limits |
| `scripts/cassi_spectral_volume.gd` and `compute/cassi_spectral_*.glsl` | One-way spectral observation and sensor accumulation |
| `scripts/cassi_radiation_engine.gd` and `compute/cassi_radiation_coupled.glsl` | Default-off extensive material/radiation state, affine frequency work, implicit LTE exchange, accepted-step publication and complete checkpoint lifecycle |
| `research/presentation/physical_radiation_reference.py` and `research/presentation/coupled_radiation_reference.py` | Independent observation and coupled-control fixture generation; no import from production GDScript or GLSL |
| `scripts/verify_physical_radiation.gd`, `scripts/verify_coupled_radiation_engine.gd` and their scenes | Retained GPU regressions for optical, energy, identity, batching, checkpoint and resource-lifecycle contracts |

Do not grow pinned legacy push constants or attach arbitrary extra meanings to existing buffers. `scripts/contracts/layout.gd` pins the instancer at 32 floats/128 B, and the existing Observatory volume PC also occupies 128 B. Group coefficients and larger descriptors belong in dedicated storage buffers/textures. New compute resources have their own explicit headers and layouts. Wire all active consumers, including recorder initialization and supported snapshot paths, when the corresponding mode is introduced.

### 8.2 Parallel ownership during implementation

After P0 freezes the shared formats, P1 can split into a spectral-backend lane and a UI/capture lane with disjoint files. The integration owner alone changes the Observatory controller and compositor boundary. P2 is an independent material-correspondence lane; it cannot change the P1 observational contract silently. P3/P4 serialize mutation of the engine step/resource boundary under one owner. Independent workers skip builds, tests, formatters and GPU launches while sibling edits are active. The integration owner runs verification once after the wave settles; GPU scenes run serially.

## 9. Acceptance matrix

Gate names below are scoped to this design. They do not renumber the existing engine battery. Numerical targets are proposed acceptance requirements; freeze fixtures, scales and thresholds before execution. A failed target is retained as a failure, not relaxed after seeing a result.

| Gate | Observable requirement |
|---|---|
| **PR-G0 — default and observation parity** | With the feature off, existing dispatch/resource paths and authoritative state remain unchanged. Preview and camera-only changes produce byte-identical sampled solver payloads in matched same-device runs. No feature GPU allocation while off. |
| **PR-G1 — units, identity and readiness** | Reject inconsistent energy/length/time scales, absent calibration, mismatched groups/topology, unsupported capabilities and incomplete checkpoints before a physical render/step. The UI reports which prerequisite is absent. |
| **PR-G2 — independent reference physics** | Reproduce the applicable existing Theory thermal/radiative controls at their published tolerances using the executed source identity. New moving, variable-density or boundary behavior requires additional controls, not inherited PASS labels. |
| **PR-G3 — spectral observation** | Zero opacity, empty volume, homogeneous slab and front/inside/behind-source cases match independent CPU transport. Initial FP32 target: normalized HDR/flux error <= 1e-4 for analytic fixtures; no NaN/Inf or negative physical radiance. Use scale-aware absolute checks near zero. |
| **PR-G4 — spectrum and colour** | Compare continuum Planck cases at 100, 3000 and 10000 K to direct integration, including bolometric tails. CPU reference meets its frozen quadrature tolerance; candidate grouped GPU preview has relative XYZ error <= 1e-3 where components are resolved and chromaticity distance in CIE u'v' <= 0.002 where luminance is nonzero. A dim/IR source is not normalized into visibility. |
| **PR-G5 — spatial and spectral convergence** | Slabs, dense core/diffuse edge and spectral features are evaluated under doubled sampling/group resolution against the independent reference. Discretization differences are recorded separately from energy-budget error. Line claims require resolved line-placement controls. |
| **PR-G6 — material/radiation exchange** | Test heating and cooling directions, zero-opacity and LTE nulls, stiff exchange and moving momentum/work. Require a nonzero exchange above the FP32 resolution floor. Initial GPU target: paired transaction residual <= 1e-5 of declared energy/momentum scales and accumulated closed-fixture budget residual <= 1e-4; report residual relative to transferred energy as well. A missing opposite source must fail. |
| **PR-G7 — topology and open boundaries** | Reinit, window translation/resize, site replacement, conservative remap, material escape, merge/accretion and supported Apply/Undo preserve named extensive budgets including recorded boundary/source fluxes. Mixed generations, double heat consumption or silently dropped radiation fail. |
| **PR-G8 — physical clock independence** | Given the same accepted physical-step schedule, paused camera motion, hidden output, appearance changes, differing draw cadence, adaptive optical quality and 1x/2x capture produce identical coupled-state payloads on the same execution path. No radiative update is sourced from render `source_epoch` or wall-clock `delta`. |
| **PR-G9 — transport scope** | M1 realizability, free streaming, isotropic equilibrium, diffusion limit and boundary conditions pass separate spatial/time refinements. Record the known crossing-beam limitation. Moving-medium sources and propagation each receive their own controls. |
| **PR-G10 — physical source accounting** | When point emitters are supported, integrated unclipped flux survives PSF/shutter changes and point/volume repartition within 1%; inverse-square point-source irradiance and resolved-surface radiance behavior are tested separately. Every physical emitter/source is counted once. |
| **PR-G11 — actual surface and capture** | Exercise both Particle and Field views, all retained appearances, valid/invalid spectral sources, resize, pause/resume, cuts, reinit and enable/disable. Inspect windowed screenshots and a short movie; verify actual encoded dimensions, enumerated files, simulation times and matching sidecars. Preserve WASD/manual camera behavior. |
| **PR-G12 — resources and performance** | Account for all owned/borrowed allocations, bounded histories and teardown; no invalid RID or TDR. Measure actual post-draw median/p95, GPU time where supported, physics steps/second and bytes/readbacks, with fixed then adaptive observation quality. No cost or FPS claim from dispatch counts alone. |

For PR-G12, start from the existing production benchmark conditions in the [technical guide](../../TECHNICAL_GUIDE.md#measured-observatory-render-boundary-timing): 2.5 million particles, 1280×720, seed 736241, matched wide/core/zoom paths and both render modes. Use fixed-state paused comparisons and matched accepted-step live comparisons; report them separately. Freeze a warmup and at least 300 measured post-draw intervals per path, with repeated runs. The existing 20 ms adaptive target is an initial interactive preview p95 target, not a promise. If it fails, retain a fixed-quality/capture-only result or revise the implementation under a new recorded run; do not change physics to meet it. Coupled dynamics also reports simulation progress independently of draw rate.

After engine/shader integration, run the default-path gate (`scenes/verify_core.tscn`) plus any relevant standalone optical, Field Particles and radiation probes. [verify/README.md](../../verify/README.md) lists the retained probes. Windowed GPU scenes run one at a time using the console executable. Do not kill the user's editor.

A missing physical prerequisite or unsupported regime is **INCONCLUSIVE** for that physical claim; a violated registered numerical/identity requirement is **FAIL**. Passing a preview gate does not promote a native thermal or radiative derivation. Performance failure blocks an interactive performance claim, not the reporting of a correct bounded reference result.

## 10. Adding future full derivations

The handoff from Theory is concrete:

1. Identify the derivation's state variables, physical normalization, material regime, frame and boundary assumptions. Supply all required material/species state; do not infer missing atomic identity from a field colour.
2. Provide equations plus a versioned coefficient/kernel bundle and independent reference fixtures: spectral power, absorption/scattering, limiting states, rates, energy/momentum exchange and validity boundaries.
3. Check which MaterialClosure capabilities it satisfies. A new opacity/emissivity law can replace the existing provider while the spectral camera and capture schema stay the same.
4. If it needs populations, excitation energies or radiation-dependent kinetics, add those canonical components and checkpoint/remap support before enabling it. Population inversion/negative net line opacity needs an active-medium capability and stored-energy accounting; it is outside the initial nonnegative-opacity provider. If it needs polarized, coherent-wave, nonlocal or richer angular transport, version the relevant solver/state interface rather than packing those quantities into RGB or an M1 scalar slot.
5. Compare provider predictions with the reference before LUT/interpolation/FP32 optimization. Qualify approximation error, spectral resolution and out-of-domain handling independently.
6. Run the applicable adapter, exchange, transport, observation and lifecycle gates. Promote only the physical scope actually exercised; retain separate labels for supplied data and derived results.

This design makes future local radiative laws replaceable without changing camera controls, recorder behavior or the renderer's physical units. It does not promise that an unknown future microscopic theory will fit an unchanged numerical state. The explicit state/capability boundary is what makes that larger change manageable.
