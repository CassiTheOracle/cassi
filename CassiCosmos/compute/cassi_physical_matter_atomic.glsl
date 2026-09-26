#[compute]
#version 450

// Per-cell hydrogen kinetics, emissivity/opacity construction, conservative
// matter-radiation source exchange, moving-frame frequency/angular remap, and
// open-boundary radiation ledgers.  One invocation owns every population and
// angular-frequency value of its cell, avoiding unordered float atomics.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer Material0 { vec4 material0[]; };
layout(set = 0, binding = 1, std430) buffer Material1 { vec4 material1[]; };
layout(set = 0, binding = 2, std430) buffer Population0 { vec4 population0[]; };
layout(set = 0, binding = 3, std430) buffer Population1 { vec4 population1[]; };
layout(set = 0, binding = 4, std430) buffer RadiationActive { float radiation_active[]; };
layout(set = 0, binding = 5, std430) buffer RadiationScratch { float radiation_scratch[]; };
// frequency = (lower Hz, upper Hz, midpoint Hz, width Hz)
layout(set = 0, binding = 6, std430) readonly buffer Frequencies { vec4 frequency_data[]; };
// ordinate = (unit direction xyz, solid-angle weight sr)
layout(set = 0, binding = 7, std430) readonly buffer Ordinates { vec4 ordinate_data[]; };
// line_a = (lower state, upper state, frequency Hz, Einstein A s^-1)
layout(set = 0, binding = 8, std430) readonly buffer LinesA { vec4 line_a[]; };
// line_b = (oscillator strength, nominal group, lower degeneracy, upper degeneracy)
layout(set = 0, binding = 9, std430) readonly buffer LinesB { vec4 line_b[]; };
// level = (excitation energy J, degeneracy, threshold frequency Hz, sigma0 m^2)
layout(set = 0, binding = 10, std430) readonly buffer Levels { vec4 level_data[]; };
// Per log-temperature row: ionization, recombination, then 15 up/down pairs.
layout(set = 0, binding = 11, std430) readonly buffer Rates { float rate_data[]; };
layout(set = 0, binding = 12, std430) buffer Opacity { float opacity_group[]; };
layout(set = 0, binding = 13, std430) buffer Emission { float emission_group[]; };
// ledger0 = (low-frequency escape, high-frequency escape,
//            spatial radiation escape, signed radiation source gain)
layout(set = 0, binding = 14, std430) buffer Ledger0 { vec4 ledger0[]; };
layout(set = 0, binding = 15, std430) coherent buffer Status { uvec4 status[]; };

layout(push_constant, std430) uniform PC {
    float mode;
    float nx;
    float ny;
    float nz;
    float group_count;
    float angle_count;
    float dt_sim;
    float c_reduced_sim;
    float length_m_per_sim;
    float time_s_per_sim;
    float density_kg_m3_per_sim;
    float energy_density_J_m3_per_sim;
    float velocity_m_s_per_sim;
    float gamma_gas;
    float density_floor;
    float pressure_floor;
    float temperature_min_K;
    float temperature_max_K;
    float maximum_v_over_c;
    float source_enabled;
    float extent_x;
    float extent_y;
    float extent_z;
    float two_photon_A_s_inv;
    float pad0;
    float pad1;
    float pad2;
    float pad3;
    float pad4;
    float pad5;
    float pad6;
    float pad7;
} pc;

const float PI = 3.14159265358979323846;
const float FOUR_PI = 12.5663706143591729538;
const float C_LIGHT = 299792458.0;
const float K_B = 1.380649e-23;
const float H_PLANCK = 6.62607015e-34;
const float M_E = 9.1093837139e-31;
const float M_H = 1.6735575e-27;
const float E_CHARGE = 1.602176634e-19;
const float EPSILON_0 = 8.8541878128e-12;
const float SIGMA_T = 6.6524587051e-29;
const float FLOAT32_EPSILON = 1.1920928955078125e-7;
const int LEVELS = 7;
const int LINES = 15;
const int RATE_STRIDE = 32;
const int RATE_SAMPLES = 96;
// The model JSON the engine hash-checks fixes 24 frequency groups and 26
// ordinates (cassi_physical_matter_engine.gd refuses to start unless the loaded
// layout is exactly 24 groups / 26 ordinates, so these compile-time bounds are
// the enforced dispatch shape).  They size the per-cell caches below; the loops
// themselves still run to the push-constant counts and main() fails closed if a
// future layout ever exceeded them.
const int MAX_GROUPS = 24;
const int MAX_ANGLES = 26;
const int ANGULAR_TARGETS = 3;
const int MAX_ANGULAR_SLOTS = 78; // MAX_ANGLES * ANGULAR_TARGETS, kept a single named bound
// exp() argument clamp for the transmission and Planck exponentials.
const float TRANSMISSION_CLAMP = 80.0;
// Exponent above which the free-free Planck term is treated as exhausted.
const float PLANCK_EXPONENT_CLAMP = 80.0;
// |x| beyond this leaves the line profile tail below 1e-15, so the group
// overlap is exactly zero.
const float LINE_TAIL_CUTOFF = 8.0;
// TEMPORARY DIAGNOSTIC (RevertMe): set true to make publish_coefficients() dump
// the group-19 (Lyman-alpha) chain into cells 1..35 of the opacity buffer at
// group 19, one value per cell (cell c holds slot c-1).  False by default, so the
// dump is dead code in every normal run: no value this shader computes depends on
// it.
//
// Scope of an ON run: the dump overwrites real opacities for cells 1..35 at
// group 19, so the gate that consumes these values is PM-G4's `spectral_cases`
// only.  Any other consumer of the whole opacity buffer on the same run
// (PM-G5/PM-G8 maximum_opacity scans, PM-G8's rendered observation, whose
// image/centroid gates read the volume the polluted opacity feeds) is reading the
// diagnostic, not the physics -- those gates are not admissible evidence while
// the switch is on.  Flip it back to false and re-run for a full pass.
const bool LINE_TERM_DIAGNOSTIC = false;
const vec4 FREE_FREE_NODES_0 = vec4(
    -0.9602898564975363, -0.7966664774136267,
    -0.5255324099163290, -0.1834346424956498);
const vec4 FREE_FREE_NODES_1 = vec4(
     0.1834346424956498,  0.5255324099163290,
     0.7966664774136267,  0.9602898564975363);
const vec4 FREE_FREE_WEIGHTS_0 = vec4(
    0.1012285362903763, 0.2223810344533745,
    0.3137066458778873, 0.3626837833783620);
const vec4 FREE_FREE_WEIGHTS_1 = vec4(
    0.3626837833783620, 0.3137066458778873,
    0.2223810344533745, 0.1012285362903763);
const uint STATUS_KINETICS_FAILURE = 128u;
const uint STATUS_SOURCE_NONFINITE = 256u;
const uint STATUS_SOURCE_LIMITED = 512u;
const uint STATUS_MOVING_FRAME_DOMAIN = 1024u;
const uint STATUS_REMAP_NONFINITE = 2048u;
// A step-domain rejection is set by the preflight before any state-writing
// dispatch. Later dispatches in the same command list return after the
// caller-inserted barrier, making the rejection transactional on GPU.
const uint STATUS_STEP_REJECTED = 131072u;
struct Coefficients {
    float emission_rate;
    float absorption;
    float scattering;
};

