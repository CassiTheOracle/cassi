shader_type spatial;
// Observatory/Cinematic additive radiance billboard. Scientific keeps the
// compatibility material untouched. Radiance is already attenuated at this
// particle's own depth and is added by the post compositor exactly once.
render_mode blend_add, depth_draw_never, cull_disabled, unshaded, fog_disabled;

uniform float size : hint_range(0.0, 500.0) = 1.0;
uniform sampler2D compact_data : filter_nearest, repeat_disable;
uniform float compact_mode = 0.0;
uniform float compact_tex_width = 4096.0;
uniform sampler3D optical_depth_texture : filter_linear, repeat_disable;
uniform sampler2D motion_texture : filter_nearest, repeat_disable;
uniform float motion_tex_width = 4096.0;
uniform float viewport_height : hint_range(1.0, 16384.0) = 720.0;
uniform float optical_near = 0.1;
uniform float optical_far = 1000000.0;
// World distance where the ordered layer begins fading out. Zero disables the
// fade entirely (the unbounded view stays bit-identical); the observatory sets
// it only while a view depth is active.
uniform float depth_fade_start = 0.0;
// Main supplies 1/reference_mass. Together with motion.w this is the
// dimensionless mass fraction used by the projected flux budget.
uniform float luminosity_scale = 1.0;
uniform float point_fraction : hint_range(0.0, 1.0) = 0.65;
uniform float emission_strength : hint_range(0.0, 16.0) = 1.0;
uniform float shutter_seconds : hint_range(0.0, 2.0) = 0.0;
uniform float velocity_time_scale = 1.0;
uniform float reference_radius = 1.0;
uniform vec3 optical_bounds_min = vec3(-1e20);
uniform vec3 optical_bounds_max = vec3(1e20);

// Explicitly naturalistic warm point spectrum. No temperature or coherence is
// interpreted as a physical black-body temperature.
const vec3 POINT_SPECTRUM = vec3(1.0, 0.67, 0.35);
const float INV_TWO_PI = 0.15915494309189535;
const float TRUNCATED_GAUSSIAN_MASS = 0.9888910034617577;
const float EPS = 1e-6;

varying flat float v_depth;
varying flat float v_mass;
varying flat float v_ray_distance;
varying flat vec2 v_sigma_px;
varying flat float v_flux;

vec4 motion_for_instance(int texel) {
	int width = max(int(motion_tex_width + 0.5), 1);
	return texelFetch(motion_texture,
		ivec2(texel % width, texel / width), 0);
}

void vertex() {
	vec3 origin = vec3(0.0);
	vec3 render_position = MODEL_MATRIX[3].xyz;
	if (compact_mode > 0.5) {
		int width = max(int(compact_tex_width + 0.5), 1);
		int texel = int(INSTANCE_ID) * 2;
		vec4 placement = texelFetch(compact_data,
			ivec2(texel % width, texel / width), 0);
		// Compact placement replaces rather than compounds the retained
		// MultiMesh transform. The second compact texel is intentionally not
		// interpreted as physical color; it carries the legacy custom payload.
		mat4 compact_transform = mat4(
			vec4(placement.w, 0.0, 0.0, 0.0),
			vec4(0.0, placement.w, 0.0, 0.0),
			vec4(0.0, 0.0, placement.w, 0.0),
			vec4(placement.xyz, 1.0));
		MODELVIEW_MATRIX = VIEW_MATRIX * compact_transform;
		MODELVIEW_NORMAL_MATRIX = mat3(VIEW_MATRIX);
		render_position = placement.xyz;
	} else {
		// Writing MODELVIEW_MATRIX makes the shader responsible for both paths.
		MODELVIEW_MATRIX = VIEW_MATRIX * MODEL_MATRIX;
		MODELVIEW_NORMAL_MATRIX = mat3(MODELVIEW_MATRIX);
	}

	vec4 motion = motion_for_instance(int(INSTANCE_ID));
	float motion_finite = (!(isnan(motion.w) || isinf(motion.w))) ? 1.0 : 0.0;
	float mass = motion_finite > 0.5 ? max(motion.w, 0.0) : 0.0;
	vec4 center_view = MODELVIEW_MATRIX * vec4(origin, 1.0);
	float depth = max(-center_view.z, 0.0);
	float projection_y = max(abs(PROJECTION_MATRIX[1][1]), 1e-3);
	float world_per_pixel = 2.0 * max(depth, EPS)
		/ max(projection_y * max(viewport_height, 1.0), 1.0);
	float physical_sigma_px = abs(size) * max(abs(VERTEX.x), abs(VERTEX.y))
		* max(length(MODELVIEW_MATRIX[0].xyz), length(MODELVIEW_MATRIX[1].xyz))
		/ max(3.0 * world_per_pixel, EPS);
	// A finite subpixel floor stabilizes sampling but never boosts flux: the
	// same normalized PSF denominator accounts for its area.
	float sigma = clamp(sqrt(0.55 * 0.55 + physical_sigma_px * physical_sigma_px),
		0.55, 256.0);

	vec3 view_velocity = (VIEW_MATRIX * vec4(motion.xyz, 0.0)).xyz;
	vec2 projected_velocity = (view_velocity.xy
		+ center_view.xy * view_velocity.z / max(depth, EPS))
		/ max(world_per_pixel, EPS) * shutter_seconds * velocity_time_scale;
	float motion_px = length(projected_velocity);
	vec2 velocity_axis = motion_px > EPS
		? projected_velocity / motion_px : vec2(1.0, 0.0);
	float sigma_major = clamp(sqrt(sigma * sigma
		+ motion_px * motion_px / 12.0), 0.55, 256.0);
	float sigma_minor = sigma;

	// Build the three-sigma support directly in view space. This avoids
	// compounding MODELVIEW scale and keeps compact/standard transforms equal.
	vec2 p = UV * 2.0 - vec2(1.0);
	vec2 perpendicular = vec2(-velocity_axis.y, velocity_axis.x);
	vec2 offset_px = (velocity_axis * p.x * sigma_major
		+ perpendicular * p.y * sigma_minor) * 3.0;
	vec3 expanded_view = center_view.xyz
		+ vec3(offset_px * world_per_pixel, 0.0);
	POSITION = PROJECTION_MATRIX * vec4(expanded_view, 1.0);

	v_depth = depth;
	v_ray_distance = length(center_view.xyz);
	v_mass = mass;
	v_sigma_px = vec2(sigma_major, sigma_minor);
	float pixel_solid_angle = pow(2.0
		/ max(projection_y * max(viewport_height, 1.0), 1.0), 2.0);
	// Projected inverse-square flux. luminosity_scale normalizes the frozen
	// initial mass, reference_radius sets the initial support scale, and the
	// Gaussian denominator below preserves integrated projected flux.
	float mass_fraction = mass * max(luminosity_scale, 0.0);
	bool inside_volume = all(greaterThanEqual(render_position, optical_bounds_min))
		&& all(lessThanEqual(render_position, optical_bounds_max));
	float resolved_fraction = inside_volume ? clamp(point_fraction, 0.0, 1.0) : 1.0;
	v_flux = mass_fraction * max(reference_radius, 0.0)
		* max(reference_radius, 0.0) / max(depth * depth * pixel_solid_angle, EPS)
		* resolved_fraction * max(emission_strength, 0.0);
}

