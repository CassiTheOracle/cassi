class_name CassiSpectralVolume
extends RefCounted
## Renderer-owned, read-only prescribed spectral volume.
## It records one formal-solution pass on the shared global RenderingDevice and
## publishes a complete linear-sRGB sensor image plus a separate raw XYZ image.

const SHADER_PATH: String = "res://compute/cassi_spectral_volume.glsl"
const MATERIAL_SCRIPT = preload("res://scripts/cassi_radiative_material.gd")
const MAX_RENDER_EDGE: int = 4096
const COEFFICIENT_FLOATS_PER_GROUP: int = 8

var _rd: RenderingDevice = null
var _material: RefCounted = null
var _shader: RID = RID()
var _pipeline: RID = RID()
var _uniform_set: RID = RID()
var _coefficients: RID = RID()
var _display_rid: RID = RID()
var _xyz_rid: RID = RID()
var _depth_rid: RID = RID()
var _display: Texture2DRD = null
var _raw_xyz: Texture2DRD = null
var _depth: Texture2DRD = null
var _size: Vector2i = Vector2i.ZERO
var _publication: Dictionary = {}
var _ready: bool = false
var _last_error: String = ""
var _dispatch_count: int = 0
var _allocation_count: int = 0
var _raw_capture_count: int = 0
var _coefficient_bytes: int = 0
var _image_bytes: int = 0

var radiance: Texture2DRD:
	get:
		return _display
var raw_xyz: Texture2DRD:
	get:
		return _raw_xyz
var depth: Texture2DRD:
	get:
		return _depth
var optical_depth: Texture3D:
	get:
		return null
var motion: Texture2DRD:
	get:
		return null


func initialize(device: RenderingDevice) -> bool:
	shutdown()
	if device == null:
		return _fail("RenderingDevice is null")
	_rd = device
	_material = MATERIAL_SCRIPT.new()
	if not _material.load_reference():
		return _fail(_material.last_error())
	var source: RDShaderFile = load(SHADER_PATH) as RDShaderFile
	if source == null or source.get_spirv() == null:
		return _fail("spectral volume shader is missing or uncompiled")
	_shader = _rd.shader_create_from_spirv(source.get_spirv())
	if not _shader.is_valid():
		return _fail("spectral shader RID is invalid")
	_pipeline = _rd.compute_pipeline_create(_shader)
	if not _pipeline.is_valid():
		return _fail("spectral pipeline creation failed")
	var packed: PackedFloat32Array = _coefficient_array()
	if packed.is_empty():
		return _fail("spectral coefficient construction failed")
	var bytes: PackedByteArray = packed.to_byte_array()
	_coefficients = _rd.storage_buffer_create(bytes.size(), bytes)
	if not _coefficients.is_valid():
		return _fail("spectral coefficient buffer creation failed")
	_coefficient_bytes = bytes.size()
	_ready = true
	return true


func update(frame: Dictionary, _settings: Dictionary) -> bool:
	if not _ready or _rd == null or _material == null:
		return false
	var requested: Vector2i = frame.get("render_size", frame.get("viewport_size", Vector2i.ONE))
	requested = Vector2i(clampi(requested.x, 1, MAX_RENDER_EDGE),
			clampi(requested.y, 1, MAX_RENDER_EDGE))
	if not _ensure_targets(requested):
		return false
	_publication = _material.publication(frame, int(frame.get("source_epoch", 0)))
	if not bool(_publication.get("ready", false)):
		return _fail(String(_publication.get("error", "spectral publication unavailable")))
	var model: Dictionary = _publication.model
	var snapshot: Dictionary = _publication.snapshot
	var units: Dictionary = model.unit_map
	var bounds: AABB = frame.get("bounds", AABB(-Vector3.ONE, Vector3.ONE * 2.0))
	var center: Vector3 = bounds.get_center()
	var radius: float = 0.48 * minf(bounds.size.x, minf(bounds.size.y, bounds.size.z))
	if not is_finite(radius) or radius <= 0.0:
		return _fail("prescribed spectral geometry has an invalid radius")
	var camera: Transform3D = frame.get("camera_transform", Transform3D.IDENTITY)
	var basis: Basis = camera.basis.orthonormalized()
	var forward: Vector3 = -basis.z
	var grid: Dictionary = _publication.spectral_grid
	var values: PackedFloat32Array = PackedFloat32Array([
		camera.origin.x, camera.origin.y, camera.origin.z,
		deg_to_rad(clampf(float(frame.get("fov", 60.0)), 1.0, 179.0)),
		basis.x.x, basis.x.y, basis.x.z, float(_size.x),
		basis.y.x, basis.y.y, basis.y.z, float(_size.y),
		forward.x, forward.y, forward.z, maxf(float(frame.get("near", 0.1)), 1e-4),
		center.x, center.y, center.z, radius,
		float(units.length_m_per_sim), float(grid.visible_group_count),
		float(snapshot.boundary_radiance_W_m2_sr) / float(units.radiance_scale_W_m2_sr),
		float(frame.get("source_epoch", 0)),
	])
	var push_constants: PackedByteArray = values.to_byte_array()
	var commands: int = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(commands, _pipeline)
	_rd.compute_list_bind_uniform_set(commands, _uniform_set, 0)
	_rd.compute_list_set_push_constant(commands, push_constants, push_constants.size())
	_rd.compute_list_dispatch(commands, ceili(float(_size.x) / 8.0),
			ceili(float(_size.y) / 8.0), 1)
	_rd.compute_list_end()
	_dispatch_count += 1
	return true


