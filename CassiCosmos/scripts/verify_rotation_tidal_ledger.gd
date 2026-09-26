extends Node
## Raw live-GPU acquisition for G86-G91. Independent gates are recomputed by
## research/rotation/rotation_tidal_ledger_verify.py.

const PhysicsEngine = preload("res://scripts/cassi_physics_engine.gd")
const DIAG_PATH := "res://_diag/rotation_tidal_ledger_gpu_integrity.json"
const ACQUISITION_SOURCE := "res://scripts/verify_rotation_tidal_ledger.gd"
const PREREGISTRATION := "research/rotation/rotation_tidal_ledger_integrity_prereg.md"
const PHI := 1.618033988749895
const FIELD_Q := PHI * PHI + 1.0
const PARTICLES := 6
const CLOUD := [0, 1, 2, 3]
const ENVIRONMENT := [4, 5]
const SEED := 86091

var _rd: RenderingDevice
var _failures: Array[String] = []


func _ready() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_fail("local RenderingDevice unavailable; run windowed")
		_finish({})
		return
	var cases: Array[Dictionary] = []
	for spec in [
		{"label": "sphere_g64_dt005", "geometry": "sphere", "grid": 64, "dt": 0.005, "intervals": 16},
		{"label": "aligned_g64_dt005", "geometry": "aligned", "grid": 64, "dt": 0.005, "intervals": 16},
		{"label": "plus_g64_dt010", "geometry": "plus", "grid": 64, "dt": 0.010, "intervals": 8},
		{"label": "plus_g64_dt005", "geometry": "plus", "grid": 64, "dt": 0.005, "intervals": 16},
		{"label": "plus_g64_dt0025", "geometry": "plus", "grid": 64, "dt": 0.0025, "intervals": 32},
		{"label": "minus_g64_dt005", "geometry": "minus", "grid": 64, "dt": 0.005, "intervals": 16},
		{"label": "plus_g128_dt005", "geometry": "plus", "grid": 128, "dt": 0.005, "intervals": 16},
	]:
		var result := _run_tidal_case(spec)
		cases.append(result)
		if not bool(result.get("ok", false)):
			_fail("tidal acquisition failed: " + str(spec.label))
			break
	var merge := {}
	if _failures.is_empty():
		merge = _run_merge_partition()
		if not bool(merge.get("ok", false)):
			_fail("merge partition acquisition failed")
	var acquisition_source_sha256 := _file_sha256(ACQUISITION_SOURCE)
	if acquisition_source_sha256.length() != 64:
		_fail("could not hash acquisition source")
	var artifact := {
		"schema": "cassi.rotation-tidal-ledger.raw.v1",
		"preregistration": PREREGISTRATION,
		"physics_preregistration": "research/rotation/rotation_tidal_ledger_prereg.md",
		"acquisition_source_sha256": acquisition_source_sha256,
		"field_reset": {"ey": PHI, "ei": 1.0, "q": FIELD_Q, "field_vel": 0.0},
		"group_tags": {"cloud": CLOUD, "environment": ENVIRONMENT},
		"cases": cases,
		"merge": merge,
		"harness_failures": _failures,
	}
	_finish(artifact)


func _base_config(grid: int, dt: float, particle_count: int) -> Dictionary:
	return {
		"rd": _rd,
		"rd_global": false,
		"owns_rd": false,
		"grid_N": grid,
		"N_particles": particle_count,
		"dt": dt,
		"seed": SEED,
		"cluster_radius": 20.0 / 1.5,
		"box_scale": 1.0,
		"box_aspect": Vector3.ONE,
		"num_clusters": 1,
		"initial_radius_fraction": 0.5,
		"initial_condition": 1,
		"initial_v_circ_factor": 0.0,
		"source_strength": 0.0,
		"gravity_mode": 3,
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
		"rotation_stress_enabled": false,
	}


