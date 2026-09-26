extends Node
## Presentation capture helper.
##
## This node is intentionally a capture/restore service rather than a camera
## owner. The free camera (or recorder) remains the normal writer. Explicit
## view restoration requests the sibling PresentationDirector's manual
## takeover first, then applies one instantaneous pose.

signal sequence_finished(summary: String)

const VIEW_COUNT: int = 3
const VIEW_CONFIG_PATH: String = "user://cassi_presentation_views.cfg"
const CAPTURE_ROOT: String = "user://cassi_captures"

var _sim: Node = null
var _camera: Camera3D = null
var _views: Array[Dictionary] = []
var _overlay_enabled: bool = false
var _interface_visible: bool = true
var _overlay_label: Label = null
var _overlay_scale: ColorRect = null
var _overlay_layer: CanvasLayer = null
var _overlay_root: Control = null
var _capture_in_progress: bool = false
var _sequence_running: bool = false
var _sequence_stop_requested: bool = false
var _sequence_fps: int = 30
var _sequence_captured: int = 0
var _sequence_dropped: int = 0
var _sequence_index: int = 0
var _sequence_directory: String = ""
var _capture_serial: int = 0
var _sequence_width: int = 0
var _sequence_height: int = 0
var _sequence_started_usec: int = 0
var _sequence_frames: Array[Dictionary] = []
var _sequence_ended_usec: int = 0

func _ready() -> void:
	for _slot in range(VIEW_COUNT):
		_views.append({})
	_load_views()
	_overlay_layer = CanvasLayer.new()
	_overlay_layer.name = "PresentationOverlayLayer"
	_overlay_layer.layer = 100
	_overlay_root = Control.new()
	_overlay_root.name = "PresentationOverlayRoot"
	_overlay_root.set_anchors_preset(Control.PRESET_FULL_RECT)
	_overlay_root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay_layer.add_child(_overlay_root)
	_overlay_label = Label.new()
	_overlay_label.name = "PresentationScaleOverlay"
	_overlay_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay_label.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_overlay_label.position = Vector2(-420.0, -58.0)
	_overlay_label.size = Vector2(400.0, 44.0)
	_overlay_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	_overlay_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_overlay_label.add_theme_color_override("font_color", Color(0.86, 0.92, 1.0, 0.94))
	_overlay_label.add_theme_color_override("font_shadow_color", Color(0.0, 0.0, 0.0, 0.9))
	_overlay_label.add_theme_constant_override("shadow_offset_x", 2)
	_overlay_label.add_theme_constant_override("shadow_offset_y", 2)
	_overlay_label.visible = false
	_overlay_root.add_child(_overlay_label)
	_overlay_scale = ColorRect.new()
	_overlay_scale.name = "PresentationScaleBar"
	_overlay_scale.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_overlay_scale.set_anchors_preset(Control.PRESET_BOTTOM_RIGHT)
	_overlay_scale.color = Color(0.86, 0.92, 1.0, 0.94)
	_overlay_scale.visible = false
	_overlay_root.add_child(_overlay_scale)
	add_child(_overlay_layer)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and event.keycode == KEY_F9:
		if not _interface_visible:
			set_interface_visible(true)
			get_viewport().set_input_as_handled()


## Bind this helper to the live simulation and its existing camera.
func setup(sim: Node, camera: Camera3D) -> void:
	_sim = sim
	_camera = camera
	_refresh_overlay()
func _process(_delta: float) -> void:
	if _overlay_enabled and _interface_visible:
		_refresh_overlay()



## Persist the current camera pose and FOV in one of three user-local slots.
func save_view(slot: int) -> Error:
	if not _valid_slot(slot) or not is_instance_valid(_camera):
		return ERR_INVALID_PARAMETER
	_views[slot] = {
		"origin": _camera.global_position,
		"basis": _camera.global_basis,
		"fov": _camera.fov,
		"near": _camera.near,
		"far": _camera.far,
	}
	return _write_views()


## Restore one saved pose. Manual takeover happens before this explicit write.
func restore_view(slot: int) -> Error:
	if not _valid_slot(slot) or not is_instance_valid(_camera):
		return ERR_INVALID_PARAMETER
	if _views[slot].is_empty():
		return ERR_DOES_NOT_EXIST
	_request_manual_takeover()
	var view: Dictionary = _views[slot]
	var origin_value: Variant = view.get("origin", Vector3.ZERO)
	var basis_value: Variant = view.get("basis", Basis.IDENTITY)
	if not origin_value is Vector3 or not basis_value is Basis:
		return ERR_FILE_CORRUPT
	var origin: Vector3 = origin_value
	var basis: Basis = basis_value
	_camera.global_transform = Transform3D(basis, origin)
	_camera.fov = clampf(float(view.get("fov", _camera.fov)), 1.0, 179.0)
	_camera.near = maxf(float(view.get("near", _camera.near)), 0.001)
	_camera.far = maxf(float(view.get("far", _camera.far)), _camera.near + 0.001)
	_refresh_overlay()
	return OK


