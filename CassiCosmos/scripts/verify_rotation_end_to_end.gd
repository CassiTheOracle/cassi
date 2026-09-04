extends Node
## Repeatable product regression: live merge spin reaches the production
## quaternion/publication path without planting rotation state.

const CassiPhysicsEngine = preload("res://scripts/cassi_physics_engine.gd")
const PHI := 1.618033988749895
const FIELD_Q := PHI * PHI + 1.0
const DIAG_PATH := "res://_diag/rotation_end_to_end_regression.json"
const PARTICLES := 4
const ORIENTATION_STEPS := 16
const EXPECTED_SPIN := Vector3(0.0, 0.0, -16.0)

var _failed := false
var _results := {}


func _ready() -> void:
	var rd := RenderingServer.create_local_rendering_device()
	if rd == null:
		_check("local RenderingDevice", false)
		_finish()
		return
	var engine = CassiPhysicsEngine.new()
	if not engine.setup(_config(rd)) or not engine.finish_setup():
		_check("engine setup", false)
		engine.shutdown()
		rd.free()
		_finish()
		return
	if not _plant_particle_and_field_state(engine):
		_check("particle and field upload", false)
		engine.shutdown()
		rd.free()
		_finish()
		return

	var before: Dictionary = engine.rotation_readback(true)
	engine.run_steps(1)
	var post_merge: Dictionary = engine.rotation_readback(true)
	for _orientation_step in range(ORIENTATION_STEPS):
		engine.run_steps(1)
	var final_state: Dictionary = engine.rotation_readback(true)
	var publication: Dictionary = engine.rotation_publish_state(PARTICLES)
	_evaluate(before, post_merge, final_state, publication)

	engine.shutdown()
	rd.free()
	_finish()


func _config(rd: RenderingDevice) -> Dictionary:
	return {
		"rd": rd,
		"rd_global": false,
		"owns_rd": false,
		"grid_N": 64,
		"N_particles": PARTICLES,
		"dt": 1.0e-6,
		"seed": 97100,
		"cluster_radius": 25.0,
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
		"particle_merge": true,
		"merge_cadence_steps": 1,
		"merge_virial": false,
		"rotation_stress_enabled": true,
		"rotation_grid_N": 32,
		"rotation_rungs": 3,
		"rotation_field_inertia": 2.0,
		"rotation_c_t": 0.0,
		"rotation_c_l": 0.0,
		"rotation_scale_omega": 0.0,
		"rotation_attenuation": 1.0 / PHI,
		"rotation_exchange_rate": 0.0,
		"rotation_reservoir_inertia": 3.0,
		"rotation_lower_reservoir_coupling": 0.0,
		"rotation_upper_reservoir_coupling": 0.0,
	}


func _plant_particle_and_field_state(engine) -> bool:
	var buffers: Dictionary = engine.workbench_read_buffers()
	if buffers.is_empty():
		return false
	buffers["pos"] = PackedFloat32Array([
		5.0, 0.0, 0.0, 10.0,
		5.4, 0.0, 0.0, 10.0,
		-15.0, 0.0, 0.0, 5.0,
		15.0, 0.0, 0.0, 5.0,
	])
	buffers["pvel"] = PackedFloat32Array([
		0.0, 3.0, 0.0, 0.0,
		0.0, -5.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
	])
	buffers["acc"] = _zero_floats(PARTICLES * 4)
	var cells: int = int(buffers.grid_N) * int(buffers.grid_N) * int(buffers.grid_N)
	buffers["ey"] = _uniform_field(PHI, cells)
	buffers["ei"] = _uniform_field(1.0, cells)
	buffers["q"] = _uniform_field(FIELD_Q, cells)
	buffers["vel"] = _zero_floats(cells * 4)
	var receipt: Dictionary = engine.workbench_write_buffers(buffers)
	return bool(receipt.get("ok", false))


