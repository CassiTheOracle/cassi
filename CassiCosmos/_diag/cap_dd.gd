extends Node
## Gate-d isolation probe: the decoupled engine boot + the fixed-target
## drain + the frame-time window (the cap battery's gate d).

const N_PARTICLES := 20000
const GRID_N := 64
const DT := 0.01
const RADIUS := 50.0

var _sim: Node
var _phase := 0
var _t0 := 0
var _samples := []

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
	_sim.meshless_mode = false
	_sim.meshless_gravity = false
	_sim.home_window_enabled = false
	_sim.ic_seed = 4242
	_sim.physics_decoupled = true
	_sim._decoupled_active = true
	_sim.reinit()
	_phase = 1
	print("[capdd] engine starting")


func _process(delta: float) -> void:
	if _sim == null:
		return
	if _phase == 1:
		if _sim._physics_engine == null or not _sim._physics_engine.setup_ready():
			if Time.get_ticks_msec() > 90000:
				print("[capdd] FAIL: engine never ready (shaders_ready=%s)" % str(_sim._shaders_ready))
				get_tree().quit(1)
			return
		if not _sim._shaders_ready:
			return
		_t0 = Time.get_ticks_msec()
		_phase = 2
	elif _phase == 2:
		# The parity's direct-record drain (no publish per record).
		if Time.get_ticks_msec() - _t0 > 60000:
			print("[capdd] FAIL: drain timeout executed=%d" % _sim._physics_engine._executed)
			get_tree().quit(1)
		var eng: Object = _sim._physics_engine
		eng.update_bh_header()
		var cl: int = _sim._rd.compute_list_begin()
		eng.record_pending_steps(cl, 2048)
		_sim._rd.compute_list_end()
		eng.readback_telemetry()
		var exec: int = eng._executed
		if exec >= 2048:
			print("[capdd] drain: executed=%d target=2048 wall=%d ms" % [exec, Time.get_ticks_msec() - _t0])
			_sim.playing = true
			_t0 = Time.get_ticks_msec()
			_phase = 3
	elif _phase == 3:
		_samples.append(delta * 1000.0)
		if Time.get_ticks_msec() - _t0 >= 15000:
			_sim.playing = false
			_samples.sort()
			var n := _samples.size()
			var mean := 0.0
			for f in _samples:
				mean += f
			mean /= float(n)
			var p99: float = _samples[int(0.99 * n)]
			var mx: float = _samples[n - 1]
			var ok: bool = p99 <= 3.0 * mean and mx <= 4.0 * mean
			print("[capdd] frame-time: n=%d mean=%.2f p99=%.2f max=%.2f ms -> %s"
					% [n, mean, p99, mx, "PASS" if ok else "FAIL"])
			get_tree().quit(0 if ok else 1)
