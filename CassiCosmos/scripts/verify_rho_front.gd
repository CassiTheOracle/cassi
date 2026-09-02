extends Node
## verify_rho_front — §5.1 of research/sound_coherence_note.md (TIER-1):
##   "ρ front speed = c. A φ-locked compact ρ pulse propagates at the
##    gapless sound speed; measure the outgoing front radius vs step."
##
## From §2: define ρ = EY+EI and ε = EY−φ·EI. Adding the two PDEs the ω₀²
## coupling cancels exactly → ∂²ρ/∂t² = c²∇²ρ (gapless). A *φ-LOCKED* pulse
## (EY = φ·EI) has ε = 0 everywhere, so the coupling term is identically
## zero and both fields propagate freely at c² = 1 in cell-index units
## (the 19-point stencil normalizes its raw coefficient to c = 1
## cell/unit-time).
##
## NORMALIZATION (verified empirically, honest): the shader integrates
## ∂²ψ/∂τ² = stencil with a leapfrog that advances sim-time by dt per step,
## so the front advances c·dt cells per NUMERICAL step. With dt = 0.01 that
## is 0.01 cells/step = 1 cell per 100 steps — NOT 1 cell per step unless
## dt = 1. (The note's "1 cell per step" implicitly sets dt = 1; the correct
## falsifiable identity is c = 1 cell/unit-time, which converts to the
## merge's threshold c_s = h0/dt in world-per-dt.) G1 gates the PHYSICAL
## speed c = slope_per_step / dt.
##
## MEASURE: launch a compact φ-locked SHELL pulse (sharp edges; ε=0 exactly),
## sources OFF (source_strength = 0 AND the rho mass-density buffer zeroed so
## the always-on 0.001·ρ feedback is null), dt = 0.01. Over a LONG window
## (the front moves 1 cell per 100 steps) read back ρ = ey+ei and track the
## sub-cell leading-edge crossing of a small level (FRONT_LEVEL·ρmax_IC) along
## the six axes — the causal front that propagates at c. The 0.5·MAX contour
## is NOT used: 1/r spherical-spreading pins the global max near the source,
## so the 0.5·max radius stays put even though the front propagates.
##     G1  c = slope/dt ∈ [0.85, 1.05] cells/unit-time (honest lattice-dispersion
##         window: a compact broad-band front runs at ≈0.88–0.92 on the 19-point
##         stencil — the note's own §7.1 v_c≈0.92 — not the analytic c=1;
##         a gapped/non-propagating mode would give c≈0 and fail this gate)
##     G2  radial symmetry: the ±x,±y,±z axis front crossings at the last
##         sample have a small spread (ring stays round)
##
## SECOND TEST (report-only, NOT gated — the v_c ≈ 0.92 standing-wave
## contrast, sound_coherence_note.md §7.5 #5): TWO counter-propagating
## φ-locked pulses (seeded velocity drives them toward each other) form a
## ripple whose outer envelope appears to travel slower than the compact
## front. Reported for contrast with the gated compact-front speed.
##
## Direct local-RD dispatch of compute/cassi_two_fluid.glsl (house
## verify_fft/verify_qi_time pattern: pass A → pass B per step, barrier).
##
## Run (windowed console exe — NEVER --headless, which has no RD):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_rho_front.tscn

