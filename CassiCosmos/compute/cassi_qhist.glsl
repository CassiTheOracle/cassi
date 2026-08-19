#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 13 floats (52 B); set 0: bindings 0-4
#version 450
// Cassi coherence-histogram — the AUTO-ALIGN sampler. Bins the Qi-rainbow
// observable AT PARTICLE POSITIONS (the exact periodic trilinear convention
// of cassi_instancer.glsl's tri_coherence) into a log-spaced histogram, so
// the host can re-fit the Qi color band to the live p1/p99 spread.
//
// THE TRACKED QUANTITY IS THE PHYSICALLY BOUNDED COHERENCE
//     q_coh = ρ² / (ρ² + φ⁻² + ε²) ,  ρ = EY + EI ,  ε = EY − φ·EI
// — the SAME value the instancer shader maps to the hue axis. This is NOT
// the unbounded intensity EY²+EI² (the old aligner's wrong-value bug: it
// chased a quantity that grows without limit, so the color band constantly
// re-anchored upward and the whole cloud washed to white during a run).
//
// Because q_coh ∈ [0,1) the host keeps a FIXED log range (lo=1e-6, hi=0.999);
// the old per-run histogram-range growth adaptation is dead — the bounded
// channel never needs it.
//
// Runs once per rendered frame while auto_align_colors is on (default OFF).
// Particles are strided (pc.stride) to keep the atomic traffic light; the
// host resets the bins every alignment cadence and reads back 512 B.
//
// Bindings (set 0): 0 = Positions (vec4/particle, w = mass), 1 = q field
// (grid_N³ floats — EY²+EI², RETAINED for layout compatibility, unused),
// 2 = histogram (BINS floats, float-atomic counts —
// GL_EXT_shader_atomic_float, verified on this rig in cassi_mass_deposit.glsl),
// 3 = EY field (grid_N³ floats), 4 = EI field (grid_N³ floats),
// 5 = Voronoi sites (vec4/site: xyz position), 6 = site psi_y, 7 = site psi_i
// (bindings 5-7 are the BOXLESS reader source; read only when pc.boxless ≥ 0.5).
// PC: N_f (grid), N_p (particles), stride, lo, hi, BINS_f, enabled, extent_x/y/z,
// win_x/y/z (movable home-window origin subtracted in the world→grid map),
// boxless (0/1 — 1 = sample coherence from the nearest Voronoi site instead of
// the periodic grid trilinear), n_sites (Voronoi site count; guard the loop).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) readonly buffer FieldQ { float qv[]; };
layout(set = 0, binding = 2, std430) coherent buffer Hist { float bins[]; };
layout(set = 0, binding = 3, std430) readonly buffer FieldEY { float eyv[]; };
layout(set = 0, binding = 4, std430) readonly buffer FieldEI { float eiv[]; };
// Boxless reader source — the moving-Voronoi sites (coordinate-independent,
// no window/extent/%N): the cell-averaged field the site leapfrog evolves.
layout(set = 0, binding = 5, std430) readonly buffer Sites { vec4 site[]; };
layout(set = 0, binding = 6, std430) readonly buffer SitePsiY { float psy[]; };
layout(set = 0, binding = 7, std430) readonly buffer SitePsiI { float psi[]; };

layout(push_constant, std430) uniform PC {
    float N_f;      // grid_N (the field resolution)
    float N_p;      // particle count
    float stride;   // particle subsample stride
    float lo;       // histogram log-range floor (q_coh below lo → bin 0)
    float hi;       // histogram log-range ceiling (q_coh above hi → bin B-1)
    float BINS_f;   // bin count (128)
    float enabled;  // 0/1 gate (host toggles live)
    float extent_x; // per-axis box half-extents — the instancer's mapping
    float extent_y;
    float extent_z;
    float win_x;    // movable home-window origin (perf-decomp 2026-08-15):
    float win_y;    // subtracted in the world→grid map; zero = legacy box
    float win_z;
    float boxless;  // 0/1 — 1 = boxless site-direct coherence sample (no wrap)
    float n_sites;  // Voronoi site count (2·16³ = 8192 at N=64)
} pc;

const float LOG_GUARD = 1e-9;
const float PHI = 1.6180339887498949;
const float PHI_INV2 = 0.3819660112501051;

int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

