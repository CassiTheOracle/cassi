extends Node
## verify_omega_invariant — §5.4 of research/sound_coherence_note.md (TIER-1):
##   "ω₀² independence of c_s, faster ε suppression. Raise omega2 = 20.0:
##    the ρ front speed is unchanged (ρ decouples from ω₀²), but the ε gap
##    √(1+φ)·√ω₀² widens, so ε-mediated incoherence oscillates faster."
##
## ρ = EY+EI obeys ∂²ρ/∂t² = c²∇²ρ (the ω₀² coupling cancels on the sum), so
## the ρ front speed is IDENTICAL for omega2 = 20 and omega2 = 200. The ε
## mode ω_gap² = ω₀²(1+φ) scales as √ω₀²: ω_gap(200) = √(200·(1+φ)) =
## 7.2361·√10 ≈ 22.88 rad/unit-time.
##
## Gates (all TIER-1):
##   G1  ρ front speed c (omega2 = 20) ∈ [0.85, 1.05] cells/unit-time
##       (lattice-dispersion window, measured 0.884 — see verify_rho_front)
##   G2  ρ front speed c (omega2 = 200) ∈ [0.85, 1.05]  (ω₀²-invariant: the
##       two values must be identical to fp — ρ decouples from ω₀²)
##   G3  ε gap frequency with omega2 = 200 ≈ 22.88 (±5%)  (the √ω₀² scaling)
##
## Each sub-run is a fresh local-RD field planted and stepped identically.
## Direct local-RD dispatch of compute/cassi_two_fluid.glsl; sources OFF
## (rho buffer zeroed → the always-on 0.001·ρ feedback is null). Run
## (windowed console exe — NEVER --headless, which has no RD):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_omega_invariant.tscn

const TWO_PI: float = 6.28318530717958647692
const PHI: float = 1.618033988749895
const GRID_N := 48
const EXTENT := 37.5
const CELLS := GRID_N * GRID_N * GRID_N
const DT: float = 0.01
const SHELL_R0 := 6.0
const SHELL_SIG := 1.8
const EPS_SIGMA := 3.5           # pure-ε IC Gaussian width (scene-2 style)
const AMP := 1.0
# ρ-front measurement (compact φ-locked SHELL pulse — same as verify_rho_front:
# the front advances c·dt cells/step; a LONG window + small-front-level sub-cell
# leading-edge crossing measures the physical speed c = slope/dt).
const FRONT_LEVEL := 0.02
const FRONT_SAMPLE_AT: Array = [0, 100, 200, 300, 400]
# ε-gap measurement (omega2 = 200): period ≈ 2π/(22.88·0.01) ≈ 27.5 steps
const EPS_STEPS := 300
const OMEGA_GAP_200: float = 22.882937			# √(200·(1+φ)) = 7.23607·√10

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

	# G1/G2: ρ front speed c at omega2 = 20 and 200 (must be identical and
	# in the lattice-dispersion window [0.85,1.05] — see verify_rho_front).
	var s20 := _measure_rho_front(20.0)
	var s200 := _measure_rho_front(200.0)
	_check("G1: ρ front speed c @ omega2=20 ∈ [0.85, 1.05]", s20 >= 0.85 and s20 <= 1.05,
		"c=%.4f cells/unit-time" % s20)
	_check("G2: ρ front speed c @ omega2=200 ∈ [0.85, 1.05] (ω₀²-invariant c)",
		s200 >= 0.85 and s200 <= 1.05,
		"c=%.4f cells/unit-time (vs %.4f @ ω₀²=20)" % [s200, s20])
	# G3: ε gap frequency with omega2 = 200
	var om := _measure_eps_gap(200.0)
	var rel := absf(om - OMEGA_GAP_200) / OMEGA_GAP_200
	_check("G3: ε gap frequency @ omega2=200 ≈ 22.88 (±5%)",
		om > 0.0 and rel <= 0.05,
		"ω_m=%.4f expected=%.4f rel=%.4f" % [om, OMEGA_GAP_200, rel])

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


func _read_f32(rid: RID) -> PackedFloat32Array:
	return _rd.buffer_get_data(rid, 0, CELLS * 4).to_float32_array()


func _dispatch(pass_sel: float, omega2: float) -> void:
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _pipe)
	_rd.compute_list_bind_uniform_set(cl, _us, 0)
	_fill_pc(pass_sel, omega2)
	_rd.compute_list_set_push_constant(cl, _pc.to_byte_array(), _pc.size() * 4)
	var wg := GRID_N / 4
	_rd.compute_list_dispatch(cl, wg, wg, wg)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()


func _fill_pc(pass_sel: float, omega2: float) -> void:
	_pc.resize(17)
	_pc[0] = float(GRID_N)
	_pc[1] = DT
	_pc[2] = 0.0                    # t
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
	_pc[15] = omega2                # ω₀² (the parameter under test)
	_pc[16] = 0.0                  # ham_completion OFF (U1 toggle, offset 64)


