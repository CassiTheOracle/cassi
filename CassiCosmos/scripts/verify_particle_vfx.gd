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
##   [0] DECOUPLED INITIAL RENDER: once bootstrap records the first populated
##       instancer list, the MultiMesh becomes visible.

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
##   [6] FIELD-PHASE (mode 5): two EY/EI states with equal q_coh produce
##       distinct direct phase hues, matching the shader's intrinsic formula.
##   [7] VELOCITY-DIRECTION (mode 6): compass direction changes hue while
##       speed relative to the host v_ref changes non-saturated lightness.
##   [8] DECOUPLED ENVELOPE BOOT: before the engine's live position set is
##       bound, the tracker refuses to sample the dormant sim position buffer.
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
const PHI_INV2 := 0.3819660112501051  # shader coherence landmark (φ⁻²)
const PHI_VALUE := 1.618033988749895
const TAU := 6.283185307179586

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
	# The checks read vertex RGBA from the raw instance buffer. Force the
	# non-LUT MultiMesh format before reinit so the rebuilt instancer keeps
	# those colors instead of routing base modes through custom_data/LUT.
	sim.color_lut_mode = false
	sim.reinit()
	# reinit() queues the decoupled worker's CPU setup and returns before the
	# render-thread finish_setup() call. Let real frames drive that lifecycle;
	# playing is held only for this bounded boot window (no physics steps are
	# requested while _decoupled_boot_wait is true).
	sim.playing = true
	var boot_frames := 0
	var boot_timeout_frames := 1800  # 30 s at 60 fps; the engine has a 45 s guard
	var boot_ready := false
	var boot_waiting := true
	var worker_setup_done := false
	var gpu_setup_done := false
	while boot_frames < boot_timeout_frames:
		await get_tree().process_frame
		boot_frames += 1
		if not sim._decoupled_active or sim._physics_engine == null:
			push_error("verify_particle_vfx: decoupled engine fell back or vanished during boot")
			get_tree().quit(1)
			return
		var engine: Object = sim._physics_engine
		boot_waiting = bool(sim._decoupled_boot_wait)
		worker_setup_done = bool(engine.get("_setup_done"))
		gpu_setup_done = bool(engine.get("_setup_compute_done"))
		# _setup_compute_done is set only by the real deferred finish_setup().
		if not boot_waiting and worker_setup_done and gpu_setup_done and sim._shaders_ready:
			boot_ready = true
			break
	if not boot_ready:
		push_error("verify_particle_vfx: timeout waiting for decoupled finish_setup (frames=%d, boot_wait=%s, worker_setup=%s, gpu_setup=%s, shaders=%s)" % [
			boot_frames, boot_waiting, worker_setup_done, gpu_setup_done, sim._shaders_ready])
		get_tree().quit(1)
		return
	# The first populated instancer list must restore the MultiMesh before this
	# test pauses the sim. Remaining checks use manual repaint/readback.
	_check_decoupled_initial_visibility()
	_check_decoupled_envelope_boot_gate()
	sim.playing = false
	await get_tree().process_frame
	await get_tree().process_frame
	await _run_all()
	print("══════ RESULT: %d/%d checks passed, %d failed ══════" % [_checks - _failures, _checks, _failures])
	get_tree().quit(0 if _failures == 0 else 1)

func _check_decoupled_initial_visibility() -> void:
	_checks += 1
	if sim._mmi != null and is_instance_valid(sim._mmi) and sim._mmi.visible:
		print("[PASS] decoupled initial render: populated MultiMesh is visible")
		return
	_failures += 1
	push_error("decoupled initial render: MultiMesh remains hidden after bootstrap")

func _check_decoupled_envelope_boot_gate() -> void:
	_checks += 1
	var saved_boot_wait: bool = sim._decoupled_boot_wait
	var saved_dc_set: RID = sim._us_occ_0_dc
	sim._decoupled_boot_wait = true
	sim._us_occ_0_dc = RID()
	var captured_dormant_positions: bool = sim._capture_envelope_sample()
	sim._us_occ_0_dc = saved_dc_set
	sim._decoupled_boot_wait = saved_boot_wait
	if not captured_dormant_positions:
		print("[PASS] decoupled envelope boot: dormant sim positions rejected")
		return
	_failures += 1
	push_error("decoupled envelope boot: tracker sampled dormant sim positions")


