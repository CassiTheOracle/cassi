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

var _mode_seg: CSegmented
var _mode_btns: Array[CToggle] = []
var _gravity_seg: CSegmented
var _grav_btns: Array[CToggle] = []
var _play_btn: CButton
var _reinit_btn: CButton

var _xi_slider: CParam;  var _xi_label: CLabel
var _src_slider: CParam; var _src_label: CLabel
var _grid_spin: CSpinParam
var _particle_spin: CSpinParam
var _nclusters_spin: CSpinParam; var _sep_spin: CSpinParam
var _init_opt: COptionParam
var _rainbow_btn: CheckButton
var _color_src_opt: OptionButton
var _fit_btn: Button
var _auto_align_btn: CheckButton
var _auto_track_btn: CheckButton
var _scale_label: Label
var _falsify_btn: CheckButton
var _falsify_label: Label
var _save_colors_btn: Button
var _reset_colors_btn: Button
var _legend: Control
var _no_rb_btn: CheckButton
var _bh_toggle_btn: CheckButton
var _phi_box_btn: CheckButton
var _dual_btn: CheckButton
var _multirung_btn: CheckButton
var _meshless_btn: CheckButton
var _vsync_btn: CheckButton
# Particle-VFX upgrades (2026-08-13, default-off): size-by-mass, additive
# glow, depth cue, and the two-axis hue=q/lightness=ρ color mode. These
# OR-ONTO the existing particle_color_mode (low nibble base mode, high
# nibble feature flags) — see compute/cassi_instancer.glsl header.
var _vfx_size_btn: CheckButton
var _vfx_glow_btn: CheckButton
var _vfx_depth_btn: CheckButton
var _vfx_twoaxis_btn: CheckButton

var _server_ip_edit: LineEdit
var _server_port_edit: LineEdit

var _fps_accum: float = 0.0
var _fps_count: int = 0
var _fps_display: float = 0.0

var _viz_texture_rect: TextureRect

const MODE_NAMES: Array[String] = ["Particles", "Field", "Black Hole", "Cosmology"]
const PHI: float = 1.618033988749895
const GradientLegend = preload("res://scripts/gradient_legend.gd")
## House design-language theme (addons/cassi_ui/theme/cassi_theme.tres):
## the single source of truth for the UI's colors and type scale.
const CASSI_THEME: Theme = preload("res://addons/cassi_ui/theme/cassi_theme.tres")


# ═══════════════════════════════════════════════════════════════════════
# Settings registry (Phase 4) — one entry per adjustable parameter. The
# build loop in _ready() drives component construction straight from this
# array: adding a new parameter = one Dictionary entry here (new param =
# one dict entry is the whole contract).
#
# Schema:  {id, kind, caption, token, min, max, step, default, changed,
#           group, [width]}
#   id       — stable string; also selects the direct-ref alias below
#              (xi→_xi_slider/_xi_label, src→_src_slider/_src_label,
#              grid→_grid_spin, particles→_particle_spin,
#              clusters→_nclusters_spin, separation→_sep_spin, init→_init_opt).
#   kind     — "slider" → CParam; "spin" → CSpinParam; "option" → COptionParam.
#   caption  — the row's caption text; token — its "Cassi" color token.
#   min/max/step/default — control range + initial value.
#   changed  — the handler METHOD NAME (GDScript `const` can't hold bound
#              Callables; resolved to Callable(self, name) at build time).
#   group    — which collapsible section owns the row (informational).
#   width    — optional min width for spin/option rows (matches the
#              hand-built VBox boxes; sliders use CParam's internal 180).
#
# NOT registry'd: the `color_src` OptionButton. It lives inside the
# compound Color row (Rainbow + src + Fit scale) and is read in 6+ places
# by the color pipeline (_sync_color_widgets, _apply_particle_color_mode,
# _on_fit_colors, _update_scale_label, _legend.set_sim), so it stays
# inline with the Color row — NOT an independent adjustable parameter.
const PARAMS: Array[Dictionary] = [
	{"id": "xi",         "kind": "slider", "caption": "xi:",        "token": "gold_soft", "min": 0.0,   "max": 100.0,    "step": 0.5,   "default": 18.0,   "changed": "_on_xi_changed",        "group": "Parameters"},
	{"id": "src",        "kind": "slider", "caption": "Source:",    "token": "gold_soft", "min": 0.0,   "max": 2.0,      "step": 0.01,  "default": 0.5,    "changed": "_on_src_changed",       "group": "Parameters"},
	{"id": "grid",       "kind": "spin",   "caption": "Grid N:",    "token": "gold",      "min": 64,    "max": 256,      "step": 64,    "default": 64,     "changed": "_on_grid_changed",      "group": "Parameters", "width": 120},
	{"id": "particles",  "kind": "spin",   "caption": "Particles:", "token": "gold",      "min": 100,   "max": 5000000,  "step": 1000,  "default": 20000,  "changed": "_on_particles_changed", "group": "Parameters", "width": 150},
	{"id": "clusters",   "kind": "spin",   "caption": "Clusters:",  "token": "cluster",   "min": 1,     "max": 20,       "step": 1,     "default": 1,      "changed": "_on_clusters_changed",  "group": "Parameters", "width": 120},
	{"id": "separation", "kind": "spin",   "caption": "Separation:", "token": "sep",     "min": 10,    "max": 500,      "step": 10,    "default": 60,     "changed": "_on_separation_changed", "group": "Parameters", "width": 120},
	{"id": "init",       "kind": "option", "caption": "Init:",      "token": "gold",      "min": 0,     "max": 2,        "step": 1,     "default": 0,      "changed": "_on_init_selected",      "group": "Parameters", "width": 120},
]
## Registry params belonging to the Parameters group's FIRST (row2) HBox;
## the rest go in its second (row3) HBox — reproduces the hand-built
## two-row arrangement exactly.
const PARAMS_ROW2: Array[String] = ["xi", "src", "grid", "particles"]
## Gravity-law segment labels (CSegmented options), matching the old
## _build_gravity_buttons mapping (0=RIVER…4=REALSIM).
const GRAVITY_NAMES: Array[String] = ["River", "Heuristic", "Plummer ref", "River self", "RealSim"]
## Initial-condition profile choices for the Init option row.
const INIT_CHOICES: Array[String] = ["Plummer", "Gaussian", "Uniform"]


# ═══════════════════════════════════════════════════════════════════════
# Auto-Track (2026-08-14) — a CPU-side live-band tracker, opt-in (default
# OFF; the existing scale controls + the sim's GPU auto-aligner are
# untouched while OFF — bit-identical default path).
#
# When ON, this tracker measures the ACTIVE color quantity's LIVE
# distribution from the sim's field buffers (q = EY²+EI² for the Qi/rainbow
# modes, ρ = EY+EI for the two-axis mode) at a low 2–4 Hz subsampled
# readback, computes ROBUST percentiles CPU-side, and EMA-glides the band
# (qi_cycle / qi_approach — the SAME vectors the sim's GPU aligner and the
# legend/instancer read every frame) so the color range hugs the current
# coherence scale and follows it as the universe evolves. High contrast at
# all times, no fixed anchors that saturate or flatten.
#
# Every constant is documented below with its rationale.
# ═══════════════════════════════════════════════════════════════════════

## Sampling cadence: re-measure the field at most every 0.4 s (~2.5 Hz —
## inside the synth's 2–4 Hz low-rate discipline). Subsampled + low-rate so
## the global-RD readback (which self-stalls) is bounded; NEVER per-frame.
const AUTO_TRACK_PERIOD_MS: int = 400
## Readback subsample cap (cells): read at most this many field cells per
## tick so the stall is bounded (default 64³ = 1 MB→ read ~128 KB for q;
## two-axis reads EY+EI → 256 KB). A contiguous central slab of the
## linearized volume (x-fastest), spanning all three axes' middle — the
## region the active coherence occupies — is a representative subsample.
const AUTO_TRACK_MAX_CELLS: int = 32768
## Robust percentiles: 2nd / 98th. Justification — the coherence q is
## log-multiplicative (spans decades), so the tails are long and noisy:
## 1st/99th (the sim's GPU aligner) is yanked by a few tail bins, while
## 5th/95th cuts too deep into the active mass. 2nd/98th trims the extreme
## tails yet still hugs the central body — high contrast without flicker.
const AUTO_TRACK_P_LO: float = 0.02
const AUTO_TRACK_P_HI: float = 0.98
## Band margin (log, ×): extend each edge this fraction past the robust
## percentile so the hue ends aren't clipped at the measured extremes
## (multiplicative margin — 1.3 ≈ ±30% in log). Clamped to the observed
## field [min, max] so the band never leaves the full range.
const AUTO_TRACK_MARGIN: float = 1.3
## EMA ATTACK (fast): when a target moves a band edge OUTWARD (span must
## grow to avoid saturating as the coherence climbs), reach ~half the way
## per tick (α = 0.45 ≈ 0.5 s to mostly extend at 2.5 Hz). Keeps the band
## ahead of fast scale-ups.
const AUTO_TRACK_ATTACK: float = 0.45
## EMA RELEASE (slow): when a target moves an edge INWARD (band could
## tighten), glide with α = 0.08 (~0.6 half-life at 2.5 Hz ≈ a few seconds
## to converge) so per-tick noise can't collapse the band — resists jitter
## and lets the tightened range settle smoothly.
const AUTO_TRACK_RELEASE: float = 0.08
## Hysteresis deadband (log): if a target is within ±10% of the current
## edge (|ln(target/edge)| < 0.1), DON'T move that edge that tick — kills
## per-sample jitter from measurement noise around a stable band.
const AUTO_TRACK_DEADBAND: float = 0.10
## Minimum span floor (log, ratio): the tracked band must always cover at
## least this log length (10×). A static or degenerate field collapses the
## measured percentiles toward a point — without this floor the band would
## collapse to zero contrast; the floor guarantees a full decade of hue.
const AUTO_TRACK_MIN_SPAN: float = 10.0

