extends Node3D
## In-engine battery — the Cassi PARTICLE MERGE ported into the standalone
## physics engine (scripts/cassi_physics_engine.gd, behind the engine config
## key `particle_merge`). Instantiates the ENGINE on a main-thread local RD
## (setup(), rd_global=false, owns_rd=true) — the same submit()+sync() local-RD
## path the decoupled worker uses for the merge's per-cycle host prefix-sum
## readbacks — plants a piecewise-coherence field + deterministic close pairs,
## drives a step (which runs the merge at the end of run_steps), and gates
## G52–G54 exactly as verify_merge_sim does for the SIM's non-decoupled path.
##
## Gates (turn brief):
##   G52  merged count converges (3 high pairs merge) + total mass conserved
##        (≤ 1e-3 relative).
##   G53  dead particles are pos.w = 0 and never deposit (Σρ == Σ live).
##   G54  LOW-q pairs do NOT merge (the φ⁻² gate).
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_merge_engine.tscn

const GRID_N := 64
const EXTENT := 37.5          # cluster_radius(25) * 1.5 — cube, matches verify_merge
const PHI: float = 1.618033988749895
const HIGH_EY: float = PHI
const HIGH_EI := 1.0          # q_coh ≈ 0.947
const LOW_EY := 0.05
const LOW_EI := 0.05          # q_coh ≈ 0.03
const CELLS: int = GRID_N * GRID_N * GRID_N

var _plant_mass := PackedFloat32Array([7.0, 3.0, 12.0, 5.0, 2.0, 9.0, 4.0, 4.0])
var _plant_pos := PackedFloat32Array([
	5.0, 0.0, 0.0, 0.0,   5.35, 0.0, 0.0, 0.0,    # pair A (high) — merges
	5.0, 4.0, 1.0, 0.0,   5.0, 4.3, 1.0, 0.0,     # pair B (high) — merges
	8.0, -4.0, 2.0, 0.0,  8.3, -4.0, 2.0, 0.0,    # pair C (high) — merges
	-5.0, 6.0, 3.0, 0.0, -5.35, 6.0, 3.0, 0.0,    # pair D (low)  — free-streams
])
var _plant_vel := PackedFloat32Array([
	0.1, 0.2, -0.1, 0.0,   -0.2, 0.05, 0.3, 0.0,
	0.0, 0.1, 0.2, 0.0,     0.15, -0.1, 0.0, 0.0,
	-0.1, 0.0, 0.25, 0.0,   0.2, 0.3, -0.05, 0.0,
	0.05, 0.0, 0.0, 0.0,    -0.05, 0.0, 0.0, 0.0,
])

var _eng = null        # CassiPhysicsEngine (RefCounted)
var _rd: RenderingDevice = null
var _phase := 0
var _checks := 0
var _failures := 0
var _t0 := 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("engine local RD acquired", false, "no RD — run windowed, not --headless")
		_finish()
		return
	_check("engine local RD acquired", true)
	_eng = load("res://scripts/cassi_physics_engine.gd").new()
	var cfg := {
		"rd": _rd, "rd_global": false, "owns_rd": true,
		"grid_N": GRID_N, "N_particles": 8,
		"cluster_radius": 25.0, "box_aspect": Vector3(1.0, 1.0, 1.0),
		"freeze_field": true, "gravity_mode": 2, "source_strength": 0.0,
		"black_holes_enabled": false, "dual_grid": false,
		"meshless_mode": false, "meshless_gravity": false,
		"particle_merge": true,
		"merge_cadence_steps": 1,   # per-batch merge for the test (the AUTO budget is config-scale)
		"initial_radius_fraction": 0.9,
	}
	var ok: bool = _eng.setup(cfg)
	if not ok:
		_check("engine setup", false, "setup() returned false")
		_finish()
		return
	_check("engine setup (merge pipe=%s set=%s)"
		% [_eng._merge_pipe.is_valid(), _eng._us_merge_0.is_valid()], ok)
	_plant_field()
	_plant_particles()
	print("[VerifyMergeEngine] planted — R_m=%.4f (h0=%.4f), hash=%dx%dx%d"
		% [0.5 * (2.0 * EXTENT / float(GRID_N)), 2.0 * EXTENT / float(GRID_N),
		_eng._merge_hash_nx, _eng._merge_hash_ny, _eng._merge_hash_nz])
	# Drive 1 step (runs the merge at the end of run_steps on this local RD),
	# then a second run_steps(1) as the "next pass" (converged → no new merges).
	_eng.run_steps(1)
	var s_a := _read_state()
	_eng.run_steps(1)
	var s_b := _read_state()
	_check_gates(s_a, s_b)
	# G53 deposit gate: after the merges, Σρ (the deposit's mass grid) must
	# equal Σ live pos.w — dead masses (pos.w=0) did not deposit.
	var live := _sigma_mass_live(s_b)
	_eng.run_steps(1)   # a fresh step deposits the LIVE survivors
	var rho_sum := _read_rho_sum()
	_check("merge G53: dead masses do NOT deposit (Σρ == Σ live)",
		absf(rho_sum - live) <= 0.01 * maxf(live, 1e-9),
		"Σρ=%.4f Σlive=%.4f (pre-merge Σm=%.4f)" % [rho_sum, live, _pre_merge_total()])
	_finish()


