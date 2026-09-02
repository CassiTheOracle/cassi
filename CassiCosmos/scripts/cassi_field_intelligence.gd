class_name CassiFieldIntelligence
extends RefCounted

const STATE_BYTES := 128
const CELL_BYTES := 8
const PC_FLOATS := 16
const SCHEMA_VERSION := 1
const MAX_GROUPS_X := 65535

var _rd: RenderingDevice
var _grid_n := 0
var _particle_count := 0
var _enabled := false
var _probe_index := 0
var _episode := 0
var _reward_control := 0
var _profile := ""
var _reset_eligibility_pending := false

var _plasticity_buf: RID
var _state_buf: RID
var _shader: RID
var _pipeline: RID
var _uniform_set: RID
var _pc := PackedByteArray()


func plasticity_buffer() -> RID:
	return _plasticity_buf


func state_buffer() -> RID:
	return _state_buf


func allocate_buffers(rd: RenderingDevice, grid_n: int, particle_count: int,
		enabled: bool, organ_radius: float, probe_index: int,
		reward_control: int, profile: String) -> void:
	_rd = rd
	_grid_n = maxi(grid_n, 1)
	_particle_count = maxi(particle_count, 0)
	_enabled = enabled
	_probe_index = maxi(probe_index, 0)
	_reward_control = clampi(reward_control, 0, 1)
	_episode = 0
	_profile = profile
	_reset_eligibility_pending = false

	var cells := _grid_n * _grid_n * _grid_n if _enabled else 1
	_plasticity_buf = _rd.storage_buffer_create(cells * CELL_BYTES)
	var plasticity_zero := PackedByteArray()
	plasticity_zero.resize(cells * CELL_BYTES)
	_rd.buffer_update(_plasticity_buf, 0, plasticity_zero.size(), plasticity_zero)

	_state_buf = _rd.storage_buffer_create(STATE_BYTES)
	var state := PackedByteArray()
	state.resize(STATE_BYTES)
	# organ lane @48; status @96; flags @112.
	state.encode_float(60, maxf(organ_radius, 1e-3))
	state.encode_u32(96, 1 if _enabled else 0)
	state.encode_u32(104, _probe_index)
	state.encode_u32(124, SCHEMA_VERSION | (_reward_control << 16))
	_rd.buffer_update(_state_buf, 0, STATE_BYTES, state)
	_pc.resize(PC_FLOATS * 4)


func compile_shader() -> bool:
	free_shader()
	var resource := load("res://compute/cassi_field_learn.glsl") \
			if ResourceLoader.exists("res://compute/cassi_field_learn.glsl") else null
	if resource == null:
		push_error("[FieldIntelligence] learning shader not found")
		return false
	var spirv = resource.get_spirv()
	if spirv == null:
		push_error("[FieldIntelligence] learning shader failed to compile")
		return false
	_shader = _rd.shader_create_from_spirv(spirv)
	if not _shader.is_valid():
		return false
	_pipeline = _rd.compute_pipeline_create(_shader)
	return _pipeline.is_valid()


func cache_uniform_set(position_buffer: RID) -> bool:
	free_uniform_set()
	if not _shader.is_valid() or not _plasticity_buf.is_valid() \
			or not _state_buf.is_valid() or not position_buffer.is_valid():
		return false
	_uniform_set = _rd.uniform_set_create([
		_uniform_storage(0, _plasticity_buf),
		_uniform_storage(1, _state_buf),
		_uniform_storage(2, position_buffer),
	], _shader, 0)
	return _uniform_set.is_valid()


func ready() -> bool:
	return not _enabled or (_pipeline.is_valid() and _uniform_set.is_valid())


func record_step(cl: int, extents: Vector3, params: Dictionary) -> void:
	if not _enabled or not _pipeline.is_valid() or not _uniform_set.is_valid():
		return
	_fill_pc(extents, params)
	_rd.compute_list_bind_compute_pipeline(cl, _pipeline)
	_rd.compute_list_bind_uniform_set(cl, _uniform_set, 0)

	if _reset_eligibility_pending:
		_dispatch_grid(cl, 4.0)
		_rd.compute_list_add_barrier(cl)
		_reset_eligibility_pending = false

	_dispatch_single(cl, 0.0)             # particle write -> reward header
	_rd.compute_list_add_barrier(cl)
	_dispatch_grid(cl, 1.0)               # reward header -> P/e update
	_rd.compute_list_add_barrier(cl)
	_dispatch_single(cl, 2.0)             # P/e update -> next control
	_rd.compute_list_add_barrier(cl)       # next PDE step reads the control


