#[compute]
// canonical layout: scripts/contracts/layout.gd §WorkbenchParticle — set 0: binding 0 pos vec4, 1 vel vec4; PC 14 scalar floats
#version 450
// Cassi interactive workbench particle impulse. Positions are world-space;
// the selection sphere uses shortest periodic displacement on each axis.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer ParticlePositions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) buffer ParticleVelocities { vec4 vel[]; };

layout(push_constant, std430) uniform PC {
    float particle_N;
    float center_x;
    float center_y;
    float center_z;
    float radius;
    float impulse_x;
    float impulse_y;
    float impulse_z;
    float extent_x;
    float extent_y;
    float extent_z;
    float window_center_x;
    float window_center_y;
    float window_center_z;
} pc;

float periodic_delta(float a, float b, float extent) {
    float period = 2.0 * max(abs(extent), 1e-12);
    float d = a - b;
    return d - period * floor(d / period + 0.5);
}

void main() {
    uint index = gl_GlobalInvocationID.x;
    int count = int(pc.particle_N);
    if (count <= 0 || index >= uint(count) || index >= uint(pos.length())) return;

    vec4 p = pos[index];
    if (p.w <= 0.0) return;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 center = vec3(pc.center_x, pc.center_y, pc.center_z);
    vec3 d = vec3(periodic_delta(p.x, center.x, ext.x),
                  periodic_delta(p.y, center.y, ext.y),
                  periodic_delta(p.z, center.z, ext.z));
    float r = max(pc.radius, 0.0);
    if (r <= 0.0 || dot(d, d) > r * r) return;
    vel[index].xyz += vec3(pc.impulse_x, pc.impulse_y, pc.impulse_z);
}
