#[compute]
#version 450

// Resample the conservative Eulerian material velocity onto the live Cassi
// particles.  In physical-matter mode the particle cloud is the moving mass
// quadrature for gravity and display, not a second independently-counted fluid.
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Pos { vec4 pos[]; };
layout(set = 0, binding = 1, std430) buffer Vel { vec4 vel[]; };
layout(set = 0, binding = 2, std430) readonly buffer Material0 { vec4 material0[]; };
layout(set = 0, binding = 3, std430) coherent buffer Status { uvec4 status[]; };

layout(push_constant, std430) uniform PC {
    float particle_count;
    float nx;
    float ny;
    float nz;
    float extent_x;
    float extent_y;
    float extent_z;
    float center_x;
    float center_y;
    float center_z;
    float density_floor;
    float blend;
    float c_reduced_sim;
    float maximum_v_over_c;
    float particle_offset;
    float pad1;
} pc;

const uint STATUS_TRACER_NONFINITE = 32768u;
const uint STATUS_TRACER_DOMAIN = 65536u;
const uint STATUS_STEP_REJECTED = 131072u;

bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
bool finite_vec3(vec3 value) { return !(any(isnan(value)) || any(isinf(value))); }
uint rounded(float value) { return (!finite_float(value) || value <= 0.0) ? 0u : uint(value + 0.5); }
uvec3 dims() { return uvec3(rounded(pc.nx), rounded(pc.ny), rounded(pc.nz)); }
uint linear_cell(uvec3 c, uvec3 d) { return c.x + d.x * (c.y + d.y * c.z); }

void main() {
    uint particle = rounded(pc.particle_offset) + gl_GlobalInvocationID.x;
    if ((status[0].x & STATUS_STEP_REJECTED) != 0u) return;
    if (particle >= rounded(pc.particle_count)) return;
    vec4 position = pos[particle];
    if (!(position.w > 0.0)) return;
    if (!finite_vec3(position.xyz)) {
        atomicOr(status[0].x, STATUS_TRACER_NONFINITE);
        return;
    }
    uvec3 d = dims();
    vec3 extent = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 normalized = (position.xyz - (vec3(pc.center_x, pc.center_y, pc.center_z) - extent))
        / (2.0 * extent);
    if (any(lessThan(normalized, vec3(0.0))) || any(greaterThan(normalized, vec3(1.0)))) return;
    vec3 coordinate = normalized * vec3(d) - vec3(0.5);
    ivec3 base = ivec3(floor(coordinate));
    vec3 fraction = coordinate - vec3(base);
    vec3 momentum_sum = vec3(0.0);
    float density_sum = 0.0;
    // Trilinear gather of the canonical physical-matter contract stated in
    // cassi_physical_matter_init.glsl (the two-pass valid_weight_sum scatter
    // there; here the same mix(vec3(1.0) - fraction, fraction, side) weights
    // drive a density-weighted velocity gather).  Keep the weight rule in
    // lockstep with that shader's four sites.
    for (int dz = 0; dz <= 1; ++dz)
        for (int dy = 0; dy <= 1; ++dy)
            for (int dx = 0; dx <= 1; ++dx) {
                ivec3 candidate = base + ivec3(dx, dy, dz);
                if (any(lessThan(candidate, ivec3(0))) || any(greaterThanEqual(candidate, ivec3(d)))) continue;
                vec3 side = vec3(dx, dy, dz);
                vec3 weights = mix(vec3(1.0) - fraction, fraction, side);
                float weight = weights.x * weights.y * weights.z;
                vec4 state = material0[linear_cell(uvec3(candidate), d)];
                if (!(state.x > pc.density_floor) || !finite_vec3(state.yzw)) continue;
                momentum_sum += weight * state.yzw;
                density_sum += weight * state.x;
            }
    if (!(density_sum > pc.density_floor)) return;
    vec3 material_velocity = momentum_sum / density_sum;
    if (!finite_vec3(material_velocity)) {
        atomicOr(status[0].x, STATUS_TRACER_NONFINITE);
        return;
    }
    if (length(material_velocity) / max(pc.c_reduced_sim, 1.0e-20) > pc.maximum_v_over_c) {
        atomicOr(status[0].x, STATUS_TRACER_DOMAIN);
        return;
    }
    vel[particle].xyz = mix(vel[particle].xyz, material_velocity, clamp(pc.blend, 0.0, 1.0));
}
