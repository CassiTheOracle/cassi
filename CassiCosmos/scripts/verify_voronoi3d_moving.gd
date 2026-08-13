extends Node
## Stage 2b verify — the MOVING 3D mesh on the GPU (steering + periodic
## ALE remap + JFA refresh), gated against the exact 3D spectral
## reference by research/meshless/stage2_verify.py.
##
## Architecture (the plan's division of labor): the heavy work stays on
## the GPU — the JFA Voronoi construction (compute/cassi_jfa.glsl) and
## the per-cell two-fluid physics (compute/cassi_voronoi_cells.glsl)
## are UNCHANGED from the Stage 1b static battery. The lightweight mesh
## management (4394 sites) is CPU-side, exactly as the numpy Stage 2a:
## every 25 steps — readback labels + cell state, Lloyd-style centroid
## relaxation + super-Lagrangian momentum ride, nearest-old-cell ALE
## remap, re-scatter, JFA refresh (12 passes), volume rebuild.
##
## Local checks are structural; the physics gates live in stage2_verify.py.
## Run: godot --path <repo> res://scenes/verify_voronoi3d_moving.tscn
##      (windowed — local RD has no headless device on this rig)

const N := 64
const L := 6.283185307179586
const DT := 0.005
const N_STEPS := 300
const N_SITES := 4394
const REBUILD := 25
const KAPPA := 0.5
const LAM := 8.0
const R0 := 1.5
const AMP := 0.02
const PHI := 1.618033988749895
const TWO_PI := 6.283185307179586
const OM2 := 20.0
const C2 := 0.01
const INT_MAX := 2147483647

var _rd: RenderingDevice
var _jfa_us: RID
var _cell_us: RID
var _jfa_shader: RID
var _cell_shader: RID
var _jfa_pipe: RID
var _cell_pipe: RID
var _labels_a: RID
var _labels_b: RID
var _sites: RID
var _psi_y: RID
var _psi_i: RID
var _pi_y: RID
var _pi_i: RID
var _lap_y: RID
var _lap_i: RID
var _vol: RID
var _jfa_pc := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
var _cell_pc := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
var _md_zero: RID
var _sites_cpu := PackedFloat32Array()
var _checks := 0
var _failures := 0
var _t0_ms := 0
var _n_remaps := 0
var _final_labels := PackedInt32Array()


func _ready() -> void:
	_t0_ms = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RenderingDevice acquired", false,
			"headless/dummy renderer? fall back to windowed run")
		_finish()
		return
	_check("local RenderingDevice acquired", true)
	if not _load_pipelines():
		_finish()
		return
	_make_buffers()

	_sites_cpu = _make_sites()
	_rd.buffer_update(_sites, 0, _sites_cpu.size() * 4, _sites_cpu.to_byte_array())

	var labels := _run_jfa()
	_check_jfa(labels)

	var ic := _make_ics()
	var psi0 := _sample_ics(ic)
	_run_volume_pass()
	var r := _run_steps_moving(psi0, labels)
	_check_trajectory(r, psi0)

	_dump_json(_final_labels, ic, psi0, r)
	_finish()


# ── shaders / buffers / uniform sets ────────────────────────────────────
func _load_pipelines() -> bool:
	var jfa_sf := load("res://compute/cassi_jfa.glsl") as RDShaderFile
	var cell_sf := load("res://compute/cassi_voronoi_cells.glsl") as RDShaderFile
	if jfa_sf == null or cell_sf == null:
		_check("shaders load", false)
		return false
	var jfa_sp := jfa_sf.get_spirv()
	var cell_sp := cell_sf.get_spirv()
	if jfa_sp == null or cell_sp == null:
		_check("shaders compile to SPIR-V", false)
		return false
	_check("shaders load + compile", true)
	_jfa_shader = _rd.shader_create_from_spirv(jfa_sp)
	_cell_shader = _rd.shader_create_from_spirv(cell_sp)
	_jfa_pipe = _rd.compute_pipeline_create(_jfa_shader)
	_cell_pipe = _rd.compute_pipeline_create(_cell_shader)
	var ok: bool = _jfa_pipe.is_valid() and _cell_pipe.is_valid()
	_check("compute pipelines build", ok)
	return ok


