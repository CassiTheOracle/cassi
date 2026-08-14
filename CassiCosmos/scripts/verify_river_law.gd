extends Node
## Synthetic verification of the river-law gravity upgrade (cassi_sim.gd +
## cassi_nbody_gravity.glsl + cassi_poisson.glsl).
##
## Runs the sim with N_particles=1 on a 64³ grid and asserts:
##   (i)   q → 0 limit: the river acceleration ≈ −(π/ρ)·∇Φ (Newtonian sector)
##   (ii)  single point mass: radial profile vs the point-mass formula
##   (iii) the mode toggle switches BOTH terms (river chord gradient vs the
##         legacy ∇q_s heuristic), each matching its own formula
##   (iv)  no NaN/Inf over 30 steps
##   (v)   reinit() keeps working (stale uniform-set regression)
## plus the Poisson solve checks (k=0 nulled, FD-Laplacian residual, r·Φ
## profile) reported for the record.
##
## Estimator note (2026-08-09): the river-arm expected values are computed
## with the shader's cell-centered gradient estimator — S = g·Φ built per
## cell, central differences, sampled at the probe (see _expected_river).
## The old per-particle estimator (central difference of trilinear
## samples) is ALGEBRAICALLY IDENTICAL to the trilinear cell-centered
## interpolation for any fixed S field (verified to 2e-16); the 0.117
## toggle mismatch in the earlier reverted stretch was a dispatch bug
## (skipped gradient pass), not an estimator difference.
##
## Run: godot --path <repo> res://scenes/verify_river_law.tscn

const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const PHI_INV3: float = (PHI - 1.0) / (PHI + 1.0)
const PI_CLAMP_MAX: float = 0.72
const M2Q: float = 0.01
const G_N: float = 1.0

var sim: Node3D
var N: int = 64
var extent: float = 37.5      # cluster_radius(25) * 1.5 — same as the sim's bh[2].y
var h: float = extent / 32.0  # cell size (hn = N/2)
var nc: int = 0

var _failures: int = 0
var _checks: int = 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")  # sibling node in the verify scene
	if sim == null:
		push_error("verify_river_law: CassiSim not found in scene")
		get_tree().quit(1)
		return
	# PIN the grid river-law battery against the campaign defaults
	# (meshless/tree/φ-aspect/dual now default on): the law's trace
	# gates run the CUBE single-lattice spectral-Poisson river chain.
	# Set before the extent read; reinit after shaders settle.
	sim.meshless_mode = false
	sim.meshless_gravity = false
	sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	sim.dual_grid = false
	N = sim.grid_N
	extent = sim._extents().x  # the box half-extent (legacy value at aspect 1)
	h = extent / (float(N) * 0.5)
	nc = N * N * N
	sim.playing = false
	sim.gravity_mode = 0  # RIVER
	# Let the sim's _ready finish and one frame pass
	await get_tree().process_frame
	await get_tree().process_frame
	# First-run import race: wait (up to 300 frames) for every shader to compile
	var waited := 0
	while not sim._shaders_ready and waited < 300:
		waited += 1
		await get_tree().process_frame
	if not sim._shaders_ready:
		push_error("verify_river_law: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	print("verify_river_law: shaders ready after %d extra frames" % waited)
	sim.reinit()  # re-materialize the cube grid / single-lattice / meshless-off state
	sim.playing = false
	_run_all()
	get_tree().quit(0 if _failures == 0 else 1)


# ═══════════════════════════════════════════════════════════════════════
# Field/buffer helpers
# ═══════════════════════════════════════════════════════════════════════

func _write_fields(ey: PackedFloat32Array, ei: PackedFloat32Array) -> void:
	sim._rd.buffer_update(sim._field_ey, 0, nc * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, nc * 4, ei.to_byte_array())
	# Keep field_q consistent for the legacy heuristic sampler (qv = ey²+ei²)
	var q = PackedFloat32Array()
	q.resize(nc)
	for i in range(nc):
		q[i] = ey[i] * ey[i] + ei[i] * ei[i]
	sim._rd.buffer_update(sim._field_q, 0, nc * 4, q.to_byte_array())


func _set_particle(pos3: Vector3, mass: float) -> void:
	# particle 1 gets ZERO mass at the same spot: no deposit, no force,
	# keeps the buffers well-formed with N_particles = 2
	var p = PackedFloat32Array([pos3.x, pos3.y, pos3.z, mass,
		pos3.x, pos3.y, pos3.z, 0.0])
	var v = PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	sim._rd.buffer_update(sim._pos_buf, 0, 32, p.to_byte_array())
	sim._rd.buffer_update(sim._vel_buf, 0, 32, v.to_byte_array())


# Two-particle setup: particle 0 = the MASS (deposited into ρ), particle 1 =
# the PROBE (tiny mass 1e-4 — its own well is negligible). A single particle
# both sources the potential and sits at its own well's minimum, where ∇Φ ≈ 0
# and the self-force vanishes — the force tests need a separate probe.
func _set_two(mass_pos: Vector3, probe_pos: Vector3) -> void:
	var p = PackedFloat32Array([mass_pos.x, mass_pos.y, mass_pos.z, 10.0,
		probe_pos.x, probe_pos.y, probe_pos.z, 1e-4])
	var v = PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	sim._rd.buffer_update(sim._pos_buf, 0, 32, p.to_byte_array())
	sim._rd.buffer_update(sim._vel_buf, 0, 32, v.to_byte_array())


func _read_phi() -> PackedFloat32Array:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._fft_buf, 0, nc * 8)
	var f = d.to_float32_array()
	var phi = PackedFloat32Array()
	phi.resize(nc)
	for i in range(nc):
		phi[i] = f[i * 2]  # real part
	return phi


