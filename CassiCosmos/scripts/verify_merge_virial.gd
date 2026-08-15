extends Node
## Cassi Particle Merge — VIRIAL STOPPING SCALE verify (§3c hypothesis gate,
## coherence_merge_rnd.md §3d falsifiable test #5 + its control):
##   "a virialised survivor's cluster of mergers must stop growing (count
##    saturates), unlike the current unbounded collapse-to-one."
##
## A single high-q pair. Particle 0 (lower index, the survivor candidate) is
## planted VIRIALISED: mass 10, |v|=20 → K = ½·10·20² = 2000, R = 0.62·∛10
## ≈ 1.34, W = G_eff·m²/(2R) ≈ 672 → 2K = 4000 ≥ 672 → virialised. Particle 1
## (mass 10, v=0) is bound to it (½μ|v_rel|²·d = 400 < 1800), subsonic, and
## within R_m — WITHOUT the virial gate it would merge.
##
## Two sub-runs:
##   - f_virial = 1  → particle 0 is virialised → merge BLOCKED → alive stays
##     2 across every merge pass (member-set saturates: G-V1, the falsifier).
##   - f_virial = 0  → control: the same pair merges (alive -> 1), proving the
##     virial flag is the sole cause of the block (G-V2, the control).
##   - G-V3: total mass conserved in both sub-runs (≤ 1e-3 rel).
##
## Run (windowed console exe — NEVER --headless):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_merge_virial.tscn

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
const HIGH_EI := 1.0                # q_coh ≈ 0.947 (everywhere)
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
var _fvirial_last := 1.0


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
	_upload_field()
	_build_input()
	# Sub-run 1: f_virial ON → the virialised target blocks the merge.
	_fvirial_last = 1.0
	_upload_input()
	var m1 := _run_merge()
	_check_gate(m1, true)
	# Sub-run 2: f_virial OFF → control, same pair merges.
	_fvirial_last = 0.0
	_upload_input()
	var m2 := _run_merge()
	_check_gate(m2, false)
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
	_pc[21] = _fvirial_last   # f_virial (the criterion under test)
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


## particle 0 (target, lower index): mass 10, |v| = 20 → virialised.
## particle 1 (incoming, would merge): mass 10, v = 0, d = 0.4 < R_m → bound
## (½μ·20²·0.4 = 400 < 1800), subsonic (20 < 1170).
func _build_input() -> void:
	_input_mass = PackedFloat32Array([10.0, 10.0])
	_input_pos = PackedFloat32Array([
		5.0, 0.0, 0.0, 0.0,
		5.4, 0.0, 0.0, 0.0,
	])
	_input_vel = PackedFloat32Array([
		20.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
	])
	for i in range(N):
		_input_pos[i * 4 + 3] = _input_mass[i]


func _upload_input() -> void:
	var pos := _input_pos.duplicate()
	var vel := _input_vel.duplicate()
	var mas := _input_mass.duplicate()
	for i in range(N):
		pos[i * 4 + 3] = mas[i]
	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_rd.buffer_update(_mass_buf, 0, mas.size() * 4, mas.to_byte_array())


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


func _check_gate(merges: int, virial_on: bool) -> void:
	var al := _rd.buffer_get_data(_alive_buf, 0, N * 4).to_float32_array()
	var pd := _rd.buffer_get_data(_pos_buf, 0, N * 16).to_float32_array()
	var alive_cnt := 0
	for i in range(N):
		if al[i] > 0.5:
			alive_cnt += 1
	var m1 := 0.0; for i in range(N): m1 += pd[i * 4 + 3]
	var m0 := 0.0; for i in range(N): m0 += _input_mass[i]
	if virial_on:
		# FALSIFIER: the virialised target rejects → member-set saturates (2 alive)
		_check("G-V1: virialised target stops the merge (alive=2)", alive_cnt == 2,
			"alive=%d merges=%d" % [alive_cnt, merges])
	else:
		# CONTROL: without the virial gate the same pair merges (alive=1)
		_check("G-V2: control (f_virial=0) merges (alive=1)", alive_cnt == 1,
			"alive=%d merges=%d" % [alive_cnt, merges])
	_check("G-V3: total mass conserved (≤1e-3)", absf(m1 - m0) <= 1e-3 * maxf(m0, 1e-9),
		"Σm0=%.4f Σm1=%.4f" % [m0, m1])


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	print("[VerifyMergeVirial] checks=%d failures=%d elapsed=%d ms"
		% [_checks, _failures, Time.get_ticks_msec() - _t0])
	if _failures == 0:
		print("[VerifyMergeVirial] RESULT: PASS")
	else:
		print("[VerifyMergeVirial] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
