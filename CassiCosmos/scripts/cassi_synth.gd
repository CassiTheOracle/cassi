extends Node
## Cassi Synth — the two-fluid universe as a living instrument.
##
## A Node you add UNDER the CassiSim in your scene. It reads the sim's
## field buffers (grid OR meshless arm — both write _field_ey/_field_ei),
## runs the cheap no-FFT cascade meter (compute/cassi_audio_reduce.glsl),
## and drives a φ-tempered harmonic bank of sine oscillators through a
## Godot AudioStreamGeneratorPlayback. The field → sound mapping:
##
##   • R=4 cascade rungs, box b_m = round(φ^m) → freq f_r = f0·φ^r (f0=55).
##   • each rung's amplitude = the L2 box-difference energy of q=EY²+EI²
##     at that scale, smoothly attack/released (~200 ms);
##   • gentle per-rung detune makes the φ chords shimmer/beat;
##   • a low drone at a musically-mapped subharmonic of the breather mode
##     (see design doc §5 — an ARBITRARY musical scaling, flagged as such);
##     mild saturation lifted by the total energy;
##   • a percussive hit when a NEW black hole nucleates (BH header polled
##     at the same low cadence).
##
## CPU budget: OK — the reduce is R+3 tiny passes + a 64-byte readback,
## every POLL_MS (default 150 ms) — NO per-frame or large readbacks. The
## sine bank is a handful of oscillators. Total audio+reactor CPU ≲ 5%.
##
## Activation: put this node under the sim root, e.g.
##   var s := CassiSynth.new(); sim.add_child(s)
## It needs a live sim node exposing _rd/_field_ey/_field_ei/_bh_buf/grid_N
## and _shaders_ready. It degrades to a silent (but still polling) no-op if
## audio cannot start.

const PHI := 1.618033988749895
const R := 4                       # resolvable cascade rungs on N=64 (design doc §2)
const F0 := 55.0                   # fundamental of the φ-tempered bank (Hz)
const MIX_RATE := 44100.0
const POLL_MS := 150               # meter cadence (100–200 ms budget)
const AR_TAU := 0.20               # attack/release smoothing (≈200 ms)
const DETUNE := 0.0035             # per-rung detune (≈±0.35%) → beating shimmer
const OUT_N := 16

@export var enabled := true
@export var master_gain := 0.25
@export var bh_hit_gain := 0.6

var _sim: Node = null
var _rd: RenderingDevice = null
var _shader_rid := RID()
var _pipe_rid := RID()
var _us_rid := RID()
var _sat_rid := RID()
var _out_rid := RID()
var _chunk := PackedByteArray()

var _ready_ok := false
var _poll_timer := 0.0
var _last_n_bh := -1

var _amp := PackedFloat32Array()     # smoothed per-rung amplitude
var _target_amp := PackedFloat32Array()
var _phase := PackedFloat32Array()   # 2 oscillators per rung
var _detune := PackedFloat32Array()
var _freq := PackedFloat32Array()
var _drone_phase := 0.0
var _hit_env := 0.0                  # percussive envelope (decaying)
var _smooth_energy := 0.0            # ~mean q, drives saturation/drone

var _player: AudioStreamPlayer = null
var _playback: AudioStreamGeneratorPlayback = null


func _ready() -> void:
	_amp.resize(R)
	_target_amp.resize(R)
	_phase.resize(R * 2)
	_detune.resize(R)
	_freq.resize(R)
	for r in range(R):
		_freq[r] = F0 * pow(PHI, float(r))
		_detune[r] = 1.0 + DETUNE * (0.5 - 0.5 * float(r % 3))
	_amp.fill(0.0)
	_target_amp.fill(0.0)
	for i in range(R * 2):
		_phase[i] = 0.0


func _process(delta: float) -> void:
	if _sim == null:
		_sim = parent_sim()
		if _sim == null:
			return
	if not _ready_ok:
		_try_wire()
		return
	if not enabled:
		_fill_audio_buffer(delta)   # keep a silent stream fed
		return

	_poll_timer += delta
	if _poll_timer >= POLL_MS / 1000.0:
		_poll_timer = 0.0
		_poll_meter()

	_update_amps(delta)               # AR smoothing toward the latest targets
	_fill_audio_buffer(delta)         # refill the audio buffer EVERY frame


