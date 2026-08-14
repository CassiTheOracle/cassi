extends Node3D
## In-engine battery — the Cassi BH ACCRETION ported into the standalone
## physics engine (scripts/cassi_physics_engine.gd, behind the engine config
## key `bh_accretion`, default off). Instantiates the ENGINE on a main-thread
## local RD (setup(), rd_global=false, owns_rd=true) — the same submit()+sync()
## local-RD path the decoupled worker uses — plants a BH record in slot 0
## (bh[base]=pos+mass, base=4+0·2) + a cloud of particles (some inside the
## accretion radius R_acc), and gates G55–G57.
##
## Gates (turn brief):
##   G55  BH mass gain == Σ swallowed particle masses — accretion is exactly
##        conserved (atomicAdd of the full pos.w into bh[base].w), with the
##        growth term zeroed (acc_rate=0) so accretion is the only change.
##   G56  swallowed particles are marked dead (pos.w = 0) and never deposit
##        (Σρ == Σ live after a fresh step); in-radius ones dead, far ones alive.
##   G57  toggle-off bit-identical: with bh_accretion=false the same plants do
##        NOT swallow — all particles stay alive and the BH mass is unchanged.
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_bh_accretion_engine.tscn

const GRID_N := 64
const EXTENT := 37.5          # cluster_radius(25) * 1.5 — cube, matches verify_merge
const R_ACC := 0.5            # accretion radius (world units)
const INIT_BH_MASS := 1.0     # planted BH slot-0 mass

