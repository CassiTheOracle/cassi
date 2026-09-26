#[compute]
#version 450

// Deterministic particle -> Eulerian material initialization and recurring
// mass-weighted particle-acceleration publication.  Extensive quantities use
// a locked carry-safe base-2^32 accumulator; no float atomics are required.
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Pos { vec4 pos[]; };
layout(set = 0, binding = 1, std430) readonly buffer Vel { vec4 vel[]; };
layout(set = 0, binding = 2, std430) readonly buffer Acc { vec4 acc[]; };
layout(set = 0, binding = 3, std430) coherent buffer FixedDigits { uvec4 fixed_digits[]; };
layout(set = 0, binding = 4, std430) buffer Material0A { vec4 material0_a[]; };
layout(set = 0, binding = 5, std430) buffer Material1A { vec4 material1_a[]; };
layout(set = 0, binding = 6, std430) buffer Population0A { vec4 population0_a[]; };
layout(set = 0, binding = 7, std430) buffer Population1A { vec4 population1_a[]; };
layout(set = 0, binding = 8, std430) buffer Material0B { vec4 material0_b[]; };
layout(set = 0, binding = 9, std430) buffer Material1B { vec4 material1_b[]; };
layout(set = 0, binding = 10, std430) buffer Population0B { vec4 population0_b[]; };
layout(set = 0, binding = 11, std430) buffer Population1B { vec4 population1_b[]; };
layout(set = 0, binding = 12, std430) buffer Gravity { vec4 gravity_cell[]; };
layout(set = 0, binding = 13, std430) buffer Ledger0 { vec4 ledger0[]; };
layout(set = 0, binding = 14, std430) buffer Ledger1 { vec4 ledger1[]; };
layout(set = 0, binding = 15, std430) buffer Ledger2 { vec4 ledger2[]; };
layout(set = 0, binding = 16, std430) coherent buffer Status { uvec4 status[]; };
// level = (excitation energy J, degeneracy, ionization threshold frequency Hz, sigma0 m^2)
layout(set = 0, binding = 17, std430) readonly buffer Levels { vec4 level_data[]; };

layout(push_constant, std430) uniform PC {
    float mode;
    float particle_count;
    float nx;
    float ny;
    float nz;
    float extent_x;
    float extent_y;
    float extent_z;
    float center_x;
    float center_y;
    float center_z;
    float total_particle_mass;
    float fixed_scale;
    float gamma_gas;
    float initial_temperature_K;
    float length_m_per_sim;
    float time_s_per_sim;
    float mass_kg_per_sim;
    float energy_J_per_sim;
    float density_kg_m3_per_sim;
    float energy_density_J_m3_per_sim;
    float velocity_m_s_per_sim;
    float dt_sim;
    float particle_offset;
} pc;

const float K_B = 1.380649e-23;
const float H_PLANCK = 6.62607015e-34;
const float M_E = 9.1093837139e-31;
const float M_H = 1.6735575e-27;
const float MAX_FIXED_FLOAT = 4294967040.0;
const float UINT32_RADIX = 4294967296.0;
const uint STATUS_NONFINITE_INPUT = 1u;
const uint STATUS_OUT_OF_DOMAIN = 2u;
const uint STATUS_FIXED_OVERFLOW = 4u;
const uint STATUS_INVALID_CELL = 8u;
const uint STATUS_STEP_REJECTED = 131072u;

bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
bool finite_vec3(vec3 value) { return !(any(isnan(value)) || any(isinf(value))); }
uint rounded_count(float value) {
    return (!finite_float(value) || value <= 0.0) ? 0u : uint(value + 0.5);
}
uvec3 dimensions() {
    return uvec3(rounded_count(pc.nx), rounded_count(pc.ny), rounded_count(pc.nz));
}
uint cell_count() {
    uvec3 dims = dimensions();
    return dims.x * dims.y * dims.z;
}
uint linear_cell(uvec3 c, uvec3 dims) {
    return c.x + dims.x * (c.y + dims.y * c.z);
}
float decode_fixed(uint channel, uint cell) {
    uvec4 digits = fixed_digits[cell * 7u + channel];
    float sum = float(digits.x) + UINT32_RADIX * float(digits.y);
    return sum / max(pc.fixed_scale, 1.0);
}
void add_fixed(uint channel, uint cell, float value) {
    if (!(value > 0.0) || !finite_float(value)) return;
    float scaled = round(value * pc.fixed_scale);
    if (!finite_float(scaled) || scaled < 0.0) {
        atomicOr(status[0].x, STATUS_FIXED_OVERFLOW);
        return;
    }
    if (scaled == 0.0) return;
    if (scaled >= MAX_FIXED_FLOAT) {
        atomicOr(status[0].x, STATUS_FIXED_OVERFLOW);
        return;
    }
    uint encoded_low = uint(scaled);
    uint base = cell * 7u + channel;
    // Accumulate the low limb with a CAS loop and carry into the high limb
    // after the successful low-limb reservation. This is lock-free: one
    // contending invocation always makes progress, so a dense particle cloud
    // cannot wedge a whole workgroup behind a spin lock.
    uint old_low = fixed_digits[base].x;
    while (true) {
        uint next_low = old_low + encoded_low;
        uint observed = atomicCompSwap(fixed_digits[base].x, old_low, next_low);
        if (observed == old_low) {
            if (next_low < old_low) {
                uint old_high = atomicAdd(fixed_digits[base].y, 1u);
                if (old_high == 0xffffffffu) {
                    atomicOr(status[0].x, STATUS_FIXED_OVERFLOW);
                    atomicMax(fixed_digits[base].y, 0xffffffffu);
                    atomicMax(fixed_digits[base].x, 0xffffffffu);
                }
            }
            break;
        }
        old_low = observed;
    }
}
void clear_initial(uint gid) {
    uint cells = cell_count();
    if (gid < cells * 7u) fixed_digits[gid] = uvec4(0u);
    if (gid < cells) {
        material0_a[gid] = vec4(0.0);
        material1_a[gid] = vec4(0.0);
        population0_a[gid] = vec4(0.0);
        population1_a[gid] = vec4(0.0);
        material0_b[gid] = vec4(0.0);
        material1_b[gid] = vec4(0.0);
        population0_b[gid] = vec4(0.0);
        population1_b[gid] = vec4(0.0);
        gravity_cell[gid] = vec4(0.0);
        ledger0[gid] = vec4(0.0);
        ledger1[gid] = vec4(0.0);
        ledger2[gid] = vec4(0.0);
    }
    if (gid < uint(status.length())) status[gid] = uvec4(0u);
}

