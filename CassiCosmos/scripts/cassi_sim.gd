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
const LN2: float = 0.6931471805599453  # ln 2 — degenerate rainbow v_scale fallback (0.95·ln2)
# Qi-rainbow (color_mode 2) stage-1 band — recalibrated 2026-08-12 from the
# measured q = EY²+EI² distribution at particle positions (1M-particle diag
# mirroring the live main.tscn config, 600 steps): typical q sits in
# [3.4e-4, 5.7e-4] — ~1000× BELOW the old φ⁻² anchor (0.381966), which
# pinned normal running at a hue sliver. The two-stage mapping gives the
# whole normal band the FULL hue circle: Q_FLOOR = 2e-4 (just below measured
# p1 = 3.1e-4 → the low tail reads orange-red; q < Q_FLOOR clamps to red)
# to Q_1 = 1e-3 (just above the late-time p99/max = 5.7e-4, so normal
# running stays in the hue stage). h = Q_SCALE·ln(q/Q_FLOOR) with
# Q_SCALE = 1.0/ln(Q_1/Q_FLOOR): f = ln(q/Q_FLOOR)/ln(Q_1/Q_FLOOR) ∈ [0,1]
# maps linearly onto the whole circle (f=0 red, f=0.5 cyan, f=1 red — the
# magenta/pink segment 0.8-1.0 the old 0.8 cap omitted is now visible);
# the measured band spans h ≈ 0.33-0.65 (green → cyan-blue; median 3.8e-4 →
# h = ln(1.9)/ln(5) ≈ 0.40). Stage 2 (q ∈ [Q_1, q_top]) ramps violet at
# Q_1 → pink at q_top (the top hue is pink — red never appears at high
# coherence) while lightness ramps to pure white at q_top = the live
# qi_condensation_threshold export (the explosion point) — recomputed per
# PC fill, so changing the threshold re-anchors the white point live (no
# reinit). The red → violet jump at the Q_1 stage boundary is the
# intentional 'entering the white-hot stage' marker.
const Q_FLOOR: float = 0.0002   # Qi-rainbow stage-1 band floor (hue = 0 at/below)
const Q_1: float = 0.001        # Qi-rainbow stage-1 band top = stage-2 entry

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

# Window VSync (frame pacing to the display refresh). On by default;
# disable for uncapped frame rate (GPU benchmarks and Movie-Maker
# recording want it off). Live — the setter applies it to the window
# immediately; the project setting display/window/vsync/vsync_mode=1 is
# the engine-level default this mirrors.
var _vsync_enabled: bool = true
@export var vsync_enabled: bool:
	get:
		return _vsync_enabled
	set(value):
		_vsync_enabled = value
		_apply_vsync()

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
## Diagnostic: freeze the two-fluid field after init (skip the PDE evolution
## passes). The initialized EY/EI stay fixed and FieldVel stays at its init
## value (zeros) — RealSim viscosity sees a consistently frozen medium — while
## the gravity/particle path (deposit, Poisson, ∇(g·Φ), KDK) runs unchanged.
## Isolates the ω₀² field oscillator's π/ρ/g modulation from the orbital
## dynamics (the v_circ-factor scan's control arm). Default false = full PDE,
## bit-identical behavior.
@export var freeze_field: bool = false
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
## Rotational support of the IC: v_tangential = factor·√(G·M_enc/r) about the
## cluster center (z-axis). 0.85 = legacy sub-Keplerian default (bit-preserving);
## 1.0 = full circular support for the IC convention (G = 1, M = per-cluster
## count). Init-time: reinit() to apply.
@export var initial_v_circ_factor: float = 0.85

# ── Box geometry (theory-accurate grid layout — GRID_LAYOUT.md) ────────
# Per-axis box half-extents: extent_i = box_scale · aspect_i · 1.5 ·
# cluster_radius (N³ cells unchanged; h_i = 2·extent_i/N). Cube (1,1,1) =
# the legacy box (the existing verify battery runs this). Theory preset
# (φ, 1, φ²) maps x = Yang (extended), y = Yin (contracted), z = String/
# P∥ (flow): the box-mode lattice becomes incommensurate — no axis-locked
# box modes, so the straight-line lock at box scale is removed. box_scale
# is a UNIFORM rescale of all three extents: the aspect ratios (and with
# them the box-mode de-resonance and the anisotropic stencil weights) are
# preserved exactly, while the periodic-image forces on the cluster drop
# like 1/(3·box_scale−1)² — scale ≈ 3 is the tested isolation regime
# (multi-axis image-force anisotropy < 2%; the scale-1 short-axis deficit
# is 10–30%). Init-time: reinit() to apply (extents are encoded in the bh
# header and the PCs at setup).
## Per-axis box aspect (extent_i = box_scale·aspect_i·1.5·cluster_radius). Cube (1,1,1) default; theory preset (φ,1,φ²) — see GRID_LAYOUT.md.
@export var box_aspect: Vector3 = Vector3(1.618, 1.0, 2.618)
## Uniform box rescale — separates the cluster from its periodic images while
## keeping the aspect (de-resonance, stencil weights). Default 1.0 = the legacy
## geometry, bit-identical (×1.0 is exact in fp32). See GRID_LAYOUT.md §2.8.
@export var box_scale: float = 1.0

# ── Cascade grid (CASCADE_GRID.md) ─────────────────────────────────────
# Gradient order for the ∇(g·Φ) build pass (bh[3].z, live — no reinit):
#   2 = 3-point central differences (legacy, bit-identical),
#   4 = 5-point central differences — measured ring anisotropy
#       1.246→1.200 @2h, 1.090→1.045 @4h (CASCADE_GRID.md §2).
## Gradient order for the ∇(g·Φ) pass: 2 = 3-point (legacy), 4 = 5-point (O4).
@export var gradient_order: int = 2
# Yin/Yang dual (BCC) grid (bh[3].y, live — no reinit): the deposit → Poisson
# → gradient chain runs on the base lattice AND the half-cell-shifted partner
# lattice; the river arm averages the two ∇(g·Φ) samples (the interleaved pair
# is the BCC lattice). Measured: placement bias 1.187→1.041 worst-dir @4h with
# gradient_order = 4 — 4.6× excess reduction (CASCADE_GRID.md §2). Cost: 2×
# deposit/solve/gradient + a second gradient sample per particle per step.
## Yin/Yang dual (BCC) grid — the shifted partner lattice runs and the force averages both samples. Live (no reinit).
@export var dual_grid: bool = true
# Multi-rung IC seeding (init-time; reinit to apply): Zel'dovich displacement
# δx = Σ_m (A/k_m)·sin(k_m·(d_m·x) + φ_m)·d_m with φ-spaced wavenumbers
# k_m = 2π·φ^m/(base_scale·cluster_radius) and Fibonacci-sphere directions —
# density power at several cascade rungs so bubbles condense at multiple
# scales simultaneously (CASCADE_GRID.md §3.3).
## Multi-rung IC seeding: φ-spaced density modes so bubbles form at several cascade scales. Init-time (reinit to apply).
@export var multi_rung_seed: bool = false
## Number of cascade rungs seeded (φ-spaced wavenumbers).
@export_range(1, 6, 1) var multi_rung_count: int = 3
## Displacement amplitude per rung (world units at the base rung; δx = A/k_m).
@export var multi_rung_amp: float = 0.2
## Base rung wavelength in units of cluster_radius (k_0 = 2π/(base·R)).

@export var multi_rung_base_scale: float = 1.0

## Meshless (moving-Voronoi) field arm — the two-fluid PDE runs on the
## JFA Voronoi cell mesh (MESHLESS_PLAN.md §10) and rasterizes back to
## the grid buffers for the render/condensation/river chain. Init-time
## (reinit to apply); default off = the grid solver, bit-identical.
@export var meshless_mode: bool = true

## Tree gravity (init-time; default off = the grid river arm, bit-identical).
## Takes effect ONLY when meshless_mode is ALSO on — the spectral-Poisson
## river chain is replaced by the open-boundary meshless tree gravity
## (fmm_design.md Q6): the mass deposit + PDE still run (ρ/q source the tree
## gather), but the Poisson FFT chain, the grid ∇(g·Φ) gradient pass and the
## dual-lattice chain are skipped and the nbody arm samples the tree walk's
## per-particle ∇Φ_g. Additive like dual_grid/gradient_order: with it off
## (the default) every existing battery stays bit-identical.
@export var meshless_gravity: bool = true

## Display mode: 0 = Particles, 1 = Field, 2 = Black Hole, 3 = Cosmology.
@export_enum("Particles", "Field", "Black Hole", "Cosmology") var mode: int = 0

# ── Particle color scheme ──────────────────────────────────────────────
## Legacy master selector for the particle colors (the consolidated gradient
## engine's source/count exports below configure it): 0 = the Cassi
## mass-temperature gradient (Salpeter blue dwarfs → red giants; default,
## shader path bit-identical); 1 = velocity rainbow (speed |v|, cycle band
## [0, v_max] measured at init, log progress, hue 0 → 0.95 magenta-pink at
## v_max, held with no wrap beyond); 2 = Qi rainbow (coherence q = EY²+EI²,
## cycle band [qi_cycle] — the FULL hue circle per pass, one pass),
## 3 = Qi double rainbow (two passes over the cycle band — the old mode-3
## doubling, now expressible as mode 2 + rainbow_count = 2). All rainbow
## modes share the white-hot approach band (violet → pink → white at
## qi_condensation_threshold). Live — re-encoded into the
## instancer PC every physics step (no reinit).
@export_enum("Cassi gradient", "Velocity rainbow", "Qi rainbow", "Qi double rainbow") var particle_color_mode: int = 2

# ── Consolidated gradient engine (live exports — read per instancer PC fill) ──
## Rainbow pass count: 0 = AUTO (mode 3 → 2 passes, modes 1/2 → 1); explicit 1-8
## overrides. Each pass sweeps the full cycle hue budget; more passes = finer
## gradient granularity. Live — no reinit.
@export_range(0, 8, 1) var rainbow_count: int = 0
## Per-segment hue shares (lo-tail, pinch, hi-tail) — normalized over the active
## cycle segments; each pass's hue budget is split by these. The pinch segment's
## share × its narrow log width gives the concentrated gradient where most
## particles sit. Live — no reinit.
@export var color_shares: Vector3 = Vector3(0.0, 0.2, 0.8)
## Cycle progress measure: 0 = Log (multiplicative physics — the pinch band is
## the narrowest log interval, intrinsically steepest; default), 1 = Linear.
## Live — no reinit.
@export_enum("Log", "Linear") var color_progress: int = 0
## Qi cycle band [lo, hi] — the hue passes' span over the coherence q. Default
## = the saved working band (3.64e-4 → 0.617); q below lo clamps to red.
## Live — no reinit.
@export var qi_cycle: Vector2 = Vector2(0.00036411325, 0.617382)
## Qi pinch split — the concentrated-gradient band inside the cycle where most
## particles sit (measured q band [3.4e-4, 5.7e-4], median ≈ 3.8e-4). OFF iff
## lo >= hi. Default (0, 0.001) clamps the lo edge to the cycle lo (pinch =
## [cycle lo, 0.001]). Live — no reinit.
@export var qi_pinch: Vector2 = Vector2(0.0, 0.001)
## Qi white-hot approach band [entry, white point] — count-invariant: violet
## (0.8) at the entry → PINK (0.93) exactly at the φ⁻² gate → red (1.0) at the
## white point, lightness 0.5 → 1.0. Live — no reinit.
@export var qi_approach: Vector2 = Vector2(0.617382, 0.618)
## White point = the LIVE qi_condensation_threshold export (re-anchors the
## approach's white end live, no reinit).
@export var qi_approach_tracks_threshold: bool = false
## Velocity cycle band; (0,0) = AUTO (init-measured v_ref → v_max). Live — no
## reinit.
@export var velocity_cycle: Vector2 = Vector2(0.0, 0.0)
## Velocity pinch split; OFF iff lo >= hi. Live — no reinit.
@export var velocity_pinch: Vector2 = Vector2(0.0, 0.0)
## Velocity white-hot approach band; OFF iff lo >= hi. Live — no reinit.
@export var velocity_approach: Vector2 = Vector2(0.0, 0.0)
## Rotate the cycle start hue (adds to the cycle hue before the pass-set wrap).
## Live — no reinit.
@export_range(0.0, 1.0, 0.01) var color_hue_offset: float = 0.0

# ── Camera startup framing (camera-only; no physics) ──────────────────
## On startup, frame a sibling Camera3D on the spawn region: the camera is
## moved to an oblique view of the cluster-centroid and aimed at it, so the
## first frame shows the particles up close instead of the far scene
## default. The free-fly camera controls (free_camera.gd) work normally
## afterwards. Only acts when a sibling Camera3D exists (main/recorder
## scenes); the headless verify scenes have none and are untouched.
@export var auto_frame_camera_on_start: bool = true
## Camera far limit: the camera is pulled back when it flies farther than
## this distance from the grid center (world units), so the particle grid
## can never be lost to the far plane. 0 = AUTO: the camera's far plane
## minus the grid bounding radius — the grid stays just inside the
## visibility limit.
@export_range(0.0, 1000000.0, 1.0) var camera_max_distance: float = 0.0

# ═══════════════════════════════════════════════════════════════════════
# Internal state
# ═══════════════════════════════════════════════════════════════════════

var _rd: RenderingDevice = null

var _sim_cam: Camera3D = null                 # sibling camera (main/recorder); null headless

# — field grid buffers (SET 0) —
var _field_ey: RID; var _field_ei: RID
var _field_q: RID;  var _field_vel: RID

# — Poisson solver (SET 0 of cassi_poisson.glsl) —
var _fft_buf: RID      # vec2 per cell — FFT workspace; real part = Φ after solve
var _tel_buf: RID      # gravity telemetry: [pi_hi, pi_lo, rho_guard, q_min, q_max, pi_min, pi_max, samples]
# — Cell-centered ∇(g·Φ) field (SET 0 binding 7 of cassi_nbody_gravity.glsl) —
var _grad_buf: RID     # vec4 per cell — gradient pass output, river-arm input
var _grad_buf2: RID    # dual-lattice ∇(g·Φ) (SET 0 binding 8 — CASCADE_GRID.md);
					   # always allocated so dual_grid stays a LIVE toggle
var _occ_buf: RID      # occupancy counters (5 uints — cassi_occupancy.glsl)
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
var _occ_shader: RID; var _occ_pipe: RID; var _us_occ_0: RID  # occupancy sampler (diagnostic; CPU fallback)
var _cond_step_counter: int = 0
var _us_inst_0: RID = RID()

