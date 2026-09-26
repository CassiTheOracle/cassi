# Particle Stationary Q2 Recovery Report

## Status: Tested—September 2026

## Abstract

This report records the canonical-preimage continuation campaign frozen in
`computations/particle_stationary_q2_recovery_v2_prereg.md`. The campaign
reconstructs the twelve saved PA32 endpoints from the registered fixed-charge
stationary solve, applies one deterministic strong-Wolfe L-BFGS continuation,
and evaluates the original Q1–Q4 gates without changing the action,
coefficient point, grids, seeds, field class, diagnostics, or thresholds.

Five structural primary arms satisfy Q1–Q4. The selected arm is
`P:separated_core`, with

$$
\widehat E=3.8542001269281165,
\qquad
\|\delta\widehat E\|_{\rm phys}=1.936974511462461\times10^{-4},
\qquad
|V_b|=1.891010199977997\times10^{-3}.
$$

The frozen primary and independent verifier agree on

$$
\boxed{\mathrm{PASS\text{—}Q2\text{-}QUALIFIED\ PRIMARY\ BACKGROUND}}.
$$

This establishes one Q2-qualified finite-grid background inside the declared
$C_4$-projected, $\mathfrak s$-independent, positive-carrier variational class.
Localization, domain convergence, resolution convergence, an unrestricted
minimum, a physical particle, and a fluctuation spectrum remain open. Every
domain arm and the selected high-resolution arm fails Q2, so the stronger
domain-and-resolution gate R6 fails.

## 1. Frozen question and intervention

The campaign asks whether a fixed continuation of the registered PA32
endpoints reaches the unchanged stationarity gate

$$
\|\delta\widehat E\|_{\rm phys}\leq3\times10^{-4},
\qquad
|V_b|\leq0.08.
$$

The static coefficient point remains

$$
\begin{aligned}
&\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
 =k_{Cx}=k_{C\mathfrak s}=u_C=1,\\
&u_\rho=u_\varphi=u_H=4,
\qquad e_C=0.75,
\qquad h_C=1.50,
\qquad q_C=4,
\qquad L_{\mathfrak s}=1.
\end{aligned}
$$

The source grids are retained:

- primary `P`: $(R,N)=(4,17)$;
- outer-domain `D`: $(R,N)=(5,21)$;
- selected high-resolution `H`: $(R,N)=(4,21)$.

Each saved endpoint receives one additional PyTorch L-BFGS call with
`max_iter=880`, `max_eval=1100`, `history_size=20`,
`tolerance_grad=1e-10`, `tolerance_change=1e-12`, and strong-Wolfe line search.
All thirteen continuations consume the 880-iteration cap, with 899–907
function evaluations. The evidence supports the frozen Q2 gate at that cap and
contains no optimizer early-stop event.

## 2. Canonical reconstruction and evidence integrity

The source artifacts store projected physical fields rather than the raw
optimization coordinates. The campaign reconstructs a canonical raw preimage,
reapplies the source projectors, boundary map, softplus carrier map, and exact
charge normalization, and requires the physical fields to round-trip within
$5\times10^{-12}$ in relative infinity norm. The largest independently
measured preflight round-trip residual is
$5.021564062290658\times10^{-16}$.

The source and reconstructed physical objective components and field-function
diagnostics agree under the frozen $10^{-8}+10^{-6}|x|$ comparison rule. The
comparison contract requires schema, finiteness, and nonnegativity for raw
coordinate gradient values because projected-out raw directions and the
carrier's pre-normalization scale are absent from the physical NPZ artifacts.
Q2 is recomputed from the physical first variation over exactly
$17N_{\rm interior}$ degrees of freedom.

The independent preflight returns `PASS`. The final verifier separately ports
the projection, finite-difference operators, PA32 energy, physical first
variation, cutoff virial, charge, gauge, flux, localization, comparison, and
selection calculations. It returns `pass: true`, `mismatches: []`, and the
same scientific verdict as the primary receipt.

The frozen recovery-source hashes are:

