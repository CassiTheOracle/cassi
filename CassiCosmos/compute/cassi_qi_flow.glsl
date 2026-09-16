#[compute]
#version 450
// ═══════════════════════════════════════════════════════════════════════
// CASSI QI-FLOW — native-site graph-bond energy current, its bounded
// current-aligned graph paths, the site-field layer, and BH source markers.
//
// RENDER-ONLY. This kernel never writes physics state: it READs the
// authoritative committed first-n_sites half of psi_y/psi_i/pi_y/pi_i plus
// sites/volume/CSR and writes only its own node/instance buffers.
//
// ── The current (per node, per channel) ────────────────────────────────
// Exactly the research reference
// (research/stellar_cells/native_counterflow_currents.py):
//   edge (i,j): d = minimum_image(sites[j] - sites[i])   [shader minimum
//               image, evaluated per DIRECTED CSR row — at an exact
//               half-period tie the shader's floor() transform need not
//               give d_ji == -d_ij, and the reference preserves that]
//   P_Y = -c2*(psi_y[j]-psi_y[i])*(pi_y[i]+pi_y[j]) / (2*d)
//   P_I = -phi*c2*(psi_i[j]-psi_i[i])*(pi_i[i]+pi_i[j]) / (2*d)
//   J(s) = (Σ_edges P_ij * d_ij) / (2*V_s),  V_s = max(|vol[s]|, volume_floor)
// This is the c2-wave ENERGY current of the graph, NOT a material velocity
// and NOT a gradient of q. Momentum enters linearly (π), field difference
// linearly (Δψ): zero momenta ⇒ P = 0, and a spatially uniform field
// (Δψ = 0) ⇒ P = 0, so both give identically zero currents and therefore
// no flow geometry at all.
//
// The winding term of the symplectic kick (pc.winding in
// cassi_site_physics.glsl) is deliberately NOT folded in here: this kernel
// reports the c2-wave channel alone. The host labels the statistic
// "c2-wave channel" whenever winding is nonzero rather than claiming a
// conserved energy flux.
//
// ── Robust display normalization (no readback, no history) ─────────────
// Mode 1 atomically publishes the max |J_Y|, max |J_I| and max amplitude
// as float bit patterns (monotone for non-negative finite floats). Flow
// GEOMETRY is built from unit directions with a graph-length step, so an
// outlier can never shrink other streamlines; INTENSITY is a compressive
// map (mag/ref)^0.35 of that bounded reference, so a 100x outlier still
// leaves a 20% intensity floor on typical structure instead of erasing it.
// The reference is a clamped display scale — it makes no physical claim.
//
// ── Modes (uniform in PC.cfg0.x) ───────────────────────────────────────
//   0  clear Stats        (1 workgroup; must precede mode 1)
//   1  node currents + q / signed imbalance / amplitude + Stats atomics
//   2  filament instance records (MultiMesh, SEGMENTS quads per seed slot)
//   3  site-field instance records (one camera-facing splat per site)
//   4  BH source marker instance records (BHData records, capacity 15)
//
// DISPATCH ORDER (one compute list, barriers between):
//   0 → barrier → 1 → barrier → (2, 3, 4 — mutually independent)
// Main must call this outside its own open compute list.
//
// ── Bindings (set 0, all std430) ───────────────────────────────────────
//   0  readonly  vec4 sites[]        tile coords in [0, 2*extent)
//   1  readonly  float psi_y[]       authoritative committed half
//   2  readonly  float psi_i[]
//   3  readonly  float pi_y[]
//   4  readonly  float pi_i[]
//   5  readonly  float volume[]
//   6  readonly  uint offsets[]      CSR row starts (n+1)
//   7  readonly  uint neighbors[]    CSR columns
//   8  readonly  uint status[4]      {generation, required, overflow, count}
//   9  readonly  vec4 bh[36]         BH header + 15 records at 4+2*slot
//  10  rw        vec4 nodes[]        4 vec4 per site (see below)
//  11  coherent  uint stats[8]       [0] max|J_Y| [1] max|J_I| [2] max amp
//  12  writeonly vec4 finst[]        MultiMesh records, 4 vec4 / segment
//  13  writeonly vec4 sinst[]        MultiMesh records, 4 vec4 / site
//  14  writeonly vec4 xinst[]        MultiMesh records, 4 vec4 / source
//
// ── nodes[] record (per site s, base = 4*s) ────────────────────────────
//   [base+0] = (J_Y.xyz, coherence q)
//   [base+1] = (J_I.xyz, signed imbalance eps/max(|rho|,1e-6) clipped ±1)
//   [base+2] = (amplitude |rho|, |J_Y|, |J_I|, field_ok)
//   [base+3] = (local.xyz, valid)   local = tile - extent + offset
//   valid    = 1 only when the topology status passed and the LOCAL POSITION
//              is finite; 0 zeroes every consumer's geometry (no stale draw).
//   field_ok = 1 when psi/pi at this site are finite; invalid data is hidden,
//              not painted as low coherence.
//   local is in the RENDER-LOCAL frame the particle instancer draws in:
//   world - render_origin. Sites live on a periodic tile, so
//   tile - extent + offset with offset = window_center - render_origin is
//   the representative inside the render window.
//
// ── MultiMesh records (Godot 4 3x4 row-major + custom data) ────────────
//   rows 0..2 = row-major 3x4 transform: basis in columns, origin in column 3.
//   row3      = custom data (consumed by shaders/qi_flow_*.gdshader):
//     filament (channel, u_along_stream, intensity, valid)
//     site     (signed_or_unsigned value, magnitude, 0, valid)
//     source   (mass01, 0, 0, valid)
// Every dispatched slot writes its full record set every frame — ineligible
// slots become finite ZERO records (valid = 0) so the materials discard and
// no stale geometry can survive a mode change, a pause, or a topology
// rebuild.
// ═══════════════════════════════════════════════════════════════════════
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

