#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 8 floats (32 B); set 0: bindings 0,3-11,14
#version 450
// Cassi Tree Gravity — open-boundary Barnes–Hut walk over the octree built
// by cassi_tree_build.glsl. Evaluates the CHORD-WEIGHTED potential gradient
//   Phi_g(r) = Σ_s w_s/|r−r_s|,   w_s = m_s·g_s   (g from the source's q_coh),
//   a(r)     = −∇Phi_g  (monopole + quadrupole, ATTRACTIVE toward matter),
// and the river arm then applies the per-target prefactor
//   a_river  = −G_N·(π/ρ)_target·∇Phi_g  =  +G_N·(π/ρ)_target·a(r)
//             (a(r) is already −∇Phi_g; G_N, π/ρ > 0 keep it attractive)
//             = G_N·(π/ρ)_target · forceOut[i]
// with NO periodic images (the MESHLESS_PLAN §0 promise; fmm_design.md Q5).
//
// One thread per TARGET walks the tree with parent-free escape links stored
// in nodeQ[2*n+1].w. Child links are generated in the build pass so this
// stackless DFS is force-complete at every accepted-tree depth and preserves
// the prior ascending-push/LIFO-pop child visitation order:
//
//   n = root
//   open: n = highest child
//   accept/leaf: n = escape[n] (next sibling or ancestor escape)
// Hardening rules:
//   (1) Always open a node whose COM-centered bounds contain the target.
//   (2) Leaves are exact point masses, with self-exclusion for own source.
// These rules keep the open-boundary force self-excluding and complete.
//
// Force terms:
//   monopole = −W·d/(d²+eps2_node)^(3/2)
//   quadrupole = [R²(Q·d) − (5/2)(d·Q·d)d] / R⁷
// The force cap remains the established node-side safety boundary.
//
// DENSITY-AWARE SOFTENING: mode-6 moments/refits precompute
// eps2_node = pc.eps2 + W^(2/3) in nodeQ[2*n+1].z. The walk reads that
// metadata, keeping the established expression and avoiding repeated
// logarithm/exponential work on every accepted node.
// Outputs per target: forceOut[i] = a(r) (vec3, attractive; the caller's
// tree-river arm applies the +G_N(π/ρ)_target prefactor), and interCount[i]
// = number of nodes accepted (> 0).
//
// Buffers (set 0, shared with the build shader): see cassi_tree_build.glsl.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict readonly buffer SrcTable { vec4 src[]; };
layout(set = 0, binding = 3, std430) readonly buffer SrcOrder { uint srcorder[]; };
layout(set = 0, binding = 4, std430) readonly buffer NodeCF { vec4 ncf[]; };
layout(set = 0, binding = 5, std430) readonly buffer NodeW { vec4 nw[]; };
layout(set = 0, binding = 6, std430) readonly buffer NodeQ { vec4 nq[]; };
layout(set = 0, binding = 7, std430) readonly buffer NodeR { ivec4 nr[]; };
// ctr[7] is a malformed-metadata diagnostic; normal walks never write it.
layout(set = 0, binding = 8, std430) coherent buffer Counters { uint ctr[]; };
layout(set = 0, binding = 9, std430) buffer ForceOut { vec4 acc[]; };
layout(set = 0, binding = 10, std430) buffer InterCount { uint inter[]; };
// Optional per-target positions (SIM path): the sim's targets are N-BODY
// PARTICLES whose positions live in the sim's _pos_buf, NOT the mesh-source
// table. When pc.use_tp > 0.5 the walk reads target i from tpos[i].xyz
// (binding 11) instead of src[2i].xyz. verify_fmm leaves the flag off and
// binds a dummy to 11 — its targets ARE the sources.
layout(set = 0, binding = 11, std430) restrict readonly buffer TargetPos { vec4 tpos[]; };
// Per-node mean coherence q_n (Arm 2, coherence_adaptive_prereg.md): written
// by the build's mode-6 MOMENTS; read here for the coherence-adaptive θ.
layout(set = 0, binding = 14, std430) readonly buffer NodeQQ { float nodeqq[]; };

layout(push_constant, std430) uniform PC {
    float N_f;        // #0 target count
    float theta;      // #1 opening criterion (0.5)
    float eps2;       // #2 softening² (1e-6)
    float use_tp;     // #3: 0 = source targets; 1 = legacy tpos targets;
                      //     2 = diagnostic tpos targets without source-ID
                      //     self-exclusion (never used by production)
    float node_cnt;   // #4 total octree node count
    float q_cent;     // #5 field mean coherence q (the running _q_mean) —
                      //     the θ-adjustment pivot; 0 when coherence_theta off
    float alpha;      // #6 θ slope: theta_eff = theta·(1 − alpha·(q_n − q_cent))
    float coherence_theta; // #7 0/1 — coherence-adaptive θ toggle (default off
                      //     → theta_eff ≡ theta, bit-identical)
} pc;

