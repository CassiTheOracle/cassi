extends RefCounted
## Cassi standalone physics engine — Phase 1 of the physics/rendering
## decoupling (godot/space-sim). A self-contained, verbatim port of the
## sim's core GPU physics chain (mass deposit → spectral Poisson FFT →
## two-fluid PDE → BH sector → cell-centered ∇(g·Φ) gradient → Yin/Yang
## dual lattice → cached-acc KDK) that runs on ANY RenderingDevice:
##   - the renderer's GLOBAL RD (main thread, inline — never submit/sync;
##     recorded lists execute via the renderer's frame machinery and
##     readbacks self-stall), or
##   - a LOCAL RD created ON the worker thread that uses it (submit()+sync()
##     when wait=true — the cassi_tree_worker.gd pattern).
##
## The engine touches NOTHING outside itself: no class_name, no globals,
## no renderer access. It is safe to instantiate while cassi_sim.gd is
## loaded (no name collisions — every member is `_`-prefixed or class-local).
##
## NOT ported (phase-2 scope): the meshless Voronoi arm, the tree build/
## walk shaders (already their own worker), the instancer, q-histogram,
## field display and BH lensing. The mode-5 nbody TREE SEAM is preserved:
## run_steps() accepts an optional per-particle tree-gradient array, which
## is uploaded into the nbody set-1 binding-3 buffer when non-empty (empty
## leaves the buffer as-is). The engine's meshless_mode/meshless_gravity
## flags gate the same chain branches they gate in the sim (tree mode
## skips the Poisson chain + gradient passes and forces the nbody to
## eff mode 5.0), but the tree gradient itself must be supplied by the
## caller — the engine never runs the tree shaders.
##
## Threading contract (verified Godot 4.7 constraints):
## - A local RD must be CREATED ON THE WORKER THREAD that uses it.
## - RDShaderFile loading is NOT thread-safe: pass pre-extracted SPIR-V
##   objects via cfg.spirv (path → RDShaderSPIRV); the engine falls back
##   to load() only when setup() runs on the main thread and no SPIR-V
##   was provided.
## - free() frees buffers/pipes/shaders + (when owns_rd) the device, but
##   NEVER the uniform sets (free_rid on sets fails from a worker thread
##   — "Attempted to free invalid ID"; the device free tears them down).
##   NOTE: the design brief names this method `free()`, but GDScript 4.7
##   hard-blocks a script method named `free()` on RefCounted (the native
##   RefCounted::free() shadows it — verified empirically: the call hits
##   the native method and errors "Can't free a RefCounted object"). The
##   cleanup API is therefore `shutdown()`.

const PHI: float = 1.618033988749895
const PHI_INV3: float = (PHI - 1.0) / (PHI + 1.0)   # φ⁻³ = attractor π/ρ ≈ 0.236068
const PHI_INV2: float = 0.3819660112501051  # φ⁻² — q decoherence threshold
const PHI_6: float = PHI * PHI * PHI * PHI * PHI * PHI  # φ⁶ ≈ 17.94427191
const PI_CLAMP_MAX: float = 0.72  # (π/ρ) upper clamp (stability; telemetry counts hits)
const LN2: float = 0.6931471805599453  # ln 2 — degenerate rainbow v_scale fallback (0.95·ln2)
# Tree-arm force calibration G_tree = G_N·ML_TREE_G_SCALE rides bh[3].w
# (float 60 — a free header slot, NOT the nbody PC). 1.0 off-tree (river
# bit-identical). Ported verbatim so the header encode matches the sim.
const ML_TREE_G_SCALE := 0.03

# ═══════════════════════════════════════════════════════════════════════
# Config — mirrors the sim's exports (same names; setup() reads these keys)
# ═══════════════════════════════════════════════════════════════════════
var grid_N: int = 64              # field grid resolution (per dim)
var N_particles: int = 2500000    # N-body particle count
var dt: float = 0.001             # simulation timestep
var xi: float = 17.94427191       # φ⁶ — Cassi Qi coupling
var softening: float = 0.1        # gravity softening length (ε² = softening²)
var cluster_radius: float = 50.0  # initial cluster scale radius
var num_clusters: int = 1
var cluster_separation: float = 60.0
var merger_speed: float = 2.0
var source_strength: float = 0.0  # PIC mass deposit drives field (0 = off)
var qi_condensation_threshold: float = 0.5
var bh_acc_rate: float = 0.01
var bh_max_age: float = 0.0       # 0 = immortal
var black_holes_enabled: bool = false
var gravity_mode: int = 0         # 0=River 1=Heuristic 2=Plummer 3=River self 4=RealSim
var realsim_drag: float = 0.5
var realsim_viscosity: float = 0.3
var realsim_friction: float = 0.01
var river_calibrate_gn: bool = false
var river_pi_ref: float = PHI_INV3
var river_q_ref: float = 0.0
var field_attractor_init: bool = false
var freeze_field: bool = false
var initial_radius_fraction: float = 0.9
var initial_condition: int = 0    # 0=Plummer 1=Gaussian 2=Uniform
var initial_v_circ_factor: float = 0.85
var box_aspect: Vector3 = Vector3(1.618, 1.0, 2.618)
var box_scale: float = 1.0
var gradient_order: int = 2
var dual_grid: bool = true
var multi_rung_seed: bool = false
var multi_rung_count: int = 3
var multi_rung_amp: float = 0.2
var multi_rung_base_scale: float = 1.0
var meshless_mode: bool = true    # gates the nbody/poisson seams only (the
var meshless_gravity: bool = true #  meshless solver itself is NOT ported)
var mode: int = 0                 # display mode (shared PC slot 7; render-side but encoded in PCs)

# Engine plumbing (cfg keys): rd, rd_global, owns_rd, seed, spirv
var _rd: RenderingDevice = null
var _rd_global: bool = true       # true = renderer's global RD (never submit/sync)
var _owns_rd: bool = false        # true = engine frees the device in free()
var _seed_set: bool = false
var _seed: int = 0
var _cfg_spirv: Dictionary = {}   # path → RDShaderSPIRV (pre-extracted on main thread)
var _freed := false

# ═══════════════════════════════════════════════════════════════════════
# GPU resources (physics side only)
# ═══════════════════════════════════════════════════════════════════════
# — field grid buffers (SET 0 of cassi_two_fluid.glsl) —
var _field_ey: RID; var _field_ei: RID
var _field_q: RID;  var _field_vel: RID
# — Poisson solver (SET 0 of cassi_poisson.glsl) —
var _fft_buf: RID      # vec2 per cell — FFT workspace; real part = Φ after solve
var _tel_buf: RID      # gravity telemetry: [pi_hi, pi_lo, rho_guard, q_min, q_max, pi_min, pi_max, samples]
# — Cell-centered ∇(g·Φ) field (SET 0 bindings 7/8 of cassi_nbody_gravity.glsl) —
var _grad_buf: RID     # vec4 per cell — gradient pass output, river-arm input
var _grad_buf2: RID    # dual-lattice ∇(g·Φ) (always allocated so dual_grid stays LIVE)
# — particle buffers (SET 1) —
var _pos_buf: RID; var _vel_buf: RID; var _acc_buf: RID
# — auxiliary buffers (SET 2) —
var _cluster_buf: RID
var _bh_buf: RID
var _mass_density_buf: RID
# — mode-5 tree seam: nbody SET 1 binding 3 (the buffer the nbody reads) —
var _tree_grad: RID    # vec4[max(N_particles,1)] — per-particle tree ∇Φ_g (uploaded via run_steps)
# — shaders and pipelines (physics side only) —
var _two_fluid_shader: RID;  var _two_fluid_pipe: RID
var _nbody_shader: RID;      var _nbody_pipe: RID
var _poisson_shader: RID;    var _poisson_pipe: RID
var _mass_deposit_shader: RID; var _mass_deposit_pipe: RID
var _cond_shader: RID;       var _cond_pipe: RID
var _bh_int_shader: RID;     var _bh_int_pipe: RID
var _us_two_0: RID
var _us_mass_dep_0: RID
var _us_nbody_0: RID; var _us_nbody_1: RID; var _us_nbody_2: RID
var _us_poisson_0: RID
var _us_cond_0: RID; var _us_cond_1: RID
var _us_bh_int_0: RID; var _us_bh_int_1: RID
var _ready := false
var _cond_step_counter: int = 0

# — pre-allocated push-constant byte buffers (hitch-free: no per-step allocs) —
var _pc_bytes: PackedByteArray        # shared 11-float PC (kept for verbatim fidelity)
var _nbody_pc_bytes: PackedByteArray  # nbody PC (15 floats: 11 shared + pass_mode + 3 RealSim)
var _two_fluid_pc_bytes: PackedByteArray  # two-fluid PC (14 floats: 11 shared + extent_x/y/z)
var _md_pc_bytes: PackedByteArray     # mass deposit PC (8 floats: N, particle_N, extent_x/y/z, off_x/y/z)
var _bh_int_pc_bytes: PackedByteArray # BH integrate PC (4 floats)
var _cond_pc_bytes: PackedByteArray   # condensation PC (4 floats)
var _poisson_pc_bytes: PackedByteArray  # poisson PC (7 floats: N, axis, dir, mode, extent_x/y/z)
var _bh_init_bytes: PackedByteArray   # BH header init (36 vec4s = 576 B)
var _tel_reset_bytes: PackedByteArray # gravity telemetry reset (kept for reference; the per-step
                                      #  reset runs on the GPU in the poisson clear pass)

