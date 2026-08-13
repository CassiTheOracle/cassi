#[compute]
#version 450
// Cassi Particle Merge — "dust -> object": two particles within a merge
// radius R_m coalesce (mass + total momentum conserved, survivor = mass-
// weighted centroid) ONLY where the local coherence
//   q_coh = rho^2 / (rho^2 + phi^-2 + eps^2),  rho = EY+EI, eps = EY - phi*EI
// exceeds the phi-anchored threshold phi^-2. This is the particle-level
// complement of the meshless collapse (MESHLESS_PLAN.md §3.3) — the
// field condenses (field -> matter), then this grows matter (matter ->
// object), then BH accretion (object -> BH). Design:
// research/meshless/particle_merge_design.md.
//
// Merge rule (per pair i,j):
//   1. min-image distance d(i,j) <= R_m
//   2. q_coh at the pair midpoint (trilinear EY/EI, nbody sampler
//      convention) > Q_th          (default Q_th = phi^-2 ~ 0.382)
// On merge the survivor is the LOWEST-INDEX member of each connected
// qualified cluster; position = mass-weighted centroid, velocity =
// momentum-weighted mean. Dissipation is deliberately left to RealSim's
// mode-4 drag/viscosity/friction (the merge itself is momentum-only —
// the inelastic content is the implicit loss of the pair's relative KE).
//
// GPU pair-resolution (race-free by the SINK rule, see design §5):
// each "cycle" = (fold, count, fill, best, sink, hop)
//   fold  survivors take their accumulated centroid/momentum
//   count+fill  rebuild the spatial hash (cell grid sized to R_m, the
//               mass-deposit world->grid map convention)
//   best  each alive i records best[i] = min index over qualified neighbors
//   sink  sink[i] = (best[i] == i) — i has no LOWER qualified neighbor
//   hop   i merges into best[i] ONLY IF sink[best[i]] (a receiver is never
//         also a forwarder in the same cycle -> momentum/mass conserved).
// The host loops cycles until mergeCount == 0 (or a cap); finalize writes
// pos.w = survivor masses / 0 for dead (the deposit/instancer/nbody all
// already read pos.w and skip mass <= 0).
//
// ONE shader, pass_mode selector (mirrors cassi_nbody_gravity.glsl), with
// ONE persistent per-particle state family (alive/mass/mom/cen) plus the
// hash/list/sink scratch the wiring wave re-allocates per §1 of the design.
// Float atomics require GL_EXT_shader_atomic_float (already verified on
// this RX 7900 XTX / Godot 4.7 by cassi_mass_deposit.glsl).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

// ── Set 0 ───────────────────────────────────────────────────────────────
layout(set = 0, binding = 0, std430) restrict buffer Positions { vec4 pos[]; };   // xyz, w=mass
layout(set = 0, binding = 1, std430) restrict buffer Velocities { vec4 vel[]; };  // xyz
layout(set = 0, binding = 2, std430) coherent buffer Alive   { float alive[]; };  // 1 / 0
layout(set = 0, binding = 3, std430) coherent buffer Mass    { float mass[]; };   // canonical mass
layout(set = 0, binding = 4, std430) coherent buffer Mom     { vec4 mom[]; };     // xyz=Sigma m v, w=receive-count
layout(set = 0, binding = 5, std430) coherent buffer Cen     { vec4 cen[]; };     // xyz=Sigma m p
layout(set = 0, binding = 6, std430) readonly buffer FieldEY { float ey[]; };     // coherence source
layout(set = 0, binding = 7, std430) readonly buffer FieldEI { float ei[]; };
layout(set = 0, binding = 8, std430) coherent buffer BestBuf { int best[]; };     // chosen target (sink machinery)
layout(set = 0, binding = 9, std430) coherent buffer SinkBuf { float sink[]; };   // sink[i] = (best[i]==i)
layout(set = 0, binding = 10, std430) coherent buffer CellCount { uint cc[]; };   // spatial-hash cells
layout(set = 0, binding = 11, std430) readonly buffer CellStart { uint cs[]; };
layout(set = 0, binding = 12, std430) coherent buffer CellHead  { uint ch[]; };   // running fill index
layout(set = 0, binding = 13, std430) coherent buffer CellList  { uint cl[]; };
layout(set = 0, binding = 14, std430) coherent buffer MergeCount { uint mc; };

