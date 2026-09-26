#[compute]
#version 450
// canonical layout: scripts/contracts/layout.gd

// Read-only orientation visualizer. Inputs are authoritative; only the
// renderer-owned MultiMesh instance records are written.
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Positions {
    vec4 pos[];
};
layout(set = 0, binding = 1, std430) readonly buffer Orientations {
    vec4 orientation[];
};
struct InstanceRecord {
    vec4 row0;
    vec4 row1;
    vec4 row2;
    vec4 color;
};
layout(set = 0, binding = 2, std430) writeonly buffer Instances {
    InstanceRecord instance[];
};

layout(push_constant, std430) uniform Params {
    float count;
    float axis_length;
    float axis_width;
    float spare;
} pc;

bool finite4(vec4 value) {
    return !any(isnan(value)) && !any(isinf(value));
}

void clear_record(uint id) {
    instance[id].row0 = vec4(0.0);
    instance[id].row1 = vec4(0.0);
    instance[id].row2 = vec4(0.0);
    instance[id].color = vec4(0.0);
}

void main() {
    uint id = gl_GlobalInvocationID.x;
    uint count = uint(max(pc.count, 0.0) + 0.5);
    if (id >= count) return;

    vec4 particle = pos[id];
    vec4 q = orientation[id];
    float qnorm = length(q);
    if (particle.w <= 0.0 || !finite4(particle) || !finite4(q) || qnorm <= 1e-12) {
        clear_record(id);
        return;
    }
    q /= qnorm;

    float x = q.x;
    float y = q.y;
    float z = q.z;
    float w = q.w;
    mat3 rotation = mat3(
        vec3(1.0 - 2.0 * (y * y + z * z),
             2.0 * (x * y + z * w),
             2.0 * (x * z - y * w)),
        vec3(2.0 * (x * y - z * w),
             1.0 - 2.0 * (x * x + z * z),
             2.0 * (y * z + x * w)),
        vec3(2.0 * (x * z + y * w),
             2.0 * (y * z - x * w),
             1.0 - 2.0 * (x * x + y * y))
    );
    mat3 basis = rotation * mat3(
        vec3(pc.axis_length, 0.0, 0.0),
        vec3(0.0, pc.axis_width, 0.0),
        vec3(0.0, 0.0, pc.axis_width)
    );

    // Godot MultiMesh TRANSFORM_3D records are three row vectors with
    // translation in w, followed by the per-instance color.
    instance[id].row0 = vec4(basis[0][0], basis[1][0], basis[2][0], particle.x);
    instance[id].row1 = vec4(basis[0][1], basis[1][1], basis[2][1], particle.y);
    instance[id].row2 = vec4(basis[0][2], basis[1][2], basis[2][2], particle.z);
    instance[id].color = vec4(0.14, 0.86, 1.0, 1.0);
}
