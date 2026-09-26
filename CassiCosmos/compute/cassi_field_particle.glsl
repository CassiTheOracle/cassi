#[compute]
#version 450

// PA12 field-particle evolution. The canonical matter state is the complete
// 18-scalar field at each Cartesian cell:
//   Psi(C^2), Phi(R^3), chi_C(C), A_x/A_y/A_z(su(2)).
// The 16 second-order coordinates have separate velocities; chi_C uses the
// first-order canonical flow. Pass 0 differentiates the exact discrete
// Hamiltonian analytically. Passes 1--4 accumulate one coupled classical RK4
// update; passes 5/6 are explicit unmasked gradient references.

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer StateIn {
    float state_in[];
};
layout(set = 0, binding = 1, std430) readonly buffer VelocityIn {
    float velocity_in[];
};
layout(set = 0, binding = 2, std430) buffer StateOut {
    float state_out[];
};
layout(set = 0, binding = 3, std430) buffer VelocityOut {
    float velocity_out[];
};
layout(set = 0, binding = 4, std430) buffer HamiltonianGradient {
    float h_gradient[];
};
layout(set = 0, binding = 5, std430) readonly buffer StateBase {
    float state_base_values[];
};
layout(set = 0, binding = 6, std430) readonly buffer VelocityBase {
    float velocity_base_values[];
};
layout(set = 0, binding = 7, std430) buffer StateAccumulator {
    float state_accumulator[];
};
layout(set = 0, binding = 8, std430) buffer VelocityAccumulator {
    float velocity_accumulator[];
};

layout(push_constant, std430) uniform Params {
    uint N;
    float dt;
    float dx;
    float fd_epsilon;

    float phi;
    float u_rho;
    float u_phi;
    float gamma_x;

    float u_h;
    float k_cx;
    float e_c;
    float h_c;

    float u_c;
    float c_psi;
    float c_h;
    float e_tx;

    uint pass_sel;
} pc;

const int STATE_STRIDE = 18;
const int VELOCITY_STRIDE = 16;

const int PSI0_RE = 0;
const int PSI0_IM = 1;
const int PSI1_RE = 2;
const int PSI1_IM = 3;
const int H0 = 4;
const int H1 = 5;
const int H2 = 6;
const int CHI_RE = 7;
const int CHI_IM = 8;
const int AX0 = 9;

int cell_index(ivec3 p) {
    return p.x + int(pc.N) * (p.y + int(pc.N) * p.z);
}

ivec3 cell_position(int id) {
    int n = int(pc.N);
    int z = id / (n * n);
    int rem = id - z * n * n;
    int y = rem / n;
    return ivec3(rem - y * n, y, z);
}

bool is_boundary(ivec3 p) {
    int last = int(pc.N) - 1;
    return p.x == 0 || p.y == 0 || p.z == 0 ||
           p.x == last || p.y == last || p.z == last;
}

ivec3 axis_shift(ivec3 p, int axis, int amount) {
    if (axis == 0) {
        p.x += amount;
    } else if (axis == 1) {
        p.y += amount;
    } else {
        p.z += amount;
    }
    return p;
}

int axis_coordinate(ivec3 p, int axis) {
    return axis == 0 ? p.x : (axis == 1 ? p.y : p.z);
}

float sample_component(
    ivec3 p,
    int component,
    int perturbed_cell,
    int perturbed_component,
    float perturbation
) {
    int id = cell_index(p);
    float value = state_in[id * STATE_STRIDE + component];
    if (id == perturbed_cell && component == perturbed_component) {
        value += perturbation;
    }
    return value;
}

vec2 sample_complex(
    ivec3 p,
    int real_component,
    int perturbed_cell,
    int perturbed_component,
    float perturbation
) {
    return vec2(
        sample_component(p, real_component, perturbed_cell, perturbed_component, perturbation),
        sample_component(p, real_component + 1, perturbed_cell, perturbed_component, perturbation)
    );
}

vec3 sample_vector(
    ivec3 p,
    int first_component,
    int perturbed_cell,
    int perturbed_component,
    float perturbation
) {
    return vec3(
        sample_component(p, first_component, perturbed_cell, perturbed_component, perturbation),
        sample_component(p, first_component + 1, perturbed_cell, perturbed_component, perturbation),
        sample_component(p, first_component + 2, perturbed_cell, perturbed_component, perturbation)
    );
}

