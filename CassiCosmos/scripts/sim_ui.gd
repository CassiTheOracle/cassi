extends Control

@onready var _info_label: Label = $"../InfoPanel/InfoLabel"
@onready var _help_panel: Panel = $"../HelpPanel"
@onready var _help_label: Label = $"../HelpPanel/HelpLabel"

var _show_help: bool = true
var _fps_accum: float = 0.0; var _fps_count: int = 0; var _fps_display: float = 0.0


func _ready() -> void:
	_update_help_text()
	var tween = create_tween()
	tween.tween_interval(8.0)
	tween.tween_property(_help_panel, "modulate:a", 0.0, 1.0)
	tween.tween_callback(func(): _help_panel.visible = false)


func _process(delta: float) -> void:
	_fps_accum += delta; _fps_count += 1
	if _fps_accum >= 0.5:
		_fps_display = _fps_count / _fps_accum
		_fps_accum = 0.0; _fps_count = 0
	_update_info()


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_H:
				_show_help = not _show_help
				_help_panel.visible = _show_help
				if _show_help: _help_panel.modulate.a = 1.0


func _update_info() -> void:
	var sim = get_node_or_null("/root/Main/NBodySim")
	var n = sim.N if sim else 0
	var sc = sim._step_count if sim else 0
	var qi = sim.qi_beta if sim else 0.0
	var pm = sim.pi_max if sim else 0.0
	var text = "FPS: %.0f\nBodies: %d\nSteps: %d\nQi: xi=18 β=%.1f π_max=%.2f" % [_fps_display, n, sc, qi, pm]
	_info_label.text = text


func _update_help_text() -> void:
	_help_label.text = """[center][b]Controls[/b][/center]
W/A/S/D  —  Move
Q/E      —  Yaw
Z        —  Up  |  X  —  Down
Space    —  Up  |  Shift  —  Down
Right-drag  —  Orbit camera
Scroll      —  Speed
H         —  Toggle this help"""
