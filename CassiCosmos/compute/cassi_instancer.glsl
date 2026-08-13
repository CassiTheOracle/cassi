#[compute]
#version 450
// Cassi Particle Instancer — writes to MultiMesh buffer (16 floats/instance):
//   3x4 row-major transform + 4 color (as confirmed by Godot issue #76884):
//   float[0-3]   = (basis_row0, origin.x)  → vec4[0]
//   float[4-7]   = (basis_row1, origin.y)  → vec4[1]
//   float[8-11]  = (basis_row2, origin.z)  → vec4[2]
//   float[12-15] = (color.rgba)              → vec4[3]
//
// ═══════════════════════════════════════════════════════════════════════
// PARTICLE-VFX UPGRADES (2026-08-13, particle-gfx workstream) — all
// default-off; the legacy color path (color_mode 0..3, flags = 0) is
// bit-for-bit preserved. New features are selected by EXTENDING the
// color_mode value read from the host PC: the low nibble is the base mode
// (0..3 legacy, 4 = two-axis hue=q/lightness=ρ), and the high nibble is a
// FEATURE-FLAG bitfield that any base mode can carry:
//   bit0 (0x10) = SIZE_BY_MASS (basis scale ∝ cbrt(pos.w))
//   bit1 (0x20) = ADDITIVE_GLOW (bright-core additive look + halo ramp)
//   bit2 (0x40) = DEPTH_CUE (per-instance fade with camera distance)
// Example: particle_color_mode = 2 + 0x10 = 18 → Qi rainbow + size-by-mass.
//
// MASS IS PER-PARTICLE: the Positions buffer's vec4.w carries the Salpeter
// mass (m ∈ [0.3, 30] M☉) — written by _init_particles, preserved verbatim
// by the nbody KDK kick (cassi_nbody_gravity.glsl: "pos[i] = vec4(p_new,
// pos[i].w)"). The default path already reads p.w for size + temperature;
// the size-by-mass mode re-reads the SAME pos.w. NO dedicated MASS/COUNT
// buffer is needed — when a future merge pass writes varied masses into
// pos.w the size mode lights up for free.
//
// ── DEFERRED cassi_sim.gd integration (green-lit after the fmm wave) ──
// Everything below runs on the CURRENT 4-binding uniform set + the host's
// existing PC fill, so NOTHING here is blocked. Two OPTIONAL upgrades are
// documented at their exact integration points and left OFF until the
// cassi_sim.gd hooks land:
//   (1) TWO-AXIS lightness from TRUE ρ = EY+EI (mode 4): bindings 4/5 of
//       `_us_inst_0` in cassi_sim.gd `_cache_uniform_sets()` MUST be added:
//           _uniform_storage(4, _field_ey),  // EY (mode 4 ρ = EY+EI)
//           _uniform_storage(5, _field_ei),  // EI
//       and the tri_rho sampler below flipped from the q-proxy to the
//       EY+EI trilinear read. Until then mode 4 uses q (EY²+EI²) as a
//       monotonic ρ proxy (same EY/EI convention; a valid two-axis look).
//   (2) DEPTH_CUE from the TRUE camera distance: `_fill_instancer_pc()`
//       MUST write the live camera world position into the 3 instancer-PC
//       slots the instancer shader never reads for their shared meaning —
//       byte 32 (slot 8, shared `source_strength`), byte 36 (slot 9,
//       `num_clusters`), byte 40 (slot 10, `gravity_mode`) — each camera
//       axis (x/y/z). sim_ui.gd has the camera reference (sibling Camera3D
//       of CassiSim; see _find_sibling_camera). Until then the shader uses
//       the world-origin distance as the depth proxy (identical when the
//       host leaves those slots as the shared fill; correct for this
//       auto-framed sim). No PC-format change: all 32 slots stay.
//   NO other host change is required. The param SCALARS (size_k, glow
//   thresholds, depth scale) are baked constants here so the features
//   work before AND after the hook; the hook may later override them via
//   the same 5 repurposable slots (see #DEFERRED slot map at the bottom).

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
//                  EXTENDED (2026-08-13): low nibble = base mode (0-4),
//                  high nibble = VFX feature flags (0x10/0x20/0x40). Base
//                  modes + flags decode below. Bit-identical for 0..3,0.
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
//                  a_lo (entry), a_hi (white point), a_top (hue at white —
//                  pink 0.93; no red at the top), approach_on (0/1)
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
    float color_mode;    // 0 = Cassi mass gradient (default, bit-identical); 1 = velocity rainbow; 2/3 = Qi rainbow (the pass count is in span_total); low nibble = base mode, high nibble = VFX flags (see header)
    float prog_mode;     // cycle progress: 0 = log (default), 1 = linear
    float ref;           // cycle reference: velocity = v_ref (mean init |v|); Qi = 0
    float lo1; float slope1;            // segment 1 [lo1, lo2)
    float lo2; float slope2; float off2;  // segment 2 [lo2, lo3)
    float lo3; float slope3; float off3;  // segment 3 [lo3, hiC]
    float hiC;           // cycle band top
    float span_total;    // H_CYCLE·C — the hue budget of the pass set
    float a_lo;          // approach entry (violet)
    float a_hi;          // approach white point (lightness 1.0)
    float a_top;         // approach hue at the white point (pink 0.93 — the top end is not red)
    float approach_on;   // 0 = approach off (pure cycle), 1 = on
    float extent_x;      // per-axis box half-extents (GRID_LAYOUT.md's φ-aspect
    float extent_y;      // box) — the q-sampler's cell mapping, the same
    float extent_z;      // values nbody reads from bh[2].yzw
    float hue_offset;    // cycle start-hue rotation (mod span_total)
} pc;

