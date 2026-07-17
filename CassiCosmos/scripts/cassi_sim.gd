extends Node3D
## Cassi Universe Simulator — core orchestration.
##
## Manages the two-fluid PDE field grid, N-body particles, black hole
## lensing, and visualization — all running in Godot compute shaders.
##
## No Python backend needed. All physics is GPU-native GLSL.

# ═══════════════════════════════════════════════════════════════════════
# Exports
@export var playing: bool = true              # simulation running

@export var grid_N: int = 32              # field grid resolution (per dim)
@export var N_particles: int = 20000      # N-body particle count
@export var dt: float = 0.001             # simulation timestep
@export var xi: float = 18.0              # Cassi Qi coupling
@export var softening: float = 0.1        # gravity softening length
@export var particle_size: float = 0.08   # rendered particle size
@export var cluster_radius: float = 5.0   # initial cluster size
@export var source_strength: float = 0.5  # field perturbation amplitude

@export_enum("Particles", "Field", "Black Hole", "Cosmology") var mode: int = 0

# ═══════════════════════════════════════════════════════════════════════
# Internal state
# ═══════════════════════════════════════════════════════════════════════

var _rd: RenderingDevice = null

# — field grid buffers (SET 0) —
var _field_ey: RID; var _field_ei: RID
var _field_q: RID;  var _field_vel: RID

# — particle buffers (SET 1) —
var _pos_buf: RID; var _vel_buf: RID; var _acc_buf: RID

# — auxiliary buffers (SET 2) —
var _bh_buf: RID

# — shaders and pipelines —
var _two_fluid_shader: RID;  var _two_fluid_pipe: RID
var _nbody_shader: RID;      var _nbody_pipe: RID
var _field_render_shader: RID; var _field_render_pipe: RID
var _bh_lensing_shader: RID;  var _bh_lensing_pipe: RID

# — MultiMesh rendering —
var _mmi: MultiMeshInstance3D; var _mm: MultiMesh

# — timing —
var _step_count: int = 0
var _time: float = 0.0
var _step_timer: float = 0.0

# — diagnostics —
var _q_mean: float = 0.0
var _eps_mean: float = 0.0
var _hubble: float = 0.0
var _scale_factor: float = 1.0

const PHI: float = 1.618033988749895
const PHI_INV3: float = (PHI - 1.0) / (PHI + 1.0)


# — Display textures for visualization modes —
var field_display_texture: Texture2D = null
signal field_texture_updated(tex: Texture2D)
var bh_display_texture: Texture2D = null
signal bh_texture_updated(tex: Texture2D)
# ═══════════════════════════════════════════════════════════════════════
# Lifecycle
# ═══════════════════════════════════════════════════════════════════════

func _ready() -> void:
	_setup_rendering_device()
	_setup_buffers()
	_setup_shaders()
	_setup_multimesh()
	_init_field()
	_init_particles()
	print("[CassiSim] Universe ready — grid=%d³ particles=%d xi=%.1f" % [grid_N, N_particles, xi])


func _process(delta: float) -> void:
	if not _rd:
		return

	if playing:
		_step_timer += delta
		while _step_timer >= dt:
			_step_timer -= dt
			_physics_step()
			_step_count += 1

	_render_frame()


func _exit_tree() -> void:
	_free_buffers()
	_free_shaders()


# ═══════════════════════════════════════════════════════════════════════
# Rendering Device setup
# ═══════════════════════════════════════════════════════════════════════

func _setup_rendering_device() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		push_error("[CassiSim] Failed to create RenderingDevice")


func _shader_from_file(path: String) -> RID:
	var sf = load(path) if ResourceLoader.exists(path) else null
	if sf == null:
		push_error("[CassiSim] Shader not found: " + path)
		return RID()
	var spirv = sf.get_spirv()
	if spirv == null:
		push_error("[CassiSim] SPIR-V compile failed: " + path)
		return RID()
	return _rd.shader_create_from_spirv(spirv)


