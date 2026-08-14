extends Node3D
## Verify — "ALL particles vanish" live bug in the meshless+treesim arm.
## Drives the sim EXACTLY as the user does (meshless_mode + meshless_gravity
## ON — the mode-5 tree arm on a LOCAL RD), two paths:
##   Path A (direct):  playing=false, call _sim._run_physics_steps(1) per frame
##   Path B (_process): playing=true  — the real _process catch-up stepping
## and, every sample-frames, reads back from the sim's GLOBAL RD:
##   alive positions (min/max |pos|, NaN/Inf count, count outside 12·extent)
##   _acc_buf NaN count + max |acc|
##   _ml_tree_grad (the mode-5 force) NaN count + max |grad|
##   _field_ey/_field_ei NaN count + range
##   _ml_psi_y/_ml_psi_i (the tree's per-site field source) NaN count
##   _ml_sites NaN count
##   _mass_density_buf (the deposit, gathered per-site by the tree) NaN count
##   pos.w (Salpeter mass) min/max + NaN count
##   BH record count (slots with mass > 0 in the 36-vec4 bh header)
## The FIRST quantity to go bad (NaN/Inf/list-off-screen) in the printed
## timeline is the diagnosis.

const SAMPLE := 20          # readback every this many frames (each readback stalls the global RD)
const N_FRAMES_A := 1200    # direct-path frames
const N_FRAMES_B := 1200    # _process-path frames
const OUTSIDE_MULT := 12.0  # |pos| > OUTSIDE_MULT · extent → "off-screen / invisible" heuristic

var _sim: Node
var _phase := 0             # 0..3 (path A warm, path A sample, switch to B, path B sample)
var _frame := 0
var _a_nan_step := -1
var _b_nan_step := -1
var _a_alive_min := -1
var _b_alive_min := -1


func _ready() -> void:
	_sim = $CassiSim
	# --river control: run the RIVER arm (tree off) with the SAME config to
	# discriminate "tree force is the ejector" vs a config-level instability.
	for a in OS.get_cmdline_user_args():
		if a == "--river":
			_sim.meshless_gravity = false
			_sim.gravity_mode = 0
			print("[VerifyParticleVanish] RIVER CONTROL: tree off, gravity_mode=0")


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready or not _sim._ml_ready:
		return
	match _phase:
		0:
			print("[VerifyParticleVanish] path A (direct _run_physics_steps/1) — grid_N=%d Np=%d dt=%.4f" %
				[_sim.grid_N, _sim.N_particles, _sim.dt])
			_frame = 0
			_phase = 1
		1:
			_step_direct()
			_frame += 1
			if _frame % SAMPLE == 0:
				var r := _sample()
				_print_timeline("A", _frame, r)
				if r.nan_pos > 0:
					_a_nan_step = _frame
				if _a_alive_min < 0 and r.alive < _sim.N_particles * 3 / 4:
					_a_alive_min = _frame
			if _frame >= N_FRAMES_A:
				print("[VerifyParticleVanish] path A done — switching to path B (playing=true)")
				_sim.playing = true
				_frame = 0
				_phase = 2
		2:
			# path B — the sim's OWN _process drives (playing=true set below);
			# we only sample periodically.
			_frame += 1
			if _frame % SAMPLE == 0:
				var r := _sample()
				_print_timeline("B", _frame, r)
				if r.nan_pos > 0:
					_b_nan_step = _frame
				if _b_alive_min < 0 and r.alive < _sim.N_particles * 3 / 4:
					_b_alive_min = _frame
			if _frame >= N_FRAMES_B:
				print("[VerifyParticleVanish] done — A(nan@%d,alive@%d) B(nan@%d,alive@%d)" % [
					_a_nan_step, _a_alive_min, _b_nan_step, _b_alive_min])
				get_tree().quit(0)


func _step_direct() -> void:
	_sim._run_physics_steps(1)


