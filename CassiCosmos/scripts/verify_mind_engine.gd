extends Node
## Stage 0 verify — mind engine no-op gate.
## Drives the engine inline (auto_step=false, serve_bridge=false):
##   Gate A (the no-op control): an attractor-ratio deposit (cy=φ, ci=1)
##     makes the conversion term vanish — the field's coupling does
##     nothing. After 50 steps max|ε|² must stay at the fp32 noise floor.
##   Gate B: an off-ratio deposit (cy=3, ci=1) evolves 1000 steps —
##     charge EY+EI is conserved and the field stays bounded. (This
##     shader's conversion term is a conservative oscillator, not a
##     damper; damped relaxation toward φ needs the gate term — Stage 2.)
##   Structural: no NaN/Inf anywhere.
## Dumps planted inputs + consumed states verbatim to
## res://_diag/mind_engine_gpu.json for the numpy gate
## research/mind/stage0_verify.py.
##
## Run (windowed — headless has no RenderingDevice on this rig):
##   godot --path <repo> res://scenes/verify_mind_engine.tscn

const PHI := 1.618033988749895
const DEP_X := 0.3
const DEP_Y := -0.2
const DEP_Z := 0.15

var _eng: Node
var _checks := 0
var _failures := 0


func _ready() -> void:
	_eng = load("res://scripts/cassi_mind_engine.gd").new()
	_eng.auto_step = false
	_eng.serve_bridge = false
	add_child(_eng)
	_run()


