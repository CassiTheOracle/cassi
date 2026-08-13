extends Node
## ───────────────────────────────────────────────────────────────────────────
## diag_bubble_rings — NUMERICAL radial-readback test of the Cassi bubble-shell
## ring ladder (Prediction 51, cassi-toe foundations/bubble-edge-geometry.md §3)
## on the SPACE-SIM second-order GLSL two-fluid PDE.
##
##   d²EY/dt² = c²∇²EY − ω₀²(EY − φ·EI)      (c² = 1 in the shader, ω₀² = 20)
##   d²EI/dt² = c²∇²EI + ω₀²(EY − φ·EI)
##
## The theory (bubble-edge-geometry.md §3.1, Prediction 51) predicts that a
## bubble's interior hosts a φ-quantized ring ladder: matter rings at
## r_k = ℓ_n·φ^{−k}, void troughs at ℓ_n·φ^{−(k+½)} (k = 0,1,2,…). Successive
## matter-ring radius ratio = φ^{−1} = 0.6180; the null (interleaved/void
## spacing) would give φ^{−1/2} = 0.7862. ~10 rings are expected at the 1%
## contrast floor, n-independent. The cassi-toe FIRST-ORDER solver found
## NO RINGS on all four arms to t=40 (bubble-edge-geometry.md §3.6); that doc
## explicitly flags that the full SECOND-ORDER form "belongs to the
## space-sim GLSL PDE" — i.e. THIS solver is the operator the ladder was
## hypothesized onto. This probe is the honest numerical observation of
## whether the space-sim second-order two-fluid PDE realizes the ladder.
##
## Renders are too coarse to resolve the ladder; the honest test is a CPU
## readback of the q = EY²+EI² field grid (the Qi-rainbow coherence
## observable) binned radially inside an evolved bubble shell.
##
## METHOD (box is the CUBE (1,1,1) default ⇒ shells spherical):
##   1. Seed a featureless bubble-capable IC at the box center:
##        filled   — a smooth-step solid condensate ball (EY = A·half(1−tanh((r−R0)/w)),
##                    EI = EY/φ ⇒ EY−φ·EI = 0 at the seed; no interior structure is
##                    pre-imposed — any ring modulation must arise organically from
##                    the PDE). source_strength = 0 (no ongoing injection).
##   2. Step the sim's OWN shader (console build — see header note below),
##      reading _field_q back on CPU at each diagnostic epoch (t = steps·dt).
##   3. Detect the shell (outermost prominent median-q ridge) → shell radius R.
##   4. Bin the q field radially in u = log_φ(r/R); median q over a Fibonacci
##      sphere at each radius (a full ring ⇒ azimuthally-complete ⇒ the median
##      is the right observable for closed matter rings).
##   5. Find matter ridges (median-q local maxima, contrast ≥ 1% over the
##      flanking minima) at r ∈ [CORE_FRAC·R, R]; measure successive ridge
##      radius ratios; apply the PRE-REGISTERED decision tree (below).
##   6. SELF-TEST (before the physics run): feed a synthetic φ-ladder profile
##      through the same ridge finder to prove it detects ≥3 ridges with
##      ratio 0.618 — i.e. a NO RIDGES physics verdict cannot be an artifact
##      of a blind detector.
##
## ── PRE-REGISTERED DECISION TREE (fixed BEFORE any run; every outcome is an
##    honest, acceptable verdict — the test is the observation, not a hope):
##      N_ridge < 3  → "NO RIDGES" (report the radial profile)
##      N_ridge ≥ 3  →
##        every successive ratio ∈ 0.6180 ± 0.08
##          AND every ratio ∉ 0.7862 ± 0.05  → "SUPPORTS"
##        else if every ratio ∈ 0.7862 ± 0.05
##          AND every ratio ∉ 0.6180 ± 0.08  → "SUPPORTS NULL"
##        else → "INDETERMINATE"
##   WHERE N_ridge = number of matter ridges found (including the shell).
##
## LAUNCH: this repo's headless probe pattern is the Console build WITHOUT the
## --headless flag (--headless kills the global RenderingDevice — see
## cassi_sim.gd:_setup_rendering_device). A transient window appears; the
## probe needs no rendering and quits itself (exit 0) after writing the report.
##   Godot_v4.7.1-stable_mono_win64_console.exe --path <space-sim> res://scenes/diag_bubble_rings.tscn
##
## Write telemetry → res://_diag/bubble_rings_report.json (gitignored).
## ───────────────────────────────────────────────────────────────────────────

