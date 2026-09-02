extends SceneTree
## Cassi space-sim verify battery runner — "run the whole battery" in one command.
##
## Launches the 38 verify scenes IN SEQUENCE as standalone project runs of the
## Godot console exe (each arm quits with get_tree().quit(0/1)), prints a
## progress line per arm, logs the stdout/stderr tail (last 15 lines) of every
## FAILED arm from the arm's log file, enforces a per-arm timeout that kills a
## hung arm (taskkill /T /F — the console exe is a wrapper that spawns the real
## Godot process, so the process TREE must be killed), and quits with exit
## code 0 only when all 38 pass.
##
## LAUNCH MODE: every child scene arm runs windowed, sequentially. Both the
## sim's global RenderingDevice and the arms' local RenderingDevices require a
## real window on this rig.
##
## The runner itself never touches a RenderingDevice, so IT may run headless
## (--headless on the runner is fine and recommended). Child scene arms are
## separate processes and are always launched windowed.
##
## Run (from the space-sim project dir, i.e. where project.godot lives):
##   "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe" \
##       --path . --headless -s res://verify/run_all.gd
##   (windowed also works: drop the --headless; only the runner's own window
##    appears — the arms are separate processes either way.)
##
## Notes:
##   - Arms are run one at a time — they share the GPU (serialization is
##     the point, not parallelism).
##   - Per-arm timeout: ARM_TIMEOUT_SEC below (default 240 s). A timed-out
##     arm is killed and counted as FAIL.
##   - Output capture: each arm runs under `cmd /c "<console exe> --path .
##     res://scenes/<scene>.tscn > <log> 2>&1"`, so its stdout/stderr land in
##     res://_diag/battery_logs/armNN_<name>.log (gitignored). The log file
##     is read back for the failure tail. (The console exe's stdout cannot
##     be piped through OS.execute_with_pipe — its pipes never deliver EOF
##     on this platform, which would deadlock a blocking reader.)
##   - Each arm dumps its own JSON/raw artifacts to res://_diag/ (gitignored)
##     for the numpy gates; those are not re-run here — the arm's exit code
##     is the battery contract.

const GODOT_EXE := "C:/Users/Carina/AppData/Local/Microsoft/WinGet/Packages/GodotEngine.GodotEngine.Mono_Microsoft.Winget.Source_8wekyb3d8bbwe/Godot_v4.7.1-stable_mono_win64/Godot_v4.7.1-stable_mono_win64_console.exe"

## Per-arm timeout in seconds; bump if a machine is slow (the arms share
## one GPU and are run strictly serially).
const ARM_TIMEOUT_SEC := 240.0

## Lines of stdout/stderr retained from the arm's log and printed for a
## FAILED arm.
const TAIL_LINES := 15

## Main-loop poll interval in ms — the loop only checks the child pid and
## the log file, so 100 ms (10 polls/s) is plenty.
const POLL_MS := 100

## Grace period after taskkill before declaring the kill unconfirmed.
const KILL_GRACE_SEC := 5.0

const ARMS := [
	"verify_fft",
	"verify_fmm",
	"verify_gravity_modes",
	"verify_merge",
	"verify_meshless_sim",
	"verify_meshless_stability",
	"verify_gridless_physics",
	"verify_phi_box",
	"verify_ring",
	"verify_river_law",
	"validate_sim_ui",
	"verify_particle_vfx",
	"verify_presentation_layers",
	"verify_survey",
	"verify_synth",
	"verify_volumetric",
	"verify_voronoi3d",
	"verify_voronoi3d_moving",
	"verify_meshless_gravity",
	"verify_river_isotropy",
	"verify_merge_sim",
	"verify_meshless_reconstruct",
	"verify_meshless_sim_aniso",
	"verify_particle_vanish",
	"verify_voronoi3d_aniso",
	"verify_voronoi3d_moving_aniso",
	# verify_autotrack removed 2026-08-16 — the Auto-Track CPU band tracker
	# (G49-G53) was removed (owner decision); superseded by the self-adapting
	# velocity-direction / field-phase color modes.
	"verify_falsify",
	"verify_mind_engine",
	"verify_field_intelligence",
	"verify_bh_accretion_engine",
	"verify_merge_engine",
	"verify_multigrid_engine",
	"verify_rho_front",
	"verify_eps_gap",
	"verify_subsonic_step",
	"verify_omega_invariant",
	"verify_tree_hier_refit_engine",
	"verify_particle_world_agent",
]


var _idx := 0            # index of the arm being run (or next to launch)
var _state := 0          # 0 = launch next, 1 = polling arm, 2 = waiting after kill
var _pid := 0
var _log_path := ""
var _start_ms := 0
var _phase_ms := 0       # timestamp of the current state transition
var _exit_code := 0
var _kill_pending := false
var _results: Array[Dictionary] = []
var _t0_ms := 0
var _battery_exit_code := 0


func _initialize() -> void:
	_t0_ms = Time.get_ticks_msec()
	var logs_dir: String = ProjectSettings.globalize_path("res://_diag/battery_logs")
	DirAccess.make_dir_recursive_absolute(logs_dir)
	print("[Battery] ============================================================")
	print("[Battery] Cassi space-sim verify battery — %d arms, %.0f s timeout each" % [ARMS.size(), ARM_TIMEOUT_SEC])
	print("[Battery] exe: %s" % GODOT_EXE)
	print("[Battery] arm logs: %s" % logs_dir)
	_state = 0


