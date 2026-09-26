#[compute]
#version 450

// Default-off supplied-material radiation kernel.  The canonical state is
// extensive: material mass/internal energy/volume and one energy per group.
// Modes 0/1 form the shared-edge affine-frequency transaction; mode 2 is the
// implicit LTE absorption/emission transaction.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer MaterialState {
    vec4 material[]; // mass_kg, internal_energy_J, volume_m3, reserved
};
layout(set = 0, binding = 1, std430) readonly buffer ExpansionState {
    float expansion_rate[]; // isotropic H [s^-1]
};
layout(set = 0, binding = 2, std430) buffer RadiationState {
    float radiation_energy[]; // element-major, group-minor [J]
};
layout(set = 0, binding = 3, std430) readonly buffer FrequencyEdges {
    float frequency_edges[]; // [Hz], group_count + 1
};
layout(set = 0, binding = 4, std430) buffer SharedEdgeFlux {
    float edge_flux[]; // element-major, group-edge-minor [J m^-3 s^-1]
};
layout(set = 0, binding = 5, std430) readonly buffer AbsorptionCoefficients {
    float absorption[]; // [m^-1]
};
layout(set = 0, binding = 6, std430) readonly buffer TemperatureGrid {
    float temperature_grid[]; // [K]
};
layout(set = 0, binding = 7, std430) readonly buffer LteEnergyTable {
    float lte_energy_density[]; // temperature-major, group-minor [J m^-3]
};
layout(set = 0, binding = 8, std430) buffer PhysicalLedger {
    vec4 ledger[]; // low escape, high escape, radiation pressure work, material gain [J]
};
layout(set = 0, binding = 9, std430) buffer PhysicalStatus {
    uint status[]; // bit 0 state/frequency, bit 1 source bracket, bit 2 source state
};

layout(push_constant, std430) uniform Params {
    uint element_count;
    uint group_count;
    uint temperature_count;
    uint mode;
    float dt_s;
    float c_light_m_s;
    float gamma;
    float specific_heat_j_kg_k;
    uint source_iterations;
    uint affine_enabled;
    uint frequency_enabled;
    uint source_enabled;
    float temperature_min_k;
    float temperature_max_k;
    float pad0;
    float pad1;
} pc;

bool finite_positive(float value) {
    return !isnan(value) && !isinf(value) && value > 0.0;
}

float lte_at(float temperature_k, uint group) {
    uint upper = 1u;
    while (upper + 1u < pc.temperature_count && temperature_grid[upper] < temperature_k) {
        upper += 1u;
    }
    uint lower = upper - 1u;
    float t0 = temperature_grid[lower];
    float t1 = temperature_grid[upper];
    float mix_value = clamp((temperature_k - t0) / max(t1 - t0, 1.0e-30), 0.0, 1.0);
    float e0 = lte_energy_density[lower * pc.group_count + group];
    float e1 = lte_energy_density[upper * pc.group_count + group];
    return mix(e0, e1, mix_value);
}

float source_residual(uint element, float temperature_k, float total_energy_j,
                      float heat_capacity_j_k, float volume_m3) {
    float value = heat_capacity_j_k * temperature_k - total_energy_j;
    uint base = element * pc.group_count;
    for (uint group = 0u; group < pc.group_count; group += 1u) {
        float lambda_g = pc.c_light_m_s * absorption[group] * pc.dt_s;
        float old_group = radiation_energy[base + group];
        float equilibrium = volume_m3 * lte_at(temperature_k, group);
        value += (old_group + lambda_g * equilibrium) / (1.0 + lambda_g);
    }
    return value;
}

void build_edge_flux(uint linear_id) {
    uint edge_count = pc.group_count + 1u;
    uint element = linear_id / edge_count;
    uint edge = linear_id - element * edge_count;
    if (element >= pc.element_count) {
        return;
    }
    uint output_index = element * edge_count + edge;
    float h = expansion_rate[element];
    if (pc.frequency_enabled == 0u || h == 0.0 || pc.dt_s == 0.0) {
        edge_flux[output_index] = 0.0;
        return;
    }
    float volume = material[element].z;
    if (!finite_positive(volume) || isnan(h) || isinf(h)) {
        atomicOr(status[element], 1u);
        edge_flux[output_index] = 0.0;
        return;
    }
    int source_group = -1;
    if (edge == 0u) {
        source_group = h > 0.0 ? 0 : -1;
    } else if (edge == pc.group_count) {
        source_group = h < 0.0 ? int(pc.group_count) - 1 : -1;
    } else {
        source_group = h > 0.0 ? int(edge) : int(edge) - 1;
    }
    if (source_group < 0) {
        edge_flux[output_index] = 0.0;
        return;
    }
    uint group = uint(source_group);
    float width_hz = frequency_edges[group + 1u] - frequency_edges[group];
    float energy_j = radiation_energy[element * pc.group_count + group];
    if (!finite_positive(width_hz) || energy_j < 0.0 || isnan(energy_j) || isinf(energy_j)) {
        atomicOr(status[element], 1u);
        edge_flux[output_index] = 0.0;
        return;
    }
    float spectral_density = energy_j / (volume * width_hz);
    edge_flux[output_index] = -h * frequency_edges[edge] * spectral_density;
}

