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
## Gridless mode owns the site-native field/force/BH path in this engine:
## moving Voronoi sites, CSR field evolution, carry-safe particle mass
## deposition, site condensation, BH integration, tree build/walk, and the
## cached-acc KDK force read the same live site state. The renderer's
## instancer, q-histogram, field display, and BH lensing remain render-side
## consumers; they bind the engine's site buffers when gridless_physics is on.
## Legacy grid mode retains the original raster chain and the compatibility
## seam described below.
##
## In legacy mode, run_steps() accepts an optional per-particle tree-gradient
## array, which is uploaded into the nbody set-1 binding-3 buffer when
## non-empty (empty leaves the buffer as-is). In gridless mode the engine
## generates the tree gradient itself from the site tree.
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

const PHI: float = CassiTreeConsts.PHI
const PHI_INV3: float = (PHI - 1.0) / (PHI + 1.0)   # φ⁻³ = attractor π/ρ ≈ 0.236068
const PHI_INV2: float = 0.3819660112501051  # φ⁻² — q decoherence threshold
const PHI_6: float = CassiTreeConsts.PHI_6  # φ⁶ ≈ 17.94427191 (computed spelling — see CassiTreeConsts)
const PI_CLAMP_MAX: float = 0.72  # (π/ρ) upper clamp (stability; telemetry counts hits)
const LN2: float = 0.6931471805599453  # ln 2 — degenerate rainbow v_scale fallback (0.95·ln2)
# Tree-arm force calibration G_tree = G_N·ML_TREE_G_SCALE rides bh[3].w
# (float 60 — a free header slot, NOT the nbody PC). 1.0 off-tree (river
# bit-identical). Ported verbatim so the header encode matches the sim.
# G_SCALE=1.0 (2026-08-16): the tree uses the same config-calibrated G_N as
# the river/IC (G_eff=1). The legacy fixed 0.03, fit at N=4000, under-binds
# the owner's 2.5M scale ~30× (G_tree=0.03·G_N=0.000285 there) → Q_vir≈30-80
# → unbound inflation = the residual vanish; 1.0 restores Q_vir≈0.5 (bound).
const ML_TREE_G_SCALE := 1.0
# Tree-walk softening (LENGTH²): eps2 = (ML_TREE_EPS2_FRAC · extent_min)²
# derived per tree job (the sim's recipe — the tree worker's monopole
# R² = ds² + eps2). ML_TREE_NODE_MAX_MULT sizes the node cap for the job.
const ML_TREE_EPS2_FRAC := 0.05
const ML_TREE_NODE_MAX_MULT := CassiTreeConsts.ML_TREE_NODE_MAX_MULT
const ML_TREE_LEAF_CAP := CassiTreeConsts.ML_TREE_LEAF_CAP      # tree-in-list (M0): the worker's tree constants, engine side
const ML_TREE_MAX_LEVELS := CassiTreeConsts.ML_TREE_MAX_LEVELS
const ML_TREE_FIELD_FLOOR := CassiTreeConsts.ML_TREE_FIELD_FLOOR
const ML_TREE_THETA := CassiTreeConsts.ML_TREE_THETA
# ── Meshless (moving-Voronoi) arm — MESHLESS_PLAN.md §10 (ported verbatim) ──
const ML_N1 := 16              # BCC sublattice count → 2·16³ = 8192 sites at N=64
const ML_REBUILD := 25         # steering + remap + JFA-refresh cadence (steps)
const SS_Q_FLOOR := 0.3819660112501051   # Arm 1 shortlist q threshold — φ⁻² (coherent-site floor)
const TREE_JOB_STEP_CAP := 8   # perf-decomp 2026-08-15: cap a tree-cadence job's step budget so the tree staging readbacks drain a SHORT engine queue (freeze duration stops growing with the backlog)
const JOB_STEP_CAP := 64       # perf-decomp 2026-08-15: GENERAL per-job cap — a coalesced backlog drains over many short jobs instead of ONE monster chain (measured 500k live: jobs 203→662→2381→6540→14004→28481 steps, ~85 s GPU chains freezing the render flush; 64 steps ≈ ≤0.25 s chain — a hitch, not a freeze; throughput is unchanged, the backlog just drains in bounded slices)
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
var meshless_mode: bool = true    # enables Voronoi/site topology and render path
var meshless_gravity: bool = true # site-native tree/N-body when gridless_physics
var gridless_physics: bool = false # authoritative site field/force/BH path
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
# Merge cadence (perf-decomp 2026-08-14): gate the merge pass on
# accumulated STEPS so it stops running every job. 0 = AUTO = 1/2 of the
# R_m reaction budget — R_m = extent_min/grid_N world units, closing speed
# v ≈ 1.0 units/s (the design's number: R_m=0.586 crossed in ~586 dt=0.001
# steps), so budget = R_m/(v·dt) steps and 1/2 = 0.5·extent_min/grid_N/dt
# (28 at the owner config: 180/64/0.05·0.5; jobs carry ~16-20 steps, so
# this lands every ~2 jobs — a quarter budget would be < 1 job and not
# reduce pass frequency); any positive value = explicit step cadence.
# Bound pairs linger within R_m for many dials (the virial/binding gate
# rejects fast fly-bys), so halving the pass rate does not change merge
# physics. Validated: T1/T2 sweeps (2026-08-14) showed cadence >= 28
# flattens the +109-135% ms/step slope (progressive slowdown) to 0-4%;
# the STEP-1 any-candidate early-out (2026-08-15) makes that moot — the
# pre-registered A/B (per-job vs AUTO) showed per-job (1) survives 60 s
# with no TDR ×2 AND catches the job-1 IC-overlap coalesce (1+33 merges
# at job 1), so the sim now defaults to 1 (per job) and AUTO stays for
# coarser-cadence users.
var merge_cadence_steps: int = 1
var _merge_step_counter := 0
var _merge_global_initialized := false
# merge is on, these gate which of the four layer criteria apply. Default on
# = the realistic merge; off recreates the legacy (distance + q_coh only) for
# the §3d falsifier A/B tests.
var merge_subsonic: bool = true   # hypothesis: |v_t| < c_s (no fly-by merges)
var merge_virial: bool = true     # hypothesis: virialised targets stop accreting
var merge_sel_gate: bool = true   # doctrine: order-selective q_sel = q_coh·q_ord
# Boxless field read (boxless_field_prereg.md): when ON (with particle_merge),
# the merge coherence gate reads the moving-Voronoi site's cell-averaged field +
# AREPO gradient + momentum density instead of the periodic grid (merge_boxless_prereg.md).
# Default OFF = grid trilinear, byte-identical. Mirrors the sim's export.
var boxless_field: bool = false
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
# Meshless J_z winding coupling (cassi-voronoi mode-1 leapfrog, amendment 3c):
# the (b2) phase-lock term that makes the site doublet wind toward coherent
# neighbors, gated by the site's openness (1−q). 0.0 (default) = OFF =
# bit-identical battery; a positive coefficient enables the winding. Rides
# cell-PC slot 17 (the appended J_wind float, offset 68 — the ham_completion
# append precedent).
var winding_coupling: float = 0.0
# Coherence-gated adaptive compute (coherence_adaptive_prereg.md Arm 3a): when
# ON, the job-boundary COM (read_com → the sim's window tracker) is weighted by
# each subsampled particle's FIELD coherence q (coherent core dominates; stray
# void particles contribute ~nothing). Default OFF = plain mass COM, bit-identical.
var q_weighted_com: bool = false
# Coherence-adaptive Barnes-Hut θ (coherence_adaptive_prereg.md Arm 2): when ON,
# the tree walk opens a node by theta_eff = θ·(1 − α·(q_n − q_mean)) — tighter
# (more opens) in high-q condensate, looser (fewer opens) in low-q voids.
# Default OFF = θ fixed, bit-identical tree.
var coherence_theta: bool = false
var coherence_theta_alpha: float = 1.0
# Cassi BH accretion — "object -> BH": particles within a BH's accretion
# radius (bh_accretion_radius, world units — a small fraction of the BH's
# σ softening) are marked dead (pos.w = 0, skipped by deposit/nbody/instancer)
# and their mass is added to the BH's record (bh[base].w) atomically — exactly
# conserved. Default off. Dispatched after the BH-integrate block in the step
# chain (pure GPU, no readback). Only meaningful when black_holes_enabled AND
# at least one BH record is active.
var bh_accretion: bool = false
var bh_accretion_radius: float = 0.1   # world units (~1× the default softening σ)
# Tree-worker consumer (decoupled mode): the sim creates + starts the

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
var _ml_sites_world: RID # vec4[n_sites] — world-space source positions for tree gravity
var _ml_mass_fix: RID  # uint[n_sites] — deterministic fixed-point particle mass
var _ml_mass: RID      # float[n_sites] — authoritative site mass
var _ml_q: RID         # float[n_sites] — authoritative site coherence
var _ml_eps: RID       # float[n_sites] — authoritative site phi-defect
var _us_jfa_0: RID
var _us_cell_0: RID
var _us_raster_0: RID
var _jfa_pc_bytes: PackedByteArray    # JFA PC (8 floats: N, jump, read_a, n_sites, h, pad×3)
var _cell_pc_bytes: PackedByteArray   # cell PC (18 floats: mode, N, n_sites, dt, hx, hy, hz, C2, OM2, PHI, source_s, rho_floor, drift_cap, kappa, lam, T_steer, lloyd_p, J_wind)
var _raster_pc_bytes: PackedByteArray # raster PC (8 floats: N, n_sites, hx, hy, hz, pad×3)
var _ml_sites_cpu := PackedFloat32Array()
var _ml_ready := false
var _ml_tree_nsrc := 0
# ── Arm 1 (coherence_adaptive_prereg.md): the coherence-filtered site
# shortlist the per-frame boxless INSTANCER samples. Built on the steer
# cadence (this rebuild list); the sim's render-dc instancer sets read these
# engine buffers directly (the engine owns the mesh in decoupled mode).
var _shortlist_shader: RID; var _shortlist_pipe: RID
var _shortlist_sites: RID      # vec4[max_sites] — (pos.xyz, float(site_idx)) for q ≥ q_floor
var _shortlist_count: RID      # uint[1] — atomic compaction cursor / result
var _us_shortlist: RID
var _shortlist_pc_bytes: PackedByteArray   # 3 floats (12 B): n_sites, q_floor, mode
# ── Boxless site hash (boxless_site_hash_prereg.md): the spatial hash over the
# shortlist (built immediately after it in _mesh_rebuild). The sim's boxless
# instancer sets bind these; the query does a bounded growing-ring nearest-site
# lookup instead of the linear O(shortlist) scan.
var _hash_shader: RID; var _hash_pipe: RID
var _hash_cell_start: RID   # uint[n_cells+1] — exclusive prefix (cell site runs)
var _hash_cell_sites: RID   # uint[max_sites] — per-cell compacted shortlist slots
var _hash_cell_count: RID   # uint[n_cells] — histogram / scatter cursor
var _hash_cfg: RID          # vec4 — (box_min.x, box_min.y, box_min.z, cell_side)
var _us_hash: RID
var _hash_pc_bytes: PackedByteArray   # 9 floats (36 B): ext_xyz, H, shortlist, tile origin xyz, mode
## Production open-render topology. These buffers are immutable per published
## generation; a rebuild writes scratch/current resources and publishes only
## after all barriers complete. The sim consumes these RIDs directly on the
## global RD and must treat generation==0 or overflow!=0 as unavailable.
var _topology_open_labels: RID
var _topology_open_labels_scratch_a: RID
var _topology_open_labels_scratch_b: RID
var _topology_adjacency: RID
var _topology_degree: RID
var _topology_offsets: RID
var _topology_neighbors: RID
var _topology_optical: RID
var _topology_shader: RID; var _topology_pipe: RID
var _topology_adj_shader: RID; var _topology_adj_pipe: RID
var _topology_csr_shader: RID; var _topology_csr_pipe: RID
var _topology_optical_shader: RID; var _topology_optical_pipe: RID
var _us_topology: RID; var _us_topology_adj: RID
var _us_topology_csr: RID; var _us_topology_optical: RID
var _topology_pc_bytes: PackedByteArray
var _topology_status: RID       # uint[4]: generation, required_edges, overflow, site_count
var _topology_meta: RID         # vec4[2]: window origin, half extents
var _topology_generation: int = 0
var _render_query_generation: int = 0
var _topology_required_neighbors: int = -1 # GPU-only until a readback is explicitly requested
var _topology_overflow: int = -1 # GPU-only until a readback is explicitly requested
var _topology_neighbor_capacity: int = 0
var _topology_site_count: int = 0
var _topology_ready: bool = false
var _meshless_query_ready: bool = false
var _mesh_rebuild_pending: bool = false
var _render_query_sites_cpu := PackedFloat32Array()
var _render_query_center := Vector3.ZERO
var _render_query_extents := Vector3.ZERO
var _render_topology_worker = null
var _render_topology_last_step := -1
var _render_topology_inflight := false

## Stable public topology accessors. Returning a Dictionary is reserved for
## full resource handoff; scalar hot paths use the allocation-free accessors.
## GPU status slots: generation, required-neighbor count, overflow flag, site count.
func topology_generation_value() -> int:
	return _topology_generation
func render_query_generation_value() -> int:
	return _render_query_generation

func topology_site_count_value() -> int:
	return _topology_site_count
func topology_resources() -> Dictionary:
	return {
		"topology_open_label_rid": _topology_open_labels,
		"topology_adjacency_rid": _topology_adjacency,
		"topology_degree_rid": _topology_degree,
		"topology_offset_rid": _topology_offsets,
		"topology_neighbor_rid": _topology_neighbors,
		"topology_optical_rid": _topology_optical,
		"topology_status_rid": _topology_status,
		"topology_meta_rid": _topology_meta,
		"topology_generation": _topology_generation,
		"render_query_generation": _render_query_generation,
		"topology_required_neighbors": _topology_required_neighbors,
		"topology_neighbor_capacity": _topology_neighbor_capacity,
		"topology_overflow": _topology_overflow,
		"topology_site_count": _topology_site_count,
		"topology_ready": _topology_ready,
		"topology_required_neighbors_gpu_only": _topology_required_neighbors < 0,
		"topology_overflow_gpu_only": _topology_overflow < 0,
		"topology_window_origin": _window_center,
		"topology_window_extent": _extents(),
	}
const HASH_H := 32          # cells per axis (32768 cells at base extents)
# TREE-IN-LIST (M0 commit 2): the tree build+walk runs INSIDE the engine's
# own compute list on the LIVE buffers (mode-7 gather reads the meshless
# state directly) — the per-job 130 MB staging round trip and the tree
# worker's local RD are gone from the engine path. The tree worker
# (cassi_tree_worker.gd) survives for the verify scenes + the sim's inline
# arm; the engine no longer uses it.
var _tree_worker = null          # CassiTreeWorker (owned by the sim — never freed here)
var _tl_src: RID; var _tl_srcw: RID; var _tl_key: RID; var _tl_order: RID
var _tl_cf: RID; var _tl_nw: RID; var _tl_nq: RID; var _tl_nr: RID; var _tl_ctr: RID
var _tl_nqq: RID   # Arm 2: per-node mean coherence q_n (nodeQq binding 14)
var _tl_tic: RID
var _tree_bld_sh: RID; var _tree_bld_pipe: RID
var _tree_walk_sh: RID; var _tree_walk_pipe: RID
var _us_tree_bld: RID; var _us_tree_walk: RID
# Tree MOMENTUM-CONSERVATION pass (cassi_tree_momcon.glsl, 2026-08-15): the
# per-particle (π/ρ) prefactor breaks action–reaction (Σm·a ≠ 0) → net
# self-impulse → the cloud ballistically drifts off the window ("all vanish").
# Zeroes Σm·a after the nbody step in tree mode — a DERIVED Newton-3rd-law
# correction, not a fitted constant.
var _tree_mc_sh: RID; var _tree_mc_pipe: RID
var _tree_mc_buf: RID     # vec4 reduce accumulator
var _us_tree_mc: RID
var _tree_mc_pc_bytes: PackedByteArray   # 3 floats (12 B): N_f, op
var _tree_cadence := 1           # submit a tree job every N physics jobs (sim's cadence semantics)
var _tree_job_counter := 0
# MOVABLE HOME-WINDOW (perf-decomp 2026-08-15, overhaul migration): the
# field grid's world-origin offset (bh[0].yzw + the deposit PC off terms).
var _home_window: bool = false
var _window_center := Vector3.ZERO
var _two_fluid_shader: RID;  var _two_fluid_pipe: RID
var _nbody_shader: RID;      var _nbody_pipe: RID
var _poisson_shader: RID;    var _poisson_pipe: RID
var _mass_deposit_shader: RID; var _mass_deposit_pipe: RID
var _cond_shader: RID;       var _cond_pipe: RID
var _bh_int_shader: RID;     var _bh_int_pipe: RID
var _site_physics_shader: RID; var _site_physics_pipe: RID
var _site_mass_shader: RID; var _site_mass_pipe: RID
var _site_nbody_shader: RID; var _site_nbody_pipe: RID
var _site_cond_shader: RID; var _site_cond_pipe: RID
var _site_bh_int_shader: RID; var _site_bh_int_pipe: RID
var _us_two_0: RID
var _us_mass_dep_0: RID
var _us_nbody_0: RID; var _us_nbody_1: RID; var _us_nbody_2: RID
var _us_poisson_0: RID
var _us_cond_0: RID; var _us_cond_1: RID
var _us_bh_int_0: RID; var _us_bh_int_1: RID
var _us_site_physics: RID
var _us_site_mass: RID
var _us_site_nbody_0: RID; var _us_site_nbody_1: RID; var _us_site_nbody_2: RID
var _us_site_cond_0: RID; var _us_site_cond_1: RID
var _us_site_bh_int_0: RID; var _us_site_bh_int_1: RID
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
var _merge_pc_bytes: PackedByteArray  # merge PC (26 floats = 104 B; F8: pre-sized, encoded in place per dispatch)
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
var _cf_density_fix_buf: RID # coarse fixed-point deposit accumulator (uvec4[N_c³])
var _cf_fft_buf: RID       # coarse Φ (N_c³ vec2 complex)
var _cf_grad_buf: RID      # coarse ∇(g·Φ) (N_c³ vec4)
var _us_poisson_c: RID     # coarse Poisson set (cf_fft + cf_density + tel + cf_fix)
var _us_mass_dep_c: RID    # coarse deposit set (pos + cf_density + cf_fix)
var _cascade_nc: int = 0   # coarse N (grid_N/2 when enabled)
var _cf_grad_pc_bytes: PackedByteArray  # coarse-gradient PC (8 floats)
var _cascade_ran := 0      # lifetime coarse-solve count (verify/battery diag)
var _ready := false
var _setup_done := false            # M0b-P: the worker's CPU-side setup complete
var _setup_compute_done := false    # M0b-P: finish_setup ran (the GPU-facing setup)
var _pipes_done := false            # M0b-P-FX: the shader/pipeline creation ran
									# (on the worker for the global path — pipeline
									# creation is NOT render-thread-gated, only
									# buffer_update + compute lists are)
