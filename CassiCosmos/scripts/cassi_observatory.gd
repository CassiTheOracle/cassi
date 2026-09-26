class_name CassiObservatory
extends RefCounted
## Read-only optical presentation. Scientific never allocates these GPU resources.
## The sim calls update only after its render snapshot has been recorded.

const PRESET_PATH := "user://observatory_appearance.cfg"
## Requested presentation default: emission 0.3 with auto exposure enabled. The
## meter follows the matter the active composition actually renders (empty frame
## regions never enter its average, and it holds its correction when nothing is
## lit), so the rendered level is stable across framing and brightness changes.
## The target luminance below sets that level deliberately. The world background
## ships off and is not directly exposure-scaled, so the frame is matter alone
## until it is enabled.
const DEFAULTS := {
	"style": 0, "exposure_ev": 0.0, "auto_exposure": true, "auto_exposure_target": 0.03,
	"optical_thickness": 1.0, "emission": 0.3, "scattering": 0.35,
	"point_fraction": 0.65, "bloom": 0.08, "temporal": true,
	"shutter_seconds": 0.0, "quality": 1, "adaptive_quality": true,
	"target_frame_ms": 20.0, "background": false, "view_depth": 0.0,
}
const SOURCE_DEFAULTS := {
	"observation_source": 0,
}
const SOURCE_NAMES: Array[String] = [
	"simulation_unit_optics",
	"prescribed_spectral_preview",
	"live_physical_matter",
]
const FLOAT_LIMITS := {
	"exposure_ev": Vector2(-12.0, 12.0), "auto_exposure_target": Vector2(0.01, 0.5),
	"optical_thickness": Vector2(0.0, 20.0),
	"emission": Vector2(0.0, 20.0), "scattering": Vector2(0.0, 1.0),
	"point_fraction": Vector2(0.0, 1.0), "bloom": Vector2(0.0, 1.0),
	"shutter_seconds": Vector2(0.0, 0.25), "target_frame_ms": Vector2(8.0, 100.0),
	"view_depth": Vector2(0.0, 5000.0),
}
const GRID_TIERS := [48, 64, 96, 128]
const IMAGE_HEIGHTS := [270, 360, 540, 1080]
const PHYSICAL_DISPLAY_BASELINE_EV := 4.0
const PHYSICAL_BACKGROUND_SCALE := 0.0625
## Outer fraction of an active view-depth window over which the particle layer
## fades out (0.85 = the last 15% of the window).
const DEPTH_FADE_FRACTION := 0.85

var _sim: Node3D
var _settings: Dictionary = DEFAULTS.duplicate()
var _source_settings: Dictionary = SOURCE_DEFAULTS.duplicate()
var _volume
var _post
var _camera: Camera3D
var _saved_environment: Environment
var _saved_compositor: Compositor
var _environment: Environment
var _compositor: Compositor
var _original_material: Material
var _particle_material: ShaderMaterial
var _particle_owner: MultiMeshInstance3D
var _original_visibility := true
var _hidden_layers: Dictionary = {}
var _active := false
var _active_source := -1
var _failed := false
var _source_epoch := 0
var _last_step := -1
var _last_time := 0.0
var _last_mode := -1
var _last_origin := Vector3.INF
var _last_camera_pose := Transform3D()
var _last_size := Vector2i.ZERO
var _history_invalid := true
var _quality_tier := 1
var _quality_requested := -1
var _overload_frames := 0
var _headroom_frames := 0
var _quality_changes := 0
var _frame_ms := 0.0
var _frames := 0
var _last_error := ""
var _frame: Dictionary = {}

func initialize(sim: Node3D) -> void:
	_sim = sim

func get_settings() -> Dictionary:
	var result: Dictionary = _settings.duplicate()
	result.merge(_source_settings, true)
	result["source_name"] = SOURCE_NAMES[int(_source_settings.observation_source)]
	return result


func get_source_settings() -> Dictionary:
	return _source_settings.duplicate()


