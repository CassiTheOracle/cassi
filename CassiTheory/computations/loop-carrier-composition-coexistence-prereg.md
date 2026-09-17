# One Carrier, How Many Coordinates? The χ-Resolved Composition Profile Under Two Orthogonal Gate Directions

## Status: Pre-registered—September 16, 2026; not executed. The executor `computations/verify_loop_carrier_composition_coexistence.py` is frozen in the same commit as this text and refuses to run on a hash mismatch.

## 0. Freeze and binding

| Row | Value | What it binds |
|---|---|---|
| `frozen_body_sha256` | `09426b6829e93bc02e7e2d330f3158b6889eebddd620bee149d9b3267f147f25` | this file, sections 1–7: everything from `## 1.` to just before `## 8.` |
| `executor_sha256` | `3852eadbd434e021d1dc351820db06e6295c34c11270144b0826f6097b09f6b1` | `computations/verify_loop_carrier_composition_coexistence.py`, the complete executor frozen with this text |
| `prior_body_sha256` | `151ab43fbaf2cd8580679bca98d51a40cbac7adf275a799b0f06249aedb9c636` | `computations/loop-carrier-attractor-write-prereg.md` §1–§7, the body carrying the coordinate $A$ and the two retention fits |
| `prior_executor_sha256` | `740d0fc036721be5f1ee0fd5527fe54e771243113e13b7133be053f6439cf6c6` | `computations/verify_loop_carrier_attractor_write.py`, imported as a library: `coordinate_of`, `ray_distance_of`, `action_of`, `clock_of`, `fit_held`, `fit_free`, `read_clock` |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | `computations/verify_loop_to_bubble_projection.py`, the frozen discrete operators |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | `computations/verify_loop_carrier_projection_relaxation.py`, the seed family, the projection and the canonical companion |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | `computations/verify_loop_carrier_projection_split.py`, the executor whose gate line direction A must reduce to term for term |
| `gate_load_executor_sha256` | `be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac` | `computations/verify_loop_carrier_gate_load.py`, the executor carrying the loaded seed family, the load reading and the loader |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | `runs/loop_carrier_projection_relaxation/verification.json`, the relaxation rate both fits hold |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` | `runs/loop_carrier_projection_split/verification.json`, the cross-protocol oracle |
| `gate_load_protocol_body_sha256` | `c0d2fe37b8b4ee7673b1ec1a7c658f2bedb4eae6ad360516057d5ee9cdc843fa` | `computations/loop-carrier-gate-load-prereg.md` §1–§7, the load reading and the oracle load |
| `gate_load_receipt_sha256` | `471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1` | `runs/loop_carrier_gate_load/verification.json`, the measured load of the seeded family |
| `prior_receipt_sha256` | `5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200` | `runs/loop_carrier_attractor_write/verification.json`, the two retention branches this body's group fits carry |
| `successor_protocol_body_sha256` | `23fb4e9a545793752db259324c87a71da9045cbb04221d0c60ef9c50b6003372` | `computations/loop-carrier-attractor-write-successor-prereg.md` §1–§7, the retention verdict this body's single-coordinate branch is the successor of |
| `successor_executor_sha256` | `d92bdd1a12a0f3ce1640cf100a23ae5898f6e51bd078c03965f0ab086c68007e` | `computations/verify_loop_carrier_attractor_write_successor.py`, imported for its binding and its short-horizon oracle literal |
| `successor_receipt_sha256` | `45a79ed37826f809116d61694315f55689178b6aa2490b2ea24ff41aecb475ff` | `runs/loop_carrier_attractor_write_successor/verification.json`, the five replication readings of §1.5 |

The executor's `check_binding` compares all sixteen rows and then calls the successor's own binding check, so the rows that chain declares are verified here too and a disturbed operator module stops this run before any arm exists. No source in this table is a running process: every one is a file whose bytes the executor reads, hashes and refuses on.

**The stopping rule, in code and in the schedule.** The executor refuses with exit 3 and no receipt when any binding mismatches, when the successor receipt does not carry the declared relaxation rate or the four declared oracle literals, or when `runs/loop_carrier_composition_coexistence/verification.json` already exists. The last is §6's stopping rule: this body is invoked **once**, and a second invocation is permitted only after an invocation that wrote no receipt.

## Abstract

Two writes into one conserved scalar have nowhere else to go. The spent chain read the loop carrier's composition on exactly such a scalar — the exterior mean of the bounded composition, $A=\text{mean}_x\,q(E_Y,E_I)$ — and concluded `WRITES` and `STORES`. A coexistence test taken on that scalar can only ever return "it adds", in the same shape as the spent gate axis that had no way to act: a clean, confident, unmeasurable yes. This body therefore reads the carrier where the declaration itself resolves it — the per-orientation, per-loop-sample composition profile $c_{s,k}$ over the $24$ declared loop samples — and writes two gate directions into it at the largest declared magnitude:

* **direction A**, the established write: the conversion field is offset by $\delta\cos\chi$ between the two *carriers*, orientation-blind;
* **direction B**, new: the conversion field is offset by $\delta\,s\cos\chi$ between the two *orientations* of each carrier.

On the declared partition of the profile these two directions act on different coordinates: A on the even group $e_k=(c_{+k}+c_{-k})/2$, B on the odd group $o_k=(c_{+k}-c_{-k})/2$. Before any integration the executor reads each direction's one-step action **on the loaded seeded state, in both directions**, together with the cross terms and a no-write null, so a domain that cannot separate them says so before a single trajectory is run. If they are not distinguishable, that is the finding and the body closes there: the conserved level has one writable coordinate on this realization, and multi-item storage has to come from placement rather than from the carrier. No re-tuning of the observable, no hand-built basis the field itself does not expose.

Three verdicts come out of the one invocation:

| Verdict | Read at | Values |
|---|---|---|
| coexistence | $T_3=1350$, after the drive is removed for five relaxation times | `COEXIST_ADDITIVE`, `COEXIST_NONADDITIVE`, `INTERFERE`, `RESERVED_ONE_RETAINED`, `RESERVED_NOT_DISTINGUISHABLE` |
| erasure | $T_2=900$, with the drive held | `ERASES_ONE`, `RESIDUAL`, `MOVES_BOTH`, `RESERVED_NO_B` |
| composition, on the retained scalar $A$ | $T_3$ | reported, **not gated**: §8 carries it as a reported-not-gated line |

The design probe, run before this text was frozen, is recorded in §1.5 with the readings the floors, bounds and bands are chosen against and with the verdicts it produced — `RESERVED_ONE_RETAINED` and `RESERVED_NO_B`, on a pre-flight that passes. The answer is therefore known before the freeze and disclosed as such rather than predicted away: the invocation's job is to reproduce it, and gate 6 checks that it does.

## 1. The reading, the two directions, and the pre-flight

### 1.1 Held fixed

Everything the chain fixes and the spent protocols carried: the profile `on_ray`, the mode-1 seed with $\alpha=0.25$ and $\beta=0.05$, the canonical companion, the projection, the RK4 integrator at $\Delta t=0.02$, the step rule $\Delta t\le1/(40\lambda_{\max})$, the shared exterior transport ($\delta_u=0$), the orientation-blind split geometry of §66 ($\delta_{\text{orientation}}=0$), the load family of §67 with the largest declared load $c=0.2$, the composition law $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ with $\rho=e_Y+e_i$ and $\varepsilon=e_Y-\varphi\,e_i$, the retain/release fits of the spent write protocol with the relaxation rate held, and the loop grid $N_\chi=24$. Nothing in §1.1 is re-derived here; each piece is bound by the digest of the file that carries it.

### 1.2 The reading domain, declared coordinate by coordinate

The retained scalar of §69 is one conserved level. It is **reported** here and it carries no verdict. The reading domain of this body is the field's own resolution of that level:

$$c_{s,k}(t)=\text{mean}_x\ q\big(F_{Y,s}(x,\chi_k),\,F_{I,s}(x,\chi_k)\big),\qquad s\in\{+1,-1\},\quad k=0,\dots,23,$$

with $F_{Y,s}$ and $F_{I,s}$ the two carriers' projections at orientation index $s$ (declaration axis 1) and loop sample $\chi_k=2\pi k/24$, mean over the exterior grid (axis 2), and $q$ the bounded composition of §1.1.

| Item | Declaration |
|---|---|
| Coordinates | the $48$ numbers $c_{s,k}$: orientation $s\in\{+,-\}$ is state axis 1, loop sample $k=0,\dots,23$ is state axis 3 |
| Resolution | $\Delta\chi=2\pi/24=0.2617993877991494$ on the loop, the full exterior grid on the mean |
| Meaning of one coordinate | the local composition of the carrier pair at one orientation and one phase of the loop modulation, averaged over the exterior structure |
| Norm | Euclidean over the coordinates of a block; the $\chi$-resolved vector is never collapsed to a single ratio |
| Partition | the field's own orientation symmetry: even $e_k=(c_{+k}+c_{-k})/2$ and odd $o_k=(c_{+k}-c_{-k})/2$, each a $24$-vector |
| Reported reductions | per-orientation levels $\text{mean}_k\,c_{s,k}$; the established scalar $A$; and the loop-mode content of each group's displacement, $\sum_k d_k\cos\chi_k$ at $k=6,18$ |

The partition is not hand-built: it is the even and odd part of the profile in the orientation index, which is the same index the seed's own $\beta$ imbalance and the carriers' opposite signs live on. Nothing in the reading uses a coordinate the field does not expose.

### 1.3 The two directions, and the phase that counters one of them

One modulation, two declared coefficient pairs. For orientation $s$ and loop sample $\chi$ the gate fields are

$$\kappa_{Y,s}=\text{rate}\,\big(1+m_s(\chi)\big),\qquad \kappa_{I,s}=\text{rate}\,\big(1-m_s(\chi)\big),\qquad m_s(\chi)=\delta\,(\text{even}+s\,\text{odd})\cos\chi,$$

where `rate` is the state's own projected gate rate of §1.1 and $\delta=1$ on every write arm, the largest declared magnitude.

| Direction | `(even, odd)` | Gate fields | Acts on |
|---|---|---|---|
| A | `(1, 0)` | $\kappa_Y=\kappa_I=\text{rate}(1+\delta\cos\chi)$, orientation-blind | the even group |
| B | `(0, 1)` | $\kappa_{Y,s}=\text{rate}(1+\delta\,s\cos\chi)$, $\kappa_{I,s}=\text{rate}(1-\delta\,s\cos\chi)$ | the odd group |
| joint | `(1, 1)` | the algebraic sum of A's and B's modulations | both |
| counter-write | `(-1, 1)` | $0$ on $s=+$, $-2\delta\cos\chi$ on $s=-$ | neither: the change against the joint is $-2$ on the even coefficient and $0$ on the odd one |

Direction A is the spent split's own gate line: at `(1, 0)` this right-hand side is the split executor's `split_rhs(state, rate, delta_g=1.0)` term for term, and the executor checks that identity with `array_equal` before any arm is built (self-check). The counter-write's second-phase change is asserted against the declared $-2$ and $0$ in the same pass: the phase is an offset in the χ-cos drive strength that preserves the orientation asymmetry, so it touches the A coordinate and leaves the B coordinate's drive unchanged.

### 1.4 The pre-flight: four readings and a null, on the seeded state, before integration

The executor reads, on the loaded seeded state (load $0.2$, no integration beyond one declared step $\Delta t=0.02$), the group-resolved displacement of a single step with direction D against the same step with no write, as a fraction of that step's own profile change (the drift):

| Reading | Quantity | Bound |
|---|---|---|
| live A | $\lVert e_A\rVert_{\text{step}}/\text{drift}$ | $\ge$ `action_floor_live` $=10^{-3}$ |
| live B | $\lVert o_B\rVert_{\text{step}}/\text{drift}$ | $\ge$ `action_floor_live` $=10^{-3}$ |
| cross A | $\lVert o_A\rVert_{\text{step}}/\text{drift}$ | $\le$ `cross_ceiling` $=10^{-3}$: A must not move B's coordinate above the readable floor |
| cross B | $\lVert e_B\rVert_{\text{step}}/\text{drift}$ | $\le$ `cross_ceiling` $=10^{-3}$ |
| distinctness | $\lvert\cos(u_A,u_B)\rvert$ on the declared $48$ coordinates | $\le$ `distinctness_ceiling` $=0.5$ |
| null | $\lVert u_{\text{no-write}}\rVert$ | exactly $0$: with no write neither coordinate moves |

The distinctness reading is a firing control on the measure, not a formality: a domain that has collapsed the orientation axis, or a partition that is not the field's own, puts $u_A$ and $u_B$ on the same coordinates and reads $\pm1$. The pre-flight's verdicts are not gates, they select the branch of §2.4; the null is a gate, because a measure that moves when nothing is written is broken irrespective of what the answer is.

### 1.5 Design probe, before freezing

The design probe was run before this text was frozen: all eight declared arms once, on the same seeds, writing nothing. It produced the same fourteen gates and the same two verdicts this body is expected to produce at the invocation, and this section records that openly. Its readings fix the floors, bounds and bands above and the twelve declared group readings in §2.5.

**The pre-flight, on the seeded state, one declared step.** The step's own drift is $2.263927425497802\times10^{-3}$; the readings are the group norms of the single-step displacement as fractions of it:

| Reading | Even | Odd | Verdict against the declared bound |
|---|---|---|---|
| live A (`(1,0)`) | $2.575354\times10^{-6}$ ($1.1376\times10^{-3}$ of the drift) | $6.529026\times10^{-7}$ ($2.8839\times10^{-4}$) | `live_A` true, `cross_A` true ($2.8839\times10^{-4}\le10^{-3}$) |
| live B (`(0,1)`) | $6.424958\times10^{-7}$ ($2.8380\times10^{-4}$) | $2.547515\times10^{-6}$ ($1.1253\times10^{-3}$) | `live_B` true, `cross_B` true ($2.8380\times10^{-4}\le10^{-3}$) |
| null (no write) | exactly $0$ | exactly $0$ | `null_zero` true |
| distinctness $\lvert\cos(u_A,u_B)\rvert$ | $0.24572751316067618$ | — | `distinct` true ($\le0.5$) |
| the scalar action, the spent direction | live $0.05339073136188713$, silent $0.0$, the step's drift $6.248434071254305\times10^{-5}$ | — | reproduces the successor receipt exactly |

So the two directions are distinguishable on the declared coordinates at one declared step, each single write's action on the other's coordinate is at or below $7\times10^{-4}$ of the step, and the measure is exactly still when nothing is written. The pre-flight's branch rule of §2.4 is therefore not taken.

**The group displacement at the three read times.** The vector reading, as the norm of each group's $24$ coordinates against the arm's declared baseline:

| Arm | even, $t_1$ | odd, $t_1$ | even, $t_2$ | odd, $t_2$ | even, $t_3$ | odd, $t_3$ |
|---|---|---|---|---|---|---|
| `ray_write` | $4.299875\times10^{-16}$ | $0$ | $4.299875\times10^{-16}$ | $0$ | $4.299875\times10^{-16}$ | $0$ |
| `write_A` | $3.578250\times10^{-3}$ | $0$ | $3.585495\times10^{-3}$ | $2.937374\times10^{-16}$ | $3.585495\times10^{-3}$ | $0$ |
| `write_B` | $8.054469\times10^{-5}$ | $2.937374\times10^{-16}$ | $8.080466\times10^{-5}$ | $1.468687\times10^{-16}$ | $8.080466\times10^{-5}$ | $0$ |
| `joint_AB` | $3.661579\times10^{-3}$ | $7.185740\times10^{-8}$ | $3.669082\times10^{-3}$ | $4.379586\times10^{-10}$ | $3.669082\times10^{-3}$ | $0$ |
| `erase_A` | $3.661579\times10^{-3}$ | $7.185740\times10^{-8}$ | $3.668465\times10^{-3}$ | $4.379025\times10^{-10}$ | $3.668465\times10^{-3}$ | $0$ |

**What the probe already says, and what the invocation is for.** On the held reading, direction A's own group is retained — $3.578250\times10^{-3}$ at $t_1$ rising to $3.585495\times10^{-3}$ at $t_3$ — and direction B's own group never becomes readable: $2.937374\times10^{-16}$ at $t_1$, and exactly $0$ at $t_3$. B's entire retained footprint sits in the *even* group, at $8.080466\times10^{-5}$: a factor $44$ below A's, in A's coordinate, not in B's. The joint's odd coordinate holds $7.185740\times10^{-8}$ at $t_1$ and is back to $0$ at $t_3$, and the counter-write phase leaves the even displacement where the joint left it ($3.668465\times10^{-3}$ against $3.669082\times10^{-3}$). The probe's own verdicts are therefore `RESERVED_ONE_RETAINED` (coexistence) and `RESERVED_NO_B` (erasure), under the declared rules of §2.4 and with the pre-flight passing. Both outcomes are what §2.4 declares for these readings, and both are findings rather than failures; the invocation's job is to reproduce them, which gate 6 checks on all twelve declared numbers.

**Why the floors are the ones declared.** The retained scalar's own readability floor is $10^{-12}$ and its silence floor $10^{-14}$; §2.5 carries them, and the new floors are fixed against the readings above:

* `readable_level` $=10^{-12}$: the probe's numerical floor is $2.9\times10^{-16}$ and its smallest physical reading is B's $8.08\times10^{-5}$ cross-action, so this floor sits five decades above the noise and eight below the smallest real effect. Both verdicts are what §2.4 gives for *any* floor in $10^{-15}$–$10^{-6}$: the reserved branches are a plateau, not a threshold artifact, and the invocation's floors are not tuned to a branch.
* `silence_level` $=10^{-14}$: the ray pair reads $4.299875\times10^{-16}$, twenty-three times below it, and the spent chain's own silence floor is the same number.

**The scalar, disclosed as the naive reading.** The probe's scalar block at $t_3$ is $A$`(write_A)` $=0.8918038559489984$, $A$`(write_B)` $=0.8923841276699156$, $A$`(joint_AB)` $=0.8917899977049457$, $A$`(erase_A)` $=0.8917901001114138$, and the sum of the two singles' displacements from the reference $0.8923974885141119$ is $0.8917904951048021$: the joint and the sum of the singles agree to a part in $1.8\times10^{6}$. Two writes into one conserved level read additive whatever the χ-resolved profile says, which is precisely why §2.4 reports this block and refuses to gate on it.

## 2. The statistics and the decision rules

### 2.1 The groups and the displacement

The groups are the two $24$-vectors of §1.2. For an arm $X$ with declared baseline $R$ (its own load and seed, no write, same schedule) the displacement is

$$d_X^{g}(t)=\text{group}_g\big(c_X(t)-c_R(t)\big),\qquad g\in\{\text{even},\text{odd}\},$$

so every reading is a *difference against a matched trajectory*, which is what cancels the symmetry-breaking transport terms both arms share and leaves the write's own effect. Each baseline arm's displacement is identically zero by construction, and gate 7 requires that exactly.

### 2.2 The release window and the two fits

Each arm's release window reads the two group norms at the same five declared horizons as the spent chain, $30,90,180,300,450$ units after the removal of the drive, and fits each group's norm series with the two established fits: `fit_held` (the successor receipt's rate held) and `fit_free` (the declared deterministic rate search). The fits are recorded per group with their shares, rate ratios, residuals and one of four labels — `SILENT` when the peak is at or below the declared silence level, `RETAINED` when the held fit leaves at least `retention_share` of the terminal reading inside the declared residual band, `DECAYED` when the free fit leaves at most `release_share` of it and its rate is within a factor `clock_tolerance` of the declared one, `UNRESOLVED` otherwise. The self-check reaches all four labels on synthetic series.

**The fits are reported; they do not decide.** The verdicts of §2.4 are read on the direct coordinates at $T_2$ and $T_3$, and the fits stand beside them as the mechanism reading: a retained coordinate that decays back at the measured rate, and a coordinate that stays, are different objects even when one direct reading is marginal, and a disagreement between the two is visible in the receipt rather than hidden inside a rule.

### 2.3 The erasure reading

At $T_2$ the drive is still held, so a counter-write's effect is read as it happens. Two displacements are compared with the erase arm's, by magnitude and by direction, within `additive_band`:

* against the B-only arm's displacement: the erase arm left exactly what B wrote, i.e. the A coordinate was erased and B's stands;
* against the joint arm's displacement: the erase arm left what the joint wrote, i.e. the A coordinate survived the counter-write.

### 2.4 The verdicts

**Coexistence**, evaluated at $T_3=1350$, with the drive removed for the last $450$ units:

| Condition | Verdict |
|---|---|
| the pre-flight failed (any of its five readings) | `RESERVED_NOT_DISTINGUISHABLE` |
| either single write's own group is below `readable_level` at $T_3$ | `RESERVED_ONE_RETAINED` |
| both singles retained, and the joint's displacement matches A's on the even group and B's on the odd group within `additive_band` | `COEXIST_ADDITIVE` |
| both singles retained, and either of the joint's own groups is below `readable_level` where the single's was readable | `INTERFERE` |
| both singles retained, neither of the above | `COEXIST_NONADDITIVE` |

**Erasure**, evaluated at $T_2=900$, drive held:

| Condition | Verdict |
|---|---|
| the B-only arm's odd group is below `readable_level` at $T_2$ | `RESERVED_NO_B` |
| the erase arm matches B's displacement, and does not match the joint's | `ERASES_ONE` |
| the erase arm matches the joint's displacement | `RESIDUAL` |
| neither | `MOVES_BOTH` |

**Composition, on the retained scalar.** The joint arm's own $A$ at $T_3$, the two singles' $A$ at $T_3$, and the sum of the singles' displacements are computed and recorded as a `composition_reported_not_gated` block. They are the reading a coexistence claim would have been taken on if this body had been naive, and they are deliberately not promoted: two writes into one conserved level have nowhere else to go, so that reading is expected to look additive whatever the χ-resolved profile says. §8 carries it as a reported-not-gated line.

### 2.5 Thresholds, declared before execution

Carried unchanged from the spent chain, each declared here as a row so the executor's constant and this table are checked against each other:

| Row | Value | Why |
|---|---|---|
| `readable_floor_q` | `1e-12` | the spent chain's scalar readability floor, held by the imported fits |
| `silence_floor_q` | `1e-14` | the spent chain's scalar silence floor |
| `persist_share` | `0.5` | the spent chain's persist share |
| `trans_share` | `0.1` | the spent chain's transient share |
| `residual_band` | `0.25` | the spent fits' residual band, and this body's `additive_band` |
| `clock_tolerance` | `2.0` | the fitted rate's band around the declared clock |
| `nu_reference` | `0.01119569724312185` | the relaxation rate both fits hold, read live from the receipt |
| `nu_tolerance` | `2.0` | the release-window clock's band |
| `action_floor_live` | `0.001` | the spent chain's action floor, here the pre-flight's live bound |
| `action_ceiling_silent` | `1e-15` | the spent chain's silent-action ceiling |
| `load_tolerance` | `1e-12` | the declared load's relative tolerance |
| `load_absolute_floor` | `1e-15` | the zero-load absolute floor |
| `step_safety` | `40.0` | the step rule's safety factor |
| `declared_dt` | `0.02` | the declared step, in the chain's candidate set |

New here, each fixed against §1.5 before the freeze:

| Row | Value | Why |
|---|---|---|
| `readable_level` | `1e-12` | the group displacement below which a coordinate is not called readable; the spent scalar floor |
| `silence_level` | `1e-14` | the group displacement below which a displacement is called silent; the ray pair's own reading must sit under it |
| `cross_ceiling` | `0.001` | the pre-flight's cross-group action bound, the readable action floor itself |
| `distinctness_ceiling` | `0.5` | the pre-flight's direction-cosine bound; a collapsed domain reads $1$ |
| `null_ceiling` | `0.0` | the null is exact |
| `ray_readable_floor` | `0.000001` | every arm charged an offset must show a live $\varepsilon$ reading at the first read time |
| `retention_share` | `0.5` | the group fit's retained share |
| `release_share` | `0.05` | the group fit's released share |
| `additive_band` | `0.25` | the band on both the magnitude gap and the direction cosine for "the same displacement"; the spent residual band |
| `replication_tolerance` | `1e-15` | the successor replication, absolute |
| `probe_tolerance` | `1e-12` | the design-probe reproduction, relative |
| `replication_load_reference_at_t1` | `0.8923960494310218` | the successor's `loadmax_anchor` at the same time |
| `replication_write_a_at_t1` | `0.8918036475597466` | the successor's `supersplit_load` final coordinate |
| `replication_ray_write_at_t1` | `0.8923974885141087` | the successor's `ray_supersplit` final coordinate |
| `replication_write_a_ray_distance` | `0.0013261506410605264` | the successor's `supersplit_load` ray distance at that time |
| `replication_ray_write_ray_distance` | `4.615955614456139e-15` | the successor's `ray_supersplit` ray distance at that time |
| `oracle_scalar_action_live` | `0.05339073136188713` | the successor's scalar action at the largest load, re-read in the pre-flight |
| `oracle_scalar_action_silent` | `0.0` | the same on the ray seed, exact |
| `oracle_scalar_action_drift` | `6.248434071254305e-05` | the same step's own drift |
| `oracle_ray_rho` | `5.329147248815693e-16` | the successor's own short-horizon residual, the cross-protocol oracle of gate 13 |
| `phase_units` | `450.0` | one write phase and the release phase, five relaxation times each |
| `phase_steps` | `22500` | `phase_units / declared_dt` |
| `total_units` | `1350.0` | three phases |
| `total_steps` | `67500` | `total_units / declared_dt` |
| `horizons` | `30, 90, 180, 300, 450` | the release window's declared read times, the spent chain's own |
| `release_sample` | `46500, 49500, 54000, 60000, 67500` | those times as step indices from the start of the run |
| `bound_seconds` | `900.0` | the invocation's bound |
| `projected_seconds_measured` | `315.0` | `472600` declared steps at the measured `6.665e-4` s/step |
| `projected_seconds_assumed` | `396.0` | the same at the assumed `8.36e-4` s/step |
| `seconds_per_step_measured` | `0.0006665` | the successor run's measured rate |
| `seconds_per_step_assumed` | `0.000836` | the chain's assumed rate |
| `declared_executions` | `8` | the arm table of §3 |
| `per_execution_cap` | `100000` | above the longest declared arm |
| `total_step_cap` | `600000` | above the declared total |
| `probe_readings` | `3.5782503187010394e-03, 0.0000000000000000e+00, 8.0544689706744455e-05, 2.9373740229761033e-16, 3.6690824708873952e-03, 4.3795864823950710e-10, 3.6684648139275978e-03, 4.3790254439566828e-10, 3.5854949127067321e-03, 0.0000000000000000e+00, 3.6690824768987312e-03, 0.0000000000000000e+00` | the design probe's twelve group readings, in the order declared in §1.5 |

## 3. The declared arms

Eight arms, one invocation. The load is the largest declared load $c=0.2$ on every charged arm; $\delta=1$ on every write phase; the drive is removed in the third phase of every arm.

| # | Arm | Role | Load | Phase 1 `(even, odd)` | Phase 2 | Phase 3 | Baseline | Steps |
|---|---|---|---|---|---|---|---|---|
| 1 | `ray_anchor` | baseline | 0 | `(0, 0)` | `(0, 0)` | `(0, 0)` | itself | 67500 |
| 2 | `load_reference` | baseline | 0.2 | `(0, 0)` | `(0, 0)` | `(0, 0)` | itself | 67500 |
| 3 | `ray_write` | ray | 0 | `(1, 0)` | `(1, 0)` | `(0, 0)` | `ray_anchor` | 67500 |
| 4 | `write_A` | single | 0.2 | `(1, 0)` | `(1, 0)` | `(0, 0)` | `load_reference` | 67500 |
| 5 | `write_B` | single | 0.2 | `(0, 1)` | `(0, 1)` | `(0, 0)` | `load_reference` | 67500 |
| 6 | `joint_AB` | joint | 0.2 | `(1, 1)` | `(1, 1)` | `(0, 0)` | `load_reference` | 67500 |
| 7 | `erase_A` | erase | 0.2 | `(1, 1)` | `(-1, 1)` | `(0, 0)` | `load_reference` | 67500 |
| 8 | `step_short` | oracle | 0 | `(0, 0)` | `(0, 0)` | `(0, 0)` | itself | 100 |

**The ray pair.** `ray_anchor` is the ray seed with no write and no load; `ray_write` is the same seed with direction A held for the first two phases. On the ray the conversion bracket vanishes identically, so both gate terms multiply a zero and the two trajectories are the same trajectory: gate 8 requires the ray write's displacement to be at or below `silence_level` at all three read times, and the probe reads it as an exact zero.

**The counter-write's matching.** `erase_A` has the same total drive time as `joint_AB` and as `write_B`; its second phase flips only the even coefficient, from $+1$ to $-1$. Whatever the erase arm's displacement is at $T_2$ therefore isolates one thing: what a $-2$ change in the χ-cos drive strength does to coordinates another write established.

**The short arm.** `step_short` is the spent chain's own short-horizon construction (the relaxed seed, no load, no write, $100$ steps at $\Delta t=0.02$): its `rho` maximum must equal the successor receipt's own value exactly, which is the cross-protocol oracle of gate 13.

## 4. Gates, features and the decision rule

### 4.1 The fourteen gates

| # | Gate | Bound |
|---|---|---|
| 1 | binding | all sixteen rows exact, and the successor's own rows agree |
| 2 | structure | nonnegative states, $0\le q<1$, finite annihilation and idempotence maxima, every arm |
| 3 | loads and shape | every declared load within `load_tolerance` (`load_absolute_floor` at zero); `declared_executions`, `per_execution_cap`, `total_step_cap` |
| 4 | schedule conformance | $\Delta t\le1/(40\lambda_{\max})$ on every arm, $\Delta t$ in the declared candidate set |
| 5 | replication of the established constructions | the three composition coordinates within `replication_tolerance` of the successor receipt's values, and the two ray distances likewise |
| 6 | design probe reproduction | every declared probe reading within `probe_tolerance` relative |
| 7 | baselines hold the zero displacement | exactly zero, by construction |
| 8 | silence on the ray pair | $\le$ `silence_level` at all three read times |
| 9 | anchor readable on every arm charged an offset | the $\varepsilon$ reading $\ge$ `ray_readable_floor` at the first read time, on all five charged arms |
| 10 | can-fail at the largest declared magnitude | `write_A`'s even group at $T_1$ $\ge$ `readable_level` |
| 11 | the null moves neither coordinate | exactly `null_ceiling` |
| 12 | the declared clock, read live from the successor receipt | fitted release-window rate within `clock_tolerance`, and the receipt's rate equals the declared one |
| 13 | cross-protocol oracle | `step_short`'s `rho` maximum bit-identical to `oracle_ray_rho` |
| 14 | single invocation | receipt absent at start, one process, pid recorded |

### 4.2 Features, and the branch-selecting set explicitly outside the status conjunction

The status is `PASS` iff all fourteen gates pass. The following are **features**: they are recorded in the receipt and they select a branch of §2.4, and a false value is a finding rather than a failure.

| Feature | Reading | Selects |
|---|---|---|
| `F1_can_fail_fired` | gate 10 | nothing: a control, kept in the features because it is a reading about the largest declared magnitude |
| `F2_ray_silent` | gate 8 | nothing: the predicted-silence control |
| `F3_anchor_readable` | gate 9 | nothing: the charged-arm control |
| `F4_preflight_live_A`, `F5_preflight_live_B` | the two live readings | `RESERVED_NOT_DISTINGUISHABLE` when false |
| `F6_preflight_cross_A`, `F7_preflight_cross_B` | the two cross readings | the same branch |
| `F8_preflight_distinct` | the direction cosine | the same branch; this is the control that fires if the orientation axis has collapsed |
| `F9_retained_A`, `F10_retained_B` | the singles' own groups at $T_3$ | `RESERVED_ONE_RETAINED` when either is false |
| `F11_joint_readable` | the joint's own groups at $T_3$ | `INTERFERE` when false where a single was readable |
| `F12_additive_even`, `F13_additive_odd` | the two matches of §2.4 | `COEXIST_ADDITIVE` when both true |
| `F14_erase_matches_B`, `F15_erase_matches_joint` | the two matches of §2.3 | `ERASES_ONE`, `RESIDUAL` or `MOVES_BOTH` |

The split is declared so that a reader can check it: the gates are exactly the constructions, controls, budgets and replications of this body — things that must hold for any answer to be worth recording — and the features are the readings that *are* the answer. A run that returns `RESERVED_NOT_DISTINGUISHABLE` or `RESERVED_ONE_RETAINED` therefore returns `PASS` with a bound, not a failure with no result.

### 4.3 Decision rule

The status is the conjunction of the gates. The two verdicts come from §2.4 in the order written, first match wins, and the reported composition block of §2.4 is computed unconditionally.

### 4.4 What a verdict would and would not say

`COEXIST_ADDITIVE` would say that on this realization the χ-resolved profile carries the two directions as independent coordinates: each single write's displacement is retained at its own group after five relaxation times of release, and the joint's displacement is the superposition of the two within the declared band. `COEXIST_NONADDITIVE` would say both are retained and the superposition fails, which is the signature of a nonlinearity that mixes the two coordinates. `INTERFERE` would say the joint's own coordinate is unreadable where the single's was readable. `RESERVED_ONE_RETAINED` would say the second direction does not survive at all on this realization, so the question of coexistence is not yet asked. `RESERVED_NOT_DISTINGUISHABLE` would bound the carrier's storage dimension at one writable coordinate on this realization: whatever multi-item storage the framework wants then has to come from placement, not from the carrier, and this body closes there.

None of these is a statement about a different seed, a different load, a different modulation shape, or a longer hold. Nothing here is a claim that the carrier *can* store two items in general, and nothing here is a claim about the continuum equations the discretization approximates.

## 5. Pre-flight reachability, before any integration

### 5.1 The action check, both directions

The readings of §1.4 are taken on the actual loaded seeded state in the same process, before any arm is constructed. The self-check requires that the two live readings are at or above the action floor, that the two cross readings are at or below the cross ceiling, that the null is exactly zero, and that the scalar action (the spent coordinate's own one-step action at the largest load) still reproduces the successor receipt's `0.05339073136188713` and the ray seed's exact `0.0` — the continuity check that this body's right-hand side is the spent one on the spent direction.

### 5.2 The null, and why it is not vacuous

The null step is the same construction with $\text{modulation}=0$: the right-hand side reduces to the no-write one term for term, and the executor checks that reduction with `array_equal` on the seeded state. Its zero reading is therefore a check on the *measure* — that the group-resolved reading instrument reports nothing when nothing is written — and not a restatement of the algebra.

### 5.3 What the probe predicts

The probe of §1.5 is the only prediction this body makes about the answer. Its readings are recorded in the receipt and gated by gate 6, so the invocation is expected to reproduce them exactly; an invocation that does not is a failure of this body's own construction and not a discovery.

## 6. Run schedule, budget and stopping rule

| Item | Value |
|---|---|
| Executions | 8, one invocation, one process |
| Longest arm | 67500 steps |
| Total | $7\times67500+100=472600$ steps |
| Per-execution cap | 100000 |
| Total cap | 600000 |
| Measured rate (successor run) | $6.665\times10^{-4}$ s/step |
| Projection at the measured rate | $315$ s |
| Projection at the assumed rate | $396$ s |
| Bound | $900$ s (`timeout 900`) |
| Stopping rule | one invocation; a second only if the first wrote no receipt |

The bound leaves a factor $2.3$ over the measured projection and $2.9$ over the assumed one. Cost against the chain: this body is one invocation of about five minutes of integration, one added long arm (the ray anchor) relative to the six the body would need without it, and no new solver, no new seed family and no new fit — the two fits, the step rule, the load family and the coordinate are the spent chain's own code, imported and bound by digest.

## 7. Interpretation boundary

* The reading is a discretized diagnostic at $N_\chi=24$ and one exterior grid. A coordinate that is unreadable at this resolution is unreadable *here*; the continuum statement is not made.
* `RESERVED_NOT_DISTINGUISHABLE` bounds the *storage* dimension of this realization's conserved level under this pair of directions. It does not prove that no other modulation shape, other than the two declared, could act on a second coordinate.
* The two directions are declared, not derived. Direction B is not claimed to be the only orientation-antisymmetric modulation, and direction A is the spent write by construction, not by preference.
* Retained is measured over five relaxation times of release. A displacement that decays on a longer timescale than $450$ units reads as retained here.
* All verdicts are about the seeded state at the largest declared load $c=0.2$. No load sweep is run, and no claim about small loads is made.
* The reported composition block of §2.4 is a reading of the retained scalar, not a coexistence result; §8 states this explicitly.

## 8. Post-execution record

**One invocation, `status=PASS`.** The run of September 16, 2026 at pid $35748$ took $305.6$ s of the declared $900$ s bound and wrote `runs/loop_carrier_composition_coexistence/verification.json` (schema `cassi.loop-carrier-composition-coexistence.v1`): $8$ arms, $472{,}600$ steps, largest $67{,}500$, all fourteen gates pass, and the binding of §0 was verified before any arm was constructed — the executor read the frozen body's digest, its own sixteen rows and the successor's own rows, and refused had any of them moved. The design probe's twelve declared group readings were reproduced with zero mismatches (gate 6), and the successor's five recorded literals were reproduced exactly (gate 5, `mismatches: []`): the composition coordinates $0.8923960494310218$ (`load_reference`), $0.8918036475597466$ (`write_A`), $0.8923974885141087$ (`ray_write`) at $t_1$, and the ray distances $0.0013261506410605264$ and $4.615955614456139\times10^{-15}$. Direction A on this realization *is* the successor's own construction, not a look-alike.

**The two verdicts.**

| Verdict | Value | The readings it is read from |
|---|---|---|
| coexistence, at $T_3=1350$ | `RESERVED_ONE_RETAINED` | direction A's own group is retained at $3.585494912706732\times10^{-3}$; direction B's own group reaches exactly $0.0$ at $T_3$ ($2.937374\times10^{-16}$ at $T_1$, $1.468687\times10^{-16}$ at $T_2$, release-window peak exactly $0.0$, label `SILENT`) |
| erasure, at $T_2=900$ | `RESERVED_NO_B` | the B-only arm's odd group is $1.468687\times10^{-16}$ at $T_2$, below the $10^{-12}$ floor, so the counter-write's effect on B's coordinate is not yet askable |
| composition, on the retained scalar $A$ | **reported, not gated** (block below) | measured and deliberately not promoted |

**The reading that carries the answer: the group-resolved displacement at the three read times.** Each entry is $\lVert\cdot\rVert$ over that group's $24$ coordinates against the arm's declared baseline; the row label is the pair of `fit_held`/`fit_free` labels on the release window.

| Arm | even $T_1$ | odd $T_1$ | even $T_2$ | odd $T_2$ | even $T_3$ | odd $T_3$ |
|---|---|---|---|---|---|---|
| `ray_anchor` (baseline) | $0$ | $0$ | $0$ | $0$ | $0$ | $0$ |
| `load_reference` (baseline) | $0$ | $0$ | $0$ | $0$ | $0$ | $0$ |
| `ray_write` | $4.299875\times10^{-16}$ | $0$ | $4.299875\times10^{-16}$ | $0$ | $4.299875\times10^{-16}$ | $0$ |
| `write_A` (`RETAINED`/`SILENT`) | $3.578250\times10^{-3}$ | $0$ | $3.585495\times10^{-3}$ | $2.937374\times10^{-16}$ | $3.585495\times10^{-3}$ | $0$ |
| `write_B` (`RETAINED`/`SILENT`) | $8.054469\times10^{-5}$ | $2.937374\times10^{-16}$ | $8.080466\times10^{-5}$ | $1.468687\times10^{-16}$ | $8.080466\times10^{-5}$ | $0$ |
| `joint_AB` (`RETAINED`/`SILENT`) | $3.661579\times10^{-3}$ | $7.185740\times10^{-8}$ | $3.669082\times10^{-3}$ | $4.379586\times10^{-10}$ | $3.669082\times10^{-3}$ | $0$ |
| `erase_A` (`RETAINED`/`SILENT`) | $3.661579\times10^{-3}$ | $7.185740\times10^{-8}$ | $3.668465\times10^{-3}$ | $4.379025\times10^{-10}$ | $3.668465\times10^{-3}$ | $0$ |

Direction A's own group holds its offset over the release — the five samples are $3.5854949095055822\times10^{-3}$ to $3.585494912706732\times10^{-3}$, a change of $9\times10^{-13}$ of itself, where a state decaying at the measured clock would have fallen by $\mathrm{e}^{\nu\,450}=155$ (`fit_held` share $1.0000000000776$, residual $1.29\times10^{-10}$ against a band of $0.25$). Direction B's own group is silent: its release-window peak is exactly $0.0$, so no share, rate or residual is even defined for it, and its only retained footprint is the $8.080466\times10^{-5}$ it leaves in the *even* group — $2.25\%$ of A's.

**The finding, in the terms the steering asked for.** On this realization the carrier's conserved conversion level has **one retained writable coordinate**, not two. The reading domain separates the two declared directions at the level of a single declared step — the pre-flight's four readings and the null all hold: live A $2.5753540367077486\times10^{-6}$ on the even group against $6.529026343075532\times10^{-7}$ on the odd one, live B $6.424958490062066\times10^{-7}$ even against $2.547515185086473\times10^{-6}$ odd, cross terms at or below $3\times10^{-4}$ of the step, direction cosine $0.24572751316067618$, null exactly zero — but one step of action is not storage. Over the hold, B's own coordinate relaxes to nothing while its whole effect appears in A's coordinate, and the joint's own-coordinate match fails on the odd group (relative gap $0.9779768743087116$) while the even group matches to $0.022781598592640784$ with cosine $1.0$. So the second direction is not an independent storage coordinate here. Whatever multi-item storage the framework wants has to come from **placement** — from where in the state the item sits — rather than from a second writable coordinate of the carrier. That is the reserved branch, reported as the answer rather than as a failure, and this body closes here: no re-tuning of the observable, no hand-built coordinate basis, no second run.

**The erasure branch, and what the counter-write did anyway.** With B's coordinate unreadable at $T_2$ the declared rule stops at `RESERVED_NO_B`, so the vector-aware erasure question is not yet asked on this realization. The reading behind it is reported: the erase arm's even displacement ($3.668465\times10^{-3}$) matches the joint arm's ($3.669082\times10^{-3}$, relative gap $1.684\times10^{-4}$) and not the B-only arm's (gap $0.9779731662779862$), i.e. the counter-write phase left the A coordinate standing and did not erase it within the declared band, and its own even fit is `RETAINED` with share $1.0000000000769$ and residual $1.28\times10^{-10}$. So the non-independence reading is not merely asserted by the reserved branch: a $-2$ change in the χ-cos drive strength, applied for a full write phase to a coordinate another write had established, did not remove it.

**The retained scalar, reported and not gated.** The block `verdicts.composition_reported_not_gated` of the receipt:

| Quantity at $T_3$ | Value |
|---|---|
| $A$(`load_reference`), the reference | $0.8923974885141119$ |
| $A$(`write_A`) | $0.8918038559489984$ |
| $A$(`write_B`) | $0.8923841276699156$ |
| $A$(`joint_AB`) | $0.8917899977049457$ |
| $A$(`erase_A`) | $0.8917901001114138$ |
| sum of the two singles' displacements | $0.8917904951048021$ |

The joint and the sum of the two singles agree to $4.97\times10^{-7}$ absolute — $5.6\times10^{-7}$ of $A$ itself, $8.2\times10^{-4}$ of the displacement the two singles wrote. On the retained scalar the two writes read as one addition, exactly as they must: two writes into one conserved quantity have nowhere else to go. **This line is deliberately not promoted.** The verdict above is read on the χ-resolved profile, where the two directions are not independent, and a coexistence claim taken on this scalar would have returned "coexistence confirmed" with no way to be wrong.

**Controls, all firing.** The ray pair: `ray_write`'s displacement is $4.299875\times10^{-16}$ at every read time against a silence level of $10^{-14}$ — the write is present in the right-hand side and its bracket vanishes identically on the ray, so the arm moves nothing, and the two ray arms' coordinate, ρ and ray-distance readings agree to the last bits ($4.615955614456139\times10^{-15}$ against $4.615955614456136\times10^{-15}$). Can-fail at the largest declared magnitude: `write_A`'s even group reads $3.578250\times10^{-3}$ at $T_1$ against a readable floor of $10^{-12}$. Anchor readable on every arm charged an offset: $0.0013442651683720991$, $0.0013261506410605264$, $0.0013439919065751046$, $0.0013258627454986066$ and $0.0013258627454986066$ at $T_1$, against the ray arms' $4.6\times10^{-15}$ — a twelve-decade separation between the charged arms and the ray. The null moves neither coordinate: exactly $0.0$ on both groups. The clock is the realization's own: the release-window rate $0.011268281516184584$, ratio $1.0064832293591475$ to the $0.01119569724312185$ read live from the relaxation receipt over $[930,1350]$. The cross-protocol oracle is bit-identical: `step_short`'s ρ maximum $5.329147248815693\times10^{-16}$ equals the successor's own short-horizon residual. Structure over every recorded state: $q_{\max}=0.9227356957733256<1$, least state and projection nonnegative, annihilation maximum $3.26\times10^{-15}$, idempotence maximum $1.67\times10^{-16}$.

**Recorded, not gated.** Three readings carry information the verdicts do not consume. (i) The odd coordinate is not *unwritable*, it is *unretained*: the joint and erase arms hold $7.185740\times10^{-8}$ there at $T_1$ — nearly five decades above the readable floor, and more than eight above B's own odd reading at the same time ($2.937374\times10^{-16}$), while A's own odd reading is exactly $0.0$ — so the *pair* writes an odd component that neither single writes, and it is gone by $T_2$ ($4.379586\times10^{-10}$) and exactly $0.0$ at $T_3$. That is a nonlinear cross term of the two directions, and it is transient, not storage. (ii) The free fit's rate on a retained group is unidentified by construction: A's even group fits a free rate $1.88$ times the declared clock, which is inside the declared factor-$2$ band but describes a nearly flat series whose offset carries $0.9999999999995$ of the terminal reading — the `RETAINED` label rests on the held fit and this rate enters no clause. (iii) The charged arms' own distance from the ray relaxes across the hold, from $1.3261506410605264\times10^{-3}$ at $T_1$ to $4.9787389206375424\times10^{-8}$: what is retained is the composition coordinate's displacement, a conserved level, and the state itself comes back near the ray while it does. The x-resolution, the mode set, the load $c=0.2$, the modulation shapes $m$ and the two fits are all as declared in §1; the reserve is what §7 says it is — a bound on this realization's storage dimension under these two declared directions, not a proof that no other modulation could reach a second coordinate.
