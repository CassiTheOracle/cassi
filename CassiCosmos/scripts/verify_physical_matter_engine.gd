extends Node
## Authoritative GPU qualification for the conditional H/H+ material and
## multigroup-radiation engine.  Every threshold is frozen in
## research/presentation/physical_matter_implementation_prereg.md.

const ENGINE = preload("res://scripts/cassi_physical_matter_engine.gd")
const ArmMetrics := preload("res://scripts/physical_matter_arm_metrics.gd")
const MODEL_PATH := "res://research/presentation/reference/cassi_physical_matter_model.json"
const MODEL_SHA256 := "58bbc2095208ccff2c8f8fa6aff0e8961a923f9f0313a85542b53b52bcd864c5"
const RECEIPT_PATH := "res://_diag/physical_matter/engine_verification.json"
const GAMMA := 5.0 / 3.0
## Small linear-response beam for the Beer-Lambert fixture.  The static-medium
## arm disables kinetics and uses this amplitude so absorption cannot materially
## cool the reservoir while the transmitted signal remains representable at
## optical depth 10.
const BEER_BEAM := 1.0e-3
## The exchange probe is considered attempted only above a fixed fraction of
## its injected beam energy; below that, float32 readback is diagnostic but not
## a conservation comparison.  Qualifying cases still gate both paired-energy
## closure and ledger-vs-radiation agreement.
const RADIATIVE_PROBE_MIN_EXCHANGE := BEER_BEAM * 1.0e-11
const G4_PAIRED_ENERGY_TOLERANCE := 3.0e-5
const M_H := 1.6735575e-27
const K_B := 1.380649e-23

var _rd: RenderingDevice
var _model: Dictionary = {}
var _checks: Array[Dictionary] = []
var _failures: int = 0
var _started_usec: int = 0


func _ready() -> void:
	call_deferred("_run")


func _run() -> void:
	_started_usec = Time.get_ticks_usec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_record("PM-G1", "local RenderingDevice is available", false, {})
		_finish()
		return
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(MODEL_PATH))
	if parsed is Dictionary:
		_model = parsed as Dictionary
	else:
		_record("PM-G1", "generated physical model parses", false, {})
		_finish()
		return
	_check_model_identity_and_units()
	_check_conservative_initialization()
	_check_hydrodynamics()
	_check_atomic_emissivity()
	_check_transactional_rejection()
	_check_stationary_transport()
	_check_moving_transport()
	_check_coupled_lifecycle()
	_check_physical_observation()
	_finish()

func _check_transactional_rejection() -> void:
	var high_velocity := _make_uniform_engine(Vector3i(8, 8, 8), Vector3.ONE,
			1.0, 1.0, Vector3(0.1, 0.0, 0.0), {
		"time_s_per_sim": 1.0,
		"reduced_light_fraction": 1.0 / 299792458.0,
		"dt_sim": 0.001,
	})
	if not bool(high_velocity.get("ok", false)):
		_record("PM-G6", "moving-frame rejection fixture initializes", false, {
			"error": high_velocity.get("error", "")})
		return
	var engine: RefCounted = high_velocity.engine
	var before := _physical_state_bytes(engine)
	var material_role_before: bool = bool(engine.get("_material_role_b"))
	var radiation_role_before: bool = bool(engine.get("_radiation_role_b"))
	var accepted_before := int(engine.call("accepted_steps"))
	var physical_time_before := float(engine.call("physical_time_sim"))
	var commands := _rd.compute_list_begin()
	var recorded := bool(engine.call("record_step", commands, 0.001))
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	var committed := bool(engine.call("commit_recorded_steps"))
	var after := _physical_state_bytes(engine)
	var publication: Dictionary = engine.call("publication")
	var status: Dictionary = publication.get("status_values", {})
	var flags := int(status.get("flags", 0))
	var rejected_without_mutation := recorded and not committed \
			and (flags & 131072) != 0 \
			and int(status.get("moving_frame_rejections", 0)) > 0 \
			and before == after \
			and bool(engine.get("_material_role_b")) == material_role_before \
			and bool(engine.get("_radiation_role_b")) == radiation_role_before \
			and int(engine.call("accepted_steps")) == accepted_before \
			and is_equal_approx(float(engine.call("physical_time_sim")), physical_time_before)
	_record("PM-G6", "moving-frame rejection is transactional and byte-identical",
			rejected_without_mutation, {
		"recorded": recorded, "committed": committed, "flags": flags,
		"moving_frame_rejections": int(status.get("moving_frame_rejections", 0)),
		"state_byte_identical": before == after,
		"roles_restored": bool(engine.get("_material_role_b")) == material_role_before
			and bool(engine.get("_radiation_role_b")) == radiation_role_before,
		"accepted_steps": int(engine.call("accepted_steps")),
		"physical_time_sim": float(engine.call("physical_time_sim")),
	})
	_teardown(high_velocity)

	var cfl_fixture := _make_uniform_engine(Vector3i(8, 8, 8), Vector3.ONE,
			1.0, 1.0, Vector3.ZERO, {
		"time_s_per_sim": 1.0,
		"reduced_light_fraction": 1.0 / 299792458.0,
	})
	if not bool(cfl_fixture.get("ok", false)):
		_record("PM-G6", "transport-CFL rejection fixture initializes", false, {
			"error": cfl_fixture.get("error", "")})
		return
	engine = cfl_fixture.engine
	before = _physical_state_bytes(engine)
	material_role_before = bool(engine.get("_material_role_b"))
	radiation_role_before = bool(engine.get("_radiation_role_b"))
	var role_containers := [
		engine.get("_radiation_a") as RID, engine.get("_radiation_b") as RID]
	var role_bytes_before: Array[PackedByteArray] = []
	for rid_value: RID in role_containers:
		role_bytes_before.append(_rd.buffer_get_data(rid_value))
	commands = _rd.compute_list_begin()
	engine.call("_record_transport", commands, 0.5)
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	after = _physical_state_bytes(engine)
	var status_words := _status_ints(engine)
	flags = ArmMetrics.status_flags(status_words)
	var roles_identical := true
	for index in range(role_containers.size()):
		if _rd.buffer_get_data(role_containers[index]) != role_bytes_before[index]:
			roles_identical = false
	var cfl_rejected := (flags & 4096) != 0 and (flags & 131072) != 0 \
			and (int(status_words[ArmMetrics.STATUS_WORD_TRANSPORT_CFL]) & 0xffffffff) > 0 \
			and before == after and roles_identical \
			and bool(engine.get("_material_role_b")) == material_role_before \
			and bool(engine.get("_radiation_role_b")) == radiation_role_before
	_record("PM-G6", "transport CFL rejection leaves both radiation roles untouched",
			cfl_rejected, {
		"flags": flags,
		"transport_cfl_rejections": int(status_words[ArmMetrics.STATUS_WORD_TRANSPORT_CFL]) & 0xffffffff,
		"state_byte_identical": before == after,
		"both_radiation_roles_unchanged": roles_identical,
		"roles_unchanged": bool(engine.get("_material_role_b")) == material_role_before
			and bool(engine.get("_radiation_role_b")) == radiation_role_before,
	})
	_teardown(cfl_fixture)



