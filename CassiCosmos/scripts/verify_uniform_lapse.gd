extends Node
## Active uniform scalar process-time probe.
##
## This verifier is deliberately separate from production.  It sends the same
## process dt and process-time t to the existing 17-float two-fluid push
## constant for baseline-A, baseline-B (duplicate OFF), and uniform-lapse.
## It is an implementation proof only: not CT-2 evidence and not universal
## physical-time evidence.  Run windowed; local RenderingDevice is unavailable
## for the unsupported headless mode.

const TWO_PI: float = 6.28318530717958647692
const PHI: float = 1.618033988749895
const GRID_N: int = 16
const CELLS: int = GRID_N * GRID_N * GRID_N
const EXTENT: float = 12.0
const OMEGA2: float = 20.0
const STEPS: int = 32
const INITIAL_SEED: int = 0x51A7
const DT_PROCESS: float = 0.005
const HAMILTONIAN_DRIFT_MAX: float = 0.01
const CLOCK_TOL: float = 1.0e-12
const RECEIPT_SCHEMA: String = "uniform_lapse_receipt/v1"
const RECEIPT_PATH: String = "res://_diag/process_time/uniform_lapse_receipt.json"
const SHADER_PATH: String = "res://compute/cassi_two_fluid.glsl"
const PREREG_PATH: String = "res://research/process_time/uniform_lapse_active_prereg.md"
const LAW_IDENTITY: String = "d2EY_dt2=L(EY)-omega2*(EY-phi*EI); d2EI_dt2=L(EI)+phi*omega2*(EY-phi*EI)"
const OPERATOR_IDENTITY: String = "L=existing periodic 19-point two-fluid Laplacian from res://compute/cassi_two_fluid.glsl"
const CANDIDATE_ROLE: String = "uniform_scalar_process_time_reparameterization"
const DEFAULT_OFF_STATE: String = "production shader unchanged; no new branch; baseline-A/B are the duplicate OFF control"
const GATE_NAMES := [
	"rd_available",
	"shader_pipeline",
	"storage_bindings",
	"exact_step_schedule",
	"finite_state",
	"baseline_off_bit_identity",
	"equal_process_age_bit_identity",
	"coordinate_process_clock",
	"hamiltonian_bounded_shadow",
	"receipt_write_reopen",
]

var _rd: RenderingDevice
var _shader: RID
var _pipe: RID
var _us: RID
var _ey: RID
var _ei: RID
var _q: RID
var _vel: RID
var _rho: RID
var _scratch: RID
var _fi_fallback: RID
var _pc := PackedFloat32Array()
var _initial_ey := PackedFloat32Array()
var _initial_ei := PackedFloat32Array()
var _zero_field := PackedByteArray()
var _zero_velocity := PackedByteArray()
var _arms: Array = []
var _gates: Dictionary = {}
var _checks: int = 0
var _failures: int = 0
var _invalid_setup: bool = false
var _t0: int = 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	print("[VerifyUniformLapse] uniform scalar process-time implementation probe")
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_invalid_setup = true
		_gate("rd_available", false, "no local RenderingDevice; run windowed, not --headless")
		_finish()
		return
	_gate("rd_available", true)
	if not _load_pipeline():
		_invalid_setup = true
		_finish()
		return
	if not _make_buffers():
		_invalid_setup = true
		_finish()
		return
	_make_initial_fields()

	# Three fresh deterministic resets.  The process PC is identical in all
	# arms; only coordinate-time bookkeeping dt_c and scalar N differ.
	_arms.append(_run_arm("baseline-A", 0.005, 1.0))
	_arms.append(_run_arm("baseline-B", 0.005, 1.0))
	_arms.append(_run_arm("uniform-lapse", 0.010, 0.5))
	_run_gates()
	_finish()


