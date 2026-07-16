#[compute]
#version 450
// Cassi Qi-enhanced N-body gravity.
// Replaces O(N^2) pairwise summation with O(N) field evaluation.
//
// Force:  F_i = G_eff(r_i) * M_enc(<r_i) / r_i^2  (radial)
// where   G_eff(r) = (pi/rho)(r) * (1 + xi * q(r)) * G
//         q(r) = 1 - exp(-beta * max(pi/rho(r) - phi^-3, 0))
//
// The Yang halo is modelled analytically: pi/rho rises from
// phi-equilibrium at the core to a plateau in the outer halo,
// creating the dark-matter-like flat rotation curve.
//
// Push constants: N, G, eps2, xi
// Cassi params:    qi_beta, halo_radius, halo_width, pi_max

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict buffer PositionBuf { float p[]; };
layout(set = 0, binding = 1, std430) restrict buffer AccelBuf   { float a[]; };

layout(push_constant, std430) uniform PC {
    float N_f;        // particle count
    float G;           // base gravitational constant
    float eps2;        // softening squared
    float xi;          // Qi coupling constant (18.0)

    float qi_beta;     // Qi saturation sharpness (3.0)
    float halo_radius; // r where Yang halo begins
    float halo_width;  // transition width
    float pi_max;      // maximum pi/rho in halo (0.5-0.7)

    float cluster_a;   // Plummer scale radius
    float M_total;     // total cluster mass
    float _pad1;
    float _pad2;
} pc;

const float PHI = 1.618033988749895;
const float PI_EQ = (PHI - 1.0) / (PHI + 1.0); // phi^-3 approx 0.236

// --- Yang halo profile (analytical) ---

float pi_rho_at(float r) {
    // Sigmoid transition from equilibrium at core to Yang plateau in halo
    float t = (r - pc.halo_radius) / max(pc.halo_width, 0.01);
    float sig = 1.0 / (1.0 + exp(-t)); // logistic sigmoid
    return PI_EQ + (pc.pi_max - PI_EQ) * sig;
}

// --- Qi coherence ---

float qi_coherence(float pr) {
    float excess = max(pr - PI_EQ, 0.0);
    return 1.0 - exp(-pc.qi_beta * excess);
}

// --- Enclosed mass (Plummer sphere) ---

float enclosed_mass(float r) {
    float r2 = r * r + pc.cluster_a * pc.cluster_a;
    float r3 = r * r * r;
    float denom = r2 * sqrt(r2);
    return pc.M_total * r3 / max(denom, 0.00001);
}

// --- Main ---

void main() {
    int N = int(pc.N_f);
    int i = int(gl_GlobalInvocationID.x);
    if (i >= N) return;

    float xi = p[i*4];
    float yi = p[i*4 + 1];
    float zi = p[i*4 + 2];
    float mi = p[i*4 + 3];

    float r2 = xi*xi + yi*yi + zi*zi;
    float r  = sqrt(r2 + pc.eps2);

    // --- Cassi Qi force (O(1) per particle!) ---
    float pr    = pi_rho_at(r);
    float q     = qi_coherence(pr);
    float G_eff = pr * (1.0 + pc.xi * q) * pc.G;
    float M_enc = enclosed_mass(r);

    float f_mag = G_eff * M_enc / max(r2 + pc.eps2, 0.00001);
    // Radial direction (pointing toward center)
    float inv_r = inversesqrt(max(r2, 0.00001));
    float fx = -f_mag * xi * inv_r;
    float fy = -f_mag * yi * inv_r;
    float fz = -f_mag * zi * inv_r;

    // Store acceleration
    a[i*4]     = fx;
    a[i*4 + 1] = fy;
    a[i*4 + 2] = fz;
    a[i*4 + 3] = 0.0;
}
