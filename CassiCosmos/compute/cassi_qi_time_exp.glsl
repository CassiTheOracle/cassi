#[compute]
#version 450
// Cassi Qi-time operator — φ-cadence multiscale mixing gate — EXPONENT arm
// (Wave-2 of the scale-telescoping program, 2026-08-14). This is a copy of
// the §32-guarded operator compute/cassi_qi_time.glsl (a FROZEN record, not
// edited) with ONE generalization: the cadence law is parameterized by an
// exponent `e`, so τ_k = round(φ^{e·k}).
//
//   e=1  ⇒ τ_k = round(φ^k)   = the §32 φ-cadence arm (BIT-IDENTICAL path)
//   e=2  ⇒ τ_k = round(φ^{2k}) = the DERIVED virial×Compton ladder (new)
//   e=0  ⇒ τ_k = round(1) = 1  = the uniform cadence control
// (The uniform_flag branch still forces τ_k=1 explicitly, as in §32.)
//
// Invariants (UNCHANGED from §32):
//   - OFF mode (active == 0): EY'=EY, EI'=EI — a byte-identical pure copy.
//   - The cell-local EY↔EI exchange and the TwistGate are unchanged:
//         rung k        = clamp(floor(log_φ(1/ρ)), 0, K=7)
//         gate G        = σ(φ⁴·(q − 1/φ)),  σ = ½(1+tanh),  q = EY²+EI²
//         twist m       = G·(EY−φ·EI)/(1+φ);  EY' = EY−m, EI' = EI+m
//     (a local exchange ≡ Σ(EY+EI) conserved cell-locally — the σ contract).
//   - Reads only the cell's own EY/EI (no neighbor reads, no in-dispatch
//     alias) — deterministic.
//
// ONLY the cadence exponent is parameterized (PC float index 9); with e=1 the
// arithmetic is identical to §32, so the φ¹ path reproduces §32's behavior
// bit-for-bit (cross-checked against §32's published G-values).
//
// Binding set 0 (identical to §32):
//   0 FieldEY (f32), 1 FieldEI (f32), 2 ProbeEY (f32, written), 3 ProbeEI (f32, written)
//
// Push-constant layout (10 floats — indices 0–8 identical to §32, 9 added):
//   0  N_f          grid N (64)
//   1  phi          golden ratio 1.618033988749895
//   2  t_f          global step count (cadence clock)
//   3  active_flag  0 = OFF pure copy, 1 = PROBE operator
//   4  uniform_flag 0 = φ-cadence (τ_k = round(φ^{e·k})), 1 = uniform (τ_k = 1)
//   5  K_f          max rung K (7)
//   6  inv_half     2/N (radius normalization)
//   7  q_thresh     1/φ (gate threshold)
//   8  q_sharp      φ⁴ (gate sharpness)
//   9  exp_f        cadence exponent e (1 ⇒ φ¹, 2 ⇒ φ², 0 ⇒ τ=1 uniform)

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
    float uniform_flag;     // 4 0 = φ-cadence (τ_k = round(φ^{e·k})), 1 = uniform (τ_k = 1)
    float K_f;       // 5 max rung K (7)
    float inv_half;  // 6 2/N (radius normalization)
    float q_thresh;  // 7 1/φ (gate threshold)
    float q_sharp;   // 8 φ⁴ (gate sharpness)
    float exp_f;     // 9 cadence exponent e (1 ⇒ φ¹, 2 ⇒ φ², 0 ⇒ τ=1 uniform)
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

    // Cadence τ_k: uniform → 1 every step; φ-cadence → round(φ^{e·k}).
    // NOTE: with e=1 (exp_f=1.0) the argument is pow(phi, 1.0*float(k)) ≡
    // pow(phi, float(k)) exactly (1.0*k == k in IEEE float), so this path is
    // BIT-IDENTICAL to the §32 shader's cadence.
    int tau;
    if (pc.uniform_flag > 0.5) {
        tau = 1;
    } else {
        float phik = pow(phi, pc.exp_f * float(k));
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