# M0b-P: the IC host arrays — the worker generates them (CPU); the main
# thread uploads them in finish_setup (global-RD buffer_update is
# render-thread-only).
var _host_pos := PackedFloat32Array()
var _host_vel := PackedFloat32Array()
var _host_acc := PackedFloat32Array()
var _host_cluster := PackedFloat32Array()
var _host_cluster_recs := 0
var _cond_step_counter: int = 0

# — pre-allocated push-constant byte buffers (hitch-free: no per-step allocs) —
var _pc_bytes: PackedByteArray        # shared 11-float PC (kept for verbatim fidelity)
var _nbody_pc_bytes: PackedByteArray  # nbody PC (15 floats: 11 shared + pass_mode + 3 RealSim)
var _two_fluid_pc_bytes: PackedByteArray  # two-fluid PC (16 floats: 11 shared + extent_x/y/z + pass_sel + omega2)
var _md_pc_bytes: PackedByteArray     # mass deposit PC (8 floats: N, particle_N, extent_x/y/z, off_x/y/z)
var _bh_int_pc_bytes: PackedByteArray # BH integrate PC (4 floats)
var _cond_pc_bytes: PackedByteArray   # condensation PC (4 floats)
var _poisson_pc_bytes: PackedByteArray  # poisson PC (7 floats: N, axis, dir, mode, extent_x/y/z)
var _bh_init_bytes: PackedByteArray   # BH header init (36 vec4s = 576 B)
var _site_physics_pc_bytes: PackedByteArray
var _site_mass_pc_bytes: PackedByteArray
var _tel_reset_bytes: PackedByteArray
var _site_nbody_pc_bytes: PackedByteArray
var _site_cond_pc_bytes: PackedByteArray
var _site_bh_int_pc_bytes: PackedByteArray
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

# — threaded runner (the M0b-P one-RD model: the worker does the CPU-side
# setup + the pipeline creation, then exits; the chains are recorded by the
# render thread into the shared global-RD queue) —
var _thread: Thread = null
var _thread_started := false
var _running := false
var _executed := 0          # render-thread cumulative executed step count
# ── (M0b-P-FX cleanup: the worker-side job machinery — _job_sem/_done_sem/
# _setup_sem/_job_mutex/_res_mutex/_job/_job_pending/_res_result/_res_gen/
# _consumed_gen/_wait_next/_snapshot_cadence/_job_counter — died with the
# job loop in M0b-P; all were reset-only. tree_cadence gates the in-list
# tree job (the sim's cfg key); snapshot_cadence is accepted and ignored
# (the readback cadence is the sim's mirror_publish_cadence).) —


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
	gridless_physics = bool(cfg.get("gridless_physics", gridless_physics))
	winding_coupling = float(cfg.get("winding_coupling", winding_coupling))
	q_weighted_com = bool(cfg.get("q_weighted_com", q_weighted_com))
	coherence_theta = bool(cfg.get("coherence_theta", coherence_theta))
	coherence_theta_alpha = float(cfg.get("coherence_theta_alpha", coherence_theta_alpha))
	mode = int(cfg.get("mode", mode))
	particle_merge = bool(cfg.get("particle_merge", particle_merge))
	merge_cadence_steps = int(cfg.get("merge_cadence_steps", 0))
	_merge_global_initialized = false
	merge_subsonic = bool(cfg.get("merge_subsonic", merge_subsonic))
	merge_virial = bool(cfg.get("merge_virial", merge_virial))
	merge_sel_gate = bool(cfg.get("merge_sel_gate", merge_sel_gate))
	boxless_field = bool(cfg.get("boxless_field", boxless_field))
	if gridless_physics:
		meshless_mode = true
		meshless_gravity = true
		boxless_field = true
	cascade_level = bool(cfg.get("cascade_level", cascade_level))
	if gridless_physics and cascade_level:
		push_error("[PhysicsEngine] cascade_level has no site-native operator; refusing a silent no-op")
		return false
	bh_accretion = bool(cfg.get("bh_accretion", bh_accretion))
	bh_accretion_radius = float(cfg.get("bh_accretion_radius", bh_accretion_radius))
	# Tree cadence (the sim's _tree_local_cadence) — the in-list tree job gate.
	_tree_cadence = int(cfg.get("tree_cadence", 1))
	_tree_job_counter = 0
	_home_window = bool(cfg.get("home_window", false))
	_window_center = Vector3(cfg.get("window_center", Vector3.ZERO))
	# ── build the chain ──
	if _rd_global:
		# M0b-P (one-RD): the worker's setup is CPU-side — the global RD's
		# buffer_update AND compute lists are render-thread-only (empirically
		# verified 2026-08-15). The GPU-facing setup (_setup_buffers + the IC
		# uploads + the initial compute dispatches) runs on the main thread
		# via finish_setup(); the expensive CPU-side IC generation stays on
		# the worker (the FIX A non-blocking boot).
		# Global RenderingDevice resources are prepared by finish_setup on the
		# render thread. The worker only performs CPU-side particle IC setup;
		# pipeline and uniform RIDs remain render-thread owned.
		_init_particles_cpu()
		_setup_done = true
		print("[PhysicsEngine] setup done (worker CPU side) — grid=%d^3 particles=%d xi=%.5f (phi6=%.5f) rd_global=%s" % [
			grid_N, N_particles, xi, PHI_6, "true" if _rd_global else "false"])
		return true
	# Local-RD standalone path (the verify_merge_engine battery + external
	# local-RD consumers): the FULL setup on the caller's thread — the
	# render-thread gate is global-RD-only; the local RD records/updates
	# freely (the legacy behavior).
	_create_pipelines()
	if not _pipelines_ready():
		var missing := []
		if not _two_fluid_pipe.is_valid(): missing.append("two_fluid")
		if not _nbody_pipe.is_valid(): missing.append("nbody")
		if not _poisson_pipe.is_valid(): missing.append("poisson")
		if not _mass_deposit_pipe.is_valid(): missing.append("mass_deposit")
		if not _cond_pipe.is_valid(): missing.append("condensation")
		if not _bh_int_pipe.is_valid(): missing.append("bh_integrate")
		push_error("[PhysicsEngine] setup failed: pipes missing = %s (spirv dict size=%d)" % [str(missing), _cfg_spirv.size()])
		return false
	_setup_buffers()
	_setup_shaders()
	if not _ready:
		push_error("[PhysicsEngine] setup failed: shader/uniform setup incomplete")
		return false
	_init_particles_cpu()
	_upload_particles()
	_init_field()
	_apply_gravity_calibration()
	_grav_warmup = true  # fill the acc cache with a fresh force before step 1
	_setup_compute_done = true   # the local path defers nothing
	_setup_done = true
	print("[PhysicsEngine] setup done (local RD) — grid=%d^3 particles=%d xi=%.5f (phi6=%.5f)" % [
		grid_N, N_particles, xi, PHI_6])
	return true


## Main-thread (render thread): the GPU-facing setup + the deferred initial
## compute dispatches — the global RD's buffer_update + compute lists are
## this once setup_ready() is true, before the first frame's chain.
## Idempotent.
func finish_setup() -> bool:
	if not _pipelines_ready():
		_create_pipelines()
	print("[PhysicsEngine] finish pipe check: rd=%s core=%s site=%s/%s/%s/%s/%s topo=%s/%s/%s/%s" % [
		str(_rd), str(_two_fluid_pipe.is_valid()), str(_site_physics_pipe.is_valid()),
		str(_site_mass_pipe.is_valid()), str(_site_nbody_pipe.is_valid()),
		str(_site_cond_pipe.is_valid()), str(_site_bh_int_pipe.is_valid()),
		str(_topology_pipe.is_valid()), str(_topology_adj_pipe.is_valid()),
		str(_topology_csr_pipe.is_valid()), str(_topology_optical_pipe.is_valid())])
	if _setup_compute_done:
		return true
	if not _pipelines_ready():
		var missing := PackedStringArray()
		for item in [
			["two_fluid", _two_fluid_pipe], ["nbody", _nbody_pipe],
			["poisson", _poisson_pipe], ["mass_deposit", _mass_deposit_pipe],
			["condensation", _cond_pipe], ["bh_integrate", _bh_int_pipe],
			["site_physics", _site_physics_pipe], ["site_mass", _site_mass_pipe],
			["site_nbody", _site_nbody_pipe], ["site_condensation", _site_cond_pipe],
			["site_bh_integrate", _site_bh_int_pipe], ["jfa", _jfa_pipe],
			["voronoi_cells", _cell_pipe], ["voronoi_raster", _raster_pipe],
			["tree_build", _topology_pipe], ["tree_adj", _topology_adj_pipe],
			["tree_csr", _topology_csr_pipe], ["tree_optical", _topology_optical_pipe],
		]:
			if not item[1].is_valid():
				missing.append(str(item[0]))
		push_error("[PhysicsEngine] finish_setup: pipes missing=%s (spirv dict size=%d)" % [
			str(missing), _cfg_spirv.size()])
		return false
	var _t0 := Time.get_ticks_msec()
	_setup_buffers()
	var _t1 := Time.get_ticks_msec()
	_setup_shaders()
	var _t2 := Time.get_ticks_msec()
	if not _ready:
		_setup_compute_done = false
		push_error("[PhysicsEngine] finish_setup: shader/uniform setup incomplete")
		return false
	_upload_particles()
	var _t3 := Time.get_ticks_msec()
	_init_field()
	var _t4 := Time.get_ticks_msec()
	_apply_gravity_calibration()
	var _t5 := Time.get_ticks_msec()
	_grav_warmup = true  # fill the acc cache with a fresh force before step 1
	_setup_compute_done = true
	print("[PhysicsEngine] finish_setup ms: buffers=%d shaders=%d upload=%d field=%d calib=%d total=%d" % [_t1 - _t0, _t2 - _t1, _t3 - _t2, _t4 - _t3, _t5 - _t4, _t5 - _t0])
	return true


## Record the full per-step chain n times. On a global RD the list is
## executed by the renderer's frame machinery (NEVER submit/sync here); on
## a local RD it is submitted, and synced when wait=true. tree_grad, when
## non-empty (exactly max(N_particles,1)*4 floats), is uploaded into the
## mode-5 nbody tree-gradient buffer first; empty leaves the buffer as-is.
## Run n steps in one compute list on THIS engine's RD. wait=true →
## submit+sync (the local-RD contract: readbacks are synchronous here).
## tree_in_list (M0 commit 2): a tree-cadence job — the tree build+walk
## dispatches run at the START of the same list, reading the LIVE meshless
## buffers (mode-7 gather) and writing _tree_grad directly; the steps below
## then read a fresh gradient (the old bootstrap semantics — no staging
## readbacks, no 32 MB seam upload, no tree worker on this path).
## M0b-P (one-RD): record the pending steps (target − executed, capped) into
## the OPEN list — the render thread's frame list ("strict per-frame staged
## command list": the sim opens the list, calls update_bh_header() BEFORE
## the begin, records the chain here, records the render passes, ends; the
## renderer's frame machinery submits). The engine's accounting
## (executed/step_count/time) advances here; the readbacks (telemetry/COM)
## are the sim's job-boundary accepted group. Returns the recorded count.
func record_pending_steps(cl: int, target: int) -> int:
	if _rd == null or not _ready:
		return 0
	var steps := target - _executed
	if steps <= 0:
		return 0
	# Render topology is an asynchronous visualization payload. It may be
	# invalid while the worker rebuilds labels/CSR, but the site-native physics
	# chain owns its live Voronoi buffers and must continue stepping.
	var tree_job := _tree_job_due()
	if tree_job:
		steps = mini(steps, TREE_JOB_STEP_CAP)
	else:
		steps = mini(steps, JOB_STEP_CAP)
	if tree_job:
		if gridless_physics:
			_site_mass_dispatches(cl)
			_barrier(cl)
		_tree_run_in_list(cl)   # the tree build+walk in THIS list (live buffers)
	if cascade_level and not gridless_physics:
		# The coarse level is intentionally solved once per recorded batch;
		# every fine step below then samples this stable long-range field.
		_dispatch_cascade(cl)
	for _s in range(steps):
		_step_dispatches(cl)
	_executed += steps
	if _rd_global and meshless_mode and not freeze_field and _step_count % ML_REBUILD == 13:
		# Host buffer preparation must happen before the next frame's list;
		# the current list is still open.
		_mesh_rebuild_pending = true
	if particle_merge and steps > 0 and N_particles > 0:
		_merge_step_counter += steps
	return steps


## M0b-P: the local-RD standalone run-a-batch form — the legacy API the
## verify_merge_engine battery drives (a main-thread local RD + submit/sync
## per call, the merge's per-cycle prefix-sum readbacks). The decoupled/
## one-RD path never calls this (the render thread records the frame's
## list); the local-RD path records its own list + submit/syncs here.
func run_steps(n: int, wait := true, tree_in_list := false) -> void:
	if _rd == null or not _ready or _rd_global:
		return
	update_bh_header()
	var cl := _rd.compute_list_begin()
	record_pending_steps(cl, _executed + n)
	_rd.compute_list_end()
	_rd.submit()
	_local_pending = true
	if wait:
		_rd.sync()
		_local_pending = false
	if mesh_rebuild_due():
		_mesh_rebuild()
	run_merge_if_due()


## M0b-P: the merge's step-cadence gate — the caller (the local-RD
## standalone path) runs the merge AFTER the list ends (the merge records
## its own lists + prefix-sum readbacks — illegal inside an open list).
func merge_due() -> bool:
	return particle_merge and _step_count > 0 and _merge_step_counter >= _merge_cadence_eff()


func run_merge_if_due() -> void:
	if merge_due():
		_merge_step_counter = 0
		_run_merge_pass()
## M0b-P global-RD merge recording: the decoupled producer shares the
## renderer's one open command list, so it cannot use _run_merge_pass()
## (that path intentionally submits/syncs for the local-RD battery). Keep
## one complete fold→zero→count→scan→fill→best→hop→finalize cycle in the
## caller's list. Merge state is initialized once per engine setup and then
## persists across frames, so finalized dead slots are not resurrected.
## There is no CPU mirror/copy and no host readback in this path.
func record_merge_if_due(cl: int) -> bool:
	if not _rd_global or not merge_due():
		return false
	if not particle_merge or not _merge_pipe.is_valid() or not _us_merge_0.is_valid() \
			or not _scan_pipe.is_valid() or not _us_scan_0.is_valid() \
			or not _merge_alive_buf.is_valid():
		return false
	if not _merge_global_initialized:
		_merge_bind_dispatch(cl, 0.0)
		_rd.compute_list_add_barrier(cl)
		_merge_global_initialized = true
	_merge_bind_dispatch(cl, 1.0)
	_rd.compute_list_add_barrier(cl)
	_merge_bind_dispatch(cl, 8.0)
	_rd.compute_list_add_barrier(cl)
	_merge_bind_dispatch(cl, 2.0)
	_rd.compute_list_add_barrier(cl)
	_merge_scan_into(cl)
	_merge_bind_dispatch(cl, 3.0)
	_rd.compute_list_add_barrier(cl)
	_merge_bind_dispatch(cl, 4.0)
	_rd.compute_list_add_barrier(cl)
	_merge_bind_dispatch(cl, 5.0, 0)
	_rd.compute_list_add_barrier(cl)
	_merge_bind_dispatch(cl, 6.0)
	return true


## M0b-P: the BH header (count/G_N/extent/toggle/dual + the window origin)
## — constant across the frame's steps; the buffer_update MUST run BEFORE
## the frame's compute_list_begin (the header contract — an update inside
## the open list would land after the chain's dispatches).
func update_bh_header() -> void:
	if _rd == null or not _ready:
		return
	_bh_init_bytes.encode_float(0, 1.0 if cascade_level else 0.0) # reserved cascade toggle; bh[0].yzw remains window center
	_bh_init_bytes.encode_float(48, 1.0 if black_holes_enabled else 0.0)
	_bh_init_bytes.encode_float(52, 1.0 if dual_grid else 0.0)
	_bh_init_bytes.encode_float(56, float(gradient_order))
	_bh_init_bytes.encode_float(60, ML_TREE_G_SCALE if (meshless_mode and meshless_gravity) else 1.0)
	_bh_init_bytes.encode_float(4, _window_center.x)
	_bh_init_bytes.encode_float(8, _window_center.y)
	_bh_init_bytes.encode_float(12, _window_center.z)
	var off_dual: Vector3 = _extents() / float(maxi(grid_N, 1))
	if gridless_physics and _ml_tree_nsrc > 0:
		var site_volume := 8.0 * _extents().x * _extents().y * _extents().z / float(_ml_tree_nsrc)
		var site_spacing := pow(maxf(site_volume, 1.0e-12), 1.0 / 3.0)
		off_dual = Vector3.ONE * site_spacing
	_bh_init_bytes.encode_float(16, off_dual.x)
	_bh_init_bytes.encode_float(20, off_dual.y)
	_bh_init_bytes.encode_float(24, off_dual.z)
	# Preserve live BH records (bh[4..35]); only the 64-byte header is mutable.
	_rd.buffer_update(_bh_buf, 0, 64, _bh_init_bytes.slice(0, 64))


## Meshless rebuild cadence. The standalone GPU chain is reserved for the
## private local-RD verifier path. A global-RD meshless rebuild is a measured
## renderer-blackout trigger on this rig, so the live global owner keeps the
## existing raster attachment and never records that chain.
func mesh_rebuild_due() -> bool:
	if not meshless_mode or not _ml_ready:
		return false
	if _rd_global:
		_mesh_rebuild_pending = false
		return false
	if freeze_field:
		return false
	return _step_count % ML_REBUILD == 13

