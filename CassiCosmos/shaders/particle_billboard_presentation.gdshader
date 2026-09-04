shader_type spatial;
// Presentation-only material selected by CassiSim.presentation_profile.
// The compatibility material remains particle_billboard.gdshader.
render_mode blend_add, depth_draw_never, cull_disabled, unshaded, fog_disabled;

uniform float size : hint_range(0.0, 500.0) = 1.5;
// Color-as-LUT contract shared with particle_billboard.gdshader.
uniform sampler2D color_lut : source_color, filter_linear, repeat_disable;
uniform float lut_enabled = 0.0;
uniform vec3 glow_tint : source_color = vec3(0.95, 0.90, 0.98);
uniform float glow_strength = 0.12;

// Presentation controls are supplied by CassiSim and intentionally bounded:
// enough footprint for distant structure, never a close-up billboard takeover.
uniform float min_pixel_radius : hint_range(0.0, 8.0) = 1.60;
uniform float max_pixel_radius : hint_range(1.0, 64.0) = 18.0;
uniform float halo_strength : hint_range(0.0, 3.0) = 0.45;
uniform float emission_strength : hint_range(0.0, 8.0) = 1.75;
uniform float core_radius : hint_range(0.05, 0.95) = 0.30;
// Density-normalized source contribution supplied by CassiSim. Additive,
// no-depth-write compositing keeps stacked layers transmissive and order-free.
uniform float stack_opacity : hint_range(0.0001, 1.0) = 0.35;
// Count-scaled screen-space visibility lift used only after the physical
// billboard falls below a few pixels. The host caps it independently.
uniform float distant_opacity : hint_range(0.0001, 0.1) = 0.04;
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


varying vec2 v_lut; // (u, glow_boost); compatibility depth fade is presentation-inert
varying float v_particle_opacity;

void vertex() {
	// Preserve the production camera-facing billboard convention.
	// VIEW_MATRIX is an orthonormal camera transform; normalizing these axes
	// per vertex only repeats work for every particle quad.
	vec3 cr = vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]);
	vec3 cu = vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]);
	vec3 v = cr * VERTEX.x * size + cu * VERTEX.y * size;

	// Keep physical sizing nearby, then apply a bounded pixel floor at range.
	// viewport_height is supplied by CassiSim because VIEWPORT_SIZE is not
	// reliable in every Godot spatial vertex path on this renderer.
	vec4 center_view = MODELVIEW_MATRIX * vec4(vec3(0.0), 1.0);
	float depth = max(-center_view.z, 1e-4);
	float projection_y = max(abs(PROJECTION_MATRIX[1][1]), 1e-3);
	float world_per_pixel = 2.0 * depth / max(projection_y * viewport_height, 1.0);
	vec3 model_x = MODELVIEW_MATRIX[0].xyz;
	vec3 model_y = MODELVIEW_MATRIX[1].xyz;
	float model_scale = sqrt(max(dot(model_x, model_x), dot(model_y, model_y)));
	float local_half = max(abs(VERTEX.x), abs(VERTEX.y)) * size;
	float physical_half = max(local_half * model_scale, 1e-5);
	float projected_half = physical_half / max(world_per_pixel, 1e-5);
	float target_half = clamp(projected_half, min_pixel_radius, max_pixel_radius) * world_per_pixel;
	float pixel_floor_weight = 1.0 - smoothstep(
			min_pixel_radius, min_pixel_radius * 2.0, projected_half);
	v_particle_opacity = mix(
			stack_opacity, max(stack_opacity, distant_opacity), pixel_floor_weight);
	v *= target_half / physical_half;
	VERTEX = v;

	// Presentation motes remain meaningful beyond the finite camera far plane.
	// Keep x/y projection untouched, but pin only beyond-far depth to the
	// renderer's far clip value. This material never writes depth, so distant
	// layers remain additive rather than occluding nearer structure.
	vec4 clip_position = PROJECTION_MATRIX * MODELVIEW_MATRIX * vec4(VERTEX, 1.0);
	if (clip_position.w > 0.0) {
		float safe_far_z = (CLIP_SPACE_FAR + 1e-5) * clip_position.w;
		clip_position.z = max(clip_position.z, safe_far_z);
	}
	POSITION = clip_position;
	v_lut = INSTANCE_CUSTOM.xy;
}

void fragment() {
	vec3 particle_color;
	if (lut_enabled > 0.5) {
		vec4 lut_color = texture(color_lut, vec2(v_lut.x, 0.5));
		float boost = v_lut.y;
		lut_color.rgb = mix(lut_color.rgb, glow_tint, boost * glow_strength);
		particle_color = presentation_particle_color(v_lut.x, lut_color.rgb);
	} else {
		particle_color = COLOR.rgb;
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

	// Presentation owns visibility: compatibility depth-fade alpha is ignored.
	// The pixel floor keeps distant points resolvable; additive blending and no
	// depth writes keep arbitrarily ordered layers from forming an opaque wall.
	ALBEDO = particle_color * (0.35 + 0.65 * core);
	EMISSION = particle_color * emission_strength * (0.18 + core + halo);
	ALPHA = v_particle_opacity * disc * mix(0.16, 1.0, core);
}
