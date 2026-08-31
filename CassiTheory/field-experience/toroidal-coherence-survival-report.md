# Toroidal Coherence Survival Report

## Status: V5 finite-time toroidal survival DOES NOT EMERGE—August 2026

## 1. Campaign outcome

The adopted campaign verdict is `DOES NOT EMERGE`. V5 passes G1–G4,
Q1–Q5, and independent verification, then fails all three survival gates.
The tested seed changes Yang winding from `+2` to `+3`, contracts to radius
ratio `0.4468592782418393`, and retains `0.3459793652013782` of its initial
helical order by `t=4`. The canonical V5 receipts are
`runs/20260831T223517Z_toroidal_coherence_survival_v5/results.json` and
`runs/20260831T223517Z_toroidal_coherence_survival_v5/verification.json`.

### 1.1 V1 initialization record

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

## 2. V1 initialization attribution

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

## 5. V3 diagnostic and initialization outcome

The preregistered V3 diagnostic at
`field-experience/toroidal-coherence-survival-v3-pre-registration.md`
separates compact-phase cancellation from angular-sector support. The original
sector ratio remains a reported secondary statistic.

The V3 receipt is
`runs/20260831T214821Z_toroidal_coherence_survival_v3/results.json`. Its closed
seed passes G1–G4:

| initialization check | frozen threshold | measured Yang/Yin values | result |
|---|---:|---:|---|
| winding | `+2 +/- 0.05`, `-3 +/- 0.05` | `2.0`, `-2.999999523162842` | pass |
| normalized phase coherence | `>= 0.95` | `0.9970051050186157`, `0.993269145488739` | pass |
| sector support | `>= 0.05` | `0.16976575553417206`, `0.16974914073944092` | pass |
| expected-winding demodulation | `>= 0.95` | `0.9981433749198914`, `0.9958257079124451` | pass |
| scrambled demodulation | `<= 0.50` | `0.007504949811846018`, `0.0071093132719397545` | pass |
| closed helical order | `>= 0.80` | `0.8272420763969421` | pass |
| closed opposition | `>= 0.80` | `1.0` | pass |

All ten frozen evolution arms complete.

## 6. V3 numerical-quality and verification outcome

The primary receipt returns

```text
INCONCLUSIVE—NUMERICAL QUALITY
```

Q1 passes. Q2–Q5 fail:

| gate | decisive measured failure |
|---|---|
| Q2 mass drift | arm J reaches `0.0003180003274592607` against `2e-4` |
| Q3 energy drift | arm E reaches `0.00545355761197847` and arm F reaches `0.012834079133810492` against `5e-3` |
| Q4 time-step agreement | opposition differs by `0.1469912790648769` against `0.05` |
| Q5 resolution agreement | helical order differs by `0.42654960357489435`; the winding difference is `1.0` turn |

The primary arm reaches `Q_Y=2` and `Q_I=-4`, normalized phase coherences
`0.02713826671242714` and `0.002970354398712516`, fitted radius
`1.8213273286819458`, core fraction `0.4651115834712982`, helical order
`0.16416975855827332`, and opposition `0.4533253610134125` at `t=4`.
These values trigger the provisional labels `UNWINDS`, `DELOCALIZES`,
`RADIUS COLLAPSES`, and `HELIX DISSOLVES`. They do not receive a scientific
survival verdict because Q2–Q5 fail.

The frozen independent verifier writes
`runs/20260831T214821Z_toroidal_coherence_survival_v3/verification.json` with
`pass: false`. It validates all source and field hashes and independently
reproduces G1–G4, Q2–Q5, the failure labels, and
`INCONCLUSIVE—NUMERICAL QUALITY`, but its metric comparison rejects
near-zero virial residual differences and opposition values in the untwisted
control. V3 therefore remains verification-invalid as well as numerically
inconclusive. Neither failure can be repaired by changing a frozen V3 source.

## 7. V4 numerical-quality outcome

The V4 protocol at
`field-experience/toroidal-coherence-survival-v4-pre-registration.md` preserves
the V3 physical seed and thresholds while evolving complex128 fields at
`dt=0.0025`. Its canonical receipt is
`runs/20260831T220853Z_toroidal_coherence_survival_v4/results.json`.

G1–G4, Q1, Q2, and Q4 pass. Q3 fails only in the spherical morphology
control F, whose maximum relative energy drift is `0.013280009933384629`
against `0.005`. Q5 fails only on the final opposition comparison:
`0.387179711030671` against `0.10`. Its radius, core-fraction, and helical-order
differences are `0.015390880742869267`, `0.04267667050243896`, and
`0.006365311339941107`; winding difference is numerical zero, and the
survival directions agree.

The primary and high-resolution arms both fail S1–S3. The primary arm ends
with `Q_Y=3`, `Q_I=-3`, fitted radius `1.9081618326792957`, core fraction
`0.6106873908594572`, helical order `0.2862566004695367`, and opposition
`0.5517105158580615`. The high-resolution arm ends with fitted radius
`1.9379894890607853`, core fraction `0.6379154766527391`, helical order
`0.28809060514519856`, and opposition `0.3380990349612745`. V4 therefore
returns

```text
INCONCLUSIVE—NUMERICAL QUALITY
```

