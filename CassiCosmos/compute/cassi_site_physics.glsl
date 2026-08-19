#[compute]
#version 450

// Cassi site-native field / gradient / telemetry kernel.
//
// Coordinate contract:
//   * sites[].xyz are tile coordinates in [0, 2*extent) for each axis.
//   * particle coordinates remain world coordinates; a particle-side consumer
//     maps p to the tile with mod((p - window_center) + extent, 2*extent).
//   * this kernel has no grid, cell index, or stencil lookup. Every operator
//     below is a directed CSR walk over site IDs.
//   * topology_status = uint[4] = {generation, required_neighbors,
//     overflow, site_count}. The host dispatches modes 1/2 only after the
//     generation is nonzero, overflow is zero, and site_count matches PC.
//
// Site state is authoritative: sites, the first n_sites entries of
// psi_y/psi_i/pi_y/pi_i, volume, and site_mass are the state owned by the
// site path. The second n_sites entries are a packed next-state half used by
// mode 1/3 to make the CSR update race-free without extra descriptors.
// GradY/GradI, LapY/LapI, SiteQ, SiteEps, and Telemetry are derived outputs.
//
// Modes:
//   0  reset telemetry, derived outputs, and packed next-state half.
//   1  graph-laplacian symplectic (leapfrog-shaped) field step, writing the
//      packed next-state half only. It never writes the state read by neighbors.
//   2  recompute graph operators and q/epsilon without advancing field state.
//   3  commit the packed next-state half into the authoritative state.
//      Mode 2 follows it in the host chain so derived outputs describe the
//      committed state.
//
// Telemetry layout:
//   [0..7] are the n-body gravity counters/ranges;
//   [8] field momentum high-clamp hits, [9] field rho-guard hits,
//   [10] field operator samples, [11] field momentum low-clamp hits.
//   The field path never overwrites the n-body π/ρ range slots.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// Set 0 is deliberately site-native. There are no grid/N³ resources here.
layout(set = 0, binding = 0, std430) readonly buffer Sites {
    vec4 sites[];
};
layout(set = 0, binding = 1, std430) buffer PsiY {
    float psi_y[];
};
layout(set = 0, binding = 2, std430) buffer PsiI {
    float psi_i[];
};
layout(set = 0, binding = 3, std430) buffer PiY {
    float pi_y[];
};
layout(set = 0, binding = 4, std430) buffer PiI {
    float pi_i[];
};
layout(set = 0, binding = 5, std430) readonly buffer Vol {
    float vol[];
};
layout(set = 0, binding = 6, std430) readonly buffer SiteMass {
    float site_mass[];
};
layout(set = 0, binding = 7, std430) readonly buffer CSROffsets {
    uint offsets[];
};
layout(set = 0, binding = 8, std430) readonly buffer CSRNeighbors {
    uint neighbors[];
};
layout(set = 0, binding = 9, std430) buffer GradY {
    vec4 grad_y[];
};
layout(set = 0, binding = 10, std430) buffer GradI {
    vec4 grad_i[];
};
layout(set = 0, binding = 11, std430) buffer LapY {
    float lap_y[];
};
layout(set = 0, binding = 12, std430) buffer LapI {
    float lap_i[];
};
layout(set = 0, binding = 13, std430) buffer SiteQ {
    float site_q[];
};
layout(set = 0, binding = 14, std430) buffer SiteEps {
    float site_eps[];
};
layout(set = 0, binding = 15, std430) coherent buffer Telemetry {
    uint telemetry[];
};
layout(set = 0, binding = 16, std430) readonly buffer TopologyStatus {
    uint topology_status[];
};

// Exactly 16 scalar floats (64 bytes), in this fixed order.
layout(push_constant, std430) uniform PC {
    float mode;
    float n_sites;
    float dt;
    float phi;
    float c2;
    float omega2;
    float source_strength;
    float rho_floor;
    float pi_cap;
    float winding;
    float time;
    float extent_x;
    float extent_y;
    float extent_z;
    float mass_scale;
    float generation;
} pc;

