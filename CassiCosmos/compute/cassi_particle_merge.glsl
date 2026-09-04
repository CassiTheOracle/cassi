#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 26 floats (104 B); set 0: bindings 0-29
#version 450
// Cassi Particle Merge — "dust -> object": two particles within a merge
// radius R_m coalesce (mass + total momentum conserved, survivor = mass-
// weighted centroid). Redesign per coherence_merge_rnd.md §3 (2026-08-15):
// the qualified-pair test is now LAYERED criteria, most-restrictive wins:
//
//   1. min-image distance d(i,j) <= R_m                          (kept)
//   2. ORDER-SELECTIVE coherence gate (§3a): q_sel = q_coh · q_ord > φ⁻²,
//      q_coh = ρ²/(ρ²+φ⁻²+ε²)  (kept — the bounded condensation barrier),
//      q_ord = 1/(1 + φ²·⟨|∇Σ|²⟩/(⟨Σ²⟩+φ⁻²)),  Σ = EY+φEI — the coherent
//      (φ-locked) combination, gradient via central differences at ±1 cell.
//      Scale-invariant: rewards smooth phase-locked order over loud noise.
//      Flag f_order off → q_sel = q_coh (the legacy amplitude gate).
//   3. GRAVITATIONAL BINDING (§3b, always on): ½μ|v_rel|²·d < G·m₁m₂,
//      G = G_N (NEWTONIAN). The q_sel coherence gate above carries the full
//      Cassi selection (only q > φ⁻² regions arm a merge); the mechanical
//      two-particle binding question is physical, so it uses Newtonian G —
//      NOT the φ⁶-amplified coupling the nbody force applies to the BULK
//      dynamics. Amplifying the pair binding on top of the coherence gate
//      double-counted coherence and coalesced structures the cloud's own
//      dynamics hold (measured: a Newtonian-supported rotating ring coalesced
//      4000→194 at φ⁶ vs 4000→3930 at Newtonian). Unbound pairs never merge —
//      no artificial cooling.
//   4. SUBSONIC INFLOW (§3b, hypothesis; flag f_subsonic): |v_t| < c_s,
//      v_t = v_rel − (v_rel·d̂)d̂, c_s = h₀/dt — the ρ-wave (coherence) phase
//      speed: sound is waves of coherence (see research/sound_coherence_note.md §2).
//      Supersonic transverse fly-bys do not merge.
//   plus the VIRIAL STOPPING SCALE (§3c, hypothesis; flag f_virial): a
//      target with 2·K ≥ |W| — K = ½L²/(mR²) + ½m|v−v_flow|² (v_flow =
//      the two-fluid's per-cell flow velocity, trilinear), W = −G·m²/(2R),
//      G = G_N (Newtonian, matching the binding gate),
//      R = clamp(SIZE_K·m^(1/3), SIZE_S_MIN, SIZE_S_MAX) — is a relaxed,
//      self-supporting object and stops accepting infall.
//      NOTE: coherence_merge_rnd.md §3c wrote the stopping inequality as
//      2K < |W|; that form blocks cold clumps (2K = 0) from ever accreting.
//      The corrected criterion is 2K ≥ |W| (virialised ≈ self-supporting);
//      this shader implements the corrected form.
//
// ANGULAR MOMENTUM (§3c): each hop transfers spin[i] + μ·(pos_i−pos_b)×
// (v_i−v_b) into spin[b] — the pair's orbital L about its center of mass
// becomes the survivor's spin. μ reads mass[b] concurrently with other
// forwarders' atomicAdds (SINK rule guarantees no thread merges INTO a
// forwarder), so Σ(m·p×v + spin) about the origin is conserved to the
// fp-atomic ordering tolerance (ulp-scale bias ≪ the 1e-3 verify gate).
// On merge the survivor is the LOWEST-INDEX member of each connected
// qualified cluster; position = mass-weighted centroid, velocity =
// momentum-weighted mean. Dissipation of the pair's relative KE is implicit
// (the merge is momentum-only — the inelastic content is the lost pair KE,
// left to RealSim's mode-4 drag/viscosity/friction per the design).
//
// GPU pair-resolution (race-free by the SINK rule, see design §5):
// each "cycle" = (fold, count, fill, best, hop)
//   fold  survivors take their accumulated centroid/momentum
//   count+fill  rebuild the spatial hash (cells are at least R_m wide)
//   best  small gates exhaust their 27-cell neighborhood; live clouds
//         time-slice one (neighbor cell, entry) phase per cadence
//   sink  sink[i] = (best[i] == i) — i has no LOWER qualified neighbor
//   hop   i merges into best[i] ONLY IF sink[best[i]] (a receiver is never
//         also a forwarder in the same cycle -> momentum/mass conserved).
// Large-cloud phase state persists across cadences, so every occupied entry
// is revisited without putting the full pair search in one TDR-sized dispatch.
// Finalize writes survivor masses to pos.w and zeroes dead slots; deposit,
// instancer, and nbody already skip mass <= 0.
//
// ONE shader, pass_mode selector (mirrors cassi_nbody_gravity.glsl), with
// ONE persistent per-particle state family (alive/mass/mom/cen/spin) plus
// the hash/list/sink scratch. Float atomics require
// GL_EXT_shader_atomic_float (already verified on this RX 7900 XTX /
// Godot 4.7 by cassi_mass_deposit.glsl and the original merge hop).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

