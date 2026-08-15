#[compute]
// Gate-vi probe shader (B-build piece 2 — the coarse-fine patch interface).
// The FINE patch tile: a padded N³ box (the rim = one ring of ghost cells
// holding the COARSE field's interpolated values) running the SAME two-fluid
// leapfrog numerics as the canonical cassi_two_fluid.glsl (the 19-point
// anisotropic lap with the h0²-normalized weights, the velocity-Verlet
// update) with the PERIODIC WRAP REPLACED by the linear padded addressing —
// the boundary stencils read the rim instead of wrapping.
//
// Modes:
//   0 = rim-fill:   the padded shell cells <- the coarse field's trilinear
//                   values at the shell-cell world positions (periodic wrap
//                   in the coarse map);
//   1 = pass A:     the leapfrog into the padded scratch (interior cells);
//   2 = pass B:     the scratch -> the canonical fine ey/ei/q/vel;
//   3 = downsample: the covered coarse cells <- the average of the fine
//                   cells they contain (the fine y/z cells align 1:1 with
//                   the coarse; the x-ratio r = h_cx/h_fx is an integer —
//                   exactly r fine cells per covered coarse cell).
//
// Set 0: bindings 0-5 = the fine padded buffers (ey, ei, q, vel, rho, scr),
//        6/7 = the coarse ey/ei (the sim's canonical field buffers).
// PC: 21 floats (84 B) — see the layout block.
#version 450

layout(local_size_x = 4, local_size_y = 4, local_size_z = 4) in;

layout(set = 0, binding = 0, std430) restrict buffer FineEY { float fey[]; };
layout(set = 0, binding = 1, std430) restrict buffer FineEI { float fei[]; };
layout(set = 0, binding = 2, std430) buffer FineQ { float fq[]; };
layout(set = 0, binding = 3, std430) buffer FineVel { vec4 fvel[]; };
layout(set = 0, binding = 4, std430) buffer FineRho { float frho[]; };
layout(set = 0, binding = 5, std430) buffer FineScr { vec4 fscr[]; };
layout(set = 0, binding = 6, std430) restrict buffer CoarseEY { float cey[]; };
layout(set = 0, binding = 7, std430) restrict buffer CoarseEI { float cei[]; };

layout(push_constant, std430) uniform PC {
    float N_fx; float N_fy; float N_fz;      // the fine tile's logical cells per axis
    float dt; float phi; float omega2;
    float ext_fx; float ext_fy; float ext_fz; // the fine tile's half-extents (world)
    float mode;
    float N_c; float ext_cx; float ext_cy; float ext_cz; // the coarse grid
    float x_off; float y_off; float z_off;   // the tile's center in the coarse [-1,1] coords
    float padx; float pady; float padz;      // the padded widths (logical + 2)
    float r_ratio;                           // h_cx / h_fx (integer for the downsample)
    float h0_c;                              // the COARSE wave-speed scale (min(ext_c)/hn_c)
} pc;

int fidx(int px, int py, int pz) {
    int pw = int(pc.padx);
    int ph = int(pc.pady);
    int pd = int(pc.padz);
    return px + pw * (py + ph * pz);
}

int cidx(int i, int j, int k) {
    int N = int(pc.N_c);
    return i + N * (j + N * k);
}

