#[compute]
#version 450
// Default-off conservative vector Qi stress and interscale-transfer sector.
// canonical layout: scripts/contracts/layout.gd
// Registered equations and gates: research/rotation/rotation_prereg.md.
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) readonly buffer Positions { vec4 pos[]; };
layout(set = 0, binding = 1, std430) buffer Velocities { vec4 vel[]; };
layout(set = 0, binding = 2, std430) buffer Displacement { vec4 displacement[]; };
layout(set = 0, binding = 3, std430) buffer Momentum { vec4 momentum[]; };
layout(set = 0, binding = 4, std430) buffer MomentumNext { vec4 momentum_next[]; };
layout(set = 0, binding = 5, std430) coherent buffer SpinHeat { vec4 spin_heat[]; };
layout(set = 0, binding = 6, std430) coherent buffer MatterAggregate { vec4 matter[]; };
layout(set = 0, binding = 7, std430) buffer CellImpulse { vec4 impulse[]; };
layout(set = 0, binding = 8, std430) buffer Orientation { vec4 orientation[]; };
layout(set = 0, binding = 9, std430) readonly buffer MergeSpin { vec4 merge_spin[]; };
layout(set = 0, binding = 10, std430) coherent buffer Telemetry { float telemetry[]; };
layout(set = 0, binding = 11, std430) buffer ReservoirDisplacement { vec4 reservoir_displacement[]; };
layout(set = 0, binding = 12, std430) buffer ReservoirMomentum { vec4 reservoir_momentum[]; };
layout(set = 0, binding = 13, std430) buffer ReservoirMomentumNext { vec4 reservoir_momentum_next[]; };

layout(push_constant, std430) uniform PC {
    float pass_mode;
    float particle_n;
    float grid_n;
    float rungs;
    float dt;
    float extent_x;
    float extent_y;
    float extent_z;
    float center_x;
    float center_y;
    float center_z;
    float field_inertia;
    float c_t;
    float c_l;
    float scale_omega;
    float attenuation;
    float exchange_rate;
    float has_merge_spin;
    float size_k;
    float size_min;
    float size_max;
    float reservoir_inertia;
    float lower_reservoir_coupling;
    float upper_reservoir_coupling;
} pc;

const int TELEMETRY_COUNT = 16;
const float EPS = 1e-12;

int grid_n() { return max(int(pc.grid_n + 0.5), 1); }
int rung_n() { return max(int(pc.rungs + 0.5), 1); }
int cell_n() { int n = grid_n(); return n * n * n; }
vec3 extents() { return vec3(pc.extent_x, pc.extent_y, pc.extent_z); }
vec3 window_center() { return vec3(pc.center_x, pc.center_y, pc.center_z); }

int wrap_index(int value, int n) {
    int wrapped = value % n;
    return wrapped < 0 ? wrapped + n : wrapped;
}

int cell_index(ivec3 c) {
    int n = grid_n();
    ivec3 w = ivec3(wrap_index(c.x, n), wrap_index(c.y, n), wrap_index(c.z, n));
    return (w.x * n + w.y) * n + w.z;
}

int flat_cell(ivec3 c) {
    int n = grid_n();
    return (c.x * n + c.y) * n + c.z;
}

ivec3 cell_coords(int index) {
    int n = grid_n();
    int x = index / (n * n);
    int rem = index - x * n * n;
    return ivec3(x, rem / n, rem % n);
}

int field_index(int rung, ivec3 c) {
    return rung * cell_n() + cell_index(c);
}

vec3 load_u(int rung, ivec3 c) {
    return displacement[field_index(rung, c)].xyz;
}

vec3 load_reservoir_u(int boundary, int cell) {
    return reservoir_displacement[boundary * cell_n() + cell].xyz;
}

vec3 cell_center(ivec3 c) {
    vec3 h = 2.0 * extents() / float(grid_n());
    return window_center() - extents() + (vec3(c) + vec3(0.5)) * h;
}

ivec3 particle_cell(vec3 p) {
    vec3 unit = fract((p - window_center() + extents()) / (2.0 * extents()));
    return ivec3(floor(unit * float(grid_n())));
}

