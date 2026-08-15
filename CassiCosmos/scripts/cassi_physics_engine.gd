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
# Tree-walk softening (LENGTH²): eps2 = (ML_TREE_EPS2_FRAC · extent_min)²
# derived per tree job (the sim's recipe — the tree worker's monopole
# R² = ds² + eps2). ML_TREE_NODE_MAX_MULT sizes the node cap for the job.
const ML_TREE_EPS2_FRAC := 0.05
const ML_TREE_NODE_MAX_MULT := 8
# ── Meshless (moving-Voronoi) arm — MESHLESS_PLAN.md §10 (ported verbatim) ──
const ML_N1 := 16              # BCC sublattice count → 2·16³ = 8192 sites at N=64
const ML_REBUILD := 25         # steering + remap + JFA-refresh cadence (steps)
const ML_KAPPA := 0.5          # Lloyd-style centroid relaxation fraction
const ML_LAM := 8.0            # super-Lagrangian momentum ride
const ML_RHO_FLOOR := 0.005    # steering guard: rho = EY+EI can hit ~0 in the live field
const ML_MAX_DRIFT := 2.0      # steering guard: cap the per-rebuild site drift (~a quarter cell)
const ML_OM2 := 20.0           # omega_0² — the same conversion constant as the grid PDE
const ML_LLOYD_P := 4.0        # density-weighted Lloyd exponent on the coherence q
const ML_LLOYD_FLOOR := 1e-3   # density-weighting floor for the mode-3 centroid
const ML_INT_MAX := 2147483647

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
# Cassi particle merge — "dust -> object" (particle_merge_design.md): two
# particles within R_m = ½·h₀ = extent/grid_N coalesce (mass + momentum
# conserved, SINK-rule pair resolution) ONLY where the local coherence
# q_coh = ρ²/(ρ²+φ⁻²+ε²) > φ⁻². The merge writes merged survivor masses + dead
# (pos.w=0) into pos[].w — the deposit skips mass ≤ 0 and the nbody/instancer
# preserve pos.w — so no other pass needs to know about death. Default off.
# Runs AFTER each run_steps batch on the engine's LOCAL RD (submit+sync per
# cycle makes the host CPU prefix-sum readback legal there); on a global-RD
# engine instance the sim's _render_frame hook runs it instead.
var particle_merge: bool = false
# Physical-merge redesign (coherence_merge_rnd.md §3, 2026-08-15): when the
# merge is on, these gate which of the four layer criteria apply. Default on
# = the realistic merge; off recreates the legacy (distance + q_coh only) for
# the §3d falsifier A/B tests.
var merge_subsonic: bool = true   # hypothesis: |v_t| < c_s (no fly-by merges)
var merge_virial: bool = true     # hypothesis: virialised targets stop accreting
var merge_sel_gate: bool = true   # doctrine: order-selective q_sel = q_coh·q_ord
# Cascade-multigrid arm (research/cascade_multigrid/multigrid_design.md): a
# coarse long-range Poisson level at N_c = grid_N/2 (the radix-2 Stockham
# constraint — the φ-ideal N_c = round(N_f/φ)=40 is NOT radix-2; see the
# design §(a) resonance consequence: N=32 re-locks the coarse/fine cell
# phase, losing the φ de-resonation, placement bias 0.56 vs 0.47 — the
# honest integer fallback documented, not the physical optimum). The coarse
# is its own periodic solve on the FULL box (no boundary data), solved ONCE
# per run_steps batch (moves slowly); the nbody river arm blends it with the
# fine ∇(g·Φ) by the radial window w(r): w=1 (r≤4·h_c, fine-exact bubble),
# 0 (r≥7·h_c), smoothstep between, volume-renormalized by (N_c/N_f)³. Default
# off -> the coarse chain never dispatches and the nbody blend branch never
# runs -> bit-identical battery.
var cascade_level: bool = false
# Cassi BH accretion — "object -> BH": particles within a BH's accretion
# radius (bh_accretion_radius, world units — a small fraction of the BH's
# σ softening) are marked dead (pos.w = 0, skipped by deposit/nbody/instancer)
# and their mass is added to the BH's record (bh[base].w) atomically — exactly
# conserved. Default off. Dispatched after the BH-integrate block in the step
# chain (pure GPU, no readback). Only meaningful when black_holes_enabled AND
# at least one BH record is active.
var bh_accretion: bool = false
var bh_accretion_radius: float = 0.1   # world units (~1× the default softening σ)

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
var _field_scratch: RID  # vec4 per cell — two-fluid PDE double-buffer scratch (determinism fix, cassi_two_fluid.glsl)
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
var _mass_density_fix: RID  # uvec4 per cell — exact fixed-point digit-sum deposit accumulator (determinism fix, cassi_mass_deposit.glsl)
# — mode-5 tree seam: nbody SET 1 binding 3 (the buffer the nbody reads) —
var _tree_grad: RID    # vec4[max(N_particles,1)] — per-particle tree ∇Φ_g (uploaded via run_steps)
# — fp16 snapshot packing (Part 2 of the transfer optimization): the pack
# pass runs on THIS engine's local RD (worker thread) and halves the
# pos/vel readback (N×8 B per array vs N×16). The render side unpacks in
# cassi_blend_pos.glsl (packed modes). CPU _pack_f16_pairs is the fallback
# when the pack shader fails to build (same byte layout).
var _pos_packed_buf: RID   # uvec2[max(N_particles,1)] — packed pos half-pairs
var _vel_packed_buf: RID   # uvec2[max(N_particles,1)] — packed vel half-pairs
var _pack_shader: RID; var _pack_pipe: RID
var _us_pack_pos: RID; var _us_pack_vel: RID
var _pack_pc_bytes: PackedByteArray  # pack PC (uint count + pad = 8 B)
# — meshless (moving-Voronoi) arm buffers (allocated always; used when meshless_mode) —
var _jfa_shader: RID; var _jfa_pipe: RID
var _cell_shader: RID; var _cell_pipe: RID
var _raster_shader: RID; var _raster_pipe: RID
var _ml_labels_a: RID
var _ml_labels_b: RID
var _ml_sites: RID
var _ml_psi_y: RID
var _ml_psi_i: RID
var _ml_pi_y: RID
var _ml_pi_i: RID
var _ml_lap_y: RID
var _ml_lap_i: RID
var _ml_vol: RID
var _ml_cen: RID
var _ml_remap: RID
var _ml_tmp_y: RID
var _ml_tmp_i: RID
var _ml_tmp_py: RID
var _ml_tmp_pi: RID
var _ml_grad_y: RID  # vec4[n_sites] — solved least-squares ∇ψ_y (.xyz), .w = 1
var _ml_grad_i: RID  # vec4[n_sites] — solved least-squares ∇ψ_i (.xyz), .w = 1
var _ml_lsm_y: RID   # vec4[3·n_sites] — least-squares M rows + rhs (ψ_y)
var _ml_lsm_i: RID   # vec4[3·n_sites] — least-squares M rows + rhs (ψ_i)
var _us_jfa_0: RID
var _us_cell_0: RID
var _us_raster_0: RID
var _jfa_pc_bytes: PackedByteArray    # JFA PC (8 floats: N, jump, read_a, n_sites, h, pad×3)
var _cell_pc_bytes: PackedByteArray   # cell PC (17 floats: mode, N, n_sites, dt, hx, hy, hz, C2, OM2, PHI, source_s, rho_floor, drift_cap, kappa, lam, T_steer, lloyd_p)
var _raster_pc_bytes: PackedByteArray # raster PC (8 floats: N, n_sites, hx, hy, hz, pad×3)
var _ml_sites_cpu := PackedFloat32Array()
var _ml_ready := false
var _ml_step_count := 0
var _ml_tree_nsrc := 0
# — tree-worker CONSUMER (decoupled mode: the engine worker drives the sim's
# cassi_tree_worker.gd instance). The sim creates + starts the tree worker on
# the MAIN thread (start() loads shaders on main) and hands the object via
# cfg.tree_worker; this worker stages jobs from ITS OWN RD (it owns the
# meshless/pos buffers now) and feeds the freshest gradient into run_steps.
var _tree_worker = null          # CassiTreeWorker (owned by the sim — never freed here)
var _tree_cadence := 1           # submit a tree job every N physics jobs (sim's cadence semantics)
var _tree_job_counter := 0
var _tree_grad_cache := PackedFloat32Array()   # freshest completed gradient (feeds run_steps)
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
# ── Particle merge (compute/cassi_particle_merge.glsl; gated on particle_merge) ──
var _merge_shader: RID; var _merge_pipe: RID; var _us_merge_0: RID
var _merge_alive_buf: RID; var _merge_mass_buf: RID; var _merge_mom_buf: RID
var _merge_cen_buf: RID; var _merge_best_buf: RID; var _merge_sink_buf: RID
var _merge_cc_buf: RID; var _merge_cs_buf: RID; var _merge_ch_buf: RID
var _merge_cl_buf: RID; var _merge_mc_buf: RID
var _merge_spin_buf: RID   # vec4[N] — per-object spin accumulator (§3c, coherence_merge_rnd.md)
var _merge_mprev_buf: RID  # float[N] — pre-hop canonical mass (pass_fold stash; exact μ for spin)
var _merge_hash_nx: int = 1; var _merge_hash_ny: int = 1; var _merge_hash_nz: int = 1
var _merge_hash_total: int = 1
var _merge_cell_wx: float = 0.0; var _merge_cell_wy: float = 0.0; var _merge_cell_wz: float = 0.0
var _merge_cycles_run := 0
# ── On-GPU exclusive scan (compute/cassi_exclusive_scan.glsl; FIX B): replaces
# the host CPU prefix-sum (cc readback + cs/ch uploads) with 4 GPU passes. The
# scratch buffer holds L1 block totals + L2 (two-level carry) regions. ──
var _scan_shader: RID; var _scan_pipe: RID; var _us_scan_0: RID
var _merge_scr_buf: RID
var _merge_nb1a: int = 256   # pad(L1 count to 256)
var _merge_nb2: int = 1      # L2 count (≤256)
# ── BH accretion (compute/cassi_bh_accretion.glsl; gated on bh_accretion) ──
var _bh_acc_shader: RID; var _bh_acc_pipe: RID; var _us_bh_acc_0: RID
var _bh_acc_pc_bytes: PackedByteArray  # BH accretion PC (4 floats)
# ── Cascade multigrid (compute/cassi_coarse_grad.glsl; gated on cascade_level) ──
var _cf_grad_shader: RID; var _cf_grad_pipe: RID; var _us_cf_grad_0: RID
var _cf_density_buf: RID   # coarse ρ (N_c³ float)
var _cf_fft_buf: RID       # coarse Φ (N_c³ vec2 complex)
var _cf_grad_buf: RID      # coarse ∇(g·Φ) (N_c³ vec4)
var _us_poisson_c: RID     # coarse poisson set (cf_fft + cf_density + tel)
var _us_mass_dep_c: RID    # coarse deposit set (pos + cf_density)
var _cascade_nc: int = 0   # coarse N (grid_N/2 when enabled)
var _cf_grad_pc_bytes: PackedByteArray  # coarse-gradient PC (8 floats)
var _cascade_ran := 0      # lifetime coarse-solve count (verify/battery diag)
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
# ── Mirror publish cadence (Part 1 of the transfer optimization): the
# snapshot+telemetry readbacks run every Kth JOB (cfg key snapshot_cadence,
# default 2) instead of every job; non-publish jobs carry ONLY
# {executed, step_count, t} — the sim skips the mirror upload and keeps the
# backlog/readouts. The sim overrides the cadence per-submit via the job
# dict ("cadence") — live without reinit.
var _snapshot_cadence: int = 2
var _job_counter := 0       # job sequence counter (publish when % cadence == 0)


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
	particle_merge = bool(cfg.get("particle_merge", particle_merge))
	merge_subsonic = bool(cfg.get("merge_subsonic", merge_subsonic))
	merge_virial = bool(cfg.get("merge_virial", merge_virial))
	merge_sel_gate = bool(cfg.get("merge_sel_gate", merge_sel_gate))
	cascade_level = bool(cfg.get("cascade_level", cascade_level))
	bh_accretion = bool(cfg.get("bh_accretion", bh_accretion))
	bh_accretion_radius = float(cfg.get("bh_accretion_radius", bh_accretion_radius))
	# Tree-worker consumer (decoupled mode): the sim creates + starts the
	# tree worker on the main thread and hands the object here.
	_tree_worker = cfg.get("tree_worker", null)
	_tree_cadence = int(cfg.get("tree_cadence", 1))
	_tree_job_counter = 0
	_tree_grad_cache = PackedFloat32Array()
	_snapshot_cadence = maxi(int(cfg.get("snapshot_cadence", 2)), 1)
	_job_counter = 0
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
		# ── Cassi particle merge (opt-in, LOCAL-RD engine only): runs AFTER
		# the step list, on the worker's local RD where submit()+sync() per
		# cycle is legal (global RD cannot submit — "Only local devices can
		# submit and sync."). The merge's cycle loop needs a host CPU
		# prefix-sum (buffer_get_data) between its spatial-hash passes; the
		# local RD makes those readbacks synchronous here. On a global-RD
		# engine instance this is skipped — the sim's _render_frame hook
		# drives it. Cadence: per run_steps batch (R_m ≈ 0.586 world units is
		# crossed in ~586 dt=0.001 steps ≫ a batch, so per-batch is far inside
		# the reaction budget).
		if particle_merge and N_particles > 0:
			_run_merge_pass()
	# Meshless steering: rebuild the mesh every ML_REBUILD steps (the sim's
	# cadence). The rebuild is a standalone compute list + readbacks — on a
	# local RD it stalls only THIS engine's physics (the decoupling win);
	# on the global RD the readbacks self-stall.
	if meshless_mode and _ml_ready and not freeze_field:
		_ml_step_count += n
		if _ml_step_count >= ML_REBUILD:
			_ml_step_count = 0
			_mesh_rebuild()


