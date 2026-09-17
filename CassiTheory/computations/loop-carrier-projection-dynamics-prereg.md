# Loop-Carrier Projection Dynamics

## Status: Pre-registered—September 2026; amended September 16, 2026 before the first execution (§6A)

## Abstract

`foundations/loop-to-bubble-projection-theorem.md` states that one closed loop carrying four nonnegative populations—Yang and Yin in each of the two loop orientations—projects through its complete loop average onto the canonical two-density PDE, with the projected equations an exact consequence of the four-population law when the conversion gate is common around the loop and the exterior transport is shared (§3.2, Theorem 1). Every check of that statement so far is algebraic and single-state: `computations/verify_loop_to_bubble_projection.py` reads the projection of one right-hand side, the fixed ray, the Gram matrix, the alternating-phase cancellation, the frozen mode spectrum, projection non-injectivity, and the fivefold scaling on a $7\times12$ grid. The carrier state has never been evolved. This protocol evolves the four-population law and the canonical pair from the same projected initial densities over declared horizons, and measures the residual of the exactness as a function of the time step, so that a discretization residual is separated from a structural disagreement. It then asks the bounded second question: do unresolved loop modes change the projected trajectory at the declared resolution, and do they relax at the rates the frozen spectrum (LB38) assigns them? The construction is a finite arithmetic realization of a derived conditional identity. It supplies no evidence that the loop carrier is physically realized, no phase law for the loop amplitudes, and no strand-to-bubble scale ratio.

## 1. The carrier model

### 1.1 Definitions taken from the repository

Each item below is the theorem's own definition, cited by section and equation label. The probe implements them as written and computes nothing new at this level.

- **Loop fibre.** At each bubble-scale point $x$, one closed internal coordinate $\chi\in S^1\cong[0,2\pi)$, with $\chi\sim\chi+2\pi$ (`foundations/loop-to-bubble-projection-theorem.md` §2.1). Carrier label $a\in\{Y,I\}$, orientation $s\in\{+1,-1\}$, populations $f_{a,s}\ge0$ (§2.1). The phase lift $\psi_{a,s}=\sqrt{f_{a,s}}e^{i\theta_{a,s}}$ is kinematic: the theorem leaves the phase law $\theta_{a,s}$ open (§2.1).
- **Loop average and projection operator.** The normalized average $\langle g\rangle_\chi=(2\pi)^{-1}\int_0^{2\pi}g\,d\chi$ and

$$
\boxed{E_a(x,t):=\sum_{s=\pm1}\langle f_{a,s}(x,\cdot,t)\rangle_\chi},
\qquad a\in\{Y,I\},
\tag{LB1}
$$

§2.2. This is the exact operator that maps the four populations to the two densities, and it is the object the probe applies at every accepted state and the object the canonical arm evolves.
- **Canonical combinations and gate.** $\rho:=E_Y+E_I$, $\varepsilon:=E_Y-\varphi E_I$, $q(E_Y,E_I):=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$, with $0\le q<1$ for finite nonnegative densities (§2.2, LB2–LB3).
- **Loop couplings.** $\Omega:=v/R$ (oriented loop speed over loop radius), $d:=D_\ell/R^2$ (arclength diffusivity over radius squared), $r\ge0$ (symmetric direction-exchange rate), and the projected gate $\kappa(x,t):=\lambda[1-q(E_Y(x,t),E_I(x,t))]$ (§3.1, LB4–LB5).
- **Four-population law.**

$$
\boxed{
\begin{aligned}
\partial_t f_{Y,s}
={}&-(\mathbf u\cdot\nabla)f_{Y,s}
+D_x\nabla^2f_{Y,s}
-s\Omega\partial_\chi f_{Y,s}
+d\partial_\chi^2f_{Y,s}
+r(f_{Y,-s}-f_{Y,s})
-\kappa f_{Y,s}
+\varphi\kappa f_{I,s},\\
\partial_t f_{I,s}
={}&-(\mathbf u\cdot\nabla)f_{I,s}
+D_x\nabla^2f_{I,s}
-s\Omega\partial_\chi f_{I,s}
+d\partial_\chi^2f_{I,s}
+r(f_{I,-s}-f_{I,s})
+\kappa f_{Y,s}
-\varphi\kappa f_{I,s}.
\end{aligned}}
\tag{LB6}
$$

§3.1. Conversion is direction preserving; the direction-exchange term preserves each species total.
- **Projection theorem and its four assumptions.** Every $f_{a,s}$ periodic in $\chi$ and regular enough for the displayed derivatives; $\mathbf u$ and $D_x$ shared by all four channels and independent of $\chi$; $\Omega$, $d$, $r$ independent of $\chi$; and $\kappa$ computed from the projected densities, hence common around each loop. Under those assumptions the projection of every solution of (LB6) obeys the canonical pair

$$
\boxed{
\begin{aligned}
\partial_tE_Y
&=-(\mathbf u\cdot\nabla)E_Y
+D_x\nabla^2E_Y
-\lambda(1-q)\varepsilon,\\
\partial_tE_I
&=-(\mathbf u\cdot\nabla)E_I
+D_x\nabla^2E_I
+\lambda(1-q)\varepsilon.
\end{aligned}}
\tag{LB7}
$$

§3.2, Theorem 1. The proof runs through the two annihilation identities $\langle\partial_\chi f_{a,s}\rangle_\chi=0$ and $\langle\partial_\chi^2f_{a,s}\rangle_\chi=0$ (LB8), the direction-sum identity $\sum_s r\langle f_{a,-s}-f_{a,s}\rangle_\chi=0$ (LB9), and the common-gate conversion projection (LB10). §3.3 adds total-density conservation (LB11) and the uniform direction-balanced fixed ray $f_{Y,\pm}=\varphi C$, $f_{I,\pm}=C$, $C\ge0$, whose projection has $E_Y/E_I=\varphi$ and $\varepsilon=0$ (LB12–LB13).
- **Closure boundary.** With a loop-varying gate $\kappa(\chi)$ and $Z(\chi):=\sum_s[f_{Y,s}(\chi)-\varphi f_{I,s}(\chi)]$, the projected Yang conversion is

$$
-\langle\kappa Z\rangle_\chi
=-\langle\kappa\rangle_\chi\,\varepsilon
-\operatorname{Cov}_\chi(\kappa,Z),
\tag{LB14}
$$

a covariance correction that the common-gate contract excludes (§3.4). Direction-dependent exterior velocities or diffusivities leave unresolved projected fluxes by the same argument.
- **Frozen internal spectrum and gap.** With exterior derivatives suppressed and $\kappa$ frozen, the four-channel generator in mode $m$ has the Kronecker-sum spectrum

$$
\Lambda_{m,c,\pm}
=-dm^2+c-r\pm\sqrt{r^2-m^2\Omega^2},
\qquad
c\in\{0,-\kappa(1+\varphi)\},
\tag{LB36}
$$

the $m=0$ spectrum $\{0,-2r,-\kappa(1+\varphi),-2r-\kappa(1+\varphi)\}$ (LB37), the slow direction branch $g_m:=dm^2+r-\operatorname{Re}\sqrt{r^2-m^2\Omega^2}$ for $|m|\ge1$ (LB38), and the internal real gap

$$
g_{\rm int}
=
\min\left\{
\kappa(1+\varphi),\;
2r,\;
d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}
\right\}
\tag{LB39}
$$

