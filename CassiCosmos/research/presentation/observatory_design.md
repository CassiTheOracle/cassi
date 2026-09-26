# Observatory presentation renderer

## Status: implementation design and verification preregistration

The requested package adds Scientific, Observatory and Cinematic appearances. Scientific (style 0) is the default and retains the current rendering paths, shaders, materials, Environment and solver behavior. Styles 1 and 2 are read-only render consumers. This document freezes the implementation interfaces and verification criteria before GPU experiments.

## Image formation

A renderer-owned world-space density grid reconstructs the existing particle mass distribution with conservative cloud-in-cell deposition and normalized filtering. It is an optical cache, never a simulation state. All particles remain simulated and individually rendered. A bounded grid (48/64/96/128 per axis) supplies diffuse emission, absorption and six-direction single-scattering illumination. Dense regions shadow the incident light during the directional sweeps. Naturalistic emissivity and extinction are explicit material assumptions in simulation units, not temperatures or astronomical spectra inferred from coherence.

The camera volume integration produces linear HDR premultiplied radiance, representative depth, and cumulative optical depth on a logarithmic camera-depth texture. The optical particle shader evaluates that cumulative optical depth at the particle's own depth. A particle is never attenuated by the whole cloud or its representative depth. Point and diffuse emission use complementary weights. Normalized, screen-space Gaussian footprints preserve integrated projected flux when the footprint grows; a projected velocity covariance implements an optional finite shutter. Distant structure is the same particle distribution plus its conservative optical reconstruction, without procedural foreground noise.

In Field mode the live site optical payload is the volume source, not a stale periodic field grid. The Scientific CanvasLayer texture remains untouched. Observatory/Cinematic suppress that display while their field volume enters the camera compositor. The same post stage therefore handles both particle and field views.

A POST_TRANSPARENT compositor sums attenuated point emission with the medium's radiance, performs restrained HDR bloom, applies one exposure/highlight transform to that matter sum, and then, when the world background is enabled, adds a faint world-stable sky through the residual transmission; the background ships disabled by default. The medium radiates only where it is the subject, the field and cosmology compositions; in the particle composition it carries transmittance alone, so the coarse volume grid never lays a voxel wash over the point cloud while dense matter still darkens the background behind it. The background is added after the exposure multiply, so it is never directly exposure-scaled and never enters the meter; because it joins the matter sum before the shared highlight transform, that transform still compresses it where matter shares the pixel. While active, a private Environment uses black background, linear tone mapping, exposure 1 and no built-in glow. Godot performs output color conversion; the custom post stage does not add a second sRGB conversion. The original Environment and optional sky visibility are restored when disabled.

Volume history reprojects representative depth, rejects camera cuts, resize, source resets and incompatible depths, and clamps historical radiance against current local neighborhoods. Point stability comes from analytic filtered footprints and MSAA, not invalid opaque motion vectors for transparent particles. Auto exposure is on by default and follows the matter the active composition renders: the meter samples that composition's own source (the point layer in the particle composition, the medium in the field and cosmology compositions), ignores frame regions with no matter, holds its correction while nothing is lit, corrects within ±8 EV around the manual Exposure control, and approaches its target over a 2 s time constant so it tracks instead of pumping the frame. The metered target luminance is a setting (`auto_exposure_target`, 0.03 by default, about 2.6 EV below the 0.18 mid-grey reference), so the converged level is chosen rather than fixed, and the same target is reached whether the frame is tightly framed on the cloud or holds it at a distance. A view-depth window (world units, 0 keeps the whole occupied domain) clamps the ordered particle layer's far distance for both the volume raymarch and the billboard optical window and fades the outer part of that window instead of ending it with a hard pop, which bounds how many particle layers stack along one view ray. UI and legends are outside the post stage.

## Ownership and interfaces

Main owns `scripts/cassi_sim.gd`, `scripts/cassi_observatory.gd`, integration and final verification. Independent workers own only their assigned new files or existing UI/capture files. No worker runs validation, formatters, builds or tests during concurrent mutation.

