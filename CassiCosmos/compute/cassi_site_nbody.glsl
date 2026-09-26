#[compute]
#version 450

// Site-native N-body force/integrator.
//
// Sites are tile coordinates in [0, 2*extent); particles and BH records are
// world coordinates. The current window center is bh[0].yzw. Site-local field
// state is sampled only inside the live window and never wraps periodically.
// The exact per-particle tree gradient remains valid outside that window, so
// its chord factor approaches the vacuum attractor π/ρ = φ^-3 there instead
// of switching gravity off on six rectangular faces.
//
// HashStart is an H^3+1 exclusive prefix and HashSites contains original site
// IDs (not shortlist slots); the host publishes a valid hash together with
// the topology generation before dispatching this pass.
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

// ── Site-native state (set 0) ───────────────────────────────────────────
layout(set = 0, binding = 0, std430) readonly buffer Sites {
    vec4 sites[];
};
layout(set = 0, binding = 1, std430) readonly buffer PsiY {
    float psi_y[];
};
layout(set = 0, binding = 2, std430) readonly buffer PsiI {
    float psi_i[];
};
layout(set = 0, binding = 3, std430) readonly buffer SiteQ {
    float site_q[];
};
layout(set = 0, binding = 4, std430) readonly buffer HashStart {
    uint hash_start[];
};
layout(set = 0, binding = 5, std430) readonly buffer HashSites {
    uint hash_sites[];
};
layout(set = 0, binding = 6, std430) readonly buffer HashCfg {
    vec4 hash_cfg[];
};
layout(set = 0, binding = 7, std430) readonly buffer GradY {
    vec4 grad_y[];
};
layout(set = 0, binding = 8, std430) readonly buffer GradI {
    vec4 grad_i[];
};
layout(set = 0, binding = 9, std430) readonly buffer SiteMass {
    float site_mass[];
};
// Telemetry layout is the tree-river layout:
//   [0] pi/rho upper clamps, [1] lower clamps, [2] rho guards,
//   [3] q_min bits, [4] q_max bits, [5] pi_min bits, [6] pi_max bits,
//   [7] chord sample count.  The host clears this buffer before a step.
layout(set = 0, binding = 10, std430) coherent buffer Telemetry {
    uint telemetry[];
};

// ── Particle state (set 1) ──────────────────────────────────────────────
layout(set = 1, binding = 0, std430) restrict buffer Pos {
    vec4 pos[];
};
layout(set = 1, binding = 1, std430) restrict buffer Vel {
    vec4 vel[];
};
layout(set = 1, binding = 2, std430) restrict buffer Acc {
    vec4 acc[];
};
layout(set = 1, binding = 3, std430) restrict readonly buffer TreeGrad {
    vec4 tree_grad[];
};
layout(set = 1, binding = 4, std430) coherent buffer SiteQueryCache {
    uint query_cache[];
};


// ── BH/Plummer state (set 2) ─────────────────────────────────────────────
layout(set = 2, binding = 0, std430) readonly buffer BHData {
    vec4 bh[36];
};
layout(set = 2, binding = 1, std430) readonly buffer ClusterBuf {
    vec4 cluster[64];
};

// Standard N-body PC ABI: 15 floats / 60 bytes.
layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float time;
    float phi;
    float xi;
    float eps2;
    float particle_N;
    float mode;
    float source_strength;
    float num_clusters;
    float gravity_mode;
    float pass_mode;
    float realsim_drag;
    float realsim_viscosity;
    float realsim_friction;
} pc;

const float PHI_INV2 = 0.3819660112501051;
const float PHI_INV3 = 0.2360679774997898;
const float PI_RHO_HI = 0.72;
const float RHO_GUARD = 1.0e-6;
const int DEFAULT_HASH_H = 32;
const uint UINT_MAX_VALUE = 0xffffffffu;

// The old tree-river KDK uses these shared counters so a dispatch with a
// partial final workgroup still reaches both barriers.  The min/max values are
// float bit patterns ordered as unsigned integers because q and pi/rho are
// non-negative after their guards/clamps; no float atomics are used.
shared uint shared_counts[16]; // 0-3 field stats; 4-14 nf_state..nf_ratio; 15 nf_bh_pos
shared uint shared_min[2];    // q_min, pi_min
shared uint shared_max[2];    // q_max, pi_max

