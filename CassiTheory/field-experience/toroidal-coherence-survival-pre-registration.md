# Toroidal Coherence Survival Probe—Pre-registration

## Status: Preregistered—August 2026

## Abstract

This probe tests whether a spatially closed Yang/Yin double helix remains a localized, wound, finite-radius object under a minimal conservative open-space field evolution. The tested evolution is a supplied two-component Schrödinger–Poisson model. It is separate from the canonical two-density reaction–diffusion PDE and from the supplied one-dimensional loop Hamiltonian in `field-experience/qi-loop-mass-cascade-pre-registration.md`.

The primary question is binary:

> Does a seeded toroidal Yang/Yin double helix preserve spatial closure, compact-phase winding, localization, and helical order through the declared observation window without external confinement?

The probe freezes the equation, initial conditions, controls, diagnostics, thresholds, stopping rules, seed, and receipt locations before implementation or model execution. A positive result establishes conditional survival in the supplied model. It does not establish spontaneous formation, a particle mass spectrum, quantum statistics, or identification with observed matter.

---

## 1. Frozen claim boundary

The probe addresses three simultaneous closures:

1. **spatial closure:** both density strands close around a toroidal centerline;
2. **phase closure:** each complex component carries an integer azimuthal winding;
3. **dynamical closure:** the object retains finite radius, localization, winding, and double-helical order.

The compact phases introduced here are additional state variables. The canonical density-plane coordinate

\[
\theta_d=\operatorname{atan2}(E_I,E_Y)
\]

remains a bounded diagnostic and is not reinterpreted as a compact phase.

The probe supplies self-gravity as the binding interaction because the repository already contains conservative Schrödinger–Poisson evolution in `two-fluid/cassi_bridge_v2.py`. The result is conditional on that supplied open-space realization. The reduced energy

\[
H(L)=TL+\frac{2\pi^2A}{L}
\]

belongs to the separate conditional loop calculation. It is not asserted as a reduction of the evolution tested here.

---

## 2. Frozen field equation

Two complex fields evolve on a periodic cube:

\[
\Psi=(\psi_Y,\psi_I),
\qquad
\rho=|\psi_Y|^2+|\psi_I|^2.
\]

The dimensionless equations are

\[
i\,\partial_t\psi_a
=
\left(-\frac12\nabla^2+g\Phi\right)\psi_a,
\qquad a\in\{Y,I\},
\]

\[
\nabla^2\Phi=\rho-\langle\rho\rangle,
\qquad
\langle\Phi\rangle=0.
\]

Frozen numerical evolution:

- periodic Fourier grid;
- exact spectral kinetic multiplier;
- mean-subtracted spectral Poisson solve with the zero mode fixed to zero;
- time-reversible Strang split: half potential, full kinetic, recomputed half potential;
- `complex64` fields and `float32` real arrays;
- GPU execution when PyTorch exposes a CUDA/ROCm device, CPU otherwise;
- no damping, absorbing layer, external potential, conversion term, attractor term, normalization after initialization, or post-step clipping.

The primary dynamics use `g=1`. The free dispersive control uses `g=0`.

---

## 3. Frozen domain and integration constants

| Quantity | Frozen value |
|---|---:|
| cube side | `L_box = 16.0` |
| reference resolution | `N = 48` |
| low-resolution arm | `N = 32` |
| high-resolution arm | `N = 64` |
| primary step | `dt = 0.005` |
| half-step convergence arm | `dt = 0.0025` |
| end time | `t_end = 4.0` |
| report cadence | `0.25` |
| torus major radius | `R0 = 4.0` |
| strand offset | `a = 1.0` |
| strand density width | `sigma = 0.75` |
| spatial helix winding | `m = 1` |
| Yang compact-phase winding | `p = +2` |
| Yin compact-phase winding | `q = -3` |
| component norm ratio | `M_Y/M_I = phi` |
| random seed | `20260831` |
| winding sectors | `64` |

The winding magnitudes `(2, 3)` are the lowest nontrivial Fibonacci pair used by the existing conditional loop probe. Their orientation is counter-directed. The finite ratio approximates `phi`; the phase closure itself follows from the integer windings.

---

## 4. Frozen initial fields

Let

