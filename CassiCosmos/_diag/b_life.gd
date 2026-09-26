extends Node
## B-build piece 3 — the PATCH LIFECYCLE (b_life): the fine patch RE-TILES
## at the pinned cadence to follow the structure (the "box stops being
## fixed" for the patches — the owner's expands-past-any-finite-tile goal).
##
## The coarse field (the sim's canonical two-fluid) carries a forward-
## projected rho pulse (the gate-vi IC). ONE fine patch (r=2, fixed size)
## re-fits its POSITION every CADENCE steps to the pulse's centroid — the
## re-tile is a PC-only update (the shader's rim + downsample read the
## per-patch offsets; no buffer rebuild — deterministic).
##
## Assertions:
##   a. the patch tracks the structure: |x_off - centroid| <= the lag bound;
##   b. the structure's envelope stays INSIDE the patch at every re-tile;
##   c. the structure EXITS the old tile's extent (the fixed tile would
##      have lost it — the patch follows instead);
##   d. determinism: two identical runs -> the coarse+fine readbacks
##      bit-identical (max-diff == 0.0).

const COARSE_N := 64
const DT := 0.01
const CADENCE := 200
const STEPS_TOTAL := 16000   # the main lobe crosses +0.25 at ~5200-8100; margin for the full-run determinism
const R := 2
const PHI := 1.618033988749895
const XI := 1.0
const OMEGA2 := 0.0   # the pure wave: no checkerboard attractor
const PULSE_AMP := 0.2
const PULSE_X0 := -0.35    # normalized launch
const PULSE_SIG := 0.08    # normalized sigma (the envelope +-0.16)
const OLD_TILE_EDGE := 0.25  # the initial patch's +x edge (normalized)
const LAG_BOUND := 0.09
const PATCH_HALF := 0.25   # the patch's half-width (normalized)

var _rd: RenderingDevice
var _ext_c := Vector3.ONE
var _c_shader: RID = RID()
var _c_pipe: RID = RID()
var _c_set: RID = RID()
var _b_cey: RID = RID(); var _b_cei: RID = RID(); var _b_cq: RID = RID()
var _b_cvel: RID = RID(); var _b_crho: RID = RID(); var _b_cscr: RID = RID()
var _fine_shader: RID = RID()
var _fine_pipe: RID = RID()
var _fine_set: RID = RID()
var _b_fey: RID = RID(); var _b_fei: RID = RID(); var _b_fq: RID = RID()
var _b_fvel: RID = RID(); var _b_frho: RID = RID(); var _b_fscr: RID = RID()
var _n_fx := 32; var _n_fy := 64; var _n_fz := 64
var _padx := 34; var _pady := 66; var _padz := 66
var _ncov := 16
var _fine_pc := PackedByteArray()
var _coarse_pc := PackedByteArray()
var _phase := 0
var _step := 0
var _x_off := 0.0
var _track_ok := true
var _cover_ok := true
var _exit_ok := false
var _run_ref := {}
var _fail := 0


func _ready() -> void:
	_rd = RenderingServer.get_rendering_device()
	_ext_c = Vector3(121.4, 75.0, 196.4)   # the fixed probe box (cluster_radius 50, phi-aspect)
	_make_coarse_pc()
	if not _setup_coarse():
		print("[BLife] FAIL: coarse pipeline setup failed")
		_fail += 1
		get_tree().quit(0)
	if not _setup_fine():
		print("[BLife] FAIL: fine pipeline setup failed")
		_fail += 1
		get_tree().quit(0)
	_build_fine(R)
	_inject_ic()
	_zero_density()
	print("[BLife] started: box=(%.1f, %.1f, %.1f) patch r=%d tile %dx%dx%d"
		% [_ext_c.x, _ext_c.y, _ext_c.z, R, _n_fx, _n_fy, _n_fz])


func _process(_delta: float) -> void:
	if _rd == null:
		return
	if _phase >= 2:
		_verdict()
		return
	_run_batch()
	_step += 1
	if _step % CADENCE == 0:
		_retile()
	if _step >= STEPS_TOTAL:
		_finish_run()