func _uniform_storage(binding: int, buf: RID) -> RDUniform:
	var u = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _setup_buffers() -> void:
	var N = grid_N
	var nc = N * N * N
	var nf = nc * 4

	# SET 0 — Field grid
	_field_ey  = _rd.storage_buffer_create(nf)
	_field_ei  = _rd.storage_buffer_create(nf)
	_field_q   = _rd.storage_buffer_create(nf)
	_field_vel = _rd.storage_buffer_create(nc * 16)
	# SET 1 — Particles
	var ps = N_particles * 16
	_pos_buf = _rd.storage_buffer_create(ps)
	_vel_buf = _rd.storage_buffer_create(ps)
	_acc_buf = _rd.storage_buffer_create(ps)

	# SET 2 — BH data + sim globals
	_bh_buf = _rd.storage_buffer_create(4 * 16)
	var bh_init = PackedFloat32Array([
		0.0, 0.0, 0.0, float(N_particles),           # pos + M_total
		0.0, 0.0, 0.0, 1.0,                           # spin + G_N
		cluster_radius, cluster_radius * 1.5, 0.0, 0.0, # cluster_a, grid_extent
		0.0, 0.0, 0.0, 0.0,
	])
	_rd.buffer_update(_bh_buf, 0, bh_init.size() * 4, bh_init.to_byte_array())

	# Render textures for field/BH output
	_make_render_textures()


func _free_buffers() -> void:
	if not _rd: return
	for rid in [_field_ey, _field_ei, _field_q, _field_vel,
				_pos_buf, _vel_buf, _acc_buf, _bh_buf]:
		if rid.is_valid(): _rd.free_rid(rid)


func _free_shaders() -> void:
	if not _rd: return
	for rid in [_two_fluid_shader, _two_fluid_pipe,
				_nbody_shader, _nbody_pipe,
				_field_render_shader, _field_render_pipe,
				_bh_lensing_shader, _bh_lensing_pipe]:
		if rid.is_valid(): _rd.free_rid(rid)


# ═══════════════════════════════════════════════════════════════════════
# Shader loading
# ═══════════════════════════════════════════════════════════════════════

func _setup_shaders() -> void:
	# Two-fluid PDE solver
	_two_fluid_shader = _shader_from_file("res://compute/cassi_two_fluid.glsl")
	if _two_fluid_shader.is_valid():
		_two_fluid_pipe = _rd.compute_pipeline_create(_two_fluid_shader)
		print("[CassiSim] Two-fluid PDE pipeline ready")

	# N-body gravity
	_nbody_shader = _shader_from_file("res://compute/cassi_nbody_gravity.glsl")
	if _nbody_shader.is_valid():
		_nbody_pipe = _rd.compute_pipeline_create(_nbody_shader)
		print("[CassiSim] N-body gravity pipeline ready")

	# Field rendering
	_field_render_shader = _shader_from_file("res://compute/cassi_field_render.glsl")
	if _field_render_shader.is_valid():
		_field_render_pipe = _rd.compute_pipeline_create(_field_render_shader)
		print("[CassiSim] Field render pipeline ready")

	# BH lensing
	_bh_lensing_shader = _shader_from_file("res://compute/cassi_bh_lensing.glsl")
	if _bh_lensing_shader.is_valid():
		_bh_lensing_pipe = _rd.compute_pipeline_create(_bh_lensing_shader)
		print("[CassiSim] BH lensing pipeline ready")


# ═══════════════════════════════════════════════════════════════════════
# Initial conditions
# ═══════════════════════════════════════════════════════════════════════

func _init_field() -> void:
	var N = grid_N
	var nc = N * N * N
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	var q  = PackedFloat32Array(); q.resize(nc)
	var vel = PackedFloat32Array(); vel.resize(nc * 4)

	var half = float(N) * 0.5
	var rng = RandomNumberGenerator.new()

	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id = i + N * (j + N * k)
				var dx = (float(i) - half) / half
				var dy = (float(j) - half) / half
				var dz = (float(k) - half) / half
				var r2 = dx*dx + dy*dy + dz*dz

				# Gaussian perturbation at center
				var amp = 0.1
				ey[id] = amp * exp(-r2 * 2.0) + rng.randf_range(-0.01, 0.01)
				ei[id] = amp * 0.707 * exp(-r2 * 1.5) + rng.randf_range(-0.01, 0.01)
				q[id] = ey[id]*ey[id] + ei[id]*ei[id]
				vel[id * 4]     = 0.0
				vel[id * 4 + 1] = 0.0
				vel[id * 4 + 2] = 0.0
				vel[id * 4 + 3] = 0.0

	_rd.buffer_update(_field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_field_ei, 0, ei.size() * 4, ei.to_byte_array())
	_rd.buffer_update(_field_q,  0, q.size() * 4, q.to_byte_array())
	_rd.buffer_update(_field_vel, 0, vel.size() * 4, vel.to_byte_array())

	print("[CassiSim] Field initialized: %d³ = %d cells" % [N, nc])


