extends Node3D

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
const POLL_SEC := 0.15
const HOLD_MS := 450

@export var auto_story := true

@onready var sim = $CassiSim
@onready var field_view: TextureRect = $UI/FieldPanel/FieldView
@onready var stage_label: Label = $UI/InfoPanel/Margin/Rows/Stage
@onready var metrics_label: Label = $UI/InfoPanel/Margin/Rows/Metrics
@onready var progress_label: Label = $UI/InfoPanel/Margin/Rows/Progress
@onready var verdict_label: Label = $UI/InfoPanel/Margin/Rows/Verdict
@onready var pause_button: Button = $UI/InfoPanel/Margin/Rows/Controls/Pause
@onready var probe_marker: MeshInstance3D = $ProbeMarker
@onready var target_marker: MeshInstance3D = $TargetMarker
@onready var organ_marker: MeshInstance3D = $OrganMarker

var _phase := "BOOT"
var _target_index := 0
var _step_limit := 0
var _poll_accum := 0.0
var _hold_until_ms := 0
var _pending_phase := ""
var _snapshot: Dictionary = {}
var _last_status: Dictionary = {}
var _trained_distances: Array[float] = []
var _cleared_distances: Array[float] = []
var _restored_distances: Array[float] = []
var _smoke_mode := false


func _ready() -> void:
	_smoke_mode = OS.get_cmdline_user_args().has("--demo-smoke")
	sim.field_texture_updated.connect(_on_field_texture)
	$UI/InfoPanel/Margin/Rows/Controls/Restart.pressed.connect(_restart_story)
	$UI/InfoPanel/Margin/Rows/Controls/Clear.pressed.connect(_clear_manual)
	$UI/InfoPanel/Margin/Rows/Controls/Restore.pressed.connect(_restore_manual)
	pause_button.pressed.connect(_toggle_pause)
	if sim.field_display_texture != null:
		_on_field_texture(sim.field_display_texture)
	if auto_story:
		call_deferred("_restart_story")
	else:
		stage_label.text = "READY • press Restart story"


func _process(delta: float) -> void:
	var pulse := 1.0 + 0.08 * sin(Time.get_ticks_msec() * 0.004)
	target_marker.scale = Vector3.ONE * pulse
	organ_marker.rotate_y(delta * 0.18)

	if _phase == "HOLD":
		if Time.get_ticks_msec() >= _hold_until_ms:
			_start_phase(_pending_phase)
		return
	if _phase == "BOOT" or _phase == "DONE" or _phase == "MANUAL" or not sim.playing:
		return

	_poll_accum += delta
	if _poll_accum < POLL_SEC:
		return
	_poll_accum = 0.0
	var status: Dictionary = sim.field_intelligence_status()
	if not status.get("ok", false):
		_fail("telemetry: %s" % status.get("error", "unknown"))
		return
	_last_status = status
	probe_marker.position = status.probe
	target_marker.position = status.target
	_update_hud(status)
	if int(status.tick) >= _step_limit:
		_finish_episode(status)


func _restart_story() -> void:
	sim.playing = false
	var cleared: Dictionary = sim.field_intelligence_clear()
	if not cleared.get("ok", false):
		_fail("clear: %s" % cleared.get("error", "unknown"))
		return
	_trained_distances.clear()
	_cleared_distances.clear()
	_restored_distances.clear()
	_snapshot = {}
	_target_index = 0
	verdict_label.text = "The field will learn, lose P/e, then recover it exactly."
	verdict_label.add_theme_color_override("font_color", Color(1.0, 0.72, 0.34))
	pause_button.text = "Pause"
	_start_phase("TRAIN")


func _start_phase(next_phase: String) -> void:
	_phase = next_phase
	if next_phase == "SNAPSHOT":
		sim.playing = false
		_snapshot = sim.field_intelligence_snapshot()
		if not _snapshot.get("ok", false):
			_fail("snapshot: %s" % _snapshot.get("error", "unknown"))
			return
		verdict_label.text = "TRAINED SNAPSHOT  •  %s…" % str(_snapshot.checksum).left(12)
		_target_index = 0
		_hold("TRAINED", 700)
		return
	if next_phase == "CLEAR":
		sim.playing = false
		var result: Dictionary = sim.field_intelligence_clear()
		if not result.get("ok", false):
			_fail("causal clear: %s" % result.get("error", "unknown"))
			return
		verdict_label.text = "P/e CLEARED  •  same body, field, targets, and timing"
		_target_index = 0
		_hold("CLEARED", 900)
		return
	if next_phase == "RESTORE":
		sim.playing = false
		var result: Dictionary = sim.field_intelligence_restore(_snapshot)
		if not result.get("ok", false):
			_fail("restore: %s" % result.get("error", "unknown"))
			return
		verdict_label.text = "P/e RESTORED  •  exact SHA-256 snapshot"
		_target_index = 0
		_hold("RESTORED", 900)
		return
	if next_phase == "DONE":
		_finish_story()
		return
	_begin_episode(next_phase)