const float EPS = 1e-12;
const float EPS_DISTANCE2 = 1e-16;
const float SQRT_ONE_HALF = 0.7071067811865475244;
const float GRADIENT_REG = 1e-6;

uint rounded_uint(float value) {
    return uint(max(value, 0.0) + 0.5);
}

uint site_count() {
    return rounded_uint(pc.n_sites);
}

uint operation_mode() {
    return rounded_uint(pc.mode);
}

vec3 box_extent() {
    return max(abs(vec3(pc.extent_x, pc.extent_y, pc.extent_z)), vec3(EPS));
}

vec3 minimum_image(vec3 delta) {
    // Sites live in a periodic tile. This is the only coordinate transform
    // used by the field operator; no integer grid coordinate is constructed.
    vec3 period = 2.0 * box_extent();
    return delta - period * floor(delta / period + vec3(0.5));
}

float volume_guard() {
    return max(abs(pc.rho_floor), EPS);
}

float site_volume(uint s) {
    return max(abs(vol[s]), volume_guard());
}

float phi_inverse_square() {
    float phi2 = max(pc.phi * pc.phi, EPS);
    return 1.0 / phi2;
}

float coherence_q(float y, float i) {
    float rho = y + i;
    float eps = y - pc.phi * i;
    float rho2 = rho * rho;
    float denominator = rho2 + phi_inverse_square() + eps * eps;
    return rho2 / denominator;
}

float radial_source(vec3 tile_position) {
    // The tile center is the radial-source center. A moving world window is
    // applied by the particle/render consumers; site positions stay tile-local.
    vec3 d = minimum_image(tile_position - box_extent());
    vec3 normalized = d / box_extent();
    return pc.source_strength * exp(-4.0 * dot(normalized, normalized));
}

vec3 solve_gradient(
    float m00, float m01, float m02,
    float m10, float m11, float m12,
    float m20, float m21, float m22,
    vec3 rhs
) {
    float determinant = m00 * (m11 * m22 - m12 * m21)
                      - m01 * (m10 * m22 - m12 * m20)
                      + m02 * (m10 * m21 - m11 * m20);
    if (abs(determinant) <= 1e-12) {
        return vec3(0.0);
    }
    float inverse_det = 1.0 / determinant;
    return inverse_det * vec3(
        (m11 * m22 - m12 * m21) * rhs.x
            + (m02 * m21 - m01 * m22) * rhs.y
            + (m01 * m12 - m02 * m11) * rhs.z,
        (m12 * m20 - m10 * m22) * rhs.x
            + (m00 * m22 - m02 * m20) * rhs.y
            + (m02 * m10 - m00 * m12) * rhs.z,
        (m10 * m21 - m11 * m20) * rhs.x
            + (m01 * m20 - m00 * m21) * rhs.y
            + (m00 * m11 - m01 * m10) * rhs.z
    );
}