# — step state —
var _time: float = 0.0
var _step_count: int = 0
var _grav_warmup: bool = false  # one-shot acc-cache warm-up before the first KDK step
var _gn_eff: float = 1.0        # effective river G after calibration
var _total_init_mass: float = 0.0
var _local_pending := false     # local RD: a list was submitted but not yet synced

# — telemetry (mirrors the sim's diagnostic members; filled by
# readback_telemetry() from the gravity telemetry buffer) —
var _q_mean: float = 0.0
var _q_min: float = 0.0
var _q_max: float = 0.0
var _pi_min: float = 0.0
var _pi_max: float = 0.0
var _pi_sat_hi_frac: float = 0.0
var _pi_sat_lo_frac: float = 0.0
var _rho_guard_hits: int = 0
var _eps_mean: float = 0.0
var _hubble: float = 0.0
var _scale_factor: float = 1.0

# — threaded runner (the cassi_tree_worker.gd pattern: local RD created on
# the worker, SPIR-V loaded on the main thread, sets left to the device) —
var _thread: Thread = null
var _thread_started := false
var _running := false
var _job_sem: Semaphore = null
var _done_sem: Semaphore = null
var _setup_sem: Semaphore = null
var _job_mutex: Mutex = null
var _res_mutex: Mutex = null
var _job: Dictionary = {}
var _job_pending := false
var _res_result: Dictionary = {}
var _res_gen := 0
var _consumed_gen := 0
var _wait_next := true      # first submit after start blocks (fresh-bootstrap)
var _executed := 0          # worker-side cumulative executed step count


# ═══════════════════════════════════════════════════════════════════════
# API
# ═══════════════════════════════════════════════════════════════════════

## Build the engine on the RenderingDevice given in cfg.rd. cfg keys use
## the SAME names as the sim's members (grid_N, N_particles, dt, xi,
## softening, box_aspect, ..., meshless_mode, meshless_gravity, mode) plus
##   rd        : RenderingDevice (REQUIRED) — global or worker-created local
##   rd_global : bool, default true — true = never submit/sync (global RD)
##   owns_rd   : bool, default false — true = free() also frees the device
##   seed      : int, optional — fixed RNG seed for the ICs (both field and
##               particles); omit for the sim's default (randomized) init
##   spirv     : Dictionary path→RDShaderSPIRV, optional — pre-extracted
##               SPIR-V (REQUIRED when setup() runs off the main thread;
##               RDShaderFile loading is not thread-safe)
## Returns true when the full physics chain is ready.
func setup(cfg: Dictionary) -> bool:
	if _freed:
		return false
	_rd = cfg.get("rd") as RenderingDevice
	if _rd == null:
		push_error("[PhysicsEngine] setup: cfg.rd is null (no RenderingDevice)")
		return false
	_rd_global = bool(cfg.get("rd_global", true))
	_owns_rd = bool(cfg.get("owns_rd", false))
	var s = cfg.get("seed", null)
	if s != null:
		_seed_set = true
		_seed = int(s)
	var sp = cfg.get("spirv", null)
	if sp is Dictionary:
		_cfg_spirv = sp
	# ── read the physics config (same names as the sim's exports) ──
	grid_N = int(cfg.get("grid_N", grid_N))
	N_particles = int(cfg.get("N_particles", N_particles))
	dt = float(cfg.get("dt", dt))
	xi = float(cfg.get("xi", xi))
	softening = float(cfg.get("softening", softening))
	cluster_radius = float(cfg.get("cluster_radius", cluster_radius))
	num_clusters = int(cfg.get("num_clusters", num_clusters))
	cluster_separation = float(cfg.get("cluster_separation", cluster_separation))
	merger_speed = float(cfg.get("merger_speed", merger_speed))
	source_strength = float(cfg.get("source_strength", source_strength))
	qi_condensation_threshold = float(cfg.get("qi_condensation_threshold", qi_condensation_threshold))
	bh_acc_rate = float(cfg.get("bh_acc_rate", bh_acc_rate))
	bh_max_age = float(cfg.get("bh_max_age", bh_max_age))
	black_holes_enabled = bool(cfg.get("black_holes_enabled", black_holes_enabled))
	gravity_mode = int(cfg.get("gravity_mode", gravity_mode))
	realsim_drag = float(cfg.get("realsim_drag", realsim_drag))
	realsim_viscosity = float(cfg.get("realsim_viscosity", realsim_viscosity))
	realsim_friction = float(cfg.get("realsim_friction", realsim_friction))
	river_calibrate_gn = bool(cfg.get("river_calibrate_gn", river_calibrate_gn))
	river_pi_ref = float(cfg.get("river_pi_ref", river_pi_ref))
	river_q_ref = float(cfg.get("river_q_ref", river_q_ref))
	field_attractor_init = bool(cfg.get("field_attractor_init", field_attractor_init))
	freeze_field = bool(cfg.get("freeze_field", freeze_field))
	initial_radius_fraction = float(cfg.get("initial_radius_fraction", initial_radius_fraction))
	initial_condition = int(cfg.get("initial_condition", initial_condition))
	initial_v_circ_factor = float(cfg.get("initial_v_circ_factor", initial_v_circ_factor))
	var ba = cfg.get("box_aspect", null)
	if ba is Vector3:
		box_aspect = ba
	elif ba is Vector2:
		box_aspect = Vector3(ba.x, ba.y, box_aspect.z)
	box_scale = float(cfg.get("box_scale", box_scale))
	gradient_order = int(cfg.get("gradient_order", gradient_order))
	dual_grid = bool(cfg.get("dual_grid", dual_grid))
	multi_rung_seed = bool(cfg.get("multi_rung_seed", multi_rung_seed))
	multi_rung_count = int(cfg.get("multi_rung_count", multi_rung_count))
	multi_rung_amp = float(cfg.get("multi_rung_amp", multi_rung_amp))
	multi_rung_base_scale = float(cfg.get("multi_rung_base_scale", multi_rung_base_scale))
	meshless_mode = bool(cfg.get("meshless_mode", meshless_mode))
	meshless_gravity = bool(cfg.get("meshless_gravity", meshless_gravity))
	mode = int(cfg.get("mode", mode))
	# ── build the chain ──
	_setup_buffers()
	_setup_shaders()
	if not _ready:
		var missing := []
		if not _two_fluid_pipe.is_valid(): missing.append("two_fluid")
		if not _nbody_pipe.is_valid(): missing.append("nbody")
		if not _poisson_pipe.is_valid(): missing.append("poisson")
		if not _mass_deposit_pipe.is_valid(): missing.append("mass_deposit")
		if not _cond_pipe.is_valid(): missing.append("condensation")
		if not _bh_int_pipe.is_valid(): missing.append("bh_integrate")
		push_error("[PhysicsEngine] setup failed: pipes missing = %s (spirv dict size=%d)" % [str(missing), _cfg_spirv.size()])
		return false
	_init_field()
	_init_particles()
	_apply_gravity_calibration()
	_grav_warmup = true  # fill the acc cache with a fresh force before step 1
	print("[PhysicsEngine] ready — grid=%d^3 particles=%d xi=%.5f (phi6=%.5f) rd_global=%s" % [
		grid_N, N_particles, xi, PHI_6, "true" if _rd_global else "false"])
	return true


## Record the full per-step chain n times. On a global RD the list is
## executed by the renderer's frame machinery (NEVER submit/sync here); on
## a local RD it is submitted, and synced when wait=true. tree_grad, when
## non-empty (exactly max(N_particles,1)*4 floats), is uploaded into the
## mode-5 nbody tree-gradient buffer first; empty leaves the buffer as-is.
func run_steps(n: int, wait := true, tree_grad: PackedFloat32Array = PackedFloat32Array()) -> void:
	if _rd == null or not _ready:
		return
	# BH header (count/G_N/extent/toggle/dual) — constant across the
	# frame's steps; buffer_update must run BEFORE compute_list_begin.
	# bh[3].x = black_holes_enabled (float 48), bh[3].y = dual_grid (52),
	# bh[3].z = gradient_order (56), bh[3].w = tree G_SCALE (60),
	# bh[1].xyz = the dual-grid offset extent_i/N (floats 16/20/24).
	_bh_init_bytes.encode_float(48, 1.0 if black_holes_enabled else 0.0)
	_bh_init_bytes.encode_float(52, 1.0 if dual_grid else 0.0)
	_bh_init_bytes.encode_float(56, float(gradient_order))
	_bh_init_bytes.encode_float(60, ML_TREE_G_SCALE if (meshless_mode and meshless_gravity) else 1.0)
	var off_dual: Vector3 = _extents() / float(grid_N)
	_bh_init_bytes.encode_float(16, off_dual.x)
	_bh_init_bytes.encode_float(20, off_dual.y)
	_bh_init_bytes.encode_float(24, off_dual.z)
	_rd.buffer_update(_bh_buf, 0, _bh_init_bytes.size(), _bh_init_bytes)
	# Mode-5 tree seam: an external tree arm uploads the per-particle ∇Φ_g
	# via this argument (the sim's own size-guarded upload contract).
	if tree_grad.size() > 0 and tree_grad.size() == maxi(N_particles, 1) * 4:
		_rd.buffer_update(_tree_grad, 0, tree_grad.size() * 4, tree_grad.to_byte_array())
	var cl := _rd.compute_list_begin()
	for _s in range(n):
		_step_dispatches(cl)
	_rd.compute_list_end()
	if not _rd_global:
		_rd.submit()
		_local_pending = true
		if wait:
			_rd.sync()
			_local_pending = false


