extends Node3D
## M1 gate-iv — wave-fidelity battery (the A-decider) + phase C prototypes
## Meshless per-site wave (cassi_voronoi_cells modes 10/0/1/12 + raster)
## vs the N³ two-fluid reference (cassi_two_fluid pass A/B), on the SAME
## physical setup: a checkerboard ground state + Gaussian pulse, source off,
## particle masses zeroed (rho_mass = 0 -> pure linear wave, no feedback).
##
## Measured: (1) the pulse ρ-front speed along x from ray profiles,
## (2) the dominant-mode frequency ratio at a probe point (FFT of ρ(t)).
##
## Gate (overhaul_build_plan.md gate-iv): |Δv_front| <= 5% and the top-2
## dominant-mode frequency ratio preserved to the N³ self-consistency
## precision. Phase C prototypes the gated site-path variants (unwrapped
## steer + per-site source) against the canonical shader.
##
## Run (windowed — the sim uses the global RD):
##   godot --path <repo> res://_diag/m1_gateiv.tscn

const STEPS_TOTAL := 1000
const BATCH := 4          # steps per _run_physics_steps call (sampling cadence)
const AMP_CB := 0.1       # checkerboard amplitude
const AMP_PULSE := 0.2    # pulse amplitude
const SIGMA := 1.0 / 8.0  # pulse width as a fraction of extent_x
const PI := 3.14159265358979

var _sim: Node
var _phase := 0
var _frames := 0
var _step := 0
var _ext := Vector3.ZERO
var _probe_ix := -1
var _ray: Array = []
var _probe_series: Array = []
var _t_series: Array = []
var _meshless_result: Dictionary = {}
var _grid_result: Dictionary = {}
var _far_site_ix := -1
var _site_series: Array = []


## The meshless site nearest x = 0.75·Lx (the pulse's far field): if its psi
## oscillates with the pulse's arrival, the site-level wave transports and
## only the raster hides it; if it stays at the checkerboard, transport fails.
func _find_far_site() -> int:
	if _sim._ml_sites_cpu.size() < 4:
		return -1
	var ext_v: Vector3 = _sim._extents()
	var Lx := 2.0 * ext_v.x
	var best := 0
	var bd := 1.0e30
	for s in range(_sim._ml_sites_cpu.size() / 4):
		var d := absf(_sim._ml_sites_cpu[s * 4] - 0.75 * Lx)
		if d < bd:
			bd = d
			best = s
	return best
var _var_shader: RID = RID()
var _var_pipe: RID = RID()
var _var_fail := 0


func _ready() -> void:
	_sim = $CassiSim
	_sim.playing = false
	_sim.reinit()


func _process(_delta: float) -> void:
	_frames += 1
	if _sim == null or not _sim._shaders_ready:
		return
	match _phase:
		0:  # start the meshless arm run
			_start_phase("meshless", true)
			_phase = 1
		1:  # drive the meshless wave to completion
			if _step < STEPS_TOTAL:
				_run_batch()
			else:
				_finish_phase("meshless")
				_phase = 2
		2:  # start the grid (N³ two-fluid) reference run
			_start_phase("grid", false)
			_phase = 3
		3:  # drive the grid wave to completion
			if _step < STEPS_TOTAL:
				_run_batch()
			else:
				_finish_phase("grid")
				_phase = 4
		4:  # verdict (prints; the variant phase C follows)
			_verdict()
			_phase = 5
		5:  # variant setup
			_variant_setup()
			_phase = 6
		6:  # unwrapped-steer + per-site-source tests
			_variant_tests()
			_phase = 7
		7:  # done
			print("[M1GateIV] phase C complete")
			get_tree().quit(0)


func _start_phase(name: String, meshless: bool) -> void:
	if meshless:
		_sim.meshless_mode = true
	else:
		_sim.meshless_mode = false
	_sim.reinit()
	_ext = _sim._extents()
	_inject_ic(meshless)
	_zero_masses()
	_step = 0
	_ray = []
	_probe_series = []
	_t_series = []
	_probe_ix = int(round(float(_sim.grid_N) * 0.25))
	_far_site_ix = _find_far_site()
	_site_series = []
	print("[M1GateIV] phase '%s' started: grid_N=%d dt=%.4f ext=(%.1f, %.1f, %.1f), far-site=%d"
		% [name, _sim.grid_N, _sim.dt, _ext.x, _ext.y, _ext.z, _far_site_ix])