// Gather both the graph Laplacian flux and the least-squares gradients from
// one identical directed CSR row. The finite-volume-like edge weight is
// face_area / distance, where face_area = volume^(2/3). Dividing the flux by
// volume in the kick recovers the existing meshless leapfrog shape.
void gather_site_operator(
    uint s,
    uint ns,
    out float out_lap_y,
    out float out_lap_i,
    out vec3 out_grad_y,
    out vec3 out_grad_i,
    out uint out_edges
) {
    vec3 self_position = sites[s].xyz;
    float self_y = psi_y[s];
    float self_i = psi_i[s];
    float face_area = pow(site_volume(s), 2.0 / 3.0);

    float ly = 0.0;
    float li = 0.0;
    float m00 = GRADIENT_REG;
    float m01 = 0.0;
    float m02 = 0.0;
    float m10 = 0.0;
    float m11 = GRADIENT_REG;
    float m12 = 0.0;
    float m20 = 0.0;
    float m21 = 0.0;
    float m22 = GRADIENT_REG;
    vec3 rhs_y = vec3(0.0);
    vec3 rhs_i = vec3(0.0);
    uint accepted_edges = 0u;

    uint begin = offsets[s];
    uint end = offsets[s + 1u];
    if (end < begin) {
        out_lap_y = 0.0;
        out_lap_i = 0.0;
        out_grad_y = vec3(0.0);
        out_grad_i = vec3(0.0);
        out_edges = 0u;
        return;
    }

    for (uint cursor = begin; cursor < end; ++cursor) {
        uint neighbor = neighbors[cursor];
        if (neighbor >= ns || neighbor == s) {
            continue;
        }

        vec3 displacement = minimum_image(sites[neighbor].xyz - self_position);
        float distance2 = dot(displacement, displacement);
        if (!(distance2 > EPS_DISTANCE2)) {
            continue;
        }
        float distance = sqrt(distance2);
        float edge_weight = face_area / max(distance, EPS);
        float delta_y = psi_y[neighbor] - self_y;
        float delta_i = psi_i[neighbor] - self_i;
        ly += edge_weight * delta_y;
        li += edge_weight * delta_i;

        // AREPO-style least-squares reconstruction. The same periodic
        // minimum-image displacement as the graph Laplacian supplies n-hat.
        vec3 direction = displacement / distance;
        float slope_y = delta_y / distance;
        float slope_i = delta_i / distance;
        m00 += direction.x * direction.x;
        m01 += direction.x * direction.y;
        m02 += direction.x * direction.z;
        m10 += direction.y * direction.x;
        m11 += direction.y * direction.y;
        m12 += direction.y * direction.z;
        m20 += direction.z * direction.x;
        m21 += direction.z * direction.y;
        m22 += direction.z * direction.z;
        rhs_y += slope_y * direction;
        rhs_i += slope_i * direction;
        accepted_edges++;
    }

    out_lap_y = ly;
    out_lap_i = li;
    out_grad_y = solve_gradient(m00, m01, m02, m10, m11, m12,
                                m20, m21, m22, rhs_y);
    out_grad_i = solve_gradient(m00, m01, m02, m10, m11, m12,
                                m20, m21, m22, rhs_i);
    out_edges = accepted_edges;
}

void reset_site_outputs(uint s) {
    grad_y[s] = vec4(0.0);
    grad_i[s] = vec4(0.0);
    lap_y[s] = 0.0;
    lap_i[s] = 0.0;
    site_q[s] = 0.0;
    site_eps[s] = 0.0;
    uint next = site_count() + s;
    psi_y[next] = 0.0;
    psi_i[next] = 0.0;
    pi_y[next] = 0.0;
    pi_i[next] = 0.0;
}

void reset_telemetry() {
    telemetry[0] = 0u;
    telemetry[1] = 0u;
    telemetry[2] = 0u;
    telemetry[3] = 0x7F800000u;
    telemetry[4] = 0u;
    telemetry[5] = 0x7F800000u;
    telemetry[6] = 0u;
    telemetry[7] = 0u;
    telemetry[8] = 0u; // field π high clamp
    telemetry[9] = 0u; // field ρ guard
    telemetry[10] = 0u; // field operator samples
    telemetry[11] = 0u; // field π low clamp

}
bool topology_is_ready(uint ns) {
    uint generation = rounded_uint(pc.generation);
    return generation > 0u
        && topology_status[0] == generation
        && topology_status[2] == 0u
        && topology_status[3] == ns;
}

void publish_derived(
    uint s,
    float y,
    float i,
    float operator_lap_y,
    float operator_lap_i,
    vec3 operator_grad_y,
    vec3 operator_grad_i,
    uint edge_count
) {
    lap_y[s] = operator_lap_y;
    lap_i[s] = operator_lap_i;
    grad_y[s] = vec4(operator_grad_y, edge_count > 0u ? 1.0 : 0.0);
    grad_i[s] = vec4(operator_grad_i, edge_count > 0u ? 1.0 : 0.0);
    site_eps[s] = y - pc.phi * i;
    site_q[s] = coherence_q(y, i);
}

