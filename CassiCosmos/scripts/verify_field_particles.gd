extends Node
## Focused acceptance arm for the default-off PA11/PA12 field-particle runtime.
## Run windowed; this machine exposes no RenderingDevice to headless scenes.

const FieldParticleEngine = preload("res://scripts/cassi_field_particle_engine.gd")
const SEED_PATH := "res://data/field_particles/localized_x2_n29.f32"
const EXPECTED_SOURCE_SHA256 := "db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0"
const EXPECTED_OUTPUT_SHA256 := "5d43794099f52f4343486a2f1b38787356301153bd48d033d0d42451160ab6d3"
const EXPECTED_ENERGY := 1.5251878559994063
const EXPECTED_OMEGA := 0.0034164531971490053
const STATIONARY_DT := 0.01
const STATIONARY_STEPS := 64
const BOOST_DT := 0.01
const BOOST_STEPS := 40
const BOOST_SPEED := 0.10

var _rd: RenderingDevice
var _engine
var _checks := 0
var _failures := 0
var _results: Array[Dictionary] = []
var _started_ms := 0
var _diag_dir := ""


func _ready() -> void:
	_started_ms = Time.get_ticks_msec()
	_diag_dir = ProjectSettings.globalize_path("res://_diag/field_particles")
	DirAccess.make_dir_recursive_absolute(_diag_dir)
	_rd = RenderingServer.create_local_rendering_device()
	_check("local RenderingDevice acquired", _rd != null, "run this scene windowed")
	if _rd == null:
		_finish()
		return
	_engine = FieldParticleEngine.new()
	_check("FP0: field engine setup", _engine.setup({
		"rd": _rd,
		"rd_global": false,
		"owns_rd": false,
		"dt": STATIONARY_DT,
	}))
	if not _engine.is_ready():
		_finish()
		return
	_run_contract()
	_finish()


