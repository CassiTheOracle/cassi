extends Node3D

# ═══════════════════════════════════════════════════════════════════════
# Background recording mode (Movie Maker batch job).
#
# Run via the console exe with --write-movie and a fixed fps; this scene
# owns the orbital camera, applies command-line overrides, and quits when
# the requested frame count is reached (Movie Maker finalizes the AVI on
# quit). No UI nodes: the video shows only the particles; progress goes
# to stdout.
#
# The camera frames the SPAWN REGION, not the origin: the orbit center is
# the cluster-centroid (mean of the cluster centers, mirroring
# cassi_sim.gd::_init_particles), and the default orbit radius is derived
# from the spawn extent (cluster-ring radius + per-cluster ball radius) so
# the startup frame shows the particles up close and dead-center — no
# hardcoded cluster position. `--orbit-radius` still pins the distance.
# ═══════════════════════════════════════════════════════════════════════

# ── Scene defaults ──
@export var record_frames: int = 900          # 30 s at 30 fps
@export var record_fps: int = 30
@export var orbit_radius: float = 150.0       # camera distance from the orbit target;
                                              # auto-framed from the spawn geometry unless --orbit-radius
@export var orbit_elevation: float = 0.35     # fixed height angle (rad)
@export var orbit_speed: float = 0.12         # rad/s around Y
@export var recording_size: Vector2i = Vector2i(1920, 1080)

var _cam: Camera3D
var _sim: Node3D
var _frame_count: int = 0
var _angle: float = 0.0
# Spawn-aware framing, set in _ready once the sim config is inherited: the
# orbit center is the cluster-centroid (NOT the origin), so single-cluster
# configs (spawn at (cluster_separation, 0, 0)) are framed dead-center too.
var _orbit_target: Vector3 = Vector3.ZERO
# --orbit-radius on the command line pins the distance; otherwise the default
# is derived from the spawn extent so the startup frame shows the particles.
var _orbit_radius_cli := false
# The sibling `PresentationDirector` node when present: a pose source that
# this recorder samples (the recorder remains the sole camera writer). Null
# (or a MANUAL director) keeps the fixed orbit below unchanged.
var _director: Node = null
var _director_requested: bool = false
# Presentation-only command-line overrides. These are applied after the
# inherited physics reinitialization and never trigger a reseed/reinit.
var _appearance_override: int = -1
var _observation_source_override: int = -1
var _exposure_override: float = NAN
var _quality_override: int = -1
var _capture_sidecar_path: String = ""
var _optics_override: String = ""


