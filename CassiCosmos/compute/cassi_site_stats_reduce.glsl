#[compute]
// Compact volume-weighted site statistics. Set 0 bindings 0-3.
// op 0 writes one unique pair of vec4 partials per 64-lane workgroup;
// op 1 reduces all pairs into stats[0:2].
#version 450

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer QValues { float q[]; };
layout(set = 0, binding = 1, std430) readonly buffer EpsilonValues { float eps[]; };
layout(set = 0, binding = 2, std430) readonly buffer Volumes { float vol[]; };
layout(set = 0, binding = 3, std430) coherent buffer Statistics { vec4 stats[]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float op;
    float _pad0;
    float _pad1;
} pc;

shared vec4 shared_a[64];
shared vec4 shared_b[64];

void reduce_shared(uint lane) {
    for (uint stride = 32u; stride > 0u; stride >>= 1u) {
        barrier();
        if (lane < stride) {
            vec4 a = shared_a[lane + stride];
            vec4 b = shared_b[lane + stride];
            shared_a[lane].x += a.x;
            shared_a[lane].y += a.y;
            shared_a[lane].z = min(shared_a[lane].z, a.z);
            shared_a[lane].w = max(shared_a[lane].w, a.w);
            shared_b[lane].x += b.x;
            shared_b[lane].y = min(shared_b[lane].y, b.y);
            shared_b[lane].z = max(shared_b[lane].z, b.z);
        }
    }
    barrier();
}

void main() {
    uint lane = gl_LocalInvocationID.x;
    uint count = uint(max(pc.N_f, 0.0));
    uint groups = (count + 63u) / 64u;
    if (pc.op < 0.5) {
        uint i = gl_GlobalInvocationID.x;
        bool valid = i < count;
        float qv = valid ? q[i] : 0.0;
        float ev = valid ? abs(eps[i]) : 0.0;
        float weight = valid ? max(vol[i], 0.0) : 0.0;
        shared_a[lane] = vec4(qv * weight, ev * weight,
            valid ? qv : 3.402823466e+38, valid ? qv : -3.402823466e+38);
        shared_b[lane] = vec4(weight,
            valid ? ev : 3.402823466e+38,
            valid ? ev : -3.402823466e+38, 0.0);
        reduce_shared(lane);
        if (lane == 0u) {
            uint base = 2u * gl_WorkGroupID.x;
            stats[base] = shared_a[0];
            stats[base + 1u] = shared_b[0];
        }
        return;
    }
    if (pc.op < 1.5) {
        float q_sum = 0.0;
        float eps_sum = 0.0;
        float q_min = 3.402823466e+38;
        float q_max = -3.402823466e+38;
        float volume_sum = 0.0;
        float eps_min = 3.402823466e+38;
        float eps_max = -3.402823466e+38;
        for (uint g = lane; g < groups; g += 64u) {
            vec4 a = stats[2u * g];
            vec4 b = stats[2u * g + 1u];
            q_sum += a.x;
            eps_sum += a.y;
            q_min = min(q_min, a.z);
            q_max = max(q_max, a.w);
            volume_sum += b.x;
            eps_min = min(eps_min, b.y);
            eps_max = max(eps_max, b.z);
        }
        shared_a[lane] = vec4(q_sum, eps_sum, q_min, q_max);
        shared_b[lane] = vec4(volume_sum, eps_min, eps_max, 0.0);
        reduce_shared(lane);
        if (lane == 0u) {
            stats[0] = shared_a[0];
            stats[1] = shared_b[0];
        }
    }
}
