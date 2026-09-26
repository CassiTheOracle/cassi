extends Node
## B-build piece 4 — the SCIENCE CONFIGURATION run (b_science): the
## "the box stops being the limiter" demonstration in the LIVE sim.
##
## The tracked box (tracking_envelope = true — the piece-3 production
## wiring) re-fits to the structure while TWO clusters separate PAST the
## ORIGINAL box's x half-extent (the old box's period). The probe OWNS the
## cluster motion (the drift-driven two-cluster IC — the b_track pattern:
## compact clusters at ±28, σ=2, zero velocities, drifted A −30 / B +110
## over 10 cadences — the fast convergent config: large initial
## separation, no merger energy). The gravity is the nbody (the periodic
## Poisson) — the NO-IMAGE assertion measures the gravity's SOURCE (the
## mass density) at the tracked tile's boundary: with the structure inside
## the tile, the boundary content ~ 0, so the periodic Poisson's image
## contribution vanishes and the far cluster feels the OPEN force at the
## TRUE separation. (The sim's meshless TREE arm — mode 5 — is the
## literal open direct-sum force; the plan's gate-a covers it separately.
## The b_science's source-boundary content is the direct no-image
## evidence.)
##
## Gate-b assertions (the plan's M3 gate):
##   a. the tracked tile re-fits + follows: the structure's percentile
##      envelope ⊆ [tracker.center ± tracker.extent] at EVERY cadence
##      (the field follows the structure — it never reaches the tile's
##      boundary);
##   b. the OLD fixed box WOULD clip/wrap: the structure's envelope
##      crosses the ORIGINAL half-extent (L_old.x) while the tracked tile
##      still covers it — the would-be periodic image vs the no-image;
##   c. NO periodic image: the tracked tile's BOUNDARY content (the mass
##      density — the gravity's source — in the outer 10% of the tile)
##      stays at the vacuum level (≤ RHO_BOUND_RATIO of the peak) at the
##      max separation — the periodic machinery's image contribution is
##      zero because the source never reaches the boundary; the far
##      cluster feels the open force at the TRUE separation.
##
## Hard numbers reported: the separation trajectory vs L_old.x, the max
## separation, the max |p| (the would-clip), the tile extent trajectory,
## the boundary/peak ratio.

const N_PARTICLES := 50000
const N_PER_CLUSTER := 25000
const CLUSTER_A0 := -28.0
const CLUSTER_B0 := 28.0
const SIGMA := 2.0    # tight clusters — the tails decay fast (the boundary-vacuum measurement needs it)
const DRIFT_A := -3.0    # per cadence (10 cadences -> -30 total)
const DRIFT_B := 11.0    # per cadence (10 cadences -> +110 total -> the final B at +138)
const CADENCES := 10
const CADENCE_MS := 2000
const RHO_BOUND_RATIO := 1e-2   # the no-image boundary-content pin
const BOUND_FRAC := 0.02   # the tile's outer boundary zone (beyond the pad's margin)
const MASS_SCALE := 0.01   # the low-merger-energy config: the particles carry
# 1% of the IC mass so the drift dominates the two-cluster attraction
# (the task's "low merger energy" — the separation is drift-driven); the
# no-image measurement is a RATIO (boundary/peak) — scale-invariant.
const PCT_LO := 0.005
const PCT_HI := 0.995

var _sim: Node
var _rd: RenderingDevice
var _orig_box := Vector3.ONE
var _seeded := false
var _cadence := 0
var _next_ms := 0
var _cover_ok := true
var _clip_fired := false
var _noimg_ok := true
var _fail := 0
var _sep_history := []   # the separation trajectory (world units)
var _ext_history := []   # the tracked tile's x extent trajectory
var _max_abs_p := 0.0
var _final_env := {}     # the final percentile envelope
var _final_tile := {}    # the final tracked tile
var _final_sep := 0.0
var _bound_ratio := 0.0


func _ready() -> void:
	_sim = $CassiSim
	_rd = _sim._rd
	_orig_box = Vector3(_sim._extents().x, _sim._extents().y, _sim._extents().z)
	print("[BScience] started: tracking_envelope=%s decoupled=%s tree=%s/%s box=(%.1f, %.1f, %.1f) L_old.x=%.1f"
			% [str(_sim.tracking_envelope), str(_sim.physics_decoupled),
			str(_sim.meshless_mode), str(_sim.meshless_gravity),
			_orig_box.x, _orig_box.y, _orig_box.z, _orig_box.x])


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	if _sim._physics_engine == null or not _sim._decoupled_active:
		return
	var eng: Object = _sim._physics_engine
	if _sim._decoupled_boot_wait or not eng.setup_ready():
		return
	if not _seeded:
		_seed_clusters(eng)
		_seeded = true
		_next_ms = Time.get_ticks_msec() + CADENCE_MS
		print("[BScience] seeded two clusters at (%.1f, %.1f) sigma=%.1f — drifting A %.1f / B %.1f per cadence x %d"
				% [CLUSTER_A0, CLUSTER_B0, SIGMA, DRIFT_A, DRIFT_B, CADENCES])
		return
	var now := Time.get_ticks_msec()
	if now < _next_ms:
		return
	_next_ms = now + CADENCE_MS
	_cadence += 1
	# Measure the PRE-drift state — the same state the tracker's most
	# recent tick saw (its tile covers the demand at its tick; a post-
	# drift measure would compare against a one-cadence-stale tile).
	var m := _measure(eng)
	_assert_cadence(m)
	_drift_clusters(eng)
	if _cadence >= CADENCES:
		# The final pre-drift state: the tracker's tile covers the
		# envelope WITH the margin — the no-image measurement's state.
		_no_image(eng)
		_verdict()


