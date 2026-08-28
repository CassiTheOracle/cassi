#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 9 floats (36 B); set 0: bindings 0-2
#version 450
// Cassi Mass Deposit — TSC (triangular-shaped cloud) scatter of
// per-particle masses into the field grid. Each particle spreads mass to
// 27 surrounding cells with the separable quadratic-spline (B-spline)
// weights — the "bubble-shaped" deposit: CIC's 8-cell tent convolved
// with itself, support 1.5h per axis, second-order accurate,
// symmetric, and an exact partition of unity (Σ w = 1 at any fractional
// position — no per-particle normalization needed).
//   1D weights (f = fractional offset within the base cell):
//     w(i0−1) = ½·(½ − f)²            (u = f + 1 ∈ (1, 1.5])
//     w(i0)   = ¾ − f²        for f ≤ ½,  else ½·(1.5 − f)²
//     w(i0+1) = ½·(½ + f)²    for f <  ½,  else ¾ − (1−f)²
//   This replaces the old trilinear CIC 8-cell tent (support 1h,
//   first-order); the wider isotropic-ish footprint removes the cubic
//   deposit anisotropy near masses and smooths the density field the
//   spectral Poisson solve sees.
//
// Accumulation: EXACT integer fixed-point via FOUR 32-bit digit-sum
// accumulators (the old fp32 atomicAdd made each cell sum depend on the
// TSC atomic execution order — a ~3.8e-6-relative run-to-run floor in
// every parity probe, the only remaining nondeterminism source).
// INTEGER addition commutes EXACTLY: any atomic ordering yields the same
// cell sum, so the deposit is bit-deterministic with NO per-step
// particle sort.
//
// Why four uint32 digit sums instead of one uint64
// (GL_EXT_shader_atomic_int64)? Godot 4.7's RDShaderFile SPIR-V loader
// REJECTS 64-bit integer types ("Failed parse" — verified on this rig
// with a minimal shader: even a type-only uint64_t buffer fails to load,
// while plain uint atomics work). So the fixed-point value is accumulated
// as four SEPARATE base-2^8 digit sums, all in uint32:
//   v = uint(round(m·w·SCALE)),  SCALE = 2^24   (v < 2^32 ⟺ m < 256)
//   d0 = v & 0xFF;  d1 = (v>>8) & 0xFF;  d2 = (v>>16) & 0xFF;  d3 = v>>24
//   fix[cell] = (Σd0, Σd1, Σd2, Σd3)  — four atomicAdd(uint32) per cell
// EXACTNESS INVARIANT: each digit sum stays < 2^32 as long as the cell
// receives ≤ 1.68e7 deposits (each digit ≤ 255): Σd_k ≤ N·255 < 2^32 ⟺
// N < 2^32/255 = 1.68e7. The ENTIRE 2.5e6-particle population in ONE
// cell is only 2.5e6 deposits — 6.7× margin (4.2× even at N = 4e6), so
// no carry can ever cross digits and every accumulator is exact.
// Particle masses span [0.3, 30] (Salpeter); merges can grow survivors,
// so v is clamped at 2^32−256 (m ≥ 256 — a pathological ≥8×-merge blob —
// under-deposits by a documented, deterministic amount; m < 256 exact).
//
// Convert pass (pc.mode = 1): the Poisson/PDE/tree chain reads rho as
// FLOAT — after the deposit the exact digit sums are reconstructed:
//   rho = s0·2^−24 + s1·2^−16 + s2·2^−8 + s3   (smallest first)
// Each term is an exact power-of-two scaling of an exact integer; the
// additions round once at the end — rho is the correctly-rounded fp32
// of the exact integer sum (deterministic, same precision class as the
// old float path, and actually one rounding instead of N).
// The per-step GPU clear (cassi_poisson.glsl mode 3) zeroes BOTH grids
// (float rho + all four digit sums) every step, and the dual-lattice
// chain clears and re-deposits the SAME single accumulator buffer
// (mirrors the float semantics exactly — see _step_dispatches).
//
// Compile fallback: if a driver lacks atomic ops, gate the int path
// behind a #define and keep the float atomicAdd — but NEVER ship the
// float path as the silent default (the determinism contract breaks).
// uint32 atomicAdd is core GLSL 4.50 — no extension required here.

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Positions {
    vec4 pos[];  // x, y, z, mass — the deposit only READS positions; the
                 // qualifier is `readonly` (not `restrict readonly`):
                 // Godot's uniform validation rejects `restrict readonly`
                 // when the sim binds its writable _pos_buf here
                 // (uniform-format mismatch — the restrict is only an
                 // aliasing hint, dropped 2026-08-14).
};

