#[compute]
#version 450
// Cassi Particle Instancer — writes to MultiMesh buffer (16 floats/instance):
//   3x4 row-major transform + 4 color (as confirmed by Godot issue #76884):
//   float[0-3]   = (basis_row0, origin.x)  → vec4[0]
//   float[4-7]   = (basis_row1, origin.y)  → vec4[1]
//   float[8-11]  = (basis_row2, origin.z)  → vec4[2]
//   float[12-15] = (color.rgba)              → vec4[3]

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) restrict buffer Instances {
    vec4 inst[];
};
layout(set = 0, binding = 2, std430) readonly buffer Velocities { vec4 vel[]; };
// q = EY²+EI² field grid (float per cell) — the Qi-rainbow (color_mode 2)
// coherence input, sampled trilinearly at the particle (exact convention
// of cassi_nbody_gravity.glsl's scalar samplers; per-axis extents from the
// PC below — that shader reads them from bh[2].yzw, which is the same
// _extents() source on the host).
layout(set = 0, binding = 3, std430) readonly buffer FieldQ { float qv[]; };

layout(push_constant, std430) uniform PC {
    float N_f; float dt; float t; float phi;
    float xi; float eps2; float particle_N;
    float mode; float source_strength; float num_clusters;
    float gravity_mode;  // unused here (nbody gravity selector)
    float color_mode;    // 0 = Cassi mass gradient (default, bit-identical); 1 = velocity rainbow; 2 = Qi rainbow
    float v_ref;         // generic rainbow REFERENCE (slots 12/13 shared by modes 1/2):
                         // mode 1 = v_ref, mean initial |v| (host-computed);
                         // mode 2 = Q_FLOOR, the Qi-rainbow stage-1 band floor (2e-4)
    float v_scale;       // generic rainbow SCALE:
                         // mode 1 = 0.8/ln(1+v_max/v_ref);
                         // mode 2 = 0.8/ln(Q_1/Q_FLOOR) — stage-1 hue ramp scale
    float extent_x;      // per-axis box half-extents (GRID_LAYOUT.md's φ-aspect
    float extent_y;      // box) — the q-sampler's cell mapping, the same
    float extent_z;      // values nbody reads from bh[2].yzw
    float q_1;           // NEW float 17 (mode 2 only): stage-1 band top (1e-3) —
                         // hue ramp ends / white-hot lightness ramp begins
    float q_top;         // NEW float 18 (mode 2 only): stage-2 white point =
                         // the scene's qi_condensation_threshold (host reads the
                         // LIVE export each fill, so the white point tracks config)
} pc;

// Branchless HSL→RGB (IQ form). hue in [0,1): 0=red, 1/3=green, 2/3=blue,
// ~0.8=violet; s,l in [0,1]. No per-channel if/else — works on all vendors.
vec3 hsl2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

// Qi-rainbow anchors are PC-fed (slots 12/13 = Q_FLOOR/Q_SCALE, 17/18 =
// Q_1/Q_TOP). TWO-STAGE mapping (recalibrated 2026-08-12 from the measured
// q = EY²+EI² distribution at particle positions — a 1M-particle diag
// mirroring main.tscn, 600 steps — typical q ∈ [3.4e-4, 5.7e-4], ~1000×
// BELOW the old φ⁻² anchor 0.381966, which pinned normal running at h ≈ 0):
//   STAGE 1 (q ∈ [Q_FLOOR, Q_1], the normal operating band): full rainbow
//     hue ramp h = Q_SCALE·ln(q/Q_FLOOR) — the ENTIRE measured band spans
//     h ≈ 0.26-0.52 (yellow-green → cyan-green; median 3.8e-4 ≈ green),
//     so normal running shows a vivid spectrum instead of a hue sliver.
//   STAGE 2 (q ∈ [Q_1, Q_TOP], elevated coherence approaching condensation):
//     hue pinned at 0.8 (violet), lightness ramps 0.5 → 1.0 — pure white
//     at q_top = the scene's qi_condensation_threshold (0.85, the physical
//     explosion point; host reads the LIVE export each fill).
// q < Q_FLOOR clamps to h = 0 (red). The q ≥ 0 clamp is a guard
// (EY²+EI² cannot go negative).

