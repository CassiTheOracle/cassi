extends RefCounted
## Default-off field-authoritative particle sector.
##
## The canonical state is the PA12 field itself. Point-like objects are derived
## readouts only; clearing a readout cannot affect subsequent evolution. The
## temporal normalization is the explicit experimental unit choice registered
## in research/field_particles/field_particle_dynamics_prereg.md.

const SHADER_PATH := "res://compute/cassi_field_particle.glsl"
const DEFAULT_SEED_PATH := "res://data/field_particles/localized_x2_n29.f32"
const DEFAULT_MANIFEST_PATH := "res://data/field_particles/localized_x2_n29.json"
const PINNED_MANIFEST_SHA256 := "280b44e7962e228a4791c6bb3506479395ccefe5068c1f0e4aa8a1a2c245ae8c"
const PINNED_SOURCE_SHA256 := "db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0"
const PINNED_OUTPUT_SHA256 := "5d43794099f52f4343486a2f1b38787356301153bd48d033d0d42451160ab6d3"
const PINNED_FIELD_ORDER := [
	"psi_0_real", "psi_0_imag", "psi_1_real", "psi_1_imag",
	"h_1", "h_2", "h_3", "chi_real", "chi_imag",
	"a_x_1", "a_x_2", "a_x_3", "a_y_1", "a_y_2", "a_y_3",
	"a_z_1", "a_z_2", "a_z_3",
]
const STATE_STRIDE := 18
const VELOCITY_STRIDE := 16
const WORKGROUP_SIZE := 64
const PSI0_RE := 0
const PSI0_IM := 1
const PSI1_RE := 2
const PSI1_IM := 3
const H0 := 4
const H1 := 5
const H2 := 6
const CHI_RE := 7
const CHI_IM := 8
const AX0 := 9

var grid_n := 0
var cells := 0
var radius := 0.0
var extent := 0.0
var dx := 0.0
var dt := 0.01
var fd_epsilon := 1.0 / 32.0
var phi := 1.618033988749895
var u_rho := 4.0
var u_phi := 4.0
var gamma_x := 1.0
var u_h := 4.0
var k_cx := 1.0
var e_c := 0.75
var h_c := 2.9598260763447164
var u_c := 1.0
var c_psi := 1.0
var c_h := 1.0
var e_tx := 1.0
var catalog_threshold_fraction := 0.05

var _rd: RenderingDevice
var _rd_global := true
var _owns_rd := false
var _shader := RID()
var _pipeline := RID()
var _state := [RID(), RID(), RID()]
var _velocity := [RID(), RID(), RID()]
var _gradient := RID()
var _state_accumulator := RID()
var _velocity_accumulator := RID()
var _uniform_sets := [RID(), RID(), RID(), RID()]
var _ready := false
var _shutdown := false
var _pc := PackedByteArray()
var _manifest: Dictionary = {}
var _seed_bytes := PackedByteArray()
var _step_count := 0
var _time := 0.0
var _catalog_cache: Array[Dictionary] = []
var _catalog_valid := false
var _energy_cache := 0.0
var _energy_valid := false
var _legacy_dispatches := {
	"deposit": 0,
	"kdk": 0,
	"accretion": 0,
	"merge": 0,
}


func setup(cfg: Dictionary) -> bool:
	if _shutdown:
		push_error("[FieldParticleEngine] setup called after shutdown")
		return false
	_rd = cfg.get("rd") as RenderingDevice
	if _rd == null:
		push_error("[FieldParticleEngine] setup requires cfg.rd")
		return false
	_rd_global = bool(cfg.get("rd_global", true))
	_owns_rd = bool(cfg.get("owns_rd", false))
	dt = float(cfg.get("dt", dt))
	fd_epsilon = float(cfg.get("fd_epsilon", fd_epsilon))
	catalog_threshold_fraction = float(cfg.get(
		"catalog_threshold_fraction", catalog_threshold_fraction))
	if dt < 0.0 or fd_epsilon <= 0.0:
		push_error("[FieldParticleEngine] dt must be nonnegative and fd_epsilon positive")
		return false

	var manifest_path := str(cfg.get("manifest_path", DEFAULT_MANIFEST_PATH))
	var seed_path := str(cfg.get("seed_path", DEFAULT_SEED_PATH))
	if not _load_manifest(manifest_path, seed_path):
		return false
	if not _load_pipeline(cfg):
		return false
	if not _make_buffers():
		return false
	_fill_push_constants(dt, 0)
	_ready = true
	print("[FieldParticleEngine] ready N=%d cells=%d dt=%.6f state_sha256=%s" % [
		grid_n, cells, dt, str(_manifest.get("output_sha256", ""))])
	return true


