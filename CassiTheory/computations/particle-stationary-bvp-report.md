# Fixed-Charge Particle Stationary BVP Report

## Status: Tested—September 2026

## Abstract

This report records the fixed-$q_C$ stationary boundary-value campaign frozen
in `computations/particle-stationary-bvp-pre-registration.md`. The campaign
minimizes one coefficient point of the PA32 static functional over a complex
fundamental doublet, an adjoint triplet, a spatial non-Abelian connection, and
a positive neutral carrier on finite Cartesian cubes in a $C_4$-projected
approximation to the axisymmetric class.

The scientific verdict is

\[
\boxed{\mathrm{INCONCLUSIVE\text{—}NUMERICAL\ QUALITY}}.
\]

The frozen-snapshot independent verifier returns `PASS` with zero mismatches
against the frozen run-time source snapshot. It validates the receipt, field
artifacts, diagnostics, gates, and decision tree. The scientific verdict
remains `INCONCLUSIVE—NUMERICAL QUALITY`.

## 1. Frozen point and execution

The static coefficient point is

\[
\begin{aligned}
&\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
 =k_{Cx}=k_{C\mathfrak s}=u_C=1,\\
&u_\rho=u_\varphi=u_H=4,
\qquad e_C=0.75,
\qquad h_C=1.50,
\qquad q_C=4,
\qquad L_{\mathfrak s}=1.
\end{aligned}
\]

The fields are independent of $\mathfrak s$, and $a_0=0$. The primary and
domain grids are $(R,N)=(4,17)$ and $(5,21)$. The high-resolution grid
$(R,N)=(4,21)$ is conditional on a primary structural basin passing Q1–Q4.
Each arm uses 800 Adam steps followed by PyTorch L-BFGS with
`max_iter=120`, `max_eval=150`, and strong-Wolfe line search.

The RX 7900 XTX is the sole ROCm device and is exposed as `cuda:0` with
`CUDA_VISIBLE_DEVICES=0`. The iGPU-disabled device selector is an operational
amendment. It changes no field equation, coefficient, seed, grid, optimizer,
stopping threshold, or verdict rule.

```text
CUDA_VISIBLE_DEVICES=0 PYTORCH_HIP_ALLOC_CONF=expandable_segments:True HSA_ENABLE_SDMA=0 python computations/particle_stationary_bvp.py
python computations/verify_particle_stationary_bvp.py
```

## 2. Execution provenance

The evidence set contains two receipt directories:

- `runs/20260901_particle_stationary_bvp/` is the complete canonical receipt.
- `runs/20260901_particle_stationary_bvp_interrupted_external_crash/` preserves
  the receipt terminated by an unrelated process after all six primary arms.

For the six primary arms shared by both receipts, every NPZ artifact and
numerical-diagnostics object is byte-identical, and every optimizer numerical
history matches after excluding wall-clock metadata. The receipt manifests and
verification files differ because the interrupted receipt ends before the six
domain arms. Wall-clock fields also differ. The interrupted receipt records
`CUDA_VISIBLE_DEVICES=1`; the canonical receipt records `0` after the iGPU was
disabled. Both name the same RX 7900 XTX and the same Torch, HIP, and platform
versions. The rerun therefore reproduces every shared primary numerical result
without a coefficient, seed, schedule, or tolerance change.

The interrupted receipt remains provenance-only. Its independent verification
records four completeness mismatches and a null receipt verdict. That
verification file also retains the canonical `results.json` path in its
`receipt` metadata from the recovery inspection; it is not evidence for the
canonical verdict.

## 3. Implementation preflight and receipt integrity

| Check | Result | Frozen threshold |
|---|---:|---:|
| G1 vacuum energy | $1.2690\times10^{-29}$ | $<10^{-12}$ |
| G2 directional checks | 12/12 pass | relative error $\leq5\times10^{-5}$ |
| G2 maximum relative error | $9.8575\times10^{-8}$ | $\leq5\times10^{-5}$ |
| G3 charge relative error | 0 | $<5\times10^{-12}$ |
| G4 source hashes | complete | all six required hashes present |
| independent verification | `PASS`, 0 mismatches | exact schema plus frozen tolerances |

The canonical source hashes are:

