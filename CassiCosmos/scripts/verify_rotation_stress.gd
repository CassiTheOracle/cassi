extends Node3D
## Windowed local-RD verification for the default-off conservative vector-Qi
## rotation/stress sector. Frozen research inputs live in
## research/rotation/rotation_prereg.md (G78-G82); G101 is the permanent
## regression contract for the adopted explicit scale-boundary reservoirs.
##
## Run windowed (NEVER --headless):
##   Godot_v4.7.1-stable_mono_win64_console.exe --path . res://scenes/verify_rotation_stress.tscn

const PhysicsEngine = preload("res://scripts/cassi_physics_engine.gd")
const DIAG_PATH := "res://_diag/rotation_stress_gpu.json"
const GRID_N := 8
const PARTICLES := 8
const ROTATION_N := 4
const RUNGS := 3
const DT := 0.01
const EXTENT := 2.0
const FIELD_INERTIA := 2.0
const C_T := 0.4
const C_L := 0.7
const SCALE_OMEGA := 0.5
const EXCHANGE_RATE := 1.5
const PHI := 1.618033988749895
const ATTENUATION := 1.0 / PHI
const FAILURE_METRIC := 1.0e30
const RESERVOIR_INERTIA := 3.0
const RESERVOIR_COUPLING := 1.0
const RESERVOIR_CELL := 7
const RESERVOIR_SEED := Vector3(0.4, -0.2, 0.1)

var _rd: RenderingDevice = null
var _checks := 0
var _failures := 0
var _t0 := 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RenderingDevice acquired", false, "run windowed, not --headless")
		_finish()
		return
	_check("local RenderingDevice acquired", true)

	var g78 := _gate_default_off()
	var default_exchange := _gate_default_exchange_inert()
	var enabled := _gate_enabled_exchange_and_stability()
	var g79: Dictionary = enabled["G79"]
	var g80: Dictionary = enabled["G80"]
	var g82: Dictionary = enabled["G82"]
	var production_smoke: Dictionary = enabled["ProductionSmoke"]
	var g81 := _gate_attenuation()
	var g101 := _gate_reservoir_contract()
	var receipts := {
		"G78": g78.get("raw", {}),
		"enabled": enabled.get("Raw", {}),
		"G81": g81.get("raw", {}),
		"G101": g101.get("raw", {}),
	}
	var g78_observations: Dictionary = receipts["G78"].get("observations", {})
	var workbench_grid_n := int(g78_observations.get("baseline_grid_n", 0))
	g78.erase("raw")
	g81.erase("raw")
	g101.erase("raw")

	_check("G78 production default-off byte identity", _pass_g78(g78), str(g78))
	_check("default rotation exchange leaves particle motion undamped",
		bool(default_exchange.get("velocity_byte_identical", false))
		and is_zero_approx(float(default_exchange.get("heat_increment", FAILURE_METRIC)))
		and is_zero_approx(float(default_exchange.get("exchange_rate", FAILURE_METRIC))),
		str(default_exchange))
	_check("G79 GPU linear-momentum exchange", _pass_g79(g79), str(g79))
	_check("G80 GPU angular-momentum ledger", _pass_g80(g80), str(g80))
	_check("G81 GPU attenuation and null controls", _pass_g81(g81), str(g81))
	_check("G82 object orientation and 64-step stability", _pass_g82(g82), str(g82))
	_check("G101 explicit scale-boundary reservoir contract",
		_pass_g101(g101), str(g101))
	print("[%s] supplemental enabled production dispatch smoke %s" % [
		"PASS" if _pass_production_smoke(production_smoke) else "FAIL", production_smoke])

	var artifact := {
		"schema": "cassi.rotation.gpu.v3",
		"parameters": {
			"grid_n": ROTATION_N,
			"rungs": RUNGS,
			"particle_count": PARTICLES,
			"workbench_grid_n": workbench_grid_n,
			"dt": DT,
			"extents": [EXTENT, EXTENT, EXTENT],
			"field_inertia": FIELD_INERTIA,
			"c_t": C_T,
			"c_l": C_L,
			"scale_omega": SCALE_OMEGA,
			"exchange_rate": EXCHANGE_RATE,
			"attenuation": ATTENUATION,
			"reservoir_inertia": RESERVOIR_INERTIA,
			"reservoir_coupling": RESERVOIR_COUPLING,
		},
		"gates": {
			"G78": g78, "G79": g79, "G80": g80, "G81": g81,
			"G82": g82, "G101": g101,
		},
		"receipts": receipts,
		"smoke": {"production_step": production_smoke},
		"regressions": {"default_exchange_inert": default_exchange},
	}
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://_diag"))
	var file := FileAccess.open(DIAG_PATH, FileAccess.WRITE)
	if file == null:
		_check("GPU artifact written", false, DIAG_PATH)
	else:
		file.store_string(JSON.stringify(artifact, "  "))
		file.close()
		_check("GPU artifact written", true, DIAG_PATH)
	_finish()