func _load_pipeline() -> bool:
	var sf: RDShaderFile = load(SHADER_PATH) as RDShaderFile
	if sf == null:
		_gate("shader_pipeline", false, "two-fluid shader failed to load")
		return false
	_shader = _rd.shader_create_from_spirv(sf.get_spirv())
	_pipe = _rd.compute_pipeline_create(_shader)
	var ok: bool = _shader.is_valid() and _pipe.is_valid()
	_gate("shader_pipeline", ok, "existing cassi_two_fluid.glsl SPIR-V compute pipeline" if ok else "shader or pipeline RID invalid")
	return ok


func _make_buffers() -> bool:
	_ey = _rd.storage_buffer_create(CELLS * 4)
	_ei = _rd.storage_buffer_create(CELLS * 4)
	_q = _rd.storage_buffer_create(CELLS * 4)
	_vel = _rd.storage_buffer_create(CELLS * 16)
	_rho = _rd.storage_buffer_create(CELLS * 4)
	_scratch = _rd.storage_buffer_create(CELLS * 16)
	var fi_zero := PackedByteArray(); fi_zero.resize(128)
	_fi_fallback = _rd.storage_buffer_create(128, fi_zero)
	var buffers_ok: bool = _ey.is_valid() and _ei.is_valid() and _q.is_valid() and _vel.is_valid() and _rho.is_valid() and _scratch.is_valid() and _fi_fallback.is_valid()
	if buffers_ok:
		_us = _rd.uniform_set_create([
			_u(0, _ey), _u(1, _ei), _u(2, _q), _u(3, _vel), _u(4, _rho), _u(5, _scratch),
			_u(6, _fi_fallback), _u(7, _fi_fallback),
		], _shader, 0)
		buffers_ok = _us.is_valid()
	_gate("storage_bindings", buffers_ok, "bindings 0..7 and seven storage buffers" if buffers_ok else "storage buffer or uniform set RID invalid")
	_zero_field.resize(CELLS * 4)
	_zero_velocity.resize(CELLS * 16)
	return buffers_ok


