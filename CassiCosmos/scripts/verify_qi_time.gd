extends Node
## Verify Qi-time — guarded prototype battery for the φ-cadence multiscale
## mixing gate (plan cassi-mind-plugin.md §32 / §31-4, 2026-08-14).
##
## Self-contained local-RD probe (no shipped engine .gd instantiated — the
## repo is dirty with the owner's live work, so this is NEW-FILES-ONLY). It
## builds its OWN RenderingDevice + buffers + pipelines:
##   - the two-fluid PDE as an UNCHANGED reference (compute/cassi_two_fluid.glsl)
##   - the Qi-time operator (compute/cassi_qi_time.glsl, new)
## and drives, per step: two-fluid pass A → pass B → qi_time pass (OFF pure
## copy / PROBE cadence operator in a scratch copy → fed back to the field).
##
## Pre-registered gates (cassi-mind-plugin.md §32 — written before this run):
##   G1  OFF-path bit-identity: after each OFF step, probe EY/EI ≡ canonical
##       EY/EI byte-exact (0 bytes differ).
##   G2  charge conservation under the cadence: the operator's OWN ΔΣ over
##       ≥5 full cadence cycles (145 isolated applications), relative to the
##       deposited charge, ≤ 1e-6 for the φ-cadence AND uniform controls.
##   G3  determinism: two identical φ-cadence runs → byte-identical final
##       probe EY/EI (0 bytes differ).
##   G4  structural: top-k=16 attractor cells after 150 coupled steps land on
##       the φ-rung lattice (D = |log_φ(1/ρ) − round(...)|) more than the
##       permutation null AND more than the uniform-cadence control:
##       PASS = z_phi ≥ 2 AND z_phi > z_uniform + 1.
##
## Dumps all gate values + a full-field probe snapshot to
## res://_diag/qi_time_gpu.json for the report. Self-quits (0 = all gates
## pass; 1 = any gate fails).
##
## Run (windowed console exe — NEVER --headless, which has no RD on this rig):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_qi_time.tscn
## (Run --import first after adding a new .glsl.)

const PHI := 1.618033988749895
const GRID_N := 64
const DT := 0.005
const EXTENT := 1.0
const K_MAX := 7
const Q_THRESH := 1.0 / PHI          # 0.61803...
const Q_SHARP := PHI * PHI * PHI * PHI   # φ⁴ ≈ 6.85410
const CADENCE_CYCLE := 29            # round(φ^7)
const ISOL_STEPS := 145              # 5 full cadence cycles, isolated operator
const COUPLED_STEPS := 150           # full coupled battery (two-fluid + operator)
const TOP_K := 16                    # attractor readout count (G4)

# Deterministic seed for the IC scatter.
const IC_SEED := 20260814

var _rd: RenderingDevice = null
var _checks := 0
var _failures := 0

# Two-fluid pipeline (reference, unchanged).
var _tf_shader: RID
var _tf_pipe: RID
var _tf_us: RID
# Qi-time pipeline (new).
var _qt_shader: RID
var _qt_pipe: RID
var _qt_us: RID

# Buffer RIDs (owned here, freed on quit).
var _ey: RID
var _ei: RID
var _q: RID
var _vel: RID
var _rho: RID
var _scratch: RID          # two-fluid double-buffer scratch (vec4/cell)
var _probe_ey: RID         # qi-time probe copy out
var _probe_ei: RID

var _cells := GRID_N * GRID_N * GRID_N

# IC deposits (radii all NON-φ — off-lattice by construction).
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
	_check("qi-time pipeline built", _qt_pipe.is_valid())

	_battery()
	_finish()


# ── setup ────────────────────────────────────────────────────────────────
func _make_buffers() -> void:
	var n := _cells
	_ey = _rd.storage_buffer_create(n * 4)
	_ei = _rd.storage_buffer_create(n * 4)
	_q = _rd.storage_buffer_create(n * 4)
	_vel = _rd.storage_buffer_create(n * 16)
	_rho = _rd.storage_buffer_create(n * 4)
	_scratch = _rd.storage_buffer_create(n * 16)
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
	], _tf_shader, 0)

	var qs := load("res://compute/cassi_qi_time.glsl") as RDShaderFile
	if qs == null:
		_check("qi-time shader load", false, "load failed (run --import after adding new .glsl)")
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


