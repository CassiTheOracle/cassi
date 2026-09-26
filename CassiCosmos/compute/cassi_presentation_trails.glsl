#[compute]
// canonical layout: scripts/contracts/layout.gd
// ═══════════════════════════════════════════════════════════════════════
// CASSI PRESENTATION VELOCITY TRAILS — bounded instantaneous-velocity
// ribbon generator (presentation-only, default-off; no solver coupling).
//
// Renders short camera-readable "long-exposure" streaks along each sampled
// particle's velocity: a flat quad whose length is the segment swept over
// shutter_seconds (clamped to [min_length, max_length]) and whose width is
// the camera-facing ribbon width. Pure instantaneous velocity — NO history
// buffer, NO atomics, NO CPU conventions. The particle billboards remain
// the authoritative per-particle visual; these streaks are dimmer, ghost
// overlays that make the velocity field readable (streams, swirls, escapes).
//
// ── Bindings (set 0) ───────────────────────────────────────────────────
//   0  readonly  vec4 pos_mass[]   particle positions + Salpeter mass in w
//                                  (render-local, the instancer's Position
//                                  convention; w ≤ 0 marks dead/merged slots)
//   1  readonly  vec4 vel[]        particle velocities (same indexing)
//   2  writeonly vec4 inst[]       MultiMesh storage — FOUR vec4 rows per
//                                  output slot, the instancer's exact
//                                  3x4 row-major transform + custom-data
//                                  record (see cassi_instancer.glsl):
//                                    row0 = (width_basis · width, origin.x)
//                                    row1 = (streak_axis · len,   origin.y)
//                                    row2 = (0,0,0,                origin.z)
//                                    row3 = (u, normalized_speed, fade, valid)
//
// ── Push constants — exactly 4 vec4 = 64 bytes (the vec4[4] ABI) ───────
//   cfg0 = (particle_count, instance_count, speed_threshold, shutter_seconds)
//   cfg1 = (min_length,     max_length,     width,           max_speed)
//   cfg2 = (camera_forward.xyz, seed)
//   cfg3 = (camera_right.xyz,   enabled)
//   seed re-shuffles the fixed-slot permutation without touching any buffer;
//   enabled < 0.5 skips the pass (every dispatched slot still gets its
//   zero record so no stale geometry can draw).
//
// ── Sampling ───────────────────────────────────────────────────────────
// One invocation per output slot. A deterministic bijective uint32 hash
// (Wang-style) permutes slot → particle index: the SAME slot always samples
// the SAME particle for a fixed seed — frame-stable, no atomics. Ineligible
// slots (dead mass, NaN/Inf payloads, speed below threshold, or degenerate
// speed) keep their all-zero record so nothing can be drawn.
//
// ── Streak geometry ────────────────────────────────────────────────────
//   len  = clamp(speed · shutter_seconds, min_length, max_length)
//   axis = normalize(velocity)                     (the streak direction)
//   width_basis = camera-right Gram-Schmidt'ed against axis (falls back to
//                 camera-up, then cross(axis, up)) → the ribbon's broad
//                 face tracks the view, readable from any camera pose.
//   origin = particle position — the streak is the segment swept over the
//            shutter window, symmetric about the particle's current spot,
//            so the billboard and its streak overlap correctly.
//   custom_data = (u, normalized_speed, fade, valid):
//     u               head fraction along the streak (0 tail → 1 head);
//                     the particle sits at the streak CENTER → u = 0.5;
//                     the material peaks its length taper at u.
//     normalized_speed = clamp(speed / max_speed, 0, 1)  → color/lightness
//     fade            = len / max_length — the streak's exposure fraction
//                     of the full shutter window (slow streaks are short
//                     AND faint; fast ones are fully exposed). α multiplier.
//     valid           = 1.0 live / 0.0 ineligible (the material discards).
// ═══════════════════════════════════════════════════════════════════════
#version 450
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer PosMass { vec4 pos_mass[]; };
layout(set = 0, binding = 1, std430) readonly buffer Velocities { vec4 vel[]; };
layout(set = 0, binding = 2, std430) restrict writeonly buffer Instances { vec4 inst[]; };

layout(push_constant, std430) uniform PC {
    vec4 cfg0;   // (particle_count, instance_count, speed_threshold, shutter_seconds)
    vec4 cfg1;   // (min_length, max_length, width, max_speed)
    vec4 cfg2;   // (camera_forward.xyz, seed)
    vec4 cfg3;   // (camera_right.xyz, enabled)
} pc;

const float EPS = 1e-6;
const float U_HEAD = 0.5;   // particle at the streak center (shutter-window midpoint)

