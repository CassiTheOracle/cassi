#[compute]
#version 450
// Cassi Spectral Poisson Solver — ∇²Φ = ρ_mass, Φ̂ = −ρ̂/k², k = 0 nulled.
//
// Convention (identical to the repo's Python solver,
// two-fluid/cassi_two_fluid_3d_gpu.py, `_poisson`):
//   k_1d = 2π·fftfreq(N)/L with L = 2·extent (periodic box [−extent, +extent])
//   fftfreq labels: n ≤ N/2 → +n, n > N/2 → n − N   (Nyquist at +N/2 only)
//   Φ̂(k=0) = 0;  Φ̂(k≠0) = −ρ̂/k²
//
// The FFT is a hand-rolled Stockham autosort complex FFT (natural order in
// and out; no bit-reversal), one axis per dispatch:
//   stage s: n_sub = 2^s, half = 2^(s−1), j = t & (n_sub−1), block = t >> s
//   out[block·n_sub + j]      = even + odd·ω^j
//   out[block·n_sub + j+half] = even − odd·ω^j
//   ω = exp(∓2πi·j/n_sub)     (forward −, inverse +)
// Forward transforms are unnormalized; each inverse pass scales by 1/N.
//
// Dispatch sequence (host, one compute list, one submit):
//   load → fft(x) → fft(y) → fft(z) → kspace → ifft(z) → ifft(y) → ifft(x)
// After the last pass the REAL part of the buffer holds Φ (imag ~ 0);
// the N-body shader samples it directly (binding 5 of its set 0).
//
// Modes (pc.mode):
//   0 = load:   ρ (uint float-bits) → complex buffer (imag = 0)
//   1 = fft:    one Stockham axis pass (pc.axis 0/1/2, pc.direction 0 fwd / 1 inv)
//   2 = kspace: Φ̂ = −ρ̂/k², k = 0 nulled  (needs pc.extent)

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer FFTBuf { vec2 f[]; };
layout(set = 0, binding = 1, std430) buffer MassDensity { uint rho[]; };
layout(set = 0, binding = 2, std430) buffer Telemetry { uint tel[]; };

layout(push_constant, std430) uniform PC {
    float N_f;
    float axis;        // fft mode: 0 = x, 1 = y, 2 = z
    float direction;   // fft mode: 0 = forward, 1 = inverse (scaled 1/N)
    float mode;        // 0 = load, 1 = fft, 2 = kspace, 3 = clear
    float extent;      // kspace mode: grid half-extent (L = 2·extent)
} pc;

const float PI = 3.14159265358979323846;
const float TWO_PI = 6.28318530717958647693;

shared vec2 sdata[2][64];

// ── Mode 0: load ρ into the complex buffer ─────────────────────────────
void load_main() {
    int nc = int(pc.N_f) * int(pc.N_f) * int(pc.N_f);
    uint gid = gl_GlobalInvocationID.x;
    if (int(gid) >= nc) return;
    f[gid] = vec2(uintBitsToFloat(rho[gid]), 0.0);
}

// ── Mode 1: Stockham FFT along one axis ────────────────────────────────
// One workgroup per row: gid.x = row id, local thread t = element in row.
// Specialized to N = 64 (local_size 64, 6 stages); N is an export of the
// sim and the pipeline is rebuilt on reinit, so a mismatch is impossible
// unless grid_N is changed without reinit — guard anyway.
void fft_main() {
    int N = int(pc.N_f);
    if (N != 64) return;  // FFT kernels are specialized to N = 64
    // One workgroup per row: the ROW is the workgroup index (each workgroup
    // of 64 threads holds one row in shared memory), NOT gl_GlobalInvocationID
    // (which is the cell index — wrong here: the butterflies would mix
    // elements of 64 different rows).
    uint row = gl_WorkGroupID.x;
    if (row >= uint(N * N)) return;
    int t = int(gl_LocalInvocationID.x);

    int axis = int(pc.axis);
    int r0 = int(row) % N;
    int r1 = int(row) / N;
    int base;
    int stride;
    if (axis == 0) { base = N * r0 + N * N * r1; stride = 1; }
    else if (axis == 1) { base = r0 + N * N * r1; stride = N; }
    else { base = r0 + N * r1; stride = N * N; }
    int gidx = base + t * stride;

    sdata[0][t] = f[gidx];
    barrier();

    int r = 0;
    int w = 1;
    for (int s = 1; s <= 6; s++) {
        int n_sub = 1 << s;
        int halfn = 1 << (s - 1);   // 'half' is a reserved word in GLSL
        int jj = t & (n_sub - 1);
        int block = t >> s;
        if (jj < halfn) {
            vec2 even = sdata[r][block * n_sub + jj];
            vec2 odd  = sdata[r][block * n_sub + jj + halfn];
            float ang = TWO_PI * float(jj) / float(n_sub);
            float sn = sin(ang);
            if (pc.direction < 0.5) sn = -sn;  // forward: exp(−iθ)
            vec2 tw = vec2(cos(ang), sn);
            vec2 o = vec2(odd.x * tw.x - odd.y * tw.y, odd.x * tw.y + odd.y * tw.x);
            sdata[w][block * n_sub + jj] = even + o;
            sdata[w][block * n_sub + jj + halfn] = even - o;
        }
        barrier();
        int tmp = r; r = w; w = tmp;
        barrier();
    }

    float scale = (pc.direction > 0.5) ? 1.0 / float(N) : 1.0;
    f[gidx] = sdata[r][t] * scale;
}

// ── Mode 2: k-space multiply Φ̂ = −ρ̂/k² (k = 0 nulled) ────────────────
void kspace_main() {
    int N = int(pc.N_f);
    int nc = N * N * N;
    uint gid = gl_GlobalInvocationID.x;
    if (int(gid) >= nc) return;

    int i = int(gid) % N;
    int j = (int(gid) / N) % N;
    int k = int(gid) / (N * N);
    int kx = (i <= N / 2) ? i : i - N;
    int ky = (j <= N / 2) ? j : j - N;
    int kz = (k <= N / 2) ? k : k - N;

    float L = 2.0 * pc.extent;
    float k2 = float(kx * kx + ky * ky + kz * kz) * (TWO_PI / L) * (TWO_PI / L);
    if (k2 > 0.0) {
        f[gid] = -f[gid] / k2;
    } else {
        f[gid] = vec2(0.0);  // k = 0 mode nulled (mean of Φ is unphysical)
    }
}

// ── Mode 3: per-step GPU clear — ρ = 0, telemetry reset ────────────────
// Required so chained steps inside ONE compute list start from a clean
// density and telemetry state (CPU buffer_update is illegal mid-list).
void clear_main() {
    int nc = int(pc.N_f) * int(pc.N_f) * int(pc.N_f);
    uint gid = gl_GlobalInvocationID.x;
    if (int(gid) >= nc) return;
    rho[gid] = 0u;
    if (gid < 8u) {
        // [0..2] saturation/guard counters → 0
        // [3] q_min → +inf, [4] q_max → 0, [5] π/ρ_min → +inf, [6] π/ρ_max → 0
        tel[0] = 0u; tel[1] = 0u; tel[2] = 0u;
        tel[3] = 0x7F800000u;
        tel[4] = 0u;
        tel[5] = 0x7F800000u;
        tel[6] = 0u;
        tel[7] = 0u;
    }
}

void main() {
    int mode = int(pc.mode);
    if (mode == 0) load_main();
    else if (mode == 1) fft_main();
    else if (mode == 2) kspace_main();
    else clear_main();
}
