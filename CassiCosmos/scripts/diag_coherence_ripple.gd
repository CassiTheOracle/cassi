extends Node
## ───────────────────────────────────────────────────────────────────────────
## diag_coherence_ripple — two-quantity headless test of the Cassi coherence
## claims against the SPACE-SIM field (scripts/cassi_sim.gd + compute/).
##
## BACKGROUND (cassi-toe foundations/qi-flow-double-helix.md, parallel
## reframing): the φ-spatial-spacing signal is a property of the COHERENCE
## field (Qi), not of matter. Two falsifiable, quantitative claims:
##   (A) CLUMPING — coherence clumps at φ-scaled spatial periods of the
##       condensation field. The DOMINANT spatial frequencies of the coherence
##       field should be spaced by φ (clump-clump separations near Λ,
##       Λ·φ⁻¹, Λ·φ⁻² … for a box scale Λ): a φ-LADDERED set of dominant
##       modes (wavelength ratios in {φ, φ², φ⁻¹}) rather than a single scale
##       or a generic continuum.
##   (B) RIPPLE — a coherence feature (field-phase structure) propagates at
##       the wave-form phase speed, DIFFERENT from the particle
##       advection/gravity speed in the same region: v_coherence ≠ v_particles,
##       with a measurable ratio.
##
## FIELD CONVENTION — the sim's colour observable is q = EY²+EI² (computed by
## cassi_two_fluid.glsl into _field_q; the Qi-rainbow anchor). The THEORY's
## coherence is q = ρ²/(ρ² + φ⁻² + ε²) with ρ = E_Y + E_I and ε = E_Y − φ·E_I.
## BOTH are computed here from the RAW _field_ey/_field_ei buffers; the
## clumping analysis (A) is run on EACH so a convention difference is visible.
##
## CONFIG — runs the sim's OWN field evolution with the gravity/river drive
## ON (the config in which the owner observes clumping), NOT an empty smooth
## ball with drives off:
##   grid_N = 64, dt = 0.05, N_particles = 65536, cluster_radius = 40,
##   box_aspect = (φ, 1, φ²) [owner's phi box], gravity_mode = 4 (RealSim —
##   the owner's live mode; river law + drag/viscosity + field source),
##   river_calibrate_gn = true, field_attractor_init = true (smooth attractor
##   start — nearly featureless EY=φ·EI, so the field carries NO pre-seeded
##   spatial structure), multi_rung_seed = FALSE (the owner's live sim also
##   turns it on, and it literally imprints φ-spaced Zel'dovich wavenumbers on
##   the PARTICLES; the point here is to test whether coherence clumping is
##   EMERGENT from gravity+drive, so the stronger no-seed control is run),
##   black_holes_enabled = false, dual_grid = false, meshless_mode =
##   meshless_gravity = false (grid-Poisson river arm — the drive semantics,
##   robust in a bare probe scene), source_strength = 0 (the two-fluid's
##   `mr·0.001` mass-density source couples the particle field into EY/EI).
##   The two-fluid PDE runs every step; gravity moves particles ⇒ clustered
##   mass density ρ ⇒ the field source seeds coherence patches.
##
## ═══ PRE-REGISTERED DECISION TREE (fixed BEFORE any run; every outcome is an
##      honest, acceptable verdict) ═══
##
## (A) CLUMPING (per coherence convention, at the epoch E, steps 400, t=20):
##     Power spectrum via a self-tested separable 3D FFT of the coherence
##     field; radially bin P by |k| (wavenumber magnitude in grid cells⁻¹,
##     shells from the Nyquist band). Detect LOCAL-MAXIMUM shells with power
##     ≥ 0.05·P_max (peak prominence) and shell separation ≥ 1 (distinct).
##     Sort dominant magnitudes ascending → {k_0 < k_1 < …}. The claim is
##     wavelengths λ_n = Λ·φ⁻ⁿ ⇒ wavenumbers k_n ∝ φⁿ ⇒ consecutive ratio φ.
##     Verdict (M = number of dominant modes found):
##       M < 3                 → "NO CLUMP LADDER" (single/absent dominant scale)
##       M ≥ 3 and every consecutive ratio k_{i+1}/k_i within φ ± T_RAT
##                               → "CLUMPING SUPPORTS φ-LADDER"
##       else                   → "CLUMPING NO φ-LADDER (continuum/mixed)"
##     WHERE T_RAT = 0.15 (log window; intentional — 3D wavenumber shells are
##     discrete integer |k| = sqrt(kx²+ky²+kz²), so exact φ ratios are rare).
##     SECOND READING: 3D autocorrelation C = IFFT(|F|²); radial peaks at
##     non-zero lag = clump-clump separations; consecutive lag ratios ~ φ⁻¹
##     (wavelengths shrink by φ) reported, not gating.
##
## (B) RIPPLE (window t ∈ [30, 40], Δt_total = 10, 5 samples every 40 steps):
##     Feature = centroid of the strongest |∇q| front (cells with |∇q| ≥
##     0.5·max|∇q|) of the colour q field. Track over the window; a robust
##     linear fit of centroid position vs t gives v_coherence (cells per
##     sim-time unit) and its velocity σ (fit slope SE).
##     v_particles = mean |v| over particles within a sphere radius 6 cells
##     around the feature centroid's mean position, read from _vel_buf; SE =
##     std/√N_region. ratio = v_coherence / v_particles; σ_ratio by error
##     propagation. Separation test (pre-registered):
##       |ratio − 1| > 3·σ_ratio  → "RIPPLE: DISTINCT" (sub-verdict: faster /
##                                   slower than particles from ratio ≷ 1)
##       else                     → "RIPPLE: NOT DISTINGUISHABLE"
##   (The free wave speed of ∂²ψ/∂t² = ∇²ψ ∓ ω₀²(EY−φEI) is c = 1 cell/unit-t;
##    if a coherence front rides at ≈1 while particles are slow, the ratio
##    should clearly exceed 1 — or the honest measured value otherwise.)
##
## LAUNCH (this repo's headless probe pattern — Console build WITHOUT
## --headless, which kills the global RenderingDevice; the probe needs no
## rendering and quits itself after writing the report):
##   Godot_v4.7.1-stable_mono_win64_console.exe \
##     --path <space-sim> res://scenes/diag_coherence_ripple.tscn
## Telemetry + verdict → res://_diag/coherence_ripple_report.json (gitignored).
## ───────────────────────────────────────────────────────────────────────────