## Publish a render-only site query payload without dispatching the global
## meshless rebuild chain. The global device's rebuild dispatch is unsafe on
## the renderer frame context, so this boundary-frame host publication keeps
## the renderer site-direct while the private local-RD chain remains intact.
## The initial global mesh has fixed site coordinates until a safe local worker
## publishes a moving rebuild; a window translation shifts the cached tile
## coordinates, and an envelope scale change rescales them before rebuilding
## the compact hash.
func publish_render_query(shift_delta: Vector3 = Vector3.ZERO) -> bool:
	if not _rd_global or _rd == null or not _ready or not _ml_ready:
		return false
	var ns := 2 * ML_N1 * ML_N1 * ML_N1
	var ext := _extents()
	var needed := ns * 4
	if _render_query_sites_cpu.size() != needed:
		if not _ml_sites.is_valid():
			return false
		_render_query_sites_cpu = _rd.buffer_get_data(_ml_sites, 0, needed * 4).to_float32_array()
		if _render_query_sites_cpu.size() != needed:
			return false
		_render_query_center = _window_center
		_render_query_extents = ext
	else:
		var old_ext := _render_query_extents
		var scale_changed := old_ext.x > 1e-6 and old_ext.y > 1e-6 and old_ext.z > 1e-6 \
				and (old_ext - ext).length_squared() > 1e-12
		var center_changed := shift_delta.length_squared() > 1e-12
		if scale_changed or center_changed:
			var lx := 2.0 * ext.x
			var ly := 2.0 * ext.y
			var lz := 2.0 * ext.z
			var sx := ext.x / old_ext.x if scale_changed else 1.0
			var sy := ext.y / old_ext.y if scale_changed else 1.0
			var sz := ext.z / old_ext.z if scale_changed else 1.0
			for i in range(ns):
				var o := i * 4
				var px := _render_query_sites_cpu[o] * sx - shift_delta.x
				var py := _render_query_sites_cpu[o + 1] * sy - shift_delta.y
				var pz := _render_query_sites_cpu[o + 2] * sz - shift_delta.z
				_render_query_sites_cpu[o] = fposmod(px, lx)
				_render_query_sites_cpu[o + 1] = fposmod(py, ly)
				_render_query_sites_cpu[o + 2] = fposmod(pz, lz)
			if center_changed:
				_render_query_center += shift_delta
			_render_query_extents = ext
	var sl := PackedFloat32Array()
	sl.resize(needed)
	var H := HASH_H # one hash contract for render, mass deposition, and diagnostics
	var hcells := H * H * H
	var counts := PackedInt32Array()
	counts.resize(hcells)
	var cell_for := PackedInt32Array()
	cell_for.resize(ns)
	var hx := 2.0 * ext.x / float(H)
	var hy := 2.0 * ext.y / float(H)
	var hz := 2.0 * ext.z / float(H)
	for i in range(ns):
		var o := i * 4
		sl[o] = _render_query_sites_cpu[o]
		sl[o + 1] = _render_query_sites_cpu[o + 1]
		sl[o + 2] = _render_query_sites_cpu[o + 2]
		sl[o + 3] = float(i)
		var cx := clampi(int(floor(sl[o] / hx)), 0, H - 1)
		var cy := clampi(int(floor(sl[o + 1] / hy)), 0, H - 1)
		var cz := clampi(int(floor(sl[o + 2] / hz)), 0, H - 1)
		var cell := cx + H * (cy + H * cz)
		cell_for[i] = cell
		counts[cell] += 1
	var starts := PackedInt32Array()
	starts.resize(hcells + 1)
	var cursor := PackedInt32Array()
	cursor.resize(hcells)
	var total := 0
	for c in range(hcells):
		starts[c] = total
		cursor[c] = total
		total += counts[c]
	starts[hcells] = total
	var cell_sites := PackedInt32Array()
	cell_sites.resize(ns)
	for i in range(ns):
		var cell := cell_for[i]
		var slot := cursor[cell]
		cell_sites[slot] = i
		cursor[cell] = slot + 1
	var zero_counts := PackedInt32Array()
	zero_counts.resize(hcells)
	if not (_ml_sites.is_valid() and _shortlist_sites.is_valid() and _shortlist_count.is_valid()
			and _hash_cell_start.is_valid() and _hash_cell_sites.is_valid()
			and _hash_cell_count.is_valid() and _hash_cfg.is_valid()):
		return false
	_rd.buffer_update(_ml_sites, 0, needed * 4, _render_query_sites_cpu.to_byte_array())
	var world_sites := PackedFloat32Array()
	world_sites.resize(needed)
	for i in range(ns):
		var o := i * 4
		world_sites[o] = _render_query_sites_cpu[o] - ext.x + _render_query_center.x
		world_sites[o + 1] = _render_query_sites_cpu[o + 1] - ext.y + _render_query_center.y
		world_sites[o + 2] = _render_query_sites_cpu[o + 2] - ext.z + _render_query_center.z
		world_sites[o + 3] = _render_query_sites_cpu[o + 3]
	_rd.buffer_update(_ml_sites_world, 0, needed * 4, world_sites.to_byte_array())
	_rd.buffer_update(_shortlist_sites, 0, needed * 4, sl.to_byte_array())
	_rd.buffer_update(_shortlist_count, 0, 4, PackedInt32Array([ns]).to_byte_array())
	_rd.buffer_update(_hash_cell_start, 0, starts.size() * 4, starts.to_byte_array())
	_rd.buffer_update(_hash_cell_sites, 0, ns * 4, cell_sites.to_byte_array())
	_rd.buffer_update(_hash_cell_count, 0, hcells * 4, zero_counts.to_byte_array())
	_rd.buffer_update(_hash_cfg, 0, 16,
		PackedFloat32Array([0.0, 0.0, 0.0, hx]).to_byte_array())
	_render_query_generation += 1
	_topology_site_count = ns
	if _topology_status.is_valid():
		_rd.buffer_update(_topology_status, 0, 16,
			PackedInt32Array([0, 0, 0, ns]).to_byte_array())
	_topology_ready = false
	_meshless_query_ready = true
	return true

## Service the render-topology worker at a global-RD frame boundary.
## Readbacks stage only the site field/gradient payload; the worker owns its
## local device and returns one coherent open-label/CSR/optical generation.
## All returned buffers are uploaded before the caller opens its global list.
func service_render_topology() -> void:
	if not _rd_global or _rd == null or not _ready or not _ml_ready:
		return
	if not _meshless_query_ready and not publish_render_query():
		return
	if _render_topology_worker == null:
		var w: RefCounted = load("res://scripts/cassi_meshless_topology_worker.gd").new()
		if not w.start(grid_N, _topology_site_count, _topology_neighbor_capacity, _extents()):
			push_warning("[PhysicsEngine] render topology worker unavailable")
			return
		_render_topology_worker = w
	var completed: Dictionary = _render_topology_worker.poll()
	if not completed.is_empty():
		_apply_render_topology(completed)
		_render_topology_inflight = false
	var cadence_due := _topology_generation <= 0 \
			or (_step_count - _render_topology_last_step >= ML_REBUILD)
	if not cadence_due or _render_topology_inflight:
		return
	var ns := 2 * ML_N1 * ML_N1 * ML_N1
	if _render_query_sites_cpu.size() != ns * 4:
		return
	var psy := _rd.buffer_get_data(_ml_psi_y, 0, ns * 4).to_float32_array()
	var psi := _rd.buffer_get_data(_ml_psi_i, 0, ns * 4).to_float32_array()
	var grady := _rd.buffer_get_data(_ml_grad_y, 0, ns * 16).to_float32_array()
	var gradi := _rd.buffer_get_data(_ml_grad_i, 0, ns * 16).to_float32_array()
	if psy.size() != ns or psi.size() != ns \
			or grady.size() != ns * 4 or gradi.size() != ns * 4:
		return
	var job := {
		"generation": _topology_generation + 1,
		"sites": _render_query_sites_cpu,
		"psy": psy,
		"psi": psi,
		"grady": grady,
		"gradi": gradi,
		"ext": _extents(),
	}
	_render_topology_last_step = _step_count
	var immediate: Dictionary = _render_topology_worker.submit(job)
	if immediate.is_empty():
		_render_topology_inflight = _render_topology_worker.is_ready()
	else:
		_apply_render_topology(immediate)
		_render_topology_inflight = false


func _apply_render_topology(result: Dictionary) -> void:
	if _rd == null or not _rd_global:
		return
	var uploads := [
		[_topology_open_labels, result.get("open_labels", PackedByteArray())],
		[_topology_adjacency, result.get("adjacency", PackedByteArray())],
		[_topology_degree, result.get("degree", PackedByteArray())],
		[_topology_offsets, result.get("offsets", PackedByteArray())],
		[_topology_neighbors, result.get("neighbors", PackedByteArray())],
		[_topology_optical, result.get("optical", PackedByteArray())],
	]
	for item in uploads:
		var rid: RID = item[0]
		var data: PackedByteArray = item[1]
		if rid.is_valid() and data.size() > 0:
			_rd.buffer_update(rid, 0, data.size(), data)
	var status: PackedByteArray = result.get("status", PackedByteArray())
	if status.size() < 16 or not _topology_status.is_valid():
		return
	_rd.buffer_update(_topology_status, 0, 16, status)
	var generation := int(status.decode_u32(0))
	var required := int(status.decode_u32(4))
	var overflow := int(status.decode_u32(8))
	var site_count := int(status.decode_u32(12))
	_topology_generation = generation
	_topology_required_neighbors = required
	_topology_overflow = overflow
	_topology_site_count = site_count
	_topology_ready = generation > 0 and site_count == 2 * ML_N1 * ML_N1 * ML_N1 \
			and overflow == 0 and required <= _topology_neighbor_capacity
	if _topology_meta.is_valid():
		var ext := _extents()
		_rd.buffer_update(_topology_meta, 0, 32,
			PackedFloat32Array([
				_window_center.x, _window_center.y, _window_center.z, float(generation),
				ext.x, ext.y, ext.z, float(site_count),
			]).to_byte_array())


## The worker owns its local device and must be joined before this engine frees
## the global buffers that the last staged job may still reference by value.
func stop_render_topology_worker() -> void:
	if _render_topology_worker != null:
		_render_topology_worker.stop()
		_render_topology_worker = null
	_render_topology_last_step = -1
	_render_topology_inflight = false


## M0b-P: the subsampled center of mass of the live pos buffer — the window
## tracker's source (the host-side mirror is gone with the snapshots).
## Main-thread readback; the accepted job-boundary group.
## When q_weighted_com (coherence_adaptive_prereg.md Arm 3a), the COM is
## WEIGHTED BY each subsampled particle's FIELD coherence q (map its position →
## grid cell → _field_q), so the coherent core dominates and stray void
## particles contribute ~nothing — the envelope follows the field, not the
## cloud. Default (OFF) = plain mass COM, bit-identical.
func _site_q_cpu_lookup(world: Vector3, sites: PackedFloat32Array,
		qf: PackedFloat32Array, starts: PackedInt32Array, hs: PackedInt32Array,
		ext: Vector3) -> float:
	var local := world - _window_center
	if absf(local.x) >= ext.x or absf(local.y) >= ext.y or absf(local.z) >= ext.z:
		return 0.0
	var span := ext * 2.0
	var tile := local + ext
	var cell := Vector3i(
		clampi(int(floor(tile.x / maxf(span.x / float(HASH_H), 1e-6))), 0, HASH_H - 1),
		clampi(int(floor(tile.y / maxf(span.y / float(HASH_H), 1e-6))), 0, HASH_H - 1),
		clampi(int(floor(tile.z / maxf(span.z / float(HASH_H), 1e-6))), 0, HASH_H - 1))
	var best := 1.0e30
	var best_q := 0.0
	for dz in range(-1, 2):
		for dy in range(-1, 2):
			for dx in range(-1, 2):
				var cx := clampi(cell.x + dx, 0, HASH_H - 1)
				var cy := clampi(cell.y + dy, 0, HASH_H - 1)
				var cz := clampi(cell.z + dz, 0, HASH_H - 1)
				var ci := cx + HASH_H * (cy + HASH_H * cz)
				if ci < 0 or ci + 1 >= starts.size():
					continue
				for k in range(starts[ci], min(starts[ci + 1], hs.size())):
					var si := hs[k]
					if si < 0 or si * 4 + 2 >= sites.size() or si >= qf.size():
						continue
					var so := si * 4
					var dd := Vector3(
						sites[so] - tile.x, sites[so + 1] - tile.y, sites[so + 2] - tile.z)
					var d2 := dd.length_squared()
					if d2 < best:
						best = d2
						best_q = qf[si]
	return best_q


func read_com() -> Array:
	if _rd == null or not _ready:
		return []
	var np1 := maxi(N_particles, 1)
	var posf: PackedFloat32Array = _rd.buffer_get_data(_pos_buf, 0, np1 * 16).to_float32_array()
	var com := Vector3.ZERO
	var cnt := 0
	if q_weighted_com:
		var ext := _extents()
		var qf: PackedFloat32Array
		var sites: PackedFloat32Array
		var starts := PackedInt32Array()
		var hs := PackedInt32Array()
		if gridless_physics:
			var ns := maxi(_ml_tree_nsrc, 1)
			qf = _rd.buffer_get_data(_ml_q, 0, ns * 4).to_float32_array()
			sites = _rd.buffer_get_data(_ml_sites, 0, ns * 16).to_float32_array()
			starts = _rd.buffer_get_data(_hash_cell_start, 0, (HASH_H * HASH_H * HASH_H + 1) * 4).to_int32_array()
			hs = _rd.buffer_get_data(_hash_cell_sites, 0, ns * 4).to_int32_array()
		else:
			var nc: int = grid_N * grid_N * grid_N
			qf = _rd.buffer_get_data(_field_q, 0, nc * 4).to_float32_array()
		var wsum := 0.0
		var i := 0
		while i + 2 < posf.size():
			var p := Vector3(posf[i], posf[i + 1], posf[i + 2])
			var q := _site_q_cpu_lookup(p, sites, qf, starts, hs, ext) if gridless_physics else qf[
				clampi(int(floorf((p.x - _window_center.x) / maxf(ext.x, 1e-4) * grid_N * 0.5 + grid_N * 0.5)), 0, grid_N - 1)
				+ grid_N * (clampi(int(floorf((p.y - _window_center.y) / maxf(ext.y, 1e-4) * grid_N * 0.5 + grid_N * 0.5)), 0, grid_N - 1)
				+ grid_N * clampi(int(floorf((p.z - _window_center.z) / maxf(ext.z, 1e-4) * grid_N * 0.5 + grid_N * 0.5)), 0, grid_N - 1))]
			com += p * q
			wsum += q
			cnt += 1
			i += 32 * 4
		if cnt <= 0 or wsum <= 0.0:
			return []
		return [com.x / wsum, com.y / wsum, com.z / wsum]
	var i := 0
	while i < posf.size():
		com.x += posf[i]
		com.y += posf[i + 1]
		com.z += posf[i + 2]
		cnt += 1
		i += 32 * 4
	if cnt <= 0:
		return []
	return [com.x / float(cnt), com.y / float(cnt), com.z / float(cnt)]


## PROBE-ONLY (M0b-P-FX): the snapshot readback survives solely for the
## _diag/m0b_parity.gd parity probe (fp32 pos/vel + field_q + pot) — the
## decoupled path's render reads the engine's live buffers directly (P3),
## so NO production caller reads snapshots. The fp16 pack transport died
## with the mirrors; packed=true now falls through to the fp32 path.
func readback_snapshot(packed := false) -> Dictionary:
	if _rd == null or not _ready:
		return {}
	if not _rd_global and _local_pending:
		_rd.sync()   # local RD: execute any un-synced submission before reading
		_local_pending = false
	var np1 := maxi(N_particles, 1)
	var pos := _rd.buffer_get_data(_pos_buf, 0, np1 * 16).to_float32_array()
	var vel := _rd.buffer_get_data(_vel_buf, 0, np1 * 16).to_float32_array()
	if gridless_physics:
		var ns := maxi(_ml_tree_nsrc, 1)
		var sites := _rd.buffer_get_data(_ml_sites, 0, ns * 16).to_float32_array()
		var psy := _rd.buffer_get_data(_ml_psi_y, 0, ns * 4).to_float32_array()
		var psi := _rd.buffer_get_data(_ml_psi_i, 0, ns * 4).to_float32_array()
		var pi_y := _rd.buffer_get_data(_ml_pi_y, 0, ns * 4).to_float32_array()
		var pi_i := _rd.buffer_get_data(_ml_pi_i, 0, ns * 4).to_float32_array()
		var q := _rd.buffer_get_data(_ml_q, 0, ns * 4).to_float32_array()
		var eps := _rd.buffer_get_data(_ml_eps, 0, ns * 4).to_float32_array()
		var vol := _rd.buffer_get_data(_ml_vol, 0, ns * 4).to_float32_array()
		var pot := PackedFloat32Array()
		pot.resize(ns)
		for i in range(ns):
			pot[i] = psy[i] + psi[i]
		return {
			"pos": pos, "vel": vel, "sites": sites, "field_q": q, "pot": pot,
			"site_psi_y": psy, "site_psi_i": psi, "site_pi_y": pi_y,
			"site_pi_i": pi_i, "site_eps": eps, "site_vol": vol,
			"t": _time, "generation": _topology_generation, "packed": false,
		}
	var nc: int = grid_N * grid_N * grid_N
	var fq := _rd.buffer_get_data(_field_q, 0, nc * 4).to_float32_array()
	var fft := _rd.buffer_get_data(_fft_buf, 0, nc * 8).to_float32_array()
	var pot := PackedFloat32Array()
	pot.resize(nc)
	var nf := mini(fft.size(), nc * 2)
	for i in range(nf / 2):
		pot[i] = fft[i * 2]
	return {"pos": pos, "vel": vel, "field_q": fq, "pot": pot, "t": _time, "packed": false}


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
	var tel := _rd.buffer_get_data(_tel_buf, 0, 48)
	if tel.size() >= 32:
		_pi_sat_hi_frac = float(tel.decode_u32(0))
		_pi_sat_lo_frac = float(tel.decode_u32(4))
		_rho_guard_hits = int(tel.decode_u32(8))
		_q_min = tel.decode_float(12)
		_q_max = tel.decode_float(16)
		_pi_min = tel.decode_float(20)
		_pi_max = tel.decode_float(24)
	var samples := 1
	if tel.size() >= 32:
		samples = maxi(int(tel.decode_u32(28)), 1)
	_pi_sat_hi_frac /= samples
	_pi_sat_lo_frac /= samples
	if gridless_physics:
		var ns := _ml_tree_nsrc
		var qf := _rd.buffer_get_data(_ml_q, 0, ns * 4).to_float32_array()
		var ef := _rd.buffer_get_data(_ml_eps, 0, ns * 4).to_float32_array()
		var vf := _rd.buffer_get_data(_ml_vol, 0, ns * 4).to_float32_array()
		var q_sum := 0.0
		var v_sum := 0.0
		var eps_sum := 0.0
		_q_min = INF; _q_max = -INF
		for i in range(mini(ns, qf.size())):
			var v := maxf(vf[i], 0.0) if i < vf.size() else 1.0
			q_sum += qf[i] * v
			v_sum += v
			_q_min = minf(_q_min, qf[i]); _q_max = maxf(_q_max, qf[i])
			if i < ef.size(): eps_sum += absf(ef[i]) * v
		_q_mean = q_sum / maxf(v_sum, 1e-12)
		_eps_mean = eps_sum / maxf(v_sum, 1e-12)
	else:
		var qf := field_q_override
		if qf.is_empty():
			var nc: int = grid_N * grid_N * grid_N
			qf = _rd.buffer_get_data(_field_q, 0, nc * 4).to_float32_array()
		if qf.size() > 0:
			var q_sum := 0.0
			for qi in range(0, qf.size(), 16):
				q_sum += qf[qi]
			_q_mean = q_sum * 16.0 / maxf(qf.size(), 1)
	var field_rho_guard_hits := int(tel.decode_u32(36)) if tel.size() >= 40 else 0
	var field_pi_sat_hi := int(tel.decode_u32(32)) if tel.size() >= 36 else 0
	var field_pi_sat_lo := int(tel.decode_u32(44)) if tel.size() >= 48 else 0
	return {
		"q_mean": _q_mean, "q_min": _q_min, "q_max": _q_max,
		"pi_min": _pi_min, "pi_max": _pi_max,
		"pi_sat_hi_frac": _pi_sat_hi_frac, "pi_sat_lo_frac": _pi_sat_lo_frac,
		"rho_guard_hits": _rho_guard_hits,
		"field_pi_sat_hi": field_pi_sat_hi, "field_pi_sat_lo": field_pi_sat_lo,
		"field_rho_guard_hits": field_rho_guard_hits,
		"eps_mean": _eps_mean, "hubble": _hubble, "scale_factor": _scale_factor,
		"gn_eff": _gn_eff,
	}