func _load_manifest(manifest_path: String, seed_path: String) -> bool:
	if FileAccess.get_sha256(manifest_path) != PINNED_MANIFEST_SHA256:
		push_error("[FieldParticleEngine] refusing an unregistered seed manifest")
		return false
	var text := FileAccess.get_file_as_string(manifest_path)
	var parsed = JSON.parse_string(text)
	if not parsed is Dictionary:
		push_error("[FieldParticleEngine] invalid manifest: %s" % manifest_path)
		return false
	_manifest = parsed
	if str(_manifest.get("schema", "")) != "cassi.field-particle-seed.v1":
		push_error("[FieldParticleEngine] unsupported seed manifest schema")
		return false
	var field_order = _manifest.get("field_order", [])
	var metadata_ok: bool = (
		str(_manifest.get("source_sha256", "")) == PINNED_SOURCE_SHA256
		and str(_manifest.get("output_sha256", "")) == PINNED_OUTPUT_SHA256
		and str(_manifest.get("source", "")) == "CassiTheory/runs/20260902_particle_carrier_resolution_recovery/fields_resolution_X2_block01.npz"
		and str(_manifest.get("output", "")) == "data/field_particles/localized_x2_n29.f32"
		and field_order is Array
		and field_order == PINNED_FIELD_ORDER
		and int(_manifest.get("grid_n", 0)) == 29
		and absf(float(_manifest.get("radius", NAN)) - 4.0) <= 1.0e-15
		and absf(float(_manifest.get("extent", NAN)) - 8.0) <= 1.0e-15
		and absf(float(_manifest.get("dx", NAN)) - (2.0 / 7.0)) <= 1.0e-15
		and absf(float(_manifest.get("omega_c", NAN)) - 0.0034164531971490053) <= 1.0e-15
	)
	var coefficients = _manifest.get("coefficients", {})
	metadata_ok = metadata_ok and coefficients is Dictionary
	if metadata_ok:
		metadata_ok = (
			absf(float(coefficients.get("h_C", NAN)) - 2.9598260763447164) <= 1.0e-15
			and absf(float(coefficients.get("q_C", NAN)) - 4.0) <= 1.0e-15
		)
	if not metadata_ok:
		push_error("[FieldParticleEngine] manifest does not match the frozen PA42 seed contract")
		return false

	grid_n = int(_manifest["grid_n"])
	cells = grid_n * grid_n * grid_n
	radius = float(_manifest["radius"])
	extent = float(_manifest["extent"])
	dx = float(_manifest["dx"])
	phi = float(coefficients.get("phi", phi))
	u_rho = float(coefficients.get("u_rho", u_rho))
	u_phi = float(coefficients.get("u_phi", u_phi))
	gamma_x = float(coefficients.get("gamma_x", gamma_x))
	u_h = float(coefficients.get("u_H", u_h))
	k_cx = float(coefficients.get("k_Cx", k_cx))
	e_c = float(coefficients.get("e_C", e_c))
	h_c = float(coefficients.get("h_C", h_c))
	u_c = float(coefficients.get("u_C", u_c))
	var temporal = _manifest.get("temporal_coefficients", {})
	if temporal is Dictionary:
		c_psi = float(temporal.get("c_psi", c_psi))
		c_h = float(temporal.get("c_h", c_h))
		e_tx = float(temporal.get("e_tx", e_tx))
	var numeric_values := [
		radius, extent, dx, phi, u_rho, u_phi, gamma_x, u_h, k_cx,
		e_c, h_c, u_c, c_psi, c_h, e_tx,
	]
	for value in numeric_values:
		if is_nan(value) or is_inf(value):
			push_error("[FieldParticleEngine] manifest contains a non-finite coefficient")
			return false
	if minf(c_psi, minf(c_h, e_tx)) <= 0.0:
		push_error("[FieldParticleEngine] temporal inertias must be positive")
		return false

	_seed_bytes = FileAccess.get_file_as_bytes(seed_path)
	var expected_bytes := cells * STATE_STRIDE * 4
	if _seed_bytes.size() != expected_bytes or int(_manifest.get("bytes", -1)) != expected_bytes:
		push_error("[FieldParticleEngine] seed byte count mismatch")
		return false
	var actual_hash := FileAccess.get_sha256(seed_path)
	if actual_hash != PINNED_OUTPUT_SHA256:
		push_error("[FieldParticleEngine] seed SHA-256 mismatch")
		return false
	if not _validate_state(_seed_bytes):
		push_error("[FieldParticleEngine] seed has non-finite values or a non-vacuum shell")
		return false
	return true


func _load_pipeline(cfg: Dictionary) -> bool:
	var spirv: RDShaderSPIRV
	var supplied = cfg.get("spirv", null)
	if supplied is Dictionary and supplied.has(SHADER_PATH):
		spirv = supplied[SHADER_PATH] as RDShaderSPIRV
	if spirv == null:
		var shader_file := load(SHADER_PATH) as RDShaderFile
		if shader_file == null:
			push_error("[FieldParticleEngine] shader resource did not load")
			return false
		spirv = shader_file.get_spirv()
	_shader = _rd.shader_create_from_spirv(spirv)
	if not _shader.is_valid():
		push_error("[FieldParticleEngine] shader creation failed")
		return false
	_pipeline = _rd.compute_pipeline_create(_shader)
	if not _pipeline.is_valid():
		push_error("[FieldParticleEngine] pipeline creation failed")
		return false
	return true


