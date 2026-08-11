extends Node
## Focused verification of the 3-mode gravity selector, the bounded
## (truncated-Plummer) ICs, the opt-in river calibration / attractor
## field init, and the cached-acc KDK (cassi_sim.gd +
## cassi_nbody_gravity.glsl).
##
## Scene: N=64, N_particles=16384, cluster_radius=50 (extent=75, h=2.34375).
##
## Battery:
##   (i)   truncated-Plummer IC: zero initial out-of-box particles, max
##         |component| ≤ fr·extent, retained CDF matches the analytic
##         u(r_max) = (x²/(1+x²))^(3/2), x = r_max/a (2% tolerance).
##   (ii)  clamp-hole fraction before/after: the legacy flat-noise field
##         has a large fraction of cells with π/ρ clamped to 0 (force-free
##         holes); the opt-in attractor init (EY = φ·EI + tiny noise) must
##         have ZERO holes (< 1e-6). Both fractions are reported.
##   (iii) Plummer reference arm vs the analytic softened enclosed-mass
##         force |a| = G_N·M·r/(r²+a²)^(3/2) at ring probes (≤5%, inward):
##         single cluster, then a 2-cluster config where the EXPECTED force
##         is the SUM of both clusters' contributions (the shader reads the
##         actual cluster centers + per-cluster masses from the cluster
##         buffer — set 2 binding 1, previously unbound).
##   (iv)  river-vs-heuristic magnitude ratio at r ≥ 8h from a Gaussian
##         blob (total mass 8, σ = 2h): the river force is coherent
##         (≈ π/ρ·g·M·h³/(4πr²)); the heuristic ∇q_s force is ~zero there.
##         Reported per radius; the 8h ratio must exceed 10. The heuristic
##         is a WEAK-FORCE result by construction — it is reported and
##         classified, never counted as a pass.
##   (v)   200-step occupancy per mode at IDENTICAL restored initial
##         positions: NaN scan, inner/face/corner/out-of-box fractions
##         (lim = 0.85·extent), and per-step timing (river with calibration
##         + attractor, heuristic and Plummer at G_N = 1 = the IC
##         convention). Plummer and calibrated-river must hold the cluster
##         (zero out-of-box); heuristic is reported as weak-force. The
##         skip-pass (heuristic/Plummer drop the 7-pass FFT + gradient)
##         must reduce ms/step vs river.
##
## NOTE on the IC vs Plummer profile: the IC circular velocity uses the
## sim's enclosed-mass profile M_enc(r) = M·r²/(r²+a²) (cassi_sim.gd
## _init_particles), which exceeds the ANALYTIC Plummer M_enc = M·r³/
## (r²+a²)^(3/2) by up to ~20% near the core; with the 0.85 v_circ factor
## the short 200-step occupancy window stays bound (≈0.005 orbits), so the
## analytic arm is compared against ITS OWN formula exactly.
##
## Run: godot --path <repo> res://scenes/verify_gravity_modes.tscn

const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const TWO_PI: float = 6.28318530717958647693
const G_N_IC: float = 1.0

var sim: Node3D
var N: int = 64
var extent: float = 75.0
var h: float = 0.0
var nc: int = 0

var _failures: int = 0
var _checks: int = 0
var _report: Array = []


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")  # sibling node in the verify scene
	if sim == null:
		push_error("verify_gravity_modes: CassiSim not found in scene")
		get_tree().quit(1)
		return
	N = sim.grid_N
	extent = sim.cluster_radius * 1.5
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
		push_error("verify_gravity_modes: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	print("verify_gravity_modes: shaders ready after %d extra frames" % waited)
	_run_all()
	get_tree().quit(0 if _failures == 0 else 1)


# ═══════════════════════════════════════════════════════════════════════
# Buffer plumbing
# ═══════════════════════════════════════════════════════════════════════

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


func _upload_bh() -> void:
	# Sync the BH header (G_N etc.) with the CPU-side init bytes — the
	# manual chains below do not go through _run_physics_steps' upload.
	sim._rd.buffer_update(sim._bh_buf, 0, sim._bh_init_bytes.size(), sim._bh_init_bytes)


func _dispatch_nbody(pass_mode: float) -> void:
	var cl = sim._rd.compute_list_begin()
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(pass_mode), 48)
	sim._rd.compute_list_dispatch(cl, ceili(float(sim.N_particles) / 256.0), 1, 1)
	sim._rd.compute_list_end()


