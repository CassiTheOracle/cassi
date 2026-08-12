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
    float color_mode;    // 0 = Cassi mass gradient (default, bit-identical); 1 = velocity rainbow; 2 = Qi rainbow; 3 = Qi double rainbow
    float v_ref;         // generic rainbow REFERENCE (slots 12/13 shared by modes 1/2/3):
                         // mode 1 = v_ref, mean initial |v| (host-computed);
                         // modes 2/3 = Q_FLOOR, the Qi-rainbow stage-1 band floor (2e-4)
    float v_scale;       // generic rainbow SCALE:
                         // mode 1 = 0.95/ln(1+v_max/v_ref) (v_max → h = 0.95, magenta-pink);
                         // modes 2/3 = 1.0/ln(Q_1/Q_FLOOR) — stage-1 hue ramp scale
                         // (full hue circle in mode 2; mode 3 doubles the ramp in the branch body)
    float extent_x;      // per-axis box half-extents (GRID_LAYOUT.md's φ-aspect
    float extent_y;      // box) — the q-sampler's cell mapping, the same
    float extent_z;      // values nbody reads from bh[2].yzw
    float q_1;           // float 17 (modes 2/3): stage-1 band top (1e-3) — hue
                         // ramp ends / stage-2 entry (violet; the red → violet jump)
    float q_top;         // float 18 (modes 2/3): stage-2 white point =
                         // the scene's qi_condensation_threshold (host reads the
                         // LIVE export each fill, so the white point tracks config)
} pc;

// ── Qi-rainbow stage-2 constants (modes 2/3, shader-side, zero PC growth) ──
// Q_GATE = φ⁻² ≈ 0.3819660112501051 — the framework's DECOHERENCE THRESHOLD
// (the qi gate; the same PHI_INV2 constant the host exports). Stage 2 is
// anchored on it: the hue passes through PINK exactly at q = Q_GATE.
// H_PINK = 0.93 — the pink (magenta-family) hue used at the gate.
const float Q_GATE = 0.3819660112501051;
const float H_PINK = 0.93;

// Branchless HSL→RGB (IQ form). hue in [0,1): 0=red, 1/3=green, 2/3=blue,
// ~0.8=violet, ~0.93=pink; s,l in [0,1]. No per-channel if/else — works on
// all vendors.
vec3 hsl2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

// ── Stage-2 Qi hue/lightness (shared modes 2/3) ─────────────────────────
// q ∈ [Q_1, Q_TOP]: violet (h = 0.8) at Q_1 → PINK (h = H_PINK) EXACTLY at
// the framework decoherence gate q = Q_GATE = φ⁻² (the qi gate —
// 0.3819660112501051, the same PHI_INV2 constant the host uses) → red
// (h = 1.0 ≡ 0) at Q_TOP, with lightness ramping 0.5 → 1.0 the whole way
// so the threshold washes to PURE WHITE (white-hot, not red-hot).
vec2 qi_stage2(float qq) {
    float l = 0.5 + 0.5 * clamp((qq - pc.q_1) / max(pc.q_top - pc.q_1, 1e-9), 0.0, 1.0);
    float h;
    if (qq < Q_GATE) {
        // violet → pink across [Q_1, Q_GATE]
        h = 0.8 + (H_PINK - 0.8) * clamp((qq - pc.q_1) / max(Q_GATE - pc.q_1, 1e-9), 0.0, 1.0);
    } else {
        // pink → red across [Q_GATE, Q_TOP]
        h = mix(H_PINK, 1.0, clamp((qq - Q_GATE) / max(pc.q_top - Q_GATE, 1e-9), 0.0, 1.0));
    }
    return vec2(h, l);
}

