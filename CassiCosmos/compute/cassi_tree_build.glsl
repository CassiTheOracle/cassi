#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 19 floats (76 B); set 0: bindings 0-13
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
//   mode 7  GATHER    (1 dispatch)  sim path — fills srcTable from the
//             meshless Voronoi mesh (site pos / EY / EI / vol + the deposit's
//             mass density at the site's grid cell, SOURCE-MASS RECIPE in
//             gather_main), then does everything mode 0 does (chord w + key)
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
//   mode 9  CTR_RESET (1 dispatch)  seed ctr = [1,0,1,0,0,0,0,0] on the GPU
//   mode 10 ROOT_SEED (1 dispatch)  write the root nodeCF + nodeR from the PC
//             (bmin+bhalf center, half=pc.bhalf; range [0, N_f)) — replaces
//             per-frame host buffer_update seeds (global-RD ordering).
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
//   9 mlsites   vec4[N]   meshless site positions (mode 7)
//  10 mlpsy     float[N]  meshless per-site EY (mode 7)
//  11 mlpsi     float[N]  meshless per-site EI (mode 7)
//  12 mlvol     float[N]  meshless per-site cell volume (mode 7)
//  13 mlrho     float[N]  field-grid mass density (deposit; site cell lookup, mode 7)
// Root box (host): box_cx/y/z = 0.5·(lo+hi), pc.half = 0.5·max(hi−lo)·(1+1e-6)
// inflate so every point is strictly inside; root node = slot 0, range [0,N).

//Morton key: interleaved 10-bit/axis (30-bit). Node source ranges are
//Morton-contiguous, so each node's split scan finds octant sub-runs inline.
//The BFS allocation avoids standalone histogram/prefix passes — the sort is
//bitonic (91 stages, exact ascending), and per-level child allocation is via
//the integer atomic counter (no float atomics needed here).

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer SrcTable { vec4 src[]; };
layout(set = 0, binding = 1, std430) buffer SrcW { float srcw[]; };
layout(set = 0, binding = 2, std430) buffer SrcKey { uint srckey[]; };
layout(set = 0, binding = 3, std430) buffer SrcOrder { uint srcorder[]; };
layout(set = 0, binding = 4, std430) buffer NodeCF { vec4 ncf[]; };
layout(set = 0, binding = 5, std430) buffer NodeW { vec4 nw[]; };
layout(set = 0, binding = 6, std430) buffer NodeQ { vec4 nq[]; };
layout(set = 0, binding = 7, std430) buffer NodeR { ivec4 nr[]; };
layout(set = 0, binding = 8, std430) coherent buffer Counters { uint ctr[]; };
// ── mode 7 GATHER (sim path only): meshless site sources ───────────────
// The tree's source table is filled from the meshless Voronoi mesh instead
// of a host-supplied srcTable. One thread per SITE: reads the site position
// and field state + the deposit's mass density at the site's grid cell and
// writes srcTable[2s] (pos,mass), srcTable[2s+1] (EY,EI) and srcw[s]
// (chord weight w = m·g) exactly like mode 0 PREPARE, then enters the same
// Morton-key/order path so the bitonic/split/moments chain is unchanged.
layout(set = 0, binding = 9, std430) restrict readonly buffer MlSites { vec4 site[]; };
layout(set = 0, binding = 10, std430) restrict readonly buffer MlPsiY { float psy[]; };
layout(set = 0, binding = 11, std430) restrict readonly buffer MlPsiI { float psi[]; };
layout(set = 0, binding = 12, std430) restrict readonly buffer MlVol { float mvol[]; };
layout(set = 0, binding = 13, std430) restrict readonly buffer MlRhoMass { float mrho[]; };
// Per-node mean coherence q_n (coherence_adaptive_prereg.md Arm 2): written by
// the mode-6 MOMENTS pass from the source (EY,EI), mass-weighted over the
// node's source range. Consumed by the WALK shader's coherence-adaptive θ.
layout(set = 0, binding = 14, std430) buffer NodeQQ { float nodeqq[]; };

