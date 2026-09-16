class_name CassiRadiationEngine
extends RefCounted
## Default-off, engine-owned material/radiation evolution over an explicitly
## supplied physical model.  prepare() is CPU-only; initialize() owns the GPU
## resources on the same thread as the supplied RenderingDevice.

const MATERIAL_MODEL = preload("res://scripts/cassi_radiative_material.gd")
const SHADER_PATH: String = "res://compute/cassi_radiation_coupled.glsl"
const CHECKPOINT_SCHEMA: String = "1.0.0"
const NUMERICAL_IDENTITY: String = \
		"cassi-radiation-coupled-v1:extensive-affine-pc:implicit-lte-bisection"
const C_LIGHT_M_S: float = 299792458.0
const WORKGROUP_SIZE: int = 64
const MAX_GROUPS: int = 32

var _prepared: bool = false
var _ready: bool = false
var _last_error: String = ""
var _rd: RenderingDevice = null
var _rd_global: bool = true
var _local_pending: bool = false

var _bundle: Dictionary = {}
var _model: Dictionary = {}
var _file_sha256: String = ""
var _model_sha256: String = ""
var _unit_map_sha256: String = ""
var _group_layout_sha256: String = ""
var _element_count: int = 0
var _group_count: int = 0
var _temperature_count: int = 0
var _frequency_cfl: float = 0.4
var _max_frequency_substeps: int = 1
var _source_iterations: int = 40
var _gamma: float = 5.0 / 3.0
var _specific_heat_j_kg_k: float = 0.0
var _temperature_min_k: float = 0.0
var _temperature_max_k: float = 0.0
var _time_s_per_physics_sim: float = 0.0
var _max_abs_expansion_rate: float = 0.0
var _affine_enabled: bool = true
var _frequency_enabled: bool = true
var _source_enabled: bool = true

var _initial_material_bytes: PackedByteArray = PackedByteArray()
var _initial_expansion_bytes: PackedByteArray = PackedByteArray()
var _initial_radiation_bytes: PackedByteArray = PackedByteArray()
var _initial_edge_bytes: PackedByteArray = PackedByteArray()
var _initial_opacity_bytes: PackedByteArray = PackedByteArray()
var _initial_temperature_bytes: PackedByteArray = PackedByteArray()
var _initial_lte_bytes: PackedByteArray = PackedByteArray()
var _initial_ledger_bytes: PackedByteArray = PackedByteArray()
var _initial_status_bytes: PackedByteArray = PackedByteArray()

var _shader: RID = RID()
var _pipeline: RID = RID()
var _uniform_set: RID = RID()
var _material_buffer: RID = RID()
var _expansion_buffer: RID = RID()
var _radiation_buffer: RID = RID()
var _frequency_edge_buffer: RID = RID()
var _shared_edge_buffer: RID = RID()
var _opacity_buffer: RID = RID()
var _temperature_buffer: RID = RID()
var _lte_buffer: RID = RID()
var _ledger_buffer: RID = RID()
var _status_buffer: RID = RID()
var _push_bytes: PackedByteArray = PackedByteArray()

var _accepted_step: int = 0
var _state_epoch: int = 1
var _reset_epoch: int = 1
var _physical_time_s: float = 0.0
var _pending_steps: int = 0
var _pending_time_s: float = 0.0
var _last_checkpoint_error: String = ""



