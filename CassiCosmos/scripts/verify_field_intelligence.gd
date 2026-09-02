extends Node

const TARGETS := [
	Vector3(6.0, 0.0, 0.0),
	Vector3(-6.0, 0.0, 0.0),
	Vector3(0.0, 6.0, 0.0),
	Vector3(0.0, -6.0, 0.0),
	Vector3(0.0, 0.0, 6.0),
	Vector3(0.0, 0.0, -6.0),
]
const TARGET_RADIUS := 0.75
const TRAIN_STEPS := 216
const REPLAY_STEPS := 300
const NORMAL_ETA := 0.18
const FAILURE_DISTANCE := 1.0e30

@onready var sim = $CassiSim
@onready var status_label: Label = $Status

var _failures: Array[String] = []
var _results := {}


func _ready() -> void:
	sim.playing = false
	await get_tree().process_frame
	await _run_verification()


func _gate(name: String, passed: bool, detail: String) -> void:
	var verdict := "PASS" if passed else "FAIL"
	print("FIELD_INTELLIGENCE_GATE %s %s — %s" % [name, verdict, detail])
	status_label.text = "%s  %s\n%s" % [name, verdict, detail]
	if not passed:
		_failures.append("%s: %s" % [name, detail])


func _run_verification() -> void:
	# FI1 paired default-off identity: full FI descriptors with runtime OFF
	# versus the one-cell disabled fallback, from the same deterministic IC.
	sim.field_intelligence_render = false
	sim.field_intelligence_enabled = true
	sim.field_intelligence_eta = NORMAL_ETA
	sim.field_intelligence_reward_control = 0
	sim.reinit()
	await get_tree().process_frame
	sim._time = 0.0
	var toggle: Dictionary = sim.field_intelligence_set_runtime_enabled_for_verify(false)
	await _run_steps(8)
	var full_off: Dictionary = sim.field_state_digest_for_verify()

	sim.field_intelligence_enabled = false
	sim.reinit()
	await get_tree().process_frame
	sim._time = 0.0
	await _run_steps(8)
	var fallback_off: Dictionary = sim.field_state_digest_for_verify()
	_gate("FI1", toggle.get("ok", false) and full_off.get("ok", false)
			and fallback_off.get("ok", false)
			and full_off.get("checksum", "") == fallback_off.get("checksum", ""),
			"default-off full/fallback SHA-256 %s / %s" % [
			str(full_off.get("checksum", "")).left(12),
			str(fallback_off.get("checksum", "")).left(12)])

	await _configure(NORMAL_ETA, 0)
	var initial: Dictionary = sim.field_intelligence_snapshot()
	var abi_ok: bool = bool(initial.get("ok", false)) \
			and int(initial.get("plasticity_bytes", -1)) == 64 * 64 * 64 * 8 \
			and int(initial.get("state_bytes", -1)) == 128
	_gate("FI0", abi_ok,
			"P/e bytes=%s header bytes=%s profile=%s" % [
			initial.get("plasticity_bytes", -1), initial.get("state_bytes", -1),
			str(initial.get("profile", "")).left(24)])

	# FI8 same-list receipt and FI7 read-only render purity.
	var episode_ok := _set_episode(TARGETS[0], false)
	sim.field_intelligence_render = true
	await _run_steps(1)
	var receipt_status: Dictionary = sim.field_intelligence_status()
	var receipt: Dictionary = sim.field_intelligence_render_receipt_for_verify()
	_gate("FI8", episode_ok and receipt_status.get("ok", false) and receipt.get("ok", false)
			and int(receipt.get("tick", -1)) == int(receipt_status.get("tick", -2)),
			"render tick=%s header tick=%s" % [receipt.get("tick", -1),
			receipt_status.get("tick", -2)])
	var before_render: Dictionary = sim.field_intelligence_snapshot()
	var render_result: Dictionary = sim.field_intelligence_render_once_for_verify()
	var after_render: Dictionary = sim.field_intelligence_snapshot()
	_gate("FI7", render_result.get("ok", false)
			and before_render.get("checksum", "") == after_render.get("checksum", ""),
			"learning checksum stayed %s" % str(after_render.get("checksum", "")).left(12))
	sim.field_intelligence_render = false

	# Normal train/replay.
	var cleared_start: Dictionary = sim.field_intelligence_clear()
	var train_statuses: Array[Dictionary] = []
	if cleared_start.get("ok", false):
		train_statuses = await _train_all()
	var trained_snapshot: Dictionary = sim.field_intelligence_snapshot()
	var finite_scan := _scan_learning_state(trained_snapshot, train_statuses)
	_gate("FI2", finite_scan.ok, finite_scan.detail)

	# FI5 exact persistence plus fail-closed profile/checksum checks.
	var clear_for_restore: Dictionary = sim.field_intelligence_clear()
	var restore_exact: Dictionary = sim.field_intelligence_restore(trained_snapshot)
	var restored_exact: Dictionary = sim.field_intelligence_snapshot()
	var exact_ok: bool = bool(clear_for_restore.get("ok", false)) and bool(restore_exact.get("ok", false)) \
			and trained_snapshot.get("checksum", "") == restored_exact.get("checksum", "")
	var bad_checksum := trained_snapshot.duplicate(true)
	bad_checksum["checksum"] = "00" + str(trained_snapshot.get("checksum", "")).substr(2)
	var reject_checksum: Dictionary = sim.field_intelligence_restore(bad_checksum)
	var bad_profile := trained_snapshot.duplicate(true)
	bad_profile["profile"] = "incompatible"
	var reject_profile: Dictionary = sim.field_intelligence_restore(bad_profile)
	var after_reject: Dictionary = sim.field_intelligence_snapshot()
	exact_ok = exact_ok and not reject_checksum.get("ok", false) \
			and not reject_profile.get("ok", false) \
			and after_reject.get("checksum", "") == trained_snapshot.get("checksum", "")
	_gate("FI5", exact_ok, "snapshot SHA-256 %s; incompatible writes rejected" %
			str(trained_snapshot.get("checksum", "")).left(16))
	var trained_distances: Array[float] = await _replay_all()
	var clear_result: Dictionary = sim.field_intelligence_clear()
	var cleared_distances: Array[float] = await _replay_all() if clear_result.get("ok", false) else []
	var restore_result: Dictionary = sim.field_intelligence_restore(trained_snapshot)
	var restored_distances: Array[float] = await _replay_all() if restore_result.get("ok", false) else []

	var trained_success := _successes(trained_distances)
	var cleared_success := _successes(cleared_distances)
	var restored_success := _successes(restored_distances)
	var trained_median := _median(trained_distances)
	var cleared_median := _median(cleared_distances)
	var restored_median := _median(restored_distances)
	_gate("FI3", trained_success >= TARGETS.size() - 1 and cleared_success <= 1
			and trained_median <= 0.5 * cleared_median,
			"success learned=%d/%d clear=%d/%d; median %.4f / %.4f" % [
			trained_success, TARGETS.size(), cleared_success, TARGETS.size(),
			trained_median, cleared_median])
	var recovery_match := restored_distances.size() == trained_distances.size()
	if recovery_match:
		for i in trained_distances.size():
			if absf(restored_distances[i] - trained_distances[i]) > 0.20:
				recovery_match = false
				break
	_gate("FI6", restore_result.get("ok", false)
			and restored_success >= TARGETS.size() - 1 and recovery_match,
			"success restored=%d/%d; median %.4f; learned/restored max Δ ≤ 0.20: %s" % [
			restored_success, TARGETS.size(), restored_median, recovery_match])

	# FI4 controls use the identical target and step schedule.
	await _configure(0.0, 0)
	await _train_all()
	var eta_zero_distances: Array[float] = await _replay_all()
	await _configure(NORMAL_ETA, 1)
	await _train_all()
	var shuffled_distances: Array[float] = await _replay_all()
	var eta_zero_success := _successes(eta_zero_distances)
	var shuffled_success := _successes(shuffled_distances)
	_gate("FI4", eta_zero_success <= 1 and shuffled_success <= 2,
			"η=0 %d/%d; shuffled reward %d/%d" % [
			eta_zero_success, TARGETS.size(), shuffled_success, TARGETS.size()])

	# Three successful rebuilds above exercise buffer/set lifecycle (normal,
	# eta-zero, shuffled) with no stale RID tolerated by the measured gates.
	_gate("FI9", sim._shaders_ready and _failures.filter(
			func(value: String) -> bool: return value.begins_with("FI0")).is_empty(),
			"reinit rebuilt FI buffers and uniform sets across three profiles")

	_results = {
		"trained_distances": trained_distances,
		"cleared_distances": cleared_distances,
		"restored_distances": restored_distances,
		"eta_zero_distances": eta_zero_distances,
		"shuffled_distances": shuffled_distances,
		"trained_success": trained_success,
		"cleared_success": cleared_success,
		"restored_success": restored_success,
		"trained_median": trained_median,
		"cleared_median": cleared_median,
		"restored_median": restored_median,
		"snapshot_checksum": trained_snapshot.get("checksum", ""),
		"failures": _failures,
	}
	_write_result()
	if _failures.is_empty():
		print("FIELD_INTELLIGENCE_VERIFY PASS — FI0–FI9")
		get_tree().quit(0)
	else:
		print("FIELD_INTELLIGENCE_VERIFY FAIL — %s" % "; ".join(_failures))
		get_tree().quit(1)