func set_target(target: Vector3, radius: float, training: bool) -> Dictionary:
	if not _enabled or not target.is_finite() or not is_finite(radius) or radius <= 0.0:
		return {"ok": false, "error": "invalid_target"}
	_episode += 1
	var lane := PackedByteArray()
	lane.resize(16)
	lane.encode_float(0, target.x)
	lane.encode_float(4, target.y)
	lane.encode_float(8, target.z)
	lane.encode_float(12, radius)
	_rd.buffer_update(_state_buf, 16, 16, lane)

	var zero32 := PackedByteArray()
	zero32.resize(32)
	_rd.buffer_update(_state_buf, 0, 16, zero32.slice(0, 16))
	_rd.buffer_update(_state_buf, 64, 32, zero32)

	var status := PackedByteArray()
	status.resize(16)
	status.encode_u32(0, 1)
	status.encode_u32(4, _episode)
	status.encode_u32(8, _probe_index)
	status.encode_u32(12, 0)
	_rd.buffer_update(_state_buf, 96, 16, status)

	var flags := PackedByteArray()
	flags.resize(16)
	flags.encode_u32(4, 1 if training else 0)
	flags.encode_u32(12, SCHEMA_VERSION | (_reward_control << 16))
	_rd.buffer_update(_state_buf, 112, 16, flags)
	_reset_eligibility_pending = true
	return {"ok": true, "episode": _episode}


func set_training(training: bool) -> Dictionary:
	if not _enabled:
		return {"ok": false, "error": "disabled"}
	var value := PackedByteArray()
	value.resize(4)
	value.encode_u32(0, 1 if training else 0)
	_rd.buffer_update(_state_buf, 116, 4, value)
	return {"ok": true, "training": training}

func set_runtime_enabled_for_verify(enabled: bool) -> Dictionary:
	if not _enabled:
		return {"ok": false, "error": "disabled"}
	var value := PackedByteArray()
	value.resize(4)
	value.encode_u32(0, 1 if enabled else 0)
	_rd.buffer_update(_state_buf, 96, 4, value)
	if not enabled:
		var zero := PackedByteArray(); zero.resize(16)
		_rd.buffer_update(_state_buf, 64, 16, zero)
	return {"ok": true, "enabled": enabled}


func clear() -> Dictionary:
	if not _enabled:
		return {"ok": false, "error": "disabled"}
	var zero := PackedByteArray()
	zero.resize(_grid_n * _grid_n * _grid_n * CELL_BYTES)
	_rd.buffer_update(_plasticity_buf, 0, zero.size(), zero)
	var zero16 := PackedByteArray()
	zero16.resize(16)
	var zero32 := PackedByteArray()
	zero32.resize(32)
	_rd.buffer_update(_state_buf, 0, 16, zero16)       # metrics
	_rd.buffer_update(_state_buf, 64, 32, zero32)      # control + context
	_rd.buffer_update(_state_buf, 108, 4, zero16.slice(0, 4))  # tick
	_rd.buffer_update(_state_buf, 112, 4, zero16.slice(0, 4))  # action
	_rd.buffer_update(_state_buf, 120, 4, zero16.slice(0, 4))  # faults
	_reset_eligibility_pending = false
	return {"ok": true}


func snapshot() -> Dictionary:
	if not _enabled:
		return {"ok": false, "error": "disabled"}
	var plasticity := _rd.buffer_get_data(_plasticity_buf, 0,
			_grid_n * _grid_n * _grid_n * CELL_BYTES)
	var state := _rd.buffer_get_data(_state_buf, 0, STATE_BYTES)
	if plasticity.size() != _grid_n * _grid_n * _grid_n * CELL_BYTES \
			or state.size() != STATE_BYTES:
		return {"ok": false, "error": "readback_failed"}
	return {
		"ok": true,
		"schema": SCHEMA_VERSION,
		"grid_n": _grid_n,
		"plasticity_bytes": plasticity.size(),
		"state_bytes": state.size(),
		"profile": _profile,
		"plasticity": plasticity,
		"state": state,
		"checksum": _checksum(plasticity, state, _profile),
	}


func restore(snapshot_data: Dictionary) -> Dictionary:
	if not _enabled:
		return {"ok": false, "error": "disabled"}
	if int(snapshot_data.get("schema", -1)) != SCHEMA_VERSION \
			or int(snapshot_data.get("grid_n", -1)) != _grid_n \
			or str(snapshot_data.get("profile", "")) != _profile:
		return {"ok": false, "error": "profile_mismatch"}
	var plasticity_value: Variant = snapshot_data.get("plasticity")
	var state_value: Variant = snapshot_data.get("state")
	if not plasticity_value is PackedByteArray or not state_value is PackedByteArray:
		return {"ok": false, "error": "invalid_payload"}
	var plasticity: PackedByteArray = plasticity_value
	var state: PackedByteArray = state_value
	var expected := _grid_n * _grid_n * _grid_n * CELL_BYTES
	if plasticity.size() != expected or state.size() != STATE_BYTES:
		return {"ok": false, "error": "size_mismatch"}
	if str(snapshot_data.get("checksum", "")) != _checksum(plasticity, state, _profile):
		return {"ok": false, "error": "checksum_mismatch"}
	_rd.buffer_update(_plasticity_buf, 0, plasticity.size(), plasticity)
	_rd.buffer_update(_state_buf, 0, state.size(), state)
	_episode = int(state.decode_u32(100))
	_probe_index = int(state.decode_u32(104))
	_reset_eligibility_pending = false
	return {"ok": true, "checksum": snapshot_data.checksum}


