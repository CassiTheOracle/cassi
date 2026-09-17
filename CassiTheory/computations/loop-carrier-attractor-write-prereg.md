# Does an Asymmetric Gate Write, or Only Shake? The Loop-Carrier Composition Attractor Under a Split Gate, Read by a Multi-Horizon Offset Fit

## Status: Pre-registered—September 16, 2026; not executed. The executor is frozen in the same commit as this text and refuses to run on a hash mismatch.

## 0. Freeze and binding

This protocol and its executor are frozen together. The executor reads the rows below and refuses to run, with exit code $3$ and no arm constructed, if any of them disagrees with the tree. Section 0 sits outside the frozen body, and the frozen body is what the executor hashes, so the two hashes bind each other without a fix point: the body digest below is a function of §1–§7 alone, and the executor's digest is written here after the executor exists. The executor's self-check is idempotent: it verifies by digest, reports the receipt's presence as a recorded fact, and writes nothing.

| Source | SHA-256 | Meaning |
|---|---|---|
| `frozen_body_sha256` | `151ab43fbaf2cd8580679bca98d51a40cbac7adf275a799b0f06249aedb9c636` | this file from `## 1.` to just before `## 8.`, the text that carries every statistic, threshold, arm and decision rule |
| `executor_sha256` | `5b51173fceda2b96be4ad4d2e64e512f70fb372718749fd8255f58a4ced4a923` | `computations/verify_loop_carrier_attractor_write.py`, the complete executor frozen with this text |
| `bound_module_sha256` | `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` | `computations/verify_loop_to_bubble_projection.py`, the frozen discrete operators |
| `base_probe_sha256` | `28d2fd540a3d3bc6ef1b4bb100fbff2f36a11baca4f4ff365ea4ad8a9dcf3622` | `computations/verify_loop_carrier_projection_relaxation.py`, the successor's executed probe: the carrier law, the projection, the composition, the canonical companion, the seeds and the integrator |
| `split_executor_sha256` | `246463f7fd1ba4a7fef282079e312d6e1382a15319b97d20b2ba49be46adcb5a` | `computations/verify_loop_carrier_projection_split.py`, the spent split protocol's executed executor, from which the split right-hand side and the split gate field are **imported** rather than re-derived |
| `gate_load_executor_sha256` | `be9f651d085bb4ee5d8f62ddb4db0a1714eb58c1b2106025d52f7fe2224f0eac` | `computations/verify_loop_carrier_gate_load.py`, §67's executed executor, from which the loaded seed, the load metric, the residual, the structure readings and the log-space power-law fit are **imported** |
| `base_receipt_sha256` | `3520231c8c54372e07443682847de9d01fbb0f132c89efef3fc7f0c16a22bcb1` | `runs/loop_carrier_projection_relaxation/verification.json`, source of the replication oracle reading and of the **relaxation rate this protocol holds** (§1.4) |
| `split_receipt_sha256` | `559d19ae43011b0f7143a5c9cf8429a5c46b5a181849c7b4cabd2ea99c8872fc` | `runs/loop_carrier_projection_split/verification.json`, source of the ray oracle reading and of the inertness §67 closed |
| `gate_load_protocol_body_sha256` | `c0d2fe37b8b4ee7673b1ec1a7c658f2bedb4eae6ad360516057d5ee9cdc843fa` | `computations/loop-carrier-gate-load-prereg.md` §1–§7, source of the declared largest load, the declared decades and the load axis this protocol holds fixed |
| `gate_load_receipt_sha256` | `471f1f8074ff7cc85187690747b7ba9235e6d8627a7e9a7cc1db2a0a81710cc1` | `runs/loop_carrier_gate_load/verification.json`, §67's receipt: the largest declared load's measured value, the decade readings and the two fits |

**What the digests are of.** Every hash above is of the file's bytes as they stand in the working tree, as the other artifacts in this chain record them; a checkout that rewrites line endings moves several rows at once and is answered by re-pinning, never by editing §1–§7.

**What the binding guarantees, exactly.** An edit to §1–§7, or to the executor, is detected before any arm is constructed. An edit to §0 is itself a disclosed amendment, visible in the diff that carries it; it is not detected by construction, and this sentence is the disclosure that it cannot be. Filling §8 after an invocation does not touch the body range, so the record cannot move the frozen text; a second invocation is refused in code while a receipt exists (§6).

**The receipt directory is new.** This protocol writes `runs/loop_carrier_attractor_write/verification.json`. It reads the three predecessor receipts and writes none of them, and it constructs no arm outside its own table.

## Abstract

§67 measured the loop-carrier projection's response to an orientation-asymmetric gate: on the ray the split is dead, off the ray it is live, first order in the split size ($p=1.0001266948985081$) and, to within $7.8\%$, linear in the conversion-bracket load ($q=1.0777928255642235$). Both readings are readings of a **separation between a split trajectory and its own unsplit twin**, taken as a maximum over a fixed window. Nothing in them distinguishes two mechanisms that a single horizon cannot separate: the gate may **displace the state transiently** while the unchanged ray pulls the composition back, or it may **move the attractor itself**, in which case the terminal composition is a function of the split and cannot decay back.

This protocol separates those two by reading one trajectory at **five horizons spanning more than four relaxation times** and fitting the two-parameter form $D(T)=D_\infty+(D_0-D_\infty)e^{-\nu T}$ at the realization's own measured rate $\nu$, so that the **offset** $D_\infty$—not a ratio of two readings—is the discriminator: a transient leaves $D_\infty=0$, a shifted attractor leaves a nonzero offset. Because a held clock is only as good as the clock, every arm is fitted a second time with $\lambda$ free, and a branch is issued only where the two fits agree; §1.5 records the measurement that forced that conjunction. It sweeps the six decades of §67 at §67's largest load with §67's own zero-split reference as the anchor, carries the ray seed as the predicted-silence control, and reports a null verdict when an offset exists but is not resolvable as a function of $\delta_g$ at these horizons.