func _make_buffers() -> void:
	_labels_a = _rd.storage_buffer_create(N * N * N * 4)
	_labels_b = _rd.storage_buffer_create(N * N * N * 4)
	_sites = _rd.storage_buffer_create(N_SITES * 16)
	_psi_y = _rd.storage_buffer_create(N_SITES * 4)
	_psi_i = _rd.storage_buffer_create(N_SITES * 4)
	_pi_y = _rd.storage_buffer_create(N_SITES * 4)
	_pi_i = _rd.storage_buffer_create(N_SITES * 4)
	_lap_y = _rd.storage_buffer_create(N_SITES * 4)
	_lap_i = _rd.storage_buffer_create(N_SITES * 4)
	_md_zero = _rd.storage_buffer_create(4)
	_rd.buffer_update(_md_zero, 0, 4, PackedByteArray([0, 0, 0, 0]))
	_vol = _rd.storage_buffer_create(N_SITES * 4)
	_jfa_us = _rd.uniform_set_create([
		_u_storage(0, _labels_a), _u_storage(1, _labels_b), _u_storage(2, _sites),
	], _jfa_shader, 0)
	_cell_us = _rd.uniform_set_create([
		_u_storage(0, _labels_a), _u_storage(1, _sites),
		_u_storage(2, _psi_y), _u_storage(3, _psi_i),
		_u_storage(4, _pi_y), _u_storage(5, _pi_i),
		_u_storage(6, _lap_y), _u_storage(7, _lap_i), _u_storage(8, _vol),
		_u_storage(9, _md_zero),
	], _cell_shader, 0)


func _u_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# ── sites: jittered BCC lattice (the stage1a recipe) ────────────────────
func _make_sites() -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	var n1 := 13
	var spacing: float = L / float(n1)
	var out := PackedFloat32Array()
	for i in range(n1):
		for j in range(n1):
			for k in range(n1):
				out.append_array(PackedFloat32Array([
					float(i) * spacing + rng.randf_range(-0.2, 0.2) * spacing,
					float(j) * spacing + rng.randf_range(-0.2, 0.2) * spacing,
					float(k) * spacing + rng.randf_range(-0.2, 0.2) * spacing,
					0.0]))
				out.append_array(PackedFloat32Array([
					(float(i) + 0.5) * spacing + rng.randf_range(-0.2, 0.2) * spacing,
					(float(j) + 0.5) * spacing + rng.randf_range(-0.2, 0.2) * spacing,
					(float(k) + 0.5) * spacing + rng.randf_range(-0.2, 0.2) * spacing,
					0.0]))
	for m in range(out.size() / 4):
		out[m * 4] = fposmod(out[m * 4], L)
		out[m * 4 + 1] = fposmod(out[m * 4 + 1], L)
		out[m * 4 + 2] = fposmod(out[m * 4 + 2], L)
	return out


# ── JFA: scatter + 11 passes + identity re-home ─────────────────────────
func _run_jfa() -> PackedInt32Array:
	var labels := PackedInt32Array()
	labels.resize(N * N * N)
	labels.fill(INT_MAX)
	var h: float = L / float(N)
	for s in range(N_SITES):
		var gi := int(floor(_sites_cpu[s * 4] / h)) % N
		var gj := int(floor(_sites_cpu[s * 4 + 1] / h)) % N
		var gk := int(floor(_sites_cpu[s * 4 + 2] / h)) % N
		var idx := gi * N * N + gj * N + gk
		if labels[idx] > s:
			labels[idx] = s  # min index per cell — the GPU atomicMin analog
	_rd.buffer_update(_labels_a, 0, labels.size() * 4, labels.to_byte_array())

	var jumps: Array[int] = [1, 2, 4, 8, 16, 32, 16, 8, 4, 2, 1]
	var read_a := 1
	for jp in jumps:
		_jfa_pass(jp, read_a)
		read_a = 1 - read_a
	_jfa_pass(0, 0)  # identity copy B -> A (odd pass count leaves result in B)

	var back := _rd.buffer_get_data(_labels_a, 0, N * N * N * 4)
	return back.to_int32_array()