bool finite_float(float value) { return !(isnan(value) || isinf(value)); }
bool finite_vec3(vec3 value) { return !(any(isnan(value)) || any(isinf(value))); }
bool finite_vec4(vec4 value) { return !(any(isnan(value)) || any(isinf(value))); }
uint rounded(float value) { return (!finite_float(value) || value <= 0.0) ? 0u : uint(value + 0.5); }
uvec3 dims() { return uvec3(rounded(pc.nx), rounded(pc.ny), rounded(pc.nz)); }
uint cells() { uvec3 d = dims(); return d.x * d.y * d.z; }
uint groups() { return rounded(pc.group_count); }
uint angles() { return rounded(pc.angle_count); }
uint rad_index(uint cell, uint group, uint angle) {
    return (cell * groups() + group) * angles() + angle;
}
uint group_index(uint cell, uint group) { return cell * groups() + group; }
ivec3 coordinate(uint cell, uvec3 d) {
    uint plane = d.x * d.y;
    uint z = cell / plane;
    uint remainder = cell - z * plane;
    return ivec3(int(remainder % d.x), int(remainder / d.x), int(z));
}
bool in_domain(ivec3 c, uvec3 d) {
    return all(greaterThanEqual(c, ivec3(0))) && all(lessThan(c, ivec3(d)));
}
uint linear_cell(ivec3 c, uvec3 d) {
    return uint(c.x) + d.x * (uint(c.y) + d.y * uint(c.z));
}
float pop_value(uint cell, int state) {
    vec4 p0 = population0[cell];
    vec4 p1 = population1[cell];
    if (state == 0) return p0.x;
    if (state == 1) return p0.y;
    if (state == 2) return p0.z;
    if (state == 3) return p0.w;
    if (state == 4) return p1.x;
    if (state == 5) return p1.y;
    return p1.z;
}
void store_populations(uint cell, float p[LEVELS]) {
    population0[cell] = vec4(p[0], p[1], p[2], p[3]);
    population1[cell] = vec4(p[4], p[5], p[6], 0.0);
}
float chemical_energy(uint cell) {
    float v2 = pc.velocity_m_s_per_sim * pc.velocity_m_s_per_sim;
    float result = 0.0;
    for (int level = 0; level < 6; ++level)
        result += pop_value(cell, level) * level_data[level].x / (M_H * v2);
    return result + pop_value(cell, 6) * level_data[6].x / (M_H * v2);
}
float resolved_thermal_floor(uint cell) {
    vec4 q0 = material0[cell];
    float kinetic = q0.x > pc.density_floor
        ? 0.5 * dot(q0.yzw, q0.yzw) / q0.x : 0.0;
    float chemical = chemical_energy(cell);
    // Energy, kinetic energy, and chemical binding energy share float32
    // storage. Reserve enough thermal energy to survive the complete allowed
    // hydro record (up to 256 substeps, with several rounded energy
    // operations each) before the next source update, while remaining below
    // the registered 3e-4 coupled-energy tolerance.
    float energy_scale = max(abs(material1[cell].x), abs(kinetic) + abs(chemical));
    return max(pc.pressure_floor / (pc.gamma_gas - 1.0),
        1024.0 * FLOAT32_EPSILON * energy_scale);
}
float temperature_from_state(uint cell) {
    vec4 q0 = material0[cell];
    if (!(q0.x > pc.density_floor)) return pc.temperature_min_K;
    float kinetic = 0.5 * dot(q0.yzw, q0.yzw) / q0.x;
    float thermal = material1[cell].x - kinetic - chemical_energy(cell);
    float ion_fraction = clamp(pop_value(cell, 6) / q0.x, 0.0, 1.0);
    float specific_si = max(thermal, 0.0) / q0.x
        * pc.velocity_m_s_per_sim * pc.velocity_m_s_per_sim;
    return clamp((pc.gamma_gas - 1.0) * M_H * specific_si
        / (K_B * (1.0 + ion_fraction)), pc.temperature_min_K, pc.temperature_max_K);
}
void refresh_thermodynamics(uint cell) {
    vec4 q0 = material0[cell];
    if (!(q0.x > pc.density_floor)) {
        material1[cell].y = 0.0;
        material1[cell].z = 0.0;
        return;
    }
    float kinetic = 0.5 * dot(q0.yzw, q0.yzw) / q0.x;
    float thermal = material1[cell].x - kinetic - chemical_energy(cell);
    float pressure = (pc.gamma_gas - 1.0) * thermal;
    if (!finite_float(thermal) || pressure < pc.pressure_floor) {
        atomicOr(status[0].x, STATUS_KINETICS_FAILURE);
        return;
    }
    material1[cell].y = temperature_from_state(cell);
    material1[cell].z = pressure;
}
// Add a controlled external thermal impulse without changing density,
// momentum, or the atomic populations.  The event is deliberately expressed
// as ΔT through the same EOS inversion used by temperature_from_state(), so
// the observable temperature increase remains tied to the registered units.
void apply_heating_event(uint cell) {
    vec4 q0 = material0[cell];
    if (!(q0.x > pc.density_floor)) return;
    float delta_temperature = pc.pad0;
    float velocity_unit2 = pc.velocity_m_s_per_sim * pc.velocity_m_s_per_sim;
    float ion_fraction = clamp(pop_value(cell, 6) / q0.x, 0.0, 1.0);
    float delta_thermal = q0.x * K_B * delta_temperature * (1.0 + ion_fraction)
        / max((pc.gamma_gas - 1.0) * M_H * velocity_unit2, 1.0e-30);
    float next_energy = material1[cell].x + delta_thermal;
    if (!finite_float(delta_temperature) || delta_temperature <= 0.0
            || !finite_float(delta_thermal) || delta_thermal <= 0.0
            || !finite_float(next_energy) || next_energy < material1[cell].x) {
        atomicOr(status[0].x, STATUS_KINETICS_FAILURE);
        return;
    }
    material1[cell].x = next_energy;
    refresh_thermodynamics(cell);
}