// ── The coarse field, trilinear at a world point (periodic wrap) ────────
vec2 coarse_sample(float wx, float wy, float wz) {
    int N = int(pc.N_c);
    float hx = 2.0 * pc.ext_cx / float(N);
    float hy = 2.0 * pc.ext_cy / float(N);
    float hz = 2.0 * pc.ext_cz / float(N);
    float fx = (wx + pc.ext_cx) / hx - 0.5;
    float fy = (wy + pc.ext_cy) / hy - 0.5;
    float fz = (wz + pc.ext_cz) / hz - 0.5;
    int i0 = int(floor(fx));
    int j0 = int(floor(fy));
    int k0 = int(floor(fz));
    float ax = fx - float(i0);
    float ay = fy - float(j0);
    float az = fz - float(k0);
    int wi0 = ((i0 % N) + N) % N; int wi1 = ((i0 + 1) % N + N) % N;
    int wj0 = ((j0 % N) + N) % N; int wj1 = ((j0 + 1) % N + N) % N;
    int wk0 = ((k0 % N) + N) % N; int wk1 = ((k0 + 1) % N + N) % N;
    float e000 = cey[cidx(wi0, wj0, wk0)];
    float e100 = cey[cidx(wi1, wj0, wk0)];
    float e010 = cey[cidx(wi0, wj1, wk0)];
    float e110 = cey[cidx(wi1, wj1, wk0)];
    float e001 = cey[cidx(wi0, wj0, wk1)];
    float e101 = cey[cidx(wi1, wj0, wk1)];
    float e011 = cey[cidx(wi0, wj1, wk1)];
    float e111 = cey[cidx(wi1, wj1, wk1)];
    float c00 = mix(e000, e100, ax);
    float c10 = mix(e010, e110, ax);
    float c01 = mix(e001, e101, ax);
    float c11 = mix(e011, e111, ax);
    float ey_s = mix(mix(c00, c10, ay), mix(c01, c11, ay), az);
    float i000 = cei[cidx(wi0, wj0, wk0)];
    float i100 = cei[cidx(wi1, wj0, wk0)];
    float i010 = cei[cidx(wi0, wj1, wk0)];
    float i110 = cei[cidx(wi1, wj1, wk0)];
    float i001 = cei[cidx(wi0, wj0, wk1)];
    float i101 = cei[cidx(wi1, wj0, wk1)];
    float i011 = cei[cidx(wi0, wj1, wk1)];
    float i111 = cei[cidx(wi1, wj1, wk1)];
    float d00 = mix(i000, i100, ax);
    float d10 = mix(i010, i110, ax);
    float d01 = mix(i001, i101, ax);
    float d11 = mix(i011, i111, ax);
    float ei_s = mix(mix(d00, d10, ay), mix(d01, d11, ay), az);
    return vec2(ey_s, ei_s);
}

// ── The 19-point anisotropic lap (the canonical weights, linear padded
//    addressing — the rim cells at px=0 and px=padx-1 hold the coarse
//    values so the boundary stencils read them instead of wrapping) ──────
float lap_fey(int px, int py, int pz) {
    float hn = pc.N_fx * 0.5;
    float hx = pc.ext_fx / hn;
    float hy = pc.ext_fy / hn;
    float hz = pc.ext_fz / hn;
    float h0 = pc.h0_c;   // the COARSE scale — the fine wave travels at the coarse's speed
    float hx2 = hx * hx; float hy2 = hy * hy; float hz2 = hz * hz; float h02 = h0 * h0;
    float bxy = (1.0 / 3.0) * h02 / (hx2 + hy2);
    float bxz = (1.0 / 3.0) * h02 / (hx2 + hz2);
    float byz = (1.0 / 3.0) * h02 / (hy2 + hz2);
    float ax = h02 / hx2 - 2.0 * (bxy + bxz);
    float ay = h02 / hy2 - 2.0 * (bxy + byz);
    float az = h02 / hz2 - 2.0 * (bxz + byz);
    float e = fey[fidx(px, py, pz)];
    float axis_x = fey[fidx(px + 1, py, pz)] + fey[fidx(px - 1, py, pz)] - 2.0 * e;
    float axis_y = fey[fidx(px, py + 1, pz)] + fey[fidx(px, py - 1, pz)] - 2.0 * e;
    float axis_z = fey[fidx(px, py, pz + 1)] + fey[fidx(px, py, pz - 1)] - 2.0 * e;
    float fd_xy = (fey[fidx(px + 1, py + 1, pz)] + fey[fidx(px - 1, py + 1, pz)]
                 + fey[fidx(px + 1, py - 1, pz)] + fey[fidx(px - 1, py - 1, pz)] - 4.0 * e);
    float fd_xz = (fey[fidx(px + 1, py, pz + 1)] + fey[fidx(px - 1, py, pz + 1)]
                 + fey[fidx(px + 1, py, pz - 1)] + fey[fidx(px - 1, py, pz - 1)] - 4.0 * e);
    float fd_yz = (fey[fidx(px, py + 1, pz + 1)] + fey[fidx(px, py - 1, pz + 1)]
                 + fey[fidx(px, py + 1, pz - 1)] + fey[fidx(px, py - 1, pz - 1)] - 4.0 * e);
    return ax * axis_x + ay * axis_y + az * axis_z
         + bxy * fd_xy + bxz * fd_xz + byz * fd_yz;
}