# ── helpers ────────────────────────────────────────────────────────────
func _approx(a: float, b: float, tol: float) -> bool:
	return absf(a - b) <= tol
## The render uniform sets bind _pos_render_buf for binding 0 in both
## inline and decoupled modes. In decoupled mode the blend pass fills it
## from the engine's live _pos_buf; never fall back to the dormant sim
## particle buffer if the render snapshot is unavailable.
func _live_pos_rid() -> RID:
	if bool(sim._decoupled_active):
		var engine: Object = sim._physics_engine
		if engine == null or not engine._pos_buf.is_valid():
			push_error("verify_particle_vfx: decoupled live position source is invalid")
			return RID()
	return _checked_live_rid("render position", sim._pos_render_buf)


func _live_vel_rid() -> RID:
	if bool(sim._decoupled_active):
		var engine: Object = sim._physics_engine
		if engine == null:
			push_error("verify_particle_vfx: decoupled live velocity engine is missing")
			return RID()
		return _checked_live_rid("velocity", engine._vel_buf)
	return _checked_live_rid("velocity", sim._vel_buf)


func _live_ey_rid() -> RID:
	if bool(sim._decoupled_active):
		var engine: Object = sim._physics_engine
		if engine == null:
			push_error("verify_particle_vfx: decoupled live EY engine is missing")
			return RID()
		return _checked_live_rid("EY field", engine._field_ey)
	return _checked_live_rid("EY field", sim._field_ey)


func _live_ei_rid() -> RID:
	if bool(sim._decoupled_active):
		var engine: Object = sim._physics_engine
		if engine == null:
			push_error("verify_particle_vfx: decoupled live EI engine is missing")
			return RID()
		return _checked_live_rid("EI field", engine._field_ei)
	return _checked_live_rid("EI field", sim._field_ei)


func _live_q_rid() -> RID:
	if bool(sim._decoupled_active):
		var engine: Object = sim._physics_engine
		if engine == null:
			push_error("verify_particle_vfx: decoupled live Q engine is missing")
			return RID()
		return _checked_live_rid("Q field", engine._field_q)
	return _checked_live_rid("Q field", sim._field_q)


