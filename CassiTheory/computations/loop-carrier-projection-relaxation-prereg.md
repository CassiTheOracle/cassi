# Loop-Carrier Projection Relaxation

## Status: Pre-registered—September 16, 2026; no invocation has been made

## Abstract

`foundations/loop-to-bubble-projection-theorem.md` states that one closed loop carrying four nonnegative populations—Yang and Yin in each of the two loop orientations—projects through its complete loop average onto the canonical two-density PDE, with the projected equations an exact consequence of the four-population law when the conversion gate is common around the loop and the exterior transport is shared (§3.2, Theorem 1). The spent protocol `computations/loop-carrier-projection-dynamics-prereg.md` measured that statement on a declared discrete realization and returned `status=FAIL` with both verdicts null (`runs/loop_carrier_projection_dynamics/verification.json`, SHA-256 `7ff42dfd8f96ff98126c58bb2e4076f2f7d814b3cea6ab11295cd7bc48978b5b`, one invocation, 185.23 s). Its eleven gates passed and thirteen of its fifteen arms held the projection residual at or below `2.62e-15` over their whole traces, but two of its four firing controls could not witness the disagreement they exist to witness: the `covariance` control read a relative (LB14) residual of `4.308692590324274e-09` against a `1e-12` bound and a terminal deviation of `3.376811012630109e-08` against a `1e-4` requirement, and `direction_split` a terminal deviation of `1.0496654051001292e-14` against the same requirement, while the same two arms reached `2.0326187974944866e-03` and `5.998107248579932e-04` during their runs—above the requirement by factors of two thousand and six hundred, against terminal readings below it by factors of thirty thousand and one trillion. Both arms failed structurally: each reads a transient deviation at the converged horizon of an attracting relaxation, by which the perturbation has returned to the canonical trajectory, and the covariance control's relative residual divides by a quantity that decays with the very content the control injects.

This protocol is the successor. It is a fresh pre-registration: no statistic, threshold, arm, seed, feature or verdict definition is inherited by reference from the spent protocol, every one of them is re-declared below, and the spent receipt is cited as the motivating evidence for the readings just quoted and for nothing else. The protocol carries its own name because its subject is the **relaxation** the spent run exposed rather than the dynamics it set out to measure: the witness for a disagreement is now the maximum deviation a run reaches, and the new frozen statistic is the rate at which that deviation decays against the arm's own declared conversion channels. It is distinguished from `computations/two-fluid-phi-ray-relaxation-prereg.md` by its object: that protocol measures the canonical two-fluid solver, this one the four-population loop carrier's projected flow on the frozen discrete operators.

## 1. The carrier model

### 1.1 Definitions taken from the repository

Each item is the theorem's own definition or the frozen module's own source; the probe implements them as written and computes nothing new at this level.

1. **The law and its projection.** `foundations/loop-to-bubble-projection-theorem.md` (LB1)–(LB14): the four-population carrier law (LB6), the complete loop average (LB1), and the projected reduction (LB7) whose exactness is §3.2 Theorem 1. The rank-one conversion and its mobility are (LB12)–(LB14); the current whose loop mean (LB45) conserves is (LB44) and the projection's invisibility to it is (LB46).
2. **The frozen spectrum and gap.** (LB36) is the closed-loop spectrum of the internal generator; (LB38) gives the mode rates $g_m=d\,m^2+r-\operatorname{Re}\sqrt{r^2-m^2\Omega^2}$; (LB39) gives the internal gap $\min[\kappa(1+\varphi),\,2r,\,g_1]$. With the module's constants these read $g_1=0.27276406320767016$, $g_2=0.7799307958477508$ and $2r=1.2$.
3. **The frozen module.** `computations/verify_loop_to_bubble_projection.py`, accepted only at SHA-256 `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1`. Its constants (lines 12–25) supply $u=0.31$, $D_x=0.17$, $R=1.7$, $v=0.8$, $D_\ell=0.13$, $r=0.6$, $\lambda=0.04$, $\Omega=v/R$, $d=D_\ell/R^2$, $N_x=7$, $N_\chi=12$ and the tolerance $10^{-11}$; its periodic difference operators are `derivative` and `laplacian` (lines 28–39) and its closed spectrum is `closed_spectrum` (lines 97–107).
4. **The canonical companions.** The canonical arm of §2 is the independently evolved solution of (LB7) on the same grid, with the same integrator, the same step count and the same gate evaluation, and the conversion term of `computations/loop-to-bubble-projection-pre-registration.md` at its declared parameters.

### 1.2 Declared realization

The theorem is a continuum statement; the following pieces are this protocol's own choices and the receipt records them as declared inputs.

1. **Discrete operators.** Periodic centered differences in $x$ and in $\chi$, spacings $2\pi/N_x$ and $2\pi/N_\chi$, read from the frozen module by import. The primary loop grid is $N_\chi=24$; the truncation arm runs at the module's own $N_\chi=12$; the exterior grid is the module's $N_x=7$.
2. **Time stepping.** Classical RK4 in float64, the canonical arm advanced by the same integrator at the same step size and count. Step size and horizon follow (LR-S1) and (LR-S2) of §2.4.
3. **Gate placement.** $\kappa$ is evaluated from the projected densities at the start of each stage, identically in both arms.
4. **Exterior modulation and profiles.** $E_a(x)=B_a(1+0.20\cos x)$ on the periodic $N_x=7$ grid, so the advection and diffusion terms act at their declared rates. Three profiles are carried:

| profile | $B_Y$ | $B_I$ | composition | role |
|---|---|---|---|---|
| `on_ray` | $1.10$ | $1.10/\varphi$ | $\varepsilon=0$ exactly | on the $\varphi$-ray; the mode and relaxation arms |
| `open_gate` | $0.35$ | $0.35/\varphi$ | low $\rho$, $q$ small | conversion runs hard |
| `closed_gate` | $5.00$ | $5.00/\varphi$ | high $\rho$, $q\to1$ | conversion nearly closed |