const PHI: float = 1.618033988749895
const PHI_INV: float = 0.618033988749895       # φ^{−1}    — theory matter-ring ratio
const PHI_INV_HALF: float = 0.7861513777574233 # φ^{−1/2}  — null ratio
const RATIO_TOL: float = 0.08                   # ±0.08 window around φ^{−1}
const NULL_RATIO_TOL: float = 0.05              # ±0.05 window around φ^{−1/2}
const REL_CONTRAST: float = 0.01                # 1% relative contrast floor
const CORE_FRAC: float = 0.10                   # exclude ridges r < 10% of shell radius
const SHELL_MIN_R_FRAC: float = 0.15            # a genuine bubble shell must sit at ≥ 15% of the half-box
const NU_BINS: int = 600                        # radial bins in u = log_φ(r/R)
const U_MIN: float = -6.2                        # innermost u ≈ log_φ(0.05·R) = −6.21
const SPHERE_PTS: int = 384                     # Fibonacci points per radial bin
const BATCH: int = 100                          # steps per compute list (readback per epoch)
const SEED_MODE: String = "filled"              # "filled" solid ball | "shell" hollow
const SEED_R: float = 38.0                      # seed shell radius (cells)
const SEED_W: float = 5.0                       # shell edge width (cells)
const SEED_A: float = 0.5                       # seed amplitude
const MIN_RIDGES: int = 3                       # tree gate
# Diagnostic epochs in STEPS; t = steps·0.001. Chosen so the inward wave front
# (speed c≈1 cell/unit t) fully sweeps the interior (r<R0≈38 ⇒ needs t≳38).
const EPOCHS: Array[int] = [4000, 12000, 24000, 40000]

var sim: Node3D
var report: Dictionary = {}


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	if sim == null:
		push_error("diag_bubble_rings: CassiSim not found")
		get_tree().quit(1)
		return
	# The owner edits cassi_sim.gd live in a parallel session; if it is
	# transiently mid-save the node holds no script. Detect that and exit
	# cleanly (exit 1) instead of aborting _ready ungracefully / hanging.
	if not sim.has_method("_run_physics_steps"):
		push_error("diag_bubble_rings: CassiSim script not loaded (mid-edit?) — aborting")
		get_tree().quit(1)
		return
	sim.playing = false
	sim.gravity_mode = 2            # Plummer arm: skips the Poisson FFT chain; field PDE unchanged
	sim.source_strength = 0.0       # no ongoing injection — freely-evolving seed
	sim.field_attractor_init = false
	# Zero the 2 seed particles (mass 0 → rho = 0 everywhere; the two-fluid
	# source's mr·0.001 term and the mass-deposit density both vanish).
	var pos := PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
	sim._rd.buffer_update(sim._pos_buf, 0, 32, pos.to_byte_array())
	await get_tree().process_frame
	await get_tree().process_frame
	var waited := 0
	while not sim._shaders_ready and waited < 600:
		waited += 1
		await get_tree().process_frame
	if not sim._shaders_ready:
		push_error("diag_bubble_rings: shaders never became ready")
		get_tree().quit(1)
		return
	print("[diag] shaders ready after %d frames (grid=%d, aspect=%s)" % [waited, sim.grid_N, str(sim.box_aspect)])
	var selftest := _self_test()
	_run()
	print("══════ diag_bubble_rings: %s (self-test %s) ══════" % [str(report.get("verdict", "?")), "PASS" if selftest else "FAIL"])

	var out_dir := "res://_diag"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	var json := JSON.stringify(report, "\t")
	var f := FileAccess.open(out_dir + "/bubble_rings_report.json", FileAccess.WRITE)
	if f:
		f.store_string(json)
		f.close()
		print("[diag] report written to res://_diag/bubble_rings_report.json")
	get_tree().quit(0)


