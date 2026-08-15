extends Node
## Cassi Particle Merge GPU verify (design: research/meshless/particle_merge_design.md;
## numpy reference + gates: research/meshless/stage6_merge.py).
##
## Self-contained: creates its OWN local RenderingDevice (display-independent)
## and runs the merge shader (compute/cassi_particle_merge.glsl) on a synthetic
## planted input:
##   - 8 particles: three disjoint close pairs in the HIGH-q region
##     (coherent -> must merge) + one close pair in the LOW-q region
##     (free-streaming -> must NOT merge), all pairwise-separated >> R_m so the
##     merges are deterministic single-pair closures.
##   - a piecewise-constant EY/EI field: q_coh ~ 0.947 (EY=PHI, EI=1) for x > 0
##     and q_coh ~ 0.03 (EY=EI=0.05) for x < 0; each pair sits deep interior, so
##     the trilinear q sample at its midpoint is the exact planted value.
## Runs reset -> (fold,count,prefix,fill,best,hop) cycles -> finalize, then dumps
## _diag/merge_gpu.json (input pos/vel/mass + EY/EI + final alive/pos/vel/mass +
## merge_count). The numpy verifier (stage6_merge.py) computes the physics gates:
##   G28  GPU merge == numpy reference on the identical planted input (same
##       survivors, same masses <= 1e-3 relative)
##   G29  GPU momentum conservation <= 1e-3
## Local checks here are structural (pipelines build, no NaN, merges happened,
## momentum sanity); the authoritative gates live in stage6_merge.py.
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_merge.tscn

const N := 8
const N_GRID := 64
const EXTENT := 37.5
const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const RM_FRAC := 0.5
const H0 := 2.0 * EXTENT / float(N_GRID)
const R_M := RM_FRAC * H0
const Q_TH: float = PHI_INV2
const XI := 17.94427190999916       # φ⁶ — Qi coupling (binding + virial G_eff)
const G_N := 1.0                    # calibrated Newton G (river_calibrate off → bh[1].w = 1.0)
const DT := 0.001                   # timestep — c_s = H0/DT ≈ 1170, so the planted subsonic pairs pass
const MAX_CYCLES := 16
const HIGH_EY: float = PHI
const HIGH_EI := 1.0
const LOW_EY := 0.05
const LOW_EI := 0.05
const HASH_NX := 128
const HASH_NY := 128
const HASH_NZ := 128
const CELL_W := (2.0 * EXTENT) / float(HASH_NX)   # >= R_m per-axis
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
var _ey_buf: RID
var _ei_buf: RID
var _best_buf: RID
var _sink_buf: RID
var _spin_buf: RID
var _fvel_buf: RID
var _mprev_buf: RID
var _cc_buf: RID
var _cs_buf: RID
var _ch_buf: RID
var _cl_buf: RID
var _mc_buf: RID

var _pc := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
	0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])

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

	# upload the planted input
	_rd.buffer_update(_pos_buf, 0, _input_pos.size() * 4, _input_pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, _input_vel.size() * 4, _input_vel.to_byte_array())
	_upload_field()
	_rd.buffer_update(_mass_buf, 0, _input_mass.size() * 4, _input_mass.to_byte_array())

	var merges := _run_merge()
	_dump_json(merges)
	_local_checks(merges)
	_finish()


