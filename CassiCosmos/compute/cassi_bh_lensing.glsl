#[compute]
#version 450
// Cassi Black Hole Gravitational Lensing — Screen-Space Post-Process
//
// Implements gravitational lensing from a Cassi black hole using:
//   - Cassi-enhanced deflection: alpha = 2*r_s/b * (1 + xi*G_eff_ext)
//   - BH shadow (b < b_crit): pure black
//   - Accretion disk emission at Cassi ISCO (~3*G*M)
//   - Gravitational redshift: color *= sqrt(1 - r_s/r)
//
// Reference: experiments/cassi_spacetime_metric.py,
//            experiments/cassi_black_hole_raytracer.py

layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;

// ── Screen texture (input/output) ──────────────────────────────────────
layout(set = 2, binding = 0, rgba32f) uniform restrict image2D screenImage;

// ── BH params buffer: vec4[4] ──────────────────────────────────────────
// [0] = BH screen position (x, y, z), w unused
// [1] = (mass, spin, G_eff_ext, _pad)
// [2] = unused (reserved)
// [3] = unused (reserved)
layout(set = 2, binding = 1, std430) restrict readonly buffer BHParams {
    vec4 bh_pos;      // x, y, z in screen-space pixel coords
    vec4 bh_params;   // mass, spin, G_eff_ext, _pad
    vec4 _reserved0;
    vec4 _reserved1;
};

// ── Push constants (must match cassi_two_fluid.glsl exactly) ───────────
layout(push_constant, std430) uniform PC {
    float N_f;             // not used in lensing (grid res)
    float dt;              // timestep
    float t;               // elapsed time
    float phi;             // golden ratio
    float xi;              // Cassi Qi coupling
    float eps2;            // softening squared (not used here)
    float particle_N;      // not used here
    float mode;            // visualization mode
    float source_strength; // not used here
    float num_clusters;    // not used here
    float gravity_mode;    // not used here
} pc;

// ── Constants ──────────────────────────────────────────────────────────
const float PI = 3.14159265358979323846;
const float TWO_PI = 6.28318530717958647692;
const float SQRT3 = 1.7320508075688772935;

// ── Smoothstep helper ──────────────────────────────────────────────────
float smooth_ring(float x, float center, float width) {
    float half_w = width * 0.5;
    return 1.0 - smoothstep(0.0, half_w, abs(x - center));
}


// ── Procedural starfield (for when source image is empty) ─────────────
float hash12(vec2 p) {
    p = fract(p * vec2(543.21, 987.65));
    p += dot(p, p + 42.42);
    return fract(p.x * p.y);
}