func _check_stationary_transport() -> void:
	var vacuum := _make_uniform_engine(Vector3i(16, 8, 8), Vector3.ONE,
			1.0e-6, 1.0, Vector3.ZERO, {
		"time_s_per_sim": 1.0,
		"reduced_light_fraction": 0.5 / 299792458.0,
	})
	if not bool(vacuum.get("ok", false)):
		_record("PM-G5", "vacuum transport fixture initializes", false, {
			"error": vacuum.get("error", "")})
		return
	var engine: RefCounted = vacuum.engine
	var publication: Dictionary = engine.call("publication")
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var grid: Vector3i = publication.grid
	var cells := grid.x * grid.y * grid.z
	var radiation := PackedFloat32Array()
	radiation.resize(cells * groups * angles)
	var plus_angle := _nearest_ordinate(engine, Vector3.RIGHT)
	var source_cell := 5 + grid.x * (grid.y / 2 + grid.y * (grid.z / 2))
	var initial_center := _cell_position(
			Vector3i(source_cell % grid.x, (source_cell / grid.x) % grid.y,
			source_cell / (grid.x * grid.y)), grid, Vector3.ONE)
	radiation[_radiation_index(source_cell, 0, plus_angle, groups, angles)] = 1.0
	var state := _state_floats(engine)
	_set_material_state(engine, state[0], state[1], state[2], state[3], radiation)
	var initial_beam_energy := _radiation_energy(engine)
	var dt := 0.04
	var steps := 6
	for _step in range(steps):
		_direct_transport(engine, dt, false)
	var final_center := _radiation_centroid(engine, 0, plus_angle)
	var ordinates := _floats(publication.ordinates)
	var direction := Vector3(ordinates[plus_angle * 4], ordinates[plus_angle * 4 + 1],
			ordinates[plus_angle * 4 + 2])
	var expected_center := initial_center + direction * 0.5 * dt * float(steps)
	var cell_width := 2.0 * Vector3.ONE / Vector3(grid)
	var crossing_error := (final_center - expected_center).length()
	var vacuum_energy_error := _relative_error(
			_radiation_energy(engine), initial_beam_energy)
	_record("PM-G5", "vacuum beam crossing remains within one cell", crossing_error
			<= cell_width.length() and vacuum_energy_error <= 8.0e-5
			and _fatal_status(engine) == 0, {
		"initial_center": _vec(initial_center),
		"expected_center": _vec(expected_center),
		"final_center": _vec(final_center),
		"center_error": crossing_error,
		"cell_width": _vec(cell_width),
		"initial_energy": initial_beam_energy,
		"final_energy": _radiation_energy(engine),
		"relative_energy_error": vacuum_energy_error,
		"fatal_status": _fatal_status(engine),
	})
	_teardown(vacuum)

	var opposed := _make_uniform_engine(Vector3i(12, 8, 8), Vector3.ONE,
			1.0e-6, 1.0, Vector3.ZERO, {
		"time_s_per_sim": 1.0,
		"reduced_light_fraction": 0.5 / 299792458.0,
	})
	if not bool(opposed.get("ok", false)):
		_record("PM-G5", "opposed-beam fixture initializes", false, {
			"error": opposed.get("error", "")})
		return
	engine = opposed.engine
	publication = engine.call("publication")
	groups = int(publication.groups); angles = int(publication.angles)
	grid = publication.grid
	cells = grid.x * grid.y * grid.z
	radiation = PackedFloat32Array(); radiation.resize(cells * groups * angles)
	plus_angle = _nearest_ordinate(engine, Vector3.RIGHT)
	var minus_angle := _nearest_ordinate(engine, Vector3.LEFT)
	var row_cell := 3 + grid.x * (grid.y / 2 + grid.y * (grid.z / 2))
	var opposite_cell := 8 + grid.x * (grid.y / 2 + grid.y * (grid.z / 2))
	radiation[_radiation_index(row_cell, 0, plus_angle, groups, angles)] = 1.0
	radiation[_radiation_index(opposite_cell, 0, minus_angle, groups, angles)] = 1.0
	state = _state_floats(engine)
	_set_material_state(engine, state[0], state[1], state[2], state[3], radiation)
	var initial_opposed_energy := _radiation_energy(engine)
	var initial_plus := _radiation_centroid(engine, 0, plus_angle)
	var initial_minus := _radiation_centroid(engine, 0, minus_angle)
	var initial_plus_energy := _radiation_energy_for(engine, 0, plus_angle)
	var initial_minus_energy := _radiation_energy_for(engine, 0, minus_angle)
	for _step in range(4):
		_direct_transport(engine, 0.02, false)
	var final_opposed_energy := _radiation_energy(engine)
	var final_plus := _radiation_centroid(engine, 0, plus_angle)
	var final_minus := _radiation_centroid(engine, 0, minus_angle)
	var final_plus_energy := _radiation_energy_for(engine, 0, plus_angle)
	var final_minus_energy := _radiation_energy_for(engine, 0, minus_angle)
	var distinct_beams := final_plus_energy > 0.5 * initial_plus_energy \
			and final_minus_energy > 0.5 * initial_minus_energy \
			and final_plus.x > initial_plus.x and final_minus.x < initial_minus.x
	var opposed_energy_error := _relative_error(final_opposed_energy, initial_opposed_energy)
	_record("PM-G5", "opposed beams retain distinct ordinate populations",
			distinct_beams and opposed_energy_error <= 8.0e-5
			and _fatal_status(engine) == 0, {
		"plus_angle": plus_angle, "minus_angle": minus_angle,
		"initial_plus": _vec(initial_plus), "final_plus": _vec(final_plus),
		"initial_minus": _vec(initial_minus), "final_minus": _vec(final_minus),
		"plus_energy": final_plus_energy,
		"minus_energy": final_minus_energy,
		"initial_plus_energy": initial_plus_energy,
		"initial_minus_energy": initial_minus_energy,
		"relative_energy_error": opposed_energy_error,
		"fatal_status": _fatal_status(engine),
	})
	_teardown(opposed)

	var escape_fixture := _make_uniform_engine(Vector3i(8, 8, 8), Vector3.ONE,
			1.0e-6, 1.0, Vector3.ZERO, {
		"time_s_per_sim": 1.0,
		"reduced_light_fraction": 0.5 / 299792458.0,
	})
	if not bool(escape_fixture.get("ok", false)):
		_record("PM-G5", "open-boundary escape fixture initializes", false, {
			"error": escape_fixture.get("error", "")})
		return
	engine = escape_fixture.engine
	publication = engine.call("publication")
	groups = int(publication.groups); angles = int(publication.angles)
	grid = publication.grid
	cells = grid.x * grid.y * grid.z
	radiation = PackedFloat32Array(); radiation.resize(cells * groups * angles)
	plus_angle = _nearest_ordinate(engine, Vector3.RIGHT)
	var edge_cell := (grid.x - 2) + grid.x * (grid.y / 2 + grid.y * (grid.z / 2))
	radiation[_radiation_index(edge_cell, 0, plus_angle, groups, angles)] = 1.0
	state = _state_floats(engine)
	_set_material_state(engine, state[0], state[1], state[2], state[3], radiation)
	var initial_escape_energy := _radiation_energy(engine)
	for _step in range(8):
		_direct_transport(engine, 0.1, true)
	var retained_escape_energy := _radiation_energy(engine)
	var escaped_energy := _ledger_total(engine, "ledger0", 2)
	var escape_closure := _relative_error(retained_escape_energy + escaped_energy,
			initial_escape_energy)
	_record("PM-G5", "escaped radiation plus retained radiation closes",
			escape_closure <= 8.0e-5 and escaped_energy > 0.0
			and _fatal_status(engine) == 0, {
		"initial_energy": initial_escape_energy,
		"retained_energy": retained_escape_energy,
		"escaped_energy": escaped_energy,
		"relative_closure_error": escape_closure,
		"fatal_status": _fatal_status(engine),
	})
	_teardown(escape_fixture)

	var beer_errors: Array[float] = []
	var beer_drifts: Array[float] = []
	var beer_cases: Array[Dictionary] = []
	var beer_cases_ok := true
	for tau in [0.1, 1.0, 10.0]:
		# A cold, fully neutral static medium: kinetics are disabled for this
		# transfer-only fixture, while bound absorption remains active.  The small
		# beam keeps the material energy exchange in the linear-response regime.
		var absorber := _make_settled_hydrogen_engine(2000.0, 1.0e24, 0.0,
				{"source_enabled": false})
		if not bool(absorber.get("ok", false)):
			beer_errors.append(INF)
			beer_cases_ok = false
			beer_cases.append({"tau": tau, "error": absorber.get("error", "")})
			continue
		engine = absorber.engine
		publication = engine.call("publication")
		groups = int(publication.groups); angles = int(publication.angles)
		cells = int(engine.get("_cell_count"))
		# The fixture is settled: its published opacity is the coefficient the
		# source exchange applies, which the drift metric confirms per case.
		var settle_trace: Array[float] = absorber.get("settle_trace", []) as Array[float]
		var opacity := _floats(publication.opacity)
		var absorber_group := _maximum_group(opacity, cells, groups)
		# The exchange evaluates its coefficients from the state at the start of
		# the step.  A zero-duration mode-0 pass does not advance the dt-scaled
		# rate solve (atomic.glsl:295), but it does refresh thermodynamics from the
		# conserved energy, so the following mode-4 publication reports the
		# coefficient the next step applies at that same state — not a pre-solve
		# approximation of it.  The fixture is already settled, so the solve the
		# step then runs moves the state only by the bounded opacity drift below.
		_direct_atomic(engine, 0, 0.0, false)
		_direct_atomic(engine, 4, 0.0, false)
		publication = engine.call("publication")
		opacity = _floats(publication.opacity)
		absorber_group = _maximum_group(opacity, cells, groups)
		var coefficient := opacity[absorber_group]
		var absorber_angle := _nearest_ordinate(engine, Vector3.RIGHT)
		radiation = PackedFloat32Array(); radiation.resize(cells * groups * angles)
		# Beer's law is linear in intensity, so the test beam is injected far below
		# the intensity that would photoionize or photoexcite the column: the
		# medium stays invariant while exp(-tau) is still exact.
		radiation[_radiation_index(0, absorber_group, absorber_angle, groups, angles)] = BEER_BEAM
		state = _state_floats(engine)
		_set_material_state(engine, state[0], state[1], state[2], state[3], radiation)
		var dt_tau := float(tau) / maxf(coefficient
				* float(publication.c_reduced_sim), 1.0e-30)
		# Pre-step budget: the material's total energy channel against the source
		# term the exchange requests, so any drain is attributable.
		var pre_material0 := _floats(publication.material0)
		var pre_material1 := _floats(publication.material1)
		var pre_emission := _floats(publication.emission)
		var pre_source_exchange := _floats(publication.ledger0)[3] \
				if _floats(publication.ledger0).size() > 3 else 0.0
		var pre_kinetic := 0.0
		for cell in range(cells):
			# material0.yzw is momentum density, so the kinetic energy density is
			# 0.5 * |p|^2 / rho, not 0.5 * rho * |p|^2.
			var cell_density := maxf(pre_material0[cell * 4], 1.0e-30)
			var momentum_squared := pre_material0[cell * 4 + 1] * pre_material0[cell * 4 + 1] \
					+ pre_material0[cell * 4 + 2] * pre_material0[cell * 4 + 2] \
					+ pre_material0[cell * 4 + 3] * pre_material0[cell * 4 + 3]
			pre_kinetic = maxf(pre_kinetic, 0.5 * momentum_squared / cell_density)
		_direct_atomic(engine, 6, dt_tau, false)
		publication = engine.call("publication")
		var result_radiation := _floats(publication.radiation)
		var actual_ratio := result_radiation[
				_radiation_index(0, absorber_group, absorber_angle, groups, angles)] / BEER_BEAM
		# Background control: every other ordinate of the same group and cell sees
		# the same medium with no beam in it, so whatever lands there is the
		# medium's own additive source rather than transmitted beam.
		var background := 0.0
		for angle in range(angles):
			if angle == absorber_angle:
				continue
			background = maxf(background, result_radiation[
					_radiation_index(0, absorber_group, angle, groups, angles)])
		var background_ratio := background / BEER_BEAM
		var expected_ratio := exp(-float(tau))
		var transmission_error: float = abs(actual_ratio - expected_ratio) \
				/ maxf(expected_ratio, 1.0e-7)
		var post_opacity := _floats(publication.opacity)
		var post_emission := _floats(publication.emission)
		var post_material1 := _floats(publication.material1)
		var post_population0 := _floats(publication.population0)
		var post_population1 := _floats(publication.population1)
		var status_after := _status_ints(engine)
		var opacity_drift: float = absf(post_opacity[absorber_group] - coefficient) \
				/ maxf(coefficient, 1.0e-30)
		# A numerically matching ratio is not a pass on its own: a latched kinetics
		# failure (or a non-finite coefficient/state) must fail the case, otherwise
		# the ratio can go green against a corrupt column.
		var case_ok := is_finite(actual_ratio) and _fatal_status(engine) == 0 \
				and _finite_material_state(_floats(publication.material0)) \
				and _finite_nonnegative(post_opacity) \
				and _finite_nonnegative(post_emission) \
				and _finite_nonnegative(post_material1) \
				and _finite_nonnegative(post_population0) \
				and _finite_nonnegative(post_population1)
		beer_cases_ok = beer_cases_ok and case_ok
		beer_drifts.append(opacity_drift)
		beer_errors.append(transmission_error)
		var post_ledger0 := _floats(publication.ledger0)
		beer_cases.append({
			"case_ok": case_ok,
			"pre_energy_density": pre_material1[0],
			"pre_kinetic_density": pre_kinetic,
			"pre_emission_maximum": _maximum_value(pre_emission),
			"pre_source_exchange": pre_source_exchange,
			"post_source_exchange": post_ledger0[3] if post_ledger0.size() > 3 else 0.0,
			"post_energy_density": post_material1[0],
			"tau": tau, "group": absorber_group, "opacity": coefficient,
			"settle_trace": settle_trace,
			"opacity_drift": opacity_drift,
			"post_opacity": post_opacity[absorber_group],
			"post_emission": post_emission[absorber_group],
			"dt_sim": dt_tau, "actual_transmission": actual_ratio,
			"background_transmission": background_ratio,
			"expected_transmission": expected_ratio, "relative_error": transmission_error,
			"post_temperature": post_material1[1],
			"post_pressure": post_material1[2],
			"post_total_energy": post_material1[0],
			"post_population_sum": post_population0[0] + post_population0[1]
				+ post_population0[2] + post_population0[3]
				+ post_population1[0] + post_population1[1] + post_population1[2],
			"status_flags": ArmMetrics.status_flags(status_after),
			"kinetics_failures": int(status_after[ArmMetrics.STATUS_WORD_KINETICS_FAILURES]) & 0xffffffff,
			"maximum_pre_source_v_over_c": _status_max_v_over_c(engine),
			"fatal_status": _fatal_status(engine),
		})
		_teardown(absorber)
	var beer_max := 0.0
	for error in beer_errors:
		beer_max = maxf(beer_max, error)
	var beer_drift_max := 0.0
	for drift in beer_drifts:
		beer_drift_max = maxf(beer_drift_max, drift)
	_record("PM-G5", "homogeneous Beer-Lambert absorption matches exp(-tau)",
			beer_max <= 1.5e-2 and not beer_errors.has(INF)
			and beer_drift_max <= 5.0e-2 and beer_cases_ok, {
		"maximum_relative_error": beer_max,
		"maximum_opacity_drift": beer_drift_max,
		"cases_valid": beer_cases_ok,
		"cases": beer_cases,
	})

	var slab := _make_ionized_hydrogen_engine(12000.0, 1.0e21, 0.5)
	if not bool(slab.get("ok", false)):
		_record("PM-G5", "homogeneous emitting slab fixture initializes", false, {
			"error": slab.get("error", "")})
		return
	engine = slab.engine
	_direct_atomic(engine, 4, 0.0, false)
	publication = engine.call("publication")
	var slab_opacity := _floats(publication.opacity)
	var slab_emission := _floats(publication.emission)
	# This fixture starts from a directly packed partially ionized state, so the
	# publication below proves the live emissivity and absorptive source paths.
	# Freeze populations only for the transfer step through the engine's explicit
	# source control; PM-G4 and PM-G7 retain the coupled kinetics path.
	var slab_source_enabled := bool(publication.source_enabled)
	var slab_pre_emission := _maximum_value(slab_emission)
	var slab_pre_state := _state_floats(engine)
	var slab_pre_ion: float = slab_pre_state[3][2] \
			/ maxf(slab_pre_state[2][0] + slab_pre_state[3][2], 1.0e-30)
	_record("PM-G5", "emitting slab fixture publishes a non-trivial source",
			slab_pre_emission > 0.0 and slab_source_enabled, {
		"pre_step_maximum_emission": slab_pre_emission,
		"pre_step_maximum_opacity": _maximum_value(slab_opacity),
		"pre_step_ion_fraction": slab_pre_ion,
		"source_enabled": slab_source_enabled,
		"settle_trace": slab.get("settle_trace", []),
		"population_trace": slab.get("population_trace", []),
	})

	groups = int(publication.groups); angles = int(publication.angles)
	cells = int(engine.get("_cell_count"))
	# Group, opacity, emission, absorption, and dt come from this one
	# zero-radiation publication.  Thomson scattering is proportional to the
	# free-electron fraction, not the total hydrogen density.
	var slab_group := _maximum_group(slab_emission, cells, groups)
	var slab_total_opacity := slab_opacity[slab_group]
	var slab_scattering := slab_pre_ion * float(publication.density_kg_m3_per_sim) / M_H \
			* float((_model.get("constants", {}) as Dictionary).get("sigma_T_m2", 0.0)) \
			* float(publication.length_m_per_sim)
	var slab_absorption := maxf(slab_total_opacity - slab_scattering, 0.0)
	var slab_dt := 1.0 / maxf(float(publication.c_reduced_sim)
			* slab_absorption, 1.0e-30)
	radiation = PackedFloat32Array()
	radiation.resize(cells * groups * angles)
	state = _state_floats(engine)
	_set_material_state(engine, state[0], state[1], state[2], state[3], radiation)
	var slab_scale_oracle := _slab_transfer_scale_oracle(engine, publication,
			state, slab_opacity, slab_emission, slab_scattering, slab_dt)
	var slab_emission_scale := float(slab_scale_oracle.get("emission_scale", 0.0))
	var slab_lambda_expected_unity := bool(
			slab_scale_oracle.get("lambda_expected_unity", false))
	var slab_input_radiation_max := _maximum_value(radiation)
	
	var transfer_population0 := state[2]
	var transfer_population1 := state[3]
	var before_material := _material_energy(engine)
	# Mode 6 performs the same source exchange without the time-dependent
	# population solve, making the transfer-only contract explicit while the
	# fixture remains source-enabled.
	_direct_atomic(engine, 6, slab_dt, false)
	publication = engine.call("publication")
	var slab_radiation := _floats(publication.radiation)
	var slab_actual := slab_radiation[_radiation_index(0, slab_group, 0, groups, angles)]
	# Post-step coefficients the transfer did not use.  They are reported for
	# drift attribution only and never enter `slab_expected`.
	var post_opacity := _floats(publication.opacity)
	var post_emission := _floats(publication.emission)
	var post_state := _state_floats(engine)
	var post_ion_fraction: float = post_state[3][2] \
			/ maxf(post_state[2][0] + post_state[3][2], 1.0e-30)
	var post_scattering := post_ion_fraction \
			* float(publication.density_kg_m3_per_sim) / M_H \
			* float((_model.get("constants", {}) as Dictionary).get("sigma_T_m2", 0.0)) \
			* float(publication.length_m_per_sim)
	var post_absorption := maxf(post_opacity[slab_group] - post_scattering, 0.0)
	var slab_opacity_drift := _relative_error(post_opacity[slab_group], slab_total_opacity)
	var slab_emission_drift := _relative_error(post_emission[slab_group],
			slab_emission[slab_group])
	var population_delta := 0.0
	for index in range(transfer_population0.size()):
		population_delta = maxf(population_delta,
				absf(post_state[2][index] - transfer_population0[index]))
	for index in range(transfer_population1.size()):
		population_delta = maxf(population_delta,
				absf(post_state[3][index] - transfer_population1[index]))
	var populations_static := population_delta == 0.0
	# `emission[]` is the normalized volumetric emissivity coefficient. Mode 6
	# uses source = emission / (4*pi*c*kappa_abs), and the ordinate weights sum
	# to 4*pi. With zero initial radiation, every ordinate receives the same
	# absorptive target T, so mean_after_absorption = 4*pi*T and
	# mean_after_absorption / 4*pi = T; scattering therefore adds no factor.
	# The CPU scale oracle below includes emission_scale in expected and proves
	# lambda = 1 from the full-exchange thermal margin.
	var slab_expected: float
	if slab_absorption > 1.0e-30:
		slab_expected = slab_emission[slab_group] \
				/ (4.0 * PI * float(publication.c_reduced_sim) * slab_absorption) \
				* (1.0 - exp(-float(publication.c_reduced_sim)
				* slab_absorption * slab_dt)) * slab_emission_scale
	else:
		slab_expected = slab_emission[slab_group] * slab_dt \
				* slab_emission_scale / (4.0 * PI)
	var slab_error := _relative_error(slab_actual, slab_expected)
	var slab_state := _state_floats(engine)
	var slab_population0 := slab_state[2]
	var slab_population1 := slab_state[3]
	var slab_ion_fraction := slab_population1[2] \
			/ maxf(slab_population0[0] + slab_population1[2], 1.0e-30)
	var slab_emission_group := _maximum_group(slab_emission, cells, groups)
	var slab_temperature := slab_state[1][1]
	var slab_nonfinite := 0
	var slab_max_emission := 0.0
	var slab_max_opacity := 0.0
	var slab_post_nonfinite := 0
	for index in range(mini(slab_emission.size(), slab_opacity.size())):
		if not is_finite(slab_emission[index]) or not is_finite(slab_opacity[index]):
			slab_nonfinite += 1
		slab_max_emission = maxf(slab_max_emission, absf(slab_emission[index]))
		slab_max_opacity = maxf(slab_max_opacity, absf(slab_opacity[index]))
	for index in range(mini(post_emission.size(), post_opacity.size())):
		if not is_finite(post_emission[index]) or not is_finite(post_opacity[index]):
			slab_post_nonfinite += 1
	var after_material := _material_energy(engine)
	var source_exchange := _ledger_total(engine, "ledger0", 3)
	var radiation_delta := _radiation_energy(engine)
	var material_delta := after_material - before_material
	var total_source_closure := maxf(absf(radiation_delta - source_exchange),
			absf(material_delta + source_exchange))
	total_source_closure /= maxf(absf(radiation_delta), 1.0e-30)
	_record("PM-G5", "homogeneous slab source function matches transfer oracle",
			slab_error <= 2.0e-2 and is_finite(slab_error)
			and absf(total_source_closure) <= 8.0e-5
			and slab_nonfinite == 0 and slab_post_nonfinite == 0 and slab_actual > 0.0
			and slab_pre_emission > 0.0 and slab_source_enabled
			and bool(publication.source_enabled) and populations_static
			and slab_input_radiation_max == 0.0
			and slab_emission_scale > 0.0 and is_finite(slab_emission_scale)
			and slab_lambda_expected_unity
			and absf(float(slab_scale_oracle.get("ordinate_weight_sum_sr", 0.0))
			- 4.0 * PI) <= 1.0e-5, {
		"actual_intensity": slab_actual, "expected_intensity": slab_expected,
		"relative_source_error": slab_error,
		"emission_scale": slab_emission_scale,
		"emission_gain": slab_scale_oracle.get("emission_gain", 0.0),
		"available_energy": slab_scale_oracle.get("available_energy", 0.0),
		"full_exchange_delta_energy": slab_scale_oracle.get("delta_energy", 0.0),
		"thermal_floor": slab_scale_oracle.get("thermal_floor", 0.0),
		"thermal_after_full_exchange":
			slab_scale_oracle.get("thermal_after_full_exchange", 0.0),
		"lambda_expected_unity": slab_lambda_expected_unity,
		"lambda_observed": slab_actual / maxf(slab_expected, 1.0e-30),
		"ordinate_weight_sum_sr": slab_scale_oracle.get("ordinate_weight_sum_sr", 0.0),
		"input_radiation_max": slab_input_radiation_max,
		"scale_oracle": "mode-6 emission_gain/available_energy; thermal_after_full_exchange >= thermal_floor",
		"opacity": slab_total_opacity, "emission": slab_emission[slab_group],
		"scattering": slab_scattering, "absorption": slab_absorption,
		"post_opacity": post_opacity[slab_group], "post_emission": post_emission[slab_group],
		"post_scattering": post_scattering, "post_absorption": post_absorption,
		"opacity_drift": slab_opacity_drift, "emission_drift": slab_emission_drift,
		"ion_fraction": slab_ion_fraction, "temperature_K": slab_temperature,
		"emission_group": slab_emission_group,
		"population0_total": slab_population0[0] + slab_population0[1]
			+ slab_population0[2] + slab_population0[3],
		"population1_total": slab_population1[0] + slab_population1[1]
			+ slab_population1[2] + slab_population1[3],
		"population_delta": population_delta,
		"populations_static": populations_static,
		"source_enabled_after_transfer": bool(publication.source_enabled),
		"transfer_mode": 6,
		"maximum_opacity": slab_max_opacity, "maximum_emission": slab_max_emission,
		"nonfinite_coefficients": slab_nonfinite,
		"post_nonfinite_coefficients": slab_post_nonfinite,
		"c_reduced_sim": float(publication.c_reduced_sim),
		"density_kg_m3_per_sim": float(publication.density_kg_m3_per_sim),
		"material_before": before_material, "material_after": after_material,
		"source_exchange_ledger": source_exchange,
		"source_closure_residual": total_source_closure,
		"fatal_status": _fatal_status(engine),
	})
	_teardown(slab)


func _set_cell_thermal(q0: PackedFloat32Array, q1: PackedFloat32Array,
		p0: PackedFloat32Array, p1: PackedFloat32Array, cell: int, rho: float,
		velocity: Vector3, thermal_energy: float, ion_fraction: float,
		velocity_scale: float) -> void:
	var momentum := rho * velocity
	var levels := _model.get("levels", []) as Array
	var ionization_energy := 0.0
	if levels.size() > 6 and levels[6] is Dictionary:
		ionization_energy = float((levels[6] as Dictionary).get(
				"excitation_energy_J", 0.0))
	var chemical_energy := ion_fraction * ionization_energy \
			/ (M_H * maxf(velocity_scale * velocity_scale, 1.0e-30))
	q0[cell * 4] = rho; q0[cell * 4 + 1] = momentum.x
	q0[cell * 4 + 2] = momentum.y; q0[cell * 4 + 3] = momentum.z
	q1[cell * 4] = thermal_energy + chemical_energy \
			+ 0.5 * rho * velocity.length_squared()
	q1[cell * 4 + 1] = thermal_energy * (GAMMA - 1.0) * M_H * velocity_scale \
			* velocity_scale / (K_B * maxf(rho * (1.0 + ion_fraction), 1.0e-30))
	q1[cell * 4 + 2] = (GAMMA - 1.0) * thermal_energy
	p0[cell * 4] = rho * (1.0 - ion_fraction)
	p1[cell * 4 + 2] = rho * ion_fraction


## Builds a hydrogen fixture whose per-cell temperature matches `temperatures_K`
## after the engine's own kinetics solve, so the published coefficients are the
## coefficients the source exchange applies.  The loop is a Newton iteration on
## the conserved total-energy channel: the engine recovers temperature from
## thermal energy, so pinning the recovered temperature pins the state.
func _make_settled_engine(grid: Vector3i, extents: Vector3,
		temperatures_K: PackedFloat32Array, ion_hints: PackedFloat32Array,
		overrides: Dictionary) -> Dictionary:
	var cells := grid.x * grid.y * grid.z
	var result := _make_engine(grid, extents, PackedFloat32Array([0.0, 0.0, 0.0, 1.0]),
			PackedFloat32Array([0.0, 0.0, 0.0, 0.0]),
			PackedFloat32Array([0.0, 0.0, 0.0, 0.0]), overrides)
	if not bool(result.get("ok", false)):
		return result
	var engine: RefCounted = result.engine
	var velocity_scale := _velocity_scale_per_sim(engine)
	var kelvin_per_energy := (GAMMA - 1.0) * M_H * velocity_scale * velocity_scale / K_B
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	q0.resize(cells * 4); q1.resize(cells * 4); p0.resize(cells * 4); p1.resize(cells * 4)
	for cell in range(cells):
		var ion := ion_hints[cell] if cell < ion_hints.size() else 0.0
		_set_cell_thermal(q0, q1, p0, p1, cell, 1.0, Vector3.ZERO,
				temperatures_K[cell] * (1.0 + ion) / kelvin_per_energy, ion, velocity_scale)
	_set_material_state(engine, q0, q1, p0, p1, PackedFloat32Array())
	var trace: Array[float] = []
	var population_trace: Array[float] = []
	var previous_ions := 0.0
	var achieved := PackedFloat32Array(); achieved.resize(cells)
	for _iteration in range(48):
		# The settle interval must be long enough for the rate solve to reach its
		# own fixed point (excitation and ionization are rate processes), so it is
		# a finite physical time, not a perturbation.  The energy correction below
		# is the thermostat that holds the target temperature through it.
		_direct_atomic(engine, 0, 2.0e-2, false)
		# Re-upload the engine's own solved state, not the initial hint: the
		# converged fixture must be a fixed point of the kinetics solve.
		var state := _state_floats(engine)
		var material1 := state[1]
		var worst := 0.0
		for cell in range(cells):
			achieved[cell] = material1[cell * 4 + 1]
			if temperatures_K[cell] > 0.0:
				worst = maxf(worst, absf(achieved[cell] / temperatures_K[cell] - 1.0))
		trace.append(worst)
		var population_drift := 0.0
		var ions := 0.0
		for cell in range(cells):
			ions += maxf(state[3][cell * 4 + 2], 0.0)
		if previous_ions > 0.0:
			population_drift = absf(ions / previous_ions - 1.0)
		previous_ions = ions
		population_trace.append(population_drift)
		# The first pass can match trivially (the energy channel is set from the
		# target), so require repeated agreement of both the temperature and the
		# rate-solved populations before declaring a fixed point.
		if _iteration >= 2 and worst <= 2.0e-3 and population_drift <= 1.0e-3:
			break
		for cell in range(cells):
			# (1 + ion) is already reflected in the recovered temperature, so the
			# Newton step is the plain Kelvin-to-energy conversion.
			material1[cell * 4] += (temperatures_K[cell] - achieved[cell]) / kelvin_per_energy
		_set_material_state(engine, state[0], material1, state[2], state[3], PackedFloat32Array())
	_direct_atomic(engine, 4, 0.0, false)
	result["temperatures_K"] = achieved
	result["settle_trace"] = trace
	result["population_trace"] = population_trace
	return result