struct TeleStats {
    uint clamp_hi;
    uint clamp_lo;
    uint rho_guard;
    uint q_min;
    uint q_max;
    uint pi_min;
    uint pi_max;
    uint samples;
    uint nf_state;
    uint nf_halfvel;
    uint nf_force;
    uint nf_output;
    uint nf_sample_field;
    uint nf_sample_mass;
    uint nf_raw;
    uint nf_bh_term;
    uint nf_tree_term;
    uint nf_hdr;
    uint nf_ratio;
    uint nf_bh_pos;
};

struct SiteSample {
    bool found;
    uint index;
    float ey;
    float ei;
    float q;
    float rho;
    float eps;
    float mass;
    vec3 grad;
    bool grad_defined;
};

bool finite_float(float value) {
    return !(isnan(value) || isinf(value));
}

bool finite_vec3(vec3 value) {
    return !(any(isnan(value)) || any(isinf(value)));
}


int hash_resolution(vec3 extent) {
    vec4 cfg = hash_cfg[0];
    float cell_side = cfg.w;
    int h = DEFAULT_HASH_H;
    if (finite_float(cell_side) && cell_side > 0.0 && finite_float(extent.x)
            && extent.x > 0.0) {
        float raw_h = (2.0 * extent.x) / cell_side;
        if (finite_float(raw_h) && raw_h >= 1.0) {
            h = int(floor(raw_h + 0.5));
        }
    }
    // The fixed bound is intentional: a malformed hash must not turn one
    // particle into an unbounded cell walk.  The published path uses H=32.
    return clamp(h, 1, 256);
}

vec3 hash_cell_size(vec3 span, int h) {
    vec3 result = span / float(h);
    float published_x = hash_cfg[0].w;
    if (finite_float(published_x) && published_x > 0.0) {
        float tolerance = max(result.x * 0.001, 1.0e-6);
        if (abs(published_x - result.x) <= tolerance) {
            result.x = published_x;
        }
    }
    return result;
}

void tele_begin(uint local_index) {
    if (local_index == 0u) {
        shared_counts[0] = 0u;
        shared_counts[1] = 0u;
        shared_counts[2] = 0u;
        shared_counts[3] = 0u;
        shared_counts[4] = 0u;
        shared_counts[5] = 0u;
        shared_counts[6] = 0u;
        shared_counts[7] = 0u;
        shared_counts[8] = 0u;
        shared_counts[9] = 0u;
        shared_counts[10] = 0u;
        shared_counts[11] = 0u;
        shared_counts[12] = 0u;
        shared_counts[13] = 0u;
        shared_counts[14] = 0u;
        shared_counts[15] = 0u;
        shared_min[0] = 0x7f800000u;
        shared_min[1] = 0x7f800000u;
        shared_max[0] = 0u;
        shared_max[1] = 0u;
    }
    barrier();
}

TeleStats tele_new() {
    TeleStats result;
    result.clamp_hi = 0u;
    result.clamp_lo = 0u;
    result.rho_guard = 0u;
    result.q_min = 0x7f800000u;
    result.q_max = 0u;
    result.pi_min = 0x7f800000u;
    result.pi_max = 0u;
    result.samples = 0u;
    result.nf_state = 0u;
    result.nf_halfvel = 0u;
    result.nf_force = 0u;
    result.nf_output = 0u;
    result.nf_sample_field = 0u;
    result.nf_sample_mass = 0u;
    result.nf_raw = 0u;
    result.nf_bh_term = 0u;
    result.nf_tree_term = 0u;
    result.nf_hdr = 0u;
    result.nf_ratio = 0u;
    result.nf_bh_pos = 0u;
    return result;
}