func _make_buffers() -> bool:
	var state_bytes := cells * STATE_STRIDE * 4
	var velocity_bytes := cells * VELOCITY_STRIDE * 4
	var zero_velocity := PackedByteArray()
	zero_velocity.resize(velocity_bytes)
	var zero_state := PackedByteArray()
	zero_state.resize(state_bytes)
	for index in 3:
		_state[index] = _rd.storage_buffer_create(state_bytes, _seed_bytes)
		_velocity[index] = _rd.storage_buffer_create(velocity_bytes, zero_velocity)
	_gradient = _rd.storage_buffer_create(state_bytes, zero_state)
	_state_accumulator = _rd.storage_buffer_create(state_bytes, zero_state)
	_velocity_accumulator = _rd.storage_buffer_create(velocity_bytes, zero_velocity)
	for rid in [
		_state[0], _state[1], _state[2],
		_velocity[0], _velocity[1], _velocity[2],
		_gradient, _state_accumulator, _velocity_accumulator,
	]:
		if not rid.is_valid():
			push_error("[FieldParticleEngine] storage-buffer creation failed")
			return false
	_uniform_sets[0] = _make_uniform_set(0, 1)
	_uniform_sets[1] = _make_uniform_set(1, 2)
	_uniform_sets[2] = _make_uniform_set(2, 1)
	_uniform_sets[3] = _make_uniform_set(1, 0)
	for uniform_set in _uniform_sets:
		if not uniform_set.is_valid():
			push_error("[FieldParticleEngine] uniform-set creation failed")
			return false
	return true


func _make_uniform_set(input_index: int, output_index: int) -> RID:
	return _rd.uniform_set_create([
		_uniform(0, _state[input_index]),
		_uniform(1, _velocity[input_index]),
		_uniform(2, _state[output_index]),
		_uniform(3, _velocity[output_index]),
		_uniform(4, _gradient),
		_uniform(5, _state[0]),
		_uniform(6, _velocity[0]),
		_uniform(7, _state_accumulator),
		_uniform(8, _velocity_accumulator),
	], _shader, 0)


func _uniform(binding: int, buffer: RID) -> RDUniform:
	var uniform := RDUniform.new()
	uniform.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	uniform.binding = binding
	uniform.add_id(buffer)
	return uniform


func is_ready() -> bool:
	return _ready


func manifest() -> Dictionary:
	return _manifest.duplicate(true)


func step_count() -> int:
	return _step_count


func simulation_time() -> float:
	return _time


func state_rid() -> RID:
	return _state[0] if _ready else RID()


func velocity_rid() -> RID:
	return _velocity[0] if _ready else RID()


func legacy_dispatch_counts() -> Dictionary:
	return _legacy_dispatches.duplicate(true)


## Record evolution into an already-open compute list. This is the global-RD
## integration seam; it never submits or synchronizes the shared device.
func record_steps(compute_list: int, count: int, step_dt: float = -1.0) -> int:
	if not _ready or count <= 0:
		return 0
	var use_dt := dt if step_dt < 0.0 else step_dt
	if use_dt < 0.0:
		return 0
	var gradient_groups := ceili(float(cells * STATE_STRIDE) / float(WORKGROUP_SIZE))
	var cell_groups := ceili(float(cells) / float(WORKGROUP_SIZE))
	for _index in range(count):
		_rd.compute_list_bind_compute_pipeline(compute_list, _pipeline)
		for stage in 4:
			_rd.compute_list_bind_uniform_set(compute_list, _uniform_sets[stage], 0)
			_fill_push_constants(use_dt, 0)
			_rd.compute_list_set_push_constant(compute_list, _pc, _pc.size())
			_rd.compute_list_dispatch(compute_list, gradient_groups, 1, 1)
			_rd.compute_list_add_barrier(compute_list)
			_fill_push_constants(use_dt, stage + 1)
			_rd.compute_list_set_push_constant(compute_list, _pc, _pc.size())
			_rd.compute_list_dispatch(compute_list, cell_groups, 1, 1)
			_rd.compute_list_add_barrier(compute_list)
		if use_dt > 0.0:
			_step_count += 1
			_time += use_dt
	_invalidate_readouts()
	return count


## Local-RD convenience path. A global RenderingDevice is owned by the renderer
## and must use record_steps() inside its frame list instead.
func run_steps(count: int, wait := true, step_dt: float = -1.0) -> bool:
	if not _ready or _rd_global:
		return false
	var compute_list := _rd.compute_list_begin()
	var recorded := record_steps(compute_list, count, step_dt)
	_rd.compute_list_end()
	_rd.submit()
	if wait:
		_rd.sync()
	return recorded == count


func _fill_push_constants(step_dt: float, pass_sel: int) -> void:
	_pc.resize(68)
	_pc.encode_u32(0, grid_n)
	_pc.encode_float(4, step_dt)
	_pc.encode_float(8, dx)
	_pc.encode_float(12, fd_epsilon)
	_pc.encode_float(16, phi)
	_pc.encode_float(20, u_rho)
	_pc.encode_float(24, u_phi)
	_pc.encode_float(28, gamma_x)
	_pc.encode_float(32, u_h)
	_pc.encode_float(36, k_cx)
	_pc.encode_float(40, e_c)
	_pc.encode_float(44, h_c)
	_pc.encode_float(48, u_c)
	_pc.encode_float(52, c_psi)
	_pc.encode_float(56, c_h)
	_pc.encode_float(60, e_tx)
	_pc.encode_u32(64, pass_sel)


