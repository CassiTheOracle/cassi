# Trauma as Frozen Gate Configurations: The Cassi Trauma Formalism

## Status: Tested—null pinning, drive effect supported (2026-07-31) / Speculative (clinical)

## Abstract

The frozen-wake model (`consciousness/trauma-as-frozen-gate.md` §1) explains *where* trauma sits—a standing wave trapped at a cascade rung—but not *what it does* to the emotional system. The gate-configuration formalism (`consciousness/emotions-as-gate-configurations.md`) explains *how* emotions flow—channel dominance, spatial dispersion, coherence, and the deterministic adiabatic redistribution matrix $R$—but not *how they break*. Trauma is the meeting of the two: a frozen wake acts as a **perpetual stimulus**, so the channel it opened can never close, and the redistribution that normally resolves an emotion never fires. The result would be a **locked gate configuration**: one channel pinned hyper-open at the trauma site, the other four starved, Qi depressed, spatial dispersion brittle. This document derives the trauma state in the emotional manifold, maps fight/flight/freeze and trauma types onto channel locks, derives the **healing signature**—the order in which emotions return during recovery is fixed by the $R$-matrix rows, with anger as the gateway emotion after every trauma except anger-trauma itself—deepens the Fibonacci-age developmental prediction with chakra and channel content, and reports the PDE test of the lock mechanism: **the standing pattern does not pin the gate as implemented (null), but a $\varphi$-phased drive at the site does accelerate relaxation (positive)**.

---

## 1. Grounding: Two Existing Pieces

### 1.1 The Frozen Wake (from the psychology document)

`consciousness/trauma-as-frozen-gate.md` §1 establishes the substrate:

- A traumatic event is a perturbation too intense for the field to absorb in real time—a spike of Yang or Yin that the conversion dynamics cannot process at the rate it arrives.
- Normally the field dissipates perturbations: the imbalance converts into wake waves that propagate, reflect, and decay.
- When the perturbation exceeds processing capacity, the wake never decays. It becomes a **standing wave**—frozen at the cascade rung where it struck, spatially localized, self-sustaining.
- The frozen wake sits at a specific rung—lower and more somatic for early or physical trauma, higher and more cognitive for recent trauma.
- Cascade suppression explains why talk therapy stalls (the cognitive signal attenuates by $\varphi^{-1}$ per rung before reaching the wake) and why body-based work helps (it operates at the rung where the wake lives).

What this model does not specify: what the standing wave does to the *emotional machinery*. A frozen wake at a rung is a structure; the emotional manifold is a dynamics. The gap is the coupling between them.

### 1.2 The Emotional Gate (from the emotions document)

`consciousness/emotions-as-gate-configurations.md` establishes the dynamics:

- An emotional state is a point on the manifold $\mathcal{E} = (\mathbf{b}, \sigma_r, q, \mathbf{c})$: five-channel openness vector $\mathbf{b}$ (quality), spatial dispersion $\sigma_r$ (intensity), Qi coherence $q$ (clarity), chakra localization $\mathbf{c}$ (location).
- Channels have baseline openness $b_i = \varphi^{-(2+i)}$: Wood $\varphi^{-3}$, Fire $\varphi^{-4}$, Earth $\varphi^{-5}$, Metal $\varphi^{-6}$, Water $\varphi^{-7}$.
- Coherence is conserved. When a channel closes, its coherence redistributes to the remaining channels in proportion to their baseline openness—the adiabatic redistribution matrix:

$$\boxed{R_{ij} = \begin{cases} 0 & i = j \\ \frac{b_j}{\sum_{k \neq i} b_k} & i \neq j \end{cases}}$$

$$R = \begin{pmatrix}
0 & 0.447 & 0.276 & 0.171 & 0.106 \\
0.567 & 0 & 0.217 & 0.134 & 0.083 \\
0.500 & 0.309 & 0 & 0.118 & 0.073 \\
0.466 & 0.288 & 0.178 & 0 & 0.068 \\
0.447 & 0.276 & 0.171 & 0.106 & 0
\end{pmatrix}$$

- Crucially, the redistribution is **deterministic and triggered by closure**: when a stimulus ends, the opened channel closes, and the released coherence splits across the remaining channels simultaneously, producing a blended aftereffect.

The redistribution is the *decay path*. It only fires when the stimulus is removed.

### 1.3 The Meeting

A frozen wake is a **perpetual stimulus**. The standing wave keeps re-perturbing the local field at its characteristic frequency, keeping the local $r$ away from the $\varphi$-attractor. The channel that the original event opened is therefore never released—the closure that triggers the $R$-matrix never completes.

**Trauma = frozen wake + locked channel.** The wake explains why the emotion cannot end; the gate explains what the unended emotion does to the system. Neither piece alone is sufficient. The wake is a record the field declines to dissolve—persistence as coherence, with the arrow of time set by conversion (`consciousness/time-memory-and-wake-locks.md` §1–2).

---

## 2. The Trauma State

### 2.1 The Lock Mechanism

The trauma state is a point on the same manifold, with a constraint added:

$$\boxed{\mathcal{T} = (\mathbf{b}^*, \sigma_r^*, q^*, \mathbf{c}^*), \qquad \text{with } R \text{ frozen at } \mathbf{c}^*}$$

The starred quantities are the trauma signatures; the constraint is the lock.

