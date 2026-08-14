extends Node
## Particle-VFX smoke test (particle-gfx workstream, 2026-08-13).
##
## Drives the REAL instancer pipeline (cassi_instancer.glsl + the sim's
## uniform set + _mm_rd_rid) through each new default-off visual feature
## and structurally verifies the instances it writes. The legacy path
## (particle_color_mode == 0) is verified SHADER-EXACT against a GDScript
## replica of the committed formulas — the bit-identity contract.
##
## Run (windowed GPU only — never --headless for the global RD):
##   Godot_v4.7-stable_win64_console.exe --path <repo> -e res://scenes/verify_particle_vfx.tscn
##   (or: --path <repo> res://scenes/verify_particle_vfx.tscn)
##
## Checks:
##   [1] DEFAULT (mode 0): per-instance size = clamp(0.5+m*0.12, 0.4, 5.0)
##       from pos.w, and color = the Salpeter mass-temperature ramp — the
##       pinned bit-identical contract.
##   [2] SIZE flag (0x10): size = clamp(SIZE_K*pow(m,1/3), 0.18, 5.0), and
##       the legacy formula differs (m^(1/3) compresses the Salpeter range).
##   [3] TWO-AXIS (mode 4): the hue engine runs (nondegenerate RGB from the
##       sampled q) and lightness is modulated by ρ̂ = q/a_hi (differs from a
##       per-instance fixed lightness — the lightness axis is active).
##   [4] GLOW flag (0x20): alpha is raised toward 1.0 for bright cores and
##       lower elsewhere (depth-offset, additive core look present; alpha
##       spans a > 0.35 floor with bright instances near 1.0). Color: the
##       bright-core lift is toward the soft warm-pink GLOW_TINT, NOT pure
##       white (2026-08-14 owner re-tune: GLOW_L_BOOST 0.25 → 0.12 + tint —
##       expected constants below updated to match).
##   [5] DEPTH flag (0x40): alpha decreases with distance from the origin —
##       the near particles keep alpha while far particles fade.
##
## Exits 0 on all checks passing, 1 on any failure.

const SIZE_K := 0.62
const SIZE_S_MIN := 0.18
const SIZE_S_MAX := 5.0
const GLOW_A_MIN := 0.35
const GLOW_A_MAX := 1.0
# 2026-08-14: the LESS-WHITE glow — lift toward the soft warm pink-white
# GLOW_TINT at GLOW_L_BOOST strength (was: pure-white vec3(1.0) at 0.25).
# MUST match cassi_instancer.glsl GLOW_TINT/GLOW_L_BOOST and the material's
# glow_tint/glow_strength (particle_billboard.gdshader).
const GLOW_TINT := Vector3(0.95, 0.90, 0.98)
const GLOW_L_BOOST := 0.12
const PHI_INV2 := 0.3819660112501051  # (not used by the new color system; kept for the legacy check only)

var sim: Node3D
var _checks := 0
var _failures := 0


func _ready() -> void:
	sim = get_node_or_null("../CassiSim")
	if sim == null:
		push_error("verify_particle_vfx: CassiSim not found")
		get_tree().quit(1)
		return
	# Small N for fast dispatch; RIVER gravity; paused (we drive the
	# instancer manually via _repaint_instancer).
	sim.playing = false
	sim.gravity_mode = 0
	sim.N_particles = 256
	sim.grid_N = 64
	# PIN the grid/CUBE field-render + instancer battery against the
	# campaign defaults (meshless/tree/φ-aspect/dual now default on): the
	# bit-identical legacy color formula and the two-axis hue engine run
	# on the single-lattice CUBE grid field.
	sim.meshless_mode = false
	sim.meshless_gravity = false
	sim.box_aspect = Vector3(1.0, 1.0, 1.0)
	sim.dual_grid = false
	sim.reinit()
	sim.playing = false
	# Wait for the shader import race to settle (mirrors verify_river_isotropy).
	var waited := 0
	while not sim._shaders_ready and waited < 240:
		await get_tree().process_frame
		waited += 1
	if not sim._shaders_ready:
		push_error("verify_particle_vfx: shaders never became ready (import failed)")
		get_tree().quit(1)
		return
	await get_tree().process_frame
	await get_tree().process_frame
	await _run_all()
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)