## The mirror state the render side will consume (phase 2): positions,
## velocities, the Qi field and the solved potential, plus the sim time.
func readback_snapshot() -> Dictionary:
	if _rd == null or not _ready:
		return {}
	if not _rd_global and _local_pending:
		_rd.sync()   # local RD: execute any un-synced submission before reading
		_local_pending = false
	var nc: int = grid_N * grid_N * grid_N
	var pos := _rd.buffer_get_data(_pos_buf, 0, maxi(N_particles, 1) * 16).to_float32_array()
	var vel := _rd.buffer_get_data(_vel_buf, 0, maxi(N_particles, 1) * 16).to_float32_array()
	var fq := _rd.buffer_get_data(_field_q, 0, nc * 4).to_float32_array()
	var fft := _rd.buffer_get_data(_fft_buf, 0, nc * 8).to_float32_array()
	# Potential = the real part of the FFT workspace (vec2 per cell, Φ in .x).
	var pot := PackedFloat32Array()
	pot.resize(nc)
	var nf := mini(fft.size(), nc * 2)
	for i in range(nf / 2):
		pot[i] = fft[i * 2]
	return {
		"pos": pos, "vel": vel, "field_q": fq, "pot": pot, "t": _time,
	}


## The sim-UI telemetry (decoupled mode): the gravity telemetry buffer's
## saturation counters + q/π/ρ range at particles + the strided field-q
## mean — decoded exactly as the sim's _render_frame does — plus the
## eps/hubble/scale-factor members (inert defaults there too) and the
## effective river G after calibration.
func readback_telemetry() -> Dictionary:
	if _rd == null or not _ready:
		return {}
	if not _rd_global and _local_pending:
		_rd.sync()
		_local_pending = false
	var tel := _rd.buffer_get_data(_tel_buf, 0, 32)
	if tel.size() >= 32:
		_pi_sat_hi_frac = float(tel.decode_u32(0))
		_pi_sat_lo_frac = float(tel.decode_u32(4))
		_rho_guard_hits = int(tel.decode_u32(8))
		_q_min = tel.decode_float(12)
		_q_max = tel.decode_float(16)
		_pi_min = tel.decode_float(20)
		_pi_max = tel.decode_float(24)
		# Sample count from the GPU (tel[7]): the shader reports the true
		# number of chord_g_at evaluations per step (7 per river kick ×
		# 2 KDK kicks per particle). Heuristic mode reports 0 → 1.
		var samples := maxi(int(tel.decode_u32(28)), 1)
		_pi_sat_hi_frac /= samples
		_pi_sat_lo_frac /= samples
	var nc: int = grid_N * grid_N * grid_N
	var q_data := _rd.buffer_get_data(_field_q, 0, nc * 4)
	if q_data.size() > 0:
		var qf := q_data.to_float32_array()
		var q_sum := 0.0
		# Strided sum — the sim's _render_frame recipe (1-in-16 subsample).
		for qi in range(0, qf.size(), 16):
			q_sum += qf[qi]
		_q_mean = q_sum * 16.0 / maxf(qf.size(), 1)
	return {
		"q_mean": _q_mean, "q_min": _q_min, "q_max": _q_max,
		"pi_min": _pi_min, "pi_max": _pi_max,
		"pi_sat_hi_frac": _pi_sat_hi_frac, "pi_sat_lo_frac": _pi_sat_lo_frac,
		"rho_guard_hits": _rho_guard_hits,
		"eps_mean": _eps_mean, "hubble": _hubble, "scale_factor": _scale_factor,
		"gn_eff": _gn_eff,
	}


# ═══════════════════════════════════════════════════════════════════════
# Threaded runner (the cassi_tree_worker.gd pattern)
# ═══════════════════════════════════════════════════════════════════════

## Start the engine on a dedicated worker thread with its own local
## RenderingDevice (created ON the worker — the verified Godot 4.7
## constraint). MAIN thread: loads the 6 physics shader FILES and passes
## the extracted SPIR-V into the worker via cfg.spirv (RDShaderFile loading
## is not thread-safe); the worker then runs setup() ITSELF (IC generation
## + buffer fills are thread-safe on the worker). The first submit_steps()
## blocks on setup + completion (the bootstrap — the caller gets an
## immediate snapshot); later submits are non-blocking with target-count
## coalescing. stop_threaded() joins the worker, whose exit path shuts the
## engine down on the worker (worker-side RID frees — no invalid frees).
## Reinit = stop_threaded() + start_threaded(new cfg).
func start_threaded(cfg: Dictionary) -> bool:
	stop_threaded()
	_freed = false  # allow a fresh setup() after a previous shutdown
	# Load the physics shaders HERE (main thread): resource loading is not
	# thread-safe; the worker receives the extracted SPIR-V.
	var spirv := {}
	for p in [
			"res://compute/cassi_two_fluid.glsl",
			"res://compute/cassi_mass_deposit.glsl",
			"res://compute/cassi_poisson.glsl",
			"res://compute/cassi_nbody_gravity.glsl",
			"res://compute/cassi_condensation.glsl",
			"res://compute/cassi_bh_integrate.glsl"]:
		var sf := load(p) as RDShaderFile
		if sf == null or sf.get_spirv() == null:
			push_error("[PhysicsEngine] start_threaded: shader load failed: " + p)
			return false
		spirv[p] = sf.get_spirv()
	var wcfg: Dictionary = cfg.duplicate()
	wcfg["spirv"] = spirv
	_job_sem = Semaphore.new()
	_done_sem = Semaphore.new()
	_setup_sem = Semaphore.new()
	_job_mutex = Mutex.new()
	_res_mutex = Mutex.new()
	_res_result = {}
	_res_gen = 0
	_consumed_gen = 0
	_job_pending = false
	_wait_next = true
	_executed = 0
	_running = true
	_thread = Thread.new()
	_thread_started = _thread.start(_threaded_main.bind(wcfg)) == OK
	if not _thread_started:
		push_warning("[PhysicsEngine] thread spawn failed — threaded runner stays offline")
		_running = false
		return false
	return true


## Stage a step-count TARGET and fire-and-forget (after the bootstrap).
## The target is CUMULATIVE: the worker executes target − (its executed so
## far) steps, so a new job replaces a pending unconsumed one (newest
## target wins) and steps are never silently lost. block=true waits for
## this job's completion and returns the fresh publish (the synchronous
## path the sim's _run_physics_steps uses). The bootstrap (first submit
## after start) always blocks and returns the immediate snapshot.
func submit_steps(target: int, block := false) -> Dictionary:
	if not _thread_started:
		return {}
	if _wait_next:
		# Bootstrap: block until the worker finished setup AND this job.
		_wait_next = false
		_setup_sem.wait()
		if not _ready:
			return {}
		_job_mutex.lock()
		_job = {"target": target}
		_job_pending = true
		_job_mutex.unlock()
		_job_sem.post()
		return _wait_executed(target)   # the bootstrap always blocks
	_job_mutex.lock()
	_job = {"target": target}
	_job_pending = true
	_job_mutex.unlock()
	_job_sem.post()
	if block:
		return _wait_executed(target)
	return {}


## Block until a publish with executed >= target arrives and return the
## freshest such publish. Robust against leftover done-posts from coalesced
## async jobs: the publish is re-checked after every wakeup, so a stale
## post just causes one extra wait round.
func _wait_executed(target: int) -> Dictionary:
	while true:
		var r := _consume_latest()
		if int(r.get("executed", -1)) >= target:
			return r
		_done_sem.wait()
	return {}   # unreachable — the loop only exits via the return above


## Non-blocking: the freshest UNCONSUMED completed publish.
func poll() -> Dictionary:
	return _consume_latest()


## Stop the threaded runner (reinit / exit). MAIN thread: joins the worker,
## whose exit path shuts the engine down on the worker (local-RD frees —
## never uniform sets, per the threading contract).
func stop_threaded() -> void:
	if _thread != null and _thread_started:
		_running = false
		_job_sem.post()   # wake the worker so it observes _running == false
		_thread.wait_to_finish()
		_thread_started = false
		_thread = null
		_rd = null        # the worker's shutdown() already freed the device
		_ready = false
		_executed = 0


