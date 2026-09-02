#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 11 floats (44 B); sets 0 (0-5), 2 (0)
#version 450
// Cassi Field Visualization — renders a 2D slice (z = N/2) of the
// two-fluid field (EY, EI, Q) as a color image.
//
// Color mapping:
//   Q (Qi density)       → warm brightness:  (1, 0.8, 0.3) * sqrt(q)
//   |EY − φ·EI| (diseq)  → blue/green imbalance
//   Background            → dark (0.01, 0.01, 0.02)
//
// Each thread writes one pixel to the output image.
// Used for "Field" visualization mode (mode == 1).

layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;

// ── Field grid buffers (SET 0) ───────────────────────────────────────
layout(set = 0, binding = 0, std430) restrict buffer FieldEY  { float ey[]; };
layout(set = 0, binding = 1, std430) restrict buffer FieldEI  { float ei[]; };
layout(set = 0, binding = 2, std430) buffer FieldQ            { float q[]; };
layout(set = 0, binding = 3, std430) buffer FieldVel          { vec4  vel[]; };
layout(set = 0, binding = 4, std430) readonly buffer FieldPlasticity { vec2 pe[]; };
layout(set = 0, binding = 5, std430) readonly buffer FieldLearningState {
    vec4 learn_metrics;
    vec4 learn_target;
    vec4 learn_probe;
    vec4 learn_organ;
    vec4 learn_control;
    vec4 learn_context;
    uvec4 learn_status;
    uvec4 learn_flags;
};

// ── Render target (SET 2) ────────────────────────────────────────────
layout(set = 2, binding = 0, rgba32f) uniform image2D RenderTarget;

// ── Push constants ────────────────────────────────────────────────────
layout(push_constant, std430) uniform PC {
    float N_f;             // grid resolution per dimension
    float dt;              // simulation timestep
    float t;               // current elapsed time
    float phi;             // golden ratio (1.6180339)
    float xi;              // Cassi Qi coupling
    float eps2;            // softening (unused here)
    float particle_N;      // particle count (unused here)
    float mode;            // visualization mode (1 = field slice)
    float source_strength; // (unused here)
    float num_clusters;    // (unused here)
    float gravity_mode;    // (unused here)
} pc;

