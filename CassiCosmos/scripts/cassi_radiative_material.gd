class_name CassiRadiativeMaterial
extends RefCounted
## Validation and immutable descriptors for prescribed spectral material.
## This component owns no RenderingDevice resources and never mutates CassiSim.

const SCHEMA_MAJOR: int = 1
const REFERENCE_PATH: String = "res://research/presentation/reference/physical_radiation_reference.json"
const REFERENCE_FILE_SHA256: String = "694a8e676c04b5fe4ce5b96b6482b7b4f37dc2013489a3b7a9c4b3c6fb28b153"
const OBSERVER_PATH: String = "res://research/presentation/reference/CIE_xyz_1931_2deg.csv"
const OBSERVER_SHA256: String = "fa663e3535a7e0763a745993a1f0a192eb0275ac46ad2d1befd7626841e713c1"
const SUPPORTED_CAPABILITIES: Array[String] = [
	"one_way_emission_absorption",
	"frozen_state_formal_solution",
]
const COUPLED_REQUIREMENTS: Array[String] = [
	"native_material_mapping",
	"canonical_extensive_state",
	"equation_of_state",
	"accepted_step_thermal_transport",
	"conservative_geometry_remap",
	"radiation_energy_momentum_state",
	"paired_matter_radiation_exchange",
	"qualified_moving_transport",
	"complete_physical_checkpoint",
]
const COUPLED_ENGINE_CAPABILITIES: Array[String] = [
	"supplied_material_mapping",
	"canonical_extensive_state",
	"ideal_monatomic_eos",
	"accepted_step_affine_thermal_work",
	"implicit_rest_frame_group_exchange",
	"moving_multigroup_isotropic_affine",
	"complete_physical_checkpoint",
]
const COUPLED_FREQUENCY_FRAME: String = "material_rest_frame"
const COUPLED_RECONSTRUCTION: String = "piecewise_constant"
const COUPLED_CLOSURE: String = "isotropic"
const COUPLED_OUTER_POLICY: String = "open_ledger"
const COUPLED_OPERATOR_ORDER: String = "affine_frequency_then_implicit_source"
const C_LIGHT_M_S: float = 299792458.0


var _bundle: Dictionary = {}
var _last_error: String = ""


func load_reference() -> bool:
	_bundle = {}
	_last_error = ""
	var reference_bytes: PackedByteArray = FileAccess.get_file_as_bytes(REFERENCE_PATH)
	if reference_bytes.is_empty():
		return _fail("reference fixture is missing or empty")
	if _sha256(reference_bytes) != REFERENCE_FILE_SHA256:
		return _fail("reference fixture SHA-256 mismatch")
	var observer_bytes: PackedByteArray = FileAccess.get_file_as_bytes(OBSERVER_PATH)
	if observer_bytes.is_empty() or _sha256(observer_bytes) != OBSERVER_SHA256:
		return _fail("CIE observer SHA-256 mismatch")
	var parsed: Variant = JSON.parse_string(reference_bytes.get_string_from_utf8())
	if not parsed is Dictionary:
		return _fail("reference fixture is not a JSON object")
	var candidate: Dictionary = parsed
	var validation: Dictionary = validate_bundle(candidate, SUPPORTED_CAPABILITIES)
	if not bool(validation.get("ok", false)):
		return _fail(String(validation.get("error", "reference validation failed")))
	_bundle = candidate.duplicate(true)
	return true


func is_ready() -> bool:
	return not _bundle.is_empty() and _last_error.is_empty()


func last_error() -> String:
	return _last_error


func bundle() -> Dictionary:
	return _bundle.duplicate(true)


func model() -> Dictionary:
	return _bundle.get("model", {}).duplicate(true)


func spectral_grid() -> Dictionary:
	return _bundle.get("selected_layout", {}).duplicate(true)


func prescribed_snapshot() -> Dictionary:
	return _bundle.get("prescribed_snapshot", {}).duplicate(true)


func observer() -> Dictionary:
	var value: Dictionary = _bundle.get("model", {}).get("observer", {})
	return value.duplicate(true)


