# Counterflow Resonant Addressing (Wave 1) Report

## Status: Hypothesized—August 2026

## Abstract

Wave 1 executed the frozen protocol in `field-experience/counterflow-resonant-addressing-pre-registration.md` using the unmodified canonical PDE/RK2 evolution between additive probe pulses. The run has protocol-validity **FAIL** under its quality gates: seed-angle-matched repeated redistribution pulses depleted the diffuse reservoir until the canonical positivity floor was contacted. The repository-level terminal classification is **INCONCLUSIVE** because the floor-contact gate invalidated the discriminator; the pre-registration's `INVALID` branch is retained as a protocol state, not as a scientific terminal label. The receipt preserves a useful infrastructure result—paired counterflow, local density-plane diagnostics, event-triggered scheduling, and exact pulse-norm matching all executed as specified—but it does not provide a valid contrast for seed-angle selectivity, checkerboard routing, or counterflow dependence. The pulse, trigger, and schedule are supplied by the additive probe; this run does not test endogenous phase-address selection.

The protocol's `phase` contrast, `phase_wrong` arm, and related receipt
terminology name the seeded $(\rho,\varepsilon)$ angle controls. The readout
called $J_z$ in the receipt is the density-plane diagnostic $J_{d,z}$, with
historical `j*` keys retained for compatibility. It is distinct in units from
the amplitude current $J_\Psi$ and has no transport interpretation without a
constitutive law.

## 1. Frozen execution

**Script:** `field-experience/counterflow_resonant_addressing_probe.py`  
**Receipt:** `runs/20260818_164007_counterflow_resonant_addressing/results.json`  
**Device:** ROCm through `torch.cuda`  
**Protocol:** $48^3$, five-channel gate, $\lambda=0.05$, $dt=0.001$, $t_{\rm end}=4.0$, 50 seed-angle evaluation events per normalized time unit.

The six frozen arms completed with fresh solvers:

| arm | pulses | mean event response | terminal $E_Y$ minimum | floor contact |
|---|---:|---:|---:|---|
| `baseline` | 0 | — | 0.9990 | no |
| `matched` | 199 | $+5.39\times10^{-4}$ | 0.0010 | yes |
| `phase_wrong` | 199 | $-1.02\times10^{-4}$ | 0.9775 | no |
| `spatial_shuffled` | 199 | $+4.01\times10^{-4}$ | 0.0010 | yes |
| `counterflow_reversed` | 199 | $+5.39\times10^{-4}$ | 0.0010 | yes |
| `counterflow_zero` | 199 | $+2.09\times10^{-3}$ | 0.0771 | no |

The matched schedule accepted all 199 available cadence events. Every replay arm used that schedule. The `phase_wrong` contrast changes only the supplied seed angle at the pulse construction; `spatial_shuffled` changes the supplied spatial/label arrangement; `counterflow_reversed` reverses the supplied shared-flow and seeded-gradient signs; and `counterflow_zero` removes that supplied counterflow proxy. Thus these controls discriminate the tested additive construction and its seeded inputs, not an independently evolving or endogenous phase-address mechanism.

## 2. Protocol gates

| gate | result |
|---|---|
| no-op wrapper versus direct canonical RK2 | PASS, maximum difference $0.0$ after 100 steps |
| finite fields | PASS |
| pulse doublet-norm parity | PASS, norm span $0.0$ |
| pulse global $\rho$ and $\varepsilon$ balance | PASS to the frozen $10^{-12}$ tolerance |
| at least 30 matched events | PASS, 199 events |
| seeded flow and density-plane diagnostic signs | PASS: $\bar u_{z,\rm right}=+0.11109$, $\bar u_{z,\rm left}=-0.11109$, $\bar J_{d,z,\rm right}=-0.008805$, $\bar J_{d,z,\rm left}=+0.008805$ |
| no $E_Y/E_I$ floor contact | FAIL |

The first floor contact occurs at $t=3.501$ in `matched`, `spatial_shuffled`, and `counterflow_reversed`. The raw pre-step pulse minimum in the matched arm reaches $E_Y=6.847\times10^{-4}$ before the canonical RK2 clamp restores the $10^{-3}$ floor.

## 3. Classification

The pre-registered decision tree requires every quality gate to pass before contrasts are classified. The floor contact selects the protocol's `INVALID` quality-gate branch. At repository level, because the discriminator is not protocol-valid, the Wave 1 terminal classification is:

$$
\boxed{\text{INCONCLUSIVE}}
$$

The contrast estimates are retained as density-plane diagnostic values only:

The contrast labels `phase-wrong` and `spatial-shuffled` are frozen
protocol names. `phase-wrong` denotes the seed-angle-wrong control and does
not compare independently evolved periodic phases.

| contrast | mean | 95% paired block-bootstrap interval |
|---|---:|---:|
| matched minus phase-wrong | $+5.76\times10^{-4}$ | $[-2.72,\,+2.92]\times10^{-3}$ |
| matched minus spatial-shuffled | $+1.02\times10^{-4}$ | $[-1.71,\,+1.42]\times10^{-3}$ |
| matched minus reversed counterflow | $+7.11\times10^{-15}$ | $[-0.91,\,+17.85]\times10^{-15}$ |
| matched minus zero counterflow | $-1.53\times10^{-3}$ | $[-3.80,\,+0.30]\times10^{-3}$ |

None reaches the frozen $0.05$ response margin or excludes zero. The protocol-validity **FAIL** independently leaves this Wave 1 line **INCONCLUSIVE**.

## 4. Mechanism diagnosis

This diagnoses a missing feature of the tested construction: a continual source-reservoir model or a bounded seed-angle synchronization operator. Both are supplied by the probe rather than native canonical dynamics; the unmodified canonical solver contains neither as a native mechanism. A valid follow-up requires a new pre-registration that chooses one of those models, freezes its invariant, and maintains the floor constraint.

## 5. Scope

Wave 1 establishes that the selected counterflow proxy, density-plane diagnostic readout, event schedule, and exact-norm control machinery execute on the unmodified canonical solver when wrapped by the additive probe. It leaves seed-angle-selective addressing, checkerboard routing, and counterflow dependence unresolved; no endogenous phase-address result is obtained.

## References

- `field-experience/counterflow-resonant-addressing-pre-registration.md`—frozen protocol and decision tree.
- `field-experience/counterflow_resonant_addressing_probe.py`—additive execution and receipt writer.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical solver and positivity clamp.
- `foundations/qi-flow-double-helix.md`—density-plane diagnostic definitions and transport boundary.