float derivative_component(
    ivec3 p,
    int component,
    int axis,
    int perturbed_cell,
    int perturbed_component,
    float perturbation
) {
    int coordinate = axis_coordinate(p, axis);
    int last = int(pc.N) - 1;
    float inv_2dx = 0.5 / pc.dx;
    if (coordinate == 0) {
        float f0 = sample_component(p, component, perturbed_cell, perturbed_component, perturbation);
        float f1 = sample_component(axis_shift(p, axis, 1), component, perturbed_cell, perturbed_component, perturbation);
        float f2 = sample_component(axis_shift(p, axis, 2), component, perturbed_cell, perturbed_component, perturbation);
        return (-3.0 * f0 + 4.0 * f1 - f2) * inv_2dx;
    }
    if (coordinate == last) {
        float f0 = sample_component(p, component, perturbed_cell, perturbed_component, perturbation);
        float f1 = sample_component(axis_shift(p, axis, -1), component, perturbed_cell, perturbed_component, perturbation);
        float f2 = sample_component(axis_shift(p, axis, -2), component, perturbed_cell, perturbed_component, perturbation);
        return (3.0 * f0 - 4.0 * f1 + f2) * inv_2dx;
    }
    float plus = sample_component(axis_shift(p, axis, 1), component, perturbed_cell, perturbed_component, perturbation);
    float minus = sample_component(axis_shift(p, axis, -1), component, perturbed_cell, perturbed_component, perturbation);
    return (plus - minus) * inv_2dx;
}

vec2 derivative_complex(
    ivec3 p,
    int real_component,
    int axis,
    int perturbed_cell,
    int perturbed_component,
    float perturbation
) {
    return vec2(
        derivative_component(p, real_component, axis, perturbed_cell, perturbed_component, perturbation),
        derivative_component(p, real_component + 1, axis, perturbed_cell, perturbed_component, perturbation)
    );
}

vec3 derivative_vector(
    ivec3 p,
    int first_component,
    int axis,
    int perturbed_cell,
    int perturbed_component,
    float perturbation
) {
    return vec3(
        derivative_component(p, first_component, axis, perturbed_cell, perturbed_component, perturbation),
        derivative_component(p, first_component + 1, axis, perturbed_cell, perturbed_component, perturbation),
        derivative_component(p, first_component + 2, axis, perturbed_cell, perturbed_component, perturbation)
    );
}

vec2 multiply_i(vec2 z) {
    return vec2(-z.y, z.x);
}

vec2 multiply_minus_i(vec2 z) {
    return vec2(z.y, -z.x);
}

float complex_norm2(vec2 z) {
    return dot(z, z);
}

void gauge_action(
    vec3 gauge,
    vec2 psi0,
    vec2 psi1,
    out vec2 result0,
    out vec2 result1
) {
    // (gauge . sigma/2) Psi in the real/imaginary representation.
    result0 = 0.5 * (gauge.x * psi1 + gauge.y * multiply_minus_i(psi1) + gauge.z * psi0);
    result1 = 0.5 * (gauge.x * psi0 + gauge.y * multiply_i(psi0) - gauge.z * psi1);
}

