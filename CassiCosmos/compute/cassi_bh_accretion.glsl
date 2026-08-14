#[compute]
#version 450
// Cassi BH Accretion — "object -> BH": particles inside a BH's accretion
// radius are swallowed (marked dead, pos.w = 0) and their mass is added to
// the BH's record. The particle-level complement of the merge (dust ->
// object) at the cascade's extreme rung. Field -> dust (condensation) ->
// object (merge) -> BH (THIS pass).
//
// R_acc (world units) is a push-constant knob — a fraction of the BH's
// softening σ (the bh_point_gravity eps2 scale in cassi_nbody_gravity.glsl),
// defaulting to the sim/engine config key bh_accretion_radius. Kept small so
// the σ-regularized BH well's accreted mass is a genuine near-field swallow,
// not a global capture.
//
// GPU shape (ONE dispatch, no host readback): one thread per particle; a
// particle within R_acc of an active BH (mass > 0) atomically adds its mass
// to bh[base].w (base = 4 + slot*2, the BH record mass field — the BHData
// layout shared with cassi_bh_integrate.glsl) and is marked dead (pos.w = 0,
// which the deposit skips — `if (mass <= 0.0) return;` — and which the nbody
// kick preserves). A particle inside multiple horizons counts into the first
// (mass, then index) it hits. The BH mass growth from a swallowed particle is
// exactly conserved (one atomicAdd of the full pos.w).
// GL_EXT_shader_atomic_float: float atomicAdd on bh[base].w (verified on this
// RX 7900 XTX / Godot 4.7 by cassi_mass_deposit.glsl and cassi_particle_merge.glsl).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer Positions { vec4 pos[]; };  // xyz, w=mass
// bh[0..3] = header (count/G_N/extents/reserved), bh[4..] = BH records
// (base = 4 + slot*2: vec4[base] = pos.xyz + mass.w, vec4[base+1] = vel + age).
layout(set = 0, binding = 1, std430) coherent buffer BHData { vec4 bh[36]; };

layout(push_constant, std430) uniform PC {
    float N_f;          // field grid resolution (unused here; shared layout convention)
    float np;           // particle count
    float r_acc;        // accretion radius (world units)
    float _pad0;
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
        if (dot(d, d) <= pc.r_acc * pc.r_acc) {
            atomicAdd(bh[base].w, p.w);        // mass Δ → BH (exactly conserved)
            pos[i].w = 0.0;                    // dead (deposit/nbody/instancer skip)
            break;                             // counted once even inside multiple horizons
        }
    }
}
