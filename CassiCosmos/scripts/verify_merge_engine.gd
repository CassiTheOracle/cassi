extends Node3D
## In-engine battery — the Cassi PARTICLE MERGE ported into the standalone
## physics engine (scripts/cassi_physics_engine.gd, behind the engine config
## key `particle_merge`). It first instantiates the engine on a main-thread
## local RD (rd_global=false, owns_rd=true), plants deterministic close pairs,
## and exercises the submit()+sync() path. It then creates a second engine with
## rd_global=true and records the no-readback command-list path used by the
## decoupled renderer into a verifier-owned local RD for deterministic readback.
##
## Gates:
##   G52  merged count converges (3 high pairs merge) + total mass conserved
##        (≤ 1e-3 relative).
##   G53  dead particles are pos.w = 0 and never deposit (Σρ == Σ live).
##   G54  LOW-q pairs do NOT merge (the φ⁻² gate).
##   G102 global list preserves survivor set/mass/momentum, resets cadence,
##        propagates meshless+boxless without gridless physics, and waits for
##        the first published query hash before enabling the indexed read.
##   G103 two consecutive no-merge cadences preserve intervening canonical
##        position/velocity updates instead of restoring the prior snapshot.
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
	var cfg := _engine_config(_rd, false, true)
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
	_run_global_record_gate()
	_finish()


func _engine_config(rd: RenderingDevice, use_global_path: bool, owns_device: bool) -> Dictionary:
	return {
		"rd": rd, "rd_global": use_global_path, "owns_rd": owns_device,
		"grid_N": GRID_N, "N_particles": 8,
		"cluster_radius": 25.0, "box_aspect": Vector3.ONE,
		"freeze_field": true, "gravity_mode": 2, "source_strength": 0.0,
		"black_holes_enabled": false, "dual_grid": false,
		"meshless_mode": false, "meshless_gravity": false,
		"particle_merge": true,
		"merge_cadence_steps": 1,
		"initial_radius_fraction": 0.9,
	}


## Exercise the no-readback command-list path used by the decoupled renderer.
## A local RD is intentional here: marking the engine rd_global=true selects
## record_merge_if_due(), while the verifier remains able to submit/sync and
## inspect the completed list deterministically.
func _run_global_record_gate() -> void:
	_release_engine()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("merge G102: global-record verifier RD acquired", false)
		return
	_eng = load("res://scripts/cassi_physics_engine.gd").new()
	var cfg := _engine_config(_rd, true, false)
	cfg["meshless_mode"] = true
	cfg["meshless_gravity"] = false
	cfg["gridless_physics"] = false
	cfg["boxless_field"] = true
	var setup_ok: bool = _eng.setup(cfg) and _eng.finish_setup()
	_check("merge G102: global-record engine setup", setup_ok)
	if not setup_ok:
		return
	_check("merge G102: boxless config propagates without gridless physics",
		_eng.boxless_field and _eng.meshless_mode and not _eng.gridless_physics)
	_check("merge G102: boxless read waits for a published query hash",
		not bool(_eng._merge_pc_dict()["boxless"]))
	_plant_field()
	_plant_particles()
	# Isolate merge recording from the physics integrator: make the cadence due
	# exactly once, then record the real global fold→zero→count→scan→fill→
	# best→hop→finalize chain into one open command list.
	_eng._step_count = 1
	_eng._merge_step_counter = 1
	var cl := _rd.compute_list_begin()
	var recorded: bool = _eng.record_merge_if_due(cl)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	var state := _read_state()
	var expected := PackedInt32Array([0, 2, 4, 6, 7])
	var got := PackedInt32Array()
	for i in state["alive"]:
		got.append(i)
	var mass_after := 0.0
	for m in state["mass"]:
		mass_after += m
	var momentum_after := _state_momentum(state)
	var cadence_reset: bool = _eng._merge_step_counter == 0
	var immediate_retry := false
	if cadence_reset:
		immediate_retry = _eng.record_merge_if_due(-1)
	_check("merge G102: global list records one due phase", recorded
		and _eng._merge_cycles_run == 1)
	_check("merge G102: global pass marks dead slots and expected survivors",
		got == expected, "got=%s" % str(got))
	_check("merge G102: global pass conserves mass",
		absf(mass_after - _pre_merge_total()) <= 1e-3 * _pre_merge_total(),
		"before=%.4f after=%.4f" % [_pre_merge_total(), mass_after])
	var p0 := _pre_merge_momentum()
	_check("merge G102: global pass conserves momentum",
		momentum_after.distance_to(p0) <= 1e-3 * maxf(p0.length(), 1e-9),
		"before=%s after=%s" % [p0, momentum_after])
	_check("merge G102: cadence counter resets and cannot rerun immediately",
		cadence_reset and not immediate_retry,
		"counter=%d immediate=%s" % [_eng._merge_step_counter, immediate_retry])
	# G103: establish one no-merge cadence, emulate the physics integrator's
	# intervening canonical pos/vel update, then record a second no-merge
	# cadence. A stale mom/cen snapshot must not roll that motion back.
	_eng._merge_step_counter = 1
	var cl_idle_a := _rd.compute_list_begin()
	var idle_a_recorded: bool = _eng.record_merge_if_due(cl_idle_a)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	var moved_state := _read_state()
	var moved_pos: PackedFloat32Array = moved_state["position"]
	var moved_vel: PackedFloat32Array = moved_state["velocity"]
	var expected_x: float = moved_pos[0] + 1.25
	var expected_vx: float = moved_vel[0] + 0.375
	moved_pos[0] = expected_x
	moved_vel[0] = expected_vx
	_rd.buffer_update(_eng._pos_buf, 0, moved_pos.size() * 4, moved_pos.to_byte_array())
	_rd.buffer_update(_eng._vel_buf, 0, moved_vel.size() * 4, moved_vel.to_byte_array())
	_eng._merge_step_counter = 1
	var cl_idle_b := _rd.compute_list_begin()
	var idle_b_recorded: bool = _eng.record_merge_if_due(cl_idle_b)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	var after_motion := _read_state()
	var after_pos: PackedFloat32Array = after_motion["position"]
	var after_vel: PackedFloat32Array = after_motion["velocity"]
	_check("merge G103: two no-merge cadences preserve intervening canonical motion",
		idle_a_recorded and idle_b_recorded
			and absf(after_pos[0] - expected_x) <= 1e-5
			and absf(after_vel[0] - expected_vx) <= 1e-5
			and after_motion["alive"] == moved_state["alive"],
		"x expected=%.6f got=%.6f vx expected=%.6f got=%.6f"
			% [expected_x, after_pos[0], expected_vx, after_vel[0]])


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
	var pos_raw: PackedByteArray = _rd.buffer_get_data(_eng._pos_buf, 0, 8 * 16)
	var vel_raw: PackedByteArray = _rd.buffer_get_data(_eng._vel_buf, 0, 8 * 16)
	var pd: PackedFloat32Array = pos_raw.to_float32_array()
	var vd: PackedFloat32Array = vel_raw.to_float32_array()
	var alive := PackedInt32Array()
	var mass := PackedFloat32Array()
	for i in range(8):
		mass.append(pd[i * 4 + 3])
		if pd[i * 4 + 3] > 0.0:
			alive.append(i)
	return {
		"alive": Array(alive), "mass": Array(mass),
		"position": pd, "velocity": vd,
	}