func capability_status(requested: Array[String]) -> Dictionary:
	var missing: Array[String] = []
	for capability: String in requested:
		if not SUPPORTED_CAPABILITIES.has(capability):
			missing.append(capability)
	return {
		"ready": is_ready() and missing.is_empty(),
		"supported": SUPPORTED_CAPABILITIES.duplicate(),
		"missing": missing,
		"error": _last_error,
	}


func coupled_readiness() -> Dictionary:
	return {
		"ready": false,
		"mode": "coupled_physical_radiation",
		"missing": COUPLED_REQUIREMENTS.duplicate(),
		"reason": "No qualified native material provider or conservative thermal/radiation state is installed.",
	}


func publication(frame: Dictionary, source_epoch: int) -> Dictionary:
	if not is_ready():
		return {"ready": false, "error": _last_error}
	var snapshot: Dictionary = prescribed_snapshot()
	var origin: Vector3 = frame.get("world_origin", Vector3.ZERO)
	var bounds: AABB = frame.get("bounds", AABB())
	snapshot["state_epoch"] = source_epoch
	snapshot["executed_step"] = int(frame.get("executed_step", frame.get("step", 0)))
	snapshot["physical_time_s"] = float(frame.get("physical_time_s", frame.get("time", 0.0)))
	snapshot["frame_origin_sim"] = [origin.x, origin.y, origin.z]
	snapshot["center_sim"] = [
		bounds.get_center().x,
		bounds.get_center().y,
		bounds.get_center().z,
	]
	snapshot["radius_sim"] = 0.5 * bounds.size.length()
	return {
		"ready": true,
		"source_kind": "prescribed",
		"coupling": "prescribed",
		"approximation": "frozen_state_formal_solution",
		"model": model(),
		"spectral_grid": spectral_grid(),
		"observer": observer(),
		"snapshot": snapshot,
		"publication_id": "%s:%d" % [String(snapshot.get("snapshot_sha256", "")), source_epoch],
		"unavailable": coupled_readiness().missing,
	}


static func load_coupled_file(path: String, expected_sha256: String) -> Dictionary:
	if path.is_empty():
		return _invalid("coupled material path is empty")
	if not _valid_hash(expected_sha256):
		return _invalid("coupled material requires an explicit SHA-256")
	var bytes: PackedByteArray = FileAccess.get_file_as_bytes(path)
	if bytes.is_empty():
		return _invalid("coupled material file is missing or empty")
	if _sha256(bytes) != expected_sha256.to_lower():
		return _invalid("coupled material file SHA-256 mismatch")
	var parsed: Variant = JSON.parse_string(bytes.get_string_from_utf8())
	if not parsed is Dictionary:
		return _invalid("coupled material file is not a JSON object")
	var candidate: Dictionary = parsed
	var validation: Dictionary = validate_coupled_bundle(candidate)
	if not bool(validation.get("ok", false)):
		return validation
	return {
		"ok": true,
		"error": "",
		"file_sha256": expected_sha256.to_lower(),
		"bundle": candidate.duplicate(true),
	}


static func validate_coupled_bundle(candidate: Dictionary) -> Dictionary:
	var finite_error: String = _finite_tree_error(candidate, "coupled_fixture")
	if not finite_error.is_empty():
		return _invalid(finite_error)
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported coupled fixture schema major")
	if not candidate.get("model", null) is Dictionary:
		return _invalid("coupled fixture is missing its model")
	if candidate.has("fixture_payload_sha256") \
			and not _valid_hash(String(candidate.fixture_payload_sha256)):
		return _invalid("coupled fixture payload identity is invalid")
	return validate_coupled_model(candidate.model)