# Full river chain: poisson → gradient pass → nbody pass, one compute
# list with barriers (the _step_dispatches ordering, minus clear/deposit —
# rho is written directly here).
func _run_river_chain() -> void:
	var cl = sim._rd.compute_list_begin()
	sim._dispatch_poisson(cl)
	sim._barrier(cl)  # poisson → gradient
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(1.0), 48)  # gradient pass
	sim._rd.compute_list_dispatch(cl, N, N, 1)
	sim._barrier(cl)  # gradient → nbody
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(0.0), 48)  # particle pass
	sim._rd.compute_list_dispatch(cl, ceili(float(sim.N_particles) / 256.0), 1, 1)
	sim._rd.compute_list_end()


# Probes on a ring (z=0 plane) around `center`; the whole particle buffer
# is re-written: probes first, zeroed (zero mass/vel/acc) elsewhere.
func _set_ring_probes(nprobe: int, r: float, center: Vector3) -> void:
	var npart: int = sim.N_particles
	var pos = PackedFloat32Array(); pos.resize(npart * 4)
	var vel = PackedFloat32Array(); vel.resize(npart * 4)
	var acc = PackedFloat32Array(); acc.resize(npart * 4)
	for kk in range(nprobe):
		var th := TWO_PI * float(kk) / float(nprobe)
		pos[kk * 4]     = center.x + r * cos(th)
		pos[kk * 4 + 1] = center.y + r * sin(th)
		pos[kk * 4 + 2] = center.z
		pos[kk * 4 + 3] = 0.0  # zero mass — no deposit, no BH term
	sim._rd.buffer_update(sim._pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	sim._rd.buffer_update(sim._vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	sim._rd.buffer_update(sim._acc_buf, 0, acc.size() * 4, acc.to_byte_array())


func _set_point_probes(points: Array) -> void:
	var npart: int = sim.N_particles
	var pos = PackedFloat32Array(); pos.resize(npart * 4)
	var vel = PackedFloat32Array(); vel.resize(npart * 4)
	var acc = PackedFloat32Array(); acc.resize(npart * 4)
	for kk in range(points.size()):
		var p: Vector3 = points[kk]
		pos[kk * 4] = p.x
		pos[kk * 4 + 1] = p.y
		pos[kk * 4 + 2] = p.z
		pos[kk * 4 + 3] = 0.0
	sim._rd.buffer_update(sim._pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	sim._rd.buffer_update(sim._vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	sim._rd.buffer_update(sim._acc_buf, 0, acc.size() * 4, acc.to_byte_array())


func _read_accs(nprobe: int) -> Array:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._acc_buf, 0, nprobe * 16)
	var f = d.to_float32_array()
	var out := []
	for kk in range(nprobe):
		out.append(Vector3(f[kk * 4], f[kk * 4 + 1], f[kk * 4 + 2]))
	return out


func _read_pos_all() -> PackedFloat32Array:
	sim._ensure_synced()
	return sim._rd.buffer_get_data(sim._pos_buf, 0, sim.N_particles * 16).to_float32_array()


func _read_vel_all() -> PackedFloat32Array:
	sim._ensure_synced()
	return sim._rd.buffer_get_data(sim._vel_buf, 0, sim.N_particles * 16).to_float32_array()


func _write_pos_vel(pos: PackedFloat32Array, vel: PackedFloat32Array) -> void:
	sim._rd.buffer_update(sim._pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	sim._rd.buffer_update(sim._vel_buf, 0, vel.size() * 4, vel.to_byte_array())


# Gaussian blob (total_mass, σ = sigma) written DIRECTLY into the density
# buffer — the verify_fft/verify_river_isotropy pattern (no deposit shader).
func _write_gaussian_blob(total_mass: float, sigma: float) -> void:
	var rho = PackedFloat32Array(); rho.resize(nc)
	var inv2s2: float = 1.0 / (2.0 * sigma * sigma)
	var sum_w := 0.0
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				var x: float = (float(i) - float(N) * 0.5) * h
				var y: float = (float(j) - float(N) * 0.5) * h
				var z: float = (float(k) - float(N) * 0.5) * h
				var w: float = exp(-(x * x + y * y + z * z) * inv2s2)
				rho[id] = w
				sum_w += w
	var norm: float = total_mass / (sum_w * h * h * h)
	for i in range(nc):
		rho[i] *= norm
	sim._rd.buffer_update(sim._mass_density_buf, 0, nc * 4, rho.to_byte_array())


# Fraction of grid cells where π/ρ = (EY−EI)/(EY+EI) clamps to 0 (or hits
# the ρ guard) — the "force-free hole" measure, computed from the FIELD
# buffers with the shader's exact clamp.
func _field_pi_zero_fraction() -> float:
	sim._ensure_synced()
	var ey = sim._rd.buffer_get_data(sim._field_ey, 0, nc * 4).to_float32_array()
	var ei = sim._rd.buffer_get_data(sim._field_ei, 0, nc * 4).to_float32_array()
	var zeros := 0
	for i in range(nc):
		var rho_f: float = ey[i] + ei[i]
		var pi_v: float = 0.0
		if rho_f >= 1e-6:
			pi_v = clampf((ey[i] - ei[i]) / rho_f, 0.0, 0.72)
		if pi_v == 0.0:
			zeros += 1
	return float(zeros) / float(nc)


func _positions_finite() -> bool:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._pos_buf, 0, 16 * 16)
	var f = d.to_float32_array()
	for v in f:
		if not is_finite(v):
			return false
	return true


# Occupancy classification of ALL particles: inner / face-edge / corner /
# out-of-box (lim = 0.85·extent; corner = 3 components ≥ lim).
func _occupancy_counts() -> Array:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._pos_buf, 0, sim.N_particles * 16)
	var f = d.to_float32_array()
	var lim: float = 0.85 * extent
	var in_c := 0
	var face := 0
	var corner := 0
	var out_c := 0
	for i in range(sim.N_particles):
		var i4 = i * 4
		var x: float = f[i4]
		var y: float = f[i4 + 1]
		var z: float = f[i4 + 2]
		if absf(x) > extent or absf(y) > extent or absf(z) > extent:
			out_c += 1
			continue
		var c: float = maxf(absf(x), maxf(absf(y), absf(z)))
		if c < lim:
			in_c += 1
		else:
			var n_hi := 0
			if absf(x) >= lim: n_hi += 1
			if absf(y) >= lim: n_hi += 1
			if absf(z) >= lim: n_hi += 1
			if n_hi >= 3:
				corner += 1
			else:
				face += 1
	var tot := float(max(sim.N_particles, 1))
	return [100.0 * float(in_c) / tot, 100.0 * float(face) / tot,
			100.0 * float(corner) / tot, out_c]


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


# ═══════════════════════════════════════════════════════════════════════
# Test battery
# ═══════════════════════════════════════════════════════════════════════

func _run_all() -> void:
	print("══════ verify_gravity_modes — N=%d, extent=%.1f, h=%.4f, N_particles=%d ══════" % [N, extent, h, sim.N_particles])
	_test_truncated_ic()
	_test_clamp_holes()
	_test_plummer_analytic()
	_test_plummer_multi_cluster()
	_test_blob_ratio()
	_test_occupancy_modes()
	print("── summary ──")
	for line in _report:
		print("  " + line)
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])


