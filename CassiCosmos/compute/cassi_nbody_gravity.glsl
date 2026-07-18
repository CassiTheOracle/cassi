#[compute]
#version 450
// Cassi N-body Gravity — KDK leapfrog with Cassi G_eff and multi-center Plummer
// Uses enclosed-mass Plummer model connected to two-fluid Qi field

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer FieldEY { float ey[]; };
layout(set = 0, binding = 1, std430) readonly buffer FieldEI { float ei[]; };
layout(set = 0, binding = 2, std430) readonly buffer FieldQ  { float qv[]; };
layout(set = 0, binding = 3, std430) readonly buffer FieldVel { vec4 vel[]; };

layout(set = 1, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 1, binding = 1, std430) restrict buffer Velocities { vec4 vel[]; };
layout(set = 1, binding = 2, std430) restrict buffer Accelerations { vec4 acc[]; };

layout(set = 2, binding = 0, std430) buffer BHData { vec4 bh[4]; };
layout(set = 2, binding = 1, std430) restrict readonly buffer ClusterCenters {
    vec4 clusters[];  // .xyz = position, .w = M_total
};

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

// ── Trilinear sample of Qi field ───────────────────────────────────────
float sample_q(vec3 wp) {
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

    float q000 = qv[idx3(i0, j0, k0)];
    float q100 = qv[idx3(i1, j0, k0)];
    float q010 = qv[idx3(i0, j1, k0)];
    float q110 = qv[idx3(i1, j1, k0)];
    float q001 = qv[idx3(i0, j0, k1)];
    float q101 = qv[idx3(i1, j0, k1)];
    float q011 = qv[idx3(i0, j1, k1)];
    float q111 = qv[idx3(i1, j1, k1)];

    float q0 = mix(mix(q000, q100, fx), mix(q010, q110, fx), fy);
    float q1 = mix(mix(q001, q101, fx), mix(q011, q111, fx), fy);
    return mix(q0, q1, fz);
}

// ── Multi-center Plummer gravity ──────────────────────────────────────
vec3 compute_grav(vec3 p, float G_eff, float eps2) {
    vec3 grav = vec3(0.0);
    int nc = int(pc.num_clusters);
    float a = bh[2].x;
    float a2 = a * a;
    for (int c = 0; c < nc; c++) {
        vec3 dc = p - clusters[c].xyz;
        float dist2 = dot(dc, dc) + eps2;
        float dist = sqrt(dist2);
        float Mc = clusters[c].w;
        float r2a = dist2 + a2;
        float denom = r2a * sqrt(r2a);
        float M_enc = Mc * (dist2 * dist) / max(denom, 1e-5);
        float f_mag = G_eff * M_enc / max(dist2, 1e-5);
        grav -= f_mag * dc / max(dist, 1e-5);
    }
    return grav;
}

// ── KDK leapfrog main kernel ──────────────────────────────────────────
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
    float eps2 = pc.eps2;

    // ── Half-step kick ─────────────────────────────────────────────────
    float q_s = sample_q(pxyz);
    float pi_over_rho = ((pc.phi - 1.0) / (pc.phi + 1.0)) + q_s * 0.7;
    pi_over_rho = clamp(pi_over_rho, 0.0, 0.72);
    float G_eff = G_N * pi_over_rho * (1.0 + xi_val * q_s);
    vec3 grav_acc = compute_grav(pxyz, G_eff, eps2);

    vec3 v_half = vxyz + grav_acc * hdt;
    vec3 p_new = pxyz + v_half * dt_val;

    // ── Full-step kick ─────────────────────────────────────────────────
    float q_s2 = sample_q(p_new);
    float pi_over_rho2 = ((pc.phi - 1.0) / (pc.phi + 1.0)) + q_s2 * 0.7;
    pi_over_rho2 = clamp(pi_over_rho2, 0.0, 0.72);
    float G_eff2 = G_N * pi_over_rho2 * (1.0 + xi_val * q_s2);
    vec3 grav_acc2 = compute_grav(p_new, G_eff2, eps2);

    vec3 v_new = v_half + grav_acc2 * hdt;

    pos[i] = vec4(p_new, pos[i].w);
    vel[i] = vec4(v_new, 0.0);
    acc[i] = vec4(grav_acc, 0.0);
}