// ── Set 0 ───────────────────────────────────────────────────────────────
layout(set = 0, binding = 0, std430) restrict buffer Positions { vec4 pos[]; };   // xyz, w=mass
layout(set = 0, binding = 1, std430) restrict buffer Velocities { vec4 vel[]; };  // xyz
layout(set = 0, binding = 2, std430) coherent buffer Alive   { float alive[]; };  // 1 / 0
layout(set = 0, binding = 3, std430) coherent buffer Mass    { float mass[]; };   // canonical mass
layout(set = 0, binding = 4, std430) coherent buffer Mom     { vec4 mom[]; };     // xyz=Sigma m v, w=spare (F6: receive-counter removed)
layout(set = 0, binding = 5, std430) coherent buffer Cen     { vec4 cen[]; };     // xyz=Sigma m p, w=spare
layout(set = 0, binding = 6, std430) readonly buffer FieldEY { float ey[]; };     // coherence source
layout(set = 0, binding = 7, std430) readonly buffer FieldEI { float ei[]; };
layout(set = 0, binding = 8, std430) coherent buffer BestBuf { int best[]; };     // chosen target (sink machinery)
layout(set = 0, binding = 9, std430) coherent buffer SinkBuf { float sink[]; };   // sink[i] = (best[i]==i)
layout(set = 0, binding = 10, std430) coherent buffer CellCount { uint cc[]; };   // spatial-hash cells
layout(set = 0, binding = 11, std430) readonly buffer CellStart { uint cs[]; };
layout(set = 0, binding = 12, std430) coherent buffer CellHead  { uint ch[]; };   // running fill index
layout(set = 0, binding = 13, std430) coherent buffer CellList  { uint cl[]; };
layout(set = 0, binding = 14, std430) coherent buffer MergeCount { uint mc[16]; }; // per-cycle merge counts (16 slots = MERGE_MAX_CYCLES)
layout(set = 0, binding = 15, std430) coherent buffer SpinBuf { vec4 spin[]; };   // xyz = accumulated spin (angular momentum), w spare
layout(set = 0, binding = 16, std430) readonly buffer FieldVel { vec4 fvel[]; }; // xyz = flow velocity (two-fluid per-cell vec4), w = eps2
layout(set = 0, binding = 17, std430) buffer MassPrev { float mprev[]; }; // pre-hop canonical mass (stashed by pass_fold, read by hop)
// ── Boxless site read set (boxless_field AND particle_merge; merge_boxless_prereg.md) ──
// The move-Voronoi site's cell-averaged field + AREPO gradient + momentum density,
// for a window-independent merge coherence gate. Immutable; zero-cost when unread.
layout(set = 0, binding = 18, std430) readonly buffer ML_Sites { vec4 ml_sites[]; };   // xyz = site position
layout(set = 0, binding = 19, std430) readonly buffer ML_PsiY { float ml_psy[]; };     // cell-averaged EY
layout(set = 0, binding = 20, std430) readonly buffer ML_PsiI { float ml_psi[]; };     // cell-averaged EI
layout(set = 0, binding = 21, std430) readonly buffer ML_GradY { vec4 ml_grad_y[]; };  // AREPO ∇EY (mode-12 solve), .w=1
layout(set = 0, binding = 22, std430) readonly buffer ML_GradI { vec4 ml_grad_i[]; };  // AREPO ∇EI (mode-12 solve), .w=1
layout(set = 0, binding = 23, std430) readonly buffer ML_PiY { float ml_piy[]; };      // site EY momentum
layout(set = 0, binding = 24, std430) readonly buffer ML_PiI { float ml_pii[]; };      // site EI momentum
// Exact accelerated nearest-site query.  The shortlist is forced to contain
// every live site while boxless merge is enabled; .w maps compact slots back
// to the full site-field arrays.  Hash positions are tile-local, while
// SiteHashCfg.xyz carries the tile's world-space center.
layout(set = 0, binding = 25, std430) readonly buffer SiteQueryPositions { vec4 site_query[]; };
layout(set = 0, binding = 26, std430) readonly buffer SiteHashStart { uint site_cell_start[]; };
layout(set = 0, binding = 27, std430) readonly buffer SiteHashSites { uint site_cell_sites[]; };
layout(set = 0, binding = 28, std430) readonly buffer SiteHashCfg { vec4 site_hash_cfg[]; };
layout(set = 0, binding = 29, std430) readonly buffer SiteQueryCount { uint site_query_count[]; };