func _base_config() -> Dictionary:
	return {
		"rd": _rd,
		"rd_global": false,
		"owns_rd": false,
		"grid_N": GRID_N,
		"N_particles": PARTICLES,
		"dt": DT,
		"seed": 78082,
		"cluster_radius": EXTENT / 1.5,
		"box_scale": 1.0,
		"box_aspect": Vector3.ONE,
		"num_clusters": 1,
		"initial_radius_fraction": 0.5,
		"source_strength": 0.0,
		"gravity_mode": 0,
		"black_holes_enabled": false,
		"bh_accretion": false,
		"dual_grid": false,
		"meshless_mode": false,
		"meshless_gravity": false,
		"gridless_physics": false,
		"particle_merge": false,
	}


func _rotation_config(attenuation: float, with_merge_spin: bool) -> Dictionary:
	var cfg := _base_config()
	cfg["rotation_stress_enabled"] = true
	cfg["rotation_grid_N"] = ROTATION_N
	cfg["rotation_rungs"] = RUNGS
	cfg["rotation_field_inertia"] = FIELD_INERTIA
	cfg["rotation_c_t"] = C_T
	cfg["rotation_c_l"] = C_L
	cfg["rotation_scale_omega"] = SCALE_OMEGA
	cfg["rotation_attenuation"] = attenuation
	cfg["rotation_exchange_rate"] = EXCHANGE_RATE
	cfg["particle_merge"] = with_merge_spin
	return cfg


func _make_engine(cfg: Dictionary, label: String):
	var engine = PhysicsEngine.new()
	if not engine.setup(cfg):
		_check("%s engine setup" % label, false, "setup returned false")
		engine.shutdown()
		return null
	return engine


func _gate_default_off() -> Dictionary:
	var baseline_cfg := _base_config()
	var explicit_cfg := _base_config()
	explicit_cfg["rotation_stress_enabled"] = false
	var baseline := _run_complete_engine(baseline_cfg, "G78 baseline")
	var explicit := _run_complete_engine(explicit_cfg, "G78 explicit-off")
	var baseline_buffers: Dictionary = baseline.get("buffers", {})
	var explicit_buffers: Dictionary = explicit.get("buffers", {})
	var baseline_ready := bool(baseline.get("ready", false))
	var explicit_ready := bool(explicit.get("ready", false))
	var baseline_disabled := bool(baseline.get("disabled", false))
	var explicit_disabled := bool(explicit.get("disabled", false))
	var baseline_grid_n := int(baseline_buffers.get("grid_N", 0))
	var explicit_grid_n := int(explicit_buffers.get("grid_N", 0))
	var disabled_readback := baseline_disabled and explicit_disabled
	return {
		"byte_identical": baseline_ready and explicit_ready \
			and _same_contract(baseline_buffers, explicit_buffers),
		"disabled_readback": disabled_readback,
		"baseline_ready": baseline_ready,
		"explicit_off_ready": explicit_ready,
		"raw": {
			"baseline": _contract_receipts(baseline_buffers),
			"explicit_off": _contract_receipts(explicit_buffers),
			"observations": {
				"baseline_ready": baseline_ready,
				"explicit_off_ready": explicit_ready,
				"baseline_disabled": baseline_disabled,
				"explicit_off_disabled": explicit_disabled,
				"baseline_grid_n": baseline_grid_n,
				"explicit_off_grid_n": explicit_grid_n,
			},
		},
	}


func _run_complete_engine(cfg: Dictionary, label: String) -> Dictionary:
	var engine = _make_engine(cfg, label)
	if engine == null:
		return {"ready": false, "disabled": false, "buffers": {}}
	var ready: bool = engine.workbench_ready()
	engine.run_steps(2)
	var buffers: Dictionary = engine.workbench_read_buffers()
	var rotation: Dictionary = engine.rotation_readback()
	var disabled: bool = not bool(rotation.get("enabled", true)) \
		and not engine._rotation_displacement_buf.is_valid() \
		and not engine._rotation_pipe.is_valid()
	engine.shutdown()
	return {"ready": ready, "disabled": disabled, "buffers": buffers}


func _same_contract(a: Dictionary, b: Dictionary) -> bool:
	for key in ["pos", "pvel", "acc", "ey", "ei", "q"]:
		var av := _float_array(a, key)
		var bv := _float_array(b, key)
		if av.to_byte_array() != bv.to_byte_array():
			return false
	return true


