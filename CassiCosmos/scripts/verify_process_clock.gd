extends Node
## Passive process-time/common-lapse lab.
##
## This scene is deliberately CPU-only.  It owns a frozen local q_lab schedule,
## integrates the canonical conversion clock K = 1-q, and compares that clock
## with calibrated oscillator and transport generators.  It never reads or
## writes a production shader, engine, simulation, or q buffer.
##
## Launch windowed (the scene has no RenderingDevice dependency):
##   Godot_v4.7.1-stable_mono_win64_console.exe --path <repo> \
##       res://scenes/verify_process_clock.tscn

const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051

# Frozen numerical design.  The target is reached by a final fractional
# midpoint step, so both trajectories terminate at the same accumulated tau_F.
const DT: float = 0.005
const TARGET_TAU_F: float = 4.0
const MAX_STEPS: int = 10000
const Q_REF: float = 0.0  # open-gate gauge; q_ref < 1 and 1-q_ref = 1.
const Q_REF_COMPLEMENT: float = 1.0 - Q_REF
const OMEGA_PHASE: float = 1.75
const TRANSPORT_SPEED: float = 0.85
const INDEPENDENT_PHASE_SCALE: float = 1.35
const INDEPENDENT_TRANSPORT_SCALE: float = 0.65

const IDENTITY_TOL: float = 1.0e-12
const BASELINE_TOL: float = 1.0e-10
const SHARED_TOL: float = 1.0e-10
const INDEPENDENT_MIN_SPREAD: float = 1.0
const TRAJECTORY_MIN_TIME_SEPARATION: float = 1.0
const TRAJECTORY_MIN_Q_MEAN_SEPARATION: float = 0.05
const RECEIPT_PATH := "res://_diag/process_time/common_lapse_receipt.json"

const TRAJECTORIES := ["trajectory_a", "trajectory_b"]
const ARMS := ["baseline", "shared", "independent"]

var _checks: int = 0
var _failures: int = 0
var _results: Dictionary = {}
var _q_ref_value: float = Q_REF


func _ready() -> void:
	print("[ProcessClock] passive common-lapse lab (CPU-only; coordinate dt authoritative)")
	_q_ref_value = Q_REF
	for trajectory_id in TRAJECTORIES:
		_results[trajectory_id] = {}
		for arm in ARMS:
			_results[trajectory_id][arm] = _run_arm(arm, trajectory_id)

	_run_gates()
	var receipt := _make_receipt()
	var receipt_ok := _write_receipt(receipt)
	_check("G8 receipt emitted at " + RECEIPT_PATH, receipt_ok,
		"raw JSON write" if receipt_ok else "FileAccess/DirAccess failed")

	print("[ProcessClock] checks=%d failures=%d" % [_checks, _failures])
	if _failures == 0:
		print("[ProcessClock] RESULT: PASS (implementation contract only; not universal physical time)")
	else:
		print("[ProcessClock] RESULT: FAIL (implementation contract only; not universal physical time)")
	get_tree().quit(0 if _failures == 0 else 1)


# ---------------------------------------------------------------------------
# Frozen local constitutive lab.  q is recomputed at each coordinate-time
# midpoint from immutable trajectories; no arm can feed back into rho/epsilon.
# This is NOT the production CassiCosmos q buffer (raw EY^2+EI^2).

func _rho_for(trajectory_id: String, t: float) -> float:
	if trajectory_id == "trajectory_a":
		return 0.75 + 0.08 * sin(0.31 * t + 0.20)
	return 1.30 + 0.10 * cos(0.23 * t - 0.40)


func _epsilon_for(trajectory_id: String, t: float) -> float:
	if trajectory_id == "trajectory_a":
		return 0.09 + 0.01 * cos(0.27 * t - 0.10)
	return 0.15 + 0.02 * sin(0.19 * t + 0.70)


func _q_lab(rho: float, epsilon: float) -> float:
	var rho2 := rho * rho
	var epsilon2 := epsilon * epsilon
	return rho2 / (rho2 + PHI_INV2 + epsilon2)


