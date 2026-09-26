#[compute]
#version 450

// Site-native particle mass deposition. Sites are tile coordinates in
// [0, 2*extent), while particles are world coordinates. Open-world queries
// reject particles outside the live window; the periodic branch is retained
// only for explicit compatibility callers.
//
// HashSites contains original site IDs (the .w payload from the shortlist),
// never compact shortlist slots. MassFix is a deterministic carry-safe
// fixed-point accumulator; only mode 2 converts the four byte digits to float.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;
layout(set = 0, binding = 0, std430) readonly buffer Pos { vec4 pos[]; };
layout(set = 0, binding = 1, std430) readonly buffer Sites { vec4 sites[]; };
layout(set = 0, binding = 2, std430) readonly buffer HashStart { uint hash_start[]; };
layout(set = 0, binding = 3, std430) readonly buffer HashSites { uint hash_sites[]; };
layout(set = 0, binding = 4, std430) readonly buffer HashCfg { vec4 hash_cfg[]; };
layout(set = 0, binding = 5, std430) coherent buffer MassFix { uvec4 mass_fix[]; };
layout(set = 0, binding = 6, std430) coherent buffer SiteMass { float site_mass[]; };
// [0] = geometry epoch; each particle record is xyz bits, original site ID,
// epoch at 1 + 5*particle.  0xffffffff is the no-site sentinel.
layout(set = 0, binding = 7, std430) coherent buffer SiteQueryCache {
    uint query_cache[];
};

layout(push_constant, std430) uniform PC {
    float mode;
    float particle_N;
    float n_sites;
    float scale;
    float extent_x;
    float extent_y;
    float extent_z;
    float window_x;
    float window_y;
    float window_z;
    float hash_H;
    float pad;       // 1 = open-world reject/no-wrap; 0 = compatibility periodic
} pc;

const float FIXED_SCALE = 16777216.0;
const float MAX_FIXED_FLOAT = 4294967040.0;
const uint UINT_MAX_VALUE = 0xffffffffu;

bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
bool finite_vec3(vec3 value) {
    return !(any(isnan(value)) || any(isinf(value)));
}
uint pc_count(float value) {
    if (!finite_float(value) || value <= 0.0) return 0u;
    return uint(value + 0.5);
}
float fixed_scale() {
    return (finite_float(pc.scale) && pc.scale > 0.0) ? pc.scale : FIXED_SCALE;
}

float wrap_scalar(float value, float period) {
    float wrapped = mod(value, period);
    if (wrapped < 0.0) wrapped += period;
    return wrapped >= period ? 0.0 : wrapped;
}
vec3 wrap_tile(vec3 value, vec3 period) {
    return vec3(wrap_scalar(value.x, period.x),
        wrap_scalar(value.y, period.y), wrap_scalar(value.z, period.z));
}
float periodic_delta(float delta, float period) {
    float wrapped = mod(delta + 0.5 * period, period);
    if (wrapped < 0.0) wrapped += period;
    return wrapped - 0.5 * period;
}
vec3 periodic_delta_vec(vec3 delta, vec3 period) {
    return vec3(periodic_delta(delta.x, period.x),
        periodic_delta(delta.y, period.y), periodic_delta(delta.z, period.z));
}

vec3 hash_cell_size(vec3 span, uint h) {
    vec3 result = span / float(h);
    float published_x = hash_cfg[0].w;
    if (finite_float(published_x) && published_x > 0.0) {
        float tolerance = max(result.x * 0.001, 1.0e-6);
        if (abs(published_x - result.x) <= tolerance) result.x = published_x;
    }
    return result;
}
float point_aabb_distance2(vec3 p, vec3 lo, vec3 hi) {
    vec3 d = max(max(lo - p, p - hi), vec3(0.0));
    return dot(d, d);
}

void clear_site_mass(uint gid, uint site_count) {
    if (gid >= site_count) return;
    mass_fix[gid] = uvec4(0u);
    site_mass[gid] = 0.0;
}
void convert_site_mass(uint gid, uint site_count) {
    if (gid >= site_count) return;
    uvec4 s = mass_fix[gid];
    float fixed_sum = float(s.x) + float(s.y) * 256.0
            + float(s.z) * 65536.0 + float(s.w) * 16777216.0;
    site_mass[gid] = fixed_sum / fixed_scale();
}
void add_fixed_digits(uint site, uint value) {
    if (value == 0u) return;
    atomicAdd(mass_fix[site].x, value & 255u);
    atomicAdd(mass_fix[site].y, (value >> 8u) & 255u);
    atomicAdd(mass_fix[site].z, (value >> 16u) & 255u);
    atomicAdd(mass_fix[site].w, (value >> 24u) & 255u);
}