## The mirror state the render side will consume (phase 2): positions,
## velocities, the Qi field and the solved potential, plus the sim time.
## packed=true returns pos/vel as fp16 half-pair PackedByteArrays (N×8 B
## each: word0 = half(x)|half(y)<<16, word1 = half(z)|half(w)<<16) — the
## transfer optimization. The pack runs ON THE WORKER's local RD (GPU pass)
## or the CPU reference packer (fallback) — never the main thread. field_q
## and pot stay fp32 either way. The dict carries "packed" so the consumer
## can pick its unpacking path.
func readback_snapshot(packed := false) -> Dictionary:
	if _rd == null or not _ready:
		return {}
	if not _rd_global and _local_pending:
		_rd.sync()   # local RD: execute any un-synced submission before reading
		_local_pending = false
	var nc: int = grid_N * grid_N * grid_N
	var np1 := maxi(N_particles, 1)
	var pos; var vel
	if packed and _pack_pipe.is_valid():
		# GPU pack pass on the local RD: read the fp32 pos/vel buffers,
		# write the half-pair buffers, then read back HALF the bytes.
		_pack_pc_bytes.encode_u32(0, np1)
		var cl := _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(cl, _pack_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_pack_pos, 0)
		_rd.compute_list_set_push_constant(cl, _pack_pc_bytes, _pack_pc_bytes.size())
		_rd.compute_list_dispatch(cl, ceili(float(np1) / 64.0), 1, 1)
		_rd.compute_list_bind_uniform_set(cl, _us_pack_vel, 0)
		_rd.compute_list_dispatch(cl, ceili(float(np1) / 64.0), 1, 1)
		_rd.compute_list_end()
		_rd.submit()
		_local_pending = true
		_rd.sync()
		_local_pending = false
		pos = _rd.buffer_get_data(_pos_packed_buf, 0, np1 * 8)
		vel = _rd.buffer_get_data(_vel_packed_buf, 0, np1 * 8)
	elif packed:
		# CPU fallback (pack shader unavailable): same byte layout, packed
		# on the worker thread — the main thread never pays the packing.
		pos = _pack_f16_pairs(_rd.buffer_get_data(_pos_buf, 0, np1 * 16).to_float32_array())
		vel = _pack_f16_pairs(_rd.buffer_get_data(_vel_buf, 0, np1 * 16).to_float32_array())
	else:
		pos = _rd.buffer_get_data(_pos_buf, 0, np1 * 16).to_float32_array()
		vel = _rd.buffer_get_data(_vel_buf, 0, np1 * 16).to_float32_array()
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
		"packed": packed,
	}


# ── fp16 (half) conversion — IEEE-754 f32 → f16 with round-to-nearest-even.
# GDScript has no builtin; the bit twiddle mirrors packHalf2x16's rounding
# (SPIR-V OpQuantizeToF16). The per-value _f32_to_f16 is the reference the
# probes verify; the BULK packers use the bits-core directly (no per-value
# allocations on the hot path). The byte layout is the same everywhere:
# two halfs per uint32, low half first: (half(a) | half(b) << 16). ──
static var _f16_scratch := PackedByteArray([0, 0, 0, 0])


static func _f32_to_f16(v: float) -> int:
	_f16_scratch.encode_float(0, v)
	return _f32_bits_to_f16(_f16_scratch.decode_u32(0))


## f32 IEEE-754 bits → f16 bits (round-to-nearest-even on the 13 dropped
## mantissa bits; ties round to even — the GLSL packHalf2x16 convention).
static func _f32_bits_to_f16(u: int) -> int:
	var sign := (u >> 16) & 0x8000
	var exp := (u >> 23) & 0xFF
	var mant := u & 0x7FFFFF
	if exp == 0xFF:
		if mant == 0:
			return sign | 0x7C00              # ±inf
		return sign | 0x7C00 | (mant >> 13)   # NaN (payload truncated)
	var e: int = exp - 127 + 15
	if e >= 0x1F:
		return sign | 0x7C00                  # overflow → ±inf
	if e <= 0:
		# |v| < 2^-14: below the f16 normal range → ±0. Subnormal f16
		# (down to 2^-24) would round here, but the sim's positions/
		# velocities/masses never live in that band — invisible at box
		# scale (and the render side shares the exact same quantization).
		return sign
	var half := sign | (e << 10) | (mant >> 13)
	var rem := mant & 0x1FFF
	if rem > 0x1000 or (rem == 0x1000 and ((half >> 10) & 1) == 1):
		half += 1
	return half


## f16 bits → f32 (exact — used by the round-trip probe).
static func _f16_to_f32(h: int) -> float:
	var sign := -1.0 if (h & 0x8000) != 0 else 1.0
	var exp := (h >> 10) & 0x1F
	var mant := h & 0x3FF
	if exp == 0x1F:
		return INF if mant == 0 else NAN
	if exp == 0:
		return sign * (float(mant) * pow(2.0, -24.0))
	return sign * (1.0 + float(mant) / 1024.0) * pow(2.0, float(exp - 15))


## Bulk pack: PackedFloat32Array → half-pair PackedByteArray (2 floats per
## uint32). Byte-identical to the GPU pack pass (cassi_pack_f16.glsl).
static func _pack_f16_pairs(f32: PackedFloat32Array) -> PackedByteArray:
	var n := f32.size()
	var out := PackedByteArray()
	out.resize(ceili(float(n) / 2.0) * 4)
	var bytes := f32.to_byte_array()
	var oi := 0
	var i := 0
	while i + 1 < n:
		out.encode_u32(oi, _f32_bits_to_f16(bytes.decode_u32(i * 4))
				| (_f32_bits_to_f16(bytes.decode_u32((i + 1) * 4)) << 16))
		oi += 4
		i += 2
	if i < n:
		out.encode_u32(oi, _f32_bits_to_f16(bytes.decode_u32(i * 4)))
	return out


## Bulk unpack: half-pair PackedByteArray → PackedFloat32Array (the mirror
## of _pack_f16_pairs — the CPU round-trip reference for the probes).
static func _unpack_f16_pairs(packed: PackedByteArray, n_floats: int) -> PackedFloat32Array:
	var out := PackedFloat32Array()
	out.resize(n_floats)
	var n_pairs := packed.size() / 4
	var i := 0
	var oi := 0
	while i + 1 < n_floats and oi < n_pairs:
		var w: int = packed.decode_u32(oi * 4)
		out[i] = _f16_to_f32(w & 0xFFFF)
		out[i + 1] = _f16_to_f32(w >> 16)
		i += 2
		oi += 1
	if i < n_floats and oi < n_pairs:
		out[i] = _f16_to_f32(packed.decode_u32(oi * 4) & 0xFFFF)
	return out


