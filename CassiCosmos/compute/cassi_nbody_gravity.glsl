#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 15 floats (60 B); sets 0 (0-8), 1 (0-3), 2 (0-1)
#version 450
// Cassi N-body Gravity — river-law chord-gradient force (DEFAULT) +
// legacy coherence-gradient heuristic (A/B toggle) + BH point sources.
//
// RIVER mode (gravity_mode == 0, the law — gravity-from-flow.md §4.1):
//   q     = ρ² / (ρ² + φ⁻² + ε²),    ρ = EY + EI,  ε = EY − φ·EI
//   g     = 1 + (φ⁶−1)·q             (φ⁶−1 = pc.xi − 1, the chord coupling)
//   ∇²Φ   = ρ_mass                   (spectral Poisson, cassi_poisson.glsl:
//                                     Φ̂ = −ρ̂/k², k = 0 nulled, Φ < 0 at mass)
//   a     = −G_N·(π/ρ)·∇(g·Φ)        — the FULL chord gradient in ONE pass
//                                     (∇(gΦ) = g∇Φ + Φ(ξ−1)∇q; never hand-split)
//   (π/ρ) = clamp((EY−EI)/(EY+EI), 0, 0.72)
//           — the Yang fraction; clamped positive-definite per the law's
//             sign-definiteness requirement (doc §1.3); saturation counted
//             in the telemetry buffer, not silent.
//
// GRADIENT ESTIMATOR (2026-08-09 upgrade): ∇(g·Φ) is now built ONCE PER
// STEP on the grid — a dedicated pass (pass_mode == 1, one thread per
// cell) evaluates S = g·Φ at cell centers from CELL values (no
// interpolation; g from the law's q at the cell) and stores the central
// differences ∇S to _grad_buf (binding 7). The per-particle river arm
// (pass_mode == 0) then does ONE trilinear sample of _grad_buf per kick.
// The measured "bias along grid lines" — |a|(θ) max/min = 1.0441 at
// r = 8h and 1.1293 at r = 4h — is intrinsic to the discrete torus-Green
// field's cubic structure, NOT the sampler: a gated separable Catmull-Rom
// tricubic experiment did not reduce it (1.0482 / 1.1445 — reverted;
// see the trilinear NOTE (kept with the fused sampler). The lever is the box size / grid
// resolution.
// ESTIMATOR EQUIVALENCE (verified, not assumed): the OLD per-particle
// estimator — central difference of trilinear samples of S at p ± h·ê —
// is ALGEBRAICALLY IDENTICAL to the trilinear cell-centered-gradient
// interpolation for any fixed S field (both blend the two adjacent
// cells' piecewise-constant trilinear gradients with the same weights
// (1−f), f). Verified to 2e-16 on random and 1/r fields — there is NO
// face-crossing error to remove. The upgrade's real content:
//   (i)   the gradient is built once per step from the SAME cell values
//         the Poisson solve and the PDE see (deterministic consistency);
//   (ii)  7× fewer per-particle chord evaluations (telemetry samples per
//         kick drop 7 → 1);
//   (iii) ~3.7× lower per-step cost (58.6 → ~7.3 ms/frame at 1M/64³).
// The earlier reverted stretch's 0.117 toggle mismatch was a DISPATCH
// bug class — a missing descriptor-set binding made the pipeline skip
// the gradient pass entirely (zero/stale gradients) — now fixed: the
// toggle check reads rel = 0.0000. The product g·Φ is still computed
// whole on the grid, never hand-split (∇(gΦ) = g∇Φ + Φ(ξ−1)∇q doctrine
// preserved).
//
// CASCADE GRID (2026-08-12, CASCADE_GRID.md): the gradient order (2/4) and
// the Yin/Yang dual (BCC) grid ride the bh header — bh[3].y = dual flag,
// bh[3].z = gradient order, bh[1].xyz = the dual offset (h_i/2 world units;
// the host encodes extent_i/N). Dual ON: the gradient pass runs twice —
// pass_mode 1.0 on the base lattice (binding 7) and 1.5 on the
// half-cell-shifted lattice (binding 8, g sampled at the SHIFTED cell
// centers); the river arm averages the two ∇(g·Φ) trilinear samples (the
// pair of interleaved grids is the BCC lattice). O4 = 5-point central
// differences in the gradient pass only. Dual OFF + order 2 = the legacy
// chain bit-for-bit.
//   a = G_N·pi_over_rho·∇q_s,  pi_over_rho = clamp(φ⁻³ + 0.7·q_s, 0, 0.72),
//   q_s = EY² + EI² + 0.01·ρ_mass  (the M2Q density hack — NOT the law)
//   (unchanged: still samples the qv field per particle — pass_mode is
//   ignored by this arm; the gradient pass runs regardless of the mode,
//   its cost is O(N³) cells and it does not touch the heuristic path.)
//   Units: the sim's G_N (bh[1].w) convention stays; the law's dimensionless
//   factors multiply it.  Field units: EY/EI are the theory's linear fields
//   (ρ = EY+EI, Π = EY−EI); φ⁻² is dimensionless, so q's denominator is in
//   the same field units — at the theory attractor (EY = φ·EI, ρ = 1+φ)
//   q = (1+φ)²/((1+φ)²+φ⁻²) = 0.947 ≈ 1.  The sim's fluid starts at noise
//   level (ρ ~ 1e-2…1e-1), so q ~ 1e-3…1e-1 and g ≈ 1 + small correction
//   until the fluid grows toward the attractor — the formula as written.
//
// HEURISTIC mode (gravity_mode == 1, legacy arm for A/B comparison):
//   a = G_N·pi_over_rho·∇q_s,  pi_over_rho = clamp(φ⁻³ + 0.7·q_s, 0, 0.72),
//   q_s = EY² + EI² + 0.01·ρ_mass  (the M2Q density hack — NOT the law)
//
// PLUMMER mode (gravity_mode == 2, grid-free REFERENCE arm — 2026-08-10):
//   a = G_N·Σ_c M_c·(c−p)/(|c−p|²+a²)^(3/2),  a = cluster radius
// (bh[2].x), M_c = per-cluster particle count from the cluster buffer
// (set 2 binding 1 — previously unbound). Reads NO Poisson/fluid/gradient
// state; the host skips the Poisson and gradient passes for this mode
// (mass deposit + PDE still run — ρ/q are visual/source state). This is
// a visual/reference mode for the corner-pooling comparison, NOT the law.
//
// RIVER-SELF mode (gravity_mode == 3 — 2026-08-11): the river law ONLY.
// The BH sector follows the global black_holes_enabled toggle (default
// off — particles only): with the toggle off, the BH point-source term
// is gated out and the host skips the BH condensation + BH-integrate
// passes (the BH buffer stays inert/zeroed). The only force on particles
// is their mutual river self-gravity — the same arm, Poisson chain,
// gradient pass and cached-acc KDK as mode 0, bit-for-bit. This is the
// "particle interactions only" answer: no other force machinery exists
// in the sim (no drag/viscosity/friction).
//
// REALSIM mode (gravity_mode == 4 — 2026-08-11): the river law EXACTLY as
// mode 0 (same arm, Poisson chain, gradient pass, cached-acc KDK —
// bit-for-bit; verified <1e-9 in verify_gravity_modes.gd); the BH sector
// follows the global black_holes_enabled toggle (default off — particles
// only). PLUS three per-particle dissipative terms representing motion
// through the two-fluid (EY/EI) medium. All three are evaluated at
// the particle position/velocity in the nbody particle pass and the
// one-shot warm-up pass (mode 4 only), and ADD to the gravity
// acceleration — never inside the river arm, never touching the telemetry
// clamp counters. Opt-in and default-coefficient-driven: with all three
// coefficients at 0 the mode is bit-identical to mode 0.
//   drag      a_drag = −γ·(ρ_local/ρ_ref)·v      γ = realsim_drag (0.5, 1/time at ρ_ref)
//             ρ_local = EY+EI trilinear at p (the fused sample_fields); ρ_ref = φ⁻³ =
//             0.236068 (the attractor). Vacuum regions (ρ → 0) coast.
//   viscosity a_visc = −ν·(v − v_field(p))       ν = realsim_viscosity (0.3, 1/time)
//             v_field = FieldVel (set 0 binding 3), trilinear-sampled — the
//             two-fluid medium's own velocity. FIELD-VELOCITY DECISION
//             (2026-08-11): the PDE genuinely evolves _field_vel to nonzero
//             values every step (cassi_two_fluid.glsl writes
//             vel[id] = vec4(∂EY/∂t, ∂EI/∂t, 0, ε²) each step), so the
//             EXISTING buffer is used — zero new buffers/passes. vel.z is
//             structurally 0 (the two-fluid wave equation evolves two scalar
//             fields); when the medium is at rest viscosity degenerates to
//             −ν·v (adds to drag), which is physically correct.
//   friction  a_fric = −min(μ·|a_g|, |v|/dt)·v̂   μ = realsim_friction (0.01, dimensionless)
//             |a_g| = the gravity magnitude (river + BH) BEFORE dissipation;
//             the |v|/dt cap guarantees |Δv| ≤ |v| — friction NEVER reverses
//             a particle's velocity.
// Dissipation runs ONLY when pc.gravity_mode > 3.5: particle pass at p_new
// with the half-kick velocity v_half; warm-up pass at the CURRENT
// (position, velocity) — a one-step approximation (the O(dt) difference
// affects only step 1's cached acceleration).
//
// TREE-RIVER mode (gravity_mode == 5 — fmm_design.md Q6, wave 3): the river
// law's per-target prefactor applied to the MESHLESS TREE walk's output.
// The meshless arm (meshless_mode && meshless_gravity) replaces the
// spectral-Poisson river chain with an open-boundary Barnes-Hut tree
// (cassi_tree_build.glsl + cassi_tree_gravity.glsl). The tree walk writes,
// per particle, _ml_tree_grad[i] = a(r) = −∇Φ_g (the chord-weighted
// potential gradient's attractive force, G absorbed; sources = the Voronoi
// sites, w_s = m_s·g_s). This arm applies the SAME clamp + telemetry as
// mode 0 — the ONLY change is the ∇(g·Φ) grid sample is replaced by the
// per-particle tree value:  a = −G_N·(π/ρ)·∇Φ_g = G_N·(π/ρ)·tgrad[i].
// The BH sector follows the global black_holes_enabled toggle (like mode
// 0); NO dissipation (that is mode 4). Modes 0-4 are bit-identical (they
// never read binding 3 / the tgrad value).
//
// BH term (when the global black_holes_enabled toggle is on — the host
// writes bh[3].x; in ANY mode; the σ-regularized sector,
// gravity-from-flow.md §4.2, physics unchanged): softened Newtonian
// point sources.
//
// CACHED-ACC KDK (2026-08-10): the previous full-kick acceleration is
// reused for the next first half-kick — ONE field-force evaluation per
// particle per step (was two). The host dispatches a one-shot warm-up
// pass (pass_mode == 2) before the first step so step 1 is exact; the
// telemetry denominator on step 1 doubles (warm-up + KDK samples) — the
// clamp fractions are ratios, so they are unaffected.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer FieldEY { float ey[]; };
layout(set = 0, binding = 1, std430) readonly buffer FieldEI { float ei[]; };
layout(set = 0, binding = 2, std430) readonly buffer FieldQ  { float qv[]; };
layout(set = 0, binding = 3, std430) readonly buffer FieldVel { vec4 fvel[]; };
layout(set = 0, binding = 4, std430) readonly buffer MassDensity { float rho[]; };
// Poisson solution buffer (complex FFT workspace; real part = Φ after solve)
layout(set = 0, binding = 5, std430) readonly buffer PhiBuf { vec2 ph[]; };
// Gravity telemetry (cleared on the GPU each step by cassi_poisson.glsl
// mode 3; accumulated per invocation across both KDK kicks, folded per
// workgroup in shared memory, emitted to the global buffer once per
// workgroup — the old code ran 28–42 contended global atomics per particle
// per step through the 7 chord samples × 2 kicks):
//   [0] = π/ρ upper-clamp hits   [1] = π/ρ lower-clamp hits
//   [2] = ρ-guard hits           [3] = q_min bits   [4] = q_max bits
//   [5] = π/ρ_min bits           [6] = π/ρ_max bits [7] = sample count
//         (number of chord_g_from evaluations this step; heuristic mode
//         reports 0 — the UI derives fractions from this denominator)
layout(set = 0, binding = 6, std430) coherent buffer Telemetry { uint tel[]; };
// Cell-centered ∇(g·Φ) field (vec4/cell, xyz = gradient, w unused) —
// built by the gradient pass (pass_mode == 1) after the Poisson solve,
// sampled trilinearly by the river arm (pass_mode == 0).
layout(set = 0, binding = 7, std430) buffer GradBuf { vec4 grad[]; };
// Dual (Yin/Yang) lattice ∇(g·Φ) — the shifted chain's gradient (built by
// the gradient pass with pass_mode == 1.5 on the half-cell-offset lattice,
// g sampled at the shifted cell centers); sampled trilinearly by the river
// arm and averaged with binding 7 when bh[3].y (the dual flag) is on.
layout(set = 0, binding = 8, std430) buffer GradBuf2 { vec4 g2[]; };
layout(set = 1, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 1, binding = 1, std430) restrict buffer Velocities { vec4 vel[]; };
layout(set = 1, binding = 2, std430) restrict buffer Accelerations { vec4 acc[]; };
// Per-particle tree gradient (mode 5 "tree river"): the meshless tree
// walk's output, _ml_tree_grad[i] = a(r) = −∇Φ_g (attractive, G absorbed).
// Written by cassi_tree_gravity.glsl; read ONLY when gravity_mode == 5.
layout(set = 1, binding = 3, std430) restrict readonly buffer TreeGrad { vec4 tgrad[]; };

