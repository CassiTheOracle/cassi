extends Node3D
## Cassi Universe Simulator — core orchestration.
##
## Manages the two-fluid PDE field grid, N-body particles, black hole
## lensing, and visualization — all running in Godot compute shaders.
##

const PHI: float = 1.618033988749895
const PHI_INV3: float = (PHI - 1.0) / (PHI + 1.0)   # φ⁻³ = attractor π/ρ ≈ 0.236068
const PHI_INV2: float = 0.3819660112501051  # φ⁻² — q decoherence threshold
const PHI_6: float = PHI * PHI * PHI * PHI * PHI * PHI  # φ⁶ ≈ 17.94427191
const PI_CLAMP_MAX: float = 0.72  # (π/ρ) upper clamp (stability; telemetry counts hits)

# ═══════════════════════════════════════════════════════════════════════
# Exports
## Master run/pause switch for the physics loop.
@export var playing: bool = true              # simulation running

## Field grid resolution per dimension (power of two, 64-256); non-powers round up with a warning.
@export var grid_N: int = 64              # field grid resolution (per dim)
## N-body particle count (rendered as a starfield/cluster; raises GPU cost).
@export var N_particles: int = 2500000      # N-body particle count
## Physics timestep in sim seconds per step; a rendered frame runs up to max_steps_per_frame steps.
@export var dt: float = 0.001             # simulation timestep
## Cassi coupling constant, xi = φ⁶ = 17.94427191; the river law's chord coefficient is xi − 1.
@export var xi: float = 17.94427191  # φ⁶ — Cassi Qi coupling (exact: φ⁶ = φ⁵ + φ⁴)
## Gravity softening length; used as epsilon² = softening² in the force kernels.
@export var softening: float = 0.1        # gravity softening length
## Rendered quad size of each particle (world units); keep ≤ 0.5 for the star-cloud look.
@export var particle_size: float = 0.3   # rendered particle size
## Scale radius of the initial cluster (Plummer scale a / Gaussian sigma / uniform sphere radius, per the IC profile).
@export var cluster_radius: float = 50.0   # initial cluster size
## Number of initial clusters (placed on a ring/Fibonacci sphere).
@export var num_clusters: int = 1           # number of galaxy clusters
## Distance of cluster centers from the origin; a single cluster centers at (separation, 0, 0).
@export var cluster_separation: float = 60.0 # separation between cluster centers
## Bulk velocity added toward the origin (cluster-merger demo).
@export var merger_speed: float = 2.0       # bulk velocity toward merger point
## Extra field injection from the deposited mass (0 = off).
@export var source_strength: float = 0.0  # PIC mass deposit drives field (set >0 for extra injection)
## Qi level above which the condensation scan nucleates a black hole record (only when black_holes_enabled).
@export var qi_condensation_threshold: float = 0.5  # Qi density above this → BH nucleation
## Black hole mass growth per step from the field.
@export var bh_acc_rate: float = 0.01                # mass growth per step from field
## Black hole record lifetime in steps (0 = immortal).
@export var bh_max_age: float = 0.0                  # 0 = immortal
# Suppress the throttled CPU readbacks (occupancy/perf/q-tel/p[0]/inst-debug)
# that stall the global RD every ~0.5 s — the stutter source; useful
# interactively AND for recording. Physics and rendering are untouched.
## Off the throttled CPU readbacks (occupancy/perf/q diagnostics) that stall the GPU every ~0.5 s — removes the stutter; physics and rendering unchanged.
@export var suppress_readbacks: bool = false
# Enables the σ-regularized BH point-source sector in EVERY gravity mode:
# the softened Newtonian point-source force (gravity_at), the condensation
# scan (every 100 steps), and the BH-integrate pass (every step). Default
# off — particles-only; flip on for point sources. The shader reads the
# live toggle from bh[3].x (float 48 of the per-frame header upload).
## Master toggle for the black hole point-source sector in any gravity mode (softened Newtonian pull + condensation + BH-integrate passes). Default off = particles only.
@export var black_holes_enabled: bool = false

# Gravity law selector (river law = the derived formula, default):
#   0 = RIVER — a = −G_N·(π/ρ)·∇(g·Φ),  g = 1+(φ⁶−1)q,  ∇²Φ = ρ_mass (spectral)
#   1 = HEURISTIC — legacy G_N·π/ρ·∇q_s arm, kept for A/B comparison only
#   2 = PLUMMER — grid-free softened analytic enclosed-mass force (cluster
#       buffer centers/masses); a visual/reference arm, NOT the law.
#   3 = RIVER-SELF — the river law ONLY (particle interactions only):
#       the BH sector follows the global black_holes_enabled toggle
#       (default off — particles only). Everything else about mode 0 is
#       preserved bit-for-bit — mass deposit, Poisson FFT chain, PDE,
#       ∇(g·Φ) gradient pass, cached-acc KDK, telemetry.
#   4 = REALSIM — the river law EXACTLY as mode 0 (bit-for-bit); the BH
#       sector follows the global toggle (black_holes_enabled, default
#       off), PLUS three per-particle dissipative terms representing
#       motion through the two-fluid (EY/EI) medium:
#         drag      a = −γ·(ρ_local/ρ_ref)·v        γ = realsim_drag
#         viscosity a = −ν·(v − v_field(p))         ν = realsim_viscosity
#         friction  a = −min(μ·|a_g|, |v|/dt)·v̂     μ = realsim_friction
#       (formulas + defaults in cassi_nbody_gravity.glsl header; with all
#       three coefficients at 0, mode 4 is bit-identical to mode 0).
#       Mode 4 keeps the full Poisson chain and gradient pass like 0/3.
# Only modes 1/2 skip the Poisson FFT chain and the river gradient pass
# (neither consumes Φ/∇(g·Φ)); modes 3/4 keep them. Mass deposit + the
# two-fluid PDE always run.
## 0 = River (the law), 1 = Heuristic (legacy A/B arm), 2 = Plummer (grid-free analytic reference), 3 = River self (river law only; BH follows the global toggle), 4 = RealSim (river law + BH per toggle + drag/viscosity/friction).
@export_enum("River", "Heuristic", "Plummer reference", "River self", "RealSim") var gravity_mode: int = 0

# ── RealSim dissipation coefficients (gravity_mode == 4 only) ──────────
# Units: γ and ν are rates (1/time) — at reference density γ's e-folding
# time is 1/γ; μ is a dimensionless fraction of |a_g|. ρ_ref = φ⁻³ =
# 0.236068 (the attractor). See the shader header for the formulas.
## γ — background drag rate (1/time at reference density ρ_ref = φ⁻³): a = −γ(ρ/ρ_ref)·v.
@export var realsim_drag: float = 0.5        # γ — background drag rate at ρ_ref (1/time)
## ν — shear-coupling rate (1/time): a = −ν(v − v_field), relaxation toward the medium's own velocity.
@export var realsim_viscosity: float = 0.3   # ν — shear-coupling rate to the medium (1/time)
## μ — Coulomb floor (dimensionless fraction of |a_g|): a = −min(μ·|a_g|, |v|/dt)·v̂, never reverses.
@export var realsim_friction: float = 0.01   # μ — Coulomb floor, fraction of |a_g| (dimensionless)

# ── River-law resolution calibration (opt-in; OFF keeps the exact G_N = 1
# verification contract). When ON, G_N is recomputed after the particle
# init from the ACTUAL deposited mean mass so the grid force matches the
# IC circular-velocity convention (G = 1, M = per-cluster count):
#   G_N = 4π / (π_ref · g_ref · h³ · m_mean),  h = 2·extent/N,
#   g_ref = 1 + (ξ−1)·q_ref,  m_mean = Σ deposited mass / N_particles.
# Written to the BH header slot bh[1].w (shared by the river arm, the BH
# point-source term and the Plummer reference arm — they all scale with
# the same explicit G_N).
## Recompute G_N after init so the grid force matches the IC circular-velocity convention at every resolution (G_eff = 1).
@export var river_calibrate_gn: bool = false
## Reference π/ρ for the calibration (default φ⁻³ attractor).
@export var river_pi_ref: float = PHI_INV3   # reference π/ρ (φ⁻³ = attractor)
## Reference q for the calibration → g_ref = 1 + (xi − 1)·q_ref.
@export var river_q_ref: float = 0.0         # reference q → g_ref = 1+(ξ−1)·q_ref
# ── Attractor field init (opt-in; OFF keeps the legacy flat-noise field
# for verification compatibility). EY = φ·EI + tiny controlled noise →
# π/ρ = (EY−EI)/(EY+EI) ≈ φ⁻³ > 0 everywhere — the river law has NO
# force-free (clamp-to-0) holes. The law's formula itself is untouched.
## Seed the field on the attractor (EY = φ·EI + noise) so π/ρ is positive everywhere — no force-free holes (river has full force coverage).
@export var field_attractor_init: bool = false
# ── Truncated-Plummer IC radius (fraction of the box half-extent):
# every initial particle lies inside r_max = fr·extent − |center|_∞ per
# cluster (a safe spherical radius inside the periodic cube). The Plummer
# profile is preserved CONDITIONAL on the truncation via a rejection-free
# inverse-CDF draw u ∈ (0.001, u_max], u_max = (x²/(1+x²))^(3/2) with
# x = r_max/a — no coordinate clamping, no shell artifacts.
## Fraction of the box half-extent used as the per-cluster safe radius r_max = fr·extent − |center|_∞.
@export var initial_radius_fraction: float = 0.9
# ── Initial-condition profile selector ──
#   0 = BOUNDED PLUMMER (default) — the truncated inverse-CDF draw below.
#   1 = GAUSSIAN BALL — positions ~ N(0, σ) with σ = cluster_radius,
#       truncated to the per-cluster safe radius r_max by REJECTION
#       (exact conditional distribution; redraws until r ≤ r_max; no
#       clamping/shell artifact). Velocities from the Gaussian enclosed
#       mass M(<r) = M_tot·[erf(z) − (2/√π)·z·e^(−z²)], z = r/(√2·σ).
#   2 = UNIFORM SPHERE — radius a = cluster_radius, r = a·u^(1/3) with
#       u drawn in (0, u_trunc], u_trunc = min(1, (r_max/a)³) — a
#       REJECTION-FREE truncated draw (u ≤ (r_max/a)³ ⟺ r ≤ r_max).
#       Velocities from M(<r) = M_tot·min(1, (r/a)³).
# All profiles reuse the cluster/bulk/Salpeter machinery below and keep
# every particle inside the per-cluster safe radius (out_of_box = 0).
## 0 = Bounded Plummer (default), 1 = Gaussian ball (sigma = cluster_radius), 2 = Uniform sphere (radius = cluster_radius); all truncated to the safe radius, out-of-box = 0.
@export_enum("Bounded Plummer", "Gaussian ball", "Uniform sphere") var initial_condition: int = 0

