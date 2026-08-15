#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 17 floats (68 B); set 0: bindings 0-19
#version 450
// Cassi Voronoi Cells — the per-cell two-fluid wave system on the JFA
// Voronoi mesh (MESHLESS_PLAN.md Stage 1 + the §10 sim integration).
// State is PER VORONOI CELL (one site each): psiY/psiI and their
// momenta piY/piI. The wave Laplacian is the two-point flux across the
// grid faces that separate different JFA labels — the staircase
// approximation of the true Voronoi face. Proven in numpy
// (research/meshless/stage1_jfa3d.py) and on the GPU (G0-G4, G9-G12).
//
// ANISOTROPIC METRIC: the accelerator grid maps index space onto the
// STRETCHED box [0, 2·extent_x) × [0, 2·extent_y) × [0, 2·extent_z)
// with per-axis spacings hx/hy/hz = 2·extent_i/N (the same mapping as
// the JFA shader, so the labels agree). Every grid-indexed coordinate
// (face flux, volume, centroid, scatter, source sample, steer) uses the
// per-axis spacing; the physical box per axis is L_i = N·h_i. The lap
// face weights become the PHYSICAL face area / physical centroid
// distance (the AREPO two-point flux): x-face (hy·hz)/d, y-face
// (hx·hz)/d, z-face (hx·hy)/d with d = |sn − sc| — exactly h²/d at
// hx=hy=hz=h (the hard cube regression). C2 is the single physical
// wave speed² = h_min² = (2·min(extent_i)/N)², matching the GRID arm's
// D19 stencil (which reads h₀²∇²_phys with h₀ = 2·min(extent)/N).
//
// Pass modes (PC.mode):
//   0 lap        — per GRID cell: the three +axis faces, float
//                  atomicAdd flux (each face counted once)
//   1 leapfrog   — per SITE: kick π (flux + coupling + the mass-driven
//                  source sampled at the site's own grid cell), drift
//                  ψ, zero lap
//   2 volume     — per GRID cell: atomicAdd hx·hy·hz per cell
//   3 centroid   — per GRID cell: atomicAdd the (stretched) cell center,
//                  MASS-weighted by w = rho_mass + LLOYD_FLOOR (the mesh
//                  follows the deposited matter; at rho_mass == 0 the
//                  floor cancels → exact geometric centroid)
//   4 steer      — per SITE: the quasi-Lagrangian ride + Lloyd-style
//                  centroid relaxation with a Qi-gated strength
//                  κ_eff = κ·(1−q)^p (q = ρ²/(ρ²+φ⁻²+ε²), the coherence
//                  of the site's own two-fluid state), per-axis periodic
//                  wrap, TOTAL displacement guarded to ML_MAX_DRIFT, and
//                  the remap index (the OLD cell containing the new pos)
//   5 state→tmp  — per SITE: copy the state to the temp buffers
//   6 tmp→state  — per SITE: gather the remapped state (tmp[remap_idx])
//   7 reset      — per SITE: vol = 0, cen = (0,0,0,0)
//   8 labels clr — per GRID cell: labels = INT_MAX
//   9 scatter    — per SITE: atomicMin the site index into its grid cell
//  10 grad zero  — per SITE: grad_y/grad_i and the lsm moment+rhs = 0
//  12 ls solve   — per SITE: g = M⁻¹·b (the least-squares gradient) -> grad
//
// The whole rebuild is ONE compute list (barriers between modes): reset
// → centroid → steer → remap copy → remap gather → labels clear →
// scatter → JFA (the ping-pong passes share the list) → volume. No
// readbacks, no CPU loops — the global RD never stalls.
// Float atomicAdd: GL_EXT_shader_atomic_float, verified on this rig in
// cassi_mass_deposit.glsl (RX 7900 XTX, Vulkan 1.4, Godot 4.7).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// MUST match scripts/cassi_sim.gd ML_LLOYD_FLOOR. The density-weighting floor:
// with rho_mass == 0 the mode-3 weight is this constant on every cell, so
// the centroid is EXACTLY the geometric one (floor cancels in the ratio).
// A tiny positive floor also keeps the weight from vanishing where the
// deposited density has holes, so the centroid is never degenerate.
const float LLOYD_FLOOR = 1e-3;

