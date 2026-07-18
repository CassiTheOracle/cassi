#[compute]
#version 450
// Cassi Particle Instancer — writes to MultiMesh buffer (16 floats/instance):
//   3x4 row-major transform + 4 color (as confirmed by Godot issue #76884):
//   float[0-3]   = (basis_row0, origin.x)  → vec4[0]
//   float[4-7]   = (basis_row1, origin.y)  → vec4[1]
//   float[8-11]  = (basis_row2, origin.z)  → vec4[2]
//   float[12-15] = (color.rgba)              → vec4[3]

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) restrict buffer Instances {
    vec4 inst[];
};

layout(push_constant, std430) uniform PC {
    float N_f; float dt; float t; float phi;
    float xi; float eps2; float particle_N;
    float mode; float source_strength; float _pad;
} pc;

void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    if (i >= N) return;

    vec4 p = pos[i];
    int base = i * 4;

    // Row-major 3x4: each vec4 = (basis_row, origin_component)
    // Row 0: basis X-axis (1,0,0) + origin.x
    inst[base]     = vec4(1.0, 0.0, 0.0, p.x);
    // Row 1: basis Y-axis (0,1,0) + origin.y
    inst[base + 1] = vec4(0.0, 1.0, 0.0, p.y);
    // Row 2: basis Z-axis (0,0,1) + origin.z
    inst[base + 2] = vec4(0.0, 0.0, 1.0, p.z);
    // Row 3: color
    float r = length(p.xyz);
    float t_c = 1.0 / (1.0 + 0.1 * r);
    float cr = mix(0.15, 1.0, t_c);
    float cg = mix(0.25, 0.8, t_c);
    float cb = mix(1.0, 0.3, t_c);
    inst[base + 3] = vec4(cr, cg, cb, 0.85);
}
