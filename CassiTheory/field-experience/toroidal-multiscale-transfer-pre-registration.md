# Toroidal Spectral-Transfer Diagnosis

## Status: Preregistered—August 2026

## Abstract

This secondary analysis asks where modal mass, kinetic activity, gravitational binding, and helical order move while the verified V5 toroidal seed unwinds, contracts, and loses helical coherence. It analyzes frozen complex128 snapshots from one single-domain, single-hierarchy-level Schrödinger–Poisson experiment. It is a spectral-scale diagnosis, not a multiscale physical experiment.

The primary hypothesis is that the V5 failure is accompanied by resolved forward redistribution from box/toroidal modes into fine modes. The no-gravity, spherical, perturbed, high-resolution, and half-step arms distinguish free dispersion, generic gravitational focusing, topology-associated transfer, perturbation sensitivity, resolution dependence, and time-step dependence.

No V5 source, field, threshold, gate, or verdict changes. No field evolves during this analysis.

---

## 1. Frozen input and scope

Canonical input directory:

```text
runs/20260831T223517Z_toroidal_coherence_survival_v5/
```

Required receipts:

- `results.json`, SHA-256 `5004c720e2e245c8cd9a8b8192f0bb7e62a0d03d0a9240e3eea4a3b7669809c6`;
- `verification.json` with `pass: true` and an empty error list;
- the field files and hashes declared by `results.json` for arms A, B, F, G, I, and J.

The V5 physical domain remains a periodic cube of side `16.0`. Its registered geometry has major radius `4.0`, strand offset `1.20`, and width `0.60`. The resolution arms represent the same physical domain and seed; they are numerical convergence controls rather than additional physical hierarchy levels.

The analysis includes smaller scales generated during evolution. It contains no independently initialized core, nested domain, external matter, cascade-rung field, boundary flux, or bidirectional exchange with another physical level.

---

## 2. Frozen spectral bands

For each arm, define the fundamental wave number

\[
k_f=\frac{2\pi}{L_{\rm box}},
\qquad
q=\frac{|\mathbf k|}{k_f}.
\]

The fixed isotropic bands are

| band | normalized wave number |
|---|---|
| B0 | `0 <= q < 2` |
| B1 | `2 <= q < 4` |
| B2 | `4 <= q < 8` |
| B3 | `8 <= q < 16` |
| B4 | `q >= 16` |

The fine set is `B3 + B4`, equivalently `q >= 8`. These grid-independent boundaries are powers of two in normalized wave number. They are not a claim of $\varphi$-selected physical scales.

All Fourier transforms use `norm="ortho"`. Every shell mask is exhaustive and mutually exclusive.

---

## 3. Frozen spectral observables

For component $a\in\{Y,I\}$, let $\widehat\psi_a$ be its orthonormal Fourier transform. With cell volume $\Delta V$, modal mass in band $b$ is

\[
M_b=\Delta V\sum_{a}\sum_{\mathbf k\in b}|\widehat\psi_a|^2,
\qquad
m_b=\frac{M_b}{\sum_cM_c}.
\]

Kinetic energy and fraction are

\[
K_b=\frac{\Delta V}{2}\sum_a\sum_{\mathbf k\in b}
k^2|\widehat\psi_a|^2,
\qquad
\kappa_b=\frac{K_b}{\sum_cK_c}.
\]

For gravitational arms, with

\[
\widehat\Phi(\mathbf k)=-\frac{\widehat\rho(\mathbf k)}{k^2},
\qquad \widehat\Phi(0)=0,
\]

define

\[
W_b=\frac{g\Delta V}{2}
\sum_{\mathbf k\in b}\operatorname{Re}
\left(\widehat\rho^*\widehat\Phi\right),
\qquad
w_b=\frac{-W_b}{-\sum_cW_c}.
\]

The potential is real and $W_b\le0$ up to floating error. Arm B has no binding fractions.

### 3.1 Instantaneous modal-mass transfer

The potential term supplies the only transfer of modal mass:

\[
\widehat{\dot\psi}_{a,V}=-ig\,\widehat{\Phi\psi_a},
\]

\[
T_b=2\Delta V\sum_a\sum_{\mathbf k\in b}
\operatorname{Re}
\left(\widehat\psi_a^*\widehat{\dot\psi}_{a,V}\right).
\]

The positive-forward flux across `q=8` is

\[
\Pi_8=-\frac{1}{M}\sum_{q<8}T_b.
\]

The trapezoidal integral of $\Pi_8$ over stored report times is compared with the measured change in fine modal-mass fraction. It is an interval estimate at the frozen `0.25` report cadence.

### 3.2 Additive helical-order contribution

For each component density $\rho_a$ and V5 carrier

\[
c(\mathbf x)=e^{i(\theta-m\chi)},
\]
with

\[
r_\perp=\sqrt{x^2+y^2},
\qquad
\chi=\operatorname{atan2}(y,x),
\qquad
\theta=\operatorname{atan2}\!\left(z,r_\perp-r_{\rm fit}(t)\right),
\qquad
m=1.
\]

The fitted radius \(r_{\rm fit}(t)\) is the value stored in the canonical V5
metric row for the same arm and report time.

define the band contribution

\[
h_{a,b}=\frac{\Delta V}{M_a}
\sum_{\mathbf x}P_b[\rho_a](\mathbf x)c(\mathbf x),
\qquad
h_a=\sum_bh_{a,b}.
\]

