shader_type spatial;
// Presentation-only material selected by CassiSim.presentation_profile.
// The compatibility material remains particle_billboard.gdshader.
render_mode blend_mix, depth_prepass_alpha, cull_disabled, unshaded;

uniform float size : hint_range(0.0, 500.0) = 1.5;
// Color-as-LUT contract shared with particle_billboard.gdshader.
uniform sampler2D color_lut : source_color, filter_linear, repeat_disable;
uniform float lut_enabled = 0.0;
uniform vec3 glow_tint : source_color = vec3(0.95, 0.90, 0.98);
uniform float glow_strength = 0.12;
const float GLOW_A_MIN = 0.35;
const float GLOW_A_MAX = 1.0;

// Presentation controls are supplied by CassiSim and intentionally bounded:
// enough footprint for distant structure, never a close-up billboard takeover.
uniform float min_pixel_radius : hint_range(0.0, 8.0) = 1.60;
uniform float max_pixel_radius : hint_range(1.0, 64.0) = 18.0;
uniform float halo_strength : hint_range(0.0, 3.0) = 0.45;
uniform float emission_strength : hint_range(0.0, 8.0) = 1.75;
uniform float core_radius : hint_range(0.05, 0.95) = 0.30;
uniform float viewport_height : hint_range(1.0, 8192.0) = 720.0;
// 0 = Cassi Night (the original presentation palette); 1 = Spectrum, which
// retains the currently selected particle Color source/LUT mapping.
uniform float color_scheme : hint_range(0.0, 1.0, 1.0) = 0.0;
vec3 presentation_hsl_to_rgb(float h, float l) {
	vec3 rgb = clamp(abs(mod(h * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0)
			- 1.0, 0.0, 1.0);
	float f = 1.0 - abs(2.0 * l - 1.0);
	return vec3(l) + (rgb - 0.5) * f;
}

vec3 presentation_particle_color(float u, vec3 source) {
	if (color_scheme > 0.5) {
		return source;
	}
	float source_luma = max(dot(source, vec3(0.2126, 0.7152, 0.0722)), 0.2);
	float expanded_u = pow(clamp(u, 0.0, 1.0), 0.35);
	float t = clamp(0.50 * expanded_u + 0.50 * source_luma, 0.0, 1.0);
	float hue = mix(0.72, 0.56, smoothstep(0.0, 0.55, t));
	hue = mix(hue, 0.93, smoothstep(0.45, 1.0, t));
	float lightness = mix(0.30, 0.58, smoothstep(0.0, 1.0, t));
	vec3 palette = presentation_hsl_to_rgb(hue, lightness);
	return palette * (0.55 + 0.75 * source_luma);
}


varying vec3 v_lut_vfx; // (u, glow_boost, depth_fade)

void vertex() {
	// Preserve the production camera-facing billboard convention.
	vec3 cr = normalize(vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]));
	vec3 cu = normalize(vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]));
	vec3 v = cr * VERTEX.x * size + cu * VERTEX.y * size;

	// Keep physical sizing nearby, then apply a bounded pixel floor at range.
	// viewport_height is supplied by CassiSim because VIEWPORT_SIZE is not
	// reliable in every Godot spatial vertex path on this renderer.
	vec4 center_view = MODELVIEW_MATRIX * vec4(vec3(0.0), 1.0);
	float depth = max(-center_view.z, 1e-4);
	float projection_y = max(abs(PROJECTION_MATRIX[1][1]), 1e-3);
	float world_per_pixel = 2.0 * depth / max(projection_y * viewport_height, 1.0);
	float model_scale = max(length(MODELVIEW_MATRIX[0].xyz), length(MODELVIEW_MATRIX[1].xyz));
	float local_half = max(abs(VERTEX.x), abs(VERTEX.y)) * size;
	float physical_half = max(local_half * model_scale, 1e-5);
	float projected_half = physical_half / max(world_per_pixel, 1e-5);
	float target_half = clamp(projected_half, min_pixel_radius, max_pixel_radius) * world_per_pixel;
	v *= target_half / physical_half;
	VERTEX = v;
	v_lut_vfx = vec3(INSTANCE_CUSTOM.x, INSTANCE_CUSTOM.y, INSTANCE_CUSTOM.z);
}

void fragment() {
	vec4 c;
	if (lut_enabled > 0.5) {
		c = texture(color_lut, vec2(v_lut_vfx.x, 0.5));
		float boost = v_lut_vfx.y;
		float fade = v_lut_vfx.z;
		c.a *= fade * mix(GLOW_A_MIN, GLOW_A_MAX, boost);
		c.rgb = mix(c.rgb, glow_tint, boost * glow_strength);
		c.rgb = presentation_particle_color(v_lut_vfx.x, c.rgb);
	} else {
		c = COLOR;
	}

	// A signed-distance-like radial mote replaces the flat square QuadMesh.
	// fwidth keeps the edge stable when a distant particle occupies only a few
	// pixels, while discard avoids shading the fully transparent corners.
	vec2 p = UV * 2.0 - vec2(1.0);
	float r = length(p);
	float aa = max(fwidth(r), 0.002);
	if (r > 1.0 + aa) {
		discard;
	}
	float disc = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, r);
	float core = 1.0 - smoothstep(core_radius, min(core_radius + 0.32, 0.98), r);
	float halo = pow(clamp(1.0 - r, 0.0, 1.0), 1.8) * halo_strength;

	ALBEDO = c.rgb * (0.35 + 0.65 * core);
	EMISSION = c.rgb * emission_strength * (0.18 + core + halo);
	ALPHA = c.a * disc * mix(0.16, 1.0, core);
}