## The worker thread: create the local RD, run setup() on THIS thread (IC
## generation + buffer fills are thread-safe here), then loop on jobs.
func _threaded_main(wcfg: Dictionary) -> void:
	var local_rd: RenderingDevice = RenderingServer.create_local_rendering_device()
	if local_rd == null:
		push_error("[PhysicsEngine] worker: local RD create failed")
		_setup_sem.post()
		return
	wcfg["rd"] = local_rd
	wcfg["rd_global"] = false
	wcfg["owns_rd"] = true
	var ok := setup(wcfg)
	_setup_sem.post()
	if ok:
		while true:
			_job_sem.wait()
			if not _running:
				break
			_job_mutex.lock()
			var job := _job
			_job_pending = false
			_job_mutex.unlock()
			_threaded_run_job(job)
			_done_sem.post()
	shutdown()  # worker-side: frees buffers/pipes/shaders + the local RD

## One job: run up to (target − executed) steps, snapshot + telemetry, and
## publish the cumulative executed count + the mirror data.
func _threaded_run_job(job: Dictionary) -> void:
	var target := int(job.get("target", _executed))
	if target > _executed:
		var steps := target - _executed
		run_steps(steps, true)  # wait=true → submit+sync on the local RD
		_executed += steps
	var snap := readback_snapshot()
	var tel := readback_telemetry()
	_res_mutex.lock()
	_res_result = {
		"executed": _executed,
		"snapshot": snap,
		"telemetry": tel,
		"t": snap.get("t", _time),
		"step_count": _step_count,
	}
	_res_gen += 1
	_res_mutex.unlock()


func _consume_latest() -> Dictionary:
	_res_mutex.lock()
	var gen := _res_gen
	var res := _res_result
	_res_mutex.unlock()
	if gen > _consumed_gen and not res.is_empty():
		_consumed_gen = gen
		return res
	return {}


## Free buffers/pipes/shaders (NOT the uniform sets — see the header
## threading contract) and, when owns_rd, the device itself.
##
## NOTE — API deviation from the design brief, forced by Godot 4.7: the
## brief specifies `func free()`, but GDScript hard-blocks a script method
## named `free()` on RefCounted — the native RefCounted::free() shadows it
## unconditionally (empirically verified: the call dispatches to the native
## method and errors "Can't free a RefCounted object", so the script method
## never runs). The cleanup API is therefore `shutdown()`. As a safety net
## the engine ALSO frees on NOTIFICATION_PREDELETE, so a consumer that just
## drops its last reference still releases the GPU resources (on whichever
## thread performs the final unref).
func shutdown() -> void:
	if _freed:
		return
	_freed = true
	if _rd == null:
		return
	for rid in [
			_two_fluid_pipe, _nbody_pipe, _poisson_pipe, _mass_deposit_pipe,
			_cond_pipe, _bh_int_pipe,
			_two_fluid_shader, _nbody_shader, _poisson_shader,
			_mass_deposit_shader, _cond_shader, _bh_int_shader,
			_field_ey, _field_ei, _field_q, _field_vel,
			_fft_buf, _tel_buf, _grad_buf, _grad_buf2,
			_pos_buf, _vel_buf, _acc_buf, _cluster_buf, _bh_buf,
			_mass_density_buf, _tree_grad]:
		if rid.is_valid():
			_rd.free_rid(rid)
	if _owns_rd:
		_rd.free()
		_rd = null
	_ready = false


# ═══════════════════════════════════════════════════════════════════════
# Host-side helpers (ported verbatim from cassi_sim.gd)
# ═══════════════════════════════════════════════════════════════════════

## Per-axis box half-extents — the single source of truth for the box
## geometry (bh[2].yzw header slots, the Poisson/mass-deposit/two-fluid
## push constants, IC truncation — all derive from this).
func _extents() -> Vector3:
	return Vector3(box_aspect.x, box_aspect.y, box_aspect.z) * (cluster_radius * 1.5) * maxf(box_scale, 1e-3)


func _extent_min() -> float:
	var e := _extents()
	return minf(minf(e.x, e.y), e.z)


func _barrier(cl: int) -> void:
	_rd.compute_list_add_barrier(cl)


func _shader_create(path: String) -> RID:
	var spirv: RDShaderSPIRV = null
	if _cfg_spirv.has(path):
		spirv = _cfg_spirv[path] as RDShaderSPIRV
	if spirv == null:
		# Fallback: direct resource load — MAIN THREAD ONLY (RDShaderFile
		# loading is not thread-safe; pass cfg.spirv for worker setup).
		var sf := load(path) as RDShaderFile
		if sf == null:
			push_error("[PhysicsEngine] Shader not found: " + path)
			return RID()
		spirv = sf.get_spirv()
	if spirv == null:
		push_error("[PhysicsEngine] SPIR-V compile failed: " + path)
		return RID()
	return _rd.shader_create_from_spirv(spirv)