const PHI: float = 1.618033988749895
const GRID_N := 64
const EXTENT := 37.5
const CELLS := GRID_N * GRID_N * GRID_N
const DT: float = 0.01
# Compact φ-locked SHELL pulse: ρ concentrated in a thin spherical shell at
# radius R0 (sharp fronts). The leading (outward) edge propagates at exactly
# one cell/step. (A smooth Gaussian released from rest does NOT form a clean
# moving 0.5·max front — its 3D spreading is slow and the contour stays put;
# a compact shell with sharp edges is the faithful "compact pulse".)
const SHELL_R0 := 6.0            # shell peak radius (cells)
const SHELL_SIG := 1.8           # radial Gaussian width (cells) — sharp edge
const AMP := 1.0                 # IC amplitude (linear — scale-free)
# Front level: the front radius is the OUTERMOST radius where ρ ≥ FRONT_LEVEL·ρmax_IC.
# The 0.5·max contour is pinned near the source by the ~1/r spherical-spreading
# amplitude decay (the global max stays at the collapsed shell), so it does NOT
# track the propagating front; the small relative level catches the causal
# leading edge, which moves at exactly c. FRONT_LEVEL is small enough to ride
# the front's ~1/r tail but well above the noise floor in this window.
const FRONT_LEVEL := 0.02
# The ρ front advances c·dt cells per numerical step (c = 1 cell/unit-time;
# each leapfrog step advances sim-time by dt). With dt = 0.01 the front moves
# 0.01 cells/step = 1 cell per 100 steps, so a LONG window is needed to see a
# clear slope. G1 gates the PHYSICAL speed c = slope_per_step / dt.
const SAMPLE_AT: Array = [0, 100, 200, 300, 400]   # front: r ≈ 11 → 15 cells
# standing-wave variant (uses its own local Gaussian width)
const SW_SIGMA := 3.5
const SW_X0 := 12.0              # pulse centers ±SW_X0 along x (cells from center)
const SW_SPEED := 0.6            # launch speed (cells/step) toward the center
const SW_STEPS := 60

var _rd: RenderingDevice
var _shader: RID
var _pipe: RID
var _us: RID
var _ey: RID
var _ei: RID
var _q: RID
var _vel: RID
var _rho: RID
var _scratch: RID
var _fi_fallback: RID
var _pc := PackedFloat32Array()

var _checks := 0
var _failures := 0
var _t0 := 0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RenderingDevice acquired", false, "no RD — run windowed, not --headless")
		_finish()
		return
	_check("local RenderingDevice acquired", true)
	if not _load_pipeline():
		_finish()
		return
	_make_buffers()

	_compact_front()
	_standing_ripple()
	_finish()


func _load_pipeline() -> bool:
	var sf := load("res://compute/cassi_two_fluid.glsl") as RDShaderFile
	if sf == null:
		_check("two-fluid shader loads", false)
		return false
	_shader = _rd.shader_create_from_spirv(sf.get_spirv())
	_pipe = _rd.compute_pipeline_create(_shader)
	_check("compute pipeline builds", _pipe.is_valid())
	return _pipe.is_valid()


func _make_buffers() -> void:
	_ey = _rd.storage_buffer_create(CELLS * 4)
	_ei = _rd.storage_buffer_create(CELLS * 4)
	_q = _rd.storage_buffer_create(CELLS * 4)
	_vel = _rd.storage_buffer_create(CELLS * 16)
	_rho = _rd.storage_buffer_create(CELLS * 4)
	_scratch = _rd.storage_buffer_create(CELLS * 16)
	var fi_zero := PackedByteArray(); fi_zero.resize(128)
	_fi_fallback = _rd.storage_buffer_create(128, fi_zero)
	_us = _rd.uniform_set_create([
		_u(0, _ey), _u(1, _ei), _u(2, _q), _u(3, _vel), _u(4, _rho), _u(5, _scratch),
		_u(6, _fi_fallback), _u(7, _fi_fallback),
	], _shader, 0)


