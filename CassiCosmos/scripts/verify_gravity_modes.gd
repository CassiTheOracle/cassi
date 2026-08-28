extends Node
## Focused verification of the 5-mode gravity selector, the bounded
## (truncated-Plummer) ICs, the opt-in river calibration / attractor
## field init, the cached-acc KDK, the river self-gravity mode, the
## global black_holes_enabled BH toggle, and the RealSim dissipation
## mode (cassi_sim.gd + cassi_nbody_gravity.glsl).
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
##         must reduce ms/step vs river. Modes 0/3/4 (RIVER family)
##         calibrate like river and must hold the cluster; with the
##         black_holes_enabled toggle OFF (the default) the BH condensation
##         + BH-integrate passes are skipped in EVERY mode, and mode 3
##         must not be SLOWER than river (lenient 1.02×; global-RD timing
##         is noisy — reported, not tightened). Mode 4 (REALSIM) keeps the
##         full river chain + per-particle dissipation → no NaN, zero
##         out-of-box like river, and ≤ 1.05× river ms/step (the terms
##         are cheap).
##   (vi)  black_holes_enabled toggle gates the BH sector in ANY mode:
##         from an 8-mass Gaussian blob with 64 ring probes at 8h, mode 0
##         with the toggle OFF equals A0 bit-for-bit (< 1e-9) even with a
##         seeded phantom BH record (8 mass at 4h) — the BH force is
##         gated; toggle ON the phantom perturbs mode 0 MATERIALLY (> 5%
##         of max|A0|). The toggle works in ANY mode: mode 3 with the
##         toggle ON equals the mode-0 toggle-ON result (< 1e-9 — same
##         river arm + same BH term, no mode special case) and mode 3 with
##         the toggle OFF equals A0 (< 1e-9). The A3 == A0 river-arm
##         identity (no records) is kept. Host-side: with the phantom in
##         _bh_init_bytes, 5 _physics_step() calls in mode 0 with the
##         toggle OFF leave the record UNCHANGED (passes gated) and 5
##         calls with the toggle ON advance it (BH-integrate runs — age/
##         mass change).
##   (vii) initial-condition profiles (0 = bounded Plummer / 1 = Gaussian
##         ball / 2 = uniform sphere): per profile, zero out-of-box,
##         max |component| and max radius ≤ fr·extent, retained fraction
##         vs the profile's analytic truncation formula within 2%
##         (Plummer u(r_max); Gaussian erf(z_max) − (2/√π)z_max·e^(−z_max²);
##         uniform min(1,(r_max/a)³)), and a 50-step NaN-stability gate
##         (containment is NOT asserted for the new profiles — their
##         virial tuning is approximate; occupancy is reported).
##   (viii) RealSim mode (gravity_mode == 4): law preservation (all three
##         coefficients at 0 → mode 4 == mode 0 bit-for-bit on the ring/
##         blob chain, <1e-9); drag (zero-mass probe in an empty attractor
##         field: |v| decays by the documented per-step factor
##         (1 − γ·ρ/ρ_ref·dt) within 5%, drag opposes v); viscosity
##         (seeded _field_vel patch: |v − v_field| decays monotonically
##         with factor ≈ (1 − ν·dt) within 5%); friction (blob present:
##         |v| strictly decreases, never reverses, per-step speed loss
##         ≤ μ·|a_g|·dt + ε); stability (50 steps at default coefficients:
##         no NaN, occupancy reported).
##   (ix)  Gaussian-ball IC degenerate regression (the startup-hang
##         config): IC=1 with cluster_separation=60, cluster_radius=50,
##         fr=0.9 → r_max = 7.5 while σ = 50 (r_max ≪ σ). The old
##         rejection sampler stormed (~17 min at 2.5M); the rejection-free
##         inverse-CDF arm must reinit 16k particles in < 3.0 s with zero
##         out-of-box, max radius ≤ r_max + 1e-3, and retained fraction
##         matching F(z_max=0.1061) ≈ 0.00087 within 2%.
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
const PHI_INV3: float = (PHI - 1.0) / (PHI + 1.0)  # φ⁻³ = attractor density scale ≈ 0.236068
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


# Abramowitz & Stegun 7.1.26 erf approximation (max |ε| < 1.5e-7 for
# x ≥ 0 — all uses here are x = r/(√2·σ) ≥ 0). Independent copy of the
# sim's _erf_approx: this Godot 4.7 install exposes no built-in erf().
func _erf_approx(x: float) -> float:
	var t: float = 1.0 / (1.0 + 0.3275911 * x)
	var poly: float = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
	return 1.0 - poly * exp(-x * x)


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")  # sibling node in the verify scene
	if sim == null:
		push_error("verify_gravity_modes: CassiSim not found in scene")
		get_tree().quit(1)
		return
	# PIN the grid-river battery against the campaign defaults (meshless/
	# tree/φ-aspect/dual now default on): every gravity mode here runs the
	# CUBE spectral-Poisson river chain and its analytic references. Set
	# BEFORE the extent read so N/h/extent reflect the cube, and reinit
	# (after shaders settle) so the sim's IC/extents are cube too.
	sim.meshless_mode = false
	sim.meshless_gravity = false
	sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	sim.dual_grid = false
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
		push_error("verify_gravity_modes: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	print("verify_gravity_modes: shaders ready after %d extra frames" % waited)
	sim.reinit()  # re-materialize the cube grid / single-lattice / meshless-off state
	sim.playing = false
	_run_all()
	get_tree().quit(0 if _failures == 0 else 1)


# ═══════════════════════════════════════════════════════════════════════
# Buffer plumbing
# ═══════════════════════════════════════════════════════════════════════

func _nbody_pc(pass_mode: float) -> PackedByteArray:
	# Same 15 fields the sim encodes into _nbody_pc_bytes per step
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
	pc.encode_float(48, sim.realsim_drag)
	pc.encode_float(52, sim.realsim_viscosity)
	pc.encode_float(56, sim.realsim_friction)
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
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(pass_mode), 60)
	sim._rd.compute_list_dispatch(cl, ceili(float(sim.N_particles) / 256.0), 1, 1)
	sim._rd.compute_list_end()


