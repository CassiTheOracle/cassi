#[compute]
// Sampled-JFA render adjacency — open-tile topology.
// mode 0 clears the symmetric bitset. mode 1 emits differing valid labels
// across interior +x/+y/+z faces. Boundary faces are intentionally dropped.
#version 450

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

layout(push_constant, std430) uniform PC {
    float grid_n_f;
    float n_sites_f;
    float words_per_site_f;
    float mode;
} pc;

layout(set = 0, binding = 0, std430) readonly buffer Labels { int labels[]; };
layout(set = 0, binding = 1, std430) buffer AdjacencyBits { uint adj[]; };

// Canonical JFA/cell label convention: x-major, z fastest.
int idx3(int x, int y, int z, int n) {
    return x * n * n + y * n + z;
}

void add_edge(int a, int b, int words, int ns) {
    if (a < 0 || b < 0 || a >= ns || b >= ns || a == b) return;
    uint ua = uint(a), ub = uint(b);
    atomicOr(adj[a * words + int(ub >> 5u)], 1u << (ub & 31u));
    atomicOr(adj[b * words + int(ua >> 5u)], 1u << (ua & 31u));
}

void main() {
    int gid = int(gl_GlobalInvocationID.x);
    int n = int(pc.grid_n_f);
    int ns = int(pc.n_sites_f);
    int words = int(pc.words_per_site_f);
    if (n <= 0 || ns <= 0 || words <= 0) return;

    if (int(pc.mode) == 0) {
        int total = ns * words;
        if (gid < total) adj[gid] = 0u;
        return;
    }

    int cells = n * n * n;
    if (gid >= cells) return;
    int x = gid / (n * n);
    int rem = gid - x * n * n;
    int y = rem / n;
    int z = rem - y * n;
    int a = labels[gid];
    if (a < 0 || a >= ns) return;

    if (x + 1 < n) add_edge(a, labels[idx3(x + 1, y, z, n)], words, ns);
    if (y + 1 < n) add_edge(a, labels[idx3(x, y + 1, z, n)], words, ns);
    if (z + 1 < n) add_edge(a, labels[idx3(x, y, z + 1, n)], words, ns);
}