# — q-histogram (auto color-align; cassi_qhist.glsl) —
var _qhist_shader: RID; var _qhist_pipe: RID; var _us_qhist_0: RID
var _qhist_buf: RID                 # 128 log-spaced float bins
var _qhist_zero_bytes: PackedByteArray
var _qhist_pc_bytes: PackedByteArray
var _qhist_lo: float = 1e-6         # adaptive log range (growth-tolerant)
var _qhist_hi: float = 1.0
var _last_align_ms: int = 0

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
var _md_pc_bytes: PackedByteArray     # mass deposit PC (8 floats: N, particle_N, extent_x/y/z, off_x/y/z)
var _bh_int_pc_bytes: PackedByteArray # BH integrate PC (4 floats)
var _cond_pc_bytes: PackedByteArray   # condensation PC (4 floats)
var _bh_init_bytes: PackedByteArray   # BH header init (16 floats)
var _tel_reset_bytes: PackedByteArray # gravity telemetry reset (8 floats)
var _poisson_pc_bytes: PackedByteArray  # poisson PC (7 floats: N, axis, dir, mode, extent_x/y/z)
var _occ_pc_bytes: PackedByteArray    # occupancy PC (10 floats: np, n_sample, stride, lim_x/y/z, ext_x/y/z, pad)
var _occ_zero_bytes: PackedByteArray  # occupancy counter reset (32 B of zeros)
# Instancer dedicated PC (32 floats = 128 B — the AMD RDNA3 Vulkan cap;
# EXACTLY 128, nothing more) — the consolidated gradient engine: the shared
# 11 + color_mode@11 + prog_mode@12 + ref@13 + the up-to-3 cycle segments
# (lo1/slope1@14-15, lo2/slope2/off2@16-18, lo3/slope3/off3@19-21) +
# hiC@22 + span_total@23 + the approach band (a_lo@24, a_hi@25, a_top@26,
# approach_on@27) + extent_x/y/z@28-30 + hue_offset@31. The dedicated-PC
# precedent (nbody 15, two-fluid 14, mass-deposit 5): field_render/
# bh_lensing keep the shared 11-float _pc_bytes, and Godot hard-errors on
# push-constant size mismatch, so the instancer's extra fields get their
# own pre-allocated buffer.
var _instancer_pc_bytes: PackedByteArray  # instancer PC (32 floats: 11 shared + color_mode@11 + prog_mode@12 + ref@13 + lo1/slope1@14-15 + lo2/slope2/off2@16-18 + lo3/slope3/off3@19-21 + hiC@22 + span_total@23 + a_lo/a_hi/gate/approach_on@24-27 + extent_x/y/z@28-30 + hue_offset@31)
# ── Meshless (moving-Voronoi) arm — MESHLESS_PLAN.md §10 integration ────
# The field PDE runs on the JFA Voronoi cell mesh and rasterizes back to
# the grid buffers. The accelerator grid stays a lookup accelerator; the
# heavy physics (lap/leapfrog) and the JFA run on the GPU, the 8192-site
# steering/remap bookkeeping is CPU-side between frames (the Stage 2b
# division of labor). Cube-box scope: the mesh world is [0, 2·extent_min)³.
const ML_N1 := 16              # BCC sublattice count → 2·16³ = 8192 sites at N=64
const ML_REBUILD := 25         # steering + remap + JFA-refresh cadence (steps)
const ML_KAPPA := 0.5          # Lloyd-style centroid relaxation fraction
const ML_LAM := 8.0            # super-Lagrangian momentum ride
const ML_RHO_FLOOR := 0.005    # steering guard: rho = EY+EI can hit ~0 in the live field
const ML_MAX_DRIFT := 2.0      # steering guard: cap the per-rebuild site drift (~a quarter cell)
const ML_OM2 := 20.0           # omega_0² — the same conversion constant as the grid PDE
# density-weighted Lloyd on the steered mesh (stage5): the Qi-gate exponent
# on the coherence q (the stage2_moving3d.q_coh / q_weighted_seeds3d power —
# structure relaxes toward the mass centroid, coherent cells ride momentum)
const ML_LLOYD_P := 4.0
# density-weighting floor for the mode-3 centroid (MUST match the shader's
# LLOYD_FLOOR). At rho_mass == 0 the floor makes the weighted centroid the
# EXACT geometric centroid (it cancels in the ratio); a tiny positive value
# keeps the weight nonzero where the deposit has holes. 1e-3 << the deposit
# densities (O(1)) yet >> fp noise, so it is inert in the rho=0 regression.
const ML_LLOYD_FLOOR := 1e-3
const ML_INT_MAX := 2147483647
var _jfa_shader: RID
var _jfa_pipe: RID
var _cell_shader: RID
var _cell_pipe: RID
var _raster_shader: RID
var _raster_pipe: RID
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
var _us_jfa_0: RID
var _us_cell_0: RID
var _us_raster_0: RID
var _jfa_pc_bytes: PackedByteArray    # JFA PC (8 floats: N, jump, read_a, n_sites, h, pad×3)
var _cell_pc_bytes: PackedByteArray   # cell PC (17 floats: mode, N, n_sites, dt, hx, hy, hz, C2, OM2, PHI, source_s, rho_floor, drift_cap, kappa, lam, T_steer, lloyd_p)
var _raster_pc_bytes: PackedByteArray # raster PC (8 floats: N, n_sites, pad×6)
var _ml_sites_cpu := PackedFloat32Array()
var _ml_ready := false
var _ml_step_count := 0

# ── Meshless TREE gravity (fmm_design.md Q6 / wave 3) ──────────────────
# Open-boundary Barnes-Hut octree replacing the spectral-Poisson river chain
# when `meshless_gravity && meshless_mode`. Sources = the 8192 Voronoi sites
# (gather mode 7 → chord-weighted w=m·g); targets = the N-body particles
# (walk writes _ml_tree_grad, which the nbody tree-river arm mode 5 reads).
# Buffers sized for N_src=ml_ns sites (node cap 8·N_src+64) and N_particles
# targets. Allocated ALWAYS (the codebase's meshless-buffer precedent), used
# only when the toggle is on.
const ML_TREE_LEAF_CAP := 1
const ML_TREE_MAX_LEVELS := 14
const ML_TREE_NODE_MAX_MULT := 8
const ML_TREE_FIELD_FLOOR := 1e-6   # source-mass recipe field-density floor
const ML_TREE_THETA := 0.5
const ML_TREE_EPS2 := 1e-6
const GRAVITY_MODE_TREE := 5.0       # `tree river` — gravity_mode value
var _tree_build_shader: RID
var _tree_build_pipe: RID
var _tree_grav_shader: RID
var _tree_grav_pipe: RID
var _ml_tree_src: RID       # vec4[2·nsrc]
var _ml_tree_srcw: RID      # float[nsrc]
var _ml_tree_key: RID       # uint[nsrc]
var _ml_tree_order: RID     # uint[nsrc]
var _ml_tree_cf: RID        # vec4[M]
var _ml_tree_w: RID         # vec4[M]
var _ml_tree_q: RID         # vec4[2M]
var _ml_tree_r: RID         # ivec4[M]
var _ml_tree_ctr: RID       # uint[8]
var _ml_tree_grad: RID      # vec4[N_particles] — per-particle tree ∇Φ_g·(−) (nbody set 1 binding 3)
var _ml_tree_icount: RID    # uint[N_particles] — walk interaction counts (walk binding 10)
var _us_tree_build: RID
var _us_tree_grav: RID
var _tree_build_pc_bytes: PackedByteArray  # build PC (19 floats: 14 shared + grid_N, ext_x/y/z, field_floor)
var _tree_grav_pc_bytes: PackedByteArray   # walk PC (5 floats: N, theta, eps2, use_tp, node_cnt)
var _ml_tree_nsrc: int = 0
var _ml_tree_nnode: int = 0
# ── Tree-gravity LOCAL-RD fallback (2026-08-13) ─────────────────────────
# The global RD (RenderingServer) does NOT execute the tree shaders from
# cassi_sim's _process loop on this build (verified extensively: even a raw
# self-contained mode-10 dispatch with a fresh shader/pipe/set no-ops, while
# the SAME dispatch runs in a bare-Node scene and on any local RD). So the
# in-sim tree arm builds + walks the tree on a LOCAL RenderingDevice
# (proven: verify_meshless_gravity, node_count=11963, G30/G31 pass), reads
# the per-particle gradient back, and re-uploads to the global `_ml_tree_grad`
# via buffer_update for the mode-5 nbody arm. Cost: ~1 HOST round trip per
# frame (readback + upload, ~3×(nsrc×16) + Np×16 + N³×4 ≈ 800 KB@N=64 /
# 150 KB@N=32) — acceptable for the toggle-on arm; see `_tree_local_cadence`.
var _tlrd: RenderingDevice
var _tl_bld_sh: RID; var _tl_bld_pipe: RID
var _tl_grv_sh: RID; var _tl_grv_pipe: RID
var _tl_us_b: RID; var _tl_us_g: RID
var _tl_src: RID; var _tl_srcw: RID; var _tl_key: RID; var _tl_order: RID
var _tl_cf: RID; var _tl_nw: RID; var _tl_nq: RID; var _tl_nr: RID; var _tl_ctr: RID
var _tl_sites: RID; var _tl_psy: RID; var _tl_psi: RID; var _tl_vol: RID; var _tl_rho: RID
var _tl_tgrad: RID; var _tl_tic: RID; var _tl_tpos: RID
var _tl_local_ready := false
var _tl_frame := 0
var _tree_local_cadence := 1  # rebuild+walk on the local RD every N frames

# True when the tree arm is LIVE (meshless + tree gravity). Gates the
# _shaders_ready retry: the tree shaders/pipes/sets must be ready before
# the sim declares itself ready, else a late-arriving tree SPIR-V leaves an
# absent uniform set that Godot silently no-ops.
func _ml_need_tree() -> bool:
	return meshless_mode and meshless_gravity

# — MultiMesh rendering —
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
var _mm_particle_size: float = -1.0  # particle_size the multimesh was built with (reinit rebuild check)
var _rainbow_vref: float = 1.0  # rainbow speed reference: mean initial |v| (set in _init_particles; fallback 1.0)
var _rainbow_vscale: float = 0.95 * LN2  # rainbow hue scale: 0.95/ln(1+v_max/v_ref) (set in _init_particles; degenerate fallback 0.95·ln2)
var _rainbow_vmax: float = 1.0  # max initial speed — the velocity cycle's AUTO band top (set in _init_particles; fallback 1.0)
# One-shot export-validation warnings (the derivation runs every PC fill; the
# warnings fire once per misuse instead of spamming the console every step).
var _warned_rainbow_count: bool = false
var _warned_qi_cycle: bool = false
var _warned_vel_cycle: bool = false

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
## Simulation time-scale: 1 = real time (default), 0.5 = half speed,
## 2 = 2× time-lapse, etc. The per-frame step cap scales with it, so
## fast-forward stays smooth at any frame rate. Live — no reinit.
@export_range(0.05, 10.0, 0.05) var sim_speed: float = 1.0
## Auto color-align: every ~1.5 s, re-fit the Qi color band to the live
## coherence distribution AT the particles (p1/p99 of a GPU q-histogram),
## so the colors stay spread across the rainbow when the coherence grows
## fast (e.g. the Meshless gravity mode). Dragging a legend handle or
## clicking Fit turns it off — manual takes over. Live — no reinit.
@export var auto_align_colors: bool = true
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

func _apply_vsync() -> void:
	# Live window VSync. The DisplayServer call is a no-op under the
	# headless/dummy driver (verify scenes, import passes) — harmless.
	DisplayServer.window_set_vsync_mode(
		DisplayServer.VSYNC_ENABLED if _vsync_enabled else DisplayServer.VSYNC_DISABLED)

func _ready() -> void:
	_apply_vsync()  # mirror the export (scene load may have set it before ready)
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
	# User-saved color defaults override the scene pins (user://color_defaults.cfg
	# — written by the bottom-bar "Save" button). No file → scene/exports stand.
	load_color_defaults()
	# Frame-0 / paused view for the rainbow modes (1/2/3): with playing=false
	# the instancer never dispatches, so the CPU init_inst pass provides the
	# visible colors — but the CPU path cannot sample the field cheaply. The
	# one-shot GPU repaint computes the colors from the uploaded pos/vel/q
	# buffers instead. Safe HERE (verified ordering): _setup_shaders cached
	# _us_inst_0, _instancer_pc_bytes is allocated (32 floats), and the
	# pos/vel/q buffers + the multimesh RD buffer are all valid (init_field
	# and init_particles ran; _mm.buffer = init_inst sized the renderer's
	# buffer). If the shader import race left _us_inst_0 invalid the call
	# no-ops and the placeholder colors stand until the retry compiles.
	if particle_color_mode != 0:
		_repaint_instancer()
	print("[CassiSim] Universe ready — grid=%d³ particles=%d xi=%.5f (φ⁶=%.5f)" % [grid_N, N_particles, xi, PHI_6])
	_sim_cam = _find_sibling_camera()
	_auto_frame_camera()


# ═══════════════════════════════════════════════════════════════════════
# Color-defaults persistence (user://color_defaults.cfg — bottom-bar Save)
# ═══════════════════════════════════════════════════════════════════════
const COLOR_DEFAULTS_PATH := "user://color_defaults.cfg"


## Persist the current color-scale settings as the startup defaults.
func save_color_defaults() -> void:
	var cfg := ConfigFile.new()
	cfg.set_value("colors", "particle_color_mode", particle_color_mode)
	cfg.set_value("colors", "rainbow_count", rainbow_count)
	cfg.set_value("colors", "color_shares_x", color_shares.x)
	cfg.set_value("colors", "color_shares_y", color_shares.y)
	cfg.set_value("colors", "color_shares_z", color_shares.z)
	cfg.set_value("colors", "color_progress", color_progress)
	cfg.set_value("colors", "color_hue_offset", color_hue_offset)
	cfg.set_value("colors", "qi_cycle_x", qi_cycle.x)
	cfg.set_value("colors", "qi_cycle_y", qi_cycle.y)
	cfg.set_value("colors", "qi_pinch_x", qi_pinch.x)
	cfg.set_value("colors", "qi_pinch_y", qi_pinch.y)
	cfg.set_value("colors", "qi_approach_x", qi_approach.x)
	cfg.set_value("colors", "qi_approach_y", qi_approach.y)
	cfg.set_value("colors", "qi_approach_tracks_threshold", qi_approach_tracks_threshold)
	cfg.set_value("colors", "velocity_cycle_x", velocity_cycle.x)
	cfg.set_value("colors", "velocity_cycle_y", velocity_cycle.y)
	cfg.set_value("colors", "velocity_pinch_x", velocity_pinch.x)
	cfg.set_value("colors", "velocity_pinch_y", velocity_pinch.y)
	cfg.set_value("colors", "velocity_approach_x", velocity_approach.x)
	cfg.set_value("colors", "velocity_approach_y", velocity_approach.y)
	var err := cfg.save(COLOR_DEFAULTS_PATH)
	print("[CassiSim] color defaults saved (err=", err, ")")


## Apply the saved color defaults over the current exports. Returns false
## when no saved file exists (the caller can fall back to a factory fit).
func load_color_defaults() -> bool:
	var cfg := ConfigFile.new()
	if cfg.load(COLOR_DEFAULTS_PATH) != OK:
		return false
	particle_color_mode = int(cfg.get_value("colors", "particle_color_mode", particle_color_mode))
	rainbow_count = int(cfg.get_value("colors", "rainbow_count", rainbow_count))
	color_shares = Vector3(
		float(cfg.get_value("colors", "color_shares_x", color_shares.x)),
		float(cfg.get_value("colors", "color_shares_y", color_shares.y)),
		float(cfg.get_value("colors", "color_shares_z", color_shares.z)))
	color_progress = int(cfg.get_value("colors", "color_progress", color_progress))
	color_hue_offset = float(cfg.get_value("colors", "color_hue_offset", color_hue_offset))
	qi_cycle = Vector2(
		float(cfg.get_value("colors", "qi_cycle_x", qi_cycle.x)),
		float(cfg.get_value("colors", "qi_cycle_y", qi_cycle.y)))
	qi_pinch = Vector2(
		float(cfg.get_value("colors", "qi_pinch_x", qi_pinch.x)),
		float(cfg.get_value("colors", "qi_pinch_y", qi_pinch.y)))
	qi_approach = Vector2(
		float(cfg.get_value("colors", "qi_approach_x", qi_approach.x)),
		float(cfg.get_value("colors", "qi_approach_y", qi_approach.y)))
	qi_approach_tracks_threshold = bool(cfg.get_value("colors", "qi_approach_tracks_threshold", qi_approach_tracks_threshold))
	velocity_cycle = Vector2(
		float(cfg.get_value("colors", "velocity_cycle_x", velocity_cycle.x)),
		float(cfg.get_value("colors", "velocity_cycle_y", velocity_cycle.y)))
	velocity_pinch = Vector2(
		float(cfg.get_value("colors", "velocity_pinch_x", velocity_pinch.x)),
		float(cfg.get_value("colors", "velocity_pinch_y", velocity_pinch.y)))
	velocity_approach = Vector2(
		float(cfg.get_value("colors", "velocity_approach_x", velocity_approach.x)),
		float(cfg.get_value("colors", "velocity_approach_y", velocity_approach.y)))
	print("[CassiSim] color defaults loaded")
	return true


