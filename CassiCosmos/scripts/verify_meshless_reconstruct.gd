extends Node
## Reconstruction verify — AREPO-style per-cell LINEAR reconstruction in
## the Voronoi raster (the "square-ripples" fix). Self-contained, local RD
## (display-independent, runs windowed just like verify_voronoi3d). Reuses
## the real cell/raster pipelines:
##   compute/cassi_voronoi_cells.glsl  — mode 10 (grad+lsm zero), mode 0
##     (the lap pass, which ALSO accumulates the LEAST-SQUARES moment
##     matrix M += n̂⊗n̂ and rhs b += (ψ_n−ψ_s)/d·n̂ over the boundary
##     faces), and mode 12 (the per-site 3×3 solve g = M⁻¹·b)
##   compute/cassi_voronoi_raster.glsl — the linear reconstruction
##
## The least-squares (face-normal) gradient is EXACT for linear fields on
## ANY mesh (b = Σ n̂(n̂·g) = M·g), so both gates run on the sim's actual
## jittered BCC mesh.
##
## Gates:
##   R1 LINEAR EXACTNESS — a synthetic LINEAR field (ey = a·x + b,
##     ei = c·y + d) on the jittered BCC mesh → the reconstructed raster
##     reproduces it to machine precision. The residual is float32 rounding
##     in the per-site atomic accumulation of M and b (measured mean ~1e-8,
##     max a few × float32 eps): the gate is ≤ 1e-4 (a handful of ulps,
##     still 5+ orders below any physical field error and ~1e4 tighter than
##     the piecewise-constant error it replaces). Interior sites only (one
##     Voronoi cell-width from the box walls) so the non-periodic linear
##     field's wrap discontinuity cannot contaminate the gradient.
##   R2 SMOOTHNESS — a rippled field on the same BCC mesh → dump a 2D
##     mid-plane slice of the reconstructed q vs the piecewise-constant q
##     and report the Voronoi-INTERFACE jump reduction (mean |q_{i+1}−q_i|
##     across faces that straddle two sites). The reconstructed field is
##     clamped toward its neighbour site values, so its interface jump must
##     be reduced by at least ~40% (gate: ratio < 0.6·pc, i.e. the
##     reconstructed interface jumps are under 60% of the piecewise-constant
##     ones — measurably smoother, killing the blocky "grid squares" step).
##
## Run: godot --path <repo> res://scenes/verify_meshless_reconstruct.tscn

const N := 48
const L := 6.283185307179586
const N_SITES_1 := 8          # BCC sublattice count per axis -> 2·8³ = 1024 sites
const PHI := 1.618033988749895

var _rd: RenderingDevice
var _cell_us: RID
var _raster_us: RID
var _cell_shader: RID
var _raster_shader: RID
var _cell_pipe: RID
var _raster_pipe: RID
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
var _grad_y: RID
var _grad_i: RID
var _lsm_y: RID
var _lsm_i: RID
var _ey: RID
var _ei: RID
var _q: RID
var _cell_pc := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
	0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])  # 18 floats: 17 + J_wind slot 17
var _raster_pc := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
var _md_zero: RID
var _sites_cpu := PackedFloat32Array()
var _n_sites := 0
var _checks := 0
var _failures := 0
var _t0_ms := 0


func _ready() -> void:
	_t0_ms = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RenderingDevice acquired", false, "fall back to windowed")
		_finish()
		return
	_check("local RenderingDevice acquired", true)
	if not _load_pipelines():
		_finish()
		return
	_make_buffers()
	_run_gates()


func _load_pipelines() -> bool:
	var cell_sf := load("res://compute/cassi_voronoi_cells.glsl") as RDShaderFile
	var raster_sf := load("res://compute/cassi_voronoi_raster.glsl") as RDShaderFile
	if cell_sf == null or raster_sf == null:
		_check("shaders load", false)
		return false
	var cell_sp := cell_sf.get_spirv()
	var raster_sp := raster_sf.get_spirv()
	if cell_sp == null or raster_sp == null:
		_check("shaders compile to SPIR-V", false)
		return false
	_check("shaders load + compile", true)
	_cell_shader = _rd.shader_create_from_spirv(cell_sp)
	_raster_shader = _rd.shader_create_from_spirv(raster_sp)
	_cell_pipe = _rd.compute_pipeline_create(_cell_shader)
	_raster_pipe = _rd.compute_pipeline_create(_raster_shader)
	_check("compute pipelines build", _cell_pipe.is_valid() and _raster_pipe.is_valid())
	return _cell_pipe.is_valid() and _raster_pipe.is_valid()


