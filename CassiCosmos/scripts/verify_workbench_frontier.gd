extends Node
## Frozen by research/interactivity/next_frontier_prereg.md. Windowed scene only.

const MAX_WAIT_FRAMES := 180
var _sim: Node3D
var _checks := 0
var _failures := 0

func _ready() -> void:
	print("[WorkbenchFrontier] NF0-NF9 frozen; seed=1729 grid=64 particles=16")
	_check_pure_modules()
	_sim = Node3D.new()
	_sim.name = "WorkbenchFrontierSim"
	_sim.set_script(load("res://scripts/cassi_sim.gd"))
	_sim.playing = false
	_sim.grid_N = 64
	_sim.N_particles = 16
	_sim.dt = 0.001
	_sim.cluster_radius = 8.0
	_sim.box_aspect = Vector3(1.0, 0.75, 1.5)
	_sim.num_clusters = 1
	_sim.cluster_separation = 0.0
	_sim.initial_condition = 2
	_sim.initial_radius_fraction = 0.25
	_sim.source_strength = 0.0
	_sim.black_holes_enabled = false
	_sim.particle_merge = false
	_sim.meshless_mode = false
	_sim.meshless_gravity = false
	_sim.dual_grid = false
	_sim.multi_rung_seed = false
	_sim.tracking_envelope = false
	_sim.home_window_enabled = false
	_sim.ic_seed = 1729
	_sim.suppress_readbacks = true
	_sim.physics_decoupled = false
	add_child(_sim)
	for _i in range(MAX_WAIT_FRAMES):
		await get_tree().process_frame
		if bool(_sim.get("_shaders_ready")) and _sim.get("field_workbench") != null:
			break
	_check("NF0 adapter ready", bool(_sim.get("_shaders_ready")) and _sim.get("field_workbench") != null)
	_run_runtime_gates()
	print("[WorkbenchFrontier] %d checks, %d failures" % [_checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)

func _check_pure_modules() -> void:
	var signature: Dictionary = WorkbenchSignatureScenario.verify_fixture()
	_check("NF8 matched field intensity", bool(signature.get("pass_matched_intensity", false)), str(signature))
	_check("NF8 coherence separates equal intensity", bool(signature.get("pass_coherence_gap", false)), str(signature))
	_check("NF8 aligned disequilibrium lower", bool(signature.get("pass_lower_abs_epsilon_aligned", false)), str(signature))
	_check("NF8 repeat/no-op stable", bool(signature.get("pass_repeat_stable_summary", false)) and bool(signature.get("pass_zero_step_baseline_digest_stable", false)), str(signature))
	var geometry := {"extents": Vector3(4.0, 2.0, 8.0), "window_center": Vector3(11.0, -3.0, 5.0)}
	var recipe := [
		{"kind":"shell", "center":Vector3.ZERO, "scale":0.5, "strength":0.2},
		{"kind":"gaussian_knot", "center":Vector3(0.2,0.0,-0.1), "scale":0.15, "strength":0.1},
		{"kind":"filament", "center":Vector3.ZERO, "scale":0.6, "strength":0.1},
		{"kind":"vortex", "center":Vector3.ZERO, "scale":0.3, "strength":0.1},
		{"kind":"phi_cascade", "center":Vector3.ZERO, "scale":0.5, "strength":0.2, "rungs":3},
	]
	var a: Dictionary = WorkbenchInitialConditions.compile(recipe, geometry)
	var b: Dictionary = WorkbenchInitialConditions.compile(recipe, geometry)
	_check("NF7 composer deterministic", bool(a.get("ok", false)) and a.get("digest") == b.get("digest") and (a.get("commands", []) as Array).size() >= 5, str(a))

func _run_runtime_gates() -> void:
	var status: Dictionary = _sim.workbench_status()
	_check("NF0 paused inline-grid mutable", bool(status.get("ok", false)) and bool(status.get("mutable", false)), str(status))
	var cursor: Dictionary = _sim.workbench_set_cursor(Vector3(2.0, -1.0, 3.0), "numeric")
	_check("NF2 numeric cursor shared", bool(cursor.get("ok", false)) and (cursor.cursor as Vector3).distance_to(Vector3(2.0,-1.0,3.0)) < 1e-6)
	var arm: Dictionary = _sim.workbench_arm_cursor(true)
	_check("NF2 cursor arm lifecycle", bool(arm.get("ok", false)) and bool(_sim.get("_workbench_cursor_armed")))
	_sim.workbench_arm_cursor(false)

	var baseline: Dictionary = _sim._workbench_read_buffers()
	var baseline_digest := _digest(baseline)
	var zero_align = _sim.workbench_apply({"kind":"align", "center":Vector3.ZERO, "radius":1e9, "strength":0.0})
	var zero_after: Dictionary = _sim._workbench_read_buffers()
	_check("NF3 GPU zero-align identity", bool(zero_align.get("ok", false)) and _digest(zero_after) == baseline_digest, str(zero_align))
	var zero_impulse = _sim.workbench_apply({"kind":"impulse", "center":Vector3.ZERO, "radius":1e9, "impulse":Vector3.ZERO})
	var zero_impulse_after: Dictionary = _sim._workbench_read_buffers()
	_check("NF3 GPU zero-impulse identity", bool(zero_impulse.get("ok", false)) and _digest(zero_impulse_after) == baseline_digest, str(zero_impulse))

	var aligned = _sim.workbench_apply({"kind":"align", "center":Vector3.ZERO, "radius":1e9, "strength":1.0})
	var aligned_buffers: Dictionary = _sim._workbench_read_buffers()
	var magnitude_ok := true
	for id in range(baseline.ey.size()):
		var m0 := Vector2(baseline.ey[id], baseline.ei[id]).length()
		var m1 := Vector2(aligned_buffers.ey[id], aligned_buffers.ei[id]).length()
		if absf(m0 - m1) > 2e-6:
			magnitude_ok = false
			break
	_check("NF4 GPU align preserves magnitude", bool(aligned.get("ok", false)) and magnitude_ok, str(aligned))

	_sim._workbench_write_buffers(baseline)
	var impulse := Vector3(0.25, -0.5, 0.75)
	var impulse_result = _sim.workbench_apply({"kind":"impulse", "center":Vector3.ZERO, "radius":1e9, "impulse":impulse})
	var impulse_after: Dictionary = _sim._workbench_read_buffers()
	var impulse_ok := true
	for p in range(baseline.pos.size() / 4):
		if baseline.pos[p*4+3] <= 0.0: continue
		var before := Vector3(baseline.pvel[p*4], baseline.pvel[p*4+1], baseline.pvel[p*4+2])
		var after := Vector3(impulse_after.pvel[p*4], impulse_after.pvel[p*4+1], impulse_after.pvel[p*4+2])
		if after.distance_to(before + impulse) > 2e-6:
			impulse_ok = false
			break
	_check("NF4 GPU impulse parity", bool(impulse_result.get("ok", false)) and impulse_ok, str(impulse_result))

	_sim._workbench_write_buffers(baseline)
	var cp: Dictionary = _sim.workbench_capture_checkpoint()
	var changed = _sim.workbench_apply({"kind":"deposit", "center":Vector3.ZERO, "radius":1e9, "strength":0.25})
	var restored: Dictionary = _sim.workbench_restore_checkpoint()
	_check("NF5 checkpoint exact restore", bool(cp.get("ok", false)) and bool(changed.get("ok", false)) and bool(restored.get("ok", false)) and _digest(_sim._workbench_read_buffers()) == baseline_digest, "cp=%s restored=%s" % [cp, restored])
	var noop: Dictionary = _sim.workbench_run_branch("noop", [], 0)
	var branch: Dictionary = _sim.workbench_run_branch("deposit", [{"kind":"deposit", "center":Vector3.ZERO, "radius":1e9, "strength":0.2}], 0)
	_check("NF6 no-op sibling exact", bool(noop.get("ok", false)) and str(noop.get("digest")) == baseline_digest, str(noop))
	_check("NF6 branch difference reported", bool(branch.get("ok", false)) and branch.get("digest") != baseline_digest and (branch.get("difference", {}) as Dictionary).has("delta"), str(branch))

	_sim.workbench_resume()
	var rejected: Dictionary = _sim.workbench_apply({"kind":"deposit", "center":Vector3.ZERO, "radius":1.0, "strength":0.1})
	_sim.workbench_pause()
	_check("NF0 playing rejects mutation", rejected is Dictionary and not bool(rejected.get("ok", false)), str(rejected))
	var old_boxless: bool = _sim.boxless_field
	var old_meshless: bool = _sim.meshless_mode
	_sim.meshless_mode = true
	_sim.boxless_field = true
	var boxless: Dictionary = _sim.workbench_status()
	_sim.meshless_mode = old_meshless
	_sim.boxless_field = old_boxless
	_check("NF0 boxless ownership rejects", not bool(boxless.get("ok", false)) and str(boxless.get("error", "")).contains("boxless"), str(boxless))

func _digest(buffers: Dictionary) -> String:
	var ctx := HashingContext.new()
	ctx.start(HashingContext.HASH_SHA256)
	for key in ["ey", "ei", "q", "vel", "pos", "pvel"]:
		ctx.update((buffers[key] as PackedFloat32Array).to_byte_array())
	ctx.update(str(buffers.grid_N).to_utf8_buffer())
	ctx.update(str(buffers.extents).to_utf8_buffer())
	ctx.update(str(buffers.window_center).to_utf8_buffer())
	return ctx.finish().hex_encode()

func _check(label: String, passed: bool, detail := "") -> void:
	_checks += 1
	if passed:
		print("PASS %s%s" % [label, (" — " + detail) if not detail.is_empty() else ""])
	else:
		_failures += 1
		print("FAIL %s%s" % [label, (" — " + detail) if not detail.is_empty() else ""])
