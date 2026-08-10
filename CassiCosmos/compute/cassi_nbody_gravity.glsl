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
// BH term (both modes, unchanged physics — the σ-regularized sector,
// gravity-from-flow.md §4.2): softened Newtonian point sources.
//
// KDK leapfrog: half-step kick, drift, full-step kick — both kicks
// evaluate the selected mode.

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

layout(set = 1, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 1, binding = 1, std430) restrict buffer Velocities { vec4 vel[]; };
layout(set = 1, binding = 2, std430) restrict buffer Accelerations { vec4 acc[]; };

// BHData: bh[0].x = count (unused), bh[1].w = G_N, bh[2].y = extent,
// bh[4..] = BH records (vec4[pos.xyz, mass] + vec4[vel.xyz, age]), max 15.
layout(set = 2, binding = 0, std430) buffer BHData { vec4 bh[36]; };

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
    float gravity_mode;  // 0 = RIVER (default), 1 = HEURISTIC (legacy)
} pc;

const float PHI_INV2 = 0.3819660112501051;  // φ⁻² — q decoherence threshold

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
// Φ lives in a vec2 buffer (FFT workspace); sample its real part.
float tri_phi(vec3 wp) {
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

    float v000 = ph[idx3(i0, j0, k0)].x;
    float v100 = ph[idx3(i1, j0, k0)].x;
    float v010 = ph[idx3(i0, j1, k0)].x;
    float v110 = ph[idx3(i1, j1, k0)].x;
    float v001 = ph[idx3(i0, j0, k1)].x;
    float v101 = ph[idx3(i1, j0, k1)].x;
    float v011 = ph[idx3(i0, j1, k1)].x;
    float v111 = ph[idx3(i1, j1, k1)].x;

    float q0 = mix(mix(v000, v100, fx), mix(v010, v110, fx), fy);
    float q1 = mix(mix(v001, v101, fx), mix(v011, v111, fx), fy);
    return mix(q0, q1, fz);
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

// ── The flow-modulated chord S = g·Φ at a point (river mode) ───────────
float chord_value(vec3 wp, inout TeleStats st) {
    float q_unused; float pi_unused;
    float g = chord_g_at(wp, q_unused, pi_unused, st);
    return g * tri_phi(wp);               // g · Φ
}
vec3 chord_gradient(vec3 wp, inout TeleStats st) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    float h = bh[2].y / hn;               // cell size
    vec3 dx = vec3(h, 0.0, 0.0);
    vec3 dy = vec3(0.0, h, 0.0);
    vec3 dz = vec3(0.0, 0.0, h);
    return vec3(
        chord_value(wp + dx, st) - chord_value(wp - dx, st),
        chord_value(wp + dy, st) - chord_value(wp - dy, st),
        chord_value(wp + dz, st) - chord_value(wp - dz, st)) / (2.0 * h);
}

// ── River-mode field force: a = −G_N·(π/ρ)·∇(g·Φ) ─────────────────────
vec3 river_field_acc(vec3 wp, inout TeleStats st) {
    vec3 gradS = chord_gradient(wp, st);
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

// ── Total gravity at a point (mode-selected) ───────────────────────────
// Telemetry stats flow through the river path only (heuristic mode is
// telemetry-free by design).
vec3 gravity_at(vec3 wp, inout TeleStats st) {
    vec3 acc = bh_point_gravity(wp, pc.eps2);
    if (pc.gravity_mode < 0.5) {
        acc += river_field_acc(wp, st);   // RIVER — the law (default)
    } else {
        acc += heuristic_field_acc(wp);   // HEURISTIC — legacy arm
    }
    return acc;
}

// ── KDK leapfrog ───────────────────────────────────────────────────────
void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    int li = int(gl_LocalInvocationIndex.x);

    // Initialize shared accumulators once; every lane reaches the barrier.
    if (li == 0) {
        s_cnt[0] = 0u; s_cnt[1] = 0u; s_cnt[2] = 0u; s_cnt[3] = 0u;
        s_min[0] = 0x7F800000u; s_min[1] = 0x7F800000u;  // +inf bits
        s_max[0] = 0u; s_max[1] = 0u;
    }
    barrier();

    if (i < N) {
        TeleStats st;
        st.clamp_hi = 0u; st.clamp_lo = 0u; st.rho_guard = 0u; st.samples = 0u;
        st.q_min = 0x7F800000u; st.q_max = 0u;
        st.pi_min = 0x7F800000u; st.pi_max = 0u;

        vec3 pxyz = pos[i].xyz;
        vec3 vxyz = vel[i].xyz;
        float hdt = pc.dt * 0.5;

        // Half-step kick
        vec3 grav_acc = gravity_at(pxyz, st);
        vec3 v_half = vxyz + grav_acc * hdt;
        vec3 p_new = pxyz + v_half * pc.dt;

        // Full-step kick at updated position
        vec3 grav_acc2 = gravity_at(p_new, st);
        vec3 v_new = v_half + grav_acc2 * hdt;

        pos[i] = vec4(p_new, pos[i].w);
        vel[i] = vec4(v_new, 0.0);
        acc[i] = vec4(grav_acc, 0.0);

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

    // EVERY invocation reaches both barriers — including the last partial
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