func _jfa_pass(jp: int, read_a: int) -> void:
	_jfa_pc[0] = float(N)
	_jfa_pc[1] = float(jp)
	_jfa_pc[2] = float(read_a)
	_jfa_pc[3] = float(N_SITES)
	_jfa_pc[4] = L / float(N)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _jfa_pipe)
	_rd.compute_list_bind_uniform_set(cl, _jfa_us, 0)
	_rd.compute_list_set_push_constant(cl, _jfa_pc.to_byte_array(), _jfa_pc.size() * 4)
	_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _check_jfa(labels: PackedInt32Array) -> void:
	var unlabeled := 0
	var distinct := {}
	for idx in range(N * N * N):
		var lab := labels[idx]
		if lab < 0 or lab >= N_SITES:
			unlabeled += 1
		else:
			distinct[lab] = true
	_check("JFA: 0 unlabeled cells", unlabeled == 0, "unlabeled=%d" % unlabeled)
	_check("JFA: every site owns cells", distinct.size() == N_SITES,
		"distinct=%d" % distinct.size())


# ── ICs: the stage1a make_ics3d recipe (6 smooth modes, r0 = 1.5) ───────
func _make_ics() -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	var ey := PackedFloat32Array()
	var ei := PackedFloat32Array()
	ey.resize(N * N * N)
	ei.resize(N * N * N)
	for m in range(6):
		var nx := rng.randi_range(1, 3)
		var ny := rng.randi_range(1, 3)
		var nz := rng.randi_range(1, 3)
		var km: float = sqrt(float(nx * nx + ny * ny + nz * nz))
		var ph := rng.randf() * TWO_PI
		var ph2 := rng.randf() * TWO_PI
		for i in range(N):
			for j in range(N):
				for k in range(N):
					var ang: float = TWO_PI * float(nx * i + ny * j + nz * k) / float(N)
					var idx := i * N * N + j * N + k
					ey[idx] += cos(ang + ph) / km
					ei[idx] += cos(ang + ph2) / km
	var mey := 0.0
	var mei := 0.0
	for idx in range(N * N * N):
		mey += ey[idx]
		mei += ei[idx]
	mey /= float(N * N * N)
	mei /= float(N * N * N)
	var maxy := 0.0
	var maxi := 0.0
	for idx in range(N * N * N):
		ey[idx] -= mey
		ei[idx] -= mei
		maxy = max(maxy, absf(ey[idx]))
		maxi = max(maxi, absf(ei[idx]))
	for idx in range(N * N * N):
		ey[idx] = R0 * (1.0 + AMP * ey[idx] / maxy)
		ei[idx] = 1.0 * (1.0 + AMP * ei[idx] / maxi)
	return {"ey": ey, "ei": ei}


func _sample_ics(ic: Dictionary) -> Array:
	var ey: PackedFloat32Array = ic["ey"]
	var ei: PackedFloat32Array = ic["ei"]
	var psy := PackedFloat32Array()
	var psi := PackedFloat32Array()
	psy.resize(N_SITES)
	psi.resize(N_SITES)
	var h: float = L / float(N)
	for s in range(N_SITES):
		var gx: float = fposmod(_sites_cpu[s * 4], L) / h
		var gy: float = fposmod(_sites_cpu[s * 4 + 1], L) / h
		var gz: float = fposmod(_sites_cpu[s * 4 + 2], L) / h
		var i0 := int(floor(gx)) % N
		var j0 := int(floor(gy)) % N
		var k0 := int(floor(gz)) % N
		var i1 := (i0 + 1) % N
		var j1 := (j0 + 1) % N
		var k1 := (k0 + 1) % N
		var fx: float = gx - floor(gx)
		var fy: float = gy - floor(gy)
		var fz: float = gz - floor(gz)
		psy[s] = _tri(ey, i0, j0, k0, i1, j1, k1, fx, fy, fz)
		psi[s] = _tri(ei, i0, j0, k0, i1, j1, k1, fx, fy, fz)
	return [psy, psi]