## CPU-only validation and state preparation.  A fixture may be supplied
## directly for focused verification; production passes path + explicit hash.
func prepare(cfg: Dictionary) -> bool:
	if _ready or _prepared:
		return _fail("radiation engine is already prepared")
	_reset_prepared_state()
	var candidate_bundle: Dictionary = {}
	if cfg.get("bundle", null) is Dictionary:
		if not bool(cfg.get("verification_only", false)):
			return _fail("direct coupled bundles are restricted to focused verification")
		candidate_bundle = (cfg.bundle as Dictionary).duplicate(true)
		var direct_validation: Dictionary = MATERIAL_MODEL.validate_coupled_bundle(candidate_bundle)
		if not bool(direct_validation.get("ok", false)):
			return _fail(String(direct_validation.get("error", "coupled model validation failed")))
		_file_sha256 = String(cfg.get("file_sha256", ""))
		if _file_sha256.length() != 64:
			return _fail("verified direct coupled bundle requires its file SHA-256")
	else:
		var loaded: Dictionary = MATERIAL_MODEL.load_coupled_file(
				String(cfg.get("path", "")), String(cfg.get("expected_sha256", "")))
		if not bool(loaded.get("ok", false)):
			return _fail(String(loaded.get("error", "coupled material load failed")))
		candidate_bundle = (loaded.bundle as Dictionary).duplicate(true)
		_file_sha256 = String(loaded.file_sha256)
	_bundle = candidate_bundle
	_model = (_bundle.model as Dictionary).duplicate(true)
	_element_count = int(cfg.get("element_count", 0))
	if _element_count < 1 or _element_count > 1_048_576:
		return _fail("radiation element_count must be in [1, 1048576]")
	var grid: Dictionary = _model.spectral_grid
	var material: Dictionary = _model.material
	var eos: Dictionary = material.eos
	var transport: Dictionary = material.transport
	var units: Dictionary = _model.unit_map
	_group_count = int(grid.group_count)
	_temperature_count = int((material.lte_table.temperature_K as Array).size())
	_frequency_cfl = float(transport.frequency_cfl)
	_max_frequency_substeps = int(transport.max_frequency_substeps)
	_source_iterations = int(transport.source_root_iterations)
	_gamma = float(eos.gamma)
	_specific_heat_j_kg_k = float(eos.specific_heat_J_kg_K)
	_temperature_min_k = float(eos.temperature_min_K)
	_temperature_max_k = float(eos.temperature_max_K)
	_time_s_per_physics_sim = float(units.time_s_per_physics_sim)
	_model_sha256 = String(_model.model_sha256)
	_unit_map_sha256 = String(units.unit_map_sha256)
	_group_layout_sha256 = String(grid.group_layout_sha256)
	_affine_enabled = bool(cfg.get("affine_enabled", true))
	_frequency_enabled = bool(cfg.get("frequency_enabled", true))
	_source_enabled = bool(cfg.get("source_enabled", true))
	var initial: Dictionary = _runtime_initial_state(cfg.get("initial_state", null))
	var initial_error: String = _validate_runtime_initial_state(initial)
	if not initial_error.is_empty():
		return _fail(initial_error)
	_build_initial_bytes(initial)
	_prepared = true
	return true


## GPU-facing half of setup.  The caller controls the RD lifetime.
func initialize(rd: RenderingDevice, rd_global: bool,
		spirv_by_path: Dictionary = {}) -> bool:
	if not _prepared:
		return _fail("radiation engine must be prepared before initialize")
	if _ready:
		return true
	if rd == null:
		return _fail("radiation engine RenderingDevice is null")
	_rd = rd
	_rd_global = rd_global
	var spirv: RDShaderSPIRV = null
	if spirv_by_path.has(SHADER_PATH):
		spirv = spirv_by_path[SHADER_PATH] as RDShaderSPIRV
	if spirv == null:
		var shader_file := load(SHADER_PATH) as RDShaderFile
		if shader_file == null or shader_file.get_spirv() == null:
			return _fail("coupled radiation shader is missing or uncompiled")
		spirv = shader_file.get_spirv()
	_shader = _rd.shader_create_from_spirv(spirv)
	if not _shader.is_valid():
		return _fail("coupled radiation shader creation failed")
	_pipeline = _rd.compute_pipeline_create(_shader)
	if not _pipeline.is_valid():
		return _fail("coupled radiation pipeline creation failed")
	_material_buffer = _create_buffer(_initial_material_bytes)
	_expansion_buffer = _create_buffer(_initial_expansion_bytes)
	_radiation_buffer = _create_buffer(_initial_radiation_bytes)
	_frequency_edge_buffer = _create_buffer(_initial_edge_bytes)
	_shared_edge_buffer = _create_zero_buffer(_element_count * (_group_count + 1) * 4)
	_opacity_buffer = _create_buffer(_initial_opacity_bytes)
	_temperature_buffer = _create_buffer(_initial_temperature_bytes)
	_lte_buffer = _create_buffer(_initial_lte_bytes)
	_ledger_buffer = _create_buffer(_initial_ledger_bytes)
	_status_buffer = _create_buffer(_initial_status_bytes)
	for rid: RID in _data_buffers():
		if not rid.is_valid():
			return _fail("coupled radiation buffer creation failed")
	_uniform_set = _rd.uniform_set_create([
		_uniform_storage(0, _material_buffer),
		_uniform_storage(1, _expansion_buffer),
		_uniform_storage(2, _radiation_buffer),
		_uniform_storage(3, _frequency_edge_buffer),
		_uniform_storage(4, _shared_edge_buffer),
		_uniform_storage(5, _opacity_buffer),
		_uniform_storage(6, _temperature_buffer),
		_uniform_storage(7, _lte_buffer),
		_uniform_storage(8, _ledger_buffer),
		_uniform_storage(9, _status_buffer),
	], _shader, 0)
	if not _uniform_set.is_valid():
		return _fail("coupled radiation uniform-set creation failed")
	_push_bytes.resize(64)
	_ready = true
	return true