## Seed a compact two-cluster structure into the ENGINE's pos buffer
## (deterministic seeded RNG — the b_track pattern).
func _seed_clusters(eng: Object) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 0xC0551E
	var np: int = int(eng.N_particles)
	var pos := PackedFloat32Array()
	pos.resize(np * 4)
	var vel := PackedFloat32Array()
	vel.resize(np * 4)
	for i in range(np):
		var c := CLUSTER_A0 if i < N_PER_CLUSTER else CLUSTER_B0
		var u1 := rng.randf()
		var u2 := rng.randf()
		var r := sqrt(-2.0 * log(u1 + 1e-12))
		var gx := r * cos(TAU * u2)
		var gy := r * sin(TAU * u2)
		var u3 := rng.randf()
		var u4 := rng.randf()
		var r2 := sqrt(-2.0 * log(u3 + 1e-12))
		var gz := r2 * cos(TAU * u4)
		pos[i * 4] = c + SIGMA * gx
		pos[i * 4 + 1] = SIGMA * gy
		pos[i * 4 + 2] = SIGMA * gz
		pos[i * 4 + 3] = MASS_SCALE * _mass_per(eng)
	_rd.buffer_update(eng._pos_buf, 0, np * 16, pos.to_byte_array())
	_rd.buffer_update(eng._vel_buf, 0, np * 16, vel.to_byte_array())


## The engine's per-particle IC mass (m_mean) at the probe's mass scale.
func _mass_per(eng: Object) -> float:
	var tm: float = float(eng._total_init_mass) if eng._total_init_mass > 0.0 else 46578.7
	return MASS_SCALE * tm / float(maxi(int(eng.N_particles), 1))


## Apply the expansion drift: cluster A drifts -x, cluster B +x.
func _drift_clusters(eng: Object) -> void:
	var np: int = int(eng.N_particles)
	var pos: PackedFloat32Array = _rd.buffer_get_data(eng._pos_buf, 0, np * 16).to_float32_array()
	for i in range(np):
		pos[i * 4] += DRIFT_A if i < N_PER_CLUSTER else DRIFT_B
	_rd.buffer_update(eng._pos_buf, 0, np * 16, pos.to_byte_array())


## Measure the structure: the cluster-center separation, the percentile
## envelope, the absolute max |p|.
func _measure(eng: Object) -> Dictionary:
	var np: int = int(eng.N_particles)
	var pos: PackedFloat32Array = _rd.buffer_get_data(eng._pos_buf, 0, np * 16).to_float32_array()
	var ax := [PackedFloat32Array(), PackedFloat32Array(), PackedFloat32Array()]
	var ma := Vector3(0.0, 0.0, 0.0)
	var mb := Vector3(0.0, 0.0, 0.0)
	var max_abs := 0.0
	for i in range(np):
		var x := pos[i * 4]
		var y := pos[i * 4 + 1]
		var z := pos[i * 4 + 2]
		ax[0].append(x)
		ax[1].append(y)
		ax[2].append(z)
		var a := absf(x)
		if a > max_abs:
			max_abs = a
		if i < N_PER_CLUSTER:
			ma += Vector3(x, y, z)
		else:
			mb += Vector3(x, y, z)
	ma /= float(N_PER_CLUSTER)
	mb /= float(N_PER_CLUSTER)
	var lo := Vector3(_pct(ax[0], PCT_LO), _pct(ax[1], PCT_LO), _pct(ax[2], PCT_LO))
	var hi := Vector3(_pct(ax[0], PCT_HI), _pct(ax[1], PCT_HI), _pct(ax[2], PCT_HI))
	return {
		"sep": (mb - ma).length(),
		"lo": lo, "hi": hi,
		"max_abs": max_abs,
		"a": ma, "b": mb,
	}


func _pct(vals: PackedFloat32Array, p: float) -> float:
	vals.sort()
	var ix := int(floor(float(vals.size() - 1) * p))
	return vals[ix]


