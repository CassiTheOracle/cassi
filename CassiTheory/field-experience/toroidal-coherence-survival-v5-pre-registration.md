# Toroidal Coherence Survival V5 Diagnostic-Precision Campaign

## Status: Preregistered—August 2026

## Abstract

This campaign tests the V3 toroidal seed with a true float64 energy diagnostic, a fourth-order symmetric split-step integrator, and a bounded opposed-helical-moment convergence statistic. The physical equation, seed, controls, spatial grids, time steps, survival thresholds, energy threshold, stopping rules, and verdict tree remain fixed.

The canonical V4 receipt at `runs/20260831T220853Z_toroidal_coherence_survival_v4/results.json` passes G1–G4, Q1, Q2, and Q4. Q3 fails on the spherical control with energy drift `0.013280009933384629`; Q5 fails on a `0.387179711030671` normalized-opposition difference while its other observables, windings, and survival directions agree. The V4 verifier reproduces those decisions and returns `pass: false`: the primary energy calculation inherits a float32 accumulator and exceeds its frozen `1e-6` comparison tolerance. V4 remains `INCONCLUSIVE—NUMERICAL QUALITY` and verification-invalid under its unchanged sources and receipts.

V5 freezes a new numerical hypothesis before implementation or execution. Its revised convergence statistic and integration method apply only to V5.

---

## 1. Frozen physical model and initialization

V5 incorporates the field equation, V2 seed geometry, component ratio, virial calibration, periodic box, control definitions, perturbation, report cadence, stopping conditions, and V3 normalized compact-phase statistics from:

- `field-experience/toroidal-coherence-survival-pre-registration.md`;
- `field-experience/toroidal-coherence-survival-v2-pre-registration.md`;
- `field-experience/toroidal-coherence-survival-v3-pre-registration.md`.

The geometry remains fixed at major radius `4.0`, strand offset `1.20`, width `0.60`, spatial winding `1`, Yang winding `+2`, Yin winding `-3`, and Yang/Yin mass ratio `phi`. Every coordinate, Fourier wavevector, phase, potential, diagnostic, and state amplitude uses float64 or complex128.

The V3 G1–G4 initialization gates and fixed scrambled-phase null apply without alteration. No geometry, mass, phase, threshold, or end-time search is permitted.

---

## 2. Frozen energy definition

For each component $a\in\{Y,I\}$, V5 computes

\[
K=-\frac12\sum_a \Delta V\sum_{\mathbf x}
\operatorname{Re}\!\left(\psi_a^*\nabla^2\psi_a\right),
\qquad
W=\frac{g}{2}\Delta V\sum_{\mathbf x}\rho\Phi,
\qquad
E=K+W.
\]

The kinetic accumulator is initialized explicitly with the real dtype of the complex128 field, hence float64. Every summand, partial accumulation, returned scalar, virial calibration value, stored energy, and Q3 drift uses this definition. The Q3 denominator remains

\[
\max\bigl(|E(0)|,K(0),10^{-12}\bigr).
\]

The V5 verifier independently recomputes the same discrete definition with NumPy complex128/float64 from the stored fields.

---

## 3. Frozen fourth-order evolution

Let $T(h)$ be the exact spectral kinetic flow for duration $h$ and $V(h)$ the exact self-consistent potential-phase flow for duration $h$. Since $V(h)$ changes phase while preserving density, its Poisson potential is constant during that subflow.

V5 defines the second-order symmetric step

\[
S_2(h)=V(h/2)\,T(h)\,V(h/2)
\]

and the fourth-order triple-jump composition

\[
S_4(\Delta t)=S_2(w_1\Delta t)\,S_2(w_0\Delta t)\,S_2(w_1\Delta t),
\]

with

\[
w_1=\frac{1}{2-2^{1/3}},
\qquad
w_0=-\frac{2^{1/3}}{2-2^{1/3}}.
\]

The Poisson field is recomputed after each kinetic subflow. Negative middle substeps use the same unitary spectral and potential flows with signed duration. No filter, damping, adaptive step, density clamp, or post-step renormalization is applied.

The hypothesis is that this fixed fourth-order composition brings the collapsing spherical control inside Q3 while preserving the V4 mass, time-step, and resolution behavior. A failure ends V5 without parameter refinement.

---

## 4. Frozen arm matrix

| arm | seed | grid | `dt` | gravity `g` | role |
|---|---|---:|---:|---:|---|
| A | closed | 64 | 0.0025 | 1 | primary |
| B | closed | 64 | 0.0025 | 0 | no-gravity control |
| C | untwisted | 64 | 0.0025 | 1 | geometry control |
| D | open | 64 | 0.0025 | 1 | closure control |
| E | scrambled | 64 | 0.0025 | 1 | compact-phase control |
| F | sphere | 64 | 0.0025 | 1 | morphology control |
| G | perturbed | 64 | 0.0025 | 1 | perturbation arm |
| H | closed | 48 | 0.0025 | 1 | low-resolution diagnostic |
| I | closed | 80 | 0.0025 | 1 | high-resolution convergence |
| J | closed | 64 | 0.00125 | 1 | half-step convergence |

Every arm runs to `t=4.0` and reports every `0.25` unless the frozen nonfinite or density-runaway stop fires.

---

## 5. Frozen opposed-helical-moment statistic

For the complex first helical moments $h_Y$ and $h_I$, define

\[
M_{\rm opp}=-\operatorname{Re}(h_Yh_I^*)
=O\,|h_Y|\,|h_I|.
\]