# ═══════════════════════════════════════════════════════════════════════
# Threaded runner (the cassi_tree_worker.gd pattern)
# ═══════════════════════════════════════════════════════════════════════

## Start the engine on a dedicated worker thread. MAIN thread: loads the
## physics shader FILES and passes extracted SPIR-V into the worker via
## cfg.spirv (RDShaderFile loading is not thread-safe). With a global RD,
## the worker performs CPU-side setup (IC generation + pipeline creation);
## finish_setup() then performs the render-thread GPU-facing setup. Without
## a passed global RD, the worker creates a local RD and runs the standalone
## setup path directly. The worker exits after setup; stop_threaded() joins
## it and shutdown() frees the engine RIDs. Reinit =
## stop_threaded() + start_threaded(new cfg).
func start_threaded(cfg: Dictionary) -> bool:
	stop_threaded()
	_freed = false  # allow a fresh setup() after a previous shutdown
	_setup_done = false
	_setup_compute_done = false
	_pipes_done = false
	_ready = false
	# Load the physics shaders HERE (main thread): resource loading is not
	# thread-safe; the worker receives the extracted SPIR-V.
	var spirv := {}
	var shader_paths := [
			"res://compute/cassi_two_fluid.glsl",
			"res://compute/cassi_mass_deposit.glsl",
			"res://compute/cassi_poisson.glsl",
			"res://compute/cassi_nbody_gravity.glsl",
			"res://compute/cassi_condensation.glsl",
			"res://compute/cassi_bh_integrate.glsl",
			"res://compute/cassi_site_physics.glsl",
			"res://compute/cassi_site_mass.glsl",
			"res://compute/cassi_site_nbody.glsl",
			"res://compute/cassi_site_condensation.glsl",
			"res://compute/cassi_site_bh_integrate.glsl",
			"res://compute/cassi_jfa.glsl",
			"res://compute/cassi_voronoi_cells.glsl",
			"res://compute/cassi_voronoi_raster.glsl",
			"res://compute/cassi_particle_merge.glsl",
			"res://compute/cassi_bh_accretion.glsl",
			"res://compute/cassi_exclusive_scan.glsl",
			"res://compute/cassi_tree_build.glsl",
			"res://compute/cassi_tree_gravity.glsl",
			"res://compute/cassi_site_shortlist.glsl",
			"res://compute/cassi_site_hash.glsl",
			"res://compute/cassi_voronoi_render_adjacency.glsl",
			"res://compute/cassi_voronoi_adjacency_csr.glsl",
			"res://compute/cassi_voronoi_optical_payload.glsl",
			"res://compute/cassi_voronoi_render_topology.glsl",
			"res://compute/cassi_voronoi_fused_volume.glsl"]
	if bool(cfg.get("cascade_level", cascade_level)):
		shader_paths.append("res://compute/cassi_coarse_grad.glsl")
	for p in shader_paths:
		var sf := load(p) as RDShaderFile
		if sf == null or sf.get_spirv() == null:
			push_error("[PhysicsEngine] start_threaded: shader load failed: " + p)
			return false
		spirv[p] = sf.get_spirv()
	var wcfg: Dictionary = cfg.duplicate()
	wcfg["spirv"] = spirv
	_executed = 0
	_running = true
	_thread = Thread.new()
	_thread_started = _thread.start(_threaded_main.bind(wcfg)) == OK
	if not _thread_started:
		push_warning("[PhysicsEngine] thread spawn failed — threaded runner stays offline")
		_running = false
		return false
	return true


## FIX A (non-blocking bootstrap): readiness poll — true once the worker's
## CPU-side setup (the config read + the IC generation into the host
## arrays + the pipeline creation — M0b-P-FX) has finished. The caller
## then runs finish_setup() on the render thread (the GPU-facing setup —
## the buffer zero-fills + the IC uploads + the initial compute dispatches,
## all render-thread-gated) before the first frame's chain. The old
## worker-side job loop / submit_steps / poll / _setup_sem.wait() bootstrap
## died with the M0b-P one-RD migration (global-RD compute lists are
## render-thread-only — the render thread records the chains directly).
func setup_ready() -> bool:
	return _setup_done and _thread_started


## Stop the threaded runner (reinit / exit). MAIN thread: joins the worker
## (already exited after its CPU-side setup — the one-RD model has no job
## loop), then frees the engine's RIDs on the main thread. The global RD is
## the sim's — never freed here (owns_rd false).
func stop_threaded() -> void:
	if _thread != null and _thread_started:
		_running = false
		_thread.wait_to_finish()
		_thread_started = false
		_thread = null
	shutdown()
	_rd = null
	_ready = false
	_executed = 0
## read + the IC generation into the host arrays + the shader/pipeline
## creation — M0b-P-FX: pipeline creation is NOT render-thread-gated, so
## the boot's pipeline-compile hitch lives here), then exit. The RD comes
## from the cfg when the consumer passes its global device (the M0b-P
## one-RD migration — the engine records its chains into the consumer's
## queue and the renderer's frame machinery submits; "Only local devices
## can submit and sync" — the rd_global chains never submit/sync here).
## Without a passed RD the worker falls back to its own local
## RenderingDevice (the legacy standalone path).
func _threaded_main(wcfg: Dictionary) -> void:
	var rd: RenderingDevice = wcfg.get("rd") as RenderingDevice
	var own_rd := false
	if rd == null or not bool(wcfg.get("rd_global", false)):
		rd = RenderingServer.create_local_rendering_device()
		own_rd = true
	if rd == null:
		push_error("[PhysicsEngine] worker: RD create/get failed")
		return
	wcfg["rd"] = rd
	wcfg["rd_global"] = not own_rd
	wcfg["owns_rd"] = own_rd
	setup(wcfg)
	# M0b-P (one-RD): the chains are recorded by the RENDER thread — global-RD
	# compute lists are render-thread-only (empirically verified 2026-08-15).
	# The worker's job loop is GONE: it exits after the CPU-side setup; the sim
	# drives the accounting + chain recording per frame.
	return
## Free buffers/pipes/shaders/uniform sets and, when owns_rd, the device itself.
func shutdown() -> void:
	stop_render_topology_worker()
	if _freed:
		_clear_gpu_handles()
		return
	_freed = true
	if _rd == null:
		_clear_gpu_handles()
		return
	var seen := {}
	var free_uniforms := [_us_two_0, _us_mass_dep_0, _us_nbody_0, _us_nbody_1, _us_nbody_2, _us_poisson_0, _us_cond_0, _us_cond_1, _us_bh_int_0, _us_bh_int_1, _us_jfa_0, _us_cell_0, _us_raster_0, _us_merge_0, _us_scan_0, _us_bh_acc_0, _us_cf_grad_0, _us_poisson_c, _us_mass_dep_c, _us_shortlist, _us_hash, _us_topology, _us_topology_adj, _us_topology_csr, _us_topology_optical, _us_tree_bld, _us_tree_walk, _us_tree_mc]
	free_uniforms.append_array([_us_site_physics, _us_site_mass, _us_site_nbody_0,
		_us_site_nbody_1, _us_site_nbody_2, _us_site_cond_0, _us_site_cond_1,
		_us_site_bh_int_0, _us_site_bh_int_1])
	for rid in free_uniforms:
		if rid.is_valid() and _rd.uniform_set_is_valid(rid) and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	var free_pipes := [_two_fluid_pipe, _nbody_pipe, _poisson_pipe, _mass_deposit_pipe, _cond_pipe, _bh_int_pipe, _jfa_pipe, _cell_pipe, _raster_pipe, _shortlist_pipe, _hash_pipe, _merge_pipe, _scan_pipe, _bh_acc_pipe, _topology_pipe, _topology_adj_pipe, _topology_csr_pipe, _topology_optical_pipe, _tree_bld_pipe, _tree_walk_pipe, _tree_mc_pipe, _cf_grad_pipe]
	free_pipes.append_array([_site_physics_pipe, _site_mass_pipe, _site_nbody_pipe,
		_site_cond_pipe, _site_bh_int_pipe])
	for rid in free_pipes:
		if rid.is_valid() and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	var free_shaders := [_two_fluid_shader, _nbody_shader, _poisson_shader, _mass_deposit_shader, _cond_shader, _bh_int_shader, _merge_shader, _scan_shader, _bh_acc_shader, _cf_grad_shader, _jfa_shader, _cell_shader, _shortlist_shader, _hash_shader, _raster_shader, _topology_shader, _topology_adj_shader, _topology_csr_shader, _topology_optical_shader, _tree_bld_sh, _tree_walk_sh, _tree_mc_sh]
	free_shaders.append_array([_site_physics_shader, _site_mass_shader, _site_nbody_shader,
		_site_cond_shader, _site_bh_int_shader])
	for rid in free_shaders:
		if rid.is_valid() and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	var free_buffers := [_acc_buf, _bh_buf, _cf_density_buf, _cf_fft_buf, _cf_grad_buf, _cluster_buf, _fft_buf, _field_ei, _field_ey, _field_q, _field_scratch, _field_vel, _grad_buf, _grad_buf2, _hash_cell_count, _hash_cell_sites, _hash_cell_start, _hash_cfg, _mass_density_buf, _mass_density_fix, _merge_alive_buf, _merge_best_buf, _merge_cc_buf, _merge_cen_buf, _merge_ch_buf, _merge_cl_buf, _merge_cs_buf, _merge_mass_buf, _merge_mc_buf, _merge_mom_buf, _merge_mprev_buf, _merge_scr_buf, _merge_sink_buf, _merge_spin_buf, _ml_cen, _ml_grad_i, _ml_grad_y, _ml_labels_a, _ml_labels_b, _ml_lap_i, _ml_lap_y, _ml_lsm_i, _ml_lsm_y, _ml_pi_i, _ml_pi_y, _ml_psi_i, _ml_psi_y, _ml_remap, _ml_sites, _ml_tmp_i, _ml_tmp_pi, _ml_tmp_py, _ml_tmp_y, _ml_vol, _pos_buf, _shortlist_count, _shortlist_sites, _tel_buf, _tl_cf, _tl_ctr, _tl_key, _tl_nq, _tl_nqq, _tl_nr, _tl_nw, _tl_order, _tl_src, _tl_srcw, _tl_tic, _topology_adjacency, _topology_degree, _topology_meta, _topology_neighbors, _topology_offsets, _topology_open_labels, _topology_open_labels_scratch_a, _topology_open_labels_scratch_b, _topology_optical, _topology_status, _tree_grad, _tree_mc_buf, _vel_buf]
	free_buffers.append_array([_ml_sites_world, _ml_mass_fix, _ml_mass, _ml_q, _ml_eps])
	var free_cascade_buffers := [_cf_density_fix_buf]
	for rid in free_cascade_buffers:
		if rid.is_valid() and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	for rid in free_buffers:
		if rid.is_valid() and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	_clear_gpu_handles()
	if _owns_rd:
		_rd.free()
	_rd = null


func _clear_gpu_handles() -> void:
	_setup_done = false
	_setup_compute_done = false
	_pipes_done = false
	_ready = false
	_ml_ready = false
	_ml_tree_nsrc = 0
	_topology_ready = false
	_topology_generation = 0
	_render_query_generation = 0
	_topology_required_neighbors = -1
	_topology_overflow = -1
	_topology_neighbor_capacity = 0
	_topology_site_count = 0
	_meshless_query_ready = false
	_render_query_sites_cpu = PackedFloat32Array()
	_render_query_center = Vector3.ZERO
	_render_query_extents = Vector3.ZERO
	_render_topology_worker = null
	_render_topology_last_step = -1
	_render_topology_inflight = false
	_field_ey = RID(); _field_ei = RID(); _field_q = RID(); _field_vel = RID()
	_field_scratch = RID(); _fft_buf = RID(); _tel_buf = RID()
	_grad_buf = RID(); _grad_buf2 = RID()
	_pos_buf = RID(); _vel_buf = RID(); _acc_buf = RID()
	_cluster_buf = RID(); _bh_buf = RID()
	_mass_density_buf = RID(); _mass_density_fix = RID(); _tree_grad = RID()
	_ml_labels_a = RID(); _ml_labels_b = RID(); _ml_sites = RID()
	_ml_psi_y = RID(); _ml_psi_i = RID(); _ml_pi_y = RID(); _ml_pi_i = RID()
	_ml_lap_y = RID(); _ml_lap_i = RID(); _ml_vol = RID(); _ml_cen = RID()
	_ml_remap = RID(); _ml_tmp_y = RID(); _ml_tmp_i = RID()
	_ml_tmp_py = RID(); _ml_tmp_pi = RID(); _ml_grad_y = RID(); _ml_grad_i = RID()
	_ml_lsm_y = RID(); _ml_lsm_i = RID()
	_ml_sites_world = RID(); _ml_mass_fix = RID(); _ml_mass = RID()
	_ml_q = RID(); _ml_eps = RID()
	_shortlist_sites = RID(); _shortlist_count = RID()
	_hash_cell_start = RID(); _hash_cell_sites = RID(); _hash_cell_count = RID(); _hash_cfg = RID()
	_topology_open_labels = RID(); _topology_open_labels_scratch_a = RID(); _topology_open_labels_scratch_b = RID()
	_topology_adjacency = RID(); _topology_degree = RID(); _topology_offsets = RID()
	_topology_neighbors = RID(); _topology_optical = RID(); _topology_status = RID(); _topology_meta = RID()
	_tl_src = RID(); _tl_srcw = RID(); _tl_key = RID(); _tl_order = RID()
	_tl_cf = RID(); _tl_nw = RID(); _tl_nq = RID(); _tl_nr = RID(); _tl_ctr = RID()
	_tl_nqq = RID(); _tl_tic = RID(); _tree_mc_buf = RID()
	_merge_alive_buf = RID(); _merge_mass_buf = RID(); _merge_mom_buf = RID()
	_merge_cen_buf = RID(); _merge_best_buf = RID(); _merge_sink_buf = RID()
	_merge_cc_buf = RID(); _merge_cs_buf = RID(); _merge_ch_buf = RID()
	_merge_cl_buf = RID(); _merge_mc_buf = RID(); _merge_spin_buf = RID()
	_merge_mprev_buf = RID(); _merge_scr_buf = RID()
	_cf_density_buf = RID(); _cf_density_fix_buf = RID(); _cf_fft_buf = RID(); _cf_grad_buf = RID()
	_jfa_shader = RID(); _jfa_pipe = RID(); _cell_shader = RID(); _cell_pipe = RID()
	_raster_shader = RID(); _raster_pipe = RID()
	_shortlist_shader = RID(); _shortlist_pipe = RID()
	_hash_shader = RID(); _hash_pipe = RID()
	_topology_shader = RID(); _topology_pipe = RID()
	_topology_adj_shader = RID(); _topology_adj_pipe = RID()
	_topology_csr_shader = RID(); _topology_csr_pipe = RID()
	_topology_optical_shader = RID(); _topology_optical_pipe = RID()
	_tree_bld_sh = RID(); _tree_bld_pipe = RID(); _tree_walk_sh = RID(); _tree_walk_pipe = RID()
	_tree_mc_sh = RID(); _tree_mc_pipe = RID()
	_two_fluid_shader = RID(); _two_fluid_pipe = RID()
	_nbody_shader = RID(); _nbody_pipe = RID()
	_poisson_shader = RID(); _poisson_pipe = RID()
	_mass_deposit_shader = RID(); _mass_deposit_pipe = RID()
	_cond_shader = RID(); _cond_pipe = RID()
	_bh_int_shader = RID(); _bh_int_pipe = RID()
	_merge_shader = RID(); _merge_pipe = RID()
	_scan_shader = RID(); _scan_pipe = RID()
	_bh_acc_shader = RID(); _bh_acc_pipe = RID()
	_cf_grad_shader = RID(); _cf_grad_pipe = RID()
	_site_physics_shader = RID(); _site_physics_pipe = RID()
	_site_mass_shader = RID(); _site_mass_pipe = RID()
	_site_nbody_shader = RID(); _site_nbody_pipe = RID()
	_site_cond_shader = RID(); _site_cond_pipe = RID()
	_site_bh_int_shader = RID(); _site_bh_int_pipe = RID()
	_us_jfa_0 = RID(); _us_cell_0 = RID(); _us_raster_0 = RID()
	_us_shortlist = RID(); _us_hash = RID()
	_us_topology = RID(); _us_topology_adj = RID(); _us_topology_csr = RID(); _us_topology_optical = RID()
	_us_tree_bld = RID(); _us_tree_walk = RID(); _us_tree_mc = RID()
	_us_two_0 = RID(); _us_mass_dep_0 = RID()
	_us_site_physics = RID(); _us_site_mass = RID()
	_us_site_nbody_0 = RID(); _us_site_nbody_1 = RID(); _us_site_nbody_2 = RID()
	_us_site_cond_0 = RID(); _us_site_cond_1 = RID()
	_us_site_bh_int_0 = RID(); _us_site_bh_int_1 = RID()
	_us_nbody_0 = RID(); _us_nbody_1 = RID(); _us_nbody_2 = RID()
	_us_poisson_0 = RID(); _us_cond_0 = RID(); _us_cond_1 = RID()
	_us_bh_int_0 = RID(); _us_bh_int_1 = RID()
	_us_merge_0 = RID(); _us_scan_0 = RID(); _us_bh_acc_0 = RID(); _us_cf_grad_0 = RID()
	_us_poisson_c = RID(); _us_mass_dep_c = RID()
	
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


