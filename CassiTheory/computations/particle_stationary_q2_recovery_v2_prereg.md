# Particle Stationary Q2 Canonical-Preimage Recovery Campaign

## Status: Preregistered—September 2026

## Abstract

This campaign tests whether the finite-dimensional stationary backgrounds in the registered PA32 campaign satisfy its unchanged Q2 first-variation and cutoff-virial gate after a fixed deterministic continuation of the numerical optimizer. The action, coefficient point, fixed charge, field class, seeds, grids, projectors, diagnostics, gate thresholds, and candidate-selection rule remain fixed.

The sole numerical intervention is one additional strong-Wolfe L-BFGS call
capped at 880 optimizer iterations for every primary and domain endpoint.
Each continuation begins from the corresponding hash-verified field artifact
in `runs/20260901_particle_stationary_bvp/`. A finer-grid arm is admitted only
by the same lowest-energy qualified-primary rule as the source campaign and
receives the original 800-step Adam plus 120-iteration L-BFGS schedule followed
by the same capped continuation call.

A passing result establishes a Q2-qualified full-field background inside the
registered finite Cartesian, $C_4$-projected, positive-carrier ansatz. It does
not establish domain or resolution convergence unless the source Q5 domain and
source Q6 resolution comparisons pass, and it does not establish a physical
particle, unrestricted minimum, spectrum, lifetime, spin, statistics, or
calibration.

## 1. Question

Does fixed-budget continuation of the registered PA32 endpoints produce at least one structural primary arm satisfying the unchanged Q1–Q4 gates, including

$$
\|\delta\widehat E\|_{\rm phys}\le 3\times10^{-4},
\qquad
|V_b|\le 0.08?
\tag{QR1}
$$

The run tests numerical stationarity at the frozen coefficient point. It introduces no physical term and makes no coefficient scan.

## 2. Source authority

The campaign uses the following source graph:

- `foundations/particle-stationary-action-closure.md`—PA32 functional, PA33–PA41 qualification gates, and PA42–PA43 fluctuation operators;
- `foundations/core-trapped-charge-support.md`—positive neutral-carrier sector;
- `foundations/nonabelian-magnetic-core-boundary.md`—non-Abelian magnetic boundary sector;
- `computations/particle-stationary-bvp-pre-registration.md`—source coefficient point, grids, seeds, diagnostics, and decision tree;
- `computations/particle_stationary_bvp.py`—source discretization and primary diagnostic implementation;
- `computations/verify_particle_stationary_bvp.py`—independent field diagnostic implementation;
- `computations/particle-stationary-bvp-report.md`—source receipt interpretation;
- `runs/20260901_particle_stationary_bvp/results.json`—source machine receipt;
- `runs/20260901_particle_stationary_bvp/verification.json`—source independent verification receipt.

The immutable source-snapshot manifest contains the SHA-256 hashes of
`results.json`, `verification.json`, the source preregistration, report,
program, verifier, and all twelve source NPZ artifacts. The source program,
verifier, preregistration, and NPZ bytes must match the hashes carried by the
source receipt; the receipt, verification receipt, and report receive separate
manifest hashes because they are not self-hashed there. Current authority
documents receive a distinct source-graph hash group and are not compared with
the frozen receipt's earlier authority hashes. Any required mismatch stops the
campaign with `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`.

The recovery manifest additionally hashes this preregistration, the recovery
primary program, and the independent recovery verifier. The primary and
verifier receipts must carry identical values for this recovery-source group.

## 3. Frozen physical problem

The recovery uses the PA32 dimensionless static energy

$$
\widehat E_{\rm obj}
=
\widehat E
+
\frac{\xi_{\rm gf}}{2}
\int (\partial_i a_i^a)^2\,d^3\widehat x,
\tag{QR2}
$$

with the source coefficient point

| Quantity | Frozen value |
|---|---:|
| $\alpha_{\mathfrak s}$ | $1.0$ |
| $u_\rho$ | $4.0$ |
| $u_\varphi$ | $4.0$ |
| $\gamma_x$ | $1.0$ |
| $\gamma_{\mathfrak s}$ | $1.0$ |
| $u_H$ | $4.0$ |
| $k_{Cx}$ | $1.0$ |
| $k_{C\mathfrak s}$ | $1.0$ |
| $e_C$ | $0.75$ |
| $h_C$ | $1.50$ |
| $u_C$ | $1.0$ |
| $q_C$ | $4.0$ |
| $L_{\mathfrak s}$ | $1.0$ |
| $\xi_{\rm gf}$ | $1.0$ |