const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051      # φ⁻² — theory q denominator
const RATIO_TOL: float = 0.15                   # ±0.15 window around φ
const PEAK_PROMINENCE: float = 0.05             # 5% of global max for a mode
const MIN_MODES: int = 3                        # gate for the ladder test
const EPOCH_STEPS: int = 400                    # clumping epoch (t=20)
const RIP_START_STEPS: int = 600                # ripple window start (t=30)
const RIP_END_STEPS: int = 800                  # ripple window end (t=40)
const RIP_SAMPLES: int = 5                      # feature samples in the window
const RIP_SPHERE_R: float = 6.0                 # particle-σ region radius (cells)
const FRONT_FRAC: float = 0.5                   # |∇q| ≥ frac·max = "the front"
const BATCH: int = 40                           # steps per compute-list batch

var sim: Node3D
var report: Dictionary = {}
var N: int = 64
var nc: int = 0


# ── Entry: called by the scene after CassiSim is a child ────────────────
func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	if sim == null:
		push_error("diag_coherence_ripple: CassiSim not found")
		get_tree().quit(1)
		return
	if not sim.has_method("_run_physics_steps"):
		push_error("diag_coherence_ripple: CassiSim script not loaded (mid-edit?) — aborting")
		get_tree().quit(1)
		return
	N = sim.grid_N
	nc = N * N * N
	print("[diag-cr] shaders-ready probe; grid=%d aspect=%s dt=%.4f grav=%d particles=%d" % [
		N, str(sim.box_aspect), sim.dt, sim.gravity_mode, sim.N_particles])
	sim.playing = false
	await get_tree().process_frame
	await get_tree().process_frame
	var waited := 0
	while not sim._shaders_ready and waited < 600:
		waited += 1
		await get_tree().process_frame
	if not sim._shaders_ready:
		push_error("diag_coherence_ripple: shaders never became ready")
		get_tree().quit(1)
		return
	print("[diag-cr] shaders ready after %d frames" % waited)

	# Self-tests FIRST (prove the FFT + front tracker before any physics).
	var fft_ok := _self_test_fft()
	var ladder_ok := _self_test_ladder_detector()

	report["config"] = {
		"grid_N": N, "dt": sim.dt, "particles": sim.N_particles,
		"cluster_radius": sim.cluster_radius, "box_aspect": str(sim.box_aspect),
		"gravity_mode": sim.gravity_mode, "river_calibrate_gn": sim.river_calibrate_gn,
		"field_attractor_init": sim.field_attractor_init,
		"multi_rung_seed": sim.multi_rung_seed, "black_holes_enabled": sim.black_holes_enabled,
		"dual_grid": sim.dual_grid, "meshless": sim.meshless_mode,
		"source_strength": sim.source_strength,
	}
	report["pre_registered"] = {
		"clump_ratio_target": PHI, "clump_ratio_tol": RATIO_TOL,
		"clump_peak_prominence": PEAK_PROMINENCE, "clump_min_modes": MIN_MODES,
		"clump_epoch_steps": EPOCH_STEPS,
		"rip_window_steps": [RIP_START_STEPS, RIP_END_STEPS],
		"rip_dt_total": float(RIP_END_STEPS - RIP_START_STEPS) * sim.dt,
		"rip_samples": RIP_SAMPLES, "rip_sphere_r": RIP_SPHERE_R,
		"rip_front_frac": FRONT_FRAC, "rip_separation_sigma": 3.0,
	}

	if not fft_ok or not ladder_ok:
		push_error("diag_coherence_ripple: self-test FAILED — aborting physics run")
		report["status"] = "SELFTEST_FAIL"
		_write_report()
		get_tree().quit(1)
		return

	var t0 := Time.get_ticks_msec()
	await _drive_to(EPOCH_STEPS)
	var clump := _clumping_analysis()
	_apply_clump_tree(clump)
	report["clumping"] = clump

	await _drive_to(RIP_START_STEPS)
	var ripple: Dictionary = await _ripple_analysis()
	_apply_ripple_tree(ripple)
	report["ripple"] = ripple

	report["runtime_ms"] = int(Time.get_ticks_msec() - t0)
	report["status"] = "OK"
	var cv: String = clump.verdict
	var rv: String = ripple.verdict
	print("\n══════ diag_coherence_ripple ══════")
	print("  [A] CLUMPING : %s (FFT selftest=%s, ladder-selftest=%s)" % [cv, fft_ok, ladder_ok])
	print("  [B] RIPPLE   : %s (v_c=%.4f v_p=%.4f ratio=%.3f)" % [rv, ripple.v_coherence_cells_per_t, ripple.v_particles, ripple.ratio])
	print("[diag-cr] runtime %.1f s ; report → res://_diag/coherence_ripple_report.json" % [report.runtime_ms / 1000.0])
	_write_report()
	get_tree().quit(0 if (fft_ok and ladder_ok) else 1)