func parent_sim() -> Node:
	var p := get_parent()
	if p != null and ("grid_N" in p) and p.get("_shaders_ready") is bool:
		return p
	return null


# ── wiring ────────────────────────────────────────────────────────────
func _try_wire() -> void:
	if not bool(_sim.get("_shaders_ready")):
		return                                  # sim still booting
	_rd = _sim.get("_rd")
	if _rd == null:
		return
	if not (_sim.get("_field_ey").is_valid() and _sim.get("_field_ei").is_valid()):
		return
	var grid_n: int = int(_sim.get("grid_N"))

	var sf := load("res://compute/cassi_audio_reduce.glsl") as RDShaderFile
	if sf == null:
		push_error("[CassiSynth] reduce shader load failed")
		return
	var spirv := sf.get_spirv()
	_shader_rid = _rd.shader_create_from_spirv(spirv)
	_pipe_rid = _rd.compute_pipeline_create(_shader_rid)
	if not _pipe_rid.is_valid():
		push_error("[CassiSynth] reduce pipeline build failed")
		return
	var n3 := grid_n * grid_n * grid_n
	_sat_rid = _rd.storage_buffer_create(n3 * 4)
	_out_rid = _rd.storage_buffer_create(OUT_N * 4)
	var z := PackedByteArray(); z.resize(OUT_N * 4)
	_rd.buffer_update(_out_rid, 0, OUT_N * 4, z)
	var zs := PackedByteArray(); zs.resize(n3 * 4)
	_rd.buffer_update(_sat_rid, 0, n3 * 4, zs)
	_us_rid = _rd.uniform_set_create([
		_us_s(0, _sat_rid), _us_s(1, _sim.get("_field_ey")),
		_us_s(2, _sim.get("_field_ei")), _us_s(3, _out_rid),
	], _shader_rid, 0)
	_chunk = PackedFloat32Array([0.0, float(grid_n), 0.0, 0.0]).to_byte_array()

	_start_audio()
	_last_n_bh = _count_bh()          # pre-existing BHs are not "new" hits
	_ready_ok = true
	print("[CassiSynth] wired to sim grid=%d³  meter @ %d ms cadence, R=%d"
		% [grid_n, POLL_MS, R])