const float EPS = 1e-12;
const float EPS_DISTANCE2 = 1e-16;
const float MAG_EPS = 1e-9;
const float RHO_FLOOR = 1e-6;
const float OVERLAP = 1.25;          // ribbon overlap across a shared path node
const float INTENSITY_POWER = 0.35;  // compressive display map (see header)
const uint SEGMENTS = 16u;           // short segments per streamline
const uint SOURCE_CAP = 15u;         // BH record slots (contract)

layout(set = 0, binding = 0, std430) readonly buffer Sites { vec4 sites[]; };
layout(set = 0, binding = 1, std430) readonly buffer PsiY { float psi_y[]; };
layout(set = 0, binding = 2, std430) readonly buffer PsiI { float psi_i[]; };
layout(set = 0, binding = 3, std430) readonly buffer PiY { float pi_y[]; };
layout(set = 0, binding = 4, std430) readonly buffer PiI { float pi_i[]; };
layout(set = 0, binding = 5, std430) readonly buffer Volumes { float volume[]; };
layout(set = 0, binding = 6, std430) readonly buffer CsrOffsets { uint offsets[]; };
layout(set = 0, binding = 7, std430) readonly buffer CsrNeighbors { uint neighbors[]; };
layout(set = 0, binding = 8, std430) readonly buffer TopologyStatus { uint status[]; };
layout(set = 0, binding = 9, std430) readonly buffer BHData { vec4 bh[36]; };
layout(set = 0, binding = 10, std430) buffer Nodes { vec4 nodes[]; };
layout(set = 0, binding = 11, std430) coherent buffer Stats { uint stats[]; };
layout(set = 0, binding = 12, std430) restrict writeonly buffer FilamentInstances { vec4 finst[]; };
layout(set = 0, binding = 13, std430) restrict writeonly buffer SiteInstances { vec4 sinst[]; };
layout(set = 0, binding = 14, std430) restrict writeonly buffer SourceInstances { vec4 xinst[]; };

// Exactly 32 floats (128 bytes) — the same PC width the volume passes use.
layout(push_constant, std430) uniform PC {
    vec4 cfg0;  // (mode, site_count, active_filament_slots, channel)
    vec4 cfg1;  // (extent.x, extent.y, extent.z, splat_scale)
    vec4 cfg2;  // (offset.xyz, min_align)
    vec4 cfg3;  // (c2, phi, volume_floor, scalar_mode)
    vec4 cfg4;  // (seeds_per_channel, reserved, stream_width, seed_salt)
    vec4 cfg5;  // (camera_right.xyz, sources_on)
    vec4 cfg6;  // (camera_forward.xyz, field_on)
    vec4 cfg7;  // (generation, render_origin.xyz)
} pc;