func state_bytes() -> PackedByteArray:
	if not _ready:
		return PackedByteArray()
	return _rd.buffer_get_data(_state[0], 0, cells * STATE_STRIDE * 4)


func velocity_bytes() -> PackedByteArray:
	if not _ready:
		return PackedByteArray()
	return _rd.buffer_get_data(_velocity[0], 0, cells * VELOCITY_STRIDE * 4)

func hamiltonian_gradient_bytes() -> PackedByteArray:
	if not _ready:
		return PackedByteArray()
	return _rd.buffer_get_data(_gradient, 0, cells * STATE_STRIDE * 4)


func reset_seed() -> bool:
	return set_state(_seed_bytes)


func set_state(bytes: PackedByteArray, velocities := PackedByteArray()) -> bool:
	if not _ready or bytes.size() != cells * STATE_STRIDE * 4 or not _validate_state(bytes):
		return false
	var velocity_data: PackedByteArray = velocities
	if velocity_data.is_empty():
		velocity_data.resize(cells * VELOCITY_STRIDE * 4)
	if velocity_data.size() != cells * VELOCITY_STRIDE * 4:
		return false
	var values := velocity_data.to_float32_array()
	for value in values:
		if is_nan(value) or is_inf(value):
			return false
	for index in 3:
		_rd.buffer_update(_state[index], 0, bytes.size(), bytes)
		_rd.buffer_update(_velocity[index], 0, velocity_data.size(), velocity_data)
	var zero_state := PackedByteArray()
	zero_state.resize(bytes.size())
	var zero_velocity := PackedByteArray()
	zero_velocity.resize(velocity_data.size())
	_rd.buffer_update(_state_accumulator, 0, zero_state.size(), zero_state)
	_rd.buffer_update(_velocity_accumulator, 0, zero_velocity.size(), zero_velocity)
	_step_count = 0
	_time = 0.0
	_invalidate_readouts()
	return true


func load_vacuum() -> bool:
	if not _ready:
		return false
	var values := PackedFloat32Array()
	values.resize(cells * STATE_STRIDE)
	var psi0 := sqrt(1.0 / phi)
	var psi1 := 1.0 / phi
	for cell in range(cells):
		var base := cell * STATE_STRIDE
		values[base + PSI0_RE] = psi0
		values[base + PSI1_RE] = psi1
		values[base + H2] = 1.0
	return set_state(values.to_byte_array())


## Apply a low-speed translational initialization without creating point state.
## Second-order fields receive -v·grad(q); the carrier receives the standard
## unit-dispersion phase exp(i v·x).
func apply_boost(direction: Vector3, speed: float) -> bool:
	if not _ready or speed < 0.0 or direction.length_squared() <= 0.0:
		return false
	var unit := direction.normalized()
	var bytes := state_bytes()
	var source := bytes.to_float32_array()
	var boosted := source.duplicate()
	var velocities := PackedFloat32Array()
	velocities.resize(cells * VELOCITY_STRIDE)
	for z in range(grid_n):
		for y in range(grid_n):
			for x in range(grid_n):
				var cell := _index(x, y, z)
				var base := cell * STATE_STRIDE
				var position := _position(x, y, z)
				var phase := speed * unit.dot(position)
				var cosine := cos(phase)
				var sine := sin(phase)
				var carrier_re := source[base + CHI_RE]
				var carrier_im := source[base + CHI_IM]
				boosted[base + CHI_RE] = carrier_re * cosine - carrier_im * sine
				boosted[base + CHI_IM] = carrier_re * sine + carrier_im * cosine
				if _is_boundary(x, y, z):
					continue
				for component in range(STATE_STRIDE):
					var velocity_component := _velocity_component(component)
					if velocity_component < 0:
						continue
					var directional := (
						unit.x * _derivative(source, x, y, z, component, 0)
						+ unit.y * _derivative(source, x, y, z, component, 1)
						+ unit.z * _derivative(source, x, y, z, component, 2)
					)
					velocities[cell * VELOCITY_STRIDE + velocity_component] = -speed * directional
	return set_state(boosted.to_byte_array(), velocities.to_byte_array())


func _validate_state(bytes: PackedByteArray) -> bool:
	if bytes.size() != cells * STATE_STRIDE * 4:
		return false
	var values := bytes.to_float32_array()
	for value in values:
		if is_nan(value) or is_inf(value):
			return false
	var vacuum := PackedFloat32Array([
		float(_manifest.get("coefficients", {}).get("phi", phi)) ** -0.5,
		1.0 / float(_manifest.get("coefficients", {}).get("phi", phi)),
		1.0,
	])
	for z in range(grid_n):
		for y in range(grid_n):
			for x in range(grid_n):
				if not _is_boundary(x, y, z):
					continue
				var base := _index(x, y, z) * STATE_STRIDE
				for component in range(STATE_STRIDE):
					var expected := 0.0
					if component == PSI0_RE:
						expected = vacuum[0]
					elif component == PSI1_RE:
						expected = vacuum[1]
					elif component == H2:
						expected = vacuum[2]
					if values[base + component] != float(expected):
						return false
	return true