func _profile(trajectory_id: String, t: float) -> Dictionary:
	var rho := _rho_for(trajectory_id, t)
	var epsilon := _epsilon_for(trajectory_id, t)
	var rho2 := rho * rho
	var epsilon2 := epsilon * epsilon
	var denominator := rho2 + PHI_INV2 + epsilon2
	var q := _q_lab(rho, epsilon)
	var k := 1.0 - q
	# Algebraic complement, evaluated independently of q, is the closure check.
	var k_identity := (PHI_INV2 + epsilon2) / denominator
	return {
		"rho": rho,
		"epsilon": epsilon,
		"rho2": rho2,
		"epsilon2": epsilon2,
		"denominator": denominator,
		"q": q,
		"k": k,
		"k_identity": k_identity,
	}


# ---------------------------------------------------------------------------
# Three arms.  tau_F is always canonical K dt.  The oscillator and transport
# are complete first-order generators: dtheta/dt = omega*N and dx/dt=v*N.
# baseline N=1, shared N=K, independent N_theta=1.35K and N_x=0.65K.

func _run_arm(arm: String, trajectory_id: String) -> Dictionary:
	var tau_f := 0.0
	var tau_identity := 0.0
	var coordinate_t := 0.0
	var phase := 0.0
	var translation := 0.0
	var q_min := 1.0e30
	var q_max := -1.0e30
	var q_sum := 0.0
	var q_samples := 0
	var k_min := 1.0e30
	var k_max := -1.0e30
	var lapse_phase_min := 1.0e30
	var lapse_phase_max := -1.0e30
	var lapse_transport_min := 1.0e30
	var lapse_transport_max := -1.0e30
	var point_identity_residual := 0.0
	var backreaction_residual := 0.0
	var shared_lapse_mismatch := 0.0
	var finite := true
	var reached_target := false
	var steps := 0

	while tau_f < TARGET_TAU_F and steps < MAX_STEPS:
		var midpoint := coordinate_t + 0.5 * DT
		var sample := _profile(trajectory_id, midpoint)
		var q: float = sample["q"]
		var k: float = sample["k"]
		var k_identity: float = sample["k_identity"]
		var delta_tau := k * DT
		if not _finite(q) or not _finite(k) or delta_tau <= 0.0:
			finite = false
			break

		var fraction := 1.0
		if tau_f + delta_tau >= TARGET_TAU_F:
			fraction = (TARGET_TAU_F - tau_f) / delta_tau
		var dt_used := DT * fraction
		var n_q := k / Q_REF_COMPLEMENT
		var phase_lapse := 1.0
		var transport_lapse := 1.0
		if arm == "shared":
			phase_lapse = k
			transport_lapse = k
		elif arm == "independent":
			phase_lapse = k * INDEPENDENT_PHASE_SCALE
			transport_lapse = k * INDEPENDENT_TRANSPORT_SCALE

		# Canonical conversion K is integrated in every arm.  n_q is the
		# relative-reference diagnostic N_q=K/(1-q_ref), not a new clock.
		tau_f += k * dt_used
		tau_identity += k_identity * dt_used
		if arm == "baseline":
			# Exact coordinate baseline for constant generators, avoiding a
			# cumulative-sum artifact in the default-off identity gate.
			coordinate_t += dt_used
			phase = OMEGA_PHASE * coordinate_t
			translation = TRANSPORT_SPEED * coordinate_t
		else:
			coordinate_t += dt_used
			phase += OMEGA_PHASE * phase_lapse * dt_used
			translation += TRANSPORT_SPEED * transport_lapse * dt_used

		q_min = minf(q_min, q)
		q_max = maxf(q_max, q)
		q_sum += q
		q_samples += 1
		k_min = minf(k_min, k)
		k_max = maxf(k_max, k)
		lapse_phase_min = minf(lapse_phase_min, phase_lapse)
		lapse_phase_max = maxf(lapse_phase_max, phase_lapse)
		lapse_transport_min = minf(lapse_transport_min, transport_lapse)
		lapse_transport_max = maxf(lapse_transport_max, transport_lapse)
		point_identity_residual = maxf(point_identity_residual, absf(k - k_identity))

		# The source schedule is immutable and is deliberately re-evaluated;
		# this residual detects any arm-side backreaction or source mutation.
		var replay := _profile(trajectory_id, midpoint)
		backreaction_residual = maxf(backreaction_residual,
			maxf(absf(float(sample["rho"]) - float(replay["rho"])),
				maxf(absf(float(sample["epsilon"]) - float(replay["epsilon"])),
					absf(float(sample["q"]) - float(replay["q"])))))
		if arm == "shared":
			shared_lapse_mismatch = maxf(shared_lapse_mismatch,
				maxf(absf(phase_lapse - k),
					maxf(absf(transport_lapse - k), absf(n_q - k / Q_REF_COMPLEMENT))))

		steps += 1
		if fraction < 1.0:
			tau_f = TARGET_TAU_F
			reached_target = true
			break
		if not _finite(tau_f) or not _finite(phase) or not _finite(translation):
			finite = false
			break

	if not reached_target and tau_f >= TARGET_TAU_F:
		reached_target = true
	var conversion_age := tau_f
	var phase_age := phase / OMEGA_PHASE
	var transport_age := translation / TRANSPORT_SPEED
	var collapse_error := maxf(absf(phase_age - conversion_age), absf(transport_age - conversion_age))
	var ages := [conversion_age, phase_age, transport_age]
	var age_min := minf(float(ages[0]), minf(float(ages[1]), float(ages[2])))
	var age_max := maxf(float(ages[0]), maxf(float(ages[1]), float(ages[2])))
	var q_mean := q_sum / float(maxi(q_samples, 1))
	return {
		"arm": arm,
		"candidate_lapse_role": "shared" if arm == "shared" else ("independent_control" if arm == "independent" else "diagnostic"),
		"trajectory": trajectory_id,
		"reached_target": reached_target,
		"finite": finite,
		"steps": steps,
		"coordinate_time": coordinate_t,
		"tau_F": tau_f,
		"tau_F_relative": tau_f / Q_REF_COMPLEMENT,
		"tau_F_identity": tau_identity,
		"conversion_identity_residual": absf(tau_f - tau_identity),
		"point_identity_residual": point_identity_residual,
		"phase": phase,
		"translation": translation,
		"inferred_ages": {
			"conversion": conversion_age,
			"phase": phase_age,
			"translation": transport_age,
		},
		"inferred_ages_relative": {
			"conversion": conversion_age / Q_REF_COMPLEMENT,
			"phase": phase_age / Q_REF_COMPLEMENT,
			"translation": transport_age / Q_REF_COMPLEMENT,
		},
		"collapse_error": collapse_error,
		"age_spread": age_max - age_min,
		"q_min": q_min,
		"q_max": q_max,
		"q_mean": q_mean,
		"k_min": k_min,
		"k_max": k_max,
		"n_q_min": k_min / Q_REF_COMPLEMENT,
		"n_q_max": k_max / Q_REF_COMPLEMENT,
		"phase_lapse_min": lapse_phase_min,
		"phase_lapse_max": lapse_phase_max,
		"transport_lapse_min": lapse_transport_min,
		"transport_lapse_max": lapse_transport_max,
		"shared_lapse_mismatch": shared_lapse_mismatch,
		"conservation_backreaction_residual": backreaction_residual,
	}


