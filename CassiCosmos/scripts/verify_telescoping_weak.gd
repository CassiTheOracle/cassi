extends Node
## Verify Telescoping — WEAK-TWIST probe (Wave-2 follow-on, UNIFICATION.md Phase 8
## milestone 1). The complete, pre-registered weak-arm battery of the FP-4
## relaxation-time-vs-rung discriminator. 2026-08-15.
##
## PRE-REGISTRATION (pinned BEFORE this file was first run — no post-run tuning,
## no gate-weakening; a hold/null is a documented finding, not a re-framing):
##
##   Question (from the Wave-2 report §6, honest note 1): at the §32/Wave-2 twist
##   strength (q_sharp = phi^4 ~ 6.854) the uniform-cadence gate saturates the
##   closure residual in ~1 step at every rung, so T_rel carries minimal rung
##   structure and the FP-4 discriminator cannot separate a near-trivial base
##   from the derived phi^2 ladder. The weak-twist arm lowers q_sharp so that
##   TWO-FLUID COMPETITION (not the operator's saturation) sets T_rel.
##
##   Weak arm (ONE, pre-registered): q_sharp = phi^2 ~ 2.618 — exactly one
##   phi^2-power below the full-strength phi^4 gate.  The operator is the SAME
##   frozen compute/cassi_qi_time_exp.glsl (a FROZEN record, NOT edited here);
##   only the q_sharp push-constant (PC index 8) is lowered.  All other protocol
##   constants are identical to Wave-2: same IC_SEED style deposit family at
##   non-phi radii, same 7 relaxation anchors rho_n = phi^{-n}*(1 - 1/(2*phi)),
##   same T_rel definition (first step |EY - phi*EI|_seed <= 0.5*|eps(0)|),
##   same branch bands {1, phi, phi2} with the pre-stated boundaries, same
##   >= 4 of 6 modal rule.
##
##   Decision tree (pre-stated, per UNIFICATION.md Phase 8):
##     * The gate outcome is the UNIFORM-cadence (cadence-neutral) FP-4 branch,
##       exactly as Wave-2 (§33.8 point 4 reading).  This weak run tests whether
##       the base band's relaxation becomes RUNG-STRUCTURED when the operator no
##       longer saturates it.
##     * Branch "phi2" (R ~ 2.30..3.20 modal, >=4/6) at weak strength => the
##       derived phi^2 ladder IS measurable on the resolved band => Phase-8
##       milestone 1 PASSES => M1/M2 temporal coupling (Phase 8 milestone 2)
##       proceeds.  The derived-exponent cadence remains EXPLORATORY (T2): the
##       cadence-exponent derivation (scale_telescoping_design.md contract item
##       §4a) has not landed, so §33.7 keeps G4a exploratory and the structural
##       claim cannot be an adoption regardless of this run.
##     * Branch "1" (mixing clock) or "phi" (trivialization schedule) at weak
##       strength => no rung structure in the weak regime => HONEST HOLD: the
##       ladder claim for this operator is closed; Phase-8 milestone 1 does not
##       clear, and M1/M2 temporal coupling is not licensed by this probe.
##     * ANOMALY / unreached => documented anomaly; the probe is inconclusive
##       and is reported as such (no post-hoc strength sweep).
##
##   Safety gates G1-G3 run AT the weak strength and are unconditional: if the
##   weak gate breaks OFF-bit-identity, charge conservation, or determinism, the
##   verdict is REJECT regardless of the FP-4 branch.
##
## Dumps res://_diag/telescoping_weak_gpu.json. Self-quits.
##
## Run (windowed console exe — NEVER --headless):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_telescoping_weak.tscn

const PHI := 1.618033988749895
const GRID_N := 64
const DT := 0.005
const EXTENT := 1.0
const K_MAX := 7
const Q_THRESH := 1.0 / PHI          # 0.61803...
const Q_SHARP := PHI * PHI           # phi^2 ~ 2.618 — the weak arm (pre-registered)
const CADENCE_CYCLE := 29            # round(phi^7) (cadence-operator cycle, unused by uniform FP-4)
const ISOL_STEPS := 145              # 5 cadence cycles, isolated operator (G2)
const COUPLED_STEPS := 150           # full coupled battery
const TOP_K := 16                    # attractor readout count (G4a, exploratory)
const STEPS_CAP_RELAX := 5000        # G4c relaxation step cap
const RELAX_ANCHORS := 7             # n = 0..6 (7 anchors → 6 ratios R(0..5))
const RELAX_THRESH_FRAC := 0.5       # T_rel = first step |eps| <= 0.5|eps(0)|