func set_source_setting(key: String, value: Variant) -> bool:
	if not SOURCE_DEFAULTS.has(key) or not (value is int or value is float):
		return false
	var next: int = clampi(int(value), 0, SOURCE_NAMES.size() - 1)
	if int(_source_settings[key]) == next:
		return false
	_source_settings[key] = next
	_source_epoch += 1
	_history_invalid = true
	_failed = false
	_last_error = ""
	if _active:
		shutdown()
	return true

func set_style(style: int) -> void:
	style = clampi(style, 0, 2)
	if int(_settings.style) == style:
		return
	_settings.style = style
	if style > 0:
		_settings.bloom = 0.16 if style == 2 else 0.08
		_settings.shutter_seconds = 0.02 if style == 2 else 0.0
	_history_invalid = true
	_failed = false
	_last_error = ""

func set_setting(key: String, value: Variant) -> bool:
	if not _settings.has(key) or key == "style":
		return false
	var next: Variant
	if FLOAT_LIMITS.has(key):
		if not (value is float or value is int) or not is_finite(float(value)):
			return false
		var limits: Vector2 = FLOAT_LIMITS[key]
		next = clampf(float(value), limits.x, limits.y)
	elif key == "quality":
		if not (value is int or value is float):
			return false
		next = clampi(int(value), 0, 3)
	else:
		if not value is bool:
			return false
		next = value
	if _settings[key] == next:
		return false
	_settings[key] = next
	_history_invalid = true
	return true

func save_preset() -> Error:
	var config := ConfigFile.new()
	for key in _settings:
		config.set_value("appearance", key, _settings[key])
	return config.save(PRESET_PATH)

func load_preset() -> Error:
	var config := ConfigFile.new()
	var error := config.load(PRESET_PATH)
	if error != OK:
		return error
	# Style first: explicit saved values supersede preset defaults.
	var style_value: Variant = config.get_value("appearance", "style", 0)
	if not (style_value is int or style_value is float):
		return ERR_INVALID_DATA
	set_style(int(style_value))
	for key in DEFAULTS:
		if key != "style" and config.has_section_key("appearance", key):
			set_setting(key, config.get_value("appearance", key))
	return OK

func invalidate() -> void:
	# Drop bindings before the sim releases/replaces any borrowed buffers.
	shutdown()
	_source_epoch += 1
	_last_step = -1
	_last_mode = -1
	_last_origin = Vector3.INF
	_history_invalid = true
	_failed = false

func update(delta: float) -> void:
	if int(_settings.style) == 0:
		if _active or _volume != null:
			shutdown()
		return
	var source: int = int(_source_settings.observation_source)
	if _failed or not is_instance_valid(_sim):
		return
	var rd: RenderingDevice = _sim.get("_rd")
	if rd == null or not bool(_sim.get("_shaders_ready")) \
			or bool(_sim.get("_decoupled_boot_wait")):
		return
	var next_camera := _sim.get_viewport().get_camera_3d()
	if _active and (next_camera != _camera or source != _active_source):
		shutdown()
	_camera = next_camera
	if _camera == null:
		return
	if not _prepare_frame(delta):
		if source == 2:
			# A physical source that loses its publication must not leave the
			# last compositor frame active. Restore the ordinary renderer until
			# the physical volume can be rebuilt from a valid live state.
			if _active:
				shutdown()
			_show_base_particles()
		return
	if not _active and not _activate(rd, source):
		return
	if not bool(_volume.update(_frame, _settings)):
		_fail("Observation volume update failed; returning to Scientific rendering")
		return
	if source == 0:
		_apply_particle_material()
	else:
		_hide_layer(_sim.get("_mmi") as Node3D)
	_hide_legacy_layers()
	var post_settings: Dictionary = _settings.duplicate()
	post_settings["composition_kind"] = source
	if source == 2:
		# Raw XYZ stays in the physical observer's declared units. This is a
		# display-only baseline that makes the low-radiance H/H+ solution visible;
		# the user Exposure control remains a relative adjustment around it.
		post_settings["exposure_ev"] = clampf(
				float(_settings.exposure_ev) + PHYSICAL_DISPLAY_BASELINE_EV,
				-12.0, 12.0)
		post_settings["background_scale"] = PHYSICAL_BACKGROUND_SCALE
	_post.configure(_frame, post_settings, _volume.radiance, _volume.depth)
	_post.enabled = true
	_history_invalid = false
	_frames += 1