# ── deterministic IC scatter (CPU side, mirrors the engine's renormalized
#    TSC partition-of-unity envelope; pure CPU → byte-reproducible for G3) ─
func plant_ic(ey: PackedFloat32Array, ei: PackedFloat32Array) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = IC_SEED
	for d in _ic:
		var x := d[0] as float
		var y := d[1] as float
		var z := d[2] as float
		var cy := d[3] as float
		var ci := d[4] as float
		var sigma := d[5] as float
		scatter(ey, ei, x, y, z, cy, ci, sigma, rng)


func scatter(ey: PackedFloat32Array, ei: PackedFloat32Array, x: float, y: float, z: float,
		cy: float, ci: float, sigma: float, rng: RandomNumberGenerator) -> void:
	# Jitter the anchor by a seeded tiny offset so the deposit is not exactly
	# at integer cell centers (deterministic; keeps the test honest — off-grid).
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


func _spline_w(t: float) -> float:
	var at := absf(t)
	if at <= 0.5:
		return 0.75 - at * at
	if at <= 1.5:
		var d := 1.5 - at
		return 0.5 * d * d
	return 0.0


# ── GPU pipelines ────────────────────────────────────────────────────────
func _upload_field(ey: PackedFloat32Array, ei: PackedFloat32Array) -> void:
	_rd.buffer_update(_ey, 0, _cells * 4, ey.to_byte_array())
	_rd.buffer_update(_ei, 0, _cells * 4, ei.to_byte_array())


## Zero every auxiliary buffer (q, vel, rho, scratch, probe) so each run
## starts from a clean state — the φ-cadence determinism runs must NOT leak
## velocity/scratch from the prior run (that would contaminate G3).
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
	p.append(0.0); p.append(0.0); p.append(0.0); p.append(0.0)   # xi..mode
	p.append(0.0); p.append(0.0); p.append(0.0)                  # source..gravity
	p.append(EXTENT); p.append(EXTENT); p.append(EXTENT)         # extent xyz
	p.append(pass_sel)                                           # 0=A 1=B
	p.append(20.0)                                               # omega2 = ω₀² (default 20.0 — bit-identical)
	p.append(0.0)                                                # ham_completion OFF (U1 toggle, offset 64)
	return p


func _qt_pc(active: float, uniform: float, t: float) -> PackedFloat32Array:
	var p := PackedFloat32Array()
	p.append(float(GRID_N)); p.append(PHI); p.append(t)
	p.append(active); p.append(uniform); p.append(float(K_MAX))
	p.append(2.0 / float(GRID_N))               # inv_half
	p.append(Q_THRESH); p.append(Q_SHARP)
	return p


func _tf_dispatch(cl, pass_sel: float, t: float) -> void:
	var p := _tf_pc(pass_sel, t)
	_rd.compute_list_set_push_constant(cl, p.to_byte_array(), p.size() * 4)
	_rd.compute_list_dispatch(cl, _grp(), _grp(), _grp())
	_rd.compute_list_add_barrier(cl)


func _qt_dispatch(cl, active: float, uniform: float, t: float) -> void:
	var p := _qt_pc(active, uniform, t)
	_rd.compute_list_set_push_constant(cl, p.to_byte_array(), p.size() * 4)
	_rd.compute_list_dispatch(cl, _grp(), _grp(), _grp())


func _grp() -> int:
	return int(GRID_N / 4)


# One full step: two-fluid pass A → pass B, then the qi-time pass.
# If apply_probe is true, the probe copy is fed back into the canonical field.
func _step_once(active: float, uniform: float, t: float, apply_probe: bool) -> void:
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _tf_pipe)
	_rd.compute_list_bind_uniform_set(cl, _tf_us, 0)
	_tf_dispatch(cl, 0.0, t)
	_tf_dispatch(cl, 1.0, t)
	_rd.compute_list_bind_compute_pipeline(cl, _qt_pipe)
	_rd.compute_list_bind_uniform_set(cl, _qt_us, 0)
	_qt_dispatch(cl, active, uniform, t)
	_rd.compute_list_end()
	_rd.submit()
	_rd.sync()
	if apply_probe:
		var pey := _read_f32(_probe_ey)
		var pei := _read_f32(_probe_ei)
		_rd.buffer_update(_ey, 0, _cells * 4, pey.to_byte_array())
		_rd.buffer_update(_ei, 0, _cells * 4, pei.to_byte_array())