The lowest no-flux scale mode remains active, so all $\partial_{\mathfrak s}$, $a_{\mathfrak s}$, and scale-link terms vanish at this coefficient point. The temporal fields remain in the Gauss-compatible stationary sector $a_0^a=0$. No represented degree of freedom changes.

The grids remain

| Family | $R$ | $N$ | $\Delta x$ |
|---|---:|---:|---:|
| Primary `P` | $4.0$ | $17$ | $0.5$ |
| Domain `D` | $5.0$ | $21$ | $0.5$ |
| Finer `H` | $4.0$ | $21$ | $0.4$ |

The structural basins remain `separated_core`, `merged_core`, `closed_loop`, `carrier_lump`, and `split_multicore`. The `delocalized` basin remains the control. Basin labels record initialization provenance only.

## 4. Endpoint reconstruction

### 4.1 Source artifacts

Each `P` and `D` arm begins from its source NPZ artifact. The source receipt must report every arm complete, and the NPZ SHA-256 must equal the receipt hash.

The saved physical arrays are $\psi_R$, $\psi_I$, $h$, $a$, and the positive normalized carrier $c$. The recovery reconstructs raw variables by

$$
\psi_R^{\rm raw}=\psi_R,
\quad
\psi_I^{\rm raw}=\psi_I,
\quad
h^{\rm raw}=h,
\quad
a^{\rm raw}=a,
\tag{QR3}
$$

and, at every interior node,

$$
w=\operatorname{softplus}^{-1}(c)
=c+\log[-\operatorname{expm1}(-c)].
\tag{QR4}
$$

Boundary values of $w$ are set to zero because the fixed mask removes them before the carrier normalization. The standard $C_4$ projectors, boundary map, softplus, and exact charge normalization are then reapplied.

### 4.2 Reconstruction gates

Before the primary program starts, the recovery verifier runs in preflight
mode and writes `preflight_verification.json`. The primary program requires a
passing preflight receipt whose source hashes match its own manifest.

All twelve source arms must pass:

1. each NPZ is loaded with `allow_pickle=False` and has exactly the keys `x`,
   `psi_real`, `psi_imag`, `h`, `a`, and `c`;
2. every array is C-contiguous `float64`, has the family-specific registered
   shape, and uses the exact registered one-dimensional $x$ grid and spacing;
3. every source field and reconstructed field is finite;
4. the relative-infinity $C_4$ projection residual is at most
   $5\times10^{-12}$ and the fixed-shell residual is at most $10^{-12}$;
5. every reconstructed raw variable, including every interior $w$, is finite;
6. every interior source carrier value is strictly positive;
7. the source and reconstructed charges satisfy the original Q1 tolerance;
8. the reconstructed boundary residual is at most $10^{-12}$;
9. every reconstructed objective term and physical diagnostic is finite;
10. reconstructed objective components and field-function diagnostics agree
    with the source receipt under (QR10);
11. the source and reconstructed raw-coordinate objective-gradient RMS and
    maximum are finite and nonnegative. These two values serve as schema
    checks. The physical NPZ does not encode projected-out raw coordinates or
    the carrier's pre-normalization scale; Q2 is evaluated from the physical
    first variation;
12. for each field $f\in\{\psi_R,\psi_I,h,a,c\}$,