The provisional labels `UNWINDS`, `RADIUS COLLAPSES`, and `HELIX DISSOLVES`
remain unadopted because Q3 and Q5 fail.

## 8. V4 verification outcome

The independent receipt
`runs/20260831T220853Z_toroidal_coherence_survival_v4/verification.json`
validates the frozen hashes, finite values, and complex128 field payloads. It
independently reproduces every gate, the failure labels, and
`INCONCLUSIVE—NUMERICAL QUALITY`.

Its final `pass` is `false`. The maximum normalized metric discrepancy is
`1.3396209321286581e-06`, above the frozen `1e-6` relative comparison
tolerance. The discrepancy is confined to energy diagnostics and Q3 drift
values. The V4 primary program inherits an energy accumulator initialized in
float32, so the declared all-float64 diagnostic path is not implemented.
V4 is therefore verification-invalid as well as numerically inconclusive.
Its frozen sources and canonical receipts remain unchanged.

## 9. V5 numerical-quality closure

The V5 protocol at
`field-experience/toroidal-coherence-survival-v5-pre-registration.md` uses a
true float64 energy accumulator, the fixed fourth-order symmetric triple-jump
integrator, and the bounded opposed-helical-moment convergence statistic. Its
canonical receipt is
`runs/20260831T223517Z_toroidal_coherence_survival_v5/results.json`.

G1–G4 and Q1–Q5 pass. The largest relative mass drift is
`2.3327780078232793e-12`. The largest normalized energy drift is
`0.00026232696068808405` in spherical control F, below the frozen `0.005`
limit. The time-step comparison has maximum reported difference
`1.4901146615082639e-06`, and its opposed-helical-moment difference is
`3.064535102348387e-07`. The resolution comparison reports:

| final A/I comparison | measured difference | frozen limit | result |
|---|---:|---:|---|
| fitted radius | `0.01540882452127678` | `0.10` relative | pass |
| core fraction | `0.04279022845967436` | `0.10` relative | pass |
| helical order | `0.006410302463782939` | `0.10` relative | pass |
| opposed helical moment | `0.017027415709989863` | `0.10` absolute | pass |
| winding | `0.0` turns | `0.10` turns | pass |
| S1–S3 direction | agreement | agreement | pass |

## 10. V5 survival outcome

The primary arm fails S1, S2, and S3:

- Yang winding changes from `+2` to `+3`; final Yang/Yin normalized phase
  coherences are `0.049387464981092734` and `0.0418586687756659`, below the
  `0.50` survival floors;
- fitted radius contracts from `4.269998986912655` to
  `1.9080886653851739`, a ratio of `0.4468592782418393` against the
  `[0.80,1.20]` final band;
- helical order falls from `0.8273853869634591` to
  `0.2862582709585142`, a retention ratio of `0.3459793652013782` against
  `0.70`, while final raw opposition is `0.5518768949443402` against
  `0.70`.

Core retention remains `0.9994728037392738`, and center displacement remains
`0.10985113653688641`; these passing submetrics do not change S2. The
high-resolution arm independently gives Yang/Yin windings `+3/-3`, fitted
radius `1.9379501999471325`, core fraction `0.6378965084148845`, and helical
order `0.2881051118669433`, with the same S1–S3 directions.

The adopted failure labels are `UNWINDS`, `RADIUS COLLAPSES`, and
`HELIX DISSOLVES`. Perturbation arm G also fails S1–S3, so P1 is `FAIL`. With
all numerical-quality gates passing, the frozen decision tree returns

```text
DOES NOT EMERGE
```

for finite-time survival of this supplied toroidal double-helix seed.

## 11. V5 independent verification

The independent receipt
`runs/20260831T223517Z_toroidal_coherence_survival_v5/verification.json`
returns `pass: true` with an empty error list. It validates every source and
field hash, confirms finite complex128 fields, independently recomputes
G1–G4, Q1–Q5, S1–S3, P1, the failure labels, and `DOES NOT EMERGE`. Its
maximum normalized metric discrepancy is `3.65019126036259e-12` under the
unchanged V4 comparison tolerance. The canonical results SHA-256 is
`5004c720e2e245c8cd9a8b8192f0bb7e62a0d03d0a9240e3eea4a3b7669809c6`.

## 12. Campaign verdict

V1 and V2 stop during initialization. V3 and V4 evolve complete matrices but
remain numerically inconclusive and verification-invalid. V5 closes the
declared numerical-quality and independent-verification gates and supplies
the campaign's adopted three-dimensional result:

> The seeded Yang/Yin toroidal double helix does not survive to `t=4` in the
> supplied two-component Schrödinger–Poisson model at the frozen mass,
> geometry, controls, and diagnostic thresholds.

This finite-time result covers the registered seed and parameter set.
Spontaneous topology formation, other seeds or couplings, unique mode or mass
selection, relativistic completion, and experimental correspondence remain
open.

## 13. Scientific boundary

The supplied one-dimensional loop Hamiltonian remains independently
reverified through Q5 at
`runs/20260827T120451Z_qi_loop_mass_cascade/results.json`. V5 shows that its
declared three-dimensional toroidal realization fails finite-time compact
phase, radius, and helical-order survival. The conditional algebraic loop
skeleton therefore has no surviving open-space representative in this tested
realization.