func _evaluate(before: Dictionary, post_merge: Dictionary,
		final_state: Dictionary, publication: Dictionary) -> void:
	var merge_pos := _floats(post_merge, "pos")
	var before_spin := _floats(before, "merge_spin")
	var merge_spin := _floats(post_merge, "merge_spin")
	var before_orientation := _floats(before, "orientation")
	var merge_orientation := _floats(post_merge, "orientation")
	var final_orientation := _floats(final_state, "orientation")

	var live_after := 0
	var survivor := -1
	for particle in range(PARTICLES):
		if merge_pos[particle * 4 + 3] > 0.0:
			live_after += 1
	for particle in [0, 1]:
		if merge_pos[particle * 4 + 3] > 0.0:
			survivor = particle
	var environment_live := merge_pos[2 * 4 + 3] > 0.0 and merge_pos[3 * 4 + 3] > 0.0
	var acquired_spin := _vec3(merge_spin, survivor) if survivor >= 0 else Vector3.INF
	var spin_error := _relative(acquired_spin, EXPECTED_SPIN)
	var initial_spin_zero := _max_abs(before_spin) == 0.0
	var g97 := initial_spin_zero and live_after == 3 and survivor >= 0 \
		and environment_live and spin_error <= 1.0e-3
	_check("G97 live angular-momentum acquisition", g97)

	var identity := Vector4(0.0, 0.0, 0.0, 1.0)
	var invalid_q := Vector4(INF, INF, INF, INF)
	var before_q := _vec4(before_orientation, survivor) if survivor >= 0 else invalid_q
	var merge_q := _vec4(merge_orientation, survivor) if survivor >= 0 else invalid_q
	var final_q := _vec4(final_orientation, survivor) if survivor >= 0 else invalid_q
	var initial_identity_error := (before_q - identity).length()
	var merge_identity_error := (merge_q - identity).length()
	var orientation_change := (final_q - identity).length()
	var norm_error := absf(final_q.length() - 1.0)
	var axis_alignment := Vector3(final_q.x, final_q.y, final_q.z).dot(acquired_spin)
	var g98 := initial_identity_error <= 1.0e-7 and merge_identity_error <= 1.0e-7 \
		and orientation_change > 1.0e-6 and norm_error <= 1.0e-5 \
		and axis_alignment > 0.0 and _rotation_finite(final_state)
	_check("G98 causal orientation advance", g98)

	var sample := PackedFloat32Array(publication.get("orientation_sample", PackedFloat32Array()))
	var published_q := _vec4(sample, survivor) if sample.size() >= PARTICLES * 4 \
		else Vector4(INF, INF, INF, INF)
	var telemetry := PackedFloat32Array(publication.get("telemetry", PackedFloat32Array()))
	var publication_error := (published_q - final_q).length()
	var invalid := telemetry[7] if telemetry.size() == 16 else INF
	var reservoirs_zero := _max_abs(_floats(final_state, "reservoir_momentum")) == 0.0 \
		and _max_abs(_floats(final_state, "reservoir_momentum_next")) == 0.0
	var g99 := bool(publication.get("enabled", false)) \
		and int(publication.get("orientation_sample_count", -1)) == PARTICLES \
		and telemetry.size() == 16 and publication_error <= 1.0e-7 \
		and invalid == 0.0 and reservoirs_zero \
		and is_equal_approx(float(publication.get("reservoir_inertia", -1.0)), 3.0) \
		and float(publication.get("lower_reservoir_coupling", -1.0)) == 0.0 \
		and float(publication.get("upper_reservoir_coupling", -1.0)) == 0.0
	_check("G99 bounded production publication", g99)

	var before_ledger := _particle_ledger(before)
	var merge_ledger := _particle_ledger(post_merge)
	var momentum_error := _relative(before_ledger.p, merge_ledger.p)
	var angular_error := _relative(before_ledger.l, merge_ledger.l)
	var environment_change := _environment_change(before, post_merge)
	var g100 := momentum_error <= 1.0e-3 and angular_error <= 1.0e-3 \
		and environment_change <= 1.0e-5
	_check("G100 merge ledger closure", g100)

	_results = {
		"schema": "cassi.rotation-end-to-end.regression.v1",
		"G97": {
			"pass": g97, "live_after": live_after, "survivor": survivor,
			"spin": [acquired_spin.x, acquired_spin.y, acquired_spin.z],
			"spin_relative_error": spin_error,
		},
		"G98": {
			"pass": g98, "orientation_change": orientation_change,
			"norm_error": norm_error, "axis_alignment": axis_alignment,
		},
		"G99": {
			"pass": g99, "publication_error": publication_error,
			"orientation_sample_count": int(publication.get(
				"orientation_sample_count", -1)),
			"invalid": invalid, "reservoirs_zero": reservoirs_zero,
		},
		"G100": {
			"pass": g100, "momentum_relative_error": momentum_error,
			"angular_relative_error": angular_error,
			"environment_relative_change": environment_change,
		},
	}