func _test_truncated_ic() -> void:
	print("── (i) truncated-Plummer IC ──")
	var fr: float = sim.initial_radius_fraction
	_check("IC: zero initial out-of-box particles", sim._init_out_of_box == 0,
		"out=%d (fr=%.2f, extent=%.1f)" % [sim._init_out_of_box, fr, extent])
	var lim: float = fr * extent
	_check("IC: max |component| ≤ fr·extent", sim._init_max_component <= lim + 1e-3,
		"max_comp=%.3f lim=%.3f" % [sim._init_max_component, lim])
	_check("IC: max radius ≤ fr·extent", sim._init_max_radius <= lim + 1e-3,
		"max_r=%.3f" % sim._init_max_radius)
	# Analytic retained CDF: u(r_max) with r_max = fr·extent − |center|_∞;
	# the scene's single cluster sits at the origin → r_max = fr·extent.
	var x_max: float = (fr * extent) / maxf(sim.cluster_radius, 1e-6)
	var u_analytic: float = pow(x_max * x_max / (1.0 + x_max * x_max), 1.5)
	var rel: float = absf(sim._init_retained_fraction - u_analytic) / maxf(u_analytic, 1e-9)
	_check("IC: retained CDF matches analytic u(r_max) (2%)", rel < 0.02,
		"retained=%.4f analytic=%.4f" % [sim._init_retained_fraction, u_analytic])
	_report.append("IC retained CDF=%.4f (analytic %.4f)  max_radius=%.1f  out_of_box=%d" % [
		sim._init_retained_fraction, u_analytic, sim._init_max_radius, sim._init_out_of_box])