void force_main() {
    uint i = gl_GlobalInvocationID.x;
    int N = int(pc.N_f);
    if (int(i) >= N) return;
    vec3 target = (pc.use_tp > 0.5) ? tpos[i].xyz : src[2 * i].xyz;
    float nx = 0.0, ny = 0.0, nz = 0.0;
    uint interactions = 0u;
    // Hosts may pass allocation capacity; ctr[0] is the produced tree size.
    int nc = min(int(pc.node_cnt), int(ctr[0]));

    // Stackless DFS: nodeQ[2*n+1].w is the escape index after the whole
    // subtree. Child c escapes to c-1 because the former stack walk pushed
    // c=0..count-1 and popped count-1 first. This visits every accepted
    // child in the established order without a finite traversal stack.
    int n = 0;
    while (n >= 0) {
        if (n >= nc) {
            atomicAdd(ctr[7], 1u);
            break;
        }
        ivec4 rng = nr[n];
        int ps = rng.x;
        int pe = rng.y;
        int cbase = rng.z;
        int ccount = rng.w;
        vec4 cf = ncf[n];
        vec4 wv = nw[n];
        vec3 com = wv.yzw;
        float W = wv.x;
        float hs = cf.w;
        vec4 q0 = nq[2 * n];
        vec4 q1 = nq[2 * n + 1];
        // q1.z is precomputed by every moments/refit pass.
        float eps2_node = q1.z;
        // Root has no parent/sibling.  Enforce its terminal sentinel at the
        // walk boundary as well as in build metadata, so every valid tree
        // remains finite even when a manual caller leaves nodeQ uncleared.
        int escape = (n == 0) ? -1 : int(round(q1.w));
        bool valid_children = (ccount == 0)
                || (ccount > 0 && cbase >= 0 && cbase + ccount <= nc);
        bool is_leaf = (ccount == 0);
        bool contains = (abs(target.x - com.x) <= hs)
                     && (abs(target.y - com.y) <= hs)
                     && (abs(target.z - com.z) <= hs);
        float theta_eff = pc.theta;
        if (pc.coherence_theta >= 0.5) {
            float qn = nodeqq[n];
            theta_eff = pc.theta * (1.0 - pc.alpha * (qn - pc.q_cent));
            theta_eff = clamp(theta_eff, 0.3 * pc.theta, 2.0 * pc.theta);
        }
        vec3 d = target - com;
        float ds2 = dot(d, d);
        float sep = sqrt(ds2);
        bool open = valid_children && (!is_leaf)
                && ((hs / max(sep, 1e-30) > theta_eff) || contains);

        if (!open) {
            if (is_leaf && (pc.use_tp < 1.5) && (srcorder[ps] == i)) {
                // Self-exclusion: a source leaf contributes no force.
            } else {
                float R2 = ds2 + eps2_node;
                float invR3 = 1.0 / (R2 * sqrt(R2));
                nx -= W * d.x * invR3;
                ny -= W * d.y * invR3;
                nz -= W * d.z * invR3;
                vec3 qd = vec3(q0.x * d.x + q0.y * d.y + q0.z * d.z,
                               q0.y * d.x + q0.w * d.y + q1.x * d.z,
                               q0.z * d.x + q1.x * d.y + q1.y * d.z);
                float dqd = dot(d, qd);
                float R2q = ds2 + eps2_node;
                float invR7 = 1.0 / (R2q * R2q * R2q * sqrt(R2q));
                vec3 quad = (R2q * qd - 2.5 * dqd * d) * invR7;
                nx += quad.x; ny += quad.y; nz += quad.z;
                float a0 = length(vec3(nx, ny, nz));
                float aC = 40.0 * ncf[0].w;
                if (a0 > aC) {
                    float sc = aC / a0;
                    nx *= sc; ny *= sc; nz *= sc;
                }
            }
            interactions++;
            if (escape < -1 || escape >= nc) {
                atomicAdd(ctr[7], 1u);
                break;
            }
            n = escape;
        } else {
            // Descend to the highest child: same order as push-ascending/
            // pop-LIFO in the original walk.
            n = cbase + ccount - 1;
        }
    }
    acc[i] = vec4(nx, ny, nz, 0.0);
    inter[i] = interactions;
}

void main() {
    force_main();
}
