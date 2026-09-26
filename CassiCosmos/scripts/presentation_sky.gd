extends MeshInstance3D
## Renderer-only procedural sky for the interactive and recorder scenes.
##
## The sphere follows the active sibling Camera3D's position, remains below
## its far plane, and never writes depth. It therefore supplies a stable
## large-scale backdrop without touching simulation state, physics buffers, or
## camera ownership.

@export_range(100.0, 100000.0, 1.0) var minimum_radius: float = 1000.0
@export_range(0.1, 0.99, 0.01) var far_plane_fraction: float = 0.92

var _camera: Camera3D = null
var _last_radius: float = -1.0


func _ready() -> void:
	cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	gi_mode = GeometryInstance3D.GI_MODE_DISABLED
	_ensure_mesh()
	_ensure_material()
	_camera = _find_camera()
	_update_transform()


func _process(_delta: float) -> void:
	if not is_instance_valid(_camera):
		_camera = _find_camera()
	_update_transform()


func _find_camera() -> Camera3D:
	var parent := get_parent()
	if parent == null:
		return null
	for child in parent.get_children():
		if child is Camera3D:
			return child
	return null


func _ensure_mesh() -> void:
	if mesh != null:
		return
	var sphere := SphereMesh.new()
	sphere.radius = 1.0
	sphere.height = 2.0
	sphere.radial_segments = 96
	sphere.rings = 48
	mesh = sphere


func _ensure_material() -> void:
	if material_override != null:
		return
	var shader := load("res://shaders/presentation_sky.gdshader") as Shader
	if shader == null:
		push_error("[PresentationSky] shader could not be loaded")
		return
	var material := ShaderMaterial.new()
	material.shader = shader
	material.render_priority = -128
	material_override = material


func _update_transform() -> void:
	if _camera == null:
		return
	global_position = _camera.global_position
	var radius := maxf(minimum_radius, _camera.far * clampf(far_plane_fraction, 0.1, 0.99))
	if is_equal_approx(radius, _last_radius):
		return
	_last_radius = radius
	scale = Vector3.ONE * radius
