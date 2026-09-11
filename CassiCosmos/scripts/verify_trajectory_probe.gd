extends Node3D
## Standalone GPU trajectory probe for the matter-formation question.
##
## The harness owns a local RenderingDevice and a CassiPhysicsEngine instance,
## so it can submit and fence every bounded batch without coupling the probe to
## the production renderer. `shell` records nested-shell dynamics with merging
## disabled. `ancestry` repeats the same seeded geometry with the existing
## merge rule enabled and a fixed high-coherence field gate.
##
## Smoke run (windowed; scene arms must not use --headless):
##   Godot_v4.7-stable_win64_console.exe --path . \
##     res://scenes/verify_trajectory_probe.tscn -- \
##     --mode=shell --steps=1024
##
## Long run inputs are explicit in the receipt. The frozen target is one
## million accepted steps, 4,096 tracers, stride 4,096, and a 256-slot ring.

const ENGINE_SCRIPT = preload("res://scripts/cassi_physics_engine.gd")
const GRID_N := 64
const PHI: float = 1.618033988749895
const DEFAULT_SEED := 20260910
const DEFAULT_PARTICLES := 8192
const DEFAULT_TRACERS := 1024
const DEFAULT_STEPS := 1024
const DEFAULT_BATCH_STEPS := 64
const DEFAULT_SAMPLE_STRIDE := 16
const DEFAULT_SAMPLE_CAPACITY := 128
const DEFAULT_EVENT_CAPACITY := 65536
const DEFAULT_MERGE_CADENCE := 64
const DEFAULT_DT: float = 0.001
const DEFAULT_CLUSTER_RADIUS: float = 25.0
const DEFAULT_TOTAL_MASS: float = 1000.0
const RUNNING := 1

var _mode := "shell"
var _seed := DEFAULT_SEED
var _particle_count := DEFAULT_PARTICLES
var _tracer_count := DEFAULT_TRACERS
var _target_steps := DEFAULT_STEPS
var _batch_steps := DEFAULT_BATCH_STEPS
var _batches_per_frame := 1
var _sample_stride := DEFAULT_SAMPLE_STRIDE
var _sample_capacity := DEFAULT_SAMPLE_CAPACITY
var _event_capacity := DEFAULT_EVENT_CAPACITY
var _merge_cadence := DEFAULT_MERGE_CADENCE
var _dt := DEFAULT_DT
var _timeout_sec := 0.0
var _recorder_enabled := true
var _out_dir := ""
var _inner_radius_arg := -1.0
var _outer_radius_arg := -1.0

var _rd: RenderingDevice = null
var _eng = null
var _initial_pos := PackedFloat32Array()
var _initial_tracer_pos := PackedFloat32Array()
var _tracer_ids := PackedInt32Array()
var _initial_live_count := 0
var _initial_total_mass := 0.0
var _inner_radius := 0.0
var _outer_radius := 0.0
var _completed_steps := 0
var _phase := 0
var _started_ms := 0
var _finished := false
var _failure := ""


func _ready() -> void:
	_parse_args()
	if not _failure.is_empty():
		_finish(1)
		return
	print("[VerifyTrajectoryProbe] mode=%s recorder=%s particles=%d steps=%d seed=%d" % [
		_mode, "on" if _recorder_enabled else "off",
		_particle_count, _target_steps, _seed])
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_fail("local RenderingDevice unavailable; run the scene windowed")
		return
	_eng = ENGINE_SCRIPT.new()
	var setup_ok: bool = _eng.setup(_engine_config())
	if not setup_ok:
		_fail("physics engine setup() returned false")
		return
	if not _eng.finish_setup():
		_fail("physics engine finish_setup() returned false")
		return
	_initial_pos = _read_positions()
	if _initial_pos.size() != _particle_count * 4:
		_fail("initial position readback size=%d expected=%d" % [
			_initial_pos.size(), _particle_count * 4])
		return
	_capture_initial_summary()
	if _initial_live_count <= 0 or _initial_total_mass <= 0.0:
		_fail("initial particle state is empty")
		return
	_inner_radius = _inner_radius_arg if _inner_radius_arg >= 0.0 else 0.25 * _support_radius()
	_outer_radius = _outer_radius_arg if _outer_radius_arg >= 0.0 else 0.75 * _support_radius()
	if _outer_radius <= _inner_radius or _outer_radius <= 0.0:
		_fail("shell radii are not ordered: %.6f %.6f" % [_inner_radius, _outer_radius])
		return
	_eng.set("trajectory_inner_radius", _inner_radius)
	_eng.set("trajectory_outer_radius", _outer_radius)
	_initial_tracer_pos = _select_tracer_state(_initial_pos)
	if _initial_tracer_pos.size() != _tracer_count * 4:
		_fail("initial tracer state size=%d expected=%d" % [
			_initial_tracer_pos.size(), _tracer_count * 4])
		return
	if _mode == "ancestry":
		_plant_coherent_field()
	print("[VerifyTrajectoryProbe] support=%.6f inner=%.6f outer=%.6f" % [
		_support_radius(), _inner_radius, _outer_radius])
	_phase = RUNNING