layout(push_constant, std430) uniform PC {
    float N;             // particle count
    float phi;
    float phi_inv2;      // phi^-2 — the q denominator scale AND default gate
    float q_threshold;   // merge requires q_sel > q_threshold (default phi^-2)
    float R_m;           // merge radius (world units), = Rm_frac * h0
    float extent_x;      // per-axis half-extents (box geometry, GRID_LAYOUT.md)
    float extent_y;
    float extent_z;
    float grid_N;        // field grid resolution (q_coh trilinear sampling)
    float hash_nx;       // spatial-hash grid dims (cells = hash_nx*ny*nz)
    float hash_ny;
    float hash_nz;
    float cell_wx;       // hash cell widths (>= R_m per axis so the 27-ngbr
    float cell_wy;       // covers every in-range pair)
    float cell_wz;
    float pass_mode;     // 0 reset, 1 fold, 2 count, 3 fill, 4 best, 5 hop, 6 finalize
    float g_n;           // calibrated Newton G (bh[1].w — the nbody's own G_N)
    float xi;            // φ⁶ — Qi coupling enhancement
    float h0;            // reference cell = 2·R_m (c_s = h0/dt)
    float dt;            // timestep (c_s = h0/dt)
    //    c_s = h0/dt is the ρ-wave (coherence) phase speed: sound is waves of
    //    coherence (see research/sound_coherence_note.md §2).
    float f_subsonic;    // flag: subsonic-inflow criterion on (>= 1)
    float f_virial;      // flag: virial stopping scale on (>= 1)
    float f_order;       // flag: order-selective gate q_sel = q_coh·q_ord on (>= 1)
    float cyc_slot;      // batched passes: which mc[] slot this cycle's hop increments (0..15)
    float boxless;       // (appended slot 24) 1.0 = site-direct boxless merge read (>= 0.5)
                         // (merge_boxless_prereg.md); 0.0 (default) = grid trilinear.
    float n_sites;       // (appended slot 25) Voronoi site count (nearest-site loop guard).
} pc;

const float PHI_INV2 = 0.3819660112501051;
// Small verification problems scan all 27 cells × 64 entries in one pass.
// Live clouds time-slice one source shard and one neighbor-cell entry. The
// host encodes the 512 × 27 lane in pass_mode's fractional bits and the entry
// round in cyc_slot. Both are exact for the shader's existing float N/index
// range (N < 2^24), so selected slots wrap by actual cell occupancy without
// the old permanent 64-entry truncation. Inactive sources publish themselves
// as sinks, preserving the receiver-not-forwarder invariant while bounding
// expensive site-coherence queries and contended hops to ceil(N/512) active
// sources per pass.
#define MAX_CELL_SCAN 64
#define MERGE_NEIGHBOR_CELLS 27
#define MERGE_SOURCE_SHARDS 512
#define MERGE_PHASE_LANES (MERGE_NEIGHBOR_CELLS * MERGE_SOURCE_SHARDS)
#define MERGE_LANE_DENOMINATOR 16384.0
// Size-by-mass law — mirror of cassi_instancer.glsl SIZE_BY_MASS (same
// constants, "no second convention"): s = clamp(SIZE_K·cbrt(m), MIN, MAX).
const float SIZE_K = 0.62;
const float SIZE_S_MIN = 0.18;
const float SIZE_S_MAX = 5.0;

bool f_subsonic_on() { return pc.f_subsonic >= 1.0; }
bool f_virial_on()   { return pc.f_virial >= 1.0; }
bool f_order_on()    { return pc.f_order >= 1.0; }

int idx3(int i, int j, int k) {
    int N = int(pc.grid_N);
    return i + N * (j + N * k);
}

// ── shared trilinear corner fetch (the nbody's fused world->grid map) ────
void corners_at(vec3 wp, out int c000, out int c100, out int c010, out int c110,
                out int c001, out int c101, out int c011, out int c111,
                out float fx, out float fy, out float fz) {
    int N = int(pc.grid_N);
    float hn = float(N) * 0.5;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    vec3 gc = (wp * inv_ext) * hn + hn;
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));
    fx = gc.x - float(i0);
    fy = gc.y - float(j0);
    fz = gc.z - float(k0);
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;
    c000 = idx3(i0, j0, k0); int c100_ = idx3(i1, j0, k0);
    int c010_ = idx3(i0, j1, k0); int c110_ = idx3(i1, j1, k0);
    int c001_ = idx3(i0, j0, k1); int c101_ = idx3(i1, j0, k1);
    int c011_ = idx3(i0, j1, k1); int c111_ = idx3(i1, j1, k1);
    c100 = c100_; c010 = c010_; c110 = c110_;
    c001 = c001_; c101 = c101_; c011 = c011_; c111 = c111_;
}

// ── Boxless indexed site read (merge_boxless_prereg.md §4) ──────────────
// The production shortlist/hash is rebuilt with every site when boxless merge
// is enabled.  A true point-to-AABB lower bound terminates the expanding-shell
// query only after every unvisited hash region is provably farther away.  This
// keeps the original exact nearest-site contract without the O(site_count)
// loop in every candidate-pair invocation.
float point_aabb_distance2(vec3 p, vec3 lo, vec3 hi) {
    vec3 d = max(max(lo - p, p - hi), vec3(0.0));
    return dot(d, d);
}

float unscanned_site_bound2(vec3 p, ivec3 c0, int ring, int H, vec3 cs, vec3 domain_hi) {
    ivec3 lo_cell = max(c0 - ivec3(ring), ivec3(0));
    ivec3 hi_cell = min(c0 + ivec3(ring), ivec3(H - 1));
    float bound2 = 1e30;
    if (lo_cell.x > 0) {
        bound2 = min(bound2, point_aabb_distance2(
            p, vec3(0.0), vec3(float(lo_cell.x) * cs.x, domain_hi.y, domain_hi.z)));
    }
    if (hi_cell.x < H - 1) {
        bound2 = min(bound2, point_aabb_distance2(
            p, vec3(float(hi_cell.x + 1) * cs.x, 0.0, 0.0), domain_hi));
    }
    if (lo_cell.y > 0) {
        bound2 = min(bound2, point_aabb_distance2(
            p, vec3(0.0), vec3(domain_hi.x, float(lo_cell.y) * cs.y, domain_hi.z)));
    }
    if (hi_cell.y < H - 1) {
        bound2 = min(bound2, point_aabb_distance2(
            p, vec3(0.0, float(hi_cell.y + 1) * cs.y, 0.0), domain_hi));
    }
    if (lo_cell.z > 0) {
        bound2 = min(bound2, point_aabb_distance2(
            p, vec3(0.0), vec3(domain_hi.x, domain_hi.y, float(lo_cell.z) * cs.z)));
    }
    if (hi_cell.z < H - 1) {
        bound2 = min(bound2, point_aabb_distance2(
            p, vec3(0.0, 0.0, float(hi_cell.z + 1) * cs.z), domain_hi));
    }
    return bound2;
}