# ── Box geometry (theory-accurate grid layout — GRID_LAYOUT.md) ────────
# Per-axis box half-extents: extent_i = aspect_i · 1.5 · cluster_radius
# (N³ cells unchanged; h_i = 2·extent_i/N). Cube (1,1,1) = the legacy box
# (the existing verify battery runs this). Theory preset (φ, 1, φ²) maps
# x = Yang (extended), y = Yin (contracted), z = String/P∥ (flow): the
# box-mode lattice becomes incommensurate — no axis-locked box modes, so
# the straight-line lock at box scale is removed. Init-time: reinit() to
# apply (extents are encoded in the bh header and the PCs at setup).
## Per-axis box aspect (extent_i = aspect_i·1.5·cluster_radius). Cube (1,1,1) default; theory preset (φ,1,φ²) — see GRID_LAYOUT.md.
@export var box_aspect: Vector3 = Vector3(1, 1, 1)

## Display mode: 0 = Particles, 1 = Field, 2 = Black Hole, 3 = Cosmology.
@export_enum("Particles", "Field", "Black Hole", "Cosmology") var mode: int = 0

# ═══════════════════════════════════════════════════════════════════════
# Internal state
# ═══════════════════════════════════════════════════════════════════════

var _rd: RenderingDevice = null

# — field grid buffers (SET 0) —
var _field_ey: RID; var _field_ei: RID
var _field_q: RID;  var _field_vel: RID

# — Poisson solver (SET 0 of cassi_poisson.glsl) —
var _fft_buf: RID      # vec2 per cell — FFT workspace; real part = Φ after solve
var _tel_buf: RID      # gravity telemetry: [pi_hi, pi_lo, rho_guard, q_min, q_max, pi_min, pi_max, samples]
# — Cell-centered ∇(g·Φ) field (SET 0 binding 7 of cassi_nbody_gravity.glsl) —
var _grad_buf: RID     # vec4 per cell — gradient pass output, river-arm input

# — particle buffers (SET 1) —
var _pos_buf: RID; var _vel_buf: RID; var _acc_buf: RID

# — auxiliary buffers (SET 2) —
var _cluster_buf: RID
var _bh_buf: RID
var _bh_lens_buf: RID  # BH lensing params (4 vec4s, visual only — NOT the 36-vec4 sim header)
var _mass_density_buf: RID

# — shaders and pipelines —
var _two_fluid_shader: RID;  var _two_fluid_pipe: RID
var _nbody_shader: RID;      var _nbody_pipe: RID
var _poisson_shader: RID;    var _poisson_pipe: RID
var _field_render_shader: RID; var _field_render_pipe: RID
var _bh_lensing_shader: RID;  var _bh_lensing_pipe: RID
var _mass_deposit_shader: RID; var _mass_deposit_pipe: RID
var _shaders_ready: bool = false
var _setup_retry_counter: int = 0
var _us_two_0: RID; var _us_two_1: RID; var _us_two_2: RID
var _us_mass_dep_0: RID
var _us_nbody_0: RID; var _us_nbody_1: RID; var _us_nbody_2: RID
var _us_poisson_0: RID
var _us_fr_0: RID; var _us_fr_2: RID  # field-render sets (cached, no per-frame alloc)
var _us_bh_lens_2: RID  # BH-lensing set (cached; was created per frame)
# — Instancer pipeline —
var _instancer_shader: RID; var _instancer_pipe: RID
var _cond_shader: RID; var _cond_pipe: RID; var _us_cond_0: RID; var _us_cond_1: RID
var _bh_int_shader: RID; var _bh_int_pipe: RID; var _us_bh_int_0: RID; var _us_bh_int_1: RID
var _cond_step_counter: int = 0
var _us_inst_0: RID = RID()

# — pre-allocated push-constant byte buffers (hitch-free: no per-step allocs) —
var _pc_bytes: PackedByteArray        # shared 11-float PC (all physics shaders)
# N-body PC is 15 floats (60 B): the nbody shader carries the
# gradient-pass selector (pass_mode) as its 12th field plus the three
# RealSim dissipation coefficients (13th-15th). The other shaders'
# structs are 11 floats (44 B) — Godot hard-errors on push-constant size
# mismatch, so the nbody shader gets its OWN pre-allocated 60 B buffer
# (the dedicated-PC precedent) instead of growing the shared one.
var _nbody_pc_bytes: PackedByteArray  # nbody PC (15 floats: 11 shared + pass_mode + 3 RealSim)
# Two-fluid dedicated PC (14 floats: the shared 11 + the 3 per-axis
# extents) — the dedicated-PC precedent: field_render/instancer/bh_lensing
# share _pc_bytes (11 floats) and Godot hard-errors on push-constant size
# mismatch, so the two-fluid's anisotropic-stencil extents get their own.
var _two_fluid_pc_bytes: PackedByteArray  # two-fluid PC (14 floats: 11 shared + extent_x/y/z)
var _md_pc_bytes: PackedByteArray     # mass deposit PC (5 floats: N, particle_N, extent_x/y/z)
var _bh_int_pc_bytes: PackedByteArray # BH integrate PC (4 floats)
var _cond_pc_bytes: PackedByteArray   # condensation PC (4 floats)
var _bh_init_bytes: PackedByteArray   # BH header init (16 floats)
var _tel_reset_bytes: PackedByteArray # gravity telemetry reset (8 floats)
var _poisson_pc_bytes: PackedByteArray  # poisson PC (7 floats: N, axis, dir, mode, extent_x/y/z)
# NOTE: global RD — no manual submit/sync anywhere (illegal on the main
# instance); readbacks self-stall via buffer_get_data.

# — MultiMesh rendering —
# GPU-DIRECT: the instancer compute shader writes straight into the
# renderer's OWN multimesh instance buffer (RenderingServer
# .multimesh_get_buffer_rd_rid) — zero per-frame readbacks/CPU uploads.
# (`MultiMesh.buffer` is PackedFloat32Array-typed in Godot 4.7; there is no
# RID-injection property, so the reverse direction is used: compute binds
# the renderer's buffer RID.)
# Visual readbacks (field slice, BH lensing) stay wall-time capped at
# ~15 Hz; full-q diagnostics ~3 Hz (each readback stalls the global RD, so
# they are throttled hard).
const RB_HZ: float = 15.0
const DIAG_HZ: float = 3.0
var _mm_rd_rid: RID = RID()              # the multimesh's RD instance buffer
var _last_field_rb_ms: int = 0
var _last_bh_rb_ms: int = 0
var _last_diag_ms: int = 0
var _last_p0_rb_ms: int = 0              # wall-time gate for the p[0] debug print
var _inst_debug_done: bool = false       # one-time inst[0..2] print
var _mmi: MultiMeshInstance3D; var _mm: MultiMesh

# — timing —
var _step_count: int = 0
var _time: float = 0.0
var _step_timer: float = 0.0
# Fixed-step catch-up cap: a 60 Hz frame at dt=0.001 needs exactly 16 steps;
# a larger backlog is dropped (and counted) instead of spiraling unbounded.
# Exported so the recorder scene can raise it for time-lapse coverage per
# video second (default 16 = unchanged behavior).
## Physics catch-up cap per rendered frame (recorder raises it for time-lapse).
@export var max_steps_per_frame: int = 16
var _dropped_steps: int = 0

# — diagnostics —
var _q_mean: float = 0.0
var _q_min: float = 0.0
var _q_max: float = 0.0
var _pi_min: float = 0.0
var _pi_max: float = 0.0
var _pi_sat_hi_frac: float = 0.0   # fraction of π/ρ samples pinned at 0.72
var _pi_sat_lo_frac: float = 0.0   # fraction of π/ρ samples clamped to 0 (Yin excess)
var _rho_guard_hits: int = 0
var _poisson_residual: float = -1.0  # FD-Laplacian residual of the Φ solve (reported)
var _poisson_residual_done: bool = false
var _eps_mean: float = 0.0
var _hubble: float = 0.0
var _scale_factor: float = 1.0
var _gn_eff: float = 1.0        # effective river G after calibration (= G_N·π_ref·g_ref·h³·m_mean/4π)
var _grav_warmup: bool = false  # one-shot acc-cache warm-up before the first KDK step

# — Initial-condition diagnostics (filled by _init_particles) —
var _init_max_radius: float = 0.0
var _init_max_component: float = 0.0
var _init_out_of_box: int = 0
var _init_retained_fraction: float = 0.0   # min over clusters of u(r_max) — CDF retained by truncation
var _total_init_mass: float = 0.0          # Σ Salpeter masses of the initial particles

# — Perf accumulation (interactive runs; verify scenes keep playing=false) —
var _perf_phys_us: int = 0
var _perf_steps: int = 0
var _perf_frames: int = 0
var _perf_last_ms: int = 0
var _last_occ_ms: int = 0


# — Display textures for visualization modes —
var field_display_texture: Texture2D = null
signal field_texture_updated(tex: Texture2D)
var bh_display_texture: Texture2D = null
signal bh_texture_updated(tex: Texture2D)
# ═══════════════════════════════════════════════════════════════════════
# Lifecycle
# ═══════════════════════════════════════════════════════════════════════

func _ready() -> void:
	if not _setup_rendering_device():
		push_error("[CassiSim] Aborting startup: no RenderingDevice (headless/dummy renderer?)")
		return
	_setup_buffers()
	_setup_multimesh()  # BEFORE _setup_shaders: the instancer uniform set
	_setup_shaders()    # binds the multimesh's RD buffer, which must exist
	_init_field()
	_init_particles()
	_apply_gravity_calibration()
	_grav_warmup = true  # fill the acc cache with a fresh force before step 1
	print("[CassiSim] Universe ready — grid=%d³ particles=%d xi=%.5f (φ⁶=%.5f)" % [grid_N, N_particles, xi, PHI_6])


func _process(delta: float) -> void:
	if not _rd:
		return

	# First-run import race: on a fresh cache the .glsl imports may not have
	# finished when _ready ran — retry until every shader compiles.
	if not _shaders_ready:
		_setup_retry_counter += 1
		if _setup_retry_counter % 30 == 0:
			_free_shaders()
			_setup_shaders()

	if playing and _shaders_ready:
		_step_timer += delta
		var n_steps := 0
		while _step_timer >= dt and n_steps < max_steps_per_frame:
			_step_timer -= dt
			n_steps += 1
		if _step_timer >= dt:
			# Backlog beyond the cap: drop the excess whole steps (counted,
			# not silent) instead of letting _step_timer grow unbounded.
			var excess := int(_step_timer / dt)
			_dropped_steps += excess
			_step_timer -= float(excess) * dt
		if n_steps > 0:
			var t0 := Time.get_ticks_usec()
			_run_physics_steps(n_steps)
			_perf_phys_us += int(Time.get_ticks_usec() - t0)
			_perf_steps += n_steps
	_perf_frames += 1

	_render_frame()


# Run n physics steps in ONE compute list per frame.
# (Global RD contract: NO submit/sync — illegal on the main instance. The
# list is executed by the renderer's frame machinery at frame end; any
# buffer_get_data readback internally flushes and stalls all frames, which
# is the only sync we need.)
func _run_physics_steps(n_steps: int) -> void:
	# BH header (count/G_N/extent/toggle) — constant across the frame's
	# steps; buffer_update must run BEFORE compute_list_begin.
	# Re-encode the live BH toggle (bh[3].x, float 48) every frame so a UI
	# flip takes effect next frame with NO reinit — the shader gates the
	# BH force term and the host gates the BH passes on the same value.
	_bh_init_bytes.encode_float(48, 1.0 if black_holes_enabled else 0.0)
	_rd.buffer_update(_bh_buf, 0, _bh_init_bytes.size(), _bh_init_bytes)
	var cl = _rd.compute_list_begin()
	for _s in range(n_steps):
		_step_dispatches(cl)
	_rd.compute_list_end()


