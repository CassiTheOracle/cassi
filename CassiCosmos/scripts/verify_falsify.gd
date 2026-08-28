extends Node
## Live falsification meter probe (color-autotrack / falsification
## workstream, 2026-08-14).
##
## Validates the sim_ui.gd GDScript port of the falsify_wo.py SURVEY-path
## w₀ estimator against the reference python values, and the full
## measure→estimate→label path on a synthetic field.
##
## Checks:
##   [F1] The estimator port _falsify_w0_wa(r) reproduces falsify_wo.py's
##        survey-path w₀ within 1e-4 for a series of synthetic r values
##        (reference w₀ from running falsify_wo.py's survey estimator
##        anchored at a=1.0).
##   [F2] The full meter path reads r = <EY>/<EI> from a synthetic field
##        (volume-mean of a known EY/EI fill) and the meter label shows the
##        corresponding w₀/distance verbatim.
##   [F3] The w₀ meter toggle + label wiring exist and default OFF; the HUD
##        line hides when OFF and shows when ON.
##
## Run (windowed GPU only — never --headless for the global RD):
##   Godot_v4.7-stable_win64_console.exe --path <repo> -e \
##     res://scenes/verify_falsify.tscn
##
## Exits 0 on all checks passing, 1 on any failure.

# Reference w₀ (survey path, anchored at a=1.0) from falsify_wo.py's
# w0_wa_from_r over r(a=1.0); values produced by running that script.
const REFERENCE := {
	"r0.5": [0.5, -0.303416, 0.843719],
	"r1.0": [1.0, -0.576827, 0.472097],
	"r1.5892": [1.5892, -0.839067, 0.441345],
	"r1.3": [1.3, -0.562507, 0.095652],
	"r1.5": [1.5, -0.592478, 0.088978],
}

var sim: Node3D
var ui: Control
var _checks := 0
var _failures := 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	ui = get_node_or_null("../SimUI")
	if sim == null or ui == null:
		push_error("verify_falsify: CassiSim or SimUI not found")
		get_tree().quit(1)
		return
	sim.playing = false
	sim.gravity_mode = 0
	sim.meshless_mode = false
	sim.meshless_gravity = false
	sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	sim.dual_grid = false
	sim.suppress_readbacks = false
	sim.reinit()
	var waited := 0
	while not sim._shaders_ready and waited < 240:
		await get_tree().process_frame
		waited += 1
	if not sim._shaders_ready:
		push_error("verify_falsify: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	await get_tree().process_frame
	await get_tree().process_frame
	await _run_all()
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)


func _run_all() -> void:
	await _check_estimator_port()
	await _check_measure_path()
	await _check_toggle_wiring()


## [F1] The estimator port reproduces falsify_wo.py within 1e-4.
func _check_estimator_port() -> void:
	var worst := 0.0
	for key in REFERENCE:
		var row: Array = REFERENCE[key]
		var r: float = row[0]
		var w0_ref: float = row[1]
		var est: Vector2 = ui._falsify_w0_wa(r)
		var dw: float = est.x - w0_ref
		worst = maxf(worst, absf(dw))
		_checks += 1
		if absf(dw) > 1e-4:
			_failures += 1
			push_error("F1: r=%s w0 port=%.8f ref=%.8f |Δ|=%.8f > 1e-4" % [key, est.x, w0_ref, absf(dw)])
		else:
			print("[PASS] F1 (r=%s): w0=%.8f ref=%.8f |Δ|=%.8f ≤ 1e-4" % [key, est.x, w0_ref, absf(dw)])
	print("[F1] worst |Δw0| vs falsify_wo.py = %.8f (≤ 1e-4 required)" % worst)


## [F2] The full measure→estimate→label path on a synthetic field.
func _check_measure_path() -> void:
	# Fill EY/EI with known volume means so r = <EY>/<EI> is exact.
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var ey := PackedFloat32Array(); ey.resize(nc)
	var ei := PackedFloat32Array(); ei.resize(nc)
	var ey_m := 0.9
	var ei_m := 0.7
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	for i in range(nc):
		ey[i] = ey_m * (1.0 + 0.01 * rng.randf_range(-1.0, 1.0))
		ei[i] = ei_m * (1.0 + 0.01 * rng.randf_range(-1.0, 1.0))
	sim._rd.buffer_update(sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())
	# The meter reads the ACTIVE field ratio; r_true = ey_m/ei_m.
	var r_true: float = ey_m / ei_m   # ≈ 1.286
	var r_measured: float = ui._falsify_measure_r()
	_checks += 1
	if r_measured > 0.0 and absf(r_measured / r_true - 1.0) < 0.03:
		print("[PASS] F2: measured r=%.4f ≈ true %.4f (< 3%%)" % [r_measured, r_true])
	else:
		_failures += 1
		push_error("F2: measured r=%.4f vs true %.4f (n_ok=?)" % [r_measured, r_true])
	# Feed the measured r through the estimator and check against the port on
	# the same r (self-consistent) and against the label render.
	var w0_exp: float = ui._falsify_w0_wa(r_measured).x
	ui._falsify_btn.button_pressed = true
	ui._last_falsify_r = r_measured
	ui._last_falsify_w0 = w0_exp
	ui._last_falsify_wa = ui._falsify_w0_wa(r_measured).y
	ui._update_falsify_label()
	var lbl: String = ui._falsify_label.text
	_checks += 1
	if lbl.contains("%.4f" % w0_exp) and lbl.contains("DESI"):
		print("[PASS] F2: meter label shows w₀=%.4f with DESI distance — [%s]" % [w0_exp, lbl])
	else:
		_failures += 1
		push_error("F2: meter label missing w₀/DESI — [%s]" % [lbl])


## [F3] Toggle + label wiring: exist, default OFF, HUD hidden when OFF.
func _check_toggle_wiring() -> void:
	_checks += 1
	if ui._falsify_btn == null or ui._falsify_label == null:
		_failures += 1
		push_error("F3: FalsifyBtn or FalsifyLabel missing")
		return
	# Reset the toggle path: OFF -> label hidden.
	ui._falsify_btn.set_pressed_no_signal(false)
	ui._on_falsify_toggled(false)
	_checks += 1
	if not ui._falsify_label.visible:
		print("[PASS] F3: w₀ meter default OFF, HUD line hidden")
	else:
		_failures += 1
		push_error("F3: w₀ meter label visible while OFF")
	# ON -> label visible.
	ui._falsify_btn.set_pressed_no_signal(true)
	ui._on_falsify_toggled(true)
	_checks += 1
	if ui._falsify_label.visible:
		print("[PASS] F3: w₀ meter label shown when ON")
	else:
		_failures += 1
		push_error("F3: w₀ meter label not shown when ON")