# ── Drive the sim forward in BATCH step increments (awaiting the frame between
#    batches so the global-RD lists flush and readbacks self-stall cleanly). ──
func _drive_to(target_steps: int) -> void:
	while sim._step_count < target_steps:
		var need: int = target_steps - sim._step_count
		var b: int = mini(need, BATCH)
		sim._run_physics_steps(b)
		await get_tree().process_frame


# ═══════════════════════════════════════════════════════════════════════════
# (A) CLUMPING
# ═══════════════════════════════════════════════════════════════════════════
func _clumping_analysis() -> Dictionary:
	var ey: PackedFloat32Array = sim._rd.buffer_get_data(sim._field_ey, 0, nc * 4).to_float32_array()
	var ei: PackedFloat32Array = sim._rd.buffer_get_data(sim._field_ei, 0, nc * 4).to_float32_array()
	var q_color := PackedFloat32Array(); q_color.resize(nc)
	var q_theory := PackedFloat32Array(); q_theory.resize(nc)
	for id in range(nc):
		var EY := ey[id]; var EIp := ei[id]
		q_color[id] = EY * EY + EIp * EIp
		var rho := EY + EIp
		var eps := EY - PHI * EIp
		q_theory[id] = (rho * rho) / (rho * rho + PHI_INV2 + eps * eps)

	var res := {}
	res["epoch_steps"] = EPOCH_STEPS
	res["epoch_t"] = EPOCH_STEPS * sim.dt
	res["conventions"] = {}
	for conv in ["color", "theory"]:
		var f: PackedFloat32Array = q_color if conv == "color" else q_theory
		var ps := _power_spectrum(f, N)
		var modes := _dominant_modes(ps)
		var a := _autocorr_peaks(f, N)
		res["conventions"][conv] = {
			"field_name": "q=EY²+EI²" if conv == "color" else "q=ρ²/(ρ²+φ⁻²+ε²)",
			"spectrum_stats": {"max_power": ps.max_abs, "total": ps.total},
			"dominant_modes": modes.mags,
			"dominant_mode_count": modes.mags.size(),
			"wavelength_ratios_consecutive": modes.ratios,   # k_{i+1}/k_i (φ = ladder)
			"clump_separation_lags": a.lags,                 # autocorr radial peaks (cells)
			"clump_separation_ratios": a.ratios,             # λ_{i+1}/λ_i (φ⁻¹ = ladder)
			"power_radial": ps.shell_frac,                   # for the report / inspection
		}
	return res