// BHData: bh[0].x = count (unused), bh[1].w = G_N, bh[2].x = cluster radius
// (the Plummer softening scale), bh[2].yzw = per-axis box half-extents
// (extent_x, extent_y, extent_z — the φ-aspect box, GRID_LAYOUT.md; the
// samplers and the gradient pass map world → grid with each axis's own
// extent; cube: all three equal the legacy extent), bh[3].x = global
// black_holes_enabled toggle (host writes 1.0/0.0; gates bh_point_gravity
// in ANY gravity mode), bh[1].xyz = the dual-grid offset (h_i/2 world
// units, host encodes extent_i/N; CASCADE_GRID.md), bh[3].y = dual-grid
// flag (1.0 = the BCC partner chain runs and the river arm averages the
// two ∇(g·Φ) samples), bh[3].z = gradient order (2 = 3-point, 4 = 5-point
// central differences), bh[4..] = BH records
// (vec4[pos.xyz, mass] + vec4[vel.xyz, age]), max 15.
layout(set = 2, binding = 0, std430) buffer BHData { vec4 bh[36]; };
// Cluster records (set 2 binding 1, max 64): vec4[center.xyz, per-cluster
// particle count]. Written by _init_particles; consumed by the Plummer
// reference arm only (was an unbound/dead buffer before the 3-mode
// gravity selector). 64-vec4 cap — keep in sync with _cluster_buf in
// cassi_sim.gd (storage_buffer_create(64 * 4 * 4)); cluster indices
// 0..63 are safe.
layout(set = 2, binding = 1, std430) readonly buffer ClusterBuf { vec4 cluster[64]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float t;
    float phi;
    float xi;            // ξ = φ⁶ (17.9443); the chord coupling is ξ − 1
    float eps2;
    float particle_N;
    float mode;
    float source_strength;
    float num_clusters;
    float gravity_mode;  // 0 = RIVER (default), 1 = HEURISTIC (legacy),
                         // 2 = PLUMMER reference (grid-free analytic arm),
                         // 3 = RIVER-SELF (river law only — the BH sector
                         // follows the global black_holes_enabled toggle),
                         // 4 = REALSIM (river law + the three dissipation
                         // terms below; BH sector follows the toggle too),
                         // 5 = TREE-RIVER (fmm_design.md Q6): the river
                         // law's π/ρ prefactor applied to the meshless tree
                         // walk's per-particle ∇Φ_g (G absorbed) — replaces
                         // the grid ∇(g·Φ) sample; BH like mode 0, NO diss.
    float pass_mode;     // 0 = N-body (particles), 1 = gradient-field build,
                         // 2 = acceleration warm-up (first-step acc cache)
    float realsim_drag;      // γ — RealSim drag rate (1/time at ρ_ref)
    float realsim_viscosity; // ν — RealSim shear-coupling rate (1/time)
    float realsim_friction;  // μ — RealSim Coulomb floor (dimensionless)
} pc;