func _checked_live_rid(label: String, rid: RID) -> RID:
	if rid.is_valid():
		return rid
	push_error("verify_particle_vfx: live %s RID is invalid" % label)
	return RID()


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
	await _check_two_axis()   # writes EY/EI ramps; intrinsic modes run afterward
	await _check_field_phase()
	await _check_velocity_direction()


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
	if pos.size() < n * 4:
		_failures += 1
		push_error("default: live position readback unavailable")
		return
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
	if pos.size() < n * 4:
		_failures += 1
		push_error("size: live position readback unavailable")
		return
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
	var ey_rid: RID = _live_ey_rid()
	var ei_rid: RID = _live_ei_rid()
	if not ey_rid.is_valid() or not ei_rid.is_valid():
		_failures += 1; _checks += 1
		push_error("two-axis: live EY/EI field buffers unavailable")
		return
	var ey_a := PackedFloat32Array(); ey_a.resize(nc)
	var ei_a := PackedFloat32Array(); ei_a.resize(nc)
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id3: int = i + N * (j + N * k)
				var f: float = float(i) / float(maxi(N - 1, 1))
				ey_a[id3] = 0.1 + 0.8 * f
				ei_a[id3] = 0.1
	sim._rd.buffer_update(ey_rid, 0, ey_a.size() * 4, ey_a.to_byte_array())
	sim._rd.buffer_update(ei_rid, 0, ei_a.size() * 4, ei_a.to_byte_array())
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
## the old pure-white vec3(1.0)·0.25 lift. Mode 2 uses the bounded
## tri_coherence(EY,EI) axis, so this arm writes EY = EI = 100 directly
## (q_coh = ρ²/(ρ²+φ⁻²+ε²) ≈ 0.913); Q is intentionally not mutated
## because it is not consumed by this glow branch. The white point a_hi =
## 0.5 is exceeded → boost saturates at 1.
## Restores the fields + engine exports afterward (the other checks run on
## the noise field).
func _check_glow_color_lift(n: int) -> bool:
	var nc: int = sim.grid_N * sim.grid_N * sim.grid_N
	var ey_rid: RID = _live_ey_rid()
	var ei_rid: RID = _live_ei_rid()
	if not ey_rid.is_valid() or not ei_rid.is_valid():
		push_error("glow color: live EY/EI field buffers unavailable")
		return false
	var ey_backup: PackedByteArray = sim._rd.buffer_get_data(ey_rid, 0, nc * 4)
	var ei_backup: PackedByteArray = sim._rd.buffer_get_data(ei_rid, 0, nc * 4)
	var approach_backup: Vector2 = sim.qi_approach
	var thresh_backup: float = sim.qi_condensation_threshold
	var approach_tracks_backup: bool = bool(sim.qi_approach_tracks_threshold)
	# White point a_hi = 0.5 (approach (0, 0.5)) — well below the
	# tri_coherence(EY,EI) value from EY = EI = 100 (q_coh ≈ 0.913).
	sim.qi_approach = Vector2(0.0, 0.5)
	sim.qi_condensation_threshold = 0.5
	sim.qi_approach_tracks_threshold = true
	var flat := PackedFloat32Array(); flat.resize(nc)
	flat.fill(100.0)     # EY = EI = 100 → q_coh ≈ 0.913 (tri_coherence axis)
	sim._rd.buffer_update(ey_rid, 0, nc * 4, flat.to_byte_array())
	sim._rd.buffer_update(ei_rid, 0, nc * 4, flat.to_byte_array())
	# Read a compact, bounded sample from each exact live RID before dispatch.
	# This proves the control reached the buffers used by the shader rather
	# than relying on the intended writes when interpreting output failures.
	var ey_probe := _read_glow_field_samples(ey_rid, nc)
	var ei_probe := _read_glow_field_samples(ei_rid, nc)
	var control_ok := ey_probe.size() == 3 and ei_probe.size() == 3
	for i in range(mini(ey_probe.size(), 3)):
		if not _approx(ey_probe[i], 100.0, 1e-3):
			control_ok = false
	for i in range(mini(ei_probe.size(), 3)):
		if not _approx(ei_probe[i], 100.0, 1e-3):
			control_ok = false
	if not control_ok:
		# Restore every field/export changed above before this early return.
		sim._rd.buffer_update(ey_rid, 0, nc * 4, ey_backup)
		sim._rd.buffer_update(ei_rid, 0, nc * 4, ei_backup)
		sim.qi_approach = approach_backup
		sim.qi_condensation_threshold = thresh_backup
		sim.qi_approach_tracks_threshold = approach_tracks_backup
		push_error("glow color: live control readback failed before dispatch (EY=%s, EI=%s; expected EY=EI=100)" % [ey_probe, ei_probe])
		return false
	sim.particle_color_mode = 2 | 0x20
	var inst: PackedFloat32Array = await _dispatch_and_read()
	# restore the noise fields + exports before evaluating (checks below
	# depend on them being back)
	sim._rd.buffer_update(ey_rid, 0, nc * 4, ey_backup)
	sim._rd.buffer_update(ei_rid, 0, nc * 4, ei_backup)
	sim.qi_approach = approach_backup
	sim.qi_condensation_threshold = thresh_backup
	sim.qi_approach_tracks_threshold = approach_tracks_backup
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

func _read_glow_field_samples(rid: RID, nc: int) -> PackedFloat32Array:
	var samples := PackedFloat32Array()
	for index in [0, int(nc / 2), nc - 1]:
		var raw: PackedByteArray = sim._rd.buffer_get_data(rid, index * 4, 4)
		if raw.size() < 4:
			return samples
		var values: PackedFloat32Array = raw.to_float32_array()
		if values.is_empty():
			return samples
		samples.append(values[0])
	return samples