func _gate_default_exchange_inert() -> Dictionary:
	var cfg := _rotation_config(ATTENUATION, false)
	cfg.erase("rotation_exchange_rate")
	cfg["rotation_c_t"] = 0.0
	cfg["rotation_c_l"] = 0.0
	cfg["rotation_scale_omega"] = 0.0
	var engine = _make_engine(cfg, "default exchange")
	if engine == null:
		return {
			"exchange_rate": FAILURE_METRIC,
			"velocity_byte_identical": false,
			"heat_increment": FAILURE_METRIC,
		}
	if not _plant_particles(engine, _particle_positions(), _particle_velocities()):
		_check("default exchange particle state planted", false)
		engine.shutdown()
		return {
			"exchange_rate": FAILURE_METRIC,
			"velocity_byte_identical": false,
			"heat_increment": FAILURE_METRIC,
		}
	var before: Dictionary = engine.rotation_readback(true)
	var exchange_rate: float = engine.rotation_exchange_rate
	var stepped: bool = engine.rotation_step_only(256)
	var after: Dictionary = engine.rotation_readback(true) if stepped else {}
	var before_vel := _float_array(before, "vel")
	var after_vel := _float_array(after, "vel")
	var result := {
		"exchange_rate": exchange_rate,
		"velocity_byte_identical": stepped
			and before_vel.to_byte_array() == after_vel.to_byte_array(),
		"heat_increment": _heat(after) - _heat(before) if stepped else FAILURE_METRIC,
	}
	engine.shutdown()
	return result


func _gate_enabled_exchange_and_stability() -> Dictionary:
	var failed := {
		"G79": {"linear_relative_error": FAILURE_METRIC, "heat_increment": -1.0},
		"G80": {"angular_relative_error": FAILURE_METRIC, "spin_error_separation": 0.0},
		"G82": {
			"orientation_delta": 0.0,
			"quaternion_norm_error": FAILURE_METRIC,
			"zero_spin_identity_error": FAILURE_METRIC,
			"finite_64_steps": false,
			"linear_momentum_drift": FAILURE_METRIC,
			"angular_momentum_drift": FAILURE_METRIC,
		},
		"ProductionSmoke": {"finite": false, "occupied_cells": 0.0},
		"Raw": {},
	}
	var engine = _make_engine(_rotation_config(ATTENUATION, true), "G79-G82")
	if engine == null:
		return failed
	if not _plant_particles(engine, _particle_positions(), _particle_velocities()):
		_check("G79-G82 particle state planted", false)
		engine.shutdown()
		return failed
	var field_count := ROTATION_N * ROTATION_N * ROTATION_N * RUNGS
	var displacement := _zero_floats(field_count * 4)
	var momentum := _zero_floats(field_count * 4)
	var spin_heat := _zero_floats(field_count * 4)
	var orientation := _identity_orientations()
	var merge_spin := _zero_floats(PARTICLES * 4)
	var occupied_cell := _particle_cell(Vector3(-1.45, -1.15, -0.35))
	momentum[occupied_cell * 4 + 0] = 0.14
	momentum[occupied_cell * 4 + 1] = -0.09
	momentum[occupied_cell * 4 + 2] = 0.03
	merge_spin[2] = 0.6
	merge_spin[2 * 4 + 0] = 0.2
	var seeded: bool = engine.rotation_write_state({
		"displacement": displacement,
		"momentum": momentum,
		"momentum_next": momentum.duplicate(),
		"spin_heat": spin_heat,
		"orientation": orientation,
		"merge_spin": merge_spin,
	})
	if not seeded:
		_check("G79-G82 rotation state planted", false)
		engine.shutdown()
		return failed

	var before: Dictionary = engine.rotation_readback(true)
	var before_ledger := _ledger(before, true)
	var before_orientation := _quaternion(_float_array(before, "orientation"), 0)
	if not engine.rotation_step_only(1):
		_check("G79-G82 first isolated step", false)
		engine.shutdown()
		return failed
	var after_one: Dictionary = engine.rotation_readback(true)
	var after_ledger := _ledger(after_one, true)
	var after_without_spin := _ledger(after_one, false)
	var linear_error := _relative_vector(after_ledger["p"], before_ledger["p"])
	var angular_error := _relative_vector(after_ledger["l"], before_ledger["l"])
	var no_spin_error := _relative_vector(after_without_spin["l"], before_ledger["l"])
	var heat_increment := _heat(after_one) - _heat(before)
	var after_orientation := _quaternion(_float_array(after_one, "orientation"), 0)
	var zero_spin_orientation := _quaternion(_float_array(after_one, "orientation"), 1)
	var identity := Vector4(0.0, 0.0, 0.0, 1.0)

	if not engine.rotation_step_only(63):
		_check("G82 remaining isolated steps", false)
		engine.shutdown()
		return failed
	var final_state: Dictionary = engine.rotation_readback(true)
	var final_ledger := _ledger(final_state, true)
	engine.run_steps(1)
	var production_state: Dictionary = engine.rotation_readback(true)
	var production_telemetry := _float_array(production_state, "telemetry")
	var production_occupied := production_telemetry[5] \
		if production_telemetry.size() > 5 else 0.0
	var result := {
		"G79": {
			"linear_relative_error": linear_error,
			"heat_increment": heat_increment,
		},
		"G80": {
			"angular_relative_error": angular_error,
			"spin_error_separation": no_spin_error / maxf(angular_error, 1.0e-30),
		},
		"G82": {
			"orientation_delta": (after_orientation - before_orientation).length(),
			"quaternion_norm_error": absf(after_orientation.length() - 1.0),
			"zero_spin_identity_error": (zero_spin_orientation - identity).length(),
			"finite_64_steps": _rotation_state_finite(final_state),
			"linear_momentum_drift": _relative_vector(final_ledger["p"], before_ledger["p"]),
			"angular_momentum_drift": _relative_vector(final_ledger["l"], before_ledger["l"]),
		},
		"ProductionSmoke": {
			"finite": _rotation_state_finite(production_state),
			"occupied_cells": production_occupied,
		},
		"Raw": {
			"before": _state_receipts(before, true),
			"after_one": _state_receipts(after_one, true),
			"after_64": _state_receipts(final_state, true),
		},
	}
	engine.shutdown()
	return result


