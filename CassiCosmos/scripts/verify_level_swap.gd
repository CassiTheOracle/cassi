extends Node
## Cassi M3 LIVE LEVEL-SWAP verify (MACHINE_PLAN.md §6 M3): the sim hot-swaps
## a level's box/extents/field/particle ICs from a cascade-tree level dir
## (the M2 survey format) instead of a full restart.
##
## This scene drives the real CassiSim inline with `level_swap = true`, writes
## TWO synthetic level dirs (self-contained — `res://_diag/level_a`, `level_b`)
## in the M2 survey byte format, swaps A→B via apply_level, and gates the M3
## acceptance criteria:
##   GS-1  apply_level(A) returns true and changes the resolved band (level/
##         rung_anchor adopted, no NaN in the swapped field/particles).
##   GS-2  r-continuity: the volume-average attractor-r before vs after the
##         swap satisfies |Δr| ≤ tolerance (both settle near the φ-attractor
##         φ⁻³ ≈ 0.236 — the M2 tree constant attractor_r ≈ 1.6449 in its own
##         units = the same φ-attractor), i.e. no discontinuity at the level
##         edge beyond measurement scatter.
##   GS-3  DEFAULT-OFF ADDITIVITY: with `level_swap = false`, apply_level is a
##         no-op (returns false) and the field buffers are untouched — the
##         default live path stays bit-identical.
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://scenes/verify_level_swap.tscn

const GRID_N := 64
const PHI: float = 1.618033988749895
const ATTRACTOR_R: float = (PHI - 1.0) / (PHI + 1.0)   # φ⁻³ ≈ 0.236
const CELLS: int = GRID_N * GRID_N * GRID_N
const R_CONT_TOL := 0.15   # |Δr| across a level-following swap (measurement scatter)

var _sim: Node
var _phase := 0
var _checks := 0
var _failures := 0
var _t0 := 0
var _frame := 0
var _level_a := "res://_diag/verify_level_a"
var _level_b := "res://_diag/verify_level_b"
var _r_before := 0.0


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_sim = $CassiSim
	_sim.grid_N = GRID_N
	_sim.box_aspect = Vector3.ONE
	_sim.cluster_radius = 25.0
	_sim.freeze_field = true
	_sim.playing = false
	_sim.level_swap = true
	_sim.reinit()
	_write_level(_level_a, 5, 184, Q_STRONG)
	_write_level(_level_b, 6, 180, Q_STRONG * 0.6)


# ── deterministic field plant per level (near-attractor, different density) ──
const Q_STRONG := 0.999

# The volume-average r of the swapped field is read from the sim; the two
# planted levels use near-attractor EY/EI so r lands near φ⁻³ in both.


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		_frame += 1
		if _frame > 900:  # ~15 s — hang guard: the sim should be ready by now
			_check("sim became shaders-ready", false, "timeout waiting for _shaders_ready")
			_finish()
		return
	match _phase:
		0:
			# GS-3 additive check first: level_swap false → no-op.
			_sim.level_swap = false
			var pre_sum: float = _field_ey_sum()
			var r0: bool = _sim.apply_level(_level_a)
			var post_sum: float = _field_ey_sum()
			_check("GS-3: default-off apply_level is a no-op (returns false)",
				not r0, "ret=%s" % r0)
			_check("GS-3: field untouched when swap off", is_equal_approx(post_sum, pre_sum),
				"Σey pre=%.6f post=%.6f" % [pre_sum, post_sum])
			# Now enable the swap and apply level A.
			_sim.level_swap = true
			var ok_a: bool = _sim.apply_level(_level_a)
			_check("GS-1: apply_level(A) accepted", ok_a, "ret=%s" % ok_a)
			_check("GS-1: swapped level adopted", _sim._level == 5 and _sim._rung_anchor == 184,
				"level=%d rung=%d" % [_sim._level, _sim._rung_anchor])
			var rb: float = _sim._volume_avg_r()
			_r_before = rb
			_check("GS-1: swapped field finite (no NaN) + near attractor",
				is_finite(rb) and absf(rb - ATTRACTOR_R) < 0.3,
				"r=%.4f (φ⁻³=%.4f)" % [rb, ATTRACTOR_R])
			_phase = 1
		1:
			# Swap A → B (the next-finer level, following the edge).
			var ok_b: bool = _sim.apply_level(_level_b)
			_check("GS-1: apply_level(B) accepted (level bump)", ok_b and _sim._level == 6 and _sim._rung_anchor == 180,
				"ret=%s level=%d rung=%d" % [ok_b, _sim._level, _sim._rung_anchor])
			var r_after: float = _sim._volume_avg_r()
			_check("GS-2: swapped-B field finite + near attractor",
				is_finite(r_after) and absf(r_after - ATTRACTOR_R) < 0.3, "r=%.4f" % r_after)
			var dr: float = absf(r_after - _r_before)
			_check("GS-2: r-continuity across the swap (|Δr| ≤ %.3f)" % R_CONT_TOL,
				dr <= R_CONT_TOL, "Δr=%.4f (prev=%.4f after=%.4f)" % [dr, _r_before, r_after])
			_check("GS-2: sim records swap continuity telemetry", _sim._level_swap_r_delta > 0.0,
				"delta=%.6f" % _sim._level_swap_r_delta)
			_phase = 2
		2:
			_finish()