# Tracker state.
var _autotrack_accum: float = 0.0


# ═══════════════════════════════════════════════════════════════════════
# Live falsification meter (w₀) — default-OFF, opt-in.
# GDScript port of research/falsification/falsify_wo.py's SURVEY path
# estimator (the theory's own H_conv formula + CPL fit). The meter reads
# r = <EY>/<EI> (the volume-mean field ratio) from the sim's field buffers
# at the same low-rate subsampled cadence as the Auto-Track tracker, feeds
# it through this port, and shows w₀ plus its distance to DESI DR2's
# −0.838 on a HUD line — a live falsification loop (loop_design.md).
# ═══════════════════════════════════════════════════════════════════════

## Sampling cadence for the meter: same 2.5 Hz subsampled field readback
## as the Auto-Track tracker (no per-frame work).
const FALSIFY_PERIOD_MS: int = 400
## Readback subsample cap (cells): same bounded subsample policy as the
## tracker — never full-resolution, never per-frame (the stutter lesson).
const FALSIFY_MAX_CELLS: int = 32768

# ── Estimator constants — mirror falsify_wo.py lines 48-58 ──────────────
const FALSIFY_PHI: float = 1.618033988749895     # falsify_wo.py:48
const FALSIFY_PHI_INV: float = 1.0 / FALSIFY_PHI # falsify_wo.py:49
const FALSIFY_LAM: float = 0.02                  # falsify_wo.py:50
const FALSIFY_H_EMPTY: float = (FALSIFY_LAM / 3.0) * FALSIFY_PHI_INV * FALSIFY_PHI_INV  # :51
const FALSIFY_DESI_A_LO: float = 0.3             # :55
const FALSIFY_DESI_A_HI: float = 1.0             # :55
const FALSIFY_N: int = 300                       # np.linspace(0.3,1.0,300) — :231
const FALSIFY_TARGET_W0: float = -0.838          # :54 (DESI DR2 best-fit)
const FALSIFY_DESI_1SIGMA: float = 0.068         # loop_design.md §5 (DESI 1σ)
const FALSIFY_ATTRACTOR_R: float = 1.5892        # calibrated r(a=1) (falsify_wo.py:270)
# ── ODE integration (survey path, falsify_wo.py lines 64-122) ───────────
# The ODE dr/dlna is autonomous in ln a, so a single snapshot r = r(a=1.0)
# reconstructs r(a) over the DESI window by back-integrating to a=0.3.
const FALSIFY_RK_STEPS: int = 20000              # dense RK4 substeps over ln a

# Meter state.
var _falsify_accum: float = 0.0
var _last_falsify_w0: float = NAN
var _last_falsify_wa: float = NAN
var _last_falsify_r: float = NAN


# ═══════════════════════════════════════════════════════════════════════
# Style — the design-language theme
# ═══════════════════════════════════════════════════════════════════════
#
# All visual tokens live in CASSI_THEME (addons/cassi_ui/theme/
# cassi_theme.tres): colors, the type scale, and the panel stylebox.
# PanelContainers are styled automatically by type through the inherited
# theme; labels pull named tokens through _make_label. No literals here.

## Named color from the house theme's "Cassi" token namespace.
func _tok_color(token: String) -> Color:
	return CASSI_THEME.get_color(StringName(token), &"Cassi")


func _make_label(text: String, color_token: String = "text", size_token: String = "body") -> Label:
	var l = Label.new()
	l.text = text
	l.add_theme_color_override("font_color", _tok_color(color_token))
	l.add_theme_font_size_override("font_size", CASSI_THEME.get_font_size(StringName(size_token), &"Cassi"))
	return l


# ═══════════════════════════════════════════════════════════════════════
# Ready — build UI tree
# ═══════════════════════════════════════════════════════════════════════

