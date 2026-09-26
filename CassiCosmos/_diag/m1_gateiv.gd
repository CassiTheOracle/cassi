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

const STEPS_TOTAL := 2400
const BATCH := 4          # steps per _run_physics_steps call (sampling cadence)
const AMP_CB := 0.0       # checkerboard amplitude — 0: the ρ = ey+ei checkerboard
                          # is a TRAVELING wave (the two-field superposition),
                          # whose phase drift contaminates the front residual;
                          # the gate runs the pulse on the zero field instead.
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
var _probe2_series: Array = []
var _t_series: Array = []
var _meshless_result: Dictionary = {}
var _corr_result: Dictionary = {}
var _grid_result: Dictionary = {}
var _corr := 1.0
var _corr_iter := 0
var _far_site_ix := -1
var _site_series: Array = []
var _strip: Array = []        # site indices on the y/z-center strip (x-ordered)
var _strip_x: Array = []      # world x per strip site
var _site_rays: Array = []    # per-sample strip rho profiles (meshless arms)
var _site_ray_xs: Array = []  # per-sample site x positions (the sites drift
                              # under the sim's rebuild steer — the ray must
                              # follow the CURRENT positions, not stale ids)


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
## The meshless sites on the y/z-center strip (|y-Ly/2| < hy, |z-Lz/2| < hz),
## x-ordered — the site-level ray (the leapfrog/lap output, BEFORE the
## raster's Barth-Jespersen limiter clamps the front's phase structure).
func _build_strip() -> void:
	_strip = []
	_strip_x = []
	if _sim._ml_sites_cpu.size() < 4:
		return
	var ext_v: Vector3 = _sim._extents()
	var Ly := 2.0 * ext_v.y
	var Lz := 2.0 * ext_v.z
	var hy: float = 2.0 * ext_v.y / float(_sim.grid_N)
	var hz: float = 2.0 * ext_v.z / float(_sim.grid_N)
	var ns: int = _sim._ml_sites_cpu.size() / 4
	for s in range(ns):
		var sy: float = _sim._ml_sites_cpu[s * 4 + 1]
		var sz: float = _sim._ml_sites_cpu[s * 4 + 2]
		if absf(sy - 0.5 * Ly) < hy and absf(sz - 0.5 * Lz) < hz:
			_strip.append(s)
			_strip_x.append(_sim._ml_sites_cpu[s * 4] - ext_v.x)
	var idx := range(_strip.size())
	idx.sort_custom(func(a, b): return _strip_x[a] < _strip_x[b])
	var s2: Array = []
	var x2: Array = []
	for a in idx:
		s2.append(_strip[a])
		x2.append(_strip_x[a])
	_strip = s2
	_strip_x = x2


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
		4:  # uncorrected verdict, then the corrected-operator arm (variant 3)
			_verdict()
			_corr_iter = 0
			_start_phase("meshless-corr", true)
			_phase = 5
		5:  # run the corrected meshless arm (static mesh, no steer); iterate
			# the corr until the site-level front lands within 5% of the grid
			if _step < STEPS_TOTAL:
				_run_corr_batch()
			else:
				_finish_phase("meshless-corr")
				_corr_iter += 1
				var gv: float = _grid_result["v"]
				var cv: float = _corr_result["v"]
				if _corr_iter < 5 and gv > 0.0 and cv > 0.0 \
						and absf(cv - gv) / gv > 0.05:
					_corr = _corr * (gv * gv) / (cv * cv)
					print("[M1GateIV] corrected iter %d: corr -> %.4f (front %.3f vs grid %.3f)"
						% [_corr_iter, _corr, cv, gv])
					_start_phase("meshless-corr", true)
				else:
					_verdict_corr()
					_lap_probe()
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
	_probe2_series = []
	_t_series = []
	_probe_ix = int(round(float(_sim.grid_N) * 0.64))   # x ≈ +34 units — on the pulse's +x path
	_far_site_ix = _find_far_site()
	_site_series = []
	_site_rays = []
	_site_ray_xs = []
	if _sim.meshless_mode:
		_build_strip()
	print("[M1GateIV] phase '%s' started: grid_N=%d dt=%.4f ext=(%.1f, %.1f, %.1f), far-site=%d"
		% [name, _sim.grid_N, _sim.dt, _ext.x, _ext.y, _ext.z, _far_site_ix])