vec3 minimum_image(vec3 delta) {
    vec3 period = 2.0 * extents();
    return delta - round(delta / period) * period;
}

bool finite3(vec3 value) {
    return !any(isnan(value)) && !any(isinf(value));
}

void clear_scratch(uint id) {
    int cells = cell_n();
    if (id < uint(cells)) {
        matter[id] = vec4(0.0);
        impulse[id] = vec4(0.0);
    }
    if (id < uint(TELEMETRY_COUNT)) telemetry[id] = 0.0;
}

void deposit_matter(uint id) {
    int count = max(int(pc.particle_n + 0.5), 0);
    if (id >= uint(count)) return;
    vec4 particle = pos[id];
    if (particle.w <= 0.0) return;
    int cell = flat_cell(particle_cell(particle.xyz));
    vec3 particle_momentum = particle.w * vel[id].xyz;
    atomicAdd(matter[cell].x, particle_momentum.x);
    atomicAdd(matter[cell].y, particle_momentum.y);
    atomicAdd(matter[cell].z, particle_momentum.z);
    atomicAdd(matter[cell].w, particle.w);
}

void field_kick(uint id) {
    int cells = cell_n();
    int total = cells * rung_n();
    if (id >= uint(total)) return;
    int rung = int(id) / cells;
    int cell = int(id) - rung * cells;
    ivec3 c = cell_coords(cell);
    vec3 h = 2.0 * extents() / float(grid_n());
    vec3 inv_h2 = 1.0 / (h * h);

    vec3 u0 = load_u(rung, c);
    vec3 ux_p = load_u(rung, c + ivec3(1, 0, 0));
    vec3 ux_m = load_u(rung, c - ivec3(1, 0, 0));
    vec3 uy_p = load_u(rung, c + ivec3(0, 1, 0));
    vec3 uy_m = load_u(rung, c - ivec3(0, 1, 0));
    vec3 uz_p = load_u(rung, c + ivec3(0, 0, 1));
    vec3 uz_m = load_u(rung, c - ivec3(0, 0, 1));
    vec3 lap = (ux_p - 2.0 * u0 + ux_m) * inv_h2.x
        + (uy_p - 2.0 * u0 + uy_m) * inv_h2.y
        + (uz_p - 2.0 * u0 + uz_m) * inv_h2.z;

    float dxx_ux = (ux_p.x - 2.0 * u0.x + ux_m.x) * inv_h2.x;
    float dyy_uy = (uy_p.y - 2.0 * u0.y + uy_m.y) * inv_h2.y;
    float dzz_uz = (uz_p.z - 2.0 * u0.z + uz_m.z) * inv_h2.z;

    vec3 dxy_u = (
        load_u(rung, c + ivec3(1, 1, 0))
        - load_u(rung, c + ivec3(1, -1, 0))
        - load_u(rung, c + ivec3(-1, 1, 0))
        + load_u(rung, c + ivec3(-1, -1, 0))
    ) / (4.0 * h.x * h.y);
    vec3 dxz_u = (
        load_u(rung, c + ivec3(1, 0, 1))
        - load_u(rung, c + ivec3(1, 0, -1))
        - load_u(rung, c + ivec3(-1, 0, 1))
        + load_u(rung, c + ivec3(-1, 0, -1))
    ) / (4.0 * h.x * h.z);
    vec3 dyz_u = (
        load_u(rung, c + ivec3(0, 1, 1))
        - load_u(rung, c + ivec3(0, 1, -1))
        - load_u(rung, c + ivec3(0, -1, 1))
        + load_u(rung, c + ivec3(0, -1, -1))
    ) / (4.0 * h.y * h.z);

    float dxy_uy = dxy_u.y;
    float dxz_uz = dxz_u.z;
    float dxy_ux = dxy_u.x;
    float dyz_uz = dyz_u.z;
    float dxz_ux = dxz_u.x;
    float dyz_uy = dyz_u.y;

    vec3 grad_div = vec3(
        dxx_ux + dxy_uy + dxz_uz,
        dxy_ux + dyy_uy + dyz_uz,
        dxz_ux + dyz_uy + dzz_uz
    );
    vec3 spatial_acc = pc.c_t * pc.c_t * lap
        + (pc.c_l * pc.c_l - pc.c_t * pc.c_t) * grad_div;

    vec3 internal_scale_acc = vec3(0.0);
    if (rung > 0) {
        float conductance = pow(pc.attenuation, float(rung));
        internal_scale_acc += pc.scale_omega * pc.scale_omega * conductance
            * (load_u(rung - 1, c) - u0);
    }
    if (rung + 1 < rung_n()) {
        float conductance = pow(pc.attenuation, float(rung + 1));
        internal_scale_acc += pc.scale_omega * pc.scale_omega * conductance
            * (load_u(rung + 1, c) - u0);
    }

    vec3 lower_boundary_acc = vec3(0.0);
    vec3 upper_boundary_acc = vec3(0.0);
    if (rung == 0) {
        lower_boundary_acc = pc.scale_omega * pc.scale_omega
            * pc.lower_reservoir_coupling * (load_reservoir_u(0, cell) - u0);
    }
    if (rung + 1 == rung_n()) {
        upper_boundary_acc = pc.scale_omega * pc.scale_omega
            * pc.upper_reservoir_coupling * (load_reservoir_u(1, cell) - u0);
    }

    vec3 spatial_impulse = pc.field_inertia * pc.dt * spatial_acc;
    vec3 internal_scale_impulse = pc.field_inertia * pc.dt * internal_scale_acc;
    vec3 lower_boundary_impulse = pc.field_inertia * pc.dt * lower_boundary_acc;
    vec3 upper_boundary_impulse = pc.field_inertia * pc.dt * upper_boundary_acc;
    vec3 scale_impulse = internal_scale_impulse
        + lower_boundary_impulse + upper_boundary_impulse;
    vec3 delta_p = spatial_impulse + scale_impulse;
    momentum_next[id] = vec4(momentum[id].xyz + delta_p, 0.0);

    // Spatial and internal-scale ledger corrections retain their existing
    // semantics. Boundary field/reservoir impulses are co-located and already
    // cancel orbital angular momentum, so they must not be counted twice.
    spin_heat[id].xyz -= cross(
        cell_center(c), spatial_impulse + internal_scale_impulse);

    bool invalid = !finite3(momentum_next[id].xyz) || !finite3(spin_heat[id].xyz);
    if (rung == 0) {
        int reservoir = cell;
        reservoir_momentum_next[reservoir] = vec4(
            reservoir_momentum[reservoir].xyz - lower_boundary_impulse, 0.0);
        atomicAdd(telemetry[8], length(lower_boundary_impulse));
        invalid = invalid || !finite3(reservoir_momentum_next[reservoir].xyz);
    }
    if (rung + 1 == rung_n()) {
        int reservoir = cells + cell;
        reservoir_momentum_next[reservoir] = vec4(
            reservoir_momentum[reservoir].xyz - upper_boundary_impulse, 0.0);
        atomicAdd(telemetry[9], length(upper_boundary_impulse));
        invalid = invalid || !finite3(reservoir_momentum_next[reservoir].xyz);
    }
    atomicAdd(telemetry[2], length(spatial_impulse));
    atomicAdd(telemetry[3], length(scale_impulse));
    if (invalid) atomicAdd(telemetry[7], 1.0);
}