func _run_contract() -> void:
	var manifest: Dictionary = _engine.manifest()
	_check("FP0: source hash pinned",
		str(manifest.get("source_sha256", "")) == EXPECTED_SOURCE_SHA256)
	_check("FP0: runtime hash pinned",
		str(manifest.get("output_sha256", "")) == EXPECTED_OUTPUT_SHA256)
	_check("FP0: qualified grid and carrier registered",
		int(manifest.get("grid_n", 0)) == 29
		and absf(float(manifest.get("radius", 0.0)) - 4.0) <= 1.0e-12
		and absf(float(manifest.get("dx", 0.0)) - 2.0 / 7.0) <= 1.0e-12
		and absf(float(manifest.get("coefficients", {}).get("h_C", 0.0)) - 2.9598260763447164) <= 1.0e-12
		and absf(float(manifest.get("coefficients", {}).get("q_C", 0.0)) - 4.0) <= 1.0e-12
		and absf(float(manifest.get("omega_c", 0.0)) - EXPECTED_OMEGA) <= 1.0e-15)

	var seed := FileAccess.get_file_as_bytes(SEED_PATH)
	var imported: PackedByteArray = _engine.state_bytes()
	_check("FP1: runtime import is byte-identical", imported == seed,
		"bytes=%d" % imported.size())
	var initial: Dictionary = _engine.observables()
	_check("FP2: all seed values finite", bool(initial["finite"]))
	_check("FP2: carrier charge agrees with Q_C=4",
		absf(float(initial["charge"]) - 4.0) / 4.0 <= 2.0e-5,
		"Q=%.12f" % float(initial["charge"]))
	_check("FP2: carrier center lies within one cell",
		Vector3(initial["center"]).length() <= _engine.dx,
		"center=%s" % str(initial["center"]))
	_check("FP2: carrier outer fraction is bounded",
		float(initial["outer_carrier_fraction"]) <= 2.0e-4,
		"outer=%.12f" % float(initial["outer_carrier_fraction"]))
	_check("FP2: PA12 physical energy matches source",
		absf(float(initial["physical_energy"]) - EXPECTED_ENERGY) / EXPECTED_ENERGY <= 5.0e-4,
		"E=%.12f" % float(initial["physical_energy"]))
	_check("FP6: pinned seed resolves to one field object",
		int(initial["component_count"]) == 1,
		"objects=%d" % int(initial["component_count"]))

	var before_zero: PackedByteArray = _engine.state_bytes()
	_check("FP3: zero-step dispatch executes", _engine.run_steps(1, true, 0.0))
	var after_zero: PackedByteArray = _engine.state_bytes()
	_check("FP3: zero-step canonical state is byte-identical",
		before_zero == after_zero, "different_bytes=%d" % _byte_difference_count(before_zero, after_zero))
	_store_bytes(_diag_dir.path_join("seed_state.f32"), after_zero)
	_store_bytes(_diag_dir.path_join("seed_gradient.f32"), _engine.hamiltonian_gradient_bytes())

	var gauss_start: float = _engine.gauss_rms()
	_check("FP5: initial temporal-gauge Gauss residual",
		gauss_start <= 2.0e-4, "rms=%.12f" % gauss_start)

	var catalog_a: Array[Dictionary] = _engine.object_catalog()
	var catalog_b: Array[Dictionary] = _engine.object_catalog()
	_check("FP6: repeated catalog reads are identical",
		var_to_bytes(catalog_a) == var_to_bytes(catalog_b))
	_check("FP6: seed catalog contains one field object",
		catalog_a.size() == 1, "objects=%d" % catalog_a.size())
	_check("FP6: seed catalog carries complete charge",
		absf(_catalog_charge(catalog_a) - float(initial["charge"])) / 4.0 <= 2.0e-5,
		"catalog=%.12f direct=%.12f" % [
			_catalog_charge(catalog_a), float(initial["charge"])])
	var control_state: PackedByteArray = _engine.state_bytes()
	var control_velocity: PackedByteArray = _engine.velocity_bytes()
	_check("FP6: retained-catalog control step", _engine.run_steps(1, true, STATIONARY_DT))
	var retained_next: PackedByteArray = _engine.state_bytes()
	_check("FP6: control state restored", _engine.set_state(control_state, control_velocity))
	_engine.clear_object_catalog()
	var catalog_c: Array[Dictionary] = _engine.object_catalog()
	_check("FP6: reconstructed catalog equals retained catalog",
		var_to_bytes(catalog_a) == var_to_bytes(catalog_c))
	_check("FP6: reconstructed-catalog control step", _engine.run_steps(1, true, STATIONARY_DT))
	var reconstructed_next: PackedByteArray = _engine.state_bytes()
	_check("FP6: catalogs cannot change field evolution",
		retained_next == reconstructed_next,
		"different_bytes=%d" % _byte_difference_count(retained_next, reconstructed_next))
	var catalog_control := _run_two_gaussian_catalog_control()

	_check("FP4: stationary seed restored", _engine.reset_seed())
	var stationary_initial_bytes: PackedByteArray = _engine.state_bytes()
	var stationary_initial: PackedFloat32Array = stationary_initial_bytes.to_float32_array()
	var stationary_initial_observables: Dictionary = _engine.observables()
	var center_cell := _carrier_peak_cell(stationary_initial)
	var center_base := center_cell * FieldParticleEngine.STATE_STRIDE
	var initial_phase := atan2(
		stationary_initial[center_base + FieldParticleEngine.CHI_IM],
		stationary_initial[center_base + FieldParticleEngine.CHI_RE])
	var stationary_started := Time.get_ticks_msec()
	_check("FP4: stationary short run executes",
		_engine.run_steps(STATIONARY_STEPS, true, STATIONARY_DT))
	var stationary_ms := Time.get_ticks_msec() - stationary_started
	var stationary_final_bytes: PackedByteArray = _engine.state_bytes()
	var stationary_final: PackedFloat32Array = stationary_final_bytes.to_float32_array()
	var stationary_final_observables: Dictionary = _engine.observables()
	var final_phase := atan2(
		stationary_final[center_base + FieldParticleEngine.CHI_IM],
		stationary_final[center_base + FieldParticleEngine.CHI_RE])
	var phase_delta := wrapf(final_phase - initial_phase, -PI, PI)
	var elapsed_time := STATIONARY_DT * STATIONARY_STEPS
	var measured_omega := -phase_delta / elapsed_time
	var charge_drift := absf(
		float(stationary_final_observables["charge"])
		- float(stationary_initial_observables["charge"])) / 4.0
	var density_drift := _carrier_density_rms_drift(stationary_initial, stationary_final)
	var charged_drift := _charged_field_rms_drift(stationary_initial, stationary_final)
	var energy_drift := absf(
		float(stationary_final_observables["physical_energy"])
		- float(stationary_initial_observables["physical_energy"])) / absf(
			float(stationary_initial_observables["physical_energy"]))
	_check("FP4: stationary evolution remains finite",
		bool(stationary_final_observables["finite"]))
	_check("FP6: stationary field remains one object",
		int(stationary_final_observables["component_count"]) == 1,
		"objects=%d" % int(stationary_final_observables["component_count"]))
	_check("FP4: carrier charge drift bounded", charge_drift <= 2.0e-3,
		"relative=%.12f" % charge_drift)
	_check("FP4: carrier-density RMS drift bounded", density_drift <= 2.0e-3,
		"relative=%.12f" % density_drift)
	_check("FP4: charged-field RMS drift bounded", charged_drift <= 5.0e-3,
		"relative=%.12f" % charged_drift)
	_check("RK4: stationary PA12 energy drift bounded", energy_drift <= 5.0e-3,
		"relative=%.12f" % energy_drift)
	_check("RK4: stationary localization remains bounded",
		float(stationary_final_observables["outer_carrier_fraction"]) <= 2.0e-4,
		"outer=%.12f" % float(stationary_final_observables["outer_carrier_fraction"]))
	_check("FP4: carrier phase advances as exp(-i omega_C t)", phase_delta < 0.0,
		"delta=%.12f" % phase_delta)
	_check("FP4: carrier phase rate matches omega_C",
		absf(measured_omega - EXPECTED_OMEGA) / EXPECTED_OMEGA <= 0.20,
		"measured=%.12f expected=%.12f" % [measured_omega, EXPECTED_OMEGA])
	var gauss_final: float = _engine.gauss_rms()
	_check("FP5: evolved temporal-gauge Gauss residual bounded",
		gauss_final <= 2.0e-3, "rms=%.12f" % gauss_final)

	_check("vacuum control loads", _engine.load_vacuum())
	_check("FP6: exact vacuum catalog is empty", _engine.object_catalog().is_empty())
	var vacuum_before: PackedByteArray = _engine.state_bytes()
	_check("vacuum control evolves", _engine.run_steps(2, true, STATIONARY_DT))
	var vacuum_after: PackedByteArray = _engine.state_bytes()
	var vacuum_delta := _float_delta_metrics(vacuum_before, vacuum_after)
	_check("RK4: vacuum numerical residual bounded",
		float(vacuum_delta["max_abs"]) <= 2.0e-6,
		JSON.stringify(vacuum_delta))
	_check("FP6: evolved vacuum catalog is empty", _engine.object_catalog().is_empty())

	_check("boost control seed restored", _engine.reset_seed())
	_check("boost control initialized", _engine.apply_boost(Vector3.RIGHT, BOOST_SPEED))
	var boosted_initial: Dictionary = _engine.observables()
	_check("FP6: boosted seed starts as one object",
		int(boosted_initial["component_count"]) == 1,
		"objects=%d" % int(boosted_initial["component_count"]))
	var boost_started := Time.get_ticks_msec()
	_check("FP7: boosted short run executes", _engine.run_steps(BOOST_STEPS, true, BOOST_DT))
	var boost_ms := Time.get_ticks_msec() - boost_started
	var boosted_final: Dictionary = _engine.observables()
	_check("FP6: boosted field remains one object",
		int(boosted_final["component_count"]) == 1,
		"objects=%d" % int(boosted_final["component_count"]))
	var displacement := Vector3(boosted_final["center"]).x - Vector3(boosted_initial["center"]).x
	var retained_fraction := float(boosted_final["charge"]) / float(boosted_initial["charge"])
	_check("FP7: derived center moves with selected boost", displacement > 0.0,
		"dx=%.12f" % displacement)
	_check("FP7: boosted carrier retains at least 99 percent charge",
		retained_fraction >= 0.99, "retained=%.12f" % retained_fraction)

	var legacy: Dictionary = _engine.legacy_dispatch_counts()
	_check("FP8: Field Particles records no point-particle dispatches",
		int(legacy["deposit"]) == 0 and int(legacy["kdk"]) == 0
		and int(legacy["accretion"]) == 0 and int(legacy["merge"]) == 0,
		str(legacy))
	_check("FP9: focused runtime remains within arm timeout",
		stationary_ms + boost_ms < 220000,
		"stationary_ms=%d boost_ms=%d" % [stationary_ms, boost_ms])

	var report := {
		"schema": "cassi.field-particle-runtime-report.v1",
		"manifest": manifest,
		"initial": initial,
		"stationary": {
			"dt": STATIONARY_DT,
			"steps": STATIONARY_STEPS,
			"wall_ms": stationary_ms,
			"charge_drift": charge_drift,
			"carrier_density_rms_drift": density_drift,
			"charged_field_rms_drift": charged_drift,
			"energy_drift": energy_drift,
			"phase_delta": phase_delta,
			"measured_omega": measured_omega,
			"gauss_initial": gauss_start,
			"gauss_final": gauss_final,
			"final": stationary_final_observables,
		},
		"vacuum": vacuum_delta,
		"boost": {
			"dt": BOOST_DT,
			"steps": BOOST_STEPS,
			"speed": BOOST_SPEED,
			"wall_ms": boost_ms,
			"displacement_x": displacement,
			"retained_fraction": retained_fraction,
			"initial": boosted_initial,
			"final": boosted_final,
		},
		"legacy_dispatches": legacy,
		"catalog_control": catalog_control,
		"checks_before_independent_verifier": _results,
	}
	_store_json(_diag_dir.path_join("runtime_report.json"), report)
	_run_independent_verifier()