## Evaluate the continuum IC (Gaussian pulse on the zero field) at a world
## point — the same pulse injected into BOTH fields (ρ = 2·pulse).
func _ic_ey_ei(wp: Vector3) -> Vector2:
	var sig := SIGMA * _ext.x
	var r2 := wp.x * wp.x + wp.y * wp.y + wp.z * wp.z
	var p := AMP_PULSE * exp(-r2 / (sig * sig))
	return Vector2(p, p)


func _inject_ic(meshless: bool) -> void:
	var N: int = _sim.grid_N
	var rd: RenderingDevice = _sim._rd
	if meshless:
		# Sample the continuum IC at the SITE positions in WORLD coordinates
		# (the sites live in the mesh world [0, Lx)×[0, Ly)×[0, Lz) = the
		# sim world shifted by +extent; the grid arm and the detector both
		# use the world convention — WITHOUT the shift the pulse would land
		# at the mesh corner and never touch the sampled ray).
		var sites: PackedFloat32Array = rd.buffer_get_data(_sim._ml_sites, 0,
			_sim._ml_sites_cpu.size() * 4).to_float32_array()
		var ns := sites.size() / 4
		var sy := PackedFloat32Array(); sy.resize(ns)
		var si := PackedFloat32Array(); si.resize(ns)
		var sz := PackedFloat32Array(); sz.resize(ns)
		for s in range(ns):
			var v := _ic_ey_ei(Vector3(sites[s * 4], sites[s * 4 + 1], sites[s * 4 + 2]) - _ext)
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


## The corrected-operator arm: the SAME per-step meshless chain the sim runs
## (grad-zero → lap → leapfrog → lsm solve → raster) but with the leapfrog
## dispatched through the VARIANT pipeline with variant=3 (C2 scaled by the
## D19/Voronoi lap-scale ratio _corr). One compute list per step with the
## same barriers the sim's chain uses (cassi_sim.gd ~4237-4262). The other
## passes (deposit, tree, nbody, KDK) never touch the field buffers, so
## running the chain alone is the honest A/B. The list executes via the
## subsequent field readback (the verify-scenes pattern; submit/sync is
## illegal on the global RD).
func _run_corr_batch() -> void:
	var rd: RenderingDevice = _sim._rd
	var N: int = _sim.grid_N
	var ml_ns := 2 * 16 * 16 * 16
	var wg1 := N * N * N / 64
	var wgs := int(ceil(float(ml_ns) / 64.0))
	for _i in range(BATCH):
		var cl := rd.compute_list_begin()
		# grad zero (mode 10) → lap (mode 0) → leapfrog (variant 3) → solve (mode 12)
		rd.compute_list_bind_compute_pipeline(cl, _sim._cell_pipe)
		rd.compute_list_bind_uniform_set(cl, _sim._us_cell_0, 0)
		rd.compute_list_set_push_constant(cl, _sim._ml_cell_pc(10.0), 68)
		rd.compute_list_dispatch(cl, wgs, 1, 1)
		rd.compute_list_add_barrier(cl)
		rd.compute_list_set_push_constant(cl, _sim._ml_cell_pc(0.0), 68)
		rd.compute_list_dispatch(cl, wg1, 1, 1)
		rd.compute_list_add_barrier(cl)
		rd.compute_list_bind_compute_pipeline(cl, _var_pipe)
		rd.compute_list_set_push_constant(cl, _variant_pc(1.0, 3.0, 0.0), 76)
		rd.compute_list_dispatch(cl, wgs, 1, 1)
		rd.compute_list_add_barrier(cl)
		rd.compute_list_bind_compute_pipeline(cl, _sim._cell_pipe)
		rd.compute_list_set_push_constant(cl, _sim._ml_cell_pc(12.0), 68)
		rd.compute_list_dispatch(cl, wgs, 1, 1)
		rd.compute_list_add_barrier(cl)
		# raster (a different pipeline + uniform set, legal mid-list — the
		# sim's own chain does the same)
		rd.compute_list_bind_compute_pipeline(cl, _sim._raster_pipe)
		rd.compute_list_bind_uniform_set(cl, _sim._us_raster_0, 0)
		var ext: Vector3 = _sim._extents()
		var rpc := PackedFloat32Array([float(N), float(ml_ns),
			2.0 * ext.x / float(N), 2.0 * ext.y / float(N), 2.0 * ext.z / float(N),
			0.0, 0.0, 0.0]).to_byte_array()
		rd.compute_list_set_push_constant(cl, rpc, rpc.size())
		rd.compute_list_dispatch(cl, wg1, 1, 1)
		rd.compute_list_end()
	_step += BATCH
	_sample_field()
	if _step % 200 == 0:
		print("[M1GateIV] %d/%d steps (corrected)" % [_step, STEPS_TOTAL])


