#[compute]
#version 450
// M1 PROTOTYPE — gated site-path variants of cassi_voronoi_cells.glsl
// (mode 4 steer + mode 1 leapfrog). PROBE-ONLY: this shader is NOT wired
// into the sim's default path — the gate-iv probe (res://_diag/m1_gateiv.gd
// phase C) creates its own pipeline and runs it on the sim's meshless
// buffers to prototype two open-domain seeds:
//
//   variant == 0  DEFAULT-COMPATIBLE: byte-identical math to the canonical
//                 mode 4 + mode 1 (the box wrap included). Used as the
//                 control so the probe can prove the other variants differ
//                 EXACTLY by their gated change (determinism evidence).
//   variant == 1  UNWRAPPED STEER: mode 4 drops the `mod(..., L)` self-wrap
//                 (the "box topology dies" seed — the build plan's M1 item
//                 for sites moving freely in world coordinates; the movable
//                 home-window frame from 3e3f9a6 is the coordinate frame).
//                 The drift_cap still bounds the per-rebuild displacement.
//   variant == 2  PER-SITE SOURCE: mode 1 anchors the Gaussian source at the
//                 SITE's own position (the field rides the structure) instead
//                 of the box center (the M1 per-site injection prototype).
//
// Bindings 0-19 mirror cassi_voronoi_cells.glsl EXACTLY (the probe reuses
// the sim's _us_cell_0 uniform set). The PC is the canonical 17 floats PLUS
// a variant selector at float 17 (the probe builds its own 72-byte PC).

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(set = 0, binding = 0, std430) buffer Labels { int labels[]; };
layout(set = 0, binding = 1, std430) buffer Sites { vec4 pos[]; };
layout(set = 0, binding = 2, std430) buffer PsiY { float psi_y[]; };
layout(set = 0, binding = 3, std430) buffer PsiI { float psi_i[]; };
layout(set = 0, binding = 4, std430) buffer PiY { float pi_y[]; };
layout(set = 0, binding = 5, std430) buffer PiI { float pi_i[]; };
layout(set = 0, binding = 6, std430) coherent buffer LapY { float lap_y[]; };
layout(set = 0, binding = 7, std430) coherent buffer LapI { float lap_i[]; };
layout(set = 0, binding = 8, std430) coherent buffer Vol { float vol[]; };
layout(set = 0, binding = 9, std430) restrict readonly buffer MassDensity { float rho_mass[]; };
layout(set = 0, binding = 10, std430) coherent buffer Cen { vec4 cen[]; };
layout(set = 0, binding = 11, std430) buffer Remap { int remap_idx[]; };
layout(set = 0, binding = 12, std430) buffer TmpY { float tmp_y[]; };
layout(set = 0, binding = 13, std430) buffer TmpI { float tmp_i[]; };
layout(set = 0, binding = 14, std430) buffer TmpPY { float tmp_py[]; };
layout(set = 0, binding = 15, std430) buffer TmpPI { float tmp_pi[]; };
layout(set = 0, binding = 16, std430) buffer GradY { vec4 grad_y[]; };
layout(set = 0, binding = 17, std430) buffer GradI { vec4 grad_i[]; };
layout(set = 0, binding = 18, std430) coherent buffer LSMY { vec4 lsm_y[]; };
layout(set = 0, binding = 19, std430) coherent buffer LSMI { vec4 lsm_i[]; };