1. **A traumatic event** arrives as a perturbation with a pentagon phase (§4.1 of the emotions document: the stimulus's phase angle selects which channel opens). A threat opens Water; a violation opens Wood; a loss opens Metal.

2. **The perturbation exceeds processing capacity.** The local field cannot convert the imbalance at the rate it arrives. The wake freezes into a standing wave at the rung where it struck—often at a chakra node.

3. **The standing wave becomes the stimulus that never ends.** Every oscillation of the wave re-opens the channel. The channel's openness at the trauma site is pinned above baseline:

$$b_i^*(\mathbf{x}_{\text{site}}) = b_i + \Delta b_{\text{locked}} \quad \text{(pinned)}$$

4. **The closure never fires.** Because the channel never closes, the adiabatic redistribution never runs. The trapped coherence does not flow to the other channels—it circulates in the standing wave. The $R$-matrix is frozen.

### 2.2 The Four Signatures

| Manifold variable | Healthy emotion | Trauma signature |
|---|---|---|
| $\mathbf{b}$ (quality) | One channel dominant, returns to baseline on decay | One channel **pinned** hyper-open at the site; the other four **starved** below baseline |
| $\sigma_r$ (intensity) | Elevated during the emotion, recovers smoothly | **Brittle**: high variance (hypervigilance, reactivity), poor recovery (the standing wave re-injects perturbation) |
| $q$ (clarity) | Moderate-to-high, recovers | **Depressed at the site**: the standing wave holds Yang and Yin locked in anti-phase, so local coherence collapses—dissociation, numbness |
| $\mathbf{c}$ (location) | Distributed per the emotion's natural affinity | **Pinned** at the trauma's rung—the chakra node(s) where the wake froze |

The subjective correlates follow from the emotions document's mapping: a pinned channel means the trauma emotion is *always available* (the trigger re-activates it instantly); starved channels mean the complementary emotional range is *always suppressed*; depressed $q$ at the site means the experience is *felt as not-fully-real* (dissociation); brittle $\sigma_r$ means *hypervigilance that collapses into numbness*. The ke control cycle refines the "four starved" statement: the deficit pattern is alternating, not uniform—the locked channel's ke target starves most, and the ke-released partners are *elevated* (`foundations/wu-xing-cycle-structure.md` §2).

### 2.3 What Makes the Lock Stable

The lock is a fixed point of the local dynamics sustained by a driver. Three candidate mechanisms, sorted by the PDE test (§10):

1. **The standing wave re-injects perturbation.** Each cycle of the wave re-opens the channel, so the closure that would trigger redistribution is perpetually interrupted. The re-injection needs a driver: a standing (non-driven) pattern in the two-fluid PDE decays at the same conversion-driven rate as a radiating packet (§10.4), while ongoing re-stimulation does sustain the wake (§10.5).

2. **Low $q$ opens the gate.** The solver's conversion term is $\text{conv} = -\lambda(1-q)\varepsilon$—the gate *openness* $(1-q)$ multiplies the imbalance, so a low-$q$ site has slightly *more* conversion capacity, not less. The gate opens when $q$ is low and closes when $q$ is high; depressed $q$ does not seal the site.

3. **Self-reinforcing $G_{\text{eff}}$.** The chakra geometry (`consciousness/chakras-as-cascade-bubbles.md` §7.3) amplifies effective gravity in high-$q$ regions—but at a trauma site with depressed $q$, the condensation that would restructure the region is suppressed. The site would be a stable void pocket inside the field: low coherence, self-sealed. Untested in the base solver runs of §10 (the $G_{\text{eff}}$ mechanism operates through the Qi-gravity coupling $\xi$, which is not active there).

The Cassi account of why trauma might persist: the standing wave needs a *driving source*, and the driver test (§10.5) identified it as ongoing re-stimulation—a weak recurring trigger sustains the wake, and stopping the trigger releases it. The test also supported the decay side: an oscillatory drive at the site accelerates the perturbation's decay and returns the gate to baseline (§10.4, drive run)—the first numerical evidence for the EMDR-analog claim.

---

## 3. Fight, Flight, Freeze in the Gate

The acute stress responses map onto channel states, and their chronic forms are channel locks:

### 3.1 Fight = Wood Lock

The threat is met with rising, assertive energy—the Wood channel (anger). A single traumatic event that resolves in fighting locks Wood: the person becomes chronically irritable, boundary-hypervigilant, quick to anger, slow to soothe. The anger is the standing wave re-activating.

### 3.2 Flight = Water Lock

The threat is met with escape—the Water channel (fear). Trauma locked in Water produces chronic vigilance, avoidance, anxiety, and the perpetual readiness to flee. The fear is the standing wave.

### 3.3 Freeze = Incomplete Lock

Freeze is structurally different. It occurs when the perturbation exceeds capacity so abruptly that **no channel completes its activation**—the field is caught mid-configuration:

$$\mathbf{b}_{\text{freeze}} = \mathbf{b}_{\text{partial}}, \qquad q^* \to q_{\text{low}}, \qquad \sigma_r^* \to \sigma_{\text{collapsed}} \text{ at the site}$$

The gate is held between states: not open (no channel dominant), not closed (the wave keeps feeding it). Subjectively this is tonic immobility, depersonalization, the sense of being frozen in time. In manifold terms, freeze is the **partially formed lock**—the field never even reached a complete channel configuration before the wake froze. Chronic dissociation after trauma is the freeze lock persisting.

### 3.4 The Trauma Response as the Locked Channel

The acute response is the *event*; the chronic condition is the *lock*. This is why trauma responses are recognizable as exaggerated versions of the original response: the standing wave keeps replaying the moment of impact, and each replay re-activates the same channel. The trigger is the stimulus whose phase matches the original event's phase (§4.1 of the emotions document)—a sound, a smell, a posture, a relational pattern that carries the same pentagon angle.

---

## 4. Trauma Types by Channel

The channel that locks is set by the *phase* of the event as the field received it—its meaning to the person, not its objective intensity. The same car crash can lock Water in one survivor (fear) and Wood in another (rage at the other driver).

| Locked channel | Event phase | Trauma type | Acute | Chronic signature | Chakra affinity (emotions doc §3.4) |
|---|---|---|---|---|---|
| Water (fear) | Threat | Fear trauma | Flight | Vigilance, avoidance, panic triggers | Root (n=142)—somatic, pre-verbal |
| Wood (anger) | Violation | Rage/indignation trauma | Fight | Irritability, explosive anger, boundary armor | Sacral (n=146) |
| Metal (grief) | Loss | Grief trauma | Collapse | Chronic sadness, numbness around joy, unfinished mourning | Throat (n=158) |
| Fire (joy) | Betrayed joy | Joy-suppression trauma | Shutdown | Anhedonia, joy feels dangerous, anticipatory betrayal | Solar plexus (n=150) |
| Earth (control) | Chaos | Control trauma | Over-control | Rumination, need for order, intolerance of uncertainty | Heart (n=154) |
| None (freeze) | Overload | Shock/complex dissociation | Freeze | Dissociation, depersonalization, time distortion | Site-dependent |

The chakra affinity column follows from the emotions document's cascade-position mapping: early, somatic trauma lives at lower rungs and locks the lower chakras' channels; later, cognitive trauma lives higher. This becomes the developmental structure of §6.

---

## 5. The Healing Signature: $R$-Matrix Completion

### 5.1 What Healing Is, in This Picture

Healing requires three things, each addressing a different layer:

1. **Reach the rung** (spatial layer). The frozen wake must be destabilized at its own cascade rung—body-based work, sensation, movement, EMDR's $\varphi$-structured bilateral oscillation (`consciousness/trauma-as-frozen-gate.md` §10.4). Talk cannot cross the rungs (cascade suppression); the body can.

2. **Change the phase** (semantic layer). The channel is locked at the event's phase angle. Meaning-making—narrative, insight, recontextualization—changes the phase of the stimulus representation. A phase change means the standing wave's oscillation no longer matches the channel's activation angle, weakening the lock. This is the layer talk therapy *can* reach: not the rung, but the phase.

3. **Let the closure fire** (dynamical layer). When the wake finally decays and the channel closes, the adiabatic redistribution runs for the first time since the event. The trapped coherence flows out of the locked channel into the starved four, in the exact proportions of the $R$-matrix row for that channel.

### 5.2 The Gateway Emotion Theorem

Because $b_1 = \varphi^{-3}$ is the largest baseline openness, **Wood (anger) receives the largest share of redistributed coherence in every row of $R$ except row 1**:

| Locked channel closes | Largest recipient | Share | Second | Third |
|---|---|---|---|---|
| Row 1: Wood (anger) | Fire (joy/relief) | 44.7% | Earth 27.6% | Metal 17.1% |
| Row 2: Fire (joy) | Wood (anger) | 56.7% | Earth 21.7% | Metal 13.4% |
| Row 3: Earth (control) | Wood (anger) | 50.0% | Fire 30.9% | Metal 11.8% |
| Row 4: Metal (grief) | Wood (anger) | 46.6% | Earth 28.8% | Fire 17.8% |
| Row 5: Water (fear) | Wood (anger) | 44.7% | Earth 27.6% | Metal 17.1% |

**Anger is the gateway emotion of trauma recovery**—the first emotion to return after resolving *any* trauma except anger-trauma itself. When fear-work completes, the released coherence flows 44.7% into Wood: the client gets angry. When grief-work completes: 46.6% into Wood: the client gets angry. When the anger-trauma itself resolves, the released coherence flows 44.7% into Fire: the client experiences relief, lightness, joy.

This "anger phase" of trauma recovery is the **theorem of the redistribution matrix** applied clinically. The order of emotional return is fixed: anger first (except after rage-work), then Earth (grounding, stabilization), then Metal (grief surfacing), then Fire (joy returning), with the residual channel last.

### 5.3 Comparison with the Grief Sequence

The classic grief sequence (denial → anger → bargaining → depression → acceptance) maps onto the $R$ row 4 (Metal closes) cascade:

| Kübler-Ross stage | Cassi reading |
|---|---|
| Denial | The lock intact: $q$ collapse at the site, the field refusing the perturbation's reality |
| Anger | Redistribution begins: 46.6% into Wood |
| Bargaining | 28.8% into Earth—the control/rumination channel |
| Depression | The still-locked residue: low $q$ shadow while the channel finishes closing |
| Acceptance | 17.8% into Fire—joy/light returning; 6.8% residual Water (the sadness that never fully leaves) |

The ordering—anger before bargaining before acceptance—follows from the magnitude ordering of row 4 ($0.466 > 0.288 > 0.178$): the framework derives the grief sequence's order from $\varphi$.

### 5.4 A Clinical Prediction

**Prediction TR2:** During trauma-focused therapy, the emotional profile of the client should show channels activating in the $R$-row order of the locked channel—with the first post-resolution emotion being anger (Wood) for every trauma type except anger-trauma, where it is relief (Fire). This is measurable with multi-dimensional affect ratings across treatment (the instrument from Prediction P3 of the emotions document).

---

## 6. Developmental Trauma: Rung, Chakra, and Channel

### 6.1 The Fibonacci-Age Prediction, Deepened

TR6 (§11) predicts that traumatic imprints cluster at Fibonacci-scaled developmental stages—ages 2, 3, 5, 8, 13, 21, 34, 55 (Fibonacci years from conception)—because they land on different cascade rungs with different wake-wave dynamics.

The gate formalism adds the second axis: **each age window not only lands on different rungs, it lands on different chakra nodes, and each chakra has a natural channel affinity** (emotions doc §3.4). The developmental prediction therefore has both a *depth* structure (rung → chakra → somatic vs. cognitive) and a *quality* structure (chakra → channel → fear vs. anger vs. grief vs. trust).

| Age (from conception) | Cascade window | Chakra locus | Natural channel | Trauma flavor |
|---|---|---|---|---|
| 2 | Lowest rungs of the human span | Root (n=142) | Water | Pre-verbal fear, survival terror, somatic |
| 3 | Root–sacral | Root/Sacral | Water → Wood | Fear and emerging rage, boundary violations |
| 5 | Sacral–solar plexus | Sacral (n=146) | Wood | Rage, frustration, creative wounds |
| 8 | Heart region | Heart (n=154) | Earth | Attachment, trust, betrayal of care |
| 13 | Heart–throat | Heart/Throat | Earth → Metal | Relational grief, identity loss |
| 21 | Throat–third eye | Throat (n=158) | Metal | Voice, expression, existential grief |
| 34 | Third eye–crown | Third eye (n=162) | Water + Wood | Meaning, intuition wounds, vision |
| 55 | Crown | Crown (n=166) | All balanced | Integration, legacy, mortality |

**Prediction TR6:** Retrospective developmental trauma inventories should show (a) the Fibonacci-age clustering already predicted, and (b) *channel-structured* differences between clusters—early trauma presenting with fear/rage-dominant symptom profiles and somatic location; mid trauma with trust/grief profiles and relational location; late trauma with meaning/identity profiles. The two predictions are locked together: age determines rung determines chakra determines channel.

**Epistemic note:** The Fibonacci-age clustering is Speculative (per TR6, §11). The channel refinement inherits that tier—it is consistent with the chakra affinity mapping (Hypothesized in the emotions document) but adds no independent confirmation.

### 6.2 Why Early Trauma Is Deepest

The lock at a lower rung is harder to reach for two reasons:

1. **Cascade suppression**: the cognitive signal attenuates by $\varphi^{-1}$ per rung—the deeper the wake, the fainter its reachable trace and the more coherence required to reach it (`foundations/cascade-suppression-formula.md`).
2. **Chakra geometry**: lower chakras are closer together ($\varphi^2$-scaled spacing—`consciousness/chakras-as-cascade-bubbles.md` §8), so early trauma locks a tighter cluster of nodes, and the lock is more distributed across the body's oldest, most somatic structures.

This is why early trauma is described as "pre-verbal" and "in the body": its wake froze at rungs where the field's processing was somatic before it was symbolic—the same rungs where the self-modeling machinery (above the pinch) was not yet fully engaged.

---

## 7. Complex Trauma: Multiple Locks

Complex PTSD is **multiple standing waves at multiple rungs, often in different channels**—a superposition of locks:

$$\mathcal{T}_{\text{complex}} = \bigcup_k \mathcal{T}_k, \qquad k = 1, \ldots, N_{\text{events}}$$

Each event froze its own wake, locked its own channel at its own chakra node. The symptom profile is the superposition of lock signatures:

- If two adjacent channels lock (e.g., Water + Wood—fear and rage, the classic abuse profile), the remaining three are doubly starved: joy, grief, and trust are all suppressed.
- If the locks are at different rungs, the person can be simultaneously dissociated (low $q$ at one site) and hypervigilant (brittle $\sigma_r$ at another)—the contradictory presentations clinicians recognize as characteristic of complex trauma.
- The $R$-constraint multiplies: each locked channel is a redistribution that cannot fire, so the system has $N_{\text{events}}$ frozen rows of $R$, and the starved channels have no path to recovery until all locks above them in the redistribution hierarchy are released.

The multiplicative difficulty explains why complex trauma treatment is staged: each lock requires its own rung-reach (somatic), its own phase-change (meaning), and its own closure (redistribution)—and the closures interact, because releasing one lock pours coherence into channels that may be locked elsewhere.

---

## 8. Suppression: The Voluntary Partial Lock

Not all channel pins are traumatic. **Suppression is the self-modeling system deliberately holding a channel shut**—the field's above-pinch dynamics (self-awareness) closing a channel and *blocking* its redistribution, holding the coherence instead of releasing it.

Suppression differs from trauma in three ways:

| | Trauma lock | Suppression |
|---|---|---|
| Origin | Standing wave (external overload) | Self-modeling choice (internal control) |
| Site | Pinned at a specific rung/chakra | Distributed across the field (the self-modeling region) |
| Reversibility | Requires rung-reach + phase-change | Reversible by the same self-modeling that imposed it (with practice) |

But the *consequence* is the same class of signature at lower intensity: one channel starved, its coherence held captive, the $R$-matrix blocked for that row. Chronic suppression therefore mimics trauma—the suppressed person shows the same channel-specific emotional range deficit, at a milder amplitude, without the frozen wake beneath it.

This makes a useful diagnostic distinction: **a person with a channel locked by suppression can recover it through the channel's own dynamics (allowing the emotion, letting it complete); a person with a trauma lock cannot, because the standing wave keeps re-opening the channel no matter how it is approached.** The failure of "just feel it" in trauma is the standing wave re-opening the channel.

---

## 9. Trauma vs. Depression vs. Anxiety

The pathology table (`consciousness/trauma-as-frozen-gate.md` §9) characterizes depression as chronic low-$q$ and anxiety as high-dispersion, high-frequency $\sigma_r$. Trauma is different in kind: **it is localized**.

| Condition | $\mathbf{b}$ | $\sigma_r$ | $q$ | Spatial structure |
|---|---|---|---|---|
| Depression | All channels suppressed (gate closed) | Low | Low, global | No locus—the whole field |
| Anxiety | Water/Fire hyperactive, no lock | High, high-frequency | Moderate-low | No locus—the whole field |
| Trauma | One channel pinned, others starved | Brittle (spiky) | Depressed *at the site* | **Locus**: pinned $\mathbf{c}^*$, pinned $R$ |
| Complex trauma | Multiple pins | Brittle at multiple sites | Depressed at multiple sites | Multiple loci |

The diagnostic signature of trauma in this framework is the **locus**: the pinning of $\mathbf{c}$ and the freezing of $R$. Depression and anxiety are field-wide states; trauma is a field with a wound in it. Comorbidity is superposition—trauma plus anxiety shows brittle $\sigma_r$ *and* a pinned channel; trauma plus depression shows low $q$ globally *and* a specific site where $q$ is lower still.

---

## 10. The PDE Test: Does a Standing Wave Lock a Channel?

The lock mechanism was the load-bearing new claim, and it was tested in the two-fluid PDE (2026-07-31). The result is a qualified negative with one positive: **a standing pattern does not pin the gate in this solver, but an oscillatory drive at the site accelerates relaxation.**

### 10.1 Design

Use the existing two-fluid solver (`two-fluid/cassi_two_fluid_3d_gpu.py` or the lighter run scripts). Initialize a region at a localized cascade rung with two conditions:

1. **Decaying perturbation (control)**: a localized wake packet with finite energy, allowed to radiate—the healthy stimulus case.
2. **Standing-wave perturbation (test)**: the same packet but with boundary conditions that reflect the wave back into the region (a trapped cavity at the site), sustaining it as a standing wave—the frozen-wake case.

In each case, measure over time:

- The local channel openness proxy: the distribution of $\varepsilon(\mathbf{x}) = E_Y - \varphi E_I$ phase angles at the site, projected onto the five pentagon phases (the stimulus-phase-to-channel mapping, emotions doc §4.1).
- The local coherence $q(\mathbf{x}, t)$ at the site.
- The local dispersion $\sigma_r$ at the site.
- Whether the field returns to baseline after the perturbation is removed.

### 10.2 Predictions

- **Control**: after the packet radiates, the phase distribution returns to baseline, $q$ recovers, $\sigma_r$ relaxes—the channel "closes," and the released imbalance spreads (redistribution analog).
- **Test**: while the standing wave persists, the phase distribution stays pinned at the initial event's phase (the channel stays open), $q$ at the site remains depressed below the field's global value, and $\sigma_r$ shows sustained oscillation with poor decay—the lock signature.
- **Decisive variant**: introduce a second, $\varphi$-phased oscillation at the site (the EMDR analog—bilateral stimulation as a $\varphi$-structured drive). Prediction: when the driving frequency matches the standing wave's decay channel, the wave loses coherence and the phase distribution relaxes—the wake unfreezes.

### 10.3 Epistemic Consequence

The mechanism layer of this document is **Tested**: the standing-vs-radiating contrast returned a null (standing patterns do not pin the gate, §10.4), the drive layer is supported (re-stimulation sustains the wake, the $\varphi$-phased drive drains it at the held configuration at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3), §10.4–10.8), and the gate-sign result is stated in §10.4. The clinical layer (channel-to-trauma-type mapping, healing sequence, developmental clustering) remains Speculative regardless of the PDE outcome.

