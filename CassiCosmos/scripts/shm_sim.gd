extends Node3D
## N-body renderer — reads positions from /dev/shm/nbody_frame.bin
## written by nbody_shm_server.py. Zero networking.


@export var N: int = 2000
@export var particle_size: float = 0.06

var _positions: PackedVector3Array = PackedVector3Array()
var _last_frame_id: int = -1
var _frame_count: int = 0
var _q_mean: float = 0.0
var _eps_mean: float = 0.0

var _mmi: MultiMeshInstance3D; var _mm: MultiMesh
var _debug_timer: float = 0.0

const SHM_PATH: String = "/dev/shm/nbody_frame.bin"


func _ready() -> void:
	_setup_multimesh()
	print("[SHMSim] Ready — polling ", SHM_PATH)


func _process(delta: float) -> void:
	_read_shm()
	_update_render()

	_debug_timer += delta
	if _debug_timer >= 3.0:
		_debug_timer = 0.0
		print("[SHMSim] frames=", _frame_count, " N=", N,
			" q=", "%.3f" % _q_mean)


func _read_shm() -> void:
	if not FileAccess.file_exists(SHM_PATH):
		return
	var f = FileAccess.open(SHM_PATH, FileAccess.READ)
	if f == null: return
	f.big_endian = false

	var frame_id = f.get_32()
	if frame_id == _last_frame_id:
		return

	_last_frame_id = frame_id
	var n = f.get_32()

	if n <= 0 or n > 10000000:
		return  # sanity check

	if n != _positions.size():
		_positions.resize(n)
	if n != N:
		N = n
	if _mm.instance_count < N:
		_mm.instance_count = N

	for i in range(N):
		var x = f.get_float()
		var y = f.get_float()
		var z = f.get_float()
		_positions[i] = Vector3(x, y, z)

	_q_mean = f.get_float()
	_eps_mean = f.get_float()
	_frame_count += 1


func _setup_multimesh() -> void:
	var qm = QuadMesh.new()
	qm.size = Vector2(particle_size, particle_size)
	qm.orientation = PlaneMesh.FACE_Z

	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true
	_mm.instance_count = N
	_mm.mesh = qm

	_mmi = MultiMeshInstance3D.new()
	_mmi.multimesh = _mm
	add_child(_mmi)

	var mat = ShaderMaterial.new()
	mat.shader = load("res://shaders/particle_billboard.gdshader")
	mat.render_priority = 1
	_mmi.material_override = mat


func _update_render() -> void:
	if _positions.is_empty():
		return

	var max_r2 = 0.0
	for i in range(N):
		var p = _positions[i]
		var r2 = p.x*p.x + p.y*p.y + p.z*p.z
		if r2 > max_r2: max_r2 = r2

	var inv_max = 1.0 / sqrt(max(max_r2, 0.0001))
	if N > _mm.instance_count:
		_mm.instance_count = N

	for i in range(N):
		var p = _positions[i]
		_mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, p))
		var t = clamp(p.length() * inv_max, 0.0, 1.0)
		_mm.set_instance_color(i, Color(
			lerp(1.0, 0.2, t),
			lerp(0.8, 0.3, t),
			lerp(0.3, 1.0, t),
			0.85
		))

	for i in range(N, _mm.instance_count):
		_mm.set_instance_transform(i, Transform3D(Basis.IDENTITY, Vector3(1e6, 1e6, 1e6)))
		_mm.set_instance_color(i, Color(0, 0, 0, 0))

	_mm.visible_instance_count = N