# ── shader / buffers / uniform set ───────────────────────────────────────
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
	_best_buf = _rd.storage_buffer_create(N * 4)
	_sink_buf = _rd.storage_buffer_create(N * 4)
	_spin_buf = _rd.storage_buffer_create(N * 16)
	_fvel_buf = _rd.storage_buffer_create(CELLS * 16)
	_mprev_buf = _rd.storage_buffer_create(N * 4)
	_ey_buf = _rd.storage_buffer_create(CELLS * 4)
	_ei_buf = _rd.storage_buffer_create(CELLS * 4)
	_cc_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_cs_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_ch_buf = _rd.storage_buffer_create(HASH_TOTAL * 4)
	_cl_buf = _rd.storage_buffer_create(N * 4)
	_mc_buf = _rd.storage_buffer_create(64)   # uint mc[16] — per-cycle merge-count slots
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
	_pc[0] = float(N)
	_pc[1] = PHI
	_pc[2] = PHI_INV2
	_pc[3] = Q_TH
	_pc[4] = R_M
	_pc[5] = EXTENT
	_pc[6] = EXTENT
	_pc[7] = EXTENT
	_pc[8] = float(N_GRID)
	_pc[9] = float(HASH_NX)
	_pc[10] = float(HASH_NY)
	_pc[11] = float(HASH_NZ)
	_pc[12] = CELL_W
	_pc[13] = CELL_W
	_pc[14] = CELL_W
	_pc[15] = pass_mode
	_pc[16] = G_N                   # g_n (bh[1].w)
	_pc[17] = XI                    # xi (φ⁶)
	_pc[18] = H0                    # h0 = 2·R_m
	_pc[19] = DT                    # dt
	_pc[20] = 1.0                   # f_subsonic (hypothesis criterion on)
	_pc[21] = 1.0                   # f_virial (hypothesis criterion on)
	_pc[22] = 1.0                   # f_order (order-selective gate on)
	_pc[23] = 0.0                   # cyc_slot (batched hop slot; the raw-pass test uses slot 0)


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


# ── planted input + field ────────────────────────────────────────────────
## Three disjoint close pairs in the HIGH-q half (x>0) + one in the LOW-q
## half (x<0); every inter-pair separation >> R_m so the merges are the
## deterministic single-pair closures. Expected: pairs (0,1),(2,3),(4,5) merge
## (survivors {0,2,4}); pair (6,7) free-streams (survivors {6,7}).
func _build_input() -> void:
	_input_mass = PackedFloat32Array([7.0, 3.0, 12.0, 5.0, 2.0, 9.0, 4.0, 4.0])
	# vec4 layout (x,y,z,w) — the shader reads vec4 buffers (16 B/particle);
	# w is a placeholder (the merge writes real masses into pos.w at reset).
	_input_pos = PackedFloat32Array([
		# pair A (high)  — merges
		5.0, 0.0, 0.0, 0.0,
		5.35, 0.0, 0.0, 0.0,
		# pair B (high)  — merges
		5.0, 4.0, 1.0, 0.0,
		5.0, 4.3, 1.0, 0.0,
		# pair C (high)  — merges
		8.0, -4.0, 2.0, 0.0,
		8.3, -4.0, 2.0, 0.0,
		# pair D (low)   — free-streams
		-5.0, 6.0, 3.0, 0.0,
		-5.35, 6.0, 3.0, 0.0,
	])
	_input_vel = PackedFloat32Array([
		0.1, 0.2, -0.1, 0.0,   -0.2, 0.05, 0.3, 0.0,
		0.0, 0.1, 0.2, 0.0,     0.15, -0.1, 0.0, 0.0,
		-0.1, 0.0, 0.25, 0.0,   0.2, 0.3, -0.05, 0.0,
		0.05, 0.0, 0.0, 0.0,    -0.05, 0.0, 0.0, 0.0,
	])
	# masses (the reset pass reads pos[i].w — here the placeholder w is 0,
	# so we push the per-particle masses into pos[].w directly)
	for i in range(N):
		_input_pos[i * 4 + 3] = _input_mass[i]


## Piecewise-constant EY/EI: q_coh ~ 0.947 for cells with world x > 0,
## q_coh ~ 0.03 for x <= 0 (the nbody q_coh formula; the exact nbody
## trilinear map maps a world x to grid gc = (x/extent)*N/2 + N/2).
func _upload_field() -> void:
	var ey := PackedFloat32Array(); ey.resize(CELLS)
	var ei := PackedFloat32Array(); ei.resize(CELLS)
	for cx in range(N_GRID):
		for cy in range(N_GRID):
			for cz in range(N_GRID):
				var id := cx + N_GRID * (cy + N_GRID * cz)
				# cell-center world x (world_to_grid is the nbody map)
				var wx: float = ((float(cx) + 0.5) / float(N_GRID) * 2.0 - 1.0) * EXTENT
				if wx > 0.0:
					ey[id] = HIGH_EY; ei[id] = HIGH_EI
				else:
					ey[id] = LOW_EY; ei[id] = LOW_EI
	_rd.buffer_update(_ey_buf, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_ei_buf, 0, ei.size() * 4, ei.to_byte_array())


