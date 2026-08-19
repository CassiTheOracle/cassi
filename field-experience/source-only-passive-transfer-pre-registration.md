# Source-Only Passive Receiver Transfer (Wave 5)

## Status: Hypothesized—August 2026

## Abstract

Wave 5 tests the canonical two-fluid solver with no corridor, edge, or receiver drive. A compact bounded amplitude-space $SO(2)$ pulse acts only inside a target core; diagonal and axial probes remain passive. The experiment measures a delayed, amplitude-retaining antisymmetric receiver response relative to same-shape direct-receiver calibrations. It tests passive receiver response in the finite proxy, not finite-speed transport or a biological pathway.

## 1. Prior constraint and hypothesis

`field-experience/checkerboard-edge-phase-coupling-wave-4-report.md` records carrier selectivity under a distributed corridor kick, while its diagonal receiver lies inside the imposed drive. A passive receiver test must remove that placement ambiguity.

The frozen hypothesis is:

> A bounded phase-matched pulse confined to the target core produces a measurable passive response at the diagonal receiver that exceeds an equal-distance axial probe after each probe is normalized by its own same-shape direct-pulse response; the excess depends on the finite proxy's phase arrangement.

The canonical `rk2_step` remains unchanged. No prescribed corridor profile, tangent velocity, saddle-to-receiver source, or receiver support is allowed.

## 2. Frozen finite geometry and compact support

The source state remains the five-site finite proxy from `field-experience/counterflow_resonant_addressing_probe.py`. It is an index-lattice construction, not the physical $\varphi$-anisotropic metric.

The compact source and passive probes are

$$
T=(12,12,24),\qquad D=(24,24,24),\qquad A=(12,29,24),
$$

where $D$ is the existing diagonal bubble center and $A$ is an axial probe beyond the axial midpoint $(12,24,24)$. Their target separations are

$$
\ell_D=12\sqrt2\simeq16.971,\qquad \ell_A=17,
$$

with a relative mismatch below $0.18\%$. The axial segment encounters the proxy's axial-void direction; it is an equal-distance control window rather than a new lattice site.

For center $C$, periodic displacement $\delta_N$, and radius $R_c=6$ cells, define the compact bump

$$
b_C(\mathbf x)=
\begin{cases}
\exp\!\left[1-\dfrac{1}{1-\left(|\delta_N(\mathbf x,C)|/R_c\right)^2}\right],
& |\delta_N(\mathbf x,C)|<R_c,\\
0,& |\delta_N(\mathbf x,C)|\ge R_c.
\end{cases}
$$

The source profile is $b_T$; receiver weights are $\chi_D=b_D/\sum b_D$ and $\chi_A=b_A/\sum b_A$. Since both target-to-probe distances exceed $2R_c=12$, the physical-space source support has exactly zero overlap with either receiver core:

$$
\max(b_Tb_D)=\max(b_Tb_A)=0.
$$

This disjoint-support gate prevents direct receiver actuation by the source pulse.

## 3. Frozen pulse and execution

Use the Wave 2 amplitude representation

$$
A=\sqrt{E_Y},\qquad B=\sqrt{E_I},\qquad \rho=E_Y+E_I.
$$

At step $n_p=100$ ($t_p=0.100$), the source arms require the target phase-match criterion

$$
M=\operatorname{Re}\!\left[\frac{Z_T}{|Z_T|}e^{-i\theta_{T,0}}\right]
\geq\cos(\pi/6),
\qquad Z_T=\langle A+iB\rangle_T.
$$

For compact profile $b$ and sign $s\in\{+1,-1\}$, solve $\beta\in[0,0.05]$ by 48 bisection steps so that

$$
\left\|\Delta(A,B)\right\|_2^2
=4\sum_{\mathbf x}\rho\sin^2\!\left(\frac{\beta b}{2}\right)
=0.45^2.
$$

Then apply once before the canonical RK2 step:

$$
\alpha=s\beta b,
\qquad
A'=\cos\alpha\,A-\sin\alpha\,B,
\qquad
B'=\sin\alpha\,A+\cos\alpha\,B,
\qquad
E_Y'=A'^2,\ E_I'=B'^2.
$$

The $10^{-3}$ floor plus $10^{-5}$ angular-margin wedge, pointwise $\rho$ conservation, and global-mass conservation remain mandatory. Every arm starts from a fresh solver with positive paired flow and runs through step 260 ($t_{\rm end}=0.260$).

## 4. Frozen arms