# No-op on the global RD: readbacks self-stall (kept so verify scripts and
# external callers can call it unconditionally).
func _ensure_synced() -> void:
	pass


# Full memory barrier inside an open compute list. Consecutive dispatches
# have EXECUTION ordering but no implicit MEMORY visibility — without this,
# a later dispatch can read stale data written by an earlier one (races
# were observed in the deposit→poisson and FFT chains). The barrier makes
# the visibility explicit.
func _barrier(cl: int) -> void:
	_rd.compute_list_add_barrier(cl)


func _exit_tree() -> void:
	# Children (incl. the MultiMeshInstance3D holding the renderer's
	# multimesh buffer) exit BEFORE this node, so the multimesh buffer RID
	# referenced by _us_inst_0 is already gone when the sets are freed —
	# releasing a set that referenced a freed buffer is safe on the global
	# RD (sets are opaque). Order: sets → buffers → shaders.
	_free_uniform_sets()  # sets reference buffers/shaders — release first
	_free_buffers()
	_free_shaders()


# ═══════════════════════════════════════════════════════════════════════
# Rendering Device setup
# ═══════════════════════════════════════════════════════════════════════

func _setup_rendering_device() -> bool:
	# GLOBAL RenderingDevice (RenderingServer.get_rendering_device()) — the
	# main renderer's device. REQUIRED for the GPU-direct MultiMesh path:
	# the renderer's own multimesh instance buffer (obtained via
	# RenderingServer.multimesh_get_buffer_rd_rid) lives on this device, and
	# a local-RD compute shader cannot bind it (different Vulkan device).
	# Global-RD contract (Godot 4.7): submit()/sync() are FORBIDDEN on the
	# main instance ("Only local devices can submit and sync"); recorded
	# compute lists are executed by the renderer's frame machinery, and
	# buffer/texture_get_data internally flushes + stalls all frames.
	if RenderingServer.has_method("get_rendering_device"):
		_rd = RenderingServer.get_rendering_device()
	if _rd == null:
		push_error("[CassiSim] Failed to acquire the global RenderingDevice (headless/dummy renderer?)")
		return false
	return true


func _shader_from_file(path: String) -> RID:
	var sf = load(path) if ResourceLoader.exists(path) else null
	if sf == null:
		push_error("[CassiSim] Shader not found: " + path)
		return RID()
	var spirv = sf.get_spirv()
	if spirv == null:
		push_error("[CassiSim] SPIR-V compile failed: " + path)
		return RID()
	return _rd.shader_create_from_spirv(spirv)


func _uniform_storage(binding: int, buf: RID) -> RDUniform:
	var u = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


# Per-axis box half-extents — the single source of truth for the box
# geometry (bh[2].yzw header slots, the Poisson/mass-deposit/two-fluid
# push constants, IC truncation, occupancy and the residual report all
# derive from this). Cube default (1,1,1) = the legacy single-extent box.
func _extents() -> Vector3:
	return Vector3(box_aspect.x, box_aspect.y, box_aspect.z) * (cluster_radius * 1.5)


func _setup_buffers() -> void:
	# The spectral Poisson FFT (cassi_poisson.glsl) is a radix-2 Stockham
	# FFT: grid_N must be a power of 2 in [64, 256]. Non-power-of-2 values
	# are rounded UP to the next power of 2 (clamped at 256) and the
	# effective grid is written back to grid_N so the UI and dispatch
	# counts always agree with what the shader actually runs.
	var n2 := 64
	while n2 < grid_N:
		n2 *= 2
	if n2 > 256:
		n2 = 256
	if n2 != grid_N:
		var old_N := grid_N
		grid_N = n2
		push_warning("[CassiSim] grid_N=%d is not a power of 2 (radix-2 FFT); using %d" % [old_N, grid_N])
	var N = grid_N
	var nc = N * N * N
	var nf = nc * 4

	# SET 0 — Field grid
	_field_ey  = _rd.storage_buffer_create(nf)
	_field_ei  = _rd.storage_buffer_create(nf)
	_field_q   = _rd.storage_buffer_create(nf)
	_field_vel = _rd.storage_buffer_create(nc * 16)
	# Poisson solver: complex FFT workspace (vec2/cell) + gravity telemetry
	_fft_buf  = _rd.storage_buffer_create(nc * 8)
	_tel_buf  = _rd.storage_buffer_create(32)
	# SET 1 — Particles
	var ps = N_particles * 16
	_pos_buf = _rd.storage_buffer_create(ps)
	_vel_buf = _rd.storage_buffer_create(ps)
	_acc_buf = _rd.storage_buffer_create(ps)

	# SET 2 — BH data + sim globals
	# 36 vec4s = 576 bytes: 4-vec4 header (count/G_N/extents/reserved) + 15
	# BH records × 2 vec4s (indices 4..33). Was 512 bytes — too small: the
	# shaders read/write up to bh[33] (slot 14), which was out of bounds.
	# bh[2] = (cluster_radius, extent_x, extent_y, extent_z) — the per-axis
	# box half-extents (GRID_LAYOUT.md); the nbody samplers/gradient pass
	# and the BH integrate/condensation shaders read bh[2].yzw directly.
	# At the cube aspect this equals the legacy single extent.
	_bh_buf = _rd.storage_buffer_create(576)
	var ext_hdr := _extents()
	var bh_init_f = PackedFloat32Array([
		0.0, 0.0, 0.0, float(N_particles),
		0.0, 0.0, 0.0, 1.0,
		cluster_radius, ext_hdr.x, ext_hdr.y, ext_hdr.z,
		0.0, 0.0, 0.0, 0.0,
	])
	# Zero the FULL 576-byte buffer (header at the front): storage buffers
	# are NOT zero-initialized on allocator reuse, and the nbody shader
	# reads bh[4..] (BH records) in every gravity mode. Stale memory there
	# produced a phantom point mass (~2×N_particles) at the origin in the
	# verify scene — deterministic setup, then the condensation/BH-
	# integrate passes own the records at runtime.
	var bh_full = PackedFloat32Array()
	bh_full.resize(576 / 4)
	for i in range(16):
		bh_full[i] = bh_init_f[i]
	_bh_init_bytes = bh_full.to_byte_array()
	_rd.buffer_update(_bh_buf, 0, _bh_init_bytes.size(), _bh_init_bytes)
	# BH lensing params — dedicated 4-vec4 buffer. The lensing shader
	# declares exactly 4 vec4s; never bind the 36-vec4 sim BH header to it.
	# Params are filled by _update_bh_lens_params() in _make_render_textures.
	_bh_lens_buf = _rd.storage_buffer_create(64)
	# Cluster center positions + masses (for multi-cluster gravity)
	_cluster_buf = _rd.storage_buffer_create(20 * 4 * 4)
	# Mass density grid (float per cell — float atomicAdd deposit, see
	# cassi_mass_deposit.glsl)
	_mass_density_buf = _rd.storage_buffer_create(nc * 4)
	# Cell-centered ∇(g·Φ) field (vec4 per cell — river-arm gradient,
	# rebuilt every step by the gradient pass between poisson and nbody)
	_grad_buf = _rd.storage_buffer_create(nc * 16)
	# NO sim-owned multimesh buffer: the instancer writes the renderer's own
	# multimesh instance buffer (see _setup_multimesh) — GPU-direct.
	_make_render_textures()

	# Pre-allocate push-constant byte buffers (hitch-free pattern)
	_pc_bytes = PackedByteArray(); _pc_bytes.resize(11 * 4)
	_nbody_pc_bytes = PackedByteArray(); _nbody_pc_bytes.resize(15 * 4)
	_md_pc_bytes = PackedByteArray(); _md_pc_bytes.resize(4 * 4)
	_bh_int_pc_bytes = PackedByteArray(); _bh_int_pc_bytes.resize(4 * 4)
	_cond_pc_bytes = PackedByteArray(); _cond_pc_bytes.resize(4 * 4)
	_poisson_pc_bytes = PackedByteArray(); _poisson_pc_bytes.resize(5 * 4)
	# NOTE: all poisson dispatches (clear/load/kspace/FFT) are 2D (N, N, 1) —
	# cells modes use gid = x + y·N·256 (see cassi_poisson.glsl), the FFT
	# uses row = workgroup.x + workgroup.y·N. A 1D (N³/256, 1, 1) dispatch
	# caps at 65535 groups on some devices and the naive x + y·N gid formula
	# covers only N² + 255N cells — the N=256 dispatch landmine.
	# Telemetry reset (kept for reference; the per-step reset runs on the GPU
	# in the poisson clear pass so chained steps stay independent)
	_tel_reset_bytes = PackedFloat32Array([0.0, 0.0, 0.0, INF, 0.0, INF, 0.0, 0.0]).to_byte_array()

func _free_buffers() -> void:
	for rid in [_field_ey, _field_ei, _field_q, _field_vel,
				_pos_buf, _vel_buf, _acc_buf, _bh_buf, _bh_lens_buf,
				_mass_density_buf, _cluster_buf, _fft_buf, _tel_buf,
				_grad_buf,
				_field_render_tex, _bh_lensing_tex]:
		if rid.is_valid(): _rd.free_rid(rid)
	_field_render_tex = RID()
	_bh_lensing_tex = RID()

func _free_uniform_sets() -> void:
	# Uniform sets reference buffers/shaders/textures — release them BEFORE
	# any of those are freed (reinit, shader retry, exit). Overwriting a
	# live set RID without freeing it leaks the set on the local RD.
	if _rd == null: return
	for rid in [_us_two_0, _us_two_1, _us_two_2, _us_mass_dep_0,
				_us_nbody_0, _us_nbody_1, _us_nbody_2, _us_poisson_0,
				_us_fr_0, _us_fr_2, _us_cond_0, _us_cond_1,
				_us_bh_int_0, _us_bh_int_1, _us_inst_0, _us_bh_lens_2]:
		if rid.is_valid(): _rd.free_rid(rid)
	_us_two_0 = RID(); _us_two_1 = RID(); _us_two_2 = RID()
	_us_mass_dep_0 = RID()
	_us_nbody_0 = RID(); _us_nbody_1 = RID(); _us_nbody_2 = RID()
	_us_poisson_0 = RID()
	_us_fr_0 = RID(); _us_fr_2 = RID()
	_us_cond_0 = RID(); _us_cond_1 = RID()
	_us_bh_int_0 = RID(); _us_bh_int_1 = RID()
	_us_inst_0 = RID()
	_us_bh_lens_2 = RID()

