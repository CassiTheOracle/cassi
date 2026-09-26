class_name CassiObservatoryPost
extends CompositorEffect
## POST_TRANSPARENT HDR compositor for Observatory/Cinematic presentation.
## The scene color RID and optical Texture2DRD RIDs are borrowed from the
## renderer/controller and are never freed here. Only history, parameter, and
## fallback resources allocated by this effect are owned and released.

const POST_SHADER_PATH: String = "res://compute/cassi_observatory_post.glsl"
const PARAM_FLOATS: int = 28

var _rd: RenderingDevice = null
var _shader: RID = RID()
var _pipeline: RID = RID()
var _uniform_set: RID = RID()
var _params_buffer: RID = RID()
var _luma_shader: RID = RID()
var _luma_pipeline: RID = RID()
var _luma_uniform_set: RID = RID()
var _luma_signature: Array = []
var _luma_state: RID = RID()
var _luma_samples: RID = RID()
var _bloom_shader: RID = RID()
var _bloom_pipeline: RID = RID()
var _bloom_uniform_set: RID = RID()
var _bloom_signature: Array = []
var _combined_texture: RID = RID()
var _bright_texture: RID = RID()
var _background_texture: RID = RID()
var _history_color: Array[RID] = [RID(), RID()]
var _uniform_sets: Array[RID] = [RID(), RID()]
var _uniform_signatures: Array[Array] = [[], []]
var _history_depth: Array[RID] = [RID(), RID()]
var _dummy_color: RID = RID()
var _dummy_depth: RID = RID()
var _history_index: int = 0
var _history_size: Vector2i = Vector2i.ZERO

# Immutable snapshots published by configure on the main thread. The render
# callback only consumes these values and never touches the scene tree.
var _frame_snapshot: Dictionary = {}
var _settings_snapshot: Dictionary = {}
var _volume_texture: Texture2DRD = null
var _snapshot_mutex: Mutex = Mutex.new()
var _depth_texture: Texture2DRD = null
var _configured: bool = false
var _initialized: bool = false
var _history_valid: bool = false
var _pending_reset: bool = true
var _previous_source_epoch: int = -1
var _previous_resize_epoch: int = -1
var _previous_camera: Transform3D = Transform3D()
var _previous_fov: float = 0.0
var _previous_size: Vector2i = Vector2i.ZERO
var _previous_field_mode: bool = false
var _stats: Dictionary = {
	"initialized": false,
	"configured": false,
	"callback_count": 0,
	"dispatch_count": 0,
	"skipped_count": 0,
	"allocation_count": 0,
	"history_resets": 0,
	"last_size": Vector2i.ZERO,
	"last_error": "",
	"resource_valid": false,
}

func _init() -> void:
	effect_callback_type = CompositorEffect.EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
	access_resolved_color = true


## Main-thread setup. Shader loading is intentionally kept out of the render
## callback because RDShaderFile loading is not thread-safe.
func initialize(device: RenderingDevice) -> bool:
	if device == null:
		_fail_initialize("RenderingDevice is null")
		return false
	_rd = device
	_release_pipeline_only()
	var shader_file: RDShaderFile = load(POST_SHADER_PATH) as RDShaderFile
	if shader_file == null:
		_fail_initialize("post shader resource failed to load: " + POST_SHADER_PATH)
		return false
	var spirv = shader_file.get_spirv()
	if spirv == null:
		_fail_initialize("post shader has no SPIR-V: " + POST_SHADER_PATH)
		return false
	_shader = _rd.shader_create_from_spirv(spirv)
	if not _shader.is_valid():
		_fail_initialize("post shader_create_from_spirv returned an invalid RID")
		return false
	_pipeline = _rd.compute_pipeline_create(_shader)
	if not _pipeline.is_valid():
		_fail_initialize("post compute pipeline creation failed")
		return false
	_initialized = true
	var luma_file: RDShaderFile = load(
			"res://compute/cassi_observatory_post_luma.glsl") as RDShaderFile
	if luma_file == null or luma_file.get_spirv() == null:
		_fail_initialize("post luminance shader failed to load or compile")
		return false
	_luma_shader = _rd.shader_create_from_spirv(luma_file.get_spirv())
	_luma_pipeline = _rd.compute_pipeline_create(_luma_shader)
	if not _luma_pipeline.is_valid():
		_fail_initialize("post luminance pipeline creation failed")
		return false
	var bloom_file: RDShaderFile = load(
			"res://compute/cassi_observatory_post_bloom.glsl") as RDShaderFile
	if bloom_file == null or bloom_file.get_spirv() == null:
		_fail_initialize("post bloom shader failed to load or compile")
		return false
	_bloom_shader = _rd.shader_create_from_spirv(bloom_file.get_spirv())
	_bloom_pipeline = _rd.compute_pipeline_create(_bloom_shader)
	if not _bloom_pipeline.is_valid():
		_fail_initialize("post bloom pipeline creation failed")
		return false
	_stats["initialized"] = true
	_stats["last_error"] = ""
	return true