void tele_emit(uint local_index) {
    barrier();
    if (local_index == 0u) {
        atomicAdd(telemetry[0], shared_counts[0]);
        atomicAdd(telemetry[1], shared_counts[1]);
        atomicAdd(telemetry[2], shared_counts[2]);
        atomicMin(telemetry[3], shared_min[0]);
        atomicMax(telemetry[4], shared_max[0]);
        atomicMin(telemetry[5], shared_min[1]);
        atomicMax(telemetry[6], shared_max[1]);
        atomicAdd(telemetry[7], shared_counts[3]);
        atomicAdd(telemetry[12], shared_counts[4]);
        atomicAdd(telemetry[13], shared_counts[5]);
        atomicAdd(telemetry[14], shared_counts[6]);
        atomicAdd(telemetry[15], shared_counts[7]);
        atomicAdd(telemetry[16], shared_counts[8]);
        atomicAdd(telemetry[17], shared_counts[9]);
        atomicAdd(telemetry[18], shared_counts[10]);
        atomicAdd(telemetry[19], shared_counts[11]);
        atomicAdd(telemetry[20], shared_counts[12]);
        atomicAdd(telemetry[21], shared_counts[13]);
        atomicAdd(telemetry[22], shared_counts[14]);
        atomicAdd(telemetry[23], shared_counts[15]);
    }
}

float point_aabb_distance2(vec3 p, vec3 lo, vec3 hi) {
    vec3 d = max(max(lo - p, p - hi), vec3(0.0));
    return dot(d, d);
}

void scan_hash_cell(uint cell, uint site_count, vec3 tile,
        inout int nearest, inout float nearest_d2) {
    uint raw_start = hash_start[cell];
    uint raw_end = hash_start[cell + 1u];
    if (raw_end < raw_start) return;
    uint list_capacity = uint(hash_sites.length());
    uint start = min(raw_start, list_capacity);
    uint end = min(raw_end, list_capacity);
    for (uint k = start; k < end; ++k) {
        uint candidate = hash_sites[k];
        if (candidate >= site_count) continue;
        vec3 site_tile = sites[candidate].xyz;
        if (!finite_vec3(site_tile)) continue;
        vec3 delta = site_tile - tile;
        float d2 = dot(delta, delta);
        if (!(d2 >= 0.0) || !finite_float(d2)) continue;
        if (d2 < nearest_d2 || (d2 == nearest_d2
                && (nearest < 0 || int(candidate) < nearest))) {
            nearest_d2 = d2;
            nearest = int(candidate);
        }
    }
}

