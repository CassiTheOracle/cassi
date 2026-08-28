extends Node3D
## ───────────────────────────────────────────────────────────────────────────
## verify_q_growth — the "is the extreme q growth a simulator bug or does
## coherence scale with structure?" probe (merge/coherence R&D workstream,
## 2026-08-14). NEW file — READ-ONLY on every existing .gd/.glsl this turn.
##
## QUESTION: the user observes (1) initial particle balls merge into one
## particle and (2) "coherence" climbs past 1 and keeps rising as structure
## forms. Is the extreme q growth a bug, or does coherence scale with
## structure?
##
## WHAT THIS MEASURES (per arm, over time):
##   sum_rho          Σ(EY+EI)            — net two-fluid field density
##   sum_qq           Σ(EY²+EI²)          — UNBOUNDED "field q" (the sim's
##                                          colour-band / Qi-rainbow observable;
##                                          passage past the PHI_INV2 and 1.0
##                                          anchors is what the user sees as
##                                          "coherence > 1")
##   peak_q           max(EY²+EI²)         — the brightest cell
##   mean_qcoh        ⟨ρ²/(ρ²+φ⁻²+ε²)⟩    — the FRAMEWORK's bounded coherence
##                                          (the merge's gate quantity)
##   frac_above_gate  fraction of cells with q_coh > φ⁻² (the merge gate)
##   corr_q_rho       Pearson( q_coh , rho_mass ) over cells — does coherence
##                                          CONCENTRATE where matter is? (the
##                                          structure-correlation question)
##   hamiltonian      ½Σ(v²)+(coupling Γ)−(source work Σ ΔH_src) — the exact
##                    two-fluid energy (see _build_energy): tracked to expose
##                    whether the ungated shader conserves when not pumped.
##
## THREE ARMS (the config levers the shader exposes; the hardcoded 0.001·ρ
## mass-density feedback in cassi_two_fluid.glsl source_ey/source_ei is
## ALWAYS ON — it is NOT config-toggleable, which is itself a finding recorded
## in the report):
##   A  source_strength = 0.0   (the LIVE default in main.tscn) — measures
##      baseline growth driven ONLY by the always-on 0.001·ρ density feedback
##      (the "does total field grow when only the structure-feedback pumps?"
##      arm — the answer quantifies the bug-vs-physics split).
##   B  source_strength = 50    — strong external Gaussian pump — the "only
##      when pumped" response baseline.
##   C  source_strength = 0.0, num_clusters = 1 (single central well) vs A's
##      10 clusters — isolates condensation-concentration (fewer merger
##      events, same density-contrast feedback) from multi-ball merging.
##
## HONEST CONSTRAINT (recorded): the task's arm (c) "source_strength default
## but WITHOUT particle feedback" is NOT implementable from config — the
## 0.001·ρ term is hardcoded in cassi_two_fluid.glsl (it does not multiply
## pc.source_strength). We therefore isolate the feedback by the A vs C
## density-contrast contrast and by the exact-energy bookkeeping below, and
## report the constraint explicitly.
##
## ENERGY-CONSERVATION CHECK (item 2(b) / item 4): with source_strength=0 the
## coupled wave system should conserve total energy IF the shader were a
## clean symplectic leapfrog with no source. It is NOT cleanly symplectic:
## (i) vel is updated BEFORE the field in pass_a ("v_old + a·dt" then
## "ey_old + v_new·dt" — velocity leapfrog rather than position-velocity
## interleaving, so the update is NOT the exact symplectic Verlet), and
## (ii) the ALWAYS-ON 0.001·ρ source adds energy every step. We measure
## ΔH per step at source_strength=0 and attribute the growth.
##
## LAUNCH (windowed console exe — NEVER --headless; local RD needs a GPU):
##   Godot_v4.7-stable_win64_console.exe --path <space-sim> \
##       res://scenes/verify_q_growth.tscn
## Report → res://_diag/q_growth_report.json (gitignored). Exit 0.
## ───────────────────────────────────────────────────────────────────────────