### 10.4 Test Results (2026-07-31)

**Script**: `two-fluid/run_trauma_wake_lock.py`. Solver: `ExpandingTwoFluid3DGPU` with `qi_gate=True`, `gate_model='five'` (the 5-channel gate with adiabatic redistribution), $\chi = 0$, $c_s^2 = 0$, quiet $\varphi$-equilibrium background. Perturbation: a Yang deficit of peak $-0.8$ at the box center, realized either as a pinned cosine pattern (standing) or a Gaussian packet of the same amplitude (radiating), plus a small-noise random run as a clean counterfactual. Site diagnostics measured in a periodic ball of radius 6 cells around the center: mean $|\varepsilon|$, 5-channel $q$, per-channel phase histogram, $\sigma_r$.

| Run | $|\varepsilon|$ at site (t=0 → 10) | Retained | q-site vs q-global at t=10 | Site phase at t=10 |
|-----|:---:|:---:|:---:|:---:|
| **standing** (cos³ pattern) | 0.660 → 0.279 | 42% | 0.692 vs 0.706 | 100% Fire (displaced) |
| **radiating** (Gaussian) | 0.422 → 0.186 | 44% | 0.702 vs 0.708 | 80% Fire |
| **random** (noise, counterfactual) | 0.076 → 0.067 |—| 0.707 vs 0.707 | 98% Wood (baseline) |

