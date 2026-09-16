// A soft presentation boundary on the actual finite field window.
// Coordinates and samples remain native: nothing is tiled or extrapolated.
uniform mat4 world_to_field = mat4(1.0);

float qi_flow_boundary_fade(vec3 position) {
	vec3 p = abs((world_to_field * vec4(position, 1.0)).xyz);
	return 1.0 - smoothstep(0.86, 1.02, max(p.x, max(p.y, p.z)));
}