## Publish a deep-copied frame/settings snapshot. Texture2DRD objects are held
## by reference until the controller has completed callback teardown.
func configure(frame: Dictionary, settings: Dictionary, volume: Texture2DRD,
		depth: Texture2DRD) -> void:
	_snapshot_mutex.lock()
	_frame_snapshot = frame.duplicate(true)
	_settings_snapshot = settings.duplicate(true)
	_volume_texture = volume
	_depth_texture = depth
	_configured = true
	_stats["configured"] = true
	var resize_epoch: int = int(_frame_snapshot.get("resize_epoch", 0))
	if resize_epoch != _previous_resize_epoch:
		_pending_reset = true
		_history_valid = false
		_stats["history_resets"] = int(_stats["history_resets"]) + 1
	var field_mode: bool = bool(_frame_snapshot.get("field_mode", false))
	if field_mode != _previous_field_mode:
		_pending_reset = true
		_history_valid = false
		_stats["history_resets"] = int(_stats["history_resets"]) + 1
	if _previous_fov > 0.0 and _camera_cut(_camera_transform()):
		_pending_reset = true
		_history_valid = false
		_stats["history_resets"] = int(_stats["history_resets"]) + 1
	if bool(_frame_snapshot.get("reset_history", false)):
		_pending_reset = true
		_history_valid = false
		_stats["history_resets"] = int(_stats["history_resets"]) + 1

	_snapshot_mutex.unlock()

## Render-thread callback. All allocations are private to this effect; the
func _render_callback(callback_type: int, render_data: RenderData) -> void:
	_snapshot_mutex.lock()
	_stats["callback_count"] = int(_stats["callback_count"]) + 1
	_render_callback_locked(callback_type, render_data)
	_snapshot_mutex.unlock()

func _render_callback_locked(callback_type: int, render_data: RenderData) -> void:
	if callback_type != CompositorEffect.EFFECT_CALLBACK_TYPE_POST_TRANSPARENT:
		return
	if not _initialized or not _pipeline.is_valid() or _rd == null:
		_stats["skipped_count"] = int(_stats["skipped_count"]) + 1
		return
	if not _configured or render_data == null:
		_stats["skipped_count"] = int(_stats["skipped_count"]) + 1
		return
	var scene_buffers: RenderSceneBuffersRD = render_data.get_render_scene_buffers()
	if scene_buffers == null:
		_stats["skipped_count"] = int(_stats["skipped_count"]) + 1
		return
	var size: Vector2i = scene_buffers.get_internal_size()
	if size.x <= 0 or size.y <= 0:
		_stats["skipped_count"] = int(_stats["skipped_count"]) + 1
		return
	var scene_color: RID = scene_buffers.get_color_layer(0)
	if not scene_color.is_valid():
		_stats["skipped_count"] = int(_stats["skipped_count"]) + 1
		return
	if not _ensure_owned_targets(size):
		_stats["skipped_count"] = int(_stats["skipped_count"]) + 1
		return
	var volume_rid: RID = _dummy_color
	if _volume_texture != null and _volume_texture.texture_rd_rid.is_valid():
		volume_rid = _volume_texture.texture_rd_rid
	var depth_rid: RID = _dummy_depth
	if _depth_texture != null and _depth_texture.texture_rd_rid.is_valid():
		depth_rid = _depth_texture.texture_rd_rid
	if bool(_settings_snapshot.get("auto_exposure", false)):
		_run_luma_reduction(scene_color, volume_rid, size)
	if not _cache_uniform_set(scene_color, volume_rid, depth_rid):
		_stats["skipped_count"] = int(_stats["skipped_count"]) + 1
		return
	_update_parameter_buffer(size)
	var push_constants: PackedByteArray = _make_push_constants(size)
	var list: int = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(list, _pipeline)
	_rd.compute_list_bind_uniform_set(list, _uniform_set, 0)
	_rd.compute_list_set_push_constant(list, push_constants, push_constants.size())
	_rd.compute_list_dispatch(list, ceili(float(size.x) / 8.0),
		ceili(float(size.y) / 8.0), 1)
	_rd.compute_list_end()
	_run_bloom(scene_color, size)
	_history_index = 1 - _history_index
	_history_valid = true
	_previous_source_epoch = int(_frame_snapshot.get("source_epoch", 0))
	_previous_resize_epoch = int(_frame_snapshot.get("resize_epoch", 0))
	_previous_size = size
	_previous_camera = _camera_transform()
	_previous_field_mode = bool(_frame_snapshot.get("field_mode", false))
	_previous_fov = _fov_radians()
	_pending_reset = false
	_stats["dispatch_count"] = int(_stats["dispatch_count"]) + 1
	_stats["last_size"] = size
	_stats["resource_valid"] = true

