extends Node
## Windowed acceptance arm for the bounded supplied-material radiation engine.

const MATERIAL = preload("res://scripts/cassi_radiative_material.gd")
const ENGINE = preload("res://scripts/cassi_radiation_engine.gd")
const PHYSICS_ENGINE = preload("res://scripts/cassi_physics_engine.gd")
const FIXTURE_PATH: String = \
		"res://research/presentation/reference/coupled_radiation_reference.json"
const FIXTURE_FILE_SHA256: String = \
		"bf0b363c941cb2e303d4e11834f90a32035c4656b7a5426f349bcd42221e8ed4"

var _checks: int = 0
var _failures: int = 0
var _fixture: Dictionary = {}
var _rd: RenderingDevice = null


func _ready() -> void:
	get_window().size = Vector2i(640, 360)
	call_deferred("_run")


func _run() -> void:
	if not _check_provider_contract():
		_finish()
		return
	_rd = RenderingServer.create_local_rendering_device()
	_check("CR-G0 local RenderingDevice is available", _rd != null)
	if _rd == null:
		_finish()
		return
	_check_initial_publication()
	_check_null_path()
	_check_affine_work()
	_check_frequency_transport()
	_check_thermal_exchange()
	_check_batch_and_commit_identity()
	_check_checkpoint_lifecycle()
	_check_parent_engine_integration()
	_rd.free()
	_rd = null
	_finish()


func _check_provider_contract() -> bool:
	var loaded: Dictionary = MATERIAL.load_coupled_file(FIXTURE_PATH, FIXTURE_FILE_SHA256)
	_check("CR-G0 hash-bound supplied model loads", bool(loaded.get("ok", false)))
	if not bool(loaded.get("ok", false)):
		return false
	_fixture = (loaded.bundle as Dictionary).duplicate(true)
	_check("CR-G0 missing file identity rejects",
			not bool(MATERIAL.load_coupled_file(FIXTURE_PATH, "").get("ok", false)))
	_check("CR-G0 mismatched file identity rejects",
			not bool(MATERIAL.load_coupled_file(FIXTURE_PATH, "0".repeat(64)).get("ok", false)))
	var malformed: Dictionary = _fixture.duplicate(true)
	malformed.model.unit_map.energy_J_per_sim *= 2.0
	_check("CR-G0 inconsistent derived energy unit rejects",
			not bool(MATERIAL.validate_coupled_bundle(malformed).get("ok", false)))
	malformed = _fixture.duplicate(true)
	malformed.model.spectral_grid.frequency_edges_Hz[3] = \
			malformed.model.spectral_grid.frequency_edges_Hz[2]
	_check("CR-G0 unordered frequency edge rejects",
			not bool(MATERIAL.validate_coupled_bundle(malformed).get("ok", false)))
	malformed = _fixture.duplicate(true)
	malformed.model.material.coefficients.absorption_m_inv[0] = -1.0
	_check("CR-G0 negative opacity rejects",
			not bool(MATERIAL.validate_coupled_bundle(malformed).get("ok", false)))
	malformed = _fixture.duplicate(true)
	malformed.model.material.initial_state.temperature_K = 100.0
	_check("CR-G0 out-of-domain initial temperature rejects",
			not bool(MATERIAL.validate_coupled_bundle(malformed).get("ok", false)))
	var inactive: RefCounted = ENGINE.new()
	var inactive_status: Dictionary = inactive.call("resource_status")
	_check("CR-G0 disabled engine owns no GPU resources",
			not bool(inactive_status.ready) and int(inactive_status.buffer_count) == 0)
	var bypass: RefCounted = ENGINE.new()
	_check("CR-G0 direct runtime bundle bypass rejects", not bool(bypass.call("prepare", {
		"bundle": _fixture, "file_sha256": FIXTURE_FILE_SHA256, "element_count": 1,
	})))
	_check("CR-G0 bypass rejection owns no GPU resources",
			int((bypass.call("resource_status") as Dictionary).buffer_count) == 0)
	return true