const float PHI_INV2 = 0.3819660112501051;  // φ⁻² — q decoherence threshold
const float PHI_INV3 = 0.2360679774997898;  // φ⁻³ — attractor density scale
                                            // (RealSim drag reference ρ_ref)

// ── Index helpers ──────────────────────────────────────────────────────
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

// ── Fused field sample (river modes) ────────────────────────────────────
// ONE neighborhood traversal at wp computes every field the river arm
// needs — EY, EI (the chord/π/ρ inputs), the cell-centered ∇(g·Φ), and
// (RealSim only) the medium velocity — from the SAME 8 corners with the
// SAME trilinear weights. The previous code ran up to FIVE separate
// trilinear samplers per particle per step in RealSim (∇(g·Φ), EY, EI,
// then EY+EI AGAIN for ρ_local, then FieldVel): 5× the coordinate setup,
// 5× the address math, and repeated loads of the same corners. Bit-
// identical: each field's mix tree is EXACTLY the former sampler's
// (same corner order, same mix(mix(mix)) tree), so this is a pure
// constant-factor refactor of the sample pattern.
struct FieldSmp {
    float ey;      // EY trilinear at wp
    float ei;      // EI trilinear at wp
    vec3 gradS;    // ∇(g·Φ) trilinear at wp (base lattice)
    vec3 gradS2;   // ∇(g·Φ) trilinear at wp (dual lattice; zeros when dual off)
    vec4 fvel;     // FieldVel trilinear at wp (RealSim only; zeros otherwise)
};
FieldSmp sample_fields(vec3 wp) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    vec3 ext = bh[2].yzw;
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    // Movable home-window (perf-decomp 2026-08-15): bh[0].yzw = the field
    // grid's world-origin offset — the world→grid map becomes window-
    // relative. Zero = the fixed-origin box, bit-identical. The dual-
    // lattice cell↔cell map (chord_s_at_dual) is translation-invariant
    // and intentionally unchanged.
    vec3 gc = ((wp - bh[0].yzw) * inv_ext) * hn + hn;
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));
    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;
    // The 8 corners — each address computed once, every field fetches it.
    int c000 = idx3(i0, j0, k0);
    int c100 = idx3(i1, j0, k0);
    int c010 = idx3(i0, j1, k0);
    int c110 = idx3(i1, j1, k0);
    int c001 = idx3(i0, j0, k1);
    int c101 = idx3(i1, j0, k1);
    int c011 = idx3(i0, j1, k1);
    int c111 = idx3(i1, j1, k1);
    FieldSmp s;
    // Each field is fetched and mixed IMMEDIATELY — its 8 corners die
    // before the next field's loads, keeping register pressure at the old
    // per-sampler level (materializing all 24+ corners up front dropped
    // occupancy and hurt throughput).
    s.ey = mix(mix(mix(ey[c000], ey[c100], fx), mix(ey[c010], ey[c110], fx), fy),
               mix(mix(ey[c001], ey[c101], fx), mix(ey[c011], ey[c111], fx), fy), fz);
    s.ei = mix(mix(mix(ei[c000], ei[c100], fx), mix(ei[c010], ei[c110], fx), fy),
               mix(mix(ei[c001], ei[c101], fx), mix(ei[c011], ei[c111], fx), fy), fz);
    s.gradS = mix(mix(mix(grad[c000].xyz, grad[c100].xyz, fx), mix(grad[c010].xyz, grad[c110].xyz, fx), fy),
                  mix(mix(grad[c001].xyz, grad[c101].xyz, fx), mix(grad[c011].xyz, grad[c111].xyz, fx), fy), fz);
    s.gradS2 = vec3(0.0);
    if (bh[3].y > 0.5) {
        // Dual (Yin/Yang) lattice sample: the SAME world point mapped with
        // the shifted grid's map (gc = (wp + off)·scale + hn) — the deposit
        // and the gradient pass of the shifted chain used the identical
        // offset, so this closes the dual chain consistently.
        vec3 off = bh[1].xyz;
        vec3 gc2 = (wp + off) * inv_ext * hn + hn;
        int d0 = int(floor(gc2.x));
        int e0 = int(floor(gc2.y));
        int f0 = int(floor(gc2.z));
        float fx2 = gc2.x - float(d0);
        float fy2 = gc2.y - float(e0);
        float fz2 = gc2.z - float(f0);
        d0 = ((d0 % N) + N) % N;  e0 = ((e0 % N) + N) % N;  f0 = ((f0 % N) + N) % N;
        int d1 = (d0 + 1) % N;    int e1 = (e0 + 1) % N;    int f1 = (f0 + 1) % N;
        int d000 = idx3(d0, e0, f0);
        int d100 = idx3(d1, e0, f0);
        int d010 = idx3(d0, e1, f0);
        int d110 = idx3(d1, e1, f0);
        int d001 = idx3(d0, e0, f1);
        int d101 = idx3(d1, e0, f1);
        int d011 = idx3(d0, e1, f1);
        int d111 = idx3(d1, e1, f1);
        s.gradS2 = mix(mix(mix(g2[d000].xyz, g2[d100].xyz, fx2), mix(g2[d010].xyz, g2[d110].xyz, fx2), fy2),
                       mix(mix(g2[d001].xyz, g2[d101].xyz, fx2), mix(g2[d011].xyz, g2[d111].xyz, fx2), fy2), fz2);
    }
    s.fvel = vec4(0.0);
    if (pc.gravity_mode > 3.5) {
        // FieldVel corners only for RealSim (uniform branch — skipped by
        // modes 0/3, so their load count matches the old path).
        s.fvel = mix(mix(mix(fvel[c000], fvel[c100], fx), mix(fvel[c010], fvel[c110], fx), fy),
                     mix(mix(fvel[c001], fvel[c101], fx), mix(fvel[c011], fvel[c111], fx), fy), fz);
    }
    return s;
}