func shutdown() -> void:
	_snapshot_mutex.lock()
	_configured = false
	_initialized = false
	_history_valid = false
	_pending_reset = true
	_volume_texture = null
	_depth_texture = null
	if _rd != null:
		for rid: RID in _uniform_sets:
			_free_uniform_set(rid)
		_uniform_sets = [RID(), RID()]
		_uniform_signatures = [[], []]
		_uniform_set = RID()
		_free_rid(_params_buffer)
		_free_uniform_set(_luma_uniform_set)
		_params_buffer = RID()
		_free_rid(_luma_state)
		_free_rid(_luma_samples)
		_luma_uniform_set = RID()
		_luma_state = RID()
		_luma_samples = RID()
		for rid: RID in _history_color:
			_free_rid(rid)
		for rid: RID in _history_depth:
			_free_rid(rid)
		_history_color = [RID(), RID()]
		_history_depth = [RID(), RID()]
		_history_size = Vector2i.ZERO
		_free_rid(_dummy_color)
		_free_uniform_set(_bloom_uniform_set)
		_free_rid(_combined_texture)
		_free_rid(_bright_texture)
		_free_rid(_background_texture)
		_free_rid(_dummy_depth)
		_dummy_color = RID()
		_dummy_depth = RID()
		_bloom_uniform_set = RID()
		_combined_texture = RID()
		_bright_texture = RID()
		_background_texture = RID()
		_luma_signature = []
		_bloom_signature = []
		_release_pipeline_only()
	_rd = null
	_stats["initialized"] = false
	_stats["configured"] = false
	_stats["resource_valid"] = false
	_snapshot_mutex.unlock()
func statistics() -> Dictionary:
	_snapshot_mutex.lock()
	var result: Dictionary = _stats.duplicate(true)
	result["history_index"] = _history_index
	result["history_valid"] = _history_valid
	result["borrowed_volume_valid"] = _volume_texture != null \
			and _volume_texture.texture_rd_rid.is_valid()
	result["borrowed_depth_valid"] = _depth_texture != null \
			and _depth_texture.texture_rd_rid.is_valid()
	_snapshot_mutex.unlock()
	return result


func _fail_initialize(message: String) -> void:
	_initialized = false
	_stats["initialized"] = false
	_stats["resource_valid"] = false
	_stats["last_error"] = message
	push_error("[CassiObservatoryPost] " + message)


func _release_pipeline_only() -> void:
	if _rd == null:
		_shader = RID()
		_pipeline = RID()
		_luma_shader = RID()
		_luma_pipeline = RID()
		_bloom_shader = RID()
		_bloom_pipeline = RID()
		return
	_free_rid(_pipeline)
	_free_rid(_shader)
	_free_rid(_luma_pipeline)
	_free_rid(_luma_shader)
	_free_rid(_bloom_pipeline)
	_free_rid(_bloom_shader)
	_pipeline = RID()
	_shader = RID()
	_luma_pipeline = RID()
	_luma_shader = RID()
	_bloom_pipeline = RID()
	_bloom_shader = RID()

func _free_rid(rid: RID) -> void:
	if rid.is_valid() and _rd != null:
		_rd.free_rid(rid)

func _free_uniform_set(rid: RID) -> void:
	# Godot invalidates descriptors when a borrowed viewport/volume image
	# is replaced. RID.is_valid() alone only tests the handle, not ownership.
	if rid.is_valid() and _rd != null and _rd.uniform_set_is_valid(rid):
		_rd.free_rid(rid)


