extends Node
## Cassi Particle Merge — SPIN / angular-momentum verify (§3c doctrine
## principle: "ΣL before = ΣL after across a merge", coherence_merge_rnd.md
## §3d falsifiable test #4).
##
## A single gravitationally-bound pair with TANGENTIAL relative motion:
##   p0 = (5, 0, 0), v0 = (0, +4, 0)   mass 10
##   p1 = (5.4, 0, 0), v1 = (0, −6, 0) mass 10   (p1 = lower index = survivor)
## d = (−0.4,0,0), v_rel = (0,10,0) → the pair's internal L about its COM is
## μ·d×v_rel = 5·(−0.4,0,0)×(0,10,0) = (0,0,−20). The survivor must acquire
## spin[1] ≈ (0,0,−20), and the TOTAL angular momentum about the origin
## (Σ m·p×v + Σ spin) must be conserved across the merge. The asymmetric
## ±velocities give the pair a nonzero COM velocity (p0.y = 10·4+10·(−6) =
## −20 ≠ 0) so G-S4's momentum tolerance is meaningful; the merge physics
## (v_rel, internal L, binding) is unchanged.
##
## Checked BEFORE merge: L = m0·p0×v0 + m1·p1×v1 = (0,0,−20) about the origin
## (the merged body's spin carries the whole pair-internal −20z; the COM now
## moves, so total L about the origin is the sum of internal spin plus the
## orbital term of the moving COM — still exactly conserved).
##
## Gates:
##   G-S1  pair merges (alive loss == 1)
##   G-S2  total L about origin conserved (≤ 1e-3 rel)
##   G-S3  survivor spin == the pair's pre-merge internal L (≤ 1e-3 rel)
##   G-S4  momentum conserved (≤ 1e-3 rel)
##
## Run (windowed console exe — NEVER --headless):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_merge_spin.tscn

const N := 2
const N_GRID := 64
const EXTENT := 37.5
const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const RM_FRAC := 0.5
const H0 := 2.0 * EXTENT / float(N_GRID)
const R_M := RM_FRAC * H0
const Q_TH: float = PHI_INV2
const XI := 17.94427190999916
const G_N := 1.0
const DT := 0.001
const MAX_CYCLES := 16
const HIGH_EY: float = PHI
const HIGH_EI := 1.0                # q_coh ≈ 0.947
const HASH_NX := 128
const HASH_NY := 128
const HASH_NZ := 128
const CELL_W := (2.0 * EXTENT) / float(HASH_NX)
const HASH_TOTAL := HASH_NX * HASH_NY * HASH_NZ
const CELLS := N_GRID * N_GRID * N_GRID

var _rd: RenderingDevice
var _shader: RID
var _pipe: RID
var _us: RID
var _pos_buf: RID
var _vel_buf: RID
var _alive_buf: RID
var _mass_buf: RID
var _mom_buf: RID
var _cen_buf: RID
var _spin_buf: RID
var _fvel_buf: RID
var _mprev_buf: RID
var _ey_buf: RID
var _ei_buf: RID
var _best_buf: RID
var _sink_buf: RID
var _cc_buf: RID
var _cs_buf: RID
var _ch_buf: RID
var _cl_buf: RID
var _mc_buf: RID
var _pc := PackedFloat32Array()

var _input_pos := PackedFloat32Array()
var _input_vel := PackedFloat32Array()
var _input_mass := PackedFloat32Array()
var _checks := 0
var _failures := 0
var _t0 := 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RenderingDevice acquired", false, "no RD — run windowed, not --headless")
		_finish()
		return
	_check("local RenderingDevice acquired", true)
	if not _load_pipeline():
		_finish()
		return
	_make_buffers()
	_build_input()
	_rd.buffer_update(_pos_buf, 0, _input_pos.size() * 4, _input_pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, _input_vel.size() * 4, _input_vel.to_byte_array())
	_upload_field()
	_rd.buffer_update(_mass_buf, 0, _input_mass.size() * 4, _input_mass.to_byte_array())
	var merges := _run_merge()
	_check_gates(merges)
	_finish()


func _load_pipeline() -> bool:
	var sf := load("res://compute/cassi_particle_merge.glsl") as RDShaderFile
	if sf == null:
		_check("merge shader loads", false)
		return false
	_shader = _rd.shader_create_from_spirv(sf.get_spirv())
	_pipe = _rd.compute_pipeline_create(_shader)
	_check("compute pipeline builds", _pipe.is_valid())
	return _pipe.is_valid()