## The sim-UI telemetry (decoupled mode): the gravity telemetry buffer's
## saturation counters + q/π/ρ range at particles + the strided field-q
## mean — decoded exactly as the sim's _render_frame does — plus the
## eps/hubble/scale-factor members (inert defaults there too) and the
## effective river G after calibration.
## FIX C2: field_q_override (the field_q the caller already read in
## readback_snapshot, or empty to read it here) avoids a SECOND full field_q
## readback per publish — the snapshot and telemetry used to each pull nc×4.
func readback_telemetry(field_q_override: PackedFloat32Array = PackedFloat32Array()) -> Dictionary:
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
	var qf := field_q_override
	if qf.is_empty():
		var nc: int = grid_N * grid_N * grid_N
		qf = _rd.buffer_get_data(_field_q, 0, nc * 4).to_float32_array()
	if qf.size() > 0:
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
			"res://compute/cassi_bh_integrate.glsl",
			"res://compute/cassi_jfa.glsl",
			"res://compute/cassi_voronoi_cells.glsl",
			"res://compute/cassi_voronoi_raster.glsl",
			"res://compute/cassi_particle_merge.glsl",
			"res://compute/cassi_bh_accretion.glsl",
			"res://compute/cassi_pack_f16.glsl",
			"res://compute/cassi_exclusive_scan.glsl"]:
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
	_job_counter = 0
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
## path the sim's _run_physics_steps uses).
##
## FIX A (non-blocking bootstrap): the FIRST submit after start NEVER blocks
## the main thread on setup (previously it did `_setup_sem.wait()` — a ~3.5 s
## frozen startup at 2.5M particles with no feedback). Instead it immediately
## queues the job (the worker runs it right after setup() completes) and
## returns {}; the caller polls `setup_ready()` / `poll()` for the first
## publish. block=true on the first-call is IGNORED (still non-blocking) —
## callers that need the first snapshot must poll. job_meta rides into the
## job dict: "cadence" (publish every Kth job) and "packed" (fp16 half-pair).
func submit_steps(target: int, block := false, job_meta: Dictionary = {}) -> Dictionary:
	if not _thread_started:
		return {}
	if _wait_next:
		# Bootstrap (FIX A): queue immediately, never block on setup. The
		# worker processes the job right after setup() posts _setup_sem; the
		# publish lands in _res_result and poll()/setup_ready() observe it.
		_wait_next = false
		_job_mutex.lock()
		_job = {"target": target}
		_job.merge(job_meta)
		_job_pending = true
		_job_mutex.unlock()
		_job_sem.post()
		return {}
	_job_mutex.lock()
	_job = {"target": target}
	_job.merge(job_meta)
	_job_pending = true
	_job_mutex.unlock()
	_job_sem.post()
	if block:
		return _wait_executed(target)
	return {}


## FIX A: non-blocking readiness poll — true once the worker's setup() has
## finished (buffers/pipelines built). The bootstrap job is queued by the
## first submit_steps BEFORE setup completes, so the caller polls this +
## poll() until the first publish arrives; the main thread never blocks.
func setup_ready() -> bool:
	return _ready and _thread_started


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

## One job: run up to (target − executed) steps, then publish. The
## snapshot + telemetry readbacks run every Kth job (job "cadence", cfg
## snapshot_cadence default) — the publish cadence optimization: non-publish
## jobs carry ONLY {executed, step_count, t}, and the sim skips the mirror
## upload while still tracking the backlog/readouts. The first job always
## publishes (the bootstrap needs the immediate snapshot).
func _threaded_run_job(job: Dictionary) -> void:
	var target := int(job.get("target", _executed))
	if target > _executed:
		var steps := target - _executed
		# Tree consumer: stage the pre-batch meshless/pos state and submit a
		# tree job (cadence-gated); the freshest completed gradient then
		# feeds the batch's mode-5 nbody via run_steps(tree_grad).
		_tree_refresh_gradient()
		run_steps(steps, true, _tree_grad_cache)  # wait=true → submit+sync on the local RD
		_executed += steps
	var cadence := maxi(int(job.get("cadence", _snapshot_cadence)), 1)
	var publish := (_job_counter % cadence) == 0
	_job_counter += 1
	var res: Dictionary = {
		"executed": _executed,
		"step_count": _step_count,
		"t": _time,
	}
	if publish:
		var snap := readback_snapshot(bool(job.get("packed", false)))
		var tel := readback_telemetry(snap.get("field_q", PackedFloat32Array()))
		res["snapshot"] = snap
		res["telemetry"] = tel
	_res_mutex.lock()
	_res_result = res
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
			_cond_pipe, _bh_int_pipe, _jfa_pipe, _cell_pipe, _raster_pipe,
			_merge_pipe, _scan_pipe, _bh_acc_pipe, _pack_pipe,
			_two_fluid_shader, _nbody_shader, _poisson_shader,
			_mass_deposit_shader, _cond_shader, _bh_int_shader,
			_jfa_shader, _cell_shader, _raster_shader, _merge_shader, _scan_shader, _bh_acc_shader,
			_pack_shader,
			_field_ey, _field_ei, _field_q, _field_vel, _field_scratch,
			_fft_buf, _tel_buf, _grad_buf, _grad_buf2,
			_pos_buf, _vel_buf, _acc_buf, _cluster_buf, _bh_buf,
			_mass_density_buf, _mass_density_fix, _tree_grad,
			_pos_packed_buf, _vel_packed_buf,
			_merge_alive_buf, _merge_mass_buf, _merge_mom_buf, _merge_cen_buf,
			_merge_best_buf, _merge_sink_buf, _merge_spin_buf, _merge_mprev_buf, _merge_cc_buf, _merge_cs_buf,
			_merge_ch_buf, _merge_cl_buf, _merge_mc_buf, _merge_scr_buf,
			_ml_labels_a, _ml_labels_b, _ml_sites,
			_ml_psi_y, _ml_psi_i, _ml_pi_y, _ml_pi_i,
			_ml_lap_y, _ml_lap_i, _ml_vol,
			_ml_cen, _ml_remap, _ml_tmp_y, _ml_tmp_i, _ml_tmp_py, _ml_tmp_pi,
			_ml_grad_y, _ml_grad_i, _ml_lsm_y, _ml_lsm_i]:
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