## Enable or disable the optional simulation-unit/time readout.
func set_overlay_enabled(enabled: bool) -> void:
	_overlay_enabled = enabled
	_refresh_overlay()


## The UI owns interface visibility; its scientific field image remains visible.
## Child control state continues updating while the interface is hidden.
func set_interface_visible(visible: bool) -> void:
	_interface_visible = visible
	get_parent().call("set_presentation_interface_visible", visible)
	_refresh_overlay()


## Start a best-effort wall-clock PNG sequence. Cadence is measured, not
## promised: frames that miss their due time are counted as dropped.
func start_sequence(fps: int = 30) -> Error:
	if _sequence_running:
		return ERR_BUSY
	if fps < 1 or fps > 240:
		return ERR_INVALID_PARAMETER
	if not is_instance_valid(_camera) or get_viewport() == null:
		return ERR_UNCONFIGURED
	var stamp: String = Time.get_datetime_string_from_system().replace(":", "").replace("-", "")
	_sequence_directory = "%s/sequence_%s_%03d" % [CAPTURE_ROOT, stamp, _capture_serial]
	_capture_serial += 1
	var dir_error: Error = _ensure_directory(_sequence_directory)
	if dir_error != OK:
		push_error("[PresentationCapture] cannot create sequence directory: %s" % _sequence_directory)
		return dir_error
	_sequence_fps = fps
	_sequence_captured = 0
	_sequence_dropped = 0
	_sequence_index = 0
	_sequence_width = 0
	_sequence_height = 0
	_sequence_frames.clear()
	_sequence_started_usec = Time.get_ticks_usec()
	_sequence_ended_usec = 0
	_sequence_stop_requested = false
	_sequence_running = true
	_sequence_loop()
	return OK


## Request a sequence stop and return a measured snapshot. A frame already
## awaiting post-draw may finish after this call; its count is not invented.
func stop_sequence() -> String:
	if not _sequence_running:
		return ""
	_sequence_stop_requested = true
	return _sequence_summary()


## Capture the postprocessed root viewport output as a local PNG. For scale 2
## the viewport is temporarily rendered at twice its current dimensions.
func capture_still(scale: int = 1) -> String:
	if _capture_in_progress or _sequence_running:
		push_warning("[PresentationCapture] capture is already active")
		return ""
	if scale < 1 or scale > 2 or not is_instance_valid(_camera):
		push_error("[PresentationCapture] still scale must be 1 or 2 and camera must be valid")
		return ""
	var viewport: Viewport = get_viewport()
	if viewport == null or viewport.get_texture() == null:
		push_error("[PresentationCapture] no render viewport is available")
		return ""
	_capture_in_progress = true
	var window: Window = get_window()
	var original_window_size: Vector2i = window.size
	var original_scale_size: Vector2i = window.content_scale_size
	var original_scale_mode: int = window.content_scale_mode
	var original_scale_aspect: int = window.content_scale_aspect
	var original_scale_factor: float = window.content_scale_factor
	var image_path: String = ""
	var result_image: Image = null
	var save_error: Error = OK
	var target_size: Vector2i = Vector2i(viewport.get_visible_rect().size)
	if target_size.x <= 0 or target_size.y <= 0:
		target_size = original_window_size
	var expected_size: Vector2i = target_size * scale
	var resized: bool = scale != 1
	if resized:
		# VIEWPORT renders at the requested base resolution, then scales to the
		# unchanged native window. Capture is not constrained by monitor size.
		window.content_scale_mode = Window.CONTENT_SCALE_MODE_VIEWPORT
		window.content_scale_size = expected_size
		window.content_scale_aspect = Window.CONTENT_SCALE_ASPECT_IGNORE
	var original_sim_playing: Variant = null
	var paused_sim: bool = false
	if resized and _sim != null:
		var playing_value: Variant = _sim.get("playing")
		if playing_value is bool:
			original_sim_playing = playing_value
			if bool(playing_value):
				_sim.set("playing", false)
				paused_sim = true
	if resized:
		window.content_scale_factor = 1.0
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
	else:
		await RenderingServer.frame_post_draw
	result_image = viewport.get_texture().get_image()
	if result_image == null or result_image.is_empty():
		push_error("[PresentationCapture] renderer returned an empty image")
	elif resized and Vector2i(result_image.get_width(), result_image.get_height()) != expected_size:
		push_error("[PresentationCapture] requested %dx%d but renderer returned %dx%d" % [
			expected_size.x, expected_size.y, result_image.get_width(), result_image.get_height()])
	else:
		var actual_width: int = result_image.get_width()
		var actual_height: int = result_image.get_height()
		image_path = "%s/still_%s_%03d_%dx%d.png" % [CAPTURE_ROOT,
			Time.get_datetime_string_from_system().replace(":", "").replace("-", ""),
			_capture_serial, actual_width, actual_height]
		_capture_serial += 1
		save_error = _ensure_directory(CAPTURE_ROOT)
		if save_error == OK:
			save_error = result_image.save_png(image_path)
		if save_error == OK:
			_write_still_sidecar(image_path, actual_width, actual_height)
		if save_error != OK:
			push_error("[PresentationCapture] PNG save failed (%d): %s" % [save_error, image_path])
			image_path = ""
	# Restore every window/content-scale and simulation property even when
	# capture or save fails.
	if resized:
		window.content_scale_size = original_scale_size
		window.content_scale_mode = original_scale_mode
		window.content_scale_aspect = original_scale_aspect
		window.content_scale_factor = original_scale_factor
		window.size = original_window_size
		if paused_sim and original_sim_playing is bool:
			_sim.set("playing", bool(original_sim_playing))
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
	_capture_in_progress = false
	return image_path


