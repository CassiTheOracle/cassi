extends Node
## B-build tracking-envelope probe battery (overhaul build plan M3 piece 1):
## the coarse N³ tile whose extent re-fits to the structure's envelope on
## the slow cadence instead of the fixed box.
##
## The probe drives the SIM'S OWN window machinery (the single source of
## the per-frame header/PC fills) — no canonical shader or sim code is
## touched:
##   - `_sim._window_center` = the tracked origin (the per-frame header
##     refresh carries it into bh[0].yzw + the deposit/render/qhist PC
##     offset terms — the 3e3f9a6 window path);
##   - `_sim.box_scale` = the uniform envelope scale (the per-frame
##     `_extents()` fills the two-fluid/deposit/poisson/qhist extent PCs
##     and the dual-lattice offsets bh[1].xyz);
##   - `_sim._bh_init_bytes` floats 36/40/44 = the per-axis half-extents
##     (the header refresh writes the whole 576 B every frame from this
##     byte array — patching the SOURCE, not the buffer).
##
## Phases (STEP-counted cadence — deterministic, not wall-clock):
##   0a  canary, tracked OFF  (2 cadences) — the reference end-state
##   0b  canary, tracked ON   (2 cadences) — the tracker computes a no-op
##       (envelope inside the hysteresis band) -> bit-identical end-state
##   1a  growing two-cluster run, tracked (6 cadences) — the A/B clusters
##       drift apart past the OLD box; the tracker re-fits origin+extent
##   1b  identical rerun — determinism (max-diff == 0.0 vs 1a)
##   2   verdict + quit
##
## Assertions:
##   - the header extent follows the tracker's extent (per cadence);
##   - the structure's envelope is covered by the tile (per cadence);
##   - the OLD fixed box would clip the structure at the end (|B| > old
##     extent while the tracked tile covers it);
##   - the extent re-fit fired (the envelope GROWS the tile);
##   - determinism: identical runs -> bit-identical end-states.

const BATCH := 4
const STEPS_PER_CADENCE := 400
const CANARY_CADENCES := 2
const RUN_CADENCES := 6
const N_PARTICLES := 50000
const N_PER_CLUSTER := 25000
const CANARY_A0 := 0.0    # unused — the canary FILLS the box (uniform)
const CANARY_B0 := 0.0
const CLUSTER_A0 := -28.0
const CLUSTER_B0 := 28.0
const SIGMA := 6.0
const DRIFT_A := -30.0     # units over the run (6 cadences)
const DRIFT_B := 80.0
const SUBSAMPLE := 16

var _sim: Node
var _rd: RenderingDevice
var _tracker
var _orig_box := Vector3.ONE   # the ORIGINAL fixed box (never changes)
var _box_old := Vector3.ONE    # the phase-start box (the would-clip ref)
var _phase := 0
var _phase_name := ""
var _step := 0
var _cadence := 0
var _cadences_total := 0
var _next_cadence_step := 0
var _tracked := false
var _growing := false
var _ref_off := {}
var _ref_1a := {}
var _fail := 0
var _hdr_follow_ok := true
var _coverage_ok := true
var _grow_fired := false


func _ready() -> void:
	_sim = $CassiSim
	_sim.playing = false
	_rd = _sim._rd
	_sim.reinit()
	_orig_box = _sim._extents()
	_box_old = _orig_box
	_tracker = EnvelopeTracker.new()
	_tracker.center = Vector3.ZERO
	_tracker.extent = _orig_box
	_start_phase("canary-off", false, false)


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	if _phase >= 9:
		_verdict()
		return
	# Drive the sim continuously (the gate-iv pattern).
	_sim._run_physics_steps(BATCH)
	_step += BATCH
	# STEP-counted cadence events — deterministic across runs.
	while _step >= _next_cadence_step:
		_next_cadence_step += STEPS_PER_CADENCE
		_cadence += 1
		if _growing:
			_drift_clusters()
		if _tracked:
			_apply_tracking()
			# One extra batch: the sim's per-frame header refresh carries the
			# patched state (the header's 36/40/44 = the tracker's extent).
			_sim._run_physics_steps(BATCH)
			_step += BATCH
			if _growing:
				_assert_cadence()
		if _cadence >= _cadences_total:
			_end_phase()
			return