func _ready() -> void:
	# Children init before the root: CassiSim already ran its _ready with
	# the scene defaults. Grab it and the camera, then apply overrides.
	_cam = get_node("Camera3D") as Camera3D
	_sim = get_node("CassiSim")
	_cam.fov = 65.0
	_cam.near = 0.1
	_cam.far = 2000.0

	# Movie fps: the reliable mechanism is --fixed-fps N on the command
	# line -- main.cpp passes it straight to MovieWriter::begin() at engine
	# start (verified: AVI strh fps matches; a runtime
	# ProjectSettings.set_setting("movie_writer/fps", ...) is a no-op for
	# the recording because begin() already ran -- keep it only so the
	# scene arg and the project setting never disagree on bare runs). The
	# AVI RESOLUTION is likewise fixed at engine start from the project
	# settings display/window/size/viewport_width/height (the window size
	# and the width_override pair are ignored or DPI-scaled on Windows) --
	# record.ps1 patches project.godot's viewport settings for the run.
	if record_fps != int(ProjectSettings.get_setting("movie_writer/fps", 30)):
		ProjectSettings.set_setting("movie_writer/fps", record_fps)

	get_window().size = recording_size
	print("[Recorder] window size after apply: %dx%d (requested %dx%d)" % [
		get_window().size.x, get_window().size.y, recording_size.x, recording_size.y])

	# ── Inherit the current settings from scenes/main.tscn ──
	# The recorder no longer carries its own settings copy: whatever is
	# currently set on main.tscn's CassiSim node (editor edits are written
	# to the file) IS the config. Load the scene WITHOUT adding it to the
	# tree (no _ready, no GPU work), copy the curated properties, free it,
	# then reinit so the sim's _ready-time buffers match. The recorder
	# owns suppress_readbacks / max_steps_per_frame / playing itself.
	var reinit_needed := false
	var inherit_list := [
		"grid_N", "N_particles", "dt", "sim_speed", "xi", "softening", "particle_size",
		"cluster_radius", "num_clusters", "cluster_separation", "merger_speed",
		"source_strength", "qi_condensation_threshold", "bh_acc_rate",
		"bh_max_age", "black_holes_enabled", "gravity_mode", "realsim_drag", "realsim_viscosity",
		"realsim_friction", "river_calibrate_gn", "river_pi_ref",
		"river_q_ref", "field_attractor_init", "freeze_field", "initial_radius_fraction",
		"initial_condition", "initial_v_circ_factor", "box_aspect", "box_scale", "mode",
		"initial_arrangement", "initial_motion", "initial_speed", "initial_total_mass",
		"initial_shape_settings", "ic_seed",
		"presentation_profile", "presentation_color_scheme",
		"presentation_macro_lod_enabled", "presentation_macro_min_coherence",
		"presentation_lod_enter", "presentation_lod_exit",
		"presentation_trails_enabled", "presentation_trail_speed_threshold",
		"presentation_trail_shutter_seconds", "presentation_volume_history_enabled",
		"presentation_volume_history_weight", "presentation_volume_history_depth_tolerance",
		"observatory_style",
		"auto_frame_camera_on_start",
	]
	var main_scene := load("res://scenes/main.tscn")
	if main_scene != null:
		var inst = main_scene.instantiate()  # NOT added to the tree
		var src = inst.get_node_or_null("CassiSim")
		if src == null:
			push_warning("[Recorder] main.tscn has no CassiSim node — using script defaults")
		else:
			for p in inherit_list:
				var v = src.get(p)
				if v != null:
					_sim.set(p, v)
			reinit_needed = true
			print("[Recorder] inherited from main.tscn: grid=%d particles=%d grav=%d init=%d sep=%.1f" % [
				_sim.get("grid_N"), _sim.get("N_particles"), _sim.get("gravity_mode"),
				_sim.get("initial_condition"), _sim.get("cluster_separation")])
		inst.free()
	else:
		push_warning("[Recorder] main.tscn not readable — using script defaults")

	# ── Command-line overrides (args after `--`) ──
	for a in OS.get_cmdline_user_args():
		var kv := a.split("=", true, 1)
		if kv.size() != 2:
			continue
		match kv[0]:
			"--record-frames":
				record_frames = int(kv[1])
			"--record-fps":
				record_fps = int(kv[1])
				ProjectSettings.set_setting("movie_writer/fps", record_fps)
			"--grid":
				_sim.set("grid_N", int(kv[1]))
				reinit_needed = true
			"--particles":
				_sim.set("N_particles", int(kv[1]))
				reinit_needed = true
			"--gravity":
				_sim.set("gravity_mode", int(kv[1]))
				reinit_needed = true
			"--init":
				_sim.set("initial_condition", int(kv[1]))
				reinit_needed = true
			"--v-circ":
				# Rotational support factor of the IC (default 0.85):
				# v_tangential = factor·√(G·M_enc/r) about z; init-time.
				_sim.set("initial_v_circ_factor", float(kv[1]))
				reinit_needed = true
			"--freeze-field":
				# Diagnostic: freeze the two-fluid field after init (skip
				# the PDE passes; gravity/particle path unchanged).
				_sim.set("freeze_field", int(kv[1]) != 0)
			"--aspect":
				# Per-axis box aspect x,y,z (e.g. 1.618,1,2.618 for the
				# φ-aspect box — GRID_LAYOUT.md); init-time, needs reinit.
				var parts := (kv[1] as String).split(",")
				if parts.size() == 3:
					_sim.set("box_aspect", Vector3(parts[0].to_float(), parts[1].to_float(), parts[2].to_float()))
					reinit_needed = true
				else:
					push_warning("[Recorder] --aspect needs x,y,z (e.g. 1.618,1,2.618)")
			"--box-scale":
				# Uniform box rescale: extent_i = box_scale·aspect_i·1.5·
				# cluster_radius. Separates the cluster from its periodic
				# images (image forces drop like 1/(3·box_scale−1)²) while
				# keeping the aspect; 1.0 = legacy. Init-time, needs reinit.
				_sim.set("box_scale", float(kv[1]))
				reinit_needed = true
			"--bhs":
				# BH toggle: live export set, no reinit needed (the host
				# re-encodes bh[3].x next frame).
				_sim.set("black_holes_enabled", int(kv[1]) != 0)
			"--color":
				# Particle color packed mode: low nibble base 0..6, high
				# nibble VFX flags 0x10/0x20/0x40. Live; --color 5/6
				# use vertex colors and are not band-fit/LUT modes.
				var cm := int(kv[1])
				if cm >= 0 and cm <= 118:
					_sim.set("particle_color_mode", cm)
					if _sim.has_method("refresh_lut_format"):
						_sim.call("refresh_lut_format")
				else:
					push_warning("[Recorder] --color needs packed mode 0..6 + flags 0x10/0x20/0x40")
			"--rainbow-count":
				# Rainbow passes over the cycle band: 0 = AUTO (mode 3 → 2,
				# else 1), explicit 1-8. Live — no reinit.
				var rc := int(kv[1])
				if rc >= 0 and rc <= 8:
					_sim.set("rainbow_count", rc)
				else:
					push_warning("[Recorder] --rainbow-count needs 0..8")
			"--grad-ranges":
				# Cycle band lo,hi for the ACTIVE source (mode >= 2 → Qi,
				# else velocity); live, no reinit. 0 < lo < hi validated.
				_apply_grad_pair("--grad-ranges", kv[1], "cycle")
			"--grad-pinch":
				_apply_grad_pair("--grad-pinch", kv[1], "pinch")
			"--grad-shares":
				# Per-segment hue shares a,b,c (lo, pinch, hi) for the
				# active source; the engine clamps >= 0 and normalizes.
				var parts3 := (kv[1] as String).split(",")
				if parts3.size() == 3:
					var sh := Vector3(parts3[0].to_float(), parts3[1].to_float(), parts3[2].to_float())
					if sh.x >= 0.0 and sh.y >= 0.0 and sh.z >= 0.0 and sh.x + sh.y + sh.z > 0.0:
						_sim.set("color_shares", sh)
					else:
						push_warning("[Recorder] --grad-shares needs a,b,c >= 0 with a positive sum")
				else:
					push_warning("[Recorder] --grad-shares needs a,b,c")
			"--grad-offset":
				# Cycle-start hue rotation (radians-ish -1..1; rotates the
				# start hue). Live — no reinit.
				var off := kv[1].to_float()
				if is_finite(off):
					_sim.set("color_hue_offset", off)
				else:
					push_warning("[Recorder] --grad-offset needs a number")
			"--steps":
				_sim.set("max_steps_per_frame", int(kv[1]))
			"--orbit-speed":
				orbit_speed = float(kv[1])
			"--orbit-radius":
				orbit_radius = float(kv[1])
				_orbit_radius_cli = true
			"--presentation-director":
				_director_requested = int(kv[1]) != 0
			"--appearance":
				_appearance_override = _parse_appearance(kv[1])
			"--observation-source":
				_observation_source_override = _parse_observation_source(kv[1])
			"--exposure":
				if kv[1].is_valid_float():
					_exposure_override = kv[1].to_float()
				else:
					push_warning("[Recorder] --exposure needs a finite number")
			"--quality":
				if kv[1].is_valid_int():
					_quality_override = clampi(int(kv[1]), 0, 3)
				else:
					push_warning("[Recorder] --quality needs an integer 0..3")
			"--optics":
				_optics_override = kv[1]
			"--capture-sidecar":
				_capture_sidecar_path = kv[1]

	# ── Spawn-aware camera framing ──
	# Aim the orbit at the actual spawn region and frame it: the default
	# radius is the spawn extent (cluster-ring radius + the per-cluster
	# ball radius), so the region fills most of the frame. --orbit-radius
	# overrides it.
	if not _orbit_radius_cli:
		orbit_radius = _framing_radius()
	_orbit_target = _spawn_centroid()
	_apply_camera_pose()
	_director = _find_director()
	if _director_requested and _director != null and _director.has_method("set_recorder_directing"):
		if _director.has_method("configure_recorder_orbit"):
			_director.call("configure_recorder_orbit",
				_orbit_target, orbit_radius, orbit_elevation, orbit_speed)

		_director.call("set_recorder_directing")

	# The sim already ran _ready with script defaults; reinit applies the
	# inherited settings + CLI overrides (fresh buffers/field/particles at
	# the new sizes).
	if reinit_needed:
		_sim.call("reinit")
	# Presentation settings are live renderer inputs: applying them here does
	# not reseed particles or call reinit, so a movie appearance override
	# cannot perturb the inherited scientific state.
	_apply_presentation_overrides()

	print("[Recorder] frames=%d fps=%d size=%dx%d grid=%d particles=%d grav=%d init=%d steps=%d orbit=%.2f rad/s cam_r=%.1f target=(%.0f, %.0f, %.0f)" % [
		record_frames, record_fps, recording_size.x, recording_size.y,
		_sim.get("grid_N"), _sim.get("N_particles"), _sim.get("gravity_mode"),
		_sim.get("initial_condition"), _sim.get("max_steps_per_frame"), orbit_speed,
		orbit_radius, _orbit_target.x, _orbit_target.y, _orbit_target.z])


