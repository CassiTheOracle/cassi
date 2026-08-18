#[compute]
// Exact sampled-JFA adjacency compaction.
// mode 0: count set bits per site; mode 1: deterministic ascending fill.
// The host dispatches mode 0, performs an exclusive scan of degree[] into
// offsets[0..n_sites], then dispatches mode 1. No degree cap is applied.
#version 450

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float n_sites_f;
    float words_per_site_f;
    float mode;
    float _pad0;
} pc;

layout(set = 0, binding = 0, std430) readonly buffer AdjacencyBits { uint adj[]; };
layout(set = 0, binding = 1, std430) readonly buffer Offsets { uint offsets[]; };
layout(set = 0, binding = 2, std430) buffer Degree { uint degree[]; };
layout(set = 0, binding = 3, std430) buffer Neighbors { uint neighbors[]; };

void main() {
    int s = int(gl_GlobalInvocationID.x);
    int ns = int(pc.n_sites_f + 0.5);
    int words = int(pc.words_per_site_f + 0.5);
    if (s >= ns || words <= 0) return;

    if (int(pc.mode + 0.5) == 0) {
        uint count = 0u;
        int base = s * words;
        for (int w = 0; w < words; ++w) count += uint(bitCount(adj[base + w]));
        degree[s] = count;
        return;
    }

    uint dst = offsets[s];
    int base = s * words;
    // Word order and bit order are ascending site IDs, so each CSR row is
    // deterministic and exactly matches the symmetric bitset.
    for (int w = 0; w < words; ++w) {
        uint bits = adj[base + w];
        while (bits != 0u) {
            uint bit = uint(findLSB(bits));
            neighbors[dst++] = uint(w) * 32u + bit;
            bits &= bits - 1u;
        }
    }
}
