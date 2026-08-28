shader_type spatial;
// Presentation macro-site LOD billboard — presentation-only, selected by
// CassiSim alongside the particle presentation profile. Consumes the
// per-site record from compute/cassi_presentation_macro_lod.glsl:
//   transform = 3×4 row-major, scale on the diagonal, origin = render-local
//               site position (the optical payload's tile-E convention);
//   custom    = (coherence, opacity, phase01, valid).
// Renders a soft radial HDR mote with a COMPLEMENTARY distance fade: the
// macro layer fades IN with distance (lod_enter → lod_exit), holding the
// far-field structure the particle layer cannot resolve. No physical mass
// claim — size comes from the base_size knob only.
render_mode blend_mix, depth_prepass_alpha, cull_disabled, unshaded;

uniform float color_scheme = 0.0;  // presentation_color_scheme: 0 = Cassi Night, 1 = Spectrum
uniform float lod_enter = 0.0;     // camera distance where the macro layer starts to appear
uniform float lod_exit = 0.0;      // camera distance where it is fully in
uniform float base_size = 1.0;     // global billboard size multiplier (per-site scale rides the transform)

const float CORE_RADIUS = 0.33;
const float HALO_STRENGTH = 0.5;
const float EMISSION_STRENGTH = 2.8;
const float ALPHA_FLOOR = 0.12;

varying vec4 v_custom;  // (coherence, opacity, phase01, valid)
varying float v_depth;  // camera-space depth of the instance origin

vec3 macro_hsl_to_rgb(vec3 c) {
	vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0)
			- 1.0, 0.0, 1.0);
	return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

vec3 macro_palette(vec4 cd) {
	float coh = clamp(cd.x, 0.0, 1.0);
	if (color_scheme > 0.5) {
		// Spectrum: phase drives the full hue wheel (the field's standing /
		// streaming wave orientation); coherence lifts the lightness.
		float hue = mod(cd.z, 1.0);
		float l = 0.14 + 0.34 * coh;
		return macro_hsl_to_rgb(vec3(hue, 0.9, l));
	}
	// Cassi Night: the presentation violet → cyan → pink coherence ramp
	// (the same landmarks as the fused-volume presentation palette).
	float lower_hue = mix(0.72, 0.56, smoothstep(0.0, 0.55, coh));
	float hue = mix(lower_hue, 0.93, smoothstep(0.45, 1.0, coh));
	float l = 0.20 + 0.32 * coh;
	return macro_hsl_to_rgb(vec3(hue, 0.85, l));
}

float macro_distance_fade(float depth) {
	// Complementary fade: 0 up close (lod_enter), 1 past lod_exit. A
	// degenerate or inverted range collapses to a step at lod_enter.
	float lo = max(lod_enter, 0.0);
	float hi = max(lod_exit, lo + 1e-3);
	return smoothstep(lo, hi, depth);
}

void vertex() {
	// Preserve the production camera-facing billboard convention (the same
	// VIEW_MATRIX-row construction as particle_billboard_presentation).
	vec3 cr = normalize(vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]));
	vec3 cu = normalize(vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]));
	vec3 v = cr * VERTEX.x * base_size + cu * VERTEX.y * base_size;
	VERTEX = v;
	v_custom = INSTANCE_CUSTOM;
	vec4 center_view = MODELVIEW_MATRIX * vec4(vec3(0.0), 1.0);
	v_depth = max(-center_view.z, 0.0);
}

void fragment() {
	if (v_custom.w < 0.5) {
		discard;
	}
	// Radial anti-aliased mote: a signed-distance-like falloff keeps the
	// edge stable when a distant site occupies only a few pixels.
	vec2 p = UV * 2.0 - vec2(1.0);
	float r = length(p);
	float aa = max(fwidth(r), 0.002);
	if (r > 1.0 + aa) {
		discard;
	}
	float disc = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, r);
	float core = 1.0 - smoothstep(CORE_RADIUS, min(CORE_RADIUS + 0.32, 0.98), r);
	float halo = pow(clamp(1.0 - r, 0.0, 1.0), 1.8) * HALO_STRENGTH;

	vec4 cd = v_custom;
	float coh = clamp(cd.x, 0.0, 1.0);
	// sigma = opacity · (0.25 + 0.75·coh) — the volume renderer's density
	// convention (cassi_voronoi_fused_volume.glsl); the floor keeps faint
	// sites readable as distant haze.
	float sigma = max(cd.y, 0.0) * (0.25 + 0.75 * coh);
	float vis = clamp(sigma, 0.0, 1.0);
	float fade = macro_distance_fade(v_depth);

	vec3 rgb = macro_palette(cd);
	ALBEDO = rgb * (0.35 + 0.65 * core);
	EMISSION = rgb * EMISSION_STRENGTH * (0.15 + core + halo) * fade;
	ALPHA = disc * mix(ALPHA_FLOOR, 1.0, vis) * fade;
}