func _invalidate_readouts() -> void:
	_catalog_valid = false
	_energy_valid = false


func clear_object_catalog() -> void:
	_catalog_cache.clear()
	_catalog_valid = false


func _box_smoothed_density(density: PackedFloat32Array) -> PackedFloat32Array:
	var smoothed := PackedFloat32Array()
	smoothed.resize(cells)
	for z in range(grid_n):
		for y in range(grid_n):
			for x in range(grid_n):
				var sum := 0.0
				var samples := 0
				for offset_z in range(-1, 2):
					var sample_z := z + offset_z
					if sample_z < 0 or sample_z >= grid_n:
						continue
					for offset_y in range(-1, 2):
						var sample_y := y + offset_y
						if sample_y < 0 or sample_y >= grid_n:
							continue
						for offset_x in range(-1, 2):
							var sample_x := x + offset_x
							if sample_x < 0 or sample_x >= grid_n:
								continue
							sum += density[_index(sample_x, sample_y, sample_z)]
							samples += 1
				smoothed[_index(x, y, z)] = sum / float(samples)
	return smoothed


## Box-smoothed connected carrier cores seed the observational catalog.
## Every raw carrier-density cell is assigned to its nearest retained core,
## so tails remain part of field-derived charge.
func object_catalog() -> Array[Dictionary]:
	if _catalog_valid:
		return _catalog_cache.duplicate(true)
	var state_values := state_bytes().to_float32_array()
	var velocity_values := velocity_bytes().to_float32_array()
	var density := PackedFloat32Array()
	density.resize(cells)
	var total_density := 0.0
	for cell in range(cells):
		var base := cell * STATE_STRIDE
		var value := (
			state_values[base + CHI_RE] * state_values[base + CHI_RE]
			+ state_values[base + CHI_IM] * state_values[base + CHI_IM]
		)
		density[cell] = value
		total_density += value
	var smoothed_density := _box_smoothed_density(density)
	var peak := 0.0
	for value in smoothed_density:
		peak = maxf(peak, value)
	if peak <= 0.0 or total_density * dx * dx * dx <= 1.0e-10:
		_catalog_cache = []
		_catalog_valid = true
		return []

	var labels := PackedInt32Array()
	labels.resize(cells)
	labels.fill(-1)
	var core_centers: Array[Vector3] = []
	var core_peaks: Array[float] = []
	var core_cells: Array[int] = []
	var threshold := peak * catalog_threshold_fraction
	for seed in range(cells):
		if labels[seed] >= 0 or smoothed_density[seed] < threshold:
			continue
		var queue := PackedInt32Array([seed])
		var queue_head := 0
		var label := core_centers.size()
		labels[seed] = label
		var weighted_position := Vector3.ZERO
		var weight := 0.0
		var component_peak := 0.0
		var component_cells := 0
		while queue_head < queue.size():
			var cell := queue[queue_head]
			queue_head += 1
			var xyz := _coordinates(cell)
			var local_density := smoothed_density[cell]
			weighted_position += _position(xyz.x, xyz.y, xyz.z) * local_density
			weight += local_density
			component_peak = maxf(component_peak, density[cell])
			component_cells += 1
			for neighbor in _neighbors(xyz.x, xyz.y, xyz.z):
				if labels[neighbor] < 0 and smoothed_density[neighbor] >= threshold:
					labels[neighbor] = label
					queue.append(neighbor)
		if weight > 0.0 and component_cells > 1:
			core_centers.append(weighted_position / weight)
			core_peaks.append(component_peak)
			core_cells.append(component_cells)
	if core_centers.is_empty():
		_catalog_cache = []
		_catalog_valid = true
		return []

	var assignment := PackedInt32Array()
	assignment.resize(cells)
	var charge_sums: Array[float] = []
	var center_sums: Array[Vector3] = []
	var current_sums: Array[Vector3] = []
	for _component in core_centers.size():
		charge_sums.append(0.0)
		center_sums.append(Vector3.ZERO)
		current_sums.append(Vector3.ZERO)
	for cell in range(cells):
		var xyz := _coordinates(cell)
		var position := _position(xyz.x, xyz.y, xyz.z)
		var owner := 0
		var nearest := INF
		for component in core_centers.size():
			var distance := position.distance_squared_to(core_centers[component])
			if distance < nearest:
				nearest = distance
				owner = component
		assignment[cell] = owner
		var local_density := density[cell]
		charge_sums[owner] += local_density
		center_sums[owner] += position * local_density
		var base := cell * STATE_STRIDE
		var carrier_re := state_values[base + CHI_RE]
		var carrier_im := state_values[base + CHI_IM]
		var grad_re := Vector3(
			_derivative(state_values, xyz.x, xyz.y, xyz.z, CHI_RE, 0),
			_derivative(state_values, xyz.x, xyz.y, xyz.z, CHI_RE, 1),
			_derivative(state_values, xyz.x, xyz.y, xyz.z, CHI_RE, 2))
		var grad_im := Vector3(
			_derivative(state_values, xyz.x, xyz.y, xyz.z, CHI_IM, 0),
			_derivative(state_values, xyz.x, xyz.y, xyz.z, CHI_IM, 1),
			_derivative(state_values, xyz.x, xyz.y, xyz.z, CHI_IM, 2))
		current_sums[owner] += carrier_re * grad_im - carrier_im * grad_re

	var centers: Array[Vector3] = []
	var radii_squared: Array[float] = []
	for component in core_centers.size():
		var weight := charge_sums[component]
		centers.append(center_sums[component] / weight if weight > 0.0 else core_centers[component])
		radii_squared.append(0.0)
	for cell in range(cells):
		var owner := assignment[cell]
		var xyz := _coordinates(cell)
		var offset := _position(xyz.x, xyz.y, xyz.z) - centers[owner]
		radii_squared[owner] += density[cell] * offset.length_squared()

	var total_energy := physical_energy()
	var objects: Array[Dictionary] = []
	var cell_volume := dx * dx * dx
	for component in core_centers.size():
		var density_sum := charge_sums[component]
		var charge := density_sum * cell_volume
		if charge <= 1.0e-8:
			continue
		objects.append({
			"id": component,
			"charge": charge,
			"center": centers[component],
			"radius": sqrt(maxf(radii_squared[component] / density_sum, 0.0)),
			"velocity": current_sums[component] / density_sum,
			"energy_proxy": total_energy * density_sum / total_density,
			"peak_density": core_peaks[component],
			"core_cells": core_cells[component],
		})
	_catalog_cache = objects
	_catalog_valid = true
	return objects.duplicate(true)