func is_prepared() -> bool:
	return _prepared


func is_ready() -> bool:
	return _ready and _last_error.is_empty()


func last_error() -> String:
	return _last_error


func last_checkpoint_error() -> String:
	return _last_checkpoint_error


func time_s_per_physics_sim() -> float:
	return _time_s_per_physics_sim


func accepted_step() -> int:
	return _accepted_step


func state_epoch() -> int:
	return _state_epoch


func resource_status() -> Dictionary:
	return {
		"prepared": _prepared,
		"ready": is_ready(),
		"shader": _shader.is_valid(),
		"pipeline": _pipeline.is_valid(),
		"uniform_set": _uniform_set.is_valid(),
		"buffer_count": _valid_buffer_count(),
		"error": _last_error,
	}


## Append one pending physical step to an already-open command list.  The
## caller commits its identity only after the enclosing submission fence.
func record_accepted_step(compute_list: int, dt_s: float) -> bool:
	if not is_ready():
		return false
	if compute_list < 0 or not is_finite(dt_s) or dt_s < 0.0:
		return _fail("invalid coupled radiation accepted-step arguments")
	var substeps: int = _frequency_substep_count(dt_s)
	if substeps > _max_frequency_substeps:
		return _fail("coupled radiation frequency substep cap exceeded")
	var sub_dt: float = dt_s / float(substeps)
	for _substep: int in substeps:
		_set_push(0, sub_dt)
		_bind_and_dispatch(compute_list, _element_count * (_group_count + 1))
		_rd.compute_list_add_barrier(compute_list)
		_set_push(1, sub_dt)
		_bind_and_dispatch(compute_list, _element_count)
		_rd.compute_list_add_barrier(compute_list)
	_set_push(2, dt_s)
	_bind_and_dispatch(compute_list, _element_count)
	_rd.compute_list_add_barrier(compute_list)
	_pending_steps += 1
	_pending_time_s += dt_s
	_local_pending = not _rd_global
	return true

## Convert the parent simulation's validated time coordinate through this
## model's hash-bound unit map before recording the accepted physical step.
func record_accepted_physics_step(compute_list: int, dt_physics_sim: float) -> bool:
	if not is_finite(dt_physics_sim) or dt_physics_sim < 0.0:
		return _fail("invalid parent physics timestep")
	return record_accepted_step(
			compute_list, dt_physics_sim * _time_s_per_physics_sim)


func record_accepted_steps(compute_list: int, count: int, dt_s: float) -> bool:
	if count < 0:
		return _fail("coupled radiation step count must be nonnegative")
	for _step: int in count:
		if not record_accepted_step(compute_list, dt_s):
			return false
	return true


## Advance host-visible identity after the caller has observed the submission
## fence.  All currently pending steps form one indivisible committed batch.
func commit_recorded_steps() -> bool:
	if not is_ready():
		return false
	if _pending_steps == 0:
		return true
	_accepted_step += _pending_steps
	_state_epoch += _pending_steps
	_physical_time_s += _pending_time_s
	_pending_steps = 0
	_pending_time_s = 0.0
	_local_pending = false
	return true


## Standalone/local-RD convenience used by the focused verifier.
func run_accepted_steps(count: int, dt_s: float) -> bool:
	if not is_ready() or _rd_global:
		return _fail("run_accepted_steps requires a ready local RenderingDevice")
	var compute_list: int = _rd.compute_list_begin()
	if not record_accepted_steps(compute_list, count, dt_s):
		_rd.compute_list_end()
		return false
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	_local_pending = false
	if not validate_status():
		return false
	return commit_recorded_steps()


func validate_status() -> bool:
	if not is_ready():
		return false
	if _local_pending:
		return _fail("coupled radiation status requested before the local submission fence")
	var values: PackedInt32Array = _rd.buffer_get_data(_status_buffer).to_int32_array()
	if values.size() != _element_count:
		return _fail("coupled radiation status readback length mismatch")
	for value: int in values:
		if value != 0:
			return _fail("coupled radiation GPU status failure: %d" % value)
	return true