after excluding the conserved total-density mode (§6.1–§6.3). The first loop harmonic is the slowest nonuniform mode. Pure ballistic circulation, $d=r=0$, has zero real gap.
- **Loop current.** With $F_s:=f_{Y,s}+f_{I,s}$, $F:=F_++F_-$ and $H:=F_+-F_-$, the complete loop average obeys $d\langle H\rangle_\chi/dt=-2r\langle H\rangle_\chi$ when exterior terms are suppressed (§6.4, LB40–LB45). Passive direction exchange damps the net orientation; persistent nonzero current with a positive gap requires a declared drive.
- **Reduced-description validity.** The zero-mode description is dynamically autonomous once $g_{\rm int}T_B\gg1$ (§7.2, LB47), where $T_B$ is the shortest bubble-scale evolution time relevant to the observation.

The result ledger assigns the closure "**Derived conditional**" with the boundary "common projected gate and common exterior transport", the spectrum "**Derived conditional**", persistent passive circulation with a positive gap "**Excluded**", a universal strand-to-bubble spatial ratio "**Open**", and physical loop-carrier and phase identification "**Hypothesized**" (§11).

### 1.2 Declared realization

The theorem is a continuum statement. The following pieces are choices made by this protocol; each is a numerical realization, and the receipt records them as declared inputs.

1. **Discrete operators.** Periodic centered differences in $x$ and in $\chi$, spacing $2\pi/N_x$ and $2\pi/N_\chi$, exactly the stencils of `computations/verify_loop_to_bubble_projection.py` (`derivative`, `laplacian`, functions at lines 28–39), read from that module by import. The frozen constants of that module (lines 12–25) supply $u=0.31$, $D_x=0.17$, $R=1.7$, $v=0.8$, $D_\ell=0.13$, $r=0.6$, $\lambda=0.04$, $\Omega=v/R$, $d=D_\ell/R^2$, $N_x=7$, $N_\chi=12$, tolerance $10^{-11}$.
2. **Loop resolution.** The primary grid is $N_\chi=24$ on the periodic loop, declared here because the frozen $N_\chi=12$ resolves only $m\le6$ and the mode arms below seed $m=\pm2$; the truncation arm re-runs one closure arm at the frozen $N_\chi=12$ so that the difference is a recorded reading. The exterior grid stays at the frozen $N_x=7$.
3. **Time stepping.** Classical RK4 in float64, with the canonical arm advanced by the same integrator, the same step count, and the same gate evaluation. Per-arm step size and horizon follow the frozen rule in §2.3.
4. **Gate placement.** $\kappa$ is evaluated from the projected densities at the start of each stage, identically in both arms, as assumption 4 requires.
5. **Initial conditions, thresholds, and control parameters.** Declared in §2.2 and §4. The covariance and direction-split controls are protocol interventions, not claims about the theory.
6. **Process.** One invocation of one process, no multiprocessing, no concurrent runs. The state is at most $4\times7\times24=672$ float64 values, far below the size where device placement changes the arithmetic; the receipt records the device and the declared execution count.
7. **Orientation imbalance of the J-carrying arms.** The arms whose $J$ reading carries a criterion — `mode1_long`, `mode2_long` and `persistent_current`, the $J$-carrying arms of §5.2 and §4 — seed each carrier with the factor $(1+s\beta)$, $\beta=0.05$. The two orientations then sum to the unmodulated total,

$$
\sum_{s=\pm1}(1+s\beta)=2,\qquad\text{so}\qquad E_a^{\rm seed}=\sum_s\langle f^{\rm uniform}_{a,s}(1+s\beta)\rangle_\chi=E_a
\tag{A1}
$$

so the loop average reproduces the declared densities and the closure and projection-blindness readings of §2 and §3 are untouched. The value is chosen once, before execution, for the sensitivity reason in §3.2: with $\beta=0.05$ the initial loop-mean current reads $0.0890$ in the frozen normalisation, ten orders above the roundoff accumulated over the $4447$ steps of §6 arm 15 (about $10^{-13}$ relative), while the seed stays a perturbation of the same size as the declared mode amplitude $\alpha=0.25$. It is not revisited after the run.
8. **Composition asymmetry of the covariance arm.** The `covariance` arm seeds the two carriers with opposite loop-phase factors,

$$
f_{Y,s}=\frac{E_Y}{2}\,[1+\alpha\cos(m\chi)],\qquad
f_{I,s}=\frac{E_I}{2}\,[1-\alpha\cos(m\chi)],
\qquad \langle 1\pm\alpha\cos(m\chi)\rangle_\chi=1,
\tag{A2}
$$

so each carrier's loop mean is exactly one, the projection again reproduces the declared densities, and the composition combination $Z(\chi)=\sum_s[f_{Y,s}-\varphi f_{I,s}]=\varepsilon+\alpha\rho\cos(m\chi)$ no longer vanishes. On the $\varphi$-ray, $\varepsilon\approx0$ cellwise, so $Z$ is carried entirely by the declared phase structure and the covariance term of (LB14) acts. The arm's other readouts are unaffected: the projection is unchanged, hence $\kappa$, $q$, the gate spread and the closure residual, and the annihilation and idempotence gates of §4 hold for any loop profile.
9. **The loop-mean current reading.** $J$ of (PD4) is read as the domain mean of $\langle H\rangle_\chi$, with the max-abs reduction recorded beside it as a reported figure. Under the declared periodic exterior terms the mean is a conserved quantity of (LB45),

$$
\frac{d}{dt}\int_0^{2\pi}\langle H\rangle_\chi\,dx
=\int_0^{2\pi}\Bigl[-(u\cdot\nabla)\langle H\rangle_\chi
+D_x\nabla^2\langle H\rangle_\chi-2r\langle H\rangle_\chi\Bigr]dx
=-2r\int_0^{2\pi}\langle H\rangle_\chi\,dx,
\tag{A3}
$$

because the advection and diffusion terms integrate to zero on the periodic grid, so $J(T)=e^{-2rT}$ is a measurement of the declared rates rather than a corrected one. The max-abs reduction is not usable for the $r=0$ reading: $\langle H\rangle_\chi$ carries the declared $20\%$ density modulation, which diffusion flattens over $T_{\rm mode}(r=0)=222.3$ with $D_xT=37.8$, so the ratio of the peak to its initial value falls from $1$ to $1/1.2=0.833$, below the declared floor of $0.9$.
10. **Clarifications declared with this protocol.** The convergence horizon takes the internal gap at the slowest cell of the arm's own gate (§2.2); $\Delta_m$ is read on the states a mode arm and its counterpart share in model time (§3.1); gates 4 and 9 are read over the contract arms and the §3 mode arms, with the controls' declared violations recorded rather than failing the schedule (§4). Each is stated again where it applies.

## 2. The statistic, the initial conditions, and the resolution ladder

### 2.1 Statistic

Both arms start from the same projected densities, $E^{\rm loop}_a(x,0)=E^{\rm can}_a(x,0)=E_a(0)$, checked at $10^{-15}$. Write $E^{\rm loop}$ for the projection (LB1) of the evolved four-population state and $E^{\rm can}$ for the independently evolved solution of LB7. At every accepted state $k=0,\dots,K$,