float group_energy(uint cell, uint group) {
    float sum = 0.0;
    for (uint angle = 0u; angle < angles(); ++angle)
        sum += ordinate_data[angle].w * max(radiation_active[rad_index(cell, group, angle)], 0.0);
    return sum;
}
vec3 group_momentum_numerator(uint cell, uint group) {
    vec3 sum = vec3(0.0);
    for (uint angle = 0u; angle < angles(); ++angle) {
        vec4 ordinate = ordinate_data[angle];
        sum += ordinate.w * max(radiation_active[rad_index(cell, group, angle)], 0.0) * ordinate.xyz;
    }
    return sum;
}
// The log-temperature lattice coordinate of rate_data is fixed for the whole
// cell (every lookup in one invocation uses one temperature), so it is built
// once.  Collisional excitation/deexcitation rates are a thermodynamic pair:
// interpolate the deexcitation direction in log space and derive excitation
// from detailed balance at the actual cell temperature.  Interpolating both
// table columns independently violates that relation between grid knots.
struct RateLattice {
    int lower;
    int upper;
    float fraction;
    float temperature;
};
RateLattice rate_lattice(float temperature) {
    float log_min = log(10.0);
    float log_max = log(1.0e8);
    float clamped_temperature = finite_float(temperature)
        ? clamp(temperature, 10.0, 1.0e8) : 10.0;
    float coordinate_t = (log(clamped_temperature) - log_min) / (log_max - log_min)
        * float(RATE_SAMPLES - 1);
    RateLattice lattice;
    lattice.lower = int(floor(coordinate_t));
    lattice.upper = min(lattice.lower + 1, RATE_SAMPLES - 1);
    lattice.fraction = coordinate_t - float(lattice.lower);
    lattice.temperature = clamped_temperature;
    return lattice;
}
float log_interpolated_rate(int slot, RateLattice lattice) {
    float a = rate_data[lattice.lower * RATE_STRIDE + slot];
    float b = rate_data[lattice.upper * RATE_STRIDE + slot];
    if (lattice.lower == lattice.upper || lattice.fraction <= 0.0) return a;
    // The deexcitation table is positive across the declared temperature
    // domain.  Keep a malformed/underflowed endpoint from manufacturing a
    // NaN; the model loader remains the authoritative shape/identity guard.
    if (!(a > 0.0) || !(b > 0.0)) return 0.0;
    return exp(mix(log(a), log(b), lattice.fraction));
}
float collisional_transition_rate_at(int slot, RateLattice lattice) {
    int line = (slot - 2) / 2;
    int deexcitation_slot = 3 + 2 * line;
    float deexcitation = log_interpolated_rate(deexcitation_slot, lattice);
    if ((slot - 2) % 2 == 1 || !(deexcitation > 0.0)) return deexcitation;
    int lower = int(line_a[line].x + 0.5);
    int upper = int(line_a[line].y + 0.5);
    float lower_degeneracy = max(level_data[lower].y, 1.0e-30);
    float upper_degeneracy = max(level_data[upper].y, 1.0e-30);
    float delta_j = max(level_data[upper].x - level_data[lower].x, 0.0);
    float log_excitation = log(deexcitation)
        + log(upper_degeneracy / lower_degeneracy)
        - delta_j / (K_B * lattice.temperature);
    return exp(log_excitation);
}
float rate_at(int slot, RateLattice lattice) {
    if (slot >= 2 && slot < 2 + LINES * 2)
        return collisional_transition_rate_at(slot, lattice);
    float a = rate_data[lattice.lower * RATE_STRIDE + slot];
    float b = rate_data[lattice.upper * RATE_STRIDE + slot];
    return mix(a, b, lattice.fraction);
}
// Sum of 1/(n+1)^3 over the six bound levels.  One canonical assembly, shared
// by solve_kinetics() and build_cell_terms(), so the two branch conventions
// cannot drift apart.
float branch_normalization() {
    float branch_norm = 0.0;
    for (int level = 0; level < 6; ++level) branch_norm += 1.0 / pow(float(level + 1), 3.0);
    return branch_norm;
}
void add_transition(inout float generator[49], int from_state, int to_state, float rate) {
    if (!(rate > 0.0) || !finite_float(rate)) return;
    generator[to_state * LEVELS + from_state] += rate;
    generator[from_state * LEVELS + from_state] -= rate;
}
// Radiation-driven rates must use the speed the radiation field actually
// propagates at in this configuration (pc.c_reduced_sim, sim units per sim
// second), not the physical c: otherwise photo/line rates run ahead of the
// energy the exchange can deposit, and the rate solve consumes thermal energy
// that no absorbed photon paid for.
float radiation_speed_m_s() {
    return pc.c_reduced_sim * pc.length_m_per_sim / max(pc.time_s_per_sim, 1.0e-30);
}
// Group a spectral line's nominal index resolves to.  Kept beside the rate
// helpers so solve_kinetics() indexes the per-cell group-energy cache exactly
// as line_absorption_rate() used to derive its own group.
uint line_energy_group(int line) {
    return uint(clamp(int(line_b[line].y + 0.5), 0, int(groups()) - 1));
}
float line_energy_density_hz(float group_energy_value, uint group) {
    return group_energy_value * pc.energy_density_J_m3_per_sim
        / max(frequency_data[group].w, 1.0);
}
float line_absorption_rate(uint cell, int line, float energy_density_hz) {
    int lower = int(line_a[line].x + 0.5);
    float frequency = line_a[line].z;
    float sigma_integral = E_CHARGE * E_CHARGE
        / (4.0 * EPSILON_0 * M_E * C_LIGHT) * max(line_b[line].x, 0.0);
    float photon_rate = radiation_speed_m_s() * energy_density_hz * sigma_integral
        / max(H_PLANCK * frequency, 1.0e-40);
    return pop_value(cell, lower) > 0.0 ? max(photon_rate, 0.0) : 0.0;
}
void solve_kinetics(uint cell) {
    vec4 q0 = material0[cell];
    if (!(q0.x > pc.density_floor) || pc.source_enabled < 0.5) return;
    float old_population[LEVELS];
    for (int state = 0; state < LEVELS; ++state) old_population[state] = max(pop_value(cell, state), 0.0);
    float temperature = temperature_from_state(cell);
    if (!finite_float(temperature)) {
        atomicOr(status[0].x, STATUS_KINETICS_FAILURE);
        return;
    }
    float electron_density = old_population[6] * pc.density_kg_m3_per_sim / M_H;
    // One angular integral per group for the whole cell: the line rates and the
    // photoionization assembly below both read this, instead of re-summing all
    // 26 ordinates for every line (15) and every (level, group) pair (144).
    // radiation_active is not written during the kinetics pass, so the cached
    // sums are bit-identical to re-deriving them.
    float group_energy_cache[MAX_GROUPS];
    for (uint group = 0u; group < groups(); ++group)
        group_energy_cache[group] = group_energy(cell, group);
    RateLattice lattice = rate_lattice(temperature);
    float generator[49];
    for (int i = 0; i < 49; ++i) generator[i] = 0.0;
    for (int line = 0; line < LINES; ++line) {
        int lower = int(line_a[line].x + 0.5);
        int upper = int(line_a[line].y + 0.5);
        uint energy_group = line_energy_group(line);
        float energy_density_hz = line_energy_density_hz(group_energy_cache[energy_group],
            energy_group);
        float coll_up = rate_at(2 + 2 * line, lattice) * electron_density;
        float coll_down = rate_at(3 + 2 * line, lattice) * electron_density;
        float radiative_down = line_a[line].w;
        if (lower == 0 && upper == 1)
            radiative_down = 0.75 * radiative_down + 0.25 * pc.two_photon_A_s_inv;
        add_transition(generator, lower, upper,
            coll_up + line_absorption_rate(cell, line, energy_density_hz));
        add_transition(generator, upper, lower, coll_down + radiative_down);
    }
    float ion_rate_coeff = rate_at(0, lattice) * electron_density;
    float recombination = rate_at(1, lattice) * electron_density;
    float branch_norm = branch_normalization();
    // photoionization_rate() inlined group-major: each level still accumulates
    // its qualifying groups in ascending order, so every level keeps the
    // identical float32 summation order while the angular integrals above are
    // re-used instead of recomputed 144 times.
    float photoionization[6];
    for (int level = 0; level < 6; ++level) photoionization[level] = 0.0;
    float radiation_speed = radiation_speed_m_s();
    for (uint group = 0u; group < groups(); ++group) {
        float frequency = frequency_data[group].z;
        float energy_si = group_energy_cache[group] * pc.energy_density_J_m3_per_sim;
        for (int level = 0; level < 6; ++level) {
            float threshold = level_data[level].z;
            if (frequency < threshold) continue;
            float sigma = level_data[level].w * pow(threshold / frequency, 3.0);
            photoionization[level] += radiation_speed * energy_si * sigma
                / max(H_PLANCK * frequency, 1.0e-40);
        }
    }
    for (int level = 0; level < 6; ++level) {
        add_transition(generator, level, 6, ion_rate_coeff + photoionization[level]);
        add_transition(generator, 6, level, recombination
            / (pow(float(level + 1), 3.0) * branch_norm));
    }
    float augmented[56];
    float dt_seconds = pc.dt_sim * pc.time_s_per_sim;
    for (int row = 0; row < LEVELS; ++row) {
        float row_scale = 1.0;
        for (int column = 0; column < LEVELS; ++column) {
            float value = (row == column ? 1.0 : 0.0) - dt_seconds * generator[row * LEVELS + column];
            augmented[row * 8 + column] = value;
            row_scale = max(row_scale, abs(value));
        }
        augmented[row * 8 + 7] = old_population[row];
        for (int column = 0; column < 8; ++column) augmented[row * 8 + column] /= row_scale;
    }
    bool valid = true;
    for (int pivot = 0; pivot < LEVELS; ++pivot) {
        int best = pivot;
        float best_value = abs(augmented[pivot * 8 + pivot]);
        for (int row = pivot + 1; row < LEVELS; ++row) {
            float candidate = abs(augmented[row * 8 + pivot]);
            if (candidate > best_value) { best = row; best_value = candidate; }
        }
        if (!(best_value > 1.0e-20) || !finite_float(best_value)) { valid = false; break; }
        if (best != pivot) {
            for (int column = 0; column < 8; ++column) {
                float temporary = augmented[pivot * 8 + column];
                augmented[pivot * 8 + column] = augmented[best * 8 + column];
                augmented[best * 8 + column] = temporary;
            }
        }
        float inverse = 1.0 / augmented[pivot * 8 + pivot];
        for (int column = pivot; column < 8; ++column) augmented[pivot * 8 + column] *= inverse;
        for (int row = 0; row < LEVELS; ++row) {
            if (row == pivot) continue;
            float factor = augmented[row * 8 + pivot];
            for (int column = pivot; column < 8; ++column)
                augmented[row * 8 + column] -= factor * augmented[pivot * 8 + column];
        }
    }
    float next_population[LEVELS];
    float total = 0.0;
    for (int state = 0; state < LEVELS; ++state) {
        next_population[state] = max(augmented[state * 8 + 7], 0.0);
        valid = valid && finite_float(next_population[state]);
        total += next_population[state];
    }
    if (!valid || !(total > 0.0)) {
        atomicOr(status[0].x, STATUS_KINETICS_FAILURE);
        atomicAdd(status[1].z, 1u);
        return;
    }
    float scale = q0.x / total;
    for (int state = 0; state < LEVELS; ++state) next_population[state] *= scale;
    // The implicit kinetics solve can request more excitation/ionization
    // energy than the material's current non-kinetic reservoir, especially
    // across the production-scale timestep.  Limit only the uphill chemical
    // part of that population update; total material energy remains
    // unchanged, so the balance is drawn from thermal energy without ever
    // crossing the registered pressure floor.
    float velocity_unit2 = pc.velocity_m_s_per_sim * pc.velocity_m_s_per_sim;
    float old_chemical = 0.0;
    float next_chemical = 0.0;
    for (int state = 0; state < LEVELS; ++state) {
        float specific_energy = level_data[state].x / (M_H * velocity_unit2);
        old_chemical += old_population[state] * specific_energy;
        next_chemical += next_population[state] * specific_energy;
    }
    float kinetic = 0.5 * dot(q0.yzw, q0.yzw) / q0.x;
    float thermal_floor = resolved_thermal_floor(cell);
    float chemical_limit = max(material1[cell].x - kinetic - thermal_floor, 0.0);
    if (next_chemical > chemical_limit && next_chemical > old_chemical) {
        float lambda = clamp((chemical_limit - old_chemical)
            / (next_chemical - old_chemical), 0.0, 1.0);
        for (int state = 0; state < LEVELS; ++state)
            next_population[state] = mix(old_population[state], next_population[state], lambda);
        atomicOr(status[0].x, STATUS_SOURCE_LIMITED);
    }
    store_populations(cell, next_population);
    refresh_thermodynamics(cell);
}
float erf_approx(float x) {
    float sign_x = sign(x);
    float a = abs(x);
    float t = 1.0 / (1.0 + 0.3275911 * a);
    float polynomial = (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
        - 0.284496736) * t + 0.254829592) * t;
    return sign_x * (1.0 - polynomial * exp(-a * a));
}
float line_group_fraction(int line, uint group, float temperature) {
    float center = line_a[line].z;
    float thermal_sigma = center * sqrt(max(2.0 * K_B * temperature / M_H, 0.0)) / C_LIGHT;
    float natural_sigma = line_a[line].w / (4.0 * PI);
    float sigma = max(max(thermal_sigma, natural_sigma), center * 1.0e-8);
    float lo = (frequency_data[group].x - center) / (sqrt(2.0) * sigma);
    float hi = (frequency_data[group].y - center) / (sqrt(2.0) * sigma);
    if (lo > LINE_TAIL_CUTOFF || hi < -LINE_TAIL_CUTOFF) return 0.0;
    return clamp(0.5 * (erf_approx(hi) - erf_approx(lo)), 0.0, 1.0);
}
float free_bound_fraction(int level, uint group, float temperature) {
    float threshold_energy = H_PLANCK * level_data[level].z;
    float lo_energy = H_PLANCK * frequency_data[group].x;
    float hi_energy = H_PLANCK * frequency_data[group].y;
    if (hi_energy <= threshold_energy) return 0.0;
    float lo = max(lo_energy - threshold_energy, 0.0);
    float hi = max(hi_energy - threshold_energy, 0.0);
    return max(exp(-lo / (K_B * temperature)) - exp(-hi / (K_B * temperature)), 0.0);
}
float two_photon_weight(uint group) {
    float lyman_frequency = line_a[0].z;
    float lo = clamp(frequency_data[group].x / lyman_frequency, 0.0, 1.0);
    float hi = clamp(frequency_data[group].y / lyman_frequency, 0.0, 1.0);
    if (hi <= lo) return 0.0;
    float mid = 0.5 * (lo + hi);
    return pow(mid * (1.0 - mid), 3.0) * (hi - lo);
}
// n_e == n_p for the single-species hydrogen closure, so one number density
// carries both charge densities.
float free_free_sample(float log_midpoint, float half_span, float node,
        float temperature) {
    float log_frequency = log_midpoint + half_span * node;
    float sample_frequency = exp(log_frequency);
    float exponent = H_PLANCK * sample_frequency / (K_B * temperature);
    float gaunt = clamp((sqrt(3.0) / PI)
        * log(max(2.25 / max(exponent, 1.0e-30), 1.000001)), 1.0, 5.0);
    return exp(log_frequency - exponent) * gaunt;
}