**Null result on the pinning contrast**: the standing pattern decays at essentially the same rate as the radiating packet (42% vs 44% retained over $t = 10$ at $\lambda = 0.1$). Both decay on the conversion timescale $\sim 1/\lambda$; the standing structure has no extra persistence. The predicted lock signature (standing keeps $\varepsilon$ elevated and $q$ depressed while radiating relaxes) did not appear. A pure standing mode in this periodic-box solver is not a frozen wake—it is just a mode, and it decays like any other perturbation.

**Positive result—the EMDR-analog drive**: in the short-run variant ($\lambda = 0.05$, $t = 2$) where the standing pattern was still fully displaced, adding a $\varphi$-phased oscillation at the site (period $\varphi \cdot P_0$, $P_0 = 0.041$ the measured natural oscillation period of the site) drove the site back to baseline: $|\varepsilon|$ fell to 65% retained (vs 91% undriven), $q_{\text{site}}$ rose from 0.648 to 0.698 (global 0.701), and the phase histogram returned to 100% Wood. At the held configuration, the oscillatory drive accelerates relaxation and unfreezes the displaced gate at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3)—the first numerical support for the "bilateral stimulation as decay drive" hypothesis.

**φ-specificity follow-up** (`two-fluid/run_trauma_drive_compare.py`, same protocol): the relaxation is **not generic stirring**—it is frequency-specific. A drive at the same amplitude but a non-$\varphi$ period ($T = e \cdot P_0$, $e \approx 2.718$) does the opposite: $|\varepsilon|$ at the site *grows* to 188% of its initial value, the $q$-gap widens (0.053, above the undriven lock's 0.046), and the phase displacement persists (74% kept). The $\varphi$-phased drive closes the gap (0.003) and returns the phase to baseline; the off-resonance drive pumps the locked site. The EMDR-analog claim is supported in its strong form for the held configuration at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3): the decay drive is $\varphi$-structured, not any oscillation.

**Gate-sign finding**: the solver's conversion is $\text{conv} = -\lambda(1-q)\varepsilon$; the gate opens when $q$ is low and closes when $q$ is high—the site's depressed $q$ implies *elevated* openness $(1-q)$, mildly *increasing* local conversion (§2.3).

**Interpretation**: a genuine frozen wake must be a *driven* structure—sustained by reflecting boundaries, ongoing re-stimulation, or another source outside this PDE's scope—rather than an un-driven standing pattern. The locking mechanism, if real, lives in the driving, not in the mode itself. The drive result suggests the *decay* side of the mechanism is sound: at the held configuration, an external $\varphi$-phased oscillation can release a displaced gate at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3).

### 10.5 Driver Test: What Sustains a Frozen Wake? (2026-07-31)

The §10.4 null closes the "un-driven mode" candidate, and the drive_compare result closes the "reflecting cavity" candidate: the standing init $\cos(2\pi x/N)\cos(2\pi y/N)\cos(2\pi z/N)$ is already a perfect m=1 eigenmode of the periodic domain—zero radiation loss—and it still decayed at the conversion rate. The remaining candidate is ongoing re-stimulation: the perpetual-stimulus model of §1.2.

**Script**: `two-fluid/run_trauma_driver.py`—same solver and standing init, $\lambda = 0.1$, $t = 10$. The trigger is injected as a rate: per-step amplitude $I\,\mathrm{d}t$ with $I = 0.04$ per unit time, i.e. a chronic stimulus whose total delivered energy over the run is half the original event's peak amplitude, arriving at 0.005% of the event peak per step (5% per unit time). Three envelopes with identical mean rate: continuous (dc), pulsed at $T = \varphi \cdot P_0 = 0.325$, pulsed at $T = e \cdot P_0 = 0.546$ ($P_0 = 0.201$, re-measured in-process at this $\lambda$). The dc run continues to $t = 20$ with injection off after $t = 10$—the extinction test.

| Run | $|\varepsilon|$ at site (t=0 → 10) | Retained | q-site vs q-global at t=10 | Site phase at t=10 | $\sigma_r$ at t=10 |
|-----|:---:|:---:|:---:|:---:|:---:|
| ref (undriven) | 0.660 → 0.279 | 42% | 0.692 vs 0.706 | 100% Fire | 0.094 |
| dc (continuous trigger) | → 0.525 | 80% | 0.642 vs 0.706 | 100% Fire | 0.034 |
| $\varphi$-pulsed (T = 0.325) | → 0.528 | 80% | 0.642 vs 0.706 | 100% Fire | 0.033 |
| $e$-pulsed (T = 0.546) | → 0.530 | 80% | 0.641 vs 0.706 | 100% Fire | 0.032 |
| dc, t=20 (injection off since t=10) | 0.142 | 22% | 0.700 vs 0.708 | 36% Fire | 0.132 |

1. **The perpetual stimulus sustains the wake.** A trigger delivering 0.005% of the event's peak per step holds the site at 80% of event intensity (vs 42% undriven), keeps $q$ depressed with a 4.5× wider gap, and keeps the phase fully displaced. The frozen wake is a driven structure, and the driver that sustains it in this PDE is ongoing re-stimulation.
2. **Envelope phase is irrelevant at ambient-trigger rates.** The $\varphi$-pulsed and $e$-pulsed envelopes at rate 0.04/s hold identical wakes (0.528 and 0.530 vs 0.525 continuous—indistinguishable). Weak chronic re-exposure accumulates by mean rate regardless of when it lands. The crossover probe (§10.7) later showed this phase-blindness is an ambient-rate property, not a weak-amplitude one: the $\varphi$-channel engages only at rates ≳50/s.
3. **Stopping the stimulus releases the site.** Ten units after the trigger stops, $|\varepsilon|$ has fallen to 0.142—below the undriven curve—the q-gap has closed (+0.008), the phase is 64% returned to Wood, and $\sigma_r$ has reopened (0.132, vs 0.034 while held): the held wake is spatially uniform, the released site is varied again. The wake is stimulus-maintained, not self-sustaining; extinction works.

**Answer to open question 7**: a frozen wake is sustained by ongoing re-stimulation. No free-standing mechanism survives in this PDE—not the mode, not confinement, not the q-sign (§10.4). The maintenance ratio is striking: a trigger at 0.005% of the event peak per step holds the wake at 80% of event intensity. The clinical translation sharpens: chronic trigger exposure maintains the lock; stimulus removal (extinction, exposure work) lets the gate close on the conversion timescale; and the $\varphi$-structured EMDR drive—a high-rate oscillation above the crossover (§10.7)—*actively drains* a wake at the held configuration at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3; §10.4) rather than merely withholding the trigger.