int nearest_site_exhaustive(vec3 wp, int ns, vec3 center, vec3 ext) {
    int best = -1;
    float best_d2 = 1e30;
    for (int s = 0; s < ns; s++) {
        vec3 sw = ml_sites[s].xyz - ext + center;
        vec3 d = sw - wp;
        float d2 = dot(d, d);
        if (d2 < best_d2 || (d2 == best_d2 && (best < 0 || s < best))) {
            best_d2 = d2;
            best = s;
        }
    }
    return best;
}

int nearest_site(vec3 wp) {
    int ns = int(pc.n_sites);
    if (ns <= 0) return -1;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec4 cfg = site_hash_cfg[0];
    vec3 center = cfg.xyz;
    int nq = int(site_query_count[0]);
    if (nq != ns || cfg.w <= 0.0) {
        return nearest_site_exhaustive(wp, ns, center, ext);
    }

    int H = int(round((2.0 * ext.x) / cfg.w));
    if (H <= 0) return nearest_site_exhaustive(wp, ns, center, ext);
    vec3 domain_hi = 2.0 * ext;
    vec3 cs_site = domain_hi / float(H);
    vec3 tile_wp = wp - center + ext;
    ivec3 c0 = clamp(ivec3(floor(tile_wp / cs_site)), ivec3(0), ivec3(H - 1));
    int best = -1;
    float best_d2 = 1e30;

    for (int ring = 0; ring < H; ring++) {
        for (int dz = -ring; dz <= ring; dz++) {
            for (int dy = -ring; dy <= ring; dy++) {
                for (int dx = -ring; dx <= ring; dx++) {
                    if (max(max(abs(dx), abs(dy)), abs(dz)) != ring) continue;
                    ivec3 hc = c0 + ivec3(dx, dy, dz);
                    if (any(lessThan(hc, ivec3(0))) || any(greaterThanEqual(hc, ivec3(H)))) continue;
                    int cell = hc.x + H * (hc.y + H * hc.z);
                    uint begin = site_cell_start[cell];
                    uint end = site_cell_start[cell + 1];
                    for (uint at = begin; at < end; at++) {
                        uint slot = site_cell_sites[at];
                        if (slot >= uint(nq)) continue;
                        int s = int(round(site_query[slot].w));
                        if (s < 0 || s >= ns) continue;
                        vec3 sw = site_query[slot].xyz - ext + center;
                        vec3 d = sw - wp;
                        float d2 = dot(d, d);
                        if (d2 < best_d2 || (d2 == best_d2 && (best < 0 || s < best))) {
                            best_d2 = d2;
                            best = s;
                        }
                    }
                }
            }
        }
        // Strict inequality preserves the lowest-index tie rule.
        if (best >= 0 && best_d2 < unscanned_site_bound2(
                tile_wp, c0, ring, H, cs_site, domain_hi)) {
            return best;
        }
    }
    return best >= 0 ? best : nearest_site_exhaustive(wp, ns, center, ext);
}
bool boxless_on() { return pc.boxless >= 0.5; }

// ── q_coh at a world point (nbody's fused trilinear EY/EI map) ──────────
float qcoh_at(vec3 wp) {
    if (boxless_on()) {
        int s = nearest_site(wp);
        if (s < 0) return 0.0;
        float e0 = ml_psy[s];
        float ei0 = ml_psi[s];
        float rho = e0 + ei0;
        float eps = e0 - pc.phi * ei0;
        return (rho * rho) / (rho * rho + PHI_INV2 + eps * eps);
    }
    int c000, c100, c010, c110, c001, c101, c011, c111;
    float fx, fy, fz;
    corners_at(wp, c000, c100, c010, c110, c001, c101, c011, c111, fx, fy, fz);
    float e0 = mix(mix(mix(ey[c000], ey[c100], fx), mix(ey[c010], ey[c110], fx), fy),
                   mix(mix(ey[c001], ey[c101], fx), mix(ey[c011], ey[c111], fx), fy), fz);
    float ei0 = mix(mix(mix(ei[c000], ei[c100], fx), mix(ei[c010], ei[c110], fx), fy),
                    mix(mix(ei[c001], ei[c101], fx), mix(ei[c011], ei[c111], fx), fy), fz);
    float rho = e0 + ei0;
    float eps = e0 - pc.phi * ei0;
    return (rho * rho) / (rho * rho + PHI_INV2 + eps * eps);
}