# Full river chain: poisson → gradient pass → nbody pass, one compute
# list with barriers (the _step_dispatches ordering, minus clear/deposit —
# rho is written directly here). With warmup=true, an acceleration
# warm-up dispatch (pass_mode 2.0, the KDK first-step cache) runs between
# the gradient and the particle pass — needed by the RealSim tests so the
# first measured step sees a fresh acc cache (the cached-acc KDK contract).
func _run_river_chain(warmup: bool = false) -> void:
	var cl = sim._rd.compute_list_begin()
	sim._dispatch_poisson(cl)
	sim._barrier(cl)  # poisson → gradient
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(1.0), 60)  # gradient pass
	sim._rd.compute_list_dispatch(cl, N, N, 1)
	sim._barrier(cl)  # gradient → warmup
	if warmup:
		sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
		sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
		sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
		sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
		sim._rd.compute_list_set_push_constant(cl, _nbody_pc(2.0), 60)  # acc warm-up
		sim._rd.compute_list_dispatch(cl, ceili(float(sim.N_particles) / 256.0), 1, 1)
		sim._barrier(cl)  # warmup → nbody
	sim._rd.compute_list_bind_compute_pipeline(cl, sim._nbody_pipe)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_0, 0)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_1, 1)
	sim._rd.compute_list_bind_uniform_set(cl, sim._us_nbody_2, 2)
	sim._rd.compute_list_set_push_constant(cl, _nbody_pc(0.0), 60)  # particle pass
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


# Max PER-PROBE relative deviation: max_k |Δ_k| / |a_k| (each probe's own
# magnitude as the scale). Used for the exact-equality checks (< 1e-9).
func _max_rel_dev(a: Array, b: Array) -> float:
	var worst := 0.0
	for kk in range(a.size()):
		var mag: float = a[kk].length()
		var dev: float = (b[kk] - a[kk]).length() / maxf(mag, 1e-30)
		worst = maxf(worst, dev)
	return worst


# Global-scale deviation: max_k |Δ_k| / max_k |a_k|. Used for the
# "material perturbation" check (the BH pull must move the max ring force
# by > 5% of its own scale).
func _max_dev_over_max(a: Array, b: Array) -> float:
	var max_mag := 0.0
	var max_dev := 0.0
	for kk in range(a.size()):
		max_mag = maxf(max_mag, a[kk].length())
		max_dev = maxf(max_dev, (b[kk] - a[kk]).length())
	return max_dev / maxf(max_mag, 1e-30)