float energy_density(
    ivec3 p,
    int perturbed_cell,
    int perturbed_component,
    float perturbation
) {
    vec2 psi0 = sample_complex(p, PSI0_RE, perturbed_cell, perturbed_component, perturbation);
    vec2 psi1 = sample_complex(p, PSI1_RE, perturbed_cell, perturbed_component, perturbation);
    vec3 h = sample_vector(p, H0, perturbed_cell, perturbed_component, perturbation);
    vec2 chi = sample_complex(p, CHI_RE, perturbed_cell, perturbed_component, perturbation);

    float rho = complex_norm2(psi0) + complex_norm2(psi1);
    vec3 spin = vec3(
        2.0 * (psi0.x * psi1.x + psi0.y * psi1.y),
        2.0 * (psi0.x * psi1.y - psi0.y * psi1.x),
        complex_norm2(psi0) - complex_norm2(psi1)
    );
    float delta_phi = 0.5 * ((1.0 - pc.phi) * rho + (1.0 + pc.phi) * dot(h, spin));

    float result = 0.25 * pc.u_rho * (rho - 1.0) * (rho - 1.0);
    result += 0.5 * pc.u_phi * delta_phi * delta_phi;
    float h_norm_error = dot(h, h) - 1.0;
    result += 0.25 * pc.u_h * h_norm_error * h_norm_error;

    float chi_density = complex_norm2(chi);
    result += (pc.e_c - pc.h_c * (1.0 - rho)) * chi_density;
    result += 0.5 * pc.u_c * chi_density * chi_density;

    vec3 gauge[3];
    gauge[0] = sample_vector(p, AX0, perturbed_cell, perturbed_component, perturbation);
    gauge[1] = sample_vector(p, AX0 + 3, perturbed_cell, perturbed_component, perturbation);
    gauge[2] = sample_vector(p, AX0 + 6, perturbed_cell, perturbed_component, perturbation);

    for (int axis = 0; axis < 3; axis++) {
        vec2 dpsi0 = derivative_complex(p, PSI0_RE, axis, perturbed_cell, perturbed_component, perturbation);
        vec2 dpsi1 = derivative_complex(p, PSI1_RE, axis, perturbed_cell, perturbed_component, perturbation);
        vec2 gauge_psi0;
        vec2 gauge_psi1;
        gauge_action(gauge[axis], psi0, psi1, gauge_psi0, gauge_psi1);
        vec2 covariant0 = dpsi0 + multiply_minus_i(gauge_psi0);
        vec2 covariant1 = dpsi1 + multiply_minus_i(gauge_psi1);
        result += 0.5 * (complex_norm2(covariant0) + complex_norm2(covariant1));

        vec3 dh = derivative_vector(p, H0, axis, perturbed_cell, perturbed_component, perturbation);
        vec3 covariant_h = dh + cross(gauge[axis], h);
        result += 0.5 * pc.gamma_x * dot(covariant_h, covariant_h);

        vec2 dchi = derivative_complex(p, CHI_RE, axis, perturbed_cell, perturbed_component, perturbation);
        result += 0.5 * pc.k_cx * complex_norm2(dchi);
    }

    // gamma_x/4 * sum_{i,j}|F_ij|^2 = gamma_x/2 * sum_{i<j}|F_ij|^2.
    for (int i = 0; i < 3; i++) {
        for (int j = i + 1; j < 3; j++) {
            vec3 d_i_a_j = derivative_vector(p, AX0 + 3 * j, i, perturbed_cell, perturbed_component, perturbation);
            vec3 d_j_a_i = derivative_vector(p, AX0 + 3 * i, j, perturbed_cell, perturbed_component, perturbation);
            vec3 curvature = d_i_a_j - d_j_a_i + cross(gauge[i], gauge[j]);
            result += 0.5 * pc.gamma_x * dot(curvature, curvature);
        }
    }
    return result;
}

float component_variation(
    ivec3 center,
    int component,
    int target_cell,
    int target_component
) {
    return cell_index(center) == target_cell && component == target_component ? 1.0 : 0.0;
}

float stencil_weight(ivec3 center, int axis, int target_cell) {
    ivec3 target = cell_position(target_cell);
    if (axis == 0 && (center.y != target.y || center.z != target.z)) {
        return 0.0;
    }
    if (axis == 1 && (center.x != target.x || center.z != target.z)) {
        return 0.0;
    }
    if (axis == 2 && (center.x != target.x || center.y != target.y)) {
        return 0.0;
    }
    int coordinate = axis_coordinate(center, axis);
    int target_coordinate = axis_coordinate(target, axis);
    int last = int(pc.N) - 1;
    float inv_2dx = 0.5 / pc.dx;
    if (coordinate == 0) {
        if (target_coordinate == coordinate) {
            return -3.0 * inv_2dx;
        }
        if (target_coordinate == coordinate + 1) {
            return 4.0 * inv_2dx;
        }
        if (target_coordinate == coordinate + 2) {
            return -inv_2dx;
        }
        return 0.0;
    }
    if (coordinate == last) {
        if (target_coordinate == coordinate) {
            return 3.0 * inv_2dx;
        }
        if (target_coordinate == coordinate - 1) {
            return -4.0 * inv_2dx;
        }
        if (target_coordinate == coordinate - 2) {
            return inv_2dx;
        }
        return 0.0;
    }
    if (target_coordinate == coordinate + 1) {
        return inv_2dx;
    }
    if (target_coordinate == coordinate - 1) {
        return -inv_2dx;
    }
    return 0.0;
}

