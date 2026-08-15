shader_type spatial;
render_mode unshaded, cull_front;

// Procedural starfield skybox shader for Godot 4.
// Apply to a large sphere mesh with outward normals (camera inside).
// Uses multi-layer grid-based stars with color temperature variation
// and optional twinkle.

#define PI 3.14159265358979323846
#define TAU 6.28318530717958647692

// Controls star density: 0.1 (sparse) to 3.0 (dense)
uniform float star_density : hint_range(0.1, 3.0) = 1.0;
// Overall brightness multiplier
uniform float star_brightness : hint_range(0.0, 3.0) = 1.0;
// Base star size in UV space
uniform float star_size : hint_range(0.0005, 0.03) = 0.003;
// How much star colors vary: 0 = all white, 1 = full blue-to-yellow range
uniform float color_temp : hint_range(0.0, 1.0) = 0.5;
// Twinkle speed (0 = no twinkle)
uniform float twinkle_speed : hint_range(0.0, 2.0) = 0.0;

// ---- Hash Functions ----

// Returns a decorrelated float from a vec2 seed.
float hash12(vec2 p) {
    p = fract(p * vec2(543.21, 987.65));
    p += dot(p, p + 42.42);
    return fract(p.x * p.y);
}

// Returns a decorrelated vec2 from a vec2 seed.
// Each channel is independently mixed via the cross-product.
vec2 hash21(vec2 p) {
    p = fract(p * vec2(234.34, 435.345));
    p += dot(p, p + 19.19);
    return fract(vec2(p.x * p.y, p.y * p.x));
}

// ---- 2D Value Noise for Background ----

float noise2d(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash12(i);
    float b = hash12(i + vec2(1.0, 0.0));
    float c = hash12(i + vec2(0.0, 1.0));
    float d = hash12(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// ---- Star Layer ----
// Evaluates one layer of stars at the given UV, grid scale, density fraction,
// and size multiplier. Returns combined (color * intensity) as a vec3.

vec3 star_layer(vec2 uv, float scale, float density, float size_mult) {
    vec2 pos = uv * scale;
    vec2 cell = floor(pos);
    vec2 cell_uv = fract(pos) - 0.5;

    vec3 result = vec3(0.0);

    // Check 3x3 cell neighborhood to catch stars straddling cell borders
    for (int y = -1; y <= 1; y++) {
        for (int x = -1; x <= 1; x++) {
            vec2 n = cell + vec2(float(x), float(y));
            vec2 rand = hash21(n);
            vec2 star_pos = rand - 0.5;
            vec2 diff = cell_uv - star_pos;
            float dist = length(diff);

            // Star brightness (luminosity class)
            float star_br = 0.5 + 0.5 * hash12(n + vec2(100.0));
            // Color temperature seed
            float temp = hash12(n + vec2(200.0));

            // Mix between blue-white and yellow-white based on seed and color_temp uniform
            vec3 col = mix(
                vec3(0.65, 0.75, 1.0),   // blue-white (hot)
                vec3(1.0, 0.95, 0.78),   // yellow-white (cool)
                temp * color_temp
            );

            // Star disc with smooth falloff
            float radius = star_size * size_mult * (0.5 + 0.5 * star_br);
            float v = 1.0 - smoothstep(0.0, radius, dist);
            v *= star_br * density;

            result += col * v;
        }
    }

    return result;
}

void fragment() {
    vec3 dir = normalize(NORMAL);

    // Map direction to spherical UV coordinates.
    // Note: atan wraps at -X, creating a seam along one meridian.
    // For a skybox this falls behind the camera so the seam is invisible.
    vec2 uv = vec2(
        atan(dir.z, dir.x) / TAU + 0.5,
        acos(clamp(dir.y, -1.0, 1.0)) / PI
    );

    // Accumulate multiple star layers for a natural starfield distribution.
    // Large bright stars are sparse; tiny dim stars fill the gaps.
    vec3 star_color = vec3(0.0);
    // Layer 1: large bright stars (sparse)
    star_color += star_layer(uv, 60.0, 0.2 * star_density, 3.0);
    // Layer 2: medium stars
    star_color += star_layer(uv, 150.0, 0.4 * star_density, 1.5);
    // Layer 3: small stars (common)
    star_color += star_layer(uv, 400.0, 0.7 * star_density, 1.0);
    // Layer 4: tiny faint stars (very dense)
    star_color += star_layer(uv, 1000.0, 1.0 * star_density, 0.5);

    // Twinkle effect (subtle sinusoidal modulation per star)
    if (twinkle_speed > 0.001) {
        float t = hash12(uv * 754.0) * TAU;
        float phase = TIME * twinkle_speed * (1.0 + hash12(uv * 321.0));
        float twinkle = 0.5 + 0.5 * sin(phase + t);
        twinkle = 0.7 + 0.3 * twinkle;
        star_color *= twinkle;
    }

    // Very faint background with subtle Milky Way noise
    float bg = noise2d(uv * 4.0) * 0.008;
    bg += noise2d(uv * 10.0) * 0.003;
    // Slight reddish-brown tint for the galactic haze
    vec3 bg_color = vec3(bg * 0.6, bg * 0.35, bg * 0.2);

    // Composite final color
    vec3 final_color = bg_color + star_color * star_brightness;

    ALBEDO = final_color;
    EMISSION = final_color;
}