func _run_coupled(active: float, uniform: float, steps: int) -> Dictionary:
	# Fresh IC each call (deterministic).
	_reset_aux_buffers()
	var ey := PackedFloat32Array(); ey.resize(_cells); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(_cells); ei.fill(0.0)
	plant_ic(ey, ei)
	_upload_field(ey, ei)
	for s in range(steps):
		_step_once(active, uniform, float(s + 1), active > 0.5)
	# Final canonical field.
	var fey := _read_f32(_ey)
	var fei := _read_f32(_ei)
	var proy := _read_f32(_probe_ey)
	var proi := _read_f32(_probe_ei)
	return {"ey": fey, "ei": fei, "pey": proy, "pei": proi}


func _run_off(steps: int) -> Dictionary:
	# OFF mode: pure-copy qi-time over the two-fluid step; probe must equal
	# canonical field byte-exact each step. Single fresh run.
	_reset_aux_buffers()
	var ey := PackedFloat32Array(); ey.resize(_cells); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(_cells); ei.fill(0.0)
	plant_ic(ey, ei)
	_upload_field(ey, ei)
	var diffs := []
	diffs.resize(steps)
	for s in range(steps):
		_step_once(0.0, 0.0, float(s + 1), false)
		var fey := _read_bytes(_ey)
		var fei := _read_bytes(_ei)
		var proy := _read_bytes(_probe_ey)
		var proi := _read_bytes(_probe_ei)
		var d := _byte_diff(fey, proy) + _byte_diff(fei, proi)
		diffs[s] = d
	return {"byte_diffs": diffs, "total": _sum_int(diffs)}


func _run_isolated_operator(uniform: float) -> Dictionary:
	# Operator in isolation (no two-fluid): apply the PROBE pass 5 cadence
	# cycles over the frozen IC, tracking Σ(EY+EI) drift. The field is
	# reflected back through the probe each application.
	_reset_aux_buffers()
	var ey := PackedFloat32Array(); ey.resize(_cells); ey.fill(0.0)
	var ei := PackedFloat32Array(); ei.resize(_cells); ei.fill(0.0)
	plant_ic(ey, ei)
	_upload_field(ey, ei)
	var sum0 := _sum_field(ey, ei)
	var max_delta := 0.0
	var tot_abs := 0.0
	for s in range(ISOL_STEPS):
		# qi-time only (no two-fluid).
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _qt_pipe)
		_rd.compute_list_bind_uniform_set(cl, _qt_us, 0)
		_qt_dispatch(cl, 1.0, uniform, float(s + 1))
		_rd.compute_list_end()
		_rd.submit()
		_rd.sync()
		var pey := _read_f32(_probe_ey)
		var pei := _read_f32(_probe_ei)
		var ssum := _sum_field(pey, pei)
		var delta := ssum - sum0
		max_delta = maxf(max_delta, absf(delta))
		tot_abs += absf(delta)
		_rd.buffer_update(_ey, 0, _cells * 4, pey.to_byte_array())
		_rd.buffer_update(_ei, 0, _cells * 4, pei.to_byte_array())
	var deposit := _sum_field(ey, ei)  # ≈ Σcy + Σci
	var rel := max_delta / maxf(deposit, 1e-9)
	return {"max_delta": max_delta, "tot_abs": tot_abs, "deposit": deposit, "rel": rel}


# ── readback helpers ─────────────────────────────────────────────────────
func _read_bytes(rid: RID) -> PackedByteArray:
	return _rd.buffer_get_data(rid, 0, _cells * 4)


func _read_f32(rid: RID) -> PackedFloat32Array:
	return _rd.buffer_get_data(rid, 0, _cells * 4).to_float32_array()