func _check_initial_publication() -> void:
	var engine: RefCounted = _make_engine("null", 3)
	if engine == null:
		return
	var state: Dictionary = engine.call("read_state")
	var initial: Dictionary = _fixture.controls["null"].initial_state
	var cv: float = float(_fixture.model.material.eos.specific_heat_J_kg_K)
	var expected_temperature: float = float(initial.internal_energy_J) / (float(initial.mass_kg) * cv)
	_check("CR-G1 initial state readback is valid", bool(state.get("ready", false)))
	var material: PackedFloat32Array = state.material
	var radiation: PackedFloat32Array = state.radiation_energy_J
	var broadcast_ok := true
	for element: int in 3:
		var base: int = element * 4
		broadcast_ok = broadcast_ok and _near(material[base], float(initial.mass_kg), 2.0e-6) \
				and _near(material[base + 1], float(initial.internal_energy_J), 2.0e-6) \
				and _near(material[base + 2], float(initial.volume_m3), 2.0e-6) \
				and _near(state.temperature_K[element], expected_temperature, 2.0e-6)
		for group: int in int(_fixture.model.spectral_grid.group_count):
			broadcast_ok = broadcast_ok and _near(
				radiation[element * int(_fixture.model.spectral_grid.group_count) + group],
				float(initial.radiation_energy_J[group]), 2.0e-6, 1.0e-12)
	_check("CR-G1 extensive state broadcasts without reinterpretation", broadcast_ok)
	var publication: Dictionary = engine.call("publication")
	_check("CR-G1 publication carries immutable identities",
			bool(publication.ready)
			and String(publication.model_sha256) == String(_fixture.model.model_sha256)
			and String(publication.unit_map_sha256) == String(_fixture.model.unit_map.unit_map_sha256)
			and String(publication.group_layout_sha256) \
					== String(_fixture.model.spectral_grid.group_layout_sha256)
			and int(publication.accepted_step) == 0 and int(publication.state_epoch) == 1)
	engine.call("shutdown")


func _check_null_path() -> void:
	var engine: RefCounted = _make_engine("null")
	if engine == null:
		return
	var before: Dictionary = engine.call("checkpoint")
	var control: Dictionary = _fixture.controls["null"]
	_check("CR-G2 null steps execute", bool(engine.call(
			"run_accepted_steps", int(control.steps), float(control.dt_s))))
	var after: Dictionary = engine.call("checkpoint")
	_check("CR-G2 null material/radiation bytes are exact",
			_checkpoint_payload_equal(before, after))
	_check("CR-G2 only accepted identity advances",
			int(after.accepted_step) == int(control.steps)
			and int(after.state_epoch) == 1 + int(control.steps))
	engine.call("shutdown")


func _check_affine_work() -> void:
	for name: String in ["affine_expansion", "affine_compression"]:
		var engine: RefCounted = _make_engine(name)
		if engine == null:
			continue
		var control: Dictionary = _fixture.controls[name]
		var initial_state: Dictionary = engine.call("read_state")
		var initial_material: PackedFloat32Array = initial_state.material
		_check("CR-G3 %s steps execute" % name, bool(engine.call(
				"run_accepted_steps", int(control.steps), float(control.dt_s))))
		var state: Dictionary = engine.call("read_state")
		var expected: Dictionary = control.expected
		var material: PackedFloat32Array = state.material
		var ok := material[0] == initial_material[0] \
				and _near(material[1], float(expected.internal_energy_J), 3.0e-5) \
				and _near(material[2], float(expected.volume_m3), 3.0e-5) \
				and _near(state.temperature_K[0], float(expected.temperature_K), 3.0e-5) \
				and material[1] > 0.0 and material[2] > 0.0
		_check("CR-G3 %s matches affine reference" % name, ok)
		engine.call("shutdown")


