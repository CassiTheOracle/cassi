extends Node

const EXPECTED_STATE_BYTES := 57 * 57 * 57 * 18 * 4
const EXPECTED_VELOCITY_BYTES := 57 * 57 * 57 * 16 * 4
const REQUIRED_STEPS := 32
const MINIMUM_MOVEMENT := 0.01
const MINIMUM_CHARGE_RETENTION := 0.98
const TIMEOUT_MS := 220_000
const SURFACE_HOLD_MS := 4_000

@onready var _sim: Node = $CassiSim
var _started_ms := 0
var _surface_ready_ms := 0
var _initial_centers: Array[Vector3] = []
var _initial_charge := 0.0
var _motion_started := false
var _checked := false
var _failures := 0


func _ready() -> void:
	_started_ms = Time.get_ticks_msec()
	print("[VerifyFieldParticlesMotion] starting paused production path")


func _process(_delta: float) -> void:
	var now := Time.get_ticks_msec()
	if now - _started_ms > TIMEOUT_MS:
		_fail("production motion verification timed out")
		_finish()
		return
	if _checked:
		if now - _surface_ready_ms >= SURFACE_HOLD_MS:
			_finish()
		return
	var engine = _sim.get("_physics_engine")
	if engine == null or not engine.workbench_ready():
		return
	if not _motion_started:
		_capture_initial_state(engine)
		if _failures > 0:
			_finish()
			return
		_sim.set("playing", true)
		_motion_started = true
		print("[VerifyFieldParticlesMotion] evolving two field particles")
		return
	if int(engine.get("_step_count")) < REQUIRED_STEPS:
		return
	_sim.set("playing", false)
	_run_contract(engine)
	_checked = true
	_surface_ready_ms = Time.get_ticks_msec()
	_sim.set("playing", true)
	print("[VerifyFieldParticlesMotion] surface ready for visual inspection")


func _capture_initial_state(engine: Object) -> void:
	_check("MP0: Field Particles is active", engine.field_particles_active())
	var catalog: Array = engine.field_particle_catalog()
	_check("MP1: initial field resolves to two particles",
		catalog.size() == 2, "objects=%d" % catalog.size())
	if catalog.size() != 2:
		return
	_initial_centers = _ordered_centers(catalog)
	_initial_charge = _catalog_charge(catalog)
	_check("MP1: initial charge is positive", _initial_charge > 0.0,
		"charge=%.9f" % _initial_charge)


