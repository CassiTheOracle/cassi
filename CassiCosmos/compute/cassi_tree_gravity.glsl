#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 5 floats (20 B); set 0: bindings 0,3-11
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
// One thread per TARGET with an explicit per-thread LIFO stack (fixed-size
// local array of depth STACK_MAX). Wait — this shader's job is the walk:
//
//   while stack not empty:
//     n = pop
//     d = target − COM_n ; sep = |d| ; half = node_half
//     contains = (|target − center_n| ≤ half per axis)     // COM-based: d
//     open = (leaf ? false : ( (half/sep > theta) || contains ) )
//     accept:  add monopole −W·d/R³ + quadrupole [R²(Q·d) − 5/2(d·Q·d)d]/R⁷
//              from node n's W,COM,Q (R² = d² + eps2; quadrupole unsoftened)
//     self-exclusion: a leaf whose single source IS the target (order[ps]==i)
//              contributes nothing — skip it
//     open: push children [childBase, childBase+childCount)
//
// Hardening rules (fmm_design.md Q2, adopted from the prototype):
//   (1) ALWAYS open a node whose bounding cube contains the target (using
//       the node COM as the box center — matches the prototype exactly; the
//       θ criterion alone can accept a node enclosing the target when
//       θ > 1/√3);
//   (2) leaves are exact point masses, with self-exclusion of the target's
//       own source leaf.
// These are REQUIRED for a correct self-excluding open-field force.
//
// Force formulas (verified in stage5_fpm.py against a 2-mass expansion and
// the direct O(N²) sum; the quadrupole sign is the CORRECT one — the naive
// swap is the negation and made quadrupole WORSE than monopole):
//   monop  = −W·d/(d²+eps2)^(3/2)
//   quad   = ( (d²)·(Q·d) − (5/2)(d·Q·d)·d ) / (d²)^(7/2)
//
// DENSITY-AWARE SOFTENING (2026-08-16, Fix 2): the global PC eps2 alone
// leaves close encounters in a dense/heavy core singular — the per-node
// force cap (below) truncated them, but the kicked particles still deposit
// two-body heating energy and the cloud slowly expands (measured: COM-relative
// rmax grew 267→608 over 1950 frames at the owner's 250k scale after Fix 1
// killed the drift). Each node is therefore softened to the sphere its own
// mass would occupy at UNIT reference density, ε_node = (W)^(1/3),
// ε²_node = pc.eps2 + W^(2/3): a DERIVED adaptive softening (GADGET-style
// ε ∝ (m/ρ_ref)^(1/3), ρ_ref = 1 mass per unit³) that leaves single/dilute
// particles (W≈1, W^(2/3)≈1 << pc.eps2≈324) bit-near-identical to the
// calibrated river while smoothing only heavy/dense nodes (W≫1) that would
// otherwise singularly kick.
//
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
layout(set = 0, binding = 8, std430) readonly buffer Counters { uint ctr[]; };
layout(set = 0, binding = 9, std430) buffer ForceOut { vec4 acc[]; };
layout(set = 0, binding = 10, std430) buffer InterCount { uint inter[]; };
// Optional per-target positions (SIM path): the sim's targets are N-BODY
// PARTICLES whose positions live in the sim's _pos_buf, NOT the mesh-source
// table. When pc.use_tp > 0.5 the walk reads target i from tpos[i].xyz
// (binding 11) instead of src[2i].xyz. verify_fmm leaves the flag off and
// binds a dummy to 11 — its targets ARE the sources.
layout(set = 0, binding = 11, std430) restrict readonly buffer TargetPos { vec4 tpos[]; };

layout(push_constant, std430) uniform PC {
    float N_f;        // #0 target count
    float theta;      // #1 opening criterion (0.5)
    float eps2;       // #2 softening² (1e-6)
    float use_tp;     // #3 target source selector: >0.5 → tpos[i].xyz
                      //     (was an unused `phi` slot; 0 = src[2i], the
                      //     verify/official path — unchanged)
    float node_cnt;   // #4 total octree node count
} pc;

const int STACK_MAX = 64;