func _sequence_loop() -> void:
	var interval: float = 1.0 / float(_sequence_fps)
	var next_due: float = Time.get_ticks_usec() / 1000000.0
	while not _sequence_stop_requested:
		var now: float = Time.get_ticks_usec() / 1000000.0
		var wait_seconds: float = next_due - now
		if wait_seconds > 0.0:
			await get_tree().create_timer(wait_seconds).timeout
		if _sequence_stop_requested:
			break
		var path: String = await _capture_sequence_frame()
		if path.is_empty():
			_sequence_dropped += 1
		else:
			_sequence_captured += 1
			_sequence_frames.append({
				"file": path.get_file(),
				"metadata": _capture_metadata(_sequence_width, _sequence_height),
			})
		_sequence_index += 1
		now = Time.get_ticks_usec() / 1000000.0
		var missed: int = maxi(0, int(floor((now - next_due) / interval)))
		_sequence_dropped += missed
		next_due += float(missed + 1) * interval
	_sequence_ended_usec = Time.get_ticks_usec()
	_sequence_running = false
	_sequence_stop_requested = false
	_write_sequence_sidecar()
	sequence_finished.emit(_sequence_summary())


func _capture_sequence_frame() -> String:
	if _capture_in_progress:
		return ""
	_capture_in_progress = true
	await RenderingServer.frame_post_draw
	var image: Image = get_viewport().get_texture().get_image()
	if image != null and not image.is_empty():
		_sequence_width = image.get_width()
		_sequence_height = image.get_height()
	var path: String = ""
	if image != null and not image.is_empty():
		path = "%s/frame_%06d.png" % [_sequence_directory, _sequence_index]
		var error: Error = image.save_png(path)
		if error != OK:
			push_error("[PresentationCapture] sequence frame save failed (%d)" % error)
			path = ""
	_capture_in_progress = false
	return path




func _request_manual_takeover() -> void:
	var director: Node = null
	if _camera != null:
		director = _camera.get_parent().get_node_or_null("PresentationDirector")
	if director != null and director.has_method("request_manual_takeover"):
		director.call("request_manual_takeover")