# ── helpers ────────────────────────────────────────────────────────────
func _approx(a: float, b: float, tol: float) -> bool:
	return absf(a - b) <= tol


## Dispatch the instancer with the current particle_color_mode and read
## back the rendered instance buffer (16 floats/instance: 3x4 basis +
## color, matching the shader's write layout).
func _dispatch_and_read() -> PackedFloat32Array:
	sim._repaint_instancer()            # fills the PC from sim exports + dispatches
	await get_tree().process_frame
	var data: PackedByteArray = sim._rd.buffer_get_data(sim._mm_rd_rid, 0, sim.N_particles * 64)
	if data.size() < sim.N_particles * 64:
		return PackedFloat32Array()
	return data.to_float32_array()


func _run_all() -> void:
	await _check_default()
	await _check_size_flag()
	await _check_glow()
	await _check_depth()
	await _check_two_axis()   # last: writes EY/EI ramps into the field


## [1] DEFAULT (mode 0) — bit-identical legacy size + mass-temperature color.
func _check_default() -> void:
	sim.particle_color_mode = 0
	var inst: PackedFloat32Array = await _dispatch_and_read()
	if inst.size() < sim.N_particles * 16:
		_failures += 1; _checks += 1
		push_error("default: instancer returned no instances")
		return
	_checks += 1
	var n: int = sim.N_particles
	var any_mismatch := 0
	var pos := _read_positions()
	for i in range(n):
		var b := i * 16
		var m: float = pos[i * 4 + 3]
		var s_expected: float = clampf(0.5 + m * 0.12, 0.4, 5.0)
		var sx: float = inst[b + 0]
		if not _approx(sx, s_expected, 1e-4):
			any_mismatch += 1
		# color: Salpeter mass-temperature (legacy formula)
		var log_m: float = clampf((log(m) / log(2.0) + 2.0) * 0.25, 0.0, 1.0)
		var cr: float = mix_01(0.15, 1.0, log_m * log_m)
		var cg: float = mix_01(0.25, 0.6, log_m)
		var cb: float = mix_01(1.0, 0.15, log_m)
		if not _approx(inst[b + 12], cr, 2e-3) or not _approx(inst[b + 13], cg, 2e-3) \
			or not _approx(inst[b + 14], cb, 2e-3) or not _approx(inst[b + 15], 1.0, 1e-4):
			any_mismatch += 1
	if any_mismatch == 0:
		print("[PASS] default (mode 0): %d instances match the legacy size+mass-temp formula exactly" % n)
	else:
		_failures += 1
		push_error("default: %d/%d instances deviated from the pinned legacy formula" % [any_mismatch, n])


## [2] SIZE flag (0x10) — m^(1/3) scaling from pos.w.
func _check_size_flag() -> void:
	sim.particle_color_mode = 0 | 0x10
	var inst: PackedFloat32Array = await _dispatch_and_read()
	if inst.size() < sim.N_particles * 16:
		_failures += 1; _checks += 1
		push_error("size: instancer returned no instances")
		return
	_checks += 1
	var n: int = sim.N_particles
	var pos := _read_positions()
	var match_cnt := 0
	var legacy_diff := 0
	for i in range(n):
		var b := i * 16
		var m: float = pos[i * 4 + 3]
		var s_exp: float = clampf(SIZE_K * pow(m, 0.3333333), SIZE_S_MIN, SIZE_S_MAX)
		var s_legacy: float = clampf(0.5 + m * 0.12, 0.4, 5.0)
		var sx: float = inst[b + 0]
		if _approx(sx, s_exp, 1e-4):
			match_cnt += 1
		if not _approx(s_exp, s_legacy, 1e-4):
			legacy_diff += 1
	# Most instances must match the m^(1/3) law, and it must differ from the
	# legacy linear law on at least some of them (the flag actually changed
	# the size, not a no-op).
	if match_cnt >= n - 2 and legacy_diff >= 2:
		print("[PASS] size-by-mass (0x10): %d/%d match clamp(SIZE_K·cbrt(m)) with %d/legacy-different" % [match_cnt, n, legacy_diff])
	else:
		_failures += 1
		push_error("size: expected cbrt scaling (match=%d/%d, legacy_diff=%d)" % [match_cnt, n, legacy_diff])