void update_affine_frequency(uint element) {
    if (element >= pc.element_count || status[element] != 0u || pc.affine_enabled == 0u) {
        return;
    }
    float h = expansion_rate[element];
    if (h == 0.0 || pc.dt_s == 0.0) {
        return;
    }
    vec4 old_material = material[element];
    if (!finite_positive(old_material.x) || !finite_positive(old_material.y)
            || !finite_positive(old_material.z) || isnan(h) || isinf(h)) {
        atomicOr(status[element], 1u);
        return;
    }

    float updated_groups[32];
    float radiation_sum = 0.0;
    uint radiation_base = element * pc.group_count;
    uint edge_base = element * (pc.group_count + 1u);
    if (pc.frequency_enabled != 0u) {
        for (uint group = 0u; group < pc.group_count; group += 1u) {
            float old_group = radiation_energy[radiation_base + group];
            float next_group = old_group
                - pc.dt_s * h * old_group
                - pc.dt_s * old_material.z
                    * (edge_flux[edge_base + group + 1u] - edge_flux[edge_base + group]);
            if (next_group < 0.0 || isnan(next_group) || isinf(next_group)) {
                atomicOr(status[element], 1u);
                return;
            }
            updated_groups[group] = next_group;
            radiation_sum += old_group;
        }
    }

    float next_internal = old_material.y
        * exp(-3.0 * h * (pc.gamma - 1.0) * pc.dt_s);
    float next_volume = old_material.z * exp(3.0 * h * pc.dt_s);
    if (!finite_positive(next_internal) || !finite_positive(next_volume)) {
        atomicOr(status[element], 1u);
        return;
    }
    if (pc.frequency_enabled != 0u) {
        for (uint group = 0u; group < pc.group_count; group += 1u) {
            radiation_energy[radiation_base + group] = updated_groups[group];
        }
        float low_escape = max(0.0, -pc.dt_s * old_material.z * edge_flux[edge_base]);
        float high_escape = max(0.0,
            pc.dt_s * old_material.z * edge_flux[edge_base + pc.group_count]);
        ledger[element].x += low_escape;
        ledger[element].y += high_escape;
        ledger[element].z += -pc.dt_s * h * radiation_sum;
    }
    material[element].y = next_internal;
    material[element].z = next_volume;
}

void update_implicit_source(uint element) {
    if (element >= pc.element_count || status[element] != 0u
            || pc.source_enabled == 0u || pc.dt_s == 0.0) {
        return;
    }
    bool has_absorption = false;
    for (uint group = 0u; group < pc.group_count; group += 1u) {
        has_absorption = has_absorption || absorption[group] > 0.0;
    }
    if (!has_absorption) {
        return;
    }

    vec4 state = material[element];
    float heat_capacity = state.x * pc.specific_heat_j_kg_k;
    if (!finite_positive(state.x) || !finite_positive(state.y) || !finite_positive(state.z)
            || !finite_positive(heat_capacity)) {
        atomicOr(status[element], 4u);
        return;
    }
    uint base = element * pc.group_count;
    float total_energy = state.y;
    for (uint group = 0u; group < pc.group_count; group += 1u) {
        float old_group = radiation_energy[base + group];
        if (old_group < 0.0 || isnan(old_group) || isinf(old_group)) {
            atomicOr(status[element], 4u);
            return;
        }
        total_energy += old_group;
    }

    float lower = pc.temperature_min_k;
    float upper = pc.temperature_max_k;
    float residual_lower = source_residual(element, lower, total_energy, heat_capacity, state.z);
    float residual_upper = source_residual(element, upper, total_energy, heat_capacity, state.z);
    if (residual_lower > 0.0 || residual_upper < 0.0
            || isnan(residual_lower) || isnan(residual_upper)) {
        atomicOr(status[element], 2u);
        return;
    }
    for (uint iteration = 0u; iteration < pc.source_iterations; iteration += 1u) {
        float middle = 0.5 * (lower + upper);
        float residual_middle = source_residual(
            element, middle, total_energy, heat_capacity, state.z);
        if (residual_middle > 0.0) {
            upper = middle;
        } else {
            lower = middle;
        }
    }
    float solved_temperature = 0.5 * (lower + upper);
    float updated_groups[32];
    float radiation_sum = 0.0;
    for (uint group = 0u; group < pc.group_count; group += 1u) {
        float lambda_g = pc.c_light_m_s * absorption[group] * pc.dt_s;
        float equilibrium = state.z * lte_at(solved_temperature, group);
        float next_group = (radiation_energy[base + group] + lambda_g * equilibrium)
            / (1.0 + lambda_g);
        if (next_group < 0.0 || isnan(next_group) || isinf(next_group)) {
            atomicOr(status[element], 4u);
            return;
        }
        updated_groups[group] = next_group;
        radiation_sum += next_group;
    }
    float next_internal = total_energy - radiation_sum;
    if (!finite_positive(next_internal)) {
        atomicOr(status[element], 4u);
        return;
    }
    for (uint group = 0u; group < pc.group_count; group += 1u) {
        radiation_energy[base + group] = updated_groups[group];
    }
    material[element].y = next_internal;
    ledger[element].w += next_internal - state.y;
}

void main() {
    uint linear_id = gl_GlobalInvocationID.x;
    if (pc.mode == 0u) {
        build_edge_flux(linear_id);
    } else if (pc.mode == 1u) {
        update_affine_frequency(linear_id);
    } else if (pc.mode == 2u) {
        update_implicit_source(linear_id);
    }
}