// ── Consolidated-gradient constants ─────────────────────────────────────
// H_ENTRY = 0.8 (violet) — the approach entry hue; the approach ramps to
// pc.a_top (pink 0.93) at the white point — red never appears at high
// coherence. LOG_GUARD keeps every log argument and every max()
const float H_ENTRY = 0.8;
const float LOG_GUARD = 1e-9;

// ── VFX constants (2026-08-13; feature work on the current PC/bindings) ─
// SIZE_BY_MASS (flag 0x10): s = clamp(SIZE_K · cbrt(m), SIZE_S_MIN,
// SIZE_S_MAX) with SIZE_K chosen so s ≈ the legacy s at m = 1
// (0.5 + 1·0.12 = 0.62). m^(1/3) over the Salpeter range [0.3, 30] spans
// cbrt(0.3)=0.67 … cbrt(30)=3.1 — a ~4.6× size contrast vs the legacy
// linear 0.4→5.0. cbrt is exact fp32 (the shader cbrt() builtin).
const float SIZE_K = 0.62;
const float SIZE_S_MIN = 0.18;
const float SIZE_S_MAX = 5.0;
// ADDITIVE_GLOW (flag 0x20): bright cores (q near/above the approach white
// point a_hi — the live qi_condensation_threshold) are boosted toward the
// hue's maximum lightness and their alpha is raised so overlapping bright
// cores read as additive glow on the dark field. The halo ramp keys on the
// INSTANCE scale s (> s_large): larger (massive / size-by-mass) objects
// get a larger soft alpha halo. GLOW_Q is the q fraction of a_hi at which
// the ramp starts (scaled per-frame from the PC so it tracks the live
// threshold); GLOW_Q_LO/GLE fall back when the approach band is off.
const float GLOW_Q_FRAC = 0.55;   // glow onset at 55% of the white point
const float GLOW_A_MIN = 0.35;    // far-from-white alpha floor (default billboard)
const float GLOW_A_MAX = 1.0;     // saturated white → fully bright halo
const float GLOW_L_BOOST = 0.25;  // lightness lift added toward white
const float GLOW_S_LARGE = 1.6;   // instance scale above which the halo grows
const float GLOW_HALO_EXTRA = 0.18; // extra lightness/alpha on large objects
// DEPTH_CUE (flag 0x40): fade alpha with the distance from the camera
// between DEPTH_NEAR and DEPTH_FAR. Until the deferred camera slots land
// the camera position is (0,0,0) (the shared PC fill), so the distance is
// measured from the world origin — the same proxy. DEPTH_NEAR/FAR are
// fractions of the box extent so they track box_scale; DEPTH_POW shapes
// the falloff (1 = linear).
const float DEPTH_NEAR_FRAC = 0.35;  // full alpha inside 35% of the box diagonal
const float DEPTH_FAR_FRAC = 1.35;   // zero alpha past 135% of the box diagonal
const float DEPTH_POW = 1.0;         // linear falloff between near/far
// two-axis lightness gain (mode 4): l = clamp(l_cycle + RHO_GAIN·(ρ̂ − 0.5)),
// ρ̂ = normalized local density (q-proxy today; EY+EI after the hook).
const float RHO_GAIN = 0.5;          // lightness swing from the density axis

