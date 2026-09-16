#[compute]
#version 450

// Standalone module: local finiteness helpers (GLSL has no includes).
bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
bool finite_vec3(vec3 value) { return !(any(isnan(value)) || any(isinf(value))); }
// GL_EXT_shader_atomic_float: the mass ledger slots bh[34]/bh[35] are
// atomicAdd'ed from here (same extension/GPU as cassi_bh_accretion.glsl).
#extension GL_EXT_shader_atomic_float : require

// Site-native BH integration.
// Each active BH performs a bounded linear nearest-site search. Sites are tile
// coordinates in [0, 2*extent); BH positions remain world coordinates. The
// BH header carries the world window center in bh[0].yzw and per-axis
// half-extents in bh[2].yzw. No raster field is read.
//
// Mass growth: the q-driven growth (acc_rate · q_site · site_vol) is the
// same mass manufactured out of a bounded order parameter with nothing
// drained (BH_DYNAMICS_PREREG finding 2) and DEFAULTS OFF (bh_acc_rate =
// 0.0). When the knob is on it is capped at a mass-proportional rate
// (Eddington-like, pc.edd_k) and booked into the CREATED ledger. Expiry
// (or a non-finite retirement) books the erased mass into EXPIRED.
//
// Ledger (bh[34]): x = created, y = expired, z = absorbed (accretion),
// w = reserved; bh[35].z counts non-finite retirements.

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

// coherent: the ledger slots are atomicAdd'ed here and by the other BH
// passes.
layout(set = 1, binding = 0, std430) coherent buffer BHData {
    vec4 bh[36];
};

layout(push_constant, std430) uniform PC {
    float n_sites;
    float dt;
    float acc_rate;    // mass growth per step (0.0 = OFF, the default)
    float max_age;     // steps before expiry (0 = immortal)
    float edd_k;       // growth ceiling: dm <= edd_k · M · dt (Eddington-like)
} pc;

void main() {
    int slot = int(gl_GlobalInvocationID.x);
    if (slot < 0 || slot >= 15) return;

    int base = 4 + slot * 2;
    float mass = bh[base].w;
    if (!(mass > 0.0)) return;
    // Retire a record whose state has gone non-finite instead of persisting
    // it (a NaN mass passes the > 0 guard and would otherwise be re-written).
    vec3 record_pos = bh[base].xyz;
    vec3 record_vel = bh[base + 1].xyz;
    if (!finite_float(mass) || !finite_vec3(record_pos)
            || !finite_vec3(record_vel) || !finite_float(bh[base + 1].w)) {
        if (finite_float(mass)) atomicAdd(bh[34].y, mass);
        atomicAdd(bh[35].z, 1.0);
        bh[base] = vec4(0.0);
        bh[base + 1] = vec4(0.0);
        return;
    }

    vec3 pos = record_pos;
    vec3 vel = record_vel;
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
        float dm = pc.acc_rate * site_q[nearest] * site_vol[nearest];
        if (dm > 0.0) dm = min(dm, max(pc.edd_k, 0.0) * mass * pc.dt);
        mass += dm;
        if (finite_float(dm) && dm != 0.0) {
            if (dm > 0.0) atomicAdd(bh[34].x, dm);
            else atomicAdd(bh[34].y, -dm);
        }
        // A non-finite sample poisons the record: retire it here so a
        // non-finite record is never written back.
        if (!finite_float(mass)) {
            atomicAdd(bh[35].z, 1.0);
            bh[base] = vec4(0.0);
            bh[base + 1] = vec4(0.0);
            return;
        }
    }

    if (pc.max_age > 0.0 && age > pc.max_age) {
        if (finite_float(mass)) atomicAdd(bh[34].y, mass);
        bh[base] = vec4(0.0);
        bh[base + 1] = vec4(0.0);
        return;
    }

    bh[base] = vec4(pos, mass);
    bh[base + 1] = vec4(vel, age);
}
