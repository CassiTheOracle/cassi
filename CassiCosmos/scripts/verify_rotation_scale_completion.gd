extends Node

const CassiPhysicsEngine = preload("res://scripts/cassi_physics_engine.gd")
const PHI := 1.618033988749895
const ATTENUATION := 1.0 / PHI
const DIAG_PATH := "res://_diag/rotation_scale_completion_gpu.json"
const ACQUISITION_SOURCE := "res://scripts/verify_rotation_scale_completion.gd"
const PREREGISTRATION := "research/rotation/rotation_scale_completion_prereg.md"
const ROTATION_N := 4
const RUNGS := 3
const CELL := 7
const DT := 0.01
const FIELD_INERTIA := 2.0
const RESERVOIR_INERTIA := 3.0
const SCALE_OMEGA := 0.5
const SEED := Vector3(0.4, -0.2, 0.1)

var _failures: Array[String] = []


func _ready() -> void:
	var source_sha256 := _file_sha256(ACQUISITION_SOURCE)
	if source_sha256.length() != 64:
		_fail("could not hash acquisition source")
	var cases: Array[Dictionary] = []
	for spec in [
		{"label": "lower_unit", "lower": 1.0, "upper": 0.0},
		{"label": "lower_d", "lower": ATTENUATION, "upper": 0.0},
		{"label": "lower_d2", "lower": ATTENUATION * ATTENUATION, "upper": 0.0},
		{"label": "upper_d", "lower": 0.0, "upper": ATTENUATION},
		{"label": "closed", "lower": 0.0, "upper": 0.0},
	]:
		var result := _run_case(spec)
		cases.append(result)
		if not bool(result.get("ok", false)):
			_fail("case acquisition failed: %s" % spec.label)
		print("[ROTATION SCALE] acquired %s" % spec.label)

	var artifact := {
		"schema": "cassi.rotation-scale-completion.raw.v1",
		"preregistration": PREREGISTRATION,
		"acquisition_source_sha256": source_sha256,
		"constants": {
			"phi": PHI,
			"attenuation": ATTENUATION,
			"rotation_grid_N": ROTATION_N,
			"rungs": RUNGS,
			"cell": CELL,
			"dt": DT,
			"field_inertia": FIELD_INERTIA,
			"reservoir_inertia": RESERVOIR_INERTIA,
			"scale_omega": SCALE_OMEGA,
			"seed": [SEED.x, SEED.y, SEED.z],
		},
		"cases": cases,
		"harness_failures": _failures,
	}
	var file := FileAccess.open(DIAG_PATH, FileAccess.WRITE)
	if file == null:
		_fail("could not open %s" % DIAG_PATH)
	else:
		file.store_string(JSON.stringify(artifact, "  "))
		file.close()
	print("WROTE: %s" % DIAG_PATH)
	if _failures.is_empty():
		print("ROTATION SCALE ACQUISITION COMPLETE")
		get_tree().quit(0)
	else:
		for failure in _failures:
			push_error("[ROTATION SCALE] %s" % failure)
		get_tree().quit(1)


func _base_config(rd: RenderingDevice, lower: float, upper: float) -> Dictionary:
	return {
		"rd": rd,
		"rd_global": false,
		"owns_rd": false,
		"grid_N": 8,
		"N_particles": 1,
		"dt": DT,
		"seed": 92096,
		"cluster_radius": 4.0,
		"box_scale": 1.0,
		"box_aspect": Vector3.ONE,
		"num_clusters": 1,
		"initial_radius_fraction": 0.5,
		"initial_condition": 1,
		"initial_v_circ_factor": 0.0,
		"source_strength": 0.0,
		"gravity_mode": 2,
		"river_calibrate_gn": false,
		"field_attractor_init": true,
		"freeze_field": true,
		"black_holes_enabled": false,
		"bh_accretion": false,
		"dual_grid": false,
		"meshless_mode": false,
		"meshless_gravity": false,
		"gridless_physics": false,
		"particle_merge": false,
		"rotation_stress_enabled": true,
		"rotation_grid_N": ROTATION_N,
		"rotation_rungs": RUNGS,
		"rotation_field_inertia": FIELD_INERTIA,
		"rotation_c_t": 0.0,
		"rotation_c_l": 0.0,
		"rotation_scale_omega": SCALE_OMEGA,
		"rotation_attenuation": ATTENUATION,
		"rotation_exchange_rate": 0.0,
		"rotation_reservoir_inertia": RESERVOIR_INERTIA,
		"rotation_lower_reservoir_coupling": lower,
		"rotation_upper_reservoir_coupling": upper,
	}


