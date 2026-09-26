extends Node
## Cassi Particle Merge — GRAVITATIONAL BINDING verify (§3b doctrine gate,
## coherence_merge_rnd.md §3d falsifiable test #2):
##   "a bound pair merges but an equal-distance unbound pair (high v_rel)
##    does NOT — with conserved momentum."
##
## HIGH-q field everywhere (q_coh ≈ 0.947, q_ord ≈ 1 constant field), so the
## ONLY discriminator is the binding test ½μ|v_rel|²·d < G_eff·m₁m₂:
##   - pair A (bound):   masses 10/10, d = 0.4 < R_m, v_rel = 0
##                       → binds, must merge.
##   - pair B (unbound): identical geometry/masses, v_rel = (50,0,0)
##                       → ½μv²d = 2500 ≥ G_eff·m₁m₂ ≈ 1800, unbound,
##                       must NOT merge (and the fast v_rel is subsonic vs
##                       c_s = h0/dt ≈ 1170, so it is NOT blocked by the
##                       subsonic criterion — isolates binding).
## All pairs far apart (>> R_m) → deterministic single-pair closures.
##
## Gates:
##   G-B1  bound pair merges (alive loss == 1), unbound pair free-streams
##         (alive loss == 0)
##   G-B2  total mass conserved (≤ 1e-3 rel)
##   G-B3  momentum conserved (≤ 1e-3 rel)
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_merge_binding.tscn

const SMALL_N := 4
const BUFFER_N := 65
const N_GRID := 64
const EXTENT := 37.5
const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const RM_FRAC := 0.5
const H0 := 2.0 * EXTENT / float(N_GRID)
const R_M := RM_FRAC * H0
const Q_TH: float = PHI_INV2
const XI := 17.94427190999916       # φ⁶
const G_N := 1.0
const DT := 0.001                   # c_s = H0/DT ≈ 1170 (subsonic passes)
const MAX_CYCLES := 16
const HIGH_EY: float = PHI
const HIGH_EI := 1.0                # q_coh ≈ 0.947
const LOW_EY := 0.05
const LOW_EI := 0.05
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
var _site_dummy_buf: RID   # boxless site-read set (bindings 18-24) — unindexed dummy (boxless off in these tests)
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
var _test_extents := Vector3(EXTENT, EXTENT, EXTENT)
var _test_hash_nx := HASH_NX
var _test_hash_ny := HASH_NY
var _test_hash_nz := HASH_NZ
var _test_cell_w := Vector3(CELL_W, CELL_W, CELL_W)
var _test_n := SMALL_N
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
	var phase_probe_n := 2_500_000
	var last_phase := CassiMergeCommon.PAIR_PHASE_LANES * phase_probe_n - 1
	var last_phase_pc := CassiMergeCommon.pair_phase_pc(last_phase)
	_check("G-B0: sharded merge phase split stays float-exact and wraps",
		phase_probe_n < CassiMergeCommon.FLOAT_EXACT_INDEX_LIMIT
		and CassiMergeCommon.next_pair_phase(0, phase_probe_n) == 1
		and CassiMergeCommon.next_pair_phase(last_phase, phase_probe_n) == 0
		and is_equal_approx(last_phase_pc.x,
			4.0 + float(CassiMergeCommon.PAIR_PHASE_LANES - 1)
				/ CassiMergeCommon.PAIR_LANE_DENOMINATOR)
		and int(last_phase_pc.y) == phase_probe_n - 1)
	_build_input()
	_rd.buffer_update(_pos_buf, 0, _input_pos.size() * 4, _input_pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, _input_vel.size() * 4, _input_vel.to_byte_array())
	_upload_field()
	_rd.buffer_update(_mass_buf, 0, _input_mass.size() * 4, _input_mass.to_byte_array())
	var merges := _run_merge()
	_check_gates(merges)
	_run_periodic_seam_gate()
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
	_pos_buf = _rd.storage_buffer_create(BUFFER_N * 16)
	_vel_buf = _rd.storage_buffer_create(BUFFER_N * 16)
	_alive_buf = _rd.storage_buffer_create(BUFFER_N * 4)
	_mass_buf = _rd.storage_buffer_create(BUFFER_N * 4)
	_mom_buf = _rd.storage_buffer_create(BUFFER_N * 16)
	_cen_buf = _rd.storage_buffer_create(BUFFER_N * 16)
	_spin_buf = _rd.storage_buffer_create(BUFFER_N * 16)
	_fvel_buf = _rd.storage_buffer_create(CELLS * 16)
	_mprev_buf = _rd.storage_buffer_create(BUFFER_N * 4)
	_ey_buf = _rd.storage_buffer_create(CELLS * 4)
	_ei_buf = _rd.storage_buffer_create(CELLS * 4)
	_best_buf = _rd.storage_buffer_create(BUFFER_N * 4)
	_sink_buf = _rd.storage_buffer_create(BUFFER_N * 4)
	_cc_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_cs_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_ch_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_cl_buf = _rd.storage_buffer_create(BUFFER_N * 4)
	_mc_buf = _rd.storage_buffer_create(64)   # uint mc[16] per-cycle slots
	_site_dummy_buf = _rd.storage_buffer_create(8192 * 16)   # boxless site set — unindexed (boxless off); sized like _ml_sites
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
	_pc.resize(26)   # 26 floats: + boxless@24 + n_sites@25 (merge_boxless_prereg.md; both 0 in these tests)
	_pc[0] = float(_test_n)
	_pc[1] = PHI
	_pc[2] = PHI_INV2
	_pc[3] = Q_TH
	_pc[4] = R_M
	_pc[5] = _test_extents.x
	_pc[6] = _test_extents.y
	_pc[7] = _test_extents.z
	_pc[8] = float(N_GRID)
	_pc[9] = float(_test_hash_nx)
	_pc[10] = float(_test_hash_ny)
	_pc[11] = float(_test_hash_nz)
	_pc[12] = _test_cell_w.x
	_pc[13] = _test_cell_w.y
	_pc[14] = _test_cell_w.z
	_pc[15] = pass_mode
	_pc[16] = G_N
	_pc[17] = XI
	_pc[18] = H0
	_pc[19] = DT
	_pc[20] = 1.0   # f_subsonic
	_pc[21] = 1.0   # f_virial
	_pc[22] = 1.0   # f_order
	_pc[23] = 0.0   # cyc_slot (batched hop slot; the raw-pass test uses slot 0)
	_pc[24] = 0.0   # boxless (site-direct read) — off in these tests → grid path
	_pc[25] = 0.0   # n_sites (nearest-site guard) — unused when boxless off