func _read_rho() -> PackedFloat32Array:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._mass_density_buf, 0, nc * 4)
	return d.to_float32_array()


func _read_acc() -> Vector3:
	sim._ensure_synced()
	# particle 1 = the PROBE (particle 0 is the deposited mass; its acc is
	# ~0 at its own well's minimum)
	var d = sim._rd.buffer_get_data(sim._acc_buf, 16, 16)
	var a = d.to_float32_array()
	return Vector3(a[0], a[1], a[2])


# ═══════════════════════════════════════════════════════════════════════
# Exact replication of the shader math (float64, same expressions)
# ═══════════════════════════════════════════════════════════════════════

func _tri(field: PackedFloat32Array, wp: Vector3) -> float:
	var hn := float(N) * 0.5
	var gc: Vector3 = wp * (hn / extent) + Vector3(hn, hn, hn)
	var i0 := int(floor(gc.x))
	var j0 := int(floor(gc.y))
	var k0 := int(floor(gc.z))
	var fx := gc.x - float(i0)
	var fy := gc.y - float(j0)
	var fz := gc.z - float(k0)
	i0 = ((i0 % N) + N) % N
	j0 = ((j0 % N) + N) % N
	k0 = ((k0 % N) + N) % N
	var i1 := (i0 + 1) % N
	var j1 := (j0 + 1) % N
	var k1 := (k0 + 1) % N
	var idx: Callable = func(ix: int, jx: int, kx: int) -> int:
		return ix + N * (jx + N * kx)
	var v000: float = field[idx.call(i0, j0, k0)]
	var v100: float = field[idx.call(i1, j0, k0)]
	var v010: float = field[idx.call(i0, j1, k0)]
	var v110: float = field[idx.call(i1, j1, k0)]
	var v001: float = field[idx.call(i0, j0, k1)]
	var v101: float = field[idx.call(i1, j0, k1)]
	var v011: float = field[idx.call(i0, j1, k1)]
	var v111: float = field[idx.call(i1, j1, k1)]
	var q0: float = lerpf(lerpf(v000, v100, fx), lerpf(v010, v110, fx), fy)
	var q1: float = lerpf(lerpf(v001, v101, fx), lerpf(v011, v111, fx), fy)
	return lerpf(q0, q1, fz)


func _clamp_pi(pi_raw: float, rho_f: float) -> float:
	if rho_f < 1e-6:
		return 0.0
	var p := pi_raw / rho_f
	if p > PI_CLAMP_MAX:
		return PI_CLAMP_MAX
	if p < 0.0:
		return 0.0
	return p