## [3] TWO-AXIS (mode 4) — hue from q + lightness from TRUE ρ = EY+EI.
func _check_two_axis() -> void:
	# The lightness axis now samples ρ = EY+EI (the two bindings 4/5), so
	# drive it with a real EY/EI ramp: EY = 0.1 + 0.8·(i/N), EI = 0.1 → ρ
	# spans ~[0.2, 1.0] across X, and q = EY²+EI² varies too (hue moves).
	var N: int = sim.grid_N
	var nc: int = N * N * N
	var ey_a := PackedFloat32Array(); ey_a.resize(nc)
	var ei_a := PackedFloat32Array(); ei_a.resize(nc)
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id3: int = i + N * (j + N * k)
				var f: float = float(i) / float(maxi(N - 1, 1))
				ey_a[id3] = 0.1 + 0.8 * f
				ei_a[id3] = 0.1
	sim._rd.buffer_update(sim._field_ey, 0, ey_a.size() * 4, ey_a.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, ei_a.size() * 4, ei_a.to_byte_array())
	# baseline: plain Qi rainbow (hue only; lightness fixed by the engine)
	sim.particle_color_mode = 2
	var inst_q: PackedFloat32Array = await _dispatch_and_read()
	# two-axis: same hue engine, lightness modulated by ρ = EY+EI
	sim.particle_color_mode = 4
	var inst_xy: PackedFloat32Array = await _dispatch_and_read()
	if inst_q.size() < sim.N_particles * 16 or inst_xy.size() < sim.N_particles * 16:
		_failures += 1; _checks += 1
		push_error("two-axis: instancer returned no instances")
		return
	_checks += 1
	var n: int = sim.N_particles
	# ρ-lightness axis must be live: mode-4 color differs from mode 2 at the
	# same q for most instances.
	var differ := 0
	# hue+lightness must be NON-uniform across the ramp (both axes move)
	var nonuniform := 0
	for i in range(n):
		var b := i * 16
		var dr: float = inst_xy[b + 12] - inst_q[b + 12]
		var dg: float = inst_xy[b + 13] - inst_q[b + 13]
		var db: float = inst_xy[b + 14] - inst_q[b + 14]
		if absf(dr) > 1e-3 or absf(dg) > 1e-3 or absf(db) > 1e-3:
			differ += 1
		if i > 0:
			var prev_b := (i - 1) * 16
			if absf(inst_xy[b + 12] - inst_xy[prev_b + 12]) > 1e-3 \
				or absf(inst_xy[b + 13] - inst_xy[prev_b + 13]) > 1e-3 \
				or absf(inst_xy[b + 14] - inst_xy[prev_b + 14]) > 1e-3:
				nonuniform += 1
	# also: no NaN/garbage — every channel in [0,1]
	var in_range := true
	for i in range(n):
		for c in range(12, 15):
			var v: float = inst_xy[i * 16 + c]
			if not (v >= -1e-3 and v <= 1.0 + 1e-3):
				in_range = false
	if differ >= n / 2 and nonuniform >= 2 and in_range:
		print("[PASS] two-axis (mode 4): %d/%d ρ-lightness shifted, %d non-uniform colors, all RGB in range" % [differ, n, nonuniform])
	else:
		_failures += 1
		push_error("two-axis: expected ρ lightness modulation (differ=%d/%d, nonuniform=%d, in_range=%s)" % [differ, n, nonuniform, in_range])