## Effective merge cadence in STEPS: the explicit export, else AUTO = 1/2
## of the R_m reaction budget (R_m/(v·dt) steps with v = 1.0 units/s — the
## design's closing speed; see the merge_cadence_steps comment). The
## measured job size is ~16-20 steps (step_cap = 16, engine coalescing), so
## a quarter-budget cadence (14) is < 1 job and the pass still runs every
## job — the cadence MUST exceed the job size to cut pass frequency: 1/2
## budget (28) lands every ~2 jobs at the owner config. Clamped >= 1.
## Cheap: a few multiplies, called once per gate check.
func _merge_cadence_eff() -> int:
	if merge_cadence_steps > 0:
		return merge_cadence_steps
	return maxi(1, int(0.5 * _extent_min() / float(maxi(grid_N, 1)) / maxf(dt, 1e-6)))


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
	var shader := _rd.shader_create_from_spirv(spirv)
	if not shader.is_valid():
		push_error("[PhysicsEngine] shader_create_from_spirv returned invalid: " + path)
	return shader


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
	_tel_buf  = _rd.storage_buffer_create(48)
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
		1.0 if cascade_level else 0.0, 0.0, 0.0, float(N_particles),
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
	if cascade_level:
		# The live deposit/Poisson shaders require the fixed-point uvec4
		# accumulator at binding 2/3; keep it cascade-only so OFF allocates
		# exactly the existing resource set.
		_cf_density_fix_buf = _rd.storage_buffer_create(cn3 * 16)
		var cfix_zero := PackedByteArray()
		cfix_zero.resize(cn3 * 16)
		_rd.buffer_update(_cf_density_fix_buf, 0, cfix_zero.size(), cfix_zero)
	_cf_grad_pc_bytes = PackedByteArray(); _cf_grad_pc_bytes.resize(8 * 4)
	# Mode-5 tree seam: per-particle tree gradient (nbody set 1 binding 3).
	# Zeroed once at setup so an unused seam reads zero force instead of
	# stale allocator memory; run_steps uploads when a gradient is supplied.
	_tree_grad = _rd.storage_buffer_create(maxi(N_particles, 1) * 16)
	var tz := PackedFloat32Array()
	tz.resize(maxi(N_particles, 1) * 4)
	# Production topology storage. Open labels are separate from periodic
	# physics labels; adjacency is a fixed bitset, while CSR is exact and
	# capacity is grow-only (never truncate a completed generation).
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var topo_words := ceili(float(ml_ns) / 32.0)
	_topology_open_labels = _rd.storage_buffer_create(grid_N * grid_N * grid_N * 4)
	_topology_open_labels_scratch_a = _rd.storage_buffer_create(grid_N * grid_N * grid_N * 4)
	_topology_open_labels_scratch_b = _rd.storage_buffer_create(grid_N * grid_N * grid_N * 4)
	_topology_status = _rd.storage_buffer_create(16)
	_topology_adjacency = _rd.storage_buffer_create(ml_ns * topo_words * 4)
	_topology_degree = _rd.storage_buffer_create(ml_ns * 4)
	_topology_offsets = _rd.storage_buffer_create((ml_ns + 1) * 4)
	_topology_neighbor_capacity = maxi(6 * grid_N * grid_N * maxi(grid_N - 1, 1), 1)
	_topology_neighbors = _rd.storage_buffer_create(_topology_neighbor_capacity * 4)
	_topology_optical = _rd.storage_buffer_create(ml_ns * 32)
	# The sampled open graph emits three positive faces per voxel. A face can
	# contribute two directed CSR entries, so 6*N²*(N−1) uints is a deterministic
	# safe bound independent of site count; actual offsets[N] is published by
	# the GPU CSR scan and overflow is explicit.
	_topology_meta = _rd.storage_buffer_create(32)
	_topology_site_count = ml_ns
	_topology_generation = 0
	_render_query_generation = 0
	_topology_required_neighbors = -1
	_topology_overflow = -1
	_topology_ready = false
	_meshless_query_ready = false
	_mesh_rebuild_pending = false
	var topo_zero := PackedByteArray()
	topo_zero.resize(16); topo_zero.fill(0)
	_rd.buffer_update(_topology_status, 0, topo_zero.size(), topo_zero)
	var topo_meta_zero := PackedByteArray()
	topo_meta_zero.resize(32); topo_meta_zero.fill(0)
	_rd.buffer_update(_topology_meta, 0, topo_meta_zero.size(), topo_meta_zero)
	_rd.buffer_update(_tree_grad, 0, tz.size() * 4, tz.to_byte_array())
	# ── Meshless arm buffers (allocated always; used only when meshless_mode
	# is on — the sim's precedent). The JFA labels ping-pong; the per-site
	# state carries the cell averages; the rebuild scratch rides the GPU.
	ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
	_ml_labels_a = _rd.storage_buffer_create(grid_N * grid_N * grid_N * 4)
	_ml_labels_b = _rd.storage_buffer_create(grid_N * grid_N * grid_N * 4)
	_ml_sites = _rd.storage_buffer_create(ml_ns * 16)
	# Site field state is packed as [authoritative | next] so the graph
	# operator can advance without adding descriptor bindings or read/write
	# races between CSR rows.
	_ml_psi_y = _rd.storage_buffer_create(ml_ns * 8)
	_ml_psi_i = _rd.storage_buffer_create(ml_ns * 8)
	# Arm 1 shortlist: sized for the worst case (every site coherent). The
	# instancer scans only the dense subset actually written by the pass.
	_shortlist_sites = _rd.storage_buffer_create(ml_ns * 16)
	_shortlist_count = _rd.storage_buffer_create(4)
	# Boxless site hash (boxless_site_hash_prereg.md): n_cells = HASH_H³ (+1 for
	# the prefix sentinel), cell_sites sized for the worst case (every site in
	# one cell), a cfg vec4 for the query's box_min.xyz + cell_side.
	var hcells := HASH_H * HASH_H * HASH_H
	_hash_cell_start = _rd.storage_buffer_create((hcells + 1) * 4)
	_hash_cell_sites = _rd.storage_buffer_create(maxi(ml_ns, 1) * 4)
	_hash_cell_count = _rd.storage_buffer_create(hcells * 4)
	_hash_cfg = _rd.storage_buffer_create(16)
	_ml_pi_y = _rd.storage_buffer_create(ml_ns * 8)
	_ml_pi_i = _rd.storage_buffer_create(ml_ns * 8)
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
	_ml_sites_world = _rd.storage_buffer_create(ml_ns * 16)
	_ml_mass_fix = _rd.storage_buffer_create(ml_ns * 16)
	_ml_mass = _rd.storage_buffer_create(ml_ns * 4)
	_ml_q = _rd.storage_buffer_create(ml_ns * 4)
	_ml_eps = _rd.storage_buffer_create(ml_ns * 4)
	_ml_lsm_i = _rd.storage_buffer_create(ml_ns * 3 * 16)
	_ml_tree_nsrc = ml_ns
	_jfa_pc_bytes = PackedByteArray(); _jfa_pc_bytes.resize(8 * 4)
	_cell_pc_bytes = PackedByteArray(); _cell_pc_bytes.resize(18 * 4)
	_raster_pc_bytes = PackedByteArray(); _raster_pc_bytes.resize(8 * 4)
	_hash_pc_bytes = PackedByteArray(); _hash_pc_bytes.resize(9 * 4)  # ext_xyz, H, shortlist, tile origin xyz, mode
	_ml_ready = false

	# ── Particle-merge buffers (INIT-TIME: allocated only when particle_merge)
	# The merge kernel's persistent per-particle state (alive/mass/mom/cen/
	# best/sink) + the spatial-hash scratch (cc/cs/ch/cl) + the merge counter.
	# Hash sized so each cell width ≥ R_m (the 27-neighbor pass_best provably
	# covers every in-range pair): hash_nx_i = ⌊2·extent_i/R_m⌋, which at the
	# default cube is exactly 2·grid_N per axis. R_m = ½·h₀ with h₀ =
	# 2·extent_min/grid_N (matches the sim's convention).
	if particle_merge and N_particles > 0:
		# Hash geometry via the shared helper (dedup — identical to the sim's
		# twin; see CassiMergeCommon.hash_geometry).
		var geom := CassiMergeCommon.hash_geometry(_extents(), _extent_min() / float(maxi(grid_N, 1)))
		_merge_hash_nx = geom["nx"]
		_merge_hash_ny = geom["ny"]
		_merge_hash_nz = geom["nz"]
		_merge_hash_total = geom["total"]
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
		_merge_cell_wx = geom["cell_wx"]
		_merge_cell_wy = geom["cell_wy"]
		_merge_cell_wz = geom["cell_wz"]
		_merge_pc_bytes = PackedByteArray(); _merge_pc_bytes.resize(26 * 4)   # 26 floats = 104 B (n_sites@25) — F8: pre-sized, never reassigned

	# Pre-allocate push-constant byte buffers (hitch-free pattern)
	_pc_bytes = PackedByteArray(); _pc_bytes.resize(11 * 4)
	_nbody_pc_bytes = PackedByteArray(); _nbody_pc_bytes.resize(15 * 4)
	_two_fluid_pc_bytes = PackedByteArray(); _two_fluid_pc_bytes.resize(17 * 4)  # + pass_sel (PDE pass A/B) + omega2 (ω₀²) + ham_completion (U1, offset 64)
	_two_fluid_pc_bytes.encode_float(64, 0.0)  # U1 ham_completion OFF (flip to 1.0 for the ON arm)
	_md_pc_bytes = PackedByteArray(); _md_pc_bytes.resize(9 * 4)  # + mode (deposit 0 / convert 1)
	_bh_int_pc_bytes = PackedByteArray(); _bh_int_pc_bytes.resize(4 * 4)
	_cond_pc_bytes = PackedByteArray(); _cond_pc_bytes.resize(4 * 4)
	_bh_acc_pc_bytes = PackedByteArray(); _bh_acc_pc_bytes.resize(4 * 4)
	_poisson_pc_bytes = PackedByteArray(); _poisson_pc_bytes.resize(7 * 4)
	_site_physics_pc_bytes = PackedByteArray(); _site_physics_pc_bytes.resize(16 * 4)
	_site_mass_pc_bytes = PackedByteArray(); _site_mass_pc_bytes.resize(12 * 4)
	_site_nbody_pc_bytes = PackedByteArray(); _site_nbody_pc_bytes.resize(15 * 4)
	_site_cond_pc_bytes = PackedByteArray(); _site_cond_pc_bytes.resize(4 * 4)
	_site_bh_int_pc_bytes = PackedByteArray(); _site_bh_int_pc_bytes.resize(4 * 4)
	# Telemetry reset (kept for reference; the per-step reset runs on the GPU
	# in the poisson clear pass so chained steps stay independent)
	_tel_reset_bytes = PackedFloat32Array([0.0, 0.0, 0.0, INF, 0.0, INF, 0.0, 0.0]).to_byte_array()


## Return true when every pipeline required by the setup/readiness path is valid.
func _pipelines_ready() -> bool:
	return (
		_two_fluid_pipe.is_valid() and _nbody_pipe.is_valid()
		and _poisson_pipe.is_valid() and _mass_deposit_pipe.is_valid()
		and _cond_pipe.is_valid() and _bh_int_pipe.is_valid()
		and (not gridless_physics or (
			_site_physics_pipe.is_valid() and _site_mass_pipe.is_valid()
			and _site_nbody_pipe.is_valid() and _site_cond_pipe.is_valid()
			and _site_bh_int_pipe.is_valid()))
		and (not particle_merge or _merge_pipe.is_valid())
		and (not particle_merge or _scan_pipe.is_valid())
		and (not bh_accretion or _bh_acc_pipe.is_valid())
		and (not cascade_level or _cf_grad_pipe.is_valid())
		and _jfa_pipe.is_valid() and _cell_pipe.is_valid() and _raster_pipe.is_valid()
		and _topology_pipe.is_valid() and _topology_adj_pipe.is_valid()
		and _topology_csr_pipe.is_valid() and _topology_optical_pipe.is_valid()
	)


## Create the shaders + compute pipelines ONLY (no buffers, no uniform
## sets) — the M0b-P-FX split: pipeline creation is NOT render-thread-gated
## (empirically: only global-RD buffer_update + compute lists are), so the
## global-RD path's worker runs this (the boot's ~600 ms pipeline-compile
## hitch returns to the worker); the uniform sets need the BUFFERS (which
## need the render thread for their zero-fill updates), so _cache_uniform_sets
## stays in finish_setup. Idempotent (_pipes_done).


func _create_pipelines() -> void:
	if _pipes_done:
		return
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
	if gridless_physics:
		_site_physics_shader = _shader_create("res://compute/cassi_site_physics.glsl")
		if _site_physics_shader.is_valid():
			_site_physics_pipe = _rd.compute_pipeline_create(_site_physics_shader)
		_site_mass_shader = _shader_create("res://compute/cassi_site_mass.glsl")
		if _site_mass_shader.is_valid():
			_site_mass_pipe = _rd.compute_pipeline_create(_site_mass_shader)
		_site_nbody_shader = _shader_create("res://compute/cassi_site_nbody.glsl")
		if _site_nbody_shader.is_valid():
			_site_nbody_pipe = _rd.compute_pipeline_create(_site_nbody_shader)
		_site_cond_shader = _shader_create("res://compute/cassi_site_condensation.glsl")
		if _site_cond_shader.is_valid():
			_site_cond_pipe = _rd.compute_pipeline_create(_site_cond_shader)
		_site_bh_int_shader = _shader_create("res://compute/cassi_site_bh_integrate.glsl")
		if _site_bh_int_shader.is_valid():
			_site_bh_int_pipe = _rd.compute_pipeline_create(_site_bh_int_shader)
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
	# Arm 1 shortlist (coherence-filtered site subset — see cassi_site_shortlist.glsl)
	_shortlist_shader = _shader_create("res://compute/cassi_site_shortlist.glsl")
	if _shortlist_shader.is_valid():
		_shortlist_pipe = _rd.compute_pipeline_create(_shortlist_shader)
	# Boxless site hash (boxless_site_hash_prereg.md) — buckets the shortlist.
	_hash_shader = _shader_create("res://compute/cassi_site_hash.glsl")
	if _hash_shader.is_valid():
		_hash_pipe = _rd.compute_pipeline_create(_hash_shader)
	_raster_shader = _shader_create("res://compute/cassi_voronoi_raster.glsl")
	if _raster_shader.is_valid():
		_raster_pipe = _rd.compute_pipeline_create(_raster_shader)
	# Production open-render topology chain: labels → sampled adjacency → exact CSR → optical payload.
	_topology_shader = _shader_create("res://compute/cassi_voronoi_render_topology.glsl")
	if _topology_shader.is_valid():
		_topology_pipe = _rd.compute_pipeline_create(_topology_shader)
	_topology_adj_shader = _shader_create("res://compute/cassi_voronoi_render_adjacency.glsl")
	if _topology_adj_shader.is_valid():
		_topology_adj_pipe = _rd.compute_pipeline_create(_topology_adj_shader)
	_topology_csr_shader = _shader_create("res://compute/cassi_voronoi_adjacency_csr.glsl")
	if _topology_csr_shader.is_valid():
		_topology_csr_pipe = _rd.compute_pipeline_create(_topology_csr_shader)
	_topology_optical_shader = _shader_create("res://compute/cassi_voronoi_optical_payload.glsl")
	if _topology_optical_shader.is_valid():
		_topology_optical_pipe = _rd.compute_pipeline_create(_topology_optical_shader)
	_pipes_done = true


