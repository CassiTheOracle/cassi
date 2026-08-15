#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 13 floats (52 B); set 0: bindings 0-2
#version 450
// Cassi q-histogram — the AUTO-ALIGN sampler. Bins the coherence q sampled
// AT PARTICLE POSITIONS (the exact periodic trilinear convention of
// cassi_instancer.glsl's tri_q) into a log-spaced histogram, so the host can
// re-fit the Qi color band to the live p1/p99 spread. This keeps the colors
// aligned when the coherence grows fast (e.g. the Meshless gravity mode),
// where a fixed band saturates.
//
// Runs once per rendered frame while auto_align_colors is on. Particles are
// strided (pc.stride) to keep the atomic traffic light; the host resets the
// bins every alignment cadence and reads back 512 B.
//
// Bindings (set 0): 0 = Positions (vec4/particle, w = mass), 1 = q field
// (grid_N³ floats), 2 = histogram (BINS floats, float-atomic counts —
// GL_EXT_shader_atomic_float, verified on this rig in cassi_mass_deposit.glsl).
// PC: N_f (grid), N_p (particles), stride, lo, hi, BINS_f, enabled, extent_x/y/z.
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) readonly buffer FieldQ { float qv[]; };
layout(set = 0, binding = 2, std430) coherent buffer Hist { float bins[]; };

layout(push_constant, std430) uniform PC {
    float N_f;      // grid_N (the field resolution)
    float N_p;      // particle count
    float stride;   // particle subsample stride
    float lo;       // histogram log-range floor (q below lo → bin 0)
    float hi;       // histogram log-range ceiling (q above hi → bin B-1)
    float BINS_f;   // bin count (128)
    float enabled;  // 0/1 gate (host toggles live)
    float extent_x; // per-axis box half-extents — the instancer's mapping
    float extent_y;
    float extent_z;
    float win_x;    // movable home-window origin (perf-decomp 2026-08-15):
    float win_y;    // subtracted in the world→grid map; zero = legacy box
    float win_z;
} pc;

const float LOG_GUARD = 1e-9;

int idx3(int i, int j, int k) {
    int N = int(pc.N_f);
    return i + N * (j + N * k);
}

float tri_q(vec3 wp) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 inv_ext = 1.0 / max(ext, vec3(0.0001));
    vec3 win = vec3(pc.win_x, pc.win_y, pc.win_z);
    vec3 gc = ((wp - win) * inv_ext) * hn + hn;
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
    if (pc.enabled < 0.5) return;
    int n = int(pc.N_p);
    int s = max(int(pc.stride), 1);
    int B = int(pc.BINS_f);
    if (B <= 0) return;
    int i = int(gl_GlobalInvocationID.x) * s;
    if (i >= n) return;
    float q = tri_q(pos[i].xyz);
    if (q <= 0.0) {
        atomicAdd(bins[0], 1.0);   // background/void → the lowest bin
        return;
    }
    float llo = log(max(pc.lo, LOG_GUARD));
    float lhi = log(max(pc.hi, pc.lo * 1.001));
    float t = clamp((log(q) - llo) / max(lhi - llo, 1e-9), 0.0, 1.0);
    int b = min(int(t * float(B - 1)), B - 1);
    atomicAdd(bins[b], 1.0);
}
