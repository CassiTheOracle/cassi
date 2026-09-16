shader_type spatial;
// ═══════════════════════════════════════════════════════════════════════
// CASSI QI-FLOW FILAMENTS — the material side of the native-site graph-bond
// current-aligned graph paths (compute/cassi_qi_flow.glsl, mode 2).
//
// Consumes the 3x4 transform + custom record that pass writes:
//   rows 0..2 = row-major 3x4 transform (basis in columns, origin in column 3)
//   row3 = custom = (channel, u_along_stream, intensity, valid)
//     channel   0 = Yang (warm gold), 1 = Yin (teal), 2 = Net (pale)
//     u         0 tail → 1 head along this streamline (the material's
//               head-brightening shows FLOW DIRECTION)
//     intensity compressive display intensity (mag/reference)^0.35 — a
//               clamped display scale, not a speed claim
//     valid     the material discards 0
//
// ── The animated pulse is a DIRECTION CUE, NOT A PARCEL SPEED ──────────
// `cue_*` uniforms advance a brightness wave from tail to head using
// FIELD_TIME (the accepted simulation time the host passes in). It is a
// phase marker: it says "this way", never "this fast", and because the
// clock is the accepted field time, pausing the simulation freezes it.
// TIME (the wall clock) is deliberately unused everywhere in this material.
//
// The ribbon is a camera-readable quad: width along basis X, length along
// basis Y in the sampled direction; additive so overlapping paths read as light.
// ═══════════════════════════════════════════════════════════════════════
render_mode blend_add, cull_disabled, unshaded, depth_draw_never;
#include "res://shaders/qi_flow_view.gdshaderinc"

// The three current colors the renderer publishes (exact values shared with
// the sim_ui color key): Yang warm gold, Yin teal, Net pale cool white.
uniform vec3 yang_color : source_color = vec3(1.0, 0.79, 0.36);
uniform vec3 yin_color : source_color = vec3(0.30, 0.85, 0.80);
uniform vec3 net_color : source_color = vec3(0.78, 0.82, 1.0);

uniform float emission_strength : hint_range(0.0, 4.0) = 2.4;
uniform float alpha_scale : hint_range(0.0, 1.0) = 0.8;
uniform float gain : hint_range(0.1, 4.0) = 1.0;
uniform float width_scale : hint_range(0.1, 4.0) = 1.0;   // ribbon width multiplier
uniform float width_softness : hint_range(0.0, 1.0) = 0.45;
uniform float head_taper : hint_range(0.0, 1.0) = 0.45;   // tail→head brightness cue
uniform float core_white : hint_range(0.0, 1.0) = 0.16;

// Direction cue (accepted field time only — pause freezes it).
uniform float field_time = 0.0;
uniform float cue_rate : hint_range(0.0, 4.0) = 0.55;     // cycles per accepted second
uniform float cue_cycles : hint_range(0.0, 4.0) = 1.0;    // spatial cycles along the stream
uniform float cue_strength : hint_range(0.0, 1.0) = 0.5;

// Camera-relative cutaway (world space, host-computed); the same three
// layers share this contract.
uniform float cut_enabled = 0.0;
uniform vec3 cut_center = vec3(0.0);
uniform vec3 cut_normal = vec3(0.0, 0.0, -1.0);
uniform float cut_threshold = 0.0;

varying vec4 v_custom;
varying vec3 v_world;

void vertex() {
	v_custom = INSTANCE_CUSTOM;
	v_world = vec3(0.0);
	if (v_custom.w < 0.5) {
		POSITION = vec4(2.0, 2.0, 2.0, 1.0);
	} else {
		vec3 center = MODEL_MATRIX[3].xyz;
		float depth = max(-(VIEW_MATRIX * vec4(center, 1.0)).z, 0.001);
		float pixel_world = 2.0 * depth / (VIEWPORT_SIZE.y * abs(PROJECTION_MATRIX[1][1]));
		float width = clamp(length(MODEL_MATRIX[0].xyz) * width_scale,
				2.0 * pixel_world, 4.0 * pixel_world);
		vec3 across = cross(normalize(MODEL_MATRIX[1].xyz),
				normalize(INV_VIEW_MATRIX[3].xyz - center));
		across = dot(across, across) > 1.0e-8 ? normalize(across) : INV_VIEW_MATRIX[0].xyz;
		v_world = center + across * VERTEX.x * width + MODEL_MATRIX[1].xyz * VERTEX.y;
		POSITION = PROJECTION_MATRIX * VIEW_MATRIX * vec4(v_world, 1.0);
	}
}

void fragment() {
	if (v_custom.w < 0.5) {
		discard;   // unwritten / ineligible slot — a finite zero record
	}
	if (cut_enabled > 0.5
			&& dot(v_world - cut_center, cut_normal) < cut_threshold) {
		discard;   // camera-relative cutaway: the near side is removed
	}

	// Godot's QuadMesh UV.y=0 is the +Y end: downstream in our instance basis.
	vec2 p = UV * 2.0 - vec2(1.0);

	float intensity = clamp(v_custom.z, 0.0, 1.0);
	float u = clamp(v_custom.y + (0.5 - UV.y) * (1.25 / 16.0), 0.0, 1.0);
	float channel = v_custom.x;

	// Soft camera-readable ribbon cross-section (symmetric in both axes, so
	// the quad's UV orientation cannot flip the look).
	float across = 1.0 - smoothstep(0.0, 1.0, abs(p.x));
	float profile = pow(max(across, 0.0), 1.0 + width_softness);
	// The segment quad is 1.25x the bond length, so the fade below starts
	// beyond the real joint: neighbouring segments overlap at full strength
	// and the polyline reads continuous instead of dotted.
	float ends = 1.0 - smoothstep(0.86, 1.0, abs(p.y));
	profile *= ends;
	if (profile < 0.004) {
		discard;
	}

	// Color: per-channel hue, with a restrained hot core at high intensity.
	vec3 hue;
	if (channel < 0.5) {
		hue = yang_color;
	} else if (channel < 1.5) {
		hue = yin_color;
	} else {
		hue = net_color;
	}
	vec3 col = mix(hue, vec3(1.0), core_white * intensity);

	// Direction cue: a brightness wave travelling tail → head. Phase uses
	// the ACCEPTED FIELD TIME, so a paused simulation holds the phase.
	float wave = 0.5 + 0.5 * sin(
			6.283185307179586 * (u * cue_cycles - field_time * cue_rate));
	float cue = mix(1.0, wave, clamp(cue_strength, 0.0, 1.0));

	// Head brightness (the second, static direction cue).
	float head = mix(1.0 - head_taper, 1.0, u);

	float strength = profile * cue * head * (0.35 + 0.65 * intensity)
			* qi_flow_boundary_fade(v_world);
	// Apply the profile once through additive alpha, not a second time in RGB.
	ALBEDO = col * gain;
	EMISSION = col * emission_strength * gain;
	ALPHA = clamp(strength * alpha_scale, 0.0, 1.0);
}
