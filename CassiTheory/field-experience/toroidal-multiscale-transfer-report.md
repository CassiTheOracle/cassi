# Toroidal Multiscale Transfer Report

## Status: Tested—August 2026

## 1. Scope and receipt

This secondary diagnosis evaluates redistribution among Fourier bands in the frozen V5 toroidal fields. The physical calculation remains one periodic domain and one hierarchy level. The result therefore concerns generated spectral substructure inside that domain.

The frozen protocol is `field-experience/toroidal-multiscale-transfer-pre-registration.md`. The canonical analysis receipts are:

- `runs/20260831T232039Z_toroidal_multiscale_transfer/transfer.json`, SHA-256 `28f46935aeee3248dce219373394d059b0e00c8050c875d88ef4130ff63faca1`;
- `runs/20260831T232039Z_toroidal_multiscale_transfer/verification.json`, SHA-256 `c550bf7c2652ad97afb9bfca6e79141d213188e65581e32060d140b8505a7ecc`.

The primary receipt returns

```text
INCONCLUSIVE—DIAGNOSTIC QUALITY
```

Q1 and Q2 pass. Q3, Q4, and Q5 fail.

## 2. Frozen gate outcome

| gate | result | decisive value |
|---|---|---|
| Q1 input identity | pass | canonical V5 verification is clean; every selected complex128 field hash matches and every value is finite |
| Q2 spectral closure | pass | maximum mass closure `4.1948894224479027e-16`; stored kinetic discrepancy `4.0362447637868966e-16`; stored potential discrepancy `5.748153971345971e-16`; helical-vector closure `1.2571659638300646e-16` |
| Q3 transfer conservation | **fail** | maximum frozen relative residual `0.9327716406897517` against `1e-10` |
| Q4 interval transfer | **fail** | high-resolution arm I has error `0.08064316330185473` against `0.05` |
| Q5 convergence | **fail** | arm I integrated-flux difference from A is `0.10527171226274645` against `0.03` |

Q3 is controlled by a near-zero-transfer snapshot. Spherical arm F at `t=0` has total modal-transfer residual `-2.434726337941614e-14` and summed absolute band transfer `2.610206219542888e-14`; their frozen ratio is `0.9327716406897517`. The absolute residual is at roundoff scale, while the registered relative denominator is equally small. Arms A and J also reach `1.8500274292084744e-10` at `t=0`, narrowly above the frozen `1e-10` limit, with absolute residual `7.66012551783532e-15`.

Q4 uses trapezoidal integration at the V5 field-report cadence of `0.25`. A and half-step arm J pass with errors `0.016244984004536334` and `0.01624145605943872`. High-resolution arm I fails at `0.08064316330185473`.

The endpoint spectra themselves satisfy the Q5 tolerances. Relative to A, arm I differs by `0.008383564956355394` in fine mass change, `0.009921099877157613` in fine kinetic change, and `0.005195180807136532` in fine binding change. Q5 fails solely on the integrated-flux comparison. Half-step arm J passes all four convergence comparisons.

## 3. Measured endpoint redistribution

The fine set is `q >= 8`, formed by B3 and B4. The registered endpoint changes are:

| arm | use | fine mass change | fine kinetic change | fine binding change | integrated fine flux | frozen class |
|---|---|---:|---:|---:|---:|---|
| A | primary torus | `0.4700353507626928` | `0.7565406294842472` | `0.046167012060945076` | `0.48628033476722915` | not `FORWARD` |
| B | no gravity | `2.2724877535296173e-16` | `1.986258379993444e-15` | n/a | `0.0` | `NO FORWARD` |
| F | spherical gravity | `0.7684051347688541` | `0.9863422801094347` | `0.6917151920354779` | `2.0949722416752903` | `FORWARD` |
| G | perturbed torus | `0.45219625266586766` | `0.7328702592265259` | `0.015909328041162532` | `0.46497579768470293` | not `FORWARD` |
| I | high resolution | `0.4616517858063374` | `0.7466195296070895` | `0.040971831253808544` | `0.3810086225044827` | not `FORWARD` |
| J | half step | `0.4700349379177524` | `0.7565401342198258` | `0.046166810106697154` | `0.48627639397719113` | not `FORWARD` |

Primary arm A moves from fine mass fraction `0.002406783254825861` to `0.47244213401751867` and from fine kinetic fraction `0.015024365708842946` to `0.7715649951930901`. Its binding-fraction increase is `0.046167012060945076`, below the frozen `0.10` requirement, so A does not satisfy the registered four-part `FORWARD` class. The no-gravity control preserves both fine fractions to floating precision. Spherical arm F has a larger endpoint redistribution than the toroidal arms.

These endpoint values are explanatory measurements under a failed diagnostic-quality tree. They do not receive a supporting or contradicting transfer verdict.

## 4. Helical-band diagnosis

For primary arm A, the direct Yang helical magnitude falls from `0.8273853616190603` to `0.26708589225746054`; the Yin magnitude falls from `0.8273854123078576` to `0.30543064965956784`. At final time the Yang B2 contribution has magnitude `0.35763540575896446`, while its B0 and B1 contributions have magnitudes `0.11917666617863944` and `0.045881729624598654`. Their complex vector sum gives the smaller direct helical magnitude. The high-resolution and half-step arms reproduce this redistribution pattern.

The decomposition shows that loss of the registered helical order accompanies redistribution and cancellation among density bands. It does not identify an independently evolving inner structure or a transfer channel between physical hierarchy levels.

## 5. Independent verification

The independent verifier validates the frozen source and input manifests and independently reproduces Q1–Q5 and `INCONCLUSIVE—DIAGNOSTIC QUALITY`. Its final `pass` is `false` because the arm-I maximum transfer-conservation ratio differs under independent band accumulation by `4.293478670192645` normalized tolerance units. This is the single recorded comparison error:

```text
arms.I.closure_maxima.transfer_conservation: normalized difference 4.29348
```

The failing value is a maximum of an ill-conditioned relative ratio at near-zero transfer. The verifier and primary agree on the global Q3 maximum `0.9327716406897517`, every gate direction, and the terminal verdict. The frozen comparison rule still makes this receipt verification-invalid.

## 6. Result and next-test boundary

The registered diagnostic result is:

> **INCONCLUSIVE—DIAGNOSTIC QUALITY.** The V5 fields show a large, endpoint-converged increase in fine modal mass and kinetic fractions under gravity, while the frozen instantaneous-transfer conservation ratio, high-resolution interval quadrature, and independent raw-metric comparison fail their declared gates.

This result supplies design information for the connected-scale campaign. That campaign requires simultaneous inner, toroidal, and outer field structure in one conservative evolution, one shared Poisson potential, explicit cross-scale controls, and a report cadence fine enough to resolve transfer at the highest retained resolution. Transfer conservation requires an absolute roundoff floor in addition to a relative activity test. The campaign must retain endpoint spectral fractions separately from instantaneous-flux quadrature.

A connected-scale result requires its own pre-registration, evolution receipts, numerical-convergence controls, and independent verifier. The present diagnosis does not establish a physical hierarchy, bidirectional scale exchange, or a preferred scale ratio.
