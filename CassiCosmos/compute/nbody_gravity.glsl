#[compute]
#version 450
// Cassi Qi-enhanced N-body gravity — O(N) field evaluation per particle.
// Replaces pairwise force summation with Yang halo field.
//
// Force: F_i = G_eff(r_i) * M_enc(<r_i) / r_i^2
// G_eff(r) = (pi/rho)(r) * (1 + xi * q(r)) * G
// q(r) = 1 - exp(-beta * max(pi/rho(r) - phi^-3, 0))
//
// pi/rho(r) modelled as sigmoid from phi^-3 (core) to pi_max (halo).

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict buffer PositionBuf { float p[]; };
layout(set = 0, binding = 1, std430) restrict buffer AccelBuf   { float a[]; };

layout(push_constant, std430) uniform PC {
    float N_f;        // 0: particle count
    float G;           // 1: base gravitational constant
    float eps2;        // 2: softening squared
    float xi;          // 3: Qi coupling constant (18.0)

    float qi_beta;     // 4: Qi saturation sharpness (3.0)
    float phi_inv3;    // 5: equilibrium pi/rho = (phi-1)/(phi+1) approx 0.236
    float halo_radius; // 6: r where Yang halo begins
    float halo_width;  // 7: transition width

    float pi_max;      // 8: asymptotic pi/rho in outer halo (0.5-0.7)
    float cluster_a;   // 9: Plummer scale radius
    float M_total;     // 10: total cluster mass (pre-computed)
    float _pad;
} pc;

// ── Yang halo profile ─────────────────────────────────────────────

float pi_rho_at(float r) {
    float t = (r - pc.halo_radius) / max(pc.halo_width, 0.01);
    float sig = 1.0 / (1.0 + exp(-t));
    return pc.phi_inv3 + (pc.pi_max - pc.phi_inv3) * sig;
}

// ── Qi coherence ───────────────────────────────────────────────────

float qi_coherence(float pr) {
    float excess = max(pr - pc.phi_inv3, 0.0);
    return 1.0 - exp(-pc.qi_beta * excess);
}

// ── Enclosed mass (Plummer sphere) ─────────────────────────────────

float enclosed_mass(float r) {
    float a2 = pc.cluster_a * pc.cluster_a;
    float r2 = r * r + a2;
    float denom = r2 * sqrt(r2);
    return pc.M_total * (r * r * r) / max(denom, 0.00001);
}

// ── Main ───────────────────────────────────────────────────────────

void main() {
    int N = int(pc.N_f);
    int i = int(gl_GlobalInvocationID.x);
    if (i >= N) return;

    float px = p[i*4];
    float py = p[i*4 + 1];
    float pz = p[i*4 + 2];

    float r2 = px*px + py*py + pz*pz;
    float r  = sqrt(r2 + pc.eps2);

    // ─── Cassi Qi force (O(1) — no j-loop!) ───
    float pr    = pi_rho_at(r);
    float q     = qi_coherence(pr);
    float G_eff = pr * (1.0 + pc.xi * q) * pc.G;
    float M_enc = enclosed_mass(r);
    float f_mag = G_eff * M_enc / max(r2 + pc.eps2, 0.00001);

    float inv_r = inversesqrt(max(r2, 0.00001));
    float ax = -f_mag * px * inv_r;
    float ay = -f_mag * py * inv_r;
    float az = -f_mag * pz * inv_r;

    a[i*4]     = ax;
    a[i*4 + 1] = ay;
    a[i*4 + 2] = az;
    a[i*4 + 3] = 0.0;
}
