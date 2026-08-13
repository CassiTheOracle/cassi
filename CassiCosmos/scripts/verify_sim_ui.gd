extends Node
## Loads sim_ui.gd (which extends Control and builds the full UI tree in
## _ready) without any CassiSim dependency, then asserts the new VFX
## controls exist and the script parsed + loaded cleanly. Exits
## 0 = loaded clean, 1 = parse/load failure. (Throws a parse error if
## sim_ui.gd has a syntax error, so a clean exit IS the pass.)

const BASE_DIR := "res://scripts/"

var _checks := 0
var _failures := 0


func _ready() -> void:
	await get_tree().process_frame
	await get_tree().process_frame
	var ui := get_node_or_null("../SimUI")
	if ui == null:
		push_error("validate_sim_ui: SimUI node missing")
		get_tree().quit(1)
		return
	_checks += 1
	# The VFX buttons must exist after _ready built the tree.
	for btn_name in ["VfxSizeBtn", "VfxGlowBtn", "VfxDepthBtn", "VfxTwoAxisBtn"]:
		var b := ui.find_child(btn_name, true, false)
		if b == null or not b is CheckButton:
			push_error("validate_sim_ui: missing VFX control %s (might not be built) — sim_ui.gd loaded?" % btn_name)
			_failures += 1
			continue
		_checks += 1
		if b.button_pressed:
			push_error("validate_sim_ui: %s defaulted ON — VFX must default-off" % btn_name)
			_failures += 1
		else:
			_checks += 1
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)
