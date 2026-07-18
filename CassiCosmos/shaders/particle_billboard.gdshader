shader_type spatial;
render_mode unshaded;

uniform float size : hint_range(0.0, 500.0) = 1.5;

void vertex() {
	vec3 cr = normalize(vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]));
	vec3 cu = normalize(vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]));
	vec3 v = cr * VERTEX.x * size + cu * VERTEX.y * size;
	VERTEX = v;
}

void fragment() {
	ALBEDO = COLOR.rgb;
	ALPHA = COLOR.a;
}
