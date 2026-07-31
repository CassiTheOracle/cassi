# Trauma as Frozen Gate Configurations: The Cassi Trauma Formalism

## Status: Tested—null pinning, drive effect supported (2026-07-31) / Speculative (clinical)

## Abstract

The frozen-wake model (`cassi-psychology.md` §16) explains *where* trauma sits—a standing wave trapped at a cascade rung—but not *what it does* to the emotional system. The gate-configuration formalism (`consciousness/emotions-as-gate-configurations.md`) explains *how* emotions flow—channel dominance, spatial dispersion, coherence, and the deterministic adiabatic redistribution matrix $R$—but not *how they break*. Trauma is the meeting of the two: a frozen wake acts as a **perpetual stimulus**, so the channel it opened can never close, and the redistribution that normally resolves an emotion never fires. The result would be a **locked gate configuration**: one channel pinned hyper-open at the trauma site, the other four starved, Qi depressed, spatial dispersion brittle. This document derives the trauma state in the emotional manifold, maps fight/flight/freeze and trauma types onto channel locks, derives the **healing signature**—the order in which emotions return during recovery is fixed by the $R$-matrix rows, with anger as the gateway emotion after every trauma except anger-trauma itself—deepens the Fibonacci-age developmental prediction with chakra and channel content, and reports the PDE test of the lock mechanism: **the standing pattern does not pin the gate as implemented (null), but a $\varphi$-phased drive at the site does accelerate relaxation (positive)**.

---

## 1. Grounding: Two Existing Pieces

### 1.1 The Frozen Wake (from the psychology document)

`cassi-psychology.md` §16 establishes the substrate:

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

**Trauma = frozen wake + locked channel.** The wake explains why the emotion cannot end; the gate explains what the unended emotion does to the system. Neither piece alone is sufficient.

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

The subjective correlates follow from the emotions document's mapping: a pinned channel means the trauma emotion is *always available* (the trigger re-activates it instantly); starved channels mean the complementary emotional range is *always suppressed*; depressed $q$ at the site means the experience is *felt as not-fully-real* (dissociation); brittle $\sigma_r$ means *hypervigilance that collapses into numbness*.

### 2.3 Why the Lock Was Thought to Be Stable

The lock was hypothesized to be a fixed point of the local dynamics. Three mechanisms were proposed; the PDE test (§10) has since qualified two of them:

1. **The standing wave re-injects perturbation.** Each cycle of the wave re-opens the channel, so the closure that would trigger redistribution is perpetually interrupted. **Status after test: unverified.** A standing (non-driven) pattern in the two-fluid PDE decays at the same conversion-driven rate as a radiating packet (§10.4)—in this solver a pure standing structure is not self-sustaining.

2. **Depressed $q$ closes the gate.** **Falsified as stated.** The solver's conversion term is $\text{conv} = -\lambda(1-q)\varepsilon$—the gate *openness* $(1-q)$ multiplies the imbalance, so a low-$q$ site has slightly *more* conversion capacity, not less. The sign of the self-reinforcement claim was inverted.

3. **Self-reinforcing $G_{\text{eff}}$.** The chakra geometry (`consciousness/chakras-as-cascade-bubbles.md` §7.3) amplifies effective gravity in high-$q$ regions—but at a trauma site with depressed $q$, the condensation that would restructure the region is suppressed. The site would be a stable void pocket inside the field: low coherence, self-sealed. **Status after test: untested** (the $G_{\text{eff}}$ mechanism operates through the Qi-gravity coupling $\xi$, which is not active in the base solver runs of §10).

The honest Cassi account of why trauma might persist is therefore still open: the standing wave needs a *driving source* (a genuine reflecting cavity, or a self-sustaining process outside the tested PDE), or the persistence must be carried by a different mechanism entirely. What the test *did* support: an oscillatory drive at the site accelerates the perturbation's decay and returns the gate to baseline (§10.4, drive run)—the first numerical evidence for the EMDR-analog claim.

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

1. **Reach the rung** (spatial layer). The frozen wake must be destabilized at its own cascade rung—body-based work, sensation, movement, EMDR's $\varphi$-structured bilateral oscillation (`cassi-psychology.md` §16). Talk cannot cross the rungs (cascade suppression); the body can.

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

This is the "anger phase" of trauma recovery—not as a clinical stage model, but as a **theorem of the redistribution matrix**. The order of emotional return is fixed: anger first (except after rage-work), then Earth (grounding, stabilization), then Metal (grief surfacing), then Fire (joy returning), with the residual channel last.

### 5.3 Comparison with the Grief Sequence

