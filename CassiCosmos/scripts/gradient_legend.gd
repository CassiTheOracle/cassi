extends Control
## Live gradient legend: the active rainbow mapping (Qi coherence q or
## velocity |v|) rendered as a color strip with draggable anchor markers.
## The strip colors come from the SAME engine constants as the GPU
## instancer (cassi_sim.gd gradient_engine() — one composer), so the legend
## shows exactly what the particles show. Dragging a marker edits the sim's
## gradient exports live (no reinit; sim_ui repaints the paused view).
##
## Marker kinds (drag targets):
##   CYCLE_LO — cycle band low edge      (qi_cycle.x / velocity_cycle.x)
##   PINCH_LO / PINCH_HI — pinch band    (qi_pinch / velocity_pinch)
##   PINCH_ADD — shown when the pinch is off; dragging creates the band
##   CYCLE_HI — band top; for Qi ALSO moves the approach entry (linked)
##   GATE — the φ⁻² pink anchor          (qi_gate)
##   WHITE — the white-hot point         (qi_approach.y / velocity_approach.y)
## The velocity legend shows the RESOLVED band (auto → v_max) and dragging
## writes an explicit velocity_cycle (turns auto off).

signal gradient_changed

enum MK { CYCLE_LO, PINCH_LO, PINCH_HI, PINCH_ADD, CYCLE_HI, GATE, WHITE }

# Engine-array indices — MIRROR cassi_sim.gd's E_* consts (keep in sync;
# the strip colors are verified against the GPU mapping by the probe).
const E_PROG: int = 0
const E_REF: int = 1
const E_LO1: int = 2
const E_SLOPE1: int = 3
const E_LO2: int = 4
const E_SLOPE2: int = 5
const E_OFF2: int = 6
const E_LO3: int = 7
const E_SLOPE3: int = 8
const E_OFF3: int = 9
const E_HIC: int = 10
const E_SPAN: int = 11
const E_ALO: int = 12
const E_AHI: int = 13
const E_GATE: int = 14
const E_APPROACH_ON: int = 15
const E_HUE_OFF: int = 16

const STRIP_TOP: float = 6.0
const STRIP_H: float = 18.0
const MARK_R: float = 5.0
const HIT_R: float = 12.0
const LABEL_H: float = 14.0
const LOG_GUARD: float = 1e-9

var sim: Node = null
var qi_mode: bool = true          # true = Qi legend, false = velocity legend
var _engine: PackedFloat32Array = PackedFloat32Array()
var _drag_idx: int = -1
var _drag_kind: int = -1
var _markers: Array[Dictionary] = []


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(0, STRIP_TOP + STRIP_H + MARK_R * 2.0 + LABEL_H + 6.0)


func set_sim(s: Node, qi: bool) -> void:
	sim = s
	qi_mode = qi
	queue_redraw()


## Exposed for probing/tests: the legend's color at a given scalar value
## (the same evaluator the GPU instancer uses, fed the same engine).
func sample_color(q: float) -> Color:
	_refresh_engine()
	return _color_for_q(q)


## Exposed for probing/tests: current marker positions (name → q).
func marker_qs() -> Dictionary:
	_refresh_engine()
	_build_markers()
	var out := {}
	for m in _markers:
		out[m.name] = m.q
	return out


## Exposed for probing/tests + the drag path: set a marker by kind.
func set_marker_q(kind: int, q: float) -> void:
	_set_marker(kind, q)
	queue_redraw()


# ── engine + evaluator (mirrors compute/cassi_instancer.glsl) ─────────

func _refresh_engine() -> void:
	if sim != null and sim.has_method("gradient_engine"):
		_engine = sim.gradient_engine()


