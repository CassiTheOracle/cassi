# Source-Only Field-Space Timing (Wave 6)

## Status: Hypothesized—August 2026

## Abstract

Wave 6 keeps the Wave 5 source-only physical construction and changes only the receiver readout. It removes projected $\mathbf J_\Psi$, local $J_{\rm rms}$ normalization, and direct-receiver pulse denominators from the classifier. The observable is the compact-window, projection-free difference in the amplitude pair $(A,B)=(\sqrt{E_Y},\sqrt{E_I})$ between matched $+/-$ source-pulse runs. It tests timing within the finite proxy; it does not test finite-speed propagation or prescribe an edge interaction.

## 1. Motivation and frozen hypothesis

`field-experience/source-only-passive-transfer-wave-5-report.md` records a valid HOLD with a source/disjoint receiver construction. Its current-projection readout has an immediate axial signal and strongly receiver-dependent direct-calibration denominators. Wave 6 leaves the source, pulse, grid, solver, and source-label controls unchanged while replacing only that readout.

The frozen hypothesis is:

> A compact target-only phase pulse produces a field-space perturbation whose diagonal receiver accumulates later than the equal-distance axial probe, and this timing relationship depends on the finite proxy's phase labels.

No receiver, corridor, saddle, or velocity profile is driven. No Wave 5 fraction, direct calibration, or threshold is used in the Wave 6 classifier.

## 2. Frozen construction

Use the Wave 5 canonical construction without its direct receiver-pulse arms:

$$
N=48,\quad dt=0.001,\quad n_p=100,\quad n_{\rm end}=260,
\qquad T=(12,12,24),\quad D=(24,24,24),\quad A=(12,29,24).
$$

The target compact bump $b_T$ and normalized passive weights $\chi_D,\chi_A$ use radius six cells exactly as in `field-experience/source-only-passive-transfer-pre-registration.md`. The support gate is unchanged:

$$
\max(b_Tb_D)=\max(b_Tb_A)=0.
$$

At $n_p$, each source arm requires the same target phase-match condition $M\geq\cos(\pi/6)$. It receives the same one-shot amplitude-space $SO(2)$ rotation with $+/-$ sign, 48 bisection steps, $\beta\in[0,0.05]$, target kick norm $0.45$, pointwise $\rho$ preservation, global-mass preservation, floor, and wedge requirements.

## 3. Frozen arms

| arm | initial labels | pulse mask | sign |
|---|---|---|---:|
| `baseline` | standard | none | 0 |
| `source_plus`, `source_minus` | standard | $b_T$ | $+1,-1$ |
| `source_shuffled_plus`, `source_shuffled_minus` | diagonal/left-lower phase-label shuffle | $b_T$ | $+1,-1$ |

Every arm starts from a fresh solver. There are no direct-diagonal, direct-axial, corridor, or velocity-drive arms.

## 4. Projection-free field-space observable

For matched source-pulse runs, define

$$
A^\pm=\sqrt{E_Y^\pm},\qquad B^\pm=\sqrt{E_I^\pm},
$$

$$
\delta A=\frac{A^+-A^-}{2},\qquad
\delta B=\frac{B^+-B^-}{2},
$$

and, for $R\in\{D,A\}$,

$$
q_R(k)=\frac{1}{0.45}
\sqrt{\sum_{\mathbf x}\chi_R(\mathbf x)
\left[\delta A(\mathbf x,k)^2+\delta B(\mathbf x,k)^2\right]}.
$$

The pulse snapshot $k=0$ occurs after the source rotation and before the first following canonical RK2 step. Since the source core is disjoint from both passive receiver cores, require

$$
q_D(0)\leq10^{-12},\qquad q_A(0)\leq10^{-12}.
$$

This is a physical-field support gate. It does not require the FFT-derived phase-current projection to vanish at $k=0$.

For telemetry only, record the Wave 5 projected-current antisymmetry

$$
S_R(0)=\frac{j_R^+(t_p)-j_R^-(t_p)}{2},
$$