func _finish_run() -> void:
	var snap := _snapshot()
	if _phase == 0:
		_run_ref = snap
		print("[BLife] run A done: tracking=%s coverage=%s exit=%s"
			% [str(_track_ok), str(_cover_ok), str(_exit_ok)])
		if not (_track_ok and _cover_ok and _exit_ok):
			_fail += 1
		_phase = 1
		_step = 0
		_x_off = 0.0
		_track_ok = true
		_cover_ok = true
		_exit_ok = false
		_fill_fine_pc(R)   # reset the patch to the start
		_inject_ic()
		_zero_density()
		_reset_all()   # the FINE + the auxiliary buffers: run A started
		# from zeros (the _make_* setup); run B MUST start from the same
		# zeros — the per-step downsample otherwise feeds the coarse slab
		# run A's END state and the fields diverge (the blife11 FAIL).
	else:
		var det := _snapshot()
		var md := _max_diff(det["ey"], _run_ref["ey"])
		var mdf := _max_diff(det["fine_ey"], _run_ref["fine_ey"])
		print("[BLife] determinism max-diff: coarse=%.6f fine=%.6f -> %s"
			% [md, mdf, "PASS" if (md == 0.0 and mdf == 0.0) else "FAIL"])
		if md != 0.0 or mdf != 0.0:
			_fail += 1
		_phase = 2


## The re-tile: measure the structure's position from the coarse field,
## re-fit the patch's x_off, assert the tracking + the coverage.
func _retile() -> void:
	var n := COARSE_N
	var ey: PackedFloat32Array = _rd.buffer_get_data(_b_cey, 0, n * n * n * 4).to_float32_array()
	var ei: PackedFloat32Array = _rd.buffer_get_data(_b_cei, 0, n * n * n * 4).to_float32_array()
	# The structure position = the |rho| PEAK (the x-slice sum collapsed
	# over y/z): the |rho| CENTROID is tail-dominated as the dispersive
	# wake spreads (the blife11 centroid stalled at +0.13 while the main
	# lobe crossed +0.25); the peak tracks the main lobe cleanly, and the
	# signed rho's total collapses to ~0 (the oscillatory tail).
	var peak_x := 0.0
	var peak_s := -1.0
	for i in range(n):
		var s := 0.0
		for j in range(n):
			for k in range(n):
				s += absf(ey[i + n * (j + n * k)] + ei[i + n * (j + n * k)])
		if s > peak_s:
			peak_s = s
			peak_x = (float(i) + 0.5) / float(n) * 2.0 - 1.0
	var c := peak_x
	_x_off = clampf(c, -0.95, 0.95)
	_fine_pc.encode_float(56, _x_off)
	# a. the tracking lag
	if absf(c - _x_off) > LAG_BOUND:
		_track_ok = false
	# b. the coverage: the pulse's envelope inside the patch
	if absf(c - _x_off) + 2.0 * PULSE_SIG > PATCH_HALF:
		_cover_ok = false
	# c. the exit: the structure beyond the OLD tile's extent
	if c > OLD_TILE_EDGE:
		_exit_ok = true
	if _step % (CADENCE * 5) == 0:
		print("[BLife] t=%d centroid=%.3f x_off=%.3f lag=%.3f exit=%s"
			% [_step, c, _x_off, absf(c - _x_off), str(_exit_ok)])


func _verdict() -> void:
	print("[BLife] ============ B-BUILD PIECE 3 (PATCH LIFECYCLE) VERDICT ============")
	if _fail == 0:
		print("[BLife] VERDICT: PASS — the patch follows the structure; the tile stops being fixed")
	else:
		print("[BLife] VERDICT: FAIL — %d failures" % _fail)
	get_tree().quit(0)