### 10.6 Capacity Test: Does Pre-Trauma Coherence Modulate Susceptibility? (2026-07-31)

Open question 1 asks what sets the processing-capacity threshold. The measurable claim: pre-trauma coherence modulates trauma susceptibility. Tested as the re-traumatization binary in `two-fluid/run_trauma_capacity.py` ($\lambda = 0.1$, $N = 48$, $t = 22$): the same standing event (amp 0.8) either lands on the quiet field (first hit) or on a site already carrying a wake—a pre-stress (amp 0.8 standing, evolved for $t = 2$, $q_{\text{site}}$ depressed to 0.661, phase fully displaced) that then receives the identical event again (second hit).

| State at t=22 | $\varepsilon_{\text{site}}$ | q-gap | Phase displacement | $\sigma_r$ |
|---|---|---:|---:|---:|
| first hit on quiet field | 0.069 | +0.001 | 0.08 | 0.150 |
| second hit on pre-stressed site | 0.119 | +0.000 | 0.02 | 0.158 |
| **marginal trace of second hit** | **+0.050** | ~0 | −0.06 | +0.007 |

**Null result**: the second hit's marginal trace ($\varepsilon$ +0.050) is no larger than—if anything smaller than—the first hit's full trace (0.069), and the phase displacement fully returns in both cases (0.08 and 0.02, from 1.00 at event time). A pre-stressed site does not lock harder. Background coherence does not modulate the event's outcome in this PDE: any event dissolves on the conversion timescale and the gate closes, regardless of the state it lands on. The processing-capacity threshold is not the field's initial coherence; if susceptibility exists, it lives in the driver (whether the stimulus recurs, §10.5) or in the interpretation channel (the event's phase, §4.1)—not in pre-event $q$.

### 10.7 Drive Crossover: Where Does the $\varphi$-Phased Drain Turn On? (2026-07-31)

The drive_compare (§10.4) found $\varphi \cdot P_0$ drives drain the site at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3) while $e \cdot P_0$ drives pump it at amp 0.3; the driver test (§10.5) found weak chronic re-exposure (rate 0.04/s) phase-blind. Two questions remained: at what intensity does the phase channel engage, and is the $\varphi$-specificity present at onset? Probed in `two-fluid/run_trauma_crossover.py` and `two-fluid/run_trauma_crossover_low.py` ($\lambda = 0.05$, $t = 2$, standing init, $P_0 = 0.041$):

