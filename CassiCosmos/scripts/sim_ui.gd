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
var _step_rate_label: Label
var _diag_label: Label
var _conn_label: Label
## The floating status panel + its content VBox (used by _update_layout to
## size it to its children and position it beside / over the rail).
var _info_panel: CPanel
var _info_vbox: VBoxContainer
## Stashed refs for the generic backed-settings controls (EXTRA_PARAMS /
## EXTRA_TOGGLES), keyed by entry id so _sync_extra_params can push the
## sim's live values and the no-signal setters can target them. Built in
## _build_setup_page / _build_system_page before _sync_extra_params runs.
var _extra_spins: Dictionary = {}         # id -> CSpinParam
var _extra_sliders: Dictionary = {}       # id -> CParam
var _extra_toggles: Dictionary = {}       # id -> CheckButton
## Cached param rows (registry + extra) keyed by id — built once on first
## _ensure_param call so the init sync's set_value_no_signal targets the
## same controls the pages display.
var _param_rows: Dictionary = {}
## EXTRA_TOGGLES entries by id (for the generic toggle setter).
var _extra_toggle_ids: Dictionary = {}
## Shared particle geometry registry; all labels and metadata come from the
## generator so the UI cannot drift from its stable contract.
const ParticleInitialConditions = preload("res://scripts/cassi_particle_initial_conditions.gd")
const SHAPE_NAMES: Array[String] = ParticleInitialConditions.SHAPE_NAMES
const ARRANGEMENT_NAMES: Array[String] = ParticleInitialConditions.ARRANGEMENT_NAMES
const MOTION_NAMES: Array[String] = ParticleInitialConditions.MOTION_NAMES
const GRAVITY_NAMES: Array[String] = ["River", "Heuristic", "Plummer ref", "River self", "RealSim"]

var _arrangement_opt: COptionParam
var _motion_opt: COptionParam
var _shape_setting_rows: Dictionary = {} # id -> CSpinParam
var _shape_setting_meta: Dictionary = {} # id -> metadata row
var _shuffle_seed_btn: CButton
var _extra_options: Dictionary = {}       # id -> COptionParam

var _mode_seg: CSegmentedV
var _mode_btns: Array[CToggle] = []
var _gravity_seg: COptionParam
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
var _presentation_color_opt: OptionButton
var _fit_btn: Button
var _presentation_director_opt: OptionButton
var _auto_align_btn: CheckButton
var _scale_label: Label
var _falsify_btn: CheckButton
var _falsify_label: Label
var _save_colors_btn: Button
var _reset_colors_btn: Button
var _legend: Control

## Observatory/Cinematic presentation controls. These are deliberately kept
## in the UI layer: CassiSim owns the rendering contract and emits
## observatory_changed whenever a setting is accepted.
var _observatory_style_opt: COptionParam
var _observation_source_opt: COptionParam
var _observatory_rows: Dictionary = {}
var _observatory_toggles: Dictionary = {}
var _observatory_status: Label
var _observatory_advanced: CGroupPanel
var _capture_helper: Node
var _capture_status: Label
var _capture_scale_opt: COptionParam
var _no_rb_btn: CheckButton
var _bh_toggle_btn: CheckButton
var _phi_box_btn: CheckButton
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

## Native field-current inspection; presentation controls never reinitialize
## the simulation or change its physical observation source.
var _qi_enable_btn: CheckButton
var _qi_channel_seg: CSegmented
var _qi_scalar_opt: COptionParam
var _qi_density_row: CParam
var _qi_gain_row: CParam
var _qi_cutaway_row: CParam
var _qi_field_toggle: CheckButton
var _qi_sources_toggle: CheckButton
var _qi_particles_toggle: CheckButton
var _qi_frame_btn: Button
var _qi_status_label: Label
## Cached: CassiSim exposes the COMPLETE qi_flow_* export family. Checked
## once from its property list (that call allocates, so it never runs per
## frame, and script exports are fixed at load — a one-shot result cannot go
## stale mid-run). A missing or partial family leaves the group inert with
## an explicit reason, instead of reading null exports and writing invalid
## properties or falling back to another drawing mode.
var _qi_props_checked: bool = false
var _qi_props_present: bool = false
## Last applied enable-state of the group's controls (1 enabled / 0 disabled,
## -1 = never applied) so the 4 Hz sync never re-writes them unchanged.
var _qi_controls_ready: int = -1
## Cached: CassiSim reports the flow view actually drawing
## (qi_flow_statistics().available). While true the UI's full-viewport field
## TextureRect stays hidden so the new 3D current geometry is not covered by
## the legacy field canvas — the sim mode and observation source are never
## touched for this.
var _qi_flow_active: bool = false

var _workbench_page: VBoxContainer
var _wb_status_label: Label
var _wb_pause_btn: CButton
var _wb_step_btn: CButton
var _wb_apply_btn: CButton
var _wb_tool_opt: COptionParam
var _wb_selection_opt: COptionParam
var _wb_motion_opt: COptionParam
var _wb_lens_opt: COptionParam
var _wb_center_spins: Array[CSpinParam] = []
var _wb_radius_spin: CSpinParam
var _wb_strength_spin: CSpinParam
var _wb_vector_spins: Array[CSpinParam] = []
var _wb_speed_spin: CSpinParam
var _wb_ratio_spin: CSpinParam
var _wb_save_btn: CButton
var _wb_replay_btn: CButton
var _wb_cursor_arm: CheckButton
var _wb_checkpoint_btn: CButton
var _wb_branch_btn: CButton
var _wb_signature_btn: CButton
var _wb_preview_btn: CButton
var _wb_undo_btn: CButton
var _wb_chat_log: RichTextLabel
var _wb_chat_input: LineEdit
var _wb_provider_url: LineEdit
var _wb_provider_session: LineEdit
var _wb_provider_token: LineEdit
var _wb_provider_status: Label
var _wb_staged_label: Label
var _wb_http: HTTPRequest
var _wb_http_action := ""
var _wb_staged_program: Dictionary = {}
var _wb_staged_digest := ""
var _wb_staged_request_id := ""
var _wb_pending_result_detail := ""
var _server_port_edit: LineEdit

var _fps_accum: float = 0.0
var _fps_count: int = 0
var _fps_display: float = 0.0
var _step_rate_display: float = 0.0
var _step_rate_accum: float = 0.0
var _step_rate_last: int = -1

var _viz_texture_rect: TextureRect

## Left operator rail — a fixed full-height CPanel (viewport-first rewrite,
## 2026-08-14). Replaces the old bottom panel: a compact header + tab bar
## (Setup/Visuals/System), an always-visible Run card, a ScrollContainer for
## the active tab, and a fixed footer holding the live scale readout and the
## interactive GradientLegend (outside the scroll body so its MOUSE_FILTER_STOP
## can never swallow scroll events).
var _control_panel: CPanel
var _presentation_interface_visible := true
var _setup_page: VBoxContainer
var _visuals_page: VBoxContainer
var _system_page: VBoxContainer
## Rail collapse button (hides the rail), + the small reopen button that
## reappears at the left edge when the rail is collapsed. Session-local;
## no persistence.
var _rail_collapse_btn: CButton
var _rail_reopen_btn: CButton
var _rail_collapsed: bool = false
## Scroll container for the active tab's content.
var _scroll: ScrollContainer
## Content VBoxes holding the already-built page roots (fed by the rail
## build helpers). `_rail_root_vbox` fills the scroll body width.
var _tab_stack: VBoxContainer
var _control_root: VBoxContainer
var _tab_bar: CSegmented
var _server_ip_edit: LineEdit
## Falsify lives in System/Diagnostics (it stays status-visible on the info
## panel only while its toggle is on — see _on_falsify_toggled).
## Rail width (px): 320 at and above 960-wide viewports, else the panel
## takes ~all of the width (leaving 16px) so a compact window never overflows.
const RAIL_WIDTH: float = 320.0
## Rail widths below 960-wide viewports (the panel is viewport-16 wide).
const RAIL_WIDTH_NARROW: float = 280.0
## Minimum remaining viewport space (px) required to float the status panel
## to the RIGHT of the rail; below this it sits top-left over the viewport.
const STATUS_MIN_SIDE_SPACE: float = 360.0

const MODE_NAMES: Array[String] = ["Particles", "Field", "Cosmology"]
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
## Schema: {id, kind, caption, token, min, max, step, default, changed,
##          group, [width], [options]}
##   id       — stable string; also selects the direct-ref alias below
##              (xi→_xi_slider/_xi_label, src→_src_slider/_src_label,
##              clusters→_nclusters_spin, separation→_sep_spin, init→_init_opt).
##   kind     — "slider" → CParam; "spin" → CSpinParam; "option" → COptionParam.
##   caption  — the row's caption text; token — its "Cassi" color token.
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
	{"id": "particles",  "kind": "spin",   "caption": "Particles:", "token": "gold",      "min": 100,   "max": 5000000,  "step": 1000,  "default": 20000, "changed": "_on_particles_changed", "group": "Parameters", "width": 150},
	{"id": "clusters",   "kind": "spin",   "caption": "Components:", "token": "cluster",  "min": 1,     "max": 20,       "step": 1,     "default": 1,      "changed": "_on_clusters_changed",  "group": "Parameters", "width": 120},
	{"id": "separation", "kind": "spin",   "caption": "Component spacing:", "token": "sep", "min": 10, "max": 1000000, "step": 10, "default": 60, "changed": "_on_separation_changed", "group": "Parameters", "width": 132},
	{"id": "init",       "kind": "option", "options": SHAPE_NAMES, "caption": "Shape:", "token": "gold", "min": 0, "max": 11, "step": 1, "default": 0, "changed": "_on_init_selected", "group": "Parameters", "width": 132},
]
# ═══════════════════════════════════════════════════════════════════════
# Backed settings registry (2026-08-14) — UI-only exposure of existing
# CassiSim exported properties the sim UI previously never surfaced. One
# entry per adjustable property; built AFTER the sim is available using
# sim.get(name)/sim.set(name, value) with explicit casts, and reinit()
# called only for entries marked reinit. These are ADDITIVE to PARAMS —
# generic no-signal setters, never replacing the specific PARAMS callbacks.
#
# Schema:  {id, prop, caption, token, min, max, step, reinit, tooltip}
#   id     — stable string (route key for the tab builder).
#   prop   — the CassiSim property name (sim.get/sim.set target).
#   reinit — true → call sim.reinit() after setting (init-time / MultiMesh
#            rebuild side effects); false → LIVE, applied next frame.
# Backed toggles ride the generic toggle table (see EXTRA_TOGGLES below),
## `kind: "option"` entries additionally provide an `options` Array[String].
# with an optional tab route (System by default).
const EXTRA_PARAMS: Array[Dictionary] = [
	# ── Setup / Initial state (all reinit — they shape the IC draw) ──────
	{"id": "cluster_radius",           "prop": "cluster_radius",           "caption": "Support size:",     "token": "cluster", "min": 1.0,   "max": 1000000.0, "step": 1.0,    "reinit": true,  "tooltip": "Overall support size in world units. Larger values spread particles farther apart without changing their count. Original profiles use a spherical radius; designed shapes use it as their scale."},
	{"id": "initial_arrangement",      "prop": "initial_arrangement",      "kind": "option", "options": ARRANGEMENT_NAMES, "caption": "Arrangement:", "token": "cluster", "min": 0, "max": 6, "step": 1, "default": 0, "reinit": true, "tooltip": "Component placement: Ring and Sphere retain explicit legacy layouts; Single and Pair ignore component count."},
	{"id": "initial_motion",           "prop": "initial_motion",           "kind": "option", "options": MOTION_NAMES, "caption": "Initial motion:", "token": "gold", "min": 0, "max": 7, "step": 1, "default": 0, "reinit": true, "tooltip": "Profile default preserves original spherical support. Designed shapes start at rest; other modes are kinematic, not equilibrium claims."},
	{"id": "initial_speed",            "prop": "initial_speed",            "caption": "Motion speed:",     "token": "gold",    "min": 0.0,   "max": 100.0,     "step": 0.1,    "default": 5.0,    "reinit": true,  "tooltip": "Speed scale for kinematic initial motion modes; At rest is exactly zero."},
	{"id": "initial_total_mass",       "prop": "initial_total_mass",       "caption": "Total mass:",       "token": "gold",    "min": 0.0,   "max": 1000000000.0, "step": 100.0, "default": 0.0, "reinit": true, "tooltip": "Optional total mass override. 0 keeps the seeded Salpeter sum and >0 rescales the same relative masses."},
	{"id": "merger_speed",             "prop": "merger_speed",             "caption": "Merger speed:",     "token": "cluster", "min": 0.0,   "max": 20.0,      "step": 0.1,    "default": 2.0,    "reinit": true,  "tooltip": "Legacy spherical-profile bulk velocity toward the merger point (2=default). Designed shapes use explicit kinematic motion."},
	{"id": "initial_radius_fraction",  "prop": "initial_radius_fraction",  "caption": "Support fraction:",  "token": "gold",    "min": 0.25, "max": 1.0,       "step": 0.05,   "reinit": true,  "tooltip": "Fraction of the spherical support radius where original-profile particles are spawned (0.9 default)."},
	{"id": "initial_v_circ_factor",    "prop": "initial_v_circ_factor",    "caption": "Circular support:", "token": "gold",    "min": 0.0,   "max": 2.0,       "step": 0.05,   "reinit": true,  "tooltip": "Fraction of circular velocity given to original spherical profiles (0.85 default); designed shapes use explicit motion."},
	{"id": "ic_seed",                  "prop": "ic_seed",                  "caption": "Seed:",             "token": "gold",    "min": 0.0,   "max": 1000000000.0, "step": 1.0,  "reinit": true, "tooltip": "Initial-condition RNG seed; 0 = random. Set non-zero for reproducible runs (reinit redraws)."},
	# ── Setup / Runtime scales ───────────────────────────────────────────
	{"id": "dt",                       "prop": "dt",                       "caption": "dt:",               "token": "sep",     "min": 0.0001, "max": 0.01,   "step": 0.0001, "reinit": false, "tooltip": "Fixed physics timestep (s). LOW = stable, accurate, slow; HIGH = fast but coarse."},
	{"id": "softening",                "prop": "softening",                "caption": "Softening:",        "token": "sep",     "min": 0.001, "max": 5.0,    "step": 0.001,  "reinit": false, "tooltip": "Gray softening length; epsilon² = softening² in the force kernels."},
	{"id": "particle_size",            "prop": "particle_size",            "caption": "Particle size:",    "token": "sep",     "min": 0.05,  "max": 1000.0, "step": 0.05,   "reinit": true,  "tooltip": "Rendered particle diameter scale in world units, not particle spacing. Changing it rebuilds the MultiMesh — reinit applies."},
	{"id": "sim_speed",                "prop": "sim_speed",                "caption": "Sim speed ×:",      "token": "sep",     "min": 0.05,  "max": 10.0,   "step": 0.05,   "reinit": false, "tooltip": "Simulation time-rate multiplier (1.0 = real time). Live; changes the step accumulator rate."},
	{"id": "physics_frame_budget",     "prop": "physics_frame_budget",     "caption": "Frame budget:",     "token": "sep",     "min": 0.0,   "max": 1.0,    "step": 0.05,   "reinit": false, "tooltip": "Fraction of measured frame time budgeted to physics steps per frame (0 = unlimited, default 0.6)."},
	# ── Physics / color numeric ──────────────────────────────────────────
	{"id": "qi_condensation_threshold","prop": "qi_condensation_threshold","caption": "Condensation:",    "token": "mint",    "min": 0.001, "max": 10.0,   "step": 0.001,  "reinit": false, "tooltip": "Qi density above which BH nucleation triggers (the white point when the approach tracks the threshold)."},
	{"id": "bh_acc_rate",              "prop": "bh_acc_rate",              "caption": "BH acc. rate:",     "token": "mint",    "min": 0.0,   "max": 1.0,    "step": 0.001,  "reinit": false, "tooltip": "Black-hole mass growth per step from the field — OFF by default (0.0), because it manufactures mass with nothing drained; experiments only, capped at bh_edd_k·M·dt. Live."},
	{"id": "bh_max_age",               "prop": "bh_max_age",               "caption": "BH max age:",       "token": "mint",    "min": 0.0,   "max": 1000000.0, "step": 100.0, "reinit": false, "tooltip": "Black-hole lifetime (steps); 0 = immortal. Live."},
	{"id": "bh_accretion_radius",      "prop": "bh_accretion_radius",      "caption": "Accretion radius:", "token": "mint",    "min": 0.001, "max": 10.0,   "step": 0.001,  "reinit": false, "tooltip": "World-unit radius at which falling matter is marked for accretion (≈1× default softening). Live."},
	{"id": "box_scale",                "prop": "box_scale",                "caption": "Box scale:",        "token": "gold",    "min": 0.25,  "max": 5.0,    "step": 0.05,   "reinit": true,  "tooltip": "Uniform rescale of all three box extents (aspect preserved). Reinit applies the new box extents."},
	{"id": "realsim_drag",             "prop": "realsim_drag",             "caption": "RealSim γ:",        "token": "sep",     "min": 0.0,   "max": 5.0,    "step": 0.05,   "reinit": false, "tooltip": "RealSim background drag rate a=−γ·(ρ/ρ_ref)·v (γ=0.5 default). Live."},
	{"id": "realsim_viscosity",        "prop": "realsim_viscosity",        "caption": "RealSim ν:",        "token": "sep",     "min": 0.0,   "max": 5.0,    "step": 0.05,   "reinit": false, "tooltip": "RealSim shear-coupling rate to the medium. Live."},
	{"id": "realsim_friction",         "prop": "realsim_friction",         "caption": "RealSim μ:",        "token": "sep",     "min": 0.0,   "max": 1.0,    "step": 0.01,   "reinit": false, "tooltip": "RealSim Coulomb friction floor. Live."},
]
## Horizontal tab-bar labels in order (0=Setup, 1=Visuals, 2=System, 3=Workbench).
const TAB_NAMES: Array[String] = ["Setup", "Visuals", "System", "Workbench"]
## Generic backed TOGGLES — existing CassiSim boolean exports the UI now
## exposes. reinit=true ones call sim.reinit() after setting; live ones
## apply next frame (the sim re-encodes its PC/bh header from the property).
const EXTRA_TOGGLES: Array[Dictionary] = [
	{"id": "field_particles",       "prop": "field_particles",       "reinit": true,  "caption": "Field Particles", "tooltip": "Particles are simulated as moving patterns in the field instead of point objects."},
	{"id": "particle_merge",        "prop": "particle_merge",        "reinit": true,  "caption": "Particle merge", "tooltip": "Dust→object particle merging (init-time buffers — applies on reinit)."},
	{"id": "bh_accretion",          "prop": "bh_accretion",          "reinit": false, "caption": "BH accretion",   "tooltip": "Black-hole mass accretion from the field (init-time shader — live once built)."},
	{"id": "meshless_gravity",      "prop": "meshless_gravity",      "reinit": false, "caption": "Meshless gravity","tooltip": "Tree-walk gravity on the moving Voronoi mesh (live; works when Meshless mode is on)."},
	{"id": "river_calibrate_gn",    "prop": "river_calibrate_gn",    "reinit": true,  "caption": "River G-calib",   "tooltip": "Calibrate G_N to the River gravity chain (init-time — applies on reinit)."},
	{"id": "field_attractor_init",  "prop": "field_attractor_init",  "reinit": true,  "caption": "Field attractor", "tooltip": "Seed the initial field near the φ-attractor (init-time — applies on reinit)."},
	{"id": "freeze_field",          "prop": "freeze_field",          "reinit": false, "caption": "Freeze field",    "tooltip": "Diagnostic: initialize the two-fluid field once and leave it frozen (live tick)."},
	{"id": "presentation_profile",  "prop": "presentation_profile",  "reinit": false, "tab": "visuals", "caption": "Presentation", "tooltip": "Soft luminous particles, range visibility, and a matched field palette. Off restores the compatibility appearance. Live, no reinit."},
	{"id": "presentation_macro_lod", "prop": "presentation_macro_lod_enabled", "reinit": false, "tab": "visuals", "caption": "Macro LOD", "tooltip": "Draw bounded Voronoi-site representatives beyond the individual-particle range. Requires Presentation and a ready meshless topology. Live, no reinit."},
	{"id": "presentation_trails", "prop": "presentation_trails_enabled", "reinit": false, "tab": "visuals", "caption": "Velocity ribbons", "tooltip": "Draw a bounded, instantaneous camera-facing ribbon for sampled moving particles. It uses current velocity only; it never records particle paths. Live, no reinit."},
	{"id": "presentation_volume_history", "prop": "presentation_volume_history_enabled", "reinit": false, "tab": "visuals", "caption": "Volume history", "tooltip": "Use depth-rejected temporal reprojection for the presentation site-volume view. History resets on camera, topology, window, resize, or mode changes. Live, no reinit."},
]


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
	move_child(_viz_texture_rect, 0)

	# Connect to CassiSim texture and presentation signals.
	var sim = _get_sim()
	if sim:
		if sim.has_signal("field_texture_updated"):
			sim.field_texture_updated.connect(_on_field_texture_updated)
		if sim.has_signal("workbench_cursor_changed"):
			sim.workbench_cursor_changed.connect(_on_wb_cursor_changed)
		if sim.has_signal("observatory_changed"):
			sim.observatory_changed.connect(_on_observatory_changed)
	# ── Floating status panel (top-left / right of the rail) ────
	# Compact: FPS/Mode line, connection line, and the (hidden-until-on)
	# falsification meter. The full diagnostics multi-line label lives in
	# System/Diagnostics (built in _build_rail below), NOT here — the rail
	# keeps this panel genuinely compact.
	var info_panel = CPanel.new()
	info_panel.name = "InfoPanel"
	info_panel.set_anchors_preset(PRESET_TOP_LEFT)
	info_panel.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(info_panel)
	_info_panel = info_panel

	var info_vbox = VBoxContainer.new()
	info_vbox.add_theme_constant_override("separation", 4)
	info_panel.add_child(info_vbox)
	_info_vbox = info_vbox

	_info_label = _make_label("FPS: --  |  N: --  |  Step: --", "text", "hud")
	_info_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info_vbox.add_child(_info_label)

	_step_rate_label = _make_label("-- steps/s", "text_hint", "param")
	_step_rate_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info_vbox.add_child(_step_rate_label)

	_conn_label = _make_label("Connection: Local", "text_hint", "param")
	_conn_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	info_vbox.add_child(_conn_label)

	_falsify_label = _make_label("", "gold_bright", "param")
	_falsify_label.name = "FalsifyLabel"
	_falsify_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_falsify_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_falsify_label.visible = false
	info_vbox.add_child(_falsify_label)

	# ── Left operator rail (viewport-first console rewrite) ─────
	# A fixed full-height CPanel (name ControlPanel preserved — probes and
	# docs reference it). Header + tab bar + Run card + a ScrollContainer
	# per-tab body + a fixed footer (scale label + GradientLegend). The
	# rail is built from helper methods below so the tab pages are compact.
	_build_rail()

	# Build the four tab pages (Setup / Visuals / System / Workbench).
	# Qi-flow inspection leads the Visuals tab (before Appearance, Color
	# mapping and every Advanced group) so the new view is discoverable
	# without opening anything; Appearance and capture stay render-only.
	_build_qi_flow_controls()
	_build_observatory_controls()
	_build_setup_page()
	_build_visuals_page()
	_build_system_page()
	_build_workbench_page()
	_setup_capture_helper()
	_sync_observatory_controls()
	_sync_capture_helper()
	_sync_extra_params()
	_sync_presentation_director_control()
	# Boot sync of the Qi-flow group: push CassiSim's live qi_flow_* values
	# with no-signal setters (same discipline as _sync_extra_params above).
	_sync_qi_flow_controls(true)

	# The three tab pages were already built by the _build_setup_page /
	# _build_visuals_page / _build_system_page calls above (they construct
	# ALL of the controls: PARAMS rows, color row, toggles, VFX, the
	# GradientLegend in the footer, and the server fields). Layout is
	# settled after the first frame so the status panel sizes to its content.
	resized.connect(_update_layout)
	if get_viewport() != null:
		# The Control's own `resized` misses window/fullscreen transitions, which
		# would leave the status panel at its small-viewport offset (under the rail).
		get_viewport().size_changed.connect(_update_layout)
	call_deferred("_update_layout")


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
		_update_shape_visibility(int(sim.initial_condition))
		_multirung_btn.button_pressed = sim.multi_rung_seed

		_meshless_btn.button_pressed = sim.meshless_mode
		_sync_color_widgets(sim)
		_no_rb_btn.button_pressed = sim.suppress_readbacks
		_bh_toggle_btn.button_pressed = sim.black_holes_enabled
		_phi_box_btn.button_pressed = (sim.box_aspect != Vector3(1.0, 1.0, 1.0))
		_multirung_btn.button_pressed = sim.multi_rung_seed
		_vsync_btn.button_pressed = sim.vsync_enabled
		# Color sync above may touch legacy enabled-state; presentation sync
		# is last so naturalistic mode always suppresses those widgets.
		_sync_observatory_controls()

	# Connect value_changed AFTER init to avoid spurious reinit() on startup.
	# (Registry sliders + spins were wired at build time — their init sync
	# above uses set_value_no_signal. The standalone toggles + the init
	# option connect here, matching the pre-migration deferral.)
	_meshless_btn.toggled.connect(_on_meshless_toggled)
	_no_rb_btn.toggled.connect(_on_suppress_readbacks_toggled)
	_bh_toggle_btn.toggled.connect(_on_black_holes_toggled)
	_phi_box_btn.toggled.connect(_on_phi_box_toggled)
	_multirung_btn.toggled.connect(_on_multirung_toggled)
	_vsync_btn.toggled.connect(_on_vsync_toggled)

	# All interactive controls (CButton/CToggle/CParam slider/CSegmented +
	# CSpinParam/COptionParam) bake FOCUS_NONE in at the component level, so
	# the WASD camera keys are never stolen — no per-control focus lines here.
	call_deferred("_update_info")