// Hash query in the finite open window. Every shell scans a complete
// Chebyshev ring. Point-to-AABB lower bounds over the six unscanned slabs make
// termination exact for sparse cells, anisotropic extents, and face queries.
int nearest_site(vec3 particle_world, vec3 extent, out bool found) {
    found = false;
    vec3 span = 2.0 * extent;
    if (!finite_vec3(span) || any(lessThanEqual(span, vec3(0.0)))) return 0;
    vec3 local = particle_world - bh[0].yzw;
    if (!finite_vec3(local) || any(lessThan(local, -extent))
            || any(greaterThanEqual(local, extent))) return 0;
    vec3 tile = local + extent;
    int h = hash_resolution(extent);
    vec3 cell_size = hash_cell_size(span, h);
    if (!finite_vec3(cell_size) || any(lessThanEqual(cell_size, vec3(0.0)))) return 0;
    ivec3 base = clamp(ivec3(floor(tile / cell_size)), ivec3(0), ivec3(h - 1));
    int nearest = -1;
    float nearest_d2 = 1.0e30;
    uint site_count = uint(sites.length());
    for (int ring = 0; ring < h; ++ring) {
        ivec3 lo_cell = max(base - ivec3(ring), ivec3(0));
        ivec3 hi_cell = min(base + ivec3(ring), ivec3(h - 1));
        if (ring == 0) {
            uint cell = uint(base.x) + uint(h) *
                    (uint(base.y) + uint(h) * uint(base.z));
            scan_hash_cell(cell, site_count, tile, nearest, nearest_d2);
        } else {
            ivec3 prev_lo = max(base - ivec3(ring - 1), ivec3(0));
            ivec3 prev_hi = min(base + ivec3(ring - 1), ivec3(h - 1));
            bool zlo_new = lo_cell.z < prev_lo.z;
            bool zhi_new = hi_cell.z > prev_hi.z;
            bool ylo_new = lo_cell.y < prev_lo.y;
            bool yhi_new = hi_cell.y > prev_hi.y;
            bool xlo_new = lo_cell.x < prev_lo.x;
            bool xhi_new = hi_cell.x > prev_hi.x;
            if (zlo_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int y = lo_cell.y; y <= hi_cell.y; ++y)
                        scan_hash_cell(uint(x) + uint(h) * (uint(y) + uint(h) * uint(lo_cell.z)),
                                site_count, tile, nearest, nearest_d2);
            if (zhi_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int y = lo_cell.y; y <= hi_cell.y; ++y)
                        scan_hash_cell(uint(x) + uint(h) * (uint(y) + uint(h) * uint(hi_cell.z)),
                                site_count, tile, nearest, nearest_d2);
            int zlo_inner = lo_cell.z + (zlo_new ? 1 : 0);
            int zhi_inner = hi_cell.z - (zhi_new ? 1 : 0);
            if (ylo_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(x) + uint(h) * (uint(lo_cell.y) + uint(h) * uint(z)),
                                site_count, tile, nearest, nearest_d2);
            if (yhi_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(x) + uint(h) * (uint(hi_cell.y) + uint(h) * uint(z)),
                                site_count, tile, nearest, nearest_d2);
            int ylo_inner = lo_cell.y + (ylo_new ? 1 : 0);
            int yhi_inner = hi_cell.y - (yhi_new ? 1 : 0);
            if (xlo_new)
                for (int y = ylo_inner; y <= yhi_inner; ++y)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(lo_cell.x) + uint(h) * (uint(y) + uint(h) * uint(z)),
                                site_count, tile, nearest, nearest_d2);
            if (xhi_new)
                for (int y = ylo_inner; y <= yhi_inner; ++y)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(hi_cell.x) + uint(h) * (uint(y) + uint(h) * uint(z)),
                                site_count, tile, nearest, nearest_d2);
        }
        float bound2 = 1.0e30;
        if (lo_cell.x > 0)
            bound2 = min(bound2, point_aabb_distance2(tile, vec3(0.0),
                vec3(float(lo_cell.x) * cell_size.x, span.y, span.z)));
        if (hi_cell.x < h - 1)
            bound2 = min(bound2, point_aabb_distance2(tile,
                vec3(float(hi_cell.x + 1) * cell_size.x, 0.0, 0.0), span));
        if (lo_cell.y > 0)
            bound2 = min(bound2, point_aabb_distance2(tile, vec3(0.0),
                vec3(span.x, float(lo_cell.y) * cell_size.y, span.z)));
        if (hi_cell.y < h - 1)
            bound2 = min(bound2, point_aabb_distance2(tile,
                vec3(0.0, float(hi_cell.y + 1) * cell_size.y, 0.0), span));
        if (lo_cell.z > 0)
            bound2 = min(bound2, point_aabb_distance2(tile, vec3(0.0),
                vec3(span.x, span.y, float(lo_cell.z) * cell_size.z)));
        if (hi_cell.z < h - 1)
            bound2 = min(bound2, point_aabb_distance2(tile,
                vec3(0.0, 0.0, float(hi_cell.z + 1) * cell_size.z), span));
        if (nearest_d2 < bound2) break;
    }
    found = nearest >= 0;
    return nearest < 0 ? 0 : nearest;
}

