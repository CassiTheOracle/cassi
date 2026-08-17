#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 6 floats (24 B); set 0: bindings 0-4
#version 450
// Boxless site hash (boxless_site_hash_prereg.md) — spatial hash over the
// Arm-1 coherence-filtered shortlist. Built on the steer cadence, IMMEDIATELY
// after cassi_site_shortlist.glsl, so the per-frame boxless instancer's
// nearest-coherent-site lookup becomes a bounded-cell ring query instead of a
// linear O(shortlist) scan: per-frame boxless render tracks coherent CONTENT
// (bucket occupancy), not the shortlist count.
//
// A fixed-resolution uniform grid over the sim box (same box/extents the
// instancer's extent PC carries). Mode-staged exactly like the tree/shortlist
// in-list passes:
//   mode 0 = RESET:   thread 0 zeroes cell_count[0..n_cells).
//   mode 1 = HISTOGRAM: one thread per shortlist slot k<n; atomicAdd
//            cell_count[cell(sl[k])].
//   mode 2 = PREFIX:  one thread builds the EXCLUSIVE prefix of cell_count into
//            cell_start[0..n_cells] AND copies cell_start[c] back into
//            cell_count[c] (the per-cell scatter cursor).
//   mode 3 = SCATTER: one thread per shortlist slot k<n; slot =
//            atomicAdd(cell_count[c], 1); cell_sites[slot] = k. The cursor was
//            seeded at cell_start[c], so each cell's sites land in a contiguous
//            run [cell_start[c], cell_start[c+1]).
//
// The instancer query (in cassi_instancer.glsl, inside the boxless branch) maps
// a world point to its cell and grows a Chebyshev ring (radius 1 → 27 cells,
// then 2 → 125, ... up to MAX_QUERY_R) until a non-empty ring is found, then
// takes the global min over ALL shortlist slots in rings ≤ that radius. Exact by
// construction: a closer site would live in an earlier, already-scanned ring.
//
// Bindings (set 0): 0 = shortlist (vec4[max_sites]: pos.xyz + float(site_idx),
// the SAME buffer cassi_site_shortlist.glsl writes), 1 = cell_start
// (uint[n_cells+1] — prefix, RW), 2 = cell_sites (uint[max_sites] — per-cell
// compacted shortlist slots), 3 = cell_count (uint[n_cells] — histogram /
// scatter cursor, RW), 4 = count (uint[1] — the shortlist's LIVE atomic count,
// read in-list after the shortlist pass's barrier → no host readback, works on
// both the local and global RD paths and never touches stale slots).
// PC: ext_x, ext_y, ext_z (the box half-extents, == the instancer extent PC),
// h (cells per axis, float; default 32 → 32768 cells), n_shortlist (float —
// host bound, only a safety cap; the live count buffer is authoritative),
// mode (float 0-3).
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Shortlist { vec4 sl[]; };
layout(set = 0, binding = 1, std430) buffer CellStart { uint cell_start[]; };
layout(set = 0, binding = 2, std430) buffer CellSites { uint cell_sites[]; };
layout(set = 0, binding = 3, std430) coherent buffer CellCount { uint cell_count[]; };
layout(set = 0, binding = 4, std430) readonly buffer ShortlistCount { uint scnt; };

layout(push_constant, std430) uniform PC {
    float ext_x;      // box half-extent x (== instancer extent PC slot 28)
    float ext_y;      // box half-extent y
    float ext_z;      // box half-extent z
    float h;          // cells per axis (power of two; 32 default)
    float n_shortlist;// current shortlist count
    float mode;       // 0 reset, 1 histogram, 2 prefix, 3 scatter
} pc;

const uint MAX_CELLS = 1u << 15;   // 32768 (H=32) — cell_start/ cell_count sizing bound
const uint MAX_QUERY_R = 5u;       // instancer ring cap (shared with the query)

// World → box-min cell (the box is [−ext, +ext] per axis, axis-aligned at the
// envelope center; the instancer's extent PC uses the same box).
uint cell_of(vec3 wp) {
    int H = int(pc.h);
    float cs = (2.0 * pc.ext_x) / float(H);
    float mn = -pc.ext_x;
    int cx = clamp(int(floor((wp.x - mn) / cs)), 0, H - 1);
    int cy = clamp(int(floor((wp.y - mn) / cs)), 0, H - 1);
    int cz = clamp(int(floor((wp.z - mn) / cs)), 0, H - 1);
    return uint(cx + H * (cy + H * cz));
}

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int H = int(pc.h);
    uint ncells = uint(H) * uint(H) * uint(H);
    int mode = int(pc.mode);
    if (mode == 0) {
        // RESET: cell_count[0..n_cells) = 0 (one thread per cell, 64/thread).
        if (gid < ncells) { cell_count[gid] = 0u; }
        return;
    }
    int ns = min(int(pc.n_shortlist), int(scnt));   // live count (read after the shortlist's barrier) caps the scan — stale slots are never touched
    if (mode == 1) {
        // HISTOGRAM: one thread per shortlist slot.
        if (gid >= uint(ns)) return;
        uint c = cell_of(sl[gid].xyz);
        atomicAdd(cell_count[c], 1u);
        return;
    }
    if (mode == 2) {
        // PREFIX: exclusive prefix of cell_count → cell_start[0..n_cells], and
        // seed cell_count[c] = cell_start[c] (the scatter cursor). Serial on one
        // thread — the grid is modest (≤ 32768) and this runs per steer cadence.
        if (gid != 0u) return;
        uint acc = 0u;
        for (uint c = 0u; c < ncells; c++) {
            uint cnt = cell_count[c];
            cell_start[c] = acc;
            cell_count[c] = acc;   // cursor = run start
            acc += cnt;
        }
        cell_start[ncells] = acc;
        return;
    }
    // SCATTER: one thread per shortlist slot.
    if (gid >= uint(ns)) return;
    uint c = cell_of(sl[gid].xyz);
    uint slot = atomicAdd(cell_count[c], 1u);
    cell_sites[slot] = gid;   // gid == the shortlist slot k
}
