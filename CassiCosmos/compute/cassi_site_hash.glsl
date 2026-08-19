#[compute]
// canonical layout: scripts/contracts/layout.gd §PC — 9 floats (36 B); set 0: bindings 0-4
#version 450
// Uniform-grid hash over shortlist tile positions. Tile space is a stable
// [0,2*extent] domain; the host converts render-local site positions to tile
// positions before this pass. Per-axis origins/cell widths preserve anisotropy.
layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;
layout(set = 0, binding = 0, std430) readonly buffer Shortlist { vec4 sl[]; };
layout(set = 0, binding = 1, std430) buffer CellStart { uint cell_start[]; };
layout(set = 0, binding = 2, std430) buffer CellSites { uint cell_sites[]; };
layout(set = 0, binding = 3, std430) coherent buffer CellCount { uint cell_count[]; };
layout(set = 0, binding = 4, std430) readonly buffer ShortlistCount { uint scnt; };
layout(push_constant, std430) uniform PC {
    float ext_x; float ext_y; float ext_z; float h; float n_shortlist;
    float origin_x; float origin_y; float origin_z; float mode;
} pc;

uvec3 tile_cell(vec3 p) {
    uint H = uint(pc.h);
    vec3 ext = vec3(pc.ext_x, pc.ext_y, pc.ext_z);
    vec3 origin = vec3(pc.origin_x, pc.origin_y, pc.origin_z);
    vec3 cs = 2.0 * ext / max(vec3(pc.h), vec3(1.0));
    return uvec3(clamp(ivec3(floor((p - origin) / cs)), ivec3(0), ivec3(int(H) - 1)));
}
uint cell_of(vec3 p) {
    uint H = uint(pc.h);
    uvec3 c = tile_cell(p);
    return c.x + H * (c.y + H * c.z);
}

void main() {
    uint gid = gl_GlobalInvocationID.x;
    uint H = uint(pc.h);
    uint ncells = H * H * H;
    int mode = int(pc.mode);
    if (mode == 0) {
        if (gid < ncells) cell_count[gid] = 0u;
        return;
    }
    int ns = min(int(pc.n_shortlist), int(scnt));
    if (mode == 1) {
        if (gid >= uint(ns)) return;
        atomicAdd(cell_count[cell_of(sl[gid].xyz)], 1u);
        return;
    }
    if (mode == 2) {
        if (gid != 0u) return;
        uint acc = 0u;
        for (uint c = 0u; c < ncells; c++) {
            uint count = cell_count[c];
            cell_start[c] = acc;
            cell_count[c] = acc;
            acc += count;
        }
        cell_start[ncells] = acc;
        return;
    }
    if (gid >= uint(ns)) return;
    uint c = cell_of(sl[gid].xyz);
    uint slot = atomicAdd(cell_count[c], 1u);
    cell_sites[slot] = gid;
}