func _begin_episode(kind: String) -> void:
	sim.playing = false
	var probe_result: Dictionary = sim.field_intelligence_set_probe_state(Vector3.ZERO)
	if not probe_result.get("ok", false):
		_fail("probe reset: %s" % probe_result.get("error", "unknown"))
		return
	var training := kind == "TRAIN"
	var target_result: Dictionary = sim.field_intelligence_set_target(
			TARGETS[_target_index], TARGET_RADIUS, training)
	if not target_result.get("ok", false):
		_fail("target: %s" % target_result.get("error", "unknown"))
		return
	_phase = kind
	_step_limit = TRAIN_STEPS if training else REPLAY_STEPS
	_poll_accum = POLL_SEC
	target_marker.position = TARGETS[_target_index]
	stage_label.text = _phase_title(kind)
	progress_label.text = "TARGET %d / %d  •  0 / %d FIELD STEPS" % [
		_target_index + 1, TARGETS.size(), _step_limit]
	sim.playing = true
	pause_button.text = "Pause"


func _finish_episode(status: Dictionary) -> void:
	sim.playing = false
	var distance := float(status.distance)
	match _phase:
		"TRAINED": _trained_distances.append(distance)
		"CLEARED": _cleared_distances.append(distance)
		"RESTORED": _restored_distances.append(distance)
	_target_index += 1
	if _target_index < TARGETS.size():
		_hold(_phase)
		return
	match _phase:
		"TRAIN": _hold("SNAPSHOT", 650)
		"TRAINED": _hold("CLEAR", 650)
		"CLEARED": _hold("RESTORE", 650)
		"RESTORED": _hold("DONE", 650)


func _hold(next_phase: String, duration_ms: int = HOLD_MS) -> void:
	_phase = "HOLD"
	_pending_phase = next_phase
	_hold_until_ms = Time.get_ticks_msec() + duration_ms
	progress_label.text = "FIELD BREATH • preparing the next episode"


func _finish_story() -> void:
	sim.playing = false
	_phase = "DONE"
	stage_label.text = "CAUSAL DEMONSTRATION COMPLETE"
	var trained_median := _median(_trained_distances)
	var cleared_median := _median(_cleared_distances)
	var restored_median := _median(_restored_distances)
	var trained_success := _successes(_trained_distances)
	var cleared_success := _successes(_cleared_distances)
	var restored_success := _successes(_restored_distances)
	var recovery_match := _restored_distances.size() == _trained_distances.size()
	if recovery_match:
		for i in _trained_distances.size():
			if absf(_restored_distances[i] - _trained_distances[i]) > 0.20:
				recovery_match = false
				break
	var passed := trained_success >= TARGETS.size() - 1 and cleared_success <= 1 \
			and restored_success >= TARGETS.size() - 1 \
			and trained_median <= 0.5 * cleared_median and recovery_match
	metrics_label.text = "median distance  learned %.3f   cleared %.3f   restored %.3f" % [
		trained_median, cleared_median, restored_median]
	progress_label.text = "successes  learned %d/%d   cleared %d/%d   restored %d/%d" % [
		trained_success, TARGETS.size(), cleared_success, TARGETS.size(),
		restored_success, TARGETS.size()]
	verdict_label.text = ("PASS • P/e is causal: clear removed the behavior; exact restore recovered it."
			if passed else "MISS • the controlled learned/clear/restore comparison did not meet its gate.")
	verdict_label.add_theme_color_override("font_color",
			Color(0.35, 1.0, 0.65) if passed else Color(1.0, 0.42, 0.32))
	pause_button.text = "Paused"
	if _smoke_mode:
		var result := {
			"passed": passed,
			"trained_distances": _trained_distances,
			"cleared_distances": _cleared_distances,
			"restored_distances": _restored_distances,
			"trained_success": trained_success,
			"cleared_success": cleared_success,
			"restored_success": restored_success,
			"trained_median": trained_median,
			"cleared_median": cleared_median,
			"restored_median": restored_median,
			"recovery_match": recovery_match,
			"snapshot_checksum": _snapshot.get("checksum", ""),
		}
		call_deferred("_finish_smoke", passed, result)


