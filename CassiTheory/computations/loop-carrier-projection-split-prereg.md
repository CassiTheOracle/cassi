# How Much Splitting Does the Loop-Carrier Projection Tolerate?

## Status: Pre-registered—September 16, 2026; not executed. The executor is frozen in the same commit as this text and refuses to run on a hash mismatch.

## 0. Freeze and binding

This protocol and its executor are frozen together. The executor reads the rows below and refuses to run, with exit code $3$ and no arm constructed, if any of them disagrees with the tree. Section 0 sits outside the frozen body, and the frozen body is what the executor hashes, so the two hashes bind each other without a fix point: the body digest below is a function of §1–§7 alone, and the executor's digest is written here after the executor exists.

| Source | SHA-256 | Meaning |
|---|---|---|
| `frozen_body_sha256` | `f7a7d9ea67bf160ca860fa49d4891a7ff5aa6de0854b97796d1570c9002c1029` | this file from `## 1.` to just before `## 8.`, the text that carries every statistic, threshold, arm and decision rule |
| `executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | `computations/verify_loop_carrier_projection_split.py`, the complete executor frozen with this text |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | `computations/verify_loop_to_bubble_projection.py`, the frozen discrete operators |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | `computations/verify_loop_carrier_projection_relaxation.py`, the successor's executed probe, whose projection, integrator, reference solver and seeds this protocol re-uses |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | `runs/loop_carrier_projection_relaxation/verification.json`, the predecessor's immutable reading, from which the two bit-identity oracles of §4.2 are read |

**What the binding guarantees, exactly.** An edit to §1–§7, or to the executor, is detected before any arm is constructed. An edit to §0 is itself a disclosed amendment, visible in the diff that carries it; it is not detected by construction, and this sentence is the disclosure that it cannot be. Filling §8 after an invocation does not touch the body range, so a legitimate second invocation under the stopping rule of §6 still passes the check, while an undeclared re-run cannot overwrite a recorded receipt (§4.4).

**Executor provenance.** Unlike the successor, whose executor was authored at execution time and defended only by bit-identical arm reproduction, this executor is frozen with the text. The two are bound by the two hashes above, and the executor additionally checks, on one state and without integrating, that its split right-hand side reduces to the successor's term for term at zero split (§4.1 gate 14).

**What the digests are of.** Every hash above is of the file's bytes as they stand in the working tree, which is what the other artifacts in this chain record for the same files; a checkout that rewrites line endings moves several rows at once and is answered by re-pinning, never by editing §1–§7.

## Abstract

The successor protocol settled two questions under two assumptions: that both carriers see one common projected gate $\kappa^{\rm eff}$, and that both carriers are advected by one shared exterior velocity $u$. Both held by construction in every one of its sixteen arms, and its own closing boundary names them. This protocol holds the carrier, the seeds, the frozen operators, the integrator, the statistic, the budget and the controls fixed, and splits one assumption at a time: a gate axis, where the two carriers' conversion fields are offset in opposite directions by a declared relative amount $\delta_g$, and a transport axis, where the two carriers' exterior velocities are offset by a declared relative amount $\delta_u$. Each axis is swept over the six declared levels $\delta\in\{10^{-6},\dots,10^{-1}\}$ plus a supersplit control at $1$, against one shared untouched reference level at $\delta=0$. The statistic is the successor's $\rho_{\max}$, the peak over the trace of the relative projection residual. The question is not whether splitting degrades the closure — it must, since the split is a declared violation — but how: whether the degradation is proportional to the split, with a fitted coefficient, or cliffs at a first level; and where, in declared units of the split, a level leaves the closure class.

## 1. What is held fixed, and what is split

### 1.1 Held fixed

| Item | Value |
|---|---|
| Carrier law | the four-population $\chi$-average of `foundations/loop-to-bubble-projection-theorem.md` (LB6)–(LB14), as the successor re-declares it |
| Discrete operators | `computations/verify_loop_to_bubble_projection.py`, bound by digest, with its exterior axis, loop stencil, exchange operator and bounded composition |
| Projection, integrator, reference solver, seeds | imported from the successor probe at its frozen digest, so the statistic is that code and not a transcription |
| Profile | `on_ray`, one rate set, one seed amplitude $\alpha=0.25$ on mode $1$, direction imbalance $\beta=0.05$ |
| Loop resolution | $N_\chi=24$ on the equal-weight grid, $N_x=7$ in the exterior |
| Class bound | $10^{-6}$, the successor's budget |
| Sub-schedule | the sweep is uniform: $\Delta t=0.02$, $T=2$, $100$ steps, one schedule for all fourteen sweep and reference arms |

### 1.2 Split axis G, the common projected gate

Each carrier's conversion field becomes $\kappa^{\rm eff}_a=\kappa\,(1+\sigma_a\,\delta_g\cos\chi)$ with $\sigma_Y=+1$ and $\sigma_I=-1$, so the two carriers' gates are offset by the declared relative amount $2\delta_g$ and the *sum* of the two conversion rates is no longer $\kappa$ times the pair's own trace. At $\delta_g=0$ this is the successor's field exactly. The gate axis is therefore a declared violation of the common-gate assumption, and the loop-average of the conversion term acquires a term the canonical pair does not have.

### 1.3 Split axis U, the shared exterior transport

Each carrier's exterior velocity becomes $u_a=u\,(1+\sigma_a\delta_u)$ with the same signs, so the two carriers advect at different speeds by the declared relative offset $2\delta_u$, while the diffusion $D_x$, the exchange, the loop transport and the gate stay shared. At $\delta_u=0$ this is the successor's transport exactly. A third, single-level construction is carried outside both sweeps: `orientation_split_005` splits the velocity across the two *orientations* of one shared carrier by the successor's own declared absolute offset $0.05$, which is the successor's `relax_split` geometry at this protocol's seed and horizon; it is a comparability reading, not a swept axis, and no law is fitted to it.

### 1.4 Relation to the successor: comparability

| Quantity | Successor | This protocol |
|---|---|---|
| Statistic | $\rho_{\max}$, peak over the trace of $\max|{\rm proj}\,f-E|/\max(1,\max|E|)$ | the same code path, imported at a frozen digest |
| Class bound | $10^{-6}$ | $10^{-6}$, re-declared in §2.3 |
| Reference solver | $E$ stepped in lockstep with the carrier at the same $\Delta t$ | the same, from the same functions |
| Seeds | mode $1$, $\alpha=0.25$, $\beta=0.05$; no seed on the null pair | the same literals, re-declared in §3 |
| Horizon | per-arm, $10/g$ or the mode rule | one declared sweep horizon $T=2$, with two declared exceptions in §3.1 |
| Controls | reference, null pair, two witness controls | reference, null pair, cross-executor oracle, two can-fail controls, reachability |

The departure is the horizon, and it is deliberate: at the successor's own $T=36.66$ a transport offset of $10^{-2}$ would move the projection by order $10^{-1}$ of the field scale, far outside the linear regime the sweep is meant to measure. $T=2$ keeps the largest swept response below the declared saturation cap while leaving the smallest level eight orders above the arithmetic floor. Section 6 declares the schedule as literals and the executor checks the step rule's inequality on every arm before it integrates anything; if the rule ever demands a different step, the run ends at gate 6 with no verdict rather than silently changing the sweep.

## 2. The statistics

### 2.1 The closure statistic, carried

For one arm, at every accepted state including $t_0$, the residual is
$$\rho(t)=\frac{\max_a\max_x|\,{\rm proj}\,f_a(x,t)-E_a(x,t)|}{\max\big(1,\max_a\max_x|E_a(x,t)|\big)},$$
with $E$ the canonical pair advanced in lockstep at the same step, and the arm's reading is $\rho_{\max}=\max_t\rho(t)$. A level is `within_budget` when its arm's $\rho_{\max}\le10^{-6}$ and `above_budget` otherwise.

### 2.2 The split statistic

For one axis, the response at level $\delta$ is $e(\delta)=\rho_{\max}(\delta)$, the arm's own reading, against the shared $\delta=0$ reference. The reading rules, all applied to these numbers alone:

| Rule | Definition |
|---|---|
| readable | $e(\delta)>10^{-13}$, three orders above the arithmetic floor the reference sits at |
| coefficient | $c=\sum\delta_k e_k/\sum\delta_k^2$ over the readable levels, a least-squares line through the origin |
| exponent | $p$, the slope of $\log e$ on $\log\delta$ over the readable levels |
| ratio | $r_k=e_k/(c\,\delta_k)$ per readable level, a declared factor band around the fitted line |
| jump | $e_{k+1}/e_k$ between adjacent readable levels, against $10^{p}$, the growth the fitted exponent implies |
| crossing | $\delta^\star=10^{-6}/c$, the level at which the fitted line reaches the class bound, recorded and not gated |

### 2.3 Declared constants and thresholds

| Constant | Value | Meaning |
|---|---|---|
| `budget` | `1.0e-6` | the closure class bound, carried from the successor |
| `reference_floor` | `1.0e-14` | the reference arm must read at or below this |
| `structural_scale` | `1.0e-4` | every can-fail control must read above this |
| `annihilation_tolerance` | `1.0e-14` | gate 2, carried |
| `idempotence_tolerance` | `1.0e-15` | gate 3, carried |
| `matched_start_tolerance` | `1.0e-15` | gate 4, carried |
| `null_floor` | `1.0e-11` | the null pair's floor, carried |
| `readable_floor` | `1.0e-13` | a level's reading must exceed this to enter the fit |
| `fit_band` | `2.0` | a readable level's ratio must lie in $[1/2,2]$ for a proportional law |
| `exponent_low` | `0.9` | the fitted exponent's lower bound for a proportional law |
| `exponent_high` | `1.1` | the fitted exponent's upper bound for a proportional law |
| `jump_factor` | `3.0` | an adjacent pair growing by $3\times$ the level ratio is a cliff |
| `monotone_tolerance` | `1.5` | a fall beyond this factor between readable levels is non-monotone |
| `min_readable` | `4` | below this many readable levels the axis is inconclusive |
| `saturation_cap` | `0.25` | a level reading above this is recorded `saturated` and excluded from the fit |
| `operand_floor_gate` | `0.05` | the gate axis's $t_0$ operand must exceed this |
| `operand_floor_transport` | `0.10` | the transport axis's $t_0$ operand must exceed this |
| `split_levels` | `1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1` | the six swept levels, one per axis |

| Schedule constant | Value | Meaning |
|---|---|---|
| `split_dt` | `0.02` | the sweep's step, uniform across the fourteen sweep and reference arms |
| `split_horizon` | `2.0` | the sweep's horizon |
| `split_steps` | `100` | the sweep's step count |
| `replication_dt` | `0.02` | the cross-executor oracle's step, the successor's own |
| `replication_horizon` | `36.66172105812361` | the successor's `mode1_long` horizon |
| `replication_steps` | `1834` | the successor's `mode1_long` step count |
| `short_dt` | `0.05` | the null pair's step, the successor's own |
| `short_horizon` | `0.3666172105812361` | the null pair's horizon |
| `short_steps` | `8` | the null pair's step count |
| `step_safety` | `40.0` | the successor's safety factor: $\Delta t\le1/(40\lambda_{\max})$ |
| `step_cap_per_execution` | `50000` | carried |
| `step_budget_total` | `6000` | this protocol's total cap, §6 |
| `declared_executions` | `19` | one process, nineteen arms |
| `bound_seconds` | `600.0` | the wall-clock bound |

### 2.4 The level of the split, and what a level means

A level is a *relative* offset: $\delta_g=10^{-2}$ means one carrier's gate carries $1+\cos\chi$ times $10^{-2}$ more than the other's, and $\delta_u=10^{-2}$ means one carrier advects $1\%$ faster than the other. Levels are not comparable across axes in physical terms, and no cross-axis claim is made; each axis is measured against its own coefficient, its own exponent and its own crossing.

## 3. The arm list

Nineteen arms, one process, in this order. Every arm carries the arms of §1.1 unless its row says otherwise: the profile is `on_ray`, the seed is mode $1$ with $\alpha=0.25$ and $\beta=0.05$, the gate is the common field at $\delta_g=0$ and the transport is shared at $\delta_u=0$ unless the row splits it.

### 3.1 References—four arms

| Arm | Construction | Schedule |
|---|---|---|
| `common_reference` | the shared $\delta=0$ level of both axes: the successor's mode-1 seed at this protocol's sweep schedule | $0.02$, $T=2$, $100$ steps |
| `successor_replication` | the successor's `mode1_long` construction exactly: same seed, step and horizon | $0.02$, $T=36.66172105812361$, $1834$ steps |
| `uniform_short` | the successor's `uniform_short` construction: uniform content, no seed, no loop content | $0.05$, $T=0.3666172105812361$, $8$ steps |
| `null` | the successor's `null` construction: byte-identical to `uniform_short` | $0.05$, $T=0.3666172105812361$, $8$ steps |

### 3.2 Gate axis—six levels and one control

| Arm | $\delta_g$ | Schedule |
|---|---|---|
| `gate_split_1` | $10^{-6}$ | sweep |
| `gate_split_2` | $10^{-5}$ | sweep |
| `gate_split_3` | $10^{-4}$ | sweep |
| `gate_split_4` | $10^{-3}$ | sweep |
| `gate_split_5` | $10^{-2}$ | sweep |
| `gate_split_6` | $10^{-1}$ | sweep |
| `supersplit_gate` | $1$ | the step rule's own output at this arm's $\lambda_{\max}$, $T=2$ |

### 3.3 Transport axis—six levels and one control

| Arm | $\delta_u$ | Schedule |
|---|---|---|
| `transport_split_1` | $10^{-6}$ | sweep |
| `transport_split_2` | $10^{-5}$ | sweep |
| `transport_split_3` | $10^{-4}$ | sweep |
| `transport_split_4` | $10^{-3}$ | sweep |
| `transport_split_5` | $10^{-2}$ | sweep |
| `transport_split_6` | $10^{-1}$ | sweep |
| `supersplit_transport` | $1$ | $0.02$, $T=2$, $100$ steps |

### 3.4 Comparability—one arm

| Arm | Construction | Schedule |
|---|---|---|
| `orientation_split_005` | the successor's own split geometry: the two orientations of one shared carrier advect at $u\mp0.05$, no gate split | sweep |

## 4. Gates, controls and reachability

### 4.1 The fourteen gates

| Gate | Requirement |
|---|---|
| 1 source binding | §0's five rows agree with the tree, and the protocol body hashes to the declared value, else exit $3$ before any arm |
| 2 discrete annihilation | the loop derivative's and Laplacian's $\chi$-sums vanish to $10^{-14}$ at every accepted state of every arm |
| 3 projection idempotence | projecting a lifted projection returns it to $10^{-15}$ |
| 4 matched start | the initial projection equals the canonical initial pair to $10^{-15}$ |
| 5 finite and nonnegative | every recorded scalar finite, every carrier and projection value $\ge0$, $0\le q<1$ |
| 6 schedule conformance | $\Delta t\le1/(40\lambda_{\max})$ and $\Delta t$ in the successor's candidate set, on every arm, before it integrates |
| 7 declared shape | nineteen executions, per-execution cap $50{,}000$, total cap $6{,}000$, no missing statistic |
| 8 reference at the floor | `common_reference` reads $\le10^{-14}$ |
| 9 witness floor | both null-pair arms read $\le10^{-11}$ and agree bit for bit |
| 10 cross-executor oracle | `successor_replication` reads exactly the successor receipt's `mode1_long` $\rho_{\max}$, and `uniform_short` exactly the receipt's null reading |
| 11 can-fail control | both supersplit arms read above $10^{-4}$ |
| 12 split reachability | both $t_0$ operands of §4.3 exceed their floors |
| 13 process declaration | one process, nineteen executions, no concurrent run |
| 14 split reduction | on the declared initial state, at $\delta=0$ the split right-hand side equals the successor's element for element, and the orientation geometry at $0.05$ equals the successor's own split; checked by `--self-check`, before execution |

Gates 1, 6, 13 and 14 are decided before or without integration; the rest are read from the traces.

### 4.2 The cross-executor oracle, and why it is not a typed number

Gate 10 compares against the successor's receipt, which is bound by digest in §0 *and* whose two readings are declared as literals in the executor. A receipt that drifted, or a literal that was mistyped, ends the run at exit $3$ before any arm. The oracle is the strongest available fidelity statement: the replication arm shares every construction with the successor's own `mode1_long`, so **bit-identity** is the expected outcome and any departure means this executor's conventions are not the successor's.

### 4.3 Reachability, read before execution

| Axis | Operand | Floor | Construction value |
|---|---|---|---|
| G | $\max_a|\langle\cos\chi\,(f_a-\langle f_a\rangle_\chi)\rangle_\chi/\langle f_a\rangle_\chi|$ at $t_0$ | `0.05` | $\alpha/2=0.125$ for the mode-1 seed |
| U | $\max_a\max_x|\partial_xE_a|$ at $t_0$ | `0.10` | $0.1868$, the frozen central difference of the `on_ray` modulation, read in the self-check |

These are the operands the two splits act on. If either were zero the corresponding axis would be vacuous — a sweep reading a flat zero against a gate it cannot fire — and the run would end at gate 12 with no verdict rather than report a law about nothing. This is the same obligation gate 11 of the successor discharges for its identity.

### 4.4 The two can-fail controls, and what they rule out

`supersplit_gate` and `supersplit_transport` carry a relative offset of $2$ — one carrier's gate doubling while the other's vanishes at $\chi=\pi$, or one carrier frozen while the other advects at twice the shared speed. Both must leave the closure class decisively, above the structural scale $10^{-4}$. If a $100\%$ violation still read at the floor, the instrument would be blind and the sweep uninformative, so the run ends at gate 11 with no verdict. The reference and null-pair arms are the other half: they prove the same statistic can read zero on this construction.

### 4.5 The refusal path and the stopping rule

The executor refuses, with exit $3$ and no receipt, when a binding mismatches, when the successor receipt disagrees with the declared oracles, or when `runs/loop_carrier_projection_split/verification.json` already exists. The last is the stopping rule of §6 in code: a second invocation is permitted only after an invocation that wrote no receipt.

## 5. Decision tree

### 5.1 Features

| Feature | Emerges when |
|---|---|
| D1 | the shared reference level is at the floor (gate 8) |
| D2 | the null pair reads the floor and agrees with itself (gate 9) |
| D3 | both can-fail controls fire (gate 11) |
| D4 | both reachability operands are live (gate 12) |
| D5 | the cross-executor oracle is bit-identical (gate 10) |
| D6 | both axes issue a law label other than `INCONCLUSIVE` |

D1–D5 are the instrument's licence; D6 is the measurement's own decidable-ness. `status=PASS` requires every gate, hence every feature; otherwise `status=FAIL` and no verdict is issued.

### 5.2 Per-axis law labels

Applied per axis to the six readings and nothing else, in this order:

| Label | Condition |
|---|---|
| `INCONCLUSIVE` | fewer than $4$ readable levels, or the response is not monotone within the tolerance |
| `PROPORTIONAL` | every readable level within the factor band of the fitted line and the exponent within its bounds |
| `CLIFF` | not proportional, but an adjacent readable pair grows by at least $3\times$ the growth the fitted exponent implies |
| `NONLINEAR` | not proportional and not a cliff, but monotone: the response bends, as a quadratic onset would |

All four are reachable: the executor's `--self-check` drives each with declared synthetic readings before any invocation, and proves that a silent can-fail control makes `status=FAIL` reachable.

### 5.3 The class boundary

Per axis, the levels are labelled `within_budget` or `above_budget`; the smallest level above the bound is named; and the crossing $\delta^\star=10^{-6}/c$ from the fitted line is recorded beside the measured bracket. The combined label is `BRACKETED` when both axes hold at least one level on each side of the class bound, `ABOVE_ALL_LEVELS` when every level on both axes is above it, `BELOW_ALL_LEVELS` when none is, and `MIXED` otherwise. The crossing is a recording, not a criterion: only the six declared levels are measurements.

### 5.4 Falsifiers

| Falsifier | Reading | Consequence |
|---|---|---|
| the instrument is blind | a supersplit at the floor | `FAIL`, no verdict |
| the axis is vacuous | an operand below its floor | `FAIL`, no verdict |
| the conventions drifted | the replication arm not bit-identical to the receipt | `FAIL`, no verdict |
| the reference is not a floor | `common_reference` above $10^{-14}$ | `FAIL`, no verdict |
| the sweep left the linear regime | any level above the saturation cap | that level is excluded from the fit and recorded as `saturated`; if fewer than four levels remain readable the axis is `INCONCLUSIVE` |
| a law is asserted from a bent sweep | monotone, off the band, no cliff | `NONLINEAR`, never `PROPORTIONAL` |

## 6. Run schedule, budget and stopping rule

| Item | Value |
|---|---|
| Command | `timeout 600 python computations/verify_loop_carrier_projection_split.py`, one process from the repository root |
| Executions | $19$, one per arm, in the order of §3 |
| Steps | $3{,}450$ at the declared schedule ($1{,}950$ in the four reference arms, $600$ per swept axis, $100$ comparability, $100$ for each supersplit), against the total cap $6{,}000$. The self-check evaluates the step rule on all nineteen arms without integrating: every arm takes $\Delta t=0.02$, and the largest $\lambda_{\max}$ over the arms is $1.049061$ on `supersplit_gate`, so the rule's limit there is $0.0238$ and the declared step holds on every arm |
| Per-execution cap | $50{,}000$, carried |
| Projection | the successor's measured $282{,}334$ steps in `runtime_seconds` $236.08994817733765$ give $8.36\times10^{-4}$ s per step at this grid, so the declared schedule projects to $\approx3$ s of integration plus interpreter start-up; the bound is $600$ s, $120\times$ the projection. The successor's per-state readings are heavier than this protocol's, so the projection is an upper bound |
| Bound | `600` s |
| Stopping rule | one invocation. A second is permitted only if the first expired inside the bound without writing a receipt, running the identical command against the identical digests, with no arm deleted and no threshold moved. Once a receipt exists the executor refuses a second invocation |

## 7. Interpretation boundary

**What a `PROPORTIONAL` verdict would say.** That over the six declared levels, on this finite realization, at one rate set, one seed amplitude and one $\chi$-resolution, the closure's degradation under a split of either assumption is a smooth law $e\approx c\,\delta$ with a fitted coefficient, so that the level at which a split of a declared size leaves the class can be computed rather than searched. **What a `CLIFF` or `NONLINEAR` verdict would say.** That the closure is not a smooth function of the split at these levels — either it holds up to a threshold and then fails, or it bends — which is a statement about the projection's stability, not about the ratio.

**What neither would say.** Nothing here measures the value of $\varphi$, the origin of the conversion ratio, the physical carrier identity, the QF1-to-carrier map, the phase law, the scale ratio or the quantum statistics. The ratio enters only as the declared entries of the four-population law, exactly as in the successor, and the four-population law remains the selected minimal member of a family whose columns sum to one, so the closure selects no member and separates no conversion law. The split coefficient is a property of the *declared* block's trace, not evidence about the ratio.

**Not covered.** Four populations at one rate set and one seed amplitude; the common projected gate and the common exterior transport are the assumptions under test, not derived; $N_\chi=24$ with no refinement; four exterior profiles are available and only `on_ray` is used; one profile per axis; the four-population law is the selected minimal member of a family whose columns sum to one; no phase law, no carrier identity, no scale ratio, no statistics; the transport axis splits the exterior velocity alone and leaves the exterior diffusion, the exchange and the loop transport shared; the gate axis splits the conversion field's magnitude alone and leaves its functional form, the exchange and the loop content untouched; the orientation comparability arm is one level and no law is fitted to it.

## 8. Post-execution record

Sections 1–7 state the protocol as it stands frozen. This section was filled after the single queued invocation. No text of §1–§7 was edited after it, no threshold moved, no arm was added, and the command of §6 ran once; the receipt it wrote is the record.

### 8.1 Invocation

| Item | Reading |
|---|---|
| Command | `timeout 600 python computations/verify_loop_carrier_projection_split.py`, one process from this directory tree's root |
| Bound | $600$ s, declared in §6 |
| Wall time, measured outside | $2$ s |
| Wall time, inside | `runtime_seconds` $2.34736967086792$, against the §6 projection of $\approx3$ s |
| Executions | $19$, one per arm, in the order of §3 |
| Steps | $3{,}450$ against the total cap $6{,}000$; the largest single arm is `successor_replication` at $1{,}834$ against the per-execution cap $50{,}000$ |
| Receipt | `runs/loop_carrier_projection_split/verification.json`, $34{,}823$ bytes, SHA-256 `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` (gitignored run artifact; the directory holds the receipt alone, and no log file was written) |
| Status | `FAIL`, neither verdict issued |

| Source | SHA-256, declared and observed |
|---|---|
| `computations/loop-carrier-projection-split-prereg.md` §1–§7 (this file's frozen body) | `f7a7d9ea67bf160ca860fa49d4891a7ff5aa6de0854b97796d1570c9002c1029` |
| `computations/verify_loop_carrier_projection_split.py`, executed | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` |
| `computations/verify_loop_to_bubble_projection.py` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` |
| `computations/verify_loop_carrier_projection_relaxation.py` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` |
| `runs/loop_carrier_projection_relaxation/verification.json` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` |

**Execution note.** The self-check cannot be re-run after an invocation: its own last item asserts that no receipt exists, so with a receipt on disk it now reports the receipt itself as a failure. The binding was verified instead by recomputing the body digest and the executor digest directly against their declared values, both of which still agree; the receipt's `binding` block carries the same comparison, with declared and observed equal row for row.

### 8.2 Gate table

$13$ gates, $12$ passed and gate $11$ failed.

| # | Gate | Bound | Reading | Result |
|---|---|---|---|---|
| 1 | binding, declared against observed | exact | all five rows of §0 equal | pass |
| 2 | discrete annihilation | $10^{-14}$ | $2.465042059363043\times10^{-15}$ | pass |
| 3 | projection idempotence | $10^{-15}$ | $1.0086980600957879\times10^{-16}$ | pass |
| 4 | matched start | $10^{-15}$ | $2.220446049250313\times10^{-16}$ | pass |
| 5 | finite and nonnegative | structural | $\min$ state $0.19855056643547828$, $q\in[0.8478829488918167,\,0.9227356957733256]$ | pass |
| 6 | schedule conformance | $\Delta t\le1/(40\lambda_{\max})$, $\Delta t\in\{0.05,0.02,0.01\}$ | no non-conformant arm; steps $0.02$ and $0.05$ | pass |
| 7 | declared shape | $19$ executions, $6{,}000$ steps total | $19$ of $19$, $3{,}450$ of $6{,}000$ | pass |
| 8 | reference at the floor | $10^{-14}$ | $5.329147248815693\times10^{-16}$ | pass |
| 9 | witness floor, null pair | $10^{-11}$ | $8.505827589859918\times10^{-17}$ with $\Delta=0.0$ | pass |
| 10 | cross-executor oracle | bit-identical | replication $2.622443969747147\times10^{-15}$ and null $8.505827589859918\times10^{-17}$, equal to the successor receipt's readings | pass |
| 11 | can-fail control | both supersplits $\ge10^{-4}$ | `supersplit_transport` $6.709984101592009\times10^{-2}$; `supersplit_gate` $5.329147248815693\times10^{-16}$ | **fail** |
| 12 | split reachability | gate $\ge0.05$, transport $\ge0.10$ | $0.12500000000000006$ and $0.18682135228047267$, read before execution | pass |
| 13 | process declaration | one process, no concurrent run | $1$ process, $19$ executions | pass |

**Margins.** The tightest passing margin is the transport operand of gate $12$ at $1.87\times$ its floor ($0.18682135228047267$ against $0.10$), followed by the gate operand at $2.5\times$ ($0.12500000000000006$ against $0.05$) and the reference floor of gate $8$ at $19\times$ ($5.329147248815693\times10^{-16}$ against $10^{-14}$). The tightest structural margin is the step, $\Delta t=0.02$ against the rule's limit $0.0238$ at the largest $\lambda_{\max}=1.049061$, i.e. $1.19\times$, as §6 records; the step total used $58\%$ of its cap. Nothing else was near a bound: the null pair sits at $10^{-17}$ against $10^{-11}$, and the failing control is short of its bound by $1.9\times10^{11}$.

### 8.3 The gate axis

| Level | $\delta_g$ | $\rho_{\max}$ | Class |
|---|---|---|---|
| 1 | $10^{-6}$ | $5.329147248815693\times10^{-16}$ | `within_budget` |
| 2 | $10^{-5}$ | $5.329147248815693\times10^{-16}$ | `within_budget` |
| 3 | $10^{-4}$ | $5.329147248815693\times10^{-16}$ | `within_budget` |
| 4 | $10^{-3}$ | $5.329147248815693\times10^{-16}$ | `within_budget` |
| 5 | $10^{-2}$ | $5.329147248815693\times10^{-16}$ | `within_budget` |
| 6 | $10^{-1}$ | $5.329147248815693\times10^{-16}$ | `within_budget` |
| supersplit | $1.0$ | $5.329147248815693\times10^{-16}$ | `within_budget` |

Every one of the seven readings is the `common_reference` reading of §8.5 to the last digit, and so is every arm's `loop_content_final` ($0.12079677487732632$) and terminal $\rho$: the seven gate arms do not leave the unsplit trajectory at all. The fit is therefore empty—$0$ of $6$ levels readable above $10^{-13}$, no exponent, no ratios, no crossing—and the boundary label is `BELOW_ALL_LEVELS`, with all six levels inside the budget.

**Why the axis is inert, from the executed code.** Let $B=-\psi_Y+\varphi\,\psi_I$ elementwise over the two orientations, the exterior grid and the loop, where $\psi_a$ is carrier $a$'s content in the four-population state; $B$ is exactly the bracket the conversion term multiplies. The executed right-hand side is linear and source-free in $B$ whenever the two carriers share an exterior velocity and no orientation split is declared: advection and diffusion contribute $-v\,\partial_xB+D_x\nabla^2B$; the loop derivative and loop diffusion contribute $\Omega\,\partial_\chi B+D_\ell\nabla^2_\chi B$, the carrier signs folding into the same bracket; the exchange between the two orientations of one carrier contributes $E\,(B-B_{\rm swap})$, linear with no constant term; and the conversion term contributes $-(\kappa_Y+\varphi\,\kappa_I)B$, whose split factor is $\kappa(1+\varphi)+\kappa\,\delta_g(1-\varphi)\cos\chi$. Checked after the run on one state without integrating: on a random state placed exactly on the ray, the non-conversion part of the right-hand side moves $B$ by $1.3\times10^{-15}$ against a right-hand side of magnitude $3.07$, the arithmetic floor, and the $\delta_g=1$ split leaves it there too; on a state carrying $B\neq0$ the same split does change $\dot B$, from $1.55\times10^{-6}$ to $1.92\times10^{-6}$, which is the channel this seed does not load. So $B\equiv0$ is invariant, and the `on_ray` seed satisfies it exactly at $t_0$: the profile's two densities are on the ray, $E_Y/E_I=\varphi$, so the conversion channel is unloaded when the run starts and stays unloaded. A gate split multiplies that zero, at every order in $\delta_g$, which is why `supersplit_gate` at $\delta_g=1.0$ reproduces the reference to the digit and why gate $11$ fired.

**What this says, plainly.** The gate axis is not resolvable in this realization, and not merely because its readings sit under the readable floor: its observable is *identically zero* on this seed, because the conversion channel it splits carries no current. The run therefore does not answer "is the gate split first order at $T=2$" with "no" or with "quadratic"; it answers that the declared split is unsensed here at any order, and that the smallest of six decades could not have measured anything. It is not evidence that a split gate is harmless, and it is not evidence about any order in $\delta_g$. A live gate-axis measurement needs a seed that carries a nonzero conversion bracket—the successor's own `covariance` relaxation construction departs from the ray and made its witness fire—which is a design change for a future protocol, made against a *new* body, not an edit to this one. No threshold, arm, statistic or sentence of §1–§7 moves here, and the frozen body digest of §8.1 still holds.

### 8.4 The transport axis

| Level | $\delta_u$ | $\rho_{\max}$ | Class |
|---|---|---|---|
| 1 | $10^{-6}$ | $6.799503171158458\times10^{-8}$ | `within_budget` |
| 2 | $10^{-5}$ | $6.799505370319889\times10^{-7}$ | `within_budget` |
| 3 | $10^{-4}$ | $6.7995273333344465\times10^{-6}$ | `above_budget` |
| 4 | $10^{-3}$ | $6.79974665183148\times10^{-5}$ | `above_budget` |
| 5 | $10^{-2}$ | $6.8001910184790587\times10^{-4}$ | `above_budget` |
| 6 | $10^{-1}$ | $6.8205755240104814\times10^{-3}$ | `above_budget` |

All six levels are readable, and the monotone response is first-order in the declared offset: the fitted coefficient is $6.820388654045467\times10^{-2}$ with exponent $1.000205540897814$, and the per-level ratios to the fitted line are $0.9969377869874585$, $0.9969381094267712$, $0.9969413296266266$, $0.9969734859315175$, $0.9972907014259487$ and $1.0000273987267432$, all inside the factor $2$ of §2.1. The boundary label is `BRACKETED`: levels $1$–$2$ inside the class bound and levels $3$–$6$ above it, with the crossing at $\delta^\star=1.4661921053529064\times10^{-5}$. The mechanism is the one §8.3 excludes for the gate axis: the differential velocity is the only term in the setting that generates $B$, so the split enters the conversion channel at first order through the departure it creates.

**No law is issued for this axis.** §5 makes `status=PASS` a conjunction over the gates and hence over the features, and gate $11$ fails, so both verdicts are withheld: the fit above is a recorded sweep (`sweep.transport.fit` in the receipt), not a verdict, and the transport axis carries no label from the law vocabulary. Its numbers stand as recorded and no threshold was retuned to give it one. `INCONCLUSIVE` is likewise not issued for the gate axis: the frozen decision tree reaches a label only for an axis whose own readings qualify, and the gate sweep has no readable level at all; what the run records there is the boundary label `BELOW_ALL_LEVELS` and the failing can-fail control.

### 8.5 Controls and the comparability arm

| Control | Reading | Bound or comparison |
|---|---|---|
| Reference level | $\rho_{\max}$ $5.329147248815693\times10^{-16}$ | gate 8 bound $10^{-14}$, $19\times$ inside |
| Null pair | $8.505827589859918\times10^{-17}$ in both arms, $\Delta=0.0$ exactly | gate 9 bound $10^{-11}$; the successor's own null reading, bit-identical |
| Cross-executor oracle | `successor_replication` $2.622443969747147\times10^{-15}$ and `uniform_short` $8.505827589859918\times10^{-17}$ | equal to the predecessor receipt's readings; its $\lambda_{\max}$ $1.0331312281605476$ is re-derived, not read |
| Reachability operands | gate $0.12500000000000006$, transport and orientation $0.18682135228047267$ | floors $0.05$ and $0.10$ |
| Can-fail, transport | `supersplit_transport` $6.709984101592009\times10^{-2}$ | fires, $671\times$ above the $10^{-4}$ bound |
| Can-fail, gate | `supersplit_gate` $5.329147248815693\times10^{-16}$ | does not fire; gate 11 fails |
| Comparability | `orientation_split_005` $\rho_{\max}$ $3.263521392755\times10^{-4}$, class `above_budget` | the successor's own `relax_split` geometry at $u\mp0.05$: its reading of that construction is $5.998107249\times10^{-4}$ on its own horizon $T=1000$, reached at $t=8.18$, so this protocol's hundred-step, $T=2$ reading of the same geometry is $0.544$ of the successor's peak and sits before it, and both are far above the class bound |

The comparability reading is a recorded observation, not a criterion: §1.4 declares it and fits no law to it, and the receipt carries it in `sweep.comparability`. It is the arm that shows the statistic is not deaf to splitting as such—the same construction the successor found far above its witness floor is found far above this protocol's class bound—while the gate axis, split by a comparable declared amount, reads exactly the reference.

### 8.6 Verdicts, boundary and stopping rule

The receipt's aggregate reading, verbatim:

```text
FAIL
degradation_gate: null
degradation_transport: null
class: null
```

Features: D1 true, D2 true, D3 **false**, D4 true, D5 true, D6 **false**. D3 is the can-fail feature and D6 the law-label feature; with them false, §5's rule withholds both verdicts and the run ends at `FAIL`. Nothing else moved: the executions are $19$ of the declared $19$, the steps $3{,}450$ of the declared cap, and the wall time $2.34736967086792$ s of the $600$ s bound.

**Boundary.** One finite realization at $N_\chi=24$, one rate set, one profile, one seed amplitude; the common projected gate and the common exterior transport remain the assumptions under test and are still not derived from the theorem; the four-population law remains the selected minimal member of a family whose columns sum to one; no reading here is a value of $\varphi$, and nothing here measures the conversion ratio, the carrier identity, the QF1-to-carrier map, the phase law, the scale ratio or the quantum statistics. **RESOLVED** by this run: the gate axis of this protocol is inert on a seed that sits exactly on the conversion ray, and the can-fail control that exists to catch exactly that fired, so the protocol returned its `FAIL` rather than a law about nothing. **UNRESOLVED** and untouched: whether a split gate degrades the projection at any level, on any seed, at any order—this run did not measure it and does not bound it, and the same question on a seed carrying a nonzero conversion bracket is open.

**Stopping rule.** The receipt now exists, so a second invocation is refused in code before any arm is constructed, and no re-run was made. §0's digests are unchanged by this section, since §8 lies outside the frozen body; the body digest and the executed executor digest of §8.1 are the values §0 declares, recomputed after the run.

## References

* `foundations/loop-to-bubble-projection-theorem.md`—(LB1)–(LB14), the loop law, its projection, the member family and the fixed ray, whose assumptions §1.1–§1.3 split.
* `computations/verify_loop_to_bubble_projection.py`—the frozen discrete operators, bound by digest.
* `computations/loop-carrier-projection-relaxation-prereg.md`—the successor protocol whose statistic, budget and comparability §1.4 re-declares.
* `computations/verify_loop_carrier_projection_relaxation.py`—the successor's probe, imported for the projection, the integrator, the reference solver and the seeds, bound by digest.
* `runs/loop_carrier_projection_relaxation/verification.json`—the successor's receipt, source of the two bit-identity oracles of §4.2, bound by digest.
* `field-experience/probe-outcome-ledger.md` §65—the successor's outcome, including the common-gate and common-transport boundary this protocol tests.
* `runs/loop_carrier_projection_split/verification.json`—this protocol's receipt, the record of the single invocation of §8, and the source of every reading quoted there.
* `foundations/phi-input-or-selection.md`—why no reading in this protocol is a value of $\varphi$; the conversion block's trace and its null vector are separated there and in `foundations/loop-rate-selection-candidates.md`.