| Source | SHA-256 |
|---|---|
| preregistration | `e9c2bf8ab3c9001fdd40297eea2d0619e6388dd6d7786d1e0711102f6c4fe264` |
| primary program | `10e269fd2a669f58fbec0c20f4076d9e07f4a693de4ca40221d5bd29cca3a2a9` |
| independent verifier | `787520fcf3abb2ccbb66cc61a5ced29c39e1a9e75976468706ca58bae3de4707` |

The evidence directory is
`runs/20260902_particle_stationary_q2_recovery_v2/`. Its required receipts are
`preflight_verification.json`, `results.json`, and `verification.json`, plus
thirteen final NPZ field artifacts.

A separate preflight-only protocol at
`runs/20260902_particle_stationary_q2_recovery/` stops before optimization
because it asks a physical NPZ reconstruction to reproduce non-unique raw
coordinate gradient diagnostics. Its dedicated receipt verifier returns
`PASS` for the fail-closed shape: R1 passes, R2 fails, no arm runs, and the
verdict is `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`. That receipt contributes
implementation provenance and no stationary-field evidence.

## 3. Independently verified arm results

All thirteen continued arms pass Q1, Q3, and Q4. Q2 is decided by the physical
gradient because every cutoff virial lies below $0.08$.

| Arm | $\widehat E$ | physical gradient RMS | cutoff virial | Q2 |
|---|---:|---:|---:|:---:|
| P separated core | 3.854200127 | $1.937\times10^{-4}$ | 0.001891 | PASS |
| P merged core | 3.854209186 | $2.193\times10^{-4}$ | 0.005140 | PASS |
| P closed loop | 3.854224530 | $2.968\times10^{-4}$ | 0.002476 | PASS |
| P carrier lump | 3.854203635 | $1.915\times10^{-4}$ | 0.002369 | PASS |
| P delocalized | 3.854765731 | $2.073\times10^{-3}$ | 0.001174 | FAIL |
| P split multicore | 3.854217157 | $2.443\times10^{-4}$ | 0.003775 | PASS |
| H separated core | 3.867888616 | $4.696\times10^{-4}$ | 0.0000321 | FAIL |
| D separated core | 3.554309548 | $6.879\times10^{-4}$ | 0.000994 | FAIL |
| D merged core | 3.554300076 | $6.400\times10^{-4}$ | 0.005238 | FAIL |
| D closed loop | 3.554490101 | $8.931\times10^{-4}$ | 0.003980 | FAIL |
| D carrier lump | 3.554292310 | $6.868\times10^{-4}$ | 0.003658 | FAIL |
| D delocalized | 3.555190957 | $1.811\times10^{-3}$ | 0.002387 | FAIL |
| D split multicore | 3.554404038 | $8.113\times10^{-4}$ | 0.012816 | FAIL |

The five Q2-qualified structural primary energies occupy a narrow interval of
$2.4403\times10^{-5}$. Under the frozen lowest-energy rule and
$10^{-10}$ tie tolerance, `separated_core` is selected. The seed label does not
establish a distinct topological sector or an unrestricted global minimum.

## 4. Selected finite-grid background

The independently recomputed selected-arm diagnostics are:

| Quantity | Value | Gate consequence |
|---|---:|---|
| charge $q_C$ | 4.0 | Q1 pass |
| charge relative error | 0 | Q1 pass |
| fixed-boundary residual | 0 | Q1 pass |
| physical gradient RMS | $1.9369745\times10^{-4}$ | Q2 pass |
| cutoff virial | $1.8910102\times10^{-3}$ | Q2 pass |
| gauge-fixing fraction | $2.2954\times10^{-8}$ | Q3 pass |
| outer flux RMS | $8.4814\times10^{-7}$ | Q4 pass |
| outer magnetic number | 0 | Q4 pass |
| carrier radius $R_C$ | 2.56816 | exceeds $R/2=2$ |
| outer carrier fraction | 0.0154769 | exceeds $10^{-3}$ |
| $\widehat\omega_C$ | 0.961914 | exceeds 0.73 and $e_C=0.75$ |
| maximum density depletion | 0.181912 | exceeds the 0.10 floor |