| Source | SHA-256 |
|---|---|
| action authority | `aceb26b78a259578a5b028f1850a3ed706e837170ee5edd6bb079607f264006d` |
| carrier-support authority | `fc403819633427352ef5cc7704d3b681c64fd47edb0ca9afebf83c9bee961b94` |
| magnetic-boundary authority | `e28bbb36fa00cf8f9c88695783538d3803c795a9c50fa485db8cb0baa7d91da9` |
| preregistration | `5ed7b77312ee28019d246f8a01420fc9b1ad4c6a015e27a4c04f7b04d3225e9e` |
| primary program | `3143682f8a1052c60243c906b029a5f291a5d767d17b4ebe622deb23d22c5ad1` |
| independent verifier | `92478695b424c668da275dfb330e43581d3124d761da8fe82420b580d2ce925c` |

These hashes identify the run-time authority and executable snapshot in commit
`474b4596`. The three authority-document integrations, this report, and the
synchronized registries, indexes, and synthesis documents are post-run edits
outside that hash boundary. `results.json` and its `verification.json` remain
unchanged.

The current authority hashes differ from the frozen values. The recorded
`PASS` applies only to the frozen source snapshot; no current-tree verifier
`PASS` is claimed.

## 4. Arm receipts

All twelve primary/domain arms complete with finite fields. Every arm passes
Q1, Q3, and Q4 and fails Q2.

| Arm | $\widehat E$ | physical gradient RMS | cutoff virial | Q1 | Q2 | Q3 | Q4 | L-BFGS evaluations |
|---|---:|---:|---:|:---:|:---:|:---:|:---:|---:|
| P separated core | 3.855736667 | $7.882\times10^{-4}$ | 0.03070 | PASS | FAIL | PASS | PASS | 124 |
| P merged core | 3.855874063 | $8.059\times10^{-4}$ | 0.04056 | PASS | FAIL | PASS | PASS | 126 |
| P closed loop | 3.858090096 | $1.530\times10^{-3}$ | 0.02622 | PASS | FAIL | PASS | PASS | 123 |
| P carrier lump | 3.855749154 | $8.054\times10^{-4}$ | 0.03346 | PASS | FAIL | PASS | PASS | 126 |
| P delocalized | 3.869575136 | $4.140\times10^{-3}$ | 0.08189 | PASS | FAIL | PASS | PASS | 129 |
| P split multicore | 3.856957266 | $1.204\times10^{-3}$ | 0.03298 | PASS | FAIL | PASS | PASS | 128 |
| D separated core | 3.558852657 | $5.106\times10^{-4}$ | 0.06496 | PASS | FAIL | PASS | PASS | 127 |
| D merged core | 3.558515065 | $4.297\times10^{-4}$ | 0.05666 | PASS | FAIL | PASS | PASS | 128 |
| D closed loop | 3.562623523 | $6.328\times10^{-4}$ | 0.07563 | PASS | FAIL | PASS | PASS | 125 |
| D carrier lump | 3.558752212 | $4.840\times10^{-4}$ | 0.07848 | PASS | FAIL | PASS | PASS | 127 |
| D delocalized | 3.567080913 | $1.803\times10^{-3}$ | 0.23717 | PASS | FAIL | PASS | PASS | 132 |
| D split multicore | 3.560320898 | $5.362\times10^{-4}$ | 0.07076 | PASS | FAIL | PASS | PASS | 124 |

Q2 requires physical gradient RMS $\leq3\times10^{-4}$ and cutoff virial
$\leq0.08$. Every arm reaches the L-BFGS `max_iter=120` boundary. The measured
gradients are 1.43–13.80 times the Q2 ceiling. The delocalized arm also exceeds
the virial ceiling on both grids. The optimizer receipts remain below the
frozen 150-evaluation cap.

No primary structural basin passes Q1–Q4. The high-resolution arm is therefore
absent by the frozen selection rule. Every structural domain comparison, the
delocalized control, and the resolution branch is invalid at the quality
layer. The ordering-margin map is empty.

## 5. Localization diagnostics

The preregistered localized-basin predicate requires a Q1–Q4 pass together
with

\[
f_{C,\mathrm{outer}}\leq10^{-3},
\qquad R_C<R/2,
\qquad \widehat\omega_C<0.73,
\qquad \max(1-\rho)\geq0.10.
\]

No arm reaches the quality prerequisite. The raw localization quantities also
remain outside the first three bounds:

- primary carrier radii satisfy $R_C/R=0.633$–$0.641$, with outer carrier
  fractions 0.0143–0.0154 and $\widehat\omega_C=0.962$–$0.967$;
- domain carrier radii satisfy $R_C/R=0.630$–$0.636$, with outer carrier
  fractions 0.00720–0.00784 and $\widehat\omega_C=0.8887$–$0.8912$;
