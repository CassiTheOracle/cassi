class_name CSegmented
extends Control
## CSegmented — Cassi UI exclusive segmented control.
##
## A group of exclusive CToggle buttons in an HBoxContainer — the sim's
## Mode / Gravity button-group pattern (sim_ui.gd `_build_mode_buttons`,
## `_build_gravity_buttons`) as a reusable component. Manages the
## mutex-selection across children and exposes the selected index.
##
## Usage:
##   var seg := CSegmented.new()
##   seg.setup(["Particles", "Field", "Black Hole", "Cosmology"], 0, _on_mode)
##   add_child(seg)
##   seg.selected_index = 2   # setter presses the right button
##
## Buttons are CToggle (interaction defaults baked in); each entry is a
## `buttons[i]` you can restyle or tooltip after setup.

## Emitted when the user picks a different segment (or when
## `selected_index` is assigned). `index` is the newly selected position.
signal selection_changed(index: int)

## The exclusive CToggle buttons, one per option — exposed for styling
## and tooltips after setup().
var buttons: Array[CToggle] = []

## Minimum width of each segment (default 100, matching the sim's Mode
## buttons at sim_ui.gd:707).
var button_min_width: int = 100:
	set(v):
		button_min_width = v
		for b in buttons:
			b.custom_minimum_size.x = float(v)

var _selected_index: int = -1
var _hbox: HBoxContainer

## The currently selected option index. Getter returns the live value;
## setter presses the matching button (respecting the group mutex).
var selected_index: int:
	get:
		return _selected_index
	set(v):
		if _selected_index == v:
			return
		if v < 0 or v >= buttons.size():
			return
		_selected_index = v
		for i in range(buttons.size()):
			buttons[i].button_pressed = (i == v)
		selection_changed.emit(v)


## Configure with the option list, the initially selected index, and an
## optional change callback. Builds the CToggle row.
func setup(options: Array[String], selected: int, on_changed: Callable = Callable()) -> void:
	# (Re)build the button row — idempotent so setup() can be re-run.
	for c in get_children():
		remove_child(c)
		c.queue_free()
	buttons.clear()
	_hbox = HBoxContainer.new()
	_hbox.add_theme_constant_override("separation", 6)
	add_child(_hbox)
	for i in range(options.size()):
		var t := CToggle.new()
		t.text = options[i]
		t.custom_minimum_size.x = float(button_min_width)
		t.toggled.connect(_on_button_toggled.bind(i))
		_hbox.add_child(t)
		buttons.append(t)
	if on_changed.is_valid():
		# Reconnect loose on re-setup so callbacks don't stack.
		if selection_changed.is_connected(on_changed):
			selection_changed.disconnect(on_changed)
		selection_changed.connect(on_changed)
	# Apply the initial selection WITHOUT emitting: setup() runs during
	# construction, before any consumer is wired — a callback connected
	# via on_changed (or later `selection_changed.connect`) would otherwise
	# fire for the builder's own initial state, not a user pick.
	set_selected_no_signal(selected)


## Press the button at `i` without emitting selection_changed (used when
## syncing from external state, e.g. the sim's live mode).
func set_selected_no_signal(i: int) -> void:
	if i < 0 or i >= buttons.size():
		return
	_selected_index = i
	for b in range(buttons.size()):
		buttons[b].set_pressed_no_signal(b == i)


## Toggle mutex: whenever one CToggle is pressed, unpressed-press the rest
## and emit the selection. A pressed button clicked again stays pressed
## (exclusive group semantics).
func _on_button_toggled(pressed: bool, index: int) -> void:
	if not pressed:
		return
	_selected_index = index
	for i in range(buttons.size()):
		if i != index:
			buttons[i].set_pressed_no_signal(false)
	selection_changed.emit(index)


func _ready() -> void:
	# No FOCUS/cursor needed on the container itself — the CToggle children
	# carry the interaction defaults. Keep the container transparent to
	# input so it never swallows camera events.
	mouse_filter = Control.MOUSE_FILTER_IGNORE