float free_free_group_emissivity(uint group, float temperature, float number_density) {
    if (!(temperature > 0.0) || !(number_density > 0.0)) return 0.0;
    float log_lower = log(max(frequency_data[group].x, 1.0));
    float log_upper = log(max(frequency_data[group].y, 1.0));
    float half_span = 0.5 * (log_upper - log_lower);
    if (!(half_span > 0.0)) return 0.0;
    float log_midpoint = 0.5 * (log_lower + log_upper);
    float weighted_integral = 0.0;
    // Keep the eight Gauss-Legendre nodes as static component accesses.  The
    // Vulkan path used here does not implement OpVectorExtractDynamic reliably;
    // a dynamic vec4 lane can become undefined and turn this positive integral
    weighted_integral += FREE_FREE_WEIGHTS_0.x
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_0.x, temperature);
    weighted_integral += FREE_FREE_WEIGHTS_0.y
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_0.y, temperature);
    weighted_integral += FREE_FREE_WEIGHTS_0.z
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_0.z, temperature);
    weighted_integral += FREE_FREE_WEIGHTS_0.w
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_0.w, temperature);
    weighted_integral += FREE_FREE_WEIGHTS_1.x
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_1.x, temperature);
    weighted_integral += FREE_FREE_WEIGHTS_1.y
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_1.y, temperature);
    weighted_integral += FREE_FREE_WEIGHTS_1.z
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_1.z, temperature);
    weighted_integral += FREE_FREE_WEIGHTS_1.w
        * free_free_sample(log_midpoint, half_span, FREE_FREE_NODES_1.w, temperature);
    if (!(weighted_integral > 0.0)) return 0.0;
    float log_emission = log(6.8) - 51.0 * log(10.0)
        + log(number_density) + log(number_density) - 0.5 * log(temperature)
        + log(half_span) + log(weighted_integral);
    return exp(log_emission);
}

