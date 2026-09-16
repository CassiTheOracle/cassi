#[compute]
#version 450

// Dimensionally split finite-volume Euler solver.  MC reconstruction and an
// HLLC contact solve are used where admissible; a first-order HLLE retry is
// applied before a cell is rejected.  Hydrogen populations are conservative
// passive partial mass densities and total energy includes their reservoirs.
layout(local_size_x = 256, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Material0In { vec4 material0_in[]; };
layout(set = 0, binding = 1, std430) readonly buffer Material1In { vec4 material1_in[]; };
layout(set = 0, binding = 2, std430) readonly buffer Population0In { vec4 population0_in[]; };
layout(set = 0, binding = 3, std430) readonly buffer Population1In { vec4 population1_in[]; };
layout(set = 0, binding = 4, std430) buffer Material0Out { vec4 material0_out[]; };
layout(set = 0, binding = 5, std430) buffer Material1Out { vec4 material1_out[]; };
layout(set = 0, binding = 6, std430) buffer Population0Out { vec4 population0_out[]; };
layout(set = 0, binding = 7, std430) buffer Population1Out { vec4 population1_out[]; };
layout(set = 0, binding = 8, std430) readonly buffer Gravity { vec4 gravity_cell[]; };
// ledger1 = (escaped mass, escaped material energy, gravity work, rejected update)
layout(set = 0, binding = 9, std430) buffer Ledger1 { vec4 ledger1[]; };
// ledger2 = signed vector momentum carried through the open boundary
layout(set = 0, binding = 10, std430) buffer Ledger2 { vec4 ledger2[]; };
layout(set = 0, binding = 11, std430) coherent buffer Status { uvec4 status[]; };
layout(set = 0, binding = 12, std430) readonly buffer Levels { vec4 level_data[]; };
layout(set = 0, binding = 13, std430) coherent buffer HydroDebug { uvec4 hydro_debug[]; };

layout(push_constant, std430) uniform PC {
    float axis;
    float nx;
    float ny;
    float nz;
    float extent_x;
    float extent_y;
    float extent_z;
    float dt_sim;
    float gamma_gas;
    float velocity_m_s_per_sim;
    float density_floor;
    float pressure_floor;
    float temperature_min_K;
    float temperature_max_K;
    float length_m_per_sim;
    float time_s_per_sim;
    float pad0;
    float pad1;
    float pad2;
    float pad3;
} pc;

const float K_B = 1.380649e-23;
const float M_H = 1.6735575e-27;
const uint STATUS_HYDRO_NONFINITE = 16u;
const uint STATUS_HYDRO_NEGATIVE = 32u;
const uint STATUS_HYDRO_RETRY = 64u;
const uint STATUS_STEP_REJECTED = 131072u;

struct State {
    vec4 q0; // rho, momentum xyz
    vec4 q1; // total energy, cached temperature, pressure, divergence
    vec4 p0; // H(n=1..4) partial mass densities
    vec4 p1; // H(n=5,6), H+, pad
};
struct Flux {
    vec4 q0;
    vec4 q1;
    vec4 p0;
    vec4 p1;
};
struct Primitive {
    float rho;
    vec3 velocity;
    float pressure;
    float sound;
    bool valid;
};

bool finite_float(float x) { return !(isnan(x) || isinf(x)); }
bool finite_vec3(vec3 x) { return !(any(isnan(x)) || any(isinf(x))); }
bool finite_vec4(vec4 x) { return !(any(isnan(x)) || any(isinf(x))); }
// Same guard as the sibling shaders: a non-finite or negative push constant
// yields a zero dimension instead of an undefined uint conversion.  The engine
// already rejects such geometry, so this only changes behaviour on input the
// engine never dispatches.
uint rounded(float value) { return (!finite_float(value) || value <= 0.0) ? 0u : uint(value + 0.5); }
uvec3 dims() { return uvec3(rounded(pc.nx), rounded(pc.ny), rounded(pc.nz)); }
uint cell_count() { uvec3 d = dims(); return d.x * d.y * d.z; }
uint linear_cell(ivec3 c, uvec3 d) { return uint(c.x) + d.x * (uint(c.y) + d.y * uint(c.z)); }
bool in_domain(ivec3 c, uvec3 d) {
    return all(greaterThanEqual(c, ivec3(0))) && all(lessThan(c, ivec3(d)));
}
ivec3 coordinate(uint gid, uvec3 d) {
    uint plane = d.x * d.y;
    uint z = gid / plane;
    uint rem = gid - z * plane;
    return ivec3(int(rem % d.x), int(rem / d.x), int(z));
}
ivec3 axis_offset(int axis_value) {
    return axis_value == 0 ? ivec3(1, 0, 0) : (axis_value == 1 ? ivec3(0, 1, 0) : ivec3(0, 0, 1));
}
float component(vec3 value, int axis_value) {
    return axis_value == 0 ? value.x : (axis_value == 1 ? value.y : value.z);
}
vec3 set_component(vec3 value, int axis_value, float scalar) {
    if (axis_value == 0) value.x = scalar;
    else if (axis_value == 1) value.y = scalar;
    else value.z = scalar;
    return value;
}
State zero_state() {
    State s;
    s.q0 = vec4(0.0); s.q1 = vec4(0.0); s.p0 = vec4(0.0); s.p1 = vec4(0.0);
    return s;
}
State load_state(ivec3 c, uvec3 d) {
    if (!in_domain(c, d)) return zero_state();
    uint index = linear_cell(c, d);
    State s;
    s.q0 = material0_in[index]; s.q1 = material1_in[index];
    s.p0 = population0_in[index]; s.p1 = population1_in[index];
    return s;
}
State state_add(State a, State b) {
    State r;
    r.q0 = a.q0 + b.q0; r.q1 = vec4(a.q1.x + b.q1.x, 0.0, 0.0, 0.0);
    r.p0 = a.p0 + b.p0; r.p1 = a.p1 + b.p1;
    return r;
}
State state_sub(State a, State b) {
    State r;
    r.q0 = a.q0 - b.q0; r.q1 = vec4(a.q1.x - b.q1.x, 0.0, 0.0, 0.0);
    r.p0 = a.p0 - b.p0; r.p1 = a.p1 - b.p1;
    return r;
}
State state_scale(State a, float scale) {
    State r;
    r.q0 = a.q0 * scale; r.q1 = vec4(a.q1.x * scale, 0.0, 0.0, 0.0);
    r.p0 = a.p0 * scale; r.p1 = a.p1 * scale;
    return r;
}
float minmod_scalar(float a, float b) {
    if (a * b <= 0.0) return 0.0;
    return sign(a) * min(abs(a), abs(b));
}
float mc_scalar(float a, float b) {
    return minmod_scalar(minmod_scalar(2.0 * a, 0.5 * (a + b)), 2.0 * b);
}
vec4 mc_vec4(vec4 a, vec4 b) {
    return vec4(mc_scalar(a.x, b.x), mc_scalar(a.y, b.y),
        mc_scalar(a.z, b.z), mc_scalar(a.w, b.w));
}
State mc_slope(State minus_delta, State plus_delta) {
    State r;
    r.q0 = mc_vec4(minus_delta.q0, plus_delta.q0);
    r.q1 = vec4(mc_scalar(minus_delta.q1.x, plus_delta.q1.x), 0.0, 0.0, 0.0);
    r.p0 = mc_vec4(minus_delta.p0, plus_delta.p0);
    r.p1 = mc_vec4(minus_delta.p1, plus_delta.p1);
    return r;
}
State reconstruct(ivec3 c, int face_sign, int axis_value, uvec3 d, bool high_order) {
    State center = load_state(c, d);
    if (!high_order) return center;
    ivec3 offset = axis_offset(axis_value);
    if (!in_domain(c - offset, d) || !in_domain(c + offset, d)) return center;
    State left = load_state(c - offset, d);
    State right = load_state(c + offset, d);
    State slope = mc_slope(state_sub(center, left), state_sub(right, center));
    return state_add(center, state_scale(slope, 0.5 * float(face_sign)));
}
float population_component(State state, int index) {
    if (index == 0) return state.p0.x;
    if (index == 1) return state.p0.y;
    if (index == 2) return state.p0.z;
    if (index == 3) return state.p0.w;
    if (index == 4) return state.p1.x;
    if (index == 5) return state.p1.y;
    return state.p1.z;
}
// Canonical definition lives in cassi_physical_matter_atomic.glsl (cell form);
// this State form and the inline copy in cassi_physical_matter_init.glsl must
// stay in lockstep with it whenever the level convention or velocity unit
// changes.
float chemical_energy(State state) {
    float velocity_unit2 = pc.velocity_m_s_per_sim * pc.velocity_m_s_per_sim;
    float result = 0.0;
    for (int level = 0; level < 6; ++level)
        result += population_component(state, level) * level_data[level].x / (M_H * velocity_unit2);
    return result + state.p1.z * level_data[6].x / (M_H * velocity_unit2);
}
Primitive primitive(State state) {
    Primitive p;
    p.rho = state.q0.x;
    p.velocity = vec3(0.0);
    p.pressure = 0.0;
    p.sound = 0.0;
    p.valid = finite_vec4(state.q0) && finite_float(state.q1.x)
        && finite_vec4(state.p0) && finite_vec4(state.p1) && p.rho >= 0.0;
    if (!p.valid || p.rho <= pc.density_floor) return p;
    p.velocity = state.q0.yzw / p.rho;
    float kinetic = 0.5 * dot(state.q0.yzw, state.q0.yzw) / p.rho;
    float thermal = state.q1.x - kinetic - chemical_energy(state);
    p.pressure = (pc.gamma_gas - 1.0) * thermal;
    p.valid = p.valid && finite_vec3(p.velocity) && finite_float(p.pressure)
        && p.pressure >= pc.pressure_floor;
    if (p.valid) p.sound = sqrt(pc.gamma_gas * p.pressure / p.rho);
    return p;
}
Flux zero_flux() {
    Flux f;
    f.q0 = vec4(0.0); f.q1 = vec4(0.0); f.p0 = vec4(0.0); f.p1 = vec4(0.0);
    return f;
}
Flux physical_flux(State state, Primitive p, int axis_value) {
    if (!(p.rho > pc.density_floor) || !p.valid) return zero_flux();
    float un = component(p.velocity, axis_value);
    Flux f;
    f.q0.x = p.rho * un;
    f.q0.yzw = state.q0.yzw * un;
    f.q0[axis_value + 1] += p.pressure;
    f.q1 = vec4((state.q1.x + p.pressure) * un, 0.0, 0.0, 0.0);
    f.p0 = state.p0 * un;
    f.p1 = state.p1 * un;
    return f;
}
Flux flux_add(Flux a, Flux b) {
    Flux r;
    r.q0 = a.q0 + b.q0; r.q1 = a.q1 + b.q1; r.p0 = a.p0 + b.p0; r.p1 = a.p1 + b.p1;
    return r;
}
Flux flux_scale(Flux a, float scale) {
    Flux r;
    r.q0 = a.q0 * scale; r.q1 = a.q1 * scale; r.p0 = a.p0 * scale; r.p1 = a.p1 * scale;
    return r;
}
Flux state_difference_flux(State a, State b) {
    Flux r;
    r.q0 = a.q0 - b.q0; r.q1 = vec4(a.q1.x - b.q1.x, 0.0, 0.0, 0.0);
    r.p0 = a.p0 - b.p0; r.p1 = a.p1 - b.p1;
    return r;
}
Flux hlle_flux(State left, State right, Primitive pl, Primitive pr, int axis_value) {
    if (!(pl.rho > pc.density_floor) && !(pr.rho > pc.density_floor)) return zero_flux();
    float ul = component(pl.velocity, axis_value);
    float ur = component(pr.velocity, axis_value);
    float sl = min(ul - pl.sound, ur - pr.sound);
    float sr = max(ul + pl.sound, ur + pr.sound);
    Flux fl = physical_flux(left, pl, axis_value);
    Flux fr = physical_flux(right, pr, axis_value);
    if (sl >= 0.0) return fl;
    if (sr <= 0.0) return fr;
    float denominator = max(sr - sl, 1.0e-20);
    Flux result = flux_add(flux_scale(fl, sr), flux_scale(fr, -sl));
    result = flux_add(result, flux_scale(state_difference_flux(right, left), sl * sr));
    return flux_scale(result, 1.0 / denominator);
}
State star_state(State state, Primitive p, float wave, float contact, float pstar, int axis_value) {
    State star = zero_state();
    float un = component(p.velocity, axis_value);
    float denominator = wave - contact;
    float rho_star = p.rho * (wave - un) / denominator;
    vec3 velocity_star = set_component(p.velocity, axis_value, contact);
    star.q0 = vec4(rho_star, rho_star * velocity_star);
    star.q1.x = ((wave - un) * state.q1.x - p.pressure * un + pstar * contact) / denominator;
    float ratio = rho_star / max(p.rho, pc.density_floor);
    star.p0 = state.p0 * ratio;
    star.p1 = state.p1 * ratio;
    return star;
}
// Takes the same already-computed primitives as hlle_flux(): face_flux() owns
// the single primitive() evaluation per reconstructed state, so a face pays two
// evaluations (each a 7-level chemical_energy loop) instead of four.
Flux riemann_flux(State left, State right, Primitive pl, Primitive pr, int axis_value) {
    if (!pl.valid || !pr.valid || !(pl.rho > pc.density_floor) || !(pr.rho > pc.density_floor))
        return hlle_flux(left, right, pl, pr, axis_value);
    float ul = component(pl.velocity, axis_value);
    float ur = component(pr.velocity, axis_value);
    float sl = min(ul - pl.sound, ur - pr.sound);
    float sr = max(ul + pl.sound, ur + pr.sound);
    Flux fl = physical_flux(left, pl, axis_value);
    Flux fr = physical_flux(right, pr, axis_value);
    if (sl >= 0.0) return fl;
    if (sr <= 0.0) return fr;
    float denominator = pl.rho * (sl - ul) - pr.rho * (sr - ur);
    if (abs(denominator) < 1.0e-20) return hlle_flux(left, right, pl, pr, axis_value);
    float contact = (pr.pressure - pl.pressure + pl.rho * ul * (sl - ul)
        - pr.rho * ur * (sr - ur)) / denominator;
    float pstar = pl.pressure + pl.rho * (sl - ul) * (contact - ul);
    if (!finite_float(contact) || !finite_float(pstar) || pstar < 0.0
            || abs(sl - contact) < 1.0e-20 || abs(sr - contact) < 1.0e-20)
        return hlle_flux(left, right, pl, pr, axis_value);
    if (contact >= 0.0) {
        State star = star_state(left, pl, sl, contact, pstar, axis_value);
        return flux_add(fl, flux_scale(state_difference_flux(star, left), sl));
    }
    State star = star_state(right, pr, sr, contact, pstar, axis_value);
    return flux_add(fr, flux_scale(state_difference_flux(star, right), sr));
}
Flux boundary_flux(State inside, int axis_value, bool lower) {
    Primitive p = primitive(inside);
    float normal_velocity = component(p.velocity, axis_value);
    bool outgoing = lower ? normal_velocity < 0.0 : normal_velocity > 0.0;
    return outgoing ? physical_flux(inside, p, axis_value) : zero_flux();
}
Flux face_flux(ivec3 left_cell, int axis_value, uvec3 d, bool high_order) {
    ivec3 offset = axis_offset(axis_value);
    ivec3 right_cell = left_cell + offset;
    bool left_inside = in_domain(left_cell, d);
    bool right_inside = in_domain(right_cell, d);
    if (!left_inside && right_inside) return boundary_flux(load_state(right_cell, d), axis_value, true);
    if (left_inside && !right_inside) return boundary_flux(load_state(left_cell, d), axis_value, false);
    if (!left_inside && !right_inside) return zero_flux();
    State left = reconstruct(left_cell, 1, axis_value, d, high_order);
    State right = reconstruct(right_cell, -1, axis_value, d, high_order);
    Primitive pl = primitive(left);
    Primitive pr = primitive(right);
    if (!pl.valid || !pr.valid) {
        left = load_state(left_cell, d);
        right = load_state(right_cell, d);
        pl = primitive(left);
        pr = primitive(right);
    }
    return high_order
        ? riemann_flux(left, right, pl, pr, axis_value)
        : hlle_flux(left, right, pl, pr, axis_value);
}
State apply_flux_update(State source, Flux lower, Flux upper, float scale) {
    State out_state = source;
    out_state.q0 -= scale * (upper.q0 - lower.q0);
    out_state.q1.x -= scale * (upper.q1.x - lower.q1.x);
    out_state.p0 -= scale * (upper.p0 - lower.p0);
    out_state.p1 -= scale * (upper.p1 - lower.p1);
    return out_state;
}
uint state_rejection_reason(State state) {
    if (!finite_vec4(state.q0) || !finite_float(state.q1.x)
            || !finite_vec4(state.p0) || !finite_vec4(state.p1)) return 1u;
    if (state.q0.x < -pc.density_floor || any(lessThan(state.p0, vec4(-pc.density_floor)))
            || any(lessThan(state.p1.xyz, vec3(-pc.density_floor)))) return 2u;
    // normalize_state() defines any finite state at or below the density
    // floor as numerical vacuum.  Riemann flux cancellation can leave both
    // positive or negative sub-floor energy while density is still within
    // the accepted floor tolerance.  Admit the complete floor state here so
    // the shared normalization zeros mass, momentum, energy, and populations
    // together instead of flagging a state that will not be retained.
    if (state.q0.x <= pc.density_floor) return 0u;
    float population_sum = dot(state.p0, vec4(1.0)) + state.p1.x + state.p1.y + state.p1.z;
    if (!(population_sum > 0.0)) return 8u;
    Primitive p = primitive(state);
    return p.valid && p.pressure >= pc.pressure_floor ? 0u : 16u;
}
bool state_admissible(State state) {
    return state_rejection_reason(state) == 0u;
}
State normalize_state(State state) {
    if (state.q0.x <= pc.density_floor) return zero_state();
    state.p0 = max(state.p0, vec4(0.0));
    state.p1.xyz = max(state.p1.xyz, vec3(0.0));
    float population_sum = dot(state.p0, vec4(1.0)) + state.p1.x + state.p1.y + state.p1.z;
    if (!(population_sum > 0.0)) {
        // Near the numerical vacuum boundary, independently advected float32
        // mass and partial densities can cancel to positive rho but zero
        // populations. Preserve that baryonic mass as neutral ground-state
        // hydrogen so every retained material cell has a closed population.
        state.p0 = vec4(state.q0.x, 0.0, 0.0, 0.0);
        state.p1 = vec4(0.0);
        return state;
    }
    if (population_sum <= state.q0.x) {
        // Put positive closure residual in the zero-binding-energy ground
        // state. Total energy and every excited-state population stay fixed.
        state.p0.x += state.q0.x - population_sum;
    } else {
        // Remove a negative closure residual proportionally. This preserves
        // total material energy while reducing (never increasing) chemical
        // energy, so normalization cannot create a pressure failure.
        float factor = state.q0.x / population_sum;
        state.p0 *= factor;
        state.p1.xyz *= factor;
    }
    return state;
}

uint normalize_and_validate(inout State state) {
    uint reason = state_rejection_reason(state);
    if (reason == 1u || reason == 2u) return reason;
    state = normalize_state(state);
    return state_rejection_reason(state);
}
float normal_velocity_at(ivec3 c, int axis_value, uvec3 d) {
    State state = load_state(c, d);
    Primitive p = primitive(state);
    return p.valid ? component(p.velocity, axis_value) : 0.0;
}
void finish_auxiliary(inout State state, State source, ivec3 c, int axis_value, uvec3 d, float dx) {
    if (state.q0.x <= pc.density_floor) { state.q1.yzw = vec3(0.0); return; }
    float kinetic = 0.5 * dot(state.q0.yzw, state.q0.yzw) / state.q0.x;
    float thermal = state.q1.x - kinetic - chemical_energy(state);
    float pressure = max((pc.gamma_gas - 1.0) * thermal, pc.pressure_floor);
    float ion_fraction = clamp(state.p1.z / state.q0.x, 0.0, 1.0);
    float thermal_specific_si = thermal / state.q0.x
        * pc.velocity_m_s_per_sim * pc.velocity_m_s_per_sim;
    float temperature = (pc.gamma_gas - 1.0) * M_H * thermal_specific_si
        / (K_B * (1.0 + ion_fraction));
    ivec3 offset = axis_offset(axis_value);
    float left_velocity = normal_velocity_at(c - offset, axis_value, d);
    float right_velocity = normal_velocity_at(c + offset, axis_value, d);
    if (!in_domain(c - offset, d)) left_velocity = normal_velocity_at(c, axis_value, d);
    if (!in_domain(c + offset, d)) right_velocity = normal_velocity_at(c, axis_value, d);
    float divergence = (axis_value == 0 ? 0.0 : source.q1.w)
        + (right_velocity - left_velocity) / (2.0 * dx);
    state.q1.y = clamp(temperature, pc.temperature_min_K, pc.temperature_max_K);
    state.q1.z = pressure;
    state.q1.w = divergence;
}

void main() {
    uint gid = gl_GlobalInvocationID.x;
    if ((status[0].x & STATUS_STEP_REJECTED) != 0u) return;
    uvec3 d = dims();
    if (gid >= cell_count()) return;
    int axis_value = clamp(int(pc.axis + 0.5), 0, 2);
    ivec3 c = coordinate(gid, d);
    ivec3 offset = axis_offset(axis_value);
    vec3 cell_size = 2.0 * vec3(pc.extent_x, pc.extent_y, pc.extent_z) / vec3(d);
    float dx = component(cell_size, axis_value);
    float scale = pc.dt_sim / dx;
    State source = load_state(c, d);
    Flux lower = face_flux(c - offset, axis_value, d, true);
    Flux upper = face_flux(c, axis_value, d, true);
    State candidate = apply_flux_update(source, lower, upper, scale);
    uint rejection_reason = normalize_and_validate(candidate);
    if (rejection_reason != 0u) {
        atomicOr(status[0].x, STATUS_HYDRO_RETRY);
        atomicOr(status[3].w, rejection_reason << 16u);
        atomicAdd(status[1].x, 1u);
        lower = face_flux(c - offset, axis_value, d, false);
        upper = face_flux(c, axis_value, d, false);
        candidate = apply_flux_update(source, lower, upper, scale);
        rejection_reason = normalize_and_validate(candidate);
    }
    if (rejection_reason != 0u) {
        atomicOr(status[0].x, (rejection_reason & 1u) != 0u
            ? STATUS_HYDRO_NONFINITE : STATUS_HYDRO_NEGATIVE);
        atomicAdd(status[1].y, 1u);
        if (axis_value == 0) atomicAdd(status[3].x, 1u);
        else if (axis_value == 1) atomicAdd(status[3].y, 1u);
        else atomicAdd(status[3].z, 1u);
        atomicOr(status[3].w, rejection_reason);
        ledger1[gid].w += 1.0;
        State source_check = source;
        uint source_reason = normalize_and_validate(source_check);
        atomicOr(status[3].w, source_reason << 8u);
        if (atomicCompSwap(hydro_debug[0].x, 0u, gid + 1u) == 0u) {
            float candidate_kinetic = candidate.q0.x > pc.density_floor
                ? 0.5 * dot(candidate.q0.yzw, candidate.q0.yzw) / candidate.q0.x : 0.0;
            float candidate_chemical = chemical_energy(candidate);
            float source_kinetic = source.q0.x > pc.density_floor
                ? 0.5 * dot(source.q0.yzw, source.q0.yzw) / source.q0.x : 0.0;
            float source_chemical = chemical_energy(source);
            hydro_debug[0] = uvec4(gid + 1u, uint(axis_value), rejection_reason, source_reason);
            hydro_debug[1] = floatBitsToUint(vec4(
                candidate.q0.x, candidate.q1.x, candidate_kinetic, candidate_chemical));
            hydro_debug[2] = floatBitsToUint(vec4(
                candidate.q1.x - candidate_kinetic - candidate_chemical,
                source.q0.x, source.q1.x, source_kinetic));
            hydro_debug[3] = floatBitsToUint(vec4(
                source_chemical, source.q1.x - source_kinetic - source_chemical,
                candidate.q1.z, source.q1.z));
        }
        candidate = source;
    }
    candidate = normalize_state(candidate);
    if (axis_value == 2 && candidate.q0.x > pc.density_floor) {
        vec3 gravity = gravity_cell[gid].xyz;
        if (finite_vec3(gravity)) {
            float energy_before = candidate.q1.x;
            float kinetic_before = 0.5
                * dot(candidate.q0.yzw, candidate.q0.yzw) / candidate.q0.x;
            float nonkinetic = candidate.q1.x - kinetic_before;
            candidate.q0.yzw += candidate.q0.x * gravity * pc.dt_sim;
            float kinetic_after = 0.5
                * dot(candidate.q0.yzw, candidate.q0.yzw) / candidate.q0.x;
            candidate.q1.x = kinetic_after + nonkinetic;
            // Pair the ledger with the discrete float32 energy actually stored.
            // Computing through kinetic energy preserves the nonkinetic
            // reservoir across the gravity kick without adding floor energy.
            ledger1[gid].z += candidate.q1.x - energy_before;
        }
    }
    finish_auxiliary(candidate, source, c, axis_value, d, dx);
    bool lower_boundary = component(vec3(c), axis_value) == 0.0;
    bool upper_boundary = component(vec3(c), axis_value) == component(vec3(d), axis_value) - 1.0;
    Flux outward = zero_flux();
    if (lower_boundary) outward = flux_add(outward, flux_scale(lower, -1.0));
    if (upper_boundary) outward = flux_add(outward, upper);
    if (lower_boundary || upper_boundary) {
        ledger1[gid].x += max(scale * outward.q0.x, 0.0);
        ledger1[gid].y += max(scale * outward.q1.x, 0.0);
        ledger2[gid].xyz += scale * outward.q0.yzw;
    }
    material0_out[gid] = candidate.q0;
    material1_out[gid] = candidate.q1;
    population0_out[gid] = candidate.p0;
    population1_out[gid] = candidate.p1;
}