// ── Σ = EY + φ·EI at a world point (the coherent φ-locked combination) ───
float sigma_at(vec3 wp) {
    if (boxless_on()) {
        int s = nearest_site(wp);
        if (s < 0) return 0.0;
        return ml_psy[s] + pc.phi * ml_psi[s];
    }
    int c000, c100, c010, c110, c001, c101, c011, c111;
    float fx, fy, fz;
    corners_at(wp, c000, c100, c010, c110, c001, c101, c011, c111, fx, fy, fz);
    float e0 = mix(mix(mix(ey[c000], ey[c100], fx), mix(ey[c010], ey[c110], fx), fy),
                   mix(mix(ey[c001], ey[c101], fx), mix(ey[c011], ey[c111], fx), fy), fz);
    float ei0 = mix(mix(mix(ei[c000], ei[c100], fx), mix(ei[c010], ei[c110], fx), fy),
                    mix(mix(ei[c001], ei[c101], fx), mix(ei[c011], ei[c111], fx), fy), fz);
    return e0 + pc.phi * ei0;
}

// ── two-fluid flow velocity (vec4 xyz) at a world point ─────────────────
vec3 flow_at(vec3 wp) {
    if (boxless_on()) {
        // Site-resident flow: the site's own velocity implied by its momentum
        // density, v = (pi_y + pi_i)/ρ — the exact quantity the site leapfrog's
        // steering uses (cassi_voronoi_cells.glsl mode 4 `vv = lam·(pi+pi)/rho`).
        int s = nearest_site(wp);
        if (s < 0) return vec3(0.0);
        float rho = max(ml_psy[s] + ml_psi[s], 1e-9);
        return (ml_piy[s] + ml_pii[s]) / rho * vec3(1.0);
    }
    int c000, c100, c010, c110, c001, c101, c011, c111;
    float fx, fy, fz;
    corners_at(wp, c000, c100, c010, c110, c001, c101, c011, c111, fx, fy, fz);
    return mix(mix(mix(fvel[c000].xyz, fvel[c100].xyz, fx), mix(fvel[c010].xyz, fvel[c110].xyz, fx), fy),
               mix(mix(fvel[c001].xyz, fvel[c101].xyz, fx), mix(fvel[c011].xyz, fvel[c111].xyz, fx), fy), fz);
}

// ── q_ord: order selectivity (§3a) — scale-invariant gradient ratio ─────
// 1 for a locally smooth Σ (standing wave / condensate), →0 for rough noise.
float qord_at(vec3 wp) {
    if (boxless_on()) {
        // Site-resident order: the AREPO face-normal gradient (the mode-12
        // least-squares solve, exact for linear fields) at the containing site.
        // ∇Σ = ∇EY + φ·∇EI; Σ = EY + φ·EI — the identical ratio, site-resident.
        int s = nearest_site(wp);
        if (s < 0) return 0.0;
        float sigma = ml_psy[s] + pc.phi * ml_psi[s];
        vec3 g = ml_grad_y[s].xyz + pc.phi * ml_grad_i[s].xyz;
        float grad2 = dot(g, g);
        return 1.0 / (1.0 + pc.phi * pc.phi * grad2 / (sigma * sigma + PHI_INV2));
    }
    int N = int(pc.grid_N);
    float hn = float(N) * 0.5;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 h = ext / hn;   // one grid cell per axis (2·extent/N)
    float dxs = (sigma_at(wp + vec3(h.x, 0.0, 0.0)) - sigma_at(wp - vec3(h.x, 0.0, 0.0))) / (2.0 * h.x);
    float dys = (sigma_at(wp + vec3(0.0, h.y, 0.0)) - sigma_at(wp - vec3(0.0, h.y, 0.0))) / (2.0 * h.y);
    float dzs = (sigma_at(wp + vec3(0.0, 0.0, h.z)) - sigma_at(wp - vec3(0.0, 0.0, h.z))) / (2.0 * h.z);
    float grad2 = dxs * dxs + dys * dys + dzs * dzs;
    // local mean Σ² over the midpoint cell's 8 corners
    int c000, c100, c010, c110, c001, c101, c011, c111;
    float fx, fy, fz;
    corners_at(wp, c000, c100, c010, c110, c001, c101, c011, c111, fx, fy, fz);
    float s000 = ey[c000] + pc.phi * ei[c000];
    float s100 = ey[c100] + pc.phi * ei[c100];
    float s010 = ey[c010] + pc.phi * ei[c010];
    float s110 = ey[c110] + pc.phi * ei[c110];
    float s001 = ey[c001] + pc.phi * ei[c001];
    float s101 = ey[c101] + pc.phi * ei[c101];
    float s011 = ey[c011] + pc.phi * ei[c011];
    float s111 = ey[c111] + pc.phi * ei[c111];
    float s2 = (s000 * s000 + s100 * s100 + s010 * s010 + s110 * s110
              + s001 * s001 + s101 * s101 + s011 * s011 + s111 * s111) / 8.0;
    return 1.0 / (1.0 + pc.phi * pc.phi * grad2 / (s2 + PHI_INV2));
}