// Per-cell quantities that coefficients() needs but that are identical for all
// 24 groups of the cell: n_e (= n_p, the ionised hydrogen population), the
// recombination rate, the two grid normalisations, and the rate-table lattice.
// Assembling them once per cell removes the per-group rate_at() log, the
// per-group two_photon_weight sweep, and the duplicated branch sum.
struct CellTerms {
    float electron_number_density;
    float recombination;
    float two_norm;
    float branch_norm;
};
CellTerms build_cell_terms(uint cell, float temperature) {
    CellTerms terms;
    float density_scale = pc.density_kg_m3_per_sim / M_H;
    terms.electron_number_density = pop_value(cell, 6) * density_scale;
    // Keep the first density multiplication explicit: reassociating n_e^2
    // before multiplying by alpha overflows float32 at the registered dense
    // slab (n_e=1e21 m^-3), even though alpha*n_e*n_e is finite.
    precise float recombination = rate_at(1, rate_lattice(temperature));
    recombination *= terms.electron_number_density;
    recombination *= terms.electron_number_density;
    terms.recombination = recombination;
    terms.branch_norm = branch_normalization();
    float two_norm = 0.0;
    for (uint candidate = 0u; candidate < groups(); ++candidate)
        two_norm += two_photon_weight(candidate);
    terms.two_norm = two_norm;
    return terms;
}
Coefficients coefficients(uint cell, uint group, float temperature, CellTerms cell_terms) {
    Coefficients result;
    result.emission_rate = 0.0;
    result.absorption = 0.0;
    float density_scale = pc.density_kg_m3_per_sim / M_H;
    float numbers[LEVELS];
    for (int state = 0; state < LEVELS; ++state) numbers[state] = pop_value(cell, state) * density_scale;
    // n_e == n_p for this single-species hydrogen closure, so one name and one
    // value carry both (recombination is rate * n_e^2).
    float electron_number_density = cell_terms.electron_number_density;
    float frequency = frequency_data[group].z;
    float width = max(frequency_data[group].w, 1.0);
    for (int line = 0; line < LINES; ++line) {
        float fraction = line_group_fraction(line, group, temperature);
        if (!(fraction > 0.0)) continue;
        int lower = int(line_a[line].x + 0.5);
        int upper = int(line_a[line].y + 0.5);
        float branch = (lower == 0 && upper == 1) ? 0.75 : 1.0;
        float photon_energy = H_PLANCK * line_a[line].z;
        // Stepwise precise accumulation, matching the free-bound and two-photon
        // terms: the chained product is reordered by the compiler into a form
        // that loses most of the line's contribution.
        precise float line_term = numbers[upper];
        line_term *= line_a[line].w * photon_energy;
        line_term *= branch;
        line_term *= fraction;
        result.emission_rate += line_term;
        float stimulated = numbers[lower] - numbers[upper] * line_b[line].z / max(line_b[line].w, 1.0);
        float sigma_integral = E_CHARGE * E_CHARGE
            / (4.0 * EPSILON_0 * M_E * C_LIGHT) * max(line_b[line].x, 0.0);
        result.absorption += max(stimulated, 0.0) * sigma_integral * fraction / width;
    }
    for (int level = 0; level < 6; ++level) {
        float threshold = level_data[level].z;
        if (frequency >= threshold)
            result.absorption += numbers[level] * level_data[level].w * pow(threshold / frequency, 3.0);
    }
    float free_free_group = free_free_group_emissivity(group, temperature,
        electron_number_density);
    result.emission_rate += free_free_group;
    float exponent = H_PLANCK * frequency / (K_B * temperature);
    float planck = exponent < PLANCK_EXPONENT_CLAMP
        ? (2.0 * H_PLANCK * frequency * frequency * frequency / (C_LIGHT * C_LIGHT)) / max(exp(exponent) - 1.0, 1.0e-30)
        : 0.0;
    if (planck > 0.0) result.absorption += free_free_group / (width * FOUR_PI * planck);
    float recombination = cell_terms.recombination;
    float branch_norm = cell_terms.branch_norm;
    for (int level = 0; level < 6; ++level) {
        float fraction = free_bound_fraction(level, group, temperature);
        float branch = 1.0 / (pow(float(level + 1), 3.0) * branch_norm);
        // Stepwise precise accumulation, matching the two-photon term below:
        // the chained product is reordered by the compiler into a form that
        // loses the term at low density.
        precise float free_bound_term = recombination;
        free_bound_term *= branch;
        free_bound_term *= fraction;
        free_bound_term *= H_PLANCK * frequency;
        result.emission_rate += free_bound_term;
    }
    float two_norm = cell_terms.two_norm;
    if (two_norm > 0.0) {
        float two_photon_energy_rate = pc.two_photon_A_s_inv
            * (H_PLANCK * line_a[0].z);
        precise float two_photon_emission = numbers[1];
        two_photon_emission *= 0.25 * two_photon_energy_rate;
        two_photon_emission *= two_photon_weight(group) / two_norm;
        result.emission_rate += two_photon_emission;
    }
    result.scattering = electron_number_density * SIGMA_T;
    result.emission_rate = max(result.emission_rate * pc.time_s_per_sim
        / pc.energy_density_J_m3_per_sim, 0.0);
    result.absorption = max(result.absorption * pc.length_m_per_sim, 0.0);
    result.scattering = max(result.scattering * pc.length_m_per_sim, 0.0);
    return result;
}
// Group-only absorptive response of one radiation cell: every term depends on
// the coefficient and the push constants alone, never on the ordinate, so it is
// assembled once per group and shared by the loss/gain, energy and write-back
// passes rather than re-derived for each of the 26 angles in each of them.
struct AbsorptionTerms {
    float emission_rate; // raw coefficient emission rate (non-absorptive arm)
    float transmission;  // exp(-min(tau, TRANSMISSION_CLAMP))
    float one_minus;     // 1 - transmission
    float source;        // equilibrium source when has_absorption
    float scatter_mix;   // isotropic in-scatter blend
    bool has_absorption; // coefficient.absorption > 1.0e-30
};
AbsorptionTerms absorption_terms(Coefficients coefficient) {
    AbsorptionTerms terms;
    terms.emission_rate = coefficient.emission_rate;
    terms.has_absorption = coefficient.absorption > 1.0e-30;
    float tau = min(pc.c_reduced_sim * coefficient.absorption * pc.dt_sim, TRANSMISSION_CLAMP);
    terms.transmission = exp(-tau);
    terms.one_minus = 1.0 - terms.transmission;
    terms.source = terms.has_absorption
        ? coefficient.emission_rate / (FOUR_PI * pc.c_reduced_sim * coefficient.absorption)
        : 0.0;
    terms.scatter_mix = 1.0 - exp(-min(pc.c_reduced_sim * coefficient.scattering * pc.dt_sim,
        TRANSMISSION_CLAMP));
    return terms;
}
Coefficients coefficients_from_cache(vec4 packed) {
    Coefficients result;
    result.emission_rate = packed.x;
    result.absorption = packed.y;
    result.scattering = packed.z;
    return result;
}
vec4 coefficients_to_cache(Coefficients coefficient) {
    return vec4(coefficient.emission_rate, coefficient.absorption,
        coefficient.scattering, 0.0);
}
float absorptive_target(float old_value, AbsorptionTerms terms, float emission_scale) {
    if (!terms.has_absorption)
        return old_value + emission_scale * terms.emission_rate * pc.dt_sim / FOUR_PI;
    return old_value * terms.transmission + emission_scale * terms.source * terms.one_minus;
}
float desired_source_value(float old_value, AbsorptionTerms terms, float emission_scale,
        float mean_after_absorption) {
    float absorbed = absorptive_target(old_value, terms, emission_scale);
    return mix(absorbed, mean_after_absorption / FOUR_PI, terms.scatter_mix);
}
float thermal_after_exchange(uint cell, float lambda, float delta_energy, vec3 delta_momentum) {
    vec4 q0 = material0[cell];
    vec3 momentum = q0.yzw - lambda * delta_momentum / max(pc.c_reduced_sim, 1.0e-20);
    float energy = material1[cell].x - lambda * delta_energy;
    float kinetic = q0.x > pc.density_floor ? 0.5 * dot(momentum, momentum) / q0.x : 0.0;
    return energy - kinetic - chemical_energy(cell);
}
// Shared limiting-factor bracket for the source exchange and the moving-frame
// remap: keep lambda = 1 when the full exchange stays above the thermal floor,
// otherwise bisect (12 halvings) for the largest lambda that does.
float limiting_lambda(uint cell, float delta_energy, vec3 delta_momentum) {
    vec4 q0 = material0[cell];
    if (!(q0.x > pc.density_floor)) return 1.0;
    float thermal_floor = resolved_thermal_floor(cell);
    if (!(thermal_after_exchange(cell, 1.0, delta_energy, delta_momentum) < thermal_floor))
        return 1.0;
    float lo = 0.0;
    float hi = 1.0;
    for (int iteration = 0; iteration < 12; ++iteration) {
        float mid = 0.5 * (lo + hi);
        if (thermal_after_exchange(cell, mid, delta_energy, delta_momentum) >= thermal_floor) lo = mid;
        else hi = mid;
    }
    atomicOr(status[0].x, STATUS_SOURCE_LIMITED);
    return lo;
}
void apply_radiation_source(uint cell, bool evolve_kinetics) {
    vec4 source_q0 = material0[cell];
    vec3 source_velocity = source_q0.x > pc.density_floor
        ? source_q0.yzw / source_q0.x : vec3(0.0);
    if (finite_vec3(source_velocity)) {
        float source_v_over_c = length(source_velocity)
            / max(pc.c_reduced_sim, 1.0e-20);
        atomicMax(status[2].w, floatBitsToUint(source_v_over_c));
    }
    if (evolve_kinetics) solve_kinetics(cell);
    float temperature = temperature_from_state(cell);
    CellTerms cell_terms = build_cell_terms(cell, temperature);
    float emission_gain = 0.0;
    float absorption_loss = 0.0;
    // coefficients() is by far the most expensive routine in this dispatch and
    // its inputs (populations, material state, temperature) are fixed for the
    // whole cell pass -- nothing between the three loops below writes any of
    // them.  One evaluation per group is therefore cached (xyz = emission_rate,
    // absorption, scattering) and the scale, energy and write-back passes read
    // the cache instead of recomputing it twice more.
    vec4 coefficient_cache[MAX_GROUPS];
    // Pass 2 derives the same per-group angular mean that pass 3 needs, so it is
    // carried across instead of re-accumulated over the 26 ordinates.
    float mean_cache[MAX_GROUPS];
    for (uint group = 0u; group < groups(); ++group) {
        Coefficients coefficient = coefficients(cell, group, temperature, cell_terms);
        coefficient_cache[group] = coefficients_to_cache(coefficient);
        AbsorptionTerms terms = absorption_terms(coefficient);
        opacity_group[group_index(cell, group)] = coefficient.absorption + coefficient.scattering;
        emission_group[group_index(cell, group)] = coefficient.emission_rate;
        for (uint angle = 0u; angle < angles(); ++angle) {
            float weight = ordinate_data[angle].w;
            float old_value = max(radiation_active[rad_index(cell, group, angle)], 0.0);
            absorption_loss += weight * old_value * terms.one_minus;
            emission_gain += terms.has_absorption
                ? (weight * terms.source * terms.one_minus)
                : (weight * coefficient.emission_rate * pc.dt_sim / FOUR_PI);
        }
    }
    vec4 q0 = material0[cell];
    float kinetic = q0.x > pc.density_floor ? 0.5 * dot(q0.yzw, q0.yzw) / q0.x : 0.0;
    float available = max(material1[cell].x - kinetic - chemical_energy(cell)
        - pc.pressure_floor / (pc.gamma_gas - 1.0), 0.0);
    float emission_scale = emission_gain > 0.0
        ? clamp((available + absorption_loss) / emission_gain, 0.0, 1.0) : 1.0;
    if (emission_scale < 0.999999) atomicOr(status[0].x, STATUS_SOURCE_LIMITED);
    float before_energy = 0.0;
    float after_energy = 0.0;
    vec3 before_momentum = vec3(0.0);
    vec3 after_momentum = vec3(0.0);
    for (uint group = 0u; group < groups(); ++group) {
        Coefficients coefficient = coefficients_from_cache(coefficient_cache[group]);
        AbsorptionTerms terms = absorption_terms(coefficient);
        float mean_after_absorption = 0.0;
        for (uint angle = 0u; angle < angles(); ++angle)
            mean_after_absorption += ordinate_data[angle].w * absorptive_target(
                max(radiation_active[rad_index(cell, group, angle)], 0.0), terms, emission_scale);
        mean_cache[group] = mean_after_absorption;
        for (uint angle = 0u; angle < angles(); ++angle) {
            vec4 ordinate = ordinate_data[angle];
            float old_value = max(radiation_active[rad_index(cell, group, angle)], 0.0);
            float target = desired_source_value(old_value, terms,
                emission_scale, mean_after_absorption);
            before_energy += ordinate.w * old_value;
            after_energy += ordinate.w * target;
            before_momentum += ordinate.w * old_value * ordinate.xyz;
            after_momentum += ordinate.w * target * ordinate.xyz;
        }
    }
    float delta_energy = after_energy - before_energy;
    vec3 delta_momentum = after_momentum - before_momentum;
    float lambda = limiting_lambda(cell, delta_energy, delta_momentum);
    for (uint group = 0u; group < groups(); ++group) {
        Coefficients coefficient = coefficients_from_cache(coefficient_cache[group]);
        AbsorptionTerms terms = absorption_terms(coefficient);
        float mean_after_absorption = mean_cache[group];
        for (uint angle = 0u; angle < angles(); ++angle) {
            uint index = rad_index(cell, group, angle);
            float old_value = max(radiation_active[index], 0.0);
            float target = desired_source_value(old_value, terms,
                emission_scale, mean_after_absorption);
            float next_value = mix(old_value, target, lambda);
            if (!finite_float(next_value) || next_value < 0.0) {
                atomicOr(status[0].x, STATUS_SOURCE_NONFINITE);
                next_value = old_value;
            }
            radiation_active[index] = next_value;
        }
    }
    material0[cell].yzw -= lambda * delta_momentum / max(pc.c_reduced_sim, 1.0e-20);
    material1[cell].x -= lambda * delta_energy;
    ledger0[cell].w += lambda * delta_energy;
    refresh_thermodynamics(cell);
}
vec3 velocity_at(ivec3 c, uvec3 d) {
    if (!in_domain(c, d)) return vec3(0.0);
    vec4 q0 = material0[linear_cell(c, d)];
    return q0.x > pc.density_floor ? q0.yzw / q0.x : vec3(0.0);
}
mat3 velocity_gradient(uint cell) {
    uvec3 d = dims();
    ivec3 c = coordinate(cell, d);
    vec3 spacing = 2.0 * vec3(pc.extent_x, pc.extent_y, pc.extent_z) / vec3(d);
    vec3 center = velocity_at(c, d);
    mat3 gradient = mat3(0.0);
    for (int axis = 0; axis < 3; ++axis) {
        ivec3 offset = axis == 0 ? ivec3(1, 0, 0) : (axis == 1 ? ivec3(0, 1, 0) : ivec3(0, 0, 1));
        vec3 lower = in_domain(c - offset, d) ? velocity_at(c - offset, d) : center;
        vec3 upper = in_domain(c + offset, d) ? velocity_at(c + offset, d) : center;
        float denominator = (in_domain(c - offset, d) && in_domain(c + offset, d))
            ? 2.0 * spacing[axis] : spacing[axis];
        gradient[axis] = (upper - lower) / denominator;
    }
    return gradient;
}
void nearest_three(vec3 direction, out ivec3 indices, out vec3 weights) {
    vec3 best_dot = vec3(-2.0);
    indices = ivec3(0);
    for (uint candidate = 0u; candidate < angles(); ++candidate) {
        float score = dot(direction, ordinate_data[candidate].xyz);
        if (score > best_dot.x) {
            best_dot.z = best_dot.y; indices.z = indices.y;
            best_dot.y = best_dot.x; indices.y = indices.x;
            best_dot.x = score; indices.x = int(candidate);
        } else if (score > best_dot.y) {
            best_dot.z = best_dot.y; indices.z = indices.y;
            best_dot.y = score; indices.y = int(candidate);
        } else if (score > best_dot.z) {
            best_dot.z = score; indices.z = int(candidate);
        }
    }
    float floor_score = best_dot.z - 1.0e-5;
    weights = max(best_dot - vec3(floor_score), vec3(1.0e-6));
    weights /= weights.x + weights.y + weights.z;
}
void frequency_targets(float target_frequency, out ivec2 indices, out vec2 weights, out int escape_side) {
    escape_side = 0;
    if (target_frequency < frequency_data[0].x) { escape_side = -1; indices = ivec2(0); weights = vec2(0.0); return; }
    if (target_frequency > frequency_data[groups() - 1u].y) { escape_side = 1; indices = ivec2(0); weights = vec2(0.0); return; }
    if (target_frequency <= frequency_data[0].z) { indices = ivec2(0); weights = vec2(1.0, 0.0); return; }
    for (uint group = 1u; group < groups(); ++group) {
        if (target_frequency <= frequency_data[group].z) {
            float lo = log(frequency_data[group - 1u].z);
            float hi = log(frequency_data[group].z);
            float fraction = clamp((log(target_frequency) - lo) / (hi - lo), 0.0, 1.0);
            indices = ivec2(int(group - 1u), int(group));
            weights = vec2(1.0 - fraction, fraction);
            return;
        }
    }
    indices = ivec2(int(groups() - 1u)); weights = vec2(1.0, 0.0);
}
void validate_moving_frame(uint cell) {
    vec4 q0 = material0[cell];
    if (!(q0.x > pc.density_floor)) return;
    vec3 velocity = q0.yzw / q0.x;
    if (!finite_vec3(velocity)) {
        atomicOr(status[0].x, STATUS_MOVING_FRAME_DOMAIN | STATUS_STEP_REJECTED);
        atomicAdd(status[1].w, 1u);
        return;
    }
    float v_over_c = length(velocity) / max(pc.c_reduced_sim, 1.0e-20);
    if (!finite_float(v_over_c) || v_over_c > pc.maximum_v_over_c) {
        atomicOr(status[0].x, STATUS_MOVING_FRAME_DOMAIN | STATUS_STEP_REJECTED);
        atomicAdd(status[1].w, 1u);
    }
}