and the fourth profile `off_ray` ($B_Y=0.90$, $B_I=1.40$, $\varepsilon\ne0$) is carried by one closure arm and its refinement. The rays are formed by division, so $\varepsilon$ sits at float64 roundoff, and on the `on_ray` profile the conversion term vanishes for every gate state, so $\kappa$ is constant in time and (LB36)–(LB38) apply exactly.
5. **The effective gate field.** For the two covariance arms of §3.2 the conversion coefficient is
$$
\kappa^{\rm eff}(x,\chi,t)=s\,\kappa(x,t)\,\bigl[1+0.5\cos\chi\bigr],
\tag{LR-A0}
$$
with the declared uniform scale $s\in\{1,\tfrac12\}$; for every other arm $\kappa^{\rm eff}=\kappa$. The scale $s$ is this protocol's own control knob: it multiplies the arm's conversion field uniformly, so every $\kappa$-dependent channel rate of that arm scales by exactly $s$, while the $2r$ and $g_1$ bounds of (LB39) do not move. The $[1+0.5\cos\chi]$ factor is the loop-varying gate the spent protocol's covariance control used; it is re-declared here because this protocol's control construction needs it, not because the spent protocol declares it.
6. **Seeds.** Four declared seeds, each written once and carried by every arm that names it.
   - (LR-A1) *Mode content.* $f_{a,s}(x,\chi)=f^{\rm uniform}_{a,s}(x)[1+\alpha\cos(m\chi)]$ with $\alpha=0.25$ and $m=1$ or $m=2$, so the projection is unchanged at roundoff and the mode energy is a declared fraction of the arm.
   - (LR-A2) *Composition asymmetry.* $f_{Y,s}=\tfrac{E_Y}{2}[1+\alpha\cos(m\chi)]$ and $f_{I,s}=\tfrac{E_I}{2}[1-\alpha\cos(m\chi)]$, so each carrier's loop mean is exactly one, the projection still reproduces the declared densities, and the composition combination $Z(\chi)=\sum_s[f_{Y,s}-\varphi f_{I,s}]=\varepsilon+\alpha\rho\cos(m\chi)$ no longer vanishes. This seed is what the two covariance arms carry.
   - (LR-A3) *Orientation imbalance.* The $J$-carrying arms multiply each carrier by $(1+s\beta)$ with $\beta=0.05$; the two orientations sum to the unmodulated total, so the loop mean of $H$ is $\beta(E_Y+E_I)$ cellwise while the projection still reproduces $E_a$ exactly.
   - (LR-A4) *Velocity split.* The split arm replaces the shared velocity by $u_\mp=u\mp0.05$ in the two orientations.
7. **Process.** One invocation of one process, no multiprocessing and no concurrent runs. The carrier state is at most $4\times7\times24=672$ float64 values; the receipt records the device, the declared execution count and the step counts.

### 1.3 Relation to the spent protocol: comparability, not inheritance

Thirteen of this protocol's sixteen arms are the spent protocol's own closure arms, re-declared in §3.1 with the same names, profiles, seeds, mode content, step sizes and horizons, because the two runs are to be directly comparable and the spent receipt's per-arm figures (thirteen of fifteen arms at or below $2.62\times10^{-15}$ over their whole traces) are the readings a comparability claim rests on; a reader should not have to re-establish that number on different machinery. The remaining three arms carry the repaired witness and the new statistic, and they are re-declarations too: the two spent arms that failed to fire are rebuilt here with the same constructions and the witness this protocol declares, and one arm is new. Nothing else is inherited: the spent protocol's thresholds, labels, gap rule, class vocabulary and verdicts do not bind this document, and where this document's rules coincide with the spent protocol's it is because they are stated here in full, not because they are incorporated by reference.

## 2. The statistics

### 2.1 The deviation, its peak, and the sensitivity witness

Both arms of every closure arm start from the same projected densities, $E^{\rm loop}_a(x,0)=E^{\rm can}_a(x,0)$, checked at $10^{-15}$. Write $E^{\rm loop}$ for the projection (LB1) of the evolved four-population state and $E^{\rm can}$ for the independently evolved solution of (LB7). At every accepted state $k=0,\dots,K$,

$$
\rho_k
=
\frac{\max_a\max_i\bigl|E^{\rm loop}_{a,i}(t_k)-E^{\rm can}_{a,i}(t_k)\bigr|}
{\max\bigl(1,\ \max_a\max_i|E^{\rm can}_{a,i}(t_k)|\bigr)},
\qquad
\rho_{\max}=\max_{0\le k\le K}\rho_k,\qquad
\rho_{\rm fin}=\rho_K .
\tag{LR1}
$$

$\rho_k$ is a residual of exactness: Theorem 1 makes the projected carrier flow and the canonical flow the same flow, so $\rho_k$ measures the declared realization's departure from an identity.

**The sensitivity witness.** For every arm whose purpose is to witness a disagreement, the declared reading is $\rho_{\max}$, the maximum deviation over the run, and its requirement is

$$
\rho_{\max}>10^{-4},
\tag{LR-W}
$$

the declared witness floor. The terminal deviation $\rho_{\rm fin}$ and the time of the maximum are recorded as observations and enter no criterion. The reason is the one the spent run established: a control exists to show that the instrument can see a disagreement, and on an attracting target the terminal state cannot carry that witness, because the fixed ratio of the conversion law is attracting and the converged horizon $T_{\rm conv}=10/g$ exists precisely to let every perturbation relax back onto the canonical trajectory. The spent protocol declared the terminal state as the reading for its two disagreement controls and thereby measured a re-converged arm: its maxima were $2.0326187974944866\times10^{-3}$ and $5.998107248579932\times10^{-4}$ while its terminal readings were $3.376811012630109\times10^{-8}$ and $1.0496654051001292\times10^{-14}$.

**Falsifier.** A required arm whose $\rho_{\max}$ is at or below $10^{-4}$ shows that the instrument is blind to a disagreement of the size the feature needs. That is `status=FAIL` with no verdict (feature H1 of §5.2), and it is not a statement about the carrier.

### 2.2 The relaxation statistic

The deviation of an arm that injects a disagreement is generated while the injected content is present and then decays. This protocol freezes the decay rate as a statistic.

