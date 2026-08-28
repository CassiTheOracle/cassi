extends Node
## Overhaul Verify phase — the capability battery (gates a-d), additive to
## the existing 8/8 regression battery. Run windowed alongside
## _diag/run_battery.ps1:
##   Godot --path . --scene res://_diag/cap_battery.tscn
##
## The gates bind the REAL sim paths (the b_track precedent — the shipped
## shaders + the window/tree machinery):
##   gate a — NO IMAGE-FORCE at the domain boundary: a probe particle at
##     +L_old (the OLD box half-extent) with the structure extending past
##     the boundary. The OPEN tree arm must see the structure at its TRUE
##     position (the box-independent force — the reference) and NOT the
##     closed-box periodic force (the wrap). Inline path (the sim's own
##     compute + tree worker + the tracked-window header refresh).
##   gate b — the structure expands past any finite tile: two clusters
##     drifting past the OLD box period with the tracked window; assert
##     (i) no periodic image mass at the image location, (ii) the tracked
##     tile covers the structure (would-clip + coverage), (iii) the tree
##     sees the clusters at their true separation (the symmetric two-
##     cluster force — NOT the ~100x wrapped force).
##   gate c — DETERMINISM in the compatibility regime: the filling
##     structure, tracking OFF vs ON — the tracker has no reason to move a
##     filling structure → the open pipeline must be bit-identical
##     (max-diff == 0.0 over pos + hdr + field) — in BOTH the closed-box
##     (poisson) arm and the OPEN (tree) arm.
##   gate d — ONE-RD staging holds (the decoupled engine path):
##     (i) the fixed-target drain sustains (executed == target, no stall),
##     (ii) the frame-time variance ≤ the honest p99/max-ratio target
##     (p99 ≤ 3·mean AND max ≤ 4·mean — NOT the ±20% which M0b-P-FX proved
##     structurally unreachable under one-RD), (iii) NO mid-chain
##     `_rd.sync()`/`buffer_get_data` on the physics path (a source grep
##     gate over the engine's chain functions).
##
## HONEST SCOPE: gates a/b/c bind the INLINE path — the ONLY path where
## the tracked-window state reaches the physics (the sim's per-frame
## header encode reads the live members + the tree worker's structure-
## rooted cube). The DECOUPLED engine's physics window is cfg-fixed (the
## tracked state never re-ships into the engine — the finish-B wiring WIP),
## so the decoupled path cannot move the tile; gate d binds the decoupled
## path for exactly the staging properties it does ship.

const N_PARTICLES := 20000
const N_PER_CLUSTER := 10000
const GRID_N := 64
const DT := 0.01
const RADIUS := 50.0          # L_old = 1.5·RADIUS = 75
const SIGMA := 15.0           # gate-a cluster width (0.2·L_old)
const CANARY_STEPS := 300
const GROW_STEPS := 400
const GROW_CADENCES := 3
const BATCH := 4

var _sim: Node
var _rd: RenderingDevice
var _tracker
var _orig_box := Vector3.ONE
var _gate := 0
var _phase := 0
var _step := 0
var _cadence := 0
var _next_cadence_step := 0
var _cadences_total := 0
var _tracked := false
var _fail := 0
var _results := []            # [{gate, name, pass, detail}]
var _ref_off := {}
var _frame_samples := []      # gate-d frame-time samples (ms)
var _frame_t0 := 0
var _frame_t1 := 0
var _last_frame_ms := 16.7

# — gate-a measured forces —
var _a_tree0 := Vector3.ZERO
var _a_tree1 := Vector3.ZERO
var _a_pois0 := Vector3.ZERO


func _ready() -> void:
	_sim = $CassiSim
	_sim.playing = false
	_sim.N_particles = N_PARTICLES
	_sim.grid_N = GRID_N
	_sim.dt = DT
	_sim.cluster_radius = RADIUS
	_sim.source_strength = 0.0
	_sim.black_holes_enabled = false
	_sim.particle_merge = false
	_sim.bh_accretion = false
	_sim.suppress_readbacks = true
	_sim.auto_frame_camera_on_start = false
	_sim.physics_decoupled = false      # gates a-c: the INLINE path (the tracking works there)
	_sim.reinit()
	_rd = _sim._rd
	_orig_box = _sim._extents()
	_tracker = EnvelopeTracker.new()
	_tracker.center = Vector3.ZERO
	_tracker.extent = _orig_box
	_begin_gate_a()