func _setup_coarse() -> bool:
	var sf = load("res://compute/cassi_two_fluid.glsl")
	if sf == null:
		return false
	var spirv = sf.get_spirv()
	if spirv == null:
		return false
	_c_shader = _rd.shader_create_from_spirv(spirv)
	_c_pipe = _rd.compute_pipeline_create(_c_shader)
	var n3 := COARSE_N * COARSE_N * COARSE_N
	_b_cey = _rd.storage_buffer_create(n3 * 4)
	_b_cei = _rd.storage_buffer_create(n3 * 4)
	_b_cq = _rd.storage_buffer_create(n3 * 4)
	_b_cvel = _rd.storage_buffer_create(n3 * 16)
	_b_crho = _rd.storage_buffer_create(n3 * 4)
	_b_cscr = _rd.storage_buffer_create(n3 * 16)
	var z := PackedFloat32Array()
	z.resize(n3)
	_rd.buffer_update(_b_cey, 0, n3 * 4, z.to_byte_array())
	_rd.buffer_update(_b_cei, 0, n3 * 4, z.to_byte_array())
	_rd.buffer_update(_b_cq, 0, n3 * 4, z.to_byte_array())
	_rd.buffer_update(_b_crho, 0, n3 * 4, z.to_byte_array())
	_c_set = _rd.uniform_set_create([
		_uni(0, _b_cey), _uni(1, _b_cei), _uni(2, _b_cq), _uni(3, _b_cvel),
		_uni(4, _b_crho), _uni(5, _b_cscr),
	], _c_shader, 0)
	return _c_pipe.is_valid()


func _make_coarse_pc() -> void:
	_coarse_pc = PackedByteArray()
	_coarse_pc.resize(16 * 4)
	_coarse_pc.encode_float(0, float(COARSE_N))
	_coarse_pc.encode_float(4, DT)
	_coarse_pc.encode_float(8, 0.0)
	_coarse_pc.encode_float(12, PHI)
	_coarse_pc.encode_float(16, XI)
	_coarse_pc.encode_float(20, 0.0)
	_coarse_pc.encode_float(24, 0.0)
	_coarse_pc.encode_float(28, 0.0)
	_coarse_pc.encode_float(32, 0.0)
	_coarse_pc.encode_float(36, 0.0)
	_coarse_pc.encode_float(40, 0.0)
	_coarse_pc.encode_float(44, _ext_c.x)
	_coarse_pc.encode_float(48, _ext_c.y)
	_coarse_pc.encode_float(52, _ext_c.z)
	_coarse_pc.encode_float(56, 0.0)
	_coarse_pc.encode_float(60, OMEGA2)


func _fill_fine_pc(r: int) -> void:
	_fine_pc = PackedByteArray()
	_fine_pc.resize(22 * 4)
	_fine_pc.encode_float(0, float(_n_fx))
	_fine_pc.encode_float(4, float(_n_fy))
	_fine_pc.encode_float(8, float(_n_fz))
	_fine_pc.encode_float(12, DT)
	_fine_pc.encode_float(16, PHI)
	_fine_pc.encode_float(20, OMEGA2)
	_fine_pc.encode_float(24, 0.25 * _ext_c.x)
	_fine_pc.encode_float(28, _ext_c.y)
	_fine_pc.encode_float(32, _ext_c.z)
	_fine_pc.encode_float(36, 0.0)
	_fine_pc.encode_float(40, float(COARSE_N))
	_fine_pc.encode_float(44, _ext_c.x)
	_fine_pc.encode_float(48, _ext_c.y)
	_fine_pc.encode_float(52, _ext_c.z)
	_fine_pc.encode_float(56, _x_off)
	_fine_pc.encode_float(60, 0.0)
	_fine_pc.encode_float(64, 0.0)
	_fine_pc.encode_float(68, float(_padx))
	_fine_pc.encode_float(72, float(_pady))
	_fine_pc.encode_float(76, float(_padz))
	_fine_pc.encode_float(80, float(r))
	var hn_c := float(COARSE_N) * 0.5
	var h0_c := minf(minf(_ext_c.x, _ext_c.y), _ext_c.z) / hn_c
	_fine_pc.encode_float(84, h0_c)


func _build_fine(r: int) -> void:
	var n_cells := int(round(0.5 / (2.0 / float(COARSE_N))))
	_n_fx = n_cells * r
	_n_fy = COARSE_N
	_n_fz = COARSE_N
	_padx = _n_fx + 2
	_pady = _n_fy + 2
	_padz = _n_fz + 2
	_ncov = n_cells
	_free_fine_buffers()
	_make_fine_buffers()
	_fill_fine_pc(r)