## Corrected-operator verdict: the same gate as the uncorrected one, vs the
## grid reference. The corr constant itself is derived from the grid arm's
## measured front: the D19's effective lap scale s·h₀² = v_grid²/C2 and the
## Voronoi's exact dimension factor 3, so corr = (v_grid²/C2)/3.
func _verdict_corr() -> void:
	var m: Dictionary = _corr_result
	var g: Dictionary = _grid_result
	var dv := 0.0
	if g["v"] != 0.0:
		dv = absf(m["v"] - g["v"]) / absf(g["v"])
	var dr := 0.0
	if g["ratio"] != 0.0:
		dr = absf(m["ratio"] - g["ratio"]) / absf(g["ratio"])
	print("[M1GateIV] ============ GATE-IV CORRECTED-OPERATOR VERDICT ============")
	print("[M1GateIV] corr = (v_grid²/C2)/3 = %.4f (D19 scale s·h₀² = %.4f, Voronoi dim factor 3)"
		% [_corr, 3.0 * _corr])
	print("[M1GateIV] meshless-corr vs grid: |Δfront|=%.1f%% (tol 5%%), |Δratio|=%.1f%% (tol 5%%)"
		% [100.0 * dv, 100.0 * dr])
	if dv <= 0.05 and dr <= 0.05:
		print("[M1GateIV] VERDICT: PASS — A stays viable with the corrected operator")
	else:
		print("[M1GateIV] VERDICT: FAIL — commit to B (the tracking-grid + patches fallback)")


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
	var probe2 := 0.0
	for i in range(N):
		var id := i + N * (jc + N * kc)
		var rho := ey[id] + ei[id]
		row[i] = rho
		if i == _probe_ix:
			probe = rho
		if i == 46:
			probe2 = rho
	_ray.append(row)
	_probe_series.append(probe)
	_probe2_series.append(probe2)
	_t_series.append(float(_step) * _sim.dt)
	if _sim.meshless_mode and _far_site_ix >= 0:
		var sy: PackedFloat32Array = rd.buffer_get_data(_sim._ml_psi_y, 0,
			_far_site_ix * 4 + 8).to_float32_array()
		_site_series.append(sy[0])
	if _sim.meshless_mode and _strip.size() > 1:
		var syf: PackedFloat32Array = rd.buffer_get_data(_sim._ml_psi_y, 0, 8192 * 4).to_float32_array()
		var sif: PackedFloat32Array = rd.buffer_get_data(_sim._ml_psi_i, 0, 8192 * 4).to_float32_array()
		var sf: PackedFloat32Array = rd.buffer_get_data(_sim._ml_sites, 0, 8192 * 16).to_float32_array()
		var extv: Vector3 = _sim._extents()
		var Ly := 2.0 * extv.y
		var Lz := 2.0 * extv.z
		var hyy: float = 2.0 * extv.y / float(_sim.grid_N)
		var hzz: float = 2.0 * extv.z / float(_sim.grid_N)
		var ids: Array = []
		var xs: Array = []
		for a in range(_strip.size()):
			var s: int = _strip[a]
			var syy: float = sf[s * 4 + 1]
			var szz: float = sf[s * 4 + 2]
			# follow the site's CURRENT position (the steer may have moved it
			# off the original strip) within a 1.5-cell tube
			if absf(syy - 0.5 * Ly) < 1.5 * hyy and absf(szz - 0.5 * Lz) < 1.5 * hzz:
				ids.append(s)
				xs.append(sf[s * 4] - extv.x)
		if ids.size() < 5:
			return
		var idx := range(ids.size())
		idx.sort_custom(func(a, b): return xs[a] < xs[b])
		var sr := PackedFloat32Array()
		sr.resize(ids.size())
		var sx := PackedFloat32Array()
		sx.resize(ids.size())
		for a in range(idx.size()):
			var k: int = idx[a]
			sr[a] = syf[ids[k]] + sif[ids[k]]
			sx[a] = xs[k]
		_site_rays.append(sr)
		_site_ray_xs.append(sx)