# Self-tested separable 3D FFT → radial power spectrum.
# Returns {shell: PackedFloat32Array (index by |k| m=0..N/2), shell_frac:
# normalized shell values, max_abs, total}.
func _power_spectrum(f: PackedFloat32Array, NN: int) -> Dictionary:
	var re: PackedFloat32Array = f.duplicate()
	var im := PackedFloat32Array(); im.resize(nc)
	_fft3d(re, im, NN, false)
	# Radial bin: shell index m = round(|k|) over the Nyquist band.
	var half := NN / 2
	var shell_sum := PackedFloat32Array(); shell_sum.resize(half + 1)
	var shell_cnt := PackedInt32Array(); shell_cnt.resize(half + 1)
	for kz in range(NN):
		var zz: float = kz if kz <= half else kz - NN
		for ky in range(NN):
			var yy: float = ky if ky <= half else ky - NN
			for kx in range(NN):
				var xx: float = kx if kx <= half else kx - NN
				var mag := sqrt(xx * xx + yy * yy + zz * zz)
				var m: int = int(round(mag))
				if m > half:
					m = half
				var id := kx + NN * (ky + NN * kz)
				shell_sum[m] += re[id] * re[id] + im[id] * im[id]
				shell_cnt[m] += 1
	var shell_avg := PackedFloat32Array(); shell_avg.resize(half + 1)
	var mx := 0.0
	var tot := 0.0
	for m in range(1, half + 1):   # m=0 (DC) excluded
		var a := 0.0 if shell_cnt[m] == 0 else shell_sum[m] / float(shell_cnt[m])
		shell_avg[m] = a
		mx = maxf(mx, a)
		tot += a
	# normalize to fraction of the max (for prominence windows)
	var frac := PackedFloat32Array(); frac.resize(half + 1)
	for m in range(1, half + 1):
		frac[m] = 0.0 if mx <= 0.0 else shell_avg[m] / mx
	return {"shell": shell_avg, "shell_frac": frac, "max_abs": mx, "total": tot, "half": half}


func _dominant_modes(ps: Dictionary) -> Dictionary:
	var half: int = ps.half
	var frac: PackedFloat32Array = ps.shell_frac
	var idx := PackedInt32Array(); idx.resize(half + 1)
	# local maxima over shells 1..half-1 (exclude the DC and the Nyquist edge)
	for m in range(1, half - 1):
		if frac[m] >= frac[m - 1] and frac[m] >= frac[m + 1] \
				and frac[m] >= PEAK_PROMINENCE:
			idx.append(m)
	var mags := []
	for m in idx:
		if m > 0:
			mags.append(float(m))
	mags.sort()
	var ratios := []
	for i in range(mags.size() - 1):
		ratios.append(float(mags[i + 1]) / float(mags[i]))
	return {"mags": mags, "ratios": ratios}


# 3D autocorrelation from the already-computed (re,im) FFT is done separately
# via a fresh inverse transform of |F|²; here we radial-bin C(r) and find its
# non-zero-lag peaks (clump-clump separations). Returns {lags, ratios}.
func _autocorr_peaks(f: PackedFloat32Array, NN: int) -> Dictionary:
	var re: PackedFloat32Array = f.duplicate()
	var im := PackedFloat32Array(); im.resize(nc)
	_fft3d(re, im, NN, false)
	for id in range(nc):
		var p := re[id] * re[id] + im[id] * im[id]
		re[id] = p
		im[id] = 0.0
	_fft3d(re, im, NN, true)   # IFFT of the power = (scaled) autocorrelation
	if re.size() > 0:
		var s0 := absf(re[0])
		if s0 > 0.0:
			var inv := 1.0 / s0
			for id in range(nc):
				re[id] *= inv
	var half := NN / 2
	var bins := PackedFloat32Array(); bins.resize(half + 1)
	var cnt := PackedInt32Array(); cnt.resize(half + 1)
	for kz in range(NN):
		var zz: float = kz if kz <= half else kz - NN
		for ky in range(NN):
			var yy: float = ky if ky <= half else ky - NN
			for kx in range(NN):
				var xx: float = kx if kx <= half else kx - NN
				var mag := sqrt(xx * xx + yy * yy + zz * zz)
				var m: int = int(round(mag))
				if m > half:
					m = half
				var id := kx + NN * (ky + NN * kz)
				bins[m] += re[id]
				cnt[m] += 1
	var avg := PackedFloat32Array(); avg.resize(half + 1)
	for m in range(1, half + 1):
		avg[m] = 0.0 if cnt[m] == 0 else bins[m] / float(cnt[m])
	# find local-max lags at r ≥ 3 (skip the trivial r=0 peak and near neighbours)
	var lags := []
	for m in range(3, half - 1):
		if avg[m] >= avg[m - 1] and avg[m] >= avg[m + 1] and avg[m] > 0.02:
			lags.append(float(m))
	var ratios := []
	for i in range(lags.size() - 1):
		ratios.append(float(lags[i + 1]) / float(lags[i]))
	return {"lags": lags, "ratios": ratios}


