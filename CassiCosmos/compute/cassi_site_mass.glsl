#[compute]
#version 450

// Site-native particle mass deposition.
//
// Sites are stored in tile coordinates [0, 2*extent) and particles are in
// world coordinates. In open-world mode a particle is translated by the
// current window center and rejected when it is outside the live site window;
// it is never wrapped onto the opposite seam. The legacy periodic branch is
// retained only for explicit compatibility callers.
// HashSites contains site indices (not shortlist slots); malformed starts and
// candidate indices are ignored.
//
// MassFix is a deterministic carry-safe fixed-point accumulator. Each site
// stores four base-2^8 digit sums (uvec4), matching the legacy mass-deposit
// accumulator. The PC scale is the number of integer units per mass unit;
// default FIXED_SCALE = 2^24. Integer atomic addition is order-independent;
// mode 2 performs the only float conversion, yielding one float mass/site.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Pos {
    vec4 pos[];
};

layout(set = 0, binding = 1, std430) readonly buffer Sites {
    vec4 sites[];
};

layout(set = 0, binding = 2, std430) readonly buffer HashStart {
    uint hash_start[];
};

layout(set = 0, binding = 3, std430) readonly buffer HashSites {
    uint hash_sites[];
};

layout(set = 0, binding = 4, std430) readonly buffer HashCfg {
    vec4 hash_cfg[];
};

layout(set = 0, binding = 5, std430) coherent buffer MassFix {
    uvec4 mass_fix[];
};