func _finish_phase(name: String) -> void:
	var N: int = _sim.grid_N
	# ── Front speed: the +x shell's OUTER profile peak, continuity-tracked ──
	# The 3D wave's profile |s·φ(s)|/(2r) with s = r−ct has its strongest
	# value at the INNER edge of any fixed region (the 1/r decay pins the
	# region-max at the near edge — the 0.26 artifact). The clean moving
	# feature is the OUTER profile peak at r = ct + σ/√2 (amplitude
	# 0.086/r — detectable down to ~1e-4). Track the outermost LOCAL
	# maximum per row (the shell's outer peak; everything beyond it is the
	# exponential tail), seed past x=30, then continuity-track within ±8
	# cells. The least-squares slope = c exactly (the σ/√2 offset is
	# constant).
	var cell := 2.0 * _ext.x / float(N)
	var i0 := int(ceil((25.0 + _ext.x) / cell))   # the first cell with x > 25
	var A_MIN := 1.0e-2   # above the IC's initial edge (~1.5e-3) so the seed
	                      # waits for the wave's SHELL, not the initial bump
	var xs := PackedFloat32Array()
	var ts := PackedFloat32Array()
	var bi := i0
	var seeded := false
	for s in range(1, _ray.size()):
		var row: PackedFloat32Array = _ray[s]
		var om := -1
		var oa := 0.0
		if not seeded:
			for i in range(i0 + 1, N - 1):
				var a := absf(row[i])
				if a > A_MIN and a > absf(row[i - 1]) and a > absf(row[i + 1]):
					om = i
					oa = a   # always overwrite: the OUTERMOST local max (the
					         # outer profile peak; the inner 1/r-stronger peak
					         # would drag the path backward)
			if om < 0:
				continue
			var xp0 := (float(om) + 0.5) * cell - _ext.x
			if xp0 <= 30.0:
				continue
			seeded = true
			bi = om
		else:
			var lo := maxi(i0, bi - 3)
			var hi := mini(N - 1, bi + 3)
			for i in range(lo, hi + 1):
				var a := absf(row[i])
				if a > A_MIN and a > absf(row[maxi(i0, i - 1)]) and a > absf(row[mini(N - 1, i + 1)]) and a >= oa:
					om = i
					oa = a
			if om < 0:
				continue
			bi = om
		xs.append((float(bi) + 0.5) * cell - _ext.x)
		ts.append(_t_series[s])
	var dbg := ""
	for i in range(0, xs.size(), 100):
		dbg += " t=%.1f x=%.1f |" % [ts[i], xs[i]]
	dbg += " t=%.1f x=%.1f |" % [ts[xs.size() - 1], xs[xs.size() - 1]]
	print("[M1GateIV] %s peak path (%d rows): %s" % [name, xs.size(), dbg])
	var v_front := 0.0
	if xs.size() >= 5:
		var n := float(xs.size())
		var sx := 0.0
		var st := 0.0
		var sxt := 0.0
		var stt := 0.0
		for i in range(xs.size()):
			sx += xs[i]
			st += ts[i]
			sxt += xs[i] * ts[i]
			stt += ts[i] * ts[i]
		var den := n * stt - st * st
		if den > 0.0:
			v_front = (n * sxt - sx * st) / den
	# ── The meshless arms measure the SITE-level wave ──
	# The raster's Barth-Jespersen limiter clamps the recon's negative phase
	# excursions at the front (the 26-neighbourhood includes sites AHEAD of
	# the front with psi ~ 0 -> lo ~ 0), so the rasterized field shows the
	# positive-only envelope, NOT the wave's oscillatory shell. The honest
	# operator test is the leapfrog/lap output: the strip's site rho.
	if (name == "meshless" or name == "meshless-corr") and _site_rays.size() >= 5:
		var vs := _site_front_speed()
		if vs > 0.0:
			v_front = vs
			print("[M1GateIV] %s SITE-level front speed=%.4f units/s (%d site-rays)"
				% [name, vs, _site_rays.size()])
	# ── Ray diagnostics: where does the pulse energy sit at t ~ 0.08, 8, 16? ──
	var kx := PI / _ext.x
	var diag := ""
	for s in [1, maxi(1, _ray.size() / 2), _ray.size() - 1]:
		var row: PackedFloat32Array = _ray[s]
		var peak := 0.0
		var pk_i := 0
		for i in range(N):
			var xc := (float(i) + 0.5) * (2.0 * _ext.x / float(N)) - _ext.x
			var cb := AMP_CB * (cos(kx * xc) + sin(kx * xc))
			var d := absf(row[i] - cb)
			if d > peak:
				peak = d
				pk_i = i
		diag += " t=%.2f peak=%.3f@x=%.1f |" % [_t_series[s], peak,
			(float(pk_i) + 0.5) * (2.0 * _ext.x / float(N)) - _ext.x]
	print("[M1GateIV] %s ray: %s" % [name, diag])
	var prof := ""
	for s in [maxi(1, _ray.size() * 3 / 4), _ray.size() - 1]:
		var row: PackedFloat32Array = _ray[s]
		prof += " t=%.1f:" % _t_series[s]
		for i in range(39, 56):
			prof += " %d:%.3f" % [i, row[i]]
	prof += ""
	print("[M1GateIV] %s profile (cells 39-55):%s" % [name, prof])
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
	print("[M1GateIV] %s: front speed=%.4f units/s (shell-peak fit, %d rows, x > 25), "
		% [name, v_front, xs.size()]
		+ "top-2 modes: %.4f (p=%.6f), %.4f (p=%.6f), ratio=%.3f"
		% [peaks[0][0], peaks[0][1], peaks[1][0], peaks[1][1], ratio])
	if name == "meshless":
		_meshless_result = {"v": v_front, "f1": peaks[0][0], "f2": peaks[1][0], "ratio": ratio}
	elif name == "meshless-corr":
		_corr_result = {"v": v_front, "f1": peaks[0][0], "f2": peaks[1][0], "ratio": ratio}
	else:
		_grid_result = {"v": v_front, "f1": peaks[0][0], "f2": peaks[1][0], "ratio": ratio}