func _gate_attenuation() -> Dictionary:
	var d_run := _run_scale_case(ATTENUATION, 0)
	var one_run := _run_scale_case(1.0, 0)
	var zero_run := _run_scale_case(1.0, 1)
	var equal_run := _run_scale_case(1.0, 2)
	var denominator: float = float(one_run.get("impulse_norm", 0.0))
	var ratio := float(d_run.get("impulse_norm", 0.0)) / maxf(denominator, 1.0e-30)
	return {
		"attenuation_relative_error": absf(ratio - ATTENUATION) / ATTENUATION,
		"null_max_abs": maxf(float(zero_run.get("max_abs", FAILURE_METRIC)),
			float(equal_run.get("max_abs", FAILURE_METRIC))),
		"finite": bool(d_run.get("finite", false)) and bool(one_run.get("finite", false)) \
			and bool(zero_run.get("finite", false)) and bool(equal_run.get("finite", false)),
		"raw": {
			"attenuated": d_run.get("raw", {}),
			"unit": one_run.get("raw", {}),
			"zero": zero_run.get("raw", {}),
			"equal": equal_run.get("raw", {}),
		},
	}


## pattern: 0 = rung-0 contrast, 1 = all zero, 2 = equal-rung constant.
func _run_scale_case(attenuation: float, pattern: int) -> Dictionary:
	var engine = _make_engine(_rotation_config(attenuation, false), "G81")
	if engine == null:
		return {"impulse_norm": 0.0, "max_abs": FAILURE_METRIC, "finite": false, "raw": {}}
	var dead_positions := _zero_floats(PARTICLES * 4)
	var dead_velocities := _zero_floats(PARTICLES * 4)
	if not _plant_particles(engine, dead_positions, dead_velocities):
		engine.shutdown()
		return {"impulse_norm": 0.0, "max_abs": FAILURE_METRIC, "finite": false, "raw": {}}
	var cells := ROTATION_N * ROTATION_N * ROTATION_N
	var field_count := cells * RUNGS
	var displacement := _zero_floats(field_count * 4)
	if pattern == 0:
		for cell in range(cells):
			displacement[cell * 4] = 0.2
	elif pattern == 2:
		for field_index in range(field_count):
			displacement[field_index * 4] = 0.2
	var zero_field := _zero_floats(field_count * 4)
	var seeded: bool = engine.rotation_write_state({
		"displacement": displacement,
		"momentum": zero_field,
		"momentum_next": zero_field.duplicate(),
		"spin_heat": zero_field.duplicate(),
		"orientation": _identity_orientations(),
	})
	if not seeded or not engine.rotation_step_only(1):
		engine.shutdown()
		return {"impulse_norm": 0.0, "max_abs": FAILURE_METRIC, "finite": false, "raw": {}}
	var state: Dictionary = engine.rotation_readback(false)
	var field_momentum := _float_array(state, "momentum")
	var norm_sq := 0.0
	for cell in range(cells):
		var value := _vec3(field_momentum, cell)
		norm_sq += value.length_squared()
	var result := {
		"impulse_norm": sqrt(norm_sq),
		"max_abs": _max_abs(field_momentum),
		"finite": _rotation_state_finite(state),
		"raw": _state_receipts(state, false),
	}
	engine.shutdown()
	return result