# ESTIMATOR (2026-08-09 upgrade): the river-arm expected values use the
# SAME estimator as the shader's new gradient-field pass — build
# S = g·Φ at CELL CENTERS from cell values (g from the law's q:
# ρ = EY+EI, ε = EY−φ·EI), central-difference the gradient on the grid
# (periodic), and trilinearly interpolate it at the probe — then
# a = −G_N·(π/ρ)·∇S.
# ESTIMATOR EQUIVALENCE (verified): the OLD estimator — central
# difference of trilinear samples of S at p ± h·ê — is algebraically
# IDENTICAL to the trilinear cell-centered-gradient interpolation for
# any fixed S field (both blend the two adjacent cells' piecewise-
# constant trilinear gradients with the same weights; verified to 2e-16
# on random and 1/r fields). The 0.117 toggle mismatch in the earlier
# reverted stretch was a DISPATCH bug (missing descriptor-set binding →
# the gradient pass was skipped → zero/stale gradients), not an
# estimator difference — the toggle check now reads rel ≈ 1e-6. This is
# a documented estimator upgrade (deterministic consistency with the
# cell fields + ~7× fewer per-particle evaluations), NOT a tolerance
# change — every threshold below is untouched.

# Cell-centered central-difference gradient of a scalar field (periodic
# wraps), sampled trilinearly at wp — exactly the shader's grad_main +
# tri_grad (2h normalization, same wrap).
# NOTE (2026-08-09, gated experiment): a separable Catmull-Rom tricubic
# sampler was measured as the anisotropy lever and REVERTED — it did not
# reduce the ring bias (1.0482/1.1445 vs the trilinear 1.0441/1.1293 at
# r=8h/4h): the anisotropy is the discrete torus-Green field's cubic
# structure, not the sampler.
func _cell_grad_tri(field: PackedFloat32Array, wp: Vector3) -> Vector3:
	var gx = PackedFloat32Array(); gx.resize(nc)
	var gy = PackedFloat32Array(); gy.resize(nc)
	var gz = PackedFloat32Array(); gz.resize(nc)
	var inv2h := 1.0 / (2.0 * h)
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				var ip := ((i + 1) % N) + N * (j + N * k)
				var im := ((i - 1 + N) % N) + N * (j + N * k)
				var jp := i + N * (((j + 1) % N) + N * k)
				var jm := i + N * (((j - 1 + N) % N) + N * k)
				var kp := i + N * (j + N * ((k + 1) % N))
				var km := i + N * (j + N * ((k - 1 + N) % N))
				gx[id] = (field[ip] - field[im]) * inv2h
				gy[id] = (field[jp] - field[jm]) * inv2h
				gz[id] = (field[kp] - field[km]) * inv2h
	return Vector3(_tri(gx, wp), _tri(gy, wp), _tri(gz, wp))


# River-mode expected acceleration: −G_N·(π/ρ)·∇(g·Φ), full chord gradient
func _expected_river(ey: PackedFloat32Array, ei: PackedFloat32Array,
		phi: PackedFloat32Array, wp: Vector3) -> Vector3:
	# S = g·Φ per cell — g from the law's q at CELL values (no
	# interpolation), Φ from the solved buffer; the whole product, never
	# hand-split, matching the shader's chord_s_at.
	var s = PackedFloat32Array(); s.resize(nc)
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				var eyv := ey[id]
				var eiv := ei[id]
				var rho_f := eyv + eiv
				var eps := eyv - PHI * eiv
				var qq := (rho_f * rho_f) / (rho_f * rho_f + PHI_INV2 + eps * eps)
				s[id] = (1.0 + (sim.xi - 1.0) * qq) * phi[id]
	var grad := _cell_grad_tri(s, wp)
	# π/ρ at wp — same trilinear sampler + clamp as the shader's chord_g_at
	var eyv2 := _tri(ey, wp)
	var eiv2 := _tri(ei, wp)
	var pi_over_rho := _clamp_pi(eyv2 - eiv2, eyv2 + eiv2)
	return -G_N * pi_over_rho * grad