func _parse_appearance(value: String) -> int:
	match value.to_lower():
		"scientific", "0":
			return 0
		"observatory", "1":
			return 1
		"cinematic", "2":
			return 2
		_:
			push_warning("[Recorder] --appearance must be scientific, observatory, or cinematic")
			return -1

func _parse_observation_source(value: String) -> int:
	match value.to_lower():
		"simulation", "simulation-unit", "0":
			return 0
		"spectral", "prescribed", "1":
			return 1
		"coupled", "physical", "2":
			return 2
		_:
			push_warning("[Recorder] --observation-source must be simulation, spectral, or coupled")
			return -1


func _set_observatory_setting(key: String, value: Variant) -> void:
	if _sim.has_method("set_observatory_setting"):
		_sim.call("set_observatory_setting", key, value)
	else:
		push_warning("[Recorder] CassiSim has no set_observatory_setting; ignored %s" % key)


func _apply_presentation_overrides() -> void:
	if _observation_source_override >= 0:
		if _sim.has_method("set_observatory_source"):
			_sim.call("set_observatory_source", _observation_source_override)
		else:
			push_warning("[Recorder] CassiSim has no set_observatory_source")
	if _appearance_override >= 0:
		if _sim.has_method("set_observatory_style"):
			_sim.call("set_observatory_style", _appearance_override)
		else:
			push_warning("[Recorder] CassiSim has no set_observatory_style")
	if is_finite(_exposure_override):
		_set_observatory_setting("exposure_ev", _exposure_override)
	if _quality_override >= 0:
		_set_observatory_setting("quality", _quality_override)
		_set_observatory_setting("adaptive_quality", false)
	if not _optics_override.is_empty():
		_apply_optics_override(_optics_override)


