#[compute]
#version 450
// Cassi Mass Deposit — scatters per-particle masses into the field grid.
// Uses nearest-neighbor assignment with float atomic add via CAS.
// Output: mass_density[grid_cell] = uint(float mass + old_value)

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) restrict readonly buffer Positions {
    vec4 pos[];  // x, y, z, mass
};

layout(set = 0, binding = 1, std430) coherent buffer MassDensity {
    uint rho[];  // float masses stored as uint for CAS
};

layout(push_constant, std430) uniform PC {
    float N_f;           // grid resolution per dimension
    float particle_N;    // active particle count
    float extent;        // grid physical half-extent
    float _pad;
} pc;

// ── Index helpers ──────────────────────────────────────────────────────
int cell_idx(vec3 wp) {
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    float scale = (pc.extent > 0.0) ? (hn / pc.extent) : hn;
    vec3 gc = wp * scale + hn;
    ivec3 ci = ivec3(clamp(gc, vec3(0.0), vec3(float(N - 1))));
    return ci.x + N * (ci.y + N * ci.z);
}

// ── Float atomic add via CAS loop ──────────────────────────────────────
// CAS: if rho[idx]==old, set rho[idx]=new, return old. Always returns old value.
// On success: ret==old → return. On failure: ret==current → retry with new old.
void atomic_add_float(int idx, float val) {
    if (val == 0.0) return;
    uint old_bits = atomicOr(rho[idx], 0u);
    int n = 0;
    float old_val;
    do {
        old_val = uintBitsToFloat(old_bits);
        old_bits = atomicCompSwap(rho[idx], old_bits, floatBitsToUint(old_val + val));
        n++;
    } while (floatBitsToUint(old_val) != old_bits && n < 512);
}

// ── Main kernel ────────────────────────────────────────────────────────
void main() {
    uint i = gl_GlobalInvocationID.x;
    int Np = int(pc.particle_N);
    if (int(i) >= Np) return;

    vec4 p = pos[i];
    float mass = p.w;
    if (mass <= 0.0) return;

    int ci = cell_idx(p.xyz);
    atomic_add_float(ci, mass);
}