func _make_buffers() -> void:
	_pos_buf = _rd.storage_buffer_create(N * 16)
	_vel_buf = _rd.storage_buffer_create(N * 16)
	_alive_buf = _rd.storage_buffer_create(N * 4)
	_mass_buf = _rd.storage_buffer_create(N * 4)
	_mom_buf = _rd.storage_buffer_create(N * 16)
	_cen_buf = _rd.storage_buffer_create(N * 16)
	_spin_buf = _rd.storage_buffer_create(N * 16)
	_fvel_buf = _rd.storage_buffer_create(CELLS * 16)
	_mprev_buf = _rd.storage_buffer_create(N * 4)
	_ey_buf = _rd.storage_buffer_create(CELLS * 4)
	_ei_buf = _rd.storage_buffer_create(CELLS * 4)
	_best_buf = _rd.storage_buffer_create(N * 4)
	_sink_buf = _rd.storage_buffer_create(N * 4)
	_cc_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_cs_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_ch_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_cl_buf = _rd.storage_buffer_create(N * 4)
	_mc_buf = _rd.storage_buffer_create(64)   # uint mc[16] per-cycle slots
	var zero := PackedByteArray(); zero.resize(64); zero.fill(0)
	_rd.buffer_update(_mc_buf, 0, 64, zero)
	_us = _rd.uniform_set_create([
		_u_storage(0, _pos_buf), _u_storage(1, _vel_buf),
		_u_storage(2, _alive_buf), _u_storage(3, _mass_buf),
		_u_storage(4, _mom_buf), _u_storage(5, _cen_buf),
		_u_storage(6, _ey_buf), _u_storage(7, _ei_buf),
		_u_storage(8, _best_buf), _u_storage(9, _sink_buf),
		_u_storage(10, _cc_buf), _u_storage(11, _cs_buf),
		_u_storage(12, _ch_buf), _u_storage(13, _cl_buf),
		_u_storage(14, _mc_buf), _u_storage(15, _spin_buf),
		_u_storage(16, _fvel_buf), _u_storage(17, _mprev_buf),
	], _shader, 0)


func _u_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _fill_pc(pass_mode: float) -> void:
	_pc.resize(24)   # 24 floats: + cyc_slot@23 (batched hop slot; raw-pass test uses slot 0)
	_pc[0] = float(N); _pc[1] = PHI; _pc[2] = PHI_INV2; _pc[3] = Q_TH
	_pc[4] = R_M; _pc[5] = EXTENT; _pc[6] = EXTENT; _pc[7] = EXTENT
	_pc[8] = float(N_GRID); _pc[9] = float(HASH_NX); _pc[10] = float(HASH_NY); _pc[11] = float(HASH_NZ)
	_pc[12] = CELL_W; _pc[13] = CELL_W; _pc[14] = CELL_W
	_pc[15] = pass_mode
	_pc[16] = G_N; _pc[17] = XI; _pc[18] = H0; _pc[19] = DT
	_pc[20] = 1.0   # f_subsonic
	_pc[21] = 1.0   # f_virial
	_pc[22] = 1.0   # f_order
	_pc[23] = 0.0   # cyc_slot (batched hop slot; the raw-pass test uses slot 0)