## 1. What is held fixed, what is measured, and what would count as writing

### 1.1 Held fixed

Each item is the repository's own definition or a frozen module's own source, imported at a bound digest; nothing here is re-derived.

| Item | Value |
|---|---|
| Law | the four-population carrier law of `foundations/loop-to-bubble-projection-theorem.md` (LB6), as implemented by the successor probe's `initial_carrier`, `carrier_rhs` and `rk4_step` |
| Discrete operators | `computations/verify_loop_to_bubble_projection.py`, held at `d687597fe960c95d8515f9caf41ea2d8a06198d9c11045836376a21dafefd8f1` |
| Loop resolution | $N_\chi=24$, the successor's own |
| Projection | (LB1), the successor's `projection`: $(E_Y,E_I)$ with $E_a(x)=\sum_s\langle f_{a,s}\rangle_\chi$ on the equal-weight loop grid |
| Composition | (LB4)–(LB5), the frozen bounded composition $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$ with $\rho=E_Y+E_I$ and $\varepsilon=E_Y-\varphi E_I$, evaluated on the projection |
| Seed family | §67's own: the profile `on_ray`, mode $m=1$, $\alpha=0.25$, imbalance $\beta=0.05$, with the declared pure transfer $\psi_Y\leftarrow\psi_Y+\tfrac{c}{2}\rho$, $\psi_I\leftarrow\psi_I-\tfrac{c}{2}\rho$ at $c=2\times10^{-1}$, imported as `loaded_seed` and held |
| Load | §67's largest declared load, $c=2\times10^{-1}$, measured by §67's own metric $\ell=\max|B|/\max|\psi|$ at $t_0$ against §67's receipt |
| Split | §67's own construction, imported from the spent split executor: every carrier's conversion field becomes $\kappa(1+\sigma_a\delta_g\cos\chi)$ with $\sigma_Y=+1$, $\sigma_I=-1$, and the shared $\kappa=\lambda[1-q]$ read from the projection |
| Transport axis | **not** re-opened: no velocity split, no orientation split, $\delta_u=0$ on every arm |
| Integrator | the successor's `rk4_step`, classical RK4 in float64, imported |
| Step rule | $\Delta t\le1/(40\lambda_{\max})$ on the arm's own loaded projection, and $\Delta t\in\{0.05,0.02,0.01\}$ |
| Canonical companion | the successor's `canonical_initial` / `canonical_step`, stepped in lockstep at the same $\Delta t$; its residual $\rho$ is recorded, never gated |
| Budget | one process, per-execution cap $50{,}000$ steps, bound $600$ s (§6) |
| Stopping rule | one invocation per frozen body; a receipt, once written, refuses a second in code |

### 1.2 What is measured: the composition coordinate, at five horizons

The coordinate is the composition the conversion rate reads, averaged over the exterior cells:

$$A(t)=\frac{1}{N_x}\sum_{x}q\big(E_Y(x,t),\,E_I(x,t)\big),$$

so $A$ is a scalar of order one, it is maximal on the ray (where $\varepsilon=0$), and it is exactly the ratio the gate law $\kappa=\lambda[1-q]$ turns into the conversion rate. Each split arm is paired with the **anchor**: the same load, the same schedule, the same seed, $\delta_g=0$, run once and shared by every arm of the sweep, because the split enters only through the right-hand side and the anchor's trajectory is deterministic and identical for all of them. The reading is the difference

$$\Delta(t)=A_{\rm arm}(t)-A_{\rm anchor}(t),$$

which is $0$ at $t_0$ by construction—the arm and the anchor start from the same state—so the pair contains nothing but the split's own effect.

**The horizon set.** Each arm is read at **five horizons of the same trajectory**,

$$H=\{30,\ 90,\ 180,\ 300,\ 450\},\qquad \Delta t=0.02,\qquad T_{\max}=450=22{,}500\ \Delta t,$$

which are, at the declared clock of §1.4, the multiples $0.336,\ 1.008,\ 2.015,\ 3.359,\ 5.038$ of the relaxation time $1/\nu$. One trajectory, five samples; no arm is run twice to obtain a horizon, and the horizons are not re-chosen after the fit.

**The clock and why the horizons are declared where they are.** The offset fit holds a rate, so the rate and the horizons must be stated together:

| Quantity | Arithmetic | Value |
|---|---|---|
| Declared rate | successor receipt, `relaxation.arms.relax_reference.fit.nu_fit`, fitted over its own window $[500,1000]$ | `NU_REFERENCE` $=1.119569724312185\times10^{-2}$ |
| Relaxation time | $1/\nu$ | $89.32002878287518$ |
| First horizon | $T_{\min}=30$ | $0.336/\nu$: the first sample sits inside the transient |
| Last horizon | $T_{\max}=450$ | $5.038/\nu$ |
| Tail at the last horizon | $e^{-\nu T_{\max}}$ | $6.486295195552842\times10^{-3}\le$ `TAIL_FRACTION` $=10^{-2}$ |
| The declared tail threshold | $\ln(1/{\rm TAIL\_FRACTION})/\nu$ | $411.333933562495$, so $T_{\max}$ clears it by $9.4\%$ |
| Span | $\nu(T_{\max}-T_{\min})$ | $4.702192842111177>$ `MIN_SPAN` $=1$: the set spans more than one relaxation time |

Both ends are declared relative to the measured rate rather than chosen as a guessed pair, and the declaration of the last horizon is a *number to be checked* (§4, gate 6), not a convenience: at $T=12$, which §67 used, the transient is $e^{-0.134}=87\%$ intact and no horizon pair there separates the branches at all.

