# Toroidal Coherence Survival V3 Diagnostic Campaign

## Status: Preregistered—August 2026

## Abstract

This campaign tests the frozen V2 toroidal seed under the supplied two-component Schrödinger–Poisson evolution after separating compact-phase coherence from angular-sector support. The V1 and V2 receipts show that the original statistic

\[
\frac{\min_j|Z_a(j)|}{\operatorname{mean}_j|Z_a(j)|}
\]

mixes phase cancellation inside a sector with the amount of field sampled in that sector. V3 retains that statistic as a secondary diagnostic, introduces separately normalized phase and support statistics, freezes a scrambled-phase null, and then applies a complete survival, control, perturbation, time-step, and resolution campaign.

A dynamical verdict remains conditional on the supplied model and seeded topology. It supplies no spontaneous-formation, unique-mass, particle-identification, or experimental-correspondence result.

---

## 1. Frozen model and seed

The field equation, periodic cube, integration method, constants, seed family, virial calibration, arms, stopping conditions, and non-phase diagnostics are incorporated from:

- `field-experience/toroidal-coherence-survival-pre-registration.md`;
- `field-experience/toroidal-coherence-survival-v2-pre-registration.md`.

The V2 geometry is fixed:

| quantity | value |
|---|---:|
| box size | `16.0` |
| reference grid | `48^3` |
| major radius | `4.0` |
| strand offset | `1.20` |
| strand width | `0.60` |
| spatial winding | `1` |
| Yang compact winding | `+2` |
| Yin compact winding | `-3` |
| Yang/Yin mass ratio | `phi` |
| reference time step | `0.005` |
| end time | `4.0` |
| report cadence | `0.25` |
| winding sectors | `64` |
| random seed | `20260831` |

No seed parameter search, geometry change, threshold fitting, or mass retuning is permitted. The virial mass is recomputed once by the incorporated algebra.

---

## 2. Diagnostic attribution

For component $a$, let

\[
Z_a(j)=\int_{\text{sector }j}\psi_a\,d^3x,
\qquad
A_a(j)=\int_{\text{sector }j}|\psi_a|\,d^3x.
\]

The original statistic is retained as

\[
L_a=\frac{\min_j|Z_a(j)|}{\operatorname{mean}_j|Z_a(j)|}.
\]

For a coherent field $\psi_a=f_a e^{iq_a\chi}$, $|Z_a(j)|$ is proportional to both the sector support $A_a(j)$ and the phase resultant inside that sector. Therefore $L_a$ changes when Cartesian sampling changes $A_a(j)$ even if the compact phase is unchanged. It remains reported and does not control a V3 gate.

---

## 3. Frozen V3 compact-phase statistics

### 3.1 Sector-normalized phasor

For every sector with $A_a(j)>0$, define

\[
U_a(j)=\frac{Z_a(j)}{A_a(j)}.
\]

The winding remains

\[
Q_a=\frac{1}{2\pi}
\sum_j\arg\left[U_a(j+1)U_a(j)^*\right].
\]

Positive real normalization leaves the sector phase unchanged, so this winding is algebraically identical to the original winding whenever every sector is represented.

The local phase-coherence statistic is

\[
C_a=\min_j|U_a(j)|.
\]

It lies in $[0,1]$ by the triangle inequality and measures cancellation inside each sector without sector-support amplitude.

### 3.2 Sector support

The independent support statistic is

\[
S_a=\frac{\min_j A_a(j)}{\operatorname{mean}_j A_a(j)}.
\]

A winding measurement is valid only when $S_a\ge0.05$. This retains the original numerical validity floor as an explicit support condition rather than embedding it in the phase statistic.

### 3.3 Expected-winding demodulation

Let $\chi_j=2\pi(j+1/2)/64$ be the center of sector $j$. For the declared component winding $q_a$, define

\[
D_a=
\frac{\left|\sum_j Z_a(j)e^{-iq_a\chi_j}\right|}
{\sum_j A_a(j)}.
\]

$D_a\in[0,1]$. An exact $q_a\chi$ compact phase gives the finite-sector factor

\[
\operatorname{sinc}\left(\frac{|q_a|\pi}{64}\right),
\]

which exceeds `0.996` for both declared windings. The initial coherent threshold `0.95` leaves more than four percentage points for Cartesian quadrature error while remaining independently anchored to the analytic finite-sector value.

### 3.4 Frozen null

The incorporated scrambled seed uses the fixed random seed and matches each component's initial phase-gradient energy. At preflight its demodulated values must satisfy

\[
D_Y^{\rm scrambled}\le0.50,
\qquad
D_I^{\rm scrambled}\le0.50.
\]

Failure of this null makes initialization invalid. This prevents the new statistic from passing both a declared compact phase and its fixed phase-scrambled control.

---

## 4. Frozen arms

The ten incorporated arms run without alteration:

| arm | seed | grid | `dt` | gravity `g` |
|---|---|---:|---:|---:|
| A | closed | 48 | 0.005 | 1 |
| B | closed | 48 | 0.005 | 0 |
| C | untwisted | 48 | 0.005 | 1 |
| D | open | 48 | 0.005 | 1 |
| E | scrambled | 48 | 0.005 | 1 |
| F | sphere | 48 | 0.005 | 1 |
| G | perturbed | 48 | 0.005 | 1 |
| H | closed | 32 | 0.005 | 1 |
| I | closed | 64 | 0.005 | 1 |
| J | closed | 48 | 0.0025 | 1 |