void deposit_initial(uint local_gid) {
    uint particles = rounded_count(pc.particle_count);
    uint gid = rounded_count(pc.particle_offset) + local_gid;
    if (gid >= particles) return;
    vec4 p4 = pos[gid];
    vec3 velocity = vel[gid].xyz;
    float mass = p4.w;
    if (!(mass > 0.0)) return;
    if (!finite_vec3(p4.xyz) || !finite_vec3(velocity) || !finite_float(mass)) {
        atomicOr(status[0].x, STATUS_NONFINITE_INPUT);
        atomicAdd(status[0].z, 1u);
        return;
    }
    uvec3 dims = dimensions();
    vec3 extent = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 center = vec3(pc.center_x, pc.center_y, pc.center_z);
    vec3 lower = center - extent;
    vec3 span = 2.0 * extent;
    vec3 normalized = (p4.xyz - lower) / span;
    if (any(lessThan(normalized, vec3(0.0))) || any(greaterThan(normalized, vec3(1.0)))) {
        atomicOr(status[0].x, STATUS_OUT_OF_DOMAIN);
        atomicAdd(status[0].y, 1u);
        return;
    }
    vec3 coordinate = normalized * vec3(dims) - vec3(0.5);
    ivec3 base = ivec3(floor(coordinate));
    vec3 fraction = coordinate - vec3(base);
    // CANONICAL trilinear gather/scatter contract for physical matter: the two
    // passes in deposit_initial(), the two in deposit_gravity() here, and the
    // density-weighted gather in cassi_physical_matter_tracer.glsl.  The shared
    // rule is the 8-corner mix(vec3(1.0) - fraction, fraction, side) weights,
    // the two-pass valid_weight_sum normalisation that keeps boundary
    // particles mass-conserving, and the (mass / total_particle_mass) scale.
    // The copies differ only in payload and in whether the normalised mass is
    // hoisted; any change to the weight or normalisation rule must land at
    // every one of those five sites.
    float valid_weight_sum = 0.0;
    for (int dz = 0; dz <= 1; ++dz)
        for (int dy = 0; dy <= 1; ++dy)
            for (int dx = 0; dx <= 1; ++dx) {
                ivec3 candidate = base + ivec3(dx, dy, dz);
                if (any(lessThan(candidate, ivec3(0))) || any(greaterThanEqual(candidate, ivec3(dims)))) continue;
                vec3 side = vec3(dx, dy, dz);
                vec3 weights = mix(vec3(1.0) - fraction, fraction, side);
                valid_weight_sum += weights.x * weights.y * weights.z;
            }
    if (!(valid_weight_sum > 0.0) || !finite_float(valid_weight_sum)) {
        atomicOr(status[0].x, STATUS_INVALID_CELL);
        return;
    }
    for (int dz = 0; dz <= 1; ++dz)
        for (int dy = 0; dy <= 1; ++dy)
            for (int dx = 0; dx <= 1; ++dx) {
                ivec3 candidate = base + ivec3(dx, dy, dz);
                if (any(lessThan(candidate, ivec3(0))) || any(greaterThanEqual(candidate, ivec3(dims)))) continue;
                vec3 side = vec3(dx, dy, dz);
                vec3 weights = mix(vec3(1.0) - fraction, fraction, side);
                float weighted_mass = (mass / max(pc.total_particle_mass, 1.0e-30))
                    * weights.x * weights.y * weights.z / valid_weight_sum;
                uint cell = linear_cell(uvec3(candidate), dims);
                add_fixed(0u, cell, weighted_mass);
                add_fixed(1u, cell, weighted_mass * max(velocity.x, 0.0));
                add_fixed(2u, cell, weighted_mass * max(-velocity.x, 0.0));
                add_fixed(3u, cell, weighted_mass * max(velocity.y, 0.0));
                add_fixed(4u, cell, weighted_mass * max(-velocity.y, 0.0));
                add_fixed(5u, cell, weighted_mass * max(velocity.z, 0.0));
                add_fixed(6u, cell, weighted_mass * max(-velocity.z, 0.0));
            }
}

float saha_fraction(float temperature, float number_density) {
    float log_s = log(2.0) + 1.5 * log(2.0 * 3.141592653589793 * M_E * K_B * temperature
        / (H_PLANCK * H_PLANCK)) - level_data[6].x / (K_B * temperature)
        - log(max(number_density, 1.0e-30));
    if (log_s > 40.0) return 1.0 - exp(-log_s);
    if (log_s < -40.0) return exp(0.5 * log_s);
    float s = exp(log_s);
    return 2.0 * s / (sqrt(s * s + 4.0 * s) + s);
}