**The pair is recorded, not classified.** The two-horizon ratio $r=\Delta(300)/\Delta(180)$ and the transient prediction $e^{-\nu(300-180)}=4.866290440665\times10^{-2}$ are recorded beside every arm, because the separation between a reading that stays put and a reading that decays at the clock is the whole reason the horizon set is long enough: the two predictions differ by $20.55\times$. The classification itself is the fit of §2, which uses all five samples and a held amplitude as well as a held rate.

**Why the coordinate and not the state.** §67's statistic was a state-space maximum; this protocol reads a scalar the gate law itself evaluates. The two are recorded together—the state-space separation of §67's construction is re-measured on these arms and recorded—but only $A$ is classified and fitted.

### 1.3 What would count as the gate writing

**`WRITES`.** The gate writes iff the largest declared split's reading has a **nonzero offset that survives the clock**: $D_\infty$ from the held-rate fit is at least `PERSIST_SHARE` of the terminal reading, the free-rate fit agrees, and the same holds at least `MIN_PERSIST` times across the sweep. Then the composition the state relaxes to is a function of $\delta_g$ and does not return to the unsplit value, the offset is fitted against $\delta_g$ and its exponent is reported, and the gate is a channel through which a static imprint can be carried.

**`PERTURBS_ONLY`.** The gate perturbs only iff the largest declared split, and every other measurable arm, has an offset that **vanishes under the free-rate fit**—the reading is a decay at the realization's own clock, $\lambda$ within a factor `CLOCK_TOLERANCE` of `NU_REFERENCE`—and no arm's offset persists. Then a split gate leaves no imprint that survives: it can shake the state, not bias it, and that is a real result about what can be carried through this channel.

**`INCONCLUSIVE`, the verdict null.** Two things are called inconclusive and both are reported:
1. **Within an arm.** The two fits can disagree: the held fit can show an offset the free fit attributes to a decay, or the residual of the two-parameter form can exceed `RESIDUAL_BAND` so that neither fit describes the reading. Such an arm is `UNRESOLVED`, it carries neither branch, and the reason and both fits are recorded. Its reading is a *finding about the relaxation structure* rather than a missing number.
2. **Across the sweep.** An offset can exist and still not be resolvable as a function of $\delta_g$ at these horizons—too few arms persist to fit a law, or the persisting offsets are not monotone in $\delta_g$. Then no single write verdict is issued, the per-level table is the result, and the outcome is `INCONCLUSIVE` with the levels named. This is a legitimate reading of *not measured*; it is not a reading of *the gate writes*.

**The conjunction is not decoration.** A held rate that is wrong by a few percent makes the held fit alone report an offset for a pure transient: §1.5 measures that at a rate $2.4\%$ above the declared one, the held fit's offset reaches $57\%$ of the terminal reading—inside the persist band—on a reading that decays exactly at its own clock. Because the realization's own rate over these windows is measured (§4, gate 7) at $1.6\%$ from the declared rate and is not known more precisely than that, the branch rule of §2.3 requires the free-rate fit to agree before any arm is called persisting, and §5.4 exhibits both sides of that boundary as synthetic witnesses before the run.

**What none of it says.** No reading here is the value of $\varphi$, the carrier identity, the QF1-to-carrier map, the phase law, the scale ratio or the quantum statistics. $\varphi$ enters only as the declared entries of the four-population law and inside the frozen composition; $A$ and the gate law are functions of the projected densities, and for a rank-one conversion block the spectrum and the relaxation rate are functions of $a+b$ alone while the ratio lives in the null vector, exactly as `open-questions-cassi-answers.md` states. "Writing" here means *this declared gate split biases this declared composition coordinate on this finite realization*, and nothing about storage in any physical sense.

### 1.4 The clock, and why the classification needs one

The two branches are told apart by whether a reading decays at the rate the state itself relaxes at, so the classification needs that rate from two directions: it is **held** in the primary fit, and it is **measured in the run** and gated. The declared value is the successor receipt's own fitted rate, `NU_REFERENCE` $=1.119569724312185\times10^{-2}$, read from `runs/loop_carrier_projection_relaxation/verification.json` at run time (the executor pins that receipt's digest in §0 and requires the value it reads to equal the literal declared in §2.3, so the clock's provenance is verified rather than asserted). The executor fits the anchor's own $\rho(t)$ over the declared window $[T_{\min},T_{\max}]=[30,450]$ and requires the fitted rate to lie within a factor `NU_TOLERANCE` of `NU_REFERENCE`. That gate licenses two things at once: the free-rate fit's rate band, and the reading of a $k\%$ clock error as a $k\%$ error rather than as an offset. §1.5 records the two measured rates for this realization, $1.61\%$ and $2.43\%$ from the declared value on the two natural windows, both inside the gate.

### 1.5 Design probe, before freezing

Everything below was measured before this text was frozen, with the same imported modules, the same seeds, the same split, the same horizons and the same schedule the executor declares. It is disclosed because the declared floors, bands and horizons are chosen against it, and the run is expected to reproduce it; the probe is a design instrument, not a reading of this protocol.