func _us_s(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _start_audio() -> void:
	var stream := AudioStreamGenerator.new()
	stream.mix_rate = MIX_RATE
	stream.buffer_length = 0.3
	_player = AudioStreamPlayer.new()
	_player.stream = stream
	add_child(_player)
	_player.play()
	_playback = _player.get_stream_playback()
	if _playback == null:
		push_warning("[CassiSynth] audio start failed (no output device?) — "
			+ "meter still runs, silent until audio is available")


# ── meter poll ────────────────────────────────────────────────────────
func _poll_meter() -> void:
	if not _pipe_rid.is_valid():
		return
	var grid_n: int = int(_sim.get("grid_N"))
	var rows := int(ceili(float(grid_n * grid_n) / 64.0))
	var cells := int(ceili(float(grid_n * grid_n * grid_n) / 256.0))
	# zero accumulators + SAT before the chain
	var zout := PackedByteArray(); zout.resize(OUT_N * 4)
	_rd.buffer_update(_out_rid, 0, OUT_N * 4, zout)
	var zsat := PackedByteArray(); zsat.resize(grid_n * grid_n * grid_n * 4)
	_rd.buffer_update(_sat_rid, 0, zsat.size(), zsat)
	for xi in range(4):
		var m := _chunk.to_float32_array()
		m[0] = float(xi)
		_chunk = m.to_byte_array()
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _pipe_rid)
		_rd.compute_list_bind_uniform_set(cl, _us_rid, 0)
		_rd.compute_list_set_push_constant(cl, _chunk, _chunk.size())
		if xi < 3:
			_rd.compute_list_dispatch(cl, rows, 1, 1)
		else:
			_rd.compute_list_dispatch(cl, cells, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_rd.compute_list_end()
		_rd.submit()
		_rd.sync()

	# the ONLY readback: 64 bytes, at the low cadence (the stutter lesson)
	var data := _rd.buffer_get_data(_out_rid, 0, OUT_N * 4)
	var f := data.to_float32_array()
	var scale := 1.0 / float(grid_n * grid_n * grid_n)
	var total := float(f[0]) * scale
	var rungs := PackedFloat32Array()
	rungs.resize(R)
	for r in range(R):
		rungs[r] = float(f[4 + r]) * scale
	_set_targets(rungs, total)

	# condensation transient: count BH records with nonzero mass in the header
	var n := _count_bh()
	if _last_n_bh >= 0 and n > _last_n_bh:
		_hit_env = 1.0
	_last_n_bh = n


func _count_bh() -> int:
	if _sim == null or not bool(_sim.get("_bh_buf").is_valid()):
		return 0
	var data := _rd.buffer_get_data(_sim.get("_bh_buf"), 0, 576)
	var f := data.to_float32_array()
	if f.size() < 144:
		return 0
	var n := 0
	for slot in range(15):
		var base := 4 + slot * 2
		if float(f[base * 4 + 3]) > 0.0:
			n += 1
	return n


# ── amplitude mapping ─────────────────────────────────────────────────
func _set_targets(rungs: PackedFloat32Array, total: float) -> void:
	# amplitude = rung detail energy normalized by a soft running scale so
	# it stays in [0,1]; smoothed in _update_amps for ~200 ms attack/release.
	var denom := maxf(maxf(_smooth_energy, total) * 4.0, 1e-4)
	for r in range(R):
		_target_amp[r] = clampf(rungs[r] / denom, 0.0, 1.0)
	_smooth_energy += (total - _smooth_energy) * 0.2


func _update_amps(delta: float) -> void:
	var k := 1.0 - exp(-delta / AR_TAU)
	for r in range(R):
		_amp[r] += (_target_amp[r] - _amp[r]) * k
	# hit envelope decay ~0.4 s (fills several frames)
	_hit_env *= exp(-delta / 0.4)


# ── sound rendering ───────────────────────────────────────────────────
func _fill_audio_buffer(_delta: float) -> void:
	if _playback == null:
		return
	var frames: int = _playback.get_frames_available()
	if frames == 0:
		return
	var buf := PackedVector2Array()
	buf.resize(frames)
	# drone: a low subharmonic of the breather deviation mode, mapped
	# musically (see design doc §5 — an ARBITRARY musical scaling).
	var drone_freq := F0 / 4.0
	var dt := 1.0 / MIX_RATE
	var hit_level := _hit_env
	for fr in range(frames):
		var s := 0.0
		for r in range(R):
			var a: float = _amp[r]
			var s0 := sin(_phase[r * 2])
			var s1 := sin(_phase[r * 2 + 1])
			s += a * 0.5 * (s0 + s1) if a > 0.0001 else 0.0
			_phase[r * 2] = fmod(_phase[r * 2] + _freq[r] * TAU * dt, TAU)
			_phase[r * 2 + 1] = fmod(_phase[r * 2 + 1] + _freq[r] * _detune[r] * TAU * dt, TAU)
		# drone subharmonic (breather-coupled level)
		s += 0.06 * _drone_level() * sin(_drone_phase)
		_drone_phase = fmod(_drone_phase + drone_freq * TAU * dt, TAU)
		# percussive hit — short noise burst + pitch drop
		if hit_level > 0.001:
			var nz := randf() * 2.0 - 1.0
			s += bh_hit_gain * hit_level * nz * exp(-6.0 * float(fr) / float(maxi(frames, 1)))
		# mild saturation lifted by the total energy
		var kk := 1.0 + 1.5 * clampf(_smooth_energy * 2.0, 0.0, 1.0)
		s = tanh(s * kk) * master_gain
		buf[fr] = Vector2(s, s)
	_playback.push_buffer(buf)


func _drone_level() -> float:
	return clampf(_smooth_energy * 1.5, 0.0, 1.0)


func _exit_tree() -> void:
	if _out_rid.is_valid() and _rd != null:
		_rd.free_rid(_out_rid)
		_rd.free_rid(_sat_rid)
		_rd.free_rid(_pipe_rid)
		_rd.free_rid(_shader_rid)
		_rd.free_rid(_us_rid)