func _run() -> void:
	_check("engine local RD acquired", _eng._rd != null)
	if _eng._rd == null:
		_finish()
		return
	_check("engine pipeline built", _eng._pipe.is_valid())

	# Gate A: attractor-ratio deposit stays dormant (the no-op control).
	_eng._clear_field()
	_eng.deposit(DEP_X, DEP_Y, DEP_Z, PHI, 1.0, 1.0)
	_eng._flush_pending()
	var rb0: Array = _eng.readback_ey_ei()
	var ey0: PackedFloat32Array = rb0[0]
	var ei0: PackedFloat32Array = rb0[1]
	_check("gate A deposit: no NaN/Inf", _finite(ey0) and _finite(ei0))
	_eng.step_n(50)
	var st_a: Dictionary = _eng.compute_state()
	_check("gate A: attractor ratio stays dormant (max eps2 < 1e-5)",
		st_a["max_eps2"] < 1e-5, "max_eps2=" + str(st_a["max_eps2"]))

	# Gate B: off-ratio deposit — charge conserved, field stays bounded.
	_eng._clear_field()
	_eng.deposit(DEP_X, DEP_Y, DEP_Z, 3.0, 1.0, 1.0)
	_eng._flush_pending()
	var rb1: Array = _eng.readback_ey_ei()
	var ey1: PackedFloat32Array = rb1[0]
	var ei1: PackedFloat32Array = rb1[1]
	var charge_0 := _sum_charge(ey1, ei1)
	var qmax_0 := _max_q(ey1, ei1)
	_check("gate B deposit: no NaN/Inf", _finite(ey1) and _finite(ei1))
	_eng.step_n(1000)
	var st_b: Dictionary = _eng.compute_state()
	var rb2: Array = _eng.readback_ey_ei()
	var ey2: PackedFloat32Array = rb2[0]
	var ei2: PackedFloat32Array = rb2[1]
	var charge_1 := _sum_charge(ey2, ei2)
	var qmax_1 := _max_q(ey2, ei2)
	_check("gate B: charge EY+EI conserved over 1000 steps",
		absf(charge_1 - charge_0) < 1e-2 * charge_0,
		str(charge_0) + " -> " + str(charge_1))
	_check("gate B: field stays bounded (max q < 2x initial)",
		qmax_1 < 2.0 * qmax_0 + 1e-12,
		str(qmax_0) + " -> " + str(qmax_1))
	_check("gate B final: no NaN/Inf", _finite(ey2) and _finite(ei2))

	# Gate C: sigma != 1.0 must conserve charge exactly (the renormalized
	# envelope fix — a sigma-invariant scatter). sigma=2 on the same deposit.
	_eng._clear_field()
	_eng.deposit(DEP_X, DEP_Y, DEP_Z, 3.0, 1.0, 2.0)
	_eng._flush_pending()
	var rb3: Array = _eng.readback_ey_ei()
	var ey3: PackedFloat32Array = rb3[0]
	var ei3: PackedFloat32Array = rb3[1]
	var cy_sum := 0.0
	var ci_sum := 0.0
	for i in range(ey3.size()):
		cy_sum += ey3[i]
		ci_sum += ei3[i]
	_check("gate C (sigma=2): scatter conserves charge (sumEY≈3, sumEI≈1)",
		absf(cy_sum - 3.0) < 1e-3 and absf(ci_sum - 1.0) < 1e-3,
		str(cy_sum) + " / " + str(ci_sum))
	_check("gate C (sigma=2): no NaN/Inf", _finite(ey3) and _finite(ei3))

	# ── Stage 4: projection gate (top-k attractor readout) ──────────────
	var PJ_X := 0.25
	var PJ_Y := -0.4
	var PJ_Z := 0.6
	var PJ_CY := 1.4562
	var PJ_CI := 0.9
	var n_g: int = _eng.grid_n

	# Gate D: deposit at a KNOWN position + 1 step; project k=8. The top cell
	# must land within ±1 of the TSC anchor cell on every axis.
	_eng._clear_field()
	_eng.deposit(PJ_X, PJ_Y, PJ_Z, PJ_CY, PJ_CI, 1.0)
	_eng._flush_pending()
	_eng.step_n(1)
	var proj_d: Dictionary = _eng.compute_projection(8)
	var cells_d: Array = proj_d["cells"]
	var top_cell: Dictionary = cells_d[0]
	var agx: int = _anchor_cell(PJ_X, 1.0, n_g)
	var agy: int = _anchor_cell(PJ_Y, 1.0, n_g)
	var agz: int = _anchor_cell(PJ_Z, 1.0, n_g)
	var tgx: int = top_cell["gx"]
	var tgy: int = top_cell["gy"]
	var tgz: int = top_cell["gz"]
	_check("gate D: top cell within ±1 of deposit anchor (every axis)",
		abs(tgx - agx) <= 1 and abs(tgy - agy) <= 1 and abs(tgz - agz) <= 1,
		"top=(%d,%d,%d) anchor=(%d,%d,%d)" % [tgx, tgy, tgz, agx, agy, agz])
	_check("gate D: k=8 returns 8 cells", cells_d.size() == 8,
		"size=" + str(cells_d.size()))
	_check("gate D: cells sorted non-increasing in q", _sorted_desc(cells_d), "")
	_check("gate D: top cell q == ey^2 + ei^2 (CPU-side)",
		absf(float(top_cell["q"])
			- (float(top_cell["ey"]) * float(top_cell["ey"])
				+ float(top_cell["ei"]) * float(top_cell["ei"]))) < 1e-6,
		"q=" + str(top_cell["q"]))

	# Protocol-level reply for the deposited charge (top 3 cells for the report).
	var relay_d: Dictionary = JSON.parse_string(
		_eng._handle_line('{"cmd":"project","k":8}'))
	var relay_has: bool = (relay_d.get("ok") == true
		and relay_d.get("cmd") == "project"
		and relay_d.has("step") and relay_d.has("t")
		and (relay_d.get("cells") is Array)
		and (relay_d["cells"] as Array).size() == 8)
	_check("gate D: projection reply has ok/cmd/step/t/cells[k=8]",
		relay_has, str(relay_d.keys()))
	var top3: Array = []
	for t in range(mini(3, (relay_d["cells"] as Array).size())):
		top3.append(relay_d["cells"][t])

	# Gate E: empty field → ok=true with k cells all q=0.
	_eng._clear_field()
	var relay_e: Dictionary = JSON.parse_string(
		_eng._handle_line('{"cmd":"project","k":8}'))
	var cells_e: Array = relay_e["cells"]
	var all_zero := true
	for c in cells_e:
		if float(c["q"]) != 0.0:
			all_zero = false
	_check("gate E: empty field ok=true, k cells all q=0",
		bool(relay_e["ok"]) and all_zero and cells_e.size() == 8,
		"size=" + str(cells_e.size()))

	# Gate F: k=0 / negative / absent / non-number → behaves as k=8.
	var f0: Dictionary = JSON.parse_string(_eng._handle_line('{"cmd":"project","k":0}'))
	var fn: Dictionary = JSON.parse_string(_eng._handle_line('{"cmd":"project","k":-7}'))
	var fa: Dictionary = JSON.parse_string(_eng._handle_line('{"cmd":"project"}'))
	var fs: Dictionary = JSON.parse_string(_eng._handle_line('{"cmd":"project","k":"abc"}'))
	_check("gate F: k=0 behaves as k=8", (f0["cells"] as Array).size() == 8)
	_check("gate F: k<0 behaves as k=8", (fn["cells"] as Array).size() == 8)
	_check("gate F: k absent behaves as k=8", (fa["cells"] as Array).size() == 8)
	_check("gate F: k non-number behaves as k=8", (fs["cells"] as Array).size() == 8)

	# Gate G: k huge (100000) → clamped to 4096, returns cells, ok=true.
	var big: Dictionary = JSON.parse_string(
		_eng._handle_line('{"cmd":"project","k":100000}'))
	var cells_g: Array = big["cells"]
	_check("gate G: k=100000 clamped, ok=true, cells returned",
		bool(big["ok"]) and cells_g.size() == 4096,
		"size=" + str(cells_g.size()))
	_check("gate G: clamped array sorted non-increasing in q", _sorted_desc(cells_g), "")

	_dump(ey0, ei0, ey1, ei1, ey2, ei2, ey3, ei3, st_a, st_b, relay_d, top3, relay_e)
	_finish()