bool cache_read(uint particle_id, vec3 particle_position, uint site_count,
        out uint site_id) {
    uint epoch = query_cache[0];
    if (epoch == 0u) return false;
    uint base = 1u + particle_id * 5u;
    if (query_cache[base] != floatBitsToUint(particle_position.x)
            || query_cache[base + 1u] != floatBitsToUint(particle_position.y)
            || query_cache[base + 2u] != floatBitsToUint(particle_position.z)
            || query_cache[base + 4u] != epoch) return false;
    site_id = query_cache[base + 3u];
    return site_id == UINT_MAX_VALUE || site_id < site_count;
}
void cache_write(uint particle_id, vec3 particle_position, uint site_id) {
    uint base = 1u + particle_id * 5u;
    query_cache[base] = floatBitsToUint(particle_position.x);
    query_cache[base + 1u] = floatBitsToUint(particle_position.y);
    query_cache[base + 2u] = floatBitsToUint(particle_position.z);
    query_cache[base + 3u] = site_id;
    query_cache[base + 4u] = query_cache[0];
}
SiteSample sample_site(vec3 particle_world, vec3 extent, uint particle_id) {
    SiteSample result;
    result.found = false;
    result.index = 0u;
    result.ey = 0.0;
    result.ei = 0.0;
    result.q = 0.0;
    result.rho = 0.0;
    result.eps = 0.0;
    result.mass = 0.0;
    result.grad = vec3(0.0);
    result.grad_defined = false;

    uint site_count = uint(sites.length());
    uint cached_id = UINT_MAX_VALUE;
    bool cached = cache_read(particle_id, particle_world, site_count, cached_id);
    bool found;
    int nearest;
    if (cached) {
        found = cached_id != UINT_MAX_VALUE;
        nearest = found ? int(cached_id) : 0;
    } else {
        nearest = nearest_site(particle_world, extent, found);
        cache_write(particle_id, particle_world,
                found ? uint(nearest) : UINT_MAX_VALUE);
    }
    if (!found) return result;

    uint index = uint(nearest);
    float ey = psi_y[index];
    float ei = psi_i[index];
    float rho = ey + ei;
    float eps = ey - pc.phi * ei;
    float rho2 = rho * rho;
    float q_formula = rho2 / max(rho2 + PHI_INV2 + eps * eps, 1.0e-30);
    float q_authoritative = site_q[index];
    float q = (finite_float(q_authoritative) && q_authoritative >= 0.0
            && q_authoritative <= 1.0) ? q_authoritative : q_formula;
    vec4 gy = grad_y[index];
    vec4 gi = grad_i[index];
    bool gradients_defined = gy.w > 0.5 && gi.w > 0.5
            && finite_vec3(gy.xyz) && finite_vec3(gi.xyz);
    result.found = true;
    result.index = index;
    result.ey = ey;
    result.ei = ei;
    result.q = clamp(q, 0.0, 1.0);
    result.rho = rho;
    result.eps = eps;
    result.mass = max(site_mass[index], 0.0);
    result.grad = gradients_defined ? gy.xyz + gi.xyz : vec3(0.0);
    result.grad_defined = gradients_defined;
    return result;
}

// Exact tree-river chord clamp/telemetry semantics.  q is sampled from the
// authoritative site state; eps is the same phi-defect used by chord_g_from.
float site_pi_over_rho(SiteSample ss, inout TeleStats stats) {
    stats.samples++;
    uint q_bits = floatBitsToUint(ss.q);
    stats.q_min = min(stats.q_min, q_bits);
    stats.q_max = max(stats.q_max, q_bits);

    float pi_over_rho;
    if (ss.rho < RHO_GUARD) {
        pi_over_rho = 0.0;
        stats.rho_guard++;
    } else {
        pi_over_rho = (ss.ey - ss.ei) / ss.rho;
        if (pi_over_rho > PI_RHO_HI) {
            stats.clamp_hi++;
            pi_over_rho = PI_RHO_HI;
        } else if (pi_over_rho < 0.0) {
            stats.clamp_lo++;
            pi_over_rho = 0.0;
        }
    }
    uint pi_bits = floatBitsToUint(pi_over_rho);
    stats.pi_min = min(stats.pi_min, pi_bits);
    stats.pi_max = max(stats.pi_max, pi_bits);
    return pi_over_rho;
}

vec3 bh_point_gravity(vec3 particle_world, float eps2_value,
        inout TeleStats stats) {
    float G_N = bh[1].w;
    float softened = max(eps2_value, 0.0);
    vec3 result = vec3(0.0);
    for (int b = 0; b < 15; ++b) {
        int base = 4 + 2 * b;
        float mass = bh[base].w;
        if (!(mass > 0.0)) {
            continue;
        }
        // One malformed record must never poison every particle: skip and
        // count a non-finite record (position OR mass; +inf passes the sign
        // test above) instead of propagating it into every particle's force.
        if (!finite_float(mass) || !finite_vec3(bh[base].xyz)) {
            stats.nf_bh_pos += 1u;
            continue;
        }
        vec3 delta = bh[base].xyz - particle_world;
        float r2 = dot(delta, delta) + softened;
        float inv_r3 = 1.0 / max(r2 * sqrt(max(r2, 1.0e-30)), 1.0e-30);
        result += G_N * mass * inv_r3 * delta;
    }
    return result;
}

