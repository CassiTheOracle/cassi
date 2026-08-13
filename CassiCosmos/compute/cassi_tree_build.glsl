#[compute]
#version 450
// Cassi Tree Build — level-by-level octree construction for the open-boundary
// FMM/tree gravity arm (research/meshless/fmm_design.md Q2; stage5_fmm.py).
//
// Builds, in storage buffers, the LINEAR (flat-array) octree the gravity
// shader (cassi_tree_gravity.glsl) walks: per node [center.xyz, half],
// [W, com.xyz], packed trace-free quadrupole, leaf range [ps,pe), and
// child base/count. Nodes are allocated LEVEL-BY-LEVEL (BFS): the children
// of every node at level d form one contiguous block [level_end, next_end)
// of the node table, so a node's children are [childBase, childBase+childCount)
// — no per-node child-array, walk opens by pushing that contiguous range.
//
// Passes (host dispatches, one pipeline; pc.mode selects):
//   mode 0  PREPARE   (1 dispatch)  one thread/source: root-box Morton key
//             (30 bit, 10/axis, interleaved) + chord weight w = m·g,
//             g = 1 + (xi−1)·q_coh from the source's own (EY,EI)  → srcW
//   mode 1  BITONIC   (91 dispatches)  sort srcOrder by the Morton key
//             ascending (N=2^13 = 8192 → 13·14/2 = 91 comparator stages;
//             deterministic exact order, no histogram/prefix stability trap).
//             Pass count documented: 91.
//   mode 5  SPLIT     (1 dispatch per octree level, host loop ≤ MAX_LEVELS)
//             one thread/node in [level_start, level_start+level_count);
//             a node with range>leaf_cap and depth<max_levels splits its
//             Morton-contiguous source range [ps,pe) into ≤8 octant
//             sub-runs (pos_axis > center_axis → bit), allocates child
//             nodes (atomicAdd node_cnt) and writes child center/half/range.
//   mode 6  MOMENTS   (1 dispatch)  one thread/node: W = Σ w, COM = Σ w·p/W,
//             trace-free Q_ij = Σ w(3 ξ_i ξ_j − |ξ|² δ_ij), ξ = p−COM,
//             from the node's [ps,pe) source range (the weighted monopole
//             + quadrupole the walk consumes).
//
// Opening/hardening rules live in the WALK shader (this shader only builds).
// Total dispatch count ≈ 1 + 91 + levels(≤ MAX_LEVELS) + 1.
//
// Buffers (set 0, shared with the gravity shader):
//   0 srcTable  vec4[2N]  [pos.xyz, mass], [EY, EI, 0, 0]
//   1 srcW      float[N]  precomputed chord weight w = m·g
//   2 srcKey    uint[N]   30-bit Morton key
//   3 srcOrder  uint[N]   sorted slot -> source index (bitonic payload)
//   4 nodeCF    vec4[M]   [cx,cy,cz, half]
//   5 nodeW     vec4[M]   [W, comx, comy, comz]
//   6 nodeQ     vec4[2M]  [Qxx,Qxy,Qxz,Qyy], [Qyz,Qzz,0,0]  (trace-free)
//   7 nodeR     ivec4[M]  [ps, pe, childBase, childCount]
//   8 counters  uint[8]   [0]=node_cnt, [1]=spare
// Root box (host): box_cx/y/z = 0.5·(lo+hi), pc.half = 0.5·max(hi−lo)·(1+1e-6)
// inflate so every point is strictly inside; root node = slot 0, range [0,N).

//Morton key: interleaved 10-bit/axis (30-bit). Node source ranges are
//Morton-contiguous, so each node's split scan finds octant sub-runs inline.
//The BFS allocation avoids standalone histogram/prefix passes — the sort is
//bitonic (91 stages, exact ascending), and per-level child allocation is via
//the integer atomic counter (no float atomics needed here).

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict readonly buffer SrcTable { vec4 src[]; };
layout(set = 0, binding = 1, std430) buffer SrcW { float srcw[]; };
layout(set = 0, binding = 2, std430) buffer SrcKey { uint srckey[]; };
layout(set = 0, binding = 3, std430) buffer SrcOrder { uint srcorder[]; };
layout(set = 0, binding = 4, std430) buffer NodeCF { vec4 ncf[]; };
layout(set = 0, binding = 5, std430) buffer NodeW { vec4 nw[]; };
layout(set = 0, binding = 6, std430) buffer NodeQ { vec4 nq[]; };
layout(set = 0, binding = 7, std430) buffer NodeR { ivec4 nr[]; };
layout(set = 0, binding = 8, std430) coherent buffer Counters { uint ctr[]; };