## A hydrogen fixture settled to the requested temperature at the requested SI
## density.  `mass_scale` is `mass_kg_per_sim` in units of the hydrogen mass, so
## with unit length it is also the SI number density in m^-3 (n = mass_scale).
## The returned engine's published coefficients are the coefficients its source
## exchange applies, because the settle loop drives the engine's own kinetics
## solve before the fixture is used.  It is not a fixed point the caller selects
## by outcome: `_make_settled_engine` iterates on temperature and population
## drift only, and a caller that needs an emitting state asserts the published
## source afterwards instead of steering the loop until it emits.
func _make_settled_hydrogen_engine(temperature_K: float, mass_scale: float,
		ion_hint: float, overrides: Dictionary = {}) -> Dictionary:
	var grid := Vector3i(4, 4, 4)
	var cells := grid.x * grid.y * grid.z
	var temperatures := PackedFloat32Array(); temperatures.resize(cells)
	var ions := PackedFloat32Array(); ions.resize(cells)
	temperatures.fill(temperature_K)
	# A zero-electron seed is an absorbing fixed point of the rate solve: with no
	# electrons there is no collisional ionization or excitation, so an emitting
	# settled fixture must start ionized and let recombination settle it.
	ions.fill(ion_hint)
	# c_reduced = 30: fast enough that radiation momentum is a small correction to
	# the material energy, slow enough to keep the transport CFL reachable in tests.
	var config := {
		"time_s_per_sim": 1.0e-4,
		"mass_kg_per_sim": M_H * mass_scale,
		"reduced_light_fraction": 1,
	}
	config.merge(overrides, true)
	return _make_settled_engine(grid, Vector3.ONE, temperatures, ions, config)


## Directly packs an emitting ionized state without evolving its populations.
## The first mode-4 publication is source-enabled and therefore exercises the
## live coefficient path; callers may then freeze populations explicitly for a
## transfer-only step with set_source_enabled(false).
func _make_ionized_hydrogen_engine(temperature_K: float, mass_scale: float,
		ion_hint: float) -> Dictionary:
	var grid := Vector3i(4, 4, 4)
	var cells := grid.x * grid.y * grid.z
	var result := _make_engine(grid, Vector3.ONE,
			PackedFloat32Array([0.0, 0.0, 0.0, 1.0]),
			PackedFloat32Array([0.0, 0.0, 0.0, 0.0]),
			PackedFloat32Array([0.0, 0.0, 0.0, 0.0]), {
		"time_s_per_sim": 1.0e-4,
		"mass_kg_per_sim": M_H * mass_scale,
		"reduced_light_fraction": 1,
		"source_enabled": true,
	})
	if not bool(result.get("ok", false)):
		return result
	var engine: RefCounted = result.engine
	var temperatures := PackedFloat32Array(); temperatures.resize(cells)
	var ions := PackedFloat32Array(); ions.resize(cells)
	temperatures.fill(temperature_K)
	ions.fill(ion_hint)
	var velocity_scale := _velocity_scale_per_sim(engine)
	var kelvin_per_energy := (GAMMA - 1.0) * M_H * velocity_scale * velocity_scale / K_B
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	q0.resize(cells * 4); q1.resize(cells * 4)
	p0.resize(cells * 4); p1.resize(cells * 4)
	for cell in range(cells):
		_set_cell_thermal(q0, q1, p0, p1, cell, 1.0, Vector3.ZERO,
				temperature_K * (1.0 + ion_hint) / kelvin_per_energy,
				ion_hint, velocity_scale)
	_set_material_state(engine, q0, q1, p0, p1, PackedFloat32Array())
	_direct_atomic(engine, 4, 0.0, false)
	result["source_enabled_at_publication"] = bool(
			(engine.call("publication") as Dictionary).source_enabled)
	result["temperatures_K"] = temperatures
	return result

func _check_coupled_lifecycle() -> void:
	var context := _make_uniform_engine(Vector3i(4, 4, 4), Vector3.ONE,
			1.0, 1.0, Vector3.ZERO, {
		"dt_sim": 1.0e-3,
		"time_s_per_sim": 1.0,
		"reduced_light_fraction": 1.0 / 299792458.0,
	})
	if not bool(context.get("ok", false)):
		_record("PM-G7", "256-step lifecycle fixture initializes", false, {
			"error": context.get("error", "")})
		_teardown(context)
		return
	var engine: RefCounted = context.engine
	var initial_energy := _material_energy(engine) + _radiation_energy(engine)
	var initial_state := _state_floats(engine)
	var failed_step := -1
	var failed_commit := -1
	for index in range(256):
		var commands := _rd.compute_list_begin()
		var recorded: bool = bool(engine.call("record_step", commands, 1.0e-3))
		_rd.compute_list_end()
		if not recorded:
			failed_step = index
			break
		_rd.submit()
		_rd.sync()
		if not bool(engine.call("commit_recorded_steps")):
			failed_commit = index
			break
	var publication: Dictionary = engine.call("publication")
	var accepted := int(publication.get("accepted_steps", -1))
	var expected_time := 256.0 * 1.0e-3
	# accumulate_spatial_escape (atomic.glsl:790-809) books radiation loss in
	# ledger0.z. Hydro's open boundary separately books escaped material energy in
	# ledger1.y, while the gravity kick records signed external work in ledger1.z.
	# The latter is subtracted because that work is already present in material1.x.
	var escaped_radiation_energy := _ledger_total(engine, "ledger0", 2)
	var escaped_material_energy := _ledger_total(engine, "ledger1", 1)
	var gravity_work := _ledger_total(engine, "ledger1", 2)
	var final_energy := _material_energy(engine) + _radiation_energy(engine) \
			+ escaped_radiation_energy + escaped_material_energy - gravity_work
	var energy_balance := _relative_error(final_energy, initial_energy)
	var initial_momentum := _material_momentum_from_values(engine, initial_state[0])
	var final_momentum := _material_momentum(engine) + _ledger_vector_total(engine, "ledger2")
	var momentum_scale := maxf(_total_material_mass(engine)
			* maxf(float(publication.c_reduced_sim), 1.0), 1.0e-30)
	var momentum_balance := (final_momentum - initial_momentum).length() / momentum_scale
	var lifecycle_ok := failed_step < 0 and failed_commit < 0 \
			and accepted == 256 \
			and absf(float(publication.get("physical_time_sim", -1.0))
				- expected_time) <= 1.0e-8 \
			and _fatal_status(engine) == 0 \
			and energy_balance <= 2.0e-4 \
			and momentum_balance <= 2.0e-4
	_record("PM-G7", "256 committed steps preserve lifecycle and ledger balances",
			lifecycle_ok, {
		"accepted_steps": accepted,
		"expected_steps": 256,
		"physical_time_sim": publication.get("physical_time_sim", -1.0),
		"expected_time_sim": expected_time,
		"record_failure_step": failed_step,
		"commit_failure_step": failed_commit,
		"relative_energy_balance": energy_balance,
		"spatial_radiation_escape_energy": escaped_radiation_energy,
		"escaped_material_energy": escaped_material_energy,
		"gravity_work": gravity_work,
		"final_total_energy_with_ledgers": final_energy,
		"initial_momentum": _vec(initial_momentum),
		"final_momentum_with_boundary_ledger": _vec(final_momentum),
		"relative_momentum_balance": momentum_balance,
		"fatal_status": _fatal_status(engine),
		"status_values": publication.get("status_values", {}),
		"maximum_pre_source_v_over_c": _status_max_v_over_c(engine),
		"initial_cell0_material0": [initial_state[0][0], initial_state[0][1],
			initial_state[0][2], initial_state[0][3]],
		"initial_cell0_material1": [initial_state[1][0], initial_state[1][1],
			initial_state[1][2], initial_state[1][3]],
		"cell_count": int(engine.get("_cell_count")),
		"c_reduced_sim": float(publication.get("c_reduced_sim", -1.0)),
	})

	var checkpoint: Dictionary = engine.call("checkpoint")
	var checkpoint_state := _physical_state_bytes(engine)
	var checkpoint_ok := bool(checkpoint.get("ok", false))
	var advanced := false
	var advance_commands := _rd.compute_list_begin()
	if bool(engine.call("record_step", advance_commands, 1.0e-5)):
		advanced = true
	_rd.compute_list_end()
	if advanced:
		_rd.submit()
		_rd.sync()
		advanced = bool(engine.call("commit_recorded_steps"))
	var restored := bool(engine.call("restore_checkpoint", checkpoint))
	var restored_state := _physical_state_bytes(engine)
	_record("PM-G7", "valid checkpoint restores the complete ping-pong state",
			checkpoint_ok and advanced and restored and restored_state == checkpoint_state, {
		"checkpoint_ok": checkpoint_ok,
		"advanced_after_checkpoint": advanced,
		"restored": restored,
		"state_equal_after_restore": restored_state == checkpoint_state,
		"checkpoint_error": engine.call("last_error"),
	})

	var malformed := checkpoint.duplicate(true)
	malformed.erase("buffers")
	var before_malformed := _physical_state_bytes(engine)
	var malformed_rejected := not bool(engine.call("restore_checkpoint", malformed))
	var after_malformed := _physical_state_bytes(engine)
	_record("PM-G7", "malformed checkpoint rejects without mutating state",
			malformed_rejected and before_malformed == after_malformed, {
		"rejected": malformed_rejected,
		"state_unchanged": before_malformed == after_malformed,
		"error": engine.call("last_error"),
	})

	engine.call("shutdown")
	var after_shutdown: Dictionary = engine.call("publication")
	var shutdown_reset := not bool(engine.call("is_operational")) \
			and not bool(after_shutdown.get("ready", true)) \
			and int(engine.get("_accepted_steps")) == 0 \
			and is_zero_approx(float(engine.get("_physical_time_sim"))) \
			and not bool(engine.get("_prepared"))
	_record("PM-G7", "shutdown releases resources and resets lifecycle state",
			shutdown_reset, {
		"operational_after_shutdown": engine.call("is_operational"),
		"accepted_steps_after_shutdown": engine.get("_accepted_steps"),
		"physical_time_after_shutdown": engine.get("_physical_time_sim"),
		"prepared_after_shutdown": engine.get("_prepared"),
	})
	_teardown(context)


func _check_physical_observation() -> void:
	var context := _make_ionized_hydrogen_engine(12000.0, 1.0e21, 1.0)
	if not bool(context.get("ok", false)):
		_record("PM-G8", "physical observation fixture initializes", false, {
			"error": context.get("error", "")})
		_teardown(context)
		return
	var engine: RefCounted = context.engine
	_direct_atomic(engine, 4, 0.0, false)
	# The observer renders the engine's published coefficients.  The fixture is
	# directly ionized and its first publication is source-enabled, so a black
	# image is a failed source/observer path rather than a vacuous all-neutral
	# input.  Keep this source precondition explicit at the boundary.
	var observation_publication: Dictionary = engine.call("publication")
	var observation_pre_emission := _maximum_value(
			_floats(observation_publication.emission))
	var observation_pre_state := _state_floats(engine)
	var observation_pre_ion: float = observation_pre_state[3][2] \
			/ maxf(observation_pre_state[2][0] + observation_pre_state[3][2], 1.0e-30)
	var observer_source_ok := observation_pre_emission > 0.0 \
			and bool(context.get("source_enabled_at_publication", false)) \
			and bool(observation_publication.source_enabled)
	_record("PM-G8", "physical observation fixture publishes a non-trivial source",
			observer_source_ok, {
		"pre_observation_maximum_emission": observation_pre_emission,
		"pre_observation_ion_fraction": observation_pre_ion,
		"source_enabled": bool(observation_publication.source_enabled),
		"source_enabled_at_publication":
			bool(context.get("source_enabled_at_publication", false)),
	})
	var volume_script := load("res://scripts/cassi_physical_volume.gd")
	var volume: RefCounted = volume_script.new()
	var volume_ready: bool = bool(volume.call("initialize", _rd))
	var frame := {
		"physical_resources": engine.call("publication"),
		"physical_model_path": MODEL_PATH,
		"render_size": Vector2i(48, 24),
		"bounds": AABB(-Vector3.ONE, Vector3.ONE * 2.0),
		"camera_transform": Transform3D(Basis.IDENTITY, Vector3(0.0, 0.0, 3.0)),
		"fov": 45.0,
		"near": 0.01,
	}
	var observer_opacity_values := _floats(observation_publication.opacity)
	var observer_max_opacity := _maximum_value(observer_opacity_values)
	# Calibrate the two observer captures to declared optical depths through
	# the central ray of this unit-depth fixture.  The live opacity is a
	# dimensionless per-simulation-length coefficient, so the old 0.1/10
	# settings were both effectively vacuum at this density.
	var observer_reference_path := (frame["bounds"] as AABB).size.z
	var observer_tau_per_scale := observer_max_opacity * observer_reference_path
	var thin_optical_scale := 0.1 / maxf(observer_tau_per_scale, 1.0e-30)
	var thick_optical_scale := 10.0 / maxf(observer_tau_per_scale, 1.0e-30)
	var observer_tau_controls := {
		"reference_path_sim": observer_reference_path,
		"maximum_opacity": observer_max_opacity,
		"tau_per_scale": observer_tau_per_scale,
		"thin_target": 0.1,
		"thick_target": 10.0,
		"thin_optical_scale": thin_optical_scale,
		"thick_optical_scale": thick_optical_scale,
	}
	var thin_ok := false
	var thick_ok := false
	var thin_xyz := PackedFloat32Array()
	var thick_xyz := PackedFloat32Array()
	var thin_rgb := PackedFloat32Array()
	var thick_rgb := PackedFloat32Array()
	var thin_depth := PackedFloat32Array()
	var thick_depth := PackedFloat32Array()
	var moved_xyz := PackedFloat32Array()
	var moved_depth := PackedFloat32Array()
	var moved_ok := false
	var solver_before := _physical_state_bytes(engine)
	if volume_ready:
		thin_ok = bool(volume.call("update", frame, {
			# Extinction and emissivity scale together: this is a path-length
			# capture, not a brightness-only adjustment.
			"optical_thickness": thin_optical_scale,
			"emission": thin_optical_scale}))
		_rd.submit()
		_rd.sync()
		if thin_ok:
			thin_xyz = _texture_floats(volume.get("_xyz_rid") as RID)
			thin_rgb = _texture_floats(volume.get("_display_rid") as RID)
			thin_depth = _texture_floats(volume.get("_depth_rid") as RID)
		var thick_update := bool(volume.call("update", frame, {
			"optical_thickness": thick_optical_scale,
			"emission": thick_optical_scale, "exposure_ev": -6.0}))
		_rd.submit()
		_rd.sync()
		thick_ok = thick_update
		if thick_ok:
			thick_xyz = _texture_floats(volume.get("_xyz_rid") as RID)
			thick_rgb = _texture_floats(volume.get("_display_rid") as RID)
			thick_depth = _texture_floats(volume.get("_depth_rid") as RID)
		# B3: re-render the same scene from a moved camera.  A weighted mean of
		# pixel centres is confined to [0, 1] by construction, so the old
		# unit-square centroid test could not fail; an observation that ignores the
		# camera cannot move its image centroid.
		if thin_ok:
			var moved_frame: Dictionary = frame.duplicate(true)
			moved_frame["camera_transform"] = Transform3D(Basis.IDENTITY,
					Vector3(1.2, 0.7, 3.0))
			moved_ok = bool(volume.call("update", moved_frame, {
				"optical_thickness": thin_optical_scale,
				"emission": thin_optical_scale}))
			_rd.submit()
			_rd.sync()
			if moved_ok:
				moved_xyz = _texture_floats(volume.get("_xyz_rid") as RID)
				moved_depth = _texture_floats(volume.get("_depth_rid") as RID)
	var solver_after := _physical_state_bytes(engine)
	var thin_summary := _observation_summary(thin_xyz, thin_depth, Vector2i(48, 24))
	var thick_summary := _observation_summary(thick_xyz, thick_depth, Vector2i(48, 24))
	var moved_summary := _observation_summary(moved_xyz, moved_depth, Vector2i(48, 24))
	var thin_centroid := thin_summary.centroid as Array
	var moved_centroid := moved_summary.centroid as Array
	# Only a real capture may produce a shift; a failed update leaves the default
	# summary, whose centroid would otherwise masquerade as a large delta.
	var centroid_shift := 0.0
	if moved_ok:
		centroid_shift = maxf(
				absf(float(moved_centroid[0]) - float(thin_centroid[0])),
				absf(float(moved_centroid[1]) - float(thin_centroid[1])))
	var ciede76 := _mean_ciede76(thin_xyz, thick_xyz)
	var raw_ok := thin_ok and thick_ok \
			and _observation_finite_nonnegative(thin_xyz) \
			and _observation_finite_nonnegative(thick_xyz) \
			and int(thin_xyz.size()) == 48 * 24 * 4
	var transfer_ok := raw_ok \
			and float(thick_summary.mean_xyz) > float(thin_summary.mean_xyz) \
			and is_finite(ciede76) and ciede76 > 1.0e-5
	var centroids_ok := raw_ok and moved_ok \
			and _observation_finite_nonnegative(moved_xyz) \
			and int(moved_xyz.size()) == 48 * 24 * 4 \
			and float(thin_summary.signal) > 0.0 \
			and is_finite(centroid_shift) and centroid_shift >= 0.02 \
			and is_finite(float(thin_summary.depth_centroid)) \
			and is_finite(float(thick_summary.depth_centroid)) \
			and is_finite(float(moved_summary.depth_centroid))
	var exposure_pure := solver_before == solver_after
	var stats: Dictionary = volume.call("statistics")
	var thin_display := thin_rgb
	var observer_publication: Dictionary = engine.call("publication")
	var observer_coefficients := _floats(observer_publication.opacity)
	var observer_emission := _floats(observer_publication.emission)
	# L11: the observers consume these buffers, so their validity is measured with
	# signed values (an abs() maximum would accept an all-negative buffer) and
	# each buffer is scanned on its own length.
	var observer_max_opacity_report := -INF
	var observer_max_emission := -INF
	var observer_nonfinite := 0
	var observer_negative := 0
	for value in observer_coefficients:
		if not is_finite(value):
			observer_nonfinite += 1
			continue
		observer_max_opacity_report = maxf(observer_max_opacity_report, value)
		if value < 0.0:
			observer_negative += 1
	for value in observer_emission:
		if not is_finite(value):
			observer_nonfinite += 1
			continue
		observer_max_emission = maxf(observer_max_emission, value)
		if value < 0.0:
			observer_negative += 1
	_record("PM-G8", "physical observer publishes finite XYZ with CIEDE separation",
			volume_ready and observer_source_ok and raw_ok and transfer_ok, {
		"volume_ready": volume_ready,
		"thin_update_ok": thin_ok,
		"thick_update_ok": thick_ok,
		"thin": thin_summary,
		"thick": thick_summary,
		"ciede76_thin_thick": ciede76,
		"source_maximum_opacity": observer_max_opacity_report,
		"source_maximum_emission": observer_max_emission,
		"optical_depth_controls": observer_tau_controls,
		"emission_scales_with_path": true,
		"source_nonfinite_coefficients": observer_nonfinite,
		"source_opacity_cell0": Array(observer_coefficients.slice(0, mini(8,
				observer_coefficients.size()))),
		"source_emission_cell0": Array(observer_emission.slice(0, mini(8,
				observer_emission.size()))),
		"raw_xyz_channels": ["X", "Y", "Z", "valid"],
		"readback_sizes": {
			"xyz": thin_xyz.size(), "expected_xyz": 48 * 24 * 4,
			"depth": thin_depth.size(), "expected_depth": 48 * 24,
			"display": thin_display.size(), "expected_display": 48 * 24 * 4,
		},
		"thin_display_sample": [thin_display[0], thin_display[1], thin_display[2]]
			if thin_display.size() >= 4 else [],
		"volume_error": volume.get("_last_error"),
		"renderer_statistics": stats,
	})
	_record("PM-G8", "thin/thick observations expose a camera-sensitive centroid",
			centroids_ok and observer_source_ok, {
		"centroids_valid": centroids_ok,
		"moved_capture_ok": moved_ok,
		"centroid_shift": centroid_shift,
		"required_centroid_shift": 0.02,
		"thin_centroid": thin_summary.centroid,
		"thick_centroid": thick_summary.centroid,
		"moved_centroid": moved_summary.centroid,
		"thin_depth_centroid": thin_summary.depth_centroid,
		"thick_depth_centroid": thick_summary.depth_centroid,
		"moved_depth_centroid": moved_summary.depth_centroid,
		"thin_signal": thin_summary.signal,
	})
	# L11: the source coefficients the observer consumes are part of the
	# observation, so assert the shape, finiteness, and non-triviality that the
	# metrics above only reported.
	var observer_groups := int(observer_publication.groups)
	var observer_grid: Vector3i = observer_publication.grid
	var observer_cells := observer_grid.x * observer_grid.y * observer_grid.z
	var observer_valid := volume_ready and observer_nonfinite == 0 and observer_negative == 0 \
			and observer_coefficients.size() == observer_cells * observer_groups \
			and observer_emission.size() == observer_cells * observer_groups \
			and observer_max_opacity > 0.0 and observer_max_emission > 0.0
	_record("PM-G8", "observer source coefficients are finite, sized, and non-trivial",
			observer_valid, {
		"volume_ready": volume_ready,
		"observer_nonfinite_coefficients": observer_nonfinite,
		"observer_negative_coefficients": observer_negative,
		"opacity_size": observer_coefficients.size(),
		"emission_size": observer_emission.size(),
		"expected_size": observer_cells * observer_groups,
		"maximum_opacity": observer_max_opacity,
		"maximum_emission": observer_max_emission,
	})
	_record("PM-G8", "camera observation and exposure remain solver-pure",
			exposure_pure and int(stats.get("dispatch_count", 0)) >= 2, {
		"solver_unchanged": exposure_pure,
		"dispatch_count": stats.get("dispatch_count", 0),
		"raw_capture_count": stats.get("raw_capture_count", 0),
	})
	volume.call("shutdown")
	_teardown(context)


