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
// HashStart is an H^3+1 exclusive prefix and HashSites contains site indices
// (not shortlist slots); the host publishes a valid hash together with the
// topology generation before dispatching this pass.
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
const int HASH_RING_MAX = 32;
const uint HASH_BUCKET_SCAN_MAX = 65536u;

// The old tree-river KDK uses these shared counters so a dispatch with a
// partial final workgroup still reaches both barriers.  The min/max values are
// float bit patterns ordered as unsigned integers because q and pi/rho are
// non-negative after their guards/clamps; no float atomics are used.
shared uint shared_counts[4]; // pi_hi, pi_lo, rho_guard, samples
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
    }
}

// Query hash cells in non-wrapping Chebyshev shells. The live site window is
// finite and open: outside particles are deliberately force-free rather than
// sampling the opposite border through a periodic image.
int nearest_site(vec3 particle_world, vec3 extent, out bool found) {
    found = false;
    vec3 span = 2.0 * extent;
    if (!finite_vec3(span) || any(lessThanEqual(span, vec3(0.0)))) {
        return 0;
    }

    vec3 window_center = bh[0].yzw;
    vec3 local = particle_world - window_center;
    if (!finite_vec3(local)
            || any(lessThan(local, -extent))
            || any(greaterThanEqual(local, extent))) {
        return 0;
    }
    vec3 tile = local + extent;
    int h = hash_resolution(extent);
    vec3 cell_size = hash_cell_size(span, h);
    if (!finite_vec3(cell_size) || any(lessThanEqual(cell_size, vec3(0.0)))) {
        return 0;
    }

    ivec3 base = ivec3(floor(tile / cell_size));
    base = clamp(base, ivec3(0), ivec3(h - 1));
    int max_ring = min(h - 1, HASH_RING_MAX);
    int nearest = -1;
    float nearest_d2 = 1.0e30;

    for (int ring = 0; ring <= max_ring; ++ring) {
        for (int oz = -ring; oz <= ring; ++oz) {
            for (int oy = -ring; oy <= ring; ++oy) {
                for (int ox = -ring; ox <= ring; ++ox) {
                    if (max(abs(ox), max(abs(oy), abs(oz))) != ring) {
                        continue;
                    }
                    int raw_cx = base.x + ox;
                    int raw_cy = base.y + oy;
                    int raw_cz = base.z + oz;
                    if (raw_cx < 0 || raw_cx >= h
                            || raw_cy < 0 || raw_cy >= h
                            || raw_cz < 0 || raw_cz >= h) {
                        continue;
                    }
                    uint cell = uint(raw_cx) + uint(h) *
                            (uint(raw_cy) + uint(h) * uint(raw_cz));
                    uint raw_start = hash_start[cell];
                    uint raw_end = hash_start[cell + 1u];
                    if (raw_end < raw_start) {
                        continue;
                    }
                    uint start = raw_start;
                    uint end = min(raw_end, raw_start + HASH_BUCKET_SCAN_MAX);
                    for (uint k = start; k < end; ++k) {
                        uint candidate = hash_sites[k];
                        vec3 site_tile = sites[candidate].xyz;
                        if (!finite_vec3(site_tile)) {
                            continue;
                        }
                        vec3 delta = site_tile - tile;
                        float d2 = dot(delta, delta);
                        if (!(d2 >= 0.0) || !finite_float(d2)) {
                            continue;
                        }
                        if (d2 < nearest_d2
                                || (d2 == nearest_d2
                                    && (nearest < 0 || int(candidate) < nearest))) {
                            nearest_d2 = d2;
                            nearest = int(candidate);
                        }
                    }
                }
            }
        }
        // After shell r, every not-yet-scanned cell is at least r cell
        // widths away along one axis. This conservative bound preserves
        // nearest-site correctness while sparse regions still terminate.
        float min_cell = min(cell_size.x, min(cell_size.y, cell_size.z));
        float unscanned_bound2 = float(ring) * min_cell;
        unscanned_bound2 *= unscanned_bound2;
        if (nearest >= 0 && nearest_d2 < unscanned_bound2) {
            break;
        }
    }
    found = nearest >= 0;
    return nearest < 0 ? 0 : nearest;
}
SiteSample sample_site(vec3 particle_world, vec3 extent) {
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

    bool found;
    int nearest = nearest_site(particle_world, extent, found);
    if (!found) {
        return result;
    }

    uint index = uint(nearest);
    float ey = psi_y[index];
    float ei = psi_i[index];
    float rho = ey + ei;
    float eps = ey - pc.phi * ei;
    float rho2 = rho * rho;
    float q_formula = rho2 / max(rho2 + PHI_INV2 + eps * eps, 1.0e-30);
    float q_authoritative = site_q[index];
    // SiteQ is the published site state.  Retain the exact river-law formula
    // as a malformed-buffer fallback so an uninitialized q cannot poison a
    // force or telemetry; valid SiteQ is already produced by that formula.
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

vec3 bh_point_gravity(vec3 particle_world, float eps2_value) {
    float G_N = bh[1].w;
    float softened = max(eps2_value, 0.0);
    vec3 result = vec3(0.0);
    for (int b = 0; b < 15; ++b) {
        int base = 4 + 2 * b;
        float mass = bh[base].w;
        if (!(mass > 0.0)) {
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
    ss = sample_site(particle_world, extent);

    vec3 result = vec3(0.0);
    if (bh[3].x > 0.5) {
        result += bh_point_gravity(particle_world, pc.eps2);
    }

    if (pc.gravity_mode > 0.5 && pc.gravity_mode < 1.5) {
        result += heuristic_field_acc(ss);
    } else if (pc.gravity_mode > 1.5 && pc.gravity_mode < 2.5) {
        result += plummer_field_acc(particle_world);
    } else {
        // Modes 0/3/4/5 are the site-native tree family.  Mode 4 adds
        // RealSim dissipation in the caller; mode 5 is the explicit tree-river
        // selector used by meshless integration.
        result += site_tree_acc(ss, particle_world, extent, particle_index, stats);
    }
    return result;
}

void add_stats_to_shared(TeleStats stats) {
    atomicAdd(shared_counts[0], stats.clamp_hi);
    atomicAdd(shared_counts[1], stats.clamp_lo);
    atomicAdd(shared_counts[2], stats.rho_guard);
    atomicAdd(shared_counts[3], stats.samples);
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
        vec3 gravity_acceleration = gravity_at(pos[gid].xyz, int(gid), ss, stats);
        if (pc.gravity_mode > 3.5 && pc.gravity_mode < 4.5) {
            gravity_acceleration += realsim_dissipation(ss, vel[gid].xyz,
                    gravity_acceleration);
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

        // Cached-acc KDK: acc is the previous full-kick force at the current
        // position, so this is exactly the old first half-kick.
        vec3 half_velocity = old_velocity + acc[gid].xyz * half_dt;
        vec3 new_position = old_position + half_velocity * pc.dt;

        SiteSample ss;
        vec3 gravity_acceleration = gravity_at(new_position, int(gid), ss, stats);
        if (pc.gravity_mode > 3.5 && pc.gravity_mode < 4.5) {
            gravity_acceleration += realsim_dissipation(ss, half_velocity,
                    gravity_acceleration);
        }
        vec3 new_velocity = half_velocity + gravity_acceleration * half_dt;

        if (pc.gravity_mode > 4.5) {
            apply_tree_safety(new_position, new_velocity);
        }
        if (!finite_vec3(new_position)) {
            new_position = old_position;
        }
        if (!finite_vec3(new_velocity)) {
            new_velocity = vec3(0.0);
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
