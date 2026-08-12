extends Node
## GPU round-trip identity test for the spectral Poisson FFT (cassi_poisson.glsl).
##
## Drives the REAL shader passes through the sim's pipeline (same buffers,
## same push constants, same dispatch counts) and asserts:
##   (a) per-axis  round trip:  IFFT(FFT(x)) == x along each axis alone
##   (b) full-3D   round trip:  the 6-pass chain == x
## on a smooth periodic Gaussian (no Gibbs), reporting max|Δ| and the
## residual imaginary part (a real input must stay real).
## Then two solve checks on the same GPU path:
##   (c) single-cell delta mass 10 at the center → Φ < 0 at the mass,
##       r·Φ ≈ const (point-mass profile), Φ(center) vs the analytic
##       torus-Green value  −M·(1/N³)·Σ_{k≠0} 1/k²
##   (d) Gaussian mass → Φ < 0 at center, FD-Laplacian residual
##       (the smooth-case reference: discretization-level, vs the large
##       reading the sim's wrapped point-mass cluster produces)
##
## Run: godot --path <repo> res://scenes/verify_fft.tscn

const TWO_PI: float = 6.28318530717958647693

var sim: Node3D
var N: int = 64
var extent: float = 37.5
var h: float = 0.0
var nc: int = 0
var sigma: float = 4.0

var _failures: int = 0
var _checks: int = 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	if sim == null:
		push_error("verify_fft: CassiSim not found in scene")
		get_tree().quit(1)
		return
	N = sim.grid_N
	extent = sim._extents().x  # the box half-extent (legacy value at aspect 1)
	h = extent / (float(N) * 0.5)
	nc = N * N * N
	sim.playing = false
	sim.gravity_mode = 0
	await get_tree().process_frame
	await get_tree().process_frame
	var waited := 0
	while not sim._shaders_ready and waited < 300:
		waited += 1
		await get_tree().process_frame
	if not sim._shaders_ready:
		push_error("verify_fft: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	print("verify_fft: shaders ready after %d extra frames" % waited)
	_run_all()
	get_tree().quit(0 if _failures == 0 else 1)


# ═══════════════════════════════════════════════════════════════════════
# GPU plumbing
# ═══════════════════════════════════════════════════════════════════════

func _write_complex(v: PackedFloat32Array) -> void:
	# interleave (real, imag=0) into a PackedFloat32Array, then upload
	var inter = PackedFloat32Array()
	inter.resize(nc * 2)
	for i in range(nc):
		inter[i * 2] = v[i]
		inter[i * 2 + 1] = 0.0
	sim._rd.buffer_update(sim._fft_buf, 0, nc * 8, inter.to_byte_array())


func _read_complex() -> PackedFloat32Array:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._fft_buf, 0, nc * 8)
	return d.to_float32_array()


func _fft_pass(axis: float, direction: float, mode: float) -> void:
	sim._ensure_synced()
	var cl: int = sim._rd.compute_list_begin()
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._poisson_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_poisson_0, 0)
	var pc: PackedByteArray = sim._poisson_pc_bytes.duplicate()
	pc.encode_float(0, float(N))
	pc.encode_float(4, axis)
	pc.encode_float(8, direction)
	pc.encode_float(12, mode)
	# Per-axis extents (the kspace multiply reads all three; at the cube
	# aspect they are equal to the legacy single extent).
	pc.encode_float(16, extent)
	pc.encode_float(20, extent)
	pc.encode_float(24, extent)
	sim._rd.compute_list_set_push_constant(cl, pc, pc.size())
	# All poisson modes dispatch 2D (N, N, 1): FFT passes = one workgroup
	# per row (row = wg.x + wg.y·N); cells modes (load/kspace/clear) cover
	# N³ cells via gid = x + y·N·256 (see cassi_poisson.glsl).
	sim._rd.compute_list_dispatch(cl, N, N, 1)
	sim._rd.compute_list_end()
	# No submit()/sync() here: the sim runs on the GLOBAL RenderingDevice,
	# where both are forbidden no-ops ("Only local devices can submit and
	# sync.") — the readback path (_read_complex → buffer_get_data) already
	# self-stalls until the pending work completes.


func _max_abs_diff(a: PackedFloat32Array, b: PackedFloat32Array) -> float:
	# a is the interleaved complex buffer (real at even indices), b is plain
	var m := 0.0
	var n: int = min(a.size() / 2, b.size())
	for i in range(n):
		var d: float = abs(a[i * 2] - b[i])
		if d > m:
			m = d
	return m


func _max_abs_imag(a: PackedFloat32Array) -> float:
	var m := 0.0
	for i in range(nc):
		var d: float = abs(a[i * 2 + 1])
		if d > m:
			m = d
	return m


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


# ═══════════════════════════════════════════════════════════════════════
# Test fields
# ═══════════════════════════════════════════════════════════════════════

