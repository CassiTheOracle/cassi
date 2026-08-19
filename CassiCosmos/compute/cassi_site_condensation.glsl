#[compute]
#version 450

// Site-native condensation scanner.
// Sites are tile coordinates in [0, 2*extent); the BH header carries the
// complete world window center in bh[0].yzw and per-axis half-extents in
// bh[2].yzw. This path has no raster-field dependency.

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

layout(set = 1, binding = 0, std430) coherent buffer BHData {
    uvec4 bh_bits[36];
};

layout(push_constant, std430) uniform PC {
    float n_sites;
    float qi_threshold;
    float window_x; // Reserved for the host contract; bh[0].yzw is authoritative.
    float window_y; // Reserved for the host contract; bh[0].yzw is authoritative.
} pc;

void main() {
    uint site = gl_GlobalInvocationID.x;
    uint site_count = uint(max(pc.n_sites, 0.0));
    uint mode = uint(max(pc.window_x, 0.0) + 0.5);

    // bh[base+1].w is a transient candidate key during the selection pass;
    // the finalize pass clears the transient record back to the normal
    // velocity/age tuple. Existing live BH records in bh[base] persist when
    // no qualifying site is present.
    if (mode == 0u) {
        if (site < 15u) {
            uint base = 4u + site * 2u;
            bh_bits[base + 1u].w = 0u;
        }
        return;
    }

    if (mode == 1u) {
        if (site >= site_count) return;
        float q = site_q[site];
        if (!(q > pc.qi_threshold) || isnan(q) || isinf(q)) return;
        float mass = q * site_vol[site];
        if (!(mass > 0.0) || isnan(mass) || isinf(mass)) return;
        uint base = 4u + (site % 15u) * 2u;
        atomicMax(bh_bits[base + 1u].w, floatBitsToUint(mass));
        return;
    }

    // One invocation owns each modulo slot and scans the site list. This
    // second dispatch is deliberately separate from atomic selection: every
    // invocation sees the completed candidate key before publishing a paired
    // position/mass record, with a lowest-site-index tie break.
    if (mode != 2u || site >= 15u) return;
    uint base = 4u + site * 2u;
    uint selected_bits = bh_bits[base + 1u].w;
    if (selected_bits == 0u) return;
    float best_mass = 0.0;
    uint best_site = site;
    for (uint candidate = site; candidate < site_count; candidate += 15u) {
        float q = site_q[candidate];
        float mass = q * site_vol[candidate];
        if (!(q > pc.qi_threshold) || !(mass > 0.0)
                || isnan(q) || isinf(q) || isnan(mass) || isinf(mass)) {
            continue;
        }
        if (mass > best_mass || (mass == best_mass && candidate < best_site)) {
            best_mass = mass;
            best_site = candidate;
        }
    }
    if (floatBitsToUint(best_mass) != selected_bits) return;

    vec3 extent = vec3(
        uintBitsToFloat(bh_bits[2].y),
        uintBitsToFloat(bh_bits[2].z),
        uintBitsToFloat(bh_bits[2].w));
    vec3 window_center = vec3(
        uintBitsToFloat(bh_bits[0].y),
        uintBitsToFloat(bh_bits[0].z),
        uintBitsToFloat(bh_bits[0].w));
    vec3 world_pos = sites[best_site].xyz - extent + window_center;
    uint old_bits = bh_bits[base].w;
    if (selected_bits >= old_bits) {
        bh_bits[base] = uvec4(
            floatBitsToUint(world_pos.x),
            floatBitsToUint(world_pos.y),
            floatBitsToUint(world_pos.z),
            selected_bits);
        bh_bits[base + 1u] = uvec4(0u);
    }
}
