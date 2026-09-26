class_name CButton
extends Button
## CButton — Cassi UI action button.
##
## A Button with the library's interaction conventions baked in, so callers
## never have to repeat them (the sim currently sets
## `focus_mode = FOCUS_NONE` + `mouse_default_cursor_shape = POINTING_HAND`
## by hand on every control):
##   - focus_mode = FOCUS_NONE      — WASD camera keeps working; UI never
##                                    steals keyboard focus.
##   - mouse_default_cursor_shape   = CURSOR_POINTING_HAND — affordance.
##   - mouse_filter = MOUSE_FILTER_STOP — interactive control claims clicks.
##
## Non-toggle action button; exclusive selection is CToggle/CSegmented's job.

const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")

## Static factory: a CButton with the given text. `pressed_cb` (optional) is
## connected to `pressed` — a Callable (method or lambda).
static func make(text: String, pressed_cb: Callable = Callable()) -> CButton:
	var b := CButton.new()
	b.text = text
	if pressed_cb.is_valid():
		b.pressed.connect(pressed_cb)
	return b


func _ready() -> void:
	focus_mode = Control.FOCUS_NONE
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	mouse_filter = Control.MOUSE_FILTER_STOP
