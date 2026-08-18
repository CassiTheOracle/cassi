#[compute]
// Site-native render topology — deterministic K-nearest candidate graph.
//
// This is deliberately an oracle-compatible first slice, not the final
// renderer. Each invocation owns one site and scans every other site, keeping
// K nearest competitors. The ray traversal can then test only this compact
// candidate set; the pre-registered probe compares it against a full scan.
#version 450

layout(local_size_x = 64, local_size_y = 1, local_size_z = 1) in;

const int K = 64;
const float INF_D2 = 3.402823466e+38;

layout(push_constant, std430) uniform PC {
    float n_sites_f;
    float mode;
} pc;

layout(set = 0, binding = 0, std430) readonly buffer Sites {
    vec4 site_pos[];
};
layout(set = 0, binding = 1, std430) buffer CandidateIndex {
    int candidate_idx[];
};
layout(set = 0, binding = 2, std430) buffer CandidateDistance {
    float candidate_d2[];
};
void insert_candidate(int base, int site_idx, float d2, int count) {
    int slot = count;
    while (slot > 0) {
        int prev = slot - 1;
        float prev_d2 = candidate_d2[base + prev];
        int prev_idx = candidate_idx[base + prev];
        bool before = (d2 < prev_d2) || (d2 == prev_d2 && site_idx < prev_idx);
        if (!before) break;
        if (slot < K) {
            candidate_d2[base + slot] = prev_d2;
            candidate_idx[base + slot] = prev_idx;
        }
        slot = prev;
    }
    if (slot < K) {
        candidate_d2[base + slot] = d2;
        candidate_idx[base + slot] = site_idx;
    }
}

void main() {
    int s = int(gl_GlobalInvocationID.x);
    int ns = int(pc.n_sites_f);
    if (s >= ns) return;

    int base = s * K;
    for (int j = 0; j < K; ++j) {
        candidate_idx[base + j] = -1;
        candidate_d2[base + j] = INF_D2;
    }

    vec3 p = site_pos[s].xyz;
    int count = 0;
    for (int j = 0; j < ns; ++j) {
        if (j == s) continue;
        vec3 d = site_pos[j].xyz - p;
        float d2 = dot(d, d);
        if (!(d2 >= 0.0) || d2 >= INF_D2) continue;
        float worst = candidate_d2[base + K - 1];
        if (count < K || d2 < worst || (d2 == worst && j < candidate_idx[base + K - 1])) {
            insert_candidate(base, j, d2, min(count, K - 1));
            count = min(count + 1, K);
        }
    }
}