func _ready() -> void:
	mouse_filter = Control.MOUSE_FILTER_IGNORE
	# The scene file's SimUI root can lack anchor_bottom (main.tscn is the
	# user's live file — never edited here), which collapses the UI to zero
	# height and clips every bottom-anchored panel off-screen. Self-frame to
	# the full viewport before building children so the bottom bar is always
	# visible regardless of the scene's serialized anchors.
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	# House theme — every child inherits it (panels styled by type, labels
	# via tokens). This is the ONE place the look is wired up.
	theme = CASSI_THEME

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
	var info_panel = CPanel.new()
	info_panel.name = "InfoPanel"
	info_panel.set_anchors_preset(PRESET_TOP_LEFT)
	info_panel.offset_left = 10; info_panel.offset_top = 10
	info_panel.offset_right = 300; info_panel.offset_bottom = 215
	info_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(info_panel)

	var info_vbox = VBoxContainer.new()
	info_vbox.add_theme_constant_override("separation", 4)
	info_panel.add_child(info_vbox)

	_info_label = _make_label("FPS: --  Mode: --", "text", "hud")
	info_vbox.add_child(_info_label)

	_diag_label = _make_label("", "text_dim", "detail")
	_diag_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	info_vbox.add_child(_diag_label)

	_conn_label = _make_label("Connection: Local", "text_hint", "param")
	info_vbox.add_child(_conn_label)

	_falsify_label = _make_label("", "gold_bright", "param")
	_falsify_label.name = "FalsifyLabel"
	_falsify_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_falsify_label.visible = false
	info_vbox.add_child(_falsify_label)

	# ── Bottom control panel ─────────────────────────────────────
	var control_panel = CPanel.new()
	control_panel.name = "ControlPanel"
	control_panel.set_anchors_preset(Control.PRESET_BOTTOM_WIDE)
	control_panel.offset_top = -296  # collapsed groups stack tighter; this is the max-height frame (all expanded = today's 4 rows + VFX + legend)
	control_panel.offset_left = 10; control_panel.offset_right = -10
	add_child(control_panel)

	var root_vbox = VBoxContainer.new()
	root_vbox.add_theme_constant_override("separation", 6)
	control_panel.add_child(root_vbox)

	# ── Grouped sections (Phase 4) — the ControlPanel's root VBox is a
	# stack of collapsible CGroupPanels, all DEFAULT EXPANDED (first render
	# = today's rows plus a slim header bar per group). Each group holds the
	# rows it did before. ──────────────────────────────────────────

	# Field: mode segmented + gravity segmented + play/reinit (today's row1)
	var field_group := CGroupPanel.new()
	field_group.set_title("Field")
	root_vbox.add_child(field_group)
	var field_content := field_group.content()

	var row1 = HBoxContainer.new()
	row1.add_theme_constant_override("separation", 8)
	field_content.add_child(row1)

	_mode_seg = CSegmented.new()
	_mode_seg.button_min_width = 100
	_mode_seg.setup(MODE_NAMES, 0)
	_mode_seg.set_selected_no_signal(0)
	_mode_seg.selection_changed.connect(_on_mode_pressed)
	_mode_btns = _mode_seg.buttons
	row1.add_child(_mode_seg)

	var sep0 = VSeparator.new()
	sep0.custom_minimum_size = Vector2(4, 0)
	row1.add_child(sep0)

	_gravity_seg = CSegmented.new()
	_gravity_seg.button_min_width = 90
	_gravity_seg.setup(GRAVITY_NAMES, 0)
	_gravity_seg.set_selected_no_signal(0)
	_gravity_seg.selection_changed.connect(_on_gravity_mode_pressed)
	_grav_btns = _gravity_seg.buttons
	row1.add_child(_gravity_seg)

	var sep1 = VSeparator.new()
	sep1.custom_minimum_size = Vector2(4, 0)
	row1.add_child(sep1)

	_play_btn = CButton.make("⏸ Pause", _on_play_toggled)
	_play_btn.custom_minimum_size = Vector2(90, 30)
	row1.add_child(_play_btn)

	_reinit_btn = CButton.make("↻ Reinit", _on_reinit)
	_reinit_btn.custom_minimum_size = Vector2(90, 30)
	row1.add_child(_reinit_btn)

	var sep2 = VSeparator.new()
	sep2.custom_minimum_size = Vector2(4, 0)
	row1.add_child(sep2)

	# Parameters: registry params (xi/src/grid/particles in the first HBox,
	# clusters/separation/init in the second) + the compound Color row +
	# the standalone check-button cluster — all in the current row order.
	var params_group := CGroupPanel.new()
	params_group.set_title("Parameters")
	root_vbox.add_child(params_group)
	var params_content := params_group.content()

	var row2 = HBoxContainer.new()
	row2.add_theme_constant_override("separation", 12)
	params_content.add_child(row2)
	var row3 = HBoxContainer.new()
	row3.add_theme_constant_override("separation", 12)
	params_content.add_child(row3)

	for p in PARAMS:
		var target: Control = row2 if p.id in PARAMS_ROW2 else row3
		var row_ctrl: Control = _build_param_row(p)
		target.add_child(row_ctrl)

	# Compound Color row: choose the quantity, click Fit scale for a clean
	# starting range, then drag LOW and HIGH on the legend below. The
	# physical white point remains visible on the legend and needs no knob.
	# (color_src stays INLINE here, NOT in the registry — see PARAMS.)
	var color_box = VBoxContainer.new()
	color_box.custom_minimum_size = Vector2(280, 40)
	row3.add_child(color_box)
	var color_lbl = _make_label("Color:", "gold", "param")
	color_box.add_child(color_lbl)
	var color_row = HBoxContainer.new()
	color_row.add_theme_constant_override("separation", 6)
	color_box.add_child(color_row)
	_rainbow_btn = CheckButton.new()
	_rainbow_btn.name = "RainbowBtn"
	_rainbow_btn.text = "Rainbow"
	_rainbow_btn.tooltip_text = "Use the rainbow scale instead of the Cassi mass-temperature colors"
	_rainbow_btn.custom_minimum_size = Vector2(92, 22)
	_rainbow_btn.focus_mode = Control.FOCUS_NONE
	_rainbow_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_rainbow_btn.toggled.connect(_on_rainbow_toggled)
	color_row.add_child(_rainbow_btn)
	_color_src_opt = OptionButton.new()
	_color_src_opt.name = "ColorSrcOpt"
	_color_src_opt.add_item("Velocity")
	_color_src_opt.add_item("Qi")
	_color_src_opt.selected = 1
	_color_src_opt.tooltip_text = "Choose the quantity mapped to color; drag LOW and HIGH on the legend to fit its scale"
	_color_src_opt.custom_minimum_size = Vector2(76, 22)
	_color_src_opt.focus_mode = Control.FOCUS_NONE
	_color_src_opt.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_color_src_opt.item_selected.connect(_on_color_src_selected)
	color_row.add_child(_color_src_opt)
	_fit_btn = Button.new()
	_fit_btn.name = "FitColorsBtn"
	_fit_btn.text = "Fit scale"
	_fit_btn.tooltip_text = "Reset the active source to a simple one-pass scale; then drag LOW and HIGH on the legend"
	_fit_btn.custom_minimum_size = Vector2(78, 22)
	_fit_btn.focus_mode = Control.FOCUS_NONE
	_fit_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_fit_btn.pressed.connect(_on_fit_colors)
	color_row.add_child(_fit_btn)

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

	# VSync toggle: frame pacing to the display refresh. On by default;
	# off for uncapped frame rate (GPU benchmarks, Movie-Maker recording).
	_vsync_btn = CheckButton.new()
	_vsync_btn.text = "VSync"
	_vsync_btn.tooltip_text = "Frame pacing to the display refresh (on by default); off for uncapped frame rate — benchmarks and Movie-Maker recording want it off"
	_vsync_btn.custom_minimum_size = Vector2(80, 22)
	_vsync_btn.focus_mode = Control.FOCUS_NONE
	_vsync_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row3.add_child(_vsync_btn)

	# Cascade-grid toggles (CASCADE_GRID.md): the dual (BCC) grid is LIVE
	# (bh[3].y re-encoded per frame — no reinit) and pairs with the O4
	# gradient (bh[3].z); multi-rung IC seeding is init-time (reinit).
	_dual_btn = CheckButton.new()
	_dual_btn.text = "Dual grid"
	_dual_btn.tooltip_text = "Yin/Yang dual (BCC) lattice gravity + 4th-order gradients — the force averages the base and half-cell-shifted lattices (placement bias ~4.6× down); live, no reinit"
	_dual_btn.custom_minimum_size = Vector2(90, 22)
	_dual_btn.focus_mode = Control.FOCUS_NONE
	_dual_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row3.add_child(_dual_btn)

	_multirung_btn = CheckButton.new()
	_multirung_btn.text = "Multi-rung"
	_multirung_btn.tooltip_text = "Seed the initial conditions with φ-spaced density modes so bubbles condense at several cascade scales; applies on reinit"
	_multirung_btn.custom_minimum_size = Vector2(90, 22)
	_multirung_btn.focus_mode = Control.FOCUS_NONE
	_multirung_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row3.add_child(_multirung_btn)
	_meshless_btn = CheckButton.new()
	_meshless_btn.text = "Meshless"
	_meshless_btn.tooltip_text = "Run the two-fluid field on the moving Voronoi cell mesh (JFA construction, steering + ALE remap); applies on reinit"
	_meshless_btn.custom_minimum_size = Vector2(90, 22)
	_meshless_btn.focus_mode = Control.FOCUS_NONE
	_meshless_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	row3.add_child(_meshless_btn)

	# ── Particle-VFX upgrades row (default-off; bit-identical when off) ──
	# New instancer visuals, each an OPT-IN flag or mode overlaid on the
	# existing color modes (see compute/cassi_instancer.glsl header for the
	# color_mode bit encoding). All live — no reinit.
	var vfx_group := CGroupPanel.new()
	vfx_group.set_title("VFX")
	root_vbox.add_child(vfx_group)
	var vfx_content := vfx_group.content()
	var row_vfx = HBoxContainer.new()
	row_vfx.add_theme_constant_override("separation", 8)
	vfx_content.add_child(row_vfx)
	var vfx_lbl = _make_label("VFX:", "mint", "param")
	vfx_lbl.custom_minimum_size = Vector2(34, 0)
	vfx_lbl.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	vfx_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row_vfx.add_child(vfx_lbl)
	_vfx_size_btn = CheckButton.new()
	_vfx_size_btn.name = "VfxSizeBtn"
	_vfx_size_btn.text = "Size∝m¹ᐟ³"
	_vfx_size_btn.tooltip_text = "Scale each instance by cbrt(particle mass) instead of the linear mass law — the steep Salpeter count compresses so a few massive giants stay visible without swamping the dwarfs. Reads per-particle mass from pos.w (preserved by the nbody kick). Live, no reinit."
	_vfx_size_btn.custom_minimum_size = Vector2(96, 22)
	_vfx_size_btn.focus_mode = Control.FOCUS_NONE
	_vfx_size_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_vfx_size_btn.toggled.connect(_on_vfx_size_toggled)
	row_vfx.add_child(_vfx_size_btn)
	_vfx_glow_btn = CheckButton.new()
	_vfx_glow_btn.name = "VfxGlowBtn"
	_vfx_glow_btn.text = "Glow"
	_vfx_glow_btn.tooltip_text = "Additive-glow look: bright cores (q near the white-hot point) lift toward white and raise alpha so overlapping cores read as additive glow on the dark field; large instances get an extra halo ramp. Live, no reinit."
	_vfx_glow_btn.custom_minimum_size = Vector2(70, 22)
	_vfx_glow_btn.focus_mode = Control.FOCUS_NONE
	_vfx_glow_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_vfx_glow_btn.toggled.connect(_on_vfx_glow_toggled)
	row_vfx.add_child(_vfx_glow_btn)
	_vfx_depth_btn = CheckButton.new()
	_vfx_depth_btn.name = "VfxDepthBtn"
	_vfx_depth_btn.text = "Depth fade"
	_vfx_depth_btn.tooltip_text = "Fade instance alpha with camera distance (linear between 35% and 135% of the box diagonal). Uses the world-origin distance today; the deferred camera hook uses the live camera position. Live, no reinit."
	_vfx_depth_btn.custom_minimum_size = Vector2(104, 22)
	_vfx_depth_btn.focus_mode = Control.FOCUS_NONE
	_vfx_depth_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_vfx_depth_btn.toggled.connect(_on_vfx_depth_toggled)
	row_vfx.add_child(_vfx_depth_btn)
	_vfx_twoaxis_btn = CheckButton.new()
	_vfx_twoaxis_btn.name = "VfxTwoAxisBtn"
	_vfx_twoaxis_btn.text = "2-axis q/ρ"
	_vfx_twoaxis_btn.tooltip_text = "Two-axis color: hue from Qi coherence (as the Qi rainbow) and lightness modulated by local density ρ = EY+EI (q-proxy today; the deferred EY/EI hook uses the true EY+EI). Requires the Rainbow toggle on."
	_vfx_twoaxis_btn.custom_minimum_size = Vector2(96, 22)
	_vfx_twoaxis_btn.focus_mode = Control.FOCUS_NONE
	_vfx_twoaxis_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_vfx_twoaxis_btn.toggled.connect(_on_vfx_twoaxis_toggled)
	row_vfx.add_child(_vfx_twoaxis_btn)
	_falsify_btn = CheckButton.new()
	_falsify_btn.name = "FalsifyBtn"
	_falsify_btn.text = "w₀ live"
	_falsify_btn.tooltip_text = "LIVE falsification meter: reads r = <EY>/<EI> (volume-mean field ratio) at a low 2.5 Hz subsampled rate, runs the theory's w₀/wₐ estimator (the falsify_wo.py survey port), and shows w₀ + distance to DESI DR2's −0.838 on the info HUD. Opt-in; OFF hides the line."
	_falsify_btn.custom_minimum_size = Vector2(76, 22)
	_falsify_btn.focus_mode = Control.FOCUS_NONE
	_falsify_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_falsify_btn.toggled.connect(_on_falsify_toggled)
	row_vfx.add_child(_falsify_btn)

	# ── Color Scale: the legend row + its live numeric readout ──
	# The readout + color controls stay in the LEFT half of the group;
	# the legend control (strip + its sample-swatch row) spans the RIGHT
	# half (EXPAND_FILL horizontally — preserved inside this group).
	var color_scale_group := CGroupPanel.new()
	color_scale_group.set_title("Color Scale")
	root_vbox.add_child(color_scale_group)
	var color_scale_content := color_scale_group.content()
	var legend_row = HBoxContainer.new()
	legend_row.add_theme_constant_override("separation", 8)
	color_scale_content.add_child(legend_row)
	var legend_left = HBoxContainer.new()
	legend_left.add_theme_constant_override("separation", 8)
	legend_left.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	legend_row.add_child(legend_left)
	_scale_label = _make_label("", "text_bright", "param")
	_scale_label.name = "ScaleLabel"
	_scale_label.custom_minimum_size = Vector2(96, 0)
	_scale_label.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_scale_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scale_label.tooltip_text = "Color scale — drag LOW and HIGH on the legend to change it"
	legend_left.add_child(_scale_label)
	_auto_align_btn = CheckButton.new()
	_auto_align_btn.name = "AutoAlignBtn"
	_auto_align_btn.text = "Auto"
	_auto_align_btn.tooltip_text = "Keep the Qi color band aligned to the live coherence distribution (Meshless gravity grows q fast). Dragging a handle or Fit takes over manually."
	_auto_align_btn.custom_minimum_size = Vector2(56, 22)
	_auto_align_btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_auto_align_btn.focus_mode = Control.FOCUS_NONE
	_auto_align_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_auto_align_btn.toggled.connect(_on_auto_align_toggled)
	legend_left.add_child(_auto_align_btn)
	_auto_track_btn = CheckButton.new()
	_auto_track_btn.name = "AutoTrackBtn"
	_auto_track_btn.text = "Auto-Track"
	_auto_track_btn.tooltip_text = "LIVE band tracker: subsampled 2-4 Hz readback of the active quantity's field, robust 2nd-98th percentiles, EMA-glided band with a min-span floor — the color band hugs and follows the live coherence scale (high contrast, no fixed anchors). Manual legend drag or Fit takes over. Opt-in; OFF = existing scale untouched."
	_auto_track_btn.custom_minimum_size = Vector2(90, 22)
	_auto_track_btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_auto_track_btn.focus_mode = Control.FOCUS_NONE
	_auto_track_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_auto_track_btn.toggled.connect(_on_auto_track_toggled)
	legend_left.add_child(_auto_track_btn)
	_save_colors_btn = Button.new()
	_save_colors_btn.name = "SaveColorsBtn"
	_save_colors_btn.text = "Save"
	_save_colors_btn.tooltip_text = "Save the current colors as the default for future runs"
	_save_colors_btn.custom_minimum_size = Vector2(54, 22)
	_save_colors_btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_save_colors_btn.focus_mode = Control.FOCUS_NONE
	_save_colors_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_save_colors_btn.pressed.connect(_on_save_colors)
	legend_left.add_child(_save_colors_btn)
	_reset_colors_btn = Button.new()
	_reset_colors_btn.name = "ResetColorsBtn"
	_reset_colors_btn.text = "Reset"
	_reset_colors_btn.tooltip_text = "Restore the saved colors (Fit scale if none are saved)"
	_reset_colors_btn.custom_minimum_size = Vector2(58, 22)
	_reset_colors_btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_reset_colors_btn.focus_mode = Control.FOCUS_NONE
	_reset_colors_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_reset_colors_btn.pressed.connect(_on_reset_colors)
	legend_left.add_child(_reset_colors_btn)
	_legend = GradientLegend.new()
	_legend.name = "GradientLegend"
	_legend.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_legend.tooltip_text = "Drag LOW and HIGH to fit the active quantity. WHITE marks the physical upper limit; the strip matches the particles exactly."
	_legend.gradient_changed.connect(_on_legend_changed)
	_legend.manual_changed.connect(_on_legend_manual)
	legend_row.add_child(_legend)

	# ── Server (future) fields — today's server row ──
	var srv_group := CGroupPanel.new()
	srv_group.set_title("Server")
	root_vbox.add_child(srv_group)
	var srv_content := srv_group.content()
	var srv_box = VBoxContainer.new()
	srv_box.custom_minimum_size = Vector2(160, 40)
	srv_content.add_child(srv_box)
	var srv_lbl = _make_label("Server (future):", "slate", "param")
	srv_box.add_child(srv_lbl)
	var srv_hbox = HBoxContainer.new()
	srv_hbox.add_theme_constant_override("separation", 4)
	srv_box.add_child(srv_hbox)
	_server_ip_edit = LineEdit.new()
	_server_ip_edit.placeholder_text = "IP"
	_server_ip_edit.text = "127.0.0.1"
	_server_ip_edit.custom_minimum_size = Vector2(90, 22)
	_server_ip_edit.editable = false
	_server_ip_edit.modulate = _tok_color("disabled")
	srv_hbox.add_child(_server_ip_edit)
	_server_port_edit = LineEdit.new()
	_server_port_edit.placeholder_text = "Port"
	_server_port_edit.text = "8080"
	_server_port_edit.custom_minimum_size = Vector2(55, 22)
	_server_port_edit.editable = false
	_server_port_edit.modulate = _tok_color("disabled")
	srv_hbox.add_child(_server_port_edit)

	# Init from sim if available — all no-signal setters so syncing the
	# sim's live values never fires a spurious callback/reinit on startup.
	sim = _get_sim()
	if sim:
		_nclusters_spin.set_value_no_signal(sim.num_clusters)
		_sep_spin.set_value_no_signal(sim.cluster_separation)
		_xi_slider.set_value_no_signal(sim.xi)
		_xi_label.text = "xi: %.1f" % sim.xi  # caption embeds the value (parity with the old row)
		_src_slider.set_value_no_signal(sim.source_strength)
		_grid_spin.set_value_no_signal(sim.grid_N)
		_particle_spin.set_value_no_signal(sim.N_particles)
		_update_play_btn(sim.playing)
		_set_mode_highlight(sim.mode)
		_set_grav_highlight(sim.gravity_mode)
		_init_opt.set_value_no_signal(sim.initial_condition)
		_multirung_btn.button_pressed = sim.multi_rung_seed

		_meshless_btn.button_pressed = sim.meshless_mode
		_sync_color_widgets(sim)
		_no_rb_btn.button_pressed = sim.suppress_readbacks
		_bh_toggle_btn.button_pressed = sim.black_holes_enabled
		_phi_box_btn.button_pressed = (sim.box_aspect != Vector3(1.0, 1.0, 1.0))
		_dual_btn.button_pressed = sim.dual_grid
		_multirung_btn.button_pressed = sim.multi_rung_seed
		_vsync_btn.button_pressed = sim.vsync_enabled

	# Connect value_changed AFTER init to avoid spurious reinit() on startup.
	# (Registry sliders + spins were wired at build time — their init sync
	# above uses set_value_no_signal. The standalone toggles + the init
	# option connect here, matching the pre-migration deferral.)
	_meshless_btn.toggled.connect(_on_meshless_toggled)
	_no_rb_btn.toggled.connect(_on_suppress_readbacks_toggled)
	_bh_toggle_btn.toggled.connect(_on_black_holes_toggled)
	_phi_box_btn.toggled.connect(_on_phi_box_toggled)
	_dual_btn.toggled.connect(_on_dual_grid_toggled)
	_multirung_btn.toggled.connect(_on_multirung_toggled)
	_vsync_btn.toggled.connect(_on_vsync_toggled)

	# All interactive controls (CButton/CToggle/CParam slider/CSegmented +
	# CSpinParam/COptionParam) bake FOCUS_NONE in at the component level, so
	# the WASD camera keys are never stolen — no per-control focus lines here.