void force_main() {
    uint i = gl_GlobalInvocationID.x;
    int N = int(pc.N_f);
    if (int(i) >= N) return;
    vec3 target = (pc.use_tp > 0.5) ? tpos[i].xyz : src[2 * i].xyz;
    float nx = 0.0, ny = 0.0, nz = 0.0;
    uint interactions = 0u;
    int nc = int(pc.node_cnt);

    int stack[STACK_MAX];
    int sp = 0;
    stack[sp++] = 0;                 // root node index 0

    while (sp > 0) {
        int n = stack[--sp];
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
        // Density-aware softening (Fix 2, 2026-08-16): ε²_node = pc.eps2 +
        // W^(2/3) — soften a node to the sphere its mass occupies at unit
        // reference density (GADGET-style ε ∝ (m/ρ)^(1/3)). Single/dilute
        // nodes (W≈1) keep the calibrated global eps2; heavy/dense nodes get
        // extra smoothing against the singular near-field. Per-node, no
        // readback. (W^(2/3) = exp(2/3·ln W); GLSL has no direct cbrt-square.)
        float eps2_node = pc.eps2 + exp((2.0 / 3.0) * log(max(W, 1e-30)));
        vec3 d = target - com;
        float ds2 = dot(d, d);
        float sep = sqrt(ds2);
        // A node is a LEAF iff it has no children (childCount == 0). This
        // correctly treats a MAX_LEVELS-capped cell holding coincident
        // sources (range > 1, never split) as an exact-ish point group, so
        // its mass is NOT dropped. (range==1 == single-particle leaf.)
        bool is_leaf = (ccount == 0);

        // contains: target within `hs` (node half) of the COM on every axis
        // (matches the prototype — the walk uses COM, not the geometric
        // center, for both the θ test and the containment hardening rule)
        bool contains = (abs(d.x) <= hs) && (abs(d.y) <= hs)
                     && (abs(d.z) <= hs);
        bool open = (!is_leaf) && ((hs / max(sep, 1e-30) > pc.theta) || contains);

        if (!open) {
            // self-exclusion: a leaf whose single source IS this target
            if (is_leaf && (srcorder[ps] == i)) {
                // skip the target's own source entirely
            } else {
                // monopole (R² = ds2 + eps2_node — density-aware)
                float R2 = ds2 + eps2_node;
                float invR3 = 1.0 / (R2 * sqrt(R2));
                nx -= W * d.x * invR3;
                ny -= W * d.y * invR3;
                nz -= W * d.z * invR3;
                // quadrupole: [R²(Q·d) − (5/2)(d·Q·d)·d] / (d²)^(7/2)
                // SOFTENED like the monopole (R2q = ds2 + eps2, was max(ds2,
                // 1e-30)): the UNsoftened 1/d⁷ near-field blew up when a
                // particle passed close to a heavy node's COM in the galaxy
                // core — a single encounter produced a huge finite force that
                // ejected the particle and cascaded (2026-08-13 vanish
                // diagnosis; verify_particle_vanish). Softening the quadrupole
                // with the SAME eps2 as the monopole restores bound orbits.
                vec4 q0 = nq[2 * n];
                vec4 q1 = nq[2 * n + 1];
                float Qxx = q0.x; float Qxy = q0.y; float Qxz = q0.z;
                float Qyy = q0.w; float Qyz = q1.x; float Qzz = q1.y;
                vec3 qd = vec3(Qxx * d.x + Qxy * d.y + Qxz * d.z,
                               Qxy * d.x + Qyy * d.y + Qyz * d.z,
                               Qxz * d.x + Qyz * d.y + Qzz * d.z);
                float dqd = dot(d, qd);
                float R2q = ds2 + eps2_node;
                float invR7 = 1.0 / (R2q * R2q * R2q * sqrt(R2q));
                vec3 quad = (R2q * qd - 2.5 * dqd * d) * invR7;
                nx += quad.x; ny += quad.y; nz += quad.z;
                // ── PER-NODE FORCE CAP (2026-08-13) ──────────────────────
                // A heavy/accreted node's monopole+quadrupole near-field can
                // still reach 10⁴–10⁶ tgrad at core-collapse densities even
                // with the eps2 softening (verify_particle_vanish: the fr≈560
                // core formed, then tgrad spiked to ~1e6 and ejected the
                // galaxy). Cap the ACCUMULATED node force at ~40·bhalf (bhalf
                // = root half = the box's max half-extent, ncf[0].w) — far
                // above any physical river force (peak ~2900) so real dynamics
                // are untouched, but it hard-stops a single singular kick from
                // escaping to float-overflow / ejection. Complemented by the
                // KDK |v|/|pos| guard; the walk cap is the targeted Node-side
                // boundary (a smooth field like the river's never exceeds it).
                float a0 = length(vec3(nx, ny, nz));
                float aC = 40.0 * ncf[0].w;                       // A_CAP
                if (a0 > aC) {
                    float sc = aC / a0;
                    nx *= sc; ny *= sc; nz *= sc;
                }
            }
            interactions++;
        } else {
            // push children [cbase, cbase+ccount)
            for (int c = 0; c < ccount; c++) {
                if (sp < STACK_MAX) stack[sp++] = cbase + c;
            }
        }
    }
    acc[i] = vec4(nx, ny, nz, 0.0);
    inter[i] = interactions;
}

void main() {
    force_main();
}