# Legacy heuristic expected: G_N·clamp(φ⁻³+0.7q_s,0,0.72)·∇q_s, q_s = qv+0.01ρ
func _expected_heuristic(qv: PackedFloat32Array, rho: PackedFloat32Array, wp: Vector3) -> Vector3:
	var q_s := _tri(qv, wp) + M2Q * _tri(rho, wp)
	var pi_over_rho := clampf(PHI_INV3 + 0.7 * q_s, 0.0, PI_CLAMP_MAX)
	var hn := float(N) * 0.5
	var gc: Vector3 = wp * (hn / extent) + Vector3(hn, hn, hn)
	var i0 := int(floor(gc.x))
	var j0 := int(floor(gc.y))
	var k0 := int(floor(gc.z))
	var fx := gc.x - float(i0)
	var fy := gc.y - float(j0)
	var fz := gc.z - float(k0)
	i0 = ((i0 % N) + N) % N
	j0 = ((j0 % N) + N) % N
	k0 = ((k0 % N) + N) % N
	var i1 := (i0 + 1) % N
	var j1 := (j0 + 1) % N
	var k1 := (k0 + 1) % N
	var idx: Callable = func(ix: int, jx: int, kx: int) -> int:
		return ix + N * (jx + N * kx)
	var qs_at: Callable = func(ix: int, jx: int, kx: int) -> float:
		return qv[idx.call(ix, jx, kx)] + M2Q * rho[idx.call(ix, jx, kx)]
	var c000: float = qs_at.call(i0, j0, k0)
	var c100: float = qs_at.call(i1, j0, k0)
	var c010: float = qs_at.call(i0, j1, k0)
	var c110: float = qs_at.call(i1, j1, k0)
	var c001: float = qs_at.call(i0, j0, k1)
	var c101: float = qs_at.call(i1, j0, k1)
	var c011: float = qs_at.call(i0, j1, k1)
	var c111: float = qs_at.call(i1, j1, k1)
	var qx_l := lerpf(lerpf(c000, c001, fz), lerpf(c010, c011, fz), fy)
	var qx_r := lerpf(lerpf(c100, c101, fz), lerpf(c110, c111, fz), fy)
	var qy_l := lerpf(lerpf(c000, c100, fx), lerpf(c001, c101, fx), fz)
	var qy_r := lerpf(lerpf(c010, c110, fx), lerpf(c011, c111, fx), fz)
	var qz_l := lerpf(lerpf(c000, c100, fx), lerpf(c010, c110, fx), fy)
	var qz_r := lerpf(lerpf(c001, c101, fx), lerpf(c011, c111, fx), fy)
	var grad := Vector3(qx_r - qx_l, qy_r - qy_l, qz_r - qz_l) / h
	return G_N * pi_over_rho * grad


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


# ═══════════════════════════════════════════════════════════════════════
# Test battery
# ═══════════════════════════════════════════════════════════════════════

func _run_all() -> void:
	print("══════ verify_river_law — N=%d, extent=%.1f, h=%.4f ══════" % [N, extent, h])
	_test_poisson()
	_test_q0_limit()
	_test_radial_profile()
	_test_mode_toggle()
	_test_nan_steps()
	_test_reinit()
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])


