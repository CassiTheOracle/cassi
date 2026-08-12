#[compute]
#version 450
// Cassi Condensation Scanner — finds Qi peaks, nucleates black holes
//
// Scans the Qi field grid. When a cell exceeds the condensation
// threshold, writes a BH candidate record to a deterministic slot.
// Slot = thread_id % 15, so multiple detections may overwrite — the
// most massive BH wins in each slot. No atomic counters needed.
//
// Throttled: dispatched once every 100 steps from cassi_sim.gd.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// ── Field grid (read-only) ─────────────────────────────────────────────
layout(set = 0, binding = 0, std430) readonly buffer FieldQ { float qv[]; };

// ── BH tracking buffer (write) ─────────────────────────────────────────
// bh[0].x       = unused (was atomic counter — removed)
// bh[1].w       = G_N (read-only, set by sim_ui)
// bh[2].yzw     = per-axis box half-extents (read-only; GRID_LAYOUT.md)
// bh[4..33]     = BH records (vec4[2] each = 32 bytes per BH, max 15)
//   [base].xyz  = position (world coords, [−extent_i, +extent_i] box)
//   [base].w    = mass (Qi density × cell volume)
//   [base+1].xy = velocity (initialized to zero)
// Buffer is 36 vec4s (576 bytes) — matches the nbody/bh_integrate readers.
layout(set = 1, binding = 0, std430) buffer BHData {
    vec4 bh[36];
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float qi_threshold;   // condensation threshold for Qi
    float _pad0;
    float _pad1;
} pc;

int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

void main() {
    int total = int(pc.N_f) * int(pc.N_f) * int(pc.N_f);
    int gid = int(gl_GlobalInvocationID.x);
    if (gid >= total) return;

    float qval = qv[gid];
    if (qval <= pc.qi_threshold) return;

    // ── Write to deterministic slot (gid % 15, max slot 14) ──
    int slot = gid % 15;
    int base = 4 + slot * 2;
    if (base + 1 >= 36) return;  // safety

    vec3 ext = bh[2].yzw;
    int N = int(pc.N_f);
    int cx = gid % N;
    int cy = (gid / N) % N;
    int cz = gid / (N * N);
    // Grid cell (0..N) → world [−extent_i, +extent_i] per axis — same
    // convention as the mass deposit and the nbody samplers (gc = wp/extent_i·N/2 + N/2).
    vec3 world_pos = ((vec3(cx, cy, cz) + 0.5) / float(N) * 2.0 - 1.0) * ext;

    float cell_vol = (ext.x / float(N)) * (ext.y / float(N)) * (ext.z / float(N));
    float mass = qval * cell_vol;

    bh[base]     = vec4(world_pos, mass);
    bh[base + 1] = vec4(0.0, 0.0, 0.0, 0.0);  // velocity (at rest)
}
