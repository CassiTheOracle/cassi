extends Node3D
## Stability verify — the meshless arm under the LIVE-sim conditions that
## collapsed it (the default FLAT-NOISE field init, where rho = EY+EI ≈ 0
## at most sites, plus the live mass-deposit/river chain). Drives 2000
## steps (80 steering rebuilds) and gates the site spread: the Voronoi
## sites must keep covering the box (>= 50% per axis) instead of
## clumping, and the field must stay finite.
##
## Run: godot --path <repo> res://scenes/verify_meshless_stability.tscn
##      (windowed — the sim uses the global RD)

const BATCH := 25
const N_BATCHES := 80

var _sim: Node
var _phase := 0
var _batch := 0
var _frames := 0


func _ready() -> void:
	_sim = $CassiSim


func _process(_delta: float) -> void:
	_frames += 1
	if _sim == null or not _sim._shaders_ready:
		return
	match _phase:
		0:
			print("[VerifyMeshlessStability] running %d steps (flat-noise field + deposit + river)"
				% [BATCH * N_BATCHES])
			_phase = 1
		1:
			if _batch < N_BATCHES:
				_sim._run_physics_steps(BATCH)
				_batch += 1
				if _batch % 20 == 0:
					print("[VerifyMeshlessStability] batch %d/%d" % [_batch, N_BATCHES])
			else:
				_check_spread()
				_phase = 2
		2:
			pass


func _check_spread() -> void:
	var fails := 0
	# field health
	var ey: PackedFloat32Array = _sim._rd.buffer_get_data(_sim._field_ey, 0,
		_sim.grid_N * _sim.grid_N * _sim.grid_N * 4).to_float32_array()
	var nan := false
	for v in ey:
		if is_nan(v) or is_inf(v):
			nan = true
	if nan:
		fails += 1
		print("[VerifyMeshlessStability] FAIL: NaN/Inf in the rasterized field")
	else:
		print("[VerifyMeshlessStability] field finite")

	# site spread: the bounding box of the sites vs the mesh world
	var sites: PackedFloat32Array = _sim._ml_sites_cpu
	var n: int = sites.size() / 4
	var mn := Vector3(INF, INF, INF)
	var mx := Vector3(-INF, -INF, -INF)
	for s in range(n):
		mn.x = minf(mn.x, sites[s * 4])
		mn.y = minf(mn.y, sites[s * 4 + 1])
		mn.z = minf(mn.z, sites[s * 4 + 2])
		mx.x = maxf(mx.x, sites[s * 4])
		mx.y = maxf(mx.y, sites[s * 4 + 1])
		mx.z = maxf(mx.z, sites[s * 4 + 2])
	var L: float = 2.0 * _sim._extent_min()
	var sx: float = (mx.x - mn.x) / L
	var sy: float = (mx.y - mn.y) / L
	var sz: float = (mx.z - mn.z) / L
	print("[VerifyMeshlessStability] site spread: x=%.3f y=%.3f z=%.3f of the box"
		% [sx, sy, sz])
	if sx < 0.5 or sy < 0.5 or sz < 0.5:
		fails += 1
		print("[VerifyMeshlessStability] FAIL: sites clumped (spread < 50%%)")

	if fails == 0:
		print("[VerifyMeshlessStability] RESULT: PASS")
		get_tree().quit(0)
	else:
		print("[VerifyMeshlessStability] RESULT: FAIL")
		get_tree().quit(1)