func _setup_shaders() -> void:
	# Production open-render topology sets.
	if _topology_shader.is_valid():
		_us_topology = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites),
			_uniform_storage(1, _topology_open_labels_scratch_a),
			_uniform_storage(2, _topology_open_labels_scratch_b),
			_uniform_storage(3, _topology_open_labels),
		], _topology_shader, 0)
	if _topology_adj_shader.is_valid():
		_us_topology_adj = _rd.uniform_set_create([
			_uniform_storage(0, _topology_open_labels),
			_uniform_storage(1, _topology_adjacency),
		], _topology_adj_shader, 0)
	if _topology_csr_shader.is_valid():
		_us_topology_csr = _rd.uniform_set_create([
			_uniform_storage(0, _topology_adjacency),
			_uniform_storage(1, _topology_offsets),
			_uniform_storage(2, _topology_degree),
			_uniform_storage(3, _topology_neighbors),
			_uniform_storage(4, _topology_status),
		], _topology_csr_shader, 0)
	if _topology_optical_shader.is_valid():
		_us_topology_optical = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites), _uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i), _uniform_storage(3, _ml_grad_y),
			_uniform_storage(4, _ml_grad_i), _uniform_storage(5, _topology_optical),
		], _topology_optical_shader, 0)
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
			# ── Boxless site read set (merge_boxless_prereg.md §4) ──
			# The moving-Voronoi site's cell-averaged field + AREPO gradient +
			# momentum density. Immutable — zero-cost when the boxless flag is 0.
			_uniform_storage(18, _ml_sites), _uniform_storage(19, _ml_psi_y),
			_uniform_storage(20, _ml_psi_i), _uniform_storage(21, _ml_grad_y),
			_uniform_storage(22, _ml_grad_i), _uniform_storage(23, _ml_pi_y),
			_uniform_storage(24, _ml_pi_i),
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
	# Cascade-multigrid sets (all use the live shader ABI: the fixed-point
	# uvec4 accumulator is binding 2 of deposit and binding 3 of Poisson).
	if cascade_level:
		if _cf_grad_shader.is_valid():
			_us_cf_grad_0 = _rd.uniform_set_create([
				_uniform_storage(0, _cf_fft_buf),
				_uniform_storage(1, _field_ey),
				_uniform_storage(2, _field_ei),
				_uniform_storage(3, _cf_grad_buf),
			], _cf_grad_shader, 0)
		if _poisson_shader.is_valid() and _cf_density_fix_buf.is_valid():
			_us_poisson_c = _rd.uniform_set_create([
				_uniform_storage(0, _cf_fft_buf),
				_uniform_storage(1, _cf_density_buf),
				_uniform_storage(2, _tel_buf),
				_uniform_storage(3, _cf_density_fix_buf),
			], _poisson_shader, 0)
		if _mass_deposit_shader.is_valid() and _cf_density_fix_buf.is_valid():
			_us_mass_dep_c = _rd.uniform_set_create([
				_uniform_storage(0, _pos_buf),
				_uniform_storage(1, _cf_density_buf),
				_uniform_storage(2, _cf_density_fix_buf),
			], _mass_deposit_shader, 0)
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
	if _shortlist_shader.is_valid():
		_us_shortlist = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites),
			_uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i),
			_uniform_storage(3, _shortlist_sites),
			_uniform_storage(4, _shortlist_count),
		], _shortlist_shader, 0)
	if _hash_shader.is_valid():
		_us_hash = _rd.uniform_set_create([
			_uniform_storage(0, _shortlist_sites),
			_uniform_storage(1, _hash_cell_start),
			_uniform_storage(2, _hash_cell_sites),
			_uniform_storage(3, _hash_cell_count),
			_uniform_storage(4, _shortlist_count),
		], _hash_shader, 0)
	if _raster_shader.is_valid():
		_us_raster_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_labels_a), _uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i), _uniform_storage(3, _field_ey),
			_uniform_storage(4, _field_ei), _uniform_storage(5, _field_q),
			_uniform_storage(6, _ml_grad_y), _uniform_storage(7, _ml_grad_i),
			_uniform_storage(8, _ml_sites),
		], _raster_shader, 0)
	if gridless_physics:
		_us_site_physics = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites), _uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i), _uniform_storage(3, _ml_pi_y),
			_uniform_storage(4, _ml_pi_i), _uniform_storage(5, _ml_vol),
			_uniform_storage(6, _ml_mass), _uniform_storage(7, _topology_offsets),
			_uniform_storage(8, _topology_neighbors), _uniform_storage(9, _ml_grad_y),
			_uniform_storage(10, _ml_grad_i), _uniform_storage(11, _ml_lap_y),
			_uniform_storage(12, _ml_lap_i), _uniform_storage(13, _ml_q),
			_uniform_storage(14, _ml_eps), _uniform_storage(15, _tel_buf),
			_uniform_storage(16, _topology_status),
		], _site_physics_shader, 0)
		_us_site_mass = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf), _uniform_storage(1, _ml_sites),
			_uniform_storage(2, _hash_cell_start), _uniform_storage(3, _hash_cell_sites),
			_uniform_storage(4, _hash_cfg), _uniform_storage(5, _ml_mass_fix),
			_uniform_storage(6, _ml_mass),
		], _site_mass_shader, 0)
		_us_site_nbody_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites), _uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i), _uniform_storage(3, _ml_q),
			_uniform_storage(4, _hash_cell_start), _uniform_storage(5, _hash_cell_sites),
			_uniform_storage(6, _hash_cfg), _uniform_storage(7, _ml_grad_y),
			_uniform_storage(8, _ml_grad_i), _uniform_storage(9, _ml_mass),
			_uniform_storage(10, _tel_buf),
		], _site_nbody_shader, 0)
		_us_site_nbody_1 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf), _uniform_storage(1, _vel_buf),
			_uniform_storage(2, _acc_buf), _uniform_storage(3, _tree_grad),
		], _site_nbody_shader, 1)
		_us_site_nbody_2 = _rd.uniform_set_create([
			_uniform_storage(0, _bh_buf), _uniform_storage(1, _cluster_buf),
		], _site_nbody_shader, 2)
		_us_site_cond_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites), _uniform_storage(1, _ml_q),
			_uniform_storage(2, _ml_vol),
		], _site_cond_shader, 0)
		_us_site_cond_1 = _rd.uniform_set_create([
			_uniform_storage(0, _bh_buf),
		], _site_cond_shader, 1)
		_us_site_bh_int_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites), _uniform_storage(1, _ml_q),
			_uniform_storage(2, _ml_vol),
		], _site_bh_int_shader, 0)
		_us_site_bh_int_1 = _rd.uniform_set_create([
			_uniform_storage(0, _bh_buf),
		], _site_bh_int_shader, 1)
	_ready = (
		_two_fluid_pipe.is_valid() and _nbody_pipe.is_valid()
		and _poisson_pipe.is_valid() and _mass_deposit_pipe.is_valid()
		and _cond_pipe.is_valid() and _bh_int_pipe.is_valid()
		and (not gridless_physics or (
			_site_physics_pipe.is_valid() and _site_mass_pipe.is_valid()
			and _site_nbody_pipe.is_valid() and _site_cond_pipe.is_valid()
			and _site_bh_int_pipe.is_valid() and _us_site_physics.is_valid()
			and _us_site_mass.is_valid() and _us_site_nbody_0.is_valid()
			and _us_site_nbody_1.is_valid() and _us_site_nbody_2.is_valid()
			and _us_site_cond_0.is_valid() and _us_site_cond_1.is_valid()
			and _us_site_bh_int_0.is_valid() and _us_site_bh_int_1.is_valid()))
		and (not particle_merge or _scan_pipe.is_valid())
		and (not bh_accretion or _bh_acc_pipe.is_valid())
		and (not cascade_level or (
			_cf_grad_pipe.is_valid() and _us_cf_grad_0.is_valid()
			and _us_poisson_c.is_valid() and _us_mass_dep_c.is_valid()
			and _cf_density_buf.is_valid() and _cf_density_fix_buf.is_valid()
			and _cf_fft_buf.is_valid() and _cf_grad_buf.is_valid()))
		and _jfa_pipe.is_valid() and _cell_pipe.is_valid() and _raster_pipe.is_valid()
		and _topology_pipe.is_valid() and _topology_adj_pipe.is_valid()
		and _topology_csr_pipe.is_valid() and _topology_optical_pipe.is_valid()
		and _us_topology.is_valid() and _us_topology_adj.is_valid()
		and _us_topology_csr.is_valid() and _us_topology_optical.is_valid()
		and _topology_open_labels.is_valid() and _topology_open_labels_scratch_a.is_valid()
		and _topology_open_labels_scratch_b.is_valid() and _topology_adjacency.is_valid()
		and _topology_degree.is_valid() and _topology_offsets.is_valid()
		and _topology_neighbors.is_valid() and _topology_optical.is_valid()
		and _topology_status.is_valid()
	)


## (Re)build the tree momentum-conservation uniform set (acc, positions, the
## 16-B Reduce accumulator). Called from _cache_uniform_sets and once after
## the pipeline exists at meshless setup.
func _sync_us_tree_mc() -> void:
	if not _tree_mc_sh.is_valid() or not _acc_buf.is_valid() or not _pos_buf.is_valid() or not _vel_buf.is_valid() or not _tree_mc_buf.is_valid():
		return
	_us_tree_mc = _rd.uniform_set_create([
		_uniform_storage(0, _acc_buf),
		_uniform_storage(1, _pos_buf),
		_uniform_storage(2, _tree_mc_buf),
		_uniform_storage(3, _vel_buf),
	], _tree_mc_sh, 0)
	if not _us_tree_mc.is_valid():
		push_error("[PhysicsEngine] tree-momcon uniform set FAILED to create (bindings 0-3)")


# ═══════════════════════════════════════════════════════════════════════
# Initial conditions (ported verbatim — the seeded Gaussian/site placement)
# ═══════════════════════════════════════════════════════════════════════

func _init_field() -> void:
	if gridless_physics:
		# The site path owns the field IC. Do not allocate, seed, or upload an
		# N³ raster state; the legacy RIDs remain allocated only for ABI
		# compatibility with explicit grid scenes.
		_ml_ready = false
		_meshless_init()
		print("[PhysicsEngine] Site-native field initialized (no raster field state)")
		return
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


func _init_particles_cpu() -> void:
	# M0b-P: the CPU-side IC generation into the HOST arrays (the worker's
	# setup — no GPU calls; the uploads are the main thread's job in
	# finish_setup). The stat prints are the same as the legacy path.
	_host_pos = PackedFloat32Array(); _host_pos.resize(N_particles * 4)
	_host_vel = PackedFloat32Array(); _host_vel.resize(N_particles * 4)
	_host_acc = PackedFloat32Array(); _host_acc.resize(N_particles * 4)
	var pos := _host_pos
	var vel := _host_vel
	var acc := _host_acc
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
		# IC-truncation ceiling: home-window OFF = the legacy box ceiling
		# (fr·min(extent)); ON = the cluster's own scale (fr·cluster_radius)
		# — the box ceases to bound the initial structure (perf-decomp
		# 2026-08-15, overhaul migration).
		var r_max_c: float = fr * (cluster_radius if _home_window else extent_min) - c_abs
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
	_host_cluster = cluster_data
	_host_cluster_recs = n_rec

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

	# M0b-P: the IC arrays stay HOST-side (the worker cannot buffer_update
	# the global RD — render-thread-only); finish_setup's _upload_particles
	# ships them.
	_host_pos = pos
	_host_vel = vel
	_host_acc = acc

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


## M0b-P: the IC host arrays → the GPU buffers. MAIN THREAD (the global
## RD's buffer_update is render-thread-only — the worker's CPU-side
## _init_particles_cpu can only stash). Called by finish_setup.
func _upload_particles() -> void:
	if _host_cluster.size() > 0:
		_rd.buffer_update(_cluster_buf, 0, _host_cluster_recs * 4 * 4, _host_cluster.to_byte_array())
	if _host_pos.size() > 0:
		_rd.buffer_update(_pos_buf, 0, _host_pos.size() * 4, _host_pos.to_byte_array())
	if _host_vel.size() > 0:
		_rd.buffer_update(_vel_buf, 0, _host_vel.size() * 4, _host_vel.to_byte_array())
	if _host_acc.size() > 0:
		_rd.buffer_update(_acc_buf, 0, _host_acc.size() * 4, _host_acc.to_byte_array())
	_host_pos = PackedFloat32Array()
	_host_vel = PackedFloat32Array()
	_host_acc = PackedFloat32Array()
	_host_cluster = PackedFloat32Array()


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
	var world_sites := PackedFloat32Array()
	world_sites.resize(sites.size())
	for s in range(ml_ns):
		var so := s * 4
		world_sites[so] = sites[so] - ext.x + _window_center.x
		world_sites[so + 1] = sites[so + 1] - ext.y + _window_center.y
		world_sites[so + 2] = sites[so + 2] - ext.z + _window_center.z
		world_sites[so + 3] = sites[so + 3]
	_rd.buffer_update(_ml_sites_world, 0, world_sites.size() * 4, world_sites.to_byte_array())

	if gridless_physics:
		_init_site_volumes_direct(sites, ml_ns, ext)
	else:
		# Legacy geometry path: JFA labels and raster cell volumes.
		_ml_scatter_and_jfa()
		_ml_volume_pass()
	if gridless_physics:
		_init_site_state_direct(sites, ml_ns, ext)
	else:
		# Legacy compatibility path: sample the initialized field grid into
		# the moving-site state.
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
	# The local-RD verifier path can publish one topology chain during
	# initialization and rebuild it on its cadence. The live decoupled path
	# requests the same chain for the next renderer-owned global list; it
	# must not open a second list on the shared device.
	if meshless_mode and boxless_field and not _rd_global:
		_mesh_rebuild()
	_ml_ready = true
	if meshless_mode and _rd_global:
		_mesh_rebuild_pending = true
	# TREE-IN-LIST (M0 commit 2): the tree build+walk resources on THIS
	# engine RD — pipelines + intermediates + uniform sets over the LIVE
	# meshless buffers. The mode-7 gather reads ml_sites/psy/psi/vol and
	# the deposit density directly; the walk reads _pos_buf and writes
	# _tree_grad (the mode-5 seam buffer) — no staging, no seam upload.
	var tnm := ML_TREE_NODE_MAX_MULT * ml_ns + 64
	_tl_src = _rd.storage_buffer_create(2 * ml_ns * 16)
	_tl_srcw = _rd.storage_buffer_create(ml_ns * 4)
	_tl_key = _rd.storage_buffer_create(ml_ns * 4)
	_tl_order = _rd.storage_buffer_create(ml_ns * 4)
	_tl_cf = _rd.storage_buffer_create(tnm * 16)
	_tl_nw = _rd.storage_buffer_create(tnm * 16)
	_tl_nq = _rd.storage_buffer_create(2 * tnm * 16)
	_tl_nr = _rd.storage_buffer_create(tnm * 16)
	_tl_nqq = _rd.storage_buffer_create(tnm * 4)  # Arm 2: per-node mean coherence q
	_tl_ctr = _rd.storage_buffer_create(8 * 4)
	_tl_tic = _rd.storage_buffer_create(maxi(N_particles, 1) * 4)
	_tree_bld_sh = _shader_create("res://compute/cassi_tree_build.glsl")
	if _tree_bld_sh.is_valid():
		_tree_bld_pipe = _rd.compute_pipeline_create(_tree_bld_sh)
	_tree_walk_sh = _shader_create("res://compute/cassi_tree_gravity.glsl")
	if _tree_walk_sh.is_valid():
		_tree_walk_pipe = _rd.compute_pipeline_create(_tree_walk_sh)
	if _tree_bld_sh.is_valid():
		var tree_sites: RID = _ml_sites_world if gridless_physics else _ml_sites
		var tree_mass: RID = _ml_mass if gridless_physics else _mass_density_buf
		_us_tree_bld = _rd.uniform_set_create([
			_uniform_storage(0, _tl_src), _uniform_storage(1, _tl_srcw),
			_uniform_storage(2, _tl_key), _uniform_storage(3, _tl_order),
			_uniform_storage(4, _tl_cf), _uniform_storage(5, _tl_nw),
			_uniform_storage(6, _tl_nq), _uniform_storage(7, _tl_nr),
			_uniform_storage(8, _tl_ctr),
			_uniform_storage(9, tree_sites), _uniform_storage(10, _ml_psi_y),
			_uniform_storage(11, _ml_psi_i), _uniform_storage(12, _ml_vol),
			_uniform_storage(13, tree_mass),
			_uniform_storage(14, _tl_nqq),
		], _tree_bld_sh, 0)
	if _tree_walk_sh.is_valid():
		_us_tree_walk = _rd.uniform_set_create([
			_uniform_storage(0, _tl_src), _uniform_storage(3, _tl_order),
			_uniform_storage(4, _tl_cf), _uniform_storage(5, _tl_nw),
			_uniform_storage(6, _tl_nq), _uniform_storage(7, _tl_nr),
			_uniform_storage(8, _tl_ctr), _uniform_storage(9, _tree_grad),
			_uniform_storage(10, _tl_tic), _uniform_storage(11, _pos_buf),
			_uniform_storage(14, _tl_nqq),
		], _tree_walk_sh, 0)
	# Tree momentum-conservation pass (cassi_tree_momcon.glsl): Reduce
	# accumulator + pipeline + uniform set (acc, positions, sum).
	if _tree_walk_sh.is_valid():
		_tree_mc_sh = _shader_create("res://compute/cassi_tree_momcon.glsl")
		if _tree_mc_sh.is_valid():
			_tree_mc_pipe = _rd.compute_pipeline_create(_tree_mc_sh)
		_tree_mc_buf = _rd.storage_buffer_create(2 * 16)   # vec4[2] reduce accumulator
		_tree_mc_pc_bytes = PackedByteArray(); _tree_mc_pc_bytes.resize(3 * 4)
		_sync_us_tree_mc()
	print("[PhysicsEngine] Meshless arm ready: %d Voronoi cells on the %d^3 accelerator grid"
		% [ml_ns, N])


func _init_site_volumes_direct(sites: PackedFloat32Array, ns: int, ext: Vector3) -> void:
	if sites.size() < ns * 4:
		return
	var vol := PackedFloat32Array()
	vol.resize(ns)
	var uniform := (2.0 * ext.x) * (2.0 * ext.y) * (2.0 * ext.z) / float(maxi(ns, 1))
	for i in range(ns):
		vol[i] = uniform
	_rd.buffer_update(_ml_vol, 0, vol.size() * 4, vol.to_byte_array())


func _init_site_state_direct(sites: PackedFloat32Array, ns: int, ext: Vector3) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = _seed if _seed_set else 20260813
	var psy := PackedFloat32Array()
	var psi := PackedFloat32Array()
	var q := PackedFloat32Array()
	var eps := PackedFloat32Array()
	psy.resize(ns)
	psi.resize(ns)
	q.resize(ns)
	eps.resize(ns)
	for s in range(ns):
		var o := s * 4
		if field_attractor_init:
			var ei_v := 0.01 * (1.0 + 0.1 * rng.randf_range(-1.0, 1.0))
			var ey_v := PHI * ei_v + rng.randf_range(-0.001, 0.001)
			psy[s] = ey_v
			psi[s] = ei_v
		else:
			psy[s] = rng.randf_range(-0.01, 0.01)
			psi[s] = rng.randf_range(-0.01, 0.01)
		var rho := psy[s] + psi[s]
		var e := psy[s] - PHI * psi[s]
		q[s] = rho * rho / maxf(rho * rho + PHI_INV2 + e * e, 1e-30)
		eps[s] = e
	var zero := PackedByteArray()
	zero.resize(ns * 4)
	var state_zero := PackedByteArray()
	state_zero.resize(ns * 8)
	var grad_zero := PackedByteArray()
	grad_zero.resize(ns * 16)
	var mass_zero := PackedByteArray()
	mass_zero.resize(ns * 16)
	_rd.buffer_update(_ml_psi_y, 0, psy.size() * 4, psy.to_byte_array())
	_rd.buffer_update(_ml_psi_y, ns * 4, ns * 4, zero)
	_rd.buffer_update(_ml_psi_i, 0, psi.size() * 4, psi.to_byte_array())
	_rd.buffer_update(_ml_psi_i, ns * 4, ns * 4, zero)
	_rd.buffer_update(_ml_pi_y, 0, ns * 8, state_zero)
	_rd.buffer_update(_ml_pi_i, 0, ns * 8, state_zero)
	_rd.buffer_update(_ml_q, 0, q.size() * 4, q.to_byte_array())
	_rd.buffer_update(_ml_eps, 0, eps.size() * 4, eps.to_byte_array())
	var tel := PackedByteArray()
	tel.resize(48)
	tel.encode_float(12, INF)
	tel.encode_float(16, 0.0)
	tel.encode_float(20, INF)
	tel.encode_float(24, 0.0)
	_rd.buffer_update(_tel_buf, 0, tel.size(), tel)
	_rd.buffer_update(_ml_mass_fix, 0, ns * 16, mass_zero)
	_rd.buffer_update(_ml_mass, 0, ns * 4, zero)
	_rd.buffer_update(_ml_grad_y, 0, grad_zero.size(), grad_zero)
	_rd.buffer_update(_ml_grad_i, 0, grad_zero.size(), grad_zero)


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
		dt * float(ML_REBUILD), ML_LLOYD_P, winding_coupling])
	return pcb.to_byte_array()


func _ml_cell_dispatch(mode: float, groups: int) -> void:
	_cell_pc_bytes = _ml_cell_pc(mode)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, groups, 1, 1)
	_rd.compute_list_end()
## Prepare host-written rebuild state before a global-RD command list opens.
## RenderingDevice forbids buffer_update while any compute list is recording.
func prepare_mesh_rebuild() -> bool:
	if _rd == null or not _ready:
		return false
	if _topology_status.is_valid():
		var invalid := PackedByteArray(); invalid.resize(16); invalid.fill(0)
		_rd.buffer_update(_topology_status, 0, invalid.size(), invalid)
	if _hash_pipe.is_valid() and _hash_cfg.is_valid():
		var ext_p := _extents()
		var hcs_cfg := (2.0 * ext_p.x) / float(HASH_H)
		_rd.buffer_update(_hash_cfg, 0, 16,
			PackedFloat32Array([0.0, 0.0, 0.0, hcs_cfg]).to_byte_array())
	return true

