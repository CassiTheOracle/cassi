#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 8 floats (32 B); set 0: bindings 0-2
#version 450
// Cassi JFA — jump-flooding Voronoi construction on the N³ accelerator
// grid (MESHLESS_PLAN.md Stage 1). The grid is a lookup accelerator
// no physics lives on it. Each pass floods every cell's current
// best site-index out to its 26-neighborhood at distance `jump`, keeping
// the site nearest the cell CENTER; the doubling sweep (1..N/2) fills
// the grid from the scattered seeds, the halving sweep refines it, and
// TWO trailing jump-1 passes resolve the tiny fraction of ambiguous
// boundary cells the index-space flood can leave on a STRETCHED box (the
// physical nearest site can sit just outside the reachable neighborhood):
// repeating the complete-graph jump-1 pass converges them to the exact
// Voronoi (0.0000 mislabel — proven in stage1b_aniso.py gate Ga). At the
// cube it is a no-op (the 11-pass flood is already exact), so the cube
// batteries and the JFA PC size are untouched. Two extra passes keep the
// total ODD so the trailing identity copy still re-homes the result from B.
// Proven in numpy (research/meshless/stage1_jfa3d.py, gate G0; and
// stage1b_aniso.py for the anisotropic metric): 13 passes on the BCC
// seed lattice reproduce the exact Voronoi on every cell (0.0000
// mislabel rate vs KDTree / brute-force nearest site).
//
// Labels ping-pong between two buffers: read_a = 1 reads A/writes B,
// read_a = 0 reads B/writes A (the GDScript side toggles per pass; an
// odd number of passes leaves the result in B, so a final identity
// copy pass — jump = 0 — re-homes it into A for the cell shaders).
// The empty-cell sentinel is INT_MAX (the GPU-side analog of numpy's
// scatter: atomicMin of the site index per cell).
//
// ANISOTROPIC METRIC: the accelerator grid maps index space onto the
// STRETCHED physical box [0, 2·extent_x) × [0, 2·extent_y) ×
// [0, 2·extent_z) with per-axis cell spacings hx/hy/hz = 2·extent_i/N.
// Grid cell centers are ((i+0.5)·hx, (j+0.5)·hy, (k+0.5)·hz) and the
// sites carry PHYSICAL coordinates on the same box. JFA is metric-
// AGNOSTIC: the flood only propagates candidate site labels through
// the 26-neighborhood; the per-cell winner is picked by whichever
// candidate's PHYSICAL distance to the (stretched) cell center is
// smallest. That comparison is exactly the Euclidean metric on the
// box, so turning per-axis spacings on does not change the algorithm
// at all — only the coordinate used for the comparison. At hx=hy=hz=h
// this reduces bit-for-bit to the original isotropic pass (jump
// indices and wraparound are unchanged; (i+0.5)·h is untouched).
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float N_f;          // grid resolution per dimension
    float jump;         // flood distance in cells (0 = identity copy)
    float read_a;       // 1.0: read A, write B ; 0.0: read B, write A
    float n_sites;      // site count (label validity bound)
    float hx;           // x cell spacing (2·extent_x / N)
    float hy;           // y cell spacing (2·extent_y / N)
    float hz;           // z cell spacing (2·extent_z / N)
    float pad0;
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

    float cx = (float(i) + 0.5) * pc.hx;
    float cy = (float(j) + 0.5) * pc.hy;
    float cz = (float(k) + 0.5) * pc.hz;

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