vec2 variation_complex(
    ivec3 center,
    int real_component,
    int target_cell,
    int target_component
) {
    return vec2(
        component_variation(center, real_component, target_cell, target_component),
        component_variation(center, real_component + 1, target_cell, target_component)
    );
}

vec3 variation_vector(
    ivec3 center,
    int first_component,
    int target_cell,
    int target_component
) {
    return vec3(
        component_variation(center, first_component, target_cell, target_component),
        component_variation(center, first_component + 1, target_cell, target_component),
        component_variation(center, first_component + 2, target_cell, target_component)
    );
}

vec2 derivative_variation_complex(
    ivec3 center,
    int real_component,
    int axis,
    int target_cell,
    int target_component
) {
    float weight = stencil_weight(center, axis, target_cell);
    return vec2(
        weight * (real_component == target_component ? 1.0 : 0.0),
        weight * (real_component + 1 == target_component ? 1.0 : 0.0)
    );
}

vec3 derivative_variation_vector(
    ivec3 center,
    int first_component,
    int axis,
    int target_cell,
    int target_component
) {
    float weight = stencil_weight(center, axis, target_cell);
    return vec3(
        weight * (first_component == target_component ? 1.0 : 0.0),
        weight * (first_component + 1 == target_component ? 1.0 : 0.0),
        weight * (first_component + 2 == target_component ? 1.0 : 0.0)
    );
}

void gauge_action_variation(
    vec3 gauge,
    vec3 gauge_variation,
    vec2 psi0,
    vec2 psi0_variation,
    vec2 psi1,
    vec2 psi1_variation,
    out vec2 result0,
    out vec2 result1
) {
    result0 = 0.5 * (
        gauge_variation.x * psi1 + gauge.x * psi1_variation +
        gauge_variation.y * multiply_minus_i(psi1) + gauge.y * multiply_minus_i(psi1_variation) +
        gauge_variation.z * psi0 + gauge.z * psi0_variation);
    result1 = 0.5 * (
        gauge_variation.x * psi0 + gauge.x * psi0_variation +
        gauge_variation.y * multiply_i(psi0) + gauge.y * multiply_i(psi0_variation) -
        gauge_variation.z * psi1 - gauge.z * psi1_variation);
}