func _tri(a: PackedFloat32Array, i0: int, j0: int, k0: int, i1: int, j1: int, k1: int,
		fx: float, fy: float, fz: float) -> float:
	var c00 := a[i0 * N * N + j0 * N + k0] * (1.0 - fx) + a[i1 * N * N + j0 * N + k0] * fx
	var c01 := a[i0 * N * N + j0 * N + k1] * (1.0 - fx) + a[i1 * N * N + j0 * N + k1] * fx
	var c10 := a[i0 * N * N + j1 * N + k0] * (1.0 - fx) + a[i1 * N * N + j1 * N + k0] * fx
	var c11 := a[i0 * N * N + j1 * N + k1] * (1.0 - fx) + a[i1 * N * N + j1 * N + k1] * fx
	var c0 := c00 * (1.0 - fy) + c10 * fy
	var c1 := c01 * (1.0 - fy) + c11 * fy
	return c0 * (1.0 - fz) + c1 * fz


# ── cell physics: volume pass + leapfrog steps ──────────────────────────
func _run_volume_pass() -> void:
	var zero := PackedFloat32Array()
	zero.resize(N_SITES)
	_rd.buffer_update(_vol, 0, zero.size() * 4, zero.to_byte_array())
	_cell_pc[0] = 2.0
	_cell_pc[1] = float(N)
	_cell_pc[2] = float(N_SITES)
	_cell_pc[3] = DT
	_cell_pc[4] = L / float(N)
	_cell_pc[5] = C2
	_cell_pc[6] = OM2
	_cell_pc[7] = PHI
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _cell_us, 0)
	_rd.compute_list_set_push_constant(cl, _cell_pc.to_byte_array(), _cell_pc.size() * 4)
	_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _run_steps_moving(psi0: Array, labels0: PackedInt32Array) -> PackedFloat32Array:
	var psy0: PackedFloat32Array = psi0[0]
	var psi0_i: PackedFloat32Array = psi0[1]
	_rd.buffer_update(_psi_y, 0, psy0.size() * 4, psy0.to_byte_array())
	_rd.buffer_update(_psi_i, 0, psi0_i.size() * 4, psi0_i.to_byte_array())
	var zero := PackedFloat32Array()
	zero.resize(N_SITES)
	_rd.buffer_update(_pi_y, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_pi_i, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_lap_y, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_lap_i, 0, zero.size() * 4, zero.to_byte_array())

	var labels := labels0
	var vol := _count_volumes(labels)

	var r := PackedFloat32Array()
	r.resize(N_STEPS + 1)
	r[0] = _ratio(psy0, psi0_i, vol)

	_cell_pc[2] = float(N_SITES)
	_cell_pc[3] = DT
	_cell_pc[4] = L / float(N)
	_cell_pc[5] = C2
	_cell_pc[6] = OM2
	_cell_pc[7] = PHI
	for st in range(N_STEPS):
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
		_rd.compute_list_bind_uniform_set(cl, _cell_us, 0)
		# lap accumulate (one thread per grid cell)
		_cell_pc[0] = 0.0
		_cell_pc[1] = float(N)
		_rd.compute_list_set_push_constant(cl, _cell_pc.to_byte_array(), _cell_pc.size() * 4)
		_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
		_rd.compute_list_add_barrier(cl)
		# leapfrog (one thread per site)
		_cell_pc[0] = 1.0
		_cell_pc[1] = float(N_SITES)
		_rd.compute_list_set_push_constant(cl, _cell_pc.to_byte_array(), _cell_pc.size() * 4)
		_rd.compute_list_dispatch(cl, int(ceil(float(N_SITES) / 64.0)), 1, 1)
		_rd.compute_list_end()
		_rd.submit()
		_rd.sync()
		var yb := _rd.buffer_get_data(_psi_y, 0, N_SITES * 4)
		var ib := _rd.buffer_get_data(_psi_i, 0, N_SITES * 4)
		r[st + 1] = _ratio(yb.to_float32_array(), ib.to_float32_array(), vol)
		if (st + 1) % REBUILD == 0:
			labels = _mesh_rebuild()
			_final_labels = labels
			vol = _count_volumes(labels)
		if (st + 1) % 100 == 0:
			print("[VerifyVoronoi3DMoving] step %d r = %.5f (remaps=%d)"
				% [st + 1, r[st + 1], _n_remaps])
	return r


