#[compute]
#version 450
// Cassi Exclusive Prefix-Sum — a compact on-GPU exclusive scan used by the
// particle-merge pass to replace the host CPU scan of the spatial-hash cell
// counts (FIX B). The merge's per-cycle host `buffer_get_data(cc)` readback
// (~33.9 MB) + two `buffer_update` uploads (cs/ch) + an 8.9M-iteration CPU
// prefix-sum were ~+276 ms per merge batch — the condensing stutter. This
// shader computes cs on the GPU; the host then needs only the 4-byte merge
// counter readback to check termination.
//
// Two-level Hillis–Steele EXCLUSIVE scan (uint counts). Scheme (single
// scratch buffer `scr` laid out as two regions — see the host):
//   cc[e]  cell count array,   E  elements (padded to Ea = ceil(E/256)*256).
//   cs[e]  output exclusive scan of cc.
//   scr[0..nb1-1]      L1: block (256-cell) totals of cc (region A).
//   scr[nb1a .. nb1a+nb2-1]  L2: block totals of L1, then L2's exclusive scan
//                            (region B). nb1a = ceil(nb1/256)*256, nb2=ceil(nb1/256).
// Passes (pass_mode):
//   1  block_scan(cc -> cs, totals -> scr[b])              size=E
//   2  block_scan(scr in-place -> loc1, totals -> scr[nb1a+bb])  size=nb1
//   3  single_scan(scr[nb1a..] in-place -> L2 exclusive)   size=nb2 (<=256)
//   4  add_carries: cs[e] += scr[e/256] + scr[nb1a + (e/256)/256]
// Final: cs[e] = cc-exclusive-sum up to e (correct for every e in [0,E)).
//
// Covers E <= 256^3 = 16.7M (nb1 <= 65536 => level-2 has <=256 blocks, so
// level-3 is a single 256-wide workgroup) — the 2.5M-particle / 8.88M-cell
// live box fits. Only integer ops, no atomics.
#extension GL_EXT_shader_atomic_float : enable   // unused; kept for parity

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 15, std430) coherent buffer Counts { uint cc[]; }; // cc (E) — ALSO cs output region via binding 16
layout(set = 0, binding = 16, std430) coherent buffer Output { uint cs[]; };
layout(set = 0, binding = 17, std430) coherent buffer Scratch { uint scr[]; };
layout(set = 0, binding = 18, std430) coherent buffer CellHead { uint ch[]; }; // fill head: pass 4 sets ch = cs

layout(push_constant, std430) uniform PC {
    float size_f;      // elements at THIS pass (E / nb1 / nb2)
    float pass_mode;   // 1..4
    float nb1a;        // nb1a (region-B base offset) — int(nb1a)
    float _pad0;
} pc;

shared uint sh[256];
const uint BLOCK = 256u;

// Hillis–Steele inclusive scan of sh[0..255]; after it, sh[255]=block total.
void hss_inclusive() {
    for (uint stride = 1u; stride < BLOCK; stride <<= 1u) {
        uint v = sh[gl_LocalInvocationID.x];
        if (gl_LocalInvocationID.x >= stride)
            v += sh[gl_LocalInvocationID.x - stride];
        memoryBarrierShared();
        barrier();
        sh[gl_LocalInvocationID.x] = v;
        memoryBarrierShared();
        barrier();
    }
}

void main() {
    int m = int(pc.pass_mode + 0.5);
    uint n = uint(pc.size_f + 0.5);
    int nb1a = int(pc.nb1a + 0.5);
    uint g = gl_WorkGroupID.x;
    uint t = gl_LocalInvocationID.x;

    if (m == 1) {
        // cc -> cs (exclusive), totals -> scr[b].
        uint off = g * BLOCK + t;
        sh[t] = (off < n) ? cc[off] : 0u;
        memoryBarrierShared(); barrier();
        hss_inclusive();
        if (t == 255u) scr[g] = sh[255];
        uint excl = sh[t];
        if (t > 0u) excl = sh[t - 1u]; else excl = 0u;
        memoryBarrierShared(); barrier();
        if (off < n) cs[off] = excl;
        return;
    }
    if (m == 2) {
        // scan scr[0..nb1-1] (L1) IN PLACE -> scr[0..nb1-1] = loc1 (exclusive
        // within level-2 blocks), totals -> scr[nb1a + bb].
        uint off = g * BLOCK + t;
        sh[t] = (off < n) ? scr[off] : 0u;
        memoryBarrierShared(); barrier();
        hss_inclusive();
        if (t == 255u) scr[nb1a + g] = sh[255];
        uint excl = sh[t];
        if (t > 0u) excl = sh[t - 1u]; else excl = 0u;
        memoryBarrierShared(); barrier();
        if (off < n) scr[off] = excl;
        return;
    }
    if (m == 3) {
        // single workgroup scan of scr[nb1a .. nb1a+nb2-1] (L2) in place ->
        // L2 exclusive (level-2 carries). n = nb2 <= 256.
        sh[t] = (t < n) ? scr[nb1a + t] : 0u;
        memoryBarrierShared(); barrier();
        hss_inclusive();
        uint excl = sh[t];
        if (t > 0u) excl = sh[t - 1u]; else excl = 0u;
        memoryBarrierShared(); barrier();
        if (t < n) scr[nb1a + t] = excl;
        return;
    }
    if (m == 4) {
        // add_carries: cs[e] += scr[e/256] (loc1) + scr[nb1a + (e/256)/256] (L2 excl).
        // Also set ch[e] = cs[e] (the fill head start for the next fill pass).
        uint off = g * BLOCK + t;
        if (off < n) {
            uint b = off / BLOCK;            // level-1 block index
            uint bb = b / BLOCK;             // level-2 block index
            cs[off] += scr[b] + scr[nb1a + bb];
            ch[off] = cs[off];
        }
        return;
    }
}