func _free_shaders() -> void:
	_free_uniform_sets()  # sets hold shader references; release before the shaders
	# Pipelines before their shaders (freeing a pipeline after its shader
	# reports "Attempted to free invalid ID" on the local RD at exit).
	for rid in [_two_fluid_pipe, _nbody_pipe, _poisson_pipe,
				_field_render_pipe, _bh_lensing_pipe,
				_instancer_pipe, _mass_deposit_pipe,
				_cond_pipe, _bh_int_pipe,
				_two_fluid_shader, _nbody_shader, _poisson_shader,
				_field_render_shader, _bh_lensing_shader,
				_instancer_shader, _mass_deposit_shader,
				_cond_shader, _bh_int_shader]:
		if rid.is_valid(): _rd.free_rid(rid)

func _setup_shaders() -> void:
	# Two-fluid PDE solver
	_two_fluid_shader = _shader_from_file("res://compute/cassi_two_fluid.glsl")
	if _two_fluid_shader.is_valid():
		_two_fluid_pipe = _rd.compute_pipeline_create(_two_fluid_shader)
		print("[CassiSim] Two-fluid PDE pipeline ready")

	# N-body gravity
	_nbody_shader = _shader_from_file("res://compute/cassi_nbody_gravity.glsl")
	if _nbody_shader.is_valid():
		_nbody_pipe = _rd.compute_pipeline_create(_nbody_shader)
		print("[CassiSim] N-body gravity pipeline ready")

	# Spectral Poisson solver (∇²Φ = ρ_mass; river-law potential)
	_poisson_shader = _shader_from_file("res://compute/cassi_poisson.glsl")
	if _poisson_shader.is_valid():
		_poisson_pipe = _rd.compute_pipeline_create(_poisson_shader)
		print("[CassiSim] Poisson pipeline ready")

	# Field rendering
	_field_render_shader = _shader_from_file("res://compute/cassi_field_render.glsl")
	if _field_render_shader.is_valid():
		_field_render_pipe = _rd.compute_pipeline_create(_field_render_shader)
		print("[CassiSim] Field render pipeline ready")

	# BH lensing
	_bh_lensing_shader = _shader_from_file("res://compute/cassi_bh_lensing.glsl")
	if _bh_lensing_shader.is_valid():
		_bh_lensing_pipe = _rd.compute_pipeline_create(_bh_lensing_shader)
		print("[CassiSim] BH lensing pipeline ready")

	# Particle instancer
	_instancer_shader = _shader_from_file("res://compute/cassi_instancer.glsl")
	if _instancer_shader.is_valid():
		_instancer_pipe = _rd.compute_pipeline_create(_instancer_shader)
		print("[CassiSim] Instancer pipeline ready")

	# Mass deposit (PIC) — scatters particle masses into field grid
	_mass_deposit_shader = _shader_from_file("res://compute/cassi_mass_deposit.glsl")
	if _mass_deposit_shader.is_valid():
		_mass_deposit_pipe = _rd.compute_pipeline_create(_mass_deposit_shader)
		print("[CassiSim] Mass deposit pipeline ready")

	# Condensation scanner (Qi peak → BH nucleation)
	_cond_shader = _shader_from_file("res://compute/cassi_condensation.glsl")
	if _cond_shader.is_valid():
		_cond_pipe = _rd.compute_pipeline_create(_cond_shader)
		print("[CassiSim] Condensation scanner pipeline ready")

	# BH integration (position + mass update each step)
	_bh_int_shader = _shader_from_file("res://compute/cassi_bh_integrate.glsl")
	if _bh_int_shader.is_valid():
		_bh_int_pipe = _rd.compute_pipeline_create(_bh_int_shader)
		print("[CassiSim] BH integration pipeline ready")

	_cache_uniform_sets()
	_shaders_ready = (
		_two_fluid_shader.is_valid() and _nbody_shader.is_valid()
		and _poisson_shader.is_valid() and _mass_deposit_shader.is_valid()
		and _instancer_shader.is_valid() and _cond_shader.is_valid()
		and _bh_int_shader.is_valid() and _field_render_shader.is_valid()
		and _bh_lensing_shader.is_valid())


func _cache_uniform_sets() -> void:
	# NOTE: must only run with all cached sets already released — callers
	# (reinit, shader-retry, startup) free them via _free_uniform_sets()
	# first. Recreating a live set would leak its RID. Texture-only rebuilds
	# go through _cache_render_texture_sets() instead.
	# Two-fluid PDE declares ONLY set 0 (bindings 0-4) — no sets 1/2
	_us_two_0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		_uniform_storage(4, _mass_density_buf),
	], _two_fluid_shader, 0)

	_us_nbody_0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		_uniform_storage(4, _mass_density_buf),
		_uniform_storage(5, _fft_buf),
		_uniform_storage(6, _tel_buf),
		_uniform_storage(7, _grad_buf),
	], _nbody_shader, 0)
	_us_nbody_1 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf), _uniform_storage(1, _vel_buf),
		_uniform_storage(2, _acc_buf),
	], _nbody_shader, 1)
	# Poisson solver (set 0: FFT workspace + mass density + telemetry)
	if _poisson_shader.is_valid():
		_us_poisson_0 = _rd.uniform_set_create([
			_uniform_storage(0, _fft_buf),
			_uniform_storage(1, _mass_density_buf),
			_uniform_storage(2, _tel_buf),
		], _poisson_shader, 0)
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
	_us_nbody_2 = _rd.uniform_set_create([
		_uniform_storage(0, _bh_buf),
		_uniform_storage(1, _cluster_buf),  # Plummer reference arm (mode 2)
	], _nbody_shader, 2)

	# Field render (cached sets — was rebuilt every frame in _dispatch_compute)
	# NOTE: the field-render shader declares only set 0 (fields) and set 2
	# (image) — NO set 1; creating one errors "Desired set (1) not used".
	if _field_render_shader.is_valid():
		_us_fr_0 = _rd.uniform_set_create([
			_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
			_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		], _field_render_shader, 0)
		if _field_render_tex.is_valid():
			_us_fr_2 = _rd.uniform_set_create([
				_get_set2_image_uniform(_field_render_shader, 0, _field_render_tex),
			], _field_render_shader, 2)

	# BH lensing (set 2 only: screen image + dedicated 4-vec4 params)
	if _bh_lensing_shader.is_valid() and _bh_lensing_tex.is_valid() and _bh_lens_buf.is_valid():
		_us_bh_lens_2 = _rd.uniform_set_create([
			_get_set2_image_uniform(_bh_lensing_shader, 0, _bh_lensing_tex),
			_get_set2_buffer_uniform(_bh_lensing_shader, 1, _bh_lens_buf),
		], _bh_lensing_shader, 2)

	# Instancer — writes DIRECTLY into the renderer's multimesh instance
	# buffer (GPU-direct; no readback). The buffer must be valid here:
	# _setup_multimesh runs before _setup_shaders (see _ready).
	if not _mm_rd_rid.is_valid():
		push_error("[CassiSim] Instancer set skipped: multimesh RD buffer unavailable")
	else:
		_us_inst_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _mm_rd_rid),
		], _instancer_shader, 0)
		print("[CassiSim] Instancer uniform set cached (GPU-direct multimesh buffer)")

	# Mass deposit
	_us_mass_dep_0 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf),
		_uniform_storage(1, _mass_density_buf),
	], _mass_deposit_shader, 0)
	print("[CassiSim] Mass deposit uniform set cached")

# ═══════════════════════════════════════════════════════════════════════
# Initial conditions
# ═══════════════════════════════════════════════════════════════════════

func _init_field() -> void:
	var N = grid_N
	var nc = N * N * N
	var ey = PackedFloat32Array(); ey.resize(nc)
	var ei = PackedFloat32Array(); ei.resize(nc)
	var q  = PackedFloat32Array(); q.resize(nc)
	var vel = PackedFloat32Array(); vel.resize(nc * 4)

	var half = float(N) * 0.5
	var rng = RandomNumberGenerator.new()

	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id = i + N * (j + N * k)
				var dx = (float(i) - half) / half
				var dy = (float(j) - half) / half
				var dz = (float(k) - half) / half
				var r2 = dx*dx + dy*dy + dz*dz

				if field_attractor_init:
					# Attractor init (opt-in): EI small positive with ±10%
					# variation, EY = φ·EI ± 1e-3 → π/ρ = (EY−EI)/(EY+EI)
					# ∈ [0.15, 0.31] — strictly positive, no force-free
					# (clamp-to-0) holes, mean ≈ φ⁻³. The river law's
					# formula is untouched; this only seeds the field on
					# the attractor (EY = φ·EI) instead of flat noise.
					var ei_v: float = 0.01 * (1.0 + 0.1 * rng.randf_range(-1.0, 1.0))
					var ey_v: float = PHI * ei_v + rng.randf_range(-0.001, 0.001)
					ey[id] = ey_v
					ei[id] = ei_v
					q[id] = ey_v * ey_v + ei_v * ei_v
				else:
					# Flat noise — no pre-existing structure (pure Cassi)
					ey[id] = rng.randf_range(-0.01, 0.01)
					ei[id] = rng.randf_range(-0.01, 0.01)
					q[id] = ey[id]*ey[id] + ei[id]*ei[id]
				vel[id * 4]     = 0.0
				vel[id * 4 + 1] = 0.0
				vel[id * 4 + 2] = 0.0
				vel[id * 4 + 3] = 0.0

	_rd.buffer_update(_field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_field_ei, 0, ei.size() * 4, ei.to_byte_array())
	_rd.buffer_update(_field_q,  0, q.size() * 4, q.to_byte_array())
	_rd.buffer_update(_field_vel, 0, vel.size() * 4, vel.to_byte_array())

	print("[CassiSim] Field initialized: %d³ = %d cells" % [N, nc])


func _erf_approx(x: float) -> float:
	# Abramowitz & Stegun 7.1.26 erf approximation: erf(x) =
	# 1 − (a₁t + a₂t² + a₃t³ + a₄t⁴ + a₅t⁵)·e^(−x²), t = 1/(1 + p·x),
	# p = 0.3275911, a = (0.254829592, −0.284496736, 1.421413741,
	# −1.453152027, 1.061405429); max |ε| < 1.5e-7 for x ≥ 0 (every call
	# site here has x = r/(√2·σ) ≥ 0). The Godot 4.7 GDScript API on this
	# install exposes no built-in erf() — this is the recorded replacement.
	var t: float = 1.0 / (1.0 + 0.3275911 * x)
	var poly: float = ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t
	return 1.0 - poly * exp(-x * x)