**The fit (LR2).** With the arm's trace $\{(t_k,\rho_k)\}$, the declared window is the second half of the trace,

$$
W=\{k:\ t_k\ge T/2,\ \rho_k>10^{-12}\},
\qquad
\nu_{\rm fit}=-\text{slope of }\ln\rho_k\text{ on }W\text{ by least squares},
\tag{LR2}
$$

recorded with its sample count $|W|$. If $|W|<50$ the reading is `no_fit` and the arm's rate clause fails; the window and the floor are declared here, before execution, so that a fit can neither be moved after the fact nor silently replaced.

**The arm's conversion bracket (LR3).** From the arm's own effective field (LR-A0), recorded by the probe from the declared field before execution,

$$
c_-=\min_{i,\chi}\kappa^{\rm eff}_i(1+\varphi),
\qquad
c_+=\max_{i,\chi}\kappa^{\rm eff}_i(1+\varphi),
\qquad
\ell=\min[c_-,\,2r,\,g_1],
\tag{LR3}
$$

with the reachability floor $c_-\ge10^{-6}$: below it the arm's slowest channel is not resolved by a $10^{-12}$ fit floor and the arm may not carry a rate clause. $\ell$ is the frozen (LB39) gap of §1.1 evaluated on the field the arm actually evolves; the spent protocol recorded its gap on the ungated field, which understated its covariance arm's slowest channel by a factor two.

**The rate clause (LR-R1).** A covariance arm's fitted rate must lie inside its own conversion bracket,

$$
0.9\,c_-\ \le\ \nu_{\rm fit}\ \le\ 1.1\,c_+ .
\tag{LR-R1}
$$

The bracket is declared rather than a single rate, with the reason stated: the tail of a sup-norm deviation is a mixture of the arm's own conversion channels, whose per-cell rates span $[c_-,c_+]$, and which cell dominates the tail is one of the things this run measures. The bracket is still a discriminating requirement: the competing readings it excludes by construction are the loop-mode rates ($g_1=0.2728$ is eleven times $c_+$ in the reference arm, and $g_2=0.7799$ is thirty-two times it), any constant read, and any artifact of the horizon, since all three lie outside it.

**The scaling clause (LR-R2).** The scaled arm differs from the reference arm in $s$ alone, and every $\kappa$-dependent channel rate scales by $s$ exactly while neither the $2r$ nor the $g_1$ bound of (LR3) binds in either arm, so the declared ratio of their fitted rates is exactly $1/2$:

$$
\frac{\nu_{\rm fit}({\rm scaled})}{\nu_{\rm fit}({\rm reference})}\in[0.45,\ 0.55].
\tag{LR-R2}
$$

This is the relaxation statistic's can-fail control: a statistic that reads the horizon, the seed amplitude, the mode rates, the normalization or roundoff cannot track a factor-two separation in the conversion scale, and the clause fails.

**Recorded observation (not a criterion).** $\nu_{\rm fit}/\ell$ is recorded for each covariance arm, so that this run states whether the tail approaches the arm's slowest channel; it gates nothing, because the protocol does not nominate the dominant cell of the mixture as §2.2 explains.

### 2.3 The scale-stable covariance identity

**(LR4).** Let $D_0=\max\bigl(1,\ \langle\kappa^{\rm eff}\rangle_\chi(0)\cdot\max_\chi|Z(0)|\bigr)$ be the arm's declared initial operand scale, read and recorded before execution with the reachability floor $D_0\ge10^{-6}$. The discrete form of (LB14) must hold at every accepted state with residual $R_k$ against that fixed scale,

$$
R_k\ \le\ 10^{-12}\,D_0 .
\tag{LR4}
$$

$D_0$ is a $t_0$ constant and cannot shrink as the arm evolves, so (LR4) is a fixed absolute bound on the identity's residual over the whole run: it can be met only by a residual that stays at roundoff on the arm's own declared scale. The spent protocol instead normalized by $\max(10^{-12},|{-}\langle\kappa\rangle\varepsilon-\operatorname{Cov}_\chi(\kappa,Z)|)$ at the same state, a quantity that decays with the very content its control injects, and its receipt records what that produces: a residual of `4.308692590324274e-09` against a `1e-12` bound. That number is a ratio to a decaying operand, so the same absolute residual reads as a growing relative disagreement as the arm relaxes; under (LR4) it is measured once against a $t_0$ constant and cannot be read two ways. The floor $D_0\ge10^{-6}$ is the same order as the spent protocol's composition floor for this control, which read $1.28$ at the seed.

### 2.4 Horizons, steps, and the declared fields

**(LR-S1) Step rule.** $\Delta t=\max\{\Delta t\in\{0.05,0.02,0.01\}:\Delta t\le1/(40\lambda_{\max})\}$, where $\lambda_{\max}$ is the largest $|\operatorname{Re}\Lambda|$ over the arm's frozen closed spectrum (LB36) at the arm's own mode content and peak $\kappa^{\rm eff}$, or $\max(u/\Delta x,\ D_x/\Delta x^2)$ for an arm with no mode content.

**(LR-S2) Horizon rule.** A convergence arm takes $T=\min(10/g,1000)$ with $g$ its internal gap (LB39) on its own effective field; a mode arm takes $T_{\rm mode}=\min(10/g_1,1000)$, its short counterpart $T_{\rm short}=T_{\rm mode}/100$, and the current arm $T=\min(10/g(r=0),1000)$.

**Declared consequences, computed before execution.** The three relaxation arms carry $m=\pm1$ mode content at $\alpha=0.25$, so (LR-S1) gives $\Delta t=0.02$; (LR-S2) gives $T=1000$ for all three because the cap binds ($10/c_-$ is $2472$ for the reference arm, $4944$ for the scaled arm and $1236$ for the split arm), so each is $50{,}000$ steps. The thirteen closure arms take the same $\Delta t$, horizon and step count as the spent protocol's arms of the same construction, because their fields, seeds and rules are the same; the spent receipt records those thirteen figures per arm.

## 3. The arm list

### 3.1 Closure group—thirteen arms, re-declared from the spent protocol

