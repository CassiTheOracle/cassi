#[compute]
#version 450
// Cassi Voronoi Raster — AREPO-style per-cell LINEAR reconstruction of the
// cell state back onto the accelerator grid (MESHLESS_PLAN.md §10 + the
// square-ripples fix). The mesh's ONLY output surface: the field render
// shader, the condensation scanner, and the river gradient all read the
// grid buffers — this pass writes them from the per-cell (site) state.
// One thread per grid cell.
//
// Previously each grid cell was filled with its Voronoi site's PIECEWISE-
// CONSTANT value, which made every Voronoi cell boundary render as a hard
// step (the "grid squares" artifact). Now each grid cell reconstructs a
// LINEAR field from the Green-Gauss gradient (computed in the cells shader
// mode 0):
//     ψ(x_g) = ψ_s + g_s · (x_gid − site_s)
// with x_gid the grid cell CENTER in physical/mesh coords
// ((i+0.5)·hx, (j+0.5)·hy, (k+0.5)·hz — the same center convention as the
// mode-3 centroid) and site_s the site's position (the CENTROID≈site after
// Lloyd steering — the per-cell state is the cell-averaged value carried at
// the site, so the linear reconstruction is the first-order consistent
// interpolant; documented approximation).
//
// SLOPE LIMITER (Barth–Jespersen, over the 26-neighbourhood): the
// unclamped recon is clamped to [lo, hi] of the site's Ψ and every
// DISTINCT site in the 3×3×3 grid stencil (the full set of Voronoi
// neighbours touching the cell — enough to bound a linear field at a
// point inside it). An interior cell (all 26 = the same site, lo==hi==ψ_s)
// is left UNCLAMPED so the smooth extrapolation is preserved; boundary
// cells can never overshoot a neighbour value. For any linear field the
// clamp is a no-op → linear-exactness is preserved (gate ≤ 1e-4, float32).
//
// q = ey² + ei² is evaluated from the RECONSTRUCTED ey/ei, so the coherence
// display inherits the smoothing too.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float N_f;      // grid resolution per dimension
    float n_sites;  // site (cell) count
    float hx;       // x cell spacing (2·extent_x / N)
    float hy;       // y cell spacing (2·extent_y / N)
    float hz;       // z cell spacing (2·extent_z / N)
    float pad0;
    float pad1;
    float pad2;
} pc;

layout(set = 0, binding = 0, std430) restrict readonly buffer Labels {
    int labels[];  // JFA site index per grid cell
};
layout(set = 0, binding = 1, std430) restrict readonly buffer PsiY {
    float psi_y[];
};
layout(set = 0, binding = 2, std430) restrict readonly buffer PsiI {
    float psi_i[];
};
layout(set = 0, binding = 3, std430) buffer FieldEY {
    float ey[];
};
layout(set = 0, binding = 4, std430) buffer FieldEI {
    float ei[];
};
layout(set = 0, binding = 5, std430) buffer FieldQ {
    float q[];
};
layout(set = 0, binding = 6, std430) restrict readonly buffer GradY {
    vec4 grad_y[];  // .xyz = ∇ψ_y·V_s (un-normalised sum), .w = V_s
};
layout(set = 0, binding = 7, std430) restrict readonly buffer GradI {
    vec4 grad_i[];  // .xyz = ∇ψ_i·V_s (un-normalised sum), .w = V_s
};
layout(set = 0, binding = 8, std430) restrict readonly buffer Sites {
    vec4 site[];  // x, y, z per site
};

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int Nn = int(pc.N_f);
    if (int(gid) >= Nn * Nn * Nn) return;
    int lab = labels[int(gid)];
    if (lab < 0 || lab >= int(pc.n_sites)) {
        lab = 0;
    }
    int ns = int(pc.n_sites);

    // grid cell center in physical/mesh coords (the mode-3 centroid basis)
    int i = int(gid) / (Nn * Nn);
    int rem = int(gid) - i * Nn * Nn;
    int j = rem / Nn;
    int k = rem - j * Nn;
    vec3 xg = vec3((float(i) + 0.5) * pc.hx,
                   (float(j) + 0.5) * pc.hy,
                   (float(k) + 0.5) * pc.hz);

    vec3 site_p = site[lab].xyz;
    vec3 dx = xg - site_p;

    // normalised gradients (Green-Gauss: g = rawSum / V_s)
    vec3 gy = grad_y[lab].xyz / max(grad_y[lab].w, 1e-12);
    vec3 gi = grad_i[lab].xyz / max(grad_i[lab].w, 1e-12);

    // per-axis contributions to be slope-limited (Barth–Jespersen)
    float cx = dx.x;
    float cxy = dx.y;
    float cxz = dx.z;
    float cont_yx = gy.x * cx;
    float cont_yy = gy.y * cxy;
    float cont_yz = gy.z * cxz;
    float cont_ix = gi.x * cx;
    float cont_iy = gi.y * cxy;
    float cont_iz = gi.z * cxz;

    float ey_r = psi_y[lab] + cont_yx + cont_yy + cont_yz;
    float ei_r = psi_i[lab] + cont_ix + cont_iy + cont_iz;
    // Barth–Jespersen overshoot guard over the 26-neighbourhood. lo/hi are
    // the min/max of the site's own value and every DISTINCT site in the
    // 3×3×3 grid stencil — the full set of Voronoi neighbours touching this
    // cell, enough to bound a linear field at a point inside the cell (the
    // cell lies in the convex hull of its Voronoi neighbours). An interior
    // cell (all 26 = the same site) has lo==hi==ψ_s and is left UNCLAMPED
    // so the smooth linear extrapolation is preserved. For any linear field
    // the clamp is a no-op → linear-exactness is preserved.
    float lo_y = psi_y[lab], hi_y = lo_y;
    float lo_i = psi_i[lab], hi_i = lo_i;
    bool has_n = false;
    for (int di = -1; di <= 1; di++) {
        for (int dj = -1; dj <= 1; dj++) {
            for (int dk = -1; dk <= 1; dk++) {
                if (di == 0 && dj == 0 && dk == 0) continue;
                int ii = (i + di + Nn) % Nn;
                int jj = (j + dj + Nn) % Nn;
                int kk = (k + dk + Nn) % Nn;
                int nb = labels[ii * Nn * Nn + jj * Nn + kk];
                if (nb >= 0 && nb < ns && nb != lab) {
                    has_n = true;
                    float vy = psi_y[nb];
                    float vi = psi_i[nb];
                    lo_y = min(lo_y, vy); hi_y = max(hi_y, vy);
                    lo_i = min(lo_i, vi); hi_i = max(hi_i, vi);
                }
            }
        }
    }
    if (has_n) {
        ey_r = clamp(ey_r, lo_y, hi_y);
        ei_r = clamp(ei_r, lo_i, hi_i);
    }
    ey[int(gid)] = ey_r;
    ei[int(gid)] = ei_r;
    q[int(gid)] = ey_r * ey_r + ei_r * ei_r;
}