// ── Cell-centered gradient field of S = g·Φ (river-mode estimator) ────
// The gradient pass (pass_mode == 1) evaluates S at CELL CENTERS from
// CELL values — g from the law's q (ρ = EY+EI, ε = EY−φ·EI), Φ from the
// Poisson solve — then central differences along x/y/z with periodic
// wraps. The per-particle river arm samples this field trilinearly.
// This pass is an ALGEBRAICALLY EQUIVALENT, consistency/performance
// refactor of the old per-particle estimator (verified to 2e-16 — there
// is no O(h) face-crossing error to remove); the measured residual bias
// along grid lines is the discrete torus-Green/cubic field structure.
// See the header for the full equivalence account.
float chord_s_at(int i, int j, int k) {
    int id = idx3(i, j, k);
    float eyv = ey[id];
    float eiv = ei[id];
    float rho_f = eyv + eiv;
    float eps = eyv - pc.phi * eiv;
    float q = (rho_f * rho_f) / (rho_f * rho_f + PHI_INV2 + eps * eps);
    return (1.0 + (pc.xi - 1.0) * q) * ph[id].x;   // g · Φ — whole product
}

// S at the dual-lattice cell center (i + 0.5 on the OFFSET lattice): the
// cell's world position on the shifted grid, EY/EI trilinearly sampled
// back on the base lattice (the field lives on ONE grid — the dual lattice
// only shifts WHERE S is evaluated), Φ from the shifted deposit's solve.
float chord_s_at_dual(int i, int j, int k) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    vec3 ext = bh[2].yzw;
    vec3 off = bh[1].xyz;
    vec3 wp = vec3(float(i) + 0.5 - hn, float(j) + 0.5 - hn, float(k) + 0.5 - hn)
            * (ext / hn) - off;
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    vec3 gc = wp * inv_ext * hn + hn;
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));
    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;
    int c000 = idx3(i0, j0, k0);
    int c100 = idx3(i1, j0, k0);
    int c010 = idx3(i0, j1, k0);
    int c110 = idx3(i1, j1, k0);
    int c001 = idx3(i0, j0, k1);
    int c101 = idx3(i1, j0, k1);
    int c011 = idx3(i0, j1, k1);
    int c111 = idx3(i1, j1, k1);
    float eyv = mix(mix(mix(ey[c000], ey[c100], fx), mix(ey[c010], ey[c110], fx), fy),
                    mix(mix(ey[c001], ey[c101], fx), mix(ey[c011], ey[c111], fx), fy), fz);
    float eiv = mix(mix(mix(ei[c000], ei[c100], fx), mix(ei[c010], ei[c110], fx), fy),
                    mix(mix(ei[c001], ei[c101], fx), mix(ei[c011], ei[c111], fx), fy), fz);
    float rho_f = eyv + eiv;
    float eps = eyv - pc.phi * eiv;
    float q = (rho_f * rho_f) / (rho_f * rho_f + PHI_INV2 + eps * eps);
    return (1.0 + (pc.xi - 1.0) * q) * ph[idx3(i, j, k)].x;
}

