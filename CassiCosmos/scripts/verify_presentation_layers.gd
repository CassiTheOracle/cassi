extends Node
## Presentation-layer integration verifier.
##
## Exercises the real windowed global-RD path used by the interactive and
## recorder scenes. It proves that the opt-in profile owns separate renderer
## resources only, emits finite macro-site and velocity-ribbon records, drives
## the true site-volume history path, and releases those resources when the
## associated visual toggles turn off. Solver state is never changed by a
## presentation check.

var sim: Node3D
var camera: Camera3D
var sky: MeshInstance3D
var _checks: int = 0
var _failures: int = 0

const BOOT_TIMEOUT_FRAMES := 1800
const LAYER_TIMEOUT_FRAMES := 900


func _ready() -> void:
	sim = get_node_or_null("../CassiSim") as Node3D
	camera = get_node_or_null("../Camera3D") as Camera3D
	sky = get_node_or_null("../PresentationSky") as MeshInstance3D
	if sim == null or camera == null or sky == null:
		push_error("verify_presentation_layers: scene is missing CassiSim, Camera3D, or PresentationSky")
		get_tree().quit(1)
		return
	await _run()
	print("══════ PRESENTATION RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)


func _run() -> void:
	# The decoupled engine boot advances only through real rendered frames.
	sim.playing = true
	var booted := false
	for _frame in range(BOOT_TIMEOUT_FRAMES):
		await get_tree().process_frame
		if _is_booted():
			booted = true
			break
	_check("decoupled boxless renderer booted", booted)
	if not booted:
		return
	# Saved operator color defaults load after the scene pins. Force the
	# compatibility depth-fade flag here so the far-view regression cannot be
	# accidentally weakened by user:// state.
	sim.particle_color_mode = 2 | 0x40
	await get_tree().process_frame
	await get_tree().process_frame
	# Prove the base particle layer at a distant oblique view before optional
	# macro/ribbon layers exist, so those layers cannot mask a culling failure.
	await _check_sky_follows_camera()
	_check_particle_profile()

	# Boot against the ordinary particle path first. The optional layers are
	# then activated live, which proves their allocation never participates in
	# the decoupled engine's startup dependency chain.
	sim.presentation_macro_lod_enabled = true
	sim.presentation_trails_enabled = true
	# Give the normal render sequence time to publish the query and write both
	# presentation MultiMeshes after their lazily created uniform sets exist.
	var layers_ready := false
	for _frame in range(LAYER_TIMEOUT_FRAMES):
		await get_tree().process_frame
		if _layers_ready():
			layers_ready = true
			break
	_check("macro and trail layers allocated on demand", layers_ready)
	if not layers_ready:
		return

	await _check_macro_records()
	_check_trail_records()
	await _capture_presentation_frame_if_requested()
	await _optional_particle_hold()
	await _check_volume_history()
	await _check_spectrum_volume_parity()
	await _check_opt_out_cleanup()

## Optional manual visual hold used by the windowed smoke check. The regular
## verifier has no hold argument and retains its fast deterministic exit.
func _optional_particle_hold() -> void:
	for arg in OS.get_cmdline_user_args():
		if not arg.begins_with("--hold-particle="):
			continue
		var seconds := clampf(arg.trim_prefix("--hold-particle=").to_float(), 0.0, 60.0)
		if seconds > 0.0:
			print("[Presentation] holding particle view for %.1f s" % seconds)
			await get_tree().create_timer(seconds).timeout
		return


## Explicit capture mode keeps the regular verifier artifact-free while
## allowing visual inspection of the actual renderer output in CI/smoke runs.
func _capture_presentation_frame_if_requested() -> void:
	if not OS.get_cmdline_user_args().has("--capture-presentation"):
		return
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var path := "res://_diag/presentation_layers_smoke.png"
	var err := image.save_png(path)
	if err != OK:
		push_error("[Presentation] failed to capture smoke frame (%d)" % err)
	else:
		print("[Presentation] captured smoke frame: ", path)


func _is_booted() -> bool:
	if not bool(sim.get("_decoupled_active")) or bool(sim.get("_decoupled_boot_wait")):
		return false
	if not bool(sim.get("_shaders_ready")):
		return false
	var engine: Object = sim.get("_physics_engine")
	return engine != null and bool(engine.get("_setup_done")) and bool(engine.get("_setup_compute_done")) \
			and bool(engine.get("_ml_ready")) and bool(engine.get("_meshless_query_ready"))


func _layers_ready() -> bool:
	var macro_mmi: MultiMeshInstance3D = sim.get("_macro_lod_mmi")
	var trail_mmi: MultiMeshInstance3D = sim.get("_trail_mmi")
	var macro_set: RID = sim.get("_us_macro_lod_0")
	var trail_set: RID = sim.get("_us_trail_0_dc")
	return macro_mmi != null and is_instance_valid(macro_mmi) and macro_mmi.visible \
			and trail_mmi != null and is_instance_valid(trail_mmi) and trail_mmi.visible \
			and macro_set.is_valid() and trail_set.is_valid()


func _check_sky_follows_camera() -> void:
	await get_tree().process_frame
	var original_transform: Transform3D = camera.global_transform
	var initial_match := sky.global_position.distance_to(camera.global_position) < 1e-3
	camera.global_position += Vector3(3.0, 0.0, -2.0)
	await get_tree().process_frame
	var moved_match := sky.global_position.distance_to(camera.global_position) < 1e-3
	_check("procedural sky follows the active camera", initial_match and moved_match)

	var base_far: float = camera.far
	var cloud_center: Vector3 = sim.get("_window_center")
	var extreme_distance := maxf(base_far * 1.1, 20_000_000.0)
	camera.global_position = cloud_center + Vector3(1.0, 0.1, 0.0).normalized() * extreme_distance
	camera.look_at(cloud_center, Vector3.UP)
	await get_tree().process_frame
	await get_tree().process_frame
	var cloud_radius: float = sim._extents().length() * 1.25
	var needed_far: float = camera.global_position.distance_to(cloud_center) + cloud_radius
	_check("camera projection stays finite at extreme presentation distance",
			is_finite(camera.far) and camera.far > base_far and camera.far <= 1_000_001.0)
	_check("extreme particle view extends beyond the finite camera plane",
			needed_far > camera.far)

	var mm: MultiMesh = sim.get("_mm")
	var camera_render_position: Vector3 = camera.global_position - sim._render_window_origin()
	var cull_box := mm.custom_aabb if mm != null else AABB()
	var min_half_extent := minf(minf(cull_box.size.x, cull_box.size.y), cull_box.size.z) * 0.5
	_check("particle cull volume follows distant camera angles",
			mm != null and cull_box.has_point(camera_render_position)
			and cull_box.get_center().distance_to(camera_render_position) <= 1.0
			and min_half_extent >= camera.far)

	# With the scene's compatibility depth-fade flag enabled, only the
	# presentation shader's range-owned alpha can leave these particles visible.
	# Hide the procedural stars so one bright central pixel proves the particle
	# MultiMesh reached the rasterizer at this distant oblique view.
	sky.visible = false
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var peak := _central_rgb_peak(image, 48)
	_check("presentation particles remain visible at distant camera angles", peak > 0.08)

	# The production scene carries millions of particles, so its count-scaled
	# source contribution is much lower than this focused arm's. Exercise that
	# real opacity at the mid-range where motes are sparse enough not to hide a
	# perceptual fade through aggregate overdraw.
	var mmi: MultiMeshInstance3D = sim.get("_mmi")
	var material := mmi.material_override as ShaderMaterial if mmi != null else null
	var material_opacity := 0.0
	var material_distant_opacity := 0.0
	var production_opacity: float = sim._effective_presentation_particle_opacity(2_500_100)
	var production_distant_opacity := minf(production_opacity * 2.0, 0.04)
	if material != null:
		material_opacity = float(material.get_shader_parameter("stack_opacity"))
		material_distant_opacity = float(material.get_shader_parameter("distant_opacity"))
		material.set_shader_parameter("stack_opacity", production_opacity)
		material.set_shader_parameter("distant_opacity", production_distant_opacity)
	camera.global_position = cloud_center + Vector3(0.0, 0.0, 600.0)
	camera.look_at(cloud_center, Vector3.UP)
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	var production_image := get_viewport().get_texture().get_image()
	var production_peak := _central_rgb_peak(production_image, 96)
	if material != null:
		material.set_shader_parameter("stack_opacity", material_opacity)
		material.set_shader_parameter("distant_opacity", material_distant_opacity)
	sky.visible = true
	print("[Presentation] production-density retreat stack=%.5f distant=%.5f peak=%.5f" % [
			production_opacity, production_distant_opacity, production_peak])
	_check("production-density particles remain visible after camera retreat",
			material != null and production_peak > 0.04)

	camera.global_transform = original_transform
	await get_tree().process_frame
	await get_tree().process_frame
	var radius := sky.scale.x
	_check("procedural sky remains inside camera far plane", radius > 0.0 and radius < camera.far)

func _central_rgb_peak(image: Image, radius: int) -> float:
	if image.is_empty():
		return 0.0
	var center := Vector2i(image.get_width() / 2, image.get_height() / 2)
	var peak := 0.0
	for y in range(maxi(center.y - radius, 0), mini(center.y + radius + 1, image.get_height())):
		for x in range(maxi(center.x - radius, 0), mini(center.x + radius + 1, image.get_width())):
			var pixel := image.get_pixel(x, y)
			peak = maxf(peak, maxf(pixel.r, maxf(pixel.g, pixel.b)))
	return peak

func _check_particle_profile() -> void:
	var mmi: MultiMeshInstance3D = sim.get("_mmi")
	var material := mmi.material_override as ShaderMaterial if mmi != null else null
	var expected := load("res://shaders/particle_billboard_presentation.gdshader") as Shader
	_check("particle presentation shader is selected", material != null and material.shader == expected)
	if material == null:
		_check("particle stack opacity is density-normalized", false)
		_check("particle stack opacity updates live", false)
		return
	var configured_opacity: float = sim.presentation_particle_opacity
	var effective_opacity: float = sim._effective_presentation_particle_opacity()
	var material_opacity := float(material.get_shader_parameter("stack_opacity"))
	_check("particle stack opacity is density-normalized",
			material_opacity > 0.0 and material_opacity <= configured_opacity
			and is_equal_approx(material_opacity, effective_opacity))
	var material_max_radius := float(material.get_shader_parameter("max_pixel_radius"))
	var dense_max_radius: float = sim._effective_presentation_max_pixel_radius(10_000_000)
	_check("particle radius cap contracts at production density",
			is_equal_approx(material_max_radius, sim._effective_presentation_max_pixel_radius())
			and dense_max_radius <= 2.0 and dense_max_radius < material_max_radius)
	sim.presentation_particle_opacity = configured_opacity * 0.5
	var changed_opacity := float(material.get_shader_parameter("stack_opacity"))
	_check("particle stack opacity updates live",
			changed_opacity > 0.0 and changed_opacity < material_opacity
			and is_equal_approx(changed_opacity, sim._effective_presentation_particle_opacity()))
	sim.presentation_particle_opacity = configured_opacity



func _check_macro_records() -> void:
	var mm: MultiMesh = sim.get("_macro_lod_mm")
	var rid: RID = sim.get("_macro_lod_rd_rid")
	if mm == null or not rid.is_valid():
		_check("macro-site records are finite and populated", false)
		return
	# Topology is published by a worker after the renderer's normal query.
	# Wait for that publication rather than reading a just-allocated all-zero
	# MultiMesh buffer and incorrectly treating the asynchronous handoff as a
	# failed macro pass.
	var topology_ready := false
	for _frame in range(180):
		await get_tree().process_frame
		var engine: Object = sim.get("_physics_engine")
		if engine != null and bool(engine.get("_topology_ready")):
			topology_ready = true
			break
	if topology_ready:
		await get_tree().process_frame
		await get_tree().process_frame
	var data: PackedFloat32Array = sim._rd.buffer_get_data(rid, 0, mm.instance_count * 64).to_float32_array()
	var finite := data.size() >= mm.instance_count * 16
	var valid := 0
	if finite:
		for i in range(mm.instance_count):
			var base := i * 16
			for j in range(16):
				if not is_finite(data[base + j]):
					finite = false
					break
			if data[base + 15] > 0.5:
				valid += 1
	_check("macro-site records are finite and populated", topology_ready and finite and valid > 0)

func _check_trail_records() -> void:
	var mm: MultiMesh = sim.get("_trail_mm")
	var rid: RID = sim.get("_trail_rd_rid")
	if mm == null or not rid.is_valid():
		_check("velocity-ribbon records are finite and populated", false)
		return
	var data: PackedFloat32Array = sim._rd.buffer_get_data(rid, 0, mm.instance_count * 64).to_float32_array()
	var finite := data.size() >= mm.instance_count * 16
	var valid := 0
	if finite:
		for i in range(mm.instance_count):
			var base := i * 16
			for j in range(16):
				if not is_finite(data[base + j]):
					finite = false
					break
			if data[base + 15] > 0.5:
				valid += 1
	_check("velocity-ribbon records are finite and populated", finite and valid > 0)


func _check_volume_history() -> void:
	# Allocation happens in _process independently of simulation stepping.
	# Wait for the actual producer rather than assuming a fixed number of
	# frames between the async topology handoff and its global-RD uniforms.
	sim.presentation_volume_history_enabled = true
	sim.mode = 1
	sim.playing = false
	sim._invalidate_volume_render_cache()
	var before_dispatch: int = int(sim.get("_volume_dispatch_id"))
	var first_resolved := false
	for _frame in range(LAYER_TIMEOUT_FRAMES):
		if bool(sim._render_site_volume_history()):
			first_resolved = true
			if int(sim.get("_volume_dispatch_id")) > before_dispatch:
				break
		await get_tree().process_frame
	var after_first_dispatch: int = int(sim.get("_volume_dispatch_id"))
	var before_second_skip: int = int(sim.get("_volume_skip_count"))
	var second_resolved: bool = bool(sim._render_site_volume_history())
	var after_second_dispatch: int = int(sim.get("_volume_dispatch_id"))
	var after_second_skip: int = int(sim.get("_volume_skip_count"))
	var state: RID = sim.get("_volume_history_state")
	var active := first_resolved and second_resolved \
			and after_first_dispatch > before_dispatch \
			and state.is_valid() and bool(sim.get("_volume_history_has_state"))
	var cache_reused := active and after_second_dispatch == after_first_dispatch \
			and after_second_skip == before_second_skip + 1
	_check("site-volume temporal reprojection allocates and resolves", active)
	_check("static site-volume history reuses its resolved image", cache_reused)
	if active:
		var output: RID = sim.get("_field_render_tex")
		_check("site-volume history preserves the shared output seam", output.is_valid() and sim.field_display_texture is Texture2DRD)

func _check_spectrum_volume_parity() -> void:
	# The current-only and history producers must share the Spectrum palette.
	# Freeze the source state, render one image through each path, and compare
	# a bounded sample of their resolved rgba32f output.
	var saved_scheme: int = sim.presentation_color_scheme
	sim.presentation_color_scheme = 1
	sim.presentation_volume_history_enabled = false
	sim._sync_presentation_volume_history()
	sim._invalidate_volume_render_cache()
	var current_before: int = int(sim.get("_volume_dispatch_id"))
	var current_rendered := false
	for _frame in range(LAYER_TIMEOUT_FRAMES):
		sim._render_site_volume()
		if int(sim.get("_volume_dispatch_id")) > current_before \
				and is_equal_approx(float(sim.get("_volume_last_scheduling")), 0.0):
			current_rendered = true
			break
		await get_tree().process_frame
	await get_tree().process_frame
	var output: RID = sim.get("_field_render_tex")
	var current := PackedFloat32Array()
	if current_rendered and output.is_valid():
		current = sim._rd.texture_get_data(output, 0).to_float32_array()
	sim.presentation_volume_history_enabled = true
	sim._invalidate_volume_render_cache()
	var history_before: int = int(sim.get("_volume_dispatch_id"))
	var history_rendered := false
	for _frame in range(LAYER_TIMEOUT_FRAMES):
		if bool(sim._render_site_volume_history()) \
				and int(sim.get("_volume_dispatch_id")) > history_before:
			history_rendered = true
			break
		await get_tree().process_frame
	await get_tree().process_frame
	var history := PackedFloat32Array()
	if history_rendered and output.is_valid():
		history = sim._rd.texture_get_data(output, 0).to_float32_array()
	var parity := current_rendered and history_rendered \
			and current.size() == history.size() and not current.is_empty()
	var visible_energy := 0.0
	var max_delta := 0.0
	if parity:
		var stride: int = maxi(4, int(current.size() / 16384) * 4)
		for i in range(0, current.size() - 3, stride):
			visible_energy = maxf(visible_energy, maxf(absf(current[i]), maxf(absf(current[i + 1]), absf(current[i + 2]))))
			for channel in range(4):
				max_delta = maxf(max_delta, absf(current[i + channel] - history[i + channel]))
		parity = visible_energy > 1e-6 and max_delta <= 2e-5
	_check("Spectrum volume palette matches with and without history", parity)
	sim.presentation_color_scheme = saved_scheme
	sim._invalidate_volume_render_cache()

func _check_opt_out_cleanup() -> void:
	var history_dispatch: int = int(sim.get("_volume_dispatch_id"))
	sim.presentation_macro_lod_enabled = false
	sim.presentation_trails_enabled = false
	sim.presentation_volume_history_enabled = false
	var current_only_resumed := false
	for _frame in range(LAYER_TIMEOUT_FRAMES):
		await get_tree().process_frame
		if int(sim.get("_volume_dispatch_id")) > history_dispatch \
				and is_equal_approx(float(sim.get("_volume_last_scheduling")), 0.0):
			current_only_resumed = true
			break
	var macro_mmi: MultiMeshInstance3D = sim.get("_macro_lod_mmi")
	var trail_mmi: MultiMeshInstance3D = sim.get("_trail_mmi")
	var history: RID = sim.get("_volume_history_state")
	_check("profile feature opt-out frees renderer-only resources", macro_mmi == null and trail_mmi == null and not history.is_valid())
	_check("volume-history opt-out resumes the current site-volume path", current_only_resumed)


func _check(label: String, ok: bool) -> void:
	_checks += 1
	if ok:
		print("[PASS] " + label)
	else:
		_failures += 1
		push_error("[FAIL] " + label)