func _test_poisson() -> void:
	print("── Poisson solve checks ──")
	# Single mass at origin, tiny uniform fluid (q ≈ 0), river mode
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	for i in range(nc):
		ey[i] = 0.00012
		ei[i] = 0.00010
	_write_fields(ey, ei)
	_set_particle(Vector3.ZERO, 10.0)
	sim._physics_step()
	var phi := _read_phi()
	var rho := _read_rho()

	# (a) k = 0 nulled: mean of Φ ≈ 0
	var mean = 0.0
	var peak = 0.0
	for v in phi:
		mean += v
		peak = max(peak, abs(v))
	mean /= float(nc)
	_check("poisson: k=0 nulled (mean Φ ≈ 0)", abs(mean) < 1e-6 * max(peak, 1e-30),
		"mean=%.6f peak=%.6f" % [mean, peak])

	# (b) FD Laplacian residual — report (discretization-level by design)
	var num = 0.0
	var den = 0.0
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id = i + N * (j + N * k)
				var i1 = ((i + 1) % N) + N * (j + N * k)
				var im = ((i - 1 + N) % N) + N * (j + N * k)
				var j1 = i + N * (((j + 1) % N) + N * k)
				var jm = i + N * (((j - 1 + N) % N) + N * k)
				var k1 = i + N * (j + N * ((k + 1) % N))
				var km = i + N * (j + N * ((k - 1 + N) % N))
				var lap = (phi[i1] + phi[im] + phi[j1] + phi[jm] + phi[k1] + phi[km] - 6.0 * phi[id]) / (h * h)
				var rv = rho[id]
				num += (lap - rv) * (lap - rv)
				den += rv * rv
	var resid = sqrt(num / max(den, 1e-30))
	print("  FD-Laplacian residual L2|∇²Φ−ρ|/|ρ| = %.6f (discretization-level; spectral solve is exact in k-space)" % resid)
	_check("poisson: solve ran and ρ deposited", den > 0.0, "total |ρ|²=%.6f" % den)
	_check("poisson: Φ negative near mass (sign)", phi[N / 2 + N * (N / 2) + N * N * (N / 2)] < 0.0,
		"Φ(center)=%.6f" % phi[N / 2 + N * (N / 2) + N * N * (N / 2)])
	# profile along +x for the record
	var prof := ""
	for stepi in range(0, 24):
		var i = N / 2 + stepi
		prof += "%.3f " % phi[i + N * (N / 2) + N * N * (N / 2)]
	print("  Φ(+x profile, r=0..%.1f): %s" % [23.0 * h, prof])

	# (c) radial FORCE profile: |∇Φ| ≈ M/(4πr²) along +x, r ∈ [4h, 16h].
	# (r·(−Φ) is NOT constant: the 3D torus Green's function carries a
	# box-truncated constant — Σ_{k≠0} 1/k² diverges with box size in 3D —
	# so Φ ≈ −M·(C + 1/4πr); the constant-free gradient is the observable
	# the river law actually consumes.)
	var ok = true
	var worst = 0.0
	var ci = N / 2
	var cj = N / 2
	var ck = N / 2
	for stepi in range(4, 17):
		var i = ci + stepi
		var r = float(stepi) * h
		var grad = (phi[(i + 1) + N * (cj + N * ck)] - phi[(i - 1) + N * (cj + N * ck)]) / (2.0 * h)
		var pred = 10.0 * (h * h * h) / (4.0 * PI * r * r)  # M = 10, G_N = 1, ×h³ quadrature
		var dev = abs(grad - pred) / pred
		worst = max(worst, dev)
		if dev > 0.25:
			ok = false
	_check("poisson: |∇Φ| ≈ M/(4πr²) (radial force, ±25%)", ok,
		"worst dev=%.1f%%" % (worst * 100.0))


func _test_q0_limit() -> void:
	print("── (i) q → 0 limit: a ≈ −(π/ρ)·∇Φ ──")
	# Fluid tiny and uniform → q ≈ 1e-7, g ≈ 1. Mass at the origin,
	# probe (mass 1e-4) at (8,0,0) — the probe's own well is negligible.
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	for i in range(nc):
		ey[i] = 0.00012
		ei[i] = 0.00010
	_write_fields(ey, ei)
	var wp := Vector3(8.0, 0.0, 0.0)
	_set_two(Vector3.ZERO, wp)
	sim.gravity_mode = 0
	sim._physics_step()
	var phi := _read_phi()
	var acc := _read_acc()

	# q at the probe (from the crafted fields)
	var eyv := _tri(ey, wp)
	var eiv := _tri(ei, wp)
	var q := (eyv + eiv) * (eyv + eiv) / ((eyv + eiv) * (eyv + eiv) + PHI_INV2 + (eyv - PHI * eiv) * (eyv - PHI * eiv))
	_check("q0: q ≈ 0 with tiny fluid", q < 1e-5, "q=%.6f" % q)

	# Newtonian-sector reference: −(π/ρ)·∇Φ — cell-centered gradient of Φ
	# (same estimator upgrade as the full river arm)
	var pi_over_rho := _clamp_pi(eyv - eiv, eyv + eiv)
	var grad_phi := _cell_grad_tri(phi, wp)
	var expected_newton := -G_N * pi_over_rho * grad_phi
	var rel = (acc - expected_newton).length() / max(expected_newton.length(), 1e-30)
	_check("q0: shader acc ≈ −(π/ρ)∇Φ (5%)", rel < 0.05,
		"rel=%.4f acc=%s expected=%s" % [rel, acc, expected_newton])
	# Full river-law expected (includes the tiny g correction) — must match tighter
	var expected_river := _expected_river(ey, ei, phi, wp)
	var rel2 = (acc - expected_river).length() / max(expected_river.length(), 1e-30)
	_check("q0: shader acc matches full chord formula (2%)", rel2 < 0.02,
		"rel=%.4f acc=%s river=%s" % [rel2, acc, expected_river])
	# Attraction sign: force points toward the mass at origin
	_check("q0: force is attractive (a·r̂ < 0)", acc.dot(wp.normalized()) < 0.0,
		"a·r̂=%.4f" % acc.dot(wp.normalized()))