// Cell selector: base cell value vs dual-lattice cell-center sample.
float s_cell(int i, int j, int k, bool d) {
    return d ? chord_s_at_dual(i, j, k) : chord_s_at(i, j, k);
}

// NOTE (2026-08-09, gated experiment): a separable Catmull-Rom tricubic
// sampler (4×4×4 taps) was implemented and MEASURED as the "bias along
// grid lines" lever — it did NOT reduce the ring anisotropy: |a|(θ)
// max/min = 1.0482 at r = 8h and 1.1445 at r = 4h vs the trilinear
// 1.0441 / 1.1293 (slightly worse — Catmull-Rom overshoot). Verdict:
// the anisotropy is intrinsic to the discrete torus-Green field (its
// cubic structure), not the sampler — reverted per the gate; the lever
// is the box geometry: the per-axis extents below (bh[2].yzw) make the
// image lattice incommensurate at box scale (GRID_LAYOUT.md). The
// small-scale r/h bias per direction persists; the box-scale axis lock
// is removed. Trilinear stays — the fused sample_fields above uses the
// SAME trilinear weights/tree as the former per-field samplers.

// ── Gradient-field build pass (pass_mode 1.0 base / 1.5 dual) ──────────
// One thread per cell (2D cells dispatch, gid = x + y·N·256 — the
// poisson cells convention; a 1D N³/256 dispatch caps at 65535 groups on
// some devices for N=256). S is evaluated at the cell and its axis
// neighbors — base cell values (is_dual false) or shifted-cell-center
// samples on the dual lattice (is_dual true) — then ∇S via central
// differences with periodic wraps: 3-point (bh[3].z == 2, legacy) or
// 5-point (bh[3].z == 4 — CASCADE_GRID.md §3.2). Stored to binding 7
// (base) or binding 8 (dual). Runs after the Poisson solve and before the
// N-body pass in the same compute list.
void grad_pass(bool is_dual) {
    int N = int(pc.N_f);
    int nc = N * N * N;
    uint gid = gl_GlobalInvocationID.x
             + gl_GlobalInvocationID.y * uint(N * 256);
    if (int(gid) >= nc) return;

    int i = int(gid) % N;
    int j = (int(gid) / N) % N;
    int k = int(gid) / (N * N);

    int ip = (i + 1) % N;     int im = (i - 1 + N) % N;
    int jp = (j + 1) % N;     int jm = (j - 1 + N) % N;
    int kp = (k + 1) % N;     int km = (k - 1 + N) % N;

    float spx = s_cell(ip, j,  k, is_dual);  float smx = s_cell(im, j,  k, is_dual);
    float spy = s_cell(i,  jp, k, is_dual);  float smy = s_cell(i,  jm, k, is_dual);
    float spz = s_cell(i,  j,  kp, is_dual); float smz = s_cell(i,  j,  km, is_dual);

    vec3 h = bh[2].yzw / (float(N) * 0.5);   // per-axis cell sizes (extent_i / hn)
    vec3 g;
    if (bh[3].z > 3.5) {
        int i2p = (i + 2) % N;    int i2m = (i - 2 + N) % N;
        int j2p = (j + 2) % N;    int j2m = (j - 2 + N) % N;
        int k2p = (k + 2) % N;    int k2m = (k - 2 + N) % N;
        float s2px = s_cell(i2p, j, k, is_dual); float s2mx = s_cell(i2m, j, k, is_dual);
        float s2py = s_cell(i, j2p, k, is_dual); float s2my = s_cell(i, j2m, k, is_dual);
        float s2pz = s_cell(i, j, k2p, is_dual); float s2mz = s_cell(i, j, k2m, is_dual);
        g = vec3((-s2px + 8.0 * spx - 8.0 * smx + s2mx) / (12.0 * h.x),
                 (-s2py + 8.0 * spy - 8.0 * smy + s2my) / (12.0 * h.y),
                 (-s2pz + 8.0 * spz - 8.0 * smz + s2mz) / (12.0 * h.z));
    } else {
        g = vec3((spx - smx) / (2.0 * h.x),
                 (spy - smy) / (2.0 * h.y),
                 (spz - smz) / (2.0 * h.z));
    }
    if (is_dual) {
        g2[gid] = vec4(g, 0.0);
    } else {
        grad[gid] = vec4(g, 0.0);
    }
}

// ── Telemetry reduction ────────────────────────────────────────────────
// Per-invocation stats are accumulated in registers (no global atomics in
// the hot path), folded into workgroup-shared accumulators, and emitted to
// tel[0..7] by invocation 0 of each workgroup. The last partial workgroup
// still reaches every barrier — no early return may precede a barrier.
// Heuristic mode never calls chord_g_from, so it has no per-sample global atomics.
struct TeleStats {
    uint clamp_hi;   // π/ρ pinned at 0.72      → tel[0]
    uint clamp_lo;   // π/ρ clamped to 0        → tel[1]
    uint rho_guard;  // ρ < 1e-6 guard hits     → tel[2]
    uint q_min;      // float bits              → tel[3]
    uint q_max;      // float bits              → tel[4]
    uint pi_min;     // float bits              → tel[5]
    uint pi_max;     // float bits              → tel[6]
    uint samples;    // chord_g_from evals        → tel[7]
};

shared uint s_cnt[4];  // clamp_hi, clamp_lo, rho_guard, samples
shared uint s_min[2];  // q_min, pi_min (float bits)
shared uint s_max[2];  // q_max, pi_max (float bits)

// ── The coherence factor q and chord factor g from sampled values ───────
// (the trilinear sampling lives in sample_fields now — this keeps the
// law's evaluation and telemetry EXACTLY as before; bit-identical inputs
// produce bit-identical stats)
float chord_g_from(float eyv, float eiv, out float q_out, out float pi_over_rho, inout TeleStats st) {
    float rho_f = eyv + eiv;
    float eps = eyv - pc.phi * eiv;
    float q = (rho_f * rho_f) / (rho_f * rho_f + PHI_INV2 + eps * eps);
    q_out = q;
    st.samples++;
    st.q_min = min(st.q_min, floatBitsToUint(q));
    st.q_max = max(st.q_max, floatBitsToUint(q));
    if (rho_f < 1e-6) {
        pi_over_rho = 0.0;
        st.rho_guard++;            // ρ guard hit (telemetry, not silent)
    } else {
        pi_over_rho = (eyv - eiv) / rho_f;
        if (pi_over_rho > 0.72) { st.clamp_hi++; pi_over_rho = 0.72; }
        else if (pi_over_rho < 0.0) { st.clamp_lo++; pi_over_rho = 0.0; }
    }
    st.pi_min = min(st.pi_min, floatBitsToUint(pi_over_rho));
    st.pi_max = max(st.pi_max, floatBitsToUint(pi_over_rho));
    return 1.0 + (pc.xi - 1.0) * q;
}

