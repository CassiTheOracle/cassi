extends Node
## verify_eps_gap — §5.2 of research/sound_coherence_note.md (TIER-1):
##   "ε is gapped. Launch a pure-ε perturbation (ρ = 0, i.e. EY = −EI): it
##    stays put, oscillating in place at ω_gap ≈ 7.236 rad/step rather
##    than radiating a front."
##
## From §2: ε = EY−φ·EI obeys ∂²ε/∂t² = c²∇²ε − ω₀²(1+φ)ε, with mass gap
##   ω_gap² = ω₀²(1+φ) = 20·(1+φ) = 20φ² ≈ 52.36  →  ω_gap ≈ 7.2361 rad/unit-time.
## A ρ-NULL, ε-NONZERO state (EY = −EI so ρ = EY+EI ≡ 0) is the genuinely
## non-propagating input: ε oscillates in place at the gap frequency and
## ρ stays ≡ 0 (the coupling cancels on the sum).
##
## IC: EY = Amp·exp(-r²/σ²), EI = −EY (ρ ≡ 0 everywhere, ε = (1+φ)EY ≠ 0).
## Sources OFF (source_strength = 0, rho buffer zeroed → null feedback),
## dt = 0.01, 32³ grid.
## GUARD AGAINST THE SPATIAL DISPERSION TRAP: the measured gap is the long-
## wavelength (k≈0) frequency of the localized Gaussian; for σ = 3.5 cells
## the k-spread shift is c²k_eff² / (2ω_gap) ≈ 0.09% (well inside the 5% gate).
##
## Gates:
##   G1  DECOUPLING: the center-cell ρ = ey+ei stays ≈ 0 over the whole run
##       (max |ρ_center| ≤ 1e-3 · max|ε|).
##   G2  GAP FREQUENCY: zero-crossing estimate of the center-cell ε(t)
##       dominant frequency over ~600 steps (≈7 periods) → |ω_m − 7.236| ≤ 0.05.
##   G3  NON-PROPAGATION: the WHOLE-GRID ρ stays ≈ 0 at the end
##       (max|ρ_all| ≤ 1e-3 · max|ε|).
##
## Direct local-RD dispatch of compute/cassi_two_fluid.glsl (pass A → pass B
## per step). Run (windowed console exe — NEVER --headless, which has no RD):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_eps_gap.tscn