func _make_texture(size: Vector2i, format: int) -> RID:
	var fmt: RDTextureFormat = RDTextureFormat.new()
	fmt.width = maxi(size.x, 1)
	fmt.height = maxi(size.y, 1)
	fmt.format = format
	fmt.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT \
			| RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT \
			| RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT \
			| RenderingDevice.TEXTURE_USAGE_CAN_UPDATE_BIT
	return _rd.texture_create(fmt, RDTextureView.new(), [])


func _ensure_owned_targets(size: Vector2i) -> bool:
	if _history_size == size and _history_color[0].is_valid() \
			and _history_color[1].is_valid() and _params_buffer.is_valid() \
			and _dummy_color.is_valid() and _dummy_depth.is_valid() \
			and _luma_state.is_valid() and _luma_samples.is_valid() \
			and _combined_texture.is_valid() and _bright_texture.is_valid() \
			and _background_texture.is_valid():
		return true
	# Descriptor sets borrow their image RIDs; release descriptors first.
	for rid: RID in _uniform_sets:
		_free_uniform_set(rid)
	_uniform_sets = [RID(), RID()]
	_uniform_signatures = [[], []]
	_free_uniform_set(_bloom_uniform_set)
	_bloom_uniform_set = RID()
	_bloom_signature = []
	for rid: RID in _history_color:
		_free_rid(rid)
	for rid: RID in _history_depth:
		_free_rid(rid)
	_free_rid(_combined_texture)
	_free_rid(_bright_texture)
	_free_rid(_background_texture)
	_combined_texture = RID()
	_bright_texture = RID()
	_background_texture = RID()
	_combined_texture = _make_texture(size, RenderingDevice.DATA_FORMAT_R16G16B16A16_SFLOAT)
	_bright_texture = _make_texture(size, RenderingDevice.DATA_FORMAT_R16G16B16A16_SFLOAT)
	_background_texture = _make_texture(size, RenderingDevice.DATA_FORMAT_R16G16B16A16_SFLOAT)
	_uniform_set = RID()
	_history_color = [_make_texture(size, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT),
			_make_texture(size, RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)]
	_history_depth = [_make_texture(size, RenderingDevice.DATA_FORMAT_R32_SFLOAT),
			_make_texture(size, RenderingDevice.DATA_FORMAT_R32_SFLOAT)]
	if not _luma_state.is_valid():
		_luma_state = _rd.storage_buffer_create(16)
		var state_zero: PackedByteArray = PackedByteArray()
		state_zero.resize(16)
		_rd.buffer_update(_luma_state, 0, 16, state_zero)
	if not _luma_samples.is_valid():
		_luma_samples = _rd.storage_buffer_create(4096 * 4)
	if not _params_buffer.is_valid():
		_params_buffer = _rd.storage_buffer_create(PARAM_FLOATS * 4)
	if not _dummy_color.is_valid():
		_dummy_color = _make_texture(Vector2i.ONE,
			RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT)
	if not _dummy_depth.is_valid():
		_dummy_depth = _make_texture(Vector2i.ONE, RenderingDevice.DATA_FORMAT_R32_SFLOAT)
	_history_size = size
	_history_index = 0
	_history_valid = false
	_pending_reset = true
	_stats["allocation_count"] = int(_stats["allocation_count"]) + 1
	return _history_color[0].is_valid() and _history_color[1].is_valid() \
			and _history_depth[0].is_valid() and _history_depth[1].is_valid() \
			and _params_buffer.is_valid() and _dummy_color.is_valid() \
			and _dummy_depth.is_valid() and _luma_state.is_valid() \
			and _luma_samples.is_valid() and _combined_texture.is_valid() \
			and _bright_texture.is_valid() and _background_texture.is_valid()


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


