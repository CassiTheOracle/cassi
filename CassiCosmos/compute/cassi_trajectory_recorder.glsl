#[compute]
#version 450

// Passive trajectory and merge-event recorder.
//
// Pass 0: write the deterministic tracer set at step zero.
// Pass 1: write one sample for every accepted step on the registered stride.
// Pass 2: after a merge hop, append one source -> survivor event per accepted
//         sink-rule hop. No physics-owned buffer is written.
//
// Radial crossings and turnarounds are derived from the sampled radial
// trajectory. The registered sample stride is therefore the measurement
// resolution for those two diagnostics.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float N;
    float tracer_count;
    float sample_capacity;
    float sample_stride;
    float event_capacity;
    float pass_mode;
    float step;
    float center_x;
    float center_y;
    float center_z;
    float inner_radius;
    float outer_radius;
} pc;

layout(set = 0, binding = 0, std430) readonly buffer Positions {
    vec4 pos[];
};
layout(set = 0, binding = 1, std430) readonly buffer Velocities {
    vec4 vel[];
};
layout(set = 0, binding = 2, std430) readonly buffer TracerIds {
    uint tracer_ids[];
};
layout(set = 0, binding = 3, std430) readonly buffer MergeBest {
    int best[];
};
layout(set = 0, binding = 4, std430) readonly buffer MergeSink {
    float sink[];
};
layout(set = 0, binding = 5, std430) readonly buffer MergeMass {
    float mass[];
};
layout(set = 0, binding = 6, std430) readonly buffer MergeMomentum {
    vec4 momentum[];
};
layout(set = 0, binding = 7, std430) readonly buffer MergeCentroid {
    vec4 centroid_buf[];
};
layout(set = 0, binding = 8, std430) coherent buffer SampleHistoryPos {
    vec4 history_pos[];
};
layout(set = 0, binding = 9, std430) coherent buffer SampleHistoryVel {
    vec4 history_vel[];
};
layout(set = 0, binding = 10, std430) coherent buffer SampleSteps {
    uint sample_steps[];
};
struct EventRecord {
    uvec4 meta;       // step, source slot, survivor slot, accepted-hop flag
    vec4 source_pos;  // pre-hop source position xyz, source mass
    vec4 source_vel;  // pre-hop source velocity xyz, source radial velocity
    vec4 survivor_pos;// post-hop COM position xyz, aggregate mass
    vec4 survivor_vel;// post-hop aggregate velocity xyz, radial velocity
};
layout(set = 0, binding = 11, std430) coherent buffer Events {
    EventRecord events[];
};
layout(set = 0, binding = 12, std430) buffer Telemetry {
    uint counters[];  // event_total, event_overflow, sample_total, sample_overflow
};
layout(set = 0, binding = 13, std430) readonly buffer Fallback {
    uint fallback[];
};

uint as_uint(float value) {
    return uint(max(value, 0.0) + 0.5);
}

vec3 center_world() {
    return vec3(pc.center_x, pc.center_y, pc.center_z);
}

float radial_velocity(vec3 position, vec3 velocity) {
    vec3 delta = position - center_world();
    float radius = length(delta);
    return radius > 1.0e-12 ? dot(velocity, delta / radius) : 0.0;
}

void record_sample(uint tracer, uint particle, uint slot) {
    uint base = slot * as_uint(pc.tracer_count) + tracer;
    vec4 p = pos[particle];
    vec4 v = vel[particle];
    history_pos[base] = p;
    history_vel[base] = vec4(v.xyz, radial_velocity(p.xyz, v.xyz));
    if (tracer == 0u) sample_steps[slot] = as_uint(pc.step);
}

void record_history(uint slot) {
    uint tracer = gl_GlobalInvocationID.x;
    uint tracer_total = as_uint(pc.tracer_count);
    uint particle_total = as_uint(pc.N);
    if (tracer >= tracer_total) return;
    uint particle = tracer_ids[tracer];
    if (particle >= particle_total) return;
    record_sample(tracer, particle, slot);
}

void record_event() {
    uint source = gl_GlobalInvocationID.x;
    uint particle_total = as_uint(pc.N);
    if (source >= particle_total) return;
    // Pass 5 leaves accepted sources dead before this pass. The stable
    // best/source ordering plus a sink target is the accepted-hop predicate.
    int target = best[source];
    if (target < 0 || target >= int(particle_total) || target >= int(source)) return;
    if (sink[target] < 0.5) return;
    uint serial = atomicAdd(counters[0], 1u);
    uint capacity = as_uint(pc.event_capacity);
    if (serial >= capacity) {
        atomicAdd(counters[1], 1u);
        return;
    }
    uint survivor = uint(target);
    float survivor_mass = max(mass[survivor], 1.0e-30);
    vec3 survivor_position = centroid_buf[survivor].xyz / survivor_mass;
    vec3 survivor_velocity = momentum[survivor].xyz / survivor_mass;
    EventRecord event;
    event.meta = uvec4(as_uint(pc.step), source, survivor, 1u);
    event.source_pos = vec4(pos[source].xyz, mass[source]);
    event.source_vel = vec4(vel[source].xyz,
            radial_velocity(pos[source].xyz, vel[source].xyz));
    event.survivor_pos = vec4(survivor_position, survivor_mass);
    event.survivor_vel = vec4(survivor_velocity,
            radial_velocity(survivor_position, survivor_velocity));
    events[serial] = event;
}

void main() {
    uint step = as_uint(pc.step);
    uint capacity = as_uint(pc.sample_capacity);
    if (pc.pass_mode < 0.5) {
        uint tracer = gl_GlobalInvocationID.x;
        uint tracer_total = as_uint(pc.tracer_count);
        uint particle_total = as_uint(pc.N);
        if (tracer >= tracer_total) return;
        uint particle = tracer_ids[tracer];
        if (particle >= particle_total) return;
        record_sample(tracer, particle, 0u);
        if (tracer == 0u) atomicMax(counters[2], 1u);
    } else if (pc.pass_mode < 1.5) {
        uint stride = as_uint(pc.sample_stride);
        if (stride == 0u || step % stride != 0u) return;
        uint slot = (step / stride) % capacity;
        record_history(slot);
        if (gl_GlobalInvocationID.x == 0u) {
            uint serial = step / stride + 1u;
            atomicMax(counters[2], serial);
            if (serial > capacity) atomicMax(counters[3], serial - capacity);
        }
    } else {
        record_event();
    }
}
