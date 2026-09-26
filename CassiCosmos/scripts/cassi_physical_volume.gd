class_name CassiPhysicalVolume
extends RefCounted
## Read-only HDR camera formal solution through the live H/H+ material grid.
## Every physical buffer is borrowed from CassiPhysicalMatterEngine; this class
## owns only its observer weights, output images, pipeline, and uniform set.

const SHADER_PATH := "res://compute/cassi_physical_volume.glsl"
const SOURCE_SHADER_PATH := "res://compute/cassi_physical_observer_source.glsl"
const MAX_RENDER_EDGE := 4096
const MAX_VISIBLE_GROUPS := 16

var _rd: RenderingDevice = null
var _shader := RID()
var _pipeline := RID()
var _source_shader := RID()
var _source_pipeline := RID()
var _source_uniform_set := RID()
var _uniform_set := RID()
var _observer_weights := RID()
var _visible_source := RID()
var _display_rid := RID()
var _xyz_rid := RID()
var _depth_rid := RID()
var _display: Texture2DRD = null
var _raw_xyz: Texture2DRD = null
var _depth: Texture2DRD = null
var _size := Vector2i.ZERO
var _resource_signature: Array = []
var _source_signature: Array = []
var _model_sha256 := ""
var _frequency_grid_sha256 := ""
var _visible_group_count := 0
var _observer_bytes := 0
var _source_bytes := 0
var _source_entries := 0
var _source_dispatch_count := 0
var _last_source_accepted_steps := -1
var _last_reset_epoch := -1
var _sigma_t_m2 := 0.0
var _hydrogen_mass_kg := 0.0
var _image_bytes := 0
var _dispatch_count := 0
var _raw_capture_count := 0
var _allocation_count := 0
var _last_publication: Dictionary = {}
var _last_error := ""
var _ready := false
var _last_command_record_us := 0
var _last_gpu_render_us := -1
var _pending_gpu_marker := ""
var _gpu_marker_id := 0

var radiance: Texture2DRD:
	get:
		return _display
var raw_xyz: Texture2DRD:
	get:
		return _raw_xyz
var depth: Texture2DRD:
	get:
		return _depth


func initialize(device: RenderingDevice) -> bool:
	if device == null:
		return _fail("physical volume received a null RenderingDevice")
	_rd = device
	var source := load(SHADER_PATH) as RDShaderFile
	var source_reduce := load(SOURCE_SHADER_PATH) as RDShaderFile
	if source == null or source.get_spirv() == null \
			or source_reduce == null or source_reduce.get_spirv() == null:
		return _fail("physical volume shaders are missing or uncompiled")
	_shader = _rd.shader_create_from_spirv(source.get_spirv())
	_source_shader = _rd.shader_create_from_spirv(source_reduce.get_spirv())
	if not _shader.is_valid() or not _source_shader.is_valid():
		return _fail("physical volume shader RID creation failed")
	_pipeline = _rd.compute_pipeline_create(_shader)
	_source_pipeline = _rd.compute_pipeline_create(_source_shader)
	if not _pipeline.is_valid() or not _source_pipeline.is_valid():
		return _fail("physical volume compute pipeline creation failed")
	_ready = true
	return true


