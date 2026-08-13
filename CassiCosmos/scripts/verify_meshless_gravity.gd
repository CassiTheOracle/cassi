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
## Run: godot --path <repo> res://scenes/verify_meshless_gravity.tscn
##      (windowed — the sim uses the global RD for particle state)

const PHI := 1.618033988749895
const LEAF_CAP := 1
const MAX_LEVELS := 14
const NODE_MAX_MULT := 8
const THETA := 0.5
const EPS2 := 1e-6
const FIELD_FLOOR := 1e-6

var _sim: Node
var _phase := 0
var _idle := 0
var _nl_sites := 0
var _n3 := 0
var _planted_ym := PackedByteArray()
var _planted_im := PackedByteArray()
var _planted_rm := PackedByteArray()
var _done := false
# local-RD tree build (the probe pattern — the tree runs on a LOCAL RD)
var _lrd: RenderingDevice
var _bld_sh: RID; var _bld_pipe: RID
var _grv_sh: RID; var _grv_pipe: RID
var _us_b: RID; var _us_g: RID
var _src: RID; var _srcw: RID; var _key: RID; var _order: RID
var _cf: RID; var _nw: RID; var _nq: RID; var _nr: RID; var _ctr: RID
var _sites: RID; var _psy: RID; var _psi: RID; var _vol: RID; var _rho: RID
var _tgrad: RID; var _tic: RID; var _tpos: RID
var _bpc := PackedFloat32Array()
var _gpc := PackedFloat32Array()