func _check_frequency_transport() -> void:
	for name: String in ["frequency_expansion", "frequency_compression"]:
		var engine: RefCounted = _make_engine(name)
		if engine == null:
			continue
		var control: Dictionary = _fixture.controls[name]
		_check("CR-G4 %s steps execute" % name, bool(engine.call(
				"run_accepted_steps", int(control.steps), float(control.dt_s))))
		var state: Dictionary = engine.call("read_state")
		var expected: Dictionary = control.expected
		var radiation: PackedFloat32Array = state.radiation_energy_J
		var ledger: PackedFloat32Array = state.ledger_J
		var scale: float = maxf(1.0, float(expected.radiation_energy_sum_J))
		var max_error: float = 0.0
		var nonnegative := true
		for group: int in radiation.size():
			max_error = maxf(max_error, _normalized_error(
					radiation[group], float(expected.radiation_energy_J[group]), scale))
			nonnegative = nonnegative and radiation[group] >= 0.0
		for index: int in 3:
			var key: String = [
				"low_frequency_escape_J", "high_frequency_escape_J",
				"radiation_pressure_work_J",
			][index]
			max_error = maxf(max_error,
					_normalized_error(ledger[index], float(expected[key]), scale))
		var sum_energy: float = 0.0
		for value: float in radiation:
			sum_energy += value
		var balance_residual: float = sum_energy \
				- float(control.initial_state.radiation_energy_J.reduce(
					func(accum: float, value: Variant) -> float: return accum + float(value), 0.0)) \
				+ ledger[0] + ledger[1] - ledger[2]
		var direction_ok: bool
		if name == "frequency_expansion":
			direction_ok = radiation[5] > 0.0 and ledger[0] >= 0.0
		else:
			direction_ok = radiation[2] > 0.0 and ledger[1] >= 0.0
		_check("CR-G4 %s shared-edge reference and direction" % name,
				max_error <= 4.0e-5 and nonnegative and direction_ok)
		_check("CR-G4 %s telescoping balance closes" % name,
				absf(balance_residual) <= 3.0e-6 * scale)
		engine.call("shutdown")


func _check_thermal_exchange() -> void:
	for name: String in ["hot_matter", "cold_matter", "exact_lte"]:
		var engine: RefCounted = _make_engine(name)
		if engine == null:
			continue
		var control: Dictionary = _fixture.controls[name]
		var initial: Dictionary = control.initial_state
		var initial_total: float = float(initial.internal_energy_J) + _array_sum(initial.radiation_energy_J)
		_check("CR-G5 %s steps execute" % name, bool(engine.call(
				"run_accepted_steps", int(control.steps), float(control.dt_s))))
		var state: Dictionary = engine.call("read_state")
		var expected: Dictionary = control.expected
		var material: PackedFloat32Array = state.material
		var radiation: PackedFloat32Array = state.radiation_energy_J
		var max_error: float = _normalized_error(
				state.temperature_K[0], float(expected.temperature_K), float(expected.temperature_K))
		for group: int in radiation.size():
			max_error = maxf(max_error, _normalized_error(
				radiation[group], float(expected.radiation_energy_J[group]), initial_total))
		var final_total: float = material[1]
		for value: float in radiation:
			final_total += value
		var transferred: float = absf(material[1] - float(initial.internal_energy_J))
		var conservation_limit: float = maxf(1.0e-7, 3.0e-6 * transferred)
		var direction_ok := true
		if name == "hot_matter":
			direction_ok = material[1] < float(initial.internal_energy_J)
		elif name == "cold_matter":
			direction_ok = material[1] > float(initial.internal_energy_J)
		_check("CR-G5 %s matches implicit reference" % name,
				max_error <= 5.0e-5 and direction_ok)
		_check("CR-G5 %s paired energy closes" % name,
				absf(final_total - initial_total) <= conservation_limit)
		engine.call("shutdown")


func _check_batch_and_commit_identity() -> void:
	var batched: RefCounted = _make_engine("hot_matter")
	var split: RefCounted = _make_engine("hot_matter")
	if batched == null or split == null:
		if batched != null: batched.call("shutdown")
		if split != null: split.call("shutdown")
		return
	var dt_s: float = float(_fixture.controls.hot_matter.dt_s)
	var compute_list: int = _rd.compute_list_begin()
	var recorded: bool = bool(batched.call("record_accepted_steps", compute_list, 4, dt_s))
	var pending_publication: Dictionary = batched.call("publication")
	_check("CR-G6 recorded work is not prematurely committed",
			recorded and int(batched.call("accepted_step")) == 0
			and not bool(pending_publication.ready) and int(pending_publication.pending_steps) == 4)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	_check("CR-G6 fenced batch commits", bool(batched.call("commit_recorded_steps"))
			and bool(batched.call("validate_status")))
	var split_ok := true
	for _step: int in 4:
		split_ok = split_ok and bool(split.call("run_accepted_steps", 1, dt_s))
	_check("CR-G6 split steps execute", split_ok)
	var batched_checkpoint: Dictionary = batched.call("checkpoint")
	var split_checkpoint: Dictionary = split.call("checkpoint")
	_check("CR-G6 batched and split state is byte-identical",
			_checkpoint_payload_equal(batched_checkpoint, split_checkpoint)
			and int(batched_checkpoint.accepted_step) == int(split_checkpoint.accepted_step))
	batched.call("shutdown")
	split.call("shutdown")


