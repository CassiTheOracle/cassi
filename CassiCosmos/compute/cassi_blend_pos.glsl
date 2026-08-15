#[compute]
#version 450
// Cassi position blend — snapshot/interpolation seam for the DECOUPLED
// PHYSICS PRODUCER. Three modes, one shader, selected by the `packed`
// push-constant float (offset 4):
//
//   packed == 0.0  (fp32 path — the INLINE renderer and the decoupled
//                   fp32 bootstrap):
//       bindings 0/1 are fp32 vec4 buffers (pos_prev, pos). Two
//       dispatches per frame:
//         (1) PRE-BATCH  (alpha = 2.0, the roll marker): pos_prev = pos —
//             the snapshot of the state that was last rendered, taken
//             BEFORE the step batch mutates pos. alpha > 1.0 marks this
//             dispatch from the post-batch one; the interp below clamps
//             to [0, 1], so the pre-batch pos_render write is still
//             exactly pos.
//         (2) POST-BATCH (alpha = _interp_alpha): pos_render =
//             mix(pos_prev, pos, alpha) — the interpolated render
//             snapshot the instancer reads.
//       Byte-identical to the legacy single-mode shader (the raw uint
//       views round-trip exactly through uintBitsToFloat/floatBitsToUint).
//
//   packed == 1.0  (fp16 PACKED mirrors — the decoupled render path):
//       bindings 0/1 are uint32 half-pair buffers (N × 8 B per particle:
//       word 0 = (half(x) | half(y)<<16), word 1 = (half(z) | half(w)<<16)).
//       ONE dispatch per frame, alpha = _interp_alpha in [0, 1] (the host
//       maintains the pos_prev pair — NO roll marker dispatch in this
//       mode, so a > 1.0 must never be sent here):
//         prev = unpackHalf2x16 pairs; cur = unpackHalf2x16 pairs;
//         pos_render = mix(prev, cur, clamp(alpha, 0, 1)).
//       pos_render stays fp32 — the instancer/qhist consumers are
//       unchanged.
//
//   packed == 2.0  (fp16 vel UNPACK — one dispatch per frame in the
//                   decoupled render list):
//       binding 0 is the packed velocity buffer (N × 8 B, same half-pair
//       layout); binding 2 is the fp32 velocity mirror _vel_buf:
//         _vel_buf[i] = vec4(unpackHalf2x16(v0), unpackHalf2x16(v1)).
//       The instancer's mode-1 |v| rainbow then reads the fp32 mirror
//       exactly as before — no instancer edit.
//
// mix(x, y, 1.0) = y exactly in fp32, so at alpha = 1.0 pos_render is a
// byte-identical copy of pos (the whole point of the dormant seam).
//
// Push constant: five floats — alpha (offset 0), packed (offset 4), and
// the movable home-window origin (win @8/12/16 — subtracted from the
// RENDER snapshot only; the pos_prev roll stays raw physics so the next
// interpolation blends true positions. win = 0 → exactly the legacy
// output, bit-identical).

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform Params {
    float alpha;
    float packed;
    float win_x;
    float win_y;
    float win_z;
} params;

// Raw uint views of bindings 0/1: the fp32 buffers are N×16 B (vec4 per
// particle → 4 uints at i*4), the packed buffers are N×8 B (2 uints at
// i*2). The mode selects the interpretation — no re-layout, no separate
// set definition.
layout(set = 0, binding = 0, std430) buffer PrevRaw { uint prev_raw[]; };
layout(set = 0, binding = 1, std430) readonly buffer CurRaw { uint cur_raw[]; };
layout(set = 0, binding = 2, std430) buffer RenderBuf { vec4 out_data[]; };

void main() {
    uint i = gl_GlobalInvocationID.x;
    float a = params.alpha;
    float mode = params.packed;

    if (mode == 2.0) {
        // Velocity unpack: packed half-pairs → fp32 vec4 mirror.
        uint v0 = prev_raw[i * 2];
        uint v1 = prev_raw[i * 2 + 1];
        out_data[i] = vec4(unpackHalf2x16(v0), unpackHalf2x16(v1));
        return;
    }

    if (mode == 1.0) {
        // Packed position blend: unpack the half-pair mirrors, interpolate.
        // No roll here — the host maintains the pos_prev pair, so alpha is
        // always in [0, 1] on this path.
        uint p0 = prev_raw[i * 2];
        uint p1 = prev_raw[i * 2 + 1];
        vec4 prev = vec4(unpackHalf2x16(p0), unpackHalf2x16(p1));
        uint c0 = cur_raw[i * 2];
        uint c1 = cur_raw[i * 2 + 1];
        vec4 cur = vec4(unpackHalf2x16(c0), unpackHalf2x16(c1));
        out_data[i] = mix(prev, cur, clamp(a, 0.0, 1.0)) - vec4(params.win_x, params.win_y, params.win_z, 0.0);
        return;
    }

    // fp32 path (mode == 0.0): pre-batch roll (pos_prev = pos ONLY on the
    // roll-marker dispatch, alpha > 1.0; identity on the post-batch one)
    // then the render snapshot. uintBitsToFloat/floatBitsToUint are exact
    // round-trips, so this is byte-identical to the vec4-declared shader.
    vec4 prev = mix(vec4(uintBitsToFloat(prev_raw[i * 4]),
                         uintBitsToFloat(prev_raw[i * 4 + 1]),
                         uintBitsToFloat(prev_raw[i * 4 + 2]),
                         uintBitsToFloat(prev_raw[i * 4 + 3])),
                    vec4(uintBitsToFloat(cur_raw[i * 4]),
                         uintBitsToFloat(cur_raw[i * 4 + 1]),
                         uintBitsToFloat(cur_raw[i * 4 + 2]),
                         uintBitsToFloat(cur_raw[i * 4 + 3])),
                    (a > 1.0) ? 1.0 : 0.0);
    prev_raw[i * 4] = floatBitsToUint(prev.x);
    prev_raw[i * 4 + 1] = floatBitsToUint(prev.y);
    prev_raw[i * 4 + 2] = floatBitsToUint(prev.z);
    prev_raw[i * 4 + 3] = floatBitsToUint(prev.w);
    out_data[i] = mix(prev,
                      vec4(uintBitsToFloat(cur_raw[i * 4]),
                           uintBitsToFloat(cur_raw[i * 4 + 1]),
                           uintBitsToFloat(cur_raw[i * 4 + 2]),
                           uintBitsToFloat(cur_raw[i * 4 + 3])),
                      clamp(a, 0.0, 1.0))
                  - vec4(params.win_x, params.win_y, params.win_z, 0.0);
}
