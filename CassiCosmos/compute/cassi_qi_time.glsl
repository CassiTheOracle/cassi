#[compute]
#version 450
// Cassi Qi-time operator — the φ-cadence multiscale mixing gate (GUARDED
// PROTOTYPE, 2026-08-14). Plan cassi-mind-plugin.md §32 / §31-4: Qi gates
// the mixing between the two fluids, so lattice scales are also TIME scales.
// Implements the cord architecture's per-rung update schedule as a dynamic
// multiscale operator on the 64³ two-fluid grid.
//
// Operator:
//   cell rung        k = clamp(floor(log_φ(1/ρ)), 0, K),  ρ = d/(N/2)
//   rung cadence     τ_k = round(φ^k) global steps   (uniform=1 ⇒ τ_k = 1)
//   gate             G = σ(φ⁴·(q − 1/φ)), σ = ½(1+tanh), q = EY²+EI²
//   twist            m = G·(EY−φ·EI)/(1+φ);  EY' = EY−m, EI' = EI+m
//
// The twist is a LOCAL EY↔EI exchange (m moves from EY to EI at the same
// cell), so Σ(EY+EI) is conserved cell-locally — the cadence schedule
// cannot break charge conservation (the σ contract, plan §12). When the
// gate is open (G→1) one full twist closes ε = EY−φ·EI to 0 exactly.
//
// OFF mode (active == 0): EY'=EY, EI'=EI — a bit-identical pure copy (the
// guarded no-op baseline). PROBE mode (active == 1): apply the operator in
// a scratch copy (probe buffers). Reads only the cell's own EY/EI (no
// neighbor reads, no in-dispatch alias) — deterministic.
//
// Bindings (set 0):
//   0 FieldEY (f32), 1 FieldEI (f32), 2 ProbeEY (f32, written), 3 ProbeEI (f32, written)

layout(local_size_x = 4, local_size_y = 4, local_size_z = 4) in;

layout(set = 0, binding = 0, std430) restrict buffer FieldEY { float ey[]; };
layout(set = 0, binding = 1, std430) restrict buffer FieldEI { float ei[]; };
layout(set = 0, binding = 2, std430) restrict buffer ProbeEY { float pey[]; };
layout(set = 0, binding = 3, std430) restrict buffer ProbeEI { float pei[]; };

layout(push_constant, std430) uniform PC {
    float N_f;       // 0 grid N (64)
    float phi;       // 1 golden ratio
    float t_f;       // 2 global step count (cadence clock)
    float active_flag;      // 3 0 = OFF pure copy, 1 = PROBE operator
    float uniform_flag;     // 4 0 = φ-cadence (τ_k = round(φ^k)), 1 = uniform (τ_k = 1)
    float K_f;       // 5 max rung K (7)
    float inv_half;  // 6 2/N (radius normalization)
    float q_thresh;  // 7 1/φ (gate threshold)
    float q_sharp;   // 8 φ⁴ (gate sharpness)
} pc;

void main() {
    int N = int(pc.N_f);
    ivec3 gid = ivec3(gl_GlobalInvocationID);
    if (gid.x >= N || gid.y >= N || gid.z >= N) return;

    int id = gid.x + N * (gid.y + N * gid.z);

    // OFF mode: bit-identical pure copy — the guarded no-op baseline.
    if (pc.active_flag < 0.5) {
        pey[id] = ey[id];
        pei[id] = ei[id];
        return;
    }

    // ── PROBE mode: the cadence operator ────────────────────────────────
    int step_i = int(floor(pc.t_f + 0.5));

    // Rung from normalized radius ρ = d/(N/2).
    float halfn = 0.5 * float(N);
    float cx = float(gid.x) - halfn + 0.5;   // cell-center coordinate
    float cy = float(gid.y) - halfn + 0.5;
    float cz = float(gid.z) - halfn + 0.5;
    float rx = cx / halfn, ry = cy / halfn, rz = cz / halfn;
    float rho = sqrt(rx * rx + ry * ry + rz * rz);
    rho = clamp(rho, 1e-6, 1.0);            // avoid log(0) at the very center

    float phi = pc.phi;
    // t = log_φ(1/ρ); clamp to [0, K]. rho=1 → t=0 (rung 0, cadence 1 → always).
    float log_phi_inv = log(1.0 / rho) / log(phi);
    float t = max(0.0, log_phi_inv);
    int K = int(floor(pc.K_f + 0.5));
    float kf = min(t, float(K));
    int k = int(floor(kf + 0.5));

    // Cadence τ_k: uniform → 1 every step; φ-cadence → round(φ^k).
    int tau;
    if (pc.uniform_flag > 0.5) {
        tau = 1;
    } else {
        float phik = pow(phi, float(k));
        tau = int(floor(phik + 0.5));
        if (tau < 1) tau = 1;
    }

    float eyv = ey[id];
    float eiv = ei[id];

    // Scheduled step only (τ_k divides the global step) applies the twist.
    if (step_i % tau == 0) {
        float q = eyv * eyv + eiv * eiv;
        float arg = pc.q_sharp * (q - pc.q_thresh);
        float G = 0.5 * (1.0 + tanh(arg));   // TwistGate: opens at q > 1/φ
        float eps = eyv - phi * eiv;
        float m = G * eps / (1.0 + phi);
        pey[id] = eyv - m;
        pei[id] = eiv + m;
    } else {
        // Not this rung's step — no mixing; keep the field (still a managed copy).
        pey[id] = eyv;
        pei[id] = eiv;
    }
}
