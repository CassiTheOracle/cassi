#[compute]
// canonical layout: scripts/contracts/layout.gd §WorkbenchField — set 0: binding 0 EY, 1 EI, 2 Q; PC 14 scalar floats
#version 450
// Cassi interactive workbench field operator.
// One invocation updates one x-fastest periodic grid cell. Mode 1 aligns
// (EY, EI) toward the normalized (phi, 1) target while preserving magnitude.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer FieldEY { float ey[]; };
layout(set = 0, binding = 1, std430) buffer FieldEI { float ei[]; };
layout(set = 0, binding = 2, std430) buffer FieldQ  { float q[]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float center_x;
    float center_y;
    float center_z;
    float radius;
    float strength;
    float extent_x;
    float extent_y;
    float extent_z;
    float window_center_x;
    float window_center_y;
    float window_center_z;
    float mode;
    float phi;
} pc;

float periodic_delta(float a, float b, float extent) {
    float period = 2.0 * max(abs(extent), 1e-12);
    float d = a - b;
    return d - period * floor(d / period + 0.5);
}

void main() {
    uint index = gl_GlobalInvocationID.x;
    int n = int(pc.N_f);
    if (n <= 0 || index >= uint(n * n * n)) return;

    int nn = int(index);
    int ix = nn % n;
    int iy = (nn / n) % n;
    int iz = nn / (n * n);
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 win = vec3(pc.window_center_x, pc.window_center_y, pc.window_center_z);
    vec3 cell = vec3((float(ix) + 0.5) * 2.0 * ext.x / float(n) - ext.x,
                     (float(iy) + 0.5) * 2.0 * ext.y / float(n) - ext.y,
                     (float(iz) + 0.5) * 2.0 * ext.z / float(n) - ext.z) + win;
    vec3 center = vec3(pc.center_x, pc.center_y, pc.center_z);
    vec3 d = vec3(periodic_delta(cell.x, center.x, ext.x),
                  periodic_delta(cell.y, center.y, ext.y),
                  periodic_delta(cell.z, center.z, ext.z));
    float r = max(pc.radius, 0.0);
    if (r <= 0.0 || dot(d, d) > r * r || pc.mode != 1.0) return;

    float y = ey[index];
    float i = ei[index];
    float magnitude = sqrt(max(y * y + i * i, 0.0));
    // A zero drive is an exact identity, including Q bit preservation.
    if (pc.strength == 0.0) return;

    float phi = pc.phi;
    float target_norm = sqrt(phi * phi + 1.0);
    vec2 target = vec2(phi, 1.0) / max(target_norm, 1e-12);
    vec2 current = (magnitude > 1e-12) ? vec2(y, i) / magnitude : target;
    float amount = clamp(pc.strength, 0.0, 1.0);
    vec2 blended = current + amount * (target - current);
    float blended_len = length(blended);
    // Antipodal interpolation can cancel exactly; use the target direction.
    vec2 direction = (blended_len > 1e-12) ? blended / blended_len : target;
    ey[index] = magnitude * direction.x;
    ei[index] = magnitude * direction.y;
    q[index] = magnitude * magnitude;
}