func _gate_reservoir_contract() -> Dictionary:
	var active := _run_reservoir_case(RESERVOIR_COUPLING)
	var closed := _run_reservoir_case(0.0)
	var failure_vector := Vector3(FAILURE_METRIC, FAILURE_METRIC, FAILURE_METRIC)
	var active_field: Vector3 = active.get("field_impulse", failure_vector)
	var active_reservoir: Vector3 = active.get("reservoir_impulse", failure_vector)
	var active_total: Vector3 = active.get("total_momentum", failure_vector)
	var expected_field: Vector3 = RESERVOIR_SEED * (
		-FIELD_INERTIA * DT * SCALE_OMEGA * SCALE_OMEGA * RESERVOIR_COUPLING)
	var expected_reservoir := -expected_field
	var expected_norm := maxf(expected_field.length(), 1.0e-30)
	var telemetry_lower := float(active.get("telemetry_lower", FAILURE_METRIC))
	return {
		"active_analytic_relative_error": maxf(
			_relative_vector(active_field, expected_field),
			_relative_vector(active_reservoir, expected_reservoir)),
		"active_pair_relative_error":
			(active_field + active_reservoir).length() / expected_norm,
		"active_total_relative_error": active_total.length() / expected_norm,
		"active_telemetry_relative_error":
			absf(telemetry_lower - expected_norm) / expected_norm,
		"closed_max_abs": float(closed.get("momentum_max_abs", FAILURE_METRIC)),
		"closed_byte_zero": bool(closed.get("momentum_byte_zero", false)),
		"finite": bool(active.get("finite", false)) and bool(closed.get("finite", false)),
		"raw": {
			"active": active.get("raw", {}),
			"closed": closed.get("raw", {}),
			"expected_field_impulse": [
				expected_field.x, expected_field.y, expected_field.z],
			"expected_reservoir_impulse": [
				expected_reservoir.x, expected_reservoir.y, expected_reservoir.z],
		},
	}


func _run_reservoir_case(lower_coupling: float) -> Dictionary:
	var failed := {
		"field_impulse": Vector3(FAILURE_METRIC, FAILURE_METRIC, FAILURE_METRIC),
		"reservoir_impulse": Vector3(FAILURE_METRIC, FAILURE_METRIC, FAILURE_METRIC),
		"total_momentum": Vector3(FAILURE_METRIC, FAILURE_METRIC, FAILURE_METRIC),
		"telemetry_lower": FAILURE_METRIC,
		"momentum_max_abs": FAILURE_METRIC,
		"momentum_byte_zero": false,
		"finite": false,
		"raw": {},
	}
	var cfg := _rotation_config(ATTENUATION, false)
	cfg["rotation_c_t"] = 0.0
	cfg["rotation_c_l"] = 0.0
	cfg["rotation_exchange_rate"] = 0.0
	cfg["rotation_reservoir_inertia"] = RESERVOIR_INERTIA
	cfg["rotation_lower_reservoir_coupling"] = lower_coupling
	cfg["rotation_upper_reservoir_coupling"] = 0.0
	var engine = _make_engine(cfg, "G101")
	if engine == null:
		return failed
	if not _plant_particles(
			engine, _zero_floats(PARTICLES * 4), _zero_floats(PARTICLES * 4)):
		engine.shutdown()
		return failed

	var cells := ROTATION_N * ROTATION_N * ROTATION_N
	var field_count := cells * RUNGS
	var reservoir_count := 2 * cells
	var displacement := _zero_floats(field_count * 4)
	for rung in range(RUNGS):
		var base := (rung * cells + RESERVOIR_CELL) * 4
		displacement[base] = RESERVOIR_SEED.x
		displacement[base + 1] = RESERVOIR_SEED.y
		displacement[base + 2] = RESERVOIR_SEED.z
	var field_zero := _zero_floats(field_count * 4)
	var reservoir_zero := _zero_floats(reservoir_count * 4)
	var seeded: bool = engine.rotation_write_state({
		"displacement": displacement,
		"momentum": field_zero,
		"momentum_next": field_zero.duplicate(),
		"spin_heat": field_zero.duplicate(),
		"reservoir_displacement": reservoir_zero,
		"reservoir_momentum": reservoir_zero.duplicate(),
		"reservoir_momentum_next": reservoir_zero.duplicate(),
		"orientation": _identity_orientations(),
		"merge_spin": _zero_floats(PARTICLES * 4),
	})
	if not seeded or not engine.rotation_step_only(1):
		engine.shutdown()
		return failed

	var state: Dictionary = engine.rotation_readback(false)
	var field_momentum := _float_array(state, "momentum")
	var field_momentum_next := _float_array(state, "momentum_next")
	var reservoir_momentum := _float_array(state, "reservoir_momentum")
	var reservoir_momentum_next := _float_array(state, "reservoir_momentum_next")
	var telemetry := _float_array(state, "telemetry")
	var valid_shape := field_momentum.size() == field_count * 4 \
		and field_momentum_next.size() == field_count * 4 \
		and reservoir_momentum.size() == reservoir_count * 4 \
		and reservoir_momentum_next.size() == reservoir_count * 4 \
		and telemetry.size() == 16
	if not valid_shape:
		engine.shutdown()
		return failed
	var field_impulse := _vec3(field_momentum, RESERVOIR_CELL)
	var reservoir_impulse := _vec3(reservoir_momentum, RESERVOIR_CELL)
	var momentum_max_abs := maxf(
		maxf(_max_abs(field_momentum), _max_abs(field_momentum_next)),
		maxf(_max_abs(reservoir_momentum), _max_abs(reservoir_momentum_next)))
	var byte_zero := _is_byte_zero(field_momentum) \
		and _is_byte_zero(field_momentum_next) \
		and _is_byte_zero(reservoir_momentum) \
		and _is_byte_zero(reservoir_momentum_next)
	var result := {
		"field_impulse": field_impulse,
		"reservoir_impulse": reservoir_impulse,
		"total_momentum": _sum_vec3(field_momentum) + _sum_vec3(reservoir_momentum),
		"telemetry_lower": telemetry[8],
		"momentum_max_abs": momentum_max_abs,
		"momentum_byte_zero": byte_zero,
		"finite": _rotation_state_finite(state),
		"raw": _state_receipts(state, false),
	}
	engine.shutdown()
	return result