func status() -> Dictionary:
	if not _enabled:
		return {"ok": false, "error": "disabled"}
	var data := _rd.buffer_get_data(_state_buf, 0, STATE_BYTES)
	if data.size() != STATE_BYTES:
		return {"ok": false, "error": "readback_failed"}
	return {
		"ok": true,
		"distance": data.decode_float(0),
		"reward": data.decode_float(4),
		"control_energy": data.decode_float(8),
		"support_margin": data.decode_float(12),
		"target": Vector3(data.decode_float(16), data.decode_float(20), data.decode_float(24)),
		"target_radius": data.decode_float(28),
		"probe": Vector3(data.decode_float(32), data.decode_float(36), data.decode_float(40)),
		"probe_mass": data.decode_float(44),
		"organ": Vector3(data.decode_float(48), data.decode_float(52), data.decode_float(56)),
		"organ_radius": data.decode_float(60),
		"control": Vector3(data.decode_float(64), data.decode_float(68), data.decode_float(72)),
		"control_score": data.decode_float(76),
		"enabled": data.decode_u32(96) != 0,
		"episode": int(data.decode_u32(100)),
		"probe_index": int(data.decode_u32(104)),
		"tick": int(data.decode_u32(108)),
		"action": int(data.decode_u32(112)),
		"training": data.decode_u32(116) != 0,
		"faults": int(data.decode_u32(120)),
		"schema": int(data.decode_u32(124) & 0xffff),
		"reward_control": int(data.decode_u32(124) >> 16),
	}


func free_uniform_set() -> void:
	if _rd != null and _uniform_set.is_valid():
		_rd.free_rid(_uniform_set)
	_uniform_set = RID()


func free_buffers() -> void:
	if _rd != null:
		for rid in [_plasticity_buf, _state_buf]:
			if rid.is_valid():
				_rd.free_rid(rid)
	_plasticity_buf = RID()
	_state_buf = RID()


func free_shader() -> void:
	free_uniform_set()
	if _rd != null:
		if _pipeline.is_valid():
			_rd.free_rid(_pipeline)
		if _shader.is_valid():
			_rd.free_rid(_shader)
	_pipeline = RID()
	_shader = RID()


func _fill_pc(extents: Vector3, params: Dictionary) -> void:
	_pc.encode_float(0, float(_grid_n))
	_pc.encode_float(4, float(_particle_count))
	_pc.encode_float(8, extents.x)
	_pc.encode_float(12, extents.y)
	_pc.encode_float(16, extents.z)
	_pc.encode_float(20, float(params.get("eta", 0.0)))
	_pc.encode_float(24, float(params.get("gamma", 0.0)))
	_pc.encode_float(28, float(params.get("decay", 0.0)))
	_pc.encode_float(32, float(params.get("p_max", 1.0)))
	_pc.encode_float(36, float(params.get("actuation", 0.0)))
	_pc.encode_float(40, float(params.get("energy_penalty", 0.0)))
	_pc.encode_float(44, float(params.get("explore_period", 0.0)))
	_pc.encode_float(48, float(params.get("explore_steps", 0.0)))
	_pc.encode_float(52, float(params.get("context_radius", 0.0)))
	_pc.encode_float(56, float(params.get("kernel_radius", 0.0)))


func _dispatch_single(cl: int, pass_sel: float) -> void:
	_pc.encode_float(60, pass_sel)
	_rd.compute_list_set_push_constant(cl, _pc, _pc.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)


func _dispatch_grid(cl: int, pass_sel: float) -> void:
	var cells := _grid_n * _grid_n * _grid_n
	var groups := ceili(float(cells) / 64.0)
	var groups_x := mini(groups, MAX_GROUPS_X)
	var groups_y := ceili(float(groups) / float(maxi(groups_x, 1)))
	_pc.encode_float(60, pass_sel)
	_rd.compute_list_set_push_constant(cl, _pc, _pc.size())
	_rd.compute_list_dispatch(cl, groups_x, groups_y, 1)


func _uniform_storage(binding: int, buffer: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding
	uniform.add_id(buffer)
	return uniform


func _checksum(plasticity: PackedByteArray, state: PackedByteArray, profile: String) -> String:
	var hash := HashingContext.new()
	hash.start(HashingContext.HASH_SHA256)
	hash.update(profile.to_utf8_buffer())
	hash.update(plasticity)
	hash.update(state)
	return hash.finish().hex_encode()
