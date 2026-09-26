extends Node
## G83-G85 production rotation publication and read-only renderer verifier.

const N := 64
const BOOT_TIMEOUT_FRAMES := 1800
const ENABLE_TIMEOUT_FRAMES := 1800
const SAMPLE_COUNT := 16
const RECEIPT_PATH := "res://_diag/rotation_observability.json"

var sim: Node3D
var _failures: Array[String] = []
var _gates: Dictionary = {}


func _ready() -> void:
	sim = get_node_or_null("../CassiSim") as Node3D
	if sim == null:
		_fail("scene is missing CassiSim")
		_finish()
		return
	await _run()
	_finish()


func _run() -> void:
	sim.playing = true
	var booted := await _wait_for_boot()
	var disabled_snapshot: Dictionary = sim.rotation_snapshot()
	var disabled_child := sim.get_node_or_null("RotationOrientationAxes")
	var disabled_rid: RID = sim.get("_rotation_axis_rd_rid")
	var disabled_set: RID = sim.get("_us_rotation_axis_0")
	var disabled_shader: RID = sim.get("_rotation_axis_shader")
	var disabled_pipe: RID = sim.get("_rotation_axis_pipe")
	var g83 := booted and not bool(disabled_snapshot.get("enabled", true)) \
			and disabled_child == null and not disabled_rid.is_valid() \
			and not disabled_set.is_valid() and not disabled_shader.is_valid() \
			and not disabled_pipe.is_valid()
	_gates["G83"] = {
		"pass": g83,
		"booted": booted,
		"snapshot": disabled_snapshot,
		"child_absent": disabled_child == null,
		"renderer_rid_valid": disabled_rid.is_valid(),
		"uniform_set_valid": disabled_set.is_valid(),
		"shader_valid": disabled_shader.is_valid(),
		"pipeline_valid": disabled_pipe.is_valid(),
	}
	_check("G83 default-off observability", g83)
	if not booted:
		return

	sim.rotation_stress_enabled = true
	sim.rotation_orientation_render_enabled = true
	sim.rotation_grid_N = 4
	sim.rotation_rungs = 2
	sim.reinit()
	sim.playing = true
	var enabled_ready := await _wait_for_enabled_state()
	var snapshot: Dictionary = sim.rotation_snapshot()
	var telemetry: PackedFloat32Array = snapshot.get("telemetry", PackedFloat32Array())
	var orientations: PackedFloat32Array = snapshot.get(
		"orientation_sample", PackedFloat32Array())
	var finite_unit := orientations.size() == SAMPLE_COUNT * 4
	var max_norm_error := 0.0
	if finite_unit:
		for i in range(SAMPLE_COUNT):
			var q := Quaternion(
				orientations[i * 4], orientations[i * 4 + 1],
				orientations[i * 4 + 2], orientations[i * 4 + 3])
			var norm_error := absf(sqrt(q.x * q.x + q.y * q.y + q.z * q.z + q.w * q.w) - 1.0)
			max_norm_error = maxf(max_norm_error, norm_error)
			finite_unit = finite_unit and q.is_finite() and norm_error <= 1e-5
	var forbidden := [
		"displacement", "momentum", "momentum_next", "spin_heat", "matter",
		"pos", "vel", "buffer", "orientation_buffer", "rid",
	]
	var keys_bounded := true
	for key in forbidden:
		keys_bounded = keys_bounded and not snapshot.has(key)
	var snapshot_bytes := var_to_bytes(snapshot).size()
	var caller_copy: Dictionary = sim.rotation_snapshot()
	caller_copy["enabled"] = false
	var copy_isolated := bool(sim.rotation_snapshot().get("enabled", false))
	var g84 := enabled_ready and bool(snapshot.get("enabled", false)) \
			and int(snapshot.get("telemetry_count", -1)) == 16 \
			and telemetry.size() == 16 \
			and int(snapshot.get("orientation_sample_count", -1)) == SAMPLE_COUNT \
			and finite_unit and keys_bounded and snapshot_bytes < 4096 \
			and copy_isolated
	_gates["G84"] = {
		"pass": g84,
		"enabled_ready": enabled_ready,
		"telemetry_count": telemetry.size(),
		"orientation_sample_count": int(snapshot.get("orientation_sample_count", -1)),
		"max_quaternion_norm_error": max_norm_error,
		"bounded_keys": keys_bounded,
		"serialized_bytes": snapshot_bytes,
		"copy_isolated": copy_isolated,
	}
	_check("G84 bounded production publication", g84)
	if not enabled_ready:
		return

	var layer_ready := await _wait_for_layer()
	var layer := sim.get_node_or_null("RotationOrientationAxes") as MultiMeshInstance3D
	var mm: MultiMesh = layer.multimesh if layer != null else null
	var layer_visible := layer != null and layer.visible
	var renderer_rid: RID = sim.get("_rotation_axis_rd_rid")
	var records := PackedFloat32Array()
	if mm != null and renderer_rid.is_valid():
		records = sim._rd.buffer_get_data(renderer_rid, 0, N * 64).to_float32_array()
	var records_finite := records.size() == N * 16
	var populated := 0
	if records_finite:
		for i in range(N):
			var base := i * 16
			var finite_record := true
			for j in range(16):
				finite_record = finite_record and is_finite(records[base + j])
			var basis_energy := 0.0
			for j in [0, 1, 2, 4, 5, 6, 8, 9, 10]:
				basis_energy += records[base + j] * records[base + j]
			if finite_record and basis_energy > 1e-10 and records[base + 15] > 0.99:
				populated += 1
			records_finite = records_finite and finite_record

	sim.playing = false
	var engine: Object = sim.get("_physics_engine")
	var before: PackedFloat32Array = engine.rotation_publish_state(SAMPLE_COUNT).get(
		"orientation_sample", PackedFloat32Array())
	await get_tree().process_frame
	await get_tree().process_frame
	await get_tree().process_frame
	var after: PackedFloat32Array = engine.rotation_publish_state(SAMPLE_COUNT).get(
		"orientation_sample", PackedFloat32Array())
	var renderer_read_only := before.to_byte_array() == after.to_byte_array()
	await _capture_if_requested()
	await _hold_if_requested()

	sim.rotation_orientation_render_enabled = false
	var cleaned := false
	for _frame in range(120):
		await get_tree().process_frame
		if sim.get_node_or_null("RotationOrientationAxes") == null:
			var freed_rid: RID = sim.get("_rotation_axis_rd_rid")
			var freed_set: RID = sim.get("_us_rotation_axis_0")
			cleaned = not freed_rid.is_valid() and not freed_set.is_valid()
			break
	var rotation_still_enabled := bool(sim.rotation_snapshot().get("enabled", false))
	var g85 := layer_ready and layer_visible and mm != null \
			and mm.instance_count == N and renderer_rid.is_valid() \
			and records_finite and populated > 0 and renderer_read_only \
			and cleaned and rotation_still_enabled
	_gates["G85"] = {
		"pass": g85,
		"layer_ready": layer_ready,
		"layer_visible_before_cleanup": layer_visible,
		"instance_count": mm.instance_count if mm != null else -1,
		"renderer_rid_valid": renderer_rid.is_valid(),
		"record_float_count": records.size(),
		"records_finite": records_finite,
		"populated_records": populated,
		"renderer_read_only": renderer_read_only,
		"cleanup": cleaned,
		"rotation_snapshot_still_enabled": rotation_still_enabled,
	}
	_check("G85 read-only orientation rendering", g85)