func _test_radial_profile() -> void:
	print("── (ii) single-mass radial profile vs point-mass formula ──")
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	for i in range(nc):
		ey[i] = 0.00012
		ei[i] = 0.00010
	_write_fields(ey, ei)
	# r ∈ [3h, 12h]: beyond 12h the torus image forces exceed the tolerance
	for rr in [3.0, 6.0, 12.0]:
		var r: float = rr * h
		_set_two(Vector3.ZERO, Vector3(r, 0.0, 0.0))
		sim._physics_step()
		var acc := _read_acc()
		var mag := acc.length()
		# Point-mass prediction: |a| = (π/ρ)·g·M·h³/(4πr²), G_N = 1, M = 10.
		# h³ = (L/N)³ is the cell-volume quadrature of the discrete Fourier
		# Green's function: the k-space solve's Green is h³/(4πr) (the
		# discrete delta has unit amplitude per cell, so the k-sum carries
		# the h³ weight) — the sim's field-gravity scale is G_N·h³.
		var eyv := _tri(ey, Vector3(r, 0, 0))
		var eiv := _tri(ei, Vector3(r, 0, 0))
		var q := (eyv + eiv) * (eyv + eiv) / ((eyv + eiv) * (eyv + eiv) + PHI_INV2 + (eyv - PHI * eiv) * (eyv - PHI * eiv))
		var g: float = 1.0 + (sim.xi - 1.0) * q
		var pi_over_rho := _clamp_pi(eyv - eiv, eyv + eiv)
		var pred: float = pi_over_rho * g * 10.0 * (h * h * h) / (4.0 * PI * r * r)
		var tol := 0.40 if rr == 3.0 else 0.25
		var ok = abs(mag - pred) / pred < tol and acc.x < 0.0  # inward
		_check("profile r=%.1f (%.0f%% tol)" % [r, tol * 100.0], ok,
			"|a|=%.6f pred=%.6f ratio=%.3f" % [mag, pred, mag / pred])


