extends Node
## Bounded local-RD comparison of the exact analytic field gradient and the
## original fourth-order finite-difference reference. It exercises asymmetric
## interior data, one-sided derivative shells, and the pinned moving pair.

const FieldParticleEngine = preload("res://scripts/cassi_field_particle_engine.gd")
const RANDOM_SEED := 20260907
const RANDOM_DT := 0.0005
const PAIR_DT := 0.0005
const OUTPUT_PATH := "res://_diag/field_particles/gradient_comparison.json"

var _rd: RenderingDevice
var _engine: FieldParticleEngine
var _cases: Array[Dictionary] = []


func _ready() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_abort({"finite": false, "error": "local RenderingDevice unavailable"})
		return
	_engine = FieldParticleEngine.new()
	if not _engine.setup({"rd": _rd, "rd_global": false, "owns_rd": false, "dt": RANDOM_DT}):
		_abort({"finite": false, "error": "random-case engine setup failed"})
		return
	_run_pinned_case()
	_run_random_case()
	_engine.shutdown()
	_engine = FieldParticleEngine.new()
	if not _engine.setup({
			"rd": _rd,
			"rd_global": false,
			"owns_rd": false,
			"dt": PAIR_DT,
			"moving_pair": true,
		}):
		_abort({"finite": false, "cases": _cases, "error": "moving-pair setup failed"})
		return
	_run_pair_case()
	_engine.shutdown()
	var passed: bool = _all_cases_finite()
	_write_result({"finite": passed, "cases": _cases})
	_rd.free()
	get_tree().quit(0 if passed else 1)


func _run_pinned_case() -> void:
	_cases.append(_compare_case("pinned_seed", RANDOM_DT))


func _run_random_case() -> void:
	_engine.load_vacuum()
	var state := _engine.state_bytes().to_float32_array()
	var velocities := PackedFloat32Array()
	velocities.resize(_engine.cells * FieldParticleEngine.VELOCITY_STRIDE)
	var rng := RandomNumberGenerator.new()
	rng.seed = RANDOM_SEED
	for z in range(_engine.grid_n):
		for y in range(_engine.grid_n):
			for x in range(_engine.grid_n):
				if x == 0 or y == 0 or z == 0 or x == _engine.grid_n - 1 \
						or y == _engine.grid_n - 1 or z == _engine.grid_n - 1:
					continue
				var cell := x + _engine.grid_n * (y + _engine.grid_n * z)
				var state_base := cell * FieldParticleEngine.STATE_STRIDE
				var fx := float(x) / float(_engine.grid_n - 1)
				var fy := float(y) / float(_engine.grid_n - 1)
				var fz := float(z) / float(_engine.grid_n - 1)
				var envelope := sin(PI * fx) * sin(PI * fy) * sin(PI * fz)
				var skew := 0.6 * sin(2.0 * PI * fx) + 0.35 * cos(2.0 * PI * fy) \
						- 0.2 * sin(2.0 * PI * fz)
				for component in range(FieldParticleEngine.STATE_STRIDE):
					state[state_base + component] = 0.08 * envelope \
							* (1.0 + 0.025 * float(component)) + 0.012 * skew \
							+ rng.randf_range(-0.004, 0.004)
				var velocity_base := cell * FieldParticleEngine.VELOCITY_STRIDE
				var velocity_wave := Vector3(
						cos(PI * fx) * sin(PI * fy),
						sin(PI * fy) * cos(PI * fz),
						cos(PI * fz) * sin(PI * fx))
				for component in range(FieldParticleEngine.VELOCITY_STRIDE):
					velocities[velocity_base + component] = 0.03 * (
							velocity_wave.x + 0.7 * velocity_wave.y
							+ 0.4 * velocity_wave.z) + rng.randf_range(-0.008, 0.008)
	_engine.set_state(state.to_byte_array(), velocities.to_byte_array())
	_cases.append(_compare_case("random_asymmetric_boundary", RANDOM_DT))


func _run_pair_case() -> void:
	_cases.append(_compare_case("pinned_moving_pair", PAIR_DT))