// ── River-mode field force: a = −G_N·(π/ρ)·∇(g·Φ) ─────────────────────
// ESTIMATOR: the cell-centered ∇(g·Φ) field (built once per step by
// grad_pass) + g/π/ρ from the fused sample's EY/EI — the same clamp logic
// and telemetry as before. With the dual grid on (bh[3].y), the two
// lattice samples are averaged (CASCADE_GRID.md §3.1). The full chord
// product is still computed whole on the grid — never hand-split.
vec3 river_field_acc_smp(FieldSmp fs, inout TeleStats st) {
    float q_unused; float pi_over_rho;
    chord_g_from(fs.ey, fs.ei, q_unused, pi_over_rho, st);
    float G_N = bh[1].w;
    vec3 gv = (bh[3].y > 0.5) ? 0.5 * (fs.gradS + fs.gradS2) : fs.gradS;
    return -G_N * pi_over_rho * gv;
}

// ── TREE-RIVER arm (gravity_mode == 5, fmm_design.md Q6) ────────────────
// The meshless tree walk already produced the chord-weighted potential
// gradient's attractive force tgrad[i] = a(r) = −∇Phi_g (G absorbed). The
// per-target river prefactor G_N·(π/ρ)_target is applied exactly as in the
// grid arm — the SAME clamp + telemetry (chord_g_from), ONLY the ∇(g·Φ)
// sample is replaced by the tree walk's per-particle value:
//   a = −G_N·(π/ρ)_target·∇Phi_g  =  +G_N·(π/ρ)_target · tgrad[i]
//      (tgrad = −∇Phi_g, so the + sign keeps it attractive toward matter)
// BH term follows the global black_holes_enabled toggle like mode 0. NO
// dissipation (that is RealSim mode 4's addition).
vec3 tree_river_field_acc(FieldSmp fs, int pi, inout TeleStats st) {
    float q_unused; float pi_over_rho;
    chord_g_from(fs.ey, fs.ei, q_unused, pi_over_rho, st);
    return bh[1].w * bh[3].w * pi_over_rho * tgrad[pi].xyz;
}

// ── Legacy heuristic: sample q_s = EY²+EI² + 0.01·ρ and its gradient ───
void sample_q_field(vec3 wp, out float q_val, out vec3 q_grad) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    vec3 ext = bh[2].yzw;
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    // Movable home-window (perf-decomp 2026-08-15): bh[0].yzw = the field
    // grid's world-origin offset — the world→grid map becomes window-
    // relative. Zero = the fixed-origin box, bit-identical. The dual-
    // lattice cell↔cell map (chord_s_at_dual) is translation-invariant
    // and intentionally unchanged.
    vec3 gc = ((wp - bh[0].yzw) * inv_ext) * hn + hn;

    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));

    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);

    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;

    float M2Q = 0.01;
    float r000 = rho[idx3(i0, j0, k0)];
    float r100 = rho[idx3(i1, j0, k0)];
    float r010 = rho[idx3(i0, j1, k0)];
    float r110 = rho[idx3(i1, j1, k0)];
    float r001 = rho[idx3(i0, j0, k1)];
    float r101 = rho[idx3(i1, j0, k1)];
    float r011 = rho[idx3(i0, j1, k1)];
    float r111 = rho[idx3(i1, j1, k1)];

    float q000 = qv[idx3(i0, j0, k0)] + r000 * M2Q;
    float q100 = qv[idx3(i1, j0, k0)] + r100 * M2Q;
    float q010 = qv[idx3(i0, j1, k0)] + r010 * M2Q;
    float q110 = qv[idx3(i1, j1, k0)] + r110 * M2Q;
    float q001 = qv[idx3(i0, j0, k1)] + r001 * M2Q;
    float q101 = qv[idx3(i1, j0, k1)] + r101 * M2Q;
    float q011 = qv[idx3(i0, j1, k1)] + r011 * M2Q;
    float q111 = qv[idx3(i1, j1, k1)] + r111 * M2Q;

    float q0 = mix(mix(q000, q100, fx), mix(q010, q110, fx), fy);
    float q1 = mix(mix(q001, q101, fx), mix(q011, q111, fx), fy);
    q_val = mix(q0, q1, fz);

    vec3 dx = ext / hn;   // per-axis cell sizes (gradient normalization)
    float qx_l = mix(mix(q000, q001, fz), mix(q010, q011, fz), fy);
    float qx_r = mix(mix(q100, q101, fz), mix(q110, q111, fz), fy);
    float qy_l = mix(mix(q000, q100, fx), mix(q001, q101, fx), fz);
    float qy_r = mix(mix(q010, q110, fx), mix(q011, q111, fx), fz);
    float qz_l = mix(mix(q000, q100, fx), mix(q010, q110, fx), fy);
    float qz_r = mix(mix(q001, q101, fx), mix(q011, q111, fx), fy);
    q_grad = vec3((qx_r - qx_l), (qy_r - qy_l), (qz_r - qz_l)) / dx;
}

// ── Legacy heuristic-mode field force ──────────────────────────────────
vec3 heuristic_field_acc(vec3 wp) {
    float q_s; vec3 grad_q;
    sample_q_field(wp, q_s, grad_q);
    float pi_over_rho = ((pc.phi - 1.0) / (pc.phi + 1.0)) + q_s * 0.7;
    pi_over_rho = clamp(pi_over_rho, 0.0, 0.72);
    float G_N = bh[1].w;
    return G_N * pi_over_rho * grad_q;
}