func _init_particles() -> void:
	var pos = PackedFloat32Array(); pos.resize(N_particles * 4)
	var vel = PackedFloat32Array(); vel.resize(N_particles * 4)
	var acc = PackedFloat32Array(); acc.resize(N_particles * 4)

	var rng = RandomNumberGenerator.new()
	var G = 1.0
	var eps2 = softening * softening

	for i in range(N_particles):
		var u = rng.randf_range(0.001, 0.999)
		var r = cluster_radius / sqrt(pow(u, -2.0 / 3.0) - 1.0)
		var th = acos(2.0 * rng.randf() - 1.0)
		var ph = rng.randf() * PI * 2.0
		var i4 = i * 4
		pos[i4]     = r * sin(th) * cos(ph)
		pos[i4 + 1] = r * sin(th) * sin(ph)
		pos[i4 + 2] = r * cos(th)
		pos[i4 + 3] = 1.0  # mass

		var vs = sqrt(2.0 * G * N_particles / sqrt(r * r + eps2)) * 0.65
		vel[i4]     = rng.randf_range(-1.0, 1.0) * vs
		vel[i4 + 1] = rng.randf_range(-1.0, 1.0) * vs
		vel[i4 + 2] = rng.randf_range(-1.0, 1.0) * vs
		vel[i4 + 3] = 0.0

	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_rd.buffer_update(_acc_buf, 0, acc.size() * 4, acc.to_byte_array())

	print("[CassiSim] Particles initialized: %d" % N_particles)



# ═══════════════════════════════════════════════════════════════════════
# Physics step
# ═══════════════════════════════════════════════════════════════════════

# — Render target textures for compute shader output —
var _field_render_tex: RID = RID()
var _bh_lensing_tex: RID = RID()
var _rt_size: Vector2i = Vector2i(512, 512)


func _make_render_texture(width: int, height: int) -> RID:
	var fmt = RDTextureFormat.new()
	fmt.width = width
	fmt.height = height
	fmt.format = RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT
	fmt.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT \
				   | RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT
	var view = RDTextureView.new()
	return _rd.texture_create(fmt, view, [])


func _get_set2_image_uniform(shader: RID, binding: int, tex: RID) -> RDUniform:
	var u = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
	u.binding = binding
	u.add_id(tex)
	return u


