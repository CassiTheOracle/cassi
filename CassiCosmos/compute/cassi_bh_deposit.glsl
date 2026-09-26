#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 9 floats (36 B); set 0: bindings 0-1
#version 450
// Cassi BH Deposit — the BH sector's mass source into the SAME
// deterministic accumulator the particles write (cassi_mass_deposit_common.glslinc),
// run in the SAME step before the SAME convert → Poisson → gradient chain.
// This is what makes a BH a source of the field rather than a bolt-on to
// the particle force sum: after this pass its mass is inside rho, so it
// reaches Phi, ∇(g·Φ), the PDE source and every field consumer.
//
// Kernel: the TSC 27-cell weights and the base-2^8 fixed-point digit-sum
// atomicAdd below are a textual copy of deposit_main — the deposit kernel
// is deliberately ONE kernel, and this pass exists separately only so a
// BH-only configuration (N_particles == 0, no particle buffers) can
// deposit without the particle uniform set. BH1 (scenes/verify_bh_dynamics.tscn)
// pins Σrho to the planted mass with the particle arm silent, which is
// exactly the check that the two copies agree.
//
// Mass units: bh[base].w is in particle-mass units (pos.w), the same unit
// the fixed-point accumulator carries. m >= 256 clamps to 2^32−256 for a
// deterministic, documented under-deposit (identical to the particle arm).
// That clamp is SILENT saturation (BH_DYNAMICS_PREREG finding 3: a planted
// M = 700 deposited as Σrho = 660.7 once the per-cell contribution pinned),
// so every clamped contribution and every non-finite record is counted into
// the bh[35] health slots instead of passing unnoticed. The counters are
// cumulative and read back by the host (never logged per frame).
//
// Dispatch: ceil(15/64) = 1 workgroup of 64, guarded to the 15 record
// slots. Runs once per lattice: the base chain, and (dual_grid) the
// shifted chain with the dual offset, mirroring the particle deposit.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// GL_EXT_shader_atomic_float: the health counters are atomicAdd'ed (same
// extension/GPU as cassi_bh_accretion.glsl).
#extension GL_EXT_shader_atomic_float : require

// bh[0..3] = header, bh[4..] = BH records (base = 4 + slot*2:
// vec4[base] = pos.xyz + mass.w, vec4[base+1] = vel + age) — the BHData
// layout shared with cassi_nbody_gravity.glsl / cassi_bh_finalize.glsl.
// bh[35] = health: (deposit-clamped contributions, deposit non-finite
// records, integrate non-finite retirements, reserved). coherent: this
// pass atomicAdd's the counters.
layout(set = 0, binding = 0, std430) coherent buffer BHData { vec4 bh[36]; };
layout(set = 0, binding = 1, std430) coherent buffer MassDensityFix {
    // Per-cell fixed-point accumulator: (Σd0, Σd1, Σd2, Σd3), one uvec4.
    uvec4 fix[];
};

// SAME 9-float layout as cassi_mass_deposit.glsl (the host pushes its
// deposit push constant verbatim; particle_N is unused here).
layout(push_constant, std430) uniform PC {
    float N_f;           // grid resolution per dimension
    float particle_N;    // unused (particle deposit's count)
    float extent_x;      // per-axis grid physical half-extents (GRID_LAYOUT.md)
    float extent_y;
    float extent_z;
    float off_x;         // dual-grid offset (CASCADE_GRID.md): 0 for the base
    float off_y;         // chain, h_i/2 for the shifted (BCC) chain
    float off_z;
    float mode;          // unused
} pc;