# Read one BH record (2 vec4s = 32 bytes): [pos.xyz, mass, vel.xyz, age].
func _read_bh_record(slot: int) -> PackedFloat32Array:
	sim._ensure_synced()
	var base := 64 + slot * 32
	return sim._rd.buffer_get_data(sim._bh_buf, base, 32).to_float32_array()


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
	_test_bh_toggle()
	_test_initial_conditions()
	_test_gaussian_degenerate()
	_test_realsim_mode()
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
	var modes: Array = [0, 1, 2, 3, 4]
	var names: Array = ["RIVER(calib)", "HEURISTIC", "PLUMMER", "RIVER-SELF", "REALSIM"]
	var timings := {}
	var occs := {}
	for mi in range(modes.size()):
		var md: int = int(modes[mi])
		sim.gravity_mode = md
		sim.river_calibrate_gn = (md == 0 or md == 3 or md == 4)  # river modes calibrated; others G_N = 1
		sim.reinit()
		sim.playing = false
		_write_pos_vel(pos0, vel0)
		# 50 warmup steps (pipeline compile + one-time reports), then 1000
		# timed steps with no readbacks, then a final 200-step stability
		# window with NaN checks. The longer timing window suppresses the
		# sub-0.1 ms global-RD scheduling jitter in the mode-3 comparison.
		for s in range(50):
			sim._physics_step()
		var timing_steps := 1000
		var t0 := Time.get_ticks_usec()
		for s in range(timing_steps):
			sim._physics_step()
		var ms_per: float = float(Time.get_ticks_usec() - t0) / 1e3 / float(timing_steps)
		var bad := false
		for s in range(200):
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
	_report.append("ms/step: river=%.3f heuristic=%.3f plummer=%.3f river-self=%.3f realsim=%.3f" % [
		timings[0], timings[1], timings[2], timings[3], timings[4]])
	_report.append("corner%% after 200 steps: river=%.1f heuristic=%.1f plummer=%.1f river-self=%.1f realsim=%.1f | out: %d/%d/%d/%d/%d" % [
		occs[0][2], occs[1][2], occs[2][2], occs[3][2], occs[4][2],
		occs[0][3], occs[1][3], occs[2][3], occs[3][3], occs[4][3]])
	_check("occupancy[PLUMMER]: zero out-of-box after 200 steps", occs[2][3] == 0,
		"out=%d" % occs[2][3])
	_check("occupancy[RIVER(calib)]: zero out-of-box after 200 steps", occs[0][3] == 0,
		"out=%d" % occs[0][3])
	_check("occupancy[RIVER-SELF]: zero out-of-box after 200 steps", occs[3][3] == 0,
		"out=%d" % occs[3][3])
	_check("occupancy[REALSIM]: zero out-of-box after 200 steps", occs[4][3] == 0,
		"out=%d" % occs[4][3])
	# Skip-pass cost win: heuristic/Plummer drop the 7-pass FFT + gradient.
	_check("cost: heuristic ms/step < river ms/step (skip-pass)", timings[1] < timings[0] * 0.98,
		"%.3f vs %.3f" % [timings[1], timings[0]])
	_check("cost: plummer ms/step < river ms/step (skip-pass)", timings[2] < timings[0] * 0.98,
		"%.3f vs %.3f" % [timings[2], timings[0]])
	# Mode 3 skips the condensation + BH-integrate passes (the BH toggle is
	# OFF — the default, so mode 0 skips them too) → must not be SLOWER
	# than river. Lenient 1.02×: global-RD timing is noisy; report the
	# actual ms/step rather than tightening.
	_check("cost: river-self ms/step ≤ river ms/step (skips BH passes, lenient)", timings[3] < timings[0] * 1.02,
		"%.3f vs %.3f" % [timings[3], timings[0]])
	# Mode 4 (RealSim) keeps the FULL river chain (poisson + gradient)
	# plus the per-particle dissipation — the three terms are cheap (one
	# extra ρ trilinear + one fvel trilinear + a few flops per particle),
	# so mode 4 must stay within 5% of river's ms/step. The BH passes are
	# skipped here too (toggle off by default).
	_check("cost: realsim ms/step ≤ river ms/step × 1.05 (cheap dissipation)", timings[4] < timings[0] * 1.05,
		"%.3f vs %.3f" % [timings[4], timings[0]])
	print("  CLASSIFICATION: heuristic |a| = |G_N·π/ρ·∇q_s| with q_s ≈ EY²+EI²+0.01ρ —")
	print("  a nearly-uniform attractor field makes ∇q_s ≈ 0 → the heuristic is a")
	print("  WEAK-FORCE result (≈ no long-range gravity), reported for reference,")
	print("  NOT counted as a pass or a failure. Its corner/out numbers below are")
	print("  the expected consequence, not a physics success.")


