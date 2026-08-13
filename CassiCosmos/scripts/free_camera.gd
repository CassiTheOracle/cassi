extends Camera3D
## 6-DOF free-fly camera for space-sim N-body rendering.
##
## Movement modes:
##   - World-axis strafe (default) — WASD move along global X/Z; SHIFT/CTRL
##     move along global Y.
##   - Look-direction flight (Tab) — WASD move along the camera's local
##     forward/right axes; SHIFT/CTRL move along local up/down.
##
## Orbit: hold right-click or middle-click and drag to rotate.
##
## Speed: scroll wheel, or Z (faster) / X (slower), adjusts logarithmically
## from 0.1 → 1000 u/s. The base speed is additionally scaled by distance
## from origin so the camera feels responsive at both planetary and
## interstellar scales.

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

@export var move_speed: float = 10.0
@export var look_sensitivity: float = 0.002
@export var speed_multiplier: float = 2.0

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

var _flight_mode: bool = true           # default: look-direction flight (W goes forward)
var _dragging: bool = false
var _prev_mouse_pos: Vector2 = Vector2.ZERO

# Current speed after scroll + origin-distance scaling.
# Recalculated every frame.
var _current_speed: float = 10.0

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

func _ready() -> void:
	_current_speed = move_speed


func _unhandled_input(event: InputEvent) -> void:
	# --- Tab: toggle flight / world-axis strafe ---
	if event.is_action_pressed(&"ui_focus_next") or (event is InputEventKey and event.keycode == KEY_TAB and event.pressed and not event.echo):
		_flight_mode = not _flight_mode
		get_viewport().set_input_as_handled()

	# --- Scroll: logarithmic speed change ---
	if event is InputEventMouseButton:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			_current_speed = clampf(_current_speed * speed_multiplier, 0.1, 1000.0)
			get_viewport().set_input_as_handled()
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			_current_speed = clampf(_current_speed / speed_multiplier, 0.1, 1000.0)
			get_viewport().set_input_as_handled()

	# --- Z / X: speed up / slow down (same step as one wheel notch; OS key
	# repeat is allowed so holding a key keeps stepping, like a throttle) ---
	if event is InputEventKey and event.pressed:
		if event.keycode == KEY_Z:
			_current_speed = clampf(_current_speed * speed_multiplier, 0.1, 1000.0)
			get_viewport().set_input_as_handled()
		elif event.keycode == KEY_X:
			_current_speed = clampf(_current_speed / speed_multiplier, 0.1, 1000.0)
			get_viewport().set_input_as_handled()

	# --- Mouse drag start ---
	if event is InputEventMouseButton:
		var btn: int = event.button_index
		if btn == MOUSE_BUTTON_RIGHT or btn == MOUSE_BUTTON_MIDDLE:
			if event.pressed and not _dragging:
				_dragging = true
				_prev_mouse_pos = event.position
				Input.set_mouse_mode(Input.MOUSE_MODE_CAPTURED)
				get_viewport().set_input_as_handled()
			elif not event.pressed and _dragging:
				_dragging = false
				Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
				get_viewport().set_input_as_handled()

	# --- Mouse drag rotate ---
	if event is InputEventMouseMotion and _dragging:
		var capture: bool = Input.get_mouse_mode() == Input.MOUSE_MODE_CAPTURED
		var delta: Vector2 = event.relative if capture else (event.position - _prev_mouse_pos)
		_prev_mouse_pos = event.position if not capture else _prev_mouse_pos

		var yaw: float   = -delta.x * look_sensitivity
		var pitch: float = -delta.y * look_sensitivity

		rotate_object_local(Vector3(0.0, 1.0, 0.0), yaw)
		# Clamp pitch to avoid gimbal flip at ±90°
		var current_pitch: float = rotation.x + pitch
		current_pitch = clampf(current_pitch, deg_to_rad(-89.9), deg_to_rad(89.9))
		pitch = current_pitch - rotation.x
		rotate_object_local(Vector3(1.0, 0.0, 0.0), pitch)


func _process(delta: float) -> void:
	# --- Keyboard rotation (Q/E yaw) ---
	var key_rot = 0.0
	if Input.is_key_pressed(KEY_Q): key_rot += 1.0
	if Input.is_key_pressed(KEY_E): key_rot -= 1.0
	if key_rot != 0.0:
		rotate_y(key_rot * delta * 2.0)

	# --- Movement input ---
	# Vertical: SHIFT = up, CTRL = down. SPACE stays reserved for the UI's
	# play/pause; Z/X are the camera speed controls.
	var input_dir: Vector3 = Vector3.ZERO
	if Input.is_key_pressed(KEY_W):  input_dir.z -= 1.0
	if Input.is_key_pressed(KEY_S):  input_dir.z += 1.0
	if Input.is_key_pressed(KEY_A):  input_dir.x -= 1.0
	if Input.is_key_pressed(KEY_D):  input_dir.x += 1.0
	if Input.is_key_pressed(KEY_SHIFT): input_dir.y += 1.0
	if Input.is_key_pressed(KEY_CTRL):  input_dir.y -= 1.0

	input_dir = input_dir.normalized()

	# Convert to movement direction depending on flight mode.
	var move_dir: Vector3
	if _flight_mode:
		# Look-direction: transform by the camera's own basis.
		move_dir = global_transform.basis * input_dir
	else:
		# World-axis: input z is global Z, x is global X, y is global Y.
		move_dir = Vector3(
			input_dir.x,
			input_dir.y,
			-input_dir.z   # forward = -Z in Godot
		)

	# --- Speed scaling by distance from origin ---
	var dist: float = global_position.length()
	var scale_factor: float = 1.0 + dist * 0.02   # gentle ramp: 2 % per unit distance
	var speed: float = _current_speed * scale_factor

	# --- Apply movement ---
	global_position += move_dir * speed * delta

	# --- Debug overlay ---
	var mode_label: String = "FLIGHT" if _flight_mode else "STRAFE"
	var msg: String = "Speed: %.2f u/s  Mode: %s  Dist: %.1f" % [speed, mode_label, dist]


func _notification(what: int) -> void:
	if what == NOTIFICATION_PREDELETE and _dragging:
		Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