The selected field is a valid Q1–Q4 background for a finite-grid constrained
variation. It fails three parts of the registered localization predicate and
the raw carrier-retention bound. The campaign therefore supplies no localized
particle or retained bound carrier claim.

## 5. Recovery gates and stronger qualification

| Gate | Result | Meaning |
|---|:---:|---|
| R1 | PASS | immutable source hashes match and execution-time authority hashes are recorded |
| R2 | PASS | all twelve source endpoints pass canonical reconstruction preflight |
| R3 | PASS | every required continuation returns finite scheduled output |
| R4 | PASS | independent recomputation matches every required metric, gate, and selection |
| R5 | PASS | at least one structural primary arm passes Q1–Q4 |
| R6 | FAIL | global Q5 domain/control and selected-arm Q6 resolution qualification do not pass |

All six domain arms fail Q2. The primary and domain delocalized controls also
fail Q2, and the selected high-resolution arm fails Q2. The five structural
Q5 comparisons, delocalized control, and Q6 comparison are therefore invalid
at their prerequisite quality layer. No domain or resolution trend is inferred
from their raw energies.

The frozen verdict tree stops at R6:

$$
\boxed{\mathrm{PASS\text{—}Q2\text{-}QUALIFIED\ PRIMARY\ BACKGROUND}}.
$$

## 6. Scientific boundary and next computation

This result closes the numerical prerequisite that blocked construction of a
finite-grid PA42 physical Hessian. It establishes numerical stationarity only
inside one finite Cartesian, $C_4$-projected, $\mathfrak s$-independent,
positive-carrier ansatz at one uncalibrated coefficient point.

The following remain open:

- outer-domain and resolution convergence;
- carrier localization and the retention inequality;
- non-$C_4$ and fully non-axisymmetric perturbations;
- higher scale and transverse modes;
- carrier phase gradients, sign changes, and exact interior zeros;
- topology-changing paths and unrepresented multicore sectors;
- infinite-domain existence and a continuum limit;
- physical calibration, mass, radius, electric charge, spin, and statistics;
- the complete fixed-charge, Gauss, boundary, and gauge-projected Hessian;
- temporal coefficients, the mixed PA43 pencil, continuum thresholds, decay,
  and lifetime.

The next admissible calculation is a preregistered finite-grid PA42 Hessian on
`runs/20260902_particle_stationary_q2_recovery_v2/fields_P_separated_core.npz`.
It must construct the joint fixed-charge,
linearized-Gauss, boundary, and gauge quotient directly, classify every zero
mode, and report the lowest physical eigenvalues. The PA43 dynamical spectrum
additionally requires selected temporal groups. Domain and resolution support
for either operator remains a separate qualification.

## References

- `computations/particle_stationary_q2_recovery_v2_prereg.md`—frozen recovery question, reconstruction, optimizer, gates, and verdict tree.
- `computations/particle_stationary_q2_recovery_v2.py`—primary canonical-preimage continuation program.
- `computations/verify_particle_stationary_q2_recovery_v2.py`—independent preflight, diagnostic, gate, and receipt verifier.
- `computations/verify_particle_stationary_q2_recovery_v1_result.py`—fail-closed verifier for the preflight-only protocol.
- `computations/particle-stationary-bvp-pre-registration.md`—source coefficient point, field class, diagnostics, and gates.
- `computations/particle-stationary-bvp-report.md`—source fixed-budget campaign receipt.
- `foundations/particle-stationary-action-closure.md`—PA32 action and PA42–PA43 fluctuation qualification authority.
- `foundations/matter-completion-boundary.md`—full matter-completion scope boundary.
- `foundations/core-trapped-charge-support.md`—neutral-carrier support and retention conditions.
- `foundations/nonabelian-magnetic-core-boundary.md`—auxiliary core and confinement boundary.
