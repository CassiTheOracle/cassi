#[compute]
#version 450
// Cassi N-body gravity — O(N) enclosed-mass Plummer + field-coupled G_eff.
// Each thread integrates one particle via KDK leapfrog.
// G_eff = G_N * (1 + xi * sample_Q(r)) from the two-fluid field.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

// SET 0: Field grid
layout(set = 0, binding = 0, std430) buffer FieldEY  { float ey[];  };
layout(set = 0, binding = 1, std430) buffer FieldEI  { float ei[];  };
layout(set = 0, binding = 2, std430) buffer FieldQ   { float qv[];  };
layout(set = 0, binding = 3, std430) buffer FieldVel { vec4  fvel[]; };

// SET 1: Particles
layout(set = 1, binding = 0, std430) buffer Positions  { vec4 pos[]; };
layout(set = 1, binding = 1, std430) buffer Velocities { vec4 vel[]; };
layout(set = 1, binding = 2, std430) buffer Accels     { vec4 acc[]; };

// SET 2: Auxiliary / BH data
layout(set = 2, binding = 0, std430) buffer BHData { vec4 bh[4]; };

// Push constants
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
    float _pad;
} pc;

// Grid index helper
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

// Trilinear Q-field sample at world-space position
float sample_q(vec3 wp) {
    int N = int(pc.N_f);
    float half = float(N) * 0.5;
    float extent = bh[2].y;
    float inv_ext = (extent > 0.0001) ? (1.0 / extent) : 1.0;
    vec3 gc = (wp * inv_ext) * half + half;

    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));

    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);

    i0 = ((i0 % N) + N) % N;
    j0 = ((j0 % N) + N) % N;
    k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;
    int j1 = (j0 + 1) % N;
    int k1 = (k0 + 1) % N;

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

// Enclosed-mass Plummer model
float enclosed_mass(float r, float r2) {
    float a = bh[2].x;
    float a2 = a * a;
    float M_total = bh[0].w;
    float r2a = r2 + a2;
    float denom = r2a * sqrt(r2a);
    return M_total * (r2 * r) / max(denom, 1e-5);
}

void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    if (i >= N) return;

    // Read state
    vec3 pxyz = pos[i].xyz;
    vec3 vxyz = vel[i].xyz;
    float G_N = bh[1].w;
    float xi_val = pc.xi;
    float dt_val = pc.dt;
    float hdt = dt_val * 0.5;
    float eps2 = pc.eps2;

    // Step 1: sample Q at current position
    float q_s = sample_q(pxyz);
    float G_eff = G_N * (1.0 + xi_val * q_s);

    // Step 2: radial distance
    float r2 = dot(pxyz, pxyz);
    float r = sqrt(r2 + eps2);

    // Step 3: enclosed mass
    float M_enc = enclosed_mass(r, r2);

    // Step 4: gravitational acceleration
    float inv_r = 1.0 / max(r, 1e-5);
    float f_mag = G_eff * M_enc / max(r2 + eps2, 1e-5);
    vec3 grav_acc = -f_mag * pxyz * inv_r;

    // Step 5: KDK leapfrog — half kick
    vec3 v_half = vxyz + grav_acc * hdt;

    // Step 6: drift
    vec3 p_new = pxyz + v_half * dt_val;

    // Step 7: re-evaluate at new position
    float r2n = dot(p_new, p_new);
    float rn = sqrt(r2n + eps2);
    float q_s2 = sample_q(p_new);
    float G_eff2 = G_N * (1.0 + xi_val * q_s2);
    float M_enc2 = enclosed_mass(rn, r2n);
    float inv_r2 = 1.0 / max(rn, 1e-5);
    float f_mag2 = G_eff2 * M_enc2 / max(r2n + eps2, 1e-5);
    vec3 grav_acc2 = -f_mag2 * p_new * inv_r2;

    // Step 8: second half kick
    vec3 v_new = v_half + grav_acc2 * hdt;

    // Write back
    pos[i] = vec4(p_new, 1.0);
    vel[i] = vec4(v_new, 0.0);
    acc[i] = vec4(grav_acc, 0.0);
}