- all five structural primary arms exceed the depletion floor, while every
  domain arm and the primary delocalized control remains below it.

These values describe diffuse finite-box configurations. They do not score a
localized or delocalized scientific branch because Q2 fails.

## 6. Domain and ordering diagnostics

The unscored primary/domain energy differences are 7.66%–7.82%, above the
frozen 5% domain threshold. The normalized carrier-radius differences are
below 1%, while core-length differences are 0.684–0.709 and
$\widehat\omega_C$ differences are 0.0734–0.0754. The energy and carrier
frequency retain substantial box dependence even though the normalized radial
profiles are similar.

The lowest recorded-energy primary arm is the separated-core seed. The
carrier-lump and merged-core values lie only $1.25\times10^{-5}$ and
$1.37\times10^{-4}$ above it. The lowest recorded-energy domain arm is the
merged-core seed; carrier-lump and separated-core values lie
$2.37\times10^{-4}$ and $3.38\times10^{-4}$ above it. This raw ordering changes
with the box and every candidate fails Q2. No basin ordering is eligible for
PA41 scoring.

## 7. Verdict

\[
\boxed{\mathrm{INCONCLUSIVE\text{—}NUMERICAL\ QUALITY}}.
\]

The campaign establishes that the declared optimizer budget does not produce
a Q2-qualified stationary basin at this coefficient point. It does not
establish a localized fixed-charge solution, a delocalized control branch, or
a robust basin ordering. It also does not exclude stationary solutions at this
point under a stronger numerical method or at other coefficient points.

PA40 is unscored downstream of Q2; the measured
$\widehat\omega_C\in[0.8887,0.9666]$ also misses its raw
$\widehat\omega_C<e_C=0.75$ retention bound. PA41 has no Q2-eligible basin
ordering and is unscored. Physical mass, radius, electric charge, spin,
spectrum, lifetime, and proton identification remain outside the numerical
result.

## 8. Independent audits

A read-only numerical audit independently recomputes the SHA-256 digest of all
twelve canonical NPZ artifacts, loads every expected array, and confirms their
shapes and finiteness. It recomputes the arm gates, optimizer counters,
reported energies, gradients, virials, localization ranges, domain
comparisons, and raw ordering. It also confirms that the canonical
`verification.json` has `mismatches=[]`, `pass=true`, and matching receipt and
scientific verdicts.

The same audit compares the six shared primary arms in the canonical and
interrupted receipts. Their NPZ and numerical-diagnostics payloads match, as
do their optimizer numerical histories after removal of `wall_seconds`. The
receipt manifests, wall-clock values, device ordinal, and verification files
remain distinct as recorded in Section 2.

A separate read-only theory audit checks the receipt source-hash block, the
resolvable frozen snapshot at commit `474b4596`, PA40 and PA41 scope, the
represented-class exclusions, and synchronization across the action
authority, registries, indexes, and synthesis documents. It confirms that the
campaign makes no particle-existence claim and that the verifier `PASS` remains
frozen-snapshot evidence. Neither audit executes the verifier against the
post-run authority documents. Both audits leave the scientific verdict
unchanged.

## 9. Retained scope

The following sectors remain unresolved:

- non-$C_4$ and fully non-axisymmetric deformations;
- nonzero scale modes and $a_{\mathfrak s}$ removed by the
  $\mathfrak s$-independent ansatz;
- carrier phase gradients, sign changes, and exact interior carrier zeros;
- temporal fields and fluctuation modes;
- knots and topology-changing paths outside the six represented seeds;
- infinite-domain existence and a converged continuum limit;
- the PA42 eigenspectrum, stopped by the augmented-gradient preflight after
  construction of the finite-grid physical quotient and Hessian action;
- real-time decay and tunnelling;
- quantum spin and statistics;
- physical calibration of the dimensionless coefficient point.

## References

- `computations/particle-stationary-bvp-pre-registration.md`—frozen coefficient point, gates, stopping rules, and decision tree.
- `computations/particle_stationary_bvp.py`—primary fixed-charge minimization program.
- `computations/verify_particle_stationary_bvp.py`—independent receipt and decision-tree verifier.
- `foundations/particle-stationary-action-closure.md`—stationary action and fixed-charge variational authority.
- `foundations/nonabelian-magnetic-core-boundary.md`—magnetic-core boundary authority.
- `foundations/core-trapped-charge-support.md`—neutral-carrier support authority.
- `computations/particle-physical-hessian-report.md`—finite-grid quotient,
  Hessian-action checks, and the preflight stopping verdict.