layout(push_constant, std430) uniform PC {
    float mode;             // see the mode list above
    float N_f;              // grid resolution per dimension
    float n_sites;          // site (cell) count
    float dt;               // leapfrog step
    float hx;               // x cell spacing (2·extent_x / N)
    float hy;               // y cell spacing (2·extent_y / N)
    float hz;               // z cell spacing (2·extent_z / N)
    float C2;               // wave speed² (h_min² — matches the grid's D19)
    float OM2;              // omega_0²
    float PHI;              // golden ratio
    float source_strength;  // field injection (the grid PDE's source_s)
    float rho_floor;        // steering guard: rho = EY+EI can hit ~0
    float drift_cap;        // steering guard: per-rebuild drift cap (= ML_MAX_DRIFT)
    float kappa;            // centroid relaxation fraction (base κ)
    float lam;              // super-Lagrangian momentum ride
    float T_steer;          // dt × rebuild cadence
    float lloyd_p;          // Qi-gate exponent: κ_eff = κ·(1 − q)^p
} pc;

layout(set = 0, binding = 0, std430) buffer Labels {
    int labels[];  // JFA site index per grid cell (read-write: clear/scatter)
};
layout(set = 0, binding = 1, std430) buffer Sites {
    vec4 pos[];  // x, y, z per site (read-write: the steer moves them)
};
layout(set = 0, binding = 2, std430) buffer PsiY {
    float psi_y[];
};
layout(set = 0, binding = 3, std430) buffer PsiI {
    float psi_i[];
};
layout(set = 0, binding = 4, std430) buffer PiY {
    float pi_y[];
};
layout(set = 0, binding = 5, std430) buffer PiI {
    float pi_i[];
};
layout(set = 0, binding = 6, std430) coherent buffer LapY {
    float lap_y[];
};
layout(set = 0, binding = 7, std430) coherent buffer LapI {
    float lap_i[];
};
layout(set = 0, binding = 8, std430) coherent buffer Vol {
    float vol[];
};
layout(set = 0, binding = 9, std430) restrict readonly buffer MassDensity {
    float rho_mass[];  // the deposit's mass density per GRID cell
};
layout(set = 0, binding = 10, std430) coherent buffer Cen {
    vec4 cen[];  // centroid sums (xyz) + count (w), per site
};
layout(set = 0, binding = 11, std430) buffer Remap {
    int remap_idx[];  // old cell index per site (the ALE remap source)
};
layout(set = 0, binding = 12, std430) buffer TmpY {
    float tmp_y[];
};
layout(set = 0, binding = 13, std430) buffer TmpI {
    float tmp_i[];
};
layout(set = 0, binding = 14, std430) buffer TmpPY {
    float tmp_py[];
};
layout(set = 0, binding = 15, std430) buffer TmpPI {
    float tmp_pi[];
};
// AREPO-style reconstruction gradients (the square-ripples fix). MODE 0
// (the lap pass) ALSO accumulates, per site and per field, the
// LEAST-SQUARES (face-normal) gradient: the 3×3 moment matrix M += n̂⊗n̂
// and rhs b += (ψ_n − ψ_s)/d·n̂ over the Voronoi boundary faces (stored
// in the lsm buffers, bindings 18/19). MODE 12 then solves the 3×3
// system g = M⁻¹·b per site — EXACT for linear fields on ANY mesh — and
// writes the solved gradient into grad_y/grad_i with .w = 1. The raster
// (cassi_voronoi_raster.glsl binding 6/7) reads the solved gradient
// directly (dividing by max(w,eps) = 1). The lap flux stays the AREPO
// two-point flux. lsm buffers are zeroed by mode 10 before the lap.
layout(set = 0, binding = 16, std430) buffer GradY {
    vec4 grad_y[];  // solved ∇ψ_y (.xyz), .w = 1 after mode 12
};
layout(set = 0, binding = 17, std430) buffer GradI {
    vec4 grad_i[];  // solved ∇ψ_i (.xyz), .w = 1 after mode 12
};
// Least-squares moment + rhs. Per site: 3 consecutive vec4 = M rows
// (.xyz) + rhs b (.w). lsm[s*3+0].xyz = M row 0 (n̂_x·n̂), .w = b.x, etc.
layout(set = 0, binding = 18, std430) coherent buffer LSMY {
    vec4 lsm_y[];
};
layout(set = 0, binding = 19, std430) coherent buffer LSMI {
    vec4 lsm_i[];
};

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int Nn = int(pc.N_f);
    int ns = int(pc.n_sites);
    int im = int(pc.mode);
    int total = Nn * Nn * Nn;
    float hx = pc.hx;
    float hy = pc.hy;
    float hz = pc.hz;

    if (im == 8) {  // labels clear
        if (int(gid) >= total) return;
        labels[int(gid)] = 2147483647;
        return;
    }
    if (im == 9) {  // scatter: min site index per grid cell
        if (int(gid) >= ns) return;
        int s = int(gid);
        vec4 sp = pos[s];
        int gi = int(floor(sp.x / hx)) % Nn;
        int gj = int(floor(sp.y / hy)) % Nn;
        int gk = int(floor(sp.z / hz)) % Nn;
        atomicMin(labels[gi * Nn * Nn + gj * Nn + gk], s);
        return;
    }
    if (im == 10) {  // lsm + grad zero — per SITE, before the lap accumulates
        if (int(gid) >= ns) return;
        grad_y[int(gid)] = vec4(0.0);
        grad_i[int(gid)] = vec4(0.0);
        int s3 = int(gid) * 3;
        lsm_y[s3] = vec4(0.0);
        lsm_y[s3 + 1] = vec4(0.0);
        lsm_y[s3 + 2] = vec4(0.0);
        lsm_i[s3] = vec4(0.0);
        lsm_i[s3 + 1] = vec4(0.0);
        lsm_i[s3 + 2] = vec4(0.0);
        return;
    }
    if (im == 12) {  // least-squares solve — per SITE: g = M⁻¹·b into grad
        if (int(gid) >= ns) return;
        int s = int(gid);
        int s3 = s * 3;
        // build M (rows) + b from the accumulated lsm buffers.
        // M row 0 = lsm_y[s3+0].xyz, row 1 = [s3+1].xyz, row 2 = [s3+2].xyz;
        // b = (.w of each). Add a tiny diagonal regulariser so an
        // under-constrained (near-collinear) neighbour stencil never NaNs.
        float m00 = lsm_y[s3 + 0].x + 1e-6, m01 = lsm_y[s3 + 0].y, m02 = lsm_y[s3 + 0].z;
        float m10 = lsm_y[s3 + 1].x, m11 = lsm_y[s3 + 1].y + 1e-6, m12 = lsm_y[s3 + 1].z;
        float m20 = lsm_y[s3 + 2].x, m21 = lsm_y[s3 + 2].y, m22 = lsm_y[s3 + 2].z + 1e-6;
        float bx = lsm_y[s3 + 0].w, by = lsm_y[s3 + 1].w, bz = lsm_y[s3 + 2].w;
        // 3×3 inverse (adjugate / det) — closed form, guarded.
        float det = m00 * (m11 * m22 - m12 * m21) - m01 * (m10 * m22 - m12 * m20)
                  + m02 * (m10 * m21 - m11 * m20);
        vec3 g = vec3(0.0);
        if (abs(det) > 1e-12) {
            float id = 1.0 / det;
            float c00 =  (m11 * m22 - m12 * m21) * id;
            float c01 = -(m01 * m22 - m02 * m21) * id;
            float c02 =  (m01 * m12 - m02 * m11) * id;
            float c10 = -(m10 * m22 - m12 * m20) * id;
            float c11 =  (m00 * m22 - m02 * m20) * id;
            float c12 = -(m00 * m12 - m02 * m10) * id;
            float c20 =  (m10 * m21 - m11 * m20) * id;
            float c21 = -(m00 * m21 - m01 * m20) * id;
            float c22 =  (m00 * m11 - m01 * m10) * id;
            g = vec3(c00 * bx + c01 * by + c02 * bz,
                     c10 * bx + c11 * by + c12 * bz,
                     c20 * bx + c21 * by + c22 * bz);
        }
        grad_y[s] = vec4(g, 1.0);
        // psi_i gradient: same M (the geometry is field-independent), new b.
        float bix = lsm_i[s3 + 0].w, biy = lsm_i[s3 + 1].w, biz = lsm_i[s3 + 2].w;
        vec3 gi = vec3(0.0);
        if (abs(det) > 1e-12) {
            float id = 1.0 / det;
            float c00 =  (m11 * m22 - m12 * m21) * id;
            float c01 = -(m01 * m22 - m02 * m21) * id;
            float c02 =  (m01 * m12 - m02 * m11) * id;
            float c10 = -(m10 * m22 - m12 * m20) * id;
            float c11 =  (m00 * m22 - m02 * m20) * id;
            float c12 = -(m00 * m12 - m02 * m10) * id;
            float c20 =  (m10 * m21 - m11 * m20) * id;
            float c21 = -(m00 * m21 - m01 * m20) * id;
            float c22 =  (m00 * m11 - m01 * m10) * id;
            gi = vec3(c00 * bix + c01 * biy + c02 * biz,
                      c10 * bix + c11 * biy + c12 * biz,
                      c20 * bix + c21 * biy + c22 * biz);
        }
        grad_i[s] = vec4(gi, 1.0);
        return;
    }
    if (im == 7) {  // reset vol + cen
        if (int(gid) >= ns) return;
        vol[int(gid)] = 0.0;
        cen[int(gid)] = vec4(0.0);
        return;
    }
    if (im == 3) {  // centroid accumulate — MASS-weighted (the OLD mesh)
        if (int(gid) >= total) return;
        int lab = labels[int(gid)];
        if (lab < 0 || lab >= ns) return;
        int i = int(gid) / (Nn * Nn);
        int rem = int(gid) - i * Nn * Nn;
        int j = rem / Nn;
        int k = rem - j * Nn;
        // per-cell weight = rho_mass + LLOYD_FLOOR. At rho_mass == 0 the
        // constant floor cancels in the centroid (same weight every cell) —
        // EXACTLY the geometric centroid, so the flat-noise / rho=0
        // regression holds bit-for-bit. With deposited matter density w,
        // the cell centroid is pulled toward the material (mesh follows Qi).
        float w = rho_mass[int(gid)] + LLOYD_FLOOR;
        atomicAdd(cen[lab].x, w * (float(i) + 0.5) * hx);
        atomicAdd(cen[lab].y, w * (float(j) + 0.5) * hy);
        atomicAdd(cen[lab].z, w * (float(k) + 0.5) * hz);
        atomicAdd(cen[lab].w, w);
        return;
    }
    if (im == 4) {  // steer: new sites + remap index — Qi-gated, guard-clamped
        if (int(gid) >= ns) return;
        int s = int(gid);
        vec4 sp = pos[s];
        // coherence: q = rho^2/(rho^2 + phi^-2 + eps^2), rho=EY+EI,
        // eps=EY-phi*EI (stage2_moving3d.q_coh, p = stage2's exponent).
        float rho = max(psi_y[s] + psi_i[s], pc.rho_floor);
        float eps = psi_y[s] - pc.PHI * psi_i[s];
        float rsq = rho * rho;
        float q = rsq / (rsq + 1.0 / (pc.PHI * pc.PHI) + eps * eps);
        // Qi-gated relaxation: structured (low-q) cells relax toward the
        // (mass-weighted) centroid; coherent (q~1) cells ride momentum only.
        float kappa_eff = pc.kappa * pow(1.0 - q, pc.lloyd_p);
        float vv = pc.lam * (pi_y[s] + pi_i[s]) / rho;
        // momentum drift — NOT clamped here; the guard below caps the
        // blended displacement as a whole (a distant mass centroid must
        // never teleport a site in one rebuild).
        float drift = vv * pc.T_steer;
        float cc = max(cen[s].w, 1e-12);
        float Lx = float(Nn) * hx;
        float Ly = float(Nn) * hy;
        float Lz = float(Nn) * hz;
        vec3 blended = (1.0 - kappa_eff) * (sp.xyz + vec3(drift, drift, drift))
                       + kappa_eff * (vec3(cen[s].x, cen[s].y, cen[s].z) / cc);
        vec3 disp = blended - sp.xyz;
        // GUARD: cap the TOTAL per-rebuild site displacement (momentum ride
        // PLUS the centroid pull) to ML_MAX_DRIFT. The old code clamped only
        // the momentum term; a distant centroid could pull a site far across
        // the box in one steer. Clamping the blended vector length keeps the
        // stutter-free rebuild from ever teleporting a site.
        float dlen = length(disp);
        if (dlen > pc.drift_cap) {
            disp *= pc.drift_cap / dlen;
        }
        vec3 npos = mod(sp.xyz + disp, vec3(Lx, Ly, Lz));
        int gi = int(floor(npos.x / hx)) % Nn;
        int gj = int(floor(npos.y / hy)) % Nn;
        int gk = int(floor(npos.z / hz)) % Nn;
        int lab = labels[gi * Nn * Nn + gj * Nn + gk];
        if (lab < 0 || lab >= ns) lab = s;
        remap_idx[s] = lab;
        pos[s] = vec4(npos, 0.0);
        return;
    }
    if (im == 5) {  // state → temp
        if (int(gid) >= ns) return;
        int s = int(gid);
        tmp_y[s] = psi_y[s];
        tmp_i[s] = psi_i[s];
        tmp_py[s] = pi_y[s];
        tmp_pi[s] = pi_i[s];
        return;
    }
    if (im == 6) {  // temp → state via remap_idx
        if (int(gid) >= ns) return;
        int s = int(gid);
        int r = remap_idx[s];
        psi_y[s] = tmp_y[r];
        psi_i[s] = tmp_i[r];
        pi_y[s] = tmp_py[r];
        pi_i[s] = tmp_pi[r];
        return;
    }
    if (im == 2) {  // volume: hx·hy·hz per grid cell, atomic
        if (int(gid) >= total) return;
        int lab = labels[int(gid)];
        if (lab >= 0 && lab < ns) {
            atomicAdd(vol[lab], hx * hy * hz);
        }
        return;
    }

    if (im == 0) {  // lap: +x/+y/+z faces of this grid cell (+ LEAST-SQUARES gradient)
        if (int(gid) >= total) return;
        int i = int(gid) / (Nn * Nn);
        int rem = int(gid) - i * Nn * Nn;
        int j = rem / Nn;
        int k = rem - j * Nn;
        int c = labels[int(gid)];
        if (c < 0 || c >= ns) return;

        // three +axis faces, periodic; each face handled exactly once
        int n1 = labels[((i + 1) % Nn) * Nn * Nn + j * Nn + k];
        int n2 = labels[i * Nn * Nn + ((j + 1) % Nn) * Nn + k];
        int n3 = labels[i * Nn * Nn + j * Nn + ((k + 1) % Nn)];

        vec4 sc = pos[c];
        // AREPO two-point flux: the physical face area / the physical
        // centroid distance. x-face area hy·hz, y-face hx·hz, z-face
        // hx·hy; at hx=hy=hz=h each weight reduces EXACTLY to h²/d.
        float ayz = hy * hz;
        float axz = hx * hz;
        float axy = hx * hy;

        // LEAST-SQUARES (face-normal) reconstruction gradient — the
        // production-AREPO / Barth-Jespersen form, EXACT for LINEAR fields
        // on ANY mesh (the naive face-flux Green-Gauss is exact only on
        // axis-aligned cells). Per boundary face to neighbour n we use the
        // unit n̂ = (x_n − x_s)/d and the two-point rhs (ψ_n − ψ_s)/d, and
        // accumulate per site the 3×3 moment matrix M += n̂⊗n̂ and rhs
        // b += (ψ_n − ψ_s)/d · n̂. Both sites across the face get the SAME
        // dyad and rhs (for the far side the direction AND the field
        // difference both flip, so the products are identical). For a
        // linear field (ψ_n−ψ_s)/d = g·n̂, hence b = Σ n̂(n̂·g) = M·g, so
        // g = M⁻¹·b is EXACT. Mode 12 solves the 3×3 per site into grad.
        // The lap flux stays the AREPO two-point flux (ψ_n − ψ_s)·A/d.
        // lsm_y layout per site: 3 consecutive vec4 = rows of M (.xyz) and
        // rhs b (.w): lsm_y[s*3+0] = (M00,M01,M02 | b.x), [s*3+1] = row 1,
        // [s*3+2] = row 2. Same for lsm_i.
        if (n1 >= 0 && n1 < ns && n1 != c) {
            vec4 sn = pos[n1];
            float d = max(length(sn.xyz - sc.xyz), 1e-12);
            float fy = (psi_y[n1] - psi_y[c]) * ayz / d;
            float fi = (psi_i[n1] - psi_i[c]) * ayz / d;
            atomicAdd(lap_y[c], fy);
            atomicAdd(lap_y[n1], -fy);
            atomicAdd(lap_i[c], fi);
            atomicAdd(lap_i[n1], -fi);
            vec3 nn = (sn.xyz - sc.xyz) / d;
            float dy = (psi_y[n1] - psi_y[c]) / d;
            float di = (psi_i[n1] - psi_i[c]) / d;
            int c3 = c * 3, n3i = n1 * 3;
            // +x face: M row i += n̂_i·n̂, b += rhs·n̂  (both endpoints)
            atomicAdd(lsm_y[c3 + 0].x, nn.x * nn.x); atomicAdd(lsm_y[n3i + 0].x, nn.x * nn.x);
            atomicAdd(lsm_y[c3 + 0].y, nn.x * nn.y); atomicAdd(lsm_y[n3i + 0].y, nn.x * nn.y);
            atomicAdd(lsm_y[c3 + 0].z, nn.x * nn.z); atomicAdd(lsm_y[n3i + 0].z, nn.x * nn.z);
            atomicAdd(lsm_y[c3 + 0].w, dy * nn.x);   atomicAdd(lsm_y[n3i + 0].w, dy * nn.x);
            atomicAdd(lsm_y[c3 + 1].x, nn.y * nn.x); atomicAdd(lsm_y[n3i + 1].x, nn.y * nn.x);
            atomicAdd(lsm_y[c3 + 1].y, nn.y * nn.y); atomicAdd(lsm_y[n3i + 1].y, nn.y * nn.y);
            atomicAdd(lsm_y[c3 + 1].z, nn.y * nn.z); atomicAdd(lsm_y[n3i + 1].z, nn.y * nn.z);
            atomicAdd(lsm_y[c3 + 1].w, dy * nn.y);   atomicAdd(lsm_y[n3i + 1].w, dy * nn.y);
            atomicAdd(lsm_y[c3 + 2].x, nn.z * nn.x); atomicAdd(lsm_y[n3i + 2].x, nn.z * nn.x);
            atomicAdd(lsm_y[c3 + 2].y, nn.z * nn.y); atomicAdd(lsm_y[n3i + 2].y, nn.z * nn.y);
            atomicAdd(lsm_y[c3 + 2].z, nn.z * nn.z); atomicAdd(lsm_y[n3i + 2].z, nn.z * nn.z);
            atomicAdd(lsm_y[c3 + 2].w, dy * nn.z);   atomicAdd(lsm_y[n3i + 2].w, dy * nn.z);
            atomicAdd(lsm_i[c3 + 0].x, nn.x * nn.x); atomicAdd(lsm_i[n3i + 0].x, nn.x * nn.x);
            atomicAdd(lsm_i[c3 + 0].y, nn.x * nn.y); atomicAdd(lsm_i[n3i + 0].y, nn.x * nn.y);
            atomicAdd(lsm_i[c3 + 0].z, nn.x * nn.z); atomicAdd(lsm_i[n3i + 0].z, nn.x * nn.z);
            atomicAdd(lsm_i[c3 + 0].w, di * nn.x);   atomicAdd(lsm_i[n3i + 0].w, di * nn.x);
            atomicAdd(lsm_i[c3 + 1].x, nn.y * nn.x); atomicAdd(lsm_i[n3i + 1].x, nn.y * nn.x);
            atomicAdd(lsm_i[c3 + 1].y, nn.y * nn.y); atomicAdd(lsm_i[n3i + 1].y, nn.y * nn.y);
            atomicAdd(lsm_i[c3 + 1].z, nn.y * nn.z); atomicAdd(lsm_i[n3i + 1].z, nn.y * nn.z);
            atomicAdd(lsm_i[c3 + 1].w, di * nn.y);   atomicAdd(lsm_i[n3i + 1].w, di * nn.y);
            atomicAdd(lsm_i[c3 + 2].x, nn.z * nn.x); atomicAdd(lsm_i[n3i + 2].x, nn.z * nn.x);
            atomicAdd(lsm_i[c3 + 2].y, nn.z * nn.y); atomicAdd(lsm_i[n3i + 2].y, nn.z * nn.y);
            atomicAdd(lsm_i[c3 + 2].z, nn.z * nn.z); atomicAdd(lsm_i[n3i + 2].z, nn.z * nn.z);
            atomicAdd(lsm_i[c3 + 2].w, di * nn.z);   atomicAdd(lsm_i[n3i + 2].w, di * nn.z);
        }
        if (n2 >= 0 && n2 < ns && n2 != c) {
            vec4 sn = pos[n2];
            float d = max(length(sn.xyz - sc.xyz), 1e-12);
            float fy = (psi_y[n2] - psi_y[c]) * axz / d;
            float fi = (psi_i[n2] - psi_i[c]) * axz / d;
            atomicAdd(lap_y[c], fy);
            atomicAdd(lap_y[n2], -fy);
            atomicAdd(lap_i[c], fi);
            atomicAdd(lap_i[n2], -fi);
            vec3 nn = (sn.xyz - sc.xyz) / d;
            float dy = (psi_y[n2] - psi_y[c]) / d;
            float di = (psi_i[n2] - psi_i[c]) / d;
            int c3 = c * 3, n3i = n2 * 3;
            atomicAdd(lsm_y[c3 + 0].x, nn.x * nn.x); atomicAdd(lsm_y[n3i + 0].x, nn.x * nn.x);
            atomicAdd(lsm_y[c3 + 0].y, nn.x * nn.y); atomicAdd(lsm_y[n3i + 0].y, nn.x * nn.y);
            atomicAdd(lsm_y[c3 + 0].z, nn.x * nn.z); atomicAdd(lsm_y[n3i + 0].z, nn.x * nn.z);
            atomicAdd(lsm_y[c3 + 0].w, dy * nn.x);   atomicAdd(lsm_y[n3i + 0].w, dy * nn.x);
            atomicAdd(lsm_y[c3 + 1].x, nn.y * nn.x); atomicAdd(lsm_y[n3i + 1].x, nn.y * nn.x);
            atomicAdd(lsm_y[c3 + 1].y, nn.y * nn.y); atomicAdd(lsm_y[n3i + 1].y, nn.y * nn.y);
            atomicAdd(lsm_y[c3 + 1].z, nn.y * nn.z); atomicAdd(lsm_y[n3i + 1].z, nn.y * nn.z);
            atomicAdd(lsm_y[c3 + 1].w, dy * nn.y);   atomicAdd(lsm_y[n3i + 1].w, dy * nn.y);
            atomicAdd(lsm_y[c3 + 2].x, nn.z * nn.x); atomicAdd(lsm_y[n3i + 2].x, nn.z * nn.x);
            atomicAdd(lsm_y[c3 + 2].y, nn.z * nn.y); atomicAdd(lsm_y[n3i + 2].y, nn.z * nn.y);
            atomicAdd(lsm_y[c3 + 2].z, nn.z * nn.z); atomicAdd(lsm_y[n3i + 2].z, nn.z * nn.z);
            atomicAdd(lsm_y[c3 + 2].w, dy * nn.z);   atomicAdd(lsm_y[n3i + 2].w, dy * nn.z);
            atomicAdd(lsm_i[c3 + 0].x, nn.x * nn.x); atomicAdd(lsm_i[n3i + 0].x, nn.x * nn.x);
            atomicAdd(lsm_i[c3 + 0].y, nn.x * nn.y); atomicAdd(lsm_i[n3i + 0].y, nn.x * nn.y);
            atomicAdd(lsm_i[c3 + 0].z, nn.x * nn.z); atomicAdd(lsm_i[n3i + 0].z, nn.x * nn.z);
            atomicAdd(lsm_i[c3 + 0].w, di * nn.x);   atomicAdd(lsm_i[n3i + 0].w, di * nn.x);
            atomicAdd(lsm_i[c3 + 1].x, nn.y * nn.x); atomicAdd(lsm_i[n3i + 1].x, nn.y * nn.x);
            atomicAdd(lsm_i[c3 + 1].y, nn.y * nn.y); atomicAdd(lsm_i[n3i + 1].y, nn.y * nn.y);
            atomicAdd(lsm_i[c3 + 1].z, nn.y * nn.z); atomicAdd(lsm_i[n3i + 1].z, nn.y * nn.z);
            atomicAdd(lsm_i[c3 + 1].w, di * nn.y);   atomicAdd(lsm_i[n3i + 1].w, di * nn.y);
            atomicAdd(lsm_i[c3 + 2].x, nn.z * nn.x); atomicAdd(lsm_i[n3i + 2].x, nn.z * nn.x);
            atomicAdd(lsm_i[c3 + 2].y, nn.z * nn.y); atomicAdd(lsm_i[n3i + 2].y, nn.z * nn.y);
            atomicAdd(lsm_i[c3 + 2].z, nn.z * nn.z); atomicAdd(lsm_i[n3i + 2].z, nn.z * nn.z);
            atomicAdd(lsm_i[c3 + 2].w, di * nn.z);   atomicAdd(lsm_i[n3i + 2].w, di * nn.z);
        }
        if (n3 >= 0 && n3 < ns && n3 != c) {
            vec4 sn = pos[n3];
            float d = max(length(sn.xyz - sc.xyz), 1e-12);
            float fy = (psi_y[n3] - psi_y[c]) * axy / d;
            float fi = (psi_i[n3] - psi_i[c]) * axy / d;
            atomicAdd(lap_y[c], fy);
            atomicAdd(lap_y[n3], -fy);
            atomicAdd(lap_i[c], fi);
            atomicAdd(lap_i[n3], -fi);
            vec3 nn = (sn.xyz - sc.xyz) / d;
            float dy = (psi_y[n3] - psi_y[c]) / d;
            float di = (psi_i[n3] - psi_i[c]) / d;
            int c3 = c * 3, n3i = n3 * 3;
            atomicAdd(lsm_y[c3 + 0].x, nn.x * nn.x); atomicAdd(lsm_y[n3i + 0].x, nn.x * nn.x);
            atomicAdd(lsm_y[c3 + 0].y, nn.x * nn.y); atomicAdd(lsm_y[n3i + 0].y, nn.x * nn.y);
            atomicAdd(lsm_y[c3 + 0].z, nn.x * nn.z); atomicAdd(lsm_y[n3i + 0].z, nn.x * nn.z);
            atomicAdd(lsm_y[c3 + 0].w, dy * nn.x);   atomicAdd(lsm_y[n3i + 0].w, dy * nn.x);
            atomicAdd(lsm_y[c3 + 1].x, nn.y * nn.x); atomicAdd(lsm_y[n3i + 1].x, nn.y * nn.x);
            atomicAdd(lsm_y[c3 + 1].y, nn.y * nn.y); atomicAdd(lsm_y[n3i + 1].y, nn.y * nn.y);
            atomicAdd(lsm_y[c3 + 1].z, nn.y * nn.z); atomicAdd(lsm_y[n3i + 1].z, nn.y * nn.z);
            atomicAdd(lsm_y[c3 + 1].w, dy * nn.y);   atomicAdd(lsm_y[n3i + 1].w, dy * nn.y);
            atomicAdd(lsm_y[c3 + 2].x, nn.z * nn.x); atomicAdd(lsm_y[n3i + 2].x, nn.z * nn.x);
            atomicAdd(lsm_y[c3 + 2].y, nn.z * nn.y); atomicAdd(lsm_y[n3i + 2].y, nn.z * nn.y);
            atomicAdd(lsm_y[c3 + 2].z, nn.z * nn.z); atomicAdd(lsm_y[n3i + 2].z, nn.z * nn.z);
            atomicAdd(lsm_y[c3 + 2].w, dy * nn.z);   atomicAdd(lsm_y[n3i + 2].w, dy * nn.z);
            atomicAdd(lsm_i[c3 + 0].x, nn.x * nn.x); atomicAdd(lsm_i[n3i + 0].x, nn.x * nn.x);
            atomicAdd(lsm_i[c3 + 0].y, nn.x * nn.y); atomicAdd(lsm_i[n3i + 0].y, nn.x * nn.y);
            atomicAdd(lsm_i[c3 + 0].z, nn.x * nn.z); atomicAdd(lsm_i[n3i + 0].z, nn.x * nn.z);
            atomicAdd(lsm_i[c3 + 0].w, di * nn.x);   atomicAdd(lsm_i[n3i + 0].w, di * nn.x);
            atomicAdd(lsm_i[c3 + 1].x, nn.y * nn.x); atomicAdd(lsm_i[n3i + 1].x, nn.y * nn.x);
            atomicAdd(lsm_i[c3 + 1].y, nn.y * nn.y); atomicAdd(lsm_i[n3i + 1].y, nn.y * nn.y);
            atomicAdd(lsm_i[c3 + 1].z, nn.y * nn.z); atomicAdd(lsm_i[n3i + 1].z, nn.y * nn.z);
            atomicAdd(lsm_i[c3 + 1].w, di * nn.y);   atomicAdd(lsm_i[n3i + 1].w, di * nn.y);
            atomicAdd(lsm_i[c3 + 2].x, nn.z * nn.x); atomicAdd(lsm_i[n3i + 2].x, nn.z * nn.x);
            atomicAdd(lsm_i[c3 + 2].y, nn.z * nn.y); atomicAdd(lsm_i[n3i + 2].y, nn.z * nn.y);
            atomicAdd(lsm_i[c3 + 2].z, nn.z * nn.z); atomicAdd(lsm_i[n3i + 2].z, nn.z * nn.z);
            atomicAdd(lsm_i[c3 + 2].w, di * nn.z);   atomicAdd(lsm_i[n3i + 2].w, di * nn.z);
        }
        return;
    }

    // im == 1 — leapfrog: one thread per site
    if (int(gid) >= ns) return;
    int s = int(gid);
    float dev = psi_y[s] - pc.PHI * psi_i[s];
    float v = max(vol[s], 1e-12);

    // the grid PDE's source, sampled at the site's own grid cell:
    // src_y = s·exp(-r²4) + rho_mass·0.001, src_i = 0.707·(same)
    vec4 sp = pos[s];
    int gi = int(floor(sp.x / hx)) % Nn;
    int gj = int(floor(sp.y / hy)) % Nn;
    int gk = int(floor(sp.z / hz)) % Nn;
    float mr = rho_mass[gi * Nn * Nn + gj * Nn + gk];
    float halfn = float(Nn) * 0.5;
    float dx = (sp.x / hx - halfn * 0.7) / halfn;
    float dy = (sp.y / hy - halfn * 0.8) / halfn;
    float dz = (sp.z / hz - halfn * 0.6) / halfn;
    float r2 = dx * dx + dy * dy + dz * dz;
    float src_y = pc.source_strength * exp(-r2 * 4.0) + mr * 0.001;
    float src_i = pc.source_strength * 0.707 * exp(-r2 * 4.0) + mr * 0.000707;

    pi_y[s] += pc.dt * (pc.C2 * lap_y[s] / v - pc.OM2 * dev + src_y);
    pi_i[s] += pc.dt * (pc.C2 * lap_i[s] / v + pc.OM2 * dev + src_i);
    psi_y[s] += pc.dt * pi_y[s];
    psi_i[s] += pc.dt * pi_i[s];
    lap_y[s] = 0.0;
    lap_i[s] = 0.0;
}
