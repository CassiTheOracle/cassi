# The $\varphi$ Ray and the Conversion Rate in the Canonical Two-Fluid Solver

## Status: Pre-registered—September 2026

## Abstract

The framework's single postulate is $\varphi=(1+\sqrt5)/2$, and the canonical two-fluid conversion is a rank-one relaxation whose fixed-point line is $E_Y=\varphi E_I$ and whose imbalance decays at $(1+\varphi)\gamma_{\mathrm{conv}}$. Until now the attractor and the rate have been stated from the local form and verified on homogeneous states; the axiom's own signature has not been measured while three-dimensional advection, the information force and a spatially varying gate act on the same fields. This schedule measures it. Two declared solver modes are evolved from five declared compositions at $N=32$ over $T=30$ in one resolution and one viscosity: the ungated base form, where the two predictions are the fixed ratio $\varphi$ and the rate $(1+\varphi)\lambda$, and the $q$-gated form on a static box, where the same two quantities are read against the gate-weighted rate and the ray-side rate $\lambda/3$. Three controls fix the floor and the sensitivity: a frozen-conversion pair, a step refinement, and one deliberately unprojected velocity that must move the conservation and closure statistics. The output is a finite schedule at one resolution, one viscosity and one horizon; it supplies no statement about the lattice, the cascade law, or any other place $\varphi$ appears.

## 1. Statistic, declared states and predictions

### 1.1 The conversion structure and its signatures

The canonical state is the real density pair $(E_Y,E_I)$. With

$$
\rho=E_Y+E_I,\qquad \varepsilon=E_Y-\varphi E_I,
$$

the conversion block of the canonical two-fluid equations
(`foundations/cassi-first-principles.md` §§1.3) is the rank-one relaxation

$$
\partial_t
\begin{pmatrix}E_Y\\ E_I\end{pmatrix}_{\!\mathrm{conv}}
=\kappa\begin{pmatrix}-1&\varphi\\ 1&-\varphi\end{pmatrix}
\begin{pmatrix}E_Y\\ E_I\end{pmatrix},
\qquad \kappa=\lambda(1-q)\ge0 ,
$$

with eigenvalues $0$ and $-\kappa(1+\varphi)$. The zero mode is the fixed-point line $E_Y=\varphi E_I$, the contracting mode is the imbalance $\varepsilon$, and the left null vector $(1,1)$ gives total-density conservation. In the gradient-flow form of `foundations/physical-becoming-hierarchy.md` §4.2 the same block is

$$
\frac{D\varepsilon}{Dt}=-(1+\varphi)\gamma_{\mathrm{conv}}\,\varepsilon,
\qquad
\gamma_{\mathrm{conv}}=\lambda(1-q),
$$

the exact gradient flow of $\mathcal F_{\mathrm{conv}}=\tfrac12\varepsilon^2$.

Three consequences are measurable in a solver trajectory, and they are the three predictions this schedule tests:

- **P1—fixed ray.** The composition relaxes to $E_Y=\varphi E_I$, so the volume ratio $R=\langle E_Y\rangle/\langle E_I\rangle$ converges to $\varphi$.
- **P2—rate.** The imbalance decays at $(1+\varphi)\gamma_{\mathrm{conv}}$; ungated, $\gamma_{\mathrm{conv}}=\lambda$; gated, the local rate carries the local openness.
- **P3—conservation.** The conversion is equal and opposite in the two channels, so $\langle\rho\rangle$ is constant and the two channel means change by equal and opposite amounts.