func _check_checkpoint_lifecycle() -> void:
	var continuous: RefCounted = _make_engine("hot_matter")
	var restored: RefCounted = _make_engine("hot_matter")
	if continuous == null or restored == null:
		if continuous != null: continuous.call("shutdown")
		if restored != null: restored.call("shutdown")
		return
	var dt_s: float = float(_fixture.controls.hot_matter.dt_s)
	_check("CR-G7 checkpoint prefix executes", bool(continuous.call("run_accepted_steps", 2, dt_s)))
	var midpoint: Dictionary = continuous.call("checkpoint")
	_check("CR-G7 checkpoint is complete", bool(midpoint.ok)
			and not String(midpoint.material_bytes).is_empty()
			and not String(midpoint.radiation_bytes).is_empty()
			and not String(midpoint.status_bytes).is_empty())
	_check("CR-G7 uninterrupted suffix executes", bool(continuous.call("run_accepted_steps", 2, dt_s)))
	var continuous_end: Dictionary = continuous.call("checkpoint")
	_check("CR-G7 earlier checkpoint restores on an advanced engine",
			bool(continuous.call("restore_checkpoint", midpoint))
			and _checkpoint_state_equal(midpoint, continuous.call("checkpoint")))
	_check("CR-G7 branched suffix executes",
			bool(continuous.call("run_accepted_steps", 2, dt_s)))
	_check("CR-G7 earlier-checkpoint branch is byte-identical",
			_checkpoint_state_equal(continuous_end, continuous.call("checkpoint")))
	_check("CR-G7 identical checkpoint restores", bool(restored.call("restore_checkpoint", midpoint)))
	_check("CR-G7 restored suffix executes", bool(restored.call("run_accepted_steps", 2, dt_s)))
	var restored_end: Dictionary = restored.call("checkpoint")
	_check("CR-G7 restore continuation is byte-identical",
			_checkpoint_payload_equal(continuous_end, restored_end)
			and int(continuous_end.accepted_step) == int(restored_end.accepted_step)
			and int(continuous_end.state_epoch) == int(restored_end.state_epoch))
	var before_reject: Dictionary = restored.call("checkpoint")
	var incompatible: Dictionary = before_reject.duplicate(true)
	incompatible.model_sha256 = "0".repeat(64)
	_check("CR-G7 incompatible checkpoint rejects without disabling engine",
			not bool(restored.call("restore_checkpoint", incompatible))
			and bool(restored.call("is_ready"))
			and not String(restored.call("last_checkpoint_error")).is_empty())
	var after_reject: Dictionary = restored.call("checkpoint")
	_check("CR-G7 rejected restore leaves state unchanged",
			_checkpoint_state_equal(before_reject, after_reject))
	var corruptions: Array[Dictionary] = [
		{
			"label": "nonfinite material",
			"value": _checkpoint_with_float(before_reject, "material_bytes", 1, NAN),
		},
		{
			"label": "out-of-domain material temperature",
			"value": _checkpoint_with_float(before_reject, "material_bytes", 1, 3.0e38),
		},
		{
			"label": "nonfinite expansion",
			"value": _checkpoint_with_float(before_reject, "expansion_bytes", 0, INF),
		},
		{
			"label": "negative radiation",
			"value": _checkpoint_with_float(before_reject, "radiation_bytes", 0, -1.0),
		},
		{
			"label": "negative escape ledger",
			"value": _checkpoint_with_float(before_reject, "ledger_bytes", 0, -1.0),
		},
		{
			"label": "nonfinite work ledger",
			"value": _checkpoint_with_float(before_reject, "ledger_bytes", 2, NAN),
		},
		{
			"label": "nonzero status",
			"value": _checkpoint_with_int(before_reject, "status_bytes", 0, 1),
		},
		{
			"label": "fractional accepted-step counter",
			"value": _checkpoint_with_fractional_counter(
					before_reject, "accepted_step"),
		},
		{
			"label": "fractional state-epoch counter",
			"value": _checkpoint_with_fractional_counter(
					before_reject, "state_epoch"),
		},
		{
			"label": "fractional reset-epoch counter",
			"value": _checkpoint_with_fractional_counter(
					before_reject, "reset_epoch"),
		},
	]
	for corruption: Dictionary in corruptions:
		var rejected: bool = not bool(restored.call(
				"restore_checkpoint", corruption.value))
		var after_corruption: Dictionary = restored.call("checkpoint")
		_check("CR-G7 %s rejects without mutation" % String(corruption.label),
				rejected and bool(restored.call("is_ready"))
				and not String(restored.call("last_checkpoint_error")).is_empty()
				and _checkpoint_state_equal(before_reject, after_corruption))
	continuous.call("shutdown")
	restored.call("shutdown")
	var control: Dictionary = _fixture.controls.hot_matter
	var reused_prepared: bool = bool(restored.call("prepare", {
		"bundle": _fixture,
		"verification_only": true,
		"file_sha256": FIXTURE_FILE_SHA256,
		"element_count": 1,
		"initial_state": control.initial_state,
		"affine_enabled": bool(control.affine_enabled),
		"frequency_enabled": bool(control.frequency_enabled),
		"source_enabled": bool(control.source_enabled),
	}))
	var reused_initialized: bool = reused_prepared \
			and bool(restored.call("initialize", _rd, false))
	_check("CR-G7 shutdown engine re-prepares and initializes", reused_initialized)
	if reused_initialized:
		var reused_initial: Dictionary = restored.call("checkpoint")
		var fresh: RefCounted = _make_engine("hot_matter")
		if fresh != null:
			var fresh_initial: Dictionary = fresh.call("checkpoint")
			_check("CR-G7 reused engine starts with fresh state and identities",
					_checkpoint_state_equal(reused_initial, fresh_initial)
					and int(reused_initial.accepted_step) == 0
					and int(reused_initial.state_epoch) == 1
					and int(reused_initial.reset_epoch) == 1
					and float(reused_initial.physical_time_s) == 0.0)
			fresh.call("shutdown")
	restored.call("shutdown")


