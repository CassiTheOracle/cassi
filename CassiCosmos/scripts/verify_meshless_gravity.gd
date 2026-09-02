extends Node3D
## Integration verify — the meshless TREE gravity arm (fmm_design.md Q6 /
## wave 3). meshless_mode + meshless_gravity ON, gravity_mode = 5,
## freeze_field ON (so the field the tree gathers does not advance), a
## PLANTED site field (EY/EI) + a PLANTED grid mass density, then the tree
## is built and walked over the sim's REAL meshless source buffers.
##
## The tree runs on a LOCAL RenderingDevice (the sim's global RD cannot
## submit/sync and, in this Godot 4.7 build on the RX 7900 XTX, does not
## execute a standalone/in-sim tree list from the _process loop — the
## shaders themselves are PROVEN on the local RD: 11963 nodes, correct
## walk). This verify: (1) reads the sim's source state back from the
## global RD, (2) rebuilds the tree EXACTLY as cassi_tree_build.glsl
## mode 7/1/5/6/8 + cassi_tree_gravity.glsl on a local RD (self-contained
## split, chord-weighted gather, per-particle walk), (3) dumps the tree's
## per-particle gradient + the gather INPUTS to
## res://_diag/meshless_gravity_gpu.json for research/meshless/
## stage5b_verify.py:
##   G31 — no NaN/Inf in the gradient; all targets in-box
##   G30 — GPU tree gradient vs the stage5_fmm prototype tree built on the
##         SAME gathered sources/targets (recipe re-implemented in numpy)
##         .. median relative <= 1e-2
##
## The same run also freezes the rejected optimization receipts:
##   G61/G62 — particle-vs-site target fidelity and equal-run walk cost
##   G63 — retained-topology source refresh vs the exact 123-dispatch build
## These research gates are evaluated by stage5b_verify.py and
## stage5c_refit_verify.py; their negative verdicts do not change the
## established G30/G31 battery-arm exit contract.
##
## Run: godot --path <repo> res://scenes/verify_meshless_gravity.tscn
##      (windowed — the sim uses the global RD for particle state)

const PHI := 1.618033988749895
const LEAF_CAP := 1
const MAX_LEVELS := 14
const NODE_MAX_MULT := 8
const THETA := 0.5
const EPS2 := 1e-6
const FIELD_FLOOR := 1e-6
const PERF_NP := 2097152
const PERF_WARMUPS := 3
const PERF_REPS := 11
const REFIT_BATCH := 32

var _sim: Node
var _phase := 0
var _idle := 0
var _nl_sites := 0
var _n3 := 0
var _planted_ym := PackedByteArray()
var _planted_im := PackedByteArray()
var _planted_rm := PackedByteArray()
var _done := false
var _diagnostic_mode := false
# local-RD tree build (the probe pattern — the tree runs on a LOCAL RD)
var _lrd: RenderingDevice
var _bld_sh: RID; var _bld_pipe: RID
var _grv_sh: RID; var _grv_pipe: RID
var _us_b: RID; var _us_g: RID
var _src: RID; var _srcw: RID; var _key: RID; var _order: RID
var _cf: RID; var _nw: RID; var _nq: RID; var _nr: RID; var _ctr: RID
var _node_qq: RID   # Arm 2: per-node mean coherence q_n (nodeQq binding 14)
var _sites: RID; var _psy: RID; var _psi: RID; var _vol: RID; var _rho: RID
var _tgrad: RID; var _tic: RID; var _tpos: RID
var _bpc := PackedFloat32Array()
var _gpc := PackedFloat32Array()
var _particle_pos := PackedFloat32Array()
var _particle_grad := PackedFloat32Array()
var _particle_icount := PackedInt32Array()
var _site_grad := PackedFloat32Array()
var _corrected_particle_grad := PackedFloat32Array()
var _corrected_particle_icount := PackedInt32Array()
var _initial_cf := PackedByteArray()
var _initial_nw := PackedByteArray()
var _initial_nr := PackedByteArray()
var _initial_order := PackedByteArray()
var _particle_walk_us: Array[int] = []
var _site_walk_us: Array[int] = []
var _build_us := 0
var _refit_result := {}
var _hier_result := {}


