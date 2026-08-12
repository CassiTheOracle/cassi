extends Control
## Cassi Universe Simulator — control panel.
## Space: play/pause | R: reinit
##
## Top-left info panel: FPS, mode, diagnostics, connection status.
## Bottom control bar: mode buttons, parameter sliders/spinboxes, play/pause, reinit.

# ═══════════════════════════════════════════════════════════════════════
# Member vars
# ═══════════════════════════════════════════════════════════════════════

var _info_label: Label
var _diag_label: Label
var _conn_label: Label

var _mode_btns: Array[Button] = []
var _grav_btns: Array[Button] = []
var _play_btn: Button
var _reinit_btn: Button

var _xi_slider: HSlider;  var _xi_label: Label
var _src_slider: HSlider; var _src_label: Label
var _grid_spin: SpinBox
var _particle_spin: SpinBox
var _nclusters_spin: SpinBox; var _sep_spin: SpinBox
var _init_opt: OptionButton
var _color_opt: OptionButton
var _no_rb_btn: CheckButton
var _bh_toggle_btn: CheckButton
var _phi_box_btn: CheckButton

var _server_ip_edit: LineEdit
var _server_port_edit: LineEdit

var _fps_accum: float = 0.0
var _fps_count: int = 0
var _fps_display: float = 0.0

var _viz_texture_rect: TextureRect

const MODE_NAMES: Array[String] = ["Particles", "Field", "Black Hole", "Cosmology"]
const PHI: float = 1.618033988749895


# ═══════════════════════════════════════════════════════════════════════
# Style
# ═══════════════════════════════════════════════════════════════════════

func _make_panel_style() -> StyleBoxFlat:
	var s = StyleBoxFlat.new()
	s.bg_color = Color(0.02, 0.03, 0.1, 0.9)
	s.border_color = Color(0.3, 0.5, 1.0, 0.5)
	s.set_border_width_all(1)
	s.set_corner_radius_all(6)
	s.set_content_margin_all(10)
	return s


func _make_label(text: String, color: Color = Color(0.8, 0.9, 1.0), font_size: int = 14) -> Label:
	var l = Label.new()
	l.text = text
	l.add_theme_color_override("font_color", color)
	l.add_theme_font_size_override("font_size", font_size)
	return l


