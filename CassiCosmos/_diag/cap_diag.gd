extends Node
## CapBattery canary diagnostic (poisson arm) — find the tracked/untracked
## divergence. Reuses the cap_battery mechanics inline.

const N_PARTICLES := 20000
const GRID_N := 64
const DT := 0.01
const RADIUS := 50.0
const CANARY_STEPS := 300
const BATCH := 4

var _sim: Node
var _rd: RenderingDevice
var _tracker
var _phase := 0
var _step := 0
var _cadence := 0
var _next := 0
var _tracked := false
var _ref := {}

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
	_sim.physics_decoupled = false
	_sim.reinit()
	_rd = _sim._rd
	_tracker = EnvelopeTracker.new()
	_tracker.center = Vector3.ZERO
	_tracker.extent = _sim._extents()
	# Gate-a prelude: the tree arm + the uniform field + the meshless re-init.
	_sim.meshless_mode = true
	_sim.meshless_gravity = true
	_sim.reinit()
	_rd = _sim._rd
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var f := PackedFloat32Array()
	f.resize(n3)
	f.fill(1.0)
	_rd.buffer_update(_sim._field_ey, 0, n3 * 4, f.to_byte_array())
	_rd.buffer_update(_sim._field_ei, 0, n3 * 4, f.to_byte_array())
	_sim._meshless_init()
	var np2: int = _sim.N_particles
	var pos2 := PackedFloat32Array()
	pos2.resize(np2 * 4)
	for i in range(np2):
		pos2[i * 4] = 90.0
		pos2[i * 4 + 3] = 1.0
	_rd.buffer_update(_sim._pos_buf, 0, np2 * 16, pos2.to_byte_array())
	_sim._run_physics_steps(1)
	_sim._run_physics_steps(1)
	print("[diag] gate-a prelude done")
	_sim.meshless_mode = false
	_sim.meshless_gravity = false
	_sim.box_scale = 1.0
	_sim._window_center = Vector3.ZERO
	_sim.reinit()
	_rd = _sim._rd
	_tracker.center = Vector3.ZERO
	_tracker.extent = _sim._extents()
	_start_canary(false)


func _process(_d: float) -> void:
	if _sim == null or not _sim._shaders_ready:
		return
	if _phase >= 3:
		_verdict()
		return
	_sim._run_physics_steps(BATCH)
	_step += BATCH
	while _step >= _next:
		_next += CANARY_STEPS
		_cadence += 1
		if _tracked and _cadence == 1:
			_sim._run_physics_steps(BATCH)
			_step += BATCH
		if _cadence >= 2:
			_phase += 1
			if _phase == 1:
				_ref = _snapshot()
				print("[diag] phase1 (off) done")
				_start_canary(true)
			elif _phase == 2:
				var snap := _snapshot()
				print("[diag] phase2 (on) done")
				_dump_state("phase2 end")
				var d := _max_diff(snap["pos"], _ref["pos"])
				print("[diag] pos max-diff = %.6f" % d)
				_phase = 3
			return
		# per-cadence divergence
		if _tracked and _ref.size() > 0:
			var sn := _snapshot()
			var d := _max_diff(sn["pos"], _ref["pos"])
			print("[diag] cadence %d (on) pos-vs-ref = %.6f" % [_cadence, d])


func _start_canary(tracked: bool) -> void:
	_tracked = tracked
	_sim.home_window_enabled = tracked
	_sim.box_scale = 1.0
	_sim._window_center = Vector3.ZERO
	_sim.reinit()
	_rd = _sim._rd
	_tracker.center = Vector3.ZERO
	_tracker.extent = _sim._extents()
	_step = 0
	_cadence = 0
	_next = CANARY_STEPS
	_seed_filling()
	if tracked:
		_apply_tracking()
	_dump_state("canary %s start" % ("on" if tracked else "off"))
	_sim._run_physics_steps(BATCH)
	_step += BATCH
	if _ref.size() > 0:
		var sn := _snapshot()
		var d := _max_diff(sn["pos"], _ref["pos"])
		print("[diag] canary %s start-vs-ref pos diff = %.6f" % ["on" if tracked else "off", d])