func _cache_uniform_set(scene_color: RID, volume: RID, depth: RID) -> bool:
	var previous: int = _history_index
	var next: int = 1 - previous
	var signature: Array = [scene_color, volume, depth,
			_history_color[previous], _history_depth[previous],
			_history_color[next], _history_depth[next], _params_buffer,
			_luma_state, _combined_texture, _bright_texture, _background_texture]
	if _uniform_sets[previous].is_valid() and _rd.uniform_set_is_valid(_uniform_sets[previous]) \
			and _uniform_signatures[previous] == signature:
		_uniform_set = _uniform_sets[previous]
		return true
	_free_uniform_set(_uniform_sets[previous])
	_uniform_sets[previous] = _rd.uniform_set_create([
		_image_uniform(0, scene_color), _image_uniform(1, volume),
		_image_uniform(2, depth), _image_uniform(3, _history_color[previous]),
		_image_uniform(4, _history_depth[previous]),
		_image_uniform(5, _history_color[next]),
		_image_uniform(6, _history_depth[next]),
		_storage_uniform(7, _params_buffer),
		_storage_uniform(8, _luma_state),
		_image_uniform(9, _combined_texture),
		_image_uniform(10, _bright_texture),
		_image_uniform(11, _background_texture),
	], _shader, 0)
	if not _uniform_sets[previous].is_valid():
		_stats["last_error"] = "post uniform set creation failed"
		push_error("[CassiObservatoryPost] post uniform set creation failed")
		return false
	_uniform_signatures[previous] = signature
	_uniform_set = _uniform_sets[previous]
	return true


func _run_luma_reduction(scene_color: RID, volume: RID, _size: Vector2i) -> void:
	if not bool(_settings_snapshot.get("auto_exposure", false)):
		return
	if not _luma_pipeline.is_valid():
		return
	var signature: Array = [scene_color, volume, _luma_state, _luma_samples]
	if not (_luma_uniform_set.is_valid() and _rd.uniform_set_is_valid(_luma_uniform_set) and _luma_signature == signature):
		_free_uniform_set(_luma_uniform_set)
		_luma_uniform_set = _rd.uniform_set_create([
			_image_uniform(0, scene_color), _image_uniform(1, volume),
			_storage_uniform(2, _luma_state),
			_storage_uniform(3, _luma_samples),
		], _luma_shader, 0)
		_luma_signature = signature
	if not _luma_uniform_set.is_valid():
		push_error("[CassiObservatoryPost] luminance uniform set creation failed")
		return
	var delta: float = maxf(float(_frame_snapshot.get("delta", 0.016)), 0.0)
	var field_mode: float = 1.0 if bool(_frame_snapshot.get("field_mode", false)) \
			or int(_settings_snapshot.get("composition_kind", 0)) > 0 else 0.0
	var target: float = clampf(
			float(_settings_snapshot.get("auto_exposure_target", 0.1)), 0.01, 1.0)
	var pc0: PackedByteArray = PackedFloat32Array(
			[0.0, delta, field_mode, target]).to_byte_array()
	var pc1: PackedByteArray = PackedFloat32Array(
			[1.0, delta, field_mode, target]).to_byte_array()
	var list: int = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(list, _luma_pipeline)
	_rd.compute_list_bind_uniform_set(list, _luma_uniform_set, 0)
	_rd.compute_list_set_push_constant(list, pc0, pc0.size())
	_rd.compute_list_dispatch(list, 8, 8, 1)
	_rd.compute_list_add_barrier(list)
	_rd.compute_list_set_push_constant(list, pc1, pc1.size())
	_rd.compute_list_dispatch(list, 1, 1, 1)
	_rd.compute_list_end()

func _camera_transform() -> Transform3D:
	var value: Variant = _frame_snapshot.get("camera_transform", Transform3D())
	if value is Transform3D:
		return value as Transform3D
	return Transform3D()


func _run_bloom(scene_color: RID, size: Vector2i) -> void:
	if not _bloom_pipeline.is_valid() or not _combined_texture.is_valid() \
			or not _bright_texture.is_valid() or not _background_texture.is_valid() \
			or not _luma_state.is_valid():
		return
	var signature: Array = [scene_color, _combined_texture, _bright_texture,
			_background_texture, _luma_state]
	if not (_bloom_uniform_set.is_valid() and _rd.uniform_set_is_valid(_bloom_uniform_set) and _bloom_signature == signature):
		_free_uniform_set(_bloom_uniform_set)
		_bloom_uniform_set = _rd.uniform_set_create([
			_image_uniform(0, scene_color), _image_uniform(1, _combined_texture),
			_image_uniform(2, _bright_texture),
			_storage_uniform(3, _luma_state),
			_image_uniform(4, _background_texture),
		], _bloom_shader, 0)
		_bloom_signature = signature
	if not _bloom_uniform_set.is_valid():
		push_error("[CassiObservatoryPost] bloom uniform set creation failed")
		return
	var exposure: float = float(_settings_snapshot.get("exposure_ev", 0.0))
	var bloom: float = float(_settings_snapshot.get("bloom", 0.08))
	var auto_exposure: float = 1.0 if bool(
			_settings_snapshot.get("auto_exposure", false)) else 0.0
	var pc: PackedByteArray = PackedFloat32Array(
			[exposure, bloom, auto_exposure, 0.0]).to_byte_array()
	var list: int = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(list, _bloom_pipeline)
	_rd.compute_list_bind_uniform_set(list, _bloom_uniform_set, 0)
	_rd.compute_list_set_push_constant(list, pc, pc.size())
	_rd.compute_list_dispatch(list, ceili(float(size.x) / 8.0),
			ceili(float(size.y) / 8.0), 1)
	_rd.compute_list_end()


