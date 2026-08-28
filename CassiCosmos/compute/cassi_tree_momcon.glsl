#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 3 floats (12 B); set 0: bindings 0-2
#version 450
// Cassi Tree momentum-conservation pass (2026-08-15).
//
// The tree gravity arm multiplies each particle's tree force by its OWN
// local field prefactor G_N·(π/ρ)_target (cassi_nbody_gravity.glsl mode-5
// seam): the force a particle A feels from the cloud is ∝ (π/ρ)_A, which
// need not equal the force it exerts on B (∝ (π/ρ)_B). Action–reaction is
// therefore BROKEN, Σ m·a ≠ 0, and the self-gravitating cloud acquires a
// net self-impulse that ballistically drifts it off the fixed render window
// ("all particles vanish" measured at the owner's scale: COM (60,0,1) →
// (105,40,69) over 1400 frames while the force stays inward).
//
// This pass restores translational symmetry: after the nbody gravity step
// (tree mode), it subtracts the MASS-WEIGHTED MEAN acceleration so Σm·a = 0
// exactly. A self-gravitating body's internal forces must sum to zero
// (Newton's 3rd law) — a DERIVED conservation correction, not a fitted
// constant. Applied to the final _acc_buf (where the full (π/ρ)-weighted
// force is known), it zeroes the net force from the tree, the BH sector and
// any field coupling together.
//
// Buffers (set 0): 0 = Accel (vec4/particle, read+wrote), 1 = Positions
// (vec4/particle, w = mass — the weights), 2 = Reduce (vec4 — atomic
// Σ(m·ax),Σ(m·ay),Σ(m·az),Σ(m)). CLEAR (op=2) → REDUCE (op=0) → SUBTRACT
// (op=1) run as three in-list dispatches with barriers between them (the
// global RD cannot host-submit mid-list; op=2, fired by 1 workgroup, zeroes
// the 16-B accumulator first). PC: N_f (particles), op.
// GL_EXT_shader_atomic_float — verified on this rig (cassi_mass_deposit.glsl).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) coherent buffer Accel { vec4 acc[]; };
layout(set = 0, binding = 1, std430) readonly buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 2, std430) coherent buffer Reduce { vec4 sum[]; };  // [0]=Σm·a.xyz, Σm in .w; [1]=Σm·v.xyz
layout(set = 0, binding = 3, std430) coherent buffer Velocities { vec4 vel[]; };

layout(push_constant, std430) uniform PC {
    float N_f;      // particle count
    float op;       // 0 = reduce, 1 = subtract, 2 = clear Reduce
    float _pad;     // host allocates 3 floats (12 B) — std430 pad to match
} pc;

void main() {
    if (pc.op > 1.5) {
        // clear: zero the Reduce accumulators (1 workgroup)
        if (gl_GlobalInvocationID.x == 0u) {
            sum[0] = vec4(0.0);
            sum[1] = vec4(0.0);
        }
        return;
    }
    uint i = gl_GlobalInvocationID.x;
    int N = int(pc.N_f);
    if (int(i) >= N) return;
    if (pc.op < 0.5) {
        // reduce: accumulate the mass-weighted net force AND net momentum
        float m = max(pos[i].w, 0.0);
        vec3 a = acc[i].xyz;
        vec3 v = vel[i].xyz;
        atomicAdd(sum[0].x, m * a.x);
        atomicAdd(sum[0].y, m * a.y);
        atomicAdd(sum[0].z, m * a.z);
        atomicAdd(sum[0].w, m);
        atomicAdd(sum[1].x, m * v.x);
        atomicAdd(sum[1].y, m * v.y);
        atomicAdd(sum[1].z, m * v.z);
    } else {
        // subtract: remove the mass-weighted mean acceleration AND the mean
        // velocity — Σ m·a = 0 (the spurious self-impulse) and Σ m·v = 0
        // (the rest frame), both restored by Newton's 3rd law.
        float m = max(sum[0].w, 1e-30);
        vec3 amean = vec3(sum[0].x, sum[0].y, sum[0].z) / m;
        vec3 vmean = vec3(sum[1].x, sum[1].y, sum[1].z) / m;
        acc[i].xyz -= amean;
        vel[i].xyz -= vmean;
    }
}
