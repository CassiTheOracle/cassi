extends Node
## Gate-vi battery (B-build piece 2): the coarse-fine patch-interface
## continuity test — a wave crossing the interface must not reflect.
##
## The probe runs BOTH tiles itself on the sim's RD:
##   - the COARSE tile = the sim's canonical two-fluid pipeline
##     (_two_fluid_pipe + _us_two_0) on the sim's field buffers with a
##     probe-built 16-float PC (passes A/B, the field of record);
##   - the FINE patch tile = the probe's padded-tile shader
##     (_diag/compute/m1_patch_iface.glsl) on probe-owned buffers with the
##     per-patch PC — the rim (coarse→fine trilinear) + the leapfrog
##     (canonical numerics, linear padded addressing — the boundary
##     stencils read the rim instead of the periodic wrap) + the downsample
##     (fine→coarse cell-average, the fine y/z align 1:1 with the coarse).
##
## Per step, one compute list: coarse A → coarse B → rim → fine A → fine B
## → downsample (the ghost-cell causality: the coarse leads, the fine
## follows on the fresh rim, the slab returns the fine's values).
##
## Measurement (the Riemann invariants — no long reflection-wait): the
## launch region behind the tile, R_± = ρ̇ ∓ c·ρ' — the +x-going incident is
## R_+ (R_− ≈ 0), the −x-going reflection is R_−. R = E(R_− at t_probe) /
## E(R_+ at t_ref). The SAME-resolution arm (r=1) pins the measurement
## floor (the dispersion residual); the resolution-change reflection =
## R_arm − R_cal, pinned at ≤ 2%.
##
## Arms: r=1 (calibration), r=2, r=4, the corner (diagonal pulse, compact
## tile, diagonal invariants), and the r=2 determinism rerun (max-diff == 0).

const COARSE_N := 64
const DT := 0.01
const STEPS_REF := 200
const STEPS_PROBE := 2500
const C_WAVE := 2.3614    # the measured grid front (gate-iv, the same box)
const R_CAL_TAIL := 0.02  # the pinned threshold: R_arm - R_cal <= 2%
const PHI := 1.618033988749895
const XI := 1.0
const OMEGA2 := 0.0   # the pure wave: no checkerboard attractor
const PULSE_AMP := 0.2
const PULSE_X0 := -0.35    # normalized launch
const PULSE_SIG := 0.125   # normalized sigma

var _sim: Node
var _rd: RenderingDevice
var _ext_c := Vector3.ONE
var _fine_shader: RID = RID()
var _fine_pipe: RID = RID()
var _fine_set: RID = RID()
var _b_fey: RID = RID(); var _b_fei: RID = RID(); var _b_fq: RID = RID()
var _b_fvel: RID = RID(); var _b_frho: RID = RID(); var _b_fscr: RID = RID()
var _n_fx := 16; var _n_fy := 64; var _n_fz := 64
var _padx := 18; var _pady := 66; var _padz := 66
var _ncov := 16
var _corner := false
var _fine_pc := PackedByteArray()
var _coarse_pc := PackedByteArray()
var _phase := 0
var _arm := 0
var _step := 0
var _cal := 0.0            # the r=1 measurement floor
var _arms_r := [0.0, 0.0, 0.0, 0.0]   # R per arm (0-2 = r=1/2/4, 3 = corner)
var _ref_forw := 0.0
var _run_ref := {}
var _fail := 0
var _s2_rhod := 0.0
var _s2_dpsi := 0.0
var _s2_cross := 0.0


func _ready() -> void:
	_sim = $CassiSim
	_sim.playing = false
	_rd = _sim._rd
	_sim.reinit()
	_ext_c = _sim._extents()
	_make_coarse_pc()
	if not _setup_fine():
		print("[GateVI] FAIL: fine pipeline setup failed")
		_fail += 1
		get_tree().quit(0)
	_start_arm(0)
	print("[GateVI] started: box=(%.1f, %.1f, %.1f) grid_N=%d dt=%.2f c=%.4f"
		% [_ext_c.x, _ext_c.y, _ext_c.z, COARSE_N, DT, C_WAVE])


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	if _phase >= 99:
		_verdict()
		return
	_run_batch()
	_step += 1
	if _step == STEPS_REF:
		var m := _measure()
		_ref_forw = m["forw"]
		print("[GateVI] arm %d t_ref: E_forw=%.4f E_back=%.4f (rhod2=%.3f dpsi2=%.3f — the forward IC health)"
			% [_arm, m["forw"], m["back"], _s2_rhod, _s2_dpsi])
	if _step >= STEPS_PROBE:
		_finish_arm()