// ── virial stopping scale (§3c, corrected inequality): a target with
// 2K >= |W| is relaxed/self-supporting and stops accepting infall ────────
bool virialized(int j) {
    float mj = mass[j];
    if (mj <= 0.0) return false;
    float Rj = clamp(SIZE_K * pow(mj, 1.0 / 3.0), SIZE_S_MIN, SIZE_S_MAX);
    // NOTE (F11): spin[j] is as-of-the-last HOP (fold→hop each cycle merges
    // new orbital L into spin only in pass_hop). The one-cycle lag is
    // intentional for the "self-supporting snapshot" heuristic: a target is
    // judged from the spin it carried into this hop, not spin that arrives
    // this same cycle — no thread-supplied post-increment sees its own gain.
    vec3 Lj = spin[j].xyz;
    vec3 dv = vel[j].xyz - flow_at(pos[j].xyz);
    float K = 0.5 * dot(Lj, Lj) / (mj * Rj * Rj) + 0.5 * mj * dot(dv, dv);
    // G = g_n: the stopping scale uses the SAME Newtonian gravity as the
    // binding gate (a pair that binds at G binds at the same W). If this
    // used the φ⁶-amplified coupling, W would be 19× larger and the
    // self-support threshold 2K ≥ W would be ~19× harder to reach — the
    // structural never-trip the cascade exploited.
    float gj = pc.g_n;
    float W = gj * mj * mj / (2.0 * Rj);
    return 2.0 * K >= W;
}

// Boxless sites live in unbounded world coordinates. The grid path is the
// periodic particle domain and therefore uses its minimum-image separation.
vec3 sep(vec3 a, vec3 b) {
    vec3 d = a - b;
    if (boxless_on()) return d;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    d -= round(d / (2.0 * ext)) * (2.0 * ext);
    return d;
}

// Midpoint on the same periodic image used by sep(). Arithmetic (a+b)/2 is
// wrong for a pair straddling opposite faces: it lands near the box center
// and samples unrelated coherence. Keep points in [-extent,+extent).
vec3 wrap_point(vec3 wp) {
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 period = 2.0 * ext;
    return wp - floor((wp + ext) / period) * period;
}

// ── spatial-hash cell of a world point (mass-deposit world->grid map).
// WRAP-AWARE (F4): each axis wraps, ((int(floor(...)) % n) + n) % n, so a pair
// within R_m across opposite box faces maps into the wrapped 27-neighbor
// window — sep() uses periodic min-image, so the OLD clamped cell_of could
// miss in-range pairs at the box faces. The wrapped index is always in
// [0, n), hence in-bounds; hash buffer sizes are unchanged. A particle exactly
// at +extent wraps to cell 0, consistent with sep's min-image (0 separation).
int cell_of(vec3 wp) {
    int nx = int(pc.hash_nx), ny = int(pc.hash_ny), nz = int(pc.hash_nz);
    int cx = int(floor((wp.x + pc.extent_x) / pc.cell_wx));
    int cy = int(floor((wp.y + pc.extent_y) / pc.cell_wy));
    int cz = int(floor((wp.z + pc.extent_z) / pc.cell_wz));
    cx = ((cx % nx) + nx) % nx;
    cy = ((cy % ny) + ny) % ny;
    cz = ((cz % nz) + nz) % nz;
    return cx + nx * (cy + ny * cz);
}

// ── pass 0: reset fold accumulators; preserve canonical spin on live slots ──
void pass_reset() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    alive[i] = pos[i].w > 0.0 ? 1.0 : 0.0;
    mass[i] = pos[i].w;
    // canonical momentum & centroid numerators (fold on cycle 1 is identity)
    mom[i] = vec4(vel[i].xyz * pos[i].w, 0.0);
    cen[i] = vec4(pos[i].xyz * pos[i].w, 0.0);
    if (pos[i].w <= 0.0) {
        spin[i] = vec4(0.0);
    } else {
        spin[i].w = 0.0;
    }
    best[i] = int(i);
    sink[i] = 1.0;
    if (i == 0u) { for (int k = 0; k < 16; k++) mc[k] = 0u; cc[0] = 0u; }
}

// ── pass 1: fold accumulated gains into canonical pos/vel (identity on
// the first cycle because reset zeroed mom/cen) ──────────────────────────
void pass_fold() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] > 0.5 && mass[i] > 0.0) {
        vec3 p = cen[i].xyz / mass[i];
        if (!boxless_on()) p = wrap_point(p);
        vec3 v = mom[i].xyz / mass[i];
        pos[i] = vec4(p, pos[i].w);
        vel[i] = vec4(v, 0.0);
        // re-base the running accumulation on the folded canonical state so
        // every cycle's fold is a faithful restart (idempotent in exact fp)
        mom[i] = vec4(v * mass[i], 0.0);
        cen[i] = vec4(p * mass[i], 0.0);
        // stash the pre-hop canonical mass: hop computes the pair's reduced
        // mass μ from mprev[b] (b's mass at the START of the hop pass), so the
        // spin transfer is exact regardless of concurrent forwarders' atomic
        // order — no post-increment mass is ever read into μ.
        mprev[i] = mass[i];
    }
}

// ── pass 2: count alive particles into their hash cell ──────────────────
void pass_count() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] > 0.5) {
        atomicAdd(cc[cell_of(pos[i].xyz)], 1u);
    }
}

// ── pass 3: fill the per-cell particle lists (the GPU exclusive scan
// produced cellStart; ch is the running fill head) ───────────────────────
void pass_fill() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] > 0.5) {
        int c = cell_of(pos[i].xyz);
        uint slot = atomicAdd(ch[c], 1u);
        cl[slot] = i;
    }
}

