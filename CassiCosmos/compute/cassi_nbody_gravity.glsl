#[compute]
#version 450
// Cassi N-body Gravity — pure field-driven (no Plummer model)
// Gravity emerges from the gradient of the Qi field: F = -G_N · ∇q
// G_eff still modulates via pi/rho density screening.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer FieldEY { float ey[]; };
layout(set = 0, binding = 1, std430) readonly buffer FieldEI { float ei[]; };
layout(set = 0, binding = 2, std430) readonly buffer FieldQ  { float qv[]; };
layout(set = 0, binding = 3, std430) readonly buffer FieldVel { vec4 fvel[]; };
layout(set = 0, binding = 4, std430) readonly buffer MassDensity { uint rho[]; };

layout(set = 1, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 1, binding = 1, std430) restrict buffer Velocities { vec4 vel[]; };
layout(set = 1, binding = 2, std430) restrict buffer Accelerations { vec4 acc[]; };

layout(set = 2, binding = 0, std430) buffer BHData { vec4 bh[4]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float t;
    float phi;
    float xi;
    float eps2;
    float particle_N;
    float mode;
    float source_strength;
    float num_clusters;
} pc;

// ── Index helpers ──────────────────────────────────────────────────────
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

// ── Qi field sample + gradient (same 8 corners, no extra reads) ───────
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
    // Blend mass density into q — bypasses slow PDE source pathway
    float M2Q = 0.01;  // tuning factor: mass density → q contribution
    float r000 = uintBitsToFloat(rho[idx3(i0, j0, k0)]);
    float r100 = uintBitsToFloat(rho[idx3(i1, j0, k0)]);
    float r010 = uintBitsToFloat(rho[idx3(i0, j1, k0)]);
    float r110 = uintBitsToFloat(rho[idx3(i1, j1, k0)]);
    float r001 = uintBitsToFloat(rho[idx3(i0, j0, k1)]);
    float r101 = uintBitsToFloat(rho[idx3(i1, j0, k1)]);
    float r011 = uintBitsToFloat(rho[idx3(i0, j1, k1)]);
    float r111 = uintBitsToFloat(rho[idx3(i1, j1, k1)]);

    float q000 = qv[idx3(i0, j0, k0)] + r000 * M2Q;
    float q100 = qv[idx3(i1, j0, k0)] + r100 * M2Q;
    float q010 = qv[idx3(i0, j1, k0)] + r010 * M2Q;
    float q110 = qv[idx3(i1, j1, k0)] + r110 * M2Q;
    float q001 = qv[idx3(i0, j0, k1)] + r001 * M2Q;
    float q101 = qv[idx3(i1, j0, k1)] + r101 * M2Q;
    float q011 = qv[idx3(i0, j1, k1)] + r011 * M2Q;
    float q111 = qv[idx3(i1, j1, k1)] + r111 * M2Q;

    // Qi value (standard trilinear)
    float q0 = mix(mix(q000, q100, fx), mix(q010, q110, fx), fy);
    float q1 = mix(mix(q001, q101, fx), mix(q011, q111, fx), fy);
    q_val = mix(q0, q1, fz);

    // Qi gradient (finite difference from same 8 corners)
    float dx = extent / hn;  // grid spacing
    float qx_l = mix(mix(q000, q001, fz), mix(q010, q011, fz), fy);
    float qx_r = mix(mix(q100, q101, fz), mix(q110, q111, fz), fy);
    float qy_l = mix(mix(q000, q100, fx), mix(q001, q101, fx), fz);
    float qy_r = mix(mix(q010, q110, fx), mix(q011, q111, fx), fz);
    float qz_l = mix(mix(q000, q100, fx), mix(q010, q110, fx), fy);
    float qz_r = mix(mix(q001, q101, fx), mix(q011, q111, fx), fy);
    q_grad = vec3((qx_r - qx_l), (qy_r - qy_l), (qz_r - qz_l)) / dx;
}

// ── KDK leapfrog with pure Cassi field gravity ────────────────────────
void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    if (i >= N) return;

    vec3 pxyz = pos[i].xyz;
    vec3 vxyz = vel[i].xyz;
    float G_N = bh[1].w;
    float xi_val = pc.xi;
    float dt_val = pc.dt;
    float hdt = dt_val * 0.5;

    // ── Half-step kick ─────────────────────────────────────────────────
    float q_s; vec3 grad_q;
    sample_q_field(pxyz, q_s, grad_q);
    float pi_over_rho = ((pc.phi - 1.0) / (pc.phi + 1.0)) + q_s * 0.7;
    pi_over_rho = clamp(pi_over_rho, 0.0, 0.72);
    vec3 grav_acc = G_N * pi_over_rho * grad_q;

    vec3 v_half = vxyz + grav_acc * hdt;
    vec3 p_new = pxyz + v_half * dt_val;

    // ── Full-step kick ─────────────────────────────────────────────────
    float q_s2; vec3 grad_q2;
    sample_q_field(p_new, q_s2, grad_q2);
    float pi_over_rho2 = ((pc.phi - 1.0) / (pc.phi + 1.0)) + q_s2 * 0.7;
    pi_over_rho2 = clamp(pi_over_rho2, 0.0, 0.72);
    vec3 grav_acc2 = G_N * pi_over_rho2 * grad_q2;

    vec3 v_new = v_half + grav_acc2 * hdt;

    pos[i] = vec4(p_new, pos[i].w);
    vel[i] = vec4(v_new, 0.0);
    acc[i] = vec4(grav_acc, 0.0);
}