// Deterministic slot → particle permutation (Wang hash — bijective on the
// uint32 domain, so consecutive slots decorrelate strongly under the mod).
// The same (slot, seed, count) triple always yields the same particle: the
// pass is frame-stable with zero atomics and zero history.
uint permute_particle(uint slot, uint count, float seed_f) {
    uint seed = floatBitsToUint(seed_f) ^ 0x9e3779b9u;
    uint x = slot * 0x9e3779b1u + seed;
    x = (x ^ 61u) ^ (x >> 16u);
    x = x + (x << 3u);
    x = x ^ (x >> 4u);
    x = x * 0x27d4eb2du;
    x = x ^ (x >> 15u);
    return x % count;
}

void main() {
    uint slot = gl_GlobalInvocationID.x;
    uint count = uint(max(pc.cfg0.x, 0.0) + 0.5);
    uint out_n = uint(max(pc.cfg0.y, 0.0) + 0.5);
    // Buffer-length guards: never touch memory past the host allocations
    // even if the PC disagrees with them. (SSBO .length() is in vec4s.)
    count = min(count, min(uint(pos_mass.length()), uint(vel.length())));
    if (slot >= out_n) return;

    uint base = slot * 4u;
    // Zero record first: ineligible slots always leave a clean transform so
    // the renderer can never draw stale/NaN geometry — also covers the
    // disabled/empty pass, which still zeroes every dispatched slot.
    inst[base]      = vec4(0.0);
    inst[base + 1u] = vec4(0.0);
    inst[base + 2u] = vec4(0.0);
    inst[base + 3u] = vec4(0.0);
    if (pc.cfg3.w < 0.5 || count == 0u) return;

    uint p = permute_particle(slot, count, pc.cfg2.w);
    vec4 pm = pos_mass[p];
    vec4 vv = vel[p];

    // Eligibility — reject invalid (NaN/Inf), massless (w ≤ 0, the dead-slot
    // sentinel), and slow (speed < threshold or degenerate) particles. The
    // `!(...)` test treats NaN as "not OK" instead of passing it through.
    float speed = length(vv.xyz);
    bool ok = pm.w > 0.0;
    ok = ok && !(speed < pc.cfg0.z || speed <= EPS);
    ok = ok && all(equal(pm.xyz, pm.xyz)) && all(lessThan(abs(pm.xyz), vec3(1e20)));
    ok = ok && all(equal(vv.xyz, vv.xyz)) && all(lessThan(abs(vv.xyz), vec3(1e20)));
    if (!ok) return;   // record stays all-zero

    float shutter = max(pc.cfg0.w, 0.0);
    float min_len = max(pc.cfg1.x, 0.0);
    float max_len = max(pc.cfg1.y, min_len);
    float width   = max(pc.cfg1.z, 0.0);
    float max_speed = max(pc.cfg1.w, EPS);

    // Long-exposure streak: the segment swept in shutter_seconds, bounded.
    float len = clamp(speed * shutter, min_len, max_len);

    // Streak axis = velocity direction (unit).
    vec3 axis = vv.xyz / speed;

    // Camera basis (defensive: the host always supplies an orthonormal
    // pair, but a zero/parallel input must not poison the ribbon).
    vec3 fwd = pc.cfg2.xyz;
    vec3 right = pc.cfg3.xyz;
    if (dot(fwd, fwd) < EPS)     fwd = vec3(0.0, 0.0, -1.0);
    if (dot(right, right) < EPS) right = vec3(1.0, 0.0, 0.0);
    fwd = normalize(fwd);
    right = normalize(right);
    vec3 up = cross(right, fwd);
    if (dot(up, up) < EPS) up = vec3(0.0, 1.0, 0.0); else up = normalize(up);

    // Camera-readable width basis: camera-right orthogonalized against the
    // streak axis, so the ribbon's broad face tracks the view. Degenerate
    // (axis ∥ right) → camera-up; last resort cross(axis, up) (axis ≈ view
    // axis — any screen-space perpendicular reads the same end-on).
    vec3 w = right - axis * dot(axis, right);
    if (dot(w, w) < EPS) {
        w = up - axis * dot(axis, up);
    }
    if (dot(w, w) < EPS) {
        w = cross(axis, up);
    }
    w = normalize(w);

    // 3x4 row-major transform (instancer record format) + custom data.
    inst[base]      = vec4(w * width, pm.x);
    inst[base + 1u] = vec4(axis * len, pm.y);
    inst[base + 2u] = vec4(0.0, 0.0, 0.0, pm.z);
    float ns = clamp(speed / max_speed, 0.0, 1.0);
    float fade = clamp(len / max_len, 0.0, 1.0);
    inst[base + 3u] = vec4(U_HEAD, ns, fade, 1.0);
}