// ── pass 4: best[i] = min index over qualified alive neighbors; sink[i] =
// (best[i] == i). Scans the WRAP-AWARE 27-cell neighborhood (cells sized >= R_m
// so it provably covers every in-range pair, including pairs straddling the
// periodic box faces — the F4 wrap-aware cell_of/neighborhood closes that
// coverage hole). Qualified = distance ∧ q_sel gate ∧ gravitational binding ∧
// (subsonic inflow) ∧ (target not virialised). ───
void pass_best() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] < 0.5) { sink[i] = 0.0; best[i] = int(i); return; }
    bool time_sliced = int(pc.N) > MAX_CELL_SCAN;
    int phase_lane = clamp(int(round(fract(pc.pass_mode) * MERGE_LANE_DENOMINATOR)),
                           0, MERGE_PHASE_LANES - 1);
    int selected_cell = phase_lane % MERGE_NEIGHBOR_CELLS;
    int selected_shard = phase_lane / MERGE_NEIGHBOR_CELLS;
    int selected_round = max(int(pc.cyc_slot), 0);
    // An inactive source is a sink for this phase: it may receive, but cannot
    // forward, so active sources retain the same race-free hop invariant.
    if (time_sliced && int(i) % MERGE_SOURCE_SHARDS != selected_shard) {
        best[i] = int(i);
        sink[i] = 1.0;
        return;
    }
    int nx = int(pc.hash_nx), ny = int(pc.hash_ny), nz = int(pc.hash_nz);
    // own cell via the SAME wrapped formula as cell_of (F4) — decompose the
    // packed wrapped index so the neighborhood below wraps per axis too.
    int cself = cell_of(pos[i].xyz);
    int ci = cself % nx;
    int cj = (cself / nx) % ny;
    int ck = cself / (nx * ny);
    int ibest = int(i);
    vec3 pi = pos[i].xyz;
    float mi = mass[i];
    float r_m2 = pc.R_m * pc.R_m;
    int neighbor_index = 0;
    // Cell 0 is the particle's own cell; cells 1..26 are the surrounding
    // shell. Large clouds evaluate one (cell,entry) phase per cadence, while
    // small-N gates retain the original exhaustive scan.
    for (int ring = 0; ring <= 1; ring++) {
        for (int dx = -ring; dx <= ring; dx++) {
            for (int dy = -ring; dy <= ring; dy++) {
                for (int dz = -ring; dz <= ring; dz++) {
                    if (max(max(abs(dx), abs(dy)), abs(dz)) != ring) continue;
                    bool visit_cell = !time_sliced || neighbor_index == selected_cell;
                    neighbor_index++;
                    if (!visit_cell) continue;
                    int cx = (ci + dx + nx) % nx;
                    int cy = (cj + dy + ny) % ny;
                    int cz = (ck + dz + nz) % nz;
                    int c = cx + nx * (cy + ny * cz);
                    int ncnt = int(cc[c]);
                    if (ncnt <= 0) continue;
                    int first = time_sliced ? (selected_round % ncnt) : 0;
                    int last = time_sliced ? (first + 1) : min(ncnt, MAX_CELL_SCAN);
                    for (int k = first; k < last; k++) {
                        int j = int(cl[int(cs[c]) + k]);
                        // Only a lower index can become this particle's sink.
                        if (j >= int(i) || alive[j] < 0.5) continue;
                        float mj = mass[j];
                        if (mj <= 0.0) continue;
                        vec3 pj = pos[j].xyz;
                        vec3 dsep = sep(pi, pj);
                        float d2 = dot(dsep, dsep);
                        if (d2 <= 0.0 || d2 > r_m2) continue;
                        float d = sqrt(d2);
                        // Reject mechanically impossible pairs before querying
                        // the field. This exact reordering keeps expensive site
                        // queries off the overwhelmingly unbound live cloud.
                        vec3 vr = vel[i].xyz - vel[j].xyz;
                        float mu = (mi * mj) / (mi + mj);
                        float g_eff = pc.g_n;
                        if (0.5 * mu * dot(vr, vr) * d >= g_eff * mi * mj) continue;
                        // subsonic inflow: |v_t| < c_s = h0/dt
                        if (f_subsonic_on()) {
                            vec3 dh = dsep / d;
                            vec3 vt = vr - dot(vr, dh) * dh;
                            if (length(vt) >= pc.h0 / max(pc.dt, 1e-9)) continue;
                        }
                        vec3 mid = boxless_on()
                            ? 0.5 * (pi + pj)
                            : wrap_point(pi - 0.5 * dsep);
                        // q_coh is cheaper than q_ord. Since q_ord <= 1, a
                        // failing q_coh can never pass the product gate.
                        float qm = qcoh_at(mid);
                        if (qm <= pc.q_threshold) continue;
                        // KEEP the product check: q_ord can pull an otherwise
                        // passing q_coh below the threshold.
                        float qg = qm;
                        if (f_order_on()) qg = qm * qord_at(mid);
                        if (qg <= pc.q_threshold) continue;
                        // virial stopping scale: skip relaxed targets
                        if (f_virial_on() && virialized(j)) continue;
                        if (j < ibest) ibest = j;
                    }
                }
            }
        }
    }
    best[i] = ibest;
    sink[i] = (ibest == int(i)) ? 1.0 : 0.0;
}

