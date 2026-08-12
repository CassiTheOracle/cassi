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
    float v_ref;         // mode 1: rainbow speed reference (mean initial |v|, host-computed);
                         // mode 2: Qi-rainbow q_ref (measured typical-band anchor, see host Q_REF)
    float v_scale;       // mode 1: rainbow hue scale 0.8/ln(1+v_max/v_ref);
                         // mode 2: Qi-rainbow ramp scale 0.8/ln(1+q_top/q_ref), q_top = the
                         // scene's qi_condensation_threshold (host-computed per fill)
    float extent_x;      // per-axis box half-extents (GRID_LAYOUT.md's φ-aspect
    float extent_y;      // box) — the q-sampler's cell mapping, the same
    float extent_z;      // values nbody reads from bh[2].yzw
} pc;

// Branchless HSL→RGB (IQ form). hue in [0,1): 0=red, 1/3=green, 2/3=blue,
// ~0.8=violet; s,l in [0,1]. No per-channel if/else — works on all vendors.
vec3 hsl2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

// Qi-rainbow anchors are PC-fed (slots 12/13: q_ref, q_scale — the host
// computes q_scale = 0.8/ln(1+q_top/q_ref) per fill from the LIVE
// qi_condensation_threshold export; see cassi_sim.gd Q_REF). Recalibrated
// 2026-08-12: the measured q distribution at particle positions (1M-particle
// diag mirroring main.tscn, 600 steps) sits ~1000× BELOW the old φ⁻² anchor
// (typical q ∈ [3.4e-4, 5.7e-4] vs φ⁻² = 0.381966), which pinned normal
// running at h ≈ 0 (pure red). q_ref = 0.00036 now sits inside the measured
// typical band; q_top = qi_condensation_threshold (the explosion point).

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
        // Qi rainbow (color_mode 2): hue from the two-fluid coherence
        // q = EY²+EI² trilinearly sampled at the particle —
        //   h = clamp(Q_SCALE·ln(1 + q/q_ref), 0.0, 0.8)
        // q_ref/q_scale arrive in the v_ref/v_scale PC slots (12/13): the
        // log ramp is anchored at the MEASURED typical-running q band
        // (q_ref = 0.00036) and topped at the scene's condensation
        // threshold q_top (q_scale = 0.8/ln(1+q_top/q_ref)) — so typical
        // running q (≈3.5-5.7e-4) gets a live hue response (h ≈ 0.07-0.10,
        // red-orange) instead of being pinned at h ≈ 0 (the old φ⁻² anchor
        // sat ~1000× above it). q→0 = red,
        // q = q_ref ≈ red-orange (h≈0.07), and the approach to the
        // threshold sweeps the full rainbow. WHITE-HOT TOP: lightness
        // ramps from 0.5 (vivid) below h = 0.6 to 1.0 (pure white) at
        // h = 0.8 = q_top — the top quarter washes to white, not violet.
        // The q ≥ 0 clamp is a guard (EY²+EI² cannot go negative).
        float qq = max(tri_q(pos[i].xyz), 0.0);
        float q_ref = max(pc.v_ref, 1e-9);  // slot 12 (mode 2: q_ref; guarded vs 0)
        float h = clamp(pc.v_scale * log(1.0 + qq / q_ref), 0.0, 0.8);
        float l = 0.5 + 0.5 * clamp((h - 0.6) / 0.2, 0.0, 1.0);  // 0.75·H_TOP=0.6, 0.25·H_TOP=0.2
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
