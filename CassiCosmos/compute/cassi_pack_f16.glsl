#[compute]
#version 450
// Cassi fp16 snapshot pack — worker-side packing for the decoupled mirror
// transfer (scripts/cassi_physics_engine.gd readback_snapshot(packed=true)).
// Runs on the ENGINE's local RD (the worker thread owns the device), so
// the fp32→fp16 conversion AND the halved readback both land off the main
// thread; the render side unpacks in cassi_blend_pos.glsl (packed modes).
//
// Per particle: vec4 → uvec2 half-pairs, N × 8 B:
//   word 0 = (half(x) | half(y) << 16), word 1 = (half(z) | half(w) << 16)
//
// ROUNDING: packHalf2x16 is implementation-defined on some vendors (AMD's
// V_CVT_PKRTZ truncates → up to 1 ULP error). We do the conversion
// EXPLICITLY with round-to-nearest-even (the same bit twiddle as the
// host's reference _f32_to_f16()), so the GPU pack is byte-identical to
// the CPU reference and the error stays ≤ half-ULP (≤ 2^-11 relative).
//
// Push constant: uint count (offset 0) + pad (offset 4) — 8 bytes total.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform Params {
    uint count;
    uint pad;
} params;

layout(set = 0, binding = 0, std430) readonly buffer InBuf { vec4 in_data[]; };
layout(set = 0, binding = 1, std430) buffer OutBuf { uvec2 out_packed[]; };

uint half_rne(float x) {
    uint u = floatBitsToUint(x);
    uint sign = (u >> 16u) & 0x8000u;
    uint exp = (u >> 23u) & 0xFFu;
    uint mant = u & 0x7FFFFFu;
    if (exp == 0xFFu) {
        // inf / NaN (payload truncated — matches the host reference).
        return sign | 0x7C00u | (mant >> 13u);
    }
    int e = int(exp) - 127 + 15;
    if (e >= 0x1F) {
        return sign | 0x7C00u;              // overflow -> +-inf
    }
    if (e <= 0) {
        return sign;                        // |x| < 2^-14 -> +-0 (host parity)
    }
    uint h = sign | (uint(e) << 10u) | (mant >> 13u);
    uint rem = mant & 0x1FFFu;
    if (rem > 0x1000u || (rem == 0x1000u && ((h >> 10u) & 1u) == 1u)) {
        h += 1u;                            // round-to-nearest-even
    }
    return h;
}

void main() {
    uint i = gl_GlobalInvocationID.x;
    if (i >= params.count) {
        return;
    }
    vec4 v = in_data[i];
    out_packed[i] = uvec2(
            half_rne(v.x) | (half_rne(v.y) << 16u),
            half_rne(v.z) | (half_rne(v.w) << 16u));
}
