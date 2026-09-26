#[compute]
#version 450
// Cassi Audio Reduce — the field → cascade-meter readout for the Cassi
// Synth (a real-time sonification of the two-fluid universe).
//
// ONE pass over the grid computing a TINY (~16 floats) summary that a
// GDScript node reads back at a LOW cadence (100–200 ms) and drives a
// φ-tempered harmonic bank with. The meter is deliberately FFT-free:
// the per-rung "structure statistic" is the L2 difference of two
// box-blurred means of q = EY² + EI² at box half-width b_m = round(φ^m)
// and 2·b_m — a local band-pass at the rung's scale. (µ_b − µ_2b)² is a
// proper per-scale detail energy; the L2 form localizes a monochromatic
// plane wave to its matching rung (n≈8→b=2, n≈1→b=8 at N=64), which the
// verify scene gates on. See research/meshless/synth_design.md.
//
// Cost: R + 3 tiny passes (a 3D inclusive-prefix SAT build + one reduce),
// all at the 100–200 ms cadence. The readback is 64 bytes. NO per-frame
// or large readbacks (the stutter lesson).
//
// Buffers (uniform set 0):
//   [0] sat    — N³ floats, 3D inclusive prefix sum of q (SAT workspace)
//   [1] ey     — N³ floats, field Yang component (read)
//   [2] ei     — N³ floats, field Yin component (read)
//   [3] out    — OUT_N floats, the meter readout (atomic float accumulators)
//
// Pass modes (pc.mode):
//   0  x-scan  — sat = inclusive prefix of q along +i (also computes q)
//   1  y-scan  — sat = inclusive prefix along +j of the x-scanned sat
//   2  z-scan  — sat = inclusive prefix along +k  → full 3D SAT of q
//   3  reduce  — per-cell rung energies + totals via atomic floatAdd
//
// OUT_N = 16 floats:
//   out[0]   = Σq (total energy)
//   out[1]   = ΣEY
//   out[2]   = ΣEI
//   out[3]   = N as float
//   out[4+r] = rung r detail energy, r = 0..R-1
//   out[8]   = R as float
//   out[9..] = spare (zero)
//
// The rung ladder (R=4 on N=64 — GRID-LIMITED; see synth_design.md §2
// for why the design's R≈7 coarse boxes alias on a 64³ grid):
//   r : b_m   freq n = f0·φ^r (f0 = 55 Hz)
//   0 : 2     ~ 55 Hz
//   1 : 3     ~ 89 Hz
//   2 : 4     ~ 144 Hz
//   3 : 8     ~ 233 Hz
// (frequencies map to the audio bank in cassi_synth.gd, not here.)

#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

#define R 4
#define OUT_N 16

layout(set = 0, binding = 0, std430) coherent buffer SAT    { float sat[]; };
layout(set = 0, binding = 1, std430) readonly  buffer FeldY { float ey[]; };
layout(set = 0, binding = 2, std430) readonly  buffer FeldI { float ei[]; };
layout(set = 0, binding = 3, std430) coherent   buffer Out   { float out_b[]; };

layout(push_constant, std430) uniform PC {
    float mode_f;
    float N_f;
    float _pad0;
    float _pad1;
} pc;

const int BOX[R] = int[](2, 3, 4, 8);

int N()      { return int(pc.N_f); }
int idx3(int i, int j, int k) { int n = N(); return i + n * (j + n * k); }

// ── Per-axis periodic half-open interval [lo, hi) → ≤2 non-wrap sub-ints ──
// Returns the count; fills (a0,b0),(a1,b1) as half-open [a,b) within [0,N).
int split(int lo, int hi, out int a0, out int b0, out int a1, out int b1) {
    int n = N();
    if (lo >= 0 && hi <= n) { a0 = lo; b0 = hi; return 1; }
    int alo = ((lo % n) + n) % n;          // wrapped start
    if (hi > n) {                          // wraps past the top
        a0 = alo; b0 = n; a1 = 0; b1 = hi - n; return 2;
    }
    // lo < 0, hi <= n : [alo, n) ∪ [0, hi)
    a0 = alo; b0 = n; a1 = 0; b1 = hi; return 2;
}

// SAT corner read; C(-1, *, *) = 0 (inclusive-prefix convention).
float cor(int i, int j, int k) {
    int n = N();
    if (i < 0 || j < 0 || k < 0) return 0.0;
    return sat[i + n * (j + n * k)];
}

