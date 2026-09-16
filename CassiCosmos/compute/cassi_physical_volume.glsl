#[compute]
#version 450

// Read-only camera formal solution through the live conditional H/H+ material.
// The physics engine owns every input buffer; this observer writes only its
// private HDR/XYZ/depth targets.
layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;

layout(set = 0, binding = 0, rgba32f) uniform writeonly image2D display_radiance;
layout(set = 0, binding = 1, rgba32f) uniform writeonly image2D raw_xyz;
layout(set = 0, binding = 2, r32f) uniform writeonly image2D first_depth;
// One state-coherent packed record per cell and camera-visible group:
// xyz = opacity, emission, exact Lebedev mean; w = electron population.
layout(set = 0, binding = 7, std430) readonly buffer VisibleSource {
    vec4 visible_source[];
};
layout(set = 0, binding = 5, std430) readonly buffer VisibleGroups {
    vec4 visible_group[];
};

layout(push_constant, std430) uniform PhysicalCameraPC {
    vec3 camera_origin; float fov_y;
    vec3 camera_right; float out_width;
    vec3 camera_up; float out_height;
    vec3 camera_forward; float optical_near;
    vec3 volume_center; float thomson_per_population;
    vec3 volume_extents; float group_count;
    vec3 grid_dimensions; float march_steps;
    float optical_scale; float emission_scale; float visible_group_count; float c_reduced_sim;
} pc;

const float FOUR_PI = 12.566370614359172;
const int MAX_VISIBLE_GROUPS = 16;

bool finite1(float x) { return !(isnan(x) || isinf(x)); }
bool finite3(vec3 x) { return all(not(isnan(x))) && all(not(isinf(x))); }

vec3 ray_direction(vec2 ndc) {
    float aspect = max(pc.out_width, 1.0) / max(pc.out_height, 1.0);
    float tangent = tan(0.5 * max(pc.fov_y, 0.001));
    return normalize(pc.camera_forward
        + pc.camera_right * (ndc.x * aspect * tangent)
        + pc.camera_up * (ndc.y * tangent));
}

float safe_inverse(float value) {
    if (abs(value) > 1.0e-8) return 1.0 / value;
    return value < 0.0 ? -1.0e8 : 1.0e8;
}

vec3 physical_cell_spacing() {
    vec3 grid = max(round(pc.grid_dimensions), vec3(1.0));
    return max(2.0 * pc.volume_extents / grid, vec3(1.0e-8));
}

float physical_support_radius() {
    // Three quarters of the physical cell diagonal covers cell corners and,
    // for the production φ:1:φ² spacing, has no support beyond ±2 cells.
    return 0.75 * length(physical_cell_spacing());
}


vec2 box_interval(vec3 origin, vec3 direction) {
    // Expand by one radial-kernel support so boundary cells fade as spheres
    // instead of being clipped against the rectangular compute domain.
    vec3 padding = vec3(physical_support_radius());
    vec3 bounds_min = pc.volume_center - pc.volume_extents - padding;
    vec3 bounds_max = pc.volume_center + pc.volume_extents + padding;
    vec3 inverse = vec3(safe_inverse(direction.x), safe_inverse(direction.y),
        safe_inverse(direction.z));
    vec3 a = (bounds_min - origin) * inverse;
    vec3 b = (bounds_max - origin) * inverse;
    vec3 lo = min(a, b);
    vec3 hi = max(a, b);
    return vec2(max(lo.x, max(lo.y, lo.z)), min(hi.x, min(hi.y, hi.z)));
}


// Small-tau switch for the formal solution.  The spectral observer
// (cassi_spectral_volume.glsl) carries a copy of this helper WITHOUT the
// min(tau, 80.0) clamp, so the two observers legitimately differ for tau > 80;
// this shader keeps the clamp because its extinction comes from the same
// conditional-hydrogen tables as the ray march below.  Unifying the two copies
// would change the spectral observer's large-tau output and is a deliberate
// decision, not a cleanup.
const float SMALL_TAU_LIMIT = 1.0e-4;
float one_minus_exp_negative(float tau) {
    if (tau < SMALL_TAU_LIMIT) return tau * (1.0 - 0.5 * tau + tau * tau / 6.0);
    return 1.0 - exp(-min(tau, 80.0));
}