func _run_independent_verifier() -> void:
	var script := ProjectSettings.globalize_path(
		"res://research/field_particles/verify_field_particle_runtime.py")
	var state_path := _diag_dir.path_join("seed_state.f32")
	var gradient_path := _diag_dir.path_join("seed_gradient.f32")
	var result_path := _diag_dir.path_join("independent_verification.json")
	var output: Array = []
	var exit_code := OS.execute("python", PackedStringArray([
		script,
		"--state", state_path,
		"--gradient", gradient_path,
		"--expect-seed-exact",
		"--output", result_path,
	]), output, true)
	_check("independent NumPy energy and gradient verifier", exit_code == 0,
		"exit=%d output=%s" % [exit_code, "\n".join(output)])


func _run_two_gaussian_catalog_control() -> Dictionary:
	_check("FP6: two-object control starts from vacuum", _engine.load_vacuum())
	var values: PackedFloat32Array = _engine.state_bytes().to_float32_array()
	var velocities: PackedByteArray = _engine.velocity_bytes()
	var half_grid := 0.5 * float(_engine.grid_n - 1)
	var sigma := 0.45
	var inverse_two_sigma2 := 0.5 / (sigma * sigma)
	var direct_density_sum := 0.0
	for z in range(1, _engine.grid_n - 1):
		for y in range(1, _engine.grid_n - 1):
			for x in range(1, _engine.grid_n - 1):
				var position := Vector3(
					(float(x) - half_grid) * _engine.dx,
					(float(y) - half_grid) * _engine.dx,
					(float(z) - half_grid) * _engine.dx)
				var left_offset := position - Vector3(-1.5, 0.0, 0.0)
				var right_offset := position - Vector3(1.5, 0.0, 0.0)
				var carrier := (
					exp(-left_offset.length_squared() * inverse_two_sigma2)
					+ exp(-right_offset.length_squared() * inverse_two_sigma2))
				var cell: int = x + int(_engine.grid_n) * (y + int(_engine.grid_n) * z)
				var base: int = cell * FieldParticleEngine.STATE_STRIDE
				values[base + FieldParticleEngine.CHI_RE] = carrier
				values[base + FieldParticleEngine.CHI_IM] = 0.0
				direct_density_sum += carrier * carrier
	_check("FP6: two-object control loads",
		_engine.set_state(values.to_byte_array(), velocities))
	var catalog: Array[Dictionary] = _engine.object_catalog()
	var direct_charge: float = (
		direct_density_sum * float(_engine.dx) * float(_engine.dx) * float(_engine.dx))
	var catalog_charge := _catalog_charge(catalog)
	_check("FP6: two-Gaussian control resolves to two field objects",
		catalog.size() == 2, "objects=%d" % catalog.size())
	_check("FP6: two-object catalog conserves carrier charge",
		absf(catalog_charge - direct_charge) / direct_charge <= 2.0e-5,
		"catalog=%.12f direct=%.12f" % [catalog_charge, direct_charge])
	var opposite_sides := false
	if catalog.size() == 2:
		var first_x := Vector3(catalog[0]["center"]).x
		var second_x := Vector3(catalog[1]["center"]).x
		opposite_sides = minf(first_x, second_x) < 0.0 and maxf(first_x, second_x) > 0.0
	_check("FP6: two-object centers lie on opposite sides", opposite_sides)
	return {
		"object_count": catalog.size(),
		"catalog_charge": catalog_charge,
		"direct_charge": direct_charge,
		"objects": catalog,
	}