$$
\rho_k
=
\frac{\max_{a}\max_{i}\bigl|E^{\rm loop}_{a,i}(t_k)-E^{\rm can}_{a,i}(t_k)\bigr|}
{\max\bigl(1,\ \max_a\max_i|E^{\rm can}_{a,i}(t_k)|\bigr)},
\qquad
\rho_{\max}=\max_{0\le k\le K}\rho_k .
\tag{PD1}
$$

The statistic is a residual of exactness: Theorem 1 makes the projected carrier flow and the canonical flow the same flow, so $\rho_k$ measures the declared realization's departure from an identity, and the decision tree in §5 separates an integrator residual from a structural disagreement by the time-step refinement of §2.3. Two secondary readings over the same horizon are recorded for the closure arms: the residual of the canonical arm restarted from $E^{\rm loop}(t_k)$ over one step (a local-error probe), and the maximum step-to-step change of $\rho$ (a growth probe). Both are recorded values; they do not enter the classifier.

**Initial profiles.** The exterior modulation is $E_a(x)=B_a\,(1+0.20\cos x)$ on the $N_x=7$ periodic grid, so the advection and diffusion terms act at their declared rates. $B$ sets the composition:

| profile | $B_Y$ | $B_I$ | composition | role |
|---|---|---|---|---|
| `off_ray` | $0.90$ | $1.40$ | $\varepsilon\ne0$, gate partly open | far from the $\varphi$-ray |
| `on_ray` | $1.10$ | $1.10/\varphi$ | $\varepsilon=0$ exactly | on the $\varphi$-ray |
| `open_gate` | $0.35$ | $0.35/\varphi$ | low $\rho$, $q$ small | conversion runs hard |
| `closed_gate` | $5.00$ | $5.00/\varphi$ | high $\rho$, $q\to1$ | conversion nearly closed |

The two rays $E_I=B_Y/\varphi$ are formed by division, so $\varepsilon$ is at float64 roundoff. The `on_ray` profile carries the mode arms and the controls because the ray is invariant: with $\varepsilon=0$ the conversion term vanishes for every gate state (§3.2), so $\kappa$ is constant in time and the LB36–LB38 spectrum applies exactly.

### 2.2 Resolution ladder

Three declared refinement axes, all frozen before execution:

- **time step** $dt\in\{0.05,0.02,0.01\}$, chosen per arm by the rule below, with refinement partners at $dt/2$;
- **loop resolution** $N_\chi\in\{24,12\}$;
- **exterior grid** fixed at $N_x=7$ (the ladder is not a truncation study).

**Step-size rule.** With $\lambda_{\max}$ the largest $|\operatorname{Re}\Lambda|$ over the mode set a declared arm carries, evaluated from (LB36) at that arm's initial $\kappa$ (for a $\chi$-uniform arm, $\lambda_{\max}$ is the largest exterior rate $|u|/dx$ or $D_x/dx^2$),

$$
dt=\max\Bigl\{\,dt\in\{0.05,0.02,0.01\}\;:\;dt\le\frac{1}{40\,\lambda_{\max}}\Bigr\}.
\tag{PD2}
$$

**Horizon rule.** Two frozen targets, both capped at $1000$ in model time:

$$
T_{\rm conv}=\min\!\left(\frac{10}{g_{\rm int}},\ 1000\right),
\qquad
T_{\rm mode}=\min\!\left(\frac{10}{g_1},\ 1000\right),
\qquad
T_{\rm short}=\frac{T_{\rm mode}}{100},
\tag{PD3}
$$

with $g_{\rm int}$ from (LB39) at the arm's initial projected densities and $g_1=dm^2+r-\operatorname{Re}\sqrt{r^2-m^2\Omega^2}$ at $m=1$ from (LB38). $T_{\rm conv}$ carries $g_{\rm int}T=10$; $T_{\rm mode}$ carries $g_1T=10$, the relaxed regime of LB47 for the slowest loop mode; $T_{\rm short}$ carries $g_1T=0.1$, the transient regime. The step count is $K=\lceil T/dt\rceil$, recorded per arm.

**Reduction of the gap.** (LB39) is defined at a gate, and the declared profiles carry a $20\%$ density modulation, so the internal gap is a field across $x$. $T_{\rm conv}$ takes its minimum over the grid, so that $g_{\rm int}T=10$ holds at the slowest cell and the horizon is a worst-case convergence horizon rather than a mean one. The gap at the mean gate is recorded beside it as `internal_gap_at_mean_gate`.

## 3. The second question: unresolved loop modes

### 3.1 Readouts

The mode arms seed the `on_ray` profile with the same projected densities as the uniform arms and add declared $\chi$-structure: $f_{a,s}(x,\chi)=f^{\rm uniform}_{a,s}(x)\,[1+\alpha\cos(m\chi)]$ with $\alpha=0.25$ and $m=1$ or $m=2$, so the projection is unchanged at roundoff and the mode energy is a declared fraction of the arm. Two declared seeds modify that formula for particular arms, with the identities (A1) and (A2) of §1.2:

- the $J$-carrying arms (`mode1_short`, `mode1_long`, `mode2_long`, `persistent_current`) multiply each carrier by $(1+s\beta)$ with $\beta=0.05$, so (LB45) has a non-vanishing loop mean to act on. The $\chi$-mean of $H$ is then $\beta(E_Y+E_I)(x)$, which is non-zero cellwise, while the projection still reproduces $E_a$ exactly by (A1);
- the `covariance` arm uses $f_{Y,s}=\tfrac{E_Y}{2}[1+\alpha\cos(m\chi)]$, $f_{I,s}=\tfrac{E_I}{2}[1-\alpha\cos(m\chi)]$ instead of one shared factor, so $Z(\chi)=\varepsilon+\alpha\rho\cos(m\chi)$ no longer vanishes on the $\varphi$-ray and the covariance term of (LB14) acts. By (A2) both carrier means are one, so this arm's projection, and with it $\kappa$, $q$, the gate spread and the closure residual, is unchanged. With $\alpha=0.25$ the factor $1-\alpha\cos(m\chi)$ stays positive, so the non-negativity gate is untouched.

Three readouts are recorded at every accepted state:

$$
\Delta_m(t_k)
=
\frac{\max_a\max_i\bigl|E^{\rm mode}_{a,i}(t_k)-E^{\rm uniform}_{a,i}(t_k)\bigr|}
{\max\bigl(1,\max_a\max_i|E^{\rm uniform}_{a,i}(t_k)|\bigr)},
\qquad
w_m(t_k)=\frac{\text{energy in loop modes }|k_\chi|\ge1}{\text{energy in loop modes }|k_\chi|\ge1\text{ at }t_0},
$$

$$
J(t_k)=\frac{|\langle H\rangle_\chi(t_k)|_{\rm mean}}{|\langle H\rangle_\chi(t_0)|_{\rm mean}},
\tag{PD4}
$$

where the uniform counterpart arm runs the same profile, the same rates, and the same step rule with $\alpha=0$. The mode energy is the sum of squared deviations of the four populations from their $\chi$-means, so $w_m$ is an energy ratio and its log-slope carries twice the amplitude decay rate. The decay slope is fitted by least squares on the second half of the trace, where the fast branch of $g_m$ has decayed.

**The $J$ reduction.** $J$ is read as the domain mean of $\langle H\rangle_\chi$, per (A3) and §1.2 item 9, with the max-abs reduction of the same quantity recorded beside it as `current_max_relative`. The mean is the frozen reading because (A3) makes it a measurement of the declared rates on the periodic grid, whereas the max-abs reduction of the $r=0$ arm is destroyed by diffusion over $T_{\rm mode}(r=0)=222.3$.