func observables() -> Dictionary:
	var objects := object_catalog()
	var state_values := state_bytes().to_float32_array()
	var total_charge := 0.0
	var weighted_center := Vector3.ZERO
	var weighted_velocity := Vector3.ZERO
	var weighted_radius2 := 0.0
	for object in objects:
		var charge := float(object["charge"])
		total_charge += charge
		weighted_center += Vector3(object["center"]) * charge
		weighted_velocity += Vector3(object["velocity"]) * charge
	if total_charge > 0.0:
		weighted_center /= total_charge
		weighted_velocity /= total_charge
		for object in objects:
			var charge := float(object["charge"])
			var center_offset := Vector3(object["center"]) - weighted_center
			weighted_radius2 += charge * (
				float(object["radius"]) * float(object["radius"])
				+ center_offset.length_squared())
	var outer_density := 0.0
	var total_density := 0.0
	var finite := true
	var density_square_sum := 0.0
	for cell in range(cells):
		var base := cell * STATE_STRIDE
		for component in range(STATE_STRIDE):
			var value := state_values[base + component]
			finite = finite and not is_nan(value) and not is_inf(value)
		var density := (
			state_values[base + CHI_RE] * state_values[base + CHI_RE]
			+ state_values[base + CHI_IM] * state_values[base + CHI_IM])
		total_density += density
		density_square_sum += density * density
		var xyz := _coordinates(cell)
		if xyz.x <= 1 or xyz.y <= 1 or xyz.z <= 1 or \
				xyz.x >= grid_n - 2 or xyz.y >= grid_n - 2 or xyz.z >= grid_n - 2:
			outer_density += density
	return {
		"charge": total_charge,
		"center": weighted_center,
		"radius": sqrt(maxf(weighted_radius2 / total_charge, 0.0)) if total_charge > 0.0 else 0.0,
		"velocity": weighted_velocity,
		"component_count": objects.size(),
		"physical_energy": physical_energy(),
		"outer_carrier_fraction": outer_density / total_density if total_density > 0.0 else 0.0,
		"carrier_density_rms": sqrt(density_square_sum / float(cells)),
		"finite": finite,
	}


func physical_energy() -> float:
	if _energy_valid:
		return _energy_cache
	var values := state_bytes().to_float32_array()
	var total := 0.0
	for z in range(grid_n):
		for y in range(grid_n):
			for x in range(grid_n):
				total += _energy_density(values, x, y, z)
	_energy_cache = total * dx * dx * dx
	_energy_valid = true
	return _energy_cache