func _catalog_charge(catalog: Array[Dictionary]) -> float:
	var charge := 0.0
	for object in catalog:
		charge += float(object["charge"])
	return charge


func _carrier_peak_cell(values: PackedFloat32Array) -> int:
	var peak_cell := 0
	var peak_density := -1.0
	for cell in range(_engine.cells):
		var base := cell * FieldParticleEngine.STATE_STRIDE
		var density := (
			values[base + FieldParticleEngine.CHI_RE] * values[base + FieldParticleEngine.CHI_RE]
			+ values[base + FieldParticleEngine.CHI_IM] * values[base + FieldParticleEngine.CHI_IM])
		if density > peak_density:
			peak_density = density
			peak_cell = cell
	return peak_cell


func _carrier_density_rms_drift(
	before: PackedFloat32Array,
	after: PackedFloat32Array
) -> float:
	var difference_squares := 0.0
	var reference_squares := 0.0
	for cell in range(_engine.cells):
		var base := cell * FieldParticleEngine.STATE_STRIDE
		var before_density := (
			before[base + FieldParticleEngine.CHI_RE] * before[base + FieldParticleEngine.CHI_RE]
			+ before[base + FieldParticleEngine.CHI_IM] * before[base + FieldParticleEngine.CHI_IM])
		var after_density := (
			after[base + FieldParticleEngine.CHI_RE] * after[base + FieldParticleEngine.CHI_RE]
			+ after[base + FieldParticleEngine.CHI_IM] * after[base + FieldParticleEngine.CHI_IM])
		var difference := after_density - before_density
		difference_squares += difference * difference
		reference_squares += before_density * before_density
	return sqrt(difference_squares / maxf(reference_squares, 1.0e-30))