and label nonzero $S_R(0)$ with zero $q_R(0)$ as a gradient-readout observation. It does not enter the classifier.

## 5. Frozen timing metrics

Over $k=1,\ldots,120$, let

$$
W_R=\sum_{k=1}^{120}q_R(k)^2,
\qquad
k_{50,R}=\min\left\{k:\sum_{\ell=1}^{k}q_R(\ell)^2\geq\frac{W_R}{2}\right\},
$$

$$
\iota_R=\frac{q_R(1)^2}{W_R},
\qquad
p_R=\frac{\sum_{k=20}^{120}q_R(k)^2}{W_R},
\qquad
Q_R^{\rm late}=\sqrt{\frac{1}{101}\sum_{k=20}^{120}q_R(k)^2}.
$$

A timing trace is detectable only if $Q_D^{\rm late}\geq10^{-12}$ and $W_D>0$. This numerical floor is fixed before execution and is independent of the Wave 5 current readout.

Define the standard-label delayed condition

$$
\mathcal D:\quad k_{50,D}>k_{50,A}\quad\text{and}\quad p_D>p_A.
$$

Define $\mathcal D_{\rm shuf}$ by the same strict inequalities for the shuffled source pair. Exact ties do not satisfy a delayed condition. A timing condition is defined only when both $W_D$ and $W_A$ are positive in its label setting; undefined shuffled timing cannot satisfy F3 and yields an INCONCLUSIVE source result.

## 6. Quality gates

The run is **INVALID** if any condition fails:

1. synthetic field-space checks give $q=0$ for equal field pairs and $q=1$ for a unit antisymmetric pair after normalization;
2. the actual read-only field-space trace wrapper differs from 100 direct canonical RK2 steps;
3. compact target/receiver support overlaps or either pulse-snapshot field-space value exceeds $10^{-12}$;
4. any source arm fails the frozen target phase-match criterion at $n_p$;
5. any field is non-finite, reaches the $10^{-3}$ floor, violates the fixed wedge, or lacks its 261-sample trace;
6. any active pulse lacks capacity below $\beta=0.05$, has norm error above $10^{-12}$, pointwise $\rho$ error above $10^{-12}$, or relative global-mass error above $10^{-12}$.

A valid run with $W_D=0$ or $Q_D^{\rm late}<10^{-12}$ is a result of no detectable diagonal field-space response, not an INVALID execution.

## 7. Frozen decision tree

| feature | condition | label |
|---|---|---|
| F1 diagonal field-space response | $W_D>0$ and $Q_D^{\rm late}\geq10^{-12}$ | EMERGES / DOES NOT EMERGE |
| F2 delayed diagonal timing | $\mathcal D$ | EMERGES / DOES NOT EMERGE |
| F3 label-specific timing | $\mathcal D$ and not $\mathcal D_{\rm shuf}$ | EMERGES / DOES NOT EMERGE |

The hypothesis **SUPPORTS** only if F1, F2, and F3 emerge. It returns **HOLD** if F1 and F2 emerge while F3 does not. It **CONTRADICTS** if F1 does not emerge or if

$$
k_{50,D}\leq k_{50,A}\qquad\text{and}\qquad\iota_D\geq\iota_A,
$$

which is the frozen immediate/global timing branch. Other valid outcomes are **INCONCLUSIVE**.

## 8. Scope

The canonical RHS contains diffusion and FFT-mediated Poisson and gradient operations, with two RHS evaluations per RK2 step. A delayed field-space rise can distinguish this finite proxy's post-step timing from a $k=0$ field rotation, but it cannot establish finite-speed causation, a physical bubble-edge transport law, a self-maintaining macro-spiral, biological circulation, neural action, or consciousness.

## References

- `field-experience/source-only-passive-transfer-pre-registration.md`—frozen source-only physical construction and amplitude-space kick.
- `field-experience/source-only-passive-transfer-wave-5-report.md`—current-projection HOLD and measurement boundary.
- `field-experience/source_only_passive_transfer_probe.py`—Wave 5 compact support and canonical wrapper implementation.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical RHS and RK2 evolution.
