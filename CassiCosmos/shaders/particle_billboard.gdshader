shader_type spatial;
render_mode unshaded;

uniform float size : hint_range(0.0, 500.0) = 1.5;
// Color-as-LUT (Tier-2): with lut_enabled the per-instance color comes from
// the baked 256×1 curve sampled at the band-relative position u (the
// instancer wrote it into custom_data; INSTANCE_CUSTOM is vertex-only, so
// the vertex shader forwards it) instead of the MultiMesh color channel —
// the sim builds use_colors=false / use_custom_data=true in LUT mode.
// custom_data = (u, glow_boost, depth_fade, spare) since 2026-08-14 — the
// per-instance VFX factors ride the y/z channels and are applied on top of
// the LUT fetch below (compute/cassi_instancer.glsl header).
uniform sampler2D color_lut : source_color, filter_linear, repeat_disable;
uniform float lut_enabled = 0.0;
// Per-instance VFX (LUT path only): the SAME constants the instancer's
// legacy branch applies (cassi_instancer.glsl GLOW_TINT / GLOW_L_BOOST /
// GLOW_A_MIN / GLOW_A_MAX — cross-referenced both files, MUST match).
// glow_tint is the soft warm pink-white glow lift (NOT pure white — the
// LESS-WHITE re-tune); glow_strength scales the lift per-instance.
uniform vec3 glow_tint : source_color = vec3(0.95, 0.90, 0.98);
uniform float glow_strength = 0.12;
const float GLOW_A_MIN = 0.35;   // same as cassi_instancer.glsl
const float GLOW_A_MAX = 1.0;    // same as cassi_instancer.glsl

varying vec3 v_lut_vfx;   // (u, glow_boost, depth_fade) — INSTANCE_CUSTOM is vertex-only

void vertex() {
	vec3 cr = normalize(vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]));
	vec3 cu = normalize(vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]));
	vec3 v = cr * VERTEX.x * size + cu * VERTEX.y * size;
	VERTEX = v;
	v_lut_vfx = vec3(INSTANCE_CUSTOM.x, INSTANCE_CUSTOM.y, INSTANCE_CUSTOM.z);
}

void fragment() {
	if (lut_enabled > 0.5) {
		vec4 c = texture(color_lut, vec2(v_lut_vfx.x, 0.5));
		// Per-instance VFX on top of the LUT fetch — the EXACT formulas the
		// legacy instancer branch applies (cassi_instancer.glsl), so the two
		// paths render identically:
		//   alpha = lut.a × depth_fade × mix(GLOW_A_MIN, GLOW_A_MAX, boost)
		//   rgb   = mix(lut.rgb, glow_tint, boost × glow_strength)
		float boost = v_lut_vfx.y;
		float fade = v_lut_vfx.z;
		ALPHA = c.a * fade * mix(GLOW_A_MIN, GLOW_A_MAX, boost);
		ALBEDO = mix(c.rgb, glow_tint, boost * glow_strength);
	} else {
		ALBEDO = COLOR.rgb;
		ALPHA = COLOR.a;
	}
}