func _color_for_q(q: float) -> Color:
	if _engine.size() < 17 or _engine[E_SPAN] <= 0.0:
		return Color(0.2, 0.2, 0.25, 1.0)
	var e := _engine
	var lin: bool = e[E_PROG] > 0.5
	# per-segment progress (log: multiplicative physics; linear: plain)
	var f1: float = log(maxf((q + e[E_REF]) / (e[E_LO1] + e[E_REF]), LOG_GUARD)) if not lin else q - e[E_LO1]
	var f2: float = log(maxf((q + e[E_REF]) / (e[E_LO2] + e[E_REF]), LOG_GUARD)) if not lin else q - e[E_LO2]
	var f3: float = log(maxf((q + e[E_REF]) / (e[E_LO3] + e[E_REF]), LOG_GUARD)) if not lin else q - e[E_LO3]
	var h1: float = e[E_SLOPE1] * f1
	var h2: float = e[E_OFF2] + e[E_SLOPE2] * f2
	var h3: float = e[E_OFF3] + e[E_SLOPE3] * f3
	# segment masks; the LAST segment extends past hiC (growth saturates at
	# the span cap instead of dropping out — the legacy velocity top held)
	var a1: float = 1.0 if (e[E_LO1] <= q and q < e[E_LO2]) else 0.0
	var a2: float = 1.0 if (e[E_LO2] <= q and q < e[E_LO3]) else 0.0
	var a3: float = 1.0 if e[E_LO3] <= q else 0.0
	var hc: float = clampf(a1 * h1 + a2 * h2 + a3 * h3, 0.0, e[E_SPAN])
	var h_cyc: float = fposmod(hc + e[E_HUE_OFF], maxf(e[E_SPAN], 1.0))
	# approach band (count-invariant): violet 0.8 at a_lo → PINK 0.93
	# EXACTLY at the gate → red 1.0 at a_hi; lightness 0.5 → 1.0
	var p_g: float = clampf((q - e[E_ALO]) / maxf(e[E_GATE] - e[E_ALO], LOG_GUARD), 0.0, 1.0)
	var p_t: float = clampf((q - e[E_GATE]) / maxf(e[E_AHI] - e[E_GATE], LOG_GUARD), 0.0, 1.0)
	var p_a: float = clampf((q - e[E_ALO]) / maxf(e[E_AHI] - e[E_ALO], LOG_GUARD), 0.0, 1.0)
	var h_a: float = lerpf(lerpf(0.8, 0.93, p_g), lerpf(0.93, 1.0, p_t), 1.0 if q >= e[E_GATE] else 0.0)
	var l_a: float = 0.5 + 0.5 * p_a
	var in_a: float = e[E_APPROACH_ON] * (1.0 if q >= e[E_ALO] else 0.0)
	var h: float = lerpf(h_cyc, h_a, in_a)
	var l: float = lerpf(0.5, l_a, in_a)
	return _hsl_to_rgb(h, 1.0, l)


## IQ-form HSL→RGB — the exact shader formula (cassi_instancer.glsl
## hsl2rgb), so the legend matches the GPU to the last bit.
static func _hsl_to_rgb(h: float, s: float, l: float) -> Color:
	var x: float = fposmod(h * 6.0 + 0.0, 6.0) - 3.0
	var y: float = fposmod(h * 6.0 + 4.0, 6.0) - 3.0
	var z: float = fposmod(h * 6.0 + 2.0, 6.0) - 3.0
	var r: float = clampf(absf(x) - 1.0, 0.0, 1.0)
	var g: float = clampf(absf(y) - 1.0, 0.0, 1.0)
	var b: float = clampf(absf(z) - 1.0, 0.0, 1.0)
	var f: float = 1.0 - absf(2.0 * l - 1.0)
	return Color(l + s * (r - 0.5) * f, l + s * (g - 0.5) * f, l + s * (b - 0.5) * f, 1.0)


# ── scale + markers ────────────────────────────────────────────────────

func _q_scale_min() -> float:
	if qi_mode:
		return maxf(1e-7, e_lo1() * 0.02)
	return 0.0


func _q_scale_max() -> float:
	if _engine.size() < 17:
		return 1.0
	var hi_c: float = _engine[E_HIC]
	var a_hi: float = _engine[E_AHI]
	if qi_mode:
		return maxf(maxf(a_hi * 1.05, hi_c * 2.0), 1.0)
	return maxf(maxf(a_hi * 1.05, hi_c * 1.2), 10.0)


func e_lo1() -> float:
	return _engine[E_LO1] if _engine.size() >= 17 else 0.0


