#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 5 floats (20 B); set 0: bindings 0-3
#version 450
// Cassi BH Accretion — "object -> BH": particles inside a BH's accretion
// radius are swallowed (marked dead, pos.w = 0) and their mass is added to
// the BH's record. The particle-level complement of the merge (dust ->
// object) at the cascade's extreme rung. Field -> dust (condensation) ->
// object (merge) -> BH (THIS pass).
//
// CAPTURE (BH_DYNAMICS_PREREG finding 6/G): the swallow region is no longer
// a fixed sphere. A particle is captured when it is inside
//     r_cap = max(r_acc, k_cap · M)          (heavier holes reach further)
// AND is gravitationally BOUND to the record:
//     |v|² ≤ 2·G_N·M/r                       (G_N = bh[1].w)
// so a fast unbound interloper passes through the horizon shell instead of
// being deleted out of a trajectory the record's own well could not bend.
// r_acc (world units) is a push-constant knob — a fraction of the BH's
// softening σ (the bh_point_gravity eps2 scale in cassi_nbody_gravity.glsl),
// defaulting to the sim/engine config key bh_accretion_radius. k_cap
// (pc.k_cap, world units per unit mass) is the new capture coefficient,
// config key bh_capture_k, defaulting to the conservative 0.001 — at the
// default r_acc = 0.1 an M = 100 hole is the first to reach beyond r_acc.
//
// GPU shape (ONE dispatch, no host readback): one thread per particle; a
// captured particle atomically adds its mass to bh[base].w (base = 4 +
// slot*2, the BH record mass field — the BHData layout shared with
// cassi_bh_integrate.glsl) and is marked dead (pos.w = 0, which the deposit
// skips — `if (mass <= 0.0) return;` — and which the nbody kick preserves).
// A particle inside multiple capture regions counts into the first (mass,
// then index) it hits. The BH mass growth from a swallowed particle is
// exactly conserved (one atomicAdd of the full pos.w) and booked into the
// ABSORBED ledger (bh[34].z), the only other account of where the particle's
// mass went.
//
// Momentum channel (pc.mom_on, the field-channel arm): a swallowed particle
// delivers its momentum pos.w·vel[i] AND its mass to the BH's pending book
// dyn[slot] (xyz = Σm·v, w = Σm since cassi_bh_finalize.glsl last ran; the
// finalize folds the impulse into the record's velocity and zeroes the book,
// so nothing in it is ever stale). The host sets mom_on only when the field
// channel is live, so the legacy path performs no new write and stays
// bit-identical.
// GL_EXT_shader_atomic_float: float atomicAdd on bh[base].w / dyn[slot] /
// the ledger (verified on this RX 7900 XTX / Godot 4.7 by
// cassi_mass_deposit.glsl and cassi_particle_merge.glsl).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer Positions { vec4 pos[]; };  // xyz, w=mass
// bh[0..3] = header (count/G_N/extents/reserved), bh[4..] = BH records
// (base = 4 + slot*2: vec4[base] = pos.xyz + mass.w, vec4[base+1] = vel + age),
// bh[34] = mass ledger (…, z = absorbed), bh[35] = health counters.
layout(set = 0, binding = 1, std430) coherent buffer BHData { vec4 bh[36]; };
layout(set = 0, binding = 2, std430) readonly buffer Velocities { vec4 vel[]; };
layout(set = 0, binding = 3, std430) coherent buffer BHDyn { vec4 dyn[15]; };

layout(push_constant, std430) uniform PC {
    float N_f;          // field grid resolution (unused here; shared layout convention)
    float np;           // particle count
    float r_acc;        // accretion radius floor (world units)
    float mom_on;       // 1.0 = deliver swallowed mass+momentum into dyn[] (field channel)
    float k_cap;        // capture coefficient: r_cap = max(r_acc, k_cap · M)
} pc;

void main() {
    uint i = gl_GlobalInvocationID.x;
    if (int(i) >= int(pc.np)) return;
    vec4 p = pos[i];
    if (p.w <= 0.0) return;                    // already dead (merged/previous swallow)
    for (int b = 0; b < 15; b++) {
        int base = 4 + b * 2;
        float bm = bh[base].w;
        if (bm <= 0.0) continue;               // empty BH slot
        vec3 d = bh[base].xyz - p.xyz;
        float d2 = dot(d, d);
        float r_cap = max(pc.r_acc, max(pc.k_cap, 0.0) * bm);
        if (d2 > r_cap * r_cap) continue;      // outside the capture region
        // Binding test: a particle moving faster than the escape speed of
        // the record's well is not captured (r floored away from 0 so the
        // test is trivially true at the centre).
        float r = max(sqrt(d2), 1.0e-6);
        vec3 pv = vel[i].xyz;
        if (dot(pv, pv) > 2.0 * bh[1].w * bm / r) continue;
        atomicAdd(bh[base].w, p.w);            // mass Δ → BH (exactly conserved)
        atomicAdd(bh[34].z, p.w);              // …and booked as ABSORBED
        if (pc.mom_on > 0.5) {
            vec3 dp = p.w * pv;                // momentum Δ → the pending book
            atomicAdd(dyn[b].x, dp.x);
            atomicAdd(dyn[b].y, dp.y);
            atomicAdd(dyn[b].z, dp.z);
            atomicAdd(dyn[b].w, p.w);          // mass Δ → the book's own Dm
        }
        pos[i].w = 0.0;                        // dead (deposit/nbody/instancer skip)
        break;                                 // counted once even inside multiple horizons
    }
}