func _fov_radians() -> float:
	var value: float = float(_frame_snapshot.get("fov", 60.0))
	return deg_to_rad(clampf(value, 1.0, 179.0))


func _make_push_constants(size: Vector2i) -> PackedByteArray:
	var camera: Transform3D = _camera_transform()
	var basis: Basis = camera.basis.orthonormalized()
	var forward: Vector3 = -basis.z
	var values: PackedFloat32Array = PackedFloat32Array([
		camera.origin.x, camera.origin.y, camera.origin.z, _fov_radians(),
		basis.x.x, basis.x.y, basis.x.z, float(size.x),
		basis.y.x, basis.y.y, basis.y.z, float(size.y),
		forward.x, forward.y, forward.z,
		maxf(float(_frame_snapshot.get("near", 0.1)), 1e-4),
	])
	return values.to_byte_array()


func _update_parameter_buffer(size: Vector2i) -> void:
	var exposure: float = float(_settings_snapshot.get("exposure_ev", 0.0))
	var bloom: float = float(_settings_snapshot.get("bloom", 0.08))
	var temporal: float = 1.0 if bool(_settings_snapshot.get("temporal", true)) else 0.0
	var field_mode: float = 1.0 if bool(_frame_snapshot.get("field_mode", false)) else 0.0
	var background: float = 1.0 if bool(_settings_snapshot.get("background", false)) else 0.0
	var auto_exposure: float = 1.0 if bool(_settings_snapshot.get("auto_exposure", false)) else 0.0
	var current_source: float = float(_frame_snapshot.get("source_epoch", 0))
	var resize_epoch: float = float(_frame_snapshot.get("resize_epoch", 0))
	var composition_kind: float = float(_settings_snapshot.get("composition_kind", 0))
	var background_scale: float = clampf(
			float(_settings_snapshot.get("background_scale", 1.0)), 0.0, 1.0)
	var values: PackedFloat32Array = PackedFloat32Array([
		exposure, clampf(bloom, 0.0, 0.35), temporal, field_mode,
		background, 1.0 if _history_valid else 0.0,
		1.0 if _pending_reset else 0.0, auto_exposure,
		_previous_camera.origin.x, _previous_camera.origin.y,
		_previous_camera.origin.z, _previous_fov,
		_previous_camera.basis.x.x, _previous_camera.basis.x.y,
		_previous_camera.basis.x.z, float(_previous_size.x),
		_previous_camera.basis.y.x, _previous_camera.basis.y.y,
		_previous_camera.basis.y.z, float(_previous_size.y),
		(-_previous_camera.basis.z).x, (-_previous_camera.basis.z).y,
		(-_previous_camera.basis.z).z, float(_previous_source_epoch),
		current_source, resize_epoch, composition_kind, background_scale,
	])
	var bytes := values.to_byte_array()
	_rd.buffer_update(_params_buffer, 0, bytes.size(), bytes)
func _camera_cut(next_camera: Transform3D) -> bool:
	if _previous_camera == Transform3D():
		return false
	var reference_radius: float = maxf(
			float(_frame_snapshot.get("reference_radius", 1.0)), 1.0)
	var translation_cut: bool = _previous_camera.origin.distance_to(
			next_camera.origin) > maxf(reference_radius * 0.5, 5.0)
	var old_forward: Vector3 = -_previous_camera.basis.z.normalized()
	var next_forward: Vector3 = -next_camera.basis.z.normalized()
	var angular_cut: bool = old_forward.dot(next_forward) < 0.8
	return translation_cut or angular_cut
