class_name COptionParam
extends Control
## COptionParam — Cassi UI option-selector parameter row.
##
## Mirror of CSpinParam for enumerated choices: a caption CLabel ABOVE an
## OptionButton (VBox separation 4, same theme lookups). Restructured from
## sim_ui.gd's Init profile selector (init_box, ~120px min width) and the
## color-source selector.
##
## Interaction rule: the OptionButton is FOCUS_NONE (library convention —
## every interactive control is FOCUS_NONE so the WASD camera keys are never
## stolen). It gets the pointing-hand cursor and its text is styled via the
## theme tokens for dark-theme readability.
##
## Usage:
##   var o := COptionParam.new()
##   o.setup("Init:", "gold", ["Plummer", "Gaussian", "Uniform"], 0, _on_init)
##   add_child(o)

const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")

## The caption (param-name) label — style it or read .text as needed.
var caption_label: CLabel
## The OptionButton itself.
var option: OptionButton

## Min width applied to the row's VBox (sim boxes are ~120 wide — the
## migration sets it per-row).
var box_min_width: int = 120

var _changed_cb: Callable = Callable()


## Report the wrapped content's minimum size as our own so a parent
## Container allocates proper space (see CParam — a plain Control does not
## propagate child min sizes, which collapses the row and stacks its
## content over the next control).
func _get_minimum_size() -> Vector2:
	if get_child_count() > 0:
		return get_child(0).get_combined_minimum_size()
	return custom_minimum_size


func _ready() -> void:
	_fit_child()


## Anchor the wrapped box to fill this Control's rectangle (tracks resizes).
func _fit_child() -> void:
	if get_child_count() > 0:
		(get_child(0) as Control).set_anchors_and_offsets_preset(PRESET_FULL_RECT)


## Configure the row: `caption` + its color token, the choice list, the
## initially selected index, and a callback fired on every selection change.
## Idempotent.
func setup(caption: String, caption_token: String, options: Array[String],
		selected: int, changed_cb: Callable) -> void:
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

	option = OptionButton.new()
	for opt in options:
		option.add_item(opt)
	option.select(selected)
	option.custom_minimum_size = Vector2(0, 22)
	# FOCUS_NONE (library convention — the OptionButton must not steal the
	# WASD camera keys; Button's own default is FOCUS_ALL).
	option.focus_mode = Control.FOCUS_NONE
	option.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_apply_option_style()
	box.add_child(option)

	option.item_selected.connect(_on_option_selected)


## Push a selection index into the OptionButton WITHOUT firing the callback
## (used to sync from external state, e.g. the sim's live mode).
func set_value_no_signal(i: int) -> void:
	option.select(i)


## Currently selected index (forwarding convenience).
func get_value() -> int:
	return option.selected


func _on_option_selected(index: int) -> void:
	if _changed_cb.is_valid():
		_changed_cb.call(index)


## Style the OptionButton text so it's readable on the dark theme. Overrides
## are applied so the style works without a root theme assignment.
func _apply_option_style() -> void:
	option.add_theme_color_override("font_color", _tok_color("text"))
	option.add_theme_color_override("font_hover_color", _tok_color("text_bright"))
	option.add_theme_color_override("font_focus_color", _tok_color("text_bright"))
	# The dropdown arrow — keep it visible against the dark field.
	option.add_theme_stylebox_override("normal", _option_style(_tok_color("panel_border")))
	var hover := _option_style(_tok_color("gold_soft"))
	option.add_theme_stylebox_override("hover", hover)
	option.add_theme_stylebox_override("focus", _option_style(_tok_color("panel_border")))


## A slim boxed style so the OptionButton reads as a control on the dark
## panel (matches the CToggle resting border).
func _option_style(border: Color) -> StyleBoxFlat:
	var s := StyleBoxFlat.new()
	s.bg_color = Color(0.0, 0.0, 0.0, 0.15)
	s.border_color = border
	s.set_border_width_all(1)
	s.set_corner_radius_all(3)
	s.content_margin_left = 8.0
	s.content_margin_right = 8.0
	s.content_margin_top = 2.0
	s.content_margin_bottom = 2.0
	return s


## Named color from the house theme's "Cassi" token namespace.
func _tok_color(token: String) -> Color:
	return CASSI_THEME.get_color(StringName(token), &"Cassi")
