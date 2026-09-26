#[compute]
#version 450

// Unsplit first-order finite-volume transport for one cell/group/ordinate per
// invocation.  Radiation angular energy density is advected at the declared
// reduced light speed with vacuum inflow and open escape on all six faces.
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer RadiationIn { float radiation_in[]; };
layout(set = 0, binding = 1, std430) buffer RadiationOut { float radiation_out[]; };
layout(set = 0, binding = 2, std430) readonly buffer Ordinates { vec4 ordinate_data[]; };
layout(set = 0, binding = 3, std430) coherent buffer Status { uvec4 status[]; };

layout(push_constant, std430) uniform PC {
    float nx;
    float ny;
    float nz;
    float group_count;
    float angle_count;
    float extent_x;
    float extent_y;
    float extent_z;
    float dt_sim;
    float c_reduced_sim;
    float cfl_limit;
    float validation_only;
} pc;

const uint STATUS_TRANSPORT_CFL = 4096u;
const uint STATUS_TRANSPORT_NONFINITE = 8192u;
const uint STATUS_TRANSPORT_NEGATIVE = 16384u;
const uint STATUS_STEP_REJECTED = 131072u;

bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
uint rounded(float value) { return (!finite_float(value) || value <= 0.0) ? 0u : uint(value + 0.5); }
uvec3 dims() { return uvec3(rounded(pc.nx), rounded(pc.ny), rounded(pc.nz)); }
uint groups() { return rounded(pc.group_count); }
uint angles() { return rounded(pc.angle_count); }
uint cell_count() { uvec3 d = dims(); return d.x * d.y * d.z; }
uint linear_cell(ivec3 c, uvec3 d) {
    return uint(c.x) + d.x * (uint(c.y) + d.y * uint(c.z));
}
bool in_domain(ivec3 c, uvec3 d) {
    return all(greaterThanEqual(c, ivec3(0))) && all(lessThan(c, ivec3(d)));
}
ivec3 coordinate(uint cell, uvec3 d) {
    uint plane = d.x * d.y;
    uint z = cell / plane;
    uint remainder = cell - z * plane;
    return ivec3(int(remainder % d.x), int(remainder / d.x), int(z));
}
uint radiation_index(uint cell, uint group, uint angle) {
    return (cell * groups() + group) * angles() + angle;
}
float sample_radiation(ivec3 c, uvec3 d, uint group, uint angle) {
    if (!in_domain(c, d)) return 0.0;
    return max(radiation_in[radiation_index(linear_cell(c, d), group, angle)], 0.0);
}

void main() {
    uint index = gl_GlobalInvocationID.x;
    if ((status[0].x & STATUS_STEP_REJECTED) != 0u) return;
    uint per_cell = groups() * angles();
    uint total = cell_count() * per_cell;
    if (index >= total || per_cell == 0u) return;
    uint cell = index / per_cell;
    uint local = index - cell * per_cell;
    uint group = local / angles();
    uint angle = local - group * angles();
    uvec3 d = dims();
    ivec3 c = coordinate(cell, d);
    vec3 direction = ordinate_data[angle].xyz;
    vec3 spacing = 2.0 * vec3(pc.extent_x, pc.extent_y, pc.extent_z) / vec3(d);
    float courant = pc.c_reduced_sim * pc.dt_sim
        * (abs(direction.x) / spacing.x + abs(direction.y) / spacing.y + abs(direction.z) / spacing.z);
    if (!finite_float(courant) || courant > pc.cfl_limit + 1.0e-6) {
        atomicOr(status[0].x, STATUS_TRANSPORT_CFL | STATUS_STEP_REJECTED);
        atomicAdd(status[2].x, 1u);
        return;
    }
    float center = max(radiation_in[index], 0.0);
    float divergence = 0.0;
    ivec3 x_upwind = c - ivec3(direction.x >= 0.0 ? 1 : -1, 0, 0);
    ivec3 y_upwind = c - ivec3(0, direction.y >= 0.0 ? 1 : -1, 0);
    ivec3 z_upwind = c - ivec3(0, 0, direction.z >= 0.0 ? 1 : -1);
    divergence += abs(direction.x) * (center - sample_radiation(x_upwind, d, group, angle)) / spacing.x;
    divergence += abs(direction.y) * (center - sample_radiation(y_upwind, d, group, angle)) / spacing.y;
    divergence += abs(direction.z) * (center - sample_radiation(z_upwind, d, group, angle)) / spacing.z;
    float next_value = center - pc.c_reduced_sim * pc.dt_sim * divergence;
    if (!finite_float(next_value)) {
        atomicOr(status[0].x, STATUS_TRANSPORT_NONFINITE | STATUS_STEP_REJECTED);
        atomicAdd(status[2].y, 1u);
        return;
    }
    if (next_value < -max(1.0e-12, center * 1.0e-5)) {
        atomicOr(status[0].x, STATUS_TRANSPORT_NEGATIVE | STATUS_STEP_REJECTED);
        atomicAdd(status[2].z, 1u);
        return;
    }
    if (pc.validation_only > 0.5) return;
    radiation_out[index] = max(next_value, 0.0);
}