layout(push_constant, std430) uniform PC {
    float N_f;          // #0 source/target count (8192)
    float bmin_x;       // #1 root box min.x
    float bmin_y;       // #2 root box min.y
    float bmin_z;       // #3 root box min.z
    float bhalf;        // #4 root half-size
    float eps2;         // #5 softening² (1e-6)
    float phi;          // #6
    float xi;           // #7 phi⁶
    float leaf_cap;     // #8 1.0
    float max_levels;   // #9 14.0
    float mode;         // #10 0 prep / 1 bitonic / 5 split / 6 moments
    float b_k;          // #11 bitonic outer k, or (split) level_start
    float b_j;          // #12 bitonic inner j, or (split) level_count
    float b_m;          // #13 bitonic pass index (0 precount, 1..91 swap)
} pc;

const float PHI_INV2 = 0.3819660112501051;   // φ⁻² — q decoherence threshold
const uint  MORT_PER_AXIS = 1024u;           // 10 bits/axis
const float MORT_F = 1024.0;

// ── bit interleave for a 30-bit Morton key from 3×10-bit coords ────────
uint dilate10(uint x) {
    uint r = 0u;
    for (int i = 0; i < 10; i++) {
        r |= ((x >> uint(i)) & 1u) << (3u * uint(i));
    }
    return r;
}

// ── mode 0: root-box Morton key + chord weight per source ──────────────
void prepare_main() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N_f)) return;
    vec4 p = src[2 * i];
    vec4 f = src[2 * i + 1];
    float mass = p.w;
    float ey = f.x;
    float ei = f.y;
    // chord weight g = 1 + (xi−1)·q_coh, q_coh = ρ²/(ρ²+φ⁻²+ε²)
    float rho = ey + ei;
    float eps = ey - pc.phi * ei;
    float q = (rho * rho) / (rho * rho + PHI_INV2 + eps * eps);
    float g = 1.0 + (pc.xi - 1.0) * q;
    srcw[i] = mass * g;
    // Morton key over the root box [bmin, bmin+2·half): 10 bits/axis.
    // Shared denominator D = 2·half per axis (equal sides → isotropic key).
    float D = 2.0 * pc.bhalf;
    uint ix = uint(clamp(floor((p.x - pc.bmin_x) * MORT_F / D), 0.0, MORT_F - 1.0));
    uint iy = uint(clamp(floor((p.y - pc.bmin_y) * MORT_F / D), 0.0, MORT_F - 1.0));
    uint iz = uint(clamp(floor((p.z - pc.bmin_z) * MORT_F / D), 0.0, MORT_F - 1.0));
    srckey[i] = dilate10(ix) | (dilate10(iy) << 1u) | (dilate10(iz) << 2u);
    srcorder[i] = i;   // identity order (sorted in the bitonic passes)
}

// ── mode 1: bitonic sort of srcorder by srckey (ascending), N = 2^k ────
// pc.b_m: 0 → initialize order identity (host may set it, but do it here
// for determinism); >0 → the b_m-th comparator stage with (b_k, b_j).
// Stage map: for outer k over powers of 2 and inner j down to 1, index m
// increments; the host passes the (k,j) pair for the m-th stage.
void bitonic_main() {
    int N = int(pc.N_f);               // must be a power of 2 (2^13 = 8192)
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= N) return;
    if (pc.b_m < 0.5) {
        srcorder[i] = i;               // identity before sorting
        return;
    }
    int k = int(pc.b_k);
    int j = int(pc.b_j);
    int li = int(i) ^ j;
    if (li <= int(i)) return;          // each pair handled once
    bool ascending = (int(i) & k) == 0;
    uint a = srckey[int(i)];
    uint b = srckey[li];
    bool swap = (ascending) ? (a > b) : (a < b);
    if (swap) {
        srckey[int(i)] = b; srckey[li] = a;
        uint oi = srcorder[int(i)]; uint ol = srcorder[li];
        srcorder[int(i)] = ol; srcorder[li] = oi;
    }
}