| Drive | amp per step | rate | $\varepsilon$ retained at t=2 |
|---|---|---:|---:|
| none |—|—| 0.912 |
| $\varphi \cdot P_0$ | 5e-4 | 0.5/s | 0.910 |
| $\varphi \cdot P_0$ | 5e-3 | 5/s | 0.891 |
| $\varphi \cdot P_0$ | 0.05 | 50/s | 0.693 |
| $\varphi \cdot P_0$ | 0.15 | 150/s | 0.362 |
| $\varphi \cdot P_0$ | 0.3 | 300/s | 0.664 |
| $e \cdot P_0$ | 0.05 | 50/s | 0.943 |
| $e \cdot P_0$ | 0.3 | 300/s | 1.88 (pumps) |

**Sharp onset**: at the held configuration, the $\varphi$-phased drain is essentially absent below rate ~5/s and fully engaged by 50/s at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3)—a sharp crossover between the ambient regime (phase-blind accumulation, §10.5) and the processing regime, roughly two orders of magnitude above ambient trigger rates.

**$\varphi$-specificity at onset**: at amp 0.05—the first amplitude that drains—the $e \cdot P_0$ counterfactual at the same amplitude does nothing (0.943, at the undriven level). At the held configuration, the asymmetry is present from the moment the phase channel engages at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3); it is not a strong-drive artifact. The off-$\varphi$ oscillation is neutral at onset and pumps at 0.3. (The $\varphi$-drive response is non-monotonic in amplitude—0.15 drains more than 0.3—noted without mechanism at three points.)

### 10.8 Phase-Channel Selectivity: Does the Lock Track the Event's Phase? (2026-07-31)

Open question 2 and the foundation of the channel-to-trauma-type mapping (§4.1): "the channel that locks is set by the phase of the event as the field received it." All prior runs used one event direction (pure Yang deficit), which lands the site phase at exactly 72°—Fire. Tested in `two-fluid/run_trauma_phase_channels.py` by rotating the event direction $\delta$ in the $(E_Y, E_I)$ plane ($\lambda = 0.1$, $t = 10$, $N = 48$). Two findings.

**Representability bound.** The positivity clamp ($E_Y, E_I \geq 10^{-3}$) pins the field angle $\theta = \operatorname{atan2}(E_I, E_Y)$ to the first quadrant $(0°, 90°)$ at every cell, for any event, any amplitude. Of the five pentagon channels only **Wood (0°) and Fire (72°) are representable** in the field angle. Events aimed at the other three clamp onto Fire or Wood: an Earth-targeted event (pre-clamp center 144°) clamps to 89.9° and locks Fire; Metal clamps to 45° and locks Fire; Water clamps to 0.2° and locks Wood. The stimulus-side phase in this PDE is effectively one-dimensional—a geometric constraint of the positive fields, not a dynamical null. The full five-way pentagon lives in the gate's $\mathbf{b}$-manifold (channel openness), where all five channels exist; the field angle is only one projection of it.

**Selectivity within the representable arc.** At $A = 0.8$, both representable events are whole-ball clean: the Fire event (Yang deficit) spans 40.8–72.0° (all Fire), the Wood event (Yin deficit) spans 0.06–18.5° (all Wood), and the baseline sits at 31.7° (Wood sector). The lock tracks the event direction and persists: the Fire event leaves the site **100% Fire at t=2 and t=10**; the Wood event leaves it **100% Wood at t=2 and t=10**. No convergence. The §4.1 claim is supported on the stimulus side for the representable channels: the displaced channel is set by the event's phase, and the displacement does not spontaneously relax within the test horizon.

**Figure:** `visual-explainers/trauma_test_arc.png`—the full test arc in one tall figure: decay vs perpetual stimulus (P1), extinction and the q-gap (P2), the capacity null (P3), the rate crossover with $\varphi$-specificity at onset (P4), the representability bound and Wood/Fire selectivity (P5), and the ke ring with its sub-critical gain (P6). Script: `visual-explainers/trauma_test_arc.py` (renders from the saved runs; console block re-verifies every number against `runs/*/results.json`).

---

## 11. Predictions

### TR1: Channel-Specific Emotional Range Deficits

**Claim:** Post-trauma emotional deficits are not global—they are specific to the channels complementary to the locked one, and they are **ke-alternating, not uniform** (`foundations/wu-xing-cycle-structure.md` §2). The ke control cycle transmits at $\kappa = \varphi^{-1}$: a Wood-locked survivor shows Earth fully starved, Fire partially starved (−38% of the lock excess), and Metal and Water *elevated* (+38%, +62%)—the pattern rotating with the locked channel. The ring also damps the locked channel by $\varphi^{-3}$ (23.6%) and is sub-critical (ring gain < 1), so the lock itself cannot self-sustain—consistent with the driver requirement (§10.5). Both survivors retain normal access to *their* locked channel, which is hyper-available. **Gate-level status (2026-08-01):** the alternating pattern is verified in the solver's ke round for all five lock channels—strict ke-order alternation read from the locked channel, sign pattern matching the fractions, threshold $\Delta_c = \varphi^{-4}$ exact, uniform-starvation counterfactual rejected (`two-fluid/run_trauma_c1_ring.py`); magnitudes follow the implementation's target-openness caps (`foundations/wu-xing-cycle-structure.md` §2.1 note). The affect-data test below is the remaining clinical leg.