bool finite_float(float v) { return !(isnan(v) || isinf(v)); }
bool finite_vec3(vec3 v) {
    return finite_float(v.x) && finite_float(v.y) && finite_float(v.z);
}
uint rounded_uint(float v) { return uint(max(v, 0.0) + 0.5); }

uint operation_mode() { return rounded_uint(pc.cfg0.x); }
uint site_count() { return rounded_uint(pc.cfg0.y); }
uint active_filament_slots() { return rounded_uint(pc.cfg0.z); }
uint channel_mode() { return rounded_uint(pc.cfg0.w); }
vec3 box_extent() { return max(abs(pc.cfg1.xyz), vec3(1.0e-6)); }
float splat_scale() { return max(pc.cfg1.w, 1.0e-4); }
vec3 domain_offset() { return pc.cfg2.xyz; }
float min_align() { return pc.cfg2.w; }
float c2_value() { return max(pc.cfg3.x, 0.0); }
float phi_value() {
    return (abs(pc.cfg3.y) > 1.0e-3) ? pc.cfg3.y : 1.6180339887498948;
}
float volume_guard() { return max(abs(pc.cfg3.z), 1.0e-12); }
uint scalar_mode() { return rounded_uint(pc.cfg3.w); }
uint seed_count() { return rounded_uint(pc.cfg4.x); }
float stream_width() { return max(pc.cfg4.z, 0.0); }
uint seed_salt() { return floatBitsToUint(pc.cfg4.w); }
vec3 camera_right() { return pc.cfg5.xyz; }
bool sources_on() { return pc.cfg5.w > 0.5; }
vec3 camera_forward() { return pc.cfg6.xyz; }
bool field_on() { return pc.cfg6.w > 0.5; }
uint generation() { return rounded_uint(pc.cfg7.x); }
vec3 render_origin() { return pc.cfg7.yzw; }

// Site tile positions are periodic; this is the only coordinate transform
// the shared operators use (cassi_site_physics.glsl, verbatim form).
vec3 minimum_image(vec3 delta) {
    vec3 period = 2.0 * box_extent();
    return delta - period * floor(delta / period + vec3(0.5));
}

// GPU-only topology gate: exactly the native mode-1/2 predicate, with the
// host-published generation required to match the frame's generation. A
// mismatched or incomplete topology zeroes every output rather than drawing
// a half-built CSR.
bool topology_ready(uint ns) {
    if (uint(status.length()) < 4u) return false;
    uint gen = generation();
    if (gen == 0u) return false;
    return status[0] == gen && status[2] == 0u && status[3] == ns;
}

bool site_readable(uint s, uint ns) { return s < ns && s < uint(sites.length()); }

bool field_readable(uint s) {
    return s < uint(psi_y.length()) && s < uint(psi_i.length())
        && s < uint(pi_y.length()) && s < uint(pi_i.length());
}

// Deterministic bijective uint32 permutation (Wang hash, the presentation
// trail convention): a seed slot always samples the same site for a fixed
// salt, so the geometry is frame-stable with zero atomics and zero history.
uint permute_site(uint seed, uint count, uint salt) {
    uint x = seed * 0x9e3779b1u + salt;
    x = (x ^ 61u) ^ (x >> 16u);
    x = x + (x << 3u);
    x = x ^ (x >> 4u);
    x = x * 0x27d4eb2du;
    x = x ^ (x >> 15u);
    return x % max(count, 1u);
}

vec3 node_position(uint s) { return nodes[4u * s + 3u].xyz; }

bool node_usable(uint s) {
    if (4u * s + 3u >= uint(nodes.length())) return false;
    vec4 tail = nodes[4u * s + 3u];
    if (tail.w < 0.5) return false;
    return nodes[4u * s + 2u].w > 0.5;   // field_ok
}

vec3 node_current(uint s, uint ch) {
    vec3 jy = nodes[4u * s].xyz;
    if (ch == 0u) return jy;
    vec3 ji = nodes[4u * s + 1u].xyz;
    if (ch == 1u) return ji;
    return jy + ji;
}

float current_reference(uint ch) {
    if (uint(stats.length()) < 3u) return 1.0;
    float ry = uintBitsToFloat(stats[0]);
    float ri = uintBitsToFloat(stats[1]);
    if (!finite_float(ry)) ry = 0.0;
    if (!finite_float(ri)) ri = 0.0;
    if (ch == 0u) return max(ry, MAG_EPS);
    if (ch == 1u) return max(ri, MAG_EPS);
    return max(ry + ri, MAG_EPS);   // |J_Y + J_I| <= |J_Y| + |J_I|
}