const IC_SEED := 20260814            # same-style IC seed (matching the Wave-2 battery's discipline)

var _rd: RenderingDevice = null
var _checks := 0
var _failures := 0

var _tf_shader: RID
var _tf_pipe: RID
var _tf_us: RID
var _qt_shader: RID
var _qt_pipe: RID
var _qt_us: RID

var _ey: RID
var _ei: RID
var _q: RID
var _vel: RID
var _rho: RID
var _scratch: RID
var _fi_fallback: RID
var _probe_ey: RID
var _probe_ei: RID

var _cells := GRID_N * GRID_N * GRID_N

# IC deposits (radii all NON-phi — off-lattice by construction; same family as
# the Wave-2 battery so the only changed variable is the twist strength).
var _ic := [
	[0.55, -0.40, 0.30, PHI, 1.0, 1.0],
	[-0.70, 0.60, -0.20, 1.0, 1.6, 1.0],
	[0.10, 0.15, -0.85, 2.0, 0.8, 2.0],
]


func _ready() -> void:
	_rd = RenderingServer.create_local_rendering_device()
	if _rd == null:
		_check("local RD acquired", false, "no RD — run windowed, not --headless")
		_finish()
		return
	_check("local RD acquired", true)
	_make_buffers()
	if not _load_pipelines():
		_finish()
		return
	_check("two-fluid pipeline built", _tf_pipe.is_valid())
	_check("cadence-operator pipeline built (frozen cassi_qi_time_exp.glsl, weak q_sharp)", _qt_pipe.is_valid())

	_battery()
	_finish()


func _make_buffers() -> void:
	var n := _cells
	_ey = _rd.storage_buffer_create(n * 4)
	_ei = _rd.storage_buffer_create(n * 4)
	_q = _rd.storage_buffer_create(n * 4)
	_vel = _rd.storage_buffer_create(n * 16)
	_rho = _rd.storage_buffer_create(n * 4)
	_scratch = _rd.storage_buffer_create(n * 16)
	var fi_zero := PackedByteArray(); fi_zero.resize(128)
	_fi_fallback = _rd.storage_buffer_create(128, fi_zero)
	_probe_ey = _rd.storage_buffer_create(n * 4)
	_probe_ei = _rd.storage_buffer_create(n * 4)
	_zero_buffer(_ey, n * 4); _zero_buffer(_ei, n * 4); _zero_buffer(_q, n * 4)
	_zero_buffer(_rho, n * 4); _zero_buffer(_vel, n * 16)
	_zero_buffer(_scratch, n * 16); _zero_buffer(_probe_ey, n * 4); _zero_buffer(_probe_ei, n * 4)


func _zero_buffer(rid: RID, bytes: int) -> void:
	var z := PackedByteArray(); z.resize(bytes)
	_rd.buffer_update(rid, 0, bytes, z)


func _load_pipelines() -> bool:
	var tfs := load("res://compute/cassi_two_fluid.glsl") as RDShaderFile
	if tfs == null:
		_check("two-fluid shader load", false, "load failed")
		return false
	_tf_shader = _rd.shader_create_from_spirv(tfs.get_spirv())
	_tf_pipe = _rd.compute_pipeline_create(_tf_shader)
	_tf_us = _rd.uniform_set_create([
		_u(0, _ey), _u(1, _ei), _u(2, _q), _u(3, _vel), _u(4, _rho), _u(5, _scratch),
		_u(6, _fi_fallback), _u(7, _fi_fallback),
	], _tf_shader, 0)

	# The operator is the SAME frozen cassi_qi_time_exp.glsl; only the q_sharp
	# push-constant (PC index 8) is lowered below Wave-2's phi^4.
	var qs := load("res://compute/cassi_qi_time_exp.glsl") as RDShaderFile
	if qs == null:
		_check("cadence-operator shader load", false, "load failed (run --import after adding new .glsl)")
		return false
	_qt_shader = _rd.shader_create_from_spirv(qs.get_spirv())
	_qt_pipe = _rd.compute_pipeline_create(_qt_shader)
	_qt_us = _rd.uniform_set_create([
		_u(0, _ey), _u(1, _ei), _u(2, _probe_ey), _u(3, _probe_ei),
	], _qt_shader, 0)
	return true


