#[compute]
#version 450
// The mass-deposit fixed-point accumulator (cassi_mass_deposit.glsl
// binding 2, SCALE = 2^24, 4×uint8-digit sums packed as uvec4 per cell):
// mode 3 (clear) zeroes it WITH rho every step so the deposit never
// accumulates stale digits and the convert pass reflects only this step.
// Plain uvec4 stores — no extension needed.
// Cassi Spectral Poisson Solver — ∇²Φ = ρ_mass, Φ̂ = −ρ̂/k², k = 0 nulled.
//
// Convention (identical to the repo's Python solver,
// two-fluid/cassi_two_fluid_3d_gpu.py, `_poisson`):
//   k_i = 2π·fftfreq(N)/L_i, L_i = 2·extent_i (per-axis torus periods —
//   the φ-aspect box, GRID_LAYOUT.md; cube: L = 2·extent)
//   fftfreq labels: n ≤ N/2 → +n, n > N/2 → n − N   (Nyquist at +N/2 only)
//   Φ̂(k=0) = 0;  Φ̂(k≠0) = −ρ̂/k²
//
// The FFT is a hand-rolled Stockham autosort complex FFT (natural order in
// and out; no bit-reversal), one axis per dispatch:
//   stage s: n_sub = 2^s, half = 2^(s−1), j = e & (n_sub−1), block = e >> s
//   out[block·n_sub + j]      = even + odd·ω^j
//   out[block·n_sub + j+half] = even − odd·ω^j
//   ω = exp(∓2πi·j/n_sub)     (forward −, inverse +)
// Forward transforms are unnormalized; each inverse pass scales by 1/N.
//
// MULTI-ROW LAYOUT (the 2026-08-14 speedup): one workgroup of 256 threads
// processes R = 256/N rows at once (R = 4/2/1 for N = 64/128/256; N = 32
// cascade level → R = 8). Thread t handles row r = t/N, element e = t%N of
// the block's R rows; the 256-slot shared array holds R rows of N elements.
// The per-element arithmetic is IDENTICAL to the old one-row-per-workgroup
// schedule (same bitrev, same twiddles, same butterfly order), so the
// transform reproduces the old one bit-for-bit — the win is 4× the row
// throughput per workgroup/barrier at N=64 (the old layout ran 256-slot
// butterflies for 64-element rows, wasting 3/4 of the threads), 2× at 128,
// and full occupancy everywhere (no idle threads, no guard-only threads).
//
// Dispatch sequence (host, one compute list, one submit):
//   clear → load+x → fft(y) → fft(z) → [kspace+inv-z] → ifft(y) → ifft(x)
// The load and the forward-x pass are FUSED (mode 4 reads ρ directly into
// shared); the k-space multiply and the inverse-z pass are FUSED (mode 5
// applies −1/k² per element while loading the z-row). 6 dispatches per
// solve instead of 8 — 2 fewer global barriers per solve.
// After the last pass the REAL part of the buffer holds Φ (imag ~ 0);
// the N-body shader samples it directly (binding 5 of its set 0).
//
// Modes (pc.mode):
//   0 = load:   ρ (float, deposited by float-atomic CIC) → complex buffer
//               (kept for external direct users; the engine chain uses 4)
//   1 = fft:    one multi-row Stockham axis pass (pc.axis 0/1/2,
//               pc.direction 0 fwd / 1 inv) — dispatch (N, N/R, 1)
//   2 = kspace: Φ̂ = −ρ̂/k², k = 0 nulled  (needs pc.extent_x/y/z; kept
//               for external direct users; the engine chain uses 5)
//   3 = clear:  ρ = 0, telemetry reset (per-step GPU clear) — TWO cells
//               per thread (dispatch (N, N/2, 1); (N, N, 1) also works —
//               the gid ≥ nc/2 threads just idle out)
//   4 = load+x: fused mode-0 + forward-x (the chain's first FFT pass)
//   5 = inv-z+kspace: fused kspace multiply + inverse-z (chain's first
//               inverse pass; direction must be 1)
//
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer FFTBuf { vec2 f[]; };
layout(set = 0, binding = 1, std430) buffer MassDensity { float rho[]; };
layout(set = 0, binding = 2, std430) buffer Telemetry { uint tel[]; };
// The mass-deposit fixed-point accumulator (see the note at the top):
// mode 3 (clear) zeroes it WITH rho every step so the deposit never
// accumulates stale digits and the convert pass reflects only this step.
layout(set = 0, binding = 3, std430) coherent buffer MassDensityFix {
    uvec4 fix[];
};