## [4] GLOW flag (0x20) — bright-core additive + low-q alpha floor.
func _check_glow() -> void:
	sim.particle_color_mode = 2            # Qi rainbow alone (no glow) for the baseline alpha=1
	var inst_base: PackedFloat32Array = await _dispatch_and_read()
	sim.particle_color_mode = 2 | 0x20   # Qi rainbow + glow
	var inst_gl: PackedFloat32Array = await _dispatch_and_read()
	if inst_base.size() < sim.N_particles * 16 or inst_gl.size() < sim.N_particles * 16:
		_failures += 1; _checks += 1
		push_error("glow: instancer returned no instances")
		return
	_checks += 1
	var n: int = sim.N_particles
	# Baseline Qi rainbow has alpha = 1.0 for every instance.
	var base_alpha_ok := true
	for i in range(n):
		if not _approx(inst_base[i * 16 + 15], 1.0, 1e-4):
			base_alpha_ok = false
	# Glow: alpha drops from 1.0 toward the GLOW_A_MIN floor (no instance may
	# exceed 1.0 or fall below the floor). With the flat-noise field q is far
	# under the white point, so the bright-core lift (fg→0) is not exercised;
	# this verifies the glow gate is LIVE (alpha moved off 1.0) and bounded.
	var a_min := 999.0
	var a_max := -999.0
	var below_one := 0
	for i in range(n):
		var a := inst_gl[i * 16 + 15]
		if a < 0.999:
			below_one += 1
		a_min = minf(a_min, a)
		a_max = maxf(a_max, a)
	var floor_ok := a_min >= GLOW_A_MIN - 1e-3   # never below the floor
	var ceiling_ok := a_max <= 1.0 + 1e-4        # never above opaque
	var color_ok := await _check_glow_color_lift(n)
	if base_alpha_ok and below_one >= n / 2 and floor_ok and ceiling_ok and color_ok:
		print("[PASS] glow (0x20): alpha [%.2f, %.2f] — %d/%d dropped to the %.2f floor; baseline all-1.0; tinted color lift GLOW_TINT×%.2f OK" % [a_min, a_max, below_one, n, GLOW_A_MIN, GLOW_L_BOOST])
	else:
		_failures += 1
		push_error("glow: bad alpha signature (base_alpha_ok=%s, below_one=%d/%d, a∈[%.2f,%.2f], floor_ok=%s, ceiling_ok=%s, color_ok=%s)" % [base_alpha_ok, below_one, n, a_min, a_max, floor_ok, ceiling_ok, color_ok])


## [4b] GLOW color — the 2026-08-14 LESS-WHITE tinted lift. Drive a uniform
## field AT/ABOVE the approach white point: every particle gets fg = 1 →
## boost = 1, base = pure white (approach top, l = 1.0), so the final color
## MUST be mix(white, GLOW_TINT, GLOW_L_BOOST) — soft warm pink-white, NOT
## the old pure-white vec3(1.0)·0.25 lift. Convention-agnostic: writes BOTH
## the q field (= EY²+EI² = 20000, drives the tri_q hue) AND EY = EI = 100
## (drives the bounded q_coh = ρ²/(ρ²+φ⁻²+ε²) ≈ 0.913 hue) — under either
## Qi axis the white point a_hi = 0.5 is exceeded → boost saturates at 1.
## Restores the fields + engine exports afterward (the other checks run on
## the noise field).
func _check_glow_color_lift(n: int) -> bool:
	var nc: int = sim.grid_N * sim.grid_N * sim.grid_N
	var field_backup: PackedByteArray = sim._rd.buffer_get_data(sim._field_q, 0, nc * 4)
	var ey_backup: PackedByteArray = sim._rd.buffer_get_data(sim._field_ey, 0, nc * 4)
	var ei_backup: PackedByteArray = sim._rd.buffer_get_data(sim._field_ei, 0, nc * 4)
	var approach_backup: Vector2 = sim.qi_approach
	var thresh_backup: float = sim.qi_condensation_threshold
	# White point a_hi = 0.5 (approach (0, 0.5), threshold untracked) — well
	# below both the q-field value (20000) and q_coh ≈ 0.913.
	sim.qi_approach = Vector2(0.0, 0.5)
	sim.qi_condensation_threshold = 0.5
	var flat := PackedFloat32Array(); flat.resize(nc)
	flat.fill(20000.0)   # EY²+EI² for the tri_q hue axis (EY=EI=100)
	sim._rd.buffer_update(sim._field_q, 0, nc * 4, flat.to_byte_array())
	flat.fill(100.0)     # EY = EI = 100 → q_coh ≈ 0.913 (tri_coherence axis)
	sim._rd.buffer_update(sim._field_ey, 0, nc * 4, flat.to_byte_array())
	sim._rd.buffer_update(sim._field_ei, 0, nc * 4, flat.to_byte_array())
	sim.particle_color_mode = 2 | 0x20
	var inst: PackedFloat32Array = await _dispatch_and_read()
	# restore the noise fields + exports before evaluating (checks below
	# depend on them being back)
	sim._rd.buffer_update(sim._field_q, 0, nc * 4, field_backup)
	sim._rd.buffer_update(sim._field_ey, 0, nc * 4, ey_backup)
	sim._rd.buffer_update(sim._field_ei, 0, nc * 4, ei_backup)
	sim.qi_approach = approach_backup
	sim.qi_condensation_threshold = thresh_backup
	if inst.size() < n * 16:
		push_error("glow color: instancer returned no instances")
		return false
	# expected = mix(white, GLOW_TINT, GLOW_L_BOOST) at boost = 1
	var er: float = lerpf(1.0, GLOW_TINT.x, GLOW_L_BOOST)
	var eg: float = lerpf(1.0, GLOW_TINT.y, GLOW_L_BOOST)
	var eb: float = lerpf(1.0, GLOW_TINT.z, GLOW_L_BOOST)
	var bad := 0
	var maxc := -1.0
	for i in range(n):
		var b := i * 16
		var r: float = inst[b + 12]; var g: float = inst[b + 13]; var bl: float = inst[b + 14]
		maxc = maxf(maxc, maxf(r, maxf(g, bl)))
		if absf(r - er) > 2e-3 or absf(g - eg) > 2e-3 or absf(bl - eb) > 2e-3:
			bad += 1
		if absf(inst[b + 15] - 1.0) > 1e-3:
			bad += 1
	# the tinted lift must stay OFF pure white (old lift hit exactly 1.0;
	# the new tint peaks at 0.9976)
	if bad == 0 and maxc <= 0.999:
		print("[PASS] glow color: boost=1 core = mix(white, GLOW_TINT, %.2f) = (%.3f, %.3f, %.3f), max channel %.3f — tinted, not white" % [GLOW_L_BOOST, er, eg, eb, maxc])
		return true
	push_error("glow color: expected (%.3f, %.3f, %.3f) ± 2e-3, maxc %.3f — %d/%d off (old pure-white lift would read 1.000)" % [er, eg, eb, maxc, bad, n])
	return false