func update(frame: Dictionary, settings: Dictionary) -> bool:
	if not _ready or _rd == null:
		return _fail("physical volume is not initialized")
	var resources_value: Variant = frame.get("physical_resources", {})
	if not resources_value is Dictionary:
		return _fail("live physical matter resources are unavailable")
	var resources := resources_value as Dictionary
	if not bool(resources.get("ready", false)):
		return _fail(String(resources.get("error", "live physical matter is not ready")))
	if not _ensure_observer(frame, resources):
		return false
	if not _ensure_scattering_source(resources):
		return false
	var requested: Vector2i = frame.get("render_size", Vector2i.ONE)
	requested = Vector2i(clampi(requested.x, 1, MAX_RENDER_EDGE),
		clampi(requested.y, 1, MAX_RENDER_EDGE))
	if not _ensure_targets(requested):
		return false
	if not _ensure_uniform_set(resources):
		return false
	_resolve_gpu_render_timestamp()
	var bounds: AABB = frame.get("bounds", AABB(-Vector3.ONE, Vector3.ONE * 2.0))
	var extents := bounds.size * 0.5
	if not extents.is_finite() or extents.x <= 0.0 or extents.y <= 0.0 or extents.z <= 0.0:
		return _fail("physical volume bounds are invalid")
	var camera: Transform3D = frame.get("camera_transform", Transform3D.IDENTITY)
	var basis := camera.basis.orthonormalized()
	var grid: Vector3i = resources.get("grid", Vector3i.ONE)
	var steps := clampi(2 * maxi(grid.x, maxi(grid.y, grid.z)), 16, 192)
	var values := PackedFloat32Array([
		camera.origin.x, camera.origin.y, camera.origin.z,
		deg_to_rad(clampf(float(frame.get("fov", 60.0)), 1.0, 179.0)),
		basis.x.x, basis.x.y, basis.x.z, float(_size.x),
		basis.y.x, basis.y.y, basis.y.z, float(_size.y),
		-basis.z.x, -basis.z.y, -basis.z.z,
		maxf(float(frame.get("near", 0.1)), 0.0001),
		bounds.get_center().x, bounds.get_center().y, bounds.get_center().z,
		(_sigma_t_m2 * float(resources.get("density_kg_m3_per_sim", 0.0))
			* float(resources.get("length_m_per_sim", 0.0))
			/ maxf(_hydrogen_mass_kg, 1.0e-30)),
		extents.x, extents.y, extents.z, float(resources.get("groups", 0)),
		float(grid.x), float(grid.y), float(grid.z), float(steps),
		maxf(float(settings.get("optical_thickness", 1.0)), 0.0),
		maxf(float(settings.get("emission", 1.0)), 0.0),
		float(_visible_group_count), maxf(float(resources.get("c_reduced_sim", 1.0)), 1.0e-20),
	])
	var push := values.to_byte_array()
	var record_started_us := Time.get_ticks_usec()
	var gpu_marker := "physical_volume_%d" % _gpu_marker_id
	var measure_gpu := _pending_gpu_marker.is_empty()
	if measure_gpu:
		_rd.capture_timestamp(gpu_marker + "/start")
	var commands := _rd.compute_list_begin()
	var source_accepted_steps := int(resources.get("accepted_steps", -1))
	var reset_epoch := int(resources.get("reset_epoch", -1))
	if source_accepted_steps != _last_source_accepted_steps \
			or reset_epoch != _last_reset_epoch:
		var source_push := PackedInt32Array([
			_source_entries / _visible_group_count,
			int(resources.get("groups", 0)),
			int(resources.get("angles", 0)),
			_visible_group_count,
		]).to_byte_array()
		_rd.compute_list_bind_compute_pipeline(commands, _source_pipeline)
		_rd.compute_list_bind_uniform_set(commands, _source_uniform_set, 0)
		_rd.compute_list_set_push_constant(commands, source_push, source_push.size())
		_rd.compute_list_dispatch(commands, ceili(float(_source_entries) / 64.0), 1, 1)
		_rd.compute_list_add_barrier(commands)
		_last_source_accepted_steps = source_accepted_steps
		_last_reset_epoch = reset_epoch
		_source_dispatch_count += 1
	_rd.compute_list_bind_compute_pipeline(commands, _pipeline)
	_rd.compute_list_bind_uniform_set(commands, _uniform_set, 0)
	_rd.compute_list_set_push_constant(commands, push, push.size())
	_rd.compute_list_dispatch(commands, ceili(float(_size.x) / 8.0),
		ceili(float(_size.y) / 8.0), 1)
	_rd.compute_list_end()
	if measure_gpu:
		_rd.capture_timestamp(gpu_marker + "/end")
		_pending_gpu_marker = gpu_marker
		_gpu_marker_id += 1
	_last_command_record_us = Time.get_ticks_usec() - record_started_us
	_dispatch_count += 1
	_last_publication = {
		"source_kind": resources.get("source_kind", ""),
		"numerical_identity": resources.get("numerical_identity", ""),
		"model_sha256": resources.get("model_sha256", ""),
		"frequency_grid_sha256": resources.get("frequency_grid_sha256", ""),
		"state_epoch": resources.get("state_epoch", 0),
		"accepted_steps": resources.get("accepted_steps", 0),
		"physical_time_sim": resources.get("physical_time_sim", 0.0),
		"energy_density_J_m3_per_sim": resources.get("energy_density_J_m3_per_sim", 0.0),
		"grid": grid,
		"render_size": _size,
		"visible_groups": _visible_group_count,
		"march_steps": steps,
		"spatial_reconstruction": "isotropic_wendland_c2_world",
	}
	_last_error = ""
	return true


