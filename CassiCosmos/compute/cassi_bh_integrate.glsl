#[compute]
#version 450
// Cassi BH Integration — updates tracked BH positions and masses each step
//
// Processes all 15 BH slots (0-14). A slot with mass > 0 is active.
// - Integrates position: p += v * dt
// - Grows mass: m += acc_rate * qi_local * cell_vol
// - Ages: age += 1
// - Expired BHs (age > max_age) get zeroed out

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer FieldQ { float qv[]; };

// bh[1].w = G_N, bh[2].y = extent, bh[4..33] = BH records (vec4[2] each, max 15)
layout(set = 1, binding = 0, std430) buffer BHData {
    vec4 bh[34];
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float acc_rate;    // mass growth per step
    float max_age;     // steps before expiry (0 = immortal)
} pc;

int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

void main() {
    int slot = int(gl_GlobalInvocationID.x);
    if (slot >= 15) return;  // max 15 BHs (slots 0-14)

    int base = 4 + slot * 2;  // max base = 32, base+1 = 33
    float mass = bh[base].w;
    if (mass <= 0.0) return;  // slot empty

    vec3 pos = bh[base].xyz;
    vec3 vel = bh[base + 1].xyz;
    float age = bh[base + 1].w;

    // Integrate position
    pos += vel * pc.dt;
    age += 1.0;

    // Read Qi at current position for mass growth
    float extent = bh[2].y;
    int N = int(pc.N_f);
    vec3 gc = (pos / max(extent, 0.001)) * float(N) + float(N) * 0.5;
    int ci = clamp(int(floor(gc.x)) % N, 0, N - 1);
    int cj = clamp(int(floor(gc.y)) % N, 0, N - 1);
    int ck = clamp(int(floor(gc.z)) % N, 0, N - 1);
    float qi_local = qv[idx3(ci, cj, ck)];

    // Grow mass from field density
    float cell_vol = pow(max(extent / float(N), 0.001), 3.0);
    mass += pc.acc_rate * qi_local * cell_vol;

    // Expire if too old
    if (pc.max_age > 0.0 && age > pc.max_age) {
        bh[base]     = vec4(0.0);
        bh[base + 1] = vec4(0.0);
        return;
    }

    bh[base]     = vec4(pos, mass);
    bh[base + 1] = vec4(vel, age);
}