func publication_metadata() -> Dictionary:
	return _publication.duplicate(true)


## Capture-only readback. Never called by the interactive frame loop.
func capture_raw_xyz() -> Dictionary:
	if _rd == null or not _xyz_rid.is_valid() or _size.x <= 0 or _size.y <= 0:
		return {"ok": false, "error": "raw XYZ target is unavailable"}
	var bytes: PackedByteArray = _rd.texture_get_data(_xyz_rid, 0)
	if bytes.size() != _size.x * _size.y * 16:
		return {"ok": false, "error": "raw XYZ byte count mismatch"}
	_raw_capture_count += 1
	return {
		"ok": true,
		"bytes": bytes,
		"size": _size,
		"format": "RGBA32F",
		"channels": ["X", "Y", "Z", "valid"],
		"units": "numeric radiance; multiply XYZ by model.unit_map.radiance_scale_W_m2_sr",
		"publication": publication_metadata(),
	}


func shutdown() -> void:
	if _rd != null:
		_free_uniform_set()
		for rid: RID in [_display_rid, _xyz_rid, _depth_rid, _coefficients,
				_pipeline, _shader]:
			if rid.is_valid():
				_rd.free_rid(rid)
	_uniform_set = RID()
	_display_rid = RID()
	_xyz_rid = RID()
	_depth_rid = RID()
	_coefficients = RID()
	_pipeline = RID()
	_shader = RID()
	_display = null
	_raw_xyz = null
	_depth = null
	_size = Vector2i.ZERO
	_publication = {}
	_ready = false
	_rd = null
	_material = null


func statistics() -> Dictionary:
	var model_value: Dictionary = _publication.get("model", {})
	var grid_value: Dictionary = _publication.get("spectral_grid", {})
	var observer_value: Dictionary = _publication.get("observer", {})
	return {
		"initialized": _ready,
		"valid": _ready and _resources_valid(),
		"source_kind": "prescribed_spectral_preview",
		"coupling": "prescribed",
		"approximation": "frozen_state_formal_solution",
		"composition_kind": "complete_spectral_camera",
		"render_size": _size,
		"visible_groups": int(grid_value.get("visible_group_count", 0)),
		"total_groups": int(grid_value.get("total_group_count", 0)),
		"model_id": String(model_value.get("model_id", "")),
		"model_sha256": String(model_value.get("model_sha256", "")),
		"unit_map_sha256": String(model_value.get("unit_map", {}).get("unit_map_sha256", "")),
		"group_layout_sha256": String(grid_value.get("layout_sha256", "")),
		"observer_sha256": String(observer_value.get("sha256", "")),
		"white_point": String(observer_value.get("white_point", "")),
		"output_transform": String(observer_value.get("xyz_to_linear_rgb", "")),
		"gamut_map": String(observer_value.get("gamut_map", "")),
		"dispatch_count": _dispatch_count,
		"allocation_count": _allocation_count,
		"raw_capture_count": _raw_capture_count,
		"coefficient_bytes": _coefficient_bytes,
		"image_bytes": _image_bytes,
		"estimated_total_bytes": _coefficient_bytes + _image_bytes,
		"per_group_depth_atlas_bytes": 0,
		"error": _last_error,
		"unavailable": MATERIAL_SCRIPT.COUPLED_REQUIREMENTS.duplicate(),
	}