## Whether a saved color-defaults file exists.
func has_color_defaults() -> bool:
	return FileAccess.file_exists(COLOR_DEFAULTS_PATH)


func _process(delta: float) -> void:
	if not _rd:
		return
	_enforce_camera_max_distance()

	# First-run import race: on a fresh cache the .glsl imports may not have
	# finished when _ready ran — retry until every shader compiles.
	if not _shaders_ready:
		_setup_retry_counter += 1
		if _setup_retry_counter % 30 == 0:
			_free_shaders()
			_setup_shaders()

	if playing and _shaders_ready:
		# Fixed-dt accumulator with a BOUNDED CARRY: steps/frame = accumulated
		# real time (× sim_speed) / dt, capped. A brief hitch carries at most
		# one frame's worth of backlog into the next frame (graceful catch-up
		# — the sim keeps real-time instead of falling into slow-motion);
		# only pathological stalls drop steps, counted in _dropped_steps. The
		# cap scales with sim_speed so time-lapse works at any frame rate
		# (max_steps_per_frame stays the floor).
		var step_cap: int = maxi(max_steps_per_frame, int(ceili(sim_speed)) * max_steps_per_frame)
		_step_timer += delta * sim_speed
		var n_steps := 0
		while _step_timer >= dt and n_steps < step_cap:
			_step_timer -= dt
			n_steps += 1
		if _step_timer >= dt:
			var carry_max := float(step_cap) * dt
			var excess := int(_step_timer / dt)
			_dropped_steps += maxi(excess - step_cap, 0)
			_step_timer = minf(_step_timer, carry_max)
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
	# BH header (count/G_N/extent/toggle/dual) — constant across the frame's
	# steps; buffer_update must run BEFORE compute_list_begin.
	# Re-encode the live BH toggles every frame so a UI flip takes effect
	# next frame with NO reinit: bh[3].x = black_holes_enabled (float 48),
	# bh[3].y = dual_grid (float 52), bh[3].z = gradient_order (float 56),
	# bh[1].xyz = the dual-grid offset h_i/2 = extent_i/N (floats 16/20/24 —
	# CASCADE_GRID.md). The shaders gate on the same values.
	_bh_init_bytes.encode_float(48, 1.0 if black_holes_enabled else 0.0)
	_bh_init_bytes.encode_float(52, 1.0 if dual_grid else 0.0)
	_bh_init_bytes.encode_float(56, float(gradient_order))
	var _off_dual: Vector3 = _extents() / float(grid_N)
	_bh_init_bytes.encode_float(16, _off_dual.x)
	_bh_init_bytes.encode_float(20, _off_dual.y)
	_bh_init_bytes.encode_float(24, _off_dual.z)
	_rd.buffer_update(_bh_buf, 0, _bh_init_bytes.size(), _bh_init_bytes)
	# ── Meshless tree gravity: build + walk, once per frame (cadence),
	# before the steps, so mode-5 nbody reads a fresh _ml_tree_grad
	# (fmm_design.md Q6). All gates off by default → the default battery is
	# bit-identical.
	#
	# NOTE (Godot 4.7, 2026-08-13): the global RD does NOT execute the tree
	# shaders from the sim's _process loop on this build — verified to the
	# last rung (even a raw self-contained mode-10 dispatch with a fresh
	# shader/pipe/set no-ops in the sim while the same dispatch runs in a
	# bare-Node scene and on any local RD). The in-sim tree arm therefore
	# builds + walks the tree on a LOCAL RenderingDevice (the
	# verify_meshless_gravity-proven path: node_count=11963, G30/G31 PASS),
	# reads the gradient back, and re-uploads to the global `_ml_tree_grad`
	# via buffer_update — so the mode-5 nbody arm reads a fresh gradient.
	# Cost: one host round trip per cadence frame (~800 KB upload+readback
	# split @N=64, ~150 KB @N=32) — acceptable for the toggle-on arm; see
	# `_tree_local_cadence` (currently every frame = 1). The global tree
	# shaders/pipes/sets remain allocated (and are PROVEN correct on a
	# local RD); they are simply not dispatched on the global RD.
	#
	# The nbody mode-5 seam + walk TargetPos-binding fixes (earlier commits)
	# remain: _step_dispatches encodes the effective mode 5.0, and the walk
	# reads _pos_buf for targets — both still required for the local-RD
	# gradient to reach the particles.
	var tree_arm := meshless_mode and meshless_gravity and _ml_ready
	if tree_arm:
		_ml_tree_nsrc = 2 * ML_N1 * ML_N1 * ML_N1
		_dispatch_tree_gravity_local()
	var cl = _rd.compute_list_begin()

	for _s in range(n_steps):
		_step_dispatches(cl)
	# ── q-histogram (auto color-align): one strided pass per frame while
	# auto_align_colors is on and the Qi rainbow is the active source. The
	# field's barrier from the last step gives the q reads visibility.
	# Runs even under suppress_readbacks: its 512 B readback every 1.5 s is
	# negligible next to the multi-MB diagnostics that toggle suppresses. ──
	if _qhist_pipe.is_valid() and _us_qhist_0.is_valid() and auto_align_colors \
			and particle_color_mode >= 2 and N_particles > 0:
		var qext := _extents()
		_qhist_pc_bytes.encode_float(0, float(grid_N))
		_qhist_pc_bytes.encode_float(4, float(N_particles))
		_qhist_pc_bytes.encode_float(8, 16.0)               # particle stride
		_qhist_pc_bytes.encode_float(12, _qhist_lo)
		_qhist_pc_bytes.encode_float(16, _qhist_hi)
		_qhist_pc_bytes.encode_float(20, 128.0)             # bins
		_qhist_pc_bytes.encode_float(24, 1.0)               # enabled
		_qhist_pc_bytes.encode_float(28, qext.x)
		_qhist_pc_bytes.encode_float(32, qext.y)
		_qhist_pc_bytes.encode_float(36, qext.z)
		_rd.compute_list_bind_compute_pipeline(cl, _qhist_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_qhist_0, 0)
		_rd.compute_list_set_push_constant(cl, _qhist_pc_bytes, _qhist_pc_bytes.size())
		var qh_threads := ceili(float(N_particles) / 16.0)
		_rd.compute_list_dispatch(cl, ceili(qh_threads / 64.0), 1, 1)
	# ── Instancer: GPU-only MultiMesh update, ONCE PER FRAME ──────────
	# Hoisted out of the per-step loop: only the frame's FINAL particle
	# state is drawn, so a per-step write of the full instance buffer
	# (N × 80 B) was max_steps_per_frame−1 redundant dispatches per
	# frame. One dispatch after the last step writes the state the
	# renderer actually draws. The PC fill runs here (not per step) so
	# _time is the frame's final time. (Paused repaint:
	# _repaint_instancer.) The last step's trailing barrier gives the
	# pos/vel writes their memory visibility before this dispatch.
	if _instancer_shader.is_valid() and N_particles > 0:
		_fill_instancer_pc()
		var ipg := ceili(float(N_particles) / 256.0)
		_rd.compute_list_bind_compute_pipeline(cl, _instancer_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_inst_0, 0)
		_rd.compute_list_set_push_constant(cl, _instancer_pc_bytes, _instancer_pc_bytes.size())
		_rd.compute_list_dispatch(cl, ipg, 1, 1)
	_rd.compute_list_end()

	# Meshless steering: rebuild the mesh every ML_REBUILD steps, BETWEEN
	# frames (the CPU-side site bookkeeping — the Stage 2b division of
	# labor). The readbacks self-stall; the JFA/volume re-dispatches are
	# standalone compute lists, legal outside the frame list.
	if meshless_mode and _ml_ready and not freeze_field:
		_ml_step_count += n_steps
		if _ml_step_count >= ML_REBUILD:
			_ml_step_count = 0
			_mesh_rebuild()


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
# box_scale multiplies ALL three extents (uniform rescale): aspect ratios,
# box-mode de-resonance and the two-fluid stencil weights are invariant,
# while the periodic-image forces on the cluster drop like 1/(3·box_scale−1)²
# (GRID_LAYOUT.md §2.8). Clamped positive so a degenerate box_scale can
# never produce zero/negative extents (h_i = 2·extent_i/N → NaN).
func _extents() -> Vector3:
	return Vector3(box_aspect.x, box_aspect.y, box_aspect.z) * (cluster_radius * 1.5) * maxf(box_scale, 1e-3)

func _extent_min() -> float:
	var e := _extents()
	return minf(minf(e.x, e.y), e.z)


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
	# Cluster center positions + masses (for multi-cluster gravity).
	# 64-vec4 cap — keep in sync with ClusterBuf in cassi_nbody_gravity.glsl
	# (set 2 binding 1); cluster indices 0..63 are safe.
	_cluster_buf = _rd.storage_buffer_create(64 * 4 * 4)
	# Mass density grid (float per cell — float atomicAdd deposit, see
	# cassi_mass_deposit.glsl)
	_mass_density_buf = _rd.storage_buffer_create(nc * 4)
	# Cell-centered ∇(g·Φ) field (vec4 per cell — river-arm gradient,
	# rebuilt every step by the gradient pass between poisson and nbody)
	_grad_buf = _rd.storage_buffer_create(nc * 16)
	# Dual-lattice ∇(g·Φ) (CASCADE_GRID.md — always allocated so dual_grid
	# stays a LIVE toggle; written only by the shifted gradient pass).
	_grad_buf2 = _rd.storage_buffer_create(nc * 16)
	# q-histogram for auto color-align (cassi_qhist.glsl): 128 log-spaced bins
	_qhist_buf = _rd.storage_buffer_create(128 * 4)
	_qhist_zero_bytes = PackedByteArray(); _qhist_zero_bytes.resize(128 * 4)
	_qhist_pc_bytes = PackedByteArray(); _qhist_pc_bytes.resize(10 * 4)
	# Meshless arm buffers (allocated always; used only when meshless_mode
	# is on). The JFA labels ping-pong; the per-site state carries the cell
	# averages; the rebuild scratch (centroids/remap/temps) rides the GPU.
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
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
	_jfa_pc_bytes = PackedByteArray(); _jfa_pc_bytes.resize(8 * 4)
	_cell_pc_bytes = PackedByteArray(); _cell_pc_bytes.resize(17 * 4)  # mode,N,n_sites,dt,hx,hy,hz,C2,OM2,PHI,src,rho_floor,drift_cap,kappa,lam,T_steer,lloyd_p
	_raster_pc_bytes = PackedByteArray(); _raster_pc_bytes.resize(8 * 4)
	# ── Tree-gravity buffers (allocated always; used when meshless_gravity) ──
	# Sources = the Voronoi sites (ml_ns); targets = the N-body particles.
	# Node cap NODE_MAX = ML_TREE_NODE_MAX_MULT·nsrc + slack — the octree of
	# 8192 sites stays well under 8·8192 nodes even at leaf_cap=1.
	_ml_tree_nsrc = ml_ns
	var tnm: int = ML_TREE_NODE_MAX_MULT * ml_ns + 64
	_ml_tree_src = _rd.storage_buffer_create(2 * ml_ns * 16)
	_ml_tree_srcw = _rd.storage_buffer_create(ml_ns * 4)
	_ml_tree_key = _rd.storage_buffer_create(ml_ns * 4)
	_ml_tree_order = _rd.storage_buffer_create(ml_ns * 4)
	_ml_tree_cf = _rd.storage_buffer_create(tnm * 16)
	_ml_tree_w = _rd.storage_buffer_create(tnm * 16)
	_ml_tree_q = _rd.storage_buffer_create(2 * tnm * 16)
	_ml_tree_r = _rd.storage_buffer_create(tnm * 16)
	_ml_tree_ctr = _rd.storage_buffer_create(8 * 4)
	# per-particle tree gradient + walk counts (N_particles targets;
	# a minimum of 1 keeps the buffers non-zero-sized even for N_particles=0
	# verify scenes, so the walk uniform set never fails to bind)
	_ml_tree_grad = _rd.storage_buffer_create(maxi(N_particles, 1) * 16)
	_ml_tree_icount = _rd.storage_buffer_create(maxi(N_particles, 1) * 4)
	_tree_build_pc_bytes = PackedByteArray(); _tree_build_pc_bytes.resize(19 * 4)
	_tree_grav_pc_bytes = PackedByteArray(); _tree_grav_pc_bytes.resize(5 * 4)

	# Pre-allocate push-constant byte buffers (hitch-free pattern)
	_pc_bytes = PackedByteArray(); _pc_bytes.resize(11 * 4)
	_nbody_pc_bytes = PackedByteArray(); _nbody_pc_bytes.resize(15 * 4)
	# Two-fluid dedicated PC (14 floats = 56 B): the shared 11 fields + the
	# 3 per-axis extents for the anisotropic 19-point stencil (GRID_LAYOUT.md).
	_two_fluid_pc_bytes = PackedByteArray(); _two_fluid_pc_bytes.resize(14 * 4)
	_md_pc_bytes = PackedByteArray(); _md_pc_bytes.resize(8 * 4)
	_instancer_pc_bytes = PackedByteArray(); _instancer_pc_bytes.resize(32 * 4)  # consolidated gradient engine PC — 128 B (the RDNA3 Vulkan cap)
	_bh_int_pc_bytes = PackedByteArray(); _bh_int_pc_bytes.resize(4 * 4)
	_cond_pc_bytes = PackedByteArray(); _cond_pc_bytes.resize(4 * 4)
	_poisson_pc_bytes = PackedByteArray(); _poisson_pc_bytes.resize(7 * 4)
	_occ_pc_bytes = PackedByteArray(); _occ_pc_bytes.resize(10 * 4)
	# NOTE: all poisson dispatches (clear/load/kspace/FFT) are 2D (N, N, 1) —

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
				_grad_buf, _grad_buf2, _occ_buf, _qhist_buf,
				_ml_labels_a, _ml_labels_b, _ml_sites,
				_ml_psi_y, _ml_psi_i, _ml_pi_y, _ml_pi_i,
				_ml_lap_y, _ml_lap_i, _ml_vol,
				_ml_cen, _ml_remap, _ml_tmp_y, _ml_tmp_i, _ml_tmp_py, _ml_tmp_pi,
				_ml_tree_src, _ml_tree_srcw, _ml_tree_key, _ml_tree_order,
				_ml_tree_cf, _ml_tree_w, _ml_tree_q, _ml_tree_r, _ml_tree_ctr,
				_ml_tree_grad, _ml_tree_icount,
				_field_render_tex, _bh_lensing_tex]:
		if rid.is_valid(): _rd.free_rid(rid)
	_field_render_tex = RID()
	_bh_lensing_tex = RID()
	_tree_local_free()


