extends Node3D
## Windowed regression for the new optical renderer. Reads real pre-tonemap
## scene color and production density/tau outputs; no solver or shader mocks.

const OUTPUT := "res://_diag/observatory"
const OPTICS = preload("res://scripts/cassi_observatory_volume.gd")
var _checks := 0
var _failures := 0
var _receipt: Dictionary = {"points": [], "density": []}
var _rd: RenderingDevice
var _owned: Array[RID] = []

class HDRReadback extends CompositorEffect:
	var mutex := Mutex.new()
	var requested := false
	var bytes := PackedByteArray()
	var dimensions := Vector2i.ZERO
	var shader := RID()
	var pipeline := RID()

	func _init() -> void:
		effect_callback_type = EFFECT_CALLBACK_TYPE_POST_TRANSPARENT
		access_resolved_color = true
		var device := RenderingServer.get_rendering_device()
		var source: RDShaderFile = load("res://compute/cassi_observatory_probe_readback.glsl")
		shader = device.shader_create_from_spirv(source.get_spirv())
		pipeline = device.compute_pipeline_create(shader)

	func request() -> void:
		mutex.lock()
		bytes.clear()
		requested = true
		mutex.unlock()

	func result() -> Dictionary:
		mutex.lock()
		var value := {"bytes": bytes, "size": dimensions}
		mutex.unlock()
		return value

	func _render_callback(_kind: int, data: RenderData) -> void:
		mutex.lock()
		if not requested:
			mutex.unlock()
			return
		var buffers := data.get_render_scene_buffers() as RenderSceneBuffersRD
		if buffers != null:
			var device := RenderingServer.get_rendering_device()
			var color := buffers.get_color_layer(0)
			if color.is_valid():
				dimensions = buffers.get_internal_size()
				var storage := device.storage_buffer_create(dimensions.x * dimensions.y * 16)
				var source := RDUniform.new()
				source.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
				source.binding = 0
				source.add_id(color)
				var target := RDUniform.new()
				target.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
				target.binding = 1
				target.add_id(storage)
				var uniforms := device.uniform_set_create([source, target], shader, 0)
				var commands := device.compute_list_begin()
				device.compute_list_bind_compute_pipeline(commands, pipeline)
				device.compute_list_bind_uniform_set(commands, uniforms, 0)
				device.compute_list_dispatch(commands, ceili(dimensions.x / 8.0), ceili(dimensions.y / 8.0), 1)
				device.compute_list_end()
				bytes = device.buffer_get_data(storage)
				device.free_rid(uniforms)
				device.free_rid(storage)
				requested = false
		mutex.unlock()

	func shutdown() -> void:
		mutex.lock()
		var device := RenderingServer.get_rendering_device()
		device.free_rid(pipeline)
		device.free_rid(shader)
		mutex.unlock()