func _finish_arm() -> void:
	var m := _measure()
	var r_val := 0.0
	if _ref_forw > 0.0:
		r_val = m["back"] / _ref_forw
	var tag := ""
	if _arm == 3:
		tag = "corner"
	elif _arm == 4:
		tag = "determinism"
	else:
		tag = "r=%d" % _r_vals[_arm]
	print("[GateVI] arm %s t_probe: E_forw=%.6f E_back=%.6f -> R=%.4f%%"
		% [tag, m["forw"], m["back"], 100.0 * r_val])
	if _arm <= 3:
		_arms_r[_arm] = r_val
		if _arm == 0:
			_cal = r_val
	if _arm == 1:
		_run_ref = _snapshot()   # the determinism reference (the r=2 arm)
	if _arm == 4:
		_phase = 99
		return
	_arm += 1
	_start_arm(_arm)


func _start_arm(arm: int) -> void:
	_arm = arm
	_step = 0
	_corner = arm == 3
	var r: int = 2 if arm >= 3 else _r_vals[arm]
	_build_fine(r)
	_inject_ic()
	_zero_density()
	print("[GateVI] arm %d started: r=%d corner=%s fine tile %dx%dx%d (padded %dx%dx%d)"
		% [arm, r, str(_corner), _n_fx, _n_fy, _n_fz, _padx, _pady, _padz])


var _r_vals := [1, 2, 4]


## Build the fine tile's geometry + buffers for the resolution ratio r.
func _build_fine(r: int) -> void:
	var n_cells := int(round(0.5 / (2.0 / float(COARSE_N))))   # 16 coarse cells
	_n_fx = n_cells * r
	if _corner:
		_n_fy = n_cells * r
		_n_fz = n_cells * r / 2
	else:
		_n_fy = COARSE_N
		_n_fz = COARSE_N
	_padx = _n_fx + 2
	_pady = _n_fy + 2
	_padz = _n_fz + 2
	_ncov = n_cells
	_free_fine_buffers()
	_make_fine_buffers()
	_fill_fine_pc(r)


func _make_coarse_pc() -> void:
	_coarse_pc = PackedByteArray()
	_coarse_pc.resize(16 * 4)
	_coarse_pc.encode_float(0, float(COARSE_N))
	_coarse_pc.encode_float(4, DT)
	_coarse_pc.encode_float(8, 0.0)          # t
	_coarse_pc.encode_float(12, PHI)
	_coarse_pc.encode_float(16, XI)
	_coarse_pc.encode_float(20, 0.0)         # eps2
	_coarse_pc.encode_float(24, 0.0)         # particle_N (no deposit)
	_coarse_pc.encode_float(28, 0.0)         # mode
	_coarse_pc.encode_float(32, 0.0)         # source_strength
	_coarse_pc.encode_float(36, 0.0)         # num_clusters
	_coarse_pc.encode_float(40, 0.0)         # gravity_mode
	_coarse_pc.encode_float(44, _ext_c.x)
	_coarse_pc.encode_float(48, _ext_c.y)
	_coarse_pc.encode_float(52, _ext_c.z)
	_coarse_pc.encode_float(56, 0.0)         # pass_sel (A)
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
	_fine_pc.encode_float(24, 0.25 * _ext_c.x)          # ext_fx
	_fine_pc.encode_float(28, 0.5 * _ext_c.y if _corner else _ext_c.y)  # ext_fy
	_fine_pc.encode_float(32, 0.125 * _ext_c.z if _corner else _ext_c.z) # ext_fz
	_fine_pc.encode_float(36, 0.0)                      # mode
	_fine_pc.encode_float(40, float(COARSE_N))
	_fine_pc.encode_float(44, _ext_c.x)
	_fine_pc.encode_float(48, _ext_c.y)
	_fine_pc.encode_float(52, _ext_c.z)
	_fine_pc.encode_float(56, 0.0)                      # x_off
	_fine_pc.encode_float(60, 0.0)                      # y_off
	_fine_pc.encode_float(64, 0.0)                      # z_off
	_fine_pc.encode_float(68, float(_padx))
	_fine_pc.encode_float(72, float(_pady))
	_fine_pc.encode_float(76, float(_padz))
	_fine_pc.encode_float(80, float(r))
	var hn_c := float(COARSE_N) * 0.5
	var h0_c := minf(minf(_ext_c.x, _ext_c.y), _ext_c.z) / hn_c
	_fine_pc.encode_float(84, h0_c)


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
		_uni(6, _sim._field_ey), _uni(7, _sim._field_ei),
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