func _sum_vec3(values: PackedFloat32Array) -> Vector3:
	var total := Vector3.ZERO
	for index in range(int(values.size() / 4)):
		total += _vec3(values, index)
	return total


func _is_byte_zero(values: PackedFloat32Array) -> bool:
	return values.to_byte_array() == _zero_floats(values.size()).to_byte_array()


func _plant_particles(engine, positions: PackedFloat32Array,
		velocities: PackedFloat32Array) -> bool:
	var buffers: Dictionary = engine.workbench_read_buffers()
	buffers["pos"] = positions
	buffers["pvel"] = velocities
	buffers["acc"] = _zero_floats(PARTICLES * 4)
	var receipt: Dictionary = engine.workbench_write_buffers(buffers, true)
	return bool(receipt.get("ok", false))


func _particle_positions() -> PackedFloat32Array:
	return PackedFloat32Array([
		-1.45, -1.15, -0.35, 1.0,
		-0.25, 0.75, 1.25, 2.0,
		0.85, -0.75, 0.65, 1.5,
		1.25, 1.15, 0.55, 0.75,
		-0.2, 1.45, 1.1, 1.25,
		1.45, -1.35, 0.15, 0.9,
		-0.55, 0.25, 1.45, 1.1,
		1.35, 0.15, -1.4, 0.8,
	])


func _particle_velocities() -> PackedFloat32Array:
	return PackedFloat32Array([
		0.42, -0.15, 0.08, 0.0,
		-0.11, 0.36, -0.04, 0.0,
		0.25, 0.18, -0.17, 0.0,
		-0.31, -0.09, 0.22, 0.0,
		0.06, -0.2, 0.11, 0.0,
		-0.18, 0.11, 0.05, 0.0,
		0.03, 0.12, -0.07, 0.0,
		0.12, -0.04, 0.14, 0.0,
	])


func _identity_orientations() -> PackedFloat32Array:
	var orientations := _zero_floats(PARTICLES * 4)
	for particle in range(PARTICLES):
		orientations[particle * 4 + 3] = 1.0
	return orientations


func _particle_cell(position: Vector3) -> int:
	var unit := (position + Vector3.ONE * EXTENT) / (2.0 * EXTENT)
	var x := posmod(int(floor(unit.x * ROTATION_N)), ROTATION_N)
	var y := posmod(int(floor(unit.y * ROTATION_N)), ROTATION_N)
	var z := posmod(int(floor(unit.z * ROTATION_N)), ROTATION_N)
	return (x * ROTATION_N + y) * ROTATION_N + z


