#[compute]
// Explicit old/new two-fluid update. Set 0 keeps every read-only field
// separate from every output so the spatial stencil always samples one
// complete old-time state. The host swaps the old/new uniform sets only
// after the dispatch barrier.
#version 450

layout(local_size_x = 4, local_size_y = 4, local_size_z = 4) in;

// Set 0 — old state, outputs, source, and field-intelligence state.
// Bindings 0..2 and 10 are read-only old state. Bindings 3..6 and 11 are
// write-only/new state. The old/new resources MUST NOT alias in one dispatch.
layout(set = 0, binding = 0, std430) readonly buffer OldFieldEY { float ey_old[]; };
layout(set = 0, binding = 1, std430) readonly buffer OldFieldEI { float ei_old[]; };
layout(set = 0, binding = 2, std430) readonly buffer OldFieldVel { vec4 vel_old[]; };
layout(set = 0, binding = 3, std430) writeonly buffer NewFieldEY { float ey_new[]; };
layout(set = 0, binding = 4, std430) writeonly buffer NewFieldEI { float ei_new[]; };
layout(set = 0, binding = 5, std430) buffer NewFieldQ { float q_new[]; };
layout(set = 0, binding = 6, std430) buffer NewFieldVel { vec4 vel_new[]; };
layout(set = 0, binding = 7, std430) readonly buffer MassDensity { float rho[]; };
layout(set = 0, binding = 8, std430) readonly buffer FieldPlasticity { vec2 pe[]; };
layout(set = 0, binding = 9, std430) readonly buffer FieldLearningState {
    vec4 learn_metrics;
    vec4 learn_target;
    vec4 learn_probe;
    vec4 learn_organ;
    vec4 learn_control;
    vec4 learn_context;
    uvec4 learn_status;
    uvec4 learn_flags;
};
// FI keeps the canonical scratch tuple (EY, EI, vx, vy) in the derivative
// pair. Its next update consumes tuple x/y exactly as the legacy pass does;
// NewFieldVel remains the bounded embodied transport exposed to consumers.
layout(set = 0, binding = 10, std430) readonly buffer OldFieldDerivative { vec4 deriv_old[]; };
layout(set = 0, binding = 11, std430) writeonly buffer NewFieldDerivative { vec4 deriv_new[]; };

layout(push_constant, std430) uniform PC {
    float N_f; float dt; float t; float phi;
    float xi; float eps2; float particle_N;
    float mode; float source_strength; float num_clusters;
    float gravity_mode;
    float extent_x; float extent_y; float extent_z;
    float reserved;       // retained slot 14; must be 0 for this entrypoint
    float omega2;         // ω₀²
    float ham_completion; // >0.5 applies φ to the EI coupling row
} pc;

int idx3(int i, int j, int k) {
    int n = int(pc.N_f);
    return i + n * (j + n * k);
}

float lap_ey_at(int i, int j, int k) {
    int n = int(pc.N_f);
    int ip = (i + 1) % n; int im = (i - 1 + n) % n;
    int jp = (j + 1) % n; int jm = (j - 1 + n) % n;
    int kp = (k + 1) % n; int km = (k - 1 + n) % n;
    float hn = float(n) * 0.5;
    float hx = pc.extent_x / hn;
    float hy = pc.extent_y / hn;
    float hz = pc.extent_z / hn;
    float h0 = min(min(pc.extent_x, pc.extent_y), pc.extent_z) / hn;
    float hx2 = hx * hx; float hy2 = hy * hy; float hz2 = hz * hz; float h02 = h0 * h0;
    float bxy = (1.0 / 3.0) * h02 / (hx2 + hy2);
    float bxz = (1.0 / 3.0) * h02 / (hx2 + hz2);
    float byz = (1.0 / 3.0) * h02 / (hy2 + hz2);
    float ax = h02 / hx2 - 2.0 * (bxy + bxz);
    float ay = h02 / hy2 - 2.0 * (bxy + byz);
    float az = h02 / hz2 - 2.0 * (bxz + byz);
    float e = ey_old[idx3(i, j, k)];
    float axis_x = ey_old[idx3(ip, j, k)] + ey_old[idx3(im, j, k)] - 2.0 * e;
    float axis_y = ey_old[idx3(i, jp, k)] + ey_old[idx3(i, jm, k)] - 2.0 * e;
    float axis_z = ey_old[idx3(i, j, kp)] + ey_old[idx3(i, j, km)] - 2.0 * e;
    float fd_xy = ey_old[idx3(ip, jp, k)] + ey_old[idx3(im, jp, k)]
                + ey_old[idx3(ip, jm, k)] + ey_old[idx3(im, jm, k)] - 4.0 * e;
    float fd_xz = ey_old[idx3(ip, j, kp)] + ey_old[idx3(im, j, kp)]
                + ey_old[idx3(ip, j, km)] + ey_old[idx3(im, j, km)] - 4.0 * e;
    float fd_yz = ey_old[idx3(i, jp, kp)] + ey_old[idx3(i, jm, kp)]
                + ey_old[idx3(i, jp, km)] + ey_old[idx3(i, jm, km)] - 4.0 * e;
    return ax * axis_x + ay * axis_y + az * axis_z
         + bxy * fd_xy + bxz * fd_xz + byz * fd_yz;
}