**Test:** Multi-dimensional affect ratings (the P3 instrument of the emotions document) in trauma-exposed populations, compared against the $\varphi^{-i}$ baseline hierarchy (Prediction P2 of the emotions document). The trauma profile should show one channel above the baseline prediction and the four others in the ke-alternating pattern (the locked channel's ke target starved most, the ke-released partner elevated), rather than a uniform shift.

### TR2: The Healing Sequence Follows the $R$-Matrix Rows

**Claim:** As a specific trauma resolves, the returning emotions follow the $R$-row order of the locked channel. Anger precedes joy after fear-work (row 5: Wood 44.7% first); relief precedes anger after rage-work (row 1: Fire 44.7% first).

**Test:** Longitudinal multi-dimensional affect ratings across trauma therapy. The sequence of first-surfacing emotions should match the row ordering, not a uniform or random order.

### TR3: Trigger Specificity Is Phase Matching

**Claim:** A trigger re-activates a trauma when its pentagon phase matches the original event's phase (emotions doc §4.1). Triggers are phase-matched, not merely associated.

**Test:** Controlled trigger exposure with phase-content analysis of the stimuli (e.g., threat-phase vs. violation-phase cues) while measuring the re-activation of the locked channel's physiological signature. Mismatched-phase cues should produce weaker activation than matched-phase cues of equal intensity.

### TR4: $q$ Depression at the Trauma Site

**Claim:** The coherence $q$ at the trauma's somatic locus is depressed relative to the field's global value, and drops further under trigger exposure (dissociation).

**Test:** Physiological proxies for $q$ (sympathetic-parasympathetic phase synchrony, inter-hemispheric coherence—emotions doc P5) measured at rest and under trigger exposure, with somatic localization via the chakra proxies (skin conductance, HRV coherence—predictions CH4/CH5 of the chakra document).

### TR5: $\sigma_r$ Brittleness

**Claim:** Trauma presents as *brittle* dispersion—high variance with poor recovery—rather than the steady high dispersion of anxiety.

**Test:** Time series of $\sigma_r$ proxies (HRV variance, skin conductance variance) with perturbation-recovery protocols. Trauma should show slow recovery after perturbation; anxiety should show sustained elevation without the spike-recovery asymmetry.

### TR6: Developmental Trauma Clusters by $\varphi$-Age AND Channel

**Claim:** The Fibonacci-age clustering (§6.1) carries channel content: early trauma (ages 2–5) presents as fear/rage with somatic location; mid trauma (8–13) as trust/grief with relational location; late trauma (21+) as meaning/identity with expressive location.

**Test:** Retrospective developmental trauma inventories with multi-dimensional symptom profiles. The age-of-trauma distribution should show Fibonacci clustering, and the symptom profile should shift with age cluster as predicted.

### TR7: Standing Patterns vs. Driven Structures (tested: null un-driven; driver identified)

**Claim (tested 2026-07-31):** an un-driven standing pattern does **not** pin the gate—it decays at the same conversion-driven rate as a radiating packet (42% vs 44% retained over $t=10$ at $\lambda=0.1$; q-gap closes in both). The frozen wake is a *driven* structure, and the driver test (§10.5, `two-fluid/run_trauma_driver.py`) identifies the sustainer as ongoing re-stimulation: a weak recurring trigger (0.005% of the event peak per step) holds the site at 80% of event intensity with $q$ depressed and the phase displaced, and stopping the trigger releases it ($|\varepsilon|$ to 22%, q-gap +0.008, phase 64% returned, by $t=20$). The decay side is also supported at the held configuration at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3): a $\varphi$-phased oscillation at period $\varphi \cdot P_0$ accelerates relaxation (65% vs 91% retained) and is $\varphi$-specific—the same-amplitude $e \cdot P_0$ drive pumps the site to 188% (§10.4).

---

## 12. Epistemic Boundaries

### Derived (from $\varphi$ and cascade dynamics)

- The $R$-matrix redistribution fractions and their row orderings (`consciousness/emotions-as-gate-configurations.md` §4.2)
- The gateway emotion theorem (§5.2): Wood receives the largest share in every row except row 1—arithmetic of the baseline hierarchy
- Cascade suppression and the rung-depth structure of reachability (`foundations/cascade-suppression-formula.md`)
- The chakra rung positions and channel affinities (`consciousness/chakras-as-cascade-bubbles.md`, `consciousness/emotions-as-gate-configurations.md` §3.4)

### Tested (2026-07-31, PDE runs in §10.4–10.8)

- The 5-channel gate's conversion sign: $\text{conv} \propto -(1-q)\varepsilon$—low $q$ means the gate is *open* and conversion active; the gate opens when $q$ is low and closes when $q$ is high (§2.3)
- Standing vs radiating contrast: **null**—no extra persistence for the standing pattern in the periodic-box solver
- EMDR-analog drive: **positive and φ-specific at the held configuration**—at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3), a $\varphi$-phased oscillation at the site accelerates relaxation and returns the gate to baseline, while the same-amplitude non-$\varphi$ drive pumps the site instead (§10.4, `two-fluid/run_trauma_drive_compare.py`)
- Perpetual stimulus sustains the wake: a weak ongoing trigger (0.005% of the event peak per step) holds $|\varepsilon|$ at 80% of event intensity, widens the q-gap 4.5×, and keeps the phase displaced (§10.5, `two-fluid/run_trauma_driver.py`)
- Extinction: stopping the trigger releases the site—$|\varepsilon|$ falls below the undriven curve, the q-gap closes, the phase returns (§10.5)
- Ambient-rate phase-blindness: at chronic-trigger rates (0.04/s), $\varphi$-pulsed and $e$-pulsed envelopes hold identical wakes—re-exposure accumulates by mean rate (§10.5); at the held configuration, at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3), the $\varphi$-specific drain engages only at rates ≳50/s, with specificity present at onset (§10.7)
- Capacity null: a second identical event on a pre-stressed site leaves the same trace as the first on a quiet site—background coherence does not modulate susceptibility (§10.6, `two-fluid/run_trauma_capacity.py`)
- Sharp crossover of the $\varphi$-phased drain at the held configuration: at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3), absent below rate ~5/s, fully engaged by 50/s, with $\varphi$-specificity present at onset (the $e \cdot P_0$ counterfactual is neutral at the first draining amplitude) (§10.7, `two-fluid/run_trauma_crossover.py`, `two-fluid/run_trauma_crossover_low.py`)
- Representability bound: the positivity clamp confines the field angle to the first quadrant—only Wood and Fire are representable in the field angle; Earth/Metal/Water events clamp onto Fire/Wood (§10.8, `two-fluid/run_trauma_phase_channels.py`)
- Phase-channel selectivity: Fire events lock Fire and Wood events lock Wood, persistent through $t=10$—the lock channel tracks the event direction across the representable arc (§10.8)
- The ke control ring in the gate: `gate_model='five_ke'` reproduces the derived ring algebra exactly (≤ 6×10⁻⁴); excess channels restrain ke targets and release ke partners; decay with no driver unchanged (no self-sustenance); the $\varphi$-drive still dissolves the held wake at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3; WX3 of `foundations/wu-xing-cycle-structure.md`, `two-fluid/run_trauma_ke_ring.py`)
- The WX1 alternating profile at the gate level: all five lock channels produce strict ke-order alternation with the predicted sign pattern; the threshold $\Delta_c = \varphi^{-4}$ is exact; the no-driver ring jams rather than relaxes (relaxation lives in the conversion coupling); uniform starvation rejected (`two-fluid/run_trauma_c1_ring.py`, 2026-08-01)