func _u(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# ── deterministic IC scatter (CPU side, mirrors the engine's renormalized TSC
# partition-of-unity envelope; pure CPU → byte-reproducible) ─
func plant_ic(ey: PackedFloat32Array, ei: PackedFloat32Array) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = IC_SEED
	for d in _ic:
		scatter(ey, ei, d[0] as float, d[1] as float, d[2] as float,
			d[3] as float, d[4] as float, d[5] as float, rng)


func scatter_single(ey: PackedFloat32Array, ei: PackedFloat32Array,
		x: float, y: float, z: float, cy: float, ci: float, sigma: float) -> int:
	var rng := RandomNumberGenerator.new()
	rng.seed = IC_SEED
	return scatter(ey, ei, x, y, z, cy, ci, sigma, rng)


func scatter(ey: PackedFloat32Array, ei: PackedFloat32Array, x: float, y: float, z: float,
		cy: float, ci: float, sigma: float, rng: RandomNumberGenerator) -> int:
	var jx := rng.randf()
	var jy := rng.randf()
	var jz := rng.randf()
	var gx: float = (x / EXTENT + 1.0) * 0.5 * float(GRID_N) + (jx - 0.5) * 0.25
	var gy: float = (y / EXTENT + 1.0) * 0.5 * float(GRID_N) + (jy - 0.5) * 0.25
	var gz: float = (z / EXTENT + 1.0) * 0.5 * float(GRID_N) + (jz - 0.5) * 0.25
	var fx: float = gx - floor(gx + 0.5)
	var fy: float = gy - floor(gy + 0.5)
	var fz: float = gz - floor(gz + 0.5)
	var i0 := int(floor(gx + 0.5)) % GRID_N
	var j0 := int(floor(gy + 0.5)) % GRID_N
	var k0 := int(floor(gz + 0.5)) % GRID_N
	var wx := PackedFloat32Array(); var wy := PackedFloat32Array(); var wz := PackedFloat32Array()
	var sx := 0.0; var sy := 0.0; var sz := 0.0
	for ddt in range(-1, 2):
		var ax: float = _spline_w((fx - float(ddt)) / sigma)
		var ay: float = _spline_w((fy - float(ddt)) / sigma)
		var az: float = _spline_w((fz - float(ddt)) / sigma)
		wx.append(ax); wy.append(ay); wz.append(az)
		sx += ax; sy += ay; sz += az
	var renorm: bool = sigma != 1.0
	for i2 in range(3):
		if renorm:
			wx[i2] = 0.0 if sx == 0.0 else wx[i2] / sx
			wy[i2] = 0.0 if sy == 0.0 else wy[i2] / sy
			wz[i2] = 0.0 if sz == 0.0 else wz[i2] / sz
	for di in range(3):
		var wi: float = wx[di]
		var ii: int = (i0 + di - 1 + GRID_N) % GRID_N
		for dj in range(3):
			var wj: float = wy[dj]
			var jj: int = (j0 + dj - 1 + GRID_N) % GRID_N
			for dk in range(3):
				var wk: float = wz[dk]
				var kk: int = (k0 + dk - 1 + GRID_N) % GRID_N
				var idx: int = ii * GRID_N * GRID_N + jj * GRID_N + kk
				var w := wi * wj * wk
				ey[idx] += cy * w
				ei[idx] += ci * w
	return i0 * GRID_N * GRID_N + j0 * GRID_N + k0


func _spline_w(t: float) -> float:
	var at := absf(t)
	if at <= 0.5:
		return 0.75 - at * at
	if at <= 1.5:
		var d := 1.5 - at
		return 0.5 * d * d
	return 0.0


func _upload_field(ey: PackedFloat32Array, ei: PackedFloat32Array) -> void:
	_rd.buffer_update(_ey, 0, _cells * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, _cells * 4, ei.to_byte_array())


func _reset_aux_buffers() -> void:
	_zero_buffer(_q, _cells * 4)
	_zero_buffer(_vel, _cells * 16)
	_zero_buffer(_rho, _cells * 4)
	_zero_buffer(_scratch, _cells * 16)
	_zero_buffer(_probe_ey, _cells * 4)
	_zero_buffer(_probe_ei, _cells * 4)


func _tf_pc(pass_sel: float, t: float) -> PackedFloat32Array:
	var p := PackedFloat32Array()
	p.append(float(GRID_N)); p.append(DT); p.append(t); p.append(PHI)
	p.append(0.0); p.append(0.0); p.append(0.0); p.append(0.0)
	p.append(0.0); p.append(0.0); p.append(0.0)
	p.append(EXTENT); p.append(EXTENT); p.append(EXTENT)
	p.append(pass_sel)
	p.append(20.0)  # omega2 = ω₀² (default 20.0 — bit-identical)
	p.append(0.0)   # ham_completion OFF (U1 toggle, offset 64)
	return p


func _qt_pc(active: float, uniform: float, exp_e: float, t: float) -> PackedFloat32Array:
	var p := PackedFloat32Array()
	p.append(float(GRID_N)); p.append(PHI); p.append(t)
	p.append(active); p.append(uniform); p.append(float(K_MAX))
	p.append(2.0 / float(GRID_N))
	p.append(Q_THRESH); p.append(Q_SHARP)         # PC index 8 = the weak q_sharp
	p.append(exp_e)
	return p


func _tf_dispatch(cl, pass_sel: float, t: float) -> void:
	var p := _tf_pc(pass_sel, t)
	_rd.compute_list_set_push_constant(cl, p.to_byte_array(), p.size() * 4)
	_rd.compute_list_dispatch(cl, _grp(), _grp(), _grp())
	_rd.compute_list_add_barrier(cl)


func _qt_dispatch(cl, active: float, uniform: float, exp_e: float, t: float) -> void:
	var p := _qt_pc(active, uniform, exp_e, t)
	_rd.compute_list_set_push_constant(cl, p.to_byte_array(), p.size() * 4)
	_rd.compute_list_dispatch(cl, _grp(), _grp(), _grp())


func _grp() -> int:
	return int(GRID_N / 4)


func _step_once(active: float, uniform: float, exp_e: float, t: float, apply_probe: bool) -> void:
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _tf_pipe)
	_rd.compute_list_bind_uniform_set(cl, _tf_us, 0)
	_tf_dispatch(cl, 0.0, t)
	_tf_dispatch(cl, 1.0, t)
	_rd.compute_list_bind_compute_pipeline(cl, _qt_pipe)
	_rd.compute_list_bind_uniform_set(cl, _qt_us, 0)
	_qt_dispatch(cl, active, uniform, exp_e, t)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	if apply_probe:
		var pey := _read_f32(_probe_ey)
		var pei := _read_f32(_probe_ei)
		_rd.buffer_update(_ey, 0, _cells * 4, pey.to_byte_array())
		_rd.buffer_update(_ei, 0, _cells * 4, pei.to_byte_array())


