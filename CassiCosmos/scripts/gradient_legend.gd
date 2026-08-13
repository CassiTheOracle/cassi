extends Control
## Live color-scale legend. Choose Qi or velocity, click Fit scale for a
## sensible starting range, then drag LOW and HIGH until the particles occupy
## the colors you want. WHITE is the fixed physical upper limit.
##
## The strip uses the same composed engine and evaluator as the GPU instancer,
## so it is a visual readout of the particle colors rather than a second map.

signal gradient_changed

enum MK { LOW, HIGH, FIXED_WHITE }

# Engine-array indices — mirror cassi_sim.gd's E_* constants.
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
const E_TOP: int = 14   # approach hue at the white point (red 1.0 — pink before white)
const E_APPROACH_ON: int = 15
const E_HUE_OFF: int = 16

const STRIP_TOP: float = 8.0
const STRIP_H: float = 20.0
const MARK_R: float = 6.0
const HIT_R: float = 14.0
const LABEL_H: float = 14.0
const LOG_GUARD: float = 1e-9

var sim: Node = null
var qi_mode: bool = true
var _engine: PackedFloat32Array = PackedFloat32Array()
var _drag_idx: int = -1
var _drag_kind: int = -1
var _markers: Array[Dictionary] = []


func _init() -> void:
	mouse_filter = Control.MOUSE_FILTER_STOP
	custom_minimum_size = Vector2(0, STRIP_TOP + STRIP_H + MARK_R * 2.0 + LABEL_H + 8.0)


func set_sim(s: Node, qi: bool) -> void:
	sim = s
	qi_mode = qi
	queue_redraw()


## Exposed for probes/tests: the legend's color at a scalar value.
func sample_color(q: float) -> Color:
	_refresh_engine()
	return _color_for_q(q)


## Exposed for probes/tests: the two editable handles and the fixed white point.
func marker_qs() -> Dictionary:
	_refresh_engine()
	_build_markers()
	var out := {}
	for m in _markers:
		out[m.name.to_lower()] = m.q
	return out


## Exposed for probes/tests and the drag path.
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
	# Per-segment progress. The engine still owns the optional pinch split;
	# the simple UI exposes only the outer scale handles.
	var f1: float = log(maxf((q + e[E_REF]) / (e[E_LO1] + e[E_REF]), LOG_GUARD)) if not lin else q - e[E_LO1]
	var f2: float = log(maxf((q + e[E_REF]) / (e[E_LO2] + e[E_REF]), LOG_GUARD)) if not lin else q - e[E_LO2]
	var f3: float = log(maxf((q + e[E_REF]) / (e[E_LO3] + e[E_REF]), LOG_GUARD)) if not lin else q - e[E_LO3]
	var h1: float = e[E_SLOPE1] * f1
	var h2: float = e[E_OFF2] + e[E_SLOPE2] * f2
	var h3: float = e[E_OFF3] + e[E_SLOPE3] * f3
	var a1: float = 1.0 if (e[E_LO1] <= q and q < e[E_LO2]) else 0.0
	var a2: float = 1.0 if (e[E_LO2] <= q and q < e[E_LO3]) else 0.0
	var a3: float = 1.0 if e[E_LO3] <= q else 0.0
	var hc: float = clampf(a1 * h1 + a2 * h2 + a3 * h3, 0.0, e[E_SPAN])
	var h_cyc: float = fposmod(hc + e[E_HUE_OFF], maxf(e[E_SPAN], 1.0))
	# Count-invariant approach: violet at entry, hue ramping to red at the
	# white point — pink (~0.93) falls naturally at pA ≈ 0.65, before white.
	var p_a: float = clampf((q - e[E_ALO]) / maxf(e[E_AHI] - e[E_ALO], LOG_GUARD), 0.0, 1.0)
	var h_a: float = lerpf(0.8, e[E_TOP], p_a)
	var l_a: float = 0.5 + 0.5 * p_a
	var in_a: float = e[E_APPROACH_ON] * (1.0 if q >= e[E_ALO] else 0.0)
	var h: float = lerpf(h_cyc, h_a, in_a)
	var l: float = lerpf(0.5, l_a, in_a)
	return _hsl_to_rgb(h, 1.0, l)


