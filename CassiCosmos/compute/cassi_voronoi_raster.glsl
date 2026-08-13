#[compute]
#version 450
// Cassi Voronoi Raster — piecewise-constant sampling of the cell state
// back onto the accelerator grid (MESHLESS_PLAN.md §10 integration).
// The mesh's ONLY output surface: the field render shader, the
// condensation scanner, and the river gradient all read the grid
// buffers — this pass writes them from the per-cell (site) state.
// One thread per grid cell.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float N_f;      // grid resolution per dimension
    float n_sites;  // site (cell) count
    float pad0;
    float pad1;
    float pad2;
    float pad3;
    float pad4;
    float pad5;
} pc;

layout(set = 0, binding = 0, std430) restrict readonly buffer Labels {
    int labels[];  // JFA site index per grid cell
};
layout(set = 0, binding = 1, std430) restrict readonly buffer PsiY {
    float psi_y[];
};
layout(set = 0, binding = 2, std430) restrict readonly buffer PsiI {
    float psi_i[];
};
layout(set = 0, binding = 3, std430) buffer FieldEY {
    float ey[];
};
layout(set = 0, binding = 4, std430) buffer FieldEI {
    float ei[];
};
layout(set = 0, binding = 5, std430) buffer FieldQ {
    float q[];
};

void main() {
    uint gid = gl_GlobalInvocationID.x;
    int Nn = int(pc.N_f);
    if (int(gid) >= Nn * Nn * Nn) return;
    int lab = labels[int(gid)];
    if (lab < 0 || lab >= int(pc.n_sites)) {
        lab = 0;
    }
    float y = psi_y[lab];
    float i_ = psi_i[lab];
    ey[int(gid)] = y;
    ei[int(gid)] = i_;
    q[int(gid)] = y * y + i_ * i_;
}