func _start_phase(name: String, tracked: bool, growing: bool) -> void:
	_phase_name = name
	_tracked = tracked
	_growing = growing
	_step = 0
	_cadence = 0
	_next_cadence_step = STEPS_PER_CADENCE
	_cadences_total = RUN_CADENCES if growing else CANARY_CADENCES
	_hdr_follow_ok = true
	_coverage_ok = true
	_sim.reinit()
	_sim.box_scale = 1.0                       # reset the tracked state
	_sim._window_center = Vector3.ZERO
	var hb0: PackedByteArray = _sim._bh_init_bytes
	hb0.encode_float(36, _orig_box.x)
	hb0.encode_float(40, _orig_box.y)
	hb0.encode_float(44, _orig_box.z)
	_sim._bh_init_bytes = hb0   # PackedByteArray is COW — reassign the member
	_box_old = _orig_box
	_tracker.center = Vector3.ZERO
	_tracker.extent = _orig_box
	_tracker.re_fits = 0
	_seed_clusters(CLUSTER_A0 if growing else CANARY_A0,
		CLUSTER_B0 if growing else CANARY_B0)
	print("[BTrack] phase '%s': grid_N=%d dt=%.4f box=(%.1f, %.1f, %.1f) tracked=%s growing=%s"
		% [name, _sim.grid_N, _sim.dt, _box_old.x, _box_old.y, _box_old.z,
		str(tracked), str(growing)])


## Seed the two-cluster IC: A = first N_PER_CLUSTER particles at (A0, 0, 0),
## B = the rest at (B0, 0, 0), gaussian sigma, zero velocities, zero masses
## (the probe OWNS the particle motion — the drift is the only driver).
func _seed_clusters(a0: float, b0: float) -> void:
	_ensure_rng_seed()   # every phase starts from the SAME particle layout
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos := PackedFloat32Array()
	pos.resize(np * 4)
	var vel := PackedFloat32Array()
	vel.resize(np * 4)
	var filling := not _growing   # the canary FILLS the box (uniform)
	for i in range(np):
		if filling:
			pos[i * 4] = (_rng.randf() * 2.0 - 1.0) * _orig_box.x
			pos[i * 4 + 1] = (_rng.randf() * 2.0 - 1.0) * _orig_box.y
			pos[i * 4 + 2] = (_rng.randf() * 2.0 - 1.0) * _orig_box.z
			pos[i * 4 + 3] = 0.0
			vel[i * 4] = 0.0
			vel[i * 4 + 1] = 0.0
			vel[i * 4 + 2] = 0.0
			vel[i * 4 + 3] = 0.0
			continue
		var c := a0 if i < N_PER_CLUSTER else b0
		var s := SIGMA * 1.0
		# Gaussian via Box-Muller (deterministic seeded RNG — see below).
		var u1 := _rng.randf()
		var u2 := _rng.randf()
		var r := sqrt(-2.0 * log(u1 + 1e-12))
		var gx := r * cos(TAU * u2)
		var gy := r * sin(TAU * u2)
		var u3 := _rng.randf()
		var u4 := _rng.randf()
		var r2 := sqrt(-2.0 * log(u3 + 1e-12))
		var gz := r2 * cos(TAU * u4)
		pos[i * 4] = c + s * gx
		pos[i * 4 + 1] = s * gy
		pos[i * 4 + 2] = s * gz
		pos[i * 4 + 3] = 0.0
		vel[i * 4] = 0.0
		vel[i * 4 + 1] = 0.0
		vel[i * 4 + 2] = 0.0
		vel[i * 4 + 3] = 0.0
	rd.buffer_update(_sim._pos_buf, 0, np * 16, pos.to_byte_array())
	rd.buffer_update(_sim._vel_buf, 0, np * 16, vel.to_byte_array())
	var xmin := 1e30
	var xmax := -1e30
	for i in range(np):
		xmin = minf(xmin, pos[i * 4])
		xmax = maxf(xmax, pos[i * 4])
	print("[BTrack] seed '%s': clusters (%d at %.1f, %d at %.1f) raw x in [%.1f, %.1f]"
		% [_phase_name, N_PER_CLUSTER, a0, N_PARTICLES - N_PER_CLUSTER, b0, xmin, xmax])
	# Reset the field to zero (the two-fluid relaxes from zero -> the
	# deterministic checkerboard attractor; no IC pulse needed here).
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var z := PackedFloat32Array()
	z.resize(n3)
	rd.buffer_update(_sim._field_ey, 0, n3 * 4, z.to_byte_array())
	rd.buffer_update(_sim._field_ei, 0, n3 * 4, z.to_byte_array())
	var zv := PackedFloat32Array()
	zv.resize(n3 * 4)
	rd.buffer_update(_sim._field_vel, 0, n3 * 16, zv.to_byte_array())