# ═══════════════════════════════════════════════════════════════════════
# UI building helpers
# ═══════════════════════════════════════════════════════════════════════

## Build one registry param's control row from a PARAMS entry: construct
## the component, wire the changed callback, store the direct-ref alias,
## and return the row Control for the caller to place in the right group
## sub-row. (New params = one dict entry in PARAMS; no new code here.)
func _build_param_row(p: Dictionary) -> Control:
	var id: String = p.id
	var caption: String = p.caption
	var token: String = p.token
	var width: float = float(p.get("width", 120))
	match p.kind:
		"slider":
			# CParam = caption CLabel above HBox[HSlider + live value CLabel];
			# FOCUS_NONE + pointing hand are baked in. The callback is wired
			# via setup — safe here because the init sync uses
			# set_value_no_signal (geometry: today's row shows the value in
			# BOTH the caption and the value label — parity kept below).
			var param := CParam.new()
			param.setup(caption, token, p.min, p.max, p.step, p.default,
				Callable(self, String(p.changed)))
			if id == "xi":
				_xi_slider = param
				_xi_label = param.caption_label
				# Caption embeds the live value (parity with "xi: %.1f").
				param.caption_label.text = "%s %.1f" % [caption, p.default]
			elif id == "src":
				_src_slider = param
				_src_label = param.caption_label
				param.caption_label.text = "%s %.2f" % [caption, p.default]
			return param
		"spin":
			# CSpinParam = caption CLabel above a SpinBox. Its setup wires
			# value_changed→callback and set_value_no_signal is no-emit, so
			# the init sync is spurious-reinit-safe. The SpinBox keeps the
			# library FOCUS_NONE default (see the component).
			var spin_box := CSpinParam.new()
			spin_box.box_min_width = int(width)
			spin_box.setup(caption, token, p.min, p.max, p.step, p.default,
				Callable(self, String(p.changed)))
			match id:
				"grid":        _grid_spin = spin_box
				"particles":   _particle_spin = spin_box
				"clusters":    _nclusters_spin = spin_box
				"separation":  _sep_spin = spin_box
			return spin_box
		"option":
			# COptionParam = caption CLabel above an OptionButton. Its setup
			# wires item_selected→callback and set_value_no_signal is
			# no-emit, so the init sync is spurious-reinit-safe. The option
			# keeps the library FOCUS_NONE default (see the component).
			var opt_param := COptionParam.new()
			opt_param.box_min_width = int(width)
			opt_param.setup(caption, token, INIT_CHOICES, p.default,
				Callable(self, String(p.changed)))
			_init_opt = opt_param
			return opt_param
	return null