# Free the local-RD tree buffers/shader/pipe/set + the local RenderingDevice
# itself (a separate device from the sim's global RD).
func _tree_local_free() -> void:
	if _tlrd == null:
		return
	for rid in [_tl_src, _tl_srcw, _tl_key, _tl_order, _tl_cf, _tl_nw, _tl_nq,
				_tl_nr, _tl_ctr, _tl_sites, _tl_psy, _tl_psi, _tl_vol, _tl_rho,
				_tl_tgrad, _tl_tic, _tl_tpos, _tl_us_b, _tl_us_g,
				_tl_bld_pipe, _tl_bld_sh, _tl_grv_pipe, _tl_grv_sh]:
		if rid.is_valid(): _tlrd.free_rid(rid)
	_tlrd.free()
	_tlrd = null
	_tl_local_ready = false

func _free_uniform_sets() -> void:
	# Uniform sets reference buffers/shaders/textures — release them BEFORE
	# any of those are freed (reinit, shader retry, exit). Overwriting a
	# live set RID without freeing it leaks the set on the local RD.
	if _rd == null: return
	for rid in [_us_two_0, _us_two_1, _us_two_2, _us_mass_dep_0,
				_us_nbody_0, _us_nbody_1, _us_nbody_2, _us_poisson_0,
				_us_fr_0, _us_fr_2, _us_cond_0, _us_cond_1,
				_us_bh_int_0, _us_bh_int_1, _us_inst_0, _us_bh_lens_2,
				_us_occ_0, _us_qhist_0, _us_jfa_0, _us_cell_0, _us_raster_0,
				_us_tree_build, _us_tree_grav]:
		if rid.is_valid(): _rd.free_rid(rid)
	_us_two_0 = RID(); _us_two_1 = RID(); _us_two_2 = RID()
	_us_mass_dep_0 = RID()
	_us_nbody_0 = RID(); _us_nbody_1 = RID(); _us_nbody_2 = RID()
	_us_poisson_0 = RID()
	_us_fr_0 = RID(); _us_fr_2 = RID()
	_us_cond_0 = RID(); _us_cond_1 = RID()
	_us_bh_int_0 = RID(); _us_bh_int_1 = RID()
	_us_inst_0 = RID(); _us_bh_lens_2 = RID()
	_us_occ_0 = RID()
	_us_jfa_0 = RID(); _us_cell_0 = RID(); _us_raster_0 = RID()
	_us_tree_build = RID(); _us_tree_grav = RID()

func _free_shaders() -> void:
	_free_uniform_sets()  # sets hold shader references; release before the shaders
	# Pipelines before their shaders (freeing a pipeline after its shader
	# reports "Attempted to free invalid ID" on the local RD at exit).
	for rid in [_two_fluid_pipe, _nbody_pipe, _poisson_pipe,
				_field_render_pipe, _bh_lensing_pipe,
				_instancer_pipe, _mass_deposit_pipe,
				_cond_pipe, _bh_int_pipe, _occ_pipe, _qhist_pipe,
				_jfa_pipe, _cell_pipe, _raster_pipe,
				_tree_build_pipe, _tree_grav_pipe,
				_two_fluid_shader, _nbody_shader, _poisson_shader,
				_field_render_shader, _bh_lensing_shader,
				_instancer_shader, _mass_deposit_shader,
				_cond_shader, _bh_int_shader, _occ_shader, _qhist_shader,
				_jfa_shader, _cell_shader, _raster_shader,
				_tree_build_shader, _tree_grav_shader]:
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

	# Occupancy sampler (diagnostic — GPU-side box classification; the
	# 0.5 s occupancy readback no longer drags the full position buffer).
	# Optional: _sample_occupancy falls back to the CPU path if invalid.
	_occ_shader = _shader_from_file("res://compute/cassi_occupancy.glsl")
	if _occ_shader.is_valid():
		_occ_pipe = _rd.compute_pipeline_create(_occ_shader)
		print("[CassiSim] Occupancy sampler pipeline ready")

	# q-histogram sampler (auto color-align; optional like the occupancy
	# sampler — excluded from _shaders_ready, so a missing import just
	# leaves the color band manual).
	_qhist_shader = _shader_from_file("res://compute/cassi_qhist.glsl")
	if _qhist_shader.is_valid():
		_qhist_pipe = _rd.compute_pipeline_create(_qhist_shader)
		print("[CassiSim] q-histogram sampler pipeline ready")

	# Meshless (Voronoi cell) arm — MESHLESS_PLAN.md §10
	_jfa_shader = _shader_from_file("res://compute/cassi_jfa.glsl")
	if _jfa_shader.is_valid():
		_jfa_pipe = _rd.compute_pipeline_create(_jfa_shader)
		print("[CassiSim] JFA Voronoi pipeline ready")
	_cell_shader = _shader_from_file("res://compute/cassi_voronoi_cells.glsl")
	if _cell_shader.is_valid():
		_cell_pipe = _rd.compute_pipeline_create(_cell_shader)
		print("[CassiSim] Voronoi cell pipeline ready")
	_raster_shader = _shader_from_file("res://compute/cassi_voronoi_raster.glsl")
	if _raster_shader.is_valid():
		_raster_pipe = _rd.compute_pipeline_create(_raster_shader)
		print("[CassiSim] Voronoi raster pipeline ready")
	# ── Tree-gravity arm (fmm_design.md; always built so meshless_gravity
	# stays a LIVE toggle — used only when meshless_mode && meshless_gravity)
	_tree_build_shader = _shader_from_file("res://compute/cassi_tree_build.glsl")
	if _tree_build_shader.is_valid():
		_tree_build_pipe = _rd.compute_pipeline_create(_tree_build_shader)
		print("[CassiSim] tree-build pipeline ready")
	_tree_grav_shader = _shader_from_file("res://compute/cassi_tree_gravity.glsl")
	if _tree_grav_shader.is_valid():
		_tree_grav_pipe = _rd.compute_pipeline_create(_tree_grav_shader)
		print("[CassiSim] tree-walk pipeline ready")

	_cache_uniform_sets()
	_shaders_ready = (
		_two_fluid_shader.is_valid() and _nbody_shader.is_valid()
		and _poisson_shader.is_valid() and _mass_deposit_shader.is_valid()
		and _instancer_shader.is_valid() and _cond_shader.is_valid()
		and _bh_int_shader.is_valid() and _field_render_shader.is_valid()
		and _bh_lensing_shader.is_valid()
		# Tree arm must be genuinely ready too, else the retry loop stops
		# while the tree uniform sets/pipes are missing (Godot silently
		# no-ops a dispatch with an absent set).
		and (_tree_build_pipe.is_valid() or not _ml_need_tree())
		and (_tree_grav_pipe.is_valid() or not _ml_need_tree())
		and (_us_tree_build.is_valid() or not _ml_need_tree())
		and (_us_tree_grav.is_valid() or not _ml_need_tree()))


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
		_uniform_storage(8, _grad_buf2),  # dual-lattice ∇(g·Φ) (CASCADE_GRID.md)
	], _nbody_shader, 0)
	_us_nbody_1 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf), _uniform_storage(1, _vel_buf),
		_uniform_storage(2, _acc_buf),
		_uniform_storage(3, _ml_tree_grad),  # tree-river (mode 5): per-particle ∇Φ_g
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
			_uniform_storage(2, _vel_buf),  # velocity rainbow (color_mode 1)
			_uniform_storage(3, _field_q),  # Qi rainbow (color_mode 2/4): coherence q = EY²+EI² grid
			_uniform_storage(4, _field_ey),  # two-axis (color_mode 4): ρ = EY+EI lightness axis
			_uniform_storage(5, _field_ei),  # two-axis (color_mode 4): ρ = EY+EI
		], _instancer_shader, 0)
		print("[CassiSim] Instancer uniform set cached (GPU-direct multimesh buffer)")

	# Mass deposit
	_us_mass_dep_0 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf),
		_uniform_storage(1, _mass_density_buf),
	], _mass_deposit_shader, 0)
	print("[CassiSim] Mass deposit uniform set cached")



	# Occupancy sampler (diagnostic; CPU fallback if invalid — the shader
	# is optional and excluded from _shaders_ready)
	if _occ_shader.is_valid() and _pos_buf.is_valid() and _occ_buf.is_valid():
		_us_occ_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _occ_buf),
		], _occ_shader, 0)

	# q-histogram sampler (auto color-align; optional like occupancy)
	if _qhist_shader.is_valid() and _pos_buf.is_valid() and _field_q.is_valid() and _qhist_buf.is_valid():
		_us_qhist_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _field_q),
			_uniform_storage(2, _qhist_buf),
		], _qhist_shader, 0)

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
		], _cell_shader, 0)
	if _raster_shader.is_valid():
		_us_raster_0 = _rd.uniform_set_create([
			_uniform_storage(0, _ml_labels_a), _uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i), _uniform_storage(3, _field_ey),
			_uniform_storage(4, _field_ei), _uniform_storage(5, _field_q),
		], _raster_shader, 0)
	# ── Tree-gravity uniform sets (fmm_design.md) ──
	# Build shader declares bindings 0-13 (set 0): the octree buffers PLUS the
	# meshless gather sources (9-13). Walk shader declares 0,3-8 + 9,10,11 —
	# a SEPARATE set (Godot validates bindings against the shader's set).
	# Created ONLY when the tree arm is live (meshless_mode + meshless_gravity):
	# the walk set binds _pos_buf, which is 0-size for N_particles=0 verify
	# scenes → a set created there would fail and push a false error.
	if _tree_build_shader.is_valid() and _ml_need_tree():
		_us_tree_build = _rd.uniform_set_create([
			_uniform_storage(0, _ml_tree_src), _uniform_storage(1, _ml_tree_srcw),
			_uniform_storage(2, _ml_tree_key), _uniform_storage(3, _ml_tree_order),
			_uniform_storage(4, _ml_tree_cf), _uniform_storage(5, _ml_tree_w),
			_uniform_storage(6, _ml_tree_q), _uniform_storage(7, _ml_tree_r),
			_uniform_storage(8, _ml_tree_ctr),
			_uniform_storage(9, _ml_sites),
			_uniform_storage(10, _ml_psi_y), _uniform_storage(11, _ml_psi_i),
			_uniform_storage(12, _ml_vol), _uniform_storage(13, _mass_density_buf),
		], _tree_build_shader, 0)
		if not _us_tree_build.is_valid():
			push_error("[CassiSim] tree-build uniform set FAILED to create (bindings 0-13)")
	if _tree_grav_shader.is_valid() and _ml_need_tree():
		_us_tree_grav = _rd.uniform_set_create([
			_uniform_storage(0, _ml_tree_src), _uniform_storage(3, _ml_tree_order),
			_uniform_storage(4, _ml_tree_cf), _uniform_storage(5, _ml_tree_w),
			_uniform_storage(6, _ml_tree_q), _uniform_storage(7, _ml_tree_r),
			_uniform_storage(8, _ml_tree_ctr),
			_uniform_storage(9, _ml_tree_grad), _uniform_storage(10, _ml_tree_icount),
			_uniform_storage(11, _pos_buf),  # walk TargetPos — targets = N-body particles (use_tp=1)
		], _tree_grav_shader, 0)
		if not _us_tree_grav.is_valid():
			push_error("[CassiSim] tree-walk uniform set FAILED to create (bindings 0,3-11)")
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
	_ml_ready = false
	if meshless_mode:
		_meshless_init()


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


# ── Camera startup framing (camera-only; mirrors the placement below) ──
## Mean of the cluster centers (the spawn region's center of mass),
## mirroring the placement in _init_particles (ring for nc <= 8, Fibonacci
## sphere above). A single cluster centers at (cluster_separation, 0, 0).
func _cluster_centroid() -> Vector3:
	var nc := maxi(1, num_clusters)
	var sep := cluster_separation
	var acc := Vector3.ZERO
	for i in range(nc):
		if nc > 8:
			var phi := acos(1.0 - 2.0 * (float(i) + 0.5) / float(nc))
			var th := PI * (1.0 + sqrt(5.0)) * float(i)
			acc += Vector3(sep * sin(phi) * cos(th), sep * sin(phi) * sin(th), sep * cos(phi))
		else:
			var angle := float(i) * PI * 2.0 / float(nc)
			acc += Vector3(sep * cos(angle), 0.0, sep * sin(angle))
	return acc / float(nc)


## Fibonacci-sphere direction (deterministic, de-resonant — the same
## distribution the multi-cluster placement uses; the multi-rung seeding's
## mode directions, CASCADE_GRID.md §3.3).
func _fib_sphere_dir(i: int, n: int) -> Vector3:
	var p := acos(1.0 - 2.0 * (float(i) + 0.5) / float(n))
	var t := PI * (1.0 + sqrt(5.0)) * float(i)
	return Vector3(sin(p) * cos(t), sin(p) * sin(t), cos(p))


## Close framing distance for the startup camera: the spawn extent
## (cluster-ring radius + per-cluster ball radius), so the region fills
## most of the vertical FOV.
func _camera_framing_radius() -> float:
	var nc := maxi(1, num_clusters)
	var ring_r: float = cluster_separation if nc > 1 else 0.0
	return maxf(maxf(ring_r, cluster_radius) + cluster_radius, 1.0)


## Point a sibling Camera3D at the spawn region (startup only, called from
## _ready). The camera sits at target + (0, 0.3R, 0.95R) — an oblique view
## at distance ≈ R with ~17° elevation — and look_at reorients it onto the
## centroid. Free-fly controls afterwards are unaffected (free_camera.gd
## only moves on input). No-op without a sibling Camera3D or when
## auto_frame_camera_on_start is off.
func _auto_frame_camera() -> void:
	if not auto_frame_camera_on_start:
		return
	var cam := _find_sibling_camera()
	if cam == null:
		return
	var target := _cluster_centroid()
	var r := _camera_framing_radius()
	cam.position = target + Vector3(0.0, 0.3 * r, 0.95 * r)
	cam.look_at(target, Vector3.UP)
	print("[CassiSim] Camera framed on spawn: target=(%.1f, %.1f, %.1f) R=%.1f pos=(%.1f, %.1f, %.1f)" % [
		target.x, target.y, target.z, r, cam.position.x, cam.position.y, cam.position.z])


## The sibling Camera3D in the same node group (main/recorder scenes);
## null in headless verify scenes. Cached once at _ready.
func _find_sibling_camera() -> Camera3D:
	var parent := get_parent()
	if parent == null:
		return null
	for child in parent.get_children():
		if child is Camera3D:
			return child
	return null


## Far limit: when the camera flies farther from the grid center (the box is
## origin-centered) than the visibility boundary, pull it back to just inside
## — the box's farthest corner then sits exactly on the camera's far plane.
## free_camera.gd's controls are untouched; this only moves the camera BACK,
## and only when it violates the limit.
func _enforce_camera_max_distance() -> void:
	if _sim_cam == null:
		return
	var max_d := _camera_max_distance()
	var d := _sim_cam.global_position.length()
	if d <= max_d or d < 1e-4:
		return
	_sim_cam.global_position = _sim_cam.global_position.normalized() * max_d


## 0 (AUTO) = the camera's far plane minus the grid's bounding-sphere radius
## (half-diagonal): the whole grid stays inside the far plane — just inside
## the visibility limit. Manual override via camera_max_distance.
func _camera_max_distance() -> float:
	if camera_max_distance > 0.0:
		return camera_max_distance
	var far: float = 4000.0
	if _sim_cam != null:
		far = _sim_cam.far
	return maxf(far - _extents().length(), 1.0)