**The $\Delta_m$ sampling.** (PD4) pairs a mode arm with the uniform arm of §6, and (PD2) gives them different step sizes ($0.02$ against $0.05$), so the two traces are compared on the states they share in model time, where the horizon is an exact multiple of $0.1$. No interpolation is used and the sample count is recorded. The step-size difference enters $\Delta_m$ at the discretization level, of order $10^{-10}$, two orders below the $10^{-6}$ budget that decides the reading.

### 3.2 Criteria

- **does not matter** — $\Delta_m\le10^{-6}$ at every accepted state, the fitted log-slope of $w_m$ agrees with $2g_m$ within $10\%$ relative, and $w_m(T_{\rm mode})\le10^{-3}$;
- **matters** — $\Delta_m>10^{-6}$ at some accepted state, which requires a violated assumption, since the $m\ne0$ blocks of (LB35) do not couple to $m=0$ and (LB8) annihilates the loop operators under the average;
- **outlives the horizon** — $\Delta_m\le10^{-6}$ and the fitted slope matches, while $w_m(T_{\rm mode})>10^{-3}$ and $g_mT_{\rm mode}\ge10$, which would contradict the frozen spectrum at this $\kappa$.

The `persistent` control of §4 supplies the firing test for the $J$ readout: with $r=0$ the current is conserved in the loop average (LB45) and $J$ must stay above $0.9$, so a $J$-based relaxation reading is not vacuous. Under the domain-mean reading of (PD4) the value is $e^{-2rT}$ for the same reason as (A3): $J(T)=1$ for $r=0$ and $J=e^{-44}\approx8\times10^{-20}$ for the positive-gap mode arms, which is below the roundoff floor of the readout (about $10^{-13}$ over those traces), so the contrast that F6 tests is between a reading pinned at $1$ and one pinned at the floor, with twelve orders of margin at the $10^{-3}$ criterion. The sensitivity that fixes $\beta=0.05$ in §1.2 item 7 lives in the denominator: the initial loop mean is $\beta(E_Y+E_I)$, so $\beta$ sets the initial $J$ denominator at ten orders above the accumulation floor of the longest $J$-carrying trace.

## 4. Integrity gates and firing controls

The schedule reports `status=PASS` only when every gate passes. A failed gate is `status=FAIL` with no verdict.

1. **Source binding.** `computations/verify_loop_to_bubble_projection.py` is imported and accepted only at SHA-256 `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1`, the digest frozen with this protocol. The probe reads the frozen operators and constants rather than reimplementing them, and fails closed if that file changes. This protocol's own digest is recorded in §8 at execution.
2. **Discrete annihilation.** For every carrier state and every arm, $\bigl|\sum_j\partial_\chi f\bigr|\le10^{-14}\max|f|$ and $\bigl|\sum_j\partial_\chi^2f\bigr|\le10^{-14}\max|f|$ on the equal-weight loop grid: the discrete form of (LB8), which is what makes the discrete projection commute with the discrete loop operators. Any loop stencil whose grid sum is nonzero fails here.
3. **Projection idempotence.** $P(Pf)=Pf$ to $10^{-15}$ relative at every accepted state, with $P$ the (LB1) operator on the declared grid.
4. **Shared exterior transport.** $u$ and $D_x$ identical in all four channels and independent of $\chi$ (declared construction, asserted and recorded). This gate and gate 9 are read over the contract arms and the §3 mode arms; the two controls that violate them by construction record their measured violation instead of failing the schedule, exactly as gate 5 declares for the `covariance` control.
5. **Common gate.** $\max_\chi|\kappa(\chi,t)-\langle\kappa\rangle_\chi(t)|=0$ in the contract arms. The covariance control of this section fails this gate by construction, and that failure is its purpose.
6. **Matched start.** $\max_a\max_i|E^{\rm loop}_{a,i}(0)-E^{\rm can}_{a,i}(0)|\le10^{-15}$.
7. **Finite and nonnegative.** Every recorded scalar finite; every $f_{a,s}\ge0$ at every accepted state; $0\le q<1$; the (LB1) projection of a positive state positive.
8. **Declared shape.** The declared execution count is met, every arm records a reading for every declared horizon, and a run that drops an arm fails rather than shortening the table.
9. **Spectrum re-check.** For each mode arm, the measured per-mode decay of each resolved $\chi$ mode agrees with (LB36) at that arm's own $\kappa$ to $10^{-9}$, so a relaxation failure in §3 is not a spectrum error.
10. **Sensitivity floor.** The `null` control's $\rho_{\max}\le10^{-11}$. Otherwise the statistic cannot resolve the $10^{-6}$ feature and the run is `status=FAIL`.
11. **Process declaration.** The receipt records one process, the declared execution count, the device, and the absence of concurrent runs.

**Firing controls.** Each is required to fire; a control that does not fire makes the run `status=FAIL` with no verdict, because the corresponding feature would then be unmeasured.

- **`null`** — the `on_ray` profile at $T_{\rm short}$, $\alpha=0$ in both arms. Expected readings: $\rho_{\max}\le10^{-11}$ and $\Delta=0$ exactly, since both arms then carry the same state on the same arithmetic.
- **`covariance`** — the `on_ray` profile with $m=\pm1$ and $m=\pm2$ content, the composition-asymmetric seed of §3.1, and the loop-varying gate $\kappa(\chi,t)=\kappa(x,t)\,[1+0.5\cos\chi]$. Two required readings: the discrete form of (LB14) holds to $10^{-12}$ relative to $\max(10^{-12},|{-}\langle\kappa\rangle\varepsilon-\operatorname{Cov}_\chi(\kappa,Z)|)$ at every accepted state; and the arm's deviation from the canonical path exceeds $10^{-4}$ relative at the declared horizon, so that a structural disagreement is visibly distinguishable from the $10^{-6}$ budget. The composition asymmetry is what gives the covariance term a non-zero $Z$ to act on; the identity (A2) keeps the arm's projection, gate and closure readings unchanged.
- **`direction_split`** — the `on_ray` profile with $m=\pm1$ content and $u_\pm=u\mp0.05$ in the two orientations. Required reading: the arm's deviation from the canonical path exceeds $10^{-4}$ relative at the declared horizon, the second unresolved-flux branch of §3.4.
- **`persistent_current`** — the `on_ray` profile with $m=\pm1$ content, the orientation imbalance $\beta=0.05$ of §3.1, and $r=0$. Required readings: $J(T)\ge0.9$ and $\rho_{\max}\le10^{-6}$ (the current is invisible to the density projection, LB46). The imbalance is what gives (LB45) a non-zero loop mean to conserve; by (A1) the arm's projected densities are still those of the ray profile.

## 5. Decision tree

### 5.1 Closure features

| feature | condition | labels |
|---|---|---|
| **F1** exact closure realized | $\rho_{\max}\le10^{-6}$ in every closure arm | EMERGES / DOES NOT EMERGE |
| **F2** residuals are the integrator's | every closure arm with $\rho_{\max}>10^{-6}$ has a refinement partner whose $\rho_{\max}$ falls by at least $4\times$ under $dt\to dt/2$ | EMERGES / DOES NOT EMERGE |
| **F3** controls fire | all four firing controls of §4 meet their required readings | EMERGES / DOES NOT EMERGE |