## Evaluate the continuum IC (checkerboard + Gaussian pulse) at a world point.
func _ic_ey_ei(wp: Vector3) -> Vector2:
	var kx := PI / _ext.x
	var cb_ey := AMP_CB * cos(kx * wp.x)
	var cb_ei := AMP_CB * sin(kx * wp.x)
	var sig := SIGMA * _ext.x
	var r2 := wp.x * wp.x + wp.y * wp.y + wp.z * wp.z
	var p := AMP_PULSE * exp(-r2 / (sig * sig))
	return Vector2(cb_ey + p, cb_ei + p)


func _inject_ic(meshless: bool) -> void:
	var N: int = _sim.grid_N
	var rd: RenderingDevice = _sim._rd
	if meshless:
		# Sample the continuum IC at the SITE positions; zero pi + lap.
		# psi_y/psi_i/pi_y/pi_i/lap_y/lap_i are FLOAT buffers (ns floats =
		# ns*4 bytes each), NOT vec4 arrays.
		var sites: PackedFloat32Array = rd.buffer_get_data(_sim._ml_sites, 0,
			_sim._ml_sites_cpu.size() * 4).to_float32_array()
		var ns := sites.size() / 4
		var sy := PackedFloat32Array(); sy.resize(ns)
		var si := PackedFloat32Array(); si.resize(ns)
		var sz := PackedFloat32Array(); sz.resize(ns)
		for s in range(ns):
			var v := _ic_ey_ei(Vector3(sites[s * 4], sites[s * 4 + 1], sites[s * 4 + 2]))
			sy[s] = v.x
			si[s] = v.y
		rd.buffer_update(_sim._ml_psi_y, 0, ns * 4, sy.to_byte_array())
		rd.buffer_update(_sim._ml_psi_i, 0, ns * 4, si.to_byte_array())
		rd.buffer_update(_sim._ml_pi_y, 0, ns * 4, sz.to_byte_array())
		rd.buffer_update(_sim._ml_pi_i, 0, ns * 4, sz.to_byte_array())
		rd.buffer_update(_sim._ml_lap_y, 0, ns * 4, sz.to_byte_array())
		rd.buffer_update(_sim._ml_lap_i, 0, ns * 4, sz.to_byte_array())
	else:
		# Sample the continuum IC at the cell centers of the N³ grid.
		var n3 := N * N * N
		var ey := PackedFloat32Array(); ey.resize(n3)
		var ei := PackedFloat32Array(); ei.resize(n3)
		var velz := PackedFloat32Array(); velz.resize(n3 * 4)
		var hx := 2.0 * _ext.x / float(N)
		var hy := 2.0 * _ext.y / float(N)
		var hz := 2.0 * _ext.z / float(N)
		for i in range(N):
			for j in range(N):
				for k in range(N):
					var wp := Vector3((float(i) + 0.5) * hx - _ext.x,
						(float(j) + 0.5) * hy - _ext.y,
						(float(k) + 0.5) * hz - _ext.z)
					var v := _ic_ey_ei(wp)
					var id := i + N * (j + N * k)
					ey[id] = v.x
					ei[id] = v.y
		rd.buffer_update(_sim._field_ey, 0, n3 * 4, ey.to_byte_array())
		rd.buffer_update(_sim._field_ei, 0, n3 * 4, ei.to_byte_array())
		rd.buffer_update(_sim._field_vel, 0, n3 * 16, velz.to_byte_array())


## Zero every particle mass (w=0) so the deposit skips all -> rho_mass = 0
## (the wave source coupling mr*0.001 = 0; pure linear wave from the IC).
func _zero_masses() -> void:
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var z := PackedFloat32Array()
	z.resize(np * 4)
	var cur: PackedFloat32Array = rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
	for i in range(np):
		z[i * 4] = cur[i * 4]
		z[i * 4 + 1] = cur[i * 4 + 1]
		z[i * 4 + 2] = cur[i * 4 + 2]
		z[i * 4 + 3] = 0.0
	rd.buffer_update(_sim._pos_buf, 0, np * 16, z.to_byte_array())