# ── Meshless (Voronoi cell) arm — MESHLESS_PLAN.md §10 ─────────────────
# BCC site lattice in the mesh world [0, 2·extent)³, JFA construction,
# per-cell state sampled from the grid IC, steering + ALE remap between
# frames, and the raster back to the field buffers (see _step_dispatches).
# Anisotropic box: the BCC seed lattice, the JFA accelerator grid and the
# trilinear IC sampling all use the per-axis spacings hx/hy/hz =
# 2·extent_i/N (the stretched box [0, 2·extent_x) × ... × [0, 2·extent_z)).
func _meshless_init() -> void:
	var N = grid_N
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
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
	print("[CassiSim] Meshless arm ready: %d Voronoi cells on the %d³ accelerator grid"
		% [ml_ns, N])


func _ml_tri(a: PackedFloat32Array, i0: int, j0: int, k0: int,
		i1: int, j1: int, k1: int, fx: float, fy: float, fz: float) -> float:
	var N = grid_N
	var c00 := a[i0 * N * N + j0 * N + k0] * (1.0 - fx) + a[i1 * N * N + j0 * N + k0] * fx
	var c01 := a[i0 * N * N + j0 * N + k1] * (1.0 - fx) + a[i1 * N * N + j0 * N + k1] * fx
	var c10 := a[i0 * N * N + j1 * N + k0] * (1.0 - fx) + a[i1 * N * N + j1 * N + k0] * fx
	var c11 := a[i0 * N * N + j1 * N + k1] * (1.0 - fx) + a[i1 * N * N + j1 * N + k1] * fx
	var c0 := c00 * (1.0 - fy) + c10 * fy
	var c1 := c01 * (1.0 - fy) + c11 * fy
	return c0 * (1.0 - fz) + c1 * fz


func _ml_scatter_and_jfa() -> void:
	var N = grid_N
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
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
	# boundary cells on a STRETCHED box (the physical nearest site can sit
	# just outside the reachable neighborhood); repeating the complete-graph
	# jump-1 pass converges them to the exact Voronoi (0.0000 mislabel). At
	# the cube it is a no-op (the 11-pass flood is already exact). Two passes
	# keep the count odd so the identity copy B → A still re-homes the result.
	var jumps: Array[int] = [1, 2, 4, 8, 16, 32, 16, 8, 4, 2, 1, 1, 1]
	var read_a := 1
	for jp in jumps:
		_ml_jfa_pass(jp, read_a)
		read_a = 1 - read_a
	_ml_jfa_pass(0, 0)  # identity copy B → A (odd pass count leaves result in B)


func _ml_jfa_pass(jp: int, read_a: int) -> void:
	var N = grid_N
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
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


func _ml_volume_pass() -> void:
	var N = grid_N
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
	var zero := PackedFloat32Array()
	zero.resize(ml_ns)
	_rd.buffer_update(_ml_vol, 0, zero.size() * 4, zero.to_byte_array())
	_ml_cell_dispatch(2.0, N * N * N / 64)


func _ml_cell_pc(mode: float) -> PackedByteArray:

	var N = grid_N
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
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


func _mesh_rebuild() -> void:
	# The FULL GPU rebuild (the stutter fix): steering + ALE remap + JFA
	# refresh as ONE compute list with barriers — zero readbacks, zero
	# CPU loops, so the global RD never stalls. Chain: reset(vol+cen) →
	# centroid(OLD mesh) → steer(new sites + remap idx) → state→tmp →
	# tmp→state (the remap gather) → labels clear → scatter → JFA (the
	# ping-pong passes share this list) → volume.
	var N = grid_N
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
	var ext_rb := _extents()
	var hx_rb: float = 2.0 * ext_rb.x / float(N)
	var hy_rb: float = 2.0 * ext_rb.y / float(N)
	var hz_rb: float = 2.0 * ext_rb.z / float(N)
	var wg1 = N * N * N / 64
	var wgs = int(ceil(float(ml_ns) / 64.0))
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

	# Build the cluster records, then upload them to the GPU buffer.
	# ClusterBuf in cassi_nbody_gravity.glsl holds 64 records; truncate
	# loudly beyond the cap (previously the buffer was 20 vec4s and
	# num_clusters > 20 wrote past its end — "Attempted to write buffer
	# (16 bytes) past the end").
	var cluster_data = PackedFloat32Array()
	for c in range(nc):
		var cen = centers[c]
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
	var max_v: float = 0.0  # max initial speed — rainbow anchor: v_max/mean ratio sets v_scale
	var sum_v: float = 0.0  # Σ|v| over the IC — mean initial speed = rainbow v_ref

	# ── Hoisted per-particle constants ────────────────────────────────
	# The GDScript interpreter paid for these inside the N_particles loop
	# on EVERY particle (pow/div/sqrt/maxf native calls). All are
	# loop-invariant; the Salpeter draw, the IC inverse-CDF arms and the
	# enclosed-mass formulas below reference the hoisted forms.
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
		var i4 = i * 4
		var cidx = min(int(i / per_cluster), nc - 1)
		var center = centers[cidx]
		var bv = bulk_vels[cidx]

		# Salpeter IMF: dN/dM ∝ M^(-2.35), range [0.3, 30.0] M☉ (the two
		# pow()s and the reciprocal exponent are hoisted above the loop —
		# they were recomputed on every particle)
		var m = pow(salp_a - rng.randf() * (salp_a - salp_b), salp_inv)
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
			r = cluster_radius / sqrt(pow(u, minus_two_thirds) - 1.0)
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
			var z_max: float = r_max_eff * s2_inv
			if z_max <= 0.0:
				# Empty truncated support (r_max ≤ 0 — a cluster center
				# beyond the safe radius): every draw collapses to r = 0
				# exactly. Skip the bisection; the old path converged
				# z → 0 over 24 iterations of pure waste. Identical
				# result, same th/ph direction draws below.
				r = 0.0
			else:
				var u: float = rng.randf() * maxf(gauss_u_max_list[cidx], 1e-30)
				var z_lo := 0.0
				var z_hi: float = z_max
				# 16 iterations → bracket 2^-16 of z_max (≈1e-5 absolute
				# at z_max ~ 0.3) — far below any IC tolerance and ≪ the
				# fp32 position ulp at these magnitudes; the old 24 were
				# 2^-24 (fp32-exact) at 50% more exp() calls per particle.
				for _b in range(16):
					var z_m: float = 0.5 * (z_lo + z_hi)
					var f_m: float = _erf_approx(z_m) - two_over_sqrt_pi * z_m * exp(-z_m * z_m)
					if f_m < u:
						z_lo = z_m
					else:
						z_hi = z_m
				var z: float = 0.5 * (z_lo + z_hi)
				r = s2 * z
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
			var u_trunc: float = minf(1.0, pow(r_max_eff / a_s, 3.0))
			var u = rng.randf() * u_trunc
			r = a_s * pow(u, third)
			var th = acos(2.0 * rng.randf() - 1.0)
			var ph = rng.randf() * PI * 2.0
			lx = r * sin(th) * cos(ph)
			ly = r * sin(th) * sin(ph)
			lz = r * cos(th)
		pos[i4]     = lx + center.x
		pos[i4 + 1] = ly + center.y
		pos[i4 + 2] = lz + center.z

		# ── Multi-rung cascade seeding (CASCADE_GRID.md §3.3) ────────
		# Zel'dovich displacement δx = Σ_m (A/k_m)·sin(k_m·(d_m·x) + φ_m)·d_m
		# with φ-spaced wavenumbers k_m = 2π·φ^m/(base·R) and Fibonacci-sphere
		# directions — linear-order density power δρ/ρ = −∇·δx at several
		# cascade rungs, so bubbles condense at multiple scales at once.
		# Applied in WORLD space (the modes span the whole box); the
		# out-of-box check below uses the displaced positions.
		if multi_rung_seed and multi_rung_count > 0:
			var wx: float = pos[i4]
			var wy: float = pos[i4 + 1]
			var wz: float = pos[i4 + 2]
			var k_base: float = TAU / (multi_rung_base_scale * maxf(cluster_radius, 1e-6))
			for mr in range(multi_rung_count):
				var km: float = k_base * pow(PHI, float(mr))
				var d: Vector3 = _fib_sphere_dir(mr, multi_rung_count)
				var ph_m: float = float(mr) * (TAU / (PHI * PHI))  # golden angle per rung
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
		# Enclosed mass M(<r) per profile, all with G = 1 and the same
		# v_circ = 0.85·sqrt(M_enc/max(r, 0.01)) convention (r softened to
		# sqrt(r²+ε²) inside the enclosed-mass formulas, as the Plummer arm
		# already does via r2p).
		var r2p = r * r + eps2
		var M_enc: float = 0.0
		if initial_condition == 0:
			# Plummer enclosed mass M(<r) = M·r³/(r²+a²)^(3/2)
			M_enc = float(per_cluster) * (r2p * r) / ((r2p + a2) * sqrt(r2p + a2))
		elif initial_condition == 1:
			# Gaussian M(<r) = M·[erf(z) − (2/√π)·z·e^(−z²)], z = r/(√2·σ),
			# r = the softened sqrt(r2p); erf via A&S 7.1.26 (_erf_approx —
			# this Godot 4.7 install has no built-in erf()).
			var z: float = sqrt(r2p) * s2_inv
			M_enc = float(per_cluster) * (_erf_approx(z) - two_over_sqrt_pi * z * exp(-z * z))
		else:
			# Uniform M(<r) = M·min(1, (r/a)³) (fully enclosed at r ≥ a)
			M_enc = float(per_cluster) * minf(1.0, pow(sqrt(r2p) / a_s, 3.0))
		var v_circ = sqrt(G * M_enc / max(r, 0.01)) * initial_v_circ_factor
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
		var vs := sqrt(vel[i4]*vel[i4] + vel[i4+1]*vel[i4+1] + vel[i4+2]*vel[i4+2])
		max_v = maxf(max_v, vs)
		sum_v += vs


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
		# Transform: 3x4 row-major (each row = [basis, origin_component])
		# Row 0 = X-axis + origin.x, Row 1 = Y-axis + origin.y, Row 2 = Z-axis + origin.z
		init_inst[b+0] = 1.0; init_inst[b+1] = 0.0; init_inst[b+2] = 0.0; init_inst[b+3] = x
		init_inst[b+4] = 0.0; init_inst[b+5] = 1.0; init_inst[b+6] = 0.0; init_inst[b+7] = y
		init_inst[b+8] = 0.0; init_inst[b+9] = 0.0; init_inst[b+10] = 1.0; init_inst[b+11] = z
		# Color: replicate the instancer shader for the SELECTED mode so the
		# paused (playing=false) view equals the first played frame. Modes 1-3
		# (the consolidated gradient engine) render frame-0 via the one-shot
		# GPU _repaint_instancer() at the end of _ready — the CPU path cannot
		# sample the field cheaply — so only mode 0 keeps a CPU color pass.
		if particle_color_mode == 0:
			# Shader-exact Cassi mass gradient: log_m = clamp((log2(m)+2)·0.25)
			var m: float = pos[i4 + 3]
			var log_m: float = clampf((log(m) / log(2.0) + 2.0) * 0.25, 0.0, 1.0)
			var cr: float = lerp(0.15, 1.0,  log_m * log_m)
			var cg: float = lerp(0.25, 0.6,  log_m)
			var cb: float = lerp(1.0,  0.15, log_m)
			init_inst[b+12] = cr; init_inst[b+13] = cg; init_inst[b+14] = cb; init_inst[b+15] = 1.0
		else:
			# Rainbow modes (1/2/3): PLACEHOLDER — the shader computes the
			# colors from the uploaded pos/vel/q buffers in the one-shot
			# _repaint_instancer() at the end of _ready (the CPU path cannot
			# sample the field cheaply). This buffer upload happens first, so
			# the repaint overwrites the colors before the first frame draws.
			init_inst[b+12] = 0.5; init_inst[b+13] = 0.5; init_inst[b+14] = 0.5; init_inst[b+15] = 1.0
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
	# Velocity-rainbow anchors (log-compressed, distribution-anchored):
	#   v_ref  = mean initial |v|          (the hue mid-point: h(v_ref) ≈ 0.4-0.5)
	#   v_scale = 0.95 / ln(1 + v_max/v_ref)  (fastest particle → h = 0.95, magenta-pink)
	#   v_max  = max initial |v| — the consolidated engine's AUTO cycle top
	# h = v_scale·ln(1+|v|/v_ref): slow → h→0 (red), and hue drifts only
	# LOGARITHMICALLY under velocity growth — a speed-up no longer pins the
	# field at the top of the ramp (the linear |v|/(|v|+v_ref) saturation bug).
	# Degenerate zero-speed IC: v_ref = 1.0, v_scale = 0.95·ln2 (smooth small-v
	# ramp instead of a division hazard); the engine maps the degenerate
	# v_max ≈ 0 to the band [0, 1.0] with ref = 1.0.
	var mean_v: float = sum_v / float(N_particles) if N_particles > 0 else 0.0
	_rainbow_vmax = max_v
	if max_v > 0.0 and mean_v > 0.0:
		_rainbow_vref = mean_v
		_rainbow_vscale = 0.95 / log(1.0 + max_v / mean_v)
	else:
		_rainbow_vref = 1.0
		_rainbow_vscale = 0.95 * LN2
	# Retained fraction = analytic fraction of the UNBOUNDED profile kept
	# inside the truncation, per profile (min over clusters, like the old
	# Plummer u_max minimum):
	#   Plummer:  u_max = (x²/(1+x²))^{3/2}, x = r_max/a
	#   Gaussian: erf(z_max) − (2/√π)·z_max·e^(−z_max²), z_max = r_max/(√2·σ)
	#   Uniform:  min(1, (r_max/a)³)
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


# ── Consolidated gradient engine (shared composer) ────────────────────
# The engine constants (one segmented-ramp mapping for both rainbow
# sources) are computed by _fill_instancer_pc each fill, persisted to
# _engine_c, and exposed to the UI's gradient legend via gradient_engine()
# — ONE source of truth, so the legend's strip renders EXACTLY the GPU
# instancer colors (same composer, same evaluator math). Index map (17
# floats; the instancer PC slots 12-27 + hue_offset).
const E_PROG: int = 0
const E_REF: int = 1
const E_LO1: int = 2
const E_SLOPE1: int = 3
const E_LO2: int = 4
const E_SLOPE2: int = 5
const E_OFF2: int = 6
const E_LO3: int = 7
const E_SLOPE3: int = 8
const E_OFF3: int = 9
const E_HIC: int = 10
const E_SPAN: int = 11
const E_ALO: int = 12
const E_AHI: int = 13
const E_TOP: int = 14   # approach hue at the white point (pink 0.93 — no red at high coherence)
const E_APPROACH_ON: int = 15
const E_HUE_OFF: int = 16
var _engine_c: PackedFloat32Array = PackedFloat32Array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0])


## Current gradient-engine constants (17 floats; E_* indices), recomputed
## from the live exports — the UI gradient legend renders from these so it
## matches the GPU instancer exactly (same composer, same evaluator).
func gradient_engine() -> PackedFloat32Array:
	_fill_instancer_pc()   # recompute (idempotent; also re-encodes the PC bytes)
	return _engine_c