Every arm runs to `t=4.0` unless a frozen stopping condition fires.

---

## 5. Frozen initialization gates

### G1—Analytic closure

The incorporated endpoint mismatch must be at most `1e-12`.

### G2—Compact phase and null discrimination

For the closed seed at `N=48`:

- `|Q_Y-2| <= 0.05`;
- `|Q_I+3| <= 0.05`;
- `C_Y >= 0.95` and `C_I >= 0.95`;
- `D_Y >= 0.95` and `D_I >= 0.95`;
- `S_Y >= 0.05` and `S_I >= 0.05`.

For the fixed scrambled seed:

- `D_Y <= 0.50` and `D_I <= 0.50`.

The secondary values $L_Y$ and $L_I$ are recorded without thresholds.

### G3—Double-helical geometry

The incorporated geometry gate remains:

- closed seed `H >= 0.80` and `O >= 0.80`;
- untwisted seed `H <= 0.20`.

### G4—Composition and virial calibration

The incorporated relative component-ratio and virial residual limits remain `1e-5`.

Failure of G1–G4 stops every evolution arm with `INCONCLUSIVE—INVALID INITIALIZATION`.

---

## 6. Frozen numerical-quality gates

The incorporated gates remain unchanged:

- **Q1:** every arm completes with finite stored fields and scalars;
- **Q2:** maximum relative mass drift in every arm is at most `2e-4`;
- **Q3:** normalized energy drift in every arm is at most `5e-3`;
- **Q4:** A/J end-state `R_fit`, core retention, `H`, and `O` agree within `5%`, and both windings agree within `0.10` turns;
- **Q5:** A/I corresponding metrics agree within `10%`, both windings agree within `0.10` turns, and every primary pass/fail direction agrees.

Arm H remains diagnostic.

---

## 7. Frozen survival gates

### S1—Compact-phase survival

At every report from arm A:

- `|Q_Y-2| <= 0.25`;
- `|Q_I+3| <= 0.25`;
- `C_Y >= 0.50` and `C_I >= 0.50`;
- `D_Y >= 0.50` and `D_I >= 0.50`;
- `S_Y >= 0.05` and `S_I >= 0.05`.

The `0.50` phase floors require a majority resultant after expected-winding demodulation and remain well separated from the fixed scrambled-null ceiling.

### S2—Localization survival

The incorporated localization gate remains:

- final core retention at least `0.75` of its initial value;
- final fitted-radius ratio in `[0.80,1.20]`;
- every fitted-radius ratio at `t>=1.0` in `[0.75,1.25]`;
- center displacement at most one quarter of the major radius.

### S3—Double-helical survival

The incorporated helical gate remains:

- final `H/H(0) >= 0.70`;
- final `O >= 0.70`.

### P1—Perturbation survival

Arm G must satisfy S1–S3. Its final `R_fit`, core retention, `H`, and `O` must each agree with arm A within `15%`.

---

## 8. Frozen verdict tree

1. If any of G1–G4 fails, return `INCONCLUSIVE—INVALID INITIALIZATION` and run no evolution arm.
2. If any of Q1–Q5 fails, return `INCONCLUSIVE—NUMERICAL QUALITY`.
3. If Q1–Q5 and S1–S3 pass, return `EMERGES CONDITIONALLY`.
4. If Q1–Q5 pass and any of S1–S3 fails, return `DOES NOT EMERGE`.
5. Report P1 separately as `PASS`, `FAIL`, or `UNSCORED` when the primary verdict is inconclusive.

Failure labels remain `UNWINDS`, `DELOCALIZES`, `RADIUS COLLAPSES`, `RADIUS EXPANDS`, `HELIX DISSOLVES`, and `DRIFTS`. `UNWINDS` includes failure of any S1 phase or support inequality.

---

## 9. Frozen stopping rules

An arm stops immediately on a nonfinite field or when maximum density exceeds `1e8` times its initial value. A stopped arm fails Q1. The protocol does not restart, retune, or extend an arm after observing its result.

---

## 10. Frozen implementation and receipts

Implementation paths:

- primary: `field-experience/toroidal_coherence_survival_v3_probe.py`;
- independent verifier: `field-experience/verify_toroidal_coherence_survival_v3.py`;
- campaign report: `field-experience/toroidal-coherence-survival-report.md`.

Receipt directory:

```text
runs/<UTC>_toroidal_coherence_survival_v3/
  results.json
  fields_<arm>.npz
  verification.json
```

The source manifest contains SHA-256 values for the V1, V2, and V3 preregistrations; the frozen V2 primary and verifier modules reused by V3; and both V3 programs.

The primary uses PyTorch on the selected device. The verifier uses NumPy, recomputes every metric and gate from stored complex fields, validates every source and field hash, checks the exact verdict tree, and creates `verification.json` exclusively. A primary result receives no adopted verdict if independent verification fails.

---

## 11. Interpretation boundary

`EMERGES CONDITIONALLY` supports finite-time survival of this seeded toroidal double helix in the supplied Schrödinger–Poisson model. `DOES NOT EMERGE` rejects survival for this seed, parameter set, time window, and frozen diagnostic. Either result leaves spontaneous topology formation, physical mode selection, relativistic completion, observed-particle identification, and experimental correspondence open.