// ── pass 5: hop — i merges into best[i] ONLY IF it is a sink (cannot
// itself forward this cycle), so receivers are never forwarders -> the
// merge conserves mass + momentum. Transfers are float atomics; the spin
// transfer adds the pair's orbital angular momentum about its COM. ───────
void pass_hop() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] < 0.5) return;
    int b = best[i];
    if (b >= int(i)) return;                       // no lower qualified neighbor
    if (sink[b] < 0.5) return;                     // target would forward this cycle
    // transfer i's FULL canonical state into b (b survives this cycle)
    atomicAdd(mass[b], mass[i]);
    vec3 mv = mass[i] * vel[i].xyz;
    atomicAdd(mom[b].x, mv.x);
    atomicAdd(mom[b].y, mv.y);
    atomicAdd(mom[b].z, mv.z);
    // mom/best .w and cen .w are SPARE (never read anywhere — F6 removed the
    // old mom[b].w receive-counter atomicAdd). The vec4 slots are kept so the
    // buffer/PC layout needs no renumbering. Accumulate i on the periodic
    // image nearest b; raw coordinates would send a seam-straddling pair's
    // centroid through the box center.
    vec3 dsep = sep(pos[i].xyz, pos[b].xyz);
    vec3 pi_image = boxless_on() ? pos[i].xyz : pos[b].xyz + dsep;
    vec3 mp = mass[i] * pi_image;
    atomicAdd(cen[b].x, mp.x);
    atomicAdd(cen[b].y, mp.y);
    atomicAdd(cen[b].z, mp.z);
    // spin: i's accumulated spin + the pair's orbital L about its COM.
    // μ uses the SURVIVOR's pre-hop mass (mprev[b], stashed at fold) so the
    // transfer is exact and independent of concurrent forwarders' ordering.
    vec3 vr = vel[i].xyz - vel[b].xyz;
    float mi = mass[i];
    float mb = mprev[b];
    float mu = (mi * mb) / max(mi + mb, 1e-30);
    vec3 dL = mu * cross(dsep, vr) + spin[i].xyz;
    atomicAdd(spin[b].x, dL.x);
    atomicAdd(spin[b].y, dL.y);
    atomicAdd(spin[b].z, dL.z);
    alive[i] = 0.0;
    atomicAdd(mc[clamp(int(pc.cyc_slot + 0.5), 0, 15)], 1u);
}

// ── pass 7: zero the spatial-hash cell counts (cc) for THIS cycle. The
// batched merge runs several cycles in ONE compute list (per-cycle barriers
// give visibility), so the host can no longer re-zero cc between cycles —
// the zero moves on-GPU. N_particles threads stride over the hash (each
// thread zeroes ceil(hash_total / N_particles) cells worst-case).
void pass_zerocc() {
    uint i = gl_GlobalInvocationID.x;
    uint ht = uint(pc.hash_nx * pc.hash_ny * pc.hash_nz);
    uint n = uint(max(int(pc.N), 1));
    for (uint c = i; c < ht; c += n) cc[c] = 0u;
}

// ── pass 8: ANY-CANDIDATE early-out (perf-decomp 2026-08-15, STEP 1) —
// ONE dispatch, no hash, no scan: cc[0] = 1 iff ANY alive mass>0 particle
// sits at q_coh(pos) > q_threshold (φ⁻²). The pair gate requires q_sel(mid)
// > q_threshold and qord <= 1, so q_coh(mid) > φ⁻² is NECESSARY for any
// merge; the host reads cc[0] (4 B) and, on 0, skips the whole
// fold→zero-cc→count→scan→fill→best→hop chain + the per-cycle count
// readbacks — the ~40-dispatch burst that starves the shared three-RD GPU
// on near-empty (diffuse) passes. cc[0] is borrowed: pass_zerocc clears it
// before any count, pass_reset zeroes it, and nothing else reads it here.
// Exactness: a skipped pass only DELAYS a merge (state is untouched) — the
// next cadenced pass re-tests. (Sub-cell ε-cancellation could theoretically
// raise the pair-midpoint q above both particles' own q; the worst case is
// one pass of delay, never corruption.)
void pass_anyq() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] < 0.5) return;   // dead particles never merge
    if (mass[i] <= 0.0) return;   // zero-mass cannot bind
    if (qcoh_at(pos[i].xyz) > pc.q_threshold) {
        atomicOr(cc[0], 1u);
    }
}

// ── pass 6: finalize — write survivor masses into pos.w (0 = dead) so the
// deposit/instancer/nbody pick up the merged state with NO further edits. ─
void pass_finalize() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] > 0.5 && mass[i] > 0.0) {
        vec3 p = cen[i].xyz / mass[i];
        if (!boxless_on()) p = wrap_point(p);
        pos[i] = vec4(p, mass[i]);
        vel[i] = vec4(mom[i].xyz / mass[i], 0.0);
    } else {
        pos[i] = vec4(pos[i].xyz, 0.0);                 // dead: zero mass
    }
}

void main() {
    int m = int(pc.pass_mode); // fractional bits encode large-N neighbor cell
    if (m == 0) { pass_reset(); return; }
    if (m == 1) { pass_fold(); return; }
    if (m == 2) { pass_count(); return; }
    if (m == 3) { pass_fill(); return; }
    if (m == 4) { pass_best(); return; }
    if (m == 5) { pass_hop(); return; }
    if (m == 6) { pass_finalize(); return; }
    if (m == 7) { pass_zerocc(); return; }
    if (m == 8) { pass_anyq(); return; }
}
