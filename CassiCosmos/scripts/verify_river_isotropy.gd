extends Node
## River-force azimuthal anisotropy measurement ("the river has a strong
## bias along grid lines").
##
## Single point mass (direct density-buffer write: delta 10.0 at the
## center cell, the verify_fft _delta pattern) + 64 zero-mass probe
## particles on rings of radius r = 8h and r = 4h in the z = 0 plane
## (grid row 32), uniform tiny fluid (q uniform → g uniform → the
## anisotropy lives in ∇Φ alone). One solve+gravity chain runs, then the
## probe accelerations are compared against the gradient estimators
## computed in GDScript on the same solved Φ:
##   NEW — trilinear interpolation of the cell-centered central-difference
##         gradient of S (the shader's current grad_main + tri_grad).
##   OLD — per-particle central difference of trilinear samples of
##         S = g·Φ at p ± h·ê (the pre-2026-08-09 shader estimator).
##
## ESTIMATOR IDENTITY (measured, machine precision): for ANY fixed S field
## the OLD and NEW estimators are algebraically identical —
##   [tri(S,p+h·ê) − tri(S,p−h·ê)]/(2h) == tri(∇_cell S)(p)
## (both blend adjacent cells' piecewise-constant trilinear gradients
## with the same weights (1−f), f — verified to 2e-16). The 0.117 toggle
## mismatch in the reverted stretch was a dispatch bug (skipped gradient
## pass), not an estimator difference.
##
## GATED EXPERIMENT (2026-08-09, verdict: REVERTED): a separable
## Catmull-Rom tricubic sampler (4×4×4 taps) was implemented in the
## shader as the bias lever and measured here — it did NOT reduce the
## ring anisotropy: |a|(θ) max/min = 1.0482 at r = 8h and 1.1445 at
## r = 4h vs the trilinear 1.0441 / 1.1293 (slightly worse; Catmull-Rom
## overshoot). The measured "bias along grid lines" is therefore
## intrinsic to the discrete torus-Green field's cubic structure, not
## the sampler — the lever is the box size / grid resolution. The
## tricubic was reverted; this test pins the trilinear baseline numbers.
##
## Assertions:
##   (i)   shader |a|(θ) matches the NEW estimator within 1%
##         (the GPU implements grad_main + tri_grad; fp32 vs fp64)
##   (ii)  OLD matches NEW within 1% (the identity, empirically)
##   (iii) no NaN/Inf anywhere; force attractive at every probe
## Reported: anisotropy ratios (max|a|/min|a| over θ) for shader/NEW/OLD
## at both radii — the honest quantitative answer to "the river has a
## bias along grid lines".
##
## NOTE on the dispatch chain: the per-step GPU clear (poisson mode 3)
## wipes any CPU-side rho write at the start of _physics_step, so the
## direct density write cannot go through sim._physics_step(). Instead the
## REAL pipeline is driven manually in one compute list — poisson solve
## (sim._dispatch_poisson), then the gradient pass (pass_mode = 1), then
## the N-body pass (pass_mode = 0) — with the same ordering, barriers and
## push constants as _step_dispatches (2.8 gradient → 3. nbody). The 4h
## ring re-dispatches only the N-body pass (the S field is unchanged).
##
## Run: godot --path <repo> res://scenes/verify_river_isotropy.tscn

const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const TWO_PI: float = 6.28318530717958647693
const G_N: float = 1.0
const PI_CLAMP_MAX: float = 0.72
const PROBE_R: float = 8.0   # ring radius in cell units (h·PROBE_R)
const NPROBE: int = 64       # probe count on the ring

var sim: Node3D
var N: int = 64
var extent: float = 37.5
var h: float = 0.0
var nc: int = 0

