class_name CSpinParam
extends Control
## CSpinParam — Cassi UI spin-box parameter row.
##
## Mirror of CParam for integer/enum-style numeric inputs: a caption CLabel
## ABOVE the SpinBox (VBox separation 4, same theme lookups). Unlike CParam
## there is NO separate value label — the SpinBox shows its own value.
## Restructured from sim_ui.gd's Grid-N / Particles / Clusters / Separation
## boxes (VBox -> caption + SpinBox, rows of ~120–150px min width).
##
## Interaction rule: the SpinBox keeps Godot's default focus_mode of
## FOCUS_NONE — only its inner LineEdit is FOCUS_ALL, so clicking the text
## area still allows keyboard entry, but the control itself never steals
## the WASD camera keys. This matches the library convention (FOCUS_NONE
## on every interactive control). It gets the pointing-hand cursor and its
## text is styled via the theme tokens for dark-theme readability.
##
## Usage:
##   var p := CSpinParam.new()
##   p.box_min_width = 120
##   p.setup("Grid N:", "gold", 64, 256, 64, 64, _on_grid)
##   add_child(p)

const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")

## The caption (param-name) label — style it or read .text as needed.
var caption_label: CLabel
## The SpinBox itself.
var spin: SpinBox

## Min width applied to the row's VBox (sim boxes are 120/150 wide — the
## migration sets it per-row).
var box_min_width: int = 120

var _changed_cb: Callable = Callable()


## Configure the row: `caption` + its color token, the SpinBox range/step/
## initial value, and a callback fired on every value change. Idempotent.
func setup(caption: String, caption_token: String, min_v: float, max_v: float,
		step_v: float, value: float, changed_cb: Callable) -> void:
	_changed_cb = changed_cb
	# Rebuild children if already set up (idempotent).
	for c in get_children():
		remove_child(c)
		c.queue_free()

	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(box_min_width, 40)
	box.add_theme_constant_override("separation", 4)
	add_child(box)

	caption_label = CLabel.make(caption, caption_token, "param")
	box.add_child(caption_label)

	spin = SpinBox.new()
	spin.min_value = min_v
	spin.max_value = max_v
	spin.step = step_v
	spin.value = value
	spin.custom_minimum_size = Vector2(0, 22)
	# Keep Godot's default FOCUS_NONE on the SpinBox (only the inner LineEdit
	# is focusable — clicking it still allows keyboard entry, but the control
	# never steals the WASD camera keys); library convention is FOCUS_NONE.
	spin.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_apply_spin_style()
	box.add_child(spin)

	spin.value_changed.connect(_on_spin_changed)


## Push a new value into the SpinBox WITHOUT firing the callback (used to
## sync from external state, e.g. the sim's live values).
func set_value_no_signal(v: float) -> void:
	spin.set_value_no_signal(v)


## Current SpinBox value (forwarding convenience).
func get_value() -> float:
	return spin.value


func _on_spin_changed(value: float) -> void:
	if _changed_cb.is_valid():
		_changed_cb.call(value)


## Style the SpinBox text so it's readable on the dark theme: the editable
## text in text-bright, finished/uneditable text in text-dim. Overrides are
## applied so the style works without a root theme assignment.
func _apply_spin_style() -> void:
	spin.add_theme_color_override("font_color", _tok_color("text_bright"))
	spin.add_theme_color_override("font_uneditable_color", _tok_color("text_dim"))
	# Baseline for the up/down-arrow icons — keep them visible against the
	# dark field.
	spin.add_theme_color_override("icon_normal_color", _tok_color("text_dim"))
	spin.add_theme_color_override("icon_hover_color", _tok_color("gold_soft"))


## Named color from the house theme's "Cassi" token namespace.
func _tok_color(token: String) -> Color:
	return CASSI_THEME.get_color(StringName(token), &"Cassi")
