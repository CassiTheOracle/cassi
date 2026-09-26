extends Node
## Windowed acceptance arm for the implemented P0/P1 physical-radiation scope.
## It exercises the immutable reference contract and the real global-RD spectral
## formal solution. Unsupported coupled capabilities are rejection checks.

const OUTPUT := "res://_diag/physical_radiation"
const MATERIAL = preload("res://scripts/cassi_radiative_material.gd")
const SPECTRAL = preload("res://scripts/cassi_spectral_volume.gd")

var _checks := 0
var _failures := 0
var _receipt: Dictionary = {"gates": {}, "measurements": {}}
var _volume: RefCounted


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
	get_window().size = Vector2i(640, 360)
	var material: RefCounted = MATERIAL.new()
	var loaded: bool = material.load_reference()
	_check("PR-G1 immutable material and unit contract loads", loaded)
	if loaded:
		_verify_contract(material)
	var rd := RenderingServer.get_rendering_device()
	_check("PR-G3 windowed global RenderingDevice is available", rd != null)
	if loaded and rd != null:
		await _verify_spectral_gpu(material, rd)
	_receipt["checks"] = _checks
	_receipt["failures"] = _failures
	var file := FileAccess.open(OUTPUT.path_join("verification.json"), FileAccess.WRITE)
	file.store_string(JSON.stringify(_receipt, "\t") + "\n")
	file.close()
	if _volume != null:
		_volume.shutdown()
	print("PHYSICAL RADIATION RESULT: %d/%d passed" % [_checks - _failures, _checks])
	get_tree().quit(0 if _failures == 0 else 1)


func _verify_contract(material: RefCounted) -> void:
	var bundle: Dictionary = material.bundle()
	var model: Dictionary = bundle.get("model", {})
	var units: Dictionary = model.get("unit_map", {})
	var layout: Dictionary = bundle.get("selected_layout", {})
	var snapshot: Dictionary = bundle.get("prescribed_snapshot", {})
	var identity_ok := str(model.get("model_sha256", "")).length() == 64 \
			and str(units.get("unit_map_sha256", "")).length() == 64 \
			and str(layout.get("layout_sha256", "")).length() == 64 \
			and str(snapshot.get("snapshot_sha256", "")).length() == 64 \
			and float(units.get("length_m_per_sim", 0.0)) > 0.0 \
			and float(units.get("radiance_scale_W_m2_sr", 0.0)) > 0.0
	_check("PR-G1 model, snapshot, layout and unit identities are complete", identity_ok)
	var rejected: Dictionary = MATERIAL.validate_bundle(bundle, ["coupled_thermal_state"])
	_check("PR-G1 unsupported live coupling is rejected before GPU work",
			not bool(rejected.get("ok", true))
			and str(rejected.get("error", "")).contains("coupled_thermal_state"))
	var candidates: Array = bundle.get("candidate_receipts", [])
	var selected_groups := int(layout.get("visible_group_count", 0))
	var selected_row: Dictionary = {}
	for value: Variant in candidates:
		var row: Dictionary = value
		if int(row.get("visible_group_count", 0)) == selected_groups:
			selected_row = row
			break
	_check("PR-G2 independent grouped Planck reference closes",
			not selected_row.is_empty()
			and float(selected_row.get("max_relative_power_error", 1.0)) < 1e-12)
	_check("PR-G4 CIE colour reference meets frozen chromaticity tolerance",
			not selected_row.is_empty()
			and float(selected_row.get("max_chromaticity_error", 1.0)) < 0.002)
	var convergence_ok := candidates.size() >= 3
	var previous_error := INF
	for value: Variant in candidates:
		var row: Dictionary = value
		var error := float(row.get("max_chromaticity_error", INF))
		convergence_ok = convergence_ok and error <= previous_error + 1e-15
		previous_error = error
	_check("PR-G5 spectral refinement is monotone", convergence_ok)
	var slab_ok := true
	for value: Variant in bundle.get("slab_controls", []):
		var row: Dictionary = value
		slab_ok = slab_ok and is_finite(float(row.get("computed", NAN))) \
				and float(row.get("relative_error", 1.0)) < 1e-12
	_check("PR-G10 zero-thin-thick formal-solution limits close", slab_ok)
	_receipt.measurements["selected_visible_groups"] = selected_groups
	_receipt.measurements["selected_candidate"] = selected_row
	_receipt.measurements["rejection"] = rejected