### Optical backend

`res://scripts/cassi_observatory_volume.gd` extends RefCounted. It is constructed by the controller. Public API:

- `initialize(device: RenderingDevice) -> bool`: load shaders/SPIR-V on main thread, establish shared global RD. No local submit/sync.
- `update(frame: Dictionary, settings: Dictionary) -> bool`: allocate/cache renderer-owned resources, record ordered compute work outside existing lists; return true only when outputs are valid.
- `shutdown() -> void`: release owned uniform sets before resources; never free borrowed source buffers.
- `radiance: Texture2DRD`, `depth: Texture2DRD`, `optical_depth: Texture3DRD`, `motion: Texture2DRD`: GPU outputs. Radiance alpha = opacity. Optical-depth xyz encode cumulative scalar tau (r sufficient) from camera to logarithmic slice distance; fully transparent means tau=0. Motion contains one vec4 per particle, xyz=world velocity, w=particle mass, width=min(4096, bounded device width), addressed by INSTANCE_ID. Reuse texture until count changes.
- `statistics() -> Dictionary`: dimensions, dispatch count, allocation count and resource validity, no frame-sized CPU readbacks.

`frame` keys: `positions` RID (vec4 xyz+mass in render-local coordinates), `velocities` RID (vec4 velocity), `particle_count` int, `source_epoch` int, `field_mode` bool, `optical_sites` RID (vec4[2*site], xyz+opacity then EY/EI/coherence/gradient), `site_count` int, `site_epoch` int, `bounds` AABB in render-local coordinates, `camera_transform` Transform3D in render-local coordinates, `fov` float vertical degrees, `viewport_size` Vector2i, `near` float, `far` float, `reference_mass` float (frozen initial total mass), `reference_radius` float (initial support scale), `delta` float, `simulation_delta` float, `playing` bool, `reset_history` bool. Particle and camera positions share the same render origin. Field optical sites are in render-local coordinates; Main ensures the appropriate transform or passes `site_origin_offset` Vector3 to translate them. Frame `near`/`far` provide the exact logarithmic optical-depth sampling range to the particle material; with an active view depth the controller clamps `far` to that window for the volume raymarch and the particle layer alike.

Settings are one dictionary. Keys/defaults: `style` 0; `exposure_ev` 0.0; `auto_exposure` true; `auto_exposure_target` 0.03; `optical_thickness` 1.0; `emission` 0.3; `scattering` 0.35; `point_fraction` 0.65; `bloom` 0.08; `temporal` true; `shutter_seconds` 0.0; `quality` 1 (0 Performance, 1 Balanced, 2 High, 3 Capture); `adaptive_quality` true; `target_frame_ms` 20.0; `background` false; `view_depth` 0.0 (world units, 0 = the whole occupied domain). Overlays belong to the capture helper, independently of appearance. Grid/viewport quality can be overridden in the frame by `grid_size` int and `render_size` Vector2i. Overrides let the controller tune total-frame cost without changing physics. Emission palette is fixed warm point light and restrained cooler diffuse light, explicitly naturalistic.

The backend owns `compute/cassi_observatory_density*.glsl`, `compute/cassi_observatory_light.glsl`, `compute/cassi_observatory_volume.glsl`, and `compute/cassi_observatory_motion.glsl` as needed. It must support particle and field sources and match source switching/reinit lifetimes. Conservative deposition must account for boundary weights without wraparound, integer quantization overflow, negative/dead mass or nonfinite inputs.

### Post stage and particle material

`res://scripts/cassi_observatory_post.gd` extends CompositorEffect. Public API:

- `initialize(device: RenderingDevice) -> bool`: main-thread shader load.
- `configure(frame: Dictionary, settings: Dictionary, volume: Texture2DRD, depth: Texture2DRD) -> void`: publish immutable per-frame state safely to render callback; frame and settings have the schema above. No scene-tree reads from render thread.
- `shutdown() -> void`: disable and release owned GPU resources safely, never free renderer scene buffers or borrowed outputs.
- `statistics() -> Dictionary`.

