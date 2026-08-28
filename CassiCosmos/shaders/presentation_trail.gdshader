shader_type spatial;
// ═══════════════════════════════════════════════════════════════════════
// CASSI PRESENTATION VELOCITY TRAIL — the material side of the
// instantaneous-velocity ribbon layer (compute/cassi_presentation_trails.glsl).
// Consumes the 3x4 transform + custom record that shader writes:
//   custom_data = (u, normalized_speed, fade, valid)
//     u               head fraction along the streak (0 tail → 1 head); the
//                     length taper peaks here (u = 0.5 → centered
//                     long-exposure streak with the particle billboard at
//                     its center)
//     normalized_speed  → color/lightness axis
//     fade            → streak exposure (α multiplier: short slow streaks
//                     are faint, fully exposed fast ones are strong)
//     valid           → 0 on ineligible slots (discarded here)
// The ribbon is a tapered, soft-edged, camera-readable quad: length along
// the streak axis (baked into the instance transform), width across the
// broad camera-facing face, HDR emission deliberately below the particle
// billboards — the velocity layer is dimmer by design. Always paired with a
// unit QuadMesh (any flat quad whose UV spans [0,1]²) in a MultiMesh.
// ═══════════════════════════════════════════════════════════════════════
render_mode blend_mix, cull_disabled, unshaded, depth_draw_never;

// color_scheme: 0 = Cassi Night (the violet/blue/cyan/pink presentation
// palette — mirrors particle_billboard_presentation.gdshader); 1 = Spectrum
// (full-hue speed rainbow). Same integer contract as presentation_color_scheme.
uniform float color_scheme : hint_range(0.0, 1.0, 1.0) = 0.0;

uniform float emission_strength : hint_range(0.0, 4.0) = 0.85;
uniform float alpha_scale : hint_range(0.0, 1.0) = 0.55;
uniform float width_softness : hint_range(0.0, 1.0) = 0.5;
uniform float taper_power : hint_range(0.25, 4.0) = 1.5;
// Distant ribbons dissolve against the field; the defaults are subtle at the
// default framing (camera orbits at ≈ the spawn radius) and only fade the
// far end of a zoomed-out view.
uniform float depth_fade_near : hint_range(0.0, 4000.0) = 200.0;
uniform float depth_fade_far : hint_range(0.0, 16000.0) = 2000.0;

varying vec4 v_trail;    // (u, normalized_speed, fade, valid)
varying float v_depth;   // view-space distance of the streak center

vec3 trail_hsl_to_rgb(float h, float s, float l) {
	vec3 rgb = clamp(abs(mod(h * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0)
			- 1.0, 0.0, 1.0);
	return l + s * (rgb - 0.5) * (1.0 - abs(2.0 * l - 1.0));
}

void vertex() {
	v_trail = INSTANCE_CUSTOM;
	// True camera distance of the streak center (the material owns the
	// camera here — the compute pass does not), for the far dissolve.
	vec4 center_view = MODELVIEW_MATRIX * vec4(vec3(0.0), 1.0);
	v_depth = max(-center_view.z, 0.0);
}

void fragment() {
	vec4 cd = v_trail;
	if (cd.w < 0.5) {
		discard;   // ineligible slot — the compute pass wrote an all-zero record
	}
	float u = clamp(cd.x, 0.0, 1.0);
	float ns = clamp(cd.y, 0.0, 1.0);
	float exposure = clamp(cd.z, 0.0, 1.0);

	// Quad-local coordinates: p.x across the width, p.y along the streak.
	vec2 p = UV * 2.0 - vec2(1.0);

	// Tapered radial softness: smooth falloff across the ribbon face…
	float edge = 1.0 - smoothstep(0.0, 1.0, abs(p.x));
	float width_profile = pow(max(edge, 0.0), 1.0 + width_softness);

	// …and a length taper peaking at the head fraction u (u = 0.5 →
	// centered streak, fading to both ends). The profile is symmetric in
	// both axes, so the exact UV orientation of the host quad mesh cannot
	// flip the look.
	float t = clamp(p.y * 0.5 + 0.5, 0.0, 1.0);
	float d = abs(t - u) / max(max(u, 1.0 - u), 1e-4);
	float taper = pow(clamp(1.0 - d, 0.0, 1.0), taper_power);

	// Palette: speed-keyed Cassi Night (presentation violet/blue/cyan/pink)
	// or Spectrum (full hue wheel, no seam at the red wrap).
	vec3 col;
	if (color_scheme > 0.5) {
		float hue = fract(0.72 + ns * 0.85);
		col = trail_hsl_to_rgb(hue, 0.85, 0.42 + 0.30 * ns);
	} else {
		float hue = mix(0.72, 0.56, smoothstep(0.0, 0.55, ns));
		hue = mix(hue, 0.93, smoothstep(0.45, 1.0, ns));
		col = trail_hsl_to_rgb(hue, 1.0, mix(0.26, 0.52, smoothstep(0.0, 1.0, ns)));
	}

	// Far dissolve (center depth from the vertex stage).
	float depth_fade = clamp((depth_fade_far - v_depth)
			/ max(depth_fade_far - depth_fade_near, 1e-4), 0.0, 1.0);

	float profile = width_profile * taper * exposure * depth_fade;
	if (profile < 0.004) {
		discard;   // fully transparent fringe — skip the blend
	}
	float intensity = 0.45 + 0.55 * ns;   // faster streaks read brighter

	ALBEDO = col * (0.30 + 0.70 * profile * intensity);
	EMISSION = col * emission_strength * profile * intensity;
	ALPHA = alpha_scale * profile * mix(0.55, 1.0, ns);
}