// Qi-rainbow anchors are PC-fed (slots 12/13 = Q_FLOOR/Q_SCALE, 17/18 =
// Q_1/Q_TOP); the stage-2 gate anchors are shader consts (Q_GATE/H_PINK
// below). TWO-STAGE mapping (recalibrated 2026-08-12 from the measured
// q = EY²+EI² distribution at particle positions — a 1M-particle diag
// mirroring main.tscn, 600 steps — typical q ∈ [3.4e-4, 5.7e-4], ~1000×
// BELOW the old φ⁻² anchor 0.381966, which pinned normal running at h ≈ 0):
//   STAGE 1 (q ∈ [Q_FLOOR, Q_1], the normal operating band): the FULL hue
//     circle — h = Q_SCALE·ln(q/Q_FLOOR) with Q_SCALE = 1/ln(Q_1/Q_FLOOR),
//     so f = ln(q/Q_FLOOR)/ln(Q_1/Q_FLOOR) ∈ [0,1] maps linearly onto
//     [0,1] (f=0 red, f=0.5 cyan, f=1 red again) — the magenta/pink
//     segment 0.8-1.0 the old 0.8 cap omitted is now visible; the measured
//     band spans h ≈ 0.33-0.65 (green → cyan-blue; median ≈ 0.40).
//   STAGE 2 (q ∈ [Q_1, Q_TOP], elevated coherence approaching condensation):
//     hue ramps violet (0.8) at Q_1 → PINK (0.93) EXACTLY at the φ⁻²
//     decoherence gate q = Q_GATE → red (1.0) at Q_TOP, while lightness
//     ramps 0.5 → 1.0 — pure white at q_top = the scene's
//     qi_condensation_threshold (0.85, the physical explosion point; host
//     reads the LIVE export each fill). The red → violet jump at Q_1 is
//     the intentional stage-2 entry marker (white-hot approach).
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
    if (pc.color_mode >= 2.5) {
        // Qi DOUBLE rainbow (color_mode 3): same two-stage structure as
        // mode 2 with the stage-1 hue ramp DOUBLED —
        //   h = clamp(2.0 · Q_SCALE · ln(q/Q_FLOOR), 0.0, 2.0)
        // The IQ hsl2rgb hue is periodic mod 1 (mod 6 inside), so the
        // normal band now passes through the rainbow TWICE for doubled
        // gradient granularity: at f = ln(q/Q_FLOOR)/ln(Q_1/Q_FLOOR) ∈
        // [0,1], h = 2·f — f=0 red, f=0.25 h=0.5 (cyan-green),
        // f=0.5 h=1.0≡0 (red), f=0.75 h=1.5≡0.5 (cyan-green),
        // f→1 h→2.0≡0 (red). Stage 2 (qq >= q_1) is IDENTICAL to
        // mode 2 (shared qi_stage2: violet → pink at the φ⁻² gate → red,
        // lightness ramps to white at q_top) — the jump from the ramp
        // limit h≡0 (red) to h=0.8 (violet) at the stage boundary is the
        // intentional 'entering the white-hot stage' marker. Same PC slots
        // as mode 2 (12/13: Q_FLOOR/Q_SCALE; 17/18: Q_1/Q_TOP) — the ×2
        // is a shader constant, zero PC growth.
        float qq = max(tri_q(pos[i].xyz), 0.0);
        float q_floor = max(pc.v_ref, 1e-9);          // slot 12 (modes 2/3: Q_FLOOR)
        vec2 hsl;
        if (qq >= pc.q_1) {
            hsl = qi_stage2(qq);                      // stage 2 (shared with mode 2)
        } else {
            hsl = vec2(clamp(2.0 * pc.v_scale * log(qq / q_floor), 0.0, 2.0), 0.5);  // two full circles
        }
        color = vec4(hsl2rgb(vec3(hsl.x, 1.0, hsl.y)), 1.0);
    } else if (pc.color_mode >= 1.5) {
        // Qi rainbow (color_mode 2) — TWO-STAGE mapping of the two-fluid
        // coherence q = EY²+EI² trilinearly sampled at the particle:
        //   STAGE 1 (q ∈ [Q_FLOOR, Q_1] — the normal operating band):
        //     h = clamp(Q_SCALE·ln(q/Q_FLOOR), 0.0, 1.0), s = 1, l = 0.5 —
        //     the FULL hue circle (f = ln(q/Q_FLOOR)/ln(Q_1/Q_FLOOR) maps
        //     linearly onto [0,1]: f=0 red, f=0.5 cyan, f=1 red again),
        //     magenta/pink segment 0.8-1.0 included; the measured band
        //     (3.4e-4…5.7e-4) spans h ≈ 0.33-0.65 (green → cyan-blue).
        //     q < Q_FLOOR clamps to red.
        //   STAGE 2 (q ∈ [Q_1, Q_TOP] — elevated coherence approaching
        //     condensation): hue ramps violet (0.8) at Q_1 → PINK (0.93)
        //     EXACTLY at the φ⁻² decoherence gate Q_GATE → red (1.0) at
        //     Q_TOP, with lightness ramping 0.5 → 1.0 (pure white at
        //     q_top = the scene's qi_condensation_threshold) — white-hot
        //     approach. The red → violet jump at Q_1 is the intentional
        //     stage-2 entry marker.
        // Q_FLOOR/Q_SCALE arrive in the generic v_ref/v_scale PC slots
        // (12/13, shared with mode 1); Q_1/Q_TOP in the new slots 17/18.
        float qq = max(tri_q(pos[i].xyz), 0.0);
        float q_floor = max(pc.v_ref, 1e-9);          // slot 12 (mode 2: Q_FLOOR)
        vec2 hsl;
        if (qq >= pc.q_1) {
            hsl = qi_stage2(qq);                      // stage 2: violet → pink gate → white
        } else {
            hsl = vec2(clamp(pc.v_scale * log(qq / q_floor), 0.0, 1.0), 0.5);  // stage 1: full circle
        }
        color = vec4(hsl2rgb(vec3(hsl.x, 1.0, hsl.y)), 1.0);
    } else if (pc.color_mode >= 0.5) {
        // Velocity rainbow (log-compressed, distribution-anchored):
        // h = v_scale·ln(1+|v|/v_ref) — slow = red (h→0), v=v_ref ≈ 0.4-0.6,
        // v=v_max → 0.95 (magenta-pink, the full-circle top). Hue drifts
        // only logarithmically under velocity growth; the one-sided clamp
        // at 0.95 keeps growth beyond v_max SATURATING at pink instead of
        // wrapping past hue 1.0 (a discontinuous jump color). v_ref guarded
        // against 0; the host guarantees v_scale = 0.95·ln2 in the
        // degenerate zero-speed case.
        float v = length(vel[i].xyz);
        float h = min(pc.v_scale * log(1.0 + v / max(pc.v_ref, 1e-6)), 0.95);
        color = vec4(hsl2rgb(vec3(h, 1.0, 0.5)), 1.0);
    }
    inst[base + 3] = color;
}