func _get_set2_buffer_uniform(shader: RID, binding: int, buf: RID) -> RDUniform:
	var u = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _dispatch_compute(shader: RID, pipeline: RID,
		set2_uniforms: Array[RDUniform],
		pc: PackedFloat32Array, groups: Vector3i) -> void:
	if not _rd: return
	if not shader.is_valid() or not pipeline.is_valid(): return

	var us0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey),
		_uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q),
		_uniform_storage(3, _field_vel),
	], shader, 0)

	var us1 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf),
		_uniform_storage(1, _vel_buf),
		_uniform_storage(2, _acc_buf),
	], shader, 1)

	var us2 = _rd.uniform_set_create(set2_uniforms, shader, 2)

	var cl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, pipeline)
	_rd.compute_list_bind_uniform_set(cl, us0, 0)
	_rd.compute_list_bind_uniform_set(cl, us1, 1)
	_rd.compute_list_bind_uniform_set(cl, us2, 2)
	_rd.compute_list_set_push_constant(cl, pc.to_byte_array(), pc.size() * 4)
	_rd.compute_list_dispatch(cl, groups.x, groups.y, groups.z)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _physics_step() -> void:
	_time += dt

	# Ensure BH buffer has correct physics params (modes may overwrite it)
	var bh_init = PackedFloat32Array([
		0.0, 0.0, 0.0, float(N_particles),           # pos + M_total
		0.0, 0.0, 0.0, 1.0,                           # spin + G_N
		cluster_radius, cluster_radius * 1.5, 0.0, 0.0, # cluster_a, grid_extent
		0.0, 0.0, 0.0, 0.0,
	])
	_rd.buffer_update(_bh_buf, 0, bh_init.size() * 4, bh_init.to_byte_array())

	var pc = PackedFloat32Array([
		float(grid_N),          # N_f
		dt,                     # dt
		_time,                  # t
		PHI,                    # phi
		xi,                     # xi
		softening * softening,   # eps2
		float(N_particles),     # particle_N
		float(mode),            # mode
		source_strength,        # source_strength
		0.0,                    # _pad
	])
	var pc_bytes = pc.to_byte_array()
	var pc_size = pc.size() * 4

	var wg = ceili(float(grid_N) / 4.0)
	var pg = ceili(float(N_particles) / 256.0) if N_particles > 0 else 1

	# Batch BOTH dispatches into a single compute list → one submit + sync
	var cl = _rd.compute_list_begin()

	# Build uniform sets for each shader (they share the same buffers)
	# Two-fluid PDE
	if _two_fluid_shader.is_valid():
		var us0 = _rd.uniform_set_create([
			_uniform_storage(0, _field_ey),
			_uniform_storage(1, _field_ei),
			_uniform_storage(2, _field_q),
			_uniform_storage(3, _field_vel),
		], _two_fluid_shader, 0)
		var us1p = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _vel_buf),
			_uniform_storage(2, _acc_buf),
		], _two_fluid_shader, 1)
		var us2t = _rd.uniform_set_create([
			_uniform_storage(0, _bh_buf),
		], _two_fluid_shader, 2)
		_rd.compute_list_bind_compute_pipeline(cl, _two_fluid_pipe)
		_rd.compute_list_bind_uniform_set(cl, us0, 0)
		_rd.compute_list_bind_uniform_set(cl, us1p, 1)
		_rd.compute_list_bind_uniform_set(cl, us2t, 2)
		_rd.compute_list_set_push_constant(cl, pc_bytes, pc_size)
		_rd.compute_list_dispatch(cl, wg, wg, wg)

	# N-body gravity
	if _nbody_shader.is_valid() and N_particles > 0:
		var us0g = _rd.uniform_set_create([
			_uniform_storage(0, _field_ey),
			_uniform_storage(1, _field_ei),
			_uniform_storage(2, _field_q),
			_uniform_storage(3, _field_vel),
		], _nbody_shader, 0)
		var us1g = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _vel_buf),
			_uniform_storage(2, _acc_buf),
		], _nbody_shader, 1)
		var us2g = _rd.uniform_set_create([
			_uniform_storage(0, _bh_buf),
		], _nbody_shader, 2)
		_rd.compute_list_bind_compute_pipeline(cl, _nbody_pipe)
		_rd.compute_list_bind_uniform_set(cl, us0g, 0)
		_rd.compute_list_bind_uniform_set(cl, us1g, 1)
		_rd.compute_list_bind_uniform_set(cl, us2g, 2)
		_rd.compute_list_set_push_constant(cl, pc_bytes, pc_size)
		_rd.compute_list_dispatch(cl, pg, 1, 1)

	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()

	# Read diagnostics (skip every frame to reduce sync overhead)
	if _step_count % 60 == 0:
		var q_data = _rd.buffer_get_data(_field_q, 0, grid_N * grid_N * grid_N * 4)
		if q_data.size() > 0:
			var qf = q_data.to_float32_array()
			var q_sum = 0.0
			for v in qf: q_sum += v
			_q_mean = q_sum / max(qf.size(), 1)


func _make_render_textures() -> void:
	_rt_size = Vector2i(512, 512)
	if _field_render_tex.is_valid(): _rd.free_rid(_field_render_tex)
	if _bh_lensing_tex.is_valid(): _rd.free_rid(_bh_lensing_tex)
	_field_render_tex = _make_render_texture(_rt_size.x, _rt_size.y)
	_bh_lensing_tex = _make_render_texture(_rt_size.x, _rt_size.y)
	print("[CassiSim] Render textures: %dx%d" % [_rt_size.x, _rt_size.y])


# ═══════════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════════

func _setup_multimesh() -> void:
	var qm = QuadMesh.new()
	qm.size = Vector2(particle_size, particle_size)
	qm.orientation = PlaneMesh.FACE_Z

	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true
	_mm.instance_count = max(N_particles, 1)
	_mm.mesh = qm

	_mmi = MultiMeshInstance3D.new()
	_mmi.multimesh = _mm
	add_child(_mmi)

	var mat = ShaderMaterial.new()
	mat.shader = load("res://shaders/particle_billboard.gdshader")
	mat.render_priority = 1
	_mmi.material_override = mat


func _render_frame() -> void:
	var realtime_mode = int(mode)

	match realtime_mode:
		0:  # Particles mode (default N-body)
			_render_particles()
		1:  # Field mode
			_render_field_slice()
		2:  # Black hole mode
			_render_particles()
			_render_bh_lensing()
		3:  # Cosmology mode (particles + expanding field)
			_render_particles()




