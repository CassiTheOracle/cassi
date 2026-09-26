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
uniform float lut_enabled = 0.0;
uniform sampler2D color_lut : source_color, filter_linear, repeat_disable;
uniform sampler2D compact_data : filter_nearest, repeat_disable;
uniform float compact_mode = 0.0;
uniform float compact_tex_width = 4096.0;
// Per-instance VFX (LUT path only): the SAME constants the instancer's
// legacy branch applies (cassi_instancer.glsl GLOW_TINT / GLOW_L_BOOST /
// GLOW_A_MIN / GLOW_A_MAX — cross-referenced both files, MUST match).
// glow_tint is the soft warm pink-white glow lift (NOT pure white — the
// LESS-WHITE re-tune); glow_strength scales the lift per-instance.
uniform vec3 glow_tint : source_color = vec3(0.95, 0.90, 0.98);
uniform float glow_strength = 0.12;
const float GLOW_A_MIN = 0.35;   // same as cassi_instancer.glsl
const float GLOW_A_MAX = 1.0;    // same as cassi_instancer.glsl

varying flat vec4 v_particle_color;

void vertex() {
	// VIEW_MATRIX is orthonormal; avoid two normalizations for every quad vertex.
	vec3 cr = vec3(VIEW_MATRIX[0][0], VIEW_MATRIX[1][0], VIEW_MATRIX[2][0]);
	vec3 cu = vec3(VIEW_MATRIX[0][1], VIEW_MATRIX[1][1], VIEW_MATRIX[2][1]);
	vec3 origin = vec3(0.0);
	float instance_size = size;
	vec4 payload = COLOR;
	if (compact_mode > 0.5) {
		int texel = int(INSTANCE_ID) * 2;
		int width = max(int(compact_tex_width), 1);
		ivec2 p0 = ivec2(texel % width, texel / width);
		vec4 data = texelFetch(compact_data, p0, 0);
		vec4 data_payload = texelFetch(compact_data,
				ivec2((texel + 1) % width, (texel + 1) / width), 0);
		mat4 compact_transform = mat4(
				vec4(data.w, 0.0, 0.0, 0.0), vec4(0.0, data.w, 0.0, 0.0),
				vec4(0.0, 0.0, data.w, 0.0), vec4(data.xyz, 1.0));
		payload = data_payload;
		// Compact data already supplies world/window-relative placement.
		// Ignore retained MultiMesh transforms, including after a live toggle.
		MODELVIEW_MATRIX = VIEW_MATRIX * compact_transform;
		MODELVIEW_NORMAL_MATRIX = mat3(VIEW_MATRIX);
	}
	VERTEX = origin + cr * VERTEX.x * instance_size + cu * VERTEX.y * instance_size;
	if (lut_enabled > 0.5) {
		vec3 vfx = compact_mode > 0.5 ? payload.xyz : INSTANCE_CUSTOM.xyz;
		vec4 c = textureLod(color_lut, vec2(vfx.x, 0.5), 0.0);
		float boost = vfx.y;
		float fade = vfx.z;
		v_particle_color = vec4(
				mix(c.rgb, glow_tint, boost * glow_strength),
				c.a * fade * mix(GLOW_A_MIN, GLOW_A_MAX, boost));
	} else {
		v_particle_color = payload;
	}
}

void fragment() {
	// The scientific path uses a QuadMesh for instancing efficiency, but the
	// observable particle support is radial. Never expose the quad's corners as
	// colored image structure.
	vec2 p = UV * 2.0 - vec2(1.0);
	float radius = length(p);
	float aa = max(fwidth(radius), 0.002);
	if (radius > 1.0 + aa) {
		discard;
	}
	float disc = 1.0 - smoothstep(1.0 - aa, 1.0 + aa, radius);
	ALBEDO = v_particle_color.rgb;
	ALPHA = v_particle_color.a * disc;
}
