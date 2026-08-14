extends Node
## Stage 1b verify — GPU jump-flooding Voronoi + per-cell two-fluid wave
## solve vs the Stage 1a numpy prototype (research/meshless/stage1_jfa3d.py).
##
## Self-contained: creates its OWN local RenderingDevice (display-
## independent — the sim's global-RD windowed rule does not apply; this
## battery runs headless) and executes the full Stage 1 chain:
##   1. BCC site scatter → 11 JFA passes + identity re-home
##      (compute/cassi_jfa.glsl)
##   2. Volume pass + IC sampling (the stage1a 6-mode recipe) at the
##      site positions
##   3. 300 leapfrog steps of the two-point-flux wave system
##      (compute/cassi_voronoi_cells.glsl), r(t) read back every step
##   4. Full state dump to res://_diag/voronoi3d_gpu.json (sites,
##      labels, grid ICs, final state, r trajectory) — the numpy
##      verifier research/meshless/stage1_verify.py computes the exact
##      3D spectral reference from the SAME dumped ICs and prints the
##      physics gates (breather, r(t), L2, spectrum).
##
## Local checks here are structural only (RD, JFA validity, no NaN,
## r bounded); the physics gates live in stage1_verify.py.
##
## Run: godot --path <repo> --headless res://scenes/verify_voronoi3d.tscn

const N := 64
const L := 6.283185307179586
const DT := 0.005
const N_STEPS := 300
const N_SITES := 4394
const R0 := 1.5
const AMP := 0.02
const PHI := 1.618033988749895
const TWO_PI := 6.283185307179586
const OM2 := 20.0
const C2 := 0.01
const INT_MAX := 2147483647

## Per-axis box aspect (1,1,1) = the cube battery (the Stage 1b original);
## a stretched box (e.g. (φ,1,φ²)) exercises the ANISOTROPIC mesh: per-axis
## grid spacings hx/hy/hz = L·aspect_i/N, the stretched JFA metric, and the
## per-axis AREPO lap face weights. The JFA mislabel + breather gates are
## recomputed by research/meshless/stage1b_aniso.py in the SAME stretched
## metric (the cube dump keeps the original stage1_verify.py path).
@export var aspect := Vector3(1, 1, 1)

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
var _cell_pc := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
	0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
var _md_zero: RID
var _grad: RID
var _lsm: RID
var _sites_cpu := PackedFloat32Array()
var _checks := 0
var _failures := 0
var _t0_ms := 0


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
	var r := _run_steps(psi0, labels)
	_check_trajectory(r, psi0)

	_dump_json(labels, ic, psi0, r)
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
	_vol = _rd.storage_buffer_create(N_SITES * 4)
	_md_zero = _rd.storage_buffer_create(4)
	_rd.buffer_update(_md_zero, 0, 4, PackedByteArray([0, 0, 0, 0]))
	_grad = _rd.storage_buffer_create(N_SITES * 16)
	_lsm = _rd.storage_buffer_create(N_SITES * 3 * 16)
	_jfa_us = _rd.uniform_set_create([
		_u_storage(0, _labels_a), _u_storage(1, _labels_b), _u_storage(2, _sites),
	], _jfa_shader, 0)
	_cell_us = _rd.uniform_set_create([
		_u_storage(0, _labels_a), _u_storage(1, _sites),
		_u_storage(2, _psi_y), _u_storage(3, _psi_i),
		_u_storage(4, _pi_y), _u_storage(5, _pi_i),
		_u_storage(6, _lap_y), _u_storage(7, _lap_i),
		_u_storage(8, _vol), _u_storage(9, _md_zero),
		_u_storage(10, _md_zero), _u_storage(11, _md_zero),
		_u_storage(12, _md_zero), _u_storage(13, _md_zero),
		_u_storage(14, _md_zero), _u_storage(15, _md_zero),
		_u_storage(16, _grad), _u_storage(17, _grad),
		_u_storage(18, _lsm), _u_storage(19, _lsm),
	], _cell_shader, 0)



func _u_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# ── sites: jittered BCC lattice (stage1a's bcc_seeds recipe) ────────────
func _make_sites() -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	var n1 := 13
	var sx: float = L * aspect.x / float(n1)
	var sy: float = L * aspect.y / float(n1)
	var sz: float = L * aspect.z / float(n1)
	var Lx: float = L * aspect.x
	var Ly: float = L * aspect.y
	var Lz: float = L * aspect.z
	var out := PackedFloat32Array()
	for i in range(n1):
		for j in range(n1):
			for k in range(n1):
				out.append_array(PackedFloat32Array([
					float(i) * sx + rng.randf_range(-0.2, 0.2) * sx,
					float(j) * sy + rng.randf_range(-0.2, 0.2) * sy,
					float(k) * sz + rng.randf_range(-0.2, 0.2) * sz,
					0.0]))
				out.append_array(PackedFloat32Array([
					(float(i) + 0.5) * sx + rng.randf_range(-0.2, 0.2) * sx,
					(float(j) + 0.5) * sy + rng.randf_range(-0.2, 0.2) * sy,
					(float(k) + 0.5) * sz + rng.randf_range(-0.2, 0.2) * sz,
					0.0]))
	for m in range(out.size() / 4):
		out[m * 4] = fposmod(out[m * 4], Lx)
		out[m * 4 + 1] = fposmod(out[m * 4 + 1], Ly)
		out[m * 4 + 2] = fposmod(out[m * 4 + 2], Lz)
	return out