func _test_bh_toggle() -> void:
	print("── (vi) black_holes_enabled toggle: gates the BH sector in ANY mode ──")
	sim.gravity_mode = 0
	sim.river_calibrate_gn = false  # G_N = 1, same convention as _test_blob_ratio
	sim.field_attractor_init = true
	sim.num_clusters = 1
	sim.cluster_separation = 0.0
	sim.black_holes_enabled = false  # default — particles only; encoded by reinit
	sim.reinit()
	sim.playing = false
	_upload_bh()
	_write_gaussian_blob(8.0, 2.0 * h)  # total 8, σ = 2h = 4.6875
	var NPROBE := 64
	var r: float = 8.0 * h
	# _set_ring_probes resets pos/vel/acc to the pristine ring BEFORE every
	# chain — the KDK leaves the cached acc non-zero between runs, which
	# would drift the probes and break the exact-equality checks.
	# 1. Baseline A0: mode 0, toggle OFF, no BH records → A0.
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 0
	_run_river_chain()
	var A0 := _read_accs(NPROBE)
	# 2. River-arm identity (kept from the river-self battery): mode 3 with
	#    no BH records == A0 (<1e-9) — with the toggle off both modes are
	#    river-only; the toggle defaults off, so this holds at the scene
	#    default too.
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 3
	_run_river_chain()
	var A3 := _read_accs(NPROBE)
	var dev_a3 := _max_rel_dev(A0, A3)
	_check("bh-toggle: A3 == A0 without BH records (<1e-9)", dev_a3 < 1e-9,
		"max rel |Δ|/|A0| = %s" % str(dev_a3))
	# 3. Toggle-off ignores a phantom: seed the phantom BH record (8 mass
	#    at (4h,0,0), slot 0 = bytes 64..79), mode 0, toggle still off.
	#    _run_river_chain does not re-upload _bh_init_bytes, so the record
	#    survives; the uploaded header's bh[3].x toggle bit is 0.
	var phantom := PackedFloat32Array([4.0 * h, 0.0, 0.0, 8.0])
	sim._rd.buffer_update(sim._bh_buf, 64, 16, phantom.to_byte_array())
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 0
	_run_river_chain()
	var A0p := _read_accs(NPROBE)
	var dev_a0p := _max_rel_dev(A0, A0p)
	_check("bh-toggle: A0 == A0+phantom with toggle OFF (<1e-9) — BH force gated", dev_a0p < 1e-9,
		"max rel |Δ|/|A0| = %s" % str(dev_a0p))
	# 4. Toggle-on feels the phantom: re-encode bh[3].x = 1.0 into
	#    _bh_init_bytes the SAME way _apply_gravity_calibration does (NO
	#    reinit — reinit regenerates the attractor field noise and clears
	#    the density blob, which would break the <1e-9 equalities below;
	#    the reinit/calibration encode path is exercised by step 1 and the
	#    runtime per-frame encode), then the BH pull must be MATERIAL (the
	#    8-mass point source at 4h clearly perturbs the 8h ring).
	sim.black_holes_enabled = true
	sim._bh_init_bytes.encode_float(48, 1.0)
	_upload_bh()
	sim._rd.buffer_update(sim._bh_buf, 64, 16, phantom.to_byte_array())
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 0
	_run_river_chain()
	var B0 := _read_accs(NPROBE)
	var dev_b0 := _max_dev_over_max(A0, B0)
	_check("bh-toggle: BH pull material in mode 0 with toggle ON (>5% of max|A0|)", dev_b0 > 0.05,
		"max |B0−A0|/max|A0| = %s" % str(dev_b0))
	# 5. The toggle works in ANY mode: with the phantom + toggle ON, mode 3
	#    must equal the mode-0 toggle-ON result (<1e-9 — identical river
	#    arm + identical BH term; mode 3 is no longer special-cased).
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 3
	_run_river_chain()
	var B3 := _read_accs(NPROBE)
	var dev_b3 := _max_rel_dev(B0, B3)
	_check("bh-toggle: mode-3 toggle-ON == mode-0 toggle-ON (<1e-9) — no mode special case", dev_b3 < 1e-9,
		"max rel |Δ|/|B0| = %s" % str(dev_b3))
	# 6. Toggle OFF (re-encode bh[3].x = 0.0, no reinit — same field state
	#    as A0/B0/B3, so the only changed input is the toggle), mode 3 with
	#    the phantom → must equal A0: the BH term is gated by the TOGGLE,
	#    off in mode 3 too.
	sim.black_holes_enabled = false
	sim._bh_init_bytes.encode_float(48, 0.0)
	_upload_bh()
	sim._rd.buffer_update(sim._bh_buf, 64, 16, phantom.to_byte_array())
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 3
	_run_river_chain()
	var A3p := _read_accs(NPROBE)
	var dev_a3p := _max_rel_dev(A0, A3p)
	_check("bh-toggle: mode-3 toggle-OFF == A0 with phantom present (<1e-9)", dev_a3p < 1e-9,
		"max rel |Δ|/|A0| = %s" % str(dev_a3p))
	# 7. Host-skip proof (the TOGGLE gates the passes, not the mode):
	#    _physics_step re-uploads _bh_init_bytes every step, so seed the
	#    phantom into it (floats 16/19 = bh[4].x/.w). Toggle OFF in mode 0
	#    → neither pass touches the record (unchanged); toggle ON (reinit
	#    to re-encode) + re-seed → the BH-integrate pass advances it
	#    (age += 1 per step, mass += acc_rate·qi·cell_vol).
	var phantom_full: PackedFloat32Array = sim._bh_init_bytes.to_float32_array()
	phantom_full[16] = 4.0 * h  # bh[4].x — pos.x
	phantom_full[19] = 8.0      # bh[4].w — mass
	sim._bh_init_bytes = phantom_full.to_byte_array()
	sim.gravity_mode = 0
	for s in range(5):
		sim._physics_step()
	var rec_off := _read_bh_record(0)
	var off_unchanged: bool = rec_off[3] == 8.0 and rec_off[7] == 0.0
	_check("bh-toggle: host skips BH passes — record unchanged after 5 steps, mode 0, toggle OFF", off_unchanged,
		"mass=%s age=%s" % [str(rec_off[3]), str(rec_off[7])])
	sim.black_holes_enabled = true
	sim.reinit()  # re-encodes bh[3].x = 1.0 (and resets _bh_init_bytes)
	sim.playing = false
	var phantom_full2: PackedFloat32Array = sim._bh_init_bytes.to_float32_array()
	phantom_full2[16] = 4.0 * h
	phantom_full2[19] = 8.0
	sim._bh_init_bytes = phantom_full2.to_byte_array()
	sim.gravity_mode = 0
	for s in range(5):
		sim._physics_step()
	var rec_on := _read_bh_record(0)
	var on_changed: bool = rec_on[7] > 0.0 or rec_on[3] != 8.0
	_check("bh-toggle: BH-integrate runs with toggle ON — record changed after 5 steps", on_changed,
		"mass=%s age=%s" % [str(rec_on[3]), str(rec_on[7])])
	# Restore the default (off) for the rest of the battery — the following
	# tests reinit, and _apply_gravity_calibration encodes this value.
	sim.black_holes_enabled = false
	_report.append("bh-toggle: A3/A0 dev=%s  phantom/OFF dev=%s  B0-material=%s  B3/B0 dev=%s  mode3-OFF dev=%s | 5-step rec OFF: mass=%s age=%s  ON: mass=%s age=%s" % [
		str(dev_a3), str(dev_a0p), str(dev_b0), str(dev_b3), str(dev_a3p),
		str(rec_off[3]), str(rec_off[7]), str(rec_on[3]), str(rec_on[7])])


