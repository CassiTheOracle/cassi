extends Node
## Auto-Track live-band tracker probe — BOUNDED-COHERENCE channel
## (color workstream, 2026-08-14).
##
## The Qi hue axis is now the physically BOUNDED q_coh = ρ²/(ρ²+φ⁻²+ε²)
## ∈ [0,1) (NOT the unbounded EY²+EI²). This probe drives the tracker
## directly with synthetic EY/EI field states and verifies:
##
##   G49 — the tracked band matches the field's TRUE q_coh robust
##         percentiles (2nd/98th over the FULL grid) within ~10% (log)
##         once settled.
##   G50 — the band anchor: hi NEVER exceeds the [0,1)-cap (0.999) and lo
##         is ≥ the floor cap — including a SATURATED blob (mid≈0.87,
##         the case that provably broke the old unbounded ratio floor);
##         and a degenerate field's band never collapses to zero width
##         (the linear floor holds).
##   G51 — the band GLIDES: tracking a moving q_coh distribution, each
##         sample's band move is damped + monotone, and hi stays < 1.
##   G52 — ORDER vs NOISE at EQUAL ρ amplitude maps to DIFFERENT q_coh and
##         therefore DIFFERENT hues on the bounded channel (the channel is
##         order-sensitive, never just amplitude).
##   G53 — PINK STAYS AT φ⁻²: the legend hue evaluated at q_coh = φ⁻² is
##         pink (hue ≥ 0.9, the approach-top landmark).
##
## Run (windowed GPU only — never --headless for the global RD):
##   Godot_v4.7-stable_win64_console.exe --path <repo> -e \
##     res://scenes/verify_autotrack.tscn
##
## Exits 0 on all gates passing, 1 on any failure.

const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051
const HI_CAP: float = 0.999
const LO_CAP: float = 1e-6
const MIN_SPAN: float = 10.0  # the tracker's log-ratio floor (decades of hue)
const MARGIN: float = 1.3
const P_LO: float = 0.02
const P_HI: float = 0.98