vec3 plummer_field_acc(vec3 particle_world) {
    float G_N = bh[1].w;
    float a_soft = max(bh[2].x, 1.0e-4);
    float eps2_value = max(pc.eps2, 0.0);
    int record_count = clamp(int(max(pc.num_clusters, 0.0) + 0.5), 0, 64);
    vec3 result = vec3(0.0);
    for (int c = 0; c < record_count; ++c) {
        float mass = cluster[c].w;
        if (!(mass > 0.0)) {
            continue;
        }
        vec3 delta = cluster[c].xyz - particle_world;
        float r2 = dot(delta, delta) + eps2_value;
        float denom = r2 + a_soft * a_soft;
        float inv = 1.0 / max(denom * sqrt(max(denom, 1.0e-30)), 1.0e-30);
        result += G_N * mass * inv * delta;
    }
    return result;
}

// Site-gradient heuristic fallback (gravity_mode == 1).  This preserves the
// legacy heuristic's bounded pi/rho dial while replacing its raster q-gradient
// with the authoritative site gradient (GradY + GradI).
vec3 heuristic_field_acc(SiteSample ss) {
    if (!ss.found || !ss.grad_defined) {
        return vec3(0.0);
    }
    float q_s = ss.q + 0.01 * ss.mass;
    float pi_over_rho = ((pc.phi - 1.0) / max(pc.phi + 1.0, 1.0e-30))
            + 0.7 * q_s;
    pi_over_rho = clamp(pi_over_rho, 0.0, PI_RHO_HI);
    return bh[1].w * pi_over_rho * ss.grad;
}

vec3 site_tree_acc(SiteSample ss, vec3 particle_world, vec3 extent,
        int particle_index, inout TeleStats stats) {
    float pi_over_rho = PHI_INV3;
    if (ss.found) {
        float site_ratio = site_pi_over_rho(ss, stats);
        vec3 rel = (particle_world - bh[0].yzw) / max(extent, vec3(1.0e-6));
        // Blend the local chord state into its asymptotic attractor through
        // an ellipsoidal shell. The tree force stays open-boundary while the
        // finite site tile cannot expose an axis-aligned force discontinuity.
        float vacuum_mix = smoothstep(0.85, 1.0, length(rel));
        pi_over_rho = mix(site_ratio, PHI_INV3, vacuum_mix);
    }
    float G_N = bh[1].w;
    float tree_scale = bh[3].w;
    if (!finite_float(pi_over_rho)) {
        stats.nf_ratio += 1u;
    }
    return G_N * tree_scale * pi_over_rho * tree_grad[particle_index].xyz;
}

vec3 realsim_dissipation(SiteSample ss, vec3 velocity,
        vec3 gravity_acceleration) {
    vec3 result = vec3(0.0);
    float rho_local = max(ss.rho, 0.0);
    result += -pc.realsim_drag * (rho_local / PHI_INV3) * velocity;
    // GradY + GradI is the site field-velocity proxy only after the AREPO
    // gradient solve publishes both .w definition markers.  Do not read a
    // raster velocity is intentionally not read here.
    if (ss.grad_defined) {
        result += -pc.realsim_viscosity * (velocity - ss.grad);
    }
    float velocity_length = length(velocity);
    float dt_abs = max(abs(pc.dt), 1.0e-30);
    if (velocity_length > 1.0e-12) {
        float friction_mag = min(pc.realsim_friction * length(gravity_acceleration),
                velocity_length / dt_abs);
        result += -friction_mag * velocity / velocity_length;
    }
    return result;
}