void remap_moving_frame(uint cell) {
    mat3 gradient = velocity_gradient(cell);
    vec4 q0 = material0[cell];
    vec3 velocity = q0.x > pc.density_floor ? q0.yzw / q0.x : vec3(0.0);
    if (!finite_vec3(velocity)) {
        atomicOr(status[0].x, STATUS_MOVING_FRAME_DOMAIN | STATUS_STEP_REJECTED);
        atomicAdd(status[1].w, 1u);
        return;
    }
    float v_over_c = length(velocity) / max(pc.c_reduced_sim, 1.0e-20);
    if (v_over_c > pc.maximum_v_over_c) {
        atomicOr(status[0].x, STATUS_MOVING_FRAME_DOMAIN | STATUS_STEP_REJECTED);
        atomicAdd(status[1].w, 1u);
        return;
    }
    uint count = groups() * angles();
    uint base = cell * count;
    for (uint index = 0u; index < count; ++index) radiation_scratch[base + index] = 0.0;
    // The angular side of the remap -- frequency projection, aberration, and the
    // three nearest target ordinates with their weights -- has no group-dependent
    // operand, so it is solved once per angle here instead of once per
    // (group, angle) pair inside the nest below.  Only the frequency
    // interpolation there depends on the group.  No buffer barrier is needed:
    // this invocation only ever writes its own base..base+count-1 slice, and the
    // engine already inserts a barrier between this dispatch and the next.
    float angular_projection[MAX_ANGLES];
    int angular_index[MAX_ANGULAR_SLOTS];
    float angular_scale[MAX_ANGULAR_SLOTS];
    for (uint angle = 0u; angle < angles(); ++angle) {
        vec4 ordinate = ordinate_data[angle];
        vec3 direction = ordinate.xyz;
        vec3 grad_times_n = gradient * direction;
        float projection = dot(direction, grad_times_n);
        angular_projection[angle] = projection;
        vec3 angular_rate = -(transpose(gradient) * direction - direction * projection);
        vec3 target_direction = normalize(direction + pc.dt_sim * angular_rate);
        ivec3 angular_indices;
        vec3 angular_weights;
        nearest_three(target_direction, angular_indices, angular_weights);
        for (int ai = 0; ai < ANGULAR_TARGETS; ++ai) {
            int target_angle = angular_indices[ai];
            uint slot = angle * uint(ANGULAR_TARGETS) + uint(ai);
            angular_index[slot] = target_angle;
            angular_scale[slot] = angular_weights[ai] * ordinate.w
                / max(ordinate_data[target_angle].w, 1.0e-30);
        }
    }
    float low_escape = 0.0;
    float high_escape = 0.0;
    for (uint group = 0u; group < groups(); ++group) {
        for (uint angle = 0u; angle < angles(); ++angle) {
            float projection = angular_projection[angle];
            float target_frequency = frequency_data[group].z * exp(-pc.dt_sim * projection);
            float energy_ratio = target_frequency / frequency_data[group].z;
            ivec2 frequency_indices;
            vec2 frequency_weights;
            int escape_side;
            frequency_targets(target_frequency, frequency_indices, frequency_weights, escape_side);
            float old_value = max(radiation_active[rad_index(cell, group, angle)], 0.0);
            if (escape_side != 0) {
                float escaped = ordinate_data[angle].w * old_value * energy_ratio;
                if (escape_side < 0) low_escape += escaped; else high_escape += escaped;
                continue;
            }
            for (int fi = 0; fi < 2; ++fi) {
                if (!(frequency_weights[fi] > 0.0)) continue;
                for (int ai = 0; ai < ANGULAR_TARGETS; ++ai) {
                    uint slot = angle * uint(ANGULAR_TARGETS) + uint(ai);
                    uint destination = rad_index(cell, uint(frequency_indices[fi]),
                        uint(angular_index[slot]));
                    radiation_scratch[destination] += old_value * energy_ratio
                        * frequency_weights[fi] * angular_scale[slot];
                }
            }
        }
    }
    float before_energy = 0.0;
    float after_energy = low_escape + high_escape;
    vec3 before_momentum = vec3(0.0);
    vec3 after_momentum = vec3(0.0);
    for (uint group = 0u; group < groups(); ++group)
        for (uint angle = 0u; angle < angles(); ++angle) {
            vec4 ordinate = ordinate_data[angle];
            uint index = rad_index(cell, group, angle);
            before_energy += ordinate.w * radiation_active[index];
            after_energy += ordinate.w * radiation_scratch[index];
            before_momentum += ordinate.w * radiation_active[index] * ordinate.xyz;
            after_momentum += ordinate.w * radiation_scratch[index] * ordinate.xyz;
        }
    float delta_energy = after_energy - before_energy;
    vec3 delta_momentum = after_momentum - before_momentum;
    float lambda = limiting_lambda(cell, delta_energy, delta_momentum);
    for (uint index = 0u; index < count; ++index) {
        float old_value = radiation_active[base + index];
        float target = radiation_scratch[base + index];
        radiation_scratch[base + index] = mix(old_value, target, lambda);
    }
    material0[cell].yzw -= lambda * delta_momentum / max(pc.c_reduced_sim, 1.0e-20);
    material1[cell].x -= lambda * delta_energy;
    ledger0[cell].x += lambda * low_escape;
    ledger0[cell].y += lambda * high_escape;
    ledger0[cell].w += lambda * delta_energy;
    refresh_thermodynamics(cell);
}
void accumulate_spatial_escape(uint cell) {
    uvec3 d = dims();
    ivec3 c = coordinate(cell, d);
    vec3 spacing = 2.0 * vec3(pc.extent_x, pc.extent_y, pc.extent_z) / vec3(d);
    // The open-boundary escape fraction of an ordinate depends on the cell
    // position and the ordinate only, so it is evaluated once per angle rather
    // than repeated for all 24 groups.  The group/angle accumulation order of
    // `escaped` is unchanged.
    float escape_fraction[MAX_ANGLES];
    for (uint angle = 0u; angle < angles(); ++angle) {
        vec4 ordinate = ordinate_data[angle];
        float fraction = 0.0;
        if (c.x == 0 && ordinate.x < 0.0) fraction += -ordinate.x / spacing.x;
        if (c.x == int(d.x) - 1 && ordinate.x > 0.0) fraction += ordinate.x / spacing.x;
        if (c.y == 0 && ordinate.y < 0.0) fraction += -ordinate.y / spacing.y;
        if (c.y == int(d.y) - 1 && ordinate.y > 0.0) fraction += ordinate.y / spacing.y;
        if (c.z == 0 && ordinate.z < 0.0) fraction += -ordinate.z / spacing.z;
        if (c.z == int(d.z) - 1 && ordinate.z > 0.0) fraction += ordinate.z / spacing.z;
        escape_fraction[angle] = fraction;
    }
    float escaped = 0.0;
    for (uint group = 0u; group < groups(); ++group)
        for (uint angle = 0u; angle < angles(); ++angle)
            escaped += ordinate_data[angle].w
                * max(radiation_active[rad_index(cell, group, angle)], 0.0)
                * pc.c_reduced_sim * pc.dt_sim * escape_fraction[angle];
    ledger0[cell].z += max(escaped, 0.0);
}
void publish_coefficients(uint cell) {
    float temperature = temperature_from_state(cell);
    CellTerms cell_terms = build_cell_terms(cell, temperature);
    for (uint group = 0u; group < groups(); ++group) {
        Coefficients coefficient = coefficients(cell, group, temperature, cell_terms);
        opacity_group[group_index(cell, group)] = coefficient.absorption + coefficient.scattering;
        emission_group[group_index(cell, group)] = coefficient.emission_rate;
        if (LINE_TERM_DIAGNOSTIC && group == 19u && cell >= 1u && cell <= 35u) {
            float diagnostic_density_scale = pc.density_kg_m3_per_sim / M_H;
            float diagnostic_fraction = line_group_fraction(0, 19u, temperature);
            float diagnostic_center = line_a[0].z;
            float diagnostic_photon_energy = H_PLANCK * diagnostic_center;
            float diagnostic_branch = (int(line_a[0].x + 0.5) == 0
                && int(line_a[0].y + 0.5) == 1) ? 0.75 : 1.0;
            RateLattice diagnostic_lattice = rate_lattice(temperature);
            float diagnostic_electrons = pop_value(cell, 6) * diagnostic_density_scale;
            float chain[35];
            for (int state = 0; state < LEVELS; ++state) chain[state] = pop_value(cell, state);
            chain[7] = diagnostic_density_scale;
            chain[8] = pop_value(cell, 1) * diagnostic_density_scale;
            chain[9] = temperature;
            chain[10] = diagnostic_fraction;
            chain[11] = diagnostic_center;
            chain[12] = line_a[0].w;
            chain[13] = float(int(line_a[0].x + 0.5));
            chain[14] = float(int(line_a[0].y + 0.5));
            chain[15] = diagnostic_branch;
            chain[16] = diagnostic_photon_energy;
            chain[17] = 1.0 + pc.dt_sim * pc.time_s_per_sim * line_a[0].w;
            chain[18] = pc.dt_sim;
            chain[19] = pc.time_s_per_sim;
            chain[20] = rate_at(2, diagnostic_lattice);
            chain[21] = rate_at(3, diagnostic_lattice);
            chain[22] = rate_at(2, diagnostic_lattice) * diagnostic_electrons;
            chain[23] = rate_at(3, diagnostic_lattice) * diagnostic_electrons;
            chain[24] = pop_value(cell, 1) * diagnostic_density_scale * line_a[0].w
                * diagnostic_photon_energy * diagnostic_branch * diagnostic_fraction;
            chain[25] = coefficient.emission_rate;
            chain[26] = float(group);
            chain[27] = float(cell);
            chain[28] = frequency_data[19u].x;
            chain[29] = frequency_data[19u].y;
            chain[30] = 1.0 + pc.dt_sim * pc.time_s_per_sim
                * (diagnostic_branch * line_a[0].w + 0.25 * pc.two_photon_A_s_inv);
            chain[31] = frequency_data[19u].z;
            chain[32] = frequency_data[19u].w;
            chain[33] = pc.dt_sim * pc.time_s_per_sim;
            chain[34] = pc.source_enabled;
            opacity_group[group_index(cell, 19u)] = chain[int(cell) - 1];
        }
    }
}