float lap_ei_at(int i, int j, int k) {
    int n = int(pc.N_f);
    int ip = (i + 1) % n; int im = (i - 1 + n) % n;
    int jp = (j + 1) % n; int jm = (j - 1 + n) % n;
    int kp = (k + 1) % n; int km = (k - 1 + n) % n;
    float hn = float(n) * 0.5;
    float hx = pc.extent_x / hn;
    float hy = pc.extent_y / hn;
    float hz = pc.extent_z / hn;
    float h0 = min(min(pc.extent_x, pc.extent_y), pc.extent_z) / hn;
    float hx2 = hx * hx; float hy2 = hy * hy; float hz2 = hz * hz; float h02 = h0 * h0;
    float bxy = (1.0 / 3.0) * h02 / (hx2 + hy2);
    float bxz = (1.0 / 3.0) * h02 / (hx2 + hz2);
    float byz = (1.0 / 3.0) * h02 / (hy2 + hz2);
    float ax = h02 / hx2 - 2.0 * (bxy + bxz);
    float ay = h02 / hy2 - 2.0 * (bxy + byz);
    float az = h02 / hz2 - 2.0 * (bxz + byz);
    float e = ei_old[idx3(i, j, k)];
    float axis_x = ei_old[idx3(ip, j, k)] + ei_old[idx3(im, j, k)] - 2.0 * e;
    float axis_y = ei_old[idx3(i, jp, k)] + ei_old[idx3(i, jm, k)] - 2.0 * e;
    float axis_z = ei_old[idx3(i, j, kp)] + ei_old[idx3(i, j, km)] - 2.0 * e;
    float fd_xy = ei_old[idx3(ip, jp, k)] + ei_old[idx3(im, jp, k)]
                + ei_old[idx3(ip, jm, k)] + ei_old[idx3(im, jm, k)] - 4.0 * e;
    float fd_xz = ei_old[idx3(ip, j, kp)] + ei_old[idx3(im, j, kp)]
                + ei_old[idx3(ip, j, km)] + ei_old[idx3(im, j, km)] - 4.0 * e;
    float fd_yz = ei_old[idx3(i, jp, kp)] + ei_old[idx3(i, jm, kp)]
                + ei_old[idx3(i, jp, km)] + ei_old[idx3(i, jm, km)] - 4.0 * e;
    return ax * axis_x + ay * axis_y + az * axis_z
         + bxy * fd_xy + bxz * fd_xz + byz * fd_yz;
}

float source_ey(int i, int j, int k) {
    int n = int(pc.N_f);
    float halfn = float(n) * 0.5;
    float dx = (float(i) - halfn) / halfn;
    float dy = (float(j) - halfn) / halfn;
    float dz = (float(k) - halfn) / halfn;
    float r2 = dx * dx + dy * dy + dz * dz;
    float s = pc.source_strength;
    float mr = rho[idx3(i, j, k)];
    return s * exp(-r2 * 4.0) + mr * 0.001;
}