# ═══════════════════════════════════════════════════════════════════════
# Ready — build UI tree
# ═══════════════════════════════════════════════════════════════════════

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE

	# ── Full-viewport visualization texture (behind UI panels) ──
	_viz_texture_rect = TextureRect.new()
	_viz_texture_rect.name = "VizTexture"
	_viz_texture_rect.set_anchors_preset(PRESET_FULL_RECT)
	_viz_texture_rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_viz_texture_rect.expand_mode = TextureRect.EXPAND_KEEP_SIZE
	_viz_texture_rect.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	_viz_texture_rect.visible = false
	add_child(_viz_texture_rect)
	move_child(_viz_texture_rect, 0)  # Behind the UI panels

	# Connect to CassiSim texture signals
	var sim = _get_sim()
	if sim:
		if sim.has_signal("field_texture_updated"):
			sim.field_texture_updated.connect(_on_field_texture_updated)
		if sim.has_signal("bh_texture_updated"):
			sim.bh_texture_updated.connect(_on_field_texture_updated)

	# ── Top-left info panel ──────────────────────────────────────
	var info_panel = PanelContainer.new()
	info_panel.name = "InfoPanel"
	info_panel.add_theme_stylebox_override("panel", _make_panel_style())
	info_panel.set_anchors_preset(PRESET_TOP_LEFT)
	info_panel.offset_left = 10; info_panel.offset_top = 10
	info_panel.offset_right = 300; info_panel.offset_bottom = 180
	info_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(info_panel)

	var info_vbox = VBoxContainer.new()
	info_vbox.add_theme_constant_override("separation", 4)
	info_panel.add_child(info_vbox)

	_info_label = _make_label("FPS: --  Mode: --", Color(0.8, 0.9, 1.0), 16)
	info_vbox.add_child(_info_label)

	_diag_label = _make_label("", Color(0.7, 0.85, 1.0), 13)
	_diag_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info_vbox.add_child(_diag_label)

	_conn_label = _make_label("Connection: Local", Color(0.5, 0.7, 0.9), 12)
	info_vbox.add_child(_conn_label)

	# ── Bottom control panel ─────────────────────────────────────
	var control_panel = PanelContainer.new()
	control_panel.name = "ControlPanel"
	control_panel.add_theme_stylebox_override("panel", _make_panel_style())
	control_panel.layout_mode = 1  # LAYOUT_MODE_ANCHORS
	control_panel.set_anchor(SIDE_TOP, 1.0)
	control_panel.set_anchor(SIDE_BOTTOM, 1.0)
	control_panel.set_anchor(SIDE_LEFT, 0.0)
	control_panel.set_anchor(SIDE_RIGHT, 1.0)
	control_panel.offset_top = -180  # accommodate 3 rows of controls
	control_panel.offset_left = 10; control_panel.offset_right = -10
	add_child(control_panel)

	var root_vbox = VBoxContainer.new()
	root_vbox.add_theme_constant_override("separation", 6)
	control_panel.add_child(root_vbox)

	# Row 1: mode buttons + play/pause + reinit
	var row1 = HBoxContainer.new()
	row1.add_theme_constant_override("separation", 8)
	root_vbox.add_child(row1)

	_build_mode_buttons(row1)

	var sep0 = VSeparator.new()
	sep0.custom_minimum_size = Vector2(4, 0)
	row1.add_child(sep0)
	_build_gravity_buttons(row1)

	var sep1 = VSeparator.new()
	sep1.custom_minimum_size = Vector2(4, 0)
	row1.add_child(sep1)
	_play_btn = Button.new()
	_play_btn.text = "⏸ Pause"
	_play_btn.custom_minimum_size = Vector2(90, 30)
	_play_btn.pressed.connect(_on_play_toggled)
	row1.add_child(_play_btn)

	_reinit_btn = Button.new()
	_reinit_btn.text = "↻ Reinit"
	_reinit_btn.custom_minimum_size = Vector2(90, 30)
	_reinit_btn.pressed.connect(_on_reinit)
	row1.add_child(_reinit_btn)

	var sep2 = VSeparator.new()
	sep2.custom_minimum_size = Vector2(4, 0)
	row1.add_child(sep2)

	# Row 2: sliders + spinboxes + server fields
	var row2 = HBoxContainer.new()
	row2.add_theme_constant_override("separation", 12)
	root_vbox.add_child(row2)

	# Xi slider
	_xi_slider = _build_slider_row(row2, "xi: 18.0", 0.0, 100.0, 0.5, 18.0,
		func(v): _on_xi_changed(v))
	_xi_label = row2.get_child(row2.get_child_count() - 1).get_child(0) as Label
	# Re-grab: the helper returns the slider, label is first child of the VBox
	_xi_label = (_xi_slider.get_parent() as VBoxContainer).get_child(0) as Label

	# Source strength slider
	_src_slider = _build_slider_row(row2, "Source: 0.50", 0.0, 2.0, 0.01, 0.5,
		func(v): _on_src_changed(v))
	_src_label = (_src_slider.get_parent() as VBoxContainer).get_child(0) as Label

	# Grid resolution spinbox
	var grid_box = VBoxContainer.new()
	grid_box.custom_minimum_size = Vector2(120, 40)
	row2.add_child(grid_box)
	var grid_lbl = _make_label("Grid N:", Color(0.9, 0.85, 0.5), 12)
	grid_box.add_child(grid_lbl)
	_grid_spin = SpinBox.new()
	# Radix-2 spectral FFT: valid grids are powers of two in [64, 256];
	# non-powers (e.g. 192) are rounded UP by the sim — the control
	# re-syncs to the effective grid after reinit.
	_grid_spin.min_value = 64; _grid_spin.max_value = 256
	_grid_spin.step = 64; _grid_spin.value = 64
	_grid_spin.editable = true
	_grid_spin.custom_minimum_size = Vector2(0, 22)
	grid_box.add_child(_grid_spin)

	# Particle count spinbox
	var part_box = VBoxContainer.new()
	part_box.custom_minimum_size = Vector2(150, 40)
	row2.add_child(part_box)
	var part_lbl = _make_label("Particles:", Color(0.9, 0.85, 0.5), 12)
	part_box.add_child(part_lbl)
	_particle_spin = SpinBox.new()
	_particle_spin.min_value = 100; _particle_spin.max_value = 5000000
	_particle_spin.step = 1000; _particle_spin.value = 20000
	_particle_spin.custom_minimum_size = Vector2(0, 22)

	# Row 3: cluster controls
	var row3 = HBoxContainer.new()
	row3.add_theme_constant_override("separation", 12)
	root_vbox.add_child(row3)

	# Cluster count spinbox
	var nclust_box = VBoxContainer.new()
	nclust_box.custom_minimum_size = Vector2(150, 40)
	row3.add_child(nclust_box)
	var nclust_lbl = _make_label("Clusters:", Color(0.8, 0.6, 0.4), 12)
	nclust_box.add_child(nclust_lbl)
	_nclusters_spin = SpinBox.new()
	_nclusters_spin.min_value = 1; _nclusters_spin.max_value = 20
	_nclusters_spin.step = 1; _nclusters_spin.value = 1
	_nclusters_spin.custom_minimum_size = Vector2(0, 22)
	nclust_box.add_child(_nclusters_spin)

	# Cluster separation spinbox
	var sep_box = VBoxContainer.new()
	sep_box.custom_minimum_size = Vector2(150, 40)
	row3.add_child(sep_box)
	var sep_lbl = _make_label("Separation:", Color(0.4, 0.7, 0.8), 12)
	sep_box.add_child(sep_lbl)
	_sep_spin = SpinBox.new()
	_sep_spin.min_value = 10; _sep_spin.max_value = 500
	_sep_spin.step = 10; _sep_spin.value = 60
	_sep_spin.custom_minimum_size = Vector2(0, 22)
	sep_box.add_child(_sep_spin)

	# Initial-condition profile selector
	var init_box = VBoxContainer.new()
	init_box.custom_minimum_size = Vector2(150, 40)
	row3.add_child(init_box)
	var init_lbl = _make_label("Init:", Color(0.9, 0.85, 0.5), 12)
	init_box.add_child(init_lbl)
	_init_opt = OptionButton.new()
	_init_opt.add_item("Plummer")
	_init_opt.add_item("Gaussian")
	_init_opt.add_item("Uniform")
	_init_opt.selected = 0
	_init_opt.custom_minimum_size = Vector2(0, 22)
	_init_opt.focus_mode = Control.FOCUS_NONE
	init_box.add_child(_init_opt)

	# Particle color scheme selector (live — no reinit; paused view repaints
	# immediately via the sim's one-shot instancer repaint).
	var color_box = VBoxContainer.new()
	color_box.custom_minimum_size = Vector2(160, 40)
	row3.add_child(color_box)
	var color_lbl = _make_label("Color:", Color(0.9, 0.85, 0.5), 12)
	color_box.add_child(color_lbl)
	_color_opt = OptionButton.new()
	_color_opt.add_item("Cassi gradient")
	_color_opt.add_item("Velocity rainbow")
	_color_opt.add_item("Qi rainbow")
	_color_opt.selected = 0
	_color_opt.tooltip_text = "Cassi = mass-temperature gradient (Salpeter blue dwarfs → red giants); Velocity rainbow = hue from speed, slow=red → fast=violet; Qi rainbow = coherence q = EY²+EI², anchored to the φ⁻² decoherence threshold — low q = red, φ⁻² = green, saturated = violet; stable because q is bounded by the field dynamics. Live — no reinit."
	_color_opt.custom_minimum_size = Vector2(150, 22)
	_color_opt.focus_mode = Control.FOCUS_NONE
	_color_opt.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	color_box.add_child(_color_opt)

	# CPU-readback suppression toggle: kills the ~0.5 s stutter (the
	# throttled occupancy/perf/q-tel readbacks stall the global RD).
	_no_rb_btn = CheckButton.new()
	_no_rb_btn.text = "No readbacks"
	_no_rb_btn.tooltip_text = "Suppress CPU readbacks (occupancy/perf/q diagnostics) — removes the ~0.5 s stutter; physics and rendering unchanged"
	_no_rb_btn.custom_minimum_size = Vector2(110, 22)
	_no_rb_btn.focus_mode = Control.FOCUS_NONE
	_no_rb_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row3.add_child(_no_rb_btn)

	# Global BH point-source toggle: works in ANY gravity mode (the shader
	# reads the live toggle from bh[3].x; the host gates the condensation
	# + BH-integrate passes on the same value — no reinit needed).
	_bh_toggle_btn = CheckButton.new()
	_bh_toggle_btn.text = "Black holes"
	_bh_toggle_btn.tooltip_text = "Enable the BH point-source sector (condensation + softened Newtonian pull) in any gravity mode"
	_bh_toggle_btn.custom_minimum_size = Vector2(100, 22)
	_bh_toggle_btn.focus_mode = Control.FOCUS_NONE
	_bh_toggle_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row3.add_child(_bh_toggle_btn)

	# φ-aspect box toggle: the theory's incommensurate bubble-lattice
	# periods (x:y:z = φ:1:φ² — GRID_LAYOUT.md) make the box-mode lattice
	# non-degenerate, removing the cubic straight-line lock at box scale.
	# box_aspect is init-time — reinit() applies the new extents.
	_phi_box_btn = CheckButton.new()
	_phi_box_btn.text = "φ box"
	_phi_box_btn.tooltip_text = "φ-aspect box (x:y:z = φ:1:φ²) — the theory's incommensurate bubble-lattice periods; breaks the cubic box-mode straight-line lock; applies on reinit"
	_phi_box_btn.custom_minimum_size = Vector2(80, 22)
	_phi_box_btn.focus_mode = Control.FOCUS_NONE
	_phi_box_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row3.add_child(_phi_box_btn)

	# Server (future) fields
	var srv_box = VBoxContainer.new()
	srv_box.custom_minimum_size = Vector2(160, 40)
	row2.add_child(srv_box)
	var srv_lbl = _make_label("Server (future):", Color(0.4, 0.5, 0.7), 12)
	srv_box.add_child(srv_lbl)
	var srv_hbox = HBoxContainer.new()
	srv_hbox.add_theme_constant_override("separation", 4)
	srv_box.add_child(srv_hbox)
	_server_ip_edit = LineEdit.new()
	_server_ip_edit.placeholder_text = "IP"
	_server_ip_edit.text = "127.0.0.1"
	_server_ip_edit.custom_minimum_size = Vector2(90, 22)
	_server_ip_edit.editable = false
	_server_ip_edit.modulate = Color(0.5, 0.5, 0.6)
	srv_hbox.add_child(_server_ip_edit)
	_server_port_edit = LineEdit.new()
	_server_port_edit.placeholder_text = "Port"
	_server_port_edit.text = "8080"
	_server_port_edit.custom_minimum_size = Vector2(55, 22)
	_server_port_edit.editable = false
	_server_port_edit.modulate = Color(0.5, 0.5, 0.6)
	srv_hbox.add_child(_server_port_edit)

	# Init from sim if available
	sim = _get_sim()
	if sim:
		_nclusters_spin.value = sim.num_clusters
		_sep_spin.value = sim.cluster_separation
		_xi_slider.value = sim.xi
		_xi_label.text = "xi: %.1f" % sim.xi  # label starts at the builder default otherwise
		_src_slider.value = sim.source_strength
		_grid_spin.value = sim.grid_N
		_particle_spin.value = sim.N_particles
		_update_play_btn(sim.playing)
		_set_mode_highlight(sim.mode)
		_set_grav_highlight(sim.gravity_mode)
		_init_opt.selected = sim.initial_condition
		_color_opt.selected = sim.particle_color_mode
		_no_rb_btn.button_pressed = sim.suppress_readbacks
		_bh_toggle_btn.button_pressed = sim.black_holes_enabled
		_phi_box_btn.button_pressed = (sim.box_aspect != Vector3(1.0, 1.0, 1.0))

	# Connect value_changed AFTER init to avoid spurious reinit() on startup
	_grid_spin.value_changed.connect(_on_grid_changed)
	_particle_spin.value_changed.connect(_on_particles_changed)
	_nclusters_spin.value_changed.connect(_on_clusters_changed)
	_sep_spin.value_changed.connect(_on_separation_changed)
	_init_opt.item_selected.connect(_on_init_selected)
	_color_opt.item_selected.connect(_on_color_mode_selected)
	_no_rb_btn.toggled.connect(_on_suppress_readbacks_toggled)
	_bh_toggle_btn.toggled.connect(_on_black_holes_toggled)
	_phi_box_btn.toggled.connect(_on_phi_box_toggled)

	# Prevent controls from stealing WASD camera input
	_grid_spin.focus_mode = Control.FOCUS_NONE
	_particle_spin.focus_mode = Control.FOCUS_NONE
	_nclusters_spin.focus_mode = Control.FOCUS_NONE
	_sep_spin.focus_mode = Control.FOCUS_NONE
	_xi_slider.focus_mode = Control.FOCUS_NONE
	_src_slider.focus_mode = Control.FOCUS_NONE