// Compressive, bounded display intensity. Reference is a clamped display
// scale (see the header): it is monotone in |J| but carries no physics.
float display_intensity(float magnitude, float reference) {
    float t = clamp(magnitude / max(reference, MAG_EPS), 0.0, 1.0);
    return pow(t, INTENSITY_POWER);
}

void write_zero_segment(uint base) {
    finst[base] = vec4(0.0);
    finst[base + 1u] = vec4(0.0);
    finst[base + 2u] = vec4(0.0);
    finst[base + 3u] = vec4(0.0);
}

void zero_filament_slot(uint slot) {
    uint base = slot * 4u * SEGMENTS;
    for (uint k = 0u; k < SEGMENTS; ++k) {
        write_zero_segment(base + 4u * k);
    }
}

// Camera-readable ribbon width basis: the camera-right vector orthogonalized
// against the local tangent, with deterministic fallbacks. Pure view
// adaptation — it invents no curvature and no path.
vec3 ribbon_width_basis(vec3 axis) {
    vec3 right = camera_right();
    vec3 fwd = camera_forward();
    if (dot(right, right) < EPS) right = vec3(1.0, 0.0, 0.0);
    if (dot(fwd, fwd) < EPS) fwd = vec3(0.0, 0.0, -1.0);
    right = normalize(right);
    fwd = normalize(fwd);
    vec3 up = cross(right, fwd);
    if (dot(up, up) < EPS) up = vec3(0.0, 1.0, 0.0); else up = normalize(up);
    vec3 w = right - axis * dot(axis, right);
    if (dot(w, w) < EPS) w = up - axis * dot(axis, up);
    if (dot(w, w) < EPS) w = cross(axis, up);
    return normalize(w);
}

// ── Mode 0: clear the atomic statistics ────────────────────────────────
void clear_stats() {
    uint gid = gl_GlobalInvocationID.x;
    if (gid < uint(stats.length())) stats[gid] = 0u;
}