func _test_mode_toggle() -> void:
	print("── (iii) mode toggle switches both terms ──")
	# Fluid with a spatial gradient → q and q_s gradients both nonzero
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	var qv = PackedFloat32Array(); qv.resize(nc)
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id = i + N * (j + N * k)
				var x = (float(i) / float(N) - 0.5) * 2.0 * extent
				ey[id] = 0.00012 + 0.05 * (x / extent + 1.0) * 0.5
				ei[id] = 0.00010
				qv[id] = ey[id] * ey[id] + ei[id] * ei[id]
	_write_fields(ey, ei)
	var wp := Vector3(5.0, 2.0, -3.0)
	_set_particle(wp, 10.0)

	# River arm
	sim.gravity_mode = 0
	sim._physics_step()
	var phi := _read_phi()
	var rho := _read_rho()
	var acc_r := _read_acc()
	var exp_r := _expected_river(ey, ei, phi, wp)
	var rel_r = (acc_r - exp_r).length() / max(exp_r.length(), 1e-30)
	_check("toggle: river term matches chord-gradient formula (5%)", rel_r < 0.05,
		"rel=%.4f acc=%s exp=%s" % [rel_r, acc_r, exp_r])

	# Heuristic arm
	sim.gravity_mode = 1
	sim._physics_step()
	var acc_h := _read_acc()
	var exp_h := _expected_heuristic(qv, rho, wp)
	var rel_h = (acc_h - exp_h).length() / max(exp_h.length(), 1e-30)
	_check("toggle: heuristic term matches legacy ∇q_s formula (5%)", rel_h < 0.05,
		"rel=%.4f acc=%s exp=%s" % [rel_h, acc_h, exp_h])

	# The two terms are genuinely different forces
	var diff = (acc_r - acc_h).length()
	var scale = max(acc_r.length(), acc_h.length())
	_check("toggle: river ≠ heuristic (different terms)", diff > 0.5 * scale,
		"|Δ|=%.6f scale=%.6f" % [diff, scale])

	sim.gravity_mode = 0  # back to default for the remaining tests


func _test_nan_steps() -> void:
	print("── (iv) 30-step NaN/Inf scan (river mode) ──")
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	for i in range(nc):
		ey[i] = 0.00012
		ei[i] = 0.00010
	_write_fields(ey, ei)
	_set_two(Vector3.ZERO, Vector3(8.0, 0.0, 0.0))
	var bad = false
	for s in range(30):
		sim._physics_step()
		if s % 5 == 0 or s == 29:
			sim._ensure_synced()
			var pd = sim._rd.buffer_get_data(sim._pos_buf, 0, 32).to_float32_array()
			var ad = sim._rd.buffer_get_data(sim._acc_buf, 0, 32).to_float32_array()
			for v in [pd[0], pd[1], pd[2], pd[4], pd[5], pd[6], ad[0], ad[1], ad[2], ad[4], ad[5], ad[6]]:
				if not is_finite(v):
					bad = true
					print("  NaN/Inf at step %d: pos=%s acc=%s" % [s, pd, ad])
	_check("nan: no NaN/Inf in 30 steps", not bad)


func _test_reinit() -> void:
	print("── (v) reinit() keeps the pipeline consistent ──")
	sim.reinit()
	sim.playing = false
	sim.gravity_mode = 0
	for s in range(3):
		sim._physics_step()
	sim._ensure_synced()
	var ad = sim._rd.buffer_get_data(sim._acc_buf, 0, 16).to_float32_array()
	var finite_ok = is_finite(ad[0]) and is_finite(ad[1]) and is_finite(ad[2])
	# After reinit, one more crafted step must still produce the river force
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	for i in range(nc):
		ey[i] = 0.00012
		ei[i] = 0.00010
	_write_fields(ey, ei)
	_set_two(Vector3.ZERO, Vector3(8.0, 0.0, 0.0))
	sim._physics_step()
	var acc := _read_acc()
	var phi := _read_phi()  # read AFTER the crafted step (fresh solve)
	# The expected must be built from the fields the shader ACTUALLY saw,
	# not the crafted arrays: the 3 warmup steps' PDE evolution leaves a
	# velocity field (unseeded reinit noise) that the crafted step's
	# leapfrog injects into ey/ei (~1e-6 at the probe — a ±15% π/ρ shift
	# run-to-run). With the crafted fields the check flakes 2.8–12.5%;
	# with the post-step readback it is exact (the shader matches its own
	# fields at ~1e-6 — verified in isolation).
	var ey_act = sim._rd.buffer_get_data(sim._field_ey, 0, nc * 4).to_float32_array()
	var ei_act = sim._rd.buffer_get_data(sim._field_ei, 0, nc * 4).to_float32_array()
	var expected := _expected_river(ey_act, ei_act, phi, Vector3(8.0, 0.0, 0.0))
	_check("reinit: acc finite after reinit", finite_ok)
	_check("reinit: river force still correct after reinit (10%)",
		(acc - expected).length() / max(expected.length(), 1e-30) < 0.10,
		"acc=%s expected=%s" % [acc, expected])