## The sim's standalone lists (meshless JFA/cell/rebuild) never submit on
## the global RD (the renderer executes them); on a LOCAL RD a recorded but
## unsubmitted list never runs — submit+sync after each standalone list.
func _finish_standalone_list() -> void:
	if not _rd_global:
		_rd.submit()
		_rd.sync()
		_local_pending = false


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
	# Two-fluid PDE double-buffer scratch (vec4 per cell — pass A writes
	# the new field here, pass B copies to the canonical buffers; the
	# single-pass neighbor-stencil write race made the field 1-ULP
	# nondeterministic — see cassi_two_fluid.glsl). Fully overwritten each
	# pass A; zeroed once for allocator-reuse hygiene.
	_field_scratch = _rd.storage_buffer_create(nc * 16)
	var scr_zero := PackedByteArray(); scr_zero.resize(nc * 16)
	_rd.buffer_update(_field_scratch, 0, scr_zero.size(), scr_zero)
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
	# Mass density grid (float per cell — written by the deposit's convert
	# pass; see cassi_mass_deposit.glsl)
	_mass_density_buf = _rd.storage_buffer_create(nc * 4)
	# Zero it once: the tree arm stages rho BEFORE the first step's GPU
	# clear (the tree gather reads pre-deposit rho), and allocator reuse
	# otherwise leaves garbage there (a latent determinism bug — fixed in
	# the sim too, same commit).
	var md_zero := PackedFloat32Array()
	md_zero.resize(nc)
	_rd.buffer_update(_mass_density_buf, 0, md_zero.size() * 4, md_zero.to_byte_array())
	# Fixed-point deposit accumulator (uvec4 per cell = 4×uint8-digit sums
	# of the SCALE = 2^24 fixed-point deposits — the DETERMINISM fix: the
	# digit sums are exact under ANY atomic ordering, so the deposited
	# cell sums are bit-identical run-to-run; see cassi_mass_deposit.glsl).
	# Zeroed once here (same tree-arm reason); the per-step poisson clear
	# (mode 3) zeroes it every step WITH the float rho grid.
	_mass_density_fix = _rd.storage_buffer_create(nc * 16)
	var mdf_zero := PackedByteArray()
	mdf_zero.resize(nc * 16)
	_rd.buffer_update(_mass_density_fix, 0, mdf_zero.size(), mdf_zero)
	# Cell-centered ∇(g·Φ) field (vec4 per cell — rebuilt every step)
	_grad_buf = _rd.storage_buffer_create(nc * 16)
	# Dual-lattice ∇(g·Φ) (always allocated so dual_grid stays a LIVE toggle)
	_grad_buf2 = _rd.storage_buffer_create(nc * 16)
	# ── Cascade-multigrid coarse buffers (ALWAYS allocated so the nbody set-0
	# binding 9 is valid in every dispatch; the coarse CHAIN only dispatches
	# when cascade_level, and the nbody blend branch only runs on bh[0].x>0.5
	# — so the default-off path is numerically bit-identical). N_c = grid_N/2
	# (radix-2 Stockham constraint; see multigrid_design.md §(a)).
	_cascade_nc = grid_N / 2
	var cnc: int = _cascade_nc
	var cn3: int = cnc * cnc * cnc
	_cf_density_buf = _rd.storage_buffer_create(cn3 * 4)
	_cf_fft_buf = _rd.storage_buffer_create(cn3 * 8)
	_cf_grad_buf = _rd.storage_buffer_create(cn3 * 16)
	var cf_zero := PackedFloat32Array(); cf_zero.resize(cn3 * 4); cf_zero.fill(0.0)
	_rd.buffer_update(_cf_grad_buf, 0, cn3 * 16, cf_zero.to_byte_array())
	_cf_grad_pc_bytes = PackedByteArray(); _cf_grad_pc_bytes.resize(8 * 4)
	# Mode-5 tree seam: per-particle tree gradient (nbody set 1 binding 3).
	# Zeroed once at setup so an unused seam reads zero force instead of
	# stale allocator memory; run_steps uploads when a gradient is supplied.
	_tree_grad = _rd.storage_buffer_create(maxi(N_particles, 1) * 16)
	var tz := PackedFloat32Array()
	tz.resize(maxi(N_particles, 1) * 4)
	_rd.buffer_update(_tree_grad, 0, tz.size() * 4, tz.to_byte_array())
	# fp16 half-pair snapshot buffers (uvec2 per particle) — written by the
	# pack pass before the readback halves the transfer. Always allocated
	# (the fp32 path never reads them; zero-fill once for allocator hygiene).
	_pos_packed_buf = _rd.storage_buffer_create(maxi(N_particles, 1) * 8)
	_vel_packed_buf = _rd.storage_buffer_create(maxi(N_particles, 1) * 8)
	var pk_zero := PackedByteArray()
	pk_zero.resize(maxi(N_particles, 1) * 8)
	_rd.buffer_update(_pos_packed_buf, 0, pk_zero.size(), pk_zero)
	_rd.buffer_update(_vel_packed_buf, 0, pk_zero.size(), pk_zero)
	_pack_pc_bytes = PackedByteArray(); _pack_pc_bytes.resize(8)
	# ── Meshless arm buffers (allocated always; used only when meshless_mode
	# is on — the sim's precedent). The JFA labels ping-pong; the per-site
	# state carries the cell averages; the rebuild scratch rides the GPU.
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	_ml_labels_a = _rd.storage_buffer_create(grid_N * grid_N * grid_N * 4)
	_ml_labels_b = _rd.storage_buffer_create(grid_N * grid_N * grid_N * 4)
	_ml_sites = _rd.storage_buffer_create(ml_ns * 16)
	_ml_psi_y = _rd.storage_buffer_create(ml_ns * 4)
	_ml_psi_i = _rd.storage_buffer_create(ml_ns * 4)
	_ml_pi_y = _rd.storage_buffer_create(ml_ns * 4)
	_ml_pi_i = _rd.storage_buffer_create(ml_ns * 4)
	_ml_lap_y = _rd.storage_buffer_create(ml_ns * 4)
	_ml_lap_i = _rd.storage_buffer_create(ml_ns * 4)
	_ml_vol = _rd.storage_buffer_create(ml_ns * 4)
	_ml_cen = _rd.storage_buffer_create(ml_ns * 16)
	_ml_remap = _rd.storage_buffer_create(ml_ns * 4)
	_ml_tmp_y = _rd.storage_buffer_create(ml_ns * 4)
	_ml_tmp_i = _rd.storage_buffer_create(ml_ns * 4)
	_ml_tmp_py = _rd.storage_buffer_create(ml_ns * 4)
	_ml_tmp_pi = _rd.storage_buffer_create(ml_ns * 4)
	_ml_grad_y = _rd.storage_buffer_create(ml_ns * 16)
	_ml_grad_i = _rd.storage_buffer_create(ml_ns * 16)
	_ml_lsm_y = _rd.storage_buffer_create(ml_ns * 3 * 16)
	_ml_lsm_i = _rd.storage_buffer_create(ml_ns * 3 * 16)
	_ml_tree_nsrc = ml_ns
	_jfa_pc_bytes = PackedByteArray(); _jfa_pc_bytes.resize(8 * 4)
	_cell_pc_bytes = PackedByteArray(); _cell_pc_bytes.resize(17 * 4)
	_raster_pc_bytes = PackedByteArray(); _raster_pc_bytes.resize(8 * 4)
	_ml_ready = false
	_ml_step_count = 0

	# ── Particle-merge buffers (INIT-TIME: allocated only when particle_merge)
	# The merge kernel's persistent per-particle state (alive/mass/mom/cen/
	# best/sink) + the spatial-hash scratch (cc/cs/ch/cl) + the merge counter.
	# Hash sized so each cell width ≥ R_m (the 27-neighbor pass_best provably
	# covers every in-range pair): hash_nx_i = ⌊2·extent_i/R_m⌋, which at the
	# default cube is exactly 2·grid_N per axis. R_m = ½·h₀ with h₀ =
	# 2·extent_min/grid_N (matches the sim's convention).
	if particle_merge and N_particles > 0:
		var ebox := _extents()
		var rem: float = _extent_min() / float(maxi(grid_N, 1))   # = R_m
		_merge_hash_nx = maxi(int(floor(2.0 * ebox.x / rem)), 8)
		_merge_hash_ny = maxi(int(floor(2.0 * ebox.y / rem)), 8)
		_merge_hash_nz = maxi(int(floor(2.0 * ebox.z / rem)), 8)
		_merge_hash_total = _merge_hash_nx * _merge_hash_ny * _merge_hash_nz
		var np1 := maxi(N_particles, 1)
		_merge_alive_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_mass_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_mom_buf = _rd.storage_buffer_create(np1 * 16)
		_merge_cen_buf = _rd.storage_buffer_create(np1 * 16)
		_merge_best_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_sink_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_spin_buf = _rd.storage_buffer_create(np1 * 16)
		_merge_mprev_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_cl_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_cc_buf = _rd.storage_buffer_create(_merge_hash_total * 4)
		_merge_cs_buf = _rd.storage_buffer_create(_merge_hash_total * 4)
		_merge_ch_buf = _rd.storage_buffer_create(_merge_hash_total * 4)
		_merge_mc_buf = _rd.storage_buffer_create(MERGE_MAX_CYCLES * 4)
		var mc_zero := PackedByteArray(); mc_zero.resize(MERGE_MAX_CYCLES * 4); mc_zero.fill(0)
		_rd.buffer_update(_merge_mc_buf, 0, mc_zero.size(), mc_zero)
		# On-GPU scan scratch (FIX B): L1 block totals + L2 two-level carries.
		var nb1 := (_merge_hash_total + 255) / 256
		_merge_nb1a = ((nb1 + 255) / 256) * 256
		_merge_nb2 = (nb1 + 255) / 256
		_merge_scr_buf = _rd.storage_buffer_create((_merge_nb1a + _merge_nb2) * 4)
		var scan_scr_zero := PackedByteArray(); scan_scr_zero.resize((_merge_nb1a + _merge_nb2) * 4)
		_rd.buffer_update(_merge_scr_buf, 0, scan_scr_zero.size(), scan_scr_zero)
		_merge_cell_wx = 2.0 * ebox.x / float(_merge_hash_nx)
		_merge_cell_wy = 2.0 * ebox.y / float(_merge_hash_ny)
		_merge_cell_wz = 2.0 * ebox.z / float(_merge_hash_nz)

	# Pre-allocate push-constant byte buffers (hitch-free pattern)
	_pc_bytes = PackedByteArray(); _pc_bytes.resize(11 * 4)
	_nbody_pc_bytes = PackedByteArray(); _nbody_pc_bytes.resize(15 * 4)
	_two_fluid_pc_bytes = PackedByteArray(); _two_fluid_pc_bytes.resize(15 * 4)  # + pass_sel (PDE pass A/B)
	_md_pc_bytes = PackedByteArray(); _md_pc_bytes.resize(9 * 4)  # + mode (deposit 0 / convert 1)
	_bh_int_pc_bytes = PackedByteArray(); _bh_int_pc_bytes.resize(4 * 4)
	_cond_pc_bytes = PackedByteArray(); _cond_pc_bytes.resize(4 * 4)
	_bh_acc_pc_bytes = PackedByteArray(); _bh_acc_pc_bytes.resize(4 * 4)
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
	# fp16 snapshot packing (worker-side; cassi_pack_f16.glsl) — always
	# built so readback_snapshot(packed=true) can halve the pos/vel
	# readback. Optional: on build failure the CPU packer takes over.
	_pack_shader = _shader_create("res://compute/cassi_pack_f16.glsl")
	if _pack_shader.is_valid():
		_pack_pipe = _rd.compute_pipeline_create(_pack_shader)
	# Particle merge (only when particle_merge; the pipeline + set are created
	# on the init-time toggle so the default-off path is bit-identical)
	if particle_merge:
		_merge_shader = _shader_create("res://compute/cassi_particle_merge.glsl")
		if _merge_shader.is_valid():
			_merge_pipe = _rd.compute_pipeline_create(_merge_shader)
		# On-GPU exclusive scan (FIX B) — only needed when the merge runs.
		_scan_shader = _shader_create("res://compute/cassi_exclusive_scan.glsl")
		if _scan_shader.is_valid():
			_scan_pipe = _rd.compute_pipeline_create(_scan_shader)
	# BH accretion (only when bh_accretion; the pipeline + set are created on
	# the init-time toggle so the default-off path is bit-identical)
	if bh_accretion:
		_bh_acc_shader = _shader_create("res://compute/cassi_bh_accretion.glsl")
		if _bh_acc_shader.is_valid():
			_bh_acc_pipe = _rd.compute_pipeline_create(_bh_acc_shader)
	# Cascade coarse-gradient (only when cascade_level; pipeline + set created
	# on the init-time toggle so the default-off path never loads the shader)
	if cascade_level:
		_cf_grad_shader = _shader_create("res://compute/cassi_coarse_grad.glsl")
		if _cf_grad_shader.is_valid():
			_cf_grad_pipe = _rd.compute_pipeline_create(_cf_grad_shader)
	# Meshless (Voronoi cell) arm — MESHLESS_PLAN.md §10
	_jfa_shader = _shader_create("res://compute/cassi_jfa.glsl")
	if _jfa_shader.is_valid():
		_jfa_pipe = _rd.compute_pipeline_create(_jfa_shader)
	_cell_shader = _shader_create("res://compute/cassi_voronoi_cells.glsl")
	if _cell_shader.is_valid():
		_cell_pipe = _rd.compute_pipeline_create(_cell_shader)
	_raster_shader = _shader_create("res://compute/cassi_voronoi_raster.glsl")
	if _raster_shader.is_valid():
		_raster_pipe = _rd.compute_pipeline_create(_raster_shader)
	_cache_uniform_sets()
	_ready = (_two_fluid_shader.is_valid() and _two_fluid_pipe.is_valid()
		and _nbody_shader.is_valid() and _nbody_pipe.is_valid()
		and _poisson_shader.is_valid() and _poisson_pipe.is_valid()
		and _mass_deposit_shader.is_valid() and _mass_deposit_pipe.is_valid()
		and _cond_shader.is_valid() and _cond_pipe.is_valid()
		and _bh_int_shader.is_valid() and _bh_int_pipe.is_valid())