static func validate_coupled_model(candidate: Dictionary) -> Dictionary:
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported coupled model schema major")
	for key: String in [
		"model_id", "revision", "model_sha256", "source_kind", "coupling",
		"qualification_scope", "unit_map", "spectral_grid", "material",
	]:
		if not candidate.has(key):
			return _invalid("missing coupled model field: " + key)
	if String(candidate.source_kind) not in ["supplied", "supplied_reference"] \
			or String(candidate.coupling) != "coupled":
		return _invalid("coupled model must be an explicitly supplied source")
	if not _valid_hash(String(candidate.model_sha256)):
		return _invalid("coupled model identity is invalid")
	if int(candidate.revision) < 1:
		return _invalid("coupled model revision must be positive")
	if not candidate.qualification_scope is Array:
		return _invalid("coupled qualification_scope must be an array")
	for capability: String in COUPLED_ENGINE_CAPABILITIES:
		if not candidate.qualification_scope.has(capability):
			return _invalid("coupled model lacks capability: " + capability)
	if not candidate.unit_map is Dictionary:
		return _invalid("coupled unit_map must be an object")
	var unit_result: Dictionary = validate_coupled_unit_map(candidate.unit_map)
	if not bool(unit_result.ok):
		return unit_result
	if not candidate.spectral_grid is Dictionary:
		return _invalid("coupled spectral_grid must be an object")
	var grid_result: Dictionary = validate_coupled_grid(candidate.spectral_grid)
	if not bool(grid_result.ok):
		return grid_result
	if not candidate.material is Dictionary:
		return _invalid("coupled material descriptor must be an object")
	return validate_coupled_material(candidate.material, int(candidate.spectral_grid.group_count))


static func validate_coupled_unit_map(candidate: Dictionary) -> Dictionary:
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported coupled unit-map schema major")
	for key: String in [
		"length_m_per_sim", "time_s_per_physics_sim", "mass_kg_per_sim",
		"temperature_K_per_value", "energy_J_per_sim", "c_gamma_sim",
	]:
		if not candidate.has(key) or not _is_finite_number(candidate[key]) \
				or float(candidate[key]) <= 0.0:
			return _invalid("coupled unit-map field must be finite and positive: " + key)
	if not _valid_hash(String(candidate.get("unit_map_sha256", ""))):
		return _invalid("coupled unit-map identity is invalid")
	var length_scale: float = float(candidate.length_m_per_sim)
	var time_scale: float = float(candidate.time_s_per_physics_sim)
	var mass_scale: float = float(candidate.mass_kg_per_sim)
	var derived_c: float = C_LIGHT_M_S * time_scale / length_scale
	if absf(derived_c / float(candidate.c_gamma_sim) - 1.0) > 1e-12:
		return _invalid("coupled c_gamma_sim is inconsistent with length/time units")
	var derived_energy: float = mass_scale * length_scale * length_scale \
			/ (time_scale * time_scale)
	if absf(derived_energy / float(candidate.energy_J_per_sim) - 1.0) > 1e-12:
		return _invalid("coupled energy_J_per_sim is inconsistent with base units")
	return {"ok": true, "error": ""}


static func validate_coupled_grid(candidate: Dictionary) -> Dictionary:
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported coupled spectral-grid schema major")
	if not _valid_hash(String(candidate.get("group_layout_sha256", ""))):
		return _invalid("coupled spectral-grid identity is invalid")
	if String(candidate.get("frequency_frame", "")) != COUPLED_FREQUENCY_FRAME:
		return _invalid("coupled frequency frame is unsupported")
	if String(candidate.get("intragroup_reconstruction", "")) != COUPLED_RECONSTRUCTION:
		return _invalid("coupled intragroup reconstruction is unsupported")
	if String(candidate.get("angular_closure", "")) != COUPLED_CLOSURE:
		return _invalid("coupled angular closure is unsupported")
	if String(candidate.get("outer_frequency_policy", "")) != COUPLED_OUTER_POLICY:
		return _invalid("coupled outer-frequency policy is unsupported")
	var group_count: int = int(candidate.get("group_count", 0))
	var edges_value: Variant = candidate.get("frequency_edges_Hz", [])
	if group_count < 1 or group_count > 32:
		return _invalid("coupled group count must be in [1, 32]")
	if not edges_value is Array or edges_value.size() != group_count + 1:
		return _invalid("coupled frequency-edge length mismatch")
	var previous: float = -INF
	for edge: Variant in edges_value:
		if not _is_finite_number(edge) or float(edge) <= 0.0 or float(edge) <= previous:
			return _invalid("coupled frequency edges must be finite, positive and strictly increasing")
		previous = float(edge)
	return {"ok": true, "error": ""}


