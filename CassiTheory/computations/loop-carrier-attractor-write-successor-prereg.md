# Does the Gate Write Something the Carrier Keeps? The Loop-Carrier Composition Offset Under a Split Gate Held and Then Removed

## Status: Pre-registered—September 16, 2026; not executed. The executor `computations/verify_loop_carrier_attractor_write_successor.py` is frozen in the same commit as this text and refuses to run on a hash mismatch.

## 0. Freeze and binding

| Row | Value | What it binds |
|---|---|---|
| `frozen_body_sha256` | `23fb4e9a545793752db259324c87a71da9045cbb04221d0c60ef9c50b6003372` | this file, sections 1–7: everything from `## 1.` to just before `## 8.` |
| `executor_sha256` | `d92bdd1a12a0f3ce1640cf100a23ae5898f6e51bd078c03965f0ab086c68007e` | `computations/verify_loop_carrier_attractor_write_successor.py`, the complete executor frozen with this text |
| `prior_body_sha256` | `151ab43fbaf2cd8580679bca98d51a40cbac7adf275a799b0f06249aedb9c636` | `computations/loop-carrier-attractor-write-prereg.md` §1–§7, the body family (i) replicates |
| `prior_executor_sha256` | `740d0fc036721be5f1ee0fd5527fe54e771243113e13b7133be053f6439cf6c6` | `computations/verify_loop_carrier_attractor_write.py` as it stands, imported as a library: its arm machinery, its two fits, its branch rule and its synthetic witnesses |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | `computations/verify_loop_to_bubble_projection.py`, the frozen discrete operators |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | `computations/verify_loop_carrier_projection_relaxation.py`, the successor probe carrying the seed family and the projection |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | `computations/verify_loop_carrier_projection_split.py`, the executor carrying the common gate split and its step |
| `gate_load_executor_sha256` | `be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac` | `computations/verify_loop_carrier_gate_load.py`, the executor carrying the loaded seed family and its own loader |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | `runs/loop_carrier_projection_relaxation/verification.json`, the relaxation rate held by both families |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` | `runs/loop_carrier_projection_split/verification.json`, the cross-protocol oracle |
| `gate_load_protocol_body_sha256` | `c0d2fe37b8b4ee7673b1ec1a7c658f2bedb4eae6ad360516057d5ee9cdc843fa` | `computations/loop-carrier-gate-load-prereg.md` §1–§7, the load reading and the oracle load |
| `gate_load_receipt_sha256` | `471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1` | `runs/loop_carrier_gate_load/verification.json`, the measured load of the seeded family |
| `prior_receipt_sha256` | `5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200` | `runs/loop_carrier_attractor_write/verification.json`, the twelve arm readings family (i) must reproduce |

The executor's `check_binding` compares all thirteen rows and then calls the predecessor's own binding check, so the ten rows that chain declares are verified here too and a disturbed operator module stops this run before any arm exists. No source in this table is a running process: every one is a file whose bytes the executor reads, hashes and refuses on.

**The predecessor's two moving parts are declared, not hidden.** The spent protocol's body was amended after its single invocation (two slips corrected in place: its §6 steps row and its §2.3/§4.3 instrument symbol) and its executor was re-anchored with it, which is why the executed digests differ from the standing ones; its own §8.7 records both pairs, and its receipt records the pair that actually ran. `prior_body_sha256` and `prior_executor_sha256` above are the standing values — the body as bound and the executor as it is imported.

**The stopping rule, in code and in the schedule.** The executor refuses with exit 3 and no receipt when any binding mismatches, when the successor receipt does not carry the declared relaxation rate, or when `runs/loop_carrier_attractor_write_successor/verification.json` already exists. The last is §6's stopping rule: this body is invoked **once**, and a second invocation is permitted only after an invocation that wrote no receipt.

## Abstract

The spent protocol asked whether an asymmetric gate **writes** the carrier's composition coordinate or only **shakes** it, and answered every one of its seven declared split sizes `PERSIST` — at 96–104% of the terminal reading, with the transient prediction off by a factor 21 — and then failed its own attribution gate and issued no verdict, because the executor recorded each arm's distance from the ray only for arms carrying a twin, so the one arm that gate is about recorded nothing. This protocol is the successor body that failure calls for. It re-runs the write on the same arms, seed family, horizons and fits with the reading taken on every arm, and it adds the question the spent razing of the gate cannot answer: **when the split is removed, does what it wrote stay?**

Two families share one run and one seed family. Family (i) reads the composition coordinate's displacement from its unsplit anchor at five horizons with the split held, in both fits, and issues `WRITES`, `PERTURBS_ONLY` or `INCONCLUSIVE`. Family (ii) holds the same split to the same long horizon, then **removes it** and integrates on for a further five horizons spanning 4.7 relaxation times, fitting the same two-parameter offset with the relaxation rate held at the successor receipt's own measured value. Its verdict is `STORES` if the displacement survives the removal, `RELEASES` if it decays back at the measured rate, `MOOT` if family (i) says nothing was displaced, and `INCONCLUSIVE` if it does neither cleanly. The joint label names the four joints: `memory`, `knob`, `no-write`, `undecided`.

The design probe, run before this text was frozen, reads `WRITES` and `STORES` at every declared split size: the post-release readings are flat to within four parts in $10^4$ of themselves over five relaxation times, where a driven state would have fallen by a factor $110$. The run is expected to reproduce that, and it is disclosed rather than predicted away.

## 1. What is held fixed, what is written, and what is removed

### 1.1 Held fixed

Everything the chain fixes and the spent protocol carried: the profile `on_ray`, the mode-1 seed with $\alpha=0.25$ and $\beta=0.05$, the four-population law's declared entries, the canonical companion, the projection, the RK2 integrator at $\Delta t=0.02$, the step rule $\Delta t\le1/(40\lambda_{\max})$, the common projected gate of §66 with its split $\delta_g$, the shared exterior transport ($\delta_u=0$), the load family of §67 with the largest declared load $c=0.2$, the composition coordinate

$$A=\Big\langle\ \text{mean}_x\,q(E_Y,E_I)\ \Big\rangle,$$

and the second family's reference, which is the same unsplit arm family (i) measures its split arms against. Nothing in §1.1 is re-derived here; each piece is bound by the digest of the file that carries it.

### 1.2 The two families, in one run

| | Family (i): the write, replicated | Family (ii): retention |
|---|---|---|
| Split | held for the whole trajectory | held to $T_{\rm hold}=450$, then **removed**: the step becomes the split's own $\delta_g=0$ branch, which is the unsplit arm's step term for term |
| Read at | $T=30,90,180,300,450$ | $t=30,90,180,300,450$ **after the removal**, i.e. $T=480$ to $900$ |
| Reference | the unsplit anchor's trajectory | the same anchor, continued to $T=900$ |
| Statistic | $D(T)=A_{\rm split}(T)-A_{\rm anchor}(T)$ | the same difference, read after the split is gone |
| Fits | rate held at the receipt's $\nu$, and rate free | the same two fits, on the post-release window |
| Branch vocabulary | `PERSIST`, `TRANS`, `UNRESOLVED`, `BELOW_FLOOR` | `RETAINED`, `RELEASED`, `PARTIAL`, `BELOW_FLOOR`, `MOOT` |
| Verdict | `WRITES`, `PERTURBS_ONLY`, `INCONCLUSIVE` | `STORES`, `RELEASES`, `MOOT`, `INCONCLUSIVE` |

The two families are one schedule, not two runs: the retention arms' held phase **is** the corresponding family (i) arm's construction (same seed, same load, same split, same step, same horizon), so their held-phase readings must reproduce family (i)'s at the same split size to the last bit, and the release is the only difference between them. Gate 22 checks that identity arm by arm and the executor records the held-phase readings with the post-release ones; the run is not two measurements of two things.

### 1.3 The clock and the horizons, and the calibration arithmetic

The rate both families hold is the successor's own, read live from the digest-bound receipt `runs/loop_carrier_projection_relaxation/verification.json` at the field `relaxation.arms.relax_reference.fit.nu_fit`, and checked in the run against the declared literal:

$$\nu=1.119569724312185\times10^{-2}\ \text{per unit time},\qquad 1/\nu=89.3197\ \text{units}.$$

| Quantity | Value | Why |
|---|---|---|
| Horizons | $30,\,90,\,180,\,300,\,450$ | five declared, distinct, spanning $\nu\,(450-30)=4.7022$ nats of exponential weight |
| Tail at the last horizon | $e^{-\nu\,450}=6.4863\times10^{-3}$ | below the declared fraction $10^{-2}$, i.e. the largest horizon carries under one percent of the transient |
| Declared threshold for the last horizon | $\ln(10^{2})/\nu=411.334$ | the smallest $T$ with a one-percent tail; the last horizon $450$ is above it |
| Hold horizon | $T_{\rm hold}=450$ | $\ge5/\nu=446.60$: the write is established to below one percent of its own transient before it is removed |
| Hold tail | $e^{-\nu\,450}=6.4863\times10^{-3}$ | the same one-percent declaration, applied to the write rather than to the release |
| Release window | $450$ to $900$ | five horizons after the removal, spanning the same $4.7022$ nats |
| Write-phase clock window | $[30,450]$ | the fitted rate of the anchor's own $\rho$ over the write phase |
| Release-phase clock window | $[480,900]$ | the same fit over the release phase, which is the licence family (ii)'s held rate needs |

Both clocks are gated against $\nu$ within a factor $2$; the release-phase clock is the new one, and without it a held rate could not be applied to the post-release fit at all.

### 1.4 Relation to the predecessor: the correction that is the reason for this protocol

The spent body, its arms, its horizons, its fits, its branch rule, its law and its instrument are carried unchanged; the digits family (i) produces are the predecessor's, and gate 17 checks that arm by arm against the predecessor's own receipt. Two things change, and only these two:

1. **Every arm's distance from the ray is taken on its final state, the anchors included.** In the spent run that reading was recorded only for arms carrying a twin, which excludes exactly the two anchors, so the gate that checks the *reference* sits on the ray — the gate that makes an offset in a split arm attributable to the split — read `null` and the run ended `FAIL`.
2. **The reference arms run the full hold-and-release span.** They have to: family (ii) needs the same unsplit trajectory past $T_{\rm hold}$. The write family's arms still run the hold span alone, and their readings are the prefix of the longer run, which is why gate 17 can ask for exact equality rather than a tolerance.

The measured amendment reading the spent protocol's §8.7 states outside its run — the loaded anchor's $\max|\varepsilon|/\max|\rho|$ at $T_{\rm max}=450$, $1.3442651683720991\times10^{-3}$ — is declared here at full precision and gate 16 checks the successor's own anchor against it. That is the one number in this protocol that was not measured by a run of its own body.

### 1.5 Design probe, before freezing

Everything below was measured before this text was frozen, with the same imported modules, the same seeds, the same split, the same horizons and the same schedules the executor declares, by the executor's own `--design-probe` mode, which writes nothing and is not part of the run. It is disclosed because the declared floors, bands and thresholds are chosen against it, and the run is expected to reproduce it.

Family (i), the write, over the seven declared split sizes (the predecessor's readings, reproduced):

| Arm | $\delta_g$ | $D_\infty^{\rm held}$ | $D_\infty^{\rm free}$ | share of terminal | free rate / $\nu$ | branch |
|---|---|---|---|---|---|---|
| `decade_1` | $10^{-6}$ | $-3.196567330\times10^{-10}$ | $-3.303508092\times10^{-10}$ | $0.9591$ | $4.0944$ | `PERSIST` |
| `decade_2` | $10^{-5}$ | $-3.196581257\times10^{-9}$ | $-3.303522902\times10^{-9}$ | $0.9591$ | $4.0944$ | `PERSIST` |
| `decade_3` | $10^{-4}$ | $-3.196811381\times10^{-8}$ | $-3.303734981\times10^{-8}$ | $0.9591$ | $4.0944$ | `PERSIST` |
| `decade_4` | $10^{-3}$ | $-3.199120887\times10^{-7}$ | $-3.305861320\times10^{-7}$ | $0.9591$ | $4.0944$ | `PERSIST` |
| `decade_5` | $10^{-2}$ | $-3.222219065\times10^{-6}$ | $-3.327127446\times10^{-6}$ | $0.9594$ | $4.0944$ | `PERSIST` |
| `decade_6` | $10^{-1}$ | $-3.453442353\times10^{-5}$ | $-3.540014041\times10^{-5}$ | $0.9623$ | $4.0944$ | `PERSIST` |
| `supersplit_load` | $1$ | $-5.800237159\times10^{-4}$ | $-6.141123877\times10^{-4}$ | $0.9791$ | $0.2442$ | `PERSIST` |

with the law $\lvert D_\infty\rvert=(4.3424057234641914\times10^{-4})\,\delta_g^{1.0302448806878108}$ labelled `PROPORTIONAL`, its instrument $\delta_w=4.129022977646817\times10^{-9}$, the ray arm exactly silent ($\Delta$ exactly $0.0$ at all five horizons, peak $3.330669\times10^{-16}$), the can-fail control at $5.924019\times10^{-4}$, and the two clocks $1.1375969997251654\times10^{-2}$ (ratio $1.016102$) and $1.1268285328754471\times10^{-2}$ (ratio $1.006484$).

Family (ii), retention, over the four declared split sizes:

| Arm | $\delta_g$ | written offset | $D_\infty^{\rm held}$ | $D_\infty^{\rm free}$ | share of written | free rate / $\nu$ | branch |
|---|---|---|---|---|---|---|---|
| `retain_1` | $10^{-3}$ | $3.1991208866120801\times10^{-7}$ | $-3.3358050312383746\times10^{-7}$ | $-3.335788\times10^{-7}$ | $1.0427$ | $1.8005$ | `RETAINED` |
| `retain_2` | $10^{-2}$ | $3.2222190653455414\times10^{-6}$ | $-3.3587960350257283\times10^{-6}$ | $-3.358779\times10^{-6}$ | $1.0424$ | $1.7997$ | `RETAINED` |
| `retain_3` | $10^{-1}$ | $3.4534423534314694\times10^{-5}$ | $-3.5889430143274970\times10^{-5}$ | $-3.588926\times10^{-5}$ | $1.0392$ | $1.7896$ | `RETAINED` |
| `retain_supersplit` | $1$ | $5.8002371593543804\times10^{-4}$ | $-5.9244410183651049\times10^{-4}$ | $-5.924423\times10^{-4}$ | $1.0214$ | $1.7092$ | `RETAINED` |

The post-release readings themselves, at $t=30,90,180,300,450$ after the removal:

| Arm | readings |
|---|---|
| `retain_1` | $-3.335587995\times10^{-7}$, $-3.335728480\times10^{-7}$, $-3.335778790\times10^{-7}$, $-3.335787435\times10^{-7}$, $-3.335788188\times10^{-7}$ |
| `retain_2` | $-3.358578712\times10^{-6}$, $-3.358719353\times10^{-6}$, $-3.358769753\times10^{-6}$, $-3.358778430\times10^{-6}$, $-3.358779170\times10^{-6}$ |
| `retain_3` | $-3.588722705\times10^{-5}$, $-3.588864927\times10^{-5}$, $-3.588916318\times10^{-5}$, $-3.588925236\times10^{-5}$, $-3.588926003\times10^{-5}$ |
| `retain_supersplit` | $-5.924190722\times10^{-4}$, $-5.924348973\times10^{-4}$, $-5.924410197\times10^{-4}$, $-5.924421474\times10^{-4}$, $-5.924422488\times10^{-4}$ |

Three things are read off that table and declared here so the run is not asked to discover them. First, the displacement is **flat** after the removal: over five relaxation times the reading moves by at most $3.9\times10^{-4}$ of itself, and by under $6.1\times10^{-5}$ of itself at the three smaller levels, where a state decaying at the measured rate would have fallen by a factor $e^{\nu\,420}=110$ between the first and the last reading; the retained fraction is $1.02$–$1.04$ of what family (i) wrote, i.e. slightly more, because the released trajectory continues its own transient for a while before it saturates. Second, the free fit's rate is $1.71$–$1.80$ times the declared clock, inside the band but at its slow side; that rate is recorded and enters no clause that decides the branch. Third, the ray arm is exactly silent in the release phase too, and the can-fail control's post-release peak is $5.924422\times10^{-4}$. The retention table's $D_\infty^{\rm free}$ column is quoted at the precision the probe's own mode prints; the four held-fit offsets it also prints are declared at full precision in the `probe_retention_offsets` row of §2.5, which is what gate 20 compares against.

The two fits' own residuals, in the same order:

| Arm | `residual_held` | `residual_free` |
|---|---|---|
| `retain_1` | $7.962386\times10^{-6}$ | $5.932632\times10^{-8}$ |
| `retain_2` | $7.911307\times10^{-6}$ | $5.901954\times10^{-8}$ |
| `retain_3` | $7.428166\times10^{-6}$ | $6.191054\times10^{-8}$ |
| `retain_supersplit` | $4.666750\times10^{-6}$ | $8.626462\times10^{-8}$ |

All eight sit far inside the declared `residual_band` of $0.25$, so both fits describe their readings at all four levels.

The probe's own verdicts are `WRITES`, `STORES` and the joint label `memory`. The run is expected to reproduce all of it: the same construction on the same seed gives the same numbers, and gate 20 checks the four retention offsets against the literals above.

## 2. The statistics and the decision rules

### 2.1 The reading, carried

The reading is the composition coordinate $A$ of the projection, and the statistic is the difference between a split arm's own trajectory and its unsplit anchor's, at the declared horizons of one run. Each reading set is fitted twice, exactly as in the spent protocol:

$$D(T)=D_\infty+(D_0-D_\infty)\,e^{-\nu T},\qquad\text{fit H with }\nu\text{ held at the receipt's value, fit F with }\nu\text{ free on the declared deterministic scan.}$$

Both fits are linear least-squares solves given their rate, so no optimiser, no seed and no iteration tolerance enters; the free rate is resolved on a declared log grid in $[\nu/4,4\nu]$ and refined by declared relative widths. A branch is issued only where the two fits agree, because a held rate wrong by a few percent makes a pure transient look like an offset — §5.3 exhibits that fragility as a witness and the self-check re-derives it.

### 2.2 Family (i): the write, replicated

The rule is the predecessor's, unchanged: `BELOW_FLOOR` when the peak reading is under `readable_floor_q`; `PERSIST` when both fits leave an offset of at least `persist_share` of the terminal reading with both residuals inside `residual_band`; `TRANS` when the free fit leaves at most `trans_share` of it with the free rate inside the clock band; `UNRESOLVED` otherwise. The law and its instrument are fitted over the `PERSIST` arms in log space when at least `min_readable` of them exist.

### 2.3 Family (ii): retention

The post-release readings are fitted with the same two fits on the same five horizons, measured from the moment the split is removed. The reference magnitude is **not** a nominal level: it is the offset the same split wrote in family (i) on the same seed, $W=\lvert D_\infty^{\rm held}\rvert$ of the family (i) arm at the same $\delta_g$, so the retention fraction is a fraction of what was actually written:

| Branch | Condition | Reading |
|---|---|---|
| `MOOT` | family (i) at that $\delta_g$ is not `PERSIST` | nothing was displaced, so there is nothing to retain; recorded, not graded |
| `BELOW_FLOOR` | the post-release peak is under `readable_floor_q` | the instrument cannot see the level |
| `RETAINED` | both fits keep at least `retention_share` of $W$, residuals inside the band | the displacement survives the removal |
| `RELEASED` | both fits keep at most `release_share` of $W$, residuals inside the band, free rate inside the clock band | it decays back at the measured rate: a driven state, not a memory |
| `PARTIAL` | neither of the above | the displacement neither stays nor releases on the measured clock; **this is a third outcome and is reported as neither** |

`retention_share` and `release_share` are the only thresholds this protocol adds; both were declared before the run and both sit far from the probe's $1.02$–$1.04$, so the `PARTIAL` zone exists for a genuine third outcome and not as a latitude for the reading.

### 2.4 The two verdicts, and the joint label

| Verdict | Clause |
|---|---|
| `WRITES` | the largest split is `PERSIST` **and** at least `min_persist` sweep arms are `PERSIST`; the law is then issued over the `PERSIST` arms when at least `min_readable` of them exist |
| `PERTURBS_ONLY` | the largest split is `TRANS`, no sweep arm is `PERSIST`, and at least `min_readable` sweep arms are `TRANS` |
| `STORES` | the largest retention level is `RETAINED` and at least `min_retained` levels are `RETAINED` |
| `RELEASES` | the largest retention level is `RELEASED` and at least `min_retained` levels are `RELEASED` |
| `MOOT` | family (i) issued `PERTURBS_ONLY`: nothing was displaced to retain |
| `INCONCLUSIVE` | every other case, with the per-level table and the levels named |

The joint label names the four joints explicitly, because the pair is the finding and neither member is one on its own:

| Write | Retention | Joint | What it says |
|---|---|---|---|
| `WRITES` | `STORES` | `memory` | the gate displaces the carrier's composition coordinate and the carrier keeps the displacement after the asymmetry is gone |
| `WRITES` | `RELEASES` | `knob` | the gate displaces it only while it is held |
| `PERTURBS_ONLY` | `MOOT` | `no-write` | there was nothing to keep |
| anything else | | `undecided` | at least one family did not reach a branch it could grade |

### 2.5 Thresholds, declared before execution

| Constant | Value | Meaning |
|---|---|---|
| `horizons` | `30.0, 90.0, 180.0, 300.0, 450.0` | the five declared horizons, on both phases |
| `retention_levels` | `0.001, 0.01, 0.1, 1.0` | the four declared retention split sizes |
| `probe_retention_offsets` | `-3.3358050312383746e-07, -3.3587960350257283e-06, -3.5889430143274970e-05, -5.9244410183651049e-04` | the design probe's retention offsets, in the order of `retention_levels` |
| `readable_floor_q` | `1e-12` | carried: a level's reading must exceed this to enter a fit |
| `silence_floor_q` | `1e-14` | carried: the ray arms must read at or below this |
| `persist_share` | `0.5` | carried: family (i)'s offset share for `PERSIST` |
| `trans_share` | `0.1` | carried: family (i)'s offset share below which `TRANS` may be issued |
| `retention_share` | `0.5` | **new**: family (ii)'s offset share for `RETAINED` |
| `release_share` | `0.05` | **new**: family (ii)'s offset share for `RELEASED` |
| `residual_band` | `0.25` | carried: the two-parameter fits' own maximum residual, relative |
| `clock_tolerance` | `2.0` | carried: the free rate's band, and the clocks' |
| `nu_reference` | `0.01119569724312185` | the receipt's rate, held by fit H in both families |
| `nu_tolerance` | `2.0` | the two clocks against the declared rate |
| `tail_fraction` | `0.01` | the transient fraction the largest horizon and the hold horizon must leave |
| `min_span` | `1.0` | the horizon set's span in nats |
| `horizon_count` | `5` | the declared number of horizons |
| `min_readable` | `4` | the levels a law needs |
| `min_persist` | `2` | family (i)'s level count for `WRITES` |
| `min_retained` | `2` | **new**: family (ii)'s level count for `STORES` or `RELEASES` |
| `action_floor_live` | `0.001` | carried: the split's action at the largest load |
| `action_ceiling_silent` | `0.000000000000001` | carried: the split's action on the ray seed |
| `anchor_ray_tolerance` | `0.005` | carried: each anchor's distance from the ray at its own final state |
| `anchor_ray_at_hold` | `0.0013442651683720991` | the predecessor's amendment reading, at the hold horizon |
| `replication_tolerance` | `1e-15` | relative, for gates 16 and 20 |
| `write_law_coefficient` | `0.00043424057234641914` | the predecessor's measured law, used by gate 6's magnitude check |
| `write_law_exponent` | `1.0302448806878108` | the same |
| `write_law_instrument` | `4.129022977646817e-09` | the same |
| `hold_min_multiple` | `5.0` | the hold horizon in relaxation times |
| `load_tolerance` | `1e-12` | carried: the measured load against §67's reading |
| `step_safety` | `40.0` | carried: $\Delta t\le1/(40\lambda_{\max})$ |
| `bound_seconds` | `900.0` | the wall-clock bound |
| `declared_executions` | `17` | one process, seventeen arms |
| `per_execution_cap` | `50000` | the steps any one execution may take |
| `total_step_cap` | `600000` | the steps of the whole schedule |

## 3. The declared arms

Seventeen arms, one process, in this order. Every arm carries the profile, the seed shape, the integrator, the canonical companion and the projection of §1.1; the load column is the transfer coefficient $c$ of §67 and the measured $\ell$ is recorded per arm; the split column is $\delta_g$; the schedule column is $(\Delta t,T,\text{steps})$.

### 3.1 References—four arms

| Arm | Construction | Schedule |
|---|---|---|
| `ray_short` | the successor's short arm: the ray seed at the successor's own short schedule; the cross-protocol oracle | $0.02$, $T=2$, $100$ steps |
| `successor_replication` | the successor's `mode1_long` construction exactly: same seed, step and horizon; the cross-executor oracle | $0.02$, $T=36.66172105812361$, $1834$ steps |
| `ray_anchor` | the unsplit ray seed over the hold **and** the release span: the reference for both families' ray arms | $0.02$, $T=900$, $45000$ steps |
| `loadmax_anchor` | the unsplit seed at the largest declared load over the same span: the reference for family (i)'s sweep and for every retention arm | $0.02$, $T=900$, $45000$ steps |

### 3.2 The write family—eight arms

| Arm | $\delta_g$ | Schedule | Twin |
|---|---|---|---|
| `ray_supersplit` | $1$ | $0.02$, $T=450$, $22500$ | `ray_anchor` |
| `decade_1` … `decade_6` | $10^{-6},10^{-5},10^{-4},10^{-3},10^{-2},10^{-1}$ | $0.02$, $T=450$, $22500$ | `loadmax_anchor` |
| `supersplit_load` | $1$ | $0.02$, $T=450$, $22500$ | `loadmax_anchor` |

### 3.3 The retention family—five arms

| Arm | $\delta_g$ | Schedule | Twin | Held for |
|---|---|---|---|---|
| `retain_ray` | $1$ | $0.02$, $T=900$, $45000$ | `ray_anchor` | $450$ |
| `retain_1`, `retain_2`, `retain_3` | $10^{-3},10^{-2},10^{-1}$ | $0.02$, $T=900$, $45000$ | `loadmax_anchor` | $450$ |
| `retain_supersplit` | $1$ | $0.02$, $T=900$, $45000$ | `loadmax_anchor` | $450$ |

`retain_supersplit` is the release phase's can-fail control and is named in the verdict clause for the same reason the spent protocol named its own: the phenomenon at issue is the strongest split's, and a null there cannot be turned into a verdict by smaller levels that stayed put.

### 3.4 What makes the two anchors long

One run of each anchor serves both families: its prefix to $T=450$ is bit-identical to the $22500$-step run family (i) would otherwise take (the same integrator on the same state, started from the same seed), and its continuation to $T=900$ is the released reference family (ii) needs. That is what makes gate 17 an equality rather than a tolerance, and it is why the anchors carry no twin and are excluded from the sweep.

## 4. Gates, features, and the decision rule

### 4.1 The twenty-two gates

| # | Gate | Bound |
|---|---|---|
| 1 | binding | thirteen declared rows exact against the tree, and the predecessor's own ten rows agree |
| 2 | structure | every recorded state of both families: nonnegative, $0\le q<1$, annihilation and idempotence finite |
| 3 | anchor load | the measured load against §67's receipt within $10^{-12}$ relative |
| 4 | action live | the split's action at the largest load $\ge10^{-3}$ of the step's own drift, before any integration |
| 5 | action silent | the same action on the ray seed $\le10^{-15}$ |
| 6 | horizon adequacy, both phases | five distinct horizons, span $\ge1$ nat, tail $\le10^{-2}$, last horizon $\ge411.334$, hold $\ge446.60$ with its own tail $\le10^{-2}$, every declared level's magnitude at or above the readable floor |
| 7 | write clock | the anchor's $\rho$ rate over $[30,450]$ within a factor $2$ of the receipt's, and the receipt's value equal to the declared literal |
| 8 | release clock | the same fit over $[480,900]$, within a factor $2$ |
| 9 | schedule conformance | $\Delta t\le1/(40\lambda_{\max})$ on every arm's own loaded projection, from the declared set |
| 10 | declared shape | $17$ executions, $50000$ steps per execution, $600000$ in total |
| 11 | silence on the ray, write phase | $\le10^{-14}$ at every horizon |
| 12 | silence on the ray, release phase | the same on the retention ray arm |
| 13 | can-fail at the largest split, write phase | the peak reading $\ge10^{-12}$ |
| 14 | can-fail at the largest split, release phase | the post-release peak $\ge10^{-12}$ |
| 15 | anchors at the ray | each anchor's own distance from the ray at its final state $\le5\times10^{-3}$ |
| 16 | anchor at the ray, at the hold horizon | the loaded anchor's distance at $T=450$ equal to the predecessor's amendment reading within $10^{-15}$ relative |
| 17 | predecessor replication | every horizon-indexed reading of the twelve predecessor arms, exact, against the digest-bound receipt |
| 18 | cross-protocol oracle | `ray_short`'s $\rho_{\max}$ bit-identical to §66's receipt reading |
| 19 | cross-executor oracle | `successor_replication`'s $\rho_{\max}$, $\rho_{\text{final}}$ and $\lambda_{\max}$ bit-identical to the successor receipt's |
| 20 | design-probe replication | the four retention offsets equal the declared literals within $10^{-15}$ relative |
| 21 | single invocation | receipt absent at start, one process |
| 22 | family identity | the retention arms' held-phase readings equal the write arms' at the same split size, exactly: the two families are one construction, so a release that fired early, or a held step that was not the split's, breaks this equality while leaving every other gate standing |

Every gate is evaluated on the run's own numbers, and none of them is satisfied by construction: the two oracles and gate 17 would fail on any change to the construction, gates 11–14 would fail on a split that is not the declared one or a ray arm that is not silent, gates 6, 8 and 16 bound the horizons and the release the whole second family rests on, gate 22 binds the two families to each other, and gates 4–5 are the action check §5.1 states.

### 4.2 Features

| Feature | Gate it reads | What it licenses |
|---|---|---|
| F1 | 13 | the instrument fires at the largest split in the write phase |
| F2 | 11 | the ray arm is silent in the write phase |
| F3 | 18, 19 | the two oracles: the same instrument on the same seeds |
| F4 | 7 | the write-phase clock is the receipt's |
| F5 | 8 | the release-phase clock is the receipt's: the held rate's licence |
| F6 | 15 | the anchors sit at the ray, so an offset is attributable to the split |
| F7 | 14 | the release instrument is not blind at the strongest split |
| F8 | 17 | family (i) is the predecessor's measurement, not a new one |
| F9 | 12 | the ray arm is silent in the release phase |
| F10 | 16 | the amendment reading is reproduced by this body's own run |
| F11 | decision | family (i)'s largest branch is gradable (`PERSIST` or `TRANS`) |
| F12 | decision | family (ii)'s largest branch is gradable (always declared, and named in the receipt) |
| F13 | 22 | the retention arms' held phase is the write arms' own readings: the second family is the first family's construction plus a removal |

F1–F3 are the instrument's licence, F4–F5 the two clocks', F6 and F10 the attribution's, F7 and F9 the retention instrument's, F8 the replication's, F13 the two families' shared construction, and F11–F12 the two questions' own answerability.

### 4.3 Decision rule

`status=PASS` requires every gate and hence every feature; otherwise the run ends at `status=FAIL` with **both** verdicts null, the joint label null, and the failing gate named. On `PASS`, family (i)'s verdict, its law and its instrument are issued together with family (ii)'s verdict and the joint label. Neither verdict is issued without the other: a write verdict without the retention reading would report a displacement whose fate is unknown, and a retention verdict without the write verdict would grade a level that may never have been displaced.

### 4.4 What a verdict would and would not say

A `WRITES` verdict says that on this seed family and at these declared split sizes the gate's asymmetry displaces the composition coordinate by an amount proportional to the split, with the reference at the ray. It does not say the displacement is large, physical, or stable beyond the horizons measured. A `STORES` verdict says that displacement survives removing the asymmetry for five relaxation times; it does not say the carrier stores *information*, that the displacement is retrievable, or that anything outside this declared coordinate was written. `memory` is the name of the joint label and not a claim about the carrier's physical memory: §7 states the boundary in full.

## 5. Pre-flight reachability, before any integration

### 5.1 The action check

The split's action on $A$ over one declared step, on the seeded state, with the numerator the change the split makes and the denominator that step's own drift at zero split: at the largest declared load the reading is $5.3390731361887128\times10^{-2}$ against the floor $10^{-3}$, and on the ray seed it is exactly $0.0$ against the ceiling $10^{-15}$. Both directions carry more than an order of magnitude of margin, so the axis is live where the sweep reads it and inert where the control says it must be. The zero-split reduction is exactly $0.0$ elementwise on the whole grid: the released step is the unsplit step term for term, which is what makes "remove the split" a removal and not a different dynamics.

### 5.2 The horizon set separates the branches

A set of horizons that cannot separate the branches is not a test of them, so the separation is exhibited before the run, on synthetic readings built from a written magnitude $W=5\times10^{-4}$ and the measured clock: a displacement that stays ($D(t)=W$), one that decays at the measured rate ($D(t)=W e^{-\nu t}$), and one that does both ($D(t)=0.3W+0.7W e^{-\nu t}$) must reach `RETAINED`, `RELEASED` and `PARTIAL` respectively on the declared five horizons. The self-check runs exactly that and fails if any of the three, or the below-floor case, or the moot case, stops being reachable. The same witness is what declares the `PARTIAL` zone meaningful: a third outcome exists in the rules because a third outcome is constructible in the readings.

### 5.3 The write family's fragility, carried

The write family's rule is the predecessor's and its fragility is the predecessor's too, re-derived in the self-check through the imported rule: a pure transient decaying $2.4\%$ off the declared clock reports an offset at $57\%$ of its terminal reading in the held fit, and the free fit is what rescues it, which is why no branch is issued without both fits agreeing. The release family inherits the same conjunction for the same reason.

### 5.4 What the probe predicts

The design probe of §1.5 predicts `PERSIST` at all seven write levels, `RETAINED` at all four retention levels, `WRITES`, `STORES` and the joint label `memory`, with the retention readings flat to $3.9\times10^{-4}$ of themselves across the release window at the largest level and under $6.1\times10^{-5}$ at the three smaller ones. The run is expected to reproduce it; the probe is not a reading of this protocol, and gate 20 is what holds the two together.

## 6. Run schedule, budget and stopping rule

| Item | Value |
|---|---|
| Executions | $17$, one per arm, in the order of §3 |
| Steps | $496{,}934$ at the declared schedules ($91{,}934$ in the four references, $180{,}000$ in the eight write-family arms, $225{,}000$ in the five retention arms), against the total cap $600{,}000$; the largest single execution is the $45{,}000$-step anchor, against the per-execution cap $50{,}000$ |
| Projection | $415.0$ s at the assumed rate $8.36\times10^{-4}$ s per step, $331.0$ s at the measured rate $6.665\times10^{-4}$ s per step — the predecessor's own $226{,}934$ steps in $151.24$ s |
| Bound | $900.0$ s, so the projection sits at $0.46$ of the bound on the assumed rate and $0.37$ on the measured one; the design probe of §1.5 ran the whole schedule in $321.3$ s, $0.97$ of the measured-rate projection |
| Process | one process, one thread per arm, no concurrent run; the receipt records the pid and the runtime |
| Receipt | `runs/loop_carrier_attractor_write_successor/verification.json`, schema `cassi.loop-carrier-attractor-write-successor.v1` |

The bound is the predecessor's $600$ s scaled by this schedule's own step ratio and doubled for margin: $496{,}934/226{,}934=2.19$, and the declared $900$ s leaves $2.2$ times the assumed-rate projection. It is declared, not discovered: a run that exceeds it writes no receipt, and §0's stopping rule permits a second invocation only in that case.

## 7. Interpretation boundary

What this protocol measures is a **declared coordinate on one finite realization**: the composition coordinate $A$ of the projection, its displacement under one declared gate split on one seed family, and the fate of that displacement when the split is removed. What it does not measure is the conversion ratio, the carrier identity, the QF1-to-carrier map, the phase law, the scale ratio or the quantum statistics. $\varphi$ enters only as the declared entries of the four-population law, which remains the selected minimal member of a family whose columns sum to one: for a rank-one conversion block the spectrum and the relaxation rate are functions of $a+b$ alone and the ratio lives in the null vector. The load is a departure of the carrier state from the ray, not a physical density, current or field strength. The split is a declared relative asymmetry of the common projected gate, not a measured coupling, and its level is not comparable across axes in physical terms.

`STORES` and `memory` are names of a branch of a decision rule on that coordinate. They do not say the carrier stores information, that the displacement is readable by any other observable, or that the channel is a physical memory: they say that on this seed, at this split size, the displacement does **not** decay at the realization's own relaxation rate once the asymmetry is removed — while a driven state would. That is the measured difference between a knob and a kept displacement, and it is the whole of the claim.

The two clocks are the meaningful guard: both are fitted on the anchor's own $\rho$ and both are gated against the receipt's rate, so the release phase of these arms is measured on a realization whose own relaxation time is known rather than assumed, and the retention fit's held rate is that measured value.

## 8. Post-execution record

**The invocation.** `timeout 900 python computations/verify_loop_carrier_attractor_write_successor.py`, one process, pid 7512, exit 0, runtime $321.00586342811584$ s against the declared bound $900$ s, writing `runs/loop_carrier_attractor_write_successor/verification.json` at schema `cassi.loop-carrier-attractor-write-successor.v1`. `status=PASS`: all twenty-two gates and all thirteen features passed in the single invocation this body allows, and the two families' verdicts are **write `WRITES`** and **retention `STORES`**, with the joint label **`memory`**. No second invocation was made and §0's stopping rule was not reached.

**The binding at the invocation.** Every row of §0 was re-read from the tree and matched, including the ten rows the predecessor's own binding check re-verifies; `binding.declared` and `binding.observed` agree on all thirteen keys and the receipt carries both.

| Row | At the invocation |
|---|---|
| `frozen_body_sha256` | `23fb4e9a545793752db259324c87a71da9045cbb04221d0c60ef9c50b6003372` |
| `executor_sha256` | `d92bdd1a12a0f3ce1640cf100a23ae5898f6e51bd078c03965f0ab086c68007e` |
| `prior_body_sha256` | `151ab43fbaf2cd8580679bca98d51a40cbac7adf275a799b0f06249aedb9c636` |
| `prior_executor_sha256` | `740d0fc036721be5f1ee0fd5527fe54e771243113e13b7133be053f6439cf6c6` |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` |
| `gate_load_executor_sha256` | `be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac` |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` |
| `gate_load_protocol_body_sha256` | `c0d2fe37b8b4ee7673b1ec1a7c658f2bedb4eae6ad360516057d5ee9cdc843fa` |
| `gate_load_receipt_sha256` | `471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1` |
| `prior_receipt_sha256` | `5ba4afcd2b17d00be8c4fd315ee4f3133422aaae7bdb83e1f0e51ad9935be200` |

**The twenty-two gates.** All passed, and the readings that carry the two verdicts:

| # | Gate | Reading |
|---|---|---|
| 3 | anchor load | the loaded anchor's measured load $3.6461142923163309\times10^{-1}$ equal to §67's receipt value to the last bit (declared literal $3.646114292316\times10^{-1}$) |
| 6 | horizon adequacy, both phases | five distinct horizons spanning $4.7022$ nats, tail $6.486295195552842\times10^{-3}$, declared threshold $411.333933562495$, hold $450\ge446.6001439143759$ with tail $6.486295195552842\times10^{-3}$, seven write levels and four retention levels, the smallest declared write magnitude $2.859309151498377\times10^{-10}$ |
| 7 | write clock | the anchor's own $\rho$ rate over $[30,450]$ fitted at $1.1375969997251654\times10^{-2}$, ratio $1.0161019675876424$, with the declared rate equal to the live receipt value $1.119569724312185\times10^{-2}$ |
| 8 | release clock | the same fit over $[480,900]$: $1.1268285328754471\times10^{-2}$, ratio $1.0064835698979995$ |
| 11, 12 | silence on the ray, both phases | peaks $3.3306690738754696\times10^{-16}$ and exactly $0.0$ |
| 13, 14 | can-fail at the largest split, both phases | $5.9240187127518329\times10^{-4}$ and $5.9244224877041951\times10^{-4}$ |
| 15 | anchors at the ray | ray anchor's own distance $4.615955614456136\times10^{-15}$, loaded anchor's $8.439048206843707\times10^{-6}$, against the bound $5\times10^{-3}$ |
| 16 | anchor at the ray, at the hold horizon | $1.3442651683720991\times10^{-3}$, equal to the predecessor's amendment reading at the declared precision |
| 17 | predecessor replication | $132$ horizon-indexed readings over the twelve predecessor arms, $0$ mismatches |
| 18 | cross-protocol oracle | `ray_short`'s $\rho_{\max}$ $5.329147248815693\times10^{-16}$, bit-identical to §66's receipt |
| 19 | cross-executor oracle | `successor_replication`'s $\rho_{\max}$ $2.622443969747147\times10^{-15}$, $\rho_{\text{final}}$ $2.219140084394095\times10^{-15}$ and $\lambda_{\max}$ $1.0331312281605476$, bit-identical to the successor receipt |
| 20 | design-probe replication | the four retention offsets equal the §1.5 literals |
| 22 | family identity | all five retention arms' held-phase readings bit-identical to their write arms' ($5$ pairs, $0$ mismatches) |

Gate 4's action check read $5.3390731361887128\times10^{-2}$ of the step's own drift at the largest load against the floor $10^{-3}$, and exactly $0.0$ on the ray seed; the zero-split reduction is exactly $0.0$ elementwise; every arm's $\Delta t$ is inside $1/(40\lambda_{\max})$ on its own loaded projection; and the structure gate found no state outside $[0,1)$ and no non-finite annihilation or idempotence residual, with $\min_x q=0.8013148274093032$ and $\max_x q=0.8923974884573972$ on the loaded anchor.

**Family (i), the write, replicated (gates 17 and 20 passing).**

| Arm | $\delta_g$ | $D_\infty^{\rm held}$ | $D_\infty^{\rm free}$ | terminal reading | share of terminal | free rate / $\nu$ | residual held / free | branch |
|---|---|---|---|---|---|---|---|---|
| `decade_1` | $10^{-6}$ | $-3.1965673301338663\times10^{-10}$ | $-3.3035080920401598\times10^{-10}$ | $-3.3328928505937938\times10^{-10}$ | $0.9590969387$ | $4.0943618995$ | $7.576993\times10^{-2}$ / $1.024171\times10^{-2}$ | `PERSIST` |
| `decade_2` | $10^{-5}$ | $-3.1965812566686525\times10^{-9}$ | $-3.3035229018272927\times10^{-9}$ | $-3.3328977355751022\times10^{-9}$ | $0.9590997115$ | $4.0943618995$ | $7.576890\times10^{-2}$ / $1.024098\times10^{-2}$ | `PERSIST` |
| `decade_3` | $10^{-4}$ | $-3.1968113811286852\times10^{-8}$ | $-3.3037349807008856\times10^{-8}$ | $-3.3331260418378861\times10^{-8}$ | $0.9591030585$ | $4.0943618995$ | $7.576593\times10^{-2}$ / $1.024724\times10^{-2}$ | `PERSIST` |
| `decade_4` | $10^{-3}$ | $-3.1991208866120801\times10^{-7}$ | $-3.3058613202974022\times10^{-7}$ | $-3.3354247119810054\times10^{-7}$ | $0.9591344920$ | $4.0943618995$ | $7.573705\times10^{-2}$ / $1.031132\times10^{-2}$ | `PERSIST` |
| `decade_5` | $10^{-2}$ | $-3.2222190653455414\times10^{-6}$ | $-3.3271274457746284\times10^{-6}$ | $-3.3584153593668731\times10^{-6}$ | $0.9594462628$ | $4.0943618995$ | $7.544916\times10^{-2}$ / $1.095023\times10^{-2}$ | `PERSIST` |
| `decade_6` | $10^{-1}$ | $-3.4534423534314694\times10^{-5}$ | $-3.5400140411285416\times10^{-5}$ | $-3.5885586093908906\times10^{-5}$ | $0.9623480426$ | $4.0943618995$ | $7.265414\times10^{-2}$ / $1.715102\times10^{-2}$ | `PERSIST` |
| `supersplit_load` | $1$ | $-5.8002371593543804\times10^{-4}$ | $-6.1411238765855997\times10^{-4}$ | $-5.9240187127518329\times10^{-4}$ | $0.9791051380$ | $0.2442312221$ | $4.825167\times10^{-2}$ / $3.568828\times10^{-2}$ | `PERSIST` |

The law over the seven persisting arms is $\lvert D_\infty\rvert=(4.3424057234641914\times10^{-4})\,\delta_g^{1.0302448806878108}$ at label `PROPORTIONAL`, per-level ratios $0.8526$–$1.3357$, decade jumps $10.000$–$16.796$, and the instrument is $\delta_w=4.1290229776468171\times10^{-9}$. `ray_supersplit` reads exactly $0.0$ at all five horizons with peak $3.3306690738754696\times10^{-16}$ and is labelled `BELOW_FLOOR`; every arm's readings are carried in the receipt, and gate 17 confirms all of them are the predecessor's own. **Verdict: `WRITES`.**

**Family (ii), retention (gate 22 passing).**

| Arm | $\delta_g$ | written (family (i)) | $D_\infty^{\rm held}$ | $D_\infty^{\rm free}$ | share held / free | free rate / $\nu$ | residual held / free | branch |
|---|---|---|---|---|---|---|---|---|
| `retain_1` | $10^{-3}$ | $3.1991208866120801\times10^{-7}$ | $-3.3358050312383746\times10^{-7}$ | $-3.3357883329490823\times10^{-7}$ | $1.042726$ / $1.042720$ | $1.800533$ | $7.962386\times10^{-6}$ / $5.932632\times10^{-8}$ | `RETAINED` |
| `retain_2` | $10^{-2}$ | $3.2222190653455414\times10^{-6}$ | $-3.3587960350257283\times10^{-6}$ | $-3.3587793231551760\times10^{-6}$ | $1.042386$ / $1.042381$ | $1.799663$ | $7.911307\times10^{-6}$ / $5.901954\times10^{-8}$ | `RETAINED` |
| `retain_3` | $10^{-1}$ | $3.4534423534314694\times10^{-5}$ | $-3.5889430143274970\times10^{-5}$ | $-3.5889261715143997\times10^{-5}$ | $1.039236$ / $1.039232$ | $1.789633$ | $7.428166\times10^{-6}$ / $6.191054\times10^{-8}$ | `RETAINED` |
| `retain_supersplit` | $1$ | $5.8002371593543804\times10^{-4}$ | $-5.9244410183651049\times10^{-4}$ | $-5.9244228458508650\times10^{-4}$ | $1.021414$ / $1.021410$ | $1.709169$ | $4.666750\times10^{-6}$ / $8.626462\times10^{-8}$ | `RETAINED` |

The post-release readings, at $t=30,90,180,300,450$ after the split is removed at $T=450$:

| Arm | readings |
|---|---|
| `retain_1` | $-3.3355879947016831\times10^{-7}$, $-3.3357284801027731\times10^{-7}$, $-3.3357787898591340\times10^{-7}$, $-3.3357874351658268\times10^{-7}$, $-3.3357881878970375\times10^{-7}$ |
| `retain_2` | $-3.3585787123646682\times10^{-6}$, $-3.3587193533080040\times10^{-6}$, $-3.3587697528814076\times10^{-6}$, $-3.3587784297184342\times10^{-6}$, $-3.3587791702371916\times10^{-6}$ |
| `retain_3` | $-3.5887227049613557\times10^{-5}$, $-3.5888649274951057\times10^{-5}$, $-3.5889163177538208\times10^{-5}$, $-3.5889252362863999\times10^{-5}$, $-3.5889260026289449\times10^{-5}$ |
| `retain_supersplit` | $-5.9241907219331758\times10^{-4}$, $-5.9243489728644239\times10^{-4}$, $-5.9244101973199292\times10^{-4}$, $-5.9244214739950785\times10^{-4}$, $-5.9244224877041951\times10^{-4}$ |

`retain_ray` reads exactly $0.0$ in both phases. In the order of the declared levels the release moves the reading by $6.002\times10^{-5}$, $5.968\times10^{-5}$, $5.665\times10^{-5}$ and $3.912\times10^{-4}$ of itself between the first and last post-release reading, against a factor $e^{\nu\,420}=110$ for a state decaying at the measured clock. The receipt also carries a retention-family law fitted over the four graded levels — $\lvert D_\infty^{\rm held}\rvert=(5.138283027628463\times10^{-4})\,\delta_g^{1.0777123093106087}$, ratios $0.8353$–$1.1530$, label `PROPORTIONAL`, instrument $8.266215754275881\times10^{-9}$ — which §2 does not declare and which enters no verdict clause; it is reported because the run computed it, and its exponent is the retention family's own. **Verdict: `STORES`.**

**What the two verdicts say.** On this seed family, at these four declaration sizes, the gate's asymmetry displaces the carrier's composition coordinate, the displacement is proportional to the split over seven decades in the write family and over three in the retention family, and — the new reading — **it does not decay when the asymmetry is removed**: five relaxation times after the split is taken away the offset stands at $1.02$–$1.04$ of what family (i) wrote, where a driven state would have fallen by a factor $110$. The joint label is `memory`: on this realization the gate is not a knob that acts only while it is turned.

Three things are recorded and not gated, because they are properties of this realization rather than of the claim. The free fit's rate in the release phase is $1.71$–$1.80$ times the measured clock, i.e. slower than the clock but inside the declared band; when an offset dominates a reading the free rate is not identified, so it enters only the transient clause. The release-phase fit's offsets sit slightly **above** the write family's own (shares $1.021$–$1.043$), because the released trajectory continues its transient for a while after the removal before it saturates. And the retained quantity is the composition coordinate's difference, which is a conserved conversion level rather than a state off the ray: the loaded anchor's own distance from the ray falls from $1.3442651683720991\times10^{-3}$ at the hold horizon to $8.439048206843707\times10^{-6}$ at $T=900$, so the released arms return to the ray while their composition coordinate stays displaced.

**Boundary.** As §7: one coordinate, one frozen discrete realization, one profile, one seed family, one declared load, one common gate and one common transport, both assumed; the identity of the write is a decision rule's branch on that coordinate and not a claim about the carrier's physical memory, retrieval, or information content. The first-order transport degradation with its coefficient and crossing, and the gate dead on the ray and live in proportion to the load, are the pre-existing measurements of §66 and §67; this body adds the third and fourth: the write is now certified by a readable attribution gate, and the carrier keeps it.

The outcome is entered as §69 of `field-experience/probe-outcome-ledger.md`.