Each arm here is one execution; the last column is the reading the spent receipt records for the identical construction, quoted as an expectation and not as a criterion.

| # | arm | profile | seed | gate | horizon | grid | spent reading |
|---|---|---|---|---|---|---|---|
| 1 | `off_ray` | `off_ray` | — | $\kappa$ | $T_{\rm conv}$ | $7\times24$ | $\rho_{\max}=1.67\times10^{-16}$ |
| 2 | `off_ray_refined` | `off_ray` | — | $\kappa$ | $T_{\rm conv}$ | $7\times24$, $\Delta t/2$ | $1.67\times10^{-16}$ |
| 3 | `on_ray` | `on_ray` | — | $\kappa$ | $T_{\rm conv}$ | $7\times24$ | $1.01\times10^{-16}$ |
| 4 | `on_ray_refined` | `on_ray` | — | $\kappa$ | $T_{\rm conv}$ | $7\times24$, $\Delta t/2$ | $1.01\times10^{-16}$ |
| 5 | `open_gate` | `open_gate` | — | $\kappa$ | $T_{\rm conv}$ | $7\times24$ | $5.55\times10^{-17}$ |
| 6 | `closed_gate` | `closed_gate` | — | $\kappa$ | $T_{\rm conv}$ | $7\times24$ | $1.65\times10^{-16}$ |
| 7 | `loop_truncated` | `on_ray` | — | $\kappa$ | $T_{\rm conv}$ | $7\times12$ | $2.76\times10^{-16}$ |
| 8 | `mode1_short` | `on_ray` | (LR-A1), $m=\pm1$ | $\kappa$ | $T_{\rm short}$ | $7\times24$ | $3.40\times10^{-16}$ |
| 9 | `mode1_long` | `on_ray` | (LR-A1), $m=\pm1$; (LR-A3) | $\kappa$ | $T_{\rm mode}$ | $7\times24$ | $2.62\times10^{-15}$ |
| 10 | `mode2_long` | `on_ray` | (LR-A1), $m=\pm2$; (LR-A3) | $\kappa$ | $T_{\rm mode}$ | $7\times24$ | $2.22\times10^{-15}$ |
| 11 | `uniform_short` | `on_ray` | — | $\kappa$ | $T_{\rm short}$ | $7\times24$ | $8.51\times10^{-17}$ |
| 12 | `null` | `on_ray` | — | $\kappa$ | $T_{\rm short}$ | $7\times24$ | $8.51\times10^{-17}$ |
| 13 | `persistent_current` | `on_ray` | (LR-A1), $m=\pm1$; (LR-A3), $r=0$ | $\kappa$ | $T(r=0)$ | $7\times24$ | $1.23\times10^{-14}$ |

Arms 11 and 12 carry the same state on the same arithmetic and form the **null pair**; arms 1/2 and 3/4 are the two declared refinement pairs; arms 8 and 11 form the short mode pair and arms 9, 10 and 11 the long one. The mode readouts and the $J$ readout of §5.1 are read exactly as the spent protocol read them ($\Delta_m$ on the states a mode arm shares with its counterpart in model time, $w_m$ as the loop-mode energy ratio, $J$ as the domain mean of $\langle H\rangle_\chi$ with the max-abs reduction recorded beside it), and no closure arm carries a witness or a rate clause.

### 3.2 Relaxation group—three arms, the repaired witness and the new statistic

| # | arm | profile | seed | effective field | $\Delta t$ | $T$ | steps | clauses it carries |
|---|---|---|---|---|---|---|---|---|
| 14 | `relax_reference` | `on_ray` | (LR-A1) $m=\pm1,\pm2$; (LR-A2) | (LR-A0), $s=1$ | $0.02$ | $1000$ | $50{,}000$ | (LR-W), (LR4), (LR-R1) |
| 15 | `relax_scaled` | `on_ray` | (LR-A1) $m=\pm1,\pm2$; (LR-A2) | (LR-A0), $s=\tfrac12$ | $0.02$ | $1000$ | $50{,}000$ | (LR-W), (LR4), (LR-R1), (LR-R2) |
| 16 | `relax_split` | `on_ray` | (LR-A1) $m=\pm1$; (LR-A4) | $\kappa$ | $0.02$ | $1000$ | $50{,}000$ | (LR-W) |

Arms 14 and 15 differ in $s$ alone, which is the construction (LR-R2) tests. Arm 14 is the same construction as the spent protocol's `covariance` control, re-declared with the peak witness and the corrected gap; arm 16 is the same construction as its `direction_split` control, re-declared with the peak witness and no rate clause—this protocol derives no rate for the orientation-imbalance channel, since that channel is not one of the arm's conversion cells, and gating a rate it cannot declare would be a criterion invented after the fact. Its fitted rate is recorded as an observation.

## 4. Integrity gates and firing controls

The schedule reports `status=PASS` only when every gate passes. A failed gate is `status=FAIL` with no verdict.