\[
r_\perp=\sqrt{x^2+y^2},
\qquad
\chi=\operatorname{atan2}(y,x).
\]

For ellipticity `e`, define

\[
R_e(\chi)=R_0\left[1+e\cos(2\chi)\right].
\]

The two strand distances are

\[
d_Y^2=
\left[r_\perp-R_e(\chi)-a\cos(m\chi)\right]^2
+
\left[z-a\sin(m\chi)\right]^2,
\]

\[
d_I^2=
\left[r_\perp-R_e(\chi)+a\cos(m\chi)\right]^2
+
\left[z+a\sin(m\chi)\right]^2.
\]

The closed-double-helix amplitudes and phases are

\[
\psi_Y=A_Y\exp\left(-\frac{d_Y^2}{4\sigma^2}\right)e^{+2i\chi},
\]

\[
\psi_I=A_I\exp\left(-\frac{d_I^2}{4\sigma^2}\right)e^{-3i\chi}.
\]

`A_Y/A_I` is fixed so that `M_Y/M_I = phi` before the common total-mass normalization.

### 4.1 Virial mass calibration

The total mass is fixed once from the reference closed seed at `N=48`, `g=1`:

1. normalize the reference seed to total mass one;
2. compute its kinetic energy `K1` and gravitational energy `W1`;
3. set

\[
M_{\rm vir}=-\frac{2K_1}{W_1};
\]

4. multiply both components by `sqrt(M_vir)`;
5. apply this same total mass to every arm and every resolution.

For Schrödinger–Poisson scaling, `K(M)=M K1` and `W(M)=M^2 W1`, so this construction fixes `2K+W=0` for the reference seed at initialization. The run stops as protocol-invalid if `W1 >= 0`, `M_vir` is nonfinite, or `M_vir` lies outside `[0.1, 1.0e6]`.

### 4.2 Seed variants

- **closed:** equations above with `e=0`;
- **untwisted:** the same construction with `m=0`;
- **open:** the closed amplitudes multiplied by a periodic smooth gap window centered at `chi=pi`, with gap width `pi/2` and edge width `0.10` radians;
- **scrambled:** the closed densities with independent deterministic low-pass random phases; each random phase is mean-free and scaled so its density-weighted phase-gradient kinetic energy equals that component's coherent phase-gradient kinetic energy;
- **sphere:** centered Gaussian component amplitudes with density width `R0/2`, flat phases, and the same component norm ratio;
- **perturbed:** the closed seed with `e=0.05` and independent deterministic low-pass phase perturbations of density-weighted RMS `0.05` radians.

The random phase generator is NumPy `PCG64` with seed `20260831` for Yang and `20260832` for Yin. Its Fourier filter is

\[
\exp\left[-(k/k_c)^4\right],
\qquad
k_c=\frac{\pi}{\sigma}.
\]

Every seed receives the frozen total mass `M_vir` after construction. No arm-specific energy or mass retuning is permitted.

---

## 5. Frozen arms

| Arm | Seed | `N` | `dt` | `g` | Purpose |
|---|---|---:|---:|---:|---|
| A | closed | 48 | 0.005 | 1 | primary survival |
| B | closed | 48 | 0.005 | 0 | free dispersive control |
| C | untwisted | 48 | 0.005 | 1 | spatial-helix control |
| D | open | 48 | 0.005 | 1 | closure control |
| E | scrambled | 48 | 0.005 | 1 | compact-phase coherence control |
| F | sphere | 48 | 0.005 | 1 | localized self-binding control |
| G | perturbed | 48 | 0.005 | 1 | perturbation arm |
| H | closed | 32 | 0.005 | 1 | low-resolution arm |
| I | closed | 64 | 0.005 | 1 | high-resolution arm |
| J | closed | 48 | 0.0025 | 1 | time-step convergence arm |

All arms run to `t_end = 4.0` unless a frozen stopping condition fires.

---

## 6. Frozen diagnostics

### 6.1 Conserved quantities

At every report time:

- component masses `M_Y`, `M_I`;
- total mass `M`;
- kinetic energy

\[
K=-\frac12\sum_a\int\operatorname{Re}(\psi_a^*\nabla^2\psi_a)\,d^3x;
\]

- gravitational energy

\[
W=\frac{g}{2}\int\rho\Phi\,d^3x;
\]

