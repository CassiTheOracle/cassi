class_name CPanel
extends PanelContainer
## CPanel — Cassi UI panel.
##
## A PanelContainer styled by the house theme's `PanelContainer/styles/panel`
## StyleBoxFlat (bg Color(0.02,0.03,0.1,0.9), border Color(0.3,0.5,1,0.5),
## radius 6, 10px content margin). Self-contained: applies the panel
## stylebox override in _ready() from the preloaded theme so the look works
## even in a project with no root theme assigned.
##
## Use as a chrome container around a single content Control (VBox/HBox).
## The panel is a passive chrome vessel — it never captures mouse events
## itself (children do), so WASD camera input is untouched.

const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")

## Static factory: build a titled-less panel wrapping `content`. Convenient
## one-liner for the common call site (e.g. add_cassi_panel(col, content)).
static func with_content(content: Control) -> CPanel:
	var p := CPanel.new()
	p.set_content(content)
	return p


## Static factory: build a panel and append `content` as its single child.
## Mirrors the sim's existing `panel.add_child(vbox)` pattern.
func set_content(content: Control) -> void:
	# A PanelContainer hosts exactly one child; clear any prior one so the
	# factory is idempotent.
	for c in get_children():
		remove_child(c)
	add_child(content)


func _ready() -> void:
	# Pull the house panel stylebox and apply it as an explicit override so
	# this class renders identically whether or not a root theme is set.
	add_theme_stylebox_override("panel", CASSI_THEME.get_stylebox(&"panel", &"PanelContainer"))