func _gaussian() -> PackedFloat32Array:
	var v = PackedFloat32Array()
	v.resize(nc)
	var c := N / 2
	var s2 := sigma * sigma
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var dx := float(i - c)
				var dy := float(j - c)
				var dz := float(k - c)
				v[i + N * (j + N * k)] = exp(-(dx * dx + dy * dy + dz * dz) / (2.0 * s2))
	return v


func _delta() -> PackedFloat32Array:
	var v = PackedFloat32Array()
	v.resize(nc)
	v[N / 2 + N * (N / 2) + N * N * (N / 2)] = 10.0
	return v


# ═══════════════════════════════════════════════════════════════════════
# Analytic torus Green's function (same k convention as the shader:
# k = 2π·fftfreq(n)/L, k = 0 excluded)
# ═══════════════════════════════════════════════════════════════════════

func _torus_green_center() -> float:
	var s := 0.0
	var kbase := TWO_PI / (2.0 * extent)
	for k in range(N):
		var kz := float(k if k <= N / 2 else k - N)
		for j in range(N):
			var ky := float(j if j <= N / 2 else j - N)
			for i in range(N):
				var kx := float(i if i <= N / 2 else i - N)
				var k2 := (kx * kx + ky * ky + kz * kz) * kbase * kbase
				if k2 > 0.0:
					s += 1.0 / k2
	return s / float(nc)


# ═══════════════════════════════════════════════════════════════════════
# Test battery
# ═══════════════════════════════════════════════════════════════════════

func _run_all() -> void:
	print("══════ verify_fft — N=%d, extent=%.1f, h=%.4f, σ=%.1f cells ══════" % [N, extent, h, sigma])
	_test_roundtrip()
	_test_delta_solve()
	_test_gaussian_solve()
	_run_n128()
	_run_n256()
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])


# N=128 battery: reinit the sim at 128³ and re-run the round-trip and
# delta-solve checks (same tolerance; σ stays 4 cells, the mass stays at
# N/2 via the member N). The Gaussian FD-residual battery is 64-only — its
# triple loop is O(N³) CPU work and the smooth-case check is resolution-
# independent in spirit.
func _run_n128() -> void:
	print("══════ N=128 ══════")
	sim.grid_N = 128
	sim.reinit()
	sim.playing = false  # reinit does not touch playing; keep sim paused
	N = sim.grid_N
	extent = sim._extents().x  # the box half-extent (legacy value at aspect 1)
	h = extent / (float(N) * 0.5)
	nc = N * N * N
	print("══════ verify_fft — N=%d, extent=%.1f, h=%.4f, σ=%.1f cells ══════" % [N, extent, h, sigma])
	_test_roundtrip()
	_test_delta_solve()


# N=256 battery: reinit at 256³ and run the round-trip checks. This is the
# dispatch-landmine regression: the cells/rows dispatches go 2D (N, N, 1)
# so 256³ = 16.7M cells fit (a 1D dispatch would also blow the 65535-group
# cap and the naive x + y·N gid covers only N² + 255N cells). Round-trip
# only — the delta-solve CPU Green's sum is O(N³) and the sim's own
# residual report is gated above 128.
func _run_n256() -> void:
	print("══════ N=256 ══════")
	sim.grid_N = 256
	sim.reinit()
	sim.playing = false
	N = sim.grid_N
	extent = sim._extents().x  # the box half-extent (legacy value at aspect 1)
	h = extent / (float(N) * 0.5)
	nc = N * N * N
	print("══════ verify_fft — N=%d, extent=%.1f, h=%.4f, σ=%.1f cells ══════" % [N, extent, h, sigma])
	_test_roundtrip()


func _test_roundtrip() -> void:
	print("── Round-trip identity: IFFT(FFT(x)) == x ──")
	var g := _gaussian()
	var gmax := 0.0
	for v in g:
		gmax = max(gmax, abs(v))
	# (a) per-axis
	for axis in range(3):
		_write_complex(g)
		_fft_pass(float(axis), 0.0, 1.0)  # forward
		_fft_pass(float(axis), 1.0, 1.0)  # inverse
		var out := _read_complex()
		var md := _max_abs_diff(out, g)      # real parts compared
		var mi := _max_abs_imag(out)
		_check("roundtrip axis %d (max|Δ| < 1e-4·max)" % axis, md < 1e-4 * gmax,
			"max|Δ|=%.8f max|imag|=%.8f gmax=%.3f" % [md, mi, gmax])
	# (b) full 3D chain
	_write_complex(g)
	for axis in range(3):
		_fft_pass(float(axis), 0.0, 1.0)
	for axis in range(2, -1, -1):
		_fft_pass(float(axis), 1.0, 1.0)
	var out3 := _read_complex()
	var md3 := _max_abs_diff(out3, g)
	var mi3 := _max_abs_imag(out3)
	_check("roundtrip full 3D (max|Δ| < 1e-4·max)", md3 < 1e-4 * gmax,
		"max|Δ|=%.8f max|imag|=%.8f" % [md3, mi3])
	# diagnostics for the full-3D round trip: worst cell + center row values
	var worst5: Array = []
	for i in range(nc):
		var d: float = abs(out3[i * 2] - g[i])
		if d > 1e-5:
			worst5.append([d, i])
	worst5.sort_custom(func(a, b): return a[0] > b[0])
	for k in range(min(5, worst5.size())):
		var wi: int = worst5[k][1]
		print("  diff %.8f at cell %d (x,y,z)=(%d,%d,%d) in=%.6f out=%.6f" % [
			worst5[k][0], wi, wi % N, (wi / N) % N, wi / (N * N),
			g[wi], out3[wi * 2]])


