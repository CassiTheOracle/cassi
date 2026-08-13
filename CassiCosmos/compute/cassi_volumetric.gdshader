shader_type spatial;
render_mode unshaded, cull_disabled;
// ═══════════════════════════════════════════════════════════════════════════
// Voxel Volume Raymarcher — the Cassi Qi field, the "recreate reality" leap.
//
// A view-per-pixel march through a 3D RG float texture carrying the two-fluid
// state (R = EY, G = EI), inside the φ-aspect box [−E, +E]. Emission color uses
// the EXACT particle palette (`compute/cassi_instancer.glsl`): the Qi-rainbow
// `hsl2rgb`, the white-hot approach band (violet 0.8 → pink 0.93 at the white
// point — red never appears at high coherence; `cassi_sim.gd:2461`), and — below the approach — the log Qi cycle. Absorption/scatter uses
// ρ = EY + EI (Beer–Lambert); a Qi-coherence glow term lifts emission toward
// white near the white point; camera-distance fog blends the residual
// transmittance toward the near-black clear color.
//
// CAMERA GEOMETRY IS PASSED AS UNIFORMS (not Godot builtins) so the host's
// verify scene and research/volumetric/volumetric_verify.py compute the EXACT
// same rays — the two-side pixel L2 gate rests on this lockstep.
//
// Uniforms mirror the verify analytic field / palette (§5, §3 of the design):
//   u_box_half     = (E_x, E_y, E_z)    the φ-aspect half-extents
//   u_cam_pos      = camera world position
//   u_cam_forward/right/up = orthonormal camera basis (rd = normalize(f + x·r·t·avg + y·u·t))
//   u_tan_half_fov  = tan(fov/2)         (perspective)
//   u_img_size      = viewport pixels (x,y) — for NDC reconstruction
//   u_steps         = fixed march step count per ray (ds = (t1−t0)/steps)
//   u_field         = sampler3D RG (R=EY, G=EI)
//   a_lo/a_hi/a_top/approach_on/q_lo/q_hi/slope = palette (see design §3)
//   σ_abs, σ_em     = extinction / emission coefficients
//   σ_fog, fog_color= cave fog constants
//   GLOW_GAIN       = Qi-coherence glow amount (0 = off)
// ═══════════════════════════════════════════════════════════════════════════

uniform vec3  u_box_half = vec3(1.618, 1.0, 2.618);
uniform vec3  u_cam_pos = vec3(-4.5, 0.8, 2.6);
uniform vec3  u_cam_forward = vec3(1.0, 0.0, 0.0);
uniform vec3  u_cam_right   = vec3(0.0, 0.0, 1.0);
uniform vec3  u_cam_up      = vec3(0.0, 0.0, 0.0);
uniform float u_tan_half_fov = 0.5206;   // tan(55°/2)
uniform vec2  u_img_size = vec2(256.0, 256.0);
uniform int   u_steps = 224;
uniform sampler3D u_field;
uniform float a_lo = 0.2;
uniform float a_hi = 0.5;
uniform float a_top = 0.93;   // pink at the white point (cassi_sim.gd:2461 — red never appears at high coherence)
uniform float approach_on = 1.0;
uniform float q_lo = 0.0002;
uniform float q_hi = 0.001;
uniform float slope = 0.621335;   // 1/ln5
uniform float s_abs = 2.0;
uniform float s_em  = 0.31;   // scaled so peak linear radiance ~ 1.0 (keeps the 8-bit verify frame unsaturated, so the pink gate stays chromatic)
uniform float s_fog = 0.0;
uniform vec3  fog_color = vec3(0.0, 0.0, 0.01);
uniform float GLOW_GAIN = 0.0;
uniform float EPS_T = 0.001;

const float H_ENTRY = 0.8;      // violet — the approach entry hue (instancer:126)
const float LOG_GUARD = 1e-9;
const float PINK_TOP = 0.93;    // the approach top hue (cassi_sim.gd:2461 a_top) — pink, no red at high coherence

// Branchless HSL→RGB (IQ form) — VERBATIM from cassi_instancer.glsl:168-171.
vec3 hsl2rgb(vec3 c) {
    vec3 rgb = clamp(abs(mod(c.x * 6.0 + vec3(0.0, 4.0, 2.0), 6.0) - 3.0) - 1.0, 0.0, 1.0);
    return c.z + c.y * (rgb - 0.5) * (1.0 - abs(2.0 * c.z - 1.0));
}

