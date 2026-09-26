extends Node

const EXPECTED_STATE_BYTES := 29 * 29 * 29 * 18 * 4
const EXPECTED_VELOCITY_BYTES := 29 * 29 * 29 * 16 * 4
const REQUIRED_STEPS := 32
const TIMEOUT_MS := 220_000
const SURFACE_HOLD_MS := 8_000

@onready var _sim: Node = $CassiSim
var _started_ms := 0
var _surface_ready_ms := 0
var _failures := 0
var _checked := false


func _ready() -> void:
	_started_ms = Time.get_ticks_msec()
	print("[VerifyFieldParticleIntegration] starting windowed production path")


func _process(_delta: float) -> void:
	var now := Time.get_ticks_msec()
	if now - _started_ms > TIMEOUT_MS:
		_fail("production integration timed out")
		_finish()
		return
	if _checked:
		if now - _surface_ready_ms >= SURFACE_HOLD_MS:
			_finish()
		return
	var engine = _sim.get("_physics_engine")
	if engine == null or not engine.workbench_ready():
		return
	if int(engine.get("_step_count")) < REQUIRED_STEPS:
		return
	_run_contract(engine)
	_checked = true
	_surface_ready_ms = Time.get_ticks_msec()
	print("[VerifyFieldParticleIntegration] surface ready for visual inspection")


func _run_contract(engine: Object) -> void:
	_sim.set("playing", false)
	_check("PI0: shared-RD producer is active", bool(_sim.get("_decoupled_active")))
	_check("PI1: Field Particles is active", engine.field_particles_active())
	_check("PI2: proxy capacity is fixed",
		int(engine.get("N_particles")) == 64,
		"capacity=%d" % int(engine.get("N_particles")))
	var field_engine = engine.get("_field_particle_engine")
	_check("PI3: one canonical field engine exists", field_engine != null)
	var legacy: Dictionary = engine.field_particle_legacy_dispatch_counts()
	_check("PI4: legacy particle dispatches remain zero",
		int(legacy.get("deposit", -1)) == 0
		and int(legacy.get("kdk", -1)) == 0
		and int(legacy.get("accretion", -1)) == 0
		and int(legacy.get("merge", -1)) == 0,
		str(legacy))
	_check("PI4: central merge chain remains unused",
		int(engine.get("_merge_cycles_run")) == 0,
		"cycles=%d" % int(engine.get("_merge_cycles_run")))
	_check("PI4: central tree chain remains unused",
		int(engine.get("_tree_full_build_count")) == 0
		and int(engine.get("_tree_hier_refit_count")) == 0)
	var engine_steps := int(engine.get("_step_count"))
	var field_steps := int(field_engine.step_count()) if field_engine != null else -1
	_check("PI5: simulator and field steps agree",
		engine_steps >= REQUIRED_STEPS and engine_steps == field_steps,
		"engine=%d field=%d" % [engine_steps, field_steps])
	_check("PI5: publish-boundary readout refreshed",
		int(engine.get("_field_particle_publish_count")) >= 2,
		"publishes=%d" % int(engine.get("_field_particle_publish_count")))

	var snapshot: Dictionary = engine.readback_snapshot()
	var catalog: Array = snapshot.get("catalog", [])
	_check("PI6: evolved field resolves to one object",
		catalog.size() == 1, "objects=%d" % catalog.size())
	var state: PackedByteArray = snapshot.get("canonical_state", PackedByteArray())
	var velocity: PackedByteArray = snapshot.get("canonical_velocity", PackedByteArray())
	_check("PI7: snapshot carries complete canonical state",
		state.size() == EXPECTED_STATE_BYTES,
		"bytes=%d" % state.size())
	_check("PI7: snapshot carries complete canonical velocity",
		velocity.size() == EXPECTED_VELOCITY_BYTES,
		"bytes=%d" % velocity.size())
	_check("PI7: snapshot keeps gravity explicitly unmapped",
		str(snapshot.get("gravity_status", "")) == "unmapped")
	_check("PI7: snapshot reports Field Particles",
		bool(snapshot.get("field_particles", false)))

	var positions: PackedFloat32Array = snapshot.get("pos", PackedFloat32Array())
	var proxy_ok := positions.size() == 64 * 4 and catalog.size() == 1
	if proxy_ok:
		var center := Vector3(catalog[0].get("center", Vector3.INF))
		var proxy := Vector3(positions[0], positions[1], positions[2])
		proxy_ok = proxy.distance_to(center) <= 2.0e-5 and positions[3] == 1.0
	_check("PI8: leading render proxy matches the field object", proxy_ok)
	var unused_zero := positions.size() == 64 * 4
	if unused_zero:
		for index in range(1, 64):
			if positions[index * 4 + 3] != 0.0:
				unused_zero = false
				break
	_check("PI8: unused render proxies have zero weight", unused_zero)
	var mmi = _sim.get("_mmi")
	_check("PI9: particle proxy surface is visible",
		mmi != null and bool(mmi.get("visible")))


func _check(label: String, condition: bool, detail := "") -> void:
	if condition:
		print("[VerifyFieldParticleIntegration] PASS ", label,
			" ", detail if not detail.is_empty() else "")
	else:
		_fail(label + (": " + detail if not detail.is_empty() else ""))


func _fail(message: String) -> void:
	_failures += 1
	push_error("[VerifyFieldParticleIntegration] FAIL " + message)


func _finish() -> void:
	if _failures == 0 and _checked:
		print("[VerifyFieldParticleIntegration] RESULT: PASS—FIELD-PARTICLE PRODUCTION INTEGRATION")
		get_tree().quit(0)
	else:
		print("[VerifyFieldParticleIntegration] RESULT: FAIL—FIELD-PARTICLE PRODUCTION INTEGRATION failures=%d" % _failures)
		get_tree().quit(1)