// ── Index helper + trilinear sample (periodic wrap) of the q field ─────
// EXACT convention of cassi_nbody_gravity.glsl's scalar samplers: the
// per-axis half-extents (here from the PC; nbody reads bh[2].yzw — the
// host's _extents() in both cases) map world → grid via
// gc = (wp·inv_ext)·N/2 + N/2 with periodic wraps. Trilinear of a linear
// ramp field is exact, so a slab/ramp test field reproduces the anchor
// hues to fp32.
int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}
float tri_q(vec3 wp) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    vec3 gc = (wp * inv_ext) * hn + hn;
    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));
    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);
    i0 = ((i0 % N) + N) % N;  j0 = ((j0 % N) + N) % N;  k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;    int j1 = (j0 + 1) % N;    int k1 = (k0 + 1) % N;
    float v000 = qv[idx3(i0, j0, k0)];
    float v100 = qv[idx3(i1, j0, k0)];
    float v010 = qv[idx3(i0, j1, k0)];
    float v110 = qv[idx3(i1, j1, k0)];
    float v001 = qv[idx3(i0, j0, k1)];
    float v101 = qv[idx3(i1, j0, k1)];
    float v011 = qv[idx3(i0, j1, k1)];
    float v111 = qv[idx3(i1, j1, k1)];
    float q0 = mix(mix(v000, v100, fx), mix(v010, v110, fx), fy);
    float q1 = mix(mix(v001, v101, fx), mix(v011, v111, fx), fy);
    return mix(q0, q1, fz);
}

void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    if (i >= N) return;

    vec4 p = pos[i];
    int base = i * 4;

    // Mass-based visual scale: m=0.3→0.6x, m=1.0→0.8x, m=30→4x
    float m = p.w;
    float s = clamp(0.5 + m * 0.12, 0.4, 5.0);

    // Row-major 3x4: scale basis by mass-derived size
    inst[base]     = vec4(s, 0.0, 0.0, p.x);
    inst[base + 1] = vec4(0.0, s, 0.0, p.y);
    inst[base + 2] = vec4(0.0, 0.0, s, p.z);

    // Mass-based color temperature (Salpeter IMF: many blue dwarfs, few red giants)
    float log_m = clamp((log2(m) + 2.0) * 0.25, 0.0, 1.0);  // 0→0.3M☉, 1→30M☉
    float cr = mix(0.15, 1.0,  log_m * log_m);                 // blue dwarf→red giant
    float cg = mix(0.25, 0.6,  log_m);
    float cb = mix(1.0,  0.15, log_m);
    vec4 color = vec4(cr, cg, cb, 1.0);
    if (pc.color_mode >= 1.5) {
        // Qi rainbow (color_mode 2) — TWO-STAGE mapping of the two-fluid
        // coherence q = EY²+EI² trilinearly sampled at the particle:
        //   STAGE 1 (q ∈ [Q_FLOOR, Q_1] — the normal operating band):
        //     h = clamp(Q_SCALE·ln(q/Q_FLOOR), 0.0, 0.8), s = 1, l = 0.5 —
        //     the full measured band (3.4e-4…5.7e-4) spans h ≈ 0.26-0.52
        //     (yellow-green → cyan-green; median ≈ green), so normal
        //     running shows a vivid rainbow instead of the old mapping's
        //     h ≈ 0.07-0.10 red-orange sliver. q < Q_FLOOR clamps to red.
        //   STAGE 2 (q ∈ [Q_1, Q_TOP] — elevated coherence approaching
        //     condensation): hue pinned at 0.8 (violet) and lightness
        //     ramps l = 0.5 + 0.5·(q − Q_1)/(Q_TOP − Q_1) — pure white
        //     (l = 1) at q_top = the scene's qi_condensation_threshold.
        //     White-hot approach, not violet saturation.
        // Q_FLOOR/Q_SCALE arrive in the generic v_ref/v_scale PC slots
        // (12/13, shared with mode 1); Q_1/Q_TOP in the new slots 17/18.
        float qq = max(tri_q(pos[i].xyz), 0.0);
        float q_floor = max(pc.v_ref, 1e-9);          // slot 12 (mode 2: Q_FLOOR)
        float h = clamp(pc.v_scale * log(qq / q_floor), 0.0, 0.8);  // stage 1 ramp
        float l = 0.5;
        if (qq >= pc.q_1) {                           // stage 2: white-hot approach
            h = 0.8;
            l = 0.5 + 0.5 * clamp((qq - pc.q_1) / max(pc.q_top - pc.q_1, 1e-9), 0.0, 1.0);
        }
        color = vec4(hsl2rgb(vec3(h, 1.0, l)), 1.0);
    } else if (pc.color_mode >= 0.5) {
        // Velocity rainbow (log-compressed, distribution-anchored):
        // h = v_scale·ln(1+|v|/v_ref) — slow = red (h→0), v=v_ref ≈ 0.4-0.6,
        // v=v_max → 0.8 (violet). Hue drifts only logarithmically under
        // velocity growth; the one-sided clamp at 0.8 keeps growth beyond
        // v_max SATURATING at violet instead of wrapping past hue 1.0 (a
        // discontinuous jump color). v_ref guarded against 0; the host
        // guarantees v_scale = 0.8·ln2 in the degenerate zero-speed case.
        float v = length(vel[i].xyz);
        float h = min(pc.v_scale * log(1.0 + v / max(pc.v_ref, 1e-6)), 0.8);
        color = vec4(hsl2rgb(vec3(h, 1.0, 0.5)), 1.0);
    }
    inst[base + 3] = color;
}