float analytic_derivative_shell_gradient(
    ivec3 p,
    int target_cell,
    int target_component
) {
    float result = 0.0;
    if (target_component <= PSI1_IM) {
        vec2 psi0 = sample_complex(p, PSI0_RE, target_cell, target_component, 0.0);
        vec2 psi1 = sample_complex(p, PSI1_RE, target_cell, target_component, 0.0);
        vec3 gauge[3];
        gauge[0] = sample_vector(p, AX0, target_cell, target_component, 0.0);
        gauge[1] = sample_vector(p, AX0 + 3, target_cell, target_component, 0.0);
        gauge[2] = sample_vector(p, AX0 + 6, target_cell, target_component, 0.0);
        for (int axis = 0; axis < 3; axis++) {
            vec2 dpsi0 = derivative_complex(p, PSI0_RE, axis, target_cell, target_component, 0.0);
            vec2 dpsi1 = derivative_complex(p, PSI1_RE, axis, target_cell, target_component, 0.0);
            vec2 gauge_psi0;
            vec2 gauge_psi1;
            gauge_action(gauge[axis], psi0, psi1, gauge_psi0, gauge_psi1);
            vec2 d_dpsi0 = derivative_variation_complex(
                p, PSI0_RE, axis, target_cell, target_component);
            vec2 d_dpsi1 = derivative_variation_complex(
                p, PSI1_RE, axis, target_cell, target_component);
            result += dot(
                dpsi0 + multiply_minus_i(gauge_psi0), d_dpsi0);
            result += dot(
                dpsi1 + multiply_minus_i(gauge_psi1), d_dpsi1);
        }
        return result;
    }
    if (target_component <= H2) {
        vec3 h = sample_vector(p, H0, target_cell, target_component, 0.0);
        vec3 gauge[3];
        gauge[0] = sample_vector(p, AX0, target_cell, target_component, 0.0);
        gauge[1] = sample_vector(p, AX0 + 3, target_cell, target_component, 0.0);
        gauge[2] = sample_vector(p, AX0 + 6, target_cell, target_component, 0.0);
        for (int axis = 0; axis < 3; axis++) {
            vec3 dh = derivative_vector(p, H0, axis, target_cell, target_component, 0.0);
            vec3 d_dh = derivative_variation_vector(
                p, H0, axis, target_cell, target_component);
            result += pc.gamma_x * dot(
                dh + cross(gauge[axis], h), d_dh);
        }
        return result;
    }
    if (target_component <= CHI_IM) {
        for (int axis = 0; axis < 3; axis++) {
            vec2 dchi = derivative_complex(p, CHI_RE, axis, target_cell, target_component, 0.0);
            vec2 d_dchi = derivative_variation_complex(
                p, CHI_RE, axis, target_cell, target_component);
            result += pc.k_cx * dot(dchi, d_dchi);
        }
        return result;
    }
    vec3 gauge[3];
    gauge[0] = sample_vector(p, AX0, target_cell, target_component, 0.0);
    gauge[1] = sample_vector(p, AX0 + 3, target_cell, target_component, 0.0);
    gauge[2] = sample_vector(p, AX0 + 6, target_cell, target_component, 0.0);
    for (int i = 0; i < 3; i++) {
        for (int j = i + 1; j < 3; j++) {
            vec3 d_i_a_j = derivative_vector(
                p, AX0 + 3 * j, i, target_cell, target_component, 0.0);
            vec3 d_j_a_i = derivative_vector(
                p, AX0 + 3 * i, j, target_cell, target_component, 0.0);
            vec3 d_d_i_a_j = derivative_variation_vector(
                p, AX0 + 3 * j, i, target_cell, target_component);
            vec3 d_d_j_a_i = derivative_variation_vector(
                p, AX0 + 3 * i, j, target_cell, target_component);
            vec3 curvature = d_i_a_j - d_j_a_i + cross(gauge[i], gauge[j]);
            vec3 curvature_variation = d_d_i_a_j - d_d_j_a_i;
            result += pc.gamma_x * dot(curvature, curvature_variation);
        }
    }
    return result;
}

