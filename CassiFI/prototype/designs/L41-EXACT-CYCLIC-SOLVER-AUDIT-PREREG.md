# L41 Exact Cyclic Solver Audit — Frozen Preregistration

## Status: FROZEN — 2026-08-30

L41 is frozen after preserving L40 `SUPPORTS` and before any L41 test, runner, verifier, smoke, or canonical execution. It is a numerical audit of immutable L34; it introduces no field operator and never edits or reruns L34 evidence. The purpose is to decide whether L34's `REJECT` can be attributed to a malformed discrete solver before another field-law hypothesis is attempted.

## Bound operator and evidence identities

Bound immutable operator: `cassi.qi-exact-cyclic-strang.v1` from `cassi_exact_cyclic_field.py`.

Evidence identities:

- board: `cassi.l41.exact-cyclic-solver-audit-board.v1`;
- traces: `cassi.l41.exact-cyclic-solver-audit-traces.v1`;
- verification: `cassi.l41.exact-cyclic-solver-audit-verification.v1`.

New files:

- `tests/test_l41_exact_cyclic_solver_audit.py`;
- `verification/run_l41_exact_cyclic_solver_audit.py`;
- `verification/verify_l41_exact_cyclic_solver_audit.py`.

## Discrete cyclic operator

For one wave mode, one batch row, and either complex field coordinate `q=C` or `q=D`, define the seven-channel cyclic shift `P` by `(Pq)_j=q_{j+1 mod 7}` and the positive cyclic graph Laplacian

\[
L_7=2I-P-P^*.
\]

The implemented reciprocal force is

\[
\kappa(P+P^*-2I)q=-\kappa L_7q.
\]

Thus the linear active-coordinate equation is

\[
\dot q=v,\qquad
\dot v=-K_mq-\gamma_mv,
\qquad
K_m=\omega_m^2I+\kappa_mL_7.
\]

With the orthonormal seven-point DFT `F`,

\[
FL_7F^*=\operatorname{diag}\left(4\sin^2\frac{\pi k}{7}\right)_{k=0}^6,
\]

so every harmonic has

\[
\Omega_{km}^2=\omega_m^2+4\kappa_m\sin^2(\pi k/7)>0.
\]

This sign, the wraparound edge, DFT normalization, and harmonic ordering are frozen and independently reconstructed by the verifier.

## Phase-space inner product and balance law

For phase states `x=(q,v)` and `y=(p,w)`, define

\[
\langle x,y\rangle_{E,m}
=\operatorname{Re}\left(v^*w+q^*K_mp\right)/(1+\phi^2).
\]

Sum this inner product over both `C/VC` and `D/VD`, then apply the implementation's mode mean and channel aggregate. Because `K_m` is Hermitian positive definite, this is an inner product. Its quadratic energy is `E=1/2 <x,x>_E`. Orthonormal DFT coordinates must give the same value by Parseval.

For the linear damped equation,

\[
\frac{dE}{dt}=-\gamma_m\lVert v\rVert^2/(1+\phi^2)\le 0.
\]

At `gamma=0`, exact linear evolution must conserve `E`; with positive damping it must be non-increasing apart from declared floating-point tolerance.

## Declared split

The nonlinear potential is

\[
V_N(C,D)=\frac{\lambda_m}{4}(|C|^2+|D|^2)^2.
\]

Its exact kick subflow for duration `h` keeps positions fixed and applies

\[
VC\leftarrow VC-h\lambda_m(|C|^2+|D|^2)C,
\qquad
VD\leftarrow VD-h\lambda_m(|C|^2+|D|^2)D.
\]

The linear damped subflow is the exact L34 DFT-diagonal propagator. One L34 step is frozen as the Strang composition

\[
\Phi_h=K_N(h/2)\circ\exp(hA_L)\circ K_N(h/2).
\]

The epsilon moving average and amplitude/energy bounds occur after this physical split and are not included in the conservative inner product. Clamp-free controls are required so bounds cannot masquerade as solver stability.

## Frozen numerical controls

All synthetic complex states are deterministic analytic functions of channel and mode index; no random generator is used.

1. **Operator/Parseval:** the physical `L_7`, DFT eigenvalues, and physical-versus-harmonic phase-space energy agree within `2e-12` in float64.
2. **No-term/free drift:** with `K=0`, `gamma=0`, and `lambda=0`, one exact helper step equals `q+h v, v` within `1e-12` in float64. With `lambda=0`, the declared split equals the exact linear helper within `1e-12`.
3. **Independent spot check:** for four fixed modes under canonical L34 coefficients, one float64 exact helper step agrees within `2e-10` absolute error with an independently coded complex RK4 integration using 4096 uniform microsteps and the physical cyclic operator.
4. **Undamped conservation:** 2048 exact linear steps with canonical stiffness and zero damping have relative phase-space energy drift at most `2e-9`.
5. **Damped stability:** 2048 exact linear steps with canonical damping end below their initial energy; the largest positive one-step energy increment is at most `2e-10` of initial energy.
6. **Nonlinear split control:** the undamped Strang map followed by its exact negative-time composition returns to the initial phase state within `2e-10` relative norm. Across 2048 forward steps, the relative nonlinear Hamiltonian envelope is at most `2e-5`.
7. **Zero-state control:** the actual L34 float32 controller evolves an exactly zero field for 2048 steps to an exactly zero field with zero clamps.
8. **Driven stability:** on the canonical RX 7900 XTX, a float32 L34 field receives heartbeat once, then 256 ticks of eight steps, depositing one deterministic symbol every eighth tick. It remains finite with zero clamps, maximum mean dynamic energy at most `1.05`, and maximum absolute input-energy drift at most `2e-5`.

Focused CPU tests may use fewer repeated steps but must exercise every equation and control shape before canonical execution. They may repair evidence plumbing only; equations, schedules, thresholds, and coefficients cannot change.

## Independent verification and outcome

The verifier regenerates every analytic initial state; rebuilds `L_7`, `K_m`, and the inner product without importing audit-runner math; performs its own 4096-substep RK4 spot integration; recomputes all recorded errors and energy controls from raw arrays; validates immutable source hashes, schemas, shapes, device, dtype, finite values, and artifact hashes; and rejects unconsumed or undeclared evidence.

Return `PASS` only when all eight controls and evidence mechanics pass. Return `FAIL` for any violated control or integrity condition and `INCOMPLETE` only when canonical evidence is unavailable or interrupted. A `PASS` validates the frozen split implementation but does not reverse L34's functional `REJECT`; it instead excludes malformed discrete evolution as that result's explanation.

## Artifacts and stopping rule

Raw:

- `_diag/l41-exact-cyclic-solver-audit/l41-board.json`;
- `_diag/l41-exact-cyclic-solver-audit/l41-traces.npz`.

Verification:

- `artifacts/l41-exact-cyclic-solver-audit/L41-EXACT-CYCLIC-SOLVER-AUDIT-REPORT.md`;
- `artifacts/l41-exact-cyclic-solver-audit/l41-verification.json`.

Writes use atomic sibling replacement, canonical finite JSON, and NPZ with `allow_pickle=False`. Run focused CPU controls, one canonical GPU audit, and one independent verifier. Preserve the first complete result. Any solver change requires a new operator identity and preregistration.