func _apply_optics_override(spec: String) -> void:
	# Accept either a bare optical thickness or comma-separated key=value
	# pairs, e.g. thickness=1.4,emission=1.1,scattering=0.35,bloom=0.08,depth=300.
	var fields := spec.split(",", false)
	for field in fields:
		var pair := field.split("=", true, 1)
		if pair.size() == 1:
			if pair[0].is_valid_float():
				var thickness := pair[0].to_float()
				if is_finite(thickness):
					_set_observatory_setting("optical_thickness", thickness)
			else:
				push_warning("[Recorder] ignored malformed optics field: %s" % field)
			continue
		var key := pair[0].strip_edges().to_lower()
		var value := pair[1].to_float()
		if not is_finite(value):
			push_warning("[Recorder] ignored non-finite optics value: %s" % field)
			continue
		match key:
			"thickness", "optical_thickness":
				_set_observatory_setting("optical_thickness", value)
			"emission":
				_set_observatory_setting("emission", value)
			"scattering":
				_set_observatory_setting("scattering", value)
			"point", "point_fraction":
				_set_observatory_setting("point_fraction", value)
			"bloom":
				_set_observatory_setting("bloom", value)
			"shutter", "shutter_seconds":
				_set_observatory_setting("shutter_seconds", value)
			"depth", "view_depth":
				_set_observatory_setting("view_depth", value)
			_:
				push_warning("[Recorder] unknown optics key: %s" % pair[0])


## Apply a --grad-* lo,hi pair to the ACTIVE source's band export (mode
## >= 2 → Qi, else velocity), with 0 < lo < hi validation. Live exports —
## no reinit. The pair applies to whichever source --color selected; set
## --color before the --grad-* flags.
func _apply_grad_pair(flag: String, value: String, kind: String) -> void:
	var parts := (value as String).split(",")
	if parts.size() != 2:
		push_warning("[Recorder] %s needs lo,hi (got %s)" % [flag, value])
		return
	var lo := parts[0].to_float()
	var hi := parts[1].to_float()
	if not (is_finite(lo) and is_finite(hi)) or not (lo > 0.0 and lo < hi):
		push_warning("[Recorder] %s needs 0 < lo < hi (got %s)" % [flag, value])
		return
	var base := int(_sim.get("particle_color_mode")) & 0xF
	if base < 1 or base > 4:
		push_warning("[Recorder] %s ignored for packed color base %d (only bases 1-4 use band fitting)" % [flag, base])
		return
	if base >= 2:
		if kind == "cycle":
			_sim.set("qi_cycle", Vector2(lo, hi))
		else:
			_sim.set("qi_pinch", Vector2(lo, hi))
	else:
		if kind == "cycle":
			_sim.set("velocity_cycle", Vector2(lo, hi))
		else:
			_sim.set("velocity_pinch", Vector2(lo, hi))


