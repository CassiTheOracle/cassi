#[compute]
#version 450
// Cassi Occupancy Sampler — GPU-side particle-box occupancy classification.
//
// Replaces the per-0.5 s full position-buffer readback (N x 16 B, 64 MB at
// 4M particles) + CPU classification loop: one strided pass over the
// particle buffer writes 5 atomic counters (inner / face-edge / corner /
// out-of-box / sampled) and the host reads 20 bytes instead of the whole
// buffer. Classification mirrors _sample_occupancy's CPU logic exactly:
//   out:    |x_i| > extent_i for any axis
//   inner:  max_i |x_i|/lim_i < 1          (lim_i = 0.85 x extent_i)
//   corner: all three |x_i| >= lim_i
//   face/edge: everything else inside the box
// Sampled particle index s -> pos[s * stride] (the CPU subsample set).

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) buffer OccCounters { uint c[5]; };

layout(push_constant, std430) uniform PC {
    float np;         // particle count
    float n_sample;   // samples to classify (<= 40000)
    float stride;     // particle-index stride = np / n_sample (CPU subsample set)
    float lim_x;      // 0.85 x extent_x
    float lim_y;      // 0.85 x extent_y
    float lim_z;      // 0.85 x extent_z
    float ext_x;      // box half-extent per axis
    float ext_y;
    float ext_z;
    float _pad0;      // 10 floats = 40 B PC (matches the host upload)
} pc;

void main() {
    int s = int(gl_GlobalInvocationID.x);
    if (s >= int(pc.n_sample)) return;
    int idx = s * int(pc.stride);
    atomicAdd(c[4], 1u);  // every classified sample (before any early-out)
    vec3 a = abs(pos[idx].xyz);
    if (a.x > pc.ext_x || a.y > pc.ext_y || a.z > pc.ext_z) {
        atomicAdd(c[3], 1u);
        return;
    }
    float cnorm = max(a.x / pc.lim_x, max(a.y / pc.lim_y, a.z / pc.lim_z));
    if (cnorm < 1.0) {
        atomicAdd(c[0], 1u);
    } else {
        int n_hi = 0;
        if (a.x >= pc.lim_x) n_hi += 1;
        if (a.y >= pc.lim_y) n_hi += 1;
        if (a.z >= pc.lim_z) n_hi += 1;
        if (n_hi >= 3) atomicAdd(c[2], 1u);
        else atomicAdd(c[1], 1u);
    }
}