// ── Mode 1: node currents, field scalars, statistics ───────────────────
void compute_nodes() {
    uint ns = site_count();
    uint s = gl_GlobalInvocationID.x;
    if (s >= ns) return;
    uint base = 4u * s;
    if (base + 3u >= uint(nodes.length())) return;
    // Default: finite ZERO record with valid = 0 — every early return below
    // (unready topology, missing state, non-finite position) leaves geometry
    // that cannot draw.
    nodes[base] = vec4(0.0);
    nodes[base + 1u] = vec4(0.0);
    nodes[base + 2u] = vec4(0.0);
    nodes[base + 3u] = vec4(0.0);
    if (!site_readable(s, ns)) return;
    if (s + 1u >= uint(offsets.length()) || uint(volume.length()) <= s) return;
    if (!topology_ready(ns)) return;

    vec3 ext = box_extent();
    vec3 local = sites[s].xyz - ext + domain_offset();
    if (!finite_vec3(local)) return;

    float y = 0.0;
    float i = 0.0;
    float py = 0.0;
    float pi = 0.0;
    bool field_ok = field_readable(s);
    if (field_ok) {
        y = psi_y[s];
        i = psi_i[s];
        py = pi_y[s];
        pi = pi_i[s];
        field_ok = finite_float(y) && finite_float(i)
            && finite_float(py) && finite_float(pi);
    }

    float q = 0.0;
    float imbalance = 0.0;
    float amplitude = 0.0;
    vec3 jy = vec3(0.0);
    vec3 ji = vec3(0.0);

    if (field_ok) {
        float phi = phi_value();
        float rho = y + i;
        float eps = y - phi * i;
        float denominator = rho * rho + 1.0 / (phi * phi) + eps * eps;
        q = (denominator > EPS) ? clamp(rho * rho / denominator, 0.0, 1.0) : 0.0;
        imbalance = clamp(eps / max(abs(rho), RHO_FLOOR), -1.0, 1.0);
        amplitude = abs(rho);

        uint begin = offsets[s];
        uint end = offsets[s + 1u];
        if (end < begin) end = begin;
        end = min(end, uint(neighbors.length()));
        float inverse_2v = 1.0 / (2.0 * max(abs(volume[s]), volume_guard()));
        float c2 = c2_value();
        for (uint cursor = begin; cursor < end; ++cursor) {
            uint n = neighbors[cursor];
            if (n == s || !site_readable(n, ns)) continue;
            if (!field_readable(n)) continue;
            vec3 displacement = minimum_image(sites[n].xyz - sites[s].xyz);
            float distance2 = dot(displacement, displacement);
            if (!(distance2 > EPS_DISTANCE2)) continue;
            float distance = max(sqrt(distance2), EPS);
            // Signed graph-bond energy current (the native reference pair).
            float dy = psi_y[n] - y;
            float di = psi_i[n] - i;
            float power_y = -c2 * dy * (py + pi_y[n]) / (2.0 * distance);
            float power_i = -phi * c2 * di * (pi + pi_i[n]) / (2.0 * distance);
            if (!finite_float(power_y)) power_y = 0.0;
            if (!finite_float(power_i)) power_i = 0.0;
            jy += power_y * displacement;
            ji += power_i * displacement;
        }
        jy *= inverse_2v;
        ji *= inverse_2v;
        if (!finite_vec3(jy)) jy = vec3(0.0);
        if (!finite_vec3(ji)) ji = vec3(0.0);
        if (!finite_float(q)) q = 0.0;
        if (!finite_float(imbalance)) imbalance = 0.0;
        if (!finite_float(amplitude)) amplitude = 0.0;
    }

    // Statistics: only non-negative finite values are published as float bit
    // patterns (monotone for that domain); NaN/Inf never poison the max.
    float magnitude_y = length(jy);
    float magnitude_i = length(ji);
    if (finite_float(magnitude_y)) atomicMax(stats[0], floatBitsToUint(magnitude_y));
    if (finite_float(magnitude_i)) atomicMax(stats[1], floatBitsToUint(magnitude_i));
    if (finite_float(amplitude)) atomicMax(stats[2], floatBitsToUint(amplitude));

    nodes[base] = vec4(jy, q);
    nodes[base + 1u] = vec4(ji, imbalance);
    nodes[base + 2u] = vec4(amplitude, magnitude_y, magnitude_i,
                            field_ok ? 1.0 : 0.0);
    nodes[base + 3u] = vec4(local, 1.0);
}