func _render_particles() -> void:
	if N_particles <= 0:
		return

	var pos_data = _rd.buffer_get_data(_pos_buf, 0, min(N_particles, 200000) * 16)
	if pos_data.size() < 16: return

	var pos = pos_data.to_float32_array()
	var n_visible = min(pos.size() / 4, N_particles)

	# Debug: log first particle's position every 3000 steps
	if _step_count > 0 and _step_count % 3000 == 0 and n_visible > 0:
		print("[CassiSim] p[0] = (%.3f, %.3f, %.3f)  steps=%d" % [
			pos[0], pos[1], pos[2], _step_count])

	var max_r2 = 0.0
	for i in range(n_visible):
		var i4 = i * 4
		var r2 = pos[i4]*pos[i4] + pos[i4+1]*pos[i4+1] + pos[i4+2]*pos[i4+2]
		if r2 > max_r2: max_r2 = r2

	var imr = 1.0 / sqrt(max(max_r2, 0.0001))

	for i in range(n_visible):
		var i4 = i * 4
		var p = Vector3(pos[i4], pos[i4+1], pos[i4+2])
		_mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, p))
		var t = clamp(p.length() * imr, 0.0, 1.0)
		var r = lerp(1.0, 0.15, t)
		var g = lerp(0.8, 0.25, t)
		var b = lerp(0.3, 1.0, t)
		_mm.set_instance_color(i, Color(r, g, b, 0.85))
	_mm.visible_instance_count = n_visible


func _render_field_slice() -> void:
	if not _field_render_shader.is_valid(): return
	if not _field_render_tex.is_valid():
		_make_render_textures()

	var pc = PackedFloat32Array([
		float(grid_N), dt, _time, PHI, xi,
		softening * softening, float(N_particles), float(mode),
		source_strength, 0.0,
	])
	var wg = Vector3i(ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1)

	_dispatch_compute(_field_render_shader, _field_render_pipe,
		[_get_set2_image_uniform(_field_render_shader, 0, _field_render_tex)],
		pc, wg)

	# Readback for UI display
	var fdata = _rd.texture_get_data(_field_render_tex, 0)
	if fdata.size() > 100:
		var img = Image.create_from_data(_rt_size.x, _rt_size.y, false, Image.FORMAT_RGBAF, fdata)
		if img:
			field_display_texture = ImageTexture.create_from_image(img)
			field_texture_updated.emit(field_display_texture)


func _render_bh_lensing() -> void:
	if not _bh_lensing_shader.is_valid(): return
	if not _bh_lensing_tex.is_valid():
		_make_render_textures()

	var pc = PackedFloat32Array([
		float(grid_N), dt, _time, PHI, xi,
		softening * softening, float(N_particles), float(mode),
		source_strength, 0.0,
	])

	# Write BH params: center screen, mass=2, spin=0, G_eff=1.0
	var bh = PackedFloat32Array([_rt_size.x*0.5, _rt_size.y*0.5, 0.0, 0.0,
		2.0, 0.0, 1.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0])
	_rd.buffer_update(_bh_buf, 0, bh.size() * 4, bh.to_byte_array())

	var wg = Vector3i(ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1)

	_dispatch_compute(_bh_lensing_shader, _bh_lensing_pipe,
		[
			_get_set2_image_uniform(_bh_lensing_shader, 0, _bh_lensing_tex),
			_get_set2_buffer_uniform(_bh_lensing_shader, 1, _bh_buf),
		],
		pc, wg)

	# Readback for UI display
	var bdata = _rd.texture_get_data(_bh_lensing_tex, 0)
	if bdata.size() > 100:
		var img = Image.create_from_data(_rt_size.x, _rt_size.y, false, Image.FORMAT_RGBAF, bdata)
		if img:
			bh_display_texture = ImageTexture.create_from_image(img)
			bh_texture_updated.emit(bh_display_texture)

# ═══════════════════════════════════════════════════════════════════════
# Public API (for UI to call)
# ═══════════════════════════════════════════════════════════════════════

func reinit() -> void:
	_rd.sync()
	_free_buffers()
	_setup_buffers()
	_init_field()
	_init_particles()
	_step_count = 0
	_time = 0.0
	print("[CassiSim] Reinitialized")


func get_diagnostics() -> String:
	return "t=%.3f  q_mean=%.4f  ε²=%.6f  H=%.4f  a=%.3f  steps=%d" % [
		_time, _q_mean, _eps_mean, _hubble, _scale_factor, _step_count]