The classic grief sequence (denial → anger → bargaining → depression → acceptance) maps onto the $R$ row 4 (Metal closes) cascade:

| Kübler-Ross stage | Cassi reading |
|---|---|
| Denial | The lock intact: $q$ collapse at the site, the field refusing the perturbation's reality |
| Anger | Redistribution begins: 46.6% into Wood |
| Bargaining | 28.8% into Earth—the control/rumination channel |
| Depression | The still-locked residue: low $q$ shadow while the channel finishes closing |
| Acceptance | 17.8% into Fire—joy/light returning; 6.8% residual Water (the sadness that never fully leaves) |

The ordering—anger before bargaining before acceptance—follows from the magnitude ordering of row 4 ($0.466 > 0.288 > 0.178$). The framework does not *assume* the grief sequence; it derives the sequence's order from $\varphi$.

### 5.4 A Clinical Prediction

**Prediction T2:** During trauma-focused therapy, the emotional profile of the client should show channels activating in the $R$-row order of the locked channel—with the first post-resolution emotion being anger (Wood) for every trauma type except anger-trauma, where it is relief (Fire). This is measurable with multi-dimensional affect ratings across treatment (the instrument from Prediction P3 of the emotions document).

---

## 6. Developmental Trauma: Rung, Chakra, and Channel

### 6.1 The Fibonacci-Age Prediction, Deepened

`cassi-psychology.md` §15 already predicts that traumatic imprints cluster at Fibonacci-scaled developmental stages—ages 2, 3, 5, 8, 13, 21, 34, 55 (Fibonacci years from conception)—because they land on different cascade rungs with different wake-wave dynamics.

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

**Prediction T6:** Retrospective developmental trauma inventories should show (a) the Fibonacci-age clustering already predicted, and (b) *channel-structured* differences between clusters—early trauma presenting with fear/rage-dominant symptom profiles and somatic location; mid trauma with trust/grief profiles and relational location; late trauma with meaning/identity profiles. The two predictions are locked together: age determines rung determines chakra determines channel.

**Epistemic note:** The Fibonacci-age clustering is Speculative (per `cassi-psychology.md` §15). The channel refinement inherits that tier—it is consistent with the chakra affinity mapping (Hypothesized in the emotions document) but adds no independent confirmation.

### 6.2 Why Early Trauma Is Deepest

The lock at a lower rung is harder to reach for two reasons:

1. **Cascade suppression**: the cognitive signal attenuates by $\varphi^{-1}$ per rung—the deeper the wake, the fainter its reachable trace and the more coherence required to reach it (`cassi-psychology.md` §5).
2. **Chakra geometry**: lower chakras are closer together ($\varphi^2$-scaled spacing—`consciousness/chakras-as-cascade-bubbles.md` §8), so early trauma locks a tighter cluster of nodes, and the lock is more distributed across the body's oldest, most somatic structures.

This is why early trauma is described as "pre-verbal" and "in the body": its wake froze at rungs where the field's processing was somatic before it was symbolic—the same rungs where the self-modeling machinery (above the pinch) was not yet fully engaged.

---

## 7. Complex Trauma: Multiple Locks

Complex PTSD is not a more intense single lock—it is **multiple standing waves at multiple rungs, often in different channels**:

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

This makes a useful diagnostic distinction: **a person with a channel locked by suppression can recover it through the channel's own dynamics (allowing the emotion, letting it complete); a person with a trauma lock cannot, because the standing wave keeps re-opening the channel no matter how it is approached.** The failure of "just feel it" in trauma is not resistance—it is the standing wave.

---

## 9. Trauma vs. Depression vs. Anxiety

The psychology document (`cassi-psychology.md` §17) characterizes depression as chronic low-$q$ and anxiety as high-dispersion, high-frequency $\sigma_r$. Trauma is different in kind: **it is localized, not global**.

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

### 10.3 Epistemic Consequence (pre-test)

The mechanism layer of this document (standing wave pins channel openness; depressed $q$ is self-reinforcing) was **Hypothesized with a designed test**—it would graduate from Speculative once the PDE run was performed, exactly as the two-bubble resonance did for the empathy mapping (`consciousness/consciousness-from-phi.md` §3). The clinical layer (channel-to-trauma-type mapping, healing sequence, developmental clustering) remains Speculative regardless of the PDE outcome.

### 10.4 Test Results (2026-07-31)

