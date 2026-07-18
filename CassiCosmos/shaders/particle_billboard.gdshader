shader_type spatial;
render_mode unshaded, billboard, depth_draw_alpha_prepass, cull_disabled;

void fragment() {
	ALBEDO = COLOR.rgb;
	ALPHA = COLOR.a;
	TRANSPARENCY = TRANSPARENCY_ALPHA;
}
