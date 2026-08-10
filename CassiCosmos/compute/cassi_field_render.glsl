#[compute]
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

    // ── Background ───────────────────────────────────────────────────
    vec3 color = vec3(0.01, 0.01, 0.02);

    // ── Qi density → warm brightness ─────────────────────────────────
    // sqrt gives a perceptually smooth falloff; max guards against
    // any negative q that might arise from numerical drift.
    float q_brightness = sqrt(max(q_val, 0.0));
    color += vec3(1.0, 0.8, 0.3) * q_brightness;

    // ── Disequilibrium |EY − φ·EI| → blue/green imbalance ────────────
    // Positive imbalance (EY > φ·EI) → blue; negative → green.
    float diseq = ey_val - pc.phi * ei_val;
    float diseq_strength = 0.5 * sqrt(abs(diseq));
    if (diseq >= 0.0) {
        color += vec3(0.1, 0.3, 0.9) * diseq_strength; // blue-dominant
    } else {
        color += vec3(0.1, 0.8, 0.4) * diseq_strength; // green-dominant
    }

    color = clamp(color, 0.0, 1.0);
    imageStore(RenderTarget, pixel, vec4(color, 1.0));
}