## CR-G8: compose the supplied-material solver into the real local-RD physics
## scheduler.  The matched disabled/enabled engines share every core setting
## and seed; only the optional radiation component differs.
func _check_parent_engine_integration() -> void:
	var disabled: RefCounted = _make_parent_engine(false)
	if disabled == null:
		return
	var disabled_publication: Dictionary = disabled.call(
			"physical_radiation_publication")
	var disabled_resources: Dictionary = disabled.call(
			"physical_radiation_resource_status")
	_check("CR-G8 default-off publication stays inactive",
			not bool(disabled_publication.enabled)
			and not bool(disabled_publication.ready)
			and int(disabled_publication.accepted_step) == 0)
	_check("CR-G8 default-off engine owns no radiation resources",
			not bool(disabled_resources.ready)
			and int(disabled_resources.buffer_count) == 0)
	disabled.call("run_steps", 4, true)
	var disabled_core: Dictionary = disabled.call("readback_snapshot")
	disabled.call("shutdown")

	var enabled: RefCounted = _make_parent_engine(true)
	if enabled == null:
		return
	var initial_publication: Dictionary = enabled.call(
			"physical_radiation_publication", true)
	var initial_state: Dictionary = initial_publication.get("state", {})
	_check("CR-G8 parent initializes hash-bound radiation state",
			bool(initial_publication.ready)
			and bool(initial_publication.enabled)
			and int(initial_publication.accepted_step) == 0
			and bool(initial_state.get("ready", false)))
	var live_resources: Dictionary = enabled.call(
			"physical_radiation_resource_status")
	_check("CR-G8 parent owns complete radiation GPU bundle",
			bool(live_resources.ready)
			and int(live_resources.buffer_count) == 10
			and bool(live_resources.shader)
			and bool(live_resources.pipeline)
			and bool(live_resources.uniform_set))
	enabled.call("run_steps", 4, true)
	var enabled_core: Dictionary = enabled.call("readback_snapshot")
	var after_four: Dictionary = enabled.call(
			"physical_radiation_publication", true)
	var after_state: Dictionary = after_four.get("state", {})
	var expected_time_s: float = 4.0 * 0.01 \
			* float(_fixture.model.unit_map.time_s_per_physics_sim)
	_check("CR-G8 accepted parent cadence commits radiation identity",
			bool(after_four.ready)
			and int(after_four.accepted_step) == 4
			and int(after_four.state_epoch) == 5
			and int(after_four.pending_steps) == 0
			and _near(float(after_four.physical_time_s),
					expected_time_s, 2.0e-6, 1.0e-12))
	_check("CR-G8 accepted parent steps publish finite physical state",
			bool(after_state.get("ready", false))
			and _finite_nonnegative_array(after_state.get(
					"radiation_energy_J", PackedFloat32Array()))
			and float(after_state.get("temperature_K",
					PackedFloat32Array([0.0]))[0]) > 0.0)
	_check("CR-G8 optional radiation leaves the core trajectory bit-identical",
			_core_snapshot_equal(disabled_core, enabled_core))

	var checkpoint: Dictionary = enabled.call(
			"physical_radiation_checkpoint")
	enabled.call("run_steps", 2, true)
	var continuous_end: Dictionary = enabled.call(
			"physical_radiation_checkpoint")
	var restored: bool = bool(enabled.call(
			"restore_physical_radiation_checkpoint", checkpoint))
	enabled.call("run_steps", 2, true)
	var restored_end: Dictionary = enabled.call(
			"physical_radiation_checkpoint")
	_check("CR-G8 parent checkpoint restores deterministic continuation",
			bool(checkpoint.get("ok", false))
			and bool(continuous_end.get("ok", false))
			and restored
			and _checkpoint_payload_equal(continuous_end, restored_end)
			and int(continuous_end.accepted_step) == 6
			and int(restored_end.accepted_step) == 6)
	enabled.call("shutdown")
	var released: Dictionary = enabled.call(
			"physical_radiation_resource_status")
	_check("CR-G8 parent shutdown releases radiation resources",
			int(released.buffer_count) == 0 and not bool(released.ready))

	var rejected: RefCounted = PHYSICS_ENGINE.new()
	var bad_cfg: Dictionary = _parent_engine_cfg(true)
	bad_cfg["physical_radiation_expected_sha256"] = "0".repeat(64)
	var rejected_setup: bool = bool(rejected.call("setup", bad_cfg))
	var rejected_resources: Dictionary = rejected.call(
			"physical_radiation_resource_status")
	_check("CR-G8 parent fails closed on unverified material identity",
			not rejected_setup and int(rejected_resources.buffer_count) == 0)
	rejected.call("shutdown")