func _u(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _make_initial_fields() -> void:
	_initial_ey.resize(CELLS)
	_initial_ei.resize(CELLS)
	for k in range(GRID_N):
		for j in range(GRID_N):
			for i in range(GRID_N):
				var theta_i: float = TWO_PI * float(i) / float(GRID_N)
				var theta_j: float = TWO_PI * float(j) / float(GRID_N)
				var theta_k: float = TWO_PI * float(k) / float(GRID_N)
				var id: int = _idx(i, j, k)
				_initial_ey[id] = 0.20 * (cos(theta_i) + 0.5 * cos(theta_j) + 0.25 * cos(theta_k))
				_initial_ei[id] = 0.10 * (sin(theta_i) - 0.5 * sin(theta_j) + 0.25 * sin(theta_k))


func _plant_initial() -> void:
	_rd.buffer_update(_ey, 0, CELLS * 4, _initial_ey.to_byte_array())
	_rd.buffer_update(_ei, 0, CELLS * 4, _initial_ei.to_byte_array())
	_rd.buffer_update(_q, 0, CELLS * 4, _zero_field)
	_rd.buffer_update(_vel, 0, CELLS * 16, _zero_velocity)
	_rd.buffer_update(_rho, 0, CELLS * 4, _zero_field)
	_rd.buffer_update(_scratch, 0, CELLS * 16, _zero_velocity)


func _fill_pc(pass_selector: float, process_dt: float, process_t: float) -> void:
	_pc.resize(17)
	_pc[0] = float(GRID_N)
	_pc[1] = process_dt             # existing pc.dt: dt_process=N*dt_coordinate
	_pc[2] = process_t               # existing pc.t: step*dt_process
	_pc[3] = PHI
	_pc[4] = 0.0                    # xi
	_pc[5] = 0.0                    # eps2
	_pc[6] = 0.0                    # particle_N: particles absent
	_pc[7] = 0.0                    # mode
	_pc[8] = 0.0                    # source_strength: sources OFF
	_pc[9] = 0.0                    # num_clusters
	_pc[10] = 0.0                   # gravity_mode
	_pc[11] = EXTENT
	_pc[12] = EXTENT
	_pc[13] = EXTENT
	_pc[14] = pass_selector         # 0 = pass A, 1 = pass B
	_pc[15] = OMEGA2
	_pc[16] = 1.0                   # ham_completion ON


func _dispatch(pass_selector: float, process_dt: float, process_t: float) -> void:
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	_rd.compute_list_bind_uniform_set(cl, _us, 0)
	_fill_pc(pass_selector, process_dt, process_t)
	_rd.compute_list_set_push_constant(cl, _pc.to_byte_array(), _pc.size() * 4)
	var workgroups: int = GRID_N / 4
	_rd.compute_list_dispatch(cl, workgroups, workgroups, workgroups)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _capture_state() -> Dictionary:
	var ey_raw: PackedByteArray = _rd.buffer_get_data(_ey, 0, CELLS * 4)
	var ei_raw: PackedByteArray = _rd.buffer_get_data(_ei, 0, CELLS * 4)
	var q_raw: PackedByteArray = _rd.buffer_get_data(_q, 0, CELLS * 4)
	var vel_raw: PackedByteArray = _rd.buffer_get_data(_vel, 0, CELLS * 16)
	return {
		"ey_raw": ey_raw,
		"ei_raw": ei_raw,
		"q_raw": q_raw,
		"vel_raw": vel_raw,
		"ey": ey_raw.to_float32_array(),
		"ei": ei_raw.to_float32_array(),
		"q": q_raw.to_float32_array(),
		"vel": vel_raw.to_float32_array(),
	}


func _run_arm(arm_id: String, dt_coordinate: float, lapse: float) -> Dictionary:
	_plant_initial()
	var process_dt: float = lapse * dt_coordinate
	var initial: Dictionary = _capture_state()
	var h_initial: float = _hamiltonian(initial)
	var pass_a_count: int = 0
	var pass_b_count: int = 0
	for step in range(STEPS):
		var process_t: float = float(step + 1) * process_dt
		_dispatch(0.0, process_dt, process_t)
		pass_a_count += 1
		_dispatch(1.0, process_dt, process_t)
		pass_b_count += 1
	var final_state: Dictionary = _capture_state()
	var ey: PackedFloat32Array = final_state["ey"]
	var ei: PackedFloat32Array = final_state["ei"]
	var q: PackedFloat32Array = final_state["q"]
	var vel: PackedFloat32Array = final_state["vel"]
	var finite_state: bool = _finite_array(ey) and _finite_array(ei) and _finite_array(q) and _finite_array(vel)
	var h_final: float = _hamiltonian(final_state)
	var h_finite: bool = _finite_scalar(h_initial) and _finite_scalar(h_final)
	var h_drift: float = 1.0e30
	if h_finite:
		h_drift = absf(h_final - h_initial) / maxf(absf(h_initial), 1.0e-12)
	return {
		"id": arm_id,
		"dt_coordinate": dt_coordinate,
		"N": lapse,
		"dt_process": process_dt,
		"coordinate_duration": float(STEPS) * dt_coordinate,
		"process_duration": float(STEPS) * process_dt,
		"final_pc_t": float(STEPS) * process_dt,
		"steps": STEPS,
		"pass_a_count": pass_a_count,
		"pass_b_count": pass_b_count,
		"finite": finite_state,
		"q_finite": _finite_array(q),
		"hamiltonian_initial": h_initial,
		"hamiltonian_final": h_final,
		"hamiltonian_finite": h_finite,
		"hamiltonian_drift": h_drift,
		"ey_raw": final_state["ey_raw"],
		"ei_raw": final_state["ei_raw"],
		"q_raw": final_state["q_raw"],
		"vel_raw": final_state["vel_raw"],
	}


func _run_gates() -> void:
	var has_arms: bool = _arms.size() == 3
	var exact_steps: bool = has_arms
	var finite_state: bool = has_arms
	for arm_value in _arms:
		var arm: Dictionary = arm_value
		exact_steps = exact_steps and int(arm["steps"]) == STEPS and int(arm["pass_a_count"]) == STEPS and int(arm["pass_b_count"]) == STEPS
		finite_state = finite_state and bool(arm["finite"]) and bool(arm["q_finite"])
	_gate("exact_step_schedule", exact_steps, "32 pass-A then pass-B pairs per arm" if exact_steps else "step or pass count mismatch")
	_gate("finite_state", finite_state, "EY, EI, q, and velocity final floats finite" if finite_state else "non-finite final GPU state")
	if not has_arms:
		_gate("baseline_off_bit_identity", false, "three arms unavailable")
		_gate("equal_process_age_bit_identity", false, "three arms unavailable")
		_gate("coordinate_process_clock", false, "three arms unavailable")
		_gate("hamiltonian_bounded_shadow", false, "three arms unavailable")
		return

	var baseline_a: Dictionary = _arms[0]
	var baseline_b: Dictionary = _arms[1]
	var lapse: Dictionary = _arms[2]
	var off_ey: bool = _same_bytes(baseline_a, baseline_b, "ey_raw")
	var off_ei: bool = _same_bytes(baseline_a, baseline_b, "ei_raw")
	var off_vel: bool = _same_bytes(baseline_a, baseline_b, "vel_raw")
	_gate("baseline_off_bit_identity", off_ey and off_ei and off_vel,
		"baseline-A/B EY, EI, velocity raw bytes" if off_ey and off_ei and off_vel else "duplicate baseline raw bytes differ")
	var age_ey: bool = _same_bytes(baseline_a, lapse, "ey_raw")
	var age_ei: bool = _same_bytes(baseline_a, lapse, "ei_raw")
	var age_vel: bool = _same_bytes(baseline_a, lapse, "vel_raw")
	_gate("equal_process_age_bit_identity", age_ey and age_ei and age_vel,
		"baseline-A/uniform-lapse EY, EI, velocity raw bytes" if age_ey and age_ei and age_vel else "equal-process-age raw bytes differ")

	var coord_base: float = float(baseline_a["coordinate_duration"])
	var coord_lapse: float = float(lapse["coordinate_duration"])
	var process_base: float = float(baseline_a["process_duration"])
	var process_lapse: float = float(lapse["process_duration"])
	var clock_ok: bool = coord_base > 0.0 and absf(coord_lapse / coord_base - 2.0) <= CLOCK_TOL
	clock_ok = clock_ok and absf(process_base - process_lapse) <= CLOCK_TOL
	for arm_value in _arms:
		var arm: Dictionary = arm_value
		clock_ok = clock_ok and absf(float(arm["dt_process"]) - DT_PROCESS) <= CLOCK_TOL
		clock_ok = clock_ok and absf(float(arm["final_pc_t"]) - process_base) <= CLOCK_TOL
	_gate("coordinate_process_clock", clock_ok, "coordinate ratio 2x; process duration and pc.dt/pc.t equal" if clock_ok else "coordinate/process timing provenance mismatch")

	var h_ok: bool = true
	for arm_value in _arms:
		var arm: Dictionary = arm_value
		var drift: float = float(arm["hamiltonian_drift"])
		h_ok = h_ok and bool(arm["hamiltonian_finite"]) and _finite_scalar(drift) and drift < HAMILTONIAN_DRIFT_MAX
	_gate("hamiltonian_bounded_shadow", h_ok, "all completed-form drifts < 1%" if h_ok else "completed-form Hamiltonian drift reached frozen bound")


func _same_bytes(a: Dictionary, b: Dictionary, key: String) -> bool:
	var left: PackedByteArray = a[key]
	var right: PackedByteArray = b[key]
	return left == right


func _idx(i: int, j: int, k: int) -> int:
	return i + GRID_N * (j + GRID_N * k)


func _laplacian(field: PackedFloat32Array, i: int, j: int, k: int) -> float:
	var ip: int = (i + 1) % GRID_N
	var im: int = (i - 1 + GRID_N) % GRID_N
	var jp: int = (j + 1) % GRID_N
	var jm: int = (j - 1 + GRID_N) % GRID_N
	var kp: int = (k + 1) % GRID_N
	var km: int = (k - 1 + GRID_N) % GRID_N
	var center: float = field[_idx(i, j, k)]
	var h_n: float = float(GRID_N) * 0.5
	var hx: float = EXTENT / h_n
	var hy: float = EXTENT / h_n
	var hz: float = EXTENT / h_n
	var h0: float = minf(minf(EXTENT, EXTENT), EXTENT) / h_n
	var hx2: float = hx * hx
	var hy2: float = hy * hy
	var hz2: float = hz * hz
	var h02: float = h0 * h0
	var bxy: float = (1.0 / 3.0) * h02 / (hx2 + hy2)
	var bxz: float = (1.0 / 3.0) * h02 / (hx2 + hz2)
	var byz: float = (1.0 / 3.0) * h02 / (hy2 + hz2)
	var ax: float = h02 / hx2 - 2.0 * (bxy + bxz)
	var ay: float = h02 / hy2 - 2.0 * (bxy + byz)
	var az: float = h02 / hz2 - 2.0 * (bxz + byz)
	var axis_x: float = field[_idx(ip, j, k)] + field[_idx(im, j, k)] - 2.0 * center
	var axis_y: float = field[_idx(i, jp, k)] + field[_idx(i, jm, k)] - 2.0 * center
	var axis_z: float = field[_idx(i, j, kp)] + field[_idx(i, j, km)] - 2.0 * center
	var face_xy: float = field[_idx(ip, jp, k)] + field[_idx(im, jp, k)] + field[_idx(ip, jm, k)] + field[_idx(im, jm, k)] - 4.0 * center
	var face_xz: float = field[_idx(ip, j, kp)] + field[_idx(im, j, kp)] + field[_idx(ip, j, km)] + field[_idx(im, j, km)] - 4.0 * center
	var face_yz: float = field[_idx(i, jp, kp)] + field[_idx(i, jm, kp)] + field[_idx(i, jp, km)] + field[_idx(i, jm, km)] - 4.0 * center
	return ax * axis_x + ay * axis_y + az * axis_z + bxy * face_xy + bxz * face_xz + byz * face_yz


func _hamiltonian(state: Dictionary) -> float:
	var ey: PackedFloat32Array = state["ey"]
	var ei: PackedFloat32Array = state["ei"]
	var vel: PackedFloat32Array = state["vel"]
	var total: float = 0.0
	for k in range(GRID_N):
		for j in range(GRID_N):
			for i in range(GRID_N):
				var id: int = _idx(i, j, k)
				var ey_value: float = ey[id]
				var ei_value: float = ei[id]
				var d: float = ey_value - PHI * ei_value
				var ly: float = _laplacian(ey, i, j, k)
				var li: float = _laplacian(ei, i, j, k)
				var velocity_offset: int = id * 4
				var kinetic: float = 0.5 * (vel[velocity_offset] * vel[velocity_offset] + vel[velocity_offset + 1] * vel[velocity_offset + 1] + vel[velocity_offset + 2] * vel[velocity_offset + 2])
				total += kinetic - 0.5 * ey_value * ly - 0.5 * ei_value * li + 0.5 * OMEGA2 * d * d
	return total


func _finite_scalar(value: float) -> bool:
	return not is_nan(value) and not is_inf(value)


func _finite_array(values: PackedFloat32Array) -> bool:
	for value in values:
		if not _finite_scalar(value):
			return false
	return true


func _sha256(raw: PackedByteArray) -> String:
	var context := HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(raw)
	return context.finish().hex_encode()


func _raw_descriptor(raw: PackedByteArray) -> Dictionary:
	return {"bytes": raw.size(), "sha256": _sha256(raw)}


func _json_number(value: float) -> Variant:
	return value if _finite_scalar(value) else null


func _arm_receipt(arm: Dictionary) -> Dictionary:
	return {
		"id": arm["id"],
		"dt_coordinate": arm["dt_coordinate"],
		"N": arm["N"],
		"dt_process": arm["dt_process"],
		"coordinate_duration": arm["coordinate_duration"],
		"process_duration": arm["process_duration"],
		"steps": arm["steps"],
		"pass_a_count": arm["pass_a_count"],
		"pass_b_count": arm["pass_b_count"],
		"pc": {
			"dt_slot": 1,
			"t_slot": 2,
			"dt": arm["dt_process"],
			"t_final": arm["final_pc_t"],
			"dt_provenance": "pc.dt=dt_process=N*dt_coordinate",
			"t_provenance": "pc.t=(step+1)*dt_process with one-based process step; same t sent to pass A and pass B",
		},
		"finite": arm["finite"],
		"q_finite_only": arm["q_finite"],
		"hamiltonian": {
			"initial": _json_number(float(arm["hamiltonian_initial"])),
			"final": _json_number(float(arm["hamiltonian_final"])),
			"relative_drift": _json_number(float(arm["hamiltonian_drift"])),
			"bound": HAMILTONIAN_DRIFT_MAX,
		},
		"raw_final": {
			"EY": _raw_descriptor(arm["ey_raw"]),
			"EI": _raw_descriptor(arm["ei_raw"]),
			"velocity_vec4": _raw_descriptor(arm["vel_raw"]),
		},
	}


func _comparison_receipt() -> Dictionary:
	if _arms.size() != 3:
		return {
			"baseline_off": {"EY": false, "EI": false, "velocity_vec4": false, "all": false},
			"equal_process_age": {"EY": false, "EI": false, "velocity_vec4": false, "all": false},
		}
	var a: Dictionary = _arms[0]
	var b: Dictionary = _arms[1]
	var l: Dictionary = _arms[2]
	var off_ey: bool = _same_bytes(a, b, "ey_raw")
	var off_ei: bool = _same_bytes(a, b, "ei_raw")
	var off_vel: bool = _same_bytes(a, b, "vel_raw")
	var age_ey: bool = _same_bytes(a, l, "ey_raw")
	var age_ei: bool = _same_bytes(a, l, "ei_raw")
	var age_vel: bool = _same_bytes(a, l, "vel_raw")
	return {
		"baseline_off": {"EY": off_ey, "EI": off_ei, "velocity_vec4": off_vel, "all": off_ey and off_ei and off_vel},
		"equal_process_age": {"EY": age_ey, "EI": age_ei, "velocity_vec4": age_vel, "all": age_ey and age_ei and age_vel},
	}


func _receipt_gates() -> Dictionary:
	var result: Dictionary = {}
	for gate_name in GATE_NAMES:
		result[gate_name] = bool(_gates.get(gate_name, false))
	return result


func _verdict() -> String:
	if _invalid_setup:
		return "INVALID_SETUP"
	return "PASS_IMPLEMENTATION_ONLY" if _failures == 0 else "FAIL_IMPLEMENTATION"


func _make_receipt() -> Dictionary:
	var arm_receipts: Array = []
	for arm_value in _arms:
		arm_receipts.append(_arm_receipt(arm_value))
	return {
		"schema": RECEIPT_SCHEMA,
		"verdict": _verdict(),
		"candidate_role": CANDIDATE_ROLE,
		"default_off_state": DEFAULT_OFF_STATE,
		"preregistration": PREREG_PATH,
		"shader": SHADER_PATH,
		"law_identity": LAW_IDENTITY,
		"operator_identity": OPERATOR_IDENTITY,
		"windowed_only": true,
		"production_changes": false,
		"initial_seed": INITIAL_SEED,
		"grid": {"N": GRID_N, "cells": CELLS, "extent": EXTENT, "periodic": true},
		"fixed_steps": STEPS,
		"ham_completion": 1.0,
		"sources": "OFF; source_strength=0 and rho buffer zeroed",
		"particles": "absent; particle_N=0",
		"q_policy": "q is not a lapse source, is not used to derive N, and is not compared; q_finite_only is recorded",
		"stopping_rule": "exactly 32 pass-A then pass-B pairs per fresh arm; no data-dependent early stop",
		"clock_provenance": {
			"coordinate": "host bookkeeping t_c; not sent as pc.dt",
			"process": "t_p=N*t_c; dt_process=N*dt_coordinate",
			"pc_dt": "slot 1; pc.dt=dt_process=N*dt_coordinate",
			"pc_t": "slot 2; pc.t=(step+1)*dt_process with one-based process step; same value for pass A/B",
		},
		"arms": arm_receipts,
		"comparisons": _comparison_receipt(),
		"gates": _receipt_gates(),
		"epistemic_boundary": "implementation proof only; not CT-2 evidence; not local coherence-derived lapse evidence; not universal physical-time evidence",
		"receipt_path": RECEIPT_PATH,
	}


func _store_receipt(receipt: Dictionary) -> bool:
	var file: FileAccess = FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(receipt))
	file.close()
	return true


