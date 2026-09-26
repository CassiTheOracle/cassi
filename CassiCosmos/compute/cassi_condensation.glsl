#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 4 floats (16 B); sets 0 (0), 1 (0)
#version 450

// Standalone module: local finiteness helpers (GLSL has no includes).
bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
bool finite_vec3(vec3 value) { return !(any(isnan(value)) || any(isinf(value))); }
// GL_EXT_shader_atomic_float: float atomicAdd on the mass ledger slots
// bh[34]/bh[35] (verified on this RX 7900 XTX / Godot 4.7 by
// cassi_mass_deposit.glsl, cassi_particle_merge.glsl and
// cassi_bh_accretion.glsl).
#extension GL_EXT_shader_atomic_float : require
// Cassi Condensation Scanner — finds Qi peaks, nucleates black holes
//
// Scans the Qi field grid. A cell above the condensation threshold forms a
// candidate record; a slot is replaced only when the candidate is AT LEAST
// AS HEAVY as the record already in it. The selection is the site twin's
// (cassi_site_condensation.glsl): ONE invocation owns each slot and scans
// every cell that maps to it, with a lowest-cell-index tie break, so the
// published record is decided by a single thread instead of by whichever
// cell happened to write last. (Before this the kernel wrote bh[base]
// unconditionally from every qualifying cell — a race between slots, and a
// claim in this header that the code did not implement.)
//
// Slot map: cell gid belongs to slot gid % 15; the OWNER of slot s is the
// canonical invocation (x = s, y = 0, z = 0). The owner scans the cells
// directly rather than relying on the dispatch's index coverage, so the
// whole grid is considered for every slot however the workgroups are laid
// out (the host dispatches the cube convention, whose x-extent alone would
// truncate a 1-D gid — the integrate pass had the same shape and was fixed
// the same way: BH_DYNAMICS_PREREG findings 5/F).
//
// Mass ledger (bh[34]; BH_DYNAMICS_PREREG findings 2/3/C): a nucleated
// record's mass comes from the field, so it is booked into CREATED
// (bh[34].x) and a displaced record's mass into EXPIRED (bh[34].y) — the
// ledger is the only account of mass entering or leaving a record without
// a particle source.
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
// bh[34]        = mass ledger: (created, expired, absorbed, reserved)
// bh[35]        = health: (deposit-clamped cells, deposit non-finite,
//                 integrate non-finite retirements, reserved)
// Buffer is 36 vec4s (576 bytes) — matches the nbody/bh_integrate readers.
// coherent: the ledger slots are atomicAdd'ed here and by the other BH
// passes in the same step.
layout(set = 1, binding = 0, std430) coherent buffer BHData {
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
    // ONE owner per slot: the canonical invocation (x < 15, y == 0, z == 0)
    // owns slot x. Without the y/z guard every (y,z) workgroup of the cube
    // dispatch repeats the identical slot write (and its ledger atomicAdd).
    if (gl_GlobalInvocationID.y != 0u || gl_GlobalInvocationID.z != 0u) return;
    int slot = int(gl_GlobalInvocationID.x);
    if (slot >= 15) return;  // max 15 BHs (slots 0-14)

    int base = 4 + slot * 2;
    if (base + 1 >= 36) return;  // safety

    vec3 ext = bh[2].yzw;
    int N = int(pc.N_f);
    float cell_vol = (ext.x / float(N)) * (ext.y / float(N)) * (ext.z / float(N));

    // Owner scan: every cell whose deterministic slot is this one, in
    // increasing cell index. Strict > keeps the lowest index among equal
    // masses (the tie break), and the single writer is what makes the
    // published record deterministic.
    int best_cell = -1;
    float best_mass = 0.0;
    for (int gid = slot; gid < total; gid += 15) {
        float qval = qv[gid];
        // NaN-safe threshold: a non-finite sample must not condense.
        if (!(qval > pc.qi_threshold)) continue;
        float mass = qval * cell_vol;
        if (!(mass > 0.0) || !finite_float(mass)) continue;
        if (best_cell < 0 || mass > best_mass) {
            best_cell = gid;
            best_mass = mass;
        }
    }
    // No qualifying cell: a live record in this slot persists untouched.
    if (best_cell < 0) return;

    float current = bh[base].w;
    // The occupant wins ties in nothing: a candidate that is at least as
    // heavy replaces it, exactly as cassi_site_condensation.glsl does.
    if (current > best_mass) return;

    int cx = best_cell % N;
    int cy = (best_cell / N) % N;
    int cz = best_cell / (N * N);
    // Grid cell (0..N) → world [−extent_i, +extent_i] per axis — same
    // convention as the mass deposit and the nbody samplers (gc = wp/extent_i·N/2 + N/2).
    // Movable home-window (perf-decomp 2026-08-15): the grid is window-
    // relative, so the world spawn adds the window origin bh[0].yzw
    // (zero = the fixed-origin box, bit-identical).
    vec3 world_pos = ((vec3(cx, cy, cz) + 0.5) / float(N) * 2.0 - 1.0) * ext + bh[0].yzw;

    // A malformed spawn must never enter the record buffer: a non-finite
    // position poisons the point-gravity term for every particle.
    if (!finite_vec3(world_pos)) return;

    // Mass ledger: the displaced record's mass leaves the sector, the
    // nucleated mass enters it. A garbage occupant is retired without a
    // mass booking (NaN must never reach an accumulator).
    if (current > 0.0 && finite_float(current)) atomicAdd(bh[34].y, current);
    atomicAdd(bh[34].x, best_mass);

    bh[base]     = vec4(world_pos, best_mass);
    bh[base + 1] = vec4(0.0, 0.0, 0.0, 0.0);  // velocity (at rest)
}
