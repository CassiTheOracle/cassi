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
// q = EY²+EI² field grid (float per cell) — the Qi-rainbow (color_mode 2/3)
// coherence input, sampled trilinearly at the particle (exact convention
// of cassi_nbody_gravity.glsl's scalar samplers; per-axis extents from the
// PC below — that shader reads them from bh[2].yzw, which is the same
// _extents() source on the host).
layout(set = 0, binding = 3, std430) readonly buffer FieldQ { float qv[]; };

// ── Consolidated gradient engine PC (32 floats = 128 B — the AMD RDNA3
// Vulkan push-constant cap; EXACTLY 128, nothing more) ──────────────────
//   slots 0-10   = the shared 11 fields (verbatim, all physics shaders)
//   slot 11      = color_mode (0 = Cassi mass gradient, 1 = velocity,
//                  2/3 = Qi coherence; the pass count lives in span_total)
//   slot 12      = prog_mode (0 = log cycle progress, 1 = linear)
//   slot 13      = ref (velocity: v_ref, mean init |v|; Qi: 0)
//   slots 14-21  = the up-to-3 CYCLE segments [lo1,lo2],[lo2,lo3],[lo3,hiC]:
//                  lo1/slope1 (14/15), lo2/slope2/off2 (16/17/18),
//                  lo3/slope3/off3 (19/20/21) — off2/off3 accumulate the
//                  segment hue shares; pinch OFF ⇒ lo2 = lo3 = hiC and the
//                  shares collapse to (1,0,0) (single segment)
//   slot 22      = hiC (cycle band top)
//   slot 23      = span_total (H_CYCLE·C — the hue budget of the pass set;
//                  h_cyc wraps mod span_total; the one-sided clamp at the
//                  span top holds hue instead of wrapping)
//   slots 24-27  = the APPROACH band (count-invariant white-hot stage):
//                  a_lo (entry), a_hi (white point), gate (pink anchor,
//                  default φ⁻²), approach_on (0/1)
//   slots 28-30  = per-axis box half-extents (the q-sampler's cell mapping —
//                  the same _extents() values nbody reads from bh[2].yzw)
//   slot 31      = hue_offset (rotates the cycle start hue mod span_total)
// GLSL cannot runtime-index push-constant arrays — the segment fields are
// NAMED members selected by the step() masks in the evaluator below.
layout(push_constant, std430) uniform PC {
    float N_f; float dt; float t; float phi;
    float xi; float eps2; float particle_N;
    float mode; float source_strength; float num_clusters;
    float gravity_mode;  // unused here (nbody gravity selector)
    float color_mode;    // 0 = Cassi mass gradient (default, bit-identical); 1 = velocity rainbow; 2/3 = Qi rainbow (the pass count is in span_total)
    float prog_mode;     // cycle progress: 0 = log (default), 1 = linear
    float ref;           // cycle reference: velocity = v_ref (mean init |v|); Qi = 0
    float lo1; float slope1;            // segment 1 [lo1, lo2)
    float lo2; float slope2; float off2;  // segment 2 [lo2, lo3)
    float lo3; float slope3; float off3;  // segment 3 [lo3, hiC]
    float hiC;           // cycle band top
    float span_total;    // H_CYCLE·C — the hue budget of the pass set
    float a_lo;          // approach entry (violet)
    float a_hi;          // approach white point (lightness 1.0)
    float gate;          // approach pink anchor (default φ⁻²)
    float approach_on;   // 0 = approach off (pure cycle), 1 = on
    float extent_x;      // per-axis box half-extents (GRID_LAYOUT.md's φ-aspect
    float extent_y;      // box) — the q-sampler's cell mapping, the same
    float extent_z;      // values nbody reads from bh[2].yzw
    float hue_offset;    // cycle start-hue rotation (mod span_total)
} pc;

// ── Consolidated-gradient constants ─────────────────────────────────────
// H_ENTRY = 0.8 (violet) — the approach entry hue; H_PINK = 0.93 — the
// magenta-family hue passed through EXACTLY at the approach gate (default
// φ⁻² ≈ 0.381966 — the framework's decoherence threshold, PHI_INV2 on the
// host); H_TOP = 1.0 (red ≡ 0) — the approach top hue at the white point.
// LOG_GUARD keeps every log argument and every max() denominator safe
// (never ≤ 0).
const float H_ENTRY = 0.8;
const float H_PINK = 0.93;
const float H_TOP = 1.0;
const float LOG_GUARD = 1e-9;

// Branchless HSL→RGB (IQ form). hue in [0,1): 0=red, 1/3=green, 2/3=blue,
// ~0.8=violet, ~0.93=pink; s,l in [0,1]. No per-channel if/else — works on
// all vendors.
vec3 hsl2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