This bounded statistic lies in `[-1,1]` and tends continuously to zero when either helical moment vanishes. Raw normalized opposition $O$ remains stored and continues to control G3, S3, and P1. V5 replaces raw-$O$ comparison only inside Q4 and Q5 with the absolute difference in $M_{\rm opp}$ frozen below.

This change tests convergence of the opposed ordered amplitude without dividing by two diminishing helical moments. It is a new V5 statistic; the V4 Q5 failure remains unchanged.

---

## 6. Frozen numerical-quality gates

### Q1—Completion and finiteness

Every arm must complete with finite stored complex128 fields and finite stored scalars.

### Q2—Mass conservation

Every arm's maximum relative total-mass drift must be at most `2e-4`.

### Q3—Energy conservation

Every arm's maximum normalized float64 energy drift must be at most `5e-3`.

### Q4—Time-step agreement

At `t=4`, arms A and J must satisfy all of:

- relative fitted-radius difference at most `0.05`;
- relative core-retention difference at most `0.05`;
- relative helical-order difference at most `0.05`;
- absolute opposed-helical-moment difference at most `0.05`;
- both component windings agree within `0.10` turns.

### Q5—Resolution agreement

At `t=4`, arms A and I must satisfy all of:

- relative fitted-radius difference at most `0.10`;
- relative core-retention difference at most `0.10`;
- relative helical-order difference at most `0.10`;
- absolute opposed-helical-moment difference at most `0.10`;
- both component windings agree within `0.10` turns;
- every primary S1–S3 pass/fail direction agrees.

Arm H remains diagnostic and does not control Q5.

---

## 7. Frozen survival and perturbation gates

The V3 S1–S3 gates apply without alteration.

### S1—Compact-phase survival

At every arm-A report:

- `|Q_Y-2| <= 0.25` and `|Q_I+3| <= 0.25`;
- `C_Y,C_I >= 0.50`;
- `D_Y,D_I >= 0.50`;
- `S_Y,S_I >= 0.05`.

### S2—Localization survival

- final core retention at least `0.75` of its initial value;
- final fitted-radius ratio in `[0.80,1.20]`;
- every fitted-radius ratio at `t>=1.0` in `[0.75,1.25]`;
- center displacement at most one quarter of the major radius.

### S3—Double-helical survival

- final `H/H(0) >= 0.70`;
- final raw opposition at least `0.70`.

### P1—Perturbation survival

Arm G must pass S1–S3 and agree with arm A within `15%` in final fitted radius, core retention, helical order, and raw opposition.

---

## 8. Frozen independent-verifier policy

The independent verifier uses NumPy and reads the unchanged complex128 field receipts. It independently recomputes all diagnostics, V5 gates, hashes, labels, and the verdict.

Source and field SHA-256 values must match exactly. Boolean and string fields must match exactly. Stable floating diagnostics retain the V4 comparison rule

\[
|x-y|\le 10^{-8}+10^{-6}\max(|x|,|y|).
\]

Raw virial residual is omitted from scalar tree comparison because subtracting two independently reduced large terms is ill-conditioned near zero; K, W, total energy, and normalized G4 are independently recomputed. Opposition is omitted from scalar tree comparison only when either corresponding helical order is below `1e-4`; it remains compared wherever it controls a gate.

The verifier creates `verification.json` exclusively. A scientific verdict is adopted only when it returns `pass: true`.

---

## 9. Frozen verdict tree

1. Any G1–G4 failure returns `INCONCLUSIVE—INVALID INITIALIZATION` and runs no arm.
2. Any Q1–Q5 failure returns `INCONCLUSIVE—NUMERICAL QUALITY`.
3. Q1–Q5 pass with S1–S3 pass returns `EMERGES CONDITIONALLY`.
4. Q1–Q5 pass with any S1–S3 failure returns `DOES NOT EMERGE`.
5. P1 is reported separately as `PASS`, `FAIL`, or `UNSCORED`.
6. Any independent-verifier failure leaves the scientific result unadopted regardless of the primary verdict.

Failure labels retain the V3 meanings.

---

## 10. Frozen implementation and receipts

Implementation paths:

- primary: `field-experience/toroidal_coherence_survival_v5_probe.py`;
- independent verifier: `field-experience/verify_toroidal_coherence_survival_v5.py`;
- report: `field-experience/toroidal-coherence-survival-report.md`.

Receipt directory:

```text
runs/<UTC>_toroidal_coherence_survival_v5/
  results.json
  fields_<arm>.npz
  verification.json
```

The source manifest contains SHA-256 values for the V1–V5 preregistrations, V2–V5 primary programs, and V2–V5 verifier programs. The V5 primary imports the frozen V4 implementation and implements the energy definition, integrator, opposed-helical-moment diagnostic, gate calculation, output identity, and source manifest in V5-local functions. The V5 verifier imports the frozen V4 NumPy implementation and applies V5-local diagnostics and gates. Neither V5 program assigns into an imported module global; all V2–V4 source files and imported runtime definitions remain unchanged.

---

## 11. Interpretation boundary

`EMERGES CONDITIONALLY` supports finite-time survival only for this seeded topology in the supplied two-component Schrödinger–Poisson model. `DOES NOT EMERGE` rejects survival only for this seed, parameter set, end time, integrator, and frozen diagnostic. Either result leaves spontaneous formation, unique mode or mass selection, relativistic completion, observed-particle identification, and experimental correspondence open.