void finalize_initial(uint gid) {
    uint cells = cell_count();
    if (gid >= cells) return;
    uvec3 dims = dimensions();
    vec3 extent = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 cell_size = 2.0 * extent / vec3(dims);
    float volume_sim3 = cell_size.x * cell_size.y * cell_size.z;
    float normalization = max(volume_sim3, 1.0e-30);
    float rho = decode_fixed(0u, gid) / normalization;
    vec3 momentum = vec3(
        decode_fixed(1u, gid) - decode_fixed(2u, gid),
        decode_fixed(3u, gid) - decode_fixed(4u, gid),
        decode_fixed(5u, gid) - decode_fixed(6u, gid)) / normalization;
    if (!(rho > 0.0)) return;
    vec3 velocity = momentum / rho;
    float temperature = max(pc.initial_temperature_K, 1.0);
    float number_density = rho * pc.density_kg_m3_per_sim / M_H;
    float ion_fraction = clamp(saha_fraction(temperature, number_density), 0.0, 1.0);
    float neutral_fraction = 1.0 - ion_fraction;
    float partition_function = 0.0;
    float boltzmann[6];
    for (int level = 0; level < 6; ++level) {
        float excitation = level_data[level].x;
        float weight = level_data[level].y * exp(-excitation / (K_B * temperature));
        boltzmann[level] = max(weight, 0.0);
        partition_function += boltzmann[level];
    }
    partition_function = max(partition_function, 1.0e-30);
    float populations[7];
    for (int level = 0; level < 6; ++level)
        populations[level] = rho * neutral_fraction * boltzmann[level] / partition_function;
    populations[6] = rho * ion_fraction;
    float velocity_unit2 = pc.velocity_m_s_per_sim * pc.velocity_m_s_per_sim;
    // Canonical definition: chemical_energy() in
    // cassi_physical_matter_atomic.glsl (cell form) and
    // cassi_physical_matter_hydro.glsl (State form).  This site folds
    // level_data[level].x / (M_H * velocity_unit2) into a shared factor, which
    // is mathematically the same sum but not ulp-identical to the canonical
    // per-term division; keep all three in lockstep if the level convention or
    // velocity unit changes.
    float chemical = 0.0;
    for (int level = 0; level < 6; ++level)
        chemical += populations[level] * level_data[level].x / (M_H * velocity_unit2);
    chemical += populations[6] * level_data[6].x / (M_H * velocity_unit2);
    float thermal_specific = 1.5 * K_B * temperature * (1.0 + ion_fraction)
        / (M_H * velocity_unit2);
    float thermal = rho * thermal_specific;
    float kinetic = 0.5 * dot(momentum, momentum) / rho;
    float total_energy = kinetic + chemical + thermal;
    float pressure = (pc.gamma_gas - 1.0) * thermal;
    vec4 q0 = vec4(rho, momentum);
    vec4 q1 = vec4(total_energy, temperature, pressure, 0.0);
    vec4 p0 = vec4(populations[0], populations[1], populations[2], populations[3]);
    vec4 p1 = vec4(populations[4], populations[5], populations[6], 0.0);
    material0_a[gid] = q0;
    material1_a[gid] = q1;
    population0_a[gid] = p0;
    population1_a[gid] = p1;
    material0_b[gid] = q0;
    material1_b[gid] = q1;
    population0_b[gid] = p0;
    population1_b[gid] = p1;
    atomicAdd(status[0].w, 1u);
}

void clear_gravity(uint gid) {
    uint cells = cell_count();
    if (gid < cells * 7u) fixed_digits[gid] = uvec4(0u);
    if (gid < cells) gravity_cell[gid] = vec4(0.0);
}

