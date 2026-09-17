# Two Coordinates On Purpose: Dialing Exactly One Gap Entry to Zero and Predicting `dim ker` Before the Run

## Status: Pre-registered—September 16, 2026; not executed. The executor `computations/verify_loop_carrier_two_coordinates.py` is frozen in the same commit as this text and refuses to run on a hash mismatch.

## 0. Freeze and binding

| Row | Value | What it binds |
|---|---|---|
| `frozen_body_sha256` | `7fce9e0e3a252eef3e54be3cee016f2e1db453a7e9c25cdae98b873884678fbe` | this file, sections 1–7: everything from `## 1.` to just before `## 8.`, with the two in-place corrections §8.1 records; the digest of the text that ran is `a2c6abe2f85b2c9c12e25fd7062ba4d12b8c640ef192c81bb8fc5e5c03c22f33` |
| `executor_sha256` | `671e4a5edbe406f6c1f932d855987d5cc746315b10c13f387291bf15cbf778f0` | `computations/verify_loop_carrier_two_coordinates.py`, the complete executor frozen with this text; re-anchored once after the single invocation, when its body-digest constant was re-anchored with the amendment §8.1 records and nothing else in it moved |
| `prior_body_sha256` | `09426b6829e93bc02e7e2d330f3158b6889eebddd620bee149d9b3267f147f25` | `computations/loop-carrier-composition-coexistence-prereg.md` §1–§7, the body whose retained writable coordinate §71 identified as a conservation law |
| `prior_executor_sha256` | `3852eadbd434e021d1dc351820db06e6295c34c11270144b0826f6097b09f6b1` | `computations/verify_loop_carrier_composition_coexistence.py`, imported as a library: its direction-A modulation is the term-for-term reference this body's carrier channel must reduce to, and its `composition_profile` is the transposed reduction this body's domain gate refuses to reproduce |
| `audit_executor_sha256` | `0503f109c8b431768fbe16d37dfe8a82dec18cce2f97dc417d2fb08d1474f07a` | `computations/verify_loop_carrier_kernel_dimension.py`, the §71 audit: the closed form's entries, the spectrum, the kernel and the two declared-shaped reading-domain probes are read from here |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | `computations/verify_loop_to_bubble_projection.py`, the frozen discrete operators |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | `computations/verify_loop_carrier_projection_relaxation.py`, the seed family, the projection, the canonical companion, the state right-hand side (LB6) with its per-arm `exchange` coefficient, and the base's own declared `persistent_current` arm at `r = 0` |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | `computations/verify_loop_carrier_projection_split.py`, the executor carrying the gate line and the seed |
| `gate_load_executor_sha256` | `be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac` | `computations/verify_loop_carrier_gate_load.py`, the executor carrying the loaded seed family and the load reading |
| `write_executor_sha256` | `PLACEHOLDER_CHECKED_AT_RUNTIME` | `computations/verify_loop_carrier_attractor_write.py`, imported as a library: `coordinate_of`, `ray_distance_of`, `fit_held`, `fit_free`, `read_clock`, and the declared release horizons and relaxation rate |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | `runs/loop_carrier_projection_relaxation/verification.json`, the relaxation rate both fits hold |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` | `runs/loop_carrier_projection_split/verification.json`, the cross-protocol oracle |
| `gate_load_receipt_sha256` | `471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1` | `runs/loop_carrier_gate_load/verification.json`, the measured load of the seeded family |
| `prior_receipt_sha256` | `5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200` | `runs/loop_carrier_attractor_write/verification.json`, the two retention branches the spent fits carry |
| `coexistence_receipt_sha256` | `9724143b98cf394eb9948741d3a117c4cc1e4b14fe54ff2ad9e81dfddb8bf60f` | `runs/loop_carrier_composition_coexistence/verification.json`, the spent body's own readings: the anchor the exchange-free run must reproduce and the transposed coordinates this body replaces |

**The amendment of September 16, 2026, after the invocation.** Two passages *inside* the body
range—§6's bound row set and §6's invocation sentence—were corrected in place at the user's
instruction, each marked in place with the value the pre-amendment text read and a pointer to §8.1,
which records the amendment, the frozen body's digest on both sides of it and the consequence. No
arm, threshold, tolerance, level, gate, feature or decision rule was touched: the corrected passages
are cost declarations that no part of this executor parses, and the arm table, the twenty thresholds,
the fourteen gates and the four branch tables are byte-identical to the text that ran. Re-anchoring
the moved body required updating this executor's own `FROZEN_BODY_DIGEST` constant and its comment,
and nothing else in it; the receipt correctly records the digests of the body and the executor that
ran, so the self-check after the amendment reports the receipt's `protocol_body_sha256` and
`executor_sha256` rows as standing against the executed pair rather than against the amended text.
That is the disclosure, not a defect: the amendment is a post-run edit, visible in the commit that
carries it.

The executor's `check_binding` compares every row and refuses with exit 3 before any arm exists on any mismatch. The `write_executor_sha256` row is the one row whose value is read at run time from the module itself rather than pasted here: the executor records the observed digest in the receipt, and §5's clock replication is the gate that fails if that module's declared rate moves.

**The stopping rule, in code and in the schedule.** The executor refuses with exit 3 and no receipt when any binding mismatches or when `runs/loop_carrier_two_coordinates/verification.json` already exists. The last is §6's stopping rule: this body is invoked **once**, and a second invocation is permitted only after an invocation that wrote no receipt.

## Abstract

§71 closed on a dial. At the spent body's own declared point the internal gap (LB39) is the $\kappa(1+\varphi)$ entry and the kernel of the frozen generator over the declared modes holds exactly one direction — the excluded total-density mode — so the retention the spent chain measured is a conservation law and not a second storage level. Every *vanishing* entry of that gap is an extra conserved direction, and the entry values say how far a point sits from each boundary. This body turns the dial on purpose: it changes one declared coefficient, keeps everything else the chain fixed, and declares the answer before it runs.

**The declared point.** With the exchange coefficient at zero, $r=0$, the three entries of (LB39) at the equilibrium are

$$\kappa(1+\varphi)=1.1268281293796237\times10^{-2},\qquad 2r=0,\qquad d+r-\operatorname{Re}\sqrt{r^2-\Omega^2}=d=4.4982698961937725\times10^{-2},$$

so **exactly one entry vanishes**, the second. LB39 names this boundary itself — *"$r=0$: the uniform direction imbalance is conserved"* — (LB42) carries the coefficient explicitly, $\partial_tH=-\Omega\partial_\chi F+d\partial_\chi^2H-2rH$, (LB45) reduces the loop average to $\tfrac{d}{dt}\langle H\rangle_\chi=-2r\langle H\rangle_\chi$, and the frozen machinery already declares an arm at this point (`persistent_current`, horizon key `mode_zero_exchange`, `ZERO_EXCHANGE = 0.0`) and multiplies the right-hand side by `arm.exchange`. Nothing is imposed on the operators: one declared coefficient is set at a value the operator family and the theorem both carry.

**The prediction, written before the run.** At $r=0$ the mode-0 direction block vanishes and the mode-0 generator is $\mathrm{gen}_c\otimes\mathbb{I}$ with $\mathrm{gen}_c$ carrying the single null vector $(\varphi,1)$: the kernel over the declared modes is the whole two-dimensional direction space at the equilibrium ratio,

$$\boxed{\ \dim\ker(\text{mode }0)\ \big|_{r=0}=2\ }$$

with the two directions labelled — (i) the **direction-symmetric** combination, which is the spent body's retained coordinate $A$ itself, and (ii) the **direction-antisymmetric, $\chi$-uniform** imbalance $H$, the mode LB39's boundary hands back. Every mode $m\ge1$ keeps real part $-d m^2$ at $r=0$, so the count is exactly two and no other entry is touched. The invocation measures four things with declared branches:

| Branch | Read at | Values |
|---|---|---|
| (a) `present` | $T_3$ | `CONFIRMED_TWO`, `MEASURED_ONE`, `MEASURED_MORE`, `MEASURED_NONE` |
| (b) `writable` | one declared step, both directions | `WRITABLE_BOTH`, `UNWRITABLE_ONE`, `UNWRITABLE_NONE` |
| (c) `retained` | the final phase, against the published counterfactual | `RETAINED_BOTH`, `RETAINED_ONE`, `UNRETAINED` |
| (d) `erased independently` | $T_3$ of the counter-write arm | `ERASED_INDEPENDENTLY`, `MOVES_BOTH`, `RESIDUAL`, `RESERVED_NO_CHARGE` |

The design probe was run before this text was frozen and is recorded in §1.5 with the readings the floors and bands are chosen against; the branches it produced are disclosed there rather than predicted away, and §4 gate 7 checks the invocation reproduces them.

## 1. The reading, the two directions, and the pre-flight

### 1.1 Held fixed

Everything the chain fixes and the spent protocols carried unchanged: the profile `on_ray`, the mode-1 seed with $\alpha=0.25$ and $\beta=0.05$, the canonical companion, the projection, the RK4 integrator at $\Delta t=0.02$, the step rule $\Delta t\le1/(40\,\lambda_{\max})$ evaluated on the arm's own exchange, the shared exterior transport, the orientation-blind split geometry, the load family with the largest declared load $c=0.2$, the composition law $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$, the loop grid $N_\chi=24$, the three-phase schedule of three $450$-unit phases with the release samples of the spent write protocol, and the two established fits with the relaxation rate held or free. Exactly one thing moves: the exchange coefficient `exchange`, which §1.1.1 sets at the declared value on every arm.

#### 1.1.1 The declared parameter point

| Arm family | `exchange` | The point |
|---|---|---|
| every arm except the restored pair | $0.0$ | $r=0$: the second entry of (LB39) vanishes |
| `write_N_restored` and its own anchor `restored_anchor` | $0.6$ | the spent body's own point, where all three entries are positive |

The restored control is a declared *different* parameter point, present for one purpose: it measures the counterfactual decay that the exchange-free run predicts its second coordinate does not suffer. It is read against `restored_anchor`, an arm that carries the same exchange and the same load and no drive at all, because at the spent point a drive-free run already differs from the exchange-free baseline in the odd group by an amount larger than any charge this body writes: the seed's own uniform imbalance is conserved at $r=0$ and damped at $r=0.6$, so the two points do not share an odd-group equilibrium and each is read against its own.

### 1.2 The reading domain, declared coordinate by coordinate

This body reads the domain the spent body's §1.2 declared and its executor did not implement:

$$c_{s,k}(t)=\text{mean}_x\ q\big(F_{Y,s}(x,\chi_k),\,F_{I,s}(x,\chi_k)\big),\qquad s\in\{+1,-1\},\quad k=0,\dots,23,$$

with $F_{Y,s}$ and $F_{I,s}$ the two carriers' projections at orientation index $s$ (state axis 1) and loop sample $\chi_k=2\pi k/24$, the mean taken over the exterior grid (state axis 2 of the state, index 1 of the reduced composition array), and $q$ the bounded composition of §1.1.

| Item | Declaration |
|---|---|
| Coordinates | the $48$ numbers $c_{s,k}$: orientation $s$ is state axis 1, loop sample $k$ is state axis 3 |
| Reduction | `mean` over the exterior axis, so the reduced array carries the orientation and loop axes and the reading is indexed by $k=0,\dots,23$ |
| Meaning of one coordinate | the local composition of the carrier pair at one orientation and one phase of the loop modulation, averaged over the exterior structure |
| Norm | Euclidean over the coordinates of a block |
| Partition | the field's own orientation symmetry: even $e_k=(c_{+k}+c_{-k})/2$ and odd $o_k=(c_{+k}-c_{-k})/2$, each a $24$-vector |
| The two coordinates this body gates on | the $\chi$-uniform content of each group, $\bar e=\text{mean}_k\,e_k$ and $\bar o=\text{mean}_k\,o_k$ |
| Reported reductions | the $\chi$-nonuniform remainders $\lVert e_k-\bar e\rVert$, $\lVert o_k-\bar o\rVert$; the loop-mode content $\sum_k d_k\cos\chi_k$ at $k=6,18$; the established scalar $A$ |
| Domain probes | the two declared-shaped states of §1.4.3, built exactly as the §71 audit built them |

$\bar e$ is not a new observable, but it is not bit for bit the spent body's scalar coordinate either, and the difference is stated here rather than papered over. The spent chain's scalar $A$ reads $q$ on the **loop-averaged projection**, this body's $\bar e$ is the exterior mean of the **pointwise** composition, and since $q$ is concave in $\rho$ the two differ by a Jensen gap whenever the state carries structure along $\chi$. The identity that does hold is at the double mean and on $\chi$-uniform states, where both readers report the same numbers; the executor checks both in the domain probe (§1.4.3) and *reports* the Jensen gap on every sampled state as a recorded reading, so the spent chain's own $A$ remains comparable without being conflated with the declared coordinate.

### 1.3 The two directions, and the phase that counters one of them

One modulation, two declared channels and two declared magnitudes, applied to the state's own projected gate rate:

$$\kappa_{Y,s}(\chi)=\text{rate}\,\big(1+\delta_D\cos\chi+\delta_N\,s\big),\qquad \kappa_{I,s}(\chi)=\text{rate}\,\big(1-\delta_D\cos\chi+\delta_N\,s\big).$$

| Direction | $(\delta_D,\delta_N)$ | Gate fields | Acts on |
|---|---|---|---|
| D, the established carrier channel | `(1, 0)` at the declared carrier magnitude `delta_carrier` $=1$ | $\kappa_{Y}=\kappa_{I}=\text{rate}(1+\delta_D\cos\chi)$ | the even group's $\chi$-uniform content |
| N, the new orientation channel | `(0, 1)` at the declared orientation magnitude `delta_orientation` $=0.2$ | $\kappa_{Y,s}=\kappa_{I,s}=\text{rate}(1+\delta_N\,s)$, uniform in $\chi$ | the odd group's $\chi$-uniform content |
| joint | `(1, 1)` | the algebraic sum of the two modulations | both |
| counter-N | `(0, -1)` | $\text{rate}(1-\delta_N\,s)$, the sign reversed on the orientation | neither after the pairing: the change against N's own phase is $-2$ on the orientation channel and $0$ on the carrier one, which is absent in that phase |

The two magnitudes are declared separately, and the reason is a measured one. The orientation channel is a uniform change of the gate rate with the *sign of the orientation*, so at unit magnitude it drives one orientation's rate to zero and doubles the other's: a degenerate intervention whose counter-write cannot cancel, because $+\delta_N$ and $-\delta_N$ are not mirror images once the rate touches zero. The declared orientation magnitude is therefore $0.2$, small enough that the gate rate stays positive on both orientations and the injection and its counter stay in the same regime from either side, and large enough that the single-step action reading at the largest declared load is orders of magnitude above the readable floor. The carrier channel keeps the spent chain's own largest declared magnitude, and at `(1, 0)` and $1$ the executor's right-hand side is the spent executor's own direction-A line term for term, checked with `array_equal` before any arm is built. The counter-N phase reverses the orientation channel and applies no carrier channel, and the same pass asserts the declared $-2$ and $0$ change against N's own phase.

### 1.4 The pre-flight: readings on the seeded state, before integration

#### 1.4.1 The action readings

On the loaded seeded state (load $0.2$, one declared step $\Delta t=0.02$), the executor reads each direction's single-step displacement of each group's $\chi$-uniform content, as a fraction of that step's own drift:

| Reading | Quantity | Bound |
|---|---|---|
| live D | $\lvert\Delta\bar e_D\rvert/\text{drift}$ | $\ge$ `action_floor_live` $=10^{-3}$ |
| live N | $\lvert\Delta\bar o_N\rvert/\text{drift}$ | $\ge$ `action_floor_live` $=10^{-3}$ |
| cross D | D's odd action over N's odd action | $\le$ `cross_ratio_ceiling` $=0.05$: the first direction does not reach the new coordinate at anything like the new direction's own strength |
| cross N | N's even action over D's even action | $\le$ `cross_share_ceiling` $=0.5$ |
| null | $\lvert\Delta\bar e\rvert,\lvert\Delta\bar o\rvert$ with no write | exactly $0$ |
| distinctness | $\lvert\cos(u_D,u_N)\rvert$ on the declared $48$ coordinates | $\le$ `distinctness_ceiling` $=0.5$ |

The cross readings are ratios between the two directions' actions on the *same* coordinate rather than fractions of the step, because the composition is a nonlinear function of the densities: a drive on one density combination always reaches the other coordinate at second order, so an absolute ceiling would measure the drive's size rather than the directions' separation. N is even under the orientation exchange and its first-order action on the orientation-mean composition vanishes by that symmetry; what survives is second order in $\delta$ and is the `cross N` reading. The group cosines of each $48$-vector against each group's own unit vector are recorded in §2.6.

#### 1.4.2 The firing control

The same two readings are taken again at the largest load for N and at the ray load for N, so the statistic is shown to register a displacement at a declared magnitude (`live N` at load $0.2$ is the firing side) and to be exactly still where the declared physics says it must be (the ray arm, where the bracket vanishes identically and both terms are zero).

#### 1.4.3 The domain probes

The declared-shaped probes of §71 are rebuilt in the frozen executor, on states of the declared shape with the composition of the probe constant along one axis, plus a third probe that is constant in $\chi$:

| Probe | Declared reader `mean(axis=1)` row spread | Spent reader `composition_profile` row spread |
|---|---|---|
| loop-only (composition varies in $\chi$, constant in $x$) | $>0$: the declared domain resolves it | $0$: the transposed reduction sees a single row |
| exterior-only (composition varies in $x$, constant in $\chi$) | $0$: the declared domain averages it out | $>0$: the transposed reduction resolves the wrong axis |
| $\chi$-uniform (composition varies in $x$, constant in $\chi$, the probe on which both readers agree) | $0$ | $>0$; both readers' reported means agree within `probe_tol` |

Gate 2 requires the declared cells at their declared values, records both spent cells, and requires the two readers' means to agree on the $\chi$-uniform probe, so the transposition §71 reported cannot recur unnoticed, the readers are tied to each other where they must be, and the executor additionally asserts that its own reader is not the spent reader on the loop-only probe.

### 1.5 The design probe, run before the freeze and disclosed

`python computations/verify_loop_carrier_two_coordinates.py --design-probe` was run on the frozen machinery before this text was written, and the readings below are what the floors, bands and bounds of §2.3 are chosen against. The run is *not* a result: it is the same code path the invocation takes, executed once to fix declared numbers, and gate 7 requires the invocation to reproduce every value in the table to within `probe_tol`. The branches it produced are stated here rather than predicted away.

**Pre-flight** (fractions of the one step's drift $7.954800792364658\times10^{-5}$): live D $=1.0169\times10^{-2}$, live N $=8.9093\times10^{-2}$, cross D $=3.2158\times10^{-2}$, cross N $=7.5982\times10^{-2}$, distinctness $=1.7682\times10^{-2}$, the null exactly $0$ on both coordinates, the ray's two readings exactly $0$. The load reading is $0.3646114292316331$, the seeded family's own recorded transfer.

**Displacements against each arm's own declared baseline** ($\bar e/\bar o$, at $T_1$, $T_2$, $T_3$):

| Arm | $T_1$ | $T_2$ | $T_3$ |
|---|---|---|---|
| `ray_anchor`, `load_reference`, `restored_anchor` | $0$ | $0$ | $0$ |
| `write_D` | $-9.823123\times10^{-5}$ / $+3.418119\times10^{-6}$ | $-9.835534\times10^{-5}$ / $+3.422219\times10^{-6}$ | $-9.835534\times10^{-5}$ / $+3.422219\times10^{-6}$ |
| `write_N` | $0$ / $0$ | $-9.921615\times10^{-7}$ / $-8.957259\times10^{-5}$ | $-9.921567\times10^{-7}$ / $-8.957258\times10^{-5}$ |
| `write_N_restored` | $0$ / $0$ | $-3.935333\times10^{-8}$ / $-5.366332\times10^{-9}$ | $-3.935333\times10^{-8}$ / $0$ |
| `joint_DN` | $-9.823123\times10^{-5}$ / $+3.418119\times10^{-6}$ | $-9.922649\times10^{-5}$ / $-8.605159\times10^{-5}$ | $-9.922648\times10^{-5}$ / $-8.605158\times10^{-5}$ |
| `erase_N` | $-9.823123\times10^{-5}$ / $+3.418119\times10^{-6}$ | $-9.922649\times10^{-5}$ / $-8.605159\times10^{-5}$ | $-9.913681\times10^{-5}$ / $-8.548401\times10^{-5}$ |
| `ray_write_N` | $0$ / $0$ | $+2.22\times10^{-16}$ / $+1.04\times10^{-17}$ | same |

The graded branch readings the probe produced are: **(a) `CONFIRMED_TWO`** — the even coordinate stands at $T_3$ on `write_D` and `joint_DN` and the odd one on `write_N` and `joint_DN`, two standing against the predicted two; **(b) `WRITABLE_BOTH`** — both live readings above the floor and both channels charged at $T_2$; **(c) `RETAINED_BOTH`** — the D share $1.000000002$ and the N share $0.99999982$, with final-phase movements $2.9\times10^{-10}$ and $2.4\times10^{-8}$ of the standing level; **(d) `RESIDUAL`** — the counter phase removes $\rho_{\rm rem}=5.68\times10^{-7}/8.605\times10^{-5}=6.6\times10^{-3}$ of N's charge while the even coordinate holds, i.e. the reversed orientation channel moves the new coordinate only in its *even* (rate-magnitude) part and is not its inverse. That last reading is a finding about the channel, not about the kernel, and it is what the (d) branch records.

**The counterfactual, measured.** The restored arm's odd charge at $T_2$ is $-5.366\times10^{-9}$, and nothing of it stands at $T_3$: `write_N_restored:odd:t3` is exactly $0.0$ against its own exchange-matched anchor, while the identical channel at $r=0$ keeps $0.99999982$ of its charge. The analytic expectation is $e^{-2r\cdot450}=4.8\times10^{-235}$; the realized value is below the declared ceiling of $10^{-6}$ because the exchange term annihilates the direction-antisymmetric part exactly in the linear regime, and the two-point contrast — the same drive, the same load, the same window, one coefficient moved — is the measurement the branch publishes.

**Domain, spectrum, clock, entries.** The loop-only probe reads $7.376815905011214\times10^{-2}$ on the declared reader and exactly $0$ on the spent one, the exterior-only probe exactly $0$ and $6.938268539288772\times10^{-2}$, and the $\chi$-uniform probe $0$ and $6.595157827686915\times10^{-2}$ with the two readers' means agreeing exactly (difference $0.0$). The stored mode-0 generator gives $\dim\ker=2$ at $r=0$ (one symmetric, one antisymmetric, carrier residual $2.6\times10^{-16}$) and $\dim\ker=1$ at $r=0.6$ (symmetric alone), the declared entries read $\kappa(1+\varphi)=1.1268281293796237\times10^{-2}$, $2r=0$, $d=4.4982698961937725\times10^{-2}$, and the loaded anchor's clock fits $1.1268283368545141\times10^{-2}$ against the receipt's declared $1.119569724312185\times10^{-2}$, ratio $1.0064833948120457$ inside the carried tolerance $2.0$. The two spent scalars reproduce as $0.8923974885141064$ and $0.8923974885141089$ against the receipt's $0.8923974885141119$ and $0.8923974885141087$ (differences $5.6\times10^{-15}$ and $2.2\times10^{-16}$), and the Jensen gap between the declared coordinate and that scalar is $0.2322$ — recorded, not gated, and the reason §1.2 states the difference instead of claiming an identity.

**Step rule.** The tightest limit is the restored arm's $1/(40\lambda_{\max})=0.023611$ at $\lambda_{\max}=1.058814$; every arm satisfies $\Delta t=0.02$ against its own exchange.

## 2. Declared branches, statistics and thresholds

### 2.1 Read times

Three phases of $450$ units each: $T_1=450$ (end of phase 1), $T_2=900$ (end of phase 2), $T_3=1350$ (end of the final phase). The release window is the final phase, sampled at the spent chain's own horizons after $T_2$, and the two fits of §1.1 are applied to each gated coordinate's series over that window.

### 2.2 The declared arm table

| # | Arm | Load | Plan $(\delta_D,\delta_N)$ per phase | Read against |
|---|---|---|---|---|
| 1 | `ray_anchor` | $0.0$ | `(0,0)`, `(0,0)`, `(0,0)` | itself |
| 2 | `load_reference` | $0.2$ | `(0,0)`, `(0,0)`, `(0,0)` | itself |
| 3 | `restored_anchor` | $0.2$ | `(0,0)`, `(0,0)`, `(0,0)`, exchange $0.6$ | itself |
| 4 | `write_D` | $0.2$ | `(1,0)`, `(1,0)`, `(0,0)` | `load_reference` |
| 5 | `write_N` | $0.2$ | `(0,0)`, `(0,1)`, `(0,0)` | `load_reference` |
| 6 | `write_N_restored` | $0.2$ | `(0,0)`, `(0,1)`, `(0,0)`, exchange $0.6$ | `restored_anchor` |
| 7 | `joint_DN` | $0.2$ | `(1,0)`, `(0,1)`, `(0,0)` | `load_reference` |
| 8 | `erase_N` | $0.2$ | `(1,0)`, `(0,1)`, `(0,-1)` | `load_reference` |
| 9 | `ray_write_N` | $0.0$ | `(0,0)`, `(0,1)`, `(0,0)` | `ray_anchor` |

Nine declared arms, one execution each, $67\,500$ steps apiece. The three baselines hold zero displacement by construction, so gate 8 is a canary on the two anchors and on the restored point's own exchange.

### 2.3 Declared thresholds

| Row | Value | Where it comes from |
|---|---|---|
| `readable_floor_q` | `1.0e-12` | the spent chain's readable level |
| `silence_floor_q` | `1.0e-14` | the spent chain's silence level |
| `action_floor_live` | `1.0e-3` | the spent pre-flight floor |
| `cross_ratio_ceiling` | `0.05` | measured: the first direction's action on the new coordinate over the new direction's own |
| `cross_share_ceiling` | `0.5` | measured: the new direction's second-order action on the first coordinate over the first direction's own |
| `distinctness_ceiling` | `0.5` | the spent pre-flight ceiling |
| `null_ceiling` | `0.0` | exact: no write moves neither coordinate |
| `retention_share` | `0.5` | the spent chain's persistence branch, carried unchanged (`PERSIST_SHARE`) |
| `release_share` | `0.1` | the spent chain's release-window allowance, carried unchanged (`TRANS_SHARE`) |
| `persist_share` | `0.5` | the spent two-fit agreement band, lower |
| `trans_share` | `0.1` | the spent two-fit agreement band, upper allowance |
| `clock_tolerance` | `2.0` | the spent clock band |
| `nu_tolerance` | `2.0` | the spent rate band |
| `delta_carrier` | `1.0` | the spent chain's largest declared magnitude: the carrier channel reduces to its direction-A line exactly here |
| `delta_orientation` | `0.2` | declared: the orientation channel's magnitude, chosen so the gate rate stays positive on both orientations and the counter-write mirrors the write |
| `counterfactual_factor` | `4.8e-235` | $e^{-2r\cdot450}$ at $r=0.6$: what N's coordinate would do on the spent point's own clock |
| `restored_share_ceiling` | `1.0e-6` | measured: the share of N's charge standing at $T_3$ on the restored point, against the analytic $e^{-2r\cdot450}$; the same channel at $r=0$ must hold at or above `retention_share` |
| `anchor_oracle_tolerance` | `1.0e-9` | the exchange-free anchor against the spent receipt's $A_{\rm eq}$ |
| `domain_chi_floor` | `1.0e-3` | measured: the loop-only probe's declared row spread |
| `domain_exterior_ceiling` | `1.0e-15` | the exterior-only probe's declared row spread |
| `probe_tol` | `1.0e-12` | the design-probe reproduction band |
| `replication_tol` | `1.0e-15` | the stored-mode replication band |

### 2.4 The pre-flight's branch rule

If `live D` or `live N` is below `action_floor_live`, or either cross reading exceeds its declared ceiling (`cross_ratio_ceiling` for the first direction on the new coordinate, `cross_share_ceiling` for the new direction on the first), or the distinctness reading exceeds `distinctness_ceiling`, the branch rule is taken: the body reports that the declared coordinates do not separate the two directions at one step, reports (a)–(d) as unresolved, and closes. The null is a gate rather than a branch: a measure that moves when nothing is written is broken irrespective of the answer.

### 2.5 The four declared branches

* **(a) `present`.** `measured_standing` counts the groups whose $T_3$ displacement from their own baseline is at or above `readable_floor_q`, read on the two arms that charge them (`write_D` for the even group, `write_N` for the odd one, each with `joint_DN` as the second reading). The closed form predicts $2$; the branch is `CONFIRMED_TWO` on equality, `MEASURED_ONE` below, `MEASURED_MORE` above, `MEASURED_NONE` at zero.
* **(b) `writable`.** Both live readings at or above `action_floor_live` and both charged $T_2$ displacements at or above `readable_floor_q` give `WRITABLE_BOTH`; one gives `UNWRITABLE_ONE`; neither gives `UNWRITABLE_NONE`.
* **(c) `retained`.** For each coordinate, the share of its $T_2$ displacement standing at $T_3$, $s_g=\lvert x_g(T_3)-x_g^{\rm base}(T_3)\rvert/\lvert x_g(T_2)-x_g^{\rm base}(T_2)\rvert$, at or above `retention_share` with the movement across the final phase's last two release samples at or below `release_share` of itself is a retained coordinate. Both retained gives `RETAINED_BOTH`, one gives `RETAINED_ONE` (naming which), none gives `UNRETAINED`. The published counterfactual is the gap's own clock: the $\kappa(1+\varphi)$ direction would fall by $e^{-5.07}=6.3\times10^{-3}$ over the $450$-unit window, and N's coordinate on the spent point's clock by the `counterfactual_factor` — which the restored control arm measures rather than assumes. That measurement is read as a **share**, not as a fitted rate: on the restored point the surviving series sits at the round-off level where a rate fit has no meaning, so the recorded reading is the share of N's $T_2$ charge still standing at $T_3$ on `write_N_restored`, against the same share on `write_N` where the identical channel runs at $r=0$. The counterfactual passes when the restored share is at or below `restored_share_ceiling` and the $r=0$ share at or above `retention_share`.
* **(d) `erased independently`.** The counter phase is read **differentially**, against `joint_DN`: both arms write D then N, so both carry the same even charge, and only the final phase differs. The even group's write moves the odd group as well, because the composition is a nonlinear function of the densities and the first phase's charge shifts the gain through which the density imbalance appears in the composition; a counter-write read against a baseline that lacks that charge would therefore be measuring the first channel, not the second. The reading is $\rho_{\rm rem}=\lvert\bar o_{\rm erase}(T_3)-\bar o_{\rm joint}(T_3)\rvert/\lvert\bar o_{\rm joint}(T_3)-\bar o_{\rm joint}^{\rm base}(T_3)\rvert$, the fraction of N's charge the counter phase removes: $\rho_{\rm rem}\ge1-$`release_share` with the even coordinate holding at or above `retention_share` of its own $T_2$ value gives `ERASED_INDEPENDENTLY`; a smaller fraction with the first coordinate standing gives `RESIDUAL`; a removed odd charge with the first not standing gives `MOVES_BOTH`; neither gives `RESERVED_NO_CHARGE`. The absolute odd readings of `erase_N` are recorded beside the differential one.

### 2.6 Recorded, not gated

The $\chi$-nonuniform remainders of both groups, the mode-wise decay of each group's loop content, the Jensen gap between the declared coordinate and the spent chain's scalar, the two counterfactual shares, and the counter phase's differential effect on the odd group are recorded and deliberately outside the verdicts. The nonuniform remainders test the declared prediction that only the $\chi$-uniform content is ungapped at this point; the Jensen gap is the honest size of the difference §1.2 discloses ($0.2322$ in the design probe) and is the reason $\bar e$ is compared to the spent scalar only through the mechanisms §5 lists; and the two shares and the differential effect are the measured counterfactual and the measured erasure, which select branches rather than gates.

## 3. Sections 3 to 5 in outline

§3 is the arm table of §2.2, one spec each. §4 is the gate table: bindings, domain, null, anchors, live actions, distinctness, spectrum reproduction, the two fits' agreement, the clock and the four branches. §5 is the replication: the stored-mode generator against `closed_spectrum` at the arm's own exchange, the spent receipt's own scalar on both anchors, its recorded load transfer, and the counterfactual against the restored arm.

## 4. Gates, in the order they are reported

The status conjunction reads these fourteen gates only. The four branches of §2.5 and every reading of §2.6 are features, reported and deliberately outside it: a reserved branch is a recorded finding, not a failure.

1. `binding`: every §0 row matches, exact.
2. `reading domain`: the declared reader is the exterior mean over the $24$ loop samples and is not the spent reader; the loop-only probe's declared row spread is $\ge$ `domain_chi_floor`, the exterior-only probe's $\le$ `domain_exterior_ceiling`, and on the $\chi$-uniform probe the two readers' reported means agree within `probe_tol`.
3. `structure`: nonnegative states and $0\le q<1$ at every recorded state.
4. `loads and shape`: every declared load within `LOAD_TOL` relative, $9$ executions, at most `100000` steps per execution, at most `620000` total.
5. `schedule conformance`: `dt = 0.02 <= 1/(40 lambda_max)` on every arm's own exchange.
6. `the spectrum and the anchors against the spent chain`: `dim ker = 2` at $r=0$ with one symmetric and one antisymmetric kernel direction and the carrier ratio $\varphi$, $\dim\ker=1$ at $r=0.6$ with the symmetric direction alone, both spectra reproduced elementwise within `replication_tol`, the spent receipt's own scalar on both anchors within `anchor_oracle_tolerance`, and its recorded load transfer within `LOAD_TOL` relative. The Jensen gap between the declared coordinate and the spent scalar is recorded in the same row and not gated.
7. `design probe reproduction`: the invocation reproduces the declared probe readings within `probe_tol`.
8. `baselines hold the zero displacement`.
9. `silence on the ray pair`: `ray_write_N` at or below `silence_floor_q` at every read time.
10. `anchor readable on every arm charged an offset`.
11. `can-fail at the declared channel magnitudes`: `write_N`'s odd $T_2$ displacement at or above `readable_floor_q`, at `delta_orientation` $=0.2$ on the largest declared load.
12. `the null moves neither coordinate`, exactly zero.
13. `the declared clock`: the loaded anchor's own $\varepsilon$-excursion decay over the release window within `nu_tolerance` of the rate read live from the receipt.
14. `single invocation`: the receipt absent at start, one process.

## 5. Replication

The stored-mode generator is built from the frozen `mode_generator` at each arm's own exchange and its spectrum compared to `closed_spectrum` elementwise; the two null vectors are read from the audit's `kernel_structure` labels; the two anchors' *spent scalar* — the spent chain's own `coordinate` field, which every arm carries beside the two declared groups — is compared to the spent receipt's `load_reference` and `ray_anchor` final values, and the seeded family's recorded load transfer is compared to the spent receipt's own reading; and the restored arm's free rate is compared to $2r$. The declared coordinate $\bar e$ is *not* asserted equal to that scalar: it is the exterior mean of the pointwise composition and the scalar is the composition of the loop-averaged projection, so they differ by the concavity of $q$ in $\rho$, and the difference is published as a recorded reading rather than gated. Nothing here re-runs a spent arm: every other reading is read from the digest-bound receipts in §0 or computed from the frozen operators.

## 6. Cost and the stopping rule

| Row | Value |
|---|---|
| declared executions | `9` |
| steps per arm | `67500` |
| per-execution step cap | `100000` |
| total step cap | `620000` |
| declared `dt` | `0.02` |
| bound | `1800` seconds |
| measured seconds per step | `1.07e-3` |
| projected seconds, measured | `650.0` |
| projected seconds, assumed | `508.0` |

*(Amended in place on September 16, 2026, after the single invocation and at the user's instruction: the pre-amendment table read `bound` `900` seconds, `measured seconds per step` `6.665e-4` and `projected seconds, measured` `405.0`, and the paragraph below read `timeout 900 …`. §8.1 records the amendment, the frozen body's digest before and after it, and what did not move; ledger section 72 carries the repair accounting. Only the cost bound moved.)*

The bound is `1800` seconds because the first invocation's own timing was observed: the nine arms consumed about $650$ seconds of wall clock on this machine under load, against the $405$ seconds a lone design probe extrapolated. The first invocation integrated every arm and then failed in the gate path, writing no receipt; the repair is the one this protocol's stopping rule permits, and the bound is re-declared from the measurement rather than kept at the optimistic extrapolation.

The invocation is `timeout 1800 python computations/verify_loop_carrier_two_coordinates.py`, run once. *(Amended in place on September 16, 2026: the pre-amendment sentence read `timeout 900 python computations/verify_loop_carrier_two_coordinates.py`; §8.1 and ledger section 72 record the amendment, the digests on both sides of it, and the observation that no other declaration moved.)* A receipt at `runs/loop_carrier_two_coordinates/verification.json` closes the body; a failure that writes no receipt leaves it open for a repaired executor and a new commit.

The static pass additionally **drives the gate, feature and receipt path on shaped inputs**: because the invocation reaches that path only after every arm has been integrated, a key the path reads and its producers do not carry would otherwise cost a whole invocation to discover — as the first invocation's repair shows. The dry run builds one arm of the declared shape per spec from the real seed family and the real load reading, hands the assembly the real pre-flight, domain and operator readings, and requires the gate table, the feature record, the branch labels and the written payload to have their declared shape. Its verdicts are not readings and are discarded; only its exceptions and shape failures are static failures.

## 7. Interpretation boundary

This body measures whether the frozen generator's second conserved direction at $r=0$ is an actual retained coordinate of the field's own state, whether a declared drive can write it, whether it survives a release window on which the spent point's clock would erase it, and whether a counter-write removes it while the first coordinate stands. It does not measure the value of $\varphi$, the conversion ratio, the carrier identity, the QF1-to-carrier map, the phase law, the scale ratio, the quantum statistics, or whether any of these is a physical density or current: the ratio enters only through the declared entries of the four-population law, the point $r=0$ is a declared coefficient of the reduced description, and the load is a departure of the carrier state from the ray rather than a physical density or current. Nothing here re-runs the spent body or amends its frozen sections.

## 8. Post-execution record

Executed **once**, `timeout 1800 python computations/verify_loop_carrier_two_coordinates.py`, exit $0$, runtime $726.1$ s, receipt `runs/loop_carrier_two_coordinates/verification.json` (`46ae3ee2b93051277c6e1c86dce4c713fb3b397d74cb06c2559ff8e7b98f344e`). Frozen pair: protocol body `a2c6abe2f85b2c9c12e25fd7062ba4d12b8c640ef192c81bb8fc5e5c03c22f33`, executor `c13afe722904e91528956cd967705238041e963b0d46280b58fff0a54fd2d518`. Fourteen of fourteen gates pass and the status is `PASS`.

**The declared prediction holds.** $\dim\ker(\text{mode }0)=2$ at $r=0$ — one direction-symmetric direction and one direction-antisymmetric, $\chi$-uniform imbalance, carrier residual $2.61\times10^{-16}$ — and $1$ at the spent point $r=0.6$, symmetric alone. The declared point's entries read $\kappa(1+\varphi)=1.1268281293796237\times10^{-2}$, $2r=0$, $d=4.4982698961937725\times10^{-2}$.

**The four branches, as measured.** `CONFIRMED_TWO` — two coordinates standing against the predicted two, the even group at $-9.835534138125102\times10^{-5}$ and the odd at $-8.957259285831062\times10^{-5}$ from their own baselines. `WRITABLE_BOTH` — live D $1.0168673283524747\times10^{-2}$ and live N $8.909301878312713\times10^{-2}$ of one step's own drift $7.954800792364658\times10^{-5}$, cross D $3.215807665154746\times10^{-2}$, cross N $7.59819639630336\times10^{-2}$, distinctness $1.768154487316154\times10^{-2}$. `RETAINED_BOTH` — share $1.0000000019979542$ with final-phase movement $2.89\times10^{-10}$ for D, share $0.9999998175949137$ with movement $2.40\times10^{-8}$ for N. `RESIDUAL` — the counter phase removes $6.595670625788662\times10^{-3}$ of N's charge, read differentially against `joint_DN`, while the D charge holds; the channel's action on the new coordinate is even in its own sign to that order, so the injector is not an inverse.

**The counterfactual, measured rather than assumed.** On `write_N_restored` the identical drive at $r=0.6$ leaves share exactly $0.0$ of a $T_2$ charge of $-5.366331823353221\times10^{-9}$ against its own exchange-matched anchor, where the same channel at $r=0$ keeps $0.9999998175949137$; the analytic expectation is $e^{-2r\cdot450}=4.8\times10^{-235}$.

**The domain, as declared.** Declared shapes $(2,24)$, spent shapes $(2,7)$; loop-only probe $7.376815905011214\times10^{-2}$ declared against exactly $0.0$ spent; exterior-only exactly $0.0$ against $6.938268539288772\times10^{-2}$; $\chi$-uniform mean difference exactly $0.0$.

**Oracles.** The spent receipt's own scalars reproduce at $0.8923974885141064$ and $0.8923974885141089$ against $0.8923974885141119$ and $0.8923974885141087$; the seeded family's recorded load transfer at $0.3646114292316331$ within $9.07\times10^{-14}$ relative; the loaded anchor's clock at $1.1268283368545141\times10^{-2}$, ratio $1.0064833948120457$ inside the carried band $2.0$. The Jensen gap between the declared coordinate and the spent scalar is $0.2322333653463856$ over $81$ sampled states — recorded, not gated, and the quantitative form of the difference §1.2 states.

**One repair, disclosed.** The first invocation integrated all nine arms and then failed in the gate path on a latent `KeyError`, writing no receipt; §6's stopping rule permits one repair after such an invocation, and the repaired pair is committed separately. The static pass now drives the gate, feature and receipt path on shaped inputs and immediately found a second latent key (the clock fit's degenerate branch); the declared bound was re-derived from the observed runtime.

### 8.1 The amendment, the cost bound, and the three states of the frozen pair

Two passages *inside* the body range were corrected in place on September 16, 2026, after the single
invocation and at the user's instruction — §6's bound row set and §6's invocation sentence — and this
subsection is the accounting, because a bound inside the digested body must be readable without
reconstruction. The oracle for the first invocation is the commit that froze the text it ran under;
the oracle for the invocation that produced the receipt is the commit that carried the repaired pair;
and the standing text is this one.

| State | Commit | Bound | Seconds per step | Projected seconds | `frozen_body_sha256` | `executor_sha256` |
|---|---|---|---|---|---|---|
| the first freeze, under which the first invocation ran and wrote no receipt | `c6694976` | `900` | `6.665e-4` | `405.0` | `d16060dd28f5b8d34dbbb542e7a16d4dbccd3d23dabd4f5a0232d8bcc51758a0` | `114fd1876c0a4845060a8fb01e21464b39eec909b707c90dec278e3c6c49fc8c` |
| the re-frozen pair, under which the invocation that produced the receipt ran | `c88872f2` | `1800` | `1.07e-3` | `650.0` | `a2c6abe2f85b2c9c12e25fd7062ba4d12b8c640ef192c81bb8fc5e5c03c22f33` | `c13afe722904e91528956cd967705238041e963b0d46280b58fff0a54fd2d518` |
| this amendment, before the sweep that follows | this commit | `1800` | `1.07e-3` | `650.0` | `7fce9e0e3a252eef3e54be3cee016f2e1db453a7e9c25cdae98b873884678fbe` | `671e4a5edbe406f6c1f932d855987d5cc746315b10c13f387291bf15cbf778f0` |

**The change is a cost bound and nothing else moved.** The first invocation's own timing is what
re-declared the ceiling: nine arms of $67500$ steps cost about $650$ seconds of wall clock on this
machine under load, against the $405$ seconds a lone design probe extrapolated, so the ceiling went
from $900$ to $1800$ seconds and the projection from $405.0$ to $650.0$. No statistic, threshold,
tolerance, level, arm, gate, feature or decision rule moved at that re-declaration, and no other
number in the table moved either. The pair's own record of what *else* moved is kept separate and is
not folded into this accounting: before the re-declaration the same repair corrected a latent key
error in the gate path and rebuilt the static pass to drive that path on shaped inputs, which is
disclosed in §8 above and was in force at the invocation that ran — so the receipt's gates are the
repaired gates, and the failure the repair answered is a bookkeeping failure with no bearing on any
statistic. This amendment adds nothing to the body but the two in-place markers §6 now carries, each
naming the value the pre-amendment text read; it changes no declared value at all.

**The first invocation left neither a receipt nor a partial artifact.** `runs/loop_carrier_two_coordinates/`
holds exactly one file — the receipt of the second invocation, written at its end — and no temporary,
partial, stale or `*.tmp` artifact of any kind exists under `runs/`. The executor writes in exactly one
place: after the gate table has been printed, after `sanitize` has accepted every reading, and after
`os.makedirs` has made the receipt's directory; the first invocation failed inside the gate stage,
before any of those steps. Nothing was overwritten, because there was nothing to overwrite.

**A third invocation is refused in code, and this is the observed behaviour.** The receipt exists, so
`execute()` refuses before it checks the bindings and before any arm is constructed. Invoked again
after this amendment, this body's own executor printed

> `REFUSING TO RUN: runs/loop_carrier_two_coordinates/verification.json already exists; this body is invoked once and a second invocation is permitted only after an invocation that wrote no receipt.`

and exited `3`, with the receipt's digest unchanged and the directory still holding exactly that one
file. The same refusal is the reason this body cannot be re-run to produce a second reading: any
further measurement of the declared point needs a new frozen body, which is what the sweep that
follows this amendment is.