void scan_hash_cell(uint cell, uint site_count, vec3 tile, vec3 span,
        bool open_world, inout uint best_site, inout float best_d2) {
    uint raw_start = hash_start[cell];
    uint raw_end = hash_start[cell + 1u];
    if (raw_end < raw_start) return;
    uint list_capacity = uint(hash_sites.length());
    uint start = min(raw_start, list_capacity);
    uint end = min(raw_end, list_capacity);
    for (uint k = start; k < end; ++k) {
        uint candidate = hash_sites[k];
        if (candidate >= site_count) continue;
        vec3 site_tile = sites[candidate].xyz;
        if (!finite_vec3(site_tile)) continue;
        vec3 delta = open_world ? site_tile - tile
                : periodic_delta_vec(site_tile - tile, span);
        float d2 = dot(delta, delta);
        if (!(d2 >= 0.0) || !finite_float(d2)) continue;
        if (d2 < best_d2 || (d2 == best_d2 && candidate < best_site)) {
            best_d2 = d2;
            best_site = candidate;
        }
    }
}

// Complete open-domain hash query. After each Chebyshev shell, the six slab
// AABBs cover every unscanned cell. A strict best<bound test is required so a
// farther shell can still supply the lower original-ID member of a tie.
uint nearest_site(vec3 particle_world, uint site_count, vec3 ext, vec3 window,
        uint h, bool open_world) {
    vec3 span = 2.0 * ext;
    vec3 local_tile = particle_world - window + ext;
    if (open_world && (any(lessThan(local_tile, vec3(0.0)))
            || any(greaterThanEqual(local_tile, span)))) return UINT_MAX_VALUE;
    vec3 tile = open_world ? local_tile : wrap_tile(local_tile, span);
    vec3 cell_size = hash_cell_size(span, h);
    if (!finite_vec3(cell_size) || any(lessThanEqual(cell_size, vec3(0.0)))) {
        return UINT_MAX_VALUE;
    }
    int hi = int(h);
    ivec3 base = clamp(ivec3(floor(tile / cell_size)), ivec3(0), ivec3(hi - 1));
    uint best_site = UINT_MAX_VALUE;
    float best_d2 = 1.0e30;
    for (int ring = 0; ring < hi; ++ring) {
        ivec3 lo_cell = max(base - ivec3(ring), ivec3(0));
        ivec3 hi_cell = min(base + ivec3(ring), ivec3(hi - 1));
        if (ring == 0) {
            uint cell = uint(base.x) + h * (uint(base.y) + h * uint(base.z));
            scan_hash_cell(cell, site_count, tile, span, open_world, best_site, best_d2);
        } else {
            ivec3 prev_lo = max(base - ivec3(ring - 1), ivec3(0));
            ivec3 prev_hi = min(base + ivec3(ring - 1), ivec3(hi - 1));
            bool zlo_new = lo_cell.z < prev_lo.z;
            bool zhi_new = hi_cell.z > prev_hi.z;
            bool ylo_new = lo_cell.y < prev_lo.y;
            bool yhi_new = hi_cell.y > prev_hi.y;
            bool xlo_new = lo_cell.x < prev_lo.x;
            bool xhi_new = hi_cell.x > prev_hi.x;
            if (zlo_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int y = lo_cell.y; y <= hi_cell.y; ++y)
                        scan_hash_cell(uint(x) + h * (uint(y) + h * uint(lo_cell.z)),
                                site_count, tile, span, open_world, best_site, best_d2);
            if (zhi_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int y = lo_cell.y; y <= hi_cell.y; ++y)
                        scan_hash_cell(uint(x) + h * (uint(y) + h * uint(hi_cell.z)),
                                site_count, tile, span, open_world, best_site, best_d2);
            int zlo_inner = lo_cell.z + (zlo_new ? 1 : 0);
            int zhi_inner = hi_cell.z - (zhi_new ? 1 : 0);
            if (ylo_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(x) + h * (uint(lo_cell.y) + h * uint(z)),
                                site_count, tile, span, open_world, best_site, best_d2);
            if (yhi_new)
                for (int x = lo_cell.x; x <= hi_cell.x; ++x)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(x) + h * (uint(hi_cell.y) + h * uint(z)),
                                site_count, tile, span, open_world, best_site, best_d2);
            int ylo_inner = lo_cell.y + (ylo_new ? 1 : 0);
            int yhi_inner = hi_cell.y - (yhi_new ? 1 : 0);
            if (xlo_new)
                for (int y = ylo_inner; y <= yhi_inner; ++y)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(lo_cell.x) + h * (uint(y) + h * uint(z)),
                                site_count, tile, span, open_world, best_site, best_d2);
            if (xhi_new)
                for (int y = ylo_inner; y <= yhi_inner; ++y)
                    for (int z = zlo_inner; z <= zhi_inner; ++z)
                        scan_hash_cell(uint(hi_cell.x) + h * (uint(y) + h * uint(z)),
                                site_count, tile, span, open_world, best_site, best_d2);
        }
        if (!open_world || best_site == UINT_MAX_VALUE) continue;
        float bound2 = 1.0e30;
        if (lo_cell.x > 0)
            bound2 = min(bound2, point_aabb_distance2(local_tile, vec3(0.0),
                vec3(float(lo_cell.x) * cell_size.x, span.y, span.z)));
        if (hi_cell.x < hi - 1)
            bound2 = min(bound2, point_aabb_distance2(local_tile,
                vec3(float(hi_cell.x + 1) * cell_size.x, 0.0, 0.0), span));
        if (lo_cell.y > 0)
            bound2 = min(bound2, point_aabb_distance2(local_tile, vec3(0.0),
                vec3(span.x, float(lo_cell.y) * cell_size.y, span.z)));
        if (hi_cell.y < hi - 1)
            bound2 = min(bound2, point_aabb_distance2(local_tile,
                vec3(0.0, float(hi_cell.y + 1) * cell_size.y, 0.0), span));
        if (lo_cell.z > 0)
            bound2 = min(bound2, point_aabb_distance2(local_tile, vec3(0.0),
                vec3(span.x, span.y, float(lo_cell.z) * cell_size.z)));
        if (hi_cell.z < hi - 1)
            bound2 = min(bound2, point_aabb_distance2(local_tile,
                vec3(0.0, 0.0, float(hi_cell.z + 1) * cell_size.z), span));
        if (best_d2 < bound2) break;
    }
    return best_site;
}