// ── mode 5: split one octree level's nodes into children ───────────────
// One thread per node in [level_start, level_start + level_count). Node n's
// source range [ps,pe) is Morton-contiguous; its children are the sub-runs
// of distinct octants (pos_axis > center_axis → bit). A node whose range
// ≤ leaf_cap, or at depth ≥ max_levels, stays a leaf (childCount 0).
void split_main() {
    uint gid = gl_GlobalInvocationID.x;
    int ls = int(pc.b_k);       // level_start
    int lc = int(pc.b_j);       // level_count
    if (int(gid) >= lc) return;
    int n = ls + int(gid);
    ivec4 rng = nr[n];
    int ps = rng.x;
    int pe = rng.y;
    int cnt = pe - ps;
    // child half = node half / 2; child center = center ± (node half / 2)/axis
    vec4 cf = ncf[n];
    float chalf = cf.w * 0.5;

    if (cnt > int(pc.leaf_cap)) {
        // count non-empty octants first, then allocate children
        int nchild = 0;
        // collect per-octant run boundaries in local arrays (≤8)
        int oct_count = 0;
        int run_oct[8];
        int run_start[8];
        int run_end[8];
        int prev_oct = -1;
        for (int s = ps; s < pe; s++) {
            uint si = srcorder[s];
            vec4 p = src[2 * si];
            int oct = (p.x > cf.x ? 4 : 0)
                    | (p.y > cf.y ? 2 : 0)
                    | (p.z > cf.z ? 1 : 0);
            if (oct != prev_oct) {
                if (oct_count < 8) {
                    run_oct[oct_count] = oct;
                    run_start[oct_count] = s;
                    run_end[oct_count] = s;   // set below
                    nchild++;
                    oct_count++;
                }
                prev_oct = oct;
            }
            if (oct_count > 0) run_end[oct_count - 1] = s + 1;
        }
        // allocate nchild contiguous node rows (the next level's block)
        uint base = atomicAdd(ctr[0], uint(nchild));
        nr[n] = ivec4(ps, pe, int(base), nchild);
        vec3 ctrv = cf.xyz;
        for (int c = 0; c < nchild; c++) {
            vec3 off;
            off.x = (run_oct[c] & 4) != 0 ? chalf : -chalf;
            off.y = (run_oct[c] & 2) != 0 ? chalf : -chalf;
            off.z = (run_oct[c] & 1) != 0 ? chalf : -chalf;
            int child = int(base) + c;
            ncf[child] = vec4(ctrv + off, chalf);
            nr[child] = ivec4(run_start[c], run_end[c], -1, 0);
        }
    } else {
        nr[n] = ivec4(ps, pe, -1, 0);   // leaf: no children
    }
}

// packed trace-free quadrupole accumulation helpers (node-local, mode 6)
// Q[6] = [Qxx,Qxy,Qxz,Qyy,Qyz,Qzz]

// ── mode 6: moments for every node (one thread/node scans its range) ───
// W = Σ w ; COM = Σ w·p / W ; Q_ij = Σ w(3 ξ_i ξ_j − |ξ|² δ_ij), ξ = p − COM.
// Accumulated in float (portable; the float32 AMOUNT of rounding is well
// below the G16 ≤5e-3 cross-check threshold vs the float64 prototype).
void moments_main() {
    uint gid = gl_GlobalInvocationID.x;
    int nc = int(ctr[0]);           // total node count (after all splits)
    if (int(gid) >= nc) return;
    ivec4 rng = nr[gid];
    int ps = rng.x;
    int pe = rng.y;
    float W = 0.0;
    vec3 s = vec3(0.0);
    for (int s2 = ps; s2 < pe; s2++) {
        uint si = srcorder[s2];
        vec4 p = src[2 * si];
        float wv = srcw[si];
        W += wv;
        s += wv * p.xyz;
    }
    vec3 com = (W > 1e-30) ? s / W : vec3(0.0);
    float qxx = 0.0, qxy = 0.0, qxz = 0.0, qyy = 0.0, qyz = 0.0, qzz = 0.0;
    for (int s2 = ps; s2 < pe; s2++) {
        uint si = srcorder[s2];
        vec4 p = src[2 * si];
        float wv = srcw[si];
        vec3 xi = p.xyz - com;
        float r2 = dot(xi, xi);
        qxx += wv * (3.0 * xi.x * xi.x - r2);
        qxy += wv * (3.0 * xi.x * xi.y);
        qxz += wv * (3.0 * xi.x * xi.z);
        qyy += wv * (3.0 * xi.y * xi.y - r2);
        qyz += wv * (3.0 * xi.y * xi.z);
        qzz += wv * (3.0 * xi.z * xi.z - r2);
    }
    nw[gid] = vec4(W, com);
    nq[2 * gid] = vec4(qxx, qxy, qxz, qyy);
    nq[2 * gid + 1] = vec4(qyz, qzz, 0.0, 0.0);
}

void main() {
    int m = int(pc.mode);
    if (m == 0) prepare_main();
    else if (m == 1) bitonic_main();
    else if (m == 5) split_main();
    else moments_main();
}