## Explicit, synchronized read surface.  It is never called from the step path.
func read_state() -> Dictionary:
	if not is_ready():
		return {"ready": false, "error": _last_error}
	if _pending_steps != 0:
		return {"ready": false, "error": "coupled radiation state has an uncommitted batch"}
	var material: PackedFloat32Array = _rd.buffer_get_data(_material_buffer).to_float32_array()
	var expansion: PackedFloat32Array = _rd.buffer_get_data(_expansion_buffer).to_float32_array()
	var radiation: PackedFloat32Array = _rd.buffer_get_data(_radiation_buffer).to_float32_array()
	var ledger: PackedFloat32Array = _rd.buffer_get_data(_ledger_buffer).to_float32_array()
	var status_values: PackedInt32Array = _rd.buffer_get_data(_status_buffer).to_int32_array()
	if material.size() != _element_count * 4 or expansion.size() != _element_count \
			or radiation.size() != _element_count * _group_count \
			or ledger.size() != _element_count * 4 or status_values.size() != _element_count:
		return {"ready": false, "error": "coupled radiation state readback length mismatch"}
	var temperatures := PackedFloat32Array()
	temperatures.resize(_element_count)
	var radiation_sums := PackedFloat32Array()
	radiation_sums.resize(_element_count)
	for element: int in _element_count:
		var base: int = element * 4
		temperatures[element] = material[base + 1] \
				/ (material[base] * _specific_heat_j_kg_k)
		var radiation_sum: float = 0.0
		for group: int in _group_count:
			radiation_sum += radiation[element * _group_count + group]
		radiation_sums[element] = radiation_sum
	return {
		"ready": true,
		"material": material,
		"expansion_rate_s_inv": expansion,
		"radiation_energy_J": radiation,
		"ledger_J": ledger,
		"status": status_values,
		"temperature_K": temperatures,
		"radiation_energy_sum_J": radiation_sums,
		"accepted_step": _accepted_step,
		"state_epoch": _state_epoch,
		"reset_epoch": _reset_epoch,
		"physical_time_s": _physical_time_s,
	}


func checkpoint() -> Dictionary:
	if not is_ready():
		return {"ok": false, "error": _last_error}
	if _pending_steps != 0:
		return {"ok": false, "error": "coupled radiation checkpoint has an uncommitted batch"}
	var material_bytes: PackedByteArray = _rd.buffer_get_data(_material_buffer)
	var expansion_bytes: PackedByteArray = _rd.buffer_get_data(_expansion_buffer)
	var radiation_bytes: PackedByteArray = _rd.buffer_get_data(_radiation_buffer)
	var ledger_bytes: PackedByteArray = _rd.buffer_get_data(_ledger_buffer)
	var status_bytes: PackedByteArray = _rd.buffer_get_data(_status_buffer)
	return {
		"ok": true,
		"schema_version": CHECKPOINT_SCHEMA,
		"numerical_identity": NUMERICAL_IDENTITY,
		"model_sha256": _model_sha256,
		"unit_map_sha256": _unit_map_sha256,
		"group_layout_sha256": _group_layout_sha256,
		"element_count": _element_count,
		"group_count": _group_count,
		"accepted_step": _accepted_step,
		"state_epoch": _state_epoch,
		"reset_epoch": _reset_epoch,
		"physical_time_s": _physical_time_s,
		"material_bytes": Marshalls.raw_to_base64(material_bytes),
		"expansion_bytes": Marshalls.raw_to_base64(expansion_bytes),
		"radiation_bytes": Marshalls.raw_to_base64(radiation_bytes),
		"ledger_bytes": Marshalls.raw_to_base64(ledger_bytes),
		"status_bytes": Marshalls.raw_to_base64(status_bytes),
	}