func _texture_floats(rid: RID) -> PackedFloat32Array:
	if not rid.is_valid():
		return PackedFloat32Array()
	return _rd.texture_get_data(rid, 0).to_float32_array()


## Interleaved [X, Y, Z, valid] pixel validity, shared with the production arm.
func _observation_finite_nonnegative(values: PackedFloat32Array) -> bool:
	return ArmMetrics.finite_nonnegative(values)


func _observation_summary(xyz: PackedFloat32Array, depth: PackedFloat32Array,
		size: Vector2i) -> Dictionary:
	if xyz.is_empty() or xyz.size() < size.x * size.y * 4:
		return {
			"mean_xyz": 0.0, "centroid": [0.0, 0.0],
			"depth_centroid": 0.0, "signal": 0.0,
		}
	var total := 0.0
	var weighted_x := 0.0
	var weighted_y := 0.0
	var weighted_depth := 0.0
	for y in range(size.y):
		for x in range(size.x):
			var pixel := x + size.x * y
			var base := pixel * 4
			var weight := maxf(xyz[base + 1], 0.0)
			total += weight
			weighted_x += weight * (float(x) + 0.5) / float(size.x)
			weighted_y += weight * (float(y) + 0.5) / float(size.y)
			if pixel < depth.size():
				# The depth target is a single-channel R32_SFLOAT texture.
				weighted_depth += weight * maxf(depth[pixel], 0.0)
	var divisor := maxf(total, 1.0e-30)
	var mean_xyz := 0.0
	for index in range(0, size.x * size.y * 4, 4):
		mean_xyz += xyz[index] + xyz[index + 1] + xyz[index + 2]
	mean_xyz /= maxf(float(size.x * size.y), 1.0)
	return {
		"mean_xyz": mean_xyz,
		"centroid": [weighted_x / divisor, weighted_y / divisor],
		"depth_centroid": weighted_depth / divisor,
		"signal": total,
	}


func _xyz_to_lab(value: Vector3) -> Vector3:
	var white := Vector3(0.95047, 1.0, 1.08883)
	var scaled := Vector3(value.x / white.x, value.y / white.y, value.z / white.z)
	var fx := _lab_curve(scaled.x)
	var fy := _lab_curve(scaled.y)
	var fz := _lab_curve(scaled.z)
	return Vector3(116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


func _lab_curve(value: float) -> float:
	return pow(maxf(value, 0.0), 1.0 / 3.0) if value > 0.008856451679 else \
			7.787037037 * value + 16.0 / 116.0


func _mean_ciede76(first: PackedFloat32Array, second: PackedFloat32Array) -> float:
	if first.size() == 0 or first.size() != second.size() or first.size() % 4 != 0:
		return NAN
	var scale := 0.0
	for index in range(0, first.size(), 4):
		scale = maxf(scale, first[index])
		scale = maxf(scale, first[index + 1])
		scale = maxf(scale, first[index + 2])
		scale = maxf(scale, second[index])
		scale = maxf(scale, second[index + 1])
		scale = maxf(scale, second[index + 2])
	scale = maxf(scale, 1.0e-30)
	var sum := 0.0
	var count := first.size() / 4
	for index in range(0, first.size(), 4):
		var a := _xyz_to_lab(Vector3(first[index], first[index + 1], first[index + 2]) / scale)
		var b := _xyz_to_lab(Vector3(second[index], second[index + 1], second[index + 2]) / scale)
		sum += a.distance_to(b)
	return sum / maxf(float(count), 1.0)


func _check_moving_transport() -> void:
	var expansion := _make_gradient_engine("expansion")
	var compression := _make_gradient_engine("compression")
	if not bool(expansion.get("ok", false)) or not bool(compression.get("ok", false)):
		_record("PM-G6", "expansion and compression fixtures initialize", false, {
			"expansion_error": expansion.get("error", ""),
			"compression_error": compression.get("error", "")})
		_teardown(expansion)
		_teardown(compression)
		return
	var expansion_engine: RefCounted = expansion.engine
	var compression_engine: RefCounted = compression.engine
	var group := int(expansion_engine.get("_group_count")) / 2
	var angle := _nearest_ordinate(expansion_engine, Vector3.RIGHT)
	_seed_single_radiation(expansion_engine, group, angle, 1.0)
	_seed_single_radiation(compression_engine, group, angle, 1.0)
	var dt := 20.0
	var expansion_before_frequency := _radiation_frequency_centroid(expansion_engine)
	var compression_before_frequency := _radiation_frequency_centroid(compression_engine)
	var expansion_before_total := _material_energy(expansion_engine) \
			+ _radiation_energy(expansion_engine)
	var compression_before_total := _material_energy(compression_engine) \
			+ _radiation_energy(compression_engine)
	_direct_atomic(expansion_engine, 1, dt, true)
	_direct_atomic(compression_engine, 1, dt, true)
	var expansion_after_frequency := _radiation_frequency_centroid(expansion_engine)
	var compression_after_frequency := _radiation_frequency_centroid(compression_engine)
	var expansion_expected := _moving_frequency_oracle(
			expansion_engine, group, angle, dt, 0.015)
	var compression_expected := _moving_frequency_oracle(
			compression_engine, group, angle, dt, -0.015)
	var expansion_width := _frequency_group_width(expansion_engine, group)
	var compression_width := _frequency_group_width(compression_engine, group)
	var expansion_error := absf(expansion_after_frequency - expansion_expected) \
			/ maxf(expansion_width, 1.0e-30)
	var compression_error := absf(compression_after_frequency - compression_expected) \
			/ maxf(compression_width, 1.0e-30)
	var expansion_red := expansion_after_frequency < expansion_before_frequency
	var compression_blue := compression_after_frequency > compression_before_frequency
	var expansion_balance := _relative_error(
			_material_energy(expansion_engine) + _radiation_energy(expansion_engine),
			expansion_before_total)
	var compression_balance := _relative_error(
			_material_energy(compression_engine) + _radiation_energy(compression_engine),
			compression_before_total)
	var moving_ledgers_ok := _ledger_finite_nonnegative(expansion_engine) \
			and _ledger_finite_nonnegative(compression_engine)
	_record("PM-G6", "Doppler red and blue centroids match first-order oracle",
			expansion_red and compression_blue
			and expansion_error <= 0.35 and compression_error <= 0.35
			and moving_ledgers_ok and expansion_balance <= 8.0e-5
			and compression_balance <= 8.0e-5, {
		"expansion_before_frequency": expansion_before_frequency,
		"expansion_after_frequency": expansion_after_frequency,
		"expansion_expected_frequency": expansion_expected,
		"expansion_error_group_widths": expansion_error,
		"compression_before_frequency": compression_before_frequency,
		"compression_after_frequency": compression_after_frequency,
		"compression_expected_frequency": compression_expected,
		"compression_error_group_widths": compression_error,
		"expansion_relative_energy_balance": expansion_balance,
		"compression_relative_energy_balance": compression_balance,
		"ledgers_finite_nonnegative": moving_ledgers_ok,
	})
	_teardown(expansion)
	_teardown(compression)

	var transverse := _make_gradient_engine("transverse")
	if not bool(transverse.get("ok", false)):
		_record("PM-G6", "transverse-flow fixture initializes", false, {
			"error": transverse.get("error", "")})
		return
	var transverse_engine: RefCounted = transverse.engine
	group = int(transverse_engine.get("_group_count")) / 2
	angle = _nearest_ordinate(transverse_engine, Vector3.RIGHT)
	_seed_single_radiation(transverse_engine, group, angle, 1.0)
	var before_moment := _radiation_first_moment(transverse_engine)
	_direct_atomic(transverse_engine, 1, 1.0, true)
	var after_moment := _radiation_first_moment(transverse_engine)
	var target_direction := Vector3(1.0, -0.01, 0.0).normalized()
	var angular_error := after_moment.distance_to(target_direction)
	_record("PM-G6", "transverse aberration preserves the angular first moment",
			angular_error <= 2.0e-2
			and _ledger_finite_nonnegative(transverse_engine), {
		"before_first_moment": _vec(before_moment),
		"after_first_moment": _vec(after_moment),
		"oracle_first_moment": _vec(target_direction),
		"angular_error": angular_error,
		"ledgers_finite_nonnegative": _ledger_finite_nonnegative(transverse_engine),
	})
	_teardown(transverse)


func _make_gradient_engine(kind: String) -> Dictionary:
	var fixture := _make_uniform_engine(Vector3i(8, 8, 8), Vector3.ONE,
			1.0, 1.0, Vector3.ZERO, {
		"time_s_per_sim": 1.0,
		"mass_kg_per_sim": M_H * 1.0e12,
		"reduced_light_fraction": 1.0 / 299792458.0,
	})
	if not bool(fixture.get("ok", false)):
		return fixture
	var engine: RefCounted = fixture.engine
	var grid: Vector3i = engine.get("_grid")
	var cells := grid.x * grid.y * grid.z
	var velocity_scale := _velocity_scale_per_sim(engine)
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	q0.resize(cells * 4); q1.resize(cells * 4)
	p0.resize(cells * 4); p1.resize(cells * 4)
	for z in range(grid.z):
		for y in range(grid.y):
			for x in range(grid.x):
				var cell := x + grid.x * (y + grid.y * z)
				var position := _cell_position(Vector3i(x, y, z), grid, Vector3.ONE)
				var velocity := Vector3.ZERO
				if kind == "expansion":
					velocity.x = 0.015 * position.x
				elif kind == "compression":
					velocity.x = -0.015 * position.x
				elif kind == "transverse":
					velocity.y = 0.01 * position.x
				_set_cell(q0, q1, p0, p1, cell, 1.0, velocity, 1.0, 0.0, velocity_scale)
	_set_material_state(engine, q0, q1, p0, p1, PackedFloat32Array())
	return fixture


func _seed_single_radiation(engine: RefCounted, group: int, angle: int,
		value: float) -> void:
	var cells: int = int(engine.get("_cell_count"))
	var groups: int = int(engine.get("_group_count"))
	var angles: int = int(engine.get("_angle_count"))
	var radiation := PackedFloat32Array()
	radiation.resize(cells * groups * angles)
	var grid: Vector3i = engine.get("_grid")
	var cell := grid.x / 2 + grid.x * (grid.y / 2 + grid.y * (grid.z / 2))
	radiation[_radiation_index(cell, group, angle, groups, angles)] = value
	var state := _state_floats(engine)
	_set_material_state(engine, state[0], state[1], state[2], state[3], radiation)


func _frequency_group_width(engine: RefCounted, group: int) -> float:
	var publication: Dictionary = engine.call("publication")
	var frequency := _floats(publication.frequency)
	return maxf(frequency[group * 4 + 1] - frequency[group * 4], 1.0e-30)


func _moving_frequency_oracle(engine: RefCounted, source_group: int,
		angle: int, dt: float, gradient_xx: float) -> float:
	var publication: Dictionary = engine.call("publication")
	var frequency := _floats(publication.frequency)
	var ordinates := _floats(publication.ordinates)
	var midpoint := frequency[source_group * 4 + 2]
	var direction := Vector3(ordinates[angle * 4], ordinates[angle * 4 + 1],
			ordinates[angle * 4 + 2])
	var target := midpoint * exp(-dt * gradient_xx * direction.x * direction.x)
	if target < frequency[0] or target > frequency[(int(publication.groups) - 1) * 4 + 1]:
		return 0.0
	var lower := 0
	for candidate in range(1, int(publication.groups)):
		if target <= frequency[candidate * 4 + 2]:
			lower = candidate - 1
			var fraction := clampf((log(target) - log(frequency[lower * 4 + 2]))
					/ (log(frequency[candidate * 4 + 2])
					- log(frequency[lower * 4 + 2])), 0.0, 1.0)
			return lerpf(frequency[lower * 4 + 2],
					frequency[candidate * 4 + 2], fraction)
	return frequency[(int(publication.groups) - 1) * 4 + 2]


func _radiation_frequency_centroid(engine: RefCounted) -> float:
	var publication: Dictionary = engine.call("publication")
	var radiation := _floats(publication.radiation)
	var frequency := _floats(publication.frequency)
	var ordinates := _floats(publication.ordinates)
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var total := 0.0
	var weighted := 0.0
	for cell in range(int(engine.get("_cell_count"))):
		for group in range(groups):
			var midpoint := frequency[group * 4 + 2]
			for angle in range(angles):
				var value := ordinates[angle * 4 + 3] * radiation[
						_radiation_index(cell, group, angle, groups, angles)]
				total += value
				weighted += value * midpoint
	return weighted / maxf(total, 1.0e-30)


func _radiation_first_moment(engine: RefCounted) -> Vector3:
	var publication: Dictionary = engine.call("publication")
	var radiation := _floats(publication.radiation)
	var ordinates := _floats(publication.ordinates)
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var total := 0.0
	var moment := Vector3.ZERO
	for cell in range(int(engine.get("_cell_count"))):
		for group in range(groups):
			for angle in range(angles):
				var value := ordinates[angle * 4 + 3] * radiation[
						_radiation_index(cell, group, angle, groups, angles)]
				total += value
				moment += value * Vector3(ordinates[angle * 4],
						ordinates[angle * 4 + 1], ordinates[angle * 4 + 2])
	return moment / maxf(total, 1.0e-30)


func _ledger_finite_nonnegative(engine: RefCounted) -> bool:
	var publication: Dictionary = engine.call("publication")
	for name in ["ledger0", "ledger1", "ledger2"]:
		var values := _floats(publication[name])
		for index in range(values.size()):
			if not is_finite(values[index]):
				return false
			if name == "ledger0" and index % 4 < 3 and values[index] < 0.0:
				return false
			if name == "ledger1" and index % 4 != 2 and values[index] < 0.0:
				return false
	return true


func _check_model_identity_and_units() -> void:
	var constants_value: Variant = _model.get("constants", {})
	var units_value: Variant = _model.get("unit_defaults", {})
	var frequency_value: Variant = _model.get("frequency_grid", {})
	var source_value: Variant = _model.get("source_record", {})
	var valid_dicts: bool = constants_value is Dictionary and units_value is Dictionary \
			and frequency_value is Dictionary and source_value is Dictionary
	_record("PM-G1", "model dictionaries are complete", valid_dicts, {})
	if not valid_dicts:
		return
	var constants := constants_value as Dictionary
	var units := units_value as Dictionary
	var frequency := frequency_value as Dictionary
	var source := source_value as Dictionary
	var expected_constants := {
		"c_m_s": 299792458.0,
		"h_J_s": 6.62607015e-34,
		"k_B_J_K": K_B,
		"m_H_kg": M_H,
		"m_e_kg": 9.1093837139e-31,
		"electron_charge_C": 1.602176634e-19,
		"sigma_T_m2": 6.6524587051e-29,
	}
	var max_constant_rel: float = 0.0
	for key_value: Variant in expected_constants:
		var key := String(key_value)
		var expected := float(expected_constants[key])
		var actual := float(constants.get(key, NAN))
		max_constant_rel = maxf(max_constant_rel, abs(actual - expected) / abs(expected))
	var scales_positive: bool = true
	for key in ["length_m_per_sim", "time_s_per_physics_sim",
			"target_total_baryonic_mass_kg", "initial_temperature_K"]:
		var value := float(units.get(key, NAN))
		scales_positive = scales_positive and is_finite(value) and value > 0.0
	var length_scale := float(units.get("length_m_per_sim", NAN))
	var time_scale := float(units.get("time_s_per_physics_sim", NAN))
	var mass_scale := float(units.get("target_total_baryonic_mass_kg", NAN))
	var energy_scale := mass_scale * pow(length_scale / time_scale, 2.0)
	var luminosity_scale := energy_scale / time_scale
	scales_positive = scales_positive and is_finite(energy_scale) and energy_scale > 0.0 \
			and is_finite(luminosity_scale) and luminosity_scale > 0.0
	_record("PM-G1", "SI constants and unit scales close", scales_positive \
			and max_constant_rel <= 2.0e-12, {
		"maximum_constant_relative_error": max_constant_rel,
		"energy_J_per_sim": energy_scale,
		"luminosity_W_per_sim": luminosity_scale,
	})
	var edges_value: Variant = frequency.get("frequency_edges_Hz", [])
	var lines_value: Variant = _model.get("transitions", [])
	var layout_ok: bool = edges_value is Array and lines_value is Array
	var line_memberships: Array[int] = []
	if layout_ok:
		var edges := edges_value as Array
		for index in range(1, edges.size()):
			layout_ok = layout_ok and float(edges[index]) > float(edges[index - 1])
		for line_value: Variant in lines_value as Array:
			if not line_value is Dictionary:
				layout_ok = false
				continue
			var line := line_value as Dictionary
			var nu := float(line.get("frequency_Hz", NAN))
			var memberships: int = 0
			for group in range(edges.size() - 1):
				var inside: bool = nu >= float(edges[group]) and (nu < float(edges[group + 1]) \
						or (group == edges.size() - 2 and nu <= float(edges[group + 1])))
				if inside:
					memberships += 1
			line_memberships.append(memberships)
			layout_ok = layout_ok and memberships == 1
	_record("PM-G1", "frequency groups uniquely contain every line", layout_ok, {
		"line_memberships": line_memberships,
		"group_count": (edges_value as Array).size() - 1 if edges_value is Array else 0,
	})
	var identity_ok: bool = String(_model.get("model_sha256", "")) == MODEL_SHA256 \
			and String(constants.get("constants_sha256", "")).length() == 64 \
			and String(units.get("unit_defaults_sha256", "")).length() == 64 \
			and String(frequency.get("frequency_grid_sha256", "")).length() == 64 \
			and String(source.get("source_record_sha256", "")).length() == 64
	var receipt_parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(
			"res://_diag/physical_matter/model_reference_receipt.json"))
	if receipt_parsed is Dictionary:
		var receipt := receipt_parsed as Dictionary
		identity_ok = identity_ok and bool(receipt.get("passed", false)) \
				and String(receipt.get("model_sha256", "")) == MODEL_SHA256 \
				and int(receipt.get("expected_total", 0)) == (receipt.get("checks", []) as Array).size()
	else:
		identity_ok = false
	_record("PM-G1", "generated bundle and reference receipt identities match", identity_ok, {
		"model_sha256": String(_model.get("model_sha256", "")),
		"frequency_grid_sha256": String(frequency.get("frequency_grid_sha256", "")),
		"atomic_bundle_sha256": String(source.get("source_record_sha256", "")),
		"unit_map_sha256": String(units.get("unit_defaults_sha256", "")),
	})