void field_drift(uint id) {
    int cells = cell_n();
    int total = cells * rung_n();
    if (id >= uint(total)) return;
    vec3 p = momentum_next[id].xyz;
    momentum[id] = vec4(p, 0.0);
    displacement[id].xyz += pc.dt * p / pc.field_inertia;
    displacement[id].w = 0.0;
    bool invalid = !finite3(displacement[id].xyz);
    if (id < uint(2 * cells)) {
        int reservoir = int(id);
        vec3 reservoir_p = reservoir_momentum_next[reservoir].xyz;
        reservoir_momentum[reservoir] = vec4(reservoir_p, 0.0);
        reservoir_displacement[reservoir].xyz +=
            pc.dt * reservoir_p / pc.reservoir_inertia;
        reservoir_displacement[reservoir].w = 0.0;
        invalid = invalid || !finite3(reservoir_displacement[reservoir].xyz);
    }
    if (invalid) atomicAdd(telemetry[7], 1.0);
}

void solve_exchange(uint id) {
    int cells = cell_n();
    if (id >= uint(cells)) return;
    float matter_mass = matter[id].w;
    if (matter_mass <= 0.0) {
        impulse[id] = vec4(0.0);
        return;
    }
    vec3 matter_velocity = matter[id].xyz / matter_mass;
    vec3 field_velocity = momentum[id].xyz / pc.field_inertia;
    float eta = 1.0 - exp(-pc.exchange_rate * pc.dt);
    float reduced_mass = matter_mass * pc.field_inertia / (matter_mass + pc.field_inertia);
    vec3 relative_velocity = matter_velocity - field_velocity;
    vec3 exchange_impulse = eta * reduced_mass * relative_velocity;
    momentum[id].xyz += exchange_impulse;
    impulse[id] = vec4(exchange_impulse, matter_mass);
    float heat = 0.5 * eta * (2.0 - eta) * reduced_mass * dot(relative_velocity, relative_velocity);
    spin_heat[id].w += heat;
    atomicAdd(telemetry[0], length(exchange_impulse));
    atomicAdd(telemetry[1], heat);
    atomicAdd(telemetry[5], 1.0);
    if (!finite3(exchange_impulse) || isnan(heat) || isinf(heat)) {
        atomicAdd(telemetry[7], 1.0);
    }
}

