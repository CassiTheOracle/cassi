extends Node3D
## Integration verify — the sim's MESHLESS arm vs its GRID arm, from the
## SAME initial condition (MESHLESS_PLAN.md §10's cross-solver agreement
## contract). Drives the CassiSim node twice — once with the grid
## two-fluid PDE, once with the moving Voronoi cell arm — collecting the
## mean-deviation trajectory d(t) and the final field of each, then dumps
## everything to res://_diag/meshless_sim_gpu.json for the numpy gate
## research/meshless/stage4_verify.py (breather ≈ √(ω₀²(1+φ)), no NaN,
## cross-arm field agreement).
##
## RECONSTRUCTION (the square-ripples fix): the raster now reconstructs a
## LINEAR field from the Green-Gauss gradient, so arm B's grid output is
## NOT the raw cell-averaged state. The physics-identity gate must compare
## the two arms at the CELL-AVERAGE level, not through the reconstruction:
##   • G11 (physics identity) — arm B's PIECEWISE-CONSTANT field built from
##     its per-site psi + labels (the cell averages on the grid), vs arm A.
##   • G12' (rendered field, HONEST) — arm B's RECONSTRUCTED field vs arm A,
##     reported separately with its own threshold (reconstruction + JFA
##     sampling add error the physics gate must not absorb).
## Arm B dumps per-site psi, labels, sites AND the reconstructed grid field.
##
## Arm B re-inits the sim (meshless_mode = true), then RESTORES arm A's
## IC into the field buffers and re-runs the meshless init sampling so
## both arms start from the identical field.
##
## Run: godot --path <repo> res://scenes/verify_meshless_sim.tscn
##      (windowed — the sim uses the global RD)

const BATCH := 25
const N_BATCHES := 60
const PHI := 1.618033988749895

var _sim: Node
var _phase := 0
var _batch := 0
var _frames := 0
var _d_a: Array[float] = []
var _d_b: Array[float] = []
var _ey_a := PackedFloat32Array()
var _ey_b := PackedFloat32Array()
var _ic_ey := PackedByteArray()
var _ic_ei := PackedByteArray()
var _psi_y_b := PackedByteArray()  # arm B per-site state (cell averages)
var _psi_i_b := PackedByteArray()
var _labels_b := PackedByteArray()  # arm B JFA labels
var _sites_b := PackedByteArray()   # arm B site positions
var _n_sites_b := 0


func _ready() -> void:
	_sim = $CassiSim
	# PIN the cross-arm agreement battery against the campaign defaults
	# (meshless/tree/φ-aspect/dual now default on): Arm A must run the
	# GRID solver on the CUBE single-lattice field (Arm B flips to
	# meshless at line 69 below), and neither arm runs tree gravity.
	_sim.meshless_mode = false
	_sim.meshless_gravity = false
	_sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	_sim.dual_grid = false
	_sim.reinit()  # re-materialize the cube grid / meshless-off state for Arm A
	_sim.playing = false


func _process(_delta: float) -> void:
	_frames += 1
	if _sim == null or not _sim._shaders_ready:
		return
	match _phase:
		0:
			# write a SMOOTH deterministic IC into the field buffers
			# (the research 6-mode recipe in the sim's units + a constant
			# deviation offset so d(t) breathes) — the sim's white-noise
			# init aliases differently onto the mesh's cell sampling, so
			# the cross-arm gate runs on the resolved smooth physics
			_write_smooth_ic()
			_ic_ey = _sim._rd.buffer_get_data(_sim._field_ey, 0, _n3() * 4)
			_ic_ei = _sim._rd.buffer_get_data(_sim._field_ei, 0, _n3() * 4)
			print("[VerifyMeshlessSim] smooth IC written — running arm A (grid)")
			_phase = 1
		1:
			if _batch < N_BATCHES:
				_sim._run_physics_steps(BATCH)
				_d_a.append(_mean_dev())
				_batch += 1
				if _batch % 20 == 0:
					print("[VerifyMeshlessSim] arm A batch %d/%d d=%.6f"
						% [_batch, N_BATCHES, _d_a[_batch - 1]])
			else:
				_ey_a = _sim._rd.buffer_get_data(_sim._field_ey, 0, _n3() * 4).to_float32_array()
				print("[VerifyMeshlessSim] arm A done — switching to arm B (meshless)")
				_batch = 0
				_phase = 2
		2:
			# reinit with the meshless arm, restore arm A's IC, re-sample
			_sim.meshless_mode = true
			_sim.reinit()
			_sim._rd.buffer_update(_sim._field_ey, 0, _ic_ey.size(), _ic_ey)
			_sim._rd.buffer_update(_sim._field_ei, 0, _ic_ei.size(), _ic_ei)
			_sim._meshless_init()
			print("[VerifyMeshlessSim] arm B re-inited — running (meshless)")
			_phase = 3
		3:
			if _batch < N_BATCHES:
				_sim._run_physics_steps(BATCH)
				_d_b.append(_mean_dev())
				_batch += 1
				if _batch % 20 == 0:
					print("[VerifyMeshlessSim] arm B batch %d/%d d=%.6f"
						% [_batch, N_BATCHES, _d_b[_batch - 1]])
			else:
				# arm B: capture the RECONSTRUCTED grid field (the rendered one)
				_ey_b = _sim._rd.buffer_get_data(_sim._field_ey, 0, _n3() * 4).to_float32_array()
				# AND the per-site cell-averaged state + labels + sites, so the
				# numpy gate builds the piecewise-constant cell-average grid
				# field for the physics-identity comparison (the reconstruction
				# must not be absorbed into the physics gate).
				_n_sites_b = 2 * _sim.ML_N1 * _sim.ML_N1 * _sim.ML_N1
				_psi_y_b = _sim._rd.buffer_get_data(_sim._ml_psi_y, 0, _n_sites_b * 4)
				_psi_i_b = _sim._rd.buffer_get_data(_sim._ml_psi_i, 0, _n_sites_b * 4)
				_labels_b = _sim._rd.buffer_get_data(_sim._ml_labels_a, 0, _n3() * 4)
				_sites_b = _sim._rd.buffer_get_data(_sim._ml_sites, 0, _n_sites_b * 16)
				_dump()
				get_tree().quit(0)
		4:
			pass