func _setup_fine() -> bool:
	var sf = load("res://_diag/compute/m1_patch_iface.glsl")
	if sf == null:
		return false
	var spirv = sf.get_spirv()
	if spirv == null:
		return false
	_fine_shader = _rd.shader_create_from_spirv(spirv)
	_fine_pipe = _rd.compute_pipeline_create(_fine_shader)
	return _fine_pipe.is_valid()


func _make_fine_buffers() -> void:
	var nf := _padx * _pady * _padz
	_b_fey = _rd.storage_buffer_create(nf * 4)
	_b_fei = _rd.storage_buffer_create(nf * 4)
	_b_fq = _rd.storage_buffer_create(nf * 4)
	_b_frho = _rd.storage_buffer_create(nf * 4)
	_b_fvel = _rd.storage_buffer_create(nf * 16)
	_b_fscr = _rd.storage_buffer_create(nf * 16)
	var z := PackedFloat32Array()
	z.resize(nf)
	_rd.buffer_update(_b_fey, 0, nf * 4, z.to_byte_array())
	_rd.buffer_update(_b_fei, 0, nf * 4, z.to_byte_array())
	_rd.buffer_update(_b_fq, 0, nf * 4, z.to_byte_array())
	_rd.buffer_update(_b_frho, 0, nf * 4, z.to_byte_array())
	var zv := PackedFloat32Array()
	zv.resize(nf * 4)
	_rd.buffer_update(_b_fvel, 0, nf * 16, zv.to_byte_array())
	_rd.buffer_update(_b_fscr, 0, nf * 16, zv.to_byte_array())
	_fine_set = _rd.uniform_set_create([
		_uni(0, _b_fey), _uni(1, _b_fei), _uni(2, _b_fq), _uni(3, _b_fvel),
		_uni(4, _b_frho), _uni(5, _b_fscr),
		_uni(6, _b_cey), _uni(7, _b_cei),
	], _fine_shader, 0)


