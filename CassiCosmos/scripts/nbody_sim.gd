extends Node3D
## Cassi Qi O(1) N-body — FULLY GPU-side. Single compute list per frame.

@export var N: int = 2000
@export var G: float = 1.0
@export var softening: float = 0.4
@export var dt: float = 0.001
@export var playing: bool = true
@export var particle_size: float = 0.06
@export var cluster_radius: float = 5.0

@export_range(0.0, 100.0) var xi: float = 18.0
@export_range(0.5, 10.0) var qi_beta: float = 3.0
@export_range(0.3, 0.99) var pi_max: float = 0.55
@export_range(0.5, 10.0) var halo_radius: float = 3.0
@export_range(0.5, 5.0) var halo_width: float = 1.5

var _compute_ready: bool = false
var _retry_frames: int = 0

var _rd: RenderingDevice = null
var _gravity_shader: RID; var _gravity_pipeline: RID; var _gravity_set: RID
var _render_shader: RID;  var _render_pipeline: RID;  var _render_set: RID
var _pos_buf: RID; var _vel_buf: RID; var _acc_buf: RID; var _mm_buf: RID

var _mmi: MultiMeshInstance3D; var _mm: MultiMesh
var _step_count: int = 0; var _step_timer: float = 0.0

const PHI_INV3: float = (1.618033988749895 - 1.0) / (1.618033988749895 + 1.0)


func _ready() -> void:
	_setup_multimesh()
	_setup_compute()
	if _compute_ready:
		_init_bodies()
	else:
		_init_static_cluster()


func _process(delta: float) -> void:
	if not _compute_ready:
		_retry_frames += 1
		if _retry_frames % 5 == 0:
			_setup_compute()
			if _compute_ready:
				_init_bodies()
		return

	if not playing:
		_render_and_readback()
		return

	_step_timer += delta
	var n_steps := 0
	while _step_timer >= dt:
		_step_timer -= dt
		n_steps += 1
		_step_count += 1

	if n_steps == 0:
		return

	# Single compute list: gravity × N + render → one submit
	var cl = _rd.compute_list_begin()

	# Gravity dispatches
	var pc_g = PackedFloat32Array([
		float(N), G, softening * softening, xi,
		qi_beta, PHI_INV3, halo_radius, halo_width,
		pi_max, cluster_radius, float(N), dt,
		1.0, 0.0,
	])
	var wg_g = ceili(float(N) / 256.0)
	for _s in range(n_steps):
		_rd.compute_list_bind_compute_pipeline(cl, _gravity_pipeline)
		_rd.compute_list_bind_uniform_set(cl, _gravity_set, 0)
		_rd.compute_list_set_push_constant(cl, pc_g.to_byte_array(), 14 * 4)
		_rd.compute_list_dispatch(cl, int(wg_g), 1, 1)

	# Render dispatch
	var pc_r = PackedFloat32Array([float(N), particle_size, 0.0, 0.0])
	var wg_r = ceili(float(N) / 256.0)
	_rd.compute_list_bind_compute_pipeline(cl, _render_pipeline)
	_rd.compute_list_bind_uniform_set(cl, _render_set, 0)
	_rd.compute_list_set_push_constant(cl, pc_r.to_byte_array(), 4 * 4)
	_rd.compute_list_dispatch(cl, int(wg_r), 1, 1)

	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()

	var data = _rd.buffer_get_data(_mm_buf, 0, N * 64).to_float32_array()
	_mm.set_buffer(data)