| Quantity | Probe reading |
|---|---|
| Anchor coordinate | $A$ at the five horizons: $8.705547\times10^{-1}$, $8.873981\times10^{-1}$, $8.917622\times10^{-1}$, $8.923552\times10^{-1}$, $8.923960\times10^{-1}$ |
| Anchor residual | $\rho$ at the same: $1.037202\times10^{-1}$, $4.910601\times10^{-2}$, $1.746169\times10^{-2}$, $4.504459\times10^{-3}$, $8.308016\times10^{-4}$ |
| Fitted clock | $\nu_{\rm fit}=1.1375969997252\times10^{-2}$ over $[30,450]$, the declared window—a factor $1.0161$ from the declared rate; $1.1468125739400613\times10^{-2}$ over $(0,450]$, a factor $1.0243$ |
| Anchor at the ray at $T_{\max}$ | $\max|\varepsilon|/\max|\rho|=1.344265\times10^{-3}$ on the projection: the unsplit reference sits at the ray to better than a part in $700$, so an offset in a split arm is attributable to the split and not to the reference still relaxing |
| Split reading, by level | $\Delta$ at the five horizons for $\delta_g=10^{-6}$: $-4.2367\times10^{-10}$, $-3.3196\times10^{-10}$, $-3.2922\times10^{-10}$, $-3.3270\times10^{-10}$, $-3.3329\times10^{-10}$—a decay from the first sample to a plateau, and *not* a decay to zero |
| Offset, held fit | $D_\infty^{\rm held}$ from $-3.1966\times10^{-10}$ at $\delta_g=10^{-6}$ to $-3.4534\times10^{-5}$ at $10^{-1}$; the free fit gives $-3.3035\times10^{-10}$ to $-3.5400\times10^{-5}$, within $3.3\%$ level by level |
| Branch | every one of the six levels is `PERSIST`, with a two-parameter residual of at most $0.076$ against a band of $0.25$; the free-rate fit for these arms runs to the edge of its scan ($\lambda/\nu=4.094$), which is recorded: when an offset dominates, the free rate is not identified |
| Law, held fit | $|D_\infty|=3.378913644274\times10^{-4}\,\delta_g^{\,1.005101810107}$, per-level ratios $0.976$–$1.034$: proportional |
| Law, free fit | $|D_\infty|=3.471548263501\times10^{-4}\,\delta_g^{\,1.004562966355}$, per-level ratios $0.979$–$1.031$: the corroborating fit gives the same exponent to $5.4\times10^{-4}$ |
| Instrument | $\delta_w=(10^{-12}/K)^{1/p}$: $3.269748\times10^{-9}$ from the held fit, $3.149705\times10^{-9}$ from the free fit—the smallest declared-axis split that leaves a persistent imprint at the readable floor |
| Ray seed | $\Delta$ exactly $0.0$ at all five horizons for $\delta_g=1$, with a peak of $3.331\times10^{-16}$ over the whole run—a factor $30$ below `SILENCE_FLOOR_Q` |
| Fragility of the held fit alone | a synthetic pure transient at $\nu_{\rm true}=1.024\,\nu$ gives a held-fit offset at $57.2\%$ of the terminal reading (inside the persist band) while the free fit reads $0.0\%$ and a rate $1.024$: the conjunction is what keeps that reading a `TRANS` |
| Action on the coordinate, one step at $t_0$ | at the largest load and $\delta_g=1$, the split's one-step change of $A$ is $3.336084649308\times10^{-6}$ against the anchor's own one-step drift $6.248434071254\times10^{-5}$—$5.339073136189\times10^{-2}$ relative; on the ray seed the same quantity is exactly $0.0$ at $\delta_g=1$ and $0.1$ alike |
| Cost | $13.556$ s for one $22{,}500$-step flow, $6.025\times10^{-4}$ s per step, so the §6 schedule projects to $\approx137$ s at the measured rate and $\approx190$ s at §67's own recorded $8.36\times10^{-4}$ s per step |

Three design consequences are declared from the probe and not tuned afterwards: the readable floor `READABLE_FLOOR_Q` $=10^{-12}$ sits two decades below the smallest probe reading and eight decades above the float64 resolution of a coordinate of order one; the quiet floor `SILENCE_FLOOR_Q` $=10^{-14}$ sits a factor $30$ above the ray arm's probe peak; and the ray-distance tolerance `ANCHOR_RAY_TOL` $=5\times10^{-3}$ sits a factor $3.7$ above the anchor's measured $1.34\times10^{-3}$.

## 2. The statistic, the branch rule and the decision rule

### 2.1 The reading set, the fits, and the branch bands

For each sweep arm the five readings $\Delta(T_i)$, $i=1\ldots5$, are computed, together with the recorded diagnostics $|\Delta|_{\rm peak}$ with its time, the two-horizon ratio of §1.2, the anchor's own series, and the structural readings of gate 2. An arm is **measurable** iff its peak over the horizon set exceeds `READABLE_FLOOR_Q`; an arm that is not measurable is classified `BELOW_FLOOR` and carries no branch.

**Fit H (the declared statistic, rate held).** With $x_i=e^{-\nu T_i}$ and $\nu=$ `NU_REFERENCE`, the model

$$\Delta(T)=D_\infty+(D_0-D_\infty)e^{-\nu T}=D_\infty(1-x)+D_0 x$$

is **linear** in the pair $(D_\infty,D_0)$, so the two parameters are a least-squares solve of the $5\times2$ system with no iteration and no initial guess. Fit H reports the **offset $D_\infty^{\rm held}$**, the amplitude $D_0$, and its residual $\max_i|\text{model}-\Delta(T_i)|/\max_i|\Delta(T_i)|$.

**Fit F (the corroboration, rate free).** The same model with $\lambda$ free is fitted by a declared deterministic search: $\lambda$ on a $4001$-point log grid over $[\nu/4,4\nu]$, each $\lambda$ solved in closed form for $(D_\infty,D_0)$, then four declared refinement widths ($2\times10^{-3},2\times10^{-4},2\times10^{-5},2\times10^{-6}$ relative, $41$ points each) around the best $\lambda$. Fit F reports $\lambda$, its offset $D_\infty^{\rm free}$ and its residual, and it records whether $\lambda$ landed at the edge of the declared scan range.

**The branch rule.** A measurable arm is classified by the two fits, with $|\Delta(T_{\max})|$ the terminal reading:

| Branch | Condition | Meaning |
|---|---|---|
| `PERSIST` | $\lvert D_\infty^{\rm held}\rvert\ge$ `PERSIST_SHARE` $\cdot\lvert\Delta(T_{\max})\rvert$ **and** $\lvert D_\infty^{\rm free}\rvert\ge$ `PERSIST_SHARE` $\cdot\lvert\Delta(T_{\max})\rvert$ **and** both residuals $\le$ `RESIDUAL_BAND` | both fits leave an offset of at least half the terminal reading: the attractor itself moved |
| `TRANS` | $\lvert D_\infty^{\rm free}\rvert\le$ `TRANS_SHARE` $\cdot\lvert\Delta(T_{\max})\rvert$ **and** the free residual $\le$ `RESIDUAL_BAND` **and** $1/$ `CLOCK_TOLERANCE` $\le\lambda/\nu\le$ `CLOCK_TOLERANCE` | the reading is a decay at the realization's own clock: a transient |
| `UNRESOLVED` | otherwise | the two fits disagree, or neither two-parameter form describes the reading: the decay structure is not the declared one |
| `BELOW_FLOOR` | peak $\le$ `READABLE_FLOOR_Q` | nothing to classify |

### 2.2 The law, and the instrument

Over the arms classified `PERSIST`, a least-squares line of $\log|D_\infty^{\rm held}|$ on $\log\delta_g$ gives the exponent $p_w$ and the coefficient $K$, so the shifted attractor's distance from the unsplit ratio is

$$|D_\infty|\approx K\,\delta_g^{\,p_w},$$

with the per-level ratios to the fitted line, the adjacency jumps and the same label vocabulary the predecessor protocols use (`PROPORTIONAL`, `CLIFF`, `NONLINEAR`, `INCONCLUSIVE`), and with `MIN_READABLE` arms and monotonicity required before any label is issued. **The exponent is reported, not assumed**: proportionality is a result of the fit, not an input to it. The same fit is computed on the free fit's offsets and on the *terminal* readings and recorded under its own name, so a `PERTURBS_ONLY` or `INCONCLUSIVE` outcome still carries a fitted scaling of its own, and so the declared statistic can be checked against two others on the same numbers.

**The instrument.** With the fitted law, the split size at which the persisting shift equals the readable floor is

$$\delta_w=\Big(\frac{\text{READABLE\_FLOOR\_Q}}{K}\Big)^{1/p_w},$$

the smallest declared-axis split that leaves a *persistent* imprint on the attractor, and it is reported beside the largest level's raw reading.

### 2.3 Thresholds, declared before execution

| Constant | Value | Role |
|---|---|---|
| `READABLE_FLOOR_Q` | 1.0e-12 | an arm's peak below this is `BELOW_FLOOR` and carries no branch |
| `SILENCE_FLOOR_Q` | 1.0e-14 | the ray arm's $|\Delta|$ at **every** declared horizon must be at or below this |
| `PERSIST_SHARE` | 0.5 | the offset's share of the terminal reading required of **both** fits for `PERSIST` |
| `TRANS_SHARE` | 0.1 | the free offset's share of the terminal reading below which the reading is a pure decay |
| `RESIDUAL_BAND` | 0.25 | the two-parameter form's own residual, relative to the peak reading, above which the arm is `UNRESOLVED` |
| `CLOCK_TOLERANCE` | 2.0 | factor band on $\lambda/\nu$ in the `TRANS` clause, and the licence the gate-7 clock reading issues |
| `NU_REFERENCE` | 0.01119569724312185 | the declared relaxation rate, held in fit H and compared in gate 7; read from the successor receipt at run time and required to equal this literal |
| `NU_TOLERANCE` | 2.0 | factor within which the run's fitted clock must agree with `NU_REFERENCE` |
| `TAIL_FRACTION` | 0.01 | $e^{-\nu T_{\max}}$ must not exceed this |
| `MIN_SPAN` | 1.0 | $\nu(T_{\max}-T_{\min})$ must be at least this |
| `HORIZON_COUNT` | 5 | the declared number of horizons, all on one trajectory |
| `HORIZONS` | 30, 90, 180, 300, 450 | the declared horizons, in the arm's own time units |
| `RATE_SCAN_FACTOR` | 4.0 | fit F's free rate spans $[\nu/4,4\nu]$ |
| `RATE_SCAN_POINTS` | 4001 | the declared log grid for fit F |
| `RATE_REFINEMENT_WIDTHS` | 2.0e-3, 2.0e-4, 2.0e-5, 2.0e-6 | declared relative refinement widths for fit F |
| `RATE_REFINEMENT_STEPS` | 20 | declared half-width of each refinement scan |
| `DECADES` | 1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1 | §67's declared decades, the sweep's first six levels |
| `SWEEP_LEVELS` | 1.0e-6, 1.0e-5, 1.0e-4, 1.0e-3, 1.0e-2, 1.0e-1, 1.0 | the sweep family's split sizes, in the order of §3 |
| `DECLARED_DT` | 0.02 | the declared step; every horizon of §1.2 is an integer multiple of it |
| `PROBE_OFFSET_COEFFICIENT` | 3.378913644274e-4 | §1.5's measured offset law's coefficient, read by gate 6's declared-magnitude check |
| `PROBE_OFFSET_EXPONENT` | 1.005101810107 | §1.5's measured offset law's exponent, read by the same check |
| `MIN_READABLE` | 4 | `PERSIST` arms required before the law is issued |
| `MIN_PERSIST` | 2 | `PERSIST` arms required, the largest declared split among them, before `WRITES` is issued |
| `SECONDS_PER_STEP_ASSUMED` | 8.36e-4 | §6's conservative per-step rate, §67's own recorded cost |
| `SECONDS_PER_STEP_MEASURED` | 6.025e-4 | §6's measured per-step rate, this protocol's design probe |
| `PROJECTED_SECONDS` | 190.0 | §6's conservative projection over the declared schedule |
| `FIT_BAND` | 2.0 | per-level ratio to the fitted line |
| `EXPONENT_LOW` | 0.9 | lower edge of the linear band for $p_w$ |
| `EXPONENT_HIGH` | 1.1 | upper edge of that band |
| `JUMP_FACTOR` | 3.0 | a `CLIFF` near-miss: an adjacent pair growing by at least this factor times the growth the fitted exponent implies |
| `MONOTONE_TOL` | 1.5 | non-monotonicity beyond this is `INCONCLUSIVE` |
| `ACTION_FLOOR_LIVE` | 1.0e-3 | at the largest load and $\delta_g=1$, the split's change of $A$ over one declared step, relative to the anchor's own one-step drift, must exceed this |
| `ACTION_CEIL_SILENT` | 1.0e-15 | on the ray seed at the same $\delta_g$, the same quantity must not exceed this |
| `ANCHOR_RAY_TOL` | 5.0e-3 | the anchor's $\max|\varepsilon|/\max|\rho|$ at $T_{\max}$ must not exceed this |
| `LOAD_TOL` | 1.0e-12 | relative tolerance of the anchor's measured load against §67's declared largest |
| `LOAD_ABS_FLOOR` | 1.0e-15 | absolute tolerance for the bracket-free member of a load family |
| `STEP_SAFETY` | 40 | carried step rule |
| `PER_EXECUTION_CAP` | 50000 | steps in any one execution |
| `TOTAL_STEP_CAP` | 300000 | steps over the whole schedule |
| `DECLARED_EXECUTIONS` | 12 | §3 |
| `BOUND_SECONDS` | 600 | §6 |