func _test_initial_conditions() -> void:
	print("── (vii) initial-condition profiles: bounded Plummer / Gaussian ball / uniform sphere ──")
	var fr: float = sim.initial_radius_fraction
	var a_s: float = sim.cluster_radius
	var r_max: float = fr * extent  # single cluster at the origin
	# Analytic retained fractions of the UNBOUNDED profile inside r_max:
	#   Plummer  u(r_max) = (x²/(1+x²))^{3/2},  x = r_max/a
	#   Gaussian erf(z) − (2/√π)·z·e^(−z²),     z = r_max/(√2·σ)
	#   Uniform  min(1, (r_max/a)³)
	var z_max: float = r_max / (sqrt(2.0) * a_s)
	var analytics := [
		pow(pow(r_max / a_s, 2.0) / (1.0 + pow(r_max / a_s, 2.0)), 1.5),
		_erf_approx(z_max) - (2.0 / sqrt(PI)) * z_max * exp(-z_max * z_max),
		minf(1.0, pow(r_max / a_s, 3.0)),
	]
	var ic_names := ["Plummer", "Gaussian", "Uniform"]
	for p in range(3):
		sim.initial_condition = p
		sim.field_attractor_init = true
		sim.num_clusters = 1
		sim.cluster_separation = 0.0
		sim.gravity_mode = 0
		sim.river_calibrate_gn = false
		sim.reinit()
		sim.playing = false
		var lim: float = fr * extent
		_check("IC[%s]: zero out-of-box" % ic_names[p], sim._init_out_of_box == 0,
			"out=%d" % sim._init_out_of_box)
		_check("IC[%s]: max |component| ≤ fr·extent" % ic_names[p], sim._init_max_component <= lim + 1e-3,
			"max_comp=%.3f lim=%.3f" % [sim._init_max_component, lim])
		_check("IC[%s]: max radius ≤ fr·extent" % ic_names[p], sim._init_max_radius <= lim + 1e-3,
			"max_r=%.3f" % sim._init_max_radius)
		var rel: float = absf(sim._init_retained_fraction - analytics[p]) / maxf(analytics[p], 1e-9)
		_check("IC[%s]: retained fraction matches analytic (2%%)" % ic_names[p], rel < 0.02,
			"retained=%.4f analytic=%.4f" % [sim._init_retained_fraction, analytics[p]])
		# NaN-stability gate only — the new profiles' virial tuning is
		# approximate, so containment is NOT asserted for them (reported).
		var bad := false
		for s in range(50):
			sim._physics_step()
			if s % 25 == 0:
				if not _positions_finite():
					bad = true
		if not _positions_finite():
			bad = true
		var occ := _occupancy_counts()
		print("  IC[%s]: after 50 steps — inner=%.1f%% face/edge=%.1f%% corner=%.1f%% out=%d" % [
			ic_names[p], occ[0], occ[1], occ[2], occ[3]])
		_check("IC[%s]: no NaN/Inf over 50 steps" % ic_names[p], not bad)
		_report.append("IC[%s]: retained=%.4f (analytic %.4f)  max_r=%.1f  out_of_box=%d | after 50 steps: inner=%.1f%% out=%d" % [
			ic_names[p], sim._init_retained_fraction, analytics[p], sim._init_max_radius,
			sim._init_out_of_box, occ[0], occ[3]])


# ═══════════════════════════════════════════════════════════════════════
# RealSim helpers (gravity_mode == 4)
# ═══════════════════════════════════════════════════════════════════════