func _ready() -> void:
	_sim = $CassiSim
	_diagnostic_mode = OS.get_cmdline_user_args().has("--gravity-interpolation-diagnostic")
	# PIN the tree-gravity battery to the CUBE meshless config (the tree
	# sources are the sim's Voronoi sites; stage5b_verify.py recomputes
	# the prototype on the same cube-planted sources). meshless_mode +
	# meshless_gravity are already true via the scene.
	_sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	_sim.dual_grid = false
	_sim.reinit()  # rebuild the meshless sites at the cube extents
	_sim.playing = false


func _process(_delta: float) -> void:
	if _done:
		return
	if _sim == null or not _sim._shaders_ready:
		return
	match _phase:
		0:
			if not _sim._ml_ready or _sim._ml_tree_nsrc <= 0:
				return
			_nl_sites = _sim._ml_tree_nsrc
			_n3 = _sim.grid_N * _sim.grid_N * _sim.grid_N
			_sim.freeze_field = true
			_plant_field()
			print("[VerifyMeshlessGravity] planted — building tree on a local RD")
			_idle = 1
			_phase = 1
		1:
			if _idle > 0:
				_idle -= 1
				return
			_build_local_tree()
			_dump()
			_done = true
			get_tree().quit(0)


func _stor(bind: int, r: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = bind
	u.add_id(r)
	return u


# ── plant a smooth site field + grid mass density on the sim's global RD ─
func _plant_field() -> void:
	var S := _nl_sites
	var v0 := 0.03
	var sites: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_sites, 0, S * 16).to_float32_array()
	var ey := PackedFloat32Array(); ey.resize(S)
	var ei := PackedFloat32Array(); ei.resize(S)
	var pey := PackedFloat32Array(); pey.resize(S)
	var pei := PackedFloat32Array(); pei.resize(S)
	var ext: Vector3 = _sim._extents()
	var w: float = 0.35 * maxf(ext.x, maxf(ext.y, ext.z))
	for s in range(S):
		var x: float = sites[s * 4]
		var y: float = sites[s * 4 + 1]
		var z: float = sites[s * 4 + 2]
		var r2: float = (x * x + y * y + z * z) / (w * w)
		var gauss := exp(-r2)
		var ei_v: float = v0 * (0.5 + 0.5 * gauss)
		var ey_v: float = PHI * ei_v + 0.001 * gauss
		pey[s] = ey_v; pei[s] = ei_v
		ey[s] = ey_v; ei[s] = ei_v
	_planted_ym = ey.to_byte_array()
	_planted_im = ei.to_byte_array()
	_rd_upd(_sim._ml_psi_y, pey)
	_rd_upd(_sim._ml_psi_i, pei)
	var Np_grid: int = _sim.grid_N
	var rho := PackedFloat32Array(); rho.resize(_n3)
	var ext2: Vector3 = _sim._extents()
	var hx: float = 2.0 * ext2.x / float(Np_grid)
	var hy: float = 2.0 * ext2.y / float(Np_grid)
	var hz: float = 2.0 * ext2.z / float(Np_grid)
	var wpt: float = 0.4 * maxf(ext2.x, maxf(ext2.y, maxf(ext2.z, ext2.z)))
	for k in range(Np_grid):
		for j in range(Np_grid):
			for i in range(Np_grid):
				var xc: float = (float(i) - 0.5 * float(Np_grid)) * hx
				var yc: float = (float(j) - 0.5 * float(Np_grid)) * hy
				var zc: float = (float(k) - 0.5 * float(Np_grid)) * hz
				var rr2: float = (xc * xc + yc * yc + zc * zc) / (wpt * wpt)
				rho[i * Np_grid * Np_grid + j * Np_grid + k] = 0.8 * exp(-rr2)
	_planted_rm = rho.to_byte_array()
	_rd_upd(_sim._mass_density_buf, rho)


func _rd_upd(buf: RID, a: PackedFloat32Array) -> void:
	_sim._rd.buffer_update(buf, 0, a.size() * 4, a.to_byte_array())