func _sync_color_widgets(sim: Node3D) -> void:
	var cm: int = sim.particle_color_mode
	var base: int = cm & 0xF
	var flags: int = (cm >> 4) & 0xF
	_rainbow_btn.set_pressed_no_signal(base >= 1)
	_color_src_opt.select(0 if base == 1 else 1)
	_auto_align_btn.set_pressed_no_signal(sim.auto_align_colors)
	_vfx_twoaxis_btn.set_pressed_no_signal(base == 4)
	_vfx_size_btn.set_pressed_no_signal((flags & 0x10) != 0)
	_vfx_glow_btn.set_pressed_no_signal((flags & 0x20) != 0)
	_vfx_depth_btn.set_pressed_no_signal((flags & 0x40) != 0)
	_sync_color_enabled()
	if _legend:
		_legend.set_sim(sim, _color_src_opt.selected == 1)
	_update_scale_label()


## Live numeric readout of the active color scale (the values the LOW/HIGH
## legend handles set). Engine slots: 2 = lo1, 10 = hiC, 13 = a_hi (white
## point), 15 = approach_on. Empty when the rainbow is off.
func _update_scale_label() -> void:
	var sim = _get_sim()
	if sim == null or _scale_label == null:
		return
	if sim.particle_color_mode == 0 or not sim.has_method("gradient_engine"):
		_scale_label.text = ""
		return
	var e: PackedFloat32Array = sim.gradient_engine()
	if e.size() < 17 or e[11] <= 0.0:
		_scale_label.text = ""
		return
	var s: String = "%s → %s" % [_fmt_scale(e[2]), _fmt_scale(e[10])]
	_scale_label.text = s
	if e[15] > 0.5:
		_scale_label.tooltip_text = "%s color scale — drag LOW and HIGH on the legend to change it; WHITE is the fixed %s" % ["Qi" if _color_src_opt.selected == 1 else "Velocity", _fmt_scale(e[13])]
	else:
		_scale_label.tooltip_text = "%s color scale — drag LOW and HIGH on the legend to change it" % ("Qi" if _color_src_opt.selected == 1 else "Velocity")


func _fmt_scale(v: float) -> String:
	if v <= 0.0:
		return "0"
	if v >= 100.0:
		return str(int(v))
	var s := "%.4f" % v
	while s.ends_with("0"):
		s = s.substr(0, s.length() - 1)
	if s.ends_with("."):
		s = s.substr(0, s.length() - 1)
	return s


func _sync_color_enabled() -> void:
	var on: bool = _rainbow_btn.button_pressed
	_color_src_opt.disabled = not on
	_fit_btn.disabled = not on


func _on_field_texture_updated(tex: Texture2D) -> void:
	_viz_texture_rect.texture = tex


func _set_mode_highlight(active: int) -> void:
	_mode_seg.set_selected_no_signal(active)
	# Show viz texture only in Field (1) or BH (2) mode
	_viz_texture_rect.visible = (active == 1 or active == 2)


func _set_grav_highlight(active: int) -> void:
	_gravity_seg.set_selected_no_signal(active)


# ═══════════════════════════════════════════════════════════════════════
# Auto-Track — the live band tracker (see the constant block above)
# ═══════════════════════════════════════════════════════════════════════
#
# The tracker opens the SAME seam the sim's GPU auto-aligner uses: it
# writes sim.qi_cycle / sim.qi_approach, which _fill_instancer_pc() (the
# instancer PC) and the legend's pins both consume every frame. So the
# moving band reaches the shader and the legend with ZERO cassi_sim.gd /
# shader changes; when Auto-Track is ON we clear sim.auto_align_colors so
# the GPU aligner doesn't fight over those vectors.
#
# Active quantity by color base mode (compute/cassi_instancer.glsl):
#   base 1 (velocity)  → |v| lives in the velocity buffer, NOT a field
#                        grid — no field quantity; Auto-Track stands idle
#                        (the velocity band keeps its init-measured AUTO).
#   base 2/3 (Qi)      → q = EY²+EI²  (reads sim._field_q)
#   base 4 (two-axis)  → ρ = EY+EI    (reads sim._field_ey + _field_ei)
#
# Measurement: a subsampled, low-rate (2.5 Hz) readback of the active
# field buffer — a contiguous central slab of the linearized volume — with
# the CSV histogram percentiles computed CPU-side. Never per-frame or
# full-resolution (the stutter lesson); the read is capped to a bounded
# subsample and gated on the sim's suppress_readbacks flag (the same
# convention that silences the other global-RD readbacks on demand).

## Per-frame cadence driver: accumulate wall time, run the sampler/tracker
## at ~2.5 Hz while the Auto-Track button is active.
func _autotrack_tick(delta: float) -> void:
	var sim = _get_sim()
	if sim == null or sim._rd == null or sim._field_q == null:
		return
	if not sim._field_q.is_valid():
		return
	if sim.suppress_readbacks:
		return  # reading the global RD would stall — leave the band frozen
	_autotrack_accum += delta
	if _autotrack_accum * 1000.0 < float(AUTO_TRACK_PERIOD_MS):
		return
	_autotrack_accum = 0.0
	var band := _autotrack_measure()
	if band.x > 0.0:
		_autotrack_update(band.x, band.y)