# ── Synthetic self-test: prove the ridge finder detects a φ-ladder ──────
# Builds a noise-free synthetic radial profile with matter ridges exactly at
# r_k = R·φ^{−k} (k = 0..8, alternating void troughs) and checks the detector
# recovers ≥3 ridges with ratios within the pre-registered SUPPORTS band.
func _self_test() -> bool:
	var R := 38.0
	var n := NU_BINS
	var sm := PackedFloat32Array(); sm.resize(n)
	var rr := PackedFloat32Array(); rr.resize(n)
	for b in range(n):
		var u := U_MIN + (0.0 - U_MIN) * (float(b) + 0.5) / float(n)
		var rv := R * pow(PHI, u)
		rr[b] = rv
		# matter ridge at EVERY integer u (u = −k ⇒ r = R·φ^{−k}), void at every
		# half-integer: amplitude ∝ |cos(π·u)| (antinode |1| at integers, node 0
		# at half-integers). Baseline 0.02 + strong rings 0.2.
		var amp := absf(cos(PI * u))
		sm[b] = 0.02 + 0.2 * amp
	var prof := {"u": rr, "r": rr, "med": sm}
	var rec: Dictionary = _analyze_epoch(0, prof, PackedFloat32Array(), 2, 1.0)
	_apply_tree(rec)
	var ok: bool = rec.verdict == "SUPPORTS"
	print("[selftest] synthetic φ-ladder → %d ridges, ratios=%s → %s" % [
		rec.ridges_r_cells.size(), str(rec.ridges_ratios), rec.verdict])
	return ok


func _run() -> void:
	var N: int = sim.grid_N
	var center := float(N) * 0.5
	print("[diag] seed: %s sphere R0=%d w=%.1f A=%.2f; cube aspect (spherical shells); %s" % [SEED_MODE, int(SEED_R), SEED_W, SEED_A, str(EPOCHS)])
	_seed_field()
	var t0 := Time.get_ticks_msec()
	var total_steps := 0
	var all_epochs := []
	for epoch in EPOCHS:
		var need := epoch - total_steps
		while need > 0:
			var b := mini(need, BATCH)
			sim._run_physics_steps(b)
			total_steps += b
			need -= b
		var qdata: PackedFloat32Array = sim._rd.buffer_get_data(sim._field_q, 0, N * N * N * 4).to_float32_array()
		var prof := _radial_profile(qdata, N, center)
		var rec := _analyze_epoch(epoch, prof, qdata, N, center)
		all_epochs.append(rec)
		print("\n──── epoch %d (t=%.1f) ────" % [epoch, epoch * sim.dt])
		_print_epoch(rec, true)
		_apply_tree(rec)
	var rt_ms := int(Time.get_ticks_msec() - t0)
	report["runtime_ms"] = rt_ms
	report["seed"] = {"mode": SEED_MODE, "R_cells": SEED_R, "w_cells": SEED_W, "A": SEED_A}
	report["grid_N"] = N
	report["dt"] = sim.dt
	report["epochs_steps"] = EPOCHS
	report["analysis"] = {
		"u_bins": NU_BINS, "u_min": U_MIN, "sphere_points": SPHERE_PTS,
		"rel_contrast_floor": REL_CONTRAST, "core_frac_excluded": CORE_FRAC,
		"ratio_target": PHI_INV, "ratio_tol": RATIO_TOL,
		"null_target": PHI_INV_HALF, "null_tol": NULL_RATIO_TOL,
	}
	# Canonical verdict = the FINAL epoch (the most-evolved shell).
	var final: Dictionary = all_epochs.back()
	report["verdict"] = final.verdict
	report["verdict_detail"] = final.verdict_detail
	report["ridge_ratios"] = final.ridges_ratios
	report["epochs"] = all_epochs
	print("\n══════ FINAL VERDICT (epoch %s): %s ══════" % [str(EPOCHS.back()), final.verdict])
	print("[diag] %s" % str(final.verdict_detail))
	print("[diag] runtime %.1f s, %d steps" % [rt_ms / 1000.0, total_steps])