- total energy `E = K + W`;
- virial residual `2K + W`.

### 6.2 Fitted ring radius and localization

The fitted cylindrical radius is

\[
R_{\rm fit}=\frac{\int r_\perp\rho\,d^3x}{\int\rho\,d^3x}.
\]

Define

\[
d_{\rm tor}=\sqrt{(r_\perp-R_{\rm fit})^2+z^2}.
\]

The core fraction is the mass fraction satisfying

\[
d_{\rm tor}\le 2.5\sigma.
\]

Core retention is `f_core(t)/f_core(0)`.

### 6.3 Compact-phase winding

Divide `chi` into 64 equal sectors. For component `a`, form the complex sector sums

\[
Z_a(j)=\int_{\text{sector }j}\psi_a\,d^3x.
\]

The measured winding is

\[
Q_a=\frac{1}{2\pi}
\sum_j\arg\left[Z_a(j+1)Z_a(j)^*\right].
\]

The sector-coherence floor is

\[
c_a=\frac{\min_j|Z_a(j)|}{\operatorname{mean}_j|Z_a(j)|}.
\]

A winding measurement is valid only when `c_a >= 0.05`.

### 6.4 Double-helical density order

With

\[
\vartheta=\operatorname{atan2}(z,r_\perp-R_{\rm fit}),
\]

define

\[
h_a=\frac{1}{M_a}\int\rho_a e^{i(\vartheta-m\chi)}\,d^3x.
\]

The helical order and strand opposition are

\[
H=\frac{|h_Y|+|h_I|}{2},
\]

\[
O=-\frac{\operatorname{Re}(h_Yh_I^*)}{|h_Y||h_I|}.
\]

`O` is reported as undefined if either order magnitude is below `1e-8`.

### 6.5 Center motion

The periodic center of mass is obtained from the first circular moment on each axis. The reported displacement is the minimum-image distance from the initial center.

---

## 7. Frozen gates

### G1—Initial geometric closure

The analytic Yang and Yin centerlines evaluated at `chi=0` and `chi=2pi` must agree to absolute distance `<= 1e-12`.

### G2—Initial compact-phase closure

At `N=48` for the closed seed:

- `|Q_Y - 2| <= 0.05`;
- `|Q_I + 3| <= 0.05`;
- `c_Y >= 0.20` and `c_I >= 0.20`.

### G3—Initial double-helical geometry

At `N=48`:

- closed seed `H >= 0.80` and `O >= 0.80`;
- untwisted seed `H <= 0.20`.

### G4—Component ratio and virial calibration

- relative component-ratio error `<= 1e-5`;
- reference relative virial residual

\[
\frac{|2K+W|}{2K+|W|}
\le 1e-5.
\]

Failure of G1–G4 makes the protocol invalid and stops all evolution.

### Q1—Finite evolution

Every stored field and scalar must remain finite. Any failure stops the affected arm and makes its scientific verdict `INCONCLUSIVE`.

### Q2—Mass conservation

Every arm must satisfy

\[
\max_t\frac{|M(t)-M(0)|}{M(0)}\le 2\times10^{-4}.
\]

### Q3—Energy conservation

Every evolved arm must satisfy

\[
\max_t\frac{|E(t)-E(0)|}{\max(|E(0)|,K(0),10^{-12})}
\le 5\times10^{-3}.
\]

### Q4—Time-step convergence

Between arms A and J at `t_end`, each of the following must differ by at most `5%` relative to the larger magnitude, with an absolute floor of `1e-8`:

- `R_fit`;
- core retention;
- `H`;
- `O`.

Their windings must differ by at most `0.10` turns.

### Q5—Resolution convergence

Between arms A (`N=48`) and I (`N=64`) at `t_end`:

- `R_fit`, core retention, `H`, and `O` must differ by at most `10%` relative to the larger magnitude, with an absolute floor of `1e-8`;
- each winding must differ by at most `0.10` turns;
- the direction of every primary pass/fail inequality must agree.

Arm H (`N=32`) is diagnostic and does not control Q5.

Failure of Q1–Q5 makes the primary dynamical verdict `INCONCLUSIVE`.

### S1—Winding survival

For every report from arm A:

- `|Q_Y - 2| <= 0.25`;
- `|Q_I + 3| <= 0.25`;
- `c_Y >= 0.05` and `c_I >= 0.05`.

### S2—Localization survival

For arm A at `t_end`:

- core retention `>= 0.75`;
- `0.80 <= R_fit(t_end)/R_fit(0) <= 1.20`;
- for every report at `t >= 1.0`, `0.75 <= R_fit(t)/R_fit(0) <= 1.25`;
- center displacement `<= 0.25 R0`.

### S3—Double-helical survival

For arm A at `t_end`:

- `H(t_end)/H(0) >= 0.70`;
- `O(t_end) >= 0.70`.

### P1—Perturbation survival

Arm G must satisfy S1–S3. At `t_end`, its `R_fit`, core retention, `H`, and `O` must each lie within `15%` of arm A, using the same relative convention as Q4.

---

## 8. Frozen verdict tree

1. If G1–G4 fail, verdict: `INCONCLUSIVE—INVALID INITIALIZATION`.
2. If Q1–Q5 fail, verdict: `INCONCLUSIVE—NUMERICAL QUALITY`.
3. If S1, S2, and S3 pass, primary verdict: `EMERGES CONDITIONALLY`.
4. If numerical quality passes and any of S1–S3 fails, primary verdict: `DOES NOT EMERGE`.
5. P1 is reported independently as `PASS`, `FAIL`, or `UNSCORED` when the primary verdict is inconclusive.

Failure labels are assigned from the first applicable category while all categories remain reported:

- `UNWINDS`—S1 failure;
- `DELOCALIZES`—core-retention failure;
- `RADIUS COLLAPSES` or `RADIUS EXPANDS`—radius failure;
- `HELIX DISSOLVES`—S3 failure;
- `DRIFTS`—center-motion failure.

Control interpretations are descriptive:

- arm B measures free dispersive loss;
- arm C tests whether toroidal closure alone reproduces helical order;
- arm D tests an open strand under the same binding interaction;
- arm E tests incoherent compact phases at fixed closed density;
- arm F verifies that the supplied gravity can retain a localized seed at the frozen mass.

Control outcomes do not override the frozen verdict tree.

---

## 9. Frozen stopping rules

An arm stops immediately if:

- any field or scalar becomes nonfinite;
- maximum density exceeds `1.0e8` times its initial value;
- GPU or CPU memory allocation fails;
- a runtime exception prevents a complete field update.

No parameter, seed, threshold, report time, arm, or field equation may change after the first evolution begins. An implementation defect discovered before evolution may be repaired while preserving this document. A defect discovered after evolution yields an invalid run; the defect and invalidation must be recorded before any replacement preregistration.

---

## 10. Frozen artifacts and independent verification

Implementation paths:

- primary probe: `field-experience/toroidal_coherence_survival_probe.py`;
- independent verifier: `field-experience/verify_toroidal_coherence_survival.py`;
- report: `field-experience/toroidal-coherence-survival-report.md`.

Run receipts:

```text
runs/<UTC>_toroidal_coherence_survival/
  results.json
  fields_<arm>.npz
  verification.json
```

`results.json` must contain:

- full frozen constants;
- device and dtype;
- source SHA-256 values;
- virial calibration values;
- every arm's full diagnostic time series;
- every gate result;
- the verdict and failure labels;
- SHA-256 values for all field receipts.

Each `fields_<arm>.npz` must contain the complex Yang and Yin fields at every report time. The independent verifier must load those arrays, recompute all diagnostics and gates without importing the primary probe, check every stored hash, and create `verification.json` with exclusive creation. Verification fails on any field, metric, gate, hash, or verdict mismatch.

---

## 11. Interpretation boundary

`EMERGES CONDITIONALLY` supports survival of a seeded toroidal double helix in this supplied Schrödinger–Poisson realization. It leaves spontaneous formation, unique mass selection, relativistic covariance, gauge charge, spinor structure, quantum statistics, and experimental correspondence open.

`DOES NOT EMERGE` rejects survival under the frozen realization and parameters. It does not reject every conservative phase-bearing Yang/Yin extension.

The existing one-dimensional ring result remains governed by `field-experience/qi-loop-mass-cascade-report.md`. The existing dissipative soliton result remains governed by `field-experience/soliton-self-trapping-report.md`.