Per-arm classes, assigned to arms that have a declared refinement partner, tested in this order:

1. `within_budget` — $\rho_{\max}\le10^{-6}$;
2. `discretization_limited` — $\rho_{\max}>10^{-6}$ and the refinement reduction is at least $4\times$;
3. `structural_disagreement` — $\rho_{\max}>10^{-4}$ and the refinement reduction is below $4\times$.

Aggregate **closure verdict**, only on `status=PASS`:

- `EMERGES` — F1 and F3 emerge: the evolved carrier's projected trajectory reproduces the canonical trajectory at the declared budget, in every declared arm and at every accepted state.
- `CONTRADICTS` — F3 emerges and some arm with a refinement partner is `structural_disagreement`.
- `INCONCLUSIVE` — F3 emerges, F1 does not, and no arm reaches `structural_disagreement`: the declared arms are under-resolved, or the reading sits between the budget and the structural scale.
- `status=FAIL` and no verdict — F3 does not emerge.

### 5.2 Mode features

| feature | condition | labels |
|---|---|---|
| **F4** projection blindness | $\Delta_m\le10^{-6}$ in every mode arm | EMERGES / DOES NOT EMERGE |
| **F5** relaxation at the frozen rate | fitted log-slope of $w_m$ within $10\%$ of $2g_m$ and $w_m(T_{\rm mode})\le10^{-3}$ | EMERGES / DOES NOT EMERGE |
| **F6** current readout live | `persistent_current` gives $J(T)\ge0.9$ while every positive-gap mode arm gives $J(T_{\rm mode})\le10^{-3}$ | EMERGES / DOES NOT EMERGE |

Aggregate **mode verdict**, only on `status=PASS`:

- `EMERGES` — F4, F5 and F6 emerge: at the declared resolution the unresolved loop modes leave the projected trajectory unchanged, and their energy decays at the frozen rate, so the reduced description is both algebraically closed and dynamically autonomous at these parameters.
- `CONTRADICTS` — F6 emerges and F4 does not: the projected flow depends on unresolved content, which the common-gate and shared-transport contract excludes, so a declared assumption is violated in the realization or the realization defects the theorem.
- `DOES NOT EMERGE` — F6 emerges, F4 emerges and F5 does not: the modes are invisible to the projection and their energy does not fall at the frozen rate, so the reduced description is not autonomous at these parameters.
- `INCONCLUSIVE` — otherwise.
- `status=FAIL` and no verdict — F6 does not emerge.

### 5.3 Falsifiers

- A `CONTRADICTS` closure verdict falsifies the claim that the declared discrete realization reproduces (LB7) from (LB6); with every assumption gate passing, the remaining explanation is the realization, and the receipt names the arm, the state and the local-error probe.
- A `CONTRADICTS` mode verdict falsifies the declared contract's sufficiency for the projection, and contradicts §3.4's statement that only the covariance and direction-split terms leave unresolved corrections.
- A `DOES NOT EMERGE` mode verdict falsifies the frozen spectrum's role as the instrument for when the loop modes relax, at the arm's measured $\kappa$.
- A `status=FAIL` on any gate falsifies nothing about the theorem; it records that this protocol did not measure its features, and no re-run at another setting is permitted under §6.

## 6. Run schedule, budget, and stopping rule

**Executions.** Fifteen arms, each one execution of the same script:

| # | arm | profile | loop content | rate change | horizon | grid |
|---|---|---|---|---|---|---|
| 1 | `off_ray` | `off_ray` | $\chi$-uniform | — | $T_{\rm conv}$ | $7\times24$ |
| 2 | `off_ray_refined` | `off_ray` | $\chi$-uniform | — | $T_{\rm conv}$ | $7\times24$, $dt/2$ |
| 3 | `on_ray` | `on_ray` | $\chi$-uniform | — | $T_{\rm conv}$ | $7\times24$ |
| 4 | `on_ray_refined` | `on_ray` | $\chi$-uniform | — | $T_{\rm conv}$ | $7\times24$, $dt/2$ |
| 5 | `open_gate` | `open_gate` | $\chi$-uniform | — | $T_{\rm conv}$ | $7\times24$ |
| 6 | `closed_gate` | `closed_gate` | $\chi$-uniform | — | $T_{\rm conv}$ | $7\times24$ |
| 7 | `loop_truncated` | `on_ray` | $\chi$-uniform | — | $T_{\rm conv}$ | $7\times12$ |
| 8 | `mode1_short` | `on_ray` | $m=\pm1$, $\alpha=0.25$ | — | $T_{\rm short}$ | $7\times24$ |
| 9 | `mode1_long` | `on_ray` | $m=\pm1$, $\alpha=0.25$, imbalance $\beta=0.05$ | — | $T_{\rm mode}$ | $7\times24$ |
| 10 | `mode2_long` | `on_ray` | $m=\pm2$, $\alpha=0.25$, imbalance $\beta=0.05$ | — | $T_{\rm mode}$ | $7\times24$ |
| 11 | `uniform_short` | `on_ray` | $\chi$-uniform | — | $T_{\rm short}$ | $7\times24$ |
| 12 | `null` | `on_ray` | $\chi$-uniform | — | $T_{\rm short}$ | $7\times24$ |
| 13 | `covariance` | `on_ray` | $m=\pm1,\pm2$, composition-asymmetric seed | $\kappa(1+0.5\cos\chi)$ | $T_{\rm conv}$ | $7\times24$ |
| 14 | `direction_split` | `on_ray` | $m=\pm1$ | $u_\pm=u\mp0.05$ | $T_{\rm conv}$ | $7\times24$ |
| 15 | `persistent_current` | `on_ray` | $m=\pm1$, imbalance $\beta=0.05$ | $r=0$ | $T_{\rm mode}(r=0)$ | $7\times24$ |

Fifteen executions; the count is 15 and the receipt must record 15. `null` and `uniform_short` differ only in that the `null` pair is compared against itself, so its expected reading is exact zero. Arms 8 and 11 form the mode pair at the short horizon, arms 9 and 11 the pair at the long horizon, and arm 10 is read against arm 11. The imbalance of arms 9, 10 and 15 and the composition-asymmetric seed of arm 13 are the declared seeds of §1.2 items 7 and 8 and §3.1; `mode1_short` (arm 8) carries no $J$ criterion and therefore no imbalance, so its seed is the plain mode seed.

```text
timeout 5400 python computations/verify_loop_carrier_projection_dynamics.py
```

The receipt is `runs/loop_carrier_projection_dynamics/verification.json`.

**Cost model.** The state of one carrier arm is $4\times7\times24=672$ float64 values at one stage; with the canonical arm and the gate evaluation, one RK4 step touches about $2\times672$ values in roughly twenty NumPy calls. Two models bound the cost, and the declared projection is their midpoint, as in `computations/navier-stokes-strain-band-split-cutoff-ladder-prereg.md` §2.