var _rng := RandomNumberGenerator.new()

## Deterministic cluster seeding: the SAME seed every phase -> every run
## starts from the same particle layout (the determinism canary needs it).
func _ensure_rng_seed() -> void:
	_rng.seed = 0xC0551E


## Apply the expansion drift: cluster A drifts -x, cluster B +x, applied at
## each re-tile cadence (the pinned re-tile cadence — the plan's determinism
## contract). One 800 KB readback + write per cadence.
func _drift_clusters() -> void:
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos: PackedFloat32Array = rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
	var da: float = DRIFT_A / float(RUN_CADENCES)
	var db: float = DRIFT_B / float(RUN_CADENCES)
	for i in range(np):
		pos[i * 4] += da if i < N_PER_CLUSTER else db
	rd.buffer_update(_sim._pos_buf, 0, np * 16, pos.to_byte_array())


## Run the envelope tracker on a subsample and write the tracked state into
## the sim's own window/extent state (the per-frame refresh carries it).
func _apply_tracking() -> void:
	var rd: RenderingDevice = _sim._rd
	var np: int = _sim.N_particles
	var pos: PackedFloat32Array = rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
	var n := np / SUBSAMPLE
	var s := PackedFloat32Array()
	s.resize(n * 4)
	for i in range(n):
		var ix := i * SUBSAMPLE * 4
		s[i * 4] = pos[ix]
		s[i * 4 + 1] = pos[ix + 1]
		s[i * 4 + 2] = pos[ix + 2]
		s[i * 4 + 3] = 0.0
	_tracker.compute(s, 4, 1)
	# The origin: the sim's per-frame header refresh reads _window_center.
	_sim._window_center = _tracker.center
	# The uniform envelope scale vs the ORIGINAL box (the sim's _extents()
	# = original * box_scale — never cumulative).
	var scl: float = _tracker.extent.x / _orig_box.x
	_sim.box_scale = maxf(scl, 1e-3)
	# The per-axis extents: patch the SIM's header byte array (the single
	# source of the per-frame 576 B refresh).
	var hb: PackedByteArray = _sim._bh_init_bytes
	hb.encode_float(36, _tracker.extent.x)
	hb.encode_float(40, _tracker.extent.y)
	hb.encode_float(44, _tracker.extent.z)
	_sim._bh_init_bytes = hb   # PackedByteArray is COW — reassign the member
	_grow_fired = _grow_fired or _tracker.re_fits > 0


