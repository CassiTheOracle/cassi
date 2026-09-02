extends Node
## G72 — production-engine hierarchical tree-refit stability and invalidation.
## Run windowed: godot --path <repo> res://scenes/verify_tree_hier_refit_engine.tscn

const ENGINE_SCRIPT := "res://scripts/cassi_physics_engine.gd"
const STEPS := 32
const PARTICLES := 512


func _ready() -> void:
	var rd: RenderingDevice = RenderingServer.create_local_rendering_device()
	if rd == null:
		_fail("local RenderingDevice unavailable")
		return
	var engine = load(ENGINE_SCRIPT).new()
	var default_off: bool = not engine.tree_hierarchical_refit
	var cfg := {
		"rd": rd,
		"rd_global": false,
		"owns_rd": true,
		"grid_N": 64,
		"N_particles": PARTICLES,
		"dt": 0.001,
		"cluster_radius": 30.0,
		"cluster_separation": 0.0,
		"num_clusters": 1,
		"box_aspect": Vector3.ONE,
		"meshless_mode": true,
		"meshless_gravity": true,
		"gridless_physics": true,
		"tree_hierarchical_refit": true,
		"tree_cadence": 1,
		"coherence_theta": false,
		"black_holes_enabled": false,
		"particle_merge": false,
		"seed": 72,
	}
	if not engine.setup(cfg):
		engine.shutdown()
		_fail("engine setup failed")
		return

	var initial_generation: int = engine._topology_generation
	var saw_transition := false
	var refits_before_transition := 0
	var fulls_at_transition := 0
	var first_after_transition_full := false
	for _step in range(STEPS):
		var generation_before: int = engine._topology_generation
		engine.run_steps(1, true)
		if engine._topology_generation != generation_before:
			saw_transition = true
			refits_before_transition = engine._tree_hier_refit_count
			fulls_at_transition = engine._tree_full_build_count
		elif saw_transition and not first_after_transition_full:
			first_after_transition_full = (
				engine._tree_full_build_count == fulls_at_transition + 1
				and engine._tree_hier_refit_count == refits_before_transition
			)

	var full_builds: int = engine._tree_full_build_count
	var hierarchical_refits: int = engine._tree_hier_refit_count
	var transition_full_builds: int = engine._tree_transition_full_build_count
	var snapshot: Dictionary = engine.readback_snapshot()
	var positions: PackedFloat32Array = snapshot.get("pos", PackedFloat32Array())
	var velocities: PackedFloat32Array = snapshot.get("vel", PackedFloat32Array())
	var accelerations: PackedFloat32Array = engine._rd.buffer_get_data(
		engine._acc_buf, 0, PARTICLES * 16).to_float32_array()
	var site_yang: PackedFloat32Array = snapshot.get("site_psi_y", PackedFloat32Array())
	var site_yin: PackedFloat32Array = snapshot.get("site_psi_i", PackedFloat32Array())
	# Freeze the end-of-run source state through one explicit refit before
	# comparing it with a full rebuild of that exact same state.
	var hierarchical_cl: int = engine._rd.compute_list_begin()
	engine._tree_run_in_list(hierarchical_cl)
	engine._rd.compute_list_end()
	engine._rd.submit()
	engine._rd.sync()
	var hierarchical_gradients: PackedFloat32Array = engine._rd.buffer_get_data(
		engine._tree_grad, 0, PARTICLES * 16).to_float32_array()

	# Rebuild the same frozen source state through the feature-OFF full path.
	# This checks the production wiring in addition to the isolated G70 probe.
	engine.tree_hierarchical_refit = false
	var cl: int = engine._rd.compute_list_begin()
	engine._tree_run_in_list(cl)
	engine._rd.compute_list_end()
	engine._rd.submit()
	engine._rd.sync()
	var full_gradients: PackedFloat32Array = engine._rd.buffer_get_data(
		engine._tree_grad, 0, PARTICLES * 16).to_float32_array()
	var max_force_relative := 0.0
	var opposite_force_count := 0
	var compared_forces := 0
	for particle in range(PARTICLES):
		var base := particle * 4
		var hierarchical := Vector3(
			hierarchical_gradients[base],
			hierarchical_gradients[base + 1],
			hierarchical_gradients[base + 2])
		var full := Vector3(
			full_gradients[base],
			full_gradients[base + 1],
			full_gradients[base + 2])
		var magnitude := full.length()
		if magnitude <= 1.0e-8:
			continue
		compared_forces += 1
		max_force_relative = maxf(
			max_force_relative, hierarchical.distance_to(full) / magnitude)
		if hierarchical.dot(full) < 0.0:
			opposite_force_count += 1
	var force_parity := (
		compared_forces > 0
		and max_force_relative <= 1.0e-4
		and opposite_force_count == 0
	)
	var finite: bool = (
		_finite(positions)
		and _finite(velocities)
		and _finite(accelerations)
		and _finite(site_yang)
		and _finite(site_yin)
		and _finite(hierarchical_gradients)
		and _finite(full_gradients)
	)
	var result := {
		"default_off": default_off,
		"steps": engine._step_count,
		"initial_generation": initial_generation,
		"final_generation": engine._topology_generation,
		"saw_transition": saw_transition,
		"refits_before_transition": refits_before_transition,
		"first_after_transition_full": first_after_transition_full,
		"full_builds": full_builds,
		"hierarchical_refits": hierarchical_refits,
		"transition_full_builds": transition_full_builds,
		"compared_forces": compared_forces,
		"max_force_relative": max_force_relative,
		"opposite_force_count": opposite_force_count,
		"force_parity": force_parity,
		"finite": finite,
	}
	var passed: bool = (
		default_off
		and engine._step_count >= STEPS
		and saw_transition
		and refits_before_transition > 0
		and first_after_transition_full
		and transition_full_builds > 0
		and force_parity
		and finite
	)
	var file := FileAccess.open("res://_diag/tree_hier_refit_engine_gpu.json", FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(result))
		file.close()
	print("[VerifyTreeHierRefitEngine] G72=", result)
	engine.shutdown()
	if passed:
		print("[VerifyTreeHierRefitEngine] RESULT: PASS")
		get_tree().quit(0)
	else:
		_fail("G72 stability/invalidation gate")


func _finite(values: PackedFloat32Array) -> bool:
	if values.is_empty():
		return false
	for value in values:
		if not is_finite(value):
			return false
	return true


func _fail(reason: String) -> void:
	print("[VerifyTreeHierRefitEngine] RESULT: FAIL — ", reason)
	get_tree().quit(1)
