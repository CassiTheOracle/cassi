#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 3 floats (12 B); set 0 bindings 0-3
// Hierarchical tree momentum correction. A producer workgroup writes one
// unique pair of vec4 partials; a single complete second reduction folds
// those pairs into partials[0:2], then the subtraction pass applies the
// accepted mass-weighted acceleration and velocity means.
//
// Buffers (set 0): 0 = acceleration vec4/particle, 1 = positions
// (vec4/particle, w = mass), 2 = vec4 partials (two records per producer
// workgroup), 3 = velocities vec4/particle. PC: N_f, op, pad. op 0 writes
// producer partials, op 1 subtracts the means, and op 3 performs the
// complete second reduction. Producer lanes outside N participate in all
// workgroup barriers with neutral values. Nonpositive masses contribute zero.
#version 450

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) coherent buffer Accel { vec4 acc[]; };
layout(set = 0, binding = 1, std430) readonly buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 2, std430) coherent buffer Reduce { vec4 partials[]; };
layout(set = 0, binding = 3, std430) coherent buffer Velocities { vec4 vel[]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float op;
    float _pad;
} pc;

shared vec4 work_acc[64];
shared vec4 work_vel[64];

void reduce_workgroup(uint lane) {
    for (uint stride = 32u; stride > 0u; stride >>= 1u) {
        barrier();
        if (lane < stride) {
            work_acc[lane] += work_acc[lane + stride];
            work_vel[lane] += work_vel[lane + stride];
        }
    }
    barrier();
}

void produce_partials() {
    uint lane = gl_LocalInvocationID.x;
    uint i = gl_GlobalInvocationID.x;
    uint count = uint(max(pc.N_f, 0.0));
    bool valid = i < count;
    float mass = valid ? max(pos[i].w, 0.0) : 0.0;
    vec3 a = valid ? acc[i].xyz : vec3(0.0);
    vec3 v = valid ? vel[i].xyz : vec3(0.0);
    work_acc[lane] = vec4(mass * a, mass);
    work_vel[lane] = vec4(mass * v, 0.0);
    reduce_workgroup(lane);
    if (lane == 0u) {
        uint base = 2u * gl_WorkGroupID.x;
        partials[base] = work_acc[0];
        partials[base + 1u] = work_vel[0];
    }
}

void reduce_partials() {
    uint lane = gl_LocalInvocationID.x;
    uint count = uint(max(pc.N_f, 0.0));
    uint groups = (count + 63u) / 64u;
    vec4 a = vec4(0.0);
    vec4 v = vec4(0.0);
    for (uint g = lane; g < groups; g += 64u) {
        a += partials[2u * g];
        v += partials[2u * g + 1u];
    }
    work_acc[lane] = a;
    work_vel[lane] = v;
    reduce_workgroup(lane);
    if (lane == 0u) {
        partials[0] = work_acc[0];
        partials[1] = work_vel[0];
    }
}

void subtract_means() {
    uint i = gl_GlobalInvocationID.x;
    uint count = uint(max(pc.N_f, 0.0));
    if (i >= count) {
        return;
    }
    float mass = max(partials[0].w, 1.0e-30);
    vec3 acceleration_mean = partials[0].xyz / mass;
    vec3 velocity_mean = partials[1].xyz / mass;
    acc[i].xyz -= acceleration_mean;
    vel[i].xyz -= velocity_mean;
}

void main() {
    if (pc.op < 0.5) {
        produce_partials();
    } else if (pc.op < 1.5) {
        subtract_means();
    } else if (pc.op > 2.5 && pc.op < 3.5) {
        reduce_partials();
    }
}