func _process(delta: float) -> void:
	_fps_accum += delta
	_fps_count += 1
	_step_rate_accum += delta
	if _fps_accum < 0.25:
		return
	_fps_display = float(_fps_count) / _fps_accum
	_fps_accum = 0.0
	_fps_count = 0
	var sim_for_rate = _get_sim()
	var steps_now: int = int(sim_for_rate._step_count) if sim_for_rate else -1
	if steps_now >= 0 and _step_rate_last >= 0 and _step_rate_accum > 0.0:
		_step_rate_display = float(steps_now - _step_rate_last) / _step_rate_accum
	_step_rate_last = steps_now
	_step_rate_accum = 0.0
	_update_info()
	# Qi-flow group rides the same 4 Hz tick: no-signal re-sync (catches an
	# inspector edit or a reinit) plus the cached statistics readout. No
	# readback, no GPU query, no per-frame cost.
	_sync_qi_flow_controls()


## Recompute the layout after build, on viewport resize, on rail toggle, on
## tab switch, and after the falsify meter's visibility flips. Anchors the
## left rail to full height with its responsive width, positions the status
## panel, sizes it to its children, and shows/hides the reopen button.
func set_presentation_interface_visible(visible: bool) -> void:
	_presentation_interface_visible = visible
	var toggle := find_child("CaptureInterface", true, false) as CheckButton
	if toggle != null:
		toggle.set_pressed_no_signal(visible)
	_update_layout()


func _update_layout() -> void:
	if not is_inside_tree():
		return
	var vw: float = get_viewport_rect().size.x if get_viewport() != null else RAIL_WIDTH
	var rail_w: float = RAIL_WIDTH if vw >= 960.0 else maxf(RAIL_WIDTH_NARROW, vw - 16.0)
	if _control_panel != null:
		_control_panel.visible = _presentation_interface_visible and not _rail_collapsed
		if not _rail_collapsed:
			_control_panel.set_anchors_and_offsets_preset(Control.PRESET_TOP_LEFT)
			_control_panel.offset_left = 0
			_control_panel.offset_top = 0
			_control_panel.offset_right = rail_w
			_control_panel.offset_bottom = get_viewport_rect().size.y if get_viewport() != null else 0
	# Small reopen button pinned to the left edge when the rail is hidden.
	if _rail_reopen_btn != null:
		_rail_reopen_btn.visible = _presentation_interface_visible and _rail_collapsed
		if _rail_collapsed:
			_rail_reopen_btn.offset_left = 6
			_rail_reopen_btn.offset_top = 6
			_rail_reopen_btn.offset_right = 6.0 + _rail_reopen_btn.custom_minimum_size.x
			_rail_reopen_btn.offset_bottom = 6.0 + _rail_reopen_btn.custom_minimum_size.y
	# Status panel: to the right of the rail when open and there's room,
	# else floating top-left over the viewport.
	if _info_panel != null:
		_info_panel.visible = _presentation_interface_visible
		_info_panel.set_anchors_preset(PRESET_TOP_LEFT)
		var side_room: float = vw - rail_w
		var side: bool = (not _rail_collapsed) and side_room >= STATUS_MIN_SIDE_SPACE
		_info_panel.offset_left = (rail_w + 12.0) if side else 10.0
		_info_panel.offset_top = 10.0
		var want_w: float = minf(440.0, maxf(vw - _info_panel.offset_left - 12.0, 120.0))
		_info_panel.offset_right = _info_panel.offset_left + want_w
		var h: float = 24.0
		if _info_vbox != null:
			var kid: float = _info_vbox.get_combined_minimum_size().y
			if kid > 0.0:
				h = kid + 24.0
		_info_panel.offset_bottom = _info_panel.offset_top + maxf(h, 56.0)


## Rail collapse toggle — hides the full-height left rail and repositions
## the status panel to top-left (session-local only; no persistence).
func _on_rail_collapse_toggled() -> void:
	_rail_collapsed = not _rail_collapsed
	if _wb_cursor_arm != null and _wb_cursor_arm.button_pressed:
		_wb_cursor_arm.set_pressed_no_signal(false)
		_wb_call("workbench_arm_cursor", [false])
	_update_layout()
## View switching is visibility-only — never calls simulation callbacks.
## The active page's ScrollContainer scroll is reset to the top so each tab
## opens at its section start.
func _on_tab_selected(index: int) -> void:
	_show_tab(index)
	if index != 3 and _wb_cursor_arm != null and _wb_cursor_arm.button_pressed:
		_wb_cursor_arm.set_pressed_no_signal(false)
		_wb_call("workbench_arm_cursor", [false])
	call_deferred("_update_layout")


func _show_tab(index: int) -> void:
	if _setup_page:
		_setup_page.visible = (index == 0)
	if _visuals_page:
		_visuals_page.visible = (index == 1)
	if _system_page:
		_system_page.visible = (index == 2)
	if _workbench_page:
		_workbench_page.visible = (index == 3)
	if _scroll != null:
		_scroll.scroll_vertical = 0
# Rail construction — the fixed full-height left operator rail
# ═══════════════════════════════════════════════════════════════════════

## Build the rail's chrome shell: header (CASSI + collapse), horizontal
func _on_rail_reopen_pressed() -> void:
	_rail_collapsed = false
	_update_layout()

func _on_group_toggled(_is_collapsed: bool) -> void:
	call_deferred("_update_layout")
## tab bar, always-visible Run card, the scroll body holding the tab pages,
## and the fixed footer (scale label + GradientLegend).
func _build_rail() -> void:
	var control_panel = CPanel.new()
	control_panel.name = "ControlPanel"
	control_panel.set_anchors_preset(Control.PRESET_TOP_LEFT)
	add_child(control_panel)
	_control_panel = control_panel

	var root_vbox = VBoxContainer.new()
	root_vbox.add_theme_constant_override("separation", 6)
	control_panel.add_child(root_vbox)
	_control_root = root_vbox

	# ── Header row: CASSI title + rail collapse button ──────────
	var header = HBoxContainer.new()
	header.add_theme_constant_override("separation", 6)
	root_vbox.add_child(header)
	var title = _make_label("CASSI", "gold_bright", "hud")
	title.mouse_filter = Control.MOUSE_FILTER_IGNORE
	header.add_child(title)
	var header_spacer = Control.new()
	header_spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	header.add_child(header_spacer)
	_rail_collapse_btn = CButton.make("–")
	_rail_collapse_btn.tooltip_text = "Hide the operator rail"
	_rail_collapse_btn.custom_minimum_size = Vector2(30, 26)
	_rail_collapse_btn.pressed.connect(_on_rail_collapse_toggled)
	header.add_child(_rail_collapse_btn)

	# ── Horizontal tab bar: Setup | Visuals | System ────────────
	_tab_bar = CSegmented.new()
	_tab_bar.button_min_width = 0
	_tab_bar.setup(TAB_NAMES, 0)
	_tab_bar.set_selected_no_signal(0)
	_tab_bar.selection_changed.connect(_on_tab_selected)
	# Equal thirds of the rail width.
	for b in _tab_bar.buttons:
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	root_vbox.add_child(_tab_bar)

	# ── Run card — always visible (transport + mode/gravity) ───
	var run_card := CGroupPanel.new()
	run_card.set_title("Run")
	run_card.toggled.connect(_on_group_toggled)
	root_vbox.add_child(run_card)
	var run_content := run_card.content()
	var transport = HBoxContainer.new()
	transport.add_theme_constant_override("separation", 8)
	run_content.add_child(transport)
	_play_btn = CButton.make("⏸ Pause", _on_play_toggled)
	_play_btn.custom_minimum_size = Vector2(0, 30)
	_play_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	transport.add_child(_play_btn)
	_reinit_btn = CButton.make("↻ Reinit", _on_reinit)
	_reinit_btn.custom_minimum_size = Vector2(0, 30)
	_reinit_btn.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	transport.add_child(_reinit_btn)
	# Mode + Gravity as vertical exclusive lists (all choices visible).
	var mode_lbl = _make_label("Mode", "gold", "param")
	mode_lbl.mouse_filter = Control.MOUSE_FILTER_IGNORE
	mode_lbl.custom_minimum_size = Vector2(0, 4)
	run_content.add_child(mode_lbl)
	_mode_seg = CSegmentedV.new()
	_mode_seg.button_min_height = 24
	_mode_seg.setup(MODE_NAMES, 0)
	_mode_seg.set_selected_no_signal(0)
	_mode_seg.selection_changed.connect(_on_mode_pressed)
	_mode_btns = _mode_seg.buttons
	run_content.add_child(_mode_seg)
	_gravity_seg = COptionParam.new()
	_gravity_seg.box_min_width = 0
	_gravity_seg.setup("Gravity", "gold", GRAVITY_NAMES, 0,
		Callable(self, "_on_gravity_mode_pressed"))
	_gravity_seg.tooltip_text = "Select the gravity law used by the particle solver."
	run_content.add_child(_gravity_seg)

	# ── Scroll body — holds the four tab pages (one visible) ──
	_scroll = ScrollContainer.new()
	_scroll.custom_minimum_size = Vector2(0, 0)
	_scroll.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_scroll.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	_scroll.mouse_filter = Control.MOUSE_FILTER_PASS
	root_vbox.add_child(_scroll)

	_tab_stack = VBoxContainer.new()
	_tab_stack.add_theme_constant_override("separation", 8)
	_tab_stack.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_scroll.add_child(_tab_stack)

	_setup_page = VBoxContainer.new()
	_setup_page.add_theme_constant_override("separation", 8)
	_setup_page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tab_stack.add_child(_setup_page)

	_visuals_page = VBoxContainer.new()
	_visuals_page.add_theme_constant_override("separation", 8)
	_visuals_page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tab_stack.add_child(_visuals_page)

	_system_page = VBoxContainer.new()
	_system_page.add_theme_constant_override("separation", 8)
	_system_page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tab_stack.add_child(_system_page)
	_workbench_page = VBoxContainer.new()
	_workbench_page.add_theme_constant_override("separation", 8)
	_workbench_page.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_tab_stack.add_child(_workbench_page)

	# ── Fixed footer (outside the scroll body): scale + legend ─
	# The GradientLegend is MOUSE_FILTER_STOP, so it lives here — its
	# MOUSE_FILTER_STOP can never swallow the ScrollContainer's wheel events.
	var footer = VBoxContainer.new()
	footer.add_theme_constant_override("separation", 6)
	root_vbox.add_child(footer)
	_scale_label = _make_label("", "text_bright", "param")
	_scale_label.name = "ScaleLabel"
	_scale_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_scale_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_scale_label.tooltip_text = "Color scale — drag LOW and HIGH on the legend to change it"
	footer.add_child(_scale_label)
	_legend = GradientLegend.new()
	_legend.name = "GradientLegend"
	_legend.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_legend.tooltip_text = "Drag LOW and HIGH to fit the active quantity. WHITE marks the physical upper limit; the strip matches the particles exactly."
	_legend.gradient_changed.connect(_on_legend_changed)
	_legend.manual_changed.connect(_on_legend_manual)
	footer.add_child(_legend)

	# ── Small reopen button (left edge, only while collapsed) ──
	_rail_reopen_btn = CButton.make("◀")
	_rail_reopen_btn.name = "RailReopenButton"
	_rail_reopen_btn.tooltip_text = "Reopen the operator rail"
	_rail_reopen_btn.custom_minimum_size = Vector2(30, 44)
	_rail_reopen_btn.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	_rail_reopen_btn.visible = false
	_rail_reopen_btn.pressed.connect(_on_rail_reopen_pressed)
	add_child(_rail_reopen_btn)


## A one-line section semantics hint (LIVE vs REINIT) alongside a heading.
## Returns the CLabel so callers can add it to a heading row.
func _make_semantics_label(mode: String) -> Label:
	var lab := _make_label(mode, "text_hint", "param")
	lab.mouse_filter = Control.MOUSE_FILTER_IGNORE
	lab.tooltip_text = ("Applied LIVE on the next frame — no reinit.") if mode == "LIVE" \
		else ("Init-time parameter — sim.reinit() applies the new value.")
	return lab