# ═══════════════════════════════════════════════════════════════════════
# UI building helpers
# ═══════════════════════════════════════════════════════════════════════

func _build_mode_buttons(parent: HBoxContainer) -> void:
	var group = ButtonGroup.new()
	for i in range(4):
		var btn = Button.new()
		btn.text = MODE_NAMES[i]
		btn.toggle_mode = true
		btn.button_group = group
		btn.button_pressed = (i == 0)
		btn.custom_minimum_size = Vector2(100, 30)
		btn.pressed.connect(_on_mode_pressed.bind(i))
		parent.add_child(btn)
		_mode_btns.append(btn)


func _build_gravity_buttons(parent: HBoxContainer) -> void:
	# Gravity law toggle: 0 = RIVER (the law, default), 1 = HEURISTIC
	# (legacy), 2 = PLUMMER reference (grid-free analytic arm),
	# 3 = RIVER-SELF (river law only — no BH point-source forces),
	# 4 = REALSIM (river law + BH + drag/viscosity/friction dissipation)
	var group = ButtonGroup.new()
	for i in range(5):
		var btn = Button.new()
		btn.text = "River" if i == 0 else ("Heuristic" if i == 1 else ("Plummer ref" if i == 2 else ("River self" if i == 3 else "RealSim")))
		btn.toggle_mode = true
		btn.button_group = group
		btn.button_pressed = (i == 0)
		btn.custom_minimum_size = Vector2(90, 30)
		btn.focus_mode = Control.FOCUS_NONE
		btn.pressed.connect(_on_gravity_mode_pressed.bind(i))
		parent.add_child(btn)
		_grav_btns.append(btn)