# ── readback everything at the current state ───────────────────────────
func _sample() -> Dictionary:
	var np: int = _sim.N_particles
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var _ex: Vector3 = _sim._extents()
	var out_lim: float = OUTSIDE_MULT * maxf(_ex.x, maxf(_ex.y, _ex.z))
	var r := {}
	r.np = np
	# positions
	var pos: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
	r.nan_pos = _count_bad(pos, 12)
	r.min_pos = 1e30; r.max_pos = -1.0; r.alive = 0
	var pw_min := 1e30; var pw_max := -1.0; var pw_nan := 0
	for i in range(np):
		var b := i * 4
		var px: float = pos[b]; var py: float = pos[b + 1]; var pz: float = pos[b + 2]
		var pr: float = sqrt(px * px + py * py + pz * pz)
		if not is_finite(pr):
			continue
		if pr < r.min_pos: r.min_pos = pr
		if pr > r.max_pos: r.max_pos = pr
		if pr <= out_lim: r.alive += 1
		var m: float = pos[b + 3]
		if is_nan(m): pw_nan += 1
		else:
			if m < pw_min: pw_min = m
			if m > pw_max: pw_max = m
	r.alive = maxf(float(r.alive), 0.0)
	r.max_pos = 0.0 if r.max_pos < 0.0 else r.max_pos
	r.min_pos = 0.0 if r.min_pos > 1e29 else r.min_pos
	r.pw_nan = pw_nan
	r.pw_min = 0.0 if pw_min > 1e29 else pw_min
	r.pw_max = 0.0 if pw_max < 0.0 else pw_max
	# acc
	var acc: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._acc_buf, 0, np * 16).to_float32_array()
	var an := 0; var amax := 0.0
	for i in range(np * 4):
		var v: float = acc[i]
		if is_nan(v) or is_inf(v): an += 1
		elif absf(v) > amax: amax = absf(v)
	r.acc_nan = an; r.acc_max = amax
	# tree gradient
	var tg: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_tree_grad, 0, np * 16).to_float32_array()
	var tn := 0; var tmax := 0.0
	for i in range(np * 4):
		var v: float = tg[i]
		if is_nan(v) or is_inf(v): tn += 1
		elif absf(v) > tmax: tmax = absf(v)
	r.tgrad_nan = tn; r.tgrad_max = tmax
	# field ey/ei
	var ey: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._field_ey, 0, n3 * 4).to_float32_array()
	var ei: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._field_ei, 0, n3 * 4).to_float32_array()
	var fy := 0; var fi := 0; var fmin := 1e30; var fmax := -1e30
	for i in range(n3):
		if is_bad(ey[i]): fy += 1
		else:
			if ey[i] < fmin: fmin = ey[i]
			if ey[i] > fmax: fmax = ey[i]
		if is_bad(ei[i]): fi += 1
	r.ey_nan = fy; r.ei_nan = fi
	r.ey_min = 0.0 if fmin > 1e29 else fmin
	r.ey_max = 0.0 if fmax < -1e29 else fmax
	# meshless site field + sites
	var ns: int = 2 * 16 * 16 * 16
	var psy: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_psi_y, 0, ns * 4).to_float32_array()
	var psi: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_psi_i, 0, ns * 4).to_float32_array()
	var pyn := 0; var pin := 0
	for i in range(ns):
		if is_bad(psy[i]): pyn += 1
		if is_bad(psi[i]): pin += 1
	r.psi_y_nan = pyn; r.psi_i_nan = pin
	var st: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._ml_sites, 0, ns * 16).to_float32_array()
	var stn := 0
	for i in range(ns * 4):
		if is_bad(st[i]): stn += 1
	r.sites_nan = stn
	# deposit mass density
	var rho: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._mass_density_buf, 0, n3 * 4).to_float32_array()
	var rn := 0; var rm := 0.0
	for i in range(n3):
		if is_bad(rho[i]): rn += 1
		elif rho[i] > rm: rm = rho[i]
	r.rho_nan = rn; r.rho_max = rm
	# BH records (36 vec4; records base 4 + b*2, mass = .w)
	var bh: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._bh_buf, 0, 36 * 16).to_float32_array()
	var bhcnt := 0; var bhmass := 0.0
	for b in range(15):
		var base: int = 4 + b * 2
		var m: float = bh[base * 4 + 3]
		if is_finite(m) and m > 0.0:
			bhcnt += 1
			bhmass += m
	r.bh_count = bhcnt; r.bh_mass = bhmass
	r.nnode = _sim._ml_tree_nnode
	return r


func is_finite(x: float) -> bool:
	return not (is_nan(x) or is_inf(x))


func is_bad(x: float) -> bool:
	return is_nan(x) or is_inf(x)


func _count_bad(a: PackedFloat32Array, stride: int) -> int:
	var n := 0
	for i in range(a.size()):
		if is_bad(a[i]): n += 1
	return n


func _print_timeline(tag: String, fr: int, r: Dictionary) -> void:
	print("[VerifyParticleVanish][%s] fr=%d alive=%d/%d |pos|[%s..%s] nan=%d pw=[%.3f..%.3f] nan=%d | acc_nan=%d max=%.4f | tgrad_nan=%d max=%.4f nnode=%d | ey_nan=%d ei_nan=%d rho_nan=%d psiY_nan=%d psiI_nan=%d sites_nan=%d | bh=%d(m=%.2f)" % [
		tag, fr,
		int(r.alive), r.np,
		_trim(r.min_pos), _trim(r.max_pos), r.nan_pos,
		r.pw_min, r.pw_max, r.pw_nan,
		r.acc_nan, r.acc_max,
		r.tgrad_nan, r.tgrad_max, r.nnode,
		r.ey_nan, r.ei_nan, r.rho_nan, r.psi_y_nan, r.psi_i_nan, r.sites_nan,
		r.bh_count, r.bh_mass])


func _trim(x: float) -> String:
	if absf(x) > 1e12 or not is_finite(x):
		return "HUGE"
	return "%.2f" % x