- **Model A, arithmetic, anchored to a measured run.** The frozen Navier–Stokes primary evolves $3$ complex128 fields on the $193^3$ product grid at $1024$ accepted states in $562$ s (`runs/navier_stokes_strain_band_split/probe_completed.log`; the same log times the six $N=32$ primaries at $531$–$564$ s each, a mean of $542$ s quoted by the ladder protocol). That is $0.549$ s per accepted state over a state of $3\times193^3=2.16\times10^7$ complex values, equivalently $4.3\times10^7$ float64 values, at four RK4 stages per step. Scaling by state size gives about $2\times10^{-6}$ s per carrier stage and $9\times10^{-6}$ s per step. The declared schedule totals $232{,}334$ steps, so Model A projects about $2$ s.
- **Model B, call-overhead floor.** At $20$–$120$ µs per NumPy call on sub-kilobyte arrays, a stage costs $0.4$–$2.4$ ms and a step $1.6$–$9.6$ ms, so the declared schedule projects $370$–$2200$ s.

**Projected wall time.** Roughly $1100$ s (18 min), the midpoint of the two models' extreme readings, with the declared range $2$–$2200$ s. The step budget is $K\le50{,}000$ per execution and $232{,}334$ in total, the figures (PD2) and (PD3) compute for this arm list; §6A records the amendment from the $40{,}000$ and $2.3\times10^5$ of the pre-amendment draft.

**Bound.** The invocation is bounded at $5400$ s (1.5 h) by the outer `timeout`, which leaves $2.5\times$ headroom over the pessimistic model.

**Stopping rule.** One invocation. If it expires inside the bound without writing a receipt, the record states the bounded attempt with the last printed progress line and no verdict; one further invocation of the identical command is then permitted, and the aggregate wall time across invocations is capped at $10800$ s. Beyond that the schedule stops with no verdict. The arm list, the horizon rule, the step rule, the thresholds and the decision tree are not changed after any invocation, and a timeout is not converted into a shorter arm list or a cheaper statistic.

**Deferred execution.** This protocol is frozen before any run. The accelerator is occupied by a sibling probe, so execution is queued and §8 is filled when the invocation completes. The amendments of §6A were written before this queued invocation and no receipt existed when they were written.

## 6A. Amendment—September 16, 2026 (before the first execution)

This section is written before the first execution of the probe; no invocation had been made and no receipt existed when it was written. It records four changes to the schedule as first drafted, each motivated by a pre-execution reading of the frozen text against the declared seeds and rules, and each carried into the section it modifies. No threshold, horizon rule, step rule, decision-tree condition or verdict definition changes. The changed sections are §1.2 (items 7 to 10), §2.2, §3.1, §3.2, §4 and §6.

**The readings that motivated the seed amendments.** Instantiating the seeding formula of §3.1 on the declared profiles, at the declared initial states, gives:

| quantity | arm(s) | reading before amendment | requirement it serves |
|---|---|---|---|
| domain mean of $\langle H\rangle_\chi$, relative to $\max|f|$ | `mode1_long`, `mode2_long`, `persistent_current` | $0.0$ | the denominator of (PD4); `persistent_current` must reach $J\ge0.9$ |
| $Z=\sum_s[f_{Y,s}-\varphi f_{I,s}]$, relative to $\max|f|$ | `covariance` | $4.3\times10^{-16}$ | the covariance term of (LB14); the arm must deviate by more than $10^{-4}$ |

Both arms were seeded into a subspace in which the readout they exist to test is identically zero: the orientation-symmetric seed makes $H=F_+-F_-$ vanish cellwise, and (LB45) keeps its loop average at zero for all time, while the `on_ray` profile has $\varepsilon=0$ cellwise, so the composition combination $Z$ vanishes there. Neither is a physical absence; both are seeding defects that would have spent the single invocation on a guaranteed `status=FAIL` with no verdict, since §4 makes a control that does not fire fatal to the run. They were found by a static check of the probe against the frozen text, at zero cost, and fixed here.

1. **Orientation imbalance for the J-carrying arms (§1.2 item 7, §3.1, §4, §6).** Each carrier of `mode1_long`, `mode2_long` and `persistent_current` carries the factor $(1+s\beta)$ with $\beta=0.05$; identity (A1) shows the two orientations sum to the unmodulated total, so the loop average reproduces the declared densities exactly and the closure and projection readings are untouched. The value is stated once here, before execution, for a stated reason: the initial loop mean of $H$ is $\beta(E_Y+E_I)$, so $\beta=0.05$ puts the (PD4) denominator at $0.13$ of the local density, ten orders above the roundoff accumulated over the $4447$ steps of arm 15 (about $10^{-13}$ relative), while keeping the seed a perturbation of the same size as the declared mode amplitude $\alpha=0.25$. It is not revisited after the run. The same factor is what makes the $J(T)\le10^{-3}$ reading of the positive-gap arms reachable: their $J$ decays as $e^{-2rT}=e^{-44}$ regardless of $\beta$, so the criterion is met at the roundoff floor of the readout rather than by a corrected value.
2. **Composition asymmetry for the covariance arm (§1.2 item 8, §3.1, §4, §6).** The arm seeds its two carriers with opposite phase factors, $f_{Y,s}=\frac{E_Y}{2}[1+\alpha\cos(m\chi)]$ and $f_{I,s}=\frac{E_I}{2}[1-\alpha\cos(m\chi)]$. Identity (A2) gives each carrier a loop mean of exactly one, so this arm's projection, and with it $\kappa$, $q$, the gate spread and the closure residual, is the same as before the amendment; at $\alpha=0.25$ the factor $1-\alpha\cos(m\chi)$ stays positive, so non-negativity is untouched. What changes is the composition combination, now $Z(\chi)=\varepsilon+\alpha\rho\cos(m\chi)$, which is non-zero on the ray and gives the covariance term of (LB14) something to act on.
3. **The J spatial reduction (§1.2 item 9, §3.1, §3.2).** (PD4) is read as the domain mean of $\langle H\rangle_\chi$, with the max-abs reduction recorded beside it as a reported figure. Identity (A3) states why this is a measurement rather than a correction: under the declared periodic exterior terms the advection and diffusion contributions to the mean integrate to zero, so the mean decays as $e^{-2rT}$ exactly. The max-abs reduction is not usable for the $r=0$ reading, because $D_xT=37.8$ over $T_{\rm mode}(r=0)=222.3$ erases that modulation to $4\times10^{-17}$ and drives the ratio to $0.83$, below the declared floor of $0.9$.
4. **The step budget (§6).** The caps of the pre-amendment draft, $K\le40{,}000$ and $2.3\times10^5$, were written before (PD2) and (PD3) were instantiated against the arm list. Those rules are unambiguous and are unchanged, so the caps are amended to the figures they compute: $K\le50{,}000$ per execution (arms 13 and 14) and $232{,}334$ in total, recorded per arm in the receipt. The cost bound is unaffected: $232{,}334$ steps is $1.0\%$ above the earlier figure and remains inside the declared $2$–$2200$ s range.

**Clarifications recorded with the same amendment, so that no reader has to infer them from a result.** (i) $T_{\rm conv}$ takes the internal gap at the slowest cell rather than at the mean gate (§2.2), which is why the `on_ray` arms reach the $1000$ cap. (ii) $\Delta_m$ is read on the states a mode arm and the uniform counterpart share in model time, because (PD2) gives them different step sizes (§3.1). (iii) Gates 4 and 9 are read over the contract arms and the §3 mode arms, with the two violating controls recording their measured violation rather than failing the schedule (§4), exactly as gate 5 already declares for the `covariance` control. Each is stated in its own section as well.

