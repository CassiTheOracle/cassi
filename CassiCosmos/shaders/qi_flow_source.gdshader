shader_type spatial;
// ═══════════════════════════════════════════════════════════════════════
// CASSI QI-FLOW SOURCES — the material side of the BH source markers
// (compute/cassi_qi_flow.glsl, mode 4).
//
// These mark the ACTUAL records in the engine's BH buffer: a record draws
// only when bh[4+2*slot].w is strictly positive and finite and its position
// is finite. Nothing here invents a horizon, a shadow, or a disk — it is a
// restrained luminous marker at a real source location, sized on a bounded
// log scale, so it stays a marker and never a fictional body. With the BH
// channel off, the compute pass writes zero records and nothing draws.
//
//   row0/row1 = instance scale (a few mean site spacings), row3 translation
//   custom = (mass01, 0, 0, valid)   mass01 = clamp(log2(1+m)/12, 0, 1)
// ═══════════════════════════════════════════════════════════════════════
render_mode blend_add, cull_disabled, unshaded, depth_draw_never;

uniform vec3 core_color : source_color = vec3(1.0, 0.95, 0.86);
uniform vec3 halo_color : source_color = vec3(1.0, 0.74, 0.38);
uniform float size_scale : hint_range(0.1, 3.0) = 1.0;
uniform float alpha_scale : hint_range(0.0, 1.0) = 0.8;
uniform float emission_strength : hint_range(0.0, 4.0) = 1.6;
uniform float gain : hint_range(0.1, 4.0) = 1.0;

// Camera-relative cutaway (shared across field / current / source layers).
uniform float cut_enabled = 0.0;
uniform vec3 cut_center = vec3(0.0);
uniform vec3 cut_normal = vec3(0.0, 0.0, -1.0);
uniform float cut_threshold = 0.0;

varying vec4 v_custom;
varying vec3 v_world;

void vertex() {
	vec3 right = normalize(vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]));
	vec3 up = normalize(vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]));
	VERTEX = (right * VERTEX.x + up * VERTEX.y) * size_scale;
	v_world = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	v_custom = INSTANCE_CUSTOM;
}

void fragment() {
	if (v_custom.w < 0.5) {
		discard;   // no positive finite BH record — a finite zero record
	}
	if (cut_enabled > 0.5
			&& dot(v_world - cut_center, cut_normal) < cut_threshold) {
		discard;
	}

	vec2 p = UV * 2.0 - vec2(1.0);
	float r = length(p);
	float aa = max(fwidth(r), 0.002);
	if (r > 1.0 + aa) {
		discard;
	}
	float disc = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, r);
	float core = 1.0 - smoothstep(0.10, 0.28, r);
	float halo = pow(clamp(1.0 - r, 0.0, 1.0), 2.2) * 0.45;

	float mass01 = clamp(v_custom.x, 0.0, 1.0);
	vec3 col = mix(halo_color, core_color, core);
	float strength = disc * (core + halo) * (0.55 + 0.45 * mass01);
	ALBEDO = col * strength * alpha_scale * gain;
	EMISSION = col * emission_strength * strength * gain;
	ALPHA = clamp(strength * alpha_scale, 0.0, 1.0);
}
