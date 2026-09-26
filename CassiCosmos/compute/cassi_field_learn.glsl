#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 16 floats (64 B); set 0: bindings 0-2
#version 450
// Cassi embodied field intelligence.
//
// One authoritative world field owns both the fast Yang/Yin dynamics and the
// slow learned state.  pe[].x is slow plasticity P; pe[].y is the eligibility
// trace e.  Six fixed actuator lobes surround the field organ.  Within each
// lobe, goal direction is encoded as a spatial offset, so one scalar P channel
// stores a target-conditioned six-action policy without a second model.
//
// Passes (pc.pass_sel):
//   0 measure reward from the live probe particle
//   1 update e and P over the whole field
//   2 select the next bounded actuator from P (deterministic ties)
//   3 clear P and e
//   4 clear e only at an episode boundary

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer FieldPlasticity {
    vec2 pe[];                         // x=P, y=eligibility
};

// Fixed 128-byte header: eight naturally-aligned 16-byte lanes.
layout(set = 0, binding = 1, std430) buffer FieldLearningState {
    vec4 metrics;                      // previous distance, reward, control energy, support margin
    vec4 target;                       // target world xyz, success radius
    vec4 probe;                        // measured probe xyz, live mass
    vec4 organ;                        // organ world xyz, actuator-lobe radius
    vec4 control;                      // bounded medium-flow xyz, selected P score
    vec4 context;                      // previous goal direction xyz, reserved
    uvec4 status;                      // enabled, episode, probe index, logical tick
    uvec4 flags;                       // selected action, training, fault bits, schema version
} learn;

layout(set = 0, binding = 2, std430) readonly buffer ParticlePosition {
    vec4 pos[];
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float particle_N;
    float extent_x;
    float extent_y;
    float extent_z;
    float eta;
    float gamma;
    float decay;
    float p_max;
    float actuation;
    float energy_penalty;
    float explore_period;
    float explore_steps;
    float context_radius;
    float kernel_radius;
    float pass_sel;
} pc;

const uint FAULT_PROBE_OOB = 1u;
const uint FAULT_PROBE_DEAD = 2u;

vec3 axis_dir(uint action) {
    if (action == 0u) return vec3( 1.0, 0.0, 0.0);
    if (action == 1u) return vec3(-1.0, 0.0, 0.0);
    if (action == 2u) return vec3( 0.0, 1.0, 0.0);
    if (action == 3u) return vec3( 0.0,-1.0, 0.0);
    if (action == 4u) return vec3( 0.0, 0.0, 1.0);
    return vec3(0.0, 0.0,-1.0);
}

ivec3 world_to_cell(vec3 world) {
    int N = max(int(pc.N_f), 1);
    vec3 ext = max(vec3(pc.extent_x, pc.extent_y, pc.extent_z), vec3(1e-6));
    vec3 uv = clamp(world / (2.0 * ext) + vec3(0.5), vec3(0.0), vec3(0.999999));
    return clamp(ivec3(floor(uv * float(N))), ivec3(0), ivec3(N - 1));
}

uint cell_id(ivec3 c) {
    uint N = uint(max(int(pc.N_f), 1));
    return uint(c.x) + N * (uint(c.y) + N * uint(c.z));
}

uint linear_id() {
    return gl_GlobalInvocationID.x
         + gl_GlobalInvocationID.y * gl_NumWorkGroups.x * gl_WorkGroupSize.x;
}

vec3 cell_world(uint id) {
    int N = max(int(pc.N_f), 1);
    uint Nu = uint(N);
    uint z = id / (Nu * Nu);
    uint rem = id - z * Nu * Nu;
    uint y = rem / Nu;
    uint x = rem - y * Nu;
    vec3 uv = (vec3(x, y, z) + vec3(0.5)) / float(N);
    return (uv * 2.0 - vec3(1.0)) * vec3(pc.extent_x, pc.extent_y, pc.extent_z);
}

vec3 context_point(uint action, vec3 goal_dir) {
    return learn.organ.xyz + axis_dir(action) * learn.organ.w
         + goal_dir * max(pc.context_radius, 0.0);
}

float sample_plasticity(uint action, vec3 goal_dir) {
    return pe[cell_id(world_to_cell(context_point(action, goal_dir)))].x;
}

