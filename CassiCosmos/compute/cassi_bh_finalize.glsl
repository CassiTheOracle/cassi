#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 15 floats (60 B); set 0: bindings 0-5; set 1: bindings 0-2
#version 450
// Cassi BH Finalize — the BH sector's motion pass. One thread per BH
// record slot (15). Replaces cassi_bh_integrate.glsl when the field
// channel is live: the BH is a TEST BODY OF THE SAME RIVER LAW the
// particles obey, sampled from the same ∇(g·Φ) field, with the same
// G_N and the same π/ρ clamp, through the shared include
// (compute/cassi_river_force_common.glslinc).
//
// INTEGRATOR: the particle arm's cached-acc KDK leapfrog, mirrored
// expression for expression (cassi_nbody_gravity.glsl §Cached-acc KDK):
//   v½ = v + a_prev·dt/2;  p' = p + v½·dt;  a' = F(p');  v' = v½ + a'·dt/2
// with a' cached in bacc[slot] for the next step's first half-kick. This
// is what makes the BH a TEST BODY rather than an approximation of one:
// planted on a massless particle's (p, v), the two trajectories agree to
// the last bit (BH3). pc.pass_mode > 0.5 is the SEED step (the predicate's
// rising edge, or a fresh plant): a_prev does not exist yet, so the pass
// evaluates the warm-up term F(p) itself, first, in the same dispatch —
// the exact mirror of the particle arm's one-time pass_mode == 2 warm-up,
// which runs against the same unmodified gradients, so a seed step is a
// complete KDK step (never a half step).
//
// MOMENTUM: dyn[slot] is a PENDING accumulator, not a state: xyz = Σ m·v
// and w = Σ m swallowed by cassi_bh_accretion.glsl SINCE THIS PASS LAST
// RAN, and this pass zeroes it. The record's vel is the live velocity, so
// a step with no swallow takes v from the record and does no arithmetic on
// it at all (the parity claim above is exact, not approximate); a step WITH
// a swallow folds the pending impulse in the momentum-conserving form
// v ← (v·(M − ΔM) + Σm·v)/M before the half-kick, where M is the record's
// post-swallow mass. The transfer is accounted to fp32 rounding, with the
// atomic accumulation order (and hence the last ulp of Σm·v) free.
//
// Ordering (host): the pass runs AFTER the gradient pass(es) of the same
// step — it samples THIS step's ∇(g·Φ) — and after accretion, so a
// swallow is folded into the same step's velocity. No pass between this
// one and the particle KDK writes the field, so both consumers evaluate
// the same gradients. It runs INSTEAD of the legacy integrate pass, which
// is what retires the q-driven mass growth (`acc_rate·q·cell_vol`) and age
// expiry while the channel is live: BH mass changes by accretion only.
//
// RealSim (gravity_mode == 4): the BH takes the river force only. The
// medium drag/viscosity/friction terms are a particle-medium coupling
// and are deliberately not applied to a point mass.
//
// A BH samples its own well (its mass is in rho). The self-force at a
// grid-symmetric point cancels by symmetry; the residual off-center is a
// discretization artifact, bounded — not hidden — by BH4. With the dual
// lattice live that symmetry is broken by the shifted chain's own half-cell
// offset, which is what bh_river_acc_mirrored (below) restores.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

// Field buffers (set 0, contiguous): the names the shared include reads.
layout(set = 0, binding = 0, std430) readonly buffer FieldEY { float ey[]; };
layout(set = 0, binding = 1, std430) readonly buffer FieldEI { float ei[]; };
layout(set = 0, binding = 2, std430) readonly buffer FieldVel { vec4 fvel[]; };
layout(set = 0, binding = 3, std430) buffer GradBuf { vec4 grad[]; };
layout(set = 0, binding = 4, std430) buffer GradBuf2 { vec4 g2[]; };
layout(set = 0, binding = 5, std430) readonly buffer CoarseGradBuf { vec4 cgrad[]; };
// bh[0..3] = header, bh[4..] = records (base = 4 + slot*2:
// vec4[base] = pos.xyz + mass.w, vec4[base+1] = vel + age). coherent:
// mass is atomicAdd'ed by the accretion pass.
layout(set = 1, binding = 0, std430) coherent buffer BHData { vec4 bh[36]; };
// Momentum book, one vec4 per slot: xyz = Σm·v pending, w = Σm pending.
// Written by the accretion pass (atomicAdd), consumed and zeroed here.
layout(set = 1, binding = 1, std430) coherent buffer BHDyn { vec4 dyn[15]; };
// The BH's cached-acc KDK state, mirroring the particle arm's acc[] buffer:
// xyz = the full-kick acceleration F(p) at the position the BH occupies at
// the START of the step (written here at the end of the previous step, or
// seeded by the warm-up term of a seed step).
layout(set = 1, binding = 2, std430) buffer BHAcc { vec4 bacc[15]; };