## The coarse field IC: a Gaussian rho pulse (eps = ey - phi*ei = 0: ey =
## phi*p, ei = p) with the velocity from the DISCRETE forward projection:
## rho_dot_hat = -i*w(k)*rho_hat, w(k) = sqrt(-S(k)) with S = the 19-point
## anisotropic lap's symbol at the coarse geometry (the coarse shader's own
## weights). This is the exact forward eigenmode of the discrete operator —
## a single-c velocity (rho_dot = -c*rho') projects ~11% backward onto the
## dispersive spectrum (the ~88% floor measured with the naive IC).
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
	# the rho-mode field + its spectrum
	for i in range(n):
		for j in range(n):
			for k in range(n):
				var wx := (float(i) + 0.5) / float(n) * 2.0 - 1.0
				var wy := (float(j) + 0.5) / float(n) * 2.0 - 1.0
				var d := 0.0
				if _corner:
					d = ((wx - PULSE_X0) + (wy - PULSE_X0)) / sqrt(2.0)
				else:
					d = wx - PULSE_X0
				var p := PULSE_AMP * exp(-d * d / (PULSE_SIG * PULSE_SIG))
				var id := i + n * (j + n * k)
				ey[id] = PHI * p
				ei[id] = p
				re[id] = (1.0 + PHI) * p
	_fft3d(re, im, false)
	# the velocity spectrum: rho_dot_hat = -i*w(k)*rho_hat
	var sym := _lap_symbols()
	for i in range(n):
		var kx := TAU * float(i) / float(n)
		var kxs := kx
		if i > n / 2:
			kxs -= TAU   # the SIGNED frequency (the bin > N/2 is negative)
		for j in range(n):
			var ky := TAU * float(j) / float(n)
			var kys := ky
			if j > n / 2:
				kys -= TAU
			for k in range(n):
				var kz := TAU * float(k) / float(n)
				var s: float = sym["ax"] * (2.0 * cos(kx) - 2.0)
				s += sym["ay"] * (2.0 * cos(ky) - 2.0)
				s += sym["az"] * (2.0 * cos(kz) - 2.0)
				s += sym["bxy"] * (4.0 * cos(kx) * cos(ky) - 4.0)
				s += sym["bxz"] * (4.0 * cos(kx) * cos(kz) - 4.0)
				s += sym["byz"] * (4.0 * cos(ky) * cos(kz) - 4.0)
				# The forward-going dispersion is ODD in k: w(k) =
				# sign(k_forward) * sqrt(-S(k)). An EVEN w makes the
				# velocity spectrum anti-Hermitian and the real-space
				# rho_dot vanishes exactly (the FFT round-trip proved it).
				var w := sqrt(maxf(-s, 0.0))
				var kf := kxs + kys if _corner else kxs
				if kf < 0.0:
					w = -w
				var id := i + n * (j + n * k)
				var a := re[id]
				var b := im[id]
				re[id] = w * b          # re(-i*w*(a+ib)) = w*b
				im[id] = -w * a         # im(-i*w*(a+ib)) = -w*a
	_fft3d(re, im, true)
	# the velocities: vel.x = phi/(1+phi)*rho_dot, vel.y = 1/(1+phi)*rho_dot
	# (eps_dot = vel.x - phi*vel.y = 0 — the eps stays zero)
	var pf := 1.0 / (1.0 + PHI)
	for i in range(n * n * n):
		zv[i * 4] = PHI * pf * re[i]
		zv[i * 4 + 1] = pf * re[i]
	_rd.buffer_update(_sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())
	_rd.buffer_update(_sim._field_vel, 0, zv.size() * 4, zv.to_byte_array())