# Swallowed (within R_ACC of the planted BH at the origin): indices 0,1,2.
var _plant_mass := PackedFloat32Array([1.0, 2.0, 3.0, 7.0, 4.0, 6.0, 9.0, 5.0])
var _plant_pos := PackedFloat32Array([
	0.10, 0.00, 0.00, 0.0,   0.00, 0.20, 0.00, 0.0,   -0.18, 0.00, 0.00, 0.0,  # in-radius (0,1,2)
	10.0, 3.0, -4.0, 0.0,    -12.0, 2.0, 5.0, 0.0,   6.0, -9.0, 1.0, 0.0,    # far (3,4,5)
	-8.0, 6.0, -3.0, 0.0,    11.0, -5.0, -8.0, 0.0,                            # far (6,7)
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

	# ── ARM 1: accretion ON (G55/G56) ──────────────────────────────
	# owns_rd=false: arm 2 reuses this same local RD and is the one that frees it.
	_eng = _make_engine(true, false)
	if _eng == null:
		_finish()
		return
	print("[VerifyBHAcc] [ON] setup ok — pipe=%s set=%s"
		% [_eng._bh_acc_pipe.is_valid(), _eng._us_bh_acc_0.is_valid()])
	_check("bh-accretion pipe+set valid (toggle ON)",
		_eng._bh_acc_pipe.is_valid() and _eng._us_bh_acc_0.is_valid())
	_plant_field(_eng)
	_plant_bh(_eng, INIT_BH_MASS, false)   # BH at origin, vel 0
	_plant_particles(_eng)
	_eng.run_steps(1)
	var bh_m1 := _read_bh_mass(_eng)
	var dead1 := _read_dead(_eng)
	_check("G55: BH slot-0 mass grew by Σ swallowed (1+2+3 from acc_rate=0)",
		absf(bh_m1 - (INIT_BH_MASS + 6.0)) <= 1e-3,
		"bh=%.4f (expected %.4f)" % [bh_m1, INIT_BH_MASS + 6.0])
	_check("G56: in-radius (0,1,2) dead pos.w=0; far (3..7) alive",
		dead1[0] == 1.0 and dead1[1] == 1.0 and dead1[2] == 1.0
			and dead1[3] == 0.0 and dead1[4] == 0.0 and dead1[5] == 0.0
			and dead1[6] == 0.0 and dead1[7] == 0.0,
		"dead=%s" % str(dead1))
	# Global mass conservation: Σ live pos.w + BH mass == Σ initial (plant + BH).
	var live_mass := _sigma_live_posw(_eng)
	_check("G55: total mass conserved (Σ live pos.w + BH == Σ initial)",
		absf((live_mass + bh_m1) - (_pre_total_mass() + INIT_BH_MASS)) <= 1e-3,
		"Σlive=%.4f + bh=%.4f = %.4f (expected %.4f)"
			% [live_mass, bh_m1, live_mass + bh_m1, _pre_total_mass() + INIT_BH_MASS])
	# G56 deposit gate: a fresh step deposits only the LIVE survivors.
	_eng.run_steps(1)
	var rho_sum := _read_rho_sum(_eng)
	_check("G56: dead masses do NOT deposit (Σρ == Σ live pos.w)",
		absf(rho_sum - live_mass) <= 0.01 * maxf(live_mass, 1e-9),
		"Σρ=%.4f Σlive=%.4f" % [rho_sum, live_mass])
	_eng.shutdown(); _eng = null

	# ── ARM 2: accretion OFF (G57 — toggle-off bit-identical) ───────
	_eng = _make_engine(false, true)
	if _eng == null:
		_finish()
		return
	print("[VerifyBHAcc] [OFF] setup ok")
	_check("bh-accretion pipe invalid when toggle OFF (default-off path untouched)",
		not _eng._bh_acc_shader.is_valid() and not _eng._bh_acc_pipe.is_valid())
	_plant_field(_eng)
	_plant_bh(_eng, INIT_BH_MASS, false)
	_plant_particles(_eng)
	_eng.run_steps(1)
	var bh_m2 := _read_bh_mass(_eng)
	var dead2 := _read_dead(_eng)
	_check("G57: toggle-OFF — NO particle swallowed (all 8 alive)",
		dead2[0] == 0.0 and dead2[1] == 0.0 and dead2[2] == 0.0
			and dead2[3] == 0.0 and dead2[4] == 0.0 and dead2[5] == 0.0
			and dead2[6] == 0.0 and dead2[7] == 0.0,
		"dead=%s" % str(dead2))
	_check("G57: toggle-OFF — BH mass unchanged during the step (acc_rate=0)",
		absf(bh_m2 - INIT_BH_MASS) <= 1e-3,
		"bh=%.4f (expected %.4f)" % [bh_m2, INIT_BH_MASS])
	_eng.shutdown(); _eng = null
	_finish()


func _make_engine(acc_on: bool, own_rd: bool) -> Object:
	var eng = load("res://scripts/cassi_physics_engine.gd").new()
	var cfg := {
		"rd": _rd, "rd_global": false, "owns_rd": own_rd,
		"grid_N": GRID_N, "N_particles": 8,
		"cluster_radius": 25.0, "box_aspect": Vector3(1.0, 1.0, 1.0),
		"freeze_field": true, "gravity_mode": 2, "source_strength": 0.0,
		"black_holes_enabled": true, "dual_grid": false,
		"meshless_mode": false, "meshless_gravity": false,
		"particle_merge": false,
		"bh_accretion": acc_on, "bh_accretion_radius": R_ACC,
		"bh_acc_rate": 0.0, "bh_max_age": 0,
		"initial_radius_fraction": 0.9,
	}
	if not eng.setup(cfg):
		_check("engine setup (bh_accretion=%s)" % acc_on, false, "setup() returned false")
		return null
	return eng


func _plant_field(eng) -> void:
	# Uniform low field: below any condensation nucleation → only the planted
	# slot-0 BH exists, and acc_rate=0 kills BH-integrate growth, so accretion
	# is the ONLY mass mover. No high-q region to confuse G55.
	var f := PackedFloat32Array(); f.resize(GRID_N * GRID_N * GRID_N); f.fill(0.05)
	_rd.buffer_update(eng._field_ey, 0, f.size() * 4, f.to_byte_array())
	_rd.buffer_update(eng._field_ei, 0, f.size() * 4, f.to_byte_array())


func _plant_bh(eng, bhm: float, _active_check: bool) -> void:
	# The engine's run_steps re-uploads _bh_init_bytes (the full 576-B header,
	# slots 0-33 = zeros because condensation is what normally nucleates BHs)
	# to _bh_buf at the start of every batch. So we MUST patch the engine's
	# CACHED header to carry the planted slot-0 record (bytes 64..95):
	#   bh[4] = vec4(pos.xyz, mass)   → bytes 64..79  (mass .w @ byte 76)
	#   bh[5] = vec4(vel, age)        → bytes 80..95
	var b: PackedByteArray = eng._bh_init_bytes
	if b.size() < 96:
		push_error("[VerifyBHAcc] _bh_init_bytes too small (%d) — plant aborted" % b.size())
		return
	# pos.xyz = origin, mass @ byte 76
	b.encode_float(64, 0.0); b.encode_float(68, 0.0); b.encode_float(72, 0.0)
	b.encode_float(76, bhm)
	# vel.xyz = 0, age = 0
	b.encode_float(80, 0.0); b.encode_float(84, 0.0); b.encode_float(88, 0.0)
	b.encode_float(92, 0.0)
	# Also patch the live buffer so reads before the next run_steps see it.
	_rd.buffer_update(eng._bh_buf, 0, b.size(), b)


func _plant_particles(eng) -> void:
	for i in range(_plant_mass.size()):
		_plant_pos[i * 4 + 3] = _plant_mass[i]
	_rd.buffer_update(eng._pos_buf, 0, _plant_pos.size() * 4, _plant_pos.to_byte_array())
	var vel_z := PackedFloat32Array(); vel_z.resize(_plant_pos.size()); vel_z.fill(0.0)
	_rd.buffer_update(eng._vel_buf, 0, vel_z.size() * 4, vel_z.to_byte_array())


func _read_bh_mass(eng) -> float:
	# bh[4].w = byte 64+12 = 76.
	var d: PackedByteArray = _rd.buffer_get_data(eng._bh_buf, 76, 4)
	return d.to_float32_array()[0] if d.size() >= 4 else -1.0


func _read_dead(eng) -> PackedFloat32Array:
	# pos[i].w — 1.0 = dead, 0.0 = alive.
	var raw: PackedByteArray = _rd.buffer_get_data(eng._pos_buf, 0, 8 * 16)
	var pd: PackedFloat32Array = raw.to_float32_array()
	var dead := PackedFloat32Array()
	for i in range(8):
		dead.append(1.0 if pd[i * 4 + 3] <= 0.0 else 0.0)
	return dead


func _sigma_live_posw(eng) -> float:
	var raw: PackedByteArray = _rd.buffer_get_data(eng._pos_buf, 0, 8 * 16)
	var pd: PackedFloat32Array = raw.to_float32_array()
	var tot := 0.0
	for i in range(8):
		if pd[i * 4 + 3] > 0.0: tot += pd[i * 4 + 3]
	return tot


func _pre_total_mass() -> float:
	var tot := 0.0
	for m in _plant_mass: tot += m
	return tot


func _read_rho_sum(eng) -> float:
	var raw: PackedByteArray = _rd.buffer_get_data(eng._mass_density_buf, 0, GRID_N * GRID_N * GRID_N * 4)
	var rh: PackedFloat32Array = raw.to_float32_array()
	var tot := 0.0
	for v in rh: tot += v
	return tot


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok: _failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var d_ms := Time.get_ticks_msec() - _t0
	if _eng != null:
		_eng.shutdown(); _eng = null
	print("[VerifyBHAcc] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, d_ms])
	print("[VerifyBHAcc] RESULT: %s" % ("PASS" if _failures == 0 else "FAIL"))
	get_tree().quit(0 if _failures == 0 else 1)