static func validate_coupled_material(candidate: Dictionary, group_count: int) -> Dictionary:
	for key: String in [
		"canonical_element", "geometry_source", "eos", "transport",
		"coefficients", "lte_table", "initial_state",
	]:
		if not candidate.has(key):
			return _invalid("missing coupled material field: " + key)
	if String(candidate.canonical_element) != "homogeneous_affine_cell" \
			or String(candidate.geometry_source) != "supplied_uniform":
		return _invalid("coupled material geometry is unsupported")
	if not candidate.eos is Dictionary:
		return _invalid("coupled EOS must be an object")
	var eos: Dictionary = candidate.eos
	if String(eos.get("kind", "")) != "ideal_gas_constant_specific_heat":
		return _invalid("coupled EOS kind is unsupported")
	for key: String in [
		"gamma", "specific_heat_J_kg_K", "temperature_min_K", "temperature_max_K",
	]:
		if not eos.has(key) or not _is_finite_number(eos[key]) or float(eos[key]) <= 0.0:
			return _invalid("invalid coupled EOS field: " + key)
	if float(eos.gamma) <= 1.0 or float(eos.temperature_max_K) <= float(eos.temperature_min_K):
		return _invalid("coupled EOS domain is invalid")
	if not candidate.transport is Dictionary:
		return _invalid("coupled transport descriptor must be an object")
	var transport: Dictionary = candidate.transport
	if String(transport.get("operator_order", "")) != COUPLED_OPERATOR_ORDER:
		return _invalid("coupled operator order is unsupported")
	if String(transport.get("source_interpolation", "")) != "linear_temperature":
		return _invalid("coupled source interpolation is unsupported")
	if not _positive_in_range(transport.get("frequency_cfl", null), 0.0, 1.0):
		return _invalid("coupled frequency CFL must be in (0, 1]")
	if int(transport.get("max_frequency_substeps", 0)) < 1 \
			or int(transport.get("max_frequency_substeps", 0)) > 65536:
		return _invalid("coupled frequency substep cap is invalid")
	if int(transport.get("source_root_iterations", 0)) < 16 \
			or int(transport.get("source_root_iterations", 0)) > 64:
		return _invalid("coupled source root iteration count is invalid")
	if not candidate.coefficients is Dictionary:
		return _invalid("coupled coefficient descriptor must be an object")
	var coefficients: Dictionary = candidate.coefficients
	if String(coefficients.get("coefficient_frame", "")) != COUPLED_FREQUENCY_FRAME \
			or String(coefficients.get("coefficient_hold", "")) != "accepted_source_step":
		return _invalid("coupled coefficient frame/hold is unsupported")
	for key: String in ["absorption_m_inv", "scattering_m_inv"]:
		var values: Variant = coefficients.get(key, [])
		if not values is Array or values.size() != group_count:
			return _invalid("coupled coefficient length mismatch: " + key)
		for value: Variant in values:
			if not _is_finite_number(value) or float(value) < 0.0:
				return _invalid("coupled coefficient must be finite and nonnegative: " + key)
	for scatter: Variant in coefficients.scattering_m_inv:
		if float(scatter) != 0.0:
			return _invalid("coupled isotropic baseline does not qualify scattering")
	if not candidate.lte_table is Dictionary:
		return _invalid("coupled LTE table must be an object")
	var table: Dictionary = candidate.lte_table
	if String(table.get("layout", "")) != "temperature_major_group_minor":
		return _invalid("coupled LTE table layout is unsupported")
	var temperatures_value: Variant = table.get("temperature_K", [])
	var energy_value: Variant = table.get("energy_density_J_m3", [])
	if not temperatures_value is Array or temperatures_value.size() < 2:
		return _invalid("coupled LTE temperature grid is invalid")
	if not energy_value is Array or energy_value.size() != temperatures_value.size() * group_count:
		return _invalid("coupled LTE energy-table length mismatch")
	var previous_temperature: float = -INF
	for temperature: Variant in temperatures_value:
		if not _is_finite_number(temperature) or float(temperature) <= previous_temperature:
			return _invalid("coupled LTE temperatures must be finite and strictly increasing")
		previous_temperature = float(temperature)
	if float(temperatures_value[0]) > float(eos.temperature_min_K) \
			or float(temperatures_value[-1]) < float(eos.temperature_max_K):
		return _invalid("coupled LTE table does not cover the EOS domain")
	for index: int in energy_value.size():
		var value: Variant = energy_value[index]
		if not _is_finite_number(value) or float(value) < 0.0:
			return _invalid("coupled LTE energy density must be finite and nonnegative")
		if index >= group_count and float(value) < float(energy_value[index - group_count]):
			return _invalid("coupled LTE group energy must be monotone with temperature")
	if not candidate.initial_state is Dictionary:
		return _invalid("coupled initial state must be an object")
	return validate_coupled_initial_state(candidate.initial_state, group_count, eos)


