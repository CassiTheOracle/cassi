#[compute]
#version 450

// Angularly integrates the live discrete-ordinate radiation field and packs
// every camera-visible material coefficient once per physical-state update.
// The ray marcher then consumes one vec4 per cell/group instead of rereading
// three large engine buffers at every pixel, ray step, and stencil cell.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Radiation {
    float radiation[];
};
layout(set = 0, binding = 1, std430) readonly buffer Ordinates {
    vec4 ordinate[];
};
layout(set = 0, binding = 2, std430) readonly buffer VisibleGroups {
    vec4 visible_group[];
};
layout(set = 0, binding = 3, std430) writeonly buffer VisibleSource {
    // xyz = opacity, emission, exact angular mean; w = electron population.
    vec4 visible_source[];
};
layout(set = 0, binding = 4, std430) readonly buffer Opacity {
    float opacity_group[];
};
layout(set = 0, binding = 5, std430) readonly buffer Emission {
    float emission_group[];
};
layout(set = 0, binding = 6, std430) readonly buffer Population1 {
    vec4 population1[];
};

layout(push_constant, std430) uniform ObserverSourcePC {
    uint cell_count;
    uint group_count;
    uint angle_count;
    uint visible_count;
} pc;

const float INV_FOUR_PI = 0.07957747154594767;

bool finite1(float value) { return !(isnan(value) || isinf(value)); }

void main() {
    uint index = gl_GlobalInvocationID.x;
    uint count = pc.cell_count * pc.visible_count;
    if (index >= count || pc.group_count == 0u || pc.angle_count == 0u) return;
    uint cell = index / pc.visible_count;
    uint visible = index - cell * pc.visible_count;
    uint group = min(uint(max(visible_group[visible].w, 0.0) + 0.5),
        pc.group_count - 1u);
    uint base = (cell * pc.group_count + group) * pc.angle_count;
    float angular_integral = 0.0;
    for (uint angle = 0u; angle < pc.angle_count; ++angle)
        angular_integral += max(ordinate[angle].w, 0.0)
            * max(radiation[base + angle], 0.0);
    float mean = angular_integral * INV_FOUR_PI;
    uint source_index = cell * pc.group_count + group;
    vec4 packed = vec4(
        max(opacity_group[source_index], 0.0),
        max(emission_group[source_index], 0.0),
        finite1(mean) ? mean : 0.0,
        max(population1[cell].z, 0.0));
    visible_source[index] = vec4(
        finite1(packed.x) ? packed.x : 0.0,
        finite1(packed.y) ? packed.y : 0.0,
        finite1(packed.z) ? packed.z : 0.0,
        finite1(packed.w) ? packed.w : 0.0);
}
