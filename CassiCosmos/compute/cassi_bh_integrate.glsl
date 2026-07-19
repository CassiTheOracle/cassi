#[compute]
#version 450
// Cassi BH Integration — updates tracked BH positions and masses each step
//
// - Integrates position: p += v * dt
// - Grows mass: m += acc_rate * qi_local * cell_vol
// - Ages: age += 1
// - Expired BHs (age > max_age) get zeroed out
//
// Dispatched every step, before nbody gravity.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// ── Field grid (read-only) ─────────────────────────────────────────────
layout(set = 0, binding = 0, std430) readonly buffer FieldQ { float qv[]; };

// ── BH tracking buffer (read-write) ────────────────────────────────────
// bh[0].x       = count
// bh[1].w       = G_N (read-only)
// bh[2].y       = extent (read-only)
// bh[4..33]     = BH records (vec4[2] each)
layout(set = 1, binding = 0, std430) buffer BHData {
    vec4 bh[34];
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float acc_rate;    // mass growth rate per step
    float max_age;     // steps before BH expires (0 = immortal)
} pc;

int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

void main() {
    int slot = int(gl_GlobalInvocationID.x);
    uint count = bh[0].x;
    if (slot >= int(count) || slot >= 16) return;

    int base = 4 + slot * 2;
    vec4 rec0 = bh[base];     // (pos.xyz, mass)
    vec4 rec1 = bh[base + 1]; // (vel.xyz, _pad)

    vec3 pos = rec0.xyz;
    float mass = rec0.w;
    vec3 vel = rec1.xyz;

    // ── Integrate position ─────────────────────────────────────────────
    pos += vel * pc.dt;

    // ── Read Qi at current position (for mass growth) ─────────────────
    float extent = bh[2].y;
    int N = int(pc.N_f);
    vec3 gc = (pos / extent) * float(N);
    int ci = clamp(int(floor(gc.x)), 0, N - 1);
    int cj = clamp(int(floor(gc.y)), 0, N - 1);
    int ck = clamp(int(floor(gc.z)), 0, N - 1);
    float qi_local = qv[idx3(ci, cj, ck)];

    // ── Grow mass from field density ───────────────────────────────────
    float cell_vol = pow(extent / float(N), 3.0);
    mass += pc.acc_rate * qi_local * cell_vol;

    // ── Age and expire ─────────────────────────────────────────────────
    float age = rec0.w == 0.0 && mass > 0.0 ? 1.0 : rec0.w + 1.0;
    // (First call: mass > 0 but age = 0 from nucleation → set to 1)
    if (pc.max_age > 0.0 && age > pc.max_age) {
        bh[base] = vec4(0.0);     // zero out
        bh[base + 1] = vec4(0.0);
        return;
    }

    // ── Write back ─────────────────────────────────────────────────────
    bh[base]     = vec4(pos, mass);
    bh[base + 1] = vec4(vel, 0.0, 0.0);
}