### 2.4 Decision rule

`status=PASS` requires every gate of §4 and hence every feature; otherwise the run ends at `status=FAIL` with the write verdict null and no label issued. On `PASS`:

1. **`WRITES`** iff the largest declared split (`supersplit_load`, $\delta_g=1$) is `PERSIST` and at least `MIN_PERSIST` sweep arms are `PERSIST`. The law of §2.2 is then issued over the `PERSIST` arms if they number at least `MIN_READABLE`, and is reported as *not issued* with the count otherwise; the instrument $\delta_w$ is reported whenever the law is.
2. **`PERTURBS_ONLY`** iff the largest declared split is `TRANS`, no sweep arm is `PERSIST`, and at least `MIN_READABLE` sweep arms are `TRANS`. The largest split is named in this clause for the same reason it is named in the first: the phenomenon at issue is the strongest split's, and a null at that split cannot be turned into a verdict by smaller arms that decayed cleanly.
3. **`INCONCLUSIVE`** (the verdict null) in every other case, with the per-level classification table and the levels named.

## 3. The arms

Twelve declared executions, in this order. `anchor` arms are read for their own coordinate series and for the clock; `sweep` arms are classified and fitted; the `silence` and `canfail` arms are controls; the two oracle arms carry §67's own short and replication schedules and are read for their residual alone. Every arm with the long schedule is read at all five horizons of §1.2.

| # | Arm | Role | $c$ | $\delta_g$ | Schedule | Anchor/twin |
|---|---|---|---|---|---|---|
| 1 | `ray_short` | oracle | $0$ | $0$ | $100$ steps, $T=2$ | self |
| 2 | `ray_anchor` | anchor | $0$ | $0$ | $22{,}500$ steps, $T_{\max}=450$ | self |
| 3 | `ray_supersplit` | silence | $0$ | $1$ | $22{,}500$ steps | `ray_anchor` |
| 4 | `successor_replication` | oracle | $0$ | $0$ | $1{,}834$ steps, $T=36.66172105812361$ | self |
| 5 | `loadmax_anchor` | anchor | $2\times10^{-1}$ | $0$ | $22{,}500$ steps | self |
| 6 | `decade_1` | sweep | $2\times10^{-1}$ | $10^{-6}$ | $22{,}500$ steps | `loadmax_anchor` |
| 7 | `decade_2` | sweep | $2\times10^{-1}$ | $10^{-5}$ | $22{,}500$ steps | `loadmax_anchor` |
| 8 | `decade_3` | sweep | $2\times10^{-1}$ | $10^{-4}$ | $22{,}500$ steps | `loadmax_anchor` |
| 9 | `decade_4` | sweep | $2\times10^{-1}$ | $10^{-3}$ | $22{,}500$ steps | `loadmax_anchor` |
| 10 | `decade_5` | sweep | $2\times10^{-1}$ | $10^{-2}$ | $22{,}500$ steps | `loadmax_anchor` |
| 11 | `decade_6` | sweep | $2\times10^{-1}$ | $10^{-1}$ | $22{,}500$ steps | `loadmax_anchor` |
| 12 | `supersplit_load` | canfail | $2\times10^{-1}$ | $1$ | $22{,}500$ steps | `loadmax_anchor` |

The **sweep family** is arms 6–12 in increasing $\delta_g$: §67's six declared decades and the largest declared split above them. The levels are §67's own declared decades, at §67's own largest load, unchanged: this protocol re-opens neither the load axis nor the transport axis, and it inherits §67's arm table by measurement rather than by re-derivation (gate 3). `supersplit_load` is both the largest declared split of the write question and the can-fail control of gate 11.

## 4. Gates and features

### 4.1 Run-time gates