bool cache_read(uint gid, vec3 particle_position, uint site_count,
        out uint site_id) {
    uint epoch = query_cache[0];
    if (epoch == 0u) return false;
    uint base = 1u + gid * 5u;
    if (query_cache[base] != floatBitsToUint(particle_position.x)
            || query_cache[base + 1u] != floatBitsToUint(particle_position.y)
            || query_cache[base + 2u] != floatBitsToUint(particle_position.z)
            || query_cache[base + 4u] != epoch) return false;
    site_id = query_cache[base + 3u];
    return site_id == UINT_MAX_VALUE || site_id < site_count;
}
void cache_write(uint gid, vec3 particle_position, uint site_id) {
    uint base = 1u + gid * 5u;
    query_cache[base] = floatBitsToUint(particle_position.x);
    query_cache[base + 1u] = floatBitsToUint(particle_position.y);
    query_cache[base + 2u] = floatBitsToUint(particle_position.z);
    query_cache[base + 3u] = site_id;
    query_cache[base + 4u] = query_cache[0];
}

void deposit_particle(uint gid, uint particle_count, uint site_count) {
    if (gid >= particle_count || site_count == 0u) return;
    vec4 particle = pos[gid];
    if (!(particle.w > 0.0) || !finite_float(particle.w)) return;
    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 window = vec3(pc.window_x, pc.window_y, pc.window_z);
    if (!finite_vec3(ext) || !finite_vec3(window) || !finite_vec3(particle.xyz)
            || any(lessThanEqual(ext, vec3(0.0)))) return;
    uint h = pc_count(pc.hash_H);
    if (h == 0u || h > 2147483647u) return;
    uint h2 = h * h;
    if (h2 / h != h) return;
    uint cell_count = h2 * h;
    if (cell_count / h2 != h || cell_count >= UINT_MAX_VALUE) return;
    bool open_world = pc.pad >= 0.5;
    uint best_site = UINT_MAX_VALUE;
    bool cached = open_world && cache_read(gid, particle.xyz, site_count, best_site);
    if (!cached) {
        best_site = nearest_site(particle.xyz, site_count, ext, window, h, open_world);
        if (open_world) cache_write(gid, particle.xyz, best_site);
    }
    if (best_site == UINT_MAX_VALUE) return;
    float contribution = round(particle.w * fixed_scale());
    if (!(contribution > 0.0)) return;
    uint fixed_mass = uint(min(contribution, MAX_FIXED_FLOAT));
    add_fixed_digits(best_site, fixed_mass);
}

void main() {
    uint gid = gl_GlobalInvocationID.x;
    uint mode_value = pc_count(pc.mode);
    uint particle_count = pc_count(pc.particle_N);
    uint site_count = pc_count(pc.n_sites);
    if (mode_value == 0u) clear_site_mass(gid, site_count);
    else if (mode_value == 1u) deposit_particle(gid, particle_count, site_count);
    else if (mode_value == 2u) convert_site_mass(gid, site_count);
    else if (mode_value == 3u && gid == 0u)
        query_cache[0] += 1u;
}