func _process(_delta: float) -> void:
	if _finished or _phase != RUNNING:
		return
	if _timeout_sec > 0.0 and Time.get_ticks_msec() - _started_ms > _timeout_sec * 1000.0:
		_fail("probe timeout after %d accepted steps" % _completed_steps)
		return
	for _batch in range(_batches_per_frame):
		if _completed_steps >= _target_steps:
			_finish(0)
			return
		var request := mini(_batch_steps, _target_steps - _completed_steps)
		_eng.run_steps(request, true)
		var observed := int(_eng.get("_executed"))
		if observed <= _completed_steps:
			_fail("engine made no progress at requested step %d" % _completed_steps)
			return
		_completed_steps = observed
		if _completed_steps >= _target_steps:
			_finish(0)
			return


## The complete registered configuration. Every receipt records this dictionary
## so a qualifying run can prove the inputs it ran under, and _engine_config()
## derives the engine call from it.
##
## The shell bounds derive from the initial radial support, which is only known
## after setup(), so setup() receives the pre-measurement zeros and _ready()
## applies the computed bounds with eng.set before the first step. Receipts are
## written after that, so their radii are the effective bounds.
func _registered_config() -> Dictionary:
	return {
		"seed": _seed,
		"grid_N": GRID_N,
		"N_particles": _particle_count,
		"batch_steps": _batch_steps,
		"batches_per_frame": _batches_per_frame,
		"dt": _dt,
		"xi": 17.94427191,
		"softening": 0.1,
		"cluster_radius": DEFAULT_CLUSTER_RADIUS,
		"cluster_separation": 0.0,
		"num_clusters": 1,
		"box_aspect": [1.0, 1.0, 1.0],
		"box_scale": 1.0,
		"window_center": [0.0, 0.0, 0.0],
		"initial_condition": 6,
		"initial_arrangement": 0,
		"initial_motion": 4,
		"initial_speed": 1.0,
		"initial_total_mass": DEFAULT_TOTAL_MASS,
		"initial_radius_fraction": 0.9,
		"initial_shape_settings": {
			"shell_count": 3,
			"shell_spacing": 0.33,
			"shell_inner_radius": 0.34,
			"shell_ellipticity": 0.88,
			"shell_offset": 0.12,
		},
		"freeze_field": true,
		"source_strength": 0.0,
		"gravity_mode": 2,
		"black_holes_enabled": false,
		"bh_accretion": false,
		"dual_grid": false,
		"meshless_mode": false,
		"meshless_gravity": false,
		"particle_merge": _mode == "ancestry",
		"merge_cadence_steps": _merge_cadence,
		"trajectory_enabled": _recorder_enabled,
		"trajectory_tracer_count": _tracer_count,
		"trajectory_sample_capacity": _sample_capacity,
		"trajectory_sample_stride": _sample_stride,
		"trajectory_event_capacity": _event_capacity,
		"trajectory_inner_radius": _inner_radius,
		"trajectory_outer_radius": _outer_radius,
	}


func _engine_config() -> Dictionary:
	var cfg := _registered_config()
	cfg["rd"] = _rd
	cfg["rd_global"] = false
	cfg["owns_rd"] = true
	cfg["box_aspect"] = Vector3.ONE
	cfg["window_center"] = Vector3.ZERO
	return cfg