## Build a titled collapsible section inside a tab page, returning its
## content VBox. `hint` (optional) is a LIVE/REINIT semantics tag placed
## in the section header so the live-vs-reinit contract is always visible.
func _add_section(page: VBoxContainer, title: String, hint: String = "") -> VBoxContainer:
	var g := CGroupPanel.new()
	g.set_title(title)
	g.toggled.connect(_on_group_toggled)
	page.add_child(g)
	var content := g.content()
	# A small LIVE/REINIT semantics tag at the top of the section content so
	# the apply-contract is visible without hunting for per-row tooltips.
	if hint != "":
		var tip = _make_semantics_label(hint)
		tip.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
		content.add_child(tip)
	return content


## Build the Setup page: Initial state, Runtime scales, Compute budget.
func _build_setup_page() -> void:
	# ── Initial state ───────────────────────────────────────────
	var init_sec := _add_section(_setup_page, "Initial state", "REINIT")
	var init_grid := GridContainer.new()
	init_grid.columns = 2
	init_grid.add_theme_constant_override("h_separation", 10)
	init_grid.add_theme_constant_override("v_separation", 6)
	init_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	init_sec.add_child(init_grid)
	# Shape, arrangement, motion, and mass remain independent controls.
	_init_spin_row(init_grid, "init")
	_init_spin_row(init_grid, "initial_arrangement")
	_init_spin_row(init_grid, "initial_motion")
	_init_spin_row(init_grid, "cluster_radius")
	_init_spin_row(init_grid, "initial_speed")
	_init_spin_row(init_grid, "initial_total_mass")
	_init_spin_row(init_grid, "clusters")
	_init_spin_row(init_grid, "separation")
	_init_spin_row(init_grid, "merger_speed")
	_init_spin_row(init_grid, "initial_radius_fraction")
	_init_spin_row(init_grid, "initial_v_circ_factor")
	_init_spin_row(init_grid, "ic_seed")
	_shuffle_seed_btn = CButton.make("Shuffle seed", _on_shuffle_seed)
	_shuffle_seed_btn.custom_minimum_size = Vector2(0, 26)
	_shuffle_seed_btn.tooltip_text = "Choose a new non-zero seed and reinitialize exactly once."
	init_grid.add_child(_shuffle_seed_btn)

	# Nested shape controls are sourced directly from the geometry registry;
	# no parallel UI parameter list is maintained here.
	var shape_sec := _add_section(_setup_page, "Shape settings", "REINIT")
	var shape_grid := GridContainer.new()
	shape_grid.columns = 2
	shape_grid.add_theme_constant_override("h_separation", 10)
	shape_grid.add_theme_constant_override("v_separation", 6)
	shape_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	shape_sec.add_child(shape_grid)
	_build_shape_setting_rows(shape_grid)

	# ── Runtime scales ──────────────────────────────────────────
	var rt_sec := _add_section(_setup_page, "Runtime scales", "LIVE")
	# xi + Source are sliders (CParam's internal 180 min width) — stack them
	# full-width; the narrow spin rows go in a 2-column grid below.
	rt_sec.add_child(_ensure_param("xi"))
	rt_sec.add_child(_ensure_param("src"))
	var rt_grid := GridContainer.new()
	rt_grid.columns = 2
	rt_grid.add_theme_constant_override("h_separation", 10)
	rt_grid.add_theme_constant_override("v_separation", 6)
	rt_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rt_sec.add_child(rt_grid)
	_init_spin_row(rt_grid, "dt")
	_init_spin_row(rt_grid, "softening")
	_init_spin_row(rt_grid, "particle_size")
	_init_spin_row(rt_grid, "box_scale")

	# ── Compute budget ──────────────────────────────────────────
	var cb_sec := _add_section(_setup_page, "Compute budget", "LIVE")
	var cb_grid := GridContainer.new()
	cb_grid.columns = 2
	cb_grid.add_theme_constant_override("h_separation", 10)
	cb_grid.add_theme_constant_override("v_separation", 6)
	cb_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	cb_sec.add_child(cb_grid)
	_init_spin_row(cb_grid, "grid")
	_init_spin_row(cb_grid, "particles")
	_init_spin_row(cb_grid, "sim_speed")
	_init_spin_row(cb_grid, "physics_frame_budget")


func _init_spin_row(grid: GridContainer, id: String) -> void:
	var ctl: Control = _ensure_param(id)
	grid.add_child(ctl)


## Construct (once) a param control for id. Registry params use the exact
## existing _build_param_row path; backed params use their generic builder.
func _ensure_param(id: String) -> Control:
	if _param_rows.has(id):
		return _param_rows[id]
	var ctl: Control = null
	if _is_registry_id(id):
		ctl = _build_param_row(_param_by_id(id))
	else:
		for e in EXTRA_PARAMS:
			if e.id != id:
				continue
			ctl = _build_extra_option(e) if e.get("kind", "spin") == "option" else _build_extra_spin(e)
			break
	if ctl != null:
		_param_rows[id] = ctl
	return ctl




func _param_by_id(id: String) -> Dictionary:
	for p in PARAMS:
		if p.id == id:
			return p
	return {}


func _is_registry_id(id: String) -> bool:
	for p in PARAMS:
		if p.id == id:
			return true
	return false


## Build one backed-numeric setting as a CSpinParam (caption + SpinBox) from
## its EXTRA_PARAMS entry. The spin is built ONCE and cached in _extra_spins;
## values sync via set_value_no_signal in _sync_extra_params.
func _build_extra_spin(e: Dictionary) -> Control:
	var id: String = e.id
	if _extra_spins.has(id):
		return _extra_spins[id]
	var spin := CSpinParam.new()
	spin.box_min_width = ROW_WIDTH
	var token: String = e.get("token", "text")
	spin.setup(String(e.caption), token, float(e.min), float(e.max), float(e.step),
		float(e.get("default", 0.0)), Callable(self, "_on_extra_param_changed").bind(id))
	spin.spin.tooltip_text = e.get("tooltip", "")
	_extra_spins[id] = spin
	return spin
## Build a backed enum setting using the same EXTRA_PARAMS registry.
func _build_extra_option(e: Dictionary) -> Control:
	var id: String = String(e.id)
	if _extra_options.has(id):
		return _extra_options[id]
	var opt := COptionParam.new()
	opt.box_min_width = ROW_WIDTH
	var options: Array[String] = []
	for name_variant in e.get("options", []):
		options.append(String(name_variant))
	var changed := Callable(self, "_on_extra_option_changed").bind(id)
	if id == "initial_arrangement":
		changed = Callable(self, "_on_arrangement_selected")
	elif id == "initial_motion":
		changed = Callable(self, "_on_motion_selected")
	opt.setup(String(e.caption), String(e.get("token", "text")),
		options, int(e.get("default", 0)), changed)
	if id == "initial_arrangement":
		_arrangement_opt = opt
	elif id == "initial_motion":
		_motion_opt = opt
	opt.tooltip_text = String(e.get("tooltip", ""))
	# Keep the compact rail width while allowing the popup to show full names.
	opt.option.custom_minimum_size = Vector2(0, 22)
	opt.option.clip_text = true
	_extra_options[id] = opt
	return opt


func _on_extra_option_changed(value: int, id: String) -> void:
	var sim = _get_sim()
	if sim == null:
		return
	for e in EXTRA_PARAMS:
		if e.id != id:
			continue
		sim.set(String(e.prop), value)
		if id == "initial_arrangement":
			_update_shape_dependent_controls(value)
		if e.get("reinit", false):
			sim.reinit()
		break

## Build the nested shape-settings rows from the generator's canonical
## metadata. The rows are cached and only their visibility changes on shape
## selection, so changing shape never resets arrangement, motion, count, or seed.
func _build_shape_setting_rows(grid: GridContainer) -> void:
	for meta_variant in ParticleInitialConditions.PARAMS:
		var meta: Dictionary = meta_variant
		var key := String(meta.get("key", ""))
		if key == "":
			continue
		var id := String(meta.get("id", "ic_" + key))
		var row := CSpinParam.new()
		row.box_min_width = ROW_WIDTH
		var step := float(meta.get("step", 0.1))
		var default_value := float(meta.get("default", 0.0))
		row.setup(String(meta.get("caption", key)), String(meta.get("token", "gold")),
			float(meta.get("min", 0.0)), float(meta.get("max", 1.0)), step,
			default_value, Callable(self, "_on_shape_setting_changed").bind(id))
		row.spin.tooltip_text = String(meta.get("tooltip", ""))
		_shape_setting_rows[id] = row
		_shape_setting_meta[id] = meta
		grid.add_child(row)


func _shape_setting_is_visible(meta: Dictionary, shape: int) -> bool:
	var shapes: Array = meta.get("shapes", [])
	return shapes.is_empty() or shapes.has(shape)


func _shape_setting_cast(value: float, meta: Dictionary) -> Variant:
	var step := float(meta.get("step", 0.1))
	return int(round(value)) if is_equal_approx(step, round(step)) else value


func _on_shape_setting_changed(value: float, id: String) -> void:
	var sim = _get_sim()
	if sim == null or not _shape_setting_meta.has(id):
		return
	var current: Variant = sim.get("initial_shape_settings")
	var settings: Dictionary = current.duplicate() if current is Dictionary else {}
	settings[String(_shape_setting_meta[id].get("key", id))] = _shape_setting_cast(value, _shape_setting_meta[id])
	sim.set("initial_shape_settings", settings)
	sim.reinit()


func _sync_shape_setting_rows(sim: Node3D) -> void:
	var current: Variant = sim.get("initial_shape_settings")
	var settings: Dictionary = current if current is Dictionary else {}
	for id in _shape_setting_rows.keys():
		var row: CSpinParam = _shape_setting_rows[id]
		var meta: Dictionary = _shape_setting_meta[id]
		var value := float(settings.get(String(meta.get("key", id)), meta.get("default", 0.0)))
		row.set_value_no_signal(value)
		row.visible = _shape_setting_is_visible(meta, int(sim.initial_condition))
	_update_shape_dependent_controls(int(sim.get("initial_arrangement")))


func _update_shape_dependent_controls(arrangement: int) -> void:
	if _nclusters_spin == null:
		return
	var fixed_count := arrangement == 2 or arrangement == 3
	_nclusters_spin.spin.editable = not fixed_count
	_nclusters_spin.tooltip_text = "Component count is ignored by Single/Pair arrangements." if fixed_count \
		else "Number of components in the selected arrangement."

## Generic no-signal setter for the backed numerics: writes the value into
## the sim and reinit()s only for reinit-marked entries. Never replaces the
## specific PARAMS callbacks (xi/src/grid/... keep their own handlers).
func _on_extra_param_changed(value: float, id: String) -> void:
	var sim = _get_sim()
	if sim == null:
		return
	for e in EXTRA_PARAMS:
		if e.id != id:
			continue
		if e.get("reinit", false):
			sim.set(String(e.prop), _cast_extra(value, e))
			sim.reinit()
		else:
			sim.set(String(e.prop), _cast_extra(value, e))
		break


# (aliases preservation is comment-documented above the registry; the
#  EXTRA_PARAMS entries carry their own captions/tooltips.)


## Cast a numeric SpinBox value to the property's native type.
func _cast_extra(value: float, e: Dictionary) -> Variant:
	var p: String = String(e.prop)
	# These exports are integer counters/IDs. Other step-1 controls such as
	# cluster_radius remain floats by contract, so do not infer type from step.
	if p == "ic_seed" or p == "bh_max_age":
		return int(round(value))
	return float(value)


## The generic backed-toggle builder + no-signal setter.
func _build_extra_toggle(e: Dictionary) -> CheckButton:
	var id: String = e.id
	if _extra_toggles.has(id):
		return _extra_toggles[id]
	var t := CheckButton.new()
	t.name = "%sToggle" % id
	t.text = String(e.caption)
	t.tooltip_text = e.get("tooltip", "")
	t.custom_minimum_size = Vector2(0, 22)
	t.focus_mode = Control.FOCUS_NONE
	t.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	# connect AFTER the init sync — the init sync uses set_pressed_no_signal.
	_extra_toggles[id] = t
	_extra_toggle_ids[id] = e
	return t


func _on_extra_toggle_changed(on: bool, id: String) -> void:
	var sim = _get_sim()
	if sim == null:
		return
	var e: Dictionary = _extra_toggle_ids.get(id, {})
	if e.is_empty():
		return
	if id == "field_particles" and sim.has_method("set_field_particles_enabled"):
		sim.call("set_field_particles_enabled", on)
		return
	if e.get("reinit", false):
		sim.set(String(e.prop), on)
		sim.reinit()
	else:
		sim.set(String(e.prop), on)


func _presentation_director() -> Node:
	var scene := get_tree().current_scene
	return scene.get_node_or_null("PresentationDirector") if scene != null else null


func _sync_presentation_director_control() -> void:
	if _presentation_director_opt == null:
		return
	var director := _presentation_director()
	if director == null:
		_presentation_director_opt.disabled = true
		_presentation_director_opt.tooltip_text = "No presentation director is present in this scene."
		return
	_presentation_director_opt.disabled = false
	var director_mode := int(director.get("mode"))
	var director_preset := int(director.get("preset"))
	var selected := 0 if director_mode == 0 else clampi(director_preset + 1, 1, 4)
	if director_mode == 2:
		selected = 3
	_presentation_director_opt.select(selected)
	var changed := Callable(self, "_on_presentation_director_mode_changed")
	if director.has_signal("mode_changed") and not director.is_connected("mode_changed", changed):
		director.connect("mode_changed", changed)


func _on_presentation_director_selected(index: int) -> void:
	var director := _presentation_director()
	if director == null:
		return
	if index <= 0:
		if director.has_method("request_manual_takeover"):
			director.call("request_manual_takeover")
		return
	if director.has_method("set_directed_preset"):
		director.call("set_directed_preset", index - 1)


func _on_presentation_director_mode_changed(next_mode: int, next_preset: int) -> void:
	if _presentation_director_opt == null:
		return
	var selected := 0 if next_mode == 0 else clampi(next_preset + 1, 1, 4)
	if next_mode == 2:
		selected = 3
	_presentation_director_opt.select(selected)


const ROW_WIDTH: int = 132


# ── Qi flow inspection ─────────────────────────────────────────────────

## Channel choices — the index order IS the qi_flow_channel contract.
const QI_FLOW_CHANNELS: Array[String] = ["Both", "Yang", "Yin", "Net"]
const QI_FLOW_CHANNEL_TIPS: Array[String] = [
	"Both currents together: gold AND teal filaments are drawn at once — that is how counterflow stays visible.",
	"Yang current only — the warm-gold filaments.",
	"Yin current only — the teal filaments.",
	"Summed Yang+Yin vector, drawn in a pale cool white. Equal and opposite currents cancel here, so Net can hide counterflow.",
]
## Scalar choices — the index order IS the qi_flow_scalar contract.
const QI_FLOW_SCALARS: Array[String] = ["Coherence", "Signed imbalance", "Field amplitude"]
## Match the renderer's channel palette.
const QI_FLOW_YANG_COLOR: Color = Color(1.0, 0.79, 0.36)   # warm gold
const QI_FLOW_YIN_COLOR: Color = Color(0.30, 0.85, 0.80)   # teal
const QI_FLOW_NET_COLOR: Color = Color(0.78, 0.82, 1.0)    # pale cool white


## Build the Visuals-tab "Qi flow inspection" group — built FIRST in the
## page (before Appearance and Color mapping) so the view is reachable
## without expanding any Advanced section. Reuses the house widgets only:
## a CGroupPanel section, CParam sliders, COptionParam and CSegmented.
func _build_qi_flow_controls() -> void:
	var sec := _add_section(_visuals_page, "Qi flow inspection", "LIVE")
	var intro := _make_label("Follow the Yang and Yin wave-energy currents through the native field.", "text_hint", "param")
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	intro.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sec.add_child(intro)

	# Compact filament color key — the three colors the renderer draws.
	var key_row := HBoxContainer.new()
	key_row.add_theme_constant_override("separation", 10)
	sec.add_child(key_row)
	var key_caption := _make_label("Currents:", "gold", "param")
	key_caption.mouse_filter = Control.MOUSE_FILTER_IGNORE
	key_row.add_child(key_caption)
	key_row.add_child(_qi_flow_key_entry("Yang", QI_FLOW_YANG_COLOR,
		"Yang current filaments (warm gold)."))
	key_row.add_child(_qi_flow_key_entry("Yin", QI_FLOW_YIN_COLOR,
		"Yin current filaments (teal)."))
	key_row.add_child(_qi_flow_key_entry("Net", QI_FLOW_NET_COLOR,
		"Summed current, drawn only in the Net channel (pale cool white)."))

	_qi_enable_btn = _build_vfx_toggle("QiFlowEnableBtn", "Enable Qi flow",
		"Draw the Qi-flow inspection layer over the authoritative meshless sites. Live and rendering-only: no reinit, and no change to the physics or the observation source.", _on_qi_flow_enabled_toggled)
	_qi_enable_btn.custom_minimum_size = Vector2(0, 24)
	sec.add_child(_qi_enable_btn)
	_qi_frame_btn = Button.new()
	_qi_frame_btn.name = "QiFlowFrameBtn"
	_qi_frame_btn.text = "Frame field"
	_qi_frame_btn.tooltip_text = "Fit the actual field window to the camera.\nMoves only the viewpoint; field size and physics are unchanged."
	_qi_frame_btn.focus_mode = Control.FOCUS_NONE
	_qi_frame_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_qi_frame_btn.disabled = true
	_qi_frame_btn.pressed.connect(_on_qi_flow_frame_pressed)
	sec.add_child(_qi_frame_btn)

	var channel_label := _make_label("Channel", "gold", "param")
	channel_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sec.add_child(channel_label)
	_qi_channel_seg = CSegmented.new()
	_qi_channel_seg.name = "QiFlowChannel"
	_qi_channel_seg.button_min_width = 0
	_qi_channel_seg.setup(QI_FLOW_CHANNELS, 0, Callable(self, "_on_qi_flow_channel_selected"))
	for i in range(_qi_channel_seg.buttons.size()):
		var b := _qi_channel_seg.buttons[i]
		b.custom_minimum_size = Vector2(0, 24)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		b.tooltip_text = QI_FLOW_CHANNEL_TIPS[i]
	sec.add_child(_qi_channel_seg)

	_qi_scalar_opt = COptionParam.new()
	_qi_scalar_opt.name = "QiFlowScalar"
	_qi_scalar_opt.box_min_width = ROW_WIDTH
	_qi_scalar_opt.setup("Scalar:", "gold", QI_FLOW_SCALARS, 0, Callable(self, "_on_qi_flow_scalar_selected"))
	_qi_scalar_opt.tooltip_text = "Coherence q: deep blue → cyan → white, fixed 0–1 scale.\nSigned imbalance (EY−φEI)/|EY+EI|: teal (−) → dark → gold (+), clipped ±1.\nField amplitude |EY+EI|: violet → gold, scaled to the current maximum."
	sec.add_child(_qi_scalar_opt)

	# Layer toggles in one column so their labels never overflow a narrow rail.
	var layers := GridContainer.new()
	layers.columns = 1
	layers.add_theme_constant_override("v_separation", 5)
	sec.add_child(layers)
	_qi_field_toggle = _build_vfx_toggle("QiFlowFieldBtn", "Field layer",
		"Draw the site-field layer itself — the selected scalar ramp over every authoritative site.", _on_qi_flow_field_toggled)
	layers.add_child(_qi_field_toggle)
	_qi_sources_toggle = _build_vfx_toggle("QiFlowSourcesBtn", "Source markers",
		"Mark occupied black-hole records at their actual world positions (up to 15).\nMarker size is a display cue for mass, not a horizon radius.", _on_qi_flow_sources_toggled)
	layers.add_child(_qi_sources_toggle)
	_qi_particles_toggle = _build_vfx_toggle("QiFlowParticlesBtn", "Particle backdrop",
		"Keep the particle cloud drawn behind the current layer.", _on_qi_flow_particles_toggled)
	layers.add_child(_qi_particles_toggle)

	_qi_density_row = _add_qi_flow_param(sec, "QiFlowDensity", "Filament density:",
		"Draw 102–1024 seeded graph paths per channel, up to 16 bonds each.\nDisplay density only; every site's current is still evaluated.", 0.1, 1.0, 0.05, 0.5, Callable(self, "_on_qi_flow_density_changed"))
	_qi_gain_row = _add_qi_flow_param(sec, "QiFlowGain", "Light / gain:",
		"Brightness of the current layer. Display-only exposure; the underlying quantities are unchanged.", 0.1, 4.0, 0.05, 1.0, Callable(self, "_on_qi_flow_gain_changed"))
	_qi_cutaway_row = _add_qi_flow_param(sec, "QiFlowCutaway", "Core cutaway:",
		"0 = whole field. Raise towards 1 to remove the camera-facing half and expose the interior. Display-only: the simulation is unchanged.", 0.0, 1.0, 0.05, 0.0, Callable(self, "_on_qi_flow_cutaway_changed"))

	var note := _make_label("Pulses indicate direction, not speed. Pause freezes them. Low coherence remains visible; missing data does not.", "text_hint", "detail")
	note.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	note.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sec.add_child(note)

	_qi_status_label = _make_label("", "text_hint", "param")
	_qi_status_label.name = "QiFlowStatus"
	_qi_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_qi_status_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	sec.add_child(_qi_status_label)