func _cache_uniform_sets() -> void:
	# Two-fluid PDE declares ONLY set 0 (bindings 0-5: fields + rho + scratch)
	_us_two_0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		_uniform_storage(4, _mass_density_buf),
		_uniform_storage(5, _field_scratch),
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
		_uniform_storage(9, _cf_grad_buf),  # cascade coarse ∇(g·Φ)
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
	# fp16 pack pass sets (set 0: fp32 in binding 0 → half-pairs binding 1)
	if _pack_shader.is_valid():
		_us_pack_pos = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _pos_packed_buf),
		], _pack_shader, 0)
		_us_pack_vel = _rd.uniform_set_create([
			_uniform_storage(0, _vel_buf),
			_uniform_storage(1, _vel_packed_buf),
		], _pack_shader, 0)
	# Poisson solver (set 0: FFT workspace + mass density + telemetry +
	# the int64 fixed-point accumulator the clear pass zeroes)
	if _poisson_shader.is_valid():
		_us_poisson_0 = _rd.uniform_set_create([
			_uniform_storage(0, _fft_buf),
			_uniform_storage(1, _mass_density_buf),
			_uniform_storage(2, _tel_buf),
			_uniform_storage(3, _mass_density_fix),
		], _poisson_shader, 0)
	# Mass deposit (set 0: positions + float rho + int64 fix accumulator)
	if _mass_deposit_shader.is_valid():
		_us_mass_dep_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _mass_density_buf),
			_uniform_storage(2, _mass_density_fix),
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
	# Particle merge (set 0: all 15 bindings — pos/vel + per-particle state +
	# EY/EI coherence field + hash scratch + merge counter). Gated on the
	# init-time toggle (its buffers only exist then).
	if particle_merge and _merge_shader.is_valid() and _merge_alive_buf.is_valid():
		_us_merge_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf), _uniform_storage(1, _vel_buf),
			_uniform_storage(2, _merge_alive_buf), _uniform_storage(3, _merge_mass_buf),
			_uniform_storage(4, _merge_mom_buf), _uniform_storage(5, _merge_cen_buf),
			_uniform_storage(6, _field_ey), _uniform_storage(7, _field_ei),
			_uniform_storage(8, _merge_best_buf), _uniform_storage(9, _merge_sink_buf),
			_uniform_storage(10, _merge_cc_buf), _uniform_storage(11, _merge_cs_buf),
			_uniform_storage(12, _merge_ch_buf), _uniform_storage(13, _merge_cl_buf),
			_uniform_storage(14, _merge_mc_buf), _uniform_storage(15, _merge_spin_buf),
			_uniform_storage(16, _field_vel), _uniform_storage(17, _merge_mprev_buf),
		], _merge_shader, 0)
	# On-GPU scan set (FIX B): cc(15) → cs(16) + scr(17) two-level + ch(18).
	if particle_merge and _scan_shader.is_valid() and _merge_scr_buf.is_valid():
		_us_scan_0 = _rd.uniform_set_create([
			_uniform_storage(15, _merge_cc_buf),
			_uniform_storage(16, _merge_cs_buf),
			_uniform_storage(17, _merge_scr_buf),
			_uniform_storage(18, _merge_ch_buf),
		], _scan_shader, 0)
	# BH accretion (set 0: positions + BHData write)
	if bh_accretion and _bh_acc_shader.is_valid():
		_us_bh_acc_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _bh_buf),
		], _bh_acc_shader, 0)
	# Meshless arm sets (MESHLESS_PLAN.md §10) — the JFA ping-pong labels
	# + sites; the cell state; the raster outputs (the field grid buffers).
	if _jfa_shader.is_valid():
		_us_jfa_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_labels_a), _uniform_storage(1, _ml_labels_b),
			_uniform_storage(2, _ml_sites),
		], _jfa_shader, 0)
		_us_cell_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_labels_a), _uniform_storage(1, _ml_sites),
			_uniform_storage(2, _ml_psi_y), _uniform_storage(3, _ml_psi_i),
			_uniform_storage(4, _ml_pi_y), _uniform_storage(5, _ml_pi_i),
			_uniform_storage(6, _ml_lap_y), _uniform_storage(7, _ml_lap_i),
			_uniform_storage(8, _ml_vol), _uniform_storage(9, _mass_density_buf),
			_uniform_storage(10, _ml_cen), _uniform_storage(11, _ml_remap),
			_uniform_storage(12, _ml_tmp_y), _uniform_storage(13, _ml_tmp_i),
			_uniform_storage(14, _ml_tmp_py), _uniform_storage(15, _ml_tmp_pi),
			_uniform_storage(16, _ml_grad_y), _uniform_storage(17, _ml_grad_i),
			_uniform_storage(18, _ml_lsm_y), _uniform_storage(19, _ml_lsm_i),
		], _cell_shader, 0)
	if _raster_shader.is_valid():
		_us_raster_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_labels_a), _uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i), _uniform_storage(3, _field_ey),
			_uniform_storage(4, _field_ei), _uniform_storage(5, _field_q),
			_uniform_storage(6, _ml_grad_y), _uniform_storage(7, _ml_grad_i),
			_uniform_storage(8, _ml_sites),
		], _raster_shader, 0)


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
	_ml_ready = false
	if meshless_mode:
		_meshless_init()


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
# Meshless (moving-Voronoi) arm — ported verbatim from cassi_sim.gd
# (MESHLESS_PLAN.md §10). The PDE runs on the JFA Voronoi cell mesh and
# rasterizes back to the grid buffers, so readback_snapshot() keeps working
# unchanged (the field_q it reads is the rasterized output).
# ═══════════════════════════════════════════════════════════════════════

func _meshless_init() -> void:
	var N := grid_N
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var ext := _extents()
	var hx: float = 2.0 * ext.x / float(N)
	var hy: float = 2.0 * ext.y / float(N)
	var hz: float = 2.0 * ext.z / float(N)
	var Lx: float = hx * float(N)
	var Ly: float = hy * float(N)
	var Lz: float = hz * float(N)
	# BCC lattice: two cubic sublattices offset by half a spacing, one
	# per axis (the anisotropic analog of the cube's uniform spacing)
	var rng := RandomNumberGenerator.new()
	rng.seed = 20260813
	var sx: float = Lx / float(ML_N1)
	var sy: float = Ly / float(ML_N1)
	var sz: float = Lz / float(ML_N1)
	var sites := PackedFloat32Array()
	for i in range(ML_N1):
		for j in range(ML_N1):
			for k in range(ML_N1):
				sites.append_array(PackedFloat32Array([
					float(i) * sx + rng.randf_range(-0.2, 0.2) * sx,
					float(j) * sy + rng.randf_range(-0.2, 0.2) * sy,
					float(k) * sz + rng.randf_range(-0.2, 0.2) * sz,
					0.0]))
				sites.append_array(PackedFloat32Array([
					(float(i) + 0.5) * sx + rng.randf_range(-0.2, 0.2) * sx,
					(float(j) + 0.5) * sy + rng.randf_range(-0.2, 0.2) * sy,
					(float(k) + 0.5) * sz + rng.randf_range(-0.2, 0.2) * sz,
					0.0]))
	for m in range(sites.size() / 4):
		sites[m * 4] = fposmod(sites[m * 4], Lx)
		sites[m * 4 + 1] = fposmod(sites[m * 4 + 1], Ly)
		sites[m * 4 + 2] = fposmod(sites[m * 4 + 2], Lz)
	_ml_sites_cpu = sites
	_rd.buffer_update(_ml_sites, 0, sites.size() * 4, sites.to_byte_array())

	# scatter (min-index per cell — the GPU atomicMin analog) + JFA
	_ml_scatter_and_jfa()
	# volume pass (hx·hy·hz per cell, atomic)
	_ml_volume_pass()
	# per-site state: trilinear sample of the grid IC (the mesh world
	# [0, Lx)×[0, Ly)×[0, Lz) maps to the sim's world x = s − extent:
	# grid coord = s.x/hx etc.)
	var ey_f := _rd.buffer_get_data(_field_ey, 0, N * N * N * 4).to_float32_array()
	var ei_f := _rd.buffer_get_data(_field_ei, 0, N * N * N * 4).to_float32_array()
	var psi_y := PackedFloat32Array()
	var psi_i := PackedFloat32Array()
	psi_y.resize(ml_ns)
	psi_i.resize(ml_ns)
	for s in range(ml_ns):
		var gx: float = fposmod(sites[s * 4], Lx) / hx
		var gy: float = fposmod(sites[s * 4 + 1], Ly) / hy
		var gz: float = fposmod(sites[s * 4 + 2], Lz) / hz
		var i0: int = int(floor(gx)) % N
		var j0: int = int(floor(gy)) % N
		var k0: int = int(floor(gz)) % N
		var i1: int = (i0 + 1) % N
		var j1: int = (j0 + 1) % N
		var k1: int = (k0 + 1) % N
		var fx: float = gx - floor(gx)
		var fy: float = gy - floor(gy)
		var fz: float = gz - floor(gz)
		psi_y[s] = _ml_tri(ey_f, i0, j0, k0, i1, j1, k1, fx, fy, fz)
		psi_i[s] = _ml_tri(ei_f, i0, j0, k0, i1, j1, k1, fx, fy, fz)
	_rd.buffer_update(_ml_psi_y, 0, psi_y.size() * 4, psi_y.to_byte_array())
	_rd.buffer_update(_ml_psi_i, 0, psi_i.size() * 4, psi_i.to_byte_array())
	var zero := PackedFloat32Array()
	zero.resize(ml_ns)
	_rd.buffer_update(_ml_pi_y, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_ml_pi_i, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_ml_lap_y, 0, zero.size() * 4, zero.to_byte_array())
	_rd.buffer_update(_ml_lap_i, 0, zero.size() * 4, zero.to_byte_array())
	_ml_step_count = 0
	_ml_ready = true
	print("[PhysicsEngine] Meshless arm ready: %d Voronoi cells on the %d^3 accelerator grid"
		% [ml_ns, N])


func _ml_tri(a: PackedFloat32Array, i0: int, j0: int, k0: int,
		i1: int, j1: int, k1: int, fx: float, fy: float, fz: float) -> float:
	var N := grid_N
	var c00 := a[i0 * N * N + j0 * N + k0] * (1.0 - fx) + a[i1 * N * N + j0 * N + k0] * fx
	var c01 := a[i0 * N * N + j0 * N + k1] * (1.0 - fx) + a[i1 * N * N + j0 * N + k1] * fx
	var c10 := a[i0 * N * N + j1 * N + k0] * (1.0 - fx) + a[i1 * N * N + j1 * N + k0] * fx
	var c11 := a[i0 * N * N + j1 * N + k1] * (1.0 - fx) + a[i1 * N * N + j1 * N + k1] * fx
	var c0 := c00 * (1.0 - fy) + c10 * fy
	var c1 := c01 * (1.0 - fy) + c11 * fy
	return c0 * (1.0 - fz) + c1 * fz