## Measure the active quantity's distribution and return the target band
## (lo, hi) for the tracker — or (-1, -1) when nothing is measurable.
## Exposed for the probe scene (verify_autotrack.gd).
func _autotrack_measure() -> Vector2:
	var sim = _get_sim()
	if sim == null or sim._rd == null:
		return Vector2(-1.0, -1.0)
	var base: int = sim.particle_color_mode & 0xF
	if base < 2:
		return Vector2(-1.0, -1.0)  # velocity/mass modes: no field quantity
	var two_axis: bool = base == 4
	if not sim._field_q.is_valid():
		return Vector2(-1.0, -1.0)
	if two_axis and (not sim._field_ey.is_valid() or not sim._field_ei.is_valid()):
		return Vector2(-1.0, -1.0)
	var nc: int = sim.grid_N * sim.grid_N * sim.grid_N
	if nc <= 0:
		return Vector2(-1.0, -1.0)
	var sample_cells: int = mini(nc, AUTO_TRACK_MAX_CELLS)
	# Subsample: a contiguous central slab of the linearized volume
	# (x-fastest), spanning all three axes' middle — the region the active
	# coherence occupies. Cheap, low-rate, not full-resolution.
	var offset: int = maxi((nc - sample_cells) / 2, 0)
	var data: PackedByteArray = sim._rd.buffer_get_data(sim._field_q, offset * 4, sample_cells * 4)
	if data.size() < sample_cells * 4:
		return Vector2(-1.0, -1.0)
	var vals: PackedFloat32Array = data.to_float32_array()
	if two_axis:
		# Two-axis: the band tracks ρ = EY+EI (the lightness axis).
		var ey_d: PackedByteArray = sim._rd.buffer_get_data(sim._field_ey, offset * 4, sample_cells * 4)
		var ei_d: PackedByteArray = sim._rd.buffer_get_data(sim._field_ei, offset * 4, sample_cells * 4)
		if ey_d.size() < sample_cells * 4 or ei_d.size() < sample_cells * 4:
			return Vector2(-1.0, -1.0)
		var ey: PackedFloat32Array = ey_d.to_float32_array()
		var ei: PackedFloat32Array = ei_d.to_float32_array()
		for i in range(sample_cells):
			vals[i] = maxf(ey[i] + ei[i], 0.0)
	# Robust percentiles CPU-side: collect only positive, finite samples
	# (background/void → q ≤ 0 reads the floor) and sort.
	var clean: PackedFloat32Array = PackedFloat32Array()
	var vmin := INF
	var vmax := -INF
	for i in range(sample_cells):
		var v := vals[i]
		if v > 0.0 and is_finite(v):
			clean.append(v)
			vmin = minf(vmin, v)
			vmax = maxf(vmax, v)
	if clean.size() < 64:
		return Vector2(-1.0, -1.0)  # too few valid samples this tick
	clean.sort()
	var lo_idx: int = clampi(int(round(float(clean.size() - 1) * AUTO_TRACK_P_LO)), 0, clean.size() - 1)
	var hi_idx: int = clampi(int(round(float(clean.size() - 1) * AUTO_TRACK_P_HI)), 0, clean.size() - 1)
	var p_lo := clean[lo_idx]
	var p_hi := clean[hi_idx]
	if p_hi <= p_lo * 1.001:
		p_hi = p_lo * 1.001
	# Margins (±AUTO_TRACK_MARGIN in log), clamped STRICTLY to the observed
	# field [min, max] so the band never exceeds the full range (G50) — the
	# margin only yields headroom when the robust percentiles sit inside the
	# observed span (the normal, tight-central-mass case).
	var band_lo: float = clampf(p_lo / AUTO_TRACK_MARGIN, vmin, vmax)
	var band_hi: float = clampf(p_hi * AUTO_TRACK_MARGIN, vmin, vmax)
	return Vector2(band_lo, band_hi)


## Glide one band edge toward a target with asymmetric attack/release + a
## hysteresis deadband. Operates in LOG space (the coherence is
## multiplicative — a ratio target moves as a ratio step, so the EMA's
## time constants are ratio-consistent). Returns the new edge value.
func _autotrack_glide_edge(current: float, target: float, expanding: bool) -> float:
	if target <= 0.0 or current <= 0.0:
		return maxf(current, target)
	var dl := log(target / current)
	if absf(dl) < AUTO_TRACK_DEADBAND:
		return current  # hysteresis: ignore sub-deadband jitter
	var alpha: float = AUTO_TRACK_ATTACK if expanding else AUTO_TRACK_RELEASE
	return exp(lerp(log(current), log(target), alpha))


## Apply a measured (lo, hi) band to the tracked qi_cycle/qi_approach with
## EMA glide, the hysteresis deadband, and the min-span floor. Returns the
## applied (lo, hi) for probes. Exposed for verify_autotrack.gd.
func _autotrack_update(band_lo: float, band_hi: float) -> Vector2:
	var sim = _get_sim()
	if sim == null:
		return Vector2(-1.0, -1.0)
	var lo := maxf(band_lo, 1e-12)
	var hi := maxf(band_hi, lo * 1.001)
	var c_lo := maxf(sim.qi_cycle.x, 1e-12)
	var c_hi := maxf(sim.qi_cycle.y, c_lo * 1.001)
	# Per-edge attack/release: expanding (span grows) uses the fast attack;
	# contracting (span shrinks) uses the slow release.
	var n_lo := _autotrack_glide_edge(c_lo, lo, lo < c_lo)
	var n_hi := _autotrack_glide_edge(c_hi, hi, hi > c_hi)
	# Min-span floor: a static/degenerate field must not collapse the band
	# to zero contrast — widen to the floor around the geometric mid.
	if log(n_hi / n_lo) < log(AUTO_TRACK_MIN_SPAN):
		var mid := sqrt(n_lo * n_hi)
		var half := sqrt(AUTO_TRACK_MIN_SPAN)
		n_lo = mid / half
		n_hi = mid * half
	# Write the SAME vectors the GPU aligner / legend / instancer consume.
	sim.qi_cycle = Vector2(n_lo, n_hi)
	if sim.qi_approach.x != n_hi:
		sim.qi_approach = Vector2(n_hi, sim.qi_approach.y)
	return Vector2(n_lo, n_hi)


# ═══════════════════════════════════════════════════════════════════════
# Live falsification meter — the w₀ estimator (loop_design.md §2-3)
# ═══════════════════════════════════════════════════════════════════════
#
# Same low-rate discipline as Auto-Track: a subsampled (bounded, capped)
# readback of the field buffers at ~2.5 Hz, computed CPU-side. The meter
# reads r = <EY>/<EI> (volume-mean ratio), feeds it through the GDScript
# port of falsify_wo.py's survey-path estimator, and shows w₀, w_a, r and
# the distance to DESI DR2's w₀ = −0.838 on the info HUD. Verdict gated
# per loop_design.md §5 — no agreement claim until the sim reaches the
# calibrated φ-attractor.

## Per-frame cadence driver for the meter (~2.5 Hz).
func _falsify_tick(delta: float) -> void:
	var sim = _get_sim()
	if sim == null or sim._rd == null:
		return
	if sim._field_ey == null or sim._field_ei == null:
		return
	if not sim._field_ey.is_valid() or not sim._field_ei.is_valid():
		return
	if sim.suppress_readbacks:
		return  # reading the global RD would stall — leave the last estimate
	_falsify_accum += delta
	if _falsify_accum * 1000.0 < float(FALSIFY_PERIOD_MS):
		return
	_falsify_accum = 0.0
	var r: float = _falsify_measure_r()
	if is_finite(r) and r > 0.0:
		var est: Vector2 = _falsify_w0_wa(r)   # (w0, wa) from the survey-path estimator
		_last_falsify_r = r
		_last_falsify_w0 = est.x
		_last_falsify_wa = est.y
		_update_falsify_label()


