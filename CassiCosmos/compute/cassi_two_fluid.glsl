#[compute]
#version 450
// Cassi Two-Fluid PDE Solver — 3D finite-difference leapfrog integration.
// Evolves EY (Yin) and EI (Yang) fields on a regular grid.
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
layout(set = 0, binding = 4, std430) coherent readonly buffer MassDensity { uint rho[]; };
layout(set = 0, binding = 3, std430) buffer FieldVel { vec4 vel[]; };
layout(push_constant, std430) uniform PC {
    float N_f; float dt; float t; float phi;
    float xi; float eps2; float particle_N;
    float mode; float source_strength; float num_clusters;
} pc;

// ── Index helpers ─────────────────────────────────────────────────────
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

float laplacian(int i, int j, int k, float field[]) {
    int N = int(pc.N_f);
    int Ni = (i + 1) % N;
    int Nj = (j + 1) % N;
    int Nk = (k + 1) % N;
    int Pi = (i - 1 + N) % N;
    int Pj = (j - 1 + N) % N;
    int Pk = (k - 1 + N) % N;

    return (field[idx3(Ni, j, k)] + field[idx3(Pi, j, k)]
          + field[idx3(i, Nj, k)] + field[idx3(i, Pj, k)]
          + field[idx3(i, j, Nk)] + field[idx3(i, j, Pk)]
          - 6.0 * field[idx3(i, j, k)]);
}

// ── Perturbation source: Gaussian at center, or multiple seeds ────────
float source_ey(int i, int j, int k) {
    int N = int(pc.N_f);
    float half = float(N) * 0.5;
    float dx = (float(i) - half) / half;
    float dy = (float(j) - half) / half;
    float dz = (float(k) - half) / half;
    float r2 = dx*dx + dy*dy + dz*dz;
	float s = pc.source_strength;
	float mr = uintBitsToFloat(rho[idx3(i, j, k)]);
	return s * exp(-r2 * 4.0) + mr * 0.001;
}

float source_ei(int i, int j, int k) {
    // EI source at offset position (Yin-Yang separation)
    int N = int(pc.N_f);
    float half = float(N) * 0.5;
    float dx = (float(i) - half * 0.7) / half;
    float dy = (float(j) - half * 0.8) / half;
    float dz = (float(k) - half * 0.6) / half;
    float r2 = dx*dx + dy*dy + dz*dz;
	float s = pc.source_strength * 0.707; // 1/sqrt(2) for EI
	float mr = uintBitsToFloat(rho[idx3(i, j, k)]) * 0.707;
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
    float lap_ey = laplacian(i, j, k, ey);
    float lap_ei = laplacian(i, j, k, ei);

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