# ── build + walk the tree on a LOCAL RD from the sim's real state ──────
func _build_local_tree() -> void:
	_lrd = RenderingServer.create_local_rendering_device()
	var Np: int = _sim.N_particles
	var ext: Vector3 = _sim._extents()
	var half: float = maxf(ext.x, maxf(ext.y, maxf(ext.z, ext.z))) * 1.000001
	var sites: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_sites, 0, _nl_sites * 16).to_float32_array()
	var psy: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_psi_y, 0, _nl_sites * 4).to_float32_array()
	var psi: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_psi_i, 0, _nl_sites * 4).to_float32_array()
	var vol: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_vol, 0, _nl_sites * 4).to_float32_array()
	var rho: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._mass_density_buf, 0, _n3 * 4).to_float32_array()
	_particle_pos = _sim._rd.buffer_get_data(_sim._pos_buf, 0, Np * 16).to_float32_array()
	var tnm: int = NODE_MAX_MULT * _nl_sites + 64
	var max_targets := maxi(PERF_NP, maxi(Np, _nl_sites))
	_src = _lrd.storage_buffer_create(2 * _nl_sites * 16)
	_srcw = _lrd.storage_buffer_create(_nl_sites * 4)
	_key = _lrd.storage_buffer_create(_nl_sites * 4)
	_order = _lrd.storage_buffer_create(_nl_sites * 4)
	_cf = _lrd.storage_buffer_create(tnm * 16)
	_nw = _lrd.storage_buffer_create(tnm * 16)
	_nq = _lrd.storage_buffer_create(2 * tnm * 16)
	_nr = _lrd.storage_buffer_create(tnm * 16)
	_ctr = _lrd.storage_buffer_create(8 * 4)
	_node_qq = _lrd.storage_buffer_create(tnm * 4)
	_sites = _lrd.storage_buffer_create(_nl_sites * 16)
	_psy = _lrd.storage_buffer_create(_nl_sites * 4)
	_psi = _lrd.storage_buffer_create(_nl_sites * 4)
	_vol = _lrd.storage_buffer_create(_nl_sites * 4)
	_rho = _lrd.storage_buffer_create(_n3 * 4)
	_tgrad = _lrd.storage_buffer_create(max_targets * 16)
	_tic = _lrd.storage_buffer_create(max_targets * 4)
	_tpos = _lrd.storage_buffer_create(max_targets * 16)
	_lrd.buffer_update(_sites, 0, sites.size() * 4, sites.to_byte_array())
	_lrd.buffer_update(_psy, 0, psy.size() * 4, psy.to_byte_array())
	_lrd.buffer_update(_psi, 0, psi.size() * 4, psi.to_byte_array())
	_lrd.buffer_update(_vol, 0, vol.size() * 4, vol.to_byte_array())
	_lrd.buffer_update(_rho, 0, rho.size() * 4, rho.to_byte_array())
	_lrd.buffer_update(_ctr, 0, 32, PackedInt32Array([1, 0, 1, 0, 0, 0, 0, 0]).to_byte_array())
	_lrd.buffer_update(_cf, 0, 16, PackedFloat32Array([ext.x, ext.y, ext.z, half]).to_byte_array())
	_lrd.buffer_update(_nr, 0, 16, PackedInt32Array([0, _nl_sites, -1, 0]).to_byte_array())
	var bsf := load("res://compute/cassi_tree_build.glsl") as RDShaderFile
	var gsf := load("res://compute/cassi_tree_gravity.glsl") as RDShaderFile
	_bld_sh = _lrd.shader_create_from_spirv(bsf.get_spirv())
	_bld_pipe = _lrd.compute_pipeline_create(_bld_sh)
	_grv_sh = _lrd.shader_create_from_spirv(gsf.get_spirv())
	_grv_pipe = _lrd.compute_pipeline_create(_grv_sh)
	_us_b = _lrd.uniform_set_create([
		_stor(0, _src), _stor(1, _srcw), _stor(2, _key), _stor(3, _order),
		_stor(4, _cf), _stor(5, _nw), _stor(6, _nq), _stor(7, _nr), _stor(8, _ctr),
		_stor(9, _sites), _stor(10, _psy), _stor(11, _psi), _stor(12, _vol), _stor(13, _rho),
		_stor(14, _node_qq),
	], _bld_sh, 0)
	_us_g = _lrd.uniform_set_create([
		_stor(0, _src), _stor(3, _order), _stor(4, _cf), _stor(5, _nw),
		_stor(6, _nq), _stor(7, _nr), _stor(8, _ctr), _stor(9, _tgrad),
		_stor(10, _tic), _stor(11, _tpos),
		_stor(14, _node_qq),
	], _grv_sh, 0)
	_bpc.resize(19)
	_bpc[0] = float(_nl_sites)
	_bpc[1] = 0.0; _bpc[2] = 0.0; _bpc[3] = 0.0
	_bpc[4] = half
	_bpc[5] = EPS2; _bpc[6] = PHI; _bpc[7] = PHI * PHI * PHI * PHI * PHI * PHI
	_bpc[8] = float(LEAF_CAP); _bpc[9] = float(MAX_LEVELS)
	_bpc[14] = float(_sim.grid_N)
	_bpc[15] = ext.x; _bpc[16] = ext.y; _bpc[17] = ext.z
	_bpc[18] = FIELD_FLOOR
	_gpc.resize(8)
	_gpc[1] = THETA; _gpc[2] = EPS2; _gpc[3] = 1.0
	_gpc[4] = float(tnm)
	_gpc[5] = 0.0; _gpc[6] = 1.0; _gpc[7] = 0.0
	_build_us = _prepare_full()
	var nc := _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var active_count: int = nc[0] if nc.size() else 0
	if _diagnostic_mode:
		_initial_cf = _lrd.buffer_get_data(_cf, 0, active_count * 16)
		_initial_nw = _lrd.buffer_get_data(_nw, 0, active_count * 16)
		_initial_nr = _lrd.buffer_get_data(_nr, 0, active_count * 16)
		_initial_order = _lrd.buffer_get_data(_order, 0, _nl_sites * 4)
	_gpc[4] = float(active_count)
	_walk_targets(_particle_pos, Np)
	_particle_grad = _lrd.buffer_get_data(_tgrad, 0, Np * 16).to_float32_array()
	_particle_icount = _lrd.buffer_get_data(_tic, 0, Np * 4).to_int32_array()
	if _diagnostic_mode:
		_gpc[3] = 2.0
		_walk_targets(_particle_pos, Np)
		_corrected_particle_grad = _lrd.buffer_get_data(_tgrad, 0, Np * 16).to_float32_array()
		_corrected_particle_icount = _lrd.buffer_get_data(_tic, 0, Np * 4).to_int32_array()
		_gpc[3] = 1.0
	_walk_targets(sites, _nl_sites)
	_site_grad = _lrd.buffer_get_data(_tgrad, 0, _nl_sites * 16).to_float32_array()
	if _diagnostic_mode:
		return
	var perf_pos := PackedFloat32Array()
	perf_pos.resize(PERF_NP * 4)
	for i in range(PERF_NP):
		var src_i := (i % Np) * 4
		var dst_i := i * 4
		perf_pos[dst_i] = _particle_pos[src_i]
		perf_pos[dst_i + 1] = _particle_pos[src_i + 1]
		perf_pos[dst_i + 2] = _particle_pos[src_i + 2]
		perf_pos[dst_i + 3] = _particle_pos[src_i + 3]
	for rep in range(PERF_WARMUPS + PERF_REPS):
		var p_first := (rep % 2) == 0
		var p_us := 0
		var s_us := 0
		if p_first:
			p_us = _walk_targets(perf_pos, PERF_NP)
			s_us = _walk_targets(sites, _nl_sites)
		else:
			s_us = _walk_targets(sites, _nl_sites)
			p_us = _walk_targets(perf_pos, PERF_NP)
		if rep >= PERF_WARMUPS:
			_particle_walk_us.append(p_us)
			_site_walk_us.append(s_us)
	_run_refit_probe(psy, psi, rho, Np)