func _cell_center(cell: int) -> Vector3:
	var x := cell / (ROTATION_N * ROTATION_N)
	var remainder := cell - x * ROTATION_N * ROTATION_N
	var y := remainder / ROTATION_N
	var z := remainder - y * ROTATION_N
	var h := 2.0 * EXTENT / float(ROTATION_N)
	return Vector3(
		-EXTENT + (float(x) + 0.5) * h,
		-EXTENT + (float(y) + 0.5) * h,
		-EXTENT + (float(z) + 0.5) * h)


func _ledger(state: Dictionary, include_spin: bool) -> Dictionary:
	var positions := _float_array(state, "pos")
	var velocities := _float_array(state, "vel")
	var momentum := _float_array(state, "momentum")
	var spin_heat := _float_array(state, "spin_heat")
	var total_p := Vector3.ZERO
	var total_l := Vector3.ZERO
	for particle in range(PARTICLES):
		var base := particle * 4
		var mass := positions[base + 3]
		if mass <= 0.0:
			continue
		var particle_p := mass * _vec3(velocities, particle)
		total_p += particle_p
		total_l += _vec3(positions, particle).cross(particle_p)
	var cells := ROTATION_N * ROTATION_N * ROTATION_N
	for field_index in range(cells * RUNGS):
		var field_p := _vec3(momentum, field_index)
		total_p += field_p
		total_l += _cell_center(field_index % cells).cross(field_p)
		if include_spin:
			total_l += _vec3(spin_heat, field_index)
	return {"p": total_p, "l": total_l}


func _heat(state: Dictionary) -> float:
	var spin_heat := _float_array(state, "spin_heat")
	var total := 0.0
	for field_index in range(spin_heat.size() / 4):
		total += spin_heat[field_index * 4 + 3]
	return total


func _rotation_state_finite(state: Dictionary) -> bool:
	for key in [
			"displacement", "momentum", "momentum_next", "spin_heat",
			"reservoir_displacement", "reservoir_momentum",
			"reservoir_momentum_next", "orientation", "telemetry",
	]:
		if not _array_finite(_float_array(state, key)):
			return false
	for key in ["pos", "vel", "merge_spin"]:
		if state.has(key) and not _array_finite(_float_array(state, key)):
			return false
	return true


func _array_finite(values: PackedFloat32Array) -> bool:
	for value in values:
		if not is_finite(value):
			return false
	return true


func _max_abs(values: PackedFloat32Array) -> float:
	var result := 0.0
	for value in values:
		result = maxf(result, absf(value))
	return result


func _relative_vector(actual: Vector3, expected: Vector3) -> float:
	return (actual - expected).length() / maxf(expected.length(), 1.0e-30)


func _quaternion(values: PackedFloat32Array, index: int) -> Vector4:
	var base := index * 4
	return Vector4(values[base], values[base + 1], values[base + 2], values[base + 3])


func _vec3(values: PackedFloat32Array, index: int) -> Vector3:
	var base := index * 4
	return Vector3(values[base], values[base + 1], values[base + 2])


func _float_array(state: Dictionary, key: String) -> PackedFloat32Array:
	var value: Variant = state.get(key, PackedFloat32Array())
	if value is PackedFloat32Array:
		return value
	return PackedFloat32Array()

func _receipt(values: PackedFloat32Array, shape: Array) -> Dictionary:
	return {
		"dtype": "<f4",
		"shape": shape,
		"base64": Marshalls.raw_to_base64(values.to_byte_array()),
	}


func _contract_receipts(buffers: Dictionary) -> Dictionary:
	var receipts := {}
	var positions := _float_array(buffers, "pos")
	var particle_count := int(positions.size() / 4)
	receipts["pos"] = _receipt(positions, [particle_count, 4])
	for key in ["pvel", "acc"]:
		receipts[key] = _receipt(
			_float_array(buffers, key), [particle_count, 4])
	var grid_n := int(buffers.get("grid_N", 0))
	for key in ["ey", "ei", "q"]:
		receipts[key] = _receipt(
			_float_array(buffers, key), [grid_n, grid_n, grid_n])
	return receipts