func _configure(eta: float, reward_control: int) -> void:
	sim.playing = false
	sim.field_intelligence_enabled = true
	sim.field_intelligence_render = false
	sim.field_intelligence_eta = eta
	sim.field_intelligence_reward_control = reward_control
	sim.reinit()
	await get_tree().process_frame
	sim._time = 0.0
	sim._update_field_intelligence_params()
	var result: Dictionary = sim.field_intelligence_clear()
	if not result.get("ok", false):
		_failures.append("configure: %s" % result.get("error", "unknown"))


func _train_all() -> Array[Dictionary]:
	var statuses: Array[Dictionary] = []
	for target in TARGETS:
		if not _set_episode(target, true):
			break
		await _run_steps(TRAIN_STEPS)
		statuses.append(sim.field_intelligence_status())
	return statuses


func _replay_all() -> Array[float]:
	var distances: Array[float] = []
	for target in TARGETS:
		if not _set_episode(target, false):
			break
		await _run_steps(REPLAY_STEPS)
		var status: Dictionary = sim.field_intelligence_status()
		if not status.get("ok", false):
			_failures.append("replay telemetry unavailable")
			distances.append(FAILURE_DISTANCE)
			continue
		var distance := float(status.distance)
		if not is_finite(distance):
			_failures.append("non-finite replay distance")
			distance = FAILURE_DISTANCE
		distances.append(distance)
	return distances