func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(OUTPUT))
	get_window().size = Vector2i(512, 512)
	_rd = RenderingServer.get_rendering_device()
	_check("windowed global RenderingDevice", _rd != null)
	if _rd != null:
		await _points()
		await _density()
	_receipt["checks"] = _checks
	_receipt["failures"] = _failures
	var file := FileAccess.open(OUTPUT + "/optics_receipt.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(_receipt, "\t"))
	file.close()
	for rid in _owned:
		if rid.is_valid():
			_rd.free_rid(rid)
	print("OBSERVATORY OPTICS RESULT: %d/%d passed" % [_checks - _failures, _checks])
	get_tree().quit(0 if _failures == 0 else 1)

func _check(label: String, passed: bool) -> void:
	_checks += 1
	if not passed:
		_failures += 1
	print("[%s] %s" % ["PASS" if passed else "FAIL", label])

func _frames(count: int = 3) -> void:
	for _index in count:
		await get_tree().process_frame
	await RenderingServer.frame_post_draw

func _points() -> void:
	var camera := Camera3D.new()
	camera.fov = 60.0
	camera.near = 0.1
	camera.far = 100.0
	camera.environment = Environment.new()
	camera.environment.background_mode = Environment.BG_COLOR
	camera.environment.background_color = Color.BLACK
	camera.environment.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	add_child(camera)
	camera.make_current()
	var probe := HDRReadback.new()
	var compositor := Compositor.new()
	compositor.compositor_effects = [probe]
	camera.compositor = compositor
	var material := ShaderMaterial.new()
	material.shader = load("res://shaders/particle_billboard_observatory.gdshader")
	material.set_shader_parameter("viewport_height", 512.0)
	material.set_shader_parameter("reference_radius", 1.0)
	material.set_shader_parameter("luminosity_scale", 1.0)
	material.set_shader_parameter("point_fraction", 1.0)
	material.set_shader_parameter("emission_strength", 0.01)
	material.set_shader_parameter("optical_near", 0.1)
	material.set_shader_parameter("optical_far", 20.0)
	material.set_shader_parameter("velocity_time_scale", 1.0)
	var point := MultiMeshInstance3D.new()
	point.multimesh = MultiMesh.new()
	point.multimesh.transform_format = MultiMesh.TRANSFORM_3D
	point.multimesh.mesh = QuadMesh.new()
	point.material_override = material
	point.custom_aabb = AABB(Vector3(-30, -30, -30), Vector3(60, 60, 60))
	add_child(point)
	var zero_tau := _tau_texture(false)
	var slab_tau := _tau_texture(true)
	material.set_shader_parameter("optical_depth_texture", zero_tau)
	var reference := 0.0
	for spec in [
		{"name": "narrow", "size": 0.015, "shutter": 0.0, "count": 1, "distance": 5.0},
		{"name": "wide", "size": 0.4, "shutter": 0.0, "count": 1, "distance": 5.0},
		{"name": "shutter", "size": 0.4, "shutter": 0.2, "count": 1, "distance": 5.0},
		{"name": "split_mass", "size": 0.4, "shutter": 0.0, "count": 4, "distance": 5.0},
		{"name": "front", "size": 0.15, "shutter": 0.0, "count": 1, "distance": 3.0},
		{"name": "inside", "size": 0.15, "shutter": 0.0, "count": 1, "distance": 5.0},
		{"name": "behind", "size": 0.15, "shutter": 0.0, "count": 1, "distance": 7.0},
		{"name": "outside_volume", "size": 0.4, "shutter": 0.0, "count": 1, "distance": 5.0},
	]:
		point.multimesh.instance_count = 0
		point.multimesh.mesh.size = Vector2.ONE * float(spec.size)
		point.multimesh.instance_count = int(spec.count)
		var motion_image := Image.create(int(spec.count), 1, false, Image.FORMAT_RGBAF)
		motion_image.fill(Color(1.5, 0.7, 0.3, 1.0 / float(spec.count)))
		var motion := ImageTexture.create_from_image(motion_image)
		material.set_shader_parameter("motion_texture", motion)
		material.set_shader_parameter("motion_tex_width", float(spec.count))
		material.set_shader_parameter("shutter_seconds", float(spec.shutter))
		if spec.name == "outside_volume":
			material.set_shader_parameter("optical_bounds_min", -Vector3.ONE)
			material.set_shader_parameter("optical_bounds_max", Vector3.ONE)
			material.set_shader_parameter("point_fraction", 0.25)
		for index in int(spec.count):
			point.multimesh.set_instance_transform(index, Transform3D(Basis.IDENTITY, Vector3(0, 0, -float(spec.distance))))
		await _frames()
		var clear := await _read_point(probe, String(spec.name) + "_clear")
		_check("finite positive HDR flux " + String(spec.name), bool(clear.finite) and float(clear.flux) > 0.0)
		if spec.name == "narrow":
			reference = float(clear.flux)
		elif spec.name == "wide" or spec.name == "shutter":
			_check("footprint/shutter preserves integrated flux " + String(spec.name), absf(float(clear.flux) / maxf(reference, 1e-20) - 1.0) < 0.05)
		if spec.name == "split_mass":
			var wide: Dictionary = _receipt.points[1]
			_check("splitting mass preserves integrated flux", absf(float(clear.flux) / maxf(float(wide.clear.flux), 1e-20) - 1.0) < 0.02)
		if spec.name == "outside_volume":
			_check("escaped point retains its full luminosity", absf(float(clear.flux) / float(_receipt.points[1].clear.flux) - 1.0) < 0.02)
		var row: Dictionary = spec.duplicate()
		row["clear"] = clear
		if spec.name in ["front", "inside", "behind"]:
			material.set_shader_parameter("optical_depth_texture", slab_tau)
			await _frames()
			var attenuated := await _read_point(probe, String(spec.name) + "_slab")
			var expected := exp(-0.5 * clampf(float(spec.distance) - 4.0, 0.0, 2.0))
			var measured := float(attenuated.flux) / maxf(float(clear.flux), 1e-20)
			_check("particle depth extinction " + String(spec.name), absf(measured / expected - 1.0) < 0.05)
			row["transmission"] = measured
			row["expected"] = expected
			material.set_shader_parameter("optical_depth_texture", zero_tau)
		_receipt.points.append(row)
	point.queue_free()
	camera.compositor = null
	probe.enabled = false
	camera.queue_free()
	await _frames()
	probe.shutdown()

func _tau_texture(slab: bool) -> ImageTexture3D:
	var slices: Array[Image] = []
	for index in 64:
		var image := Image.create(1, 1, false, Image.FORMAT_RF)
		var distance := exp(lerpf(log(0.1), log(20.0), (float(index) + 0.5) / 64.0))
		image.fill(Color(0.5 * clampf(distance - 4.0, 0.0, 2.0) if slab else 0.0, 0, 0))
		slices.append(image)
	var texture := ImageTexture3D.new()
	texture.create(Image.FORMAT_RF, 1, 1, 64, false, slices)
	return texture

func _read_point(probe: HDRReadback, label: String) -> Dictionary:
	probe.request()
	var data: Dictionary = {}
	for _index in 20:
		await _frames(1)
		data = probe.result()
		if not data.bytes.is_empty():
			break
	var size: Vector2i = data.get("size", Vector2i.ZERO)
	var bytes: PackedByteArray = data.get("bytes", PackedByteArray())
	if bytes.is_empty() or size.x < 1:
		return {"finite": false, "flux": 0.0}
	var image := Image.create_from_data(size.x, size.y, false, Image.FORMAT_RGBAF, bytes)
	var flux := 0.0
	var finite := true
	for y in size.y:
		for x in size.x:
			var color := image.get_pixel(x, y)
			finite = finite and is_finite(color.r) and is_finite(color.g) and is_finite(color.b)
			flux += 0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b
	_write_bytes(label + ".bin", bytes)
	return {"finite": finite, "flux": flux, "width": size.x, "height": size.y, "pixel_bytes": 16}

func _density() -> void:
	var positions := PackedFloat32Array()
	for x in 4:
		for y in 4:
			for z in 4:
				positions.append_array(PackedFloat32Array([float(x) / 1.5 - 1.0, float(y) / 1.5 - 1.0, float(z) / 1.5 - 1.0, 1.0]))
	var position_rid := _rd.storage_buffer_create(positions.size() * 4, positions.to_byte_array())
	var velocities := PackedByteArray()
	velocities.resize(positions.size() * 4)
	var velocity_rid := _rd.storage_buffer_create(velocities.size(), velocities)
	_owned.append_array([position_rid, velocity_rid])
	var optics := OPTICS.new()
	_check("production optical pipelines initialize", optics.initialize(_rd))
	var frame := {
		"positions": position_rid, "velocities": velocity_rid, "particle_count": 64,
		"source_epoch": 1, "site_epoch": 0, "site_count": 0, "field_mode": false,
		"bounds": AABB(-Vector3.ONE, Vector3.ONE * 2.0),
		"camera_transform": Transform3D(Basis.IDENTITY, Vector3(0, 0, 4)),
		"fov": 30.0, "viewport_size": Vector2i(32, 32), "render_size": Vector2i(32, 32),
		"near": 0.1, "far": 8.0, "reference_mass": 64.0, "reference_radius": 1.0,
		"delta": 1.0 / 60.0, "simulation_delta": 0.0, "playing": false,
		"reset_history": true,
	}
	var settings: Dictionary = CassiObservatory.DEFAULTS.duplicate()
	settings.style = 1
	settings.adaptive_quality = false
	settings.scattering = 0.0
	for grid in [48, 64, 96, 128]:
		frame["grid_size"] = grid
		frame.source_epoch += 1
		_check("density reconstruction tier %d" % grid, optics.update(frame, settings))
		await _frames()
		var rho_bytes := _rd.texture_get_data(optics.get("_density_tex"), 0)
		var rho := rho_bytes.to_float32_array()
		var total := 0.0
		var finite: bool = rho.size() == grid * grid * grid * 4
		for index in range(0, rho.size(), 4):
			finite = finite and is_finite(rho[index]) and rho[index] >= 0.0
			total += float(rho[index])
		total *= 8.0 / float(grid * grid * grid)
		_check("boundary mass conservation tier %d" % grid, finite and absf(total / 64.0 - 1.0) < 0.005)
		_receipt.density.append({"grid": grid, "mass": total, "finite": finite})
		if grid == 64:
			_write_bytes("density64.bin", rho_bytes)
			_write_bytes("tau64.bin", _rd.texture_get_data(optics.optical_depth.texture_rd_rid, 0))
			_write_bytes("radiance64.bin", _rd.texture_get_data(optics.radiance.texture_rd_rid, 0))
			_receipt["volume_frame"] = {"camera": [0, 0, 4], "bounds_min": [-1, -1, -1], "bounds_max": [1, 1, 1], "fov": 30.0, "width": 32, "height": 32, "near": 0.1, "far": 8.0, "reference_mass": 64.0, "reference_radius": 1.0}
	positions[0] = 10.0
	_rd.buffer_update(position_rid, 0, positions.size() * 4, positions.to_byte_array())
	frame.source_epoch += 1
	optics.update(frame, settings)
	await _frames()
	var bounded_density := _rd.texture_get_data(optics.get("_density_tex"), 0).to_float32_array()
	var bounded_mass := 0.0
	for index in range(0, bounded_density.size(), 4): bounded_mass += float(bounded_density[index])
	bounded_mass *= 8.0 / pow(128.0, 3.0)
	_check("escaped mass is not deposited on optical boundary", absf(bounded_mass / 63.0 - 1.0) < 0.005)
	positions[0] = -1.0
	_rd.buffer_update(position_rid, 0, positions.size() * 4, positions.to_byte_array())
	settings.optical_thickness = 0.0
	frame.source_epoch += 1
	_check("zero extinction still emits", optics.update(frame, settings))
	await _frames()
	var transparent_tau := _rd.texture_get_data(optics.optical_depth.texture_rd_rid, 0).to_float32_array()
	var maximum_tau := 0.0
	for value in transparent_tau:
		maximum_tau = maxf(maximum_tau, absf(value))
	var clear_light := _rd.texture_get_data(optics.radiance.texture_rd_rid, 0).to_float32_array()
	var luminosity := 0.0
	for index in range(0, clear_light.size(), 4):
		luminosity += float(clear_light[index]) + float(clear_light[index + 1]) + float(clear_light[index + 2])
	_check("transparent medium has zero tau and positive emission", maximum_tau == 0.0 and luminosity > 0.0)
	await _slab_and_light(optics, frame, settings)
	optics.shutdown()

func _slab_and_light(optics: RefCounted, frame: Dictionary, settings: Dictionary) -> void:
	const GRID := 48
	var ey := PackedFloat32Array()
	ey.resize(GRID * GRID * GRID)
	ey.fill(1.0)
	var ei := PackedFloat32Array()
	ei.resize(ey.size())
	var ey_rid := _rd.storage_buffer_create(ey.size() * 4, ey.to_byte_array())
	var ei_rid := _rd.storage_buffer_create(ei.size() * 4, ei.to_byte_array())
	_owned.append_array([ey_rid, ei_rid])
	frame.merge({"grid_size": GRID, "field_grid_size": GRID, "field_mode": true,
		"field_ey": ey_rid, "field_ei": ei_rid, "field_extents": Vector3.ONE,
		"field_origin_offset": Vector3.ZERO, "particle_count": 0}, true)
	settings.optical_thickness = 0.5
	settings.scattering = 0.0
	frame.source_epoch += 1
	optics.update(frame, settings)
	await _frames()
	var tau := _rd.texture_get_data(optics.optical_depth.texture_rd_rid, 0).to_float32_array()
	var radiance := _rd.texture_get_data(optics.radiance.texture_rd_rid, 0).to_float32_array()
	var pixel := 16 * 32 + 16
	var ray_length := 2.0 * sqrt(1.0 + 2.0 * pow(tan(deg_to_rad(15.0)) / 32.0, 2.0))
	var expected_tau := 0.5 * ray_length
	var measured_tau := float(tau[63 * 32 * 32 + pixel])
	var expected_red := 0.73 * (1.0 - exp(-expected_tau)) / 0.5
	var unscattered_red := float(radiance[4 * pixel])
	_check("reconstructed slab obeys Beer-Lambert column", absf(measured_tau / expected_tau - 1.0) < 0.005)
	_check("slab radiance matches analytic emission and absorption", absf(unscattered_red / expected_red - 1.0) < 0.005)
	settings.scattering = 0.7
	optics.update(frame, settings)
	await _frames()
	radiance = _rd.texture_get_data(optics.radiance.texture_rd_rid, 0).to_float32_array()
	_check("incident illumination adds bounded first scattering", float(radiance[4 * pixel]) > unscattered_red and float(radiance[4 * pixel]) < unscattered_red * 1.7)
	for x in GRID:
		for y in GRID:
			ey[x * GRID * GRID + y * GRID + 24] = 16.0
	_rd.buffer_update(ey_rid, 0, ey.size() * 4, ey.to_byte_array())
	frame.source_epoch += 1
	optics.update(frame, settings)
	await _frames()
	var light := _rd.texture_get_data(optics.get("_light_state_tex"), 0).to_float32_array()
	var before := float(light[4 * (23 * GRID * GRID + 24 * GRID + 24)])
	var after := float(light[4 * (24 * GRID * GRID + 24 * GRID + 24)])
	var expected_transmission := exp(-16.0 * 0.5 * 2.0 / float(GRID))
	# Separate the occluder's own emission to measure transport of incident light.
	var transmitted := after - 0.22 / 0.5 * (1.0 - expected_transmission)
	_check("dense occluder attenuates incident illumination", before > 0.0 and absf(transmitted / before - expected_transmission) < 0.005)
	_receipt["slab"] = {"tau": measured_tau, "expected_tau": expected_tau,
		"radiance_red": unscattered_red, "expected_red": expected_red,
		"shadow_transmission": transmitted / maxf(before, 1e-20), "expected_shadow": expected_transmission}
	_write_bytes("slab_light.bin", _rd.texture_get_data(optics.get("_light_state_tex"), 0))
	settings.emission = 0.0
	optics.update(frame, settings)
	await _frames()
	radiance = _rd.texture_get_data(optics.radiance.texture_rd_rid, 0).to_float32_array()
	var maximum_light := 0.0
	for index in range(0, radiance.size(), 4):
		for channel in 3: maximum_light = maxf(maximum_light, absf(radiance[index + channel]))
	_check("zero emission has no fictitious incident light", maximum_light == 0.0)
	ey.fill(0.0)
	_rd.buffer_update(ey_rid, 0, ey.size() * 4, ey.to_byte_array())
	frame.source_epoch += 1
	settings.emission = 1.0
	optics.update(frame, settings)
	await _frames()
	radiance = _rd.texture_get_data(optics.radiance.texture_rd_rid, 0).to_float32_array()
	tau = _rd.texture_get_data(optics.optical_depth.texture_rd_rid, 0).to_float32_array()
	var empty := true
	for value in radiance: empty = empty and is_finite(value) and value == 0.0
	for value in tau: empty = empty and is_finite(value) and value == 0.0
	_check("empty optical volume is finite and transparent", empty)

func _write_bytes(name: String, bytes: PackedByteArray) -> void:
	var file := FileAccess.open(OUTPUT.path_join(name), FileAccess.WRITE)
	file.store_buffer(bytes)
	file.close()