func _energy_density(values: PackedFloat32Array, x: int, y: int, z: int) -> float:
	var base := _index(x, y, z) * STATE_STRIDE
	var psi0 := Vector2(values[base + PSI0_RE], values[base + PSI0_IM])
	var psi1 := Vector2(values[base + PSI1_RE], values[base + PSI1_IM])
	var h := Vector3(values[base + H0], values[base + H1], values[base + H2])
	var chi := Vector2(values[base + CHI_RE], values[base + CHI_IM])
	var rho := psi0.length_squared() + psi1.length_squared()
	var spin := Vector3(
		2.0 * (psi0.x * psi1.x + psi0.y * psi1.y),
		2.0 * (psi0.x * psi1.y - psi0.y * psi1.x),
		psi0.length_squared() - psi1.length_squared())
	var delta_phi := 0.5 * ((1.0 - phi) * rho + (1.0 + phi) * h.dot(spin))
	var result := 0.25 * u_rho * (rho - 1.0) * (rho - 1.0)
	result += 0.5 * u_phi * delta_phi * delta_phi
	var h_error := h.length_squared() - 1.0
	result += 0.25 * u_h * h_error * h_error
	var chi_density := chi.length_squared()
	result += (e_c - h_c * (1.0 - rho)) * chi_density
	result += 0.5 * u_c * chi_density * chi_density
	var gauge: Array[Vector3] = [
		Vector3(values[base + AX0], values[base + AX0 + 1], values[base + AX0 + 2]),
		Vector3(values[base + AX0 + 3], values[base + AX0 + 4], values[base + AX0 + 5]),
		Vector3(values[base + AX0 + 6], values[base + AX0 + 7], values[base + AX0 + 8]),
	]
	for axis in 3:
		var dpsi0 := Vector2(
			_derivative(values, x, y, z, PSI0_RE, axis),
			_derivative(values, x, y, z, PSI0_IM, axis))
		var dpsi1 := Vector2(
			_derivative(values, x, y, z, PSI1_RE, axis),
			_derivative(values, x, y, z, PSI1_IM, axis))
		var acted := _gauge_action(gauge[axis], psi0, psi1)
		var covariant0 := dpsi0 + _multiply_minus_i(acted[0])
		var covariant1 := dpsi1 + _multiply_minus_i(acted[1])
		result += 0.5 * (covariant0.length_squared() + covariant1.length_squared())
		var dh := Vector3(
			_derivative(values, x, y, z, H0, axis),
			_derivative(values, x, y, z, H1, axis),
			_derivative(values, x, y, z, H2, axis))
		var covariant_h := dh + gauge[axis].cross(h)
		result += 0.5 * gamma_x * covariant_h.length_squared()
		var dchi := Vector2(
			_derivative(values, x, y, z, CHI_RE, axis),
			_derivative(values, x, y, z, CHI_IM, axis))
		result += 0.5 * k_cx * dchi.length_squared()
	for i in 3:
		for j in range(i + 1, 3):
			var d_i_a_j := Vector3(
				_derivative(values, x, y, z, AX0 + 3 * j, i),
				_derivative(values, x, y, z, AX0 + 3 * j + 1, i),
				_derivative(values, x, y, z, AX0 + 3 * j + 2, i))
			var d_j_a_i := Vector3(
				_derivative(values, x, y, z, AX0 + 3 * i, j),
				_derivative(values, x, y, z, AX0 + 3 * i + 1, j),
				_derivative(values, x, y, z, AX0 + 3 * i + 2, j))
			var curvature := d_i_a_j - d_j_a_i + gauge[i].cross(gauge[j])
			result += 0.5 * gamma_x * curvature.length_squared()
	return result


func gauss_rms() -> float:
	var state_values := state_bytes().to_float32_array()
	var velocity_values := velocity_bytes().to_float32_array()
	var squares := 0.0
	var samples := 0
	for z in range(grid_n):
		for y in range(grid_n):
			for x in range(grid_n):
				var cell := _index(x, y, z)
				var state_base := cell * STATE_STRIDE
				var velocity_base := cell * VELOCITY_STRIDE
				var psi0 := Vector2(state_values[state_base + PSI0_RE], state_values[state_base + PSI0_IM])
				var psi1 := Vector2(state_values[state_base + PSI1_RE], state_values[state_base + PSI1_IM])
				var vpsi0 := Vector2(velocity_values[velocity_base], velocity_values[velocity_base + 1])
				var vpsi1 := Vector2(velocity_values[velocity_base + 2], velocity_values[velocity_base + 3])
				var h := Vector3(state_values[state_base + H0], state_values[state_base + H1], state_values[state_base + H2])
				var vh := Vector3(velocity_values[velocity_base + 4], velocity_values[velocity_base + 5], velocity_values[velocity_base + 6])
				var charge_psi := c_psi * Vector3(
					0.5 * (_complex_inner_imag(psi0, vpsi1) + _complex_inner_imag(psi1, vpsi0)),
					0.5 * (_complex_inner_imag(psi0, _multiply_minus_i(vpsi1)) + _complex_inner_imag(psi1, _multiply_i(vpsi0))),
					0.5 * (_complex_inner_imag(psi0, vpsi0) - _complex_inner_imag(psi1, vpsi1)))
				var charge_h := -c_h * h.cross(vh)
				var lhs := Vector3.ZERO
				for axis in 3:
					var e_component := AX0 - 2 + axis * 3
					var electric := Vector3(
						velocity_values[velocity_base + 7 + axis * 3],
						velocity_values[velocity_base + 8 + axis * 3],
						velocity_values[velocity_base + 9 + axis * 3])
					var gauge := Vector3(
						state_values[state_base + AX0 + axis * 3],
						state_values[state_base + AX0 + axis * 3 + 1],
						state_values[state_base + AX0 + axis * 3 + 2])
					lhs += Vector3(
						_derivative(velocity_values, x, y, z, e_component, axis, VELOCITY_STRIDE),
						_derivative(velocity_values, x, y, z, e_component + 1, axis, VELOCITY_STRIDE),
						_derivative(velocity_values, x, y, z, e_component + 2, axis, VELOCITY_STRIDE))
					lhs += gauge.cross(electric)
				var residual := e_tx * lhs - charge_psi - charge_h
				squares += residual.length_squared()
				samples += 3
	return sqrt(squares / float(maxi(samples, 1)))