func _parse_args() -> void:
	_mode = _arg_value("mode", "shell").to_lower()
	if _mode != "shell" and _mode != "ancestry":
		_failure = "mode must be shell or ancestry"
		return
	_seed = _arg_int("seed", DEFAULT_SEED)
	_particle_count = _arg_int("particles", DEFAULT_PARTICLES)
	_tracer_count = _arg_int("tracers", mini(DEFAULT_TRACERS, _particle_count))
	_target_steps = _arg_int("steps", DEFAULT_STEPS)
	_batch_steps = _arg_int("batch-steps", DEFAULT_BATCH_STEPS)
	_batches_per_frame = _arg_int("batches-per-frame", 1)
	_sample_stride = _arg_int("sample-stride", DEFAULT_SAMPLE_STRIDE)
	_sample_capacity = _arg_int("sample-capacity", DEFAULT_SAMPLE_CAPACITY)
	_event_capacity = _arg_int("event-capacity", DEFAULT_EVENT_CAPACITY)
	_merge_cadence = _arg_int("merge-cadence", DEFAULT_MERGE_CADENCE)
	_dt = _arg_float("dt", DEFAULT_DT)
	_timeout_sec = _arg_float("timeout-sec", 0.0)
	var recorder_mode := _arg_value("recorder", "on").to_lower()
	if recorder_mode == "on" or recorder_mode == "true":
		_recorder_enabled = true
	elif recorder_mode == "off" or recorder_mode == "false":
		_recorder_enabled = false
	else:
		_failure = "recorder must be on or off"
		return
	_inner_radius_arg = _arg_float("inner-radius", -1.0)
	_outer_radius_arg = _arg_float("outer-radius", -1.0)
	_out_dir = _arg_value("out-dir",
		"res://_diag/matter_formation/trajectory_%s" % _mode)
	if _particle_count < 1 or _tracer_count < 1 or _tracer_count > _particle_count:
		_failure = "particle/tracer counts are invalid"
	elif _target_steps < 1 or _batch_steps < 1 or _batches_per_frame < 1:
		_failure = "steps and batch controls must be positive"
	elif _sample_stride < 1 or _sample_capacity < 1 or _event_capacity < 1:
		_failure = "recorder capacities and stride must be positive"
	elif _merge_cadence < 1:
		_failure = "merge cadence must be positive"
	elif _dt <= 0.0 or not is_finite(_dt):
		_failure = "dt must be finite and positive"
	elif _inner_radius_arg < -1.0 or _outer_radius_arg < -1.0:
		_failure = "shell radius overrides must be nonnegative"


func _arg_value(name: String, fallback: String) -> String:
	var prefix := "--" + name + "="
	for raw in OS.get_cmdline_user_args():
		var arg := String(raw)
		if arg.begins_with(prefix):
			return arg.substr(prefix.length())
	return fallback


func _arg_int(name: String, fallback: int) -> int:
	return int(_arg_value(name, str(fallback)))


func _arg_float(name: String, fallback: float) -> float:
	return float(_arg_value(name, str(fallback)))


func _read_positions() -> PackedFloat32Array:
	if _eng == null or _rd == null:
		return PackedFloat32Array()
	return _rd.buffer_get_data(_eng.get("_pos_buf")).to_float32_array()


func _capture_initial_summary() -> void:
	_initial_live_count = 0
	_initial_total_mass = 0.0
	for particle in range(_particle_count):
		var mass := _initial_pos[particle * 4 + 3]
		if mass > 0.0 and is_finite(mass):
			_initial_live_count += 1
			_initial_total_mass += mass


func _support_radius() -> float:
	var support := 0.0
	for particle in range(_particle_count):
		var base := particle * 4
		if _initial_pos[base + 3] <= 0.0:
			continue
		var radius := Vector3(
			_initial_pos[base], _initial_pos[base + 1], _initial_pos[base + 2]).length()
		support = maxf(support, radius)
	return support


func _select_tracer_state(pos: PackedFloat32Array) -> PackedFloat32Array:
	var selected := PackedFloat32Array()
	selected.resize(_tracer_count * 4)
	_tracer_ids.resize(_tracer_count)
	for tracer in range(_tracer_count):
		var particle := int(float(tracer) * float(_particle_count) / float(_tracer_count))
		_tracer_ids[tracer] = particle
		var source := particle * 4
		var target := tracer * 4
		for component in 4:
			selected[target + component] = pos[source + component]
	return selected


## Resolve the active field-role buffers. The current engine exposes the active
## role through get_field_role_state() (it ping-pongs between two buffer sets);
## the engine as committed has one set under the same property names.
func _field_role_rids() -> Dictionary:
	if _eng.has_method("get_field_role_state"):
		return _eng.get_field_role_state()
	return {
		"ey": _eng.get("_field_ey"),
		"ei": _eng.get("_field_ei"),
		"q": _eng.get("_field_q"),
	}