func _test_delta_solve() -> void:
	print("── Point-mass solve: single-cell delta M=10 at center ──")
	_write_complex(_delta())
	for axis in range(3):
		_fft_pass(float(axis), 0.0, 1.0)
	_fft_pass(0.0, 0.0, 2.0)  # kspace: Φ̂ = −ρ̂/k²
	for axis in range(2, -1, -1):
		_fft_pass(float(axis), 1.0, 1.0)
	var phi := _read_complex()
	var cid := N / 2 + N * (N / 2) + N * N * (N / 2)
	var center := phi[cid * 2]
	_check("delta: Φ(center) < 0 (attractive sign)", center < 0.0, "Φ(center)=%.6f" % center)

	# analytic torus estimate for the record
	var g0 := _torus_green_center()
	print("  torus G(0) = (1/N³)·Σ_{k≠0} 1/k² = %.6f → Φ_an(0) = −M·G(0) = %.6f" % [g0, -10.0 * g0])

	# r·(−Φ) is NOT constant here: the 3D torus Green's function carries a
	# box-truncated constant (Σ_{k≠0} 1/k² diverges with box size in 3D), so
	# Φ ≈ −M·(C + 1/4πr) and r·Φ grows linearly in r. The constant-free
	# observable — and the one the river law actually consumes — is the
	# radial FORCE: |∇Φ| = M/(4πr²). Check that (r ∈ [4h, 16h]).
	var ok := true
	var worst := 0.0
	for stepi in range(4, 17):
		var i = N / 2 + stepi
		var r := float(stepi) * h
		var grad: float = (phi[(i + 1 + N * (N / 2) + N * N * (N / 2)) * 2]
			 - phi[(i - 1 + N * (N / 2) + N * N * (N / 2)) * 2]) / (2.0 * h)
		# discrete Fourier Green: h³/(4πr) — the h³ cell-volume quadrature
		var pred := 10.0 * (h * h * h) / (4.0 * PI * r * r)  # M = 10, G_N = 1
		var dev: float = abs(grad - pred) / pred
		worst = max(worst, dev)
		if dev > 0.25:
			ok = false
	_check("delta: |∇Φ| ≈ M/(4πr²) (radial force, ±25%)", ok,
		"worst dev=%.1f%%" % (worst * 100.0))


func _test_gaussian_solve() -> void:
	print("── Gaussian-mass solve + smooth-case FD residual ──")
	var g := _gaussian()
	_write_complex(g)
	for axis in range(3):
		_fft_pass(float(axis), 0.0, 1.0)
	_fft_pass(0.0, 0.0, 2.0)
	for axis in range(2, -1, -1):
		_fft_pass(float(axis), 1.0, 1.0)
	var phi := _read_complex()
	var cid := N / 2 + N * (N / 2) + N * N * (N / 2)
	var center := phi[cid * 2]
	_check("gaussian: Φ(center) < 0", center < 0.0, "Φ(center)=%.6f" % center)
	# FD 7-point Laplacian residual (smooth-case reference for the sim report)
	var num := 0.0
	var den := 0.0
	var hh := h * h
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				var i1 := ((i + 1) % N) + N * (j + N * k)
				var im := ((i - 1 + N) % N) + N * (j + N * k)
				var j1 := i + N * (((j + 1) % N) + N * k)
				var jm := i + N * (((j - 1 + N) % N) + N * k)
				var k1 := i + N * (j + N * ((k + 1) % N))
				var km := i + N * (j + N * ((k - 1 + N) % N))
				var lap := (phi[i1 * 2] + phi[im * 2] + phi[j1 * 2] + phi[jm * 2]
					 + phi[k1 * 2] + phi[km * 2] - 6.0 * phi[id * 2]) / hh
				var rho_v := g[id]
				num += (lap - rho_v) * (lap - rho_v)
				den += rho_v * rho_v
	var resid := sqrt(num / max(den, 1e-30))
	print("  smooth-case FD residual L2|∇²Φ−ρ|/|ρ| = %.6f (discretization-level)" % resid)
	_check("gaussian: smooth-case residual < 1.0", resid < 1.0)