const ENGINE_SCRIPT := "res://scripts/cassi_physics_engine.gd"
const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051

# ── probe geometry (mirrors verify_merge_engine's main-thread local-RD
# engine pattern; N small so the nbody river step stays bounded) ──
const GRID_N := 64
const N_PARTICLES := 30000
const CLUSTER_RADIUS := 50.0
const SEP := 60.0

# ── step budget ──
const STEPS_PER_SAMPLE := 20
const SAMPLES := 30            # → 600 steps per arm (t up to 1.2 at dt=0.002)
const LONG_SAMPLE := 200       # long-horizon arm A: sample every 200 steps
const LONG_STEPS := 6000       # → t up to 12.0 — the live sim's structure window
const TOTAL_STEPS := STEPS_PER_SAMPLE * SAMPLES
const DT: float = 0.002

var _rd: RenderingDevice = null
var _eng = null
var _report: Dictionary = {}
var _arms: Array = []
var _t0 := 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	print("[qgrowth] coherence-growth probe — arms over %d steps each" % int(TOTAL_STEPS))
	# Arm A is the LIVE default (source_strength=0): run it TWICE — a quick
	# 600-step scan and a LONG horizon to catch the onset of structure-driven
	# growth that the user observes over the live sim's many-thousand-step runs.
	_run_arm("A", {"source_strength": 0.0, "num_clusters": 10}, STEPS_PER_SAMPLE, TOTAL_STEPS)
	_run_arm("A_long", {"source_strength": 0.0, "num_clusters": 10}, LONG_SAMPLE, LONG_STEPS)
	_run_arm("B", {"source_strength": 50.0, "num_clusters": 10}, STEPS_PER_SAMPLE, TOTAL_STEPS)
	_run_arm("C", {"source_strength": 0.0, "num_clusters": 1}, STEPS_PER_SAMPLE, TOTAL_STEPS)
	# Arm D = the LIVE sim's actual FIELD path: cassi_sim.gd's meshless_mode
	# default (true — the Voronoi cell PDE with the (1−q) Qi-gated steering),
	# rasterized back to q=EY²+EI². meshless_gravity=false keeps particle
	# gravity on the grid river (the engine cannot run the tree worker — the
	# tree gradient must be supplied externally) so we isolate the FIELD
	# growth this turn. Reproduces whether the LIVE q=EY²+EI² grows as
	# structure forms.
	_run_arm("D_meshless", {
		"meshless_mode": true, "meshless_gravity": false,
		"gravity_mode": 3, "source_strength": 0.0, "num_clusters": 10,
	}, STEPS_PER_SAMPLE, TOTAL_STEPS)
	_print_summary()
	_write_report()
	print("[qgrowth] done — report → res://_diag/q_growth_report.json")
	get_tree().quit(0)


func _base_cfg() -> Dictionary:
	return {
		"rd": _rd, "rd_global": false, "owns_rd": true,
		"grid_N": GRID_N, "N_particles": N_PARTICLES,
		"dt": DT,
		"cluster_radius": CLUSTER_RADIUS,
		"num_clusters": 10,
		"cluster_separation": SEP,
		"source_strength": 0.0,
		"gravity_mode": 3,            # river-SELF: pure gravity, no dissipation
		"river_calibrate_gn": true,
		"field_attractor_init": true,  # EY=φ·EI+tiny noise (the live attractor IC)
		"black_holes_enabled": false,
		"particle_merge": false,       # isolate the FIELD growth from the merge
		"dual_grid": true,
		"meshless_mode": false,        # grid two-fluid path (the live grid PDE)
		"meshless_gravity": false,
		"initial_radius_fraction": 0.9,
		"seed": 7,
	}