// ── Mode 2: current-aligned graph paths ─────────────────────────────────
// One slot = SEGMENTS real CSR bonds from a deterministically sampled site.
// Each bond must point along the local current; the previous tangent only
// breaks ties towards a smoother path. These are discrete graph paths, not
// continuous integral curves or parcel trajectories. Stop at the draw-window
// boundary rather than wrapping a line across the image.
void emit_filaments() {
    uint slot = gl_GlobalInvocationID.x;
    uint capacity = uint(finst.length()) / (4u * SEGMENTS);
    if (slot >= capacity) return;
    uint ch = 0u;
    uint seed = slot;
    uint mode = channel_mode();
    if (mode == 0u) {                       // Both: gold slots then teal slots
        if (slot >= seed_count()) { ch = 1u; seed = slot - seed_count(); }
    } else if (mode == 1u) {                // Yang only
        ch = 0u;
    } else if (mode == 2u) {                // Yin only
        ch = 1u;
    } else {                                // Net (Yang + Yin)
        ch = 2u;
    }
    if (slot >= active_filament_slots() || slot >= capacity) {
        zero_filament_slot(slot);
        return;
    }

    uint ns = site_count();
    if (ns == 0u || !topology_ready(ns)
            || ns > uint(sites.length()) || ns + 1u > uint(offsets.length())) {
        zero_filament_slot(slot);
        return;
    }
    uint start = permute_site(seed, ns, seed_salt());
    if (!node_usable(start)) {
        zero_filament_slot(slot);
        return;
    }

    vec3 direction = node_current(start, ch);
    float magnitude = length(direction);
    float reference = current_reference(ch);
    // Suppress float-roundoff ghosts when equal opposing channels cancel.
    // This display floor does not modify the measured node currents.
    float display_floor = max(MAG_EPS, reference * 1.0e-6);
    if (!(magnitude > display_floor) || !finite_float(magnitude)) {
        zero_filament_slot(slot);            // zero momentum / uniform field
        return;
    }
    vec3 tangent = direction / magnitude;
    vec3 point = node_position(start);
    uint current_site = start;
    uint written = 0u;
    uint base_slot = slot * 4u * SEGMENTS;
    vec3 ext = box_extent();
    float width = stream_width();
    float align_floor = min_align();

    for (uint k = 0u; k < SEGMENTS; ++k) {
        uint begin = offsets[current_site];
        uint end = offsets[current_site + 1u];
        if (end < begin) end = begin;
        end = min(end, uint(neighbors.length()));

        uint best = 0xFFFFFFFFu;
        float best_score = -2.0;
        vec3 best_displacement = vec3(0.0);
        vec3 heading = direction / max(magnitude, MAG_EPS);
        for (uint cursor = begin; cursor < end; ++cursor) {
            uint n = neighbors[cursor];
            if (n >= ns || n == current_site) continue;
            if (!node_usable(n)) continue;
            vec3 displacement = minimum_image(sites[n].xyz - sites[current_site].xyz);
            float distance2 = dot(displacement, displacement);
            if (!(distance2 > EPS_DISTANCE2)) continue;
            vec3 unit = displacement / sqrt(distance2);
            if (dot(heading, unit) < align_floor) continue;
            float score = 0.6 * dot(heading, unit) + 0.4 * dot(tangent, unit);
            if (score > best_score) {
                best_score = score;
                best = n;
                best_displacement = displacement;
            }
        }
        if (best == 0xFFFFFFFFu || best_score < align_floor) break;

        // Match the native minimum-image operator, but never draw outside
        // the finite open-topology window or extrapolate its field.
        vec3 endpoint = point + best_displacement;
        vec3 relative = endpoint - domain_offset();
        if (abs(relative.x) > ext.x * 1.001
                || abs(relative.y) > ext.y * 1.001
                || abs(relative.z) > ext.z * 1.001) break;

        vec3 step = endpoint - point;
        float length_step = length(step);
        if (!(length_step > EPS) || !finite_vec3(step)) break;
        vec3 axis = step / length_step;
        vec3 middle = 0.5 * (point + endpoint);
        vec3 across = ribbon_width_basis(axis);
        uint base = base_slot + 4u * k;
        vec3 normal = cross(across, axis);
        vec3 along = axis * (length_step * OVERLAP);
        // Godot stores three ROWS; basis vectors occupy their columns.
        finst[base] = vec4(across.x * width, along.x, normal.x, middle.x);
        finst[base + 1u] = vec4(across.y * width, along.y, normal.y, middle.y);
        finst[base + 2u] = vec4(across.z * width, along.z, normal.z, middle.z);
        float u = (float(k) + 0.5) / float(SEGMENTS);
        finst[base + 3u] = vec4(float(ch), u,
                                display_intensity(magnitude, reference), 1.0);
        written = k + 1u;

        point = endpoint;
        current_site = best;
        direction = node_current(best, ch);
        magnitude = length(direction);
        tangent = axis;
        if (!finite_float(magnitude) || !(magnitude > display_floor)) break;
    }

    // Every unwritten segment of this slot stays a finite zero record.
    for (uint k = written; k < SEGMENTS; ++k) {
        write_zero_segment(base_slot + 4u * k);
    }
}