layout(push_constant, std430) uniform PC {
    float N;             // particle count
    float phi;
    float phi_inv2;      // phi^-2 — the q denominator scale AND default gate
    float q_threshold;   // merge requires q_coh > q_threshold (default phi^-2)
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
} pc;

const float PHI_INV2 = 0.3819660112501051;

int idx3(int i, int j, int k) {
    int N = int(pc.grid_N);
    return i + N * (j + N * k);
}

// ── q_coh at a world point (nbody's fused trilinear EY/EI map) ──────────
float qcoh_at(vec3 wp) {
    int N = int(pc.grid_N);
    float hn = float(N) * 0.5;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    vec3 gc = (wp * inv_ext) * hn + hn;
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));
    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;
    int c000 = idx3(i0, j0, k0); int c100 = idx3(i1, j0, k0);
    int c010 = idx3(i0, j1, k0); int c110 = idx3(i1, j1, k0);
    int c001 = idx3(i0, j0, k1); int c101 = idx3(i1, j0, k1);
    int c011 = idx3(i0, j1, k1); int c111 = idx3(i1, j1, k1);
    float e0 = mix(mix(mix(ey[c000], ey[c100], fx), mix(ey[c010], ey[c110], fx), fy),
                   mix(mix(ey[c001], ey[c101], fx), mix(ey[c011], ey[c111], fx), fy), fz);
    float ei0 = mix(mix(mix(ei[c000], ei[c100], fx), mix(ei[c010], ei[c110], fx), fy),
                    mix(mix(ei[c001], ei[c101], fx), mix(ei[c011], ei[c111], fx), fy), fz);
    float rho = e0 + ei0;
    float eps = e0 - pc.phi * ei0;
    return (rho * rho) / (rho * rho + PHI_INV2 + eps * eps);
}

// ── min-image separation (periodic box, matching the deposit/nbody wrap) ─
vec3 sep(vec3 a, vec3 b) {
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 d = a - b;
    d -= round(d / (2.0 * ext)) * (2.0 * ext);
    return d;
}

// ── spatial-hash cell of a world point (mass-deposit world->grid map) ───
int cell_of(vec3 wp) {
    int nx = int(pc.hash_nx), ny = int(pc.hash_ny), nz = int(pc.hash_nz);
    int cx = int(clamp(floor((wp.x + pc.extent_x) / pc.cell_wx), 0.0, float(nx - 1)));
    int cy = int(clamp(floor((wp.y + pc.extent_y) / pc.cell_wy), 0.0, float(ny - 1)));
    int cz = int(clamp(floor((wp.z + pc.extent_z) / pc.cell_wz), 0.0, float(nz - 1)));
    return cx + nx * (cy + ny * cz);
}

// ── pass 0: reset the persistent merge state from the src particle mass ──
void pass_reset() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    alive[i] = 1.0;
    mass[i] = pos[i].w;
    // canonical momentum & centroid numerators (fold on cycle 1 is identity)
    mom[i] = vec4(vel[i].xyz * pos[i].w, 0.0);
    cen[i] = vec4(pos[i].xyz * pos[i].w, 0.0);
    best[i] = int(i);
    sink[i] = 1.0;
    if (i == 0u) mc = 0u;
}

