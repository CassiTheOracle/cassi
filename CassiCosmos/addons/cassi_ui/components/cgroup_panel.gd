class_name CGroupPanel
extends CPanel
## CGroupPanel — Cassi UI collapsible titled group panel.
##
## A CPanel whose first child is a collapse header (a CButton toggling
## "▸ Title" / "▾ Title") over a content VBoxContainer you fill with rows.
## Collapsing hides the content (header stays so the group can be reopened).
##
## Used to organize a control panel into collapsible sections without
## stealing camera focus. The header is a CButton, so focus stays
## FOCUS_NONE and the cursor is a pointing hand; its tooltip is
## "collapse/expand" by default.
##
## Usage:
##   var g := CGroupPanel.new()
##   g.set_title("Physics")
##   add_child(g)
##   g.content().add_child(some_row)
##   g.collapsed = true   # hides the content rows

## Emitted when the collapse state flips. `is_collapsed` mirrors `collapsed`.
signal toggled(is_collapsed: bool)

## Collapsed state (default false = expanded). Assigning it flips the
## header glyph and content visibility. Safe to set BEFORE the panel is in
## the tree (content_box is built in _ready()): the value is stored and
## applied once _ready() builds the header + content. The `toggled` signal
## fires only on an actual in-tree flip.
var collapsed: bool = false:
	set(v):
		if collapsed == v:
			return
		collapsed = v
		if content_box == null:
			# Not in the tree yet (or _ready not run) — store only; the
			# header/content don't exist to update and this is initial
			# config, not a user flip, so no signal.
			return
		_update_header()
		content_box.visible = not collapsed
		toggled.emit(collapsed)

var _header: CButton
## The content container — fill this with your rows.
var content_box: VBoxContainer

var _title: String = ""


## Set the group's title. The header reads "<▸|▾> <title>" by collapse state.
## Safe to call before the panel is in the tree (the title is stored and
## applied once _ready() builds the header).
func set_title(t: String) -> void:
	_title = t
	if _header != null:
		_header.text = _header_text(t)


## The content VBoxContainer to populate.
func content() -> VBoxContainer:
	return content_box


func _ready() -> void:
	# Styled as a panel (CPanel._ready applies the panel stylebox). The panel
	# hosts a SINGLE VBoxContainer child (PanelContainer fits every child
	# into the same content rect — it does not stack), which stacks the
	# collapse header ABOVE the content rows.
	super._ready()
	var stack := VBoxContainer.new()
	stack.add_theme_constant_override("separation", 4)
	add_child(stack)

	_header = CButton.new()
	_header.toggle_mode = true
	_header.tooltip_text = "collapse/expand"
	_header.alignment = HORIZONTAL_ALIGNMENT_LEFT
	_header.pressed.connect(_on_header_pressed)
	stack.add_child(_header)

	content_box = VBoxContainer.new()
	content_box.add_theme_constant_override("separation", 6)
	content_box.size_flags_vertical = Control.SIZE_EXPAND_FILL
	stack.add_child(content_box)

	# Apply any collapse state assigned before entering the tree: the glyph
	# comes from _update_header (reads `collapsed`), and the content
	# visibility follows the stored value.
	content_box.visible = not collapsed
	_update_header()


func _on_header_pressed() -> void:
	collapsed = not collapsed


func _update_header() -> void:
	_header.text = _header_text(_title)


func _header_text(title: String) -> String:
	return ("▾ " if not collapsed else "▸ ") + title