// ── Mode 3: site-field reconstruction (one splat per authoritative site) ─
// No coherence shortlist, no q threshold, no culling of low-q cores: every
// authoritative site gets a record, and the material's alpha floor keeps the
// raw scalar readable where the field is weak. The value handed to the
// material is the selected channel; the material owns the palette.
void emit_sites() {
    uint slot = gl_GlobalInvocationID.x;
    uint capacity = uint(sinst.length()) / 4u;
    if (slot >= capacity) return;
    uint base = 4u * slot;
    if (base + 3u >= uint(sinst.length())) return;
    sinst[base] = vec4(0.0);
    sinst[base + 1u] = vec4(0.0);
    sinst[base + 2u] = vec4(0.0);
    sinst[base + 3u] = vec4(0.0);
    if (!field_on()) return;
    uint ns = site_count();
    if (ns == 0u) return;
    // Every authoritative site is represented: when the layer is smaller
    // than the site array (a topology above the host's splat cap), the slot
    // is spread DETERMINISTICALLY across the whole array — a uniform sample
    // of all sites, never a biased prefix and never a shortlist.
    uint s = slot;
    if (ns > capacity) {
        float mapped = float(slot) * float(ns) / float(capacity);
        s = min(uint(mapped + 0.5), ns - 1u);
    }
    if (s >= ns || 4u * s + 3u >= uint(nodes.length())) return;
    if (!topology_ready(ns)) return;
    vec4 position_record = nodes[4u * s + 3u];
    if (position_record.w < 0.5) return;
    if (!finite_vec3(position_record.xyz)) return;

    float q = nodes[4u * s].w;
    float imbalance = nodes[4u * s + 1u].w;
    float amplitude = nodes[4u * s + 2u].x;
    float field_ok = nodes[4u * s + 2u].w;
    if (field_ok < 0.5) return; // missing/invalid field is not low coherence

    uint mode = scalar_mode();
    float value = 0.0;
    float magnitude = 0.0;
    if (mode == 0u) {                        // coherence q (bounded [0,1])
        value = clamp(q, 0.0, 1.0);
        magnitude = value;
    } else if (mode == 1u) {                 // signed imbalance (clipped ±1)
        value = clamp(imbalance, -1.0, 1.0);
        magnitude = abs(value);
    } else {                                 // field amplitude, compressive
        float reference = uintBitsToFloat(stats[2]);
        if (!finite_float(reference)) reference = 0.0;
        value = display_intensity(max(amplitude, 0.0), max(reference, MAG_EPS));
        magnitude = value;
    }
    if (!finite_float(value) || !finite_float(magnitude)) {
        value = 0.0;
        magnitude = 0.0;
    }

    // Splat size: a fraction of the mean site spacing, which is exactly
    // sqrt(c2) for this solver's c2 = (box_volume/count)^(2/3). Compact,
    // overlapping soft supports — never a cube, never a wall.
    float spacing = max(sqrt(c2_value()), 1.0e-6);
    float size = splat_scale() * spacing;
    sinst[base] = vec4(size, 0.0, 0.0, position_record.x);
    sinst[base + 1u] = vec4(0.0, size, 0.0, position_record.y);
    sinst[base + 2u] = vec4(0.0, 0.0, size, position_record.z);
    sinst[base + 3u] = vec4(value, magnitude, 0.0, 1.0);
}

// ── Mode 4: BH source markers (real records only) ──────────────────────
// bh[4 + 2*slot] = (world position, mass). A marker needs a strictly
// positive FINITE mass and a finite position; a negative, zero, NaN or Inf
// record draws nothing. Position is world space, so the drawing frame
// subtracts render_origin (the site tile offset does NOT apply to BHs).
void emit_sources() {
    uint slot = gl_GlobalInvocationID.x;
    uint capacity = min(uint(xinst.length()) / 4u, SOURCE_CAP);
    if (slot >= capacity) return;
    uint base = 4u * slot;
    xinst[base] = vec4(0.0);
    xinst[base + 1u] = vec4(0.0);
    xinst[base + 2u] = vec4(0.0);
    xinst[base + 3u] = vec4(0.0);
    if (!sources_on()) return;
    if (!topology_ready(site_count())) return;
    uint record = 4u + 2u * slot;
    if (record >= uint(bh.length())) return;
    vec4 record_data = bh[record];
    float mass = record_data.w;
    if (!(mass > 0.0) || !finite_float(mass)) return;
    vec3 world = record_data.xyz;
    if (!finite_vec3(world)) return;
    vec3 local = world - render_origin();
    if (!finite_vec3(local)) return;

    float spacing = max(sqrt(c2_value()), 1.0e-6);
    float normalized = clamp(log2(1.0 + mass) / 12.0, 0.0, 1.0);
    float size = spacing * mix(0.9, 2.2, normalized);
    xinst[base] = vec4(size, 0.0, 0.0, local.x);
    xinst[base + 1u] = vec4(0.0, size, 0.0, local.y);
    xinst[base + 2u] = vec4(0.0, 0.0, size, local.z);
    xinst[base + 3u] = vec4(normalized, 0.0, 0.0, 1.0);
}

void main() {
    uint mode = operation_mode();
    if (mode == 0u) {
        clear_stats();
    } else if (mode == 1u) {
        compute_nodes();
    } else if (mode == 2u) {
        emit_filaments();
    } else if (mode == 3u) {
        emit_sites();
    } else if (mode == 4u) {
        emit_sources();
    }
}