func _count_volumes(labels: PackedInt32Array) -> PackedFloat32Array:
	var vol := PackedFloat32Array()
	vol.resize(N_SITES)
	var h3: float = pow(L / float(N), 3.0)
	for idx in range(N * N * N):
		var lab := labels[idx]
		if lab >= 0 and lab < N_SITES:
			vol[lab] += h3
	return vol


# ── the mesh rebuild: steer + ALE remap + JFA refresh (Stage 2a recipe) ─
func _mesh_rebuild() -> PackedInt32Array:
	_n_remaps += 1
	var h: float = L / float(N)
	var labels := _rd.buffer_get_data(_labels_a, 0, N * N * N * 4).to_int32_array()
	var y := _rd.buffer_get_data(_psi_y, 0, N_SITES * 4).to_float32_array()
	var i_f := _rd.buffer_get_data(_psi_i, 0, N_SITES * 4).to_float32_array()
	var py := _rd.buffer_get_data(_pi_y, 0, N_SITES * 4).to_float32_array()
	var pi := _rd.buffer_get_data(_pi_i, 0, N_SITES * 4).to_float32_array()

	# centroids (wrapped) from the old labels
	var cnt := PackedInt32Array()
	cnt.resize(N_SITES)
	var cx := PackedFloat64Array()
	var cy := PackedFloat64Array()
	var cz := PackedFloat64Array()
	cx.resize(N_SITES)
	cy.resize(N_SITES)
	cz.resize(N_SITES)
	for i in range(N):
		for j in range(N):
			for k in range(N):
				var lab := labels[i * N * N + j * N + k]
				if lab >= 0 and lab < N_SITES:
					cnt[lab] += 1
					cx[lab] += (float(i) + 0.5) * h
					cy[lab] += (float(j) + 0.5) * h
					cz[lab] += (float(k) + 0.5) * h

	# steering: (1-kappa)(site + lam*(piY+piI)/rho * T) + kappa*centroid
	var T_steer: float = DT * float(REBUILD)
	var new_sites := PackedFloat32Array()
	new_sites.resize(N_SITES * 4)
	for s in range(N_SITES):
		var rho: float = y[s] + i_f[s] + 1e-12
		var v: float = LAM * (py[s] + pi[s]) / rho
		var cc: float = max(float(cnt[s]), 1.0)
		var sx: float = (1.0 - KAPPA) * (_sites_cpu[s * 4] + v * T_steer) \
			+ KAPPA * (float(cx[s]) / cc)
		var sy: float = (1.0 - KAPPA) * (_sites_cpu[s * 4 + 1] + v * T_steer) \
			+ KAPPA * (float(cy[s]) / cc)
		var sz: float = (1.0 - KAPPA) * (_sites_cpu[s * 4 + 2] + v * T_steer) \
			+ KAPPA * (float(cz[s]) / cc)
		new_sites[s * 4] = fposmod(sx, L)
		new_sites[s * 4 + 1] = fposmod(sy, L)
		new_sites[s * 4 + 2] = fposmod(sz, L)

	# ALE remap: new cell state = old state at the new seed's old cell
	var ny := PackedFloat32Array()
	var ni := PackedFloat32Array()
	var npy := PackedFloat32Array()
	var npi := PackedFloat32Array()
	ny.resize(N_SITES)
	ni.resize(N_SITES)
	npy.resize(N_SITES)
	npi.resize(N_SITES)
	for s in range(N_SITES):
		var gi := int(floor(new_sites[s * 4] / h)) % N
		var gj := int(floor(new_sites[s * 4 + 1] / h)) % N
		var gk := int(floor(new_sites[s * 4 + 2] / h)) % N
		var lab := labels[gi * N * N + gj * N + gk]
		if lab < 0 or lab >= N_SITES:
			lab = s
		ny[s] = y[lab]
		ni[s] = i_f[lab]
		npy[s] = py[lab]
		npi[s] = pi[lab]

	_sites_cpu = new_sites
	_rd.buffer_update(_sites, 0, _sites_cpu.size() * 4, _sites_cpu.to_byte_array())
	_rd.buffer_update(_psi_y, 0, ny.size() * 4, ny.to_byte_array())
	_rd.buffer_update(_psi_i, 0, ni.size() * 4, ni.to_byte_array())
	_rd.buffer_update(_pi_y, 0, npy.size() * 4, npy.to_byte_array())
	_rd.buffer_update(_pi_i, 0, npi.size() * 4, npi.to_byte_array())
	var zero := PackedFloat32Array()
	zero.resize(N_SITES)
	_rd.buffer_update(_lap_y, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_lap_i, 0, zero.size() * 4, zero.to_byte_array())

	return _run_jfa()