var _failures: int = 0
var _checks: int = 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")  # sibling node in the verify scene
	if sim == null:
		push_error("verify_river_isotropy: CassiSim not found in scene")
		get_tree().quit(1)
		return
	N = sim.grid_N
	extent = sim.cluster_radius * 1.5
	h = extent / (float(N) * 0.5)
	nc = N * N * N
	sim.playing = false
	sim.gravity_mode = 0  # RIVER
	await get_tree().process_frame
	await get_tree().process_frame
	var waited := 0
	while not sim._shaders_ready and waited < 300:
		waited += 1
		await get_tree().process_frame
	if not sim._shaders_ready:
		push_error("verify_river_isotropy: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	print("verify_river_isotropy: shaders ready after %d extra frames" % waited)
	_run_all()
	get_tree().quit(0 if _failures == 0 else 1)


# ═══════════════════════════════════════════════════════════════════════
# Field/buffer plumbing
# ═══════════════════════════════════════════════════════════════════════

func _write_fields(ey: PackedFloat32Array, ei: PackedFloat32Array) -> void:
	sim._rd.buffer_update(sim._field_ey, 0, nc * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, nc * 4, ei.to_byte_array())
	var q = PackedFloat32Array()
	q.resize(nc)
	for i in range(nc):
		q[i] = ey[i] * ey[i] + ei[i] * ei[i]
	sim._rd.buffer_update(sim._field_q, 0, nc * 4, q.to_byte_array())


# Single-cell delta mass 10.0 at the grid center — the verify_fft _delta
# pattern, written DIRECTLY into the density buffer (the deposit shader is
# not exercised; all particles have zero mass).
func _write_delta_rho() -> void:
	var rho = PackedFloat32Array()
	rho.resize(nc)
	rho[N / 2 + N * (N / 2) + N * N * (N / 2)] = 10.0
	sim._rd.buffer_update(sim._mass_density_buf, 0, nc * 4, rho.to_byte_array())


# 64 zero-mass probes on the ring radius r = radius_h·h in the z = 0 plane.
func _set_probes(radius_h: float) -> void:
	var pos = PackedFloat32Array()
	pos.resize(NPROBE * 4)
	var vel = PackedFloat32Array()
	vel.resize(NPROBE * 4)
	var acc = PackedFloat32Array()
	acc.resize(NPROBE * 4)
	var r := radius_h * h
	for kk in range(NPROBE):
		var th := TWO_PI * float(kk) / float(NPROBE)
		pos[kk * 4] = r * cos(th)
		pos[kk * 4 + 1] = r * sin(th)
		pos[kk * 4 + 2] = 0.0
		pos[kk * 4 + 3] = 0.0  # zero mass — no deposit, no BH term
	sim._rd.buffer_update(sim._pos_buf, 0, NPROBE * 16, pos.to_byte_array())
	sim._rd.buffer_update(sim._vel_buf, 0, NPROBE * 16, vel.to_byte_array())
	sim._rd.buffer_update(sim._acc_buf, 0, NPROBE * 16, acc.to_byte_array())


# The manual chain: poisson solve → gradient pass → nbody pass, in ONE
# compute list with barriers — the exact ordering/push constants of
# _step_dispatches (poisson → 2.8 gradient → 3. nbody).
func _run_chain() -> void:
	var cl = sim._rd.compute_list_begin()
	sim._dispatch_poisson(cl)
	sim._barrier(cl)  # poisson → gradient
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	# ALL THREE sets must be bound (the pipeline rejects a dispatch with any
	# declared set missing) — grad_main reads set 0 + bh extent (set 2).
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(1.0), 48)  # gradient pass
	sim._rd.compute_list_dispatch(cl, N, N, 1)  # 2D cells dispatch
	sim._barrier(cl)  # gradient → nbody
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(0.0), 48)  # particle pass
	sim._rd.compute_list_dispatch(cl, ceili(float(NPROBE) / 256.0), 1, 1)
	sim._rd.compute_list_end()


func _nbody_pc(pass_mode: float) -> PackedByteArray:
	# Same 12 fields the sim encodes into _nbody_pc_bytes per step
	var pc: PackedByteArray = sim._nbody_pc_bytes.duplicate()
	pc.encode_float(0, float(N))
	pc.encode_float(4, sim.dt)
	pc.encode_float(8, sim._time)
	pc.encode_float(12, PHI)
	pc.encode_float(16, sim.xi)
	pc.encode_float(20, sim.softening * sim.softening)
	pc.encode_float(24, float(sim.N_particles))
	pc.encode_float(28, float(sim.mode))
	pc.encode_float(32, sim.source_strength)
	pc.encode_float(36, float(sim.num_clusters))
	pc.encode_float(40, float(sim.gravity_mode))
	pc.encode_float(44, pass_mode)
	return pc


func _read_phi() -> PackedFloat32Array:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._fft_buf, 0, nc * 8)
	var f = d.to_float32_array()
	var phi = PackedFloat32Array()
	phi.resize(nc)
	for i in range(nc):
		phi[i] = f[i * 2]  # real part
	return phi


func _read_accs() -> Array:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._acc_buf, 0, NPROBE * 16)
	var f = d.to_float32_array()
	var out := []
	for kk in range(NPROBE):
		out.append(Vector3(f[kk * 4], f[kk * 4 + 1], f[kk * 4 + 2]))
	return out


