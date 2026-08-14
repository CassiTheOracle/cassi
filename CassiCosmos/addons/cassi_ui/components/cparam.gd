class_name CParam
extends Control
## CParam — Cassi UI parameter row.
##
## A labeled slider row: a caption CLabel ABOVE an HBoxContainer holding an
## HSlider plus a live value CLabel. Restructured from sim_ui.gd's
## `_build_slider_row` (VBox -> Label + HBox -> HSlider + Label) — the
## difference is the caption stays fixed (the param name) while the value
## label beside the slider shows the live number, updating as you drag.
##
## Layout/spacing constants follow the sim: caption sits alone (VBox
## separation 4), the slider+value HBox separates by 6; the slider is
## 20px tall (sim_ui.gd:743); the row carries a 180px min width like the
## original slider boxes (sim_ui.gd:736).
##
## Value-label formatting (matches the sim's live readouts):
##   - fractional step (e.g. 0.5, 0.01) → one decimal, "%.1f"
##   - integer step (e.g. 1, 64)        → integer, "%d"

const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")

## The caption (param-name) label — style it or read .text as needed.
var caption_label: CLabel
## The live value label beside the slider.
var value_label: CLabel
## The slider itself.
var slider: HSlider

var _step: float = 1.0
var _changed_cb: Callable = Callable()


## Configure the row: `caption` + its color token (gold_soft is the
## default the sim's slider captions use), the slider range/step/initial
## value, and a callback fired on every value change (the sim's
## `_on_xi_changed`-style handler). Idempotent — safe to re-run.
func setup(caption: String, caption_token: String, min_v: float, max_v: float,
		step_v: float, value: float, changed_cb: Callable) -> void:
	_step = step_v
	_changed_cb = changed_cb
	# Rebuild children if already set up (idempotent).
	for c in get_children():
		remove_child(c)
		c.queue_free()

	var box := VBoxContainer.new()
	box.custom_minimum_size = Vector2(180, 40)
	box.add_theme_constant_override("separation", 4)
	add_child(box)

	caption_label = CLabel.make(caption, caption_token, "param")
	box.add_child(caption_label)

	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	box.add_child(row)

	slider = HSlider.new()
	slider.min_value = min_v
	slider.max_value = max_v
	slider.step = step_v
	slider.value = value
	slider.custom_minimum_size = Vector2(0, 20)
	slider.focus_mode = Control.FOCUS_NONE
	slider.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(slider)

	value_label = CLabel.make(_fmt(value), caption_token, "param")
	value_label.custom_minimum_size = Vector2(64, 0)
	row.add_child(value_label)

	slider.value_changed.connect(_on_slider_changed)


## Push a new value into the slider + label WITHOUT firing the callback
## (used to sync from external state, e.g. the sim's live values).
func set_value_no_signal(v: float) -> void:
	slider.set_value_no_signal(v)
	value_label.text = _fmt(v)


## Current slider value (forwarding convenience).
func get_value() -> float:
	return slider.value


func _on_slider_changed(value: float) -> void:
	value_label.text = _fmt(value)
	if _changed_cb.is_valid():
		_changed_cb.call(value)


## Format the live value: one decimal for fractional steps, integer for
## whole-number steps (matches the sim's "xi: %.1f" / integer readouts).
func _fmt(v: float) -> String:
	if floorf(_step) == _step:
		return "%d" % int(round(v))
	return "%.1f" % v
