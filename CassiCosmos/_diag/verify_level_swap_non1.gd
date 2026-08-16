extends Node
## STAGED (NOT registered in the battery runner) — verify_level_swap #3
## "non-1 case" for the apply_level box-adoption fix (review_sim.md #3 /
## review_audit_2026-08-16.md #3).
##
## WHY THIS IS STAGED: it exercises a pre-swap box with box_scale != 1.0
## (a path the existing verify_level_swap scene never hits — that scene
## fixes the cube default aspect ONE + box_scale 1.0). It MUST be run on
## the GPU (windowed console exe, NEVER --headless) before it is promoted
## into the battery runner.
##
## THE FIX IT GUARDS: apply_level divides by the PRE-mutation extent
## (`pre_extent.x`) instead of the post-mutation `_extents().x` (which has
## already lost the pre-swap aspect after `box_aspect = Vector3.ONE`).
## Pre-swap geometry here: box_aspect = (0.8, 1, 1) and box_scale = 1.25,
## so aspect.x·box_scale = 1.0 — the pre-swap x-extent equals the base box
## (cluster_radius·1.5), and the level's declared extent (ent = 37.5 = the
## base box) is adopted EXACTLY with the fix:
##   box_scale_fixed = ent / pre_extent.x = 37.5 / 37.5 = 1.0
##   post extent      = 1.0 · 37.5 · 1.0 = 37.5 = ent.
## The OLD buggy divisor _extents().x post-aspect = 1.0·37.5·1.25 = 46.875
## would give box_scale = 37.5/46.875 = 0.8 → post extent 30 < ent, so the
## level's particles (authored up to ±0.9·ent = ±33.75) sit OUTSIDE the
## adopted box. So this scene FAILS on the pre-fix code and PASSES with the
## fix — a genuine detector.
##
## Assertions:
##   NB-1  apply_level returns true and adopts the level.
##   NB-2  the adopted box_scale equals ext.x / pre_adoption_extent.x
##         (the fixed formula), and the post-swap box x-extent equals the
##         level's declared extent (ent).
##   NB-3  every adopted particle sits inside the post-swap box.
##   NB-4  DEFAULT-OFF ADDITIVITY: with level_swap false apply_level is a
##         no-op and nothing is touched (guards the default live path).
##
## Run (windowed console exe — NEVER --headless, which has no RenderingDevice):
##   Godot_v4.7-stable_win64_console.exe --path <repo> res://_diag/verify_level_swap_non1.tscn

const GRID_N := 64
const PHI: float = 1.618033988749895
const ATTRACTOR_R: float = (PHI - 1.0) / (PHI + 1.0)   # φ⁻³ ≈ 0.236
const CELLS: int = GRID_N * GRID_N * GRID_N
const LEVEL_EXT := 37.5          # = cluster_radius·1.5 (level declares this physical extent)
const PARTICLE_SPAN := 0.9       # level particles authored up to ±PARTICLE_SPAN·ent
const PRE_ASPECT := Vector3(0.8, 1.0, 1.0)
const PRE_SCALE := 1.25
const BOX_TOL := 0.001           # fp tolerance on position-vs-box-edge

var _sim: Node
var _phase := 0
var _checks := 0
var _failures := 0
var _t0 := 0
var _frame := 0
var _level := "res://_diag/verify_level_non1_a"


func _ready() -> void:
	_t0 = Time.get_ticks_msec()
	_sim = $CassiSim
	_sim.grid_N = GRID_N
	_sim.box_aspect = PRE_ASPECT
	_sim.box_scale = PRE_SCALE
	_sim.cluster_radius = 25.0
	_sim.freeze_field = true
	_sim.playing = false
	_sim.level_swap = true
	_sim.reinit()
	_write_level(_level)


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		_frame += 1
		if _frame > 900:  # ~15 s — hang guard: the sim should be ready by now
			_check("sim became shaders-ready", false, "timeout waiting for _shaders_ready")
			_finish()
		return
	match _phase:
		0:
			# NB-4 additive check first: level_swap false → no-op.
			var pre_scale: float = _sim.box_scale
			var pre_aspect: Vector3 = _sim.box_aspect
			_sim.level_swap = false
			var r0: bool = _sim.apply_level(_level)
			_check("NB-4: apply_level is a no-op when level_swap off",
				not r0 and is_equal_approx(_sim.box_scale, pre_scale) and _sim.box_aspect == pre_aspect,
				"ret=%s box_scale %.4f->%.4f" % [r0, pre_scale, _sim.box_scale])
			# Enable the swap and capture the pre-adoption extent for NB-2.
			_sim.level_swap = true
			var pre_extent: Vector3 = _sim._extents()
			var ok: bool = _sim.apply_level(_level)
			_check("NB-1: apply_level accepted the level", ok, "ret=%s" % ok)
			_check("NB-1: level adopted", _sim._level == 5 and _sim._rung_anchor == 184,
				"level=%d rung=%d" % [_sim._level, _sim._rung_anchor])
			# NB-2: the fixed formula — box_scale == ext.x / pre_extent.x.
			var want_scale: float = LEVEL_EXT / maxf(pre_extent.x, 1e-30)
			_check("NB-2: box_scale == ext.x / pre_adoption_extent.x",
				is_equal_approx(_sim.box_scale, want_scale),
				"box_scale=%.6f want=%.6f pre_extent.x=%.3f" % [_sim.box_scale, want_scale, pre_extent.x])
			# NB-2b: with aspect.x·scale = 1.0 the pre-swap x-extent == the base box,
			# so the fixed adoption reproduces the level extent exactly.
			var post_extent: Vector3 = _sim._extents()
			_check("NB-2: post-swap box x-extent == level extent",
				is_equal_approx(post_extent.x, LEVEL_EXT),
				"ext.x=%.3f want=%.3f" % [post_extent.x, LEVEL_EXT])
			# NB-3: every adopted particle inside the post-swap box.
			var in_box: bool = _adopted_particles_in_box(post_extent)
			_check("NB-3: all adopted particles inside the new box",
				in_box, "ext=(%.2f, %.2f, %.2f)" % [post_extent.x, post_extent.y, post_extent.z])
			_phase = 1
		1:
			_finish()