func restore_checkpoint(value: Dictionary) -> bool:
	_last_checkpoint_error = ""
	if not is_ready():
		return false
	if _pending_steps != 0:
		_last_checkpoint_error = "cannot restore across an uncommitted radiation batch"
		return false
	var decoded: Dictionary = _validate_checkpoint(value)
	if not bool(decoded.get("ok", false)):
		_last_checkpoint_error = String(
				decoded.get("error", "invalid coupled radiation checkpoint"))
		return false
	_rd.buffer_update(_material_buffer, 0, decoded.material.size(), decoded.material)
	_rd.buffer_update(_expansion_buffer, 0, decoded.expansion.size(), decoded.expansion)
	_rd.buffer_update(_radiation_buffer, 0, decoded.radiation.size(), decoded.radiation)
	_rd.buffer_update(_ledger_buffer, 0, decoded.ledger.size(), decoded.ledger)
	_rd.buffer_update(_status_buffer, 0, decoded.status.size(), decoded.status)
	_accepted_step = int(value.accepted_step)
	_state_epoch = int(value.state_epoch)
	_reset_epoch = int(value.reset_epoch)
	_physical_time_s = float(value.physical_time_s)
	_pending_steps = 0
	_pending_time_s = 0.0
	_local_pending = false
	return true


func publication(include_state: bool = false) -> Dictionary:
	if not is_ready():
		return {
			"ready": false,
			"mode": "coupled_physical_radiation",
			"error": _last_error,
		}
	if _pending_steps != 0:
		return {
			"ready": false,
			"mode": "coupled_physical_radiation",
			"error": "coupled radiation batch is not committed",
			"pending_steps": _pending_steps,
		}
	var result := {
		"ready": true,
		"mode": "coupled_physical_radiation",
		"coupling": "coupled",
		"source_kind": String(_model.source_kind),
		"capabilities": MATERIAL_MODEL.COUPLED_ENGINE_CAPABILITIES.duplicate(),
		"model_sha256": _model_sha256,
		"unit_map_sha256": _unit_map_sha256,
		"group_layout_sha256": _group_layout_sha256,
		"file_sha256": _file_sha256,
		"numerical_identity": NUMERICAL_IDENTITY,
		"element_count": _element_count,
		"group_count": _group_count,
		"accepted_step": _accepted_step,
		"state_epoch": _state_epoch,
		"reset_epoch": _reset_epoch,
		"physical_time_s": _physical_time_s,
		"pending_steps": _pending_steps,
		"material_buffer": _material_buffer,
		"radiation_buffer": _radiation_buffer,
		"status_buffer": _status_buffer,
	}
	if include_state:
		result["state"] = read_state()
	return result


func shutdown() -> void:
	if _rd != null:
		if _uniform_set.is_valid() and _rd.uniform_set_is_valid(_uniform_set):
			_rd.free_rid(_uniform_set)
		for rid: RID in _data_buffers():
			if rid.is_valid():
				_rd.free_rid(rid)
		if _pipeline.is_valid():
			_rd.free_rid(_pipeline)
		if _shader.is_valid():
			_rd.free_rid(_shader)
	_clear_handles()
	_reset_prepared_state()


func _runtime_initial_state(override_value: Variant) -> Dictionary:
	if override_value is Dictionary:
		return (override_value as Dictionary).duplicate(true)
	var material: Dictionary = _model.material
	var initial: Dictionary = material.initial_state
	var volume: float = float(initial.volume_m3)
	var mass: float = float(initial.mass_density_kg_m3) * volume
	var internal: float = mass * _specific_heat_j_kg_k * float(initial.temperature_K)
	var radiation := []
	for density: Variant in initial.radiation_energy_density_J_m3:
		radiation.append(float(density) * volume)
	return {
		"mass_kg": mass,
		"internal_energy_J": internal,
		"volume_m3": volume,
		"expansion_rate_s_inv": float(initial.expansion_rate_s_inv),
		"radiation_energy_J": radiation,
		"low_frequency_escape_J": 0.0,
		"high_frequency_escape_J": 0.0,
		"radiation_pressure_work_J": 0.0,
		"material_radiation_transfer_J": 0.0,
	}


func _validate_runtime_initial_state(value: Dictionary) -> String:
	for key: String in ["mass_kg", "internal_energy_J", "volume_m3", "expansion_rate_s_inv"]:
		if not value.has(key) or not (value[key] is float or value[key] is int) \
				or not is_finite(float(value[key])):
			return "invalid coupled runtime initial-state field: " + key
	if float(value.mass_kg) <= 0.0 or float(value.internal_energy_J) <= 0.0 \
			or float(value.volume_m3) <= 0.0:
		return "coupled runtime mass, internal energy and volume must be positive"
	var temperature: float = float(value.internal_energy_J) \
			/ (float(value.mass_kg) * _specific_heat_j_kg_k)
	if temperature < _temperature_min_k or temperature > _temperature_max_k:
		return "coupled runtime initial temperature is outside the provider domain"
	var radiation: Variant = value.get("radiation_energy_J", [])
	if not radiation is Array or radiation.size() != _group_count:
		return "coupled runtime radiation group length mismatch"
	for energy: Variant in radiation:
		if not (energy is float or energy is int) or not is_finite(float(energy)) \
				or float(energy) < 0.0:
			return "coupled runtime radiation energy must be finite and nonnegative"
	for key: String in [
		"low_frequency_escape_J", "high_frequency_escape_J",
		"radiation_pressure_work_J", "material_radiation_transfer_J",
	]:
		if value.has(key) and (not (value[key] is float or value[key] is int) \
				or not is_finite(float(value[key]))):
			return "invalid coupled runtime ledger field: " + key
	return ""