func _ratio(y: PackedFloat32Array, i: PackedFloat32Array, vol: PackedFloat32Array) -> float:
	var sy := 0.0
	var si := 0.0
	for m in range(N_SITES):
		sy += y[m] * vol[m]
		si += i[m] * vol[m]
	return sy / max(si, 1e-30)


func _check_trajectory(r: PackedFloat32Array, psi0: Array) -> void:
	var nan := false
	var max_dev := 0.0
	for m in range(N_STEPS + 1):
		if is_nan(r[m]) or is_inf(r[m]):
			nan = true
		max_dev = max(max_dev, absf(r[m] - R0))
	_check("trajectory: no NaN/Inf in r(t)", not nan)
	_check("trajectory: r stays within 0.5 of r0", max_dev < 0.5,
		"max|r-r0|=%.4f" % max_dev)
	_check("moving mesh: remaps performed", _n_remaps == N_STEPS / REBUILD,
		"remaps=%d" % _n_remaps)


func _dump_json(labels: PackedInt32Array, ic: Dictionary, psi0: Array, r: PackedFloat32Array) -> void:
	var yb := _rd.buffer_get_data(_psi_y, 0, N_SITES * 4)
	var ib := _rd.buffer_get_data(_psi_i, 0, N_SITES * 4)
	var nan := false
	for m in range(N_SITES):
		if is_nan(yb.to_float32_array()[m]) or is_inf(yb.to_float32_array()[m]):
			nan = true
	_check("final state: no NaN/Inf on GPU", not nan)
	var d := {
		"N": N, "L": L, "dt": DT, "n_steps": N_STEPS, "n_sites": N_SITES,
		"rebuild": REBUILD, "kappa": KAPPA, "lam": LAM,
		"sites_b64": Marshalls.raw_to_base64(_sites_cpu.to_byte_array()),
		"labels_b64": Marshalls.raw_to_base64(labels.to_byte_array()),
		"ey0_b64": Marshalls.raw_to_base64(ic["ey"].to_byte_array()),
		"ei0_b64": Marshalls.raw_to_base64(ic["ei"].to_byte_array()),
		"psi_y0_b64": Marshalls.raw_to_base64(psi0[0].to_byte_array()),
		"psi_i0_b64": Marshalls.raw_to_base64(psi0[1].to_byte_array()),
		"psi_y_b64": Marshalls.raw_to_base64(yb),
		"psi_i_b64": Marshalls.raw_to_base64(ib),
		"r": Array(r),
	}
	var f := FileAccess.open("res://_diag/voronoi3d_moving_gpu.json", FileAccess.WRITE)
	if f == null:
		_check("JSON dump written to res://_diag/voronoi3d_moving_gpu.json", false,
			"FileAccess failed")
		return
	f.store_string(JSON.stringify(d))
	f.close()
	_check("JSON dump written to res://_diag/voronoi3d_moving_gpu.json", true)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0_ms
	print("[VerifyVoronoi3DMoving] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyVoronoi3DMoving] RESULT: PASS — state dumped for stage2_verify.py")
	else:
		print("[VerifyVoronoi3DMoving] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