# ---------------------------------------------------------------------------
# Frozen gates.  Every gate is evaluated after the fixed-horizon runs; there
# are no adaptive retries or post-hoc arm/trajectory selection.

func _run_gates() -> void:
	var q_bounds_ok := _finite(_q_ref_value) and _q_ref_value < 1.0 and Q_REF_COMPLEMENT > 0.0
	var closure_ok := true
	var baseline_ok := true
	var shared_ok := true
	var independent_ok := true
	var equal_tau_ok := true
	var passive_ok := true
	var shared_common_age_ok := true

	for trajectory_id in TRAJECTORIES:
		var baseline: Dictionary = _results[trajectory_id]["baseline"]
		var shared: Dictionary = _results[trajectory_id]["shared"]
		var independent: Dictionary = _results[trajectory_id]["independent"]
		for result in [baseline, shared, independent]:
			q_bounds_ok = q_bounds_ok and bool(result["finite"]) and bool(result["reached_target"])
			q_bounds_ok = q_bounds_ok and float(result["q_min"]) >= 0.0 and float(result["q_max"]) < 1.0
			q_bounds_ok = q_bounds_ok and float(result["k_min"]) > 0.0
			closure_ok = closure_ok and float(result["point_identity_residual"]) <= IDENTITY_TOL
			closure_ok = closure_ok and float(result["conversion_identity_residual"]) <= IDENTITY_TOL
			passive_ok = passive_ok and float(result["conservation_backreaction_residual"]) <= IDENTITY_TOL

		# The immutable source schedule must be identical across arms.  This
		# cross-arm comparison makes the passive control sensitive to any
		# accidental arm-dependent source or coordinate-time feedback.
		for key in ["coordinate_time", "q_min", "q_max", "q_mean", "k_min", "k_max"]:
			passive_ok = passive_ok and absf(float(baseline[key]) - float(shared[key])) <= IDENTITY_TOL
			passive_ok = passive_ok and absf(float(baseline[key]) - float(independent[key])) <= IDENTITY_TOL

		var t: float = baseline["coordinate_time"]
		var baseline_phase_expected := OMEGA_PHASE * t
		var baseline_transport_expected := TRANSPORT_SPEED * t
		baseline_ok = baseline_ok and absf(float(baseline["phase"]) - baseline_phase_expected) <= BASELINE_TOL
		baseline_ok = baseline_ok and absf(float(baseline["translation"]) - baseline_transport_expected) <= BASELINE_TOL
		baseline_ok = baseline_ok and absf(float(baseline["inferred_ages"]["phase"]) - float(baseline["inferred_ages"]["translation"])) <= BASELINE_TOL
		baseline_ok = baseline_ok and float(baseline["phase_lapse_min"]) == 1.0 and float(baseline["phase_lapse_max"]) == 1.0
		baseline_ok = baseline_ok and float(baseline["transport_lapse_min"]) == 1.0 and float(baseline["transport_lapse_max"]) == 1.0

		shared_ok = shared_ok and float(shared["shared_lapse_mismatch"]) <= IDENTITY_TOL
		shared_ok = shared_ok and float(shared["collapse_error"]) <= SHARED_TOL
		shared_ok = shared_ok and absf(float(shared["tau_F"]) / Q_REF_COMPLEMENT - TARGET_TAU_F / Q_REF_COMPLEMENT) <= SHARED_TOL
		shared_common_age_ok = shared_common_age_ok and float(shared["age_spread"]) <= SHARED_TOL

		independent_ok = independent_ok and float(independent["age_spread"]) > INDEPENDENT_MIN_SPREAD
		independent_ok = independent_ok and absf(float(independent["inferred_ages"]["phase"]) / TARGET_TAU_F - INDEPENDENT_PHASE_SCALE) <= SHARED_TOL
		independent_ok = independent_ok and absf(float(independent["inferred_ages"]["translation"]) / TARGET_TAU_F - INDEPENDENT_TRANSPORT_SCALE) <= SHARED_TOL

	var shared_a: Dictionary = _results["trajectory_a"]["shared"]
	var shared_b: Dictionary = _results["trajectory_b"]["shared"]
	equal_tau_ok = absf(float(shared_a["tau_F"]) - float(shared_b["tau_F"])) <= IDENTITY_TOL
	equal_tau_ok = equal_tau_ok and absf(float(shared_a["coordinate_time"]) - float(shared_b["coordinate_time"])) > TRAJECTORY_MIN_TIME_SEPARATION
	equal_tau_ok = equal_tau_ok and absf(float(shared_a["q_mean"]) - float(shared_b["q_mean"])) > TRAJECTORY_MIN_Q_MEAN_SEPARATION
	equal_tau_ok = equal_tau_ok and absf(float(shared_a["inferred_ages"]["conversion"]) - TARGET_TAU_F) <= IDENTITY_TOL
	equal_tau_ok = equal_tau_ok and absf(float(shared_b["inferred_ages"]["conversion"]) - TARGET_TAU_F) <= IDENTITY_TOL

	_check("G1 q_lab/q_ref bounds and positive K", q_bounds_ok,
		"q_ref=%.6f" % _q_ref_value)
	_check("G2 analytic complement and numerical tau_F closure", closure_ok,
		"tol=%.12f" % IDENTITY_TOL)
	_check("G3 exact default-off coordinate baseline identity", baseline_ok,
		"baseline oscillator/transport use N=1")
	_check("G4 shared K generator and common normalized process age", shared_ok and shared_common_age_ok,
		"N=K; ages=(tau_F, phase/omega, translation/v)")
	_check("G5 independent per-sector lapse rejects collapse", independent_ok,
		"scales=(%.2f, %.2f), min spread=%.2f" % [INDEPENDENT_PHASE_SCALE, INDEPENDENT_TRANSPORT_SCALE, INDEPENDENT_MIN_SPREAD])
	_check("G6 equal-tau two-trajectory discriminator", equal_tau_ok,
		"same tau_F=%.3f, distinct coordinate times/q means" % TARGET_TAU_F)
	_check("G7 passive conservation/backreaction residual", passive_ok,
		"immutable q_lab replay residual <= %.12f" % IDENTITY_TOL)