func _q_from_x(x: float) -> float:
	var w: float = maxf(size.x, 1.0)
	var qmin: float = _q_scale_min()
	var qmax: float = _q_scale_max()
	var t: float = clampf(x / w, 0.0, 1.0)
	if qi_mode:
		return qmin * pow(qmax / qmin, t)
	return qmin + (qmax - qmin) * t


func _x_from_q(q: float) -> float:
	var w: float = maxf(size.x, 1.0)
	var qmin: float = _q_scale_min()
	var qmax: float = _q_scale_max()
	var t: float
	if qi_mode:
		t = clampf(log(q / qmin) / log(qmax / qmin), 0.0, 1.0) if q > 0.0 else 0.0
	else:
		t = clampf((q - qmin) / maxf(qmax - qmin, 1e-9), 0.0, 1.0)
	return t * w


func _build_markers() -> void:
	_markers = []
	_refresh_engine()
	if sim == null or _engine.size() < 17:
		return
	var e := _engine
	var lo1: float = e[E_LO1]
	var lo2: float = e[E_LO2]
	var lo3: float = e[E_LO3]
	var hi_c: float = e[E_HIC]
	var gate: float = e[E_GATE]
	var a_hi: float = e[E_AHI]
	var a_on: bool = e[E_APPROACH_ON] > 0.5
	_markers.append(_mk("cycle lo", MK.CYCLE_LO, lo1))
	if lo2 < lo3:
		_markers.append(_mk("pinch lo", MK.PINCH_LO, lo2))
		_markers.append(_mk("pinch hi", MK.PINCH_HI, lo3))
	else:
		_markers.append(_mk("pinch +", MK.PINCH_ADD, sqrt(lo1 * hi_c)))
	_markers.append(_mk("band top", MK.CYCLE_HI, hi_c))
	if a_on:
		_markers.append(_mk("pink gate", MK.GATE, gate))
		_markers.append(_mk("white", MK.WHITE, a_hi))


func _mk(name: String, kind: int, q: float) -> Dictionary:
	return {"name": name, "kind": kind, "q": q}


func _set_marker(kind: int, q: float) -> void:
	if sim == null:
		return
	match kind:
		MK.CYCLE_LO:
			if qi_mode:
				sim.qi_cycle = Vector2(q, sim.qi_cycle.y)
			else:
				sim.velocity_cycle = Vector2(q, _engine[E_HIC])
		MK.CYCLE_HI:
			if qi_mode:
				sim.qi_cycle = Vector2(sim.qi_cycle.x, q)
				sim.qi_approach = Vector2(q, sim.qi_approach.y)  # linked: band top = approach entry
			else:
				sim.velocity_cycle = Vector2(sim.velocity_cycle.x, q)
		MK.PINCH_LO:
			var cur: Vector2 = sim.qi_pinch if qi_mode else sim.velocity_pinch
			var y: float = cur.y
			if y <= cur.x:
				y = q * 1.5   # enabling: create the band above the grab
			if qi_mode:
				sim.qi_pinch = Vector2(q, y)
			else:
				sim.velocity_pinch = Vector2(q, y)
		MK.PINCH_HI:
			if qi_mode:
				sim.qi_pinch = Vector2(sim.qi_pinch.x, q)
			else:
				sim.velocity_pinch = Vector2(sim.velocity_pinch.x, q)
		MK.PINCH_ADD:
			if qi_mode:
				sim.qi_pinch = Vector2(q, q * 1.5)
			else:
				sim.velocity_pinch = Vector2(q, q * 1.5)
		MK.GATE:
			sim.qi_gate = q
		MK.WHITE:
			if qi_mode:
				sim.qi_approach = Vector2(sim.qi_approach.x, q)
				sim.qi_approach_tracks_threshold = false
			else:
				sim.velocity_approach = Vector2(sim.velocity_approach.x, q)
	gradient_changed.emit()


# ── input + drawing ────────────────────────────────────────────────────

func _gui_input(event: InputEvent) -> void:
	if sim == null:
		return
	if event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT:
		var mb := event as InputEventMouseButton
		if mb.pressed:
			_build_markers()
			_drag_idx = _hit_marker(mb.position.x)
			_drag_kind = int(_markers[_drag_idx].kind) if _drag_idx >= 0 else -1
			if _drag_idx >= 0:
				accept_event()
		elif _drag_kind >= 0:
			_end_drag()
			accept_event()
	elif event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		if _drag_kind >= 0:
			_apply_drag_x(mm.position.x)
			accept_event()
		else:
			mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND if _hit_marker(mm.position.x) >= 0 else Control.CURSOR_ARROW


