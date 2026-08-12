#[compute]
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
// see the NOTE at tri_grad). The lever is the box size / grid
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
// HEURISTIC mode (gravity_mode == 1, legacy arm for A/B comparison):
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
//             ρ_local = EY+EI trilinear at p (tri_ey/tri_ei); ρ_ref = φ⁻³ =
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
//         (number of chord_g_at evaluations this step; heuristic mode
//         reports 0 — the UI derives fractions from this denominator)
layout(set = 0, binding = 6, std430) coherent buffer Telemetry { uint tel[]; };
// Cell-centered ∇(g·Φ) field (vec4/cell, xyz = gradient, w unused) —
// built by the gradient pass (pass_mode == 1) after the Poisson solve,
// sampled trilinearly by the river arm (pass_mode == 0).
layout(set = 0, binding = 7, std430) buffer GradBuf { vec4 grad[]; };

layout(set = 1, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 1, binding = 1, std430) restrict buffer Velocities { vec4 vel[]; };
layout(set = 1, binding = 2, std430) restrict buffer Accelerations { vec4 acc[]; };

// BHData: bh[0].x = count (unused), bh[1].w = G_N, bh[2].x = cluster radius
// (the Plummer softening scale), bh[2].y = extent, bh[3].x = global
// black_holes_enabled toggle (host writes 1.0/0.0; gates bh_point_gravity
// in ANY gravity mode), bh[4..] = BH records
// (vec4[pos.xyz, mass] + vec4[vel.xyz, age]), max 15.
layout(set = 2, binding = 0, std430) buffer BHData { vec4 bh[36]; };
// Cluster records (set 2 binding 1, max 20): vec4[center.xyz, per-cluster
// particle count]. Written by _init_particles; consumed by the Plummer
// reference arm only (was an unbound/dead buffer before the 3-mode
// gravity selector).
layout(set = 2, binding = 1, std430) readonly buffer ClusterBuf { vec4 cluster[20]; };

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
                         // terms below; BH sector follows the toggle too)
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

// ── Trilinear sample (periodic wrap) of a scalar field ─────────────────
// Implemented via a macro that generates one function per buffer: strict
// GLSL (glslang) rejects unsized array function parameters, so the sampler
// body is duplicated per field at compile time.
#define DEFINE_TRI_SAMPLER(NAME, FIELD) \
float NAME(vec3 wp) { \
    int N = int(pc.N_f); \
    float hn = float(N) * 0.5; \
    float extent = bh[2].y; \
    float inv_ext = 1.0 / max(extent, 0.0001); \
    vec3 gc = (wp * inv_ext) * hn + hn; \
    int i0 = int(floor(gc.x)); \
    int j0 = int(floor(gc.y)); \
    int k0 = int(floor(gc.z)); \
    float fx = gc.x - float(i0); \
    float fy = gc.y - float(j0); \
    float fz = gc.z - float(k0); \
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N; \
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N; \
    float v000 = FIELD[idx3(i0, j0, k0)]; \
    float v100 = FIELD[idx3(i1, j0, k0)]; \
    float v010 = FIELD[idx3(i0, j1, k0)]; \
    float v110 = FIELD[idx3(i1, j1, k0)]; \
    float v001 = FIELD[idx3(i0, j0, k1)]; \
    float v101 = FIELD[idx3(i1, j0, k1)]; \
    float v011 = FIELD[idx3(i0, j1, k1)]; \
    float v111 = FIELD[idx3(i1, j1, k1)]; \
    float q0 = mix(mix(v000, v100, fx), mix(v010, v110, fx), fy); \
    float q1 = mix(mix(v001, v101, fx), mix(v011, v111, fx), fy); \
    return mix(q0, q1, fz); \
}

DEFINE_TRI_SAMPLER(tri_ey, ey)
DEFINE_TRI_SAMPLER(tri_ei, ei)

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

// Trilinear sample (periodic wrap) of the vec4 gradient buffer → vec3
// (w unused). Same coordinate convention as the scalar samplers.
// NOTE (2026-08-09, gated experiment): a separable Catmull-Rom tricubic
// sampler (4×4×4 taps) was implemented and MEASURED as the "bias along
// grid lines" lever — it did NOT reduce the ring anisotropy: |a|(θ)
// max/min = 1.0482 at r = 8h and 1.1445 at r = 4h vs the trilinear
// 1.0441 / 1.1293 (slightly worse — Catmull-Rom overshoot). Verdict:
// the anisotropy is intrinsic to the discrete torus-Green field (its
// cubic structure), not the sampler — reverted per the gate; the lever
// is the box size / grid resolution. Trilinear stays.
vec3 tri_grad(vec3 wp) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    float extent = bh[2].y;
    float inv_ext = 1.0 / max(extent, 0.0001);
    vec3 gc = (wp * inv_ext) * hn + hn;

    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));

    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);

    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;

    vec3 v000 = grad[idx3(i0, j0, k0)].xyz;
    vec3 v100 = grad[idx3(i1, j0, k0)].xyz;
    vec3 v010 = grad[idx3(i0, j1, k0)].xyz;
    vec3 v110 = grad[idx3(i1, j1, k0)].xyz;
    vec3 v001 = grad[idx3(i0, j0, k1)].xyz;
    vec3 v101 = grad[idx3(i1, j0, k1)].xyz;
    vec3 v011 = grad[idx3(i0, j1, k1)].xyz;
    vec3 v111 = grad[idx3(i1, j1, k1)].xyz;

    vec3 q0 = mix(mix(v000, v100, fx), mix(v010, v110, fx), fy);
    vec3 q1 = mix(mix(v001, v101, fx), mix(v011, v111, fx), fy);
    return mix(q0, q1, fz);
}