vec3 gravity_at(vec3 particle_world, int particle_index,
        out SiteSample ss, inout TeleStats stats) {
    vec3 extent = max(abs(bh[2].yzw), vec3(1.0e-6));
    // Every particle uses the same finite, open site query, including the
    // analytic Plummer fallback. Outside particles receive the explicit
    // no-site sample rather than wrapping across the box, so RealSim and tree
    // consume identical site state.
    ss = sample_site(particle_world, extent, uint(particle_index));
    // Count non-finite site state at the source: the field pair and its
    // derived rho/q, then the mass/eps pair, so the poisoned buffer is named.
    if (!finite_float(ss.ey) || !finite_float(ss.ei) || !finite_float(ss.q)
            || !finite_float(ss.rho)) {
        stats.nf_sample_field += 1u;
    }
    if (!finite_float(ss.eps) || !finite_float(ss.mass)) {
        stats.nf_sample_mass += 1u;
    }

    vec3 result = vec3(0.0);
    if (!finite_float(bh[1].w) || !finite_float(bh[3].w)
            || !finite_vec3(bh[2].yzw) || !finite_vec3(bh[0].yzw)) {
        stats.nf_hdr += 1u;
    }
    if (bh[3].x > 0.5) {
        vec3 bh_term = bh_point_gravity(particle_world, pc.eps2, stats);
        if (!finite_vec3(bh_term)) {
            // Counted at the source and contained here: one malformed term
            // must not propagate into acc and freeze every particle forever.
            stats.nf_bh_term += 1u;
            bh_term = vec3(0.0);
        }
        result += bh_term;
    }

    if (pc.gravity_mode > 0.5 && pc.gravity_mode < 1.5) {
        result += heuristic_field_acc(ss);
    } else if (pc.gravity_mode > 1.5 && pc.gravity_mode < 2.5) {
        result += plummer_field_acc(particle_world);
    } else {
        // Modes 0/3/4/5 are the site-native tree family.  Mode 4 adds
        // RealSim dissipation in the caller; mode 5 is the explicit tree-river
        // selector used by meshless integration.
        vec3 tree_term = site_tree_acc(ss, particle_world, extent, particle_index, stats);
        if (!finite_vec3(tree_term)) {
            // Same contract as the BH term: counted and contained.
            stats.nf_tree_term += 1u;
            tree_term = vec3(0.0);
        }
        result += tree_term;
    }
    // Raw pre-dissipation force: separates the site-force evaluation from the
    // caller's RealSim dissipation term.
    if (!finite_vec3(result)) {
        stats.nf_raw += 1u;
    }
    return result;
}

void add_stats_to_shared(TeleStats stats) {
    atomicAdd(shared_counts[0], stats.clamp_hi);
    atomicAdd(shared_counts[1], stats.clamp_lo);
    atomicAdd(shared_counts[2], stats.rho_guard);
    atomicAdd(shared_counts[3], stats.samples);
    atomicAdd(shared_counts[4], stats.nf_state);
    atomicAdd(shared_counts[5], stats.nf_halfvel);
    atomicAdd(shared_counts[6], stats.nf_force);
    atomicAdd(shared_counts[7], stats.nf_output);
    atomicAdd(shared_counts[8], stats.nf_sample_field);
    atomicAdd(shared_counts[9], stats.nf_sample_mass);
    atomicAdd(shared_counts[10], stats.nf_raw);
    atomicAdd(shared_counts[11], stats.nf_bh_term);
    atomicAdd(shared_counts[12], stats.nf_tree_term);
    atomicAdd(shared_counts[13], stats.nf_hdr);
    atomicAdd(shared_counts[14], stats.nf_ratio);
    atomicAdd(shared_counts[15], stats.nf_bh_pos);
    atomicMin(shared_min[0], stats.q_min);
    atomicMax(shared_max[0], stats.q_max);
    atomicMin(shared_min[1], stats.pi_min);
    atomicMax(shared_max[1], stats.pi_max);
}

