extends Node
## Auto-Track live-band tracker probe (color-autotrack workstream, 2026-08-14).
##
## Instantiates the real CassiSim + SimUI (root named `Main` so the UI's
## _get_sim() resolves), then drives the Auto-Track tracker directly with
## synthetic field states and verifies the three gates:
##
##   G49 — the tracked band matches the field's TRUE robust percentiles
##         (2nd/98th over the FULL grid) within ~10% (log) once settled,
##         for BOTH the Qi quantity (q = EY²+EI²) and the two-axis
##         quantity (ρ = EY+EI).
##   G50 — the band span never drops below the min-span floor (a static /
##         degenerate field still shows a full decade of hue) and never
##         exceeds the full field range.
##   G51 — the band GLIDES: tracking a moving distribution, each sample's
##         band move is damped (never jumps further than the target moved),
##         monotone in response, and bounded by the EMA limit — no
##         per-sample teleport.
##
## Run (windowed GPU only — never --headless for the global RD):
##   Godot_v4.7-stable_win64_console.exe --path <repo> -e \
##     res://scenes/verify_autotrack.tscn
##
## Exits 0 on all gates passing, 1 on any failure.

var sim: Node3D
var ui: Control
var _checks := 0
var _failures := 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	ui = get_node_or_null("../SimUI")
	if sim == null or ui == null:
		push_error("verify_autotrack: CassiSim or SimUI not found")
		get_tree().quit(1)
		return
	# Pinned battery config: single-lattice CUBE grid field, paused.
	sim.playing = false
	sim.gravity_mode = 0
	sim.meshless_mode = false
	sim.meshless_gravity = false
	sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	sim.dual_grid = false
	sim.suppress_readbacks = false
	sim.reinit()
	# Wait for the shader import race to settle (mirrors verify_river_isotropy).
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
	# Enable Auto-Track (the UI button -> clears the sim GPU auto-aligner so
	# it doesn't fight over qi_cycle; the probe then drives the tracker core
	# directly for determinism).
	ui._auto_track_btn.button_pressed = true
	await _run_all()
	print("══════ RESULT: %d/%d gates passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)


func _log10(v: float) -> float:
	return log(maxf(v, 1e-30)) / log(10.0)


## Compute the robust 2nd/98th percentiles of a full value array (CPU-side).
func _robust_percentiles(vals: PackedFloat32Array) -> Vector2:
	var clean := PackedFloat32Array()
	for v in vals:
		if v > 0.0 and is_finite(v):
			clean.append(v)
	if clean.size() < 4:
		return Vector2(-1.0, -1.0)
	clean.sort()
	var lo_i: int = clampi(int(round(float(clean.size() - 1) * 0.02)), 0, clean.size() - 1)
	var hi_i: int = clampi(int(round(float(clean.size() - 1) * 0.98)), 0, clean.size() - 1)
	return Vector2(clean[lo_i], clean[hi_i])


func _fill_field_q(q_lo: float, q_hi: float, seed_v: int) -> void:
	# Fill the whole _field_q grid log-uniform over [q_lo, q_hi] (a
	# position-independent value distribution, so the central-slab subsample
	# is representative of the whole field).
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var arr := PackedFloat32Array(); arr.resize(nc)
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_v
	var llo := _log10(q_lo)
	var lhi := _log10(q_hi)
	for i in range(nc):
		arr[i] = pow(10.0, lerpf(llo, lhi, rng.randf()))
	sim._rd.buffer_update(sim._field_q, 0, arr.size() * 4, arr.to_byte_array())


## G49 — the tracked band matches the field's TRUE robust percentiles.
func _check_g49() -> void:
	# Qi quantity: q = EY²+EI² (mode 2).
	sim.particle_color_mode = 2
	var q_lo := 2.0e-4
	var q_hi := 5.0e-3
	_fill_field_q(q_lo, q_hi, 7)
	# TRUE robust percentiles over the FULL field.
	var full := PackedFloat32Array(); full.resize(sim.grid_N * sim.grid_N * sim.grid_N)
	var fd: PackedByteArray = sim._rd.buffer_get_data(sim._field_q, 0, full.size() * 4)
	if fd.size() < full.size() * 4:
		_failures += 1; _checks += 1
		push_error("G49: field readback failed (fd=%d want=%d)" % [fd.size(), full.size() * 4])
		return
	full = fd.to_float32_array()
	var p := _robust_percentiles(full)
	var vmin := INF
	var vmax := -INF
	for v in full:
		if v <= 0.0 or not is_finite(v):
			continue
		vmin = minf(vmin, v); vmax = maxf(vmax, v)
	# Target band with margin + the SAME strict [vmin, vmax] clamp
	# _autotrack_measure applies.
	var t_lo: float = clampf(p.x / 1.3, vmin, vmax)
	var t_hi: float = clampf(p.y * 1.3, vmin, vmax)
	# Measure through the tracker (subsampled central slab).
	var band: Vector2 = ui._autotrack_measure()
	if band.x <= 0.0:
		_failures += 1; _checks += 1
		push_error("G49 (Qi): measure returned invalid band %.6g, %.6g" % [band.x, band.y])
		return
	# Settle the EMA (repeated glide toward the measured target) and confirm
	# the tracked qi_cycle converges to it.
	var settled := Vector2.ZERO
	for _s in range(60):
		settled = ui._autotrack_update(band.x, band.y)
	# Within ~10% (log) of the TRUE full-field robust band.
	var ok_lo: bool = absf(_log10(settled.x) - _log10(t_lo)) <= 0.1
	var ok_hi: bool = absf(_log10(settled.y) - _log10(t_hi)) <= 0.1
	_checks += 1
	if ok_lo and ok_hi:
		print("[PASS] G49 (Qi q=EY²+EI²): settled band %s → %s matches true %s → %s (|Δlog10| ≤ 0.1)" % [
			_sci(settled.x), _sci(settled.y), _sci(t_lo), _sci(t_hi)])
	else:
		_failures += 1
		push_error("G49 (Qi): settled band %s → %s vs true %s → %s (ok_lo=%s ok_hi=%s)" % [
			_sci(settled.x), _sci(settled.y), _sci(t_lo), _sci(t_hi), ok_lo, ok_hi])

	# Two-axis quantity: ρ = EY+EI (mode 4). Fill EY/EI ramps.
	sim.particle_color_mode = 4
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var ey := PackedFloat32Array(); ey.resize(nc)
	var ei := PackedFloat32Array(); ei.resize(nc)
	var rng := RandomNumberGenerator.new()
	rng.seed = 11
	for i in range(nc):
		ey[i] = 0.05 + rng.randf() * 0.9   # EY ∈ [0.05, 0.95]
		ei[i] = 0.05 + rng.randf() * 0.5   # EI ∈ [0.05, 0.55]
	sim._rd.buffer_update(sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())
	var rho := PackedFloat32Array(); rho.resize(nc)
	for i in range(nc):
		rho[i] = ey[i] + ei[i]   # ρ = EY+EI
	var pr := _robust_percentiles(rho)
	var rmin := INF
	var rmax := -INF
	for v in rho:
		if v <= 0.0 or not is_finite(v):
			continue
		rmin = minf(rmin, v); rmax = maxf(rmax, v)
	var r_lo: float = clampf(pr.x / 1.3, rmin, rmax)
	var r_hi: float = clampf(pr.y * 1.3, rmin, rmax)
	var band_r: Vector2 = ui._autotrack_measure()
	_checks += 1
	if band_r.x > 0.0 \
			and absf(_log10(band_r.x) - _log10(r_lo)) <= 0.1 \
			and absf(_log10(band_r.y) - _log10(r_hi)) <= 0.1:
		print("[PASS] G49 (two-axis ρ=EY+EI): measured band %s → %s matches true %s → %s" % [
			_sci(band_r.x), _sci(band_r.y), _sci(r_lo), _sci(r_hi)])
	else:
		_failures += 1
		push_error("G49 (two-axis): measured %s → %s vs true %s → %s" % [
			_sci(band_r.x), _sci(band_r.y), _sci(r_lo), _sci(r_hi)])


## G50 — the band span never drops below the floor nor exceeds the full range.
func _check_g50() -> void:
	sim.particle_color_mode = 2
	# First: the wide log-uniform field (spans decades). The tracked band is
	# tight around the central mass — its span must sit ≤ the full field span.
	_fill_field_q(2.0e-4, 5.0e-3, 21)
	var band: Vector2 = ui._autotrack_measure()
	if band.x <= 0.0:
		_failures += 1; _checks += 1
		push_error("G50: measure invalid on wide field")
		return
	var full_range_ratio := 5.0e-3 / 2.0e-4  # the field's observed range
	var span_wide: float = band.y / band.x
	_checks += 1
	if span_wide >= 10.0 and span_wide <= full_range_ratio * 1.05:
		print("[PASS] G50 (wide field): band span %.2f ≥ floor 10 and ≤ full range %.1f" % [span_wide, full_range_ratio])
	else:
		_failures += 1
		push_error("G50 (wide field): span %.2f outside [10, %.1f×1.05]" % [span_wide, full_range_ratio])
	# Then: a static / degenerate field — every cell the same value. The
	# measured percentiles collapse to a point; the min-span floor must hold
	# the band at the decade floor.
	_fill_field_q(1.0e-3, 1.0001e-3, 22)
	var band_d: Vector2 = ui._autotrack_measure()
	# Settle the EMA from the current qi_cycle (after the wide-field settle
	# it's wide; glide it toward the collapsed band — the floor caps it).
	var settled := Vector2.ZERO
	for _s in range(60):
		settled = ui._autotrack_update(band_d.x, band_d.y)
	var span_degen: float = settled.y / settled.x
	_checks += 1
	if band_d.x > 0.0 and span_degen >= 10.0 - 1e-3:
		print("[PASS] G50 (degenerate field): band span %.2f held at the 10× floor" % span_degen)
	else:
		_failures += 1
		push_error("G50 (degenerate): span %.2f dropped below the 10× floor (band=%s→%s)" % [
			span_degen, _sci(band_d.x), _sci(band_d.y)])


## G51 — the band GLIDES (damped, monotone, no per-sample jump) tracking a
## moving distribution.
func _check_g51() -> void:
	sim.particle_color_mode = 2
	# Use a WIDE (ratio 20) moving field so the robust band span exceeds the
	# min-span floor — the EMA GLIDE is what's exercised, not the floor cap.
	var base_lo := 5.0e-5
	var base_hi := 1.0e-3
	# Reset the tracker to a known start on the first field.
	_fill_field_q(base_lo, base_hi, 31)
	var band0: Vector2 = ui._autotrack_measure()
	if band0.x <= 0.0:
		_failures += 1; _checks += 1
		push_error("G51: measure failed on the start field")
		return
	# Settle the tracker onto the start band so the recorded glide begins
	# from a converged state (the following ×1.35 growth is then a clean
	# monotone expansion, not a catch-up from a prior wider band).
	for _k in range(15):
		ui._autotrack_update(band0.x, band0.y)
	var prev: Vector2 = ui._autotrack_update(band0.x, band0.y)
	# Feed a MONOTONE-rising distribution (a cascade-style scale-up): each
	# step the whole field band moves up by a factor, the measured target
	# follows. The EMA must glide: every tracked move is damped (never
	# out-runs the target's own per-sample move) and monotone (no backwards
	# jitter) — no per-sample teleport.
	var per_step := 1.35      # log move ln(1.35) ≈ 0.30 per sample
	var steps := 12
	var monotone := true
	var max_damp := true      # every tracked move ≤ the target's move this sample
	var prev_log := _log10(prev.y)
	var ok := true
	for s in range(steps):
		var f := pow(per_step, float(s + 1))
		_fill_field_q(base_lo * f, base_hi * f, 40 + s)
		var band: Vector2 = ui._autotrack_measure()
		if band.x <= 0.0:
			ok = false
			break
		var applied: Vector2 = ui._autotrack_update(band.x, band.y)
		var dl: float = _log10(applied.y) - prev_log
		# Damped: the tracked hi edge's per-sample move must never exceed the
		# target's own per-sample log move (the EMA approaches, it cannot
		# out-run the moving target), and may never move backwards (< 0).
		var tg_step: float = log(per_step) / log(10.0)
		if dl > tg_step + 1e-9 or dl < -1e-9:
			max_damp = false
		# Monotone: the hi edge log must be non-decreasing across a monotone
		# rising target sequence (the EMA of a monotone sequence is monotone).
		if _log10(applied.y) < prev_log - 1e-12:
			monotone = false
		prev_log = _log10(applied.y)
	if ok:
		var dl_tot: float = prev_log - _log10(band0.y)
		_checks += 1
		if max_damp and monotone:
			print("[PASS] G51: band glided across %d samples (Δlog10 top ≈ %+.2f), damped ≤ target move and monotone" % [steps, dl_tot])
		else:
			_failures += 1
			push_error("G51: glide violated (max_damp=%s monotone=%s, Δtop=%+.2f)" % [max_damp, monotone, dl_tot])
	else:
		_failures += 1; _checks += 1
		push_error("G51: a sample's measure/update failed mid-glide")


func _run_all() -> void:
	await _check_g49()
	await _check_g50()
	await _check_g51()


## Compact scientific formatting ("4.2e-4") — GDScript's % has no %e.
func _sci(v: float) -> String:
	if v == 0.0:
		return "0"
	var e := int(floor(_log10(absf(v))))
	var m := v / pow(10.0, float(e))
	var ms := "%.2f" % m
	if ms.ends_with(".00"):
		ms = ms.substr(0, ms.length() - 3)
	return "%se%d" % [ms, e]