func _sigma_mass_live(s: Dictionary) -> float:
	var mass: Array = s["mass"]; var alive: Array = s["alive"]
	var tot := 0.0
	for i in alive: tot += mass[i]
	return tot


func _pre_merge_total() -> float:
	var tot := 0.0
	for m in _plant_mass: tot += m
	return tot


func _pre_merge_momentum() -> Vector3:
	var total := Vector3.ZERO
	for i in range(_plant_mass.size()):
		total += Vector3(
			_plant_vel[i * 4], _plant_vel[i * 4 + 1], _plant_vel[i * 4 + 2]) \
			* _plant_mass[i]
	return total


func _state_momentum(s: Dictionary) -> Vector3:
	var mass: Array = s["mass"]
	var velocity: PackedFloat32Array = s["velocity"]
	var total := Vector3.ZERO
	for i in range(mass.size()):
		total += Vector3(
			velocity[i * 4], velocity[i * 4 + 1], velocity[i * 4 + 2]) * mass[i]
	return total


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

	# G52 scheduler regression: a second four-cycle submission must consume
	# count slots 4..7 rather than rereading the first batch at slots 0..3.
	var batch_counts := PackedInt32Array(
		[100, 100, 100, 100, 8, 7, 6, 5, 0, 0, 0, 0, 0, 0, 0, 0])
	var later_batch := CassiMergeCommon.merge_batch_result(batch_counts, 4, 4)
	_check("merge G52: later scheduler batch reads slots 4..7",
		later_batch == Vector2i(26, 5), "result=%s" % str(later_batch))

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


func _release_engine() -> void:
	if _eng != null:
		var engine_owns_device := bool(_eng.get("_owns_rd"))
		_eng.shutdown()
		_eng = null
		if _rd != null and not engine_owns_device:
			_rd.free()
	elif _rd != null:
		_rd.free()
	_rd = null


func _finish() -> void:
	var d_ms := Time.get_ticks_msec() - _t0
	_release_engine()
	print("[VerifyMergeEngine] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, d_ms])
	print("[VerifyMergeEngine] RESULT: %s" % ("PASS" if _failures == 0 else "FAIL"))
	get_tree().quit(0 if _failures == 0 else 1)