## The 19-point anisotropic lap weights at the COARSE geometry (the
## canonical formulas from cassi_two_fluid.glsl — the same weights the
## coarse shader applies).
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


## Separable 3D radix-2 FFT (the gate-iv's in-place 1D core, 64^3).
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
				# the x-line (j,k fixed): start = n*(j + n*k), stride 1
				i0 = n * i2
				stride = 1
			elif axis == 1:
				# the y-line (i,k fixed): start = i + n*n*k, stride n
				i0 = (i2 % n) + n * n * (i2 / n)
				stride = n
			else:
				# the z-line (i,j fixed): start = i + n*j, stride n*n
				i0 = (i2 % n) + n * (i2 / n)
				stride = n * n
			for t in range(n):
				line_r[t] = re[i0 + t * stride]
				line_i[t] = im[i0 + t * stride]
			_fft(line_r, line_i, invert)
			for t in range(n):
				re[i0 + t * stride] = line_r[t]
				im[i0 + t * stride] = line_i[t]


## In-place radix-2 complex FFT (the gate-iv core, N power of two).
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


## Zero the sim's mass density (the two-fluid source term = rho·0.001 must
## stay zero — the gate-vi wave is source-free).
func _zero_density() -> void:
	var n3 := COARSE_N * COARSE_N * COARSE_N
	var z := PackedFloat32Array()
	z.resize(n3)
	_rd.buffer_update(_sim._mass_density_buf, 0, n3 * 4, z.to_byte_array())


## One physics step: coarse A -> coarse B -> rim -> fine A -> fine B ->
## downsample (one compute list, barriers between — the global RD contract:
## no submit/sync; the readbacks at the measurement times flush the list).
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
	# (1) the coarse step (the sim's canonical two-fluid, passes A/B)
	rd.compute_list_bind_compute_pipeline(cl, _sim._two_fluid_pipe)
	rd.compute_list_bind_uniform_set(cl, _sim._us_two_0, 0)
	_coarse_pc.encode_float(56, 0.0)
	rd.compute_list_set_push_constant(cl, _coarse_pc, 64)
	rd.compute_list_dispatch(cl, wg_c, wg_c, wg_c)
	rd.compute_list_add_barrier(cl)
	_coarse_pc.encode_float(56, 1.0)
	rd.compute_list_set_push_constant(cl, _coarse_pc, 64)
	rd.compute_list_dispatch(cl, wg_c, wg_c, wg_c)
	rd.compute_list_add_barrier(cl)
	# (2) the rim: the coarse -> the fine shell
	rd.compute_list_bind_compute_pipeline(cl, _fine_pipe)
	rd.compute_list_bind_uniform_set(cl, _fine_set, 0)
	_fine_pc.encode_float(36, 0.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_px, wg_py, wg_pz)
	rd.compute_list_add_barrier(cl)
	# (3) the fine pass A
	_fine_pc.encode_float(36, 1.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_fx, wg_fy, wg_fz)
	rd.compute_list_add_barrier(cl)
	# (4) the fine pass B
	_fine_pc.encode_float(36, 2.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_fx, wg_fy, wg_fz)
	rd.compute_list_add_barrier(cl)
	# (5) the downsample: the fine -> the coarse slab
	_fine_pc.encode_float(36, 3.0)
	rd.compute_list_set_push_constant(cl, _fine_pc, 88)
	rd.compute_list_dispatch(cl, wg_ds, wg_dy, wg_dy)
	rd.compute_list_end()


