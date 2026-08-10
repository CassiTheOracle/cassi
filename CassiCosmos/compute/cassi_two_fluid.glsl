#[compute]
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
layout(push_constant, std430) uniform PC {
    float N_f; float dt; float t; float phi;
    float xi; float eps2; float particle_N;
    float mode; float source_strength; float num_clusters;
    float gravity_mode;  // unused here (nbody gravity selector)
} pc;

// ── Index helpers ─────────────────────────────────────────────────────
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

// 19-point isotropic periodic Laplacian (inlined per field — strict GLSL
// rejects unsized array function parameters, which silently disabled this
// shader in earlier builds). Weights: 6 axis neighbors 1/3 each, 12 face
// diagonals 1/6 each, center −4. Symbol ω19² = k² − (1/12)(kx²+ky²+kz²)²
// + O(k⁶): the quartic term is isotropic, so dispersion anisotropy is
// O(h⁶) instead of the 7-point's O(h²). The 7-point's anisotropy bowed the
// [110] front inward 2–4% with the corner-to-face gap growing linearly
// with radius — the user's "the ring becomes a square". Max |symbol| 5.333
// vs 12.000 (7-point): CFL bound relaxes 1.5×; dt=0.001 is far below both.
float lap_ey_at(int i, int j, int k) {
    int N = int(pc.N_f);
    int ip = (i + 1) % N; int im = (i - 1 + N) % N;
    int jp = (j + 1) % N; int jm = (j - 1 + N) % N;
    int kp = (k + 1) % N; int km = (k - 1 + N) % N;
    float axis = (ey[idx3(ip, j, k)] + ey[idx3(im, j, k)]
                + ey[idx3(i, jp, k)] + ey[idx3(i, jm, k)]
                + ey[idx3(i, j, kp)] + ey[idx3(i, j, km)]
                - 6.0 * ey[idx3(i, j, k)]);
    float fd = (ey[idx3(ip, jp, k)] + ey[idx3(im, jp, k)]
              + ey[idx3(ip, jm, k)] + ey[idx3(im, jm, k)]
              + ey[idx3(ip, j, kp)] + ey[idx3(im, j, kp)]
              + ey[idx3(ip, j, km)] + ey[idx3(im, j, km)]
              + ey[idx3(i, jp, kp)] + ey[idx3(i, jm, kp)]
              + ey[idx3(i, jp, km)] + ey[idx3(i, jm, km)]
              - 12.0 * ey[idx3(i, j, k)]);
    return (1.0 / 3.0) * axis + (1.0 / 6.0) * fd;
}

float lap_ei_at(int i, int j, int k) {
    int N = int(pc.N_f);
    int ip = (i + 1) % N; int im = (i - 1 + N) % N;
    int jp = (j + 1) % N; int jm = (j - 1 + N) % N;
    int kp = (k + 1) % N; int km = (k - 1 + N) % N;
    float axis = (ei[idx3(ip, j, k)] + ei[idx3(im, j, k)]
                + ei[idx3(i, jp, k)] + ei[idx3(i, jm, k)]
                + ei[idx3(i, j, kp)] + ei[idx3(i, j, km)]
                - 6.0 * ei[idx3(i, j, k)]);
    float fd = (ei[idx3(ip, jp, k)] + ei[idx3(im, jp, k)]
              + ei[idx3(ip, jm, k)] + ei[idx3(im, jm, k)]
              + ei[idx3(ip, j, kp)] + ei[idx3(im, j, kp)]
              + ei[idx3(ip, j, km)] + ei[idx3(im, j, km)]
              + ei[idx3(i, jp, kp)] + ei[idx3(i, jm, kp)]
              + ei[idx3(i, jp, km)] + ei[idx3(i, jm, km)]
              - 12.0 * ei[idx3(i, j, k)]);
    return (1.0 / 3.0) * axis + (1.0 / 6.0) * fd;
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

// ── Main kernel ───────────────────────────────────────────────────────
void main() {
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
    float omega2 = 20.0;  // ω₀² — resonance frequency
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

    // Compute q = (EY² + EI²) normalized
    float q_val = ey_new * ey_new + ei_new * ei_new;

    // Compute ε² = (EY − φ·EI)²
    float eps = ey_new - phi * ei_new;
    float eps2 = eps * eps;

    // Write back
    ey[id] = ey_new;
    ei[id] = ei_new;
    q[id] = q_val;
    vel[id] = vec4(vx_new, vy_new, 0.0, eps2);
}