func _test_clamp_holes() -> void:
	print("── (ii) clamp-hole fraction: legacy noise vs attractor init ──")
	sim.field_attractor_init = false
	sim.river_calibrate_gn = false
	sim.gravity_mode = 0
	sim.num_clusters = 1
	sim.cluster_separation = 0.0
	sim.reinit()
	sim.playing = false
	var frac_legacy := _field_pi_zero_fraction()
	sim.field_attractor_init = true
	sim.reinit()
	sim.playing = false
	var frac_attr := _field_pi_zero_fraction()
	print("  π/ρ = 0 fraction: legacy noise = %.4f   attractor = %.6f" % [frac_legacy, frac_attr])
	_check("attractor init: zero force-free holes (<1e-6)", frac_attr < 1e-6,
		"attr=%.6f" % frac_attr)
	_report.append("clamp-hole (π/ρ=0) fraction: legacy=%.4f attractor=%.6f" % [frac_legacy, frac_attr])


func _test_plummer_analytic() -> void:
	print("── (iii) Plummer reference arm vs analytic (single cluster, 8h ring) ──")
	sim.gravity_mode = 2
	sim.river_calibrate_gn = false  # G_N = 1 = the IC convention
	sim.field_attractor_init = true
	sim.num_clusters = 1
	sim.cluster_separation = 0.0
	sim.reinit()
	sim.playing = false
	_upload_bh()
	var NPROBE := 64
	var r: float = 8.0 * h
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	_dispatch_nbody(0.0)
	var accs := _read_accs(NPROBE)
	# Analytic: |a| = G_N·M·r/(r²+a²)^(3/2), M = per-cluster count (nc=1)
	var M: float = float(sim.N_particles)
	var a_soft: float = sim.cluster_radius
	var pred_mag: float = G_N_IC * M * r / pow(r * r + a_soft * a_soft, 1.5)
	var worst := 0.0
	var inward := true
	for kk in range(NPROBE):
		var mag: float = accs[kk].length()
		var dev: float = absf(mag - pred_mag) / maxf(pred_mag, 1e-30)
		worst = maxf(worst, dev)
		var th := TWO_PI * float(kk) / float(NPROBE)
		if accs[kk].dot(Vector3(cos(th), sin(th), 0.0)) >= 0.0:
			inward = false
	_check("plummer: |a| matches analytic M·r/(r²+a²)^{3/2} ≤5%", worst < 0.05,
		"worst=%.2f%% pred=%.8f (r=%.2f, M=%.0f, a=%.1f)" % [worst * 100.0, pred_mag, r, M, a_soft])
	_check("plummer: force inward at every probe", inward)
	_report.append("Plummer |a|@8h: pred=%.8f worst dev=%.2f%%" % [pred_mag, worst * 100.0])