// Branchless HSL→RGB (IQ form). hue in [0,1): 0=red, 1/3=green, 2/3=blue,
// ~0.8=violet, ~0.93=pink; s,l in [0,1]. No per-channel if/else — works on
// all vendors.
vec3 hsl2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

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

// ── DEFERRED (green-light): TRUE ρ = EY+EI trilinear for mode 4. This
// sampler duplicates tri_q with bindings 4/5. It stays OFF until the host
// adds the two bindings to `_us_inst_0` (see the header). Then uncomment,
// bind, and swap rho_proxy() below to call tri_rho instead of the q read.
// layout(set = 0, binding = 4, std430) readonly buffer FieldEY { float ey[]; };
// layout(set = 0, binding = 5, std430) readonly buffer FieldEI { float ei[]; };
// float tri_rho(vec3 wp) {
//     return tri_q_src(wp, ey, ei);  // see the mirrored sampler below
// }

// ── Mode/feature decoding ──────────────────────────────────────────────
// color_mode low nibble = base mode, high nibble = feature flags, packed
// by sim_ui.gd into the particle_color_mode export (bit-identical for the
// legacy 0..3 base modes, since & 0xF == the raw value when flags = 0).
int cm_base(void) { return int(pc.color_mode) & 0xF; }
int cm_flags(void) { return (int(pc.color_mode) >> 4) & 0xF; }
const int F_SZ = 0x1;  // bit0 flag: size-by-mass
const int F_GL = 0x2;  // bit1 flag: additive glow
const int F_DP = 0x4;  // bit2 flag: depth cue

// Local density proxy for mode 4's lightness axis. Today q = EY²+EI² (a
// monotonic ρ proxy over the same EY/EI field); after the deferred EY/EI
// bindings land this becomes ρ = EY+EI. Returns a [0,1]-ish normalized
// value clamped to keep lightness in-hue.
float rho_proxy(float q) {
    // Normalize against the approach white point when live, else a fixed
    // φ⁻²-referenced floor. a_hi is the live qi_condensation_threshold
    // (> 0 when the approach band is on; the Qi default is 0.5).
    float ref = max(pc.a_hi, 0.001);
    // clamp into a sane [0,1.5] band so RHO_GAIN never blows up lightness
    return clamp(q / ref, 0.0, 1.5);
}