## Read the sim's live position buffer and verify every particle's |pos|
## component is within the adopted box (plus fp tolerance).
func _adopted_particles_in_box(ext: Vector3) -> bool:
	if _sim == null or not _sim._pos_buf.is_valid():
		return false
	var n := _sim.N_particles
	if n <= 0:
		return _ext_vec_le(ext, Vector3.ZERO)
	var pos := _sim._rd.buffer_get_data(_sim._pos_buf, 0, n * 16).to_float32_array()
	if pos.size() < n * 4:
		return false
	var lim := Vector3(ext.x + BOX_TOL, ext.y + BOX_TOL, ext.z + BOX_TOL)
	for i in range(n):
		var b := i * 4
		var w := pos[b + 3]
		if w <= 0.0:
			continue   # dead particle — skip (liveness convention)
		if absf(pos[b]) > lim.x or absf(pos[b + 1]) > lim.y or absf(pos[b + 2]) > lim.z:
			return false
	return true


func _ext_vec_le(a: Vector3, b: Vector3) -> bool:
	return a.x <= b.x and a.y <= b.y and a.z <= b.z


# ── write a deterministic level dir (particles up to ±PARTICLE_SPAN·ent) ──
func _write_level(dir_root: String) -> void:
	var g := ProjectSettings.globalize_path(dir_root)
	if not DirAccess.dir_exists_absolute(g):
		DirAccess.make_dir_recursive_absolute(g)
	var ent: float = LEVEL_EXT
	var ey := PackedFloat32Array(); ey.resize(CELLS)
	var ei := PackedFloat32Array(); ei.resize(CELLS)
	var rng := RandomNumberGenerator.new()
	rng.seed = 5
	for c in range(CELLS):
		var r: float = ATTRACTOR_R + 0.02 * rng.randf_range(-1.0, 1.0)
		var amp: float = 0.999
		ei[c] = amp * (1.0 - r) * 0.5
		ey[c] = amp * (1.0 + r) * 0.5
	_write_raw(dir_root, "field_ey.raw", ey)
	_write_raw(dir_root, "field_ei.raw", ei)
	var n_particles := 300
	var px := PackedFloat32Array()
	var span := ent * PARTICLE_SPAN
	for p in range(n_particles):
		px.append(rng.randf_range(-span, span))
		px.append(rng.randf_range(-span, span))
		px.append(rng.randf_range(-span, span))
	_write_raw(dir_root, "particles.raw", px)
	var meta := {
		"grid_N": GRID_N,
		"extents": {"x": ent, "y": ent, "z": ent},
		"particle_count": n_particles,
		"level": 5,
		"rung_anchor": 184,
		"parent": "",
		"seed": 5,
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


func _check(name: String, ok: bool, detail: String = "") -> void:
	_checks += 1
	if not ok:
		_failures += 1
	print("[%s] %s %s" % ["PASS" if ok else "FAIL", name, detail])


func _finish() -> void:
	print("[VerifyLevelSwapNon1] checks=%d failures=%d elapsed=%d ms STAGED — needs a GPU run before battery registration"
		% [_checks, _failures, Time.get_ticks_msec() - _t0])
	if _failures == 0:
		print("[VerifyLevelSwapNon1] RESULT: PASS (staged)")
	else:
		print("[VerifyLevelSwapNon1] RESULT: FAIL")
	get_tree().quit(0 if _failures == 0 else 1)