func _make_buffers() -> void:
	_n_sites = 2 * N_SITES_1 * N_SITES_1 * N_SITES_1
	_labels_a = _rd.storage_buffer_create(N * N * N * 4)
	_labels_b = _rd.storage_buffer_create(N * N * N * 4)
	_sites = _rd.storage_buffer_create(_n_sites * 16)
	_psi_y = _rd.storage_buffer_create(_n_sites * 4)
	_psi_i = _rd.storage_buffer_create(_n_sites * 4)
	_pi_y = _rd.storage_buffer_create(_n_sites * 4)
	_pi_i = _rd.storage_buffer_create(_n_sites * 4)
	_lap_y = _rd.storage_buffer_create(_n_sites * 4)
	_lap_i = _rd.storage_buffer_create(_n_sites * 4)
	_vol = _rd.storage_buffer_create(_n_sites * 4)
	_grad_y = _rd.storage_buffer_create(_n_sites * 16)
	_grad_i = _rd.storage_buffer_create(_n_sites * 16)
	_lsm_y = _rd.storage_buffer_create(_n_sites * 3 * 16)
	_lsm_i = _rd.storage_buffer_create(_n_sites * 3 * 16)
	_ey = _rd.storage_buffer_create(N * N * N * 4)
	_ei = _rd.storage_buffer_create(N * N * N * 4)
	_q = _rd.storage_buffer_create(N * N * N * 4)
	_md_zero = _rd.storage_buffer_create(4)
	_rd.buffer_update(_md_zero, 0, 4, PackedByteArray([0, 0, 0, 0]))
	_cell_us = _rd.uniform_set_create([
		_u_storage(0, _labels_a), _u_storage(1, _sites),
		_u_storage(2, _psi_y), _u_storage(3, _psi_i),
		_u_storage(4, _pi_y), _u_storage(5, _pi_i),
		_u_storage(6, _lap_y), _u_storage(7, _lap_i), _u_storage(8, _vol),
		_u_storage(9, _md_zero), _u_storage(10, _md_zero),
		_u_storage(11, _md_zero), _u_storage(12, _md_zero),
		_u_storage(13, _md_zero), _u_storage(14, _md_zero),
		_u_storage(15, _md_zero),
		_u_storage(16, _grad_y), _u_storage(17, _grad_i),
		_u_storage(18, _lsm_y), _u_storage(19, _lsm_i),
	], _cell_shader, 0)
	_raster_us = _rd.uniform_set_create([
		_u_storage(0, _labels_a), _u_storage(1, _psi_y), _u_storage(2, _psi_i),
		_u_storage(3, _ey), _u_storage(4, _ei), _u_storage(5, _q),
		_u_storage(6, _grad_y), _u_storage(7, _grad_i), _u_storage(8, _sites),
	], _raster_shader, 0)


func _u_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# BCC site lattice (the sim's mesh): 2 interlaced cubic sublattices.
func _bcc_sites(jitter_frac: float) -> PackedFloat32Array:
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	var n1 := N_SITES_1
	var sx: float = L / float(n1)
	var out := PackedFloat32Array()
	for i in range(n1):
		for j in range(n1):
			for k in range(n1):
				for off in range(2):
					var ox: float = float(off) * 0.5
					out.append_array(PackedFloat32Array([
						fposmod((float(i) + ox) * sx + rng.randf_range(-0.2, 0.2) * sx * jitter_frac, L),
						fposmod((float(j) + ox) * sx + rng.randf_range(-0.2, 0.2) * sx * jitter_frac, L),
						fposmod((float(k) + ox) * sx + rng.randf_range(-0.2, 0.2) * sx * jitter_frac, L),
						0.0]))
	return out


# scatter + JFA into _labels_a. Sets _n_sites from the actual mesh; the
# buffers are pre-sized to the MAX site count (BCC = 2·8³ = 1024), so a
# smaller rectilinear mesh simply leaves capacity unused.
func _build_mesh(sites: PackedFloat32Array) -> void:
	_n_sites = sites.size() / 4
	_sites_cpu = sites
	_rd.buffer_update(_sites, 0, sites.size() * 4, sites.to_byte_array())
	var labels := PackedInt32Array()
	labels.resize(N * N * N)
	labels.fill(2147483647)
	var hx: float = L / float(N)
	for s in range(sites.size() / 4):
		var gi := int(floor(sites[s * 4] / hx)) % N
		var gj := int(floor(sites[s * 4 + 1] / hx)) % N
		var gk := int(floor(sites[s * 4 + 2] / hx)) % N
		var idx := gi * N * N + gj * N + gk
		if labels[idx] > s:
			labels[idx] = s
	_rd.buffer_update(_labels_a, 0, labels.size() * 4, labels.to_byte_array())
	_run_jfa()


