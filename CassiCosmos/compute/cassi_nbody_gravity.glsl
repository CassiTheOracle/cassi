#[compute]
#version 450
// Cassi N-body gravity — O(N) enclosed-mass Plummer + field-coupled G_eff.
//
// Each thread integrates one particle via KDK leapfrog.  The gravitational
// constant is modulated by the two-fluid Q field sampled at the particle's
// position:  G_eff = G_N * (1 + xi * q_sample).
//
// Buffer layout (agreed with cassi_two_fluid.glsl and cassi_sim.gd):
//   SET 0 — field grid (EY, EI, Q as float[N^3], Vel as vec4[N^3])
//   SET 1 — particles  (Positions, Velocities, Accels as vec4[N_particles])
//   SET 2 — aux / BH   (vec4[4] — M_total, G_N, cluster_a, grid_extent)

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

// ── SET 0: Field grid ──────────────────────────────────────────────────
layout(set = 0, binding = 0, std430) buffer FieldEY  { float ey[];  };
layout(set = 0, binding = 1, std430) buffer FieldEI  { float ei[];  };
layout(set = 0, binding = 2, std430) buffer FieldQ   { float qv[];  };
layout(set = 0, binding = 3, std430) buffer FieldVel { vec4  fvel[]; };
layout(set = 1, binding = 0, std430) buffer Positions  { vec4 pos[]; };
layout(set = 1, binding = 1, std430) buffer Velocities { vec4 vel[]; };
layout(set = 1, binding = 2, std430) buffer Accels     { vec4 acc[]; };
layout(set = 2, binding = 0, std430) buffer BHData { vec4 bh[4]; };

// ── Push constants (matches cassi_two_fluid.glsl exactly) ──────────────
layout(push_constant, std430) uniform PC {
    float N_f;             // grid resolution per dimension
    float dt;              // simulation timestep
    float t;               // current elapsed time
    float phi;             // golden ratio
    float xi;              // Cassi Qi coupling
    float eps2;            // gravity softening squared
    float particle_N;      // number of particles
    float mode;            // visualization mode (unused here)
    float source_strength; // (unused here — field shader uses this)
    float _pad;
} pc;

// ── Grid index helper (matches cassi_two_fluid.glsl) ───────────────────
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

// ── Trilinear Q-field sample at a world-space position ─────────────────
// Maps particle position to fractional grid coordinates, then performs
// trilinear interpolation with periodic wrap (matching the field solver).
float sample_q(vec3 world_pos) {
    int N = int(pc.N_f);
    float half = float(N) * 0.5;
    float extent = bh[2].y;  // grid_extent: world half-width mapping to grid

    // Map world → grid fractional coords
    // Grid center (half, half, half) corresponds to world origin.
    float inv_extent = (extent > 0.0001) ? (1.0 / extent) : 1.0;
    vec3 gc = (world_pos * inv_extent) * half + half;

    // Integer cell coords (floor)
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));

    // Fractional part
    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);

    // Periodic wrap
    i0 = ((i0 % N) + N) % N;
    j0 = ((j0 % N) + N) % N;
    k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;
    int j1 = (j0 + 1) % N;
    int k1 = (k0 + 1) % N;

    // 8-corner trilinear interpolation
    float q000 = qv[idx3(i0, j0, k0)];
    float q100 = qv[idx3(i1, j0, k0)];
    float q010 = qv[idx3(i0, j1, k0)];
    float q110 = qv[idx3(i1, j1, k0)];
    float q001 = qv[idx3(i0, j0, k1)];
    float q101 = qv[idx3(i1, j0, k1)];
    float q011 = qv[idx3(i0, j1, k1)];
    float q111 = qv[idx3(i1, j1, k1)];

    float q00 = mix(q000, q100, fx);
    float q10 = mix(q010, q110, fx);
    float q01 = mix(q001, q101, fx);
    float q11 = mix(q011, q111, fx);

    float q0 = mix(q00, q10, fy);
    float q1 = mix(q01, q11, fy);

    return mix(q0, q1, fz);
}

// ── Enclosed-mass Plummer model ────────────────────────────────────────
// M_enc(r) = M_total * r^3 / (r^2 + a^2)^(3/2)
float enclosed_mass(float r, float r2) {
    float a = bh[2].x;  // cluster_a (Plummer softening radius)
    float a2 = a * a;
    float M_total = bh[0].w;

    float r2a = r2 + a2;
    float denom = r2a * sqrt(r2a);  // (r^2 + a^2)^(3/2)
    return M_total * (r2 * r) / max(denom, 1e-5);
}

// ── Main kernel ────────────────────────────────────────────────────────
void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    if (i >= N) return;

    // Read particle state
    vec4 p = pos[i];
    vec4 v = vel[i];
    vec3 pxyz = p.xyz;
    vec3 vxyz = v.xyz;

    float dt_val = pc.dt;
    float hdt = dt_val * 0.5;
    float G_N = bh[1].w;
    float xi_val = pc.xi;

    // ── Single-step KDK leapfrog ───────────────────────────────────────
    // (The GD script dispatches once per physics tick; sub-stepping, if
    //  desired, is handled by calling dispatch multiple times.)

    // 1. Sample Q field at particle position for spatially-varying G
    float q_sample = sample_q(pxyz);
    float G_eff = G_N * (1.0 + xi_val * q_sample);

    // 2. Compute radial distance with softening
    float r2 = dot(pxyz, pxyz);
    float r = sqrt(r2 + pc.eps2);

    // 3. Enclosed mass (Plummer model)
    float M_enc = enclosed_mass(r, r2);

    // 4. Gravitational acceleration magnitude
    float inv_r = 1.0 / max(r, 1e-5);
    float f_mag = G_eff * M_enc / max(r2 + pc.eps2, 1e-5);

    vec3 grav_acc = -f_mag * pxyz * inv_r;

    // 5. KDK: half-kick (velocity update)
    vec3 v_half = vxyz + grav_acc * hdt;

    // 6. Drift (position update)
    vec3 p_new = pxyz + v_half * dt_val;

    // 7. Re-evaluate G_eff at new position for second half-kick
    float q_sample2 = sample_q(p_new);
    float G_eff2 = G_N * (1.0 + xi_val * q_sample2);

    float r2_new = dot(p_new, p_new);
    float r_new = sqrt(r2_new + pc.eps2);
    float M_enc2 = enclosed_mass(r_new, r2_new);
    float inv_r2 = 1.0 / max(r_new, 1e-5);
    float f_mag2 = G_eff2 * M_enc2 / max(r2_new + pc.eps2, 1e-5);
    vec3 grav_acc2 = -f_mag2 * p_new * inv_r2;

    // 8. Second half-kick
    vec3 v_new = v_half + grav_acc2 * hdt;

    // ── Write back ─────────────────────────────────────────────────────
    pos[i] = vec4(p_new, 1.0);
    vel[i] = vec4(v_new, 0.0);
    acc[i] = vec4(grav_acc, 0.0);
}
