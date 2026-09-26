extends Node
## Exercises real main-scene transitions and capture. Raw images, timings and
## results live in _diag/observatory; persisted operator preferences are restored.

const OUTPUT := "res://_diag/observatory"
var sim: Node3D
var camera: Camera3D
var ui: Control
var capture: Node
var _world: Node
var _checks := 0
var _failures := 0
var _backup: Dictionary = {}
var _receipt: Dictionary = {"views": [], "timings": [], "captures": []}

func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
	for path in ["user://observatory_appearance.cfg", "user://cassi_presentation_views.cfg"]:
		_backup[path] = FileAccess.get_file_as_bytes(path) if FileAccess.file_exists(path) else null
	get_window().size = Vector2i(960, 540)
	_world = load("res://scenes/main.tscn").instantiate()
	sim = _world.get_node("CassiSim")
	var count := 2048
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--particles="):
			count = argument.trim_prefix("--particles=").to_int()
	sim.set("N_particles", count)
	sim.set("grid_N", 64)
	sim.set("ic_seed", 736241)
	sim.set("cluster_radius", 25.0)
	sim.set("physics_frame_budget", 0.0)
	sim.set("max_steps_per_frame", 1)
	sim.set("auto_frame_camera_on_start", false)
	sim.set("observatory_style", 0)
	sim.set("physical_matter_enabled", false)
	_world.tree_entered.connect(func() -> void: get_tree().current_scene = _world, CONNECT_ONE_SHOT)
	get_tree().root.add_child.call_deferred(_world)
	await _world.ready
	camera = _world.get_node("Camera3D")
	camera.set_process(false)
	camera.position = Vector3(0, 15, 90)
	camera.look_at(Vector3.ZERO)
	ui = _world.get_node("UILayer/SimUI")
	capture = ui.get("_capture_helper")
	_check("main UI connects capture to active camera", capture != null)
	sim.set("playing", true)
	var booted := false
	var boot_deadline := Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < boot_deadline:
		await get_tree().process_frame
		if not bool(sim.get("_decoupled_boot_wait")) and bool(sim.get("_shaders_ready")) and int(sim.get("_step_count")) >= 2:
			booted = true
			break
	_check("production scene boots", booted)
	if booted:
		await _exercise()
	_receipt["checks"] = _checks
	_receipt["failures"] = _failures
	_receipt["particle_count"] = count
	var file := FileAccess.open(OUTPUT + "/integration_receipt.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(_receipt, "\t"))
	file.close()
	_restore_preferences()
	print("OBSERVATORY INTEGRATION RESULT: %d/%d passed" % [_checks - _failures, _checks])
	get_tree().quit(0 if _failures == 0 else 1)

func _exercise() -> void:
	sim.set("playing", false)
	sim.set("auto_align_colors", false)
	if capture != null:
		capture.call("set_interface_visible", false)
	await _frames(12)
	var baseline := await _image("scientific_before")
	var buffers := _solver_bytes()
	var original_pose := camera.global_transform
	var original_environment := camera.environment
	sim.call("set_observatory_style", 1)
	sim.call("set_observatory_setting", "adaptive_quality", false)
	sim.call("set_observatory_setting", "quality", 0)
	sim.call("set_observatory_setting", "background", false)
	await _frames(10)
	var statistics: Dictionary = sim.call("get_observatory_statistics")
	_check("real Observatory compositor produces frames", bool(statistics.active) and int(statistics.post.get("dispatch_count", 0)) > 0)
	var preset_before := await _image("observatory_particles")
	var saved := int(sim.call("save_observatory_preset")) == OK
	sim.call("set_observatory_style", 2)
	sim.call("set_observatory_setting", "exposure_ev", -3.0)
	var loaded := int(sim.call("load_observatory_preset")) == OK
	await _frames(12)
	var preset_after := await _image("preset_restored")
	_check("saved appearance restores the rendered image", saved and loaded and preset_before.get_data() == preset_after.get_data())
	_check("appearance never takes camera ownership", camera.global_transform == original_pose)
	_check("optical rendering preserves paused solver bytes", _solver_bytes() == buffers)
	sim.call("set_observatory_source", 1)
	sim.call("set_observatory_style", 1)
	await _frames(8)
	statistics = sim.call("get_observatory_statistics")
	_check("prescribed spectral source activates independently of appearance",
			bool(statistics.active)
			and str(statistics.source_name) == "prescribed_spectral_preview"
			and int(statistics.volume.get("dispatch_count", 0)) > 0)
	var spectral := await _image("prescribed_spectral_preview")
	_check("prescribed spectral source produces finite visible pixels",
			not spectral.is_empty() and _image_is_finite_nonzero(spectral))
	_check("one-way spectral observation preserves every solver buffer",
			_solver_bytes() == buffers)
	var publication: Dictionary = statistics.get("publication", {})
	_check("spectral publication retains immutable model provenance",
			str(publication.get("model", {}).get("model_sha256", "")).length() == 64
			and str(publication.get("observer", {}).get("sha256", "")).length() == 64
			and str(publication.get("snapshot", {}).get("snapshot_sha256", "")).length() == 64
			and str(publication.get("coupling", "")) == "prescribed")
	sim.call("set_observatory_source", 2)
	await _frames(4)
	statistics = sim.call("get_observatory_statistics")
	var readiness: Dictionary = statistics.get("source_readiness", {})
	_check("live physical source fails closed while its engine is disabled",
			not bool(statistics.active) and not bool(readiness.get("ready", true))
			and not bool(readiness.get("enabled", true))
			and (readiness.get("missing", []) as Array).size() >= 1)

	sim.set("physical_matter_enabled", true)
	sim.call("reinit")
	sim.set("playing", true)
	var physical_deadline := Time.get_ticks_msec() + 45000
	while Time.get_ticks_msec() < physical_deadline:
		await get_tree().process_frame
		readiness = sim.call("get_physical_matter_readiness")
		statistics = sim.call("get_observatory_statistics")
		if bool(readiness.get("ready", false)) and bool(statistics.get("active", false)):
			break
	_check("live physical source initializes against production physics",
			bool(readiness.get("ready", false)) and bool(statistics.get("active", false))
			and str(statistics.get("source_name", "")) == "live_physical_matter")
	sim.set("playing", false)
	await _frames(4)
	var physical_before := _physical_solver_bytes()
	statistics = sim.call("get_observatory_statistics")
	var physical := await _image("live_physical_matter")
	_check("live physical source produces finite visible pixels",
			not physical.is_empty() and _image_is_finite_nonzero(physical))
	_check("physical camera formal solution preserves paused material and radiation",
			not physical_before.is_empty() and _physical_solver_bytes() == physical_before)
	var raw_physical: Dictionary = sim.call("capture_observation_raw_xyz")
	var raw_size: Vector2i = raw_physical.get("size", Vector2i.ZERO)
	_check("live physical source publishes complete raw XYZ",
			bool(raw_physical.get("ok", false))
			and (raw_physical.get("bytes", PackedByteArray()) as PackedByteArray).size()
				== raw_size.x * raw_size.y * 16
			and float(raw_physical.get("unit_scale_J_m3_per_sim", 0.0)) > 0.0)
	var accepted_before := int(readiness.get("accepted_steps", 0))
	var source_dispatch_before := int(statistics.get("volume", {}).get(
			"scattering_source_dispatch_count", 0))
	sim.set("playing", true)
	var evolution_deadline := Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < evolution_deadline:
		await get_tree().process_frame
		readiness = sim.call("get_physical_matter_readiness")
		if int(readiness.get("accepted_steps", 0)) > accepted_before:
			break
	await _frames(2)
	statistics = sim.call("get_observatory_statistics")
	_check("physical radiation evolution refreshes the camera scattering source",
			int(readiness.get("accepted_steps", 0)) > accepted_before
			and int(statistics.get("volume", {}).get(
				"scattering_source_dispatch_count", 0)) > source_dispatch_before)
	_receipt["live_physical"] = {
		"readiness": readiness,
		"renderer": statistics.get("volume", {}),
		"raw_xyz_size": raw_size,
	}
	sim.set("playing", false)
	sim.set("physical_matter_enabled", false)
	sim.call("set_observatory_source", 0)
	sim.call("set_observatory_style", 0)
	sim.call("reinit")
	var default_ready_deadline := Time.get_ticks_msec() + 30000
	while Time.get_ticks_msec() < default_ready_deadline:
		await get_tree().process_frame
		if not bool(sim.get("_decoupled_boot_wait")) and bool(sim.get("_shaders_ready")):
			break
	await _frames(4)
	camera.global_transform = original_pose
	baseline = await _image("scientific_after_physical_reset")
	buffers = _solver_bytes()
	sim.call("set_observatory_style", 0)
	await _frames(12)
	var restored := await _image("scientific_after")
	_check("Scientific restores the original environment", camera.environment == original_environment)
	_check("Scientific restores fixed-state framebuffer", baseline.get_data() == restored.get_data())
	_check("style on/off preserves every captured solver buffer", _solver_bytes() == buffers)

	for mode in [0, 1]:
		sim.set("mode", mode)
		for style in [1, 2]:
			sim.call("set_observatory_style", style)
			await _frames(8)
			statistics = sim.call("get_observatory_statistics")
			_check("active renderer mode %d style %d" % [mode, style], bool(statistics.active))
			var image := await _image("mode%d_style%d" % [mode, style])
			_receipt.views.append({"mode": mode, "style": style, "stats": statistics, "width": image.get_width(), "height": image.get_height()})
			sim.call("set_observatory_setting", "exposure_ev", -2.0)
			await _frames(4)
			var dark := await _image("mode%d_style%d_dark" % [mode, style])
			_check("exposure changes actual pixels mode %d style %d" % [mode, style], dark.get_data() != image.get_data())
			sim.call("set_observatory_setting", "exposure_ev", 0.0)
		sim.call("set_observatory_style", 0)
		await _frames(4)

	# Regression: main.tscn ships the compatibility particle material with
	# compact placement. Its cull volume must still follow a free camera beyond
	# the old ±5000 fallback, and the camera target must share the particle
	# snapshot's render-local home-window coordinates.
	_check("main scene retains the compatibility particle profile",
			not bool(sim.get("presentation_profile"))
			and bool(sim.get("compact_render_data")))
	var saved_home_window: bool = bool(sim.get("home_window_enabled"))
	var saved_window_center: Vector3 = sim.get("_window_center")
	sim.set("home_window_enabled", true)
	sim.set("_window_center", Vector3(12000.0, -3000.0, 7000.0))
	_check("home-window camera target matches translated particle coordinates",
			(sim.call("get_presentation_camera_target") as Vector3).is_zero_approx())

	var away_pose := camera.global_transform
	var render_center: Vector3 = sim.call("_render_window_center")
	var window_extents: Vector3 = sim.call("_extents")
	var structure_direction := Vector3(0.68, 0.31, 0.66).normalized()
	camera.global_position = render_center + structure_direction * maxf(
			window_extents.length() * 0.45, 500.0)
	camera.look_at(render_center, Vector3.UP)
	sim.call("set_observatory_source", 0)
	sim.call("set_observatory_style", 1)
	sim.call("set_observatory_setting", "background", true)
	await _frames(8)
	var home_window_image := await _image("camera_nonzero_home_window_oblique")
	_check("nonzero home-window camera retains a continuous frame at an oblique angle",
			_image_has_background_floor(home_window_image))

	var outward := Vector3(1.0, 0.23, 0.31).normalized()
	camera.global_position = render_center + outward * maxf(window_extents.length() * 2.0, 20000.0)
	camera.look_at(camera.global_position + outward, Vector3.UP)
	await _frames(8)
	var multimesh: MultiMesh = sim.get("_mm")
	var cull_box := multimesh.custom_aabb if multimesh != null else AABB()
	_check("compatibility particle cull volume follows the outside camera",
			multimesh != null and cull_box.has_point(camera.global_position)
			and cull_box.get_center().distance_to(camera.global_position) <= 1.0)
	var outward_image := await _image("camera_outside_window_looking_away")
	_check("camera outside the home window retains a visible background when looking away",
			_image_has_background_floor(outward_image))
	camera.global_transform = away_pose
	sim.set("_window_center", saved_window_center)
	sim.set("home_window_enabled", saved_home_window)
	sim.call("set_observatory_setting", "background", false)
	sim.call("set_observatory_style", 0)
	await _frames(4)

	sim.set("mode", 0)
	sim.call("set_observatory_style", 1)
	if capture != null:
		_check("save camera view", int(capture.call("save_view", 0)) == OK)
		camera.position += Vector3(50, 30, 10)
		_check("restore camera view", int(capture.call("restore_view", 0)) == OK and camera.global_transform == original_pose)
		sim.call("set_observatory_source", 1)
		await _frames(4)
		for scale in [1, 2]:
			var size_before := get_window().size
			var path: String = await capture.call("capture_still", scale)
			var image := Image.load_from_file(path) if not path.is_empty() else null
			_check("actual %dx still dimensions" % scale, image != null and image.get_size() == Vector2i(960, 540) * scale)
			_check("still restores window and pause", get_window().size == size_before and not bool(sim.get("playing")))
			_receipt.captures.append({"scale": scale, "path": ProjectSettings.globalize_path(path) if not path.is_empty() else ""})
			var sidecar := path.trim_suffix(".png") + ".json"
			var raw_xyz := path.trim_suffix(".png") + ".xyz.rgba32f"
			_check("spectral still writes provenance sidecar %dx" % scale,
					FileAccess.file_exists(sidecar))
			_check("spectral still writes raw linear XYZ %dx" % scale,
					FileAccess.file_exists(raw_xyz)
					and FileAccess.get_file_as_bytes(raw_xyz).size() > 0)
		sim.call("set_observatory_source", 0)
		# Overload the recorder with real frame pacing so dropped-frame reporting
		# and file enumeration are exercised together.
		var capture_max_fps := Engine.max_fps
		var capture_vsync := bool(sim.get("vsync_enabled"))
		sim.set("vsync_enabled", false)
		Engine.max_fps = 30
		_receipt["sequence_pacing"] = {"vsync": false, "max_fps": 30, "requested_fps": 120}
		_check("start PNG sequence", int(capture.call("start_sequence", 120)) == OK)
		await get_tree().create_timer(0.6).timeout
		capture.call("stop_sequence")
		await get_tree().create_timer(0.4).timeout
		_receipt["sequence"] = capture.call("_sequence_summary")
		var sequence_count := int(capture.get("_sequence_captured"))
		var sequence_directory := str(capture.get("_sequence_directory"))
		var sequence_files := DirAccess.get_files_at(sequence_directory)
		_receipt["sequence_directory"] = ProjectSettings.globalize_path(sequence_directory)
		_receipt["sequence_files"] = sequence_files
		_receipt["sequence_dropped"] = int(capture.get("_sequence_dropped"))
		var png_count := 0
		var frames_readable := true
		for filename in sequence_files:
			if not filename.ends_with(".png"):
				continue
			png_count += 1
			var frame := Image.load_from_file(sequence_directory.path_join(filename))
			frames_readable = frames_readable and frame != null and frame.get_size() == Vector2i(960, 540)
		frames_readable = frames_readable and png_count >= 2 and png_count == sequence_count
		_check("PNG sequence frames decode at viewport dimensions", frames_readable)
		_check("overloaded PNG sequence reports dropped slots", int(_receipt["sequence_dropped"]) > 0)
		var completed_summary := str(_receipt["sequence"])
		await get_tree().create_timer(0.2).timeout
		_check("completed sequence cadence remains stable", str(capture.call("_sequence_summary")) == completed_summary)
		Engine.max_fps = capture_max_fps
		sim.set("vsync_enabled", capture_vsync)
		capture.call("set_overlay_enabled", true)
		capture.call("set_interface_visible", true)
		ui.call("_on_tab_selected", 1)
		await _frames()
		await _image("observatory_ui")
		capture.call("set_interface_visible", false)
		var restore_key := InputEventKey.new()
		restore_key.keycode = KEY_F9
		restore_key.pressed = true
		Input.parse_input_event(restore_key)
		await _frames()
		var interface_toggle := ui.find_child("CaptureInterface", true, false) as CheckButton
		_check("F9 restores interface and its toggle", ui.get("_control_panel").is_visible_in_tree() and interface_toggle.button_pressed)
		capture.call("set_interface_visible", false)

	for quality in [0, 1, 2, 3]:
		sim.call("set_observatory_setting", "quality", quality)
		await _frames(6)
		_check("quality controls the real optical grid %d" % quality, int(sim.call("get_observatory_statistics").volume.grid) == [48, 64, 96, 128][quality])
	# Exercise hysteresis using real rendered-frame pacing, not injected deltas.
	var original_max_fps := Engine.max_fps
	var original_vsync := bool(sim.get("vsync_enabled"))
	sim.set("vsync_enabled", false)
	sim.call("set_observatory_setting", "quality", 2)
	sim.call("set_observatory_setting", "adaptive_quality", true)
	sim.call("set_observatory_setting", "target_frame_ms", 20.0)
	Engine.max_fps = 30
	await _frames(150)
	var overload_stats: Dictionary = sim.call("get_observatory_statistics")
	_receipt["quality_pacing"] = {"vsync": false, "max_fps": 30, "target_frame_ms": 20.0, "measured_frame_ms": overload_stats.frame_ms_ema}
	_check("sustained slow frames lower actual optical resolution", int(overload_stats.volume.grid) == 48 and float(overload_stats.frame_ms_ema) > 24.0)
	Engine.max_fps = original_max_fps
	sim.call("set_observatory_setting", "target_frame_ms", 100.0)
	await _frames(510)
	_check("sustained headroom restores requested optical resolution", int(sim.call("get_observatory_statistics").volume.grid) == 96)
	sim.set("vsync_enabled", original_vsync)
	sim.call("set_observatory_setting", "adaptive_quality", false)
	sim.call("set_observatory_setting", "target_frame_ms", 20.0)
	get_window().size = Vector2i(800, 600)
	await _frames(5)
	await _image("resized")
	get_window().size = Vector2i(960, 540)
	camera.position = Vector3(25, 10, 70)
	camera.look_at(Vector3.ZERO)
	await _frames(1)
	var cut_image := await _image("camera_cut")
	sim.call("set_observatory_setting", "temporal", false)
	await _frames(3)
	var cut_reference := await _image("camera_cut_current_only")
	_check("camera cut has no previous-view ghost", cut_image.get_data() == cut_reference.get_data())
	sim.call("set_observatory_setting", "temporal", true)
	sim.call("set_observatory_setting", "quality", 0)
	sim.set("playing", true)
	await _frames(12)
	sim.set("playing", false)
	await _frames(4)
	_check("resume advances real physics", int(sim.get("_step_count")) > 2)
	var reinit_started := Time.get_ticks_msec()
	sim.call("reinit")
	var reinitialized := false
	while Time.get_ticks_msec() - reinit_started < 30000:
		await _frames()
		if not bool(sim.get("_decoupled_boot_wait")) and bool(sim.get("_shaders_ready")) and bool(sim.call("get_observatory_statistics").active):
			reinitialized = true
			break
	_receipt["reinit_ready_ms"] = Time.get_ticks_msec() - reinit_started
	_check("reinit reacquires live optical sources", reinitialized)
	if not reinitialized:
		return
	sim.set("playing", true)
	for style in [0, 1, 2]:
		sim.call("set_observatory_style", style)
		await _frames(10)
		var timings: Array[float] = []
		var previous := Time.get_ticks_usec()
		for index in 90:
			camera.position = Vector3(15 * sin(float(index) / 90.0), 15, 65 + 25 * cos(float(index) / 90.0))
			camera.look_at(Vector3.ZERO)
			await get_tree().process_frame
			var now := Time.get_ticks_usec()
			timings.append(float(now - previous) / 1000.0)
			previous = now
		_receipt.timings.append({"style": style, "timing_boundary": "SceneTree.process_frame", "frame_ms": timings, "stats": sim.call("get_observatory_statistics")})
	sim.set("playing", false)
	sim.call("set_observatory_style", 0)
	await _frames(4)

func _frames(count: int = 3) -> void:
	for _index in count:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw

func _image(label: String) -> Image:
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	image.save_png(OUTPUT.path_join(label + ".png"))
	return image

func _image_is_finite_nonzero(image: Image) -> bool:
	var nonzero := false
	for y in range(0, image.get_height(), maxi(image.get_height() / 16, 1)):
		for x in range(0, image.get_width(), maxi(image.get_width() / 16, 1)):
			var pixel := image.get_pixel(x, y)
			if not is_finite(pixel.r) or not is_finite(pixel.g) or not is_finite(pixel.b):
				return false
			nonzero = nonzero or maxf(pixel.r, maxf(pixel.g, pixel.b)) > 0.0
	return nonzero


func _image_has_background_floor(image: Image) -> bool:
	if image == null or image.is_empty():
		return false
	var step_x := maxi(image.get_width() / 24, 1)
	var step_y := maxi(image.get_height() / 16, 1)
	for y in range(step_y / 2, image.get_height(), step_y):
		for x in range(step_x / 2, image.get_width(), step_x):
			var pixel := image.get_pixel(x, y)
			if not is_finite(pixel.r) or not is_finite(pixel.g) or not is_finite(pixel.b):
				return false
			if maxf(pixel.r, maxf(pixel.g, pixel.b)) <= 0.002:
				return false
	return true


func _physical_solver_bytes() -> Dictionary:
	var owner: Object = sim.get("_physics_engine") if bool(sim.get("_decoupled_active")) else sim
	if owner == null or not owner.has_method("physical_matter_render_resources"):
		return {}
	var resources: Dictionary = owner.call("physical_matter_render_resources")
	var device: RenderingDevice = sim.get("_rd")
	var result: Dictionary = {}
	for key in [
			"material0", "material1", "population0", "population1",
			"radiation", "opacity", "emission",
	]:
		var rid: RID = resources.get(key, RID())
		if rid.is_valid():
			result[key] = device.buffer_get_data(rid)
	return result


func _solver_bytes() -> Dictionary:
	var owner: Object = sim.get("_physics_engine") if bool(sim.get("_decoupled_active")) else sim
	var device: RenderingDevice = sim.get("_rd")
	var result: Dictionary = {}
	for key in ["_pos_buf", "_vel_buf", "_field_ey", "_field_ei", "_field_pp_ey", "_field_pp_ei"]:
		var rid: RID = owner.get(key)
		if rid.is_valid():
			result[key] = device.buffer_get_data(rid)
	return result

func _check(label: String, passed: bool) -> void:
	_checks += 1
	if not passed:
		_failures += 1
	print("[%s] %s" % ["PASS" if passed else "FAIL", label])

func _restore_preferences() -> void:
	for path in _backup:
		if _backup[path] == null:
			if FileAccess.file_exists(path):
				DirAccess.remove_absolute(path)
		else:
			var file := FileAccess.open(path, FileAccess.WRITE)
			file.store_buffer(_backup[path])
			file.close()
	_backup.clear()

func _exit_tree() -> void:
	_restore_preferences()
