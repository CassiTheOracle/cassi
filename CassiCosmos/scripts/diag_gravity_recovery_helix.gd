extends Node
## Registered G65 acquisition: three live grid-phase snapshots under Arm R.

const ENGINE_SCRIPT := "res://scripts/cassi_physics_engine.gd"
const GRID_N := 64
const PARTICLES := 512
const FINAL_STEP := 34


func _ready() -> void:
	var rd: RenderingDevice = RenderingServer.create_local_rendering_device()
	if rd == null:
		_fail("local RenderingDevice unavailable")
		return
	var engine = load(ENGINE_SCRIPT).new()
	var cfg := {
		"rd": rd,
		"rd_global": false,
		"owns_rd": true,
		"grid_N": GRID_N,
		"N_particles": PARTICLES,
		"dt": 0.001,
		"seed": 72,
		"num_clusters": 1,
		"cluster_separation": 0.0,
		"cluster_radius": 20.0,
		"box_aspect": Vector3.ONE,
		"field_attractor_init": true,
		"source_strength": 0.0,
		"meshless_mode": true,
		"meshless_gravity": true,
		"gridless_physics": false,
		"tree_hierarchical_refit": true,
		"tree_cadence": 1,
		"black_holes_enabled": false,
		"particle_merge": false,
	}
	if not engine.setup(cfg):
		engine.shutdown()
		_fail("engine setup failed")
		return

	var snapshots: Array[Dictionary] = []
	var field_bytes := GRID_N * GRID_N * GRID_N * 4
	for step in range(1, FINAL_STEP + 1):
		engine.run_steps(1, true)
		if step >= 32:
			snapshots.append({
				"step": step,
				"ey_b64": Marshalls.raw_to_base64(
					engine._rd.buffer_get_data(engine._field_ey, 0, field_bytes)),
				"ei_b64": Marshalls.raw_to_base64(
					engine._rd.buffer_get_data(engine._field_ei, 0, field_bytes)),
			})
	var result := {
		"grid_N": GRID_N,
		"steps": engine._step_count,
		"topology_generation": engine._topology_generation,
		"full_builds": engine._tree_full_build_count,
		"hierarchical_refits": engine._tree_hier_refit_count,
		"transition_full_builds": engine._tree_transition_full_build_count,
		"snapshots": snapshots,
	}
	var acquired: bool = (
		snapshots.size() == 3
		and engine._step_count == FINAL_STEP
		and engine._tree_hier_refit_count > 0
		and engine._tree_transition_full_build_count > 0
	)
	var file := FileAccess.open("res://_diag/gravity_recovery_helix_gpu.json", FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(result))
		file.close()
	print("[GravityRecoveryHelix] steps=", engine._step_count,
		" full=", engine._tree_full_build_count,
		" refit=", engine._tree_hier_refit_count,
		" transition_full=", engine._tree_transition_full_build_count,
		" snapshots=", snapshots.size())
	engine.shutdown()
	if acquired:
		print("[GravityRecoveryHelix] ACQUISITION: PASS")
		get_tree().quit(0)
	else:
		_fail("registered snapshot acquisition")


func _fail(reason: String) -> void:
	print("[GravityRecoveryHelix] ACQUISITION: FAIL — ", reason)
	get_tree().quit(1)