// Same 15-float layout as cassi_nbody_gravity.glsl, so the host pushes
// the step's nbody push-constant bytes verbatim. Read here: N_f, dt, phi,
// xi, gravity_mode.
layout(push_constant, std430) uniform PC {
    float N_f;
    float dt;
    float t;
    float phi;
    float xi;
    float eps2;
    float particle_N;
    float mode;
    float source_strength;
    float num_clusters;
    float gravity_mode;
    float pass_mode;
    float realsim_drag;
    float realsim_viscosity;
    float realsim_friction;
    float self_mirror;   // BH self-force mirror-average toggle (byte 60, default 0 = OFF)
} pc;

#include "res://compute/cassi_river_force_common.glslinc"

// ── Mirror-symmetric force sample about the record (BH4) — KNOB, OFF ───
// `pc.self_mirror` (byte 60, default 0.0 = OFF): the OFF path below is the
// pre-change estimator, bit-identical to it — the DEFAULT configuration is
// unchanged (repo rule: new engine behaviour must leave the default
// bit-identical).
//
// WHY THE KNOB EXISTS. An isolated body must not accelerate itself: the
// record's own mass is in rho, so the field it samples contains its own
// deposited well. That self-term cancels by symmetry ONLY while the sample
// is mirror-symmetric about the record. The dual (Yin/Yang) lattice breaks
// that: its chain samples the same well half a cell off the record's
// centre, so the odd (asymmetric) part of the record's own well stops
// cancelling — BH4 measured |dv| = 0.0599/step with the dual chain live
// against 2.37e-8 base-only (research/bh_dynamics/BH_DYNAMICS_PREREG.md).
// With the knob ON the sample is taken at pos + delta AND pos − delta and
// averaged, where delta is the dual-lattice offset actually in use
// (bh[1].xyz = extent_i/N, the shifted chain's half-cell shift), so the odd
// part of the record's own well cancels in the average.
//
// WHAT IT BUYS AND WHAT IT COSTS (measured, verify_bh_dynamics.tscn, same
// binary, dual chain live, everything else identical): with the knob on,
// the dual-chain self-force falls 5.759 → 2.807 and BH2b/BH3f/BH5b improve
// (0.0167→0.0087, 1.282→1.045, 0.644→0.508), while BH3a/b/c lose exact
// massless-particle parity because a source cannot both cancel its own well
// and match a non-source's estimator; the 1e-3 BH4 bound is not reached
// either way. The parity gates encode "BH behaves like a mass-0 particle",
// which is what the review flagged as the defect — so this knob is the
// honest way to expose the tradeoff rather than redefine a gate.
//
// BH-ONLY: the particle arm keeps its single sample (cassi_nbody_gravity's
// chord_g_from). A particle is a massless test body — its own well is not in
// rho, so it has no self-term to cancel, and its trajectory is the parity
// reference BH3 pins.
vec3 bh_river_acc_mirrored(vec3 wp) {
    vec3 delta = ((bh[3].y > 0.5) && (pc.self_mirror > 0.5)) ? bh[1].xyz : vec3(0.0);
    if (dot(delta, delta) == 0.0) return river_acc_at(wp);
    return 0.5 * (river_acc_at(wp + delta) + river_acc_at(wp - delta));
}

void main() {
    uint slot = gl_GlobalInvocationID.x;
    if (slot >= 15u) return;
    int base = 4 + int(slot) * 2;
    float M = bh[base].w;
    if (M <= 0.0) return;                  // empty record slot

    vec3 wp = bh[base].xyz;
    vec3 v = bh[base + 1].xyz;             // the record IS the live velocity
    float hdt = pc.dt * 0.5;

    // Fold this step's swallows in, momentum-conserving, before the kick. A
    // step with no swallow takes the branch never: v is left UNTOUCHED, which
    // is what keeps the test-body parity exact. dM > 0 implies the accretion
    // pass ran this step and M already includes it.
    vec4 pend = dyn[slot];
    float dM = pend.w;
    if (dM > 0.0) v = (v * (M - dM) + pend.xyz) / M;
    dyn[slot] = vec4(0.0);                 // the book is pending-only

    // Warm-up term on a seed step (the gradient the particle arm's pass_mode
    // == 2 warm-up reads this same step), the cache otherwise. Both
    // evaluations go through the mirror-symmetric sample above.
    vec3 a_prev = (pc.pass_mode > 0.5) ? bh_river_acc_mirrored(wp) : bacc[slot].xyz;

    vec3 v_half = v + a_prev * hdt;
    vec3 wp_new = wp + v_half * pc.dt;
    vec3 grav_acc = bh_river_acc_mirrored(wp_new);
    vec3 v_new = v_half + grav_acc * hdt;

    if (any(isnan(wp_new)) || any(isinf(wp_new))) wp_new = wp;
    if (any(isnan(v_new)) || any(isinf(v_new))) v_new = vec3(0.0);

    bh[base].xyz = wp_new;
    bh[base + 1].xyz = v_new;              // age (w) untouched
    bacc[slot] = vec4(grav_acc, 0.0);      // next step's first half-kick
}