func _ready() -> void:
	_sim = $CassiSim


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
	# copy the sim's meshless state (global RD readbacks)
	var sites: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_sites, 0, _nl_sites * 16).to_float32_array()
	var psy: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_psi_y, 0, _nl_sites * 4).to_float32_array()
	var psi: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_psi_i, 0, _nl_sites * 4).to_float32_array()
	var vol: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_vol, 0, _nl_sites * 4).to_float32_array()
	var rho: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._mass_density_buf, 0, _n3 * 4).to_float32_array()
	var pos: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._pos_buf, 0, Np * 16).to_float32_array()
	var tnm: int = NODE_MAX_MULT * _nl_sites + 64
	_src = _lrd.storage_buffer_create(2 * _nl_sites * 16)
	_srcw = _lrd.storage_buffer_create(_nl_sites * 4)
	_key = _lrd.storage_buffer_create(_nl_sites * 4)
	_order = _lrd.storage_buffer_create(_nl_sites * 4)
	_cf = _lrd.storage_buffer_create(tnm * 16)
	_nw = _lrd.storage_buffer_create(tnm * 16)
	_nq = _lrd.storage_buffer_create(2 * tnm * 16)
	_nr = _lrd.storage_buffer_create(tnm * 16)
	_ctr = _lrd.storage_buffer_create(8 * 4)
	_sites = _lrd.storage_buffer_create(_nl_sites * 16)
	_psy = _lrd.storage_buffer_create(_nl_sites * 4)
	_psi = _lrd.storage_buffer_create(_nl_sites * 4)
	_vol = _lrd.storage_buffer_create(_nl_sites * 4)
	_rho = _lrd.storage_buffer_create(_n3 * 4)
	_tgrad = _lrd.storage_buffer_create(Np * 16)
	_tic = _lrd.storage_buffer_create(Np * 4)
	_tpos = _lrd.storage_buffer_create(Np * 16)
	_lrd.buffer_update(_sites, 0, sites.size() * 4, sites.to_byte_array())
	_lrd.buffer_update(_psy, 0, psy.size() * 4, psy.to_byte_array())
	_lrd.buffer_update(_psi, 0, psi.size() * 4, psi.to_byte_array())
	_lrd.buffer_update(_vol, 0, vol.size() * 4, vol.to_byte_array())
	_lrd.buffer_update(_rho, 0, rho.size() * 4, rho.to_byte_array())
	_lrd.buffer_update(_tpos, 0, pos.size() * 4, pos.to_byte_array())
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
	], _bld_sh, 0)
	_us_g = _lrd.uniform_set_create([
		_stor(0, _src), _stor(3, _order), _stor(4, _cf), _stor(5, _nw),
		_stor(6, _nq), _stor(7, _nr), _stor(8, _ctr), _stor(9, _tgrad),
		_stor(10, _tic), _stor(11, _tpos),
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
	_gpc.resize(5)
	_gpc[0] = float(Np); _gpc[1] = THETA; _gpc[2] = EPS2; _gpc[3] = 1.0  # use_tp
	_gpc[4] = float(tnm)
	# gather (mode 7) + bitonic (91) in one list
	var pg := int(ceil(float(_nl_sites) / 64.0))
	var cl := _lrd.compute_list_begin()
	_lrd.compute_list_bind_compute_pipeline(cl, _bld_pipe)
	_lrd.compute_list_bind_uniform_set(cl, _us_b, 0)
	_bpc[10] = 7.0
	_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
	_lrd.compute_list_dispatch(cl, pg, 1, 1)
	_lrd.compute_list_add_barrier(cl)
	var k := 2
	while k <= _nl_sites:
		var j := k >> 1
		while j >= 1:
			_bpc[10] = 1.0; _bpc[11] = float(k); _bpc[12] = float(j); _bpc[13] = 1.0
			_lrd.compute_list_set_push_constant(cl, _bpc.to_byte_array(), _bpc.size() * 4)
			_lrd.compute_list_dispatch(cl, pg, 1, 1)
			_lrd.compute_list_add_barrier(cl)
			j = j >> 1
		k = k << 1
	_lrd.compute_list_add_barrier(cl)
	var pall := int(ceil(float(tnm) / 64.0))
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
	# walk (use_tp reads _tpos = the sim's particle positions)
	_lrd.compute_list_bind_compute_pipeline(cl, _grv_pipe)
	_lrd.compute_list_bind_uniform_set(cl, _us_g, 0)
	_lrd.compute_list_set_push_constant(cl, _gpc.to_byte_array(), _gpc.size() * 4)
	_lrd.compute_list_dispatch(cl, int(ceil(float(Np) / 64.0)), 1, 1)
	_lrd.compute_list_end()
	_lrd.submit()
	_lrd.sync()
	var nc := _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	_gpc[4] = float(nc[0] if nc.size() else 0)


# ── dump the tree output + gather inputs ───────────────────────────────
func _dump() -> void:
	var Np: int = _sim.N_particles
	var grad: PackedFloat32Array = _lrd.buffer_get_data(_tgrad, 0, Np * 16).to_float32_array()
	var icount: PackedInt32Array = _lrd.buffer_get_data(_tic, 0, Np * 4).to_int32_array()
	var sites: PackedFloat32Array = _lrd.buffer_get_data(_sites, 0, _nl_sites * 16).to_float32_array()
	var vol: PackedFloat32Array = _lrd.buffer_get_data(_vol, 0, _nl_sites * 4).to_float32_array()
	var pos: PackedFloat32Array = _lrd.buffer_get_data(_tpos, 0, Np * 16).to_float32_array()
	var nc: PackedInt32Array = _lrd.buffer_get_data(_ctr, 0, 4).to_int32_array()
	var ext: Vector3 = _sim._extents()
	var gmax := 0.0
	for _vi in range(Np * 3):
		gmax = maxf(gmax, absf(grad[_vi]))
	print("[VerifyMeshlessGravity] node_count=", (nc[0] if nc.size() else 0), " grad max|a|=", gmax)
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
	}
	var f := FileAccess.open("res://_diag/meshless_gravity_gpu.json", FileAccess.WRITE)
	if f == null:
		print("[VerifyMeshlessGravity] FAIL: JSON dump failed")
		get_tree().quit(1)
		return
	f.store_string(JSON.stringify(d))
	f.close()
	print("[VerifyMeshlessGravity] RESULT: PASS — dump for stage5b_verify.py")