POST_TRANSPARENT callback reads resolved linear HDR scene color through RenderSceneBuffersRD; field_mode ignores particle scene color and displays the field volume. Particle mode adds scene color (already depth-attenuated by the material) and volume. Shared tone/exposure/bloom processing is identical for both modes. No premultiplied-alpha double multiplication. Background is optional: a continuous, position-independent deep-sky floor keeps empty rays legible at every camera angle, with a faint world-stable star field and no invented foreground structures. History applies to volume only, with depth reprojection/current-neighborhood clamp and reset handling. GPU exposure estimation is bounded and never reads full images to CPU. All GPU images are finite on empty/transparent input, resized safely, and allocated lazily.

`res://shaders/particle_billboard_observatory.gdshader` preserves existing compact/noncompact transform placement, but uses additive radiance, normalized Gaussian PSFs and view-depth extinction. Main binds uniforms: `size` 1.0, `compact_data` Texture2DRD, `compact_mode` float, `compact_tex_width` float, `optical_depth_texture` Texture3DRD, `motion_texture` Texture2DRD, `motion_tex_width` float, `viewport_height` float, `optical_near` float, `optical_far` float, `depth_fade_start` float (0 disables the fade), `luminosity_scale` float, `point_fraction` float, `emission_strength` float, `shutter_seconds` float, `velocity_time_scale` float, `reference_radius` float. For compact positions, the existing data texture stores vec4 xyz+instance scale and color/custom in two texels; true mass is supplied by motion.w (backend must store original particle mass there). Noncompact mass also comes from motion.w. Shader handles dead entries without draw, preserves flux under radius and velocity-covariance changes, and never treats mass/speed/coherence as physical temperature. Agent must communicate any additional uniform through the shared brief, not guess its controller binding.

Post worker owns its script, particle shader, and `compute/cassi_observatory_post*.glsl`/include files only. Shaders outside that set stay unchanged.

### Controller, UI and capture

Main exposes on CassiSim:

- `@export_enum("Scientific", "Observatory", "Cinematic") var observatory_style: int = 0`
- `get_observatory_settings() -> Dictionary`
- `set_observatory_setting(key: String, value: Variant) -> void`
- `set_observatory_style(style: int) -> void`
- `save_observatory_preset() -> Error`, `load_observatory_preset() -> Error`
- `get_observatory_statistics() -> Dictionary`
- `signal observatory_changed(settings: Dictionary)`

Style switching changes rendering only, not playing/dt/mode/particle data or camera ownership. Cinematic supplies bloom/shutter defaults but directed motion remains an explicit manual-first camera choice. Scientific restores the original visual settings and releases Observatory GPU resources. Quality automatic decisions use measured full-frame latency with hysteresis, not isolated volume time; fixed quality remains available for capture. Saved rendering settings do not silently enable the new renderer at startup.

UI worker owns `scripts/sim_ui.gd` and an optional `scripts/cassi_observatory_controls.gd` helper if needed to keep the large UI maintainable. Reuse the PARAMS/backed registry and house COptionParam/CSpinParam/CParam/CheckButton conventions. Add appearance, exposure, optical thickness, emission, view depth, quality and camera-adjacent controls; put scattering, point fraction, bloom, temporal, shutter, auto exposure, quality budget and background in a collapsible advanced group. Provide save/load appearance, explicit units/model explanation, and disable irrelevant legacy color controls/legend only while the naturalistic profile is active, restoring them on Scientific. `_viz_texture_rect` visibility = field mode AND style==0, so the canvas cannot cover the new compositor. UI does not hide point/volume resources itself. Keep WASD focus-safe and resize-aware.