## Continue a drag after the pointer leaves this 54-pixel-high Control.
## Embedded-game input otherwise stops delivering _gui_input motion events
## as soon as the cursor crosses the strip edge.
func _input(event: InputEvent) -> void:
	if _drag_kind < 0:
		return
	if event is InputEventMouseMotion:
		var mm := event as InputEventMouseMotion
		var local_pos: Vector2 = get_global_transform_with_canvas().affine_inverse() * mm.global_position
		_apply_drag_x(local_pos.x)
		get_viewport().set_input_as_handled()
	elif event is InputEventMouseButton and event.button_index == MOUSE_BUTTON_LEFT and not event.pressed:
		_end_drag()
		get_viewport().set_input_as_handled()


func _apply_drag_x(x: float) -> void:
	if _drag_kind < 0:
		return
	_set_marker(_drag_kind, _q_from_x(clampf(x, 0.0, size.x)))
	queue_redraw()


func _end_drag() -> void:
	_drag_idx = -1
	_drag_kind = -1
	mouse_default_cursor_shape = Control.CURSOR_ARROW


func _hit_marker(x: float) -> int:
	var best: int = -1
	var best_dist: float = HIT_R + 1.0
	for i in range(_markers.size()):
		var mx: float = _x_from_q(_markers[i].q)
		var dist: float = absf(mx - x)
		if dist <= best_dist:
			best = i
			best_dist = dist
	return best


func _draw() -> void:
	if sim == null:
		_draw_placeholder("No simulation")
		return
	if int(sim.particle_color_mode) == 0:
		_draw_placeholder("Rainbow off — enable Rainbow to show the Qi scale")
		return
	_refresh_engine()
	_build_markers()
	if _engine.size() < 17:
		_draw_placeholder("…")
		return
	# the strip: one pixel column per x, colors from the engine evaluator
	for x in range(0, int(size.x)):
		var c: Color = _color_for_q(_q_from_x(float(x) + 0.5))
		draw_rect(Rect2(float(x), STRIP_TOP, 1.0, STRIP_H), c)
	draw_rect(Rect2(0.0, STRIP_TOP, size.x, STRIP_H), Color(1, 1, 1, 0.25), false, 1.0)
	# markers: line through the strip + grab handle + q label
	var font: Font = ThemeDB.fallback_font
	for m in _markers:
		var mx: float = _x_from_q(m.q)
		draw_line(Vector2(mx, STRIP_TOP), Vector2(mx, STRIP_TOP + STRIP_H), Color(1, 1, 1, 0.7), 1.0)
		draw_circle(Vector2(mx, STRIP_TOP + STRIP_H + MARK_R), MARK_R, Color(1, 1, 1))
		var label: String = _fmt(m.q)
		var tw: float = font.get_string_size(label).x
		draw_string(font, Vector2(clampf(mx - tw * 0.5, 0.0, maxf(size.x - tw, 0.0)), STRIP_TOP + STRIP_H + MARK_R * 2.0 + LABEL_H), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.95, 0.97, 1.0))


func _draw_placeholder(text: String) -> void:
	draw_rect(Rect2(0.0, STRIP_TOP, size.x, STRIP_H), Color(0.12, 0.13, 0.18, 1.0))
	var font: Font = ThemeDB.fallback_font
	var tw: float = font.get_string_size(text).x
	draw_string(font, Vector2(maxf((size.x - tw) * 0.5, 0.0), STRIP_TOP + STRIP_H * 0.5 + 4.0), text, HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color(0.6, 0.65, 0.75))


func _fmt(v: float) -> String:
	if v <= 0.0:
		return "0"
	if v >= 100.0:
		return str(int(v))
	if v >= 0.01:
		return "%.4f" % v
	if v >= 0.0001:
		return "%.6f" % v
	if v >= 1e-6:
		return "%.7f" % v
	return str(v)