func _read_cc() -> PackedInt32Array:
	var d := _rd.buffer_get_data(_cc_buf, 0, HASH_TOTAL * 4)
	return d.to_int32_array()


# ── run the merge cycles ─────────────────────────────────────────────────
func _run_merge() -> int:
	_dispatch(0.0)   # reset: alive=1, mass=pos.w, mom/cen=0
	var total_merges := 0
	for cyc in range(MAX_CYCLES):
		_dispatch(1.0)   # fold accumulated gains into canonical pos/vel
		# zero the count buffer, then count
		zero_uints(_cc_buf, HASH_TOTAL)
		_dispatch(2.0)
		# host exclusive prefix-sum: cc -> cs, then cs -> ch (fill head)
		var cc := _read_cc()
		var cs := PackedInt32Array(); cs.resize(HASH_TOTAL)
		var run := 0
		for c in range(HASH_TOTAL):
			cs[c] = run
			run += cc[c]
		_rd.buffer_update(_cs_buf, 0, cs.size() * 4, cs.to_byte_array())
		_rd.buffer_update(_ch_buf, 0, cs.size() * 4, cs.to_byte_array())
		_dispatch(3.0)   # fill per-cell lists
		_dispatch(4.0)   # best[i], sink[i]
		# reset per-cycle merge counter, then hop
		zero_uints(_mc_buf, 1)
		_dispatch(5.0)
		var merges := read_uint(_mc_buf)
		total_merges += merges
		print("[VerifyMerge] cycle %d: %d merges" % [cyc + 1, merges])
		if merges == 0:
			break
	_dispatch(6.0)   # finalize: write survivor masses to pos.w / zero dead
	return total_merges


func zero_uints(buf: RID, count: int) -> void:
	var z := PackedByteArray()
	z.resize(count * 4)
	z.fill(0)
	_rd.buffer_update(buf, 0, z.size(), z)


func read_uint(buf: RID) -> int:
	var d := _rd.buffer_get_data(buf, 0, 4)
	return int(d.decode_u32(0))


# ── dump + local structural checks ───────────────────────────────────────
func _dump_json(merges: int) -> void:
	var pd := _rd.buffer_get_data(_pos_buf, 0, N * 16).to_float32_array()
	var vd := _rd.buffer_get_data(_vel_buf, 0, N * 16).to_float32_array()
	var al := _rd.buffer_get_data(_alive_buf, 0, N * 4).to_float32_array()
	var ma := _rd.buffer_get_data(_mass_buf, 0, N * 4).to_float32_array()
	var ey := _rd.buffer_get_data(_ey_buf, 0, CELLS * 4).to_float32_array()
	var ei := _rd.buffer_get_data(_ei_buf, 0, CELLS * 4).to_float32_array()
	var pos_fin := PackedFloat32Array(); pos_fin.resize(N * 3)
	var vel_fin := PackedFloat32Array(); vel_fin.resize(N * 3)
	var mass_fin := PackedFloat32Array(); mass_fin.resize(N)
	for i in range(N):
		pos_fin[i * 3] = pd[i * 4]; pos_fin[i * 3 + 1] = pd[i * 4 + 1]; pos_fin[i * 3 + 2] = pd[i * 4 + 2]
		vel_fin[i * 3] = vd[i * 4]; vel_fin[i * 3 + 1] = vd[i * 4 + 1]; vel_fin[i * 3 + 2] = vd[i * 4 + 2]
		mass_fin[i] = pd[i * 4 + 3]  # finalized mass in pos.w (0 for dead)
	var d := {
		"N": N, "N_grid": N_GRID, "extent": EXTENT, "phi": PHI, "phi_inv2": PHI_INV2,
		"Rm_frac": RM_FRAC, "h0": H0, "R_m": R_M, "Q_th": Q_TH, "merge_count": merges,
		"ey": ey, "ei": ei,
		"alive": al,
		"pos_final": pos_fin, "vel_final": vel_fin, "mass_final": mass_fin,
	}
	# numpy (stage6_merge.py) expects (n,3) xyz + flat mass; extract from the
	# vec4-layout input arrays.
	var pos_np := PackedFloat32Array(); pos_np.resize(N * 3)
	var vel_np := PackedFloat32Array(); vel_np.resize(N * 3)
	for i in range(N):
		pos_np[i * 3] = _input_pos[i * 4]; pos_np[i * 3 + 1] = _input_pos[i * 4 + 1]; pos_np[i * 3 + 2] = _input_pos[i * 4 + 2]
		vel_np[i * 3] = _input_vel[i * 4]; vel_np[i * 3 + 1] = _input_vel[i * 4 + 1]; vel_np[i * 3 + 2] = _input_vel[i * 4 + 2]
	d["pos"] = pos_np
	d["vel"] = vel_np
	d["mass"] = _input_mass
	var f := FileAccess.open("res://_diag/merge_gpu.json", FileAccess.WRITE)
	if f == null:
		_check("JSON dump written to res://_diag/merge_gpu.json", false, "FileAccess failed")
		return
	f.store_string(JSON.stringify(d))
	f.close()
	_check("JSON dump written to res://_diag/merge_gpu.json", true)