func _dispatch(pass_mode: float, cyc_slot := 0.0) -> void:
	_fill_pc(pass_mode)
	_pc[23] = float(cyc_slot)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	_rd.compute_list_bind_uniform_set(cl, _us, 0)
	_rd.compute_list_set_push_constant(cl, _pc.to_byte_array(), _pc.size() * 4)
	_rd.compute_list_dispatch(cl, int(ceil(float(_test_n) / 256.0)), 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


## pair 0-1 (bound): masses 10/10 near x=5, v_rel = 0.
## pair 2-3 (unbound): same geometry/masses near x=10, v_rel = (50,0,0)
## (asymmetric ±velocities (-20,+30) → |v_rel|=50 unchanged, so the unbound
## physics is identical: ½μv²d = 2500 ≥ G_eff·m₁m₂ ≈ 1894 still fails to
## bind). Net p0.x = 10·(-20)+10·30 = 100 ≠ 0 → G-B3's relative tolerance
## is meaningful rather than an exact-zero check.
func _build_input() -> void:
	_input_mass = PackedFloat32Array([10.0, 10.0, 10.0, 10.0])
	_input_pos = PackedFloat32Array([
		5.0, 0.0, 0.0, 0.0,
		5.4, 0.0, 0.0, 0.0,
		10.0, 0.0, 0.0, 0.0,
		10.4, 0.0, 0.0, 0.0,
	])
	_input_vel = PackedFloat32Array([
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
		-20.0, 0.0, 0.0, 0.0,
		30.0, 0.0, 0.0, 0.0,
	])
	for i in range(_test_n):
		_input_pos[i * 4 + 3] = _input_mass[i]


## Uniform HIGH-q field (constant → q_ord = 1): isolates the binding test.
func _upload_field() -> void:
	var ey := PackedFloat32Array(); ey.resize(CELLS)
	var ei := PackedFloat32Array(); ei.resize(CELLS)
	for c in range(CELLS):
		ey[c] = HIGH_EY
		ei[c] = HIGH_EI
	_rd.buffer_update(_ey_buf, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_ei_buf, 0, ei.size() * 4, ei.to_byte_array())

## Regression for the periodic path used by anisotropic production boxes.
## The only eligible pair straddles ±extent.x. Its arithmetic midpoint is the
## deliberately LOW-q box center; only the min-image midpoint at the coherent
## seam may merge. The survivor must also remain at the seam rather than
## acquiring the raw-coordinate centroid at x=0.
func _run_periodic_seam_gate() -> void:
	_test_extents = Vector3(PHI, 1.0, PHI * PHI) * EXTENT
	var geom := CassiMergeCommon.hash_geometry(_test_extents, R_M)
	_test_hash_nx = int(geom["nx"])
	_test_hash_ny = int(geom["ny"])
	_test_hash_nz = int(geom["nz"])
	_test_cell_w = Vector3(
		float(geom["cell_wx"]), float(geom["cell_wy"]), float(geom["cell_wz"]))
	var geom_ok := int(geom["total"]) <= HASH_TOTAL \
		and _test_cell_w.x >= R_M and _test_cell_w.y >= R_M and _test_cell_w.z >= R_M
	_check("G-B4: anisotropic merge hash is bounded with cell widths >= R_m", geom_ok,
		"hash=%dx%dx%d cells=%d width=%s" % [
			_test_hash_nx, _test_hash_ny, _test_hash_nz, int(geom["total"]), _test_cell_w])

	_test_n = BUFFER_N
	var seam_x := _test_extents.x - 0.2
	var seam_source := BUFFER_N - 2   # index 63: a real nonzero production shard
	_input_mass = PackedFloat32Array()
	_input_pos = PackedFloat32Array()
	_input_vel = PackedFloat32Array()
	_input_mass.resize(_test_n)
	_input_pos.resize(_test_n * 4)
	_input_vel.resize(_test_n * 4)
	_input_mass[0] = 10.0
	_input_mass[seam_source] = 10.0
	_input_pos[0] = seam_x
	_input_pos[seam_source * 4] = -seam_x
	_input_vel[0] = 0.25
	_input_vel[seam_source * 4] = 0.25
	for i in range(_test_n):
		_input_pos[i * 4 + 3] = _input_mass[i]
	_rd.buffer_update(_pos_buf, 0, _input_pos.size() * 4, _input_pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, _input_vel.size() * 4, _input_vel.to_byte_array())
	_rd.buffer_update(_mass_buf, 0, _input_mass.size() * 4, _input_mass.to_byte_array())
	zero_uints(_spin_buf, BUFFER_N * 4)
	_upload_periodic_seam_field()

	var merges := _run_merge(true)
	var al := _rd.buffer_get_data(_alive_buf, 0, BUFFER_N * 4).to_float32_array()
	var pd := _rd.buffer_get_data(_pos_buf, 0, BUFFER_N * 16).to_float32_array()
	var vd := _rd.buffer_get_data(_vel_buf, 0, BUFFER_N * 16).to_float32_array()
	var seam_alive := int(al[0] > 0.5) + int(al[seam_source] > 0.5)
	_check("G-B5: real N>64 shard 63/cell 5 phase merges seam pair",
		merges == 1 and seam_alive == 1,
		"merges=%d alive=%d" % [merges, seam_alive])
	var seam_error := absf(absf(pd[0]) - _test_extents.x)
	_check("G-B6: seam survivor keeps periodic centroid", seam_error <= 1e-3,
		"x=%.6f |extent|=%.6f error=%.8f" % [
			pd[0], _test_extents.x, seam_error])
	var mass_after := 0.0
	var momentum_after := Vector3.ZERO
	for i in range(BUFFER_N):
		var m := pd[i * 4 + 3]
		mass_after += m
		momentum_after += Vector3(vd[i * 4], vd[i * 4 + 1], vd[i * 4 + 2]) * m
	_check("G-B7: seam merge preserves mass", absf(mass_after - 20.0) <= 1e-3,
		"mass=%.6f" % mass_after)
	_check("G-B8: seam merge preserves momentum",
		momentum_after.distance_to(Vector3(5.0, 0.0, 0.0)) <= 5e-3,
		"momentum=%s" % momentum_after)


func _upload_periodic_seam_field() -> void:
	var ey := PackedFloat32Array()
	var ei := PackedFloat32Array()
	ey.resize(CELLS)
	ei.resize(CELLS)
	for z in range(N_GRID):
		for y in range(N_GRID):
			for x in range(N_GRID):
				var idx := x + N_GRID * (y + N_GRID * z)
				var coherent_seam := x <= 1 or x >= N_GRID - 2
				ey[idx] = HIGH_EY if coherent_seam else LOW_EY
				ei[idx] = HIGH_EI if coherent_seam else LOW_EI
	_rd.buffer_update(_ey_buf, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_ei_buf, 0, ei.size() * 4, ei.to_byte_array())


func _run_merge(encoded_seam_lane := false) -> int:
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
		var seam_lane := (BUFFER_N - 2) * CassiMergeCommon.PAIR_NEIGHBOR_CELLS + 5
		var best_pc := CassiMergeCommon.pair_phase_pc(
			seam_lane) if encoded_seam_lane else Vector2(4.0, 0.0)
		_dispatch(best_pc.x, best_pc.y)
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
	var al := _rd.buffer_get_data(_alive_buf, 0, _test_n * 4).to_float32_array()
	var pd := _rd.buffer_get_data(_pos_buf, 0, _test_n * 16).to_float32_array()
	var vd := _rd.buffer_get_data(_vel_buf, 0, _test_n * 16).to_float32_array()
	# pair 0-1 must merge (1 alive loss); pair 2-3 must not (0 alive loss)
	var a01 := (1.0 if al[0] > 0.5 else 0.0) + (1.0 if al[1] > 0.5 else 0.0)
	var a23 := (1.0 if al[2] > 0.5 else 0.0) + (1.0 if al[3] > 0.5 else 0.0)
	_check("G-B1: bound pair (0,1) merges (alive=1)", a01 == 1.0, "alive01=%d" % int(a01))
	_check("G-B1: unbound pair (2,3) free-streams (alive=2)", a23 == 2.0, "alive23=%d" % int(a23))
	# G-B2: total mass conserved
	var m0 := 0.0; for i in range(_test_n): m0 += _input_mass[i]
	var m1 := 0.0; for i in range(_test_n): m1 += pd[i * 4 + 3]
	_check("G-B2: total mass conserved (≤1e-3)", absf(m1 - m0) <= 1e-3 * maxf(m0, 1e-9),
		"Σm0=%.4f Σm1=%.4f" % [m0, m1])
	# G-B3: momentum conserved
	var px0 := 0.0; var py0 := 0.0; var pz0 := 0.0
	var px1 := 0.0; var py1 := 0.0; var pz1 := 0.0
	for i in range(_test_n):
		var mm := pd[i * 4 + 3]
		px0 += _input_vel[i * 4] * _input_mass[i]
		py0 += _input_vel[i * 4 + 1] * _input_mass[i]
		pz0 += _input_vel[i * 4 + 2] * _input_mass[i]
		px1 += vd[i * 4] * mm; py1 += vd[i * 4 + 1] * mm; pz1 += vd[i * 4 + 2] * mm
	var pre := Vector3(px0, py0, pz0); var post := Vector3(px1, py1, pz1)
	var rel := post.distance_to(pre) / maxf(pre.length(), 1e-30)
	_check("G-B3: momentum conserved (≤1e-3)", rel <= 1e-3, "rel=%.8f" % rel)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0
	print("[VerifyMergeBinding] checks=%d failures=%d elapsed=%d ms"
		% [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyMergeBinding] RESULT: PASS")
	else:
		print("[VerifyMergeBinding] RESULT: FAIL")
	if _rd != null:
		for rid in [_us, _pipe, _shader,
				_pos_buf, _vel_buf, _alive_buf, _mass_buf, _mom_buf, _cen_buf,
				_spin_buf, _fvel_buf, _mprev_buf, _site_dummy_buf, _ey_buf,
				_ei_buf, _best_buf, _sink_buf, _cc_buf, _cs_buf, _ch_buf,
				_cl_buf, _mc_buf]:
			if rid.is_valid():
				_rd.free_rid(rid)
		_rd.free()
		_rd = null
	get_tree().quit(0 if _failures == 0 else 1)
