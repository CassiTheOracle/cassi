#[compute]
#version 450

// Site-native BH integration.
// Each active BH performs a bounded linear nearest-site search. Sites are tile
// coordinates in [0, 2*extent); BH positions remain world coordinates. The
// BH header carries the world window center in bh[0].yzw and per-axis
// half-extents in bh[2].yzw. No raster field is read.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Sites {
    vec4 sites[];
};
layout(set = 0, binding = 1, std430) readonly buffer SiteQ {
    float site_q[];
};
layout(set = 0, binding = 2, std430) readonly buffer SiteVol {
    float site_vol[];
};

layout(set = 1, binding = 0, std430) buffer BHData {
    vec4 bh[36];
};

layout(push_constant, std430) uniform PC {
    float n_sites;
    float dt;
    float acc_rate;
    float max_age;
} pc;

void main() {
    int slot = int(gl_GlobalInvocationID.x);
    if (slot < 0 || slot >= 15) return;

    int base = 4 + slot * 2;
    float mass = bh[base].w;
    if (mass <= 0.0) return;

    vec3 pos = bh[base].xyz;
    vec3 vel = bh[base + 1].xyz;
    float age = bh[base + 1].w;
    pos += vel * pc.dt;
    age += 1.0;

    vec3 extent = bh[2].yzw;
    vec3 period = 2.0 * extent;
    vec3 window_center = bh[0].yzw;
    vec3 particle_tile = mod((pos - window_center) + extent, period);

    int site_count = int(max(pc.n_sites, 0.0));
    int nearest = -1;
    float nearest_d2 = 1.0e30;
    for (int site = 0; site < site_count; ++site) {
        vec3 delta = sites[site].xyz - particle_tile;
        delta -= period * floor(delta / period + 0.5);
        float d2 = dot(delta, delta);
        if (d2 < nearest_d2) {
            nearest_d2 = d2;
            nearest = site;
        }
    }

    if (nearest >= 0) {
        mass += pc.acc_rate * site_q[nearest] * site_vol[nearest];
    }

    if (pc.max_age > 0.0 && age > pc.max_age) {
        bh[base] = vec4(0.0);
        bh[base + 1] = vec4(0.0);
        return;
    }

    bh[base] = vec4(pos, mass);
    bh[base + 1] = vec4(vel, age);
}