float lap_fei(int px, int py, int pz) {
    float hn = pc.N_fx * 0.5;
    float hx = pc.ext_fx / hn;
    float hy = pc.ext_fy / hn;
    float hz = pc.ext_fz / hn;
    float h0 = pc.h0_c;   // the COARSE scale — the fine wave travels at the coarse's speed
    float hx2 = hx * hx; float hy2 = hy * hy; float hz2 = hz * hz; float h02 = h0 * h0;
    float bxy = (1.0 / 3.0) * h02 / (hx2 + hy2);
    float bxz = (1.0 / 3.0) * h02 / (hx2 + hz2);
    float byz = (1.0 / 3.0) * h02 / (hy2 + hz2);
    float ax = h02 / hx2 - 2.0 * (bxy + bxz);
    float ay = h02 / hy2 - 2.0 * (bxy + byz);
    float az = h02 / hz2 - 2.0 * (bxz + byz);
    float e = fei[fidx(px, py, pz)];
    float axis_x = fei[fidx(px + 1, py, pz)] + fei[fidx(px - 1, py, pz)] - 2.0 * e;
    float axis_y = fei[fidx(px, py + 1, pz)] + fei[fidx(px, py - 1, pz)] - 2.0 * e;
    float axis_z = fei[fidx(px, py, pz + 1)] + fei[fidx(px, py, pz - 1)] - 2.0 * e;
    float fd_xy = (fei[fidx(px + 1, py + 1, pz)] + fei[fidx(px - 1, py + 1, pz)]
                 + fei[fidx(px + 1, py - 1, pz)] + fei[fidx(px - 1, py - 1, pz)] - 4.0 * e);
    float fd_xz = (fei[fidx(px + 1, py, pz + 1)] + fei[fidx(px - 1, py, pz + 1)]
                 + fei[fidx(px + 1, py, pz - 1)] + fei[fidx(px - 1, py, pz - 1)] - 4.0 * e);
    float fd_yz = (fei[fidx(px, py + 1, pz + 1)] + fei[fidx(px, py - 1, pz + 1)]
                 + fei[fidx(px, py + 1, pz - 1)] + fei[fidx(px, py - 1, pz - 1)] - 4.0 * e);
    return ax * axis_x + ay * axis_y + az * axis_z
         + bxy * fd_xy + bxz * fd_xz + byz * fd_yz;
}

// ── Mode 0: rim-fill — the padded shell from the coarse field ───────────
void rim_fill() {
    int pw = int(pc.padx);
    int ph = int(pc.pady);
    int pd = int(pc.padz);
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    if (gid.x >= pw || gid.y >= ph || gid.z >= pd) return;
    int px = gid.x;
    int py = gid.y;
    int pz = gid.z;
    if (px >= 1 && px < pw - 1 && py >= 1 && py < ph - 1 && pz >= 1 && pz < pd - 1) {
        return;   // the interior is owned by the leapfrog
    }
    float hfx = 2.0 * pc.ext_fx / pc.N_fx;
    float hfy = 2.0 * pc.ext_fy / pc.N_fy;
    float hfz = 2.0 * pc.ext_fz / pc.N_fz;
    float wx = pc.x_off * pc.ext_cx - pc.ext_fx + (float(px) - 0.5) * hfx;
    float wy = pc.y_off * pc.ext_cy - pc.ext_fy + (float(py) - 0.5) * hfy;
    float wz = pc.z_off * pc.ext_cz - pc.ext_fz + (float(pz) - 0.5) * hfz;
    vec2 v = coarse_sample(wx, wy, wz);
    int id = fidx(px, py, pz);
    fey[id] = v.x;
    fei[id] = v.y;
}