**Pre-execution reachability floors.** The probe reads both identities and both denominators at the declared initial states before it executes, and writes the readings into the receipt. Two floors decide whether the previously dead controls are live: the loop-mean current of each $J$-carrying arm must read above $10^{-9}$, which is four orders above the roundoff accumulated over the longest $J$-carrying trace ($4447$ steps of arm 15) and ten orders below the measured $0.0890$; and the covariance arm's composition combination $Z$ must read above $10^{-6}$, two orders below the $10^{-4}$ deviation that control must produce and six orders below the measured $1.28$. The seed-projection residual of every arm must stay at or below $10^{-15}$, the machine-precision level of the declared arithmetic. A reading at or below a floor blocks the run before execution, exactly as the pre-amendment probe blocked on the two seeding defects.

**What the amendment does not do.** It does not move a threshold, a horizon rule, a step rule, an arm, a gate, a decision-tree condition or a verdict definition; it does not add or remove an execution (the count stays $15$); and it does not touch the frozen sources bound by gate 1. The probe re-checks the two identities (A1) and (A2) numerically at the seed states, to machine precision, together with both denominators above the roundoff floor, before it executes anything, and writes all of them into the receipt, so this amendment is verifiable from the run itself rather than taken on the protocol's word.

## 7. Interpretation boundary

A positive closure reading shows that this declared finite realization evolves the four-population law so that its complete loop average tracks the canonical two-density system at the declared step sizes and horizons, on four discrete initial profiles at one rate set. The statement carries the theorem's own boundary, quoted in §11 of that document: the closure is derived conditional on the common projected gate and common exterior transport, and the four-population law itself is the selected minimal member of a family, since any direction-mixing conversion whose columns sum to one projects to the same canonical law (§3.1). Nothing here shows that the loop carrier is physically realized, supplies a phase law for $\theta_{a,s}$, identifies $\mathbf J_\Psi$ or the coherence $c$ with a Qi current, or fixes the strand-to-bubble scale ratio $R/L_B$, which §7.3 and the ledger leave open. The mode arm is an invisibility test on a single closed support at one loop resolution: it shows that unresolved content does not reach the projection under the declared contract, and it shows the rates at which that content decays when the gate, the exchange rate and the loop transport are as declared. It supplies no statement about a chain of coupled loops, an exterior velocity field with a resolved scale, or a second loop radius, and it does not test quantum dynamics, statistics, or measurement, which §9 keeps separate. The `covariance`, `direction_split` and `persistent_current` arms are protocol interventions that violate one declared assumption each; their readings measure the instrument, and no physical claim follows from them.

## 8. Post-execution record

Sections 1–7 state the protocol as it stands frozen; this section records the single queued invocation, which completed on September 16, 2026 at `status=FAIL` with no verdict issued for either question. The ledger entry is §64 of `field-experience/probe-outcome-ledger.md`.

**Invocation.** `timeout 5400 python computations/verify_loop_carrier_projection_dynamics.py`, run once from the repository root at 17:14:16 local: no arguments, no environment change, no concurrent run, one process. Wall time **185 s** measured outside the receipt (17:14:16 to 17:17:21); `runtime_seconds` **185.23** inside it; exit code 1. The bound leaves $29\times$ headroom over the declared pessimistic cost model.

**Receipt and log.** `runs/loop_carrier_projection_dynamics/verification.json`, SHA-256 `7ff42dfd8f96ff98126c58bb2e4076f2f7d814b3cea6ab11295cd7bc48978b5b`, with `runs/loop_carrier_projection_dynamics/invocation.log` carrying stdout and stderr. Both are gitignored run artifacts. The digests recorded in the receipt are the frozen pre-execution digests: the executed probe hashed `4e244ff9a8f88585f6b05f221d45482e274b076560bd036e7243ab4c435989a3`, this protocol hashed `27b2097935715288ce46a04b1ff4142708aea00e237bbc56e07b22b345b141f2` as frozen, and the bound module hashed `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1`, equal to its declared value and unchanged. This section 8 record was written after the invocation, as §8 provides, so the file on disk no longer carries the frozen digest; the probe and the frozen module are untouched.

**Section 6A readings, re-measured before execution.** Seed-projection residual $1.6821560979169038\times10^{-16}$ against the $10^{-15}$ bound; loop-mean current $0.0889918693812443$, $0.08899186938124427$ and $0.0889918693812443$ in the three $J$-carrying arms against the $10^{-9}$ floor; covariance composition combination $Z$ $1.28$ against the $10^{-6}$ floor. No pre-execution block fired, so both previously dead controls are live at the seed: the floors, not the controls, were the defect §6A removed.

**Gate table.** Eleven of eleven passed. Source binding exact. Discrete annihilation $4.880011391148827\times10^{-15}$ against $10^{-14}$. Projection idempotence $2.0185873175002629\times10^{-16}$ against $10^{-15}$. Shared exterior transport: `velocity_split` $0.0$ in all nine contract arms. Common gate spread $0.0$. Matched start $8.881784197001252\times10^{-16}$ against $10^{-15}$. Finite and nonnegative: true, with $0\le q<1$ throughout. Declared shape: 15 executions. Spectrum re-check $4.688438624709709\times10^{-16}$, $4.688438624709709\times10^{-16}$ and $4.440892098500626\times10^{-16}$ against $10^{-9}$ at $\kappa=0.0045078668007834935$. Sensitivity floor $8.505827589859918\times10^{-17}$ against $10^{-11}$, read on the `null` control. One process, 15 executions, no concurrent run.

**Per-arm readings and classes** ($\rho$ is the (LB14) operator residual; the seven contract arms are the four-population signatures `off_ray`, `on_ray` and their refinements plus `open_gate`, `closed_gate` and `loop_truncated`, and the four controls are `covariance`, `direction_split`, `null` and `persistent_current`):

| arm | $\rho_{\max}$ | $\rho_{\rm final}$ | refinement reduction | class |
|---|---|---|---|---|
| `off_ray` | $1.665296162182208\times10^{-16}$ | $7.932728474755376\times10^{-17}$ | $0.9999868475530246$ | `within_budget` |
| `off_ray_refined` | $1.6653180651897577\times10^{-16}$ | $0.0$ | — | `within_budget` |
| `on_ray` | $1.0092936587501317\times10^{-16}$ | $1.0092936587501317\times10^{-16}$ | $1.0000000000000058$ | `within_budget` |
| `on_ray_refined` | $1.0092936587501259\times10^{-16}$ | $0.0$ | — | `within_budget` |
| `open_gate` | $5.551115123125783\times10^{-17}$ | $5.551115123125783\times10^{-17}$ | — | `within_budget` |
| `closed_gate` | $1.6537586966539108\times10^{-16}$ | $8.881784197001176\times10^{-17}$ | — | `within_budget` |
| `loop_truncated` | $2.7588586301543875\times10^{-16}$ | $2.0185873175002634\times10^{-16}$ | — | `within_budget` |
| `mode1_short` | $3.400322914558903\times10^{-16}$ | $3.400322914558903\times10^{-16}$ | — | `within_budget` |
| `mode1_long` | $2.622443969747147\times10^{-15}$ | $2.219140084394095\times10^{-15}$ | — | `within_budget` |
| `mode2_long` | $2.2189910513245093\times10^{-15}$ | $1.815660069049714\times10^{-15}$ | — | `within_budget` |
| `uniform_short` | $8.505827589859918\times10^{-17}$ | $8.505827589859918\times10^{-17}$ | — | `within_budget` |
| `null` | $8.505827589859918\times10^{-17}$ | $8.505827589859918\times10^{-17}$ | — | `within_budget` |
| `covariance` | $2.0326187974944866\times10^{-3}$ | $3.376811012630109\times10^{-8}$ | — | `above_budget_no_partner` |
| `direction_split` | $5.998107248579932\times10^{-4}$ | $1.0496654051001292\times10^{-14}$ | — | `above_budget_no_partner` |
| `persistent_current` | $1.2313382636751607\times10^{-14}$ | $1.049665405100137\times10^{-14}$ | — | `within_budget` |