func _run_contract(engine: Object) -> void:
	var snapshot: Dictionary = engine.readback_snapshot()
	var catalog: Array = snapshot.get("catalog", [])
	_check("MP2: evolved field still resolves to two particles",
		catalog.size() == 2, "objects=%d" % catalog.size())
	if catalog.size() == 2:
		var final_centers := _ordered_centers(catalog)
		var left_motion := final_centers[0].x - _initial_centers[0].x
		var right_motion := final_centers[1].x - _initial_centers[1].x
		_check("MP3: left particle moves right", left_motion >= MINIMUM_MOVEMENT,
			"dx=%.6f" % left_motion)
		_check("MP3: right particle moves left", right_motion <= -MINIMUM_MOVEMENT,
			"dx=%.6f" % right_motion)
	var final_charge := _catalog_charge(catalog)
	var retention := final_charge / _initial_charge if _initial_charge > 0.0 else 0.0
	_check("MP4: field charge remains", retention >= MINIMUM_CHARGE_RETENTION,
		"retention=%.6f" % retention)

	var field_engine = engine.get("_field_particle_engine")
	var parent_steps := int(engine.get("_step_count"))
	var field_steps := int(field_engine.step_count()) if field_engine != null else -1
	_check("MP5: simulator and field steps agree",
		parent_steps >= REQUIRED_STEPS and parent_steps == field_steps,
		"engine=%d field=%d" % [parent_steps, field_steps])
	var legacy: Dictionary = engine.field_particle_legacy_dispatch_counts()
	_check("MP6: point-particle physics stays off",
		int(legacy.get("deposit", -1)) == 0
		and int(legacy.get("kdk", -1)) == 0
		and int(legacy.get("accretion", -1)) == 0
		and int(legacy.get("merge", -1)) == 0,
		str(legacy))
	_check("MP6: site, tree, rotation, and gravity paths stay off",
		int(engine.get("_merge_cycles_run")) == 0
		and int(engine.get("_tree_full_build_count")) == 0
		and int(engine.get("_tree_hier_refit_count")) == 0
		and not bool(engine.get("gridless_physics"))
		and not bool(engine.get("meshless_mode"))
		and not bool(engine.get("rotation_stress_enabled"))
		and not bool(engine.get("black_holes_enabled")))

	var state: PackedByteArray = snapshot.get("canonical_state", PackedByteArray())
	var velocity: PackedByteArray = snapshot.get("canonical_velocity", PackedByteArray())
	_check("MP7: snapshot carries the complete field state",
		state.size() == EXPECTED_STATE_BYTES, "bytes=%d" % state.size())
	_check("MP7: snapshot carries the complete field velocity",
		velocity.size() == EXPECTED_VELOCITY_BYTES, "bytes=%d" % velocity.size())
	var manifest: Dictionary = snapshot.get("manifest", {})
	_check("MP7: snapshot identifies the moving pair",
		str(manifest.get("schema", "")) == "cassi.field-particles-pair.v1")
	_check("MP7: gravity remains explicitly unmapped",
		str(snapshot.get("gravity_status", "")) == "unmapped")

	var positions: PackedFloat32Array = snapshot.get("pos", PackedFloat32Array())
	var proxies_match := positions.size() == 64 * 4 and catalog.size() == 2
	if proxies_match:
		for index in 2:
			var center := Vector3(catalog[index].get("center", Vector3.INF))
			var base := index * 4
			var proxy := Vector3(positions[base], positions[base + 1], positions[base + 2])
			if proxy.distance_to(center) > 2.0e-5 or positions[base + 3] != 1.0:
				proxies_match = false
				break
	_check("MP8: the first two render particles match the field", proxies_match)
	var unused_zero := positions.size() == 64 * 4
	if unused_zero:
		for index in range(2, 64):
			if positions[index * 4 + 3] != 0.0:
				unused_zero = false
				break
	_check("MP8: unused render particles stay hidden", unused_zero)
	var rendered_pair := false
	var render_detail := "render buffer unavailable"
	var render_device = _sim.get("_rd")
	var render_buffer: RID = _sim.get("_mm_rd_rid")
	if render_device != null and render_buffer.is_valid() and catalog.size() == 2:
		var instances: PackedFloat32Array = render_device.buffer_get_data(
			render_buffer, 0, 2 * 16 * 4).to_float32_array()
		if instances.size() == 32:
			var rendered_centers: Array[Vector3] = [
				Vector3(instances[3], instances[7], instances[11]),
				Vector3(instances[19], instances[23], instances[27]),
			]
			if rendered_centers[0].x > rendered_centers[1].x:
				rendered_centers.reverse()
			var catalog_centers := _ordered_centers(catalog)
			var left_error := rendered_centers[0].distance_to(catalog_centers[0])
			var right_error := rendered_centers[1].distance_to(catalog_centers[1])
			rendered_pair = (
				instances[0] > 0.0
				and instances[16] > 0.0
				and rendered_centers[1].x - rendered_centers[0].x > 6.0
				and left_error <= 0.2
				and right_error <= 0.2
			)
			render_detail = "left=%s right=%s error=(%.6f, %.6f)" % [
				rendered_centers[0], rendered_centers[1], left_error, right_error]
	_check("MP9: both field particles receive separate draw transforms",
		rendered_pair, render_detail)
	var mmi = _sim.get("_mmi")
	_check("MP10: the particle display is visible",
		mmi != null and bool(mmi.get("visible")))


func _ordered_centers(catalog: Array) -> Array[Vector3]:
	var centers: Array[Vector3] = []
	for object in catalog:
		centers.append(Vector3(object.get("center", Vector3.INF)))
	if centers.size() == 2 and centers[0].x > centers[1].x:
		var swap := centers[0]
		centers[0] = centers[1]
		centers[1] = swap
	return centers


func _catalog_charge(catalog: Array) -> float:
	var charge := 0.0
	for object in catalog:
		charge += float(object.get("charge", 0.0))
	return charge


func _check(label: String, condition: bool, detail := "") -> void:
	if condition:
		print("[VerifyFieldParticlesMotion] PASS ", label,
			" ", detail if not detail.is_empty() else "")
	else:
		_fail(label + (": " + detail if not detail.is_empty() else ""))


func _fail(message: String) -> void:
	_failures += 1
	push_error("[VerifyFieldParticlesMotion] FAIL " + message)


func _finish() -> void:
	if _failures == 0 and _checked:
		print("[VerifyFieldParticlesMotion] RESULT: PASS—SEPARATED MOVING FIELD PARTICLES")
		get_tree().quit(0)
	else:
		print("[VerifyFieldParticlesMotion] RESULT: FAIL—SEPARATED MOVING FIELD PARTICLES failures=%d" % _failures)
		get_tree().quit(1)