func _seed_filling() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 0xC0551E
	var np: int = _sim.N_particles
	var pos := PackedFloat32Array()
	pos.resize(np * 4)
	var vel := PackedFloat32Array()
	vel.resize(np * 4)
	var e: Vector3 = _sim._extents()
	for i in range(np / 2):
		var gx := rng.randf() * 2.0 - 1.0
		var gy := rng.randf() * 2.0 - 1.0
		var gz := rng.randf() * 2.0 - 1.0
		pos[i * 4] = gx * e.x
		pos[i * 4 + 1] = gy * e.y
		pos[i * 4 + 2] = gz * e.z
		pos[i * 4 + 3] = 1.0
		var j := i + np / 2
		pos[j * 4] = -gx * e.x
		pos[j * 4 + 1] = -gy * e.y
		pos[j * 4 + 2] = -gz * e.z
		pos[j * 4 + 3] = 1.0
	_rd.buffer_update(_sim._pos_buf, 0, np * 16, pos.to_byte_array())
	_rd.buffer_update(_sim._vel_buf, 0, np * 16, vel.to_byte_array())
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var z := PackedFloat32Array()
	z.resize(n3)
	_rd.buffer_update(_sim._field_ey, 0, n3 * 4, z.to_byte_array())
	_rd.buffer_update(_sim._field_ei, 0, n3 * 4, z.to_byte_array())
	var zv := PackedFloat32Array()
	zv.resize(n3 * 4)
	_rd.buffer_update(_sim._field_vel, 0, n3 * 16, zv.to_byte_array())
	_sim._window_center = Vector3.ZERO
	_sim.box_scale = 1.0
	var hb: PackedByteArray = _sim._bh_init_bytes
	hb.encode_float(36, e.x); hb.encode_float(40, e.y); hb.encode_float(44, e.z)
	_sim._bh_init_bytes = hb


func _apply_tracking() -> void:
	var np: int = _sim.N_particles
	var pos: PackedFloat32Array = _rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array()
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
	print("[diag] tracker compute: center=(%.6f,%.6f,%.6f) extent=(%.4f,%.4f,%.4f) demand=%.2f re_fits=%d"
			% [_tracker.center.x, _tracker.center.y, _tracker.center.z,
			_tracker.extent.x, _tracker.extent.y, _tracker.extent.z, _tracker.last_demand, _tracker.re_fits])
	_sim._window_center = _tracker.center
	var scl: float = _tracker.extent.x / _sim._extents().x
	_sim.box_scale = maxf(scl, 1e-3)
	var hb: PackedByteArray = _sim._bh_init_bytes
	hb.encode_float(36, _tracker.extent.x)
	hb.encode_float(40, _tracker.extent.y)
	hb.encode_float(44, _tracker.extent.z)
	_sim._bh_init_bytes = hb


func _dump_state(tag: String) -> void:
	var hdr: PackedFloat32Array = _rd.buffer_get_data(_sim._bh_buf, 0, 64).to_float32_array()
	print("[diag] %s: window=(%.6f, %.6f, %.6f) box_scale=%.6f tracker_center=(%.6f,%.6f,%.6f) tracker_ext=(%.4f,%.4f,%.4f) hdr[0..3]=(%.6f,%.6f,%.6f,%.6f) hdr[9..11]=(%.4f,%.4f,%.4f)"
			% [tag, _sim._window_center.x, _sim._window_center.y, _sim._window_center.z,
			_sim.box_scale,
			_tracker.center.x, _tracker.center.y, _tracker.center.z,
			_tracker.extent.x, _tracker.extent.y, _tracker.extent.z,
			hdr[0], hdr[1], hdr[2], hdr[3], hdr[9], hdr[10], hdr[11]])


func _snapshot() -> Dictionary:
	var n3: int = _sim.grid_N * _sim.grid_N * _sim.grid_N
	var np: int = _sim.N_particles
	return {
		"hdr": _rd.buffer_get_data(_sim._bh_buf, 0, 256).to_float32_array(),
		"pos": _rd.buffer_get_data(_sim._pos_buf, 0, np * 16).to_float32_array(),
	}


func _max_diff(a: PackedFloat32Array, b: PackedFloat32Array) -> float:
	var n := mini(a.size(), b.size())
	var m := 0.0
	for i in range(n):
		m = maxf(m, absf(a[i] - b[i]))
	return m


func _verdict() -> void:
	print("[diag] done")
	get_tree().quit(0)