func _init_particles() -> void:
	var pos = PackedFloat32Array(); pos.resize(N_particles * 4)
	var vel = PackedFloat32Array(); vel.resize(N_particles * 4)
	var acc = PackedFloat32Array(); acc.resize(N_particles * 4)

	var rng = RandomNumberGenerator.new()
	var G = 1.0
	var eps2 = softening * softening
	var fr: float = initial_radius_fraction
	var ext_box: Vector3 = _extents()
	var extent_min: float = minf(ext_box.x, minf(ext_box.y, ext_box.z))

	# Pre-compute cluster centers and bulk velocities
	var centers = []
	var sep = cluster_separation
	var ms = merger_speed
	var nc = max(1, num_clusters)
	var bulk_vels = []
	var per_cluster = N_particles / nc
	# Truncation bounds: per cluster, r_max = fr·extent_min − |center|_∞
	# (a safe spherical radius inside the periodic box — the SHORTEST axis
	# bounds every direction, so all ICs stay in-box at any aspect),
	# shared by ALL initial-condition profiles below. The retained
	# fraction reported as
	# _init_retained_fraction is profile-specific: for the Plummer draw it
	# is u_max = (x²/(1+x²))^{3/2} with x = r_max/a (fraction of the
	# unbounded profile kept inside the truncation); Gaussian/uniform
	# compute their own analytic retained mass (see the end of this func).
	var u_max_list: Array = []
	var gauss_u_max_list: Array = []
	var r_max_list: Array = []
	var retained_min: float = INF
	for c in range(nc):
		var angle = float(c) * PI * 2.0 / float(nc)
		var cx = sep * cos(angle); var cy = 0.0; var cz = sep * sin(angle)
		if nc > 8:
			# Fibonacci sphere distribution for many clusters
			var phi = acos(1.0 - 2.0 * (float(c) + 0.5) / float(nc))
			var th = PI * (1.0 + sqrt(5.0)) * float(c)
			cx = sep * sin(phi) * cos(th)
			cy = sep * sin(phi) * sin(th)
			cz = sep * cos(phi)
		centers.append(Vector3(cx, cy, cz))
		var bv = Vector3(-cx, -cy, -cz).normalized() * ms + \
				  Vector3(-cz, 0.0, cx).normalized() * ms * 0.3
		bulk_vels.append(bv)
		var c_abs: float = maxf(absf(cx), maxf(absf(cy), absf(cz)))
		var r_max_c: float = fr * extent_min - c_abs
		if r_max_c < 0.0:
			r_max_c = 0.0  # degenerate: cluster center beyond the safe radius
		r_max_list.append(r_max_c)
		var x_max: float = r_max_c / maxf(cluster_radius, 1e-6)
		var u_hi: float = pow(x_max * x_max / (1.0 + x_max * x_max), 1.5)
		u_max_list.append(u_hi)
		# Gaussian-ball truncation CDF F(z_max) = erf(z_max) −
		# (2/√π)·z_max·e^(−z_max²), z_max = r_max/(√2·σ) — the uniform-draw
		# ceiling for the rejection-free inverse-CDF draw in the IC==1 arm.
		var z_max_c: float = r_max_c / (sqrt(2.0) * maxf(cluster_radius, 1e-6))
		var g_hi: float = _erf_approx(z_max_c) - (2.0 / sqrt(PI)) * z_max_c * exp(-z_max_c * z_max_c)
		gauss_u_max_list.append(maxf(g_hi, 0.0))
		retained_min = minf(retained_min, u_hi)

	# Upload cluster centers to GPU buffer
	var cluster_data = PackedFloat32Array()
	for c in range(nc):
		var cen = centers[c]
		cluster_data.append(cen.x); cluster_data.append(cen.y)
		cluster_data.append(cen.z); cluster_data.append(float(per_cluster))
	_rd.buffer_update(_cluster_buf, 0, cluster_data.size() * 4, cluster_data.to_byte_array())

	var max_r: float = 0.0
	var max_comp: float = 0.0
	var out_box := 0
	var total_mass: float = 0.0

	for i in range(N_particles):
		var i4 = i * 4
		var cidx = min(int(i / per_cluster), nc - 1)
		var center = centers[cidx]
		var bv = bulk_vels[cidx]

		# Salpeter IMF: dN/dM ∝ M^(-2.35), range [0.3, 30.0] M☉
		# (named salp_exp so the global exp() stays callable below — the
		# Gaussian velocity arm and the retained-fraction math use it)
		var alpha = 2.35; var salp_exp = 1.0 - alpha
		var A = pow(0.3, salp_exp); var B = pow(30.0, salp_exp)
		var m = pow(A - rng.randf() * (A - B), 1.0 / salp_exp)
		pos[i4 + 3] = m
		total_mass += m

		# ── Position draw (per initial-condition profile) ──
		var lx := 0.0; var ly := 0.0; var lz := 0.0
		var r := 0.0
		var r_max_eff: float = r_max_list[cidx]
		if initial_condition == 0:
			# Truncated Plummer distribution around cluster center —
			# REJECTION-FREE inverse CDF: draw u ∈ (0.001, max(u_max, 0.0011)]
			# with u_max = (x²/(1+x²))^{3/2} for x = r_max/a. The conditional
			# distribution of u given u ≤ u_max is uniform, so the profile is
			# preserved exactly on the truncation; r(u_max) = r_max ⇒ every
			# particle lies inside the safe radius (no clamping, no shell).
			var u_hi: float = u_max_list[cidx]
			var u = rng.randf_range(0.001, maxf(u_hi, 0.0011))
			r = cluster_radius / sqrt(pow(u, -2.0 / 3.0) - 1.0)
			var th = acos(2.0 * rng.randf() - 1.0)
			var ph = rng.randf() * PI * 2.0
			lx = r * sin(th) * cos(ph)
			ly = r * sin(th) * sin(ph)
			lz = r * cos(th)
		elif initial_condition == 1:
			# Gaussian ball — REJECTION-FREE truncated N(0, σ) draw (the
			# same exact conditional distribution as rejection sampling,
			# but O(1) per particle for ANY σ vs r_max ratio): the radial
			# CDF of a 3D Gaussian truncated at r_max is
			#   F(z) = erf(z) − (2/√π)·z·e^(−z²),  z = r/(√2·σ),
			# so a uniform u ∈ (0, F(z_max)] inverted by bisection (F
			# strictly increasing on [0, ∞)) gives r ≤ r_max directly —
			# no rejection retries, no attempt cap, no degenerate retry
			# storm when r_max ≪ σ (the old sampler burned ~660 attempts
			# per particle at r_max/σ = 0.15 → ~17 min at 2.5M particles).
			# Radius and direction are independent for a spherically
			# symmetric Gaussian; direction = the same uniform th/ph draw
			# as the Plummer arm.
			var z_max: float = r_max_eff / (sqrt(2.0) * maxf(cluster_radius, 1e-6))
			var u: float = rng.randf() * maxf(gauss_u_max_list[cidx], 1e-30)
			var z_lo := 0.0
			var z_hi: float = z_max
			for _b in range(24):
				var z_m: float = 0.5 * (z_lo + z_hi)
				var f_m: float = _erf_approx(z_m) - (2.0 / sqrt(PI)) * z_m * exp(-z_m * z_m)
				if f_m < u:
					z_lo = z_m
				else:
					z_hi = z_m
			var z: float = 0.5 * (z_lo + z_hi)
			r = sqrt(2.0) * maxf(cluster_radius, 1e-6) * z
			var th = acos(2.0 * rng.randf() - 1.0)
			var ph = rng.randf() * PI * 2.0
			lx = r * sin(th) * cos(ph)
			ly = r * sin(th) * sin(ph)
			lz = r * cos(th)
		else:
			# Uniform sphere — REJECTION-FREE truncated draw: r = a·u^(1/3)
			# with u drawn in (0, u_trunc], u_trunc = min(1, (r_max/a)³);
			# u ≤ u_trunc ⟺ r ≤ r_max, so every particle lands inside the
			# safe radius. Direction via the same th/ph draw as Plummer.
			var a_s: float = maxf(cluster_radius, 1e-6)
			var u_trunc: float = minf(1.0, pow(r_max_eff / a_s, 3.0))
			var u = rng.randf() * u_trunc
			r = a_s * pow(u, 1.0 / 3.0)
			var th = acos(2.0 * rng.randf() - 1.0)
			var ph = rng.randf() * PI * 2.0
			lx = r * sin(th) * cos(ph)
			ly = r * sin(th) * sin(ph)
			lz = r * cos(th)
		pos[i4]     = lx + center.x
		pos[i4 + 1] = ly + center.y
		pos[i4 + 2] = lz + center.z

		var rr: float = sqrt(lx * lx + ly * ly + lz * lz)
		max_r = maxf(max_r, rr)
		var mc: float = maxf(absf(pos[i4]), maxf(absf(pos[i4 + 1]), absf(pos[i4 + 2])))
		max_comp = maxf(max_comp, mc)
		if absf(pos[i4]) > ext_box.x or absf(pos[i4 + 1]) > ext_box.y or absf(pos[i4 + 2]) > ext_box.z:
			out_box += 1

		# ── Circular velocity around cluster center + bulk ──
		# Enclosed mass M(<r) per profile, all with G = 1 and the same
		# v_circ = 0.85·sqrt(M_enc/max(r, 0.01)) convention (r softened to
		# sqrt(r²+ε²) inside the enclosed-mass formulas, as the Plummer arm
		# already does via r2p).
		var a2 = cluster_radius * cluster_radius
		var r2p = r * r + eps2
		var M_enc: float = 0.0
		if initial_condition == 0:
			# Plummer enclosed mass M(<r) = M·r³/(r²+a²)^(3/2)
			M_enc = float(per_cluster) * (r2p * r) / ((r2p + a2) * sqrt(r2p + a2))
		elif initial_condition == 1:
			# Gaussian M(<r) = M·[erf(z) − (2/√π)·z·e^(−z²)], z = r/(√2·σ),
			# r = the softened sqrt(r2p); erf via A&S 7.1.26 (_erf_approx —
			# this Godot 4.7 install has no built-in erf()).
			var z: float = sqrt(r2p) / (sqrt(2.0) * maxf(cluster_radius, 1e-6))
			M_enc = float(per_cluster) * (_erf_approx(z) - (2.0 / sqrt(PI)) * z * exp(-z * z))
		else:
			# Uniform M(<r) = M·min(1, (r/a)³) (fully enclosed at r ≥ a)
			M_enc = float(per_cluster) * minf(1.0, pow(sqrt(r2p) / maxf(cluster_radius, 1e-6), 3.0))
		var v_circ = sqrt(G * M_enc / max(r, 0.01)) * 0.85
		var nx = -ly; var ny = lx; var nz = 0.0
		var nl = sqrt(nx*nx + ny*ny + nz*nz)
		if nl > 0.001:
			nx /= nl; ny /= nl; nz /= nl
		else:
			nx = 1.0; ny = 0.0; nz = 0.0
		var pert = 0.05
		vel[i4]     = (nx + rng.randf_range(-pert, pert)) * v_circ + bv.x
		vel[i4 + 1] = (ny + rng.randf_range(-pert, pert)) * v_circ + bv.y
		vel[i4 + 2] = (nz + rng.randf_range(-pert, pert)) * v_circ + bv.z
		vel[i4 + 3] = 0.0


	# Initialize MultiMesh instance buffer with initial positions
	var init_inst = PackedFloat32Array()
	init_inst.resize(N_particles * 16)  # 16 floats per instance
	# Debug: show mass distribution of first few particles
	var mass_sample = ""
	for mi in range(min(8, N_particles)):
		mass_sample += "%.1f " % pos[mi * 4 + 3]
	print("[CassiSim] Salpeter masses (first 8): %s" % mass_sample)
	for i in range(N_particles):
		var i4 = i * 4
		var b = i * 16
		var x = pos[i4]; var y = pos[i4+1]; var z = pos[i4+2]
		var rt = sqrt(x*x + y*y + z*z + eps2)
		var t_c = 1.0 / (1.0 + 0.1 * rt)
		# Transform: 3x4 row-major (each row = [basis, origin_component])
		# Row 0 = X-axis + origin.x, Row 1 = Y-axis + origin.y, Row 2 = Z-axis + origin.z
		init_inst[b+0] = 1.0; init_inst[b+1] = 0.0; init_inst[b+2] = 0.0; init_inst[b+3] = x
		init_inst[b+4] = 0.0; init_inst[b+5] = 1.0; init_inst[b+6] = 0.0; init_inst[b+7] = y
		init_inst[b+8] = 0.0; init_inst[b+9] = 0.0; init_inst[b+10] = 1.0; init_inst[b+11] = z
		# Color: Cassi gradient
		var cr = lerp(1.0, 0.15, 1.0-t_c)
		var cg = lerp(0.8, 0.25, 1.0-t_c)
		var cb = lerp(0.3, 1.0, 1.0-t_c)
		init_inst[b+12] = cr; init_inst[b+13] = cg; init_inst[b+14] = cb; init_inst[b+15] = 0.85
	# Initial instance data → the renderer's OWN multimesh buffer (one-time
	# CPU upload at init; every subsequent frame the instancer shader writes
	# it directly). NOTE: do NOT assign _mm.buffer again later — a CPU
	# upload would overwrite the GPU-direct writes.
	_mm.buffer = init_inst
	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_rd.buffer_update(_acc_buf, 0, acc.size() * 4, acc.to_byte_array())

	_init_max_radius = max_r
	_init_max_component = max_comp
	_init_out_of_box = out_box
	# Retained fraction = analytic fraction of the UNBOUNDED profile kept
	# inside the truncation, per profile (min over clusters, like the old
	# Plummer u_max minimum):
	#   Plummer:  u_max = (x²/(1+x²))^{3/2}, x = r_max/a
	#   Gaussian: erf(z_max) − (2/√π)·z_max·e^(−z_max²), z_max = r_max/(√2·σ)
	#   Uniform:  min(1, (r_max/a)³)
	var retained: float = retained_min if retained_min < INF else 1.0
	if initial_condition == 1:
		var s2: float = sqrt(2.0) * maxf(cluster_radius, 1e-6)
		var g_min: float = INF
		for c in range(nc):
			var z_max: float = r_max_list[c] / s2
			var f: float = _erf_approx(z_max) - (2.0 / sqrt(PI)) * z_max * exp(-z_max * z_max)
			g_min = minf(g_min, f)
		retained = g_min
	elif initial_condition == 2:
		var a_s: float = maxf(cluster_radius, 1e-6)
		var u_min: float = INF
		for c in range(nc):
			var u_tr: float = minf(1.0, pow(r_max_list[c] / a_s, 3.0))
			u_min = minf(u_min, u_tr)
		retained = u_min
	_init_retained_fraction = retained
	_total_init_mass = total_mass
	if out_box > 0:
		# A cluster center beyond fr·extent_min − |center|_∞ (e.g. legacy
		# scene configs with cluster_separation ≫ the small box) leaves NO
		# in-box spherical placement — the truncation packs those particles
		# at the center (u_max = 0); the count below is the config's
		# consequence, not a truncation failure. The verify scenes
		# overwrite positions.
		push_warning("[CassiSim] IC: %d initial particles outside the box (fr=%.2f, extent_min=%.1f, aspect=%s) — a cluster center sits beyond the safe radius; config-level, not a truncation failure" % [out_box, fr, extent_min, str(box_aspect)])
	var ic_name := "Plummer" if initial_condition == 0 else ("Gaussian" if initial_condition == 1 else "Uniform")
	print("[CassiSim] IC [%s]: retained=%.4f  max_radius=%.1f  max|comp|=%.1f  out_of_box=%d (fr=%.2f, extent_min=%.1f, aspect=%s)" % [
		ic_name, _init_retained_fraction, max_r, max_comp, out_box, fr, extent_min, str(box_aspect)])
	print("[CassiSim] Particles initialized: %d (Σm=%.1f, m_mean=%.4f)" % [N_particles, total_mass, total_mass / float(max(N_particles, 1))])