func _build_initial_bytes(initial: Dictionary) -> void:
	var material_values := PackedFloat32Array()
	material_values.resize(_element_count * 4)
	var expansion_values := PackedFloat32Array()
	expansion_values.resize(_element_count)
	var radiation_values := PackedFloat32Array()
	radiation_values.resize(_element_count * _group_count)
	var ledger_values := PackedFloat32Array()
	ledger_values.resize(_element_count * 4)
	var radiation: Array = initial.radiation_energy_J
	_max_abs_expansion_rate = absf(float(initial.expansion_rate_s_inv))
	for element: int in _element_count:
		var material_base: int = element * 4
		material_values[material_base] = float(initial.mass_kg)
		material_values[material_base + 1] = float(initial.internal_energy_J)
		material_values[material_base + 2] = float(initial.volume_m3)
		material_values[material_base + 3] = 0.0
		expansion_values[element] = float(initial.expansion_rate_s_inv)
		for group: int in _group_count:
			radiation_values[element * _group_count + group] = float(radiation[group])
		ledger_values[material_base] = float(initial.get("low_frequency_escape_J", 0.0))
		ledger_values[material_base + 1] = float(initial.get("high_frequency_escape_J", 0.0))
		ledger_values[material_base + 2] = float(initial.get("radiation_pressure_work_J", 0.0))
		ledger_values[material_base + 3] = float(initial.get("material_radiation_transfer_J", 0.0))
	_initial_material_bytes = material_values.to_byte_array()
	_initial_expansion_bytes = expansion_values.to_byte_array()
	_initial_radiation_bytes = radiation_values.to_byte_array()
	_initial_ledger_bytes = ledger_values.to_byte_array()
	var status_values := PackedInt32Array()
	status_values.resize(_element_count)
	_initial_status_bytes = status_values.to_byte_array()
	var edges := PackedFloat32Array()
	for value: Variant in _model.spectral_grid.frequency_edges_Hz:
		edges.append(float(value))
	_initial_edge_bytes = edges.to_byte_array()
	var opacity := PackedFloat32Array()
	for value: Variant in _model.material.coefficients.absorption_m_inv:
		opacity.append(float(value))
	_initial_opacity_bytes = opacity.to_byte_array()
	var temperatures := PackedFloat32Array()
	for value: Variant in _model.material.lte_table.temperature_K:
		temperatures.append(float(value))
	_initial_temperature_bytes = temperatures.to_byte_array()
	var lte := PackedFloat32Array()
	for value: Variant in _model.material.lte_table.energy_density_J_m3:
		lte.append(float(value))
	_initial_lte_bytes = lte.to_byte_array()


func _frequency_substep_count(dt_s: float) -> int:
	if not _affine_enabled or not _frequency_enabled \
			or _max_abs_expansion_rate == 0.0 or dt_s == 0.0:
		return 1
	var edges: Array = _model.spectral_grid.frequency_edges_Hz
	var max_rate: float = 0.0
	for group: int in _group_count:
		var width: float = float(edges[group + 1]) - float(edges[group])
		max_rate = maxf(max_rate, _max_abs_expansion_rate * float(edges[group + 1]) / width)
	return maxi(1, ceili(dt_s * max_rate / _frequency_cfl))