1. **Source binding.** `computations/verify_loop_to_bubble_projection.py` is imported and accepted only at SHA-256 `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1`. The probe reads the frozen operators and constants rather than reimplementing them, and fails closed if that file changes. This protocol's own digest is recorded in §8 at execution.
2. **Discrete annihilation.** For every carrier state and every arm, $|\sum_j\partial_\chi f|\le10^{-14}\max|f|$ and $|\sum_j\partial_\chi^2f|\le10^{-14}\max|f|$ on the equal-weight loop grid (LB8). Any loop stencil whose grid sum is nonzero fails here.
3. **Projection idempotence.** $P(Pf)=Pf$ to $10^{-15}$ relative at every accepted state.
4. **Shared exterior transport.** $u$ and $D_x$ identical in all four channels and independent of $\chi$ in every closure arm. The split arm violates this by construction and records its measured violation instead of failing the schedule, as gate 5 declares for the two covariance arms.
5. **Common gate.** $\max_\chi|\kappa^{\rm eff}(\chi,t)-\langle\kappa^{\rm eff}\rangle_\chi(t)|=0$ in every closure arm. Arms 14 and 15 violate this by construction and record the measured violation; that is what their gate factor is for.
6. **Matched start.** $\max_a\max_i|E^{\rm loop}_{a,i}(0)-E^{\rm can}_{a,i}(0)|\le10^{-15}$.
7. **Finite and nonnegative.** Every recorded scalar finite; every $f_{a,s}\ge0$ at every accepted state; $0\le q<1$; the projection of a positive state positive.
8. **Declared shape.** Sixteen executions; every arm records a reading for every statistic it carries; the recorded total step count is at most the declared cap of §6 and the per-arm counts are the figures (LR-S1) and (LR-S2) compute. An arm that drops out fails rather than shortening the table.
9. **Spectrum re-check.** For each mode-carrying closure arm, the measured per-mode decay agrees with (LB36) at that arm's own $\kappa$ to $10^{-9}$.
10. **Witness floor.** The null pair reads $\rho_{\max}\le10^{-11}$ and $\Delta=0$ exactly. Otherwise the statistic cannot resolve the $10^{-6}$ feature and the run is `status=FAIL`.
11. **Bracket and identity reachability.** For arms 14 and 15, read before execution: $D_0\ge10^{-6}$, $c_-\ge10^{-6}$ and $c_+\le1$. A failed reading is `status=FAIL` before any arm executes, since a rate clause whose bracket is unresolved cannot be met.
12. **Process declaration.** The receipt records one process, sixteen executions, the device, and the absence of concurrent runs.

**Firing controls.** Each is required to fire; a control that does not fire makes the run `status=FAIL` with no verdict, because the feature it witnesses would then be unmeasured.

- **Null pair** (`uniform_short`, `null`) — same state, same arithmetic; required readings $\rho_{\max}\le10^{-11}$ and $\Delta=0$ exactly.
- **`relax_reference`** — required readings: $\rho_{\max}>10^{-4}$ (LR-W); (LR4) at every accepted state; $\nu_{\rm fit}$ inside (LR-R1) for its own bracket.
- **`relax_scaled`** — required readings: $\rho_{\max}>10^{-4}$; (LR4) at every accepted state; $\nu_{\rm fit}$ inside its own bracket; the ratio clause (LR-R2).
- **`relax_split`** — required reading: $\rho_{\max}>10^{-4}$ (LR-W). Its $\nu_{\rm fit}$ is recorded and not gated, for the reason §3.2 states.

## 5. Decision tree

### 5.1 Closure features

| feature | condition | labels |
|---|---|---|
| **G1** exact closure realized | $\rho_{\max}\le10^{-6}$ in every closure arm | EMERGES / DOES NOT EMERGE |
| **G2** the readings are the mechanism's, not the step size's | for each declared refinement pair, the two arms' $\rho_{\max}$ agree within a factor $4$ | EMERGES / DOES NOT EMERGE |
| **G3** the instrument is live | the null pair meets its floor, arms 14 and 15 meet (LR4) at every accepted state, and gate 11's reachability readings hold | EMERGES / DOES NOT EMERGE |

G2 replaces the spent protocol's feature of the same purpose, which read "every closure arm with $\rho_{\max}>10^{-6}$ has a refinement partner whose $\rho_{\max}$ falls by at least $4\times$". That condition quantifies over arms above the budget while the same tree's G1 requires every closure arm to be at or below it, so its antecedent is empty whenever the protocol is about to pass and the feature is true by construction; the spent receipt records exactly that, with no closure arm above $10^{-6}$. G2 is applied to measured readings on both members of each declared pair and is not entailed by G1: a pair reading $10^{-6}$ coarse and $10^{-16}$ refined satisfies G1 and violates G2.

Per-arm classes, assigned to the four arms of the two refinement pairs and tested in this order:

1. `within_budget` — $\rho_{\max}\le10^{-6}$;
2. `step_dependent` — the pair's $\rho_{\max}$ ratio lies outside $[\tfrac14,4]$, so the reading moves with the step size and no agreement between two runs at different resolutions is possible;
3. `structural_disagreement` — $\rho_{\max}>10^{-4}$ and the pair is inside $[\tfrac14,4]$, so the reading is stable and far above the budget.

Aggregate **closure verdict**, only on `status=PASS`:

- `EMERGES` — G1, G2 and G3 emerge: the evolved carrier's projected trajectory reproduces the canonical trajectory at the declared budget, at every accepted state of every closure arm, with the readings stable under the declared refinement and the instrument live.
- `CONTRADICTS` — G3 emerges and some arm is `structural_disagreement`.
- `INCONCLUSIVE` — G3 emerges, G1 does not, and no arm is `structural_disagreement`: the declared arms are under-resolved, or step-dependent, or the reading sits between the budget and the structural scale.
- `status=FAIL` and no verdict — G3 does not emerge.

### 5.2 Relaxation features

| feature | condition | labels |
|---|---|---|
| **H1** the witness is visible | every relaxation arm reaches $\rho_{\max}>10^{-4}$ | EMERGES / DOES NOT EMERGE |
| **H2** the deviation decays in its own conversion bracket | arms 14 and 15 satisfy (LR-R1) for their own brackets | EMERGES / DOES NOT EMERGE |
| **H3** the rate scales with the conversion scale | (LR-R2) holds | EMERGES / DOES NOT EMERGE |

Aggregate **relaxation verdict**, only on `status=PASS`:

- `EMERGES` — H1, H2 and H3 emerge: a deviation from the canonical trajectory injected at the declared seeds is visible above the witness floor, its tail decays at a rate inside the arm's own conversion bracket at both gate amplitudes, and that rate scales with the conversion scale exactly as the declared channels do.
- `CONTRADICTS` — H1 emerges and H2 does not: the deviation is visible and its tail decays at a rate none of the arm's own conversion cells carries, so the relaxation is not the declared channel's.
- `INCONCLUSIVE` — H1 and H2 emerge and H3 does not: the tail lands in the bracket at one amplitude but the reading does not scale with the conversion scale, so the statistic's mechanism is not established at these settings.
- `status=FAIL` and no verdict — H1 does not emerge: the peak deviation is at or below the witness floor, so the instrument cannot see a disagreement of the required size.