// ── Mode 1: pass A — the leapfrog into the padded scratch (interior) ────
void pass_a() {
    int Nx = int(pc.N_fx);
    int Ny = int(pc.N_fy);
    int Nz = int(pc.N_fz);
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    if (gid.x >= Nx || gid.y >= Ny || gid.z >= Nz) return;
    int px = gid.x + 1;
    int py = gid.y + 1;
    int pz = gid.z + 1;
    int id = fidx(px, py, pz);
    float ey_old = fey[id];
    float ei_old = fei[id];
    vec4 vel_old = fvel[id];
    float lap_ey = lap_fey(px, py, pz);
    float lap_ei = lap_fei(px, py, pz);
    float omega2 = pc.omega2;
    float phi = pc.phi;
    float diff = ey_old - phi * ei_old;
    float acc_ey = lap_ey - omega2 * diff;
    float acc_ei = lap_ei + omega2 * diff;
    float dt = pc.dt;
    float vx_new = vel_old.x + acc_ey * dt;
    float vy_new = vel_old.y + acc_ei * dt;
    float ey_new = ey_old + vx_new * dt;   // no source (gate-vi: pure wave)
    float ei_new = ei_old + vy_new * dt;
    fscr[id] = vec4(ey_new, ei_new, vx_new, vy_new);
}

// ── Mode 2: pass B — the scratch -> the canonical fine buffers ──────────
void pass_b() {
    int Nx = int(pc.N_fx);
    int Ny = int(pc.N_fy);
    int Nz = int(pc.N_fz);
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    if (gid.x >= Nx || gid.y >= Ny || gid.z >= Nz) return;
    int id = fidx(gid.x + 1, gid.y + 1, gid.z + 1);
    vec4 s = fscr[id];
    float ey_new = s.x;
    float ei_new = s.y;
    float phi = pc.phi;
    float q_val = ey_new * ey_new + ei_new * ei_new;
    float eps = ey_new - phi * ei_new;
    fey[id] = ey_new;
    fei[id] = ei_new;
    fq[id] = q_val;
    fvel[id] = vec4(s.z, s.w, 0.0, eps * eps);
}

// ── Mode 3: downsample — the covered coarse cells <- the fine average ───
void downsample() {
    int N = int(pc.N_c);
    int r = int(pc.r_ratio + 0.5);
    float lo = pc.x_off - pc.ext_fx / pc.ext_cx;
    float hi = pc.x_off + pc.ext_fx / pc.ext_cx;
    int cx0 = int(ceil((lo + 1.0) * pc.N_c * 0.5));
    int cx1 = int(floor((hi + 1.0) * pc.N_c * 0.5)) - 1;
    int ncx = cx1 - cx0 + 1;
    if (ncx <= 0) return;
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    int total = ncx * N * N;
    if (gid.x >= total) return;
    int cx = cx0 + gid.x % ncx;
    int cy = (gid.x / ncx) % N;
    int cz = gid.x / (ncx * N);
    int fx0 = (cx - cx0) * r;
    float acc_ey = 0.0;
    float acc_ei = 0.0;
    for (int fx = 0; fx < r; ++fx) {
        int id = fidx(fx0 + fx + 1, cy + 1, cz + 1);
        acc_ey += fey[id];
        acc_ei += fei[id];
    }
    cey[cidx(cx, cy, cz)] = acc_ey / float(r);
    cei[cidx(cx, cy, cz)] = acc_ei / float(r);
}

void main() {
    float m = pc.mode;
    if (m < 0.5) {
        rim_fill();
    } else if (m < 1.5) {
        pass_a();
    } else if (m < 2.5) {
        pass_b();
    } else {
        downsample();
    }
}