// ── Plummer-reference mode (gravity_mode == 2) ─────────────────────────
// Softened ANALYTIC enclosed-mass force summed over every cluster record
// (set 2 binding 1, max 64; multi-cluster behavior: contributions from
// ALL clusters add — no cutoff beyond the Plummer softening):
//   a = G_N · Σ_c M_c·(c−p) / (|c−p|² + a²)^(3/2),  a = bh[2].x (cluster
// radius), M_c = the cluster record's per-cluster particle count — the
// SAME mass convention the IC circular velocities use, so G_N = 1 is the
// IC-consistent scale (the calibrated river G_N keeps it aligned with the
// grid force when river_calibrate_gn is on).
// GRID-FREE: reads no Poisson/fluid/gradient state — the reference arm
// for the visual "pooling" comparison and for measuring how much of the
// river's grid structure is intrinsic vs a force-scale artifact. This is
// a visual/reference mode, NOT the river law — the law stays the default.
vec3 plummer_field_acc(vec3 wp) {
    float G_N = bh[1].w;
    float a_soft = max(bh[2].x, 1e-4);
    vec3 acc = vec3(0.0);
    int nrec = min(int(pc.num_clusters), 64);
    vec3 dbg = vec3(0.0);  // DEBUG: sum of (mass, len, 0)
    for (int c = 0; c < nrec; c++) {
        float mass = cluster[c].w;
        if (mass <= 0.0) continue;
        vec3 delta = cluster[c].xyz - wp;
        float r2 = dot(delta, delta) + pc.eps2;
        float denom = r2 + a_soft * a_soft;
        float inv = 1.0 / (denom * sqrt(denom));
        acc += G_N * mass * inv * delta;
        dbg += vec3(mass, length(delta), float(c));
    }
    return acc;
}

// ── BH point-source gravity (σ-regularized sector, unchanged) ──────────
vec3 bh_point_gravity(vec3 particle_pos, float eps2) {
    float G_N = bh[1].w;
    vec3 acc = vec3(0.0);
    for (int b = 0; b < 15; b++) {
        int base = 4 + b * 2;
        float mass = bh[base].w;
        if (mass <= 0.0) continue;  // empty slot
        vec3 delta = bh[base].xyz - particle_pos;
        float r2 = dot(delta, delta) + eps2;
        float inv_r3 = 1.0 / (r2 * sqrt(r2));
        acc += G_N * mass * inv_r3 * delta;
    }
    return acc;
}

// ── RealSim dissipation (gravity_mode == 4 only) ──────────────────────
// Three per-particle terms ADD to the gravity acceleration; they never
// touch the river arm's internals or the telemetry/clamp state. Formulas
// (documented in the header):
//   drag      a = −γ·(ρ_local/ρ_ref)·v,        ρ_ref = φ⁻³ (0.236068)
//   viscosity a = −ν·(v − v_field(p))
//   friction  a = −min(μ·|a_g|, |v|/dt)·v̂      (never reverses: |Δv| ≤ |v|)
// ρ_local and v_field come from the FUSED neighborhood sample (the same
// corners the river arm read) — the old path resampled EY/EI a second
// time for ρ_local and ran a separate FieldVel sampler. Lightweight and
// deliberately telemetry-silent; only the river arm feeds the counters.
vec3 realsim_dissipation_smp(FieldSmp fs, vec3 v, vec3 a_g) {
    vec3 a = vec3(0.0);
    float rho_local = fs.ey + fs.ei;
    // Drag — background resistance, ρ-scaled; vacuum (ρ → 0) coasts.
    a += -pc.realsim_drag * (rho_local / PHI_INV3) * v;
    // Viscosity — shear coupling to the medium's own velocity.
    a += -pc.realsim_viscosity * (v - fs.fvel.xyz);
    // Friction — Coulomb floor; the |v|/dt cap bounds the per-step kick by
    // |v|, so it can never reverse the velocity.
    float vlen = length(v);
    if (vlen > 1e-12) {
        float mag = min(pc.realsim_friction * length(a_g), vlen / pc.dt);
        a += -mag * (v / vlen);
    }
    return a;
}

// ── Legacy-arm gravity (HEURISTIC / PLUMMER modes only) ────────────────
// The river arm (modes 0/3/4) routes through the fused neighborhood
// sample in main()/warmup_main() instead — sample_fields + chord_g_from
// share the SAME EY/EI corners with RealSim's dissipation, so the river
// branch was removed from this selector. Telemetry stats flow through
// the river path only (heuristic/Plummer are telemetry-free by design).
vec3 gravity_at(vec3 wp, inout TeleStats st) {
    vec3 acc = vec3(0.0);
    if (bh[3].x > 0.5) acc = bh_point_gravity(wp, pc.eps2);   // BH sector: global black_holes_enabled toggle (bh[3].x), ANY mode
    if (pc.gravity_mode < 1.5) {
        acc += heuristic_field_acc(wp);          // HEURISTIC (mode 1)
    } else {
        acc += plummer_field_acc(wp);            // PLUMMER (mode 2)
    }
    return acc;
}

// ── Telemetry shared-memory init/fold (both particle passes) ───────────
void tele_begin(int li) {
    // Initialize shared accumulators once; every lane reaches the barrier.
    if (li == 0) {
        s_cnt[0] = 0u; s_cnt[1] = 0u; s_cnt[2] = 0u; s_cnt[3] = 0u;
        s_min[0] = 0x7F800000u; s_min[1] = 0x7F800000u;  // +inf bits
        s_max[0] = 0u; s_max[1] = 0u;
    }
    barrier();
}

TeleStats tele_new_stats() {
    TeleStats st;
    st.clamp_hi = 0u; st.clamp_lo = 0u; st.rho_guard = 0u; st.samples = 0u;
    st.q_min = 0x7F800000u; st.q_max = 0u;
    st.pi_min = 0x7F800000u; st.pi_max = 0u;
    return st;
}

void tele_emit(int li) {
    // EVERY invocation reaches the barrier — including the last partial
    // workgroup (threads with i >= N simply contribute nothing).
    barrier();
    if (li == 0) {
        // One global emission per workgroup (8 atomics), not per particle.
        atomicAdd(tel[0], s_cnt[0]);
        atomicAdd(tel[1], s_cnt[1]);
        atomicAdd(tel[2], s_cnt[2]);
        atomicMin(tel[3], s_min[0]);
        atomicMax(tel[4], s_max[0]);
        atomicMin(tel[5], s_min[1]);
        atomicMax(tel[6], s_max[1]);
        atomicAdd(tel[7], s_cnt[3]);
    }
}