**Script**: `two-fluid/run_trauma_wake_lock.py`. Solver: `ExpandingTwoFluid3DGPU` with `qi_gate=True`, `gate_model='five'` (the 5-channel gate with adiabatic redistribution), $\chi = 0$, $c_s^2 = 0$, quiet $\varphi$-equilibrium background. Perturbation: a Yang deficit of peak $-0.8$ at the box center, realized either as a pinned cosine pattern (standing) or a Gaussian packet of the same amplitude (radiating), plus a small-noise random run as a clean counterfactual. Site diagnostics measured in a periodic ball of radius 6 cells around the center: mean $|\varepsilon|$, 5-channel $q$, per-channel phase histogram, $\sigma_r$.

| Run | $|\varepsilon|$ at site (t=0 → 10) | Retained | q-site vs q-global at t=10 | Site phase at t=10 |
|-----|:---:|:---:|:---:|:---:|
| **standing** (cos³ pattern) | 0.660 → 0.279 | 42% | 0.692 vs 0.706 | 100% Fire (displaced) |
| **radiating** (Gaussian) | 0.422 → 0.186 | 44% | 0.702 vs 0.708 | 80% Fire |
| **random** (noise, counterfactual) | 0.076 → 0.067 |—| 0.707 vs 0.707 | 98% Wood (baseline) |

**Null result on the pinning contrast**: the standing pattern decays at essentially the same rate as the radiating packet (42% vs 44% retained over $t = 10$ at $\lambda = 0.1$). Both decay on the conversion timescale $\sim 1/\lambda$; the standing structure has no extra persistence. The predicted lock signature (standing keeps $\varepsilon$ elevated and $q$ depressed while radiating relaxes) did not appear. A pure standing mode in this periodic-box solver is not a frozen wake—it is just a mode, and it decays like any other perturbation.

**Positive result—the EMDR-analog drive**: in the short-run variant ($\lambda = 0.05$, $t = 2$) where the standing pattern was still fully displaced, adding a $\varphi$-phased oscillation at the site (period $\varphi \cdot P_0$, $P_0 = 0.041$ the measured natural oscillation period of the site) drove the site back to baseline: $|\varepsilon|$ fell to 65% retained (vs 91% undriven), $q_{\text{site}}$ rose from 0.648 to 0.698 (global 0.701), and the phase histogram returned to 100% Wood. The oscillatory drive accelerates relaxation and unfreezes the displaced gate—the first numerical support for the "bilateral stimulation as decay drive" hypothesis.