// Compact, nonnegative C2 radial basis in world space. Every cell contributes
// through spherical support; there are no tensor-product faces whose level
// sets can expose the Cartesian storage lattice as colored rectangles.
float isotropic_cell_weight(float distance_world, float support_radius) {
    float q = distance_world / max(support_radius, 1.0e-20);
    if (q >= 1.0) return 0.0;
    float one_minus_q = 1.0 - q;
    float square = one_minus_q * one_minus_q;
    return square * square * (1.0 + 4.0 * q);
}

vec3 xyz_to_linear_srgb(vec3 xyz) {
    return mat3(
         3.2406, -0.9689,  0.0557,
        -1.5372,  1.8758, -0.2040,
        -0.4986,  0.0415,  1.0570
    ) * xyz;
}

void main() {
    ivec2 pixel = ivec2(gl_GlobalInvocationID.xy);
    ivec2 dimensions_out = imageSize(display_radiance);
    if (pixel.x >= dimensions_out.x || pixel.y >= dimensions_out.y
            || dimensions_out.x <= 0 || dimensions_out.y <= 0) return;

    vec2 uv = (vec2(pixel) + vec2(0.5)) / vec2(dimensions_out);
    vec2 ndc = vec2(uv.x * 2.0 - 1.0, 1.0 - uv.y * 2.0);
    vec3 direction = ray_direction(ndc);
    vec2 interval = box_interval(pc.camera_origin, direction);
    float begin = max(interval.x, max(pc.optical_near, 0.0));
    float end = interval.y;
    if (!(end > begin) || !finite1(begin) || !finite1(end)) {
        imageStore(display_radiance, pixel, vec4(0.0));
        imageStore(raw_xyz, pixel, vec4(0.0, 0.0, 0.0, 1.0));
        imageStore(first_depth, pixel, vec4(0.0));
        return;
    }

    uvec3 grid = uvec3(max(round(pc.grid_dimensions), vec3(1.0)));
    int visible = clamp(int(round(pc.visible_group_count)), 0, MAX_VISIBLE_GROUPS);
    int steps = clamp(int(round(pc.march_steps)), 1, 192);
    float ds = (end - begin) / float(steps);
    float intensity[MAX_VISIBLE_GROUPS];
    float throughput[MAX_VISIBLE_GROUPS];
    vec3 material_integral[MAX_VISIBLE_GROUPS];
    for (int group = 0; group < MAX_VISIBLE_GROUPS; ++group) {
        intensity[group] = 0.0;
        throughput[group] = 1.0;
        material_integral[group] = vec3(0.0);
    }
    float nearest_signal_depth = 0.0;

    // Integrate from the far boundary toward the camera. The expensive
    // angle/group reduction is packed once per physical-state update. Here,
    // each radial neighbor is visited once and only positive-weight cells
    // fetch packed material; zero-weight cells never touch global buffers.
    vec3 lower = pc.volume_center - pc.volume_extents;
    vec3 span = max(2.0 * pc.volume_extents, vec3(1.0e-8));
    vec3 cell_spacing = physical_cell_spacing();
    float support_radius = physical_support_radius();
    float support_squared = support_radius * support_radius;
    for (int sample_index = 0; sample_index < steps; ++sample_index) {
        float distance = end - (float(sample_index) + 0.5) * ds;
        vec3 position = pc.camera_origin + direction * distance;
        vec3 normalized = (position - lower) / span;
        vec3 grid_position = normalized * vec3(grid) - vec3(0.5);
        ivec3 nearest = ivec3(floor(grid_position + vec3(0.5)));
        vec3 nearest_center = lower
            + (vec3(nearest) + vec3(0.5)) * cell_spacing;
        vec3 center_delta = position - nearest_center;
        float stencil_weight_sum = 0.0;
        float electron_integral = 0.0;
        for (int group = 0; group < visible; ++group)
            material_integral[group] = vec3(0.0);
        for (int z = -2; z <= 2; ++z) {
            for (int y = -2; y <= 2; ++y) {
                for (int x = -2; x <= 2; ++x) {
                    ivec3 offset = ivec3(x, y, z);
                    vec3 displacement = center_delta
                        - vec3(offset) * cell_spacing;
                    float distance_squared = dot(displacement, displacement);
                    if (distance_squared >= support_squared) continue;
                    float weight = isotropic_cell_weight(
                        sqrt(distance_squared), support_radius);
                    stencil_weight_sum += weight;
                    ivec3 coordinate = nearest + offset;
                    bool inside = all(greaterThanEqual(coordinate, ivec3(0)))
                        && all(lessThan(coordinate, ivec3(grid)));
                    if (!inside) continue;
                    uint cell = uint(coordinate.x) + grid.x
                        * (uint(coordinate.y) + grid.y * uint(coordinate.z));
                    if (visible > 0)
                        electron_integral += weight
                            * visible_source[cell * uint(visible)].w;
                    for (int visible_index = 0;
                            visible_index < visible; ++visible_index) {
                        material_integral[visible_index] += weight
                            * visible_source[cell * uint(visible)
                                + uint(visible_index)].xyz;
                    }
                }
            }
        }
        float inverse_stencil_weight =
            1.0 / max(stencil_weight_sum, 1.0e-20);
        float electron_population = max(
            electron_integral * inverse_stencil_weight, 0.0);
        float scattering_full = electron_population
            * max(pc.thomson_per_population, 0.0);
        if (!finite1(scattering_full)) scattering_full = 0.0;
        bool cell_signal = false;
        for (int visible_index = 0; visible_index < visible; ++visible_index) {
            vec3 material = max(
                material_integral[visible_index] * inverse_stencil_weight,
                vec3(0.0));
            float tabulated_extinction = material.x;
            float tabulated_emission = material.y;
            float tabulated_mean_intensity = material.z;
            float absorption = max(tabulated_extinction - scattering_full, 0.0);
            float extinction = (absorption + scattering_full)
                * max(pc.optical_scale, 0.0);
            float true_source = tabulated_emission
                * max(pc.emission_scale, 0.0)
                / (FOUR_PI * max(pc.c_reduced_sim, 1.0e-20));
            float scatter_source = scattering_full * max(pc.optical_scale, 0.0)
                * tabulated_mean_intensity;
            if (!finite1(extinction) || !finite1(true_source)
                    || !finite1(scatter_source)) continue;
            float tau = extinction * ds;
            float transmission = exp(-min(tau, 80.0));
            float source_per_length = true_source + scatter_source;
            float emitted = extinction > 1.0e-30
                ? (source_per_length / extinction) * one_minus_exp_negative(tau)
                : source_per_length * ds;
            intensity[visible_index] =
                intensity[visible_index] * transmission + emitted;
            throughput[visible_index] *= transmission;
            cell_signal = cell_signal
                || extinction > 0.0 || source_per_length > 0.0;
        }
        if (cell_signal) nearest_signal_depth = distance;
    }

    vec3 xyz = vec3(0.0);
    float weighted_transmission = 0.0;
    float transmission_weight = 0.0;
    for (int visible_index = 0; visible_index < visible; ++visible_index) {
        vec3 observer = max(visible_group[visible_index].xyz, vec3(0.0));
        xyz += intensity[visible_index] * observer;
        float weight = max(observer.y, 0.0);
        weighted_transmission += clamp(throughput[visible_index], 0.0, 1.0)
            * weight;
        transmission_weight += weight;
    }
    if (!finite3(xyz) || any(lessThan(xyz, vec3(0.0)))) xyz = vec3(0.0);
    float residual_transmission = transmission_weight > 1.0e-20
        ? weighted_transmission / transmission_weight : 1.0;
    if (!finite1(residual_transmission)) residual_transmission = 1.0;
    float opacity_alpha = 1.0 - clamp(residual_transmission, 0.0, 1.0);
    vec3 linear_rgb = max(xyz_to_linear_srgb(xyz), vec3(0.0));
    if (!finite3(linear_rgb)) linear_rgb = vec3(0.0);
    imageStore(display_radiance, pixel, vec4(linear_rgb, opacity_alpha));
    imageStore(raw_xyz, pixel, vec4(xyz, 1.0));
    imageStore(first_depth, pixel, vec4(nearest_signal_depth, 0.0, 0.0, 0.0));
}