layout(set = 0, binding = 1, std430) coherent buffer MassDensity {
    float rho[];  // float masses — written ONLY by the convert pass (mode 1)
};

layout(set = 0, binding = 2, std430) coherent buffer MassDensityFix {
    // Per-cell EXACT fixed-point accumulator: 4×uint8-digit sums of the
    // SCALE = 2^24 fixed-point deposits, packed one uvec4 per cell
    // (x = Σd0, y = Σd1, z = Σd2, w = Σd3). Godot 4.7 rejects uint64
    // buffers ("Failed parse"), so exactness comes from four carry-free
    // uint32 sums (see the header comment — every sum stays < 2^32).
    // uint atomicAdd is core GLSL 4.50 — no extension needed.
    uvec4 fix[];
};

layout(push_constant, std430) uniform PC {
    float N_f;           // grid resolution per dimension
    float particle_N;    // active particle count
    float extent_x;      // per-axis grid physical half-extents (GRID_LAYOUT.md)
    float extent_y;
    float extent_z;
    float off_x;         // dual-grid offset (CASCADE_GRID.md): the deposit
    float off_y;         // runs once per lattice — 0 for the base chain,
    float off_z;         // h_i/2 = extent_i/N for the shifted (BCC) chain
    float mode;          // 0 = deposit (scatter), 1 = convert (fix → rho)
} pc;