func _check_conservative_initialization() -> void:
	var levels := _model.get("levels", []) as Array
	var ionization_energy := float((levels[6] as Dictionary).get("excitation_energy_J", 0.0))
	for count in [8, 257, 4096]:
		var inputs := _particle_fixture(count)
		var first := _make_engine(Vector3i(8, 8, 8), Vector3.ONE,
				inputs.positions, inputs.velocities, inputs.accelerations, {})
		var second := _make_engine(Vector3i(8, 8, 8), Vector3.ONE,
				inputs.positions, inputs.velocities, inputs.accelerations, {})
		var ready: bool = bool(first.get("ok", false)) and bool(second.get("ok", false))
		if not ready:
			_record("PM-G2", "%d-particle fixture initializes" % count, false, {
				"first_error": first.get("error", ""), "second_error": second.get("error", "")})
			_teardown(first)
			_teardown(second)
			continue
		var engine: RefCounted = first.engine
		var publication: Dictionary = engine.call("publication")
		var q0 := _floats(publication.material0)
		var q1 := _floats(publication.material1)
		var p0 := _floats(publication.population0)
		var p1 := _floats(publication.population1)
		var cell_volume: float = 8.0 / float(8 * 8 * 8)
		var mass: float = 0.0
		var momentum := Vector3.ZERO
		var positive: bool = true
		for cell in range(8 * 8 * 8):
			var rho: float = q0[cell * 4]
			mass += rho * cell_volume
			momentum += Vector3(q0[cell * 4 + 1], q0[cell * 4 + 2], q0[cell * 4 + 3]) * cell_volume
			if rho > 0.0:
				var kinetic: float = 0.5 * (q0[cell * 4 + 1] * q0[cell * 4 + 1] \
						+ q0[cell * 4 + 2] * q0[cell * 4 + 2] \
						+ q0[cell * 4 + 3] * q0[cell * 4 + 3]) / rho
				var chemical: float = p1[cell * 4 + 2] * ionization_energy \
						/ (float(first.mass_scale) * pow(float(first.velocity_scale), 2.0))
				positive = positive and is_finite(q1[cell * 4]) \
						and q1[cell * 4] - kinetic - chemical > 0.0 \
						and q1[cell * 4 + 1] > 0.0 and q1[cell * 4 + 2] > 0.0
				var pop_sum: float = p0[cell * 4] + p0[cell * 4 + 1] + p0[cell * 4 + 2] \
						+ p0[cell * 4 + 3] + p1[cell * 4] + p1[cell * 4 + 1] + p1[cell * 4 + 2]
				positive = positive and abs(pop_sum - rho) <= 3.0e-6 * maxf(rho, 1.0)
		var expected_momentum: Vector3 = inputs.expected_momentum
		var mass_error: float = abs(mass - 1.0)
		var momentum_error := momentum - expected_momentum
		var momentum_ok: bool = true
		for component in range(3):
			var actual_error: float = abs(momentum_error[component])
			var relative: float = actual_error / maxf(abs(expected_momentum[component]), 1.0e-30)
			momentum_ok = momentum_ok and (relative <= 3.0e-6 or actual_error <= 3.0e-8)
		var repeat_equal: bool = _state_bytes(engine) == _state_bytes(second.engine)
		var passed: bool = mass_error <= 2.0e-6 and momentum_ok and positive and repeat_equal
		_record("PM-G2", "%d-particle conservative initialization" % count, passed, {
			"mass": mass,
			"relative_mass_error": mass_error,
			"momentum": [momentum.x, momentum.y, momentum.z],
			"expected_momentum": [expected_momentum.x, expected_momentum.y, expected_momentum.z],
			"momentum_error": [momentum_error.x, momentum_error.y, momentum_error.z],
			"positive": positive,
			"repeat_byte_identical": repeat_equal,
		})
		_teardown(first)
		_teardown(second)


func _check_hydrodynamics() -> void:
	_check_uniform_flow()
	_check_subfloor_vacuum_interface()
	_check_sod_shock()
	_check_advection_pulse()
	_check_hydrostatic_balance()


func _check_uniform_flow() -> void:
	var fixture := _make_uniform_engine(Vector3i(12, 8, 8), Vector3(1.5, 1.0, 1.0), 1.0, 0.4,
			Vector3(0.2, -0.1, 0.05), {})
	if not bool(fixture.get("ok", false)):
		_record("PM-G3", "uniform-flow fixture initializes", false, {"error": fixture.get("error", "")})
		return
	var before := _state_floats(fixture.engine)
	_direct_hydro(fixture.engine, 0.002, [0, 1, 2])
	var after := _state_floats(fixture.engine)
	var grid := Vector3i(12, 8, 8)
	var max_error: float = 0.0
	var finite_positive: bool = true
	var component_errors := PackedFloat32Array()
	component_errors.resize(16)
	for z in range(2, grid.z - 2):
		for y in range(2, grid.y - 2):
			for x in range(2, grid.x - 2):
				var cell := x + grid.x * (y + grid.y * z)
				for buffer_index in range(4):
					for component in range(4):
						var prior: float = before[buffer_index][cell * 4 + component]
						var current: float = after[buffer_index][cell * 4 + component]


						max_error = maxf(max_error, abs(current - prior) / maxf(abs(prior), 1.0))
						var error: float = abs(current - prior) / maxf(abs(prior), 1.0)
						component_errors[buffer_index * 4 + component] = maxf(
								component_errors[buffer_index * 4 + component], error)
				var rho: float = after[0][cell * 4]
				finite_positive = finite_positive and is_finite(rho) and rho > 0.0 \
						and is_finite(after[1][cell * 4]) and after[1][cell * 4] > 0.0
	_record("PM-G3", "uniform flow remains invariant in the interior",
			max_error <= 3.0e-5 and finite_positive, {
		"maximum_normalized_state_error": max_error,
		"finite_positive": finite_positive,
		"component_errors": Array(component_errors),
	})
	_teardown(fixture)


func _check_subfloor_vacuum_interface() -> void:
	var grid := Vector3i(8, 4, 4)
	var fixture := _make_uniform_engine(
			grid, Vector3(1740.6715, 1075.8168, 2816.4883),
			1.0, 1.0, Vector3.ZERO, {})
	if not bool(fixture.get("ok", false)):
		_record("PM-G3", "sub-floor vacuum interface fixture initializes", false,
				{"error": fixture.get("error", "")})
		return
	var cells := grid.x * grid.y * grid.z
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	q0.resize(cells * 4); q1.resize(cells * 4)
	p0.resize(cells * 4); p1.resize(cells * 4)
	var source_cell := 4 + grid.x * (2 + grid.y * 2)
	var floor_cell := 1
	var source_density := 2.0e-17
	_set_cell(q0, q1, p0, p1, source_cell, source_density, Vector3.ZERO,
			0.66 * source_density, 0.0, _velocity_scale_per_sim(fixture.engine))
	q0[floor_cell * 4] = 0.5e-20
	q1[floor_cell * 4] = -2.0e-24
	p0[floor_cell * 4] = 0.5e-20
	_set_material_state(fixture.engine, q0, q1, p0, p1, PackedFloat32Array())
	_direct_hydro(fixture.engine, 0.05, [0])
	var state := _state_floats(fixture.engine)
	var status_words := _status_ints(fixture.engine)
	var status_flags := ArmMetrics.status_flags(status_words)
	var finite_source := is_finite(state[0][source_cell * 4]) \
			and is_finite(state[1][source_cell * 4]) \
			and state[0][source_cell * 4] > 0.0 \
			and state[1][source_cell * 4] > 0.0
	var vacuum_normalized := true
	for neighbor in [source_cell - 1, source_cell + 1, floor_cell]:
		for buffer_index in range(4):
			for component in range(4):
				vacuum_normalized = vacuum_normalized \
						and state[buffer_index][neighbor * 4 + component] == 0.0
	# The arm's own non-fatal mask (engine STATUS_NONFATAL_MASK = 64 | 512) is the
	# acceptance criterion the engine applies; an all-zero status word was
	# stricter than the arm and failed on non-fatal bookkeeping bits.
	_record("PM-G3", "sub-floor vacuum influx normalizes without rejection",
			_fatal_status(fixture.engine) == 0 and finite_source and vacuum_normalized, {
		"status_flags": status_flags,
		"fatal_status": _fatal_status(fixture.engine),
		"hydro_retries": int(status_words[ArmMetrics.STATUS_WORD_HYDRO_RETRIES]) & 0xffffffff,
		"hydro_rejections": int(status_words[ArmMetrics.STATUS_WORD_HYDRO_REJECTIONS]) & 0xffffffff,
		"source_density": state[0][source_cell * 4],
		"explicit_floor_cell": floor_cell,
		"finite_source": finite_source,
		"vacuum_normalized": vacuum_normalized,
	})
	_teardown(fixture)




func _check_sod_shock() -> void:
	var grid := Vector3i(128, 4, 4)
	var fixture := _make_uniform_engine(grid, Vector3(0.5, 0.5, 0.5), 1.0, 1.0, Vector3.ZERO, {})
	if not bool(fixture.get("ok", false)):
		_record("PM-G3", "Sod fixture initializes", false, {"error": fixture.get("error", "")})
		return
	var q0 := PackedFloat32Array()
	var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array()
	var p1 := PackedFloat32Array()
	q0.resize(grid.x * grid.y * grid.z * 4)
	q1.resize(q0.size()); p0.resize(q0.size()); p1.resize(q0.size())
	var velocity_scale := _velocity_scale_per_sim(fixture.engine)
	for z in range(grid.z):
		for y in range(grid.y):
			for x in range(grid.x):
				var cell := x + grid.x * (y + grid.y * z)
				var rho: float = 1.0 if x < grid.x / 2 else 0.125
				var pressure: float = 1.0 if x < grid.x / 2 else 0.1
				_set_cell(q0, q1, p0, p1, cell, rho, Vector3.ZERO, pressure, 0.0,
						velocity_scale)
	_set_material_state(fixture.engine, q0, q1, p0, p1, PackedFloat32Array())
	for _step in range(200):
		_direct_hydro(fixture.engine, 0.001, [0])
	var state := _state_floats(fixture.engine)
	var reference_cases := _model.get("reference_cases", {}) as Dictionary
	var sod := reference_cases.get("sod_128_t0p2", {}) as Dictionary
	var ref_density := sod.get("density", []) as Array
	var ref_pressure := sod.get("pressure", []) as Array
	var density_error: float = 0.0
	var pressure_error: float = 0.0
	var density: Array[float] = []
	var pressure: Array[float] = []
	var finite_positive: bool = true
	for x in range(grid.x):
		var cell := x + grid.x * (2 + grid.y * 2)
		var rho: float = state[0][cell * 4]
		var momentum: float = state[0][cell * 4 + 1]
		var thermal: float = state[1][cell * 4] - 0.5 * momentum * momentum / maxf(rho, 1.0e-30)
		var press: float = (GAMMA - 1.0) * thermal
		density.append(rho); pressure.append(press)
		density_error += abs(rho - float(ref_density[x])) / float(grid.x)
		pressure_error += abs(press - float(ref_pressure[x])) / float(grid.x)
		finite_positive = finite_positive and is_finite(rho) and rho > 0.0 \
				and is_finite(press) and press > 0.0
	var gpu_shock := _gradient_peak(pressure, 80, 122)
	var ref_shock := _gradient_peak(_array_float(ref_pressure), 80, 122)
	var gpu_contact := _gradient_peak(density, 68, 100)
	var ref_contact := _gradient_peak(_array_float(ref_density), 68, 100)
	var passed: bool = density_error <= 0.035 and pressure_error <= 0.045 \
			and abs(gpu_shock - ref_shock) <= 2 and abs(gpu_contact - ref_contact) <= 2 \
			and finite_positive
	_record("PM-G3", "Sod shock tube matches the frozen HLLC oracle", passed, {
		"l1_density_error": density_error,
		"l1_pressure_error": pressure_error,
		"gpu_shock_cell": gpu_shock,
		"reference_shock_cell": ref_shock,
		"gpu_contact_cell": gpu_contact,
		"reference_contact_cell": ref_contact,
		"finite_positive": finite_positive,
	})
	_teardown(fixture)


func _check_advection_pulse() -> void:
	var grid := Vector3i(16, 16, 16)
	var extent := Vector3.ONE
	var fixture := _make_uniform_engine(grid, extent, 1.0e-8, 1.0e-10, Vector3.ZERO, {})
	if not bool(fixture.get("ok", false)):
		_record("PM-G3", "advection fixture initializes", false, {"error": fixture.get("error", "")})
		return
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	var cells := grid.x * grid.y * grid.z
	q0.resize(cells * 4); q1.resize(cells * 4); p0.resize(cells * 4); p1.resize(cells * 4)
	var velocity := Vector3(0.25, 0.15, 0.1)
	var velocity_scale := _velocity_scale_per_sim(fixture.engine)
	for z in range(grid.z):
		for y in range(grid.y):
			for x in range(grid.x):
				var cell := x + grid.x * (y + grid.y * z)
				var position := _cell_position(Vector3i(x, y, z), grid, extent)
				var radius2 := position.length_squared()
				var rho: float = 1.0e-8 + exp(-radius2 / (2.0 * 0.18 * 0.18))
				_set_cell(q0, q1, p0, p1, cell, rho, velocity, 1.0e-4 * rho, 0.0,
						velocity_scale)
	_set_material_state(fixture.engine, q0, q1, p0, p1, PackedFloat32Array())
	var initial := _mass_center(fixture.engine, grid, extent, 1.0e-8)
	for _step in range(40):
		_direct_hydro(fixture.engine, 0.01, [0, 1, 2])
	var final := _mass_center(fixture.engine, grid, extent, 1.0e-8)
	var expected_center: Vector3 = initial.center + velocity * 0.4
	var cell_width := 2.0 * extent / Vector3(grid)
	var displacement_cells: float = (final.center - expected_center).length() / cell_width.length()
	var mass_error: float = abs(float(final.mass) - float(initial.mass)) / maxf(abs(float(initial.mass)), 1.0e-30)
	var status_ok := _fatal_status(fixture.engine) == 0
	_record("PM-G3", "three-dimensional free advection preserves pulse mass and center",
			mass_error <= 5.0e-6 and displacement_cells <= 0.75 and status_ok, {
		"relative_mass_error": mass_error,
		"center_error_cells": displacement_cells,
		"initial_center": _vec(initial.center),
		"expected_center": _vec(expected_center),
		"final_center": _vec(final.center),
		"fatal_status": _fatal_status(fixture.engine),
	})
	_teardown(fixture)


func _check_hydrostatic_balance() -> void:
	var grid := Vector3i(16, 16, 16)
	var extent := Vector3.ONE
	var fixture := _make_uniform_engine(grid, extent, 1.0, 1.0, Vector3.ZERO, {})
	if not bool(fixture.get("ok", false)):
		_record("PM-G3", "hydrostatic fixture initializes", false, {"error": fixture.get("error", "")})
		return
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	var gravity := PackedFloat32Array()
	var cells := grid.x * grid.y * grid.z
	q0.resize(cells * 4); q1.resize(cells * 4); p0.resize(cells * 4); p1.resize(cells * 4)
	gravity.resize(cells * 4)
	var acceleration := Vector3(0.02, 0.0, 0.0)
	var velocity_scale := _velocity_scale_per_sim(fixture.engine)
	for z in range(grid.z):
		for y in range(grid.y):
			for x in range(grid.x):
				var cell := x + grid.x * (y + grid.y * z)
				var position := _cell_position(Vector3i(x, y, z), grid, extent)
				var rho: float = 1.0
				var pressure: float = 1.0 + rho * acceleration.x * position.x
				_set_cell(q0, q1, p0, p1, cell, rho, Vector3.ZERO, pressure, 0.0,
						velocity_scale)
				gravity[cell * 4] = acceleration.x
				gravity[cell * 4 + 1] = acceleration.y
				gravity[cell * 4 + 2] = acceleration.z
				gravity[cell * 4 + 3] = rho
	_set_material_state(fixture.engine, q0, q1, p0, p1, PackedFloat32Array())
	for _step in range(64):
		_update_buffer(fixture.engine.get("_gravity") as RID, gravity)
		_direct_hydro(fixture.engine, 0.0005, [0, 1, 2])
	var state := _state_floats(fixture.engine)
	var momentum_l1: float = 0.0
	var characteristic: float = 0.0
	for z in range(3, grid.z - 3):
		for y in range(3, grid.y - 3):
			for x in range(3, grid.x - 3):
				var cell := x + grid.x * (y + grid.y * z)
				momentum_l1 += abs(state[0][cell * 4 + 1]) + abs(state[0][cell * 4 + 2]) \
						+ abs(state[0][cell * 4 + 3])
				characteristic += state[0][cell * 4] * sqrt(GAMMA * state[1][cell * 4 + 2])
	var drift: float = momentum_l1 / maxf(characteristic, 1.0e-30)
	_record("PM-G3", "hydrostatic source balance limits momentum drift",
			drift <= 2.0e-4 and _fatal_status(fixture.engine) == 0, {
		"normalized_momentum_drift": drift,
		"fatal_status": _fatal_status(fixture.engine),
	})
	_teardown(fixture)


