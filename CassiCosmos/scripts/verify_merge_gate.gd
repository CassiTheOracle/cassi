extends Node
## Cassi Particle Merge — ORDER-SELECTIVE GATE verify (§3a doctrine gate,
## coherence_merge_rnd.md §3d falsifiable test #1):
##   "a smooth standing wave at ρ=5 passes; same-amplitude white-noise field
##    must NOT pass q_sel > φ⁻²."
##
## Two field halves, SAME amplitude (q_coh ≈ 0.496 > φ⁻² in BOTH — so only
## the order term q_ord can discriminate):
##   - LEFT half (x < 0): EY = A, EI = 0 constant → Σ = EY+φEI smooth,
##     q_ord ≈ 1 → q_sel ≈ q_coh passes → pair merges.
##   - RIGHT half (x > 0): EY = A·(−1)^(i+j+k) (cell-scale checkerboard,
##     EI = 0) → Σ ragged, q_ord ≈ 0.15 → q_sel ≈ 0.07 ≤ φ⁻² blocked →
##     pair free-streams.
## The checkerboard (period = 2 cells) gives |∇Σ| comparable to Σ/h, so q_ord
## drops well below the φ⁻² crossover — the loud-rough field is rejected.
## Both pairs are bound (v_rel = 0), subsonic, cold (not virialised): the ONLY
## discriminator is the order gate.
##
## Gates:
##   G-G1  smooth pair merges (alive loss == 1)
##   G-G2  checkerboard pair free-streams (alive loss == 0)
##   G-G3  total mass conserved (≤ 1e-3 rel)
##
## Run (windowed console exe — NEVER --headless):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_merge_gate.tscn

const N := 4
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
const A := 5.0                    # amplitude (q_coh ≈ 0.496 in both halves)
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
var _site_dummy_buf: RID   # boxless site-read set (bindings 18-24) — unindexed dummy (boxless off)
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
	_site_dummy_buf = _rd.storage_buffer_create(8192 * 16)   # boxless site set — unindexed (boxless off); sized like _ml_sites
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
		# Boxless site/query set (bindings 18-29). Dummies satisfy descriptor
		# validation; the boxless flag is off in this verifier.
		_u_storage(18, _site_dummy_buf), _u_storage(19, _site_dummy_buf),
		_u_storage(20, _site_dummy_buf), _u_storage(21, _site_dummy_buf),
		_u_storage(22, _site_dummy_buf), _u_storage(23, _site_dummy_buf),
		_u_storage(24, _site_dummy_buf), _u_storage(25, _site_dummy_buf),
		_u_storage(26, _site_dummy_buf), _u_storage(27, _site_dummy_buf),
		_u_storage(28, _site_dummy_buf), _u_storage(29, _site_dummy_buf),
	], _shader, 0)


func _u_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _fill_pc(pass_mode: float) -> void:
	_pc.resize(26)   # 26 floats: + boxless@24 + n_sites@25 (merge_boxless_prereg.md; both 0 here)
	_pc[0] = float(N); _pc[1] = PHI; _pc[2] = PHI_INV2; _pc[3] = Q_TH
	_pc[4] = R_M; _pc[5] = EXTENT; _pc[6] = EXTENT; _pc[7] = EXTENT
	_pc[8] = float(N_GRID); _pc[9] = float(HASH_NX); _pc[10] = float(HASH_NY); _pc[11] = float(HASH_NZ)
	_pc[12] = CELL_W; _pc[13] = CELL_W; _pc[14] = CELL_W
	_pc[15] = pass_mode
	_pc[16] = G_N; _pc[17] = XI; _pc[18] = H0; _pc[19] = DT
	_pc[20] = 1.0   # f_subsonic
	_pc[21] = 1.0   # f_virial
	_pc[22] = 1.0   # f_order (the criterion under test)
	_pc[23] = 0.0   # cyc_slot (batched hop slot; the raw-pass test uses slot 0)
	_pc[24] = 0.0   # boxless (site-direct read) — off in these tests → grid path
	_pc[25] = 0.0   # n_sites (nearest-site guard) — unused when boxless off


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


## pair 0-1 in the SMOOTH half (x<0): masses 10/10, v_rel = 0 → must merge.
## pair 2-3 in the CHECKERBOARD half (x>0): same, → must NOT merge.
func _build_input() -> void:
	_input_mass = PackedFloat32Array([10.0, 10.0, 10.0, 10.0])
	_input_pos = PackedFloat32Array([
		-5.0, 0.0, 0.0, 0.0,
		-5.4, 0.0, 0.0, 0.0,
		5.0, 0.0, 0.0, 0.0,
		5.4, 0.0, 0.0, 0.0,
	])
	_input_vel = PackedFloat32Array([
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
	])
	for i in range(N):
		_input_pos[i * 4 + 3] = _input_mass[i]


## LEFT half (x<0): EY = A constant (smooth Σ). RIGHT half (x>0):
## EY = A·(−1)^(i+j+k) (cell-scale checkerboard — maximal incoherent
## roughness). EI = 0 everywhere. q_coh = A²/(2A²+φ⁻²) ≈ 0.496 in BOTH halves
## (only q_ord differs).
func _upload_field() -> void:
	var ey := PackedFloat32Array(); ey.resize(CELLS)
	var ei := PackedFloat32Array(); ei.resize(CELLS)
	for cx in range(N_GRID):
		for cy in range(N_GRID):
			for cz in range(N_GRID):
				var id := cx + N_GRID * (cy + N_GRID * cz)
				var wx: float = ((float(cx) + 0.5) / float(N_GRID) * 2.0 - 1.0) * EXTENT
				var cb := 1.0 if ((cx + cy + cz) & 1) == 0 else -1.0
				ey[id] = A if wx < 0.0 else A * cb
				ei[id] = 0.0
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
	# pair 0-1 (smooth) must merge; pair 2-3 (checkerboard) must not
	var a01 := (1.0 if al[0] > 0.5 else 0.0) + (1.0 if al[1] > 0.5 else 0.0)
	var a23 := (1.0 if al[2] > 0.5 else 0.0) + (1.0 if al[3] > 0.5 else 0.0)
	_check("G-G1: smooth pair (0,1) merges (alive=1)", a01 == 1.0, "alive01=%d" % int(a01))
	_check("G-G2: checkerboard pair (2,3) free-streams (alive=2)", a23 == 2.0, "alive23=%d" % int(a23))
	var m0 := 0.0; for i in range(N): m0 += _input_mass[i]
	var m1 := 0.0; for i in range(N): m1 += pd[i * 4 + 3]
	_check("G-G3: total mass conserved (≤1e-3)", absf(m1 - m0) <= 1e-3 * maxf(m0, 1e-9),
		"Σm0=%.4f Σm1=%.4f" % [m0, m1])


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	print("[VerifyMergeGate] checks=%d failures=%d elapsed=%d ms"
		% [_checks, _failures, Time.get_ticks_msec() - _t0])
	if _failures == 0:
		print("[VerifyMergeGate] RESULT: PASS")
	else:
		print("[VerifyMergeGate] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