func _complex_inner_imag(left: Vector2, right: Vector2) -> float:
	return left.x * right.y - left.y * right.x


func _gauge_action(gauge: Vector3, psi0: Vector2, psi1: Vector2) -> Array[Vector2]:
	return [
		0.5 * (gauge.x * psi1 + gauge.y * _multiply_minus_i(psi1) + gauge.z * psi0),
		0.5 * (gauge.x * psi0 + gauge.y * _multiply_i(psi0) - gauge.z * psi1),
	]


func _multiply_i(value: Vector2) -> Vector2:
	return Vector2(-value.y, value.x)


func _multiply_minus_i(value: Vector2) -> Vector2:
	return Vector2(value.y, -value.x)


func _velocity_component(component: int) -> int:
	if component <= H2:
		return component
	if component >= AX0:
		return 7 + component - AX0
	return -1


func _derivative(
	values: PackedFloat32Array,
	x: int,
	y: int,
	z: int,
	component: int,
	axis: int,
	stride: int = STATE_STRIDE
) -> float:
	var coordinate := x if axis == 0 else (y if axis == 1 else z)
	var p0 := _sample(values, x, y, z, component, stride)
	if coordinate == 0:
		var p1 := _shifted_sample(values, x, y, z, component, axis, 1, stride)
		var p2 := _shifted_sample(values, x, y, z, component, axis, 2, stride)
		return (-3.0 * p0 + 4.0 * p1 - p2) / (2.0 * dx)
	if coordinate == grid_n - 1:
		var p1 := _shifted_sample(values, x, y, z, component, axis, -1, stride)
		var p2 := _shifted_sample(values, x, y, z, component, axis, -2, stride)
		return (3.0 * p0 - 4.0 * p1 + p2) / (2.0 * dx)
	var plus := _shifted_sample(values, x, y, z, component, axis, 1, stride)
	var minus := _shifted_sample(values, x, y, z, component, axis, -1, stride)
	return (plus - minus) / (2.0 * dx)


func _shifted_sample(
	values: PackedFloat32Array,
	x: int,
	y: int,
	z: int,
	component: int,
	axis: int,
	offset: int,
	stride: int
) -> float:
	if axis == 0:
		x += offset
	elif axis == 1:
		y += offset
	else:
		z += offset
	return _sample(values, x, y, z, component, stride)


func _sample(
	values: PackedFloat32Array,
	x: int,
	y: int,
	z: int,
	component: int,
	stride: int
) -> float:
	return values[_index(x, y, z) * stride + component]


func _index(x: int, y: int, z: int) -> int:
	return x + grid_n * (y + grid_n * z)


func _coordinates(cell: int) -> Vector3i:
	var z := cell / (grid_n * grid_n)
	var remainder := cell - z * grid_n * grid_n
	var y := remainder / grid_n
	return Vector3i(remainder - y * grid_n, y, z)


func _position(x: int, y: int, z: int) -> Vector3:
	return Vector3(float(x) * dx - radius, float(y) * dx - radius, float(z) * dx - radius)


func _is_boundary(x: int, y: int, z: int) -> bool:
	var last := grid_n - 1
	return x == 0 or y == 0 or z == 0 or x == last or y == last or z == last


func _neighbors(x: int, y: int, z: int) -> PackedInt32Array:
	var result := PackedInt32Array()
	if x > 0:
		result.append(_index(x - 1, y, z))
	if x + 1 < grid_n:
		result.append(_index(x + 1, y, z))
	if y > 0:
		result.append(_index(x, y - 1, z))
	if y + 1 < grid_n:
		result.append(_index(x, y + 1, z))
	if z > 0:
		result.append(_index(x, y, z - 1))
	if z + 1 < grid_n:
		result.append(_index(x, y, z + 1))
	return result


func shutdown() -> void:
	if _shutdown:
		return
	_shutdown = true
	_ready = false
	if _rd == null:
		return
	for uniform_set in _uniform_sets:
		if uniform_set.is_valid() and _rd.uniform_set_is_valid(uniform_set):
			_rd.free_rid(uniform_set)
	for rid in [
		_velocity_accumulator, _state_accumulator, _gradient,
		_velocity[2], _velocity[1], _velocity[0],
		_state[2], _state[1], _state[0], _pipeline, _shader,
	]:
		if rid.is_valid():
			_rd.free_rid(rid)
	if _owns_rd:
		_rd.free()
	_rd = null