// ── Mode 0: TSC (triangular-shaped cloud) mass deposit ───────────────
void deposit_main() {
    uint i = gl_GlobalInvocationID.x;
    int Np = int(pc.particle_N);
    if (int(i) >= Np) return;

    vec4 p = pos[i];
    float mass = p.w;
    if (mass <= 0.0) return;

    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    // Per-axis world→grid map. The TSC kernel itself stays CELL-BASED (its
    // weights are functions of the fractional-cell offsets only, an exact
    // partition of unity); the per-axis physical support (1.5h_i) falls out
    // of this map — the φ-aspect deposit needs no kernel change. The dual
    // lattice (CASCADE_GRID.md) shifts the SAME map by the PC offset.
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 scale = (ext.x > 0.0) ? (hn / ext) : vec3(hn);
    vec3 gc = (p.xyz + vec3(pc.off_x, pc.off_y, pc.off_z)) * scale + hn;

    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));

    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);

    // Wrap with periodic boundary — REQUIRED for the base cells too: the
    // nbody integrator never wraps positions, so halo particles cross
    // ±extent and gc can leave [0, N) (gc == N exactly at the wrap);
    // an unwrapped i0 would atomicAdd out of bounds.
    i0 = ((i0 % N) + N) % N;
    j0 = ((j0 % N) + N) % N;
    k0 = ((k0 % N) + N) % N;

    // TSC 1D weights (partition of unity at any f — see header)
    float wxm = 0.5 * (0.5 - fx) * (0.5 - fx);
    float wxp = (fx < 0.5) ? 0.5 * (0.5 + fx) * (0.5 + fx) : 0.75 - (1.0 - fx) * (1.0 - fx);
    float wx0 = (fx < 0.5) ? 0.75 - fx * fx : 0.5 * (1.5 - fx) * (1.5 - fx);
    float wym = 0.5 * (0.5 - fy) * (0.5 - fy);
    float wyp = (fy < 0.5) ? 0.5 * (0.5 + fy) * (0.5 + fy) : 0.75 - (1.0 - fy) * (1.0 - fy);
    float wy0 = (fy < 0.5) ? 0.75 - fy * fy : 0.5 * (1.5 - fy) * (1.5 - fy);
    float wzm = 0.5 * (0.5 - fz) * (0.5 - fz);
    float wzp = (fz < 0.5) ? 0.5 * (0.5 + fz) * (0.5 + fz) : 0.75 - (1.0 - fz) * (1.0 - fz);
    float wz0 = (fz < 0.5) ? 0.75 - fz * fz : 0.5 * (1.5 - fz) * (1.5 - fz);

    // Periodic wrap of the three-cell neighborhood
    int im = ((i0 - 1 + N) % N), jm = ((j0 - 1 + N) % N), km = ((k0 - 1 + N) % N);
    int i1 = (i0 + 1) % N,    j1 = (j0 + 1) % N,    k1 = (k0 + 1) % N;

    // 27-cell separable deposit: w_x(i)·w_y(j)·w_z(k)
    int idx[3] = int[](im, i0, i1);
    int jdx[3] = int[](jm, j0, j1);
    int kdx[3] = int[](km, k0, k1);
    float wx[3] = float[](wxm, wx0, wxp);
    float wy[3] = float[](wym, wy0, wyp);
    float wz[3] = float[](wzm, wz0, wzp);
    // Exact integer fixed-point accumulation (SCALE = 2^24, digit base
    // 2^8 — see header): four carry-free uint32 digit sums, each exact
    // under ANY atomic ordering (integer addition commutes; no digit sum
    // can reach 2^32 while the cell holds ≤ 1.68e7 deposits). The float
    // product (mass · w) is the same expression the old float path
    // accumulated; × SCALE is an exact power-of-2 multiply, and the
    // round-to-nearest is a pure function of the float value.
    for (int a = 0; a < 3; a++) {
        for (int b = 0; b < 3; b++) {
            for (int c = 0; c < 3; c++) {
                int id = idx[a] + N * (jdx[b] + N * kdx[c]);
                // Clamp at 2^32−256: masses ≥ 256 (pathological merge
                // giants, ≥8× the Salpeter cap) would overflow uint — the
                // clamp keeps the deposit exact for m < 256 and makes the
                // ≥256 case a deterministic, documented under-deposit.
                float vf = min(round(mass * wx[a] * wy[b] * wz[c] * 16777216.0), 4294967040.0);
                uint v = uint(vf);
                // P1 (perf-decomp 2026-08-15): issue atomics ONLY for the
                // non-zero base-2^8 digits — d_k = (v >> 8k) & 255, top
                // digit index = findMSB(v)>>3 (0..3; v == 0 → no atomics).
                // Omitting guaranteed-zero addends leaves every exact digit
                // sum identical (integer addition), so rho — one rounding
                // of the exact sums in convert — is BIT-IDENTICAL. The
                // digit-use distribution: d3 ≠ 0 ⟺ v ≥ 2^24 ⟺ m·w ≥ 1.0;
                // the max TSC cell weight is 0.4219 (center, f=0), so d3 is
                // written only for m ≥ ~2.4 (center) / ~7 (side) / ~21
                // (corner) — ~6% of Salpeter particles touch it in the
                // center cell alone → ~23% fewer atomics at 2M particles.
                // (P0 measurement, perf_findings §15: the deposit is
                // ~≤2 ms/step of the ~50 — the win is small but exact.)
                if (v != 0u) {
                    uint nd = (uint(findMSB(v)) >> 3) + 1u;   // 1..4 digits
                    for (uint k = 0u; k < nd; k++) {
                        atomicAdd(fix[id][k], (v >> (8u * k)) & 255u);
                    }
                }
            }
        }
    }
}

// ── Mode 1: convert — exact digit sums → float rho ───────────────────
// One thread per cell, the poisson (N, N, 1) 2D dispatch convention
// (gid = x + y·(N·256), guard gid < N³ — the N=256 landmine-safe form).
// rho = s0·2^−24 + s1·2^−16 + s2·2^−8 + s3, smallest term first: every
// term is an exact power-of-two scaling of an exact integer sum, so the
// four-term sum rounds ONCE — rho is the correctly-rounded fp32 of the
// exact cell mass. Runs between the deposit and the Poisson solve (and
// in the dual-lattice chain), with barriers both sides (_step_dispatches).
void convert_main() {
    int N = int(pc.N_f);
    int nc = N * N * N;
    uint gid = gl_GlobalInvocationID.x
             + gl_GlobalInvocationID.y * uint(N * 256);
    if (int(gid) >= nc) return;
    uvec4 s = fix[gid];
    rho[gid] = float(s.x) * 5.9604644775390625e-08
             + float(s.y) * 0.0000152587890625
             + float(s.z) * 0.00390625
             + float(s.w);
}

void main() {
    if (pc.mode > 0.5) {
        convert_main();
    } else {
        deposit_main();
    }
}
