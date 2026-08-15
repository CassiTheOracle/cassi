#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 8 floats (32 B); set 0: bindings 0-3
#version 450
// Cassi Coarse-Gradient — the cascade-multigrid coarse level's ∇(g·Φ) build
// (research/cascade_multigrid/multigrid_design.md §(d), stage7_multigrid.py).
//
// The coarse level is its OWN periodic spectral-Poisson solve on the FULL box
// at N_c (no boundary data — same torus geometry L_i, lower resolution). This
// pass turns that coarse Φ into a cell-centered ∇(g·Φ)_c field (one thread
// per coarse cell) in WORLD units, the EXACT per-cell operator the fine
// chain's grad_pass uses — see compute/cassi_nbody_gravity.glsl (chord_s_at):
//   S_c(i,j,k) = g(i,j,k) · Φ_c(i,j,k)      (whole product per CELL)
//   g(i,j,k)  = 1 + (ξ−1)·q,  ξ=φ⁶,  q = ρ²/(ρ²+φ⁻²+ε²),  ρ=EY+EI, ε=EY−φ·EI
//   ∇S_c       = O2 periodic central diff of S_c / (2·h_i),  h_i = 2·ext_i/N_c
// where g at a coarse cell is the fine-field coherence trilinearly sampled at
// that cell's world center (the chord_s_at_dual pattern) — the fine field
// lives on ONE grid. Each neighbor evaluates S at ITS OWN g (the true
// ∇(g·Φ) operator, bit-shape-identical to the fine grad_pass).
//
// The g factor is load-bearing: at the attractor q≈0.947, g≈17, so a plain
// ∇Φ_c would be ~17× too weak against the fine ∇(g·Φ)_f at the hand-off —
// the "per-level normalization must be exact" trap (design §(b)). Using
// ∇(g·Φ)_c keeps both levels the SAME operator; the (N_c/N_f)³ volume
// renormalization lives in the nbody blend (design §(b)).
//
// Stored as vec4[cell] (xyz = ∇(g·Φ)_c, w = 0), matching GradBuf's layout.
//
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer PhiBuf { vec2 ph[]; };   // coarse Φ (real = .x)
layout(set = 0, binding = 1, std430) readonly buffer FieldEY { float ey[]; }; // FINE EY (field lives on the fine grid)
layout(set = 0, binding = 2, std430) readonly buffer FieldEI { float ei[]; }; // FINE EI
layout(set = 0, binding = 3, std430) buffer GradBuf { vec4 gc[]; };           // coarse ∇(g·Φ) output

layout(push_constant, std430) uniform PC {
    float N_c;       // coarse grid resolution per dimension
    float N_f;       // fine grid resolution (field sampling)
    float ext_x;     // per-axis box half-extents (same as bh[2].yzw)
    float ext_y;
    float ext_z;
    float phi;       // φ — the coherence law's base
    float xi;        // ξ = φ⁶ (17.9443); g = 1 + (ξ−1)·q
    float _pad0;
} pc;

const float PHI_INV2 = 0.3819660112501051;   // φ⁻² — q decoherence threshold

// Fine-field coherence factor g at the coarse cell (ci,cj,ck)'s world center.
float coarse_g_at(int ci, int cj, int ck) {
    int Nf = int(pc.N_f);
    float hnf = float(Nf) * 0.5;
    vec3 ext = vec3(pc.ext_x, pc.ext_y, pc.ext_z);
    vec3 wp = (vec3(float(ci) + 0.5, float(cj) + 0.5, float(ck) + 0.5) - hnf)
            * (ext / hnf);
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    vec3 gc = wp * inv_ext * hnf + hnf;
    int i0 = int(floor(gc.x)); int j0 = int(floor(gc.y)); int k0 = int(floor(gc.z));
    float fx = gc.x - float(i0); float fy = gc.y - float(j0); float fz = gc.z - float(k0);
    i0 = ((i0 % Nf) + Nf) % Nf;  j0 = ((j0 % Nf) + Nf) % Nf;  k0 = ((k0 % Nf) + Nf) % Nf;
    int i1 = (i0 + 1) % Nf;      int j1 = (j0 + 1) % Nf;      int k1 = (k0 + 1) % Nf;
    int c000 = i0 + Nf * (j0 + Nf * k0);
    int c100 = i1 + Nf * (j0 + Nf * k0);
    int c010 = i0 + Nf * (j1 + Nf * k0);
    int c110 = i1 + Nf * (j1 + Nf * k0);
    int c001 = i0 + Nf * (j0 + Nf * k1);
    int c101 = i1 + Nf * (j0 + Nf * k1);
    int c011 = i0 + Nf * (j1 + Nf * k1);
    int c111 = i1 + Nf * (j1 + Nf * k1);
    float eyv = mix(mix(mix(ey[c000], ey[c100], fx), mix(ey[c010], ey[c110], fx), fy),
                    mix(mix(ey[c001], ey[c101], fx), mix(ey[c011], ey[c111], fx), fy), fz);
    float eiv = mix(mix(mix(ei[c000], ei[c100], fx), mix(ei[c010], ei[c110], fx), fy),
                    mix(mix(ei[c001], ei[c101], fx), mix(ei[c011], ei[c111], fx), fy), fz);
    float rho_f = eyv + eiv;
    float eps = eyv - pc.phi * eiv;
    float q = (rho_f * rho_f) / (rho_f * rho_f + PHI_INV2 + eps * eps);
    return 1.0 + (pc.xi - 1.0) * q;
}

void main() {
    int Nc = int(pc.N_c);
    int nc = Nc * Nc * Nc;
    uint gid = gl_GlobalInvocationID.x
             + gl_GlobalInvocationID.y * uint(Nc * 256);
    if (int(gid) >= nc) return;

    int i = int(gid) % Nc;
    int j = (int(gid) / Nc) % Nc;
    int k = int(gid) / (Nc * Nc);

    int ip = (i + 1) % Nc;   int im = (i - 1 + Nc) % Nc;
    int jp = (j + 1) % Nc;   int jm = (j - 1 + Nc) % Nc;
    int kp = (k + 1) % Nc;   int km = (k - 1 + Nc) % Nc;

    // per-axis coarse cell-width-inverse: 1/(2·h_i), h_i = 2·extent_i/N_c
    float hxs = 0.5 * float(Nc) / max(pc.ext_x, 0.001);
    float hys = 0.5 * float(Nc) / max(pc.ext_y, 0.001);
    float hzs = 0.5 * float(Nc) / max(pc.ext_z, 0.001);

    // S = g·Φ at the cell and its axis neighbors (each at ITS OWN g).
    float s0  = coarse_g_at(i,  j,  k)  * ph[ gid ].x;
    float sxp = coarse_g_at(ip, j,  k)  * ph[ip + Nc * (j  + Nc * k )].x;
    float sxm = coarse_g_at(im, j,  k)  * ph[im + Nc * (j  + Nc * k )].x;
    float syp = coarse_g_at(i,  jp, k)  * ph[i  + Nc * (jp + Nc * k )].x;
    float sym = coarse_g_at(i,  jm, k)  * ph[i  + Nc * (jm + Nc * k )].x;
    float szp = coarse_g_at(i,  j,  kp) * ph[i  + Nc * (j  + Nc * kp)].x;
    float szm = coarse_g_at(i,  j,  km) * ph[i  + Nc * (j  + Nc * km)].x;

    gc[gid] = vec4(
        (sxp - sxm) * hxs,
        (syp - sym) * hys,
        (szp - szm) * hzs,
        0.0);
}