vec3 starfield(vec2 pixel_pos) {
    // Grid-based pseudo-random starfield
    vec2 cell = floor(pixel_pos * 0.03);
    vec3 stars = vec3(0.0);
    for (int dy = -1; dy <= 1; dy++) {
        for (int dx = -1; dx <= 1; dx++) {
            vec2 n = cell + vec2(float(dx), float(dy));
            float h = hash12(n);
            if (h > 0.97) {
                vec2 star_uv = fract(n * 0.03) - 0.5;
                float d = length(star_uv);
                float bright = 1.0 - smoothstep(0.0, 0.08, d);
                float temp = hash12(n + vec2(100.0));
                vec3 col = mix(vec3(0.7, 0.8, 1.0), vec3(1.0, 0.95, 0.7), temp);
                stars += col * bright * h * 2.0;
            }
        }
    }
    return stars;
}
// ── Main kernel ────────────────────────────────────────────────────────
void main() {
    ivec2 pix = ivec2(gl_GlobalInvocationID.xy);
    ivec2 dims = imageSize(screenImage);
    if (pix.x >= dims.x || pix.y >= dims.y) return;

    // Read BH parameters
    vec3 bh_screen = bh_pos.xyz;
    float M       = bh_params.x;   // mass
    float spin    = bh_params.y;   // spin parameter a/M
    float G_eff   = bh_params.z;   // external G_eff from Qi field

    float xi_val = pc.xi;

    // ── Per-pixel geometry ─────────────────────────────────────────────
    // Pixel position in screen space (fractional coords)
    vec2 pixel_pos = vec2(float(pix.x), float(pix.y));
    vec2 bh_xy = bh_screen.xy;

    // Vector from pixel to BH center in screen space
    vec2 delta = bh_xy - pixel_pos;
    float b_pixel = length(delta);  // impact parameter in pixels

    // Convert to physical units: scale so that M maps to a reasonable
    // pixel radius. Use the screen diagonal as reference.
    float screen_scale = max(float(dims.x), float(dims.y));
    float M_pixels = M * screen_scale * 0.1;  // M in pixel units (tunable)
    if (M_pixels < 1.0) M_pixels = 1.0;       // minimum 1 pixel

    // Impact parameter in physical units (multiples of M_pixels)
    float b = b_pixel / M_pixels;

    // ── Schwarzschild radius and critical impact parameter ─────────────
    float r_s = 2.0 * M_pixels;  // Schwarzschild radius in pixels
    float r_s_phys = 2.0;        // r_s in units of M (= 2M, natural units)

    // GR photon sphere critical impact parameter: b_crit = 3*sqrt(3)*M
    float b_crit_base = 3.0 * SQRT3;  // in units of M
    // Cassi correction: slight enlargement from external G_eff
    float b_crit = b_crit_base * (1.0 + xi_val * G_eff * 0.05);
    float b_crit_pixels = b_crit * M_pixels;

    // ── BH Shadow: pixels within photon sphere are black ───────────────
    if (b_pixel < b_crit_pixels) {
        imageStore(screenImage, pix, vec4(0.0, 0.0, 0.0, 1.0));
        return;
    }

    // ── Gravitational deflection ───────────────────────────────────────
    // Cassi-enhanced deflection angle:
    // where b_phys is the physical impact parameter (in natural units)
    float b_phys = b;  // already in units of M
    float deflection = 2.0 * r_s_phys / b_phys * (1.0 + xi_val * G_eff);

    // Deflection direction: radially toward BH center
    vec2 defl_dir = (b_pixel > 1e-6) ? (delta / b_pixel) : vec2(0.0);

    // Source offset in pixel space: deflect by angle * distance_scale
    // The deflection shifts where we sample the background
    float deflection_scale = M_pixels * 0.5;  // maps angle to pixel offset
    vec2 sample_offset = defl_dir * deflection * deflection_scale;

    // ── Sample the background at the deflected position ────────────────
    vec2 source_uv = pixel_pos + sample_offset;
    ivec2 src_pix = ivec2(clamp(source_uv, vec2(0.0), vec2(dims) - 1.0));
    vec4 source_color = imageLoad(screenImage, src_pix);

    // ── Gravitational redshift ─────────────────────────────────────────
    // redshift factor: sqrt(1 - r_s/r) where r = b (closest approach)
    float r_phys = b;  // in units of M
    float redshift = 1.0;
    if (r_phys > r_s_phys * 0.5 + 0.01) {
        redshift = sqrt(max(1.0 - r_s_phys / r_phys, 0.0));
	}
    // ── Starfield background (when source image is black) ──────────────
    vec4 bg = source_color;
    if (bg.r + bg.g + bg.b < 0.01) {
        bg = vec4(starfield(source_uv + vec2(float(dims.x) * 0.1)), 0.0);
    }
    vec4 lensed_color = bg * redshift;
    // Cassi reduces it; spec says ~10x GR result, so ISCO ~ 3M in units
    // where GR ISCO = 6M, meaning Cassi ISCO = 60M... but spec says
    // "ISCO ~ 10x GR" matching ~3*G*M for the Cassi model).
    // Using Cassi ISCO = 3.0 * G_eff * M_pixels as the ring radius.
    float isco_radius = 3.0 * M_pixels;  // in pixels (Cassi ISCO ~3M)

    // Disk brightness: ring profile peaked at ISCO
    float disk_width = M_pixels * 1.5;  // radial width of the disk
    float disk_profile = smooth_ring(b_pixel, isco_radius, disk_width);

    // Doppler-like beaming: brighter on the approaching side
    // Use BH spin direction to break symmetry
    vec2 spin_dir = normalize(vec2(spin, 0.0) + vec2(1e-6));
    float doppler = 1.0 + 0.3 * dot(normalize(delta + vec2(1e-6)), spin_dir);
    doppler = max(doppler, 0.3);  // clamp

    // Disk color: hot white-orange, modulated by distance
    float temp = isco_radius / max(b_pixel, 1.0);  // hotter closer in
    vec3 disk_color = vec3(1.0, 0.6 + 0.4 * temp, 0.3 + 0.3 * temp) * disk_profile * doppler;

    // Disk emission intensity (fades outside ISCO region)
    float disk_intensity = disk_profile * 0.8;

    // Blend disk emission with lensed background
    // Disk adds to the color (emission, not absorption)
    lensed_color.rgb += disk_color * disk_intensity;

    // ── Einstein ring enhancement ──────────────────────────────────────
    // Near the shadow edge, light piles up (Einstein ring)
    float ring_factor = 1.0;
    float ring_dist = (b_pixel - b_crit_pixels) / M_pixels;
    if (ring_dist < 2.0 && ring_dist > 0.0) {
        // Brightness enhancement falling off from shadow edge
        ring_factor = 1.0 + 2.0 * exp(-ring_dist * 2.0);
    }
    lensed_color.rgb *= ring_factor;

    // ── Output ─────────────────────────────────────────────────────────
    // Clamp to prevent overflow
    lensed_color.rgb = clamp(lensed_color.rgb, vec3(0.0), vec3(100.0));
    lensed_color.a = 1.0;

    imageStore(screenImage, pix, lensed_color);
}
