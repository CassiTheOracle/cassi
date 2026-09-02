#[compute]
#version 450
// Authoritative paused-world particle-program commit. The CPU compiler and
// workbench validate a canonical program and produce one complete fp32 target
// state; this kernel is the only decoupled-engine path that publishes that
// particle state into the live simulation buffers.
//
// Bindings (set 0):
//   0 target position/mass, 1 target velocity, 2 target acceleration,
//   3 live position/mass,   4 live velocity,   5 live acceleration.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly restrict buffer TargetPos { vec4 target_pos[]; };
layout(set = 0, binding = 1, std430) readonly restrict buffer TargetVel { vec4 target_vel[]; };
layout(set = 0, binding = 2, std430) readonly restrict buffer TargetAcc { vec4 target_acc[]; };
layout(set = 0, binding = 3, std430) restrict buffer LivePos { vec4 live_pos[]; };
layout(set = 0, binding = 4, std430) restrict buffer LiveVel { vec4 live_vel[]; };
layout(set = 0, binding = 5, std430) restrict buffer LiveAcc { vec4 live_acc[]; };

layout(push_constant, std430) uniform PC {
    uint particle_count;
    uint reserved_0;
    uint reserved_1;
    uint reserved_2;
} pc;

void main() {
    uint particle = gl_GlobalInvocationID.x;
    if (particle >= pc.particle_count) return;
    live_pos[particle] = target_pos[particle];
    live_vel[particle] = target_vel[particle];
    live_acc[particle] = target_acc[particle];
}