## One Qi-flow slider row (CParam) with the house caption/value formatting.
func _add_qi_flow_param(parent: Control, id: String, caption: String, tooltip: String,
		min_v: float, max_v: float, step_v: float, default_v: float,
		changed: Callable) -> CParam:
	var row := CParam.new()
	row.name = id
	row.setup(caption, "gold_soft", min_v, max_v, step_v, default_v, changed)
	row.tooltip_text = tooltip
	row.slider.tooltip_text = tooltip
	parent.add_child(row)
	return row


## One compact color-key entry: swatch + name (the renderer's exact color).
func _qi_flow_key_entry(label: String, color: Color, tip: String) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 4)
	row.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	row.tooltip_text = tip
	var swatch := ColorRect.new()
	swatch.color = color
	swatch.custom_minimum_size = Vector2(12, 12)
	swatch.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	swatch.mouse_filter = Control.MOUSE_FILTER_IGNORE
	swatch.tooltip_text = tip
	row.add_child(swatch)
	var entry_label := _make_label(label, "text_hint", "detail")
	entry_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(entry_label)
	return row


# ── Qi-flow callbacks (each writes exactly one CassiSim export) ─────────

func _on_qi_flow_enabled_toggled(on: bool) -> void:
	_qi_flow_set("qi_flow_enabled", on)
	_update_qi_flow_status()


func _on_qi_flow_channel_selected(index: int) -> void:
	_qi_flow_set("qi_flow_channel", clampi(index, 0, QI_FLOW_CHANNELS.size() - 1))


func _on_qi_flow_scalar_selected(index: int) -> void:
	_qi_flow_set("qi_flow_scalar", clampi(index, 0, QI_FLOW_SCALARS.size() - 1))


func _on_qi_flow_density_changed(value: float) -> void:
	_qi_flow_set("qi_flow_density", clampf(value, 0.1, 1.0))


func _on_qi_flow_gain_changed(value: float) -> void:
	_qi_flow_set("qi_flow_gain", clampf(value, 0.1, 4.0))


func _on_qi_flow_cutaway_changed(value: float) -> void:
	_qi_flow_set("qi_flow_cutaway", clampf(value, 0.0, 1.0))


func _on_qi_flow_field_toggled(on: bool) -> void:
	_qi_flow_set("qi_flow_show_field", on)


func _on_qi_flow_sources_toggled(on: bool) -> void:
	_qi_flow_set("qi_flow_show_sources", on)


func _on_qi_flow_particles_toggled(on: bool) -> void:
	_qi_flow_set("qi_flow_show_particles", on)


func _on_qi_flow_frame_pressed() -> void:
	var sim := _get_sim()
	if sim != null:
		sim.call("frame_qi_flow_view")


# ── Qi-flow sync / status ──────────────────────────────────────────────

## Write one rendering-only qi_flow_* export. Never reinit()s, never touches
## a physics or observation source; a missing export family is reported in
## the status line instead of being worked around.
func _qi_flow_set(prop: String, value: Variant) -> void:
	var sim := _get_sim()
	if sim == null or not _qi_prop_ready(sim):
		return
	sim.set(prop, value)


## Qi-flow exports this group binds to — the whole set must exist before
## any control is live: a partial integration would otherwise read null
## exports and write invalid properties.
const QI_FLOW_PROPS: Array[String] = [
	"qi_flow_enabled", "qi_flow_channel", "qi_flow_scalar", "qi_flow_density",
	"qi_flow_gain", "qi_flow_cutaway", "qi_flow_show_field",
	"qi_flow_show_sources", "qi_flow_show_particles",
]


## One-shot check that CassiSim owns the WHOLE qi_flow_* export family
## (cached — get_property_list() allocates, so this must never run per
## frame). A build without the family leaves the group disabled and says so.
func _qi_prop_ready(sim: Node3D) -> bool:
	if _qi_props_checked:
		return _qi_props_present
	_qi_props_checked = true
	var names := {}
	for entry in sim.get_property_list():
		names[String(entry.name)] = true
	_qi_props_present = true
	for prop in QI_FLOW_PROPS:
		if not names.has(prop):
			_qi_props_present = false
			break
	return _qi_props_present


## Push CassiSim's live qi_flow_* values into the group with no-signal
## setters — the boot / reinit / inspector cadence the backed registries
## use. `force` writes every control (boot); otherwise only a control whose
## value actually drifted is rewritten, so this can ride the HUD tick
## without fighting a live slider drag. Rendering-only: no reinit, no
## source switch, no GPU work.
func _sync_qi_flow_controls(force: bool = false) -> void:
	if _qi_status_label == null:
		return
	var sim := _get_sim()
	if sim == null:
		_qi_flow_refresh_enabled(false)
		_set_qi_flow_active(false)
		_set_qi_flow_status("Unavailable: CassiSim is not in the scene tree.", "disabled")
		return
	var family_ready := _qi_prop_ready(sim)
	_qi_flow_refresh_enabled(family_ready)
	if not family_ready:
		if force:
			_qi_enable_btn.set_pressed_no_signal(false)
			_qi_channel_seg.set_selected_no_signal(0)
			_qi_scalar_opt.set_value_no_signal(0)
			_qi_density_row.set_value_no_signal(0.5)
			_qi_gain_row.set_value_no_signal(1.0)
			_qi_cutaway_row.set_value_no_signal(0.0)
			_qi_field_toggle.set_pressed_no_signal(true)
			_qi_sources_toggle.set_pressed_no_signal(true)
			_qi_particles_toggle.set_pressed_no_signal(false)
		_update_qi_flow_status()
		return
	var enabled := bool(sim.get("qi_flow_enabled"))
	if force or _qi_enable_btn.button_pressed != enabled:
		_qi_enable_btn.set_pressed_no_signal(enabled)
	var channel := clampi(int(sim.get("qi_flow_channel")), 0, QI_FLOW_CHANNELS.size() - 1)
	if force or _qi_channel_seg.selected_index != channel:
		_qi_channel_seg.set_selected_no_signal(channel)
	var scalar := clampi(int(sim.get("qi_flow_scalar")), 0, QI_FLOW_SCALARS.size() - 1)
	if force or _qi_scalar_opt.get_value() != scalar:
		_qi_scalar_opt.set_value_no_signal(scalar)
	var show_field := bool(sim.get("qi_flow_show_field"))
	if force or _qi_field_toggle.button_pressed != show_field:
		_qi_field_toggle.set_pressed_no_signal(show_field)
	var show_sources := bool(sim.get("qi_flow_show_sources"))
	if force or _qi_sources_toggle.button_pressed != show_sources:
		_qi_sources_toggle.set_pressed_no_signal(show_sources)
	var show_particles := bool(sim.get("qi_flow_show_particles"))
	if force or _qi_particles_toggle.button_pressed != show_particles:
		_qi_particles_toggle.set_pressed_no_signal(show_particles)
	_qi_sync_row(_qi_density_row, float(sim.get("qi_flow_density")), force)
	_qi_sync_row(_qi_gain_row, float(sim.get("qi_flow_gain")), force)
	_qi_sync_row(_qi_cutaway_row, float(sim.get("qi_flow_cutaway")), force)
	_update_qi_flow_status()


## Rewrite a slider only when CassiSim's value really differs from the one
## shown (an inspector edit or a reinit) — not when the control's own step
## quantization is the only difference.
func _qi_sync_row(row: CParam, sim_value: float, force: bool) -> void:
	if force or absf(row.get_value() - sim_value) > row.slider.step * 0.5:
		row.set_value_no_signal(sim_value)


## Enable or disable the whole group as one unit. `exports_present` is false
## only when CassiSim does not expose the qi_flow_* family: the controls are
## then inert, and the status line says why — nothing falls back to another
## mode and no invalid property is ever written. Idempotent (-1 = never
## applied): the 4 Hz sync calls this every tick, so it no-ops unless the
## export family's availability actually flipped.
func _qi_flow_refresh_enabled(exports_present: bool) -> void:
	var state := 1 if exports_present else 0
	if _qi_controls_ready == state:
		return
	_qi_controls_ready = state
	_qi_enable_btn.disabled = not exports_present
	_qi_scalar_opt.option.disabled = not exports_present
	for b in _qi_channel_seg.buttons:
		b.disabled = not exports_present
	_qi_field_toggle.disabled = not exports_present
	_qi_sources_toggle.disabled = not exports_present
	_qi_particles_toggle.disabled = not exports_present
	_qi_density_row.slider.editable = exports_present
	_qi_gain_row.slider.editable = exports_present
	_qi_cutaway_row.slider.editable = exports_present


## Refresh the group's status line from CassiSim's cached
## qi_flow_statistics() readout: whether the view is drawing, the site count
## and the accepted field time when available, else Main's own reason. Reads
## a Dictionary only — no buffer readback, no GPU query, no per-frame work.
func _update_qi_flow_status() -> void:
	if _qi_status_label == null:
		return
	# Every path below this line leaves the flow view either provably drawing
	# (the available branch) or provably not — the texture gate is cleared
	# first so no early return can strand the field canvas hidden.
	_set_qi_flow_active(false)
	var sim := _get_sim()
	if sim == null:
		_set_qi_flow_status("Unavailable: CassiSim is not in the scene tree.", "disabled")
		return
	if not _qi_prop_ready(sim):
		_set_qi_flow_status("Unavailable: CassiSim does not expose the qi_flow_* inspection exports in this build.", "disabled")
		return
	if not sim.has_method("qi_flow_statistics"):
		_set_qi_flow_status("Unavailable: CassiSim has no qi_flow_statistics() readout.", "disabled")
		return
	var stats: Variant = sim.call("qi_flow_statistics")
	if not (stats is Dictionary):
		_set_qi_flow_status("Unavailable: qi_flow_statistics() returned no readout.", "disabled")
		return
	var s: Dictionary = stats
	if bool(s.get("available", false)):
		_set_qi_flow_active(true)
		_qi_status_label.tooltip_text = String(s.get("quantity", "Native field wave-energy current"))
		_set_qi_flow_status("Native window · %d sites · t = %.3f" % [
			int(s.get("sites", 0)), float(s.get("time", 0.0))], "mint")
		return
	_set_qi_flow_active(false)
	var reason := String(s.get("reason", "")).strip_edges()
	_set_qi_flow_status("Unavailable — %s" % (reason if not reason.is_empty() else "not ready yet"), "text_hint")


## Write the status line only when it changes (the HUD tick must not churn
## theme overrides every quarter second).
func _set_qi_flow_status(text: String, token: String) -> void:
	if _qi_status_label.text == text:
		return
	_qi_status_label.text = text
	_qi_status_label.add_theme_color_override("font_color", _tok_color(token))


## Track whether CassiSim reports the flow view actually drawing. While it
## is, the UI hides its own full-viewport field TextureRect so the 3D current
## geometry is not covered by the legacy field canvas; ordinary Field-mode
## visibility returns as soon as the flow view stops. The sim mode and the
## observation source are never touched for this, and nothing reinit()s.
func _set_qi_flow_active(active: bool) -> void:
	_qi_frame_btn.disabled = not active
	if _qi_flow_active == active:
		return
	_qi_flow_active = active
	_update_field_texture_visibility()


## Build the Visuals page: Color mapping, particle presentation controls,
## and the four compatibility VFX flags. The large GradientLegend lives in
## the rail footer (not per-tab).
func _build_visuals_page() -> void:
	# ── Color mapping ───────────────────────────────────────────
	var color_sec := _add_section(_visuals_page, "Color mapping", "LIVE")
	var cm_row := HBoxContainer.new()
	cm_row.add_theme_constant_override("separation", 6)
	color_sec.add_child(cm_row)
	_rainbow_btn = CheckButton.new()
	_rainbow_btn.name = "RainbowBtn"
	_rainbow_btn.text = "Rainbow"
	_rainbow_btn.tooltip_text = "Use the rainbow scale instead of the Cassi mass-temperature colors"
	_rainbow_btn.custom_minimum_size = Vector2(88, 22)
	_rainbow_btn.focus_mode = Control.FOCUS_NONE
	_rainbow_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_rainbow_btn.toggled.connect(_on_rainbow_toggled)
	cm_row.add_child(_rainbow_btn)
	_color_src_opt = OptionButton.new()
	_color_src_opt.name = "ColorSrcOpt"
	_color_src_opt.add_item("Velocity (dir)")    # 0 → mode 6: hue = atan2(vy,vx) compass, lightness = speed
	_color_src_opt.add_item("Qi")                # 1 → mode 2: hue = q_coh amplitude
	_color_src_opt.add_item("Field phase")       # 2 → mode 5: hue = atan2(EI,EY) orientation, lightness = q_coh
	_color_src_opt.add_item("Velocity (speed)")  # 3 → mode 1: legacy speed rainbow
	_color_src_opt.selected = 1
	_color_src_opt.tooltip_text = "Choose the quantity mapped to color; drag LOW and HIGH on the legend to fit its scale"
	_color_src_opt.custom_minimum_size = Vector2(76, 22)
	_color_src_opt.focus_mode = Control.FOCUS_NONE
	_color_src_opt.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_color_src_opt.item_selected.connect(_on_color_src_selected)
	cm_row.add_child(_color_src_opt)
	_fit_btn = Button.new()
	_fit_btn.name = "FitColorsBtn"
	_fit_btn.text = "Fit scale"
	_fit_btn.tooltip_text = "Fit LOW/HIGH for band modes 1–4; phase/direction modes 5/6 ignore band fitting"
	_fit_btn.focus_mode = Control.FOCUS_NONE
	_fit_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_fit_btn.pressed.connect(_on_fit_colors)
	cm_row.add_child(_fit_btn)
	var palette_row := HBoxContainer.new()
	palette_row.add_theme_constant_override("separation", 6)
	color_sec.add_child(palette_row)
	var palette_label := _make_label("Presentation palette:", "gold", "param")
	palette_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	palette_row.add_child(palette_label)
	_presentation_color_opt = OptionButton.new()
	_presentation_color_opt.name = "PresentationColorSchemeOpt"
	_presentation_color_opt.add_item("Cassi Night")
	_presentation_color_opt.add_item("Spectrum")
	_presentation_color_opt.selected = 0
	_presentation_color_opt.tooltip_text = "Choose the palette that colors all presentation layers; Color source remains the data input mapped by the Color controls. Live, no reinit."
	_presentation_color_opt.custom_minimum_size = Vector2(112, 22)
	_presentation_color_opt.focus_mode = Control.FOCUS_NONE
	_presentation_color_opt.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_presentation_color_opt.item_selected.connect(_on_presentation_color_scheme_selected)
	palette_row.add_child(_presentation_color_opt)

	var cm_auto := HBoxContainer.new()
	cm_auto.add_theme_constant_override("separation", 6)
	color_sec.add_child(cm_auto)
	# Auto (GPU q_coh aligner) — KEPT (owner decision 2026-08-16). The broken
	# CPU Auto-Track tracker was removed; the aligner reads the bounded q_coh
	# histogram and re-fits the Qi band to the live distribution. Manual
	# legend drag / Fit releases it so the band stands.
	_auto_align_btn = CheckButton.new()
	_auto_align_btn.name = "AutoAlignBtn"
	_auto_align_btn.text = "Auto"
	_auto_align_btn.tooltip_text = "Auto-fit bounded Qi bands for modes 2–4; phase/direction modes 5/6 ignore band fitting"
	_auto_align_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_auto_align_btn.toggled.connect(_on_auto_align_toggled)
	cm_auto.add_child(_auto_align_btn)
	_save_colors_btn = Button.new()
	_save_colors_btn.name = "SaveColorsBtn"
	_save_colors_btn.text = "Save"
	_save_colors_btn.tooltip_text = "Save the current colors as the default for future runs"
	_save_colors_btn.custom_minimum_size = Vector2(54, 22)
	_save_colors_btn.focus_mode = Control.FOCUS_NONE
	_save_colors_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_save_colors_btn.pressed.connect(_on_save_colors)
	cm_auto.add_child(_save_colors_btn)
	_reset_colors_btn = Button.new()
	_reset_colors_btn.name = "ResetColorsBtn"
	_reset_colors_btn.text = "Reset"
	_reset_colors_btn.tooltip_text = "Restore the saved colors (Fit scale if none are saved)"
	_reset_colors_btn.custom_minimum_size = Vector2(58, 22)
	_reset_colors_btn.focus_mode = Control.FOCUS_NONE
	_reset_colors_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_reset_colors_btn.pressed.connect(_on_reset_colors)
	cm_auto.add_child(_reset_colors_btn)
	# The live scale readout complements the legend (footer) — keep it
	# visible here too so a collapsed section still telegraphs the band.
	# (`_scale_label` is created in the footer; this is the readout text.)

	# ── Particle appearance (four VFX flags; live, default-off) ─
	var vfx_sec := _add_section(_visuals_page, "Particle appearance", "LIVE")
	var vfx_grid := GridContainer.new()
	vfx_grid.columns = 2
	vfx_grid.add_theme_constant_override("h_separation", 10)
	vfx_grid.add_theme_constant_override("v_separation", 6)
	vfx_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	vfx_sec.add_child(vfx_grid)
	_vfx_size_btn = _build_vfx_toggle("VfxSizeBtn", "Size∝m¹ᐟ³",
		"Scale each instance by cbrt(particle mass) instead of the linear mass law — the steep Salpeter count compresses so a few massive giants stay visible without swamping the dwarfs. Reads per-particle mass from pos.w (preserved by the nbody kick). Live, no reinit.",
		_on_vfx_size_toggled)
	vfx_grid.add_child(_vfx_size_btn)
	_vfx_glow_btn = _build_vfx_toggle("VfxGlowBtn", "Glow",
		"Additive-glow look: bright cores (q near the white-hot point) lift toward white and raise alpha so overlapping cores read as additive glow on the dark field; large instances get an extra halo ramp. Live, no reinit.",
		_on_vfx_glow_toggled)
	vfx_grid.add_child(_vfx_glow_btn)
	_vfx_depth_btn = _build_vfx_toggle("VfxDepthBtn", "Depth fade",
		"Fade instance alpha with camera distance (linear between 35% and 135% of the box diagonal). Uses the world-origin distance today; the deferred camera hook uses the live camera position. Live, no reinit.",
		_on_vfx_depth_toggled)
	vfx_grid.add_child(_vfx_depth_btn)
	_vfx_twoaxis_btn = _build_vfx_toggle("VfxTwoAxisBtn", "2-axis q/ρ",
		"Two-axis color: hue from Qi coherence (as the Qi rainbow) and lightness modulated by local density ρ = EY+EI (q-proxy today; the deferred EY/EI hook uses the true EY+EI). Requires the Rainbow toggle on.",
		_on_vfx_twoaxis_toggled)
	vfx_grid.add_child(_vfx_twoaxis_btn)

	# Generic presentation-profile toggle, kept in the backed registry so
	# initial state and live updates use the same no-signal sync mechanism.
	for e in EXTRA_TOGGLES:
		if e.get("tab", "system") == "visuals":
			vfx_grid.add_child(_build_extra_toggle(e))


	# ── Camera direction (manual-first pose source) ─────────────
	var camera_sec := _add_section(_visuals_page, "Camera direction", "LIVE")
	var camera_row := HBoxContainer.new()
	camera_row.add_theme_constant_override("separation", 6)
	camera_sec.add_child(camera_row)
	var camera_label := _make_label("Camera:", "gold", "param")
	camera_label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	camera_row.add_child(camera_label)
	_presentation_director_opt = OptionButton.new()
	_presentation_director_opt.name = "PresentationDirectorOpt"
	_presentation_director_opt.add_item("Manual")
	_presentation_director_opt.add_item("Wide envelope")
	_presentation_director_opt.add_item("Focus core")
	_presentation_director_opt.add_item("Record orbit")
	_presentation_director_opt.add_item("Follow structure")
	_presentation_director_opt.selected = 0
	_presentation_director_opt.tooltip_text = "Follow structure keeps the live cloud close and centered without orbiting. Other presets orbit. Any manual camera input immediately returns to Manual."
	_presentation_director_opt.custom_minimum_size = Vector2(150, 22)
	_presentation_director_opt.focus_mode = Control.FOCUS_NONE
	_presentation_director_opt.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_presentation_director_opt.item_selected.connect(_on_presentation_director_selected)
	camera_row.add_child(_presentation_director_opt)