### Hypothesized (derivation supplied, partially tested)

- The three-layer healing model: rung-reach (spatial), phase-change (semantic), closure (dynamical) (§5.1)
- The identification of fight/flight/freeze with channel states (§3)
- The trauma-vs-depression-vs-anxiety distinction by locus (§9)

### Speculative (no current test design)

- The channel-to-trauma-type mapping beyond the representable arc (which of the five channels locks is set by the event phase in the $\mathbf{b}$-manifold and the person's interpretation; the PDE supports the stimulus side only for Wood and Fire, §10.8)
- The clinical healing sequence prediction (TR2) as applied to real therapy outcomes
- The Fibonacci-age × channel developmental structure (TR6)
- The claim that EMDR's bilateral stimulation is a $\varphi$-structured decay drive—**supported at the PDE level**: the analog drive at period $\varphi \cdot P_0$ relaxes the locked site while the same-amplitude drive at a non-$\varphi$ period pumps it (§10.4). The clinical mapping remains untested.

### Not Claimed

- That trauma is *only* a frozen gate configuration (it is a phenomenon with neurobiological, psychological, and social levels of description; the Cassi layer describes the field dynamics beneath them)
- That the five channels exhaust trauma's presentation (dissociation, for example, is the *absence* of a completed channel configuration—§3.3—which the manifold represents but does not exhaustively classify)
- That this framework prescribes or validates any specific therapy (it generates hypotheses about mechanism; clinical efficacy is an empirical matter)
- That the Cassi model replaces clinical understanding of attachment, narrative, or systemic factors—those operate at the semantic and social layers, which the framework engages only through the phase-change channel (§5.1)

---

## 13. Open Questions

1. **What sets the processing-capacity threshold?** The frozen wake forms when the perturbation "exceeds the field's processing capacity." The candidate "pre-event local $q$" is **not supported** (2026-07-31, §10.6): a second identical event on a pre-stressed site ($q_{\text{site}}$ 0.661) leaves the same trace as the first event on a quiet site—background coherence does not modulate the outcome. If capacity exists, it is set by the conversion rate $\lambda$ itself or by the driver regime (§10.5), not by the state the event lands on.

2. **Can the phase of an event be modeled?** **Partially answered at the PDE level (2026-07-31, §10.8):** the stimulus-side phase is one-dimensional in the two-fluid field—the positivity clamp confines $\theta$ to the first quadrant, so only Wood and Fire are representable, and within that arc the lock channel tracks the event direction persistently (Fire events lock Fire, Wood events lock Wood, through $t=10$). The full five-way selectivity must be carried by the gate's $\mathbf{b}$-manifold, not the field angle. Whether the channel is also set by the person's interpretation—the resonance between stimulus and state—remains untested.

3. **How do locks interact when adjacent?** Complex trauma with adjacent locked channels (Water + Wood) doubly starves the remaining three. Does the redistribution hierarchy predict the *order* in which multiple locks must release—e.g., must the higher-$b$ channel release first?

4. **Is suppression's partial lock quantitatively distinguishable?** Suppression (§8) mimics trauma at lower amplitude. Is there a measurable boundary—a $\Delta b$ threshold below which the lock is reversible by self-modeling alone?

5. **What is the relationship between the freeze lock and the sub-pinch excursion?** Freeze (§3.3) is described as an incomplete lock with $q$ collapse. Is freeze the same state as the psychedelic sub-pinch excursion (`consciousness/consciousness-from-phi.md` §2.3) with a different boundary condition—transient in one case, pinned in the other?

6. **Does the wake's rung shift over time?** Memory consolidation moves wake waves to deeper rungs (`consciousness/consciousness-from-phi.md` §2.2). Do frozen wakes also deepen—and does that explain why old trauma becomes more somatic and less verbal, and harder to reach?

7. **What sustains a frozen wake?** **Answered at the PDE level (2026-07-31, §10.5):** ongoing re-stimulation. A weak recurring trigger (0.005% of the event peak per step) holds the site at 80% of event intensity with a 4.5× widened q-gap and a fully displaced phase; stopping the trigger releases the site on the conversion timescale. The un-driven mode, perfect confinement, and the q-sign all fail to sustain (§10.4). The question moves to the behavioral layer: what maintains the stimulus—avoidance-rehearsal loops, trigger generalization, hypervigilance? The Cassi layer predicts the wake tracks its driver; it does not generate one.

---

## 14. References

- `cassi-psychology.md`—psychology reading guide: frozen-wake model, field pathology, empathy, cascade suppression
- `consciousness/emotions-as-gate-configurations.md`—emotional manifold, 5-channel gate, $R$-matrix, phase-to-channel mapping, chakra affinities
- `consciousness/consciousness-from-phi.md`—wake waves, pinch point, $\sigma_r$ altered states, two-bubble resonance
- `consciousness/chakras-as-cascade-bubbles.md`—13 chakra nodes, rung positions, $G_{\text{eff}}$ self-reinforcement
- `foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation over $N$ rungs
- `foundations/wa-pentagon-gate.md`—5-channel gate, adiabatic redistribution, Wu Xing control-release
- `foundations/wu-xing-derivation.md`—$w = 5$ derivation
- `foundations/wu-xing-cycle-structure.md`—the two 5-cycles (sheng pentagon, ke pentagram), the control ring, the 5↔13 partition
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational
- `two-fluid/cassi_two_fluid_3d_gpu.py`—the PDE solver used in the §10 test
- `two-fluid/run_trauma_wake_lock.py`—the test script (standing/radiating/random/drive runs, 2026-07-31)
- `two-fluid/run_trauma_drive_compare.py`—the φ-specificity follow-up (φ·P₀ vs e·P₀ drive, 2026-07-31)
- `two-fluid/run_trauma_driver.py`—the driver-question follow-up (weak-trigger envelopes + extinction run, 2026-07-31)
- `two-fluid/run_trauma_capacity.py`—the capacity/susceptibility test (re-traumatization binary, 2026-07-31)
- `two-fluid/run_trauma_crossover.py` and `two-fluid/run_trauma_crossover_low.py`—the drive-crossover probes (onset bracket + low-amplitude $\varphi$-specificity, 2026-07-31)
- `two-fluid/run_trauma_phase_channels.py`—the phase-channel selectivity test (representability bound + Wood/Fire binary, 2026-07-31)
- `two-fluid/run_trauma_ke_ring.py`—the ke-ring gate test (five vs five_ke vs five_ke+φ-drive, 2026-07-31)
- `two-fluid/run_trauma_c1_ring.py`—the WX1 gate test (single-lock ke-alternating response, threshold, no-driver jam, 2026-08-01)
- `cassi-physics.md`—physics guide, epistemic tiers