func _compare_case(label: String, step_dt: float) -> Dictionary:
	var analytic_started_usec := Time.get_ticks_usec()
	var analytic := _engine.gradient_diagnostic_bytes("analytic")
	var analytic_elapsed_usec := Time.get_ticks_usec() - analytic_started_usec
	var numeric_started_usec := Time.get_ticks_usec()
	var numeric := _engine.gradient_diagnostic_bytes("numeric")
	var numeric_elapsed_usec := Time.get_ticks_usec() - numeric_started_usec
	var raw_dir := ProjectSettings.globalize_path("res://_diag/field_particles")
	_store_f32(raw_dir.path_join("gradient_%s_analytic.f32" % label), analytic)
	_store_f32(raw_dir.path_join("gradient_%s_numeric.f32" % label), numeric)
	var max_abs := 0.0
	var max_relative := 0.0
	var l2_difference := 0.0
	var l2_reference := 0.0
	var finite := analytic.size() == numeric.size() \
			and analytic.size() == _engine.cells * FieldParticleEngine.STATE_STRIDE
	if finite:
		for index in analytic.size():
			var difference := float(analytic[index]) - float(numeric[index])
			var reference := absf(float(numeric[index]))
			max_abs = maxf(max_abs, absf(difference))
			max_relative = maxf(max_relative, absf(difference) / maxf(reference, 1.0e-7))
			l2_difference += difference * difference
			l2_reference += float(numeric[index]) * float(numeric[index])
			finite = finite and is_finite(float(analytic[index])) \
					and is_finite(float(numeric[index]))
	var normalized_l2 := sqrt(l2_difference) / maxf(sqrt(l2_reference), 1.0e-7)
	var gradient_match := finite and normalized_l2 <= 5.0e-3
	var before_state := _engine.state_bytes().to_float32_array()
	var before_energy := _engine.physical_energy()
	var before_charge := _charge(before_state)
	var before_center := _center(before_state)
	var before_catalog := _engine.object_catalog()
	var step_ok := _engine.run_steps(1, true, step_dt)
	var after_state := _engine.state_bytes().to_float32_array()
	var after_energy := _engine.physical_energy()
	var after_charge := _charge(after_state)
	var after_center := _center(after_state)
	var after_catalog := _engine.object_catalog()
	var motion_distance := before_center.distance_to(after_center)
	var object_motion_distance := _catalog_motion(before_catalog, after_catalog)
	var motion_valid := is_finite(motion_distance) and is_finite(object_motion_distance) \
			and (label != "pinned_moving_pair" or object_motion_distance > 0.0)
	finite = finite and step_ok and is_finite(before_energy) and is_finite(after_energy) \
			and is_finite(before_charge) and is_finite(after_charge) \
			and before_center.is_finite() and after_center.is_finite() and motion_valid
	return {
		"analytic_raw_path": "res://_diag/field_particles/gradient_%s_analytic.f32" % label,
		"numeric_raw_path": "res://_diag/field_particles/gradient_%s_numeric.f32" % label,
		"label": label,
		"finite": finite,
		"gradient_match": gradient_match,
		"gradient_elements": analytic.size(),
		"analytic_readback_usec": analytic_elapsed_usec,
		"numeric_readback_usec": numeric_elapsed_usec,
		"max_abs_difference": max_abs,
		"max_relative_difference": max_relative,
		"normalized_l2_difference": normalized_l2,
		"energy_before": before_energy,
		"energy_after": after_energy,
		"charge_before": before_charge,
		"charge_after": after_charge,
		"center_before": before_center,
		"center_after": after_center,
		"motion_distance": motion_distance,
		"object_motion_distance": object_motion_distance,
		"motion_valid": motion_valid,
		"step_dt": step_dt,
	}


func _charge(values: PackedFloat32Array) -> float:
	var total := 0.0
	for cell in range(_engine.cells):
		var base := cell * FieldParticleEngine.STATE_STRIDE
		total += values[base + FieldParticleEngine.CHI_RE] ** 2 \
				+ values[base + FieldParticleEngine.CHI_IM] ** 2
	return total * _engine.dx ** 3


func _center(values: PackedFloat32Array) -> Vector3:
	var total := 0.0
	var center := Vector3.ZERO
	for z in range(_engine.grid_n):
		for y in range(_engine.grid_n):
			for x in range(_engine.grid_n):
				var cell := x + _engine.grid_n * (y + _engine.grid_n * z)
				var base := cell * FieldParticleEngine.STATE_STRIDE
				var density := values[base + FieldParticleEngine.CHI_RE] ** 2 \
						+ values[base + FieldParticleEngine.CHI_IM] ** 2
				total += density
				center += Vector3(float(x) * _engine.dx - _engine.radius,
						float(y) * _engine.dx - _engine.radius,
						float(z) * _engine.dx - _engine.radius) * density
	return center / total if total > 0.0 else Vector3.ZERO

func _catalog_motion(before: Array[Dictionary], after: Array[Dictionary]) -> float:
	var maximum := 0.0
	for previous in before:
		for current in after:
			if int(previous.get("id", -1)) == int(current.get("id", -2)):
				maximum = maxf(
					maximum,
					Vector3(previous.get("center", Vector3.ZERO)).distance_to(
						Vector3(current.get("center", Vector3.ZERO))))
	return maximum


func _write_result(payload: Dictionary) -> void:
	var path := ProjectSettings.globalize_path(OUTPUT_PATH)
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(payload, "\t"))
		file.close()

func _store_f32(path: String, values: PackedFloat32Array) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_buffer(values.to_byte_array())
		file.close()

func _all_cases_finite() -> bool:
	if _cases.is_empty():
		return false
	for case_data in _cases:
		if not bool(case_data.get("finite", false)) \
				or not bool(case_data.get("gradient_match", false)):
			return false
	return true

func _abort(payload: Dictionary) -> void:
	if _engine != null:
		_engine.shutdown()
	if _rd != null:
		_rd.free()
	_write_result(payload)
	get_tree().quit(1)