func _plant_field() -> void:
	var ey := PackedFloat32Array(); ey.resize(CELLS)
	var ei := PackedFloat32Array(); ei.resize(CELLS)
	for cx in range(GRID_N):
		for cy in range(GRID_N):
			for cz in range(GRID_N):
				var id := cx + GRID_N * (cy + GRID_N * cz)
				var wx: float = ((float(cx) + 0.5) / float(GRID_N) * 2.0 - 1.0) * EXTENT
				if wx > 0.0:
					ey[id] = HIGH_EY; ei[id] = HIGH_EI
				else:
					ey[id] = LOW_EY; ei[id] = LOW_EI
	_rd.buffer_update(_eng._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_eng._field_ei, 0, ei.size() * 4, ei.to_byte_array())


func _plant_particles() -> void:
	for i in range(_plant_mass.size()):
		_plant_pos[i * 4 + 3] = _plant_mass[i]
	_rd.buffer_update(_eng._pos_buf, 0, _plant_pos.size() * 4, _plant_pos.to_byte_array())
	_rd.buffer_update(_eng._vel_buf, 0, _plant_vel.size() * 4, _plant_vel.to_byte_array())


func _read_state() -> Dictionary:
	var raw: PackedByteArray = _rd.buffer_get_data(_eng._pos_buf, 0, 8 * 16)
	var pd: PackedFloat32Array = raw.to_float32_array()
	var alive := PackedInt32Array()
	var mass := PackedFloat32Array()
	for i in range(8):
		mass.append(pd[i * 4 + 3])
		if pd[i * 4 + 3] > 0.0:
			alive.append(i)
	return {"alive": Array(alive), "mass": Array(mass)}


func _sigma_mass_live(s: Dictionary) -> float:
	var mass: Array = s["mass"]; var alive: Array = s["alive"]
	var tot := 0.0
	for i in alive: tot += mass[i]
	return tot


func _pre_merge_total() -> float:
	var tot := 0.0
	for m in _plant_mass: tot += m
	return tot


func _read_rho_sum() -> float:
	var raw: PackedByteArray = _rd.buffer_get_data(_eng._mass_density_buf, 0, GRID_N * GRID_N * GRID_N * 4)
	var rh: PackedFloat32Array = raw.to_float32_array()
	var tot := 0.0
	for v in rh: tot += v
	return tot


func _check_gates(s1: Dictionary, s2: Dictionary) -> void:
	var a1: Array = s1["alive"]; var a2: Array = s2["alive"]
	var mass1: Array = s1["mass"]; var mass2: Array = s2["mass"]
	print("[VerifyMergeEngine] state A: %d alive, state B: %d alive, ΣmB=%.4f"
		% [a1.size(), a2.size(), _sigma_mass_live(s2)])

	# G52a: merged count monotonic (A→B, converged → no new merges)
	var c1 := 8 - a1.size()
	var c2 := 8 - a2.size()
	_check("merge G52: merged count monotonic (A=%d → B=%d)" % [c1, c2],
		c2 >= c1 and (c2 - c1) <= 1, "cA=%d cB=%d" % [c1, c2])

	# G52b: total mass conserved (≤ 1e-3 relative)
	var total0 := 0.0
	for m in _plant_mass: total0 += m
	var total1 := 0.0
	for m in mass2: total1 += m
	_check("merge G52: total mass conserved (≤1e-3 rel)",
		absf(total1 - total0) <= 1e-3 * total0, "Σm0=%.4f Σm1=%.4f" % [total0, total1])

	# G54: the LOW-q pair (6,7) did NOT merge — both alive, masses intact.
	var alive_low := (a2.has(6) and a2.has(7))
	_check("merge G54: LOW-q pair (6,7) free-streams (φ⁻² gate blocks)",
		alive_low and absf(mass2[6] - 4.0) < 1e-6 and absf(mass2[7] - 4.0) < 1e-6,
		"alive6=%s alive7=%s m6=%.4f m7=%.4f" % [a2.has(6), a2.has(7), mass2[6], mass2[7]])

	# Expected survivor set after the 3 high merges: {0,2,4,6,7}
	var exp := PackedInt32Array([0, 2, 4, 6, 7])
	var got := PackedInt32Array()
	for i in range(8):
		if a2.has(i): got.append(i)
	_check("merge G53: dead marked pos.w=0, survivors {0,2,4,6,7}",
		got == exp, "got=%s" % str(got))


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok: _failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var d_ms := Time.get_ticks_msec() - _t0
	# shutdown() (owns_rd=true) already freed the device; do not free twice.
	if _eng != null:
		_eng.shutdown()
	print("[VerifyMergeEngine] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, d_ms])
	print("[VerifyMergeEngine] RESULT: %s" % ("PASS" if _failures == 0 else "FAIL"))
	get_tree().quit(0 if _failures == 0 else 1)