void measure_reward() {
    if (gl_GlobalInvocationID.x != 0u) return;
    if (learn.status.x == 0u) {
        learn.control = vec4(0.0);
        return;
    }

    uint count = uint(max(pc.particle_N, 0.0));
    uint probe_index = learn.status.z;
    if (count == 0u || probe_index >= count) {
        learn.flags.z |= FAULT_PROBE_OOB;
        learn.control = vec4(0.0);
        return;
    }

    vec4 body = pos[probe_index];
    if (body.w <= 0.0) {
        learn.flags.z |= FAULT_PROBE_DEAD;
        learn.control = vec4(0.0);
        return;
    }

    float distance_now = length(learn.target.xyz - body.xyz);
    float energy = dot(learn.control.xyz, learn.control.xyz);
    float reward = 0.0;
    if (learn.status.w > 0u) {
        reward = clamp(learn.metrics.x - distance_now, -1.0, 1.0)
               - max(pc.energy_penalty, 0.0) * energy;
    }
    // Control arm: preserve every reward magnitude but deterministically
    // permute its sign, breaking the action-outcome association without
    // changing the world dynamics or reward scale.
    if ((learn.flags.w >> 16u) == 1u && learn.status.w > 0u) {
        uint shuffled = learn.status.w * 747796405u
                      + learn.status.y * 2891336453u;
        shuffled ^= shuffled >> 16u;
        shuffled *= 2246822519u;
        shuffled ^= shuffled >> 13u;
        shuffled *= 3266489917u;
        shuffled ^= shuffled >> 16u;
        reward = abs(reward) * ((shuffled & 1u) == 0u ? -1.0 : 1.0);
    }
    learn.metrics = vec4(distance_now, reward, energy, learn.metrics.w);
    learn.probe = body;
    learn.status.w += 1u;
}

void update_plasticity() {
    uint id = linear_id();
    uint N = uint(max(int(pc.N_f), 1));
    uint cells = N * N * N;
    if (id >= cells || learn.status.x == 0u) return;

    vec2 old = pe[id];
    if (learn.flags.y == 0u) {
        pe[id] = vec2(old.x, 0.0);      // replay freezes the learned state
        return;
    }

    uint action = min(learn.flags.x, 5u);
    vec3 center = context_point(action, learn.context.xyz);
    float sigma = max(pc.kernel_radius, 1e-4);
    vec3 delta = cell_world(id) - center;
    float activation = exp(-0.5 * dot(delta, delta) / (sigma * sigma));
    float eligibility = clamp(pc.gamma, 0.0, 1.0) * old.y + activation;
    float plasticity = (1.0 - clamp(pc.decay, 0.0, 1.0)) * old.x
                     + max(pc.eta, 0.0) * learn.metrics.y * eligibility;
    float bound = max(pc.p_max, 1e-6);
    pe[id] = vec2(clamp(plasticity, -bound, bound), eligibility);
}

void select_control() {
    if (gl_GlobalInvocationID.x != 0u) return;
    if (learn.status.x == 0u || learn.flags.z != 0u) {
        learn.control = vec4(0.0);
        return;
    }

    vec3 to_target = learn.target.xyz - learn.probe.xyz;
    float distance_now = length(to_target);
    if (distance_now <= max(learn.target.w, 0.0)) {
        learn.control = vec4(0.0);
        learn.metrics.w = 0.0;
        return;
    }
    vec3 goal_dir = to_target / max(distance_now, 1e-8);

    float scores[6];
    uint best = 0u;
    float best_score = sample_plasticity(0u, goal_dir);
    scores[0] = best_score;
    for (uint action = 1u; action < 6u; action++) {
        float score = sample_plasticity(action, goal_dir);
        scores[action] = score;
        // Strict greater-than makes an exact tie choose the lower action id.
        if (score > best_score + 1e-6) {
            best = action;
            best_score = score;
        }
    }

    float second = -3.402823e38;
    for (uint action = 0u; action < 6u; action++) {
        if (action != best) second = max(second, scores[action]);
    }

    if (learn.flags.y != 0u) {
        uint tick = learn.status.w;
        uint warm = uint(max(pc.explore_steps, 0.0));
        uint period = uint(max(pc.explore_period, 0.0));
        if (tick <= warm) {
            best = tick % 6u;
            best_score = scores[best];
        } else if (period > 0u && tick % period == 0u) {
            best = (tick / period) % 6u;
            best_score = scores[best];
        }
    }

    float support_floor = max(1e-4, 0.01 * max(pc.p_max, 1e-6));
    float confidence = learn.flags.y != 0u ? 1.0
                     : (best_score > support_floor ? 1.0 : 0.0);
    float approach = clamp(distance_now / max(learn.organ.w, 1e-4), 0.0, 1.0);
    float amplitude = clamp(pc.actuation, 0.0, 8.0) * confidence * approach;
    learn.control = vec4(axis_dir(best) * amplitude, best_score);
    learn.context = vec4(goal_dir, 0.0);
    learn.flags.x = best;
    learn.metrics.w = best_score - second;
}

void clear_all() {
    uint id = linear_id();
    uint N = uint(max(int(pc.N_f), 1));
    uint cells = N * N * N;
    if (id < cells) pe[id] = vec2(0.0);
}

void clear_eligibility() {
    uint id = linear_id();
    uint N = uint(max(int(pc.N_f), 1));
    uint cells = N * N * N;
    if (id < cells) pe[id].y = 0.0;
}

void main() {
    if (pc.pass_sel < 0.5) measure_reward();
    else if (pc.pass_sel < 1.5) update_plasticity();
    else if (pc.pass_sel < 2.5) select_control();
    else if (pc.pass_sel < 3.5) clear_all();
    else clear_eligibility();
}