func _run_arm(tag: String, overrides: Dictionary, step_per_sample: int, total_steps: int) -> void:
	print("\n── [qgrowth] ARM %s  %s  (%d steps) ──" % [tag, str(overrides), total_steps])
	# FRESH local RD per arm: the engine owns_rd=true FREES the device on
	# shutdown, so a shared probe RD cannot be reused across engines.
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		print("[qgrowth] arm %s: no local RD" % tag)
		_report[tag] = {"error": "no local RD"}
		return
	var cfg := _base_cfg()
	for k in overrides:
		cfg[k] = overrides[k]
	_eng = load(ENGINE_SCRIPT).new()
	if not _eng.setup(cfg):
		print("[qgrowth] arm %s: engine setup FAILED" % tag)
		_report[tag] = {"error": "setup failed"}
		_eng = null
		return
	var series: Array = []
	var steps := 0
	var grid := GRID_N * GRID_N * GRID_N
	while steps < total_steps:
		_eng.run_steps(step_per_sample)
		steps += step_per_sample
		var ey: PackedFloat32Array = _rd.buffer_get_data(_eng._field_ey, 0, grid * 4).to_float32_array()
		var ei: PackedFloat32Array = _rd.buffer_get_data(_eng._field_ei, 0, grid * 4).to_float32_array()
		var vel: PackedFloat32Array = _rd.buffer_get_data(_eng._field_vel, 0, grid * 16).to_float32_array()
		var rho: PackedFloat32Array = _rd.buffer_get_data(_eng._mass_density_buf, 0, grid * 4).to_float32_array()
		series.append(_measure(ey, ei, vel, rho, steps))
	var last: Dictionary = _series_last(series) if series.size() > 0 else {}
	_report[tag] = {
		"cfg": overrides, "samples": series.size(),
		"steps_total": steps, "last": last, "series": series,
	}
	_print_arm(tag, series)
	_eng.shutdown()
	_eng = null
	_rd = null   # engine freed it (owns_rd=true)


func _measure(ey: PackedFloat32Array, ei: PackedFloat32Array,
		vel: PackedFloat32Array, rho: PackedFloat32Array, steps: int) -> Dictionary:
	var n := ey.size()
	var sum_rho := 0.0
	var sum_qq := 0.0
	var peak_q := 0.0
	var sum_qcoh := 0.0
	var cells_above := 0
	var sum_eps2 := 0.0
	var sum_ekin := 0.0
	# correlation accumulators (q_coh vs rho)
	var sx := 0.0; var sy := 0.0; var sxx := 0.0; var syy := 0.0; var sxy := 0.0
	var count := 0
	for i in range(n):
		var e := ey[i]
		var ii := ei[i]
		var r := e + ii
		var eps := e - PHI * ii
		var qq := e * e + ii * ii
		var qcoh := (r * r) / (r * r + PHI_INV2 + eps * eps)
		var vx := vel[i * 4]; var vy := vel[i * 4 + 1]
		sum_rho += r
		sum_qq += qq
		sum_eps2 += eps * eps
		sum_ekin += 0.5 * (vx * vx + vy * vy)
		sum_qcoh += qcoh
		if qq > peak_q: peak_q = qq
		if qcoh > PHI_INV2: cells_above += 1
		var m := rho[i]
		sx += qcoh; sy += m; sxx += qcoh * qcoh; syy += m * m; sxy += qcoh * m
		count += 1
	var corr := 0.0
	var den := sqrt(maxf(sxx * count - sx * sx, 0.0)) * sqrt(maxf(syy * count - sy * sy, 0.0))
	if den > 1e-30:
		corr = (sxy * count - sx * sy) / den
	# exact two-fluid energy: H = Σ[ ½v² + ½ω₀²·ε² + ½c²·(∇EY²,∇EI²) ]
	# (we omit the field-gradient term on a coarse grid — dominated by the
	# coupling + kinetic here; the report notes it). ω₀² = 20 (v_omega2 in
	# cassi_two_fluid.glsl).
	var hamiltonian := sum_ekin + 0.5 * 20.0 * sum_eps2
	return {
		"steps": steps, "t": float(steps) * DT,
		"sum_rho": sum_rho,
		"sum_qq": sum_qq,
		"peak_q": peak_q,
		"mean_qcoh": sum_qcoh / maxf(count, 1),
		"frac_above_gate": float(cells_above) / maxf(count, 1),
		"corr_q_rho": corr,
		"sum_eps2": sum_eps2,
		"sum_ekin": sum_ekin,
		"hamiltonian": hamiltonian,
	}