func _activate(rd: RenderingDevice, source: int) -> bool:
	var volume_path := "res://scripts/cassi_observatory_volume.gd"
	if source == 1:
		volume_path = "res://scripts/cassi_spectral_volume.gd"
	elif source == 2:
		volume_path = "res://scripts/cassi_physical_volume.gd"
	var volume_script: Script = load(volume_path)
	var post_script: Script = load("res://scripts/cassi_observatory_post.gd")
	var particle_shader: Shader = load(
			"res://shaders/particle_billboard_observatory.gdshader") \
			if source == 0 else null
	if volume_script == null or post_script == null \
			or (source == 0 and particle_shader == null):
		_fail("Observation resources could not be loaded")
		return false
	_volume = volume_script.new()
	_post = post_script.new()
	if not bool(_volume.initialize(rd)) or not bool(_post.initialize(rd)):
		_fail("Observation GPU pipeline initialization failed")
		return false
	if particle_shader != null:
		_particle_material = ShaderMaterial.new()
		_particle_material.shader = particle_shader
	_saved_environment = _camera.environment
	_saved_compositor = _camera.compositor
	var base_environment: Environment = _saved_environment
	var world_environment := _sim.get_parent().get_node_or_null("WorldEnvironment") as WorldEnvironment
	if base_environment == null and world_environment != null:
		base_environment = world_environment.environment
	_environment = base_environment.duplicate(true) if base_environment != null else Environment.new()
	_environment.background_mode = Environment.BG_COLOR
	_environment.background_color = Color.BLACK
	_environment.background_energy_multiplier = 1.0
	_environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	_environment.tonemap_exposure = 1.0
	_environment.glow_enabled = false
	_environment.fog_enabled = false
	_environment.volumetric_fog_enabled = false
	_camera.environment = _environment
	_compositor = Compositor.new()
	var effects: Array[CompositorEffect] = []
	if _saved_compositor != null:
		effects.assign(_saved_compositor.compositor_effects)
	elif world_environment != null and world_environment.compositor != null:
		effects.assign(world_environment.compositor.compositor_effects)
	effects.append(_post)
	_compositor.compositor_effects = effects
	_camera.compositor = _compositor
	_active = true
	_active_source = source
	print("[Observatory] HDR compositor active; source=%s" % SOURCE_NAMES[source])
	return true