func _finish_smoke(passed: bool, result: Dictionary) -> void:
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var screenshot_error := ERR_CANT_CREATE
	if image != null:
		screenshot_error = image.save_png("res://_diag/field_intelligence_demo.png")
	result["screenshot"] = "res://_diag/field_intelligence_demo.png"
	result["screenshot_error"] = screenshot_error
	var file := FileAccess.open("res://_diag/field_intelligence_demo.json", FileAccess.WRITE)
	if file == null:
		push_error("[FieldIntelligenceDemo] could not write smoke receipt")
		get_tree().quit(1)
		return
	file.store_string(JSON.stringify(result, "\t"))
	file.close()
	var smoke_passed := passed and screenshot_error == OK
	print("FIELD_INTELLIGENCE_DEMO %s — learned=%d/%d clear=%d/%d restored=%d/%d" % [
			"PASS" if smoke_passed else "FAIL",
			int(result.trained_success), TARGETS.size(),
			int(result.cleared_success), TARGETS.size(),
			int(result.restored_success), TARGETS.size()])
	get_tree().quit(0 if smoke_passed else 1)


func _update_hud(status: Dictionary) -> void:
	stage_label.text = _phase_title(_phase)
	metrics_label.text = "distance  %.3f     reward  %+.4f     control  %s" % [
		float(status.distance), float(status.reward), _action_name(int(status.action))]
	progress_label.text = "TARGET %d / %d  •  %d / %d FIELD STEPS  •  margin %+.4f" % [
		_target_index + 1, TARGETS.size(), int(status.tick), _step_limit,
		float(status.support_margin)]
	if int(status.faults) != 0:
		verdict_label.text = "FIELD FAULT 0x%X" % int(status.faults)


func _phase_title(kind: String) -> String:
	match kind:
		"TRAIN": return "LEARNING • reward binds motion to six field lobes"
		"TRAINED": return "LEARNED REPLAY • P frozen, exploration off"
		"CLEARED": return "CAUSAL ABLATION • P/e erased"
		"RESTORED": return "RESTORED REPLAY • exact field memory returned"
		_: return kind


func _action_name(action: int) -> String:
	const NAMES := ["+X", "−X", "+Y", "−Y", "+Z", "−Z"]
	return NAMES[clampi(action, 0, 5)]


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


func _on_field_texture(texture: Texture2D) -> void:
	field_view.texture = texture


func _toggle_pause() -> void:
	if _phase == "DONE" or _phase == "BOOT":
		return
	sim.playing = not sim.playing
	pause_button.text = "Pause" if sim.playing else "Resume"


func _clear_manual() -> void:
	auto_story = false
	sim.playing = false
	var result: Dictionary = sim.field_intelligence_clear()
	_phase = "MANUAL"
	stage_label.text = "MANUAL • P/e CLEARED" if result.get("ok", false) else "CLEAR FAILED"
	verdict_label.text = "Press Restart story for the full controlled comparison."
	verdict_label.add_theme_color_override("font_color", Color(1.0, 0.72, 0.34))


func _restore_manual() -> void:
	verdict_label.add_theme_color_override("font_color", Color(1.0, 0.72, 0.34))
	if _snapshot.is_empty():
		verdict_label.text = "No trained snapshot yet."
		return
	auto_story = false
	sim.playing = false
	var result: Dictionary = sim.field_intelligence_restore(_snapshot)
	_phase = "MANUAL"
	stage_label.text = "MANUAL • TRAINED P/e RESTORED" if result.get("ok", false) else "RESTORE FAILED"


func _fail(reason: String) -> void:
	sim.playing = false
	_phase = "DONE"
	stage_label.text = "DEMO STOPPED"
	verdict_label.text = reason
	verdict_label.add_theme_color_override("font_color", Color(1.0, 0.42, 0.32))
	push_error("[FieldIntelligenceDemo] %s" % reason)
