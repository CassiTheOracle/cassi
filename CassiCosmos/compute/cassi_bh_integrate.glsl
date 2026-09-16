#[compute]
#version 450

// Standalone module: local finiteness helpers (GLSL has no includes).
bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
bool finite_vec3(vec3 value) { return !(any(isnan(value)) || any(isinf(value))); }
// GL_EXT_shader_atomic_float: the mass ledger slots bh[34]/bh[35] are
// atomicAdd'ed from here (same extension/GPU as cassi_bh_accretion.glsl).
#extension GL_EXT_shader_atomic_float : require
// Cassi BH Integration — updates tracked BH positions and masses each step
//
// Processes all 15 BH slots (0-14). A slot with mass > 0 is active.
// - Integrates position: p += v * dt
// - Grows mass: m += acc_rate * qi_local * cell_vol, capped at a mass-
//   proportional rate (Eddington-like, pc.edd_k) and booked into the
//   CREATED ledger. The knob DEFAULTS OFF (bh_acc_rate = 0.0): the growth
//   is mass manufactured out of a bounded order parameter, not a density,
//   with nothing drained (BH_DYNAMICS_PREREG finding 2) — kept only for
//   experiments.
// - Ages: age += 1
// - Expired BHs (age > max_age) get zeroed out; the erased mass is booked
//   into the EXPIRED ledger.
//
// Dispatch: ONE workgroup. The kernel indexes its records by
// gl_GlobalInvocationID.x alone, so the cube convention the 4^3-cell
// kernels need made every (y,z) workgroup repeat the same racy
// read-modify-write (BH_DYNAMICS_PREREG finding 5/F).
//
// Mass ledger (bh[34]; BH_DYNAMICS_PREREG C/J):
//   x = created mass (q-growth), y = expired/retired mass,
//   z = mass absorbed from particles (cassi_bh_accretion.glsl),
//   w = reserved. bh[35].z counts non-finite retirements.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer FieldQ { float qv[]; };

// bh[1].w = G_N, bh[2].yzw = per-axis box half-extents (GRID_LAYOUT.md),
// bh[4..33] = BH records (vec4[2] each, max 15), bh[34]/bh[35] = ledger.
// coherent: the ledger slots are atomicAdd'ed here and by the other BH
// passes.
layout(set = 1, binding = 0, std430) coherent buffer BHData {
    vec4 bh[36];
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float acc_rate;    // mass growth per step (0.0 = OFF, the default)
    float max_age;     // steps before expiry (0 = immortal)
    float edd_k;       // growth ceiling: dm <= edd_k · M · dt (Eddington-like)
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
    if (!(mass > 0.0)) return;  // slot empty
    // Retire a record whose state has gone non-finite instead of persisting it.
    vec3 record_pos = bh[base].xyz;
    vec3 record_vel = bh[base + 1].xyz;
    if (!finite_float(mass) || !finite_vec3(record_pos)
            || !finite_vec3(record_vel) || !finite_float(bh[base + 1].w)) {
        // The whole record leaves the sector: book a finite mass as
        // EXPIRED (a non-finite one cannot enter an accumulator) and count
        // the retirement itself.
        if (finite_float(mass)) atomicAdd(bh[34].y, mass);
        atomicAdd(bh[35].z, 1.0);
        bh[base] = vec4(0.0);
        bh[base + 1] = vec4(0.0);
        return;
    }

    vec3 pos = record_pos;
    vec3 vel = record_vel;
    float age = bh[base + 1].w;

    // Integrate position
    pos += vel * pc.dt;
    age += 1.0;

    // Read Qi at the record's own position for mass growth (per-axis world
    // map, window-relative and floor-safe — the SAME map the deposit writes
    // with: gc = (pos − window_origin)·(N/2)/extent + N/2, wrapped by the
    // floor-safe modulo the deposit/condensation use). The previous form
    // ignored bh[0].yzw and clamped a NEGATIVE index to cell 0, so a record
    // left of the window origin sampled the wrong cell.
    vec3 ext = bh[2].yzw;
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    vec3 scale = (ext.x > 0.0) ? (hn / max(ext, vec3(0.001))) : vec3(hn);
    vec3 gc = (pos - bh[0].yzw) * scale + hn;
    int ci = ((int(floor(gc.x)) % N) + N) % N;
    int cj = ((int(floor(gc.y)) % N) + N) % N;
    int ck = ((int(floor(gc.z)) % N) + N) % N;
    float qi_local = qv[idx3(ci, cj, ck)];

    // Grow mass from field density (per-axis cell volume: V = Π extent_i/N)
    float cell_vol = max(ext.x / float(N), 0.001)
                   * max(ext.y / float(N), 0.001)
                   * max(ext.z / float(N), 0.001);
    float dm = pc.acc_rate * qi_local * cell_vol;
    // Eddington-like ceiling: growth can never outrun a mass-proportional
    // rate. No-op while the growth knob is off (dm == 0).
    if (dm > 0.0) dm = min(dm, max(pc.edd_k, 0.0) * mass * pc.dt);
    mass += dm;
    // Ledger: mass that appeared from nowhere (dm > 0) or was drained by
    // the knob (dm < 0). Exact no-op at the default acc_rate = 0.0.
    if (finite_float(dm) && dm != 0.0) {
        if (dm > 0.0) atomicAdd(bh[34].x, dm);
        else atomicAdd(bh[34].y, -dm);
    }
    // The growth sample can poison the record (a non-finite qi_local): retire
    // it HERE, so a non-finite record is never written back. A finite mass
    // is impossible to lose this way (mass > 0 at entry, dm == 0 at the
    // default acc_rate).
    if (!finite_float(mass)) {
        atomicAdd(bh[35].z, 1.0);
        bh[base]     = vec4(0.0);
        bh[base + 1] = vec4(0.0);
        return;
    }

    // Expire if too old
    if (pc.max_age > 0.0 && age > pc.max_age) {
        if (finite_float(mass)) atomicAdd(bh[34].y, mass);
        bh[base]     = vec4(0.0);
        bh[base + 1] = vec4(0.0);
        return;
    }

    bh[base]     = vec4(pos, mass);
    bh[base + 1] = vec4(vel, age);
}