func _set_episode(target: Vector3, training: bool) -> bool:
	sim.playing = false
	var probe: Dictionary = sim.field_intelligence_set_probe_state(Vector3.ZERO)
	var goal: Dictionary = sim.field_intelligence_set_target(target, TARGET_RADIUS, training)
	if not probe.get("ok", false) or not goal.get("ok", false):
		_failures.append("episode setup failed: %s / %s" % [probe, goal])
		return false
	return true


func _run_steps(count: int) -> void:
	var remaining := count
	while remaining > 0:
		var batch := mini(12, remaining)
		sim._run_physics_steps(batch)
		remaining -= batch
		await get_tree().process_frame


func _scan_learning_state(snapshot_data: Dictionary,
		statuses: Array[Dictionary]) -> Dictionary:
	if not snapshot_data.get("ok", false):
		return {"ok": false, "detail": "snapshot unavailable"}
	var bytes: PackedByteArray = snapshot_data.plasticity
	var p_peak := 0.0
	var e_peak := 0.0
	for offset in range(0, bytes.size(), 8):
		var p := bytes.decode_float(offset)
		var eligibility := bytes.decode_float(offset + 4)
		if not is_finite(p) or not is_finite(eligibility) \
				or absf(p) > sim.field_intelligence_p_max + 1e-5:
			return {"ok": false, "detail": "non-finite or unbounded P/e at byte %d" % offset}
		p_peak = maxf(p_peak, absf(p))
		e_peak = maxf(e_peak, absf(eligibility))
	for status in statuses:
		for key in ["distance", "reward", "control_energy", "support_margin"]:
			if not is_finite(float(status.get(key, NAN))):
				return {"ok": false, "detail": "non-finite telemetry %s" % key}
		var command: Vector3 = status.get("control", Vector3(INF, INF, INF))
		if not command.is_finite() or absf(command.x) > 8.0 \
				or absf(command.y) > 8.0 or absf(command.z) > 8.0 \
				or int(status.get("faults", 1)) != 0:
			return {"ok": false, "detail": "invalid bounded control or fault"}
	return {"ok": true, "detail": "finite P/e; |P|max=%.5f |e|max=%.5f" % [p_peak, e_peak]}


func _successes(values: Array[float]) -> int:
	var count := 0
	for value in values:
		if value <= TARGET_RADIUS:
			count += 1
	return count


func _median(values: Array[float]) -> float:
	if values.is_empty():
		return INF
	var sorted := values.duplicate()
	sorted.sort()
	return sorted[sorted.size() / 2]


func _write_result() -> void:
	var file := FileAccess.open("res://_diag/field_intelligence_verify.json", FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(_results, "  "))


func _exit_tree() -> void:
	if sim != null and sim.has_method("shutdown"):
		sim.shutdown()