func _prepare_frame(delta: float) -> bool:
	var positions: RID = _sim.get("_pos_render_buf")
	var velocities: RID = _sim.get("_vel_buf")
	var engine: Object = _sim.get("_physics_engine")
	var decoupled := bool(_sim.get("_decoupled_active"))
	var field_mode := int(_sim.get("mode")) == 1
	var optics := RID()
	var sites := 0
	var site_epoch := 0
	var reference_mass := float(_sim.get("_total_init_mass"))
	var origin: Vector3 = _sim.call("_render_window_origin")
	var window_center: Vector3 = _sim.get("_window_center")
	var extents: Vector3 = _sim.call("_extents")
	var site_offset := window_center - origin
	if decoupled:
		if engine == null or not bool(engine.call("setup_ready")):
			return false
		velocities = engine.get("_vel_buf")
		reference_mass = float(engine.get("_total_init_mass"))
		if field_mode:
			var topology: Dictionary = engine.call("topology_resources")
			if not bool(topology.get("topology_ready", false)):
				return false
			optics = topology.get("topology_optical_rid", RID())
			sites = int(topology.get("topology_site_count", 0))
			site_epoch = int(topology.get("topology_generation", 0))
			var topology_origin: Vector3 = topology.get(
					"topology_window_origin", window_center)
			site_offset = topology_origin - origin
			extents = topology.get("topology_window_extent", extents)
			var rd: RenderingDevice = _sim.get("_rd")
			var command_list := rd.compute_list_begin()
			engine.call("record_render_optics", command_list)
			rd.compute_list_end()
	var source := int(_source_settings.observation_source)
	var physical_resources: Dictionary = {}
	if source == 2:
		physical_resources = engine.call("physical_matter_render_resources") \
				if engine != null and engine.has_method("physical_matter_render_resources") else {}
		if not bool(physical_resources.get("ready", false)):
			_last_error = String(physical_resources.get(
					"error", "Live physical matter is not enabled or ready"))
			return false
		extents = physical_resources.get("extents", extents)
		window_center = physical_resources.get("center", window_center)
		site_offset = window_center - origin
	if not positions.is_valid() or not velocities.is_valid():
		return false
	var size := Vector2i(_sim.get_viewport().get_visible_rect().size)
	if size.x < 1 or size.y < 1:
		return false
	_select_quality(delta)
	var step := int(_sim.get("_step_count"))
	if step != _last_step or bool(_sim.get("playing")):
		_source_epoch += 1
		_last_step = step
	var mode := int(_sim.get("mode"))
	var time := float(_sim.get("_time"))
	var simulation_delta := maxf(time - _last_time, 0.0)
	_last_time = time
	var pose := _camera.global_transform
	var radius := maxf(float(_sim.get("cluster_radius")), 0.001)
	if mode != _last_mode or not origin.is_equal_approx(_last_origin) or size != _last_size:
		_history_invalid = true
	if _active and (pose.origin.distance_to(_last_camera_pose.origin) > radius * 0.3 \
			or pose.basis.z.dot(_last_camera_pose.basis.z) < 0.94):
		_history_invalid = true
	_last_camera_pose = pose
	_last_origin = origin
	_last_mode = mode
	_last_size = size
	var vertical_fov := _camera.fov
	if _camera.keep_aspect == Camera3D.KEEP_WIDTH:
		vertical_fov = rad_to_deg(2.0 * atan(tan(deg_to_rad(vertical_fov) * 0.5) * float(size.y) / float(size.x)))
	var center := window_center - origin
	var bounds := AABB(center - extents, extents * 2.0)
	var height := mini(int(IMAGE_HEIGHTS[_quality_tier]), size.y)
	var width := maxi(1, roundi(float(height) * float(size.x) / float(size.y)))
	var near_distance := maxf(_camera.near, 0.01)
	# The optical texture only needs the finite occupied domain. Sampling past
	# this far distance returns the complete column, including escaped points.
	var far_distance := maxf(near_distance * 2.0, pose.origin.distance_to(center) + extents.length() * 1.1)
	# View depth (world units, 0 = the whole occupied domain) is one ordered
	# window for both the optical column and the particle layer: a smaller value
	# shortens how far matter is visible and bounds how many layers stack along
	# a view ray. The volume stop and the billboard fade share this far distance.
	var view_depth := maxf(float(_settings.view_depth), 0.0)
	var depth_limited := view_depth > 0.0 and view_depth < far_distance
	if depth_limited:
		far_distance = maxf(view_depth, near_distance * 2.0)
	_frame = {
		"positions": positions, "velocities": velocities,
		"particle_count": int(_sim.get("N_particles")), "source_epoch": _source_epoch,
		"field_mode": field_mode, "optical_sites": optics, "site_count": sites,
		"site_epoch": site_epoch, "site_origin_offset": site_offset,
		"bounds": bounds, "camera_transform": pose, "world_origin": origin,
		"fov": vertical_fov, "viewport_size": size,
		"near": near_distance, "far": far_distance,
		"depth_fade_start": far_distance * DEPTH_FADE_FRACTION if depth_limited else 0.0,
		"reference_mass": maxf(reference_mass, 0.000001), "reference_radius": radius,
		"delta": maxf(delta, 0.0), "simulation_delta": simulation_delta,
		"playing": bool(_sim.get("playing")), "reset_history": _history_invalid,
		"grid_size": int(GRID_TIERS[_quality_tier]), "render_size": Vector2i(width, height),
		"field_grid_size": int(_sim.get("grid_N")),
		"field_ey": _sim.get("_field_pp_ey") if bool(_sim.get("_field_role_b")) else _sim.get("_field_ey"),
		"field_ei": _sim.get("_field_pp_ei") if bool(_sim.get("_field_role_b")) else _sim.get("_field_ei"),
		"field_extents": extents, "field_origin_offset": site_offset,
		"physical_resources": physical_resources,
		"physical_model_path": String(_sim.get("physical_matter_model_path")),
	}
	_frame["step"] = step
	_frame["time"] = time
	_frame["observation_source"] = int(_source_settings.observation_source)
	return true