func _test_plummer_multi_cluster() -> void:
	print("── (iii) Plummer multi-cluster: 2 clusters, forces sum ──")
	sim.gravity_mode = 2
	sim.river_calibrate_gn = false
	sim.field_attractor_init = true
	sim.num_clusters = 2
	sim.cluster_separation = 60.0  # centers ±60 (r_max = 67.5−60 = 7.5 > 0)
	sim.reinit()
	sim.playing = false
	_upload_bh()
	var sep: float = sim.cluster_separation
	var M_each: float = float(sim.N_particles) / 2.0
	var a_soft: float = sim.cluster_radius
	var c0 := Vector3(float(sep), 0.0, 0.0)
	var c1 := Vector3(-float(sep), 0.0, 0.0)
	var NPROBE := 32
	var r: float = 6.0 * h  # 14.06 — ring inside the box (x ∈ [45.9, 74.1])
	_set_ring_probes(NPROBE, r, c0)
	_dispatch_nbody(0.0)
	var accs := _read_accs(NPROBE)
	var worst := 0.0
	for kk in range(NPROBE):
		var th := TWO_PI * float(kk) / float(NPROBE)
		var wp := c0 + Vector3(r * cos(th), r * sin(th), 0.0)
		# Force ON the probe FROM each cluster: a = G·M·(c−p)/(|c−p|²+a²)^{3/2}
		# (toward the cluster — the shader's delta = cluster[c].xyz − wp)
		var d0 := c0 - wp
		var d1 := c1 - wp
		var a_exp := G_N_IC * M_each * d0 / pow(d0.length_squared() + a_soft * a_soft, 1.5) \
			+ G_N_IC * M_each * d1 / pow(d1.length_squared() + a_soft * a_soft, 1.5)
		var dev: float = (accs[kk] - a_exp).length() / maxf(a_exp.length(), 1e-30)
		worst = maxf(worst, dev)
	_check("plummer-2c: |a| matches summed analytic force ≤5%", worst < 0.05,
		"worst=%.2f%% (sep=%.0f, M_each=%.0f)" % [worst * 100.0, sep, M_each])
	_report.append("Plummer 2-cluster summed-force worst dev=%.2f%%" % (worst * 100.0))


func _test_blob_ratio() -> void:
	print("── (iv) river vs heuristic magnitude at r ≥ 8h (Gaussian blob) ──")
	sim.gravity_mode = 0
	sim.river_calibrate_gn = false  # ratio is G_N-independent; keep G_N = 1
	sim.field_attractor_init = true
	sim.num_clusters = 1
	sim.cluster_separation = 0.0
	sim.reinit()
	sim.playing = false
	_upload_bh()
	_write_gaussian_blob(8.0, 2.0 * h)  # total 8, σ = 2h = 4.6875
	var probes := [
		Vector3(8.0 * h, 0.0, 0.0),
		Vector3(12.0 * h, 0.0, 0.0),
		Vector3(16.0 * h, 0.0, 0.0),
		Vector3(24.0 * h, 0.0, 0.0),
	]
	_set_point_probes(probes)
	sim.gravity_mode = 0
	_run_river_chain()
	var acc_r := _read_accs(probes.size())
	sim.gravity_mode = 1
	_dispatch_nbody(0.0)
	var acc_h := _read_accs(probes.size())
	var mag_r := []
	var mag_h := []
	var bad := false
	for kk in range(probes.size()):
		mag_r.append(acc_r[kk].length())
		mag_h.append(acc_h[kk].length())
		if not (is_finite(mag_r[kk]) and is_finite(mag_h[kk])):
			bad = true
	_check("blob: river and heuristic accelerations finite", not bad)
	var radii := [8.0, 12.0, 16.0, 24.0]
	var ratio_8h := 0.0
	for kk in range(probes.size()):
		var ratio := 0.0
		if mag_h[kk] > 1e-12:
			ratio = mag_r[kk] / mag_h[kk]
		print("  r=%.0fh: |a_river|=%.8f  |a_heuristic|=%.8f  ratio=%s" % [radii[kk], mag_r[kk], mag_h[kk], str(ratio)])
		if kk == 0:
			ratio_8h = ratio
	_check("blob: river |a| > 10× heuristic at 8h (heuristic ≈ 0 long-range)", ratio_8h > 10.0,
		"ratio=%s" % str(ratio_8h))
	_report.append("river/heuristic |a| ratio: 8h=%s 12h=%s 16h=%s 24h=%s" % [
		str(ratio_8h),
		str(mag_r[1] / mag_h[1]) if mag_h[1] > 1e-12 else "~0",
		str(mag_r[2] / mag_h[2]) if mag_h[2] > 1e-12 else "~0",
		str(mag_r[3] / mag_h[3]) if mag_h[3] > 1e-12 else "~0"])