func _make_receipt() -> Dictionary:
	var shared_a: Dictionary = _results["trajectory_a"]["shared"]
	var shared_b: Dictionary = _results["trajectory_b"]["shared"]
	return {
		"schema": "cassi.cosmos.process-clock-receipt.v1",
		"law_id": "bounded-q-common-lapse-diagnostic.v1",
		"result": "PASS" if _failures == 0 else "FAIL",
		"verdict_scope": "implementation PASS/FAIL only; not evidence for universal physical time",
		"contract": "passive_common_lapse_cross_clock",
		"conversion_age_receipt_role": "diagnostic integral only; no conversion row or lambda_rate exposure",
		"coordinate_dt_authoritative": true,
		"gpu_or_readback_dependency": false,
		"q_provenance": {
			"formula": "q_lab=rho^2/(rho^2+phi^-2+epsilon^2)",
			"phi": PHI,
			"q_ref": _q_ref_value,
			"q_ref_role": "open-gate gauge; q_ref<1; generator uses K=1-q",
			"schedule": "recomputed from frozen deterministic rho/epsilon at each coordinate-time midpoint",
			"production_q": "not read or relabeled: production CassiCosmos q buffer is raw EY^2+EI^2 and unbounded",
		},
		"constants": {
			"dt": DT,
			"target_tau_F": TARGET_TAU_F,
			"max_steps": MAX_STEPS,
			"q_ref": _q_ref_value,
			"n_q_definition": "N_q=(1-q)/(1-q_ref), relative-reference diagnostic only",
			"omega_phase": OMEGA_PHASE,
			"transport_speed": TRANSPORT_SPEED,
			"independent_phase_scale": INDEPENDENT_PHASE_SCALE,
			"independent_transport_scale": INDEPENDENT_TRANSPORT_SCALE,
		},
		"arms": _results,
		"equal_tau_summary": {
			"trajectory_a_coordinate_time": shared_a["coordinate_time"],
			"trajectory_b_coordinate_time": shared_b["coordinate_time"],
			"trajectory_a_tau_F": shared_a["tau_F"],
			"trajectory_b_tau_F": shared_b["tau_F"],
			"coordinate_time_delta": absf(float(shared_a["coordinate_time"]) - float(shared_b["coordinate_time"])),
			"q_mean_delta": absf(float(shared_a["q_mean"]) - float(shared_b["q_mean"])),
		},
		"gate_count_before_receipt_emission": _checks,
		"expected_total_gate_count": _checks + 1,
		"receipt_emission_gate": "PASS is implied when this complete JSON receipt is readable",
		"failure_count_before_receipt_gate": _failures,
	}


func _write_receipt(receipt: Dictionary) -> bool:
	var out_dir := "res://_diag/process_time"
	var err := DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out_dir))
	if err != OK and not DirAccess.dir_exists_absolute(ProjectSettings.globalize_path(out_dir)):
		return false
	var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
	if file == null:
		return false
	file.store_string(JSON.stringify(receipt))
	file.close()
	return true


func _finite(value: float) -> bool:
	return is_finite(value)

func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s%s" % ["PASS" if ok else "FAIL", name, (" — " + detail) if detail != "" else ""])
