#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 16 floats (64 B); set 0: bindings 0-5
#version 450
// Cassi Two-Fluid PDE Solver — 3D finite-difference leapfrog integration.
// Evolves EY (Yang) and EI (Yin) fields on a regular grid.
// (Naming per the theory convention: ρ = EY+EI, Π = EY−EI, ε = EY−φ·EI;
// see hypotheses/gravity-from-flow.md §1.1 — EY is the YANG field.)
//
// Equations:
//   ∂²EY/∂t² = c²·∇²EY − ω₀²·(EY − φ·EI)
//   ∂²EI/∂t² = c²·∇²EI + ω₀²·(EY − φ·EI)
//
// Leapfrog scheme: second-order centered in time and space.
// Each thread updates one grid cell.

layout(local_size_x = 4, local_size_y = 4, local_size_z = 4) in;

// ── Field grid buffers (SET 0) ───────────────────────────────────────
layout(set = 0, binding = 0, std430) restrict buffer FieldEY { float ey[]; };
layout(set = 0, binding = 1, std430) restrict buffer FieldEI { float ei[]; };
layout(set = 0, binding = 2, std430) buffer FieldQ { float q[]; };
layout(set = 0, binding = 3, std430) buffer FieldVel { vec4 vel[]; };
layout(set = 0, binding = 4, std430) coherent readonly buffer MassDensity { float rho[]; };
// Double-buffered PDE scratch (DETERMINISM fix, 2026-08-14): pass A
// (pc.pass_sel == 0) computes the new field into THIS buffer (read-old /
// write-scratch — the read and write buffers never alias within a
// dispatch); pass B (pc.pass_sel == 1) copies scratch → the canonical
// ey/ei/q/vel. The single-pass version wrote the field in the SAME
// dispatch that read the 19-point neighbor stencil: a thread could read
// a neighbor's NEW value (its write landed first) — a genuine in-dispatch
// read-after-write race, 1-ULP field nondeterminism in ~0.04% of cells
// per step (verified run-to-run, and it feeds the particle forces via
// the river arm's trilinear samples — the real floor behind the old
// ~3.8e-6 parity gap). Scratch is fully overwritten every pass A, so it
// never needs clearing. vec4 = (ey_new, ei_new, vx_new, vy_new).
layout(set = 0, binding = 5, std430) buffer FieldScratch { vec4 scr[]; };
layout(push_constant, std430) uniform PC {
    float N_f; float dt; float t; float phi;
    float xi; float eps2; float particle_N;
    float mode; float source_strength; float num_clusters;
    float gravity_mode;  // unused here (nbody gravity selector)
    float extent_x; float extent_y; float extent_z;  // per-axis box half-extents (GRID_LAYOUT.md §2.5)
    float pass_sel;      // 0 = pass A (compute → scr), 1 = pass B (scr → field)
    float omega2;       // ω₀² — resonance frequency (default 20.0)
} pc;

// ── Index helpers ─────────────────────────────────────────────────────
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