## Use the simulation's explicit arrangement and generated support bounds.
func _spawn_centroid() -> Vector3:
	return _sim.call("_cluster_centroid")


func _framing_radius() -> float:
	return float(_sim.call("_camera_framing_radius"))


## Place the camera at the current orbit angle around the spawn centroid.
func _apply_camera_pose() -> void:
	var e := orbit_elevation
	_cam.position = _orbit_target + Vector3(
		orbit_radius * cos(_angle) * cos(e),
		orbit_radius * sin(e),
		orbit_radius * sin(_angle) * cos(e))
	_cam.look_at(_orbit_target, Vector3.UP)


# ---------------------------------------------------------------------------
# Director sampling (presentation director; all no-ops when absent)
# ---------------------------------------------------------------------------

## The sibling `PresentationDirector` node, if present. Cached once at
## _ready and re-resolved lazily so a director added later is honored.
func _find_director() -> Node:
	return get_node_or_null("PresentationDirector")


## The cached director ref, re-resolved when missing or freed.
func _current_director() -> Node:
	if not is_instance_valid(_director):
		_director = _find_director()
	return _director


func _process(delta: float) -> void:
	# While a director is present and directing, it is the pose source; the
	# recorder stays the sole camera writer and applies the sampled pose.
	# Without a director (or in MANUAL) the fixed orbit below is unchanged.
	var director := _current_director()
	if director != null and director.has_method("is_directing") and director.call("is_directing"):
		var pose: Transform3D = director.call("sample_pose", delta, _cam)
		_cam.global_transform = pose
	else:
		_angle += orbit_speed * delta
		_apply_camera_pose()

	_frame_count += 1
	if _frame_count % 30 == 0 or _frame_count == record_frames:
		var sim_t := float(_sim.get("_time"))
		print("[Recorder] frame %d/%d (sim t=%.2f)" % [_frame_count, record_frames, sim_t])

	if _frame_count >= record_frames:
		_write_movie_sidecar()
		print("[Recorder] done")
		get_tree().quit(0)

func _write_movie_sidecar() -> void:
	if _capture_sidecar_path.is_empty():
		return
	var observation: Dictionary = {}
	if _sim.has_method("get_observation_capture_metadata"):
		var value: Variant = _sim.call("get_observation_capture_metadata")
		if value is Dictionary:
			observation = value
	var transform: Transform3D = _cam.global_transform
	var metadata: Dictionary = _json_safe({
		"schema_version": "1.0.0",
		"capture_kind": "movie",
		"frames": _frame_count,
		"fps": record_fps,
		"actual_width": int(ProjectSettings.get_setting(
				"display/window/size/viewport_width", recording_size.x)),
		"actual_height": int(ProjectSettings.get_setting(
				"display/window/size/viewport_height", recording_size.y)),
		"executed_step": int(_sim.get("_step_count")),
		"simulation_time": float(_sim.get("_time")),
		"camera": {
			"origin": transform.origin,
			"basis": transform.basis,
			"fov_degrees": _cam.fov,
			"near": _cam.near,
			"far": _cam.far,
		},
		"source": observation,
	})
	var file := FileAccess.open(_capture_sidecar_path, FileAccess.WRITE)
	if file == null:
		push_error("[Recorder] cannot write capture sidecar: " + _capture_sidecar_path)
		return
	file.store_string(JSON.stringify(metadata, "\t") + "\n")
	file.close()


func _json_safe(value: Variant) -> Variant:
	if value is Dictionary:
		var mapped := {}
		for key: Variant in value:
			mapped[str(key)] = _json_safe(value[key])
		return mapped
	if value is Array:
		var mapped := []
		for child: Variant in value:
			mapped.append(_json_safe(child))
		return mapped
	if value is Vector2:
		return [value.x, value.y]
	if value is Vector2i:
		return [value.x, value.y]
	if value is Vector3:
		return [value.x, value.y, value.z]
	if value is Basis:
		return [
			value.x.x, value.x.y, value.x.z,
			value.y.x, value.y.y, value.y.z,
			value.z.x, value.z.y, value.z.z,
		]
	if value is AABB:
		return {"position": _json_safe(value.position), "size": _json_safe(value.size)}
	return value