func _run_case(spec: Dictionary) -> Dictionary:
	var rd := RenderingServer.create_local_rendering_device()
	if rd == null:
		return {"label": spec.label, "ok": false, "error": "local RD unavailable"}
	var engine = CassiPhysicsEngine.new()
	var cfg := _base_config(rd, float(spec.lower), float(spec.upper))
	if not engine.setup(cfg) or not engine.finish_setup():
		engine.shutdown()
		rd.free()
		return {"label": spec.label, "ok": false, "error": "engine setup failed"}

	var state := _seed_state()
	if not engine.rotation_write_state(state):
		engine.shutdown()
		rd.free()
		return {"label": spec.label, "ok": false, "error": "state upload failed"}
	var before := engine.rotation_readback(false)
	var stepped := engine.rotation_step_only(1)
	var after := engine.rotation_readback(false) if stepped else {}
	var finite := stepped and _state_finite(before) and _state_finite(after)
	var result := {
		"label": spec.label,
		"ok": finite,
		"lower_coupling": float(spec.lower),
		"upper_coupling": float(spec.upper),
		"config": _config_receipt(cfg, engine),
		"before_hashes": _state_hashes(before),
		"after_hashes": _state_hashes(after) if stepped else {},
		"before": before,
		"after": after,
	}
	engine.shutdown()
	rd.free()
	return result


func _seed_state() -> Dictionary:
	var cells: int = ROTATION_N * ROTATION_N * ROTATION_N
	var field_count: int = cells * RUNGS
	var reservoir_count: int = 2 * cells
	var displacement := PackedFloat32Array()
	var field_zero := PackedFloat32Array()
	var reservoir_displacement := PackedFloat32Array()
	var reservoir_zero := PackedFloat32Array()
	displacement.resize(field_count * 4)
	field_zero.resize(field_count * 4)
	reservoir_displacement.resize(reservoir_count * 4)
	reservoir_zero.resize(reservoir_count * 4)
	for rung in range(RUNGS):
		var base: int = (rung * cells + CELL) * 4
		displacement[base] = SEED.x
		displacement[base + 1] = SEED.y
		displacement[base + 2] = SEED.z
	var orientation := PackedFloat32Array([0.0, 0.0, 0.0, 1.0])
	var particle_zero := PackedFloat32Array([0.0, 0.0, 0.0, 0.0])
	return {
		"displacement": displacement,
		"momentum": field_zero,
		"momentum_next": field_zero,
		"spin_heat": field_zero,
		"reservoir_displacement": reservoir_displacement,
		"reservoir_momentum": reservoir_zero,
		"reservoir_momentum_next": reservoir_zero,
		"orientation": orientation,
		"merge_spin": particle_zero,
	}


func _state_finite(state: Dictionary) -> bool:
	for key in [
		"displacement", "momentum", "momentum_next", "spin_heat",
		"reservoir_displacement", "reservoir_momentum",
		"reservoir_momentum_next", "telemetry",
	]:
		if not state.has(key):
			return false
		for value in state[key]:
			if not is_finite(float(value)):
				return false
	return true


func _config_receipt(cfg: Dictionary, engine) -> Dictionary:
	var receipt := {}
	for key in cfg:
		if key == "rd":
			continue
		var value: Variant = cfg[key]
		if value is Vector3:
			var vector: Vector3 = value
			receipt[key] = [vector.x, vector.y, vector.z]
		else:
			receipt[key] = value
	var extents: Vector3 = engine._extents()
	receipt["effective_extents"] = [extents.x, extents.y, extents.z]
	return receipt


func _state_hashes(state: Dictionary) -> Dictionary:
	var hashes := {}
	for key in [
		"momentum", "momentum_next",
		"reservoir_momentum", "reservoir_momentum_next",
	]:
		var floats: PackedFloat32Array = state[key]
		hashes[key] = _bytes_sha256(floats.to_byte_array())
	return hashes


func _bytes_sha256(bytes: PackedByteArray) -> String:
	var context := HashingContext.new()
	if context.start(HashingContext.HASH_SHA256) != OK:
		return ""
	if context.update(bytes) != OK:
		return ""
	return context.finish().hex_encode()


func _file_sha256(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	var bytes := file.get_buffer(file.get_length())
	file.close()
	return _bytes_sha256(bytes)


func _fail(message: String) -> void:
	_failures.append(message)