// ── Acceleration warm-up (pass_mode == 2; dispatched by the host ONCE, ─
// before the first KDK step): fills acc[i] = F(p) at the CURRENT positions
// with the CURRENT field, so the cached-acc KDK's first half-kick is a
// fresh evaluation — step 1 is bit-identical to the old two-evaluation
// KDK. No position/velocity update.
void warmup_main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    int li = int(gl_LocalInvocationIndex.x);
    tele_begin(li);
    if (i < N) {
        TeleStats st = tele_new_stats();
        vec3 a_w = vec3(0.0);
        if (pc.gravity_mode < 0.5 || pc.gravity_mode > 2.5) {
            // River: ONE fused neighborhood sample feeds the chord force
            // AND (RealSim) the dissipation — no re-sampling of ρ_local.
            // Mode 5 = tree river: the tree walk's per-particle ∇Φ_g^a.
            FieldSmp fs = sample_fields(pos[i].xyz);
            if (bh[3].x > 0.5) a_w = bh_point_gravity(pos[i].xyz, pc.eps2);
            if (pc.gravity_mode > 4.5) a_w += tree_river_field_acc(fs, i, st);
            else a_w += river_field_acc_smp(fs, st);
            if (pc.gravity_mode > 3.5 && pc.gravity_mode < 4.5) {
                // RealSim (mode 4) ONLY: dissipation at the CURRENT
                // (position, velocity) — a one-step approximation (the
                // particle pass uses the half-kick velocity; the O(dt)
                // difference affects only step 1's cached acceleration).
                a_w += realsim_dissipation_smp(fs, vel[i].xyz, a_w);
            }
        } else {
            a_w = gravity_at(pos[i].xyz, st);   // heuristic / Plummer arms
        }
        acc[i] = vec4(a_w, 0.0);
        atomicAdd(s_cnt[0], st.clamp_hi);
        atomicAdd(s_cnt[1], st.clamp_lo);
        atomicAdd(s_cnt[2], st.rho_guard);
        atomicAdd(s_cnt[3], st.samples);
        atomicMin(s_min[0], st.q_min);
        atomicMax(s_max[0], st.q_max);
        atomicMin(s_min[1], st.pi_min);
        atomicMax(s_max[1], st.pi_max);
    }
    tele_emit(li);
}

// ── Cached-acc KDK leapfrog (pass_mode == 0) ───────────────────────────
// Velocity-Verlet with the previous full-kick acceleration reused for the
// next first half-kick — ONE field-force evaluation per particle per step
// instead of two:
//   v½ = v + a_prev·dt/2;  p' = p + v½·dt;  a' = F(p');  v' = v½ + a'·dt/2
// acc[i] stores a' (the FULL-kick acceleration at p') for the next step —
// p' is exactly the position at the start of the next step, so steps ≥ 2
// are bit-identical to the two-evaluation KDK. Step 1 is made exact by
// the host's warm-up dispatch (pass_mode == 2). Trajectory-verified in a
// float64 shader-exact mini-sim: max |Δp| ≈ 0.15% of a cell and max |Δv|
// ≈ 1.4e-3 vs the two-evaluation KDK over 2000 steps, no secular drift.
void main() {
    if (pc.pass_mode > 1.5) { warmup_main(); return; }    // acc warm-up (2.0)
    if (pc.pass_mode > 1.2) { grad_pass(true); return; }  // dual gradient (1.5)
    if (pc.pass_mode > 0.5) { grad_pass(false); return; } // base gradient (1.0)
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    int li = int(gl_LocalInvocationIndex.x);

    tele_begin(li);

    if (i < N) {
        TeleStats st = tele_new_stats();

        vec3 pxyz = pos[i].xyz;
        vec3 vxyz = vel[i].xyz;
        float hdt = pc.dt * 0.5;

        // First half-kick: reuse the previous full-kick acceleration
        // (cached at the position the particle now occupies).
        vec3 v_half = vxyz + acc[i].xyz * hdt;
        vec3 p_new = pxyz + v_half * pc.dt;

        // Full-step kick at the updated position — the only field eval.
        // River modes: ONE fused neighborhood sample feeds the chord
        // evaluation, the ∇(g·Φ) force AND (RealSim) the dissipation.
        vec3 grav_acc;
        if (pc.gravity_mode < 0.5 || pc.gravity_mode > 2.5) {
            FieldSmp fs = sample_fields(p_new);
            grav_acc = vec3(0.0);
            if (bh[3].x > 0.5) grav_acc = bh_point_gravity(p_new, pc.eps2);
            if (pc.gravity_mode > 4.5) {
                // TREE-RIVER (mode 5): the tree walk's per-particle ∇Φ_g^a
                // replaces the grid ∇(g·Φ) sample (fmm_design.md Q6).
                grav_acc += tree_river_field_acc(fs, i, st);
            } else {
                grav_acc += river_field_acc_smp(fs, st);
            }
            if (pc.gravity_mode > 3.5 && pc.gravity_mode < 4.5) {
                // RealSim (mode 4) ONLY: dissipative terms at (p_new,
                // v_half) — the position and velocity the particle has
                // mid-step. Adds to the gravity acceleration; the river arm
                // and TeleStats are untouched.
                grav_acc += realsim_dissipation_smp(fs, v_half, grav_acc);
            }
        } else {
            grav_acc = gravity_at(p_new, st);   // heuristic / Plummer arms
        }
        vec3 v_new = v_half + grav_acc * hdt;

        // SAFETY GUARD (mode-5 tree arm ONLY): a bad close encounter must
        // never eject a particle or overflow float32 (the pre-fix unsoftened
        // tree quadrupole wiped the galaxy to |p| ~ 1e9 then NaN, 2026-08-13).
        // Bounds are WIDE (far beyond any legitimate escape/halo orbit) so
        // real dynamics are untouched; the river path (mode < 5) is identical.
        if (pc.gravity_mode > 4.5) {
            float emax = max(max(bh[2].y, bh[2].z), bh[2].w); // box half-ext max
            float vcap = 120.0 * emax;      // |v| cap - far above v_escape
            float vl = length(v_new);
            if (vl > vcap) v_new *= vcap / vl;
            float R_safe = 1e4 * emax;      // position reabsorb sphere
            float pl = length(p_new);
            if (pl > R_safe) p_new *= R_safe / pl;
        }

        pos[i] = vec4(p_new, pos[i].w);
        vel[i] = vec4(v_new, 0.0);
        acc[i] = vec4(grav_acc, 0.0);   // cache for the next step's half-kick

        // Fold this invocation's stats into the workgroup accumulators
        // (shared-memory atomics — no global traffic).
        atomicAdd(s_cnt[0], st.clamp_hi);
        atomicAdd(s_cnt[1], st.clamp_lo);
        atomicAdd(s_cnt[2], st.rho_guard);
        atomicAdd(s_cnt[3], st.samples);
        atomicMin(s_min[0], st.q_min);
        atomicMax(s_max[0], st.q_max);
        atomicMin(s_min[1], st.pi_min);
        atomicMax(s_max[1], st.pi_max);
    }

    tele_emit(li);
}