func _verify_spectral_gpu(material: RefCounted, rd: RenderingDevice) -> void:
	_volume = SPECTRAL.new()
	var initialized: bool = _volume.initialize(rd)
	_check("PR-G3 spectral GPU backend initializes", initialized)
	if not initialized:
		return
	var samples: Array[Dictionary] = []
	for edge in [33, 65]:
		var frame := _frame(Vector2i(edge, edge), edge)
		var submitted: bool = _volume.update(frame, {})
		await RenderingServer.frame_post_draw
		var raw: Dictionary = _volume.capture_raw_xyz()
		var measured := _center_xyz(raw)
		var expected := _expected_center_xyz(material, frame)
		var relative := _relative_vector_error(measured, expected)
		samples.append({
			"edge": edge,
			"measured_xyz_numeric": [measured.x, measured.y, measured.z],
			"expected_xyz_numeric": [expected.x, expected.y, expected.z],
			"relative_error": relative,
			"byte_count": (raw.get("bytes", PackedByteArray()) as PackedByteArray).size(),
		})
		_check("PR-G3 GPU formal solution matches CPU reference at %dx%d" % [edge, edge],
				submitted and bool(raw.get("ok", false)) and relative < 2e-5)
	var spatial := _relative_vector_error(
			Vector3(samples[0].measured_xyz_numeric[0], samples[0].measured_xyz_numeric[1], samples[0].measured_xyz_numeric[2]),
			Vector3(samples[1].measured_xyz_numeric[0], samples[1].measured_xyz_numeric[1], samples[1].measured_xyz_numeric[2]))
	_check("PR-G5 center-ray result is resolution independent", spatial < 2e-6)
	var before: Dictionary = _volume.statistics()
	_volume.update(_frame(Vector2i(65, 65), 3), {})
	await RenderingServer.frame_post_draw
	var after: Dictionary = _volume.statistics()
	_check("PR-G12 same-size frame reuses spectral allocations",
			int(after.get("allocation_count", -1)) == int(before.get("allocation_count", -2)))
	var maximum_spectral_bytes := SPECTRAL.MAX_RENDER_EDGE * SPECTRAL.MAX_RENDER_EDGE * 36
	_check("PR-G12 spectral outputs stay below their bounded memory envelope",
			int(after.get("estimated_total_bytes", 1 << 60)) < 256 * 1024 * 1024
			and maximum_spectral_bytes < 1024 * 1024 * 1024
			and int(after.get("per_group_depth_atlas_bytes", -1)) == 0)
	var publication: Dictionary = _volume.publication_metadata()
	_check("PR-G6 P1 publication is explicitly prescribed and one-way",
			str(publication.get("coupling", "")) == "prescribed"
			and "paired_matter_radiation_exchange" in publication.get("unavailable", []))
	_receipt.measurements["gpu_samples"] = samples
	_receipt.measurements["spatial_relative_error"] = spatial
	_receipt.measurements["gpu_statistics"] = _json_safe(after)
	_receipt.measurements["publication"] = _json_safe(publication)


func _frame(size: Vector2i, epoch: int) -> Dictionary:
	return {
		"render_size": size,
		"camera_transform": Transform3D(Basis.IDENTITY, Vector3(0.0, 0.0, 3.0)),
		"fov": 60.0,
		"near": 0.1,
		"far": 100.0,
		"bounds": AABB(-Vector3.ONE, Vector3.ONE * 2.0),
		"world_origin": Vector3.ZERO,
		"source_epoch": epoch,
		"executed_step": 0,
		"physical_time_s": 0.0,
	}


func _center_xyz(raw: Dictionary) -> Vector3:
	if not bool(raw.get("ok", false)):
		return Vector3(INF, INF, INF)
	var size: Vector2i = raw.get("size", Vector2i.ZERO)
	var bytes: PackedByteArray = raw.get("bytes", PackedByteArray())
	var offset := ((size.y / 2) * size.x + size.x / 2) * 16
	if offset < 0 or offset + 12 > bytes.size():
		return Vector3(INF, INF, INF)
	return Vector3(bytes.decode_float(offset), bytes.decode_float(offset + 4), bytes.decode_float(offset + 8))


func _expected_center_xyz(material: RefCounted, frame: Dictionary) -> Vector3:
	var bundle: Dictionary = material.bundle()
	var model: Dictionary = bundle.model
	var layout: Dictionary = bundle.selected_layout
	var controls: Array = bundle.temperature_controls
	var selected: Dictionary = {}
	for value: Variant in controls:
		var row: Dictionary = value
		if is_equal_approx(float(row.temperature_K), float(model.material.temperature_K)):
			selected = row
			break
	var radius := 0.48 * 2.0
	var camera := Vector3(0.0, 0.0, 3.0)
	var b := camera.dot(Vector3(0.0, 0.0, -1.0))
	var root := sqrt(b * b - (camera.length_squared() - radius * radius))
	var distance_m := maxf((-b + root) - maxf(-b - root, float(frame.near)), 0.0) \
			* float(model.unit_map.length_m_per_sim)
	var xyz := Vector3.ZERO
	var radiance_groups: Array = selected.group_radiance_W_m2_sr
	var groups: Array = layout.groups
	var scale := float(model.unit_map.radiance_scale_W_m2_sr)
	var alpha := float(model.material.absorption_m_inv)
	for index in int(layout.visible_group_count):
		var group: Dictionary = groups[index + 1]
		var weights: Array = group.observer_xyz_integral_m
		var width_m := (float(group.wavelength_hi_nm) - float(group.wavelength_lo_nm)) * 1e-9
		var source := float(radiance_groups[index + 1]) / scale
		var intensity := source * (1.0 - exp(-alpha * distance_m))
		xyz += intensity * Vector3(float(weights[0]), float(weights[1]), float(weights[2])) / width_m
	return xyz


func _relative_vector_error(a: Vector3, b: Vector3) -> float:
	return (a - b).length() / maxf(b.length(), 1e-30)


func _check(label: String, passed: bool) -> void:
	_checks += 1
	if not passed:
		_failures += 1
	print("[%s] %s" % ["PASS" if passed else "FAIL", label])


func _json_safe(value: Variant) -> Variant:
	if value is Dictionary:
		var mapped := {}
		for key: Variant in value:
			mapped[str(key)] = _json_safe(value[key])
		return mapped
	if value is Array:
		var mapped := []
		for child: Variant in value:
			mapped.append(_json_safe(child))
		return mapped
	if value is Vector2i:
		return [value.x, value.y]
	if value is Vector3:
		return [value.x, value.y, value.z]
	return value