func _seed_field() -> void:
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var ey := PackedFloat32Array(); ey.resize(nc)
	var ei := PackedFloat32Array(); ei.resize(nc)
	var q := PackedFloat32Array(); q.resize(nc)
	var vel := PackedFloat32Array(); vel.resize(nc * 4)
	var center := float(N) * 0.5
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var dx := float(i) - center
				var dy := float(j) - center
				var dz := float(k) - center
				var r := sqrt(dx * dx + dy * dy + dz * dz)
				var g: float
				if SEED_MODE == "shell":
					g = exp(-pow((r - SEED_R) / SEED_W, 2.0))
				else:  # filled: smooth-step solid ball (featureless interior)
					g = 0.5 * (1.0 - tanh((r - SEED_R) / SEED_W))
				var v: float = SEED_A * g
				var id: int = i + N * (j + N * k)
				ey[id] = v
				ei[id] = v / PHI
				q[id] = v * v + (v / PHI) * (v / PHI)
	sim._rd.buffer_update(sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())
	sim._rd.buffer_update(sim._field_q, 0, q.size() * 4, q.to_byte_array())
	_rd_zero(sim._field_vel, nc * 16)


func _rd_zero(rid: RID, bytes: int) -> void:
	var z := PackedByteArray(); z.resize(bytes)
	sim._rd.buffer_update(rid, 0, bytes, z)


# Trilinear periodic sample of a float[N³] grid at cell coords (cx,cy,cz).
func _triq(a: PackedFloat32Array, N: int, cx: float, cy: float, cz: float) -> float:
	var i0 := int(floor(cx)); var j0 := int(floor(cy)); var k0 := int(floor(cz))
	var fx := cx - float(i0); var fy := cy - float(j0); var fz := cz - float(k0)
	i0 = ((i0 % N) + N) % N; j0 = ((j0 % N) + N) % N; k0 = ((k0 % N) + N) % N
	var i1 := (i0 + 1) % N; var j1 := (j0 + 1) % N; var k1 := (k0 + 1) % N
	var v000 := a[i0 + N * (j0 + N * k0)]
	var v100 := a[i1 + N * (j0 + N * k0)]
	var v010 := a[i0 + N * (j1 + N * k0)]
	var v110 := a[i1 + N * (j1 + N * k0)]
	var v001 := a[i0 + N * (j0 + N * k1)]
	var v101 := a[i1 + N * (j0 + N * k1)]
	var v011 := a[i0 + N * (j1 + N * k1)]
	var v111 := a[i1 + N * (j1 + N * k1)]
	var q0 := lerpf(lerpf(v000, v100, fx), lerpf(v010, v110, fx), fy)
	var q1 := lerpf(lerpf(v001, v101, fx), lerpf(v011, v111, fx), fy)
	return lerpf(q0, q1, fz)


# Fibonacci-sphere median q at radius r (cells) from center.
func _sphere_median(a: PackedFloat32Array, N: int, center: float, r: float) -> Dictionary:
	var vals := PackedFloat32Array()
	vals.resize(SPHERE_PTS)
	var ga := 2.399963229728653 # golden angle 2π·(1−1/φ)
	for m in range(SPHERE_PTS):
		var zz := 1.0 - 2.0 * (float(m) + 0.5) / float(SPHERE_PTS)
		var rr := sqrt(maxf(0.0, 1.0 - zz * zz))
		var th := ga * float(m)
		var px := center + r * rr * cos(th)
		var py := center + r * zz
		var pz := center + r * rr * sin(th)
		vals[m] = _triq(a, N, px, py, pz)
	vals.sort()
	var med := vals[SPHERE_PTS / 2]
	var mx := vals[SPHERE_PTS - 1]
	return {"med": med, "max": mx}