static func validate_coupled_initial_state(candidate: Dictionary, group_count: int,
		eos: Dictionary) -> Dictionary:
	for key: String in [
		"mass_density_kg_m3", "volume_m3", "temperature_K", "expansion_rate_s_inv",
	]:
		if not candidate.has(key) or not _is_finite_number(candidate[key]):
			return _invalid("invalid coupled initial-state field: " + key)
	if float(candidate.mass_density_kg_m3) <= 0.0 or float(candidate.volume_m3) <= 0.0:
		return _invalid("coupled initial mass density and volume must be positive")
	var temperature: float = float(candidate.temperature_K)
	if temperature < float(eos.temperature_min_K) or temperature > float(eos.temperature_max_K):
		return _invalid("coupled initial temperature is outside the EOS domain")
	var radiation: Variant = candidate.get("radiation_energy_density_J_m3", [])
	if not radiation is Array or radiation.size() != group_count:
		return _invalid("coupled initial radiation group length mismatch")
	for value: Variant in radiation:
		if not _is_finite_number(value) or float(value) < 0.0:
			return _invalid("coupled initial radiation energy must be finite and nonnegative")
	return {"ok": true, "error": ""}

static func validate_bundle(candidate: Dictionary, required_capabilities: Array[String] = []) -> Dictionary:
	var finite_error: String = _finite_tree_error(candidate, "fixture")
	if not finite_error.is_empty():
		return _invalid(finite_error)
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported fixture schema major")
	for key: String in ["model", "selected_layout", "prescribed_snapshot", "observer_asset"]:
		if not candidate.has(key) or not candidate[key] is Dictionary:
			return _invalid("missing fixture object: " + key)
	var model_result: Dictionary = validate_model(candidate.model, required_capabilities)
	if not bool(model_result.ok):
		return model_result
	var grid_result: Dictionary = validate_grid(candidate.selected_layout)
	if not bool(grid_result.ok):
		return grid_result
	var snapshot_result: Dictionary = validate_snapshot(candidate.prescribed_snapshot,
			String(candidate.model.model_sha256), String(candidate.model.unit_map.unit_map_sha256),
			String(candidate.selected_layout.layout_sha256))
	if not bool(snapshot_result.ok):
		return snapshot_result
	var observer_asset: Dictionary = candidate.observer_asset
	if String(observer_asset.get("sha256", "")) != OBSERVER_SHA256:
		return _invalid("observer asset identity mismatch")
	return {"ok": true, "error": ""}