void clear_radiation_state(uint cell) {
    for (uint group = 0u; group < groups(); ++group) {
        opacity_group[group_index(cell, group)] = 0.0;
        emission_group[group_index(cell, group)] = 0.0;
        for (uint angle = 0u; angle < angles(); ++angle) {
            radiation_active[rad_index(cell, group, angle)] = 0.0;
            radiation_scratch[rad_index(cell, group, angle)] = 0.0;
        }
    }
}


void main() {
    uint cell = gl_GlobalInvocationID.x;
    if (cell >= cells()) return;
    uint mode = rounded(pc.mode);
    if (mode == 5u) {
        if ((status[0].x & STATUS_STEP_REJECTED) == 0u) validate_moving_frame(cell);
        return;
    }
    if ((status[0].x & STATUS_STEP_REJECTED) != 0u) return;
    // MAX_GROUPS/MAX_ANGLES size the per-cell caches inside the modes below.
    // The engine refuses to start unless the hash-checked model JSON supplies
    // exactly 24 groups and 26 ordinates (cassi_physical_matter_engine.gd layout
    // checks), so this is a fail-closed guard for that contract rather than a
    // reachable path: exceeding the bound would otherwise write past the caches.
    if (int(groups()) > MAX_GROUPS || int(angles()) > MAX_ANGLES) {
        atomicOr(status[0].x, STATUS_MOVING_FRAME_DOMAIN);
        atomicAdd(status[1].w, 1u);
        return;
    }
    if (mode == 0u) apply_radiation_source(cell, pc.source_enabled > 0.5);
    else if (mode == 1u) remap_moving_frame(cell);
    else if (mode == 2u) accumulate_spatial_escape(cell);
    else if (mode == 3u) clear_radiation_state(cell);
    else if (mode == 4u) publish_coefficients(cell);
    else if (mode == 6u) apply_radiation_source(cell, false);
    else if (mode == 7u) apply_heating_event(cell);
}