func _record_full(cl) -> void:
	var pg := int(ceil(float(_nl_sites) / 64.0))
	var tnm := NODE_MAX_MULT * _nl_sites + 64
	var pall := int(ceil(float(tnm) / 64.0))
	_lrd.compute_list_bind_compute_pipeline(cl, _bld_pipe)
	_lrd.compute_list_bind_uniform_set(cl, _us_b, 0)
	_bpc[10] = 9.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, 1, 1, 1)
	_lrd.compute_list_add_barrier(cl)
	_bpc[10] = 10.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, 1, 1, 1)
	_lrd.compute_list_add_barrier(cl)
	_bpc[10] = 7.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, pg, 1, 1)
	_lrd.compute_list_add_barrier(cl)
	var k := 2
	while k <= _nl_sites:
		var j := k >> 1
		while j >= 1:
			_bpc[10] = 1.0
			_bpc[11] = float(k)
			_bpc[12] = float(j)
			_bpc[13] = 1.0
			_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
			_lrd.compute_list_dispatch(cl, pg, 1, 1)
			_lrd.compute_list_add_barrier(cl)
			j = j >> 1
		k = k << 1
	for _d in range(MAX_LEVELS):
		_bpc[10] = 5.0
		_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
		_lrd.compute_list_dispatch(cl, pall, 1, 1)
		_lrd.compute_list_add_barrier(cl)
		_bpc[10] = 8.0
		_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
		_lrd.compute_list_dispatch(cl, 1, 1, 1)
		_lrd.compute_list_add_barrier(cl)
	_bpc[10] = 6.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, pall, 1, 1)
	_lrd.compute_list_add_barrier(cl)


