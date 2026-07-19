#[compute]
#version 450
// Cassi Condensation Scanner — finds Qi peaks, nucleates black holes
//
// Scans the Qi field grid; when a cell exceeds the condensation
// threshold, records a BH candidate in the BHData buffer.
// Uses an atomic counter to claim slots without races.
//
// Throttled: dispatched once every ~100 steps from cassi_sim.gd.
// BH lifetime is maintained in _bh_integrate (separate dispatch every step).

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// ── Field grid (read-only) ─────────────────────────────────────────────
layout(set = 0, binding = 0, std430) readonly buffer FieldQ { float qv[]; };

// ── BH tracking buffer (write) ─────────────────────────────────────────
// bh[0].x       = count (atomic uint)
// bh[1].w       = G_N (read-only, set by sim_ui)
// bh[2].y       = extent (read-only, set by sim_ui)
// bh[4..33]     = tracked BH records (vec4[2] each = 32 bytes)
//   record.xy   = position (world coords)
//   record.z    = mass (Qi density × cell volume)
//   record.w    = age in steps (0 at nucleation)
//   record2.xy  = velocity (initialized to zero)
//   record2.zw  = unused
layout(set = 1, binding = 0, std430) buffer BHData {
    vec4 bh[34];
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float qi_threshold;   // condensation threshold for Qi
    float _pad0;
    float _pad1;
} pc;

// ── Index helpers ──────────────────────────────────────────────────────
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

int cell_x(int idx) { return idx % int(pc.N_f); }
int cell_y(int idx) { return (idx / int(pc.N_f)) % int(pc.N_f); }
int cell_z(int idx) { return idx / (int(pc.N_f) * int(pc.N_f)); }

void main() {
    int total = int(pc.N_f) * int(pc.N_f) * int(pc.N_f);
    int gid = int(gl_GlobalInvocationID.x);
    if (gid >= total) return;

    // Read Qi at this cell
    float qval = qv[gid];

    if (qval <= pc.qi_threshold) return;

    // ── Write BH record via atomic counter ─────────────────────────────
    uint slot = atomicAdd(bh[0].x, 1u);

    if (slot >= 15u) return;  // max 16 BHs (slots 0–15)

    // Cell center in world coordinates
    float extent = bh[2].y;
    int N = int(pc.N_f);
    int cx = cell_x(gid);
    int cy = cell_y(gid);
    int cz = cell_z(gid);
    vec3 world_pos = (vec3(cx, cy, cz) + 0.5) / float(N) * extent;

    // BH mass proxy: Qi density × cell volume
    float cell_vol = pow(extent / float(N), 3.0);
    float mass = qval * cell_vol;

    int base = 4 + int(slot) * 2;
    bh[base]     = vec4(world_pos, mass, 0.0);   // position + mass
    bh[base + 1] = vec4(0.0, 0.0, 0.0, 0.0);    // velocity (start at rest)
}