// Trilinear sample of the EY grid at a world point (window offset already in
// the grid-cell fractional units of gc). Mirrors the instancer's convention;
// the sampler reads the SSBO global directly (GLSL 450 can't pass buffer
// arrays as function arguments).
float tri_ey(vec3 gc, vec3 f) {
    int N = int(pc.N_f);
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;
    float v000 = eyv[idx3(i0, j0, k0)];
    float v100 = eyv[idx3(i1, j0, k0)];
    float v010 = eyv[idx3(i0, j1, k0)];
    float v110 = eyv[idx3(i1, j1, k0)];
    float v001 = eyv[idx3(i0, j0, k1)];
    float v101 = eyv[idx3(i1, j0, k1)];
    float v011 = eyv[idx3(i0, j1, k1)];
    float v111 = eyv[idx3(i1, j1, k1)];
    float q0 = mix(mix(v000, v100, f.x), mix(v010, v110, f.x), f.y);
    float q1 = mix(mix(v001, v101, f.x), mix(v011, v111, f.x), f.y);
    return mix(q0, q1, f.z);
}

float tri_ei(vec3 gc, vec3 f) {
    int N = int(pc.N_f);
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;
    float v000 = eiv[idx3(i0, j0, k0)];
    float v100 = eiv[idx3(i1, j0, k0)];
    float v010 = eiv[idx3(i0, j1, k0)];
    float v110 = eiv[idx3(i1, j1, k0)];
    float v001 = eiv[idx3(i0, j0, k1)];
    float v101 = eiv[idx3(i1, j0, k1)];
    float v011 = eiv[idx3(i0, j1, k1)];
    float v111 = eiv[idx3(i1, j1, k1)];
    float q0 = mix(mix(v000, v100, f.x), mix(v010, v110, f.x), f.y);
    float q1 = mix(mix(v001, v101, f.x), mix(v011, v111, f.x), f.y);
    return mix(q0, q1, f.z);
}

// Boxless reference: sites and particles are compared in the same render-local
// tile space. The host uploads site positions with the window translation
// already removed, so no stale world/window offset can bias the brute-force arm.
float site_coherence(vec3 wp) {
    int ns = int(pc.n_sites);
    if (ns <= 0) return 0.0;
    vec3 tile_wp = wp + vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    int best = 0;
    float bd = 1e30;
    for (int s = 0; s < ns; s++) {
        vec3 d = site[s].xyz - tile_wp;
        float dd = dot(d, d);
        if (dd < bd) { bd = dd; best = s; }
    }
    float ey = psy[best], ei = psi[best];
    float rho = ey + ei, eps = ey - PHI * ei, rho2 = rho * rho;
    return rho2 / (rho2 + PHI_INV2 + eps * eps);
}

void main() {
    if (pc.enabled < 0.5) return;
    int n = int(pc.N_p);
    int s = max(int(pc.stride), 1);
    int B = int(pc.BINS_f);
    if (B <= 0) return;
    int i = int(gl_GlobalInvocationID.x) * s;
    if (i >= n) return;

    float q;
    if (pc.boxless >= 0.5) {
        // Boxless: the coherence at the particle comes from the nearest
        // Voronoi site (its own cell-averaged field) — no window/extent/%N,
        // so the read is correct even if the tracking envelope lags.
        q = site_coherence(pos[i].xyz);
    } else {
        int N = int(pc.N_f);
        float hn = float(N) * 0.5;
        vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
        vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
        vec3 win = vec3(pc.win_x, pc.win_y, pc.win_z);
        vec3 gc = ((pos[i].xyz - win) * inv_ext) * hn + hn;
        vec3 f = gc - floor(gc);
        float ey = tri_ey(gc, f);
        float ei = tri_ei(gc, f);
        float rho = ey + ei;
        float eps = ey - PHI * ei;
        float rho2 = rho * rho;
        q = rho2 / (rho2 + PHI_INV2 + eps * eps);   // ∈ [0,1)
    }
    if (q <= 0.0) {
        atomicAdd(bins[0], 1.0);   // incoherent/void floor → the lowest bin
        return;
    }
    float llo = log(max(pc.lo, LOG_GUARD));
    float lhi = log(max(pc.hi, pc.lo * 1.001));
    float t = clamp((log(q) - llo) / max(lhi - llo, 1e-9), 0.0, 1.0);
    int b = min(int(t * float(B - 1)), B - 1);
    atomicAdd(bins[b], 1.0);
}