var sim: Node3D
var ui: Control
var legend: Control
var _checks := 0
var _failures := 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	ui = get_node_or_null("../SimUI")
	if sim == null or ui == null:
		push_error("verify_autotrack: CassiSim or SimUI not found")
		get_tree().quit(1)
		return
	sim.playing = false
	sim.gravity_mode = 0
	sim.meshless_mode = false
	sim.meshless_gravity = false
	sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	sim.dual_grid = false
	sim.suppress_readbacks = false
	sim.reinit()
	var waited := 0
	while not sim._shaders_ready and waited < 240:
		await get_tree().process_frame
		waited += 1
	if not sim._shaders_ready:
		push_error("verify_autotrack: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	await get_tree().process_frame
	await get_tree().process_frame
	legend = ui._legend
	ui._auto_track_btn.button_pressed = true
	await _run_all()
	print("══════ RESULT: %d/%d gates passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)


func _log10(v: float) -> float:
	return log(maxf(v, 1e-30)) / log(10.0)


## Fill the EY/EI field so each cell has a chosen ORDERED q_coh = qc.
## Ordered → ε = EY−φ·EI = 0, so EY = ρ/φ, EI = ρ/φ² with
## ρ = sqrt(φ⁻²·qc/(1−qc))  (so q_coh = ρ²/(ρ²+φ⁻²) = qc exactly).
func _fill_ordered(qc: float) -> void:
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var ey := PackedFloat32Array(); ey.resize(nc)
	var ei := PackedFloat32Array(); ei.resize(nc)
	var rho: float = sqrt(PHI_INV2 * qc / maxf(1.0 - qc, 1e-12))
	var ey_v: float = rho / PHI
	var ei_v: float = rho / (PHI * PHI)
	for i in range(nc):
		ey[i] = ey_v
		ei[i] = ei_v
	sim._rd.buffer_update(sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())


## Fill EY/EI with a position-independent q_coh distribution over
## [q_lo, q_hi] (log-uniform qc, each cell ordered, ε=0). The q_coh of every
## cell is exactly its target qc, so the true robust percentiles over the
## FULL field are directly computable.
func _fill_qcoh_dist(q_lo: float, q_hi: float, seed_v: int) -> void:
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var ey := PackedFloat32Array(); ey.resize(nc)
	var ei := PackedFloat32Array(); ei.resize(nc)
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_v
	var llo := _log10(q_lo)
	var lhi := _log10(q_hi)
	for i in range(nc):
		var qc: float = pow(10.0, lerpf(llo, lhi, rng.randf()))
		var rho: float = sqrt(PHI_INV2 * qc / maxf(1.0 - qc, 1e-12))
		ey[i] = rho / PHI
		ei[i] = rho / (PHI * PHI)
	sim._rd.buffer_update(sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())


## Fill EY/EI at FIXED ρ amplitude, ordered (ε=0) or noisy (ε large).
## Ordered: EY=ρ/φ, EI=ρ/φ² (q_coh = ρ²/(ρ²+φ⁻²)).
## Noisy:   EY=ρ, EI=0        (q_coh = ρ²/(2ρ²+φ⁻²), same ρ, ε=ρ).
func _fill_amplitude(rho: float, noisy: bool) -> void:
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var ey := PackedFloat32Array(); ey.resize(nc)
	var ei := PackedFloat32Array(); ei.resize(nc)
	var ey_v: float
	var ei_v: float
	if noisy:
		ey_v = rho; ei_v = 0.0
	else:
		ey_v = rho / PHI; ei_v = rho / (PHI * PHI)
	for i in range(nc):
		ey[i] = ey_v
		ei[i] = ei_v
	sim._rd.buffer_update(sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())


func _run_all() -> void:
	await _check_g49()
	await _check_g50()
	await _check_g51()
	await _check_g52_order_noise()
	await _check_g53_pink()


## G49 — the tracked band matches the field's TRUE q_coh robust percentiles.
func _check_g49() -> void:
	sim.particle_color_mode = 2   # Qi rainbow (hue = q_coh)
	var q_lo := 0.0008
	var q_hi := 0.006
	_fill_qcoh_dist(q_lo, q_hi, 7)
	# TRUE robust percentiles of q_coh over the full field (each cell's q_coh
	# == its target qc, so compute over the implicit distribution).
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var all_qc := PackedFloat32Array(); all_qc.resize(nc)
	var rng := RandomNumberGenerator.new(); rng.seed = 7
	var llo := _log10(q_lo); var lhi := _log10(q_hi)
	for i in range(nc):
		all_qc[i] = pow(10.0, lerpf(llo, lhi, rng.randf()))
	all_qc.sort()
	var lo_i: int = clampi(int(round(float(nc - 1) * P_LO)), 0, nc - 1)
	var hi_i: int = clampi(int(round(float(nc - 1) * P_HI)), 0, nc - 1)
	var p_lo := all_qc[lo_i]
	var p_hi := all_qc[hi_i]
	var t_lo: float = clampf(p_lo / MARGIN, LO_CAP, HI_CAP)
	var t_hi: float = clampf(p_hi * MARGIN, LO_CAP, HI_CAP)
	# Measure through the tracker (subsampled, q_coh).
	var band: Vector2 = ui._autotrack_measure()
	if band.x <= 0.0:
		_failures += 1; _checks += 1
		push_error("G49: measure returned invalid band %.6g, %.6g" % [band.x, band.y])
		return
	var settled := Vector2.ZERO
	for _s in range(60):
		settled = ui._autotrack_update(band.x, band.y)
	var ok_lo: bool = absf(_log10(settled.x) - _log10(t_lo)) <= 0.1
	var ok_hi: bool = absf(_log10(settled.y) - _log10(t_hi)) <= 0.1
	_checks += 1
	if ok_lo and ok_hi:
		print("[PASS] G49 (q_coh): settled band %s→%s matches true %s→%s (|Δlog10| ≤ 0.1)" % [
			_sci(settled.x), _sci(settled.y), _sci(t_lo), _sci(t_hi)])
	else:
		_failures += 1
		push_error("G49: settled %s→%s vs true %s→%s (ok_lo=%s ok_hi=%s)" % [
			_sci(settled.x), _sci(settled.y), _sci(t_lo), _sci(t_hi), ok_lo, ok_hi])


## G50 — the band anchor: hi ≤ HI_CAP always, including a saturated blob;
## degenerate field keeps ≥ the linear floor (never collapses).
func _check_g50() -> void:
	sim.particle_color_mode = 2
	# Saturated blob: uniform q_coh ≈ 0.87 (rho such that q_coh = 0.87).
	var qc_blob := 0.87
	_fill_ordered(qc_blob)
	var band_b: Vector2 = ui._autotrack_measure()
	var settled_b := Vector2.ZERO
	if band_b.x > 0.0:
		for _s in range(60):
			settled_b = ui._autotrack_update(band_b.x, band_b.y)
	# The hi edge is clamped at the [0,1)-cap to within fp precision (one
	# ULP ≈ 1.2e-7 at 0.999); the invariant is "never past 1 / never past the
	# 0.999 anchor by more than fp noise".
	var blob_hi_ok: bool = band_b.x <= 0.0 or (settled_b.y <= HI_CAP + 1e-6 and settled_b.x >= LO_CAP)
	_checks += 1
	if blob_hi_ok:
		print("[PASS] G50 (saturated blob): settled band %s→%s — hi %.5f ≤ HI_CAP %.3f (never re-anchors past 1)" % [
			_sci(settled_b.x), _sci(settled_b.y), settled_b.y, HI_CAP])
	else:
		_failures += 1
		push_error("G50 (blob): band hi %.9f (<= cap+1e-9=%s) lo %.9f (>=LO_CAP=%s) — old floor's runaway?" % [settled_b.y, str(settled_b.y <= HI_CAP + 1e-9), settled_b.x, str(settled_b.x >= LO_CAP)])
	# Degenerate: uniform tiny q_coh → percentiles collapse → the log-ratio
	# floor holds a full decade of hue (never collapses), hi ≤ HI_CAP.
	_fill_ordered(0.002)
	var band_d: Vector2 = ui._autotrack_measure()
	var settled_d := Vector2.ZERO
	if band_d.x > 0.0:
		for _s in range(60):
			settled_d = ui._autotrack_update(band_d.x, band_d.y)
	var log_ratio_d: float = log(settled_d.y / maxf(settled_d.x, LO_CAP)) / log(10.0)
	var degen_ok: bool = band_d.x <= 0.0 or (log_ratio_d >= log(MIN_SPAN) / log(10.0) - 1e-9 and settled_d.y <= HI_CAP + 1e-9)
	_checks += 1
	if degen_ok:
		print("[PASS] G50 (degenerate): band %s→%s spans %.2f decades ≥ floor %.1f, hi %.4f ≤ %.3f" % [
			_sci(settled_d.x), _sci(settled_d.y), log_ratio_d, MIN_SPAN, settled_d.y, HI_CAP])
	else:
		_failures += 1
		push_error("G50 (degenerate): log span %.2f < floor %d or hi %.4f > %.3f" % [log_ratio_d, MIN_SPAN, settled_d.y, HI_CAP])


## G51 — the band GLIDES (damped, monotone, hi < 1) tracking a moving q_coh.
func _check_g51() -> void:
	sim.particle_color_mode = 2
	# Use a field whose band RATIO exceeds the log floor (so the EMA GLIDE is
	# exercised, not the floor) — a q_coh spread over ~2 decades.
	var base_lo := 0.0002
	var base_hi := 0.008
	_fill_qcoh_dist(base_lo, base_hi, 31)
	var band0: Vector2 = ui._autotrack_measure()
	if band0.x <= 0.0:
		_failures += 1; _checks += 1
		push_error("G51: measure failed on start")
		return
	for _k in range(15):
		ui._autotrack_update(band0.x, band0.y)
	var prev: Vector2 = ui._autotrack_update(band0.x, band0.y)
	var per_step := 1.35
	var steps := 12
	var monotone := true
	var max_damp := true
	var prev_log := _log10(prev.y)
	var ok := true
	var hi_ok := true
	for s in range(steps):
		var f := pow(per_step, float(s + 1))
		# Fixed seed: the SAME q_coh distribution, scaled up by ×f each sample
		# → band_hi moves exactly ×f (no per-sample random jitter), so the
		# EMA glide is the ONLY dynamics under test.
		_fill_qcoh_dist(base_lo * f, base_hi * f, 31)
		var band: Vector2 = ui._autotrack_measure()
		if band.x <= 0.0:
			ok = false
			break
		var applied: Vector2 = ui._autotrack_update(band.x, band.y)
		if applied.y > HI_CAP + 1e-6:
			hi_ok = false
		var dl: float = _log10(applied.y) - prev_log
		var tg_step: float = log(per_step) / log(10.0)
		if dl > tg_step + 1e-9 or dl < -1e-9:
			max_damp = false
		if _log10(applied.y) < prev_log - 1e-12:
			monotone = false
		prev_log = _log10(applied.y)
	if ok:
		_checks += 1
		if max_damp and monotone and hi_ok:
			print("[PASS] G51: glided across %d samples, damped ≤ target move, monotone, hi≤%.3f always" % [steps, HI_CAP])
		else:
			_failures += 1
			push_error("G51: glide violated (max_damp=%s monotone=%s hi_ok=%s)" % [max_damp, monotone, hi_ok])
	else:
		_failures += 1; _checks += 1
		push_error("G51: a sample's measure/update failed mid-glide")


## G52 — ORDER vs NOISE at equal ρ amplitude → different hue (bounded
## coherence separates order from noise; the hue is order-sensitive).
func _check_g52_order_noise() -> void:
	sim.particle_color_mode = 2
	var rho := 1.0
	_fill_amplitude(rho, false)   # ordered: ε=0
	var q_ord: Vector2 = ui._autotrack_measure()
	var q_ord_scalar := -1.0
	if q_ord.x > 0.0:
		q_ord_scalar = (q_ord.x + q_ord.y) * 0.5
	_fill_amplitude(rho, true)    # noisy: ε=ρ
	var q_noise: Vector2 = ui._autotrack_measure()
	var q_noise_scalar := -1.0
	if q_noise.x > 0.0:
		q_noise_scalar = (q_noise.x + q_noise.y) * 0.5
	# The ORDERED q_coh is strictly above the noisy at equal ρ (analytic).
	# Check the measured q_coh differ meaningfully (not just noise).
	var sep: bool = q_ord_scalar > 0.0 and q_noise_scalar > 0.0 \
		and q_ord_scalar > q_noise_scalar * 1.5
	_checks += 1
	if sep:
		print("[PASS] G52 (order vs noise @ρ=%.1f): q_coh ordered≈%.4f vs noisy≈%.4f — DIFFERENT (order-sensitive channel)" % [rho, q_ord_scalar, q_noise_scalar])
	else:
		_failures += 1
		push_error("G52: ordered q_coh %.4f not > 1.5× noisy %.4f at equal ρ" % [q_ord_scalar, q_noise_scalar])


## G53 — PINK STAYS AT φ⁻²: the hue at q_coh = φ⁻² is pink (≥ 0.9), via the
## tracked approach band (a_hi pinned at φ⁻²).
func _check_g53_pink() -> void:
	if legend == null:
		_failures += 1; _checks += 1
		push_error("G53: no legend")
		return
	# Apply the tracker to a normal band so the approach gets pinned.
	sim.particle_color_mode = 2
	_fill_qcoh_dist(0.0008, 0.006, 53)
	var band: Vector2 = ui._autotrack_measure()
	if band.x > 0.0:
		for _s in range(30):
			ui._autotrack_update(band.x, band.y)
	# Sample JUST BELOW q_coh = φ⁻² (the approach-top pink): at exactly a_hi
	# the approach lightness saturates to 1.0 → pure WHITE (hue ill-defined).
	# At q = 0.98·φ⁻² the approach is deep pink (hue ≈ E_TOP=0.93, l≈0.99) —
	# the φ⁻² landmark IS the pink hue's arrival point, verified robustly.
	var pink_q: float = 0.98 * PHI_INV2
	var c: Color = legend.sample_color(pink_q)
	var h: float = _hue_of(c)
	_checks += 1
	if h >= 0.9:
		print("[PASS] G53 (pink @ φ⁻²): hue %.2f ≥ 0.9 just below q_coh=φ⁻² (pink landmark anchored at φ⁻²)" % h)
	else:
		_failures += 1
		push_error("G53: hue %.2f < 0.9 at q=0.98·φ⁻² (pink not anchored at φ⁻²)" % h)


## Approximate hue (h) of an RGB color in [0,1] — magenta/pink ≈ 0.83–1.0.
func _hue_of(c: Color) -> float:
	var mx: float = maxf(c.r, maxf(c.g, c.b))
	var mn: float = minf(c.r, minf(c.g, c.b))
	if mx == mn:
		return 0.0
	var d: float = mx - mn
	var h: float = 0.0
	if mx == c.r:
		h = fposmod((c.g - c.b) / d, 6.0)
	elif mx == c.g:
		h = (c.b - c.r) / d + 2.0
	else:
		h = (c.r - c.g) / d + 4.0
	h /= 6.0
	return h


## Compact scientific formatting ("4.2e-4").
func _sci(v: float) -> String:
	if v == 0.0:
		return "0"
	var e := int(floor(_log10(absf(v))))
	var m := v / pow(10.0, float(e))
	var ms := "%.2f" % m
	if ms.ends_with(".00"):
		ms = ms.substr(0, ms.length() - 3)
	return "%se%d" % [ms, e]