# ── Resolution-aware river calibration (opt-in) ─────────────────────────
# The spectral Poisson solve's field force carries a cell-volume factor:
# for a mass concentration with mean deposited mass m_mean the river force
# on a particle is
#   |a| = G_N·(π/ρ)·g·V_cell·Σm/(4π r²),  V_cell = h_x·h_y·h_z,
#   h_i = 2·extent_i/N  (cube: V_cell = h³, h = 2·extent/N),
# while the IC circular velocities use the G = 1, M = per-cluster COUNT
# convention. Setting
#   G_N = 4π / (π_ref·g_ref·V_cell·m_mean),  g_ref = 1+(ξ−1)·q_ref,
# makes |a| = M_count/r² — the grid force and the IC convention agree at
# every resolution (the V_cell factor cancels the m_mean·M_count
# conversion).
# Written to the BH header slot bh[1].w (offset 7·4), which the river
# arm, the BH point-source term and the Plummer reference arm all read —
# one explicit shared G_N, never silently divergent.
func _apply_gravity_calibration() -> void:
	if _bh_init_bytes.size() < 32:
		return
	# Global BH toggle → bh[3].x (float 48 of the 576-B header): the shader
	# gates bh_point_gravity on it in ANY gravity mode. Encoded here so
	# _ready/reinit (and verify's _upload_bh, which uploads _bh_init_bytes
	# verbatim) always carry it.
	_bh_init_bytes.encode_float(48, 1.0 if black_holes_enabled else 0.0)
	if not river_calibrate_gn:
		_bh_init_bytes.encode_float(28, 1.0)
		_gn_eff = 1.0
		return
	var ext_box: Vector3 = _extents()
	var h: float = 2.0 * ext_box.x / float(max(grid_N, 1))
	var hy: float = 2.0 * ext_box.y / float(max(grid_N, 1))
	var hz: float = 2.0 * ext_box.z / float(max(grid_N, 1))
	var m_mean: float = _total_init_mass / float(max(N_particles, 1))
	var g_ref: float = 1.0 + (xi - 1.0) * river_q_ref
	var gn: float = 4.0 * PI / (river_pi_ref * g_ref * h * hy * hz * m_mean)
	_bh_init_bytes.encode_float(28, gn)  # bh[1].w — G_N
	_gn_eff = gn * river_pi_ref * g_ref * (h * hy * hz) * m_mean / (4.0 * PI)
	print("[CassiSim] Gravity calibration: h=(%.4f,%.4f,%.4f)  m_mean=%.4f  π/ρ_ref=%.4f  g_ref=%.4f → G_N=%.4f (G_eff=%.4f)" % [
		h, hy, hz, m_mean, river_pi_ref, g_ref, gn, _gn_eff])


# ═══════════════════════════════════════════════════════════════════════
# Physics step
# ═══════════════════════════════════════════════════════════════════════

# — Render target textures for compute shader output —
var _field_render_tex: RID = RID()
var _bh_lensing_tex: RID = RID()
var _rt_size: Vector2i = Vector2i(512, 512)


func _make_render_texture(width: int, height: int) -> RID:
	var fmt = RDTextureFormat.new()
	fmt.width = width
	fmt.height = height
	fmt.format = RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT
	fmt.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT \
				   | RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT
	var view = RDTextureView.new()
	return _rd.texture_create(fmt, view, [])


func _get_set2_image_uniform(shader: RID, binding: int, tex: RID) -> RDUniform:
	var u = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
	u.binding = binding
	u.add_id(tex)
	return u


func _get_set2_buffer_uniform(shader: RID, binding: int, buf: RID) -> RDUniform:
	var u = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = binding
	u.add_id(buf)
	return u


func _render_field_slice() -> void:
	if not _field_render_shader.is_valid(): return
	var now_ms := Time.get_ticks_msec()
	if now_ms - _last_field_rb_ms < int(1000.0 / RB_HZ): return  # ~15 Hz cap
	_last_field_rb_ms = now_ms
	if not _field_render_tex.is_valid():
		_make_render_textures()
		_cache_render_texture_sets()  # sets referencing the new texture

	# Shared PC (11 floats) — reuse the pre-allocated buffer
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
	var wg = Vector3i(ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1)

	var cl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _field_render_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_fr_0, 0)
	_rd.compute_list_bind_uniform_set(cl, _us_fr_2, 2)
	_rd.compute_list_set_push_constant(cl, _pc_bytes, _pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg.x, wg.y, wg.z)
	_rd.compute_list_end()
	# Global RD: no submit/sync; texture_get_data self-stalls (executes the
	# recorded list, then reads back).

	# Readback for UI display (15 Hz — one 512² RGBAF readback per gate)
	var fdata = _rd.texture_get_data(_field_render_tex, 0)
	if fdata.size() > 100:
		var img = Image.create_from_data(_rt_size.x, _rt_size.y, false, Image.FORMAT_RGBAF, fdata)
		if img:
			# Reuse the ImageTexture via update() when the size matches —
			# avoids allocating a new GPU texture every readback.
			if field_display_texture is ImageTexture \
					and field_display_texture.get_width() == _rt_size.x \
					and field_display_texture.get_height() == _rt_size.y:
				field_display_texture.update(img)
			else:
				field_display_texture = ImageTexture.create_from_image(img)
			field_texture_updated.emit(field_display_texture)


func _physics_step() -> void:
	# Single-step API (verify script / external callers): wraps the step
	# dispatches in its own list+submit+sync.
	_run_physics_steps(1)