layout(push_constant, std430) uniform PC {
    float N_f;
    float axis;        // fft mode: 0 = x, 1 = y, 2 = z
    float direction;   // fft mode: 0 = forward, 1 = inverse (scaled 1/N)
    float mode;        // 0 = load, 1 = fft, 2 = kspace, 3 = clear, 4 = load+x, 5 = inv-z+kspace
    float extent_x;    // kspace mode: per-axis grid half-extents
    float extent_y;    // (L_i = 2·extent_i = 2·aspect_i·1.5·cluster_radius)
    float extent_z;
} pc;

const float PI = 3.14159265358979323846;
const float TWO_PI = 6.28318530717958647693;

shared vec2 sdata[2][256];
// Forward twiddle table (255 entries, exp(−2πi·jj/2^s) for s ∈ [1..8],
// jj ∈ [0, 2^(s−1))): built once per pass — one sin/cos per thread instead
// of one per thread per stage. Layout: offset[s] = 2^(s−1) − 1.
shared vec2 tw_tab[255];

// ── Mode 0: load ρ into the complex buffer ─────────────────────────────
void load_main() {
    int nc = int(pc.N_f) * int(pc.N_f) * int(pc.N_f);
    // Cells modes dispatch (N, N, 1) with 256 threads/group: x covers one
    // 256-thread group (N·256 threads), y walks the groups — row-major
    // cell index = x + y·(N·256), exactly N³ cells. (The naive
    // x + y·N covers only N² + 255N cells — the Vulkan dispatch landmine
    // that drops every 256th group at N=256.)
    uint gid = gl_GlobalInvocationID.x
             + gl_GlobalInvocationID.y * uint(int(pc.N_f) * 256);
    if (int(gid) >= nc) return;
    f[gid] = vec2(rho[gid], 0.0);  // ρ is already a float (float-atomic deposit)
}

// ── Modes 1/4/5: multi-row Stockham FFT along one axis ────────────────
// R = 256/N rows per workgroup; dispatch (N, N/R, 1) — workgroup count
// N²/R, block id = wg.x + wg.y·N (the same 2D enumeration as the old
// (N, N, 1) row dispatch, compressed by R in y). Thread t → row r = t/N,
// element e = t%N. N-generic radix-2: any power of 2 with 32 ≤ N ≤ 256
// (R = 256/N ∈ [1, 8]; the shared array always holds R·N = 256 slots).
//
// This is a radix-2 DIT schedule: butterflies run over blocks that double
// each stage, pairing elements jj and jj + halfn with twiddle ω^jj.
// DIT REQUIRES THE INPUT IN BIT-REVERSED ORDER: the row is loaded into
// shared memory with the local index bit-reversed (log2(N) bits, per
// axis — the reversal permutes positions WITHIN the row). The same
// reversed load is applied on the inverse side, so the transform pair
// closes: FFT⁻¹(FFT(x)) = x.
//
// Barrier discipline: EVERY one of the 256 local threads reaches every
// barrier (all threads are active in every stage — no guards except the
// butterfly's `jj < halfn` write-selector, whose inactive half still hits
// the barriers). The whole-workgroup early return (block ≥ N²/R) fires
// uniformly across the group, so it can never strand threads at a barrier.
int bitrev(int x, int bits) {
    int r = 0;
    for (int b = 0; b < bits; b++) {
        r = (r << 1) | (x & 1);
        x >>= 1;
    }
    return r;
}