void main() {
    uint gid = gl_GlobalInvocationID.x;
    uint ns = site_count();
    uint op = operation_mode();

    // Mode 0 is the only workgroup-synchronised operation. It is uniform in
    // pc.mode, and no invocation can return before reaching the barrier.
    if (op == 0u) {
        if (gid < ns) {
            reset_site_outputs(gid);
        }
        if (gl_LocalInvocationID.x == 0u) {
            reset_telemetry();
        }
        memoryBarrierBuffer();
        barrier();
        return;
    }

    // Mode 3 is a host-ordered commit. Each invocation copies one independent
    // next-state record, so no device-wide barrier is required in the pass.
    if (op == 3u) {
        if (gid < ns) {
            uint next = ns + gid;
            psi_y[gid] = psi_y[next];
            psi_i[gid] = psi_i[next];
            pi_y[gid] = pi_y[next];
            pi_i[gid] = pi_i[next];
        }
        return;
    }

    if (gid >= ns || (op != 1u && op != 2u)) {
        return;
    }
    if (!topology_is_ready(ns)) {
        return;
    }

    float operator_lap_y;
    float operator_lap_i;
    vec3 operator_grad_y;
    vec3 operator_grad_i;
    uint edge_count;
    gather_site_operator(gid, ns, operator_lap_y, operator_lap_i,
                         operator_grad_y, operator_grad_i, edge_count);
    atomicAdd(telemetry[10], 1u);

    float y_old = psi_y[gid];
    float i_old = psi_i[gid];
    float rho_old = y_old + i_old;
    if (abs(rho_old) < volume_guard()) {
        atomicAdd(telemetry[9], 1u);
    }

    if (op == 2u) {
        // Diagnostic/recompute mode never changes authoritative field state.
        publish_derived(gid, y_old, i_old, operator_lap_y, operator_lap_i,
                        operator_grad_y, operator_grad_i, edge_count);
        return;
    }

    // Mode 1: symplectic-Euler/leapfrog-shaped kick and drift, matching the
    // existing meshless equation:
    //   piY += dt*(c2*lapY/vol - omega2*dev + sourceY)
    //   piI += dt*(c2*lapI/vol + omega2*dev + sourceI)
    //   psi += dt*pi. The phi-defect conversion is explicitly +/- omega2*dev.
    // The computed record is written to scratch; mode 3 commits it after the
    // dispatch boundary so every CSR row reads the same old field state.
    float dev = y_old - pc.phi * i_old;
    float local_volume = site_volume(gid);
    float inverse_volume = 1.0 / local_volume;
    float rho_density = site_mass[gid] / local_volume;
    float mass_source = pc.mass_scale * rho_density;
    float radial = radial_source(sites[gid].xyz);
    float source_y = mass_source + radial;
    float source_i = SQRT_ONE_HALF * (mass_source + radial);
    float q_old = coherence_q(y_old, i_old);
    float openness = 1.0 - q_old;
    float winding_y = pc.winding * openness * operator_lap_y * inverse_volume;
    float winding_i = pc.winding * openness * operator_lap_i * inverse_volume;

    float acceleration_y = pc.c2 * operator_lap_y * inverse_volume
                         - pc.omega2 * dev + source_y + winding_y;
    float acceleration_i = pc.c2 * operator_lap_i * inverse_volume
                         + pc.omega2 * dev + source_i + winding_i;

    float pi_y_new = pi_y[gid] + pc.dt * acceleration_y;
    float pi_i_new = pi_i[gid] + pc.dt * acceleration_i;
    if (pc.pi_cap > 0.0) {
        if (pi_y_new > pc.pi_cap) {
            pi_y_new = pc.pi_cap;
            atomicAdd(telemetry[8], 1u);
        } else if (pi_y_new < -pc.pi_cap) {
            pi_y_new = -pc.pi_cap;
            atomicAdd(telemetry[11], 1u);
        }
        if (pi_i_new > pc.pi_cap) {
            pi_i_new = pc.pi_cap;
            atomicAdd(telemetry[8], 1u);
        } else if (pi_i_new < -pc.pi_cap) {
            pi_i_new = -pc.pi_cap;
            atomicAdd(telemetry[11], 1u);
        }
    }

    float y_new = y_old + pc.dt * pi_y_new;
    float i_new = i_old + pc.dt * pi_i_new;
    uint next = ns + gid;
    pi_y[next] = pi_y_new;
    pi_i[next] = pi_i_new;
    psi_y[next] = y_new;
    psi_i[next] = i_new;
}
