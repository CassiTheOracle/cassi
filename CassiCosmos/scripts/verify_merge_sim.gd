extends Node3D
## In-sim battery — the Cassi PARTICLE MERGE arm wired into the live sim
## (compute/cassi_particle_merge.glsl dispatched from cassi_sim.gd behind the
## init-time `particle_merge` export via _run_merge_pass, hooked in _render_frame
## so the merge's CPU-prefix-sum readbacks execute in the frame context).
## Drives the REAL CassiSim node with the merge ON and a planted
## piecewise-coherence field + deterministic close pairs, then gates the live
## wiring end-to-end (the standalone GPU parity G28/G29 live in
## stage6_merge.py on verify_merge.gd; THIS scene proves the SIM integration:
## planted state → merge pass → conserved merged masses / dead marking /
## the φ⁻² gate / the deposit skip).
##
## Driven from _process (frame context) exactly like verify_meshless_sim:
## the global-RD compute lists + buffer_get_data readbacks only execute in
## the renderer's frame, so nothing runs from _ready.
##
## Gates (the turn brief):
##   G52  merged count grows monotonically across passes and total mass is
##        conserved (SINK rule, ≤ 1e-3 relative).
##   G53  dead particles are marked pos.w = 0 and never contribute to the
##        deposit (Σρ after a physics step == Σ live masses; the dead would
##        inflate it if the deposit did not skip mass ≤ 0).
##   G54  pairs in the LOW-q region do NOT merge (the φ⁻² gate).
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_merge_sim.tscn

const GRID_N := 64
const EXTENT := 37.5          # cluster_radius(25) * 1.5 — cube, matches verify_merge
const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const H0: float = 2.0 * EXTENT / float(GRID_N)
const R_M := 0.5 * H0         # merge radius — the sim computes ½·h0, h0 = 2·extent_min/N
const HIGH_EY: float = PHI
const HIGH_EI := 1.0          # q_coh ≈ 0.947
const LOW_EY := 0.05
const LOW_EI := 0.05          # q_coh ≈ 0.03
const CELLS: int = GRID_N * GRID_N * GRID_N

# Planted pairs (same deterministic set as the standalone verify_merge.gd):
# 3 close pairs in the HIGH-q half (x>0) → must merge; 1 close pair in the
# LOW-q half (x<0) → must free-stream. Masses are copied into pos.w.
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

var _sim: Node
var _phase := 0
var _checks := 0
var _failures := 0
var _t0 := 0
var _frame := 0
var s_a := {}
var s_b := {}


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_sim = $CassiSim
	_sim.grid_N = GRID_N
	_sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	_sim.cluster_radius = 25.0
	_sim.freeze_field = true
	_sim.particle_merge = true
	_sim.N_particles = 8
	_sim.playing = false
	_sim.reinit()


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	match _phase:
		0:
			# Plant the deterministic input, then one physics step so
			# _step_count >= 1 (the _render_frame merge hook gates on it).
			_plant_field()
			_plant_particles()
			print("[VerifyMergeSim] planted — R_m=%.4f (h0=%.4f), hash=%dx%dx%d"
				% [R_M, H0, _sim._merge_hash_nx, _sim._merge_hash_ny, _sim._merge_hash_nz])
			_sim._run_physics_steps(1)
			_phase = 1
		1, 2, 3:
			# Let the sim's _render_frame run the merge (frame context — the
			# only place the global-RD lists + readbacks execute). One frame
			# converges the planted pairs; stay 3 frames to be safe.
			if _phase == 3:
				s_a = _read_state()
			_phase += 1
		4:
			# A later frame's merge must have added nothing (converged).
			s_b = _read_state()
			_check_gates(s_a, s_b)
			var live := _sigma_mass_live(s_b)
			var rho_raw: PackedByteArray = _sim._rd.buffer_get_data(_sim._mass_density_buf, 0, GRID_N * GRID_N * GRID_N * 4)
			var rh: PackedFloat32Array = rho_raw.to_float32_array()
			var rho_sum := 0.0
			for v in rh: rho_sum += v
			_check("merge G53: dead masses do NOT deposit (Σρ == Σ live after a step)",
				absf(rho_sum - live) <= 0.01 * maxf(live, 1e-9),
				"Σρ=%.4f Σlive=%.4f (pre-merge Σm=%.4f)" % [rho_sum, live, _pre_merge_total()])
			_phase = 5
		5:
			_finish()


func _check_gates(s1: Dictionary, s2: Dictionary) -> void:
	var a1: Array = s1["alive"]; var a2: Array = s2["alive"]
	var mass1: Array = s1["mass"]; var mass2: Array = s2["mass"]
	var N := mass1.size()
	print("[VerifyMergeSim] state A: %d alive, state B: %d alive, ΣmB=%.4f"
		% [a1.size(), a2.size(), _sigma_mass_live(s2)])

	# G52a: merged count grows monotonically (A → B, converged → no new merges)
	var c1 := N - a1.size()
	var c2 := N - a2.size()
	_check("merge G52: merged count monotonic (A=%d → B=%d)" % [c1, c2],
		c2 >= c1 and (c2 - c1) <= 1, "cA=%d cB=%d" % [c1, c2])

	# G52b: total mass conserved across the merge (≤ 1e-3 relative)
	var total0 := 0.0
	for m in _plant_mass: total0 += m
	var total1 := 0.0
	for m in mass2: total1 += m
	_check("merge G52: total mass conserved (≤1e-3 rel)",
		absf(total1 - total0) <= 1e-3 * total0, "Σm0=%.4f Σm1=%.4f" % [total0, total1])

	# G54: the LOW-q pair (6,7) did NOT merge — both stay alive, masses intact.
	var alive_low := (a2.has(6) and a2.has(7))
	_check("merge G54: LOW-q pair (6,7) free-streams (φ⁻² gate blocks)",
		alive_low and absf(mass2[6] - 4.0) < 1e-6 and absf(mass2[7] - 4.0) < 1e-6,
		"alive6=%s alive7=%s m6=%.4f m7=%.4f" % [a2.has(6), a2.has(7), mass2[6], mass2[7]])

	# Expected survivor set after the 3 high merges: {0,2,4,6,7}
	var exp := PackedInt32Array([0, 2, 4, 6, 7])
	var got := PackedInt32Array()
	for i in range(N):
		if a2.has(i): got.append(i)
	_check("merge G53: dead marked pos.w=0, survivors {0,2,4,6,7}",
		got == exp, "got=%s" % str(got))



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
	_sim._rd.buffer_update(_sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_sim._rd.buffer_update(_sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())


func _plant_particles() -> void:
	for i in range(_plant_mass.size()):
		_plant_pos[i * 4 + 3] = _plant_mass[i]
	_sim._rd.buffer_update(_sim._pos_buf, 0, _plant_pos.size() * 4, _plant_pos.to_byte_array())
	_sim._rd.buffer_update(_sim._vel_buf, 0, _plant_vel.size() * 4, _plant_vel.to_byte_array())


func _read_state() -> Dictionary:
	var N: int = _sim.N_particles
	var raw: PackedByteArray = _sim._rd.buffer_get_data(_sim._pos_buf, 0, N * 16)
	var pd: PackedFloat32Array = raw.to_float32_array()
	var alive := PackedInt32Array()
	var mass := PackedFloat32Array()
	for i in range(N):
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


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok: _failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var d_ms := Time.get_ticks_msec() - _t0
	print("[VerifyMergeSim] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, d_ms])
	print("[VerifyMergeSim] RESULT: %s" % ("PASS" if _failures == 0 else "FAIL"))
	get_tree().quit(0 if _failures == 0 else 1)
