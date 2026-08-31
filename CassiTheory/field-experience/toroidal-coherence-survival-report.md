# Toroidal Coherence Survival Report

## Status: Two invalid initializations; no dynamical verdict—August 2026

## 1. Outcome

The frozen protocol in `field-experience/toroidal-coherence-survival-pre-registration.md` stopped before field evolution with

```text
INCONCLUSIVE—INVALID INITIALIZATION
```

The receipt is `runs/20260831T205711Z_toroidal_coherence_survival/results.json`.

The analytic centerlines closed, both compact phases carried their declared integer windings, the component ratio matched `phi`, the virial calibration closed, and the untwisted control was discriminated. The seeded closed density pair did not reach the frozen initial double-helical order threshold:

| initialization check | frozen threshold | measured value | result |
|---|---:|---:|---|
| analytic endpoint mismatch | `<= 1e-12` | `1.2488995852222597e-15` | pass |
| Yang winding | `2 +/- 0.05` | `2.0` | pass |
| Yin winding | `-3 +/- 0.05` | `-2.999999523162842` | pass |
| Yang sector coherence | `>= 0.20` | `0.2677786648273468` | pass |
| Yin sector coherence | `>= 0.20` | `0.2681727409362793` | pass |
| closed helical order | `>= 0.80` | `0.670671820640564` | **fail** |
| closed strand opposition | `>= 0.80` | `1.0` | pass |
| untwisted helical order | `<= 0.20` | `4.4526145757117774e-06` | pass |
| relative component-ratio error | `<= 1e-5` | `2.1088e-07` | pass |
| relative virial residual | `<= 1e-5` | `0.0` | pass |

No survival, control, perturbation, resolution, or time-step arm evolved. The receipt therefore supplies no spatial-loop stability verdict.

## 2. Initialization attribution

The frozen strand offset and density width were

```text
a = 1.0
sigma = 0.75
```

The two density tubes were exactly opposed, as shown by opposition `1.0`, while their finite cross-sectional width reduced the first poloidal helical moment to `0.670671820640564`. G3 correctly rejected that seed as an insufficiently resolved double helix for the declared `H >= 0.80` survival test.

This initialization failure carries no evidence about dynamical survival.

## 3. V1 independent-verifier boundary

The frozen V1 verifier reaches a `KeyError: 'arms'` because its invalid-initialization receipt contains `preflight` and no evolved `arms` map. It creates no `verification.json`. The primary receipt remains preserved without overwrite, and its exact verifier source remains unchanged at `field-experience/verify_toroidal_coherence_survival.py`.

## 4. V2 initialization outcome

The V2 initialization protocol in `field-experience/toroidal-coherence-survival-v2-pre-registration.md` uses

```text
a = 1.20
sigma = 0.60
```

Its receipt is `runs/20260831T210445Z_toroidal_coherence_survival_v2/results.json`, with independent verification at `runs/20260831T210445Z_toroidal_coherence_survival_v2/verification.json`.

The narrower, more separated strands pass G3: closed helical order is `0.8272420763969421`, opposition is `1.0`, and untwisted order is `2.545056645431032e-07`. G2 fails because the 64-sector coherence floors are `0.1700311303138733` for Yang and `0.17034706473350525` for Yin, below the frozen `0.20` threshold. The measured windings remain exactly `+2` and `-3`.

The independent verifier reports `pass: true`, recomputes `G1=true`, `G2=false`, `G3=true`, `G4=true`, and reproduces

```text
INCONCLUSIVE—INVALID INITIALIZATION
```

No V2 dynamical arm evolved.

## 5. Campaign boundary

The V1 geometry passes the sector-coherence floor and fails helical order. The V2 geometry passes helical order and fails the frozen 64-sector coherence floor. Both failures occur in initialization diagnostics before evolution.

The campaign therefore stops without a spatial survival, control, perturbation, resolution, or time-step result. A different sector diagnostic or seed family constitutes a new diagnostic hypothesis with its own preregistration; it cannot continue this frozen campaign.

## 6. Scientific boundary

The supplied one-dimensional loop Hamiltonian remains independently reverified through Q5 at `runs/20260827T120451Z_qi_loop_mass_cascade/results.json`. These initialization receipts do not extend that conditional result into three-dimensional open-space dynamics.