func _build_slider_row(parent: HBoxContainer, label_text: String,
		min_v: float, max_v: float, step_v: float, default_v: float,
		callback: Callable) -> HSlider:
	var box = VBoxContainer.new()
	box.custom_minimum_size = Vector2(180, 40)
	parent.add_child(box)
	var lbl = _make_label(label_text, Color(0.9, 0.8, 0.5), 12)
	box.add_child(lbl)
	var slider = HSlider.new()
	slider.min_value = min_v; slider.max_value = max_v
	slider.step = step_v; slider.value = default_v
	slider.custom_minimum_size = Vector2(0, 20)
	slider.value_changed.connect(callback)
	box.add_child(slider)
	return slider


func _on_field_texture_updated(tex: Texture2D) -> void:
	_viz_texture_rect.texture = tex


func _set_mode_highlight(active: int) -> void:
	for i in range(_mode_btns.size()):
		_mode_btns[i].button_pressed = (i == active)
	# Show viz texture only in Field (1) or BH (2) mode
	_viz_texture_rect.visible = (active == 1 or active == 2)


func _set_grav_highlight(active: int) -> void:
	for i in range(_grav_btns.size()):
		_grav_btns[i].button_pressed = (i == active)


# ═══════════════════════════════════════════════════════════════════════
# Process & input
# ═══════════════════════════════════════════════════════════════════════