func _refresh_overlay() -> void:
	if _overlay_label == null:
		return
	_overlay_label.visible = _overlay_enabled and _interface_visible
	_overlay_scale.visible = _overlay_label.visible
	if not _overlay_label.visible or _camera == null:
		return
	var sim_time: float = 0.0
	if _sim != null and _sim.get("_time") != null:
		sim_time = float(_sim.get("_time"))
	var target: Vector3 = Vector3.ZERO
	if _sim != null and _sim.has_method("get_presentation_camera_target"):
		target = _sim.call("get_presentation_camera_target")
	var distance: float = maxf(-_camera.to_local(target).z, 0.001)
	var viewport_size: Vector2 = get_viewport().get_visible_rect().size
	var viewport_height: float = maxf(viewport_size.y, 1.0)
	var vertical_tangent := tan(deg_to_rad(_camera.fov) * 0.5)
	if _camera.keep_aspect == Camera3D.KEEP_WIDTH:
		vertical_tangent *= viewport_height / maxf(viewport_size.x, 1.0)
	var world_span: float = 2.0 * distance * vertical_tangent
	var units_per_pixel: float = world_span / viewport_height
	var scale_units: float = _nice_scale(maxf(units_per_pixel * 160.0, 0.001))
	_overlay_label.text = "%s simulation units   |   t = %.3f" % [String.num(scale_units, 3), sim_time]
	_overlay_scale.offset_left = -20.0 - scale_units / units_per_pixel
	_overlay_scale.offset_right = -20.0
	_overlay_scale.offset_top = -18.0
	_overlay_scale.offset_bottom = -16.0


func _nice_scale(value: float) -> float:
	var exponent: float = floor(log(value) / log(10.0))
	var base: float = value / pow(10.0, exponent)
	var nice_base: float = 1.0 if base < 2.0 else (2.0 if base < 5.0 else 5.0)
	return nice_base * pow(10.0, exponent)


func _valid_slot(slot: int) -> bool:
	return slot >= 0 and slot < VIEW_COUNT


func _ensure_directory(path: String) -> Error:
	var absolute: String = ProjectSettings.globalize_path(path)
	if DirAccess.dir_exists_absolute(absolute):
		return OK
	return DirAccess.make_dir_recursive_absolute(absolute)

func _write_still_sidecar(image_path: String, width: int, height: int) -> void:
	if image_path.is_empty():
		return
	var metadata: Dictionary = _capture_metadata(width, height)
	metadata["schema_version"] = "1.0.0"
	metadata["capture_kind"] = "still"
	metadata["pixel_file"] = image_path.get_file()
	if _sim != null and _sim.has_method("capture_observation_raw_xyz"):
		var raw: Variant = _sim.call("capture_observation_raw_xyz")
		if raw is Dictionary and bool(raw.get("ok", false)):
			var raw_data: Dictionary = raw
			var raw_size: Vector2i = raw_data.get("size", Vector2i.ZERO)
			var raw_path: String = image_path.trim_suffix(".png") + ".xyz.rgba32f"
			var raw_file: FileAccess = FileAccess.open(raw_path, FileAccess.WRITE)
			if raw_file != null:
				raw_file.store_buffer(raw_data.get("bytes", PackedByteArray()))
				raw_file.close()
				metadata["raw_linear"] = {
					"file": raw_path.get_file(),
					"format": String(raw_data.get("format", "RGBA32F")),
					"channels": raw_data.get("channels", []),
					"units": String(raw_data.get("units", "")),
					"width": raw_size.x,
					"height": raw_size.y,
				}
	_write_json(image_path.trim_suffix(".png") + ".json", metadata)


func _write_sequence_sidecar() -> void:
	if _sequence_directory.is_empty():
		return
	_write_json(_sequence_directory.path_join("sequence.json"), {
		"schema_version": "1.0.0",
		"capture_kind": "png_sequence",
		"directory": _sequence_directory.get_file(),
		"requested_fps": _sequence_fps,
		"captured": _sequence_captured,
		"dropped": _sequence_dropped,
		"actual_width": _sequence_width,
		"actual_height": _sequence_height,
		"started_usec": _sequence_started_usec,
		"ended_usec": _sequence_ended_usec,
		"frames": _sequence_frames,
	})


func _capture_metadata(width: int, height: int) -> Dictionary:
	var observation: Dictionary = {}
	if _sim != null and _sim.has_method("get_observation_capture_metadata"):
		var value: Variant = _sim.call("get_observation_capture_metadata")
		if value is Dictionary:
			observation = value
	var transform: Transform3D = _camera.global_transform if is_instance_valid(_camera) \
			else Transform3D.IDENTITY
	return _json_safe({
		"source": observation,
		"executed_step": int(_sim.get("_step_count")) if _sim != null else -1,
		"simulation_time": float(_sim.get("_time")) if _sim != null else 0.0,
		"camera": {
			"origin": transform.origin,
			"basis": transform.basis,
			"fov_degrees": _camera.fov if is_instance_valid(_camera) else 0.0,
			"near": _camera.near if is_instance_valid(_camera) else 0.0,
			"far": _camera.far if is_instance_valid(_camera) else 0.0,
		},
		"actual_width": width,
		"actual_height": height,
		"exposure_ev": float(observation.get("settings", {}).get("exposure_ev", 0.0)),
		"shutter_seconds": float(observation.get("settings", {}).get("shutter_seconds", 0.0)),
	})