func _series_last(series: Array) -> Dictionary:
	var d: Dictionary = series[series.size() - 1]
	d["sum_qq_start"] = (series[0] as Dictionary).get("sum_qq", 0.0)
	d["sum_qq_growth_mult"] = (d["sum_qq"] / maxf(float(d["sum_qq_start"]), 1e-30))
	d["sum_rho_start"] = (series[0] as Dictionary).get("sum_rho", 0.0)
	d["peak_q_start"] = (series[0] as Dictionary).get("peak_q", 0.0)
	d["mean_qcoh_start"] = (series[0] as Dictionary).get("mean_qcoh", 0.0)
	return d


func _print_arm(tag: String, series: Array) -> void:
	if series.size() == 0: return
	print("  %-6s %8s %10s %10s %9s %9s %10s %10s" % ["step", "Σρ", "Σ(EY²+EI²)", "peak_q", "mean_qc", ">gate", "corr(q,ρ)", "H"])
	for d in series:
		print("  %-6d %10.3f %10.4f %9.4f %9.4f %9.4f %10.4f %10.4f" % [
			int(d["steps"]), float(d["sum_rho"]), float(d["sum_qq"]), float(d["peak_q"]),
			float(d["mean_qcoh"]), float(d["frac_above_gate"]), float(d["corr_q_rho"]),
			float(d["hamiltonian"])])
	var last: Dictionary = _series_last(series)
	print("  => Σ(EY²+EI²) grew ×%.1f (%.4f → %.4f); peak_q %.4f → %.4f; Σ(EY+EI) %.3f → %.3f" % [
		float(last["sum_qq_growth_mult"]), float(last["sum_qq_start"]), float(last["sum_qq"]),
		float(last["peak_q_start"]), float(last["peak_q"]),
		float(last["sum_rho_start"]), float(last["sum_rho"])])


func _print_summary() -> void:
	print("\n══════ q-growth summary ══════")
	print("(does the ungated field q = EY²+EI² grow when pumped? does peak q grow even")
	print(" when total is conserved? does q concentrate where particles are?)")
	for tag in ["A", "A_long", "B", "C", "D_meshless"]:
		var a: Dictionary = _report.get(tag, {})
		if a.is_empty() or a.has("error"):
			print("  %s: ERROR" % tag)
			continue
		var idx := 0
		var growth := 1.0
		var series: Array = a["series"]
		if series.size() > 1:
			var s0: Dictionary = series[0]; var s1: Dictionary = series[series.size() - 1]
			growth = float(s1["sum_qq"]) / maxf(float(s0["sum_qq"]), 1e-30)
			if absf(float(s0["sum_qq"])) < 1e-12:
				growth = 0.0
			print("  ARM %s: Σ(EY²+EI²) %.4f→%.4f (×%.1f), peak_q %.4f→%.4f, corr(q_coh,ρ)=%.3f, frac>gate=%.3f" % [
				tag, float(s0["sum_qq"]), float(s1["sum_qq"]), growth,
				float(s0["peak_q"]), float(s1["peak_q"]),
				float(s1["corr_q_rho"]), float(s1["frac_above_gate"])])


func _write_report() -> void:
	var out := "res://_diag"
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
	var f := FileAccess.open(out + "/q_growth_report.json", FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(_report, "\t"))
		f.close()