// Sum of the SAT over a NON-wrap cuboid [xa,xb)×[ya,yb)×[za,zb) via
// 8-corner inclusion–exclusion (xb,yb,zb are exclusive upper bounds).
float cuboid(int xa, int xb, int ya, int yb, int za, int zb) {
    int xi = xb - 1, yi = yb - 1, zi = zb - 1;
    return cor(xi, yi, zi)
         - cor(xa - 1, yi, zi) - cor(xi, ya - 1, zi) - cor(xi, yi, za - 1)
         + cor(xa - 1, ya - 1, zi) + cor(xa - 1, yi, za - 1) + cor(xi, ya - 1, za - 1)
         - cor(xa - 1, ya - 1, za - 1);
}

// Sum of q over the PERIODIC box [c−b, c+b+1)³ (half-open), i.e. the
// (2b+1)³ cells centered on cell c. Decomposes each wrapped axis.
float boxsum(int cx, int cy, int cz, int b) {
    int xa0, xb0, xa1, xb1; int xn = split(cx - b, cx + b + 1, xa0, xb0, xa1, xb1);
    int ya0, yb0, ya1, yb1; int yn = split(cy - b, cy + b + 1, ya0, yb0, ya1, yb1);
    int za0, zb0, za1, zb1; int zn = split(cz - b, cz + b + 1, za0, zb0, za1, zb1);
    int xa[2] = int[](xa0, xa1), xb[2] = int[](xb0, xb1);
    int ya[2] = int[](ya0, ya1), yb[2] = int[](yb0, yb1);
    int za[2] = int[](za0, za1), zb[2] = int[](zb0, zb1);
    float s = 0.0;
    for (int ix = 0; ix < xn; ix++)
        for (int iy = 0; iy < yn; iy++)
            for (int iz = 0; iz < zn; iz++)
                s += cuboid(xa[ix], xb[ix], ya[iy], yb[iy], za[iz], zb[iz]);
    return s;
}

// ── Pass 0: build x-prefix of q (also computes q = ey² + ei²) ────────
void scan_x() {
    int n = N();
    uint t = gl_GlobalInvocationID.x;
    int total_rows = n * n;
    if (int(t) >= total_rows) return;
    int j = int(t) % n;
    int k = int(t) / n;
    float run = 0.0;
    for (int i = 0; i < n; i++) {
        int gi = idx3(i, j, k);
        float q = ey[gi] * ey[gi] + ei[gi] * ei[gi];
        run += q;
        sat[gi] = run;
    }
}

// ── Pass 1: y-prefix of the (x-scanned) sat ──────────────────────────
void scan_y() {
    int n = N();
    uint t = gl_GlobalInvocationID.x;
    int total_rows = n * n;
    if (int(t) >= total_rows) return;
    int i = int(t) % n;
    int k = int(t) / n;
    float run = 0.0;
    for (int j = 0; j < n; j++) {
        float v = sat[idx3(i, j, k)];
        run += v;
        sat[idx3(i, j, k)] = run;
    }
}

// ── Pass 2: z-prefix of the (y-scanned) sat → full 3D SAT ────────────
void scan_z() {
    int n = N();
    uint t = gl_GlobalInvocationID.x;
    int total_rows = n * n;
    if (int(t) >= total_rows) return;
    int i = int(t) % n;
    int j = int(t) / n;
    float run = 0.0;
    for (int k = 0; k < n; k++) {
        float v = sat[idx3(i, j, k)];
        run += v;
        sat[idx3(i, j, k)] = run;
    }
}

// ── Pass 3: reduce — per-cell rung energies and totals ───────────────
void reduce_pass() {
    int n = N();
    int total = n * n * n;
    int gid = int(gl_GlobalInvocationID.x);
    if (gid >= total) return;
    int cx = gid % n;
    int cy = (gid / n) % n;
    int cz = gid / (n * n);
    float q = ey[gid] * ey[gid] + ei[gid] * ei[gid];

    atomicAdd(out_b[0], q);
    atomicAdd(out_b[1], ey[gid]);
    atomicAdd(out_b[2], ei[gid]);

    for (int r = 0; r < R; r++) {
        int b = BOX[r];
        float sb = boxsum(cx, cy, cz, b);
        float lb = boxsum(cx, cy, cz, 2 * b);
        float ns = float(2 * b + 1) * float(2 * b + 1) * float(2 * b + 1);
        float nl = float(4 * b + 1) * float(4 * b + 1) * float(4 * b + 1);
        float d = sb / ns - lb / nl;
        atomicAdd(out_b[4 + r], d * d);
    }
}

void main() {
    int mode = int(pc.mode_f + 0.5);
    if (mode == 0) scan_x();
    else if (mode == 1) scan_y();
    else if (mode == 2) scan_z();
    else if (mode == 3) reduce_pass();
}
