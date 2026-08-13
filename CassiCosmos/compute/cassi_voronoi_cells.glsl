#[compute]
#version 450
// Cassi Voronoi Cells — the per-cell two-fluid wave system on the JFA
// Voronoi mesh (MESHLESS_PLAN.md Stage 1). State is PER VORONOI CELL
// (one site each): psiY/psiI and their momenta piY/piI. The wave
// Laplacian is the two-point flux across the grid faces that separate
// different JFA labels — the staircase approximation of the true
// Voronoi face (each face contributes (psi_n - psi_c) h² / d_cn to
// both cells; the grid-aligned faces converge to the Voronoi faces as
// N grows relative to the site count). Proven in numpy:
// research/meshless/stage1_jfa3d.py — breather within 0.9% of
// sqrt(om2 (1+phi)), L2 = 1.5e-3 vs the exact 3D spectral reference.
//
// Pass modes (PC):
//   0 lap       — one thread per GRID cell: the three +axis faces
//                 (each face counted once), float atomicAdd flux
//   1 leapfrog  — one thread per SITE: kick π, drift ψ, zero lap
//   2 volume    — one thread per GRID cell: atomicAdd h³ per cell
// The per-step chain is lap → barrier → leapfrog (the leapfrog's lap
// reset doubles as the next step's clear — no separate zero pass).
// Float atomicAdd: GL_EXT_shader_atomic_float, verified on this rig in
// cassi_mass_deposit.glsl (RX 7900 XTX, Vulkan 1.4, Godot 4.7).
#extension GL_EXT_shader_atomic_float : require

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float mode;         // 0 lap, 1 leapfrog, 2 volume
    float N_f;          // grid resolution per dimension
    float n_sites;      // site (cell) count
    float dt;           // leapfrog step
    float h;            // cell spacing (L / N)
    float C2;           // wave speed²
    float OM2;          // omega_0²
    float PHI;          // golden ratio
} pc;

layout(set = 0, binding = 0, std430) restrict readonly buffer Labels {
    int labels[];  // JFA site index per grid cell
};
layout(set = 0, binding = 1, std430) restrict readonly buffer Sites {
    vec4 pos[];  // x, y, z per site
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

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int Nn = int(pc.N_f);
    int ns = int(pc.n_sites);
    int im = int(pc.mode);

    if (im == 2) {  // volume: h³ per grid cell, atomic
        if (int(gid) >= Nn * Nn * Nn) return;
        int lab = labels[int(gid)];
        if (lab >= 0 && lab < ns) {
            atomicAdd(vol[lab], pc.h * pc.h * pc.h);
        }
        return;
    }

    if (im == 0) {  // lap: +x/+y/+z faces of this grid cell
        if (int(gid) >= Nn * Nn * Nn) return;
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
        float h2 = pc.h * pc.h;

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
    pi_y[s] += pc.dt * (pc.C2 * lap_y[s] / v - pc.OM2 * dev);
    pi_i[s] += pc.dt * (pc.C2 * lap_i[s] / v + pc.OM2 * dev);
    psi_y[s] += pc.dt * pi_y[s];
    psi_i[s] += pc.dt * pi_i[s];
    lap_y[s] = 0.0;
    lap_i[s] = 0.0;
}