layout(push_constant, std430) uniform PC {
    float mode;             // 1 (leapfrog) or 4 (steer)
    float N_f;              // grid resolution
    float n_sites;          // site count
    float dt;               // leapfrog step
    float hx;               // x cell spacing
    float hy;
    float hz;
    float C2;               // wave speed²
    float OM2;              // omega_0²
    float PHI;              // golden ratio
    float source_strength;  // field injection
    float rho_floor;        // steering guard
    float drift_cap;        // per-rebuild drift cap
    float kappa;            // centroid relaxation
    float lam;              // momentum ride
    float T_steer;          // dt × rebuild cadence
    float lloyd_p;          // Qi-gate exponent
    float variant;          // 0 = canonical, 1 = unwrapped steer, 2 = per-site source
} pc;

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int Nn = int(pc.N_f);
    int ns = int(pc.n_sites);
    int im = int(pc.mode);
    float hx = pc.hx;
    float hy = pc.hy;
    float hz = pc.hz;

    if (im == 4) {  // steer — Qi-gated, guard-clamped (canonical mode 4)
        if (int(gid) >= ns) return;
        int s = int(gid);
        vec4 sp = pos[s];
        float rho = max(psi_y[s] + psi_i[s], pc.rho_floor);
        float eps = psi_y[s] - pc.PHI * psi_i[s];
        float rsq = rho * rho;
        float q = rsq / (rsq + 1.0 / (pc.PHI * pc.PHI) + eps * eps);
        float kappa_eff = pc.kappa * pow(1.0 - q, pc.lloyd_p);
        float vv = pc.lam * (pi_y[s] + pi_i[s]) / rho;
        float drift = vv * pc.T_steer;
        float cc = max(cen[s].w, 1e-12);
        float Lx = float(Nn) * hx;
        float Ly = float(Nn) * hy;
        float Lz = float(Nn) * hz;
        vec3 blended = (1.0 - kappa_eff) * (sp.xyz + vec3(drift, drift, drift))
                       + kappa_eff * (vec3(cen[s].x, cen[s].y, cen[s].z) / cc);
        vec3 disp = blended - sp.xyz;
        float dlen = length(disp);
        if (dlen > pc.drift_cap) {
            disp *= pc.drift_cap / dlen;
        }
        vec3 npos;
        if (pc.variant > 0.5) {
            // UNWRAPPED: the site moves freely in world coordinates. The
            // movable home-window (bh[0].yzw) provides the coordinate frame;
            // nothing re-folds the site back into [0, L). "Leaves the box"
            // is now meaningful — the site can exit the accelerator window
            // and the tree (open) still sees it at true distance.
            npos = sp.xyz + disp;
        } else {
            npos = mod(sp.xyz + disp, vec3(Lx, Ly, Lz));
        }
        int gi = int(floor(npos.x / hx)) % Nn;
        int gj = int(floor(npos.y / hy)) % Nn;
        int gk = int(floor(npos.z / hz)) % Nn;
        if (gi < 0) gi = 0; if (gi >= Nn) gi = Nn - 1;
        if (gj < 0) gj = 0; if (gj >= Nn) gj = Nn - 1;
        if (gk < 0) gk = 0; if (gk >= Nn) gk = Nn - 1;
        int lab = labels[gi * Nn * Nn + gj * Nn + gk];
        if (lab < 0 || lab >= ns) lab = s;
        remap_idx[s] = lab;
        pos[s] = vec4(npos, 0.0);
        return;
    }

    if (im == 1) {  // leapfrog (canonical mode 1)
        if (int(gid) >= ns) return;
        int s = int(gid);
        float dev = psi_y[s] - pc.PHI * psi_i[s];
        float v = max(vol[s], 1e-12);
        vec4 sp = pos[s];
        int gi = int(floor(sp.x / hx)) % Nn;
        int gj = int(floor(sp.y / hy)) % Nn;
        int gk = int(floor(sp.z / hz)) % Nn;
        if (gi < 0) gi = 0; if (gi >= Nn) gi = Nn - 1;
        if (gj < 0) gj = 0; if (gj >= Nn) gj = Nn - 1;
        if (gk < 0) gk = 0; if (gk >= Nn) gk = Nn - 1;
        float mr = rho_mass[gi * Nn * Nn + gj * Nn + gk];
        float halfn = float(Nn) * 0.5;
        float dx, dy, dz;
        if (pc.variant > 1.5) {
            // PER-SITE SOURCE: the Gaussian is anchored at the site's own
            // position (the "breath" rides the structure) instead of the
            // fixed box-center offset (0.7/0.8/0.6 halfn).
            dx = (sp.x / hx - halfn) / halfn;
            dy = (sp.y / hy - halfn) / halfn;
            dz = (sp.z / hz - halfn) / halfn;
        } else {
            dx = (sp.x / hx - halfn * 0.7) / halfn;
            dy = (sp.y / hy - halfn * 0.8) / halfn;
            dz = (sp.z / hz - halfn * 0.6) / halfn;
        }
        float r2 = dx * dx + dy * dy + dz * dz;
        float src_y = pc.source_strength * exp(-r2 * 4.0) + mr * 0.001;
        float src_i = pc.source_strength * 0.707 * exp(-r2 * 4.0) + mr * 0.000707;
        pi_y[s] += pc.dt * (pc.C2 * lap_y[s] / v - pc.OM2 * dev + src_y);
        pi_i[s] += pc.dt * (pc.C2 * lap_i[s] / v + pc.OM2 * dev + src_i);
        psi_y[s] += pc.dt * pi_y[s];
        psi_i[s] += pc.dt * pi_i[s];
        lap_y[s] = 0.0;
        lap_i[s] = 0.0;
        return;
    }
}