# Radial profile: median q over the sphere surface at radius r = SEED_R·φ^u,
# for u ∈ [U_MIN, 0]. Anchored at SEED_R (≈ the shell radius); ring RATIOS are
# computed from the detected ridge radii directly (scale-free), so the anchor
# is purely a tabulation convenience.
func _radial_profile(qdata: PackedFloat32Array, N: int, center: float) -> Dictionary:
	var R_anchor := SEED_R
	var med := PackedFloat32Array(); med.resize(NU_BINS)
	var mxx := PackedFloat32Array(); mxx.resize(NU_BINS)
	var cnt := PackedInt32Array(); cnt.resize(NU_BINS)
	for b in range(NU_BINS):
		var u := U_MIN + (0.0 - U_MIN) * (float(b) + 0.5) / float(NU_BINS)
		var r := R_anchor * pow(PHI, u)
		if r < 0.8 or r >= float(N) * 0.5 - 0.5:
			continue
		var s := _sphere_median(qdata, N, center, r)
		med[b] = s.med
		mxx[b] = s.max
		cnt[b] = 1
	var uu := []
	var rr := []
	var mm := []
	for b in range(NU_BINS):
		if cnt[b] == 0:
			continue
		var u := U_MIN + (0.0 - U_MIN) * (float(b) + 0.5) / float(NU_BINS)
		uu.append(u)
		rr.append(SEED_R * pow(PHI, u))
		mm.append(med[b])
	return {"u": uu, "r": rr, "med": mm, "max": mxx}


func _analyze_epoch(step: int, prof: Dictionary, qdata: PackedFloat32Array, N: int, center: float) -> Dictionary:
	var rr_arr: Array = prof.r
	var m_arr: Array = prof.med
	var n := m_arr.size()
	# 5-pt moving average.
	var sm := PackedFloat32Array(); sm.resize(n)
	for i in range(n):
		var acc := 0.0
		for o in range(-2, 3):
			var j := clampi(i + o, 0, n - 1)
			acc += m_arr[j]
		sm[i] = acc / 5.0
	# local maxima, INCLUDING boundary bins (the shell peak sits at the
	# outermost u≈0 end of the profile). A bin is a peak if it is not strictly
	# below either neighbor (out-of-range = −∞ ⇒ a boundary high counts).
	var ridge_idx := []
	for i in range(n):
		var left: float = -INF if i == 0 else sm[i - 1]
		var right: float = -INF if i == n - 1 else sm[i + 1]
		if sm[i] > left and sm[i] >= right:
			ridge_idx.append(i)
	# contrast floor: peak must exceed its flanking minima by ≥ REL_CONTRAST.
	# Walk each side of the peak outward to the first point that stops the
	# descent (a local min, or the profile boundary); the peak-to-valley rise
	# is measured against the deeper of the two flanking valleys.
	var kept := []
	for i in ridge_idx:
		var lo: int = i
		while lo > 0 and sm[lo] > sm[lo - 1]:
			# descend left from the peak toward the valley
			lo -= 1
		var hi: int = i
		while hi < n - 1 and sm[hi] > sm[hi + 1]:
			# descend right from the peak toward the valley
			hi += 1
		var base_l := sm[lo]
		var base_r := sm[hi]
		var base := minf(base_l, base_r)
		if sm[i] > 1e-12 and (sm[i] - base) / sm[i] >= REL_CONTRAST:
			kept.append(i)
	var cells := []
	for i in kept:
		cells.append(rr_arr[i])
	if cells.is_empty():
		return {"step": step, "R_shell_cells": 0.0, "ridges_r_cells": [], "ridges_ratios": [],
				"verdict": "NO RIDGES", "verdict_detail": "no ridge found — profile tabulated", "profile": prof}
	# The SHELL is the outermost prominent ridge. A genuine bubble shell must
	# sit at a substantial radius (≥ SHELL_MIN_R_FRAC of the half-box); if no
	# outer shell exists at this epoch, there is no ladder to measure (the deep
	# interior remnants alone are not a shell).
	var R_shell := 0.0
	for c in cells:
		R_shell = maxf(R_shell, c)
	var halfbox := maxf(float(N) * 0.5, 1.0)
	if R_shell < SHELL_MIN_R_FRAC * halfbox:
		return {"step": step, "R_shell_cells": R_shell, "ridges_r_cells": [], "ridges_ratios": [],
				"verdict": "NO RIDGES", "verdict_detail": "no candidate at shell radius (found r=%.1f, need ≥ %.1f) — profile tabulated" % [R_shell, SHELL_MIN_R_FRAC * halfbox],
				"profile": prof}
	# Interior matter ridges: r ∈ [CORE_FRAC·R_shell, R_shell]; outermost first.
	var interior := []
	for c in cells:
		if c >= CORE_FRAC * R_shell:
			interior.append(c)
	interior.sort()
	interior.reverse()
	var ratios := []
	for i in range(interior.size() - 1):
		ratios.append(interior[i + 1] / interior[i])
	return {"step": step, "R_shell_cells": R_shell, "ridges_r_cells": interior, "ridges_ratios": ratios, "profile": prof}