Capture worker owns `scripts/main_recorder.gd`, `scripts/cassi_presentation_director.gd`, `scripts/cassi_presentation_capture.gd` (new), and discovered existing movie launch helper only. Public capture helper is a Node constructed by UI with `setup(sim: Node, camera: Camera3D)`. Methods: `save_view(slot: int) -> Error`, `restore_view(slot: int) -> Error`, `capture_still(scale: int = 1) -> String` (awaitable; returns actual local PNG path or empty on failure), `set_overlay_enabled(bool)`, `set_interface_visible(bool)`, `start_sequence(fps: int = 30) -> Error`, `stop_sequence() -> String`. Persist views as user:// resources/configs, camera pose plus FOV, no simulation state. Restore requests manual takeover; direct camera ownership remains free_camera/recorder. Stills and PNG sequences contain actual postprocessed image at verified dimensions, with optional scale/time overlay. Sequence capture reports dropped frames/wall times; do not mislabel a variable-cadence interactive sequence as deterministic Movie Maker. High-resolution capture must actually render at requested resolution and restore window/viewport/UI state on all paths. Preserve original Movie Maker path and add `--appearance=scientific|observatory|cinematic`, exposure/quality overrides without affecting old args. New overlay labels simulation units, not invented physical units. UI worker consumes the capture helper API.

## Verification before acceptance

Run GPU work serially, using the authoritative console executable in verify/README.md. Account for the current game child before launch; never kill the editor. No concurrent GPU agent runs.

1. Disabled style: exact unchanged shader/material selections and initial solver buffers; switch on/off while paused and compare fixed-state scientific framebuffer and solver payload bytes. Tolerance zero for solver payloads. Compare scientific frames with only existing nondeterministic presentation effects excluded by fixed camera/state.
2. Optical model: render a synthetic constant-density slab with emitter in front/inside/behind. Check transmission against exp(-tau) to 5% relative (sampling approximation), monotone ordering, zero extinction identity, and finite empty-volume output. Check single scattering responds to emission/scattering controls and is attenuated by a dense occluder. Check deposited mass conservation to 0.5% across quality tiers and boundaries.
3. Flux: fixed emitter and exposure, vary Gaussian footprint and shutter stretch; integrated unclipped HDR flux within 5%. Same mass split across particle counts within 2%. No arbitrary minimum-radius brightness gain.
4. Both real views: Particle and Field modes exercise Scientific/Observatory/Cinematic, camera movement, resize, pause/resume, source change/reinit, quality changes and disable/re-enable. Inspect actual screenshots and movie frames; no shader/runtime errors, no NaN/Inf pixels, no stale history after cuts. UI remains readable and controls change real output.
5. Capture: save/restore view, still at 1x and 2x, PNG sequence, and short Movie Maker run. Verify encoded dimensions/frame count/cadence metadata; restore interactive state after stills.
6. Performance: matched seed/camera/viewport, rendering enabled versus disabled, fixed quality then adaptive, dense core/diffuse outskirts/zoom path, report median/p95 full-frame latency and quality tiers. Measure rather than promise FPS. Adaptive quality cannot alter solver parameters or count.
7. Full configured GPU battery must pass. New targeted optical verification can be a standalone retained regression scene because optical ordering, conservation and toggle transitions defend plausible errors. Do not weaken existing verification material pins or numerical anchors.

Stop a GPU probe after a bounded timeout, preserve raw output and fix the actual failure before rerunning. A pretty frame does not replace buffer/optical checks. Store raw receipts under `_diag/observatory/`; report measured performance and limits in the final delivery.

## Planned physical-radiation extension

[Physical radiation: thermal state, material closures and spectral observation](physical_radiation_design.md)
defines the opt-in upgrade path: a one-way prescribed spectral preview, followed
by separately qualified engine-owned thermal/radiative dynamics. It preserves
this renderer's simulation-unit mode and read-only ownership. Its material,
unit and spectral interfaces allow later qualified Cassi derivations to replace
supplied optical laws. That document is a plan, not an implementation result.

The equation source is the completed
[conditional radiative-material closure](../../../CassiTheory/turbulence/cassi-radiative-material-closure.md).
Its tested source kernels and remaining material/moving-transport requirements
are carried into that implementation plan; no physical mode is enabled here.
