#[compute]
#version 450
// Cassi JFA — jump-flooding Voronoi construction on the N³ accelerator
// grid (MESHLESS_PLAN.md Stage 1). The grid is a lookup accelerator
// ONLY: no physics lives on it. Each pass floods every cell's current
// best site-index out to its 26-neighborhood at distance `jump`, keeping
// the site nearest the cell CENTER; the doubling sweep (1..N/2) fills
// the grid from the scattered seeds, the halving sweep refines it.
// Proven in numpy (research/meshless/stage1_jfa3d.py, gate G0): 11
// passes on the BCC seed lattice reproduce the exact Voronoi on every
// cell (0.0000 mislabel rate vs KDTree).
//
// Labels ping-pong between two buffers: read_a = 1 reads A/writes B,
// read_a = 0 reads B/writes A (the GDScript side toggles per pass; an
// odd number of passes leaves the result in B, so a final identity
// copy pass — jump = 0 — re-homes it into A for the cell shaders).
// The empty-cell sentinel is INT_MAX (the GPU-side analog of numpy's
// scatter: atomicMin of the site index per cell).
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float N_f;          // grid resolution per dimension
    float jump;         // flood distance in cells (0 = identity copy)
    float read_a;       // 1.0: read A, write B ; 0.0: read B, write A
    float n_sites;      // site count (label validity bound)
    float h;            // cell spacing (L / N)
    float pad0;
    float pad1;
    float pad2;
} pc;

layout(set = 0, binding = 0, std430) buffer LabelsA {
    int a[];  // site index per grid cell, INT_MAX = unlabeled
};
layout(set = 0, binding = 1, std430) buffer LabelsB {
    int b[];
};
layout(set = 0, binding = 2, std430) restrict readonly buffer Sites {
    vec4 pos[];  // x, y, z per site
};

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int Nn = int(pc.N_f);
    int total = Nn * Nn * Nn;
    if (int(gid) >= total) return;
    int ns = int(pc.n_sites);
    int jp = int(pc.jump);
    int r_a = int(pc.read_a);

    int best = (r_a == 1) ? a[int(gid)] : b[int(gid)];

    if (jp == 0) {  // identity copy pass: re-home labels into A
        a[int(gid)] = best;
        return;
    }

    int i = int(gid) / (Nn * Nn);
    int rem = int(gid) - i * Nn * Nn;
    int j = rem / Nn;
    int k = rem - j * Nn;

    float cx = (float(i) + 0.5) * pc.h;
    float cy = (float(j) + 0.5) * pc.h;
    float cz = (float(k) + 0.5) * pc.h;

    float best_d2 = 1e30;
    if (best >= 0 && best < ns) {
        vec4 sp = pos[best];
        float dx = sp.x - cx;
        float dy = sp.y - cy;
        float dz = sp.z - cz;
        best_d2 = dx * dx + dy * dy + dz * dz;
    }

    for (int di = -1; di <= 1; di++) {
        for (int dj = -1; dj <= 1; dj++) {
            for (int dk = -1; dk <= 1; dk++) {
                if (di == 0 && dj == 0 && dk == 0) continue;
                int ii = i + di * jp;
                int jj = j + dj * jp;
                int kk = k + dk * jp;
                ii = (ii % Nn + Nn) % Nn;
                jj = (jj % Nn + Nn) % Nn;
                kk = (kk % Nn + Nn) % Nn;
                int idx = ii * Nn * Nn + jj * Nn + kk;
                int cand = (r_a == 1) ? a[idx] : b[idx];
                if (cand < 0 || cand >= ns) continue;
                vec4 sp = pos[cand];
                float dx = sp.x - cx;
                float dy = sp.y - cy;
                float dz = sp.z - cz;
                float d2 = dx * dx + dy * dy + dz * dz;
                if (d2 < best_d2) {
                    best_d2 = d2;
                    best = cand;
                }
            }
        }
    }

    if (r_a == 1) {
        b[int(gid)] = best;
    } else {
        a[int(gid)] = best;
    }
}