func _ml_scatter_and_jfa() -> void:
	var N := grid_N
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var labels := PackedInt32Array()
	labels.resize(N * N * N)
	labels.fill(ML_INT_MAX)
	var ext := _extents()
	var hx: float = 2.0 * ext.x / float(N)
	var hy: float = 2.0 * ext.y / float(N)
	var hz: float = 2.0 * ext.z / float(N)
	for s in range(ml_ns):
		var gi: int = int(floor(_ml_sites_cpu[s * 4] / hx)) % N
		var gj: int = int(floor(_ml_sites_cpu[s * 4 + 1] / hy)) % N
		var gk: int = int(floor(_ml_sites_cpu[s * 4 + 2] / hz)) % N
		var idx: int = gi * N * N + gj * N + gk
		if labels[idx] > s:
			labels[idx] = s
	_rd.buffer_update(_ml_labels_a, 0, labels.size() * 4, labels.to_byte_array())
	# jumps: doubling 1..N/2, halving sweep, then two jump-1 refinement
	# passes — JFA's index-space flood leaves a tiny fraction of ambiguous
	# boundary cells on a STRETCHED box; repeating the complete-graph
	# jump-1 pass converges them to the exact Voronoi. Two passes keep the
	# count odd so the identity copy B → A still re-homes the result.
	var jumps: Array[int] = [1, 2, 4, 8, 16, 32, 16, 8, 4, 2, 1, 1, 1]
	var read_a := 1
	for jp in jumps:
		_ml_jfa_pass(jp, read_a)
		read_a = 1 - read_a
	_ml_jfa_pass(0, 0)  # identity copy B → A (odd pass count leaves result in B)


func _ml_jfa_pass(jp: int, read_a: int) -> void:
	var N := grid_N
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var ext := _extents()
	var pcb := PackedFloat32Array([float(N), float(jp), float(read_a),
		float(ml_ns), 2.0 * ext.x / float(N), 2.0 * ext.y / float(N),
		2.0 * ext.z / float(N), 0.0])
	_jfa_pc_bytes = pcb.to_byte_array()
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _jfa_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_jfa_0, 0)
	_rd.compute_list_set_push_constant(cl, _jfa_pc_bytes, _jfa_pc_bytes.size())
	_rd.compute_list_dispatch(cl, N * N * N / 64, 1, 1)
	_rd.compute_list_end()
	_finish_standalone_list()


func _ml_volume_pass() -> void:
	var N := grid_N
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var zero := PackedFloat32Array()
	zero.resize(ml_ns)
	_rd.buffer_update(_ml_vol, 0, zero.size() * 4, zero.to_byte_array())
	_ml_cell_dispatch(2.0, N * N * N / 64)


func _ml_cell_pc(mode: float) -> PackedByteArray:
	var N := grid_N
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var ext := _extents()
	var hx: float = 2.0 * ext.x / float(N)
	var hy: float = 2.0 * ext.y / float(N)
	var hz: float = 2.0 * ext.z / float(N)
	var h_min: float = minf(hx, minf(hy, hz))
	var c2: float = h_min * h_min  # the grid's 19-point stencil reads h₀²∇² — match it
	var pcb := PackedFloat32Array([mode, float(N), float(ml_ns), dt,
		hx, hy, hz, c2, ML_OM2, PHI, source_strength,
		ML_RHO_FLOOR, ML_MAX_DRIFT, ML_KAPPA, ML_LAM,
		dt * float(ML_REBUILD), ML_LLOYD_P])
	return pcb.to_byte_array()


func _ml_cell_dispatch(mode: float, groups: int) -> void:
	_cell_pc_bytes = _ml_cell_pc(mode)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, groups, 1, 1)
	_rd.compute_list_end()
	_finish_standalone_list()