func _record_hier_refit(cl) -> void:
	var pg := int(ceil(float(_nl_sites) / 64.0))
	var tnm := NODE_MAX_MULT * _nl_sites + 64
	var pall := int(ceil(float(tnm) / 64.0))
	_lrd.compute_list_bind_compute_pipeline(cl, _bld_pipe)
	_lrd.compute_list_bind_uniform_set(cl, _us_b, 0)
	_bpc[10] = 11.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, pg, 1, 1)
	_lrd.compute_list_add_barrier(cl)
	_bpc[10] = 12.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, pall, 1, 1)
	_lrd.compute_list_add_barrier(cl)
	for depth in range(MAX_LEVELS - 1, -1, -1):
		_bpc[10] = 13.0
		_bpc[11] = float(depth)
		_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
		_lrd.compute_list_dispatch(cl, pall, 1, 1)
		_lrd.compute_list_add_barrier(cl)


func _prepare_full() -> int:
	var cl := _lrd.compute_list_begin()
	_record_full(cl)
	_lrd.compute_list_end()
	var started := Time.get_ticks_usec()
	_lrd.submit()
	_lrd.sync()
	return Time.get_ticks_usec() - started


func _prepare_refit() -> int:
	var pg := int(ceil(float(_nl_sites) / 64.0))
	var tnm := NODE_MAX_MULT * _nl_sites + 64
	var pall := int(ceil(float(tnm) / 64.0))
	var cl := _lrd.compute_list_begin()
	_lrd.compute_list_bind_compute_pipeline(cl, _bld_pipe)
	_lrd.compute_list_bind_uniform_set(cl, _us_b, 0)
	_bpc[10] = 11.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, pg, 1, 1)
	_lrd.compute_list_add_barrier(cl)
	_bpc[10] = 6.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, pall, 1, 1)
	_lrd.compute_list_end()
	var started := Time.get_ticks_usec()
	_lrd.submit()
	_lrd.sync()
	return Time.get_ticks_usec() - started


func _prepare_hier_refit() -> int:
	var cl := _lrd.compute_list_begin()
	_record_hier_refit(cl)
	_lrd.compute_list_end()
	var started := Time.get_ticks_usec()
	_lrd.submit()
	_lrd.sync()
	return Time.get_ticks_usec() - started


func _prepare_batch(hierarchical: bool) -> int:
	var cl := _lrd.compute_list_begin()
	for _i in range(REFIT_BATCH):
		if hierarchical:
			_record_hier_refit(cl)
		else:
			_record_full(cl)
	_lrd.compute_list_end()
	var started := Time.get_ticks_usec()
	_lrd.submit()
	_lrd.sync()
	return Time.get_ticks_usec() - started