func _fill_instancer_pc() -> void:
	# Consolidated gradient engine PC (32 floats = 128 B — see the instancer
	# shader header for the slot map): the shared 11 + the engine block
	# (slots 11-31). One segmented-ramp composer serves BOTH rainbow sources:
	# the scalar axis x (velocity: speed; Qi: coherence q) is partitioned
	# into up to 3 CYCLE segments [lo1,lo2],[lo2,lo3],[lo3,hiC] (the pinch
	# split concentrates hue gradient where most particles sit; pinch OFF ⇒
	# one segment) plus the APPROACH band (a_lo → a_hi, the
	# count-invariant white-hot stage). Per-segment hue SHARES allocate each
	# pass's hue budget; count C = the number of hue passes over the cycle
	# band. Progress is LOG per segment (multiplicative physics — the pinch
	# band is the narrowest log interval, intrinsically steepest); the
	# approach is LINEAR (violet 0.8 at a_lo → pink 0.93 at a_hi — no red at
	# high coherence; lightness 0.5 → 1.0).
	# H_CYCLE = 1.0 (Qi) / 0.95
	# (velocity — the legacy full-circle top, held with no wrap).
	# Derivation reads the LIVE exports (particle_color_mode, rainbow_count,
	# color_shares, color_progress, qi_cycle/pinch/approach/gate,
	# qi_approach_tracks_threshold, velocity_cycle/pinch/approach,
	# color_hue_offset, qi_condensation_threshold) + the measured velocity
	# anchors each fill, so a UI flip applies on the next dispatch (no
	# reinit). Validation: count > 8 clamps, an inverted/empty cycle falls
	# back to the canonical band, an inverted pinch/approach turns off
	# (one-shot warnings per misuse).
	var ext_pc: Vector3 = _extents()
	_instancer_pc_bytes.encode_float(0, float(grid_N))
	_instancer_pc_bytes.encode_float(4, dt)
	_instancer_pc_bytes.encode_float(8, _time)
	_instancer_pc_bytes.encode_float(12, PHI)
	_instancer_pc_bytes.encode_float(16, xi)
	_instancer_pc_bytes.encode_float(20, softening * softening)
	_instancer_pc_bytes.encode_float(24, float(N_particles))
	_instancer_pc_bytes.encode_float(28, float(mode))
	_instancer_pc_bytes.encode_float(32, source_strength)
	_instancer_pc_bytes.encode_float(36, float(num_clusters))
	_instancer_pc_bytes.encode_float(40, float(gravity_mode))
	# ── DEPTH_CUE camera source (particle-VFX, default-off) ──────────
	# The instancer shader reads slots 8/9/10 (shared source_strength /
	# num_clusters / gravity_mode) as the CAMERA world position ONLY when
	# the 0x40 depth flag is set — none of those shared values are consumed
	# by the instancer's color/size paths, so repurposing them here is
	# bit-identical at defaults. A sibling Camera3D (main/recorder) feeds
	# the live camera; the headless verify scenes have none → origin fallback
	# (the shader's own origin-probe when the depth flag is on).
	var _cam_p: Vector3 = _sim_cam.global_position if _sim_cam != null else Vector3.ZERO
	_instancer_pc_bytes.encode_float(32, _cam_p.x)
	_instancer_pc_bytes.encode_float(36, _cam_p.y)
	_instancer_pc_bytes.encode_float(40, _cam_p.z)
	_instancer_pc_bytes.encode_float(44, float(particle_color_mode))  # slot 11
	if particle_color_mode == 0:
		# Mode 0 = Cassi mass gradient — the shader branch is untouched; the
		# whole engine block (slots 12-31) is zeroed (nothing reads it).
		for slot in range(48, 128, 4):
			_instancer_pc_bytes.encode_float(slot, 0.0)
		_engine_c.fill(0.0)   # keep the shared engine cache consistent
		return
	# ── engine derivation (modes 1/2/3) ──────────────────────────────
	var is_qi: bool = particle_color_mode >= 2
	# pass count: rainbow_count 0 = AUTO (mode 3 → 2, else 1); explicit 1-8
	var count: int = rainbow_count
	if count > 8:
		if not _warned_rainbow_count:
			_warned_rainbow_count = true
			push_warning("[CassiSim] rainbow_count=%d > 8 — clamped to 8" % count)
		count = 8
	if count <= 0:
		count = 2 if particle_color_mode == 3 else 1
	var h_cycle: float = 1.0 if is_qi else 0.95   # H_CYCLE (Qi full circle / velocity 0.95 top)
	var prog: float = float(color_progress)       # 0 = log (default), 1 = linear
	var ref: float = 0.0
	var lo1: float = 0.0
	var hi_c: float = 0.0
	var pinch := Vector2.ZERO
	var a_lo: float = 0.0
	var a_hi: float = 0.0
	var approach_on: float = 0.0
	if is_qi:
		# Qi: cycle band [qi_cycle] (calibrated default 2e-4 → 1e-3), pinch
		# [qi_pinch], shares [color_shares]; approach [qi_approach] with the
		# white point = the LIVE qi_condensation_threshold (tracks_threshold).
		ref = 0.0
		lo1 = qi_cycle.x
		hi_c = qi_cycle.y
		pinch = qi_pinch
		if lo1 >= hi_c:
			if not _warned_qi_cycle:
				_warned_qi_cycle = true
				push_warning("[CassiSim] qi_cycle (%g, %g) inverted/empty — using the calibrated band (2e-4, 1e-3)" % [lo1, hi_c])
			lo1 = Q_FLOOR
			hi_c = Q_1
		a_lo = qi_approach.x
		a_hi = qi_approach.y
		if qi_approach_tracks_threshold:
			a_hi = qi_condensation_threshold
		if a_lo < a_hi:
			approach_on = 1.0
			a_hi = maxf(a_hi, a_lo * 1.001)   # verbatim guard (white point above the entry)
	else:
		# Velocity: cycle band [velocity_cycle] or AUTO = [0, v_max] measured at
		# init, ref = v_ref (mean init |v|); degenerate zero-speed IC → band
		# [0, 1.0] with ref = 1.0. Optional approach [velocity_approach].
		ref = maxf(_rainbow_vref, 1e-6)
		pinch = velocity_pinch
		if velocity_cycle == Vector2.ZERO:
			lo1 = 0.0
			if _rainbow_vmax <= 1e-9:
				hi_c = 1.0
				ref = 1.0
			else:
				hi_c = _rainbow_vmax
		else:
			lo1 = velocity_cycle.x
			hi_c = velocity_cycle.y
			if lo1 >= hi_c:
				if not _warned_vel_cycle:
					_warned_vel_cycle = true
					push_warning("[CassiSim] velocity_cycle (%g, %g) inverted/empty — using the measured auto band" % [lo1, hi_c])
				lo1 = 0.0
				hi_c = _rainbow_vmax if _rainbow_vmax > 1e-9 else 1.0
		a_lo = velocity_approach.x
		a_hi = velocity_approach.y
		if a_lo < a_hi:
			approach_on = 1.0
	# degenerate guard: a cycle band with hiC ≤ lo1 collapses to a sliver
	if hi_c <= lo1:
		hi_c = lo1 * 1.001
	# ── segments + shares ───────────────────────────────────────────
	# The pinch controls are user-editable, so keep their active interval
	# inside the cycle band before taking logarithms. A scene may specify a
	# convenient lower bound of zero even though the Qi cycle starts at the
	# calibrated floor; using the raw zero would create log(q / 0) = NaN and
	# paint the entire legend black.
	var pinch_lo: float = clampf(pinch.x, lo1, hi_c)
	var pinch_hi: float = clampf(pinch.y, lo1, hi_c)
	var pinch_on: bool = pinch.x < pinch.y and pinch_hi - pinch_lo > 1e-9
	# The hue shares are clamped ≥ 0 and normalized over the active segments;
	# a non-positive sum forces pinch OFF with (1, 0, 0).
	var sh := Vector3(maxf(color_shares.x, 0.0), maxf(color_shares.y, 0.0), maxf(color_shares.z, 0.0))
	if not pinch_on or sh.x + sh.y + sh.z <= 0.0:
		pinch_on = false
		sh = Vector3(1.0, 0.0, 0.0)
	else:
		var ssum: float = sh.x + sh.y + sh.z
		sh /= ssum
	var lo2: float = hi_c
	var lo3: float = hi_c
	if pinch_on:
		lo2 = pinch_lo
		lo3 = pinch_hi
	var span: float = h_cycle * float(count)   # span_total = H_CYCLE·C
	# segment widths: log mode (multiplicative physics) or linear mode
	var w1: float = log((lo2 + ref) / (lo1 + ref)) if color_progress == 0 else lo2 - lo1
	var w2: float = log((lo3 + ref) / (lo2 + ref)) if color_progress == 0 else lo3 - lo2
	var w3: float = log((hi_c + ref) / (lo3 + ref)) if color_progress == 0 else hi_c - lo3
	var slope1: float = span * sh.x / maxf(w1, 1e-9)
	var slope2: float = span * sh.y / maxf(w2, 1e-9)
	var slope3: float = span * sh.z / maxf(w3, 1e-9)
	var off2: float = span * sh.x
	var off3: float = span * (sh.x + sh.y)
	# ── persist the engine constants (shared with the UI gradient legend) ──
	_engine_c[E_PROG] = prog
	_engine_c[E_REF] = ref
	_engine_c[E_LO1] = lo1
	_engine_c[E_SLOPE1] = slope1
	_engine_c[E_LO2] = lo2
	_engine_c[E_SLOPE2] = slope2
	_engine_c[E_OFF2] = off2
	_engine_c[E_LO3] = lo3
	_engine_c[E_SLOPE3] = slope3
	_engine_c[E_OFF3] = off3
	_engine_c[E_HIC] = hi_c
	_engine_c[E_SPAN] = span
	_engine_c[E_ALO] = a_lo
	_engine_c[E_AHI] = a_hi
	_engine_c[E_TOP] = 0.93  # approach top hue = pink — red never appears at high coherence
	_engine_c[E_APPROACH_ON] = approach_on
	_engine_c[E_HUE_OFF] = color_hue_offset
	# ── encode slots 12-31 ──
	_instancer_pc_bytes.encode_float(48, _engine_c[E_PROG])          # 12 prog_mode
	_instancer_pc_bytes.encode_float(52, _engine_c[E_REF])           # 13 ref
	_instancer_pc_bytes.encode_float(56, _engine_c[E_LO1])           # 14
	_instancer_pc_bytes.encode_float(60, _engine_c[E_SLOPE1])        # 15
	_instancer_pc_bytes.encode_float(64, _engine_c[E_LO2])           # 16
	_instancer_pc_bytes.encode_float(68, _engine_c[E_SLOPE2])        # 17
	_instancer_pc_bytes.encode_float(72, _engine_c[E_OFF2])          # 18
	_instancer_pc_bytes.encode_float(76, _engine_c[E_LO3])           # 19
	_instancer_pc_bytes.encode_float(80, _engine_c[E_SLOPE3])        # 20
	_instancer_pc_bytes.encode_float(84, _engine_c[E_OFF3])          # 21
	_instancer_pc_bytes.encode_float(88, _engine_c[E_HIC])           # 22
	_instancer_pc_bytes.encode_float(92, _engine_c[E_SPAN])          # 23
	_instancer_pc_bytes.encode_float(96, _engine_c[E_ALO])           # 24
	_instancer_pc_bytes.encode_float(100, _engine_c[E_AHI])          # 25
	_instancer_pc_bytes.encode_float(104, _engine_c[E_TOP])           # 26
	_instancer_pc_bytes.encode_float(108, _engine_c[E_APPROACH_ON])  # 27
	_instancer_pc_bytes.encode_float(112, ext_pc.x)                  # 28
	_instancer_pc_bytes.encode_float(116, ext_pc.y)                  # 29
	_instancer_pc_bytes.encode_float(120, ext_pc.z)                  # 30
	_instancer_pc_bytes.encode_float(124, _engine_c[E_HUE_OFF])      # 31 hue_offset (rotates the cycle start)


func _repaint_instancer() -> void:
	# One-shot GPU repaint of the multimesh instance buffer from the CURRENT
	# pos/vel buffers — used when paused (playing=false), where
	# _step_dispatches never runs, so a live color-mode flip repaints the
	# visible instances immediately. Precedent: _render_field_slice / the
	# BH-lensing path — a standalone compute list on the global RD, no
	# submit/sync (illegal on the main instance).
	if _rd == null or not _instancer_shader.is_valid() or not _us_inst_0.is_valid() or N_particles <= 0:
		return
	if not _mm_rd_rid.is_valid(): return
	_fill_instancer_pc()
	var pg = ceili(float(N_particles) / 256.0)
	var cl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _instancer_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_inst_0, 0)
	_rd.compute_list_set_push_constant(cl, _instancer_pc_bytes, _instancer_pc_bytes.size())
	_rd.compute_list_dispatch(cl, pg, 1, 1)
	_rd.compute_list_end()