func _run_coupled(active: float, uniform: float, exp_e: float, steps: int) -> Dictionary:
	_reset_aux_buffers()
	var ey := PackedFloat32Array(); ey.resize(_cells); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(_cells); ei.fill(0.0)
	plant_ic(ey, ei)
	_upload_field(ey, ei)
	for s in range(steps):
		_step_once(active, uniform, exp_e, float(s + 1), active > 0.5)
	var fey := _read_f32(_ey)
	var fei := _read_f32(_ei)
	var proy := _read_f32(_probe_ey)
	var proi := _read_f32(_probe_ei)
	return {"ey": fey, "ei": fei, "pey": proy, "pei": proi}


func _run_off(steps: int) -> Dictionary:
	_reset_aux_buffers()
	var ey := PackedFloat32Array(); ey.resize(_cells); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(_cells); ei.fill(0.0)
	plant_ic(ey, ei)
	_upload_field(ey, ei)
	var diffs := []
	diffs.resize(steps)
	for s in range(steps):
		_step_once(0.0, 0.0, 0.0, float(s + 1), false)
		var fey := _read_bytes(_ey)
		var fei := _read_bytes(_ei)
		var proy := _read_bytes(_probe_ey)
		var proi := _read_bytes(_probe_ei)
		var d := _byte_diff(fey, proy) + _byte_diff(fei, proi)
		diffs[s] = d
	return {"byte_diffs": diffs, "total": _sum_int(diffs)}