func _run_refit_probe(psy: PackedFloat32Array, psi: PackedFloat32Array,
		rho: PackedFloat32Array, target_count: int) -> void:
	var changed_psy := psy.duplicate()
	var changed_psi := psi.duplicate()
	var changed_rho := rho.duplicate()
	for i in range(changed_psy.size()):
		changed_psy[i] = psy[i] * 1.03125 + float(i % 17) * 1.0e-7
		changed_psi[i] = psi[i] * 0.96875 + float(i % 13) * 1.0e-7
	for i in range(changed_rho.size()):
		changed_rho[i] = rho[i] * (1.015625 + float(i % 5) * 0.001)
	_lrd.buffer_update(_psy, 0, changed_psy.size() * 4, changed_psy.to_byte_array())
	_lrd.buffer_update(_psi, 0, changed_psi.size() * 4, changed_psi.to_byte_array())
	_lrd.buffer_update(_rho, 0, changed_rho.size() * 4, changed_rho.to_byte_array())

	var first_refit_us := _prepare_refit()
	var refit_count_data := _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var refit_count := refit_count_data[0] if refit_count_data.size() else 0
	var refit_order := _lrd.buffer_get_data(_order, 0, _nl_sites * 4)
	var refit_ranges := _lrd.buffer_get_data(_nr, 0, refit_count * 16)
	_gpc[4] = float(refit_count)
	_walk_targets(_particle_pos, target_count)
	var refit_gradient := _lrd.buffer_get_data(_tgrad, 0, target_count * 16)

	var first_full_us := _prepare_full()
	var full_count_data := _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var full_count := full_count_data[0] if full_count_data.size() else 0
	var full_order := _lrd.buffer_get_data(_order, 0, _nl_sites * 4)
	var full_ranges := _lrd.buffer_get_data(_nr, 0, full_count * 16)
	_gpc[4] = float(full_count)
	_walk_targets(_particle_pos, target_count)
	var full_gradient := _lrd.buffer_get_data(_tgrad, 0, target_count * 16)
	var full_gradient_f32 := full_gradient.to_float32_array()
	var gradient_finite := true
	for value in full_gradient_f32:
		if not is_finite(value):
			gradient_finite = false
			break

	var full_samples: Array[int] = []
	var refit_samples: Array[int] = []
	for rep in range(PERF_WARMUPS + PERF_REPS):
		var full_us := 0
		var refit_us := 0
		if rep % 2 == 0:
			full_us = _prepare_full()
			refit_us = _prepare_refit()
		else:
			refit_us = _prepare_refit()
			full_us = _prepare_full()
		if rep >= PERF_WARMUPS:
			full_samples.append(full_us)
			refit_samples.append(refit_us)
	_refit_result = {
		"source_change": "mass_and_yang_yin",
		"full_dispatches": 123,
		"refit_dispatches": 2,
		"refit_node_count": refit_count,
		"full_node_count": full_count,
		"node_count_identical": refit_count == full_count,
		"source_order_identical": refit_order == full_order,
		"node_ranges_identical": refit_ranges == full_ranges,
		"particle_gradient_identical": refit_gradient == full_gradient,
		"particle_gradient_finite": gradient_finite,
		"first_full_prepare_us": first_full_us,
		"first_refit_prepare_us": first_refit_us,
		"full_prepare_us": full_samples,
		"refit_prepare_us": refit_samples,
		"warmups": PERF_WARMUPS,
		"repetitions": PERF_REPS,
	}
	print("[VerifyMeshlessGravity] G63 refit=", _refit_result)

	_prepare_full()
	var retained_count_data := _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var retained_count := retained_count_data[0] if retained_count_data.size() else 0
	var retained_order := _lrd.buffer_get_data(_order, 0, _nl_sites * 4)
	var retained_ranges := _lrd.buffer_get_data(_nr, 0, retained_count * 16)
	var retained_centers := _lrd.buffer_get_data(_cf, 0, retained_count * 16)

	var first_hier_us := _prepare_hier_refit()
	var hier_count_data := _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var hier_count := hier_count_data[0] if hier_count_data.size() else 0
	var hier_order := _lrd.buffer_get_data(_order, 0, _nl_sites * 4)
	var hier_ranges := _lrd.buffer_get_data(_nr, 0, hier_count * 16)
	var hier_centers := _lrd.buffer_get_data(_cf, 0, hier_count * 16)
	_gpc[4] = float(hier_count)
	_walk_targets(_particle_pos, target_count)
	var hier_gradient := _lrd.buffer_get_data(_tgrad, 0, target_count * 16)

	var first_fresh_full_us := _prepare_full()
	var fresh_count_data := _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var fresh_count := fresh_count_data[0] if fresh_count_data.size() else 0
	var fresh_order := _lrd.buffer_get_data(_order, 0, _nl_sites * 4)
	var fresh_ranges := _lrd.buffer_get_data(_nr, 0, fresh_count * 16)
	var fresh_centers := _lrd.buffer_get_data(_cf, 0, fresh_count * 16)
	_gpc[4] = float(fresh_count)
	_walk_targets(_particle_pos, target_count)
	var fresh_gradient := _lrd.buffer_get_data(_tgrad, 0, target_count * 16)

	var hier_samples: Array[int] = []
	var full_batch_samples: Array[int] = []
	for rep in range(PERF_WARMUPS + PERF_REPS):
		var hier_us := 0
		var full_batch_us := 0
		if rep % 2 == 0:
			full_batch_us = _prepare_batch(false)
			hier_us = _prepare_batch(true)
		else:
			hier_us = _prepare_batch(true)
			full_batch_us = _prepare_batch(false)
		if rep >= PERF_WARMUPS:
			full_batch_samples.append(full_batch_us)
			hier_samples.append(hier_us)
	_hier_result = {
		"source_change": "mass_and_yang_yin",
		"target_count": target_count,
		"full_dispatches": 123,
		"hier_dispatches": 16,
		"batch_size": REFIT_BATCH,
		"retained_node_count": retained_count,
		"hier_node_count": hier_count,
		"fresh_node_count": fresh_count,
		"retained_node_count_identical": retained_count == hier_count,
		"retained_order_identical": retained_order == hier_order,
		"retained_ranges_identical": retained_ranges == hier_ranges,
		"retained_centers_identical": retained_centers == hier_centers,
		"fresh_raw_slots_identical": (
			retained_count == fresh_count
			and retained_order == fresh_order
			and retained_ranges == fresh_ranges
			and retained_centers == fresh_centers
		),
		"hier_gradient_b64": Marshalls.raw_to_base64(hier_gradient),
		"fresh_gradient_b64": Marshalls.raw_to_base64(fresh_gradient),
		"first_hier_prepare_us": first_hier_us,
		"first_fresh_full_prepare_us": first_fresh_full_us,
		"full_batch_us": full_batch_samples,
		"hier_batch_us": hier_samples,
		"warmups": PERF_WARMUPS,
		"repetitions": PERF_REPS,
	}
	print("[VerifyMeshlessGravity] G70/G71 hierarchical refit: nodes=", hier_count,
		" dispatches=16/123 full_batch_us=", full_batch_samples,
		" refit_batch_us=", hier_samples)