func _process(delta: float) -> void:
	_fps_accum += delta; _fps_count += 1
	if _fps_accum >= 0.5:
		_fps_display = _fps_count / _fps_accum
		_fps_accum = 0.0; _fps_count = 0
		_update_info()  # status strings change at ~2 Hz; no per-frame rebuilds


func _input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed:
		match event.keycode:
			KEY_SPACE:
				_on_play_toggled()
				get_viewport().set_input_as_handled()
			KEY_R:
				_on_reinit()
				get_viewport().set_input_as_handled()


# ═══════════════════════════════════════════════════════════════════════
# Callbacks
# ═══════════════════════════════════════════════════════════════════════

func _on_mode_pressed(idx: int) -> void:
	var sim = _get_sim()
	if sim:
		sim.mode = idx
	_set_mode_highlight(idx)


func _on_gravity_mode_pressed(idx: int) -> void:
	var sim = _get_sim()
	if sim:
		sim.gravity_mode = idx
	_set_grav_highlight(idx)


func _on_init_selected(idx: int) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.initial_condition = idx
	sim.reinit()  # positions regenerate with the new profile


func _on_color_mode_selected(idx: int) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.particle_color_mode = idx  # live — re-encoded into the instancer PC next physics step (no reinit)
	if not sim.playing:
		sim._repaint_instancer()    # paused: repaint the visible instances now