func _process(_delta: float) -> bool:
	match _state:
		0:
			if _idx >= ARMS.size():
				_finish()
				return true
			_launch(_idx)
		1:
			_poll()
		2:
			_poll_after_kill()
	OS.delay_msec(POLL_MS)
	return false


func _finalize() -> void:
	print("[Battery] runner exiting (exit code %d)" % _battery_exit_code)


# ── launch / poll ──────────────────────────────────────────────────────

func _launch(i: int) -> void:
	var name: String = ARMS[i]
	var scene := "res://scenes/%s.tscn" % name
	var log_file := "%s/battery_logs/arm%02d_%s.log" % [
		ProjectSettings.globalize_path("res://_diag"), i + 1, name]
	_log_path = log_file.replace("/", "\\")
	var cmd_line := "\"%s\" --path . %s > \"%s\" 2>&1" % [GODOT_EXE.replace("/", "\\"), scene, _log_path]
	print("[Battery] arm %d/%d %s — %s" % [i + 1, ARMS.size(), name, scene])
	_pid = OS.create_process("cmd.exe", PackedStringArray(["/c", cmd_line]))
	if _pid == 0:
		_record(name, false, 0.0, "launch failed")
		_idx += 1
		_state = 0
		return
	_kill_pending = false
	_start_ms = Time.get_ticks_msec()
	_state = 1


func _poll() -> void:
	var elapsed := (Time.get_ticks_msec() - _start_ms) / 1000.0
	if OS.is_process_running(_pid):
		if elapsed > ARM_TIMEOUT_SEC:
			print("[Battery] arm %d/%d %s: TIMEOUT after %.0f s — killing pid %d" % [_idx + 1, ARMS.size(), ARMS[_idx], elapsed, _pid])
			# cmd.exe /c spawns the console wrapper, which spawns the real
			# Godot process; kill the whole tree or orphans keep the GPU
			# and a window.
			OS.execute("taskkill", PackedStringArray(["/PID", "%d" % _pid, "/T", "/F"]))
			_kill_pending = true
			_phase_ms = Time.get_ticks_msec()
			_state = 2
		return
	_exit_code = OS.get_process_exit_code(_pid)
	_record(ARMS[_idx], _exit_code == 0, elapsed, "exit %d" % _exit_code)
	_idx += 1
	_state = 0


func _poll_after_kill() -> void:
	var elapsed := (Time.get_ticks_msec() - _start_ms) / 1000.0
	if not OS.is_process_running(_pid):
		_exit_code = OS.get_process_exit_code(_pid)
		_record(ARMS[_idx], false, elapsed, "killed after timeout (exit %d)" % _exit_code)
		_idx += 1
		_state = 0
	elif (Time.get_ticks_msec() - _phase_ms) > KILL_GRACE_SEC * 1000.0:
		_record(ARMS[_idx], false, elapsed, "killed after timeout (process unconfirmed)")
		_idx += 1
		_state = 0


# ── log reading ────────────────────────────────────────────────────────

## Read the last TAIL_LINES non-empty lines of the arm's log file.
func _read_log_tail() -> Array[String]:
	var tail: Array[String] = []
	var f := FileAccess.open(_log_path, FileAccess.READ)
	if f == null:
		return tail
	var text := f.get_as_text()
	f.close()
	var lines := text.split("\n")
	var start := maxi(lines.size() - TAIL_LINES, 0)
	for i in range(start, lines.size()):
		var ln: String = lines[i].strip_edges()
		if ln != "":
			tail.append(ln)
	return tail


# ── recording / summary ────────────────────────────────────────────────

func _record(name: String, ok: bool, secs: float, note: String) -> void:
	print("[Battery] arm %d/%d %s: %s (%s, %d s)" % [_idx + 1, ARMS.size(), name, "PASS" if ok else "FAIL", note, int(secs)])
	if not ok:
		var tail := _read_log_tail()
		if tail.is_empty():
			print("[Battery]   (log empty: %s)" % _log_path)
		else:
			print("[Battery]   --- last %d lines of %s ---" % [tail.size(), _log_path])
			for line in tail:
				print("[Battery]   | " + line)
	_results.append({"name": name, "ok": ok, "secs": secs, "note": note})


func _finish() -> void:
	var total := (Time.get_ticks_msec() - _t0_ms) / 1000.0
	var failed := 0
	var failed_names: Array[String] = []
	print("[Battery] ============================================================")
	for i in _results.size():
		var r: Dictionary = _results[i]
		var ok: bool = r["ok"]
		print("[Battery]   %2d/%-2d %-28s %s (%d s)" % [i + 1, _results.size(), r["name"], "PASS" if ok else "FAIL", int(r["secs"])])
		if not ok:
			failed += 1
			failed_names.append(r["name"])
	if failed == 0:
		print("[Battery] %d/%d PASS (total %d s)" % [_results.size(), ARMS.size(), int(total)])
		_battery_exit_code = 0
		quit(0)
	else:
		print("[Battery] %d/%d FAILED — %s" % [failed, ARMS.size(), ", ".join(failed_names)])
		_battery_exit_code = 1
		quit(1)