void deposit_gravity(uint local_gid) {
    uint particles = rounded_count(pc.particle_count);
    uint gid = rounded_count(pc.particle_offset) + local_gid;
    if (gid >= particles) return;
    vec4 p4 = pos[gid];
    vec3 acceleration = acc[gid].xyz;
    float mass = p4.w;
    if (!(mass > 0.0)) return;
    if (!finite_vec3(p4.xyz) || !finite_vec3(acceleration) || !finite_float(mass)) {
        atomicOr(status[0].x, STATUS_NONFINITE_INPUT);
        return;
    }
    uvec3 dims = dimensions();
    vec3 extent = vec3(pc.extent_x, pc.extent_y, pc.extent_z);
    vec3 center = vec3(pc.center_x, pc.center_y, pc.center_z);
    vec3 lower = center - extent;
    vec3 span = 2.0 * extent;
    vec3 normalized = (p4.xyz - lower) / span;
    if (any(lessThan(normalized, vec3(0.0))) || any(greaterThan(normalized, vec3(1.0)))) {
        atomicOr(status[0].x, STATUS_OUT_OF_DOMAIN);
        atomicAdd(status[0].y, 1u);
        return;
    }
    vec3 coordinate = normalized * vec3(dims) - vec3(0.5);
    ivec3 base = ivec3(floor(coordinate));
    vec3 fraction = coordinate - vec3(base);
    float valid_weight_sum = 0.0;
    // Trilinear scatter, second copy (see the canonical contract comment above).
    for (int dz = 0; dz <= 1; ++dz)
        for (int dy = 0; dy <= 1; ++dy)
            for (int dx = 0; dx <= 1; ++dx) {
                ivec3 candidate = base + ivec3(dx, dy, dz);
                if (any(lessThan(candidate, ivec3(0))) || any(greaterThanEqual(candidate, ivec3(dims)))) continue;
                vec3 side = vec3(dx, dy, dz);
                vec3 weights = mix(vec3(1.0) - fraction, fraction, side);
                valid_weight_sum += weights.x * weights.y * weights.z;
            }
    if (!(valid_weight_sum > 0.0) || !finite_float(valid_weight_sum)) {
        atomicOr(status[0].x, STATUS_INVALID_CELL);
        return;
    }
    float normalized_mass = mass / max(pc.total_particle_mass, 1.0e-30);
    // Gravity scatter: same canonical trilinear contract as above; the
    // normalised mass is hoisted, which the identical left-to-right multiply
    // order makes bit-identical to the inline form.
    for (int dz = 0; dz <= 1; ++dz)
        for (int dy = 0; dy <= 1; ++dy)
            for (int dx = 0; dx <= 1; ++dx) {
                ivec3 candidate = base + ivec3(dx, dy, dz);
                if (any(lessThan(candidate, ivec3(0))) || any(greaterThanEqual(candidate, ivec3(dims)))) continue;
                vec3 side = vec3(dx, dy, dz);
                vec3 weights = mix(vec3(1.0) - fraction, fraction, side);
                float weighted_mass = normalized_mass * weights.x * weights.y * weights.z
                    / valid_weight_sum;
                uint cell = linear_cell(uvec3(candidate), dims);
                add_fixed(0u, cell, weighted_mass);
                add_fixed(1u, cell, weighted_mass * max(acceleration.x, 0.0));
                add_fixed(2u, cell, weighted_mass * max(-acceleration.x, 0.0));
                add_fixed(3u, cell, weighted_mass * max(acceleration.y, 0.0));
                add_fixed(4u, cell, weighted_mass * max(-acceleration.y, 0.0));
                add_fixed(5u, cell, weighted_mass * max(acceleration.z, 0.0));
                add_fixed(6u, cell, weighted_mass * max(-acceleration.z, 0.0));
            }
}

void finalize_gravity(uint gid) {
    uint cells = cell_count();
    if (gid >= cells) return;
    float mass = decode_fixed(0u, gid);
    if (!(mass > 0.0)) {
        gravity_cell[gid] = vec4(0.0);
        return;
    }
    vec3 weighted = vec3(
        decode_fixed(1u, gid) - decode_fixed(2u, gid),
        decode_fixed(3u, gid) - decode_fixed(4u, gid),
        decode_fixed(5u, gid) - decode_fixed(6u, gid));
    vec3 acceleration = weighted / mass;
    if (!finite_vec3(acceleration)) {
        atomicOr(status[0].x, STATUS_INVALID_CELL);
        acceleration = vec3(0.0);
    }
    gravity_cell[gid] = vec4(acceleration, mass);
}

void main() {
    uint gid = gl_GlobalInvocationID.x;
    if ((status[0].x & STATUS_STEP_REJECTED) != 0u) return;
    uint mode = rounded_count(pc.mode);
    if (mode == 0u) clear_initial(gid);
    else if (mode == 1u) deposit_initial(gid);
    else if (mode == 2u) finalize_initial(gid);
    else if (mode == 3u) clear_gravity(gid);
    else if (mode == 4u) deposit_gravity(gid);
    else if (mode == 5u) finalize_gravity(gid);
}