// ── Gradient-field build pass (pass_mode == 1) ─────────────────────────
// One thread per cell (2D cells dispatch, gid = x + y·N·256 — the
// poisson cells convention; a 1D N³/256 dispatch caps at 65535 groups on
// some devices for N=256). S is evaluated at the cell and its 6 axis
// neighbors DIRECTLY from cell values (no interpolation), then ∇S via
// central differences with periodic wraps, stored to _grad_buf.
// Runs after the Poisson solve and before the N-body pass in the same
// compute list (the nbody arm reads this buffer — see the header).
void grad_main() {
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

    float s00 = chord_s_at(i,  j,  k);
    float spx = chord_s_at(ip, j,  k);  float smx = chord_s_at(im, j,  k);
    float spy = chord_s_at(i,  jp, k);  float smy = chord_s_at(i,  jm, k);
    float spz = chord_s_at(i,  j,  kp); float smz = chord_s_at(i,  j,  km);

    float h = bh[2].y / (float(N) * 0.5);   // cell size (extent / hn)
    grad[gid] = vec4(
        (spx - smx) / (2.0 * h),
        (spy - smy) / (2.0 * h),
        (spz - smz) / (2.0 * h),
        0.0);
}

// ── Telemetry reduction ────────────────────────────────────────────────
// Per-invocation stats are accumulated in registers (no global atomics in
// the hot path), folded into workgroup-shared accumulators, and emitted to
// tel[0..7] by invocation 0 of each workgroup. The last partial workgroup
// still reaches every barrier — no early return may precede a barrier.
// Heuristic mode never calls chord_g_at, so it has no per-sample global atomics.
struct TeleStats {
    uint clamp_hi;   // π/ρ pinned at 0.72      → tel[0]
    uint clamp_lo;   // π/ρ clamped to 0        → tel[1]
    uint rho_guard;  // ρ < 1e-6 guard hits     → tel[2]
    uint q_min;      // float bits              → tel[3]
    uint q_max;      // float bits              → tel[4]
    uint pi_min;     // float bits              → tel[5]
    uint pi_max;     // float bits              → tel[6]
    uint samples;    // chord_g_at evals        → tel[7]
};

shared uint s_cnt[4];  // clamp_hi, clamp_lo, rho_guard, samples
shared uint s_min[2];  // q_min, pi_min (float bits)
shared uint s_max[2];  // q_max, pi_max (float bits)

// ── The coherence factor q and chord factor g at a point ───────────────
float chord_g_at(vec3 wp, out float q_out, out float pi_over_rho, inout TeleStats st) {
    float eyv = tri_ey(wp);
    float eiv = tri_ei(wp);
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
// ESTIMATOR: one trilinear sample of the cell-centered ∇(g·Φ) field
// (built once per step by grad_main). g/π/ρ at p and the clamp logic
// come from chord_g_at EXACTLY as before (telemetry-bearing). The full
// chord product is still computed whole on the grid — never hand-split.
vec3 river_field_acc(vec3 wp, inout TeleStats st) {
    vec3 gradS = tri_grad(wp);
    float q_unused; float pi_over_rho;
    chord_g_at(wp, q_unused, pi_over_rho, st);
    float G_N = bh[1].w;
    return -G_N * pi_over_rho * gradS;
}

// ── Legacy heuristic: sample q_s = EY²+EI² + 0.01·ρ and its gradient ───
void sample_q_field(vec3 wp, out float q_val, out vec3 q_grad) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    float extent = bh[2].y;
    float inv_ext = 1.0 / max(extent, 0.0001);
    vec3 gc = (wp * inv_ext) * hn + hn;

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

    float dx = extent / hn;
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
// (set 2 binding 1, max 20; multi-cluster behavior: contributions from
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
    int nrec = min(int(pc.num_clusters), 20);
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

// Trilinear sample (periodic wrap) of the vec4 FieldVel buffer → vec4
// (the two-fluid medium's own velocity, RealSim viscosity input).
// Same coordinate convention as the scalar samplers. The buffer is
// genuinely evolved by the PDE every step (see the header's
// FIELD-VELOCITY DECISION) — sampling it costs zero new buffers/passes.
vec4 tri_fvel(vec3 wp) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    float extent = bh[2].y;
    float inv_ext = 1.0 / max(extent, 0.0001);
    vec3 gc = (wp * inv_ext) * hn + hn;

    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));

    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);

    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;

    vec4 v000 = fvel[idx3(i0, j0, k0)];
    vec4 v100 = fvel[idx3(i1, j0, k0)];
    vec4 v010 = fvel[idx3(i0, j1, k0)];
    vec4 v110 = fvel[idx3(i1, j1, k0)];
    vec4 v001 = fvel[idx3(i0, j0, k1)];
    vec4 v101 = fvel[idx3(i1, j0, k1)];
    vec4 v011 = fvel[idx3(i0, j1, k1)];
    vec4 v111 = fvel[idx3(i1, j1, k1)];

    vec4 q0 = mix(mix(v000, v100, fx), mix(v010, v110, fx), fy);
    vec4 q1 = mix(mix(v001, v101, fx), mix(v011, v111, fx), fy);
    return mix(q0, q1, fz);
}