## Measure r = <EY>/<EI> from a subsampled slice of the field buffers —
## volume-mean ratio (loop_design.md: r = <EY>/<EI>). Returns -1 when
## nothing measurable. Exposed for the probe (verify_falsify.gd).
func _falsify_measure_r() -> float:
	var sim = _get_sim()
	if sim == null or sim._rd == null:
		return -1.0
	if not sim._field_ey.is_valid() or not sim._field_ei.is_valid():
		return -1.0
	var nc: int = sim.grid_N * sim.grid_N * sim.grid_N
	if nc <= 0:
		return -1.0
	var sample_cells: int = mini(nc, FALSIFY_MAX_CELLS)
	var offset: int = maxi((nc - sample_cells) / 2, 0)
	var ey_d: PackedByteArray = sim._rd.buffer_get_data(sim._field_ey, offset * 4, sample_cells * 4)
	var ei_d: PackedByteArray = sim._rd.buffer_get_data(sim._field_ei, offset * 4, sample_cells * 4)
	if ey_d.size() < sample_cells * 4 or ei_d.size() < sample_cells * 4:
		return -1.0
	var ey := ey_d.to_float32_array()
	var ei := ei_d.to_float32_array()
	# Volume-mean: sum the positive-definite fields (EQ of the ratio of
	# means = ratio of the spatially averaged fields, falsify_wo.py:207-209).
	var ey_sum := 0.0
	var ei_sum := 0.0
	var n_ok := 0
	for i in range(sample_cells):
		var eyv: float = ey[i]
		var eiv: float = ei[i]
		if is_finite(eyv) and is_finite(eiv) and eyv > 0.0 and eiv > 0.0:
			ey_sum += eyv
			ei_sum += eiv
			n_ok += 1
	if n_ok < 64 or ei_sum <= 0.0:
		return -1.0
	return ey_sum / ei_sum


## Survey-path estimator: given r = r(a=1.0) (today), reconstruct r(a) over
## the DESI window a∈[0.3,1.0] by back-integrating the theory ODE, then
## CPL-fit (w0, wa). Port of falsify_wo.py `w0_wa_from_r` + `_integrate_r`
## (lines 76-148). Returns (w0, wa).
static func _falsify_w0_wa(r: float) -> Vector2:
	# ── 1. Build the a-grid (np.linspace(0.3,1.0,300), falsify_wo.py:231) ─
	var a := PackedFloat32Array()
	a.resize(FALSIFY_N)
	var h_a: float = (FALSIFY_DESI_A_HI - FALSIFY_DESI_A_LO) / float(FALSIFY_N - 1)
	for i in range(FALSIFY_N):
		a[i] = FALSIFY_DESI_A_LO + float(i) * h_a
	# ── 2. Back-integrate r(a) anchored at r(1.0) — RK4 dense over ln a ──
	# The ODE is autonomous in t = ln a; t runs from ln(1.0)=0 down to
	# ln(0.3) (falsify_wo.py _integrate_r below-anchor segment, :88-107).
	var t_lo: float = log(maxf(FALSIFY_DESI_A_LO, 1e-6))
	var t_hi: float = log(FALSIFY_DESI_A_HI)   # 0.0
	var dt: float = (t_lo - t_hi) / float(FALSIFY_RK_STEPS)   # negative
	# Evaluate r at each a-grid point (in descending t) via dense linear
	# interpolation between RK4 substeps.
	var rt := PackedFloat32Array()
	rt.resize(FALSIFY_N)
	rt[FALSIFY_N - 1] = r   # at a = 1.0 (t = 0)
	var r_cur: float = r
	var t_cur: float = t_hi
	# Walk the grid points from a=1.0 (index N-1) down to a=0.3 (index 0).
	var gi: int = FALSIFY_N - 2
	for s in range(FALSIFY_RK_STEPS):
		var t_next: float = t_cur + dt
		var tt: float = t_cur
		var rk1: float = _falsify_dr_dlna(r_cur)
		var rk2: float = _falsify_dr_dlna(r_cur + 0.5 * dt * rk1)
		var rk3: float = _falsify_dr_dlna(r_cur + 0.5 * dt * rk2)
		var rk4: float = _falsify_dr_dlna(r_cur + dt * rk3)
		var r_next: float = r_cur + (dt / 6.0) * (rk1 + 2.0 * rk2 + 2.0 * rk3 + rk4)
		# Fill any a-grid points crossed in this substep (t descends: t_cur
		# ≥ tg ≥ t_next). Linear interp between the step endpoints.
		while gi >= 0:
			var tg := log(maxf(a[gi], 1e-6))
			if tg <= t_cur and tg >= t_next:
				var f: float = (tg - t_next) / (t_cur - t_next)   # 1 at t_cur, 0 at t_next
				rt[gi] = r_cur + (r_next - r_cur) * f
				gi -= 1
			else:
				break
		r_cur = r_next
		t_cur = t_next
		if gi < 0:
			break
	if rt[0] <= 0.0:
		rt[0] = maxf(rt[0], 1e-12)
	# ── 3. w(a) and the CPL fit (falsify_wo.py w0_wa_from_r, :129-147) ──
	# H = H_EMPTY + H_conv(r); w = -1 - (2/3) d ln H / d ln a; CPL fit over
	# the DESI window with column [1, 1-a].
	var w := PackedFloat32Array()
	w.resize(FALSIFY_N)
	var dlnH := PackedFloat32Array(); dlnH.resize(FALSIFY_N)
	var dlna := PackedFloat32Array(); dlna.resize(FALSIFY_N)
	for i in range(FALSIFY_N):
		var ri: float = maxf(rt[i], 1e-30)
		var h_conv: float = (FALSIFY_LAM / 3.0) * (FALSIFY_PHI - ri) * (1.0 + ri) / (ri + 1e-30)
		var hi: float = FALSIFY_H_EMPTY + h_conv
		dlnH[i] = log(hi + 1e-30)
		dlna[i] = log(maxf(a[i], 1e-30))
	# np.gradient with uniform a-spacing h_a (central diff, one-sided edges).
	for i in range(FALSIFY_N):
		var dh: float
		var da: float
		if i == 0:
			dh = (dlnH[1] - dlnH[0]) / h_a
			da = (dlna[1] - dlna[0]) / h_a
		elif i == FALSIFY_N - 1:
			dh = (dlnH[FALSIFY_N - 1] - dlnH[FALSIFY_N - 2]) / h_a
			da = (dlna[FALSIFY_N - 1] - dlna[FALSIFY_N - 2]) / h_a
		else:
			dh = (dlnH[i + 1] - dlnH[i - 1]) / (2.0 * h_a)
			da = (dlna[i + 1] - dlna[i - 1]) / (2.0 * h_a)
		w[i] = -1.0 - (2.0 / 3.0) * dh / maxf(da, 1e-30)
	# Least squares: A = [1, 1-a], solve A^T А x = A^T w (2x2 normal eqs).
	var s00 := 0.0  # A^T A [0][0] = Σ 1
	var s01 := 0.0  # Σ (1-a)
	var s11 := 0.0  # Σ (1-a)²
	var s0w := 0.0  # Σ w
	var s1w := 0.0  # Σ w·(1-a)
	for i in range(FALSIFY_N):
		var one_a: float = 1.0 - a[i]
		s00 += 1.0
		s01 += one_a
		s11 += one_a * one_a
		s0w += w[i]
		s1w += w[i] * one_a
	var det: float = s00 * s11 - s01 * s01
	if absf(det) < 1e-30:
		return Vector2(-1.0, -1.0)
	var w0: float = (s11 * s0w - s01 * s1w) / det
	var wa: float = (s00 * s1w - s01 * s0w) / det
	return Vector2(w0, wa)


## dr/dlna — the theory ODE (falsify_wo.py `_ode_dr_dlna`, lines 64-73).
static func _falsify_dr_dlna(r: float) -> float:
	var h_conv: float = (FALSIFY_LAM / 3.0) * (FALSIFY_PHI - r) * (1.0 + r) / maxf(r, 1e-12)
	var h: float = FALSIFY_H_EMPTY + h_conv
	var eps_sq: float = (r - FALSIFY_PHI) * (r - FALSIFY_PHI) * FALSIFY_PHI * FALSIFY_PHI \
		/ ((1.0 + r) * (1.0 + r) + 1e-30)
	var gate: float = (FALSIFY_PHI_INV * FALSIFY_PHI_INV + eps_sq) \
		/ (FALSIFY_PHI * FALSIFY_PHI + FALSIFY_PHI_INV * FALSIFY_PHI_INV + eps_sq + 1e-30)
	return FALSIFY_LAM * gate * (FALSIFY_PHI - r) * (1.0 + r) / (h + 1e-30)