| arm | initial labels | pulse mask | sign |
|---|---|---|---:|
| `baseline` | standard | none | 0 |
| `source_plus`, `source_minus` | standard | $b_T$ | $+1,-1$ |
| `direct_diagonal_plus`, `direct_diagonal_minus` | standard | $b_D$ | $+1,-1$ |
| `direct_axial_plus`, `direct_axial_minus` | standard | $b_A$ | $+1,-1$ |
| `source_shuffled_plus`, `source_shuffled_minus` | diagonal/left-lower phase-label shuffle | $b_T$ | $+1,-1$ |
| `direct_diagonal_shuffled_plus`, `direct_diagonal_shuffled_minus` | diagonal/left-lower phase-label shuffle | $b_D$ | $+1,-1$ |
| `direct_axial_shuffled_plus`, `direct_axial_shuffled_minus` | diagonal/left-lower phase-label shuffle | $b_A$ | $+1,-1$ |

The direct arms calibrate each passive receiver's local susceptibility under the same compact shape and $0.45$ pulse norm. They do not count as transfer evidence.

## 5. Frozen passive-response statistic

Define the amplitude phase current and receiver projections

$$
\mathbf J_\Psi=A\nabla B-B\nabla A,
\qquad
j_D=\langle\mathbf J_\Psi\cdot(1,1,0)/\sqrt2\rangle_{\chi_D},
\qquad
j_A=\langle\mathbf J_\Psi\cdot(0,1,0)\rangle_{\chi_A}.
$$

For any plus/minus arm pair $X$, form its antisymmetric trace

$$
S_R^X(k)=\frac{j_R^{X,+}(t_p+k\,dt)-j_R^{X,-}(t_p+k\,dt)}{2},
\qquad R\in\{D,A\}.
$$

Use the frozen delayed window $k=20,\ldots,120$, or $\tau\in[0.020,0.120]$. If $J_{R,{\rm rms},0}=\sqrt{\langle|\mathbf J_\Psi|^2\rangle_{\chi_R}}$ is the relevant initial receiver scale, define

$$
G_R^X=
\sqrt{\frac{1}{101}\sum_{k=20}^{120}
\left(\frac{S_R^X(k)}{J_{R,{\rm rms},0}}\right)^2},
\qquad
F_D=\frac{G_D^{\rm source}}{G_D^{\rm direct}},
\qquad
F_A=\frac{G_A^{\rm source}}{G_A^{\rm direct}}.
$$

The phase-label-shuffled arms define $F_D^{\rm shuf}$, $F_A^{\rm shuf}$ and

$$
E=F_D-F_A,
\qquad
E_{\rm shuf}=F_D^{\rm shuf}-F_A^{\rm shuf}.
$$

Unlike carrier coherence, $G_R^X$ retains response magnitude. The $+/-$ antisymmetry cancels the common unpulsed trajectory without adding a driven receiver to the source arm.

## 6. Quality gates

The run is **INVALID** if any condition fails:

1. synthetic trace checks give $G=0$ for equal $+/-$ traces and $G=1$ for a scripted unit antisymmetric pair;
2. the no-op wrapper differs from 100 direct canonical RK2 steps;
3. compact-source overlap with either receiver core is nonzero;
4. any source arm fails the frozen target phase-match criterion at $n_p$;
5. any field is non-finite, reaches the $10^{-3}$ floor, violates the fixed wedge, or has an absent lag-window trace;
6. any active pulse lacks capacity below $\beta=0.05$, has norm error above $10^{-12}$, pointwise $\rho$ error above $10^{-12}$, or relative global-mass error above $10^{-12}$;
7. either direct calibration has $G_R^{\rm direct}\leq10^{-12}$.

## 7. Frozen decision tree

The numerical feasibility thresholds are fixed before execution relative to a same-norm direct local response:

| feature | criterion | verdict label |
|---|---|---|
| F1 passive diagonal response | $F_D\geq0.010$ | EMERGES / DOES NOT EMERGE |
| F2 diagonal-over-axial response | $E\geq0.005$ | EMERGES / DOES NOT EMERGE |
| F3 phase-arrangement dependence | $E-E_{\rm shuf}\geq0.005$ | EMERGES / DOES NOT EMERGE |

The passive finite-proxy hypothesis **SUPPORTS** only if F1, F2, and F3 emerge. It returns **HOLD** if F1 and F2 emerge while F3 does not. It **CONTRADICTS** if F1 or F2 does not emerge. Any other valid combination is **INCONCLUSIVE**.

## 8. Scope

The canonical PDE includes diffusion and FFT-mediated pressure/Poisson operations; this experiment therefore has no finite-speed causal interpretation. A positive result would measure a passive, lagged finite-proxy response under a source-localized pulse. It would not establish a physical bubble-edge transport law, a self-maintaining macro-spiral, biological circulation, neural action, or consciousness.

## References

- `field-experience/checkerboard-edge-phase-coupling-wave-4-report.md`—distributed-drive result and receiver-placement boundary.
- `field-experience/counterflow-amplitude-phase-kick-pre-registration.md`—bounded amplitude-space $SO(2)$ pulse and invariant convention.
- `field-experience/counterflow_resonant_addressing_probe.py`—five-site finite proxy and canonical solver construction.
- `foundations/bubble-lattice-fabric.md` §1.2—diagonal saddle and axial void geometry.