func _coefficient_array() -> PackedFloat32Array:
	var result: PackedFloat32Array = PackedFloat32Array()
	var bundle: Dictionary = _material.bundle()
	var model_value: Dictionary = bundle.model
	var material_value: Dictionary = model_value.material
	var units: Dictionary = model_value.unit_map
	var grid: Dictionary = bundle.selected_layout
	var controls: Array = bundle.temperature_controls
	var temperature: float = float(material_value.temperature_K)
	var selected: Dictionary = {}
	for value: Variant in controls:
		var row: Dictionary = value
		if is_equal_approx(float(row.temperature_K), temperature):
			selected = row
			break
	if selected.is_empty():
		return result
	var radiance_groups: Array = selected.group_radiance_W_m2_sr
	var groups: Array = grid.groups
	var scale: float = float(units.radiance_scale_W_m2_sr)
	for index: int in int(grid.visible_group_count):
		var group: Dictionary = groups[index + 1]
		var weights: Array = group.observer_xyz_integral_m
		var width_m: float = (float(group.wavelength_hi_nm) - float(group.wavelength_lo_nm)) * 1e-9
		result.append_array(PackedFloat32Array([
			float(radiance_groups[index + 1]) / scale,
			float(material_value.absorption_m_inv),
			float(weights[0]) / width_m,
			float(weights[1]) / width_m,
			float(weights[2]) / width_m,
			width_m,
			float(group.frequency_lo_hz),
			float(group.frequency_hi_hz),
		]))
	return result


func _ensure_targets(requested: Vector2i) -> bool:
	if requested == _size and _resources_valid():
		return true
	_free_uniform_set()
	for rid: RID in [_display_rid, _xyz_rid, _depth_rid]:
		if rid.is_valid():
			_rd.free_rid(rid)
	_display_rid = _make_texture(requested, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
	_xyz_rid = _make_texture(requested, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
	_depth_rid = _make_texture(requested, RenderingDevice.DATA_FORMAT_R32_SFLOAT)
	if not _display_rid.is_valid() or not _xyz_rid.is_valid() or not _depth_rid.is_valid():
		return _fail("spectral output allocation failed")
	_uniform_set = _rd.uniform_set_create([
		_image_uniform(0, _display_rid), _image_uniform(1, _xyz_rid),
		_image_uniform(2, _depth_rid), _storage_uniform(3, _coefficients),
	], _shader, 0)
	if not _uniform_set.is_valid():
		return _fail("spectral uniform set creation failed")
	_display = Texture2DRD.new()
	_display.texture_rd_rid = _display_rid
	_raw_xyz = Texture2DRD.new()
	_raw_xyz.texture_rd_rid = _xyz_rid
	_depth = Texture2DRD.new()
	_depth.texture_rd_rid = _depth_rid
	_size = requested
	_image_bytes = requested.x * requested.y * (16 + 16 + 4)
	_allocation_count += 1
	return true


func _make_texture(size: Vector2i, format: RenderingDevice.DataFormat) -> RID:
	var descriptor: RDTextureFormat = RDTextureFormat.new()
	descriptor.width = size.x
	descriptor.height = size.y
	descriptor.format = format
	descriptor.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT \
			| RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT \
			| RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT
	return _rd.texture_create(descriptor, RDTextureView.new(), [])


func _image_uniform(binding: int, rid: RID) -> RDUniform:
	var uniform: RDUniform = RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
	uniform.binding = binding
	uniform.add_id(rid)
	return uniform


func _storage_uniform(binding: int, rid: RID) -> RDUniform:
	var uniform: RDUniform = RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding
	uniform.add_id(rid)
	return uniform


func _free_uniform_set() -> void:
	if _uniform_set.is_valid() and _rd != null and _rd.uniform_set_is_valid(_uniform_set):
		_rd.free_rid(_uniform_set)
	_uniform_set = RID()


func _resources_valid() -> bool:
	return _shader.is_valid() and _pipeline.is_valid() and _coefficients.is_valid() \
			and _display_rid.is_valid() and _xyz_rid.is_valid() and _depth_rid.is_valid() \
			and _uniform_set.is_valid()


func _fail(message: String) -> bool:
	_last_error = message
	push_error("[CassiSpectralVolume] " + message)
	return false