func _wait_for_boot() -> bool:
	for _frame in range(BOOT_TIMEOUT_FRAMES):
		await get_tree().process_frame
		if _is_booted():
			return true
	return false


func _wait_for_enabled_state() -> bool:
	for _frame in range(ENABLE_TIMEOUT_FRAMES):
		await get_tree().process_frame
		if _is_booted() and bool(sim.rotation_snapshot().get("enabled", false)):
			return true
	return false


func _wait_for_layer() -> bool:
	for _frame in range(ENABLE_TIMEOUT_FRAMES):
		await get_tree().process_frame
		var layer := sim.get_node_or_null("RotationOrientationAxes") as MultiMeshInstance3D
		var uniform_set: RID = sim.get("_us_rotation_axis_0")
		var rid: RID = sim.get("_rotation_axis_rd_rid")
		if layer != null and layer.visible and uniform_set.is_valid() and rid.is_valid():
			await get_tree().process_frame
			await get_tree().process_frame
			return true
	return false


func _is_booted() -> bool:
	if not bool(sim.get("_decoupled_active")) or bool(sim.get("_decoupled_boot_wait")):
		return false
	if not bool(sim.get("_shaders_ready")):
		return false
	var engine: Object = sim.get("_physics_engine")
	return engine != null and engine.setup_ready()


func _capture_if_requested() -> void:
	if not OS.get_cmdline_user_args().has("--capture-orientation"):
		return
	await RenderingServer.frame_post_draw
	var image := get_viewport().get_texture().get_image()
	var err := image.save_png("res://_diag/rotation_observability_smoke.png")
	_check("orientation surface capture written", err == OK)


func _hold_if_requested() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--hold-orientation="):
			var seconds := clampf(arg.trim_prefix("--hold-orientation=").to_float(), 0.0, 60.0)
			if seconds > 0.0:
				await get_tree().create_timer(seconds).timeout
			return


func _check(label: String, ok: bool) -> void:
	if ok:
		print("[PASS] ", label)
	else:
		_fail(label)


func _fail(label: String) -> void:
	_failures.append(label)
	push_error("[FAIL] " + label)


func _write_receipt() -> void:
	var absolute := ProjectSettings.globalize_path(RECEIPT_PATH)
	DirAccess.make_dir_recursive_absolute(absolute.get_base_dir())
	var receipt := {
		"schema": "cassi.rotation-observability.v1",
		"preregistration": "research/rotation/rotation_observability_prereg.md",
		"gates": _gates,
		"failures": _failures,
		"pass": _failures.is_empty(),
	}
	var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
	if file == null:
		_fail("could not write rotation observability receipt")
		return
	file.store_string(JSON.stringify(receipt, "  ") + "\n")
	file.close()


func _finish() -> void:
	_write_receipt()
	print("G83 %s" % ("PASS" if bool(_gates.get("G83", {}).get("pass", false)) else "FAIL"))
	print("G84 %s" % ("PASS" if bool(_gates.get("G84", {}).get("pass", false)) else "FAIL"))
	print("G85 %s" % ("PASS" if bool(_gates.get("G85", {}).get("pass", false)) else "FAIL"))
	if _failures.is_empty():
		print("ALL CHECKS PASSED")
	get_tree().quit(0 if _failures.is_empty() else 1)