float source_ei(int i, int j, int k) {
    int n = int(pc.N_f);
    float halfn = float(n) * 0.5;
    float dx = (float(i) - halfn * 0.7) / halfn;
    float dy = (float(j) - halfn * 0.8) / halfn;
    float dz = (float(k) - halfn * 0.6) / halfn;
    float r2 = dx * dx + dy * dy + dz * dz;
    float s = pc.source_strength * 0.707;
    float mr = rho[idx3(i, j, k)] * 0.707;
    return s * exp(-r2 * 4.0) + mr * 0.001;
}

vec3 learned_cell_world(int i, int j, int k) {
    float halfn = float(int(pc.N_f)) * 0.5;
    return vec3((float(i) - halfn) / halfn * pc.extent_x,
                (float(j) - halfn) / halfn * pc.extent_y,
                (float(k) - halfn) / halfn * pc.extent_z);
}

float learned_source(int i, int j, int k) {
    vec3 command = clamp(learn_control.xyz, vec3(-8.0), vec3(8.0));
    float amplitude = length(command);
    if (amplitude <= 1e-8) return 0.0;
    vec3 lobe = learn_organ.xyz + command / amplitude * learn_organ.w;
    float sigma = max(learn_organ.w * 0.65, 1e-4);
    vec3 delta = learned_cell_world(i, j, k) - lobe;
    return 0.01 * amplitude * exp(-0.5 * dot(delta, delta) / (sigma * sigma));
}

vec3 learned_medium_flow(int i, int j, int k) {
    vec3 command = clamp(learn_control.xyz, vec3(-8.0), vec3(8.0));
    float sigma = max(learn_organ.w * 2.5, 1e-4);
    vec3 delta = learned_cell_world(i, j, k) - learn_organ.xyz;
    return command * exp(-0.5 * dot(delta, delta) / (sigma * sigma));
}

void main() {
    int n = int(pc.N_f);
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    if (gid.x >= n || gid.y >= n || gid.z >= n) return;
    int id = idx3(gid.x, gid.y, gid.z);

    float ey0 = ey_old[id];
    float ei0 = ei_old[id];
    vec4 old_v = vel_old[id];
    vec4 old_d = deriv_old[id];
    bool fi_enabled = learn_status.x != 0u;
    vec4 dsrc = fi_enabled ? old_d : old_v;
    float coupling = ey0 - pc.phi * ei0;
    float acc_ey = lap_ey_at(gid.x, gid.y, gid.z) - pc.omega2 * coupling;
    float acc_ei = lap_ei_at(gid.x, gid.y, gid.z)
                 + (pc.ham_completion > 0.5 ? pc.phi * pc.omega2 : pc.omega2) * coupling;
    float vx = dsrc.x + acc_ey * pc.dt;
    float vy = dsrc.y + acc_ei * pc.dt;
    float ey1 = ey0 + vx * pc.dt + source_ey(gid.x, gid.y, gid.z) * pc.dt * pc.dt;
    float ei1 = ei0 + vy * pc.dt + source_ei(gid.x, gid.y, gid.z) * pc.dt * pc.dt;
    if (learn_status.x != 0u) {
        float pulse = learned_source(gid.x, gid.y, gid.z) * pc.dt * pc.dt;
        vx = clamp(vx, -8.0, 8.0);
        vy = clamp(vy, -8.0, 8.0);
        ey1 = clamp(ey1 + pulse, -8.0, 8.0);
        ei1 = clamp(ei1 + pulse * 0.7071067811865476, -8.0, 8.0);
    }
    ey_new[id] = ey1;
    ei_new[id] = ei1;
    q_new[id] = ey1 * ey1 + ei1 * ei1;
    float eps = ey1 - pc.phi * ei1;
    float eps_sq = eps * eps;
    if (learn_status.x != 0u) {
        vel_new[id] = vec4(clamp(learned_medium_flow(gid.x, gid.y, gid.z),
                                  vec3(-8.0), vec3(8.0)), eps_sq);
    } else {
        vel_new[id] = vec4(vx, vy, 0.0, eps_sq);
    }
    deriv_new[id] = fi_enabled ? vec4(ey1, ei1, vx, vy) : vec4(vx, vy, 0.0, eps_sq);
}
