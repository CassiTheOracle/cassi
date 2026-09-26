class_name CLabel
extends Label
## CLabel — Cassi UI label.
##
## Theme-driven text: colors and font sizes resolve from the house theme's
## "Cassi" token namespace (colors text/text_dim/text_hint/text_bright/gold…,
## font sizes hud/body/detail/param). Applies font_color + font_size
## overrides in _ready() so it renders identically without a root theme.
##
## Mirrors sim_ui.gd's `_make_label(text, color_token, size_token)` helper
## (lines 188-193) — the migration target for every hand-built Label.

const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")

## Display text.
@export var text_content: String = "":
	set(v):
		text_content = v
		text = v
## Which "Cassi" color token to resolve (text, text_dim, text_hint,
## text_bright, gold, gold_soft, gold_bright, cluster, sep, mint, slate,
## disabled).
@export var color_token: String = "text"
## Which "Cassi" font-size token to resolve (hud, body, detail, param).
@export var size_token: String = "body"
## Optional tooltip — shown on hover (wired in for consistency; the sim
## labels that carry explanatory hints set this).


## Static factory: resolve tokens and return a styled label.
## Mirrors sim_ui.gd `_make_label(text, color_token, size_token)`.
static func make(text: String, color_token: String = "text", size_token: String = "body") -> CLabel:
	var l := CLabel.new()
	l.text = text
	l.color_token = color_token
	l.size_token = size_token
	l._apply_tokens()
	return l


func _ready() -> void:
	_apply_tokens()


func _apply_tokens() -> void:
	add_theme_color_override("font_color", _tok_color(color_token))
	add_theme_font_size_override("font_size", _tok_size(size_token))


## Named color from the house theme's "Cassi" token namespace.
func _tok_color(token: String) -> Color:
	return CASSI_THEME.get_color(StringName(token), &"Cassi")


## Named font size from the house theme's "Cassi" token namespace.
func _tok_size(token: String) -> int:
	return CASSI_THEME.get_font_size(StringName(token), &"Cassi")