// Slab intersect the φ-aspect box [−E, E] against ray (ro, rd).
// Returns true + (t0, t1) clipping the ray to the volume; false = miss.
bool box_intersect(vec3 ro, vec3 rd, vec3 half, out float t0, out float t1) {
    vec3 inv = 1.0 / max(abs(rd), vec3(1e-9));
    // sign-correction for the reciprocal (the slab crossing t=(plane−ro)/rd
    // needs the ray's SIGN, not its magnitude)
    inv = mix(inv, -inv, lessThan(rd, vec3(0.0)));
    vec3 n0 = (-half - ro) * inv;
    vec3 n1 = ( half - ro) * inv;
    vec3 lo = min(n0, n1);
    vec3 hi = max(n0, n1);
    t0 = max(max(lo.x, lo.y), lo.z);
    t1 = min(min(hi.x, hi.y), hi.z);
    return t0 <= t1;
}

// sample the analytic-equivalent field from the 3D texture:
//   EY = R, EI = G  (world p → [0,1]³ texture uv)
vec3 sample_field(vec3 p) {
    vec3 uv = (p / u_box_half) * 0.5 + 0.5;
    return texture(u_field, clamp(uv, 0.001, 0.999)).rgb;
}

void fragment() {
    // ── ray reconstruction (pinhole, uniform camera — mirror of the NumPy) ──
    vec3 ro = u_cam_pos;
    vec3 fwd = normalize(u_cam_forward);
    vec3 rgt = normalize(u_cam_right);
    vec3 upv = normalize(u_cam_up);
    // NDC in [−1,1] with y up; FRAGCOORD origin top-left. Viewport y runs down.
    vec2 ndc = vec2(
        (FRAGCOORD.x / u_img_size.x) * 2.0 - 1.0,
        (1.0 - FRAGCOORD.y / u_img_size.y) * 2.0 - 1.0);
    float aspect = u_img_size.x / u_img_size.y;
    vec3 rd = normalize(fwd + rgt * (ndc.x * u_tan_half_fov * aspect)
                             + upv * (ndc.y * u_tan_half_fov));

    vec3 result_px = fog_color;        // default: pure camera fog (box miss)

    // ── clip to the φ-box ──
    float t0, t1;
    if (box_intersect(ro, rd, u_box_half, t0, t1)) {
        t0 = max(t0, 0.0);
        if (t1 > t0) {
            float ds = (t1 - t0) / float(u_steps);
            float trans = 1.0;               // transmittance
            vec3  lum = vec3(0.0);           // accumulated radiance

            // ── march ──
            for (int i = 0; i < u_steps; i++) {
                vec3 p = ro + rd * (t0 + (float(i) + 0.5) * ds);
                vec3 f = sample_field(p);
                float EY = max(f.r, 0.0);
                float EI = max(f.g, 0.0);
                float q = max(EY * EY + EI * EI, 0.0);
                float rho = max(EY + EI, 0.0);

                // palette (exact instancer semantics, §3)
                float pA = clamp((q - a_lo) / max(a_hi - a_lo, LOG_GUARD), 0.0, 1.0);
                float hA = H_ENTRY + (a_top - H_ENTRY) * pA;
                float lA = 0.5 + 0.5 * pA;
                float inA = approach_on * step(a_lo, q);
                float h_cyc = mod(slope * log(max((q + LOG_GUARD) / (q_lo + LOG_GUARD), LOG_GUARD)), 1.0);  // Qi cycle: full hue circle, span 1.0 (instancer span_total)
                float h = mix(h_cyc, hA, inA);
                float l = mix(0.5, lA, inA);
                vec3 emit = hsl2rgb(vec3(h, 1.0, l));

                // Qi-coherence glow (optional; lift toward white near the white point)
                float g = clamp((q / max(a_hi, LOG_GUARD)) * GLOW_GAIN, 0.0, 1.0);
                emit = mix(emit, vec3(1.0), g);

                // Beer–Lambert first-order front-to-back
                float st = s_abs * rho + s_fog;
                float dtrans = exp(-st * ds);
                lum += trans * (s_em * emit) * ds;
                trans *= dtrans;
                if (trans < EPS_T) break;
            }

            // camera-distance fog on the surviving transmittance
            result_px = lum + trans * fog_color;
        }
    }
    ALBEDO = vec3(result_px);
}