### 5.3 Falsifiers

- A `CONTRADICTS` closure verdict falsifies the claim that the declared discrete realization reproduces (LB7) from (LB6) at these settings; with every assumption gate passing, the remaining explanation is the realization, and the receipt names the arm, the state and the local-error probe.
- A `CONTRADICTS` relaxation verdict falsifies the claim that a deviation from the canonical trajectory decays at the arm's own conversion-channel rates.
- An `INCONCLUSIVE` relaxation verdict records that the fitted rate does not scale with the declared conversion scale, so the rate reading is not established as the declared channel's.
- A `DOES NOT EMERGE` on H1 is not a statement about the carrier: it records that this protocol's witness could not see a disagreement of $10^{-4}$ and returns `status=FAIL` with no verdict.
- A `status=FAIL` on any gate falsifies nothing about the theorem or the carrier; it records that this protocol did not measure its features, and §6 permits no re-run at another setting.

## 6. Run schedule, budget, and stopping rule

**Executions.** Sixteen arms, each one execution of the same script:

```text
timeout 1200 python computations/verify_loop_carrier_projection_relaxation.py
```

The receipt is `runs/loop_carrier_projection_relaxation/verification.json` and the log is `runs/loop_carrier_projection_relaxation/invocation.log`; both are gitignored run artifacts. Sixteen executions; the receipt must record sixteen. The step counts are $132{,}334$ for the thirteen closure arms (the spent receipt's per-arm figures, summed) and $50{,}000$ each for the three relaxation arms, so the declared schedule is $282{,}334$ RK2 steps. The per-execution cap is $50{,}000$ and the declared total cap is $290{,}000$; gate 8 requires the recorded counts to be the rules' figures and the recorded total to be at or below the cap.

**Cost model, anchored to a measured run.** The spent invocation ran $232{,}334$ RK2 steps of this same arithmetic—the same frozen operators, the same canonical companion arm, the same per-stage gate evaluation and the same per-state identity reading—in `runtime_seconds` 185.23 s of one process (`runs/loop_carrier_projection_dynamics/verification.json`), which is $7.97\times10^{-4}$ s per step. Scaling by the declared $282{,}334$ steps gives a projection of **225 s**. The anchor is preferred over an arithmetic model because it measures the whole loop, NumPy call overhead included, and this schedule adds no per-step work of a different order: the relaxation arms record the same $\rho_k$ the spent arms already recorded, and the two added readings (one log-slope fit per relaxation arm and the $t_0$ checks of gate 11) run once, not per step. The declared projection carries the range $180$–$270$ s, the anchor being a single measurement.

**Bound.** The invocation is bounded at **1200 s** by the outer `timeout`, $5.3\times$ the projection and $6.5\times$ the measured run it is anchored to. This is deliberately tighter than the spent protocol's $5400$ s against an $185$ s run, because the spent run's own measurement, not a per-step estimate, now sets the scale.

**Stopping rule.** One invocation. If it expires inside the bound without writing a receipt, the record states the bounded attempt with the last printed progress line and no verdict; one further invocation of the identical command is then permitted, and the aggregate wall time across invocations is capped at $2400$ s. Beyond that the schedule stops with no verdict. The arm list, the horizon rule, the step rule, the thresholds, the witness, the fit window and the decision tree are not changed after any invocation, and a timeout is not converted into a shorter arm list or a cheaper statistic. A re-run at another setting is not permitted: this protocol measures what it measures.

**Deferred execution.** This protocol is frozen before any run and no invocation has been made. Execution is queued; §8 is filled when it completes.

## 7. Interpretation boundary

A positive closure reading shows that this declared finite realization evolves the four-population law so that its complete loop average tracks the canonical two-density system at the declared step sizes and horizons, on four discrete initial profiles at one rate set. The statement carries the theorem's own boundary, quoted in §11 of that document: the closure is derived conditional on the common projected gate and common exterior transport, and the four-population law itself is the selected minimal member of a family, since any direction-mixing conversion whose columns sum to one projects to the same canonical law. A positive relaxation reading adds one statement and no more: a deviation from the canonical trajectory, injected by the declared seeds, reaches a peak above $10^{-4}$ and then decays at a rate that lies inside the arm's own conversion bracket and scales with the conversion scale. It does not show that every deviation relaxes at a conversion rate, that the decay mechanism is the same one the canonical two-fluid probe measures, or that the $\varphi$-ray's attraction is a property of the loop carrier rather than of the conversion law it shares. Nothing here shows that the loop carrier is physically realized, supplies a phase law for $\theta_{a,s}$, identifies $\mathbf J_\Psi$, fixes the physical carrier identity or the QF1-to-carrier state map, or changes any row of the theorem's result ledger, of `open-questions-cassi-answers.md`, of `parameter-inventory.md` or of the DQ and GQ physical-identification verdicts.

## 8. Post-execution record

Sections 1–7 state the protocol as it stands frozen. This section is filled when the queued invocation completes: the invocation and its bound, the receipt path and digest, the gate table, the per-arm readings, the witness readings $\rho_{\max}$, $\rho_{\rm fin}$ and the peak time, the fitted rates with their windows and sample counts, both brackets and both $\ell$, the classes, both verdicts, and the digests of the frozen sources (this file, `computations/verify_loop_to_bubble_projection.py`, and the executed probe script). No text of sections 1–7 is edited after an invocation; the spent protocol's record stands as written in `computations/loop-carrier-projection-dynamics-prereg.md` §8 and `field-experience/probe-outcome-ledger.md` §64.

### 8.1 Invocation

| Item | Reading |
|---|---|
| Command | `timeout 1200 python computations/verify_loop_carrier_projection_relaxation.py`, one process from this directory tree's root, `PID` $16572$ |
| Bound | $1200$ s, declared in §6 |
| Wall time, measured outside | $236.4$ s (`real 3m56.399s`), $5.1\times$ inside the bound |
| Wall time, inside | `runtime_seconds` $236.08994817733765$, against the §6 projection of $225$ s |
| Executions | $16$, one per arm, in the order of the §6 table |
| Receipt | `runs/loop_carrier_projection_relaxation/verification.json`, $81{,}496$ bytes, SHA-256 `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` |
| Log | `runs/loop_carrier_projection_relaxation/invocation.log`, SHA-256 `973153da5a2ff2c50300ca26afba8f7457f322574c2a1abe6bb9de533c9c1287` |
| Status | `PASS`, both verdicts issued |

**Execution note.** This protocol was frozen as text without its executor: the executed probe script did not exist at the commit that froze this file, and it was authored at execution time as a transcription of the spent protocol's probe—the frozen operators, the integrator, the construction functions, the thirteen closure arms with their step counts and horizons, and every threshold of §1, §3.1, §4 and §6 are carried over unchanged, and the new constituents of §2.2–§2.4, §3.2 and §5 are added. The transcription is not asserted but checked against the spent run: all thirteen closure arms reproduce the spent receipt's $\rho_{\max}$ bit for bit (§8.3), on the same step sizes, horizons and seeds. The digests of the frozen sources, read by the receipt and re-read after the invocation:

| Source | SHA-256 |
|---|---|
| `computations/loop-carrier-projection-relaxation-prereg.md` (this file) | `699f7b4d3f84cf127af254a3f0250448ff5eb675ada04f4257206a8db2684b38` |
| `computations/verify_loop_to_bubble_projection.py`, expected and observed | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` |
| `computations/verify_loop_carrier_projection_relaxation.py`, executed | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` |

### 8.2 Gate table

Twelve of twelve passed.

| Gate | Reading | Bound |
|---|---|---|
| 1 source binding | `d687597f…` observed, equal to the bound digest | exact |
| 2 discrete annihilation | $5.10702591327572\times10^{-15}$ | $10^{-14}$ |
| 3 projection idempotence | $2.0185873175002629\times10^{-16}$ | $10^{-15}$ |
| 4 shared exterior transport | `velocity_split` $0.0$ in all thirteen closure arms; the split arm records its $0.05$ violation | $0.0$ in every closure arm |
| 5 common gate | closure spread $0.0$; arms 14 and 15 record $3.0433\times10^{-3}$ and $4.5635\times10^{-3}$ | $0.0$ in every closure arm |
| 6 matched start | $8.881784197001252\times10^{-16}$ | $10^{-15}$ |
| 7 finite and nonnegative | true, with $0.3607\le q\le0.9960$ and every projection positive | every scalar finite, $f\ge0$, $0\le q<1$ |
| 8 declared shape | $16$ executions, $282{,}334$ recorded steps against the $290{,}000$ cap, per-arm counts the rules' figures, no missing statistic | as declared in §6 |
| 9 spectrum re-check | four mode-carrying closure arms, largest residual $4.688438624709709\times10^{-16}$ | $10^{-9}$ |
| 10 witness floor, null pair | $\rho_{\max}$ $8.505827589859918\times10^{-17}$ in both arms and $\Delta=0$ exactly | $10^{-11}$, $\Delta=0$ |
| 11 bracket and identity reachability, read before execution | $D_0=1.0$ for both covariance arms; $c_-$ $4.0456114916509155\times10^{-3}$ and $2.0228057458254577\times10^{-3}$; $c_+$ $2.389484016651345\times10^{-2}$ and $1.1947420083256725\times10^{-2}$ | $D_0\ge10^{-6}$, $c_-\ge10^{-6}$, $c_+\le1$ |
| 12 process declaration | one process, $16$ executions, CPU, no concurrent run | as declared |

### 8.3 Closure arms

Every closure arm is `within_budget`, and every reading is bit-identical to the spent receipt's reading of the same construction:

| Arm | $\rho_{\max}$ | $\rho_{\rm fin}$ | Class |
|---|---|---|---|
| `off_ray` | $1.665296162182208\times10^{-16}$ | $7.932728\times10^{-17}$ | `within_budget` |
| `off_ray_refined` | $1.6653180651897577\times10^{-16}$ | $0.0$ | `within_budget` |
| `on_ray` | $1.0092936587501317\times10^{-16}$ | $1.009294\times10^{-16}$ | `within_budget` |
| `on_ray_refined` | $1.0092936587501259\times10^{-16}$ | $0.0$ | `within_budget` |
| `open_gate` | $5.551115123125783\times10^{-17}$ | $5.551115\times10^{-17}$ | `within_budget` |
| `closed_gate` | $1.653758697\times10^{-16}$ | $8.881784\times10^{-17}$ | `within_budget` |
| `loop_truncated` | $2.758858630\times10^{-16}$ | $2.018587\times10^{-16}$ | `within_budget` |
| `mode1_short` | $3.400322915\times10^{-16}$ | $3.400323\times10^{-16}$ | `within_budget` |
| `mode1_long` | $2.622443970\times10^{-15}$ | $2.219140\times10^{-15}$ | `within_budget` |
| `mode2_long` | $2.218991051\times10^{-15}$ | $1.815660\times10^{-15}$ | `within_budget` |
| `uniform_short` | $8.505827589859918\times10^{-17}$ | $8.505828\times10^{-17}$ | `within_budget` |
| `null` | $8.505827589859918\times10^{-17}$ | $8.505828\times10^{-17}$ | `within_budget` |
| `persistent_current` | $1.2313382636751607\times10^{-14}$ | $1.049665\times10^{-14}$ | `within_budget` |

The two declared refinement pairs agree within the factor $4$ of G2, at ratios $0.9999868475530246$ and $1.0000000000000058$; both members of each pair sit at the arithmetic floor, as they did in the spent run.

### 8.4 Relaxation arms

| Arm | $s$ | $\rho_{\max}$ | peak time | $\rho_{\rm fin}$ | fit window | samples | $\nu_{\rm fit}$ | (LR-R1) bracket | inside | $\nu_{\rm fit}/\ell$ | (LR4) residual |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `relax_reference` | $1$ | $2.0326187974944866\times10^{-3}$ | $11.64$ | $3.376811012630109\times10^{-8}$ | $[500,1000]$ | $25{,}001$ | $1.119569724312185\times10^{-2}$ | $[3.641050342485824\times10^{-3},2.6284324183164797\times10^{-2}]$ | yes | $2.767368361056627$ | $2.3892561918486857\times10^{-18}$ |
| `relax_scaled` | $\tfrac12$ | $1.1055338816802886\times10^{-3}$ | $14.96$ | $4.486540938158338\times10^{-6}$ | $[500,1000]$ | $25{,}001$ | $5.615991276376917\times10^{-3}$ | $[1.820525171242912\times10^{-3},1.3142162091582399\times10^{-2}]$ | yes | $2.776337415476921$ | $1.2145393672442599\times10^{-18}$ |
| `relax_split` | $1$ | $5.998107249\times10^{-4}$ | $8.18$ | $1.0496654051001292\times10^{-14}$ | empty | $0$ | not fitted | — | — | — | $1.1036085720070312\times10^{-18}$ |

The fit window is $W=\{t\ge500,\ \rho>10^{-12}\}$; the split arm's tail passes below the floor before the window opens, so its rate is recorded as unfitted and gates nothing, as §3.2 declares. Every (LR4) residual is measured against the fixed absolute bound $10^{-12}D_0$ with $D_0=1.0$, taken at $t_0$ and not rescaled during the run; $\ell=c_-$ in both covariance arms. The ratio clause (LR-R2) reads $\nu_{\rm fit}(\text{arm }15)/\nu_{\rm fit}(\text{arm }14)=0.5016205024503622$ against its declared band $[0.45,0.55]$. The recorded observation $\nu_{\rm fit}/\ell$ is $2.77$ in both covariance arms and is not a criterion of this protocol.

### 8.5 Controls

| Control | Requirement | Reading | Fired |
|---|---|---|---|
| null pair (`uniform_short`, `null`) | $\rho_{\max}\le10^{-11}$, $\Delta=0$ exactly | $8.505827589859918\times10^{-17}$ both arms, $\Delta=0$ on $9$ matched states | yes |
| `relax_reference` | $\rho_{\max}>10^{-4}$; (LR4) at every accepted state; $\nu_{\rm fit}$ inside its own bracket | $2.0326\times10^{-3}$; $2.389\times10^{-18}\le10^{-12}$; $1.1196\times10^{-2}\in[3.6411\times10^{-3},2.6284\times10^{-2}]$ | yes |
| `relax_scaled` | the same, plus (LR-R2) | $1.1055\times10^{-3}$; $1.215\times10^{-18}\le10^{-12}$; $5.6160\times10^{-3}\in[1.8205\times10^{-3},1.3142\times10^{-2}]$; ratio $0.5016$ | yes |
| `relax_split` | $\rho_{\max}>10^{-4}$ | $5.9981\times10^{-4}$ | yes |

The two repaired controls are the spent protocol's two silent ones, with their traces bit-identical and only the reading changed. The spent `covariance` control read $\rho_{\rm fin}=3.376811012630109\times10^{-8}$ against $10^{-4}$ and an identity residual of $4.308692590324274\times10^{-9}$ against $10^{-12}$; this protocol's `relax_reference` reads the same trace at its peak, $2.0326187974944866\times10^{-3}$, and its identity at $2.389\times10^{-18}$. The spent `direction_split` control read $\rho_{\rm fin}=1.0496654051001292\times10^{-14}$; `relax_split` reads the same trace's peak, $5.998107249\times10^{-4}$. The sensitivity the spent terminal readings could not witness is present in the peak readings of the very traces the spent run already computed.

### 8.6 Verdicts

```text
PASS
closure_verdict: EMERGES
relaxation_verdict: EMERGES
```

G1, G2 and G3 emerge, so the evolved carrier's projected trajectory reproduces the canonical trajectory at the declared budget, at every accepted state of every closure arm, with the readings stable under the declared refinement and the instrument live. H1, H2 and H3 emerge, so a deviation injected by the declared seeds is visible above the witness floor, its tail decays at a rate inside the arm's own conversion bracket at both gate amplitudes, and that rate scales with the conversion scale as the declared channels do. The boundary of §7 applies verbatim and is not extended: this is one finite realization at $N_\chi=24$, one rate set, one seed amplitude, four initial profiles at one $\chi$-resolution each with one halved refinement, and the closure remains conditional on the common projected gate and the common exterior transport, with the four-population law the selected minimal member of a family whose members any direction-mixing conversion with unit column sums joins. The run measures no physical carrier identity, no phase law, no scale ratio and no quantum statistics, and no reading here is a value of $\varphi$: every closure arm sits at the arithmetic floor and the two fitted rates are $1.12\times10^{-2}$ and $5.62\times10^{-3}$, so this protocol adds no evidence about where $\varphi$ comes from. `field-experience/probe-outcome-ledger.md` §65 records the outcome in the house format.

## References

- `foundations/loop-to-bubble-projection-theorem.md`—shared-support loop carrier, projection theorem (LB1)–(LB14), frozen spectrum and gap (LB36)–(LB47), result ledger and verification
- `computations/verify_loop_to_bubble_projection.py`—frozen discrete operators, rate constants and closed spectrum, whose module this protocol imports and binds by digest
- `computations/loop-to-bubble-projection-pre-registration.md`—frozen construction and gates LB1–LB7 of the single-state identity check
- `computations/loop-carrier-projection-dynamics-prereg.md`—the spent protocol, whose §8 post-execution record and §6A amendment are the motivating evidence for §2
- `runs/loop_carrier_projection_dynamics/verification.json`—spent receipt at `status=FAIL` with both verdicts null, the source of this protocol's cost anchor and of every spent reading quoted here (gitignored run artifact)
- `computations/two-fluid-phi-ray-relaxation-prereg.md`—the canonical two-fluid measure of the same fixed ratio and its relaxation, cited for the attractor's status and not for any construction here
- `computations/navier-stokes-strain-band-split-cutoff-ladder-prereg.md`—house protocol pattern for a frozen statistic, a run matrix, integrity gates, a decision tree, a cost model and a stopping rule
- `field-experience/probe-outcome-ledger.md`—probe outcome record, updated on execution