## φ-locked SHELL pulse → ε = 0 exactly → pure ρ wave propagates at the
## lattice wave speed (see verify_rho_front for the normalization).
func _plant_rho(omega2: float) -> void:
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
	_rd.buffer_update(_ey, 0, CELLS * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, CELLS * 4, ei.to_byte_array())
	_zero_buffer(_q, CELLS * 4)
	_zero_buffer(_vel, CELLS * 16)
	_zero_buffer(_rho, CELLS * 4)
	_zero_buffer(_scratch, CELLS * 16)


## Sub-cell leading-edge crossing of FRONT_LEVEL·ρmax_IC along the six axes
## (mean of the interpolated crossings) — the causal ρ front.
func _front_crossing(ey: PackedFloat32Array, ei: PackedFloat32Array, level: float) -> float:
	var c := GRID_N / 2
	var dirs := [[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]]
	var crosses: Array = []
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
	return mean_r


func _rho_front_slope(omega2: float) -> float:
	# least-squares slope of the front crossing vs step over FRONT_SAMPLE_AT
	var level := FRONT_LEVEL * (PHI + 1.0) * AMP
	var ts: Array = []
	var rs: Array = []
	var stepper := 0
	for st in FRONT_SAMPLE_AT:
		while stepper < st:
			_dispatch(0.0, omega2); _dispatch(1.0, omega2)
			stepper += 1
		var ey := _read_f32(_ey)
		var ei := _read_f32(_ei)
		ts.append(st)
		rs.append(_front_crossing(ey, ei, level))
	# least-squares slope
	var n := ts.size()
	var sx := 0.0; var sy := 0.0; var sxx := 0.0; var sxy := 0.0
	for i in range(n):
		sx += float(ts[i]); sy += float(rs[i]); sxx += float(ts[i]) * float(ts[i]); sxy += float(ts[i]) * float(rs[i])
	var den := n * sxx - sx * sx
	if absf(den) < 1e-12:
		return 0.0
	return (n * sxy - sx * sy) / den


func _measure_rho_front(omega2: float) -> float:
	_plant_rho(omega2)
	var slope := _rho_front_slope(omega2)
	var c := slope / DT   # cells per unit sim-time
	print("  [omega_invariant] ρ front @ ω₀²=%.0f: slope=%.5f cells/step → c=%.4f cells/unit-time"
		% [omega2, slope, c])
	return c


func _measure_eps_gap(omega2: float) -> float:
	# pure-ε: EY = Amp·exp(-r²/σ²), EI = −EY (ρ ≡ 0). Record center ε(t) and
	# zero-crossing mean period → ω.
	var ey := PackedFloat32Array(); ey.resize(CELLS); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(CELLS); ei.fill(0.0)
	var c := GRID_N / 2
	var s2 := EPS_SIGMA * EPS_SIGMA
	for k in range(GRID_N):
		for j in range(GRID_N):
			for i in range(GRID_N):
				var dx := float(i - c); var dy := float(j - c); var dz := float(k - c)
				var g := AMP * exp(-(dx * dx + dy * dy + dz * dz) / (2.0 * s2))
				var id := i + GRID_N * (j + GRID_N * k)
				ey[id] = g; ei[id] = -g
	_rd.buffer_update(_ey, 0, CELLS * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, CELLS * 4, ei.to_byte_array())
	_zero_buffer(_q, CELLS * 4)
	_zero_buffer(_vel, CELLS * 16)
	_zero_buffer(_rho, CELLS * 4)
	_zero_buffer(_scratch, CELLS * 16)
	var cid := c + GRID_N * (c + GRID_N * c)
	var eps_series := PackedFloat32Array(); eps_series.resize(EPS_STEPS)
	for s in range(EPS_STEPS):
		var eyr := _read_f32(_ey)
		var eir := _read_f32(_ei)
		var eps_c := eyr[cid] - PHI * eir[cid]
		eps_series[s] = eps_c
		_dispatch(0.0, omega2); _dispatch(1.0, omega2)
	var crossings: Array = []
	var prev := eps_series[0]
	for t in range(1, EPS_STEPS):
		var cur := eps_series[t]
		if (prev < 0.0 and cur >= 0.0) or (prev >= 0.0 and cur < 0.0):
			crossings.append(t)
		prev = cur
	if crossings.size() < 4:
		print("  [omega_invariant] ε gap @ ω₀²=%.0f: too few zero crossings (%d) for a frequency"
			% [omega2, crossings.size()])
		return 0.0
	var sum_period := 0.0
	var cnt := 0
	for i in range(crossings.size() - 2):
		sum_period += float(int(crossings[i + 2]) - int(crossings[i]))
		cnt += 1
	var period := sum_period / float(cnt)
	var om := TWO_PI / (period * DT)
	var crossings_count: int = crossings.size()
	print("  [omega_invariant] ε gap @ ω₀²=%.0f: mean period=%.2f steps (%d crossings) → ω_m=%.4f"
		% [omega2, period, crossings_count, om])
	return om


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
	print("[VerifyOmegaInvariant] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyOmegaInvariant] RESULT: PASS")
	else:
		print("[VerifyOmegaInvariant] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