const LINE_ORACLE_COLLISIONAL_DOMINANCE_THRESHOLD := 1.0


## The CPU reference assumes LTE populations, but the engine's line channel
## only relaxes through collisional excitation/de-excitation and spontaneous
## decay.  Compare group 19 only when electron collisions dominate its
## Ly-alpha spontaneous decay; otherwise retain its measured trace but exclude
## it from the line-channel oracle (free-free/free-bound remain unconditional).
func _line_oracle_scope(reference: Dictionary, density_m3: float) -> Dictionary:
	var kinetics_value: Variant = _model.get("kinetics", {})
	var transitions_value: Variant = _model.get("transitions", [])
	if not kinetics_value is Dictionary or not transitions_value is Array \
			or (transitions_value as Array).is_empty():
		return {
			"eligible": false, "ratio_ne_q21_over_a21": NAN,
			"threshold": LINE_ORACLE_COLLISIONAL_DOMINANCE_THRESHOLD,
			"skip_reason": "line_rate_metadata_unavailable",
		}
	var kinetics := kinetics_value as Dictionary
	var grid_value: Variant = kinetics.get("temperature_grid_K", [])
	var rates_value: Variant = kinetics.get("collisional_transition_rates", [])
	if not grid_value is Array or not rates_value is Array \
			or (grid_value as Array).is_empty() or (rates_value as Array).is_empty():
		return {
			"eligible": false, "ratio_ne_q21_over_a21": NAN,
			"threshold": LINE_ORACLE_COLLISIONAL_DOMINANCE_THRESHOLD,
			"skip_reason": "line_rate_metadata_unavailable",
		}
	var transition_value: Variant = (transitions_value as Array)[0]
	var rate_value: Variant = (rates_value as Array)[0]
	if not transition_value is Dictionary or not rate_value is Dictionary:
		return {
			"eligible": false, "ratio_ne_q21_over_a21": NAN,
			"threshold": LINE_ORACLE_COLLISIONAL_DOMINANCE_THRESHOLD,
			"skip_reason": "line_rate_metadata_unavailable",
		}
	var temperatures := grid_value as Array
	var deexcitation_value: Variant = (rate_value as Dictionary).get(
			"deexcitation_m3_s", [])
	if not deexcitation_value is Array or (deexcitation_value as Array).is_empty():
		return {
			"eligible": false, "ratio_ne_q21_over_a21": NAN,
			"threshold": LINE_ORACLE_COLLISIONAL_DOMINANCE_THRESHOLD,
			"skip_reason": "line_rate_metadata_unavailable",
		}
	var nearest_index := 0
	var nearest_distance := INF
	var temperature := float(reference.get("temperature_K", 0.0))
	for index in range(mini(temperatures.size(), (deexcitation_value as Array).size())):
		var distance := absf(float(temperatures[index]) - temperature)
		if distance < nearest_distance:
			nearest_distance = distance
			nearest_index = index
	var a21 := float((transition_value as Dictionary).get("A_s_inv", 0.0))
	var q21 := float((deexcitation_value as Array)[nearest_index])
	var electron_density := density_m3 * float(reference.get("ion_fraction", 0.0))
	var ratio := electron_density * q21 / maxf(a21, 1.0e-30)
	var eligible := is_finite(ratio) and ratio >= LINE_ORACLE_COLLISIONAL_DOMINANCE_THRESHOLD
	return {
		"eligible": eligible,
		"ratio_ne_q21_over_a21": ratio,
		"electron_density_m3": electron_density,
		"q21_m3_s": q21,
		"a21_s_inv": a21,
		"threshold": LINE_ORACLE_COLLISIONAL_DOMINANCE_THRESHOLD,
		"skip_reason": "" if eligible else "line_collision_not_dominant",
	}


func _check_atomic_emissivity() -> void:
	var cases_value: Variant = (_model.get("reference_cases", {}) as Dictionary).get("thermo_atomic", [])
	if not cases_value is Array:
		_record("PM-G4", "atomic reference cases are available", false, {})
		return
	var cases := cases_value as Array
	var maximum_temperature_error: float = 0.0
	var maximum_pressure_error: float = 0.0
	var maximum_ion_error: float = 0.0
	var maximum_group_error: float = 0.0
	var maximum_bolometric_error: float = 0.0
	var maximum_population_oracle_error: float = 0.0
	var maximum_population_closure_error: float = 0.0
	var maximum_thermo_exchange_error: float = 0.0
	var maximum_radiative_exchange_error: float = 0.0
	var radiative_exchange_probe_cases: Array[Dictionary] = []
	var radiative_exchange_nonzero_cases: int = 0
	var compared_groups: int = 0
	var thermodynamics_written: bool = false
	var worst_group: Dictionary = {}
	var worst_bolometric: Dictionary = {}
	var spectral_cases: Array[Dictionary] = []
	var closure_cases: Array[Dictionary] = []
	var finite_positive: bool = true
	var emission_signal_ok: bool = true
	# The fixture's own dt_sim, used both as its configuration and as the warm
	# pass interval below, so the settle and the oracle share one time unit.
	var fixture_dt := 1.0e-3
	for density in [1.0e6, 1.0e12, 1.0e18]:
		var fixture := _make_uniform_engine(Vector3i(4, 4, 4), Vector3.ONE,
				1.0, 1.0, Vector3.ZERO, {
			"mass_kg_per_sim": M_H * density,
			"dt_sim": fixture_dt,
		})
		if not bool(fixture.get("ok", false)):
			_record("PM-G4", "atomic density fixture initializes", false, {
				"density_m3": density, "error": fixture.get("error", "")})
			continue
		for case_value: Variant in cases:
			if not case_value is Dictionary:
				continue
			var reference := case_value as Dictionary
			if float(reference.get("hydrogen_number_density_m3", 0.0)) != density:
				continue
			var temperature := float(reference.get("temperature_K", 0.0))
			# The packed temperature channel is deliberately scaled away from the
			# reference so the thermodynamic comparison below cannot be satisfied by
			# the fixture echoing its own input back out of the engine.
			var state := _atomic_state(reference, fixture.engine, 1.5)
			_set_material_state(fixture.engine, state.q0, state.q1, state.p0, state.p1,
					state.radiation)
			# TEMPORARY DIAGNOSTIC (RevertMe): publish the coefficients once on the
			# freshly packed state -- mode 4 writes coefficients only, never state --
			# so the receipt carries the group-19 level chain the shader reads both
			# as the fixture packed it and after the solve below.  The decode is
			# inert unless atomic.glsl's LINE_TERM_DIAGNOSTIC is on, so a
			# default-off run changes no gate.
			_direct_atomic(fixture.engine, 4, fixture_dt, false)
			var packed_publication: Dictionary = fixture.engine.call("publication")
			# The packed channels only seed the fixture.  A mode-0 pass at the
			# fixture's own (tiny) dt runs solve_kinetics, so the levels and the
			# electron density the line, free-free, and free-bound terms read are
			# the engine's own rate-solved populations rather than the fixture's
			# hand-packed copy; the 1.5-scaled witness channel above then proves
			# the comparison is not the fixture echoing its own input.  The dt is
			# small enough that the exchange does not move the conserved state.
			_direct_atomic(fixture.engine, 0, fixture_dt, false)
			# Mode 4 publishes coefficients only: it derives its temperature from the
			# conserved energy (atomic.glsl:810-816) but never writes material1[1..2],
			# so it serves the emissivity oracle and nothing else.
			_direct_atomic(fixture.engine, 4, fixture_dt, false)
			var publication: Dictionary = fixture.engine.call("publication")
			var gpu_emission := _floats(publication.emission)
			var expected_emission := _array_float(
					reference.get("post_step_total_group_emissivity_W_m3", []) as Array)
			var expected_populations := _array_float(
					reference.get("post_step_population_number_density_m3", []) as Array)
			var expected_temperature := float(reference.get("post_step_temperature_K", temperature))
			var expected_pressure := float(reference.get("post_step_pressure_Pa", 0.0))
			var expected_ion_fraction := float(reference.get("post_step_ion_fraction", 0.0))
			# TEMPORARY DIAGNOSTIC (RevertMe): shader-side chain decode plus the
			# verifier-side packed and solved level fractions for the same cell 0, so
			# the receipt can attribute the group-19 deficit to the packed state or
			# to the solve.  Both decodes are inert (ordinary opacities, unrelated to
			# the level chain) whenever the shader switch is off, and nothing in this
			# gate consumes them.
			var solved_state := _state_floats(fixture.engine)
			var packed_density := float(reference.get("hydrogen_number_density_m3", 0.0))
			var packed_population_number_density_cell0 := [
					state.p0[0] * packed_density, state.p0[1] * packed_density,
					state.p0[2] * packed_density, state.p0[3] * packed_density,
					state.p1[0] * packed_density, state.p1[1] * packed_density,
					state.p1[2] * packed_density]
			var solved_density_scale := float(publication.density_kg_m3_per_sim) / M_H
			var solved_population_number_density_cell0 := [
					solved_state[2][0] * solved_density_scale,
					solved_state[2][1] * solved_density_scale,
					solved_state[2][2] * solved_density_scale,
					solved_state[2][3] * solved_density_scale,
					solved_state[3][0] * solved_density_scale,
					solved_state[3][1] * solved_density_scale,
					solved_state[3][2] * solved_density_scale]
			var solved_temperature: float = solved_state[1][1]
			var solved_pressure: float = solved_state[1][2]
			var solved_ion_fraction: float = solved_state[3][2] \
					/ maxf(solved_state[0][0], 1.0e-30)
			maximum_temperature_error = maxf(maximum_temperature_error,
					_relative_error(solved_temperature, expected_temperature))
			maximum_pressure_error = maxf(maximum_pressure_error,
					_relative_error(
							solved_pressure * float(publication.energy_density_J_m3_per_sim),
							expected_pressure))
			maximum_ion_error = maxf(maximum_ion_error,
					abs(solved_ion_fraction - expected_ion_fraction))
			for population_index in range(mini(7, expected_populations.size())):
				var expected_fraction := expected_populations[population_index] / maxf(packed_density, 1.0e-30)
				var actual_fraction: float
				if population_index < 4:
					actual_fraction = solved_state[2][population_index]
				else:
					actual_fraction = solved_state[3][population_index - 4]
				maximum_population_oracle_error = maxf(maximum_population_oracle_error,
						abs(actual_fraction - expected_fraction))
			var diagnostic := {
				"line_diagnostic_packed": _line_diagnostic(packed_publication, 19, false),
				"line_diagnostic_solved": _line_diagnostic(publication, 19, false),
				"packed_population_fractions_cell0": [
					state.p0[0], state.p0[1], state.p0[2], state.p0[3],
					state.p1[0], state.p1[1], state.p1[2]],
				"solved_population_fractions_cell0": [
					solved_state[2][0], solved_state[2][1], solved_state[2][2],
					solved_state[2][3], solved_state[3][0], solved_state[3][1],
					solved_state[3][2]],
				"packed_population_number_density_m3_cell0":
					packed_population_number_density_cell0,
				"solved_population_number_density_m3_cell0":
					solved_population_number_density_cell0,
				# These are the exact state-buffer slots written by _atomic_state:
				# p0[1] is n=2, while p1[2] is the ion/electron fraction.
				"packed_state_slots_cell0": {
					"material0_q0": state.q0[0], "material0_q1": state.q1[0],
					"material1_q1": state.q1[1], "material1_q2": state.q1[2],
					"population0_p0_n1": state.p0[0],
					"population0_p0_n2": state.p0[1],
					"population0_p0_n3": state.p0[2],
					"population0_p0_n4": state.p0[3],
					"population1_p1_n5": state.p1[0],
					"population1_p1_n6": state.p1[1],
					"population1_p1_electron": state.p1[2]},
				"mode4_only_population_number_density_m3_cell0":
					packed_population_number_density_cell0,
				"packed_n2_number_density_m3_cell0":
					packed_population_number_density_cell0[1],
				"solved_n2_number_density_m3_cell0":
					solved_population_number_density_cell0[1],
				"solved_density_cell0": solved_state[0][0],
				"packed_radiation_maximum": _maximum_value(
						_floats(packed_publication.radiation)),
				"reference_population_number_density_m3": reference.get(
						"population_number_density_m3", []),
				"reference_ion_fraction": float(reference.get("ion_fraction", 0.0)),
				"publication_time_s_per_sim": float(publication.time_s_per_sim),
				"fixture_dt_sim": fixture_dt,
				"solved_population_sum_cell0": solved_state[2][0] + solved_state[2][1]
					+ solved_state[2][2] + solved_state[2][3] + solved_state[3][0]
					+ solved_state[3][1] + solved_state[3][2],
				# Material density/energy must be nonnegative; momentum components
				# are signed and therefore require finiteness only.
				"solved_material0_finite":
					_finite_material_state(solved_state[0]),
				"solved_material1_finite_nonnegative":
					_finite_nonnegative(solved_state[1]),
				"fatal_status": _fatal_status(fixture.engine),
				"status_values": publication.get("status_values", {}),
			}
			var line_scope := {
				"eligible": true,
				"skip_reason": "post_step_rate_oracle_covers_all_groups",
			}
			var conversion: float = float(state.energy_density) / float(state.time_scale)
			var gpu_bolometric: float = 0.0
			var expected_bolometric: float = 0.0
			for group in range(expected_emission.size()):
				var actual_physical: float = gpu_emission[group] * conversion
				var expected_physical: float = expected_emission[group]
				gpu_bolometric += actual_physical
				expected_bolometric += expected_physical
			# Fixture precondition: an emitting reference case must be compared
			# against a solved state that emits.  A fully empty publication only
			# ever appears as a relative error of 1.0 against the reference
			# bolometric, so it is asserted here as a property of the engine's
			# solved state (a 100 K ground-state case legitimately publishes zero
			# and its reference bolometric is zero, so it is exempt).
			emission_signal_ok = emission_signal_ok \
					and (expected_bolometric <= 0.0 or gpu_bolometric > 0.0)
			var significant: float = expected_bolometric * 1.0e-12
			for group in range(expected_emission.size()):
				if expected_emission[group] > significant:
					var actual_physical: float = gpu_emission[group] * conversion
					var expected_physical: float = expected_emission[group]
					var group_error := _relative_error(actual_physical, expected_physical)
					if group_error > maximum_group_error:
						maximum_group_error = group_error
						worst_group = {
							"temperature_K": temperature, "density_m3": density, "group": group,
							"gpu_W_m3": actual_physical, "reference_W_m3": expected_physical,
						}
					compared_groups += 1
			var oracle_gpu_bolometric: float = 0.0
			var oracle_reference_bolometric: float = 0.0
			for group in range(expected_emission.size()):
				oracle_gpu_bolometric += gpu_emission[group] * conversion
				oracle_reference_bolometric += expected_emission[group]
			var bolometric_error := _relative_error(oracle_gpu_bolometric,
					oracle_reference_bolometric)
			spectral_cases.append({
				"temperature_K": temperature, "density_m3": density,
				"group0_gpu_W_m3": gpu_emission[0] * conversion,
				"group0_reference_W_m3": expected_emission[0],
				"group23_gpu_W_m3": gpu_emission[23] * conversion,
				"group23_reference_W_m3": expected_emission[23],
				"group19_gpu_W_m3": gpu_emission[19] * conversion,
				"group19_reference_W_m3": expected_emission[19],
				"group19_relative_error": _relative_error(
						gpu_emission[19] * conversion, expected_emission[19]),
				"gpu_bolometric_W_m3": gpu_bolometric,
				"reference_bolometric_W_m3": expected_bolometric,
				"line_diagnostic": diagnostic,
				"line_oracle_scope": line_scope,
				"oracle_gpu_bolometric_W_m3": oracle_gpu_bolometric,
				"oracle_reference_bolometric_W_m3": oracle_reference_bolometric,
			})
			if bolometric_error > maximum_bolometric_error:
				maximum_bolometric_error = bolometric_error
				worst_bolometric = {
					"temperature_K": temperature, "density_m3": density,
					"gpu_W_m3": oracle_gpu_bolometric,
					"reference_W_m3": oracle_reference_bolometric,
				}
			# B1: the thermodynamics sub-oracle is driven through the mode-0 source
			# pass, which runs solve_kinetics and refresh_thermodynamics
			# (atomic.glsl:532/617) and rewrites material1[1..2] from the conserved
			# energy plus the solved populations.  `thermodynamics_written` records
			# that at least one case observed an engine-written value rather than the
			# injected hint.
			_direct_atomic(fixture.engine, 0, 1.0e-3, false)
			var current := _state_floats(fixture.engine)
			var recovered_temperature: float = current[1][1]
			thermodynamics_written = thermodynamics_written \
					or _relative_error(recovered_temperature, float(state.temperature_hint)) \
					> 1.0e-3
			finite_positive = finite_positive and _finite_material_state(current[0]) \
					and _finite_nonnegative(current[1]) and _fatal_status(fixture.engine) == 0
			var before_energy: float = _cell_material_radiation_energy(fixture.engine, 0)
			_direct_atomic(fixture.engine, 0, 1.0e-3, false)
			var after := _state_floats(fixture.engine)
			var population_sum: float = after[2][0] + after[2][1] + after[2][2] + after[2][3] \
					+ after[3][0] + after[3][1] + after[3][2]
			maximum_population_closure_error = maxf(maximum_population_closure_error,
					abs(population_sum - after[0][0]))
			# TEMPORARY DIAGNOSTIC (RevertMe): the residual above is a sum, so it
			# cannot name a level on its own; record the per-slot values and the
			# status at this metric's own moment (the third mode-0 pass) so the
			# residual can be attributed, and so `finite_positive`'s source (which
			# channel, and whether a fatal status latched) is on the receipt.
			var closure_publication: Dictionary = fixture.engine.call("publication")
			closure_cases.append({
				"temperature_K": temperature, "density_m3": density,
				"populations": [after[2][0], after[2][1], after[2][2], after[2][3],
					after[3][0], after[3][1], after[3][2]],
				"population_sum": population_sum, "material0": after[0][0],
				"closure_residual": absf(population_sum - after[0][0]),
				"material0_finite": _finite_material_state(after[0]),
				"material1_finite_nonnegative": _finite_nonnegative(after[1]),
				"fatal_status": _fatal_status(fixture.engine),
				"status_values": closure_publication.get("status_values", {}),
			})
			var after_energy: float = _cell_material_radiation_energy(fixture.engine, 0)
			maximum_thermo_exchange_error = maxf(maximum_thermo_exchange_error,
					_relative_error(after_energy, before_energy))
			# The CPU post-step oracle above intentionally uses zero radiation so
			# its kinetics/emissivity comparison is isolated from transport.  A
			# separate nonzero probe exercises the real material-radiation exchange
			# path and checks the paired energy invariant without weakening either
			# oracle.
			var probe_publication: Dictionary = fixture.engine.call("publication")
			var probe_cells := int(fixture.engine.get("_cell_count"))
			var probe_groups := int(probe_publication.groups)
			var probe_angles := int(probe_publication.angles)
			var probe_radiation := PackedFloat32Array()
			probe_radiation.resize(probe_cells * probe_groups * probe_angles)
			probe_radiation.fill(0.0)
			var probe_group := _maximum_group(_floats(probe_publication.opacity),
					probe_cells, probe_groups)
			probe_radiation[_radiation_index(0, probe_group, 0,
					probe_groups, probe_angles)] = BEER_BEAM
			_set_material_state(fixture.engine, current[0], current[1],
					current[2], current[3], probe_radiation)
			_direct_atomic(fixture.engine, 4, 0.0, false)
			var probe_before_total := _material_energy(fixture.engine) \
					+ _radiation_energy(fixture.engine)
			var probe_before_radiation_global := _radiation_energy(fixture.engine)
			var probe_before_radiation_cell := _cell_radiation_energy(fixture.engine, 0)
			var probe_source_before := _ledger_total(fixture.engine, "ledger0", 3)
			var probe_source_before_cell := _ledger_component_at(fixture.engine,
					"ledger0", 0, 3)
			_direct_atomic(fixture.engine, 6, fixture_dt, false)
			var probe_after_total := _material_energy(fixture.engine) \
					+ _radiation_energy(fixture.engine)
			var probe_after_radiation_global := _radiation_energy(fixture.engine)
			var probe_after_radiation_cell := _cell_radiation_energy(fixture.engine, 0)
			var probe_radiation_delta := probe_after_radiation_global \
					- probe_before_radiation_global
			var probe_radiation_delta_cell := probe_after_radiation_cell \
					- probe_before_radiation_cell
			var probe_source_after := _ledger_total(fixture.engine, "ledger0", 3)
			var probe_source_after_cell := _ledger_component_at(fixture.engine,
					"ledger0", 0, 3)
			var probe_source_delta := probe_source_after - probe_source_before
			var probe_source_delta_cell := probe_source_after_cell \
					- probe_source_before_cell
			var probe_total_error := _relative_error(probe_after_total,
					probe_before_total)
			var probe_ledger_residual := absf(probe_source_delta - probe_radiation_delta)
			var probe_ledger_error := probe_ledger_residual / maxf(
					absf(probe_before_total), 1.0)
			var probe_nonzero := absf(probe_radiation_delta) \
					> RADIATIVE_PROBE_MIN_EXCHANGE \
					and absf(probe_source_delta) > RADIATIVE_PROBE_MIN_EXCHANGE
			if probe_nonzero:
				radiative_exchange_nonzero_cases += 1
				maximum_radiative_exchange_error = maxf(
						maximum_radiative_exchange_error,
						maxf(probe_total_error, probe_ledger_error))
			radiative_exchange_probe_cases.append({
				"temperature_K": temperature,
				"density_m3": density,
				"group": probe_group,
				"input_intensity": BEER_BEAM,
				"paired_energy_before": probe_before_total,
				"paired_energy_after": probe_after_total,
				"paired_energy_relative_error": probe_total_error,
				"radiation_delta_global": probe_radiation_delta,
				"radiation_delta_cell0": probe_radiation_delta_cell,
				"source_exchange_ledger_delta_global": probe_source_delta,
				"source_exchange_ledger_delta_cell0": probe_source_delta_cell,
				"source_ledger_relative_error": probe_ledger_error,
				"source_ledger_absolute_residual": probe_ledger_residual,
				"nonzero_exchange": probe_nonzero,
				"fatal_status": _fatal_status(fixture.engine),
			})
			finite_positive = finite_positive and _finite_material_state(current[0]) \
					and _finite_nonnegative(current[1]) and _fatal_status(fixture.engine) == 0
		_teardown(fixture)
	var passed: bool = maximum_temperature_error <= 2.0e-5 \
			and maximum_pressure_error <= 2.0e-5 \
			and maximum_ion_error <= 3.0e-4 \
			and maximum_group_error <= 8.0e-3 \
			and maximum_bolometric_error <= 2.0e-3 \
			and maximum_population_oracle_error <= 3.0e-6 \
			and maximum_population_closure_error <= 3.0e-6 \
			and maximum_thermo_exchange_error <= G4_PAIRED_ENERGY_TOLERANCE \
			and maximum_radiative_exchange_error <= G4_PAIRED_ENERGY_TOLERANCE \
			and radiative_exchange_nonzero_cases > 0 \
			and compared_groups > 0 and finite_positive and thermodynamics_written \
			and emission_signal_ok
	_record("PM-G4", "atomic post-step kinetics, emissivity, and exchange match the CPU oracle", passed, {
		"oracle_state": "post_step_rate_solve",
		"oracle_controls": {
			"dt_sim": fixture_dt,
			"time_s_per_sim": 1.0e-4,
			"radiation_energy": "zero",
			"source_enabled": true,
		},
		"radiative_exchange_controls": {
			"input_intensity": BEER_BEAM,
			"minimum_exchange_abs": RADIATIVE_PROBE_MIN_EXCHANGE,
			"paired_energy_and_ledger_tolerance": G4_PAIRED_ENERGY_TOLERANCE,
			"ledger_comparison": "cell0 source ledger delta versus cell0 radiation-energy delta; global paired energy is the conservation oracle",
		},
		"maximum_temperature_relative_error": maximum_temperature_error,
		"maximum_pressure_relative_error": maximum_pressure_error,
		"maximum_ion_fraction_absolute_error": maximum_ion_error,
		"maximum_significant_group_emissivity_relative_error": maximum_group_error,
		"maximum_bolometric_relative_error": maximum_bolometric_error,
		"maximum_population_oracle_absolute_error": maximum_population_oracle_error,
		"maximum_population_closure_absolute_error": maximum_population_closure_error,
		"maximum_thermodynamic_exchange_relative_error": maximum_thermo_exchange_error,
		"maximum_radiative_exchange_relative_error": maximum_radiative_exchange_error,
		"radiative_exchange_nonzero_cases": radiative_exchange_nonzero_cases,
		"radiative_exchange_probe_cases": radiative_exchange_probe_cases,
		"worst_group": worst_group,
		"worst_bolometric": worst_bolometric,
		"compared_groups": compared_groups,
		"thermodynamics_written_by_mode0": thermodynamics_written,
		"solved_emission_signal_cases_ok": emission_signal_ok,
		"spectral_cases": spectral_cases,
		"closure_attribution": closure_cases,
		"finite_positive": finite_positive,
	})