func _select_quality(delta: float) -> void:
	var requested := int(_settings.quality)
	if delta > 0.0 and delta < 1.0:
		_frame_ms = delta * 1000.0 if _frame_ms <= 0.0 else lerpf(_frame_ms, delta * 1000.0, 0.06)
	var adaptive := bool(_settings.adaptive_quality) and requested != 3
	if requested != _quality_requested or not adaptive:
		_quality_tier = requested
		_quality_requested = requested
		_overload_frames = 0
		_headroom_frames = 0
		return
	# Whole rendered-frame interval includes the shared physics workload.
	# Ignore pauses in the application/window manager rather than treating a
	# multi-second focus change as evidence for a permanent quality reduction.
	if delta <= 0.0 or delta > 1.0:
		return
	var target := float(_settings.target_frame_ms)
	_overload_frames = _overload_frames + 1 if _frame_ms > target * 1.2 else 0
	_headroom_frames = _headroom_frames + 1 if _frame_ms < target * 0.72 else 0
	if _overload_frames >= 45 and _quality_tier > 0:
		_quality_tier -= 1
		_quality_changes += 1
		_overload_frames = 0
		_history_invalid = true
	elif _headroom_frames >= 240 and _quality_tier < requested:
		_quality_tier += 1
		_quality_changes += 1
		_headroom_frames = 0
		_history_invalid = true

func _bind_particle_material() -> MultiMeshInstance3D:
	var owner: MultiMeshInstance3D = _sim.get("_mmi")
	if owner == null or _particle_material == null:
		return null
	if owner != _particle_owner:
		_particle_owner = owner
		_original_material = owner.material_override
		_original_visibility = owner.visible
	owner.material_override = _particle_material
	owner.visible = not bool(_frame.field_mode)
	_particle_material.set_shader_parameter("size", 1.0)
	_particle_material.set_shader_parameter(
			"compact_mode", 1.0 if bool(_sim.get("compact_render_data")) else 0.0)
	_particle_material.set_shader_parameter(
			"compact_tex_width", float(_sim.get("_compact_render_width")))
	var compact: Texture2D = _sim.get("_compact_render_texture")
	if compact != null:
		_particle_material.set_shader_parameter("compact_data", compact)
	_particle_material.set_shader_parameter("viewport_height", float(_last_size.y))
	return owner


func _apply_particle_material() -> void:
	if _bind_particle_material() == null:
		return
	_particle_material.set_shader_parameter("optical_depth_texture", _volume.optical_depth)
	_particle_material.set_shader_parameter("motion_texture", _volume.motion)
	_particle_material.set_shader_parameter("motion_tex_width", float(_volume.motion.get_width()))
	_particle_material.set_shader_parameter("optical_near", float(_frame.near))
	_particle_material.set_shader_parameter("optical_far", float(_frame.far))
	_particle_material.set_shader_parameter(
			"depth_fade_start", float(_frame.get("depth_fade_start", 0.0)))
	_particle_material.set_shader_parameter("reference_radius", float(_frame.reference_radius))
	_particle_material.set_shader_parameter("optical_bounds_min", _frame.bounds.position)
	_particle_material.set_shader_parameter("optical_bounds_max", _frame.bounds.end)
	_particle_material.set_shader_parameter("luminosity_scale", 1.0 / float(_frame.reference_mass))
	_particle_material.set_shader_parameter("point_fraction", float(_settings.point_fraction))
	_particle_material.set_shader_parameter("emission_strength", float(_settings.emission))
	_particle_material.set_shader_parameter("shutter_seconds", float(_settings.shutter_seconds))
	# A paused state retains its velocities; still capture must preserve its
	# chosen shutter instead of silently replacing it with a zero exposure.
	_particle_material.set_shader_parameter("velocity_time_scale", float(_sim.get("sim_speed")))





func _show_base_particles() -> void:
	var owner: MultiMeshInstance3D = _sim.get("_mmi")
	if owner != null:
		owner.visible = int(_sim.get("mode")) != 1


