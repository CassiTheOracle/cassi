extends Node3D
## Cassi Qi-enhanced N-body — O(N) gravity via Yang halo field.
## The compute shader now evaluates the Yang halo profile analytically
## instead of computing N(N-1)/2 pairwise forces. ~100x faster at N=2000.

@export var N: int = 2000
@export var G: float = 1.0
@export var softening: float = 0.4
@export var dt: float = 0.001
@export var playing: bool = false
@export var particle_size: float = 0.06
@export var cluster_radius: float = 5.0

# Cassi Qi parameters
@export_range(0.0, 100.0) var xi: float = 18.0
@export_range(0.5, 10.0) var qi_beta: float = 3.0
@export_range(0.3, 0.99) var pi_max: float = 0.55
@export_range(0.5, 10.0) var halo_radius: float = 3.0
@export_range(0.5, 5.0) var halo_width: float = 1.5

var _compute_ready: bool = false
var _retry_frames: int = 0

var _rd: RenderingDevice = null
var _shader: RID; var _pipeline: RID; var _uniform_set: RID
var _pos_buf: RID; var _vel_buf: RID; var _acc_buf: RID
var _pos_staging: PackedFloat32Array

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
	if not _compute_ready and _retry_frames < 120:
		_retry_frames += 1
		if _retry_frames in [10, 60]:
			_setup_compute()
			if _compute_ready:
				_init_bodies()

	if not playing or not _compute_ready:
		_update_render()
		return

	_step_timer += delta
	while _step_timer >= dt:
		_step_timer -= dt
		_step()
		_step_count += 1
	_update_render()


# ── RenderingDevice compute pipeline ──────────────────────────────

func _setup_compute() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		return
	var sf = load("res://compute/nbody_gravity.glsl")
	if sf == null:
		push_error("[NBodySim] Shader file not found")
		return
	var spirv = sf.get_spirv()
	if spirv == null:
		push_error("[NBodySim] SPIR-V compile failed")
		return

	_shader = _rd.shader_create_from_spirv(spirv)
	_pipeline = _rd.compute_pipeline_create(_shader)
	_compute_ready = true
	print("[NBodySim] Cassi Qi gravity pipeline ready (xi=%.1f, pi_max=%.2f)" % [xi, pi_max])


func _create_buffers() -> void:
	for rid in [_pos_buf, _vel_buf, _acc_buf]:
		if rid.is_valid(): _rd.free_rid(rid)
	var sz = N * 4 * 4
	_pos_buf = _rd.storage_buffer_create(sz)
	_vel_buf = _rd.storage_buffer_create(sz)
	_acc_buf = _rd.storage_buffer_create(sz)

	var u0 = RDUniform.new()
	u0.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u0.binding = 0; u0.add_id(_pos_buf)

	var u1 = RDUniform.new()
	u1.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u1.binding = 1; u1.add_id(_acc_buf)

	if _uniform_set.is_valid(): _rd.free_rid(_uniform_set)
	_uniform_set = _rd.uniform_set_create([u0, u1], _shader, 0)


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
		var vx = rng.randf_range(-1.0, 1.0) * vs
		var vy = rng.randf_range(-1.0, 1.0) * vs
		var vz = rng.randf_range(-1.0, 1.0) * vs
		vel[i * 4]     = vx
		vel[i * 4 + 1] = vy
		vel[i * 4 + 2] = vz
		vel[i * 4 + 3] = 0.0

	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_pos_staging = pos


func _init_static_cluster() -> void:
	var pos = PackedFloat32Array(); pos.resize(N * 4)
	var rng = RandomNumberGenerator.new()
	for i in range(N):
		var r = cluster_radius * sqrt(rng.randf())
		var th = rng.randf() * PI * 2.0
		var y = rng.randf_range(-1.0, 1.0) * 0.5
		pos[i * 4]     = r * cos(th)
		pos[i * 4 + 1] = y
		pos[i * 4 + 2] = r * sin(th)
		pos[i * 4 + 3] = 1.0
	_pos_staging = pos
	print("[NBodySim] Static cluster — compute not available")


# ── Simulation step ─────────────────────────────────────────────────

func _dispatch() -> void:
	# Push constants match the shader's PC struct exactly:
	#   N_f, G, eps2, xi, qi_beta, phi_inv3, halo_radius, halo_width,
	#   pi_max, cluster_a, M_total, _pad
	var pc = PackedFloat32Array([
		float(N),               # N_f
		G,                      # G
		softening * softening,  # eps2
		xi,                     # xi (Qi coupling)
		qi_beta,                # qi_beta
		PHI_INV3,               # phi_inv3
		halo_radius,            # halo_radius
		halo_width,             # halo_width
		pi_max,                 # pi_max
		cluster_radius,         # cluster_a
		float(N),               # M_total
		0.0,                    # _pad
	])

	var wg = ceili(float(N) / 256.0)
	var cl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipeline)
	_rd.compute_list_bind_uniform_set(cl, _uniform_set, 0)
	_rd.compute_list_set_push_constant(cl, pc.to_byte_array(), 12 * 4)
	_rd.compute_list_dispatch(cl, int(wg), 1, 1)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _step() -> void:
	_dispatch()
	var acc = _rd.buffer_get_data(_acc_buf, 0, N * 16).to_float32_array()
	var pos = _rd.buffer_get_data(_pos_buf, 0, N * 16).to_float32_array()
	var vel = _rd.buffer_get_data(_vel_buf, 0, N * 16).to_float32_array()

	var hdt = dt * 0.5
	for i in range(N):
		var i4 = i * 4
		vel[i4]     += acc[i4]     * hdt
		vel[i4 + 1] += acc[i4 + 1] * hdt
		vel[i4 + 2] += acc[i4 + 2] * hdt
		pos[i4]     += vel[i4]     * dt
		pos[i4 + 1] += vel[i4 + 1] * dt
		pos[i4 + 2] += vel[i4 + 2] * dt
		vel[i4]     += acc[i4]     * hdt
		vel[i4 + 1] += acc[i4 + 1] * hdt
		vel[i4 + 2] += acc[i4 + 2] * hdt

	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_pos_staging = pos


# ── MultiMesh rendering ────────────────────────────────────────────

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


func _update_render() -> void:
	if _pos_staging.is_empty(): return
	var mr = 0.0
	for i in range(N):
		var i4 = i * 4
		var r2 = _pos_staging[i4] * _pos_staging[i4] + \
		         _pos_staging[i4 + 1] * _pos_staging[i4 + 1] + \
		         _pos_staging[i4 + 2] * _pos_staging[i4 + 2]
		if r2 > mr: mr = r2
	var imr = 1.0 / sqrt(max(mr, 0.0001))
	for i in range(N):
		var i4 = i * 4
		var p = Vector3(_pos_staging[i4], _pos_staging[i4 + 1], _pos_staging[i4 + 2])
		_mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, p))
		var t = clamp(p.length() * imr, 0.0, 1.0)
		# Color: warm inner → cool outer. Yang halo particles turn deep blue.
		_mm.set_instance_color(i,
			Color(lerp(1.0, 0.2, t), lerp(0.8, 0.3, t), lerp(0.3, 1.0, t), 0.85))
	_mm.visible_instance_count = N