const TWO_PI: float = 6.28318530717958647692
const PHI: float = 1.618033988749895
const GRID_N := 32
const EXTENT := 37.5
const CELLS := GRID_N * GRID_N * GRID_N
const DT: float = 0.01
const SIGMA := 3.5
const AMP := 1.0
# gap prediction
const OMEGA_GAP: float = 7.23606797749979   # √(ω₀²(1+φ)) = √(20·2.618034) = √52.3607
const STEPS := 600                          # ≈ 6.9 periods (period ≈ 86.8 steps)

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
	_run_gap()
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
	_us = _rd.uniform_set_create([
		_u(0, _ey), _u(1, _ei), _u(2, _q), _u(3, _vel), _u(4, _rho), _u(5, _scratch),
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
	_pc[15] = 20.0                  # omega2 = ω₀² (default 20.0)
	_pc[16] = 0.0                  # ham_completion OFF (U1 toggle, offset 64)


func _plant_pure_eps() -> void:
	# EY = Amp·exp(-r²/σ²), EI = −EY → ρ ≡ 0, ε = EY−φ·EI = (1+φ)EY ≠ 0.
	var ey := PackedFloat32Array(); ey.resize(CELLS); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(CELLS); ei.fill(0.0)
	var c := GRID_N / 2
	var s2 := SIGMA * SIGMA
	for k in range(GRID_N):
		for j in range(GRID_N):
			for i in range(GRID_N):
				var dx := float(i - c); var dy := float(j - c); var dz := float(k - c)
				var g := AMP * exp(-(dx * dx + dy * dy + dz * dz) / (2.0 * s2))
				var id := i + GRID_N * (j + GRID_N * k)
				ey[id] = g
				ei[id] = -g
	_rd.buffer_update(_ey, 0, CELLS * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, CELLS * 4, ei.to_byte_array())
	_zero_buffer(_q, CELLS * 4)
	_zero_buffer(_vel, CELLS * 16)
	_zero_buffer(_rho, CELLS * 4)   # null the 0.001·ρ feedback
	_zero_buffer(_scratch, CELLS * 16)


## Mean period (steps) of the ε(t) series by zero-crossing: find every step
## where ε changes sign; a full period lies between two same-direction
## crossings. Returns steps-per-period, or 0 if too few crossings.
func _zero_crossing_period_steps(eps_series: PackedFloat32Array) -> float:
	var crossings: Array = []
	var n := eps_series.size()
	var prev := eps_series[0]
	for t in range(1, n):
		var cur := eps_series[t]
		if (prev < 0.0 and cur >= 0.0) or (prev >= 0.0 and cur < 0.0):
			crossings.append(t)
		prev = cur
	if crossings.size() < 4:
		return 0.0
	var sum_period := 0.0
	var cnt := 0
	for i in range(crossings.size() - 2):
		sum_period += float(int(crossings[i + 2]) - int(crossings[i]))
		cnt += 1
	return sum_period / float(cnt)


func _run_gap() -> void:
	print("\n── [eps_gap] pure-ε perturbation: ρ stays 0, ε oscillates at ω_gap ≈ 7.236 ──")
	_plant_pure_eps()
	var c := GRID_N / 2
	var cid := c + GRID_N * (c + GRID_N * c)
	var max_rho_center := 0.0
	var max_eps := 0.0
	var eps_series := PackedFloat32Array()
	eps_series.resize(STEPS)
	for s in range(STEPS):
		# read the CURRENT center state BEFORE advancing (s=0 is the IC)
		var ey := _read_f32(_ey)
		var ei := _read_f32(_ei)
		var e0 := ey[cid]; var i0 := ei[cid]
		var rho_c := e0 + i0
		var eps_c := e0 - PHI * i0
		eps_series[s] = eps_c
		if absf(rho_c) > max_rho_center: max_rho_center = absf(rho_c)
		if absf(eps_c) > max_eps: max_eps = absf(eps_c)
		_dispatch(0.0); _dispatch(1.0)
	# final whole-grid max|ρ| (G3)
	var fey := _read_f32(_ey)
	var fei := _read_f32(_ei)
	var max_rho_all := 0.0
	for i in range(CELLS):
		var r := absf(fey[i] + fei[i])
		if r > max_rho_all: max_rho_all = r
	# G1: center ρ decoupled from ε over the whole run
	var thr := 1e-3 * max_eps
	_check("G1: center ρ stays ≈ 0 (max|ρ_c| ≤ 1e-3·max|ε|)",
		max_rho_center <= thr,
		"max|ρ_c|=%s max|ε|=%.6f thr=%s" % [str(max_rho_center), max_eps, str(thr)])
	# G2: gap frequency from zero-crossings
	var period_steps := _zero_crossing_period_steps(eps_series)
	var crossings_count := 0
	for t in range(1, eps_series.size()):
		if (eps_series[t - 1] < 0.0 and eps_series[t] >= 0.0) or (eps_series[t - 1] >= 0.0 and eps_series[t] < 0.0):
			crossings_count += 1
	var omega_m := 0.0
	if period_steps > 0.0:
		omega_m = TWO_PI / (period_steps * DT)
	print("  zero-crossing: mean period=%.2f steps (%d crossings) → ω_m=%.4f rad/unit"
		% [period_steps, crossings_count, omega_m])
	var rel := absf(omega_m - OMEGA_GAP) / OMEGA_GAP
	_check("G2: ε center frequency ≈ ω_gap (±5%)",
		period_steps > 0.0 and rel <= 0.05,
		"ω_m=%.4f expected=%.4f rel=%.6f" % [omega_m, OMEGA_GAP, rel])
	# G3: whole-grid ρ stays ≈ 0 (non-propagation)
	_check("G3: whole-grid ρ stays ≈ 0 (max|ρ_all| ≤ 1e-3·max|ε|)",
		max_rho_all <= thr,
		"max|ρ_all|=%s thr=%s" % [str(max_rho_all), str(thr)])


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	var elapsed := Time.get_ticks_msec() - _t0
	print("[VerifyEpsGap] checks=%d failures=%d elapsed=%d ms" % [_checks, _failures, elapsed])
	if _failures == 0:
		print("[VerifyEpsGap] RESULT: PASS")
	else:
		print("[VerifyEpsGap] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