// ── RealSim: local two-fluid density ρ = EY + EI at a point ───────────
// Lightweight: pure trilinear sampling of the existing EY/EI buffers — NO
// clamps, NO TeleStats (the dissipation terms are deliberately telemetry-
// silent; only the river arm feeds the clamp counters).
float rho_local_at(vec3 wp) {
    return tri_ey(wp) + tri_ei(wp);
}

// ── RealSim dissipation (gravity_mode == 4 only) ──────────────────────
// Three per-particle terms ADD to the gravity acceleration; they never
// touch the river arm's internals or the telemetry/clamp state. Formulas
// (documented in the header):
//   drag      a = −γ·(ρ_local/ρ_ref)·v,        ρ_ref = φ⁻³ (0.236068)
//   viscosity a = −ν·(v − v_field(p))
//   friction  a = −min(μ·|a_g|, |v|/dt)·v̂      (never reverses: |Δv| ≤ |v|)
// v_field comes from the evolved FieldVel buffer (tri_fvel); |a_g| is the
// gravity magnitude from the river+BH acceleration BEFORE dissipation.
vec3 realsim_dissipation(vec3 wp, vec3 v, vec3 a_g, float rho_local) {
    vec3 a = vec3(0.0);
    // Drag — background resistance, ρ-scaled; vacuum (ρ → 0) coasts.
    a += -pc.realsim_drag * (rho_local / PHI_INV3) * v;
    // Viscosity — shear coupling to the medium's own velocity.
    a += -pc.realsim_viscosity * (v - tri_fvel(wp).xyz);
    // Friction — Coulomb floor; the |v|/dt cap bounds the per-step kick by
    // |v|, so it can never reverse the velocity.
    float vlen = length(v);
    if (vlen > 1e-12) {
        float mag = min(pc.realsim_friction * length(a_g), vlen / pc.dt);
        a += -mag * (v / vlen);
    }
    return a;
}

// ── Total gravity at a point (mode-selected) ───────────────────────────
// Telemetry stats flow through the river path only (heuristic/Plummer
// modes are telemetry-free by design).
vec3 gravity_at(vec3 wp, inout TeleStats st) {
    vec3 acc = vec3(0.0);
    if (bh[3].x > 0.5) acc = bh_point_gravity(wp, pc.eps2);   // BH sector: global black_holes_enabled toggle (bh[3].x), ANY mode
    if (pc.gravity_mode < 0.5 || pc.gravity_mode > 2.5) {
        acc += river_field_acc(wp, st);          // RIVER (modes 0, 3, 4)
    } else if (pc.gravity_mode < 1.5) {
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
        vec3 a_w = gravity_at(pos[i].xyz, st);
        if (pc.gravity_mode > 3.5) {
            // RealSim: evaluate dissipation at the CURRENT (position,
            // velocity) — a one-step approximation (the particle pass uses
            // the half-kick velocity; the O(dt) difference affects only
            // step 1's cached acceleration).
            a_w += realsim_dissipation(pos[i].xyz, vel[i].xyz, a_w, rho_local_at(pos[i].xyz));
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
    if (pc.pass_mode > 1.5) { warmup_main(); return; }   // acc warm-up
    if (pc.pass_mode > 0.5) { grad_main(); return; }     // gradient-field build
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

        // Full-step kick at the updated position — the only field eval
        vec3 grav_acc = gravity_at(p_new, st);
        if (pc.gravity_mode > 3.5) {
            // RealSim: dissipative terms at (p_new, v_half) — the position
            // and velocity the particle has mid-step. Adds to the gravity
            // acceleration; the river arm and TeleStats are untouched.
            grav_acc += realsim_dissipation(p_new, v_half, grav_acc, rho_local_at(p_new));
        }
        vec3 v_new = v_half + grav_acc * hdt;

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
