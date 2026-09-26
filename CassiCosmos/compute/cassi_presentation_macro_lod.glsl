#[compute]
// canonical layout: scripts/contracts/layout.gd
// Cassi Presentation Macro-Site LOD — writes one MultiMesh record per
// topology site, gated by coherence. Presentation-only and default-off
// (CassiSim enables it alongside the particle presentation profile);
// with enabled = 0 every record is a finite zero, so the layer renders
// nothing and the default battery is untouched.
//
// ═══════════════════════════════════════════════════════════════════════
// SHARED ABI (owned by the global-RD renderer wiring; see the fused-volume
// set for the source buffers):
//   binding 0: readonly compact optical payload, vec4[2·site]:
//              optical[2s+0] = render-local xyz (tile-E) + opacity
//              optical[2s+1] = EY, EI, coherence, gradient
//              (cassi_voronoi_optical_payload.glsl — verbatim layout).
//   binding 1: readonly topology status, uint[4] = {generation, required,
//              overflow, site_count} (cassi_voronoi_adjacency_csr.glsl /
//              cassi_site_physics.glsl convention).
//   binding 2: writeonly MultiMesh storage, four vec4 rows per site —
//              3×4 row-major transform + custom data (the Godot #76884
//              instance record format, identical to the particle
//              instancer's 16-float/instance output).
//   PC vec4[1]: (site_count, min_coherence, base_size, enabled) — no
//              other resources, exactly one 16-byte group.
// Output custom data: (coherence, opacity, phase01, valid) — consumed by
// shaders/presentation_macro_billboard.gdshader.
#version 450
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

const float TAU = 6.283185307179586;

layout(set = 0, binding = 0, std430) readonly buffer Optical { vec4 optical[]; };
layout(set = 0, binding = 1, std430) readonly buffer TopologyStatus { uint status[]; };
layout(set = 0, binding = 2, std430) writeonly buffer Instances { vec4 inst[]; };

layout(push_constant, std430) uniform PC {
    float site_count_f;   // expected site count (dispatch size)
    float min_coherence;  // coherence gate: sites below are zeroed
    float base_size;      // per-site billboard size (no mass/opacity claim)
    float enabled;        // 0 = pass disabled (writes finite zeros), 1 = live
} pc;

bool finite_float(float value) {
    return !(isnan(value) || isinf(value));
}

void main() {
    uint s = gl_GlobalInvocationID.x;
    uint site_count = uint(max(pc.site_count_f, 0.0) + 0.5);
    if (site_count == 0u || s >= site_count) return;
    uint base = 4u * s;
    if (base + 3u >= uint(inst.length())) return;

    // Default: finite zero record — zero transform (invisible) + valid = 0.
    inst[base]      = vec4(0.0);
    inst[base + 1u] = vec4(0.0);
    inst[base + 2u] = vec4(0.0);
    inst[base + 3u] = vec4(0.0);

    if (pc.enabled <= 0.5) return;

    // Status validation: a generation must have been published, no CSR
    // overflow, and the published count must match the PC (the host
    // dispatches only a complete topology — the same gates as the site
    // physics topology_ok()). Any mismatch zeroes every record rather than
    // rendering a partially-built topology.
    if (uint(status.length()) < 4u) return;
    if (status[0] == 0u || status[2] != 0u || status[3] != site_count) return;

    uint oi = 2u * s;
    if (oi + 1u >= uint(optical.length())) return;

    vec4 pos_op = optical[oi];
    vec4 psi    = optical[oi + 1u];
    float ey    = psi.x;
    float ei    = psi.y;
    float coh   = psi.z;
    // A non-finite payload entry (field or position) is an invalid site →
    // the finite zero record stands.
    if (!finite_float(ey) || !finite_float(ei) || !finite_float(coh)
            || !finite_float(pos_op.w)
            || !finite_float(pos_op.x) || !finite_float(pos_op.y)
            || !finite_float(pos_op.z)) return;
    // Coherence gate: below min_coherence the site is not macro-relevant.
    if (coh < pc.min_coherence) return;

    // Phase θ = atan(EI, EY) wrapped to [0,1) — the instancer's field-phase
    // convention (cassi_instancer.glsl tri_phase), so Spectrum motes share
    // the particle hue wheel.
    float phase01 = mod(atan(ei, ey) / TAU + 0.5, 1.0);

    // Presentation-only size: base_size with a gentle coherence emphasis so
    // coherent condensations dominate the skyline. Deliberately NO mass or
    // opacity dependence — this layer makes no physical mass claim.
    float size = pc.base_size * mix(0.7, 1.15, clamp(coh, 0.0, 1.0));

    // Row-major 3×4: scale on the diagonal (the material billboards it),
    // origin = the optical payload's render-local site position.
    inst[base]      = vec4(size, 0.0, 0.0, pos_op.x);
    inst[base + 1u] = vec4(0.0, size, 0.0, pos_op.y);
    inst[base + 2u] = vec4(0.0, 0.0, size, pos_op.z);
    inst[base + 3u] = vec4(coh, pos_op.w, phase01, 1.0);  // custom_data: (coherence, opacity, phase01, valid)
}