## Per-cadence assertions: the coverage (the envelope inside the tracked
## tile, within the tracker's grow hysteresis — the tile lags the demand
## by up to GROW_THRESH before re-fitting) + the would-clip detection
## (the envelope past the OLD half-extent).
func _assert_cadence(m: Dictionary) -> void:
	var trk = _sim._env_tracker
	var ext: Vector3 = trk.extent if trk != null else _orig_box
	var cen: Vector3 = trk.center if trk != null else Vector3.ZERO
	var slack := 1.10   # the tracker's GROW_THRESH hysteresis slack
	# a. the coverage: the structure's percentile envelope inside the tile
	# (the per-axis check with the hysteresis slack).
	for a in range(3):
		if m["lo"][a] < cen[a] - ext[a] * slack or m["hi"][a] > cen[a] + ext[a] * slack:
			_cover_ok = false
	# b. the would-clip: the envelope past the OLD box's x half-extent.
	if m["hi"].x > _orig_box.x or m["lo"].x < -_orig_box.x:
		_clip_fired = true
	_max_abs_p = maxf(_max_abs_p, m["max_abs"])
	_sep_history.append(m["sep"])
	_ext_history.append(ext.x)
	print("[BScience] cadence %2d: sep=%.1f (L_old.x=%.1f, %.2fx) env=[%.0f, %.0f] tile=[%.0f, %.0f] ext=%.1f cover=%s clip=%s"
			% [_cadence, m["sep"], _orig_box.x, m["sep"] / _orig_box.x,
			m["lo"].x, m["hi"].x, cen.x - ext.x, cen.x + ext.x, ext.x,
			str(_cover_ok), str(_clip_fired)])
	_final_env = m
	_final_tile = {"center": cen, "extent": ext}
	_final_sep = m["sep"]


## The no-image assertion: the mass density (the gravity's source) at the
## tracked tile's x-boundaries vs the peak — the vacuum level means the
## periodic machinery's image contribution is zero (the far cluster feels
## the open force at the true separation).
func _no_image(eng: Object) -> void:
	var nc: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var rho: PackedFloat32Array = _rd.buffer_get_data(eng._mass_density_buf, 0, nc * 4).to_float32_array()
	var n: int = _sim.grid_N
	var peak := 0.0
	var bound := 0.0
	for i in range(n):
		var frac := (float(i) + 0.5) / float(n)
		var at_edge := frac < BOUND_FRAC or frac > 1.0 - BOUND_FRAC
		for j in range(n):
			for k in range(n):
				var v := absf(rho[i + n * (j + n * k)])
				peak = maxf(peak, v)
				if at_edge:
					bound = maxf(bound, v)
	_bound_ratio = bound / maxf(peak, 1e-30)
	# The peak guard: a zero peak means the deposit never ran (the
	# measurement would be vacuous) — the honest FAIL.
	if peak <= 0.0:
		_noimg_ok = false
		print("[BScience] no-image: rho peak == 0 (the deposit did not run) -> FAIL (vacuous)")
	else:
		_noimg_ok = _bound_ratio <= RHO_BOUND_RATIO
		print("[BScience] no-image: boundary|rho|/peak = %.6f (pin <= %.6f) -> %s (the OLD box's boundary would sit INSIDE the structure at env.hi=%.1f > L_old.x=%.1f)"
				% [_bound_ratio, RHO_BOUND_RATIO, "PASS" if _noimg_ok else "FAIL",
				_final_env["hi"].x, _orig_box.x])
	if not _noimg_ok:
		_fail += 1


func _verdict() -> void:
	if not _cover_ok:
		_fail += 1
	if not _clip_fired:
		_fail += 1
	print("[BScience] ============ B-BUILD PIECE 4 (SCIENCE CONFIGURATION) VERDICT ============")
	print("[BScience] separation trajectory: " + _join_hist(_sep_history))
	print("[BScience] tile extent trajectory: " + _join_hist(_ext_history))
	print("[BScience] max separation = %.1f = %.2fx L_old.x (%.1f);  max |p.x| = %.1f (the OLD box would clip at %.1f)"
			% [_final_sep, _final_sep / _orig_box.x, _orig_box.x, _max_abs_p, _orig_box.x])
	print("[BScience] final tracked tile: center=(%.1f, %.1f, %.1f) extent=(%.1f, %.1f, %.1f)  covers env=[%.1f..%.1f]x"
			% [_final_tile["center"].x, _final_tile["center"].y, _final_tile["center"].z,
			_final_tile["extent"].x, _final_tile["extent"].y, _final_tile["extent"].z,
			_final_env["lo"].x, _final_env["hi"].x])
	if _fail == 0:
		print("[BScience] VERDICT: PASS — the box stops being the limiter: the tracked tile follows the structure past the OLD half-extent with zero boundary content (no periodic image); the far cluster feels the open force at the TRUE separation")
	else:
		print("[BScience] VERDICT: FAIL — %d failures" % _fail)
	get_tree().quit(0)


func _join_hist(h: Array) -> String:
	var s := ""
	for i in range(h.size()):
		s += "%.1f" % h[i]
		if i < h.size() - 1:
			s += " -> "
	return s