func _state_receipts(state: Dictionary, include_particles: bool) -> Dictionary:
	var receipts := {}
	var field_shape := [RUNGS, ROTATION_N, ROTATION_N, ROTATION_N, 4]
	for key in ["displacement", "momentum", "momentum_next", "spin_heat"]:
		receipts[key] = _receipt(_float_array(state, key), field_shape)
	var reservoir_shape := [2, ROTATION_N, ROTATION_N, ROTATION_N, 4]
	for key in [
			"reservoir_displacement", "reservoir_momentum",
			"reservoir_momentum_next",
	]:
		receipts[key] = _receipt(_float_array(state, key), reservoir_shape)
	receipts["orientation"] = _receipt(
		_float_array(state, "orientation"), [PARTICLES, 4])
	var telemetry := _float_array(state, "telemetry")
	receipts["telemetry"] = _receipt(telemetry, [telemetry.size()])
	if include_particles:
		for key in ["pos", "vel", "merge_spin"]:
			receipts[key] = _receipt(_float_array(state, key), [PARTICLES, 4])
	return receipts


func _zero_floats(count: int) -> PackedFloat32Array:
	var values := PackedFloat32Array()
	values.resize(count)
	values.fill(0.0)
	return values


func _pass_g78(gate: Dictionary) -> bool:
	return bool(gate.get("byte_identical", false)) \
		and bool(gate.get("disabled_readback", false)) \
		and bool(gate.get("baseline_ready", false)) \
		and bool(gate.get("explicit_off_ready", false))


func _pass_g79(gate: Dictionary) -> bool:
	var linear := float(gate.get("linear_relative_error", FAILURE_METRIC))
	var heat := float(gate.get("heat_increment", -1.0))
	return is_finite(linear) and linear <= 2.0e-5 \
		and is_finite(heat) and heat >= 0.0


func _pass_g80(gate: Dictionary) -> bool:
	var angular := float(gate.get("angular_relative_error", FAILURE_METRIC))
	var separation := float(gate.get("spin_error_separation", 0.0))
	return is_finite(angular) and angular <= 5.0e-4 \
		and is_finite(separation) and separation >= 10.0


func _pass_g81(gate: Dictionary) -> bool:
	var attenuation_error := float(gate.get("attenuation_relative_error", FAILURE_METRIC))
	var null_max := float(gate.get("null_max_abs", FAILURE_METRIC))
	return is_finite(attenuation_error) and attenuation_error <= 2.0e-4 \
		and is_finite(null_max) and null_max <= 1.0e-6 \
		and bool(gate.get("finite", false))


func _pass_g82(gate: Dictionary) -> bool:
	var orientation_delta := float(gate.get("orientation_delta", 0.0))
	var norm_error := float(gate.get("quaternion_norm_error", FAILURE_METRIC))
	var identity_error := float(gate.get("zero_spin_identity_error", FAILURE_METRIC))
	var linear_drift := float(gate.get("linear_momentum_drift", FAILURE_METRIC))
	var angular_drift := float(gate.get("angular_momentum_drift", FAILURE_METRIC))
	return is_finite(orientation_delta) and orientation_delta > 1.0e-6 \
		and is_finite(norm_error) and norm_error <= 1.0e-5 \
		and is_finite(identity_error) and identity_error <= 1.0e-6 \
		and bool(gate.get("finite_64_steps", false)) \
		and is_finite(linear_drift) and linear_drift <= 5.0e-4 \
		and is_finite(angular_drift) and angular_drift <= 5.0e-3


func _pass_g101(gate: Dictionary) -> bool:
	var analytic := float(gate.get("active_analytic_relative_error", FAILURE_METRIC))
	var pair := float(gate.get("active_pair_relative_error", FAILURE_METRIC))
	var total := float(gate.get("active_total_relative_error", FAILURE_METRIC))
	var telemetry := float(gate.get(
		"active_telemetry_relative_error", FAILURE_METRIC))
	var closed := float(gate.get("closed_max_abs", FAILURE_METRIC))
	return bool(gate.get("finite", false)) \
		and is_finite(analytic) and analytic <= 2.0e-5 \
		and is_finite(pair) and pair <= 2.0e-6 \
		and is_finite(total) and total <= 2.0e-6 \
		and is_finite(telemetry) and telemetry <= 2.0e-5 \
		and closed == 0.0 and bool(gate.get("closed_byte_zero", false))


func _pass_production_smoke(smoke: Dictionary) -> bool:
	var occupied := float(smoke.get("occupied_cells", 0.0))
	return bool(smoke.get("finite", false)) \
		and is_finite(occupied) and occupied > 0.0


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	if _rd != null:
		_rd.free()
		_rd = null
	var elapsed := Time.get_ticks_msec() - _t0
	print("[VerifyRotationStress] checks=%d failures=%d elapsed=%d ms" % [
		_checks, _failures, elapsed])
	print("[VerifyRotationStress] RESULT: %s" % ("PASS" if _failures == 0 else "FAIL"))
	get_tree().quit(0 if _failures == 0 else 1)