void main() {
    uint slot = gl_GlobalInvocationID.x;
    if (slot >= 15u) return;
    int base = 4 + int(slot) * 2;
    float mass = bh[base].w;
    if (mass <= 0.0) return;               // empty (or expired) record slot

    vec3 p = bh[base].xyz;
    // `mass <= 0.0` is FALSE for NaN, so a poisoned record would otherwise
    // reach round()/uint() — undefined in GLSL. Count it and skip: the
    // integrator retires the record itself.
    if (isnan(mass) || isinf(mass) || any(isnan(p)) || any(isinf(p))) {
        atomicAdd(bh[35].y, 1.0);
        return;
    }
    int N = int(pc.N_f);
    float hn = float(N) * 0.5;
    // Per-axis world→grid map, identical to the particle deposit: the TSC
    // kernel is CELL-BASED (partition of unity at any fractional offset);
    // the per-axis physical support falls out of this map, and the dual
    // lattice shifts the SAME map by the push-constant offset.
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 scale = (ext.x > 0.0) ? (hn / ext) : vec3(hn);
    vec3 gc = (p + vec3(pc.off_x, pc.off_y, pc.off_z)) * scale + hn;

    int i0 = int(floor(gc.x));
    int j0 = int(floor(gc.y));
    int k0 = int(floor(gc.z));

    float fx = gc.x - float(i0);
    float fy = gc.y - float(j0);
    float fz = gc.z - float(k0);

    // Periodic wrap — required for the base cells too: BHs are not wrapped
    // by the integrator, so gc can leave [0, N) and an unwrapped i0 would
    // atomicAdd out of bounds.
    i0 = ((i0 % N) + N) % N;
    j0 = ((j0 % N) + N) % N;
    k0 = ((k0 % N) + N) % N;

    // TSC 1D weights (partition of unity at any f)
    float wxm = 0.5 * (0.5 - fx) * (0.5 - fx);
    float wxp = (fx < 0.5) ? 0.5 * (0.5 + fx) * (0.5 + fx) : 0.75 - (1.0 - fx) * (1.0 - fx);
    float wx0 = (fx < 0.5) ? 0.75 - fx * fx : 0.5 * (1.5 - fx) * (1.5 - fx);
    float wym = 0.5 * (0.5 - fy) * (0.5 - fy);
    float wyp = (fy < 0.5) ? 0.5 * (0.5 + fy) * (0.5 + fy) : 0.75 - (1.0 - fy) * (1.0 - fy);
    float wy0 = (fy < 0.5) ? 0.75 - fy * fy : 0.5 * (1.5 - fy) * (1.5 - fy);
    float wzm = 0.5 * (0.5 - fz) * (0.5 - fz);
    float wzp = (fz < 0.5) ? 0.5 * (0.5 + fz) * (0.5 + fz) : 0.75 - (1.0 - fz) * (1.0 - fz);
    float wz0 = (fz < 0.5) ? 0.75 - fz * fz : 0.5 * (1.5 - fz) * (1.5 - fz);

    int im = ((i0 - 1 + N) % N), jm = ((j0 - 1 + N) % N), km = ((k0 - 1 + N) % N);
    int i1 = (i0 + 1) % N,    j1 = (j0 + 1) % N,    k1 = (k0 + 1) % N;

    int idx[3] = int[](im, i0, i1);
    int jdx[3] = int[](jm, j0, j1);
    int kdx[3] = int[](km, k0, k1);
    float wx[3] = float[](wxm, wx0, wxp);
    float wy[3] = float[](wym, wy0, wyp);
    float wz[3] = float[](wzm, wz0, wzp);
    // Exact fixed-point accumulation (SCALE = 2^24, digit base 2^8): four
    // carry-free uint32 digit sums; integer addition commutes, so the BH
    // contribution can land in any order relative to the particle deposits
    // without changing a cell's sum.
    uint clamped = 0u;
    for (int a = 0; a < 3; a++) {
        for (int b = 0; b < 3; b++) {
            for (int c = 0; c < 3; c++) {
                int id = idx[a] + N * (jdx[b] + N * kdx[c]);
                float raw = round(mass * wx[a] * wy[b] * wz[c] * 16777216.0);
                // 2^32−256: the largest contribution the four 8-bit digit
                // sums can carry. Reaching it means the deposit saturated —
                // count it (the mass silently does NOT arrive).
                if (raw > 4294967040.0) clamped++;
                float vf = min(raw, 4294967040.0);
                uint v = uint(vf);
                if (v != 0u) {
                    uint nd = (uint(findMSB(v)) >> 3) + 1u;   // 1..4 digits
                    for (uint k = 0u; k < nd; k++) {
                        atomicAdd(fix[id][k], (v >> (8u * k)) & 255u);
                    }
                }
            }
        }
    }
    if (clamped > 0u) atomicAdd(bh[35].x, float(clamped));
}
