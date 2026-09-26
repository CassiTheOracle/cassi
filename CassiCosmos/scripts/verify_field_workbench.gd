extends Node
## PRE-REGISTRATION G0-G7: paused/rejection, deposit, alignment, impulse,
## ledger ordering, scenario replay, pause/step/resume, no-op/readout/lens.
## Every gate prints PASS/FAIL; exit 0 only when all pass.

const MAX_WAIT_FRAMES := 120
const SCENARIO_PATH := "user://field_workbench_verify.scenario.json"
var _sim: Node
var _checks := 0
var _failures := 0
var _started_ms := 0

func _ready() -> void:
	_started_ms = Time.get_ticks_msec()
	print("[Workbench] PRE-REGISTRATION G0-G7 frozen; seed=1729 grid=64 particles=8")
	_sim = Node3D.new()
	_sim.name = "WorkbenchCassiSim"
	_sim.set_script(load("res://scripts/cassi_sim.gd"))
	_sim.playing = false
	_sim.grid_N = 64
	_sim.N_particles = 8
	_sim.dt = 0.01
	_sim.cluster_radius = 2.0
	_sim.num_clusters = 1
	_sim.cluster_separation = 0.0
	_sim.initial_condition = 2
	_sim.initial_radius_fraction = 0.25
	_sim.source_strength = 0.0
	_sim.black_holes_enabled = false
	_sim.particle_merge = false
	_sim.meshless_mode = false
	_sim.meshless_gravity = false
	_sim.dual_grid = false
	_sim.multi_rung_seed = false
	if _sim.get("ic_seed") != null:
		_sim.ic_seed = 1729
	_sim.suppress_readbacks = true
	if _sim.get("physics_decoupled") != null:
		_sim.physics_decoupled = false
	if _sim.get("box_aspect") != null:
		_sim.box_aspect = Vector3.ONE
	add_child(_sim)
	await _wait_for_ready()
	_run_gates()
	_finish()

func _wait_for_ready() -> void:
	for _i in range(MAX_WAIT_FRAMES):
		await get_tree().process_frame
		if bool(_sim.get("_shaders_ready")) and _sim.get("field_workbench") != null:
			return
	_check("G0: deterministic CassiSim/workbench ready", false, "readiness timeout")

func _run_gates() -> void:
	_check("G0: paused initial state", not _sim.playing and int(_sim.get("_step_count")) == 0)
	_check_rejection()
	_apply("G1", {"kind":"deposit", "center":Vector3.ZERO, "radius":1.0, "strength":0.25, "weighted":false})
	_apply("G2", {"kind":"align", "center":Vector3.ZERO, "radius":1.0, "strength":1.0})
	_apply("G3", {"kind":"impulse", "center":Vector3.ZERO, "radius":1.0, "direction":Vector3.RIGHT, "strength":0.1})
	_check_ledger()
	_check_replay()
	_check_step()
	_check_noop()
	_check_readout()

func _check_rejection() -> void:
	_sim.workbench_resume()
	var r = _sim.workbench_apply({"kind":"deposit", "center":Vector3.ZERO, "radius":1.0, "strength":0.1})
	_sim.workbench_pause()
	_check("G0: operation rejected while playing", _rejected(r))
	var p = _sim.workbench_apply({"kind":"deposit", "center":Vector3.ZERO, "radius":1.0, "strength":0.01})
	_check("G0: paused operation accepted", _ok(p))

func _apply(label: String, command: Dictionary) -> void:
	var result = _sim.workbench_apply(command)
	_check(label + ": " + str(command.get("kind")), _ok(result), str(result))

func _ok(value) -> bool:
	return value is Dictionary and bool(value.get("ok", false))

func _rejected(value) -> bool:
	return value is Dictionary and not bool(value.get("ok", false))

func _check_ledger() -> void:
	var log: Array = _sim.workbench_log()
	var ok := log.size() >= 4
	var expected := 1
	for entry in log:
		if not entry is Dictionary or int(entry.get("id", -1)) != expected: ok = false
		expected += 1
	_check("G4: command order and sequential ids", ok)

func _check_replay() -> void:
	var saved = _sim.workbench_save(SCENARIO_PATH)
	var replay = _sim.workbench_replay(SCENARIO_PATH)
	var ok := _ok(saved) and _ok(replay)
	if ok: ok = int(saved.get("version", 1)) > 0 and str(saved.get("digest", "")) == str(replay.get("digest", ""))
	_check("G5: versioned scenario save/replay exactness", ok, "save=%s replay=%s" % [str(saved), str(replay)])

func _check_step() -> void:
	var before := int(_sim.get("_step_count"))
	var result = _sim.workbench_step(1)
	var after := int(_sim.get("_step_count"))
	_check("G6: paused explicit single-step", _ok(result) and after == before + 1 and not _sim.playing)
	_sim.workbench_resume()
	_sim.workbench_pause()
	_check("G6: pause/resume seam", not _sim.playing)

func _check_noop() -> void:
	var before = _sim.workbench_measure(Vector3.ZERO, 1.0)
	var after = _sim.workbench_measure(Vector3.ZERO, 1.0)
	_check("G7: no-op identity", str(before) == str(after))

func _check_readout() -> void:
	var r: Dictionary = _sim.workbench_measure(Vector3.ZERO, 1.0)
	var ok := _ok(r) and r.has("q") and r.has("rho")
	if ok: ok = absf(float(r.get("rho")) - (float(r.get("ey", 0.0)) + float(r.get("ei", 0.0)))) <= 2.0e-4
	_check("G7: selected readout/lens formulas", ok)

func _check(label: String, passed: bool, detail := "") -> void:
	_checks += 1
	if passed: print("PASS %s%s" % [label, (" — " + detail) if detail != "" else ""])
	else:
		_failures += 1
		print("FAIL %s%s" % [label, (" — " + detail) if detail != "" else ""])

func _finish() -> void:
	print("[Workbench] %d checks, %d failures, elapsed=%d ms" % [_checks, _failures, Time.get_ticks_msec() - _started_ms])
	get_tree().quit(0 if _failures == 0 else 1)