func _n3() -> int:
	var N: int = _sim.grid_N
	return N * N * N


func _mean_dev() -> float:
	var N: int = _sim.grid_N
	var ey: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._field_ey, 0, N * N * N * 4).to_float32_array()
	var ei: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._field_ei, 0, N * N * N * 4).to_float32_array()
	var s := 0.0
	for idx in range(N * N * N):
		s += ey[idx] - PHI * ei[idx]
	return s / float(N * N * N)


func _write_smooth_ic() -> void:

	var N: int = _sim.grid_N
	var nc := N * N * N
	var ey := PackedFloat32Array()
	var ei := PackedFloat32Array()
	ey.resize(nc)
	ei.resize(nc)
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	for m in range(6):
		var nx := rng.randi_range(1, 3)
		var ny := rng.randi_range(1, 3)
		var nz := rng.randi_range(1, 3)
		var km: float = sqrt(float(nx * nx + ny * ny + nz * nz))
		var ph := rng.randf() * 6.283185307179586
		var ph2 := rng.randf() * 6.283185307179586
		for i in range(N):
			for j in range(N):
				for k in range(N):
					var ang: float = 6.283185307179586 * float(nx * i + ny * j + nz * k) / float(N)
					var idx := i * N * N + j * N + k
					ey[idx] += cos(ang + ph) / km
					ei[idx] += cos(ang + ph2) / km
	# normalize the mode sums, then assemble the sim-scale field:
	# ei = 0.01·(1 + 0.05·modes), ey = φ·ei + 5e-4·(1 + 0.05·modes2)
	var maxy := 0.0
	var maxi := 0.0
	for idx in range(nc):
		maxy = max(maxy, absf(ey[idx]))
		maxi = max(maxi, absf(ei[idx]))
	for idx in range(nc):
		var mi: float = ei[idx] / maxi
		var my: float = ey[idx] / maxy
		ei[idx] = 0.01 * (1.0 + 0.05 * mi)
		ey[idx] = PHI * ei[idx] + 0.0005 * (1.0 + 0.05 * my)
	_sim._rd.buffer_update(_sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_sim._rd.buffer_update(_sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())





func _dump() -> void:
	var nan := false
	for v in _ey_b:
		if is_nan(v) or is_inf(v):
			nan = true
	if nan:
		print("[VerifyMeshlessSim] FAIL: NaN/Inf in the meshless final field")
		get_tree().quit(1)
		return
	var d := {
		"N": _sim.grid_N, "dt": _sim.dt, "batch": BATCH, "n_batches": N_BATCHES,
		"d_a": Array(_d_a), "d_b": Array(_d_b),
		"ey_a_b64": Marshalls.raw_to_base64(_ey_a.to_byte_array()),
		"ey_b_b64": Marshalls.raw_to_base64(_ey_b.to_byte_array()),
		"ic_ey_b64": Marshalls.raw_to_base64(_ic_ey),
		"ic_ei_b64": Marshalls.raw_to_base64(_ic_ei),
		# arm B per-site cell-averaged state + labels + sites: the numpy gate
		# builds the piecewise-constant cell-average grid field (physics
		# identity) separately from the reconstructed field (rendered).
		"n_sites_b": _n_sites_b,
		"psi_y_b_b64": Marshalls.raw_to_base64(_psi_y_b),
		"psi_i_b_b64": Marshalls.raw_to_base64(_psi_i_b),
		"labels_b_b64": Marshalls.raw_to_base64(_labels_b),
		"sites_b_b64": Marshalls.raw_to_base64(_sites_b),
	}
	var f := FileAccess.open("res://_diag/meshless_sim_gpu.json", FileAccess.WRITE)
	if f == null:
		print("[VerifyMeshlessSim] FAIL: JSON dump failed")
		get_tree().quit(1)
		return
	f.store_string(JSON.stringify(d))
	f.close()
	print("[VerifyMeshlessSim] RESULT: PASS — state dumped for stage4_verify.py")