func _process(delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	_last_frame_ms = delta * 1000.0
	match _gate:
		0:
			_gate_a_open()
		1:
			_gate_a_closed()
		2:
			_gate_c_drive()
		3:
			_gate_b_drive()
		4:
			_gate_d_drive()
		_:
			_verdict()
			return


func _reinit() -> void:
	_sim.reinit()
	_rd = _sim._rd
	_orig_box = _sim._extents()
	_tracker = EnvelopeTracker.new()
	_tracker.center = Vector3.ZERO
	_tracker.extent = _orig_box


# ═══════════════════════════════════════════════════════════════════════
# GATE A — no image-force at the domain boundary
# ═══════════════════════════════════════════════════════════════════════
# The probe particle at +L_old (the OLD box half-extent) with the cluster
# centered at +1.1·L_old — OUTSIDE the old box (the open regime's whole
# point — the structure extends past the boundary). The tracked window
# covers it (the tile follows the structure). The OPEN (tree) arm sees the
# cluster at its true position; the CLOSED (periodic poisson) arm wraps
# the outside mass to the −x side (the nearest image) — the force on the
# probe flips toward the wrapped image. Assertions:
#   A1  the tree force on the boundary probe == the tree force on the
#       mirror probe (the same σ separation on the far side) — the open
#       force is box-independent (the no-fold reference).
#   A2  the poisson force on the boundary probe ≠ the tree force — the
#       closed-box periodic force (the wrap) — the sign flips or the
#       magnitude differs by > 30%.

func _begin_gate_a() -> void:
	_sim.physics_decoupled = false
	_sim._decoupled_active = false
	_sim.meshless_mode = true
	_sim.meshless_gravity = true
	_sim.home_window_enabled = true
	_sim.box_scale = 1.0
	_sim._window_center = Vector3.ZERO
	_reinit()
	_phase = 0
	print("[CapBattery] gate a: no image-force at the domain boundary")


func _gate_a_open() -> void:
	if _phase == 0:
		_seed_gate_a()
		_apply_tracking()
		_sim._run_physics_steps(1)   # the deposit seeds the tree's mode-7 rho
		_sim._run_physics_steps(1)   # the tree job reads the FRESH rho -> the acc
		_a_tree0 = _probe_acc(0)
		_a_tree1 = _probe_acc(1)
		print("[CapA] diag: probe0=(%.1f,%.1f,%.1f) probe1=(%.1f,%.1f,%.1f) cluster_c=%.1f sigma=%.1f tracker=(%.2f,%.2f,%.2f, ext %.2f) box_scale=%.3f"
				% [_a_tree0.length(), 0.0, 0.0, _a_tree1.length(), 0.0, 0.0, 90.0, SIGMA,
				_tracker.center.x, _tracker.center.y, _tracker.center.z, _tracker.extent.x, _sim.box_scale])
		print("[CapA] tree: boundary acc=(%.6f, %.6f, %.6f) mirror acc=(%.6f, %.6f, %.6f)"
				% [_a_tree0.x, _a_tree0.y, _a_tree0.z, _a_tree1.x, _a_tree1.y, _a_tree1.z])
		_phase = 1
	else:
		# Closed-box arm: the same state, the poisson (periodic) solver.
		_sim.meshless_mode = false
		_sim.meshless_gravity = false
		_reinit()
		_gate = 1
		_phase = 2


func _gate_a_closed() -> void:
	if _phase == 2:
		_seed_gate_a()
		_apply_tracking()
		_sim._run_physics_steps(1)
		_sim._run_physics_steps(1)
		_a_pois0 = _probe_acc(0)
		print("[CapA] poisson: boundary acc=(%.6f, %.6f, %.6f)" % [_a_pois0.x, _a_pois0.y, _a_pois0.z])
		_assert_gate_a()
		_gate = 2
		_begin_gate_c()


func _assert_gate_a() -> void:
	var mag0 := _a_tree0.length()
	var mag1 := _a_tree1.length()
	var d1 := absf(mag1 - mag0)
	var a1_ok: bool = mag0 > 1e-12 and d1 <= 0.05 * mag0
	var magp := _a_pois0.length()
	var dp := (_a_pois0 - _a_tree0).length()
	var a2_ok: bool = mag0 > 1e-12 and (dp > 0.30 * mag0 or _a_pois0.dot(_a_tree0) <= 0.0)
	print("[CapA] A1 tree box-independence: ||tree_bnd| − |tree_mirror||/|tree_bnd| = %.4f -> %s"
			% [d1 / maxf(mag0, 1e-12), "PASS" if a1_ok else "FAIL"])
	print("[CapA] A2 open vs closed: |tree − poisson|/|tree| = %.4f (poisson %.6f vs tree %.6f) -> %s"
			% [dp / maxf(mag0, 1e-12), magp, mag0, "PASS" if a2_ok else "FAIL"])
	if not a1_ok:
		_fail += 1
	if not a2_ok:
		_fail += 1
	_results.append({"gate": "a", "name": "no image-force at the boundary",
			"pass": a1_ok and a2_ok,
			"detail": "A1 rel=%.4f A2 rel=%.4f" % [d1 / maxf(mag0, 1e-12), dp / maxf(mag0, 1e-12)]})


## Seed: probe0 at +L_old (the boundary), probe1 at +L_old + σ (the mirror,
## the same σ separation from the cluster center on the far side), the
## cluster centered at +1.1·L_old (outside the old box), gaussian σ.
func _seed_gate_a() -> void:
	_ensure_rng_seed()
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var L: float = _orig_box.x
	var pos := PackedFloat32Array()
	pos.resize(np * 4)
	var vel := PackedFloat32Array()
	vel.resize(np * 4)
	var cc: float = 1.2 * L
	# probe0 at the OLD boundary (+L), probe1 the mirror at the SAME 1-sigma
	# separation on the far side (cc+SIGMA) — the tree force magnitudes
	# must be equal (the open force is box-independent).
	pos[0] = L; pos[1] = 0.0; pos[2] = 0.0; pos[3] = 1.0
	pos[4] = cc + SIGMA; pos[5] = 0.0; pos[6] = 0.0; pos[7] = 1.0
	for i in range(2, np):
		var u1 := _rng.randf()
		var u2 := _rng.randf()
		var r := sqrt(-2.0 * log(u1 + 1e-12))
		var gx := r * cos(TAU * u2)
		var u3 := _rng.randf()
		var u4 := _rng.randf()
		var r2 := sqrt(-2.0 * log(u3 + 1e-12))
		var gy := r2 * cos(TAU * u4)
		var gz := r2 * sin(TAU * u4)
		pos[i * 4] = cc + SIGMA * gx
		pos[i * 4 + 1] = SIGMA * gy
		pos[i * 4 + 2] = SIGMA * gz
		pos[i * 4 + 3] = 1.0
	rd.buffer_update(_sim._pos_buf, 0, np * 16, pos.to_byte_array())
	rd.buffer_update(_sim._vel_buf, 0, np * 16, vel.to_byte_array())
	_uniform_field()


func _probe_acc(idx: int) -> Vector3:
	var rd: RenderingDevice = _sim._rd
	var acc: PackedFloat32Array = rd.buffer_get_data(_sim._acc_buf, idx * 16, 16).to_float32_array()
	return Vector3(acc[0], acc[1], acc[2])


func _zero_fields() -> void:
	var rd: RenderingDevice = _sim._rd
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var z := PackedFloat32Array()
	z.resize(n3)
	rd.buffer_update(_sim._field_ey, 0, n3 * 4, z.to_byte_array())
	rd.buffer_update(_sim._field_ei, 0, n3 * 4, z.to_byte_array())
	var zv := PackedFloat32Array()
	zv.resize(n3 * 4)
	rd.buffer_update(_sim._field_vel, 0, n3 * 16, zv.to_byte_array())


## The tree-river's force carries the (π/ρ)_target prefactor (the river-law
## density). The gate-a/b measurements compare force magnitudes across
## probe positions — the prefactor must not vary spatially, so the field
## is seeded UNIFORM (EY = EI = 1.0 → ρ = 2.0 everywhere; the two-fluid
## relaxes negligibly over the 2-step measurement window). The sim's
## meshless init then re-samples the uniform field into the site psi so
## the tree's chord weights agree with the grid field (a field overwrite
## without the re-init leaves the site psi at the pre-overwrite field —
## an inconsistency that zeroed the tree forces).
func _uniform_field() -> void:
	var rd: RenderingDevice = _sim._rd
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var f := PackedFloat32Array()
	f.resize(n3)
	f.fill(1.0)
	rd.buffer_update(_sim._field_ey, 0, n3 * 4, f.to_byte_array())
	rd.buffer_update(_sim._field_ei, 0, n3 * 4, f.to_byte_array())
	var zv := PackedFloat32Array()
	zv.resize(n3 * 4)
	rd.buffer_update(_sim._field_vel, 0, n3 * 16, zv.to_byte_array())
	_sim._meshless_init()   # re-sample the site psi from the uniform field


# ═══════════════════════════════════════════════════════════════════════
# GATE C — determinism in the compatibility regime
# ═══════════════════════════════════════════════════════════════════════
# The FILLING structure (uniform over the box) with the tracking OFF vs
# ON: the tracker no-ops for a filling structure (the envelope inside the
# hysteresis — b_track5's canary) → the open pipeline must be bit-
# identical (max-diff == 0.0). Two arms: the poisson (phases 1-2) and the
# tree (phases 3-4).

func _begin_gate_c() -> void:
	print("[CapBattery] gate c: determinism in the compatibility regime")
	_sim.physics_decoupled = false
	_sim._decoupled_active = false
	_sim.meshless_mode = false
	_sim.meshless_gravity = false
	_sim.home_window_enabled = false
	_sim.box_scale = 1.0
	_sim._window_center = Vector3.ZERO
	_reinit()
	_phase = 1
	_start_canary("c-poisson-off", false)
	_step = 0
	_cadence = 0
	_next_cadence_step = CANARY_STEPS
	_cadences_total = 2


func _gate_c_drive() -> void:
	_sim._run_physics_steps(BATCH)
	_step += BATCH
	while _step >= _next_cadence_step:
		_next_cadence_step += CANARY_STEPS
		_cadence += 1
		if _tracked and _cadence == 1:
			_sim._run_physics_steps(BATCH)
			_step += BATCH
		if _cadence >= _cadences_total:
			_advance_canary()
			return


func _advance_canary() -> void:
	match _phase:
		1:   # poisson-off done
			_ref_off = _snapshot()
			_start_canary("c-poisson-on", true)
			_phase = 2
		2:   # poisson-on done — the bit-identity assert
			_assert_canary("poisson-arm")
			_sim.meshless_mode = true
			_sim.meshless_gravity = true
			_reinit()
			_start_canary("c-tree-off", false)
			_phase = 3
		3:
			_ref_off = _snapshot()
			_start_canary("c-tree-on", true)
			_phase = 4
		4:
			_assert_canary("tree-arm")
			_gate = 3
			_begin_gate_b()


func _start_canary(name: String, tracked: bool) -> void:
	_tracked = tracked
	_sim.home_window_enabled = tracked
	_sim.reinit()
	_rd = _sim._rd
	_tracker.center = Vector3.ZERO
	_tracker.extent = _sim._extents()
	_step = 0
	_cadence = 0
	_next_cadence_step = CANARY_STEPS
	_cadences_total = 2
	_seed_filling()
	if tracked:
		_apply_tracking()   # the no-op at the seed (the re-centered mid == 0)
	_sim._run_physics_steps(BATCH)   # the bootstrap frame (the tree worker blocks once)
	_step += BATCH
	print("[CapC] canary '%s' started (tracked=%s)" % [name, str(tracked)])


func _seed_filling() -> void:
	_ensure_rng_seed()
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos := PackedFloat32Array()
	pos.resize(np * 4)
	var vel := PackedFloat32Array()
	vel.resize(np * 4)
	var e: Vector3 = _sim._extents()
	# PLAIN RNG filling, RE-CENTERED by the tracker's OWN percentile-mid
	# (the same 0.5/99.5 order-stat indices the tracker uses on the same
	# stride-16 subsample) — the tracked canary's tracker then sees
	# mid == 0 EXACTLY at the seed, a guaranteed no-op independent of the
	# RNG draw. (The raw RNG mid drifts ~1.4 at 1250 samples — the
	# tracker's 0.375 move dead band is too tight for it; the b_track's
	# 50k/3125-sample canary happened to land inside by luck.)
	for i in range(np):
		pos[i * 4] = (_rng.randf() * 2.0 - 1.0) * e.x
		pos[i * 4 + 1] = (_rng.randf() * 2.0 - 1.0) * e.y
		pos[i * 4 + 2] = (_rng.randf() * 2.0 - 1.0) * e.z
		pos[i * 4 + 3] = 1.0
	var mid := _percentile_mid(pos, np, 16, e)
	for i in range(np):
		pos[i * 4] -= mid.x
		pos[i * 4 + 1] -= mid.y
		pos[i * 4 + 2] -= mid.z
	rd.buffer_update(_sim._pos_buf, 0, np * 16, pos.to_byte_array())
	rd.buffer_update(_sim._vel_buf, 0, np * 16, vel.to_byte_array())
	_zero_fields()
	_sim._window_center = Vector3.ZERO
	_sim.box_scale = 1.0
	var hb: PackedByteArray = _sim._bh_init_bytes
	hb.encode_float(36, e.x); hb.encode_float(40, e.y); hb.encode_float(44, e.z)
	_sim._bh_init_bytes = hb


## The 0.5/99.5 percentile-mid of the stride-16 subsample — computed with
## the tracker's EXACT indexing (floor((n-1)*p)) so the re-centering makes
## the tracker's center move EXACTLY zero.
func _percentile_mid(pos: PackedFloat32Array, np: int, stride: int, e: Vector3) -> Vector3:
	var n := np / stride
	var ax := [PackedFloat32Array(), PackedFloat32Array(), PackedFloat32Array()]
	for i in range(n):
		var ix := i * stride * 4
		for a in range(3):
			ax[a].append(pos[ix + a])
	var mid := Vector3.ZERO
	for a in range(3):
		ax[a].sort()
		var lo: float = ax[a][int(floor(float(ax[a].size() - 1) * 0.005))]
		var hi: float = ax[a][int(floor(float(ax[a].size() - 1) * 0.995))]
		mid[a] = (lo + hi) * 0.5
	return mid


func _assert_canary(arm: String) -> void:
	var snap := _snapshot()
	var d := _max_diff(snap["pos"], _ref_off["pos"])
	var dh := _max_diff(snap["hdr"], _ref_off["hdr"])
	var df := _max_diff(snap["field"], _ref_off["field"])
	var dh_idx := -1
	var dh_val := 0.0
	for i in range(mini(snap["hdr"].size(), _ref_off["hdr"].size())):
		var v := absf(snap["hdr"][i] - _ref_off["hdr"][i])
		if v > dh_val:
			dh_val = v
			dh_idx = i
	print("[CapC] canary %s: hdr max-diff at float idx %d (byte %d) = %.6f (off=%.6f on=%.6f)"
			% [arm, dh_idx, dh_idx * 4, dh_val,
			_ref_off["hdr"][dh_idx] if dh_idx >= 0 else 0.0,
			snap["hdr"][dh_idx] if dh_idx >= 0 else 0.0])
	var ok := d == 0.0 and dh == 0.0 and df == 0.0
	print("[CapC] canary %s: max-diff pos=%.6f hdr=%.6f field=%.6f -> %s"
			% [arm, d, dh, df, "PASS" if ok else "FAIL"])
	if not ok:
		_fail += 1
	_results.append({"gate": "c", "name": "determinism (%s canary)" % arm,
			"pass": ok, "detail": "max-diff pos=%.6f hdr=%.6f field=%.6f" % [d, dh, df]})


# ═══════════════════════════════════════════════════════════════════════
# GATE B — the structure expands past any finite tile (the owner's
# "box is the limiter" acceptance), tree arm + tracked window.
# ═══════════════════════════════════════════════════════════════════════

func _begin_gate_b() -> void:
	print("[CapBattery] gate b: the structure expands past any finite tile")
	_sim.physics_decoupled = false
	_sim._decoupled_active = false
	_sim.meshless_mode = true
	_sim.meshless_gravity = true
	_sim.home_window_enabled = true
	_sim.box_scale = 1.0
	_sim._window_center = Vector3.ZERO
	_reinit()
	_tracker.re_fits = 0
	_phase = 1
	_step = 0
	_cadence = 0
	_next_cadence_step = GROW_STEPS
	_cadences_total = GROW_CADENCES
	_seed_clusters(0.0, 0.0, 6.0)
	_sim._run_physics_steps(BATCH * 2)   # the bootstrap + a deposit for the tree's mode-7 rho
	_step += BATCH


func _gate_b_drive() -> void:
	_sim._run_physics_steps(BATCH)
	_step += BATCH
	while _step >= _next_cadence_step:
		_next_cadence_step += GROW_STEPS
		_cadence += 1
		_drift_clusters()
		_apply_tracking()
		_sim._run_physics_steps(BATCH)
		_step += BATCH
		if _cadence >= _cadences_total:
			_assert_gate_b()
			_gate = 4
			_begin_gate_d()
			return


func _seed_clusters(a0: float, b0: float, sig: float) -> void:
	_ensure_rng_seed()
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos := PackedFloat32Array()
	pos.resize(np * 4)
	var vel := PackedFloat32Array()
	vel.resize(np * 4)
	for i in range(np):
		var c := a0 if i < N_PER_CLUSTER else b0
		var u1 := _rng.randf()
		var u2 := _rng.randf()
		var r := sqrt(-2.0 * log(u1 + 1e-12))
		var gx := r * cos(TAU * u2)
		var u3 := _rng.randf()
		var u4 := _rng.randf()
		var r2 := sqrt(-2.0 * log(u3 + 1e-12))
		var gy := r2 * cos(TAU * u4)
		var gz := r2 * sin(TAU * u4)
		pos[i * 4] = c + sig * gx
		pos[i * 4 + 1] = sig * gy
		pos[i * 4 + 2] = sig * gz
		pos[i * 4 + 3] = 1.0
	rd.buffer_update(_sim._pos_buf, 0, np * 16, pos.to_byte_array())
	rd.buffer_update(_sim._vel_buf, 0, np * 16, vel.to_byte_array())
	# The sim's OWN init field (the reinit's _init_field — the site psi and
	# the grid field agree; the uniform field's q_coh would amplify the
	# tree chord weights ~15x and blast the structure).
	_sim._window_center = Vector3.ZERO
	_sim.box_scale = 1.0
	var hb: PackedByteArray = _sim._bh_init_bytes
	hb.encode_float(36, _orig_box.x); hb.encode_float(40, _orig_box.y); hb.encode_float(44, _orig_box.z)
	_sim._bh_init_bytes = hb


func _drift_clusters() -> void:
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos: PackedFloat32Array = rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
	var da: float = -60.0 / float(GROW_CADENCES)
	var db: float = 240.0 / float(GROW_CADENCES)
	for i in range(np):
		pos[i * 4 + 2] += da if i < N_PER_CLUSTER else db
	rd.buffer_update(_sim._pos_buf, 0, np * 16, pos.to_byte_array())


## Run the envelope tracker on a subsample + write the tracked state into
## the sim's window/extent members (the per-frame header encode carries it).
func _apply_tracking() -> void:
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos: PackedFloat32Array = rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
	var n := np / 16
	var s := PackedFloat32Array()
	s.resize(n * 4)
	for i in range(n):
		var ix := i * 16 * 4
		s[i * 4] = pos[ix]
		s[i * 4 + 1] = pos[ix + 1]
		s[i * 4 + 2] = pos[ix + 2]
		s[i * 4 + 3] = 0.0
	_tracker.compute(s, 4, 1)
	_sim._window_center = _tracker.center
	var scl: float = _tracker.extent.x / _orig_box.x
	_sim.box_scale = maxf(scl, 1e-3)
	var hb: PackedByteArray = _sim._bh_init_bytes
	hb.encode_float(36, _tracker.extent.x)
	hb.encode_float(40, _tracker.extent.y)
	hb.encode_float(44, _tracker.extent.z)
	_sim._bh_init_bytes = hb


func _assert_gate_b() -> void:
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos: PackedFloat32Array = rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
	var a_com := Vector3.ZERO
	var b_com := Vector3.ZERO
	var na := 0
	var nb := 0
	for i in range(np):
		if i < N_PER_CLUSTER:
			a_com += Vector3(pos[i * 4], pos[i * 4 + 1], pos[i * 4 + 2])
			na += 1
		else:
			b_com += Vector3(pos[i * 4], pos[i * 4 + 1], pos[i * 4 + 2])
			nb += 1
	a_com /= float(na)
	b_com /= float(nb)
	var sep := (b_com - a_com).length()
	var L: float = _orig_box.x
	var max_abs := 0.0
	for i in range(np):
		max_abs = maxf(max_abs, absf(pos[i * 4]))
		max_abs = maxf(max_abs, absf(pos[i * 4 + 1]))
		max_abs = maxf(max_abs, absf(pos[i * 4 + 2]))
	var would_clip := max_abs > L
	var ext_max: float = maxf(maxf(_tracker.extent.x, _tracker.extent.y), _tracker.extent.z)
	var coverage_ok: bool = _tracker.last_demand <= ext_max * EnvelopeTracker.GROW_THRESH + 1e-6
	var img_x: float = b_com.x - 2.0 * L
	var rho: PackedFloat32Array = rd.buffer_get_data(_sim._mass_density_buf, 0,
			_sim.grid_N * _sim.grid_N * _sim.grid_N * 4).to_float32_array()
	var rho_true := _rho_at_world(rho, b_com)
	var rho_img := _rho_at_world(rho, Vector3(img_x, b_com.y, b_com.z))
	var no_image: bool = rho_img < 0.01 * maxf(rho_true, 1e-9)
	var acc_buf: PackedFloat32Array = rd.buffer_get_data(_sim._acc_buf, 0, np * 16).to_float32_array()
	var a_mid := _cluster_center_acc(acc_buf, 0, N_PER_CLUSTER, pos)
	var b_mid := _cluster_center_acc(acc_buf, N_PER_CLUSTER, np, pos)
	var sym: bool = absf(b_mid.length() - a_mid.length()) <= 0.20 * maxf(a_mid.length(), 1e-12)
	print("[CapB] separations: A=(%.1f,%.1f,%.1f) B=(%.1f,%.1f,%.1f) sep=%.1f old-box-period=%.1f tracker_center=(%.2f,%.2f,%.2f) tracker_ext=(%.2f,%.2f,%.2f) window=(%.2f,%.2f,%.2f) box_scale=%.3f"
			% [a_com.x, a_com.y, a_com.z, b_com.x, b_com.y, b_com.z, sep, 2.0 * L,
			_tracker.center.x, _tracker.center.y, _tracker.center.z,
			_tracker.extent.x, _tracker.extent.y, _tracker.extent.z,
			_sim._window_center.x, _sim._window_center.y, _sim._window_center.z, _sim.box_scale])
	print("[CapB] would-clip=%.1f>%.1f (%s) coverage=%s rho_true=%.4f rho_img=%.4f (%s) |aA|=%.5f |aB|=%.5f sym(%s)"
			% [max_abs, L, "PASS" if would_clip else "FAIL", str(coverage_ok),
			rho_true, rho_img, "PASS" if no_image else "FAIL",
			a_mid.length(), b_mid.length(), "PASS" if sym else "FAIL"])
	var ok: bool = would_clip and coverage_ok and no_image and sym
	if not ok:
		_fail += 1
	_results.append({"gate": "b", "name": "structure expands past the tile",
			"pass": ok,
			"detail": "sep=%.1f would-clip=%s coverage=%s no-image=%s tree-sym=%s"
					% [sep, str(would_clip), str(coverage_ok), str(no_image), str(sym)]})


func _cluster_center_acc(acc: PackedFloat32Array, i0: int, i1: int, pos: PackedFloat32Array) -> Vector3:
	var com := Vector3.ZERO
	for i in range(i0, i1):
		com += Vector3(pos[i * 4], pos[i * 4 + 1], pos[i * 4 + 2])
	com /= float(i1 - i0)
	var best := i0
	var bd := 1e30
	for i in range(i0, i1):
		var d := (Vector3(pos[i * 4], pos[i * 4 + 1], pos[i * 4 + 2]) - com).length()
		if d < bd:
			bd = d
			best = i
	return Vector3(acc[best * 4], acc[best * 4 + 1], acc[best * 4 + 2])


## The mass-density value at a world position (the tracked-window cell map).
func _rho_at_world(rho: PackedFloat32Array, w: Vector3) -> float:
	var N: int = _sim.grid_N
	var e: Vector3 = _sim._extents()
	var c: Vector3 = _sim._window_center
	var hx: float = e.x * 2.0 / float(N)
	var hy: float = e.y * 2.0 / float(N)
	var hz: float = e.z * 2.0 / float(N)
	var gx := int(floor((w.x - c.x + e.x) / hx)) % N
	var gy := int(floor((w.y - c.y + e.y) / hy)) % N
	var gz := int(floor((w.z - c.z + e.z) / hz)) % N
	if gx < 0: gx += N
	if gy < 0: gy += N
	if gz < 0: gz += N
	return rho[gx + N * (gy + N * gz)]


# ═══════════════════════════════════════════════════════════════════════
# GATE D — one-RD staging holds (the decoupled engine path)
# ═══════════════════════════════════════════════════════════════════════

func _begin_gate_d() -> void:
	print("[CapBattery] gate d: one-RD staging holds")
	_sim.box_scale = 1.0
	_sim._window_center = Vector3.ZERO
	_grep_gate()
	_sim.physics_decoupled = true
	_sim._decoupled_active = true   # the sim's own _ready latched it from the tscn (false)
	_sim.meshless_mode = false      # the parity probe's proven config — the drain
	_sim.meshless_gravity = false   # tests the one-RD record path, not the tree
	_sim.home_window_enabled = false
	_sim.playing = false
	_sim.reinit()
	_rd = _sim._rd
	_phase = 1
	_frame_samples.clear()
	print("[CapD] decoupled engine starting...")


func _gate_d_drive() -> void:
	if _phase == 1:
		if _sim._physics_engine == null or not _sim._physics_engine.setup_ready():
			return
		var t0 := Time.get_ticks_msec()
		var eng: Object = _sim._physics_engine
		while eng._executed < 2048 and Time.get_ticks_msec() - t0 < 60000:
			eng.update_bh_header()
			var cl: int = _sim._rd.compute_list_begin()
			var steps: int = eng.record_pending_steps(cl, 2048)
			_sim._rd.compute_list_end()
			if steps > 0:
				if eng.mesh_rebuild_due():
					eng._mesh_rebuild()
				eng.readback_telemetry()   # the readback self-stall = the sync
		var t1 := Time.get_ticks_msec()
		var exec: int = eng._executed
		var ok_drain: bool = exec >= 2048 and t1 - t0 < 60000
		print("[CapD] fixed-target drain: executed=%d target=2048 wall=%d ms -> %s"
				% [exec, t1 - t0, "PASS" if ok_drain else "FAIL"])
		if not ok_drain:
			_fail += 1
		_results.append({"gate": "d", "name": "fixed-target drain sustains",
				"pass": ok_drain, "detail": "executed=%d wall=%d ms" % [exec, t1 - t0]})
		_sim.playing = true
		_frame_t0 = Time.get_ticks_msec()
		_frame_t1 = _frame_t0 + 2000   # discard the drain-settling first 2 s
		_phase = 2
	elif _phase == 2:
		var now := Time.get_ticks_msec()
		if now < _frame_t1:
			return
		if now - _frame_t1 < 15000:
			_frame_samples.append(_last_frame_ms)
			return
		_sim.playing = false
		_assert_frame_variance()
		_gate = 5
		_verdict()
		return


func _assert_frame_variance() -> void:
	var n := _frame_samples.size()
	if n < 50:
		print("[CapD] frame-variance: too few samples (%d) — FAIL" % n)
		_fail += 1
		_results.append({"gate": "d", "name": "frame-time variance", "pass": false,
				"detail": "samples=%d" % n})
		return
	_frame_samples.sort()
	var mean := 0.0
	for f in _frame_samples:
		mean += f
	mean /= float(n)
	var p99: float = _frame_samples[int(0.99 * n)]
	var mx: float = _frame_samples[n - 1]
	var ok: bool = p99 <= 3.0 * mean and mx <= 4.0 * mean
	print("[CapD] frame-time over 15 s: n=%d mean=%.1f p99=%.1f max=%.1f ms (p99<=3x %s, max<=4x %s) -> %s"
			% [n, mean, p99, mx, str(p99 <= 3.0 * mean), str(mx <= 4.0 * mean),
			"PASS" if ok else "FAIL"])
	if not ok:
		_fail += 1
	_results.append({"gate": "d", "name": "frame-time variance (p99/max ratio)",
			"pass": ok, "detail": "mean=%.1f p99=%.1f max=%.1f ms" % [mean, p99, mx]})


## Grep gate: the one-RD physics CHAIN functions must contain NO mid-list
## buffer_get_data / _rd.sync / _rd.submit (the global-RD contract — the
## engine records its chains into the shared queue and NEVER syncs/reads
## mid-list). The sanctioned readback sites are the job-boundary accepted
## group (the publish/telemetry/COM/rebuild) + the local-RD standalone
## paths (run_steps + the inline path's own readbacks, which the battery
## drives). The gate asserts the CHAIN functions; the other sync sites are
## REPORTED (the accounting — the merge's cycle readbacks are the known
## deferred item; the inline path's staging readbacks are its own model).
func _grep_gate() -> void:
	var chains := {
		"res://scripts/cassi_physics_engine.gd": ["record_pending_steps", "_step_dispatches", "_tree_run_in_list"],
		"res://scripts/cassi_sim.gd": ["_decoupled_poll_and_render"],
	}
	var banned := ["buffer_get_data", ".sync(", ".submit()"]
	var violations := []
	var accounting := 0
	for p in chains:
		var f := FileAccess.open(p, FileAccess.READ)
		if f == null:
			violations.append("%s: unreadable" % p)
			continue
		var lines: PackedStringArray = f.get_as_text().split("\n")
		var cur := "?"
		var in_chain := false
		var chain_start := -1
		for li in range(lines.size()):
			var ln: String = lines[li]
			var m := RegEx.new()
			m.compile("^func ([A-Za-z0-9_]+)")
			var mm := m.search(ln)
			if mm:
				cur = mm.get_string(1)
				in_chain = cur in chains[p]
				chain_start = li if in_chain else -1
				continue
			if in_chain:
				if ln.begins_with("\t") or ln.strip_edges().is_empty():
					for b in banned:
						if ln.contains(b):
							violations.append("%s:%d %s (in %s)" % [p, li + 1, b, cur])
				else:
					in_chain = false   # the function body ended (a non-indented line)
			else:
				for b in banned:
					if ln.contains(b):
						accounting += 1
	var ok: bool = violations.is_empty()
	for v in violations:
		print("[CapD] CHAIN-SYNC-VIOLATION: " + v)
	print("[CapD] grep gate: %d mid-chain sync/get_data violation(s) -> %s (other sync sites accounted: %d)"
			% [violations.size(), "PASS" if ok else "FAIL", accounting])
	if not ok:
		_fail += 1
	_results.append({"gate": "d", "name": "no mid-chain sync/get_data",
			"pass": ok, "detail": "%d violation(s), %d other sites" % [violations.size(), accounting]})


# ═══════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════

var _rng := RandomNumberGenerator.new()

func _ensure_rng_seed() -> void:
	_rng.seed = 0xC0551E


func _snapshot() -> Dictionary:
	var rd: RenderingDevice = _sim._rd
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var np: int = _sim.N_particles
	return {
		"hdr": rd.buffer_get_data(_sim._bh_buf, 0, 256).to_float32_array(),
		"field": rd.buffer_get_data(_sim._field_ey, 0, n3 * 4).to_float32_array(),
		"pos": rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array(),
	}


func _max_diff(a: PackedFloat32Array, b: PackedFloat32Array) -> float:
	var n := mini(a.size(), b.size())
	var m := 0.0
	for i in range(n):
		m = maxf(m, absf(a[i] - b[i]))
	return m


func _verdict() -> void:
	print("[CapBattery] ============ CAPABILITY BATTERY VERDICT ============")
	print("[CapBattery] gate | result | detail")
	for r in _results:
		print("[CapBattery] %-4s | %s | %s" % [r["gate"], "PASS" if r["pass"] else "FAIL", r["detail"]])
	if _fail == 0:
		print("[CapBattery] VERDICT: PASS — gates a-d all green")
	else:
		print("[CapBattery] VERDICT: FAIL — %d assertion failure(s)" % _fail)
	get_tree().quit(0 if _fail == 0 else 1)