$$
\operatorname{rel}_\infty(f',f)
=
\frac{\|f'-f\|_\infty}
{\max(\|f\|_\infty,10^{-12})}
\le 5\times10^{-12}.
\tag{QR5}
$$

A failure returns `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`; no arm is optimized.

## 5. Frozen continuation algorithm

### 5.1 Primary and domain arms

Every source `P` and `D` endpoint receives one fresh PyTorch L-BFGS optimizer
call with

| Setting | Frozen value |
|---|---:|
| `max_iter` | `880` |
| `max_eval` | `1100` |
| `history_size` | `20` |
| `tolerance_grad` | `1e-10` |
| `tolerance_change` | `1e-12` |
| line search | `strong_wolfe` |
| dtype | `float64` |
| deterministic algorithms | enabled |
| device selector | `CUDA_VISIBLE_DEVICES=0` |

Resetting the L-BFGS history changes the numerical path, while the objective
and admissible field space remain unchanged. `max_iter=880` is an upper bound:
PyTorch may return earlier under the frozen gradient, parameter-change, or
objective-change stopping tests, and strong-Wolfe closure evaluations remain
capped by `max_eval=1100`. The cap extends the source maximum of 120 to at most
1000 quasi-Newton optimizer iterations across the two calls. Early return is
accepted only as the unmodified optimizer outcome; Q1–Q4 still decide whether
the resulting field qualifies.

All six primary arms run before selection. The finer-grid basin is the lowest-physical-energy structural `P` basin that passes Q1–Q4. Ties within $10^{-10}$ follow the frozen basin order. No structural basin is selected from its source energy, source gradient, or expected recovery behavior.

All six domain arms run after the finer-grid arm.

### 5.2 Finer-grid arm

If a structural `P` arm passes Q1–Q4, the selected `H` arm starts from its registered analytic seed and receives:

1. Adam for 800 steps, with learning rate $0.020$ for steps 0–399 and $0.005$ for steps 400–799;
2. strong-Wolfe L-BFGS with `max_iter=120`, `max_eval=150`, `history_size=20`, `tolerance_grad=1e-10`, and `tolerance_change=1e-12`;
3. a fresh continuation L-BFGS stage with the settings in §5.1.

If no structural `P` arm passes Q1–Q4, no `H` arm runs.

### 5.3 Checkpoint rule

The program writes its receipt after preflight and after every completed arm. A process restart may resume only when every frozen source hash, schedule value, completed-arm artifact hash, and recorded arm order matches. Completed arms are never rerun. An interrupted arm may restart from its original frozen input because it has no accepted output artifact.

No coefficient, gate, tolerance, seed, grid, optimizer setting, reconstruction formula, arm order, or stopping rule may change after the first arm begins.

## 6. Frozen diagnostics and gates

The primary program evaluates the source PA39 diagnostics. The recovery
verifier contains a separate NumPy/PyTorch port of the finite-difference
operators, energy, physical first variation, cutoff virial, charge, boundary
residual, gauge divergence, gauge-fixing fraction, outer curvature flux,
magnetic number, localization quantities, and frequency. It does not import or
invoke either stationary primary program or the source verifier's hard-coded
receipt contract.

The physical first-variation RMS uses exactly

$$
M=17N_{\rm interior}
=
(2+2+3+9+1)N_{\rm interior},
\tag{QR6a}
$$

for the real and imaginary doublet components, adjoint triplet, spatial
connection, and carrier tangent. The recovery verifier uses the same declared
inner product and component count.

For every completed arm:

### Q1—Charge and boundary

$$
\text{relative charge error}\le5\times10^{-12},
\qquad
\text{maximum fixed-boundary residual}\le10^{-12}.
\tag{QR6}
$$

### Q2—Physical stationarity

$$
\|\delta\widehat E\|_{\rm phys}\le3\times10^{-4},
\qquad
|V_b|\le0.08.
\tag{QR7}
$$

### Q3—Gauge representative

$$
\|\partial_i a_i\|_{\rm RMS}\le0.02,
\qquad
\frac{E_{\rm gf}}{\max(|\widehat E|,10^{-12})}\le0.01.
\tag{QR8}
$$

### Q4—Outer magnetic boundary

$$
\Phi_{\partial\Omega}\le0.05,
\qquad
|N_G^{\rm outer,disc}|\le10^{-10}.
\tag{QR9}
$$

The independent verifier compares every recomputed scalar with the primary receipt using

$$
|x_{\rm verify}-x_{\rm primary}|
\le10^{-8}+10^{-6}|x_{\rm verify}|.
\tag{QR10}
$$

A verifier mismatch makes the recovery receipt invalid regardless of its scientific verdict.

## 7. Background selection and convergence

A structural `P` arm is a Q2-qualified primary background only when Q1–Q4 all
pass. The selected background is the lowest-energy such arm under the frozen
tie rule.

The source Q5 domain gate remains global. Every one of the five structural
`P`/`D` pairs must pass Q1–Q4 and satisfy

$$
\operatorname{reldiff}(E_P,E_D)\le0.05,
\quad
|L_P-L_D|\le0.75,
\quad
|\omega_{C,P}-\omega_{C,D}|\le0.10,
\tag{QR11}
$$

plus the registered localized or normalized carrier-radius comparison at
relative difference at most $0.10$. The delocalized control follows the source
decision: a localized pair uses those same comparisons; a nonlocalized pair
must satisfy

$$
\operatorname{reldiff}(R_{C,D}/R_D,R_{C,P}/R_P)\le0.10,
\qquad
E_{c4,D}\le E_{c4,P}+10^{-6},
\tag{QR12}
$$

$$
\frac{|E_D-e_Cq_C|}{e_Cq_C}\le0.25.
\tag{QR13}
$$

A localization mismatch fails Q5.

The source Q6 gate applies only to the selected `H` arm. It must pass Q1–Q4
and agree with its selected `P` counterpart under the Q5 energy, core-length,
frequency, and applicable radius tolerances.

A Q2-qualified primary background can seed the fixed-charge Hessian
calculation. The global Q5 and selected-arm Q6 gates determine whether that
background also carries finite-box domain and resolution support.

## 8. Recovery gates

| Gate | Pass condition |
|---|---|
| R1 | Every immutable source-snapshot hash matches and current authority hashes are recorded separately |
| R2 | All twelve saved endpoints pass the raw-variable, forward-round-trip, charge, boundary, objective, and diagnostic preflight |
| R3 | Every required optimizer call returns with finite fields, objective, and gradients under the frozen caps and stopping tests |
| R4 | Independent recomputation agrees under (QR10), including exact gate booleans and selection |
| R5 | At least one structural `P` arm passes Q1–Q4 |
| R6 | The full five-pair plus delocalized-control Q5 gate and the selected-arm Q6 gate pass |

R5 is the gate for the requested Q2-qualified full-field background. R6 is a
stronger domain-and-resolution qualification and does not replace R5.

## 9. Frozen verdict tree

Evaluate in this order:

1. Any R1 or R2 failure before optimization:
   `INCONCLUSIVE—IMPLEMENTATION PREFLIGHT`.
2. Any missing, nonfinite, schedule-incomplete, or independently mismatched
   required result: `INCONCLUSIVE—EXECUTION OR VERIFICATION`.
3. R5 fails: `FAIL—NO Q2-QUALIFIED PRIMARY BACKGROUND`.
4. R5 passes and R6 fails: `PASS—Q2-QUALIFIED PRIMARY BACKGROUND`.
5. R5 and R6 pass:
   `PASS—Q2-QUALIFIED DOMAIN-AND-RESOLUTION BACKGROUND`.

The campaign stops after this tree. A failing or partially qualified result is
not rerun with a larger budget, different optimizer, altered gate, selected
basin, or changed coefficient point.

## 10. Scope retained after any verdict

The campaign cannot establish:

- an unrestricted global minimum;
- non-$C_4$ or fully non-axisymmetric deformations;
- nonzero scale modes or $a_{\mathfrak s}$ dynamics;
- carrier phase gradients, sign changes, or exact interior carrier zeros;
- knots, topology-changing paths, or unrepresented multicore sectors;
- infinite-domain existence;
- the full constrained Hessian or mixed dynamical spectrum;
- real-time stability, tunnelling, or lifetime;
- quantum spin or statistics;
- physical calibration of the coefficient point;
- proton identification.

A `PASS` supplies one finite-dimensional full-field background eligible for the separately preregistered PA42–PA43 fluctuation calculation.

## 11. Programs and receipts

Primary program:

- `computations/particle_stationary_q2_recovery_v2.py`

Independent verifier:

- `computations/verify_particle_stationary_q2_recovery_v2.py`

Frozen run directory:

- `runs/20260902_particle_stationary_q2_recovery_v2/`

Required artifacts:

- `preflight_verification.json`—independent source and reconstruction preflight;
- `results.json`—primary receipt and checkpoint;
- `fields_<family>_<basin>.npz`—accepted recovery fields;
- `verification.json`—independent final verification receipt.

The execution order is:

```text
python computations/verify_particle_stationary_q2_recovery_v2.py --preflight
python computations/particle_stationary_q2_recovery_v2.py
python computations/verify_particle_stationary_q2_recovery_v2.py
```

## References

- `computations/particle-stationary-bvp-pre-registration.md`—source PA32 campaign contract
- `computations/particle-stationary-bvp-report.md`—source numerical-quality verdict
- `computations/particle_stationary_bvp.py`—source discretization and objective
- `computations/verify_particle_stationary_bvp.py`—independent diagnostic implementation
- `foundations/particle-stationary-action-closure.md`—particle action and stationary qualification authority
- `foundations/matter-completion-boundary.md`—nine-part conditional completion boundary