func _mesh_rebuild() -> void:
	# The FULL GPU rebuild (the sim's stutter fix): steering + ALE remap +
	# JFA refresh as ONE compute list with barriers — zero readbacks, zero
	# CPU loops. Chain: reset(vol+cen) → centroid(OLD mesh) → steer(new
	# sites + remap idx) → state→tmp → tmp→state (the remap gather) →
	# labels clear → scatter → JFA (ping-pong passes share this list) →
	# volume.
	var N := grid_N
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var ext_rb := _extents()
	var hx_rb: float = 2.0 * ext_rb.x / float(N)
	var hy_rb: float = 2.0 * ext_rb.y / float(N)
	var hz_rb: float = 2.0 * ext_rb.z / float(N)
	var wg1 := N * N * N / 64
	var wgs := int(ceil(float(ml_ns) / 64.0))
	_cell_pc_bytes = _ml_cell_pc(7.0)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	# 1. reset vol + cen
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 2. centroid accumulate (the OLD mesh)
	_cell_pc_bytes = _ml_cell_pc(3.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 3. steer: new sites + remap index (reads the OLD labels)
	_cell_pc_bytes = _ml_cell_pc(4.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 4. ALE remap: state → temp → gathered state
	_cell_pc_bytes = _ml_cell_pc(5.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	_cell_pc_bytes = _ml_cell_pc(6.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 5. labels clear + scatter (the NEW sites)
	_cell_pc_bytes = _ml_cell_pc(8.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	_cell_pc_bytes = _ml_cell_pc(9.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 6. JFA (the ping-pong passes share this list)
	_rd.compute_list_bind_compute_pipeline(cl, _jfa_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_jfa_0, 0)
	var read_a := 1
	for jp in [1, 2, 4, 8, 16, 32, 16, 8, 4, 2, 1, 1, 1]:
		_jfa_pc_bytes = PackedFloat32Array([float(N), float(jp), float(read_a),
			float(ml_ns), hx_rb, hy_rb, hz_rb, 0.0]).to_byte_array()
		_rd.compute_list_set_push_constant(cl, _jfa_pc_bytes, _jfa_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		read_a = 1 - read_a
	_jfa_pc_bytes = PackedFloat32Array([float(N), 0.0, 0.0,
		float(ml_ns), hx_rb, hy_rb, hz_rb, 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _jfa_pc_bytes, _jfa_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 7. volume accumulate (the NEW mesh)
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	_cell_pc_bytes = _ml_cell_pc(2.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_end()
	_finish_standalone_list()


# ── Tree-worker CONSUMER (decoupled mode) ───────────────────────────────
# The sim creates + starts cassi_tree_worker.gd on the MAIN thread (its
# start() loads the tree shaders — not thread-safe off-main) and hands the
# object via cfg.tree_worker. This ENGINE worker stages the tree job from
# ITS OWN RD (it owns the meshless/pos buffers now) and calls
# submit()/poll() from its thread (pure mutex/semaphore — thread-agnostic;
# the tree worker's RD work stays on its own thread). The freshest
# completed gradient is cached and fed into run_steps(tree_grad=...), which
# uploads it to the nbody mode-5 seam buffer.

## Stage + submit a tree job and refresh the gradient cache (cadence-gated:
## the sim's _tree_local_cadence semantics — default 1 = every physics job).
func _tree_refresh_gradient() -> void:
	if not meshless_mode or not meshless_gravity or _tree_worker == null or not _ml_ready:
		return
	if _ml_tree_nsrc <= 0:
		return
	_tree_job_counter += 1
	if _tree_cadence > 1 and _tree_job_counter % _tree_cadence != 1:
		return  # skip this job (stale-but-recent gradient is fine for 1/K)
	var S := _ml_tree_nsrc
	var N3 := grid_N * grid_N * grid_N
	var Np: int = N_particles
	var ext := _extents()
	var half: float = maxf(ext.x, maxf(ext.y, maxf(ext.z, ext.z))) * 1.000001
	# Stage the CURRENT meshless source state from THIS engine's RD (the
	# worker consumes copies — no shared buffers with the sim).
	var job := {
		"sites": _rd.buffer_get_data(_ml_sites, 0, S * 16).to_float32_array(),
		"psy": _rd.buffer_get_data(_ml_psi_y, 0, S * 4).to_float32_array(),
		"psi": _rd.buffer_get_data(_ml_psi_i, 0, S * 4).to_float32_array(),
		"vol": _rd.buffer_get_data(_ml_vol, 0, S * 4).to_float32_array(),
		"rho": _rd.buffer_get_data(_mass_density_buf, 0, N3 * 4).to_float32_array(),
		"pos": _rd.buffer_get_data(_pos_buf, 0, Np * 16).to_float32_array(),
		"ext": ext,
		"half": half,
		"S": S,
		"N3": N3,
		"Np": Np,
		"grid_N": grid_N,
		"eps2": ML_TREE_EPS2_FRAC * ML_TREE_EPS2_FRAC * _extent_min() * _extent_min(),
		"tnm": ML_TREE_NODE_MAX_MULT * S + 64,
	}
	var res: Dictionary = _tree_worker.submit(job)   # blocks only on the bootstrap tree job
	if res.is_empty():
		res = _tree_worker.poll()
	if not res.is_empty():
		var grad: PackedFloat32Array = res.get("grad", PackedFloat32Array())
		if grad.size() == Np * 4:
			_tree_grad_cache = grad


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
	_md_pc_bytes.encode_float(32, 0.0)  # mode 0 = deposit (1 = convert)
	# BH integrate PC: [N_f, dt, acc_rate, max_age]
	_bh_int_pc_bytes.encode_float(0, float(grid_N))
	_bh_int_pc_bytes.encode_float(4, dt)
	_bh_int_pc_bytes.encode_float(8, bh_acc_rate)
	_bh_int_pc_bytes.encode_float(12, bh_max_age)
	# Condensation PC: [N_f, qi_threshold, _, _]
	_cond_pc_bytes.encode_float(0, float(grid_N))
	_cond_pc_bytes.encode_float(4, qi_condensation_threshold)
	# BH accretion PC: [N_f, np, r_acc, _]
	_bh_acc_pc_bytes.encode_float(0, float(grid_N))
	_bh_acc_pc_bytes.encode_float(4, float(N_particles))
	_bh_acc_pc_bytes.encode_float(8, bh_accretion_radius)

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
		_rd.compute_list_dispatch(cl, grid_N, grid_N / 2, 1)  # 2D cells dispatch (2 cells/thread)
	_barrier(cl)  # clear → deposit

	# ── 1. Mass deposit: scatter particle masses → int64 fixed-point grid ──
	if _mass_deposit_shader.is_valid() and N_particles > 0:
		_md_pc_bytes.encode_float(32, 0.0)  # mode 0 = deposit
		_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_0, 0)
		_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
	_barrier(cl)  # deposit → convert (int64 atomic visibility)

	# ── 1.2. Fixed-point → float convert: rho = fix / SCALE ──────────
	# The exact uint64 cell sum is converted once per cell to the float
	# mass-density grid the Poisson/PDE/tree chain reads. Deterministic
	# (a single rounding of an exact integer sum — no float atomic order).
	# Runs unconditionally in principle (with no deposit the clear left
	# fix == 0, so rho is written 0 — the same empty state), but MUST be
	# skipped when the deposit uniform set is invalid: at N_particles == 0
	# the particle buffers are zero-size (Vk buffer-create fails → RID()),
	# so _us_mass_dep_0 could not be created and binding it would error.
	if _mass_deposit_shader.is_valid() and _us_mass_dep_0.is_valid():
		_md_pc_bytes.encode_float(32, 1.0)  # mode 1 = convert
		_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_0, 0)
		_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
		_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)  # 2D cells dispatch
	_barrier(cl)  # convert → poisson (float rho visibility)

	# ── 1.5. Spectral Poisson solve: ∇²Φ = ρ_mass ─────────────────────
	# RIVER MODES ONLY (0, 3 and 4); SKIPPED under tree gravity
	# (meshless_mode && meshless_gravity — the octree replaces the solve).
	if (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) \
			and not (meshless_mode and meshless_gravity):
		_dispatch_poisson(cl)
	_barrier(cl)  # deposit → PDE (rho visibility for the PDE source)

	# ── 2. Two-fluid PDE — grid solver, or the meshless Voronoi arm ──
	# freeze_field (diagnostic): the field is initialized once and left
	# fixed — the PDE evolution passes are skipped while the gravity/
	# particle path runs unchanged.
	if meshless_mode and _ml_ready and _cell_pipe.is_valid() and not freeze_field:
		# Meshless (MESHLESS_PLAN.md §10): cell lap + leapfrog on the
		# Voronoi mesh, then rasterize the cell state back into the grid
		# field buffers (readback_snapshot reads the rasterized output).
		# The accelerator grid is a lookup accelerator only.
		var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
		var wg1 := grid_N * grid_N * grid_N / 64
		var ext_r := _extents()
		var hxr: float = 2.0 * ext_r.x / float(grid_N)
		var hyr: float = 2.0 * ext_r.y / float(grid_N)
		var hzr: float = 2.0 * ext_r.z / float(grid_N)
		_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
		# grad zero → lap (the lap pass also accumulates the least-squares M+b)
		_cell_pc_bytes = _ml_cell_pc(10.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, int(ceil(float(ml_ns) / 64.0)), 1, 1)
		_barrier(cl)  # grad zero → lap
		_cell_pc_bytes = _ml_cell_pc(0.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
		_barrier(cl)  # lap → leapfrog
		_cell_pc_bytes = _ml_cell_pc(1.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, int(ceil(float(ml_ns) / 64.0)), 1, 1)
		_barrier(cl)  # leapfrog → gradient solve
		# least-squares solve g = M⁻¹·b per site (into grad)
		_cell_pc_bytes = _ml_cell_pc(12.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, int(ceil(float(ml_ns) / 64.0)), 1, 1)
		_barrier(cl)  # solve → raster
		_rd.compute_list_bind_compute_pipeline(cl, _raster_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_raster_0, 0)
		_raster_pc_bytes = PackedFloat32Array([float(grid_N), float(ml_ns),
			hxr, hyr, hzr, 0.0, 0.0, 0.0]).to_byte_array()
		_rd.compute_list_set_push_constant(cl, _raster_pc_bytes, _raster_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
	elif _two_fluid_shader.is_valid() and not freeze_field:
		_rd.compute_list_bind_compute_pipeline(cl, _two_fluid_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_two_0, 0)
		# Two-pass double-buffered PDE (DETERMINISM fix): pass A computes
		# the new field into the scratch buffer (reads canonical, writes
		# scratch — no in-dispatch aliasing), pass B copies scratch to the
		# canonical field. The old single pass read a 19-point neighbor
		# stencil and wrote the same buffers in one dispatch — a genuine
		# read-after-write race (1-ULP field nondeterminism run-to-run).
		_two_fluid_pc_bytes.encode_float(56, 0.0)  # pass_sel = A
		_rd.compute_list_set_push_constant(cl, _two_fluid_pc_bytes, _two_fluid_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg, wg, wg)
		_barrier(cl)  # PDE pass A → pass B (scratch visibility)
		_two_fluid_pc_bytes.encode_float(56, 1.0)  # pass_sel = B
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

	# ── 2.65. BH accretion (every step, when enabled): particles within a BH's
	# accretion radius are swallowed (pos.w = 0, mass Δ added atomically to the
	# BH record). Pure GPU, no host readback — one dispatch, one thread per
	# particle. Reads bh[4..] (written by condensation/BH-integrate above) and
	# this step's pos; the barrier after gives the nbody pass visibility.
	if _bh_acc_shader.is_valid() and bh_accretion and black_holes_enabled:
		_rd.compute_list_bind_compute_pipeline(cl, _bh_acc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_bh_acc_0, 0)
		_rd.compute_list_set_push_constant(cl, _bh_acc_pc_bytes, _bh_acc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
	_barrier(cl)  # BH integrate/accretion → gradient

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
			_rd.compute_list_dispatch(cl, grid_N, grid_N / 2, 1)  # 2D cells dispatch (2 cells/thread)
		_barrier(cl)  # dual clear → deposit
		if _mass_deposit_shader.is_valid() and N_particles > 0:
			_md_pc_bytes.encode_float(20, ext_step.x / float(grid_N))
			_md_pc_bytes.encode_float(24, ext_step.y / float(grid_N))
			_md_pc_bytes.encode_float(28, ext_step.z / float(grid_N))
			_md_pc_bytes.encode_float(32, 0.0)  # mode 0 = deposit
			_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
			_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_0, 0)
			_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
			_rd.compute_list_dispatch(cl, pg, 1, 1)
		_barrier(cl)  # dual deposit → convert
		# Dual-lattice convert: the SAME fix buffer was re-cleared by the
		# dual clear → the shifted deposit accumulates fresh → convert to
		# rho for the shifted Poisson solve (one int64 buffer, mirroring
		# the float semantics exactly).
		if _mass_deposit_shader.is_valid() and _us_mass_dep_0.is_valid():
			_md_pc_bytes.encode_float(32, 1.0)  # mode 1 = convert
			_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
			_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_0, 0)
			_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
			_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)
		_barrier(cl)  # dual convert → poisson
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


# load+x → FFT(y) → FFT(z) → Φ̂=−ρ̂/k² (k=0 nulled) → IFFT(z) → IFFT(y) → IFFT(x)
# FUSED (cassi_poisson.glsl modes 4/5): mode 4 = load ρ + forward-x in one
# pass; mode 5 = the k-space multiply fused into the inverse-z pass. 6
# dispatches per solve instead of 8 — 2 fewer global barriers. All FFT
# passes are multi-row: R = 256/grid_N rows per workgroup → dispatch
# (grid_N, grid_N²/256, 1) instead of (grid_N, grid_N, 1).
func _dispatch_poisson(cl: int) -> void:
	if not _poisson_shader.is_valid():
		return
	_rd.compute_list_bind_compute_pipeline(cl, _poisson_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_poisson_0, 0)
	# The per-axis extents ride along for the kspace multiply (fused into
	# mode 5) — the FFT passes only touch floats 4/8/12.
	var ext_p: Vector3 = _extents()
	var n := grid_N
	var fft_groups_y := maxi(n * n / 256, 1)  # R = 256/n rows/workgroup
	_poisson_pc_bytes.encode_float(0, float(n)); _poisson_pc_bytes.encode_float(4, 0.0)
	_poisson_pc_bytes.encode_float(8, 0.0); _poisson_pc_bytes.encode_float(12, 0.0)
	_poisson_pc_bytes.encode_float(16, ext_p.x)
	_poisson_pc_bytes.encode_float(20, ext_p.y)
	_poisson_pc_bytes.encode_float(24, ext_p.z)
	# mode 4: fused load ρ → forward x (reads ρ directly, no load pass)
	_poisson_pc_bytes.encode_float(12, 4.0)
	_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
	_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)  # 2D rows dispatch
	_barrier(cl)  # load+x → fwd y
	# mode 1: forward FFT passes y, z
	for axis in [1, 2]:
		_poisson_pc_bytes.encode_float(4, float(axis))
		_poisson_pc_bytes.encode_float(8, 0.0)   # forward
		_poisson_pc_bytes.encode_float(12, 1.0)
		_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
		_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)  # 2D rows dispatch
		_barrier(cl)  # FFT passes: memory visibility between stages
	# mode 5: k-space multiply Φ̂ = −ρ̂/k² fused into the inverse-z pass
	# (BETWEEN fwd and inv — required; the multiply rides the z-row load)
	_poisson_pc_bytes.encode_float(4, 2.0)
	_poisson_pc_bytes.encode_float(8, 1.0)   # inverse
	_poisson_pc_bytes.encode_float(12, 5.0)
	_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
	_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)  # 2D rows dispatch
	_barrier(cl)  # fwd z → inv-z (kspace applied)
	# mode 1: inverse FFT passes y, x (scaled 1/N each)
	for axis in [1, 0]:
		_poisson_pc_bytes.encode_float(4, float(axis))
		_poisson_pc_bytes.encode_float(8, 1.0)   # inverse
		_poisson_pc_bytes.encode_float(12, 1.0)
		_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
		_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)  # 2D rows dispatch
		_barrier(cl)  # inverse FFT passes


# ═══════════════════════════════════════════════════════════════════════
# Cassi particle merge (compute/cassi_particle_merge.glsl) — the engine-side
# port. Runs on the LOCAL-RD worker AFTER each run_steps batch, where
# submit()+sync() per cycle makes the host CPU prefix-sum readbacks legal
# (the global RD cannot submit — see merge_wiring_notes.md §2).
# ═══════════════════════════════════════════════════════════════════════
const MERGE_MAX_CYCLES := 16
## How many merge cycles run per compute-list batch (FIX 1, perf-decomp
## 2026-08-14): each cycle's fold→zero-cc→count→scan→fill→best→hop chain is
## recorded into ONE list with intra-list barriers, and the batch ends with
## ONE submit+sync + ONE 64 B count readback — vs the old 3 submits + 1
## device-sync readback + 1 host update PER CYCLE. The old per-cycle drain
## is the TDR trigger on the shared three-RD GPU (device-lost backtraces
## land in _merge_read_uint); batching collapses ~5 drains/cycle into 1.
## Results are identical (a 0-merge cycle is a deterministic no-op: fold is
## idempotent after re-basing, so the batch's last-zero count stops the
## loop with exactly the per-cycle early-exit semantics). Tune 2..8.
const MERGE_BATCH_CYCLES := 4


## Run one merge pass (returns the total merges). FIX 1 (perf-decomp
## 2026-08-14): cycles execute in BATCHES of MERGE_BATCH_CYCLES — every
## cycle's fold→zero-cc→count→scan→fill→best→hop chain is recorded into ONE
## compute list with intra-list barriers (visibility identical to the old
## per-cycle submit+sync), ending with ONE submit+sync + ONE 64 B count
## readback. The old per-cycle flow did 3 submits + 1 device-sync readback +
## 1 host buffer_update PER CYCLE — that drain burst is the TDR trigger on
## the shared three-RD GPU (device-lost backtraces land in _merge_read_uint).
## Results are bit-identical: a 0-merge cycle is a deterministic no-op (the
## fold re-bases mom/cen onto the canonical state, so it is idempotent), so
## the batch's last cycle reading 0 stops the loop with exactly the old
## per-cycle early-exit semantics. The scan is folded into the batch list
## (its 4 passes barrier internally); cc is re-zeroed ON-GPU per cycle (mode
## 7) — the old flow zeroed cc once per pass, which left cc dirty (2x counts)
## for multi-cycle passes; the batched flow is exact.
func _run_merge_pass() -> int:
	if not particle_merge or not _merge_shader.is_valid() or not _merge_pipe.is_valid() \
			or not _us_merge_0.is_valid() or not _merge_alive_buf.is_valid() \
			or not _scan_pipe.is_valid() or not _us_scan_0.is_valid() \
			or N_particles <= 0:
		return 0
	# reset in its own list + submit/sync (its per-particle state writes must
	# be visible to the first cycle's fold)
	_zero_merge_bytes(_merge_cc_buf, _merge_hash_total)
	_zero_merge_bytes(_merge_mc_buf, MERGE_MAX_CYCLES)
	var cl0 := _rd.compute_list_begin()
	_merge_bind_dispatch(cl0, 0.0)   # reset: alive=1, mass=pos.w, mom/cen=m p/m v
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	var total := 0
	var cyc := 0
	while cyc < MERGE_MAX_CYCLES:
		var ncyc := mini(MERGE_BATCH_CYCLES, MERGE_MAX_CYCLES - cyc)
		var cl := _rd.compute_list_begin()
		for c in range(ncyc):
			_merge_bind_dispatch(cl, 1.0)              # fold → canonical pos/vel
			_rd.compute_list_add_barrier(cl)
			_merge_bind_dispatch(cl, 7.0)              # zero cc (per-cycle, in-list)
			_rd.compute_list_add_barrier(cl)
			_merge_bind_dispatch(cl, 2.0)              # count into cc
			_rd.compute_list_add_barrier(cl)
			_merge_scan_into(cl)                       # 4 scan passes (barriers inside)
			_merge_bind_dispatch(cl, 3.0)              # fill per-cell lists
			_rd.compute_list_add_barrier(cl)
			_merge_bind_dispatch(cl, 4.0)              # best[i], sink[i]
			_rd.compute_list_add_barrier(cl)
			_merge_bind_dispatch(cl, 5.0, cyc + c)     # hop → mc[cyc+c]
			_rd.compute_list_add_barrier(cl)           # next cycle's fold sees this hop
		_rd.compute_list_end()
		_rd.submit(); _rd.sync()
		var counts := _merge_read_counts()
		var batch_merges := 0
		for c in range(ncyc):
			batch_merges += counts[c]
		total += batch_merges
		_merge_cycles_run += ncyc
		cyc += ncyc
		if counts[ncyc - 1] == 0:
			break   # last cycle no-op → all later cycles are deterministic no-ops
	var clf := _rd.compute_list_begin()
	_merge_bind_dispatch(clf, 6.0)   # finalize: survivor masses → pos.w / dead = 0
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	if total > 0:
		print("[PhysicsEngine] merge pass: %d merges (%d cycles)" % [total, _merge_cycles_run])
	return total


## The merge push constant as 24 floats (shader layout: N, phi, phi_inv2,
## q_threshold, R_m, extent.xyz, grid_N, hash_nxyz, cell_w.xyz, pass_mode@15,
## g_n, xi, h0, dt, f_subsonic, f_virial, f_order, cyc_slot@23 — the §3
## redesign + the batched-merge cycle slot).
func _merge_pc_values() -> PackedFloat32Array:
	var ebox := _extents()
	var r_m: float = _extent_min() / float(maxi(grid_N, 1))   # ½·h₀
	var f := PackedFloat32Array()
	f.resize(24)
	f[0] = float(N_particles)          # N
	f[1] = PHI                          # phi
	f[2] = PHI_INV2                     # phi^-2 (q denom scale + default gate)
	f[3] = PHI_INV2                     # q_threshold = phi^-2
	f[4] = r_m                          # R_m = ½·h₀
	f[5] = ebox.x                       # extent_x
	f[6] = ebox.y                       # extent_y
	f[7] = ebox.z                       # extent_z
	f[8] = float(grid_N)                # grid_N (q_coh trilinear)
	f[9] = float(_merge_hash_nx)        # hash_nx
	f[10] = float(_merge_hash_ny)       # hash_ny
	f[11] = float(_merge_hash_nz)       # hash_nz
	f[12] = _merge_cell_wx              # cell_wx
	f[13] = _merge_cell_wy              # cell_wy
	f[14] = _merge_cell_wz              # cell_wz
	# §3 redesign fields: g_n = the calibrated Newton G (bh[1].w, the same
	# G_N the nbody force uses — single source of truth), ξ = φ⁶, h0 = 2·R_m,
	# dt, and the hypothesis-tier feature flags.
	f[16] = _bh_init_bytes.decode_float(28)   # G_N (bh[1].w)
	f[17] = xi                                # φ⁶ coupling
	f[18] = 2.0 * r_m                         # h₀ = 2·R_m (reference cell)
	f[19] = dt                                # timestep (c_s = h0/dt)
	f[20] = 1.0 if merge_subsonic else 0.0    # subsonic-inflow criterion
	f[21] = 1.0 if merge_virial else 0.0      # virial stopping scale
	f[22] = 1.0 if merge_sel_gate else 0.0    # order-selective q_sel gate
	f[23] = 0.0                               # cyc_slot (batched hop slot; set per dispatch)
	return f


## Bind the merge pipeline/set/PC and dispatch one pass mode into the open
## list `cl`. Rebuilds the PC each dispatch (Trap T1 safe). The caller adds
## barriers between consecutive in-list passes and submit+sync across lists.
func _merge_bind_dispatch(cl: int, pass_mode: float, cyc_slot := 0) -> void:
	var pf := _merge_pc_values()
	pf[15] = pass_mode
	pf[23] = float(cyc_slot)
	var pc_bytes := pf.to_byte_array()
	_rd.compute_list_bind_compute_pipeline(cl, _merge_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_merge_0, 0)
	_rd.compute_list_set_push_constant(cl, pc_bytes, pc_bytes.size())
	_rd.compute_list_dispatch(cl, ceili(float(N_particles) / 256.0), 1, 1)


func _merge_read_counts() -> PackedInt32Array:
	var d := _rd.buffer_get_data(_merge_mc_buf, 0, MERGE_MAX_CYCLES * 4)
	var out := PackedInt32Array()
	out.resize(MERGE_MAX_CYCLES)
	if d.size() >= MERGE_MAX_CYCLES * 4:
		for k in range(MERGE_MAX_CYCLES):
			out[k] = int(d.decode_u32(k * 4))
	return out


## FIX B (batched): record the 4 on-GPU exclusive-scan passes into the OPEN
## compute list `cl` (cassi_exclusive_scan.glsl): cc -> cs (exclusive), ch =
## cs (the per-cell fill head). Intra-list barriers for pass-to-pass
## visibility; the CALLER owns list begin/end/submit — the batched merge
## folds the scan into the batch list so the whole batch is ONE submit+sync
## (the scan reads cc, which the batch zeroed per cycle just before).
func _merge_scan_into(cl: int) -> void:
	var E := _merge_hash_total
	var nb1 := (E + 255) / 256
	var nb2 := _merge_nb2
	var pc := PackedFloat32Array()
	pc.resize(4)
	pc[2] = float(_merge_nb1a)
	# pass 1: cc -> cs (block-local exclusive) + L1 totals -> scr[b]
	pc[0] = float(E); pc[1] = 1.0
	_scan_dispatch(cl, pc, nb1)
	_rd.compute_list_add_barrier(cl)
	# pass 2: scan scr(L1) in place -> loc1 + L2 totals -> scr[nb1a + bb]
	pc[0] = float(nb1); pc[1] = 2.0
	_scan_dispatch(cl, pc, nb2)
	_rd.compute_list_add_barrier(cl)
	# pass 3: single workgroup scan of L2 -> exclusive (nb2 <= 256)
	pc[0] = float(nb2); pc[1] = 3.0
	_scan_dispatch(cl, pc, 1)
	_rd.compute_list_add_barrier(cl)
	# pass 4: cs += carries; ch = cs
	pc[0] = float(E); pc[1] = 4.0
	_scan_dispatch(cl, pc, nb1)
	_rd.compute_list_add_barrier(cl)


func _scan_dispatch(cl: int, pc: PackedFloat32Array, groups: int) -> void:
	_rd.compute_list_bind_compute_pipeline(cl, _scan_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_scan_0, 0)
	_rd.compute_list_set_push_constant(cl, pc.to_byte_array(), pc.size() * 4)
	_rd.compute_list_dispatch(cl, maxi(groups, 1), 1, 1)


func _zero_merge_bytes(buf: RID, count: int) -> void:
	var z := PackedByteArray(); z.resize(count * 4); z.fill(0)
	_rd.buffer_update(buf, 0, z.size(), z)
