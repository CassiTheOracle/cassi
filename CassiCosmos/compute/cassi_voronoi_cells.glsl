#[compute]
#version 450
// Cassi Voronoi Cells — the per-cell two-fluid wave system on the JFA
// Voronoi mesh (MESHLESS_PLAN.md Stage 1 + the §10 sim integration).
// State is PER VORONOI CELL (one site each): psiY/psiI and their
// momenta piY/piI. The wave Laplacian is the two-point flux across the
// grid faces that separate different JFA labels — the staircase
// approximation of the true Voronoi face. Proven in numpy
// (research/meshless/stage1_jfa3d.py) and on the GPU (G0-G4, G9-G12).
//
// Pass modes (PC.mode):
//   0 lap        — per GRID cell: the three +axis faces, float
//                  atomicAdd flux (each face counted once)
//   1 leapfrog   — per SITE: kick π (flux + coupling + the mass-driven
//                  source sampled at the site's own grid cell), drift
//                  ψ, zero lap
//   2 volume     — per GRID cell: atomicAdd h³ per cell
//   3 centroid   — per GRID cell: atomicAdd the cell center into
//                  cen[lab].xyz, count into cen[lab].w (the OLD mesh)
//   4 steer      — per SITE: the quasi-Lagrangian ride + Lloyd-style
//                  centroid relaxation (guards: rho floor + drift cap),
//                  writes the new site position AND the remap index
//                  (the OLD cell containing the new position)
//   5 state→tmp  — per SITE: copy the state to the temp buffers
//   6 tmp→state  — per SITE: gather the remapped state (tmp[remap_idx])
//   7 reset      — per SITE: vol = 0, cen = (0,0,0,0)
//   8 labels clr — per GRID cell: labels = INT_MAX
//   9 scatter    — per SITE: atomicMin the site index into its grid cell
//
// The whole rebuild is ONE compute list (barriers between modes): reset
// → centroid → steer → remap copy → remap gather → labels clear →
// scatter → JFA (the ping-pong passes share the list) → volume. No
// readbacks, no CPU loops — the global RD never stalls.
// Float atomicAdd: GL_EXT_shader_atomic_float, verified on this rig in
// cassi_mass_deposit.glsl (RX 7900 XTX, Vulkan 1.4, Godot 4.7).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float mode;             // see the mode list above
    float N_f;              // grid resolution per dimension
    float n_sites;          // site (cell) count
    float dt;               // leapfrog step
    float h;                // cell spacing (L / N)
    float C2;               // wave speed² (h₀² — matches the grid's D19)
    float OM2;              // omega_0²
    float PHI;              // golden ratio
    float source_strength;  // field injection (the grid PDE's source_s)
    float rho_floor;        // steering guard: rho = EY+EI can hit ~0
    float drift_cap;        // steering guard: per-rebuild drift cap
    float kappa;            // centroid relaxation fraction
    float lam;              // super-Lagrangian momentum ride
    float T_steer;          // dt × rebuild cadence
} pc;