func _test_occupancy_modes() -> void:
	print("── (v) 200-step occupancy per mode (identical ICs) + timing ──")
	sim.num_clusters = 1
	sim.cluster_separation = 0.0
	sim.field_attractor_init = true
	sim.gravity_mode = 0
	sim.river_calibrate_gn = true
	sim.reinit()
	sim.playing = false
	# Identical ICs for every mode: capture after the first (river) init.
	var pos0 := _read_pos_all()
	var vel0 := _read_vel_all()
	var modes: Array = [0, 1, 2]
	var names: Array = ["RIVER(calib)", "HEURISTIC", "PLUMMER"]
	var timings := {}
	var occs := {}
	for mi in range(modes.size()):
		var md: int = int(modes[mi])
		sim.gravity_mode = md
		sim.river_calibrate_gn = (md == 0)  # river calibrated; others G_N = 1
		sim.reinit()
		sim.playing = false
		_write_pos_vel(pos0, vel0)
		# 50 warmup steps (pipeline compile + one-time reports), then 100
		# timed steps with no readbacks, then 50 steps with NaN checks.
		for s in range(50):
			sim._physics_step()
		var t0 := Time.get_ticks_usec()
		for s in range(100):
			sim._physics_step()
		var ms_per: float = float(Time.get_ticks_usec() - t0) / 1e3 / 100.0
		var bad := false
		for s in range(50):
			sim._physics_step()
			if s % 25 == 0:
				if not _positions_finite():
					bad = true
		if not _positions_finite():
			bad = true
		var occ := _occupancy_counts()
		timings[md] = ms_per
		occs[md] = occ
		print("  %s: %.3f ms/step | inner=%.1f%% face/edge=%.1f%% corner=%.1f%% out=%d" % [
			names[mi], ms_per, occ[0], occ[1], occ[2], occ[3]])
		_check("occupancy[%s]: no NaN/Inf over 200 steps" % names[mi], not bad)
	_report.append("ms/step: river=%.3f heuristic=%.3f plummer=%.3f" % [timings[0], timings[1], timings[2]])
	_report.append("corner%% after 200 steps: river=%.1f heuristic=%.1f plummer=%.1f | out: %d/%d/%d" % [
		occs[0][2], occs[1][2], occs[2][2], occs[0][3], occs[1][3], occs[2][3]])
	_check("occupancy[PLUMMER]: zero out-of-box after 200 steps", occs[2][3] == 0,
		"out=%d" % occs[2][3])
	_check("occupancy[RIVER(calib)]: zero out-of-box after 200 steps", occs[0][3] == 0,
		"out=%d" % occs[0][3])
	# Skip-pass cost win: heuristic/Plummer drop the 7-pass FFT + gradient.
	_check("cost: heuristic ms/step < river ms/step (skip-pass)", timings[1] < timings[0] * 0.98,
		"%.3f vs %.3f" % [timings[1], timings[0]])
	_check("cost: plummer ms/step < river ms/step (skip-pass)", timings[2] < timings[0] * 0.98,
		"%.3f vs %.3f" % [timings[2], timings[0]])
	print("  CLASSIFICATION: heuristic |a| = |G_N·π/ρ·∇q_s| with q_s ≈ EY²+EI²+0.01ρ —")
	print("  a nearly-uniform attractor field makes ∇q_s ≈ 0 → the heuristic is a")
	print("  WEAK-FORCE result (≈ no long-range gravity), reported for reference,")
	print("  NOT counted as a pass or a failure. Its corner/out numbers below are")
	print("  the expected consequence, not a physics success.")