layout(set = 0, binding = 6, std430) coherent buffer SiteMass {
    float site_mass[];
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

const float FIXED_SCALE = 16777216.0;    // 2^24, base-2^8 x 4 digits
const float MAX_FIXED_FLOAT = 4294967040.0; // UINT_MAX - 255, exactly representable
const uint UINT_MAX_VALUE = 0xffffffffu;

bool finite_float(float value) {
    return !(isnan(value) || isinf(value));
}

bool finite_vec3(vec3 value) {
    return !(any(isnan(value)) || any(isinf(value)));
}

uint pc_count(float value) {
    if (!finite_float(value) || value <= 0.0) {
        return 0u;
    }
    return uint(value + 0.5);
}

float fixed_scale() {
    return (finite_float(pc.scale) && pc.scale > 0.0) ? pc.scale : FIXED_SCALE;
}

float wrap_scalar(float value, float period) {
    float wrapped = mod(value, period);
    if (wrapped < 0.0) {
        wrapped += period;
    }
    // Protect the cell lookup from a roundoff value exactly at the upper seam.
    if (wrapped >= period) {
        wrapped = 0.0;
    }
    return wrapped;
}

vec3 wrap_tile(vec3 value, vec3 period) {
    return vec3(
        wrap_scalar(value.x, period.x),
        wrap_scalar(value.y, period.y),
        wrap_scalar(value.z, period.z)
    );
}

float periodic_delta(float delta, float period) {
    float wrapped = mod(delta + 0.5 * period, period);
    if (wrapped < 0.0) {
        wrapped += period;
    }
    return wrapped - 0.5 * period;
}

vec3 periodic_delta_vec(vec3 delta, vec3 period) {
    return vec3(
        periodic_delta(delta.x, period.x),
        periodic_delta(delta.y, period.y),
        periodic_delta(delta.z, period.z)
    );
}

int wrap_cell(int value, int h) {
    int wrapped = value % h;
    return wrapped < 0 ? wrapped + h : wrapped;
}

int neighbor_cell(int value, int h, bool open_world) {
    return open_world ? clamp(value, 0, h - 1) : wrap_cell(value, h);
}

// The published cfg keeps the historical (origin.xyz, x-cell-width) record.
// The tile origin is fixed at zero by this ABI; use a finite, consistent x
// width as a validation/readback of the published hash while deriving y/z
// widths from the per-axis PC extents.
vec3 hash_cell_size(vec3 span, uint h) {
    vec3 result = span / float(h);
    vec4 cfg = hash_cfg[0];
    float published_x = cfg.w;
    if (finite_float(published_x) && published_x > 0.0) {
        float tolerance = max(result.x * 0.001, 1.0e-6);
        if (abs(published_x - result.x) <= tolerance) {
            result.x = published_x;
        }
    }
    return result;
}

void clear_site_mass(uint gid, uint site_count) {
    if (gid >= site_count) {
        return;
    }
    mass_fix[gid] = uvec4(0u);
    site_mass[gid] = 0.0;
}

void convert_site_mass(uint gid, uint site_count) {
    if (gid >= site_count) {
        return;
    }
    uvec4 s = mass_fix[gid];
    float fixed_sum = float(s.x)
                    + float(s.y) * 256.0
                    + float(s.z) * 65536.0
                    + float(s.w) * 16777216.0;
    site_mass[gid] = fixed_sum / fixed_scale();
}
void add_fixed_digits(uint site, uint value) {
    if (value == 0u) {
        return;
    }
    atomicAdd(mass_fix[site].x, value & 255u);
    atomicAdd(mass_fix[site].y, (value >> 8u) & 255u);
    atomicAdd(mass_fix[site].z, (value >> 16u) & 255u);
    atomicAdd(mass_fix[site].w, (value >> 24u) & 255u);
}

void deposit_particle(uint gid, uint particle_count, uint site_count) {
    if (gid >= particle_count || site_count == 0u) {
        return;
    }

    vec4 particle = pos[gid];
    float mass = particle.w;
    // The strict-positive test also rejects NaN.  Explicit finite checks keep
    // invalid values out of the coordinate map and uint conversion.
    if (!(mass > 0.0) || !finite_float(mass)) {
        return;
    }

    vec3 ext = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 window = vec3(pc.window_x, pc.window_y, pc.window_z);
    if (!finite_vec3(ext) || !finite_vec3(window) || !finite_vec3(particle.xyz)) {
        return;
    }
    if (any(lessThanEqual(ext, vec3(0.0)))) {
        return;
    }

    uint h = pc_count(pc.hash_H);
    // The cell-neighborhood loop uses signed offsets.  Reject values that do
    // not fit in the signed integer used for periodic cell wrapping.
    if (h == 0u || h > 2147483647u) {
        return;
    }
    uint h2 = h * h;
    if (h2 / h != h) {
        return;
    }
    uint cell_count = h2 * h;
    if (cell_count / h2 != h || cell_count >= UINT_MAX_VALUE) {
        return;
    }

    vec3 span = 2.0 * ext;
    bool open_world = pc.pad >= 0.5;
    vec3 local_tile = particle.xyz - window + ext;
    if (open_world) {
        if (any(lessThan(local_tile, vec3(0.0)))
                || any(greaterThanEqual(local_tile, span))) {
            return;
        }
    }
    vec3 tile = open_world ? local_tile : wrap_tile(local_tile, span);
    vec3 cell_size = hash_cell_size(span, h);
    if (!finite_vec3(cell_size) || any(lessThanEqual(cell_size, vec3(0.0)))) {
        return;
    }

    int hi = int(h);
    ivec3 base = ivec3(floor(tile / cell_size));
    base = clamp(base, ivec3(0), ivec3(hi - 1));

    uint best_site = UINT_MAX_VALUE;
    float best_d2 = 1.0e30;
    for (int oz = -1; oz <= 1; oz++) {
        int cz = neighbor_cell(base.z + oz, hi, open_world);
        for (int oy = -1; oy <= 1; oy++) {
            int cy = neighbor_cell(base.y + oy, hi, open_world);
            for (int ox = -1; ox <= 1; ox++) {
                int cx = neighbor_cell(base.x + ox, hi, open_world);
                uint cell = uint(cx) + h * (uint(cy) + h * uint(cz));

                uint raw_start = hash_start[cell];
                uint raw_end = hash_start[cell + 1u];
                if (raw_end < raw_start) {
                    continue;
                }
                // HashSites is provisioned for at most one entry per site.
                // Clamping turns an oversized/malformed prefix into a safe
                // empty or truncated run without touching memory out of range.
                uint start = min(raw_start, site_count);
                uint end = min(raw_end, site_count);
                if (start >= end) {
                    continue;
                }

                for (uint k = start; k < end; k++) {
                    uint candidate = hash_sites[k];
                    if (candidate >= site_count) {
                        continue;
                    }
                    vec3 site_tile = sites[candidate].xyz;
                    if (!finite_vec3(site_tile)) {
                        continue;
                    }
                    vec3 delta = open_world ? site_tile - tile
                            : periodic_delta_vec(site_tile - tile, span);
                    float d2 = dot(delta, delta);
                    if (!(d2 >= 0.0) || !finite_float(d2)) {
                        continue;
                    }
                    // Candidate-index tie breaking makes coincident sites
                    // deterministic even when their hash order changes.
                    if (d2 < best_d2 || (d2 == best_d2 && candidate < best_site)) {
                        best_d2 = d2;
                        best_site = candidate;
                    }
                }
            }
        }
    }

    if (best_site == UINT_MAX_VALUE) {
        return;
    }

    float contribution = round(mass * fixed_scale());
    if (!(contribution > 0.0)) {
        return;
    }
    contribution = min(contribution, MAX_FIXED_FLOAT);
    uint fixed_mass = uint(contribution);
    add_fixed_digits(best_site, fixed_mass);
}

void main() {
    uint gid = gl_GlobalInvocationID.x;
    uint mode_value = pc_count(pc.mode);
    uint particle_count = pc_count(pc.particle_N);
    uint site_count = pc_count(pc.n_sites);

    if (mode_value == 0u) {
        clear_site_mass(gid, site_count);
    } else if (mode_value == 1u) {
        deposit_particle(gid, particle_count, site_count);
    } else if (mode_value == 2u) {
        convert_site_mass(gid, site_count);
    }
}
