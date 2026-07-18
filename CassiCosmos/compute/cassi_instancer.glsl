#[compute]
#version 450
// Cassi Particle Instancer — writes to MultiMesh buffer (16 floats/instance):
//   float[0-2]   = basis column 0 (right)
//   float[3-5]   = basis column 1 (up)
//   float[6-8]   = basis column 2 (forward)
//   float[9-11]  = origin (xyz)
//   float[12-15] = color (rgba)
// Packed into 4 vec4 since std430 aligns to 16 bytes:
//   vec4[0] = (col0.x, col0.y, col0.z, col1.x)
//   vec4[1] = (col1.y, col1.z, col2.x, col2.y)
//   vec4[2] = (col2.z,  origin.x, origin.y, origin.z)
//   vec4[3] = (color.r, color.g, color.b, color.a)

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

    // Identity basis: col0=(1,0,0), col1=(0,1,0), col2=(0,0,1)
    // Packed into 4 vec4:
    inst[base]     = vec4(1.0, 0.0, 0.0, 0.0);  // col0.xyz | col1.x
    inst[base + 1] = vec4(1.0, 0.0, 0.0, 0.0);  // col1.yz | col2.xy
    inst[base + 2] = vec4(1.0, p.x, p.y, p.z);  // col2.z | origin.xyz
    // Color: Cassi gradient by radial distance
    float r = length(p.xyz);
    float t_c = 1.0 / (1.0 + 0.1 * r);
    float cr = mix(0.15, 1.0, t_c);
    float cg = mix(0.25, 0.8, t_c);
    float cb = mix(1.0, 0.3, t_c);
    inst[base + 3] = vec4(cr, cg, cb, 0.85);
}