## Observatory controls are backed exclusively by CassiSim's frozen
## presentation API. A missing API leaves that row disabled rather than
## inventing a second local state store.
const OBSERVATORY_BASE_PARAMS: Array[Dictionary] = [
	{"id": "exposure_ev", "caption": "Exposure (EV):", "min": -12.0, "max": 12.0, "step": 0.05, "default": 0.0},
	{"id": "optical_thickness", "caption": "Optical thickness:", "min": 0.0, "max": 20.0, "step": 0.05, "default": 1.0},
	{"id": "emission", "caption": "Emission:", "min": 0.0, "max": 20.0, "step": 0.01, "default": 0.3},
	{"id": "view_depth", "caption": "View depth:", "min": 0.0, "max": 5000.0, "step": 5.0, "default": 0.0,
		"tooltip": "Maximum camera distance for the ordered particle layer, in world units. 0 keeps the whole occupied domain; a smaller value shortens how far matter stays visible and bounds how many particles stack along one view ray."},
	{"id": "quality", "kind": "option", "options": ["Performance", "Balanced", "High", "Capture"], "caption": "Quality:", "default": 1},
]
const OBSERVATORY_ADVANCED_PARAMS: Array[Dictionary] = [
	{"id": "scattering", "caption": "Scattering:", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.35},
	{"id": "point_fraction", "caption": "Point fraction:", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.65},
	{"id": "bloom", "caption": "Bloom:", "min": 0.0, "max": 1.0, "step": 0.01, "default": 0.08},
	{"id": "auto_exposure_target", "caption": "Auto-exposure target:", "min": 0.01, "max": 0.5, "step": 0.005, "default": 0.03,
		"tooltip": "Luminance the auto exposure drives the lit matter toward, measured as the geometric mean of the metered samples before tone mapping. Lower is dimmer: 0.18 matches a mid-grey exposure; the default 0.03 sits about 2.6 EV below that. Regions with no matter are never metered."},
	{"id": "shutter_seconds", "caption": "Shutter (s):", "min": 0.0, "max": 0.25, "step": 0.001, "default": 0.0},
	{"id": "target_frame_ms", "caption": "Quality budget (ms):", "min": 8.0, "max": 100.0, "step": 0.5, "default": 20.0},
]
const OBSERVATORY_TOGGLES: Array[Dictionary] = [
	{"id": "temporal", "caption": "Temporal reprojection", "default": true},
	{"id": "auto_exposure", "caption": "Auto exposure", "default": true},
	{"id": "adaptive_quality", "caption": "Adaptive quality", "default": true},
	{"id": "background", "caption": "World background", "default": false},
]


func _build_observatory_controls() -> void:
	var appearance := _add_section(_visuals_page, "Appearance", "LIVE")
	_observatory_style_opt = COptionParam.new()
	_observatory_style_opt.name = "ObservatoryStyle"
	_observatory_style_opt.box_min_width = 150
	_observatory_style_opt.setup("View:", "gold", ["Scientific", "Observatory", "Cinematic"], 0,
		Callable(self, "_on_observatory_style_selected"))
	appearance.add_child(_observatory_style_opt)
	_observation_source_opt = COptionParam.new()
	_observation_source_opt.name = "ObservationSource"
	_observation_source_opt.box_min_width = 190
	_observation_source_opt.setup("Source:", "gold",
		["Simulation-unit optics", "Prescribed spectral preview", "Live physical matter"],
		0, Callable(self, "_on_observation_source_selected"))
	appearance.add_child(_observation_source_opt)
	var intro := _make_label("Choose one source for both the simulation and its optical readout. Simulation-unit optics uses the default solver; spectral preview is a declared 6500 K reference; live physical matter initializes and renders the evolving H/H+ gas with line and continuum emission, absorption, and radiation coupling.", "text_hint", "param")
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	intro.mouse_filter = Control.MOUSE_FILTER_IGNORE
	appearance.add_child(intro)
	var base_grid := GridContainer.new()
	base_grid.columns = 1
	base_grid.add_theme_constant_override("h_separation", 6)
	base_grid.add_theme_constant_override("v_separation", 5)
	appearance.add_child(base_grid)
	for entry in OBSERVATORY_BASE_PARAMS:
		if String(entry.get("kind", "param")) == "option":
			var options: Array[String] = []
			options.assign(entry.options)
			_add_observatory_option(base_grid, String(entry.id), String(entry.caption),
				options, int(entry.default))
		else:
			_add_observatory_param(base_grid, String(entry.id), String(entry.caption),
				float(entry.min), float(entry.max), float(entry.step), float(entry.default),
				String(entry.get("tooltip", "")))
	var appearance_actions := HBoxContainer.new()
	appearance_actions.add_theme_constant_override("separation", 6)
	appearance.add_child(appearance_actions)
	appearance_actions.add_child(CButton.make("Save appearance", Callable(self, "_on_save_observatory_preset")))
	appearance_actions.add_child(CButton.make("Load appearance", Callable(self, "_on_load_observatory_preset")))
	_observatory_status = _make_label("", "text_hint", "param")
	_observatory_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_observatory_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	appearance.add_child(_observatory_status)

	_observatory_advanced = CGroupPanel.new()
	_observatory_advanced.name = "AdvancedScattering"
	_observatory_advanced.set_title("Advanced scattering")
	_observatory_advanced.collapsed = true
	_observatory_advanced.toggled.connect(_on_group_toggled)
	_visuals_page.add_child(_observatory_advanced)
	var advanced := _observatory_advanced.content()
	var adv_grid := GridContainer.new()
	adv_grid.columns = 1
	adv_grid.add_theme_constant_override("h_separation", 6)
	adv_grid.add_theme_constant_override("v_separation", 5)
	advanced.add_child(adv_grid)
	for entry in OBSERVATORY_ADVANCED_PARAMS:
		_add_observatory_param(adv_grid, String(entry.id), String(entry.caption),
			float(entry.min), float(entry.max), float(entry.step), float(entry.default),
			String(entry.get("tooltip", "")))
	for entry in OBSERVATORY_TOGGLES:
		_add_observatory_toggle(adv_grid, String(entry.id), String(entry.caption), bool(entry.default))

	var capture := _add_section(_visuals_page, "Camera & capture", "LIVE")
	var capture_hint := _make_label("Manual camera remains the default owner. Saving/restoring a view stores only camera pose and FOV.", "text_hint", "param")
	capture_hint.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	capture_hint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	capture.add_child(capture_hint)
	var slots := VBoxContainer.new()
	slots.add_theme_constant_override("separation", 4)
	capture.add_child(slots)
	for slot in range(3):
		var slot_row := HBoxContainer.new()
		slot_row.add_theme_constant_override("separation", 4)
		slots.add_child(slot_row)
		var save := CButton.make("Save %d" % (slot + 1),
			Callable(self, "_on_capture_save_view").bind(slot))
		var restore := CButton.make("Restore %d" % (slot + 1),
			Callable(self, "_on_capture_restore_view").bind(slot))
		save.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		restore.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		slot_row.add_child(save)
		slot_row.add_child(restore)
	var capture_row := VBoxContainer.new()
	capture_row.add_theme_constant_override("separation", 4)
	capture.add_child(capture_row)
	var still_row := HBoxContainer.new()
	still_row.add_theme_constant_override("separation", 5)
	capture_row.add_child(still_row)
	_capture_scale_opt = COptionParam.new()
	_capture_scale_opt.name = "CaptureScale"
	_capture_scale_opt.box_min_width = 72
	_capture_scale_opt.setup("Still:", "gold", ["1x", "2x"], 0, Callable(self, "_on_capture_scale_selected"))
	still_row.add_child(_capture_scale_opt)
	still_row.add_child(CButton.make("Save PNG", Callable(self, "_on_capture_still_pressed")))
	var action_grid := GridContainer.new()
	action_grid.columns = 2
	action_grid.add_theme_constant_override("h_separation", 4)
	action_grid.add_theme_constant_override("v_separation", 4)
	capture_row.add_child(action_grid)
	action_grid.add_child(CButton.make("Start sequence", Callable(self, "_on_capture_sequence_started")))
	action_grid.add_child(CButton.make("Stop sequence", Callable(self, "_on_capture_sequence_stopped")))
	var overlay := CheckButton.new()
	overlay.name = "CaptureOverlay"
	overlay.text = "Overlay"
	overlay.focus_mode = Control.FOCUS_NONE
	overlay.toggled.connect(_on_capture_overlay_toggled)
	action_grid.add_child(overlay)
	var iface := CheckButton.new()
	iface.name = "CaptureInterface"
	iface.text = "Interface"
	iface.tooltip_text = "Hide controls without hiding the field image. F9 restores the interface."
	iface.button_pressed = true
	iface.focus_mode = Control.FOCUS_NONE
	iface.toggled.connect(_on_capture_interface_toggled)
	action_grid.add_child(iface)
	_capture_status = _make_label("Capture helper unavailable", "text_hint", "param")
	_capture_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_capture_status.mouse_filter = Control.MOUSE_FILTER_IGNORE
	capture.add_child(_capture_status)


func _add_observatory_param(parent: Control, key: String, caption: String,
		min_v: float, max_v: float, step_v: float, default_v: float,
		tooltip_v: String = "") -> void:
	var row := CParam.new()
	row.name = "Observatory_" + key
	row.setup(caption, "gold_soft", min_v, max_v, step_v, default_v,
		func(value: float) -> void: _set_observatory_value(key, value))
	if not tooltip_v.is_empty():
		row.tooltip_text = tooltip_v
	parent.add_child(row)
	_observatory_rows[key] = row


func _add_observatory_option(parent: Control, key: String, caption: String,
		options: Array[String], default_i: int) -> void:
	var row := COptionParam.new()
	row.name = "Observatory_" + key
	row.box_min_width = 150
	row.setup(caption, "gold_soft", options, default_i,
		func(value: int) -> void: _set_observatory_value(key, value))
	parent.add_child(row)
	_observatory_rows[key] = row


func _add_observatory_toggle(parent: Control, key: String, caption: String, default_v: bool) -> void:
	var toggle := _build_vfx_toggle("Observatory_" + key, caption, "Live presentation setting.", func(value: bool) -> void: _set_observatory_value(key, value))
	toggle.set_pressed_no_signal(default_v)
	parent.add_child(toggle)
	_observatory_toggles[key] = toggle


func _set_observatory_value(key: String, value: Variant) -> void:
	var sim := _get_sim()
	if sim == null or not sim.has_method("set_observatory_setting"):
		return
	sim.call("set_observatory_setting", key, value)


func _on_observatory_style_selected(index: int) -> void:
	var sim := _get_sim()
	if sim != null and sim.has_method("set_observatory_style"):
		sim.call("set_observatory_style", clampi(index, 0, 2))

func _on_observation_source_selected(index: int) -> void:
	var sim := _get_sim()
	if sim == null or not sim.has_method("set_observatory_source"):
		return
	var source := clampi(index, 0, 2)
	sim.call("set_observatory_source", source)
	var physical_enabled := source == 2
	if bool(sim.get("physical_matter_enabled")) != physical_enabled:
		sim.set("physical_matter_enabled", physical_enabled)
		if sim.has_method("reinit"):
			sim.call("reinit")


func _on_observatory_changed(settings: Dictionary) -> void:
	_sync_observatory_controls(settings)


func _sync_observatory_controls(incoming: Dictionary = {}) -> void:
	var sim := _get_sim()
	if sim == null:
		return
	var settings: Dictionary = incoming
	if settings.is_empty() and sim.has_method("get_observatory_settings"):
		var current: Variant = sim.call("get_observatory_settings")
		if current is Dictionary:
			settings = current
	var style := clampi(int(settings.get("style", int(sim.get("observatory_style")) if sim.get("observatory_style") != null else 0)), 0, 2)
	if _observatory_style_opt != null:
		_observatory_style_opt.set_value_no_signal(style)
	var source := clampi(int(settings.get("observation_source", 0)), 0, 2)
	if _observation_source_opt != null:
		_observation_source_opt.set_value_no_signal(source)
	for key in _observatory_rows.keys():
		var value: Variant = settings.get(key)
		if value == null:
			continue
		var row: Control = _observatory_rows[key]
		if row is COptionParam:
			(row as COptionParam).set_value_no_signal(int(value))
		elif row is CParam:
			(row as CParam).set_value_no_signal(float(value))
	for key in _observatory_toggles.keys():
		if settings.has(key):
			(_observatory_toggles[key] as CheckButton).set_pressed_no_signal(bool(settings[key]))
	for key: String in ["optical_thickness", "emission", "scattering", "point_fraction"]:
		if _observatory_rows.has(key) and _observatory_rows[key] is CParam:
			var editable := source == 0 \
					or (source == 2 and key in ["optical_thickness", "emission"])
			(_observatory_rows[key] as CParam).slider.editable = editable
	var naturalistic := style != 0
	# Naturalistic styles own the palette and compositor. Legacy color controls
	# and the legend are restored exactly when Scientific is selected.
	_rainbow_btn.disabled = naturalistic
	_color_src_opt.disabled = naturalistic
	_fit_btn.disabled = naturalistic
	_auto_align_btn.disabled = naturalistic
	_presentation_color_opt.disabled = naturalistic
	_save_colors_btn.disabled = naturalistic
	_reset_colors_btn.disabled = naturalistic
	if _legend != null:
		_legend.visible = not naturalistic
	if _scale_label != null:
		_scale_label.visible = not naturalistic
	if _observatory_status != null:
		_refresh_observatory_status(sim, source, style, naturalistic)
	_update_field_texture_visibility()


func _refresh_observatory_status(
		sim: Node3D, source: int, style: int, naturalistic: bool) -> void:
	if source == 2:
		var readiness: Dictionary = sim.call("get_physical_matter_readiness") \
				if sim.has_method("get_physical_matter_readiness") else {}
		if bool(readiness.get("ready", false)):
			var grid: Vector3i = readiness.get("grid", Vector3i.ZERO)
			var groups := int(readiness.get("groups", 0))
			var angles := int(readiness.get("angles", 0))
			_observatory_status.text = "Live H/H+ material · %d×%d×%d finite-volume grid · %d-group Lebedev-%d radiation · CIE 1931 camera" % [
				grid.x, grid.y, grid.z, groups, angles]
		elif bool(readiness.get("enabled", false)) \
				and String(readiness.get("error", "")).is_empty():
			_observatory_status.text = "Live physical matter initializing…"
		else:
			var missing: Array = readiness.get("missing", [])
			var detail := ", ".join(missing)
			if detail.is_empty():
				detail = String(readiness.get("error", "physical engine unavailable"))
			_observatory_status.text = "Live physical matter unavailable: " + detail
	elif not naturalistic:
		_observatory_status.text = "Scientific (legacy renderer)"
	elif source == 1:
		_observatory_status.text = "Prescribed material · 6500 K LTE · CIE 1931 · one-way frozen-state formal solution"
	elif style == 1:
		_observatory_status.text = "Observatory simulation-unit optics"
	else:
		_observatory_status.text = "Cinematic simulation-unit optics"