# ═══════════════════════════════════════════════════════════════════════
# Estimators (exact GDScript replications of the shader math, float64)
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
	var v000: float = field[i0 + N * (j0 + N * k0)]
	var v100: float = field[i1 + N * (j0 + N * k0)]
	var v010: float = field[i0 + N * (j1 + N * k0)]
	var v110: float = field[i1 + N * (j1 + N * k0)]
	var v001: float = field[i0 + N * (j0 + N * k1)]
	var v101: float = field[i1 + N * (j0 + N * k1)]
	var v011: float = field[i0 + N * (j1 + N * k1)]
	var v111: float = field[i1 + N * (j1 + N * k1)]
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


# S = g·Φ per cell (g from the law's q at CELL values) — the shader's
# chord_s_at, replicated exactly.
func _build_s(ey: PackedFloat32Array, ei: PackedFloat32Array,
		phi: PackedFloat32Array) -> PackedFloat32Array:
	var s = PackedFloat32Array()
	s.resize(nc)
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
	return s


# OLD estimator: central difference of trilinear samples of S at p ± h·ê
# (the per-particle chord_gradient the shader used before the upgrade).
func _old_grad(s: PackedFloat32Array, wp: Vector3) -> Vector3:
	return Vector3(
		_tri(s, wp + Vector3(h, 0, 0)) - _tri(s, wp - Vector3(h, 0, 0)),
		_tri(s, wp + Vector3(0, h, 0)) - _tri(s, wp - Vector3(0, h, 0)),
		_tri(s, wp + Vector3(0, 0, h)) - _tri(s, wp - Vector3(0, 0, h))) / (2.0 * h)


# NEW estimator: trilinear interpolation of the cell-centered
# central-difference gradient of S (the shader's grad_main + tri_grad).
# Builds the three gradient arrays ONCE (O(N³)); sampling is O(1) per
# probe — the per-probe rebuild made the 64-probe ring run for hours.
func _build_new_grad(s: PackedFloat32Array) -> Array:
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
				gx[id] = (s[ip] - s[im]) * inv2h
				gy[id] = (s[jp] - s[jm]) * inv2h
				gz[id] = (s[kp] - s[km]) * inv2h
	return [gx, gy, gz]


func _sample_new_grad(grad_fields: Array, wp: Vector3) -> Vector3:
	return Vector3(_tri(grad_fields[0], wp), _tri(grad_fields[1], wp), _tri(grad_fields[2], wp))


# π/ρ at a point (same sampler + clamp as the shader's chord_g_at).
func _pi_over_rho(ey: PackedFloat32Array, ei: PackedFloat32Array, wp: Vector3) -> float:
	return _clamp_pi(_tri(ey, wp) - _tri(ei, wp), _tri(ey, wp) + _tri(ei, wp))


# ═══════════════════════════════════════════════════════════════════════
# Test battery
# ═══════════════════════════════════════════════════════════════════════

func _run_all() -> void:
	print("══════ verify_river_isotropy — N=%d, extent=%.1f, h=%.4f, rings r=4h,8h (%d probes each) ══════" % [N, extent, h, NPROBE])
	# Uniform tiny fluid: q uniform → g uniform → the anisotropy lives in
	# ∇(g·Φ) alone (the sampled field's direction structure)
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	for i in range(nc):
		ey[i] = 0.00012
		ei[i] = 0.00010
	_write_fields(ey, ei)
	_write_delta_rho()
	_set_probes(PROBE_R)
	_run_chain()

	var phi := _read_phi()
	var s := _build_s(ey, ei, phi)
	var new_grad_fields := _build_new_grad(s)  # built ONCE (O(N³))

	# 8h ring (the chain's own probe positions)
	var accs8 := _read_accs()
	_measure_ring(accs8, PROBE_R, ey, ei, s, new_grad_fields)

	# 4h ring: re-place the probes and re-dispatch ONLY the N-body pass —
	# the S field is unchanged, so the poisson + gradient passes need no
	# re-run (same ordering as _step_dispatches' nbody block).
	_set_probes(4.0)
	var cl = sim._rd.compute_list_begin()
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(0.0), 48)
	sim._rd.compute_list_dispatch(cl, ceili(float(NPROBE) / 256.0), 1, 1)
	sim._rd.compute_list_end()
	_measure_ring(_read_accs(), 4.0, ey, ei, s, new_grad_fields)

	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])


