class_name CToggle
extends Button
## CToggle — Cassi UI exclusive/press toggle button.
##
## A Button in `toggle_mode` with the library's interaction conventions and
## a pressed-state style distinguishable via theme lookups (gold accents,
## matching the sim's current gold-accent look). Use for check/radio-style
## on-off controls, or as the member of a CSegmented exclusive group.
##
## Defaults (same contract as CButton):
##   - focus_mode = FOCUS_NONE                 — WASD camera keeps working.
##   - mouse_default_cursor_shape = POINTING_HAND
##   - mouse_filter = MOUSE_FILTER_STOP
##   - toggle_mode = true

const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")

## Static factory: a CToggle with the given text, pressed by default or not.
## Sets toggle_mode immediately so the pressed state materializes without
## waiting for _ready() (the tree may add it later).
static func make(text: String, pressed: bool = false) -> CToggle:
	var t := CToggle.new()
	t.text = text
	t.toggle_mode = true
	t.button_pressed = pressed
	return t


func _ready() -> void:
	focus_mode = Control.FOCUS_NONE
	mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	mouse_filter = Control.MOUSE_FILTER_STOP
	toggle_mode = true
	# Pressed-state styling — gold on gold-border, the φ-accent motif. The
	# house theme defines no Button styleboxes, so build a pressed stylebox
	# from the panel tokens (border color + a translucent gold fill).
	var border := _tok_color("panel_border")
	var gold := _tok_color("gold")
	var pressed_style := StyleBoxFlat.new()
	pressed_style.bg_color = Color(gold.r, gold.g, gold.b, 0.18)
	pressed_style.border_color = Color(gold.r, gold.g, gold.b, 0.7)
	pressed_style.set_border_width_all(1)
	pressed_style.set_corner_radius_all(4)
	pressed_style.content_margin_left = 8.0
	pressed_style.content_margin_right = 8.0
	pressed_style.content_margin_top = 3.0
	pressed_style.content_margin_bottom = 3.0
	add_theme_stylebox_override("pressed", pressed_style)
	add_theme_color_override("font_pressed_color", _tok_color("gold_bright"))
	add_theme_color_override("font_hover_pressed_color", _tok_color("gold_bright"))
	add_theme_color_override("font_hover_color", _tok_color("text_bright"))
	# Subtle border on the resting state so the toggle reads as a control.
	var idle_style := StyleBoxFlat.new()
	idle_style.bg_color = Color(0.0, 0.0, 0.0, 0.15)
	idle_style.border_color = border
	idle_style.set_border_width_all(1)
	idle_style.set_corner_radius_all(4)
	idle_style.content_margin_left = 8.0
	idle_style.content_margin_right = 8.0
	idle_style.content_margin_top = 3.0
	idle_style.content_margin_bottom = 3.0
	add_theme_stylebox_override("normal", idle_style)
	add_theme_stylebox_override("hover", idle_style.duplicate())


## Named color from the house theme's "Cassi" token namespace.
func _tok_color(token: String) -> Color:
	return CASSI_THEME.get_color(StringName(token), &"Cassi")