## The Riemann-invariant measurement in the launch region: R_± = ρ̇ ∓ c·ρ'
## (ρ = ey+ei, ρ̇ = vel.x + vel.y, ρ' = the central difference along the
## wave's normal). E_forw = Σ R_+², E_back = Σ R_−² over the region.
func _measure() -> Dictionary:
	_s2_rhod = 0.0
	_s2_dpsi = 0.0
	_s2_cross = 0.0
	var n := COARSE_N
	var ey: PackedFloat32Array = _rd.buffer_get_data(_sim._field_ey, 0, n * n * n * 4).to_float32_array()
	var ei: PackedFloat32Array = _rd.buffer_get_data(_sim._field_ei, 0, n * n * n * 4).to_float32_array()
	var vel: PackedFloat32Array = _rd.buffer_get_data(_sim._field_vel, 0, n * n * n * 16).to_float32_array()
	var xlo := -0.60 if not _corner else -0.65
	var xhi := -0.30 if not _corner else -0.40
	var e_f := 0.0
	var e_b := 0.0
	for i in range(1, n - 1):
		var xn := (float(i) + 0.5) / float(n) * 2.0 - 1.0
		if xn < xlo or xn > xhi:
			continue
		for j in range(n):
			var yn := (float(j) + 0.5) / float(n) * 2.0 - 1.0
			if _corner and (yn < xlo or yn > xhi):
				continue
			for k in range(n):
				var id := i + n * (j + n * k)
				var rho := ey[id] + ei[id]
				var rhod := vel[id * 4] + vel[id * 4 + 1]
				var ip := id + 1
				var im := id - 1
				# the world-unit derivative: /(2*hx) — the invariants use the
				# world-unit speed c (the per-cell rho' would mismatch c).
				var hxw := 2.0 * _ext_c.x / float(n)
				var rho_x := (ey[ip] + ei[ip] - ey[im] - ei[im]) * 0.5 / hxw
				var dpsi := rho_x
				if _corner:
					var jp := i + n * ((j + 1) % n) + n * n * k
					var jm2 := i + n * ((j - 1 + n) % n) + n * n * k
					var rho_y := (ey[jp] + ei[jp] - ey[jm2] - ei[jm2]) * 0.5 / hxw
					dpsi = (rho_x + rho_y) / sqrt(2.0)
				# the invariants: R_+ = ρ̇ − c·ρ' (the +x-going), R_− = ρ̇ + c·ρ'
				var rf := rhod - C_WAVE * dpsi
				var rb := rhod + C_WAVE * dpsi
				e_f += rf * rf
				e_b += rb * rb
				_s2_rhod += rhod * rhod
				_s2_dpsi += dpsi * dpsi
				_s2_cross += rhod * dpsi
	return {"forw": e_f, "back": e_b}


func _snapshot() -> Dictionary:
	var n := COARSE_N
	return {
		"ey": _rd.buffer_get_data(_sim._field_ey, 0, n * n * n * 4).to_float32_array(),
		"ei": _rd.buffer_get_data(_sim._field_ei, 0, n * n * n * 4).to_float32_array(),
		"fine_ey": _rd.buffer_get_data(_b_fey, 0, _padx * _pady * _padz * 4).to_float32_array(),
	}


func _verdict() -> void:
	# the determinism rerun (arm 4 = the r=2 rerun): compare its snapshot
	# to the arm-1 snapshot.
	var det := _snapshot()
	var md := _max_diff(det["ey"], _run_ref["ey"])
	var mdf := _max_diff(det["fine_ey"], _run_ref["fine_ey"])
	print("[GateVI] determinism max-diff: coarse=%.6f fine=%.6f -> %s"
		% [md, mdf, "PASS" if (md == 0.0 and mdf == 0.0) else "FAIL"])
	if md != 0.0 or mdf != 0.0:
		_fail += 1
	print("[GateVI] ============ GATE-VI VERDICT ============")
	var cal: float = _arms_r[0]
	var ok := true
	for a in range(4):
		var tag := "r=1" if a == 0 else "r=2" if a == 1 else "r=4" if a == 2 else "corner"
		var dr: float = _arms_r[a] - cal
		var passes := dr <= R_CAL_TAIL
		if not passes:
			ok = false
		print("[GateVI] arm %-7s R=%.4f%%  R-R_cal=%.4f%%  (pin <= %.2f%%)  %s"
			% [tag, 100.0 * _arms_r[a], 100.0 * dr, 100.0 * R_CAL_TAIL,
			"PASS" if passes else "FAIL"])
	if _fail == 0 and ok:
		print("[GateVI] VERDICT: PASS — the coarse-fine interface transmits without reflection (R-R_cal <= 2%)")
	else:
		print("[GateVI] VERDICT: FAIL — %d failures" % _fail)
	get_tree().quit(0)


func _max_diff(a: PackedFloat32Array, b: PackedFloat32Array) -> float:
	var m := 0.0
	for i in range(mini(a.size(), b.size())):
		m = maxf(m, absf(a[i] - b[i]))
	return m
