extends Node3D
## q_coh band-calibration diag (2026-08-15).
##
## Mirrors the LIVE scenes/main.tscn physics config (2.5M particles, grid 64,
## river gravity, attractor init, mergers, BH accretion, box_scale 3.0) and
## samples the Qi-rainbow observable AT PARTICLE POSITIONS:
##
##     q_coh = ρ² / (ρ² + φ⁻² + ε²)   ρ = EY + EI,  ε = EY − φ·EI
##
## — the bounded [0,1) coherence the instancer shader maps to hue (the exact
## trilinear convention of compute/cassi_qhist.glsl's tri_* and
## cassi_instancer.glsl's tri_coherence, window offset included).
##
## Purpose: pin the fixed qi_cycle band (and the Fit-scale starting band) to
## the measured live distribution — the color scale must never be anchored to
## the unbounded intensity EY²+EI² (the old aligner's bug: the band chased a
## growing quantity, so colors constantly climbed toward white).
##
## Run (windowed, never headless): <exe> --path . res://_diag/diag_qcoh_band.tscn
## Prints a percentile table per epoch + the recommended band, writes
## res://_diag/qcoh_band_report.json, exits 0.

const PHI: float = 1.618033988749895
const PHI_INV2: float = 0.3819660112501051

const EPOCH_STEPS: int = 50
const TOTAL_STEPS: int = 400
const SAMPLE_STRIDE: int = 16     # 1-in-16 particles — the sim's own subsample convention
const LO_MARGIN: float = 1.3      # multiplicative margins, like the Auto-Track band
const HI_MARGIN: float = 1.3
const LO_CAP: float = 1e-6
const HI_CAP: float = 0.999

var sim: Node3D


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	if sim == null:
		push_error("diag_qcoh_band: CassiSim not found")
		get_tree().quit(1)
		return
	if not sim.has_method("_run_physics_steps"):
		push_error("diag_qcoh_band: CassiSim script not loaded (mid-edit?) — aborting")
		get_tree().quit(1)
		return
	sim.playing = false
	print("[diag-qcoh] grid=%d particles=%d dt=%.3f grav=%d box_scale=%.2f" % [
		sim.grid_N, sim.N_particles, sim.dt, sim.gravity_mode, sim.box_scale])
	await get_tree().process_frame
	await get_tree().process_frame
	var waited := 0
	while not sim._shaders_ready and waited < 600:
		waited += 1
		await get_tree().process_frame
	if not sim._shaders_ready:
		push_error("diag_qcoh_band: shaders never became ready")
		get_tree().quit(1)
		return
	print("[diag-qcoh] shaders ready after %d frames" % waited)

	var epochs: Array[Dictionary] = []
	var all_p1: PackedFloat32Array = PackedFloat32Array()
	var all_p99: PackedFloat32Array = PackedFloat32Array()
	for epoch in range(TOTAL_STEPS / EPOCH_STEPS + 1):
		if epoch > 0:
			sim._run_physics_steps(EPOCH_STEPS)
			await get_tree().process_frame
		var d: Dictionary = _sample()
		epochs.append(d)
		if d.size() > 0:
			all_p1.append(d["p1"])
			all_p99.append(d["p99"])
			print("[diag-qcoh] t=%5.1f  p1=%s p10=%s p50=%s p90=%s p99=%s max=%s" % [
				d["t"], _sci(d["p1"]), _sci(d["p10"]), _sci(d["p50"]), _sci(d["p90"]), _sci(d["p99"]), _sci(d["max"])])

	# Recommended fixed band: floor just below the epoch-min p1, top just
	# above the epoch-max p99 — clamped into the bounded channel.
	var q_floor: float = 0.0
	var q_one: float = 0.0
	if all_p1.size() > 0:
		var mn: float = all_p1[0]
		var mx: float = all_p99[0]
		for i in range(1, all_p1.size()):
			mn = minf(mn, all_p1[i])
			mx = maxf(mx, all_p99[i])
		q_floor = clampf(mn / LO_MARGIN, LO_CAP, HI_CAP)
		q_one = clampf(mx * HI_MARGIN, q_floor, HI_CAP)
		if q_one <= q_floor * 1.001:
			q_one = q_floor * 1.001
	print("")
	print("[diag-qcoh] recommended fixed band: qi_cycle = (%s, %s)" % [_sci(q_floor), _sci(q_one)])
	print("[diag-qcoh]   log span = %.2f decades; approach entry %s → φ⁻² = %.6f (white)" % [
		log(q_one / q_floor) / log(10.0) if q_floor > 0.0 else 0.0, _sci(q_one), PHI_INV2])

	var report := {
		"config": {
			"grid_N": sim.grid_N, "N_particles": sim.N_particles, "dt": sim.dt,
			"cluster_radius": sim.cluster_radius, "box_scale": sim.box_scale,
			"gravity_mode": sim.gravity_mode, "river_calibrate_gn": sim.river_calibrate_gn,
			"field_attractor_init": sim.field_attractor_init,
			"multi_rung_seed": sim.multi_rung_seed, "multi_rung_count": sim.multi_rung_count,
			"black_holes_enabled": sim.black_holes_enabled,
			"particle_merge": sim.particle_merge, "bh_accretion": sim.bh_accretion,
			"source_strength": sim.source_strength,
		},
		"epochs": epochs,
		"recommended_band": [q_floor, q_one],
		"phi_inv2": PHI_INV2,
	}
	var f := FileAccess.open("res://_diag/qcoh_band_report.json", FileAccess.WRITE)
	if f != null:
		f.store_string(JSON.stringify(report, "\t"))
		f.close()
	print("[diag-qcoh] report -> res://_diag/qcoh_band_report.json")
	get_tree().quit(0)