func _dispatch(pass_mode: float) -> void:
	_fill_pc(pass_mode)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	_rd.compute_list_bind_uniform_set(cl, _us, 0)
	_rd.compute_list_set_push_constant(cl, _pc.to_byte_array(), _pc.size() * 4)
	_rd.compute_list_dispatch(cl, int(ceil(float(N) / 256.0)), 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


## One bound pair with tangential orbital motion: L_internal = μ·d×v_rel
## = 5·(−0.4,0,0)×(0,10,0) = (0,0,−20). Binding: ½μ|v_rel|²·d = 100 < 1800 ✓.
## Asymmetric v0/v1 (0,±) → nonzero COM velocity; v_rel kept (0,10,0).
func _build_input() -> void:
	_input_mass = PackedFloat32Array([10.0, 10.0])
	_input_pos = PackedFloat32Array([
		5.0, 0.0, 0.0, 0.0,
		5.4, 0.0, 0.0, 0.0,
	])
	_input_vel = PackedFloat32Array([
		0.0, 4.0, 0.0, 0.0,
		0.0, -6.0, 0.0, 0.0,
	])
	for i in range(N):
		_input_pos[i * 4 + 3] = _input_mass[i]


func _upload_field() -> void:
	var ey := PackedFloat32Array(); ey.resize(CELLS)
	var ei := PackedFloat32Array(); ei.resize(CELLS)
	for c in range(CELLS):
		ey[c] = HIGH_EY
		ei[c] = HIGH_EI
	_rd.buffer_update(_ey_buf, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_ei_buf, 0, ei.size() * 4, ei.to_byte_array())


func _run_merge() -> int:
	_dispatch(0.0)
	var total := 0
	for cyc in range(MAX_CYCLES):
		_dispatch(1.0)
		zero_uints(_cc_buf, HASH_TOTAL)
		_dispatch(2.0)
		var cc := _rd.buffer_get_data(_cc_buf, 0, HASH_TOTAL * 4).to_int32_array()
		var cs := PackedInt32Array(); cs.resize(HASH_TOTAL)
		var run := 0
		for c in range(HASH_TOTAL):
			cs[c] = run
			run += cc[c]
		_rd.buffer_update(_cs_buf, 0, cs.size() * 4, cs.to_byte_array())
		_rd.buffer_update(_ch_buf, 0, cs.size() * 4, cs.to_byte_array())
		_dispatch(3.0)
		_dispatch(4.0)
		zero_uints(_mc_buf, 1)
		_dispatch(5.0)
		var merges := read_uint(_mc_buf)
		total += merges
		if merges == 0:
			break
	_dispatch(6.0)
	return total


func zero_uints(buf: RID, count: int) -> void:
	var z := PackedByteArray(); z.resize(count * 4); z.fill(0)
	_rd.buffer_update(buf, 0, z.size(), z)


func read_uint(buf: RID) -> int:
	var d := _rd.buffer_get_data(buf, 0, 4)
	return int(d.decode_u32(0))


func _check_gates(merges: int) -> void:
	var al := _rd.buffer_get_data(_alive_buf, 0, N * 4).to_float32_array()
	var pd := _rd.buffer_get_data(_pos_buf, 0, N * 16).to_float32_array()
	var vd := _rd.buffer_get_data(_vel_buf, 0, N * 16).to_float32_array()
	var sp := _rd.buffer_get_data(_spin_buf, 0, N * 16).to_float32_array()
	# G-S1: merged
	var alive_cnt := 0
	for i in range(N):
		if al[i] > 0.5:
			alive_cnt += 1
	_check("G-S1: pair merges (alive=1)", alive_cnt == 1, "alive=%d" % alive_cnt)
	# pre-merge L about origin (input canonical masses/positions/velocities)
	var l0 := Vector3.ZERO
	for i in range(N):
		l0 += _input_mass[i] * Vector3(_input_pos[i * 4], _input_pos[i * 4 + 1], _input_pos[i * 4 + 2]) \
			.cross(Vector3(_input_vel[i * 4], _input_vel[i * 4 + 1], _input_vel[i * 4 + 2]))
	# post-merge L about origin: Σ over alive survivors of (m·p×v) + spin
	var l1 := Vector3.ZERO
	for i in range(N):
		if al[i] > 0.5:
			var m: float = pd[i * 4 + 3]
			var p := Vector3(pd[i * 4], pd[i * 4 + 1], pd[i * 4 + 2])
			var v := Vector3(vd[i * 4], vd[i * 4 + 1], vd[i * 4 + 2])
			l1 += m * p.cross(v) + Vector3(sp[i * 4], sp[i * 4 + 1], sp[i * 4 + 2])
	var lrel := (l1 - l0).length() / maxf(l0.length(), 1e-30)
	_check("G-S2: total L about origin conserved (≤1e-3)", lrel <= 1e-3,
		"rel=%.8f L0=%s L1=%s" % [lrel, l0, l1])
	# G-S3: survivor spin == the pair's pre-merge INTERNAL L about the pair
	# COM. With a nonzero COM velocity the origin-frame L0 no longer equals
	# the spin target, so compare against the analytic constant of the test
	# data: L_int = μ·d×v_rel (a conserved internal quantity, independent of
	# the COM translation added for G-S4). μ = m0·m1/(m0+m1) = 5,
	# d = p0−p1, v_rel = v0−v1 → L_int = 5·(−0.4,0,0)×(0,10,0) = (0,0,−20).
	var mu: float = _input_mass[0] * _input_mass[1] / (_input_mass[0] + _input_mass[1])
	var pv0 := Vector3(_input_pos[0], _input_pos[1], _input_pos[2])
	var pv1 := Vector3(_input_pos[4], _input_pos[5], _input_pos[6])
	var vv0 := Vector3(_input_vel[0], _input_vel[1], _input_vel[2])
	var vv1 := Vector3(_input_vel[4], _input_vel[5], _input_vel[6])
	var l_int: Vector3 = mu * (pv0 - pv1).cross(vv0 - vv1)
	for i in range(N):
		if al[i] > 0.5:
			var sl := Vector3(sp[i * 4], sp[i * 4 + 1], sp[i * 4 + 2])
			var srel := (sl - l_int).length() / maxf(l_int.length(), 1e-30)
			_check("G-S3: survivor spin == pair internal L (≤1e-3)", srel <= 1e-3,
				"rel=%.8f spin=%s L_int=%s" % [srel, sl, l_int])
	# G-S4: momentum
	var p0 := Vector3.ZERO
	var p1v := Vector3.ZERO
	for i in range(N):
		p0 += _input_mass[i] * Vector3(_input_vel[i * 4], _input_vel[i * 4 + 1], _input_vel[i * 4 + 2])
		p1v += pd[i * 4 + 3] * Vector3(vd[i * 4], vd[i * 4 + 1], vd[i * 4 + 2])
	var prel := (p1v - p0).length() / maxf(p0.length(), 1e-30)
	_check("G-S4: momentum conserved (≤1e-3)", prel <= 1e-3, "rel=%.8f" % prel)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	print("[VerifyMergeSpin] checks=%d failures=%d elapsed=%d ms"
		% [_checks, _failures, Time.get_ticks_msec() - _t0])
	if _failures == 0:
		print("[VerifyMergeSpin] RESULT: PASS")
	else:
		print("[VerifyMergeSpin] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