// Returns the base index of `row`'s first element and the stride along
// the transform axis (mode 1/4/5 share the row enumeration).
void row_base_stride(int row, int N, int axis, out int base, out int stride) {
    int r0 = row % N;
    int r1 = row / N;
    if (axis == 0) { base = N * r0 + N * N * r1; stride = 1; }
    else if (axis == 1) { base = r0 + N * N * r1; stride = N; }
    else { base = r0 + N * r1; stride = N * N; }
}

// k² for one cell (identical formula to the old kspace pass — the
// multiply MUST stay `−f/k2` (division, one rounding) to reproduce the
// old chain bit-for-bit; a reciprocal-multiply would differ by ~1 ulp).
float k2_of_cell(int cell, int N) {
    int i = cell % N;
    int j = (cell / N) % N;
    int k = cell / (N * N);
    int kx = (i <= N / 2) ? i : i - N;
    int ky = (j <= N / 2) ? j : j - N;
    int kz = (k <= N / 2) ? k : k - N;
    float kxw = TWO_PI * float(kx) / (2.0 * pc.extent_x);
    float kyw = TWO_PI * float(ky) / (2.0 * pc.extent_y);
    float kzw = TWO_PI * float(kz) / (2.0 * pc.extent_z);
    return kxw * kxw + kyw * kyw + kzw * kzw;
}

// mode 1: plain axis pass on the complex buffer.
// mode 4: fused load ρ + forward-x (axis forced 0, reads rho[]).
// mode 5: fused kspace multiply + inverse-z (axis forced 2, applies the
//         −1/k² factor to every element while loading the z-row).
void fft_main() {
    int N = int(pc.N_f);
    if (N < 2 || (N & (N - 1)) != 0 || N > 256) return;  // radix-2, ≤ 256
    int bits = 0;
    for (int n = N; n > 1; n >>= 1) bits++;
    int R = 256 / N;                       // rows per workgroup (N ≤ 256 → ≥ 1)
    int axis = int(pc.axis);
    if (pc.mode > 4.5) {                   // mode 5: kspace+inv-z
        axis = 2;
    }
    // One workgroup per R rows: dispatch (N, N/R, 1) — block id
    // = wg.x + wg.y·N walks N²/R blocks in row-major order.
    uint block = gl_WorkGroupID.x + gl_WorkGroupID.y * uint(N);
    if (block >= uint(N * N / R)) return;  // whole-group early return (uniform)
    int t = int(gl_LocalInvocationID.x);
    int r = t / N;                         // row within the block
    int e = t % N;                         // element within the row
    int row = int(block) * R + r;

    int base;
    int stride;
    row_base_stride(row, N, axis, base, stride);
    int gidx = base + e * stride;

    // Load the block's rows into shared memory, bit-reversed per row.
    if (pc.mode > 4.5) {
        // mode 5: the k-space multiply rides in on the load (the first
        // inverse pass — the full forward spectrum is already in f[]).
        // The element this thread loads sits at the BIT-REVERSED offset
        // (the DIT load permutation); k² belongs to that PHYSICAL cell
        // (the old chain multiplied every physical cell in mode 2 BEFORE
        // the inverse's bit-reversed load). `−v/k2` with k = 0 nulled —
        // the EXACT old kspace arithmetic, fused into the inverse-z load.
        int cell = base + bitrev(e, bits) * stride;
        vec2 v = f[cell];
        float k2 = k2_of_cell(cell, N);
        if (k2 > 0.0) {
            v = -v / k2;
        } else {
            v = vec2(0.0);  // k = 0 mode nulled (mean of Φ is unphysical)
        }
        sdata[0][t] = v;
    } else if (pc.mode > 3.5) {
        // mode 4: fused load — read ρ directly (imag = 0), no separate
        // load pass and no intermediate global write before the x pass.
        sdata[0][t] = vec2(rho[base + bitrev(e, bits) * stride], 0.0);
    } else {
        sdata[0][t] = f[base + bitrev(e, bits) * stride];
    }
    // Build the forward twiddle table (thread t computes entry t). Shares
    // the load barrier: the table writes are visible to every butterfly.
    if (t < 255) {
        int s = 1;
        for (int q = 2; q <= 8; q++) {
            if (t >= (1 << (q - 1)) - 1) s = q;
        }
        int jj = t - ((1 << (s - 1)) - 1);
        float ang = TWO_PI * float(jj) / float(1 << s);
        tw_tab[t] = vec2(cos(ang), -sin(ang));  // forward: exp(−iθ)
    }
    barrier();

    int rbank = 0;
    int wbank = 1;
    for (int s = 1; s <= bits; s++) {
        int n_sub = 1 << s;
        int halfn = 1 << (s - 1);   // 'half' is a reserved word in GLSL
        int jj = e & (n_sub - 1);
        int blk = e >> s;           // butterfly block WITHIN the row
        if (jj < halfn) {
            int slot = r * N + blk * n_sub + jj;
            vec2 even = sdata[rbank][slot];
            vec2 odd  = sdata[rbank][slot + halfn];
            vec2 tw = tw_tab[(1 << (s - 1)) - 1 + jj];
            if (pc.direction > 0.5) tw.y = -tw.y;  // inverse: conjugate
            vec2 o = vec2(odd.x * tw.x - odd.y * tw.y, odd.x * tw.y + odd.y * tw.x);
            sdata[wbank][slot] = even + o;
            sdata[wbank][slot + halfn] = even - o;
        }
        // ONE barrier per stage: it orders every thread's stage-s writes
        // (bank w) before the stage-(s+1) reads of bank w, and every
        // thread's stage-s reads of bank r before the stage-(s+1) writes
        // to bank r (the swap flips the banks). The old second barrier
        // after the swap was redundant with the double buffer.
        barrier();
        int tmp = rbank; rbank = wbank; wbank = tmp;
    }

    float scale = (pc.direction > 0.5) ? 1.0 / float(N) : 1.0;
    f[gidx] = sdata[rbank][t] * scale;
}