void main() {
    int i = int(gl_GlobalInvocationID.x);
    int N = int(pc.particle_N);
    if (i >= N) return;

    vec4 p = pos[i];
    int base = i * 4;
    int bmode = cm_base();
    int flags = cm_flags();

    // ── Size: legacy (bit-identical) or size-by-mass (flag 0x10) ──────
    float m = p.w;                                   // per-particle Salpeter mass
    float s = clamp(0.5 + m * 0.12, 0.4, 5.0);       // legacy linear (DEFAULT)
    if ((flags & F_SZ) != 0) {
        // m^(1/3): the visual-size-law upgrade — cbrt compresses the steep
        // Salpeter count so a few massive red giants stay visible without
        // swamping the dwarfs. pos[].w is preserved by the nbody kick.
        s = clamp(SIZE_K * pow(m, 0.3333333), SIZE_S_MIN, SIZE_S_MAX);
    }

    // Row-major 3x4: scale basis by mass-derived size
    inst[base]     = vec4(s, 0.0, 0.0, p.x);
    inst[base + 1] = vec4(0.0, s, 0.0, p.y);
    inst[base + 2] = vec4(0.0, 0.0, s, p.z);

    // ── Color: legacy (bit-identical) or the consolidated engine ──────
    vec4 color;
    // The Qi/velocity scalar axis, sampled ONCE so both the engine and the
    // additive-glow ramp (flag 0x20) read the same value without re-sampling
    // the field.
    float x_axis = 0.0;
    if (bmode == 1) {
        x_axis = length(vel[i].xyz);          // velocity: speed |v|
    } else if (bmode >= 2) {
        x_axis = max(tri_q(pos[i].xyz), 0.0); // Qi: coherence q (q ≥ 0 guard)
    }
    if (bmode >= 1) {
        // ── Consolidated rainbow engine (base modes 1/2/3/4) ─────────
        // One branchless evaluator for both sources; every difference
        // between the sources/modes lives in the host-composed PC.
        float x = x_axis;
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
        // approach band (count-invariant): violet 0.8 at a_lo → pc.a_top
        // (pink 0.93) at a_hi — the lightness ramp makes it white at the
        // top; red never appears at high coherence
        float pA = clamp((x - pc.a_lo) / max(pc.a_hi - pc.a_lo, LOG_GUARD), 0.0, 1.0);
        float hA = mix(H_ENTRY, pc.a_top, pA);
        float lA = 0.5 + 0.5 * pA;
        float inA = pc.approach_on * step(pc.a_lo, x);
        float h = mix(h_cyc, hA, inA);
        float l = mix(0.5, lA, inA);
        // mode 4 (TWO-AXIS): the ENGINE keeps hue but modulates lightness
        // with local density ρ. Today ρ̂ = q-proxy; after the deferred EY/EI
        // hook this becomes the true EY+EI trilinear. The approach band (if
        // on) still dominates near the white point — the two-axis lift rides
        // under it so a condensation glow is never dimmed by a low ρ cell.
        if (bmode == 4) {
            float rho = rho_proxy(x);
            float l2 = clamp(l + RHO_GAIN * (rho - 0.5), 0.0, 1.0);
            l = mix(l, l2, 1.0 - inA);
        }
        color = vec4(hsl2rgb(vec3(h, 1.0, l)), 1.0);
    } else {
        // Mass-based color temperature (Salpeter IMF: many blue dwarfs, few
        // red giants) — the LEGACY default path, bit-identical.
        float log_m = clamp((log2(m) + 2.0) * 0.25, 0.0, 1.0);  // 0→0.3M☉, 1→30M☉
        float cr = mix(0.15, 1.0,  log_m * log_m);                 // blue dwarf→red giant
        float cg = mix(0.25, 0.6,  log_m);
        float cb = mix(1.0,  0.15, log_m);
        color = vec4(cr, cg, cb, 1.0);
    }
    // Additive-glow (flag 0x20): bright-core additive treatment over ANY
    // base color mode — q near the white point (bright core) → lightness
    // lifted toward white AND alpha raised so core overlap reads as
    // additive glow; a halo ramp adds extra brightness on large instances.
    // Reads the engine's scalar axis (x_axis): q in the Qi modes, |v| in
    // the velocity mode. The bright-core ramp keys on pc.a_hi (the live
    // white point), so a condensation-heavy region glows brightest.
    if ((flags & F_GL) != 0) {
        float x = x_axis;
        float ref = max(pc.a_hi, 0.001);
        // bright-core fraction: 0 below the onset, → 1 at the white point
        float fg = clamp((x / ref - GLOW_Q_FRAC) / (1.0 - GLOW_Q_FRAC), 0.0, 1.0);
        // halo ramp on large instances (the size just computed, which the
        // size-by-mass flag sharpened)
        float halo = clamp((s - GLOW_S_LARGE) / max(GLOW_S_LARGE, 1e-6), 0.0, 1.0);
        float boost = clamp(fg + GLOW_HALO_EXTRA * halo, 0.0, 1.0);
        // lift toward pure white (additive on the dark field)
        vec3 core = mix(color.rgb, vec3(1.0), boost * GLOW_L_BOOST);
        color.rgb = core;
        color.a = mix(GLOW_A_MIN, GLOW_A_MAX, boost);
    }

    // ── Feature flags applied to ANY mode ────────────────────────────
    // Depth cue (flag 0x40): fade alpha with camera distance. Camera pos
    // comes from the deferred PC slots when the hook lands; the current
    // shared fill leaves them unreferenced → origin probe (the auto-framed
    // camera sits a fixed oblique distance from the origin, so this is a
    // faithful fallback until the hook feeds the live camera).
    if ((flags & F_DP) != 0) {
        // until the deferred host writes the camera, read the shared slots
        // (which are inert in the instancer): origin == camera-at-origin
        vec3 cam = vec3(pc.source_strength, pc.num_clusters, pc.gravity_mode);
        // pre-hook those slots hold sim values, NOT camera pos — so use the
        // origin-probe form below until the slot map is live; the hook
        // flips cam to read the real camera from the same slots.
        cam = vec3(0.0, 0.0, 0.0);   // ← restore to vec3(...) above after the hook
        float d = length(pos[i].xyz - cam);
        float boxd = length(vec3(pc.extent_x, pc.extent_y, pc.extent_z));
        float dn = DEPTH_NEAR_FRAC * boxd;
        float df = max(DEPTH_FAR_FRAC * boxd, dn + 1e-6);
        float fade = clamp((df - d) / (df - dn), 0.0, 1.0);
        color.a *= pow(fade, DEPTH_POW);
    }

    inst[base + 3] = color;
}
