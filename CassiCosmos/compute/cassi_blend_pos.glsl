#[compute]
#version 450
// Cassi position blend — snapshot/interpolation seam for the DECOUPLED
// PHYSICS PRODUCER. DORMANT NOW: the host pins alpha to 1.0, so
// pos_render == pos bit-for-bit and rendering is identical to today; the
// producer will drive alpha in (0, 1] later.
//
// Two dispatches per frame, one thread per particle (local_size 64):
//   (1) PRE-BATCH  (alpha = 2.0, the roll marker): pos_prev = pos — the
//       snapshot of the state that was last rendered, taken BEFORE the
//       step batch mutates pos. The alpha value > 1.0 is the marker that
//       tells this dispatch from the post-batch one (dormant alpha == 1.0
//       otherwise cannot distinguish them); the interp below clamps to
//       [0, 1], so the pre-batch pos_render write is still exactly pos.
//   (2) POST-BATCH (alpha = _interp_alpha): pos_render = mix(pos_prev,
//       pos, alpha) — the interpolated render snapshot the instancer
//       reads via the _us_inst_0_render uniform-set variant (binding 0).
//       alpha > 1.0 is false here (dormant 1.0, future (0, 1]), so the
//       pos_prev snapshot survives the post-batch dispatch.
//
// mix(x, y, 1.0) = y exactly in fp32, so at alpha = 1.0 pos_render is a
// byte-identical copy of pos (the whole point of the dormant seam).
//
// Push constant: one float alpha (offset 0). Godot reflects a 1-float
// block as exactly 4 bytes — the host passes a 4-byte PC.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform Params {
    float alpha;
} params;

layout(set = 0, binding = 0, std430) buffer PrevPos { vec4 pos_prev[]; };
layout(set = 0, binding = 1, std430) readonly buffer CurPos { vec4 pos[]; };
layout(set = 0, binding = 2, std430) buffer RenderPos { vec4 pos_render[]; };

void main() {
    uint i = gl_GlobalInvocationID.x;
    float a = params.alpha;
    // Pre-batch roll: pos_prev = pos ONLY on the roll-marker dispatch
    // (alpha > 1.0); identity (pos_prev unchanged) on the post-batch one.
    float roll = (a > 1.0) ? 1.0 : 0.0;
    vec4 prev = mix(pos_prev[i], pos[i], roll);
    pos_prev[i] = prev;
    // Render snapshot: pos_render = mix(pos_prev, pos, clamp(alpha, 0, 1)).
    // The clamp keeps the roll-marker dispatch (alpha = 2.0) writing
    // exactly pos (mix(x, x, 1.0) = x) instead of an extrapolation.
    pos_render[i] = mix(prev, pos[i], clamp(a, 0.0, 1.0));
}