func _run_batch() -> void:
	_sim._run_physics_steps(BATCH)
	_step += BATCH
	_sample_field()
	if _step % 200 == 0:
		print("[M1GateIV] %d/%d steps" % [_step, STEPS_TOTAL])


func _sample_field() -> void:
	var N: int = _sim.grid_N
	var rd: RenderingDevice = _sim._rd
	var n3 := N * N * N
	var ey: PackedFloat32Array = rd.buffer_get_data(_sim._field_ey, 0, n3 * 4).to_float32_array()
	var ei: PackedFloat32Array = rd.buffer_get_data(_sim._field_ei, 0, n3 * 4).to_float32_array()
	var jc := N / 2
	var kc := N / 2
	var row := PackedFloat32Array()
	row.resize(N)
	var probe := 0.0
	for i in range(N):
		var id := i + N * (jc + N * kc)
		var rho := ey[id] + ei[id]
		row[i] = rho
		if i == _probe_ix:
			probe = rho
	_ray.append(row)
	_probe_series.append(probe)
	_t_series.append(float(_step) * _sim.dt)
	if _sim.meshless_mode and _far_site_ix >= 0:
		var sy: PackedFloat32Array = rd.buffer_get_data(_sim._ml_psi_y, 0,
			_far_site_ix * 4 + 8).to_float32_array()
		_site_series.append(sy[0])


