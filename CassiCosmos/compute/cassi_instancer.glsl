#[compute]
#version 450
// Cassi Particle Instancer — copies positions from gravity output to
// MultiMesh instance buffer format (GPU-side, no CPU readback needed).
//
// Instance format (TRANSFORM_3D + colors, 80 bytes each):
//   vec4 basis_row0  (scale/rotation)
//   vec4 basis_row1
//   vec4 basis_row2
//   vec4 origin      (xyz + w=1)
//   vec4 color       (rgba)

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) restrict buffer Instances {
    vec4 inst[];  // 5 vec4 per particle
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float t;
    float phi;
    float xi;
    float eps2;
    float particle_N;
    float mode;
    float source_strength;
    float _pad;
} pc;

void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    if (i >= N) return;

    vec4 p = pos[i];
    int base = i * 5;

    // Identity basis
    inst[base]     = vec4(1.0, 0.0, 0.0, 0.0);
    inst[base + 1] = vec4(0.0, 1.0, 0.0, 0.0);
    inst[base + 2] = vec4(0.0, 0.0, 1.0, 0.0);

    // Origin = position
    inst[base + 3] = vec4(p.xyz, 1.0);

    // Color: Cassi gradient from radial distance
    float r = length(p.xyz);
    float t_c = 1.0 / (1.0 + 0.1 * r);  // falloff with distance
    float cr = 1.0;   // warm core
    float cg = 0.8;
    float cb = 0.3;
    // Shift toward cold at large r
    cr = mix(cr, 0.15, 1.0 - t_c);
    cg = mix(cg, 0.25, 1.0 - t_c);
    cb = mix(cb, 1.0, 1.0 - t_c);

    inst[base + 4] = vec4(cr, cg, cb, 0.85);
}
