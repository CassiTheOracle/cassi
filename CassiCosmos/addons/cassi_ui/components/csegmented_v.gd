class_name CSegmentedV
extends Control
## CSegmentedV — Cassi UI exclusive vertical segmented list.
##
## The vertical counterpart of CSegmented (addons/cassi_ui/components/
## csegmented.gd): a stack of exclusive CToggle buttons in a VBoxContainer,
## filling the full height available. Mirrors CSegmented's public API so the
## two are drop-in interchangeable for exclusive-choice rows.
##
## Used by the sim's left rail for the vertical Mode / Gravity lists, where
## every choice must stay visible without overflowing the panel width.
##
## Usage:
##   var seg := CSegmentedV.new()
##   seg.button_min_height = 28
##   seg.setup(["River", "Heuristic", "Plummer ref"], 0, _on_gravity)
##   add_child(seg)
##   seg.selected_index = 2   # setter presses the right button

## Emitted when the user picks a different segment (or when
## `selected_index` is assigned). `index` is the newly selected position.
signal selection_changed(index: int)

## The exclusive CToggle buttons, one per option — exposed for styling
## and tooltips after setup().
var buttons: Array[CToggle] = []

## Minimum height of each segment (default 28, matching the rail's compact
## compact row scale).
var button_min_height: int = 28:
	set(v):
		button_min_height = v
		for b in buttons:
			b.custom_minimum_size.y = float(v)

var _selected_index: int = -1
var _vbox: VBoxContainer

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
## optional change callback. Builds the CToggle stack.
func setup(options: Array[String], selected: int, on_changed: Callable = Callable()) -> void:
	# (Re)build the button stack — idempotent so setup() can be re-run.
	for c in get_children():
		remove_child(c)
		c.queue_free()
	buttons.clear()
	_vbox = VBoxContainer.new()
	_vbox.add_theme_constant_override("separation", 6)
	add_child(_vbox)
	_fit_child()  # the built stack fills our rect even if _ready already ran
	for i in range(options.size()):
		var t := CToggle.new()
		t.text = options[i]
		t.custom_minimum_size.y = float(button_min_height)
		t.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		t.toggled.connect(_on_button_toggled.bind(i))
		_vbox.add_child(t)
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
	_fit_child()


## Report the button stack's minimum size so a parent Container gives this
## list real space. A plain Control does not propagate child min sizes —
## without this the list reports ~0 size, its buttons draw at (0,0), and
## overlap the controls below (the stacked-layout bug).
func _get_minimum_size() -> Vector2:
	if _vbox != null:
		return _vbox.get_combined_minimum_size()
	return custom_minimum_size


## Anchor the button stack to fill this Control's rectangle (tracks resizes).
func _fit_child() -> void:
	if _vbox != null:
		_vbox.set_anchors_and_offsets_preset(PRESET_FULL_RECT)