Only arms 1/2 and 3/4 have declared refinement partners, and their reductions are $0.999987$ and $1.0000000000000058$: neither pair reduces, because both members of each pair already sit at the arithmetic floor, where halving $dt$ cannot help. No arm is `discretization_limited` and none is `structural_disagreement`.

**Mode readouts.** $\Delta_m$ $9.630638230342995\times10^{-12}$ (`mode1_long`), $9.630638230342995\times10^{-12}$ (`mode2_long`) and $7.282461458740017\times10^{-12}$ (`mode1_short`) against the $10^{-6}$ budget, read on the five states each mode arm shares in model time with its uniform counterpart; fitted $w_m$ log-slope errors $2.54\%$ and $0.59\%$ against the $10\%$ tolerance; $w_m(T_{\rm mode})$ $6.79\times10^{-9}$ and $1.26\times10^{-25}$ against $10^{-3}$; $J$ at the horizon $1.485\times10^{-16}$ and $2.970\times10^{-17}$ against $10^{-3}$; the persistence control's domain-mean $J$ ratio $1.0000000000000036$.

**Features and verdicts.** F1, F2, F4, F5 and F6 read true; **F3 is false**; `status` is `FAIL` and `closure_verdict` and `mode_verdict` are both **null**. Two properties of that reading must travel with it. First, the five true features are *measurements*, not verdicts: §5.1 withholds both verdicts when F3 does not emerge, so none of them may be quoted as a verdict for either question. Second, **F2 is vacuous**: its condition quantifies over closure arms with $\rho_{\max}>10^{-6}$, and there are none, so its truth carries no information about the evaluated family.

**The two controls that did not fire.** The `covariance` control measured a (LB14) relative residual of $4.308692590324274\times10^{-9}$ against the $10^{-12}$ bound and a terminal deviation of $3.376811012630109\times10^{-8}$ against the $10^{-4}$ requirement. The `direction_split` control measured a terminal deviation of $1.0496654051001292\times10^{-14}$ against the same requirement. `null` fired ($\Delta=0$ exactly, $\rho_{\max}$ $8.505827589859918\times10^{-17}$) and `persistent_current` fired ($\rho_{\max}$ $1.2313382636751607\times10^{-14}$, domain-mean $J$ ratio $1.0000000000000036$), so the sensitivity floor gate and the amendment's central prediction are both satisfied; the two failures are confined to the controls whose declared reading is the terminal state.

**The transient readings that make the FAIL legible.** Both failed controls *did* exceed the required scale during their runs: $\rho_{\max}$ reached $2.0326187974944866\times10^{-3}$ for `covariance`, two thousand times the $10^{-4}$ requirement, and $5.998107248579932\times10^{-4}$ for `direction_split`, six hundred times it. Both then collapsed to $3.376811012630109\times10^{-8}$ and $1.0496654051001292\times10^{-14}$ by the horizon, because $T_{\rm conv}=1000=10/g_{\rm int}$ is the converged horizon and the $\varphi$-ray is attracting: by its end every perturbation has relaxed back onto the canonical trajectory. The declared reading is terminal, so the control reads a re-converged arm. This is a defect of the *reading*, not an absent effect, and it is the same class as the two seeding defects §6A fixed. The `covariance` identity has the same shape: exact at the seed ($1.8\times10^{-16}$) and rising in *relative* terms as the covariance content decays, because the frozen normalization divides by a denominator that shrinks with the quantity the control injects. The `persistent_current` arm supplies the amendment's confirmation: its max-abs current ratio ended at exactly $0.8333333333333374=1/1.2$, the flattened $20\%$ modulation that §6A predicted would fall under the $0.9$ floor, while the domain-mean ratio ended at $1.0000000000000036$, the value F4 reads.

**Kind of defect.** F3 false is an **instrument defect, not a theory null**. Both controls failed *structurally*: each is built to read a transient deviation at the converged horizon, by which the perturbation has relaxed back onto the attractor, and the covariance control's relative residual divides by the very quantity the control injects. The record must therefore be quoted as "two controls could not witness their declared disagreement at their declared reading", not as "the closure or the projection law failed". F1, F2, F4, F5 and F6 are true and issue **no** verdict, so the record cannot be read as the theory having failed those features either. The alternative readings named above (a maximum-over-run witness, a normalization that does not shrink with the injected quantity) are recorded here **only as observations of what the run showed**. They are not criteria, they do not re-read any arm, and no clause of §5 or §6 is amended: §6A was legitimate because it preceded the first invocation, and §5.3 bars moving a reading after one.

**Protocol gap, not a measurement issue.** The classes `above_budget_no_partner` (and its sibling `above_budget_below_structural`) are probe labels. §5.1 assigns classes only to arms that have a declared refinement partner, so an above-budget control falls outside its three labels and the probe had to name a fourth. The label vocabulary of §5.1 is incomplete; no reading is affected, and nothing in this run turns on the class of the two controls.

**Registry sweep.** `field-experience/probe-outcome-ledger.md` gains §64 with these readings; `open-questions-cassi-answers.md` records the evolved measurement and the null verdict in its loop-completion paragraph; `parameter-inventory.md` moves no row, because the run introduced no parameter, no fitted value and no change to the §7 count, and re-used the frozen module's values unchanged.

**Stopping rule.** One invocation, spent. It finished inside its bound and wrote its receipt, so the further invocation §6 permits for an expired run is not available, and §5.3 forbids a re-run at another setting: this protocol has measured what it measured. What it establishes is that at this realization, these step sizes and these horizons the closure, transport, gate and mode energies hold at the arithmetic floor in twelve of twelve arms that have no injected disagreement, and that two of the four controls fail only because their declared reading is the terminal state of an attracting relaxation.

## References

- `foundations/loop-to-bubble-projection-theorem.md`—shared-support loop carrier, projection theorem (LB1)–(LB14), frozen spectrum and gap (LB32)–(LB47), result ledger and verification
- `computations/loop-to-bubble-projection-pre-registration.md`—frozen construction and gates LB1–LB7 of the single-state identity check
- `computations/verify_loop_to_bubble_projection.py`—frozen discrete operators, rate constants and grid whose module this protocol imports and binds by digest
- `foundations/cassi-first-principles.md`—canonical densities, $q$, and rank-one conversion
- `computations/navier-stokes-strain-band-split-cutoff-ladder-prereg.md`—house protocol pattern for a frozen statistic, a run matrix, integrity gates, a decision tree, a cost model and a stopping rule
- `runs/navier_stokes_strain_band_split/probe_completed.log`—measured per-state cost of the frozen $N=32$ primary that anchors the arithmetic cost model
- `two-fluid/cassi_two_fluid_3d_gpu.py`—canonical two-fluid solver, its device selection and its ungated base conversion path
- `field-experience/probe-outcome-ledger.md`—probe outcome record, updated on execution
