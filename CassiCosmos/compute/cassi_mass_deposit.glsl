#[compute]
#version 450
// Cassi Mass Deposit — trilinear (CIC) scatter of per-particle masses
// into the field grid. Each particle spreads mass to 8 surrounding
// cells with trilinear weights, producing a smooth density field
// without nearest-neighbor grid aliasing.
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

// ── Main kernel: CIC (Cloud-In-Cell) mass deposit ─────────────────────
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

    // Wrap with periodic boundary
    i0 = ((i0 % N) + N) % N;
    j0 = ((j0 % N) + N) % N;
    k0 = ((k0 % N) + N) % N;
    int i1 = (i0 + 1) % N;
    int j1 = (j0 + 1) % N;
    int k1 = (k0 + 1) % N;

    // Trilinear weights
    float w000 = (1.0 - fx) * (1.0 - fy) * (1.0 - fz);
    float w100 = fx       * (1.0 - fy) * (1.0 - fz);
    float w010 = (1.0 - fx) * fy       * (1.0 - fz);
    float w110 = fx       * fy       * (1.0 - fz);
    float w001 = (1.0 - fx) * (1.0 - fy) * fz;
    float w101 = fx       * (1.0 - fy) * fz;
    float w011 = (1.0 - fx) * fy       * fz;
    float w111 = fx       * fy       * fz;

    int idx000 = i0 + N * (j0 + N * k0);
    int idx100 = i1 + N * (j0 + N * k0);
    int idx010 = i0 + N * (j1 + N * k0);
    int idx110 = i1 + N * (j1 + N * k0);
    int idx001 = i0 + N * (j0 + N * k1);
    int idx101 = i1 + N * (j0 + N * k1);
    int idx011 = i0 + N * (j1 + N * k1);
    int idx111 = i1 + N * (j1 + N * k1);

    atomicAdd(rho[idx000], mass * w000);
    atomicAdd(rho[idx100], mass * w100);
    atomicAdd(rho[idx010], mass * w010);
    atomicAdd(rho[idx110], mass * w110);
    atomicAdd(rho[idx001], mass * w001);
    atomicAdd(rho[idx101], mass * w101);
    atomicAdd(rho[idx011], mass * w011);
    atomicAdd(rho[idx111], mass * w111);
}