## Record the complete meshless rebuild into an existing command list when
## the live renderer owns global RD; with the default -1 it retains the local
## standalone-list behavior used by the verifier arms.
func _mesh_rebuild(existing_cl: int = -1) -> void:
	if _rd_global:
		_mesh_rebuild_pending = false
		return
	var owns_list := existing_cl < 0
	if owns_list and not prepare_mesh_rebuild():
		return
	var N := grid_N
	var ml_ns := 2 * ML_N1 * ML_N1 * ML_N1
	var ext_rb := _extents()
	var hx_rb: float = 2.0 * ext_rb.x / float(N)
	var hy_rb: float = 2.0 * ext_rb.y / float(N)
	var hz_rb: float = 2.0 * ext_rb.z / float(N)
	var wg1 := maxi(N * N * N / 64, 1)
	var wgs := maxi(int(ceil(float(ml_ns) / 64.0)), 1)
	var topo_words := ceili(float(ml_ns) / 32.0)
	var topology_chain_valid := _topology_pipe.is_valid() and _topology_adj_pipe.is_valid() and _topology_csr_pipe.is_valid() and _topology_optical_pipe.is_valid() and _us_topology.is_valid() and _us_topology_adj.is_valid() and _us_topology_csr.is_valid() and _us_topology_optical.is_valid() and _topology_status.is_valid() and _topology_open_labels.is_valid() and _topology_open_labels_scratch_a.is_valid() and _topology_open_labels_scratch_b.is_valid() and _topology_adjacency.is_valid() and _topology_degree.is_valid() and _topology_offsets.is_valid() and _topology_neighbors.is_valid() and _topology_optical.is_valid()
	var query_chain_valid := topology_chain_valid and _shortlist_pipe.is_valid() and _us_shortlist.is_valid() and _hash_pipe.is_valid() and _us_hash.is_valid() and _hash_cfg.is_valid() and _hash_cell_count.is_valid() and _hash_cell_start.is_valid() and _hash_cell_sites.is_valid()
	var next_generation := _topology_generation + 1
	var cl := existing_cl
	if owns_list:
		cl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	for cell_mode in [7.0, 3.0, 4.0, 5.0, 6.0, 8.0, 9.0]:
		_cell_pc_bytes = _ml_cell_pc(cell_mode)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1 if cell_mode == 3.0 or cell_mode == 8.0 else wgs, 1, 1)
		_barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _jfa_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_jfa_0, 0)
	var read_a := 1
	for jp in [1, 2, 4, 8, 16, 32, 16, 8, 4, 2, 1, 1, 1]:
		_jfa_pc_bytes = PackedFloat32Array([float(N), float(jp), float(read_a), float(ml_ns), hx_rb, hy_rb, hz_rb, 0.0]).to_byte_array()
		_rd.compute_list_set_push_constant(cl, _jfa_pc_bytes, _jfa_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
		_barrier(cl)
		read_a = 1 - read_a
	_jfa_pc_bytes = PackedFloat32Array([float(N), 0.0, 0.0,
		float(ml_ns), hx_rb, hy_rb, hz_rb, 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _jfa_pc_bytes, _jfa_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	_cell_pc_bytes = _ml_cell_pc(2.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _topology_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_topology, 0)
	_topology_pc_bytes = PackedFloat32Array([float(N), float(ml_ns), 0.0,
		0.0, 0.0, 0.0, 0.0, 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_barrier(cl)
	_topology_pc_bytes = PackedFloat32Array([float(N), float(ml_ns), 1.0,
		0.0, 0.0, ext_rb.x, ext_rb.y, ext_rb.z]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	var open_read_a := 1.0
	var open_jump := 1
	while open_jump < N: open_jump *= 2
	open_jump /= 2
	while open_jump >= 1:
		_topology_pc_bytes = PackedFloat32Array([float(N), float(ml_ns), 2.0,
			open_read_a, float(open_jump), ext_rb.x, ext_rb.y, ext_rb.z]).to_byte_array()
		_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1); _barrier(cl)
		open_read_a = 1.0 - open_read_a
		open_jump /= 2
	_topology_pc_bytes = PackedFloat32Array([float(N), float(ml_ns), 3.0,
		open_read_a, 0.0, ext_rb.x, ext_rb.y, ext_rb.z]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1); _barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _topology_adj_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_topology_adj, 0)
	_topology_pc_bytes = PackedFloat32Array([float(N), float(ml_ns), float(topo_words), 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, maxi(int(ceil(float(ml_ns * topo_words) / 64.0)), 1), 1, 1); _barrier(cl)
	_topology_pc_bytes = PackedFloat32Array([float(N), float(ml_ns), float(topo_words), 1.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1); _barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _topology_csr_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_topology_csr, 0)
	_topology_pc_bytes = PackedFloat32Array([float(ml_ns), float(topo_words), 0.0, float(_topology_neighbor_capacity), float(next_generation), 0.0, 0.0, 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1); _barrier(cl)
	_topology_pc_bytes = PackedFloat32Array([float(ml_ns), float(topo_words), 2.0, float(_topology_neighbor_capacity), float(next_generation), 0.0, 0.0, 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1); _barrier(cl)
	_topology_pc_bytes = PackedFloat32Array([float(ml_ns), float(topo_words), 1.0, float(_topology_neighbor_capacity), float(next_generation), 0.0, 0.0, 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1); _barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _topology_optical_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_topology_optical, 0)
	_topology_pc_bytes = PackedFloat32Array([float(ml_ns), ext_rb.x, ext_rb.y, ext_rb.z, 1.0, 0.0, 0.0, 0.0]).to_byte_array()
	_rd.compute_list_set_push_constant(cl, _topology_pc_bytes, _topology_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1); _barrier(cl)
	# Arm 1 shortlist: rebuild the coherence-filtered tile-local site list
	# before the boxless hash. Sites are already in [0, 2·extent) tile space;
	# the reset and compact passes share the live count through binding 4.
	if _shortlist_pipe.is_valid() and _us_shortlist.is_valid():
		_rd.compute_list_bind_compute_pipeline(cl, _shortlist_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_shortlist, 0)
		var shortlist_floor := 0.0 if gridless_physics else SS_Q_FLOOR
		_shortlist_pc_bytes = PackedFloat32Array([float(ml_ns), shortlist_floor, 0.0]).to_byte_array()
		_rd.compute_list_set_push_constant(cl, _shortlist_pc_bytes, _shortlist_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_shortlist_pc_bytes = PackedFloat32Array([float(ml_ns), shortlist_floor, 1.0]).to_byte_array()
		_rd.compute_list_set_push_constant(cl, _shortlist_pc_bytes, _shortlist_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wgs, 1, 1)
		_rd.compute_list_add_barrier(cl)
	# Boxless site hash: bucket the just-built shortlist in the same list.
	# Hash PC coordinates are explicit: per-axis cell widths come from
	# 2·extent/H, and origin=(0,0,0) because _ml_sites are tile-local
	# [0,2·extent). This remains correct when the render window is translated.
	if _hash_pipe.is_valid() and _us_hash.is_valid():
		_hash_pc_bytes = PackedFloat32Array([ext_rb.x, ext_rb.y, ext_rb.z,
			float(HASH_H), float(ml_ns), 0.0, 0.0, 0.0, 0.0]).to_byte_array()
		_hash_pc_bytes.encode_float(0, ext_rb.x)
		_hash_pc_bytes.encode_float(4, ext_rb.y)
		_hash_pc_bytes.encode_float(8, ext_rb.z)
		_hash_pc_bytes.encode_float(12, float(HASH_H))
		_hash_pc_bytes.encode_float(16, float(ml_ns))
		_hash_pc_bytes.encode_float(20, 0.0)
		_hash_pc_bytes.encode_float(24, 0.0)
		_hash_pc_bytes.encode_float(28, 0.0)
		_hash_pc_bytes.encode_float(32, 0.0)  # mode: reset
		_rd.compute_list_bind_compute_pipeline(cl, _hash_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_hash, 0)
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		var hcells := HASH_H * HASH_H * HASH_H
		_rd.compute_list_dispatch(cl, maxi(int(ceil(float(hcells) / 64.0)), 1), 1, 1)
		_rd.compute_list_add_barrier(cl)
		_hash_pc_bytes.encode_float(32, 1.0)  # mode: histogram
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wgs, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_hash_pc_bytes.encode_float(32, 2.0)  # mode: exclusive prefix
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_hash_pc_bytes.encode_float(32, 3.0)  # mode: scatter
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wgs, 1, 1)
		_rd.compute_list_add_barrier(cl)
	if owns_list:
		_rd.compute_list_end()
		_finish_standalone_list()
	if topology_chain_valid:
		_topology_generation = next_generation
		_topology_site_count = ml_ns
		_topology_ready = true
		_topology_required_neighbors = -1
		_topology_overflow = -1
		_mesh_rebuild_pending = false
		_meshless_query_ready = query_chain_valid
	else:
		_topology_ready = false
		_mesh_rebuild_pending = false
		_meshless_query_ready = false
# worker's local RD are gone from the engine path. The tree worker survives
# for the verify scenes + the sim's inline arm.

## Cadence gate (the sim's _tree_local_cadence semantics). True when THIS
## job is a tree-cadence job (residue 1 mod tree_cadence).
func _tree_job_due() -> bool:
	if not meshless_mode or not meshless_gravity or not _ml_ready:
		return false
	if _ml_tree_nsrc <= 0:
		return false
	_tree_job_counter += 1
	return not (_tree_cadence > 1 and _tree_job_counter % _tree_cadence != 1)


## Append the tree build+walk dispatches to the CURRENT compute list cl.
## Reads the live meshless buffers + _pos_buf; writes _tree_grad. The PC
## values (bmin/bhalf adaptive root, eps2, tnm) come from the host-side
## site mirror (_ml_sites_cpu — no readback).
func _tree_run_in_list(cl: int) -> void:
	if not _us_tree_bld.is_valid() or not _us_tree_walk.is_valid():
		return
	var S := _ml_tree_nsrc
	var Np: int = N_particles
	var ext := _extents()
	# ADAPTIVE TREE ROOT (perf-decomp 2026-08-15, overhaul migration): the
	# root cube from the tracked structure's bounding box (the CPU site
	# mirror) instead of the fixed box origin.
	# Gated on the tracked window's ACTUAL RE-FIT state, not the enable
	# flag: OFF (default) = the legacy box cube, bit-identical; AND a flag
	# ON with the tracked geometry no-oping (the sim ships box_scale 1.0 /
	# a zero window origin for a filling structure) ALSO keeps the box
	# cube, so the tree force is bit-identical to the closed box in the
	# compatibility regime (gate-c: the flag-only gate changed the root
	# half → the tree-arm pos max-diff 121.9 over 600 steps). The
	# structure-rooted cube engages only after the geometry actually
	# re-fits (the sim's envelope tracker re-fit — box_scale != 1.0 — or a
	# moved window origin).
	var bmin := Vector3.INF
	var bmax := -Vector3.INF
	var root_offset := (-ext + _window_center) if gridless_physics else Vector3.ZERO
	for si in range(S):
		var site_pos := Vector3(
			_ml_sites_cpu[si * 4], _ml_sites_cpu[si * 4 + 1], _ml_sites_cpu[si * 4 + 2]) + root_offset
		bmin.x = minf(bmin.x, site_pos.x); bmin.y = minf(bmin.y, site_pos.y); bmin.z = minf(bmin.z, site_pos.z)
		bmax.x = maxf(bmax.x, site_pos.x); bmax.y = maxf(bmax.y, site_pos.y); bmax.z = maxf(bmax.z, site_pos.z)
	var box_half: float = maxf(ext.x, maxf(ext.y, maxf(ext.z, ext.z))) * 1.000001
	var window_refit: bool = _home_window and (box_scale != 1.0 \
			or _window_center != Vector3.ZERO)
	if not window_refit:
		bmin = -Vector3.ONE * box_half
		bmax = Vector3.ONE * box_half
	elif bmin.x <= -1.0e30 or bmin.x == INF or not (bmin.x == bmin.x):
		bmin = -Vector3.ONE * box_half
		bmax = Vector3.ONE * box_half
	var bhalf: float = 0.5 * maxf(bmax.x - bmin.x, maxf(bmax.y - bmin.y, bmax.z - bmin.z)) * 1.000001 + 1e-6
	var eps2: float = ML_TREE_EPS2_FRAC * ML_TREE_EPS2_FRAC * _extent_min() * _extent_min()
	var tnm: int = ML_TREE_NODE_MAX_MULT * S + 64
	var bpc := PackedFloat32Array()
	bpc.resize(19)
	bpc[0] = float(S)
	bpc[1] = bmin.x; bpc[2] = bmin.y; bpc[3] = bmin.z
	bpc[4] = bhalf
	bpc[5] = eps2
	bpc[6] = PHI
	bpc[7] = PHI_6
	bpc[8] = float(ML_TREE_LEAF_CAP)
	bpc[9] = float(ML_TREE_MAX_LEVELS)
	bpc[14] = float(grid_N)
	bpc[15] = ext.x; bpc[16] = ext.y; bpc[17] = ext.z
	bpc[18] = -ML_TREE_FIELD_FLOOR if gridless_physics else ML_TREE_FIELD_FLOOR
	var gpc := PackedFloat32Array()
	gpc.resize(8)
	gpc[0] = float(Np)
	gpc[1] = ML_TREE_THETA
	gpc[2] = eps2
	gpc[3] = 1.0
	gpc[4] = float(tnm)
	# Arm 2 (coherence-adaptive θ): q_cent (running field mean q), α, toggle.
	gpc[5] = _q_mean
	gpc[6] = coherence_theta_alpha
	gpc[7] = 1.0 if coherence_theta else 0.0
	var pg := int(ceil(float(S) / 64.0))
	var pall := int(ceil(float(tnm) / 64.0))
	# Mode 9 CTR_RESET + mode 10 ROOT_SEED: the on-GPU counter/root seeding
	# (replaces the worker's per-job host buffer_update seeds).
	bpc[10] = 9.0
	_rd.compute_list_bind_compute_pipeline(cl, _tree_bld_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_tree_bld, 0)
	_rd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	bpc[10] = 10.0
	_rd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# gather (mode 7) + bitonic (1) + BFS split (5/8) + moments (6) — the
	# worker's verbatim sequence, in this list on the live buffers.
	bpc[10] = 7.0
	_rd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_rd.compute_list_dispatch(cl, pg, 1, 1)
	_rd.compute_list_add_barrier(cl)
	var k := 2
	while k <= S:
		var j := k >> 1
		while j >= 1:
			bpc[10] = 1.0
			bpc[11] = float(k)
			bpc[12] = float(j)
			bpc[13] = 1.0
			_rd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
			_rd.compute_list_dispatch(cl, pg, 1, 1)
			_rd.compute_list_add_barrier(cl)
			j = j >> 1
		k = k << 1
	_rd.compute_list_add_barrier(cl)
	for _d in range(ML_TREE_MAX_LEVELS):
		bpc[10] = 5.0
		_rd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
		_rd.compute_list_dispatch(cl, pall, 1, 1)
		_rd.compute_list_add_barrier(cl)
		bpc[10] = 8.0
		_rd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
	bpc[10] = 6.0
	_rd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_rd.compute_list_dispatch(cl, pall, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# walk — one thread per particle (reads _pos_buf live), writes _tree_grad
	_rd.compute_list_bind_compute_pipeline(cl, _tree_walk_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_tree_walk, 0)
	_rd.compute_list_set_push_constant(cl, gpc.to_byte_array(), gpc.size() * 4)
	_rd.compute_list_dispatch(cl, int(ceil(float(Np) / 64.0)), 1, 1)
	_rd.compute_list_add_barrier(cl)   # walk's _tree_grad writes → the step chain's reads


# ═══════════════════════════════════════════════════════════════════════
# The per-step chain (ported verbatim — every constant, PC layout and
# dispatch order preserved)
# ═══════════════════════════════════════════════════════════════════════

func _site_mass_dispatches(cl: int) -> void:
	if not gridless_physics or not _site_mass_pipe.is_valid() or not _us_site_mass.is_valid():
		return
	var ns := maxi(_ml_tree_nsrc, 1)
	var sg := maxi(ceili(float(ns) / 64.0), 1)
	var pg := maxi(ceili(float(N_particles) / 64.0), 1)
	var ext := _extents()
	_site_mass_pc_bytes.encode_float(4, float(N_particles))
	_site_mass_pc_bytes.encode_float(8, float(ns))
	_site_mass_pc_bytes.encode_float(12, 16777216.0)
	_site_mass_pc_bytes.encode_float(16, ext.x)
	_site_mass_pc_bytes.encode_float(20, ext.y)
	_site_mass_pc_bytes.encode_float(24, ext.z)
	_site_mass_pc_bytes.encode_float(28, _window_center.x)
	_site_mass_pc_bytes.encode_float(32, _window_center.y)
	_site_mass_pc_bytes.encode_float(36, _window_center.z)
	_site_mass_pc_bytes.encode_float(40, float(HASH_H))
	_site_mass_pc_bytes.encode_float(44, 1.0) # open-world: reject, never wrap, out-of-window particles
	_site_mass_pc_bytes.encode_float(0, 0.0)
	_rd.compute_list_bind_compute_pipeline(cl, _site_mass_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_site_mass, 0)
	_rd.compute_list_set_push_constant(cl, _site_mass_pc_bytes, _site_mass_pc_bytes.size())
	_rd.compute_list_dispatch(cl, sg, 1, 1)
	_barrier(cl)
	if N_particles > 0:
		_site_mass_pc_bytes.encode_float(0, 1.0)
		_rd.compute_list_set_push_constant(cl, _site_mass_pc_bytes, _site_mass_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
		_barrier(cl)
	_site_mass_pc_bytes.encode_float(0, 2.0)
	_rd.compute_list_set_push_constant(cl, _site_mass_pc_bytes, _site_mass_pc_bytes.size())
	_rd.compute_list_dispatch(cl, sg, 1, 1)
	_barrier(cl)


func _site_physics_dispatch(cl: int, dispatch_mode: float) -> void:
	if not gridless_physics or not _site_physics_pipe.is_valid() or not _us_site_physics.is_valid():
		return
	var ns := maxi(_ml_tree_nsrc, 1)
	var sg := maxi(ceili(float(ns) / 64.0), 1)
	var ext := _extents()
	# The site operator's characteristic spacing comes from the physical
	# volume represented by one site, never from the legacy raster resolution.
	var site_cell_volume := maxf(8.0 * ext.x * ext.y * ext.z / float(ns), 1.0e-12)
	var site_spacing := pow(site_cell_volume, 1.0 / 3.0)
	_site_physics_pc_bytes.encode_float(0, dispatch_mode)
	_site_physics_pc_bytes.encode_float(4, float(ns))
	_site_physics_pc_bytes.encode_float(8, dt)
	_site_physics_pc_bytes.encode_float(12, PHI)
	_site_physics_pc_bytes.encode_float(16, site_spacing * site_spacing)
	_site_physics_pc_bytes.encode_float(20, ML_OM2)
	_site_physics_pc_bytes.encode_float(24, source_strength)
	_site_physics_pc_bytes.encode_float(28, ML_RHO_FLOOR)
	_site_physics_pc_bytes.encode_float(32, 0.0) # field momentum is unclipped; nbody owns force clamps
	_site_physics_pc_bytes.encode_float(36, winding_coupling)
	_site_physics_pc_bytes.encode_float(40, _time)
	_site_physics_pc_bytes.encode_float(44, ext.x)
	_site_physics_pc_bytes.encode_float(48, ext.y)
	_site_physics_pc_bytes.encode_float(52, ext.z)
	# Site mass is aggregate mass, so the site-volume conversion keeps the
	# legacy 0.001-per-cell source normalization without importing grid_N.
	_site_physics_pc_bytes.encode_float(56, 0.001 * site_cell_volume)
	_site_physics_pc_bytes.encode_float(60, float(_topology_generation))
	_rd.compute_list_bind_compute_pipeline(cl, _site_physics_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_site_physics, 0)
	_rd.compute_list_set_push_constant(cl, _site_physics_pc_bytes, _site_physics_pc_bytes.size())
	_rd.compute_list_dispatch(cl, sg, 1, 1)
	_barrier(cl)


func _site_nbody_dispatch(cl: int, pass_mode: float) -> void:
	if not gridless_physics or not _site_nbody_pipe.is_valid() or not _us_site_nbody_0.is_valid():
		return
	var pg := maxi(ceili(float(N_particles) / 256.0), 1)
	_site_nbody_pc_bytes.encode_float(0, float(_ml_tree_nsrc))
	_site_nbody_pc_bytes.encode_float(4, dt)
	_site_nbody_pc_bytes.encode_float(8, _time)
	_site_nbody_pc_bytes.encode_float(12, PHI)
	_site_nbody_pc_bytes.encode_float(16, xi)
	_site_nbody_pc_bytes.encode_float(20, softening * softening)
	_site_nbody_pc_bytes.encode_float(24, float(N_particles))
	_site_nbody_pc_bytes.encode_float(28, float(mode))
	_site_nbody_pc_bytes.encode_float(32, source_strength)
	_site_nbody_pc_bytes.encode_float(36, float(num_clusters))
	_site_nbody_pc_bytes.encode_float(40, 5.0)
	_site_nbody_pc_bytes.encode_float(44, pass_mode)
	_site_nbody_pc_bytes.encode_float(48, realsim_drag)
	_site_nbody_pc_bytes.encode_float(52, realsim_viscosity)
	_site_nbody_pc_bytes.encode_float(56, realsim_friction)
	_rd.compute_list_bind_compute_pipeline(cl, _site_nbody_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_site_nbody_0, 0)
	_rd.compute_list_bind_uniform_set(cl, _us_site_nbody_1, 1)
	_rd.compute_list_bind_uniform_set(cl, _us_site_nbody_2, 2)
	_rd.compute_list_set_push_constant(cl, _site_nbody_pc_bytes, _site_nbody_pc_bytes.size())
	_rd.compute_list_dispatch(cl, pg, 1, 1)
	_barrier(cl)


func _site_step_dispatches(cl: int) -> void:
	_time += dt
	_step_count += 1
	_cond_step_counter += 1
	_site_mass_dispatches(cl)
	_site_physics_dispatch(cl, 0.0)
	if not freeze_field:
		_site_physics_dispatch(cl, 1.0)
		_site_physics_dispatch(cl, 3.0)
		_site_physics_dispatch(cl, 2.0)
	else:
		_site_physics_dispatch(cl, 2.0)
	if _cond_step_counter >= 100:
		_cond_step_counter = 0
	if _cond_step_counter == 0 and black_holes_enabled \
			and _site_cond_pipe.is_valid() and _us_site_cond_0.is_valid():
		_site_cond_pc_bytes.encode_float(0, float(_ml_tree_nsrc))
		_site_cond_pc_bytes.encode_float(4, qi_condensation_threshold)
		_rd.compute_list_bind_compute_pipeline(cl, _site_cond_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_site_cond_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_site_cond_1, 1)
		var cond_groups := maxi(ceili(float(_ml_tree_nsrc) / 64.0), 1)
		for cond_mode in range(3):
			_site_cond_pc_bytes.encode_float(8, float(cond_mode))
			_site_cond_pc_bytes.encode_float(12, 0.0)
			_rd.compute_list_set_push_constant(cl, _site_cond_pc_bytes, _site_cond_pc_bytes.size())
			_rd.compute_list_dispatch(cl, cond_groups if cond_mode < 2 else 1, 1, 1)
			_barrier(cl)
	if black_holes_enabled and _site_bh_int_pipe.is_valid() and _us_site_bh_int_0.is_valid():
		_site_bh_int_pc_bytes.encode_float(0, float(_ml_tree_nsrc))
		_site_bh_int_pc_bytes.encode_float(4, dt)
		_site_bh_int_pc_bytes.encode_float(8, bh_acc_rate)
		_site_bh_int_pc_bytes.encode_float(12, bh_max_age)
		_rd.compute_list_bind_compute_pipeline(cl, _site_bh_int_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_site_bh_int_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_site_bh_int_1, 1)
		_rd.compute_list_set_push_constant(cl, _site_bh_int_pc_bytes, _site_bh_int_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_barrier(cl)
	if _bh_acc_pipe.is_valid() and bh_accretion and black_holes_enabled:
		_bh_acc_pc_bytes.encode_float(0, float(grid_N))
		_bh_acc_pc_bytes.encode_float(4, float(N_particles))
		_bh_acc_pc_bytes.encode_float(8, bh_accretion_radius)
		_bh_acc_pc_bytes.encode_float(12, 0.0)
		_rd.compute_list_bind_compute_pipeline(cl, _bh_acc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_bh_acc_0, 0)
		_rd.compute_list_set_push_constant(cl, _bh_acc_pc_bytes, _bh_acc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, maxi(ceili(float(N_particles) / 64.0), 1), 1, 1)
		_barrier(cl)
	if _grav_warmup and N_particles > 0:
		_grav_warmup = false
		_site_nbody_dispatch(cl, 2.0)
	_site_nbody_dispatch(cl, 0.0)
	if N_particles > 0 and _tree_mc_pipe.is_valid() and _us_tree_mc.is_valid():
		var pg64 := maxi(ceili(float(N_particles) / 64.0), 1)
		_tree_mc_pc_bytes.encode_float(0, float(N_particles))
		_tree_mc_pc_bytes.encode_float(4, 2.0)
		_rd.compute_list_bind_compute_pipeline(cl, _tree_mc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree_mc, 0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_tree_mc_pc_bytes.encode_float(4, 0.0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg64, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_tree_mc_pc_bytes.encode_float(4, 1.0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg64, 1, 1)
		_rd.compute_list_add_barrier(cl)


func _step_dispatches(cl: int) -> void:
	if gridless_physics:
		_site_step_dispatches(cl)
		return
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

	# Two-fluid PC (dedicated 64 B): shared 11 fields + 3 per-axis extents
	# + pass_sel (float 14) + omega2 (float 15)
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
	_two_fluid_pc_bytes.encode_float(60, 20.0)  # omega2 = ω₀² (the two-fluid resonance; default 20.0 — bit-identical to the pre-PC hardcode)

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
	# Movable home-window: off = −c (the shader maps [c−ext, c+ext] →
	# [0, N]; at c = 0 it is exactly the legacy 0.0, bit-identical).
	_md_pc_bytes.encode_float(20, -_window_center.x)
	_md_pc_bytes.encode_float(24, -_window_center.y)
	_md_pc_bytes.encode_float(28, -_window_center.z)
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
			_md_pc_bytes.encode_float(20, ext_step.x / float(grid_N) - _window_center.x)
			_md_pc_bytes.encode_float(24, ext_step.y / float(grid_N) - _window_center.y)
			_md_pc_bytes.encode_float(28, ext_step.z / float(grid_N) - _window_center.z)
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

	# ── 3.1. Tree MOMENTUM CONSERVATION (tree mode only) ─────────────
	# The tree arm's per-particle (π/ρ) prefactor breaks action–reaction
	# (Σm·a ≠ 0); the cloud gains a net self-impulse and drifts off the
	# window (the "all vanish" measured at the owner's scale). Clear →
	# reduce (Σm·a) → barrier → subtract the mass-weighted mean, all in-list
	# (cassi_tree_momcon.glsl). Newton-3rd-law correction — DERIVED, not
	# fitted. The momcon shader is local_size 64 (independent of `pg`).
	if (meshless_mode and meshless_gravity) and _tree_mc_pipe.is_valid() \
			and N_particles > 0 and _us_tree_mc.is_valid():
		var pg64 := ceili(float(N_particles) / 64.0)
		# clear the 16-B accumulator
		_tree_mc_pc_bytes.encode_float(0, float(N_particles))
		_tree_mc_pc_bytes.encode_float(4, 2.0)   # op = clear
		_rd.compute_list_bind_compute_pipeline(cl, _tree_mc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree_mc, 0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		# reduce Σ(m·a)
		_tree_mc_pc_bytes.encode_float(4, 0.0)   # op = reduce
		_rd.compute_list_bind_compute_pipeline(cl, _tree_mc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree_mc, 0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg64, 1, 1)
		_rd.compute_list_add_barrier(cl)
		# subtract the mass-weighted mean (Σm·a → 0)
		_tree_mc_pc_bytes.encode_float(4, 1.0)   # op = subtract
		_rd.compute_list_bind_compute_pipeline(cl, _tree_mc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree_mc, 0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg64, 1, 1)
		_rd.compute_list_add_barrier(cl)


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


## Record one complete coarse long-range solve before a batch's fine steps.
## The coarse density has its own fixed-point accumulator because the live
## mass-deposit and Poisson shaders require binding 2/3, respectively.
func _dispatch_cascade(cl: int) -> void:
	if not cascade_level or _cascade_nc <= 0:
		return
	if not _cf_grad_pipe.is_valid() or not _us_cf_grad_0.is_valid() \
			or not _us_poisson_c.is_valid() or not _us_mass_dep_c.is_valid():
		return
	var n: int = _cascade_nc
	var ext_p: Vector3 = _extents()
	var fft_groups_y: int = maxi(n * n / 256, 1)
	var pg: int = ceili(float(N_particles) / 256.0) if N_particles > 0 else 1

	# Coarse clear: rho, fixed-point digits, and telemetry.
	_poisson_pc_bytes.encode_float(0, float(n))
	_poisson_pc_bytes.encode_float(4, 0.0)
	_poisson_pc_bytes.encode_float(8, 0.0)
	_poisson_pc_bytes.encode_float(12, 3.0)
	_poisson_pc_bytes.encode_float(16, ext_p.x)
	_poisson_pc_bytes.encode_float(20, ext_p.y)
	_poisson_pc_bytes.encode_float(24, ext_p.z)
	_rd.compute_list_bind_compute_pipeline(cl, _poisson_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_poisson_c, 0)
	_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
	_rd.compute_list_dispatch(cl, n, n / 2, 1)
	_barrier(cl)

	# The same TSC deposit as the fine level, with N_c and the full physical
	# box. No density rescale belongs here; the volume factor is applied only
	# when the coarse gradient is blended into the fine force.
	_md_pc_bytes.encode_float(0, float(n))
	_md_pc_bytes.encode_float(4, float(N_particles))
	_md_pc_bytes.encode_float(8, ext_p.x)
	_md_pc_bytes.encode_float(12, ext_p.y)
	_md_pc_bytes.encode_float(16, ext_p.z)
	_md_pc_bytes.encode_float(20, -_window_center.x)
	_md_pc_bytes.encode_float(24, -_window_center.y)
	_md_pc_bytes.encode_float(28, -_window_center.z)
	if N_particles > 0:
		_md_pc_bytes.encode_float(32, 0.0)
		_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_c, 0)
		_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
	_barrier(cl)

	# Fixed-point digits → coarse float density.
	_md_pc_bytes.encode_float(32, 1.0)
	_rd.compute_list_bind_compute_pipeline(cl, _mass_deposit_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_mass_dep_c, 0)
	_rd.compute_list_set_push_constant(cl, _md_pc_bytes, _md_pc_bytes.size())
	_rd.compute_list_dispatch(cl, n, n, 1)
	_barrier(cl)

	# Coarse periodic Poisson solve, using the same physical half-extents and
	# Stockham schedule as the fine solve but N_f = N_c.
	_rd.compute_list_bind_compute_pipeline(cl, _poisson_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_poisson_c, 0)
	_poisson_pc_bytes.encode_float(0, float(n))
	_poisson_pc_bytes.encode_float(4, 0.0)
	_poisson_pc_bytes.encode_float(8, 0.0)
	_poisson_pc_bytes.encode_float(12, 4.0)
	_poisson_pc_bytes.encode_float(16, ext_p.x)
	_poisson_pc_bytes.encode_float(20, ext_p.y)
	_poisson_pc_bytes.encode_float(24, ext_p.z)
	_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
	_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)
	_barrier(cl)
	for axis in [1, 2]:
		_poisson_pc_bytes.encode_float(4, float(axis))
		_poisson_pc_bytes.encode_float(8, 0.0)
		_poisson_pc_bytes.encode_float(12, 1.0)
		_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
		_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)
		_barrier(cl)
	_poisson_pc_bytes.encode_float(4, 2.0)
	_poisson_pc_bytes.encode_float(8, 1.0)
	_poisson_pc_bytes.encode_float(12, 5.0)
	_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
	_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)
	_barrier(cl)
	for axis in [1, 0]:
		_poisson_pc_bytes.encode_float(4, float(axis))
		_poisson_pc_bytes.encode_float(8, 1.0)
		_poisson_pc_bytes.encode_float(12, 1.0)
		_rd.compute_list_set_push_constant(cl, _poisson_pc_bytes, _poisson_pc_bytes.size())
		_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)
		_barrier(cl)

	# Coarse ∇(g·Φ) in world units: h_i = 2·extent_i / N_c.
	_cf_grad_pc_bytes.encode_float(0, float(n))
	_cf_grad_pc_bytes.encode_float(4, float(grid_N))
	_cf_grad_pc_bytes.encode_float(8, ext_p.x)
	_cf_grad_pc_bytes.encode_float(12, ext_p.y)
	_cf_grad_pc_bytes.encode_float(16, ext_p.z)
	_cf_grad_pc_bytes.encode_float(20, PHI)
	_cf_grad_pc_bytes.encode_float(24, xi)
	_cf_grad_pc_bytes.encode_float(28, 0.0)
	_rd.compute_list_bind_compute_pipeline(cl, _cf_grad_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cf_grad_0, 0)
	_rd.compute_list_set_push_constant(cl, _cf_grad_pc_bytes, _cf_grad_pc_bytes.size())
	_rd.compute_list_dispatch(cl, n, fft_groups_y, 1)
	_barrier(cl)
	_cascade_ran += 1

# ═══════════════════════════════════════════════════════════════════════
# Cassi particle merge (compute/cassi_particle_merge.glsl) — the engine-side
# port. Runs on the LOCAL-RD worker AFTER each run_steps batch, where
# submit()+sync() per cycle makes the host CPU prefix-sum readbacks legal
# (the global RD cannot submit — see merge_wiring_notes.md §2).
# NOTE: keep the merge-cycle logic in _run_merge_pass in sync with the twin
# in cassi_sim.gd (same fold→zero-cc→count→scan→fill→best→hop batched chain,
# same per-cycle in-list cc zero). The two intentionally differ only in the
# sync style (engine: explicit submit+sync; sim: readback self-stall).
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
	# F1: cc is re-zeroed ON-GPU per cycle (mode 7 at the top of the cycle
	# batch, before every count) — the pre-loop host cc zero was redundant with
	# the batched mode-7 zero and is gone (mc still needs the pre-loop zero).
	_zero_merge_bytes(_merge_mc_buf, MERGE_MAX_CYCLES)
	var cl0 := _rd.compute_list_begin()
	_merge_bind_dispatch(cl0, 0.0)   # reset: alive=1, mass=pos.w, mom/cen=m p/m v
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	# STEP 1 (perf-decomp 2026-08-15): GPU any-candidate early-out — ONE
	# dispatch (mode 8) sets cc[0] iff ANY alive mass>0 particle sits at
	# q_coh > q_threshold; ONE 4 B readback decides. On 0: this pass CANNOT
	# merge (q_sel(mid) > φ⁻² with qord ≤ 1 requires q_coh(mid) > φ⁻², so the
	# per-particle q gate is a necessary condition) — skip the whole
	# fold/count/scan/fill/best/hop chain AND the per-cycle count readbacks,
	# i.e. the ~40-dispatch burst that starved the shared three-RD GPU on
	# near-empty passes (the measured TDR trigger; backtraces landed in
	# _merge_read_counts). cc[0] is borrowed: reset zeroed it, pass_zerocc
	# clears it before the first count, and nothing else reads it here.
	# Skipping a pass with a false-negative flag only DELAYS a merge (pos/vel
	# are untouched — reset wrote only the merge scratch), never corrupts.
	var cla := _rd.compute_list_begin()
	_merge_bind_dispatch(cla, 8.0)
	_rd.compute_list_end()
	_rd.submit(); _rd.sync()
	if int(_rd.buffer_get_data(_merge_cc_buf, 0, 4).decode_u32(0)) == 0:
		return 0
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
## redesign + the batched-merge cycle slot). Deduped via CassiMergeCommon so
## the sim twin cannot drift (the F1-class divergence guard).
func _merge_pc_values() -> PackedFloat32Array:
	return CassiMergeCommon.merge_pc_values(_merge_pc_dict())


## The merge PC inputs as a Dictionary (shared helper's key set).
func _merge_pc_dict() -> Dictionary:
	var ebox := _extents()
	var r_m: float = _extent_min() / float(maxi(grid_N, 1))   # ½·h₀
	return {
		"n_particles": float(N_particles),
		"phi": PHI, "phi_inv2": PHI_INV2,
		"r_m": r_m, "extent": ebox, "grid_n": float(grid_N),
		"hash_nx": _merge_hash_nx, "hash_ny": _merge_hash_ny, "hash_nz": _merge_hash_nz,
		"cell_wx": _merge_cell_wx, "cell_wy": _merge_cell_wy, "cell_wz": _merge_cell_wz,
		"g_n": _bh_init_bytes.decode_float(28),   # G_N (bh[1].w) — single source of truth
		"xi": xi, "dt": dt,
		"subsonic": merge_subsonic, "virial": merge_virial, "order": merge_sel_gate,
		"boxless": _ml_ready and boxless_field and particle_merge,   # gated: boxless mesh live AND merge on → site-direct read (merge_boxless_prereg.md)
		"n_sites": _ml_sites_cpu.size() / 4,                         # Voronoi site count (nearest-site read guard)
	}


## Bind the merge pipeline/set/PC and dispatch one pass mode into the open
## list `cl`. F8: the PC is ENCODED INTO the pre-sized `_merge_pc_bytes` member
## (26 floats = 104 B) — never reassigned — so dispatches stay hitch-free.
## The caller adds barriers between consecutive in-list passes and
## submit+sync across lists.
func _merge_bind_dispatch(cl: int, pass_mode: float, cyc_slot := 0) -> void:
	var pf := _merge_pc_values()
	pf[15] = pass_mode
	pf[23] = float(cyc_slot)
	for i in range(26):
		_merge_pc_bytes.encode_float(i * 4, pf[i])
	_rd.compute_list_bind_compute_pipeline(cl, _merge_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_merge_0, 0)
	_rd.compute_list_set_push_constant(cl, _merge_pc_bytes, _merge_pc_bytes.size())
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