// 19-point periodic Laplacian, ANISOTROPIC on the φ-aspect box (inlined
// per field — strict GLSL rejects unsized array function parameters,
// which silently disabled this shader in earlier builds). Cube weights:
// 6 axis neighbors 1/3 each, 12 face diagonals 1/6 each, center −4.
// Symbol ω19² = k² − (1/12)(kx²+ky²+kz²)² + O(k⁶): the quartic term is
// isotropic, so dispersion anisotropy is O(h⁶) instead of the 7-point's
// O(h²). The 7-point's anisotropy bowed the [110] front inward 2–4% with
// the corner-to-face gap growing linearly with radius — the user's "the
// ring becomes a square". Max |symbol| 5.333 vs 12.000 (7-point): CFL
// bound relaxes 1.5×; dt=0.001 is far below both.
//
// PER-AXIS EXTENSION (GRID_LAYOUT.md §2.5): with h_i = 2·extent_i/N the
// weights become
//   b_ij = (1/3)·h₀²/(h_i²+h_j²),   a_i = h₀²/h_i² − 2·(b_ij + b_ik),
//   h₀ = 2·min(extent_i)/N  (the reference cell size — at the cube and
//   the (φ,1,φ²) presets the min-extent axis IS the unit-aspect axis, so
//   h₀ = 2·extent_base/N exactly; any aspect inherits uniform-rescale
//   invariance). DERIVATION: the face-diagonal stencil sum approximates
//   F_ij ≈ 2h_i²∂²_iψ + 2h_j²∂²_jψ (the 4-neighbor average carries a
//   factor 2 — its symbol is 4(cosθ_icosθ_j − 1)), so the ∂²_i coefficient
//   is h_i²(a_i + 2b_ij + 2b_ik); constraining it to h₀² (the cube's
//   normalization — the current operator reads h²∇²) gives the a_i above.
//   The leading symbol is −h₀²·k²_phys — EXACTLY ISOTROPIC in physical
//   wavenumbers (matches the per-axis Poisson symbol); the O(k⁴) terms
//   are direction-dependent (∝ h_i⁴k_i⁴ — unavoidable on an anisotropic
//   lattice), which is the expected ellipsoidal dispersion at fixed
//   physical |k| (verify_phi_box check e pins it to the analytic symbol).
//   The weights reduce EXACTLY to (1/3, 1/6) at unit aspect (fp32-exact:
//   (1/3)·h02/(2·h02) = (1/3)/2 = 1/6). At the (φ,1,φ²) aspect the
//   weights are a = (0.127, 0.731, −0.009), b = (0.092, 0.035, 0.042);
//   a_z is slightly negative but the symbol stays negative-definite
//   (max|S| ≈ 4.05 at (π,π,0) — LOWER than the cube's 8.00 at (π,π,π) /
//   5.33 at (π,π,0)), so the CFL bound is relaxed, not tightened.
float lap_ey_at(int i, int j, int k) {
    int N = int(pc.N_f);
    int ip = (i + 1) % N; int im = (i - 1 + N) % N;
    int jp = (j + 1) % N; int jm = (j - 1 + N) % N;
    int kp = (k + 1) % N; int km = (k - 1 + N) % N;
    float hn = float(N) * 0.5;
    float hx = pc.extent_x / hn;
    float hy = pc.extent_y / hn;
    float hz = pc.extent_z / hn;
    float h0 = min(min(pc.extent_x, pc.extent_y), pc.extent_z) / hn;
    float hx2 = hx * hx; float hy2 = hy * hy; float hz2 = hz * hz; float h02 = h0 * h0;
    float bxy = (1.0 / 3.0) * h02 / (hx2 + hy2);
    float bxz = (1.0 / 3.0) * h02 / (hx2 + hz2);
    float byz = (1.0 / 3.0) * h02 / (hy2 + hz2);
    float ax = h02 / hx2 - 2.0 * (bxy + bxz);
    float ay = h02 / hy2 - 2.0 * (bxy + byz);
    float az = h02 / hz2 - 2.0 * (bxz + byz);
    float e = ey[idx3(i, j, k)];
    float axis_x = ey[idx3(ip, j, k)] + ey[idx3(im, j, k)] - 2.0 * e;
    float axis_y = ey[idx3(i, jp, k)] + ey[idx3(i, jm, k)] - 2.0 * e;
    float axis_z = ey[idx3(i, j, kp)] + ey[idx3(i, j, km)] - 2.0 * e;
    float fd_xy = (ey[idx3(ip, jp, k)] + ey[idx3(im, jp, k)]
                 + ey[idx3(ip, jm, k)] + ey[idx3(im, jm, k)] - 4.0 * e);
    float fd_xz = (ey[idx3(ip, j, kp)] + ey[idx3(im, j, kp)]
                 + ey[idx3(ip, j, km)] + ey[idx3(im, j, km)] - 4.0 * e);
    float fd_yz = (ey[idx3(i, jp, kp)] + ey[idx3(i, jm, kp)]
                 + ey[idx3(i, jp, km)] + ey[idx3(i, jm, km)] - 4.0 * e);
    return ax * axis_x + ay * axis_y + az * axis_z
         + bxy * fd_xy + bxz * fd_xz + byz * fd_yz;
}

float lap_ei_at(int i, int j, int k) {
    int N = int(pc.N_f);
    int ip = (i + 1) % N; int im = (i - 1 + N) % N;
    int jp = (j + 1) % N; int jm = (j - 1 + N) % N;
    int kp = (k + 1) % N; int km = (k - 1 + N) % N;
    float hn = float(N) * 0.5;
    float hx = pc.extent_x / hn;
    float hy = pc.extent_y / hn;
    float hz = pc.extent_z / hn;
    float h0 = min(min(pc.extent_x, pc.extent_y), pc.extent_z) / hn;
    float hx2 = hx * hx; float hy2 = hy * hy; float hz2 = hz * hz; float h02 = h0 * h0;
    float bxy = (1.0 / 3.0) * h02 / (hx2 + hy2);
    float bxz = (1.0 / 3.0) * h02 / (hx2 + hz2);
    float byz = (1.0 / 3.0) * h02 / (hy2 + hz2);
    float ax = h02 / hx2 - 2.0 * (bxy + bxz);
    float ay = h02 / hy2 - 2.0 * (bxy + byz);
    float az = h02 / hz2 - 2.0 * (bxz + byz);
    float e = ei[idx3(i, j, k)];
    float axis_x = ei[idx3(ip, j, k)] + ei[idx3(im, j, k)] - 2.0 * e;
    float axis_y = ei[idx3(i, jp, k)] + ei[idx3(i, jm, k)] - 2.0 * e;
    float axis_z = ei[idx3(i, j, kp)] + ei[idx3(i, j, km)] - 2.0 * e;
    float fd_xy = (ei[idx3(ip, jp, k)] + ei[idx3(im, jp, k)]
                 + ei[idx3(ip, jm, k)] + ei[idx3(im, jm, k)] - 4.0 * e);
    float fd_xz = (ei[idx3(ip, j, kp)] + ei[idx3(im, j, kp)]
                 + ei[idx3(ip, j, km)] + ei[idx3(im, j, km)] - 4.0 * e);
    float fd_yz = (ei[idx3(i, jp, kp)] + ei[idx3(i, jm, kp)]
                 + ei[idx3(i, jp, km)] + ei[idx3(i, jm, km)] - 4.0 * e);
    return ax * axis_x + ay * axis_y + az * axis_z
         + bxy * fd_xy + bxz * fd_xz + byz * fd_yz;
}

