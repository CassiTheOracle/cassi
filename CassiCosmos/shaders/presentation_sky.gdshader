shader_type spatial;
// Camera-following procedural backdrop for CassiCosmos presentation scenes.
// It is an inward-facing sphere with no depth writes, so it establishes a
// stable visual scale without participating in physics or occluding particles.
render_mode unshaded, cull_front, depth_draw_never, fog_disabled;

uniform vec3 zenith_color : source_color = vec3(0.003, 0.007, 0.020);
uniform vec3 horizon_color : source_color = vec3(0.008, 0.016, 0.040);
uniform vec3 nebula_color_a : source_color = vec3(0.12, 0.035, 0.22);
uniform vec3 nebula_color_b : source_color = vec3(0.01, 0.12, 0.22);
uniform float star_density : hint_range(0.0, 1.0) = 0.006;
uniform float star_intensity : hint_range(0.0, 8.0) = 1.45;
uniform float nebula_strength : hint_range(0.0, 1.0) = 0.19;

const float SKY_PI = 3.141592653589793;
const float SKY_TAU = 6.283185307179586;

varying vec3 sky_direction;

float hash12(vec2 p) {
	p = fract(p * vec2(123.34, 456.21));
	p += dot(p, p + 45.32);
	return fract(p.x * p.y);
}

float value_noise(vec2 p) {
	vec2 i = floor(p);
	vec2 f = fract(p);
	f = f * f * (3.0 - 2.0 * f);
	return mix(mix(hash12(i), hash12(i + vec2(1.0, 0.0)), f.x),
			mix(hash12(i + vec2(0.0, 1.0)), hash12(i + vec2(1.0, 1.0)), f.x), f.y);
}

float fbm(vec2 p) {
	float v = 0.0;
	float a = 0.5;
	for (int i = 0; i < 4; i++) {
		v += a * value_noise(p);
		p = p * 2.03 + vec2(17.3, 9.2);
		a *= 0.5;
	}
	return v;
}

float star_field(vec2 cells, vec2 id) {
	float selected = step(1.0 - star_density, hash12(id));
	if (selected < 0.5) {
		return 0.0;
	}
	vec2 f = fract(cells) - 0.5;
	float radius = mix(0.035, 0.18, hash12(id + 7.13));
	float d = length(f);
	float aa = max(fwidth(d), 0.003);
	return 1.0 - smoothstep(radius, radius + aa * 1.8, d);
}

void vertex() {
	// The sphere is translated to the camera by presentation_sky.gd, but its
	// rotation remains world-stable so stars move naturally as the camera turns.
	sky_direction = normalize(VERTEX);
}

void fragment() {
	vec3 dir = normalize(sky_direction);
	vec2 uv = vec2(atan(dir.z, dir.x) / SKY_TAU + 0.5, asin(clamp(dir.y, -1.0, 1.0)) / SKY_PI + 0.5);
	float elevation = smoothstep(-0.65, 0.85, dir.y);
	vec3 background = mix(horizon_color, zenith_color, elevation);

	// A restrained, world-stable galactic haze supports depth perception without
	// competing with the particle/field palette.
	float band_center = 0.10 * sin(dir.x * 5.0) + 0.04 * sin(dir.z * 7.0);
	float band_delta = (dir.y - band_center) * 4.5;
	float band = exp(-band_delta * band_delta);
	float cloud = fbm(uv * vec2(6.0, 3.0) + vec2(0.0, 2.3));
	float haze = band * smoothstep(0.44, 0.73, cloud) * nebula_strength;
	background += mix(nebula_color_a, nebula_color_b, cloud) * haze;

	vec2 star_cells = uv * vec2(960.0, 480.0);
	vec2 star_id = floor(star_cells);
	float star = star_field(star_cells, star_id);
	vec3 star_emission = vec3(0.0);
	if (star > 0.0) {
		float temperature = hash12(star_id + 19.7);
		vec3 star_color = mix(vec3(0.42, 0.62, 1.0), vec3(1.0, 0.78, 0.58), temperature);
		star_emission = star_color * star * star_intensity;
	}
	ALBEDO = background;
	EMISSION = background * 0.26 + star_emission;
}
