shader_type spatial;
render_mode unshaded, billboard, cull_disabled;

void fragment() {
	ALBEDO = COLOR.rgb;
	ALPHA = COLOR.a;
}