func _make_parent_engine(radiation_enabled: bool) -> RefCounted:
	var engine: RefCounted = PHYSICS_ENGINE.new()
	var prepared: bool = bool(engine.call(
			"setup", _parent_engine_cfg(radiation_enabled)))
	_check("CR-G8 parent setup radiation=%s" % radiation_enabled, prepared)
	if not prepared:
		engine.call("shutdown")
		return null
	return engine


func _parent_engine_cfg(radiation_enabled: bool) -> Dictionary:
	var control: Dictionary = _fixture.controls.hot_matter
	return {
		"rd": _rd,
		"rd_global": false,
		"owns_rd": false,
		"seed": 606,
		"grid_N": 64,
		"N_particles": 8,
		"dt": 0.01,
		"cluster_radius": 25.0,
		"cluster_separation": 0.0,
		"box_scale": 2.0,
		"box_aspect": Vector3.ONE,
		"freeze_field": true,
		"gravity_mode": 2,
		"source_strength": 0.0,
		"black_holes_enabled": false,
		"dual_grid": false,
		"meshless_mode": false,
		"meshless_gravity": false,
		"gridless_physics": false,
		"particle_merge": false,
		"bh_accretion": false,
		"initial_radius_fraction": 0.9,
		"physical_radiation_enabled": radiation_enabled,
		"physical_radiation_path": FIXTURE_PATH,
		"physical_radiation_expected_sha256": FIXTURE_FILE_SHA256,
		"physical_radiation_element_count": 1,
		"physical_radiation_initial_state": control.initial_state,
		"physical_radiation_affine_enabled": bool(control.affine_enabled),
		"physical_radiation_frequency_enabled": bool(control.frequency_enabled),
		"physical_radiation_source_enabled": bool(control.source_enabled),
	}


func _core_snapshot_equal(a: Dictionary, b: Dictionary) -> bool:
	if a.is_empty() or b.is_empty():
		return false
	for key: String in ["pos", "vel", "field_q", "pot"]:
		var av: Variant = a.get(key, null)
		var bv: Variant = b.get(key, null)
		if not av is PackedFloat32Array or not bv is PackedFloat32Array:
			return false
		if Marshalls.raw_to_base64((av as PackedFloat32Array).to_byte_array()) \
				!= Marshalls.raw_to_base64(
						(bv as PackedFloat32Array).to_byte_array()):
			return false
	return float(a.get("t", -1.0)) == float(b.get("t", -2.0))