// ── Mode 2: k-space multiply Φ̂ = −ρ̂/k² (k = 0 nulled) ────────────────
void kspace_main() {
    int N = int(pc.N_f);
    int nc = N * N * N;
    uint gid = gl_GlobalInvocationID.x
             + gl_GlobalInvocationID.y * uint(N * 256);
    if (int(gid) >= nc) return;
    float k2 = k2_of_cell(int(gid), N);
    if (k2 > 0.0) {
        f[gid] = -f[gid] / k2;
    } else {
        f[gid] = vec2(0.0);  // k = 0 mode nulled (mean of Φ is unphysical)
    }
}

// ── Mode 3: per-step GPU clear — ρ = 0, telemetry reset ────────────────
// Two cells per thread (gid and gid + nc/2) so the dispatch is (N, N/2, 1)
// — half the threads of the old (N, N, 1) clear. The (N, N, 1) shape still
// works: threads with gid ≥ nc/2 idle out and the coverage is unchanged.
// Required so chained steps inside ONE compute list start from a clean
// density and telemetry state (CPU buffer_update is illegal mid-list).
void clear_main() {
    int nc = int(pc.N_f) * int(pc.N_f) * int(pc.N_f);
    uint gid = gl_GlobalInvocationID.x
             + gl_GlobalInvocationID.y * uint(int(pc.N_f) * 256);
    if (gid >= uint(nc / 2)) return;   // nc even (radix-2 grid)
    rho[gid] = 0.0;                    // float buffer (written by the deposit convert)
    rho[gid + uint(nc / 2)] = 0.0;
    fix[gid] = uvec4(0);               // digit-sum accumulator — zeroed WITH rho so
    fix[gid + uint(nc / 2)] = uvec4(0); // the convert never accumulates stale digits
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
    else if (mode == 3) clear_main();
    else fft_main();  // modes 4/5: fused passes (the mode branch inside fft_main)
}
