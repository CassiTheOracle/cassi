shader_type spatial;
render_mode unshaded;

uniform float size : hint_range(0.0, 500.0) = 1.5;
// Color-as-LUT (Tier-2): with lut_enabled the per-instance color comes from
// the baked 256×1 curve sampled at the band-relative position u (the
// instancer wrote it into custom_data; INSTANCE_CUSTOM is vertex-only, so
// the vertex shader forwards it) instead of the MultiMesh color channel —
// the sim builds use_colors=false / use_custom_data=true in LUT mode.
uniform sampler2D color_lut : source_color, filter_linear, repeat_disable;
uniform float lut_enabled = 0.0;

varying float v_lut_u;

void vertex() {
	vec3 cr = normalize(vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]));
	vec3 cu = normalize(vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]));
	vec3 v = cr * VERTEX.x * size + cu * VERTEX.y * size;
	VERTEX = v;
	v_lut_u = INSTANCE_CUSTOM.x;
}

void fragment() {
	if (lut_enabled > 0.5) {
		vec4 c = texture(color_lut, vec2(v_lut_u, 0.5));
		ALBEDO = c.rgb;
		ALPHA = c.a;
	} else {
		ALBEDO = COLOR.rgb;
		ALPHA = COLOR.a;
	}
}