// ── pass 1: fold accumulated gains into canonical pos/vel (identity on
// the first cycle because reset zeroed mom/cen) ──────────────────────────
void pass_fold() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] > 0.5 && mass[i] > 0.0) {
        vec3 p = cen[i].xyz / mass[i];
        vec3 v = mom[i].xyz / mass[i];
        pos[i] = vec4(p, pos[i].w);
        vel[i] = vec4(v, 0.0);
        // re-base the running accumulation on the folded canonical state so
        // every cycle's fold is a faithful restart (idempotent in exact fp)
        mom[i] = vec4(v * mass[i], 0.0);
        cen[i] = vec4(p * mass[i], 0.0);
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

// ── pass 3: fill the per-cell particle lists (host ran an exclusive
// prefix-sum on cellCount -> cellStart and copied it into cellHead) ───────
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
// (best[i] == i). Scans the 27-cell neighborhood (cells sized >= R_m so it
// provably covers every in-range pair). ──────────────────────────────────
void pass_best() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] < 0.5) { sink[i] = 0.0; best[i] = int(i); return; }
    int nx = int(pc.hash_nx), ny = int(pc.hash_ny), nz = int(pc.hash_nz);
    int ci = int(clamp(floor((pos[i].x + pc.extent_x) / pc.cell_wx), 0.0, float(nx - 1)));
    int cj = int(clamp(floor((pos[i].y + pc.extent_y) / pc.cell_wy), 0.0, float(ny - 1)));
    int ck = int(clamp(floor((pos[i].z + pc.extent_z) / pc.cell_wz), 0.0, float(nz - 1)));
    int ibest = int(i);
    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            for (int dz = -1; dz <= 1; dz++) {
                int cx = clamp(ci + dx, 0, nx - 1);
                int cy = clamp(cj + dy, 0, ny - 1);
                int cz = clamp(ck + dz, 0, nz - 1);
                int c = cx + nx * (cy + ny * cz);
                int ncnt = int(cc[c]);
                int base = int(cs[c]);
                for (int k = 0; k < ncnt; k++) {
                    int j = int(cl[base + k]);
                    if (j == int(i) || alive[j] < 0.5) continue;
                    if (length(sep(pos[i].xyz, pos[j].xyz)) > pc.R_m) continue;
                    if (qcoh_at((pos[i].xyz + pos[j].xyz) * 0.5) <= pc.q_threshold) continue;
                    if (j < ibest) ibest = j;
                }
            }
        }
    }
    best[i] = ibest;
    sink[i] = (ibest == int(i)) ? 1.0 : 0.0;
}

// ── pass 5: hop — i merges into best[i] ONLY IF it is a sink (cannot
// itself forward this cycle), so receivers are never forwarders -> the
// merge conserves mass + momentum. Transfers are float atomics. ──────────
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
    atomicAdd(mom[b].w, 1.0);
    vec3 mp = mass[i] * pos[i].xyz;
    atomicAdd(cen[b].x, mp.x);
    atomicAdd(cen[b].y, mp.y);
    atomicAdd(cen[b].z, mp.z);
    alive[i] = 0.0;
    atomicAdd(mc, 1u);
}

// ── pass 6: finalize — write survivor masses into pos.w (0 = dead) so the
// deposit/instancer/nbody pick up the merged state with NO further edits. ─
void pass_finalize() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.N)) return;
    if (alive[i] > 0.5 && mass[i] > 0.0) {
        pos[i] = vec4(cen[i].xyz / mass[i], mass[i]);   // folded centroid + mass
        vel[i] = vec4(mom[i].xyz / mass[i], 0.0);
    } else {
        pos[i] = vec4(pos[i].xyz, 0.0);                 // dead: zero mass
    }
}

void main() {
    int m = int(pc.pass_mode + 0.5);
    if (m == 0) { pass_reset(); return; }
    if (m == 1) { pass_fold(); return; }
    if (m == 2) { pass_count(); return; }
    if (m == 3) { pass_fill(); return; }
    if (m == 4) { pass_best(); return; }
    if (m == 5) { pass_hop(); return; }
    if (m == 6) { pass_finalize(); return; }
}