func _particle_ledger(state: Dictionary) -> Dictionary:
	var pos := _floats(state, "pos")
	var vel := _floats(state, "vel")
	var spin := _floats(state, "merge_spin")
	var total_mass := 0.0
	var center_sum := Vector3.ZERO
	var total_p := Vector3.ZERO
	for particle in range(PARTICLES):
		var mass := pos[particle * 4 + 3]
		if mass <= 0.0:
			continue
		total_mass += mass
		center_sum += mass * _vec3(pos, particle)
		total_p += mass * _vec3(vel, particle)
	var center := center_sum / total_mass
	var mean_velocity := total_p / total_mass
	var total_l := Vector3.ZERO
	for particle in range(PARTICLES):
		var mass := pos[particle * 4 + 3]
		if mass <= 0.0:
			continue
		total_l += (_vec3(pos, particle) - center).cross(
			mass * (_vec3(vel, particle) - mean_velocity))
		total_l += _vec3(spin, particle)
	return {"p": total_p, "l": total_l}


func _environment_change(before: Dictionary, after: Dictionary) -> float:
	var before_pos := _floats(before, "pos")
	var after_pos := _floats(after, "pos")
	var before_vel := _floats(before, "vel")
	var after_vel := _floats(after, "vel")
	var difference_sq := 0.0
	var before_sq := 0.0
	var after_sq := 0.0
	for particle in [2, 3]:
		for component in range(4):
			for pair in [
				[before_pos, after_pos], [before_vel, after_vel],
			]:
				var a: float = pair[0][particle * 4 + component]
				var b: float = pair[1][particle * 4 + component]
				difference_sq += (b - a) * (b - a)
				before_sq += a * a
				after_sq += b * b
	return sqrt(difference_sq) / maxf(maxf(sqrt(before_sq), sqrt(after_sq)), 1.0e-30)


func _rotation_finite(state: Dictionary) -> bool:
	for key in ["orientation", "merge_spin", "telemetry"]:
		for value in _floats(state, key):
			if not is_finite(value):
				return false
	return true


func _uniform_field(value: float, count: int) -> PackedFloat32Array:
	var result := PackedFloat32Array()
	result.resize(count)
	result.fill(value)
	return result


func _zero_floats(count: int) -> PackedFloat32Array:
	var result := PackedFloat32Array()
	result.resize(count)
	return result


func _floats(state: Dictionary, key: String) -> PackedFloat32Array:
	return PackedFloat32Array(state.get(key, PackedFloat32Array()))


func _vec3(values: PackedFloat32Array, index: int) -> Vector3:
	var base := index * 4
	return Vector3(values[base], values[base + 1], values[base + 2])


func _vec4(values: PackedFloat32Array, index: int) -> Vector4:
	var base := index * 4
	return Vector4(values[base], values[base + 1], values[base + 2], values[base + 3])


func _max_abs(values: PackedFloat32Array) -> float:
	var maximum := 0.0
	for value in values:
		maximum = maxf(maximum, absf(value))
	return maximum


func _relative(a: Vector3, b: Vector3) -> float:
	return (a - b).length() / maxf(maxf(a.length(), b.length()), 1.0e-30)


func _check(label: String, passed: bool) -> void:
	print("[%s] %s" % ["PASS" if passed else "FAIL", label])
	if not passed:
		_failed = true


func _finish() -> void:
	var file := FileAccess.open(DIAG_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(_results, "  "))
		file.close()
	print("WROTE: %s" % DIAG_PATH)
	if _failed:
		get_tree().quit(1)
	else:
		print("ALL CHECKS PASSED")
		get_tree().quit(0)