func _on_suppress_readbacks_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.suppress_readbacks = on


func _on_black_holes_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.black_holes_enabled = on  # live — the host re-encodes bh[3].x next frame (no reinit)


func _on_phi_box_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.box_aspect = Vector3(PHI, 1.0, PHI * PHI) if on else Vector3(1.0, 1.0, 1.0)
	sim.reinit()  # extents are init-time (bh header + PCs) — reinit applies


func _on_xi_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.xi = value
	_xi_label.text = "xi: %.1f" % value


func _on_src_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.source_strength = value
	_src_label.text = "Source: %.2f" % value


func _on_grid_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.grid_N = int(value)
	# Grid change requires reinit — buffer sizes change
	sim.reinit()
	# Show the EFFECTIVE grid (non-powers of two round UP in the sim,
	# e.g. 96 → 128); set_value_no_signal avoids a second reinit.
	_grid_spin.set_value_no_signal(sim.grid_N)


func _on_particles_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.N_particles = int(value)


func _on_clusters_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.num_clusters = int(value)
	sim._step_count = 0  # trigger diagnostic on next frame


func _on_separation_changed(value: float) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.cluster_separation = value
	sim._step_count = 0
	sim.reinit()


func _on_play_toggled() -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.playing = not sim.playing
	_update_play_btn(sim.playing)


func _on_reinit() -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.reinit()


# ═══════════════════════════════════════════════════════════════════════
# UI updates
# ═══════════════════════════════════════════════════════════════════════

func _update_play_btn(is_playing: bool) -> void:
	_play_btn.text = "⏸ Pause" if is_playing else "▶ Play"


func _update_info() -> void:
	var sim = _get_sim()
	if sim:
		var mode_name = MODE_NAMES[sim.mode] if sim.mode >= 0 and sim.mode < MODE_NAMES.size() else "?"
		_info_label.text = "FPS: %.0f  |  Mode: %s" % [_fps_display, mode_name]
		# Convert particle count to readable format
		var p_str = str(sim.N_particles)
		if sim.N_particles >= 1000000:
			p_str = "%.1fM" % (sim.N_particles / 1e6)
		elif sim.N_particles >= 1000:
			p_str = "%.0fk" % (sim.N_particles / 1e3)
		var grav_name := "RIVER" if sim.gravity_mode == 0 else ("HEURISTIC" if sim.gravity_mode == 1 else ("PLUMMER" if sim.gravity_mode == 2 else ("RIVER-SELF" if sim.gravity_mode == 3 else "REALSIM")))
		_diag_label.text = \
			"q_mean: %.4f  ε²: %.6f\n" % [sim._q_mean, sim._eps_mean] + \
			"xi: %.1f  src: %.2f  soften: %.2f\n" % [sim.xi, sim.source_strength, sim.softening] + \
			"sf: %.3f  H: %.4f  steps: %d  drop: %d\n" % [sim._scale_factor, sim._hubble, sim._step_count, sim._dropped_steps] + \
			"N: %s | grid: %d³ | dt: %.4f\n" % [p_str, sim.grid_N, sim.dt] + \
			"grav: %s  G_N=%.4f  calib=%s  attr=%s  chord ξ−1: %.3f\n" % [grav_name, sim._gn_eff, "on" if sim.river_calibrate_gn else "off", "on" if sim.field_attractor_init else "off", sim.PHI_6 - 1.0] + \
			"q∈[%.6f, %.6f]  π/ρ∈[%.4f, %.4f]  sat↑%.1f%% sat↓%.1f%%" % [
				sim._q_min, sim._q_max, sim._pi_min, sim._pi_max,
				sim._pi_sat_hi_frac * 100.0, sim._pi_sat_lo_frac * 100.0]
		_conn_label.text = "Connection: Local"
	else:
		_info_label.text = "FPS: %.0f  |  Mode: --" % _fps_display
		_diag_label.text = "(CassiSim not found)"
		_conn_label.text = "Connection: Disconnected"


func _get_sim() -> Node3D:
	return get_node_or_null("/root/Main/CassiSim")