func _uniform_storage(binding: int, buf: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _erf_approx(x: float) -> float:
	# Abramowitz & Stegun 7.1.26 erf approximation (the sim's recorded
	# replacement for the missing Godot built-in).
	var t: float = 1.0 / (1.0 + 0.3275911 * x)
	var poly: float = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
	return 1.0 - poly * exp(-x * x)


## Fibonacci-sphere direction (deterministic, de-resonant — the same
## distribution the multi-cluster placement uses; the multi-rung seeding's
## mode directions, CASCADE_GRID.md §3.3).
func _fib_sphere_dir(i: int, n: int) -> Vector3:
	var p := acos(1.0 - 2.0 * (float(i) + 0.5) / float(n))
	var t := PI * (1.0 + sqrt(5.0)) * float(i)
	return Vector3(sin(p) * cos(t), sin(p) * sin(t), cos(p))


# ═══════════════════════════════════════════════════════════════════════
# Buffer / shader setup (physics side only — ported verbatim)
# ═══════════════════════════════════════════════════════════════════════

func _setup_buffers() -> void:
	# The spectral Poisson FFT is radix-2 Stockham: grid_N must be a power
	# of 2 in [64, 256]; non-powers round UP (clamped at 256).
	var n2 := 64
	while n2 < grid_N:
		n2 *= 2
	if n2 > 256:
		n2 = 256
	if n2 != grid_N:
		var old_N := grid_N
		grid_N = n2
		push_warning("[PhysicsEngine] grid_N=%d is not a power of 2 (radix-2 FFT); using %d" % [old_N, grid_N])
	var N := grid_N
	var nc := N * N * N
	var nf := nc * 4

	# SET 0 — Field grid
	_field_ey  = _rd.storage_buffer_create(nf)
	_field_ei  = _rd.storage_buffer_create(nf)
	_field_q   = _rd.storage_buffer_create(nf)
	_field_vel = _rd.storage_buffer_create(nc * 16)
	# Poisson solver: complex FFT workspace (vec2/cell) + gravity telemetry
	_fft_buf  = _rd.storage_buffer_create(nc * 8)
	_tel_buf  = _rd.storage_buffer_create(32)
	# SET 1 — Particles
	var ps := N_particles * 16
	_pos_buf = _rd.storage_buffer_create(ps)
	_vel_buf = _rd.storage_buffer_create(ps)
	_acc_buf = _rd.storage_buffer_create(ps)

	# SET 2 — BH data + sim globals (36 vec4s = 576 bytes: 4-vec4 header +
	# 15 BH records × 2 vec4s). bh[2] = (cluster_radius, extent_x/y/z).
	_bh_buf = _rd.storage_buffer_create(576)
	var ext_hdr := _extents()
	var bh_init_f := PackedFloat32Array([
		0.0, 0.0, 0.0, float(N_particles),
		0.0, 0.0, 0.0, 1.0,
		cluster_radius, ext_hdr.x, ext_hdr.y, ext_hdr.z,
		0.0, 0.0, 0.0, 0.0,
	])
	# Zero the FULL 576-byte buffer (storage buffers are NOT zero-initialized
	# on allocator reuse; the nbody shader reads bh[4..] in every gravity mode).
	var bh_full := PackedFloat32Array()
	bh_full.resize(576 / 4)
	for i in range(16):
		bh_full[i] = bh_init_f[i]
	_bh_init_bytes = bh_full.to_byte_array()
	_rd.buffer_update(_bh_buf, 0, _bh_init_bytes.size(), _bh_init_bytes)
	# Cluster center positions + masses (64-vec4 cap — keep in sync with
	# ClusterBuf in cassi_nbody_gravity.glsl, set 2 binding 1).
	_cluster_buf = _rd.storage_buffer_create(64 * 4 * 4)
	# Mass density grid (float per cell — float atomicAdd deposit)
	_mass_density_buf = _rd.storage_buffer_create(nc * 4)
	# Cell-centered ∇(g·Φ) field (vec4 per cell — rebuilt every step)
	_grad_buf = _rd.storage_buffer_create(nc * 16)
	# Dual-lattice ∇(g·Φ) (always allocated so dual_grid stays a LIVE toggle)
	_grad_buf2 = _rd.storage_buffer_create(nc * 16)
	# Mode-5 tree seam: per-particle tree gradient (nbody set 1 binding 3).
	# Zeroed once at setup so an unused seam reads zero force instead of
	# stale allocator memory; run_steps uploads when a gradient is supplied.
	_tree_grad = _rd.storage_buffer_create(maxi(N_particles, 1) * 16)
	var tz := PackedFloat32Array()
	tz.resize(maxi(N_particles, 1) * 4)
	_rd.buffer_update(_tree_grad, 0, tz.size() * 4, tz.to_byte_array())

	# Pre-allocate push-constant byte buffers (hitch-free pattern)
	_pc_bytes = PackedByteArray(); _pc_bytes.resize(11 * 4)
	_nbody_pc_bytes = PackedByteArray(); _nbody_pc_bytes.resize(15 * 4)
	_two_fluid_pc_bytes = PackedByteArray(); _two_fluid_pc_bytes.resize(14 * 4)
	_md_pc_bytes = PackedByteArray(); _md_pc_bytes.resize(8 * 4)
	_bh_int_pc_bytes = PackedByteArray(); _bh_int_pc_bytes.resize(4 * 4)
	_cond_pc_bytes = PackedByteArray(); _cond_pc_bytes.resize(4 * 4)
	_poisson_pc_bytes = PackedByteArray(); _poisson_pc_bytes.resize(7 * 4)
	# Telemetry reset (kept for reference; the per-step reset runs on the GPU
	# in the poisson clear pass so chained steps stay independent)
	_tel_reset_bytes = PackedFloat32Array([0.0, 0.0, 0.0, INF, 0.0, INF, 0.0, 0.0]).to_byte_array()


func _setup_shaders() -> void:
	# Two-fluid PDE solver
	_two_fluid_shader = _shader_create("res://compute/cassi_two_fluid.glsl")
	if _two_fluid_shader.is_valid():
		_two_fluid_pipe = _rd.compute_pipeline_create(_two_fluid_shader)
	# N-body gravity
	_nbody_shader = _shader_create("res://compute/cassi_nbody_gravity.glsl")
	if _nbody_shader.is_valid():
		_nbody_pipe = _rd.compute_pipeline_create(_nbody_shader)
	# Spectral Poisson solver (∇²Φ = ρ_mass; river-law potential)
	_poisson_shader = _shader_create("res://compute/cassi_poisson.glsl")
	if _poisson_shader.is_valid():
		_poisson_pipe = _rd.compute_pipeline_create(_poisson_shader)
	# Mass deposit (PIC)
	_mass_deposit_shader = _shader_create("res://compute/cassi_mass_deposit.glsl")
	if _mass_deposit_shader.is_valid():
		_mass_deposit_pipe = _rd.compute_pipeline_create(_mass_deposit_shader)
	# Condensation scanner (Qi peak → BH nucleation)
	_cond_shader = _shader_create("res://compute/cassi_condensation.glsl")
	if _cond_shader.is_valid():
		_cond_pipe = _rd.compute_pipeline_create(_cond_shader)
	# BH integration (position + mass update each step)
	_bh_int_shader = _shader_create("res://compute/cassi_bh_integrate.glsl")
	if _bh_int_shader.is_valid():
		_bh_int_pipe = _rd.compute_pipeline_create(_bh_int_shader)
	_cache_uniform_sets()
	_ready = (_two_fluid_shader.is_valid() and _two_fluid_pipe.is_valid()
		and _nbody_shader.is_valid() and _nbody_pipe.is_valid()
		and _poisson_shader.is_valid() and _poisson_pipe.is_valid()
		and _mass_deposit_shader.is_valid() and _mass_deposit_pipe.is_valid()
		and _cond_shader.is_valid() and _cond_pipe.is_valid()
		and _bh_int_shader.is_valid() and _bh_int_pipe.is_valid())


func _cache_uniform_sets() -> void:
	# Two-fluid PDE declares ONLY set 0 (bindings 0-4)
	_us_two_0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		_uniform_storage(4, _mass_density_buf),
	], _two_fluid_shader, 0)
	# N-body: set 0 (fields/Φ/telemetry/gradients), set 1 (particles + the
	# mode-5 tree-gradient binding 3), set 2 (BH header + clusters).
	_us_nbody_0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		_uniform_storage(4, _mass_density_buf),
		_uniform_storage(5, _fft_buf),
		_uniform_storage(6, _tel_buf),
		_uniform_storage(7, _grad_buf),
		_uniform_storage(8, _grad_buf2),  # dual-lattice ∇(g·Φ)
	], _nbody_shader, 0)
	_us_nbody_1 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf), _uniform_storage(1, _vel_buf),
		_uniform_storage(2, _acc_buf),
		_uniform_storage(3, _tree_grad),  # tree-river (mode 5): per-particle ∇Φ_g
	], _nbody_shader, 1)
	_us_nbody_2 = _rd.uniform_set_create([
		_uniform_storage(0, _bh_buf),
		_uniform_storage(1, _cluster_buf),  # Plummer reference arm (mode 2)
	], _nbody_shader, 2)
	# Poisson solver (set 0: FFT workspace + mass density + telemetry)
	if _poisson_shader.is_valid():
		_us_poisson_0 = _rd.uniform_set_create([
			_uniform_storage(0, _fft_buf),
			_uniform_storage(1, _mass_density_buf),
			_uniform_storage(2, _tel_buf),
		], _poisson_shader, 0)
	# Mass deposit (set 0: positions + mass density)
	if _mass_deposit_shader.is_valid():
		_us_mass_dep_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _mass_density_buf),
		], _mass_deposit_shader, 0)
	# Condensation scanner (set 0: field_q, set 1: BHData write)
	if _cond_shader.is_valid():
		_us_cond_0 = _rd.uniform_set_create([
			_uniform_storage(0, _field_q),
		], _cond_shader, 0)
		_us_cond_1 = _rd.uniform_set_create([
			_uniform_storage(0, _bh_buf),
		], _cond_shader, 1)
	# BH integration (set 0: field_q, set 1: BHData write)
	if _bh_int_shader.is_valid():
		_us_bh_int_0 = _rd.uniform_set_create([
			_uniform_storage(0, _field_q),
		], _bh_int_shader, 0)
		_us_bh_int_1 = _rd.uniform_set_create([
			_uniform_storage(0, _bh_buf),
		], _bh_int_shader, 1)


# ═══════════════════════════════════════════════════════════════════════
# Initial conditions (ported verbatim — the seeded Gaussian/site placement)
# ═══════════════════════════════════════════════════════════════════════

func _init_field() -> void:
	var N := grid_N
	var nc := N * N * N
	var ey := PackedFloat32Array(); ey.resize(nc)
	var ei := PackedFloat32Array(); ei.resize(nc)
	var q := PackedFloat32Array(); q.resize(nc)
	var vel := PackedFloat32Array(); vel.resize(nc * 4)
	var half := float(N) * 0.5
	var rng := RandomNumberGenerator.new()
	if _seed_set:
		rng.seed = _seed
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id := i + N * (j + N * k)
				var dx := (float(i) - half) / half
				var dy := (float(j) - half) / half
				var dz := (float(k) - half) / half
				var r2 := dx * dx + dy * dy + dz * dz
				if field_attractor_init:
					# Attractor init (opt-in): EI small positive with ±10%
					# variation, EY = φ·EI ± 1e-3.
					var ei_v: float = 0.01 * (1.0 + 0.1 * rng.randf_range(-1.0, 1.0))
					var ey_v: float = PHI * ei_v + rng.randf_range(-0.001, 0.001)
					ey[id] = ey_v
					ei[id] = ei_v
					q[id] = ey_v * ey_v + ei_v * ei_v
				else:
					# Flat noise — no pre-existing structure (pure Cassi)
					ey[id] = rng.randf_range(-0.01, 0.01)
					ei[id] = rng.randf_range(-0.01, 0.01)
					q[id] = ey[id] * ey[id] + ei[id] * ei[id]
				vel[id * 4] = 0.0
				vel[id * 4 + 1] = 0.0
				vel[id * 4 + 2] = 0.0
				vel[id * 4 + 3] = 0.0
	_rd.buffer_update(_field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_field_ei, 0, ei.size() * 4, ei.to_byte_array())
	_rd.buffer_update(_field_q, 0, q.size() * 4, q.to_byte_array())
	_rd.buffer_update(_field_vel, 0, vel.size() * 4, vel.to_byte_array())
	print("[PhysicsEngine] Field initialized: %d^3 = %d cells" % [N, nc])