void apply_exchange(uint id) {
    int count = max(int(pc.particle_n + 0.5), 0);
    if (id >= uint(count)) return;
    vec4 particle = pos[id];
    if (particle.w <= 0.0) return;
    ivec3 c = particle_cell(particle.xyz);
    int cell = flat_cell(c);
    vec4 cell_impulse = impulse[cell];
    if (cell_impulse.w <= 0.0) return;
    vec3 velocity_change = cell_impulse.xyz / cell_impulse.w;
    vel[id].xyz -= velocity_change;
    vec3 particle_impulse = particle.w * velocity_change;
    vec3 offset = minimum_image(particle.xyz - cell_center(c));
    vec3 spin_correction = cross(offset, particle_impulse);
    atomicAdd(spin_heat[cell].x, spin_correction.x);
    atomicAdd(spin_heat[cell].y, spin_correction.y);
    atomicAdd(spin_heat[cell].z, spin_correction.z);
    atomicAdd(telemetry[4], length(spin_correction));
    if (!finite3(vel[id].xyz) || !finite3(spin_correction)) {
        atomicAdd(telemetry[7], 1.0);
    }
}

vec4 quaternion_product(vec4 a, vec4 b) {
    return vec4(
        a.w * b.xyz + b.w * a.xyz + cross(a.xyz, b.xyz),
        a.w * b.w - dot(a.xyz, b.xyz)
    );
}

void integrate_orientation(uint id) {
    int count = max(int(pc.particle_n + 0.5), 0);
    if (id >= uint(count) || pos[id].w <= 0.0 || pc.has_merge_spin < 0.5) return;
    float mass = pos[id].w;
    float radius = clamp(pc.size_k * pow(max(mass, EPS), 1.0 / 3.0), pc.size_min, pc.size_max);
    float moment_inertia = 0.4 * mass * radius * radius;
    vec3 omega = merge_spin[id].xyz / max(moment_inertia, EPS);
    vec4 q = orientation[id];
    float q_norm = length(q);
    if (q_norm <= EPS) q = vec4(0.0, 0.0, 0.0, 1.0);
    else q /= q_norm;
    q += 0.5 * pc.dt * quaternion_product(vec4(omega, 0.0), q);
    q /= max(length(q), EPS);
    orientation[id] = q;
    if (any(isnan(q)) || any(isinf(q))) atomicAdd(telemetry[7], 1.0);
}


void main() {
    uint id = gl_GlobalInvocationID.x;
    int mode = int(pc.pass_mode + 0.5);
    if (mode == 0) clear_scratch(id);
    else if (mode == 1) deposit_matter(id);
    else if (mode == 2) field_kick(id);
    else if (mode == 3) field_drift(id);
    else if (mode == 4) solve_exchange(id);
    else if (mode == 5) apply_exchange(id);
    else if (mode == 6) integrate_orientation(id);
}
