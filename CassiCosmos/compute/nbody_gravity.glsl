#[compute]
#version 450
// Cassi O(1) N-body — combined force + KDK integration on GPU.
// Eliminates per-step buffer readback. Positions read once per frame
// for rendering only.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict buffer PositionBuf { float p[]; };
layout(set = 0, binding = 1, std430) restrict buffer VelocityBuf { float v[]; };
layout(set = 0, binding = 2, std430) restrict buffer AccelBuf   { float a[]; };

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
    float dt;
    int   n_substeps;
    float _pad2;
} pc;

float enclosed_mass(float r, float r2) {
    float a2 = pc.cluster_a * pc.cluster_a;
    float r2a = r2 + a2;
    float denom = r2a * sqrt(r2a);
    return pc.M_total * (r2 * r) / max(denom, 0.00001);
}

void main() {
    int N = int(pc.N_f);
    int i = int(gl_GlobalInvocationID.x);
    if (i >= N) return;

    float px = p[i*4];
    float py = p[i*4 + 1];
    float pz = p[i*4 + 2];
    float vx = v[i*4];
    float vy = v[i*4 + 1];
    float vz = v[i*4 + 2];

    // Sub-step KDK loop on GPU
    float hdt = pc.dt * 0.5;

    for (int s = 0; s < pc.n_substeps; s++) {
        float r2 = px*px + py*py + pz*pz;
        float r  = sqrt(r2 + pc.eps2);

        float M_enc = enclosed_mass(r, r2);
        float G_eff = pc.G;
        float f_mag = G_eff * M_enc / max(r2 + pc.eps2, 0.00001);
        float inv_r = 1.0 / max(r, 0.00001);

        float ax = -f_mag * px * inv_r;
        float ay = -f_mag * py * inv_r;
        float az = -f_mag * pz * inv_r;

        // KDK
        vx += ax * hdt;
        vy += ay * hdt;
        vz += az * hdt;
        px += vx * pc.dt;
        py += vy * pc.dt;
        pz += vz * pc.dt;
        vx += ax * hdt;
        vy += ay * hdt;
        vz += az * hdt;
    }

    p[i*4]     = px;
    p[i*4 + 1] = py;
    p[i*4 + 2] = pz;
    p[i*4 + 3] = 1.0;
    v[i*4]     = vx;
    v[i*4 + 1] = vy;
    v[i*4 + 2] = vz;
    v[i*4 + 3] = 0.0;
    a[i*4]     = 0.0;  // unused
    a[i*4 + 1] = 0.0;
    a[i*4 + 2] = 0.0;
    a[i*4 + 3] = 0.0;
}