func _update_field_texture_visibility() -> void:
	if _viz_texture_rect == null:
		return
	var sim := _get_sim()
	var field_mode := (int(sim.get("mode")) if sim != null else _mode_seg.selected_index) == 1
	var style := int(sim.get("observatory_style")) if sim != null and sim.get("observatory_style") != null else 0
	# While the Qi-flow view is actually drawing, the legacy full-viewport
	# field canvas would cover the new 3D current geometry — keep it hidden.
	# Only this UI-owned overlay is involved: the sim mode and the
	# observation source are untouched (no reinit either way).
	_viz_texture_rect.visible = field_mode and style == 0 and not _qi_flow_active


func _on_save_observatory_preset() -> void:
	var sim := _get_sim()
	if sim != null and sim.has_method("save_observatory_preset"):
		var err: int = int(sim.call("save_observatory_preset"))
		_observatory_status.text = "Appearance saved." if err == OK else "Appearance save failed (%s)." % error_string(err)


func _on_load_observatory_preset() -> void:
	var sim := _get_sim()
	if sim != null and sim.has_method("load_observatory_preset"):
		var err: int = int(sim.call("load_observatory_preset"))
		_observatory_status.text = "Appearance loaded." if err == OK else "Appearance load failed (%s)." % error_string(err)


func _setup_capture_helper() -> void:
	var script := load("res://scripts/cassi_presentation_capture.gd")
	var sim := _get_sim()
	if script == null or sim == null:
		return
	var camera: Camera3D = null
	if sim.get_parent() != null:
		camera = sim.get_parent().get_node_or_null("Camera3D") as Camera3D
	if camera == null and get_viewport() != null:
		camera = get_viewport().get_camera_3d()
	if camera == null:
		return
	_capture_helper = Node.new()
	_capture_helper.name = "PresentationCapture"
	_capture_helper.set_script(script)
	add_child(_capture_helper)
	_capture_helper.connect("sequence_finished", _on_capture_sequence_finished)
	if _capture_helper.has_method("setup"):
		_capture_helper.call("setup", sim, camera)


func _sync_capture_helper() -> void:
	if _capture_status == null:
		return
	_capture_status.text = "Capture helper ready (user:// captures)" if _capture_helper != null else "Capture helper unavailable"


func _capture_call(method: String, args: Array = []) -> Variant:
	if _capture_helper == null or not _capture_helper.has_method(method):
		if _capture_status != null:
			_capture_status.text = "Capture unavailable: %s" % method
		return ERR_UNAVAILABLE
	return _capture_helper.callv(method, args)


func _on_capture_save_view(slot: int) -> void:
	var err := int(_capture_call("save_view", [slot]))
	if _capture_status != null:
		_capture_status.text = "View %d saved." % (slot + 1) if err == OK else "Save view %d failed (%s)." % [slot + 1, error_string(err)]


func _on_capture_restore_view(slot: int) -> void:
	var err := int(_capture_call("restore_view", [slot]))
	if _capture_status != null:
		_capture_status.text = "View %d restored." % (slot + 1) if err == OK else "Restore view %d failed (%s)." % [slot + 1, error_string(err)]


func _on_capture_scale_selected(_index: int) -> void:
	if _capture_status != null:
		_capture_status.text = "Still scale: %dx." % (2 if _index == 1 else 1)


func _on_capture_still_pressed() -> void:
	if _capture_helper == null or not _capture_helper.has_method("capture_still"):
		_capture_status.text = "Capture helper unavailable"
		return
	var scale := 1
	if _capture_scale_opt != null:
		scale = 2 if _capture_scale_opt.get_value() == 1 else 1
	var path: String = await _capture_helper.call("capture_still", scale)
	_capture_status.text = "Saved PNG: %s" % path if path != "" else "Still capture failed."


func _on_capture_sequence_started() -> void:
	var err := int(_capture_call("start_sequence", [30]))
	if _capture_status != null:
		_capture_status.text = "Sequence started at 30 fps." if err == OK else "Sequence start failed (%s)." % error_string(err)


func _on_capture_sequence_stopped() -> void:
	var path: String = str(_capture_call("stop_sequence"))
	if _capture_status != null:
		_capture_status.text = "Finishing PNG sequence..." if path != "" else "No active sequence."

func _on_capture_sequence_finished(summary: String) -> void:
	if _capture_status != null:
		_capture_status.text = "Sequence: %s" % summary



func _on_capture_overlay_toggled(enabled: bool) -> void:
	_capture_call("set_overlay_enabled", [enabled])


func _on_capture_interface_toggled(enabled: bool) -> void:
	_capture_call("set_interface_visible", [enabled])


## Build one VFX CheckButton with the house interaction defaults.
func _build_vfx_toggle(name: String, text: String, tip: String, cb: Callable) -> CheckButton:
	var t := CheckButton.new()
	t.name = name
	t.text = text
	t.tooltip_text = tip
	t.custom_minimum_size = Vector2(0, 22)
	t.focus_mode = Control.FOCUS_NONE
	t.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	t.toggled.connect(cb)
	return t


## Build the System page: Physics & lattice, Performance, RealSim, black
## hole thresholds, Diagnostics (the full _diag_label + falsify meter), and
## the disabled Server (future) fields.
func _build_system_page() -> void:
	# ── Physics & lattice toggles ───────────────────────────────
	var phys_sec := _add_section(_system_page, "Physics & lattice", "LIVE")
	var phys_grid := GridContainer.new()
	phys_grid.columns = 2
	phys_grid.add_theme_constant_override("h_separation", 10)
	phys_grid.add_theme_constant_override("v_separation", 6)
	phys_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	phys_sec.add_child(phys_grid)

	_bh_toggle_btn = _build_system_toggle("Black holes",
		"Enable the BH point-source sector (condensation + softened Newtonian pull) in any gravity mode", _on_black_holes_toggled, false)
	phys_grid.add_child(_bh_toggle_btn)
	_phi_box_btn = _build_system_toggle("φ box",
		"φ-aspect box (x:y:z = φ:1:φ²) — the theory's incommensurate bubble-lattice periods; breaks the cubic box-mode straight-line lock; applies on reinit", _on_phi_box_toggled, false)
	phys_grid.add_child(_phi_box_btn)
	_multirung_btn = _build_system_toggle("Multi-rung",
		"Seed the initial conditions with φ-spaced density modes so bubbles condense at several cascade scales; applies on reinit", _on_multirung_toggled, false)
	phys_grid.add_child(_multirung_btn)
	_meshless_btn = _build_system_toggle("Meshless",
		"Run the two-fluid field on the moving Voronoi cell mesh (JFA construction, steering + ALE remap); applies on reinit", _on_meshless_toggled, false)
	phys_grid.add_child(_meshless_btn)
	# Generic backed System toggles (meshless gravity, particle merge, BH
	# accretion, River calibration, field attractor, freeze field).
	for e in EXTRA_TOGGLES:
		if e.get("tab", "system") == "system":
			var t := _build_extra_toggle(e)
			phys_grid.add_child(t)

	# ── Performance ─────────────────────────────────────────────
	var perf_sec := _add_section(_system_page, "Performance", "LIVE")
	var perf_row := HBoxContainer.new()
	perf_row.add_theme_constant_override("separation", 8)
	perf_sec.add_child(perf_row)
	_no_rb_btn = _build_system_toggle("No readbacks",
		"Suppress CPU readbacks (occupancy/perf/q diagnostics) — removes the ~0.5 s stutter; physics and rendering unchanged", _on_suppress_readbacks_toggled, false)
	perf_row.add_child(_no_rb_btn)
	_vsync_btn = _build_system_toggle("VSync",
		"Frame pacing to the display refresh (on by default); off for uncapped frame rate — benchmarks and Movie-Maker recording want it off", _on_vsync_toggled, false)
	perf_row.add_child(_vsync_btn)

	# ── RealSim coefficients ────────────────────────────────────
	var rs_sec := _add_section(_system_page, "RealSim", "LIVE")
	var rs_grid := GridContainer.new()
	rs_grid.columns = 2
	rs_grid.add_theme_constant_override("h_separation", 10)
	rs_grid.add_theme_constant_override("v_separation", 6)
	rs_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	rs_sec.add_child(rs_grid)
	_init_spin_row(rs_grid, "realsim_drag")
	_init_spin_row(rs_grid, "realsim_viscosity")
	_init_spin_row(rs_grid, "realsim_friction")

	# ── Black-hole thresholds ───────────────────────────────────
	var bh_sec := _add_section(_system_page, "Black-hole thresholds", "LIVE")
	var bh_grid := GridContainer.new()
	bh_grid.columns = 2
	bh_grid.add_theme_constant_override("h_separation", 10)
	bh_grid.add_theme_constant_override("v_separation", 6)
	bh_grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	bh_sec.add_child(bh_grid)
	_init_spin_row(bh_grid, "qi_condensation_threshold")
	_init_spin_row(bh_grid, "bh_acc_rate")
	_init_spin_row(bh_grid, "bh_max_age")
	_init_spin_row(bh_grid, "bh_accretion_radius")

	# ── Diagnostics: full field readout + falsification meter ──
	var diag_sec := _add_section(_system_page, "Diagnostics", "")
	var diag_label2 = _make_label("", "text_dim", "detail")
	diag_label2.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	diag_label2.mouse_filter = Control.MOUSE_FILTER_IGNORE
	diag_sec.add_child(diag_label2)
	_diag_label = diag_label2
	var falsify_row := HBoxContainer.new()
	falsify_row.add_theme_constant_override("separation", 6)
	diag_sec.add_child(falsify_row)
	_falsify_btn = CheckButton.new()
	_falsify_btn.name = "FalsifyBtn"
	_falsify_btn.text = "w₀ live"
	_falsify_btn.tooltip_text = "LIVE falsification meter: reads r = <EY>/<EI> (volume-mean field ratio) at a low 2.5 Hz subsampled rate, runs the theory's w₀/wₐ estimator (the falsify_wo.py survey port), and shows w₀ + distance to DESI DR2's −0.838 on the info HUD. Opt-in; OFF hides the line."
	_falsify_btn.custom_minimum_size = Vector2(76, 22)
	_falsify_btn.focus_mode = Control.FOCUS_NONE
	_falsify_btn.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	_falsify_btn.toggled.connect(_on_falsify_toggled)
	falsify_row.add_child(_falsify_btn)

	# ── Server (future) fields — today's server row ─────────────
	var srv_sec := _add_section(_system_page, "Server (future)", "")
	var srv_row := HBoxContainer.new()
	srv_row.add_theme_constant_override("separation", 4)
	srv_sec.add_child(srv_row)
	_server_ip_edit = LineEdit.new()
	_server_ip_edit.placeholder_text = "IP"
	_server_ip_edit.text = "127.0.0.1"
	_server_ip_edit.custom_minimum_size = Vector2(90, 22)
	_server_ip_edit.editable = false
	_server_ip_edit.modulate = _tok_color("disabled")
	srv_row.add_child(_server_ip_edit)
	_server_port_edit = LineEdit.new()
	_server_port_edit.placeholder_text = "Port"
	_server_port_edit.text = "8080"
	_server_port_edit.custom_minimum_size = Vector2(55, 22)
	_server_port_edit.editable = false
	_server_port_edit.modulate = _tok_color("disabled")
	srv_row.add_child(_server_port_edit)
func _build_workbench_page() -> void:
	var intro := _make_label("One staged path: Preview is pure; Apply requires pause; Undo restores the exact pre-Apply checkpoint.", "text_hint", "param")
	intro.mouse_filter = Control.MOUSE_FILTER_IGNORE
	intro.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_workbench_page.add_child(intro)

	var transport := _add_section(_workbench_page, "Workbench transport", "")
	var tr := HBoxContainer.new()
	transport.add_child(tr)
	_wb_pause_btn = CButton.make("Pause / Resume", _on_wb_pause)
	_wb_pause_btn.name = "WorkbenchPause"
	_wb_pause_btn.tooltip_text = "Toggle simulation pause; every workbench mutation requires paused."
	tr.add_child(_wb_pause_btn)
	_wb_step_btn = CButton.make("Step 1", _on_wb_step)
	_wb_step_btn.name = "WorkbenchStep"
	_wb_step_btn.tooltip_text = "Advance exactly one deterministic physics step while paused."
	tr.add_child(_wb_step_btn)
	_wb_status_label = _make_label("Workbench ready (view-only)", "text_dim", "param")
	_wb_status_label.name = "WorkbenchStatus"
	_wb_status_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	transport.add_child(_wb_status_label)

	var agent_sec := _add_section(_workbench_page, "Field agent", "")
	var provider_grid := GridContainer.new()
	provider_grid.columns = 2
	provider_grid.add_theme_constant_override("h_separation", 8)
	provider_grid.add_theme_constant_override("v_separation", 5)
	agent_sec.add_child(provider_grid)
	var configured_url := OS.get_environment("CASSI_WORLD_URL")
	if configured_url.is_empty():
		configured_url = "http://127.0.0.1:8086"
	_wb_provider_url = _wb_make_line("Endpoint", configured_url, false, provider_grid)
	_wb_provider_url.name = "ParticleProviderEndpoint"
	var configured_session := OS.get_environment("CASSI_WORLD_SESSION")
	if configured_session.is_empty():
		configured_session = "cassi-cosmos-workbench"
	_wb_provider_session = _wb_make_line("Session", configured_session, false, provider_grid)
	_wb_provider_session.name = "ParticleProviderSession"
	_wb_provider_token = _wb_make_line("Bearer", OS.get_environment("CASSI_WORLD_TOKEN"), true, provider_grid)
	_wb_provider_token.name = "ParticleProviderToken"
	_wb_provider_status = _make_label("Provider: not contacted", "text_dim", "param")
	_wb_provider_status.name = "ParticleProviderStatus"
	_wb_provider_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	agent_sec.add_child(_wb_provider_status)
	_wb_chat_log = RichTextLabel.new()
	_wb_chat_log.name = "ParticleChatTranscript"
	_wb_chat_log.bbcode_enabled = false
	_wb_chat_log.fit_content = false
	_wb_chat_log.scroll_active = true
	_wb_chat_log.selection_enabled = true
	_wb_chat_log.custom_minimum_size = Vector2(0, 120)
	_wb_chat_log.text = "Field agent ready. Returned programs remain staged until Preview and Apply.\n"
	agent_sec.add_child(_wb_chat_log)
	_wb_chat_input = LineEdit.new()
	_wb_chat_input.name = "ParticleChatInput"
	_wb_chat_input.placeholder_text = "Arrange the selected particles into a ring around the orange cursor"
	_wb_chat_input.text_submitted.connect(func(_text: String) -> void: _on_wb_chat_send())
	agent_sec.add_child(_wb_chat_input)
	var chat_row := HBoxContainer.new()
	agent_sec.add_child(chat_row)
	var send_btn := CButton.make("Send", _on_wb_chat_send)
	send_btn.name = "ParticleChatSend"
	send_btn.tooltip_text = "Ask the persistent field session and stage its validated particle program. Never auto-applies."
	chat_row.add_child(send_btn)
	var ping_btn := CButton.make("Ping", _on_wb_provider_ping)
	ping_btn.name = "ParticleProviderPing"
	chat_row.add_child(ping_btn)
	_wb_staged_label = _make_label("No chat program staged", "text_hint", "param")
	_wb_staged_label.name = "ParticleStagedProgram"
	_wb_staged_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	agent_sec.add_child(_wb_staged_label)
	_wb_http = HTTPRequest.new()
	_wb_http.name = "ParticleWorldHTTP"
	_wb_http.timeout = 20.0
	_wb_http.request_completed.connect(_on_wb_http_completed)
	add_child(_wb_http)

	var tool_sec := _add_section(_workbench_page, "Operation / target", "")
	_wb_tool_opt = COptionParam.new()
	_wb_tool_opt.box_min_width = ROW_WIDTH
	_wb_tool_opt.setup("Tool", "gold", [
		"Deposit", "Align", "Impulse", "Line", "Ring", "Sphere", "Grid",
		"Helix", "Double helix", "Translate", "Scale", "Rotate",
	], 4, Callable(self, "_on_wb_tool"))
	_wb_tool_opt.tooltip_text = "Manual controls compile into the same FieldWorkbench command pipeline used by chat."
	tool_sec.add_child(_wb_tool_opt)
	_wb_selection_opt = COptionParam.new()
	_wb_selection_opt.box_min_width = ROW_WIDTH
	_wb_selection_opt.setup("Selection", "mint", ["All live", "Sphere", "Box"], 0, Callable())
	_wb_selection_opt.tooltip_text = "Select live particle IDs deterministically in ascending ID order."
	tool_sec.add_child(_wb_selection_opt)
	_wb_motion_opt = COptionParam.new()
	_wb_motion_opt.box_min_width = ROW_WIDTH
	_wb_motion_opt.setup("Motion", "mint", ["Exact + zero velocity", "Exact + preserve velocity", "Steer"], 0, Callable())
	tool_sec.add_child(_wb_motion_opt)
	var grid := GridContainer.new()
	grid.columns = 2
	grid.add_theme_constant_override("h_separation", 8)
	grid.add_theme_constant_override("v_separation", 5)
	tool_sec.add_child(grid)
	_wb_center_spins.clear()
	for axis in ["X", "Y", "Z"]:
		var spin := CSpinParam.new()
		spin.box_min_width = ROW_WIDTH
		spin.setup("Center %s" % axis, "gold_soft", -10000.0, 10000.0, 0.1, 0.0, Callable())
		spin.spin.tooltip_text = "World-space selection and target center (%s)." % axis
		grid.add_child(spin)
		_wb_center_spins.append(spin)
	_wb_cursor_arm = CheckButton.new()
	_wb_cursor_arm.text = "Place orange cursor in viewport"
	_wb_cursor_arm.tooltip_text = "Arm left-click placement. Leaving Workbench or collapsing the rail disarms it."
	_wb_cursor_arm.focus_mode = Control.FOCUS_NONE
	_wb_cursor_arm.toggled.connect(_on_wb_cursor_armed)
	tool_sec.add_child(_wb_cursor_arm)
	_wb_radius_spin = _wb_make_spin("Radius / size", 5.0, 0.1, 10000.0, "Selection radius, ring/sphere radius, or line half-scale.")
	grid.add_child(_wb_radius_spin)
	_wb_strength_spin = _wb_make_spin("Strength / pitch", 1.0, -10000.0, 10000.0, "Field strength, grid spacing, helix pitch, scale, or rotation degrees.")
	grid.add_child(_wb_strength_spin)
	_wb_vector_spins.clear()
	for axis in ["X", "Y", "Z"]:
		var vector_spin := _wb_make_spin("Vector %s" % axis, 0.0, -10000.0, 10000.0, "Impulse, offset, direction, normal, axis, or box half-extent.")
		grid.add_child(vector_spin)
		_wb_vector_spins.append(vector_spin)
	_wb_ratio_spin = _wb_make_spin("Ratio / turns", 3.0, -10000.0, 10000.0, "Alignment ratio or helix turn count.")
	grid.add_child(_wb_ratio_spin)
	_wb_speed_spin = _wb_make_spin("Steer speed", 1.0, 0.01, 10000.0, "Bounded steering speed when Motion is Steer.")
	grid.add_child(_wb_speed_spin)
	var action_row := HBoxContainer.new()
	tool_sec.add_child(action_row)
	_wb_preview_btn = CButton.make("Preview", _on_wb_preview)
	_wb_preview_btn.name = "ParticlePreview"
	_wb_preview_btn.tooltip_text = "Resolve the staged program and show cyan ghost targets without changing state."
	action_row.add_child(_wb_preview_btn)
	_wb_apply_btn = CButton.make("Apply", _on_wb_apply)
	_wb_apply_btn.name = "ParticleApply"
	_wb_apply_btn.tooltip_text = "Capture automatic undo, then apply the staged program while paused."
	action_row.add_child(_wb_apply_btn)
	_wb_undo_btn = CButton.make("Undo", _on_wb_undo)
	_wb_undo_btn.name = "ParticleUndo"
	_wb_undo_btn.tooltip_text = "Restore the exact automatic pre-Apply checkpoint."
	action_row.add_child(_wb_undo_btn)

	var view_sec := _add_section(_workbench_page, "Measure / scenario", "")
	_wb_lens_opt = COptionParam.new()
	_wb_lens_opt.box_min_width = ROW_WIDTH
	_wb_lens_opt.setup("Lens", "mint", ["Qi", "Density", "Phase", "Velocity"], 0, Callable(self, "_on_wb_lens"))
	_wb_lens_opt.tooltip_text = "Choose a readout lens; this never changes simulation physics."
	view_sec.add_child(_wb_lens_opt)
	var view_row := HBoxContainer.new()
	view_sec.add_child(view_row)
	var measure := CButton.make("Measure region", _on_wb_measure)
	measure.tooltip_text = "Read the selected region using the active lens."
	view_row.add_child(measure)
	_wb_save_btn = CButton.make("Save scenario", _on_wb_save)
	_wb_save_btn.tooltip_text = "Save deterministic workbench state to user://workbench_scenario.json."
	view_row.add_child(_wb_save_btn)
	_wb_replay_btn = CButton.make("Replay scenario", _on_wb_replay)
	_wb_replay_btn.tooltip_text = "Replay user://workbench_scenario.json."
	view_row.add_child(_wb_replay_btn)
	var branch_row := HBoxContainer.new()
	view_sec.add_child(branch_row)
	_wb_checkpoint_btn = CButton.make("Checkpoint", _on_wb_checkpoint)
	_wb_checkpoint_btn.tooltip_text = "Capture the exact authoritative state."
	branch_row.add_child(_wb_checkpoint_btn)
	_wb_branch_btn = CButton.make("Compare branch", _on_wb_branch)
	_wb_branch_btn.tooltip_text = "Restore checkpoint, apply the staged operation, and show fixed-scale differences."
	branch_row.add_child(_wb_branch_btn)
	_wb_signature_btn = CButton.make("Energy ≠ coherence", _on_wb_signature)
	_wb_signature_btn.tooltip_text = "Run the equal-field-intensity, different-coherence guided fixture."
	view_sec.add_child(_wb_signature_btn)