func _finish_phase(name: String) -> void:
	var N: int = _sim.grid_N
	# ── Front speed: locate the pulse's leading edge on the +x side ──
	# Robust: (a) scan from the CENTER outward (the pulse starts at the
	# center; the box-edge cells carry raster boundary artifacts), (b) use a
	# RELATIVE threshold (the pulse amplitude decays as it spreads), (c)
	# track only a MONOTONICALLY advancing front (a receding detection is
	# noise, not the wave).
	var kx := PI / _ext.x
	var cx := N / 2
	var fronts := PackedFloat32Array()
	var t_first := 0.0
	var t_last := 0.0
	var x_first := 0.0
	var x_last := 0.0
	var max_front := -1.0e30
	for s in range(1, _ray.size()):
		var row: PackedFloat32Array = _ray[s]
		var peak := 0.0
		for i in range(N):
			var xc := (float(i) + 0.5) * (2.0 * _ext.x / float(N)) - _ext.x
			var cb := AMP_CB * cos(kx * xc)
			peak = maxf(peak, absf(row[i] - cb))
		var eps := maxf(0.25 * peak, 1e-4)
		var fx := -1.0
		var cell := 2.0 * _ext.x / float(N)
		for i in range(cx, N):
			var xc := (float(i) + 0.5) * cell - _ext.x
			var cb := AMP_CB * cos(kx * xc)
			if absf(row[i] - cb) > eps and xc > max_front - 2.0 * cell:
				fx = xc
				break
		if fx > 0.0:
			max_front = maxf(max_front, fx)
			fronts.append(fx)
			if fronts.size() == 1:
				t_first = _t_series[s]; x_first = fx
			t_last = _t_series[s]; x_last = fx
	var v_front := 0.0
	if fronts.size() >= 3 and t_last > t_first:
		v_front = (x_last - x_first) / (t_last - t_first)
	# ── Ray diagnostics: where does the pulse energy sit at t ~ 0.08, 5, 10? ──
	var diag := ""
	for s in [1, maxi(1, _ray.size() / 2), _ray.size() - 1]:
		var row: PackedFloat32Array = _ray[s]
		var peak := 0.0
		var pk_i := 0
		for i in range(N):
			var xc := (float(i) + 0.5) * (2.0 * _ext.x / float(N)) - _ext.x
			var cb := AMP_CB * cos(kx * xc)
			var d := absf(row[i] - cb)
			if d > peak:
				peak = d
				pk_i = i
		diag += " t=%.2f peak=%.3f@x=%.1f |" % [_t_series[s], peak,
			(float(pk_i) + 0.5) * (2.0 * _ext.x / float(N)) - _ext.x]
	print("[M1GateIV] %s ray: %s" % [name, diag])
	if _site_series.size() > 1:
		var first: float = _site_series[0]
		var last: float = _site_series[_site_series.size() - 1]
		var amp := 0.0
		for s in _site_series:
			amp = maxf(amp, absf(s - first))
		print("[M1GateIV] %s far-site psi_y: start=%.4f end=%.4f max|dev|=%.4f (pulse arrival would move it)"
			% [name, first, last, amp])
	# ── FFT of the probe series (radix-2, 512 points) ──
	var nf := 512
	var n_use := mini(_probe_series.size(), nf)
	var re := PackedFloat32Array(); re.resize(nf)
	var im := PackedFloat32Array(); im.resize(nf)
	for i in range(n_use):
		var w := 0.5 - 0.5 * cos(2.0 * PI * float(i) / float(nf - 1))
		re[i] = float(_probe_series[i]) * w
	for i in range(n_use, nf):
		re[i] = 0.0
	for i in range(nf):
		im[i] = 0.0
	_fft(re, im, false)
	var peaks := [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
	for i in range(1, nf / 2):
		var p := re[i] * re[i] + im[i] * im[i]
		if p > peaks[0][1]:
			peaks[2] = peaks[1]; peaks[1] = peaks[0]
			peaks[0] = [float(i) / (float(nf) * float(BATCH) * float(_sim.dt)), p]
		elif p > peaks[1][1]:
			peaks[2] = peaks[1]
			peaks[1] = [float(i) / (float(nf) * float(BATCH) * float(_sim.dt)), p]
		elif p > peaks[2][1]:
			peaks[2] = [float(i) / (float(nf) * float(BATCH) * float(_sim.dt)), p]
	var ratio := 0.0
	if peaks[1][1] > 1e-12:
		ratio = peaks[0][0] / peaks[1][0]
	print("[M1GateIV] %s: front speed=%.4f units/s (t %.3f..%.3f, x %.1f..%.1f), "
		% [name, v_front, t_first, t_last, x_first, x_last]
		+ "top-2 modes: %.4f (p=%.6f), %.4f (p=%.6f), ratio=%.3f"
		% [peaks[0][0], peaks[0][1], peaks[1][0], peaks[1][1], ratio])
	if name == "meshless":
		_meshless_result = {"v": v_front, "f1": peaks[0][0], "f2": peaks[1][0], "ratio": ratio}
	else:
		_grid_result = {"v": v_front, "f1": peaks[0][0], "f2": peaks[1][0], "ratio": ratio}


func _verdict() -> void:
	var m: Dictionary = _meshless_result
	var g: Dictionary = _grid_result
	var dv := 0.0
	if g["v"] != 0.0:
		dv = absf(m["v"] - g["v"]) / absf(g["v"])
	var dr := 0.0
	if g["ratio"] != 0.0:
		dr = absf(m["ratio"] - g["ratio"]) / absf(g["ratio"])
	print("[M1GateIV] ============ GATE-IV VERDICT ============")
	print("[M1GateIV] meshless vs grid: |Δfront|=%.1f%% (tol 5%%), |Δratio|=%.1f%% (tol 5%%)"
		% [100.0 * dv, 100.0 * dr])
	var passed := dv <= 0.05 and dr <= 0.05
	if passed:
		print("[M1GateIV] VERDICT: PASS — meshless per-site wave meets the fidelity gate → A viable")
	else:
		print("[M1GateIV] VERDICT: FAIL — out of tolerance → lean B (keep the N³ lattice waves)")


## In-place radix-2 complex FFT (GDScript, N power of two).
func _fft(re: PackedFloat32Array, im: PackedFloat32Array, invert: bool) -> void:
	var n := re.size()
	var j := 0
	for i in range(1, n):
		var bit := n >> 1
		while j & bit != 0:
			j ^= bit
			bit >>= 1
		j ^= bit
		if i < j:
			var tr := re[i]; re[i] = re[j]; re[j] = tr
			var ti := im[i]; im[i] = im[j]; im[j] = ti
	var len2 := 2
	while len2 <= n:
		var ang := (2.0 * PI / float(len2)) * (-1.0 if not invert else 1.0)
		var wr := cos(ang)
		var wi := sin(ang)
		for i in range(0, n, len2):
			var cr := 1.0
			var ci := 0.0
			for k in range(len2 / 2):
				var kk := i + k
				var jj := kk + len2 / 2
				var ur := re[jj] * cr - im[jj] * ci
				var ui := re[jj] * ci + im[jj] * cr
				re[jj] = re[kk] - ur
				im[jj] = im[kk] - ui
				re[kk] += ur
				im[kk] += ui
				var ncr := cr * wr - ci * wi
				ci = cr * wi + ci * wr
				cr = ncr
		len2 <<= 1
	if invert:
		for i in range(n):
			re[i] /= float(n)
			im[i] /= float(n)


# ═══════════════════════════════════════════════════════════════════════
# Phase C — the gated site-path prototypes (unwrapped steer + per-site source)
# variant==0 must be bit-identical to the canonical shader (same math, no
# variant branch active); variant==1 drops the mode-4 mod() wrap; variant==2
# anchors the mode-1 source at the site.
# ═══════════════════════════════════════════════════════════════════════

func _variant_setup() -> void:
	var rd: RenderingDevice = _sim._rd
	var sf = load("res://_diag/compute/m1_sites_unwrapped.glsl")
	if sf == null:
		print("[M1GateIV] FAIL: variant shader not found")
		_var_fail += 1
		return
	var spirv = sf.get_spirv()
	if spirv == null:
		print("[M1GateIV] FAIL: variant SPIR-V compile failed")
		_var_fail += 1
		return
	_var_shader = rd.shader_create_from_spirv(spirv)
	_var_pipe = rd.compute_pipeline_create(_var_shader)
	print("[M1GateIV] phase C: variant pipeline created")


## The probe's own PC floats (the canonical 17 + the variant selector).
## kappa=0 (no centroid pull), lam=1, T_steer=1, drift_cap=2.0 — a fully
## controlled steer scenario; source_strength=1.0 for the mode-1 test.
func _variant_pc_floats(mode: float) -> PackedFloat32Array:
	var N: int = _sim.grid_N
	var ml_ns := 2 * 16 * 16 * 16
	var ext: Vector3 = _sim._extents()
	var hx: float = 2.0 * ext.x / float(N)
	var hy: float = 2.0 * ext.y / float(N)
	var hz: float = 2.0 * ext.z / float(N)
	var h_min: float = minf(hx, minf(hy, hz))
	return PackedFloat32Array([mode, float(N), float(ml_ns), _sim.dt,
		hx, hy, hz, h_min * h_min, 20.0, 1.618033988749895, 1.0, 1e-3,
		2.0, 0.0, 1.0, 1.0, 4.0])


## 17-float PC for the SIM's canonical pipe (68 bytes — the canonical
## shader's push-constant contract; the 18-float PC belongs only to the
## variant pipeline).
func _variant_pc17(mode: float) -> PackedByteArray:
	var f := _variant_pc_floats(mode)
	var out := PackedFloat32Array()
	out.resize(17)
	for i in range(17):
		out[i] = f[i]
	return out.to_byte_array()


func _variant_pc(mode: float, variant: float) -> PackedByteArray:
	var f := _variant_pc_floats(mode)
	var out := PackedFloat32Array()
	out.resize(18)
	for i in range(18):
		out[i] = f[i] if i < 17 else variant
	return out.to_byte_array()


func _dispatch_pc(pipe: RID, pc: PackedByteArray) -> void:
	var rd: RenderingDevice = _sim._rd
	var ns := 2 * 16 * 16 * 16
	var cl := rd.compute_list_begin()
	rd.compute_list_bind_compute_pipeline(cl, pipe)
	rd.compute_list_bind_uniform_set(cl, _sim._us_cell_0, 0)
	rd.compute_list_set_push_constant(cl, pc, pc.size())
	rd.compute_list_dispatch(cl, int(ceil(float(ns) / 64.0)), 1, 1)
	rd.compute_list_end()
	# The sim's RD is the GLOBAL device: submit/sync is local-only (errors).
	# The subsequent buffer_get_data readbacks self-stall and execute the
	# recorded list (the verify scenes' established pattern).


func _read_sites() -> PackedFloat32Array:
	var ns := 2 * 16 * 16 * 16
	return _sim._rd.buffer_get_data(_sim._ml_sites, 0, ns * 16).to_float32_array()


func _write_sites(arr: PackedFloat32Array) -> void:
	_sim._rd.buffer_update(_sim._ml_sites, 0, arr.size() * 4, arr.to_byte_array())


func _write_floats(rid: RID, arr: PackedFloat32Array) -> void:
	_sim._rd.buffer_update(rid, 0, arr.size() * 4, arr.to_byte_array())


## Controlled steer scenario: site 0 sits just inside the +x edge with a
## large outward momentum; everything else is inert (psi=pi=0).
func _variant_steer_state() -> PackedFloat32Array:
	var ns := 2 * 16 * 16 * 16
	var sites := PackedFloat32Array(); sites.resize(ns * 4)
	var ext: Vector3 = _sim._extents()
	var Lx := 2.0 * ext.x
	var Ly := 2.0 * ext.y
	var Lz := 2.0 * ext.z
	sites[0] = Lx - 0.05          # just inside the +x edge
	sites[1] = 0.5 * Ly
	sites[2] = 0.5 * Lz
	return sites


func _variant_tests() -> void:
	var ns := 2 * 16 * 16 * 16
	var rd: RenderingDevice = _sim._rd
	var z_f := _zeros(ns)
	var z_v := _zeros(ns * 4)
	var ones_f := _zeros(ns)
	ones_f[0] = 1.0
	var pi10_f := _zeros(ns)
	pi10_f[0] = 10.0

	_write_sites(_variant_steer_state())
	_write_floats(_sim._ml_psi_y, ones_f)
	_write_floats(_sim._ml_psi_i, ones_f)
	_write_floats(_sim._ml_pi_y, pi10_f)
	_write_floats(_sim._ml_pi_i, pi10_f)
	_write_floats(_sim._ml_lap_y, z_f)
	_write_floats(_sim._ml_lap_i, z_f)
	rd.buffer_update(_sim._ml_cen, 0, ns * 16, z_v.to_byte_array())

	# ── T1: canonical steer (the sim's pipe, the probe's controlled PC) ──
	_dispatch_pc(_sim._cell_pipe, _variant_pc17(4.0))
	var canon := _read_sites()
	# ── T2: variant-0 steer (must be bit-identical to canonical) ──
	_write_sites(_variant_steer_state())
	_dispatch_pc(_var_pipe, _variant_pc(4.0, 0.0))
	var var0 := _read_sites()
	# ── T3: variant-1 steer (unwrapped — site 0 leaves the window) ──
	_write_sites(_variant_steer_state())
	_dispatch_pc(_var_pipe, _variant_pc(4.0, 1.0))
	var var1 := _read_sites()

	var ext: Vector3 = _sim._extents()
	var Lx := 2.0 * ext.x
	var xc := canon[0]
	var x0 := var0[0]
	var x1 := var1[0]
	var ident_ok := true
	for i in range(ns * 4):
		if canon[i] != var0[i]:
			ident_ok = false
			break
	# Expected displacement: drift = lam·(pi_y+pi_i)/rho·T_steer = 1·20/2·1 =
	# 10 -> capped by the 3D vector-length drift_cap=2.0: disp =
	# (2/√12)·(1,1,1)·... — the cap applies to |disp|, so per-axis =
	# 2.0/√3 = 1.1547; wrapped x = mod(242.75+1.1547, Lx) = 1.1047; unwrapped
	# x = 242.75+1.1547 = 243.9047 (outside [0, Lx)).
	var per_axis := 2.0 / sqrt(3.0)   # the 3D drift-cap on (2,2,2)
	var exp_wrap := fmod(Lx - 0.05 + per_axis, Lx)
	var exp_unwrap := Lx - 0.05 + per_axis
	print("[M1GateIV] T1 canon site0 x=%.4f (expect wrapped ~%.4f)" % [xc, exp_wrap])
	print("[M1GateIV] T2 variant0 site0 x=%.4f bit-identical=%s" % [x0, ident_ok])
	print("[M1GateIV] T3 variant1 site0 x=%.4f (expect unwrapped ~%.4f, outside [0,%.1f))"
		% [x1, exp_unwrap, Lx])
	var t1_ok := absf(xc - exp_wrap) < 1e-3
	var t3_ok := absf(x1 - exp_unwrap) < 1e-3 and (x1 < 0.0 or x1 >= Lx)
	if not (ident_ok and t1_ok and t3_ok):
		_var_fail += 1
		print("[M1GateIV] FAIL: steer variant checks (ident=%s t1=%s t3=%s)"
			% [ident_ok, t1_ok, t3_ok])
	else:
		print("[M1GateIV] PASS: steer variant checks (bit-identical control, wrap = exactly Lx)")

	# ── T4/T5: per-site source (mode 1 leapfrog) vs CPU expectation ──
	var sites2 := _variant_steer_state()
	sites2[0] = 0.1 * Lx
	_write_sites(sites2)
	_write_floats(_sim._ml_psi_y, z_f)
	_write_floats(_sim._ml_psi_i, z_f)
	_write_floats(_sim._ml_pi_y, z_f)
	_write_floats(_sim._ml_pi_i, z_f)
	_write_floats(_sim._ml_lap_y, z_f)
	_write_floats(_sim._ml_lap_i, z_f)
	var vol1 := _zeros(ns)
	vol1[0] = 1.0
	_write_floats(_sim._ml_vol, vol1)

	_dispatch_pc(_var_pipe, _variant_pc(1.0, 0.0))
	var p0: PackedFloat32Array = rd.buffer_get_data(_sim._ml_psi_y, 0, ns * 4).to_float32_array()
	var dt_f: float = _sim.dt
	var N: int = _sim.grid_N
	var hx: float = 2.0 * ext.x / float(N)
	var halfn := float(N) * 0.5
	var sx := sites2[0] / hx
	var dx_c := (sx - halfn * 0.7) / halfn
	var dy_c := (0.5 * float(N) - halfn * 0.8) / halfn
	var dz_c := (0.5 * float(N) - halfn * 0.6) / halfn
	var r2c := dx_c * dx_c + dy_c * dy_c + dz_c * dz_c
	var src_c := exp(-r2c * 4.0)
	var exp_c: float = dt_f * dt_f * src_c
	var t4_ok := absf(p0[0] - exp_c) < 1e-4 * maxf(absf(exp_c), 1.0)

	_write_floats(_sim._ml_psi_y, z_f)
	_write_floats(_sim._ml_psi_i, z_f)
	_write_floats(_sim._ml_pi_y, z_f)
	_write_floats(_sim._ml_pi_i, z_f)
	_dispatch_pc(_var_pipe, _variant_pc(1.0, 2.0))
	var p2: PackedFloat32Array = rd.buffer_get_data(_sim._ml_psi_y, 0, ns * 4).to_float32_array()
	var dx_s := (sx - halfn) / halfn
	var dy_s := (0.5 * float(N) - halfn) / halfn
	var dz_s := (0.5 * float(N) - halfn) / halfn
	var r2s := dx_s * dx_s + dy_s * dy_s + dz_s * dz_s
	var src_s := exp(-r2s * 4.0)
	var exp_s: float = dt_f * dt_f * src_s
	var t5_ok := absf(p2[0] - exp_s) < 1e-4 * maxf(absf(exp_s), 1.0)
	if not (t4_ok and t5_ok):
		_var_fail += 1
		print("[M1GateIV] FAIL: per-site source checks (canon=%s site=%s, got %.6f/%.6f exp %.6f/%.6f)"
			% [t4_ok, t5_ok, p0[0], p2[0], exp_c, exp_s])
	else:
		print("[M1GateIV] PASS: per-site source checks (canonical and site-anchored match their formulas)")

	print("[M1GateIV] phase C verdict: %s" % ("PASS" if _var_fail == 0 else "FAIL"))
	_restore_meshless_state()


## Put the sim's meshless state back to a sane default (the phase-C tests
## scrambled psi/pi/sites on the shared buffers).
func _restore_meshless_state() -> void:
	var ns := 2 * 16 * 16 * 16
	var z := _zeros(ns)   # float buffers are ns floats, NOT ns*4
	_write_floats(_sim._ml_psi_y, z)
	_write_floats(_sim._ml_psi_i, z)
	_write_floats(_sim._ml_pi_y, z)
	_write_floats(_sim._ml_pi_i, z)
	_write_floats(_sim._ml_lap_y, z)
	_write_floats(_sim._ml_lap_i, z)
	_write_sites(_variant_steer_state())


func _zeros(n: int) -> PackedFloat32Array:
	var a := PackedFloat32Array()
	a.resize(n)
	return a