## Per-cadence assertions during the growing run.
func _assert_cadence() -> void:
	var rd: RenderingDevice = _sim._rd
	# (a) the header extent follows the tracker's extent (after the sim's
	# per-frame refresh has carried the patched bytes). The extents live at
	# BYTE offsets 36/40/44 (bh[2].yzw = float indices 9/10/11 — the
	# layout.gd "floats 36/40/44" are byte offsets).
	var hdr: PackedFloat32Array = rd.buffer_get_data(_sim._bh_buf, 36, 12).to_float32_array()
	for a in range(3):
		if absf(hdr[a] - _tracker.extent[a]) > 1e-3 * maxf(_tracker.extent[a], 1.0):
			_hdr_follow_ok = false
	# (b) the structure's envelope is covered by the tile: the coverage
	# demand (max over axes of |env_mid - center| + env_ext, x the pad)
	# must be <= the current extent (the tracker's own grow rule).
	var ext_max: float = maxf(maxf(_tracker.extent.x, _tracker.extent.y), _tracker.extent.z)
	if _tracker.last_demand > ext_max * EnvelopeTracker.GROW_THRESH + 1e-6:
		_coverage_ok = false
	if not _hdr_follow_ok or not _coverage_ok:
		print("[BTrack] cadence %d: hdr_follow=%s coverage=%s demand=%.2f ext=%.2f"
			% [_cadence, str(_hdr_follow_ok), str(_coverage_ok),
			_tracker.last_demand, ext_max])


func _end_phase() -> void:
	var snap := _snapshot()
	print("[BTrack] phase '%s' done: center=(%.2f, %.2f, %.2f) extent=(%.2f, %.2f, %.2f) re_fits=%d"
		% [_phase_name, _tracker.center.x, _tracker.center.y, _tracker.center.z,
		_tracker.extent.x, _tracker.extent.y, _tracker.extent.z, _tracker.re_fits])
	match _phase_name:
		"canary-off":
			_ref_off = snap
			_phase = 1
			_start_phase("canary-on", true, false)
		"canary-on":
			var d := _max_diff(snap["hdr"], _ref_off["hdr"])
			var df := _max_diff(snap["field"], _ref_off["field"])
			var dp := _max_diff(snap["pos"], _ref_off["pos"])
			var ok := d == 0.0 and df == 0.0 and dp == 0.0
			print("[BTrack] canary max-diff: hdr=%.6f field=%.6f pos=%.6f -> %s"
				% [d, df, dp, "PASS" if ok else "FAIL"])
			if not ok:
				_fail += 1
			_phase = 2
			_start_phase("grow-a", true, true)
		"grow-a":
			_ref_1a = snap
			# (c) the old fixed box would clip the structure at the end.
			var np: int = _sim.N_particles
			var pos: PackedFloat32Array = _rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
			var max_abs := 0.0
			for i in range(np):
				max_abs = maxf(max_abs, absf(pos[i * 4]))
			var would_clip := max_abs > _box_old.x
			print("[BTrack] would-clip (old box): max|p.x|=%.2f vs old extent %.2f -> %s"
				% [max_abs, _box_old.x, "PASS" if would_clip else "FAIL"])
			if not would_clip:
				_fail += 1
			print("[BTrack] growing run: header-follow=%s coverage=%s grow-fired=%s"
				% [str(_hdr_follow_ok), str(_coverage_ok), str(_grow_fired)])
			if not (_hdr_follow_ok and _coverage_ok and _grow_fired):
				_fail += 1
			_phase = 3
			_start_phase("grow-b", true, true)
		"grow-b":
			var dh := _max_diff(snap["hdr"], _ref_1a["hdr"])
			var df := _max_diff(snap["field"], _ref_1a["field"])
			var dp := _max_diff(snap["pos"], _ref_1a["pos"])
			var ok := dh == 0.0 and df == 0.0 and dp == 0.0
			print("[BTrack] determinism max-diff: hdr=%.6f field=%.6f pos=%.6f -> %s"
				% [dh, df, dp, "PASS" if ok else "FAIL"])
			if not ok:
				_fail += 1
			_phase = 9


## End-state readbacks for the canary/determinism comparisons.
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
	print("[BTrack] ============ B-BUILD PIECE 1 (TRACKING ENVELOPE) VERDICT ============")
	if _fail == 0:
		print("[BTrack] VERDICT: PASS — the coarse grid follows the structure; the box stops being fixed")
	else:
		print("[BTrack] VERDICT: FAIL — %d assertion failures" % _fail)
	get_tree().quit(0)