func _ensure_observer(frame: Dictionary, resources: Dictionary) -> bool:
	var expected := String(resources.get("model_sha256", ""))
	if _observer_weights.is_valid() and expected == _model_sha256:
		return true
	_free_uniform_set()
	_free_source_uniform_set()
	if _observer_weights.is_valid():
		_rd.free_rid(_observer_weights)
	_observer_weights = RID()
	var path := String(frame.get("physical_model_path", ""))
	if path.is_empty() or not FileAccess.file_exists(path):
		return _fail("physical observer model is unavailable")
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		return _fail("physical observer model is not a JSON object")
	var model := parsed as Dictionary
	var constants_value: Variant = model.get("constants", {})
	if not constants_value is Dictionary:
		return _fail("physical observer constants are unavailable")
	var constants := constants_value as Dictionary
	_sigma_t_m2 = float(constants.get("sigma_T_m2", 0.0))
	_hydrogen_mass_kg = float(constants.get("m_H_kg", 0.0))
	if not is_finite(_sigma_t_m2) or _sigma_t_m2 <= 0.0 \
			or not is_finite(_hydrogen_mass_kg) or _hydrogen_mass_kg <= 0.0:
		return _fail("physical observer constants are invalid")
	if String(model.get("model_sha256", "")) != expected:
		return _fail("physical observer model identity does not match the live engine")
	var grid_value: Variant = model.get("frequency_grid", {})
	if not grid_value is Dictionary:
		return _fail("physical observer frequency grid is unavailable")
	var frequency_grid := grid_value as Dictionary
	var observer_value: Variant = frequency_grid.get("observer_xyz_average", [])
	var expected_groups := int(resources.get("groups", 0))
	if not observer_value is Array or (observer_value as Array).size() != expected_groups:
		return _fail("physical observer weights do not match the live frequency grid")
	var packed := PackedFloat32Array()
	for group in range(expected_groups):
		var row_value: Variant = (observer_value as Array)[group]
		if not row_value is Array or (row_value as Array).size() != 3:
			return _fail("physical observer weight record is malformed")
		var row := row_value as Array
		var weight := Vector3(float(row[0]), float(row[1]), float(row[2]))
		if not weight.is_finite() or weight.x < 0.0 or weight.y < 0.0 or weight.z < 0.0:
			return _fail("physical observer weights must be finite and nonnegative")
		if weight.x + weight.y + weight.z > 1.0e-12:
			packed.append_array(PackedFloat32Array([weight.x, weight.y, weight.z, float(group)]))
	if packed.is_empty() or packed.size() / 4 > MAX_VISIBLE_GROUPS:
		return _fail("physical observer visible-group count is unsupported")
	_observer_weights = _rd.storage_buffer_create(packed.size() * 4, packed.to_byte_array())
	if not _observer_weights.is_valid():
		return _fail("physical observer weight buffer creation failed")
	_visible_group_count = packed.size() / 4
	_observer_bytes = packed.size() * 4
	_model_sha256 = expected
	_frequency_grid_sha256 = String(resources.get("frequency_grid_sha256", ""))
	return true

func _ensure_scattering_source(resources: Dictionary) -> bool:
	var grid: Vector3i = resources.get("grid", Vector3i.ZERO)
	var cells := grid.x * grid.y * grid.z
	var groups := int(resources.get("groups", 0))
	var angles := int(resources.get("angles", 0))
	var radiation: RID = resources.get("radiation", RID())
	var ordinates: RID = resources.get("ordinates", RID())
	var opacity: RID = resources.get("opacity", RID())
	var emission: RID = resources.get("emission", RID())
	var population1: RID = resources.get("population1", RID())
	if cells <= 0 or groups <= 0 or angles <= 0 or _visible_group_count <= 0 \
			or not radiation.is_valid() or not ordinates.is_valid() \
			or not opacity.is_valid() or not emission.is_valid() \
			or not population1.is_valid():
		return _fail("physical visible-source resources are invalid")
	var entries := cells * _visible_group_count
	if entries != _source_entries or not _visible_source.is_valid():
		_free_uniform_set()
		_free_source_uniform_set()
		if _visible_source.is_valid():
			_rd.free_rid(_visible_source)
		_source_entries = entries
		_source_bytes = entries * 16
		_visible_source = _rd.storage_buffer_create(_source_bytes)
		if not _visible_source.is_valid():
			return _fail("physical visible-source allocation failed")
	var signature: Array = [
		radiation, ordinates, opacity, emission, population1,
		_observer_weights, _visible_source,
		cells, groups, angles, _visible_group_count,
	]
	if signature == _source_signature and _source_uniform_set.is_valid() \
			and _rd.uniform_set_is_valid(_source_uniform_set):
		return true
	_free_source_uniform_set()
	_source_uniform_set = _rd.uniform_set_create([
		_storage_uniform(0, radiation), _storage_uniform(1, ordinates),
		_storage_uniform(2, _observer_weights),
		_storage_uniform(3, _visible_source),
		_storage_uniform(4, opacity), _storage_uniform(5, emission),
		_storage_uniform(6, population1),
	], _source_shader, 0)
	if not _source_uniform_set.is_valid():
		return _fail("physical visible-source uniform set creation failed")
	_source_signature = signature
	_last_source_accepted_steps = -1
	_last_reset_epoch = -1
	return true