vec3 hsv_to_rgb(float h, float s, float v) {
    vec3 p = abs(fract(h + vec3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
    return v * mix(vec3(1.0), clamp(p - 1.0, 0.0, 1.0), s);
}

vec2 plasticity_at(vec2 uv, int N, int gz) {
    ivec2 cell = clamp(ivec2(floor(uv * float(N))), ivec2(0), ivec2(N - 1));
    int id = cell.x + N * cell.y + N * N * gz;
    return pe[id];
}

void main() {
    ivec2 pixel = ivec2(gl_GlobalInvocationID.xy);
    ivec2 dims  = imageSize(RenderTarget);
    if (pixel.x >= dims.x || pixel.y >= dims.y) return;

    int N = int(pc.N_f);
    if (N <= 0) {
        imageStore(RenderTarget, pixel, vec4(0.01, 0.01, 0.02, 1.0));
        return;
    }

    // Map pixel → grid coords with bilinear sampling (4 loads + fractional
    // lerp per axis). The old nearest-neighbor truncation stair-stepped one
    // cell = 8×8 pixels at 512² and visually sharpened the ring corners.
    float fx = float(pixel.x) * float(N) / float(dims.x);
    float fy = float(pixel.y) * float(N) / float(dims.y);
    int gx = int(fx);
    int gy = int(fy);
    float tx = fx - float(gx);
    float ty = fy - float(gy);
    // Clamp so we never sample out of range when the render target is
    // smaller than the grid (the old clamp behavior; tx/ty then saturate
    // to the last cell).
    gx = clamp(gx, 0, N - 2);
    gy = clamp(gy, 0, N - 2);
    tx = clamp(tx, 0.0, 1.0);
    ty = clamp(ty, 0.0, 1.0);
    int gz = N / 2; // z-slice through the middle of the 3D grid

    int i00 = gx + N * gy + N * N * gz;
    int i10 = i00 + 1;
    int i01 = i00 + N;
    int i11 = i01 + 1;

    float ey00 = ey[i00]; float ey10 = ey[i10];
    float ey01 = ey[i01]; float ey11 = ey[i11];
    float ey_val = mix(mix(ey00, ey10, tx), mix(ey01, ey11, tx), ty);

    float ei00 = ei[i00]; float ei10 = ei[i10];
    float ei01 = ei[i01]; float ei11 = ei[i11];
    float ei_val = mix(mix(ei00, ei10, tx), mix(ei01, ei11, tx), ty);

    float q00 = q[i00]; float q10 = q[i10];
    float q01 = q[i01]; float q11 = q[i11];
    float q_val = mix(mix(q00, q10, tx), mix(q01, q11, tx), ty);

    if (pc.mode > 4.5) {
        float phase = fract((atan(ei_val, ey_val) + 3.141592653589793) / 6.283185307179586);
        float energy = 1.0 - exp(-18.0 * sqrt(max(q_val, 0.0)));
        vec3 phase_color = hsv_to_rgb(phase, 0.82, 0.12 + 0.88 * energy);
        float wave = clamp(0.18 + energy, 0.0, 1.0);
        vec4 output_color = vec4(phase_color, 0.18 + 0.72 * wave);
        if (pixel.x == 0 && pixel.y == 0) {
            uint tick = learn_status.w;
            vec4 receipt = vec4(
                float(tick & 255u),
                float((tick >> 8u) & 255u),
                float((tick >> 16u) & 255u),
                255.0) / 255.0;
            imageStore(RenderTarget, pixel, receipt);
            return;
        }

        // Bottom-right inset: live P/e sampled directly from the same SSBO
        // the learning and two-fluid passes used in this command list.
        vec2 screen_uv = (vec2(pixel) + vec2(0.5)) / vec2(dims);
        const vec2 inset_min = vec2(0.675, 0.675);
        const vec2 inset_max = vec2(0.975, 0.975);
        if (all(greaterThanEqual(screen_uv, inset_min))
                && all(lessThanEqual(screen_uv, inset_max))) {
            vec2 inset_uv = (screen_uv - inset_min) / (inset_max - inset_min);
            vec2 state = plasticity_at(inset_uv, N, gz);
            float p_norm = clamp(state.x / max(pc.source_strength, 1e-6), -1.0, 1.0);
            float e_norm = 1.0 - exp(-0.12 * max(state.y, 0.0));
            vec3 negative = vec3(0.92, 0.16, 0.72);
            vec3 positive = vec3(0.05, 0.88, 1.0);
            vec3 p_color = mix(vec3(0.025, 0.03, 0.07),
                               positive, max(p_norm, 0.0));
            p_color = mix(p_color, negative, max(-p_norm, 0.0));
            p_color += vec3(1.0, 0.58, 0.08) * e_norm * 0.65;
            bool border = any(lessThan(inset_uv, vec2(0.018)))
                       || any(greaterThan(inset_uv, vec2(0.982)));
            output_color = vec4(border ? vec3(0.75, 0.86, 1.0)
                                       : clamp(p_color, 0.0, 1.0), 0.96);
        }
        imageStore(RenderTarget, pixel, output_color);
        return;
    }

    // ── Transparent background + volumetric field contribution ──────────
    // Empty cells contribute no overlay, while field energy contributes a
    // soft alpha so the GPU particle MultiMesh remains visible underneath.
    vec3 color = vec3(0.0);
    float q_brightness = sqrt(max(q_val, 0.0));
    color += vec3(1.0, 0.8, 0.3) * q_brightness;

    float diseq = ey_val - pc.phi * ei_val;
    float diseq_strength = 0.5 * sqrt(abs(diseq));
    if (diseq >= 0.0) {
        color += vec3(0.1, 0.3, 0.9) * diseq_strength;
    } else {
        color += vec3(0.1, 0.8, 0.4) * diseq_strength;
    }

    color = clamp(color, 0.0, 1.0);
    float alpha = clamp(max(q_brightness, diseq_strength) * 1.35, 0.0, 0.82);
    imageStore(RenderTarget, pixel, vec4(color, alpha));
}