func _step_dispatches(cl: int) -> void:
	_time += dt
	_step_count += 1

	var ext_step: Vector3 = _extents()  # per-axis box half-extents (PCs + bh header)

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

	# Two-fluid PC (dedicated 56 B): the shared 11 fields + the 3 per-axis
	# extents (the anisotropic 19-point stencil needs h_i = 2·extent_i/N —
	# the dedicated-PC precedent: the shared _pc_bytes stays at 11 floats
	# for field_render/instancer/bh_lensing).
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
	# Effective gravity mode: when the meshless TREE arm is live, force the
	# nbody shader to the tree path (mode 5) regardless of the EXPORTED
	# `gravity_mode` (which stays 0 for the default/battery bit-identical
	# contract). Otherwise the shader encodes gravity_mode=0 and runs the
	# RIVER arm sampling the (never-written, since the ∇(g·Φ) gradient pass
	# is skipped under the tree arm) _grad_buf → zero force. The tree
	# build/walk writes _ml_tree_grad; only this encode gates whether the
	# nbody consumes it. nbody-only: the two-fluid/field/instancer passes do
	# not branch on gravity_mode.
	var eff_gmode: float = 5.0 if (meshless_mode and meshless_gravity) else float(gravity_mode)
	_nbody_pc_bytes.encode_float(40, eff_gmode)
	_nbody_pc_bytes.encode_float(44, 0.0)  # pass_mode = 0 (particles)
	_nbody_pc_bytes.encode_float(48, realsim_drag)
	_nbody_pc_bytes.encode_float(52, realsim_viscosity)
	_nbody_pc_bytes.encode_float(56, realsim_friction)

	# Mass deposit PC: [N_f, particle_N, extent_x/y/z, off_x/y/z] — the
	# offsets are encoded per dispatch (0 for the base lattice; the dual
	# offset h_i/2 = extent_i/N for the shifted chain, CASCADE_GRID.md).
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

	# 1.5. Spectral Poisson solve: ∇²Φ = ρ_mass (Φ̂ = −ρ̂/k², k=0 nulled) ──
	# RIVER MODES ONLY (0, 3 and 4): the heuristic and Plummer-reference arms
	# consume neither Φ nor ∇(g·Φ) — skipping the 7-pass FFT chain is their
	# main step-cost win. The clear+deposit+PDE chain above still runs so
	# ρ/q remain the visual/source state (the PDE's injection reads ρ).
	# SKIPPED under tree gravity too (meshless_gravity && meshless_mode) —
	# the octree replaces the spectral solve (fmm_design.md Q6).
	if (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) \
			and not (meshless_mode and meshless_gravity):
		_dispatch_poisson(cl)
	_barrier(cl)  # deposit → PDE (rho visibility for the PDE source)

	# ── 2. Two-fluid PDE — grid solver, or the meshless Voronoi arm ──
	# freeze_field (diagnostic): the field is initialized once and left
	# fixed — the PDE evolution passes are skipped while the gravity/
	# particle path (deposit, Poisson, gradient, KDK) runs unchanged.
	# FieldVel stays at its init value (zeros), so RealSim's viscosity
	# sees a consistently frozen medium.
	if meshless_mode and _ml_ready and _cell_pipe.is_valid() and not freeze_field:
		# Meshless (MESHLESS_PLAN.md §10): cell lap + leapfrog on the
		# Voronoi mesh, then rasterize the cell state back into the grid
		# field buffers (the render/condensation/river chain reads them
		# unchanged). The accelerator grid is a lookup accelerator only.
		var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
		var wg1 = grid_N * grid_N * grid_N / 64
		_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
		_cell_pc_bytes = _ml_cell_pc(0.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
		_barrier(cl)  # lap → leapfrog
		_cell_pc_bytes = _ml_cell_pc(1.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, int(ceil(float(ml_ns) / 64.0)), 1, 1)
		_barrier(cl)  # leapfrog → raster
		_rd.compute_list_bind_compute_pipeline(cl, _raster_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_raster_0, 0)
		_raster_pc_bytes = PackedFloat32Array([float(grid_N), float(ml_ns),
			0.0, 0.0, 0.0, 0.0, 0.0, 0.0]).to_byte_array()
		_rd.compute_list_set_push_constant(cl, _raster_pc_bytes, _raster_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
	elif _two_fluid_shader.is_valid() and not freeze_field:
		_rd.compute_list_bind_compute_pipeline(cl, _two_fluid_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_two_0, 0)
		_rd.compute_list_set_push_constant(cl, _two_fluid_pc_bytes, _two_fluid_pc_bytes.size())
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
	# mode 0. SKIPPED under tree gravity (the walk produces ∇Φ_g directly).
	if (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) \
			and not (meshless_mode and meshless_gravity) and _nbody_shader.is_valid():
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

	# ── 2.85. Dual (Yin/Yang) lattice chain (CASCADE_GRID.md) ──────────
	# The SAME deposit → Poisson → gradient chain on the half-cell-shifted
	# partner lattice; the river arm averages the two ∇(g·Φ) samples (the
	# interleaved pair is the BCC lattice). The k-space symbol is
	# translation-invariant, so only the deposit and gradient world maps
	# carry the offset — the Poisson FFT chain itself is unchanged. Runs
	# AFTER the PDE (the shifted gradient samples the same post-PDE field
	# at shifted cell centers). River modes only, gated on dual_grid. SKIPPED
	# under tree gravity (the tree is already isotropic — no BCC partner).
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
	_barrier(cl)  # end-of-step visibility (nbody writes → next step / frame-end instancer)


# ── Meshless TREE gravity: build + walk INTO the frame's compute list ──
# The tree replaces the spectral-Poisson river chain under the
# meshless_gravity && meshless_mode toggle. It appends its chain (gather →
# bitonic → BFS split → moments → walk) to the frame's ONE compute list
# `cl`, BEFORE the per-step loop, so mode-5 nbody reads a fresh
# _ml_tree_grad across the frame's steps. Per-frame (not per-step) refresh
# is the deliberate integration: the frame loop lives in ONE global-RD
# compute list with no CPU syncs (the codebase's stutter-fix idiom), and
# the global RD forbids host submit/sync from the main instance, so the
# tree MUST run inside the renderer's list. The split is SELF-CONTAINED
# (cassi_tree_build.glsl mode 5/8 — no host level readbacks), so the whole
# chain runs in-list with barriers only; 0 CPU stalls. The sites themselves
# are only rebuilt every ML_REBUILD steps, so a per-frame tree gradient is
# well matched to the mesh cadence. Ordering (field → g → tree → walk, Q3):
# the gather reads the mesh sites' post-PDE (EY,EI) + the deposit's ρ_mass;
# the walk runs only after the full build (all barriers in-list), and the
# nbody pass (mode 5) reads _ml_tree_grad after a barrier.
#
# PC layouts (dedicated buffers, both ≤ 128 B):
#   build (19 f)  N_f, bmin.xyz, bhalf, eps2, phi, xi, leaf_cap, max_levels,
#                 mode, b_k, b_j, b_m, grid_N, ext.xyz, field_floor
#   walk (5 f)    N_f, theta, eps2, use_tp(1 = _pos_buf targets), node_cnt
func _dispatch_tree_gravity(cl: int) -> void:
	# LOUD guards (2026-08-13, fresh-eyes finding): Godot SILENTLY no-ops a
	# compute dispatch whose uniform set is absent or incomplete (<-> no
	# error), so every reason to skip here is named explicitly. Each runs
	# once for diagnosis and keeps the skip.
	if _ml_tree_nsrc <= 0:
		push_error("[CassiSim] tree-gravity SKIP: _ml_tree_nsrc=%d <= 0 (no meshless sources)"
			% int(_ml_tree_nsrc))
		return
	if not _tree_build_pipe.is_valid():
		push_error("[CassiSim] tree-gravity SKIP: _tree_build_pipe invalid (tree-build shader failed to load/compile?)")
		return
	if not _tree_grav_pipe.is_valid():
		push_error("[CassiSim] tree-gravity SKIP: _tree_grav_pipe invalid (tree-walk shader failed to load/compile?)")
		return
	if not _us_tree_build.is_valid():
		push_error("[CassiSim] tree-gravity SKIP: _us_tree_build uniform set invalid (Godot would silently no-op this dispatch)")
		return
	if not _us_tree_grav.is_valid():
		push_error("[CassiSim] tree-gravity SKIP: _us_tree_grav uniform set invalid (Godot would silently no-op the walk)")
		return
	if not _ml_ready:
		push_error("[CassiSim] tree-gravity SKIP: _ml_ready false (meshless init not complete)")
		return
	var N_src = _ml_tree_nsrc
	var Np = maxi(N_particles, 1)
	var pg_src = ceili(float(N_src) / 64.0)
	var ext = _extents()
	var half: float = maxf(ext.x, maxf(ext.y, ext.z)) * 1.000001
	var bp = _tree_build_pc_bytes
	# constant build fields — root cube covers the sites ([0, 2·extent)³):
	# bmin = (0,0,0), bhalf = max(extent) → box [0, 2·half] ⊇ every site.
	bp.encode_float(0, float(N_src))
	bp.encode_float(1, 0.0); bp.encode_float(2, 0.0); bp.encode_float(3, 0.0)
	bp.encode_float(4, half)
	bp.encode_float(5, ML_TREE_EPS2)
	bp.encode_float(6, PHI)
	bp.encode_float(7, PHI_6)
	bp.encode_float(8, float(ML_TREE_LEAF_CAP))
	bp.encode_float(9, float(ML_TREE_MAX_LEVELS))
	bp.encode_float(14, float(grid_N))
	bp.encode_float(15, ext.x); bp.encode_float(16, ext.y); bp.encode_float(17, ext.z)
	bp.encode_float(18, ML_TREE_FIELD_FLOOR)
	var wp = _tree_grav_pc_bytes
	wp.encode_float(0, float(Np))
	wp.encode_float(1, ML_TREE_THETA)
	wp.encode_float(2, ML_TREE_EPS2)
	wp.encode_float(3, 1.0)  # use_tp — read particle positions (_pos_buf)
	wp.encode_float(4, float(ML_TREE_NODE_MAX_MULT * N_src + 64))  # bound (unused by walk)

	_rd.compute_list_bind_compute_pipeline(cl, _tree_build_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_tree_build, 0)

	# 0a. root seed (mode 10) + counter reset (mode 9) ON THE GPU — replaces
	# the removed per-frame host buffer_update of _ml_tree_ctr/cf/r. No
	# pre-list CPU buffer traffic for the tree arm. One thread each.
	bp.encode_float(10, 10.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	bp.encode_float(10, 9.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, 1, 1, 1)
	_rd.compute_list_add_barrier(cl)

	# 1. gather (mode 7) — source table from the meshless sites + chord/Morton
	bp.encode_float(10, 7.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, pg_src, 1, 1)
	_rd.compute_list_add_barrier(cl)

	# 2. bitonic sort (91 stages, in-list barriers)
	var k := 2
	while k <= N_src:
		var j := k >> 1
		while j >= 1:
			bp.encode_float(10, 1.0)
			bp.encode_float(11, float(k))
			bp.encode_float(12, float(j))
			bp.encode_float(13, 1.0)
			_rd.compute_list_set_push_constant(cl, bp, bp.size())
			_rd.compute_list_dispatch(cl, pg_src, 1, 1)
			_rd.compute_list_add_barrier(cl)
			j = j >> 1
		k = k << 1
	_rd.compute_list_add_barrier(cl)  # sorted order → split

	# 3. self-contained BFS split: MAX_LEVELS × [mode 5 split → mode 8 commit]
	var tnm: int = ML_TREE_NODE_MAX_MULT * N_src + 64
	var pg_all = ceili(float(tnm) / 64.0)
	for _depth in range(ML_TREE_MAX_LEVELS):
		bp.encode_float(10, 5.0)
		_rd.compute_list_set_push_constant(cl, bp, bp.size())
		_rd.compute_list_dispatch(cl, pg_all, 1, 1)
		_rd.compute_list_add_barrier(cl)
		bp.encode_float(10, 8.0)
		_rd.compute_list_set_push_constant(cl, bp, bp.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)

	# 4. moments (mode 6) — self-clips to ctr[0] (no host count needed)
	bp.encode_float(10, 6.0)
	_rd.compute_list_set_push_constant(cl, bp, bp.size())
	_rd.compute_list_dispatch(cl, pg_all, 1, 1)
	_rd.compute_list_add_barrier(cl)

	# 5. walk — one thread per PARTICLE (_pos_buf targets via use_tp)
	_rd.compute_list_bind_compute_pipeline(cl, _tree_grav_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_tree_grav, 0)
	_rd.compute_list_set_push_constant(cl, wp, wp.size())
	_rd.compute_list_dispatch(cl, ceili(float(Np) / 64.0), 1, 1)
	_rd.compute_list_add_barrier(cl)


# ── TREE-GRAVITY LOCAL-RD FALLBACK (2026-08-13) ─────────────────────────
# The in-sim tree arm. The global RD won't execute the tree shaders from the
# sim's _process loop (verified to the last rung), so we build + walk the
# tree on a LOCAL RenderingDevice — the path verify_meshless_gravity PROVES
# works (node_count=11963, G30 med=1.22e-5 / G31 PASS) — then read the
# per-particle gradient back and re-upload it to the global `_ml_tree_grad`
# for the mode-5 nbody arm.
#
# Cost (documented): one host round trip per cadence frame — read nsrc×16
# (sites) + nsrc×4 (ψy, ψi, vol) + N³×4 (ρ) + Np×16 (pos) from the global RD,
# upload them to the local RD, submit+sync the build+walk, read back Np×16
# (gradient), upload to the global `_ml_tree_grad`. ~800 KB/frame @N=64 /
# ~150 KB @N=32. `_tree_local_cadence` (default 1 = every frame) can throttle
# to every other frame for cheaper but temporally-coarser forces.
func _dispatch_tree_gravity_local() -> void:
	if not _ml_ready or _ml_tree_nsrc <= 0:
		return
	if not _tl_local_ready:
		_tree_local_setup()
		if not _tl_local_ready:
			push_error("[CassiSim] tree local-RD setup failed")
			return
	_tl_frame += 1
	if _tree_local_cadence > 1 and _tl_frame % _tree_local_cadence != 1:
		return  # skip this frame (stale-but-recent gradient is fine for 1/K)
	var S := _ml_tree_nsrc
	var N3 := grid_N * grid_N * grid_N
	var Np: int = N_particles
	var ext := _extents()
	var half: float = maxf(ext.x, maxf(ext.y, maxf(ext.z, ext.z))) * 1.000001
	# ── host round trip #1: pull the sim's CURRENT meshless source state ──
	var sites: PackedFloat32Array = _rd.buffer_get_data(_ml_sites, 0, S * 16).to_float32_array()
	var psy: PackedFloat32Array = _rd.buffer_get_data(_ml_psi_y, 0, S * 4).to_float32_array()
	var psi: PackedFloat32Array = _rd.buffer_get_data(_ml_psi_i, 0, S * 4).to_float32_array()
	var vol: PackedFloat32Array = _rd.buffer_get_data(_ml_vol, 0, S * 4).to_float32_array()
	var rho: PackedFloat32Array = _rd.buffer_get_data(_mass_density_buf, 0, N3 * 4).to_float32_array()
	var pos: PackedFloat32Array = _rd.buffer_get_data(_pos_buf, 0, Np * 16).to_float32_array()
	_tlrd.buffer_update(_tl_sites, 0, sites.size() * 4, sites.to_byte_array())
	_tlrd.buffer_update(_tl_psy, 0, psy.size() * 4, psy.to_byte_array())
	_tlrd.buffer_update(_tl_psi, 0, psi.size() * 4, psi.to_byte_array())
	_tlrd.buffer_update(_tl_vol, 0, vol.size() * 4, vol.to_byte_array())
	_tlrd.buffer_update(_tl_rho, 0, rho.size() * 4, rho.to_byte_array())
	_tlrd.buffer_update(_tl_tpos, 0, pos.size() * 4, pos.to_byte_array())
	# seed the self-contained counters + root (host seed is FINE on the
	# local RD — no global-RD cross-list race here)
	_tlrd.buffer_update(_tl_ctr, 0, 32, PackedInt32Array([1, 0, 1, 0, 0, 0, 0, 0]).to_byte_array())
	_tlrd.buffer_update(_tl_cf, 0, 16, PackedFloat32Array([ext.x, ext.y, ext.z, half]).to_byte_array())
	_tlrd.buffer_update(_tl_nr, 0, 16, PackedInt32Array([0, S, -1, 0]).to_byte_array())
	var tnm: int = ML_TREE_NODE_MAX_MULT * S + 64
	var bpc := PackedFloat32Array(); bpc.resize(19)
	bpc[0] = float(S); bpc[1] = 0.0; bpc[2] = 0.0; bpc[3] = 0.0; bpc[4] = half
	bpc[5] = ML_TREE_EPS2; bpc[6] = PHI; bpc[7] = PHI_6
	bpc[8] = float(ML_TREE_LEAF_CAP); bpc[9] = float(ML_TREE_MAX_LEVELS)
	bpc[14] = float(grid_N); bpc[15] = ext.x; bpc[16] = ext.y; bpc[17] = ext.z
	bpc[18] = ML_TREE_FIELD_FLOOR
	var gpc := PackedFloat32Array(); gpc.resize(5)
	gpc[0] = float(Np); gpc[1] = ML_TREE_THETA; gpc[2] = ML_TREE_EPS2; gpc[3] = 1.0
	gpc[4] = float(tnm)
	var pg := int(ceil(float(S) / 64.0))
	var pall := int(ceil(float(tnm) / 64.0))
	var cl := _tlrd.compute_list_begin()
	_tlrd.compute_list_bind_compute_pipeline(cl, _tl_bld_pipe)
	_tlrd.compute_list_bind_uniform_set(cl, _tl_us_b, 0)
	# gather (mode 7) + bitonic (91) + BFS split (14×) + moments (6)
	bpc[10] = 7.0
	_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_tlrd.compute_list_dispatch(cl, pg, 1, 1)
	_tlrd.compute_list_add_barrier(cl)
	var k := 2
	while k <= S:
		var j := k >> 1
		while j >= 1:
			bpc[10] = 1.0; bpc[11] = float(k); bpc[12] = float(j); bpc[13] = 1.0
			_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
			_tlrd.compute_list_dispatch(cl, pg, 1, 1)
			_tlrd.compute_list_add_barrier(cl)
			j = j >> 1
		k = k << 1
	_tlrd.compute_list_add_barrier(cl)
	for _d in range(ML_TREE_MAX_LEVELS):
		bpc[10] = 5.0
		_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
		_tlrd.compute_list_dispatch(cl, pall, 1, 1)
		_tlrd.compute_list_add_barrier(cl)
		bpc[10] = 8.0
		_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
		_tlrd.compute_list_dispatch(cl, 1, 1, 1)
		_tlrd.compute_list_add_barrier(cl)
	bpc[10] = 6.0
	_tlrd.compute_list_set_push_constant(cl, bpc.to_byte_array(), bpc.size() * 4)
	_tlrd.compute_list_dispatch(cl, pall, 1, 1)
	_tlrd.compute_list_add_barrier(cl)
	# walk — reads _tl_tpos (the sim's particle positions), writes _tl_tgrad
	_tlrd.compute_list_bind_compute_pipeline(cl, _tl_grv_pipe)
	_tlrd.compute_list_bind_uniform_set(cl, _tl_us_g, 0)
	_tlrd.compute_list_set_push_constant(cl, gpc.to_byte_array(), gpc.size() * 4)
	_tlrd.compute_list_dispatch(cl, int(ceil(float(Np) / 64.0)), 1, 1)
	_tlrd.compute_list_end()
	_tlrd.submit()
	_tlrd.sync()
	# host round trip #2: pull the gradient, record node count, re-upload
	# to the GLOBAL _ml_tree_grad for the mode-5 nbody arm.
	var grad := _tlrd.buffer_get_data(_tl_tgrad, 0, Np * 16).to_float32_array()
	var nc := _tlrd.buffer_get_data(_tl_ctr, 0, 4).to_int32_array()
	_ml_tree_nnode = nc[0] if nc.size() else 0
	_rd.buffer_update(_ml_tree_grad, 0, grad.size() * 4, grad.to_byte_array())


# Create the LOCAL RenderingDevice + tree build/walk buffers, shaders,
# pipelines and uniform sets — mirroring the verified verify_meshless_gravity
# recipe. Called once, lazily, on first tree-arm frame.
func _tree_local_setup() -> void:
	if _ml_tree_nsrc <= 0:
		return
	_tlrd = RenderingServer.create_local_rendering_device()
	if _tlrd == null:
		push_error("[CassiSim] tree local-RD create failed")
		return
	var S := _ml_tree_nsrc
	var N3 := grid_N * grid_N * grid_N
	var Np: int = N_particles
	var tnm: int = ML_TREE_NODE_MAX_MULT * S + 64
	_tl_src = _tlrd.storage_buffer_create(2 * S * 16)
	_tl_srcw = _tlrd.storage_buffer_create(S * 4)
	_tl_key = _tlrd.storage_buffer_create(S * 4)
	_tl_order = _tlrd.storage_buffer_create(S * 4)
	_tl_cf = _tlrd.storage_buffer_create(tnm * 16)
	_tl_nw = _tlrd.storage_buffer_create(tnm * 16)
	_tl_nq = _tlrd.storage_buffer_create(2 * tnm * 16)
	_tl_nr = _tlrd.storage_buffer_create(tnm * 16)
	_tl_ctr = _tlrd.storage_buffer_create(8 * 4)
	_tl_sites = _tlrd.storage_buffer_create(S * 16)
	_tl_psy = _tlrd.storage_buffer_create(S * 4)
	_tl_psi = _tlrd.storage_buffer_create(S * 4)
	_tl_vol = _tlrd.storage_buffer_create(S * 4)
	_tl_rho = _tlrd.storage_buffer_create(N3 * 4)
	_tl_tgrad = _tlrd.storage_buffer_create(maxi(Np, 1) * 16)
	_tl_tic = _tlrd.storage_buffer_create(maxi(Np, 1) * 4)
	_tl_tpos = _tlrd.storage_buffer_create(maxi(Np, 1) * 16)
	var bsf := load("res://compute/cassi_tree_build.glsl") as RDShaderFile
	var gsf := load("res://compute/cassi_tree_gravity.glsl") as RDShaderFile
	if bsf == null or gsf == null or bsf.get_spirv() == null or gsf.get_spirv() == null:
		push_error("[CassiSim] tree local-RD shaders failed to load")
		return
	_tl_bld_sh = _tlrd.shader_create_from_spirv(bsf.get_spirv())
	_tl_bld_pipe = _tlrd.compute_pipeline_create(_tl_bld_sh)
	_tl_grv_sh = _tlrd.shader_create_from_spirv(gsf.get_spirv())
	_tl_grv_pipe = _tlrd.compute_pipeline_create(_tl_grv_sh)
	_tl_us_b = _tlrd.uniform_set_create([
		_stor_tl(0, _tl_src), _stor_tl(1, _tl_srcw), _stor_tl(2, _tl_key), _stor_tl(3, _tl_order),
		_stor_tl(4, _tl_cf), _stor_tl(5, _tl_nw), _stor_tl(6, _tl_nq), _stor_tl(7, _tl_nr), _stor_tl(8, _tl_ctr),
		_stor_tl(9, _tl_sites), _stor_tl(10, _tl_psy), _stor_tl(11, _tl_psi), _stor_tl(12, _tl_vol), _stor_tl(13, _tl_rho),
	], _tl_bld_sh, 0)
	_tl_us_g = _tlrd.uniform_set_create([
		_stor_tl(0, _tl_src), _stor_tl(3, _tl_order), _stor_tl(4, _tl_cf), _stor_tl(5, _tl_nw),
		_stor_tl(6, _tl_nq), _stor_tl(7, _tl_nr), _stor_tl(8, _tl_ctr), _stor_tl(9, _tl_tgrad),
		_stor_tl(10, _tl_tic), _stor_tl(11, _tl_tpos),
	], _tl_grv_sh, 0)
	_tl_local_ready = _tl_bld_pipe.is_valid() and _tl_grv_pipe.is_valid() \
		and _tl_us_b.is_valid() and _tl_us_g.is_valid()
	print("[CassiSim] tree local-RD ready: pipes(b=%s,g=%s) sets(b=%s,g=%s)"
		% [_tl_bld_pipe.is_valid(), _tl_grv_pipe.is_valid(), _tl_us_b.is_valid(), _tl_us_g.is_valid()])


# LOCAL-RD uniform-storage helper (RDUniform for a storage buffer).
func _stor_tl(bind: int, r: RID) -> RDUniform:
	var u := RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_STORAGE_BUFFER
	u.binding = bind
	u.add_id(r)
	return u


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
	# mode 0: load ρ → complex buffer. The per-axis extents ride along for
	# the kspace multiply — the FFT passes only touch floats 4/8/12, so the
	# extents persist from this encode through the whole chain.
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

func _free_multimesh() -> void:
	# Release the renderer-owned instance buffer: remove and free the
	# MultiMeshInstance3D child (its MultiMesh holds the RD buffer that
	# _mm_rd_rid points at). Only safe with all uniform sets already freed
	# (callers free them first — see reinit).
	if _mmi != null and is_instance_valid(_mmi):
		remove_child(_mmi)
		_mmi.free()
	_mmi = null
	_mm = null
	_mm_rd_rid = RID()


func _setup_multimesh() -> void:
	var qm = QuadMesh.new()
	qm.size = Vector2(particle_size, particle_size)
	qm.orientation = PlaneMesh.FACE_Z

	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = true
	_mm.mesh = qm
	_mm.instance_count = max(N_particles, 1)
	_mm_particle_size = particle_size
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
			# Strided sum: the full-grid GDScript reduction was the slow part
			# of this 3 Hz readback (16.7M iterations at grid 256). A 1-in-16
			# subsample keeps the diagnostic mean accurate for the smooth q
			# field while cutting the loop ~16x.
			for qi in range(0, qf.size(), 16):
				q_sum += qf[qi]
			_q_mean = q_sum * 16.0 / max(qf.size(), 1)
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
	# Auto color-align cadence: re-fit the Qi band to the live q histogram
	# at the particles (~1.5 s — the Meshless mode grows q by orders of
	# magnitude and the fixed band would saturate). Independent of
	# suppress_readbacks (512 B readback, negligible).
	if auto_align_colors and particle_color_mode >= 2 \
			and _qhist_buf.is_valid() and _step_count > 0 and now_ms - _last_align_ms >= 1500:
		_last_align_ms = now_ms
		_align_color_band()
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




## Auto-align: read the particle-q histogram, re-fit the Qi cycle band to
## the live p1/p99 spread (blended toward the current band so the colors
## track smoothly as the coherence grows — e.g. the Meshless gravity mode),
## adapt the histogram range to the growth, and reset the bins for the next
## window. Manual legend drags and Fit disable auto_align_colors, so the
## manual band then stands.
func _align_color_band() -> void:
	if _rd == null or not _qhist_buf.is_valid():
		return
	var data := _rd.buffer_get_data(_qhist_buf, 0, 512)
	if data.size() < 512:
		return
	var bins := data.to_float32_array()
	var total := 0.0
	for b in bins:
		total += b
	if total < 200.0:   # too few samples yet — reset and wait
		_rd.buffer_update(_qhist_buf, 0, _qhist_zero_bytes.size(), _qhist_zero_bytes)
		return
	var span_l := log(maxf(_qhist_hi / _qhist_lo, 1.001))
	var p1 := _qhist_lo
	var p99 := _qhist_hi
	var cum := 0.0
	for b in range(128):
		var prev := cum
		cum += bins[b]
		if prev < 0.01 * total and cum >= 0.01 * total:
			p1 = _qhist_lo * pow(_qhist_hi / _qhist_lo, float(b) / 127.0)
		if prev < 0.99 * total and cum >= 0.99 * total:
			p99 = _qhist_lo * pow(_qhist_hi / _qhist_lo, float(b) / 127.0)
	# Range adaptation: keep the window a few decades wide around the live
	# spread so the next measurement stays well-resolved under growth.
	var top_frac := bins[127] / total
	var bot_frac := bins[0] / total
	if top_frac > 0.03:
		_qhist_hi *= 8.0
	elif p99 < _qhist_hi * 0.25:
		_qhist_hi = maxf(p99 * 8.0, _qhist_hi * 0.25)
	if bot_frac > 0.1:
		_qhist_lo = maxf(_qhist_lo * 0.01, 1e-9)
	elif p1 > _qhist_lo * 4.0:
		_qhist_lo = maxf(p1 * 0.25, 1e-9)
	# Re-fit: p1/p99 with generous margins, blended; the approach entry
	# follows the band top (the Fit action's convention).
	if p99 > p1 * 2.0 and p1 > 0.0:
		qi_cycle = qi_cycle.lerp(Vector2(p1 * 0.8, p99 * 1.5), 0.5)
		qi_approach = Vector2(qi_cycle.y, qi_approach.y)
	_rd.buffer_update(_qhist_buf, 0, _qhist_zero_bytes.size(), _qhist_zero_bytes)


## Sampled occupancy diagnostic: read back up to 40k strided particle
# positions and classify inner / face-edge / corner / out-of-box relative
# to the periodic box (per-axis ±extent_i = ±aspect_i·1.5·cluster_radius;
# lim_i = 0.85·extent_i).
# "Pooling in grid corners" shows up as a growing corner fraction with
# escaped particles stalling at the weak-field box corners.
func _sample_occupancy() -> void:
	if not _pos_buf.is_valid() or N_particles <= 0:
		return
	var n_sample := mini(N_particles, 40000)
	var stride := maxi(1, int(N_particles / n_sample))
	var ext_box: Vector3 = _extents()
	var lim := Vector3(0.85 * ext_box.x, 0.85 * ext_box.y, 0.85 * ext_box.z)
	# GPU path: one strided classify pass into 5 atomic counters (see
	# cassi_occupancy.glsl) — a 32-byte readback instead of the full
	# N x 16 B position buffer (64 MB per readback at 4M particles, the
	# 0.5 s stutter source). The CPU loop below is the fallback for when
	# the sampler shader/import is unavailable; it classifies the SAME
	# subsample set (pos[s x stride]).
	var gpu_done := false
	if _occ_shader.is_valid() and _occ_pipe.is_valid() and _us_occ_0.is_valid() \
			and _occ_pc_bytes.size() >= 40 and _occ_zero_bytes.size() >= 32:
		_occ_pc_bytes.encode_float(0, float(N_particles))
		_occ_pc_bytes.encode_float(4, float(n_sample))
		_occ_pc_bytes.encode_float(8, float(stride))
		_occ_pc_bytes.encode_float(12, lim.x)
		_occ_pc_bytes.encode_float(16, lim.y)
		_occ_pc_bytes.encode_float(20, lim.z)
		_occ_pc_bytes.encode_float(24, ext_box.x)
		_occ_pc_bytes.encode_float(28, ext_box.y)
		_occ_pc_bytes.encode_float(32, ext_box.z)
		# Zero the counters BEFORE the dispatch (buffer_update outside a
		# compute list — the BH-header contract).
		_rd.buffer_update(_occ_buf, 0, _occ_zero_bytes.size(), _occ_zero_bytes)
		var ocl = _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(ocl, _occ_pipe)
		_rd.compute_list_bind_uniform_set(ocl, _us_occ_0, 0)
		_rd.compute_list_set_push_constant(ocl, _occ_pc_bytes, _occ_pc_bytes.size())
		_rd.compute_list_dispatch(ocl, ceili(float(n_sample) / 256.0), 1, 1)
		_rd.compute_list_end()
		# Global RD: no submit/sync; buffer_get_data self-stalls.
		var od = _rd.buffer_get_data(_occ_buf, 0, 32)
		if od.size() >= 20:
			var g_in := int(od.decode_u32(0))
			var g_face := int(od.decode_u32(4))
			var g_corner := int(od.decode_u32(8))
			var g_out := int(od.decode_u32(12))
			var g_tot := maxi(int(od.decode_u32(16)), 1)
			print("[CassiSim] occ: inner=%.1f%% face/edge=%.1f%% corner=%.1f%% out=%d (n=%d, aspect=%s)" % [
				100.0 * float(g_in) / float(g_tot), 100.0 * float(g_face) / float(g_tot),
				100.0 * float(g_corner) / float(g_tot), g_out, g_tot, str(box_aspect)])
			gpu_done = true
	if gpu_done:
		return
	# CPU fallback (legacy full-buffer readback + classification).
	_ensure_synced()
	var pd = _rd.buffer_get_data(_pos_buf, 0, N_particles * 16)
	if pd.size() < N_particles * 16:
		return
	var pf = pd.to_float32_array()
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
	# The MultiMesh instance buffer is sized at _setup_multimesh from the
	# THEN-current N_particles. When N (or particle_size) changed since,
	# rebuild it before _init_particles: assigning a differently-sized
	# array to _mm.buffer ERR_FAILs (Godot multimesh.cpp set_buffer size
	# check) and the instancer dispatch then writes out-of-bounds past the
	# stale buffer. Rebuild runs BEFORE _cache_uniform_sets because
	# _us_inst_0 binds the (possibly new) _mm_rd_rid.
	if _mm == null or _mm.instance_count != max(N_particles, 1) or _mm_particle_size != particle_size:
		_free_multimesh()
		_setup_multimesh()
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
