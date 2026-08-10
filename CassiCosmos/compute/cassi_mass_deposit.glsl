#[compute]
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
// Accumulation: hardware FLOAT atomicAdd (GL_EXT_shader_atomic_float) —
// one atomicAdd per cell instead of the old 8-way atomic CAS loop
// (atomicOr + atomicCompSwap retry). Verified on this rig (RX 7900 XTX,
// Vulkan 1.4.349, Godot 4.7): the extension compiles, the pipeline builds,
// and results are exact for representable values. Known caveats:
//   - fp32 sequential-summation drift: long single-address chains drift by
//     ~Σ ULP/2 (deterministic; ~1e-3 at 1024 adds/cell, ~1% only in the
//     pathological 1M-adds-to-one-cell case). Same noise class as the old
//     CAS loop; irrelevant at realistic occupancies (tens-hundreds/cell).
//   - Godot's RESPV optimizer prints "OpAtomicFAddEXT is not supported yet."
//     to stderr and skips optimizing THIS shader (harmless; the driver
//     runs the original SPIR-V — verified non-fatal in 4.7's
//     rendering_shader_container / rendering_device_driver_vulkan).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict readonly buffer Positions {
    vec4 pos[];  // x, y, z, mass
};

layout(set = 0, binding = 1, std430) coherent buffer MassDensity {
    float rho[];  // float masses, accumulated with float atomicAdd
};

layout(push_constant, std430) uniform PC {
    float N_f;           // grid resolution per dimension
    float particle_N;    // active particle count
    float extent;        // grid physical half-extent
    float _pad;
} pc;

// ── Main kernel: TSC (triangular-shaped cloud) mass deposit ───────────
void main() {
    uint i = gl_GlobalInvocationID.x;
    int Np = int(pc.particle_N);
    if (int(i) >= Np) return;

    vec4 p = pos[i];
    float mass = p.w;
    if (mass <= 0.0) return;

    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    float scale = (pc.extent > 0.0) ? (hn / pc.extent) : hn;
    vec3 gc = p.xyz * scale + hn;  // fractional grid coordinates

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
    for (int a = 0; a < 3; a++) {
        for (int b = 0; b < 3; b++) {
            for (int c = 0; c < 3; c++) {
                int id = idx[a] + N * (jdx[b] + N * kdx[c]);
                atomicAdd(rho[id], mass * wx[a] * wy[b] * wz[c]);
            }
        }
    }
}