float analytic_density_gradient(
    ivec3 p,
    int target_cell,
    int target_component
) {
    if (cell_index(p) != target_cell) {
        return analytic_derivative_shell_gradient(p, target_cell, target_component);
    }
    vec2 psi0 = sample_complex(p, PSI0_RE, target_cell, target_component, 0.0);
    vec2 psi1 = sample_complex(p, PSI1_RE, target_cell, target_component, 0.0);
    vec3 h = sample_vector(p, H0, target_cell, target_component, 0.0);
    vec2 chi = sample_complex(p, CHI_RE, target_cell, target_component, 0.0);
    vec2 psi0_variation = variation_complex(p, PSI0_RE, target_cell, target_component);
    vec2 psi1_variation = variation_complex(p, PSI1_RE, target_cell, target_component);
    vec3 h_variation = variation_vector(p, H0, target_cell, target_component);
    vec2 chi_variation = variation_complex(p, CHI_RE, target_cell, target_component);

    float rho = complex_norm2(psi0) + complex_norm2(psi1);
    float rho_variation = 2.0 * (dot(psi0, psi0_variation) + dot(psi1, psi1_variation));
    vec3 spin = vec3(
        2.0 * (psi0.x * psi1.x + psi0.y * psi1.y),
        2.0 * (psi0.x * psi1.y - psi0.y * psi1.x),
        complex_norm2(psi0) - complex_norm2(psi1)
    );
    vec3 spin_variation = vec3(
        2.0 * (psi0_variation.x * psi1.x + psi0.x * psi1_variation.x +
               psi0_variation.y * psi1.y + psi0.y * psi1_variation.y),
        2.0 * (psi0_variation.x * psi1.y + psi0.x * psi1_variation.y -
               psi0_variation.y * psi1.x - psi0.y * psi1_variation.x),
        2.0 * (dot(psi0, psi0_variation) - dot(psi1, psi1_variation))
    );
    float delta_phi = 0.5 * ((1.0 - pc.phi) * rho + (1.0 + pc.phi) * dot(h, spin));
    float delta_phi_variation = 0.5 * (
        (1.0 - pc.phi) * rho_variation +
        (1.0 + pc.phi) * (dot(h_variation, spin) + dot(h, spin_variation)));
    float result = 0.5 * pc.u_rho * (rho - 1.0) * rho_variation;
    result += pc.u_phi * delta_phi * delta_phi_variation;
    float h_norm_error = dot(h, h) - 1.0;
    result += pc.u_h * h_norm_error * dot(h, h_variation);

    float chi_density = complex_norm2(chi);
    float chi_density_variation = 2.0 * dot(chi, chi_variation);
    float chi_potential = pc.e_c - pc.h_c * (1.0 - rho);
    result += pc.h_c * chi_density * rho_variation;
    result += chi_potential * chi_density_variation;
    result += 2.0 * pc.u_c * chi_density * dot(chi, chi_variation);

    vec3 gauge[3];
    vec3 gauge_variation[3];
    gauge[0] = sample_vector(p, AX0, target_cell, target_component, 0.0);
    gauge[1] = sample_vector(p, AX0 + 3, target_cell, target_component, 0.0);
    gauge[2] = sample_vector(p, AX0 + 6, target_cell, target_component, 0.0);
    gauge_variation[0] = variation_vector(p, AX0, target_cell, target_component);
    gauge_variation[1] = variation_vector(p, AX0 + 3, target_cell, target_component);
    gauge_variation[2] = variation_vector(p, AX0 + 6, target_cell, target_component);

    for (int axis = 0; axis < 3; axis++) {
        vec2 dpsi0 = derivative_complex(p, PSI0_RE, axis, target_cell, target_component, 0.0);
        vec2 dpsi1 = derivative_complex(p, PSI1_RE, axis, target_cell, target_component, 0.0);
        vec2 d_dpsi0 = derivative_variation_complex(
            p, PSI0_RE, axis, target_cell, target_component);
        vec2 d_dpsi1 = derivative_variation_complex(
            p, PSI1_RE, axis, target_cell, target_component);
        vec2 gauge_psi0;
        vec2 gauge_psi1;
        vec2 gauge_psi0_variation;
        vec2 gauge_psi1_variation;
        gauge_action(gauge[axis], psi0, psi1, gauge_psi0, gauge_psi1);
        gauge_action_variation(
            gauge[axis], gauge_variation[axis], psi0, psi0_variation,
            psi1, psi1_variation, gauge_psi0_variation, gauge_psi1_variation);
        vec2 covariant0 = dpsi0 + multiply_minus_i(gauge_psi0);
        vec2 covariant1 = dpsi1 + multiply_minus_i(gauge_psi1);
        vec2 covariant0_variation = d_dpsi0 + multiply_minus_i(gauge_psi0_variation);
        vec2 covariant1_variation = d_dpsi1 + multiply_minus_i(gauge_psi1_variation);
        result += dot(covariant0, covariant0_variation) +
            dot(covariant1, covariant1_variation);

        vec3 dh = derivative_vector(p, H0, axis, target_cell, target_component, 0.0);
        vec3 d_dh = derivative_variation_vector(
            p, H0, axis, target_cell, target_component);
        vec3 covariant_h = dh + cross(gauge[axis], h);
        vec3 covariant_h_variation = d_dh + cross(gauge_variation[axis], h) +
            cross(gauge[axis], h_variation);
        result += pc.gamma_x * dot(covariant_h, covariant_h_variation);

        vec2 dchi = derivative_complex(p, CHI_RE, axis, target_cell, target_component, 0.0);
        vec2 d_dchi = derivative_variation_complex(
            p, CHI_RE, axis, target_cell, target_component);
        result += pc.k_cx * dot(dchi, d_dchi);
    }

    for (int i = 0; i < 3; i++) {
        for (int j = i + 1; j < 3; j++) {
            vec3 d_i_a_j = derivative_vector(
                p, AX0 + 3 * j, i, target_cell, target_component, 0.0);
            vec3 d_j_a_i = derivative_vector(
                p, AX0 + 3 * i, j, target_cell, target_component, 0.0);
            vec3 d_d_i_a_j = derivative_variation_vector(
                p, AX0 + 3 * j, i, target_cell, target_component);
            vec3 d_d_j_a_i = derivative_variation_vector(
                p, AX0 + 3 * i, j, target_cell, target_component);
            vec3 curvature = d_i_a_j - d_j_a_i + cross(gauge[i], gauge[j]);
            vec3 curvature_variation = d_d_i_a_j - d_d_j_a_i +
                cross(gauge_variation[i], gauge[j]) +
                cross(gauge[i], gauge_variation[j]);
            result += pc.gamma_x * dot(curvature, curvature_variation);
        }
    }
    return result;
}