func _run_tidal_case(spec: Dictionary) -> Dictionary:
	var engine = PhysicsEngine.new()
	var cfg := _base_config(int(spec.grid), float(spec.dt), PARTICLES)
	if not engine.setup(cfg):
		engine.shutdown()
		return {"ok": false, "label": spec.label, "error": "engine_setup"}
	var planted := _plant_state(engine, _tidal_positions(str(spec.geometry)), _zero_vectors(PARTICLES))
	if not planted:
		engine.shutdown()
		return {"ok": false, "label": spec.label, "error": "plant_state"}

	# One completed warm-up step leaves a live cached acceleration at both
	# endpoints of every registered interval.
	engine.run_steps(1)
	var states: Array[Dictionary] = [_particle_snapshot(engine, PARTICLES)]
	for _interval in range(int(spec.intervals)):
		engine.run_steps(1)
		states.append(_particle_snapshot(engine, PARTICLES))
	var finite := true
	for state in states:
		finite = finite and _state_finite(state)
	var result := {
		"ok": finite and states.size() == int(spec.intervals) + 1,
		"label": spec.label,
		"geometry": spec.geometry,
		"grid_N": spec.grid,
		"dt": spec.dt,
		"intervals": spec.intervals,
		"duration": float(spec.dt) * int(spec.intervals),
		"extents": [20.0, 20.0, 20.0],
		"masses": [1.0, 1.0, 1.0, 1.0, 30.0, 30.0],
		"config": _config_receipt(cfg, engine),
		"states": states,
	}
	engine.shutdown()
	print("[PASS] acquired %s (%d states)" % [spec.label, states.size()])
	return result


func _tidal_positions(geometry: String) -> PackedFloat32Array:
	var cloud: Array[Vector3] = []
	if geometry == "sphere":
		cloud = [
			Vector3(1.5, 0.0, 0.0), Vector3(-1.5, 0.0, 0.0),
			Vector3(0.0, 1.5, 0.0), Vector3(0.0, -1.5, 0.0),
		]
	else:
		var theta := 0.0
		if geometry == "plus":
			theta = PI / 4.0
		elif geometry == "minus":
			theta = -PI / 4.0
		var u := Vector3(cos(theta), sin(theta), 0.0)
		var v := Vector3(-sin(theta), cos(theta), 0.0)
		cloud = [2.0 * u, -2.0 * u, 0.75 * v, -0.75 * v]
	var positions := PackedFloat32Array()
	positions.resize(PARTICLES * 4)
	for i in range(4):
		_set_particle(positions, i, cloud[i], 1.0)
	_set_particle(positions, 4, Vector3(8.0, 0.0, 0.0), 30.0)
	_set_particle(positions, 5, Vector3(-8.0, 0.0, 0.0), 30.0)
	return positions


func _plant_state(engine, positions: PackedFloat32Array,
		velocities: PackedFloat32Array) -> bool:
	var buffers: Dictionary = engine.workbench_read_buffers()
	if buffers.is_empty():
		return false
	var acceleration := _zero_vectors(positions.size() >> 2)
	var ey: PackedFloat32Array = buffers.ey
	var ei: PackedFloat32Array = buffers.ei
	var q: PackedFloat32Array = buffers.q
	var field_vel: PackedFloat32Array = buffers.vel
	ey.fill(PHI)
	ei.fill(1.0)
	q.fill(FIELD_Q)
	field_vel.fill(0.0)
	buffers["ey"] = ey
	buffers["ei"] = ei
	buffers["q"] = q
	buffers["vel"] = field_vel
	buffers["pos"] = positions
	buffers["pvel"] = velocities
	buffers["acc"] = acceleration
	var receipt: Dictionary = engine.workbench_write_buffers(buffers, false)
	return bool(receipt.get("ok", false))


func _particle_snapshot(engine, count: int) -> Dictionary:
	return {
		"pos": engine._rd.buffer_get_data(engine._pos_buf, 0, count * 16).to_float32_array(),
		"vel": engine._rd.buffer_get_data(engine._vel_buf, 0, count * 16).to_float32_array(),
		"acc": engine._rd.buffer_get_data(engine._acc_buf, 0, count * 16).to_float32_array(),
	}