# Single velocity probe: particle 0 at wp with velocity v (zero mass — no
# deposit, no BH term), everything else zeroed. The drag/viscosity/friction
# tests integrate ONE particle through the KDK.
func _set_velocity_probe(wp: Vector3, v: Vector3) -> void:
	var npart: int = sim.N_particles
	var pos = PackedFloat32Array(); pos.resize(npart * 4)
	var vel = PackedFloat32Array(); vel.resize(npart * 4)
	var acc = PackedFloat32Array(); acc.resize(npart * 4)
	pos[0] = wp.x; pos[1] = wp.y; pos[2] = wp.z; pos[3] = 0.0
	vel[0] = v.x; vel[1] = v.y; vel[2] = v.z; vel[3] = 0.0
	sim._rd.buffer_update(sim._pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	sim._rd.buffer_update(sim._vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	sim._rd.buffer_update(sim._acc_buf, 0, acc.size() * 4, acc.to_byte_array())


func _read_vel0() -> Vector3:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._vel_buf, 0, 16)
	var f = d.to_float32_array()
	return Vector3(f[0], f[1], f[2])


func _read_acc0() -> Vector3:
	sim._ensure_synced()
	var d = sim._rd.buffer_get_data(sim._acc_buf, 0, 16)
	var f = d.to_float32_array()
	return Vector3(f[0], f[1], f[2])


# Seed the FieldVel buffer (set 0 binding 3 — the RealSim viscosity input)
# with a uniform known medium velocity. Uniform patch: the probe's path
# stays inside it.
func _seed_field_vel(v: Vector3) -> void:
	var vel = PackedFloat32Array(); vel.resize(nc * 4)
	for i in range(nc):
		vel[i * 4] = v.x; vel[i * 4 + 1] = v.y; vel[i * 4 + 2] = v.z; vel[i * 4 + 3] = 0.0
	sim._rd.buffer_update(sim._field_vel, 0, vel.size() * 4, vel.to_byte_array())


# Trilinear ρ = EY + EI at wp from the ACTUAL field readback — mirrors the
# shader's rho_local_at (tri_ey + tri_ei, periodic wrap, same coordinate
# convention). float64 here vs float32 in the shader: agree to ~1e-7.
func _field_rho_at(wp: Vector3) -> float:
	sim._ensure_synced()
	var ey = sim._rd.buffer_get_data(sim._field_ey, 0, nc * 4).to_float32_array()
	var ei = sim._rd.buffer_get_data(sim._field_ei, 0, nc * 4).to_float32_array()
	var hn := float(N) * 0.5
	var gc: Vector3 = wp * (hn / extent) + Vector3(hn, hn, hn)
	var i0 := int(floor(gc.x)); var j0 := int(floor(gc.y)); var k0 := int(floor(gc.z))
	var fx := gc.x - float(i0); var fy := gc.y - float(j0); var fz := gc.z - float(k0)
	i0 = ((i0 % N) + N) % N; j0 = ((j0 % N) + N) % N; k0 = ((k0 % N) + N) % N
	var i1 := (i0 + 1) % N; var j1 := (j0 + 1) % N; var k1 := (k0 + 1) % N
	var r000: float = ey[i0 + N * (j0 + N * k0)] + ei[i0 + N * (j0 + N * k0)]
	var r100: float = ey[i1 + N * (j0 + N * k0)] + ei[i1 + N * (j0 + N * k0)]
	var r010: float = ey[i0 + N * (j1 + N * k0)] + ei[i0 + N * (j1 + N * k0)]
	var r110: float = ey[i1 + N * (j1 + N * k0)] + ei[i1 + N * (j1 + N * k0)]
	var r001: float = ey[i0 + N * (j0 + N * k1)] + ei[i0 + N * (j0 + N * k1)]
	var r101: float = ey[i1 + N * (j0 + N * k1)] + ei[i1 + N * (j0 + N * k1)]
	var r011: float = ey[i0 + N * (j1 + N * k1)] + ei[i0 + N * (j1 + N * k1)]
	var r111: float = ey[i1 + N * (j1 + N * k1)] + ei[i1 + N * (j1 + N * k1)]
	var q0: float = lerpf(lerpf(r000, r100, fx), lerpf(r010, r110, fx), fy)
	var q1: float = lerpf(lerpf(r001, r101, fx), lerpf(r011, r111, fx), fy)
	return lerpf(q0, q1, fz)


# ═══════════════════════════════════════════════════════════════════════
# (viii) RealSim mode — law preservation + drag/viscosity/friction
# ═══════════════════════════════════════════════════════════════════════
func _test_realsim_mode() -> void:
	print("── (viii) RealSim mode (gravity_mode = 4): law + dissipation ──")
	var DEF_D: float = sim.realsim_drag
	var DEF_V: float = sim.realsim_viscosity
	var DEF_F: float = sim.realsim_friction
	sim.field_attractor_init = true
	sim.num_clusters = 1
	sim.cluster_separation = 0.0
	sim.gravity_mode = 4
	sim.river_calibrate_gn = false  # G_N = 1, the blob-test convention

	# 1. LAW PRESERVATION: with all three coefficients at 0, mode 4 must be
	# bit-identical to mode 0 on the ring/blob chain (the A3==A0 pattern:
	# same operations, no BH records → the BH term contributes exactly 0 in
	# both modes; dissipation contributes exactly 0 with zero coefficients).
	sim.realsim_drag = 0.0
	sim.realsim_viscosity = 0.0
	sim.realsim_friction = 0.0
	sim.reinit()
	sim.playing = false
	_upload_bh()
	_write_gaussian_blob(8.0, 2.0 * h)
	var NPROBE := 64
	var r: float = 8.0 * h
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 0
	_run_river_chain()
	var A0 := _read_accs(NPROBE)
	_set_ring_probes(NPROBE, r, Vector3.ZERO)
	sim.gravity_mode = 4
	_run_river_chain()
	var A4 := _read_accs(NPROBE)
	var dev_law := _max_rel_dev(A0, A4)
	_check("realsim-law: A4 == A0 with all coefficients 0 (<1e-9)", dev_law < 1e-9,
		"max rel |Δ|/|A0| = %s" % str(dev_law))

	# 2. DRAG: zero-mass probe, empty field (rho=0 → Φ=0 → no gravity),
	# attractor field present (ρ_local = EY+EI ≈ (1+φ)·0.01). Expected
	# per-step decay |v| → |v|·(1 − γ·(ρ_local/ρ_ref)·dt), ρ_ref = φ⁻³.
	# γ = 5.0 here (test coefficient, same formula — stronger signal than
	# the 0.5 default). The KDK's cached-acc recurrence gives the EXACT
	# per-step factor (1 − γ·ρ/ρ_ref·dt) in steady state (verified
	# algebraically); the warm-up's step-1 evaluation at the current (not
	# half-kick) velocity differs by O((γ·ρ/ρ_ref·dt)²) ≈ 1e-7 — negligible
	# against the 5% band.
	var GAMMA := 5.0
	sim.realsim_drag = GAMMA
	sim.realsim_viscosity = 0.0
	sim.realsim_friction = 0.0
	sim.reinit()
	sim.playing = false
	_upload_bh()
	_write_gaussian_blob(0.0, 2.0 * h)  # empty field — no gravity
	var wp_d := Vector3(8.0 * h, 0.0, 0.0)
	var v0_d := Vector3(1.0, 0.0, 0.0)
	_set_velocity_probe(wp_d, v0_d)
	var rho_loc: float = _field_rho_at(wp_d)
	var rho_ratio: float = rho_loc / PHI_INV3
	var ND := 200
	var f_pred_d: float = pow(1.0 - GAMMA * rho_ratio * sim.dt, float(ND))
	var drag_bad_fac := false
	var drag_bad_dot := false
	var v_prev := v0_d
	for s in range(ND):
		_run_river_chain(s == 0)  # warm-up only on step 1 (the KDK contract)
		var v := _read_vel0()
		var a := _read_acc0()
		if s == ND - 1:
			var f_meas: float = v.length() / v0_d.length()
			drag_bad_fac = absf(f_meas - f_pred_d) / maxf(f_pred_d, 1e-30) > 0.05
			drag_bad_dot = a.dot(v) >= 0.0  # drag opposes v
		v_prev = v
	_check("realsim-drag: |v| decay factor within 5%% after %d steps" % ND, not drag_bad_fac,
		"meas=%.4f pred=%.4f (γ=%.1f, ρ/ρ_ref=%.4f)" % [v_prev.length() / v0_d.length(), f_pred_d, GAMMA, rho_ratio])
	_check("realsim-drag: drag opposes v (a·v < 0)", not drag_bad_dot,
		"a·v = %s" % str(_read_acc0().dot(v_prev)))

	# 3. VISCOSITY: seed _field_vel (the evolved FieldVel buffer — the
	# RealSim medium velocity) with a known uniform patch (0.5, 0, 0); probe
	# at rest → u = v − v_field, |u₀| = 0.5. Expected per-step relaxation
	# |u| → |u|·(1 − ν·dt), ν = 10.0 (test coefficient). The KDK gives the
	# exact steady-state factor (1 − ν·dt); assert monotone decrease + the
	# final factor within 5%.
	var NU := 10.0
	sim.realsim_drag = 0.0
	sim.realsim_viscosity = NU
	sim.realsim_friction = 0.0
	sim.reinit()
	sim.playing = false
	_upload_bh()
	_write_gaussian_blob(0.0, 2.0 * h)
	var v_field := Vector3(0.5, 0.0, 0.0)
	_seed_field_vel(v_field)
	_set_velocity_probe(Vector3.ZERO, Vector3.ZERO)
	var NV := 100
	var u0: float = (Vector3.ZERO - v_field).length()
	var f_pred_v: float = pow(1.0 - NU * sim.dt, float(NV))
	var visc_mono := true
	var u_prev := u0
	for s in range(NV):
		_run_river_chain(s == 0)
		var u: float = (_read_vel0() - v_field).length()
		if s > 0 and u >= u_prev:
			visc_mono = false
		u_prev = u
	var f_meas_v: float = u_prev / maxf(u0, 1e-30)
	_check("realsim-visc: |v − v_field| decreases monotonically", visc_mono)
	_check("realsim-visc: |v − v_field| factor within 5%% of (1−ν·dt)^%d" % NV,
		absf(f_meas_v - f_pred_v) / maxf(f_pred_v, 1e-30) < 0.05,
		"meas=%.4f pred=%.4f (ν=%.1f)" % [f_meas_v, f_pred_v, NU])

	# 4. FRICTION: blob present (gravity on), drag=visc=0, μ = 0.5 (test
	# coefficient). Probe at 4h on a CIRCULAR orbit (v0 = sqrt(|a_g|·r)
	# tangential, |a_g| measured from a coefficients-0 run) → gravity ⊥ v,
	# does no work on |v|; friction alone reduces the speed. Assert: |v|
	# strictly decreases, never reverses (v·v̂₀ ≥ 0), and per-step |Δ|v|| ≤
	# μ·|a_g|·dt + ε, ε = 5% slack (float32 + the tiny residual gravity work
	# as the orbit arcs — the estimator, not a loosened tolerance).
	var MU := 0.5
	sim.realsim_drag = 0.0
	sim.realsim_viscosity = 0.0
	sim.realsim_friction = 0.0
	sim.reinit()
	sim.playing = false
	_upload_bh()
	_write_gaussian_blob(64.0, 2.0 * h)  # heavier blob → measurable per-step loss
	var wp_f := Vector3(4.0 * h, 0.0, 0.0)
	_set_velocity_probe(wp_f, Vector3(0.0, 1.0, 0.0))
	_run_river_chain(true)  # measure |a_g| (pure gravity, μ = 0)
	var a_g: float = _read_acc0().length()
	# Circular velocity at r = 4h: gravity is centripetal (⊥ v, no work).
	var v_circ := sqrt(a_g * wp_f.length())
	var v0_f := Vector3(0.0, v_circ, 0.0)
	sim.realsim_friction = MU
	_set_velocity_probe(wp_f, v0_f)
	var NF := 100
	var eps_f: float = 0.05 * MU * a_g * sim.dt + 1e-9
	var fric_strict := true
	var fric_rev := true
	var fric_bound := true
	var vhat0 := v0_f.normalized()
	var v_prev_f := v0_f
	for s in range(NF):
		_run_river_chain(s == 0)
		var v := _read_vel0()
		if v.length() >= v_prev_f.length():
			fric_strict = false
		if v.dot(vhat0) < 0.0:
			fric_rev = false
		if absf(v.length() - v_prev_f.length()) > MU * a_g * sim.dt + eps_f:
			fric_bound = false
		v_prev_f = v
	_check("realsim-fric: |v| strictly decreases (gravity ⊥ v, friction only)", fric_strict,
		"|v|: %.6f → %.6f (|a_g|=%.6f, v_circ=%.4f)" % [v0_f.length(), v_prev_f.length(), a_g, v_circ])
	_check("realsim-fric: velocity never reverses (v·v̂₀ ≥ 0)", fric_rev)
	_check("realsim-fric: per-step |Δ|v|| ≤ μ·|a_g|·dt + ε", fric_bound,
		"μ·|a_g|·dt=%s ε=%s" % [str(MU * a_g * sim.dt), str(eps_f)])

	# 5. STABILITY: 50 full-chain steps at DEFAULT coefficients — no NaN,
	# occupancy reported (the dissipation runs through the real step chain
	# with the live PDE field).
	sim.realsim_drag = DEF_D
	sim.realsim_viscosity = DEF_V
	sim.realsim_friction = DEF_F
	sim.gravity_mode = 4
	sim.river_calibrate_gn = true
	sim.reinit()
	sim.playing = false
	var stab_bad := false
	for s in range(50):
		sim._physics_step()
		if s % 25 == 0:
			if not _positions_finite():
				stab_bad = true
	if not _positions_finite():
		stab_bad = true
	var occ := _occupancy_counts()
	_check("realsim-stability: no NaN/Inf over 50 steps at default coefficients", not stab_bad)
	print("  REALSIM 50-step occupancy: inner=%.1f%% face/edge=%.1f%% corner=%.1f%% out=%d" % [
		occ[0], occ[1], occ[2], occ[3]])
	_report.append("realsim: law-dev=%s  drag: ρ/ρ_ref=%.4f  visc-mono=%s  fric: |a_g|=%.6f strict=%s | 50-step occ: inner=%.1f%% out=%d" % [
		str(dev_law), rho_ratio, str(visc_mono), a_g, str(fric_strict), occ[0], occ[3]])


# ═══════════════════════════════════════════════════════════════════════
# (ix) Gaussian-ball IC degenerate regression — the exact config that
# hung the user's startup (main.tscn pins IC=1, cluster_separation=60):
# r_max = fr·extent − sep = 0.9·75 − 60 = 7.5 while σ = 50 → the OLD
# rejection sampler drew ~660 rejected particles per placed particle
# (~17 min at 2.5M). The rejection-free inverse-CDF arm must complete a
# full 16k-particle reinit in < 3.0 s with the analytic truncation
# invariants intact (retained F(z_max) ≈ 0.00087, no out-of-box, all
# radii ≤ r_max).
# ═══════════════════════════════════════════════════════════════════════
func _test_gaussian_degenerate() -> void:
	print("── (ix) Gaussian-ball IC, degenerate truncation (r_max ≪ σ) ──")
	var fr_save: float = sim.initial_radius_fraction
	var sep_save: float = sim.cluster_separation
	var ic_save: int = sim.initial_condition
	sim.num_clusters = 1
	sim.cluster_radius = 50.0  # σ — stays at the scene default
	sim.cluster_separation = 60.0  # the degenerate offset: r_max = 7.5
	sim.initial_radius_fraction = 0.9
	sim.field_attractor_init = true
	sim.initial_condition = 1  # Gaussian ball
	sim.gravity_mode = 0
	sim.river_calibrate_gn = false
	var r_max_d: float = sim.initial_radius_fraction * (sim.cluster_radius * 1.5) - sim.cluster_separation
	var z_max_d: float = r_max_d / (sqrt(2.0) * sim.cluster_radius)
	var f_an_d: float = _erf_approx(z_max_d) - (2.0 / sqrt(PI)) * z_max_d * exp(-z_max_d * z_max_d)
	var t0_d := Time.get_ticks_usec()
	sim.reinit()
	sim.playing = false
	var dt_s: float = float(Time.get_ticks_usec() - t0_d) / 1e6
	_check("gauss-degen: reinit wall-time < 3.0 s (rejection storm pinned)", dt_s < 3.0,
		"t=%.2f s (old rejection sampler: ~6.8 s at 16k)" % dt_s)
	_check("gauss-degen: zero out-of-box", sim._init_out_of_box == 0,
		"out=%d" % sim._init_out_of_box)
	_check("gauss-degen: max radius ≤ r_max + 1e-3 (r_max = fr·extent − sep = %.3f)" % r_max_d,
		sim._init_max_radius <= r_max_d + 1e-3,
		"max_r=%.4f lim=%.4f" % [sim._init_max_radius, r_max_d])
	var rel_d: float = absf(sim._init_retained_fraction - f_an_d) / maxf(f_an_d, 1e-9)
	_check("gauss-degen: retained matches analytic F(z_max) within 2%% (z_max=%.5f)" % z_max_d,
		rel_d < 0.02,
		"retained=%.6f analytic=%.6f" % [sim._init_retained_fraction, f_an_d])
	print("  gauss-degen: reinit=%.2f s | out=%d | max_r=%.4f (lim %.3f) | retained=%.6f (analytic %.6f, z_max=%.5f)" % [
		dt_s, sim._init_out_of_box, sim._init_max_radius, r_max_d,
		sim._init_retained_fraction, f_an_d, z_max_d])
	_report.append("gauss-degen: reinit=%.2f s  retained=%.6f/%.6f  max_r=%.3f≤%.3f  out=%d" % [
		dt_s, sim._init_retained_fraction, f_an_d, sim._init_max_radius, r_max_d, sim._init_out_of_box])
	# restore the battery's config convention
	sim.initial_radius_fraction = fr_save
	sim.cluster_separation = sep_save
	sim.initial_condition = ic_save