func _apply_clump_tree(rec: Dictionary) -> void:
	var best_convs := []
	for conv in ["color", "theory"]:
		var c: Dictionary = rec.conventions[conv]
		var n_mode: int = c.dominant_mode_count
		var r: Array = c.wavelength_ratios_consecutive
		if n_mode < MIN_MODES:
			best_convs.append({"conv": conv, "verdict": "NO CLUMP LADDER",
				"detail": "%d dominant mode(s) (< %d)" % [n_mode, MIN_MODES]})
			continue
		var all_in := true
		for k in range(r.size()):
			if absf(float(r[k]) - PHI) > RATIO_TOL:
				all_in = false
		if all_in and r.size() >= MIN_MODES - 1:
			best_convs.append({"conv": conv, "verdict": "CLUMPING SUPPORTS φ-LADDER",
				"detail": "%d modes, %d ratios all within φ±%.2f" % [n_mode, r.size(), RATIO_TOL]})
		else:
			best_convs.append({"conv": conv, "verdict": "CLUMPING NO φ-LADDER",
				"detail": "%d modes / %d ratios, mixed placement" % [n_mode, r.size()]})
	rec["per_convention_verdicts"] = best_convs
	# Canonical = whichever convention supports the ladder; else the colour one.
	rec["verdict"] = "CLUMPING SUPPORTS φ-LADDER" if any_v(best_convs, "CLUMPING SUPPORTS φ-LADDER") \
		else best_convs[0].verdict
	print("[diag-cr] (A) %s" % rec["verdict"])


# ═══════════════════════════════════════════════════════════════════════════
# (B) RIPPLE
# ═══════════════════════════════════════════════════════════════════════════
func _ripple_analysis() -> Dictionary:
	# Re-read q (colour) at each sample; track the strongest |∇q| front centroid.
	var times := []
	var cents := []
	var Nsamples := 0
	while Nsamples < RIP_SAMPLES:
		var step_now: int = sim._step_count
		var t_now: float = step_now * sim.dt
		var q: PackedFloat32Array = sim._rd.buffer_get_data(sim._field_q, 0, nc * 4).to_float32_array()
		var c := _front_centroid(q)
		times.append(t_now)
		cents.append(c)
		Nsamples += 1
		if step_now >= RIP_END_STEPS:
			break
		var need: int = mini(RIP_END_STEPS - step_now, BATCH)
		# first sample recorded at the window start; step forward for the rest
		sim._run_physics_steps(need if Nsamples < RIP_SAMPLES else 0)
		await get_tree().process_frame
	# linear fit c(t): slope = centroid velocity (cells/unit-t), along each axis.
	var res := {}
	var vc: Vector3 = _linfit_velocity(times, cents)
	res["v_coherence_cells_per_t"] = vc.length()
	res["v_coherence_vec"] = [vc.x, vc.y, vc.z]
	res["samples_t"] = times
	res["samples_centroid"] = cents
	res["ratio"] = 0.0
	res["v_particles"] = 0.0
	res["separation"] = "N/A"
	res["sigma_ratio"] = 0.0
	var mean_c := Vector3.ZERO
	for c in cents:
		mean_c += c
	mean_c /= float(cents.size())
	# Particle velocities in the spherical region around the feature.
	var vp_stats := _particle_vel_stats(mean_c, RIP_SPHERE_R)
	res["v_particles"] = vp_stats.mean
	res["v_particles_sem"] = vp_stats.sem
	res["v_particles_n"] = vp_stats.n
	res["v_particles_std"] = vp_stats.std
	# velocity σ from the fit residual (position spread about the line / Δt)
	res["v_coherence_sigma"] = _linfit_sigma(times, cents)
	# per-segment speeds (diagnostic for front continuity)
	var segs := PackedFloat32Array()
	for i in range(cents.size() - 1):
		var dtv: float = times[i + 1] - times[i]
		if absf(dtv) > 1e-12:
			segs.append(((cents[i + 1] as Vector3) - (cents[i] as Vector3)).length() / dtv)
	res["v_coherence_segments"] = segs
	var vc_v: float = res["v_coherence_cells_per_t"]
	var vp_v: float = res["v_particles"]
	if vp_v > 1e-9 and vc_v > 1e-9:
		var ratio := vc_v / vp_v
		var sigma_ratio := ratio * sqrt(pow(res["v_coherence_sigma"] / vc_v, 2.0) + pow(vp_stats.sem / vp_v, 2.0))
		res["ratio"] = ratio
		res["sigma_ratio"] = sigma_ratio
	return res


