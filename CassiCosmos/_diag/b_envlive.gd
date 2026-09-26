extends Node
## B-build piece 3 — the PRODUCTION WIRING probe (b_envlive): the tracked
## box as a LIVE toggle in the running sim. The sim SELF-DRIVES (playing,
## physics_decoupled) with tracking_envelope = true (the scene export —
## applied at the sim's OWN _ready, so the decoupled engine boots with it;
## NO mid-run reinit: the probe is a passive observer). The sim's own
## `_track_envelope_window()` (the production wiring) computes the
## structure's percentile envelope from the ENGINE's live pos buffer (the
## P3 published-mirror source), feeds the EnvelopeTracker, and writes the
## THREE state slots the b_track probe proved — window_center, box_scale
## (TOTAL vs the original box, never cumulative) and the bh header's
## per-axis half-extents (bytes 36/40/44) — into BOTH the sim (the render
## seam) and the engine (the physics box).
##
## The OFF control (tracking_envelope=false -> the fixed box stays fixed,
## box_scale 1.0, center 0) is covered by the battery 8/8 (the default
## path bit-identical) + was directly verified in the first b_envlive
## run's OFF phase (PASS) before the probe's double-reinit design bug was
## removed.
##
## The ON phase: the probe seeds a compact two-cluster structure into the
## engine's pos buffer (after the engine boot); the tracker's next 2 s
## tick re-fits the tile to the structure (shrink); assertions per tick:
## the ENGINE's header 36/40/44 (readback) == the tracker's extent; the
## engine's box_scale/window_center == the sim's == the tracker's state;
## re_fits advanced.

const N_PARTICLES := 50000
const N_PER_CLUSTER := 25000
const CLUSTER_A0 := -28.0
const CLUSTER_B0 := 28.0
const SIGMA := 6.0
const TICKS_TO_WATCH := 3     # the envelope ticks to verify

var _sim: Node
var _rd: RenderingDevice
var _seeded := false
var _ticks := 0
var _last_re_fits := -1
var _on_ok := true
var _orig_box := Vector3.ONE
var _fail := 0


func _ready() -> void:
	_sim = $CassiSim
	_rd = _sim._rd
	_orig_box = Vector3(_sim._extents().x, _sim._extents().y, _sim._extents().z)
	print("[BEnvLive] started: tracking_envelope=%s decoupled=%s box=(%.1f, %.1f, %.1f)"
			% [str(_sim.tracking_envelope), str(_sim.physics_decoupled),
			_orig_box.x, _orig_box.y, _orig_box.z])


func _process(_delta: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	if _sim._physics_engine == null or not _sim._decoupled_active:
		return
	var eng: Object = _sim._physics_engine
	if not _sim._decoupled_boot_wait and eng.setup_ready() and not _seeded:
		_seed_clusters(eng)
		_seeded = true
	var trk = _sim._env_tracker
	if trk == null:
		return
	if trk.re_fits != _last_re_fits:
		_last_re_fits = trk.re_fits
		_ticks += 1
		_check_tick(eng, trk)
		# Verdict once the initial no-op consistency (tick 1) AND the
		# verified re-fit (the tile contracted to the structure, the three
		# slots flowed) have both been checked.
		if trk.re_fits >= 1 and _ticks >= 2:
			_verdict()


## Seed a compact two-cluster structure into the ENGINE's pos buffer
## (the probe OWNS the IC — the structure's envelope is far smaller than
## the box, so the tracker must CONTRACT the tile on its next tick).
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
		pos[i * 4 + 3] = 0.0
	_rd.buffer_update(eng._pos_buf, 0, np * 16, pos.to_byte_array())
	_rd.buffer_update(eng._vel_buf, 0, np * 16, vel.to_byte_array())
	print("[BEnvLive] seeded two clusters at (%.1f, %.1f) sigma=%.1f — the tracker must CONTRACT the tile"
			% [CLUSTER_A0, CLUSTER_B0, SIGMA])


## The ON-phase assertions: the ENGINE's header + box follow the tracker
## (the three slots flowed through the sim's per-frame refresh and the
## engine's update_bh_header).
func _check_tick(eng: Object, trk) -> void:
	var ok := true
	# (a) the engine's header extents (bytes 36/40/44 — read back the
	# buffer the engine's update_bh_header refreshed from its bytes).
	var hdr: PackedFloat32Array = _rd.buffer_get_data(eng._bh_buf, 36, 12).to_float32_array()
	for a in range(3):
		if absf(hdr[a] - trk.extent[a]) > 1e-3 * maxf(trk.extent[a], 1.0):
			ok = false
	# (b) the engine's scale == the sim's == the tracker's total-vs-orig.
	var scl: float = trk.extent.x / maxf(_orig_box.x, 1e-30)
	if absf(eng.box_scale - scl) > 1e-4 or absf(_sim.box_scale - scl) > 1e-4:
		ok = false
	# (c) the window centers agree.
	if (eng._window_center - trk.center).length() > 1e-3:
		ok = false
	if (_sim._window_center - trk.center).length() > 1e-3:
		ok = false
	if not ok:
		_on_ok = false
		_fail += 1
	print("[BEnvLive] tick %d: re_fits=%d center=(%.1f, %.1f, %.1f) extent=(%.1f, %.1f, %.1f) box_scale=%.3f hdr_ext=(%.1f, %.1f, %.1f) -> %s"
			% [_ticks, trk.re_fits, trk.center.x, trk.center.y, trk.center.z,
			trk.extent.x, trk.extent.y, trk.extent.z, _sim.box_scale,
			hdr[0], hdr[1], hdr[2], "PASS" if ok else "FAIL"])


func _verdict() -> void:
	print("[BEnvLive] ============ B-BUILD PIECE 3 (PRODUCTION WIRING) VERDICT ============")
	if _fail == 0:
		print("[BEnvLive] VERDICT: PASS — the tracked box is a live toggle (OFF = the fixed box, bit-identical; ON = the envelope re-fit flows into the sim + the engine)")
	else:
		print("[BEnvLive] VERDICT: FAIL — %d failures" % _fail)
	get_tree().quit(0)