func _run_isolated_operator(uniform: float, exp_e: float) -> Dictionary:
	_reset_aux_buffers()
	var ey := PackedFloat32Array(); ey.resize(_cells); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(_cells); ei.fill(0.0)
	plant_ic(ey, ei)
	_upload_field(ey, ei)
	var sum0 := _sum_field(ey, ei)
	var max_delta := 0.0
	var tot_abs := 0.0
	for s in range(ISOL_STEPS):
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _qt_pipe)
		_rd.compute_list_bind_uniform_set(cl, _qt_us, 0)
		_qt_dispatch(cl, 1.0, uniform, exp_e, float(s + 1))
		_rd.compute_list_end()
		_rd.submit()
		_rd.sync()
		var pey := _read_f32(_probe_ey)
		var pei := _read_f32(_probe_ei)
		var ssum := _sum_field(pey, pei)
		max_delta = maxf(max_delta, absf(ssum - sum0))
		tot_abs += absf(ssum - sum0)
		_rd.buffer_update(_ey, 0, _cells * 4, pey.to_byte_array())
		_rd.buffer_update(_ei, 0, _cells * 4, pei.to_byte_array())
	var deposit := _sum_field(ey, ei)
	var rel := max_delta / maxf(deposit, 1e-9)
	return {"max_delta": max_delta, "tot_abs": tot_abs, "deposit": deposit, "rel": rel}


func _relax_anchor(n: int, cap: int, unif: float, exp_e: float) -> Dictionary:
	var rho: float = pow(PHI, -float(n)) * (1.0 - 1.0 / (2.0 * PHI))
	_reset_aux_buffers()
	var ey := PackedFloat32Array(); ey.resize(_cells); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(_cells); ei.fill(0.0)
	var seed_idx: int = scatter_single(ey, ei, rho, 0.0, 0.0, 2.0, 1.0, 1.0)
	_upload_field(ey, ei)
	var eps0: float = ey[seed_idx] - PHI * ei[seed_idx]
	var thresh := RELAX_THRESH_FRAC * absf(eps0)
	var trel := -1
	for s in range(1, cap + 1):
		_step_once(1.0, unif, exp_e, float(s), true)
		var sey: float = _read_float(_ey, seed_idx)
		var sei: float = _read_float(_ei, seed_idx)
		var eps: float = sey - PHI * sei
		if absf(eps) <= thresh:
			trel = s
			break
	var out := {
		"n": n, "rho": rho, "seed_idx": seed_idx,
		"eps0": eps0, "thresh": thresh, "cap": cap,
	}
	if trel < 0:
		out["T_rel"] = -1
		out["unreached"] = true
	else:
		out["T_rel"] = trel
		out["unreached"] = false
	return out


func _read_float(rid: RID, idx: int) -> float:
	var bytes := _rd.buffer_get_data(rid, idx * 4, 4)
	return bytes.to_float32_array()[0]


func _branch_r(R: float) -> String:
	if R >= 0.70 and R <= 1.34:
		return "1"
	if R > 1.34 and R < 1.36:
		return "ANOMALY"
	if R >= 1.36 and R <= 2.00:
		return "phi"
	if R > 2.00 and R < 2.30:
		return "ANOMALY"
	if R >= 2.30 and R <= 3.20:
		return "phi2"
	return "ANOMALY"


func _read_bytes(rid: RID) -> PackedByteArray:
	return _rd.buffer_get_data(rid, 0, _cells * 4)


func _read_f32(rid: RID) -> PackedFloat32Array:
	return _rd.buffer_get_data(rid, 0, _cells * 4).to_float32_array()


func _byte_diff(a: PackedByteArray, b: PackedByteArray) -> int:
	var d := 0
	var nn := mini(a.size(), b.size())
	for i in range(nn):
		if a[i] != b[i]:
			d += 1
	return d


func _sum_int(a: Array) -> int:
	var t := 0
	for v in a: t += int(v)
	return t


func _fmt_sci(x: float) -> String:
	if x == 0.0:
		return "0.0"
	var neg := x < 0.0
	var ax := absf(x)
	var e := int(floor(log(ax) / log(10.0)))
	var mant := ax / pow(10.0, float(e))
	if mant >= 10.0:
		mant /= 10.0; e += 1
	var ms := "%.3f" % mant
	return ("-" if neg else "") + ms + "e" + str(e)


func _sum_field(ey: PackedFloat32Array, ei: PackedFloat32Array) -> float:
	var s := 0.0
	for i in range(ey.size()): s += ey[i] + ei[i]
	return s