func _wb_make_spin(caption: String, value: float, min_v: float, max_v: float, tip: String) -> CSpinParam:
	var s := CSpinParam.new()
	s.box_min_width = ROW_WIDTH
	s.setup(caption, "gold_soft", min_v, max_v, 0.1, value, Callable())
	s.spin.tooltip_text = tip
	return s

func _wb_make_line(caption: String, value: String, secret: bool, parent: GridContainer) -> LineEdit:
	var label := _make_label(caption, "text_hint", "param")
	parent.add_child(label)
	var edit := LineEdit.new()
	edit.text = value
	edit.secret = secret
	edit.custom_minimum_size = Vector2(ROW_WIDTH, 24)
	parent.add_child(edit)
	return edit

func _wb_status(text: String) -> void:
	if _wb_status_label != null:
		_wb_status_label.text = text

func _wb_call(method: String, args: Array = []) -> Variant:
	var sim = _get_sim()
	if sim == null:
		_wb_status("Workbench: CassiSim unavailable")
		return null
	if not sim.has_method(method):
		_wb_status("Workbench: API missing %s" % method)
		return null
	return sim.callv(method, args)
func _on_wb_cursor_armed(armed: bool) -> void:
	var result = _wb_call("workbench_arm_cursor", [armed])
	if result is Dictionary and bool(result.get("ok", false)):
		_wb_status("Workbench: viewport placement %s" % ("armed" if armed else "disarmed"))

func _on_wb_cursor_changed(world_position: Vector3, _source: String) -> void:
	if _wb_center_spins.size() != 3:
		return
	_wb_center_spins[0].set_value_no_signal(world_position.x)
	_wb_center_spins[1].set_value_no_signal(world_position.y)
	_wb_center_spins[2].set_value_no_signal(world_position.z)

func _on_wb_pause() -> void:
	var sim = _get_sim()
	if sim == null: return
	if sim.has_method("workbench_pause") and not sim.playing:
		sim.call("workbench_resume")
	elif sim.has_method("workbench_pause"):
		sim.call("workbench_pause")
	else:
		sim.playing = not sim.playing
	_wb_status("Workbench: %s" % ("running" if sim.playing else "paused"))

func _on_wb_step() -> void:
	var sim = _get_sim()
	if sim == null: return
	if sim.playing:
		_wb_status("Pause before stepping (no mutation performed)")
		return
	if _wb_call("workbench_step", [1]) != null:
		_wb_status("Workbench: stepped 1")

func _on_wb_tool(_idx: int) -> void:
	_wb_status("Workbench: tool staged; click Apply while paused")

func _on_wb_lens(_idx: int) -> void:
	_wb_status("Workbench: lens changed (view-only)")

func _wb_center() -> Vector3:
	return Vector3(_wb_center_spins[0].get_value(), _wb_center_spins[1].get_value(), _wb_center_spins[2].get_value())

func _wb_vector() -> Vector3:
	return Vector3(_wb_vector_spins[0].get_value(), _wb_vector_spins[1].get_value(), _wb_vector_spins[2].get_value())

func _wb_selection(center: Vector3, radius: float, vector: Vector3) -> Dictionary:
	var selection_index := int(_wb_selection_opt.get_value())
	if selection_index == 0:
		return {"type": "all"}
	if selection_index == 1:
		return {"type": "sphere", "center": center, "radius": radius}
	var half_extents := vector.abs()
	if half_extents.x <= 0.0 or half_extents.y <= 0.0 or half_extents.z <= 0.0:
		half_extents = Vector3.ONE * radius
	return {"type": "box", "center": center, "half_extents": half_extents}

func _wb_motion() -> Dictionary:
	var motion_index := int(_wb_motion_opt.get_value())
	if motion_index == 2:
		return {"type": "steer", "speed": _wb_speed_spin.get_value()}
	return {"type": "exact", "velocity_policy": "preserve" if motion_index == 1 else "zero"}

func _wb_request_id(prefix: String) -> String:
	return "%s-%d-%d" % [prefix, int(Time.get_unix_time_from_system()), Time.get_ticks_usec()]

func _wb_dict() -> Dictionary:
	var tool := int(_wb_tool_opt.get_value())
	var center := _wb_center()
	var radius := _wb_radius_spin.get_value()
	var strength := _wb_strength_spin.get_value()
	var vector := _wb_vector()
	var ratio := _wb_ratio_spin.get_value()
	if tool < 3:
		return {"tool": tool, "center": center, "radius": radius, "strength": strength, "vector": vector, "ratio": ratio}
	var axis := vector.normalized() if vector.length_squared() > 1e-24 else Vector3.UP
	var target: Dictionary
	match tool:
		3:
			target = {"type": "line", "center": center, "direction": Vector3.RIGHT if vector.length_squared() <= 1e-24 else axis, "length": radius * 2.0}
		4:
			target = {"type": "ring", "center": center, "normal": axis, "radius": radius, "phase": 0.0}
		5:
			target = {"type": "sphere", "center": center, "radius": radius}
		6:
			target = {"type": "grid", "center": center, "spacing": maxf(absf(strength), 0.1)}
		7, 8:
			target = {"type": "double_helix" if tool == 8 else "helix", "center": center, "axis": axis, "radius": radius, "pitch": maxf(absf(strength), 0.1), "turns": maxf(absf(ratio), 0.1), "phase": 0.0}
		9:
			target = {"type": "translate", "offset": vector}
		10:
			target = {"type": "scale", "center": center, "factor": maxf(absf(strength), 0.01)}
		_:
			target = {"type": "rotate", "center": center, "axis": axis, "angle_radians": deg_to_rad(strength)}
	var sim = _get_sim()
	var particle_count := int(sim.N_particles) if sim != null else 2500000
	return {
		"schema": "cassi.particle-program.v1",
		"operation": "arrange",
		"selection": _wb_selection(center, radius, vector),
		"target": target,
		"motion": _wb_motion(),
		"constraints": {"maximum_particles": maxi(particle_count, 1), "maximum_displacement": 10000.0, "maximum_speed": 10000.0},
		"source": {"kind": "manual"},
		"request_id": _wb_request_id("manual"),
	}

func _wb_active_command() -> Dictionary:
	return _wb_staged_program.duplicate(true) if not _wb_staged_program.is_empty() else _wb_dict()

func _on_wb_preview() -> void:
	var sim = _get_sim()
	if sim == null:
		return
	if sim.playing:
		_wb_status("Workbench: pause before Preview")
		return
	var result = _wb_call("workbench_preview", [_wb_active_command()])
	if not result is Dictionary:
		return
	if not bool(result.get("ok", false)):
		_wb_status("Preview rejected: %s" % str(result.get("error", "unknown")))
		if not _wb_staged_program.is_empty():
			_wb_post_result({"schema":"cassi.particle-result.v1", "status":"rejected", "error":str(result.get("error", "unknown")), "affected_count":0, "world_step":int(sim.get("_step_count"))})
		return
	if not _wb_staged_digest.is_empty() and str(result.get("program_digest", "")) != _wb_staged_digest:
		_wb_call("workbench_clear_preview")
		_wb_status("Preview rejected: provider/local program digest mismatch")
		_wb_post_result({"schema":"cassi.particle-result.v1", "status":"rejected", "error":"program_digest_mismatch", "affected_count":0, "world_step":int(sim.get("_step_count"))})
		return
	_wb_status("Preview: %d particles, max Δ %.4f" % [int(result.get("affected_count", 0)), float(result.get("maximum_displacement", 0.0))])
	if _wb_staged_label != null:
		_wb_staged_label.text = "Previewed %s — %d particles" % [str(result.get("program_digest", "")).left(12), int(result.get("affected_count", 0))]

func _apply_receipt(result: Dictionary) -> Dictionary:
	if bool(result.get("duplicate", false)):
		return result.get("receipt", {})
	var commands: Array = result.get("commands", [])
	if commands.is_empty() or not commands[-1] is Dictionary:
		return {}
	return commands[-1].get("receipt", {})

func _on_wb_apply() -> void:
	var sim = _get_sim()
	if sim == null:
		return
	if sim.playing:
		_wb_status("Workbench: pause before Apply")
		return
	var chat_program := not _wb_staged_program.is_empty()
	var result = _wb_call("workbench_apply", [_wb_active_command()])
	if not result is Dictionary:
		return
	if not bool(result.get("ok", false)):
		_wb_status("Apply rejected: %s" % str(result.get("error", "unknown")))
		if chat_program:
			_wb_post_result({"schema":"cassi.particle-result.v1", "status":"rejected", "error":str(result.get("error", "unknown")), "affected_count":0, "world_step":int(sim.get("_step_count"))})
		return
	var receipt := _apply_receipt(result)
	_wb_status("Workbench: %s" % ("duplicate receipt returned" if bool(result.get("duplicate", false)) else "operation applied"))
	if chat_program and not receipt.is_empty():
		_wb_post_result(receipt)

func _on_wb_undo() -> void:
	var result = _wb_call("workbench_undo")
	if result is Dictionary:
		_wb_status("Undo: %s" % (str(result.get("digest", "")).left(12) if bool(result.get("ok", false)) else str(result.get("error", "unavailable"))))
		if bool(result.get("ok", false)):
			_wb_chat_append("World", "Last Apply restored from its exact automatic checkpoint.")

func _wb_wire_value(value: Variant) -> Variant:
	if value is Vector3:
		return [value.x, value.y, value.z]
	if value is Array:
		var array: Array = []
		for item in value:
			array.append(_wb_wire_value(item))
		return array
	if value is Dictionary:
		var mapped := {}
		for key in value:
			mapped[str(key)] = _wb_wire_value(value[key])
		return mapped
	return value

func _wb_endpoint() -> String:
	var endpoint := _wb_provider_url.text.strip_edges().trim_suffix("/")
	var pattern := RegEx.new()
	pattern.compile("^http://127[.]0[.]0[.]1:([0-9]{1,5})$")
	var matched := pattern.search(endpoint)
	if matched == null:
		return ""
	var port := int(matched.get_string(1))
	return endpoint if port >= 1 and port <= 65535 else ""

func _wb_begin_request(action: String, path: String, body: Dictionary = {}, method := HTTPClient.METHOD_POST) -> bool:
	if _wb_http == null or _wb_http.get_http_client_status() != HTTPClient.STATUS_DISCONNECTED:
		_wb_status("Provider request already in flight")
		return false
	var endpoint := _wb_endpoint()
	if endpoint.is_empty():
		_wb_status("Provider endpoint must be explicit 127.0.0.1 HTTP")
		return false
	var token := _wb_provider_token.text
	if token.to_utf8_buffer().size() < 16:
		_wb_status("Provider bearer token must contain at least 16 UTF-8 bytes")
		return false
	var headers := PackedStringArray(["Accept: application/json", "Authorization: Bearer " + token])
	var encoded := ""
	if method == HTTPClient.METHOD_POST:
		headers.append("Content-Type: application/json")
		encoded = JSON.stringify(_wb_wire_value(body))
	_wb_http_action = action
	var error := _wb_http.request(endpoint + path, headers, method, encoded)
	if error != OK:
		_wb_http_action = ""
		_wb_status("Provider request failed to start: %s" % error_string(error))
		return false
	_wb_provider_status.text = "Provider: contacting %s" % endpoint
	return true

func _wb_world_context() -> Dictionary:
	var status = _wb_call("workbench_status")
	var state: Dictionary = status.get("state", {}) if status is Dictionary else {}
	var center := _wb_center()
	var vector := _wb_vector()
	var radius := _wb_radius_spin.get_value()
	var world_center: Vector3 = state.get("window_center", Vector3.ZERO)
	var extents: Vector3 = state.get("extents", Vector3.ONE)
	return {
		"cursor": [center.x, center.y, center.z],
		"selection": _wb_wire_value(_wb_selection(center, radius, vector)),
		"particle_count": int(state.get("particle_count", 1)),
		"world_bounds": {"min":[world_center.x-extents.x, world_center.y-extents.y, world_center.z-extents.z], "max":[world_center.x+extents.x, world_center.y+extents.y, world_center.z+extents.z]},
		"constraints": {"maximum_particles":maxi(int(state.get("particle_count", 1)), 1), "maximum_displacement":maxf(extents.length() * 2.0, 1.0), "maximum_speed":10000.0},
		"default_radius": radius,
		"world_step": int(state.get("step", 0)),
	}

func _wb_chat_append(role: String, text: String) -> void:
	if _wb_chat_log == null:
		return
	_wb_chat_log.text += "%s: %s\n" % [role, text]
	_wb_chat_log.scroll_to_line(maxi(_wb_chat_log.get_line_count() - 1, 0))

func _on_wb_chat_send() -> void:
	var message := _wb_chat_input.text.strip_edges()
	if message.is_empty():
		_wb_status("Enter a particle-world request first")
		return
	var request_id := _wb_request_id("world")
	_wb_staged_program.clear()
	_wb_staged_digest = ""
	_wb_staged_request_id = ""
	_wb_call("workbench_clear_preview")
	_wb_chat_append("You", message)
	var body := {
		"user": _wb_provider_session.text.strip_edges(),
		"world_id": "cassi-cosmos-main",
		"request_id": request_id,
		"message": message,
		"context": _wb_world_context(),
	}
	if _wb_begin_request("turn", "/v1/world/turn", body):
		_wb_chat_input.clear()

func _on_wb_provider_ping() -> void:
	_wb_begin_request("health", "/v1/health", {}, HTTPClient.METHOD_GET)

func _wb_post_result(outcome: Dictionary) -> void:
	if _wb_staged_request_id.is_empty() or _wb_staged_digest.is_empty():
		return
	_wb_pending_result_detail = str(outcome.get("error", outcome.get("status", "")))
	var body := {
		"user": _wb_provider_session.text.strip_edges(),
		"world_id": "cassi-cosmos-main",
		"request_id": _wb_staged_request_id,
		"program_digest": _wb_staged_digest,
		"outcome": _wb_wire_value(outcome),
	}
	if not _wb_begin_request("result", "/v1/world/result", body):
		_wb_status("World result retained locally; provider post did not start")