| # | Gate | Bound |
|---|---|---|
| 1 | binding, declared against observed, on all ten rows of §0 | exact |
| 2 | finite and nonnegative states, $0\le q<1$, and the annihilation and idempotence maxima over every recorded state | structural |
| 3 | the anchor's measured load equals §67's declared largest load | relative `LOAD_TOL` |
| 4 | the action of the split on the coordinate over one declared step, at the largest load and $\delta_g=1$ | $\ge$ `ACTION_FLOOR_LIVE` |
| 5 | the same quantity on the ray seed at $\delta_g=1$ | $\le$ `ACTION_CEIL_SILENT` |
| 6 | horizon adequacy, from declared numbers alone: `HORIZON_COUNT` horizons with distinct $e^{-\nu T_i}$; $\nu(T_{\max}-T_{\min})\ge$ `MIN_SPAN`; $e^{-\nu T_{\max}}\le$ `TAIL_FRACTION`; $T_{\max}\ge\ln(1/{\rm TAIL\_FRACTION})/\nu$; and at least `MIN_READABLE` declared levels whose probe magnitude exceeds `READABLE_FLOOR_Q` | structural, declared numbers only |
| 7 | the clock: the anchor's fitted $\rho$ decay rate over $[T_{\min},T_{\max}]$ against `NU_REFERENCE` | factor `NU_TOLERANCE` |
| 8 | schedule conformance, $\Delta t\le1/(40\lambda_{\max})$ on the arm's own loaded projection and $\Delta t\in\{0.05,0.02,0.01\}$ | every arm |
| 9 | declared shape: $12$ executions, no execution over the per-execution cap, total over the total cap | $12$, $50{,}000$, $300{,}000$ |
| 10 | the ray arm's $|\Delta|$ at every declared horizon | $\le$ `SILENCE_FLOOR_Q` |
| 11 | the largest declared split's peak $|\Delta|$ over the horizon set | $\ge$ `READABLE_FLOOR_Q` |
| 12 | the anchor sits at the ray at $T_{\max}$: its $\max|\varepsilon|/\max|\rho|$ on the projection | $\le$ `ANCHOR_RAY_TOL` |
| 13 | cross-protocol oracle: `ray_short` reproduces the §67 receipt's `ray_short` $\rho_{\max}$ | bit-identical |
| 14 | cross-executor oracle: `successor_replication` reproduces the successor receipt's `mode1_long` $\rho_{\max}$, $\rho_{\rm final}$ and $\lambda_{\max}$ | bit-identical |
| 15 | one process, no concurrent run | structural |

Gate 6 is the check the horizons exist for: a set too short to span a relaxation time, or one whose tail is not below the declared fraction, or one above the readable floor of the levels it must classify, is declared unpassable **before** any arm runs, so the run cannot return a classification the horizons never licensed. Gate 7 is what makes the held rate a reading rather than an assumption, and gate 12 is what makes a nonzero offset attributable to the split rather than to a reference that is still relaxing: an unsplit arm that has not reached its own ray cannot certify anyone else's attractor.

### 4.2 Features

| Feature | Condition |
|---|---|
| F1 | gate 11 holds: the largest declared split is readable—the can-fail control, without which no branch could be read |
| F2 | gate 10 holds: the ray arm is silent at every horizon—the predicted negative §67 earned |
| F3 | gates 13 and 14 hold: both oracles are bit-identical |
| F4 | gate 7 holds: the clock both fits depend on is the realization's own, verified in-run |
| F5 | gate 12 holds: the unsplit reference is at the ray at $T_{\max}$, so a split arm's offset is the split's |
| F6 | the largest declared split is classified, `PERSIST` or `TRANS`, rather than `UNRESOLVED` or `BELOW_FLOOR` |

F1–F3 are the instrument's licence, F4 the rate's licence, F5 the attribution's, and F6 the write question's own answerability at the strongest split.

## 5. Pre-flight reachability, before any integration

§67's pre-flight checked the split's action on the bracket's **rate**, which was the right check for that protocol and the wrong coordinate for this one. This protocol checks the action on the coordinate it classifies, and adds the checks that make a multi-horizon fit a test at all:

| Check | Quantity | Declared condition |
|---|---|---|
| 5.1 live | at the largest load and $\delta_g=1$, $|A(\text{one declared step with the split})-A(\text{the same step without it})|$ on the seeded state, relative to the anchor's own one-step drift | $\ge$ `ACTION_FLOOR_LIVE` |
| 5.2 silent | the same quantity on the ray seed at the same $\delta_g$ | $\le$ `ACTION_CEIL_SILENT` |
| 5.3 reduction | the split right-hand side at $\delta_g=0$ equals the successor's own right-hand side term for term | elementwise, $0$ difference |
| 5.4 horizon adequacy | $\nu(T_{\max}-T_{\min})$ against `MIN_SPAN`; $e^{-\nu T_{\max}}$ against `TAIL_FRACTION`; $T_{\max}$ against $\ln(1/{\rm TAIL\_FRACTION})/\nu$; and the per-level probe magnitudes against `READABLE_FLOOR_Q` | all four, from declared numbers alone |
| 5.5 branch reachability | synthetic five-horizon readings of all three structures at $\nu_{\rm true}/\nu\in\{0.5,1.0161,1.024,0.9,1.1,1.5,2\}$, classified by the §2.1 rule | every structure reaches its own branch, and the $2\nu$ transient is excluded by the clock band |
| 5.6 anchor load | the anchor's measured $\ell$ against §67's declared largest load, read from §67's receipt | relative `LOAD_TOL` |
| 5.7 anchor ray distance | the anchor's $\max|\varepsilon|/\max|\rho|$ at $T_{\max}$ | $\le$ `ANCHOR_RAY_TOL` |

5.1 and 5.2 are checked by the self-check **and** evaluated as gates 4 and 5 at run time. From §1.5 the expected readings are $5.339073136189\times10^{-2}$ live and exactly $0.0$ silent, so the live direction clears its floor by a factor $53$ and the silent direction is an identity rather than a near miss: neither can be satisfied by accident, and the ray's exact silence is the reading §67 earned. 5.5 is the check that a fit of this shape is decidable at all: it is *not* required that the synthetic witnesses be the readings the run makes—it is required that the rule reaches each branch on readings built from the same model, and it is that requirement which exposes the held fit's fragility (§1.3) as a property of the rule rather than as a surprise at the run.

