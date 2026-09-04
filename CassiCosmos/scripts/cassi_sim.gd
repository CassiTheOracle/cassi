extends Node3D
## Cassi Universe Simulator — core orchestration.
##
## Manages the two-fluid PDE field grid, N-body particles, black-hole physics,
## and visualization — all running in Godot compute shaders.
##

const PHI: float = CassiTreeConsts.PHI
const PHI_INV3: float = (PHI - 1.0) / (PHI + 1.0)   # φ⁻³ = attractor π/ρ ≈ 0.236068
const PHI_INV2: float = 0.3819660112501051  # φ⁻² — q decoherence threshold
const PHI_6: float = CassiTreeConsts.PHI_6  # φ⁶ ≈ 17.94427191 (computed spelling — see CassiTreeConsts)
const CassiFieldIntelligenceRuntime = preload("res://scripts/cassi_field_intelligence.gd")
const PI_CLAMP_MAX: float = 0.72  # (π/ρ) upper clamp (stability; telemetry counts hits)
const LN2: float = 0.6931471805599453  # ln 2 — degenerate rainbow v_scale fallback (0.95·ln2)
const FIELD_PARTICLE_PROXY_CAPACITY := 64
const FIELD_PARTICLE_DT := 0.01
# Cadence/timeout consts (hoisted from the bare literals — review_sim.md #10;
# zero behavior change — same values the literals carried).
const COM_TRACK_CADENCE_MS := 2000          # window COM tracker cadence (2 s)
const ENV_TRACK_CADENCE_MS := 2000          # envelope tracker cadence (2 s)
const BOOT_PROGRESS_INTERVAL_MS := 5000     # decoupled-bootstrap progress print interval (5 s)
const BOOT_TIMEOUT_MS := 45000              # decoupled-bootstrap setup deadline (45 s)
const ALIGN_CADENCE_MS := 1500              # qhist color-align cadence (1.5 s)
const COM_MOVE_CAP_FRAC := 0.25             # window-tracker soft move cap (≤ 0.25·min_extent / tick)
const COM_DEAD_BAND_FRAC := 0.02            # window-tracker move dead band — skip moves below 2% of the cap (matches envelope_tracker.gd DEAD_BAND_FRAC := 0.02, no jitter on COM percentile noise)
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
const Q_FLOOR: float = 0.005   # Qi-rainbow bounded-channel band floor (hue = 0 at/below)
const Q_1: float = 0.95        # Qi-rainbow bounded-channel band top = the fit-scale band hi

# ═══════════════════════════════════════════════════════════════════════
# Exports
## Master run/pause switch for the physics loop.
@export var playing: bool = true              # simulation running

## Field grid resolution per dimension (power of two, 64-256); non-powers round up with a warning.
@export var grid_N: int = 64              # field grid resolution (per dim)
## N-body particle count (rendered as a starfield/cluster; raises GPU cost).
@export var N_particles: int = 2500000      # N-body particle count
## Physics timestep in sim seconds per step; a rendered frame runs up to max_steps_per_frame steps.
@export var dt: float = 0.03
## Cassi coupling constant, xi = φ⁶ = 17.94427191; the river law's chord coefficient is xi − 1.
@export var xi: float = 17.94427191  # φ⁶ — Cassi Qi coupling (exact: φ⁶ = φ⁵ + φ⁴)
## Gravity softening length; used as epsilon² = softening² in the force kernels.
@export var softening: float = 0.1        # gravity softening length
## Rendered quad size of each particle (world units); keep ≤ 0.5 for the star-cloud look.
@export var particle_size: float = 1.5
## Scale radius of the initial cluster (Plummer scale a / Gaussian sigma / uniform sphere radius, per the IC profile).
@export var cluster_radius: float = 120
## Number of initial clusters (placed on a ring/Fibonacci sphere).
@export var num_clusters: int = 1           # number of galaxy clusters
## Distance of cluster centers from the origin; a single cluster centers at (separation, 0, 0).
@export var cluster_separation: float = 150
## Bulk velocity added toward the origin (cluster-merger demo).
@export var merger_speed: float = 0.0
## Extra field injection from the deposited mass (0 = off).
@export var source_strength: float = 0.0  # PIC mass deposit drives field (set >0 for extra injection)
## Qi level above which the condensation scan nucleates a black hole record (only when black_holes_enabled).
@export var qi_condensation_threshold: float = 0.9
## Black hole mass growth per step from the field.
@export var bh_acc_rate: float = 0.01                # mass growth per step from field
## Black hole record lifetime in steps (0 = immortal).
@export var bh_max_age: float = 0.0                  # 0 = immortal
# Suppress the throttled CPU readbacks (occupancy/perf/q-tel/p[0]/inst-debug)
# that stall the global RD every ~0.5 s — the stutter source; useful
# interactively AND for recording. Physics and rendering are untouched.
## Off the throttled CPU readbacks (occupancy/perf/q diagnostics) that stall the GPU every ~0.5 s — removes the stutter; physics and rendering unchanged.
@export var suppress_readbacks: bool = true
# Enables the σ-regularized BH point-source sector in EVERY gravity mode:
# the softened Newtonian point-source force (gravity_at), the condensation
# scan (every 100 steps), and the BH-integrate pass (every step). Default
# off — particles-only; flip on for point sources. The shader reads the
# live toggle from bh[3].x (float 48 of the per-frame header upload).
## Master toggle for the black hole point-source sector in any gravity mode (softened Newtonian pull + condensation + BH-integrate passes). Default off = particles only.
@export var black_holes_enabled: bool = false

# Cassi particle merge — "dust -> object" (particle_merge_design.md): the
# THEORY's matter-growth complement to BH accretion (field -> matter grows,
# then matter -> object via THIS pass, then object -> BH). Two particles
# within the merge radius R_m = ½·h₀ = extent/grid_N coalesce (mass +
# momentum conserved, SINK-rule pair resolution) ONLY where the local
# coherence q_coh = ρ²/(ρ² + φ⁻² + ε²) exceeds φ⁻² (the phi gate). The merge
# writes merged survivor masses + dead (pos.w = 0) into pos[].w — which the
# deposit (mass ≤ 0 skip), the nbody kick (w preserved, mass 0 deposits
# nothing) and the instancer (size ∝ mass) all already honor, so NO other
# pass needs to know about death. Runs OUTSIDE the frame's step list: each
# cycle needs a host prefix-sum between the hash count→fill passes, which
# requires CPU syncs (buffer_get_data) illegal inside an open compute list
# on the global RD — so it is a standalone list sequence dispatched from
# _process after the physics batch (cadence: every frame; R_m ≈ 0.586 world
# units at the default 64³ / extent 37.5, crossed in ~586 dt=0.001 steps ≫ a
# frame's step budget, so once-per-frame is far inside the reaction budget).
## Two-particle merge (SINK-rule, q_coh > φ⁻² gate, R_m = extent/grid_N) grows matter from dust. Default off = particles-only. Init-time — reinit to apply.
@export var particle_merge: bool = false
## Merge cadence in accumulated STEPS (live): 0 = AUTO = 1/2 of the R_m
## reaction budget (R_m/(v·dt) with v = 1.0 world-units/s — the design's
## closing speed: R_m=0.586 crossed in ~586 dt=0.001 steps; at the owner
## config 180/64/0.05 → budget 56 → cadence 28, i.e. every ~2 of the
## ~16-20-step jobs); any positive value = an explicit step cadence. Gates
## BOTH the decoupled engine merge (passed via cfg) and the inline
## _render_frame hook. DEFAULT = 1 (per job): the local path retains the
## STEP-1 any-candidate early-out, while large decoupled/global clouds run one
## bounded source-shard/cell/entry phase per job. The latter measured 97 ms
## for 2.5 million particles, so per-job cadence remains responsive and still
## catches initial overlap; AUTO stays available for coarser-cadence users.
@export_range(0, 200, 1) var merge_cadence_steps: int = 1
var _merge_step_counter := 0
var _merge_pair_phase := 0
# Physical-merge redesign (coherence_merge_rnd.md §3, 2026-08-15): which of
# the four layer criteria apply when the merge is on. Default on = the
# realistic merge; off recreates the legacy (distance + q_coh only) for the
# §3d falsifier A/B tests. These are persistent flags (not init-time — read
# per dispatch, so they toggle live).
@export var merge_subsonic: bool = true   # hypothesis: |v_t| < c_s (no fly-by merges)
@export var merge_virial: bool = true     # hypothesis: virialised targets stop accreting
@export var merge_sel_gate: bool = true   # doctrine: order-selective q_sel = q_coh·q_ord

# Conservative vector-Qi stress and interscale momentum transfer. This sector
# is independent of FieldVel, runs only in the decoupled physics engine, and
# stays allocation-free and byte-inert while disabled. Reinitialize to apply.
@export var rotation_stress_enabled: bool = false
@export_range(4, 32, 1) var rotation_grid_N: int = 16
@export_range(2, 8, 1) var rotation_rungs: int = 4
@export_range(0.01, 100.0, 0.01) var rotation_field_inertia: float = 1.0
@export_range(0.0, 10.0, 0.01) var rotation_c_t: float = 0.5
@export_range(0.0, 10.0, 0.01) var rotation_c_l: float = 0.8
@export_range(0.0, 10.0, 0.01) var rotation_scale_omega: float = 0.5
@export_range(0.01, 1.0, 0.001) var rotation_attenuation: float = 1.0 / PHI
## Viscous matter↔field exchange is opt-in. Its heat ledger has no live
## pressure/thermal return path yet, so a nonzero default irreversibly
## thermalizes long runs even though momentum remains conserved.
@export_range(0.0, 10.0, 0.01) var rotation_exchange_rate: float = 0.0
@export_range(0.01, 100.0, 0.01) var rotation_reservoir_inertia: float = 1.0
@export_range(0.0, 10.0, 0.001) var rotation_lower_reservoir_coupling: float = 0.0
@export_range(0.0, 10.0, 0.001) var rotation_upper_reservoir_coupling: float = 0.0
## Read-only compact-object orientation axes. Requires rotation stress and
## reinitialization; writes only a renderer-owned MultiMesh.
@export var rotation_orientation_render_enabled: bool = false
# M3 live level-swap (MACHINE_PLAN.md §6 M3): when true, apply_level(dir) can
# hot-swap the box/extents/field/particle ICs from a cascade-tree level dir
# instead of a full restart. Default OFF → apply_level is a no-op and the
# default live path is bit-identical (the battery regression contract).
@export var level_swap: bool = true

# Object -> BH accretion: particles within a BH's accretion radius
# (bh_accretion_radius, world units, ~1× the default softening σ) are marked
# dead (pos.w = 0) and their mass is added atomically to the BH record — exactly
# conserved. Default off. Wired into both the decoupled engine and the
# non-decoupled _render_frame path.
@export var bh_accretion: bool = true
@export var bh_accretion_radius: float = 0.1

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
@export_enum("River", "Heuristic", "Plummer reference", "River self", "RealSim") var gravity_mode: int = 4

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
@export var initial_radius_fraction: float = 1
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
@export var initial_v_circ_factor: float = 1

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
@export var box_scale: float = 5

# ── Cascade grid (CASCADE_GRID.md) ─────────────────────────────────────
# Gradient order for the ∇(g·Φ) build pass (bh[3].z, live — no reinit):
#   2 = 3-point central differences (legacy, bit-identical),
#   4 = 5-point central differences — measured ring anisotropy
#       1.246→1.200 @2h, 1.090→1.045 @4h (CASCADE_GRID.md §2).
## Gradient order for the ∇(g·Φ) pass: 2 = 3-point (legacy), 4 = 5-point (O4).
@export var gradient_order: int = 4
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
@export var multi_rung_seed: bool = true
## Number of cascade rungs seeded (φ-spaced wavenumbers).
@export_range(1, 6, 1) var multi_rung_count: int = 6
## Displacement amplitude per rung (world units at the base rung; δx = A/k_m).
@export var multi_rung_amp: float = 0.2
## Base rung wavelength in units of cluster_radius (k_0 = 2π/(base·R)).

@export var multi_rung_base_scale: float = 1.0

## Meshless (moving-Voronoi) field arm. In the explicit legacy compatibility
## path (`gridless_physics=false`) it runs the two-fluid PDE on the JFA cell
## mesh and rasterizes back to grid buffers for render/condensation/river
## consumers. In the production site-native path (`gridless_physics=true`),
## the standalone engine owns field, mass, force, condensation, and telemetry
## on the live sites; this flag selects its topology/render integration.
## The legacy raster path remains available only for verification/compatibility
## scenes and is never selected by the production scenes.
@export var meshless_mode: bool = true
@export var gridless_physics: bool = false
## Tree gravity (init-time; default ON = the open-boundary meshless tree
## arm, first-class with meshless_mode — additive like dual_grid/
## gradient_order). Takes effect ONLY when meshless_mode is ALSO on — the
## spectral-Poisson river chain is replaced by the open-boundary meshless
## tree gravity (fmm_design.md Q6): the mass deposit + PDE still run (ρ/q
## source the tree gather), but the Poisson FFT chain, the grid ∇(g·Φ)
## gradient pass and the dual-lattice chain are skipped and the nbody arm
## samples the tree walk's per-particle ∇Φ_g. Leaving it off restores the
## grid river arm (that battery stays bit-identical).
@export var meshless_gravity: bool = true
## Reuse the decoupled engine's tree topology between site-mesh rebuilds and
## refresh moments bottom-up. Default OFF preserves the established full-build
## chain; a site-topology generation or home-window change forces a full build.
@export var tree_hierarchical_refit: bool = false

## Optional meshless phase-lock coupling (amendment 3c). A coefficient > 0
## enables the additive openness-gated laplacian term in the meshless site
## leapfrog (cassi_voronoi_cells.glsl mode 1). This is a diagnostic coupling
## proxy; it is not a stored compact phase field or a measured J_z current.
## The shader ABI calls this appended value J_wind (cell-PC slot 17, offset 68).
## 0.0 (default) = OFF = bit-identical battery. Init-time; reinit to apply.
@export var winding_coupling: float = 0.0

## Coherence-gated adaptive compute (coherence_adaptive_prereg.md Arm 3a): when
## ON, the job-boundary COM the window tracker follows is weighted by each
## particle's FIELD coherence q (the coherent core dominates; stray void
## particles contribute ~nothing) — the tracking envelope follows the field,
## not the raw cloud. Live (no reinit). Default OFF = plain mass COM, bit-identical.
@export var q_weighted_com: bool = false

## Coherence-gated adaptive compute (coherence_adaptive_prereg.md Arm 3b): when
## ON, the moving-Voronoi mesh rebuilds LESS often when the field's mean
## coherence q is high (coherent cells move rigidly / phase-lock and stay valid
## longer) and reverts toward the fixed ML_REBUILD base when q is low. β scales
## the q-driven lengthening: threshold = ML_REBUILD·(1 + β·min(q/φ⁻²,1)).
## Default OFF (β has no effect) = fixed ML_REBUILD, bit-identical.
@export var adaptive_rebuild: bool = true
@export var coherence_rebuild_beta: float = 1.0

## Coherence-adaptive Barnes-Hut (Arm 2): when ON, the tree-walk θ is
## modulated by per-node coherence — θ_eff = θ·(1 − α·(q_n − q_cent)) for
## nodes with q_n > q_cent (high-coherence regions resolve MORE opens, since
## they hold ordered structure worth resolving). Default OFF = plain θ,
## bit-identical. Forwards to the engine (decoupled) + the sim's global tree walk.
@export var coherence_theta: bool = true
@export var coherence_theta_alpha: float = 1.0

func _ml_rebuild_threshold() -> int:
	if not adaptive_rebuild:
		return ML_REBUILD
	var q_scaled: float = minf(_q_mean / PHI_INV2, 1.0) if PHI_INV2 > 0.0 else 0.0
	return maxi(ML_REBUILD, int(round(ML_REBUILD * (1.0 + coherence_rebuild_beta * q_scaled))))

## Boxless field reader (true-boxless arm, boxless_field_design.md): when ON,
## the q-histogram color-aligner samples coherence at particles from the
## moving-Voronoi sites directly instead of the periodic rasterized grid.
## Coordinate-independent and live; requires meshless_mode and a ready mesh.
## Current shipped default is ON; disabling it restores the grid sampler.
@export var boxless_field: bool = true

## Arm 1 latch: the live decoupled renderer is boxless only after the
## topology + shortlist + spatial-hash chain has been recorded. This avoids
## selecting site bindings while they still contain initialization zeros.
func _ml_boxless_on() -> bool:
	var ready_mesh := _ml_ready
	if _decoupled_active and _physics_engine != null:
		ready_mesh = bool(_physics_engine.get("_ml_ready"))
		var query_ready := bool(_physics_engine.get("_meshless_query_ready"))
		return boxless_field and meshless_mode and ready_mesh and query_ready
	return boxless_field and meshless_mode and ready_mesh

const FIELD_PARTICLES_SETTINGS: Dictionary = {
	"physics_decoupled": true,
	"N_particles": FIELD_PARTICLE_PROXY_CAPACITY,
	"num_clusters": 1,
	"cluster_radius": 4.0,
	"cluster_separation": 0.0,
	"particle_size": 2.5,
	"dt": FIELD_PARTICLE_DT,
	"particle_merge": false,
	"black_holes_enabled": false,
	"bh_accretion": false,
	"gridless_physics": false,
	"meshless_mode": false,
	"meshless_gravity": false,
	"boxless_field": false,
	"home_window_enabled": false,
	"tracking_envelope": false,
	"field_attractor_init": false,
	"source_strength": 0.0,
}
var _field_particles_saved_settings: Dictionary = {}

## Particles are simulated as moving patterns in the field instead of point objects.
@export var field_particles: bool = false
# Keeps the pinned single object available to verification scenes without
# adding a second user-facing setting.
@export_storage var field_particles_single_seed: bool = false

## Run the physics on the standalone engine's worker thread (decoupled
## producer: the engine owns a local RenderingDevice on its own thread and
## publishes snapshots; this sim's global-RD buffers become mirrors + render
## side, with one-batch-late position interpolation). Init-time; requires
## meshless_mode OFF for the documented grid producer path. Current shipped
## default is ON; when incompatible it falls back to the inline path.
@export var physics_decoupled: bool = true
## interpolation alpha already spans the MEASURED publish interval, so the
## display lag stays ≤ one publish interval at any cadence. Live — passed
## per-submit in the job dict, no reinit.
@export_range(1, 8, 1) var mirror_publish_cadence: int = 8  # perf-decomp 2026-08-15 FX2: 4→8 — the P3 publish is telemetry-only (32 B); the readback stall now lands half as often (the frame-bounded staging's accepted group). Display lag ≤ 1 interval either way.
## MOVABLE HOME-WINDOW (perf-decomp 2026-08-15, overhaul migration): when
## ON, the field grid's origin slowly follows the structure's center of
## mass instead of the fixed box origin — "expansion hits the wall" becomes
## "expansion outruns the window" (a tracking-capacity issue, not a
## topology issue). Reinit to apply. OFF (default) = the legacy fixed-origin
## box, bit-identical (every offset term is exactly 0.0).
@export var home_window_enabled: bool = false
var _window_center := Vector3.ZERO        # the field grid's world-origin offset
var _win_track_last_ms: int = 0           # slow-cadence COM tracker (2 s)
var _pub_com: Vector3 = Vector3.INF       # P3: engine-published COM (window tracker source)
## TRACKING ENVELOPE (B-build piece 3): when ON, the tracked box RE-FITS
## to the structure's percentile envelope (the EnvelopeTracker: the
## aspect-preserving extent with the grow/shrink hysteresis + the soft
## move cap) instead of the COM-only home-window. Writes the SAME three
## state slots the b_track probe proved: window_center (the origin),
## box_scale (the uniform envelope scale vs the ORIGINAL box — the
## per-frame _extents() derives every extent PC from it) and the bh
## header's per-axis half-extents (bytes 36/40/44 = bh[2].yzw — the
## per-frame 576 B refresh persists them). In the decoupled mode the
## ENGINE's state is written too (the engine owns the physics box); the
## sim's mirrors stay aligned (the render seam). Live: a toggle arms it
## at the next 2 s tick — no reinit. OFF (default) = the fixed box,
## bit-identical (every offset term exactly 0.0, box_scale 1.0).
@export var tracking_envelope: bool = true
var _env_tracker = null               # EnvelopeTracker (lazy: EnvelopeTracker.new())
var _env_orig_box := Vector3.ONE      # the fixed box at box_scale = 1.0 (the tracker's start extent)
var _env_track_last_ms: int = 0       # the same slow cadence as the COM tracker (2 s)
var _env_target_center := Vector3.ZERO
var _env_target_scale: float = 1.0
var _env_applied_center := Vector3.ZERO
var _env_applied_scale: float = 1.0
const ENV_APPLY_TAU_SEC: float = 0.75
const ENV_APPLY_CADENCE_MS: int = 500
var _env_apply_last_ms: int = 0
const ENVELOPE_SAMPLE_MAX: int = 8192
## Fixed seed for the initial conditions (0 = the legacy random init).
## Applied to BOTH the inline IC generators and the decoupled engine's ICs.
@export var ic_seed: int = 0

## Embodied field intelligence. Init-time and inline-global-RD only: the slow
## P/e state is another component of this authoritative world field, and its
## passes are recorded into the physics owner list. OFF keeps the historic
## field path bit-identical; disabled instances allocate only descriptor-safe
## one-cell fallback storage.
@export_group("Field Intelligence")
@export var field_intelligence_enabled: bool = false
@export_range(0, 65535, 1) var field_intelligence_probe_index: int = 0
@export_range(0.0, 1.0, 0.001) var field_intelligence_eta: float = 0.18
@export_range(0.0, 1.0, 0.001) var field_intelligence_gamma: float = 0.85
@export_range(0.0, 0.1, 0.0001) var field_intelligence_decay: float = 0.0001
@export_range(0.01, 8.0, 0.01) var field_intelligence_p_max: float = 1.0
@export_range(0.0, 8.0, 0.05) var field_intelligence_actuation: float = 4.0
@export_range(0.0, 0.1, 0.0001) var field_intelligence_energy_penalty: float = 0.0002
@export_enum("Normal", "Deterministically shuffled") var field_intelligence_reward_control: int = 0
@export_range(0, 256, 1) var field_intelligence_explore_period: int = 18
@export_range(0, 2048, 1) var field_intelligence_explore_steps: int = 72
@export_range(0.1, 64.0, 0.1) var field_intelligence_organ_radius: float = 4.0
@export_range(0.0, 32.0, 0.1) var field_intelligence_context_radius: float = 2.0
@export_range(0.1, 16.0, 0.1) var field_intelligence_kernel_radius: float = 0.8
@export var field_intelligence_render: bool = true
@export_group("")

## Display mode: 0 = Particles, 1 = Field, 2 = Cosmology.
@export_enum("Particles", "Field", "Cosmology") var mode: int = 0

 # ── Particle color scheme ──────────────────────────────────────────────
## Particle base mode (low nibble) plus VFX flags (high nibble):
## 0 = Cassi mass gradient (legacy, bit-identical); 1 = velocity speed
## rainbow; 2 = Qi rainbow; 3 = Qi double rainbow; 4 = two-axis q/ρ;
## 5 = field phase; 6 = velocity direction. Modes 5/6 use direct phase/
## direction mappings and ignore band fitting. Live — no reinit.
## High flags: 0x10 size-by-mass, 0x20 additive glow, 0x40 depth cue.
@export_range(0, 118, 1) var particle_color_mode: int = 2
## Presentation-only particle/material profile. OFF preserves the legacy
## billboard shader and the default field-volume palette; production scenes
## may opt in without changing physics, buffer layouts, or verification arms.
@export var presentation_profile: bool = false:
	get:
		return _presentation_profile
	set(value):
		if _presentation_profile == value:
			return
		_presentation_profile = value
		_apply_particle_presentation_profile()
		_update_particle_cull_bounds()
		_invalidate_volume_render_cache()

## Upper bound for one presentation particle's additive contribution at the
## 1,000-particle reference density. The renderer reduces it as particle count
## grows, so stacked layers stay luminous without becoming an opaque surface.
@export_range(0.01, 1.0, 0.01) var presentation_particle_opacity: float = 0.35:
	get:
		return _presentation_particle_opacity
	set(value):
		var next_opacity := clampf(value, 0.01, 1.0)
		if is_equal_approx(_presentation_particle_opacity, next_opacity):
			return
		_presentation_particle_opacity = next_opacity
		_apply_particle_presentation_opacity()

## Presentation palette applied consistently to particles, macro sites,
## velocity ribbons, and the profile-gated site-volume renderer. Color source
## remains particle_color_mode; this changes only the display mapping.
@export_enum("Cassi Night", "Spectrum") var presentation_color_scheme: int = 0:
	get:
		return _presentation_color_scheme
	set(value):
		var next_scheme := clampi(value, 0, 1)
		if _presentation_color_scheme == next_scheme:
			return
		_presentation_color_scheme = next_scheme
		_apply_particle_presentation_profile()
		_invalidate_volume_render_cache()

## Visual-only site representatives for the far field. The particle layer and
## every solver buffer remain unchanged when this is on.
@export var presentation_macro_lod_enabled: bool = false
@export_range(0.0, 1.0, 0.01) var presentation_macro_min_coherence: float = 0.03
@export_range(1.0, 100000.0, 1.0) var presentation_lod_enter: float = 300.0
@export_range(1.0, 100000.0, 1.0) var presentation_lod_exit: float = 700.0

## Bounded instantaneous velocity ribbons. This never allocates a
## per-particle temporal path history.
@export var presentation_trails_enabled: bool = false
@export_range(0.0, 10000.0, 0.01) var presentation_trail_speed_threshold: float = 0.25
@export_range(0.001, 2.0, 0.001) var presentation_trail_shutter_seconds: float = 0.08

## Opt-in true temporal reprojection for the site volume. It owns separate
## history resources and does not touch the compatibility volume pipeline.
@export var presentation_volume_history_enabled: bool = false
@export_range(0.0, 0.95, 0.01) var presentation_volume_history_weight: float = 0.45
@export_range(0.001, 0.5, 0.001) var presentation_volume_history_depth_tolerance: float = 0.05



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
## Qi cycle band [lo, hi] — the hue passes' span over the BOUNDED coherence
## q_coh = ρ²/(ρ²+φ⁻²+ε²) ∈ [0,1). Default = the calibrated full channel
## (measured live-config span; q_coh below lo clamps to red, above hi holds
## the span-top hue). The 2026-08-15 diag_qcoh_band measurement (live config,
## 1M particles): q_coh median 0.0018 at t=0 climbing to ~0.99 by t=4 as the
## collapse saturates — so a fixed band over the full channel shows the
## structure while the scale stays STABLE (no per-run re-anchor). Live — no reinit.
@export var qi_cycle: Vector2 = Vector2(0.005, 0.95)
## Qi pinch split — the concentrated-gradient band inside the cycle where most
## particles sit. OFF by default. OFF iff lo >= hi. Live — no reinit.
@export var qi_pinch: Vector2 = Vector2.ZERO
## Qi white-hot approach band [entry, white point] — count-invariant: violet
## (0.8) at the entry → PINK (0.93) at the white point, lightness 0.5 → 1.0.
## OFF by default: a fixed full-channel cycle gives the whole cloud hue with
## no monotone march to white as coherence saturates (the washout the user
## reported). Re-enable by dragging the legend's WHITE handle if you want
## condensation cores to glow. Live — no reinit.
@export var qi_approach: Vector2 = Vector2(1.0, 1.0)
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
## Dynamic fused-volume resolution controller. Default OFF preserves 512² output.
@export var volume_dynamic_resolution: bool = false
@export var volume_resolution_target: int = 512
@export var volume_resolution_min: int = 256
## Maximum fused-volume render tier. The controller rounds this bound to 256, 512, or 1024.
@export var volume_resolution_max: int = 1024
## Target wall-clock budget for the fused-volume dispatch controller, in milliseconds.
@export var volume_frame_budget_ms: float = 16.7
## Color-as-LUT (Tier-2, default ON in the current shipped configuration):
## bake the active color curve into a 256×1 RGBA8 LUT and drop the
## MultiMesh instance color channel (use_colors=false; custom_data carries
## the band position u + per-instance VFX factors). The LUT path is valid
## ONLY for base modes 0–3; modes 4/5/6 require vertex colors. A base-mode
## boundary crossing rebuilds the MultiMesh format without reseeding.
@export var color_lut_mode: bool = true
## On startup, frame a sibling Camera3D on the spawn region; headless scenes are unaffected.
@export var auto_frame_camera_on_start: bool = true
## to this on startup so very large structures stay visible (the default
## 4000 culls distant particles). Applied at _ready via
## _apply_camera_view_range().
@export_range(100.0, 10000000.0, 100.0) var camera_far_plane: float = 500000.0
## Legacy (scrapped 2026-08-15): the old automatic far-distance pull-back
## lock. Retained only so scene files that still pin it load cleanly — its
## value is IGNORED. The camera now flies freely and the F key returns it
## to the tracked particle cloud (_frame_camera_on_cloud).
@export_range(0.0, 1000000.0, 1.0) var camera_max_distance: float = 0.0

# ═══════════════════════════════════════════════════════════════════════
# Internal state
# ═══════════════════════════════════════════════════════════════════════

var _rd: RenderingDevice = null

var _sim_cam: Camera3D = null                 # sibling camera (main/recorder); null headless

# — field grid buffers (SET 0) —
var _field_ey: RID; var _field_ei: RID
var _field_q: RID;  var _field_vel: RID
var _field_scratch: RID  # vec4 per cell — two-fluid PDE double-buffer scratch (determinism fix, cassi_two_fluid.glsl)

# — Poisson solver (SET 0 of cassi_poisson.glsl) —
var _fft_buf: RID      # vec2 per cell — FFT workspace; real part = Φ after solve
var _tel_buf: RID      # gravity telemetry: [pi_hi, pi_lo, rho_guard, q_min, q_max, pi_min, pi_max, samples]
# — Cell-centered ∇(g·Φ) field (SET 0 binding 7 of cassi_nbody_gravity.glsl) —
var _grad_buf: RID     # vec4 per cell — gradient pass output, river-arm input
var _grad_buf2: RID    # dual-lattice ∇(g·Φ) (SET 0 binding 8 — CASCADE_GRID.md);
					   # always allocated so dual_grid stays a LIVE toggle
var _occ_buf: RID      # 32-byte occupancy counters (cassi_occupancy.glsl)
var _occ_sample_buf: RID   # compact vec4 samples for envelope tracking
var _envelope_sample_positions := PackedFloat32Array()
# — particle buffers (SET 1) —
var _pos_buf: RID; var _vel_buf: RID; var _acc_buf: RID
# — snapshot/interpolation buffers (decoupled physics producer seam) —
var _pos_prev_buf: RID = RID()     # pre-batch snapshot (= the previously rendered state)
var _pos_render_buf: RID = RID()   # interpolated render snapshot (the instancer reads this)
var _interp_alpha: float = 1.0     # DORMANT: alpha pinned to 1.0 → pos_render == pos bit-for-bit
# — blend shader (position snapshot/interpolation; cassi_blend_pos.glsl) —
var _blend_sh: RID; var _blend_pipe: RID; var _blend_pc: PackedByteArray
var _us_blend_0: RID            # fp32 set (inline)
var _us_blend_0_dc: RID         # P3 one-RD set: the ENGINE's live fp32 pos → pos_render (−c seam)
var _us_inst_0_render_dc: RID   # P3 one-RD instancer set: pos_render + the ENGINE's vel/fields
var _us_inst_0_lut_render_dc: RID
var _us_qhist_0_render_dc: RID  # P3 one-RD qhist set: pos_render + the ENGINE's field_q
var _us_occ_0_dc: RID           # P3 one-RD occupancy set: the ENGINE's pos
# — Decoupled physics producer (the standalone engine on a worker thread) —
var _physics_engine = null            # CassiPhysicsEngine (untyped: dynamic dispatch)
var _decoupled_active := false        # decoupled AND meshless off (the grid path)
var _decoupled_boot_wait := false     # FIX A: true until the first publish lands
var _decoupled_boot_start_ms := 0     # FIX A: wall clock when boot began (timeout)
var _decoupled_boot_fs_ms := 0        # M0b-P-FX: wall clock when finish_setup began (hitch measurement)
var _decoupled_boot_last_progress_ms := 0  # FIX A: wall clock of the last bootstrap progress print
var _decoupled_target := 0            # cumulative REQUESTED steps (the job target)
var _pub_counter := 0                 # M0b-P: publish cadence counter (the frame-path jobs)
var _decoupled_pending := 0           # truthful backlog = target − executed (UI "behind X s")
var _last_publish_ms := 0             # wall-clock gate for the interp alpha
const DECOUPLED_LEAD_CAP: int = 8
var _batch_ema_ms := 16.7             # EMA of publish intervals (ms) — alpha sweep scale
var _executed_prev := 0               # previous publish's executed count (perf delta)

var _decoupled_initial_render_pending := false
var _gridless_failure := false  # fail closed; never re-enter inline grid physics
var _decoupled_initial_blend_id := 0
# — auxiliary buffers (SET 2) —
var _cluster_buf: RID
var _bh_buf: RID
var _mass_density_buf: RID
var _mass_density_fix: RID  # uvec4 per cell — exact fixed-point digit-sum deposit accumulator (determinism fix, cassi_mass_deposit.glsl)

var _two_fluid_shader: RID;  var _two_fluid_pipe: RID
var _nbody_shader: RID;      var _nbody_pipe: RID
var _poisson_shader: RID;    var _poisson_pipe: RID
var _field_render_shader: RID; var _field_render_pipe: RID
var _volume_shader: RID; var _volume_pipe: RID
var _mass_deposit_shader: RID; var _mass_deposit_pipe: RID
var _shaders_ready: bool = false
var _setup_retry_counter: int = 0
var _volume_pc_bytes: PackedByteArray
var _volume_stats_zero: PackedByteArray
var _volume_resolve_pc_bytes: PackedByteArray
var _volume_history_state_bytes: PackedByteArray

# True temporal volume history is a separate default-off path. The live
# fused-volume shader and its fixed 32-float ABI remain the compatibility
# route; this path owns current/depth, ping-pong history, resolve, and state.
var _volume_history_shader: RID; var _volume_history_pipe: RID
var _volume_reproject_shader: RID; var _volume_reproject_pipe: RID
var _volume_current_tex: RID
var _volume_current_depth_tex: RID
var _volume_history_color_a: RID; var _volume_history_color_b: RID
var _volume_history_depth_a: RID; var _volume_history_depth_b: RID
var _volume_history_state: RID
var _us_volume_history_0: RID
var _us_volume_reproject_ab: RID; var _us_volume_reproject_ba: RID
var _volume_history_prev_is_a: bool = true
var _volume_history_has_state: bool = false
var _volume_history_last_origin := Vector3.INF
var _volume_history_last_forward := Vector3.ZERO
var _volume_history_last_fov: float = -1.0
var _volume_history_last_size := Vector2i(-1, -1)
var _volume_history_last_topology: int = -1
var _volume_history_last_query: int = -1
var _volume_history_last_key: float = -1.0
var _volume_stats: RID
var _volume_history_neutral: RID
var _volume_cache_valid: bool = false
var _volume_last_generation: int = -1
var _volume_last_site_count: int = -1
var _volume_last_cam_transform := Transform3D()
var _volume_last_fov := -1.0
var _volume_last_window_center := Vector3.INF
var _volume_last_extents := Vector3(-INF, -INF, -INF)
var _volume_last_rt_size := Vector2i(-1, -1)
var _volume_dispatch_frame_prev: int = 0
var _volume_dispatch_frame_delta := 0.0
var _volume_dispatch_frame_ema := 0.0
var _volume_eval_counter: int = 0
var _volume_overload_streak: int = 0
var _volume_underload_streak: int = 0
var _volume_current_tier: int = 512
var _volume_last_tier_change_frame: int = -1
var _volume_tier_change_count: int = 0
var _volume_last_tier_change_reason := ""
var _volume_downshift_latency: int = 0
var _volume_last_requested_tier: int = 512
var _volume_pending_tier: int = 0
var _volume_last_max_steps := -1.0
var _volume_last_cutoff := -1.0
var _volume_last_history_weight := -1.0
var _volume_last_history_depth_tolerance := -1.0
var _volume_last_scheduling := -1.0
var _volume_last_boxless_active := false
var _volume_last_record_us := 0
var _volume_max_record_us := 0
var _us_poisson_0: RID
var _us_fr_0: RID; var _us_fr_2: RID
var _us_volume_0: RID = RID()
var _volume_dispatch_id: int = 0
var _volume_skip_count: int = 0
var _volume_uniform_set_create_count: int = 0
var _volume_set_dirty: bool = true
var _volume_us_sig_shader: RID
var _volume_us_sig_0: RID; var _volume_us_sig_1: RID; var _volume_us_sig_2: RID
var _volume_us_sig_3: RID; var _volume_us_sig_4: RID; var _volume_us_sig_5: RID
var _volume_us_sig_6: RID; var _volume_us_sig_7: RID; var _volume_us_sig_8: RID
var _volume_us_sig_9: RID
var _us_two_0: RID; var _us_two_1: RID; var _us_two_2: RID
var _field_intelligence: RefCounted = null
var _field_intelligence_params := {}
var _us_mass_dep_0: RID
var _us_nbody_0: RID; var _us_nbody_1: RID; var _us_nbody_2: RID
signal workbench_cursor_changed(world_position: Vector3, source: String)
var field_workbench: FieldWorkbench = null
var _workbench_cursor_world := Vector3.ZERO
var _workbench_cursor_armed := false
var _workbench_cursor_marker: MeshInstance3D = null
var _workbench_preview_marker: MultiMeshInstance3D = null
var _instancer_shader: RID; var _instancer_pipe: RID
var _cond_shader: RID; var _cond_pipe: RID; var _us_cond_0: RID; var _us_cond_1: RID
var _bh_int_shader: RID; var _bh_int_pipe: RID; var _us_bh_int_0: RID; var _us_bh_int_1: RID
var _occ_shader: RID; var _occ_pipe: RID; var _us_occ_0: RID  # occupancy sampler (diagnostic; CPU fallback)
# ── Particle merge (compute/cassi_particle_merge.glsl; init-time, particle_merge) ──
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
var _merge_cycles_run: int = 0   # lifetime merge-cycle count (verify/battery diag)
var _merge_dc_first_completion_logged := false
# ── On-GPU exclusive scan (compute/cassi_exclusive_scan.glsl; FIX B): replaces
# the host CPU prefix-sum (cc readback + cs/ch uploads) with 4 GPU passes. ──
var _scan_shader: RID; var _scan_pipe: RID; var _us_scan_0: RID
var _merge_scr_buf: RID
var _merge_nb1a: int = 256   # pad(L1 count to 256)
var _merge_nb2: int = 1      # L2 count (≤256)
# ── BH accretion (compute/cassi_bh_accretion.glsl; init-time, bh_accretion) ──
var _bh_acc_shader: RID; var _bh_acc_pipe: RID; var _us_bh_acc_0: RID
var _bh_acc_pc_bytes: PackedByteArray
var _cond_step_counter: int = 0
var _us_inst_0: RID = RID()
var _us_inst_0_render: RID = RID()  # instancer set variant: position binding (0) reads _pos_render_buf
# Color-as-LUT (Tier-2) instancer set variants: binding 6 = the LUT-mode flag
# buffer — the legacy sets bind the static OFF buffer, the LUT sets the ON
# buffer, so the SET SELECTION is the mode switch (no per-frame uploads).
var _us_inst_0_lut: RID = RID()
var _us_inst_0_lut_render: RID = RID()
var _lut_u_buf_on: RID = RID()   # 16 B {1,0,0,0} — bound by the LUT set variants
var _lut_u_buf_off: RID = RID()  # 16 B {0,0,0,0} — bound by the legacy set variants
var _lut_u_on_bytes: PackedByteArray = PackedByteArray()
var _lut_u_off_bytes: PackedByteArray = PackedByteArray()
# Arm 1 boxless instancer set variants: .y in the flag buffer = 1 → the
# instancer's tri_coherence/tri_phase read the moving-Voronoi sites via the
# coherence-filtered shortlist. Selected only when _ml_boxless_on(); the
# legacy sets (flag.y=0) stay the default, bit-identical.
var _us_inst_0_boxless: RID = RID()
var _us_inst_0_render_boxless: RID = RID()
var _us_inst_0_lut_boxless: RID = RID()
var _us_inst_0_lut_render_boxless: RID = RID()
var _us_inst_0_boxless_render_dc: RID = RID()
var _us_inst_0_lut_boxless_render_dc: RID = RID()
var _shortlist_flag_off: RID = RID()   # 16 B {0,1,0,0}
var _shortlist_flag_on: RID = RID()    # 16 B {1,1,0,0}
var _color_lut_tex: ImageTexture = null  # 256×1 RGBA8 — re-baked on band change
var _lut_sig: PackedFloat32Array = PackedFloat32Array()  # 18 floats: 17 engine + base mode (empty = never baked)
var _lut_bake_dirty: bool = false
var _mm_lut_mode: bool = false   # the FORMAT the multimesh was built with (static per build)
var _warned_lut_build_incompat: bool = false
var _warned_lut_incompat: bool = false

# — q-histogram (auto color-align; cassi_qhist.glsl) —
var _qhist_shader: RID; var _qhist_pipe: RID; var _us_qhist_0: RID
var _us_qhist_0_render: RID = RID()  # qhist set variant: binding 0 reads _pos_render_buf
var _qhist_buf: RID                 # 128 log-spaced float bins
var _qhist_zero_bytes: PackedByteArray
var _qhist_pc_bytes: PackedByteArray
var _qhist_lo: float = 1e-6         # FIXED bounded-channel log range (q_coh ∈ [0,1))
var _qhist_hi: float = 0.999        # — the old per-run growth adaptation is dead
var _last_align_ms: int = 0
var _align_ran_this_frame := false   # FIX 2: true when _align_color_band self-stalled this frame

# — pre-allocated push-constant byte buffers (hitch-free: no per-step allocs) —
var _pc_bytes: PackedByteArray        # shared 11-float PC (all physics shaders)
# N-body PC is 15 floats (60 B): the nbody shader carries the
# gradient-pass selector (pass_mode) as its 12th field plus the three
# RealSim dissipation coefficients (13th-15th). The other shaders'
# structs are 11 floats (44 B) — Godot hard-errors on push-constant size
# mismatch, so the nbody shader gets its OWN pre-allocated 60 B buffer
# (the dedicated-PC precedent) instead of growing the shared one.
var _nbody_pc_bytes: PackedByteArray  # nbody PC (15 floats: 11 shared + pass_mode + 3 RealSim)
# Two-fluid dedicated PC (16 floats: the shared 11 + the 3 per-axis
# extents + pass_sel + omega2 — layout key `cassi_two_fluid`) — the
# dedicated-PC precedent: field_render/instancer
# share _pc_bytes (11 floats) and Godot hard-errors on push-constant size
# mismatch, so the two-fluid's anisotropic-stencil extents get their own.
var _two_fluid_pc_bytes: PackedByteArray  # two-fluid PC (16 floats: 11 shared + extent_x/y/z + pass_sel + omega2)
var _md_pc_bytes: PackedByteArray     # mass deposit PC (9 floats: N, particle_N, extent_x/y/z, off_x/y/z, mode)
var _bh_int_pc_bytes: PackedByteArray # BH integrate PC (4 floats)
var _cond_pc_bytes: PackedByteArray   # condensation PC (4 floats)
var _bh_init_bytes: PackedByteArray   # BH header init (the full 36-vec4/576-B header — float 144; the nbody shader reads bh[4..] records, so the whole buffer is seeded)
var _tel_reset_bytes: PackedByteArray # gravity telemetry reset (8 floats)
var _poisson_pc_bytes: PackedByteArray  # poisson PC (7 floats: N, axis, dir, mode, extent_x/y/z)
var _occ_pc_bytes: PackedByteArray    # occupancy PC (10 floats: np, n_sample, stride, lim_x/y/z, ext_x/y/z, pad)
var _occ_zero_bytes: PackedByteArray  # occupancy counter reset (32 B of zeros)
var _merge_pc_bytes: PackedByteArray  # merge PC (26 floats: N, phi, phi_inv2, q_th, R_m, ext.xyz, grid_N, hash_nxyz, cell_w.xyz, pass_mode, cyc_slot, boxless, n_sites)
var _merge_scan_pc_bytes: PackedByteArray  # exclusive-scan PC (4 floats, reused across passes)
# Instancer dedicated PC (32 floats = 128 B — the AMD RDNA3 Vulkan cap;
# EXACTLY 128, nothing more) — the consolidated gradient engine: the shared
# 11 + color_mode@11 + prog_mode@12 + ref@13 + the up-to-3 cycle segments
# (lo1/slope1@14-15, lo2/slope2/off2@16-18, lo3/slope3/off3@19-21) +
# hiC@22 + span_total@23 + the approach band (a_lo@24, a_hi@25, a_top@26,
# approach_on@27) + extent_x/y/z@28-30 + hue_offset@31.
# The shared-PC consumers are field_render and the instancer. Godot hard-errors
# on push-constant size mismatch, so the instancer's extra fields get their
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
const ML_JFA_JUMPS := [1, 2, 4, 8, 16, 32, 16, 8, 4, 2, 1, 1, 1]
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
const SS_Q_FLOOR := 0.3819660112501051   # Arm 1 shortlist q threshold — φ⁻² (coherent-site floor)
const HASH_H := 32                        # boxless site hash cells per axis (32768 cells)
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
var _ml_grad_y: RID  # vec4[n_sites] — solved least-squares ∇ψ_y (.xyz), .w = 1
var _ml_grad_i: RID  # vec4[n_sites] — solved least-squares ∇ψ_i (.xyz), .w = 1
var _ml_lsm_y: RID   # vec4[3·n_sites] — least-squares M rows + rhs (ψ_y)
var _ml_lsm_i: RID   # vec4[3·n_sites] — least-squares M rows + rhs (ψ_i)
# ── Arm 1 shortlist (coherence_adaptive_prereg.md) — the coherent-site subset
# the per-frame boxless INSTANCER samples (built on the steer cadence) ──
var _shortlist_shader: RID; var _shortlist_pipe: RID
var _shortlist_sites: RID      # vec4[max_sites] — (pos.xyz, float(site_idx)) for q ≥ q_floor
var _shortlist_count: RID      # uint[1] — atomic compaction cursor / result
var _us_shortlist: RID
var _shortlist_pc_bytes: PackedByteArray   # 3 floats (12 B): n_sites, q_floor, mode
# ── Boxless site hash (boxless_site_hash_prereg.md): the spatial hash over the
# shortlist (sim's own inline build; the decoupled arm reads the engine's).
var _hash_shader: RID; var _hash_pipe: RID
var _hash_cell_start: RID; var _hash_cell_sites: RID; var _hash_cell_count: RID
var _hash_cfg: RID
var _us_hash: RID
var _hash_pc_bytes: PackedByteArray   # 9 floats: ext_xyz, H, shortlist, tile origin xyz, mode
var _hash_cfg_bytes: PackedByteArray  # 4 floats: world origin xyz, hash cell side
var _us_jfa_0: RID
var _us_cell_0: RID
var _us_raster_0: RID
var _jfa_pc_bytes: PackedByteArray    # JFA PC (8 floats: N, jump, read_a, n_sites, h, pad×3)
var _cell_pc_bytes: PackedByteArray   # cell PC (18 floats: mode, N, n_sites, dt, hx, hy, hz, C2, OM2, PHI, source_s, rho_floor, drift_cap, kappa, lam, T_steer, lloyd_p, J_wind)
var _raster_pc_bytes: PackedByteArray # raster PC (8 floats: N, n_sites, hx, hy, hz, pad×3)
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
const ML_TREE_LEAF_CAP := CassiTreeConsts.ML_TREE_LEAF_CAP
const ML_TREE_MAX_LEVELS := CassiTreeConsts.ML_TREE_MAX_LEVELS
const ML_TREE_NODE_MAX_MULT := CassiTreeConsts.ML_TREE_NODE_MAX_MULT
const ML_TREE_FIELD_FLOOR := CassiTreeConsts.ML_TREE_FIELD_FLOOR   # source-mass recipe field-density floor
const ML_TREE_THETA := CassiTreeConsts.ML_TREE_THETA
# Tree-walk softening ε (LENGTH²: the walk's monopole R² = ds² + eps2 and the
# softened quadrupole R² = ds² + eps2 both scale ∝ 1/R³ / 1/R⁷). Picked as a
# PHYSICAL scale tied to the box's min half-extent: the effective
# eps2 = (ML_TREE_EPS2_FRAC · extent_min)² is derived per-dispatch (see
# _dispatch_tree_gravity*). Justification of 0.05: at the default 64³ /
# cluster_radius 150 box (extent_min = 75) that is (0.05·75)² = 14, a softening
# length ~3.75 ≈ 1.6 leaf cells. Empirically calibrated against the river
# control via verify_particle_vanish: 0.02 (length 1.5) delayed but did not
# prevent the core-collapse force blow-up (fr≈560 tgrad spiked to ~1e6);
# 0.05 flattens the tree's point-source near-field to the river's grid-convolved
# smoothness at collapse densities, and with the per-node cap + G_SCALE it
# confers 100% retention on both drive paths (no escape kick, no NaN).
const ML_TREE_EPS2_FRAC := 0.05      # input to the derived eps2
const GRAVITY_MODE_TREE := 5.0       # `tree river` — gravity_mode value
# Tree-arm force calibration, G_tree = G_N · ML_TREE_G_SCALE, carried in the
# BH header slot bh[3].w (float 60 — a free slot; routed there instead of the
# nbody PC so the 15-float nbody push constant keeps every manual 60-byte
# dispatcher in the verify battery valid). The river G_N is calibrated for the
# spectral-Poisson ∇(g·Φ) which carries an implicit V_cell/(4πr²) suppression;
# the tree's ∇Φ_g is a direct Newtonian sum with NO such suppression (and site
# weights w=m·g already carry g≈ξ). G_SCALE = 1.0: the tree uses the SAME
# config-calibrated G_N as the river/IC (the G_eff=1 convention), so the tree
# force reproduces the IC circular-velocity binding at every resolution.
# DERIVED 2026-08-16 (virial theorem, measured at the owner's 2.5M decoupled
# config): the legacy fixed 0.03 (fit at N=4000 against verify_particle_vanish)
# makes G_tree = 0.03·G_N = 0.000285 at the owner's scale (river_calibrate_gn
# already shrinks G_N with the deposited mass), giving 2KE/|W| ≈ 30-80 — the
# cloud is violently UNBOUND and inflates, streaming past the camera = the
# residual "vanish." G_SCALE=1.0 restores Q_vir=2KE/|W| to 0.4-0.6 (bound,
# relaxing), with tgrad bounded ~12k and 100% retention to 3000 frames.
const ML_TREE_G_SCALE := 1.0
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
var _ml_tree_nqq: RID       # float[M] — Arm 2 per-node mean coherence q (nodeQq binding 14)
var _ml_tree_ctr: RID       # uint[8]
var _ml_tree_grad: RID      # vec4[N_particles] — per-particle tree ∇Φ_g·(−) (nbody set 1 binding 3)
var _ml_tree_icount: RID    # uint[N_particles] — walk interaction counts (walk binding 10)
var _us_tree_build: RID
var _us_tree_grav: RID
var _tree_build_pc_bytes: PackedByteArray  # build PC (19 floats: 14 shared + grid_N, ext_x/y/z, field_floor)
var _tree_grav_pc_bytes: PackedByteArray   # walk PC (5 floats: N, theta, eps2, use_tp, node_cnt)
var _ml_tree_nsrc: int = 0
var _ml_tree_nnode: int = 0
# ── Tree momentum-conservation pass (cassi_tree_momcon.glsl, 2026-08-15) ──
# The tree's per-particle (π/ρ) prefactor breaks action–reaction (Σm·a ≠ 0),
# so the cloud acquires a net self-impulse and ballistically drifts off the
# fixed window (the "all particles vanish" measured at the owner's scale).
# This pass zeroes Σm·a after the nbody gravity step in tree mode — a DERIVED
# Newton-3rd-law correction, not a fitted constant.
var _tree_mc_shader: RID
var _tree_mc_pipe: RID
var _tree_mc_buf: RID        # vec4 reduce accumulator (Σm·ax, Σm·ay, Σm·az, Σm)
var _us_tree_mc: RID
var _tree_mc_pc_bytes: PackedByteArray   # 3 floats (12 B): N_f, op
# ── Tree-gravity THREADED arm (cassi_tree_worker.gd, 2026-08-13) ─────────
# The global RD (RenderingServer) does NOT execute the tree shaders from
# cassi_sim's _process loop on this build (verified extensively: even a raw
# self-contained mode-10 dispatch with a fresh shader/pipe/set no-ops, while
# the SAME dispatch runs in a bare-Node scene and on any local RD). The tree
# arm therefore runs on a LOCAL RenderingDevice — and now on a DEDICATED
# THREAD (the first slice of the physics decoupling): the worker owns the
# local RD + build/walk shaders and computes the per-particle gradient OFF
# the main thread, publishing the newest completed result. The sim stages
# the frame's meshless source state (the global-RD readbacks — main-thread-
# only) and submits a job; the bootstrap frame blocks for a fresh gradient
# so step 1 reads correct forces, every later frame is non-blocking (the
# last gradient stands until the worker finishes — the same freshness
# semantics as the cadence skip). See cassi_tree_worker.gd for the contract.
var _tree_worker: RefCounted = null   # CassiTreeWorker (lazy, recreated on reinit)
var _tl_frame := 0
var _tree_local_cadence := 200  # tree refresh every 200th physics job/frame (perf-decomp 2026-08-15 FX2: 50→200 — the in-list tree build is a ~25 ms render-thread burst at 50k; 200 chains ≈ 0.5 s at the 400 fps live rate, still ~6× FRESHER PER STEP than the 500k-era blessed window (200×2.5 steps vs 50×64 steps), so the gravity accuracy is unchanged while the burst duty drops 20%→5% — the one-RD frame-bounded staging's burst cadence knob)

# True when the tree arm is LIVE (meshless + tree gravity). Gates the
# _shaders_ready retry: the tree shaders/pipes/sets must be ready before
# the sim declares itself ready, else a late-arriving tree SPIR-V leaves an
# absent uniform set that Godot silently no-ops.
func _ml_need_tree() -> bool:
	return meshless_mode and meshless_gravity

# — MultiMesh rendering —
# NOTE: global RD — no manual submit/sync anywhere (illegal on the main
# instance); readbacks self-stall via buffer_get_data.
# GPU-DIRECT: the instancer compute shader writes straight into the
# renderer's OWN multimesh instance buffer (RenderingServer
# .multimesh_get_buffer_rd_rid) — zero per-frame readbacks/CPU uploads.
# (`MultiMesh.buffer` is PackedFloat32Array-typed in Godot 4.7; there is no
# RID-injection property, so the reverse direction is used: compute binds
# the renderer's buffer RID.)
# Visual field readbacks stay wall-time capped at ~15 Hz; full-q diagnostics
# stay near ~3 Hz because each readback stalls the global RD.
const RB_HZ: float = 15.0
const DIAG_HZ: float = 3.0
var _mm_rd_rid: RID = RID()              # the multimesh's RD instance buffer
var _last_field_rb_ms: int = 0
var _last_diag_ms: int = 0
var _last_p0_rb_ms: int = 0              # wall-time gate for the p[0] debug print
var _mmi: MultiMeshInstance3D; var _mm: MultiMesh
var _presentation_profile: bool = false
var _presentation_color_scheme: int = 0
var _presentation_particle_opacity: float = 0.35
var _particle_compat_shader: Shader = null
var _particle_presentation_shader: Shader = null
var _presentation_viewport_height: float = -1.0

# ── Optional presentation layers (each owns a renderer-only MultiMesh) ──
# The individual-particle buffer remains authoritative. These layers write
# only renderer-owned instance buffers and are allocated lazily while their
# opt-in toggle *and* presentation_profile are enabled.
const PRESENTATION_TRAIL_CAP: int = 65_536
var _macro_lod_shader: RID; var _macro_lod_pipe: RID; var _us_macro_lod_0: RID
var _macro_lod_pc: PackedByteArray
var _macro_lod_mmi: MultiMeshInstance3D = null
var _macro_lod_mm: MultiMesh = null
var _macro_lod_rd_rid: RID
var _macro_lod_material: ShaderMaterial = null
var _macro_lod_last_scheme: int = -1
var _macro_lod_last_range := Vector2(INF, INF)

var _trail_shader: RID; var _trail_pipe: RID
var _us_trail_0: RID; var _us_trail_0_dc: RID
var _trail_pc: PackedByteArray
var _trail_mmi: MultiMeshInstance3D = null
var _trail_mm: MultiMesh = null
var _trail_rd_rid: RID
var _trail_material: ShaderMaterial = null
var _trail_last_scheme: int = -1

var _rotation_axis_shader: RID; var _rotation_axis_pipe: RID
var _us_rotation_axis_0: RID
var _rotation_axis_pc: PackedByteArray
var _rotation_axis_mmi: MultiMeshInstance3D = null
var _rotation_axis_mm: MultiMesh = null
var _rotation_axis_rd_rid: RID
var _rotation_snapshot: Dictionary = {"enabled": false}
# GPU-written open-world particle transforms are not bounded by the adaptive
# high-Q field envelope. Keep the documented conservative support box while
# still allowing a genuinely larger simulation envelope to expand the AABB.
const PARTICLE_CULL_MIN_HALF_EXTENT: float = 5000.0
const PRESENTATION_OPACITY_REFERENCE_PARTICLES: float = 1000.0
const PRESENTATION_MIN_PIXEL_RADIUS: float = 1.6
const PRESENTATION_MAX_PIXEL_RADIUS: float = 18.0
# Forward+ light-frustum reconstruction loses precision beyond this range on
# the Windows/Vulkan presentation path. Presentation particles clamp their own
# clip depth, so the camera projection can stay finite while viewing farther.
const PRESENTATION_SAFE_CAMERA_FAR: float = 1_000_000.0
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
# Fixed-step hard ceiling: the paced loop (see _process) runs at most this
# many steps per frame regardless of the time budget — a safety rail, not
# the throttle. The recorder scene raises it for time-lapse coverage per
# video second (default 16 = unchanged behavior).
## Physics catch-up cap per rendered frame (recorder raises it for time-lapse).
@export var max_steps_per_frame: int = 16
## Simulation time-scale: 1 = real time (default), 0.5 = half speed,
## 2 = 2× time-lapse, etc. The per-frame step cap scales with it, so
## fast-forward stays smooth at any frame rate. Live — no reinit.
@export_range(0.05, 10.0, 0.05) var sim_speed: float = 1.0
## Wall-clock budget for physics per rendered frame: the frame runs at
## most this fraction of the MEASURED frame time in physics (using the
## rolling per-step cost), so a heavy config slows the SIM — reported
## truthfully as the backlog — instead of collapsing the frame rate.
## 0.6 = physics ≤ 60% of each frame (the smooth-run design). 0 = off —
## no budget, the old cap-only behavior (recorder style). Live — no reinit.
@export_range(0.0, 1.0, 0.05) var physics_frame_budget: float = 0.6
## Auto color-align: every ~1.5 s, re-fit the Qi color band to the live
## particles (the fixed-band alternative to Fit/legend). Default OFF: the
## band is stable and the scale never re-anchors on its own (the old
## default-ON aligner sampled the unbounded EY²+EI², so the band chased a
## growing quantity every 1.5 s and the colors constantly increased toward
## white). When ON, the aligner re-fits qi_cycle to the live q_coh spread in
## the bounded channel [1e-6, 0.999] — the same value the instancer maps to
## hue. Clicking Fit or dragging a legend handle turns it off — manual takes
## over. Live — no reinit.
@export var auto_align_colors: bool = false
var _phys_us_ema: float = 500.0      # rolling per-step GPU cost (us; budget input)
var _frame_us_ema: float = 16667.0   # rolling frame time (us; budget input)
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


var field_display_texture: Texture2D = null
signal field_texture_updated(tex: Texture2D)
var _render_texture_rebuild_count: int = 0
# ═══════════════════════════════════════════════════════════════════════
# Lifecycle
# ═══════════════════════════════════════════════════════════════════════

func _apply_vsync() -> void:
	# Live window VSync. The DisplayServer call is a no-op under the
	# headless/dummy driver (verify scenes, import passes) — harmless.
	DisplayServer.window_set_vsync_mode(
		DisplayServer.VSYNC_ENABLED if _vsync_enabled else DisplayServer.VSYNC_DISABLED)

func _apply_field_particles_settings() -> void:
	if _field_particles_saved_settings.is_empty():
		for property_name in FIELD_PARTICLES_SETTINGS:
			_field_particles_saved_settings[property_name] = get(property_name)
		for property in get_property_list():
			if StringName(property.get("name", "")) == &"rotation_stress_enabled":
				_field_particles_saved_settings["rotation_stress_enabled"] = get(
					&"rotation_stress_enabled")
				break
	for property_name in FIELD_PARTICLES_SETTINGS:
		set(property_name, FIELD_PARTICLES_SETTINGS[property_name])
	if _field_particles_saved_settings.has("rotation_stress_enabled"):
		set(&"rotation_stress_enabled", false)


func _restore_field_particles_settings() -> void:
	for property_name in _field_particles_saved_settings:
		set(property_name, _field_particles_saved_settings[property_name])
	_field_particles_saved_settings.clear()


## Switch modes from the live control and rebuild the matching engine and display.
func set_field_particles_enabled(enabled: bool) -> void:
	if enabled == field_particles:
		return
	field_particles = enabled
	if enabled:
		_apply_field_particles_settings()
	else:
		_restore_field_particles_settings()
	reinit()


func _ready() -> void:
	if field_particles:
		_apply_field_particles_settings()
		print("[CassiSim] Field Particles enabled: moving field objects, point-particle physics off")
	_apply_vsync()  # mirror the export (scene load may have set it before ready)
	_fit_initial_condition_to_domain()
	if field_intelligence_enabled and (physics_decoupled or gridless_physics or meshless_mode):
		push_error("[CassiSim] Field intelligence requires the inline grid field (physics_decoupled=false, gridless_physics=false, meshless_mode=false)")
		return
	if rotation_stress_enabled and not physics_decoupled:
		push_error("[CassiSim] Rotation stress requires physics_decoupled=true; the inline duplicate is intentionally unchanged")
		return
	if not _setup_rendering_device():
		push_error("[CassiSim] Aborting startup: no RenderingDevice (headless/dummy renderer?)")
		return
	_field_intelligence = CassiFieldIntelligenceRuntime.new()
	_setup_buffers()
	_setup_multimesh()  # BEFORE _setup_shaders: the instancer uniform set
	field_workbench = FieldWorkbench.new(self)
	_setup_workbench_cursor()
	_setup_shaders()    # binds the multimesh's RD buffer, which must exist
	if gridless_physics and not physics_decoupled:
		_fail_gridless_physics("site-native physics requires physics_decoupled=true")
		return
	# ── Decoupled physics producer (phase A+B+C): the standalone engine runs
	# the core chain on its own worker thread/local RD — grid AND meshless
	# (the Voronoi arm is ported; the tree worker is handed to the engine
	# worker) — and this sim's global-RD buffers become MIRRORS + the render
	# side.
	_decoupled_active = physics_decoupled
	if _decoupled_active:
		if _decoupled_start_engine():
			print("[CassiSim] Decoupled physics producer started (worker local RD)")
		else:
			if gridless_physics:
				_fail_gridless_physics("engine start failed")
				return
			if rotation_stress_enabled:
				push_error("[CassiSim] rotation-stress engine start failed; refusing an inline no-op fallback")
				return
			push_error("[CassiSim] decoupled engine failed to start — falling back to the inline path")
			_decoupled_active = false
			_init_field()
			_init_particles()
			_apply_gravity_calibration()
			_grav_warmup = true
	else:
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
	# Color-as-LUT: bake the real curve at startup (the placeholder stands
	# only for LUT mode + paused + never-dispatched — normally the repaint
	# above already filled the engine and this is the exact same bake).
	if _mm_lut_mode:
		_fill_instancer_pc()
		_bake_color_lut()
		_lut_bake_dirty = false
	print("[CassiSim] Universe ready — grid=%d³ particles=%d xi=%.5f (φ⁶=%.5f)" % [grid_N, N_particles, xi, PHI_6])
	_sim_cam = _find_sibling_camera()
	if _sim_cam != null:
		_sim_cam.make_current()
	_apply_camera_view_range()
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
	if _gridless_failure:
		return
	_update_particle_presentation_viewport()
	_apply_camera_view_range()
	if presentation_profile:
		_update_particle_cull_bounds()


	# Optional presentation layers are renderer-only and allocate lazily.
	# Run the lifecycle outside all compute lists so a live toggle can never
	# invalidate a set currently bound by the render/physics chain.
	_sync_presentation_macro_lod()
	_sync_presentation_trails()
	_sync_rotation_orientation_layer()
	_sync_presentation_volume_history()
	# First-run import race: on a fresh cache the .glsl imports may not have
	# finished when _ready ran — retry until every shader compiles.
	if not _shaders_ready:
		_setup_retry_counter += 1
		if _setup_retry_counter % 30 == 0:
			_free_shaders()
			_setup_shaders()

	# Color-as-LUT (Tier-2): re-bake the 256×1 LUT when the engine band
	# changed (auto-align publishes, manual legend drags, inspector edits,
	# hue_offset/mode flips — all flow through _fill_instancer_pc →
	# _update_lut_bake_sig). Must run OUTSIDE a compute list (texture
	# update), so it happens here, before any physics dispatch.
	if _lut_bake_dirty and _color_lut_tex != null:
		_bake_color_lut()
		_lut_bake_dirty = false
	# LUT-built multimesh with a live LUT-incompatible color config: since
	# 2026-08-14 only base mode 4 (two-axis ρ) remains gated — its
	# per-instance ρ-lightness axis cannot ride the static band LUT (glow/
	# depth ride custom_data channels and ARE applied in LUT mode) — one
	# honest warning.
	if _mm_lut_mode and not _lut_compatible() and not _warned_lut_incompat:
		_warned_lut_incompat = true
		push_warning("[CassiSim] LUT format is active but the live color config is LUT-incompatible (base mode 4 — two-axis ρ lightness) — that per-instance lightness axis still cannot ride the static band LUT, so it is not applied in LUT mode. Use a base mode 0-3 (glow/depth/size VFX are supported in LUT mode) or turn color_lut_mode off + reinit.")

	if playing and _shaders_ready:
		# ── Paced fixed-dt with a TIME BUDGET (the smooth-run design) ────
		# The accumulator requests delta × sim_speed / dt steps — the
		# deterministic contract the verify battery and probes rely on.
		# The per-frame LIMIT is not a step count but a wall-clock budget:
		# at most physics_frame_budget × the measured frame time, using the
		# rolling per-step GPU cost — so a heavy config slows the SIM
		_step_timer += delta * sim_speed
		var n_steps := 0   # shared with the post-batch merge gate below
		if _decoupled_active:
			# ── Decoupled pacing: only the per-frame REQUEST ceiling and the
			# backlog cap. The target accumulates; the ENGINE's
			# record_pending_steps (called from _render_frame) consumes the
			# pending (target − executed) in the frame's list — under-requesting
			# is the truthful backlog (_decoupled_pending).
			# BOOT GATE: during the decoupled bootstrap the engine is still
			# building ICs on its worker thread. Requesting steps then would
			# accumulate _decoupled_target, and the first chain after boot
			# would execute the whole accumulated target at once (the
			# "particles pop in already evolved" artifact). Hold the pacing
			# timer at 0 during boot so the first post-boot request is ~1
			# step and the first chain shows the freshly-initialized cluster
			# near t = 0.
			if _decoupled_boot_wait:
				_step_timer = 0.0
			else:
				var step_cap: int = maxi(max_steps_per_frame, int(ceili(sim_speed)) * max_steps_per_frame)
				while _step_timer >= dt and n_steps < step_cap:
					_step_timer -= dt
					n_steps += 1
				var backlog_cap := 2.0  # sim-seconds of carried catch-up
				if _step_timer > backlog_cap:
					_dropped_steps += int((_step_timer - backlog_cap) / dt)
					_step_timer = backlog_cap
				if n_steps > 0:
					var requested_target := _decoupled_target + n_steps
					var target_limit := requested_target
					if _physics_engine != null and _physics_engine.setup_ready():
						target_limit = int(_physics_engine._executed) + DECOUPLED_LEAD_CAP
					if requested_target > target_limit:
						_dropped_steps += requested_target - target_limit
					_decoupled_target = mini(requested_target, target_limit)
		else:
			var budget_steps := 1_000_000_000 if physics_frame_budget <= 0.0 \
					else int(maxf(physics_frame_budget * _frame_us_ema / maxf(_phys_us_ema, 10.0), 1.0))
			var step_cap: int = maxi(max_steps_per_frame, int(ceili(sim_speed)) * max_steps_per_frame)
			while _step_timer >= dt and n_steps < budget_steps and n_steps < step_cap:
				_step_timer -= dt
				n_steps += 1
			var backlog_cap := 2.0  # sim-seconds of carried catch-up
			if _step_timer > backlog_cap:
				_dropped_steps += int((_step_timer - backlog_cap) / dt)
				_step_timer = backlog_cap
			if n_steps > 0:
				var t0 := Time.get_ticks_usec()
				_run_physics_steps(n_steps)
				var spent := int(Time.get_ticks_usec() - t0)
				_perf_phys_us += spent
				_perf_steps += n_steps
				if spent > 0:
					_phys_us_ema = lerp(_phys_us_ema, float(spent) / float(n_steps), 0.2)
	_perf_frames += 1

	_render_frame()


# Run n physics steps in ONE compute list per frame.
# (Global RD contract: NO submit/sync — illegal on the main instance. The
# list is executed by the renderer's frame machinery at frame end; any
# buffer_get_data readback internally flushes and stalls all frames, which
# is the only sync we need.)
func _run_physics_steps(n_steps: int) -> void:
	if _decoupled_active:
		# Decoupled SYNC path (probes / paused repaints / external callers):
		# the chain records on the render thread; the readbacks self-stall =
		# the sync. The async frame path records from _render_frame instead.
		if _physics_engine == null or n_steps <= 0:
			return
		_decoupled_target += n_steps
		if not _physics_engine.setup_ready():
			return
		_physics_engine.update_bh_header()
		var rebuild_requested: bool = bool(_physics_engine.mesh_rebuild_due())
		if rebuild_requested and not _physics_engine.prepare_mesh_rebuild():
			rebuild_requested = false
		var cl := _rd.compute_list_begin()
		var executed: int = _physics_engine.record_pending_steps(cl, _decoupled_target)
		if rebuild_requested:
			_physics_engine._mesh_rebuild(cl)
			_barrier(cl)
		_rd.compute_list_end()
		if executed > 0:
			_apply_decoupled_publish(_engine_read_publish(true))
		return
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
	# Movable home-window: bh[0].yzw = the field grid's world-origin offset
	# (floats 4/8/12 — zero = the fixed-origin box, bit-identical). The
	# nbody samplers subtract it in the world→grid map; the dual-lattice
	# cell↔cell map is translation-invariant and needs no change.
	_bh_init_bytes.encode_float(4, _window_center.x)
	_bh_init_bytes.encode_float(8, _window_center.y)
	_bh_init_bytes.encode_float(12, _window_center.z)
	# Tree-arm force calibration G_tree = G_N·ML_TREE_G_SCALE rides bh[3].w
	# (float 60, a free header slot — NOT the nbody PC, keeping the nbody
	# push constant at 15 floats so manual 60-byte dispatchers in the verify
	# battery stay valid). The river-calibrated G_N (bh[1].w) inverts the
	# spectral Poisson's implicit V_cell/(4πr²) suppression that the tree's
	# DIRECT sum lacks (particle_vanish.md (b)); the scalar renormalizes the
	# tree force to the IC |a|≈M/r² convention. 1.0 off-tree (river bit-identical).
	_bh_init_bytes.encode_float(60, ML_TREE_G_SCALE if (meshless_mode and meshless_gravity) else 1.0)
	var _off_dual: Vector3 = _extents() / float(grid_N)
	_bh_init_bytes.encode_float(16, _off_dual.x)
	_bh_init_bytes.encode_float(20, _off_dual.y)
	_bh_init_bytes.encode_float(24, _off_dual.z)
	_rd.buffer_update(_bh_buf, 0, _bh_init_bytes.size(), _bh_init_bytes)
	# ── Meshless tree gravity (THREADED): the worker rebuilds + walks the
	# tree on its own thread/local-RD before the steps, so mode-5 nbody
	# reads a fresh _ml_tree_grad. All gates off by default → the default
	# battery is bit-identical. The frame-1 submission blocks (bootstrap —
	# step 1 needs a fresh gradient); every later frame is non-blocking.
	# The nbody mode-5 seam + walk TargetPos-binding fixes remain:
	# _step_dispatches encodes the effective mode 5.0, and the walk reads
	# _pos_buf for targets — both still required for the worker's gradient
	# to reach the particles.
	var tree_arm := meshless_mode and meshless_gravity and _ml_ready
	if tree_arm:
		_ml_tree_nsrc = 2 * ML_N1 * ML_N1 * ML_N1
		_tree_worker_frame()
	if field_intelligence_enabled:
		_update_field_intelligence_params()
		if field_intelligence_render:
			_ensure_field_intelligence_render_target()
	var cl = _rd.compute_list_begin()

	# ── Snapshot roll (pre-batch): pos_prev = pos ───────────────────
	# One blend dispatch BEFORE the step batch captures the pre-batch state
	# (== the previously rendered state) into pos_prev, so the post-batch
	# interpolation below can retrace the last RENDERED positions. alpha =
	# 2.0 is the ROLL MARKER: it tells this dispatch from the post-batch
	# one (dormant alpha == 1.0 could not — both would roll and clobber the
	# snapshot); the shader rolls pos_prev only when alpha > 1.0 and clamps
	# its interpolation to [0, 1], so the pos_render side-effect stays
	# exactly pos. The first full barrier inside _step_dispatches (clear →
	# deposit) orders this dispatch's pos reads before the batch's first
	# pos write.
	# The roll is dormant at the pinned _interp_alpha == 1.0 (review_sim.md
	# #4): its only consumer is the interp blend below, whose mix(prev, curr,
	# 1.0) == curr ignores pos_prev — so the roll dispatch is gated away on
	# the default path (one fewer full-N blend dispatch per frame). If a
	# decoupled producer ever sets alpha < 1.0 the roll runs exactly as
	# before.
	if _interp_alpha < 1.0 and _blend_sh.is_valid() and N_particles > 0:
		_blend_pc.encode_float(0, 2.0)  # roll marker (> 1.0)
		_blend_pc.encode_float(4, 0.0)  # shader subtracts the supplied window origin
		_blend_pc.encode_float(8, _render_window_origin().x)
		_blend_pc.encode_float(12, _render_window_origin().y)
		_blend_pc.encode_float(16, _render_window_origin().z)
		_rd.compute_list_bind_compute_pipeline(cl, _blend_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_blend_0, 0)
		_rd.compute_list_set_push_constant(cl, _blend_pc, _blend_pc.size())
		_rd.compute_list_dispatch(cl, ceili(float(N_particles) / 64.0), 1, 1)

	for _s in range(n_steps):
		_step_dispatches(cl)
	if field_intelligence_enabled and field_intelligence_render:
		_record_field_intelligence_view(cl)
	# ── q-histogram (auto color-align): one strided pass per frame while
	# auto_align_colors is on and the Qi rainbow is the active source. The
	# field's barrier from the last step gives the q reads visibility.
	# Runs even under suppress_readbacks: its 512 B readback every 1.5 s is
	# negligible next to the multi-MB diagnostics that toggle suppresses. ──
	var color_base: int = int(particle_color_mode) & 0xF
	if _qhist_pipe.is_valid() and _us_qhist_0.is_valid() and auto_align_colors \
			and color_base >= 2 and color_base <= 4 and N_particles > 0:
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
		_qhist_pc_bytes.encode_float(40, -_window_center.x)
		_qhist_pc_bytes.encode_float(44, -_window_center.y)
		_qhist_pc_bytes.encode_float(48, -_window_center.z)
		# True-boxless arm (boxless_field_design.md): when the moving-Voronoi mesh
		# is live and the toggle is on, the sampler reads coherence from the sites
		# (coordinate-independent, no window/extent/%N). Off (default) = dead branch.
		var _boxless_on: float = 1.0 if (boxless_field and meshless_mode and _ml_ready) else 0.0
		_qhist_pc_bytes.encode_float(52, _boxless_on)
		_qhist_pc_bytes.encode_float(56, float(2 * ML_N1 * ML_N1 * ML_N1))
		_rd.compute_list_bind_compute_pipeline(cl, _qhist_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_qhist_0, 0)
		_rd.compute_list_set_push_constant(cl, _qhist_pc_bytes, _qhist_pc_bytes.size())
		var qh_threads := ceili(float(N_particles) / 16.0)
		_rd.compute_list_dispatch(cl, ceili(qh_threads / 64.0), 1, 1)
	# ── Interpolation dispatch (post-batch): pos_render = mix(pos_prev,
	# pos, _interp_alpha) ──
	# The instancer below is bound to _us_inst_0_render, which reads
	# pos_render — the interpolated render snapshot. DORMANT:
	# _interp_alpha = 1.0 → pos_render == pos (mix(x, y, 1.0) = y exactly),
	# so rendering is bit-identical to today; the decoupled producer will
	# vary alpha later. The barrier after it gives the instancer's
	# pos_render reads their memory visibility (consecutive dispatches have
	# execution ordering but no implicit memory visibility).
	if _blend_sh.is_valid() and N_particles > 0:
		_blend_pc.encode_float(0, _interp_alpha)
		_blend_pc.encode_float(4, 0.0)  # shader subtracts the supplied window origin
		_blend_pc.encode_float(8, _render_window_origin().x)
		_blend_pc.encode_float(12, _render_window_origin().y)
		_blend_pc.encode_float(16, _render_window_origin().z)
		_rd.compute_list_bind_compute_pipeline(cl, _blend_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_blend_0, 0)
		_rd.compute_list_set_push_constant(cl, _blend_pc, _blend_pc.size())
		_rd.compute_list_dispatch(cl, ceili(float(N_particles) / 64.0), 1, 1)
	_barrier(cl)  # blend pos_render write → instancer read
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
		# RENDER variant: binding 0 reads _pos_render_buf (the post-batch
		# interpolation snapshot) — == _pos_buf while _interp_alpha == 1.0,
		# so the rendered frame is bit-identical today.
		if _ml_boxless_on():
			_rd.compute_list_bind_uniform_set(cl, _us_inst_0_lut_render_boxless if _lut_active() else _us_inst_0_render_boxless, 0)
		else:
			_rd.compute_list_bind_uniform_set(cl, _us_inst_0_lut_render if _lut_active() else _us_inst_0_render, 0)
		_rd.compute_list_set_push_constant(cl, _instancer_pc_bytes, _instancer_pc_bytes.size())
		_rd.compute_list_dispatch(cl, ipg, 1, 1)
	_record_presentation_trails(cl, _us_trail_0)
	_rd.compute_list_end()
	if field_intelligence_enabled and field_intelligence_render \
			and field_display_texture != null:
		field_texture_updated.emit(field_display_texture)

	# Inline simulation owns the global RenderingDevice and keeps the
	# renderer's command ordering intact. Meshless topology rebuilds are
	# therefore confined to the decoupled engine's private local RD path;
	# no standalone rebuild is issued from this global-RD branch.
	# Merge cadence: accumulate the inline batch's steps for the merge gate
	# in _render_frame (the merge itself must run there — the ONLY context
	# where global-RD lists + buffer_get_data readbacks execute). Reached
	# only on the inline path (the decoupled branch returns above).
	if particle_merge:
		_merge_step_counter += n_steps


# No-op on the global RD: readbacks self-stall (kept so verify scripts and
# external callers can call it unconditionally).
func _ensure_synced() -> void:
	pass


## Cassi particle-merge pass — runs the verified merge kernel
## (compute/cassi_particle_merge.glsl) on the live particle state, as its own
## standalone compute-list sequence AFTER the physics batch. Returns the total
## merges this pass (0 = none / not ready). From _process (every frame) and
## from verify scenes that drive steps directly via _run_physics_steps.
## NOTE: keep the merge-cycle logic here in sync with the twin
## `_run_merge_pass` in cassi_physics_engine.gd (same batched chain, same
## per-cycle in-list cc zero). The two differ only in sync style (this sim:
## readback self-stall; engine: explicit submit+sync).
##
## Small verification problems execute merge cycles in batches of
## MERGE_BATCH_CYCLES, retaining the established early-exit behavior and one
## self-stalling count readback per batch. Production clouds execute exactly
## one persisted (neighbor-cell, entry) phase per cadence; no single frame can
## expand back into a multi-cycle TDR burst. Both paths keep the complete
## fold→zero-cc→count→scan→fill→best→hop chain in one compute list with
## barriers, and mode 7 clears cc before every count.
##
## The large-cloud phase is split across pass_mode's fractional bits (cell)
## and cyc_slot (entry round), keeping both fields exact throughout N entries.
func _run_merge_pass() -> int:
	if not particle_merge or not _merge_shader.is_valid() or not _merge_pipe.is_valid() \
			or not _us_merge_0.is_valid() or not _merge_alive_buf.is_valid() \
			or not _scan_pipe.is_valid() or not _us_scan_0.is_valid() \
			or N_particles <= 0:
		return 0
	_fill_merge_pc()
	# reset in its own list; force its completion + visibility with a readback
	# (global RD: separate compute_list_end()s don't guarantee cross-list
	# memory visibility; buffer_get_data self-stalls and executes pending
	# work, but ONLY from the frame context — see the _render_frame hook).
	# F1: cc is re-zeroed ON-GPU per cycle (mode 7 at the top of the cycle
	# batch, before every count) — NO pre-loop host zero needed; the old
	# pre-loop cc zero was redundant with the batched mode-7 zero and is gone.
	_zero_merge_bytes(_merge_mc_buf, MERGE_MAX_CYCLES)    # all count slots 0
	var cl0 := _rd.compute_list_begin()
	_merge_bind_dispatch(cl0, 0.0)   # reset: alive=1, mass=pos.w, mom/cen=m p/m v
	_rd.compute_list_end()
	_merge_read_uint()   # forced sync → reset visible
	# Keep the any-q readback for small gates. At production counts it would
	# query every particle before the deliberately time-sliced pair pass.
	if N_particles <= CassiMergeCommon.FULL_PAIR_SCAN_PARTICLE_LIMIT:
		var cla := _rd.compute_list_begin()
		_merge_bind_dispatch(cla, 8.0)
		_rd.compute_list_end()
		if int(_rd.buffer_get_data(_merge_cc_buf, 0, 4).decode_u32(0)) == 0:
			return 0
	var total := 0
	var cyc := 0
	var time_sliced := N_particles > CassiMergeCommon.FULL_PAIR_SCAN_PARTICLE_LIMIT
	while cyc < MERGE_MAX_CYCLES:
		var ncyc := 1 if time_sliced else mini(MERGE_BATCH_CYCLES, MERGE_MAX_CYCLES - cyc)
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
			var pair_phase := _merge_pair_phase
			_merge_pair_phase = CassiMergeCommon.next_pair_phase(_merge_pair_phase, N_particles)
			_merge_bind_dispatch(cl, 4.0, pair_phase)   # best[i], sink[i]
			_rd.compute_list_add_barrier(cl)
			_merge_bind_dispatch(cl, 5.0, cyc + c)     # hop → mc[cyc+c]
			_rd.compute_list_add_barrier(cl)           # next cycle's fold sees this hop
		_rd.compute_list_end()
		var counts := _merge_read_counts()   # self-stalling: executes the batch + reads all slots
		var batch_result := CassiMergeCommon.merge_batch_result(counts, cyc, ncyc)
		total += batch_result.x
		_merge_cycles_run += ncyc
		cyc += ncyc
		if time_sliced or batch_result.y == 0:
			break   # large clouds resume at the next phase/cadence
	var clf := _rd.compute_list_begin()
	_merge_bind_dispatch(clf, 6.0)   # finalize: survivor masses → pos.w / dead = 0
	_rd.compute_list_end()
	if total > 0:
		print("[CassiSim] merge pass: %d merges (%d cycles)" % [total, _merge_cycles_run])
	return total


const MERGE_MAX_CYCLES := 16


## Effective merge cadence in STEPS: the explicit export, else AUTO = 1/2
## of the R_m reaction budget (see the merge_cadence_steps export comment).
## Default 1 = per job — local runs keep the STEP-1 early-out and large clouds
## bound each job to one persisted source-shard/cell/entry phase.
## Cheap: a few multiplies, called once per gate check.
func _merge_cadence_eff() -> int:
	if merge_cadence_steps > 0:
		return merge_cadence_steps
	return maxi(1, int(0.5 * _extent_min() / float(maxi(grid_N, 1)) / maxf(dt, 1e-6)))
## Small verification problems batch this many complete merge cycles before
## their count readback. Large clouds ignore the batch size and run exactly
## one persisted pair phase per cadence.
const MERGE_BATCH_CYCLES := 4


## The merge PC as 26 floats: pass_mode@15 uses fractional bits for the
## large-cloud neighbor-cell phase, cyc_slot@23 carries its entry round,
## boxless@24 selects site-direct coherence, and n_sites@25 guards that read.
## CassiMergeCommon owns the layout so the engine twin cannot drift.
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
		"boxless": _ml_boxless_on() and particle_merge,   # gated: boxless mesh live AND merge on → site-direct read (merge_boxless_prereg.md)
		"n_sites": _ml_sites_cpu.size() / 4,               # Voronoi site count (nearest-site read guard)
	}

## Encode the invariant portion once per merge pass. Individual dispatches
## only change the pass selector and cycle/phase slot.
func _fill_merge_pc() -> void:
	var values := _merge_pc_values()
	for i in range(26):
		_merge_pc_bytes.encode_float(i * 4, values[i])


## Bind the merge pipeline/set/PC and dispatch one pass mode into the open
## compute list `cl` (N_particles threads). The caller fills the invariant PC
## fields once per chain; only the selector fields change between dispatches.
func _merge_bind_dispatch(cl: int, pass_mode: float, cyc_slot := 0) -> void:
	var encoded_mode := pass_mode
	var encoded_slot := float(cyc_slot)
	if int(pass_mode) == 4 and N_particles > CassiMergeCommon.FULL_PAIR_SCAN_PARTICLE_LIMIT:
		var phase_pc := CassiMergeCommon.pair_phase_pc(int(cyc_slot))
		encoded_mode = phase_pc.x
		encoded_slot = phase_pc.y
	_merge_pc_bytes.encode_float(15 * 4, encoded_mode)
	_merge_pc_bytes.encode_float(23 * 4, encoded_slot)
	_rd.compute_list_bind_compute_pipeline(cl, _merge_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_merge_0, 0)
	_rd.compute_list_set_push_constant(cl, _merge_pc_bytes, _merge_pc_bytes.size())
	_rd.compute_list_dispatch(cl, ceili(float(N_particles) / 256.0), 1, 1)


## FIX B (batched): record the 4 on-GPU exclusive-scan passes into the OPEN
## compute list `cl` (cassi_exclusive_scan.glsl): cc -> cs (exclusive), ch =
## cs (the per-cell fill head). Intra-list barriers for pass-to-pass
## visibility; the CALLER owns list begin/end/sync — the batched merge folds
## the scan into the batch list so the whole batch is ONE self-stalling
## readback (the scan reads cc, which the batch zeroed per cycle just before).
func _merge_scan_into(cl: int) -> void:
	var E := _merge_hash_total
	var nb1 := (E + 255) / 256
	var nb2 := _merge_nb2
	_merge_scan_pc_bytes.encode_float(2 * 4, float(_merge_nb1a))
	# pass 1: cc -> cs (block-local exclusive) + L1 totals -> scr[b]
	_merge_scan_pc_bytes.encode_float(0, float(E))
	_merge_scan_pc_bytes.encode_float(4, 1.0)
	_scan_dispatch(cl, nb1)
	_rd.compute_list_add_barrier(cl)
	# pass 2: scan scr(L1) in place -> loc1 + L2 totals -> scr[nb1a + bb]
	_merge_scan_pc_bytes.encode_float(0, float(nb1))
	_merge_scan_pc_bytes.encode_float(4, 2.0)
	_scan_dispatch(cl, nb2)
	_rd.compute_list_add_barrier(cl)
	# pass 3: single workgroup scan of L2 -> exclusive (nb2 <= 256)
	_merge_scan_pc_bytes.encode_float(0, float(nb2))
	_merge_scan_pc_bytes.encode_float(4, 3.0)
	_scan_dispatch(cl, 1)
	_rd.compute_list_add_barrier(cl)
	# pass 4: cs += carries; ch = cs
	_merge_scan_pc_bytes.encode_float(0, float(E))
	_merge_scan_pc_bytes.encode_float(4, 4.0)
	_scan_dispatch(cl, nb1)
	_rd.compute_list_add_barrier(cl)


func _scan_dispatch(cl: int, groups: int) -> void:
	_rd.compute_list_bind_compute_pipeline(cl, _scan_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_scan_0, 0)
	_rd.compute_list_set_push_constant(cl, _merge_scan_pc_bytes, _merge_scan_pc_bytes.size())
	_rd.compute_list_dispatch(cl, maxi(groups, 1), 1, 1)


## Force the just-recorded merge compute list to actually execute AND read
## all MERGE_MAX_CYCLES per-cycle merge counts in ONE device drain. The
## global RD does not submit lists from __ready/__process outside the
## renderer's frame; a submit+sync (or a self-stalling readback) is required
## for the merge's between-list orderings to be correct — the batched pass
## needs exactly one per batch.
func _merge_read_counts() -> PackedInt32Array:
	var d := _rd.buffer_get_data(_merge_mc_buf, 0, MERGE_MAX_CYCLES * 4)
	var out := PackedInt32Array()
	out.resize(MERGE_MAX_CYCLES)
	if d.size() >= MERGE_MAX_CYCLES * 4:
		for k in range(MERGE_MAX_CYCLES):
			out[k] = int(d.decode_u32(k * 4))
	return out


func _merge_read_uint() -> int:
	var d := _rd.buffer_get_data(_merge_mc_buf, 0, 4)
	return int(d.decode_u32(0)) if d.size() >= 4 else 0


func _zero_merge_bytes(buf: RID, count: int) -> void:
	var z := PackedByteArray(); z.resize(count * 4); z.fill(0)
	_rd.buffer_update(buf, 0, z.size(), z)




# Full memory barrier inside an open compute list. Consecutive dispatches
# have EXECUTION ordering but no implicit MEMORY visibility — without this,
# a later dispatch can read stale data written by an earlier one (races
# were observed in the deposit→poisson and FFT chains). The barrier makes
# the visibility explicit.
func _barrier(cl: int) -> void:
	_rd.compute_list_add_barrier(cl)


# ═══════════════════════════════════════════════════════════════════════
# Decoupled physics producer (the standalone engine on a worker thread)
# ═══════════════════════════════════════════════════════════════════════
# The engine owns a worker-created local RenderingDevice and runs the core
# chain (deposit → Poisson → two-fluid → BH → gradient → KDK) OFF the main
# thread. ONE shared RD: the sim's render sets bind the ENGINE's LIVE
# buffers directly — there are no host-side mirrors and no mirror
# re-uploads. Every frame the sim records the render list: the blend
# interpolation (pos_render = mix(pos_prev, pos, alpha); the −c window
# seam only — no roll, no packed half-pair transport) + instancer + qhist.
# The publish is BOOKKEEPING + the accepted readback group (telemetry +
# the tracker COM at cadence); it carries no snapshot.

## Per-submit job bookkeeping: whether this job's publish reads the
## accepted readback group (telemetry + the tracker COM). The publish
## carries NO snapshot — the render reads the engine's live buffers — so
## P3 (M0b-P): build the publish dict at the job boundary — the readbacks
## (telemetry + the tracker COM) are the accepted group; the snapshots are
## gone (the render reads the engine's live buffers). force_telemetry:
## the sync path always reads; the frame path reads at the cadence.
func _engine_read_publish(force_telemetry: bool) -> Dictionary:
	var eng: Object = _physics_engine
	if field_particles and not eng.refresh_field_particle_readout():
		push_error("[CassiSim] Field Particles readout failed")
	var pub := {"executed": eng._executed, "step_count": eng._step_count, "t": eng._time}
	if force_telemetry:
		pub["telemetry"] = eng.readback_telemetry()
		if rotation_stress_enabled:
			pub["rotation"] = eng.rotation_publish_state(16)
		if home_window_enabled and Time.get_ticks_msec() - _win_track_last_ms >= COM_TRACK_CADENCE_MS:
			var c: Array = eng.read_com()
			if not c.is_empty():
				pub["com"] = c
	return pub
func _fail_gridless_physics(reason: String) -> void:
	push_error("[CassiSim] gridless physics unavailable — refusing raster fallback: %s" % reason)
	_gridless_failure = true
	playing = false
	# These uniform sets reference the engine's live buffers. Release the
	# renderer-only profile resources before stopping that producer so a
	# fail-closed gridless transition cannot leave stale presentation RIDs.
	_free_macro_lod_multimesh()
	_free_trail_multimesh()
	_free_rotation_orientation_multimesh()
	_free_volume_history_resources()
	_decoupled_boot_wait = false
	if _physics_engine != null:
		_physics_engine.stop_threaded()
		_physics_engine = null
	_decoupled_active = false
	if _mmi != null:
		_mmi.visible = false



## Build the engine cfg from the live exports (an explicit dict with the
## same names the engine's setup() reads — never pass the sim node), start
## the threaded runner and bootstrap-wait until the engine's setup is ready
## (the render then binds the engine's live buffers directly — no mirror
## upload).
func _decoupled_start_engine() -> bool:
	_rotation_snapshot = {"enabled": false}
	if _physics_engine == null:
		_physics_engine = load("res://scripts/cassi_physics_engine.gd").new()
	var cfg := {
		"grid_N": grid_N, "N_particles": N_particles, "dt": dt,
		"xi": xi, "softening": softening,
		"cluster_radius": cluster_radius, "num_clusters": num_clusters,
		"cluster_separation": cluster_separation, "merger_speed": merger_speed,
		"source_strength": source_strength,
		"qi_condensation_threshold": qi_condensation_threshold,
		"bh_acc_rate": bh_acc_rate, "bh_max_age": bh_max_age,
		"black_holes_enabled": black_holes_enabled,
		"gravity_mode": gravity_mode,
		"realsim_drag": realsim_drag, "realsim_viscosity": realsim_viscosity,
		"realsim_friction": realsim_friction,
		"river_calibrate_gn": river_calibrate_gn,
		"river_pi_ref": river_pi_ref, "river_q_ref": river_q_ref,
		"field_attractor_init": field_attractor_init,
		"freeze_field": freeze_field,
		"home_window": home_window_enabled,
		"window_center": _window_center,
		"initial_radius_fraction": initial_radius_fraction,
		"initial_condition": initial_condition,
		"initial_v_circ_factor": initial_v_circ_factor,
		"box_aspect": box_aspect, "box_scale": box_scale,
		"gradient_order": gradient_order, "dual_grid": dual_grid,
		"multi_rung_seed": multi_rung_seed, "multi_rung_count": multi_rung_count,
		"multi_rung_amp": multi_rung_amp, "multi_rung_base_scale": multi_rung_base_scale,
		"meshless_mode": meshless_mode, "meshless_gravity": meshless_gravity,
		"tree_hierarchical_refit": tree_hierarchical_refit,
		"gridless_physics": gridless_physics,
		"field_particles": field_particles,
		"field_particles_single_seed": field_particles_single_seed,
		"boxless_field": boxless_field,
		"winding_coupling": winding_coupling,
		"q_weighted_com": q_weighted_com,
		"coherence_theta": coherence_theta,
		"coherence_theta_alpha": coherence_theta_alpha,
		"mode": mode,
		"particle_merge": particle_merge,
		"merge_cadence_steps": merge_cadence_steps,
		"merge_subsonic": merge_subsonic,
		"merge_virial": merge_virial,
		"merge_sel_gate": merge_sel_gate,
		"rotation_stress_enabled": rotation_stress_enabled,
		"rotation_grid_N": rotation_grid_N,
		"rotation_rungs": rotation_rungs,
		"rotation_field_inertia": rotation_field_inertia,
		"rotation_c_t": rotation_c_t,
		"rotation_c_l": rotation_c_l,
		"rotation_scale_omega": rotation_scale_omega,
		"rotation_attenuation": rotation_attenuation,
		"rotation_exchange_rate": rotation_exchange_rate,
		"rotation_reservoir_inertia": rotation_reservoir_inertia,
		"rotation_lower_reservoir_coupling": rotation_lower_reservoir_coupling,
		"rotation_upper_reservoir_coupling": rotation_upper_reservoir_coupling,
		"bh_accretion": bh_accretion,
		"bh_accretion_radius": bh_accretion_radius,
	}
	# M0b-P (one-RD): the engine runs its chains on THIS sim's global RD —
	# no worker-local device, no mirrors (P3). The worker records into the
	# shared queue; the renderer's frame machinery submits; the engine
	# never submit/syncs (the "Only local devices can submit and sync"
	# contract — the engine's rd_global branch already implements it).
	cfg["rd"] = _rd
	cfg["rd_global"] = true
	cfg["owns_rd"] = false
	# M0b-P: the tree worker is NOT created in decoupled mode — the tree
	# build+walk runs in the engine's own list (M0) on the shared RD; the
	# worker's local RD was the third device in the topology (and its boot
	# cost ~1 s). The tree CADENCE still ships (the engine's in-list gate —
	# the engine's default would otherwise be every chain).
	cfg["tree_cadence"] = _tree_local_cadence
	if ic_seed != 0:
		cfg["seed"] = ic_seed
	if not _physics_engine.start_threaded(cfg):
		return false
	# FIX A (non-blocking bootstrap): queue the first job WITHOUT blocking the
	# main thread on the worker's setup() (the old path froze the main thread
	# ~3.5 s while the 2.5M-particle ICs initialized). The worker processes it
	# right after setup(); the first snapshot lands via poll(). _decoupled_active
	# is set true by the caller; _decoupled_boot_wait gates rendering until the
	# first publish arrives so the sim never renders uninitialized mirrors.
	_decoupled_target = 0
	_decoupled_pending = 0
	_last_publish_ms = 0
	_batch_ema_ms = 16.7
	_step_count = 0
	_merge_step_counter = 0
	_merge_pair_phase = 0
	_merge_dc_first_completion_logged = false
	_time = 0.0
	_decoupled_initial_render_pending = true
	_decoupled_boot_wait = true
	_decoupled_boot_start_ms = Time.get_ticks_msec()
	_decoupled_boot_last_progress_ms = 0
	# Hide the particle MultiMesh during the IC init: the instance buffer is
	# still its initial zeroed state, so without this all N instances render
	# piled at the origin (the "single square at origin" startup artifact).
	# _decoupled_poll_and_render restores visibility after the first populated
	# instancer list, or the timeout→inline fallback restores it immediately.
	if _mmi != null:
		_mmi.visible = false
	print("[CassiSim] decoupled bootstrap queued (non-blocking) — main thread free")
	return true


## Apply a fresh engine publish: refresh time/step/telemetry bookkeeping
## and the interpolation timing. The publish carries NO snapshot — the
## render reads the engine's live buffers directly — so there is no mirror
## pair to shift and no mirror upload. The accepted readback group
## (telemetry + the tracker COM, read at the cadence) rides the publish;
## the interpolation timing (physics ms/step + the alpha sweep) is derived
## from the publish interval.
func _apply_decoupled_publish(pub: Dictionary) -> void:
	# Time / step / truthful backlog on EVERY publish.
	_time = float(pub.get("t", _time))
	_step_count = int(pub.get("step_count", _step_count))
	_decoupled_pending = maxi(_decoupled_target - int(pub.get("executed", 0)), 0)
	var tel: Dictionary = pub.get("telemetry", {})
	if not tel.is_empty():
		_q_mean = float(tel.get("q_mean", _q_mean))
		_q_min = float(tel.get("q_min", _q_min))
		_q_max = float(tel.get("q_max", _q_max))
		_pi_min = float(tel.get("pi_min", _pi_min))
		_pi_max = float(tel.get("pi_max", _pi_max))
		_pi_sat_hi_frac = float(tel.get("pi_sat_hi_frac", _pi_sat_hi_frac))
		_pi_sat_lo_frac = float(tel.get("pi_sat_lo_frac", _pi_sat_lo_frac))
		_rho_guard_hits = int(tel.get("rho_guard_hits", _rho_guard_hits))
		_eps_mean = float(tel.get("eps_mean", _eps_mean))
		_hubble = float(tel.get("hubble", _hubble))
		_scale_factor = float(tel.get("scale_factor", _scale_factor))
		_gn_eff = float(tel.get("gn_eff", _gn_eff))
	if pub.has("rotation"):
		var rotation_pub: Dictionary = pub["rotation"]
		_rotation_snapshot = rotation_pub.duplicate(true)
	# P3 (M0b-P one-RD): the publish carries NO snapshot — the render reads
	# the ENGINE's live buffers directly (the render sets re-point on the
	# shared RD); the mirrors + 12 MB uploads + the pot mirror are gone.
	# The COM (the window tracker's source) ships when the tracker is due.
	if pub.has("com"):
		var c: Array = pub["com"]
		_pub_com = Vector3(float(c[0]), float(c[1]), float(c[2]))
	# Interpolation timing: publish-interval wall time per executed step
	# (the decoupled "physics ms/step" number). The blend's alpha is pinned
	# at 1.0 — the render list executes AFTER the chain in the shared queue,
	# so the render IS the live engine state (no interp lag to smooth).
	var now_ms := Time.get_ticks_msec()
	var prev_exec := int(pub.get("executed", 0))
	if _last_publish_ms > 0:
		_batch_ema_ms = lerp(_batch_ema_ms, maxf(float(now_ms - _last_publish_ms), 1.0), 0.2)
		_perf_phys_us += int(float(now_ms - _last_publish_ms) * 1000.0)
		_perf_steps += prev_exec - _executed_prev
	_executed_prev = prev_exec
	_last_publish_ms = now_ms


## MOVABLE HOME-WINDOW tracker (perf-decomp 2026-08-15): every ~2 s, when
## home_window_enabled and decoupled, compute the structure's center of
## mass over a subsample of the published position mirror and nudge the
## field-grid origin toward it (soft speed limit: ≤ 0.25·min_extent per
## tick — the grid never jerks). The offset flows into the bh header
## (bh[0].yzw), the deposit PC (off = −c / h/2 − c), the blend render seam
## (pos_render − c) and the qhist PC — every world→grid map becomes
## window-relative; at c = 0 all terms vanish and behavior is bit-identical
## to the fixed-origin box.
func _track_window_center() -> void:
	if not home_window_enabled or not _decoupled_active:
		return
	var now := Time.get_ticks_msec()
	if now - _win_track_last_ms < COM_TRACK_CADENCE_MS:
		return
	_win_track_last_ms = now
	# P3 (M0b-P one-RD): the host-side position mirror is gone — the ENGINE
	# computes the subsampled COM at its job boundary (track_window meta)
	# and ships it in the publish; this tracker consumes it.
	if not _pub_com.is_finite():
		return   # no COM published yet (engine still booting)
	var com := _pub_com
	var ext := _extents()
	var max_move: float = COM_MOVE_CAP_FRAC * minf(minf(ext.x, ext.y), ext.z)
	var d := com - _window_center
	var dist := d.length()
	# Dead band: skip the move entirely when the COM displacement is below a
	# small fraction of the cap (2% — the envelope tracker's DEAD_BAND_FRAC
	# value), so percentile noise never nudges the window.
	if dist < max_move * COM_DEAD_BAND_FRAC:
		return
	if dist > max_move:
		d = d.normalized() * max_move
	_window_center += d
	if _physics_engine != null:
		_physics_engine._window_center = _window_center
		if boxless_field and meshless_mode:
			_physics_engine.publish_render_query(d)
		_physics_engine._mesh_rebuild_pending = true
	print("[CassiSim] window -> (%.1f, %.1f, %.1f)  COM (%.1f, %.1f, %.1f)  t=%.1f s"
			% [_window_center.x, _window_center.y, _window_center.z, com.x, com.y, com.z, float(now) / 1000.0])


## TRACKING-ENVELOPE tracker (B-build piece 3 — the "box stops being
## fixed" for the LIVE sim): every ~2 s, when tracking_envelope and
## decoupled, run the EnvelopeTracker on a deterministic compact GPU sample
## of the ENGINE's live position buffer. The occupancy pass reads only the
## selected positions back (at most 8192 vec4s), then the existing CPU
## percentile/q-gate path publishes the window state.
## The fit publishes the THREE state slots the b_track probe proved: the
## window origin, the uniform box_scale (= tracker.extent.x / the ORIGINAL
## box x — TOTAL vs original, never cumulative), and the bh header's per-axis
## half-extents (bytes 36/40/44 — the per-frame 576 B refresh persists them).
## The ENGINE's state is written too (the decoupled engine owns the physics
## box: its own box_scale/_window_center/_bh_init_bytes — the engine's
## update_bh_header + its per-step PC fills pick the new values up before the
## frame's list); the sim's mirrors stay aligned for the render seam. OFF:
## the whole path is gated — the fixed box, bit-identical.

func _capture_envelope_sample() -> bool:
	if N_particles <= 0 or not _occ_shader.is_valid() or not _occ_pipe.is_valid() \
			or not _occ_buf.is_valid() or not _occ_sample_buf.is_valid() \
			or _occ_pc_bytes.size() < 40:
		return false
	var n_sample := mini((N_particles + 31) / 32, ENVELOPE_SAMPLE_MAX)
	var stride := maxi(32, int(N_particles / maxi(n_sample, 1)))
	var ext := _extents()
	var lim := ext * 0.85
	var occ_set: RID
	if _decoupled_active:
		# Never sample the dormant sim buffer while the decoupled engine is
		# booting. Its zero positions look like a real point envelope and
		# collapse the live site window to the one-unit minimum.
		if _decoupled_boot_wait or not _us_occ_0_dc.is_valid():
			return false
		occ_set = _us_occ_0_dc
	else:
		occ_set = _us_occ_0
	if not occ_set.is_valid():
		return false
	_occ_pc_bytes.encode_float(0, float(N_particles))
	_occ_pc_bytes.encode_float(4, float(n_sample))
	_occ_pc_bytes.encode_float(8, float(stride))
	_occ_pc_bytes.encode_float(12, lim.x)
	_occ_pc_bytes.encode_float(16, lim.y)
	_occ_pc_bytes.encode_float(20, lim.z)
	_occ_pc_bytes.encode_float(24, ext.x)
	_occ_pc_bytes.encode_float(28, ext.y)
	_occ_pc_bytes.encode_float(32, ext.z)
	_occ_pc_bytes.encode_float(36, float(n_sample))
	_rd.buffer_update(_occ_buf, 0, _occ_zero_bytes.size(), _occ_zero_bytes)
	var ocl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(ocl, _occ_pipe)
	_rd.compute_list_bind_uniform_set(ocl, occ_set, 0)
	_rd.compute_list_set_push_constant(ocl, _occ_pc_bytes, _occ_pc_bytes.size())
	_rd.compute_list_dispatch(ocl, ceili(float(n_sample) / 256.0), 1, 1)
	_rd.compute_list_end()
	var sample_bytes := n_sample * 16
	var raw := _rd.buffer_get_data(_occ_sample_buf, 0, sample_bytes)
	if raw.size() < sample_bytes:
		return false
	_envelope_sample_positions = raw.to_float32_array()
	return _envelope_sample_positions.size() >= n_sample * 4

func _track_envelope_window() -> void:
	if not tracking_envelope or not _decoupled_active or _physics_engine == null \
			or not _physics_engine.setup_ready() or _decoupled_boot_wait \
			or not _us_occ_0_dc.is_valid():
		return
	var now := Time.get_ticks_msec()
	if now - _env_track_last_ms < ENV_TRACK_CADENCE_MS:
		return
	_env_track_last_ms = now
	if _env_tracker == null:
		_env_tracker = EnvelopeTracker.new()
		_env_orig_box = Vector3(box_aspect.x, box_aspect.y, box_aspect.z) * (cluster_radius * 1.5)
		# The live engine starts at the exported box_scale. Seed the tracker
		# with that same physical extent; starting at scale-1 would make the
		# first fit shrink a scale-5 IC out of its own force window.
		_env_applied_scale = maxf(box_scale, 1e-3)
		_env_tracker.extent = _env_orig_box * _env_applied_scale
		_env_applied_center = _window_center
		_env_target_center = _window_center
		_env_target_scale = _env_applied_scale
	var eng: Object = _physics_engine
	if q_weighted_com and (
			not bool(eng.get("_ml_ready"))
			or not bool(eng.get("_meshless_query_ready"))):
		return
	if not _capture_envelope_sample():
		return
	var posf: PackedFloat32Array = _envelope_sample_positions
	if posf.size() < 12:
		return
	var s := PackedFloat32Array()
	s.resize(posf.size())
	var ext := _extents()
	var track_ext := ext * 1.5
	var qf := PackedFloat32Array()
	var qsites := PackedFloat32Array()
	var qstarts := PackedInt32Array()
	var qhs := PackedInt32Array()
	var q_gate := 0.0
	if q_weighted_com and eng._ml_q.is_valid() and eng._ml_sites.is_valid():
		var qns := maxi(int(eng._ml_tree_nsrc), 1)
		qf = _rd.buffer_get_data(eng._ml_q, 0, qns * 4).to_float32_array()
		qsites = _rd.buffer_get_data(eng._ml_sites, 0, qns * 16).to_float32_array()
		qstarts = _rd.buffer_get_data(eng._hash_cell_start, 0, (HASH_H * HASH_H * HASH_H + 1) * 4).to_int32_array()
		qhs = _rd.buffer_get_data(eng._hash_cell_sites, 0, qns * 4).to_int32_array()
		if qf.size() >= qns and qsites.size() >= qns * 4 \
				and qstarts.size() >= HASH_H * HASH_H * HASH_H + 1 \
				and qhs.size() >= qns:
			q_gate = maxf(float(eng._q_mean) * 0.5, 1e-4)
	var cnt := 0
	var i := 0
	while i + 3 < posf.size():
		var p := Vector3(posf[i], posf[i + 1], posf[i + 2])
		var near_window := posf[i + 3] > 0.0 \
				and absf(p.x - _window_center.x) <= track_ext.x \
				and absf(p.y - _window_center.y) <= track_ext.y \
				and absf(p.z - _window_center.z) <= track_ext.z
		if near_window and q_gate > 0.0:
			var q: float = eng._site_q_cpu_lookup(p, qsites, qf, qstarts, qhs, ext)
			near_window = q >= q_gate
		if near_window:
			s[cnt * 4] = p.x
			s[cnt * 4 + 1] = p.y
			s[cnt * 4 + 2] = p.z
			s[cnt * 4 + 3] = 0.0
			cnt += 1
		i += 4
	if cnt == 0:
		return
	s.resize(cnt * 4)
	# Feed the sampled live positions into the tracker before publishing its
	# target. Without this call, tracking_envelope only re-published the
	# initial fixed tile, so escaped particles were forced onto the readout
	# fallback instead of bringing the site window with them.
	_env_tracker.compute(s, 4, 1)
	_env_target_center = _env_tracker.center
	var scl: float = _env_tracker.extent.x / maxf(_env_orig_box.x, 1e-30)
	_env_target_scale = maxf(scl, 1e-3)
	print("[CassiSim] envelope target -> center (%.1f, %.1f, %.1f)  extent (%.1f, %.1f, %.1f)  box_scale %.3f  re_fits=%d"
			% [_env_target_center.x, _env_target_center.y, _env_target_center.z,
			_env_tracker.extent.x, _env_tracker.extent.y, _env_tracker.extent.z,
			_env_target_scale, _env_tracker.re_fits])
func _apply_envelope_state() -> void:
	if not tracking_envelope or not _decoupled_active or _physics_engine == null \
			or not _physics_engine.setup_ready():
		return
	if _env_tracker == null:
		return
	var now := Time.get_ticks_msec()
	if now - _env_apply_last_ms < ENV_APPLY_CADENCE_MS:
		return
	_env_apply_last_ms = now
	# Geometry publication is deliberately cadence-limited. The target is
	# sampled every two seconds; republishing the global site hash on every
	# smoothing frame creates a full CPU rebuild and several RD uploads per
	# frame while the envelope is moving.
	var dt_sec: float = clampf(float(ENV_APPLY_CADENCE_MS) / 1000.0, 0.0, 1.0)
	var alpha: float = 1.0 - exp(-dt_sec / maxf(ENV_APPLY_TAU_SEC, 1e-3))
	_env_applied_center = _env_applied_center.lerp(_env_target_center, alpha)
	_env_applied_scale = lerpf(_env_applied_scale, _env_target_scale, alpha)
	_window_center = _env_applied_center
	box_scale = maxf(_env_applied_scale, 1e-3)
	_update_particle_cull_bounds()
	var ext := _extents()
	var hb: PackedByteArray = _bh_init_bytes
	if hb.size() >= 48:
		hb.encode_float(36, ext.x)
		hb.encode_float(40, ext.y)
		hb.encode_float(44, ext.z)
		_bh_init_bytes = hb
	var eng: Object = _physics_engine
	var geometry_changed: bool = eng._window_center.distance_to(_window_center) > 1e-4 \
			or absf(float(eng.box_scale) - box_scale) > 1e-4
	var center_delta: Vector3 = _window_center - eng._window_center
	eng._window_center = _window_center
	eng.box_scale = box_scale
	if geometry_changed:
		if boxless_field and meshless_mode:
			eng.publish_render_query(center_delta)
		eng._mesh_rebuild_pending = true
	var ehb: PackedByteArray = eng._bh_init_bytes
	if ehb.size() >= 48:
		ehb.encode_float(36, ext.x)
		ehb.encode_float(40, ext.y)
		ehb.encode_float(44, ext.z)
		eng._bh_init_bytes = ehb

## One decoupled frame: consume the freshest engine publish, then record
## the render list (blend → instancer → …).
func _decoupled_poll_and_render() -> void:
	# M0b-P (one-RD): the frame records the pending steps + the render
	# passes into ONE list (the "strict per-frame staged command list") —
	# global-RD compute lists are render-thread-only, so the chain cannot
	# be recorded by the engine's worker. The renderer's frame machinery
	# submits; the readbacks + the publish follow at the job boundary.
	if _decoupled_boot_wait:
		# P3 (M0b-P one-RD): the ENGINE's buffers hold the initialized IC —
		# the render can start as soon as the engine's setup is ready (the
		# mirrors are gone; the publish carries no snapshot).
		if not _physics_engine.setup_ready():
			# The all-extras 2M-particle IC build takes ~13.5 s of worker CPU
			# (and more under GPU/CPU contention), so the deadline is
			# generous (45 s); a progress line prints every ~5 s so a
			# slow-but-healthy boot is visible instead of a silent stall.
			var boot_elapsed := Time.get_ticks_msec() - _decoupled_boot_start_ms
			if boot_elapsed - _decoupled_boot_last_progress_ms >= BOOT_PROGRESS_INTERVAL_MS:
				_decoupled_boot_last_progress_ms = boot_elapsed
				print("[CassiSim] decoupled bootstrap: waiting for engine setup... %d s (IC init of %d particles takes ~13.5 s CPU on the worker)"
						% [int(boot_elapsed / 1000), N_particles])
			if boot_elapsed > BOOT_TIMEOUT_MS:
				if gridless_physics:
					_fail_gridless_physics("bootstrap timeout")
					return
				push_error("[CassiSim] decoupled bootstrap timeout — falling back to inline")
				_physics_engine.stop_threaded()
				_physics_engine = null
				_decoupled_active = false
				_decoupled_boot_wait = false
				if _mmi != null:
					_mmi.visible = true   # the inline path draws the particles now
				_init_field(); _init_particles(); _apply_gravity_calibration(); _grav_warmup = true
			# Never call finish_setup while the worker is still mutating the
			# engine's setup state. This was a race in the non-blocking boot
			# path and could wedge the debug renderer before the first frame.
			return
		if not _physics_engine.finish_setup():
			if gridless_physics:
				_fail_gridless_physics("finish_setup failed")
				return
			push_error("[CassiSim] decoupled bootstrap finish_setup failed — falling back to inline")
			_physics_engine.stop_threaded()
			_physics_engine = null
			_decoupled_active = false
			_decoupled_boot_wait = false
			if _mmi != null:
				_mmi.visible = true   # the inline path draws the particles now
			_init_field(); _init_particles(); _apply_gravity_calibration(); _grav_warmup = true
			return
		_decoupled_boot_wait = false
		print("[CassiSim] decoupled bootstrap complete (non-blocking) — finish_setup took %d ms" % [Time.get_ticks_msec() - _decoupled_boot_fs_ms])
	# Paused decoupled scenes still need one renderer binding pass and
	# repeated topology-worker servicing. Otherwise the async worker can become
	# ready just after the first paused frame and never receive its first job.
	if not _us_blend_0_dc.is_valid():
		_build_dc_sets()
	# The topology path stages global-RD uploads/readbacks. Let the renderer
	# consume one setup-backed frame before starting that asynchronous work.
	if _physics_engine != null and boxless_field and meshless_mode \
			and not _decoupled_initial_render_pending:
		if not bool(_physics_engine.get("_meshless_query_ready")):
			_physics_engine.publish_render_query()
		_physics_engine.service_render_topology()
	var initial_blend_ready := _decoupled_initial_render_pending and _us_blend_0_dc.is_valid() and _blend_pipe.is_valid() and _physics_engine != null and bool(_physics_engine.get("_ml_ready"))
	if ((not playing and not initial_blend_ready) or (not _shaders_ready and not initial_blend_ready)):
		return
	_physics_engine.update_bh_header()   # BEFORE the list

	var cl := _rd.compute_list_begin()
	var frame_target := _decoupled_target
	if _physics_engine.setup_ready():
		frame_target = mini(frame_target, int(_physics_engine._executed) + DECOUPLED_LEAD_CAP)
		_decoupled_target = frame_target
	var executed: int = _physics_engine.record_pending_steps(cl, frame_target)
	# M0b-P decoupled merge: record the engine-owned GPU merge cycle in this
	# same global list, before blend/instancer consume positions. This keeps
	# dead slots (pos.w=0) hidden without a CPU mirror or copy.
	if executed > 0:
		_physics_engine.record_merge_if_due(cl)
		_barrier(cl)
	# Decoupled fp32 blend: set every PC field explicitly; never inherit
	# inline-path state. Shader layout = alpha, mode, win_x, win_y, win_z.
	_blend_pc.encode_float(0, 1.0)
	_blend_pc.encode_float(4, 0.0)
	_blend_pc.encode_float(8, _render_window_origin().x)
	_blend_pc.encode_float(12, _render_window_origin().y)
	_blend_pc.encode_float(16, _render_window_origin().z)
	_rd.compute_list_bind_compute_pipeline(cl, _blend_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_blend_0_dc, 0)
	_rd.compute_list_set_push_constant(cl, _blend_pc, _blend_pc.size())
	_rd.compute_list_dispatch(cl, ceili(float(N_particles) / 64.0), 1, 1)
	_barrier(cl)
	var initial_instancer_recorded := false

	# ── Instancer (render variant — binding 0 reads pos_render; the DC
	# set reads the ENGINE's vel + field buffers directly) ──
	if _instancer_shader.is_valid() and N_particles > 0 and _us_inst_0_render_dc.is_valid():
		_fill_instancer_pc()
		var ipg := ceili(float(N_particles) / 256.0)
		_rd.compute_list_bind_compute_pipeline(cl, _instancer_pipe)
		if _ml_boxless_on():
			_rd.compute_list_bind_uniform_set(cl, _us_inst_0_lut_boxless_render_dc if _lut_active() else _us_inst_0_boxless_render_dc, 0)
		else:
			_rd.compute_list_bind_uniform_set(cl, _us_inst_0_lut_render_dc if _lut_active() else _us_inst_0_render_dc, 0)
		_rd.compute_list_set_push_constant(cl, _instancer_pc_bytes, _instancer_pc_bytes.size())
		_rd.compute_list_dispatch(cl, ipg, 1, 1)
		_rd.compute_list_add_barrier(cl)
		if _decoupled_initial_render_pending:
			initial_instancer_recorded = true
	# ── Presentation macro-site LOD (renderer-only) ───────────────────
	# Dispatch the fixed site capacity, not merely the currently published
	# count: the shader writes finite zero records whenever topology status is
	# absent/stale/overflowed, so an invalidated topology cannot leave the
	# previous generation visible.
	if _presentation_macro_lod_wanted() and _us_macro_lod_0.is_valid() \
			and _rd.uniform_set_is_valid(_us_macro_lod_0) \
			and _macro_lod_mm != null and _macro_lod_mm.instance_count > 0:
		var macro_count := _macro_lod_mm.instance_count
		_macro_lod_pc.encode_float(0, float(macro_count))
		_macro_lod_pc.encode_float(4, clampf(presentation_macro_min_coherence, 0.0, 1.0))
		_macro_lod_pc.encode_float(8, maxf(cluster_radius * 0.08, 1.5))
		_macro_lod_pc.encode_float(12, 1.0)
		_rd.compute_list_bind_compute_pipeline(cl, _macro_lod_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_macro_lod_0, 0)
		_rd.compute_list_set_push_constant(cl, _macro_lod_pc, _macro_lod_pc.size())
		_rd.compute_list_dispatch(cl, ceili(float(macro_count) / 256.0), 1, 1)
		_rd.compute_list_add_barrier(cl)
	_record_presentation_trails(cl, _us_trail_0_dc)
	_record_rotation_orientation(cl)

	# ── q-histogram (auto color-align; RENDER variant reads pos_render —
	var color_base_dc: int = int(particle_color_mode) & 0xF
	if _qhist_pipe.is_valid() and _us_qhist_0_render_dc.is_valid() and auto_align_colors \
			and color_base_dc >= 2 and color_base_dc <= 4 and N_particles > 0:
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
		_qhist_pc_bytes.encode_float(40, -_window_center.x)
		_qhist_pc_bytes.encode_float(44, -_window_center.y)
		_qhist_pc_bytes.encode_float(48, -_window_center.z)
		# True-boxless arm: require a published topology chain in decoupled
		# mode so the site buffers are live and spatially indexed.
		var _boxless_on: float = 1.0 if _ml_boxless_on() else 0.0
		var _qhist_site_count := 2 * ML_N1 * ML_N1 * ML_N1
		if _decoupled_active and _physics_engine != null:
			_qhist_site_count = int(_physics_engine.get("_topology_site_count"))
		_qhist_pc_bytes.encode_float(52, _boxless_on)
		_qhist_pc_bytes.encode_float(56, float(_qhist_site_count))
		_rd.compute_list_bind_compute_pipeline(cl, _qhist_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_qhist_0_render_dc, 0)
		_rd.compute_list_set_push_constant(cl, _qhist_pc_bytes, _qhist_pc_bytes.size())
		var qh_threads := ceili(float(N_particles) / 16.0)
		_rd.compute_list_dispatch(cl, ceili(qh_threads / 64.0), 1, 1)
	if initial_instancer_recorded:
		_decoupled_initial_blend_id += 1
		_decoupled_initial_render_pending = false
	_rd.compute_list_end()
	if initial_instancer_recorded and _mmi != null and not _mmi.visible:
		_mmi.visible = true
	# Publish at the cadence — the readbacks (telemetry + the tracker COM)
	# are the accepted job-boundary group; the bookkeeping rides every frame.
	_pub_counter += 1 if executed > 0 else 0
	var pub: Dictionary = {"executed": _physics_engine._executed,
			"step_count": _physics_engine._step_count, "t": _physics_engine._time}
	if _pub_counter == 1 or _pub_counter % maxi(mirror_publish_cadence, 1) == 0:
		pub = _engine_read_publish(true)
	_apply_decoupled_publish(pub)
	if not _merge_dc_first_completion_logged and _physics_engine != null \
			and int(_physics_engine.get("_merge_cycles_run")) > 0:
		_merge_dc_first_completion_logged = true
		var merge_elapsed_ms := Time.get_ticks_msec() \
			- int(_physics_engine.get("_merge_first_record_tick_ms"))
		print("[CassiSim] particle-merge phase 0 completed in %d ms at step %d" % [
			merge_elapsed_ms, int(pub.get("step_count", 0))])


## P3 (M0b-P one-RD): the decoupled render sets bind the ENGINE's live
## buffers — no mirrors, no copies, no uploads. The engine's RIDs exist on
## the shared global RD after its worker setup; built lazily on the first
## frame the engine is ready. The blend keeps the sim's pos_render staging
## (the −c window seam — the instancer's PC has no room for the center);
## the instancer/qhist/occ read the engine's vel/fields/pos directly.
func _build_dc_sets() -> void:
	var eng: Object = _physics_engine
	if eng == null or not _blend_sh.is_valid():
		return
	if not eng._pos_buf.is_valid():
		return
	_us_blend_0_dc = _rd.uniform_set_create([
		_uniform_storage(0, eng._pos_buf),
		_uniform_storage(1, eng._pos_buf),
		_uniform_storage(2, _pos_render_buf),
	], _blend_sh, 0)
	if _instancer_shader.is_valid() and _mm_rd_rid.is_valid():
		_us_inst_0_render_dc = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, eng._vel_buf),
			_uniform_storage(3, eng._field_q),
			_uniform_storage(4, eng._field_ey),
			_uniform_storage(5, eng._field_ei),
			_uniform_storage(6, _lut_u_buf_off),
			_uniform_storage(7, eng._shortlist_sites),
			_uniform_storage(8, eng._ml_psi_y),
			_uniform_storage(9, eng._ml_psi_i),
			_uniform_storage(10, eng._shortlist_count),
			_uniform_storage(11, eng._hash_cell_start),
			_uniform_storage(12, eng._hash_cell_sites),
			_uniform_storage(13, eng._hash_cfg),
		], _instancer_shader, 0)
		_us_inst_0_lut_render_dc = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, eng._vel_buf),
			_uniform_storage(3, eng._field_q),
			_uniform_storage(4, eng._field_ey),
			_uniform_storage(5, eng._field_ei),
			_uniform_storage(6, _lut_u_buf_on),
			_uniform_storage(7, eng._shortlist_sites),
			_uniform_storage(8, eng._ml_psi_y),
			_uniform_storage(9, eng._ml_psi_i),
			_uniform_storage(10, eng._shortlist_count),
			_uniform_storage(11, eng._hash_cell_start),
			_uniform_storage(12, eng._hash_cell_sites),
			_uniform_storage(13, eng._hash_cfg),
		], _instancer_shader, 0)
		# ── Arm 1 BOXLESS dc variants (engine builds the shortlist in decoupled
		# mode → bind eng._shortlist_*). Selected only when _ml_boxless_on().
		_us_inst_0_boxless_render_dc = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, eng._vel_buf),
			_uniform_storage(3, eng._field_q),
			_uniform_storage(4, eng._field_ey),
			_uniform_storage(5, eng._field_ei),
			_uniform_storage(6, _shortlist_flag_off),
			_uniform_storage(7, eng._shortlist_sites),
			_uniform_storage(8, eng._ml_psi_y),
			_uniform_storage(9, eng._ml_psi_i),
			_uniform_storage(10, eng._shortlist_count),
			_uniform_storage(11, eng._hash_cell_start),
			_uniform_storage(12, eng._hash_cell_sites),
			_uniform_storage(13, eng._hash_cfg),
		], _instancer_shader, 0)
		_us_inst_0_lut_boxless_render_dc = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, eng._vel_buf),
			_uniform_storage(3, eng._field_q),
			_uniform_storage(4, eng._field_ey),
			_uniform_storage(5, eng._field_ei),
			_uniform_storage(6, _shortlist_flag_on),
			_uniform_storage(7, eng._shortlist_sites),
			_uniform_storage(8, eng._ml_psi_y),
			_uniform_storage(9, eng._ml_psi_i),
			_uniform_storage(10, eng._shortlist_count),
			_uniform_storage(11, eng._hash_cell_start),
			_uniform_storage(12, eng._hash_cell_sites),
			_uniform_storage(13, eng._hash_cfg),
		], _instancer_shader, 0)
	if _presentation_trails_wanted() and _trail_rd_rid.is_valid() \
			and not (_us_trail_0_dc.is_valid() and _rd.uniform_set_is_valid(_us_trail_0_dc)):
		_us_trail_0_dc = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, eng._vel_buf),
			_uniform_storage(2, _trail_rd_rid),
		], _trail_shader, 0)
	if _qhist_shader.is_valid() and _pos_render_buf.is_valid():
		_us_qhist_0_render_dc = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, eng._field_q),
			_uniform_storage(2, _qhist_buf),
			_uniform_storage(3, eng._field_ey),
			_uniform_storage(4, eng._field_ei),
			_uniform_storage(5, eng._ml_sites),
			_uniform_storage(6, eng._ml_psi_y),
			_uniform_storage(7, eng._ml_psi_i),
		], _qhist_shader, 0)
	if _occ_shader.is_valid() and _occ_buf.is_valid() and _occ_sample_buf.is_valid() and eng._pos_buf.is_valid():
		_us_occ_0_dc = _rd.uniform_set_create([
			_uniform_storage(0, eng._pos_buf),
			_uniform_storage(1, _occ_buf),
			_uniform_storage(2, _occ_sample_buf),
		], _occ_shader, 0)
	print("[CassiSim] P3 one-RD render sets bound to the engine's live buffers")
	if _us_blend_0_dc.is_valid():
		_decoupled_initial_render_pending = true


func _exit_tree() -> void:
	if _decoupled_active and _physics_engine != null:
		_physics_engine.stop_threaded()
		_physics_engine = null
	_decoupled_active = false
	_free_uniform_sets()
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

func _render_window_origin() -> Vector3:
	# Physics and envelope tracking may move the field window while the
	# operator has home-window following disabled. Keep that motion out of
	# the render-space translation so the camera remains user-controlled.
	return _window_center if home_window_enabled else Vector3.ZERO

func _extent_min() -> float:
	var e := _extents()
	return minf(minf(e.x, e.y), e.z)

func _fit_initial_condition_to_domain() -> void:
	# A site-native run is open-boundary, but its live site mesh still needs a
	# finite initial support. Never silently seed a Gaussian/Plummer cloud
	# beyond that support: the old periodic mapper folded the whole cloud onto
	# the box seam, producing the visible wall pile-up and enormous overdraw.
	if not gridless_physics or initial_condition < 0 or initial_condition > 2:
		return
	var center_radius := maxf(cluster_separation, 0.0)
	var support_radius := maxf(cluster_radius * 1.25, 1.0)
	var frac := maxf(initial_radius_fraction, 0.1)
	var required_extent := (center_radius + support_radius) / frac * 1.05
	var current_extent := _extent_min()
	if required_extent <= current_extent:
		return
	var base_extent := maxf(minf(minf(box_aspect.x, box_aspect.y), box_aspect.z)
			* cluster_radius * 1.5, 1e-3)
	var fitted_scale := required_extent / base_extent
	if fitted_scale > box_scale:
		var old_scale := box_scale
		box_scale = fitted_scale
		push_warning("[CassiSim] IC support exceeded the site window; fitting box_scale %.3f → %.3f before startup" % [old_scale, box_scale])


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
	var ps = N_particles * 16
	_pos_buf = _rd.storage_buffer_create(ps)
	_vel_buf = _rd.storage_buffer_create(ps)
	_acc_buf = _rd.storage_buffer_create(ps)
	# Snapshot/interpolation buffers (decoupled physics producer seam):
	# pos_prev = the pre-batch snapshot (rolled every frame BEFORE the step
	# batch); pos_render = the interpolated render snapshot the instancer's
	# render-set variant reads (== pos while _interp_alpha == 1.0).
	# maxi(N_particles, 1) keeps them nonzero-sized for N_particles=0 verify
	# scenes (the tree-grad precedent — a 0-size buffer fails set creation).
	_pos_prev_buf = _rd.storage_buffer_create(maxi(N_particles, 1) * 16)
	_pos_render_buf = _rd.storage_buffer_create(maxi(N_particles, 1) * 16)
	_field_intelligence.allocate_buffers(
		_rd, grid_N, N_particles, field_intelligence_enabled,
		field_intelligence_organ_radius, field_intelligence_probe_index,
		field_intelligence_reward_control, _field_intelligence_profile())

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
		0.0, _window_center.x, _window_center.y, _window_center.z,
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
	# Cluster center positions + masses (for multi-cluster gravity).
	# 64-vec4 cap — keep in sync with ClusterBuf in cassi_nbody_gravity.glsl
	# (set 2 binding 1); cluster indices 0..63 are safe.
	_cluster_buf = _rd.storage_buffer_create(64 * 4 * 4)
	# Mass density grid (float per cell — written by the deposit's convert
	# pass, see cassi_mass_deposit.glsl)
	_mass_density_buf = _rd.storage_buffer_create(nc * 4)
	# Zero it once: the tree arm stages rho BEFORE the first step's GPU
	# clear (the tree gather reads pre-deposit rho), and allocator reuse
	# otherwise leaves garbage there — a nondeterministic step-1 tree
	# source. Mirrored in cassi_physics_engine.gd (same commit).
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
	# Cell-centered ∇(g·Φ) field (vec4 per cell — river-arm gradient,
	# rebuilt every step by the gradient pass between poisson and nbody)
	_grad_buf = _rd.storage_buffer_create(nc * 16)
	# Dual-lattice ∇(g·Φ) (CASCADE_GRID.md — always allocated so dual_grid
	# stays a LIVE toggle; written only by the shifted gradient pass).
	_grad_buf2 = _rd.storage_buffer_create(nc * 16)
	# q-histogram for auto color-align (cassi_qhist.glsl): 128 log-spaced bins
	_qhist_buf = _rd.storage_buffer_create(128 * 4)
	# Occupancy counters plus a separate compact envelope sample. The sample
	# is written by the same strided GPU pass so envelope tracking never
	# reads back the full N-particle position buffer.
	_occ_buf = _rd.storage_buffer_create(32)
	_occ_sample_buf = _rd.storage_buffer_create(ENVELOPE_SAMPLE_MAX * 16)
	_qhist_pc_bytes = PackedByteArray(); _qhist_pc_bytes.resize(15 * 4)  # + win@10-12 (movable home-window) + boxless@13 + n_sites@14 (true-boxless arm)
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
	# Arm 1 shortlist: sized for the worst case (every site coherent). The
	# instancer scans only the dense subset actually written.
	_shortlist_sites = _rd.storage_buffer_create(ml_ns * 16)
	_shortlist_count = _rd.storage_buffer_create(4)
	# Boxless site hash (boxless_site_hash_prereg.md): n_cells = HASH_H³, cell_sites
	# worst-case sized, cfg vec4 for the box_min/cell_side the query reads.
	var hcells_s: int = HASH_H * HASH_H * HASH_H
	_hash_cell_start = _rd.storage_buffer_create((hcells_s + 1) * 4)
	_hash_cell_sites = _rd.storage_buffer_create(maxi(ml_ns, 1) * 4)
	_hash_cell_count = _rd.storage_buffer_create(hcells_s * 4)
	_hash_cfg = _rd.storage_buffer_create(16)
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
	_jfa_pc_bytes = PackedByteArray(); _jfa_pc_bytes.resize(8 * 4)
	_cell_pc_bytes = PackedByteArray(); _cell_pc_bytes.resize(18 * 4)  # mode,N,n_sites,dt,hx,hy,hz,C2,OM2,PHI,src,rho_floor,drift_cap,kappa,lam,T_steer,lloyd_p,J_wind
	_raster_pc_bytes = PackedByteArray(); _raster_pc_bytes.resize(8 * 4)
	_shortlist_pc_bytes = PackedByteArray(); _shortlist_pc_bytes.resize(3 * 4)
	_hash_pc_bytes = PackedByteArray(); _hash_pc_bytes.resize(9 * 4)
	_hash_cfg_bytes = PackedByteArray(); _hash_cfg_bytes.resize(4 * 4)
	# ── Particle-merge buffers (INIT-TIME: allocated only when particle_merge)
	# The merge kernel's persistent per-particle state (alive/mass/mom/cen/
	# best/sink) + the spatial-hash scratch (cc/cs/ch/cl) + the merge counter.
	# Cell widths stay ≥ R_m, so the wrapped 27-neighbor walk covers every
	# in-range pair. The shared helper uniformly coarsens anisotropic raw
	# dimensions to the shortest-axis cube; large-N pass_best time-slices the
	# actual cell occupancy, avoiding both the old aspect-volume scan blow-up
	# and its 64-entry omission. Cubic verifier geometry is unchanged.
	if particle_merge and N_particles > 0:
		# Hash geometry via the shared helper (dedup — identical to the engine
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
		# Non-cubic cells: per-axis widths from the per-axis hash counts
		_merge_cell_wx = geom["cell_wx"]
		_merge_cell_wy = geom["cell_wy"]
		_merge_cell_wz = geom["cell_wz"]
		print("[CassiSim] particle-merge hash: %dx%dx%d = %d cells, widths=%s (R_m=%.4f)" % [
			_merge_hash_nx, _merge_hash_ny, _merge_hash_nz, _merge_hash_total,
			Vector3(_merge_cell_wx, _merge_cell_wy, _merge_cell_wz),
			_extent_min() / float(maxi(grid_N, 1))])
		_merge_pc_bytes = PackedByteArray(); _merge_pc_bytes.resize(26 * 4)   # 26 floats = 104 B (n_sites@25) — F8: pre-sized, never reassigned
		_merge_scan_pc_bytes = PackedByteArray(); _merge_scan_pc_bytes.resize(4 * 4)
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
	_ml_tree_nqq = _rd.storage_buffer_create(tnm * 4)  # Arm 2: per-node mean q
	_ml_tree_ctr = _rd.storage_buffer_create(8 * 4)
	# per-particle tree gradient + walk counts (N_particles targets;
	# a minimum of 1 keeps the buffers non-zero-sized even for N_particles=0
	# verify scenes, so the walk uniform set never fails to bind)
	_ml_tree_grad = _rd.storage_buffer_create(maxi(N_particles, 1) * 16)
	_ml_tree_icount = _rd.storage_buffer_create(maxi(N_particles, 1) * 4)
	_tree_build_pc_bytes = PackedByteArray(); _tree_build_pc_bytes.resize(19 * 4)
	_tree_grav_pc_bytes = PackedByteArray(); _tree_grav_pc_bytes.resize(8 * 4)

	# Pre-allocate push-constant byte buffers (hitch-free pattern)
	_pc_bytes = PackedByteArray(); _pc_bytes.resize(11 * 4)
	_nbody_pc_bytes = PackedByteArray(); _nbody_pc_bytes.resize(15 * 4)
	# Two-fluid dedicated PC (14 floats = 56 B): the shared 11 fields + the
	# 3 per-axis extents for the anisotropic 19-point stencil (GRID_LAYOUT.md).
	_two_fluid_pc_bytes = PackedByteArray(); _two_fluid_pc_bytes.resize(17 * 4)  # + pass_sel (PDE pass A/B) + omega2 (ω₀²) + ham_completion (U1, offset 64)
	_two_fluid_pc_bytes.encode_float(64, 0.0)  # U1 ham_completion OFF (flip to 1.0 for the ON arm)
	_md_pc_bytes = PackedByteArray(); _md_pc_bytes.resize(9 * 4)  # + mode (deposit 0 / convert 1)
	_instancer_pc_bytes = PackedByteArray(); _instancer_pc_bytes.resize(32 * 4)  # consolidated gradient engine PC — 128 B (the RDNA3 Vulkan cap)
	_bh_int_pc_bytes = PackedByteArray(); _bh_int_pc_bytes.resize(4 * 4)
	_cond_pc_bytes = PackedByteArray(); _cond_pc_bytes.resize(4 * 4)
	_bh_acc_pc_bytes = PackedByteArray(); _bh_acc_pc_bytes.resize(4 * 4)
	_poisson_pc_bytes = PackedByteArray(); _poisson_pc_bytes.resize(7 * 4)
	_occ_pc_bytes = PackedByteArray(); _occ_pc_bytes.resize(10 * 4)
	# Blend PC (8 B = 2 floats): alpha @ byte 0, packed mode @ byte 4.
	# Godot reflects the 2-float push-constant block as exactly 8 bytes
	# (verified empirically — 4.7 hard-errors on any size mismatch).
	_blend_pc = PackedByteArray(); _blend_pc.resize(20)  # alpha@0, packed@4, win@8/12/16 (movable home-window)
	_macro_lod_pc = PackedByteArray(); _macro_lod_pc.resize(4 * 4)
	_trail_pc = PackedByteArray(); _trail_pc.resize(16 * 4)
	_rotation_axis_pc = PackedByteArray(); _rotation_axis_pc.resize(4 * 4)
	_volume_pc_bytes = PackedByteArray(); _volume_pc_bytes.resize(32 * 4); _volume_pc_bytes.fill(0)
	_volume_resolve_pc_bytes = PackedByteArray(); _volume_resolve_pc_bytes.resize(32 * 4)
	_volume_history_state_bytes = PackedByteArray(); _volume_history_state_bytes.resize(20 * 4)
	_volume_stats_zero = PackedByteArray(); _volume_stats_zero.resize(32); _volume_stats_zero.fill(0)
	_volume_stats = _rd.storage_buffer_create(32)
	_rd.buffer_update(_volume_stats, 0, 32, _volume_stats_zero)
	# NOTE: all poisson dispatches (clear/load/kspace/FFT) are 2D (N, N, 1) —

	# uses row = workgroup.x + workgroup.y·N. A 1D (N³/256, 1, 1) dispatch
	# caps at 65535 groups on some devices and the naive x + y·N gid formula
	# covers only N² + 255N cells — the N=256 dispatch landmine.
	# Telemetry reset (kept for reference; the per-step reset runs on the GPU
	# in the poisson clear pass so chained steps stay independent)
	_tel_reset_bytes = PackedFloat32Array([0.0, 0.0, 0.0, INF, 0.0, INF, 0.0, 0.0]).to_byte_array()

	# ── Color-as-LUT (Tier-2): two static 16-byte flag buffers (the instancer
	# set-variant selection IS the mode switch — the shader reads the flag from
	# whichever set is bound, never re-uploaded) + the 256×1 RGBA8 LUT texture
	# (re-baked via update() on band changes — the RID stays stable, so the
	# instancer sets and the material keep their references).
	_lut_u_on_bytes = PackedFloat32Array([1.0, 0.0, 0.0, 0.0]).to_byte_array()
	_lut_u_off_bytes = PackedFloat32Array([0.0, 0.0, 0.0, 0.0]).to_byte_array()
	_lut_u_buf_on = _rd.storage_buffer_create(16)
	_lut_u_buf_off = _rd.storage_buffer_create(16)
	_rd.buffer_update(_lut_u_buf_on, 0, 16, _lut_u_on_bytes)
	_rd.buffer_update(_lut_u_buf_off, 0, 16, _lut_u_off_bytes)
	# Arm 1 boxless flags: .y selects site coherence; .z selects open-world
	# rendering/deposition (no periodic fold or seam re-entry for escaped
	# particles). .x still carries the LUT bit.
	var _bx_off := PackedFloat32Array([0.0, 1.0, 1.0, 0.0]).to_byte_array()
	var _bx_on := PackedFloat32Array([1.0, 1.0, 1.0, 0.0]).to_byte_array()
	_shortlist_flag_off = _rd.storage_buffer_create(16)
	_shortlist_flag_on = _rd.storage_buffer_create(16)
	_rd.buffer_update(_shortlist_flag_off, 0, 16, _bx_off)
	_rd.buffer_update(_shortlist_flag_on, 0, 16, _bx_on)
	var lut_img := Image.create_empty(LUT_SIZE, 1, false, Image.FORMAT_RGBA8)
	lut_img.fill(Color(0.4, 0.4, 0.5, 1.0))  # placeholder; the real bake runs in _ready
	_color_lut_tex = ImageTexture.create_from_image(lut_img)
	_lut_sig = PackedFloat32Array()  # sentinel: never baked → first engine fill marks dirty
	_lut_bake_dirty = false          # set by _update_lut_bake_sig on the first fill

func _free_buffers() -> void:
	_free_volume_history_resources()
	if _field_intelligence != null:
		_field_intelligence.free_buffers()
	for rid in [_field_ey, _field_ei, _field_q, _field_vel, _field_scratch,
				_fft_buf, _tel_buf, _cluster_buf, _mass_density_buf, _mass_density_fix,
				_pos_buf, _vel_buf, _acc_buf, _pos_prev_buf, _pos_render_buf,
				_bh_buf,
				_grad_buf, _grad_buf2, _occ_buf, _occ_sample_buf, _qhist_buf,
				_ml_labels_a, _ml_labels_b, _ml_sites,
				_ml_psi_y, _ml_psi_i, _ml_pi_y, _ml_pi_i,
				_ml_lap_y, _ml_lap_i, _ml_vol,
				_ml_cen, _ml_remap, _ml_tmp_y, _ml_tmp_i, _ml_tmp_py, _ml_tmp_pi,
				_ml_grad_y, _ml_grad_i, _ml_lsm_y, _ml_lsm_i,
				_shortlist_sites, _shortlist_count, _shortlist_flag_off, _shortlist_flag_on,
				_hash_cell_start, _hash_cell_sites, _hash_cell_count, _hash_cfg,
				_ml_tree_src, _ml_tree_srcw, _ml_tree_key, _ml_tree_order,
				_ml_tree_cf, _ml_tree_w, _ml_tree_q, _ml_tree_r, _ml_tree_ctr,
				_ml_tree_nqq, _ml_tree_grad, _ml_tree_icount, _tree_mc_buf,
				_field_render_tex, _volume_history_neutral,
				_lut_u_buf_on, _lut_u_buf_off, _volume_stats]:
		if rid.is_valid(): _rd.free_rid(rid)
	for rid in [_merge_alive_buf, _merge_mass_buf, _merge_mom_buf, _merge_cen_buf,
				_merge_best_buf, _merge_sink_buf, _merge_spin_buf, _merge_mprev_buf, _merge_cc_buf, _merge_cs_buf,
				_merge_ch_buf, _merge_cl_buf, _merge_mc_buf, _merge_scr_buf]:
		if rid.is_valid(): _rd.free_rid(rid)
	_merge_alive_buf = RID(); _merge_mass_buf = RID(); _merge_mom_buf = RID()
	_merge_cen_buf = RID(); _merge_best_buf = RID(); _merge_sink_buf = RID()
	_merge_cc_buf = RID(); _merge_cs_buf = RID(); _merge_ch_buf = RID()
	_merge_cl_buf = RID(); _merge_mc_buf = RID(); _merge_scr_buf = RID()
	_merge_spin_buf = RID(); _merge_mprev_buf = RID()
	_field_render_tex = RID()
	_volume_history_neutral = RID(); _volume_stats = RID()
	_lut_u_buf_on = RID(); _lut_u_buf_off = RID()
	_shortlist_sites = RID(); _shortlist_count = RID()
	_hash_cell_start = RID(); _hash_cell_sites = RID(); _hash_cell_count = RID(); _hash_cfg = RID()
	_shortlist_flag_off = RID(); _shortlist_flag_on = RID()
	_color_lut_tex = null
	_tree_mc_buf = RID()   # stale freed RID must not survive a set-only rebuild
	_tree_worker_stop()

func _free_uniform_sets() -> void:
	# Uniform sets reference buffers/shaders/textures — release them BEFORE
	# any of those are freed (reinit, shader retry, exit). Overwriting a
	# live set RID without freeing it leaks the set on the local RD.
	if _rd == null: return
	if _field_intelligence != null:
		_field_intelligence.free_uniform_set()
	var seen := {}
	for rid in [_us_two_0, _us_two_1, _us_two_2, _us_mass_dep_0,
				_us_nbody_0, _us_nbody_1, _us_nbody_2, _us_poisson_0,
				_us_fr_0, _us_fr_2, _us_cond_0, _us_cond_1,
				_us_bh_int_0, _us_bh_int_1, _us_inst_0, _us_inst_0_render,
				_us_inst_0_lut, _us_inst_0_lut_render,
				_us_inst_0_boxless, _us_inst_0_render_boxless,
				_us_inst_0_lut_boxless, _us_inst_0_lut_render_boxless,
				_us_blend_0, _us_blend_0_dc,
				_us_inst_0_render_dc, _us_inst_0_lut_render_dc,
				_us_inst_0_boxless_render_dc, _us_inst_0_lut_boxless_render_dc,
				_us_qhist_0_render_dc, _us_occ_0_dc, _us_occ_0,
				_us_qhist_0, _us_qhist_0_render, _us_jfa_0, _us_cell_0,
				_us_raster_0, _us_shortlist, _us_hash, _us_volume_0,
				_us_volume_history_0, _us_volume_reproject_ab, _us_volume_reproject_ba,
				_us_macro_lod_0, _us_trail_0, _us_trail_0_dc,
				_us_rotation_axis_0]:
		if rid.is_valid() and _rd.uniform_set_is_valid(rid) and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	_us_two_0 = RID(); _us_two_1 = RID(); _us_two_2 = RID()
	_us_mass_dep_0 = RID()
	_us_nbody_0 = RID(); _us_nbody_1 = RID(); _us_nbody_2 = RID()
	_us_poisson_0 = RID()
	_us_fr_0 = RID(); _us_fr_2 = RID()
	_us_cond_0 = RID(); _us_cond_1 = RID()
	_us_bh_int_0 = RID(); _us_bh_int_1 = RID()
	_us_inst_0 = RID(); _us_inst_0_render = RID()
	_us_inst_0_lut = RID(); _us_inst_0_lut_render = RID()
	_us_inst_0_boxless = RID(); _us_inst_0_render_boxless = RID()
	_us_inst_0_lut_boxless = RID(); _us_inst_0_lut_render_boxless = RID()
	_us_inst_0_boxless_render_dc = RID(); _us_inst_0_lut_boxless_render_dc = RID()
	_us_blend_0 = RID()
	_us_blend_0_dc = RID(); _us_inst_0_render_dc = RID(); _us_inst_0_lut_render_dc = RID()
	_us_qhist_0_render_dc = RID(); _us_occ_0_dc = RID()
	_us_occ_0 = RID()
	_us_qhist_0 = RID(); _us_qhist_0_render = RID()
	_us_jfa_0 = RID(); _us_cell_0 = RID(); _us_raster_0 = RID()
	_us_tree_build = RID(); _us_tree_grav = RID(); _us_tree_mc = RID()
	_us_merge_0 = RID(); _us_bh_acc_0 = RID(); _us_scan_0 = RID()
	_us_shortlist = RID(); _us_hash = RID(); _us_volume_0 = RID()
	_us_volume_history_0 = RID()
	_us_volume_reproject_ab = RID()
	_us_volume_reproject_ba = RID()
	_us_macro_lod_0 = RID()
	_us_trail_0 = RID()
	_us_trail_0_dc = RID()
	_us_rotation_axis_0 = RID()
	_volume_clear_signature()

func _free_shaders() -> void:
	_free_uniform_sets()
	if _field_intelligence != null:
		_field_intelligence.free_shader()
	var seen := {}
	for rid in [_two_fluid_pipe, _nbody_pipe, _poisson_pipe, _field_render_pipe, _volume_pipe, _instancer_pipe, _mass_deposit_pipe, _cond_pipe, _bh_int_pipe, _occ_pipe, _qhist_pipe, _jfa_pipe, _cell_pipe, _raster_pipe, _shortlist_pipe, _hash_pipe, _tree_build_pipe, _tree_grav_pipe, _tree_mc_pipe, _blend_pipe, _merge_pipe, _scan_pipe, _bh_acc_pipe, _two_fluid_shader, _nbody_shader, _poisson_shader, _field_render_shader, _volume_shader, _instancer_shader, _mass_deposit_shader, _cond_shader, _bh_int_shader, _occ_shader, _qhist_shader, _jfa_shader, _cell_shader, _raster_shader, _shortlist_shader, _hash_shader, _tree_build_shader, _tree_grav_shader, _tree_mc_shader, _blend_sh, _merge_shader, _scan_shader, _bh_acc_shader]:
		if rid.is_valid() and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	for rid in [_volume_history_pipe, _volume_reproject_pipe,
				_volume_history_shader, _volume_reproject_shader,
				_macro_lod_pipe, _macro_lod_shader, _trail_pipe, _trail_shader,
				_rotation_axis_pipe, _rotation_axis_shader]:
		if rid.is_valid() and not seen.has(rid):
			seen[rid] = true
			_rd.free_rid(rid)
	_two_fluid_shader = RID(); _nbody_shader = RID(); _poisson_shader = RID(); _field_render_shader = RID(); _volume_shader = RID(); _instancer_shader = RID(); _mass_deposit_shader = RID(); _cond_shader = RID(); _bh_int_shader = RID(); _occ_shader = RID(); _qhist_shader = RID(); _jfa_shader = RID(); _cell_shader = RID(); _raster_shader = RID(); _shortlist_shader = RID(); _hash_shader = RID(); _tree_build_shader = RID(); _tree_grav_shader = RID(); _tree_mc_shader = RID(); _blend_sh = RID(); _merge_shader = RID(); _scan_shader = RID(); _bh_acc_shader = RID()
	_two_fluid_pipe = RID(); _nbody_pipe = RID(); _poisson_pipe = RID(); _field_render_pipe = RID(); _volume_pipe = RID(); _instancer_pipe = RID(); _mass_deposit_pipe = RID(); _cond_pipe = RID(); _bh_int_pipe = RID(); _occ_pipe = RID(); _qhist_pipe = RID(); _jfa_pipe = RID(); _cell_pipe = RID(); _raster_pipe = RID(); _shortlist_pipe = RID(); _hash_pipe = RID(); _tree_build_pipe = RID(); _tree_grav_pipe = RID(); _tree_mc_pipe = RID(); _blend_pipe = RID(); _merge_pipe = RID(); _scan_pipe = RID(); _bh_acc_pipe = RID()
	_volume_history_shader = RID()
	_volume_reproject_shader = RID()
	_volume_history_pipe = RID()
	_volume_reproject_pipe = RID()
	_macro_lod_shader = RID()
	_macro_lod_pipe = RID()
	_trail_shader = RID()
	_trail_pipe = RID()
	_rotation_axis_shader = RID()
	_rotation_axis_pipe = RID()
	_invalidate_volume_history_state()
func _invalidate_volume_render_cache() -> void:
	_volume_cache_valid = false
	_volume_last_generation = -1
	_volume_last_site_count = -1
	_volume_last_cam_transform = Transform3D()
	_volume_last_fov = -1.0
	_volume_last_window_center = Vector3.INF
	_volume_last_extents = Vector3(-INF, -INF, -INF)
	_volume_last_rt_size = Vector2i(-1, -1)
	_volume_last_max_steps = -1.0
	_volume_last_cutoff = -1.0
	_volume_last_history_weight = -1.0
	_volume_last_history_depth_tolerance = -1.0
	_volume_last_scheduling = -1.0
	_volume_last_boxless_active = false
	_volume_overload_streak = 0
	_volume_underload_streak = 0
	_invalidate_volume_history_state()


func _volume_clear_signature() -> void:
	_volume_us_sig_shader = RID()
	_volume_us_sig_0 = RID(); _volume_us_sig_1 = RID(); _volume_us_sig_2 = RID()
	_volume_us_sig_3 = RID(); _volume_us_sig_4 = RID(); _volume_us_sig_5 = RID()
	_volume_us_sig_6 = RID(); _volume_us_sig_7 = RID(); _volume_us_sig_8 = RID()
	_volume_us_sig_9 = RID()
	_volume_cache_valid = false
	_volume_set_dirty = true

func _volume_sanitize_tier(v: int) -> int:
	var t := 256 if v <= 384 else (512 if v <= 768 else 1024)
	var lo := 256 if volume_resolution_min <= 384 else (512 if volume_resolution_min <= 768 else 1024)
	var hi := 256 if volume_resolution_max <= 384 else (512 if volume_resolution_max <= 768 else 1024)
	if lo > hi: var swap := lo; lo = hi; hi = swap
	return clampi(t, lo, hi)

func _volume_tier_down(t: int) -> int:
	return 512 if t >= 1024 else 256

func _volume_tier_up(t: int) -> int:
	return 512 if t <= 256 else 1024

func _prepare_volume_resolution() -> bool:
	if mode != 1 or not _ml_boxless_on(): return false
	var manual := _volume_sanitize_tier(volume_resolution_target)
	var manual_changed := manual != _volume_last_requested_tier
	if manual_changed:
		_volume_last_requested_tier = manual
		_volume_pending_tier = 0
		_volume_overload_streak = 0
		_volume_underload_streak = 0
	var target := manual
	var automatic := false
	if volume_dynamic_resolution:
		if _volume_pending_tier != 0:
			target = _volume_sanitize_tier(_volume_pending_tier)
			automatic = true
		else:
			target = _volume_current_tier
	if target == _volume_current_tier and _rt_size.x == target \
			and _field_render_tex.is_valid() and _volume_history_neutral.is_valid():
		_volume_pending_tier = 0
		return false
	_rt_size = Vector2i(target, target)
	_volume_current_tier = target
	_volume_tier_change_count += 1
	_volume_last_tier_change_frame = Engine.get_process_frames()
	_volume_last_tier_change_reason = "auto" if automatic else "manual"
	_volume_pending_tier = 0
	_make_render_textures()
	_invalidate_volume_render_cache()
	return true

func _note_volume_dispatch_frame(frame_ms: float) -> void:
	if not volume_dynamic_resolution:
		_volume_overload_streak = 0
		_volume_underload_streak = 0
		return
	_volume_dispatch_frame_delta = frame_ms
	_volume_dispatch_frame_ema = frame_ms if _volume_dispatch_frame_ema <= 0.0 else (_volume_dispatch_frame_ema * 0.9 + frame_ms * 0.1)
	_volume_eval_counter += 1
	if frame_ms > volume_frame_budget_ms * 1.10:
		_volume_overload_streak += 1
		_volume_underload_streak = 0
	else:
		_volume_overload_streak = 0
	if _volume_overload_streak >= 2:
		_volume_pending_tier = _volume_tier_down(_volume_current_tier)
		_volume_last_tier_change_reason = "overload"
		_volume_downshift_latency = _volume_eval_counter
		_volume_overload_streak = 0
		_volume_underload_streak = 0
	if _volume_dispatch_frame_ema < volume_frame_budget_ms * 0.72:
		_volume_underload_streak += 1
	else:
		_volume_underload_streak = 0
	if _volume_underload_streak >= 120:
		_volume_pending_tier = _volume_tier_up(_volume_current_tier)
		_volume_last_tier_change_reason = "underload"
		_volume_overload_streak = 0
		_volume_underload_streak = 0
func _volume_needs_dispatch(generation: int, site_count: int, cam_transform: Transform3D, fov: float, center: Vector3, ext: Vector3) -> bool:
	if not _volume_cache_valid: return true
	return generation != _volume_last_generation or site_count != _volume_last_site_count or cam_transform != _volume_last_cam_transform or fov != _volume_last_fov or center != _volume_last_window_center or ext != _volume_last_extents or _rt_size != _volume_last_rt_size or _volume_last_max_steps != 128.0 or _volume_last_cutoff != 1e-3
func _sync_volume_uniform_set() -> bool:
	if not _field_render_tex.is_valid() or not _volume_history_neutral.is_valid():
		_volume_set_dirty = true
		return false
	if not _volume_set_dirty and _volume_cache_valid and _us_volume_0.is_valid() \
			and _rd.uniform_set_is_valid(_us_volume_0):
		return true
	var topo: Dictionary = _physics_engine.topology_resources() if _physics_engine != null and _physics_engine.has_method("topology_resources") else {}
	var r0: RID = topo.get("topology_open_label_rid", RID())
	var r1: RID = topo.get("topology_adjacency_rid", RID())
	var r2: RID = topo.get("topology_degree_rid", RID())
	var r3: RID = topo.get("topology_offset_rid", RID())
	var r4: RID = topo.get("topology_neighbor_rid", RID())
	var r5: RID = topo.get("topology_optical_rid", RID())
	var r6: RID = topo.get("topology_status_rid", RID())
	if not r0.is_valid() or not r1.is_valid() or not r2.is_valid() or not r3.is_valid() or not r4.is_valid() or not r5.is_valid() or not r6.is_valid():
		_volume_set_dirty = true
		return false
	if _us_volume_0.is_valid() and _rd.uniform_set_is_valid(_us_volume_0):
		_rd.free_rid(_us_volume_0)
	_us_volume_0 = _rd.uniform_set_create([
		_uniform_storage(0, r0), _uniform_storage(1, r1), _uniform_storage(2, r2), _uniform_storage(3, r3),
		_uniform_storage(4, r4), _uniform_storage(5, r5), _uniform_storage(6, r6),
		_get_set2_image_uniform(_volume_shader, 7, _field_render_tex),
		_get_set2_image_uniform(_volume_shader, 8, _volume_history_neutral),
		_uniform_storage(9, _volume_stats),
	], _volume_shader, 0)
	if not _us_volume_0.is_valid() or not _rd.uniform_set_is_valid(_us_volume_0):
		_volume_clear_signature()
		_volume_set_dirty = true
		return false
	_volume_uniform_set_create_count += 1
	_volume_us_sig_7 = _field_render_tex
	_volume_us_sig_8 = _volume_history_neutral
	_volume_us_sig_9 = _volume_stats
	_volume_cache_valid = true
	_volume_set_dirty = false
	return true

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

	# Fused site-volume producer (cassi_voronoi_fused_volume.glsl).
	_volume_shader = _shader_from_file("res://compute/cassi_voronoi_fused_volume.glsl")
	if _volume_shader.is_valid():
		_volume_pipe = _rd.compute_pipeline_create(_volume_shader)
		print("[CassiSim] fused volume pipeline ready")
		print("[CassiSim] Field render pipeline ready")

	# Optional presentation layers are isolated from the solver/instancer
	# contracts. Their MultiMesh buffers are allocated lazily only when their
	# default-off visual toggles become active.
	_macro_lod_shader = _shader_from_file("res://compute/cassi_presentation_macro_lod.glsl")
	if _macro_lod_shader.is_valid():
		_macro_lod_pipe = _rd.compute_pipeline_create(_macro_lod_shader)
		print("[CassiSim] presentation macro LOD pipeline ready")
	_trail_shader = _shader_from_file("res://compute/cassi_presentation_trails.glsl")
	if _trail_shader.is_valid():
		_trail_pipe = _rd.compute_pipeline_create(_trail_shader)
		print("[CassiSim] presentation trail pipeline ready")
	if rotation_stress_enabled and rotation_orientation_render_enabled:
		_rotation_axis_shader = _shader_from_file(
			"res://compute/cassi_rotation_orientation_instancer.glsl")
		if _rotation_axis_shader.is_valid():
			_rotation_axis_pipe = _rd.compute_pipeline_create(_rotation_axis_shader)
			print("[CassiSim] rotation orientation-axis pipeline ready")
	_volume_history_shader = _shader_from_file("res://compute/cassi_voronoi_fused_volume_history.glsl")
	if _volume_history_shader.is_valid():
		_volume_history_pipe = _rd.compute_pipeline_create(_volume_history_shader)
		print("[CassiSim] presentation volume current pipeline ready")
	_volume_reproject_shader = _shader_from_file("res://compute/cassi_volume_reproject.glsl")
	if _volume_reproject_shader.is_valid():
		_volume_reproject_pipe = _rd.compute_pipeline_create(_volume_reproject_shader)
		print("[CassiSim] presentation volume reprojection pipeline ready")


	# Particle instancer
	_instancer_shader = _shader_from_file("res://compute/cassi_instancer.glsl")
	if _instancer_shader.is_valid():
		_instancer_pipe = _rd.compute_pipeline_create(_instancer_shader)
		print("[CassiSim] Instancer pipeline ready")

	# Arm 1 coherence-filtered site shortlist (cassi_site_shortlist.glsl):
	# reduces the moving-Voronoi sites to the coherent subset the boxless
	# instancer samples. Pipeline created when the shader imported; the
	# uniform set binds the site psi buffers + the shortlist outputs.
	_shortlist_shader = _shader_from_file("res://compute/cassi_site_shortlist.glsl")
	if _shortlist_shader.is_valid():
		_shortlist_pipe = _rd.compute_pipeline_create(_shortlist_shader)
		_us_shortlist = _rd.uniform_set_create([
			_uniform_storage(0, _ml_sites),
			_uniform_storage(1, _ml_psi_y),
			_uniform_storage(2, _ml_psi_i),
			_uniform_storage(3, _shortlist_sites),
			_uniform_storage(4, _shortlist_count),
		], _shortlist_shader, 0)
		print("[CassiSim] shortlist pipeline ready (set valid=", _us_shortlist.is_valid(), ")")
	# Boxless site hash (cassi_site_hash.glsl): buckets the shortlist into the
	# uniform grid for the boxless instancer's bounded-ring nearest-site query.
	_hash_shader = _shader_from_file("res://compute/cassi_site_hash.glsl")
	if _hash_shader.is_valid():
		_hash_pipe = _rd.compute_pipeline_create(_hash_shader)
		_us_hash = _rd.uniform_set_create([
			_uniform_storage(0, _shortlist_sites),
			_uniform_storage(1, _hash_cell_start),
			_uniform_storage(2, _hash_cell_sites),
			_uniform_storage(3, _hash_cell_count),
			_uniform_storage(4, _shortlist_count),
		], _hash_shader, 0)
		print("[CassiSim] boxless site-hash pipeline ready (set valid=", _us_hash.is_valid(), ")")

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

	# Particle merge (only needed when particle_merge; the pipeline + set are
	# created on the init-time toggle so the default-off battery is bit-identical)
	if particle_merge:
		_merge_shader = _shader_from_file("res://compute/cassi_particle_merge.glsl")
		if _merge_shader.is_valid():
			_merge_pipe = _rd.compute_pipeline_create(_merge_shader)
			print("[CassiSim] particle-merge pipeline ready")
		# On-GPU exclusive scan (FIX B) — only needed when the merge runs.
		_scan_shader = _shader_from_file("res://compute/cassi_exclusive_scan.glsl")
		if _scan_shader.is_valid():
			_scan_pipe = _rd.compute_pipeline_create(_scan_shader)
			print("[CassiSim] exclusive-scan pipeline ready")
	# BH accretion (only when bh_accretion; the pipeline + set are created on
	# the init-time toggle so the default-off path is bit-identical)
	if bh_accretion:
		_bh_acc_shader = _shader_from_file("res://compute/cassi_bh_accretion.glsl")
		if _bh_acc_shader.is_valid():
			_bh_acc_pipe = _rd.compute_pipeline_create(_bh_acc_shader)
			print("[CassiSim] bh-accretion pipeline ready")


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
	# Tree momentum-conservation pass (cassi_tree_momcon.glsl): the Reduce
	# accumulator (16 B) is allocated here; the uniform set binds acc/pos/sum.
	_tree_mc_shader = _shader_from_file("res://compute/cassi_tree_momcon.glsl")
	if _tree_mc_shader.is_valid():
		_tree_mc_pipe = _rd.compute_pipeline_create(_tree_mc_shader)
		_tree_mc_buf = _rd.storage_buffer_create(2 * 16)   # vec4[2] reduce accumulator
		_tree_mc_pc_bytes = PackedByteArray(); _tree_mc_pc_bytes.resize(3 * 4)
		_sync_us_tree_mc()
		print("[CassiSim] tree-momcon pipeline ready")

	# Position blend (snapshot/interpolation seam — cassi_blend_pos.glsl).
	# DORMANT: the host pins alpha to 1.0, so pos_render == pos bit-for-bit
	# and rendering is identical to today; the decoupled physics producer
	# will vary _interp_alpha later. The pipe is included in _shaders_ready
	# (the blend dispatches gate on _blend_sh.is_valid()).
	_blend_sh = _shader_from_file("res://compute/cassi_blend_pos.glsl")
	if _blend_sh.is_valid():
		_blend_pipe = _rd.compute_pipeline_create(_blend_sh)
		print("[CassiSim] blend pipeline ready")

	if _field_intelligence != null and _field_intelligence.compile_shader():
		print("[CassiSim] embodied field-intelligence pipeline ready")
	_cache_uniform_sets()
	_shaders_ready = (
		_two_fluid_shader.is_valid() and _nbody_shader.is_valid()
		and _poisson_shader.is_valid() and _mass_deposit_shader.is_valid()
		and _instancer_shader.is_valid() and _cond_shader.is_valid()
		and _bh_int_shader.is_valid() and _field_render_shader.is_valid()
		# Tree arm must be genuinely ready too, else the retry loop stops
		# while the tree uniform sets/pipes are missing (Godot silently
		# no-ops a dispatch with an absent set).
		and (_tree_build_pipe.is_valid() or not _ml_need_tree())
		and (_tree_grav_pipe.is_valid() or not _ml_need_tree())
		and (_tree_mc_pipe.is_valid() or not _ml_need_tree())
		and (_us_tree_build.is_valid() or not _ml_need_tree())
		and (_us_tree_grav.is_valid() or not _ml_need_tree())
		and (_us_tree_mc.is_valid() or not _ml_need_tree())
		and (_field_intelligence == null or _field_intelligence.ready()))


func _cache_uniform_sets() -> void:
	# NOTE: must only run with all cached sets already released — callers
	# (reinit, shader-retry, startup) free them via _free_uniform_sets()
	# first. Recreating a live set would leak its RID. Texture-only rebuilds
	# go through _cache_render_texture_sets() instead.
	# Two-fluid PDE set 0: fields + rho + scratch + descriptor-safe FI
	# buffers. The helper allocates one cell while disabled; reflection still
	# requires both descriptors even though the default branch is OFF.
	_us_two_0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		_uniform_storage(4, _mass_density_buf),
		_uniform_storage(5, _field_scratch),
		_uniform_storage(6, _field_intelligence.plasticity_buffer()),
		_uniform_storage(7, _field_intelligence.state_buffer()),
	], _two_fluid_shader, 0)
	if _field_intelligence != null:
		_field_intelligence.cache_uniform_set(_pos_buf)

	_us_nbody_0 = _rd.uniform_set_create([
		_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
		_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
		_uniform_storage(4, _mass_density_buf),
		_uniform_storage(5, _fft_buf),
		_uniform_storage(6, _tel_buf),
		_uniform_storage(7, _grad_buf),
		_uniform_storage(8, _grad_buf2),  # dual-lattice ∇(g·Φ) (CASCADE_GRID.md)
		_uniform_storage(9, _grad_buf),   # cascade placeholder; bh[0].x gates the blend
	], _nbody_shader, 0)
	_us_nbody_1 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf), _uniform_storage(1, _vel_buf),
		_uniform_storage(2, _acc_buf),
		_uniform_storage(3, _ml_tree_grad),  # tree-river (mode 5): per-particle ∇Φ_g
	], _nbody_shader, 1)
	# Poisson solver (set 0: FFT workspace + mass density + telemetry +
	# the int64 fixed-point accumulator the clear pass zeroes)
	if _poisson_shader.is_valid():
		_us_poisson_0 = _rd.uniform_set_create([
			_uniform_storage(0, _fft_buf),
			_uniform_storage(1, _mass_density_buf),
			_uniform_storage(2, _tel_buf),
			_uniform_storage(3, _mass_density_fix),
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
	# Particle merge (set 0: all 15 bindings — pos/vel + per-particle state +
	# EY/EI coherence field + hash scratch + merge counter). Created only when
	# the init-time feature is on (its buffers only exist then).
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
			_uniform_storage(25, _shortlist_sites), _uniform_storage(26, _hash_cell_start),
			_uniform_storage(27, _hash_cell_sites), _uniform_storage(28, _hash_cfg),
			_uniform_storage(29, _shortlist_count),
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
	_us_nbody_2 = _rd.uniform_set_create([
		_uniform_storage(0, _bh_buf),
		_uniform_storage(1, _cluster_buf),  # Plummer reference arm (mode 2)
	], _nbody_shader, 2)
	_sync_us_tree_mc()

	# Field render (cached sets — was rebuilt every frame in _dispatch_compute)
	# NOTE: the field-render shader declares only set 0 (fields) and set 2
	# (image) — NO set 1; creating one errors "Desired set (1) not used".
	if _field_render_shader.is_valid():
		_us_fr_0 = _rd.uniform_set_create([
			_uniform_storage(0, _field_ey), _uniform_storage(1, _field_ei),
			_uniform_storage(2, _field_q), _uniform_storage(3, _field_vel),
			_uniform_storage(4, _field_intelligence.plasticity_buffer()),
			_uniform_storage(5, _field_intelligence.state_buffer()),
		], _field_render_shader, 0)
		if _field_render_tex.is_valid():
			_us_fr_2 = _rd.uniform_set_create([
				_get_set2_image_uniform(_field_render_shader, 0, _field_render_tex),
			], _field_render_shader, 2)


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
			_uniform_storage(6, _lut_u_buf_off),  # LUT-mode flag: OFF → legacy color writes, byte-identical
			_uniform_storage(7, _shortlist_sites),  # Arm 1 boxless shortlist (flag.y=0 → unused)
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		# RENDER variant — identical except binding 0 (Positions) reads the
		# interpolated snapshot _pos_render_buf. Bound for the per-frame
		# instancer dispatch (see _run_physics_steps) so the renderer draws
		# pos_render; at the DORMANT alpha = 1.0 that IS pos, so rendering
		# stays bit-identical — the whole point of the dormant seam.
		_us_inst_0_render = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, _vel_buf),
			_uniform_storage(3, _field_q),
			_uniform_storage(4, _field_ey),
			_uniform_storage(5, _field_ei),
			_uniform_storage(6, _lut_u_buf_off),
			_uniform_storage(7, _shortlist_sites),
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		# COLOR-AS-LUT variants (Tier-2): identical bindings except binding 6
		# reads the ON flag buffer — the set selection IS the LUT-mode switch
		# (the shader writes custom_data (u, glow_boost, depth_fade, spare)
		# instead of a color and the billboard material samples the baked LUT
		# at INSTANCE_CUSTOM.x, applying the VFX factors on top).
		_us_inst_0_lut = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, _vel_buf),
			_uniform_storage(3, _field_q),
			_uniform_storage(4, _field_ey),
			_uniform_storage(5, _field_ei),
			_uniform_storage(6, _lut_u_buf_on),
			_uniform_storage(7, _shortlist_sites),
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		_us_inst_0_lut_render = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, _vel_buf),
			_uniform_storage(3, _field_q),
			_uniform_storage(4, _field_ey),
			_uniform_storage(5, _field_ei),
			_uniform_storage(6, _lut_u_buf_on),
			_uniform_storage(7, _shortlist_sites),
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		# ── Arm 1 BOXLESS variants: flag.y = 1 → the instancer reads the
		# moving-Voronoi sites via the coherence-filtered shortlist. Selected
		# only when _ml_boxless_on(); otherwise dead (never dispatched).
		_us_inst_0_boxless = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, _vel_buf),
			_uniform_storage(3, _field_q),
			_uniform_storage(4, _field_ey),
			_uniform_storage(5, _field_ei),
			_uniform_storage(6, _shortlist_flag_off),  # .y=1 boxless, .x=0 (legacy flags)
			_uniform_storage(7, _shortlist_sites),
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		_us_inst_0_render_boxless = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, _vel_buf),
			_uniform_storage(3, _field_q),
			_uniform_storage(4, _field_ey),
			_uniform_storage(5, _field_ei),
			_uniform_storage(6, _shortlist_flag_off),
			_uniform_storage(7, _shortlist_sites),
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		_us_inst_0_lut_boxless = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, _vel_buf),
			_uniform_storage(3, _field_q),
			_uniform_storage(4, _field_ey),
			_uniform_storage(5, _field_ei),
			_uniform_storage(6, _shortlist_flag_on),   # .y=1 boxless, .x=1 (LUT flags)
			_uniform_storage(7, _shortlist_sites),
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		_us_inst_0_lut_render_boxless = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _mm_rd_rid),
			_uniform_storage(2, _vel_buf),
			_uniform_storage(3, _field_q),
			_uniform_storage(4, _field_ey),
			_uniform_storage(5, _field_ei),
			_uniform_storage(6, _shortlist_flag_on),
			_uniform_storage(7, _shortlist_sites),
			_uniform_storage(8, _ml_psi_y),
			_uniform_storage(9, _ml_psi_i),
			_uniform_storage(10, _shortlist_count),
			_uniform_storage(11, _hash_cell_start),
			_uniform_storage(12, _hash_cell_sites),
			_uniform_storage(13, _hash_cfg),
		], _instancer_shader, 0)
		print("[CassiSim] Instancer uniform sets cached (GPU-direct multimesh buffer; LUT variants %s)" % ("ready" if _lut_u_buf_on.is_valid() else "SKIPPED"))

	# Mass deposit (set 0: positions + float rho + int64 fix accumulator)
	_us_mass_dep_0 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_buf),
		_uniform_storage(1, _mass_density_buf),
		_uniform_storage(2, _mass_density_fix),
	], _mass_deposit_shader, 0)
	print("[CassiSim] Mass deposit uniform set cached")



	# Occupancy sampler (diagnostic; CPU fallback if invalid — the shader
	# is optional and excluded from _shaders_ready).
	if _occ_shader.is_valid() and _pos_buf.is_valid() and _occ_buf.is_valid() and _occ_sample_buf.is_valid():
		_us_occ_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _occ_buf),
			_uniform_storage(2, _occ_sample_buf),
		], _occ_shader, 0)

	# q-histogram sampler (auto color-align; optional like occupancy)
	if _qhist_shader.is_valid() and _pos_buf.is_valid() and _field_q.is_valid() and _qhist_buf.is_valid():
		_us_qhist_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_buf),
			_uniform_storage(1, _field_q),
			_uniform_storage(2, _qhist_buf),
			_uniform_storage(3, _field_ey),
			_uniform_storage(4, _field_ei),
			_uniform_storage(5, _ml_sites),
			_uniform_storage(6, _ml_psi_y),
			_uniform_storage(7, _ml_psi_i),
		], _qhist_shader, 0)
		# RENDER variant (decoupled): binding 0 reads the interpolated
		# pos_render — the same snapshot the instancer draws. No shader edit.
		_us_qhist_0_render = _rd.uniform_set_create([
			_uniform_storage(0, _pos_render_buf),
			_uniform_storage(1, _field_q),
			_uniform_storage(2, _qhist_buf),
			_uniform_storage(3, _field_ey),
			_uniform_storage(4, _field_ei),
			_uniform_storage(5, _ml_sites),
			_uniform_storage(6, _ml_psi_y),
			_uniform_storage(7, _ml_psi_i),
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
			_uniform_storage(14, _ml_tree_nqq),
		], _tree_build_shader, 0)
		if not _us_tree_build.is_valid():
			push_error("[CassiSim] tree-build uniform set FAILED to create (bindings 0-14)")
	if _tree_grav_shader.is_valid() and _ml_need_tree():
		_us_tree_grav = _rd.uniform_set_create([
			_uniform_storage(0, _ml_tree_src), _uniform_storage(3, _ml_tree_order),
			_uniform_storage(4, _ml_tree_cf), _uniform_storage(5, _ml_tree_w),
			_uniform_storage(6, _ml_tree_q), _uniform_storage(7, _ml_tree_r),
			_uniform_storage(8, _ml_tree_ctr),
			_uniform_storage(9, _ml_tree_grad), _uniform_storage(10, _ml_tree_icount),
			_uniform_storage(11, _pos_buf),  # walk TargetPos — targets = N-body particles (use_tp=1)
			_uniform_storage(14, _ml_tree_nqq),
		], _tree_grav_shader, 0)
		if not _us_tree_grav.is_valid():
			push_error("[CassiSim] tree-walk uniform set FAILED to create (bindings 0,3-11,14)")
	# Position blend (cassi_blend_pos.glsl, set 0): pos_prev, pos,
	# pos_render — bindings 0, 1, 2. Created whenever the shader compiled;
	# the buffers are always allocated (maxi(N_particles, 1) sizing).
	if _blend_sh.is_valid():
		_us_blend_0 = _rd.uniform_set_create([
			_uniform_storage(0, _pos_prev_buf),
			_uniform_storage(1, _pos_buf),
			_uniform_storage(2, _pos_render_buf),
		], _blend_sh, 0)
		if not _us_blend_0.is_valid():
			push_error("[CassiSim] blend uniform set FAILED to create (bindings 0-2)")


## (Re)build the tree momentum-conservation uniform set (acc, positions, the
## 16-B Reduce accumulator). Called from _cache_uniform_sets and once after
## the shader/pipeline exist at setup; the acc/pos buffers are stable across
## frames (realloc'd only on count change via _cache_uniform_sets).
func _sync_us_tree_mc() -> void:
	if not _tree_mc_shader.is_valid() or not _acc_buf.is_valid() or not _pos_buf.is_valid() or not _vel_buf.is_valid() or not _tree_mc_buf.is_valid():
		return
	_us_tree_mc = _rd.uniform_set_create([
		_uniform_storage(0, _acc_buf),
		_uniform_storage(1, _pos_buf),
		_uniform_storage(2, _tree_mc_buf),
		_uniform_storage(3, _vel_buf),
	], _tree_mc_shader, 0)
	if not _us_tree_mc.is_valid():
		push_error("[CassiSim] tree-momcon uniform set FAILED to create (bindings 0-3)")


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
	if ic_seed != 0:
		rng.seed = ic_seed

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


## Current presentation focus. Static scenes retain the spawn centroid;
## tracking scenes follow the measured render envelope rather than a stale
## initialization coordinate. This is camera-only and never feeds physics.
func get_presentation_camera_target() -> Vector3:
	if home_window_enabled or tracking_envelope:
		return _window_center
	return _cluster_centroid()


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


## Keep the sibling camera's far plane beyond both the tracked cloud and the
## current viewpoint. `camera_far_plane` is a floor, not a ceiling. Within a
## display profile the range only grows; entering presentation may clamp an
## unsafe Forward+ projection because its particle shader carries far depth.
func _apply_camera_view_range() -> void:
	if _sim_cam == null:
		return
	var cloud_radius: float = maxf(_extents().length() * 1.25, 1.0)
	var required_far: float = (
			_sim_cam.global_position.distance_to(_window_center) + cloud_radius) * 1.25
	if is_finite(required_far):
		var target_far := maxf(camera_far_plane, required_far)
		if presentation_profile:
			target_far = minf(target_far, PRESENTATION_SAFE_CAMERA_FAR)
			if _sim_cam.far > PRESENTATION_SAFE_CAMERA_FAR:
				_sim_cam.far = PRESENTATION_SAFE_CAMERA_FAR
		if target_far > _sim_cam.far:
			_sim_cam.far = target_far


## Hotkey F (added 2026-08-15): the old auto pull-back limit was scrapped —
## it locked the camera out of the tracked envelope and lost sight of the
## cloud as the structure moved/expanded. Instead the camera flies freely
## and F snaps it back onto the particle cloud: recenter on the tracked
## envelope/window center (_window_center — the moving field-grid origin;
## zero when envelope/home-window tracking is off) along the camera's
## current view direction, at a distance that fits the box in view, and
## re-aim. Free-fly controls are unaffected afterwards.
func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_F:
		_frame_camera_on_cloud()
		get_viewport().set_input_as_handled()


func _frame_camera_on_cloud() -> void:
	if _sim_cam == null:
		return
	var target := _window_center                      # envelope/home-window center; origin when off
	var r: float = _extents().length() * 1.1          # box half-diagonal × pad
	var dist: float = maxf(r / sin(deg_to_rad(_sim_cam.fov) * 0.5), 10.0)
	var fwd: Vector3 = -_sim_cam.global_transform.basis.z   # camera's forward
	_sim_cam.global_position = target - fwd * dist
	_sim_cam.look_at(target, Vector3.UP)
	_apply_camera_view_range()
	print("[CassiSim] F: camera centered on cloud (%.1f, %.1f, %.1f) at %.1f u" % [
		target.x, target.y, target.z, dist])


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
	sites.resize(ml_ns * 4)
	var site_offset := 0
	for i in range(ML_N1):
		for j in range(ML_N1):
			for k in range(ML_N1):
				sites[site_offset] = float(i) * sx + rng.randf_range(-0.2, 0.2) * sx
				sites[site_offset + 1] = float(j) * sy + rng.randf_range(-0.2, 0.2) * sy
				sites[site_offset + 2] = float(k) * sz + rng.randf_range(-0.2, 0.2) * sz
				site_offset += 4
				sites[site_offset] = (float(i) + 0.5) * sx + rng.randf_range(-0.2, 0.2) * sx
				sites[site_offset + 1] = (float(j) + 0.5) * sy + rng.randf_range(-0.2, 0.2) * sy
				sites[site_offset + 2] = (float(k) + 0.5) * sz + rng.randf_range(-0.2, 0.2) * sz
				site_offset += 4
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
	# Pre-sized in-place encode (review_sim.md #5): _jfa_pc_bytes is sized
	# 8*4 B at init; zero per-call allocations, byte-identical to the old
	# PackedFloat32Array([...]).to_byte_array() (same values, same order).
	_jfa_pc_bytes.encode_float(0, float(N))
	_jfa_pc_bytes.encode_float(4, float(jp))
	_jfa_pc_bytes.encode_float(8, float(read_a))
	_jfa_pc_bytes.encode_float(12, float(ml_ns))
	_jfa_pc_bytes.encode_float(16, 2.0 * ext.x / float(N))
	_jfa_pc_bytes.encode_float(20, 2.0 * ext.y / float(N))
	_jfa_pc_bytes.encode_float(24, 2.0 * ext.z / float(N))
	_jfa_pc_bytes.encode_float(28, 0.0)
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
	# Pre-sized in-place encode (review_sim.md #5): _cell_pc_bytes is sized
	# 18*4 B at init; encode every field here so each call does ZERO
	# allocations. Byte-identical to the old `PackedFloat32Array([...]).
	# to_byte_array()` — same values, same order (PackedFloat32Array is
	# float32 LE and to_byte_array copies those bytes verbatim, which is
	# exactly what encode_float writes).
	var N = grid_N
	var ml_ns = 2 * ML_N1 * ML_N1 * ML_N1
	var ext := _extents()
	var hx: float = 2.0 * ext.x / float(N)
	var hy: float = 2.0 * ext.y / float(N)
	var hz: float = 2.0 * ext.z / float(N)
	var h_min: float = minf(hx, minf(hy, hz))
	var c2: float = h_min * h_min  # the grid's 19-point stencil reads h₀²∇² — match it
	_cell_pc_bytes.encode_float(0, mode)
	_cell_pc_bytes.encode_float(4, float(N))
	_cell_pc_bytes.encode_float(8, float(ml_ns))
	_cell_pc_bytes.encode_float(12, dt)
	_cell_pc_bytes.encode_float(16, hx)
	_cell_pc_bytes.encode_float(20, hy)
	_cell_pc_bytes.encode_float(24, hz)
	_cell_pc_bytes.encode_float(28, c2)
	_cell_pc_bytes.encode_float(32, ML_OM2)
	_cell_pc_bytes.encode_float(36, PHI)
	_cell_pc_bytes.encode_float(40, source_strength)
	_cell_pc_bytes.encode_float(44, ML_RHO_FLOOR)
	_cell_pc_bytes.encode_float(48, ML_MAX_DRIFT)
	_cell_pc_bytes.encode_float(52, ML_KAPPA)
	_cell_pc_bytes.encode_float(56, ML_LAM)
	_cell_pc_bytes.encode_float(60, dt * float(_ml_rebuild_threshold()))
	_cell_pc_bytes.encode_float(64, ML_LLOYD_P)
	_cell_pc_bytes.encode_float(68, winding_coupling)  # J_wind (amendment 3c append)
	return _cell_pc_bytes


func _ml_cell_dispatch(mode: float, groups: int) -> void:
	_ml_cell_pc(mode)
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
	_ml_cell_pc(7.0)
	# The hash config is a host-written buffer and must be updated before
	# opening the command list; RenderingDevice forbids buffer_update while
	# any compute list is being recorded.
	var hext_s: Vector3 = _extents()
	var hcells_s := HASH_H * HASH_H * HASH_H
	var hcs_cfg := (2.0 * hext_s.x) / float(HASH_H)
	_hash_cfg_bytes.encode_float(0, _window_center.x)
	_hash_cfg_bytes.encode_float(4, _window_center.y)
	_hash_cfg_bytes.encode_float(8, _window_center.z)
	_hash_cfg_bytes.encode_float(12, hcs_cfg)
	_rd.buffer_update(_hash_cfg, 0, _hash_cfg_bytes.size(), _hash_cfg_bytes)
	
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	# 1. reset vol + cen
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 2. centroid accumulate (the OLD mesh)
	_ml_cell_pc(3.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 3. steer: new sites + remap index (reads the OLD labels)
	_ml_cell_pc(4.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 4. ALE remap: state → temp → gathered state
	_ml_cell_pc(5.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	_ml_cell_pc(6.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 5. labels clear + scatter (the NEW sites)
	_ml_cell_pc(8.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	_ml_cell_pc(9.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wgs, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 6. JFA (the ping-pong passes share this list)
	_rd.compute_list_bind_compute_pipeline(cl, _jfa_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_jfa_0, 0)
	var read_a := 1
	_jfa_pc_bytes.encode_float(0, float(N))
	_jfa_pc_bytes.encode_float(12, float(ml_ns))
	_jfa_pc_bytes.encode_float(16, hx_rb)
	_jfa_pc_bytes.encode_float(20, hy_rb)
	_jfa_pc_bytes.encode_float(24, hz_rb)
	_jfa_pc_bytes.encode_float(28, 0.0)
	for jp in ML_JFA_JUMPS:
		_jfa_pc_bytes.encode_float(4, float(jp))
		_jfa_pc_bytes.encode_float(8, float(read_a))
		_rd.compute_list_set_push_constant(cl, _jfa_pc_bytes, _jfa_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		read_a = 1 - read_a
	_jfa_pc_bytes.encode_float(4, 0.0)
	_jfa_pc_bytes.encode_float(8, 0.0)
	_rd.compute_list_set_push_constant(cl, _jfa_pc_bytes, _jfa_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 7. volume accumulate (the NEW mesh)
	_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
	_ml_cell_pc(2.0)
	_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
	_rd.compute_list_dispatch(cl, wg1, 1, 1)
	_rd.compute_list_add_barrier(cl)
	# 8. Arm 1: site shortlist (on the steer cadence). Boxless merge needs the
	# full list for its exact indexed nearest-site query; otherwise retain the
	# coherence-filtered list consumed by the per-frame boxless instancer.
	if _shortlist_pipe.is_valid() and _us_shortlist.is_valid():
		_rd.compute_list_bind_compute_pipeline(cl, _shortlist_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_shortlist, 0)
		var shortlist_floor := 0.0 if particle_merge and boxless_field else SS_Q_FLOOR
		_shortlist_pc_bytes.encode_float(0, float(ml_ns))
		_shortlist_pc_bytes.encode_float(4, shortlist_floor)
		_shortlist_pc_bytes.encode_float(8, 0.0)
		_rd.compute_list_set_push_constant(cl, _shortlist_pc_bytes, _shortlist_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_shortlist_pc_bytes.encode_float(8, 1.0)
		_rd.compute_list_set_push_constant(cl, _shortlist_pc_bytes, _shortlist_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wgs, 1, 1)
		_rd.compute_list_add_barrier(cl)
	# Boxless site hash (boxless_site_hash_prereg.md): bucket the just-built
	# shortlist into the uniform grid (in-chain — the shader reads the LIVE count
	# via binding 4 after the barrier, so no host readback / extra sync). The
	# boxless instancer sets read these; off by construction when flag.y = 0.
	if _hash_pipe.is_valid() and _us_hash.is_valid():
		# _hash_cfg was reset before compute_list_begin() above.
		_rd.compute_list_bind_compute_pipeline(cl, _hash_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_hash, 0)
		_hash_pc_bytes.encode_float(0, hext_s.x)
		_hash_pc_bytes.encode_float(4, hext_s.y)
		_hash_pc_bytes.encode_float(8, hext_s.z)
		_hash_pc_bytes.encode_float(12, float(HASH_H))
		_hash_pc_bytes.encode_float(16, float(ml_ns))
		_hash_pc_bytes.encode_float(20, 0.0)
		_hash_pc_bytes.encode_float(24, 0.0)
		_hash_pc_bytes.encode_float(28, 0.0)
		_hash_pc_bytes.encode_float(32, 0.0)
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		_rd.compute_list_dispatch(cl, ceili(float(hcells_s) / 64.0), 1, 1)
		_rd.compute_list_add_barrier(cl)
		_hash_pc_bytes.encode_float(32, 1.0)
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wgs, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_hash_pc_bytes.encode_float(32, 2.0)
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_rd.compute_list_add_barrier(cl)
		_hash_pc_bytes.encode_float(32, 3.0)
		_rd.compute_list_set_push_constant(cl, _hash_pc_bytes, _hash_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wgs, 1, 1)
		_rd.compute_list_add_barrier(cl)
	_rd.compute_list_end()



func _init_particles() -> void:
	var pos = PackedFloat32Array(); pos.resize(N_particles * 4)
	var vel = PackedFloat32Array(); vel.resize(N_particles * 4)
	var acc = PackedFloat32Array(); acc.resize(N_particles * 4)

	var rng = RandomNumberGenerator.new()
	if ic_seed != 0:
		rng.seed = ic_seed
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
		# Applied in WORLD space (the modes span the whole box). The
		# displacement is projected back into the cluster's safe sphere
		# afterward so the cascade seed cannot violate the IC containment
		# contract at the edge of the truncated support.
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
			var displaced := Vector3(wx - center.x, wy - center.y, wz - center.z)
			var displaced_r: float = displaced.length()
			if displaced_r > r_max_eff and displaced_r > 0.0:
				displaced *= r_max_eff / displaced_r
			pos[i4] = center.x + displaced.x
			pos[i4 + 1] = center.y + displaced.y
			pos[i4 + 2] = center.z + displaced.z

		var local_x: float = pos[i4] - center.x
		var local_y: float = pos[i4 + 1] - center.y
		var local_z: float = pos[i4 + 2] - center.z
		var rr: float = sqrt(local_x * local_x + local_y * local_y + local_z * local_z)
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
		var color_base_init: int = int(particle_color_mode) & 0xF
		if color_base_init == 0:
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
var _volume_texture_2d: Texture2D = null
var _rt_size: Vector2i = Vector2i(512, 512)


func _make_render_texture(width: int, height: int) -> RID:
	var fmt = RDTextureFormat.new()
	fmt.width = width
	fmt.height = height
	fmt.format = RenderingDevice.DATA_FORMAT_R32G32B32A32_SFLOAT
	# The compute pass writes this image and Texture2DRD samples it directly
	# through the main renderer. COPY_FROM is intentionally omitted: field
	# presentation never reads the texture back to the CPU.
	# The compute pass writes this image and Texture2DRD samples it directly.
	# COPY_FROM is included for the volume history lifecycle.
	fmt.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT \
				   | RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT \
				   | RenderingDevice.TEXTURE_USAGE_CAN_COPY_FROM_BIT \
				   | RenderingDevice.TEXTURE_USAGE_CAN_UPDATE_BIT
	var view := RDTextureView.new()
	return _rd.texture_create(fmt, view, [])


func _make_render_depth_texture(width: int, height: int) -> RID:
	var fmt := RDTextureFormat.new()
	fmt.width = width
	fmt.height = height
	fmt.format = RenderingDevice.DATA_FORMAT_R32_SFLOAT
	fmt.usage_bits = RenderingDevice.TEXTURE_USAGE_STORAGE_BIT \
				   | RenderingDevice.TEXTURE_USAGE_SAMPLING_BIT \
				   | RenderingDevice.TEXTURE_USAGE_CAN_UPDATE_BIT
	return _rd.texture_create(fmt, RDTextureView.new(), [])


func _get_set2_image_uniform(shader: RID, binding: int, tex: RID) -> RDUniform:
	var u = RDUniform.new()
	u.uniform_type = RenderingDevice.UNIFORM_TYPE_IMAGE
	u.binding = binding
	u.add_id(tex)
	return u




func _field_intelligence_profile() -> String:
	return "%d|%.9f|%.9f|%.9f|%.9f|%.9f|%d|%d|%d|%.9f|%.9f|%.9f" % [
		grid_N, field_intelligence_eta, field_intelligence_gamma,
		field_intelligence_decay, field_intelligence_p_max,
		field_intelligence_actuation, field_intelligence_reward_control,
		field_intelligence_explore_period, field_intelligence_explore_steps,
		field_intelligence_organ_radius, field_intelligence_context_radius,
		field_intelligence_kernel_radius]


func _update_field_intelligence_params() -> void:
	_field_intelligence_params["eta"] = field_intelligence_eta
	_field_intelligence_params["gamma"] = field_intelligence_gamma
	_field_intelligence_params["decay"] = field_intelligence_decay
	_field_intelligence_params["p_max"] = field_intelligence_p_max
	_field_intelligence_params["actuation"] = field_intelligence_actuation
	_field_intelligence_params["energy_penalty"] = field_intelligence_energy_penalty
	_field_intelligence_params["explore_period"] = field_intelligence_explore_period
	_field_intelligence_params["explore_steps"] = field_intelligence_explore_steps
	_field_intelligence_params["context_radius"] = field_intelligence_context_radius
	_field_intelligence_params["kernel_radius"] = field_intelligence_kernel_radius


func _ensure_field_intelligence_render_target() -> bool:
	if not _field_render_pipe.is_valid() or not _us_fr_0.is_valid():
		return false
	if not _field_render_tex.is_valid():
		_make_render_textures()
		_cache_render_texture_sets()
	if not _field_render_tex.is_valid() or not _us_fr_2.is_valid():
		return false
	if field_display_texture == null or not (field_display_texture is Texture2DRD):
		field_display_texture = CassiGpuTextureBridge.wrap(_field_render_tex)
	return field_display_texture != null


func _record_field_intelligence_view(cl: int) -> void:
	if not _field_render_pipe.is_valid() or not _us_fr_0.is_valid() \
			or not _us_fr_2.is_valid() or not _field_render_tex.is_valid():
		return
	_pc_bytes.encode_float(0, float(grid_N))
	_pc_bytes.encode_float(4, dt)
	_pc_bytes.encode_float(8, _time)
	_pc_bytes.encode_float(12, PHI)
	_pc_bytes.encode_float(16, xi)
	_pc_bytes.encode_float(20, softening * softening)
	_pc_bytes.encode_float(24, float(N_particles))
	_pc_bytes.encode_float(28, 5.0)  # phase field + live P/e inset
	_pc_bytes.encode_float(32, field_intelligence_p_max)
	_pc_bytes.encode_float(36, float(num_clusters))
	_pc_bytes.encode_float(40, float(gravity_mode))
	_barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _field_render_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_fr_0, 0)
	_rd.compute_list_bind_uniform_set(cl, _us_fr_2, 2)
	_rd.compute_list_set_push_constant(cl, _pc_bytes, _pc_bytes.size())
	_rd.compute_list_dispatch(cl, ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1)
	_barrier(cl)


func field_intelligence_set_target(target: Vector3, radius: float, training: bool = true) -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	if playing:
		return {"ok": false, "error": "pause_required"}
	return _field_intelligence.set_target(target, radius, training)


func field_intelligence_set_training(training: bool) -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	if playing:
		return {"ok": false, "error": "pause_required"}
	return _field_intelligence.set_training(training)


func field_intelligence_set_probe_state(position: Vector3, velocity: Vector3 = Vector3.ZERO,
		mass: float = 1.0, probe_index: int = -1) -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	if playing:
		return {"ok": false, "error": "pause_required"}
	var index := field_intelligence_probe_index if probe_index < 0 else probe_index
	if index != field_intelligence_probe_index or index < 0 or index >= N_particles \
			or not position.is_finite() or not velocity.is_finite() \
			or not is_finite(mass) or mass <= 0.0:
		return {"ok": false, "error": "invalid_probe"}
	var pos_bytes := PackedFloat32Array([position.x, position.y, position.z, mass]).to_byte_array()
	var vel_bytes := PackedFloat32Array([velocity.x, velocity.y, velocity.z, 0.0]).to_byte_array()
	var zero := PackedByteArray(); zero.resize(16)
	var offset := index * 16
	for buffer in [_pos_buf, _pos_prev_buf, _pos_render_buf]:
		_rd.buffer_update(buffer, offset, 16, pos_bytes)
	_rd.buffer_update(_vel_buf, offset, 16, vel_bytes)
	_rd.buffer_update(_acc_buf, offset, 16, zero)
	_grav_warmup = true
	_step_timer = 0.0
	return {"ok": true, "probe_index": index}


func field_intelligence_clear() -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	if playing:
		return {"ok": false, "error": "pause_required"}
	return _field_intelligence.clear()


func field_intelligence_snapshot() -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	if playing:
		return {"ok": false, "error": "pause_required"}
	return _field_intelligence.snapshot()


func field_intelligence_restore(snapshot_data: Dictionary) -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	if playing:
		return {"ok": false, "error": "pause_required"}
	return _field_intelligence.restore(snapshot_data)


func field_intelligence_status() -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	return _field_intelligence.status()


func field_intelligence_set_runtime_enabled_for_verify(enabled: bool) -> Dictionary:
	if not field_intelligence_enabled or _field_intelligence == null:
		return {"ok": false, "error": "disabled"}
	if playing:
		return {"ok": false, "error": "pause_required"}
	return _field_intelligence.set_runtime_enabled_for_verify(enabled)


func field_state_digest_for_verify() -> Dictionary:
	if playing:
		return {"ok": false, "error": "pause_required"}
	var cells := grid_N * grid_N * grid_N
	var hash := HashingContext.new()
	hash.start(HashingContext.HASH_SHA256)
	for spec in [
		[_field_ey, cells * 4], [_field_ei, cells * 4], [_field_q, cells * 4],
		[_field_vel, cells * 16], [_pos_buf, N_particles * 16],
		[_vel_buf, N_particles * 16],
	]:
		var bytes := _rd.buffer_get_data(spec[0], 0, spec[1])
		if bytes.size() != spec[1]:
			return {"ok": false, "error": "readback_failed"}
		hash.update(bytes)
	return {"ok": true, "checksum": hash.finish().hex_encode()}


func field_intelligence_render_once_for_verify() -> Dictionary:
	if not field_intelligence_enabled or playing:
		return {"ok": false, "error": "disabled_or_playing"}
	if not _ensure_field_intelligence_render_target():
		return {"ok": false, "error": "render_target_unavailable"}
	var cl := _rd.compute_list_begin()
	_record_field_intelligence_view(cl)
	_rd.compute_list_end()
	return {"ok": true}


func field_intelligence_render_receipt_for_verify() -> Dictionary:
	if not field_intelligence_enabled or playing or not _field_render_tex.is_valid():
		return {"ok": false, "error": "disabled_playing_or_no_texture"}
	var bytes := _rd.texture_get_data(_field_render_tex, 0)
	if bytes.size() < 12:
		return {"ok": false, "error": "readback_failed"}
	var low := clampi(roundi(bytes.decode_float(0) * 255.0), 0, 255)
	var mid := clampi(roundi(bytes.decode_float(4) * 255.0), 0, 255)
	var high := clampi(roundi(bytes.decode_float(8) * 255.0), 0, 255)
	return {"ok": true, "tick": low | (mid << 8) | (high << 16)}


func _render_field_slice() -> void:
	if not _field_render_shader.is_valid(): return
	var now_ms := Time.get_ticks_msec()
	if now_ms - _last_field_rb_ms < int(1000.0 / RB_HZ): return  # ~15 Hz cap
	_last_field_rb_ms = now_ms
	if not _field_render_tex.is_valid():
		_make_render_textures()
		_cache_render_texture_sets()  # sets referencing the new texture
	# The shared global-RD texture is renderer-visible through Texture2DRD.
	# Construct the wrapper once per target allocation and keep it on the
	# signal/TextureRect path; no texture_get_data/Image path is needed.
	if field_display_texture == null \
			or not (field_display_texture is Texture2DRD):
		field_display_texture = CassiGpuTextureBridge.wrap(_field_render_tex)

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
	# The renderer consumes the shared RD image asynchronously. Signal the
	# same existing presentation seam after recording the producer dispatch.
	field_texture_updated.emit(field_display_texture)



func _physics_step() -> void:
	# Single-step API (verify script / external callers): wraps the step
	# dispatches in its own list+submit+sync.
	_run_physics_steps(1)


# ═══════════════════════════════════════════════════════════════════════
# Color-as-LUT (Tier-2): bake the active color curve into a 256×1 RGBA8 LUT
# ═══════════════════════════════════════════════════════════════════════
# The instancer's per-instance color math is a pure function of the
# band-relative scalar axis (q / |v| / log-m) given the engine constants —
# so it bakes into a 1D LUT. In LUT mode the MultiMesh drops its color
# channel (use_colors=false), the instancer writes the band position u plus
# the per-instance VFX factors (glow boost, depth fade) into custom_data,
# and the billboard material samples the LUT at INSTANCE_CUSTOM.x, applying
# the factors on top (material-side placement — the LUT bake itself is a
# pure band curve, unchanged). The framing is the exact
# inverse of the shader's band_u() (compute/cassi_instancer.glsl):
#   cycle    u ∈ [0, 1-U_LUT_A):  h = u/(1-U_LUT_A)·span,  l = 0.5
#   approach u ∈ [1-U_LUT_A, 1]:  pA = (u-(1-U_LUT_A))/U_LUT_A,
#                                 h = mix(0.8, a_top, pA), l = 0.5+0.5·pA
const LUT_SIZE := 256
const LUT_APPROACH_ENTRY := 0.751953125  # (192.5)/256 — approach entry lands on texel 192's center (the cycle→approach color discontinuity must never sit inside a linear-filter blend interval)
const LUT_APPROACH_TOP := 0.998046875    # (255.5)/256 — the white point lands exactly on texel 255's center
const LUT_APPROACH_SPAN := LUT_APPROACH_TOP - LUT_APPROACH_ENTRY  # 63 texel-intervals for the white-hot stage




func _lut_active() -> bool:
	# The runtime behavior follows the FORMAT the multimesh was BUILT with
	# (the buffer layout is fixed by use_colors/use_custom_data and cannot
	# flip per-dispatch). color_lut_mode is read at build (reinit()).
	#
	# Intrinsic phase/direction modes are always vertex-color formats.
	if not _lut_compatible():
		return false
	return _mm_lut_mode


func _lut_compatible() -> bool:
	# The LUT contains only a scalar band curve. Base modes 4/5/6 have
	# per-instance axes (density, phase, or direction) that cannot be
	# represented by that static curve. High-nibble VFX flags remain valid:
	# size is transform-side and glow/depth ride custom_data.
	var base := int(particle_color_mode) & 0xF
	return base >= 0 and base <= 3

## NON-DESTRUCTIVE MultiMesh format flip (2026-08-16): when the active color
## base mode becomes LUT-incompatible (field-phase 5 / velocity-direction 6)
## the MultiMesh must be rebuilt from the LUT (custom_data) format to the
## legacy (colors) format so the instancer's per-instance color writes land
## in the color slot — WITHOUT reseeding particles/field (unlike reinit()).
## Rebuilds the MultiMesh + the instancer uniform sets only; particles and
## the field buffers are untouched. No-op when the format is already correct.
## Called by sim_ui._apply_particle_color_mode when the base-mode change
## flips _lut_compatible().
func refresh_lut_format() -> void:
	if _rd == null:
		return
	var want_lut: bool = color_lut_mode and _lut_compatible()
	if _mm_lut_mode == want_lut:
		return
	_free_uniform_sets()    # cached sets reference the old multimesh RID
	_free_multimesh()
	_setup_multimesh()
	_cache_uniform_sets()   # rebind the instancer set to the new RID
	_apply_lut_material()
	if _mm_lut_mode:
		_fill_instancer_pc()
		_bake_color_lut()
		_lut_bake_dirty = false


## Exposed for probes: the baked LUT texture (256×1 RGBA8) — read via
## get_image() for exact texel access.
func color_lut_texture() -> ImageTexture:
	return _color_lut_tex


func _apply_lut_material() -> void:
	# Push the LUT mode + texture onto the billboard material. Runs once per
	# build (the texture RID is stable — re-bakes use update(), so the
	# material's reference stays valid).
	if _mmi == null or not is_instance_valid(_mmi) or _mmi.material_override == null:
		return
	var mat := _mmi.material_override as ShaderMaterial
	if mat == null:
		return
	mat.set_shader_parameter("lut_enabled", 1.0 if _mm_lut_mode else 0.0)
	if _color_lut_tex != null:
		mat.set_shader_parameter("color_lut", _color_lut_tex)
	# Per-instance VFX uniforms: pinned to the instancer's constants
	# (cassi_instancer.glsl GLOW_TINT / GLOW_L_BOOST). The shader defaults
	# are the same values — cross-referenced comments in both files.
	mat.set_shader_parameter("glow_tint", Vector3(0.95, 0.90, 0.98))
	mat.set_shader_parameter("glow_strength", 0.12)


func _apply_particle_presentation_profile() -> void:
	if _mmi == null or not is_instance_valid(_mmi) or _mmi.material_override == null:
		return
	var mat := _mmi.material_override as ShaderMaterial
	if mat == null:
		return
	if _particle_compat_shader == null:
		_particle_compat_shader = load("res://shaders/particle_billboard.gdshader") as Shader
	if _particle_presentation_shader == null:
		_particle_presentation_shader = load("res://shaders/particle_billboard_presentation.gdshader") as Shader
	var target: Shader = _particle_presentation_shader if presentation_profile else _particle_compat_shader
	if target == null:
		push_error("[CassiSim] particle presentation shader could not be loaded")
		return
	mat.shader = target
	if presentation_profile:
		# QuadMesh already carries particle_size; the presentation shader's
		# screen-space correction operates from that single physical scale.
		mat.set_shader_parameter("size", 1.0)
		mat.set_shader_parameter("min_pixel_radius", PRESENTATION_MIN_PIXEL_RADIUS)
		mat.set_shader_parameter("max_pixel_radius", _effective_presentation_max_pixel_radius())
		mat.set_shader_parameter("halo_strength", 0.45)
		mat.set_shader_parameter("emission_strength", 1.75)
		mat.set_shader_parameter("core_radius", 0.30)
		mat.set_shader_parameter("color_scheme", float(_presentation_color_scheme))
		_apply_particle_presentation_opacity()
	else:
		# Restore the legacy shader's historical default if the live toggle is
		# switched off after the presentation material was active.
		mat.set_shader_parameter("size", 1.5)
	_apply_lut_material()


func _effective_presentation_max_pixel_radius(particle_count: int = -1) -> float:
	var count := N_particles if particle_count < 0 else particle_count
	# Keep million-particle layers as individually moving motes instead of
	# letting capped billboards overlap into one opaque, apparently static wall.
	var count_scale := sqrt(PRESENTATION_OPACITY_REFERENCE_PARTICLES / maxf(
			float(count), PRESENTATION_OPACITY_REFERENCE_PARTICLES))
	return maxf(PRESENTATION_MIN_PIXEL_RADIUS, PRESENTATION_MAX_PIXEL_RADIUS * count_scale)


func _effective_presentation_particle_opacity(particle_count: int = -1) -> float:
	var count := N_particles if particle_count < 0 else particle_count
	# Count scaling keeps nearby layers from saturating. The shader may lift
	# sub-pixel motes slightly, but that floor remains count-scaled too.
	var count_scale := sqrt(PRESENTATION_OPACITY_REFERENCE_PARTICLES / maxf(
			float(count), PRESENTATION_OPACITY_REFERENCE_PARTICLES))
	return clampf(_presentation_particle_opacity * count_scale, 0.0001, 1.0)


func _apply_particle_presentation_opacity() -> void:
	if not presentation_profile or _mmi == null or not is_instance_valid(_mmi):
		return
	var mat := _mmi.material_override as ShaderMaterial
	if mat == null or mat.shader != _particle_presentation_shader:
		return
	var stack_opacity := _effective_presentation_particle_opacity()
	mat.set_shader_parameter("stack_opacity", stack_opacity)
	mat.set_shader_parameter("distant_opacity", minf(stack_opacity * 2.0, 0.04))


func _presentation_layers_ready() -> bool:
	# Decoupled setup mutates its live RD buffers on a worker. Do not create
	# renderer-owned presentation targets until that worker has published its
	# finished setup; doing it earlier can contend with the first topology
	# query on the global device.
	return not _decoupled_boot_wait and (_physics_engine == null or _physics_engine.setup_ready())


func _presentation_macro_lod_wanted() -> bool:
	return _presentation_layers_ready() and _physics_engine != null \
			and presentation_profile and presentation_macro_lod_enabled \
			and _macro_lod_pipe.is_valid() and _macro_lod_shader.is_valid()


func _sync_presentation_macro_lod() -> void:
	if not _presentation_macro_lod_wanted():
		_free_macro_lod_multimesh()
		return
	if _macro_lod_mmi == null or not is_instance_valid(_macro_lod_mmi):
		_setup_macro_lod_multimesh()
	if _macro_lod_mmi == null or _macro_lod_material == null:
		return
	_macro_lod_mmi.visible = true
	var scheme := _presentation_color_scheme
	if _macro_lod_last_scheme != scheme:
		_macro_lod_material.set_shader_parameter("color_scheme", float(scheme))
		_macro_lod_last_scheme = scheme
	var lod_range := Vector2(
		minf(presentation_lod_enter, presentation_lod_exit),
		maxf(presentation_lod_enter, presentation_lod_exit))
	if lod_range != _macro_lod_last_range:
		_macro_lod_material.set_shader_parameter("lod_enter", lod_range.x)
		_macro_lod_material.set_shader_parameter("lod_exit", lod_range.y)
		_macro_lod_last_range = lod_range
	_sync_macro_lod_uniform_set()


func _setup_macro_lod_multimesh() -> void:
	if _macro_lod_mmi != null and is_instance_valid(_macro_lod_mmi):
		return
	var site_cap := maxi(2 * ML_N1 * ML_N1 * ML_N1, 1)
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	quad.orientation = PlaneMesh.FACE_Z
	_macro_lod_mm = MultiMesh.new()
	_macro_lod_mm.transform_format = MultiMesh.TRANSFORM_3D
	_macro_lod_mm.use_colors = false
	_macro_lod_mm.use_custom_data = true
	_macro_lod_mm.mesh = quad
	_macro_lod_mm.instance_count = site_cap
	# Force allocation of the renderer-owned storage before the compute writer
	# obtains its RID. The finite zero records also make a not-yet-published
	# topology explicitly invisible.
	var zero_records := PackedFloat32Array()
	zero_records.resize(site_cap * 16)
	_macro_lod_mm.buffer = zero_records
	_macro_lod_mmi = MultiMeshInstance3D.new()
	_macro_lod_mmi.name = "PresentationMacroLod"
	_macro_lod_mmi.multimesh = _macro_lod_mm
	add_child(_macro_lod_mmi)
	_macro_lod_rd_rid = RenderingServer.multimesh_get_buffer_rd_rid(_macro_lod_mm.get_rid())
	if not _macro_lod_rd_rid.is_valid():
		push_error("[CassiSim] presentation macro LOD could not acquire its MultiMesh RD buffer")
		_free_macro_lod_multimesh()
		return
	_macro_lod_material = ShaderMaterial.new()
	_macro_lod_material.shader = load("res://shaders/presentation_macro_billboard.gdshader") as Shader
	if _macro_lod_material.shader == null:
		push_error("[CassiSim] presentation macro LOD material shader could not be loaded")
		_free_macro_lod_multimesh()
		return
	_macro_lod_material.render_priority = 0
	_macro_lod_material.set_shader_parameter("base_size", 1.0)
	_macro_lod_mmi.material_override = _macro_lod_material
	_macro_lod_last_scheme = -1
	_update_particle_cull_bounds()


func _free_macro_lod_multimesh() -> void:
	if _rd != null and _us_macro_lod_0.is_valid() \
			and _rd.uniform_set_is_valid(_us_macro_lod_0):
		_rd.free_rid(_us_macro_lod_0)
	_us_macro_lod_0 = RID()
	_macro_lod_last_range = Vector2(INF, INF)
	if _macro_lod_mmi != null and is_instance_valid(_macro_lod_mmi):
		remove_child(_macro_lod_mmi)
		_macro_lod_mmi.free()
	_macro_lod_mmi = null
	_macro_lod_mm = null
	_macro_lod_rd_rid = RID()
	_macro_lod_material = null
	_macro_lod_last_scheme = -1


func _sync_macro_lod_uniform_set() -> bool:
	if _rd == null or not _macro_lod_rd_rid.is_valid() or _physics_engine == null:
		return false
	if _us_macro_lod_0.is_valid() and _rd.uniform_set_is_valid(_us_macro_lod_0):
		return true
	if not _physics_engine.has_method("topology_resources"):
		return false
	var topo: Dictionary = _physics_engine.topology_resources()
	var optical: RID = topo.get("topology_optical_rid", RID())
	var status: RID = topo.get("topology_status_rid", RID())
	if not optical.is_valid() or not status.is_valid():
		return false
	_us_macro_lod_0 = _rd.uniform_set_create([
		_uniform_storage(0, optical),
		_uniform_storage(1, status),
		_uniform_storage(2, _macro_lod_rd_rid),
	], _macro_lod_shader, 0)
	if not _us_macro_lod_0.is_valid():
		push_warning("[CassiSim] presentation macro LOD uniform set creation failed")
		return false
	return true


func _presentation_trails_wanted() -> bool:
	return _presentation_layers_ready() and presentation_profile and presentation_trails_enabled \
			and _trail_pipe.is_valid() and _trail_shader.is_valid()


func _sync_presentation_trails() -> void:
	if not _presentation_trails_wanted():
		_free_trail_multimesh()
		return
	if _trail_mmi == null or not is_instance_valid(_trail_mmi):
		_setup_trail_multimesh()
	if _trail_mmi == null or _trail_material == null:
		return
	_trail_mmi.visible = true
	var scheme := _presentation_color_scheme
	if _trail_last_scheme != scheme:
		_trail_material.set_shader_parameter("color_scheme", float(scheme))
		_trail_last_scheme = scheme
	if _decoupled_active:
		_sync_trail_dc_uniform_set()
	else:
		_sync_trail_inline_uniform_set()


func _setup_trail_multimesh() -> void:
	if _trail_mmi != null and is_instance_valid(_trail_mmi):
		return
	var quad := QuadMesh.new()
	quad.size = Vector2.ONE
	quad.orientation = PlaneMesh.FACE_Z
	_trail_mm = MultiMesh.new()
	_trail_mm.transform_format = MultiMesh.TRANSFORM_3D
	_trail_mm.use_colors = false
	_trail_mm.use_custom_data = true
	_trail_mm.mesh = quad
	_trail_mm.instance_count = PRESENTATION_TRAIL_CAP
	var zero_records := PackedFloat32Array()
	zero_records.resize(PRESENTATION_TRAIL_CAP * 16)
	_trail_mm.buffer = zero_records
	_trail_mmi = MultiMeshInstance3D.new()
	_trail_mmi.name = "PresentationVelocityRibbons"
	_trail_mmi.multimesh = _trail_mm
	add_child(_trail_mmi)
	_trail_rd_rid = RenderingServer.multimesh_get_buffer_rd_rid(_trail_mm.get_rid())
	if not _trail_rd_rid.is_valid():
		push_error("[CassiSim] presentation trails could not acquire their MultiMesh RD buffer")
		_free_trail_multimesh()
		return
	_trail_material = ShaderMaterial.new()
	_trail_material.shader = load("res://shaders/presentation_trail.gdshader") as Shader
	if _trail_material.shader == null:
		push_error("[CassiSim] presentation trail material shader could not be loaded")
		_free_trail_multimesh()
		return
	_trail_material.render_priority = 0
	_trail_material.set_shader_parameter("emission_strength", 0.85)
	_trail_material.set_shader_parameter("alpha_scale", 0.55)
	_trail_material.set_shader_parameter("width_softness", 0.5)
	_trail_material.set_shader_parameter("taper_power", 1.5)
	_trail_material.set_shader_parameter("depth_fade_near", 200.0)
	_trail_material.set_shader_parameter("depth_fade_far", 2000.0)
	_trail_mmi.material_override = _trail_material
	_trail_last_scheme = -1
	_update_particle_cull_bounds()


func _free_trail_multimesh() -> void:
	if _rd != null:
		for rid in [_us_trail_0, _us_trail_0_dc]:
			if rid.is_valid() and _rd.uniform_set_is_valid(rid):
				_rd.free_rid(rid)
	_us_trail_0 = RID()
	_us_trail_0_dc = RID()
	if _trail_mmi != null and is_instance_valid(_trail_mmi):
		remove_child(_trail_mmi)
		_trail_mmi.free()
	_trail_mmi = null
	_trail_mm = null
	_trail_rd_rid = RID()
	_trail_material = null
	_trail_last_scheme = -1


func _sync_trail_inline_uniform_set() -> bool:
	if _rd == null or not _trail_rd_rid.is_valid() or _decoupled_active:
		return false
	if _us_trail_0.is_valid() and _rd.uniform_set_is_valid(_us_trail_0):
		return true
	if not _pos_render_buf.is_valid() or not _vel_buf.is_valid():
		return false
	_us_trail_0 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_render_buf),
		_uniform_storage(1, _vel_buf),
		_uniform_storage(2, _trail_rd_rid),
	], _trail_shader, 0)
	return _us_trail_0.is_valid()


func _sync_trail_dc_uniform_set() -> bool:
	if _rd == null or not _trail_rd_rid.is_valid() or _physics_engine == null:
		return false
	if _us_trail_0_dc.is_valid() and _rd.uniform_set_is_valid(_us_trail_0_dc):
		return true
	var engine_vel: RID = _physics_engine.get("_vel_buf")
	if not _pos_render_buf.is_valid() or not engine_vel.is_valid():
		return false
	_us_trail_0_dc = _rd.uniform_set_create([
		_uniform_storage(0, _pos_render_buf),
		_uniform_storage(1, engine_vel),
		_uniform_storage(2, _trail_rd_rid),
	], _trail_shader, 0)
	return _us_trail_0_dc.is_valid()

func _record_presentation_trails(cl, uniform_set: RID) -> void:
	if not _presentation_trails_wanted() or not uniform_set.is_valid() \
			or not _rd.uniform_set_is_valid(uniform_set) \
			or _trail_mm == null or _trail_mm.instance_count <= 0:
		return
	var cam := _sim_cam
	if cam == null:
		return
	var forward := -cam.global_transform.basis.z.normalized()
	var right := cam.global_transform.basis.x.normalized()
	var min_length := maxf(cluster_radius * 0.02, 0.5)
	var max_length := maxf(cluster_radius * 0.12, 6.0)
	var width := maxf(cluster_radius * 0.004, 0.10)
	_trail_pc.encode_float(0, float(N_particles))
	_trail_pc.encode_float(4, float(_trail_mm.instance_count))
	_trail_pc.encode_float(8, maxf(presentation_trail_speed_threshold, 0.0))
	_trail_pc.encode_float(12, maxf(presentation_trail_shutter_seconds, 0.0))
	_trail_pc.encode_float(16, min_length)
	_trail_pc.encode_float(20, max_length)
	_trail_pc.encode_float(24, width)
	_trail_pc.encode_float(28,
		maxf(_rainbow_vmax, presentation_trail_speed_threshold * 1.05))
	_trail_pc.encode_float(32, forward.x)
	_trail_pc.encode_float(36, forward.y)
	_trail_pc.encode_float(40, forward.z)
	_trail_pc.encode_float(44, 1337.0)
	_trail_pc.encode_float(48, right.x)
	_trail_pc.encode_float(52, right.y)
	_trail_pc.encode_float(56, right.z)
	_trail_pc.encode_float(60, 1.0)
	_rd.compute_list_bind_compute_pipeline(cl, _trail_pipe)
	_rd.compute_list_bind_uniform_set(cl, uniform_set, 0)
	_rd.compute_list_set_push_constant(cl, _trail_pc, _trail_pc.size())
	_rd.compute_list_dispatch(cl, ceili(float(_trail_mm.instance_count) / 256.0), 1, 1)
	_rd.compute_list_add_barrier(cl)

func _rotation_orientation_requested() -> bool:
	return rotation_stress_enabled and rotation_orientation_render_enabled


func _ensure_rotation_orientation_pipeline() -> bool:
	if not _rotation_orientation_requested() or _rd == null:
		return false
	if not _rotation_axis_shader.is_valid():
		_rotation_axis_shader = _shader_from_file(
			"res://compute/cassi_rotation_orientation_instancer.glsl")
	if _rotation_axis_shader.is_valid() and not _rotation_axis_pipe.is_valid():
		_rotation_axis_pipe = _rd.compute_pipeline_create(_rotation_axis_shader)
		if _rotation_axis_pipe.is_valid():
			print("[CassiSim] rotation orientation-axis pipeline ready")
	return _rotation_axis_shader.is_valid() and _rotation_axis_pipe.is_valid()


func _rotation_orientation_wanted() -> bool:
	return _presentation_layers_ready() and _decoupled_active \
			and _physics_engine != null and _ensure_rotation_orientation_pipeline()


func _sync_rotation_orientation_layer() -> void:
	if not _rotation_orientation_requested() or not _rotation_orientation_wanted():
		_free_rotation_orientation_multimesh()
		return
	if _rotation_axis_mmi == null or not is_instance_valid(_rotation_axis_mmi):
		_setup_rotation_orientation_multimesh()
	if _rotation_axis_mmi == null:
		return
	_rotation_axis_mmi.visible = true
	_sync_rotation_orientation_uniform_set()


func _setup_rotation_orientation_multimesh() -> void:
	if _rotation_axis_mmi != null and is_instance_valid(_rotation_axis_mmi):
		return
	var box := BoxMesh.new()
	box.size = Vector3.ONE
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(0.14, 0.86, 1.0, 1.0)
	material.emission_enabled = true
	material.emission = Color(0.08, 0.66, 1.0)
	material.emission_energy_multiplier = 1.6
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.vertex_color_use_as_albedo = true
	box.material = material
	_rotation_axis_mm = MultiMesh.new()
	_rotation_axis_mm.transform_format = MultiMesh.TRANSFORM_3D
	_rotation_axis_mm.use_colors = true
	_rotation_axis_mm.use_custom_data = false
	_rotation_axis_mm.mesh = box
	_rotation_axis_mm.instance_count = maxi(N_particles, 1)
	var zero_records := PackedFloat32Array()
	zero_records.resize(_rotation_axis_mm.instance_count * 16)
	_rotation_axis_mm.buffer = zero_records
	_rotation_axis_mmi = MultiMeshInstance3D.new()
	_rotation_axis_mmi.name = "RotationOrientationAxes"
	_rotation_axis_mmi.multimesh = _rotation_axis_mm
	add_child(_rotation_axis_mmi)
	_rotation_axis_rd_rid = RenderingServer.multimesh_get_buffer_rd_rid(
		_rotation_axis_mm.get_rid())
	if not _rotation_axis_rd_rid.is_valid():
		push_error("[CassiSim] rotation orientation layer could not acquire its MultiMesh RD buffer")
		_free_rotation_orientation_multimesh()
		return
	_update_particle_cull_bounds()


func _free_rotation_orientation_multimesh() -> void:
	if _rd != null and _us_rotation_axis_0.is_valid() \
			and _rd.uniform_set_is_valid(_us_rotation_axis_0):
		_rd.free_rid(_us_rotation_axis_0)
	_us_rotation_axis_0 = RID()
	if _rotation_axis_mmi != null and is_instance_valid(_rotation_axis_mmi):
		remove_child(_rotation_axis_mmi)
		_rotation_axis_mmi.free()
	_rotation_axis_mmi = null
	_rotation_axis_mm = null
	_rotation_axis_rd_rid = RID()


func _sync_rotation_orientation_uniform_set() -> bool:
	if _rd == null or not _rotation_axis_rd_rid.is_valid() \
			or _physics_engine == null:
		return false
	if _us_rotation_axis_0.is_valid() and _rd.uniform_set_is_valid(_us_rotation_axis_0):
		return true
	var resources: Dictionary = _physics_engine.rotation_render_resources()
	var orientation: RID = resources.get("orientation_buffer", RID())
	if not bool(resources.get("enabled", false)) \
			or not _pos_render_buf.is_valid() or not orientation.is_valid():
		return false
	_us_rotation_axis_0 = _rd.uniform_set_create([
		_uniform_storage(0, _pos_render_buf),
		_uniform_storage(1, orientation),
		_uniform_storage(2, _rotation_axis_rd_rid),
	], _rotation_axis_shader, 0)
	return _us_rotation_axis_0.is_valid()


func _record_rotation_orientation(cl) -> void:
	if not _rotation_orientation_wanted() \
			or not _us_rotation_axis_0.is_valid() \
			or not _rd.uniform_set_is_valid(_us_rotation_axis_0) \
			or _rotation_axis_mm == null:
		return
	_rotation_axis_pc.encode_float(0, float(N_particles))
	_rotation_axis_pc.encode_float(4, maxf(particle_size * 2.5, 0.25))
	_rotation_axis_pc.encode_float(8, maxf(particle_size * 0.12, 0.03))
	_rotation_axis_pc.encode_float(12, 0.0)
	_rd.compute_list_bind_compute_pipeline(cl, _rotation_axis_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_rotation_axis_0, 0)
	_rd.compute_list_set_push_constant(
		cl, _rotation_axis_pc, _rotation_axis_pc.size())
	_rd.compute_list_dispatch(cl, ceili(float(maxi(N_particles, 1)) / 256.0), 1, 1)
	_rd.compute_list_add_barrier(cl)

func _update_particle_presentation_viewport() -> void:
	if not presentation_profile or _mmi == null or not is_instance_valid(_mmi):
		return
	var mat := _mmi.material_override as ShaderMaterial
	if mat == null:
		return
	var viewport := get_viewport()
	if viewport == null:
		return
	var height := viewport.get_visible_rect().size.y
	if height <= 0.0 or is_equal_approx(height, _presentation_viewport_height):
		return
	mat.set_shader_parameter("viewport_height", height)
	_presentation_viewport_height = height

func _bake_color_lut() -> void:
	# Bake the CURRENT color curve into the LUT (256 RGBA8 texels, u ∈ [0,1]
	# per the framing header — the exact inverse of the shader's band_u()).
	# Mode 0 bakes the Salpeter mass-temperature ramp keyed on the same
	# normalized log-mass the shader uses. Call outside any compute list.
	if _color_lut_tex == null:
		return
	var e := _engine_c
	var img := Image.create_empty(LUT_SIZE, 1, false, Image.FORMAT_RGBA8)
	if int(particle_color_mode & 0xF) == 0:
		# Salpeter mass-temperature ramp (the shader's legacy mode-0 formula)
		for i in range(LUT_SIZE):
			var u := (float(i) + 0.5) / float(LUT_SIZE)
			var log_m := u
			var cr := lerpf(0.15, 1.0, log_m * log_m)
			var cg := lerpf(0.25, 0.6, log_m)
			var cb := lerpf(1.0, 0.15, log_m)
			img.set_pixel(i, 0, Color(cr, cg, cb, 1.0))
	else:
		var span: float = e[E_SPAN] if e.size() >= 17 else 1.0
		var a_top: float = e[E_TOP] if e.size() >= 17 else 0.93
		for i in range(LUT_SIZE):
			var u := (float(i) + 0.5) / float(LUT_SIZE)
			var h: float
			var l: float
			if u < LUT_APPROACH_ENTRY:
				h = (u / LUT_APPROACH_ENTRY) * span
				l = 0.5
			else:
				var p_a := (u - LUT_APPROACH_ENTRY) / LUT_APPROACH_SPAN
				h = lerpf(0.8, a_top, p_a)
				l = 0.5 + 0.5 * p_a
			img.set_pixel(i, 0, _lut_hsl_to_rgb(h, l))
	_color_lut_tex.update(img)
	# snapshot the bake signature (17 engine floats + base mode)
	if _lut_sig.size() != 18:
		_lut_sig.resize(18)
	for k in range(17):
		_lut_sig[k] = e[k]
	_lut_sig[17] = float(int(particle_color_mode & 0xF))


static func _lut_hsl_to_rgb(h: float, l: float) -> Color:
	# IQ-form HSL→RGB with s = 1 — the exact shader formula (hsl2rgb in
	# cassi_instancer.glsl with c.y = 1.0).
	var r: float = clampf(absf(fposmod(h * 6.0 + 0.0, 6.0) - 3.0) - 1.0, 0.0, 1.0)
	var g: float = clampf(absf(fposmod(h * 6.0 + 4.0, 6.0) - 3.0) - 1.0, 0.0, 1.0)
	var b: float = clampf(absf(fposmod(h * 6.0 + 2.0, 6.0) - 3.0) - 1.0, 0.0, 1.0)
	var f: float = 1.0 - absf(2.0 * l - 1.0)
	return Color(l + (r - 0.5) * f, l + (g - 0.5) * f, l + (b - 0.5) * f, 1.0)


func _update_lut_bake_sig() -> void:
	# Dirty-track the bake from _fill_instancer_pc (runs inside the compute
	# list — only sets the flag; the actual texture update happens in
	# _process, outside any list). Covers EVERY band/mode change: qi_cycle/
	# pinch/approach, hue_offset, shares, progress, rainbow_count, threshold
	# tracking, auto-align publishes, and manual legend drags all flow
	# through the engine constants.
	if _lut_sig.size() != 18:
		_lut_bake_dirty = true
		return
	for k in range(17):
		if _engine_c[k] != _lut_sig[k]:
			_lut_bake_dirty = true
			return
	if int(_lut_sig[17]) != int(particle_color_mode & 0xF):
		_lut_bake_dirty = true


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
	var packed_mode := int(particle_color_mode)
	var base_mode := packed_mode & 0xF
	if base_mode > 6:
		push_warning("[CassiSim] particle_color_mode base %d is invalid; using base 0 while preserving flags" % base_mode)
		base_mode = 0
		packed_mode &= 0xF0
		particle_color_mode = packed_mode
	_instancer_pc_bytes.encode_float(44, float(packed_mode))
	_instancer_pc_bytes.encode_float(112, ext_pc.x)
	_instancer_pc_bytes.encode_float(116, ext_pc.y)
	_instancer_pc_bytes.encode_float(120, ext_pc.z)
	if base_mode == 0:
		for slot in range(48, 112, 4):
			_instancer_pc_bytes.encode_float(slot, 0.0)
		_instancer_pc_bytes.encode_float(124, 0.0)
		_engine_c.fill(0.0)
		_update_lut_bake_sig()
		return
	if base_mode >= 5:
		for slot in range(48, 112, 4):
			_instancer_pc_bytes.encode_float(slot, 0.0)
		_instancer_pc_bytes.encode_float(112, ext_pc.x)
		_instancer_pc_bytes.encode_float(116, ext_pc.y)
		_instancer_pc_bytes.encode_float(120, ext_pc.z)
		_instancer_pc_bytes.encode_float(124, color_hue_offset)
		if base_mode == 6:
			_instancer_pc_bytes.encode_float(52, maxf(_rainbow_vref, 1e-6))
		_engine_c.fill(0.0)
		_update_lut_bake_sig()
		return
	var is_qi: bool = base_mode >= 2
	var count: int = rainbow_count
	if count > 8:
		if not _warned_rainbow_count:
			_warned_rainbow_count = true
			push_warning("[CassiSim] rainbow_count=%d > 8 — clamped to 8" % count)
		count = 8
	if count <= 0:
		count = 2 if base_mode == 3 else 1
	var h_cycle: float = 1.0 if is_qi else 0.95
	var prog: float = float(color_progress)
	var ref: float = 0.0
	var lo1: float = 0.0
	var hi_c: float = 0.0
	var pinch := Vector2.ZERO
	var a_lo: float = 0.0
	var a_hi: float = 0.0
	var approach_on: float = 0.0
	if is_qi:
		hi_c = qi_cycle.y
		pinch = qi_pinch
		if lo1 >= hi_c:
			if not _warned_qi_cycle:
				_warned_qi_cycle = true
				push_warning("[CassiSim] qi_cycle (%s, %s) inverted/empty — using the calibrated band (%s, %s)"
						% [_sci(lo1), _sci(hi_c), _sci(Q_FLOOR), _sci(Q_1)])
			lo1 = Q_FLOOR
			hi_c = Q_1
		a_lo = qi_approach.x
		a_hi = qi_approach.y
		if qi_approach_tracks_threshold:
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
	_update_lut_bake_sig()


func _repaint_instancer() -> void:
	# One-shot GPU repaint of the multimesh instance buffer from the CURRENT
	# pos/vel buffers — used when paused (playing=false), where
	# _step_dispatches never runs, so a live color-mode flip repaints the
	# visible instances immediately. It uses a standalone compute list on the
	# global RD with no submit/sync.
	if _rd == null or not _instancer_shader.is_valid() or not _us_inst_0.is_valid() or N_particles <= 0:
		return
	if not _mm_rd_rid.is_valid(): return
	_fill_instancer_pc()
	var pg = ceili(float(N_particles) / 256.0)
	var cl = _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _instancer_pipe)
	# Decoupled (one-RD): the repaint binds the DC render sets — the
	# ENGINE's live buffers directly (vel/fields/pos); there are no fp32
	# _pos_buf mirrors or packed half-pair mirrors. The blend (the −c seam)
	# wrote pos_render from the engine's live pos. Inline: _pos_buf is
	# current and its own physics-buffer sets are bound.
	if _decoupled_active:
		var selected: RID = RID()
		if _ml_boxless_on():
			selected = _us_inst_0_lut_boxless_render_dc if _lut_active() else _us_inst_0_boxless_render_dc
		elif _lut_active():
			selected = _us_inst_0_lut_render_dc
		else:
			selected = _us_inst_0_render_dc
		if not selected.is_valid():
			_rd.compute_list_end()
			return
		_rd.compute_list_bind_uniform_set(cl, selected, 0)
	elif _ml_boxless_on():
		var selected_inline: RID = _us_inst_0_lut_boxless if _lut_active() else _us_inst_0_boxless
		if not selected_inline.is_valid():
			_rd.compute_list_end()
			return
		_rd.compute_list_bind_uniform_set(cl, selected_inline, 0)
	elif _lut_active():
		if not _us_inst_0_lut.is_valid(): _rd.compute_list_end(); return
		_rd.compute_list_bind_uniform_set(cl, _us_inst_0_lut, 0)
	else:
		if not _us_inst_0.is_valid(): _rd.compute_list_end(); return
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

	# Two-fluid PC (dedicated 64 B): the shared 11 fields + the 3 per-axis
	# extents (the anisotropic 19-point stencil needs h_i = 2·extent_i/N —
	# the dedicated-PC precedent: the shared _pc_bytes stays at 11 floats
	# for field_render/instancer) + pass_sel (float 14)
	# + omega2 (float 15).
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
	# Movable home-window: off = −c (the shader maps [c−ext, c+ext] →
	# [0, N] via gc = (p + off)·scale + hn — the +hn provides the −ext
	# shift, so off is a pure frame translation; at c = 0 it is exactly
	# the legacy 0.0, bit-identical).
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
		var ext_r := _extents()
		var hxr: float = 2.0 * ext_r.x / float(grid_N)
		var hyr: float = 2.0 * ext_r.y / float(grid_N)
		var hzr: float = 2.0 * ext_r.z / float(grid_N)
		_rd.compute_list_bind_compute_pipeline(cl, _cell_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_cell_0, 0)
		# grad zero → lap (the lap pass also accumulates the least-squares M+b)
		_ml_cell_pc(10.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, int(ceil(float(ml_ns) / 64.0)), 1, 1)
		_barrier(cl)  # grad zero → lap
		_ml_cell_pc(0.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, wg1, 1, 1)
		_barrier(cl)  # lap → leapfrog
		_ml_cell_pc(1.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, int(ceil(float(ml_ns) / 64.0)), 1, 1)
		_barrier(cl)  # leapfrog → gradient solve
		# least-squares solve g = M⁻¹·b per site (into grad)
		_ml_cell_pc(12.0)
		_rd.compute_list_set_push_constant(cl, _cell_pc_bytes, _cell_pc_bytes.size())
		_rd.compute_list_dispatch(cl, int(ceil(float(ml_ns) / 64.0)), 1, 1)
		_barrier(cl)  # solve → raster
		_rd.compute_list_bind_compute_pipeline(cl, _raster_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_raster_0, 0)
		# Pre-sized in-place encode (review_sim.md #5): _raster_pc_bytes is
		# sized 8*4 B at init; zero per-step allocations, byte-identical to
		# the old PackedFloat32Array([...]).to_byte_array().
		_raster_pc_bytes.encode_float(0, float(grid_N))
		_raster_pc_bytes.encode_float(4, float(ml_ns))
		_raster_pc_bytes.encode_float(8, hxr)
		_raster_pc_bytes.encode_float(12, hyr)
		_raster_pc_bytes.encode_float(16, hzr)
		_raster_pc_bytes.encode_float(20, 0.0)
		_raster_pc_bytes.encode_float(24, 0.0)
		_raster_pc_bytes.encode_float(28, 0.0)
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

	# ── 2.65. BH accretion (every step, when enabled): particles within a BH's
	# accretion radius are swallowed (pos.w = 0, mass Δ added atomically to the
	# BH record). Pure GPU, one dispatch, one thread per particle; the barrier
	# after gives the nbody pass visibility. NOTE: this step's deposit already
	# ran (line ~3490), so a swallowed particle still fed THIS step's ρ; the
	# death takes effect from the NEXT step's deposit — same semantics as merge.
	if _bh_acc_shader.is_valid() and bh_accretion and black_holes_enabled:
		_rd.compute_list_bind_compute_pipeline(cl, _bh_acc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_bh_acc_0, 0)
		_rd.compute_list_set_push_constant(cl, _bh_acc_pc_bytes, _bh_acc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg, 1, 1)
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

	# ── 3.1. Tree MOMENTUM CONSERVATION (tree mode only) ─────────────
	# The tree arm's per-particle (π/ρ) prefactor breaks action–reaction
	# (Σm·a ≠ 0); the cloud gains a net self-impulse and drifts off the
	# window (the "all vanish" measured at the owner's scale — cassi_tree_momcon.glsl).
	# Clear → reduce (Σm·a) → barrier → subtract the mass-weighted mean, all
	# in-list (the global-RD can't host-submit mid-list). Newton-3rd-law
	# correction, applied to the final _acc_buf of THIS step.
	if _ml_need_tree() and _tree_mc_pipe.is_valid() and N_particles > 0 and _us_tree_mc.is_valid():
		# Momcon shader is local_size 64 — dispatches use a 64-based group
		# count, NOT pg (which is N/256 for the nbody shader) — else 4× undercover.
		var pg64 := ceili(float(N_particles) / 64.0)
		# clear the 16-B accumulator
		_tree_mc_pc_bytes.encode_float(0, float(N_particles))
		_tree_mc_pc_bytes.encode_float(4, 2.0)   # op = clear
		_rd.compute_list_bind_compute_pipeline(cl, _tree_mc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree_mc, 0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, 1, 1, 1)
		_barrier(cl)
		# reduce Σ(m·a)
		_tree_mc_pc_bytes.encode_float(4, 0.0)   # op = reduce
		_rd.compute_list_bind_compute_pipeline(cl, _tree_mc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree_mc, 0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg64, 1, 1)
		_barrier(cl)
		# subtract the mass-weighted mean (Σm·a → 0)
		_tree_mc_pc_bytes.encode_float(4, 1.0)   # op = subtract
		_rd.compute_list_bind_compute_pipeline(cl, _tree_mc_pipe)
		_rd.compute_list_bind_uniform_set(cl, _us_tree_mc, 0)
		_rd.compute_list_set_push_constant(cl, _tree_mc_pc_bytes, _tree_mc_pc_bytes.size())
		_rd.compute_list_dispatch(cl, pg64, 1, 1)
		_barrier(cl)
	if field_intelligence_enabled and _field_intelligence != null:
		_barrier(cl)  # particle writes -> reward measurement
		_field_intelligence.record_step(cl, _extents(), _field_intelligence_params)


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
	var eps2: float = ML_TREE_EPS2_FRAC * ML_TREE_EPS2_FRAC * _extent_min() * _extent_min()
	bp.encode_float(5, eps2)
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
	wp.encode_float(2, eps2)
	wp.encode_float(3, 1.0)  # use_tp — read particle positions (_pos_buf)
	wp.encode_float(4, float(ML_TREE_NODE_MAX_MULT * N_src + 64))  # bound (unused by walk)
	# Arm 2 (coherence-adaptive θ): q_cent, alpha, toggle (default-off → shader dead)
	wp.encode_float(5, _q_mean)
	wp.encode_float(6, coherence_theta_alpha)
	wp.encode_float(7, 1.0 if coherence_theta else 0.0)

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


# ── TREE-GRAVITY THREADED ARM ───────────────────────────────────────────
# The in-sim tree arm runs on a dedicated worker thread
# (cassi_tree_worker.gd) with its own local RenderingDevice — the first
# slice of the physics decoupling. The main thread stages the frame's
# meshless source state (global-RD readbacks — main-thread-only) and
# submits a job; the worker build+walks the tree and publishes the
# freshest completed gradient, which the sim re-uploads to the global
# `_ml_tree_grad` for the mode-5 nbody arm. The bootstrap frame blocks
# (step 1 needs a fresh gradient); afterwards the main thread never waits
# for the tree GPU work. The global tree shaders/pipes/sets remain
# allocated (PROVEN correct on a local RD); they are simply not dispatched
# on the global RD.


## Stop the tree worker (reinit / shader retry / exit). Safe with no worker.
## The worker is recreated lazily by _tree_worker_frame().
## Also resets the cadence phase (_tl_frame): the counter is the worker's
## lifecycle state — a fresh worker must start its refresh at phase 1, or
## the first up-to-200 frames after a reinit skip the tree build and the
## nbody runs on a zero/stale gradient (the gate-c tree canary's 10.5
## divergence — the OFF/ON canaries' workers started at different phases).
func _tree_worker_stop() -> void:
	_tl_frame = 0
	if _tree_worker != null:
		_tree_worker.stop()
		_tree_worker = null


## One tree-arm frame: respect the cadence, lazily start the worker, stage
## the meshless source state, submit (non-blocking after the bootstrap),
## and upload the freshest completed gradient to the global _ml_tree_grad.
func _tree_worker_frame() -> void:
	if not _ml_ready or _ml_tree_nsrc <= 0:
		return
	_tl_frame += 1
	if _tree_local_cadence > 1 and _tl_frame % _tree_local_cadence != 1:
		return  # skip this frame (stale-but-recent gradient is fine for 1/K)
	var S := _ml_tree_nsrc
	var N3 := grid_N * grid_N * grid_N
	var Np: int = N_particles
	if _tree_worker == null or not _tree_worker.is_ready():
		_tree_worker_stop()
		var w: RefCounted = load("res://scripts/cassi_tree_worker.gd").new()
		if w.start(S, N3, Np):
			_tree_worker = w
		if _tree_worker == null:
			push_error("[CassiSim] tree worker failed to start")
			return
	var ext := _extents()
	# Host round trip #1: pull the sim's CURRENT meshless source state from
	# the global RD (main-thread-only reads; the same reads the old sync
	# path performed). The worker consumes these copies — no shared buffers.
	var sites := _rd.buffer_get_data(_ml_sites, 0, S * 16).to_float32_array()
	# ADAPTIVE TREE ROOT (perf-decomp 2026-08-15, overhaul migration): seed
	# the root cube from the tracked structure's bounding box (the staged
	# sites — the structure's own scale) instead of the fixed box origin.
	# The walk's resolution then follows the structure; the box-anchored
	# root is gone. bmin = structure min corner, half = 0.5·max(hi−lo)
	# inflated; the default (no bmin in the job) stays the legacy box cube.
	var bmin := Vector3.INF
	var bmax := -Vector3.INF
	for si in range(S):
		bmin.x = minf(bmin.x, sites[si * 4]); bmin.y = minf(bmin.y, sites[si * 4 + 1]); bmin.z = minf(bmin.z, sites[si * 4 + 2])
		bmax.x = maxf(bmax.x, sites[si * 4]); bmax.y = maxf(bmax.y, sites[si * 4 + 1]); bmax.z = maxf(bmax.z, sites[si * 4 + 2])
	var half: float = maxf(ext.x, maxf(ext.y, ext.z)) * 1.000001   # box-cube fallback
	# Gated on the tracked window's ACTUAL RE-FIT state, not the enable
	# flags: OFF (default) stays bit-identical (the legacy box root), AND a
	# flag ON with the tracker no-oping (a filling structure — the envelope
	# == the original box, re_fits == 0, the center unmoved) ALSO keeps the
	# box root, so the tree force is bit-identical to the closed box in the
	# compatibility regime (gate-c: the flag-only gate changed the root
	# half — the structure-rooted cube ≈ 0.97× the box — → pos max-diff
	# 121.9 over 600 steps). The structure-rooted cube engages ONLY after
	# the tracked geometry actually re-fits (the envelope re-fit or a moved
	# window origin).
	var window_refit: bool = _window_center != Vector3.ZERO \
			or (_env_tracker != null and _env_tracker.re_fits > 0)
	if not window_refit:
		bmin = -Vector3.ONE * half
		bmax = Vector3.ONE * half
	elif bmin.x <= -1.0e30 or bmin.x == INF or not (bmin.x == bmin.x):
		bmin = -Vector3.ONE * half
		bmax = Vector3.ONE * half
	var bhalf: float = 0.5 * maxf(bmax.x - bmin.x, maxf(bmax.y - bmin.y, bmax.z - bmin.z)) * 1.000001 + 1e-6
	var job := {
		"sites": sites,
		"psy": _rd.buffer_get_data(_ml_psi_y, 0, S * 4).to_float32_array(),
		"psi": _rd.buffer_get_data(_ml_psi_i, 0, S * 4).to_float32_array(),
		"vol": _rd.buffer_get_data(_ml_vol, 0, S * 4).to_float32_array(),
		"rho": _rd.buffer_get_data(_mass_density_buf, 0, N3 * 4).to_float32_array(),
		"pos": _rd.buffer_get_data(_pos_buf, 0, Np * 16).to_float32_array(),
		"bmin": bmin,
		"half": bhalf,
		"ext": ext,
		"S": S,
		"N3": N3,
		"Np": Np,
		"grid_N": grid_N,
		"eps2": ML_TREE_EPS2_FRAC * ML_TREE_EPS2_FRAC * _extent_min() * _extent_min(),
		"tnm": ML_TREE_NODE_MAX_MULT * S + 64,
		"coherence_theta": coherence_theta,
		"coherence_theta_alpha": coherence_theta_alpha,
		"q_cent": _q_mean,
	}
	var res: Dictionary = _tree_worker.submit(job)   # blocks only on the bootstrap frame
	if res.is_empty():
		res = _tree_worker.poll()
	if not res.is_empty():
		var grad: PackedFloat32Array = res.get("grad", PackedFloat32Array())
		if grad.size() == Np * 4:
			_rd.buffer_update(_ml_tree_grad, 0, grad.size() * 4, grad.to_byte_array())
		_ml_tree_nnode = int(res.get("nc", 0))


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


# load+x → FFT(y) → FFT(z) → Φ̂=−ρ̂/k² (k=0 nulled) → IFFT(z) → IFFT(y) → IFFT(x)
# FUSED (cassi_poisson.glsl modes 4/5): mode 4 = load ρ + forward-x in one
# pass; mode 5 = the k-space multiply fused into the inverse-z pass. 6
# dispatches per solve instead of 8 — 2 fewer global barriers. All FFT
# passes are multi-row: R = 256/grid_N rows per workgroup → dispatch
# (grid_N, grid_N²/256, 1) instead of (grid_N, grid_N, 1).
func _dispatch_poisson(cl: int) -> void:
	if not _poisson_shader.is_valid(): return
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


func _presentation_volume_history_wanted() -> bool:
	return _presentation_layers_ready() and _physics_engine != null \
			and bool(_physics_engine.get("_topology_ready")) \
			and presentation_profile and presentation_volume_history_enabled and mode == 1 \
			and _volume_history_pipe.is_valid() and _volume_reproject_pipe.is_valid()


func _sync_presentation_volume_history() -> void:
	if not _presentation_volume_history_wanted() and (_volume_current_tex.is_valid() \
			or _volume_history_state.is_valid() or _us_volume_history_0.is_valid()):
		_free_volume_history_resources()
		# The current-only producer shares the resolved output target. Its
		# cache must not retain a temporal image after the live opt-out.
		_invalidate_volume_render_cache()


func _free_volume_history_resources() -> void:
	if _rd != null:
		var seen := {}
		for rid in [_us_volume_history_0, _us_volume_reproject_ab, _us_volume_reproject_ba]:
			if rid.is_valid() and _rd.uniform_set_is_valid(rid) and not seen.has(rid):
				seen[rid] = true
				_rd.free_rid(rid)
		for rid in [_volume_current_tex, _volume_current_depth_tex,
					_volume_history_color_a, _volume_history_color_b,
					_volume_history_depth_a, _volume_history_depth_b,
					_volume_history_state]:
			if rid.is_valid():
				_rd.free_rid(rid)
	_us_volume_history_0 = RID()
	_us_volume_reproject_ab = RID()
	_us_volume_reproject_ba = RID()
	_volume_current_tex = RID()
	_volume_current_depth_tex = RID()
	_volume_history_color_a = RID()
	_volume_history_color_b = RID()
	_volume_history_depth_a = RID()
	_volume_history_depth_b = RID()
	_volume_history_state = RID()
	_volume_history_prev_is_a = true
	_volume_history_has_state = false
	_volume_history_last_origin = Vector3.INF
	_volume_history_last_forward = Vector3.ZERO
	_volume_history_last_fov = -1.0
	_volume_history_last_size = Vector2i(-1, -1)
	_volume_history_last_topology = -1
	_volume_history_last_query = -1
	_volume_history_last_key = -1.0


func _invalidate_volume_history_state() -> void:
	if _rd != null and _volume_history_state.is_valid():
		var zero := PackedByteArray()
		zero.resize(20 * 4)
		zero.fill(0)
		_rd.buffer_update(_volume_history_state, 0, zero.size(), zero)
	_volume_history_has_state = false
	_volume_history_last_origin = Vector3.INF
	_volume_history_last_forward = Vector3.ZERO
	_volume_history_last_fov = -1.0
	_volume_history_last_size = Vector2i(-1, -1)
	_volume_history_last_topology = -1
	_volume_history_last_query = -1
	_volume_history_last_key = -1.0


func _ensure_volume_history_resources() -> bool:
	if _field_render_tex.is_valid() and _volume_history_neutral.is_valid() \
			and _volume_current_tex.is_valid() and _volume_current_depth_tex.is_valid() \
			and _volume_history_color_a.is_valid() and _volume_history_color_b.is_valid() \
			and _volume_history_depth_a.is_valid() and _volume_history_depth_b.is_valid() \
			and _volume_history_state.is_valid():
		return true
	_free_volume_history_resources()
	if _rd == null or not _field_render_tex.is_valid() or not _volume_history_neutral.is_valid():
		return false
	_volume_current_tex = _make_render_texture(_rt_size.x, _rt_size.y)
	_volume_current_depth_tex = _make_render_depth_texture(_rt_size.x, _rt_size.y)
	_volume_history_color_a = _make_render_texture(_rt_size.x, _rt_size.y)
	_volume_history_color_b = _make_render_texture(_rt_size.x, _rt_size.y)
	_volume_history_depth_a = _make_render_depth_texture(_rt_size.x, _rt_size.y)
	_volume_history_depth_b = _make_render_depth_texture(_rt_size.x, _rt_size.y)
	_volume_history_state = _rd.storage_buffer_create(20 * 4)
	var clear_color := PackedByteArray()
	clear_color.resize(_rt_size.x * _rt_size.y * 16)
	clear_color.fill(0)
	var clear_depth := PackedByteArray()
	clear_depth.resize(_rt_size.x * _rt_size.y * 4)
	clear_depth.fill(0)
	for tex in [_volume_current_tex, _volume_history_color_a, _volume_history_color_b]:
		_rd.texture_update(tex, 0, clear_color)
	for tex in [_volume_current_depth_tex, _volume_history_depth_a, _volume_history_depth_b]:
		_rd.texture_update(tex, 0, clear_depth)
	var state_zero := PackedByteArray()
	state_zero.resize(20 * 4)
	state_zero.fill(0)
	_rd.buffer_update(_volume_history_state, 0, state_zero.size(), state_zero)
	_volume_history_prev_is_a = true
	return true


func _ensure_volume_history_uniform_sets() -> bool:
	if not _ensure_volume_history_resources() or _physics_engine == null \
			or not _physics_engine.has_method("topology_resources"):
		return false
	var topo: Dictionary = _physics_engine.topology_resources()
	var r0: RID = topo.get("topology_open_label_rid", RID())
	var r1: RID = topo.get("topology_adjacency_rid", RID())
	var r2: RID = topo.get("topology_degree_rid", RID())
	var r3: RID = topo.get("topology_offset_rid", RID())
	var r4: RID = topo.get("topology_neighbor_rid", RID())
	var r5: RID = topo.get("topology_optical_rid", RID())
	var r6: RID = topo.get("topology_status_rid", RID())
	if not r0.is_valid() or not r1.is_valid() or not r2.is_valid() or not r3.is_valid() \
			or not r4.is_valid() or not r5.is_valid() or not r6.is_valid():
		return false
	if not (_us_volume_history_0.is_valid() and _rd.uniform_set_is_valid(_us_volume_history_0)):
		_us_volume_history_0 = _rd.uniform_set_create([
			_uniform_storage(0, r0), _uniform_storage(1, r1),
			_uniform_storage(2, r2), _uniform_storage(3, r3),
			_uniform_storage(4, r4), _uniform_storage(5, r5),
			_uniform_storage(6, r6),
			_get_set2_image_uniform(_volume_history_shader, 7, _volume_current_tex),
			_get_set2_image_uniform(_volume_history_shader, 8, _volume_history_neutral),
			_uniform_storage(9, _volume_stats),
			_get_set2_image_uniform(_volume_history_shader, 10, _volume_current_depth_tex),
		], _volume_history_shader, 0)
	if not (_us_volume_reproject_ab.is_valid() and _rd.uniform_set_is_valid(_us_volume_reproject_ab)):
		_us_volume_reproject_ab = _rd.uniform_set_create([
			_get_set2_image_uniform(_volume_reproject_shader, 0, _volume_current_tex),
			_get_set2_image_uniform(_volume_reproject_shader, 1, _volume_current_depth_tex),
			_get_set2_image_uniform(_volume_reproject_shader, 2, _volume_history_color_a),
			_get_set2_image_uniform(_volume_reproject_shader, 3, _volume_history_depth_a),
			_get_set2_image_uniform(_volume_reproject_shader, 4, _field_render_tex),
			_get_set2_image_uniform(_volume_reproject_shader, 5, _volume_history_color_b),
			_get_set2_image_uniform(_volume_reproject_shader, 6, _volume_history_depth_b),
			_uniform_storage(7, _volume_history_state),
		], _volume_reproject_shader, 0)
	if not (_us_volume_reproject_ba.is_valid() and _rd.uniform_set_is_valid(_us_volume_reproject_ba)):
		_us_volume_reproject_ba = _rd.uniform_set_create([
			_get_set2_image_uniform(_volume_reproject_shader, 0, _volume_current_tex),
			_get_set2_image_uniform(_volume_reproject_shader, 1, _volume_current_depth_tex),
			_get_set2_image_uniform(_volume_reproject_shader, 2, _volume_history_color_b),
			_get_set2_image_uniform(_volume_reproject_shader, 3, _volume_history_depth_b),
			_get_set2_image_uniform(_volume_reproject_shader, 4, _field_render_tex),
			_get_set2_image_uniform(_volume_reproject_shader, 5, _volume_history_color_a),
			_get_set2_image_uniform(_volume_reproject_shader, 6, _volume_history_depth_a),
			_uniform_storage(7, _volume_history_state),
		], _volume_reproject_shader, 0)
	return _us_volume_history_0.is_valid() and _us_volume_reproject_ab.is_valid() \
			and _us_volume_reproject_ba.is_valid()


func _volume_history_geometry_key() -> float:
	# Stable and exactly representable (< 2^24). Camera/window/size live in
	# the state record; this key covers presentation radiance semantics.
	return float(mode * 64 + _presentation_color_scheme * 8 \
			+ (1 if presentation_profile else 0) \
			+ int(volume_dynamic_resolution) * 2)


func _volume_history_reject_current(origin: Vector3, forward: Vector3, fov: float,
		generation: int, query_generation: int, key: float) -> bool:
	if not _volume_history_has_state:
		return true
	if _volume_history_last_size != _rt_size or generation != _volume_history_last_topology \
			or query_generation != _volume_history_last_query \
			or not is_equal_approx(key, _volume_history_last_key):
		return true
	if absf(fov - _volume_history_last_fov) > 0.002:
		return true
	if origin.distance_to(_volume_history_last_origin) > maxf(0.5, _extent_min() * 0.05):
		return true
	return forward.normalized().dot(_volume_history_last_forward.normalized()) < 0.9986


func _store_volume_history_state(origin: Vector3, transform: Transform3D, fov: float,
		generation: int, query_generation: int, key: float) -> void:
	if not _volume_history_state.is_valid():
		return
	var right := transform.basis.x.normalized()
	var up := transform.basis.y.normalized()
	var forward := -transform.basis.z.normalized()
	_volume_history_state_bytes.encode_float(0, origin.x)
	_volume_history_state_bytes.encode_float(4, origin.y)
	_volume_history_state_bytes.encode_float(8, origin.z)
	_volume_history_state_bytes.encode_float(12, fov)
	_volume_history_state_bytes.encode_float(16, right.x)
	_volume_history_state_bytes.encode_float(20, right.y)
	_volume_history_state_bytes.encode_float(24, right.z)
	_volume_history_state_bytes.encode_float(28, float(_rt_size.x))
	_volume_history_state_bytes.encode_float(32, up.x)
	_volume_history_state_bytes.encode_float(36, up.y)
	_volume_history_state_bytes.encode_float(40, up.z)
	_volume_history_state_bytes.encode_float(44, float(_rt_size.y))
	_volume_history_state_bytes.encode_float(48, forward.x)
	_volume_history_state_bytes.encode_float(52, forward.y)
	_volume_history_state_bytes.encode_float(56, forward.z)
	_volume_history_state_bytes.encode_float(60, 0.0)
	_volume_history_state_bytes.encode_float(64, float(generation))
	_volume_history_state_bytes.encode_float(68, float(query_generation))
	_volume_history_state_bytes.encode_float(72, key)
	_volume_history_state_bytes.encode_float(76, 1.0)
	_rd.buffer_update(
		_volume_history_state, 0,
		_volume_history_state_bytes.size(), _volume_history_state_bytes)
	_volume_history_has_state = true
	_volume_history_last_origin = origin
	_volume_history_last_forward = forward
	_volume_history_last_fov = fov
	_volume_history_last_size = _rt_size
	_volume_history_last_topology = generation
	_volume_history_last_query = query_generation
	_volume_history_last_key = key
func _make_render_textures() -> void:
	_render_texture_rebuild_count += 1
	if _rt_size.x <= 0 or _rt_size.y <= 0:
		_rt_size = Vector2i(512, 512)
	# Image uniform sets reference the old textures, so release every
	# presentation-history set before replacing the texture RIDs.
	_free_volume_history_resources()
	if _us_fr_2.is_valid() and _rd.uniform_set_is_valid(_us_fr_2): _rd.free_rid(_us_fr_2)
	if _us_volume_0.is_valid() and _rd.uniform_set_is_valid(_us_volume_0): _rd.free_rid(_us_volume_0)
	_us_fr_2 = RID(); _us_volume_0 = RID()
	if _field_render_tex.is_valid(): _rd.free_rid(_field_render_tex)
	if _volume_history_neutral.is_valid(): _rd.free_rid(_volume_history_neutral)
	_field_render_tex = _make_render_texture(_rt_size.x, _rt_size.y)
	_volume_history_neutral = _make_render_texture(_rt_size.x, _rt_size.y)
	var clear := PackedByteArray(); clear.resize(_rt_size.x * _rt_size.y * 16); clear.fill(0)
	_rd.texture_update(_volume_history_neutral, 0, clear)


func _fill_volume_pc(origin: Vector3, transform: Transform3D, forward: Vector3,
		fov: float, site_count: int, ext: Vector3, generation: int,
		query_generation: int, profile_enabled: bool) -> void:
	_volume_pc_bytes.encode_float(0, origin.x)
	_volume_pc_bytes.encode_float(4, origin.y)
	_volume_pc_bytes.encode_float(8, origin.z)
	_volume_pc_bytes.encode_float(12, fov)
	_volume_pc_bytes.encode_float(16, transform.basis.x.x)
	_volume_pc_bytes.encode_float(20, transform.basis.x.y)
	_volume_pc_bytes.encode_float(24, transform.basis.x.z)
	_volume_pc_bytes.encode_float(28, float(_rt_size.x))
	_volume_pc_bytes.encode_float(32, transform.basis.y.x)
	_volume_pc_bytes.encode_float(36, transform.basis.y.y)
	_volume_pc_bytes.encode_float(40, transform.basis.y.z)
	_volume_pc_bytes.encode_float(44, float(_rt_size.y))
	_volume_pc_bytes.encode_float(48, forward.x)
	_volume_pc_bytes.encode_float(52, forward.y)
	_volume_pc_bytes.encode_float(56, forward.z)
	_volume_pc_bytes.encode_float(60, float(site_count))
	_volume_pc_bytes.encode_float(64, ext.x)
	_volume_pc_bytes.encode_float(68, ext.y)
	_volume_pc_bytes.encode_float(72, ext.z)
	_volume_pc_bytes.encode_float(76, float(grid_N))
	_volume_pc_bytes.encode_float(80, float(generation))
	_volume_pc_bytes.encode_float(84, float(query_generation))
	_volume_pc_bytes.encode_float(88, 1.0 if profile_enabled else 0.0)
	_volume_pc_bytes.encode_float(92, float(_presentation_color_scheme))
	_volume_pc_bytes.encode_float(96, 0.0)
	_volume_pc_bytes.encode_float(100, 128.0)
	_volume_pc_bytes.encode_float(104, 1e-3)
	_volume_pc_bytes.encode_float(108, float(generation))
	_volume_pc_bytes.encode_float(112, 0.0)
	_volume_pc_bytes.encode_float(116, 0.0)
	_volume_pc_bytes.encode_float(120, 0.0)
	_volume_pc_bytes.encode_float(124, 1.0)

func _render_site_volume() -> void:
	# A selected temporal path must never fall through to the current-only
	# pipeline while its own topology uniforms are still being built. Keeping
	# the last resolved image is both visually stable and avoids binding a
	# stale/null current-only uniform set during the live toggle transition.
	if _presentation_volume_history_wanted():
		_render_site_volume_history()
		return
	var cam := _sim_cam
	if cam == null: return
	if _physics_engine == null or not bool(_physics_engine.get("_topology_ready")):
		return
	# Public/direct callers (the palette parity verifier included) may enter
	# this producer immediately after history teardown. Rebind its dedicated
	# topology/image set before recording, rather than silently binding null.
	if not _volume_pipe.is_valid() or not _us_volume_0.is_valid() \
			or not _rd.uniform_set_is_valid(_us_volume_0):
		if not _sync_volume_uniform_set():
			return
	# The site-native producer writes the same shared render target consumed by
	# the existing Texture2DRD → field_texture_updated → SimUI TextureRect
	# seam. Keep the wrapper stable across frames; no CPU texture copy.
	if field_display_texture == null or not (field_display_texture is Texture2DRD):
		field_display_texture = CassiGpuTextureBridge.wrap(_field_render_tex)
	var ext := _extents()
	var transform: Transform3D = cam.global_transform
	var fov := cam.fov * PI / 180.0
	var generation := int(_physics_engine.topology_generation_value()) if _physics_engine != null else 0
	var site_count := int(_physics_engine.topology_site_count_value()) if _physics_engine != null else 0
	if not _volume_needs_dispatch(generation, site_count, transform, fov, _window_center, ext):
		_volume_skip_count += 1
		return
	var started := Time.get_ticks_usec()
	var origin := cam.global_position - _window_center
	var forward := -transform.basis.z
	_fill_volume_pc(
		origin, transform, forward, fov, site_count, ext,
		generation, generation, presentation_profile)
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _volume_pipe); _rd.compute_list_bind_uniform_set(cl, _us_volume_0, 0)
	_rd.compute_list_set_push_constant(cl, _volume_pc_bytes, 128); _rd.compute_list_dispatch(cl, ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1); _rd.compute_list_end()
	_volume_dispatch_id += 1
	_volume_last_record_us = Time.get_ticks_usec() - started; _volume_max_record_us = maxi(_volume_max_record_us, _volume_last_record_us)
	_note_volume_dispatch_frame(get_process_delta_time() * 1000.0)
	_volume_last_generation = generation; _volume_last_site_count = site_count; _volume_last_cam_transform = transform; _volume_last_fov = fov; _volume_last_window_center = _window_center; _volume_last_extents = ext; _volume_last_rt_size = _rt_size; _volume_last_max_steps = 128.0; _volume_last_cutoff = 1e-3; _volume_cache_valid = true
	_volume_last_history_weight = -1.0
	_volume_last_history_depth_tolerance = -1.0
	_volume_last_scheduling = 0.0
	# Publish the same Texture2DRD object through the existing SimUI seam.
	field_texture_updated.emit(field_display_texture)


func _render_site_volume_history() -> bool:
	var cam := _sim_cam
	if cam == null or _physics_engine == null or not bool(_physics_engine.get("_topology_ready")):
		return false
	if not _ensure_volume_history_uniform_sets():
		return false
	# The resolved render target remains the one stable Texture2DRD exposed to
	# SimUI. The current/depth and ping-pong history targets are private.
	if field_display_texture == null or not (field_display_texture is Texture2DRD):
		field_display_texture = CassiGpuTextureBridge.wrap(_field_render_tex)
	var ext := _extents()
	var transform: Transform3D = cam.global_transform
	var origin := cam.global_position - _window_center
	var forward := -transform.basis.z.normalized()
	var fov := cam.fov * PI / 180.0
	var generation := int(_physics_engine.topology_generation_value())
	var query_generation := int(_physics_engine.render_query_generation_value()) \
			if _physics_engine.has_method("render_query_generation_value") else generation
	var site_count := int(_physics_engine.topology_site_count_value())
	var key := _volume_history_geometry_key()
	var history_weight := clampf(presentation_volume_history_weight, 0.0, 0.95)
	var history_depth_tolerance := clampf(presentation_volume_history_depth_tolerance, 0.001, 0.5)
	if _volume_cache_valid \
			and _volume_history_has_state \
			and _volume_last_scheduling == 1.0 \
			and not _volume_needs_dispatch(generation, site_count, transform, fov, _window_center, ext) \
			and query_generation == _volume_history_last_query \
			and is_equal_approx(key, _volume_history_last_key) \
			and is_equal_approx(history_weight, _volume_last_history_weight) \
			and is_equal_approx(history_depth_tolerance, _volume_last_history_depth_tolerance):
		_volume_skip_count += 1
		return true
	var reject_history := _volume_history_reject_current(
			origin, forward, fov, generation, query_generation, key)
	_fill_volume_pc(
		origin, transform, forward, fov, site_count, ext,
		generation, query_generation, true)
	_volume_resolve_pc_bytes.fill(0)
	_volume_resolve_pc_bytes.encode_float(0, origin.x)
	_volume_resolve_pc_bytes.encode_float(4, origin.y)
	_volume_resolve_pc_bytes.encode_float(8, origin.z)
	_volume_resolve_pc_bytes.encode_float(12, fov)
	_volume_resolve_pc_bytes.encode_float(16, transform.basis.x.x)
	_volume_resolve_pc_bytes.encode_float(20, transform.basis.x.y)
	_volume_resolve_pc_bytes.encode_float(24, transform.basis.x.z)
	_volume_resolve_pc_bytes.encode_float(28, float(_rt_size.x))
	_volume_resolve_pc_bytes.encode_float(32, transform.basis.y.x)
	_volume_resolve_pc_bytes.encode_float(36, transform.basis.y.y)
	_volume_resolve_pc_bytes.encode_float(40, transform.basis.y.z)
	_volume_resolve_pc_bytes.encode_float(44, float(_rt_size.y))
	_volume_resolve_pc_bytes.encode_float(48, forward.x)
	_volume_resolve_pc_bytes.encode_float(52, forward.y)
	_volume_resolve_pc_bytes.encode_float(56, forward.z)
	_volume_resolve_pc_bytes.encode_float(60, float(generation))
	_volume_resolve_pc_bytes.encode_float(64, float(query_generation))
	_volume_resolve_pc_bytes.encode_float(68, key)
	_volume_resolve_pc_bytes.encode_float(72, history_weight)
	_volume_resolve_pc_bytes.encode_float(76, history_depth_tolerance)
	_volume_resolve_pc_bytes.encode_float(80, 0.0 if reject_history else 1.0)
	var started := Time.get_ticks_usec()
	var history_set: RID = _us_volume_reproject_ab if _volume_history_prev_is_a else _us_volume_reproject_ba
	var cl := _rd.compute_list_begin()
	_rd.compute_list_bind_compute_pipeline(cl, _volume_history_pipe)
	_rd.compute_list_bind_uniform_set(cl, _us_volume_history_0, 0)
	_rd.compute_list_set_push_constant(cl, _volume_pc_bytes, _volume_pc_bytes.size())
	_rd.compute_list_dispatch(cl, ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1)
	_barrier(cl)
	_rd.compute_list_bind_compute_pipeline(cl, _volume_reproject_pipe)
	_rd.compute_list_bind_uniform_set(cl, history_set, 0)
	_rd.compute_list_set_push_constant(
		cl, _volume_resolve_pc_bytes, _volume_resolve_pc_bytes.size())
	_rd.compute_list_dispatch(cl, ceili(_rt_size.x / 8.0), ceili(_rt_size.y / 8.0), 1)
	_rd.compute_list_end()
	_volume_history_prev_is_a = not _volume_history_prev_is_a
	_store_volume_history_state(origin, transform, fov, generation, query_generation, key)
	_volume_dispatch_id += 1
	_volume_last_record_us = Time.get_ticks_usec() - started
	_volume_max_record_us = maxi(_volume_max_record_us, _volume_last_record_us)
	_note_volume_dispatch_frame(get_process_delta_time() * 1000.0)
	_volume_last_generation = generation
	_volume_last_site_count = site_count
	_volume_last_cam_transform = transform
	_volume_last_fov = fov
	_volume_last_window_center = _window_center
	_volume_last_extents = ext
	_volume_last_rt_size = _rt_size
	_volume_last_max_steps = 128.0
	_volume_last_cutoff = 1e-3
	_volume_last_history_weight = history_weight
	_volume_last_history_depth_tolerance = history_depth_tolerance
	_volume_last_scheduling = 1.0
	_volume_cache_valid = true
	field_texture_updated.emit(field_display_texture)
	return true
func _cache_render_texture_sets() -> void:
	# Rebuild ONLY the image uniform sets after _make_render_textures()
	# recreates the textures (the old sets were freed there). The full
	field_display_texture = null
	# _cache_uniform_sets() must not be used here — it would overwrite the
	# live sets of untouched buffers and leak their RIDs.
	if _field_render_shader.is_valid() and _field_render_tex.is_valid():
		_us_fr_2 = _rd.uniform_set_create([
			_get_set2_image_uniform(_field_render_shader, 0, _field_render_tex),
		], _field_render_shader, 2)





# Rendering
# ═══════════════════════════════════════════════════════════════════════

func _free_multimesh() -> void:
	# Release the renderer-owned instance buffer: remove and free the
	# MultiMeshInstance3D child (its MultiMesh holds the RD buffer that
	# _mm_rd_rid points at). Only safe with all uniform sets already freed
	# (callers free them first — see reinit).
	_free_macro_lod_multimesh()
	_free_trail_multimesh()
	_free_rotation_orientation_multimesh()
	if _mmi != null and is_instance_valid(_mmi):
		remove_child(_mmi)
		_mmi.free()
	_mmi = null
	_mm = null
	_mm_rd_rid = RID()


func _update_particle_cull_bounds() -> void:
	var ext := _extents()
	var local_center := _window_center - _render_window_origin()
	var margin := maxf(_mm_particle_size * 4.0, 1.0)
	var particle_bound := Vector3(
		maxf(ext.x, PARTICLE_CULL_MIN_HALF_EXTENT),
		maxf(ext.y, PARTICLE_CULL_MIN_HALF_EXTENT),
		maxf(ext.z, PARTICLE_CULL_MIN_HALF_EXTENT)
	) + Vector3.ONE * margin
	var particle_aabb := AABB(local_center - particle_bound, particle_bound * 2.0)
	var presentation_margin := maxf(cluster_radius * 0.15, 8.0)
	var presentation_bound := ext + Vector3.ONE * presentation_margin
	var presentation_aabb := AABB(
		local_center - presentation_bound, presentation_bound * 2.0)

	# GPU-written particle positions cannot provide a cheap CPU-side bounds
	# reduction. In presentation mode, bound every potentially visible point
	# by the active camera's far-volume instead. Because the camera remains
	# inside this AABB, rotating or retreating can never frustum-cull the whole
	# MultiMesh before its individual particles reach the rasterizer.
	if presentation_profile and _sim_cam != null and is_instance_valid(_sim_cam):
		var camera_center := _sim_cam.global_position - _render_window_origin()
		var camera_half_extent := maxf(
			_sim_cam.far * 1.05, PARTICLE_CULL_MIN_HALF_EXTENT)
		var camera_bound := Vector3.ONE * camera_half_extent
		var camera_aabb := AABB(camera_center - camera_bound, camera_bound * 2.0)
		particle_aabb = camera_aabb
		presentation_aabb = camera_aabb

	if _mm != null and _mm.custom_aabb != particle_aabb:
		_mm.custom_aabb = particle_aabb
	if _macro_lod_mm != null and _macro_lod_mm.custom_aabb != presentation_aabb:
		_macro_lod_mm.custom_aabb = presentation_aabb
	if _trail_mm != null and _trail_mm.custom_aabb != presentation_aabb:
		_trail_mm.custom_aabb = presentation_aabb
	if _rotation_axis_mm != null and _rotation_axis_mm.custom_aabb != presentation_aabb:
		_rotation_axis_mm.custom_aabb = presentation_aabb

func _setup_multimesh() -> void:
	# Color-as-LUT (Tier-2): the MultiMesh FORMAT is static per build —
	# legacy keeps the instance color channel (16 floats/instance),
	# LUT mode drops it (use_colors=false) and carries the band position +
	# VFX factors in custom_data (still 16 floats/instance — the transform
	# is 12 floats in Godot 4.7's MultiMesh buffer, so a per-instance
	# channel costs the same 16 B either way; the win is the baked color
	# math + the color channel gone). Since 2026-08-14 the VFX flags
	# (0x10/0x20/0x40) are LUT-compatible; the ONLY remaining gate is base
	# mode 4 (see _lut_compatible).
	_mm_lut_mode = color_lut_mode and _lut_compatible()
	if color_lut_mode and not _lut_compatible() and not _warned_lut_build_incompat:
		_warned_lut_build_incompat = true
		push_warning("[CassiSim] color_lut_mode is on with a LUT-incompatible color config (base mode 4 — two-axis ρ) — a band LUT cannot carry the per-instance ρ-lightness axis; falling back to the legacy instancer color path. Use a base mode 0-3 (glow/depth/size VFX are supported in LUT mode) or turn color_lut_mode off and reinit.")
	var qm = QuadMesh.new()
	qm.size = Vector2(particle_size, particle_size)
	qm.orientation = PlaneMesh.FACE_Z

	_mm = MultiMesh.new()
	_mm.transform_format = MultiMesh.TRANSFORM_3D
	_mm.use_colors = not _mm_lut_mode
	_mm.use_custom_data = _mm_lut_mode
	_mm.mesh = qm
	_mm.instance_count = max(N_particles, 1)
	if physics_decoupled:
		# The renderer-owned buffer needs one ordinary upload before global-RD
		# compute can write it. The MultiMesh stays hidden until that first
		# compute list completes, so zeroed records allocate the same buffer
		# without an interpreted identity-fill loop over every particle.
		var seed_inst := PackedFloat32Array()
		seed_inst.resize(max(N_particles, 1) * 16)
		_mm.buffer = seed_inst
	_mm_particle_size = particle_size
	_update_particle_cull_bounds()

	_mmi = MultiMeshInstance3D.new()
	_mmi.multimesh = _mm
	add_child(_mmi)

	# GPU-direct: grab the renderer's instance buffer RID (created by
	# multimesh_allocate_data when instance_count was set above) — the
	# instancer compute shader writes it every step, no readback/upload.
	_mm_rd_rid = RenderingServer.multimesh_get_buffer_rd_rid(_mm.get_rid())
	if _mm_rd_rid.is_valid():
		print("[CassiSim] MultiMesh GPU-direct: renderer buffer RID acquired (%d × 16 floats = %d B/instance, colors=%s custom=%s)" % [max(N_particles, 1), 64, not _mm_lut_mode, _mm_lut_mode])
	else:
		push_error("[CassiSim] multimesh_get_buffer_rd_rid returned an invalid RID — instancer writes will fail")

	var mat = ShaderMaterial.new()
	_particle_compat_shader = load("res://shaders/particle_billboard.gdshader") as Shader
	_particle_presentation_shader = load("res://shaders/particle_billboard_presentation.gdshader") as Shader
	mat.shader = _particle_presentation_shader if presentation_profile and _particle_presentation_shader != null else _particle_compat_shader
	mat.render_priority = 1
	_mmi.material_override = mat
	_apply_particle_presentation_profile()
	_apply_lut_material()


func _render_frame() -> void:
	var now_ms := Time.get_ticks_msec()
	# M0b (perf-decomp 2026-08-15): the color-band refit is deferred to the
	# boundary-accepted occupancy drain (the 2 Hz block below) so its 512 B
	# qhist readback adds no separate global-RD self-stall between the render
	# list recording and its submission. The flag gates the merge off on
	# align frames (FIX 2: never share a frame between the merge burst and
	var render_base: int = int(particle_color_mode) & 0xF
	var align_due := auto_align_colors and render_base >= 2 and render_base <= 4 \
			and _qhist_buf.is_valid() and _step_count > 0 \
			and now_ms - _last_align_ms >= ALIGN_CADENCE_MS
	_align_ran_this_frame = align_due

	# Decoupled producer: read the engine's freshest publish (bookkeeping +
	# the accepted readback group — no snapshot, no mirror refresh) and
	# record the render list (blend −c seam + instancer + qhist) — no
	# physics list on the global RD in this mode.
	if _decoupled_active:
		# A pause freezes simulation-owned window geometry as well as stepping.
		# Rendering and topology publication stay live below so a paused view
		# can still converge its renderer-only resources.
		if playing:
			if tracking_envelope:
				_track_envelope_window()   # percentile measurement updates the target
				_apply_envelope_state()    # continuous applied physics window; never camera
			else:
				_track_window_center()     # movable home-window: slow-cadence COM follow
		_decoupled_poll_and_render()

	# Throttled diagnostics readback (wall-time ~3 Hz; the step-count gate
	# fired 60×/s at high FPS and drained the local device each time).
	# Decoupled: the publish carries the same telemetry at publish frequency
	# (fresher) — the global _tel_buf is never written in this mode.
	var q_guard = now_ms - _last_diag_ms >= int(1000.0 / DIAG_HZ)
	if q_guard and not suppress_readbacks and _field_q.is_valid() and not _decoupled_active:
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
	# at the particles. Saturated and normal bands share the ~1.5 s cadence
	# (perf-decomp 2026-08-15: the saturated 0.5 s rate hammered the shared
	# global RD during cascade scale-ups — it is a visual nicety that must
	# not add readback pressure; FIX 2 had already cut it 0.2 s → 0.5 s).
	# M0b: the refit itself runs in the 2 Hz occupancy block below — its
	# 512 B qhist read rides that block's already-accepted device drain.
	# One-time Poisson residual report (FD-Laplacian check of the Φ solve).
	# River modes only (0, 3 and 4): modes 1/2 skip the solve, so _fft_buf
	# holds stale data there and the residual would be meaningless.
	# Decoupled: the sim's mass-density buffer is not a mirror — skip.
	if not _poisson_residual_done and _shaders_ready and _step_count >= 1 \
			and (gravity_mode == 0 or gravity_mode == 3 or gravity_mode == 4) \
			and not _decoupled_active:
		_poisson_residual_done = true
		_report_poisson_residual()

	# ── Cassi particle merge (opt-in): runs AFTER the physics batch + the
	# frame's render-work recording, in the same submission context as the
	# throttled occupancy readback below (the ONLY place global-RD compute
	# lists + buffer_get_data readbacks reliably execute). The merge's cycle
	# loop needs host CPU prefix-sums between its spatial-hash passes.
	# Every frame; R_m ≈ 0.586 world units is crossed in ~586 dt=0.001 steps
	# ≫ a frame's step budget, so once-per-frame is far inside the reaction
	# budget. Decoupled: skipped — it mutates the mirrored pos buffer.
	# FIX 2 (perf-decomp): never share a frame between the merge burst and
	# the auto-align's global-RD self-stall readback (the two device drains
	# that trip the TDR when concurrent). The merge is cadenced; the auto-
	# align is a 0.5-1.5 s visual nicety — skip the merge on align frames.
	# FIX 3: the merge also waits for its step-cadence (see the
	# merge_cadence_steps export) — accumulated by _run_physics_steps.
	if particle_merge and _step_count > 0 and not _decoupled_active \
			and not _align_ran_this_frame \
			and _merge_step_counter >= _merge_cadence_eff():
		_merge_step_counter = 0
		_run_merge_pass()
	# M0b: verify/headless scenes (playing=false or suppress_readbacks) never
	# reach the occupancy drain, so the deferred align would latch the
	# merge gate off forever (auto_align_colors defaults true). Run it
	# STANDALONE here instead — the old mid-frame position, but only in the
	# gate-off cases — so the 1.5 s cadence advances and the FIX-2 pair
	# (the merge block above already skipped align frames) holds.
	if align_due and (not playing or suppress_readbacks):
		_last_align_ms = now_ms
		_align_color_band()

	# Throttled occupancy + perf report (~2 Hz; interactive runs only —
	# verify scenes keep playing=false and report their own numbers).
	if playing and not suppress_readbacks and now_ms - _last_occ_ms >= 500:
		_last_occ_ms = now_ms
		if _perf_steps > 0:
			var dt_ms: float = float(_perf_phys_us) / 1e3 / float(_perf_steps)
			var fps: float = float(_perf_frames) * 1000.0 / float(max(now_ms - _perf_last_ms, 1))
			# Truthful backlog: decoupled = requested − executed (× dt);
			# inline = the carried accumulator.
			var behind: float = (_decoupled_pending * dt) if _decoupled_active else _step_timer
			print("[CassiSim] perf: fps=%.1f  physics=%.3f ms/step (%d steps, behind %.2f s, lost %d)" % [fps, dt_ms, _perf_steps, behind, _dropped_steps])
		_sample_occupancy()
		# M0b: the color-band refit rides this block's already-accepted drain
		# (the occupancy dispatch + 32 B read self-stall serve the 512 B
		# qhist read too — one device sync instead of two mid-frame drains).
		if align_due:
			_last_align_ms = now_ms
			_align_color_band()
		_perf_phys_us = 0
		_perf_steps = 0
		_perf_frames = 0
		_perf_last_ms = now_ms

	var realtime_mode = int(mode)
	match realtime_mode:
		0:
			_render_particles()
		1:
			_render_particles()
			if _ml_boxless_on():
				_prepare_volume_resolution()
				if _field_render_tex.is_valid() and _volume_history_neutral.is_valid():
					if _volume_set_dirty or not _us_volume_0.is_valid() \
							or not _rd.uniform_set_is_valid(_us_volume_0):
						_sync_volume_uniform_set()
					if _volume_pipe.is_valid() and _us_volume_0.is_valid() \
							and _rd.uniform_set_is_valid(_us_volume_0):
						_render_site_volume()
			elif not _decoupled_active and not field_intelligence_enabled:
				# Legacy raster field rendering remains only for explicit
				# inline compatibility arms. The live decoupled renderer
				# retains its last site-volume image until topology is ready.
				_render_field_slice()
		2:
			_render_particles()



## Auto-align: read the particle q_coh histogram (cassi_qhist.glsl — the
## BOUNDED coherence q_coh = ρ²/(ρ²+φ⁻²+ε²) ∈ [0,1) the instancer maps to
## hue, sampled at the particles), re-fit the Qi cycle band to the live
## p1/p99 spread (blended so the colors track smoothly as coherence grows),
## and reset the bins for the next window. The histogram range is FIXED to
## the bounded channel [1e-6, 0.999] — no per-run growth adaptation (dead).
## Manual legend drags and Fit disable auto_align_colors, so the manual band
## then stands.
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
	# Re-fit: p1/p99 with generous margins, blended; the approach entry
	# follows the band top (the Fit action's convention). All writes are
	# CLAMPED into the bounded q_coh channel [1e-6, 0.999] — q_coh ∈ [0,1)
	# can never run away behind a growing concentration front (the
	# runaway-concentration fix), so an auto-aligned band always stays
	# inside the [0,1) anchor the shader's hue axis lives in.
	var Q_HI_CAP := 0.999  # the bounded q_coh channel's hard anchor (< 1)
	if p99 > p1 * 2.0 and p1 > 0.0:
		var fit_lo: float = clampf(p1 * 0.8, 1e-6, Q_HI_CAP)
		var fit_hi: float = clampf(p99 * 1.5, fit_lo, Q_HI_CAP)
		qi_cycle = qi_cycle.lerp(Vector2(fit_lo, fit_hi), 0.5)
		# Approach entry follows the band top (pinned white point at the
		# φ⁻² decoherence landmark — the engine turns the approach OFF when
		# the cycle top already exceeds φ⁻², i.e. the bulk is saturated).
		qi_approach = Vector2(qi_cycle.y, PHI_INV2)
	_rd.buffer_update(_qhist_buf, 0, _qhist_zero_bytes.size(), _qhist_zero_bytes)


## Compact scientific formatting (GDScript's % has no %e/%g): "4.2e-4".
func _sci(v: float) -> String:
	if v == 0.0:
		return "0"
	var e := int(floor(log(absf(v)) / log(10.0)))
	var m := v / pow(10.0, float(e))
	return "%.2fe%d" % [m, e]


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
	var occ_set: RID = _us_occ_0_dc if (_decoupled_active and _us_occ_0_dc.is_valid()) else _us_occ_0
	if _occ_shader.is_valid() and _occ_pipe.is_valid() and occ_set.is_valid() \
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
		_occ_pc_bytes.encode_float(36, 0.0)  # diagnostics only need counters
		# Zero the counters BEFORE the dispatch (buffer_update outside a
		# compute list — the BH-header contract).
		_rd.buffer_update(_occ_buf, 0, _occ_zero_bytes.size(), _occ_zero_bytes)
		var ocl = _rd.compute_list_begin()
		_rd.compute_list_bind_compute_pipeline(ocl, _occ_pipe)
		_rd.compute_list_bind_uniform_set(ocl, occ_set, 0)
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
	# Decoupled engines own the live particle positions; the sim mirror may
	# remain intentionally stale between accepted publishes.
	var live_pos_rid: RID = _pos_buf
	if _decoupled_active and _physics_engine != null and _physics_engine._pos_buf.is_valid():
		live_pos_rid = _physics_engine._pos_buf
	_ensure_synced()
	var pd = _rd.buffer_get_data(live_pos_rid, 0, N_particles * 16)
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
		var pos_rid: RID = _pos_buf
		if _decoupled_active and _physics_engine != null and _physics_engine._pos_buf.is_valid():
			pos_rid = _physics_engine._pos_buf
		var pos_data = _rd.buffer_get_data(pos_rid, 0, 16)
		if pos_data.size() >= 16:
			var pos = pos_data.to_float32_array()
			print("[CassiSim] p[0] = (%.3f, %.3f, %.3f)  steps=%d" % [
				pos[0], pos[1], pos[2], _step_count])


func _setup_workbench_cursor() -> void:
	_workbench_cursor_world = _window_center
	if _workbench_cursor_marker != null:
		return
	_workbench_cursor_marker = MeshInstance3D.new()
	_workbench_cursor_marker.name = "WorkbenchCursor"
	var sphere := SphereMesh.new()
	sphere.radius = 0.65
	sphere.height = 1.3
	_workbench_cursor_marker.mesh = sphere
	var material := StandardMaterial3D.new()
	material.albedo_color = Color(1.0, 0.72, 0.18, 0.92)
	material.emission_enabled = true
	material.emission = Color(1.0, 0.42, 0.08)
	material.emission_energy_multiplier = 2.0
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	_workbench_cursor_marker.material_override = material
	_workbench_cursor_marker.visible = false
	add_child(_workbench_cursor_marker)
	_workbench_preview_marker = MultiMeshInstance3D.new()
	_workbench_preview_marker.name = "WorkbenchPreview"
	var preview_mesh := SphereMesh.new()
	preview_mesh.radius = 0.24
	preview_mesh.height = 0.48
	var preview_material := StandardMaterial3D.new()
	preview_material.albedo_color = Color(0.18, 0.92, 1.0, 0.56)
	preview_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	preview_material.emission_enabled = true
	preview_material.emission = Color(0.08, 0.72, 1.0)
	preview_material.emission_energy_multiplier = 1.8
	preview_material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	preview_mesh.material = preview_material
	var preview_multimesh := MultiMesh.new()
	preview_multimesh.transform_format = MultiMesh.TRANSFORM_3D
	preview_multimesh.mesh = preview_mesh
	preview_multimesh.instance_count = 0
	_workbench_preview_marker.multimesh = preview_multimesh
	add_child(_workbench_preview_marker)

func workbench_set_preview(points: Array) -> Dictionary:
	if _workbench_preview_marker == null or _workbench_preview_marker.multimesh == null:
		return {"ok": false, "error": "preview_marker_unavailable"}
	var bounded := mini(points.size(), 512)
	var multimesh := _workbench_preview_marker.multimesh
	multimesh.instance_count = bounded
	for index in range(bounded):
		var value: Variant = points[index]
		var point: Vector3
		if value is Vector3:
			point = value
		elif value is Array and value.size() == 3:
			point = Vector3(float(value[0]), float(value[1]), float(value[2]))
		else:
			multimesh.instance_count = 0
			return {"ok": false, "error": "invalid_preview_point"}
		if not point.is_finite():
			multimesh.instance_count = 0
			return {"ok": false, "error": "invalid_preview_point"}
		multimesh.set_instance_transform(index, Transform3D(Basis.IDENTITY, point - _window_center))
	return {"ok": true, "count": bounded}

func workbench_clear_preview() -> void:
	if _workbench_preview_marker != null and _workbench_preview_marker.multimesh != null:
		_workbench_preview_marker.multimesh.instance_count = 0

func _refresh_workbench_cursor_marker() -> void:
	if _workbench_cursor_marker != null:
		_workbench_cursor_marker.position = _workbench_cursor_world - _window_center
		_workbench_cursor_marker.visible = _workbench_cursor_armed

func workbench_set_cursor(world_position: Vector3, source := "numeric") -> Dictionary:
	if not world_position.is_finite():
		return {"ok": false, "error": "invalid_cursor"}
	var ext := _extents()
	var local := world_position - _window_center
	_workbench_cursor_world = _window_center + Vector3(clampf(local.x,-ext.x,ext.x), clampf(local.y,-ext.y,ext.y), clampf(local.z,-ext.z,ext.z))
	_refresh_workbench_cursor_marker()
	workbench_cursor_changed.emit(_workbench_cursor_world, source)
	return {"ok": true, "cursor": _workbench_cursor_world}
func workbench_arm_cursor(armed: bool) -> Dictionary:
	_workbench_cursor_armed = armed
	_refresh_workbench_cursor_marker()
	return {"ok": true, "armed": armed}

func workbench_place_from_screen(screen_position: Vector2) -> Dictionary:
	if not _workbench_cursor_armed:
		return {"ok": false, "error": "cursor_not_armed"}
	if _sim_cam == null:
		return {"ok": false, "error": "camera_unavailable"}
	var origin := _sim_cam.project_ray_origin(screen_position)
	var direction := _sim_cam.project_ray_normal(screen_position).normalized()
	var ext := _extents()
	var relative := origin - _window_center
	var denom := direction.dot(direction)
	var t := direction.dot(_window_center - origin) / maxf(denom, 1e-12)
	var point := origin + direction * maxf(t, _sim_cam.near * 4.0)
	var local := point - _window_center
	point = _window_center + Vector3(clampf(local.x,-ext.x,ext.x), clampf(local.y,-ext.y,ext.y), clampf(local.z,-ext.z,ext.z))
	return workbench_set_cursor(point, "viewport")

func workbench_status() -> Dictionary:
	return field_workbench.status() if field_workbench != null else {"ok": false, "error": "workbench_unavailable"}

func workbench_pause() -> Dictionary:
	return field_workbench.pause()

func workbench_resume() -> Dictionary:
	return field_workbench.resume()

func workbench_step(count := 1) -> Dictionary:
	return field_workbench.step(count)

func workbench_apply(command: Dictionary) -> Dictionary:
	var queued: Dictionary = field_workbench.queue_command(command)
	if not queued.ok or bool(queued.get("duplicate", false)):
		return queued
	var result: Dictionary = field_workbench.apply_queued()
	if result.ok:
		workbench_clear_preview()
	return result

func workbench_preview(command: Dictionary) -> Dictionary:
	var result: Dictionary = field_workbench.preview_command(command)
	if result.ok:
		workbench_set_preview(result.target_sample)
	else:
		workbench_clear_preview()
	return result

func workbench_undo() -> Dictionary:
	var result: Dictionary = field_workbench.undo_last_apply()
	if result.ok:
		workbench_clear_preview()
	return result
func workbench_measure(center: Vector3, radius: float) -> Dictionary:
	return field_workbench.selected_readout(center, radius)

func workbench_log() -> Array[Dictionary]:
	return field_workbench.command_log()

func workbench_capture_checkpoint() -> Dictionary:
	return field_workbench.capture_checkpoint()

func workbench_restore_checkpoint(checkpoint: Dictionary = {}) -> Dictionary:
	return field_workbench.restore_checkpoint(checkpoint)

func workbench_run_branch(name: String, commands: Array, steps := 0) -> Dictionary:
	return field_workbench.run_branch(name, commands, steps)

func workbench_compile_recipe(recipe: Array) -> Dictionary:
	return WorkbenchInitialConditions.compile(recipe, {"extents": _extents(), "window_center": _window_center})

func workbench_signature() -> Dictionary:
	return WorkbenchSignatureScenario.verify_fixture()

func workbench_save(path: String) -> Dictionary:
	var saved: Dictionary = field_workbench.save_scenario()
	if not saved.ok: return saved
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null: return {"ok": false, "error": "scenario_open_failed"}
	file.store_string(JSON.stringify(saved.scenario))
	return {"ok": true, "version": saved.version, "digest": saved.digest}

func workbench_replay(path: String) -> Dictionary:
	if not FileAccess.file_exists(path): return {"ok": false, "error": "scenario_missing"}
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null: return {"ok": false, "error": "scenario_open_failed"}
	var parsed = JSON.parse_string(file.get_as_text())
	return field_workbench.replay_scenario(parsed) if parsed is Dictionary else {"ok": false, "error": "scenario_parse_failed"}

func _workbench_state() -> Dictionary:
	var authority_ready := false
	var authority := "inline"
	if _decoupled_active:
		authority = "decoupled_engine"
		authority_ready = _physics_engine != null and _physics_engine.workbench_ready()
	else:
		authority_ready = _rd != null
	return {"playing":playing, "decoupled_active":_decoupled_active, "authority":authority, "authority_ready":authority_ready,
		"boxless_active":meshless_mode and boxless_field, "meshless_mode":meshless_mode,
		"particle_merge":particle_merge, "black_holes_enabled":black_holes_enabled, "tracking_envelope":tracking_envelope,
		"home_window_enabled":home_window_enabled, "grid_N":grid_N, "extents":_extents(), "window_center":_window_center,
		"particle_count":N_particles, "step":_step_count, "time":_time}

func _workbench_pause() -> void: playing = false
func _workbench_resume() -> void: playing = true
func _workbench_step(count: int) -> void: _run_physics_steps(count)
func _workbench_step_count() -> int: return _step_count
func _workbench_restore_clock(step: int, time_value: float) -> void:
	_step_count = step
	_time = time_value

func _workbench_read_buffers() -> Dictionary:
	if _decoupled_active:
		return _physics_engine.workbench_read_buffers() if _physics_engine != null else {}
	if _rd == null:
		return {}
	return {"grid_N":grid_N, "extents":_extents(), "window_center":_window_center,
		"ey":_rd.buffer_get_data(_field_ey).to_float32_array(), "ei":_rd.buffer_get_data(_field_ei).to_float32_array(),
		"q":_rd.buffer_get_data(_field_q).to_float32_array(), "vel":_rd.buffer_get_data(_field_vel).to_float32_array(),
		"pos":_rd.buffer_get_data(_pos_buf).to_float32_array(), "pvel":_rd.buffer_get_data(_vel_buf).to_float32_array(),
		"acc":_rd.buffer_get_data(_acc_buf).to_float32_array()}

func _workbench_refresh_render_positions(values: PackedFloat32Array) -> Dictionary:
	if _rd == null or not _pos_prev_buf.is_valid() or not _pos_render_buf.is_valid():
		return {"ok":false, "error":"render_position_buffers_unavailable"}
	var bytes := values.to_byte_array()
	_rd.buffer_update(_pos_prev_buf, 0, bytes.size(), bytes)
	_rd.buffer_update(_pos_render_buf, 0, bytes.size(), bytes)
	_last_publish_ms = 0
	_batch_ema_ms = 16.7
	_decoupled_initial_render_pending = false
	return {"ok":true}

func _workbench_write_buffers(buffers: Dictionary, particle_only := false) -> Dictionary:
	if _decoupled_active:
		if _physics_engine == null:
			return {"ok":false, "error":"engine_authority_unavailable"}
		var engine_result: Dictionary = _physics_engine.workbench_write_buffers(buffers, particle_only)
		if not engine_result.ok:
			return engine_result
		var refresh := _workbench_refresh_render_positions(buffers.pos)
		if not refresh.ok:
			return refresh
		engine_result["render_refreshed"] = true
		return engine_result
	if _rd == null or not buffers.has_all(["ey", "ei", "q", "vel", "pos", "pvel", "acc"]):
		return {"ok":false, "error":"inline_authority_buffers_missing"}
	var cells := grid_N * grid_N * grid_N
	var particles := maxi(N_particles, 1) * 4
	if buffers.ey.size() != cells or buffers.ei.size() != cells or buffers.q.size() != cells \
			or buffers.vel.size() != cells * 4 or buffers.pos.size() != particles \
			or buffers.pvel.size() != particles or buffers.acc.size() != particles:
		return {"ok":false, "error":"inline_authority_buffer_size_mismatch"}
	var pairs := [[_pos_buf,buffers.pos],[_vel_buf,buffers.pvel],[_acc_buf,buffers.acc]]
	if not particle_only:
		pairs = [[_field_ey,buffers.ey],[_field_ei,buffers.ei],[_field_q,buffers.q],[_field_vel,buffers.vel]] + pairs
	for pair in pairs:
		var values: PackedFloat32Array = pair[1]
		_rd.buffer_update(pair[0], 0, values.size()*4, values.to_byte_array())
	_grav_warmup = true
	_tl_frame = 0
	var refresh := _workbench_refresh_render_positions(buffers.pos)
	if not refresh.ok:
		return refresh
	return {"ok":true, "authority":"inline", "backend":"authoritative_cpu", "render_refreshed":true}

# ═══════════════════════════════════════════════════════════════════════
# Public API (for UI to call)
# ═══════════════════════════════════════════════════════════════════════

## Latest bounded rotation publication. The deep copy prevents UI/verifier
## callers from mutating the stored production snapshot.
func rotation_snapshot() -> Dictionary:
	return _rotation_snapshot.duplicate(true)


func reinit() -> void:
	if field_particles:
		_apply_field_particles_settings()
	if field_workbench != null:
		field_workbench.invalidate_state()
	_workbench_cursor_world = _window_center
	_refresh_workbench_cursor_marker()
	# STOP ORDER (decoupled): stop the ENGINE worker FIRST (it may be
	# blocked inside a tree-worker submit), THEN the tree worker (via
	# _free_buffers → _tree_worker_stop below). The engine worker must
	# never call into a stopped tree worker.
	if _decoupled_active and _physics_engine != null:
		_physics_engine.stop_threaded()
	_free_uniform_sets()  # cached sets reference the buffers being freed
	_free_buffers()
	_decoupled_active = physics_decoupled
	# The MultiMesh instance buffer is sized at _setup_multimesh from the
	# THEN-current N_particles, and rebuilt when the FORMAT must change:
	# N/size (legacy) or the color-as-LUT flag flipped (use_colors/
	# use_custom_data are static per build). Assigning a differently-sized
	# array to _mm.buffer ERR_FAILs (Godot multimesh.cpp set_buffer size
	# check) and the instancer dispatch then writes out-of-bounds past the
	# stale buffer. Rebuild runs BEFORE _cache_uniform_sets because
	# _us_inst_0 binds the (possibly new) _mm_rd_rid.
	var want_lut: bool = color_lut_mode and _lut_compatible()
	if _mm == null or _mm.instance_count != max(N_particles, 1) or _mm_particle_size != particle_size or _mm_lut_mode != want_lut:
		_free_multimesh()
		_setup_multimesh()
	_setup_buffers()
	_cache_uniform_sets()  # CRITICAL: cached sets reference the OLD freed buffers
	_apply_lut_material()  # reinit may have recreated the material (format flip)
	# Color-as-LUT: bake the real curve immediately after any reinit (the
	# placeholder only ever exists inside _ready→_process ordering races).
	if _mm_lut_mode:
		_fill_instancer_pc()
		_bake_color_lut()
		_lut_bake_dirty = false
	if _decoupled_active:
		# Restart the threaded engine with the CURRENT exports + bootstrap.
		if _decoupled_start_engine():
			_cond_step_counter = 0
			_dropped_steps = 0
			print("[CassiSim] Reinitialized (decoupled)")
			return
		if gridless_physics:
			_fail_gridless_physics("reinit engine start failed")
			return
		push_error("[CassiSim] decoupled reinit failed — falling back to the inline path")
		_decoupled_active = false
	_init_field()          # without this, every dispatch after reinit is stale
	_init_particles()
	_apply_gravity_calibration()
	_grav_warmup = true  # fresh acc cache for the regenerated positions
	_step_count = 0
	_merge_step_counter = 0
	_merge_pair_phase = 0
	_merge_dc_first_completion_logged = false
	_cond_step_counter = 0
	_dropped_steps = 0
	_time = 0.0
	_poisson_residual_done = false
	print("[CassiSim] Reinitialized")


## M3 live level-swap (MACHINE_PLAN.md §6 M3): hot-swap the box/extents/
## field/particle ICs from a cascade-tree level directory (the M2 offline
## tree's survey format; loaded by CassiLevelSwap) — box/extents/ICs from the
## registry instead of a restart. Additive: a no-op unless `level_swap` is on
## (default-off → default live path bit-identical). Returns true on a swap;
## false (with a push_warning) when off, unloadable, or mis-sized.
##
## Contract vs the offline tree: the level's grid_N must match the sim's
## (the M2 tree is uniformly 64³ per D6). The level's physical box extents
## are adopted via box_aspect/box_scale so its particle positions stay
## in-box. r-continuity: the volume-average attractor-r before and after the
## swap is recorded into `_level_swap_r_delta`/`_level_prev_r` for the
## acceptance check (measured, not assumed).
func apply_level(dir_path: String) -> bool:
	if gridless_physics:
		push_warning("[CassiSim] apply_level is unavailable for site-native physics; use reinit with site ICs")
		return false
	if not level_swap or dir_path.is_empty():
		if level_swap:
			push_warning("[CassiSim] apply_level: empty dir — no swap")
		return false
	# Clean stop order (mirrors reinit): stop the physics engine worker BEFORE
	# touching the buffers it owns, so a decoupled run swaps consistently.
	if _decoupled_active and _physics_engine != null:
		_physics_engine.stop_threaded()
		_decoupled_active = false
	# Lazy-load the level reader (class-scope preload would force a top-level
	# dependency; this keeps the default live path free of any loader cost).
	var loader: GDScript = load("res://scripts/cassi_level_swap.gd") as GDScript
	if loader == null:
		push_warning("[CassiSim] apply_level: level-swap loader missing")
		return false
	var lv: Dictionary = loader.load_level(dir_path)
	if not lv.get("ok", false):
		push_warning("[CassiSim] apply_level: %s" % lv.get("error", "load failed"))
		return false
	var nl := int(lv.get("grid_N", 0))
	if nl != grid_N:
		push_warning("[CassiSim] apply_level: level grid_N=%d != sim grid_N=%d — swap refused (M3 contract)" % [nl, grid_N])
		return false
	# Record the PRE-swap attractor-r (volume avg) for the continuity check.
	_level_prev_r = _volume_avg_r()
	# Adopt the level's physical box extents (cubic in the tree → aspect 1).
	var pre_extent := _extents()
	var ext: Vector3 = lv.get("extents", Vector3.ZERO)
	if ext.x > 0.0:
		box_aspect = Vector3.ONE
		# Divide by the PRE-mutation extent: _extents() reflects `box_aspect`
		# which was just set to Vector3.ONE, so post-mutation _extents().x =
		# 1.5·R·old_box_scale (aspect dropped out) and the adopted box would
		# land at ext.x/old_scale whenever the pre-swap box_scale != 1.
		# pre_extent.x already carries the pre-swap aspect × scale, giving
		# the exact level box. (At the default box_scale == 1.0 and aspect
		# ONE this divisor is value-identical to the old _extents().x, so the
		# verify scale-1 path computes the same box_scale as before.)
		box_scale = (ext.x as float) / maxf(pre_extent.x, 1e-30)
	# Particles: realloc at the level's count if it differs, then upload.
	var np := int(lv.get("particle_count", 0))
	var count_changed: bool = np != N_particles
	var ext_changed: bool = not pre_extent.is_equal_approx(_extents())
	# F2/F3: a count change reallocates the per-particle buffers (nbody +
	# merge state) and a count OR extents change invalidates the merge hash
	# geometry; BOTH leave the cached uniform sets stale (they bind the freed
	# RIDs). Rebuild everything here, exactly once, BETWEEN frames (apply_level
	# runs off the render/compute list), then re-cache the sets. Default-off:
	# with particle_merge off, _rebuild_merge_geometry is a no-op and the sets
	# still need rebinding only when count changed (pos/vel/acc realloc'd).
	if count_changed or ext_changed:
		_free_uniform_sets()
		if count_changed:
			# The MultiMesh instance buffer is count-scaled and bound by the
			# instancer sets — rebuild it when N changes (mirror reinit).
			if _mm == null or _mm.instance_count != max(np, 1):
				_free_multimesh()
				_setup_multimesh()
			_realloc_particle_buffers(np)
			N_particles = np
		_rebuild_merge_geometry()
		_cache_uniform_sets()
	# Upload the field (ey/ei; q recomputed when absent).
	var nc: int = grid_N * grid_N * grid_N
	var ey: PackedFloat32Array = lv["ey"]
	var ei: PackedFloat32Array = lv["ei"]
	_rd.buffer_update(_field_ey, 0, ey.size() * 4, ey.to_byte_array())
	_rd.buffer_update(_field_ei, 0, ei.size() * 4, ei.to_byte_array())
	var qarr: PackedFloat32Array = lv.get("q", PackedFloat32Array())
	if qarr.is_empty() or qarr.size() != nc:
		qarr = PackedFloat32Array(); qarr.resize(nc)
		for i in range(nc):
			qarr[i] = ey[i] * ey[i] + ei[i] * ei[i]
	_rd.buffer_update(_field_q, 0, qarr.size() * 4, qarr.to_byte_array())
	var velz := PackedFloat32Array(); velz.resize(nc * 4); velz.fill(0.0)
	_rd.buffer_update(_field_vel, 0, velz.size() * 4, velz.to_byte_array())
	var posxyz: PackedFloat32Array = lv.get("pos_xyz", PackedFloat32Array())
	var masses: PackedFloat32Array = lv.get("masses", PackedFloat32Array())
	var pos := PackedFloat32Array(); pos.resize(np * 4)
	var vel := PackedFloat32Array(); vel.resize(max(np, 1) * 4)
	for i in range(np):
		pos[i * 4] = posxyz[i * 3]; pos[i * 4 + 1] = posxyz[i * 3 + 1]; pos[i * 4 + 2] = posxyz[i * 3 + 2]
		pos[i * 4 + 3] = (masses[i] if i < masses.size() else 1.0)
		vel[i * 4] = 0.0; vel[i * 4 + 1] = 0.0; vel[i * 4 + 2] = 0.0; vel[i * 4 + 3] = 0.0
	_rd.buffer_update(_pos_buf, 0, pos.size() * 4, pos.to_byte_array())
	_rd.buffer_update(_vel_buf, 0, vel.size() * 4, vel.to_byte_array())
	_apply_gravity_calibration()
	_cond_step_counter = 0
	_step_count = 0
	_merge_step_counter = 0
	_merge_pair_phase = 0
	_merge_dc_first_completion_logged = false
	_dropped_steps = 0
	_time = 0.0
	_level = int(lv.get("level", -1))
	_rung_anchor = int(lv.get("rung_anchor", -1))
	_level_rung_score = float(lv.get("rung_score", 0.0))
	_level_swap_r_delta = absf(_volume_avg_r() - _level_prev_r)
	print("[CassiSim] apply_level: level=%d rung=%d np=%d r_delta=%.6f"
		% [_level, _rung_anchor, np, _level_swap_r_delta])
	return true


## Realloc the per-particle buffers (nbody pos/vel/acc AND, when
## particle_merge is on, the merge kernel's per-particle state — alive/mass/
## mom/cen/best/sink/spin/mprev/cl) at a new count. The spatial-hash buffers
## (cc/cs/ch/scr) are NOT touched here (they are hash-sized, not N-sized —
## see _rebuild_merge_geometry); the MultiMesh render buffer is also NOT
## touched here (render-side; apply_level rebuilds it when N changes).
##
## F10 — CALL-SITE TIMING: only safe BETWEEN frames and OUTSIDE any open
## compute list (it frees + recreates RIDs that cached uniform sets bind, so
## callers must _free_uniform_sets() before and _cache_uniform_sets() after).
## In decoupled mode, sync/stop the engine worker first so it cannot be mid-
## submit on buffers this frees.
func _realloc_particle_buffers(n: int) -> void:
	var np1 := maxi(n, 1)
	for rid in [_pos_buf, _vel_buf, _acc_buf]:
		if rid.is_valid():
			_rd.free_rid(rid)
	_pos_buf = _rd.storage_buffer_create(np1 * 16)
	_vel_buf = _rd.storage_buffer_create(np1 * 16)
	_acc_buf = _rd.storage_buffer_create(np1 * 16)
	# Merge per-particle buffers (only exist when particle_merge) — recreate
	# them here so the cached uniform sets never bind freed RIDs after a count
	# change (F2/F3; _setup_buffers sizes these from N_particles).
	if particle_merge:
		for rid in [_merge_alive_buf, _merge_mass_buf, _merge_mom_buf, _merge_cen_buf,
				_merge_best_buf, _merge_sink_buf, _merge_spin_buf, _merge_mprev_buf, _merge_cl_buf]:
			if rid.is_valid():
				_rd.free_rid(rid)
		_merge_alive_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_mass_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_mom_buf = _rd.storage_buffer_create(np1 * 16)
		_merge_cen_buf = _rd.storage_buffer_create(np1 * 16)
		_merge_best_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_sink_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_spin_buf = _rd.storage_buffer_create(np1 * 16)
		_merge_mprev_buf = _rd.storage_buffer_create(np1 * 4)
		_merge_cl_buf = _rd.storage_buffer_create(np1 * 4)
		# F8: the PC byte buffer must stay sized (26 floats) so _merge_bind_dispatch's
		# encode-in-place never targets an empty buffer (covers init N=0 → swap N>0).
		if _merge_pc_bytes.size() != 26 * 4:
			_merge_pc_bytes = PackedByteArray(); _merge_pc_bytes.resize(26 * 4)
		if _merge_scan_pc_bytes.size() != 4 * 4:
			_merge_scan_pc_bytes = PackedByteArray(); _merge_scan_pc_bytes.resize(4 * 4)


## Recompute the merge spatial-hash geometry from the CURRENT extents/R_m and
## recreate the hash-sized buffers (cc/cs/ch + the on-GPU scan scrub). Called
## by apply_level when a level swap changes box_aspect/box_scale (the hash
## geometry and the cc/cs/ch buffer sizes would otherwise go stale → wrong
## neighbor coverage / OOB). Must run with the uniform sets already freed
## (sets bind the old cc/cs/ch RIDs) and before _cache_uniform_sets. F2/F3.
func _rebuild_merge_geometry() -> void:
	if not particle_merge:
		return
	var r_m: float = _extent_min() / float(maxi(grid_N, 1))
	var geom := CassiMergeCommon.hash_geometry(_extents(), r_m)
	_merge_hash_nx = geom["nx"]
	_merge_hash_ny = geom["ny"]
	_merge_hash_nz = geom["nz"]
	_merge_hash_total = geom["total"]
	_merge_cell_wx = geom["cell_wx"]
	_merge_cell_wy = geom["cell_wy"]
	_merge_cell_wz = geom["cell_wz"]
	for rid in [_merge_cc_buf, _merge_cs_buf, _merge_ch_buf, _merge_scr_buf]:
		if rid.is_valid(): _rd.free_rid(rid)
	_merge_cc_buf = _rd.storage_buffer_create(_merge_hash_total * 4)
	_merge_cs_buf = _rd.storage_buffer_create(_merge_hash_total * 4)
	_merge_ch_buf = _rd.storage_buffer_create(_merge_hash_total * 4)
	var nb1 := (_merge_hash_total + 255) / 256
	_merge_nb1a = ((nb1 + 255) / 256) * 256
	_merge_nb2 = (nb1 + 255) / 256
	_merge_scr_buf = _rd.storage_buffer_create((_merge_nb1a + _merge_nb2) * 4)
	var hz := PackedByteArray(); hz.resize(_merge_hash_total * 4); hz.fill(0)
	_rd.buffer_update(_merge_cc_buf, 0, hz.size(), hz)
	_rd.buffer_update(_merge_cs_buf, 0, hz.size(), hz)
	_rd.buffer_update(_merge_ch_buf, 0, hz.size(), hz)
	var sz := PackedByteArray(); sz.resize((_merge_nb1a + _merge_nb2) * 4); sz.fill(0)
	_rd.buffer_update(_merge_scr_buf, 0, sz.size(), sz)
	var mc_zero := PackedByteArray(); mc_zero.resize(MERGE_MAX_CYCLES * 4); mc_zero.fill(0)
	_rd.buffer_update(_merge_mc_buf, 0, mc_zero.size(), mc_zero)


## Volume-average attractor ratio r = ⟨(EY−EI)/(EY+EI)⟩ over the live field
## (the sim's usual r telemetry source), for the M3 level-swap continuity
## check. No readback when freeze or unready.
func _volume_avg_r() -> float:
	if _rd == null or not _field_ey.is_valid():
		return 0.0
	var nc: int = grid_N * grid_N * grid_N
	var ey := _rd.buffer_get_data(_field_ey, 0, nc * 4).to_float32_array()
	var ei := _rd.buffer_get_data(_field_ei, 0, nc * 4).to_float32_array()
	var num := 0.0
	var den := 0.0
	for i in range(nc):
		var e0 := ey[i]; var e1 := ei[i]
		num += e0 - e1
		den += e0 + e1
	return num / maxf(den, 1e-30)


var _level_prev_r: float = 0.0       # volume-average r before the last level swap
var _level_swap_r_delta: float = 0.0 # |r_after − r_before| across the last swap (continuity)
var _level: int = -1                 # current cascade-tree level (after apply_level)
var _rung_anchor: int = -1
var _level_rung_score: float = 0.0


func get_diagnostics() -> String:
	var law := "RIVER" if gravity_mode == 0 else ("HEURISTIC" if gravity_mode == 1 else ("PLUMMER" if gravity_mode == 2 else ("RIVER-SELF" if gravity_mode == 3 else "REALSIM")))
	return "t=%.3f  q_mean=%.4f  ε²=%.6f  H=%.4f  sf=%.3f  steps=%d  grav=%s  G_N=%.4f  calib=%s  attr=%s  φ⁶−1=%.4f" % [
		_time, _q_mean, _eps_mean, _hubble, _scale_factor, _step_count, law,
		_gn_eff, "on" if river_calibrate_gn else "off",
		"on" if field_attractor_init else "off", PHI_6 - 1.0]