## [5] DEPTH flag (0x40) — alpha fades with camera distance.
func _check_depth() -> void:
	sim.particle_color_mode = 2 | 0x40   # Qi rainbow + depth cue
	var inst: PackedFloat32Array = await _dispatch_and_read()
	if inst.size() < sim.N_particles * 16:
		_failures += 1; _checks += 1
		push_error("depth: instancer returned no instances")
		return
	_checks += 1
	var n: int = sim.N_particles
	var ext: Vector3 = sim._extents()
	var boxd: float = ext.length()
	var dn: float = 0.35 * boxd
	var df: float = 1.35 * boxd
	# The shader applies depth to `pf`, the same position it writes into the
	# instance transform after selecting open-world or periodic rendering.
	# Read that emitted position rather than raw source position: escaped
	# particles are legitimately folded by the legacy path.
	var ok := 0
	var fail := 0
	for i in range(n):
		var b := i * 16
		var d: float = Vector3(inst[b + 3], inst[b + 7], inst[b + 11]).length()
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
## [6] FIELD-PHASE (mode 5) — direct θ hue and bounded q lightness.
## The two field states keep ρ and |ε| fixed while flipping ε, so q_coh
## (and therefore lightness) is fixed but atan(EI,EY) must rotate the hue.
## This deliberately bypasses the fitted scalar bands: base 5's shader branch
## consumes only EY/EI and the hue offset.
func _check_field_phase() -> void:
	var n: int = sim.N_particles
	var nc: int = sim.grid_N * sim.grid_N * sim.grid_N
	var pos := _read_positions()
	if pos.size() < n * 4:
		_failures += 1; _checks += 1
		push_error("field-phase: position readback unavailable")
		return
	var ey_rid: RID = _live_ey_rid()
	var ei_rid: RID = _live_ei_rid()
	if not ey_rid.is_valid() or not ei_rid.is_valid():
		_failures += 1; _checks += 1
		push_error("field-phase: live EY/EI field buffers unavailable")
		return
	var ey_backup: PackedByteArray = sim._rd.buffer_get_data(ey_rid, 0, nc * 4)
	var ei_backup: PackedByteArray = sim._rd.buffer_get_data(ei_rid, 0, nc * 4)
	var mode_backup: int = int(sim.particle_color_mode)
	# ρ = 1 and ε = ±0.25 give identical q_coh but distinct order-frame
	# phases. Solving EY+EI=ρ and EY−φ·EI=ε keeps both field states positive.
	var rho0: float = 1.0
	var eps0: float = 0.25
	var den: float = 1.0 + PHI_VALUE
	var ey_a_value: float = (PHI_VALUE * rho0 + eps0) / den
	var ei_a_value: float = (rho0 - eps0) / den
	var ey_b_value: float = (PHI_VALUE * rho0 - eps0) / den
	var ei_b_value: float = (rho0 + eps0) / den
	var ey_a := PackedFloat32Array(); ey_a.resize(nc); ey_a.fill(ey_a_value)
	var ei_a := PackedFloat32Array(); ei_a.resize(nc); ei_a.fill(ei_a_value)
	var ey_b := PackedFloat32Array(); ey_b.resize(nc); ey_b.fill(ey_b_value)
	var ei_b := PackedFloat32Array(); ei_b.resize(nc); ei_b.fill(ei_b_value)
	sim._rd.buffer_update(ey_rid, 0, nc * 4, ey_a.to_byte_array())
	sim._rd.buffer_update(ei_rid, 0, nc * 4, ei_a.to_byte_array())
	sim.particle_color_mode = 5
	# Bases 5/6 need the real color (not LUT custom_data) instance format.
	sim.refresh_lut_format()
	var inst_a: PackedFloat32Array = await _dispatch_and_read()
	sim._rd.buffer_update(ey_rid, 0, nc * 4, ey_b.to_byte_array())
	sim._rd.buffer_update(ei_rid, 0, nc * 4, ei_b.to_byte_array())
	var inst_b: PackedFloat32Array = await _dispatch_and_read()
	# Restore every mutated resource before evaluating or continuing.
	sim._rd.buffer_update(ey_rid, 0, nc * 4, ey_backup)
	sim._rd.buffer_update(ei_rid, 0, nc * 4, ei_backup)
	sim.particle_color_mode = mode_backup
	sim.refresh_lut_format()
	if inst_a.size() < n * 16 or inst_b.size() < n * 16:
		_failures += 1; _checks += 1
		push_error("field-phase: instancer returned no instances")
		return
	_checks += 1
	var q_coh: float = rho0 * rho0 / (rho0 * rho0 + PHI_INV2 + eps0 * eps0)
	var expected_l: float = 0.08 + 0.85 * q_coh
	var hue_offset: float = float(sim.color_hue_offset)
	var expected_a := _hsl_to_rgb(fposmod(atan2(ei_a_value, ey_a_value) / TAU + 0.5 + hue_offset, 1.0), 1.0, expected_l)
	var expected_b := _hsl_to_rgb(fposmod(atan2(ei_b_value, ey_b_value) / TAU + 0.5 + hue_offset, 1.0), 1.0, expected_l)
	var active := 0
	var bad := 0
	var changed := 0
	for i in range(n):
		if pos[i * 4 + 3] <= 0.0:
			continue
		active += 1
		var b := i * 16
		if absf(inst_a[b + 12] - expected_a.x) > 2e-3 \
			or absf(inst_a[b + 13] - expected_a.y) > 2e-3 \
			or absf(inst_a[b + 14] - expected_a.z) > 2e-3 \
			or absf(inst_b[b + 12] - expected_b.x) > 2e-3 \
			or absf(inst_b[b + 13] - expected_b.y) > 2e-3 \
			or absf(inst_b[b + 14] - expected_b.z) > 2e-3 \
			or absf(inst_a[b + 15] - 1.0) > 1e-3 \
			or absf(inst_b[b + 15] - 1.0) > 1e-3:
			bad += 1
		if absf(inst_a[b + 12] - inst_b[b + 12]) > 1e-3 \
			or absf(inst_a[b + 13] - inst_b[b + 13]) > 1e-3 \
			or absf(inst_a[b + 14] - inst_b[b + 14]) > 1e-3:
			changed += 1
	var changed_min := maxi(active - 2, 1)
	if active > 0 and bad == 0 and changed >= changed_min:
		print("[PASS] field-phase (mode 5): %d/%d active colors match direct atan(EI,EY)+q_coh; %d phase-dependent colors changed (bands bypassed)" % [active - bad, active, changed])
	else:
		_failures += 1
		push_error("field-phase: expected direct phase/q mapping (active=%d, bad=%d, changed=%d/%d)" % [active, bad, changed, active])