func _init_particles() -> void:
	var pos := PackedFloat32Array(); pos.resize(N_particles * 4)
	var vel := PackedFloat32Array(); vel.resize(N_particles * 4)
	var acc := PackedFloat32Array(); acc.resize(N_particles * 4)
	var rng := RandomNumberGenerator.new()
	if _seed_set:
		rng.seed = _seed
	var G := 1.0
	var eps2 := softening * softening
	var fr: float = initial_radius_fraction
	var ext_box: Vector3 = _extents()
	var extent_min: float = minf(ext_box.x, minf(ext_box.y, ext_box.z))

	# Pre-compute cluster centers and bulk velocities
	var centers := []
	var sep := cluster_separation
	var ms := merger_speed
	var nc := maxi(1, num_clusters)
	var bulk_vels := []
	var per_cluster := N_particles / nc
	var u_max_list: Array = []
	var gauss_u_max_list: Array = []
	var r_max_list: Array = []
	var retained_min: float = INF
	for c in range(nc):
		var angle := float(c) * PI * 2.0 / float(nc)
		var cx := sep * cos(angle); var cy := 0.0; var cz := sep * sin(angle)
		if nc > 8:
			# Fibonacci sphere distribution for many clusters
			var phi := acos(1.0 - 2.0 * (float(c) + 0.5) / float(nc))
			var th := PI * (1.0 + sqrt(5.0)) * float(c)
			cx = sep * sin(phi) * cos(th)
			cy = sep * sin(phi) * sin(th)
			cz = sep * cos(phi)
		centers.append(Vector3(cx, cy, cz))
		var bv := Vector3(-cx, -cy, -cz).normalized() * ms \
				+ Vector3(-cz, 0.0, cx).normalized() * ms * 0.3
		bulk_vels.append(bv)
		var c_abs: float = maxf(absf(cx), maxf(absf(cy), absf(cz)))
		var r_max_c: float = fr * extent_min - c_abs
		if r_max_c < 0.0:
			r_max_c = 0.0  # degenerate: cluster center beyond the safe radius
		r_max_list.append(r_max_c)
		var x_max: float = r_max_c / maxf(cluster_radius, 1e-6)
		var u_hi: float = pow(x_max * x_max / (1.0 + x_max * x_max), 1.5)
		u_max_list.append(u_hi)
		var z_max_c: float = r_max_c / (sqrt(2.0) * maxf(cluster_radius, 1e-6))
		var g_hi: float = _erf_approx(z_max_c) - (2.0 / sqrt(PI)) * z_max_c * exp(-z_max_c * z_max_c)
		gauss_u_max_list.append(maxf(g_hi, 0.0))
		retained_min = minf(retained_min, u_hi)

	# Cluster records → GPU buffer (64-record cap)
	var cluster_data := PackedFloat32Array()
	for c in range(nc):
		var cen: Vector3 = centers[c]
		cluster_data.append(cen.x); cluster_data.append(cen.y)
		cluster_data.append(cen.z); cluster_data.append(float(per_cluster))
	var n_rec := mini(nc, 64)
	if n_rec < nc:
		push_warning("num_clusters=%d exceeds the 64-record cluster buffer cap; using %d records" % [nc, n_rec])
	_rd.buffer_update(_cluster_buf, 0, n_rec * 4 * 4, cluster_data.to_byte_array())

	var max_r: float = 0.0
	var max_comp: float = 0.0
	var out_box := 0
	var total_mass: float = 0.0

	# ── Hoisted per-particle constants (the sim's interpreter-cost fix) ──
	var salp_exp: float = 1.0 - 2.35
	var salp_a: float = pow(0.3, salp_exp)
	var salp_b: float = pow(30.0, salp_exp)
	var salp_inv: float = 1.0 / salp_exp
	var s2: float = sqrt(2.0) * maxf(cluster_radius, 1e-6)  # √2·σ
	var s2_inv: float = 1.0 / s2
	var two_over_sqrt_pi: float = 2.0 / sqrt(PI)
	var a2: float = cluster_radius * cluster_radius
	var a_s: float = maxf(cluster_radius, 1e-6)
	var third: float = 1.0 / 3.0
	var minus_two_thirds: float = -2.0 / 3.0

	for i in range(N_particles):
		var i4 := i * 4
		var cidx := mini(int(i / per_cluster), nc - 1)
		var center: Vector3 = centers[cidx]
		var bv: Vector3 = bulk_vels[cidx]

		# Salpeter IMF: dN/dM ∝ M^(-2.35), range [0.3, 30.0] M☉
		var m := pow(salp_a - rng.randf() * (salp_a - salp_b), salp_inv)
		pos[i4 + 3] = m
		total_mass += m

		# ── Position draw (per initial-condition profile) ──
		var lx := 0.0; var ly := 0.0; var lz := 0.0
		var r := 0.0
		var r_max_eff: float = r_max_list[cidx]
		if initial_condition == 0:
			# Truncated Plummer — REJECTION-FREE inverse CDF
			var u_hi: float = u_max_list[cidx]
			var u := rng.randf_range(0.001, maxf(u_hi, 0.0011))
			r = cluster_radius / sqrt(pow(u, minus_two_thirds) - 1.0)
			var th := acos(2.0 * rng.randf() - 1.0)
			var ph := rng.randf() * PI * 2.0
			lx = r * sin(th) * cos(ph)
			ly = r * sin(th) * sin(ph)
			lz = r * cos(th)
		elif initial_condition == 1:
			# Gaussian ball — REJECTION-FREE truncated N(0, σ) draw
			var z_max: float = r_max_eff * s2_inv
			if z_max <= 0.0:
				r = 0.0
			else:
				var u: float = rng.randf() * maxf(gauss_u_max_list[cidx], 1e-30)
				var z_lo := 0.0
				var z_hi: float = z_max
				for _b in range(16):
					var z_m: float = 0.5 * (z_lo + z_hi)
					var f_m: float = _erf_approx(z_m) - two_over_sqrt_pi * z_m * exp(-z_m * z_m)
					if f_m < u:
						z_lo = z_m
					else:
						z_hi = z_m
				var z: float = 0.5 * (z_lo + z_hi)
				r = s2 * z
			var th := acos(2.0 * rng.randf() - 1.0)
			var ph := rng.randf() * PI * 2.0
			lx = r * sin(th) * cos(ph)
			ly = r * sin(th) * sin(ph)
			lz = r * cos(th)
		else:
			# Uniform sphere — REJECTION-FREE truncated draw
			var u_trunc: float = minf(1.0, pow(r_max_eff / a_s, 3.0))
			var u := rng.randf() * u_trunc
			r = a_s * pow(u, third)
			var th := acos(2.0 * rng.randf() - 1.0)
			var ph := rng.randf() * PI * 2.0
			lx = r * sin(th) * cos(ph)
			ly = r * sin(th) * sin(ph)
			lz = r * cos(th)
		pos[i4] = lx + center.x
		pos[i4 + 1] = ly + center.y
		pos[i4 + 2] = lz + center.z

		# ── Multi-rung cascade seeding (CASCADE_GRID.md §3.3) ──
		if multi_rung_seed and multi_rung_count > 0:
			var wx: float = pos[i4]
			var wy: float = pos[i4 + 1]
			var wz: float = pos[i4 + 2]
			var k_base: float = TAU / (multi_rung_base_scale * maxf(cluster_radius, 1e-6))
			for mr in range(multi_rung_count):
				var km: float = k_base * pow(PHI, float(mr))
				var d: Vector3 = _fib_sphere_dir(mr, multi_rung_count)
				var ph_m: float = float(mr) * (TAU / (PHI * PHI))
				var s: float = sin(km * (d.x * wx + d.y * wy + d.z * wz) + ph_m)
				var amp: float = multi_rung_amp / km
				wx += amp * s * d.x
				wy += amp * s * d.y
				wz += amp * s * d.z
			pos[i4] = wx
			pos[i4 + 1] = wy
			pos[i4 + 2] = wz

		var rr: float = sqrt(lx * lx + ly * ly + lz * lz)
		max_r = maxf(max_r, rr)
		var mc: float = maxf(absf(pos[i4]), maxf(absf(pos[i4 + 1]), absf(pos[i4 + 2])))
		max_comp = maxf(max_comp, mc)
		if absf(pos[i4]) > ext_box.x or absf(pos[i4 + 1]) > ext_box.y or absf(pos[i4 + 2]) > ext_box.z:
			out_box += 1

		# ── Circular velocity around cluster center + bulk ──
		var r2p := r * r + eps2
		var M_enc: float = 0.0
		if initial_condition == 0:
			M_enc = float(per_cluster) * (r2p * r) / ((r2p + a2) * sqrt(r2p + a2))
		elif initial_condition == 1:
			var z: float = sqrt(r2p) * s2_inv
			M_enc = float(per_cluster) * (_erf_approx(z) - two_over_sqrt_pi * z * exp(-z * z))
		else:
			M_enc = float(per_cluster) * minf(1.0, pow(sqrt(r2p) / a_s, 3.0))
		var v_circ := sqrt(G * M_enc / maxf(r, 0.01)) * initial_v_circ_factor
		var nx := -ly; var ny := lx; var nz := 0.0
		var nl := sqrt(nx * nx + ny * ny + nz * nz)
		if nl > 0.001:
			nx /= nl; ny /= nl; nz /= nl
		else:
			nx = 1.0; ny = 0.0; nz = 0.0
		var pert := 0.05
		vel[i4] = (nx + rng.randf_range(-pert, pert)) * v_circ + bv.x
		vel[i4 + 1] = (ny + rng.randf_range(-pert, pert)) * v_circ + bv.y
		vel[i4 + 2] = (nz + rng.randf_range(-pert, pert)) * v_circ + bv.z
		vel[i4 + 3] = 0.0

	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_rd.buffer_update(_acc_buf, 0, acc.size() * 4, acc.to_byte_array())

	# Retained fraction (analytic, per profile — min over clusters)
	var retained: float = retained_min if retained_min < INF else 1.0
	if initial_condition == 1:
		var g_min: float = INF
		for c in range(nc):
			var z_max: float = r_max_list[c] / s2
			var f: float = _erf_approx(z_max) - two_over_sqrt_pi * z_max * exp(-z_max * z_max)
			g_min = minf(g_min, f)
		retained = g_min
	elif initial_condition == 2:
		var u_min: float = INF
		for c in range(nc):
			var u_tr: float = minf(1.0, pow(r_max_list[c] / a_s, 3.0))
			u_min = minf(u_min, u_tr)
		retained = u_min
	_total_init_mass = total_mass
	if out_box > 0:
		push_warning("[PhysicsEngine] IC: %d initial particles outside the box (fr=%.2f, extent_min=%.1f, aspect=%s) — a cluster center sits beyond the safe radius; config-level, not a truncation failure" % [out_box, fr, extent_min, str(box_aspect)])
	var ic_name := "Plummer" if initial_condition == 0 else ("Gaussian" if initial_condition == 1 else "Uniform")
	print("[PhysicsEngine] IC [%s]: retained=%.4f  max_radius=%.1f  max|comp|=%.1f  out_of_box=%d (fr=%.2f, extent_min=%.1f, aspect=%s)" % [
		ic_name, retained, max_r, max_comp, out_box, fr, extent_min, str(box_aspect)])
	print("[PhysicsEngine] Particles initialized: %d (Σm=%.1f, m_mean=%.4f)" % [N_particles, total_mass, total_mass / float(maxi(N_particles, 1))])