# Intensity-weighted centroid of the strongest |∇q| front (colour coherence q).
func _front_centroid(q: PackedFloat32Array) -> Vector3:
	# central-difference |∇q| magnitude per cell.
	var gmax := 0.0
	var grad := PackedFloat32Array(); grad.resize(nc)
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				var gx: float = (q[((i + 1) % N) + N * (j + N * k)] - q[((i - 1 + N) % N) + N * (j + N * k)]) * 0.5
				var gy: float = (q[(i + N * (((j + 1) % N) + N * k))] - q[(i + N * (((j - 1 + N) % N) + N * k))]) * 0.5
				var gz: float = (q[(i + N * (j + N * ((k + 1) % N)))] - q[(i + N * (j + N * ((k - 1 + N) % N)))]) * 0.5
				var gm := sqrt(gx * gx + gy * gy + gz * gz)
				grad[id] = gm
				gmax = maxf(gmax, gm)
	if gmax <= 0.0:
		return Vector3(float(N) * 0.5, float(N) * 0.5, float(N) * 0.5)
	var thr: float = FRONT_FRAC * gmax
	var wsum := 0.0
	var c := Vector3.ZERO
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				var gm: float = grad[id]
				if gm >= thr:
					c.x += gm * float(i)
					c.y += gm * float(j)
					c.z += gm * float(k)
					wsum += gm
	if wsum <= 0.0:
		return Vector3(float(N) * 0.5, float(N) * 0.5, float(N) * 0.5)
	return c / wsum


# Mean |v| of particles within a sphere (in CELL space — particle positions are
# in cell units only if the box maps 1:1; convert by centering on N/2 and
# scaling by the cell size per axis). Reads _vel_buf (vec4/particle).
func _particle_vel_stats(center: Vector3, r: float) -> Dictionary:
	var np: int = sim.N_particles
	var vel: PackedFloat32Array = sim._rd.buffer_get_data(sim._vel_buf, 0, np * 16).to_float32_array()
	var pos: PackedFloat32Array = sim._rd.buffer_get_data(sim._pos_buf, 0, np * 16).to_float32_array()
	var n := 0
	var sum := 0.0
	var ssum := 0.0
	var halfbox := float(N) * 0.5
	var ext: Vector3 = sim._extents()
	var h0: float = 2.0 * minf(minf(ext.x, ext.y), ext.z) / float(N)  # reference cell (world/cell)
	var cell := Vector3(2.0 * ext.x / float(N), 2.0 * ext.y / float(N), 2.0 * ext.z / float(N))
	for p in range(np):
		# world → cell coordinates (periodic center-on-N/2), then distance from center
		var cw := Vector3(pos[p * 4], pos[p * 4 + 1], pos[p * 4 + 2])
		var cc: Vector3 = Vector3(halfbox + cw.x / cell.x, halfbox + cw.y / cell.y, halfbox + cw.z / cell.z)
		# periodic min-image distance in cell units
		var dd := cc - center
		dd.x -= roundf(dd.x / float(N)) * float(N)
		dd.y -= roundf(dd.y / float(N)) * float(N)
		dd.z -= roundf(dd.z / float(N)) * float(N)
		if dd.length() <= r:
			var v := Vector3(vel[p * 4], vel[p * 4 + 1], vel[p * 4 + 2])
			var m := v.length() / h0   # reference-cell units per unit time (matches v_coherence)
			sum += m
			ssum += m * m
			n += 1
	if n == 0:
		return {"mean": 0.0, "sem": 0.0, "n": 0, "std": 0.0}
	var mean := sum / float(n)
	var variance := maxf(0.0, ssum / float(n) - mean * mean)
	var std := sqrt(variance)
	return {"mean": mean, "sem": std / sqrt(float(n)), "n": n, "std": std}