## Packs one reference case into the engine's conserved channels.  The unit
## conversions come from the engine's own published unit map (B5), and the
## temperature channel is written from `temperature_hint_scale` so the caller
## can prove the engine overwrote it rather than echoing the fixture input.
func _atomic_state(reference: Dictionary, engine: RefCounted,
		temperature_hint_scale: float = 1.0) -> Dictionary:
	var cells: int = int(engine.get("_cell_count"))
	var groups: int = int(engine.get("_group_count"))
	var angles: int = int(engine.get("_angle_count"))
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	var radiation := PackedFloat32Array()
	q0.resize(cells * 4); q1.resize(cells * 4); p0.resize(cells * 4); p1.resize(cells * 4)
	radiation.resize(cells * groups * angles)
	var density := float(reference.get("hydrogen_number_density_m3", 0.0))
	var temperature := float(reference.get("temperature_K", 0.0))
	var ion_fraction := float(reference.get("ion_fraction", 0.0))
	var velocity_scale := _velocity_scale_per_sim(engine)
	var velocity_squared := velocity_scale * velocity_scale
	# rho_sim is 1 for every packed cell, so the physical energy density is
	# exactly the engine's own published unit and the emission conversion uses the
	# engine's own time unit; neither is re-derived here (B5).
	var publication: Dictionary = engine.call("publication")
	var energy_density: float = float(publication.energy_density_J_m3_per_sim)
	var time_scale: float = float(publication.time_s_per_sim)
	var pressure_sim: float = float(reference.get("pressure_Pa", 0.0)) / energy_density
	var populations_value: Variant = reference.get("population_number_density_m3", [])
	var populations := populations_value as Array
	var levels := _model.get("levels", []) as Array
	var chemical: float = 0.0
	for level in range(6):
		var level_record := levels[level] as Dictionary
		chemical += float(populations[level]) / density \
				* float(level_record.get("excitation_energy_J", 0.0)) \
				/ (M_H * velocity_squared)
	chemical += ion_fraction * float((levels[6] as Dictionary).excitation_energy_J) \
			/ (M_H * velocity_squared)
	var temperature_hint := temperature * temperature_hint_scale
	for cell in range(cells):
		q0[cell * 4] = 1.0
		q1[cell * 4] = pressure_sim / (GAMMA - 1.0) + chemical
		q1[cell * 4 + 1] = temperature_hint
		q1[cell * 4 + 2] = pressure_sim
		for level in range(4):
			p0[cell * 4 + level] = float(populations[level]) / density
		p1[cell * 4] = float(populations[4]) / density
		p1[cell * 4 + 1] = float(populations[5]) / density
		p1[cell * 4 + 2] = ion_fraction
	return {
		"q0": q0, "q1": q1, "p0": p0, "p1": p1, "radiation": radiation,
		"pressure_sim": pressure_sim, "energy_density": energy_density,
		"time_scale": time_scale, "temperature_hint": temperature_hint,
	}

func _direct_atomic(engine: RefCounted, mode: int, dt: float,
		toggle_radiation: bool) -> void:
	var compute_list := _rd.compute_list_begin()
	engine.call("_record_atomic", compute_list, mode, dt)
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	if toggle_radiation:
		engine.set("_radiation_role_b", not bool(engine.get("_radiation_role_b")))

const LINE_DIAGNOSTIC_SLOTS := 31
const LINE_DIAGNOSTIC_LABELS := [
	"population_n1_fraction", "population_n2_fraction", "population_n3_fraction",
	"population_n4_fraction", "population_n5_fraction", "population_n6_fraction",
	"population_electron_fraction", "density_scale_per_m3",
	"n2_number_density_m3", "temperature_K", "line_group_fraction",
	"line_center_Hz", "line_a_s_inv", "line_lower_level", "line_upper_level",
	"line_branch", "line_photon_energy_J", "one_plus_dt_times_a", "dt_sim",
	"time_s_per_sim", "collisional_up_coefficient_m3_s",
	"collisional_down_coefficient_m3_s", "collisional_up_rate_s",
	"collisional_down_rate_s", "line_term_W_m3", "published_group_emission",
	"group_index", "cell_index", "group_lower_edge_Hz", "group_upper_edge_Hz",
	"predicted_one_step_divisor",
]

## TEMPORARY DIAGNOSTIC (RevertMe): decode the group-slot diagnostic slice written
## by the shader's LINE_TERM_DIAGNOSTIC dump.  The caller must explicitly pass
## enabled=true after confirming that the shader switch is enabled; ordinary
## opacity values are never presented as labelled diagnostic slots.
func _line_diagnostic(publication: Dictionary, group: int,
		enabled: bool = false) -> Dictionary:
	var groups: int = int(publication.get("groups", 0))
	var opacity := _floats(publication.opacity)
	var cells: int = opacity.size() / groups if groups > 0 else 0
	if not enabled:
		return {"enabled": false, "group": group, "group_count": groups,
			"cell_count": cells, "cells": []}
	var entries: Array[Dictionary] = []
	for slot in range(LINE_DIAGNOSTIC_SLOTS):
		var cell := slot + 1
		var index := cell * groups + group
		if cells <= cell or index >= opacity.size():
			break
		entries.append({"slot": slot, "label": LINE_DIAGNOSTIC_LABELS[slot],
				"cell": cell, "value": opacity[index]})
	return {"enabled": true, "group": group, "group_count": groups,
		"cell_count": cells, "cells": entries}


func _direct_transport(engine: RefCounted, dt: float, include_escape: bool) -> bool:
	if include_escape:
		_direct_atomic(engine, 2, dt, false)
	var compute_list := _rd.compute_list_begin()
	engine.call("_record_transport", compute_list, dt)
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	var flags := ArmMetrics.status_flags(_status_ints(engine))
	# 131072 is STATUS_STEP_REJECTED: the transport pass must specifically have
	# rejected the step, so this is deliberately narrower than status_is_fatal.
	if (flags & 131072) != 0:
		return false
	engine.set("_radiation_role_b", not bool(engine.get("_radiation_role_b")))
	return true


func _radiation_index(cell: int, group: int, angle: int,
		groups: int, angles: int) -> int:
	return (cell * groups + group) * angles + angle


func _nearest_ordinate(engine: RefCounted, target: Vector3) -> int:
	var publication: Dictionary = engine.call("publication")
	var ordinates := _floats(publication.ordinates)
	var desired := target.normalized()
	var best := 0
	var score := -INF
	for angle in range(int(publication.angles)):
		var direction := Vector3(ordinates[angle * 4], ordinates[angle * 4 + 1],
				ordinates[angle * 4 + 2])
		var current := direction.dot(desired)
		if current > score:
			score = current
			best = angle
	return best


func _radiation_energy(engine: RefCounted) -> float:
	var publication: Dictionary = engine.call("publication")
	var radiation := _floats(publication.radiation)
	var ordinates := _floats(publication.ordinates)
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var sum := 0.0
	for cell in range(int(engine.get("_cell_count"))):
		for group in range(groups):
			for angle in range(angles):
				sum += ordinates[angle * 4 + 3] * radiation[
						_radiation_index(cell, group, angle, groups, angles)]
	var extents: Vector3 = publication.extents
	var volume := 8.0 * extents.x * extents.y * extents.z \
			/ float(int(engine.get("_cell_count")))
	return sum * volume


func _radiation_energy_for(engine: RefCounted, group: int, angle: int) -> float:
	var publication: Dictionary = engine.call("publication")
	var radiation := _floats(publication.radiation)
	var ordinates := _floats(publication.ordinates)
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var sum := 0.0
	for cell in range(int(engine.get("_cell_count"))):
		sum += ordinates[angle * 4 + 3] * radiation[
				_radiation_index(cell, group, angle, groups, angles)]
	var extents: Vector3 = publication.extents
	var volume := 8.0 * extents.x * extents.y * extents.z \
			/ float(int(engine.get("_cell_count")))
	return sum * volume


func _radiation_centroid(engine: RefCounted, group: int, angle: int) -> Vector3:
	var publication: Dictionary = engine.call("publication")
	var radiation := _floats(publication.radiation)
	var ordinates := _floats(publication.ordinates)
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var grid: Vector3i = publication.grid
	var extents: Vector3 = publication.extents
	var total := 0.0
	var weighted := Vector3.ZERO
	for z in range(grid.z):
		for y in range(grid.y):
			for x in range(grid.x):
				var cell := x + grid.x * (y + grid.y * z)
				var energy := ordinates[angle * 4 + 3] * radiation[
						_radiation_index(cell, group, angle, groups, angles)]
				total += energy
				weighted += energy * _cell_position(Vector3i(x, y, z), grid, extents)
	return weighted / maxf(total, 1.0e-30)


## Reconstructs the two scalar brackets that mode 6 applies after its
## coefficient/source update.  `emission_scale` is the shader's available-energy
## limiter; `lambda_expected_unity` proves the full exchange stays above the
## thermal floor, so the formal source oracle may use lambda = 1 explicitly.
func _slab_transfer_scale_oracle(engine: RefCounted, publication: Dictionary,
		state: Array[PackedFloat32Array], opacity: PackedFloat32Array,
		emission: PackedFloat32Array, scattering: float, dt: float) -> Dictionary:
	var four_pi := 4.0 * PI
	var weights_value: Variant = (_model.get("frequency_grid", {}) as Dictionary) \
			.get("ordinate_weights_sr", [])
	var ordinate_weight_sum := 0.0
	if weights_value is Array:
		for weight in weights_value as Array:
			ordinate_weight_sum += float(weight)
	var groups := int(publication.groups)
	var c_reduced := float(publication.c_reduced_sim)
	var emission_gain := 0.0
	for group in range(groups):
		var absorption := maxf(opacity[group] - scattering, 0.0)
		if absorption > 1.0e-30:
			var tau := minf(c_reduced * absorption * dt, 80.0)
			emission_gain += ordinate_weight_sum * emission[group] \
					* (1.0 - exp(-tau)) \
					/ (four_pi * c_reduced * absorption)
		else:
			emission_gain += ordinate_weight_sum * emission[group] * dt / four_pi
	var material0 := state[0]
	var material1 := state[1]
	var population0 := state[2]
	var population1 := state[3]
	var density := material0[0]
	var kinetic := 0.0
	if density > float(engine.get("_density_floor")):
		kinetic = 0.5 * (material0[1] * material0[1]
				+ material0[2] * material0[2] + material0[3] * material0[3]) / density
	var velocity_scale := float(publication.length_m_per_sim) \
			/ maxf(float(publication.time_s_per_sim), 1.0e-30)
	var chemical := 0.0
	var levels_value: Variant = _model.get("levels", [])
	if levels_value is Array:
		var levels := levels_value as Array
		for level in range(mini(7, levels.size())):
			var descriptor: Variant = levels[level]
			if descriptor is Dictionary:
				var population := population0[level] if level < 4 \
						else population1[level - 4]
				chemical += float(population) \
						* float((descriptor as Dictionary).get("excitation_energy_J", 0.0)) \
						/ (M_H * velocity_scale * velocity_scale)
	var gamma := float(engine.get("_gamma_gas"))
	var pressure_floor := float(engine.get("_pressure_floor"))
	var available_energy := maxf(material1[0] - kinetic - chemical
			- pressure_floor / (gamma - 1.0), 0.0)
	var emission_scale := 1.0 if emission_gain <= 0.0 \
			else clampf(available_energy / emission_gain, 0.0, 1.0)
	var delta_energy := emission_gain * emission_scale
	var energy_scale := maxf(absf(material1[0]), absf(kinetic) + absf(chemical))
	var thermal_floor := maxf(pressure_floor / (gamma - 1.0),
			1024.0 * 1.1920928955078125e-7 * energy_scale)
	var thermal_after_full_exchange := material1[0] - delta_energy \
			- kinetic - chemical
	return {
		"ordinate_weight_sum_sr": ordinate_weight_sum,
		"emission_gain": emission_gain,
		"available_energy": available_energy,
		"emission_scale": emission_scale,
		"delta_energy": delta_energy,
		"thermal_floor": thermal_floor,
		"thermal_after_full_exchange": thermal_after_full_exchange,
		"lambda_expected_unity": is_finite(thermal_after_full_exchange)
			and thermal_after_full_exchange >= thermal_floor,
	}
	