float density_gradient_numeric(
    ivec3 center,
    int target_cell,
    int target_component,
    float epsilon
) {
    float plus_two = energy_density(center, target_cell, target_component, 2.0 * epsilon);
    float plus_one = energy_density(center, target_cell, target_component, epsilon);
    float minus_one = energy_density(center, target_cell, target_component, -epsilon);
    float minus_two = energy_density(center, target_cell, target_component, -2.0 * epsilon);
    return (-plus_two + 8.0 * plus_one - 8.0 * minus_one + minus_two) /
        (12.0 * epsilon);
}

float discrete_hamiltonian_gradient_analytic(int target_cell, int target_component) {
    ivec3 target = cell_position(target_cell);
    float result = analytic_density_gradient(target, target_cell, target_component);
    int n = int(pc.N);
    for (int axis = 0; axis < 3; axis++) {
        for (int offset = -2; offset <= 2; offset++) {
            if (offset == 0) {
                continue;
            }
            int coordinate = axis_coordinate(target, axis) + offset;
            if (coordinate >= 0 && coordinate < n) {
                result += analytic_density_gradient(
                    axis_shift(target, axis, offset), target_cell, target_component);
            }
        }
    }
    return result * pc.dx * pc.dx * pc.dx;
}

float discrete_hamiltonian_gradient_numeric(int target_cell, int target_component) {
    ivec3 target = cell_position(target_cell);
    float value = state_in[target_cell * STATE_STRIDE + target_component];
    float epsilon = pc.fd_epsilon * max(1.0, abs(value));
    float result = density_gradient_numeric(target, target_cell, target_component, epsilon);
    int n = int(pc.N);
    for (int axis = 0; axis < 3; axis++) {
        for (int offset = -2; offset <= 2; offset++) {
            if (offset == 0) {
                continue;
            }
            int coordinate = axis_coordinate(target, axis) + offset;
            if (coordinate >= 0 && coordinate < n) {
                result += density_gradient_numeric(
                    axis_shift(target, axis, offset), target_cell, target_component, epsilon);
            }
        }
    }
    return result * pc.dx * pc.dx * pc.dx;
}

float discrete_hamiltonian_gradient(int target_cell, int target_component) {
    return discrete_hamiltonian_gradient_analytic(target_cell, target_component);
}

float discrete_hamiltonian_gradient_reference(int target_cell, int target_component) {
    return discrete_hamiltonian_gradient_numeric(target_cell, target_component);
}

// Pass 0 is the production analytic gradient. Passes 5 and 6 are explicit
// unmasked numeric and analytic reference dispatches for gradient diagnostics.
void differentiate() {
    int work_item = int(gl_GlobalInvocationID.x);
    int cells = int(pc.N * pc.N * pc.N);
    if (work_item >= cells * STATE_STRIDE) {
        return;
    }
    int cell = work_item / STATE_STRIDE;
    int component = work_item - cell * STATE_STRIDE;
    bool reference_dispatch = pc.pass_sel >= 5u;
    if (is_boundary(cell_position(cell)) && !reference_dispatch) {
        h_gradient[work_item] = 0.0;
        return;
    }
    h_gradient[work_item] = pc.pass_sel == 5u
        ? discrete_hamiltonian_gradient_reference(cell, component)
        : discrete_hamiltonian_gradient(cell, component);
}

int velocity_component_for_state(int component) {
    if (component <= H2) {
        return component;
    }
    if (component >= AX0) {
        return 7 + component - AX0;
    }
    return -1;
}


int state_component_for_velocity(int component) {
    return component <= 6 ? component : AX0 + component - 7;
}