void warmup_main() {
    uint gid = gl_GlobalInvocationID.x;
    uint local_index = gl_LocalInvocationIndex;
    tele_begin(local_index);
    if (gid < uint(max(pc.particle_N, 0.0) + 0.5)) {
        TeleStats stats = tele_new();
        SiteSample ss;
        if (!finite_vec3(pos[gid].xyz) || !finite_vec3(vel[gid].xyz)) {
            stats.nf_state += 1u;
        }
        vec3 gravity_acceleration = gravity_at(pos[gid].xyz, int(gid), ss, stats);
        if (pc.gravity_mode > 3.5 && pc.gravity_mode < 4.5) {
            gravity_acceleration += realsim_dissipation(ss, vel[gid].xyz,
                    gravity_acceleration);
        }
        if (!finite_vec3(gravity_acceleration)) {
            stats.nf_force += 1u;
        }
        acc[gid] = vec4(gravity_acceleration, 0.0);
        add_stats_to_shared(stats);
    }
    tele_emit(local_index);
}

void apply_tree_safety(inout vec3 particle_position, inout vec3 particle_velocity) {
    // Limit a bad tree close encounter without imposing a position boundary.
    // Site-native coordinates are open-world: every finite escaped position
    // must continue unaltered rather than accumulating on a reabsorption sphere.
    float emax = max(max(bh[2].y, bh[2].z), bh[2].w);
    if (!(emax > 0.0) || !finite_float(emax)) {
        return;
    }
    float velocity_cap = 120.0 * emax;
    float velocity_length = length(particle_velocity);
    if (velocity_length > velocity_cap) {
        particle_velocity *= velocity_cap / velocity_length;
    }
}

void kdk_main() {
    uint gid = gl_GlobalInvocationID.x;
    uint local_index = gl_LocalInvocationIndex;
    tele_begin(local_index);
    if (gid < uint(max(pc.particle_N, 0.0) + 0.5)) {
        TeleStats stats = tele_new();
        vec3 old_position = pos[gid].xyz;
        vec3 old_velocity = vel[gid].xyz;
        float half_dt = 0.5 * pc.dt;
        // Count every non-finite source class so a silent fallback can never
        // hide: state = inputs already poisoned, halfvel = first half-kick,
        // force = gravity+RealSim kick, output = the fallback clamp fired.
        if (!finite_vec3(old_position) || !finite_vec3(old_velocity)
                || !finite_vec3(acc[gid].xyz)) {
            stats.nf_state += 1u;
        }

        // Cached-acc KDK: acc is the previous full-kick force at the current
        // position, so this is exactly the old first half-kick.
        vec3 half_velocity = old_velocity + acc[gid].xyz * half_dt;
        if (!finite_vec3(half_velocity)) {
            stats.nf_halfvel += 1u;
        }
        vec3 new_position = old_position + half_velocity * pc.dt;

        SiteSample ss;
        vec3 gravity_acceleration = gravity_at(new_position, int(gid), ss, stats);
        if (pc.gravity_mode > 3.5 && pc.gravity_mode < 4.5) {
            gravity_acceleration += realsim_dissipation(ss, half_velocity,
                    gravity_acceleration);
        }
        if (!finite_vec3(gravity_acceleration)) {
            stats.nf_force += 1u;
        }
        vec3 new_velocity = half_velocity + gravity_acceleration * half_dt;

        if (pc.gravity_mode > 4.5) {
            apply_tree_safety(new_position, new_velocity);
        }
        if (!finite_vec3(new_position)) {
            new_position = old_position;
            stats.nf_output += 1u;
        }
        if (!finite_vec3(new_velocity)) {
            new_velocity = vec3(0.0);
            stats.nf_output += 1u;
        }

        pos[gid] = vec4(new_position, pos[gid].w);
        vel[gid] = vec4(new_velocity, 0.0);
        // Cache the post-drift full-kick acceleration for the next step.
        acc[gid] = vec4(gravity_acceleration, 0.0);
        add_stats_to_shared(stats);
    }
    tele_emit(local_index);
}

void main() {
    // Compatibility gradient dispatches are intentionally no-ops.  The site
    // path has no gradient-build pass; GradY/GradI are published site state.
    if (pc.pass_mode > 0.5 && pc.pass_mode < 1.75) {
        return;
    }
    if (pc.pass_mode > 1.75) {
        warmup_main();
        return;
    }
    kdk_main();
}