## IQ-form HSL→RGB — the exact shader formula.
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
	_markers.append(_mk("LOW", MK.LOW, _engine[E_LO1], true))
	_markers.append(_mk("HIGH", MK.HIGH, _engine[E_HIC], true))
	if _engine[E_APPROACH_ON] > 0.5:
		_markers.append(_mk("WHITE", MK.FIXED_WHITE, _engine[E_AHI], false))


func _mk(name: String, kind: int, q: float, draggable: bool) -> Dictionary:
	return {"name": name, "kind": kind, "q": q, "draggable": draggable}


func _set_marker(kind: int, q: float) -> void:
	if sim == null:
		return
	_refresh_engine()
	if _engine.size() < 17:
		return
	var low: float = _engine[E_LO1]
	var high: float = _engine[E_HIC]
	var white: float = _engine[E_AHI]
	var has_white: bool = _engine[E_APPROACH_ON] > 0.5 and white > low
	if kind == MK.LOW:
		q = clampf(q, _q_scale_min(), maxf(high * 0.999, _q_scale_min() + 1e-7))
		if qi_mode:
			sim.qi_cycle = Vector2(q, sim.qi_cycle.y)
		else:
			sim.velocity_cycle = Vector2(q, high)
	elif kind == MK.HIGH:
		var upper: float = white * 0.999 if has_white else _q_scale_max()
		q = clampf(q, low * 1.001, maxf(upper, low * 1.001))
		if qi_mode:
			sim.qi_cycle = Vector2(sim.qi_cycle.x, q)
			sim.qi_approach = Vector2(q, sim.qi_approach.y)
		else:
			sim.velocity_cycle = Vector2(sim.velocity_cycle.x, q)
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


## Continue a drag after the pointer leaves the short legend control.
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
		if not _markers[i].draggable:
			continue
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
		_draw_placeholder("Rainbow off — enable Rainbow to show the scale")
		return
	_refresh_engine()
	_build_markers()
	if _engine.size() < 17:
		_draw_placeholder("Waiting for color scale")
		return
	for x in range(0, int(size.x)):
		var c: Color = _color_for_q(_q_from_x(float(x) + 0.5))
		draw_rect(Rect2(float(x), STRIP_TOP, 1.0, STRIP_H), c)
	draw_rect(Rect2(0.0, STRIP_TOP, size.x, STRIP_H), Color(1, 1, 1, 0.35), false, 1.0)
	var font: Font = ThemeDB.fallback_font
	for m in _markers:
		var mx: float = _x_from_q(m.q)
		var draggable: bool = m.draggable
		var mark_color := Color(1.0, 1.0, 1.0, 1.0) if draggable else Color(0.7, 0.8, 0.95, 0.9)
		var radius: float = MARK_R if draggable else MARK_R - 1.0
		draw_line(Vector2(mx, STRIP_TOP), Vector2(mx, STRIP_TOP + STRIP_H), mark_color, 1.0)
		draw_circle(Vector2(mx, STRIP_TOP + STRIP_H + MARK_R), radius, mark_color)
		var label: String = "%s %s" % [m.name, _fmt(m.q)]
		var tw: float = font.get_string_size(label).x
		var lx: float = clampf(mx - tw * 0.5, 0.0, maxf(size.x - tw, 0.0))
		var ly: float = STRIP_TOP + STRIP_H + MARK_R * 2.0 + LABEL_H
		draw_string(font, Vector2(lx + 1.0, ly + 1.0), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(0.0, 0.0, 0.0, 0.6))
		draw_string(font, Vector2(lx, ly), label, HORIZONTAL_ALIGNMENT_LEFT, -1, 12, Color(1.0, 1.0, 1.0, 0.95))


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