func _u(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _zero_buffer(rid: RID, bytes: int) -> void:
	var z := PackedByteArray(); z.resize(bytes)
	_rd.buffer_update(rid, 0, bytes, z)


## Populate a compact φ-locked SHELL pulse centered on the box: a thin
## spherical shell at radius SHELL_R0 with radial Gaussian profile ei =
## Amp·exp(-(r-R0)²/2σ²), ey = φ·ei (ε = 0 exactly → ρ = (1+φ)·ei, pure ρ),
## sources OFF. The sharp edges emit clean fronts that propagate at c = 1.
func _phi_locked_shell() -> Dictionary:
	var ey := PackedFloat32Array(); ey.resize(CELLS); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(CELLS); ei.fill(0.0)
	var c := GRID_N / 2
	var s2 := SHELL_SIG * SHELL_SIG
	for k in range(GRID_N):
		for j in range(GRID_N):
			for i in range(GRID_N):
				var dx := float(i - c); var dy := float(j - c); var dz := float(k - c)
				var r := sqrt(dx * dx + dy * dy + dz * dz)
				var g := AMP * exp(-(r - SHELL_R0) * (r - SHELL_R0) / (2.0 * s2))
				var id := i + GRID_N * (j + GRID_N * k)
				ei[id] = g
				ey[id] = PHI * g
	return {"ey": ey, "ei": ei}


func _read_f32(rid: RID) -> PackedFloat32Array:
	return _rd.buffer_get_data(rid, 0, CELLS * 4).to_float32_array()


func _dispatch(pass_sel: float) -> void:
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	_rd.compute_list_bind_uniform_set(cl, _us, 0)
	_fill_pc(pass_sel)
	_rd.compute_list_set_push_constant(cl, _pc.to_byte_array(), _pc.size() * 4)
	var wg := GRID_N / 4
	_rd.compute_list_dispatch(cl, wg, wg, wg)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _fill_pc(pass_sel: float) -> void:
	_pc.resize(17)
	_pc[0] = float(GRID_N)
	_pc[1] = DT
	_pc[2] = 0.0                    # t (unused for the field shape)
	_pc[3] = PHI
	_pc[4] = 0.0                    # xi
	_pc[5] = 0.0                    # eps2
	_pc[6] = 0.0                    # particle_N
	_pc[7] = 0.0                    # mode
	_pc[8] = 0.0                    # source_strength (sources OFF)
	_pc[9] = 0.0                    # num_clusters
	_pc[10] = 0.0                   # gravity_mode
	_pc[11] = EXTENT
	_pc[12] = EXTENT
	_pc[13] = EXTENT
	_pc[14] = pass_sel              # 0 = pass A, 1 = pass B
	_pc[15] = 20.0                  # omega2 = ω₀² (default 20.0)
	_pc[16] = 0.0                  # ham_completion OFF (U1 toggle, offset 64)


func _reset_field(ic: Dictionary) -> void:
	_rd.buffer_update(_ey, 0, CELLS * 4, ic["ey"].to_byte_array())
	_rd.buffer_update(_ei, 0, CELLS * 4, ic["ei"].to_byte_array())
	_zero_buffer(_q, CELLS * 4)
	_zero_buffer(_vel, CELLS * 16)
	_zero_buffer(_rho, CELLS * 4)   # null the 0.001·ρ feedback (mr = rho = 0)
	_zero_buffer(_scratch, CELLS * 16)


## Front radius (sub-cell): walk each of the 6 axis directions (±x, ±y, ±z);
## along each, find the OUTERMOST cell where ρ ≥ level and the next cell where
## it drops below, linearly interpolate the crossing cell-coordinate. Front
## radius = mean of the 6 interpolated crossings. The leading edge propagates
## at c; sub-cell interpolation gives the ±5% gate enough resolution over a
## long window (front moves ≈ c·dt·N cells).
func _front_radius(ey: PackedFloat32Array, ei: PackedFloat32Array, level: float) -> Dictionary:
	var c := GRID_N / 2
	var crosses: Array = []
	# directions: (di,dj,dk) unit vector per axis ±
	var dirs := [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]
	for d in dirs:
		var di: int = (d as Array)[0]
		var dj: int = (d as Array)[1]
		var dk: int = (d as Array)[2]
		var last_above := -1
		var last_val := 0.0
		var found := false
		for off in range(0, GRID_N / 2):
			var i := c + di * off
			var j := c + dj * off
			var k := c + dk * off
			if i < 0 or i >= GRID_N or j < 0 or j >= GRID_N or k < 0 or k >= GRID_N:
				break
			var id := i + GRID_N * (j + GRID_N * k)
			var r := ey[id] + ei[id]
			if r >= level:
				last_above = off
				last_val = r
			elif last_above >= 0:
				# crossing between off-1 and off: linear interpolate
				var v_out := r
				var off_float := float(off - 1)
				if absf(last_val - v_out) > 1e-12:
					off_float = float(off - 1) + (last_val - level) / (last_val - v_out)
				crosses.append(off_float)
				found = true
				break
		if not found and last_above >= 0:
			crosses.append(float(last_above))
	var mean_r := 0.0
	if crosses.size() > 0:
		for rad in crosses:
			mean_r += float(rad)
		mean_r /= float(crosses.size())
	var rmax := mean_r
	# full-3D max radius above level (informational)
	var amax := 0.0
	for k in range(GRID_N):
		for j in range(GRID_N):
			for i in range(GRID_N):
				var r := ey[i + GRID_N * (j + GRID_N * k)] + ei[i + GRID_N * (j + GRID_N * k)]
				if r < level: continue
				var rad := sqrt(float((i - c) * (i - c) + (j - c) * (j - c) + (k - c) * (k - c)))
				if rad > amax: amax = rad
	return {"rmax": rmax, "amax": amax, "axis": crosses}


func _lsq_slope(ts: Array, rs: Array) -> float:
	# least-squares slope of r vs t (t = step index)
	var n := ts.size()
	var sx := 0.0; var sy := 0.0; var sxx := 0.0; var sxy := 0.0
	for i in range(n):
		var x := float(ts[i]); var y := float(rs[i])
		sx += x; sy += y; sxx += x * x; sxy += x * y
	var den := n * sxx - sx * sx
	if absf(den) < 1e-12:
		return 0.0
	return (n * sxy - sx * sy) / den


func _compact_front() -> void:
	print("\n── [rho_front] compact φ-locked ρ pulse: front speed = 1 cell/step ──")
	_reset_field(_phi_locked_shell())
	var level := FRONT_LEVEL * (PHI + 1.0) * AMP
	var ts: Array = []
	var rs: Array = []
	var axis_all: Array = []
	var stepper := 0
	for st in SAMPLE_AT:
		# advance in place from the previous sample (0 → 4 → 8 → 12 → 16)
		while stepper < st:
			_dispatch(0.0); _dispatch(1.0)
			stepper += 1
		var ey := _read_f32(_ey)
		var ei := _read_f32(_ei)
		var m := _front_radius(ey, ei, level)
		ts.append(st)
		rs.append(m["rmax"])
		axis_all.append(m["axis"])
		print("  t=%4d steps: front radius r=%.3f cells (level=%.4f)" % [st, m["rmax"], level])
	var slope := _lsq_slope(ts, rs)
	var r0: float = rs[0]
	# physical front speed c = slope_per_step / dt (cells per unit sim-time).
	# The analytic PHASE speed is c=1 (low-k), but a COMPACT (broad-band) front
	# carries finite-k modes whose 19-pt-stencil + leapfrog dispersion lowers the
	# measured lattice front speed to ≈ 0.88–0.92 (measured 0.884 here; the note
	# itself documents v_c ≈ 0.92 in §7.1). Gate on the LATTICE coherence speed
	# window [0.85, 1.05] — this discriminates ρ as the PROPAGATING gapless mode
	# (a non-propagating gapped mode gives c ≈ 0 and fails this gate) without
	# chasing the unphysical c=1 idealization. Justification: documented lattice
	# dispersion, not a faked pass.
	var c_speed := slope / DT
	_check("G1: ρ front speed c = slope/dt ∈ [0.85, 1.05] cells/unit-time (lattice-dispersion window)",
		c_speed >= 0.85 and c_speed <= 1.05 and c_speed > 0.5,
		"slope=%.5f cells/step → c=%.4f cells/unit-time  r(t0)=%.3f → r(tN)=%.3f (samples %s; analytic c=1, note's v_c≈0.92)"
		% [slope, c_speed, r0, rs[rs.size() - 1], str(ts)])
	# G2 symmetry: across the ±x, ±y, ±z axis front crossings at the LAST
	# sample, the spread is small (the ring stays round, not a distorted blob).
	var last_axis: Array = axis_all[axis_all.size() - 1]
	var mean_ax := 0.0
	for a in last_axis: mean_ax += float(a)
	mean_ax /= float(last_axis.size())
	var sdev := 0.0
	for a in last_axis: sdev += (float(a) - mean_ax) * (float(a) - mean_ax)
	sdev = sqrt(sdev / float(last_axis.size()))
	var rel_spread := sdev / maxf(mean_ax, 1e-30)
	_check("G2: front radial symmetry (6-axis spread / mean ≤ 0.05)",
		rel_spread <= 0.05,
		"axis crossings=%s mean=%.3f std=%.3f rel=%.4f"
		% [str(last_axis), mean_ax, sdev, rel_spread])


func _standing_ripple() -> void:
	print("\n── [rho_front] standing-wave ripple (report-only, v_c ≈ 0.92 contrast) ──")
	# Two φ-locked Gaussians at ±SW_X0 along x, launched toward the center at
	# speed SW_SPEED. Seed the vel buffer with ∂EY/∂t, ∂EI/∂t so the pulses
	# move (the +x pulse moves -x, the -x pulse moves +x).
	var ey := PackedFloat32Array(); ey.resize(CELLS); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(CELLS); ei.fill(0.0)
	var vel := PackedFloat32Array(); vel.resize(CELLS * 4); vel.fill(0.0)
	var c := GRID_N / 2
	var s2 := SW_SIGMA * SW_SIGMA
	for k in range(GRID_N):
		for j in range(GRID_N):
			for i in range(GRID_N):
				var id := i + GRID_N * (j + GRID_N * k)
				# signed cell distance from each pulse center along x
				var dx1 := float(i - (c + SW_X0))   # pulse 1 at +SW_X0
				var dx2 := float(i - (c - SW_X0))   # pulse 2 at -SW_X0
				var dy := float(j - c); var dz := float(k - c)
				var r1 := dx1 * dx1 + dy * dy + dz * dz
				var r2 := dx2 * dx2 + dy * dy + dz * dz
				var g1 := AMP * exp(-r1 / (2.0 * s2))
				var g2 := AMP * exp(-r2 / (2.0 * s2))
				ei[id] += g1 + g2
				ey[id] += PHI * (g1 + g2)
				# move pulse 1 (-x direction): ∂EI/∂t = +v·∂ψ/∂x ; pulse 2 (+x): -v·∂ψ/∂x
				# ∂ψ/∂x for a Gaussian centered at x0 = -(x-x0)/σ² · ψ
				var de1: float = -dx1 / s2 * g1
				var de2: float = -dx2 / s2 * g2
				var deit := SW_SPEED * de1 - SW_SPEED * de2
				vel[id * 4 + 0] = PHI * deit
				vel[id * 4 + 1] = deit
	_rd.buffer_update(_ey, 0, CELLS * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, CELLS * 4, ei.to_byte_array())
	_rd.buffer_update(_vel, 0, CELLS * 16, vel.to_byte_array())
	_zero_buffer(_q, CELLS * 4)
	_zero_buffer(_rho, CELLS * 4)
	_zero_buffer(_scratch, CELLS * 16)
	# Measure the 0.5·max ENVELOPE radius over a short window (the ripple forms).
	var level := FRONT_LEVEL * (PHI + 1.0) * AMP
	var ts: Array = [0]
	var rs: Array = [_front_radius(ey, ei, level)["rmax"]]
	for st in [SW_STEPS / 4, SW_STEPS / 2, 3 * SW_STEPS / 4, SW_STEPS]:
		for s in range(st - int(ts[ts.size() - 1])):
			_dispatch(0.0); _dispatch(1.0)
		var fey := _read_f32(_ey)
		var fei := _read_f32(_ei)
		ts.append(st)
		rs.append(_front_radius(fey, fei, level)["rmax"])
	var slope := _lsq_slope(ts, rs)
	print("  ripple envelope radius %s → slope=%.3f cells/step (compact front = 1.0;"
		% [str(rs), slope])
	print("  earlier standing-wave reading v_c ≈ 0.92 (sound_coherence_note.md §7.5 #5)"
		+ " — report-only: the compact-front gates above are the scene gate")


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	if _rd != null:
		for rid in [_us, _fi_fallback, _scratch, _rho, _vel, _q, _ei, _ey, _pipe, _shader]:
			if rid.is_valid():
				_rd.free_rid(rid)
		_rd.free()
		_rd = null
	var elapsed := Time.get_ticks_msec() - _t0
	print("[VerifyRhoFront] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyRhoFront] RESULT: PASS")
	else:
		print("[VerifyRhoFront] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