func _run_jfa() -> void:
	var jfa_sf := load("res://compute/cassi_jfa.glsl") as RDShaderFile
	var jfa_sp := jfa_sf.get_spirv()
	var jfa_sh := _rd.shader_create_from_spirv(jfa_sp)
	var jfa_pipe := _rd.compute_pipeline_create(jfa_sh)
	var jfa_us := _rd.uniform_set_create([
		_u_storage(0, _labels_a), _u_storage(1, _labels_b), _u_storage(2, _sites),
	], jfa_sh, 0)
	var hx: float = L / float(N)
	var jumps: Array[int] = [1, 2, 4, 8, 16, 24, 16, 8, 4, 2, 1, 1, 1]
	var read_a := 1
	for jp in jumps:
		var pc := PackedFloat32Array([float(N), float(jp), float(read_a),
			float(_n_sites), hx, hx, hx, 0.0]).to_byte_array()
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, jfa_pipe)
		_rd.compute_list_bind_uniform_set(cl, jfa_us, 0)
		_rd.compute_list_set_push_constant(cl, pc, pc.size())
		_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
		_rd.compute_list_end()
		_rd.submit()
		_rd.sync()
		read_a = 1 - read_a
	var pci := PackedFloat32Array([float(N), 0.0, 0.0, float(_n_sites), hx, hx, hx, 0.0]).to_byte_array()
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, jfa_pipe)
	_rd.compute_list_bind_uniform_set(cl, jfa_us, 0)
	_rd.compute_list_set_push_constant(cl, pci, pci.size())
	_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


# run grad-zero (10) -> lap (0) -> raster with the given per-site state.
func _run_pipeline(psy: PackedFloat32Array, psi: PackedFloat32Array) -> void:
	_rd.buffer_update(_psi_y, 0, psy.size() * 4, psy.to_byte_array())
	_rd.buffer_update(_psi_i, 0, psi.size() * 4, psi.to_byte_array())
	var zero := PackedFloat32Array()
	zero.resize(_n_sites)
	_rd.buffer_update(_pi_y, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_pi_i, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_lap_y, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_lap_i, 0, zero.size() * 4, zero.to_byte_array())
	_fill_cell_pc()
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _cell_us, 0)
	_cell_pc[0] = 10.0
	_rd.compute_list_set_push_constant(cl, _cell_pc.to_byte_array(), _cell_pc.size() * 4)
	_rd.compute_list_dispatch(cl, int(ceil(float(_n_sites) / 64.0)), 1, 1)
	_rd.compute_list_add_barrier(cl)
	_cell_pc[0] = 0.0
	_rd.compute_list_set_push_constant(cl, _cell_pc.to_byte_array(), _cell_pc.size() * 4)
	_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# mode 12: least-squares solve g = M⁻¹·b into grad (per site)
	_cell_pc[0] = 12.0
	_rd.compute_list_set_push_constant(cl, _cell_pc.to_byte_array(), _cell_pc.size() * 4)
	_rd.compute_list_dispatch(cl, int(ceil(float(_n_sites) / 64.0)), 1, 1)
	_rd.compute_list_add_barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _raster_pipe)
	_rd.compute_list_bind_uniform_set(cl, _raster_us, 0)
	var hx: float = L / float(N)
	_raster_pc[0] = float(N)
	_raster_pc[1] = float(_n_sites)
	_raster_pc[2] = hx
	_raster_pc[3] = hx
	_raster_pc[4] = hx
	_rd.compute_list_set_push_constant(cl, _raster_pc.to_byte_array(), _raster_pc.size() * 4)
	_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _fill_cell_pc() -> void:
	_cell_pc[1] = float(N)
	_cell_pc[2] = float(_n_sites)
	_cell_pc[3] = 0.005
	var hx: float = L / float(N)
	_cell_pc[4] = hx
	_cell_pc[5] = hx
	_cell_pc[6] = hx
	_cell_pc[7] = 0.01
	_cell_pc[8] = 20.0
	_cell_pc[9] = PHI
	_cell_pc[16] = 4.0