static func validate_model(candidate: Dictionary, required_capabilities: Array[String] = []) -> Dictionary:
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported model schema major")
	for key: String in ["model_id", "model_revision", "model_sha256", "source_kind",
			"coupling", "qualification_scope", "unit_map", "material", "observer"]:
		if not candidate.has(key):
			return _invalid("missing model field: " + key)
	if String(candidate.source_kind) != "prescribed" or String(candidate.coupling) != "prescribed":
		return _invalid("P0/P1 accepts only prescribed, one-way material")
	if not candidate.qualification_scope is Array:
		return _invalid("qualification_scope must be an array")
	for required: String in required_capabilities:
		if not candidate.qualification_scope.has(required):
			return _invalid("unsupported capability: " + required)
	var unit_result: Dictionary = validate_unit_map(candidate.unit_map)
	if not bool(unit_result.ok):
		return unit_result
	var material: Dictionary = candidate.material
	for key: String in ["temperature_K", "absorption_m_inv", "scattering_m_inv",
			"boundary_radiance_W_m2_sr"]:
		if not material.has(key) or not _is_finite_number(material[key]):
			return _invalid("invalid material field: " + key)
	if float(material.temperature_K) <= 0.0:
		return _invalid("temperature_K must be positive")
	if float(material.absorption_m_inv) < 0.0 or float(material.scattering_m_inv) < 0.0:
		return _invalid("material coefficients must be nonnegative")
	if float(material.scattering_m_inv) != 0.0:
		return _invalid("scattering requires an explicit incoming angular source")
	if float(material.boundary_radiance_W_m2_sr) < 0.0:
		return _invalid("boundary radiance must be nonnegative")
	var observer_value: Dictionary = candidate.observer
	if String(observer_value.get("sha256", "")) != OBSERVER_SHA256:
		return _invalid("model observer hash mismatch")
	return {"ok": true, "error": ""}


static func validate_unit_map(candidate: Dictionary) -> Dictionary:
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported unit-map schema major")
	for key: String in ["length_m_per_sim", "time_s_per_physics_sim", "mass_kg_per_sim",
			"temperature_K_per_value", "radiance_scale_W_m2_sr", "c_gamma_sim"]:
		if not candidate.has(key) or not _is_finite_number(candidate[key]) or float(candidate[key]) <= 0.0:
			return _invalid("unit-map field must be finite and positive: " + key)
	var derived_c: float = 299792458.0 * float(candidate.time_s_per_physics_sim) \
			/ float(candidate.length_m_per_sim)
	if absf(derived_c / float(candidate.c_gamma_sim) - 1.0) > 1e-12:
		return _invalid("c_gamma_sim is inconsistent with length/time units")
	return {"ok": true, "error": ""}


static func validate_grid(candidate: Dictionary) -> Dictionary:
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported spectral-grid schema major")
	var visible_count: int = int(candidate.get("visible_group_count", 0))
	var total_count: int = int(candidate.get("total_group_count", 0))
	var groups_value: Variant = candidate.get("groups", [])
	if visible_count not in [16, 32, 64] or total_count != visible_count + 2:
		return _invalid("unsupported spectral group count")
	if not groups_value is Array or groups_value.size() != total_count:
		return _invalid("spectral group array length mismatch")
	var groups: Array = groups_value
	if String(groups[0].get("kind", "")) != "ultraviolet_tail" \
			or String(groups[-1].get("kind", "")) != "infrared_tail":
		return _invalid("spectral layout requires explicit bolometric tails")
	var previous_hi: float = 360.0
	for index: int in range(1, total_count - 1):
		var group: Dictionary = groups[index]
		if String(group.get("kind", "")) != "visible":
			return _invalid("interior spectral group is not visible")
		var lo: float = float(group.get("wavelength_lo_nm", NAN))
		var hi: float = float(group.get("wavelength_hi_nm", NAN))
		if not is_finite(lo) or not is_finite(hi) or lo != previous_hi or hi <= lo:
			return _invalid("spectral wavelength coverage is unordered or has gaps")
		var f_lo: float = float(group.get("frequency_lo_hz", NAN))
		var f_hi: float = float(group.get("frequency_hi_hz", NAN))
		if not is_finite(f_lo) or not is_finite(f_hi) or f_hi <= f_lo:
			return _invalid("spectral frequency interval is invalid")
		var weights: Variant = group.get("observer_xyz_integral_m", [])
		if not weights is Array or weights.size() != 3:
			return _invalid("spectral observer weights are missing")
		for weight: Variant in weights:
			if not _is_finite_number(weight) or float(weight) < 0.0:
				return _invalid("spectral observer weight is invalid")
		previous_hi = hi
	if previous_hi != 830.0:
		return _invalid("spectral visible coverage must end at 830 nm")
	return {"ok": true, "error": ""}