func _write_receipt_and_reopen(receipt: Dictionary) -> bool:
	var directory: String = ProjectSettings.globalize_path("res://_diag/process_time")
	if DirAccess.make_dir_recursive_absolute(directory) != OK:
		_gates["receipt_write_reopen"] = false
		return false
	_gates["receipt_write_reopen"] = false
	receipt["gates"] = _receipt_gates()
	if not _store_receipt(receipt):
		return false
	var verify_file: FileAccess = FileAccess.open(RECEIPT_PATH, FileAccess.READ)
	if verify_file == null:
		return false
	var parsed: Variant = JSON.parse_string(verify_file.get_as_text())
	verify_file.close()
	if not (parsed is Dictionary) or str((parsed as Dictionary).get("schema", "")) != RECEIPT_SCHEMA:
		return false
	_gates["receipt_write_reopen"] = true
	receipt["gates"] = _receipt_gates()
	receipt["verdict"] = _verdict()
	if not _store_receipt(receipt):
		_gates["receipt_write_reopen"] = false
		return false
	var final_file: FileAccess = FileAccess.open(RECEIPT_PATH, FileAccess.READ)
	if final_file == null:
		_gates["receipt_write_reopen"] = false
		return false
	var final_parsed: Variant = JSON.parse_string(final_file.get_as_text())
	final_file.close()
	return final_parsed is Dictionary and str((final_parsed as Dictionary).get("schema", "")) == RECEIPT_SCHEMA


func _gate(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	_gates[name] = ok
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _exit_tree() -> void:
	if _rd != null:
		for rid in [_us, _fi_fallback, _scratch, _rho, _vel, _q, _ei, _ey, _pipe, _shader]:
			if rid.is_valid():
				_rd.free_rid(rid)
		_rd.free()
		_rd = null


func _finish() -> void:
	var receipt: Dictionary = _make_receipt()
	var receipt_ok: bool = _write_receipt_and_reopen(receipt)
	_gate("receipt_write_reopen", receipt_ok, RECEIPT_PATH if receipt_ok else "receipt write/re-open failed")
	var elapsed: int = Time.get_ticks_msec() - _t0
	print("[VerifyUniformLapse] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyUniformLapse] RESULT: PASS_IMPLEMENTATION_ONLY (not CT-2 or universal physical-time evidence)")
	else:
		print("[VerifyUniformLapse] RESULT: %s (not CT-2 or universal physical-time evidence)" % _verdict())
	get_tree().quit(0 if _failures == 0 else 1)