func _on_wb_http_completed(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	var action := _wb_http_action
	_wb_http_action = ""
	var parsed: Variant = JSON.parse_string(body.get_string_from_utf8())
	if result != HTTPRequest.RESULT_SUCCESS or response_code < 200 or response_code >= 300 or not parsed is Dictionary:
		var message := "transport=%d HTTP=%d" % [result, response_code]
		if parsed is Dictionary and parsed.has("error"):
			message = str(parsed.error.get("message", message)) if parsed.error is Dictionary else str(parsed.error)
		_wb_provider_status.text = "Provider: error — " + message
		_wb_status("Provider: " + message)
		return
	_wb_provider_status.text = "Provider: connected — HTTP %d" % response_code
	if action == "health":
		_wb_status("Provider health: %s" % str(parsed.get("status", "ok")))
		return
	if action == "turn":
		_wb_chat_append("Field", str(parsed.get("assistant", "")))
		var staged: Variant = parsed.get("staged_program")
		if staged is Dictionary:
			_wb_staged_program = staged.duplicate(true)
			_wb_staged_digest = str(parsed.get("program_digest", ""))
			_wb_staged_request_id = str(parsed.get("request_id", ""))
			_wb_staged_label.text = "Staged %s via %s — Preview before Apply" % [_wb_staged_digest.left(12), str(parsed.get("planner", "provider"))]
			_wb_status("Provider program staged; no world mutation performed")
		else:
			_wb_staged_label.text = "Clarification: %s" % str(parsed.get("clarification", "no program"))
			_wb_status("Provider returned a clarification; nothing staged")
		return
	if action == "result":
		_wb_chat_append("Field", str(parsed.get("assistant", "")))
		var observed_status := str(parsed.get("status", "observed"))
		_wb_staged_label.text = "%s receipt observed once by field — %s" % [observed_status.capitalize(), _wb_staged_digest.left(12)]
		var detail_suffix := "" if _wb_pending_result_detail.is_empty() else " — " + _wb_pending_result_detail
		_wb_pending_result_detail = ""
		_wb_status("Provider observed the %s world result exactly once%s" % [observed_status, detail_suffix])
func _on_wb_measure() -> void:
	var result = _wb_call("workbench_measure", [_wb_center(), _wb_radius_spin.get_value()])
	if result != null:
		_wb_status("Workbench measurement: %s" % str(result))

func _on_wb_save() -> void:
	if _wb_call("workbench_save", ["user://workbench_scenario.json"]) != null:
		_wb_status("Workbench: saved user://workbench_scenario.json")
func _on_wb_checkpoint() -> void:
	var result = _wb_call("workbench_capture_checkpoint")
	if result is Dictionary:
		_wb_status("Checkpoint: %s" % str(result.get("digest", result.get("error", "unavailable"))))

func _on_wb_branch() -> void:
	var result = _wb_call("workbench_run_branch", ["staged", [_wb_dict()], 0])
	if result is Dictionary:
		_wb_status("Branch difference: %s" % str(result.get("difference", result.get("error", "unavailable"))))

func _on_wb_signature() -> void:
	var result = _wb_call("workbench_signature")
	if result is Dictionary:
		_wb_status("Equal E², different coherence: %s" % str(result))

func _on_wb_replay() -> void:
	if _wb_call("workbench_replay", ["user://workbench_scenario.json"]) != null:
		_wb_status("Workbench: replayed user://workbench_scenario.json")

## Build one System-page CheckButton with the house interaction defaults.
## NOTE: the callback is NOT connected here — these toggles are
## direct-assigned by the init sync (e.g. `_multirung_btn.button_pressed =
## sim.multi_rung_seed`) and connecting at build would make that assignment
## spuriously fire a reinit() on startup. The preserved connect-after-init
## block in _ready() wires them after the sim values are synced.
func _build_system_toggle(text: String, tip: String, _cb: Callable, _pressed: bool) -> CheckButton:
	var t := CheckButton.new()
	t.text = text
	t.tooltip_text = tip
	t.custom_minimum_size = Vector2(0, 22)
	t.focus_mode = Control.FOCUS_NONE
	t.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	return t


## Push the sim's live values into every backed setting (no-signal setters
## so syncing never fires a spurious callback/reinit on startup), and wire
## the backed toggles' signals AFTER that init sync.
func _sync_extra_params() -> void:
	var sim = _get_sim()
	if sim == null:
		# No sim yet — leave the generic controls at their schema defaults;
		# the callbacks remain unwired (defensive, never crash).
		for id in _extra_toggles.keys():
			_extra_toggles[id].toggled.connect(_on_extra_toggle_changed.bind(id))
		return
	for id in _extra_spins.keys():
		var spin: CSpinParam = _extra_spins[id]
		for e in EXTRA_PARAMS:
			if e.id != id:
				continue
			spin.set_value_no_signal(float(sim.get(String(e.prop))))
			break
	for id in _extra_options.keys():
		var opt: COptionParam = _extra_options[id]
		for e in EXTRA_PARAMS:
			if e.id != id:
				continue
			opt.set_value_no_signal(int(sim.get(String(e.prop))))
			break
	_sync_shape_setting_rows(sim)
	for id in _extra_toggles.keys():
		var t: CheckButton = _extra_toggles[id]
		var e: Dictionary = _extra_toggle_ids.get(id, {})
		if not e.is_empty():
			var b: Variant = sim.get(String(e.prop))
			t.set_pressed_no_signal(bool(b))
		t.toggled.connect(_on_extra_toggle_changed.bind(id))


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
			var param := CParam.new()
			param.setup(caption, token, p.min, p.max, p.step, p.default,
				Callable(self, String(p.changed)))
			if id == "xi":
				_xi_slider = param
				_xi_label = param.caption_label
				param.caption_label.text = "%s %.1f" % [caption, p.default]
			elif id == "src":
				_src_slider = param
				_src_label = param.caption_label
				param.caption_label.text = "%s %.2f" % [caption, p.default]
			return param
		"spin":
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
			var opt_param := COptionParam.new()
			opt_param.box_min_width = int(width)
			var options: Array[String] = []
			for name_variant in p.get("options", []):
				options.append(String(name_variant))
			opt_param.setup(caption, token, options, int(p.default),
				Callable(self, String(p.changed)))
			if id == "init":
				opt_param.tooltip_text = "Plummer/Gaussian/Uniform preserve the original spherical support. Designed shapes start at rest; choose Initial motion for explicitly kinematic velocities."
				_init_opt = opt_param
			return opt_param
	return null
func _sync_color_widgets(sim: Node3D) -> void:
	var cm: int = int(sim.particle_color_mode)
	var base: int = cm & 0xF
	var flags: int = (cm >> 4) & 0xF
	_rainbow_btn.set_pressed_no_signal(base >= 1)
	# source dropdown: 0=vel-dir(6), 1=Qi(2/4), 2=field-phase(5), 3=vel-speed(1)
	match base:
		6: _color_src_opt.select(0)
		2, 4: _color_src_opt.select(1)
		5: _color_src_opt.select(2)
		1: _color_src_opt.select(3)
	if _presentation_color_opt != null:
		_presentation_color_opt.select(clampi(int(sim.presentation_color_scheme), 0, 1))
	_auto_align_btn.set_pressed_no_signal(sim.auto_align_colors)
	_vfx_twoaxis_btn.set_pressed_no_signal(base == 4)
	_vfx_size_btn.set_pressed_no_signal((flags & 0x1) != 0)
	_vfx_glow_btn.set_pressed_no_signal((flags & 0x2) != 0)
	_vfx_depth_btn.set_pressed_no_signal((flags & 0x4) != 0)
	_sync_color_enabled()
	if _legend:
		var band_fit := base >= 1 and base <= 4
		_legend.set_sim(sim, band_fit and (_color_src_opt.selected == 1 or _color_src_opt.selected == 2))
	_update_scale_label()


## Live numeric readout of the active color scale (the values the LOW/HIGH
## legend handles set). Engine slots: 2 = lo1, 10 = hiC, 13 = a_hi (white
func _update_scale_label() -> void:
	var sim = _get_sim()
	if sim == null or _scale_label == null:
		return
	var base := int(sim.particle_color_mode) & 0xF
	if base == 0 or base >= 5 or not sim.has_method("gradient_engine"):
		_scale_label.text = ""
		return
	var e: PackedFloat32Array = sim.gradient_engine()
	if e.size() < 17 or e[11] <= 0.0:
		_scale_label.text = ""
		return
	var s: String = "%s → %s" % [_fmt_scale(e[2]), _fmt_scale(e[10])]
	_scale_label.text = s
	var src_name := "Velocity"
	match _color_src_opt.selected:
		1, 2: src_name = "Qi"
	if e[15] > 0.5:
		_scale_label.tooltip_text = "%s color scale — drag LOW and HIGH on the legend to change it; WHITE is the fixed %s" % [src_name, _fmt_scale(e[13])]
	else:
		_scale_label.tooltip_text = "%s color scale — drag LOW and HIGH on the legend to change it" % src_name


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
	var base := int(_get_sim().particle_color_mode) & 0xF if _get_sim() != null else 0
	var band_fit := base >= 1 and base <= 4
	_color_src_opt.disabled = not on
	_fit_btn.disabled = not on or not band_fit
	_auto_align_btn.disabled = not on or not band_fit
	if not band_fit and _auto_align_btn.button_pressed:
		_auto_align_btn.set_pressed_no_signal(false)


func _on_field_texture_updated(tex: Texture2D) -> void:
	_viz_texture_rect.texture = tex


func _set_mode_highlight(active: int) -> void:
	_mode_seg.set_selected_no_signal(active)
	_update_field_texture_visibility()


func _set_grav_highlight(active: int) -> void:
	_gravity_seg.set_value_no_signal(active)


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
	if bool(sim.gridless_physics):
		var site_eng = sim._physics_engine
		if site_eng == null or not site_eng._ml_psi_y.is_valid() \
				or not site_eng._ml_psi_i.is_valid() or not site_eng._ml_vol.is_valid():
			return
	if sim.suppress_readbacks:
		return  # reading the live RD would stall — leave the last estimate
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
	# Gridless production uses the authoritative moving-site field. The
	# volume weighting preserves the survey observable while avoiding any
	# raster buffer read.
	if bool(sim.gridless_physics):
		var site_eng = sim._physics_engine
		if site_eng == null or site_eng._rd == null:
			return -1.0
		if not site_eng._ml_psi_y.is_valid() or not site_eng._ml_psi_i.is_valid() \
				or not site_eng._ml_vol.is_valid():
			return -1.0
		var ns: int = int(site_eng._ml_tree_nsrc)
		if ns <= 0:
			return -1.0
		var sample_sites: int = mini(ns, FALSIFY_MAX_CELLS)
		var offset_sites: int = maxi((ns - sample_sites) / 2, 0)
		var ey_d: PackedByteArray = site_eng._rd.buffer_get_data(
			site_eng._ml_psi_y, offset_sites * 4, sample_sites * 4)
		var ei_d: PackedByteArray = site_eng._rd.buffer_get_data(
			site_eng._ml_psi_i, offset_sites * 4, sample_sites * 4)
		var vol_d: PackedByteArray = site_eng._rd.buffer_get_data(
			site_eng._ml_vol, offset_sites * 4, sample_sites * 4)
		if ey_d.size() < sample_sites * 4 or ei_d.size() < sample_sites * 4 \
				or vol_d.size() < sample_sites * 4:
			return -1.0
		var ey_site := ey_d.to_float32_array()
		var ei_site := ei_d.to_float32_array()
		var vol_site := vol_d.to_float32_array()
		var ey_sum := 0.0
		var ei_sum := 0.0
		var n_ok := 0
		for i in range(sample_sites):
			var eyv: float = ey_site[i]
			var eiv: float = ei_site[i]
			var vv: float = vol_site[i]
			if is_finite(eyv) and is_finite(eiv) and is_finite(vv) \
					and eyv > 0.0 and eiv > 0.0 and vv > 0.0:
				ey_sum += eyv * vv
				ei_sum += eiv * vv
				n_ok += 1
		if n_ok < 64 or ei_sum <= 0.0:
			return -1.0
		return ey_sum / ei_sum
	var field_state: Dictionary = sim.get_field_role_state()
	if not field_state.ey.is_valid() or not field_state.ei.is_valid():
		return -1.0
	var nc: int = sim.grid_N * sim.grid_N * sim.grid_N
	if nc <= 0:
		return -1.0
	var sample_cells: int = mini(nc, FALSIFY_MAX_CELLS)
	var offset: int = maxi((nc - sample_cells) / 2, 0)
	var ey_d: PackedByteArray = sim._rd.buffer_get_data(field_state.ey, offset * 4, sample_cells * 4)
	var ei_d: PackedByteArray = sim._rd.buffer_get_data(field_state.ei, offset * 4, sample_cells * 4)
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
func _input(event: InputEvent) -> void:
	if not event is InputEventKey or not event.pressed:
		return
	var focus := get_viewport().gui_get_focus_owner()
	if focus is LineEdit or focus is TextEdit or focus is SpinBox:
		return
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


func _on_presentation_color_scheme_selected(idx: int) -> void:
	var sim = _get_sim()
	if sim == null:
		return
	sim.presentation_color_scheme = clampi(idx, 0, 1)


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
		_rainbow_btn.set_pressed_no_signal(true)
	_apply_particle_color_mode(sim)
	_sync_color_widgets(sim)
	_repaint_if_paused(sim)


func _on_init_selected(idx: int) -> void:
	var sim = _get_sim()
	if sim == null:
		return
	sim.initial_condition = clampi(idx, 0, SHAPE_NAMES.size() - 1)
	_update_shape_visibility(sim.initial_condition)
	sim.reinit()  # positions regenerate with the new profile/geometry

func _update_shape_visibility(shape: int) -> void:
	for id in _shape_setting_rows.keys():
		var row: CSpinParam = _shape_setting_rows[id]
		row.visible = _shape_setting_is_visible(_shape_setting_meta[id], shape)
	_update_shape_dependent_controls(int(_arrangement_opt.get_value()) if _arrangement_opt != null else 0)


func _on_shuffle_seed() -> void:
	var sim = _get_sim()
	if sim == null:
		return
	var seed := randi() & 0x3fffffff
	if seed == 0:
		seed = 1
	sim.ic_seed = seed
	if _extra_spins.has("ic_seed"):
		(_extra_spins["ic_seed"] as CSpinParam).set_value_no_signal(float(seed))
	sim.reinit()


func _on_arrangement_selected(idx: int) -> void:
	var sim = _get_sim()
	if sim == null:
		return
	sim.initial_arrangement = clampi(idx, 0, ARRANGEMENT_NAMES.size() - 1)
	_update_shape_dependent_controls(sim.initial_arrangement)
	sim.reinit()


func _on_motion_selected(idx: int) -> void:
	var sim = _get_sim()
	if sim == null:
		return
	sim.initial_motion = clampi(idx, 0, MOTION_NAMES.size() - 1)
	sim.reinit()


## Recompute sim.particle_color_mode from the UI state. Encoding (matches
## compute/cassi_instancer.glsl header): low nibble = base mode (0 = Cassi
## mass gradient, 1 = velocity SPEED, 2 = Qi amplitude, 4 = two-axis q/ρ,
## 5 = field-phase, 6 = velocity DIRECTION), high nibble = feature flags
## (0x10 size-by-mass, 0x20 additive glow, 0x40 depth cue). Defaults (all
func _apply_particle_color_mode(sim: Node3D) -> void:
	var old_base: int = int(sim.particle_color_mode) & 0xF
	var base := 0
	if _rainbow_btn.button_pressed:
		match _color_src_opt.selected:
			0: base = 6
			1: base = 2
			2: base = 5
			3: base = 1
	var flags := 0
	if _vfx_size_btn.button_pressed: flags |= 0x10
	if _vfx_glow_btn.button_pressed: flags |= 0x20
	if _vfx_depth_btn.button_pressed: flags |= 0x40
	sim.particle_color_mode = base | flags
	var new_base: int = base & 0xF
	if old_base <= 3 and new_base > 3 or old_base > 3 and new_base <= 3:
		if sim.has_method("refresh_lut_format"):
			sim.refresh_lut_format()


func _on_legend_changed() -> void:
	var sim = _get_sim()
	if sim == null: return
	_update_scale_label()
	_auto_align_btn.set_pressed_no_signal(sim.auto_align_colors)
	_repaint_if_paused(sim)


func _on_fit_colors() -> void:
	var sim = _get_sim()
	if sim == null: return
	var base := int(sim.particle_color_mode) & 0xF
	if base >= 5:
		sim.auto_align_colors = false
		_auto_align_btn.set_pressed_no_signal(false)
		_scale_label.text = ""
		_repaint_if_paused(sim)
		return
	sim.auto_align_colors = false
	sim.rainbow_count = 1
	sim.color_shares = Vector3(1.0, 0.0, 0.0)
	sim.color_progress = 0
	sim.color_hue_offset = 0.0
	var qi_source: bool = _color_src_opt.selected == 1 or _color_src_opt.selected == 2
	if qi_source:
		# A stable, measured starting band on the BOUNDED q_coh channel
		# q_coh = ρ²/(ρ²+φ⁻²+ε²) ∈ [0,1). Calibrated 2026-08-15 by
		# diag_qcoh_band.gd (live config, 1M particles): q_coh median 0.0018
		# at t=0 climbing to ~0.99 by t=4 as the collapse saturates — so the
		# fixed band spans the full channel (0.005 → 0.95) and the white-hot
		# approach is OFF (no monotone march to white). The two legend
		# handles then make the final fit a direct visual operation; drag the
		# WHITE handle to re-enable the condensation glow.
		sim.qi_cycle = Vector2(0.005, 0.95)
		sim.qi_pinch = Vector2.ZERO
		sim.qi_approach = Vector2(1.0, 1.0)   # OFF
		sim.qi_approach_tracks_threshold = false
	else:
		sim.velocity_cycle = Vector2.ZERO
		sim.velocity_pinch = Vector2.ZERO
		sim.velocity_approach = Vector2.ZERO
	# The VFX flags ride particle_color_mode's high nibble — recompose so a
	# fit never silently clears size/glow/depth. Base comes from the option.
	_apply_particle_color_mode(sim)
	_sync_color_widgets(sim)
	_repaint_if_paused(sim)


func _on_falsify_toggled(on: bool) -> void:
	if _falsify_label != null:
		_falsify_label.visible = on
		_falsify_label.text = "" if not on else _falsify_label.text
	_falsify_accum = 0.0
	# The status panel's height changes with the 4-line meter — re-size it.
	call_deferred("_update_layout")


## A manual legend handle edit (drag / Fit) — repaint the visible instances
## so a paused sim reflects the new fit immediately.
func _on_legend_manual() -> void:
	_repaint_if_paused(_get_sim())


func _on_auto_align_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.auto_align_colors = on
	if sim.has_method("_repaint_instancer"):
		_repaint_if_paused(sim)


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


func _on_multirung_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	sim.multi_rung_seed = on
	sim.reinit()  # IC seeding is init-time (particle draw) — reinit applies
func _on_meshless_toggled(on: bool) -> void:
	var sim = _get_sim()
	if sim == null: return
	if bool(sim.gridless_physics) and not on:
		push_warning("[SimUI] meshless mode is mandatory for site-native physics")
		if _meshless_btn != null:
			_meshless_btn.set_pressed_no_signal(true)
		return
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
	sim.reinit()


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
		# Convert particle count to readable format
		var p_str = str(sim.N_particles)
		if sim.N_particles >= 1000000:
			p_str = "%.1fM" % (sim.N_particles / 1e6)
		elif sim.N_particles >= 1000:
			p_str = "%.0fk" % (sim.N_particles / 1e3)
		_info_label.text = "FPS: %.0f  |  N: %s  |  Step: %d" % [_fps_display, p_str, sim._step_count]
		_step_rate_label.text = "%.1f steps/s" % _step_rate_display
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
		if _observatory_status != null and sim.has_method("get_observatory_settings"):
			var observatory_settings: Dictionary = sim.call("get_observatory_settings")
			var observation_source := int(observatory_settings.get("observation_source", 0))
			if observation_source == 2:
				var observation_style := int(observatory_settings.get("style", 0))
				_refresh_observatory_status(
						sim, observation_source, observation_style, observation_style != 0)
	else:
		_info_label.text = "FPS: %.0f  |  N: --  |  Step: --" % _fps_display
		_step_rate_label.text = "-- steps/s"
		_diag_label.text = "(CassiSim not found)"
		_conn_label.text = "Connection: Disconnected"


func _get_sim() -> Node3D:
	return get_node_or_null("/root/Main/CassiSim")
