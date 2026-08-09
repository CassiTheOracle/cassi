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

    // Map pixel → grid coords.  Clamp so we never sample out of range
    // when the render target is larger than the grid.
    int gx = int(float(pixel.x) * float(N) / float(dims.x));
    int gy = int(float(pixel.y) * float(N) / float(dims.y));
    gx = clamp(gx, 0, N - 1);
    gy = clamp(gy, 0, N - 1);
    int gz = N / 2; // z-slice through the middle of the 3D grid

    int idx = gx + N * gy + N * N * gz;

    float ey_val = ey[idx];
    float ei_val = ei[idx];
    float q_val  = q[idx];

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