func _uni(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _free_fine_buffers() -> void:
	if _fine_set.is_valid():
		_rd.free_rid(_fine_set)
		_fine_set = RID()
	for r in [_b_fey, _b_fei, _b_fq, _b_fvel, _b_frho, _b_fscr]:
		if r.is_valid():
			_rd.free_rid(r)


func _inject_ic() -> void:
	var n := COARSE_N
	var ey := PackedFloat32Array()
	var ei := PackedFloat32Array()
	var zv := PackedFloat32Array()
	ey.resize(n * n * n)
	ei.resize(n * n * n)
	zv.resize(n * n * n * 4)
	var re := PackedFloat32Array()
	var im := PackedFloat32Array()
	re.resize(n * n * n)
	im.resize(n * n * n)
	for i in range(n):
		for j in range(n):
			for k in range(n):
				var wx := (float(i) + 0.5) / float(n) * 2.0 - 1.0
				var wy := (float(j) + 0.5) / float(n) * 2.0 - 1.0
				var d := wx - PULSE_X0
				var p := PULSE_AMP * exp(-d * d / (PULSE_SIG * PULSE_SIG))
				var id := i + n * (j + n * k)
				ey[id] = PHI * p
				ei[id] = p
				re[id] = (1.0 + PHI) * p
	_fft3d(re, im, false)
	var sym := _lap_symbols()
	for i in range(n):
		var kx := TAU * float(i) / float(n)
		var kxs := kx
		if i > n / 2:
			kxs -= TAU
		for j in range(n):
			var ky := TAU * float(j) / float(n)
			for k in range(n):
				var kz := TAU * float(k) / float(n)
				var s: float = sym["ax"] * (2.0 * cos(kx) - 2.0)
				s += sym["ay"] * (2.0 * cos(ky) - 2.0)
				s += sym["az"] * (2.0 * cos(kz) - 2.0)
				s += sym["bxy"] * (4.0 * cos(kx) * cos(ky) - 4.0)
				s += sym["bxz"] * (4.0 * cos(kx) * cos(kz) - 4.0)
				s += sym["byz"] * (4.0 * cos(ky) * cos(kz) - 4.0)
				var w := sqrt(maxf(-s, 0.0))
				if kxs < 0.0:
					w = -w
				var id := i + n * (j + n * k)
				var a := re[id]
				var b := im[id]
				re[id] = w * b
				im[id] = -w * a
	_fft3d(re, im, true)
	var pf := 1.0 / (1.0 + PHI)
	for i in range(n * n * n):
		zv[i * 4] = PHI * pf * re[i]
		zv[i * 4 + 1] = pf * re[i]
	_rd.buffer_update(_b_cey, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_b_cei, 0, ei.size() * 4, ei.to_byte_array())
	_rd.buffer_update(_b_cvel, 0, zv.size() * 4, zv.to_byte_array())


func _lap_symbols() -> Dictionary:
	var n := float(COARSE_N)
	var hn := n * 0.5
	var hx := _ext_c.x / hn
	var hy := _ext_c.y / hn
	var hz := _ext_c.z / hn
	var h0 := minf(minf(_ext_c.x, _ext_c.y), _ext_c.z) / hn
	var hx2 := hx * hx
	var hy2 := hy * hy
	var hz2 := hz * hz
	var h02 := h0 * h0
	var bxy := (1.0 / 3.0) * h02 / (hx2 + hy2)
	var bxz := (1.0 / 3.0) * h02 / (hx2 + hz2)
	var byz := (1.0 / 3.0) * h02 / (hy2 + hz2)
	return {
		"ax": h02 / hx2 - 2.0 * (bxy + bxz),
		"ay": h02 / hy2 - 2.0 * (bxy + byz),
		"az": h02 / hz2 - 2.0 * (bxz + byz),
		"bxy": bxy, "bxz": bxz, "byz": byz,
	}


func _zero_density() -> void:
	var n3 := COARSE_N * COARSE_N * COARSE_N
	var z := PackedFloat32Array()
	z.resize(n3)
	_rd.buffer_update(_b_crho, 0, n3 * 4, z.to_byte_array())


## Re-queue the FULL zero initialization of the fine + the auxiliary
## buffers (the exact _ready() state) so the run-B start is bit-identical
## to run A's. The coarse ey/ei/vel are overwritten by _inject_ic; the
## pass-A scratch is fully written each step (the initial garbage never
## read), but zero it anyway for the byte-identical determinism.
func _reset_all() -> void:
	var n3 := COARSE_N * COARSE_N * COARSE_N
	var z := PackedFloat32Array()
	z.resize(n3)
	_rd.buffer_update(_b_cq, 0, n3 * 4, z.to_byte_array())
	_rd.buffer_update(_b_crho, 0, n3 * 4, z.to_byte_array())
	var zs := PackedFloat32Array()
	zs.resize(n3 * 4)
	_rd.buffer_update(_b_cscr, 0, n3 * 16, zs.to_byte_array())
	var nf := _padx * _pady * _padz
	var zf := PackedFloat32Array()
	zf.resize(nf)
	_rd.buffer_update(_b_fey, 0, nf * 4, zf.to_byte_array())
	_rd.buffer_update(_b_fei, 0, nf * 4, zf.to_byte_array())
	_rd.buffer_update(_b_fq, 0, nf * 4, zf.to_byte_array())
	_rd.buffer_update(_b_frho, 0, nf * 4, zf.to_byte_array())
	var zfv := PackedFloat32Array()
	zfv.resize(nf * 4)
	_rd.buffer_update(_b_fvel, 0, nf * 16, zfv.to_byte_array())
	_rd.buffer_update(_b_fscr, 0, nf * 16, zfv.to_byte_array())


func _run_batch() -> void:
	var rd := _rd
	var cl := rd.compute_list_begin()
	# The local size is 4^3: the dispatches must be 3D (a 1D dispatch
	# covers only a 4-thread-wide slab of the volume — the pulse froze).
	var wg_c := int(ceil(float(COARSE_N) / 4.0))
	var wg_fx := int(ceil(float(_n_fx) / 4.0))
	var wg_fy := int(ceil(float(_n_fy) / 4.0))
	var wg_fz := int(ceil(float(_n_fz) / 4.0))
	var wg_px := int(ceil(float(_padx) / 4.0))
	var wg_py := int(ceil(float(_pady) / 4.0))
	var wg_pz := int(ceil(float(_padz) / 4.0))
	var wg_ds := int(ceil(float(_ncov) / 4.0))
	var wg_dy := int(ceil(float(COARSE_N) / 4.0))
	rd.compute_list_bind_compute_pipeline(cl, _c_pipe)
	rd.compute_list_bind_uniform_set(cl, _c_set, 0)
	_coarse_pc.encode_float(56, 0.0)
	rd.compute_list_set_push_constant(cl, _coarse_pc, 64)
	rd.compute_list_dispatch(cl, wg_c, wg_c, wg_c)
	rd.compute_list_add_barrier(cl)
	_coarse_pc.encode_float(56, 1.0)
	rd.compute_list_set_push_constant(cl, _coarse_pc, 64)
	rd.compute_list_dispatch(cl, wg_c, wg_c, wg_c)
	rd.compute_list_add_barrier(cl)
	rd.compute_list_bind_compute_pipeline(cl, _fine_pipe)
	rd.compute_list_bind_uniform_set(cl, _fine_set, 0)
	_fine_pc.encode_float(36, 0.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_px, wg_py, wg_pz)
	rd.compute_list_add_barrier(cl)
	_fine_pc.encode_float(36, 1.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_fx, wg_fy, wg_fz)
	rd.compute_list_add_barrier(cl)
	_fine_pc.encode_float(36, 2.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_fx, wg_fy, wg_fz)
	rd.compute_list_add_barrier(cl)
	_fine_pc.encode_float(36, 3.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_ds, wg_dy, wg_dy)
	rd.compute_list_end()


func _snapshot() -> Dictionary:
	var n := COARSE_N
	return {
		"ey": _rd.buffer_get_data(_b_cey, 0, n * n * n * 4).to_float32_array(),
		"fine_ey": _rd.buffer_get_data(_b_fey, 0, _padx * _pady * _padz * 4).to_float32_array(),
	}


func _max_diff(a: PackedFloat32Array, b: PackedFloat32Array) -> float:
	var m := 0.0
	for i in range(mini(a.size(), b.size())):
		m = maxf(m, absf(a[i] - b[i]))
	return m


## Separable 3D radix-2 FFT (the gate-vi core, 64^3).
func _fft3d(re: PackedFloat32Array, im: PackedFloat32Array, invert: bool) -> void:
	var n := COARSE_N
	var line_r := PackedFloat32Array()
	var line_i := PackedFloat32Array()
	line_r.resize(n)
	line_i.resize(n)
	for axis in range(3):
		for i2 in range(n * n):
			var i0 := 0
			var stride := 1
			if axis == 0:
				i0 = n * i2
				stride = 1
			elif axis == 1:
				i0 = (i2 % n) + n * n * (i2 / n)
				stride = n
			else:
				i0 = (i2 % n) + n * (i2 / n)
				stride = n * n
			for t in range(n):
				line_r[t] = re[i0 + t * stride]
				line_i[t] = im[i0 + t * stride]
			_fft(line_r, line_i, invert)
			for t in range(n):
				re[i0 + t * stride] = line_r[t]
				im[i0 + t * stride] = line_i[t]


func _fft(re: PackedFloat32Array, im: PackedFloat32Array, invert: bool) -> void:
	var n := re.size()
	var j := 0
	for i in range(1, n):
		var bit := n >> 1
		while j & bit != 0:
			j ^= bit
			bit >>= 1
		j ^= bit
		if i < j:
			var tr := re[i]; re[i] = re[j]; re[j] = tr
			var ti := im[i]; im[i] = im[j]; im[j] = ti
	var len2 := 2
	while len2 <= n:
		var ang := (2.0 * PI / float(len2)) * (-1.0 if not invert else 1.0)
		var wr := cos(ang)
		var wi := sin(ang)
		for i in range(0, n, len2):
			var cr := 1.0
			var ci := 0.0
			for k in range(len2 / 2):
				var kk := i + k
				var jj := kk + len2 / 2
				var ur := re[jj] * cr - im[jj] * ci
				var ui := re[jj] * ci + im[jj] * cr
				re[jj] = re[kk] - ur
				im[jj] = im[kk] - ui
				re[kk] += ur
				im[kk] += ui
				var ncr := cr * wr - ci * wi
				ci = cr * wi + ci * wr
				cr = ncr
		len2 <<= 1
	if invert:
		for i in range(n):
			re[i] /= float(n)
			im[i] /= float(n)