func _finite_nonnegative_array(values: Variant) -> bool:
	if not values is PackedFloat32Array or (values as PackedFloat32Array).is_empty():
		return false
	for value: float in values as PackedFloat32Array:
		if not is_finite(value) or value < 0.0:
			return false
	return true

func _make_engine(control_name: String, element_count: int = 1) -> RefCounted:
	var control: Dictionary = _fixture.controls[control_name]
	var engine: RefCounted = ENGINE.new()
	var prepared: bool = bool(engine.call("prepare", {
		"bundle": _fixture,
		"verification_only": true,
		"file_sha256": FIXTURE_FILE_SHA256,
		"element_count": element_count,
		"initial_state": control.initial_state,
		"affine_enabled": bool(control.affine_enabled),
		"frequency_enabled": bool(control.frequency_enabled),
		"source_enabled": bool(control.source_enabled),
	}))
	_check("%s engine prepares" % control_name, prepared)
	if not prepared:
		print("[COUPLED-RAD] setup error: ", engine.call("last_error"))
		return null
	var initialized: bool = bool(engine.call("initialize", _rd, false))
	_check("%s GPU resources initialize" % control_name, initialized)
	if not initialized:
		print("[COUPLED-RAD] initialize error: ", engine.call("last_error"))
		engine.call("shutdown")
		return null
	return engine


func _checkpoint_payload_equal(a: Dictionary, b: Dictionary) -> bool:
	if not bool(a.get("ok", false)) or not bool(b.get("ok", false)):
		return false
	for key: String in [
		"material_bytes", "expansion_bytes", "radiation_bytes", "ledger_bytes", "status_bytes",
	]:
		if String(a.get(key, "")) != String(b.get(key, "")):
			return false
	return true


func _checkpoint_state_equal(a: Dictionary, b: Dictionary) -> bool:
	if not _checkpoint_payload_equal(a, b):
		return false
	for key: String in [
		"schema_version", "numerical_identity", "model_sha256", "unit_map_sha256",
		"group_layout_sha256", "element_count", "group_count", "accepted_step",
		"state_epoch", "reset_epoch", "physical_time_s",
	]:
		if a.get(key, null) != b.get(key, null):
			return false
	return true


func _checkpoint_with_float(source: Dictionary, key: String,
		index: int, value: float) -> Dictionary:
	var result: Dictionary = source.duplicate(true)
	var bytes: PackedByteArray = Marshalls.base64_to_raw(String(result[key]))
	bytes.encode_float(index * 4, value)
	result[key] = Marshalls.raw_to_base64(bytes)
	return result


func _checkpoint_with_int(source: Dictionary, key: String,
		index: int, value: int) -> Dictionary:
	var result: Dictionary = source.duplicate(true)
	var bytes: PackedByteArray = Marshalls.base64_to_raw(String(result[key]))
	bytes.encode_s32(index * 4, value)
	result[key] = Marshalls.raw_to_base64(bytes)
	return result


func _checkpoint_with_fractional_counter(source: Dictionary,
		key: String) -> Dictionary:
	var result: Dictionary = source.duplicate(true)
	result[key] = float(result[key]) + 0.5
	return result


func _array_sum(values: Array) -> float:
	var result: float = 0.0
	for value: Variant in values:
		result += float(value)
	return result


func _near(actual: float, expected: float, relative: float, absolute: float = 0.0) -> bool:
	return absf(actual - expected) <= maxf(absolute, relative * maxf(absf(expected), 1.0e-30))


func _normalized_error(actual: float, expected: float, scale: float) -> float:
	return absf(actual - expected) / maxf(absf(expected), maxf(1.0e-8 * scale, 1.0e-30))


func _check(label: String, passed: bool) -> void:
	_checks += 1
	if not passed:
		_failures += 1
	print("[COUPLED-RAD] %s: %s" % ["PASS" if passed else "FAIL", label])


func _finish() -> void:
	var passed: bool = _failures == 0
	print("COUPLED RADIATION RESULT: %s (%d/%d checks)" % [
		"PASS" if passed else "FAIL", _checks - _failures, _checks,
	])
	get_tree().quit(0 if passed else 1)