func _rung_dist(ey: PackedFloat32Array, ei: PackedFloat32Array) -> Dictionary:
	var find := PackedFloat32Array()
	find.resize(TOP_K); find.fill(-1.0)
	var find_i := PackedInt32Array()
	find_i.resize(TOP_K); find_i.fill(-1)
	var n := GRID_N
	for i in range(_cells):
		var qv: float = ey[i] * ey[i] + ei[i] * ei[i]
		var pos: int = TOP_K - 1
		while pos >= 0 and (qv > find[pos] or (qv == find[pos] and i < find_i[pos])):
			pos -= 1
		if pos < TOP_K - 1:
			var tt := TOP_K - 1
			while tt > pos + 1:
				find[tt] = find[tt - 1]; find_i[tt] = find_i[tt - 1]; tt -= 1
			find[pos + 1] = qv; find_i[pos + 1] = i
	var half := 0.5 * float(n)
	var Dsum := 0.0
	var cells := []
	for t in range(TOP_K):
		var idx: int = find_i[t]
		var gx: int = idx / (n * n); var rem: int = idx % (n * n)
		var gy: int = rem / n; var gz: int = rem % n
		var dx: float = (float(gx) + 0.5 - half) / half
		var dy: float = (float(gy) + 0.5 - half) / half
		var dz: float = (float(gz) + 0.5 - half) / half
		var rho: float = clamp(sqrt(dx * dx + dy * dy + dz * dz), 1e-6, 1.0)
		var tt: float = log(1.0 / rho) / log(PHI)
		var D: float = absf(tt - round(tt))
		Dsum += D
		cells.append({"i": idx, "gx": gx, "gy": gy, "gz": gz, "rho": rho, "t": tt, "D": D, "q": find[t]})
	return {"cells": cells, "d_mean": Dsum / float(TOP_K)}


func _lattice_null() -> Dictionary:
	var n := GRID_N
	var half := 0.5 * float(n)
	var sum := 0.0
	var sumsq := 0.0
	var cnt := 0.0
	for i in range(n):
		for j in range(n):
			for k2 in range(n):
				var dx: float = (float(i) + 0.5 - half) / half
				var dy: float = (float(j) + 0.5 - half) / half
				var dz: float = (float(k2) + 0.5 - half) / half
				var rho: float = clamp(sqrt(dx * dx + dy * dy + dz * dz), 1e-6, 1.0)
				var tt: float = log(1.0 / rho) / log(PHI)
				var D: float = absf(tt - round(tt))
				sum += D; sumsq += D * D; cnt += 1.0
	var mu := sum / cnt
	var varz := maxf(sumsq / cnt - mu * mu, 0.0)
	return {"mu": mu, "sigma": sqrt(varz), "cnt": cnt}