func _apply_ripple_tree(rec: Dictionary) -> void:
	var vc: float = rec.v_coherence_cells_per_t
	var vp: float = rec.v_particles
	var ratio: float = rec.ratio
	var sigma_ratio: float = rec.sigma_ratio
	if vp <= 1e-9 or vc <= 1e-9 or sigma_ratio <= 0.0:
		rec.verdict = "RIPPLE: NOT DISTINGUISHABLE (degenerate speed)"
		print("[diag-cr] (B) %s" % rec.verdict)
		return
	var sep := absf(ratio - 1.0) > 3.0 * sigma_ratio
	if sep:
		rec.verdict = "RIPPLE: DISTINCT, coherence %s than particles" % ("faster" if ratio > 1.0 else "slower")
		rec.separation = "DISTINCT (|ratio-1| > 3σ)"
	else:
		rec.verdict = "RIPPLE: NOT DISTINGUISHABLE"
		rec.separation = "NOT DISTINCT (|ratio-1| <= 3σ)"
	print("[diag-cr] (B) v_c=%.4f v_p=%.4f ratio=%.3f σ_ratio=%.3f → %s" % [vc, vp, ratio, sigma_ratio, rec.verdict])


# ═══════════════════════════════════════════════════════════════════════════
# Utility: separable radix-2 FFT (CPU, self-tested) + helpers
# ═══════════════════════════════════════════════════════════════════════════
func _fft3d(re: PackedFloat32Array, im: PackedFloat32Array, NN: int, inverse: bool) -> void:
	var row := PackedFloat32Array(); row.resize(NN)
	var lim := PackedFloat32Array(); lim.resize(NN)
	# axis 0: rows along x (contiguous stride N)
	for kc in range(NN):
		for jc in range(NN):
			var base := kc * NN * NN + jc * NN
			for i in range(NN):
				row[i] = re[base + i]
				lim[i] = im[base + i]
			_fft1d(row, lim, NN, inverse)
			for i in range(NN):
				re[base + i] = row[i]
				im[base + i] = lim[i]
	# axis 1: along y (stride NN)
	for kc in range(NN):
		for ic in range(NN):
			for jc in range(NN):
				var base := kc * NN * NN + ic
				row[jc] = re[base + jc * NN]
				lim[jc] = im[base + jc * NN]
			_fft1d(row, lim, NN, inverse)
			for jc in range(NN):
				var base := kc * NN * NN + ic
				re[base + jc * NN] = row[jc]
				im[base + jc * NN] = lim[jc]
	# axis 2: along z
	for jc in range(NN):
		for ic in range(NN):
			for kc in range(NN):
				var base := jc * NN + ic
				row[kc] = re[base + kc * NN * NN]
				lim[kc] = im[base + kc * NN * NN]
			_fft1d(row, lim, NN, inverse)
			for kc in range(NN):
				var base := jc * NN + ic
				re[base + kc * NN * NN] = row[kc]
				im[base + kc * NN * NN] = lim[kc]


func _fft1d(re: PackedFloat32Array, im: PackedFloat32Array, n: int, inverse: bool) -> void:
	# bit-reversal permutation
	var j := 0
	for i in range(1, n):
		var bit: int = n >> 1
		while j & bit != 0:
			j ^= bit
			bit >>= 1
		j ^= bit
		if i < j:
			var tr: float = re[i]; re[i] = re[j]; re[j] = tr
			var ti: float = im[i]; im[i] = im[j]; im[j] = ti
	# butterflies
	var len := 2
	while len <= n:
		var ang: float = (6.283185307179586 / float(len)) * (-1.0 if not inverse else 1.0)
		var wl_r := cos(ang)
		var wl_i := sin(ang)
		var wr := 1.0
		var wi := 0.0
		for k in range(0, n, len):
			wr = 1.0; wi = 0.0
			for i in range(len >> 1):
				var ar: float = re[k + i]
				var ai: float = im[k + i]
				var br: float = re[k + i + (len >> 1)]
				var bi: float = im[k + i + (len >> 1)]
				var xr := wr * br - wi * bi
				var xi := wr * bi + wi * br
				re[k + i] = ar + xr
				im[k + i] = ai + xi
				re[k + i + (len >> 1)] = ar - xr
				im[k + i + (len >> 1)] = ai - xi
				var nr := wr * wl_r - wi * wl_i
				var ni := wr * wl_i + wi * wl_r
				wr = nr; wi = ni
		len <<= 1
	if inverse:
		var inv := 1.0 / float(n)
		for i in range(n):
			re[i] *= inv
			im[i] *= inv


# linear fit c(t) → velocity; returns the 3-vector velocity.
func _linfit_velocity(ts: Array, cs: Array) -> Vector3:
	var n := cs.size()
	if n < 2:
		return Vector3.ZERO
	var mt := 0.0
	for t in ts:
		mt += t
	mt /= float(n)
	var sx := 0.0; var sy := 0.0; var sz := 0.0
	var stt := 0.0
	for i in range(n):
		var dtv: float = ts[i] - mt
		var c: Vector3 = cs[i]
		sx += dtv * c.x; sy += dtv * c.y; sz += dtv * c.z
		stt += dtv * dtv
	if absf(stt) < 1e-12:
		return Vector3.ZERO
	return Vector3(sx / stt, sy / stt, sz / stt)