func _ensure_targets(requested: Vector2i) -> bool:
	if requested == _size and _targets_valid():
		return true
	_free_uniform_set()
	for rid: RID in [_display_rid, _xyz_rid, _depth_rid]:
		if rid.is_valid():
			_rd.free_rid(rid)
	_display_rid = _make_texture(requested,
		RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
	_xyz_rid = _make_texture(requested,
		RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
	_depth_rid = _make_texture(requested, RenderingDevice.DATA_FORMAT_R32_SFLOAT)
	if not _display_rid.is_valid() or not _xyz_rid.is_valid() or not _depth_rid.is_valid():
		return _fail("physical volume output allocation failed")
	# Texture2DRD can wrap only textures owned by the renderer's global device.
	# Local-device callers (verify arms) read the raw RIDs directly.
	_display = _wrap_rd_texture(_display_rid)
	_raw_xyz = _wrap_rd_texture(_xyz_rid)
	_depth = _wrap_rd_texture(_depth_rid)
	_size = requested
	_image_bytes = requested.x * requested.y * (16 + 16 + 4)
	_allocation_count += 1
	return true


func _ensure_uniform_set(_resources: Dictionary) -> bool:
	var signature: Array = [
		_observer_weights, _visible_source,
		_display_rid, _xyz_rid, _depth_rid,
	]
	if signature == _resource_signature and _uniform_set.is_valid() \
			and _rd.uniform_set_is_valid(_uniform_set):
		return true
	if not _observer_weights.is_valid() or not _visible_source.is_valid():
		return _fail("physical volume received invalid packed-source RIDs")
	_free_uniform_set()
	_uniform_set = _rd.uniform_set_create([
		_image_uniform(0, _display_rid), _image_uniform(1, _xyz_rid),
		_image_uniform(2, _depth_rid),
		_storage_uniform(5, _observer_weights),
		_storage_uniform(7, _visible_source),
	], _shader, 0)
	if not _uniform_set.is_valid():
		return _fail("physical volume uniform set creation failed")
	_resource_signature = signature
	return true


func _make_texture(size: Vector2i, format: RenderingDevice.DataFormat) -> RID:
	var descriptor := RDTextureFormat.new()
	descriptor.width = size.x
	descriptor.height = size.y
	descriptor.format = format
	descriptor.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT \
	| RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT \
	| RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT
	return _rd.texture_create(descriptor, RDTextureView.new(), [])


func _wrap_rd_texture(rid: RID) -> Texture2DRD:
	if _rd != RenderingServer.get_rendering_device():
		return null
	var wrapper := Texture2DRD.new()
	wrapper.texture_rd_rid = rid
	return wrapper


func _image_uniform(binding: int, rid: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
	uniform.binding = binding
	uniform.add_id(rid)
	return uniform


func _storage_uniform(binding: int, rid: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding
	uniform.add_id(rid)
	return uniform


func _targets_valid() -> bool:
	return _display_rid.is_valid() and _xyz_rid.is_valid() and _depth_rid.is_valid()


func capture_raw_xyz() -> Dictionary:
	if _rd == null or not _xyz_rid.is_valid() or _size.x <= 0 or _size.y <= 0:
		return {"ok": false, "error": "physical raw XYZ target is unavailable"}
	var bytes := _rd.texture_get_data(_xyz_rid, 0)
	_resolve_gpu_render_timestamp()
	if bytes.size() != _size.x * _size.y * 16:
		return {"ok": false, "error": "physical raw XYZ byte count mismatch"}
	_raw_capture_count += 1
	return {
		"ok": true, "bytes": bytes, "size": _size, "format": "RGBA32F",
		"channels": ["X", "Y", "Z", "valid"],
		"units": "solver radiation energy density per solid angle, CIE-weighted",
		"unit_scale_J_m3_per_sim": _last_publication.get(
			"energy_density_J_m3_per_sim", 0.0),
		"publication": publication_metadata(),
	}


func _resolve_gpu_render_timestamp() -> void:
	if _pending_gpu_marker.is_empty() or _rd == null:
		return
	var start_ns := -1
	var end_ns := -1
	for index in range(_rd.get_captured_timestamps_count()):
		var name := _rd.get_captured_timestamp_name(index)
		if name == _pending_gpu_marker + "/start":
			start_ns = _rd.get_captured_timestamp_gpu_time(index)
		elif name == _pending_gpu_marker + "/end":
			end_ns = _rd.get_captured_timestamp_gpu_time(index)
	if start_ns >= 0 and end_ns >= start_ns:
		# Godot's Vulkan backend returns nanoseconds here; publish microseconds.
		_last_gpu_render_us = int(end_ns - start_ns) / 1000
		_pending_gpu_marker = ""


func publication_metadata() -> Dictionary:
	return _last_publication.duplicate(true)


func statistics() -> Dictionary:
	_resolve_gpu_render_timestamp()
	return {
		"initialized": _ready, "valid": _ready and _targets_valid(),
		"source_kind": "live_conditional_hydrogen_plasma",
		"coupling": "read_only_camera_formal_solution",
		"composition_kind": "complete_live_material_state",
		"model_sha256": _model_sha256,
		"frequency_grid_sha256": _frequency_grid_sha256,
		"render_size": _size, "visible_groups": _visible_group_count,
		"spatial_reconstruction": "isotropic_wendland_c2_world",
		"alpha_contract": "cie_y_weighted_spectral_transmittance",
		"dispatch_count": _dispatch_count,
		"scattering_source_dispatch_count": _source_dispatch_count,
		"raw_capture_count": _raw_capture_count,
		"allocation_count": _allocation_count,
		"observer_bytes": _observer_bytes, "source_bytes": _source_bytes,
		"image_bytes": _image_bytes,
		"estimated_total_bytes": _observer_bytes + _source_bytes + _image_bytes,
		"last_command_record_us": _last_command_record_us,
		"last_gpu_render_us": _last_gpu_render_us,
		"error": _last_error,
	}


func shutdown() -> void:
	if _rd != null:
		_free_uniform_set()
		_free_source_uniform_set()
		for rid: RID in [
				_display_rid, _xyz_rid, _depth_rid, _observer_weights,
				_visible_source, _pipeline, _shader,
				_source_pipeline, _source_shader,
		]:
			if rid.is_valid():
				_rd.free_rid(rid)
	_uniform_set = RID()
	_source_uniform_set = RID()
	_display_rid = RID()
	_xyz_rid = RID()
	_depth_rid = RID()
	_observer_weights = RID()
	_visible_source = RID()
	_pipeline = RID()
	_shader = RID()
	_source_pipeline = RID()
	_source_shader = RID()
	_display = null
	_raw_xyz = null
	_depth = null
	_rd = null
	_size = Vector2i.ZERO
	_resource_signature.clear()
	_source_signature.clear()
	_model_sha256 = ""
	_frequency_grid_sha256 = ""
	_visible_group_count = 0
	_source_entries = 0
	_source_bytes = 0
	_last_source_accepted_steps = -1
	_last_reset_epoch = -1
	_last_command_record_us = 0
	_last_gpu_render_us = -1
	_pending_gpu_marker = ""
	_gpu_marker_id = 0
	_ready = false


func _free_uniform_set() -> void:
	if _uniform_set.is_valid() and _rd != null and _rd.uniform_set_is_valid(_uniform_set):
		_rd.free_rid(_uniform_set)
	_uniform_set = RID()
	_resource_signature.clear()


func _free_source_uniform_set() -> void:
	if _source_uniform_set.is_valid() and _rd != null \
			and _rd.uniform_set_is_valid(_source_uniform_set):
		_rd.free_rid(_source_uniform_set)
	_source_uniform_set = RID()
	_source_signature.clear()


func _fail(message: String) -> bool:
	_last_error = message
	push_error("[CassiPhysicalVolume] " + message)
	return false