Here $P_b$ is the real spectral projection of the density into band $b$. The analysis records the real and imaginary parts of every $h_{a,b}$ at initial and final time for arms A, I, and J. This decomposition includes cross-scale interference already present in the full density; it does not introduce an independently evolving substructure.

---

## 4. Frozen arms and times

| arm | use |
|---|---|
| A | primary toroidal transfer |
| B | free-dispersive control |
| F | spherical gravitational focusing control |
| G | perturbation sensitivity |
| I | high-resolution convergence |
| J | half-step convergence |

Mass, kinetic, binding, and transfer spectra are evaluated at every stored report time. Helical band vectors are evaluated only at initial and final time for A, I, and J.

No arm or time may be added after execution.

---

## 5. Frozen diagnostic-quality gates

### Q1—Input identity

- canonical `results.json` hash matches;
- canonical V5 verification has `pass: true` and no errors;
- every selected field hash matches `results.json`;
- all selected fields are complex128 and finite.

### Q2—Spectral closure

At every selected snapshot:

- band mass sums reproduce direct mass within relative `1e-10`;
- band kinetic sums reproduce the stored V5 kinetic value within `1e-6` relative;
- gravitational band sums reproduce the stored potential value within `1e-6` relative;
- mass and kinetic fractions sum to one within `1e-12`;
- gravitational binding fractions sum to one within `1e-12`.

For A, I, and J at initial and final time, summed helical band vectors reproduce the direct helical vector within absolute `1e-10`, and its magnitude reproduces the stored V5 component magnitude within `1e-6` relative.

### Q3—Transfer conservation

At every selected gravitational snapshot,

\[
\frac{|\sum_bT_b|}{\max(\sum_b|T_b|,10^{-30})}\le10^{-10}.
\]

Arm B must have exactly zero reported potential transfer.

### Q4—Interval-transfer consistency

For A, I, and J, the absolute difference between measured final-minus-initial fine mass fraction and the trapezoidal integral of $\Pi_8$ must be at most `0.05`. Their signs must agree unless both magnitudes are below `1e-8`.

### Q5—Resolution and time-step convergence

Let

\[
\Delta m_f=m_f(t_f)-m_f(0),\quad
\Delta\kappa_f=\kappa_f(t_f)-\kappa_f(0),\quad
\Delta w_f=w_f(t_f)-w_f(0),
\]

where each fine fraction sums B3 and B4. Arms I and J must each agree with A within:

- `0.03` absolute in $\Delta m_f$;
- `0.05` absolute in $\Delta\kappa_f$;
- `0.05` absolute in $\Delta w_f$;
- `0.03` absolute in integrated $\Pi_8$.

---

## 6. Frozen forward-redistribution test

A gravitational arm is classified `FORWARD` only when all four conditions hold:

\[
\Delta m_f\ge0.05,
\qquad
\Delta\kappa_f\ge0.10,
\qquad
\Delta w_f\ge0.10,
\qquad
\int\Pi_8\,dt\ge0.02.
\]

Arm B is classified `NO FORWARD` when

\[
|\Delta m_f|<0.01,
\qquad
|\Delta\kappa_f|<0.01,
\qquad
\Pi_8=0.
\]

The helical band vectors are explanatory diagnostics. They do not alter this classification.

---

## 7. Frozen verdict tree

1. Any Q1–Q5 failure returns `INCONCLUSIVE—DIAGNOSTIC QUALITY`.
2. Q1–Q5 pass and arm A is not `FORWARD` returns `CONTRADICTS FORWARD-TRANSFER HYPOTHESIS`.
3. A is `FORWARD` and B is not `NO FORWARD` returns `INCONCLUSIVE—GRAVITY ATTRIBUTION`.
4. A and G are `FORWARD`, B is `NO FORWARD`, and F is `FORWARD` returns `SUPPORTS GENERIC GRAVITATIONAL FOCUSING`.
5. A and G are `FORWARD`, B is `NO FORWARD`, and F is not `FORWARD` returns `SUPPORTS TOROIDAL-SPECIFIC FORWARD TRANSFER`.
6. A is `FORWARD`, B is `NO FORWARD`, and G is not `FORWARD` returns `INCONCLUSIVE—PERTURBATION SENSITIVITY`.

The tree is evaluated in the listed order.

---

## 8. Frozen implementation and receipts

Implementation paths:

- primary: `field-experience/toroidal_multiscale_transfer_probe.py`;
- independent verifier: `field-experience/verify_toroidal_multiscale_transfer.py`;
- report: `field-experience/toroidal-multiscale-transfer-report.md`.

Receipt directory:

```text
runs/<UTC>_toroidal_multiscale_transfer/
  transfer.json
  verification.json
```

The primary receipt records hashes for this preregistration, both analysis programs, canonical V5 results and verification files, and every selected field file. The independent verifier recomputes the frozen summary from the canonical fields without importing the primary program.

Hashes, strings, and booleans must match exactly. Independently recomputed
floating values must satisfy

\[
|x-y|\le 10^{-10}+10^{-8}\max(|x|,|y|).
\]

---

## 9. Interpretation boundary

A supporting verdict identifies redistribution among spectral modes inside the V5 single-domain experiment. It does not establish a connected multiscale hierarchy, a $\varphi$-selected cascade, an independently initialized core, environmental support, or bidirectional exchange between physical levels. It determines which connection the next preregistered physical experiment must test.