func _hide_legacy_layers() -> void:
	for property in ["_macro_lod_mmi", "_trail_mmi", "_rotation_axis_mmi"]:
		var layer: Node3D = _sim.get(property)
		_hide_layer(layer)
	_hide_layer(_sim.get_parent().get_node_or_null("PresentationSky") as Node3D)

func _hide_layer(layer: Node3D) -> void:
	if layer == null:
		return
	if not _hidden_layers.has(layer):
		_hidden_layers[layer] = layer.visible
	layer.visible = false

func shutdown() -> void:
	if _post != null:
		_post.enabled = false
	if _active and is_instance_valid(_camera):
		_camera.compositor = _saved_compositor
		_camera.environment = _saved_environment
	if _post != null:
		_post.shutdown()
	if is_instance_valid(_particle_owner):
		_particle_owner.material_override = _original_material
		_particle_owner.visible = _original_visibility
	for layer in _hidden_layers:
		if is_instance_valid(layer):
			layer.visible = bool(_hidden_layers[layer])
	_hidden_layers.clear()
	_particle_material = null
	_original_material = null
	_particle_owner = null
	if _volume != null:
		_volume.shutdown()
	_volume = null
	_post = null
	_compositor = null
	_environment = null
	_saved_environment = null
	_saved_compositor = null
	_active = false
	_active_source = -1
	_history_invalid = true

func _fail(message: String) -> void:
	_last_error = message
	_failed = true
	shutdown()
	push_error("[Observatory] " + message)
	# Surface a failed renderer as Scientific, never an active-looking black
	# view or a silently substituted optical source.
	_sim.set_deferred("observatory_style", 0)

func statistics() -> Dictionary:
	var source: int = int(_source_settings.observation_source)
	var readiness := {
		"ready": not _failed,
		"enabled": true,
		"missing": [],
		"error": _last_error,
	}
	if source == 2:
		readiness = _physical_source_readiness()
	var particle_layer_kind := "none"
	if _active and source == 0:
		particle_layer_kind = "simulation_unit_optics"
	return {
		"active": _active, "style": int(_settings.style), "frames": _frames,
		"observation_source": source, "source_name": SOURCE_NAMES[source],
		"settings": get_settings(),
		"source_ready": _active and bool(readiness.get("ready", false)),
		"source_readiness": readiness,
		"particle_layer_kind": particle_layer_kind,
		"post_composition_kind": source,
		"quality_tier": _quality_tier, "quality_changes": _quality_changes,
		"frame_ms_ema": _frame_ms, "source_epoch": _source_epoch,
		"error": _last_error,
		"publication": _volume.publication_metadata() if _volume != null \
				and _volume.has_method("publication_metadata") else {},
		"volume": _volume.statistics() if _volume != null else {},
		"post": _post.statistics() if _post != null else {},
	}

func _physical_source_readiness() -> Dictionary:
	if not is_instance_valid(_sim):
		return {"ready": false, "enabled": false, "missing": ["simulation"], "error": ""}
	var engine: Object = _sim.get("_physics_engine")
	if engine == null or not engine.has_method("physical_matter_publication"):
		return {
			"ready": false,
			"enabled": bool(_sim.get("physical_matter_enabled")),
			"missing": ["live physical matter engine"],
			"error": "",
		}
	var result: Dictionary = engine.call("physical_matter_publication")
	result["missing"] = [] if bool(result.get("ready", false)) else [
		String(result.get("error", "live physical matter is initializing"))]
	return result


func capture_metadata() -> Dictionary:
	return statistics()


func capture_raw_xyz() -> Dictionary:
	if _active_source < 1 or _volume == null or not _volume.has_method("capture_raw_xyz"):
		return {"ok": false, "error": "raw XYZ requires an active spectral or physical source"}
	return _volume.capture_raw_xyz()

func capture_shape_target() -> Dictionary:
	if _volume == null:
		return {"ok": false, "error": "observation shape target is unavailable"}
	if _active_source == 0 and _volume.has_method("capture_shape_radiance"):
		return _volume.capture_shape_radiance()
	if _volume.has_method("capture_raw_xyz"):
		return _volume.capture_raw_xyz()
	return {"ok": false, "error": "active observation source has no shape target"}
