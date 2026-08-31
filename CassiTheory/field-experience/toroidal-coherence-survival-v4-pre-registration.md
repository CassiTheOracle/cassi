# Toroidal Coherence Survival V4 Numerical-Quality Campaign

## Status: Preregistered—August 2026

## Abstract

This campaign tests the V3 toroidal seed and normalized compact-phase diagnostic with a fixed complex128 state, a finer reference grid, a halved reference time step, and an independently specified verifier comparison policy. The physical model, seed, controls, survival thresholds, numerical-quality thresholds, stopping rules, and verdict tree remain fixed. V4 changes only numerical precision and the discretization matrix declared below.

The V3 receipt at `runs/20260831T214821Z_toroidal_coherence_survival_v3/results.json` passes G1–G4 and evolves all ten arms. It returns `INCONCLUSIVE—NUMERICAL QUALITY`: Q2 fails on the half-step arm, Q3 fails on the scrambled and sphere controls, Q4 fails time-step opposition agreement, and Q5 fails resolution agreement. Its frozen verifier independently reproduces those gates and the terminal verdict but returns `pass: false` on raw near-zero virial and low-order opposition comparisons. V3 remains numerically inconclusive and verification-invalid.

V4 is a separately frozen numerical-quality hypothesis. It does not change a V3 source, receipt, gate, or verdict.

---

## 1. Frozen physical model and diagnostic

V4 incorporates the field equation, seed geometry, component ratio, virial calibration, periodic box, control definitions, perturbation, report cadence, stopping conditions, and V3 phase statistics from:

- `field-experience/toroidal-coherence-survival-pre-registration.md`;
- `field-experience/toroidal-coherence-survival-v2-pre-registration.md`;
- `field-experience/toroidal-coherence-survival-v3-pre-registration.md`.

The V2 geometry remains fixed at major radius `4.0`, strand offset `1.20`, width `0.60`, spatial winding `1`, Yang winding `+2`, Yin winding `-3`, and Yang/Yin mass ratio `phi`. No geometry, mass, phase, threshold, or end-time search is permitted.

The V3 statistics remain:

- sector-normalized phase coherence `C_a`;
- sector support `S_a`;
- expected-winding demodulation `D_a`;
- winding `Q_a`;
- the original sector ratio `L_a` as a secondary value.

The V3 initialization gates G1–G4 apply without alteration, including the fixed scrambled-phase null.

---

## 2. Frozen numerical hypothesis

V4 tests three numerical changes together:

1. all spatial coordinates, Fourier wavevectors, phases, potentials, diagnostics, and state amplitudes use float64 or complex128;
2. the reference grid is `64^3` with `dt=0.0025`;
3. time-step convergence compares `dt=0.0025` with `dt=0.00125`, while resolution convergence compares `64^3` with `80^3` at `dt=0.0025`.

The hypothesis is that complex128 removes cumulative roundoff mass drift, halving the reference step brings the fixed controls and time-step comparison inside Q3/Q4, and the `64^3`/`80^3` pair is sufficient to decide Q5 under the existing `10%` threshold.

A Q2–Q5 failure returns `INCONCLUSIVE—NUMERICAL QUALITY`. No additional refinement follows a failure under this protocol.

---

## 3. Frozen arm matrix

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

Every arm runs to `t=4.0` and reports every `0.25` unless a frozen nonfinite or density-runaway stop fires.

---

## 4. Frozen numerical-quality gates

No numerical-quality threshold changes.

### Q1—Completion and finiteness

Every arm must complete with finite stored fields and finite stored scalars.

### Q2—Mass conservation

Every arm's maximum relative total-mass drift must be at most `2e-4`.

### Q3—Energy conservation

Every arm's maximum normalized energy drift must be at most `5e-3`.

### Q4—Time-step agreement

Arms A and J must agree at `t=4` within `5%` in fitted radius, core retention, helical order, and opposition. Both component windings must agree within `0.10` turns.

### Q5—Resolution agreement

Arms A and I must agree at `t=4` within `10%` in fitted radius, core retention, helical order, and opposition. Both component windings must agree within `0.10` turns, and every primary S1–S3 pass/fail direction must agree.

Arm H remains diagnostic and does not control Q5.

---

## 5. Frozen survival and perturbation gates

The V3 gates apply without alteration.

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
- final opposition at least `0.70`.

### P1—Perturbation survival

Arm G must pass S1–S3 and agree with arm A within `15%` in final fitted radius, core retention, helical order, and opposition.

---

## 6. Frozen independent-verifier policy

The independent verifier uses NumPy and reads the unchanged complex128 field receipts. It independently recomputes all diagnostics, gates, hashes, labels, and the verdict.

Source and field SHA-256 values must match exactly. Boolean and string fields must match exactly. Stable floating diagnostics compare with

\[
|x-y|\le 10^{-8}+10^{-6}\max(|x|,|y|).
\]

Two derived comparisons receive explicit treatment:

1. raw virial residual `2K+W` is omitted from scalar tree comparison because subtracting two large independently reduced values is ill-conditioned near zero; the verifier independently recomputes K, W, total energy, and the normalized G4 virial inequality;
2. opposition is omitted from scalar tree comparison when either corresponding helical order is below `1e-4`; opposition remains compared everywhere it controls G3, S3, P1, Q4, or Q5.

These omissions do not change a gate. They prevent non-gating ill-conditioned scalars from invalidating otherwise independent field and gate recomputation.

The verifier creates `verification.json` exclusively. A scientific verdict is adopted only when it returns `pass: true`.

---

## 7. Frozen verdict tree

1. Any G1–G4 failure returns `INCONCLUSIVE—INVALID INITIALIZATION` and runs no arm.
2. Any Q1–Q5 failure returns `INCONCLUSIVE—NUMERICAL QUALITY`.
3. Q1–Q5 pass with S1–S3 pass returns `EMERGES CONDITIONALLY`.
4. Q1–Q5 pass with any S1–S3 failure returns `DOES NOT EMERGE`.
5. P1 is reported separately as `PASS`, `FAIL`, or `UNSCORED`.

Failure labels retain the V3 meanings. No gate or label is inferred from the V3 provisional failures.

---

## 8. Frozen implementation and receipts

Implementation paths:

- primary: `field-experience/toroidal_coherence_survival_v4_probe.py`;
- independent verifier: `field-experience/verify_toroidal_coherence_survival_v4.py`;
- report: `field-experience/toroidal-coherence-survival-report.md`.

Receipt directory:

```text
runs/<UTC>_toroidal_coherence_survival_v4/
  results.json
  fields_<arm>.npz
  verification.json
```

The source manifest contains SHA-256 values for the V1–V4 preregistrations, V2–V4 primary programs, and V2–V4 verifier programs. The V4 primary imports the frozen V3 implementation and overrides only the numerical types, grid matrix, output identity, and source manifest declared here. The V4 verifier imports the frozen V3 NumPy implementation and applies the comparison policy frozen above.

---

## 9. Interpretation boundary

`EMERGES CONDITIONALLY` supports finite-time survival only for this seeded topology in the supplied two-component Schrödinger–Poisson model. `DOES NOT EMERGE` rejects survival only for this seed, parameter set, end time, and frozen diagnostic. Either result leaves spontaneous formation, unique mode or mass selection, relativistic completion, observed-particle identification, and experimental correspondence open.