# ── JFA: scatter + 11 passes + identity re-home ─────────────────────────
func _run_jfa() -> PackedInt32Array:
	var labels := PackedInt32Array()
	labels.resize(N * N * N)
	labels.fill(INT_MAX)
	var hx: float = L * aspect.x / float(N)
	var hy: float = L * aspect.y / float(N)
	var hz: float = L * aspect.z / float(N)
	for s in range(N_SITES):
		var gi := int(floor(_sites_cpu[s * 4] / hx)) % N
		var gj := int(floor(_sites_cpu[s * 4 + 1] / hy)) % N
		var gk := int(floor(_sites_cpu[s * 4 + 2] / hz)) % N
		var idx := gi * N * N + gj * N + gk
		if labels[idx] > s:
			labels[idx] = s  # min index per cell — the GPU atomicMin analog
	_rd.buffer_update(_labels_a, 0, labels.size() * 4, labels.to_byte_array())

	# doubling + halving + two jump-1 refinement passes (odd → result in B);
	# the refinement resolves the stretched-box ambiguous boundary cells to
	# the exact Voronoi (0.0000 mislabel), a no-op at the cube.
	var jumps: Array[int] = [1, 2, 4, 8, 16, 32, 16, 8, 4, 2, 1, 1, 1]
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
	_jfa_pc[4] = L * aspect.x / float(N)
	_jfa_pc[5] = L * aspect.y / float(N)
	_jfa_pc[6] = L * aspect.z / float(N)
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
	var hx: float = L * aspect.x / float(N)
	var hy: float = L * aspect.y / float(N)
	var hz: float = L * aspect.z / float(N)
	for s in range(N_SITES):
		var gx: float = fposmod(_sites_cpu[s * 4], L * aspect.x) / hx
		var gy: float = fposmod(_sites_cpu[s * 4 + 1], L * aspect.y) / hy
		var gz: float = fposmod(_sites_cpu[s * 4 + 2], L * aspect.z) / hz
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


# ── cell physics: volume pass + 300 leapfrog steps ──────────────────────
func _run_volume_pass() -> void:
	var zero := PackedFloat32Array()
	zero.resize(N_SITES)
	_rd.buffer_update(_vol, 0, zero.size() * 4, zero.to_byte_array())
	_cell_pc[0] = 2.0
	_fill_cell_pc()
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _cell_us, 0)
	_rd.compute_list_set_push_constant(cl, _cell_pc.to_byte_array(), _cell_pc.size() * 4)
	_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


# fills [1..9, 16]: (N, n_sites, dt, hx, hy, hz, C2, OM2, PHI, ..., lloyd_p)
func _fill_cell_pc() -> void:
	_cell_pc[1] = float(N)
	_cell_pc[2] = float(N_SITES)
	_cell_pc[3] = DT
	_cell_pc[4] = L * aspect.x / float(N)
	_cell_pc[5] = L * aspect.y / float(N)
	_cell_pc[6] = L * aspect.z / float(N)
	_cell_pc[7] = C2
	_cell_pc[8] = OM2
	_cell_pc[9] = PHI
	_cell_pc[16] = 4.0


func _run_steps(psi0: Array, labels: PackedInt32Array) -> PackedFloat32Array:
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

	# CPU-side cell volumes for the r sums (bincount x hx·hy·hz — the
	# same per-cell physical volumes the GPU volume pass accumulates)
	var vol := PackedFloat32Array()
	vol.resize(N_SITES)
	var vcell: float = (L * aspect.x / float(N)) * (L * aspect.y / float(N)) * (L * aspect.z / float(N))
	for idx in range(N * N * N):
		var lab := labels[idx]
		if lab >= 0 and lab < N_SITES:
			vol[lab] += vcell

	var r := PackedFloat32Array()
	r.resize(N_STEPS + 1)
	r[0] = _ratio(psy0, psi0_i, vol)

	_fill_cell_pc()
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
		if (st + 1) % 100 == 0:
			print("[VerifyVoronoi3D] step %d r = %.5f" % [st + 1, r[st + 1]])
	return r


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
	var fy: PackedFloat32Array = psi0[0]
	var fi: PackedFloat32Array = psi0[1]
	var nan0 := false
	for m in range(N_SITES):
		if is_nan(fy[m]) or is_inf(fy[m]) or is_nan(fi[m]) or is_inf(fi[m]):
			nan0 = true
	_check("IC: no NaN/Inf in sampled site state", not nan0)


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
		"aspect": [aspect.x, aspect.y, aspect.z],
		"Lx": L * aspect.x, "Ly": L * aspect.y, "Lz": L * aspect.z,
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
	if aspect == Vector3(1, 1, 1):
		var f := FileAccess.open("res://_diag/voronoi3d_gpu.json", FileAccess.WRITE)
		if f == null:
			_check("JSON dump written to res://_diag/voronoi3d_gpu.json", false,
				"FileAccess failed")
			return
		f.store_string(JSON.stringify(d))
		f.close()
		_check("JSON dump written to res://_diag/voronoi3d_gpu.json", true)
	else:
		var fa := FileAccess.open("res://_diag/voronoi3d_aniso_gpu.json", FileAccess.WRITE)
		if fa == null:
			_check("JSON dump written to res://_diag/voronoi3d_aniso_gpu.json", false,
				"FileAccess failed")
			return
		fa.store_string(JSON.stringify(d))
		fa.close()
		_check("JSON dump written to res://_diag/voronoi3d_aniso_gpu.json", true)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0_ms
	print("[VerifyVoronoi3D] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyVoronoi3D] RESULT: PASS — state dumped for stage1_verify.py")
	else:
		print("[VerifyVoronoi3D] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