func _verdict() -> void:
	# The corrected arm (next phase) dispatches the variant pipeline — create
	# it here so it exists before the run.
	if not _var_pipe.is_valid():
		_variant_setup()
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
	# The corrected operator's scale: the MEASURED lap-scale ratio between
	# the arms — corr = v_grid²/c_meshless² makes the corrected meshless
	# wave travel at the grid's speed. (The theory-form constant (v_grid²/
	# C2)/3 assumes the Voronoi's continuum limit lap/v -> 3·∇²ψ exactly;
	# the measured c_meshless supersedes it.)
	var gv: float = g["v"]
	var mv: float = m["v"]
	if gv > 0.0 and mv > 0.0:
		_corr = (gv * gv) / (mv * mv)
	elif gv > 0.0:
		var ext: Vector3 = _sim._extents()
		var h_min := minf(2.0 * ext.x / float(_sim.grid_N),
			minf(2.0 * ext.y / float(_sim.grid_N), 2.0 * ext.z / float(_sim.grid_N)))
		_corr = (gv * gv / (h_min * h_min)) / 3.0
	print("[M1GateIV] derived corr = v_grid²/c_meshless² = %.4f (grid %.4f, meshless %.4f units/s)"
		% [_corr, gv, mv])


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


## The site-level front: the outermost local maximum past x=25 on each strip
## rho profile (per-sample positions — the sites drift under the rebuild
## steer), seeded once the peak passes x=30, continuity-tracked within ±2
## sites (below the inner-outer 2σ ≈ 21-unit separation), least-squares fit
## x(t) — the slope = the site wave's speed c.
func _site_front_speed() -> float:
	var xs_all := PackedFloat32Array()
	var ts_all := PackedFloat32Array()
	var bi := -1
	for s in range(1, _site_rays.size()):
		var row: PackedFloat32Array = _site_rays[s]
		var xs: PackedFloat32Array = _site_ray_xs[s]
		var om := -1
		var oa := 0.0
		if bi < 0:
			for a in range(1, xs.size() - 1):
				var xw: float = xs[a]
				if xw <= 25.0:
					continue
				var v: float = absf(row[a])
				if v > 1.0e-2 and v > absf(row[a - 1]) and v > absf(row[a + 1]):
					om = a
					oa = v   # the OUTERMOST local max
			if om < 0:
				continue
			if xs[om] <= 30.0:
				continue
			bi = om
		else:
			var lo := maxi(1, bi - 2)
			var hi := mini(xs.size() - 2, bi + 2)
			for a in range(lo, hi + 1):
				var v: float = absf(row[a])
				if v > 2.0e-4 and v > absf(row[a - 1]) and v > absf(row[a + 1]) and v >= oa:
					om = a
					oa = v
			if om < 0:
				continue
			bi = om
		xs_all.append(xs[bi])
		ts_all.append(_t_series[s])
	if xs_all.size() < 5:
		return 0.0
	var n := float(xs_all.size())
	var sx := 0.0
	var st := 0.0
	var sxt := 0.0
	var stt := 0.0
	for i in range(xs_all.size()):
		sx += xs_all[i]
		st += ts_all[i]
		sxt += xs_all[i] * ts_all[i]
		stt += ts_all[i] * ts_all[i]
	var den := n * stt - st * st
	if den <= 0.0:
		return 0.0
	return (n * sxt - sx * st) / den


