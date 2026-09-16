shader_type spatial;
// ═══════════════════════════════════════════════════════════════════════
// CASSI QI-FLOW SITE FIELD — the material side of the low-opacity site-field
// reconstruction layer (compute/cassi_qi_flow.glsl, mode 3).
//
// One camera-facing soft splat per AUTHORITATIVE site — no coherence
// shortlist, no q threshold, no low-q core censoring. Every site the solver
// owns gets a record; weak regions simply fade toward the alpha floor.
//
//   row0/row1 = the instance scale (fraction of the mean site spacing,
//               sqrt(c2) — compact overlapping soft supports, never a cube
//               and never a wall)
//   row3 = custom = (value, magnitude, 0, valid)
//     scalar_mode 0  coherence q          value ∈ [0,1]
//     scalar_mode 1  signed imbalance     value ∈ [-1,1] (clearly signed)
//     scalar_mode 2  field amplitude      value ∈ [0,1] (compressive)
//     magnitude is |value| and drives alpha; the alpha FLOOR below is what
//     keeps the shells readable where the field is weak.
// ═══════════════════════════════════════════════════════════════════════
render_mode blend_mix, cull_disabled, unshaded, depth_draw_never;
#include "res://shaders/qi_flow_view.gdshaderinc"

uniform float scalar_mode = 0.0;             // 0 q, 1 signed imbalance, 2 amplitude
uniform float size_scale : hint_range(0.1, 3.0) = 1.0;
uniform float opacity_scale : hint_range(0.0, 1.0) = 0.06;
uniform float alpha_floor : hint_range(0.0, 1.0) = 0.30;
uniform float emission_strength : hint_range(0.0, 4.0) = 0.25;
uniform float gain : hint_range(0.1, 4.0) = 1.0;

// Camera-relative cutaway (shared across field / current / source layers).
uniform float cut_enabled = 0.0;
uniform vec3 cut_center = vec3(0.0);
uniform vec3 cut_normal = vec3(0.0, 0.0, -1.0);
uniform float cut_threshold = 0.0;

varying vec4 v_custom;
varying vec3 v_world;

// Fixed, bounded palettes — deliberately NOT a free hue ramp, so a value
// always reads the same color.
//   q         : deep blue → cyan → white
//   imbalance : teal (−) ← dark neutral → warm gold (+)
//   amplitude : dark violet → violet → gold
vec3 qi_flow_palette(float value, float magnitude, float mode) {
	if (mode < 0.5) {
		float t = clamp(value, 0.0, 1.0);
		vec3 low = vec3(0.05, 0.10, 0.35);
		vec3 mid = vec3(0.16, 0.72, 0.95);
		vec3 high = vec3(0.92, 0.98, 1.0);
		return (t < 0.5) ? mix(low, mid, t * 2.0) : mix(mid, high, (t - 0.5) * 2.0);
	}
	if (mode < 1.5) {
		float v = clamp(value, -1.0, 1.0);
		vec3 negative = vec3(0.20, 0.72, 0.74);
		vec3 neutral = vec3(0.14, 0.12, 0.19);
		vec3 positive = vec3(1.0, 0.72, 0.30);
		float m = clamp(magnitude, 0.0, 1.0);
		vec3 arm = (v < 0.0) ? negative : positive;
		return mix(neutral, arm, m);
	}
	float t = clamp(value, 0.0, 1.0);
	vec3 low = vec3(0.09, 0.06, 0.20);
	vec3 mid = vec3(0.52, 0.28, 0.86);
	vec3 high = vec3(1.0, 0.82, 0.44);
	return (t < 0.6) ? mix(low, mid, t / 0.6) : mix(mid, high, (t - 0.6) / 0.4);
}

void vertex() {
	v_custom = INSTANCE_CUSTOM;
	v_world = vec3(0.0);
	if (v_custom.w < 0.5) {
		POSITION = vec4(2.0, 2.0, 2.0, 1.0);
	} else {
		vec3 center = MODEL_MATRIX[3].xyz;
		float depth = max(-(VIEW_MATRIX * vec4(center, 1.0)).z, 0.001);
		float pixel_world = 2.0 * depth / (VIEWPORT_SIZE.y * abs(PROJECTION_MATRIX[1][1]));
		float size = min(length(MODEL_MATRIX[0].xyz) * size_scale, 72.0 * pixel_world);
		v_world = center + (INV_VIEW_MATRIX[0].xyz * VERTEX.x
				+ INV_VIEW_MATRIX[1].xyz * VERTEX.y) * size;
		POSITION = PROJECTION_MATRIX * VIEW_MATRIX * vec4(v_world, 1.0);
	}
}

void fragment() {
	if (v_custom.w < 0.5) {
		discard;   // unready topology / no site — a finite zero record
	}
	if (cut_enabled > 0.5
			&& dot(v_world - cut_center, cut_normal) < cut_threshold) {
		discard;
	}

	float value = v_custom.x;
	float magnitude = clamp(v_custom.y, 0.0, 1.0);

	// Broad Gaussian support: no bright disk rims or opaque bead centres.
	vec2 p = UV * 2.0 - vec2(1.0);
	float r2 = dot(p, p);
	if (r2 > 1.0) discard;
	float profile = exp(-3.0 * r2) * (1.0 - smoothstep(0.6, 1.0, r2));
	vec3 col = qi_flow_palette(value, magnitude, scalar_mode);
	float alpha = profile * mix(alpha_floor, 1.0, magnitude) * opacity_scale
			* gain * qi_flow_boundary_fade(v_world);
	if (alpha < 0.0005) discard;
	ALBEDO = col;
	EMISSION = col * emission_strength;
	ALPHA = clamp(alpha, 0.0, 1.0);
}