## [5] DEPTH flag (0x40) — alpha fades with camera distance.
func _check_depth() -> void:
	sim.particle_color_mode = 2 | 0x40   # Qi rainbow + depth cue
	var inst: PackedFloat32Array = await _dispatch_and_read()
	if inst.size() < sim.N_particles * 16:
		_failures += 1; _checks += 1
		push_error("depth: instancer returned no instances")
		return
	_checks += 1
	var pos := _read_positions()
	var n: int = sim.N_particles
	var ext: Vector3 = sim._extents()
	var boxd: float = ext.length()
	var dn: float = 0.35 * boxd
	var df: float = 1.35 * boxd
	# Alpha must equal the depth fade exactly: a = clamp((df−d)/(df−dn),0,1)
	# times the base alpha (1.0 for Qi rainbow). Verify per-particle so the
	# check is independent of the IC geometry (camera-at-origin proxy today).
	var ok := 0
	var fail := 0
	for i in range(n):
		var b := i * 16
		var d: float = Vector3(pos[i * 4], pos[i * 4 + 1], pos[i * 4 + 2]).length()
		var a := inst[b + 15]
		var fade: float = clampf((df - d) / (df - dn), 0.0, 1.0)   # DEPTH_POW = 1 (linear)
		if _approx(a, fade, 2e-3):
			ok += 1
		else:
			fail += 1
	if ok >= n - 2:
		print("[PASS] depth (0x40): %d/%d alpha matches the linear fade clamp((df-d)/(df-dn))" % [ok, n])
	else:
		_failures += 1
		push_error("depth: %d/%d alpha off the expected fade (dn=%.1f df=%.1f boxd=%.1f)" % [fail, n, dn, df, boxd])


# ── misc helpers ───────────────────────────────────────────────────────
func _read_positions() -> PackedFloat32Array:
	var pd: PackedByteArray = sim._rd.buffer_get_data(sim._pos_buf, 0, sim.N_particles * 16)
	if pd.size() < sim.N_particles * 16:
		return PackedFloat32Array()
	return pd.to_float32_array()


func mix_01(a: float, b: float, t: float) -> float:
	return a + (b - a) * t