# ── Resolution-aware river calibration (opt-in; ported verbatim) ────────
func _apply_gravity_calibration() -> void:
	if _bh_init_bytes.size() < 32:
		return
	_bh_init_bytes.encode_float(48, 1.0 if black_holes_enabled else 0.0)
	if not river_calibrate_gn:
		_bh_init_bytes.encode_float(28, 1.0)
		_gn_eff = 1.0
		return
	var ext_box: Vector3 = _extents()
	var h: float = 2.0 * ext_box.x / float(maxi(grid_N, 1))
	var hy: float = 2.0 * ext_box.y / float(maxi(grid_N, 1))
	var hz: float = 2.0 * ext_box.z / float(maxi(grid_N, 1))
	var m_mean: float = _total_init_mass / float(maxi(N_particles, 1))
	var g_ref: float = 1.0 + (xi - 1.0) * river_q_ref
	var gn: float = 4.0 * PI / (river_pi_ref * g_ref * h * hy * hz * m_mean)
	_bh_init_bytes.encode_float(28, gn)  # bh[1].w — G_N
	_gn_eff = gn * river_pi_ref * g_ref * (h * hy * hz) * m_mean / (4.0 * PI)
	print("[PhysicsEngine] Gravity calibration: h=(%.4f,%.4f,%.4f)  m_mean=%.4f  π/ρ_ref=%.4f  g_ref=%.4f → G_N=%.4f (G_eff=%.4f)" % [
		h, hy, hz, m_mean, river_pi_ref, g_ref, gn, _gn_eff])


# ═══════════════════════════════════════════════════════════════════════
# The per-step chain (ported verbatim — every constant, PC layout and
# dispatch order preserved)
# ═══════════════════════════════════════════════════════════════════════