func _write_json(path: String, value: Dictionary) -> void:
	var file: FileAccess = FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		push_error("[PresentationCapture] cannot write sidecar: " + path)
		return
	file.store_string(JSON.stringify(_json_safe(value), "\t") + "\n")
	file.close()


func _json_safe(value: Variant) -> Variant:
	if value is Dictionary:
		var mapped: Dictionary = {}
		for key: Variant in value:
			mapped[String(key)] = _json_safe(value[key])
		return mapped
	if value is Array:
		var mapped: Array = []
		for child: Variant in value:
			mapped.append(_json_safe(child))
		return mapped
	if value is Vector2:
		return [value.x, value.y]
	if value is Vector2i:
		return [value.x, value.y]
	if value is Vector3:
		return [value.x, value.y, value.z]
	if value is Vector3i:
		return [value.x, value.y, value.z]
	if value is Basis:
		return [
			value.x.x, value.x.y, value.x.z,
			value.y.x, value.y.y, value.y.z,
			value.z.x, value.z.y, value.z.z,
		]
	if value is Transform3D:
		return {"basis": _json_safe(value.basis), "origin": _json_safe(value.origin)}
	if value is AABB:
		return {"position": _json_safe(value.position), "size": _json_safe(value.size)}
	if value is RID:
		return "RID(%d)" % value.get_id()
	return value


func _write_views() -> Error:
	var config := ConfigFile.new()
	for slot in range(VIEW_COUNT):
		if _views[slot].is_empty():
			continue
		var view: Dictionary = _views[slot]
		var origin: Vector3 = view["origin"]
		var basis: Basis = view["basis"]
		config.set_value("view_%d" % slot, "origin",
				[origin.x, origin.y, origin.z])
		config.set_value("view_%d" % slot, "basis", [
			basis.x.x, basis.x.y, basis.x.z,
			basis.y.x, basis.y.y, basis.y.z,
			basis.z.x, basis.z.y, basis.z.z])
		config.set_value("view_%d" % slot, "fov", view["fov"])
		config.set_value("view_%d" % slot, "near", view["near"])
		config.set_value("view_%d" % slot, "far", view["far"])
	return config.save(VIEW_CONFIG_PATH)


func _load_views() -> void:
	var config := ConfigFile.new()
	if config.load(VIEW_CONFIG_PATH) != OK:
		return
	for slot in range(VIEW_COUNT):
		var section := "view_%d" % slot
		if not config.has_section(section):
			continue
		var origin_value: Variant = config.get_value(section, "origin", [])
		var basis_value: Variant = config.get_value(section, "basis", [])
		var origin: Variant = _decode_origin(origin_value)
		var basis: Variant = _decode_basis(basis_value)
		if origin == null or basis == null:
			continue
		_views[slot] = {
			"origin": origin,
			"basis": basis,
			"fov": float(config.get_value(section, "fov", 70.0)),
			"near": float(config.get_value(section, "near", 0.1)),
			"far": float(config.get_value(section, "far", 2000.0)),
		}


func _decode_origin(value: Variant) -> Variant:
	if value is Vector3:
		return value
	if value is Array and value.size() == 3:
		return Vector3(float(value[0]), float(value[1]), float(value[2]))
	return null


func _decode_basis(value: Variant) -> Variant:
	if value is Basis:
		return value
	if value is Array and value.size() == 9:
		return Basis(
			Vector3(float(value[0]), float(value[1]), float(value[2])),
			Vector3(float(value[3]), float(value[4]), float(value[5])),
			Vector3(float(value[6]), float(value[7]), float(value[8])))
	return null

func _sequence_summary() -> String:
	var end_usec: int = Time.get_ticks_usec() if _sequence_running else _sequence_ended_usec
	var elapsed: float = maxf(
			float(end_usec - _sequence_started_usec) / 1000000.0,
			0.001)
	var actual_fps: float = float(_sequence_captured) / elapsed
	return "directory=%s size=%dx%d captured=%d dropped=%d requested_fps=%d elapsed_seconds=%.3f actual_fps=%.3f" % [
		_sequence_directory, _sequence_width, _sequence_height,
		_sequence_captured, _sequence_dropped, _sequence_fps, elapsed, actual_fps]