## Largest value in a published coefficient buffer.  A fixture precondition uses
## this because an all-zero buffer is an absent signal, not a small one.  Every
## coefficient the shader publishes is non-negative by construction
## (atomic.glsl:577-580 clamps emission, absorption, and scattering at zero), so
## a signed maximum is the same reading as an unsigned one here and cannot let an
## all-negative buffer pass as "no emission".
func _maximum_value(values: PackedFloat32Array) -> float:
	var maximum := 0.0
	for value in values:
		maximum = maxf(maximum, value)
	return maximum


## Reduces across every cell of a `cell * groups + group` coefficient buffer
## (`group_index`, cassi_physical_matter_atomic.glsl:123).  Reading only cell 0's
## row could name a group that is not the dominant one anywhere else.
func _maximum_group(values: PackedFloat32Array, cells: int, groups: int) -> int:
	assert(cells > 0 and groups > 0 and values.size() == cells * groups)
	var best := 0
	var best_value := -INF
	for index in range(values.size()):
		if values[index] > best_value:
			best_value = values[index]
			best = index % groups
	return best


func _material_energy(engine: RefCounted) -> float:
	var publication: Dictionary = engine.call("publication")
	var material := _floats(publication.material1)
	var extents: Vector3 = publication.extents
	var volume := 8.0 * extents.x * extents.y * extents.z \
			/ float(int(engine.get("_cell_count")))
	var sum := 0.0
	for cell in range(int(engine.get("_cell_count"))):
		sum += material[cell * 4] * volume
	return sum


func _ledger_total(engine: RefCounted, name: String, component: int) -> float:
	var publication: Dictionary = engine.call("publication")
	var values := _floats(publication[name])
	var extents: Vector3 = publication.extents
	var volume := 8.0 * extents.x * extents.y * extents.z \
			/ float(int(engine.get("_cell_count")))
	var sum := 0.0
	for cell in range(int(engine.get("_cell_count"))):
		sum += values[cell * 4 + component] * volume
	return sum


func _material_momentum_from_values(engine: RefCounted,
		values: PackedFloat32Array) -> Vector3:
	var publication: Dictionary = engine.call("publication")
	var extents: Vector3 = publication.extents
	var volume := 8.0 * extents.x * extents.y * extents.z \
			/ float(int(engine.get("_cell_count")))
	var sum := Vector3.ZERO
	for cell in range(int(engine.get("_cell_count"))):
		var offset := cell * 4
		sum += Vector3(values[offset + 1], values[offset + 2], values[offset + 3]) * volume
	return sum


func _material_momentum(engine: RefCounted) -> Vector3:
	var publication: Dictionary = engine.call("publication")
	return _material_momentum_from_values(engine, _floats(publication.material0))
func _ledger_vector_total(engine: RefCounted, name: String) -> Vector3:
	var publication: Dictionary = engine.call("publication")
	var values := _floats(publication[name])
	var extents: Vector3 = publication.extents
	var volume := 8.0 * extents.x * extents.y * extents.z \
			/ float(int(engine.get("_cell_count")))
	var sum := Vector3.ZERO
	for cell in range(int(engine.get("_cell_count"))):
		var offset := cell * 4
		sum += Vector3(values[offset], values[offset + 1], values[offset + 2]) * volume
	return sum


func _total_material_mass(engine: RefCounted) -> float:
	var publication: Dictionary = engine.call("publication")
	var values := _floats(publication.material0)
	var extents: Vector3 = publication.extents
	var volume := 8.0 * extents.x * extents.y * extents.z \
			/ float(int(engine.get("_cell_count")))
	var sum := 0.0
	for cell in range(int(engine.get("_cell_count"))):
		sum += values[cell * 4] * volume
	return sum


func _physical_state_bytes(engine: RefCounted) -> String:
	var joined := PackedByteArray()
	for name in [
			"_material0_a", "_material1_a", "_population0_a", "_population1_a",
			"_material0_b", "_material1_b", "_population0_b", "_population1_b",
			"_radiation_a", "_radiation_b", "_opacity", "_emission",
			"_ledger0", "_ledger1", "_ledger2", "_gravity", "_hydro_debug",
	]:
		joined.append_array(_rd.buffer_get_data(engine.get(name) as RID))
	return Marshalls.raw_to_base64(joined)

func _cell_material_radiation_energy(engine: RefCounted, cell: int) -> float:
	var publication: Dictionary = engine.call("publication")
	var material := _floats(publication.material1)
	var radiation := _floats(publication.radiation)
	var ordinates := _floats(publication.ordinates)
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var total: float = material[cell * 4]
	for group in range(groups):
		for angle in range(angles):
			total += ordinates[angle * 4 + 3] * radiation[(cell * groups + group) * angles + angle]
	return total

func _cell_radiation_energy(engine: RefCounted, cell: int) -> float:
	var publication: Dictionary = engine.call("publication")
	var radiation := _floats(publication.radiation)
	var ordinates := _floats(publication.ordinates)
	var groups: int = int(publication.groups)
	var angles: int = int(publication.angles)
	var total := 0.0
	for group in range(groups):
		for angle in range(angles):
			total += ordinates[angle * 4 + 3] * radiation[
					_radiation_index(cell, group, angle, groups, angles)]
	return total


func _ledger_component_at(engine: RefCounted, name: String,
		cell: int, component: int) -> float:
	var publication: Dictionary = engine.call("publication")
	return _floats(publication[name])[cell * 4 + component]



func _relative_error(actual: float, expected: float) -> float:
	return abs(actual - expected) / maxf(abs(expected), 1.0e-30)


func _finite_nonnegative(values: PackedFloat32Array) -> bool:
	for value in values:
		if not is_finite(value) or value < 0.0:
			return false
	return true


func _finite_material_state(values: PackedFloat32Array) -> bool:
	if values.size() % 4 != 0:
		return false
	for cell in range(values.size() / 4):
		var offset := cell * 4
		if not is_finite(values[offset]) or values[offset] < 0.0:
			return false
		for component in range(1, 4):
			if not is_finite(values[offset + component]):
				return false
	return true


func _particle_fixture(count: int) -> Dictionary:
	var positions := PackedFloat32Array()
	var velocities := PackedFloat32Array()
	var accelerations := PackedFloat32Array()
	positions.resize(count * 4); velocities.resize(count * 4); accelerations.resize(count * 4)
	var total_mass: float = 0.0
	var total_momentum := Vector3.ZERO
	for index in range(count):
		var u: float = float((index * 73 + 19) % 997) / 996.0
		var v: float = float((index * 193 + 47) % 991) / 990.0
		var w: float = float((index * 389 + 71) % 983) / 982.0
		var position := Vector3(2.0 * u - 1.0, 2.0 * v - 1.0, 2.0 * w - 1.0)
		if index < 8:
			position = Vector3(-1.0 if (index & 1) == 0 else 1.0,
					-1.0 if (index & 2) == 0 else 1.0,
					-1.0 if (index & 4) == 0 else 1.0)
		elif index % 31 == 0:
			position.x = 0.0
		elif index % 37 == 0:
			position.y = 0.25
		elif index % 41 == 0:
			position.z = -0.5
		var velocity := Vector3(0.21 * sin(float(index) * 0.37),
				0.17 * cos(float(index) * 0.23), 0.13 * sin(float(index) * 0.11 + 0.4))
		var mass: float = 0.5 + float((index * 29 + 3) % 101) / 100.0
		positions[index * 4] = position.x; positions[index * 4 + 1] = position.y
		positions[index * 4 + 2] = position.z; positions[index * 4 + 3] = mass
		velocities[index * 4] = velocity.x; velocities[index * 4 + 1] = velocity.y
		velocities[index * 4 + 2] = velocity.z
		total_mass += mass
		total_momentum += mass * velocity
	return {
		"positions": positions, "velocities": velocities, "accelerations": accelerations,
		"expected_momentum": total_momentum / total_mass,
	}


func _make_uniform_engine(grid: Vector3i, extents: Vector3, rho: float, pressure: float,
		velocity: Vector3, overrides: Dictionary) -> Dictionary:
	var positions := PackedFloat32Array([0.0, 0.0, 0.0, 1.0])
	var velocities := PackedFloat32Array([velocity.x, velocity.y, velocity.z, 0.0])
	var accelerations := PackedFloat32Array([0.0, 0.0, 0.0, 0.0])
	var result := _make_engine(grid, extents, positions, velocities, accelerations, overrides)
	if not bool(result.get("ok", false)):
		return result
	var cells: int = grid.x * grid.y * grid.z
	var q0 := PackedFloat32Array(); var q1 := PackedFloat32Array()
	var p0 := PackedFloat32Array(); var p1 := PackedFloat32Array()
	q0.resize(cells * 4); q1.resize(cells * 4); p0.resize(cells * 4); p1.resize(cells * 4)
	var velocity_scale := _velocity_scale_per_sim(result.engine)
	for cell in range(cells):
		_set_cell(q0, q1, p0, p1, cell, rho, velocity, pressure, 0.0, velocity_scale)
	_set_material_state(result.engine, q0, q1, p0, p1, PackedFloat32Array())
	return result


func _make_engine(grid: Vector3i, extents: Vector3, positions: PackedFloat32Array,
		velocities: PackedFloat32Array, accelerations: PackedFloat32Array,
		overrides: Dictionary) -> Dictionary:
	var count: int = positions.size() / 4
	var total_mass: float = 0.0
	for index in range(count):
		total_mass += positions[index * 4 + 3]
	var pos_rid := _rd.storage_buffer_create(positions.size() * 4, positions.to_byte_array())
	var vel_rid := _rd.storage_buffer_create(velocities.size() * 4, velocities.to_byte_array())
	var acc_rid := _rd.storage_buffer_create(accelerations.size() * 4, accelerations.to_byte_array())
	var engine: RefCounted = ENGINE.new()
	var cfg := {
		"model_path": MODEL_PATH,
		"model_sha256": MODEL_SHA256,
		"grid": grid,
		"extents": extents,
		"center": Vector3.ZERO,
		"particle_count": count,
		"total_particle_mass": total_mass,
		"cadence_steps": 1,
		"dt_sim": 0.001,
		"initial_temperature_K": 8000.0,
		"length_m_per_sim": 1.0,
		"time_s_per_sim": 0.0001,
		"mass_kg_per_sim": M_H * 1.0e12,
		"reduced_light_fraction": 1.0e-8,
		"tracer_blend": 0.0,
	}
	cfg.merge(overrides, true)
	var prepared: bool = bool(engine.call("prepare", cfg))
	var initialized: bool = prepared and bool(engine.call("initialize", _rd, false, {}, pos_rid, vel_rid, acc_rid))
	return {
		"ok": initialized,
		"error": "" if initialized else String(engine.call("last_error")),
		"engine": engine,
		"inputs": [pos_rid, vel_rid, acc_rid],
		"mass_scale": float(cfg.mass_kg_per_sim),
		"velocity_scale": _velocity_scale_per_sim(engine),
	}


## The engine's own sim-to-SI velocity conversion
## (`_velocity_m_s_per_sim = _length_m_per_sim / _time_s_per_sim`,
## cassi_physical_matter_engine.gd:235), read back from the published unit map so
## every fixture packer shares one convention instead of re-deriving it or
## hardcoding its square.
func _velocity_scale_per_sim(engine: RefCounted) -> float:
	var publication: Dictionary = engine.call("publication")
	return float(publication.length_m_per_sim) / float(publication.time_s_per_sim)


func _set_cell(q0: PackedFloat32Array, q1: PackedFloat32Array,
		p0: PackedFloat32Array, p1: PackedFloat32Array, cell: int,
		rho: float, velocity: Vector3, pressure: float, ion_fraction: float,
		velocity_scale: float) -> void:
	var momentum := rho * velocity
	q0[cell * 4] = rho; q0[cell * 4 + 1] = momentum.x
	q0[cell * 4 + 2] = momentum.y; q0[cell * 4 + 3] = momentum.z
	q1[cell * 4 + 1] = pressure / maxf(rho * (1.0 + ion_fraction), 1.0e-30) \
			* M_H * velocity_scale * velocity_scale / K_B
	q1[cell * 4] = pressure / (GAMMA - 1.0) + 0.5 * rho * velocity.length_squared()
	q1[cell * 4 + 2] = pressure
	p0[cell * 4] = rho * (1.0 - ion_fraction)
	p1[cell * 4 + 2] = rho * ion_fraction


func _set_material_state(engine: RefCounted, q0: PackedFloat32Array, q1: PackedFloat32Array,
		p0: PackedFloat32Array, p1: PackedFloat32Array, radiation: PackedFloat32Array) -> void:
	for name in ["_material0_a", "_material0_b"]:
		_update_buffer(engine.get(name) as RID, q0)
	for name in ["_material1_a", "_material1_b"]:
		_update_buffer(engine.get(name) as RID, q1)
	for name in ["_population0_a", "_population0_b"]:
		_update_buffer(engine.get(name) as RID, p0)
	for name in ["_population1_a", "_population1_b"]:
		_update_buffer(engine.get(name) as RID, p1)
	if not radiation.is_empty():
		for name in ["_radiation_a", "_radiation_b"]:
			_update_buffer(engine.get(name) as RID, radiation)
	var zero_status := PackedByteArray(); zero_status.resize(64); zero_status.fill(0)
	_rd.buffer_update(engine.get("_status") as RID, 0, zero_status.size(), zero_status)
	for name in ["_ledger0", "_ledger1", "_ledger2"]:
		var rid := engine.get(name) as RID
		var zero := PackedByteArray(); zero.resize(_rd.buffer_get_data(rid).size()); zero.fill(0)
		_rd.buffer_update(rid, 0, zero.size(), zero)
	engine.set("_material_role_b", false)
	engine.set("_radiation_role_b", false)


func _direct_hydro(engine: RefCounted, dt: float, axes: Array[int]) -> void:
	for axis in axes:
		var compute_list := _rd.compute_list_begin()
		engine.call("_record_hydro", compute_list, axis, dt)
		_rd.compute_list_end()
		_rd.submit(); _rd.sync()
		engine.set("_material_role_b", not bool(engine.get("_material_role_b")))


func _mass_center(engine: RefCounted, grid: Vector3i, extent: Vector3,
		background: float) -> Dictionary:
	var state := _state_floats(engine)
	var mass: float = 0.0
	var weighted := Vector3.ZERO
	for z in range(grid.z):
		for y in range(grid.y):
			for x in range(grid.x):
				var cell := x + grid.x * (y + grid.y * z)
				var excess: float = maxf(state[0][cell * 4] - background, 0.0)
				mass += excess
				weighted += excess * _cell_position(Vector3i(x, y, z), grid, extent)
	return {"mass": mass, "center": weighted / maxf(mass, 1.0e-30)}


func _cell_position(cell: Vector3i, grid: Vector3i, extent: Vector3) -> Vector3:
	return -extent + (Vector3(cell) + Vector3(0.5, 0.5, 0.5)) * (2.0 * extent / Vector3(grid))


func _state_floats(engine: RefCounted) -> Array[PackedFloat32Array]:
	var publication: Dictionary = engine.call("publication")
	return [
		_floats(publication.material0), _floats(publication.material1),
		_floats(publication.population0), _floats(publication.population1),
	]


func _state_bytes(engine: RefCounted) -> String:
	var publication: Dictionary = engine.call("publication")
	var joined := PackedByteArray()
	for key in ["material0", "material1", "population0", "population1", "radiation"]:
		joined.append_array(_rd.buffer_get_data(publication[key] as RID))
	return Marshalls.raw_to_base64(joined)


func _floats(rid_value: Variant) -> PackedFloat32Array:
	return _rd.buffer_get_data(rid_value as RID).to_float32_array()


func _update_buffer(rid: RID, values: PackedFloat32Array) -> void:
	var bytes := values.to_byte_array()
	_rd.buffer_update(rid, 0, bytes.size(), bytes)


## The fatal-flag policy lives in the shared arm-metrics module so the two
## acceptance arms cannot drift apart.
func _fatal_status(engine: RefCounted) -> int:
	return ArmMetrics.fatal_status_bits(ArmMetrics.status_flags(_status_ints(engine)))


func _status_ints(engine: RefCounted) -> PackedInt32Array:
	return _rd.buffer_get_data(engine.get("_status") as RID).to_int32_array()


func _status_max_v_over_c(engine: RefCounted) -> float:
	var floats := _rd.buffer_get_data(engine.get("_status") as RID).to_float32_array()
	var index := ArmMetrics.STATUS_FLOAT_MAX_V_OVER_C
	return float(floats[index]) if floats.size() > index else -1.0


func _gradient_peak(values: Array[float], start: int, finish: int) -> int:
	var best: int = start
	var magnitude: float = -1.0
	for index in range(maxi(start, 1), mini(finish, values.size() - 1)):
		var candidate: float = abs(values[index + 1] - values[index - 1])
		if candidate > magnitude:
			magnitude = candidate
			best = index
	return best


func _array_float(values: Array) -> Array[float]:
	var result: Array[float] = []
	for value: Variant in values:
		result.append(float(value))
	return result


func _vec(value: Vector3) -> Array[float]:
	return [value.x, value.y, value.z]


func _teardown(context: Dictionary) -> void:
	var engine_value: Variant = context.get("engine", null)
	if engine_value is RefCounted:
		(engine_value as RefCounted).call("shutdown")
	for rid_value: Variant in context.get("inputs", []) as Array:
		var rid := rid_value as RID
		if rid.is_valid():
			_rd.free_rid(rid)


func _record(gate: String, name: String, passed: bool, metrics: Dictionary) -> void:
	var row := {"gate": gate, "name": name, "passed": passed, "metrics": metrics}
	_checks.append(row)
	if not passed:
		_failures += 1
	print("[PHYSICAL-MATTER] %s: %s — %s" % ["PASS" if passed else "FAIL", gate, name])


func _finish() -> void:
	var elapsed_ms: float = float(Time.get_ticks_usec() - _started_usec) / 1000.0
	var receipt := {
		"schema": "cassi-physical-matter-engine-verification-v1",
		"timestamp_utc": Time.get_datetime_string_from_system(true),
		"model_sha256": MODEL_SHA256,
		"device": RenderingServer.get_video_adapter_name(),
		"checks": _checks,
		"passed": _failures == 0,
		"failure_count": _failures,
		"elapsed_ms": elapsed_ms,
	}
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(RECEIPT_PATH.get_base_dir()))
	var file := FileAccess.open(RECEIPT_PATH, FileAccess.WRITE)
	if file != null:
		file.store_string(JSON.stringify(receipt, "  ") + "\n")
		file.close()
	print("PHYSICAL MATTER ENGINE RESULT: %s (%d/%d checks)" % [
		"PASS" if _failures == 0 else "FAIL", _checks.size() - _failures, _checks.size()])
	if _rd != null:
		_rd.free()
	get_tree().quit(0 if _failures == 0 else 1)