**φ-specificity follow-up** (`two-fluid/run_trauma_drive_compare.py`, same protocol): the relaxation is **not generic stirring**—it is frequency-specific. A drive at the same amplitude but a non-$\varphi$ period ($T = e \cdot P_0$, $e \approx 2.718$) does the opposite: $|\varepsilon|$ at the site *grows* to 188% of its initial value, the $q$-gap widens (0.053, above the undriven lock's 0.046), and the phase displacement persists (74% kept). The $\varphi$-phased drive closes the gap (0.003) and returns the phase to baseline; the off-resonance drive pumps the locked site. The EMDR-analog claim is supported in its strong form: the decay drive is $\varphi$-structured, not any oscillation.

**Gate-sign finding**: the solver's conversion is $\text{conv} = -\lambda(1-q)\varepsilon$; the site's depressed $q$ therefore implies *elevated* openness $(1-q)$, mildly *increasing* local conversion. The earlier claim that "depressed $q$ closes the gate" (§2.3) had the sign inverted and is withdrawn.

**Interpretation**: a genuine frozen wake must be a *driven* structure—sustained by reflecting boundaries, ongoing re-stimulation, or another source outside this PDE's scope—rather than an un-driven standing pattern. The locking mechanism, if real, lives in the driving, not in the mode itself. The drive result suggests the *decay* side of the mechanism is sound: an external $\varphi$-phased oscillation can release a displaced gate.

---

## 11. Predictions

### T1: Channel-Specific Emotional Range Deficits

**Claim:** Post-trauma emotional deficits are not global—they are specific to the channels complementary to the locked one. A Water-locked (fear) survivor shows suppressed anger, joy, grief, and trust responses; a Wood-locked (rage) survivor shows suppressed joy, grief, fear, and trust—but both retain normal access to *their* locked channel, which is hyper-available.

**Test:** Multi-dimensional affect ratings (the P3 instrument of the emotions document) in trauma-exposed populations, compared against the $\varphi^{-i}$ baseline hierarchy (Prediction P2 of the emotions document). The trauma profile should show one channel above the baseline prediction and four below, rather than a uniform shift.

### T2: The Healing Sequence Follows the $R$-Matrix Rows

**Claim:** As a specific trauma resolves, the returning emotions follow the $R$-row order of the locked channel. Anger precedes joy after fear-work (row 5: Wood 44.7% first); relief precedes anger after rage-work (row 1: Fire 44.7% first).

**Test:** Longitudinal multi-dimensional affect ratings across trauma therapy. The sequence of first-surfacing emotions should match the row ordering, not a uniform or random order.

### T3: Trigger Specificity Is Phase Matching

**Claim:** A trigger re-activates a trauma when its pentagon phase matches the original event's phase (emotions doc §4.1). Triggers are phase-matched, not merely associated.

**Test:** Controlled trigger exposure with phase-content analysis of the stimuli (e.g., threat-phase vs. violation-phase cues) while measuring the re-activation of the locked channel's physiological signature. Mismatched-phase cues should produce weaker activation than matched-phase cues of equal intensity.

### T4: $q$ Depression at the Trauma Site

**Claim:** The coherence $q$ at the trauma's somatic locus is depressed relative to the field's global value, and drops further under trigger exposure (dissociation).

**Test:** Physiological proxies for $q$ (sympathetic-parasympathetic phase synchrony, inter-hemispheric coherence—emotions doc P5) measured at rest and under trigger exposure, with somatic localization via the chakra proxies (skin conductance, HRV coherence—predictions C4/C5 of the chakra document).

### T5: $\sigma_r$ Brittleness

**Claim:** Trauma presents as *brittle* dispersion—high variance with poor recovery—rather than the steady high dispersion of anxiety.

**Test:** Time series of $\sigma_r$ proxies (HRV variance, skin conductance variance) with perturbation-recovery protocols. Trauma should show slow recovery after perturbation; anxiety should show sustained elevation without the spike-recovery asymmetry.

### T6: Developmental Trauma Clusters by $\varphi$-Age AND Channel

**Claim:** The Fibonacci-age clustering (`cassi-psychology.md` §15) carries channel content: early trauma (ages 2–5) presents as fear/rage with somatic location; mid trauma (8–13) as trust/grief with relational location; late trauma (21+) as meaning/identity with expressive location.

**Test:** Retrospective developmental trauma inventories with multi-dimensional symptom profiles. The age-of-trauma distribution should show Fibonacci clustering, and the symptom profile should shift with age cluster as predicted.

### T7: Standing Patterns vs. Driven Structures (tested, null with a positive)

**Claim (tested 2026-07-31, `two-fluid/run_trauma_wake_lock.py`):** an un-driven standing pattern does **not** pin the gate—it decays at the same conversion-driven rate as a radiating packet (42% vs 44% retained over $t=10$ at $\lambda=0.1$; q-gap closes in both). **But** an oscillatory drive at the site does accelerate relaxation (short-run variant: $|\varepsilon|$ 65% retained vs 91% undriven; $q_{\text{site}}$ returns to global; phase histogram returns to baseline). The frozen wake, if real, must be a *driven* structure; the decay side of the mechanism (a $\varphi$-phased oscillation releases a displaced gate) has its first numerical support.

---

## 12. Epistemic Boundaries

### Derived (from $\varphi$ and cascade dynamics)

- The $R$-matrix redistribution fractions and their row orderings (`consciousness/emotions-as-gate-configurations.md` §4.2)
- The gateway emotion theorem (§5.2): Wood receives the largest share in every row except row 1—arithmetic of the baseline hierarchy
- Cascade suppression and the rung-depth structure of reachability (`foundations/cascade-suppression-formula.md`)
- The chakra rung positions and channel affinities (`consciousness/chakras-as-cascade-bubbles.md`, `consciousness/emotions-as-gate-configurations.md` §3.4)

### Tested (2026-07-31, PDE runs in §10.4)

- The 5-channel gate's conversion sign: $\text{conv} \propto -(1-q)\varepsilon$—low $q$ means the gate is *open*, conversion active (falsified the earlier "depressed $q$ closes the gate" claim, §2.3)
- Standing vs radiating contrast: **null**—no extra persistence for the standing pattern in the periodic-box solver
- EMDR-analog drive: **positive and φ-specific**—a $\varphi$-phased oscillation at the site accelerates relaxation and returns the gate to baseline, while the same-amplitude non-$\varphi$ drive pumps the site instead (§10.4, `run_trauma_drive_compare.py`)

### Hypothesized (derivation supplied, partially tested)

- The lock mechanism as *driven* structure: a frozen wake sustained by a genuine cavity/reflection or ongoing re-stimulation would pin a channel and depress $q$ at its site (§2, open driver question in §13.7)
- The three-layer healing model: rung-reach (spatial), phase-change (semantic), closure (dynamical) (§5.1)
- The identification of fight/flight/freeze with channel states (§3)
- The trauma-vs-depression-vs-anxiety distinction by locus (§9)

### Speculative (no current test design)

- The channel-to-trauma-type mapping (which trauma locks which channel—the phase is set by the person's interpretation, which is not yet modeled)
- The clinical healing sequence prediction (T2) as applied to real therapy outcomes
- The Fibonacci-age × channel developmental structure (T6)
- The claim that EMDR's bilateral stimulation is a $\varphi$-structured decay drive—**supported at the PDE level**: the analog drive at period $\varphi \cdot P_0$ relaxes the locked site while the same-amplitude drive at a non-$\varphi$ period pumps it (§10.4). The clinical mapping remains untested.

### Not Claimed

- That trauma is *only* a frozen gate configuration (it is a phenomenon with neurobiological, psychological, and social levels of description; the Cassi layer describes the field dynamics beneath them)
- That the five channels exhaust trauma's presentation (dissociation, for example, is the *absence* of a completed channel configuration—§3.3—which the manifold represents but does not exhaustively classify)
- That this framework prescribes or validates any specific therapy (it generates hypotheses about mechanism; clinical efficacy is an empirical matter)
- That the Cassi model replaces clinical understanding of attachment, narrative, or systemic factors—those operate at the semantic and social layers, which the framework engages only through the phase-change channel (§5.1)

---

## 13. Open Questions

1. **What sets the processing-capacity threshold?** The frozen wake forms when the perturbation "exceeds the field's processing capacity." What determines that capacity—the local $q$ before the event, the cascade rung, the conversion rate $\lambda$? If capacity is state-dependent, the framework predicts *pre-trauma coherence modulates trauma susceptibility*—a measurable claim.

2. **Can the phase of an event be modeled?** The channel that locks is set by the event's pentagon phase as received (§4.1), but the phase includes the person's interpretation. Is the phase a property of the stimulus, the person, or the resonance between them?

3. **How do locks interact when adjacent?** Complex trauma with adjacent locked channels (Water + Wood) doubly starves the remaining three. Does the redistribution hierarchy predict the *order* in which multiple locks must release—e.g., must the higher-$b$ channel release first?

4. **Is suppression's partial lock quantitatively distinguishable?** Suppression (§8) mimics trauma at lower amplitude. Is there a measurable boundary—a $\Delta b$ threshold below which the lock is reversible by self-modeling alone?

5. **What is the relationship between the freeze lock and the sub-pinch excursion?** Freeze (§3.3) is described as an incomplete lock with $q$ collapse. Is freeze the same state as the psychedelic sub-pinch excursion (`consciousness/consciousness-from-phi.md` §2.3) with a different boundary condition—transient in one case, pinned in the other?

6. **Does the wake's rung shift over time?** Memory consolidation moves wake waves to deeper rungs (`cassi-psychology.md` §9). Do frozen wakes also deepen—and does that explain why old trauma becomes more somatic and less verbal, and harder to reach?

7. **What sustains a frozen wake?** The PDE test (§10.4) showed that an un-driven standing pattern decays like any other perturbation. A genuine frozen wake therefore requires a *driver*: a reflecting cavity, ongoing re-stimulation, a self-organizing source, or a mechanism outside the tested PDE (e.g., the $G_{\text{eff}}$ self-sealing of §2.3, which the base solver does not activate). Identifying the driver is now the central open question of the trauma mechanism.

---

## 14. References

- `cassi-psychology.md`—frozen-wake trauma model (§16), depression/anxiety/psychosis (§17), empathy resonance (§20), cascade suppression (§5)
- `consciousness/emotions-as-gate-configurations.md`—emotional manifold, 5-channel gate, $R$-matrix, phase-to-channel mapping, chakra affinities
- `consciousness/consciousness-from-phi.md`—wake waves, pinch point, $\sigma_r$ altered states, two-bubble resonance
- `consciousness/chakras-as-cascade-bubbles.md`—13 chakra nodes, rung positions, $G_{\text{eff}}$ self-reinforcement
- `foundations/cascade-suppression-formula.md`—$\varphi^{-N}$ attenuation over $N$ rungs
- `foundations/wa-pentagon-gate.md`—5-channel gate, adiabatic redistribution, Wu Xing control-release
- `foundations/wu-xing-derivation.md`—$w = 5$ derivation
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational
- `two-fluid/cassi_two_fluid_3d_gpu.py`—the PDE solver used in the §10 test
- `two-fluid/run_trauma_wake_lock.py`—the test script (standing/radiating/random/drive runs, 2026-07-31)
- `two-fluid/run_trauma_drive_compare.py`—the φ-specificity follow-up (φ·P₀ vs e·P₀ drive, 2026-07-31)
- `cassi-physics.md`—physics guide, epistemic tiers