// ── Perturbation source: Gaussian at center, or multiple seeds ────────
float source_ey(int i, int j, int k) {
    int N = int(pc.N_f);
    float halfn = float(N) * 0.5;  // 'half' is a reserved word in GLSL
    float dx = (float(i) - halfn) / halfn;
    float dy = (float(j) - halfn) / halfn;
    float dz = (float(k) - halfn) / halfn;
    float r2 = dx*dx + dy*dy + dz*dz;
	float s = pc.source_strength;
	float mr = rho[idx3(i, j, k)];
	return s * exp(-r2 * 4.0) + mr * 0.001;
}

float source_ei(int i, int j, int k) {
    // EI source at offset position (Yin-Yang separation)
    int N = int(pc.N_f);
    float halfn = float(N) * 0.5;  // 'half' is a reserved word in GLSL
    float dx = (float(i) - halfn * 0.7) / halfn;
    float dy = (float(j) - halfn * 0.8) / halfn;
    float dz = (float(k) - halfn * 0.6) / halfn;
    float r2 = dx*dx + dy*dy + dz*dz;
	float s = pc.source_strength * 0.707; // 1/sqrt(2) for EI
	float mr = rho[idx3(i, j, k)] * 0.707;
	return s * exp(-r2 * 4.0) + mr * 0.001;
}

// ── Pass A (pc.pass_sel == 0): compute the new field into scratch ────
// Reads the canonical ey/ei/vel/rho (old values) and writes ONLY scr —
// no read/write aliasing within the dispatch, so the 19-point stencil
// sees the OLD field deterministically (no in-dispatch race).
void pass_a() {
    int N = int(pc.N_f);
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    if (gid.x >= N || gid.y >= N || gid.z >= N) return;

    int i = gid.x, j = gid.y, k = gid.z;
    int id = idx3(i, j, k);

    // Read current fields
    float ey_old = ey[id];
    float ei_old = ei[id];
    vec4 vel_old = vel[id];

    // Laplacian
    float lap_ey = lap_ey_at(i, j, k);
    float lap_ei = lap_ei_at(i, j, k);

    // φ coupling terms
    float omega2 = pc.omega2;  // ω₀² — resonance frequency (default 20.0)
    float phi = pc.phi;
    float ey_ei_diff = ey_old - phi * ei_old;

    // Leapfrog: ∂²ψ/∂t² = c²·∇²ψ ∓ ω₀²·(EY − φ·EI)
    // Using vel.xyz as time derivative (∂EY/∂t, ∂EI/∂t, ...)
    float acc_ey = lap_ey - omega2 * ey_ei_diff;
    float acc_ei = lap_ei + omega2 * ey_ei_diff;

    float dt = pc.dt;

    // Update velocity (half-step)
    float vx_new = vel_old.x + acc_ey * dt;
    float vy_new = vel_old.y + acc_ei * dt;

    // Update fields
    float ey_new = ey_old + vx_new * dt + source_ey(i, j, k) * dt * dt;
    float ei_new = ei_old + vy_new * dt + source_ei(i, j, k) * dt * dt;

    scr[id] = vec4(ey_new, ei_new, vx_new, vy_new);
}

// ── Pass B (pc.pass_sel == 1): scratch → canonical field ─────────────
// Reads ONLY scr (written by pass A, barrier-ordered); writes the
// canonical ey/ei/q/vel. q and ε² are recomputed from the scratch values
// — bit-identical to the single-pass formulas.
void pass_b() {
    int N = int(pc.N_f);
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    if (gid.x >= N || gid.y >= N || gid.z >= N) return;

    int i = gid.x, j = gid.y, k = gid.z;
    int id = idx3(i, j, k);

    vec4 s = scr[id];
    float ey_new = s.x;
    float ei_new = s.y;
    float phi = pc.phi;

    // q = (EY² + EI²) normalized
    float q_val = ey_new * ey_new + ei_new * ei_new;

    // ε² = (EY − φ·EI)²
    float eps = ey_new - phi * ei_new;
    float eps2 = eps * eps;

    ey[id] = ey_new;
    ei[id] = ei_new;
    q[id] = q_val;
    vel[id] = vec4(s.z, s.w, 0.0, eps2);
}

void main() {
    if (pc.pass_sel > 0.5) {
        pass_b();
    } else {
        pass_a();
    }
}