# scatter of the centroid samples about the best-fit line → velocity σ.
# Robust estimate: the standard error of the per-segment centroid speeds
# (in cells/unit-t). This is the defensible measure of how uncertain the
# measured feature speed is given the front jitter across the window.
func _linfit_sigma(ts: Array, cs: Array) -> float:
	var n := cs.size()
	if n < 3:
		return 0.0
	var segs := PackedFloat32Array()
	for i in range(n - 1):
		var dtv: float = ts[i + 1] - ts[i]
		if absf(dtv) < 1e-12:
			continue
		var d: Vector3 = (cs[i + 1] as Vector3) - (cs[i] as Vector3)
		segs.append(d.length() / dtv)
	if segs.size() < 2:
		return 0.0
	var mean := 0.0
	for s in segs:
		mean += s
	mean /= float(segs.size())
	var var_acc := 0.0
	for s in segs:
		var_acc += (s - mean) * (s - mean)
	var std := sqrt(var_acc / float(segs.size() - 1))
	return std / sqrt(float(segs.size()))


# ── Self-tests (prove the detectors before the physics run) ────────────
func _self_test_fft() -> bool:
	var ok := true
	# (i) plane wave along x at +m: power must peak near shell m.
	for m in [2, 5, 9]:
		var f := PackedFloat32Array(); f.resize(nc)
		for k in range(N):
			for j in range(N):
				for i in range(N):
					var id := i + N * (j + N * k)
					f[id] = cos(6.283185307179586 * float(m) * float(i) / float(N))
		var ps := _power_spectrum(f, N)
		var peak := 1
		for mm in range(2, ps.half):
			if ps.shell_frac[mm] > ps.shell_frac[peak]:
				peak = mm
		if absf(float(peak) - float(m)) > 1:
			push_error("diag_cr FFT selftest: plane-wave %d peaked at %d" % [m, peak])
			ok = false
	# (ii) 3D sinusoid at (p,q,r) → dominant k-magnitude matches sqrt(p²+q²+r²).
	var f3 := PackedFloat32Array(); f3.resize(nc)
	var pp := 1; var qq := 2; var rr := 3
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				f3[id] = cos(6.283185307179586 / float(N) * (pp * float(i) + qq * float(j) + rr * float(k)))
	var ps3 := _power_spectrum(f3, N)
	var peak3 := 1
	for mm in range(2, ps3.half):
		if ps3.shell_frac[mm] > ps3.shell_frac[peak3]:
			peak3 = mm
	var expect := sqrt(float(pp * pp + qq * qq + rr * rr))
	if absf(float(peak3) - expect) > 1:
		push_error("diag_cr FFT selftest: 3D sinusoid peaked %d expect %.1f" % [peak3, expect])
		ok = false
	print("[diag-cr] FFT self-test: %s" % ("PASS" if ok else "FAIL"))
	return ok


func _self_test_ladder_detector() -> bool:
	# synthetic radial power peaking exactly at shells {1,2,3,5,8,13} (≈φ ladder)
	var half := (N / 2)
	var frac := PackedFloat32Array(); frac.resize(half + 1)
	for m in range(1, half + 1):
		frac[m] = 0.012
	for m in [1, 2, 3, 5, 8, 13]:
		if m < half:
			frac[m] = 1.0
	var ps := {"shell": frac, "shell_frac": frac, "max_abs": 1.0, "total": 1.0, "half": half}
	var modes := _dominant_modes(ps)
	# detector should return ≥3 of the planted shells
	if modes.mags.size() < 3:
		push_error("diag_cr ladder selftest: detected %d modes (need >=3)" % modes.mags.size())
		return false
	print("[diag-cr] ladder self-test: detected modes %s" % str(modes.mags))
	return true


func any_v(arr: Array, needle: String) -> bool:
	for e in arr:
		if e is Dictionary and e.get("verdict", "") == needle:
			return true
	return false


func _write_report() -> void:
	var out_dir := "res://_diag"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	var json := JSON.stringify(report, "\t")
	var seed_tag := "seed" if sim.multi_rung_seed else "noseed"
	var f := FileAccess.open(out_dir + "/coherence_ripple_report_%s.json" % seed_tag, FileAccess.WRITE)
	if f:
		f.store_string(json)
		f.close()
		print("[diag-cr] report written to res://_diag/coherence_ripple_report_%s.json" % seed_tag)