func _plant_coherent_field() -> void:
	var cells := GRID_N * GRID_N * GRID_N
	var ey := PackedFloat32Array()
	var ei := PackedFloat32Array()
	var q := PackedFloat32Array()
	ey.resize(cells)
	ei.resize(cells)
	q.resize(cells)
	for cell in range(cells):
		ey[cell] = PHI
		ei[cell] = 1.0
		q[cell] = PHI * PHI + 1.0
	var state: Dictionary = _field_role_rids()
	var ey_rid: RID = state.get("ey")
	var ei_rid: RID = state.get("ei")
	var q_rid: RID = state.get("q")
	_rd.buffer_update(ey_rid, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(ei_rid, 0, ei.size() * 4, ei.to_byte_array())
	_rd.buffer_update(q_rid, 0, q.size() * 4, q.to_byte_array())


func _write_bytes(name: String, bytes: PackedByteArray) -> bool:
	var path := ProjectSettings.globalize_path(_out_dir.path_join(name))
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		print("[VerifyTrajectoryProbe] cannot open %s" % path)
		return false
	file.store_buffer(bytes)
	file.close()
	return true


func _write_receipt(receipt: Dictionary) -> bool:
	var path := ProjectSettings.globalize_path(_out_dir.path_join("receipt.json"))
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null:
		print("[VerifyTrajectoryProbe] cannot open %s" % path)
		return false
	file.store_string(JSON.stringify(receipt, "\t"))
	file.close()
	return true


func _finish(code: int) -> void:
	if _finished:
		return
	_finished = true
	if code == 0 and _eng != null:
		if not _write_artifacts():
			code = 1
	if _eng != null:
		var engine_owns_device := bool(_eng.get("_owns_rd"))
		_eng.shutdown()
		_eng = null
		if _rd != null and not engine_owns_device:
			_rd.free()
	elif _rd != null:
		_rd.free()
	_rd = null
	if code != 0:
		print("[VerifyTrajectoryProbe] RESULT: FAIL%s" % (" — " + _failure if not _failure.is_empty() else ""))
	else:
		print("[VerifyTrajectoryProbe] RESULT: RAW_WRITTEN")
	get_tree().quit(code)


func _fail(message: String) -> void:
	if _failure.is_empty():
		_failure = message
	print("[VerifyTrajectoryProbe] FAIL: %s" % _failure)
	_finish(1)


func _write_artifacts() -> bool:
	var final_pos: PackedFloat32Array = _read_positions()
	if final_pos.size() != _particle_count * 4:
		_failure = "final position readback size=%d expected=%d" % [
			final_pos.size(), _particle_count * 4]
		return false
	var final_tracer_pos := _select_tracer_state(final_pos)
	var final_live_count := 0
	var final_total_mass := 0.0
	for particle in range(_particle_count):
		var mass := final_pos[particle * 4 + 3]
		if mass > 0.0 and is_finite(mass):
			final_live_count += 1
			final_total_mass += mass
	var global_dir := ProjectSettings.globalize_path(_out_dir)
	DirAccess.make_dir_recursive_absolute(global_dir)
	if not _recorder_enabled:
		var baseline_files_ok := true
		baseline_files_ok = _write_bytes("tracer_ids.bin", _tracer_ids.to_byte_array()) and baseline_files_ok
		baseline_files_ok = _write_bytes("initial_tracers.bin", _initial_tracer_pos.to_byte_array()) and baseline_files_ok
		baseline_files_ok = _write_bytes("final_tracers.bin", final_tracer_pos.to_byte_array()) and baseline_files_ok
		var baseline_receipt := {
			"schema": "cassi.trajectory-probe.v1",
			"mode": _mode,
			"recorder_enabled": false,
			"seed": _seed,
			"engine": _registered_config(),
			"accepted_steps_requested": _target_steps,
			"accepted_steps": int(_eng.get("_executed")),
			"step_count": int(_eng.get("_step_count")),
			"dt": _dt,
			"merge_cadence_steps": _merge_cadence,
			"grid_N": GRID_N,
			"N_particles": _particle_count,
			"tracer_count": _tracer_count,
			"initial_live_count": _initial_live_count,
			"initial_total_mass": _initial_total_mass,
			"final_live_count": final_live_count,
			"final_total_mass": final_total_mass,
			"inner_radius": _inner_radius,
			"outer_radius": _outer_radius,
			"files": ["receipt.json", "tracer_ids.bin", "initial_tracers.bin", "final_tracers.bin"],
		}
		if not baseline_files_ok or not _write_receipt(baseline_receipt):
			_failure = "baseline artifact write failed"
			return false
		print("[VerifyTrajectoryProbe] wrote baseline %s steps=%d mass=%.6f→%.6f" % [
			_out_dir, baseline_receipt.accepted_steps,
			_initial_total_mass, final_total_mass])
		return true
	var trajectory: Dictionary = _eng.readback_trajectory()
	if trajectory.is_empty():
		_failure = "trajectory readback is empty"
		return false
	var counters: PackedInt32Array = trajectory.get("counters", PackedInt32Array())
	var files_ok := true
	files_ok = _write_bytes("tracer_ids.bin", _tracer_ids.to_byte_array()) and files_ok
	files_ok = _write_bytes("sample_steps.bin", trajectory.get("sample_steps", PackedByteArray())) and files_ok
	files_ok = _write_bytes("history_pos.bin", trajectory.get("history_pos", PackedByteArray())) and files_ok
	files_ok = _write_bytes("history_vel.bin", trajectory.get("history_vel", PackedByteArray())) and files_ok
	files_ok = _write_bytes("events.bin", trajectory.get("events", PackedByteArray())) and files_ok
	files_ok = _write_bytes("initial_tracers.bin", _initial_tracer_pos.to_byte_array()) and files_ok
	files_ok = _write_bytes("final_tracers.bin", final_tracer_pos.to_byte_array()) and files_ok
	var receipt := {
		"schema": "cassi.trajectory-probe.v1",
		"mode": _mode,
		"recorder_enabled": true,
		"seed": _seed,
		"engine": _registered_config(),
		"accepted_steps_requested": _target_steps,
		"accepted_steps": int(_eng.get("_executed")),
		"step_count": int(_eng.get("_step_count")),
		"dt": _dt,
		"merge_cadence_steps": _merge_cadence,
		"grid_N": GRID_N,
		"N_particles": _particle_count,
		"tracer_count": int(trajectory.get("tracer_count", 0)),
		"sample_total": int(trajectory.get("sample_total", 0)),
		"sample_slots": int(trajectory.get("sample_slots", 0)),
		"sample_capacity": _sample_capacity,
		"sample_stride": _sample_stride,
		"event_total": int(counters[0]) if counters.size() >= 1 else -1,
		"event_overflow": int(counters[1]) if counters.size() >= 2 else -1,
		"sample_overflow": int(counters[3]) if counters.size() >= 4 else -1,
		"event_records_stored": int(trajectory.get("event_count", 0)),
		"event_capacity": _event_capacity,
		"initial_live_count": _initial_live_count,
		"initial_total_mass": _initial_total_mass,
		"final_live_count": final_live_count,
		"final_total_mass": final_total_mass,
		"cluster_radius": DEFAULT_CLUSTER_RADIUS,
		"box_aspect": [1.0, 1.0, 1.0],
		"extents": [DEFAULT_CLUSTER_RADIUS * 1.5, DEFAULT_CLUSTER_RADIUS * 1.5, DEFAULT_CLUSTER_RADIUS * 1.5],
		"inner_radius": _inner_radius,
		"outer_radius": _outer_radius,
		"geometry": {
			"initial_condition": "Nested shells",
			"initial_arrangement": "Ring",
			"initial_motion": "Inward",
			"shell_count": 3,
			"shell_spacing": 0.33,
			"shell_inner_radius": 0.34,
			"shell_ellipticity": 0.88,
			"shell_offset": 0.12,
		},
		"field_control": {
			"freeze_field": true,
			"source_strength": 0.0,
			"coherent_field_plant": _mode == "ancestry",
			"plant_EY": PHI if _mode == "ancestry" else 0.0,
			"plant_EI": 1.0 if _mode == "ancestry" else 0.0,
		},
		"files": [
			"receipt.json", "tracer_ids.bin", "sample_steps.bin", "history_pos.bin",
			"history_vel.bin", "events.bin", "initial_tracers.bin", "final_tracers.bin",
		],
	}
	if not files_ok or not _write_receipt(receipt):
		_failure = "raw artifact write failed"
		return false
	print("[VerifyTrajectoryProbe] wrote %s samples=%d events=%d mass=%.6f→%.6f" % [
		_out_dir, receipt.sample_slots, receipt.event_records_stored,
		_initial_total_mass, final_total_mass])
	return true