func _byte_diff(a: PackedByteArray, b: PackedByteArray) -> int:
	var d := 0
	var n := mini(a.size(), b.size())
	for i in range(n):
		if a[i] != b[i]:
			d += 1
	return d


func _sum_int(a: Array) -> int:
	var t := 0
	for v in a: t += int(v)
	return t


## Scientific-ish formatting safe in GDScript (the %-operator has NO %e
## specifier). Renders a number like "1.23e-7" from a float using fixed
## notation decomposition (3 significant digits).
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


# ── G4 helpers ───────────────────────────────────────────────────────────
func _rung_dist(ey: PackedFloat32Array, ei: PackedFloat32Array) -> Dictionary:
	# For the top-k cells by q, compute D = |t − round(t)|, t = log_φ(1/ρ).
	# Returns {cells: [{i,q,rho,t,D}], d_mean}.
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
			var t := TOP_K - 1
			while t > pos + 1:
				find[t] = find[t - 1]; find_i[t] = find_i[t - 1]; t -= 1
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
	# Permutation null: D over all 262144 cells.
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


# ── battery ──────────────────────────────────────────────────────────────
func _battery() -> void:
	# G1 — OFF-path bit-identity (3 steps).
	var off := _run_off(3)
	_check("G1: OFF path bit-identity (0 bytes differ over 3 steps)",
		off["total"] == 0, "total_bytes_diff=" + str(off["total"]) + " per_step=" + str(off["byte_diffs"]))

	# G2 — operator charge conservation in isolation (5 cadence cycles), BOTH arms.
	var g2_phi := _run_isolated_operator(0.0)
	var g2_unif := _run_isolated_operator(1.0)
	_check("G2: φ-cadence arm |ΔΣ|/deposit ≤ 1e-6",
		g2_phi["rel"] <= 1e-6,
		"rel=" + _fmt_sci(g2_phi["rel"]) + " maxΔ=" + _fmt_sci(g2_phi["max_delta"]) + " deposit=%.4f" % g2_phi["deposit"])
	_check("G2: uniform arm |ΔΣ|/deposit ≤ 1e-6",
		g2_unif["rel"] <= 1e-6,
		"rel=" + _fmt_sci(g2_unif["rel"]) + " maxΔ=" + _fmt_sci(g2_unif["max_delta"]) + " deposit=%.4f" % g2_unif["deposit"])

	# G4 φ — coupled φ-cadence battery (also G2 full-run context + G3 run 1).
	var phi_run := _run_coupled(1.0, 0.0, COUPLED_STEPS)
	var phi_topk := _rung_dist(phi_run["ey"], phi_run["ei"])
	var nullz := _lattice_null()
	var z_phi: float = (float(nullz["mu"]) - float(phi_topk["d_mean"])) / float(nullz["sigma"])

	# G4 uniform control — coupled uniform battery.
	var unif_run := _run_coupled(1.0, 1.0, COUPLED_STEPS)
	var unif_topk := _rung_dist(unif_run["ey"], unif_run["ei"])
	var z_unif: float = (float(nullz["mu"]) - float(unif_topk["d_mean"])) / float(nullz["sigma"])

	# G3 — determinism: repeat the exact φ-cadence run, byte-compare final probe.
	var phi_run2 := _run_coupled(1.0, 0.0, COUPLED_STEPS)
	var pey1: PackedByteArray = (phi_run["pey"] as PackedFloat32Array).to_byte_array()
	var pei1: PackedByteArray = (phi_run["pei"] as PackedFloat32Array).to_byte_array()
	var pey2: PackedByteArray = (phi_run2["pey"] as PackedFloat32Array).to_byte_array()
	var pei2: PackedByteArray = (phi_run2["pei"] as PackedFloat32Array).to_byte_array()
	var det_diff := _byte_diff(pey1, pey2) + _byte_diff(pei1, pei2)
	_check("G3: determinism — two φ-cadence runs byte-identical (0 bytes differ)",
		det_diff == 0, "bytes_diff=" + str(det_diff))

	# G4: structural gate.
	_check("G4: z_phi ≥ 2",
		z_phi >= 2.0, "z_phi=%.3f d_mean=%.4f (null μ=%.4f σ=%.4f)"
			% [z_phi, phi_topk["d_mean"], nullz["mu"], nullz["sigma"]])
	_check("G4: z_phi > z_uniform + 1",
		z_phi > (z_unif + 1.0),
		"z_phi=%.3f z_uniform=%.3f" % [z_phi, z_unif])

	# ── full-run charge context (documented, NOT a gate) ────────────────
	var sum_ic := 0.0
	for d in _ic: sum_ic += float(d[3]) + float(d[4])
	var sum_phi := _sum_field(phi_run["ey"], phi_run["ei"])
	var sum_unif := _sum_field(unif_run["ey"], unif_run["ei"])

	var dump := {
		"meta": {"date": "2026-08-14", "grid_n": GRID_N, "dt": DT, "k_max": K_MAX,
			"cadence_cycle": CADENCE_CYCLE, "isol_steps": ISOL_STEPS,
			"coupled_steps": COUPLED_STEPS, "top_k": TOP_K,
			"q_thresh": Q_THRESH, "q_sharp": Q_SHARP},
		"g1": {"pass": off["total"] == 0, "total_bytes_diff": off["total"],
			"per_step_bytes_diff": off["byte_diffs"]},
		"g2": {
			"phi_arm": {"pass": g2_phi["rel"] <= 1e-6, "rel": g2_phi["rel"],
				"max_delta": g2_phi["max_delta"], "tot_abs": g2_phi["tot_abs"], "deposit": g2_phi["deposit"]},
			"uniform_arm": {"pass": g2_unif["rel"] <= 1e-6, "rel": g2_unif["rel"],
				"max_delta": g2_unif["max_delta"], "tot_abs": g2_unif["tot_abs"], "deposit": g2_unif["deposit"]}},
		"g3": {"pass": det_diff == 0, "bytes_diff": det_diff},
		"g4": {
			"z_phi": z_phi, "z_uniform": z_unif,
			"phi_d_mean": phi_topk["d_mean"], "unif_d_mean": unif_topk["d_mean"],
			"null_mu": nullz["mu"], "null_sigma": nullz["sigma"],
			"null_cnt": nullz["cnt"],
			"phi_pass_z_ge_2": z_phi >= 2.0,
			"phi_pass_beats_uniform": z_phi > (z_unif + 1.0),
			"pass": (z_phi >= 2.0) and (z_phi > (z_unif + 1.0)),
			"phi_topk": phi_topk["cells"], "unif_topk": unif_topk["cells"]},
		"charge_context": {
			"ic_sum": sum_ic,
			"phi_sum_after_150": sum_phi, "phi_rel_drift": (sum_phi - sum_ic) / maxf(sum_ic, 1e-9),
			"unif_sum_after_150": sum_unif, "unif_rel_drift": (sum_unif - sum_ic) / maxf(sum_ic, 1e-9)},
		"final_probe_phi_b64": Marshalls.raw_to_base64(pey1),
		"final_probe_ei_phi_b64": Marshalls.raw_to_base64(pei1),
	}
	var f := FileAccess.open("res://_diag/qi_time_gpu.json", FileAccess.WRITE)
	if f == null:
		_check("JSON dump written to res://_diag/qi_time_gpu.json", false, "FileAccess failed")
	else:
		f.store_string(JSON.stringify(dump))
		f.close()
		_check("JSON dump written to res://_diag/qi_time_gpu.json", true)


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	if _rd != null:
		_rd.free_rid(_probe_ei); _rd.free_rid(_probe_ey)
		_rd.free_rid(_scratch); _rd.free_rid(_rho); _rd.free_rid(_vel)
		_rd.free_rid(_q); _rd.free_rid(_ei); _rd.free_rid(_ey)
		_rd.free_rid(_qt_pipe); _rd.free_rid(_qt_shader)
		_rd.free_rid(_tf_pipe); _rd.free_rid(_tf_shader)
	print("[VerifyQiTime] checks=%d failures=%d" % [_checks, _failures])
	if _failures == 0:
		print("[VerifyQiTime] RESULT: PASS — state dumped for qi_time_engine_report.md")
	else:
		print("[VerifyQiTime] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