static func validate_snapshot(candidate: Dictionary, model_hash: String,
		unit_hash: String, group_hash: String) -> Dictionary:
	if _schema_major(String(candidate.get("schema_version", ""))) != SCHEMA_MAJOR:
		return _invalid("unsupported material-snapshot schema major")
	if String(candidate.get("source_kind", "")) != "prescribed" \
			or String(candidate.get("coupling", "")) != "prescribed":
		return _invalid("snapshot is not prescribed and one-way")
	for pair: Array in [
		["model_sha256", model_hash], ["unit_map_sha256", unit_hash],
		["group_layout_sha256", group_hash],
	]:
		if String(candidate.get(String(pair[0]), "")) != String(pair[1]):
			return _invalid("snapshot identity mismatch: " + String(pair[0]))
	for key: String in ["state_epoch", "reset_epoch", "executed_step", "physical_time_s",
			"integration_interval_s", "temperature_K", "absorption_m_inv",
			"scattering_m_inv", "boundary_radiance_W_m2_sr", "radius_sim"]:
		if not candidate.has(key) or not _is_finite_number(candidate[key]):
			return _invalid("invalid snapshot field: " + key)
	if int(candidate.state_epoch) < 0 or int(candidate.reset_epoch) < 0 \
			or int(candidate.executed_step) < 0 or float(candidate.physical_time_s) < 0.0 \
			or float(candidate.integration_interval_s) < 0.0:
		return _invalid("snapshot counters/times must be nonnegative")
	if float(candidate.temperature_K) <= 0.0 or float(candidate.absorption_m_inv) < 0.0 \
			or float(candidate.scattering_m_inv) != 0.0 or float(candidate.radius_sim) <= 0.0:
		return _invalid("snapshot material domain is invalid")
	if not bool(candidate.get("valid", false)):
		return _invalid("snapshot validity mask rejects the state")
	return {"ok": true, "error": ""}


static func formal_transfer(intensity_in: float, source_radiance: float,
		alpha_m_inv: float, distance_m: float) -> float:
	if not is_finite(intensity_in) or not is_finite(source_radiance) \
			or not is_finite(alpha_m_inv) or not is_finite(distance_m) \
			or intensity_in < 0.0 or source_radiance < 0.0 \
			or alpha_m_inv < 0.0 or distance_m < 0.0:
		return NAN
	var tau: float = alpha_m_inv * distance_m
	if tau < 1e-5:
		# 1-exp(-tau), evaluated without cancellation through its series.
		var one_minus: float = tau * (1.0 - 0.5 * tau + tau * tau / 6.0)
		return intensity_in * exp(-tau) + source_radiance * one_minus
	return intensity_in * exp(-tau) + source_radiance * (1.0 - exp(-tau))


static func _valid_hash(value: String) -> bool:
	if value.length() != 64:
		return false
	var lowered: String = value.to_lower()
	for index: int in lowered.length():
		if "0123456789abcdef".find(lowered.substr(index, 1)) < 0:
			return false
	return true


static func _positive_in_range(value: Variant, lower_exclusive: float,
		upper_inclusive: float) -> bool:
	return _is_finite_number(value) and float(value) > lower_exclusive \
			and float(value) <= upper_inclusive


static func _schema_major(value: String) -> int:
	var token: String = value.split(".")[0] if not value.is_empty() else ""
	return int(token) if token.is_valid_int() else -1


static func _is_finite_number(value: Variant) -> bool:
	return (value is int or value is float) and is_finite(float(value))


static func _finite_tree_error(value: Variant, path: String) -> String:
	if value is float and not is_finite(float(value)):
		return path + " is nonfinite"
	if value is Array:
		for index: int in value.size():
			var child_error: String = _finite_tree_error(value[index], "%s[%d]" % [path, index])
			if not child_error.is_empty():
				return child_error
	elif value is Dictionary:
		for key: Variant in value:
			var child_error: String = _finite_tree_error(value[key], path + "." + String(key))
			if not child_error.is_empty():
				return child_error
	return ""


static func _sha256(bytes: PackedByteArray) -> String:
	var context: HashingContext = HashingContext.new()
	context.start(HashingContext.HASH_SHA256)
	context.update(bytes)
	return context.finish().hex_encode()


static func _invalid(message: String) -> Dictionary:
	return {"ok": false, "error": message}


func _fail(message: String) -> bool:
	_last_error = message
	_bundle = {}
	return false