The repository's own falsifiers are already stated in this form: a measured imbalance-decay rate away from $(1+\varphi)\gamma_{\mathrm{conv}}$, or conversion that fails to conserve total density exactly, is evidence against the structure (`foundations/physical-becoming-hierarchy.md` §4.1–4.2; `open-questions-cassi-answers.md` §The $\varphi$-Attractor). Amended after the second invocation (§6), changing no rule, threshold or reading. The rate in that falsifier is the trace $\kappa(1+\varphi)$ of the declared block (`foundations/phi-input-or-selection.md:177-181`): a rank-one conversion block whose entries carry the ratio has $\operatorname{tr}M^k=(-1)^k(a+b)^k$ (`foundations/loop-rate-selection-candidates.md` §2.2), so its spectrum, characteristic polynomial and relaxation rate are functions of $a+b$ alone and a member with rate ratio $\varphi'$ would contract at $\kappa(1+\varphi')$. What this schedule can therefore falsify is the declared pair's agreement with its own law, not the value of the ratio.

Two declared modes of `two-fluid/cassi_two_fluid_3d_gpu.py` are used, and the mode is named with every reading:

- **Mode A, ungated base.** `TwoFluid3DGPU`, whose `rhs` applies the ungated $-\lambda\varepsilon$ term (`foundations/cassi-first-principles.md` §1.3). Predictions P1 and P2 with $\gamma_{\mathrm{conv}}=\lambda$.
- **Mode B, $q$-gated static box.** `ExpandingTwoFluid3DGPU` with `qi_gate=True` and the static-box convention of `computations/cassi-fluid-feasibility-prereg.md` §2.2: `hubble_mode='friedmann'`, `H0=0`, `a0=1`, `cs2=0`, `hyper_nu=0`, `qi_memory=False`, `wu_xing=False`, `phi_inv2=PHI**-2`, `gate_model='single'`. Here $\gamma_{\mathrm{conv}}=\lambda(1-q)$ is a field. Predictions P1 and P3 are unchanged; P2 is read as the gate-weighted identity below, and its ray-side value is the registered $\Gamma_0=\lambda/3$ (`parameter-inventory.md` §3.1 row $\Gamma_0$, row $\gamma_\varepsilon$).

The probe scripts nothing: it loads the solver module from disk, calls its `rhs` through `rk2_step`, calls its own `_project` for the declared initial velocity and its own `compute_q_field` for the gate reading, and computes the statistics below from the resulting fields.

### 1.2 Statistics

Volume means are grid means over the $N^3$ cells, $\langle f\rangle=N^{-3}\sum_x f(x)$.

- **S1—ratio.** $R(t)=\langle E_Y\rangle(t)/\langle E_I\rangle(t)$, with $R_0=R(0)$ and $R_T=R(T)$. Predicted: $R_T\to\varphi$.
- **S2—imbalance rate.** The least-squares slope $r_{\mathrm{fit}}$ of $\ln|\langle\varepsilon\rangle(t_k)|$ against $t_k$ over the sampled series of §1.4. Predicted ungated: $(1+\varphi)\lambda$; predicted gated: the gate-weighted value of the next item. The slope of that logarithm is negative for a decaying imbalance; $r_{\mathrm{fit}}$ denotes the decay rate, $r_{\mathrm{fit}}=-\partial_t\ln|\langle\varepsilon\rangle|$, which is the positive quantity compared with $(1+\varphi)\lambda$ in §4 and §3 (the raw log-slope is also recorded in the receipt). Clarified before the first invocation.
- **S3—conservation.** $\Sigma_{\mathrm{res}}=\max_t|\langle\rho\rangle(t)-\langle\rho\rangle(0)|/\langle\rho\rangle(0)$, with no quadrature in the statistic. Predicted: zero to roundoff, and by construction the same statement as the equal-and-opposite claim for the two channel means.
- **S4—closure.** The per-step residual of the predicted mean-imbalance law,
  $$
  C(t)=
  \frac{\left|\Delta\langle\varepsilon\rangle_{\mathrm{step}}
  +(1+\varphi)\lambda\,\overline{\langle w\varepsilon\rangle}\,\Delta t\right|}
  {\langle\rho\rangle(0)\,10^{-3}+
  \left|\Delta\langle\varepsilon\rangle_{\mathrm{step}}\right|
  +(1+\varphi)\lambda\left|\overline{\langle w\varepsilon\rangle}\right|\Delta t},
  $$
  where $\overline{\langle w\varepsilon\rangle}$ is the trapezoidal average of the openness-weighted imbalance over the step and $w\equiv1$ in mode A. Predicted: at the level of the RK2 truncation of that identity, which §2 projects at $3\times10^{-7}$.
- **S5—local rate (reported).** The least-squares slope of $\ln\sqrt{\langle\varepsilon^2\rangle}$ against $t$. Predicted ungated: $(1+\varphi)\lambda$, with the retained-band fraction $\langle\varepsilon_P^2\rangle/\langle\varepsilon^2\rangle$ reported as the candidate explanation of any shortfall, since the solver's two-thirds dealias mask acts on the conversion's spectral content.
- **S6—gate sub-question (declared).** With $w=1-q$ the local openness the conversion uses, the openness-weighted ratio $R_w=\langle wE_Y\rangle/\langle wE_I\rangle$ and, at a declared checkpoint, the equal-count quartile readings $R_q=\langle E_Y\rangle_q/\langle E_I\rangle_q$ of the cells in each quartile of $w$. The sub-question is whether the gate's own local variation moves the fixed ratio away from $\varphi$ where the gate is not constant, and the answer is the pair (the weighted ratio against $\varphi$, the quartile spread against the volume ratio). The gated form's fixed set is $\varepsilon=0$ for every $w\ge0$, so a time-asymptotic movement of the ray is not expected from the frozen form; what the gate can produce is a transient spatial differentiation of the local ratios, and $R_w$ and the quartiles are the statistics that would show it. In mode A the field used for the weighting is the constant one, so $R_w$ reduces to $R$ identically, which §3 checks.
- **Reported companions.** $\Xi(t)=\langle w\varepsilon\rangle/\langle\varepsilon\rangle$, $\langle w\rangle(t)$, the openness spread $\max_x w-\min_x w$, the raw local imbalance fraction $\sqrt{\langle\varepsilon^2\rangle}/\langle\rho\rangle$, the channel means against the accumulated conversion $\Delta\langle E_Y\rangle=-\lambda I_\varepsilon$ with $I_\varepsilon=\int_0^t\langle\varepsilon\rangle\,dt'$, the field minima, $\max|\mathbf u|$ and the solenoidal residual.

### 1.3 Declared initial states

Each state is built in Fourier space so that the declared composition is exact and the construction's own floor is never invoked:

1. A unit-variance real field is drawn from a declared seed, kept only on the integer modes $|m_i|\le4$ on every axis, and inverse transformed. The declared band is the same physical band at every declared grid, since $L$ is fixed, and it lies inside the two-thirds exact-dealiasing limit at $N=32$.
2. Each channel is $E=E_{\mathrm{mean}}+0.1\,\eta$ with its own declared seed, then rescaled by its exact declared mean, so $\langle E_Y\rangle$ and $\langle E_I\rangle$ are exact and $R_0$ is exact.
3. The velocity is three such fields at amplitude $0.05$, passed through the solver's own `_project`, so the declared state is solenoidal. A nonzero $\nabla\cdot\mathbf u$ would make the advection contribute to the channel means, and the advection's mean contribution is exactly zero per discrete mode when $k\cdot\hat{\mathbf u}=0$.

The declared means satisfy $E_{Y,\mathrm{mean}}+E_{I,\mathrm{mean}}=1+\varphi^{-1}$ and $E_{Y,\mathrm{mean}}/E_{I,\mathrm{mean}}=R_0$. Five compositions are declared:

| Tag | $R_0=\langle E_Y\rangle/\langle E_I\rangle$ | $E_{Y,\mathrm{mean}}$ | $E_{I,\mathrm{mean}}$ | $\varepsilon_0$ | Role |
|---|---|---|---|---|---|
| `ray` | $\varphi=1.6180$ | 1.000000 | 0.618034 | 0 | control: the declared state is on the ray |
| `mild_inv` | $1$ | 0.809017 | 0.809017 | $-0.500000$ | inverted composition |
| `inv` | $\varphi^{-1}=0.6180$ | 0.618034 | 1.000000 | $-1.000000$ | inverted composition |
| `deep_inv` | $\varphi^{-2}=0.3820$ | 0.447214 | 1.170820 | $-1.447214$ | inverted composition, deepest |
| `yang` | $\varphi^{2}=2.6180$ | 1.170820 | 0.447214 | $+0.447214$ | Yang-rich, opposite sign of $\varepsilon_0$ |

Declared seeds: the $E_Y$ draw 20260916, the $E_I$ draw 20260917, the velocity draw 20260918. The declared amplitude of $0.1$ is a noise amplitude, not a field floor: the realized minimum over the sixteen declared states is $0.0242$ (the deepest composition, $\varphi^{-2}$, whose mean is $0.447214$) and the smallest margin over the solver's step floor of $10^{-3}$ is a factor $24$. No clamping step is part of the construction, and §3 verifies both the realized minimum and that every constructed state equals its declared composition. Corrected after invocation 1 (§6): the original sentence here claimed the amplitude keeps every field above $0.1$, which the measured minima contradict.

### 1.4 Declared modes, resolution, step and horizon

| Quantity | Declared value |
|---|---|
| Grid | $N=32$, $L=2\pi$; one resolution check at $N=64$ |
| Conversion rate | $\lambda=0.1$ (the named C-class convention, `parameter-inventory.md` §2.1 row 1) |
| Viscosity, diffusivity, mobility | $\nu=0.001$, $D=0$, $\chi=0$ |
| Step, horizon | $\Delta t=0.002$, $T=30$ (15000 steps); one refinement at $\Delta t=0.001$ |
| Long horizon | $T_{\mathrm{long}}=240$ (120000 steps) for one gated state |
| Sampling | statistics accumulated every step; the fitted series every 25 steps (601 samples); the receipt's series every 125 steps (121 rows); checkpoints at $t/T\in\{0,1/8,1/4,1/2,3/4,1\}$ |
| Predicted rate | $(1+\varphi)\lambda=0.261803398874989$ |
| Predicted ray-side gated rate | $\lambda/3=0.033333333333333$, from $(1+\varphi)\lambda\,\varphi^{-2}/((1+\varphi^{-1})^2+\varphi^{-2})$ and `parameter-inventory.md` §3.1 |
| Tolerances | $10^{-3}$ on $R_T/\varphi$; $10^{-4}$ on $r_{\mathrm{fit}}/((1+\varphi)\lambda)$; $10^{-11}$ on $\Sigma_{\mathrm{res}}$; $10^{-6}$ on $C$; $10^{-5}$ on the refinement; $10^{-12}$ on the solenoidal residual |

$\chi=0$ is declared for mode A: the chemotactic drift is a separate candidate coupling in the base `rhs` whose local aggregation is outside this statistic, and its density fluxes are divergence-form, so disabling it changes no prediction above. Mode B's `rhs` carries no chemotactic term at all, which makes the two modes differ by the gate, the weak-force attenuation and the post-step floor, and nothing else. $T_{\mathrm{long}}=8T$ is declared because the gated approach slows toward the ray-side rate: reaching $|\varepsilon|/\rho\le6.2\times10^{-3}$ from the deepest declared state needs about $6.1$ e-folds, and the ray-side rate $\lambda/3$ supplies those e-folds in $183$ time units, so $240$ carries margin.

## 2. Run matrix, compute budget and stopping rule

Sixteen executions are declared, each one state and one mode:

| Run | Mode | $R_0$ | $\lambda$ | $N$ | $\Delta t$ | $T$ | Role |
|---|---|---|---|---|---|---|---|
| A1 | A | $\varphi$ | 0.1 | 32 | 0.002 | 30 | ray control, ungated |
| A2 | A | 1 | 0.1 | 32 | 0.002 | 30 | decisive |
| A3 | A | $\varphi^{-1}$ | 0.1 | 32 | 0.002 | 30 | decisive |
| A4 | A | $\varphi^{-2}$ | 0.1 | 32 | 0.002 | 30 | decisive |
| A5 | A | $\varphi^{2}$ | 0.1 | 32 | 0.002 | 30 | decisive |
| B1 | B | $\varphi$ | 0.1 | 32 | 0.002 | 30 | ray control, gated |
| B2 | B | 1 | 0.1 | 32 | 0.002 | 30 | decisive |
| B3 | B | $\varphi^{-1}$ | 0.1 | 32 | 0.002 | 30 | decisive |
| B4 | B | $\varphi^{-2}$ | 0.1 | 32 | 0.002 | 30 | decisive |
| B5 | B | $\varphi^{2}$ | 0.1 | 32 | 0.002 | 30 | decisive |
| C1 | A | $\varphi^{2}$ | 0 | 32 | 0.002 | 30 | frozen-conversion control |
| C2 | B | $\varphi^{-1}$ | 0 | 32 | 0.002 | 30 | frozen-conversion control |
| R1 | A | $\varphi^{-1}$ | 0.1 | 32 | 0.001 | 30 | step refinement of A3 |
| R2 | B | $\varphi^{-1}$ | 0.1 | 64 | 0.002 | 30 | resolution check of B3 |
| L1 | B | $\varphi^{-1}$ | 0.1 | 32 | 0.002 | 240 | long horizon, gated |
| M1 | A | $\varphi^{2}$ | 0.1 | 32 | 0.002 | 30 | sensitivity control: unprojected velocity |

M1 repeats A5 with the velocity draw left unprojected, so $\nabla\cdot\mathbf u\ne0$ and the advection acquires a nonzero mean. It is not a physics arm: it exists to show that the conservation and closure statistics can move, and its readings are excluded from the aggregate verdict. Every other run is decisive.

The invocation runs from the repository root:

```text
timeout 10800 python computations/verify_two_fluid_phi_ray_relaxation.py
```

**Projected wall time.** A throwaway step-cost measurement ran before this file was complete, at the declared grid and declared parameters on a state that is not one of the sixteen: 3.187 ms per RK2 step for mode A and 4.007 ms per RK2 step for mode B at $N=32$, over 43 steps of each mode, on the same ROCm device. Charging the probe's own per-step diagnostics, two inverse transforms and eight device reductions, at one quarter of the measured step cost gives 3.98 ms per mode-A step and 5.01 ms per mode-B step. The projection is then 60 s for each of the six $N=32$ mode-A runs (A1–A5, C1), 60 s for M1, 119 s for R1, 75 s for each of the six $N=32$ mode-B runs (B1–B5, C2), 720 s for the $N=64$ run R2 at nine and a half times the $N=32$ transform count, and 601 s for L1, a total of about 2310 s (0.64 h). The declared range is 1700–4000 s, the low end being the measured step costs with no diagnostic charge and the high end being the same projection with the $N=64$ run at twice the assumed transform ratio.

**Bound.** The invocation is bounded at 10800 s (3 h) by the outer `timeout`, which leaves at least 2.7× headroom over the pessimistic projection.

**Stopping rule.** One invocation. If it expires inside the bound without writing a receipt, the execution record states the bounded attempt with the last printed progress line and no verdict; a single re-run of the identical command and the identical matrix under a larger bound is then permitted, and the aggregate wall time across all invocations of this probe is capped at 21600 s. Beyond that the probe stops with no verdict. No run is added, removed or shortened after any invocation starts, the tolerances of §1.4 are not relaxed, and a timeout is not converted into a smaller matrix. A second invocation with the identical matrix is also permitted when the first invocation completes inside the bound with a receipt whose `status` is `FAIL` on a gate that the record shows to be mis-specified—a gate that does not measure what §3 says it measures, or a class the frozen decision tree applies where its mechanism is disabled. The amendment, the failed gate, the measured value and the reason are stated in §1.3 and §4 and recorded in §6; the first receipt is retained beside the second; the tolerances of §1.4, the run matrix of §2, the horizons and every class of §4 that bears on a prediction are unchanged; and the second invocation's readings are reported against the first as a reproducibility comparison. Added before the second invocation, after the first receipt exposed two such defects.

## 3. Integrity gates

The receipt reports `status=PASS` only when every gate passes; a verdict is assigned only on `PASS`. On `FAIL` the receipt records the failed gate, the measured value and the bound, and no verdict.

- `declared_run_count`—sixteen executions, one per declared row.
- `configuration_match`—each run's actual configuration equals its declared $N$, $\Delta t$, step count, $\lambda$, $\chi$, $D$, $\nu$, gate flag, `gate_model`, `phi_inv2`, `hubble_mode`, `H0`, `a0`, `cs2`, `hyper_nu`, `qi_memory` and `wu_xing`.
- `source_binding`—the solver module loaded from disk has SHA-256 `368e5539e3e1ae9205c543ed413350c8c3aa83c395809012fa44891d0aa6468c`, the declared digest. The gate fails closed.
- `finite_values`—every recorded scalar of every run is finite.
- `sampling_coverage`—every run records the sampling cadence of §1.4 at its own step count: $\text{steps}/25+1$ fitted samples, $\text{steps}/125+1$ series rows and the six declared checkpoints. At $T=30$ that is $601$ samples and $121$ rows; R1 records $1201$ and $241$; L1 records $4801$ and $961$. Amended before the first invocation: the original wording named the $T=30$ counts for every run, which the two longer runs cannot satisfy.
- `construction_positive_above_step_floor`—every declared initial field has a positive minimum whose margin over the solver's step floor of $10^{-3}$ exceeds a factor of one; the measured minima and margins are recorded. Amended after invocation 1 (§6): the original bullet here required every initial field's minimum to exceed $0.1$, a threshold derived from the incorrect sentence of §1.3, and it failed on the deepest declared composition ($0.0242$) although that composition's construction is exactly the declared one and no clamp exists anywhere in it.
- `construction_declared_state`—every declared initial state equals its declared composition: $R(0)$ against the declared $R_0$ and $\langle\rho\rangle(0)$ against $1+\varphi^{-1}$, each to $10^{-12}$ relative. Added after invocation 1 (§6) as the direct check the replaced threshold was standing in for.
- `solenoidal`—the maximum solenoidal residual over the fifteen projected runs is at most $10^{-12}$ relative.
- `step_floor_inactive`—in the six mode-B runs at $T=30$ (B1–B5, C2) the minimum field value over the run exceeds $10^{-3}$, so the expanding class's floor-and-renormalization operation never intervenes in the runs that carry the gated readings. L1's floor status is recorded as a flag rather than gated, and L1's readings are decisive only when that flag is clear.
- `refinement_agreement`—$r_{\mathrm{fit}}$ and $R_T$ of R1 agree with A3 to $10^{-5}$ relative.
- `mode_a_weight_identity`—in every mode-A run the recorded openness-weighted ratio equals the plane ratio to $10^{-14}$ relative, which the constant weighting requires.

Two controls are read rather than gated. The frozen-conversion pair must show a stationary composition, $|R_T/R_0-1|\le10^{-3}$, and its rate class is not applicable, since the prediction of P2 is a statement about the conversion channel. M1 must show both statistics outside their tolerances; if it does not, the receipt records `mutation_did_not_fire` and the sensitivity claim is not established.

## 4. Decision tree

**Ratio classes**, tested in this order, from $R_0$ and $R_T$. Runs with $\lambda=0$ are the frozen-conversion pair and their ratio class is `ratio_not_applicable`: the conversion whose fixed ray P1 states is switched off in those runs, exactly as their rate class is not applicable to P2, and a composition that is stationary away from the ray because nothing converts cannot be evidence about the ray. Their ratio readings and their `frozen` class are reported in full.

1. `ray`—$|R_T/\varphi-1|\le10^{-3}$.
2. `departing`—$|R_T-\varphi|\ge|R_0-\varphi|$.
3. `other_ratio`—$|R_T-R_0|\le0.1\,|R_0-\varphi|$: the composition is stationary away from the ray.
4. `approaching`—otherwise: the composition moved toward the ray by more than the ratio tolerance but not within it.

The ray controls start at $R_0=\varphi$, so for them only `ray` and `departing` are reachable. Amended before the second invocation: the frozen-provision is new, and it is forced by the first receipt, where the two $\lambda=0$ runs were classified `departing` at the $10^{-16}$ level of their own motion and were named by the aggregate clause below as evidence against the ray.

**Rate classes.** Runs whose $|\langle\varepsilon\rangle(0)|\le10^{-12}\langle\rho\rangle(0)$ are ray controls and their rate class is `rate_not_defined`; the frozen-conversion runs have `rate_not_applicable`. Otherwise, from $r_{\mathrm{fit}}$ against $(1+\varphi)\lambda$:

1. `rate_matches`—$|r_{\mathrm{fit}}/((1+\varphi)\lambda)-1|\le10^{-4}$.
2. `rate_above`—$r_{\mathrm{fit}}>(1+10^{-4})(1+\varphi)\lambda$.
3. `rate_below`—$r_{\mathrm{fit}}<(1-10^{-4})(1+\varphi)\lambda$, split into `rate_below_gated` when the run is mode B and $r_{\mathrm{fit}}\ge0.1(1+\varphi)\lambda$, and `rate_below_unexplained` otherwise.

**Closure and conservation classes.** `closure_holds` when $\max_tC\le10^{-6}$, else `closure_fails`. `exact` when $\Sigma_{\mathrm{res}}\le10^{-11}$; `floor_limited` when $\Sigma_{\mathrm{res}}\le\max(10^{-10},3\,\Sigma_{\mathrm{res}}^{\lambda=0})$ against the frozen-conversion control of the same mode; else `violated`. `frozen` when $|R_T/R_0-1|\le10^{-3}$, else `composition_moved`.

**Gate sub-question.** Read at the final checkpoint of L1, where the volume-mean ratio is the converged one. `gate_uniform` when the openness spread is at most $10^{-6}$ at every sampled state of the decisive gated runs, so the question has no content. Otherwise `gate_differentiates` when the volume-mean class of L1 is `ray` and some quartile ratio is outside $10^{-3}$ of $\varphi$, and `gate_does_not_differentiate` when the volume-mean class is `ray` and every quartile ratio is inside it. `gate_unresolved` when L1's ratio class is not `ray`, since a converged volume ratio is what attributes the quartile spread to the gate rather than to incomplete relaxation. The weighted ratio $R_w$ at the L1 final checkpoint is recorded against $\varphi$ at the same tolerance. These outcomes are recorded readings; they do not by themselves change the aggregate verdict, because the frozen gated form's fixed set is $\varepsilon=0$ for every $w$ and its prediction is about the rate rather than about a moved ray.

**Aggregate verdict.** With every gate passed:

- `CONTRADICTS`—any decisive run whose ratio class is applicable is `other_ratio` or `departing`; or any mode-A decisive run is `rate_above`, `rate_below_gated` or `rate_below_unexplained`; or any mode-B decisive run is `rate_above` or `rate_below_unexplained`; or any decisive run is `closure_fails`; or any decisive run's conservation is `violated`; or either frozen-conversion control is not `frozen`. Each of these is one of the repository's own falsifiers: a stationary ratio away from $\varphi$, an imbalance rate away from the predicted one without a gate to account for it, imbalance evolution that violates the predicted mean law, or conversion that fails to conserve total density.
- `SUPPORTS`—no `CONTRADICTS` condition holds, every mode-A decisive run is `ray` with `rate_matches`, every mode-B decisive run at $T=30$ is `ray` or `approaching` with `closure_holds` and a rate class of `rate_below_gated` or, for a run whose rate class is `rate_not_defined` by the paragraph above, no rate requirement, L1 is `ray` with `closure_holds`, every decisive conservation class is `exact` or `floor_limited`, and the gate sub-question is classified. Amended before the second invocation: the original wording required `rate_below_gated` from every mode-B decisive run at $T=30$, including the gated ray control B1, whose rate class the same section defines as `rate_not_defined`; that made this branch unreachable for every possible outcome. The repair makes `SUPPORTS` reachable and changes no other condition.
- `INCONCLUSIVE`—otherwise, for instance when a gated run has not reached the ray inside its horizon or when a conservation class is `floor_limited` throughout.

The verdict vocabulary is the repository's frozen set. `EMERGES` and `DOES NOT EMERGE` are not reachable here: this schedule tests a stated prediction rather than searching for whether a phenomenon appears, so its verdict domain is `SUPPORTS`, `CONTRADICTS` and `INCONCLUSIVE`.

## 5. Interpretation boundary

A solver trajectory at one resolution, one viscosity, one horizon and one step size measures whether the implemented two-fluid dynamics carries the declared rank-one structure and its $\varphi$ ray. It does not measure the lattice, the cascade law, the dark-energy or gravity mappings, or any other place $\varphi$ appears in the framework, and it supplies no continuum statement beyond the sampled states. The mean-imbalance closure of mode A is exact algebra for a solenoidal velocity and a pointwise linear conversion, so what the receipt adds to it is the measured size of the residual in an implementation that stirs the fields and forces the velocity; the local readings, the gate weighting and the quartile pattern are not closed by that algebra and are the evidence that the fields are not a homogeneous pair. A `SUPPORTS` outcome is a statement about this solver at these settings and would extend the measured scope of the conditional attractor row in `open-questions-cassi-answers.md` from homogeneous conversion-only dynamics to a stirred three-dimensional evolution; it is not a derivation of $\varphi$ and it is not evidence for any of the mappings that consume the ratio. A `CONTRADICTS` outcome would be a measured deviation of the implemented dynamics from the stated structure at these settings, and would need the same attribution work as any other solver result. The band-limited initial condition is declared rather than physical: it exists so that the construction is exact, the two-thirds dealiasing of the initial products is exact, and the declared statistics are not read through grid-scale noise. The unprojected control measures what that choice removes.

## 6. Post-execution record

Two invocations ran the identical matrix of §2 from the repository root:

| Invocation | Command | Wall time | Receipt | Status | Verdict |
|---|---|---|---|---|---|
| 1 | `timeout 10800 python computations/verify_two_fluid_phi_ray_relaxation.py` | 2259.5 s | `runs/two_fluid_phi_ray_relaxation/verification_invocation1.json` | `FAIL` | none |
| 2 | the same command and the same matrix | 1762.9 s | `runs/two_fluid_phi_ray_relaxation/verification.json` | `PASS` | `CONTRADICTS` |

The aggregate wall time is 4022 s against the 21600 s cap of §2. No run was added, removed, shortened or resized between the invocations, and no tolerance of §1.4 was relaxed.

Invocation 1 completed all sixteen runs inside its bound and failed one gate, `construction_floor_inactive`, which required every initial field's minimum to exceed $0.1$. The measured minimum is $0.0242$, on the deepest declared composition, whose declared mean is $0.447214$ and whose noise amplitude is $0.1$; the threshold came from the incorrect sentence of §1.3 corrected above, and the construction contains no clamp. Two further defects of the same family surfaced in the same receipt and are recorded in place: the two $\lambda=0$ runs were classified `departing` at the $10^{-16}$ level of their own motion and were named by the aggregate clause as evidence against the ray, and the `SUPPORTS` branch required `rate_below_gated` from the gated ray control B1, whose rate class the same decision tree defines as `rate_not_defined`—which made that branch unreachable for every possible outcome. Six changes are disclosed at the point each one changes: `sampling_coverage` in §3, made before the first invocation because its original wording named the $T=30$ sampling counts for every run; four made after the first receipt and before the second—the construction sentence of §1.3 and the gate that replaced its threshold in §3, the $\lambda=0$ ratio class in §4, the `SUPPORTS` rate requirement in §4, and the second-invocation provision of §2; and one made after the second invocation, which changes no rule, no threshold and no reading—the falsifier of §1 now names the measured rate as the trace $\kappa(1+\varphi)$ of the declared block, so that it cannot be read as a probe of the ratio's value. The last subsection of this section evaluates the pre-amendment tree against invocation 1's own numbers, clause by clause. None of the six touches a tolerance, a matrix row, a horizon or the clause the verdict routes through; the second invocation re-ran the identical matrix under the identical tolerances.

**Reproducibility.** The two receipts agree in every recorded run scalar: zero differences across the sixteen run records, their 2896 series rows, their 14416 fitted samples and their 96 checkpoints. The only differences are the two $\lambda=0$ ratio classes amended between the invocations and the metadata fields. Source binding held at invocation 2: the solver digest `368e5539e3e1ae9205c543ed413350c8c3aa83c395809012fa44891d0aa6468c` equals the declared digest, the probe revision is `P1a`, and the probe, this prereg and both referenced foundations documents are hashed in the receipt. The receipt binds the protocol hash as it stood when the matrix started (`cac1483252fddd5d4e9d7b4b1a2c653d10ea4464f64549a344092cb3b6d10dcb`); the only edits to the protocol since that binding are this §6, which records the execution, and the scope clause added to the falsifier of §1 after the second invocation, which changes no rule; the probe hash recorded in the receipt (`b13ac154814d9186f6215b861fd46290da47b31110cc48ee2645abd7aedb2242`) still equals the committed probe. The invocation-1 receipt records its own protocol and probe revisions (`60326900ecbdf3d1430bde95b535191ac07d1255b0c9f61b61624b2eee524ad6` and `782efe34c5ae98371709f6176e7e37e71f7182136d15f576bfd2f5660ac5c627`), both superseded by the pre-invocation-2 amendments.

**Gates.** Eleven of eleven pass in invocation 2. The construction gates read $R(0)$ against the declared $R_0$ and $\langle\rho\rangle(0)$ against $1+\varphi^{-1}$ to $2.2\times10^{-16}$ relative in every run, the worst initial minimum is a factor $24.2$ over the step floor, the solenoidal residual over the fifteen projected runs is at most $1.5\times10^{-16}$, the step floor is inactive in the six $T=30$ gated runs and clear for L1, the refinement of A3 agrees to $3.4\times10^{-8}$ in rate and $1.0\times10^{-10}$ in ratio, and the mode-A weight identity holds exactly.

**Per-state readings.** $R_0$, $R_T$ and the rate are receipt fields of invocation 2; $\Sigma_{\mathrm{res}}$ is S3, $C$ is S4 and the last column is the §4 class quadruple ratio/rate/closure/conservation.

| Run | Mode | $R_0$ | $R_T$ | $R_T/\varphi-1$ | $r_{\mathrm{fit}}$ | $\Sigma_{\mathrm{res}}$ | $C$ | Class |
|---|---|---|---|---|---|---|---|---|
| A1 | A | 1.618034 | 1.618034 | $+2.2\times10^{-16}$ | — | $1.4\times10^{-16}$ | $9.9\times10^{-14}$ | ray / not defined / holds / exact |
| A2 | A | 1.000000 | 1.617720 | $-1.94\times10^{-4}$ | 0.26180339 | $2.7\times10^{-16}$ | $8.4\times10^{-9}$ | ray / matches / holds / exact |
| A3 | A | 0.618034 | 1.617406 | $-3.88\times10^{-4}$ | 0.26180339 | $2.7\times10^{-16}$ | $1.4\times10^{-8}$ | ray / matches / holds / exact |
| A4 | A | 0.381966 | 1.617125 | $-5.62\times10^{-4}$ | 0.26180339 | $1.1\times10^{-15}$ | $1.7\times10^{-8}$ | ray / matches / holds / exact |
| A5 | A | 2.618034 | 1.618315 | $+1.74\times10^{-4}$ | 0.26180339 | $9.3\times10^{-15}$ | $7.7\times10^{-9}$ | ray / matches / holds / exact |
| B1 | B | 1.618034 | 1.614039 | $-2.47\times10^{-3}$ | — | $8.9\times10^{-14}$ | $2.9\times10^{-11}$ | departing / not defined / holds / exact |
| B2 | B | 1.000000 | 1.400640 | $-1.34\times10^{-1}$ | 0.04009123 | $1.3\times10^{-13}$ | $1.7\times10^{-10}$ | approaching / below gated / holds / exact |
| B3 | B | 0.618034 | 1.305781 | $-1.93\times10^{-1}$ | 0.04817116 | $1.4\times10^{-13}$ | $3.1\times10^{-9}$ | approaching / below gated / holds / exact |
| B4 | B | 0.381966 | 1.266608 | $-2.17\times10^{-1}$ | 0.05428311 | $1.5\times10^{-13}$ | $9.0\times10^{-9}$ | approaching / below gated / holds / exact |
| B5 | B | 2.618034 | 1.849493 | $+1.43\times10^{-1}$ | 0.04003847 | $3.1\times10^{-14}$ | $5.8\times10^{-11}$ | approaching / below gated / holds / exact |
| C1 | A | 2.618034 | 2.618034 | frozen | — | $2.7\times10^{-16}$ | $3.4\times10^{-14}$ | not applicable / not applicable / holds / exact |
| C2 | B | 0.618034 | 0.618034 | frozen | — | $5.9\times10^{-14}$ | $5.5\times10^{-13}$ | not applicable / not applicable / holds / exact |
| R1 | A | 0.618034 | 1.617406 | $-3.88\times10^{-4}$ | 0.26180340 | $2.7\times10^{-16}$ | $2.1\times10^{-9}$ | ray / matches / holds / exact |
| R2 | B | 0.618034 | 1.306061 | $-1.93\times10^{-1}$ | 0.04819081 | $1.6\times10^{-13}$ | $3.1\times10^{-9}$ | approaching / below gated / holds / exact |
| L1 | B | 0.618034 | 1.617527 | $-3.13\times10^{-4}$ | 0.03179604 | $6.5\times10^{-13}$ | $3.1\times10^{-9}$ | ray / below gated / holds / exact |
| M1 | A | 2.618034 | 1.618319 | $+1.76\times10^{-4}$ | 0.26102030 | $1.2\times10^{-2}$ | $7.6\times10^{-4}$ | ray / below unexplained / fails / violated |

Predicted rate $(1+\varphi)\lambda=0.2618033988749895$. The four decisive mode-A rates are equal to nine digits at $0.261803387$—a factor $1-4.6\times10^{-8}$ below the prediction, the size of the RK2 bias that §2 projects. The gated rates fall at $0.153$, $0.184$, $0.207$ and $0.153$ of the prediction, inside the band the gate's own openness makes at the declared states. Every decisive conservation class is `exact`, the widest residual being L1's $6.5\times10^{-13}$ against the range in which $\lambda=0$ freezes the channels.

**Verdict.**

```text
CONTRADICTS
```

The aggregate fires exactly one clause: the ratio clause, through the gated ray control B1, whose volume ratio ends $2.47\times10^{-3}$ below $\varphi$ against the $10^{-3}$ tolerance of §4. Every other clause is clear—no decisive non-control run is `other_ratio` or `departing`, no mode-A decisive run's rate class is anything but `rate_matches`, no mode-B decisive run is `rate_above` or `rate_below_unexplained`, every decisive closure holds and every decisive conservation class is `exact`, and both frozen-conversion controls are `frozen`. Of the `SUPPORTS` conditions, `mode_a_ray_and_rate`, `mode_a_ray_control`, `gated_long_horizon_ray`, `conservation` and `subquestion_classified` hold in invocation 2; `gated_approach` does not, and it does not because B1 is the run in question.

B1 is readable, and the reading is the sub-question's content. Its initial state is exactly on the ray ($R(0)/\varphi-1=+2.2\times10^{-16}$) and its displacement grows and saturates: $-9.0\times10^{-4}$ at $t=3.75$, $-1.51\times10^{-3}$ at $7.5$, $-2.20\times10^{-3}$ at $15$, $-2.45\times10^{-3}$ at $22.5$, $-2.47\times10^{-3}$ at $30$. Over the same interval the local imbalance amplitude decays from $1.14\times10^{-1}$ to $3.83\times10^{-2}$ of $\langle\rho\rangle_0$, so the displacement is largest while the local excursions are largest. The ungated ray control A1, the same initial state under the same velocity, holds $R_T/\varphi-1=+2.2\times10^{-16}$ exactly, and its recorded log-slope of the local imbalance equals the prediction to $2\times10^{-8}$ relative. The gate's pointwise fixed set is $\varepsilon=0$ for every $w\ge0$; what moves the volume mean is the cross-correlation the finite state makes possible, and the receipt carries its sign and size: the openness-weighted mean imbalance $\langle w\varepsilon\rangle$ is opposite in sign to the volume mean $\langle\varepsilon\rangle$ at late times, so $\Xi=\langle w\varepsilon\rangle/\langle\varepsilon\rangle$ rises from $-0.82$ at $t=3.75$ through zero to $+0.0124$ at $t=30$. The same quantity fixes the long-horizon behaviour.

**Gate sub-question.** Class `gate_does_not_differentiate`; the widest openness range over the gated checkpoints is $0.5054$, at L1's initial state, so the question has content. There the openness spans $0.0697$ to $0.2719$ about a mean of $0.1296$ against the ray-side value $\varphi^{-2}/3=0.1273$, the volume ratio is within $3.13\times10^{-4}$ of $\varphi$, the weighted ratio is within $2.76\times10^{-4}$, and the equal-count quartile ratios of $w$ read $1.617049$, $1.617451$, $1.617700$, $1.618028$—a monotone ladder whose worst deviation from $\varphi$ is $6.09\times10^{-4}$, inside the $10^{-3}$ tolerance. The gate's local variation therefore orders the local fixed ratios without moving any quartile outside tolerance at that state.

**Long horizon.** L1 reaches the ray within its declared horizon: $R_T/\varphi-1=-3.13\times10^{-4}$ at $T=240$, class `ray`, with $\langle\varepsilon\rangle/\langle\rho\rangle_0=-3.13\times10^{-4}$ and a local imbalance amplitude of $2.61\times10^{-4}$, the two decaying together at the terminal rate. The terminal segment rates are $0.02976$ over $t\in[180,240]$ and $0.02960$ over $[210,240]$, and the fitted rate over the whole horizon is $0.031796$. The registered ray-side value $\Gamma_0=\lambda/3=0.033333$ is the pointwise rate at the reference density; the volume mean is weighted by the gate's own distribution, and the receipt's measured weighting closes the difference: $\Xi=0.11254$ at that checkpoint gives $(1+\varphi)\lambda\,\Xi=0.029463$, within $0.5\%$ of the measured terminal segment rate. The registered value is therefore not the volume-mean rate of a gated state at this resolution, and the measured relation is $(1+\varphi)\lambda\,\Xi$.

**Mutation control.** M1 fired on both statistics it exists to move: conservation is `violated` at $\Sigma_{\mathrm{res}}=1.24\times10^{-2}$ and closure fails at $C=7.6\times10^{-4}$, and its unprojected velocity leaves a solenoidal residual of $1.55$ against $1.5\times10^{-16}$ for the fifteen projected runs. Its fields reach $-1.014$, below zero, and its readings are excluded from the verdict as §2 declares.

**Reconciliation of the departure.** The volume deviation is an identity rather than a second measurement: with $\delta=E_Y/(\varphi E_I)-1$ per cell, $D=R_T/\varphi-1=\langle\delta\rangle_{E_I}$ exactly. The receipt's second weighted reading is a different weighting of the same $\delta$, since $R_w/\varphi-1=\langle\delta\rangle_{wE_I}$ with $w=1-q$ the gate's own openness, so $D_w-D=\operatorname{cov}_{E_I}(w,\delta)/\langle w\rangle_{E_I}$. The discriminator was fixed before the band readings below were extracted: a departure frozen into the cells whose gate is nearly closed shows the lowest-openness band dominating it and decaying slower than its own openness permits; a departure of the relaxation itself shows the bands decaying in common proportion.

What each checkpoint serialises is the volume ratio, the openness-weighted ratio, the openness envelope, four equal-count openness quartile ratios, the imbalance r.m.s. and the closure and conservation scalars. The per-cell fields are not stored, so the per-cell distribution of $\delta$ and the $E_I$ mass of each band are not recoverable, and no state is reconstructed or re-run here. The quartile readings are available and each carries the $E_I$ weight inside its band by construction, because a band reading is $\sum_{\text{band}}E_Y/\sum_{\text{band}}E_I$.

$D_w-D$ at the final checkpoint of every gated run:

| Run | $D=R_T/\varphi-1$ | $D_w=R_w/\varphi-1$ | $D_w-D$ |
|---|---:|---:|---:|
| B1 | $-2.47\times10^{-3}$ | $-2.38\times10^{-4}$ | $+2.23\times10^{-3}$ |
| B2 | $-1.34\times10^{-1}$ | $-1.33\times10^{-1}$ | $+1.54\times10^{-3}$ |
| B3 | $-1.93\times10^{-1}$ | $-1.91\times10^{-1}$ | $+1.69\times10^{-3}$ |
| B4 | $-2.17\times10^{-1}$ | $-2.16\times10^{-1}$ | $+1.66\times10^{-3}$ |
| B5 | $+1.43\times10^{-1}$ | $+1.44\times10^{-1}$ | $+1.18\times10^{-3}$ |
| R2 | $-1.93\times10^{-1}$ | $-1.91\times10^{-1}$ | $+1.52\times10^{-3}$ |
| L1 | $-3.13\times10^{-4}$ | $-2.76\times10^{-4}$ | $+3.73\times10^{-5}$ |
| C2 | $-6.18\times10^{-1}$ | $-6.31\times10^{-1}$ | $-1.25\times10^{-2}$ |

In the ungated mode the weighting is trivial: $\Xi=1.000000$ and $R_w=R_T$ to roundoff at every checkpoint of A1–A5 and R1, so the openness-composition covariance exists only where the gate does. In the frozen control C2 the difference is $-1.25\times10^{-2}$ at every checkpoint, an imprint of the construction rather than of any evolution. Every decisive gated state has $D_w-D>0$: the cells the gate weights up sit systematically higher in composition than the volume mean, so the departure is carried by the cells the gate weights down. The identity's necessary consistency holds where it could have failed—the volume reading lies inside the four band readings at every gated final checkpoint (B1 between $-1.71\times10^{-2}$ and $+1.81\times10^{-2}$, L1 between $-6.09\times10^{-4}$ and $-3.41\times10^{-6}$, C2 between $-5.25\times10^{-1}$ and $-7.02\times10^{-1}$)—and with equal band masses the four band readings average to $-1.31\times10^{-3}$ at B1 and $-2.95\times10^{-4}$ at L1 against the volume readings $-2.47\times10^{-3}$ and $-3.13\times10^{-4}$, so consistency requires the $E_I$ mass of the lowest-openness band to exceed the equal-count share by $0.033$ at B1 and $0.030$ at L1.

B1 and L1 at their checkpoints:

| Run | $t$ | $D$ | r.m.s. imbalance | band 1 | band 2 | band 3 | band 4 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B1 | 0 | $+2.22\times10^{-16}$ | $1.14\times10^{-1}$ | $-1.96\times10^{-2}$ | $-2.35\times10^{-2}$ | $-1.29\times10^{-2}$ | $+6.80\times10^{-2}$ |
| B1 | 7.5 | $-1.51\times10^{-3}$ | $8.52\times10^{-2}$ | $-2.30\times10^{-2}$ | $-2.05\times10^{-2}$ | $-3.70\times10^{-3}$ | $+5.18\times10^{-2}$ |
| B1 | 30 | $-2.47\times10^{-3}$ | $3.83\times10^{-2}$ | $-1.71\times10^{-2}$ | $-7.42\times10^{-3}$ | $+1.21\times10^{-3}$ | $+1.81\times10^{-2}$ |
| L1 | 0 | $-6.18\times10^{-1}$ | $6.29\times10^{-1}$ | $-5.25\times10^{-1}$ | $-5.96\times10^{-1}$ | $-6.41\times10^{-1}$ | $-7.02\times10^{-1}$ |
| L1 | 120 | $-1.16\times10^{-2}$ | $8.26\times10^{-3}$ | $-1.79\times10^{-2}$ | $-1.29\times10^{-2}$ | $-9.46\times10^{-3}$ | $-4.34\times10^{-3}$ |
| L1 | 180 | $-1.87\times10^{-3}$ | $1.44\times10^{-3}$ | $-3.31\times10^{-3}$ | $-2.14\times10^{-3}$ | $-1.36\times10^{-3}$ | $-2.83\times10^{-4}$ |
| L1 | 240 | $-3.13\times10^{-4}$ | $2.61\times10^{-4}$ | $-6.09\times10^{-4}$ | $-3.60\times10^{-4}$ | $-2.07\times10^{-4}$ | $-3.41\times10^{-6}$ |

At the frozen horizon the departure is a small residual of two large opposing band readings, $-1.71\times10^{-2}$ in the lowest-openness band and $+1.81\times10^{-2}$ in the highest, so the volume mean sits $2.5\times10^{-3}$ off the ray while the local composition deviations are an order of magnitude larger. Its time course is stored twice, in the ladder above and in the 121-point and 961-point series. B1's series puts the peak of $|D|$ at $t=26.75$ s with $D=-2.4823\times10^{-3}$ and reads $D(30)=-2.4692\times10^{-3}$, so the frozen horizon samples the plateau 0.5% past the peak at $2.48\times$ the ratio tolerance. Over that window the local imprint decays and the volume mean does not: the imbalance r.m.s. falls from $1.144\times10^{-1}$ to $3.830\times10^{-2}$ of $\langle\rho\rangle_0$, a rate of $0.0365$ per second, while the lowest-openness band retains $0.85$ of its deviation from $t=3.75$ to $t=30$, a rate of $0.0063$, where the slowest local rate the solver's own closure offers, $(1+\varphi)\lambda\min w=0.0190$, would retain $0.61$. Within the frozen window the lowest-openness quarter therefore lags by more than its own openness permits. The bands are recomputed at every checkpoint, so this is a reading of the field's low-openness quartile and not of a fixed set of cells.

L1 is the only longer gated horizon stored, and there the branch is the transient one. Over $t\in[220,240]$ the volume deviation decays at $0.02955$ per second against the gate-weighted value $(1+\varphi)\lambda\Xi=0.02946$ from the same checkpoint's $\Xi=0.11254$, the imbalance r.m.s. decays at $0.02853$ over $t\in[180,240]$, and the four band deviations decay at $0.0282$, $0.0297$, $0.0314$ and—in a band whose deviation has fallen to $3.4\times10^{-6}$—$0.0736$, in common proportion rather than by a persisting frozen share. The volume ratio is inside the ratio tolerance from $t=201$ s onward.

Read against the declared discriminator, the departure is a transient of the relaxation with a rate-ordered lag: it is generated from a zero-mean initial state by the gate's own spatial rate variation, it is carried by the low-openness cells, it is not a uniform shift (its sign follows the initial composition in all four off-ray states, whose residual deviations keep the sign of $R_0-\varphi$), it saturates near $t\approx27$ s at this resolution, and at the only longer horizon stored it decays at the measured gate-weighted rate. The frozen window is the unfavourable one for a run started on the ray, since it samples the departure at its plateau. Decaying from the measured peak at the measured rate it would reach the $10^{-3}$ tolerance about $31$ s after the peak, near $t\approx58$ s; that arithmetic extrapolates stored rates and is not a measurement, because no gated run started on the ray has a horizon longer than $T=30$. The verdict of §4 and the paragraph above are unchanged by this reading: the protocol's horizon for the ray controls is $T=30$ and the class definition for a control that leaves the ray is unconditional. What remains unmeasured is the per-cell distribution of $\delta$ and the $E_I$ mass of each band, which no checkpoint serialises; the residence of individual cells in the low-openness quartile; the resolution and amplitude dependence of the departure; and any horizon on which B1 itself is observed to decay.

**What the measurement does not cover.** One solver mode of each declared form, one resolution with one refinement and one resolution check, one viscosity and diffusivity, and horizons of $30$ and $240$. It measures the implemented two-fluid conversion on a $32^3$ and $64^3$ grid with a two-thirds dealiased spectral velocity; the retained-band fraction of the imbalance is $1.0000$ at every checkpoint of every run, so the dealiasing mask truncates no part of the imbalance's spectral content in these runs and S5's candidate explanation for a rate shortfall has no work to do here. It says nothing about the lattice, the cascade law, the dark-energy or gravity mappings, or any other place $\varphi$ appears. The mean-imbalance closure of mode A is exact algebra for a solenoidal velocity and a pointwise linear conversion, so the receipt's contribution there is the size of the residual ($1.4\times10^{-8}$ at A3) in an implementation that stirs the fields, and the gated closure ($3.1\times10^{-9}$ at B3) is the corresponding measurement of the gate-weighted law. The gated volume-mean displacement that fires the verdict is measured at one resolution, one amplitude and two horizons; whether it shrinks with resolution or with the fluctuation amplitude is not settled here, and it is the natural next measurement.

**Amendment invariance.** The verdict routes through one clause, and both receipts store enough to evaluate the pre-amendment tree against the invocation-1 numbers, because those numbers are the invocation-2 numbers: the two files agree in every recorded run scalar, and their decision parameters agree in all eleven keys that bear on a prediction—`ratio_tolerance` $10^{-3}$, `rate_tolerance` $10^{-4}$, `sum_tolerance` $10^{-11}$, `closure_tolerance` $10^{-6}$, `refinement_tolerance` $10^{-5}$, `solenoidal_tolerance` $10^{-12}$, `step_floor` $10^{-3}$, `gate_spread_tolerance` $10^{-6}$, `rate_floor` $0.026180$, `control_ratio_tolerance` $10^{-3}$, `ray_eps_floor` $10^{-12}$—the only difference being the construction key. The pre-amendment wordings the table uses are quoted in the in-place disclosures of §1.3, §3 and §4; the tree outcomes are the receipts' own stored classes and aggregates.

| Clause | Invocation-1 rule, against invocation-1 numbers | Invocation-2 rule, against invocation-2 numbers | Identical? |
|---|---|---|---|
| Firing clause (`CONTRADICTS` on the ratio class) | B1 stored class `departing`, $R_T/\varphi-1=-2.4692\times10^{-3}$ against the $10^{-3}$ tolerance; stored aggregate `contradictory_conditions.ratio = ["B1","C1","C2"]` | B1 stored class `departing`, the same $-2.4692\times10^{-3}$; stored aggregate `["B1"]` | Yes for B1: same reading, same class, same clause text, and B1 is not a control |
| Frozen controls C1, C2 | both `departing`, at their own motion $\lvert R_T/R_0-1\rvert=0$ and $1.8\times10^{-14}$, and named by a clause that read "any decisive run is `other_ratio` or `departing`" | both `ratio_not_applicable`, exempted by "any decisive run whose ratio class is applicable" | Names removed, none added. The old classification also fired the verdict, and it fired it on B1 as well, so the reclassification cannot have manufactured the result |
| Construction gate | `construction_floor_inactive`: "every declared initial field has minimum above $0.1$, so the construction's clamp is never invoked"; measured minimum $0.0242$ (A4, B4); check FAIL, `status` FAIL, no verdict issued | `construction_positive_above_step_floor` (positive minimum with margin over the solver's $10^{-3}$ step floor above a factor of one) and `construction_declared_state` ($R(0)$ against the declared $R_0$, $\langle\rho\rangle(0)$ against $1+\varphi^{-1}$, each to $10^{-12}$): both PASS, `status` PASS | No: the one status an amendment changed, FAIL to PASS. Weaker on magnitude by two decades and stronger on what it measures; the compensation is stated below |
| `SUPPORTS` branch `gated_approach` | "every mode-B decisive run at $T=30$ is `ray` or `approaching` with `closure_holds` and `rate_below_gated`": required `rate_below_gated` from B1, whose rate class §4 defines as `rate_not_defined` ($\lvert\langle\varepsilon\rangle(0)\rvert\le10^{-12}\langle\rho\rangle(0)$ holds by construction), and from C2, `rate_not_applicable` at $\lambda=0$; unsatisfiable for every possible outcome; stored `supports_conditions.gated_approach = false` | the same requirement with no rate requirement for a run whose rate class §4 defines as undefined; stored `gated_approach = false` on B1's departure | Yes: false under both. The amendment could only have enabled the branch and did not, and enabling it could not have changed the verdict either, since the branch is gated on no `CONTRADICTS` condition holding and the firing clause fires under both wordings |
| Rate, closure, conservation and frozen-control clauses | no decisive run `rate_above`, `rate_below_unexplained`, `closure_fails` or `violated`; `frozen_controls = {C1: frozen, C2: frozen}`; `supports_conditions` all as recorded | the same classes, clauses and values | Yes: no amendment touched these texts or their inputs |
| Run matrix, horizons, seeds, tolerances | the §2 `scope` block: identical grids, $N$, $L$, $\lambda$, $\nu$, $dt$, $T=30$, $T_{\text{long}}=240$, steps, band $4$, amplitude $0.1$, velocity amplitude $0.05$, the three seeds, the five declared states and the sixteen-run list | equal field for field, with the eleven shared decision parameters above | Yes for every quantity a prediction depends on; the sole decision-parameter difference is the construction key |
| Aggregate and verdict | checks FAIL, so no verdict is issued; the ratio clause evaluated on these numbers yields `CONTRADICTS` with $\{B1,C1,C2\}$ | checks PASS, `CONTRADICTS` with $\{B1\}$ | Same verdict, B1 the common member and the only member that matters |

The second invocation rests on a provision added after the first receipt, and the record states that plainly rather than claiming a permission declared in advance. The §2 stopping rule now reads: "A second invocation with the identical matrix is also permitted when the first invocation completes inside the bound with a receipt whose `status` is `FAIL` on a gate that the record shows to be mis-specified—a gate that does not measure what §3 says it measures, or a class the frozen decision tree applies where its mechanism is disabled… Added before the second invocation, after the first receipt exposed two such defects." Its own disclosure dates it after invocation 1; before that receipt the rule permitted a re-run only after a timeout that wrote no receipt, under the same $21600$ s aggregate cap. Nothing in the verdict depends on that provenance: the second invocation changed no run, no seed, no horizon and no tolerance, and the firing clause reads B1 identically in both receipts.

No amendment touched a tolerance, a horizon, a matrix row or the firing clause. The one status an amendment changed is the construction gate, from FAIL to PASS, and it changed as a correction rather than a relaxation. The replaced threshold asserted that every declared initial field's minimum exceeds $0.1$, a number taken from the §1.3 sentence about a clamp that the solver does not contain; it failed on the deepest declared composition ($0.0242$), whose construction is exactly its declared state. The corrected pair asserts the properties that matter for the prediction—positivity with margin over the solver's own $10^{-3}$ step floor, and identity of the declared initial state to $10^{-12}$—and the same recorded numbers that failed the old threshold satisfy them with a margin of a factor $24.2$ over the step floor and a declared-state error of $2.2\times10^{-16}$. The corrected gate is weaker on magnitude, by two decades, and that weakness is bought back by the check the threshold was standing in for: the composition the run actually starts from is now verified directly, to a tolerance six orders tighter than the magnitude it gave up.

## References

- `foundations/cassi-first-principles.md`—canonical real-density state, ungated and gated conversion, rank-one matrix and its eigenvalues.
- `foundations/physical-becoming-hierarchy.md`—gradient-flow form of the conversion, Lyapunov derivative and predicted rate $(1+\varphi)\gamma_{\mathrm{conv}}$.
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical solver: `TwoFluid3DGPU` (ungated base) and `ExpandingTwoFluid3DGPU` ($q$-gated form and static-box parameters).
- `computations/cassi-fluid-feasibility-prereg.md`—static-box convention for the gated class, and the frozen conservation and conversion controls.
- `parameter-inventory.md`—$\lambda=0.1$ convention row, the $\Gamma_0=\lambda/3$ reference-state rate, and the composition-rate row.
- `open-questions-cassi-answers.md`—the $\varphi$-attractor row whose measured scope this schedule addresses.
- `field-experience/probe-outcome-ledger.md`—ledger record of this probe.