func _step_dispatches(cl: int) -> void:
	_time += dt
	_step_count += 1

	# ── Pre-allocated push constants (no per-step allocations) ──────────
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

	# N-body PC (dedicated 48 B): same 11 fields + pass_mode at float 11.
	# pass_mode = 0 for the particle pass; the gradient pass (2.8) sets 1.
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
	_nbody_pc_bytes.encode_float(40, float(gravity_mode))
	_nbody_pc_bytes.encode_float(44, 0.0)  # pass_mode = 0 (particles)
	_nbody_pc_bytes.encode_float(48, realsim_drag)
	_nbody_pc_bytes.encode_float(52, realsim_viscosity)
	_nbody_pc_bytes.encode_float(56, realsim_friction)

	# Mass deposit PC: [N_f, particle_N, extent, _]
	_md_pc_bytes.encode_float(0, float(grid_N))
	_md_pc_bytes.encode_float(4, float(N_particles))
	_md_pc_bytes.encode_float(8, cluster_radius * 1.5)
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

	var wg = ceili(float(grid_N) / 4.0)
	var pg = ceili(float(N_particles) / 256.0) if N_particles > 0 else 1

	# ── 0. GPU clear (poisson mode 3): ρ = 0, telemetry reset ─────────
	# Must happen ON THE GPU per step: CPU buffer_update is illegal inside
	# an open compute list, and chained steps need a clean ρ each step.
	if _poisson_shader.is_valid():
		_poisson_pc_bytes.encode_float(0, float(grid_N))
		_poisson_pc_bytes.encode_float(4, 0.0)
		_poisson_pc_bytes.encode_float(8, 0.0)
		_poisson_pc_bytes.encode_float(12, 3.0)  # mode 3 = clear
		_poisson_pc_bytes.encode_float(16, cluster_radius * 1.5)
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

	# ── 1.5. Spectral Poisson solve: ∇²Φ = ρ_mass (Φ̂ = −ρ̂/k², k=0 nulled) ──
	# RIVER MODES ONLY (0, 3 and 4): the heuristic and Plummer-reference arms
	# consume neither Φ nor ∇(g·Φ) — skipping the 7-pass FFT chain is their
	# main step-cost win. The clear+deposit+PDE chain above still runs so
	# ρ/q remain the visual/source state (the PDE's injection reads ρ).
	if gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4:
		_dispatch_poisson(cl)
	_barrier(cl)  # deposit → PDE (rho visibility for the PDE source)

	# ── 2. Two-fluid PDE ─────────────────────────────────────────────
	if _two_fluid_shader.is_valid():
		_rd.compute_list_bind_compute_pipeline(cl, _two_fluid_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_two_0, 0)
		_rd.compute_list_set_push_constant(cl, _pc_bytes, _pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg, wg, wg)
	_barrier(cl)  # PDE → condensation

	# ── 2.5. Condensation scan (every 100 steps) ───────────────────
	# The BH sector follows the global black_holes_enabled toggle (not the
	# gravity mode): with the toggle off, no BH records are nucleated or
	# advanced in ANY mode (the buffer stays inert/zeroed).
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
	# One thread per cell; S = g·Φ at cells, central differences stored to
	# _grad_buf. Runs AFTER the Poisson solve (needs this step's Φ) and
	# BEFORE the N-body pass (which samples _grad_buf). Reads the same
	# post-PDE EY/EI the nbody pass sees. 2D cells dispatch (N, N, 1) —
	# the poisson cells convention: a 1D N³/256 dispatch caps at 65535
	# groups at N=256. RIVER MODE ONLY: the heuristic/Plummer arms never
	# sample _grad_buf, so the O(N³) pass is skipped with the FFT chain.
	# Mode 3 (river self) and mode 4 (RealSim) sample it too — kept with
	# mode 0.
	if (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) and _nbody_shader.is_valid():
		_nbody_pc_bytes.encode_float(44, 1.0)  # pass_mode = 1 (gradient)
		_rd.compute_list_bind_compute_pipeline(cl, _nbody_pipe)
		# ALL THREE sets must be bound: the pipeline rejects a dispatch with
		# any declared set missing ("Uniforms were never supplied for set
		# (1)") — the pass reads ey/ei/ph/grad (set 0) and bh extent (set 2);
		# set 1 is unused by grad_main but must still be present.
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_1, 1)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_2, 2)
		_rd.compute_list_set_push_constant(cl, _nbody_pc_bytes, _nbody_pc_bytes.size())
		_rd.compute_list_dispatch(cl, grid_N, grid_N, 1)
	_barrier(cl)  # gradient → nbody

	# ── 2.9. Acceleration warm-up (ONE-TIME, before the first KDK step) ──
	# Fills _acc_buf with the field force at the CURRENT positions with the
	# CURRENT field, so the cached-acc KDK's first half-kick is a fresh
	# evaluation — step 1 stays bit-identical to the two-evaluation KDK.
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

	# ── 3. N-body gravity ────────────────────────────────────────────
	if _nbody_shader.is_valid() and N_particles > 0:
		_nbody_pc_bytes.encode_float(44, 0.0)  # pass_mode = 0 (particles)
		_rd.compute_list_bind_compute_pipeline(cl, _nbody_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_0, 0)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_1, 1)
		_rd.compute_list_bind_uniform_set(cl, _us_nbody_2, 2)
		_rd.compute_list_set_push_constant(cl, _nbody_pc_bytes, _nbody_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
	_barrier(cl)  # nbody → instancer

	# ── 4. Instancer: GPU-only MultiMesh update ──────────────────────
	if _instancer_shader.is_valid() and N_particles > 0:
		_rd.compute_list_bind_compute_pipeline(cl, _instancer_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_inst_0, 0)
		_rd.compute_list_set_push_constant(cl, _pc_bytes, _pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
	# NOTE: the compute list is owned by the caller (_run_physics_steps);
	# end/submit/sync happen there, once per frame.

# ── One-time FD-Laplacian residual report for the Poisson solve ─────────
# Checks ∇²Φ ≈ ρ (7-point stencil) on the solved potential. The spectral
# solve inverts the CONTINUOUS Laplacian, so the residual measures the
# discretization mismatch (expected O(h²) of the stencil), not solver error.
func _report_poisson_residual() -> void:
	if not _rd or not _fft_buf.is_valid(): return
	if grid_N > 128:
		print("[CassiSim] Poisson residual report skipped: grid_N=%d > 128 (full-grid CPU triple loop too slow)" % grid_N)
		return
	_ensure_synced()
	var N = grid_N
	var phi = _rd.buffer_get_data(_fft_buf, 0, N * N * N * 8)
	var rhob = _rd.buffer_get_data(_mass_density_buf, 0, N * N * N * 4)
	if phi.size() < N * N * N * 8 or rhob.size() < N * N * N * 4:
		push_error("[CassiSim] Poisson residual readback failed")
		return
	var pf = phi.to_float32_array()
	var rf = rhob.to_float32_array()
	var ext_r: Vector3 = _extents()
	var hx = ext_r.x / (float(N) * 0.5)  # per-axis cell sizes
	var hy = ext_r.y / (float(N) * 0.5)
	var hz = ext_r.z / (float(N) * 0.5)
	var num = 0.0
	var den = 0.0
	for k in range(N):
		for j in range(N):
			for i in range(N):
				var id = i + N * (j + N * k)
				var i1 = ((i + 1) % N) + N * (j + N * k)
				var im = ((i - 1 + N) % N) + N * (j + N * k)
				var j1 = i + N * (((j + 1) % N) + N * k)
				var jm = i + N * (((j - 1 + N) % N) + N * k)
				var k1 = i + N * (j + N * ((k + 1) % N))
				var km = i + N * (j + N * ((k - 1 + N) % N))
				# Per-axis 7-point: each direction's second difference divided
				# by its own h_i² (identical to the cube formula at aspect 1).
				var lap_x: float = (pf[i1 * 2] + pf[im * 2] - 2.0 * pf[id * 2]) / (hx * hx)
				var lap_y: float = (pf[j1 * 2] + pf[jm * 2] - 2.0 * pf[id * 2]) / (hy * hy)
				var lap_z: float = (pf[k1 * 2] + pf[km * 2] - 2.0 * pf[id * 2]) / (hz * hz)
				var lap: float = lap_x + lap_y + lap_z
				var rho_v = rf[id]
				num += (lap - rho_v) * (lap - rho_v)
				den += rho_v * rho_v
	_poisson_residual = sqrt(num / max(den, 1e-30))
	print("[CassiSim] Poisson residual: L2 |∇²Φ − ρ| / |ρ| = %.6f  (cells=%d, h=(%.4f,%.4f,%.4f))" % [_poisson_residual, N * N * N, hx, hy, hz])


# load ρ → FFT(x) → FFT(y) → FFT(z) → Φ̂=−ρ̂/k² (k=0 nulled) → IFFT(z) → IFFT(y) → IFFT(x)
func _dispatch_poisson(cl: int) -> void:
	if not _poisson_shader.is_valid(): return
	_rd.compute_list_bind_compute_pipeline(cl, _poisson_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_poisson_0, 0)
	# mode 0: load ρ → complex buffer
	_poisson_pc_bytes.encode_float(0, float(grid_N)); _poisson_pc_bytes.encode_float(4, 0.0)
	_poisson_pc_bytes.encode_float(8, 0.0); _poisson_pc_bytes.encode_float(12, 0.0)
	_poisson_pc_bytes.encode_float(16, cluster_radius * 1.5)
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
	# mode 2: k-space multiply Φ̂ = −ρ̂/k²  (BETWEEN fwd and inv — required)
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

func _make_render_textures() -> void:
	_rt_size = Vector2i(512, 512)
	# Image uniform sets reference the old textures — release them before
	# the textures they point to.
	if _us_fr_2.is_valid(): _rd.free_rid(_us_fr_2)
	if _us_bh_lens_2.is_valid(): _rd.free_rid(_us_bh_lens_2)
	_us_fr_2 = RID(); _us_bh_lens_2 = RID()
	if _field_render_tex.is_valid(): _rd.free_rid(_field_render_tex)
	if _bh_lensing_tex.is_valid(): _rd.free_rid(_bh_lensing_tex)
	_field_render_tex = _make_render_texture(_rt_size.x, _rt_size.y)
	_bh_lensing_tex = _make_render_texture(_rt_size.x, _rt_size.y)
	_update_bh_lens_params()
	print("[CassiSim] Render textures: %dx%d" % [_rt_size.x, _rt_size.y])


func _cache_render_texture_sets() -> void:
	# Rebuild ONLY the image uniform sets after _make_render_textures()
	# recreates the textures (the old sets were freed there). The full
	# _cache_uniform_sets() must not be used here — it would overwrite the
	# live sets of untouched buffers and leak their RIDs.
	if _field_render_shader.is_valid() and _field_render_tex.is_valid():
		_us_fr_2 = _rd.uniform_set_create([
			_get_set2_image_uniform(_field_render_shader, 0, _field_render_tex),
		], _field_render_shader, 2)
	if _bh_lensing_shader.is_valid() and _bh_lensing_tex.is_valid() and _bh_lens_buf.is_valid():
		_us_bh_lens_2 = _rd.uniform_set_create([
			_get_set2_image_uniform(_bh_lensing_shader, 0, _bh_lensing_tex),
			_get_set2_buffer_uniform(_bh_lensing_shader, 1, _bh_lens_buf),
		], _bh_lensing_shader, 2)


func _update_bh_lens_params() -> void:
	# Lens demo params (visual only): BH at screen center, M=0.2, spin=0,
	# G_eff=1.0 — the values the old per-frame array intended but never
	# uploaded. Live in a dedicated buffer so the 36-vec4 sim BH header is
	# never bound to the lensing shader's 4-vec4 layout.
	if not _bh_lens_buf.is_valid(): return
	var p = PackedFloat32Array([
		_rt_size.x * 0.5, _rt_size.y * 0.5, 0.0, 0.0,
		0.2, 0.0, 1.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
		0.0, 0.0, 0.0, 0.0,
	])
	_rd.buffer_update(_bh_lens_buf, 0, 64, p.to_byte_array())


# Rendering
# ═══════════════════════════════════════════════════════════════════════

func _setup_multimesh() -> void:
	var qm = QuadMesh.new()
	qm.size = Vector2(particle_size, particle_size)
	qm.orientation = PlaneMesh.FACE_Z

	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true
	_mm.mesh = qm
	_mm.instance_count = max(N_particles, 1)
	_mm.custom_aabb = AABB(Vector3(-5000, -5000, -5000), Vector3(10000, 10000, 10000))

	_mmi = MultiMeshInstance3D.new()
	_mmi.multimesh = _mm
	add_child(_mmi)

	# GPU-direct: grab the renderer's instance buffer RID (created by
	# multimesh_allocate_data when instance_count was set above) — the
	# instancer compute shader writes it every step, no readback/upload.
	_mm_rd_rid = RenderingServer.multimesh_get_buffer_rd_rid(_mm.get_rid())
	if _mm_rd_rid.is_valid():
		print("[CassiSim] MultiMesh GPU-direct: renderer buffer RID acquired (%d × 64 B)" % max(N_particles, 1))
	else:
		push_error("[CassiSim] multimesh_get_buffer_rd_rid returned an invalid RID — instancer writes will fail")

	var mat = ShaderMaterial.new()
	mat.shader = load("res://shaders/particle_billboard.gdshader")
	mat.render_priority = 1
	_mmi.material_override = mat


func _render_frame() -> void:
	var now_ms := Time.get_ticks_msec()

	# GPU-direct MultiMesh: NO per-frame readback/upload — the instancer
	# shader wrote the renderer's buffer this frame. One-time debug print
	# of the first instances (single small readback, cheap).
	if not suppress_readbacks and not _inst_debug_done and _mm_rd_rid.is_valid() and _step_count >= 1:
		_inst_debug_done = true
		var inst_data = _rd.buffer_get_data(_mm_rd_rid, 0, min(3, N_particles) * 64)
		if inst_data.size() >= 48:
			var mm_f32 := inst_data.to_float32_array()
			for inst_idx in range(min(3, N_particles)):
				var b = inst_idx * 16
				print("[CassiSim] inst[%d] origin=(%.2f,%.2f,%.2f) color=(%.2f,%.2f,%.2f,%.2f)" % [
					inst_idx, mm_f32[b+3], mm_f32[b+7], mm_f32[b+11],
					mm_f32[b+12], mm_f32[b+13], mm_f32[b+14], mm_f32[b+15]])

	# Throttled diagnostics readback (wall-time ~3 Hz; the step-count gate
	# fired 60×/s at high FPS and drained the local device each time)
	var q_guard = now_ms - _last_diag_ms >= int(1000.0 / DIAG_HZ)
	if q_guard and not suppress_readbacks and _field_q.is_valid():
		_last_diag_ms = now_ms
		_ensure_synced()
		var q_data = _rd.buffer_get_data(_field_q, 0, grid_N * grid_N * grid_N * 4)
		if q_data.size() > 0:
			var qf = q_data.to_float32_array()
			var q_sum = 0.0
			for v in qf: q_sum += v
			_q_mean = q_sum / max(qf.size(), 1)
		# Gravity telemetry: saturation counters + q/π/ρ range at particles
		var tel = _rd.buffer_get_data(_tel_buf, 0, 32)
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
			var samples = max(int(tel.decode_u32(28)), 1)
			_pi_sat_hi_frac /= samples
			_pi_sat_lo_frac /= samples
	# One-time Poisson residual report (FD-Laplacian check of the Φ solve).
	# River modes only (0, 3 and 4): modes 1/2 skip the solve, so _fft_buf
	# holds stale data there and the residual would be meaningless.
	if not _poisson_residual_done and _shaders_ready and _step_count >= 1 and (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4):
		_poisson_residual_done = true
		_report_poisson_residual()

	# Throttled occupancy + perf report (~2 Hz; interactive runs only —
	# verify scenes keep playing=false and report their own numbers).
	if playing and not suppress_readbacks and now_ms - _last_occ_ms >= 500:
		_last_occ_ms = now_ms
		if _perf_steps > 0:
			var dt_ms: float = float(_perf_phys_us) / 1e3 / float(_perf_steps)
			var fps: float = float(_perf_frames) * 1000.0 / float(max(now_ms - _perf_last_ms, 1))
			print("[CassiSim] perf: fps=%.1f  physics=%.3f ms/step (%d steps, %d dropped)" % [fps, dt_ms, _perf_steps, _dropped_steps])
		_sample_occupancy()
		_perf_phys_us = 0
		_perf_steps = 0
		_perf_frames = 0
		_perf_last_ms = now_ms

	var realtime_mode = int(mode)

	match realtime_mode:
		0:  # Particles mode (default N-body)
			_render_particles()
		1:  # Field mode
			_render_field_slice()
		2:  # Black hole mode — particles + BH formation, lensing only when BHs exist
			_render_particles()
			if _q_mean > 0.0:
				_render_bh_lensing()
		3:  # Cosmology mode (particles + expanding field)
			_render_particles()




# Sampled occupancy diagnostic: read back up to 40k strided particle
# positions and classify inner / face-edge / corner / out-of-box relative
# to the periodic box (per-axis ±extent_i = ±aspect_i·1.5·cluster_radius;
# lim_i = 0.85·extent_i).
# "Pooling in grid corners" shows up as a growing corner fraction with
# escaped particles stalling at the weak-field box corners.
func _sample_occupancy() -> void:
	if not _pos_buf.is_valid() or N_particles <= 0:
		return
	_ensure_synced()
	var n_sample := mini(N_particles, 40000)
	var stride := maxi(1, int(N_particles / n_sample))
	# Read the FULL position buffer, then subsample with the stride on the
	# CPU — a head-only slice would bias toward the first particles.
	var pd = _rd.buffer_get_data(_pos_buf, 0, N_particles * 16)
	if pd.size() < N_particles * 16:
		return
	var pf = pd.to_float32_array()
	var ext_box: Vector3 = _extents()
	var lim := Vector3(0.85 * ext_box.x, 0.85 * ext_box.y, 0.85 * ext_box.z)
	var in_c := 0
	var face := 0
	var corner := 0
	var out_c := 0
	for s in range(n_sample):
		var i4 = s * stride * 4
		var x: float = pf[i4]
		var y: float = pf[i4 + 1]
		var z: float = pf[i4 + 2]
		if absf(x) > ext_box.x or absf(y) > ext_box.y or absf(z) > ext_box.z:
			out_c += 1
			continue
		# Per-axis normalized distance: c = max_i |x_i|/lim_i < 1 → inner;
		# corner = all three components beyond their own lim (identical to
		# the cube rule at aspect 1).
		var c: float = maxf(absf(x) / lim.x, maxf(absf(y) / lim.y, absf(z) / lim.z))
		if c < 1.0:
			in_c += 1
		else:
			var n_hi := 0
			if absf(x) >= lim.x: n_hi += 1
			if absf(y) >= lim.y: n_hi += 1
			if absf(z) >= lim.z: n_hi += 1
			if n_hi >= 3:
				corner += 1
			else:
				face += 1
	var tot := maxf(float(n_sample), 1.0)
	print("[CassiSim] occ: inner=%.1f%% face/edge=%.1f%% corner=%.1f%% out=%d (n=%d, aspect=%s)" % [
		100.0 * float(in_c) / tot, 100.0 * float(face) / tot,
		100.0 * float(corner) / tot, out_c, n_sample, str(box_aspect)])


func _render_particles() -> void:
	if N_particles <= 0:
		return

	# MultiMesh reads from GPU buffer directly — no CPU transform updates needed.
	# First-particle position debug print, wall-time gated (once per 10 s —
	# each readback stalls the global RD, so no step-count spam).
	var now_ms := Time.get_ticks_msec()
	if not suppress_readbacks and _step_count > 0 and now_ms - _last_p0_rb_ms >= 10000:
		_last_p0_rb_ms = now_ms
		var pos_data = _rd.buffer_get_data(_pos_buf, 0, 16)
		if pos_data.size() >= 16:
			var pos = pos_data.to_float32_array()
			print("[CassiSim] p[0] = (%.3f, %.3f, %.3f)  steps=%d" % [
				pos[0], pos[1], pos[2], _step_count])


func _render_bh_lensing() -> void:
	if not _bh_lensing_shader.is_valid(): return
	var now_ms := Time.get_ticks_msec()
	if now_ms - _last_bh_rb_ms < int(1000.0 / RB_HZ): return  # ~15 Hz cap
	_last_bh_rb_ms = now_ms
	if not _bh_lensing_tex.is_valid():
		_make_render_textures()
		_cache_render_texture_sets()  # sets referencing the new texture

	# Shared PC (11 floats) — pre-allocated, no per-frame allocation
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

	var wg = Vector3i(ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1)

	var cl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _bh_lensing_pipe)
	# Set 2 only — lensing shader doesn't use sets 0 or 1. The set is
	# cached (uniform_set_create was a per-frame local-RD allocation);
	# the params live in the dedicated 4-vec4 _bh_lens_buf, not the
	# 36-vec4 sim BH header.
	_rd.compute_list_bind_uniform_set(cl, _us_bh_lens_2, 2)
	_rd.compute_list_set_push_constant(cl, _pc_bytes, _pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg.x, wg.y, wg.z)
	_rd.compute_list_end()
	# Global RD: no submit/sync; texture_get_data self-stalls.

	# Readback for UI display (15 Hz — one 512² RGBAF readback per gate)
	var bdata = _rd.texture_get_data(_bh_lensing_tex, 0)
	if bdata.size() > 100:
		var img = Image.create_from_data(_rt_size.x, _rt_size.y, false, Image.FORMAT_RGBAF, bdata)
		if img:
			# Reuse the ImageTexture via update() when the size matches —
			# avoids allocating a new GPU texture every readback.
			if bh_display_texture is ImageTexture \
					and bh_display_texture.get_width() == _rt_size.x \
					and bh_display_texture.get_height() == _rt_size.y:
				bh_display_texture.update(img)
			else:
				bh_display_texture = ImageTexture.create_from_image(img)
			bh_texture_updated.emit(bh_display_texture)

# ═══════════════════════════════════════════════════════════════════════
# Public API (for UI to call)
# ═══════════════════════════════════════════════════════════════════════

func reinit() -> void:
	_free_uniform_sets()  # cached sets reference the buffers being freed
	_free_buffers()
	_setup_buffers()
	_cache_uniform_sets()  # CRITICAL: cached sets reference the OLD freed buffers
	_init_field()          # without this, every dispatch after reinit is stale
	_init_particles()
	_apply_gravity_calibration()
	_grav_warmup = true  # fresh acc cache for the regenerated positions
	_step_count = 0
	_cond_step_counter = 0
	_dropped_steps = 0
	_time = 0.0
	_poisson_residual_done = false
	print("[CassiSim] Reinitialized")


func get_diagnostics() -> String:
	var law := "RIVER" if gravity_mode == 0 else ("HEURISTIC" if gravity_mode == 1 else ("PLUMMER" if gravity_mode == 2 else ("RIVER-SELF" if gravity_mode == 3 else "REALSIM")))
	return "t=%.3f  q_mean=%.4f  ε²=%.6f  H=%.4f  sf=%.3f  steps=%d  grav=%s  G_N=%.4f  calib=%s  attr=%s  φ⁶−1=%.4f" % [
		_time, _q_mean, _eps_mean, _hubble, _scale_factor, _step_count, law,
		_gn_eff, "on" if river_calibrate_gn else "off",
		"on" if field_attractor_init else "off", PHI_6 - 1.0]
