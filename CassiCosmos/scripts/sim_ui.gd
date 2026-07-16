extends Control
## In-game control panel — self-built, no scene dependencies.
## Space: play/pause | R: reinit

var _info_label: Label
var _n_spin: SpinBox
var _xi_slider: HSlider; var _xi_label: Label
var _pi_slider: HSlider; var _pi_label: Label
var _play_btn: Button
var _fps_accum: float = 0.0; var _fps_count: int = 0; var _fps_display: float = 0.0


func _ready() -> void:
	# Build UI tree
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	# Top-left info panel
	var info_panel = PanelContainer.new()
	info_panel.name = "InfoPanel"
	info_panel.set_anchors_preset(PRESET_TOP_LEFT)
	info_panel.offset_left = 10; info_panel.offset_top = 10
	info_panel.offset_right = 220; info_panel.offset_bottom = 100
	info_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(info_panel)
	_info_label = Label.new()
	_info_label.name = "InfoLabel"
	_info_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info_panel.add_child(_info_label)

	# Bottom control panel
	var control_panel = PanelContainer.new()
	control_panel.name = "ControlPanel"
	control_panel.set_anchors_preset(PRESET_BOTTOM_WIDE)
	control_panel.offset_top = -70
	control_panel.offset_left = 10; control_panel.offset_right = -10
	add_child(control_panel)

	var hbox = HBoxContainer.new()
	hbox.name = "HBox"
	control_panel.add_child(hbox)

	# N control
	var n_label = Label.new(); n_label.text = "N:"
	hbox.add_child(n_label)
	_n_spin = SpinBox.new()
	_n_spin.min_value = 100; _n_spin.max_value = 200000
	_n_spin.step = 1000; _n_spin.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hbox.add_child(_n_spin)
	var apply_btn = Button.new(); apply_btn.text = "Apply N"
	apply_btn.pressed.connect(_on_n_apply)
	hbox.add_child(apply_btn)
	_play_btn = Button.new(); _play_btn.text = "⏸ Pause"
	_play_btn.pressed.connect(_on_play_toggled)
	hbox.add_child(_play_btn)

	# Xi slider
	var xi_pad = VBoxContainer.new(); xi_pad.custom_minimum_size = Vector2(150, 50)
	hbox.add_child(xi_pad)
	_xi_label = Label.new(); _xi_label.text = "xi: 18.0"
	xi_pad.add_child(_xi_label)
	_xi_slider = HSlider.new()
	_xi_slider.min_value = 0; _xi_slider.max_value = 100
	_xi_slider.step = 0.5; _xi_slider.value = 18.0
	_xi_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_xi_slider.value_changed.connect(func(v): _on_xi_changed(v))
	xi_pad.add_child(_xi_slider)

	# Pi_max slider
	var pi_pad = VBoxContainer.new(); pi_pad.custom_minimum_size = Vector2(150, 50)
	hbox.add_child(pi_pad)
	_pi_label = Label.new(); _pi_label.text = "π_max: 0.55"
	pi_pad.add_child(_pi_label)
	_pi_slider = HSlider.new()
	_pi_slider.min_value = 0.3; _pi_slider.max_value = 0.99
	_pi_slider.step = 0.01; _pi_slider.value = 0.55
	_pi_slider.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_pi_slider.value_changed.connect(func(v): _on_pi_changed(v))
	pi_pad.add_child(_pi_slider)

	# Init from sim state
	var sim = _get_sim()
	if sim:
		_n_spin.value = sim.N
		_xi_slider.value = sim.xi
		_pi_slider.value = sim.pi_max
		_play_btn.text = "⏸ Pause" if sim.playing else "▶ Play"


func _process(delta: float) -> void:
	_fps_accum += delta; _fps_count += 1
	if _fps_accum >= 0.5:
		_fps_display = _fps_count / _fps_accum
		_fps_accum = 0.0; _fps_count = 0
	_update_info()


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_SPACE:
				_on_play_toggled()
				get_viewport().set_input_as_handled()
			KEY_R:
				_on_n_apply()
				get_viewport().set_input_as_handled()


func _on_n_apply() -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.N = int(_n_spin.value)
	sim.reinit()


func _on_xi_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.xi = value
	_xi_label.text = "xi: %.1f" % value


func _on_pi_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.pi_max = value
	_pi_label.text = "π_max: %.2f" % value


func _on_play_toggled() -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.playing = not sim.playing
	_play_btn.text = "⏸ Pause" if sim.playing else "▶ Play"


func _get_sim() -> Node3D:
	return get_node_or_null("/root/Main/NBodySim")


func _update_info() -> void:
	var sim = _get_sim()
	var n = sim.N if sim else 0
	var sc = sim._step_count if sim else 0
	_info_label.text = "FPS: %.0f\nBodies: %d\nSteps: %d\n[Space] play/pause  [R] reinit" % [_fps_display, n, sc]