## Refresh the HUD line with the latest estimate + DESI distance. Honest
## verdict gating per loop_design.md §5: no agreement claim until r sits
## near the calibrated attractor.
func _update_falsify_label() -> void:
	if _falsify_label == null:
		return
	if not is_finite(_last_falsify_w0):
		_falsify_label.text = "w₀: — (no field ratio yet)"
		return
	var delta_w0: float = _last_falsify_w0 - FALSIFY_TARGET_W0
	var abs_d: float = absf(delta_w0)
	var verdict: String
	if abs_d <= FALSIFY_DESI_1SIGMA:
		verdict = "WITHIN 1σ"
	elif abs_d <= 2.0 * FALSIFY_DESI_1SIGMA:
		verdict = "MARGINAL (1-2σ)"
	else:
		verdict = "FALSIFIED (>2σ)"
	# Relaxation gate: until r is near the calibrated attractor the estimate
	# is not falsifiable (loop_design.md §4.1, §5) — show it plainly.
	var relaxed: bool = absf(_last_falsify_r - FALSIFY_ATTRACTOR_R) <= 0.05
	var note: String = "" if relaxed \
		else "  [r≠1.59 — still relaxing to φ-attractor; not yet meaningful]"
	_falsify_label.text = \
		("w₀=%s w_a=%s  r=<EY>/<EI>=%s (φ=%.3f)\n" \
		 + "Δw₀ vs DESI %s = %s  [%s]%s") % [
		_fmt_sign(_last_falsify_w0), _fmt_sign(_last_falsify_wa),
		_fmt_sign(_last_falsify_r), FALSIFY_PHI,
		_fmt_sign(FALSIFY_TARGET_W0), _fmt_sign(delta_w0), verdict, note]


## Signed compact formatter for the meter (w₀/wₐ/delta can be negative —
## the ui's _fmt_scale collapses ≤ 0 to "0").
func _fmt_sign(v: float) -> String:
	if not is_finite(v):
		return "—"
	if absf(v) >= 100.0:
		return "%.1f" % v
	if absf(v) >= 0.1:
		return "%.4f" % v
	if absf(v) >= 0.01:
		return "%.5f" % v
	return "%.6f" % v


# ═══════════════════════════════════════════════════════════════════════
# Process & input
# ═══════════════════════════════════════════════════════════════════════

func _process(delta: float) -> void:
	_fps_accum += delta; _fps_count += 1
	if _auto_track_btn != null and _auto_track_btn.button_pressed:
		_autotrack_tick(delta)
	if _falsify_btn != null and _falsify_btn.button_pressed:
		_falsify_tick(delta)
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


func _on_rainbow_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	_apply_particle_color_mode(sim)
	_sync_color_widgets(sim)
	_repaint_if_paused(sim)


func _on_color_src_selected(idx: int) -> void:
	var sim = _get_sim()
	if sim == null: return
	if _rainbow_btn.button_pressed:
		_apply_particle_color_mode(sim)
	_sync_color_widgets(sim)
	_repaint_if_paused(sim)


func _on_vfx_size_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	_apply_particle_color_mode(sim)
	_repaint_if_paused(sim)


func _on_vfx_glow_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	_apply_particle_color_mode(sim)
	_repaint_if_paused(sim)


func _on_vfx_depth_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	_apply_particle_color_mode(sim)
	_repaint_if_paused(sim)


func _on_vfx_twoaxis_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	if on and not _rainbow_btn.button_pressed:
		# two-axis rides the rainbow engine — enable it so base mode 4 lands
		_rainbow_btn.button_pressed = true
	_apply_particle_color_mode(sim)
	_sync_color_widgets(sim)
	_repaint_if_paused(sim)


## Recompute sim.particle_color_mode from the UI state. Encoding (matches
## compute/cassi_instancer.glsl header): low nibble = base mode (0 = Cassi
## mass gradient, 1 = velocity, 2 = Qi, 4 = two-axis q/ρ), high nibble =
## feature flags (0x10 size-by-mass, 0x20 additive glow, 0x40 depth cue).
## Defaults (all VFX + rainbow off) → 0, bit-identical to the legacy path.
func _apply_particle_color_mode(sim: Node3D) -> void:
	var base := 0
	if _rainbow_btn.button_pressed:
		if _vfx_twoaxis_btn.button_pressed and _color_src_opt.selected == 1:
			base = 4          # two-axis hue=q / lightness=ρ (Qi source only)
		elif _color_src_opt.selected == 0:
			base = 1          # velocity rainbow
		else:
			base = 2          # Qi rainbow
	var flags := 0
	if _vfx_size_btn.button_pressed:  flags |= 0x10  # size-by-mass
	if _vfx_glow_btn.button_pressed:  flags |= 0x20  # additive glow
	if _vfx_depth_btn.button_pressed: flags |= 0x40  # depth cue
	sim.particle_color_mode = base | flags


func _on_legend_changed() -> void:
	var sim = _get_sim()
	if sim == null: return
	_update_scale_label()
	_auto_align_btn.set_pressed_no_signal(sim.auto_align_colors)
	_repaint_if_paused(sim)


func _on_fit_colors() -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.auto_align_colors = false
	_auto_align_btn.set_pressed_no_signal(false)
	_auto_track_btn.set_pressed_no_signal(false)
	_autotrack_accum = 0.0
	var qi_source: bool = _color_src_opt.selected == 1
	sim.rainbow_count = 1
	sim.color_shares = Vector3(1.0, 0.0, 0.0)
	sim.color_progress = 0
	sim.color_hue_offset = 0.0
	if qi_source:
		# A stable, measured starting band. The two legend handles then make
		# the final fit a direct visual operation rather than a settings hunt.
		sim.qi_cycle = Vector2(0.0002, 0.001)
		sim.qi_pinch = Vector2.ZERO
		sim.qi_approach = Vector2(sim.qi_cycle.y, sim.qi_condensation_threshold)
		sim.qi_approach_tracks_threshold = true
	else:
		sim.velocity_cycle = Vector2.ZERO
		sim.velocity_pinch = Vector2.ZERO
		sim.velocity_approach = Vector2.ZERO
	# The VFX flags ride particle_color_mode's high nibble — recompose so a
	# fit never silently clears size/glow/depth. Base comes from the option.
	_apply_particle_color_mode(sim)
	_sync_color_widgets(sim)
	_repaint_if_paused(sim)


func _on_auto_align_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.auto_align_colors = on
	if on and _auto_track_btn != null and _auto_track_btn.button_pressed:
		# Auto-Track and the GPU auto-aligner fight over qi_cycle — only one
		# may drive the band. Re-enabling Auto releases Auto-Track.
		_auto_track_btn.set_pressed_no_signal(false)


func _on_auto_track_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	if on:
		# Auto-Track takes over: keep the sim's GPU auto-aligner from
		# rewriting qi_cycle mid-glide. (Auto re-enables only if the user
		# toggles it back on; a manual legend drag also releases Auto-Track.)
		sim.auto_align_colors = false
		_auto_align_btn.set_pressed_no_signal(false)
	_autotrack_accum = 0.0
	if on and sim.has_method("_repaint_instancer"):
		_repaint_if_paused(sim)


## A manual legend handle edit (drag / Fit-adjacent set) takes over from both
## auto paths. Auto-Track is released so the manually-set band stands.
func _on_legend_manual() -> void:
	if _auto_track_btn != null and _auto_track_btn.button_pressed:
		_auto_track_btn.set_pressed_no_signal(false)
	_autotrack_accum = 0.0


func _on_falsify_toggled(on: bool) -> void:
	if _falsify_label != null:
		_falsify_label.visible = on
		_falsify_label.text = "" if not on else _falsify_label.text
	_falsify_accum = 0.0


func _on_save_colors() -> void:
	var sim = _get_sim()
	if sim == null: return
	if sim.has_method("save_color_defaults"):
		sim.save_color_defaults()
	_save_colors_btn.text = "Saved"
	var t := get_tree().create_timer(1.5)
	t.timeout.connect(func() -> void:
		if is_instance_valid(_save_colors_btn):
			_save_colors_btn.text = "Save")


func _on_reset_colors() -> void:
	var sim = _get_sim()
	if sim == null: return
	if sim.has_method("load_color_defaults") and sim.load_color_defaults():
		_sync_color_widgets(sim)
		_repaint_if_paused(sim)
	else:
		_on_fit_colors()   # nothing saved yet → the factory band


func _repaint_if_paused(sim: Node3D) -> void:
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


func _on_dual_grid_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.dual_grid = on
	# The measured preset pairs the dual with 4th-order gradients
	# (CASCADE_GRID.md §2) — both ride the bh header, live, no reinit.
	sim.gradient_order = 4 if on else 2


func _on_multirung_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.multi_rung_seed = on
	sim.reinit()  # IC seeding is init-time (particle draw) — reinit applies
func _on_meshless_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.meshless_mode = on
	sim.reinit()  # IC seeding is init-time (particle draw) — reinit applies


func _on_vsync_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.vsync_enabled = on  # live — the property setter applies it to the window


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
			"sf: %.3f  H: %.4f  steps: %d  behind: %.2f s\n" % [sim._scale_factor, sim._hubble, sim._step_count, sim._step_timer] + \
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