func _set_push(mode: int, dt_s: float) -> void:
	_push_bytes.encode_u32(0, _element_count)
	_push_bytes.encode_u32(4, _group_count)
	_push_bytes.encode_u32(8, _temperature_count)
	_push_bytes.encode_u32(12, mode)
	_push_bytes.encode_float(16, dt_s)
	_push_bytes.encode_float(20, C_LIGHT_M_S)
	_push_bytes.encode_float(24, _gamma)
	_push_bytes.encode_float(28, _specific_heat_j_kg_k)
	_push_bytes.encode_u32(32, _source_iterations)
	_push_bytes.encode_u32(36, 1 if _affine_enabled else 0)
	_push_bytes.encode_u32(40, 1 if _frequency_enabled else 0)
	_push_bytes.encode_u32(44, 1 if _source_enabled else 0)
	_push_bytes.encode_float(48, _temperature_min_k)
	_push_bytes.encode_float(52, _temperature_max_k)
	_push_bytes.encode_float(56, 0.0)
	_push_bytes.encode_float(60, 0.0)


func _bind_and_dispatch(compute_list: int, invocation_count: int) -> void:
	_rd.compute_list_bind_compute_pipeline(compute_list, _pipeline)
	_rd.compute_list_bind_uniform_set(compute_list, _uniform_set, 0)
	_rd.compute_list_set_push_constant(compute_list, _push_bytes, _push_bytes.size())
	_rd.compute_list_dispatch(compute_list,
			maxi(1, ceili(float(invocation_count) / float(WORKGROUP_SIZE))), 1, 1)


func _validate_checkpoint(value: Dictionary) -> Dictionary:
	for pair: Array in [
		["schema_version", CHECKPOINT_SCHEMA],
		["numerical_identity", NUMERICAL_IDENTITY],
		["model_sha256", _model_sha256],
		["unit_map_sha256", _unit_map_sha256],
		["group_layout_sha256", _group_layout_sha256],
	]:
		if String(value.get(String(pair[0]), "")) != String(pair[1]):
			return {"ok": false, "error": "checkpoint identity mismatch: " + String(pair[0])}
	if int(value.get("element_count", -1)) != _element_count \
			or int(value.get("group_count", -1)) != _group_count:
		return {"ok": false, "error": "checkpoint shape identity mismatch"}
	for key: String in ["accepted_step", "state_epoch", "reset_epoch"]:
		if not value.has(key) or not value[key] is int or int(value[key]) < 0:
			return {"ok": false, "error": "invalid checkpoint counter: " + key}
	if not value.has("physical_time_s") \
			or not (value.physical_time_s is int or value.physical_time_s is float) \
			or not is_finite(float(value.physical_time_s)) \
			or float(value.physical_time_s) < 0.0:
		return {"ok": false, "error": "invalid checkpoint counter: physical_time_s"}
	var decoded := {
		"material": Marshalls.base64_to_raw(String(value.get("material_bytes", ""))),
		"expansion": Marshalls.base64_to_raw(String(value.get("expansion_bytes", ""))),
		"radiation": Marshalls.base64_to_raw(String(value.get("radiation_bytes", ""))),
		"ledger": Marshalls.base64_to_raw(String(value.get("ledger_bytes", ""))),
		"status": Marshalls.base64_to_raw(String(value.get("status_bytes", ""))),
	}
	for pair: Array in [
		["material", _element_count * 16],
		["expansion", _element_count * 4],
		["radiation", _element_count * _group_count * 4],
		["ledger", _element_count * 16],
		["status", _element_count * 4],
	]:
		if (decoded[String(pair[0])] as PackedByteArray).size() != int(pair[1]):
			return {"ok": false, "error": "checkpoint byte length mismatch: " + String(pair[0])}
	var material: PackedFloat32Array = \
			(decoded.material as PackedByteArray).to_float32_array()
	var expansion: PackedFloat32Array = \
			(decoded.expansion as PackedByteArray).to_float32_array()
	var radiation: PackedFloat32Array = \
			(decoded.radiation as PackedByteArray).to_float32_array()
	var ledger: PackedFloat32Array = \
			(decoded.ledger as PackedByteArray).to_float32_array()
	var status: PackedInt32Array = \
			(decoded.status as PackedByteArray).to_int32_array()
	for element: int in _element_count:
		var base: int = element * 4
		var mass: float = material[base]
		var internal_energy: float = material[base + 1]
		var volume: float = material[base + 2]
		if not is_finite(mass) or not is_finite(internal_energy) \
				or not is_finite(volume) or mass <= 0.0 \
				or internal_energy <= 0.0 or volume <= 0.0:
			return {"ok": false, "error": "checkpoint material state must be finite and positive"}
		if not is_finite(material[base + 3]) or material[base + 3] != 0.0:
			return {"ok": false, "error": "checkpoint material reserved channel is invalid"}
		var temperature: float = internal_energy / (mass * _specific_heat_j_kg_k)
		if not is_finite(temperature) or temperature < _temperature_min_k \
				or temperature > _temperature_max_k:
			return {"ok": false, "error": "checkpoint material temperature is outside the provider domain"}
		if not is_finite(expansion[element]):
			return {"ok": false, "error": "checkpoint expansion rate is nonfinite"}
		for channel: int in 4:
			var ledger_value: float = ledger[base + channel]
			if not is_finite(ledger_value):
				return {"ok": false, "error": "checkpoint ledger is nonfinite"}
			if channel < 2 and ledger_value < 0.0:
				return {"ok": false, "error": "checkpoint escape ledger is negative"}
		if status[element] != 0:
			return {"ok": false, "error": "checkpoint status is not restorable"}
	for energy: float in radiation:
		if not is_finite(energy) or energy < 0.0:
			return {"ok": false, "error": "checkpoint radiation energy must be finite and nonnegative"}
	decoded["ok"] = true
	return decoded