func _finite(a: PackedFloat32Array) -> bool:
	for v in a:
		if is_nan(v) or is_inf(v):
			return false
	return true


func _sum_charge(ey: PackedFloat32Array, ei: PackedFloat32Array) -> float:
	var s := 0.0
	for i in range(ey.size()):
		s += ey[i] + ei[i]
	return s


func _max_q(ey: PackedFloat32Array, ei: PackedFloat32Array) -> float:
	var m := 0.0
	for i in range(ey.size()):
		m = maxf(m, ey[i] * ey[i] + ei[i] * ei[i])
	return m


## Anchor cell for a physical coordinate — matches _scatter's rounding:
## g = (p/extent+1)*0.5*N, anchor = floor(g+0.5) mod N (TSC center).
func _anchor_cell(p: float, ext: float, n: int) -> int:
	var g: float = (p / ext + 1.0) * 0.5 * float(n)
	return int(floor(g + 0.5)) % n


func _sorted_desc(cells: Array) -> bool:
	for i in range(1, cells.size()):
		if float(cells[i]["q"]) > float(cells[i - 1]["q"]):
			return false
	return true


func _dump(ey0: PackedFloat32Array, ei0: PackedFloat32Array,
		ey1: PackedFloat32Array, ei1: PackedFloat32Array,
		ey2: PackedFloat32Array, ei2: PackedFloat32Array,
		ey3: PackedFloat32Array, ei3: PackedFloat32Array,
		st_a: Dictionary, st_b: Dictionary,
		relay_d: Dictionary, top3: Array, relay_e: Dictionary) -> void:
	var d := {
		"N": _eng.grid_n, "dt": _eng.dt, "extent": [1.0, 1.0, 1.0],
		"dep_x": DEP_X, "dep_y": DEP_Y, "dep_z": DEP_Z,
		"gate_a": {"cy": PHI, "ci": 1.0, "steps": 50, "max_eps2": st_a["max_eps2"]},
		"gate_b": {"cy": 3.0, "ci": 1.0, "steps": 1000,
			"max_eps2": st_b["max_eps2"], "mean_ey": st_b["mean_ey"], "mean_ei": st_b["mean_ei"]},
		"gate_c": {"cy": 3.0, "ci": 1.0, "sigma": 2.0},
		"project": {
			"deposit": {"x": 0.25, "y": -0.4, "z": 0.6, "cy": 1.4562, "ci": 0.9, "sigma": 1.0},
			"k": 8,
			"reply": relay_d,
			"top3": top3,
			"empty_reply": relay_e,
		},
		"ey0_b64": Marshalls.raw_to_base64(ey0.to_byte_array()),
		"ei0_b64": Marshalls.raw_to_base64(ei0.to_byte_array()),
		"ey1_b64": Marshalls.raw_to_base64(ey1.to_byte_array()),
		"ei1_b64": Marshalls.raw_to_base64(ei1.to_byte_array()),
		"ey2_b64": Marshalls.raw_to_base64(ey2.to_byte_array()),
		"ei2_b64": Marshalls.raw_to_base64(ei2.to_byte_array()),
		"ey3_b64": Marshalls.raw_to_base64(ey3.to_byte_array()),
		"ei3_b64": Marshalls.raw_to_base64(ei3.to_byte_array()),
	}
	var f := FileAccess.open("res://_diag/mind_engine_gpu.json", FileAccess.WRITE)
	if f == null:
		_check("JSON dump written to res://_diag/mind_engine_gpu.json", false,
			"FileAccess failed")
		return
	f.store_string(JSON.stringify(d))
	f.close()
	_check("JSON dump written to res://_diag/mind_engine_gpu.json", true)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	print("[VerifyMindEngine] checks=%d failures=%d" % [_checks, _failures])
	if _failures == 0:
		print("[VerifyMindEngine] RESULT: PASS — state dumped for stage0_verify.py")
	else:
		print("[VerifyMindEngine] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