// ── Consolidated rainbow mapping (recalibrated 2026-08-12 from the
// measured q = EY²+EI² distribution at particle positions — a 1M-particle
// diag mirroring main.tscn, 600 steps — typical q ∈ [3.4e-4, 5.7e-4],
// ~1000× BELOW the old φ⁻² anchor 0.381966, which pinned normal running at
// h ≈ 0). ONE segmented-ramp engine serves both sources (velocity mode 1,
// Qi modes 2/3); the host composes the PC from the legacy exports + the
// consolidated gradient exports:
//   CYCLE — the scalar axis x (q or |v|) is partitioned into up to 3
//     segments [lo1,lo2],[lo2,lo3],[lo3,hiC]; the pinch split concentrates
//     hue gradient where most particles sit (the measured q band; the
//     pinch band is the NARROWEST log interval → intrinsically steepest);
//     pinch OFF ⇒ one segment. Per-segment hue SHARES allocate each pass's
//     hue budget; count C = the number of hue passes over the band
//     (span_total = H_CYCLE·C; H_CYCLE = 1.0 Qi / 0.95 velocity — the
//     legacy velocity top, held with no wrap). Progress is LOG per segment
//     by default (multiplicative physics; the old mapping), LINEAR
//     optional. h_cyc wraps mod span_total (hue_offset rotates the start).
//   APPROACH — count-invariant white-hot stage: violet (0.8) at a_lo →
//     PINK (0.93) EXACTLY at the gate (φ⁻² = the qi gate) → red (1.0) at
//     a_hi, lightness 0.5 → 1.0 (pure white at a_hi = the live
//     qi_condensation_threshold — the physical explosion point; the host
//     reads the LIVE export each fill, so the white point tracks config).
//     The red → violet jump at a_lo is the intentional stage-2 entry
//     marker. The approach is LINEAR (matches the legacy stage 2).
// q < lo1 clamps to h = 0 (red). The q ≥ 0 clamp is a guard
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
    if (pc.color_mode >= 0.5) {
        // ── Consolidated rainbow engine (modes 1/2/3) ────────────────
        // One branchless evaluator for both sources; every difference
        // between the sources/modes lives in the host-composed PC.
        float x = (pc.color_mode >= 1.5)
            ? max(tri_q(pos[i].xyz), 0.0)     // Qi: coherence q (q ≥ 0 guard)
            : length(vel[i].xyz);             // velocity: speed |v|
        float lin = pc.prog_mode;             // 0 = log, 1 = linear
        // per-segment progress (log: multiplicative physics; linear: plain)
        float f1 = mix(log(max((x + pc.ref) / (pc.lo1 + pc.ref), LOG_GUARD)), x - pc.lo1, lin);
        float f2 = mix(log(max((x + pc.ref) / (pc.lo2 + pc.ref), LOG_GUARD)), x - pc.lo2, lin);
        float f3 = mix(log(max((x + pc.ref) / (pc.lo3 + pc.ref), LOG_GUARD)), x - pc.lo3, lin);
        // segment hues: h1 starts at 0; h2/h3 start at the accumulated
        // share offsets — the pinch band's steepness comes from its narrow
        // log interval (the intrinsic steepest segment).
        float h1 = pc.slope1 * f1;
        float h2 = pc.off2 + pc.slope2 * f2;
        float h3 = pc.off3 + pc.slope3 * f3;
        // segment masks (pinch OFF ⇒ lo2 = lo3 = hiC ⇒ only a1 is live).
        // The LAST segment extends past hiC (no upper step): growth beyond
        // the cycle top saturates at the span cap instead of dropping out —
        // the legacy velocity top (h = 0.95 at v ≥ v_max, pink) is held.
        float a1 = step(pc.lo1, x) * (1.0 - step(pc.lo2, x));
        float a2 = step(pc.lo2, x) * (1.0 - step(pc.lo3, x));
        float a3 = step(pc.lo3, x);
        float hc = clamp(a1 * h1 + a2 * h2 + a3 * h3, 0.0, pc.span_total);
        // the offset rotates the cycle start; the wrap boundary is at least
        // a full circle so a single-pass top (velocity span 0.95) is HELD at
        // the cap instead of wrapping back to red (mod(x, y) = 0 for x = y).
        float h_cyc = mod(hc + pc.hue_offset, max(pc.span_total, 1.0));
        // approach band (count-invariant): violet 0.8 at a_lo → PINK 0.93
        // EXACTLY at the gate → red 1.0 at a_hi; lightness 0.5 → 1.0
        float pG = clamp((x - pc.a_lo) / max(pc.gate - pc.a_lo, LOG_GUARD), 0.0, 1.0);
        float pT = clamp((x - pc.gate) / max(pc.a_hi - pc.gate, LOG_GUARD), 0.0, 1.0);
        float pA = clamp((x - pc.a_lo) / max(pc.a_hi - pc.a_lo, LOG_GUARD), 0.0, 1.0);
        float hA = mix(mix(H_ENTRY, H_PINK, pG), mix(H_PINK, H_TOP, pT), step(pc.gate, x));
        float lA = 0.5 + 0.5 * pA;
        float inA = pc.approach_on * step(pc.a_lo, x);
        float h = mix(h_cyc, hA, inA);
        float l = mix(0.5, lA, inA);
        color = vec4(hsl2rgb(vec3(h, 1.0, l)), 1.0);
    }
    inst[base + 3] = color;
}
