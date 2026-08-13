extends Node3D
## Survey exporter verification — a SceneTree probe (mirrors the
## verify_meshless_sim.gd instantiation pattern) that:
##   1. instantiates the sim with a SMALL config (playing=false, small
##      particle count, a few hundred physics steps on the default 64³ grid),
##   2. attaches cassi_survey.gd and triggers ONE snapshot programmatically,
##   3. writes a DIRECT reference read of the EY/EI field buffers to
##      res://_diag/survey_ref.raw / survey_ref_ei.raw,
##   4. prints [VerifySurvey] PASS/FAIL and quits.
##
## The Python gate research/meshless/survey_read.py checks that the dumped
## field_ey.raw equals _diag/survey_ref.raw EXACTLY (byte-for-byte), so the
## reference read must come from the SAME frozen sim state as the snapshot —
## the sim is paused (playing=false) and no steps run between the two reads.
##
## Run windowed via the console exe (the sim uses the global RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe \
##     --path <repo> res://scenes/verify_survey.tscn > _diag/survey_gpu.log 2>&1

const BATCH := 25
const N_BATCHES := 8   # 200 simulated steps — enough to evolve EY/EI trivially

var _sim: Node
var _survey: Node
var _phase := 0
var _batch := 0
var _survey_dir := ""


func _ready() -> void:
	_sim = $CassiSim
	_survey = $CassiSurvey


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	match _phase:
		0:
			# Deterministic smooth IC so the dumped fields are non-trivial.
			_write_smooth_ic()
			print("[VerifySurvey] smooth IC written — stepping physics")
			_phase = 1
		1:
			if _batch < N_BATCHES:
				_sim._run_physics_steps(BATCH)
				_batch += 1
			else:
				print("[VerifySurvey] %d steps run — triggering one survey dump" % [BATCH * N_BATCHES])
				var meta: Dictionary = _survey.take_snapshot()
				if meta.is_empty():
					print("[VerifySurvey] FAIL: survey snapshot returned empty")
					get_tree().quit(1)
					return
				_survey_dir = meta.get("dir_path", "")
				# Direct reference read of the FROZEN field buffers (the sim
				# stays paused; identical to what the survey just dumped).
				var N: int = _sim.grid_N
				var ey_ref: PackedByteArray = _sim._rd.buffer_get_data(_sim._field_ey, 0, N * N * N * 4)
				var ei_ref: PackedByteArray = _sim._rd.buffer_get_data(_sim._field_ei, 0, N * N * N * 4)
				_write_raw("res://_diag/survey_ref.raw", ey_ref)
				_write_raw("res://_diag/survey_ref_ei.raw", ei_ref)
				print("[VerifySurvey] snapshot dir = %s" % _survey_dir)
				print("[VerifySurvey] ref ey=%d bytes ei=%d bytes" % [ey_ref.size(), ei_ref.size()])
				print("[VerifySurvey] grid=%d³ particles=%d step=%d arm=%s" % [
					int(meta.get("grid_N", 0)), int(meta.get("particle_count", 0)),
					int(meta.get("step", 0)), meta.get("gravity_mode_name", "?")])
				_phase = 2
		2:
			print("[VerifySurvey] PASS — snapshot + reference written; quitting")
			get_tree().quit(0)


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
	var maxy := 0.0
	var maxi := 0.0
	for idx in range(nc):
		maxy = max(maxy, absf(ey[idx]))
		maxi = max(maxi, absf(ei[idx]))
	for idx in range(nc):
		var mi: float = ei[idx] / maxi
		var my: float = ey[idx] / maxy
		ei[idx] = 0.01 * (1.0 + 0.05 * mi)
		ey[idx] = 1.618033988749895 * ei[idx] + 0.0005 * (1.0 + 0.05 * my)
	_sim._rd.buffer_update(_sim._field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_sim._rd.buffer_update(_sim._field_ei, 0, ei.size() * 4, ei.to_byte_array())


func _write_raw(path: String, bytes: PackedByteArray) -> void:
	var f := FileAccess.open(ProjectSettings.globalize_path(path), FileAccess.WRITE)
	if f == null:
		print("[VerifySurvey] FAIL: cannot open %s (err %d)" % [path, FileAccess.get_open_error()])
		get_tree().quit(1)
		return
	f.store_buffer(bytes)
	f.close()