## [7] VELOCITY-DIRECTION (mode 6) — compass hue + soft speed lightness.
## Four deterministic velocity groups exercise direction at equal speed and
## lightness at fixed direction. The shader's current host v_ref is used
## unchanged; the test only replaces the velocity buffer contents.
func _check_velocity_direction() -> void:
	var n: int = sim.N_particles
	var pos := _read_positions()
	if pos.size() < n * 4:
		_failures += 1; _checks += 1
		push_error("velocity-direction: position readback unavailable")
		return
	var vel_rid: RID = _live_vel_rid()
	if not vel_rid.is_valid():
		_failures += 1; _checks += 1
		push_error("velocity-direction: live velocity buffer unavailable")
		return
	var vel_backup: PackedByteArray = sim._rd.buffer_get_data(vel_rid, 0, n * 16)
	var mode_backup: int = int(sim.particle_color_mode)
	var vref: float = maxf(float(sim._rainbow_vref), 1e-6)
	var vel_probe := PackedFloat32Array(); vel_probe.resize(n * 4)
	for i in range(n):
		var group: int = i % 4
		var v := Vector3.ZERO
		if group == 0:
			v = Vector3(0.25 * vref, 0.0, 0.0)
		elif group == 1:
			v = Vector3(2.0 * vref, 0.0, 0.0)
		elif group == 2:
			v = Vector3(0.0, vref, 0.0)
		else:
			v = Vector3(-vref, 0.0, 0.0)
		vel_probe[i * 4] = v.x
		vel_probe[i * 4 + 1] = v.y
		vel_probe[i * 4 + 2] = v.z
		vel_probe[i * 4 + 3] = 0.0
	sim._rd.buffer_update(vel_rid, 0, n * 16, vel_probe.to_byte_array())
	sim.particle_color_mode = 6
	sim.refresh_lut_format()
	var inst: PackedFloat32Array = await _dispatch_and_read()
	# Restore the live velocities and the prior mode/instance format.
	sim._rd.buffer_update(vel_rid, 0, n * 16, vel_backup)
	sim.particle_color_mode = mode_backup
	sim.refresh_lut_format()
	if inst.size() < n * 16:
		_failures += 1; _checks += 1
		push_error("velocity-direction: instancer returned no instances")
		return
	_checks += 1
	var hue_offset: float = float(sim.color_hue_offset)
	var bad := 0
	var active := 0
	var slow_l := -1.0
	var fast_l := -1.0
	var dir_y := Vector3.ZERO
	var dir_neg_x := Vector3.ZERO
	var have_dir_y := false
	var have_dir_neg_x := false
	for i in range(n):
		if pos[i * 4 + 3] <= 0.0:
			continue
		active += 1
		var group: int = i % 4
		var v := Vector3.ZERO
		if group == 0:
			v = Vector3(0.25 * vref, 0.0, 0.0)
		elif group == 1:
			v = Vector3(2.0 * vref, 0.0, 0.0)
		elif group == 2:
			v = Vector3(0.0, vref, 0.0)
		else:
			v = Vector3(-vref, 0.0, 0.0)
		var speed: float = v.length()
		var vn: float = speed / vref
		var expected_l: float = clampf(0.12 + 0.75 * (vn / (vn + 1.0)), 0.0, 1.0)
		var expected := _hsl_to_rgb(fposmod(atan2(v.y, v.x) / TAU + 0.5 + hue_offset, 1.0), 0.9, expected_l)
		var b := i * 16
		var observed := Vector3(inst[b + 12], inst[b + 13], inst[b + 14])
		if absf(observed.x - expected.x) > 2e-3 \
			or absf(observed.y - expected.y) > 2e-3 \
			or absf(observed.z - expected.z) > 2e-3 \
			or absf(inst[b + 15] - 1.0) > 1e-3:
			bad += 1
		var observed_l: float = _rgb_lightness(observed)
		if group == 0:
			slow_l = observed_l
		elif group == 1:
			fast_l = observed_l
		elif group == 2 and not have_dir_y:
			dir_y = observed
			have_dir_y = true
		elif group == 3 and not have_dir_neg_x:
			dir_neg_x = observed
			have_dir_neg_x = true
	var direction_delta: float = dir_y.distance_to(dir_neg_x) if have_dir_y and have_dir_neg_x else 0.0
	var speed_delta: float = fast_l - slow_l if slow_l >= 0.0 and fast_l >= 0.0 else 0.0
	# The 2·v_ref sample must remain below the white endpoint: this catches
	# legacy/fitted-band saturation as well as a direction-only no-op.
	var non_saturated := fast_l >= 0.0 and fast_l < 0.9
	if active > 0 and bad == 0 and direction_delta > 0.05 and speed_delta > 0.2 and non_saturated:
		print("[PASS] velocity-direction (mode 6): %d/%d active colors match atan(vy,vx)+soft |v|/v_ref (v_ref=%.4f), direction Δ=%.3f, lightness Δ=%.3f" % [active - bad, active, vref, direction_delta, speed_delta])
	else:
		_failures += 1
		push_error("velocity-direction: expected intrinsic compass/speed mapping (active=%d, bad=%d, direction_delta=%.3f, speed_delta=%.3f, fast_l=%.3f)" % [active, bad, direction_delta, speed_delta, fast_l])