func _render_and_readback() -> void:
	var cl = _rd.compute_list_begin()
	var pc_r = PackedFloat32Array([float(N), particle_size, 0.0, 0.0])
	var wg = ceili(float(N) / 256.0)
	_rd.compute_list_bind_compute_pipeline(cl, _render_pipeline)
	_rd.compute_list_bind_uniform_set(cl, _render_set, 0)
	_rd.compute_list_set_push_constant(cl, pc_r.to_byte_array(), 4 * 4)
	_rd.compute_list_dispatch(cl, int(wg), 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	var data = _rd.buffer_get_data(_mm_buf, 0, N * 64).to_float32_array()
	_mm.set_buffer(data)


# ── Compute pipeline setup ────────────────────────────────────────

func _setup_compute() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		push_error("[NBody] RenderingDevice failed")
		return

	var sf_g = load("res://compute/nbody_gravity.glsl")
	if sf_g == null: push_error("[NBody] gravity.glsl not found"); return
	var spv_g = sf_g.get_spirv()
	if spv_g == null: push_error("[NBody] gravity SPIR-V FAILED"); return
	_gravity_shader = _rd.shader_create_from_spirv(spv_g)
	_gravity_pipeline = _rd.compute_pipeline_create(_gravity_shader)

	var sf_r = load("res://compute/nbody_render.glsl")
	if sf_r == null: push_error("[NBody] render.glsl not found"); return
	var spv_r = sf_r.get_spirv()
	if spv_r == null: push_error("[NBody] render SPIR-V FAILED"); return
	_render_shader = _rd.shader_create_from_spirv(spv_r)
	_render_pipeline = _rd.compute_pipeline_create(_render_shader)

	_compute_ready = true
	print("[NBody] Full GPU pipeline ready (%.0f particles)" % N)


func _create_buffers() -> void:
	for rid in [_pos_buf, _vel_buf, _acc_buf, _mm_buf]:
		if rid.is_valid(): _rd.free_rid(rid)

	var sz_part = N * 4 * 4
	_pos_buf = _rd.storage_buffer_create(sz_part)
	_vel_buf = _rd.storage_buffer_create(sz_part)
	_acc_buf = _rd.storage_buffer_create(sz_part)
	_mm_buf  = _rd.storage_buffer_create(N * 16 * 4)
	_mm.visible_instance_count = N

	var u0 = RDUniform.new(); u0.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u0.binding = 0; u0.add_id(_pos_buf)
	var u1 = RDUniform.new(); u1.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u1.binding = 1; u1.add_id(_vel_buf)
	var u2 = RDUniform.new(); u2.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u2.binding = 2; u2.add_id(_acc_buf)
	if _gravity_set.is_valid(): _rd.free_rid(_gravity_set)
	_gravity_set = _rd.uniform_set_create([u0, u1, u2], _gravity_shader, 0)

	var r0 = RDUniform.new(); r0.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	r0.binding = 0; r0.add_id(_pos_buf)
	var r1 = RDUniform.new(); r1.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	r1.binding = 1; r1.add_id(_mm_buf)
	if _render_set.is_valid(): _rd.free_rid(_render_set)
	_render_set = _rd.uniform_set_create([r0, r1], _render_shader, 0)


# ── Initial conditions ─────────────────────────────────────────────

func _init_bodies() -> void:
	_create_buffers()
	var pos = PackedFloat32Array(); pos.resize(N * 4)
	var vel = PackedFloat32Array(); vel.resize(N * 4)
	var rng = RandomNumberGenerator.new()

	for i in range(N):
		var u = rng.randf_range(0.001, 0.999)
		var r = cluster_radius / sqrt(pow(u, -2.0 / 3.0) - 1.0)
		var th = acos(2.0 * rng.randf() - 1.0)
		var ph = rng.randf() * PI * 2.0
		pos[i * 4]     = r * sin(th) * cos(ph)
		pos[i * 4 + 1] = r * sin(th) * sin(ph)
		pos[i * 4 + 2] = r * cos(th)
		pos[i * 4 + 3] = 1.0

		var vs = sqrt(2.0 * G * N / sqrt(r * r + softening * softening)) * 0.65
		vel[i * 4]     = rng.randf_range(-1.0, 1.0) * vs
		vel[i * 4 + 1] = rng.randf_range(-1.0, 1.0) * vs
		vel[i * 4 + 2] = rng.randf_range(-1.0, 1.0) * vs
		vel[i * 4 + 3] = 0.0

	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_render_and_readback()


func _init_static_cluster() -> void:
	_create_buffers()
	var pos = PackedFloat32Array(); pos.resize(N * 4)
	var rng = RandomNumberGenerator.new()
	for i in range(N):
		var r = cluster_radius * sqrt(rng.randf())
		var th = rng.randf() * PI * 2.0
		pos[i * 4]     = r * cos(th)
		pos[i * 4 + 1] = rng.randf_range(-1.0, 1.0) * 0.5
		pos[i * 4 + 2] = r * sin(th)
		pos[i * 4 + 3] = 1.0
	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_render_and_readback()
	print("[NBody] Static cluster")


# ── MultiMesh setup ───────────────────────────────────────────────

func _setup_multimesh() -> void:
	var qm = QuadMesh.new(); qm.size = Vector2(particle_size, particle_size)
	qm.orientation = PlaneMesh.FACE_Z
	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true; _mm.instance_count = N; _mm.mesh = qm
	_mmi = MultiMeshInstance3D.new(); _mmi.multimesh = _mm
	add_child(_mmi)
	var mat = ShaderMaterial.new()
	mat.shader = load("res://shaders/particle_billboard.gdshader")
	mat.render_priority = 1
	_mmi.material_override = mat