func _local_checks(merges: int) -> void:
	var pd := _rd.buffer_get_data(_pos_buf, 0, N * 16).to_float32_array()
	var vd := _rd.buffer_get_data(_vel_buf, 0, N * 16).to_float32_array()
	var al := _rd.buffer_get_data(_alive_buf, 0, N * 4).to_float32_array()
	var nan := false
	var alive_cnt := 0
	for i in range(N):
		for k in range(3):
			if not is_finite(pd[i * 4 + k]) or not is_finite(vd[i * 4 + k]):
				nan = true
		if al[i] > 0.5:
			alive_cnt += 1
	_check("merge: no NaN/Inf in final pos/vel", not nan)
	_check("merge: >= 1 merge happened", merges >= 1, "merges=%d" % merges)
	_check("merge: alive flag is boolean (0/1)", alive_cnt == N - merges,
		"alive=%d expected=%d" % [alive_cnt, N - merges])
	# expected survivor set: {0,2,4,6,7} (3 high pairs merge, low pair streams)
	var exp_surv := [0, 2, 4, 6, 7]
	var got_surv := PackedInt32Array()
	for i in range(N):
		if al[i] > 0.5:
			got_surv.append(i)
	_check("merge: planted survivor set {0,2,4,6,7}", \
		PackedInt32Array(exp_surv) == got_surv, "got=%s" % got_surv)
	# momentum sanity (authoritative G29 in stage6_merge.py)
	var px := 0.0; var py := 0.0; var pz := 0.0
	var px2 := 0.0; var py2 := 0.0; var pz2 := 0.0
	for i in range(N):
		var m0: float = _input_mass[i]
		var m1: float = pd[i * 4 + 3]   # finalized mass in pos.w (0 for dead)
		px += _input_vel[i * 4] * m0; py += _input_vel[i * 4 + 1] * m0; pz += _input_vel[i * 4 + 2] * m0
		px2 += vd[i * 4] * m1; py2 += vd[i * 4 + 1] * m1; pz2 += vd[i * 4 + 2] * m1
	var pre := Vector3(px, py, pz)
	var post := Vector3(px2, py2, pz2)
	var rel: float = post.distance_to(pre) / maxf(pre.length(), 1e-30)
	_check("merge: momentum conservation sanity (<=1e-3)", rel <= 1e-3,
		"rel=%.8f pre=%s post=%s" % [rel, pre, post])


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0
	print("[VerifyMerge] checks=%d failures=%d elapsed=%d ms — stage6_merge.py computes G28/G29"
		% [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyMerge] RESULT: PASS — state dumped for stage6_merge.py")
	else:
		print("[VerifyMerge] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