func _walk_targets(targets: PackedFloat32Array, count: int) -> int:
	_lrd.buffer_update(_tpos, 0, count * 16, targets.to_byte_array())
	_gpc[0] = float(count)
	var cl := _lrd.compute_list_begin()
	_lrd.compute_list_bind_compute_pipeline(cl, _grv_pipe)
	_lrd.compute_list_bind_uniform_set(cl, _us_g, 0)
	_lrd.compute_list_set_push_constant(cl, _gpc.to_byte_array(), _gpc.size() * 4)
	_lrd.compute_list_dispatch(cl, int(ceil(float(count) / 64.0)), 1, 1)
	_lrd.compute_list_end()
	var started := Time.get_ticks_usec()
	_lrd.submit()
	_lrd.sync()
	return Time.get_ticks_usec() - started

# ── dump the tree output + gather inputs ───────────────────────────────
func _dump() -> void:
	var Np: int = _sim.N_particles
	var grad := _particle_grad
	var icount := _particle_icount
	var site_grad := _site_grad
	var sites: PackedFloat32Array = _lrd.buffer_get_data(_sites, 0, _nl_sites * 16).to_float32_array()
	var vol: PackedFloat32Array = _lrd.buffer_get_data(_vol, 0, _nl_sites * 4).to_float32_array()
	var pos := _particle_pos
	var nc: PackedInt32Array = _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var ext: Vector3 = _sim._extents()
	var gmax := 0.0
	for _vi in range(Np * 3):
		gmax = maxf(gmax, absf(grad[_vi]))
	print("[VerifyMeshlessGravity] node_count=", (nc[0] if nc.size() else 0), " grad max|a|=", gmax)
	var site_gmax := 0.0
	for _vi in range(_nl_sites * 3):
		site_gmax = maxf(site_gmax, absf(site_grad[_vi]))
	print("[VerifyMeshlessGravity] site grad max|a|=", site_gmax,
		" build_us=", _build_us,
		" particle_walk_us=", _particle_walk_us,
		" site_walk_us=", _site_walk_us)
	var d := {
		"N": _sim.grid_N, "Np": Np, "nsrc": _nl_sites,
		"node_count": (nc[0] if nc.size() else 0),
		"dt": _sim.dt, "xi": _sim.xi, "phi": PHI,
		"theta": THETA, "eps2": EPS2, "leaf_cap": LEAF_CAP,
		"max_levels": MAX_LEVELS, "field_floor": FIELD_FLOOR,
		"extent_x": ext.x, "extent_y": ext.y, "extent_z": ext.z,
		"grad_b64": Marshalls.raw_to_base64(grad.to_byte_array()),
		"pos_b64": Marshalls.raw_to_base64(pos.to_byte_array()),
		"sites_b64": Marshalls.raw_to_base64(sites.to_byte_array()),
		"vol_b64": Marshalls.raw_to_base64(vol.to_byte_array()),
		"icount_b64": Marshalls.raw_to_base64(icount.to_byte_array()),
		"ey_b64": Marshalls.raw_to_base64(_planted_ym),
		"ei_b64": Marshalls.raw_to_base64(_planted_im),
		"rho_b64": Marshalls.raw_to_base64(_planted_rm),
		"site_grad_b64": Marshalls.raw_to_base64(site_grad.to_byte_array()),
		"perf_particle_count": PERF_NP,
		"perf_site_count": _nl_sites,
		"perf_warmups": PERF_WARMUPS,
		"perf_reps": PERF_REPS,
		"build_us": _build_us,
		"particle_walk_us": _particle_walk_us,
		"site_walk_us": _site_walk_us,
	}
	if _diagnostic_mode:
		var diagnostic := d.duplicate(true)
		diagnostic["node_count"] = _initial_cf.size() / 16
		diagnostic["legacy_grad_b64"] = Marshalls.raw_to_base64(_particle_grad.to_byte_array())
		diagnostic["legacy_icount_b64"] = Marshalls.raw_to_base64(_particle_icount.to_byte_array())
		diagnostic["corrected_grad_b64"] = Marshalls.raw_to_base64(_corrected_particle_grad.to_byte_array())
		diagnostic["corrected_icount_b64"] = Marshalls.raw_to_base64(_corrected_particle_icount.to_byte_array())
		diagnostic["ncf_b64"] = Marshalls.raw_to_base64(_initial_cf)
		diagnostic["nw_b64"] = Marshalls.raw_to_base64(_initial_nw)
		diagnostic["nr_b64"] = Marshalls.raw_to_base64(_initial_nr)
		diagnostic["srcorder_b64"] = Marshalls.raw_to_base64(_initial_order)
		diagnostic["legacy_selector"] = 1
		diagnostic["corrected_selector"] = 2
		var df := FileAccess.open("res://_diag/gravity_interpolation_diagnostic_gpu.json", FileAccess.WRITE)
		if df == null:
			print("[VerifyMeshlessGravity] FAIL: interpolation diagnostic JSON dump failed")
			get_tree().quit(1)
			return
		df.store_string(JSON.stringify(diagnostic))
		df.close()
		print("[VerifyMeshlessGravity] RESULT: PASS — interpolation diagnostic dump")
		return
	var rf := FileAccess.open("res://_diag/tree_refit_gpu.json", FileAccess.WRITE)
	if rf == null:
		print("[VerifyMeshlessGravity] FAIL: refit JSON dump failed")
		get_tree().quit(1)
		return
	rf.store_string(JSON.stringify(_refit_result))
	rf.close()
	var hf := FileAccess.open("res://_diag/tree_hier_refit_gpu.json", FileAccess.WRITE)
	if hf == null:
		print("[VerifyMeshlessGravity] FAIL: hierarchical refit JSON dump failed")
		get_tree().quit(1)
		return
	hf.store_string(JSON.stringify(_hier_result))
	hf.close()
	var f := FileAccess.open("res://_diag/meshless_gravity_gpu.json", FileAccess.WRITE)
	if f == null:
		print("[VerifyMeshlessGravity] FAIL: JSON dump failed")
		get_tree().quit(1)
		return
	f.store_string(JSON.stringify(d))
	f.close()
	print("[VerifyMeshlessGravity] RESULT: PASS — dump for stage5b_verify.py")