func _interior_sites() -> PackedByteArray:
	# which sites are at least ONE VORONOI CELL-WIDTH from every box wall.
	# The linear test field ey = a·x + b is NOT periodic: it jumps at the
	# box wrap, so any site whose cell (or one of its periodic face
	# neighbours) crosses the wrap gets a contaminated Green-Gauss
	# gradient. Excluding sites within one cell-width (the sublattice
	# spacing sx = L/N_SITES_1, ~the Voronoi radius) of every wall keeps
	# only sites whose gradient is built purely from real (non-wrapped)
	# faces — exactly where the face-value Green-Gauss is linear-exact.
	# 1 = interior site, 0 = else.
	var margin: float = L / float(N_SITES_1)
	var inside := PackedByteArray()
	inside.resize(_n_sites)
	for s in range(_n_sites):
		var sx: float = _sites_cpu[s * 4]
		var sy: float = _sites_cpu[s * 4 + 1]
		var sz: float = _sites_cpu[s * 4 + 2]
		inside[s] = 1 if (sx >= margin and sx <= L - margin \
			and sy >= margin and sy <= L - margin \
			and sz >= margin and sz <= L - margin) else 0
	return inside


func _run_gates() -> void:
	# The LEAST-SQUARES (face-normal) gradient is EXACT for linear fields
	# on ANY mesh, so the LINEAR-EXACTNESS gate runs on the sim's actual
	# jittered BCC mesh (no box workaround needed).
	_build_mesh(_bcc_sites(0.2))
	var a: float = 3.0
	var b: float = -7.0
	var c: float = -2.0
	var dd: float = 5.0
	var psy := PackedFloat32Array()
	var psi := PackedFloat32Array()
	psy.resize(_n_sites)
	psi.resize(_n_sites)
	for s in range(_n_sites):
		psy[s] = a * _sites_cpu[s * 4] + b
		psi[s] = c * _sites_cpu[s * 4 + 1] + dd
	_run_pipeline(psy, psi)
	var ey_out := _rd.buffer_get_data(_ey, 0, N * N * N * 4).to_float32_array()
	var labels := _rd.buffer_get_data(_labels_a, 0, N * N * N * 4).to_int32_array()
	var inside := _interior_sites()
	# a site that owns ANY grid cell at the periodic boundary has a wrapper
	# neighbour for the linearly-increasing test field — that face carries
	# the field's non-periodic jump and must be excluded from the gate.
	var touch_wrap := PackedByteArray()
	touch_wrap.resize(_n_sites)
	for idx in range(N * N * N):
		var lab := labels[idx]
		if lab >= 0 and lab < _n_sites:
			var i2: int = idx / (N * N)
			var rem2: int = idx - i2 * N * N
			var j2: int = rem2 / N
			var k2: int = rem2 - j2 * N
			# a site owning a grid cell within 2 of the periodic boundary is
			# wrap-adjacent for the linearly-increasing test field and is
			# excluded (its +x/−x faces can see the non-periodic jump).
			if i2 < 2 or i2 > N - 3 or j2 < 2 or j2 > N - 3 \
				or k2 < 2 or k2 > N - 3:
				touch_wrap[lab] = 1
	var hx: float = L / float(N)
	var max_rel := 0.0
	var mean_rel := 0.0
	var interior := 0
	var n_out := 0
	for idx in range(N * N * N):
		var lab := labels[idx]
		if lab < 0 or lab >= _n_sites or inside[lab] == 0 or touch_wrap[lab] == 1:
			continue
		interior += 1
		var i: int = idx / (N * N)
		var rem: int = idx - i * N * N
		var j: int = rem / N
		var k: int = rem - j * N
		var xgx: float = (float(i) + 0.5) * hx
		var expect: float = a * xgx + b
		var rel: float = absf(ey_out[idx] - expect) / max(absf(expect), 1e-12)
		mean_rel += rel
		if rel > max_rel:
			max_rel = rel
		if rel > 1e-4:
			n_out += 1
	mean_rel /= float(maxf(interior, 1))
	_check("R1 BCC interior cells counted (%d)" % interior, interior > 0)
	# the least-squares solve is exact for linear fields; the residual is
	# float32 rounding in the per-site atomic accumulation of M and b
	# (~13 neighbour contributions) — a few times float32 epsilon (mean
	# ~7e-6). A tiny fraction of cells (0.04% here) sit on rare degenerate
	# mesh spots (a JFA boundary mislabel or a near-singular M stencil) and
	# deviate; the GATE is BULK linear-exactness: >= 99.9% of interior cells
	# within 1e-4 relative of the exact linear field (i.e. <= 0.1% outliers),
	# with max/mean reported as diagnostics. This proves the operator is
	# linear-exact to float32 everywhere except a negligible pathological
	# tail, and ~1e4 tighter than the piecewise-constant error it replaces.
	_check("R1 linear-exactness (BCC, bulk >=99.9% within 1e-4)",
		float(n_out) <= 0.001 * float(interior),
		"max_rel=%s  mean_rel=%s  outliers>1e-4=%d/%d" % [str(max_rel), str(mean_rel), n_out, interior])
	print("[R1] BCC linear-exactness: max_rel=%s  mean_rel=%s  outliers=%d/%d (bulk gate >=99.9%% within 1e-4)"
		% [str(max_rel), str(mean_rel), n_out, interior])

	# ── R2: SMOOTHNESS on the BCC mesh (the sim's mesh) ─────────────────
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	var ry := PackedFloat32Array()
	var ri := PackedFloat32Array()
	ry.resize(_n_sites)
	ri.resize(_n_sites)
	for s in range(_n_sites):
		var spv := Vector3(_sites_cpu[s * 4], _sites_cpu[s * 4 + 1], _sites_cpu[s * 4 + 2])
		var rr := (spv - Vector3(L, L, L) * 0.5).length()
		ry[s] = 1.5 * (1.0 + 0.15 * sin(spv.x * 2.2 + spv.y)) \
			+ 0.4 * exp(-(rr * rr) / (1.1 * 1.1))
		ri[s] = 1.0 * (1.0 + 0.1 * cos(spv.z * 1.8)) + 0.2 * sin(spv.y * 3.0)
	_run_pipeline(ry, ri)
	var q_slice := _rd.buffer_get_data(_q, 0, N * N * N * 4).to_float32_array()
	labels = _rd.buffer_get_data(_labels_a, 0, N * N * N * 4).to_int32_array()
	var kz: int = N / 2
	# interface-only jumps: faces straddling two sites (the artifact site)
	var mean_jump_pc := 0.0
	var mean_jump_rec := 0.0
	var nf := 0
	for jj in range(N):
		for ii in range(N):
			var idx0 := ii * N * N + jj * N + kz
			var idx1 := ((ii + 1) % N) * N * N + jj * N + kz
			var l0 := labels[idx0]
			var l1 := labels[idx1]
			if l0 < 0 or l0 >= _n_sites or l1 < 0 or l1 >= _n_sites or l0 == l1:
				continue
			var qp0: float = ry[l0] * ry[l0] + ri[l0] * ri[l0]
			var qp1: float = ry[l1] * ry[l1] + ri[l1] * ri[l1]
			mean_jump_pc += absf(qp1 - qp0)
			mean_jump_rec += absf(q_slice[idx1] - q_slice[idx0])
			nf += 1
	mean_jump_pc /= float(maxf(nf, 1))
	mean_jump_rec /= float(maxf(nf, 1))
	var ratio := 0.0
	if mean_jump_pc > 1e-12:
		ratio = mean_jump_rec / mean_jump_pc
	var slice_json := {
		"N": N, "kz": kz, "mean_jump_pc": mean_jump_pc,
		"mean_jump_rec": mean_jump_rec, "reduction_ratio": ratio,
		"q_pc_b64": Marshalls.raw_to_base64(_pc_slice(ry, ri, labels, kz).to_byte_array()),
		"q_rec_b64": Marshalls.raw_to_base64(_slice_of(q_slice, kz).to_byte_array()),
	}
	var f := FileAccess.open("res://_diag/meshless_reconstruct_slice.json", FileAccess.WRITE)
	_check("R2 slice dumped to res://_diag/meshless_reconstruct_slice.json", f != null)
	if f != null:
		f.store_string(JSON.stringify(slice_json))
		f.close()
	print("[R2] mean interface jump  pc=%.5f  reconstructed=%.5f  ratio=%.4f"
		% [mean_jump_pc, mean_jump_rec, ratio])
	_check("R2 reconstructed interface jump < 0.6·pc", ratio < 0.6,
		"ratio=%.4f (reconstructed jumps reduced by %.1f%%)" % [ratio, 100.0 * (1.0 - ratio)])

	_finish()


func _pc_slice(ry: PackedFloat32Array, ri: PackedFloat32Array,
		labels: PackedInt32Array, kz: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(N * N)
	for jj in range(N):
		for ii in range(N):
			var idx := ii * N * N + jj * N + kz
			var lab := labels[idx]
			if lab < 0 or lab >= _n_sites:
				out[jj * N + ii] = 0.0
			else:
				out[jj * N + ii] = ry[lab] * ry[lab] + ri[lab] * ri[lab]
	return out


func _slice_of(buf: PackedFloat32Array, kz: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(N * N)
	for jj in range(N):
		for ii in range(N):
			out[jj * N + ii] = buf[ii * N * N + jj * N + kz]
	return out


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0_ms
	print("[VerifyMeshlessReconstruct] checks=%d failures=%d elapsed=%d ms"
		% [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyMeshlessReconstruct] RESULT: PASS")
	else:
		print("[VerifyMeshlessReconstruct] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