## Sample q_coh at strided particle positions; return percentiles.
func _sample() -> Dictionary:
	var res: Dictionary = {"t": float(sim._step_count) * sim.dt}
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var np: int = sim.N_particles
	if np <= 0:
		return res
	var ext: Vector3 = sim._extents()
	var pos: PackedFloat32Array = sim._rd.buffer_get_data(sim._pos_buf, 0, np * 16).to_float32_array()
	var ey: PackedFloat32Array = sim._rd.buffer_get_data(sim._field_ey, 0, nc * 4).to_float32_array()
	var ei: PackedFloat32Array = sim._rd.buffer_get_data(sim._field_ei, 0, nc * 4).to_float32_array()
	if pos.size() < np * 4 or ey.size() < nc or ei.size() < nc:
		return res
	var win: Vector3 = sim._window_center
	var hn: float = float(N) * 0.5
	var vals := PackedFloat32Array()
	for i in range(0, np, SAMPLE_STRIDE):
		var b: int = i * 4
		var gc: Vector3 = (Vector3(pos[b], pos[b + 1], pos[b + 2]) - win) * hn
		gc = Vector3(gc.x / maxf(ext.x, 0.0001), gc.y / maxf(ext.y, 0.0001), gc.z / maxf(ext.z, 0.0001)) + Vector3(hn, hn, hn)
		var i0: int = int(floor(gc.x))
		var j0: int = int(floor(gc.y))
		var k0: int = int(floor(gc.z))
		var fx: float = gc.x - float(i0)
		var fy: float = gc.y - float(j0)
		var fz: float = gc.z - float(k0)
		i0 = ((i0 % N) + N) % N
		j0 = ((j0 % N) + N) % N
		k0 = ((k0 % N) + N) % N
		var i1: int = (i0 + 1) % N
		var j1: int = (j0 + 1) % N
		var k1: int = (k0 + 1) % N
		var eyv := _tri(ey, N, i0, j0, k0, i1, j1, k1, fx, fy, fz)
		var eiv := _tri(ei, N, i0, j0, k0, i1, j1, k1, fx, fy, fz)
		var rho: float = eyv + eiv
		var eps: float = eyv - PHI * eiv
		var rho2: float = rho * rho
		var qc: float = rho2 / (rho2 + PHI_INV2 + eps * eps)
		if not is_finite(qc):
			continue
		vals.append(clampf(qc, 0.0, 1.0))
	if vals.size() < 64:
		return res
	vals.sort()
	var pct := func(i: int, f: float) -> float:
		var idx: int = clampi(int(round(float(vals.size() - 1) * f)), 0, vals.size() - 1)
		return vals[idx]
	res["n"] = vals.size()
	res["p1"] = pct.call(0, 0.01)
	res["p10"] = pct.call(0, 0.10)
	res["p50"] = pct.call(0, 0.50)
	res["p90"] = pct.call(0, 0.90)
	res["p99"] = pct.call(0, 0.99)
	res["max"] = vals[vals.size() - 1]
	return res


func _sci(v: float) -> String:
	if v == 0.0:
		return "0"
	var e: int = int(floor(log(absf(v)) / log(10.0)))
	var m: float = v / pow(10.0, float(e))
	return "%.2fe%d" % [m, e]


func _tri(a: PackedFloat32Array, N: int, i0: int, j0: int, k0: int,
		i1: int, j1: int, k1: int, fx: float, fy: float, fz: float) -> float:
	var v000: float = a[i0 + N * (j0 + N * k0)]
	var v100: float = a[i1 + N * (j0 + N * k0)]
	var v010: float = a[i0 + N * (j1 + N * k0)]
	var v110: float = a[i1 + N * (j1 + N * k0)]
	var v001: float = a[i0 + N * (j0 + N * k1)]
	var v101: float = a[i1 + N * (j0 + N * k1)]
	var v011: float = a[i0 + N * (j1 + N * k1)]
	var v111: float = a[i1 + N * (j1 + N * k1)]
	var q0: float = lerpf(lerpf(v000, v100, fx), lerpf(v010, v110, fx), fy)
	var q1: float = lerpf(lerpf(v001, v101, fx), lerpf(v011, v111, fx), fy)
	return lerpf(q0, q1, fz)
