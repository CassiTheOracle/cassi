#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 3 floats (12 B); set 0: bindings 0-4
#version 450
// Arm 1 (coherence_adaptive_prereg.md): coherence-filtered moving-Voronoi site
// shortlist. On the steer cadence (alongside _mesh_rebuild()), reduces the full
// site mesh (2·16³ = 8192 at N=64) to the COMPACT set of coherent sites
// (q_coh ≥ q_floor = φ⁻² ≈ 0.382) that the per-frame boxless INSTANCER samples.
// The per-particle instancer scan then costs O(shortlist) instead of O(8192) —
// the structured subset, so display cost tracks coherent content, not mesh count.
//
// Two modes (host sets the PC mode field on a per-dispatch basis, the same
// in-list reset+filter pattern as the tree/cell passes):
//   mode 0 = RESET: zero the count (must precede mode 1 in the same list).
//   mode 1 = FILTER+COMPACT: one thread per site; sites with q_coh ≥ q_floor
//            are appended to the shortlist via the atomic count (the prior
//            counter value is the output slot — safe compaction). Writes
//            shortlist[slot] = vec4(site_pos.xyz, float(site_index)); the
//            instancer uses .w as the index into the site psi buffers.
//
// Bounded coherence q_coh = ρ²/(ρ²+φ⁻²+ε²), ρ = EY+EI, ε = EY−φ·EI — the SAME
// formula the instancer's grid path / qhist boxless path use, so the boxless
// instancer hue lands on the identical value the grid path would have produced
// (parity-proven by the §4 Arm 1 probe: site vs grid ≤ 1e-3).
//
// Bindings (set 0): 0 = Voronoi sites (vec4/site: xyz position), 1 = site
// psi_y (float/site), 2 = site psi_i (float/site), 3 = shortlist output
// (vec4[max_sites] — sized for the worst case where every site is coherent),
// 4 = count (uint[1] — atomic compaction cursor / result).
// PC: n_sites (float), q_floor (float, default φ⁻² ≈ 0.382).
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Sites { vec4 site[]; };
layout(set = 0, binding = 1, std430) readonly buffer SitePsiY { float psy[]; };
layout(set = 0, binding = 2, std430) readonly buffer SitePsiI { float psi[]; };
layout(set = 0, binding = 3, std430) buffer Shortlist { vec4 sl[]; };
layout(set = 0, binding = 4, std430) coherent buffer Count { uint cnt; };

layout(push_constant, std430) uniform PC {
    float n_sites;   // site count (8192 at N=64)
    float q_floor;   // coherence filter threshold (φ⁻² ≈ 0.382)
    float mode;      // 0 = reset count, 1 = filter+compact
} pc;

const float PHI = 1.6180339887498949;
const float PHI_INV2 = 0.3819660112501051;

void main() {
    uint gid = gl_GlobalInvocationID.x;
    if (int(pc.mode) == 0) {
        // RESET: thread 0 zeroes the counter.
        if (gid == 0u) { cnt = 0u; }
        return;
    }
    int ns = int(pc.n_sites);
    if (gid >= uint(ns)) return;
    int si = int(gid);
    vec3 p = site[si].xyz;
    float ey = psy[si];
    float ei = psi[si];
    float rho = ey + ei;
    float eps = ey - PHI * ei;
    float rho2 = rho * rho;
    float q = rho2 / (rho2 + PHI_INV2 + eps * eps);
    if (q < pc.q_floor) return;
    // Compact: the atomic prior value is this site's slot in the dense list.
    uint slot = atomicAdd(cnt, 1u);
    if (slot < uint(pc.n_sites)) {
        sl[slot] = vec4(p, float(si));
    }
}