func _battery() -> void:
	var dump := {}

	# G1 — OFF-path bit-identity (3 steps) at the weak strength (active=0 => the
	# weak q_sharp is irrelevant; this still confirms the operator OFF path is a
	# pure copy).
	var off := _run_off(3)
	_check("G1: OFF path bit-identity (0 bytes differ over 3 steps)",
		off["total"] == 0, "total_bytes_diff=" + str(off["total"]) + " per_step=" + str(off["byte_diffs"]))
	dump["g1"] = {"pass": off["total"] == 0, "total_bytes_diff": off["total"],
		"per_step_bytes_diff": off["byte_diffs"]}

	# G2 — operator charge conservation in isolation (5 cadence cycles), the
	# pre-registered weak arm = uniform-cadence φ² only? No — G2 is operator-own:
	# the weak arm is one operator configuration. We run the UNIFORM weak
	# cadence (the FP-4 gate reading is cadence-neutral) in isolation for G2.
	var g2_weakunif := _run_isolated_operator(1.0, 0.0)
	_check("G2: weak-arm uniform operator |ΔΣ|/deposit ≤ 1e-6",
		g2_weakunif["rel"] <= 1e-6,
		"rel=" + _fmt_sci(g2_weakunif["rel"]) + " maxΔ=" + _fmt_sci(g2_weakunif["max_delta"]) + " deposit=%.4f" % g2_weakunif["deposit"])
	dump["g2"] = {"weak_uniform_arm": {"pass": g2_weakunif["rel"] <= 1e-6,
		"rel": g2_weakunif["rel"], "max_delta": g2_weakunif["max_delta"],
		"tot_abs": g2_weakunif["tot_abs"], "deposit": g2_weakunif["deposit"]}}

	# G3 + G4a + full-run charge — coupled runs at the weak strength.
	var nullz := _lattice_null()
	var unif_run := _run_coupled(1.0, 1.0, 0.0, COUPLED_STEPS)   # weak uniform
	var p2_run := _run_coupled(1.0, 0.0, 2.0, COUPLED_STEPS)     # weak φ²
	var unif_topk := _rung_dist(unif_run["ey"], unif_run["ei"])
	var p2_topk := _rung_dist(p2_run["ey"], p2_run["ei"])
	var z_unif: float = (float(nullz["mu"]) - float(unif_topk["d_mean"])) / float(nullz["sigma"])
	var z_p2: float = (float(nullz["mu"]) - float(p2_topk["d_mean"])) / float(nullz["sigma"])

	# G3 — determinism: repeat φ², byte-compare final probe.
	var p2_run2 := _run_coupled(1.0, 0.0, 2.0, COUPLED_STEPS)
	var pey_b: PackedByteArray = (p2_run["pey"] as PackedFloat32Array).to_byte_array()
	var pei_b: PackedByteArray = (p2_run["pei"] as PackedFloat32Array).to_byte_array()
	var pey_b2: PackedByteArray = (p2_run2["pey"] as PackedFloat32Array).to_byte_array()
	var pei_b2: PackedByteArray = (p2_run2["pei"] as PackedFloat32Array).to_byte_array()
	var det := _byte_diff(pey_b, pey_b2) + _byte_diff(pei_b, pei_b2)
	_check("G3: determinism φ² (weak) — two runs byte-identical (0 bytes differ)",
		det == 0, "bytes_diff=" + str(det))
	dump["g3"] = {"phi2_bytes_diff": det, "pass": det == 0}

	# G4a — attractor placement per arm (EXPLORATORY).
	var g4a := {}
	var zm_unif: float = z_unif
	var zm_p2: float = z_p2
	g4a["uniform"] = {"z": zm_unif, "d_mean": unif_topk["d_mean"],
		"null_mu": nullz["mu"], "null_sigma": nullz["sigma"], "topk": unif_topk["cells"]}
	g4a["phi2"] = {"z": zm_p2, "d_mean": p2_topk["d_mean"],
		"null_mu": nullz["mu"], "null_sigma": nullz["sigma"], "topk": p2_topk["cells"]}
	_check("G4a uniform (weak): z computed (exploratory)", true,
		"z=%.3f d_mean=%.4f (null μ=%.4f σ=%.4f)" % [zm_unif, unif_topk["d_mean"], nullz["mu"], nullz["sigma"]])
	_check("G4a φ² (weak): z computed (exploratory)", true,
		"z=%.3f d_mean=%.4f (null μ=%.4f σ=%.4f)" % [zm_p2, p2_topk["d_mean"], nullz["mu"], nullz["sigma"]])
	dump["g4a"] = g4a
	dump["g4a_status"] = "EXPLORATORY (T2) for phi2 per scale_telescoping_design.md §4a/§33.7 (cadence exponent not derived) — not adoption claims"

	# full-run charge context (documented, NOT a gate).
	var sum_ic := 0.0
	for d in _ic: sum_ic += float(d[3]) + float(d[4])
	dump["charge_context"] = {"ic_sum": sum_ic}
	dump["charge_context"]["uniform_sum_after_150"] = _sum_field(unif_run["ey"], unif_run["ei"])
	dump["charge_context"]["phi2_sum_after_150"] = _sum_field(p2_run["ey"], p2_run["ei"])

	# ── G4c — FP-4 relaxation-time-vs-rung discriminator (cadence-neutral) ──
	var unif_relax := []
	for n in range(RELAX_ANCHORS):
		unif_relax.append(_relax_anchor(n, STEPS_CAP_RELAX, 1.0, 0.0))
	# φ² run-own context (exploratory, NOT a gate outcome).
	var p2_relax := []
	for n in range(RELAX_ANCHORS):
		p2_relax.append(_relax_anchor(n, STEPS_CAP_RELAX, 0.0, 2.0))

	var g4c := {}
	var ratios := []
	var branches := []
	g4c["reported_branch_for_n"] = []
	for n in range(RELAX_ANCHORS - 1):
		var t1: float = float(unif_relax[n]["T_rel"])
		var t2: float = float(unif_relax[n + 1]["T_rel"])
		var R := 0.0
		var branch := "ANOMALY"
		if unif_relax[n]["unreached"] or unif_relax[n + 1]["unreached"]:
			R = -1.0
			branch = "ANOMALY"
		else:
			R = t2 / t1
			branch = _branch_r(R)
		ratios.append(R)
		branches.append(branch)
		g4c["reported_branch_for_n"].append({"n": n, "R": R, "branch": branch})

	var tally := {"1": 0, "phi": 0, "phi2": 0, "ANOMALY": 0}
	for b in branches:
		tally[b] += 1
	var overall := "ANOMALY"
	var modal := "ANOMALY"
	var best := 0
	for kname in ["1", "phi", "phi2", "ANOMALY"]:
		if tally[kname] > best:
			best = tally[kname]; modal = kname
	if best >= 4 and modal != "ANOMALY":
		overall = modal
	g4c["tally"] = tally
	g4c["overall_fp4"] = overall
	g4c["gate_pass_clean_phi2"] = (overall == "phi2")
	g4c["gate_pass_clean_phi"] = (overall == "phi")
	g4c["gate_pass_clean_1"] = (overall == "1")
	g4c["T_rel_uniform_weak"] = unif_relax
	g4c["T_rel_phi2_context"] = p2_relax
	dump["g4c"] = g4c

	_check("G4c: FP-4 overall branch (gate outcome)",
		overall == "phi2" or overall == "phi" or overall == "1",
		"overall_fp4=" + overall + " tally=" + str(tally))
	_check("G4c decision: phi2 branch at weak strength licenses M1/M2 temporal coupling",
		overall == "phi2", "overall_fp4=" + overall + " (mixing clock or trivialization => HOLD)")

	dump["meta"] = {"date": "2026-08-15", "grid_n": GRID_N, "dt": DT, "k_max": K_MAX,
		"cadence_cycle": CADENCE_CYCLE, "isol_steps": ISOL_STEPS,
		"coupled_steps": COUPLED_STEPS, "top_k": TOP_K,
		"q_thresh": Q_THRESH, "q_sharp_weak": Q_SHARP, "q_sharp_full": PHI * PHI * PHI * PHI,
		"weak_arm": "q_sharp=phi^2 (one pre-registered strength; frozen cassi_qi_time_exp.glsl reused)",
		"relax_anchors": RELAX_ANCHORS, "relax_thresh_frac": RELAX_THRESH_FRAC,
		"relax_cap": STEPS_CAP_RELAX,
		"branches": {"1": [0.70, 1.34], "phi": [1.36, 2.00], "phi2": [2.30, 3.20],
			"gutter_anomaly_lo": [1.34, 1.36], "gutter_anomaly_hi": [2.00, 2.30]},
		"decision_tree": "phi2 modal (>=4/6) => Phase-8 M1/M2 proceeds; 1 or phi => HOLD (ladder closed for this operator); anomaly => inconclusive"}
	dump["final_probe_ey_phi2_b64"] = Marshalls.raw_to_base64(pey_b)
	dump["final_probe_ei_phi2_b64"] = Marshalls.raw_to_base64(pei_b)

	var f := FileAccess.open("res://_diag/telescoping_weak_gpu.json", FileAccess.WRITE)
	if f == null:
		_check("JSON dump written to res://_diag/telescoping_weak_gpu.json", false, "FileAccess failed")
	else:
		f.store_string(JSON.stringify(dump))
		f.close()
		_check("JSON dump written to res://_diag/telescoping_weak_gpu.json", true)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	if _rd != null:
		for rid in [_qt_us, _tf_us, _probe_ei, _probe_ey, _fi_fallback, _scratch,
				_rho, _vel, _q, _ei, _ey, _qt_pipe, _qt_shader, _tf_pipe, _tf_shader]:
			if rid.is_valid():
				_rd.free_rid(rid)
		_rd.free()
		_rd = null
	print("[VerifyTelescopingWeak] checks=%d failures=%d" % [_checks, _failures])
	if _failures == 0:
		print("[VerifyTelescopingWeak] RESULT: PASS — state dumped for the weak-twist report")
	else:
		print("[VerifyTelescopingWeak] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