**The branch witnesses, measured before freezing.** Each row is a synthetic five-horizon reading built from the probe's own amplitudes ($D_\infty=-3.3329\times10^{-10}$, $D_0=-1.1149\times10^{-10}$) and classified by the rule of §2.1; `share` is the held fit's offset as a fraction of the terminal reading, which is what a held fit alone would threshold.

| $\nu_{\rm true}/\nu$ | pure transient | pure shift | shift with overshoot |
|---|---|---|---|
| $0.5$ | `TRANS` (share $1.97$) | `PERSIST` ($0.92$) | `PERSIST` ($0.95$) |
| $0.9$ | `TRANS` ($1.52$) | `PERSIST` ($0.99$) | `PERSIST` ($1.00$) |
| $1.0$ | `TRANS` ($0.00$) | `PERSIST` ($1.01$) | `PERSIST` ($1.00$) |
| $1.0161$ | `TRANS` ($0.37$) | `PERSIST` ($1.01$) | `PERSIST` ($1.01$) |
| $1.024$ | `TRANS` ($0.57$) | `PERSIST` ($1.01$) | `PERSIST` ($1.01$) |
| $1.1$ | `TRANS` ($3.16$) | `PERSIST` ($1.02$) | `PERSIST` ($1.01$) |
| $1.5$ | `TRANS` ($73.9$) | `PERSIST` ($1.04$) | `PERSIST` ($1.03$) |
| $2.0$ | `UNRESOLVED` ($1122.6$) | `PERSIST` ($1.05$) | `PERSIST` ($1.03$) |

**The oracle readings, declared as literals.** Gates 13 and 14 compare against numbers read from the two digest-bound receipts, and the executor also checks that each declared literal still equals the receipt's own value, so a tampered receipt fails the binding rather than the oracle:

| Literal | Value | Source |
|---|---|---|
| `ORACLE_RAY_RHO` | $5.329147248815693\times10^{-16}$ | §67 receipt, arm `ray_short`, $\rho_{\max}$ |
| `ORACLE_REPLICATION_RHO` | $2.622443969747147\times10^{-15}$ | successor receipt, arm `mode1_long`, $\rho_{\max}$ |
| `ORACLE_REPLICATION_FINAL` | $2.219140084394095\times10^{-15}$ | successor receipt, arm `mode1_long`, $\rho_{\text{final}}$ |
| `ORACLE_REPLICATION_LAMBDA` | $1.0331312281605476$ | both receipts, the same arm's $\lambda_{\max}$ |
| `ORACLE_RAY_LOAD` | $3.646114292316331\times10^{-1}$ | §67 receipt, arm `loadLmax_reference`, the declared largest load's measured value |
| `ORACLE_CLOCK` | $1.119569724312185\times10^{-2}$ | successor receipt, `relaxation.arms.relax_reference.fit.nu_fit`, the relaxation rate of §1.4 |

## 6. Run schedule, budget and stopping rule

| Item | Value |
|---|---|
| Command | `timeout 600 python computations/verify_loop_carrier_attractor_write.py`, one process from this directory tree's root |
| Executions | $12$, one per arm, in the order of §3 |
| Steps | $10\times22{,}500+100+1{,}834=226{,}934$ against the total cap $300{,}000$; the largest arm is any of the ten at $22{,}500$ against the per-execution cap $50{,}000$ |
| Cost, stated in the bound | ten arms run the full $22{,}500$ steps and each is read at five horizons of that one run, so a horizon costs nothing: at §67's own recorded $8.36\times10^{-4}$ s per step the schedule projects to $189.7$ s, and at this protocol's design probe's measured $6.025\times10^{-4}$ s per step to $136.7$ s |
| Bound | `600` s, $3.2\times$ the conservative projection and $4.4\times$ the measured one; §67's own protocol ran its $22$ arms under the same $600$ s |
| Stopping rule | one invocation; the executor refuses a second while its receipt exists; no arm, level, horizon, threshold or band is edited after the run |

The bound is stated against the conservative rate rather than the flattering one because the two arms that carry the verdict—the anchor and the largest split—are the two longest, and because a bound discovered at the run is not a bound.

## 7. References

* `foundations/loop-to-bubble-projection-theorem.md`—(LB1)–(LB14), the loop law, its projection, the member family and the fixed ray.
* `computations/verify_loop_to_bubble_projection.py`—the frozen discrete operators, bound by digest.
* `computations/verify_loop_carrier_projection_relaxation.py`—the successor's executed probe, imported for the carrier law, the projection, the composition, the integrator, the canonical companion and the seeds, bound by digest.
* `computations/verify_loop_carrier_projection_split.py`—the spent split protocol's executor, imported for the split right-hand side and the split gate field, bound by digest.
* `computations/verify_loop_carrier_gate_load.py`—§67's executed executor, imported for the loaded seed, the load metric, the residual, the structure readings and the log-space power-law fit, bound by digest.
* `computations/loop-carrier-gate-load-prereg.md`—§67's protocol, whose largest declared load, decades and load axis this protocol holds fixed.
* `runs/loop_carrier_gate_load/verification.json`—§67's receipt, source of the largest load's measured value and of the `ray_short` oracle reading.
* `runs/loop_carrier_projection_split/verification.json`—the spent split protocol's receipt, source of the ray oracle reading and of the inertness §67 closed.
* `runs/loop_carrier_projection_relaxation/verification.json`—the successor receipt, source of the replication oracle reading and of the relaxation rate this protocol holds.
* `field-experience/probe-outcome-ledger.md` §65–§67—the three predecessor outcomes this protocol reads and does not re-open.
* `open-questions-cassi-answers.md`—the trace-versus-null-vector separation that keeps every reading here from being read as evidence about the conversion ratio.

## 8. Post-execution record

Not yet executed. This protocol and `computations/verify_loop_carrier_attractor_write.py` are frozen at the digests in §0; the invocation, its gate table, its per-arm readings, its branch classifications, its law, its instrument and its write verdict belong in this section, under the stopping rule of §6.