func _print_epoch(rec: Dictionary, tabulate: bool) -> void:
	print("  R_shell = %.2f cells" % rec.R_shell_cells)
	var ridges: Array = rec.ridges_r_cells
	if ridges.is_empty():
		print("  no ridges found")
		if tabulate:
			_print_profile(rec.profile)
		return
	for k in range(ridges.size()):
		print("    ridge[%d] r=%.3f cells (r/R=%.3f)" % [k, ridges[k], ridges[k] / maxf(rec.R_shell_cells, 1e-9)])
	var rs: Array = rec.ridges_ratios
	for k in range(rs.size()):
		print("    ratio[%d->%d] = %.4f  (φ⁻¹ 0.6180±0.08 | null φ^{-1/2} 0.7862±0.05)" % [k, k + 1, rs[k]])
	if tabulate:
		_print_profile(rec.profile)


func _print_profile(prof: Dictionary) -> void:
	var uu: Array = prof.u
	var rr: Array = prof.r
	var mm: Array = prof.med
	print("    radial profile: u(r/R)  r(cells)  q_med")
	for i in range(uu.size()):
		# downsample for stdout (every 5th bin plus cores); full table → JSON
		if i % 5 == 0 or rr[i] < 3.0:
			print("      u=%6.3f  r=%7.2f  q_med=%.8f" % [uu[i], rr[i], mm[i]])


func _apply_tree(rec: Dictionary) -> void:
	var ratios: Array = rec.ridges_ratios
	var n_ridge: int = rec.ridges_r_cells.size()
	if n_ridge < MIN_RIDGES:
		rec.verdict = "NO RIDGES"
		rec.verdict_detail = "%d ridge(s) (< %d) — profile tabulated" % [n_ridge, MIN_RIDGES]
		return
	var sup := true
	var nul := true
	for k in range(ratios.size()):
		var r: float = ratios[k]
		var in_phi := absf(r - PHI_INV) <= RATIO_TOL
		var in_null := absf(r - PHI_INV_HALF) <= NULL_RATIO_TOL
		if not in_phi or in_null:
			sup = false
		if not in_null or in_phi:
			nul = false
	if sup:
		rec.verdict = "SUPPORTS"
		rec.verdict_detail = "%d successive ratios all in 0.6180±0.08, outside 0.7862±0.05" % ratios.size()
	elif nul:
		rec.verdict = "SUPPORTS NULL"
		rec.verdict_detail = "%d successive ratios all in 0.7862±0.05, outside 0.6180±0.08" % ratios.size()
	else:
		rec.verdict = "INDETERMINATE"
		rec.verdict_detail = "%d ridge(s)/%d ratio(s), mixed placement" % [n_ridge, ratios.size()]
	print("  ── verdict: %s  (%s)" % [rec.verdict, rec.verdict_detail])