func _run_merge_partition() -> Dictionary:
	const MERGE_N := 4
	var engine = PhysicsEngine.new()
	var cfg := _base_config(64, 1.0e-6, MERGE_N)
	cfg["cluster_radius"] = 25.0
	cfg["gravity_mode"] = 2
	cfg["particle_merge"] = true
	cfg["merge_cadence_steps"] = 1
	cfg["merge_virial"] = false
	if not engine.setup(cfg):
		engine.shutdown()
		return {"ok": false, "error": "engine_setup"}
	var positions := PackedFloat32Array([
		5.0, 0.0, 0.0, 10.0,
		5.4, 0.0, 0.0, 10.0,
		-15.0, 0.0, 0.0, 5.0,
		15.0, 0.0, 0.0, 5.0,
	])
	var velocities := PackedFloat32Array([
		0.0, 3.0, 0.0, 0.0,
		0.0, -5.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
	])
	if not _plant_state(engine, positions, velocities):
		engine.shutdown()
		return {"ok": false, "error": "plant_state"}
	var before := _particle_snapshot(engine, MERGE_N)
	before["merge_spin"] = engine._rd.buffer_get_data(
		engine._merge_spin_buf, 0, MERGE_N * 16).to_float32_array()
	engine.run_steps(1)
	var after := _particle_snapshot(engine, MERGE_N)
	after["merge_spin"] = engine._rd.buffer_get_data(
		engine._merge_spin_buf, 0, MERGE_N * 16).to_float32_array()
	var live := 0
	for i in range(MERGE_N):
		if float(after.pos[i * 4 + 3]) > 0.0:
			live += 1
	var finite := _state_finite(before) and _state_finite(after) \
			and _array_finite(before.merge_spin) and _array_finite(after.merge_spin)
	var result := {
		"ok": finite,
		"dt": 1.0e-6,
		"grid_N": 64,
		"extents": [37.5, 37.5, 37.5],
		"config": _config_receipt(cfg, engine),
		"pair": [0, 1],
		"environment": [2, 3],
		"expected_pair_internal_L": [0.0, 0.0, -16.0],
		"live_after": live,
		"before": before,
		"after": after,
	}
	engine.shutdown()
	print("[%s] acquired merge partition (live=%d)" % ["PASS" if result.ok else "FAIL", live])
	return result


func _zero_vectors(count: int) -> PackedFloat32Array:
	var values := PackedFloat32Array()
	values.resize(count * 4)
	values.fill(0.0)
	return values


func _set_particle(values: PackedFloat32Array, index: int,
		position: Vector3, mass: float) -> void:
	var base := index * 4
	values[base] = position.x
	values[base + 1] = position.y
	values[base + 2] = position.z
	values[base + 3] = mass


func _array_finite(values: PackedFloat32Array) -> bool:
	for value in values:
		if not is_finite(value):
			return false
	return true


func _state_finite(state: Dictionary) -> bool:
	return _array_finite(state.pos) and _array_finite(state.vel) \
			and _array_finite(state.acc)


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
	receipt["effective_gravity_g_n"] = engine._bh_init_bytes.decode_float(28)
	receipt["effective_gravity_g_eff"] = engine._gn_eff
	return receipt


func _file_sha256(path: String) -> String:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null:
		return ""
	var bytes := file.get_buffer(file.get_length())
	file.close()
	var context := HashingContext.new()
	if context.start(HashingContext.HASH_SHA256) != OK:
		return ""
	if context.update(bytes) != OK:
		return ""
	return context.finish().hex_encode()


func _fail(message: String) -> void:
	_failures.append(message)
	push_error("[FAIL] " + message)


func _finish(artifact: Dictionary) -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://_diag"))
	if not artifact.is_empty():
		var file := FileAccess.open(DIAG_PATH, FileAccess.WRITE)
		if file == null:
			_fail("could not write " + DIAG_PATH)
		else:
			file.store_string(JSON.stringify(artifact, "  ") + "\n")
			file.close()
	if _failures.is_empty():
		print("RAW ACQUISITION PASSED")
	get_tree().quit(0 if _failures.is_empty() else 1)
