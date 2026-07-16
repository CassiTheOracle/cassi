#[compute]
#version 450
// Minimal Cassi O(1) N-body — radial force with constant G_eff.
// Debug step: if this works, we add the Yang halo profile back.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict buffer PositionBuf { float p[]; };
layout(set = 0, binding = 1, std430) restrict buffer AccelBuf   { float a[]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float G;
    float eps2;
    float xi;
    float qi_beta;
    float phi_inv3;
    float halo_radius;
    float halo_width;
    float pi_max;
    float cluster_a;
    float M_total;
    float _pad;
} pc;

void main() {
    int N = int(pc.N_f);
    int i = int(gl_GlobalInvocationID.x);
    if (i >= N) return;

    float px = p[i*4];
    float py = p[i*4 + 1];
    float pz = p[i*4 + 2];

    float r2 = px*px + py*py + pz*pz;
    float r  = sqrt(r2 + pc.eps2);

    // Enclosed mass (Plummer sphere)
    float a2 = pc.cluster_a * pc.cluster_a;
    float r2a = r2 + a2;
    float denom = r2a * sqrt(r2a);
    float M_enc = pc.M_total * (r2 * r) / max(denom, 0.00001);

    // Constant G_eff for now (debug)
    float G_eff = pc.G;

    float f_mag = G_eff * M_enc / max(r2 + pc.eps2, 0.00001);
    float inv_r = 1.0 / max(r, 0.00001);

    a[i*4]     = -f_mag * px * inv_r;
    a[i*4 + 1] = -f_mag * py * inv_r;
    a[i*4 + 2] = -f_mag * pz * inv_r;
    a[i*4 + 3] = 0.0;
}