void fragment() {
	if (!(v_mass > 0.0) || !(v_depth > max(optical_near, EPS))
		|| !(v_ray_distance > max(optical_near, EPS))
		|| !(v_flux > 0.0) || isnan(v_depth) || isinf(v_depth)
		|| isnan(v_ray_distance) || isinf(v_ray_distance)) {
		discard;
	}
	vec2 p = UV * 2.0 - vec2(1.0);
	float edge_radius = length(p);
	float aa = max(fwidth(p.x), fwidth(p.y));
	if (edge_radius > 1.0 + aa) {
		discard;
	}
	vec2 sigma = max(v_sigma_px, vec2(0.55));
	// The vertex support is already rotated and stretched. UV is in that
	// principal-axis frame; rotating it again would change integrated flux.
	vec2 q = p * 3.0;
	float gaussian = exp(-0.5 * dot(q, q)) * INV_TWO_PI
		/ max(sigma.x * sigma.y * TRUNCATED_GAUSSIAN_MASS, 1e-4);
	float edge = 1.0 - smoothstep(0.98, 1.0 + max(aa, 0.002), edge_radius);
	if (edge <= 0.0) {
		discard;
	}

	float log_span = max(log(max(optical_far, optical_near + EPS)
		/ max(optical_near, EPS)), EPS);
	float log_depth = clamp(log(max(v_ray_distance, optical_near)
		/ max(optical_near, EPS)) / log_span, 0.0, 1.0);
	float tau = texture(optical_depth_texture,
		vec3(clamp(SCREEN_UV, vec2(0.0), vec2(1.0)), log_depth)).r;
	if (isnan(tau) || isinf(tau)) {
		tau = 0.0;
	}
	float transmission = exp(-max(tau, 0.0));
	// Optional view depth: the outer part of the ordered window fades to zero,
	// so a bounded depth reads as a soft edge instead of a hard pop.
	float depth_fade = 1.0;
	if (depth_fade_start > 0.0) {
		depth_fade = 1.0 - smoothstep(depth_fade_start,
			max(optical_far, depth_fade_start + EPS), v_ray_distance);
		if (depth_fade <= 0.0) {
			discard;
		}
	}
	vec3 radiance = POINT_SPECTRUM
		* (v_flux * gaussian * transmission * edge * depth_fade);
	// Forward+ unshaded outputs ALBEDO as HDR radiance; EMISSION is ignored.
	// Alpha never participates in a second attenuation operation.
	ALBEDO = radiance;
	ALPHA = 1.0;
}