func _hsl_to_rgb(h: float, s: float, l: float) -> Vector3:
	var r: float = clampf(absf(fposmod(h * 6.0 + 0.0, 6.0) - 3.0) - 1.0, 0.0, 1.0)
	var g: float = clampf(absf(fposmod(h * 6.0 + 4.0, 6.0) - 3.0) - 1.0, 0.0, 1.0)
	var b: float = clampf(absf(fposmod(h * 6.0 + 2.0, 6.0) - 3.0) - 1.0, 0.0, 1.0)
	var f: float = 1.0 - absf(2.0 * l - 1.0)
	return Vector3(l + s * (r - 0.5) * f, l + s * (g - 0.5) * f, l + s * (b - 0.5) * f)


func _rgb_lightness(c: Vector3) -> float:
	var hi: float = maxf(c.x, maxf(c.y, c.z))
	var lo: float = minf(c.x, minf(c.y, c.z))
	return 0.5 * (hi + lo)




# ── misc helpers ───────────────────────────────────────────────────────
func _read_positions() -> PackedFloat32Array:
	var pos_rid: RID = _live_pos_rid()
	if not pos_rid.is_valid():
		return PackedFloat32Array()
	var pd: PackedByteArray = sim._rd.buffer_get_data(pos_rid, 0, sim.N_particles * 16)
	if pd.size() < sim.N_particles * 16:
		push_error("verify_particle_vfx: live position readback is short")
		return PackedFloat32Array()
	return pd.to_float32_array()


func mix_01(a: float, b: float, t: float) -> float:
	return a + (b - a) * t