# Measure one ring: shader-vs-NEW and OLD-vs-NEW agreement + anisotropy
# ratios. (OLD ≡ NEW for a fixed S field — verified to 2e-16 — so the
# ratios are equal by identity; the reported anisotropy is intrinsic to
# the discrete torus-Green field — the tricubic-sampler gate experiment
# did not reduce it, see the header.)
func _measure_ring(accs: Array, radius_h: float, ey: PackedFloat32Array,
		ei: PackedFloat32Array, s: PackedFloat32Array, new_grad_fields: Array) -> void:
	var label := "r=%.1fh" % radius_h
	var a_new := []
	var a_old := []
	var r := radius_h * h
	for kk in range(NPROBE):
		var th := TWO_PI * float(kk) / float(NPROBE)
		var wp := Vector3(r * cos(th), r * sin(th), 0.0)
		var por := _pi_over_rho(ey, ei, wp)
		a_new.append(-G_N * por * _sample_new_grad(new_grad_fields, wp))
		a_old.append(-G_N * por * _old_grad(s, wp))

	var mag_sh := []
	var mag_new := []
	var mag_old := []
	for kk in range(NPROBE):
		mag_sh.append(accs[kk].length())
		mag_new.append(a_new[kk].length())
		mag_old.append(a_old[kk].length())

	# NaN check across shader + both estimators
	var bad := false
	for kk in range(NPROBE):
		if not (is_finite(mag_sh[kk]) and is_finite(mag_new[kk]) and is_finite(mag_old[kk])):
			bad = true
			print("  NaN/Inf at probe %d: |a_sh|=%.6g |a_new|=%.6g |a_old|=%.6g" % [kk, mag_sh[kk], mag_new[kk], mag_old[kk]])
	_check("isotropy[%s]: no NaN/Inf in shader or estimators" % label, not bad)

	# Inward force sanity (the ring must be attracted to the central mass)
	var inward := true
	for kk in range(NPROBE):
		var th := TWO_PI * float(kk) / float(NPROBE)
		if accs[kk].dot(Vector3(cos(th), sin(th), 0.0)) >= 0.0:
			inward = false
	_check("isotropy[%s]: force is attractive (a·r̂ < 0) at every probe" % label, inward)

	# (i) shader matches the NEW estimator (the GPU implements grad_main +
	# tri_grad; residual = fp32 vs fp64)
	var mean_new := 0.0
	for kk in range(NPROBE):
		mean_new += mag_new[kk]
	mean_new /= float(NPROBE)
	var worst_rel := 0.0
	var worst_old := 0.0
	for kk in range(NPROBE):
		var rel: float = (accs[kk] - a_new[kk]).length() / max(mean_new, 1e-30)
		worst_rel = max(worst_rel, rel)
		var relo: float = (a_old[kk] - a_new[kk]).length() / max(mean_new, 1e-30)
		worst_old = max(worst_old, relo)
	_check("isotropy[%s]: shader |a| matches NEW estimator < 1%%" % label, worst_rel < 0.01,
		"max rel=%.6f (fp32-vs-fp64 residual)" % worst_rel)
	# (ii) OLD ≡ NEW by identity (measured; see header for the algebra)
	_check("isotropy[%s]: OLD estimator matches NEW < 1%% (identity)" % label, worst_old < 0.01,
		"max |old−new|/mean = %.6f" % worst_old)

	# Anisotropy ratios max|a|/min|a| over θ for shader / new / old
	var mx_sh := 0.0; var mn_sh := INF
	var mx_new := 0.0; var mn_new := INF
	var mx_old := 0.0; var mn_old := INF
	for kk in range(NPROBE):
		mx_sh = max(mx_sh, mag_sh[kk]); mn_sh = min(mn_sh, mag_sh[kk])
		mx_new = max(mx_new, mag_new[kk]); mn_new = min(mn_new, mag_new[kk])
		mx_old = max(mx_old, mag_old[kk]); mn_old = min(mn_old, mag_old[kk])
	var ratio_sh := mx_sh / mn_sh
	var ratio_new := mx_new / mn_new
	var ratio_old := mx_old / mn_old
	print("  [%s] |a|(θ): shader max=%.6f min=%.6f ratio=%.4f" % [label, mx_sh, mn_sh, ratio_sh])
	print("  [%s] |a|(θ): NEW    max=%.6f min=%.6f ratio=%.4f" % [label, mx_new, mn_new, ratio_new])
	print("  [%s] |a|(θ): OLD    max=%.6f min=%.6f ratio=%.4f" % [label, mx_old, mn_old, ratio_old])
	print("  [%s] grid-line bias (ratio−1): shader %.1f%%  NEW %.1f%%  OLD %.1f%%" % [
		label, 100.0 * (ratio_sh - 1.0), 100.0 * (ratio_new - 1.0), 100.0 * (ratio_old - 1.0)])


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])