func _create_buffer(bytes: PackedByteArray) -> RID:
	if bytes.is_empty():
		return RID()
	var rid: RID = _rd.storage_buffer_create(bytes.size())
	if rid.is_valid():
		_rd.buffer_update(rid, 0, bytes.size(), bytes)
	return rid


func _create_zero_buffer(size_bytes: int) -> RID:
	if size_bytes <= 0:
		return RID()
	var zero := PackedByteArray()
	zero.resize(size_bytes)
	return _create_buffer(zero)


func _uniform_storage(binding: int, buffer: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding
	uniform.add_id(buffer)
	return uniform


func _data_buffers() -> Array[RID]:
	return [
		_material_buffer, _expansion_buffer, _radiation_buffer,
		_frequency_edge_buffer, _shared_edge_buffer, _opacity_buffer,
		_temperature_buffer, _lte_buffer, _ledger_buffer, _status_buffer,
	]


func _valid_buffer_count() -> int:
	var count: int = 0
	for rid: RID in _data_buffers():
		if rid.is_valid():
			count += 1
	return count


func _settle_local() -> void:
	if _rd != null and not _rd_global and _local_pending:
		_rd.submit()
		_rd.sync()
		_local_pending = false


func _clear_handles() -> void:
	_shader = RID()
	_pipeline = RID()
	_uniform_set = RID()
	_material_buffer = RID()
	_expansion_buffer = RID()
	_radiation_buffer = RID()
	_frequency_edge_buffer = RID()
	_shared_edge_buffer = RID()
	_opacity_buffer = RID()
	_temperature_buffer = RID()
	_lte_buffer = RID()
	_ledger_buffer = RID()
	_status_buffer = RID()


func _reset_prepared_state() -> void:
	_prepared = false
	_ready = false
	_last_error = ""
	_rd = null
	_rd_global = true
	_local_pending = false
	_bundle = {}
	_model = {}
	_file_sha256 = ""
	_model_sha256 = ""
	_unit_map_sha256 = ""
	_group_layout_sha256 = ""
	_element_count = 0
	_group_count = 0
	_temperature_count = 0
	_frequency_cfl = 0.4
	_max_frequency_substeps = 1
	_source_iterations = 40
	_gamma = 5.0 / 3.0
	_specific_heat_j_kg_k = 0.0
	_temperature_min_k = 0.0
	_temperature_max_k = 0.0
	_time_s_per_physics_sim = 0.0
	_max_abs_expansion_rate = 0.0
	_affine_enabled = true
	_frequency_enabled = true
	_source_enabled = true
	_initial_material_bytes = PackedByteArray()
	_initial_expansion_bytes = PackedByteArray()
	_initial_radiation_bytes = PackedByteArray()
	_initial_edge_bytes = PackedByteArray()
	_initial_opacity_bytes = PackedByteArray()
	_initial_temperature_bytes = PackedByteArray()
	_initial_lte_bytes = PackedByteArray()
	_initial_ledger_bytes = PackedByteArray()
	_initial_status_bytes = PackedByteArray()
	_push_bytes = PackedByteArray()
	_accepted_step = 0
	_state_epoch = 1
	_reset_epoch = 1
	_physical_time_s = 0.0
	_pending_steps = 0
	_pending_time_s = 0.0
	_last_checkpoint_error = ""


func _fail(message: String) -> bool:
	_last_error = message
	_ready = false
	return false