float state_rate(int state_base, int velocity_base, int component, float cell_volume) {
    if (component == CHI_RE) {
        return 0.5 * h_gradient[state_base + CHI_IM] / cell_volume;
    }
    if (component == CHI_IM) {
        return -0.5 * h_gradient[state_base + CHI_RE] / cell_volume;
    }
    int velocity_component = velocity_component_for_state(component);
    return velocity_in[velocity_base + velocity_component];
}

float velocity_rate(int state_base, int velocity_component, float cell_volume) {
    int component = state_component_for_velocity(velocity_component);
    float inertia = component <= PSI1_IM ? pc.c_psi :
                    (component <= H2 ? pc.c_h : pc.e_tx);
    return -h_gradient[state_base + component] / (inertia * cell_volume);
}

void integrate_rk4_stage() {
    int cell = int(gl_GlobalInvocationID.x);
    int cells = int(pc.N * pc.N * pc.N);
    if (cell >= cells) {
        return;
    }
    int state_base = cell * STATE_STRIDE;
    int velocity_base = cell * VELOCITY_STRIDE;
    uint stage = pc.pass_sel;

    if (pc.dt == 0.0) {
        for (int component = 0; component < STATE_STRIDE; component++) {
            state_out[state_base + component] = state_base_values[state_base + component];
            if (stage == 1u) {
                state_accumulator[state_base + component] = 0.0;
            }
        }
        for (int component = 0; component < VELOCITY_STRIDE; component++) {
            velocity_out[velocity_base + component] = velocity_base_values[velocity_base + component];
            if (stage == 1u) {
                velocity_accumulator[velocity_base + component] = 0.0;
            }
        }
        return;
    }

    if (is_boundary(cell_position(cell))) {
        for (int component = 0; component < STATE_STRIDE; component++) {
            state_out[state_base + component] = state_base_values[state_base + component];
            if (stage == 1u) {
                state_accumulator[state_base + component] = 0.0;
            }
        }
        for (int component = 0; component < VELOCITY_STRIDE; component++) {
            velocity_out[velocity_base + component] = 0.0;
            if (stage == 1u) {
                velocity_accumulator[velocity_base + component] = 0.0;
            }
        }
        return;
    }

    float cell_volume = pc.dx * pc.dx * pc.dx;
    for (int component = 0; component < STATE_STRIDE; component++) {
        float rate = state_rate(state_base, velocity_base, component, cell_volume);
        if (stage == 1u) {
            state_accumulator[state_base + component] = rate;
            state_out[state_base + component] =
                state_base_values[state_base + component] + 0.5 * pc.dt * rate;
        } else if (stage == 2u) {
            state_accumulator[state_base + component] += 2.0 * rate;
            state_out[state_base + component] =
                state_base_values[state_base + component] + 0.5 * pc.dt * rate;
        } else if (stage == 3u) {
            state_accumulator[state_base + component] += 2.0 * rate;
            state_out[state_base + component] =
                state_base_values[state_base + component] + pc.dt * rate;
        } else {
            float total_rate = state_accumulator[state_base + component] + rate;
            state_out[state_base + component] =
                state_base_values[state_base + component] + (pc.dt / 6.0) * total_rate;
        }
    }
    for (int component = 0; component < VELOCITY_STRIDE; component++) {
        float rate = velocity_rate(state_base, component, cell_volume);
        if (stage == 1u) {
            velocity_accumulator[velocity_base + component] = rate;
            velocity_out[velocity_base + component] =
                velocity_base_values[velocity_base + component] + 0.5 * pc.dt * rate;
        } else if (stage == 2u) {
            velocity_accumulator[velocity_base + component] += 2.0 * rate;
            velocity_out[velocity_base + component] =
                velocity_base_values[velocity_base + component] + 0.5 * pc.dt * rate;
        } else if (stage == 3u) {
            velocity_accumulator[velocity_base + component] += 2.0 * rate;
            velocity_out[velocity_base + component] =
                velocity_base_values[velocity_base + component] + pc.dt * rate;
        } else {
            float total_rate = velocity_accumulator[velocity_base + component] + rate;
            velocity_out[velocity_base + component] =
                velocity_base_values[velocity_base + component] + (pc.dt / 6.0) * total_rate;
        }
    }
}

void main() {
    if (pc.pass_sel == 0u || pc.pass_sel == 5u || pc.pass_sel == 6u) {
        differentiate();
    } else {
        integrate_rk4_stage();
    }
}