func _step_dispatches(cl: int) -> void:
	_time += dt
	_step_count += 1
	var ext_step: Vector3 = _extents()

	# ── Pre-allocated push constants (no per-step allocations) ──
	_pc_bytes.encode_float(0, float(grid_N))
	_pc_bytes.encode_float(4, dt)
	_pc_bytes.encode_float(8, _time)
	_pc_bytes.encode_float(12, PHI)
	_pc_bytes.encode_float(16, xi)
	_pc_bytes.encode_float(20, softening * softening)
	_pc_bytes.encode_float(24, float(N_particles))
	_pc_bytes.encode_float(28, float(mode))
	_pc_bytes.encode_float(32, source_strength)
	_pc_bytes.encode_float(36, float(num_clusters))
	_pc_bytes.encode_float(40, float(gravity_mode))

	# Two-fluid PC (dedicated 56 B): shared 11 fields + 3 per-axis extents
	_two_fluid_pc_bytes.encode_float(0, float(grid_N))
	_two_fluid_pc_bytes.encode_float(4, dt)
	_two_fluid_pc_bytes.encode_float(8, _time)
	_two_fluid_pc_bytes.encode_float(12, PHI)
	_two_fluid_pc_bytes.encode_float(16, xi)
	_two_fluid_pc_bytes.encode_float(20, softening * softening)
	_two_fluid_pc_bytes.encode_float(24, float(N_particles))
	_two_fluid_pc_bytes.encode_float(28, float(mode))
	_two_fluid_pc_bytes.encode_float(32, source_strength)
	_two_fluid_pc_bytes.encode_float(36, float(num_clusters))
	_two_fluid_pc_bytes.encode_float(40, float(gravity_mode))
	_two_fluid_pc_bytes.encode_float(44, ext_step.x)
	_two_fluid_pc_bytes.encode_float(48, ext_step.y)
	_two_fluid_pc_bytes.encode_float(52, ext_step.z)

	# N-body PC (dedicated 60 B): shared 11 fields + pass_mode at float 11
	# (0 = particles; 1/1.5 = gradient/dual-gradient; 2 = warmup) + the
	# three RealSim coefficients.
	_nbody_pc_bytes.encode_float(0, float(grid_N))
	_nbody_pc_bytes.encode_float(4, dt)
	_nbody_pc_bytes.encode_float(8, _time)
	_nbody_pc_bytes.encode_float(12, PHI)
	_nbody_pc_bytes.encode_float(16, xi)
	_nbody_pc_bytes.encode_float(20, softening * softening)
	_nbody_pc_bytes.encode_float(24, float(N_particles))
	_nbody_pc_bytes.encode_float(28, float(mode))
	_nbody_pc_bytes.encode_float(32, source_strength)
	_nbody_pc_bytes.encode_float(36, float(num_clusters))
	# Effective gravity mode: when the meshless TREE arm is live, force the
	# nbody shader to the tree path (mode 5) regardless of the exported
	# gravity_mode — the caller supplies the per-particle gradient via
	# run_steps(tree_grad). Otherwise the exported gravity_mode stands.
	var eff_gmode: float = 5.0 if (meshless_mode and meshless_gravity) else float(gravity_mode)
	_nbody_pc_bytes.encode_float(40, eff_gmode)
	_nbody_pc_bytes.encode_float(44, 0.0)  # pass_mode = 0 (particles)
	_nbody_pc_bytes.encode_float(48, realsim_drag)
	_nbody_pc_bytes.encode_float(52, realsim_viscosity)
	_nbody_pc_bytes.encode_float(56, realsim_friction)

	# Mass deposit PC: [N_f, particle_N, extent_x/y/z, off_x/y/z] — the
	# offsets are encoded per dispatch (0 for the base lattice; the dual
	# offset extent_i/N for the shifted chain).
	_md_pc_bytes.encode_float(0, float(grid_N))
	_md_pc_bytes.encode_float(4, float(N_particles))
	_md_pc_bytes.encode_float(8, ext_step.x)
	_md_pc_bytes.encode_float(12, ext_step.y)
	_md_pc_bytes.encode_float(16, ext_step.z)
	_md_pc_bytes.encode_float(20, 0.0)
	_md_pc_bytes.encode_float(24, 0.0)
	_md_pc_bytes.encode_float(28, 0.0)
	# BH integrate PC: [N_f, dt, acc_rate, max_age]
	_bh_int_pc_bytes.encode_float(0, float(grid_N))
	_bh_int_pc_bytes.encode_float(4, dt)
	_bh_int_pc_bytes.encode_float(8, bh_acc_rate)
	_bh_int_pc_bytes.encode_float(12, bh_max_age)
	# Condensation PC: [N_f, qi_threshold, _, _]
	_cond_pc_bytes.encode_float(0, float(grid_N))
	_cond_pc_bytes.encode_float(4, qi_condensation_threshold)

	_cond_step_counter += 1
	if _cond_step_counter >= 100:
		_cond_step_counter = 0

	var wg := ceili(float(grid_N) / 4.0)
	var pg := ceili(float(N_particles) / 256.0) if N_particles > 0 else 1

	# ── 0. GPU clear (poisson mode 3): ρ = 0, telemetry reset ─────────
	# On the GPU per step (CPU buffer_update is illegal inside an open
	# compute list, and chained steps need a clean ρ each step).
	if _poisson_shader.is_valid():
		_poisson_pc_bytes.encode_float(0, float(grid_N))
		_poisson_pc_bytes.encode_float(4, 0.0)
		_poisson_pc_bytes.encode_float(8, 0.0)
		_poisson_pc_bytes.encode_float(12, 3.0)  # mode 3 = clear
		_poisson_pc_bytes.encode_float(16, ext_step.x)
		_poisson_pc_bytes.encode_float(20, ext_step.y)
		_poisson_pc_bytes.encode_float(24, ext_step.z)
		_rd.compute_list_bind_compute_pipeline(cl, _poisson_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_poisson_0, 0)
		_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
		_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)  # 2D cells dispatch
	_barrier(cl)  # clear → deposit

	# ── 1. Mass deposit: scatter particle masses → field grid (PIC) ──
	if _mass_deposit_shader.is_valid() and N_particles > 0:
		_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_0, 0)
		_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
	_barrier(cl)  # deposit → poisson

	# ── 1.5. Spectral Poisson solve: ∇²Φ = ρ_mass ─────────────────────
	# RIVER MODES ONLY (0, 3 and 4); SKIPPED under tree gravity
	# (meshless_mode && meshless_gravity — the octree replaces the solve).
	if (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) \
			and not (meshless_mode and meshless_gravity):
		_dispatch_poisson(cl)
	_barrier(cl)  # deposit → PDE (rho visibility for the PDE source)

	# ── 2. Two-fluid PDE — the grid solver (the meshless Voronoi arm is
	# NOT ported in this phase; meshless_mode only gates the nbody seams).
	# freeze_field (diagnostic): the field is initialized once and left fixed.
	if _two_fluid_shader.is_valid() and not freeze_field:
		_rd.compute_list_bind_compute_pipeline(cl, _two_fluid_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_two_0, 0)
		_rd.compute_list_set_push_constant(cl, _two_fluid_pc_bytes, _two_fluid_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg, wg, wg)
	_barrier(cl)  # PDE → condensation

	# ── 2.5. Condensation scan (every 100 steps) ───────────────────
	if _cond_step_counter == 0 and _cond_shader.is_valid() and black_holes_enabled:
		_rd.compute_list_bind_compute_pipeline(cl, _cond_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_cond_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_cond_1, 1)
		_rd.compute_list_set_push_constant(cl, _cond_pc_bytes, _cond_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg, wg, wg)
	_barrier(cl)  # condensation → BH integrate

	# ── 2.6. BH integration (every step) ──────────────────────────
	if _bh_int_shader.is_valid() and black_holes_enabled:
		_rd.compute_list_bind_compute_pipeline(cl, _bh_int_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_bh_int_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_bh_int_1, 1)
		_rd.compute_list_set_push_constant(cl, _bh_int_pc_bytes, _bh_int_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg, wg, wg)
	_barrier(cl)  # BH integrate → gradient

	# ── 2.8. Cell-centered ∇(g·Φ) build (river-arm estimator) ──────
	# One thread per cell; pass_mode = 1. RIVER MODE ONLY; skipped under
	# tree gravity (the walk produces ∇Φ_g directly).
	if (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) \
			and not (meshless_mode and meshless_gravity) and _nbody_shader.is_valid():
		_nbody_pc_bytes.encode_float(44, 1.0)  # pass_mode = 1 (gradient)
		_rd.compute_list_bind_compute_pipeline(cl, _nbody_pipe)
		# ALL THREE sets must be bound (the pipeline rejects a dispatch
		# with any declared set missing).
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_1, 1)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_2, 2)
		_rd.compute_list_set_push_constant(cl, _nbody_pc_bytes, _nbody_pc_bytes.size())
		_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)
	_barrier(cl)  # gradient → nbody

	# ── 2.85. Dual (Yin/Yang) lattice chain (CASCADE_GRID.md) ─────
	# The SAME deposit → Poisson → gradient chain on the half-cell-shifted
	# partner lattice. River modes only, gated on dual_grid. Skipped under
	# tree gravity (the tree is already isotropic — no BCC partner).
	if dual_grid and (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) \
			and not (meshless_mode and meshless_gravity) and _nbody_shader.is_valid():
		if _poisson_shader.is_valid():
			_poisson_pc_bytes.encode_float(12, 3.0)  # mode 3 = clear (ρ = 0)
			_rd.compute_list_bind_compute_pipeline(cl, _poisson_pipe)
			_rd.compute_list_bind_uniform_set(cl, _us_poisson_0, 0)
			_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
			_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)
		_barrier(cl)  # dual clear → deposit
		if _mass_deposit_shader.is_valid() and N_particles > 0:
			_md_pc_bytes.encode_float(20, ext_step.x / float(grid_N))
			_md_pc_bytes.encode_float(24, ext_step.y / float(grid_N))
			_md_pc_bytes.encode_float(28, ext_step.z / float(grid_N))
			_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
			_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_0, 0)
			_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
			_rd.compute_list_dispatch(cl, pg, 1, 1)
		_barrier(cl)  # dual deposit → poisson
		_dispatch_poisson(cl)
		_barrier(cl)  # dual poisson → gradient
		_nbody_pc_bytes.encode_float(44, 1.5)  # pass_mode = 1.5 (dual gradient)
		_rd.compute_list_bind_compute_pipeline(cl, _nbody_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_1, 1)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_2, 2)
		_rd.compute_list_set_push_constant(cl, _nbody_pc_bytes, _nbody_pc_bytes.size())
		_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)
		_barrier(cl)  # dual gradient → nbody

	# ── 2.9. Acceleration warm-up (ONE-TIME, before the first KDK step) ──
	if _grav_warmup and _nbody_shader.is_valid() and N_particles > 0:
		_grav_warmup = false
		_nbody_pc_bytes.encode_float(44, 2.0)  # pass_mode = 2 (warmup)
		_rd.compute_list_bind_compute_pipeline(cl, _nbody_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_1, 1)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_2, 2)
		_rd.compute_list_set_push_constant(cl, _nbody_pc_bytes, _nbody_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
		_barrier(cl)  # warmup → nbody

	# ── 3. N-body gravity (cached-acc KDK) ─────────────────────────
	if _nbody_shader.is_valid() and N_particles > 0:
		_nbody_pc_bytes.encode_float(44, 0.0)  # pass_mode = 0 (particles)
		_rd.compute_list_bind_compute_pipeline(cl, _nbody_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_1, 1)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_2, 2)
		_rd.compute_list_set_push_constant(cl, _nbody_pc_bytes, _nbody_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
	_barrier(cl)  # end-of-step visibility (nbody writes → next step)


# load ρ → FFT(x) → FFT(y) → FFT(z) → Φ̂=−ρ̂/k² (k=0 nulled) → IFFT(z) → IFFT(y) → IFFT(x)
func _dispatch_poisson(cl: int) -> void:
	if not _poisson_shader.is_valid():
		return
	_rd.compute_list_bind_compute_pipeline(cl, _poisson_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_poisson_0, 0)
	# mode 0: load ρ → complex buffer. The per-axis extents ride along for
	# the kspace multiply — the FFT passes only touch floats 4/8/12.
	var ext_p: Vector3 = _extents()
	_poisson_pc_bytes.encode_float(0, float(grid_N)); _poisson_pc_bytes.encode_float(4, 0.0)
	_poisson_pc_bytes.encode_float(8, 0.0); _poisson_pc_bytes.encode_float(12, 0.0)
	_poisson_pc_bytes.encode_float(16, ext_p.x)
	_poisson_pc_bytes.encode_float(20, ext_p.y)
	_poisson_pc_bytes.encode_float(24, ext_p.z)
	_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
	_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)  # 2D cells dispatch
	_barrier(cl)  # load → fwd x
	# mode 1: forward FFT passes x, y, z
	for axis in range(3):
		_poisson_pc_bytes.encode_float(4, float(axis))
		_poisson_pc_bytes.encode_float(8, 0.0)   # forward
		_poisson_pc_bytes.encode_float(12, 1.0)
		_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
		_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)  # 2D rows dispatch
		_barrier(cl)  # FFT passes: memory visibility between stages
	# mode 2: k-space multiply Φ̂ = −ρ̂/k² (BETWEEN fwd and inv — required)
	_poisson_pc_bytes.encode_float(12, 2.0)
	_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
	_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)  # 2D cells dispatch
	_barrier(cl)  # fwd z → kspace
	# mode 1: inverse FFT passes z, y, x (scaled 1/N each)
	for axis in range(2, -1, -1):
		_poisson_pc_bytes.encode_float(4, float(axis))
		_poisson_pc_bytes.encode_float(8, 1.0)   # inverse
		_poisson_pc_bytes.encode_float(12, 1.0)
		_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
		_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)  # 2D rows dispatch
		_barrier(cl)  # inverse FFT passes