layout(set = 0, binding = 0, std430) buffer Labels {
    int labels[];  // JFA site index per grid cell (read-write: clear/scatter)
};
layout(set = 0, binding = 1, std430) buffer Sites {
    vec4 pos[];  // x, y, z per site (read-write: the steer moves them)
};
layout(set = 0, binding = 2, std430) buffer PsiY {
    float psi_y[];
};
layout(set = 0, binding = 3, std430) buffer PsiI {
    float psi_i[];
};
layout(set = 0, binding = 4, std430) buffer PiY {
    float pi_y[];
};
layout(set = 0, binding = 5, std430) buffer PiI {
    float pi_i[];
};
layout(set = 0, binding = 6, std430) coherent buffer LapY {
    float lap_y[];
};
layout(set = 0, binding = 7, std430) coherent buffer LapI {
    float lap_i[];
};
layout(set = 0, binding = 8, std430) coherent buffer Vol {
    float vol[];
};
layout(set = 0, binding = 9, std430) restrict readonly buffer MassDensity {
    float rho_mass[];  // the deposit's mass density per GRID cell
};
layout(set = 0, binding = 10, std430) coherent buffer Cen {
    vec4 cen[];  // centroid sums (xyz) + count (w), per site
};
layout(set = 0, binding = 11, std430) buffer Remap {
    int remap_idx[];  // old cell index per site (the ALE remap source)
};
layout(set = 0, binding = 12, std430) buffer TmpY {
    float tmp_y[];
};
layout(set = 0, binding = 13, std430) buffer TmpI {
    float tmp_i[];
};
layout(set = 0, binding = 14, std430) buffer TmpPY {
    float tmp_py[];
};
layout(set = 0, binding = 15, std430) buffer TmpPI {
    float tmp_pi[];
};

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int Nn = int(pc.N_f);
    int ns = int(pc.n_sites);
    int im = int(pc.mode);
    int total = Nn * Nn * Nn;
    float h = pc.h;

    if (im == 8) {  // labels clear
        if (int(gid) >= total) return;
        labels[int(gid)] = 2147483647;
        return;
    }
    if (im == 9) {  // scatter: min site index per grid cell
        if (int(gid) >= ns) return;
        int s = int(gid);
        vec4 sp = pos[s];
        int gi = int(floor(sp.x / h)) % Nn;
        int gj = int(floor(sp.y / h)) % Nn;
        int gk = int(floor(sp.z / h)) % Nn;
        atomicMin(labels[gi * Nn * Nn + gj * Nn + gk], s);
        return;
    }
    if (im == 7) {  // reset vol + cen
        if (int(gid) >= ns) return;
        vol[int(gid)] = 0.0;
        cen[int(gid)] = vec4(0.0);
        return;
    }
    if (im == 3) {  // centroid accumulate (the OLD mesh)
        if (int(gid) >= total) return;
        int lab = labels[int(gid)];
        if (lab < 0 || lab >= ns) return;
        int i = int(gid) / (Nn * Nn);
        int rem = int(gid) - i * Nn * Nn;
        int j = rem / Nn;
        int k = rem - j * Nn;
        atomicAdd(cen[lab].x, (float(i) + 0.5) * h);
        atomicAdd(cen[lab].y, (float(j) + 0.5) * h);
        atomicAdd(cen[lab].z, (float(k) + 0.5) * h);
        atomicAdd(cen[lab].w, 1.0);
        return;
    }
    if (im == 4) {  // steer: new sites + remap index (the OLD mesh)
        if (int(gid) >= ns) return;
        int s = int(gid);
        vec4 sp = pos[s];
        float rho = max(psi_y[s] + psi_i[s], pc.rho_floor);
        float vv = pc.lam * (pi_y[s] + pi_i[s]) / rho;
        float drift = clamp(vv * pc.T_steer, -pc.drift_cap, pc.drift_cap);
        float cc = max(cen[s].w, 1.0);
        float L = float(Nn) * h;
        float nx = mod((1.0 - pc.kappa) * (sp.x + drift)
                       + pc.kappa * (cen[s].x / cc), L);
        float ny = mod((1.0 - pc.kappa) * (sp.y + drift)
                       + pc.kappa * (cen[s].y / cc), L);
        float nz = mod((1.0 - pc.kappa) * (sp.z + drift)
                       + pc.kappa * (cen[s].z / cc), L);
        int gi = int(floor(nx / h)) % Nn;
        int gj = int(floor(ny / h)) % Nn;
        int gk = int(floor(nz / h)) % Nn;
        int lab = labels[gi * Nn * Nn + gj * Nn + gk];
        if (lab < 0 || lab >= ns) lab = s;
        remap_idx[s] = lab;
        pos[s] = vec4(nx, ny, nz, 0.0);
        return;
    }
    if (im == 5) {  // state → temp
        if (int(gid) >= ns) return;
        int s = int(gid);
        tmp_y[s] = psi_y[s];
        tmp_i[s] = psi_i[s];
        tmp_py[s] = pi_y[s];
        tmp_pi[s] = pi_i[s];
        return;
    }
    if (im == 6) {  // temp → state via remap_idx
        if (int(gid) >= ns) return;
        int s = int(gid);
        int r = remap_idx[s];
        psi_y[s] = tmp_y[r];
        psi_i[s] = tmp_i[r];
        pi_y[s] = tmp_py[r];
        pi_i[s] = tmp_pi[r];
        return;
    }
    if (im == 2) {  // volume: h³ per grid cell, atomic
        if (int(gid) >= total) return;
        int lab = labels[int(gid)];
        if (lab >= 0 && lab < ns) {
            atomicAdd(vol[lab], h * h * h);
        }
        return;
    }

    if (im == 0) {  // lap: +x/+y/+z faces of this grid cell
        if (int(gid) >= total) return;
        int i = int(gid) / (Nn * Nn);
        int rem = int(gid) - i * Nn * Nn;
        int j = rem / Nn;
        int k = rem - j * Nn;
        int c = labels[int(gid)];
        if (c < 0 || c >= ns) return;

        // three +axis faces, periodic; each face handled exactly once
        int n1 = labels[((i + 1) % Nn) * Nn * Nn + j * Nn + k];
        int n2 = labels[i * Nn * Nn + ((j + 1) % Nn) * Nn + k];
        int n3 = labels[i * Nn * Nn + j * Nn + ((k + 1) % Nn)];

        vec4 sc = pos[c];
        float h2 = h * h;

        if (n1 >= 0 && n1 < ns && n1 != c) {
            vec4 sn = pos[n1];
            float d = length(sn.xyz - sc.xyz);
            float fy = (psi_y[n1] - psi_y[c]) * h2 / max(d, 1e-12);
            float fi = (psi_i[n1] - psi_i[c]) * h2 / max(d, 1e-12);
            atomicAdd(lap_y[c], fy);
            atomicAdd(lap_y[n1], -fy);
            atomicAdd(lap_i[c], fi);
            atomicAdd(lap_i[n1], -fi);
        }
        if (n2 >= 0 && n2 < ns && n2 != c) {
            vec4 sn = pos[n2];
            float d = length(sn.xyz - sc.xyz);
            float fy = (psi_y[n2] - psi_y[c]) * h2 / max(d, 1e-12);
            float fi = (psi_i[n2] - psi_i[c]) * h2 / max(d, 1e-12);
            atomicAdd(lap_y[c], fy);
            atomicAdd(lap_y[n2], -fy);
            atomicAdd(lap_i[c], fi);
            atomicAdd(lap_i[n2], -fi);
        }
        if (n3 >= 0 && n3 < ns && n3 != c) {
            vec4 sn = pos[n3];
            float d = length(sn.xyz - sc.xyz);
            float fy = (psi_y[n3] - psi_y[c]) * h2 / max(d, 1e-12);
            float fi = (psi_i[n3] - psi_i[c]) * h2 / max(d, 1e-12);
            atomicAdd(lap_y[c], fy);
            atomicAdd(lap_y[n3], -fy);
            atomicAdd(lap_i[c], fi);
            atomicAdd(lap_i[n3], -fi);
        }
        return;
    }

    // im == 1 — leapfrog: one thread per site
    if (int(gid) >= ns) return;
    int s = int(gid);
    float dev = psi_y[s] - pc.PHI * psi_i[s];
    float v = max(vol[s], 1e-12);

    // the grid PDE's source, sampled at the site's own grid cell:
    // src_y = s·exp(-r²4) + rho_mass·0.001, src_i = 0.707·(same)
    vec4 sp = pos[s];
    int gi = int(floor(sp.x / h)) % Nn;
    int gj = int(floor(sp.y / h)) % Nn;
    int gk = int(floor(sp.z / h)) % Nn;
    float mr = rho_mass[gi * Nn * Nn + gj * Nn + gk];
    float halfn = float(Nn) * 0.5;
    float dx = (sp.x / h - halfn * 0.7) / halfn;
    float dy = (sp.y / h - halfn * 0.8) / halfn;
    float dz = (sp.z / h - halfn * 0.6) / halfn;
    float r2 = dx * dx + dy * dy + dz * dz;
    float src_y = pc.source_strength * exp(-r2 * 4.0) + mr * 0.001;
    float src_i = pc.source_strength * 0.707 * exp(-r2 * 4.0) + mr * 0.000707;

    pi_y[s] += pc.dt * (pc.C2 * lap_y[s] / v - pc.OM2 * dev + src_y);
    pi_i[s] += pc.dt * (pc.C2 * lap_i[s] / v + pc.OM2 * dev + src_i);
    psi_y[s] += pc.dt * pi_y[s];
    psi_i[s] += pc.dt * pi_i[s];
    lap_y[s] = 0.0;
    lap_i[s] = 0.0;
}