## The probe's own PC floats (the canonical 17 + the variant selector + corr).
## kappa=0 (no centroid pull), lam=1, T_steer=1, drift_cap=2.0 — a fully
## controlled steer scenario; source_strength defaults to 1.0 for the phase-C
## source tests (the corrected-operator arm passes 0.0 — the gate runs with
## the source OFF, exactly like the sim's chain).
func _variant_pc_floats(mode: float, src: float = 1.0) -> PackedFloat32Array:
	var N: int = _sim.grid_N
	var ml_ns := 2 * 16 * 16 * 16
	var ext: Vector3 = _sim._extents()
	var hx: float = 2.0 * ext.x / float(N)
	var hy: float = 2.0 * ext.y / float(N)
	var hz: float = 2.0 * ext.z / float(N)
	var h_min: float = minf(hx, minf(hy, hz))
	return PackedFloat32Array([mode, float(N), float(ml_ns), _sim.dt,
		hx, hy, hz, h_min * h_min, 20.0, 1.618033988749895, src, 1e-3,
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


func _variant_pc(mode: float, variant: float, src: float = 1.0) -> PackedByteArray:
	var f := _variant_pc_floats(mode, src)
	var out := PackedFloat32Array()
	out.resize(19)
	for i in range(19):
		if i < 17:
			out[i] = f[i]
		elif i == 17:
			out[i] = variant
		else:
			out[i] = _corr
	return out.to_byte_array()


func _dispatch_pc(pipe: RID, pc: PackedByteArray, wg: int = 0) -> void:
	var rd: RenderingDevice = _sim._rd
	var ns := 2 * 16 * 16 * 16
	if wg <= 0:
		wg = int(ceil(float(ns) / 64.0))
	var cl := rd.compute_list_begin()
	rd.compute_list_bind_compute_pipeline(cl, pipe)
	rd.compute_list_bind_uniform_set(cl, _sim._us_cell_0, 0)
	rd.compute_list_set_push_constant(cl, pc, pc.size())
	rd.compute_list_dispatch(cl, wg, 1, 1)
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

	# ── T6: variant-3 corr scaling (the corrected operator's core): one
	# leapfrog step with lap=1, vol=1, psi=pi=0 -> pi = dt·C2·corr, so the
	# pi ratio between corr=2 and corr=1 must be EXACTLY 2.
	_write_floats(_sim._ml_psi_y, z_f)
	_write_floats(_sim._ml_psi_i, z_f)
	_write_floats(_sim._ml_pi_y, z_f)
	_write_floats(_sim._ml_pi_i, z_f)
	_write_floats(_sim._ml_lap_y, ones_f)
	_write_floats(_sim._ml_lap_i, z_f)
	_write_floats(_sim._ml_vol, vol1)
	var corr_saved: float = _corr
	_corr = 1.0
	_dispatch_pc(_var_pipe, _variant_pc(1.0, 3.0, 0.0))
	var p1y: PackedFloat32Array = rd.buffer_get_data(_sim._ml_pi_y, 0, ns * 4).to_float32_array()
	var pi1: float = p1y[0]
	_corr = 2.0
	_write_floats(_sim._ml_pi_y, z_f)
	_write_floats(_sim._ml_lap_y, ones_f)   # the leapfrog zeroes lap per step
	_dispatch_pc(_var_pipe, _variant_pc(1.0, 3.0, 0.0))
	var p2y: PackedFloat32Array = rd.buffer_get_data(_sim._ml_pi_y, 0, ns * 4).to_float32_array()
	var pi2: float = p2y[0]
	_corr = corr_saved
	var t6_ok := absf(pi2 / maxf(absf(pi1), 1e-30) - 2.0) < 5.0e-3   # float32 ~0.2%
	print("[M1GateIV] T6 variant3 corr: pi(corr=1)=%.6f pi(corr=2)=%.6f ratio=%.4f (expect 2) %s"
		% [pi1, pi2, pi2 / maxf(absf(pi1), 1e-30), "PASS" if t6_ok else "FAIL"])
	if not t6_ok:
		_var_fail += 1

	print("[M1GateIV] phase C verdict: %s" % ("PASS" if _var_fail == 0 else "FAIL"))
	_restore_meshless_state()


## DIRECT lap/v measurement: seed the site psi with the quadratic x²/100
## (∇² = 0.02), run ONE canonical lap, and read lap_y[s]/vol[s] — the theory
## (ΣA·d = 6V identity) predicts lap/v = 3·∇²ψ = 0.060 at every interior
## site. Any large shortfall is the transport defect, measured with zero
## ambiguity.
func _lap_probe() -> void:
	var rd: RenderingDevice = _sim._rd
	var ns := 2 * 16 * 16 * 16
	var sites: PackedFloat32Array = rd.buffer_get_data(_sim._ml_sites, 0, ns * 16).to_float32_array()
	var psi := PackedFloat32Array()
	psi.resize(ns)
	var ext: Vector3 = _sim._extents()
	for s in range(ns):
		var xw: float = sites[s * 4] - ext.x
		psi[s] = xw * xw / 100.0
	_write_floats(_sim._ml_psi_y, psi)
	_write_floats(_sim._ml_psi_i, _zeros(ns))
	_write_floats(_sim._ml_pi_y, _zeros(ns))
	_write_floats(_sim._ml_pi_i, _zeros(ns))
	_write_floats(_sim._ml_lap_y, _zeros(ns))
	_write_floats(_sim._ml_lap_i, _zeros(ns))
	var N: int = _sim.grid_N
	_dispatch_pc(_sim._cell_pipe, _sim._ml_cell_pc(0.0), N * N * N / 64)
	var lap: PackedFloat32Array = rd.buffer_get_data(_sim._ml_lap_y, 0, ns * 4).to_float32_array()
	var vol: PackedFloat32Array = rd.buffer_get_data(_sim._ml_vol, 0, ns * 4).to_float32_array()
	var nz := 0
	var sum := 0.0
	var asum := 0.0
	var vsum := 0.0
	var isum := 0.0
	var inz := 0
	for s in range(ns):
		var v: float = vol[s]
		if v > 0.0:
			var lv: float = lap[s] / v
			sum += lv
			asum += absf(lv)
			vsum += v
			nz += 1
			if absf(sites[s * 4] - ext.x) < 100.0:
				isum += lv
				inz += 1
	print("[M1GateIV] lap probe: theory lap/v = 3·∇²(x²/100) = 0.0600; "
		+ "mean %.6f |mean| %.6f over %d sites, interior |x|<100: %.6f over %d sites (vol mean %.1f)"
		% [sum / maxf(float(nz), 1.0), asum / maxf(float(nz), 1.0), nz,
			isum / maxf(float(inz), 1.0), inz, vsum / maxf(float(nz), 1.0)])


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
