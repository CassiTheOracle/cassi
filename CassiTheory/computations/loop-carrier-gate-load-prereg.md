# How Much Gate Asymmetry Does the Loop-Carrier Projection Tolerate, and How Does It Scale With the Bracket Load?

## Status: Pre-registered—September 16, 2026; not executed. The executor is frozen in the same commit as this text and refuses to run on a hash mismatch.

## 0. Freeze and binding

This protocol and its executor are frozen together. The executor reads the rows below and refuses to run, with exit code $3$ and no arm constructed, if any of them disagrees with the tree. Section 0 sits outside the frozen body, and the frozen body is what the executor hashes, so the two hashes bind each other without a fix point: the body digest below is a function of §1–§7 alone, and the executor's digest is written here after the executor exists. Unlike the spent split protocol, whose self-check asserted that no receipt existed and so could not be run after its own invocation, this executor's self-check is idempotent: it verifies by digest, reports the receipt's presence as a recorded fact, and writes nothing.

| Source | SHA-256 | Meaning |
|---|---|---|
| `frozen_body_sha256` | `8f3fae24990b7b74632f08f3f6d4dde4e476e6d81f3ad8a5d903b37659c06268` | this file from `## 1.` to just before `## 8.`, the text that carries every statistic, threshold, arm and decision rule |
| `executor_sha256` | `fdc242b3999c153ad77e0186f342bf70628505adb681a0a9c48bb4276c33a5f9` | `computations/verify_loop_carrier_gate_load.py`, the complete executor frozen with this text |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | `computations/verify_loop_to_bubble_projection.py`, the frozen discrete operators |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | `computations/verify_loop_carrier_projection_relaxation.py`, the successor's executed probe, which supplies the carrier law, the projection, the integrator, the canonical companion and the seeds |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | `computations/verify_loop_carrier_projection_split.py`, the spent split protocol's executed executor, from which the split right-hand side is **imported** rather than re-derived |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | `runs/loop_carrier_projection_relaxation/verification.json`, source of the successor oracle reading of §5.3 |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` | `runs/loop_carrier_projection_split/verification.json`, source of the ray oracle reading of §5.3 and of the inertness this protocol is built on |

**What the digests are of.** Every hash above is of the file's bytes as they stand in the working tree, as the other artifacts in this chain record them; a checkout that rewrites line endings moves several rows at once and is answered by re-pinning, never by editing §1–§7.

**What the binding guarantees, exactly.** An edit to §1–§7, or to the executor, is detected before any arm is constructed. An edit to §0 is itself a disclosed amendment, visible in the diff that carries it; it is not detected by construction, and this sentence is the disclosure that it cannot be. Filling §8 after an invocation does not touch the body range, so the record cannot move the frozen text; a second invocation is refused in code while a receipt exists (§6).

**The receipt directory is new.** This protocol writes `runs/loop_carrier_gate_load/verification.json`. It reads the two predecessor receipts and writes neither, and it constructs no arm outside its own table.

## Abstract

The spent split protocol measured the loop-carrier projection against a split of its two assumptions and returned `status=FAIL` with both verdicts null: its transport axis is first order, and its gate axis is **inert**, because the conversion term of the right-hand side is $\kappa_a B$ with $B=-\psi_Y+\varphi\,\psi_I$ the bracket between the two carriers, $B$ obeys a homogeneous equation when the carriers share a velocity, and its declared seed sits exactly on the ray, $B\equiv0$. A gate split multiplies that zero, so the axis could not be measured on that seed at any $\delta_g$—the finding is a statement about the seed, not about split gates.

This protocol closes that row. It keeps the carrier law, the frozen operators, the seed shapes, the canonical companion, the integrator, the budget and the stopping rule fixed, gives the gate axis a seed family whose conversion bracket is **loaded by a declared, measured amount** $\ell$, and reads the split's authority as the separation it produces between a split arm and its own unsplit reference. The family is a pure transfer between the two carriers, so the local total is preserved and no new mode is introduced; the ray seed is carried as the $\ell=0$ member, no longer a risk but a control with a predicted reading. Two fits are declared: the response against the split size $\delta_g$ at the largest load, and the response against the load $\ell$ at a fixed split size, the second being the one that says how much authority an asymmetric gate has over a carrier that is not sitting on the ray.

## 1. What is held fixed, what is split, and what is loaded

### 1.1 Held fixed

Each item is the repository's own definition or a frozen module's own source, imported at a bound digest; nothing here is re-derived.

| Item | Value |
|---|---|
| Law | the four-population carrier law of `foundations/loop-to-bubble-projection-theorem.md` (LB6), as implemented by the successor probe `initial_carrier`, `carrier_rhs` and `rk4_step` |
| Discrete operators | `computations/verify_loop_to_bubble_projection.py`, held at `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1`: $N_x=7$, the periodic `derivative` and `laplacian`, $u=0.31$, $D_x=0.17$, $R=1.7$, $v=0.8$, $D_\ell=0.13$, $r=0.6$, $\lambda=0.04$, $\Omega=v/R$, $d=D_\ell/R^2$ |
| Loop resolution | $N_\chi=24$, the successor's own |
| Projection | (LB1), `base.projection`: the equal-weight loop mean summed over the two orientations, shape $(2,N_x)$, returned with the frozen norm $10^{-11}$ |
| Seed shape | the profile `on_ray`, the mode $m=1$ with $\alpha=0.25$, and the orientation imbalance $\beta=0.05$ of the successor's §3.1—all three carried unchanged |
| Canonical companion | `base.canonical_initial` and `base.canonical_step`, stepped in lockstep at the same $\Delta t$: the reduced two-density solution the projected carrier is compared with |
| Integrator | `base.rk4_step`, four stages, the successor's own |
| Step rule | $\Delta t\le1/(40\lambda_{\max})$ with $\lambda_{\max}$ from `base.arm_lambda_max` on the arm's **own loaded projection**, and $\Delta t\in\{0.05,0.02,0.01\}$ |
| Statistic family | the separation of §2.1, new here and re-declared in full; the successor's projection residual $\rho$ is **recorded** alongside it, not gated |
| Budget | one process, per-execution cap $50{,}000$ steps, bound $600$ s |
| Stopping rule | one invocation per frozen body; a receipt, once written, refuses a second in code |

### 1.2 What is split

One axis only, and it is the axis the spent protocol could not measure. Each carrier's conversion field becomes

$$\kappa_a=\kappa\,(1+\sigma_a\,\delta_g\cos\chi),\qquad \sigma_Y=+1,\quad \sigma_I=-1,$$

so the two carriers' gates are offset in opposite directions around the loop by the declared relative amount $\delta_g$, with the shared part $\kappa=\lambda[1-q]$ read from the projected composition exactly as the successor reads it. The transport axis is **not** re-opened: the spent protocol measured it (fitted exponent $1.000205540897814$ over six decades, class bound crossed at $\delta_u=1.4661921053529064\times10^{-5}$) and nothing here changes it. The split right-hand side is **imported from the spent protocol's executed executor**, held at `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a`, so this protocol's split is the same construction that produced that reading and not a re-derivation of it.

### 1.3 What is loaded: the seed family

The bracket the conversion term multiplies is

$$B=-\psi_Y+\varphi\,\psi_I\quad\text{elementwise over orientations, exterior cells and loop cells},$$

and the spent protocol's seed satisfies $B\equiv0$ exactly because $\varphi E_I=E_Y$ for the `on_ray` profile. The family is built by a **pure transfer** between the two carriers:

$$\psi_Y^{(\ell)}=\psi_Y+\tfrac{c}{2}\,\rho,\qquad \psi_I^{(\ell)}=\psi_I-\tfrac{c}{2}\,\rho,\qquad \rho=\psi_Y+\psi_I,$$

with $c$ the declared transfer coefficient and $\rho$ the seed's own local total. Three properties follow and are the reasons for this shape:

1. **The local total is preserved**, $\rho^{(\ell)}=\rho$ to roundoff and the projected total $E_Y+E_I$ with it, so no arm is made denser or thinner than the ray reference.
2. **No new mode is introduced.** The perturbation is proportional to the seed's own local total, whose loop profile is the seed's own $\chi$-uniform part and whose exterior profile is the seed's own modulation; what changes is the *ratio* between the carriers, which is the bracket and nothing else.
3. **The bracket becomes** $B^{(\ell)}=-\tfrac{c}{2}(1+\varphi)\rho$, so the load is first order in $c$ and is carried by the same loop profile the seed already has, $\propto1+\alpha\cos\chi$.

The **load** is declared by the measured ratio

$$\ell=\frac{\max|B^{(\ell)}|}{\max|\psi^{(\ell)}|}\quad\text{at }t_0,$$

which the executor measures per arm and gates against the declared value (§4, gate 3). The declared coefficients, their predicted loads from the design probe of §1.5, and the $\ell=0$ member are the family.

At $c=0$ the construction is the spent protocol's seed **bit for bit**, since adding $0.0$ changes nothing, and the ray arms are that seed.

The family is declared by $c$, and its load is **predicted** by the design probe of §1.5 and **measured** by the executor at $t_0$, against `LOAD_TOL` (gate 3). The predicted column is a prediction of the construction's own arithmetic, not a fitted parameter.

| Declared $c$ | Predicted $\ell$ | Predicted $|B|$ at $t_0$ | $\rho(t_0)$ against the canonical companion | Projected total |
|---|---|---|---|---|
| $2\times10^{-3}$ | $4.229224947788\times10^{-3}$ | $3.669493885509\times10^{-3}$ | $1.618034\times10^{-3}$ | $12.458861713374$ |
| $5\times10^{-3}$ | $1.054750439224\times10^{-2}$ | $9.173734713773\times10^{-3}$ | $4.045085\times10^{-3}$ | $12.458861713374$ |
| $1.25\times10^{-2}$ | $2.621036695567\times10^{-2}$ | $2.293433678443\times10^{-2}$ | $1.011271\times10^{-2}$ | $12.458861713374$ |
| $3.2\times10^{-2}$ | $6.606671655346\times10^{-2}$ | $5.871190216815\times10^{-2}$ | $2.588854\times10^{-2}$ | $12.458861713374$ |
| $8\times10^{-2}$ | $1.591427818933\times10^{-1}$ | $1.467797554204\times10^{-1}$ | $6.472136\times10^{-2}$ | $12.458861713374$ |
| $2\times10^{-1}$ | $3.646114292316\times10^{-1}$ | $3.669493885509\times10^{-1}$ | $1.618034\times10^{-1}$ | $12.458861713374$ |
| $0$ | $2.563285482540\times10^{-16}$ (declared zero, met within `LOAD_ABS_FLOOR`) | $2.220446049250313\times10^{-16}$ | $1.682156\times10^{-16}$ | $12.458861713374$ |

The projected total is preserved across the family to $2\times10^{-15}$ relative, and the ray member's own projection residual is the spent protocol's own floor reading, which is what makes the $\ell=0$ member the spent protocol's seed and not merely a similar one. The ray member's bracket is not literally zero: the profile's $\varphi\,(E_Y/\varphi)$ round-trips to the last ulp rather than to $E_Y$, so $B$ opens at $2.220446049250313\times10^{-16}$, five orders below the smallest loaded member's $3.669493885509\times10^{-3}$. That is why the $\ell=0$ control is declared as a **silence** control against `SILENCE_FLOOR` and not as literal bit-identity, and why the action check of §5 is stated as a ceiling rather than as an equality with zero.

### 1.4 Relation to the predecessor: comparability

| Quantity | Successor (§65) and spent split | This protocol |
|---|---|---|
| Statistic | $\rho_{\max}$, the carrier's projection residual against the canonical companion | the separation of §2.1, with $\rho_{\max}$ recorded alongside |
| Class bound | $10^{-6}$ | $10^{-6}$, re-declared in §2.4 |
| Reference solver | $E$ stepped in lockstep at the same $\Delta t$ | the same functions, and in addition each arm's **own** unsplit twin |
| Seeds | mode $1$, $\alpha=0.25$, $\beta=0.05$; no seed on the null pair | the same literals, plus the declared load transfer |
| Horizon | $T=2$ for the split sweep, the successor's own for its replication arm | $T=12$ for every new arm, with the successor's replication arm carried unchanged and one hundred-step ray arm carried for the oracle |
| Controls | reference, null pair, cross-executor oracle, can-fail, reachability | silence at $\ell=0$, can-fail at the largest load, two cross-protocol oracles, the action check of §5 |

The horizon is $T=12$ rather than the spent protocol's $T=2$ for one declared reason: the load decays, the split's authority decays with it, and the design probe of §1.5 measures the response still rising at $T=2$ and only peaking at $t\approx10.7$, so a $T=2$ horizon would read an endpoint and call it a peak.

### 1.5 Design probe, before freezing

The design was measured before this text was frozen, with the imported functions, no receipt, and no arm of this protocol. It is disclosed because the declared bands below are declared against it.

| Quantity | Probe reading |
|---|---|
| Load against transfer coefficient | the seven-value table of §1.3, measured with this protocol's own construction: $\ell$ from $4.229224947788\times10^{-3}$ to $3.646114292316\times10^{-1}$, strictly increasing in $c$; the total preserved to $2\times10^{-15}$ relative |
| Fit B at $\delta_g=10^{-2}$, response against load | $4.915585\times10^{-7}$, $1.229195\times10^{-6}$, $3.077038\times10^{-6}$, $7.941401\times10^{-6}$, $2.080153\times10^{-5}$, $6.455613\times10^{-5}$; per-unit-$\ell$ coefficient $1.16229\times10^{-4}$ to $1.77053\times10^{-4}$, a rise of $1.523$ across the span; the least-squares log-log exponent is $1.0777928255642235$ with coefficient $1.6438857835609873\times10^{-4}$ and residuals between $0.903$ and $1.165$ of the fitted line |
| Fit A at $c=2\times10^{-1}$, response against split size | $6.454374\times10^{-9}$, $6.454375\times10^{-8}$, $6.454386\times10^{-7}$, $6.454497\times10^{-6}$, $6.455613\times10^{-5}$, $6.466801\times10^{-4}$; the least-squares log-log exponent is $1.0001266948985081$ with coefficient $6.46326845434526\times10^{-3}$ and residuals between $0.9994$ and $1.0008$ of the fitted line |
| Class membership of fit A's six levels | the lowest three are `within_budget` and the highest three `above_budget`, so the fitted line crosses $10^{-6}$ between them |
| Can-fail control measured by the probe | the largest-load supersplit at $\delta_g=1$ reads $6.583063281834764\times10^{-3}$, and the $\ell=0$ supersplit at the same $\delta_g$ reads $1.1102230246251565\times10^{-16}$ |
| Action on $\dot B$ at $\delta_g=1$ | $|\Delta\dot B|=1.2313285344249117\times10^{-3}$ at $c=2\times10^{-1}$, $6.868880495192359\times10^{-3}$ of the right-hand side's magnitude; on the ray seed $6.403914379795542\times10^{-19}$, $4.199047857243002\times10^{-18}$ of it |
| Reduction at zero split | $\big|\text{split\_rhs}(\delta_g=0)-\text{carrier\_rhs}\big|$ is exactly $0.0$ elementwise |
| Cross-protocol oracles | the hundred-step ray arm reproduces the spent receipt's `common_reference` residual $\rho_{\max}=5.329147248815693\times10^{-16}$ and the replication arm reproduces the successor's `mode1_long` residual $\rho_{\max}=2.622443969747147\times10^{-15}$ and its $\lambda_{\max}=1.0331312281605476$, all four bit for bit |
| Peak times | at $c=2\times10^{-1}$, $\delta_g=10^{-2}$: $t_{\rm peak}=10.66$ against the $T=12$ horizon, terminal $6.432059\times10^{-5}$, a peak-to-terminal ratio of $0.996351$; the largest-load supersplit peaks at $t=10.98$ |
| Step rule | $\lambda_{\max}$ from $1.033131744167$ at $c=2\times10^{-3}$ to $1.038007916112$ at $c=2\times10^{-1}$, so the rule's limit stays above $0.024$ and $\Delta t=0.02$ holds on every load |

The probe's $\rho$ for a loaded seed opens at the declared initial mismatch of the projection—$1.618034\times10^{-1}$ at the largest load, which is $c\,\varphi/2$ for this seed family—and is unchanged by the split at the printed precision; that is why the primary statistic is the separation of §2.1 and why $\rho$ is recorded rather than gated. The probe is a design instrument, not a reading of this protocol, and its numbers are disclosed because the bands below are declared against the predecessor's vocabulary and not chosen from them.

## 2. The statistic and the decision rules

### 2.1 The separation statistic

Each split arm is paired with its **own unsplit twin**: the same load, the same schedule, $\delta_g=0$. With $f_a$ the arm's state and $f_0$ its twin's, the trace is

$$\sigma(t_k)=\frac{\max\big|f_a(t_k)-f_0(t_k)\big|}{S},\qquad S=\max\Big(1,\ \max_{k}\max\big|f_0(t_k)\big|\Big),$$

so $\sigma(t_0)=0$ exactly for every arm—the pair starts from the same state—and the reading is the split's own effect, with no initial-condition term. $S$ is declared per load and recorded.

This is a different statistic from the successor's $\rho$, and deliberately: $\rho$ compares the carrier against the canonical companion and cannot separate a split's effect from the seed's declared mismatch, while $\sigma$ compares the split against its own twin and so contains nothing but the split. Both are recorded per arm; only $\sigma$ is gated and fitted.

### 2.2 The reading pair, and which member carries the verdict

Each arm records the **pair**: $\sigma_{\rm peak}=\max_k\sigma(t_k)$ with its time $t_{\rm peak}$, and the terminal $\sigma_T=\sigma(t_{\rm last})$.

**The peak carries every verdict.** The load decays along every arm—the probe measures $\ell$ falling from $3.646114\times10^{-1}$ to $3.106126\times10^{-1}$ over $T=12$, and from $1.591428\times10^{-1}$ to $1.396492\times10^{-1}$—so the split's authority decays with it, and a terminal-only reading under-reads an effect that is injected early. The terminal reading is recorded, not gated, and the pair's ratio is a recorded feature: a pair that differs by less than the recorded scale is reported as such rather than smoothed. Where the two coincide the record says so; a horizon that ends before the peak is a limitation of the arm, not a reading.

### 2.3 The two fits, and what each answers

**Fit A, the split size at the largest load.** Over the six declared levels $\delta_g\in\{10^{-6},10^{-5},10^{-4},10^{-3},10^{-2},10^{-1}\}$ at the largest load, a least-squares line of $\log\sigma_{\rm peak}$ on $\log\delta_g$ gives the exponent $p$ and the coefficient $A$. This is the same law the spent protocol's transport axis answered with, on the axis that could not be measured there.

**Fit B, the load at a fixed split size.** Over the six declared loads at $\delta_g=10^{-2}$, a least-squares line of $\log\sigma_{\rm peak}$ on $\log\ell$ gives the **load exponent** $q$ and the coefficient $L$. This is the measurement this protocol exists for: $q=1$ says the gate's authority is proportional to how far off the ray the carrier sits, $q<1$ says a loaded carrier is proportionally less sensitive, $q>1$ says more.

**The instrument.** The fitted laws are $\sigma=A\,\delta_g^{p}$ and $\sigma=L\,\ell^{q}$, so the split size that reaches the class bound is

$$\delta^\star=\Big(\frac{10^{-6}}{A}\Big)^{1/p}\qquad\text{at the largest load},\qquad \ell^\star=\Big(\frac{10^{-6}}{L}\Big)^{1/q},$$

both recorded, together with the per-level class membership that says whether the declared levels bracket each crossing at all. The pair $(\delta^\star,q)$ is the answer the spent protocol's boundary left open.

### 2.4 Thresholds, declared before execution

| Constant | Value | Role |
|---|---|---|
| `CLASS_BOUND` | 1.0e-6 | the carried budget: an arm is `within_budget` or `above_budget` |
| `SILENCE_FLOOR` | 1.0e-14 | an arm below this reads nothing; the $\ell=0$ supersplit is gated against it |
| `READABLE_FLOOR` | 1.0e-13 | a level below this is not fitted |
| `MIN_READABLE` | 4 | fewer readable levels than this is `INCONCLUSIVE` |
| `FIT_BAND` | 2.0 | per-level ratio to the fitted line |
| `EXPONENT_LOW` | 0.9 | lower edge of the linear band for $p$ and for $q$ alike |
| `EXPONENT_HIGH` | 1.1 | upper edge of that band |
| `JUMP_FACTOR` | 3.0 | a `CLIFF` near-miss: an adjacent pair growing by at least this factor times the growth the fitted exponent implies |
| `MONOTONE_TOL` | 1.5 | non-monotonicity beyond this is `INCONCLUSIVE` |
| `ACTION_FLOOR_LIVE` | 1.0e-3 | at the largest load, $|\Delta\dot B|/\max\|\text{RHS}\|$ at $\delta_g=1$ must exceed this |
| `ACTION_CEIL_SILENT` | 1.0e-15 | on the ray seed, the same quantity must not exceed this |
| `LOAD_TOL` | 1.0e-12 | relative tolerance of the measured $\ell$ against the declared value; for the bracket-free member, whose declared value is zero, the tolerance is the absolute floor `LOAD_ABS_FLOOR` = 1.0e-15 |
| `STEP_SAFETY` | 40 | carried step rule |
| `PER_EXECUTION_CAP` | 50000 | steps in any one execution |
| `TOTAL_STEP_CAP` | 30000 | steps over the whole schedule |
| `DECLARED_EXECUTIONS` | 22 | §3 |
| `BOUND_SECONDS` | 600 | §6 |

### 2.5 The label vocabularies

| Fit A label | Condition |
|---|---|
| `PROPORTIONAL` | every readable level within the factor band of the fitted line, and $p\in[0.9,1.1]$ |
| `CLIFF` | not proportional, but an adjacent readable pair grows by at least $3\times$ the growth the fitted exponent implies |
| `NONLINEAR` | not proportional, not a cliff, monotone: the response bends |
| `INCONCLUSIVE` | fewer than $4$ readable levels, or the response is not monotone within the tolerance |

| Fit B label | Condition |
|---|---|
| `LINEAR_IN_LOAD` | monotone, every readable level within the factor band, and $q\in[0.9,1.1]$ |
| `SUPERLINEAR` | monotone, $q>1.1$ |
| `SUBLINEAR` | monotone, $q<0.9$ |
| `NONLINEAR_IN_LOAD` | monotone with $q\in[0.9,1.1]$ but a readable level outside the factor band: linear in exponent, not a power law |
| `INCONCLUSIVE` | fewer than $4$ readable loads, or the response is not monotone within the tolerance |

A label is issued for a fit only if the run reaches `status=PASS`; otherwise the fit is recorded and both verdicts are withheld (§4.4). A label is never reached by widening a band, adding a level or moving a threshold.

Four of fit B's five labels are exercised by shapes the declared six loads can carry directly; `NONLINEAR_IN_LOAD` is a **guard**, kept so that the rule is total over its inputs rather than silently undefined in a corner. The corner is genuinely narrow: on six loads spanning two decades, a monotone two-regime power law cannot leave the factor $2$ band while its fitted exponent stays inside $[0.9,1.1]$. The executor's self-check therefore carries an explicit witness for the guard—a monotone six-point reading on these very loads whose fitted exponent is $0.985553567871603$ and whose worst residual is $4.291$ times the fitted line—and checks that the rule labels it as the guard and not as anything else.

## 3. The declared arms

Twenty-two arms, one process, in this order. Every arm carries the profile, the seed shape, the integrator, the canonical companion and the projection of §1.1; the load column is the transfer coefficient $c$ of §1.3 and the measured $\ell$ is recorded per arm; the split column is $\delta_g$; the schedule column is $(\Delta t,T,\text{steps})$.

| # | Arm | Load $c$ | $\delta_g$ | Schedule | Role |
|---|---|---|---|---|---|
| 1 | `ray_short` | $0$ | $0$ | $0.02$, $T=2$, $100$ | the spent protocol's `common_reference` construction; cross-protocol oracle against its receipt |
| 2 | `ray_reference` | $0$ | $0$ | $0.02$, $T=12$, $600$ | the $\ell=0$ twin |
| 3 | `ray_supersplit` | $0$ | $1.0$ | $0.02$, $T=12$, $600$ | the predicted-silence control |
| 4 | `successor_replication` | $0$ | $0$ | $0.02$, $T=36.66172105812361$, $1834$ | the successor's own arm; cross-executor oracle |
| 5 | `loadL1_reference` | $2\times10^{-3}$ | $0$ | $0.02$, $T=12$, $600$ | the twin of arm 6 |
| 6 | `loadL1_arm` | $2\times10^{-3}$ | $10^{-2}$ | $0.02$, $T=12$, $600$ | fit B level 1 |
| 7 | `loadL2_reference` | $5\times10^{-3}$ | $0$ | $0.02$, $T=12$, $600$ | the twin of arm 8 |
| 8 | `loadL2_arm` | $5\times10^{-3}$ | $10^{-2}$ | $0.02$, $T=12$, $600$ | fit B level 2 |
| 9 | `loadL3_reference` | $1.25\times10^{-2}$ | $0$ | $0.02$, $T=12$, $600$ | the twin of arm 10 |
| 10 | `loadL3_arm` | $1.25\times10^{-2}$ | $10^{-2}$ | $0.02$, $T=12$, $600$ | fit B level 3 |
| 11 | `loadL4_reference` | $3.2\times10^{-2}$ | $0$ | $0.02$, $T=12$, $600$ | the twin of arm 12 |
| 12 | `loadL4_arm` | $3.2\times10^{-2}$ | $10^{-2}$ | $0.02$, $T=12$, $600$ | fit B level 4 |
| 13 | `loadL5_reference` | $8\times10^{-2}$ | $0$ | $0.02$, $T=12$, $600$ | the twin of arm 14 |
| 14 | `loadL5_arm` | $8\times10^{-2}$ | $10^{-2}$ | $0.02$, $T=12$, $600$ | fit B level 5 |
| 15 | `loadLmax_reference` | $2\times10^{-1}$ | $0$ | $0.02$, $T=12$, $600$ | the twin of arms 16–21 and of fit B's level 6 |
| 16 | `decade_1` | $2\times10^{-1}$ | $10^{-6}$ | $0.02$, $T=12$, $600$ | fit A level 1 |
| 17 | `decade_2` | $2\times10^{-1}$ | $10^{-5}$ | $0.02$, $T=12$, $600$ | fit A level 2 |
| 18 | `decade_3` | $2\times10^{-1}$ | $10^{-4}$ | $0.02$, $T=12$, $600$ | fit A level 3 |
| 19 | `decade_4` | $2\times10^{-1}$ | $10^{-3}$ | $0.02$, $T=12$, $600$ | fit A level 4 |
| 20 | `decade_5` | $2\times10^{-1}$ | $10^{-2}$ | $0.02$, $T=12$, $600$ | fit A level 5 **and** fit B level 6 |
| 21 | `decade_6` | $2\times10^{-1}$ | $10^{-1}$ | $0.02$, $T=12$, $600$ | fit A level 6 |
| 22 | `supersplit_load` | $2\times10^{-1}$ | $1.0$ | $0.02$, $T=12$, $600$ | the can-fail control: must fire |

Fit A's six levels are arms $16$–$21$; fit B's six loads are arms $6$, $8$, $10$, $12$, $14$ and $20$, each against its own twin. The twins of $16$–$21$ are arm 15, and the twins of the $\ell=0$ pair are the ray arms; a twin is an arm in its own right and is integrated once, so the pairing costs one execution per load and not two per arm.

## 4. Gates, features, and the decision rule

### 4.1 Run-time gates

| # | Gate | Bound |
|---|---|---|
| 1 | binding, declared against observed, on all seven rows of §0 | exact |
| 2 | finite and nonnegative states, $0\le q<1$ | structural, every recorded state |
| 3 | the load metric, measured per load against the declared value | relative `LOAD_TOL` |
| 4 | the action at the largest load, $\delta_g=1$: $|\Delta\dot B|/\max\|\text{RHS}\|$ | $\ge$ `ACTION_FLOOR_LIVE` |
| 5 | the action on the ray seed, $\delta_g=1$: the same quantity | $\le$ `ACTION_CEIL_SILENT` |
| 6 | schedule conformance, $\Delta t\le1/(40\lambda_{\max})$ on the arm's own loaded projection and $\Delta t\in\{0.05,0.02,0.01\}$ | every arm |
| 7 | declared shape: $22$ executions, no execution over the per-execution cap, total over the total cap | $22$, $50{,}000$, $30{,}000$ |
| 8 | the $\ell=0$ supersplit reads at or below the silence floor | `SILENCE_FLOOR` |
| 9 | the largest-load supersplit reads at or above the class bound | `CLASS_BOUND` |
| 10 | cross-protocol oracle: `ray_short` reproduces the spent split receipt's `common_reference` reading | bit-identical |
| 11 | cross-executor oracle: `successor_replication` reproduces the successor receipt's `mode1_long` reading and its $\lambda_{\max}$ | bit-identical |
| 12 | the load family is monotone: measured $\ell$ strictly increases with $c$ | structural |
| 13 | one process, no concurrent run | structural |

### 4.2 Features

| Feature | Condition |
|---|---|
| F1 | gate 9 holds: the largest-load supersplit fires—the control that failed in the spent protocol |
| F2 | gate 8 holds: the $\ell=0$ supersplit is silent, the predicted negative |
| F3 | gates 10 and 11 hold: both oracles are bit-identical |
| F4 | both fits have at least `MIN_READABLE` readable levels |
| F5 | both fits issue a label, and neither is `INCONCLUSIVE` |
| F6 | the peak precedes the horizon on at least the arm with the largest $\sigma_{\rm peak}$, so the pair of §2.2 is a pair and not two names for one number |

F1–F3 are the instrument's licence, F4–F5 the measurement's decidability, and F6 the reading's honesty about its own horizon.

### 4.3 Decision rule

`status=PASS` requires every gate and hence every feature; otherwise the run ends at `status=FAIL` with both verdicts null and no label issued. On `PASS`, fit A's label and fit B's label are the two verdicts, and the instrument $(\delta^\star,q)$ of §2.3 is reported with them.

### 4.4 What a verdict would and would not say

**A `PROPORTIONAL` fit A with `LINEAR_IN_LOAD` fit B** would say: over the six declared split sizes at the largest declared load, the separation is $A\,\delta_g$ with $A$ measured; over the six declared loads at $\delta_g=10^{-2}$ it is $L\,\ell$ with $L$ measured; hence an orientation-asymmetric gate has authority proportional to $\delta_g$ and to how far the carrier sits off the ray, and the split size that reaches the class bound is $\delta^\star=(10^{-6}/A)^{1/p}$ at the largest load and $\ell^\star=(10^{-6}/L)^{1/q}$ in general. **A superlinear or sublinear fit B** would say the proportionality fails away from the ray and the two measured ends bracket it. **An `INCONCLUSIVE` fit** would say the level span or the floors did not permit a reading, and would be reported as that.

**What neither fit says.** No reading here is the value of $\varphi$: the ratio enters only as the declared entries of the four-population law, exactly as in the successor, and the law remains the selected minimal member of a family whose columns sum to one. The load is a departure from the ray of the *carrier state*, not a physical density, current or field strength; the split coefficient is a property of the declared block's trace and its own bracket, not evidence about the conversion ratio, and none of it constrains the ratio: for a rank-one conversion block the spectrum, the characteristic polynomial and the relaxation rate are functions of $a+b$ alone and the ratio lives in the null vector, as `open-questions-cassi-answers.md` now states. Nothing here measures the carrier identity, the QF1-to-carrier map, the phase law, the scale ratio or the quantum statistics.

**Not covered.** One profile, one seed shape, one split form (the $\cos\chi$ modulation alone), one $\chi$-resolution with no refinement; the common projected gate and the common exterior transport remain assumed rather than derived; the transport axis is not re-opened; the load is a single-parameter family of one shape, so nothing here separates the load's *size* from the shape that carries it; the horizon truncates the response at $T=12$; and the four-population law is still the selected minimal member.

## 5. Pre-flight reachability, before any integration

The spent protocol's static check verified that the split's **operand** was above its floor and its axis was still inert, because the operand multiplied a channel carrying no current. This protocol checks the **action** instead, on the seeded state, before any integration, in both directions:

| Check | Quantity | Declared condition |
|---|---|---|
| 5.1 live | at the largest load, $|\Delta\dot B|/\max\|\text{RHS}\|$ with $\Delta\dot B$ the change in the bracket's rate produced by $\delta_g=1$ | $\ge$ `ACTION_FLOOR_LIVE` |
| 5.2 silent | on the ray seed, the same quantity with the same $\delta_g=1$ | $\le$ `ACTION_CEIL_SILENT` |
| 5.3 reduction | the split right-hand side at $\delta_g=0$ equals the successor's own right-hand side term for term | elementwise, $0$ difference |
| 5.4 operands | the seed's own bracket $|B|$ relative to the state, and the $\cos\chi$ overlap, at each declared load | reported; no load may be declared that the family cannot realize |

5.1 and 5.2 are checked by the self-check **and** evaluated as gates 4 and 5 at run time. From §1.5 the expected readings are $6.868880495192359\times10^{-3}$ live and $4.199047857243002\times10^{-18}$ silent, so both directions have more than an order of magnitude of margin and neither can be satisfied by accident.

5.3 is checked elementwise and is expected to be exactly zero, because the split's zero-split branch multiplies by $1.0$ and adds $0.0$, both exact float64 operations on the same operands the successor's right-hand side uses.

**The oracle readings, declared as literals.** Gates 10 and 11 compare against numbers read from the two digest-bound receipts, and the executor also checks that each declared literal still equals the receipt's own value, so a tampered receipt fails the binding rather than the oracle:

| Literal | Value | Source |
|---|---|---|
| `ORACLE_RAY_RHO` | $5.329147248815693\times10^{-16}$ | spent split receipt, arm `common_reference`, $\rho_{\max}$ |
| `ORACLE_REPLICATION_RHO` | $2.622443969747147\times10^{-15}$ | successor receipt, arm `mode1_long`, $\rho_{\max}$ |
| `ORACLE_REPLICATION_LAMBDA` | $1.0331312281605476$ | both receipts, the same arm's $\lambda_{\max}$ |
| `ORACLE_REPLICATION_FINAL` | $2.219140084394095\times10^{-15}$ | successor receipt, arm `mode1_long`, $\rho_{\text{final}}$ |

## 6. Run schedule, budget and stopping rule

| Item | Value |
|---|---|
| Command | `timeout 600 python computations/verify_loop_carrier_gate_load.py`, one process from this directory tree's root |
| Executions | $22$, one per arm, in the order of §3 |
| Steps | $19\times600+100+1{,}834=13{,}334$ against the total cap $30{,}000$; the largest arm is the carried replication at $1{,}834$ against the per-execution cap $50{,}000$ |
| Projection | the successor's measured $282{,}334$ steps in `runtime_seconds` $236.08994817733765$ give $8.36\times10^{-4}$ s per step at this grid, so the declared schedule projects to $\approx12$ s of integration plus interpreter start-up |
| Bound | `600` s, $50\times$ the projection |
| Stopping rule | one invocation; the executor refuses a second while its receipt exists; no arm, threshold, level or band is edited after the run |

## 7. References

* `foundations/loop-to-bubble-projection-theorem.md`—(LB1)–(LB14), the loop law, its projection, the member family and the fixed ray.
* `computations/verify_loop_to_bubble_projection.py`—the frozen discrete operators, bound by digest.
* `computations/verify_loop_carrier_projection_relaxation.py`—the successor's executed probe, imported for the law, the projection, the integrator, the canonical companion and the seeds, bound by digest.
* `computations/verify_loop_carrier_projection_split.py`—the spent split protocol's executor, imported for the split right-hand side, bound by digest.
* `computations/loop-carrier-projection-split-prereg.md`—the spent protocol whose gate axis is inert and whose boundary this protocol closes.
* `runs/loop_carrier_projection_split/verification.json`—the spent receipt, source of the ray oracle reading and of the inertness finding, bound by digest.
* `runs/loop_carrier_projection_relaxation/verification.json`—the successor receipt, source of the replication oracle reading, bound by digest.
* `field-experience/probe-outcome-ledger.md` §65–§66—the two predecessor outcomes this protocol reads and does not re-open.
* `open-questions-cassi-answers.md`—the trace-versus-null-vector separation that keeps every reading here from being read as evidence about the conversion ratio.

## 8. Post-execution record

Not yet executed. This protocol and `computations/verify_loop_carrier_gate_load.py` are frozen at the digests in §0; the invocation, its gate table, its per-arm readings, its two fits and its verdicts belong in this section, under the stopping rule of §6.