layout(push_constant, std430) uniform PC {
    float N_f;          // #0 source count (sites, 8192)
    float bmin_x;       // #1 root box min.x
    float bmin_y;       // #2 root box min.y
    float bmin_z;       // #3 root box min.z
    float bhalf;        // #4 root half-size
    float eps2;         // #5 softening² (1e-6)
    float phi;          // #6
    float xi;           // #7 phi⁶
    float leaf_cap;     // #8 1.0
    float max_levels;   // #9 14.0
    float mode;         // #10 0 prep / 1 bitonic / 5 split / 6 moments / 7 gather / 8 commit / 9 ctr-reset / 10 root-seed
    float b_k;          // #11 bitonic outer k, or (split) level_start
    float b_j;          // #12 bitonic inner j, or (split) level_count
    float b_m;          // #13 bitonic pass index (0 precount, 1..91 swap)
    // mode-7 gather extras (read only when mode == 7; the verify scene
    // leaves 0.0 and the sim sets them for the site→grid-cell lookup):
    float grid_N;       // #14  field grid resolution (rho_mass lookup)
    float extent_x;     // #15  per-axis sim half-extents (h_i = 2·extent_i/N)
    float extent_y;     // #16
    float extent_z;     // #17
    float field_floor;  // #18  field-mass density floor (source-mass recipe)
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

// ── mode 7: GATHER — fill the source table from the meshless Voronoi mesh ─
// One thread per SITE (N_src). Equivalent to the sim running mode 0 PREPARE
// on a host-filled srcTable, except the source position, field state, cell
// volume and the deposit mass density are read DIRECTLY from the meshless
// buffers. SOURCE-MASS RECIPE (documented; the numpy gate G30 reimplements
// the SAME recipe):
//   m_s  = rho_mass(site cell) · V_s  +  max(rho_field · V_s, field_floor)
//   rho_field = EY_s + EI_s  (the Qi field's mass-energy in the cell)
//   field_floor = pc.field_floor · V_s  (see below)
// The deposit term rho_mass·V_s is the particles' TSC-scattered mass inside
// the site's Voronoi cell (the leapfrog's grid-cell sampling convention,
// cassi_voronoi_cells.glsl mode 1); the field term adds the Qi field's own
// mass-energy. field_floor is a dimensionless floor on the FIELD density
// (default 1e-6) so a source is never EXACTLY massless where both the
// deposit and the field are simultaneously empty — COM/quadrupole ratios in
// mode 6 stay defined. When the deposit is nonzero the floor is moot; it
// only guards the fully-empty case.
void gather_main() {
    uint s = gl_GlobalInvocationID.x;
    if (int(s) >= int(pc.N_f)) return;
    vec4 sp = site[s];
    // site's grid cell (leapfrog convention: gi = floor(sp.x / hx) % N)
    int N = int(pc.grid_N);
    float hx = (pc.extent_x > 0.0) ? 2.0 * pc.extent_x / float(N) : 1.0;
    float hy = (pc.extent_y > 0.0) ? 2.0 * pc.extent_y / float(N) : 1.0;
    float hz = (pc.extent_z > 0.0) ? 2.0 * pc.extent_z / float(N) : 1.0;
    int gi = int(floor(sp.x / hx)) % N;
    int gj = int(floor(sp.y / hy)) % N;
    int gk = int(floor(sp.z / hz)) % N;
    float rho_mass = mrho[gi * N * N + gj * N + gk];
    float ey = psy[s];
    float ei = psi[s];
    float V = max(mvol[s], 1e-12);
    float rho_field = ey + ei;
    float mfield = max(rho_field * V, pc.field_floor * V);
    float mass = rho_mass * V + mfield;
    src[2 * s] = vec4(sp.xyz, mass);
    src[2 * s + 1] = vec4(ey, ei, 0.0, 0.0);
    // chord + Morton key (identical to mode 0 prepare)
    float rho = rho_field;
    float eps = ey - pc.phi * ei;
    float q = (rho * rho) / (rho * rho + PHI_INV2 + eps * eps);
    float g = 1.0 + (pc.xi - 1.0) * q;
    srcw[s] = mass * g;
    float D = 2.0 * pc.bhalf;
    uint ix = uint(clamp(floor((sp.x - pc.bmin_x) * MORT_F / D), 0.0, MORT_F - 1.0));
    uint iy = uint(clamp(floor((sp.y - pc.bmin_y) * MORT_F / D), 0.0, MORT_F - 1.0));
    uint iz = uint(clamp(floor((sp.z - pc.bmin_z) * MORT_F / D), 0.0, MORT_F - 1.0));
    srckey[s] = dilate10(ix) | (dilate10(iy) << 1u) | (dilate10(iz) << 2u);
    srcorder[s] = s;
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

// ── mode 5: split one BFS level's nodes into children ──────────────────
// SELF-CONTAINED round — no host level feedback, so the whole build runs
// in the frame's ONE compute list (stutter-free: the codebase forbids
// per-frame CPU syncs on the global RD). Counters (uint[8]):
//   ctr[0] = node_cnt (produced; root=1 at init)
//   ctr[2] = level_end — the FROZEN frontier capping this round: a thread
//            owns node gid and splits it iff gid < ctr[2] (nodes produced
//            by the previous round) and the node is not yet internal
//            (nr[gid].w, the childCount, == 0). Children are allocated via
//            atomicAdd(ctr[0], nchild) into slots ≥ ctr[2], so they are not
//            touched this round. After the round a mode-8 COMMIT pass sets
//            ctr[2] = ctr[0]; the next round then splits exactly the newly-
//            produced level. Internal nodes (childCount>0) are skipped;
//            leaf cells re-split idempotently (they stay childCount 0). The
//            host loops MAX_LEVELS × [split → barrier → commit → barrier];
//            once a round produces no new nodes, later rounds skip all.
void split_main() {
    uint gid = gl_GlobalInvocationID.x;
    if (int(gid) >= int(ctr[2])) return;      // not in the current level block
    ivec4 rng = nr[gid];
    if (rng.w != 0) return;                    // already split (internal)
    int ps = rng.x;
    int pe = rng.y;
    int cnt = pe - ps;
    // child half = node half / 2; child center = center ± (node half / 2)/axis
    vec4 cf = ncf[gid];
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
        nr[gid] = ivec4(ps, pe, int(base), nchild);
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
        nr[gid] = ivec4(ps, pe, -1, 0);   // leaf: no children
    }
}

// ── mode 8: COMMIT — advance the BFS frontier after a split round ───────
// One thread: ctr[2] = ctr[0] (the new node count = the next level's end).
// Runs after a barrier post-split so ctr[0]'s atomicAdds are all visible;
// a barrier after it hands the next split round a stable level_end.
void commit_main() {
    if (gl_GlobalInvocationID.x != 0u) return;
    ctr[2] = ctr[0];
}

// ── mode 9: CTR_RESET — seed the build counters ON THE GPU ─────────────
// One thread, dispatched in-list as the FIRST tree pass (before gather).
// ctr[0]=node_cnt(1), ctr[1]=unused, ctr[2]=level_end(1), ctr[3..7]=0.
// Moving the counter seed onto the GPU removes ALL pre-list CPU buffer
// traffic for the tree arm (the global-RD seed-race suspected in the
// in-sim no-op: a pre-list buffer_update queued against the same buffer
// the chain writes in-list).
void ctr_reset_main() {
    if (gl_GlobalInvocationID.x != 0u) return;
    ctr[0] = 1u; ctr[1] = 0u; ctr[2] = 1u;
    ctr[3] = 0u; ctr[4] = 0u; ctr[5] = 0u; ctr[6] = 0u; ctr[7] = 0u;
}

// ── mode 10: ROOT_SEED — write the root nodeCF + nodeR on the GPU ───────
// One thread: root box [bmin, bmin+2·half]³ centered (bmin+bhalf) per
// axis, half = pc.bhalf (the PC already carries bmin.xyz + bhalf); root
// range [0, N_f), childBase −1, childCount 0 (not yet internal). Replaces
// the per-frame host buffer_update of _ml_tree_cf/_ml_tree_r.
void root_seed_main() {
    if (gl_GlobalInvocationID.x != 0u) return;
    ncf[0] = vec4(pc.bmin_x + pc.bhalf, pc.bmin_y + pc.bhalf,
                  pc.bmin_z + pc.bhalf, pc.bhalf);
    nr[0] = ivec4(0, int(pc.N_f), -1, 0);
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
    float qsum = 0.0;   // Arm 2: mass-weighted Σ(w·q_i) for the node's mean q
    for (int s2 = ps; s2 < pe; s2++) {
        uint si = srcorder[s2];
        vec4 p = src[2 * si];
        float wv = srcw[si];
        W += wv;
        s += wv * p.xyz;
        // q_i from the source's own (EY,EI): ρ=EY+EI, ε=EY−φ·EI
        vec4 f = src[2 * si + 1];
        float rho = f.x + f.y;
        float eps = f.x - pc.phi * f.y;
        float r2 = rho * rho;
        float qi = r2 / (r2 + PHI_INV2 + eps * eps);
        qsum += wv * qi;
    }
    vec3 com = (W > 1e-30) ? s / W : vec3(0.0);
    nodeqq[gid] = (W > 1e-30) ? qsum / W : 0.0;
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
    else if (m == 7) gather_main();
    else if (m == 1) bitonic_main();
    else if (m == 8) commit_main();
    else if (m == 9) ctr_reset_main();
    else if (m == 10) root_seed_main();
    else if (m == 5) split_main();
    else moments_main();
}