func _charged_field_rms_drift(
	before: PackedFloat32Array,
	after: PackedFloat32Array
) -> float:
	var difference_squares := 0.0
	var reference_squares := 0.0
	for cell in range(_engine.cells):
		var base := cell * FieldParticleEngine.STATE_STRIDE
		for component in 4:
			var difference := after[base + component] - before[base + component]
			difference_squares += difference * difference
			reference_squares += before[base + component] * before[base + component]
	return sqrt(difference_squares / maxf(reference_squares, 1.0e-30))


func _float_delta_metrics(left: PackedByteArray, right: PackedByteArray) -> Dictionary:
	var left_values := left.to_float32_array()
	var right_values := right.to_float32_array()
	if left_values.size() != right_values.size():
		return {"max_abs": INF, "rms": INF, "changed_floats": -1}
	var max_abs := 0.0
	var sum_squares := 0.0
	var changed := 0
	for index in left_values.size():
		var difference := absf(right_values[index] - left_values[index])
		max_abs = maxf(max_abs, difference)
		sum_squares += difference * difference
		if difference > 0.0:
			changed += 1
	return {
		"max_abs": max_abs,
		"rms": sqrt(sum_squares / float(maxi(left_values.size(), 1))),
		"changed_floats": changed,
		"different_bytes": _byte_difference_count(left, right),
	}


func _byte_difference_count(left: PackedByteArray, right: PackedByteArray) -> int:
	if left.size() != right.size():
		return maxi(left.size(), right.size())
	var count := 0
	for index in left.size():
		if left[index] != right[index]:
			count += 1
	return count


func _store_bytes(path: String, bytes: PackedByteArray) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_buffer(bytes)
		file.close()


func _store_json(path: String, value: Variant) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(value, "  ", false, true) + "\n")
		file.close()


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	_results.append({"name": name, "pass": ok, "detail": detail})
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	if _engine != null:
		_engine.shutdown()
		_engine = null
	if _rd != null:
		_rd.free()
		_rd = null
	var elapsed := Time.get_ticks_msec() - _started_ms
	print("[VerifyFieldParticles] checks=%d failures=%d elapsed=%d ms" % [
		_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyFieldParticles] RESULT: PASS—FIELD-PARTICLE CATALOG RECOVERY")
	else:
		print("[VerifyFieldParticles] RESULT: FAIL—FIELD-PARTICLE CATALOG RECOVERY")
	get_tree().quit(0 if _failures == 0 else 1)