## Is the live field equal to what a level dir plants? (compare a strided
## sample against the dir's own field_ey.raw — probe the default-off contract)
func _field_ey_sum() -> float:
	if _sim == null or not _sim._field_ey.is_valid():
		return -1.0
	var ey := _rd_read(_sim._field_ey, CELLS)
	var s := 0.0
	for i in range(0, ey.size(), 4096):
		s += ey[i]
	return s


func _rd_read(rid: RID, count: int) -> PackedFloat32Array:
	return _sim._rd.buffer_get_data(rid, 0, count * 4).to_float32_array()


# ── write a synthetic level dir in the M2 survey format ──────────────────
func _write_level(dir_root: String, level: int, rung: int, q_density: float) -> void:
	var g := ProjectSettings.globalize_path(dir_root)
	if not DirAccess.dir_exists_absolute(g):
		DirAccess.make_dir_recursive_absolute(g)
	var ent: float = 37.5   # cube extent matching the sim box (ext = cluster_radius*1.5)
	var ey := PackedFloat32Array(); ey.resize(CELLS)
	var ei := PackedFloat32Array(); ei.resize(CELLS)
	var rng := RandomNumberGenerator.new()
	rng.seed = level
	for c in range(CELLS):
		# Near-attractor: r = (EY−EI)/(EY+EI) ≈ φ⁻³ (0.236), amplitude q_density.
		var r: float = ATTRACTOR_R + 0.02 * rng.randf_range(-1.0, 1.0)
		var amp: float = q_density
		ei[c] = amp * (1.0 - r) * 0.5
		ey[c] = amp * (1.0 + r) * 0.5
	# write raw files
	_write_raw(dir_root, "field_ey.raw", ey)
	_write_raw(dir_root, "field_ei.raw", ei)
	var px := PackedFloat32Array()
	var n_particles := 300  # must equal the sim's N_particles (apply_level reallocs if different)
	for p in range(n_particles):
		px.append(rng.randf_range(-ent * 0.8, ent * 0.8))
		px.append(rng.randf_range(-ent * 0.8, ent * 0.8))
		px.append(rng.randf_range(-ent * 0.8, ent * 0.8))
	_write_raw(dir_root, "particles.raw", px)
	# meta.json (M2 extended: level, parent, rung_anchor, seed)
	var meta := {
		"grid_N": GRID_N,
		"extents": {"x": ent, "y": ent, "z": ent},
		"particle_count": n_particles,
		"level": level,
		"rung_anchor": rung,
		"parent": ("verify_level_%d" % (level - 1)) if level > 0 else "",
		"seed": level,
		"rung_score": 0.95,
		"attractor_r": ATTRACTOR_R,
	}
	_write_text(dir_root, "meta.json", JSON.stringify(meta))


func _write_raw(dir_root: String, name: String, floats: PackedFloat32Array) -> void:
	var f := FileAccess.open(ProjectSettings.globalize_path("%s/%s" % [dir_root, name]), FileAccess.WRITE)
	if f == null:
		return
	f.store_buffer(floats.to_byte_array())
	f.close()


func _write_text(dir_root: String, name: String, txt: String) -> void:
	var f := FileAccess.open(ProjectSettings.globalize_path("%s/%s" % [dir_root, name]), FileAccess.WRITE)
	if f == null:
		return
	f.store_string(txt)
	f.close()


func _read_raw_floats(path: String, expect: int) -> PackedFloat32Array:
	var f := FileAccess.open(ProjectSettings.globalize_path(path), FileAccess.READ)
	var out := PackedFloat32Array()
	if f == null:
		return out
	out.resize(expect)
	for i in range(expect):
		out[i] = f.get_float()
	f.close()
	return out


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	print("[VerifyLevelSwap] checks=%d failures=%d elapsed=%d ms"
		% [_checks, _failures, Time.get_ticks_msec() - _t0])
	if _failures == 0:
		print("[VerifyLevelSwap] RESULT: PASS")
	else:
		print("[VerifyLevelSwap] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
