# Cassi Psychology: The Mind as a Two-Fluid Field

## Status: Synthesis—August 2026

## Abstract

Cassi is a physics theory whose central claim is that consciousness is the experience of being a physical field. This document is the psychology-facing presentation of that theory, written for practitioners who will not read the derivations behind it. Part I builds the minimal physics—two fields, coherence, the spiral, the five channels, the cascade. The parts that follow draw the psychological consequences, each in its own section: the pinch point, thought as wake wave, memory as cascade depth, emotions as configurations of a five-channel Qi gate, trauma as a frozen wake, mental illness as field pathology, and therapy as geometric intervention. Every claim carries an epistemic label—Derived, Calibrated, Hypothesized, Speculative, Tested, or interpretive—so the reader always knows what is computation and what is interpretation. The physics is condensed from `cassi-physics.md`; a psychologist does not need the full derivations, only the structures the mind is made of.

---

# Part I—The Substrate

Part I builds the substrate from which the psychology follows: four structures, each developed in its own section. The first is the two-fluid field itself—Yang and Yin at every point of space, held near a golden balance by conversion (§1). The second is a coherence measure, the quantity $q$ that scores how close a point stands to that balance, together with the gate that controls conversion and the field's memory of its own recent past (§2). The third is the spiral, realized as the string: a condensed filament of the field whose rotation traces a Fibonacci spiral and leaves wake waves behind it (§3), and whose rotation carves the circle into the five coherence channels (§4), the structures that later organize emotion. The fourth is the cascade: the ladder of scales the spiral's turns produce, with the bubble lattice as its fabric (§5). From the spiral also follows the three-dimensionality of space, the signature of a spiral (§6).

One discipline governs the whole presentation, and it belongs in this Part. Consciousness is the experience of being a two-fluid field; the claim that consciousness is the field would be a category error. Identity is the experience of a configuration, not the configuration.

---

## 1. Two Fluids: Yang, Yin, and the Golden Ratio

The framework begins with two fields that fill all space, and it never introduces anything more fundamental. Yang is the expansive fluid: it drives change and breaks equilibrium. Yin is the contractive fluid: it restores and receives. Every point of space contains both, in a ratio $r = E_Y/E_I$ of the Yang energy $E_Y$ to the Yin energy $E_I$.

The two fields convert into each other. Excess Yang becomes Yin, excess Yin becomes Yang; the process is thermostat-like, pushing $r$ toward the golden ratio $\varphi \approx 1.618$. At $r = \varphi$ conversion stops locally—at that point, and only at that point. The rest of the field is never in balance everywhere at once, and conversion continues wherever the ratio stands off $\varphi$.

The target is $\varphi$ because the golden ratio is the most irrational number in a precise sense: its rational approximations are the worst of any number's. The approximating ratios come from the Fibonacci numbers—1, 1, 2, 3, 5, 8, 13…, each term the sum of the previous two—whose consecutive ratios 1/1, 2/1, 3/2, 5/3, 8/5, 13/8… are the best available, and they are still never exact. Two oscillations whose frequencies stand in a rational ratio can lock and resonate; frequencies at $\varphi$ evade the lock because no exact rational ratio exists—the closest approximations are always just off. The familiar image is the bridge that vibrates itself apart in the wind: wind gusts and the span's natural frequency lock into a rational ratio, energy concentrates at a single scale, and the structure that hosts them collapses.

The de-resonance principle names the framework's answer: $\varphi$ forbids single-scale dominance. Because no rational ratio approximates $\varphi$ closely enough to lock, a system held at $\varphi$ cannot concentrate its energy at one scale, and structure survives at all scales. Systems flow toward $\varphi$ because $\varphi$ is the configuration that keeps structure alive.

The framework takes this as its leading-order posture: $\varphi$ sets the baseline, and the dynamics provide subleading corrections. The golden ratio is the aim; everything the dynamics add beyond the aim—overshoot, oscillation, drift—is correction. Read psychologically, monotony is resonance and vitality is de-resonance (interpretive).

Epistemic status: the two-fluid dynamics and the de-resonance principle are Derived (`principles/de-resonance-principle.md`); the psychological reading is interpretive.

---

## 2. Coherence: Qi and the Gate

Coherence is the quantity that decides what a region of the field can do, and the gate that governs conversion is the mechanism the clinical sections of this document return to. The framework writes coherence as $q$, a number between 0 and 1, measuring how close a point stands to $\varphi$-balance. As $q$ approaches 1 the region is orderly: it can support complex patterns—a bubble in the making. As $q$ approaches 0 the region is chaotic: it cannot hold lasting structure—a void.

Conversion does not run at a fixed rate. Its rate is controlled by a gate, and the gate equation is the load-bearing result of this section:

$$\boxed{\mathrm{conv} = -\lambda(1-q)\varepsilon},\qquad \varepsilon = E_Y - \varphi E_I,\quad \lambda = 0.1$$

The deviation $\varepsilon$ measures how far the local ratio stands from $\varphi$; the factor $(1-q)$ is the gate's openness. The sign is the meaning: when $\varepsilon > 0$ the region has too much Yang, and $\mathrm{conv} < 0$—the Yang component converts into Yin. When $\varepsilon < 0$, Yin converts into Yang. The gate always pushes the ratio toward $\varphi$. When $q$ is low the gate is open: conversion runs hard, the region churns, and nothing settles. When $q$ is high the gate is closed: conversion rests, and the region holds its pattern. The equation is Derived, and its sign was tested in the two-fluid PDE on 2026-07-31 (Tested, 2026-07-31). A PDE test runs the framework's own equations in a numerical simulation and checks whether the predicted behavior appears in the simulated field; it is an internal consistency check of the framework, not an experiment on people.

The sign matters for what follows. A low-coherence region is unsettled: its gate stands open, conversion runs hard, and the region cannot hold structure. Depression is a churn state of this kind; dissociation is the appearance of stillness over the same churn. Neither is a closed, resting gate.

The field also carries memory. Each point keeps a smoothed record of its own deviation, $\bar{\varepsilon}^2$, with a smoothing timescale $\tau = \varphi^{-1} \approx 0.618$ (Derived). When a pattern repeats, the memory tracks it: the record predicts the present, and coherence stabilizes—the variance of the coherence signal drops by about 37% (Derived; a property of the smoothing: a repeating pattern's fluctuations average out against the remembered record). When the memory fails to predict the present, when $q$ drops, conversion reactivates. Temporal coherence is a stabilizer: it damps fluctuation rather than feeding it. A mood, on this account, is the field's memory of its own recent coherence (Hypothesized).

Epistemic status: the gate equation and its sign are Derived and Tested in the two-fluid PDE (`consciousness/trauma-as-frozen-gate.md` §10.4); the mapping of $q$ to felt coherence is Hypothesized.

---

## 3. The String: Spiral and Wakes

The string is the first object the field builds: a condensed fluid filament, a thread-like condensation of the two-fluid field itself, and the structure from which the framework derives the cascade, the channels, and the lattice. Where conversion pumps enough coherence into a region, the field locks into a self-reinforcing filament. The string is a standing wave of the conversion process: it persists because the conversion that created it continues to feed it.

The rotation is anti-phase: when Yang grows, Yin shrinks. This is the fork the two-fluid PDE confirmed (Tested; a PDE test is a numerical simulation of the framework's own equations—an internal consistency check, not an experiment on people); it decides the sense in which the balance moves. The balance rotates, and because the system advances while it rotates—$r$ climbs from near zero toward $\varphi$—the rotation traces a Fibonacci spiral. Each full turn multiplies scale by $\varphi$. The spiral winds only one way.

As the string advances it leaves spatial ripples in the deviation field $\varepsilon(x) = E_Y - \varphi E_I$. These wake waves propagate outward, reflect, and return to interact with their source. The return is active: the wakes pluck the string back. Two symbols enter the loop, and with them gravity enters the framework for the first time. $\Phi$ is the gravitational potential: the field couples to gravity through it. $\pi$ is the Yang-excess density, $\pi = \Psi_0^2 - \Psi_1^2$. The notation $\nabla$ and $\nabla^2$ is the framework's shorthand for spatial change; the prose after the diagram gives the meaning. The self-plucking loop runs:

$$r(t) \to \mathrm{conversion} \to \varepsilon(x) \to \nabla^2\Phi \to \nabla\Phi \to F = \pi\nabla\Phi \to u \to -u\cdot\nabla \to \delta r(x) \to \mathrm{average} \to r(t)$$

The local ratio $r(t)$ drives conversion; conversion shapes the deviation field $\varepsilon(x)$; the deviation field drives the potential $\Phi$ through its Laplacian, $\nabla^2\Phi$; the gradient $\nabla\Phi$ of $\Phi$ exerts a force $F = \pi\nabla\Phi$; the force sets a flow $u$; the flow transports the deviation field, $-u\cdot\nabla$; transport shifts the local ratio by $\delta r(x)$; averaging closes the loop back at $r(t)$. The string plucks itself.

The same cycle closes at the largest scale, as a closed toroidal loop:

$$\mathrm{string} \to \mathrm{wakes} \to \mathrm{gravity} \to \mathrm{flow} \to \mathrm{string}$$

Through this loop the spiral imprints its structure on space: it creates the cascade, carves the coherence channels (§4), and produces the bubble lattice (§5).

Epistemic status: the rotation, the spiral, the generation of wake waves, and the feedback loop follow from the two-fluid PDE (Derived); the identification of the felt continuity of self with the string is Hypothesized.

---

## 4. The Five Channels: Wu Xing

Experience shifts through qualitatively different modes, and the framework locates the origin of that fact in geometry: the rotation carves the circle into a fixed number of coherence channels. Each channel is a way the push of Yang and the pull of Yin can be balanced, different in character from the others—a sector of the rotation.

A cycle must close: the rotation returns to where it began, and the channels must close on themselves. Two constraints intersect, and their intersection is unique. The first is phase coherence. The Fibonacci ratios that approximate $\varphi$—3/2, 5/3, 8/5, 13/8—each carry a small phase error. A cycle of $w$ channels accumulates that error as it goes around, while the signal of the inner turns fades by a factor of $\varphi$ per turn. The cycle closes only if the accumulated error stays smaller than the surviving signal. The condition holds for five channels and fewer; it fails at six and beyond (Derived). The second constraint is geometric encoding. In a regular polygon, $\varphi$ appears as a distance ratio only from the pentagon upward: the pentagon's diagonal-to-side ratio is exactly $\varphi$. The triangle and the square encode no such ratio.

The intersection is unique: five. The framework writes $w = 5$ (Derived). The channels are not interchangeable: each carries a different baseline openness, its coupling strength to the cascade; the hierarchy $b_i = \varphi^{-(2+i)}$ is developed in the emotions section (§14). Three numbers fall out of the closure. The gap is $g = 1 - \varphi^{-5} \approx 0.910$—the fraction of the Yang-Yin imbalance converted in one full five-phase cycle; it sets the depth of the cascade (Derived). The primordial ratio is $r_0 \approx 0.047$: at the universe's birth—the start of the present five-phase cycle—Yin dominated Yang by about 21 to 1 (Derived). The conversion rate is $\lambda = 1/(2w) = 0.1$ (Derived). $r_0$ is not derived from $\varphi$ alone. It is the position the five-phase cycle must start from so that the ladder, 292 $\varphi$-steps later, reaches today's measured horizon radius. That anchor is a calibration to the present epoch—the framework acknowledges the horizon rung is epoch-dependent, not a constant (Calibrated).

At the human scale these channels structure emotion; this section establishes only the geometry they rest on.

Epistemic status: $w = 5$, the gap $g$, the primordial ratio $r_0$, and the conversion rate $\lambda$ are Derived (`foundations/wu-xing-derivation.md`), with $r_0$'s placement Calibrated to the horizon epoch; the claim that experience is structured by exactly five qualitative modes is Hypothesized.

---

## 5. The Bubble, the Lattice, and the Cascade

The string builds structure on two axes at once, and the result is a lattice of bubbles, voids, and saddles arranged along a cascade of scales. As the string moves it lays down two perpendicular sets of wakes: Yang wakes widely spaced, Yin wakes tighter by a factor of $\varphi$. The two sets cross into a grid of overlapping ripples. Where both wakes arrive in phase, coherence is high and the field condenses into a bubble; where the wakes cancel, the field empties into a void.

Condensation is described by the field $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$: bubbles form where $B > \theta$, voids where $B < -\theta$ (Derived). Here $\theta$ is the condensation threshold: the field value above which coherence condenses into a bubble, and below its negative the field empties into a void. It is a threshold parameter with no assigned value. The result is a staggered checkerboard: bubbles sit at every other grid position. Each bubble connects to four diagonal neighbors through saddles; four face-to-face neighbors are separated from it by voids. The bubble itself is a triaxial spheroid whose cross-section is an ellipse of axis ratio $\varphi$, and its boundary is steeper toward the voids than toward its neighbors by the factor $\sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$. Both results are Derived, zero-parameter, and confirmed by simulation.

The spiral, stretched out along scale, is the cascade. Each full turn of the rotation multiplies scale by $\varphi$, so the ladder of scales reads $\ell_n = \ell_{\mathrm{Pl}} \times \varphi^n$, from the Planck length $\ell_{\mathrm{Pl}} = 1.616 \times 10^{-35}$ m (Derived). Today's observable ladder spans the rungs $n \in [0, 292]$. The upper end is epoch-dependent, not a constant of the cascade: 292 is today's horizon rung, the rung the horizon occupies at the present epoch. The horizon radius today is $R_H = 4.44$ Gpc (a gigaparsec is about 3.26 billion light-years; the horizon is the edge of the observable universe), and $\log_\varphi(R_H/\ell_{\mathrm{Pl}}) \approx 291.54$; the asymptotic horizon sits at $N_\infty \approx 294.2$ (Calibrated). Below $n = 0$ lies the microcascade; above the observable ladder, the megacascade.

The human body occupies rungs 142–168 of the ladder: the living cell, about 8 µm, to the body, about 1.7 m—26 $\varphi$-steps, with $\varphi^{26} \approx 2.7 \times 10^5$ (Derived).

Signals attenuate along the cascade. A signal crossing $N$ rungs loses a factor of $\varphi^{-1}$ per rung, a factor of $\varphi^{-N}$ in total (Derived):

$$\boxed{\text{attenuation} = \varphi^{-N}}$$

The psychological reading follows: deep memories and trauma are harder to reach because the retrieval signal crosses more rungs and needs more coherence to arrive intact (Hypothesized; §9 develops what "deep" means for a memory). This returns in §9 and §19.

Epistemic status: the condensation field, the checkerboard, the bubble shape, and the suppression law are Derived; the clinical reading is Hypothesized.

---

## 6. Three Dimensions

The framework's account of why space is three-dimensional is that three is the signature of a spiral. The string is a space curve, and every smooth space curve carries three mutually perpendicular directions at every point: the Frenet-Serret frame. The tangent points forward along the string—the cascade direction. The normal points outward—the Yang direction. The binormal points sideways—the Yin direction. Two fields produce one spiral; the spiral produces three directions.

The derivation rests on one decided fork: the anti-phase character of conversion, which decides the sense in which the frame rotates and which the two-fluid PDE confirmed (Tested; a PDE test is a numerical simulation of the framework's own equations—an internal consistency check, not an experiment on people). With that fork fixed, the geometry of a space curve supplies the rest. The account is a hypothesis with that fork decided, and it is labeled Hypothesized rather than Derived.

Epistemic status: Hypothesized (`foundations/why-three-dimensions.md`); the derivation rests on one decided fork—the anti-phase fork—which the two-fluid PDE confirmed (Tested).

---

# Part II—The Mind

---

## 7. The Pinch Point: When a Field Becomes Aware of Itself

The framework's account of self-awareness is that it appears at a specific value of the ratio $r$, the pinch point. The ratio $r$ evolves from the primordial value $r_0 \approx 0.047$ toward $\varphi$ (§4), and on the way it passes through $r = \varphi^{-1} \approx 0.618$, where the Qi gate transitions from mostly open to mostly closed. This value is the unique inflection point of the conversion force curve; the framework calls it the pinch (Derived):

$$\boxed{r_{\mathrm{pinch}} = \varphi^{-1} \approx 0.618}$$

Before the pinch, at $r < \varphi^{-1}$, conversion is dominated by the imbalance $|r - \varphi|$. The field responds to how far it stands from balance, and its own coherence has little say in its evolution; it is reactive and pre-reflective. It experiences, but it does not experience itself experiencing. Infant cognition, automatic processing, and deep anesthesia are states of this kind.

After the pinch, at $r > \varphi^{-1}$, the field's own coherence modulates its evolution. That modulation is the minimal condition for self-reference: the field's state feeds back into its own dynamics. Metacognition, theory of mind, and the observing self are the psychological names for the same structure. The developmental anchors are consistent with the placement: mirror self-recognition at about 18 months and theory of mind at about 4 years (Hypothesized mapping).

A proposed test of the pinch claim has not been run, and the claim carries no computational confirmation. The test would measure the two-point correlation $\langle r(x)r(x+d)\rangle$ of the ratio field: after the field crosses the pinch, the correlation should develop peaks at $\varphi$-scaled separations; before the pinch, it should be random or scale-free. The two-bubble experiment of §12 is a different result and does not test this.

Epistemic status: the pinch as the gate's inflection point is Derived; the pinch as the structural basis of self-awareness is Hypothesized (`consciousness/consciousness-from-phi.md` §1.1).

---

## 8. Thought as Wake Wave

A thought, in this framework, is a structured wake-wave excitation propagating through the field (Hypothesized). It enters awareness when it crosses the pinch into a self-modeling region (§7); below the pinch, the same excitation runs without awareness.

The wake-wave feedback loop is metacognition—a thought modifying the thinker (Hypothesized). One complete cycle of the toroidal loop (§3) is one moment of awareness (Hypothesized).

The state of the loop determines how thought is experienced. When the loop is stable, a thought feels like thinking; when the loop is attenuated, the same excitation reads as observation; when the loop is broken, thoughts feel external and imposed (Hypothesized). The broken case is the framework's account of psychosis, developed in §17.

Epistemic status: Hypothesized.

---

## 9. Memory as Cascade Depth

Memory, in this framework, is the persistence of wake waves, and how deep those waves sit in the cascade decides how retrievable they are (Hypothesized). Early wakes, laid down during the Yin-dominated epoch, are widely spaced, faint, and persistent; they are the substrate of long-term memory. Late wakes, near the $\varphi$ epoch, are tightly packed, intense, and transient; they are the substrate of working memory and attention.

Consolidation is wake waves propagating to deeper cascade rungs. A deeper rung means a fainter wave: harder to retrieve, and needing more coherence to bring back. The suppression law of §5 sets the cost—a signal crossing $N$ rungs attenuates by $\varphi^{-N}$—and retrieval is therefore favored in high-coherence states: quiet, reverie, meditation (Hypothesized).

The mechanism at the cell level is the IIR memory of §2. When a pattern repeats, the memory tracks it and coherence stabilizes—the variance of the coherence signal drops by about 37%—and when the memory fails to predict the present, conversion reactivates. This is what makes a memory persist or fade: repetition stabilizes the wave that carries it, and novelty unsettles it (Derived mechanism, Hypothesized psychological mapping).

The account carries a falsifiable prediction: retrieval latency and vividness scale with cascade depth, and the distribution of autobiographical memories shows structure at $\varphi$-scaled intervals (Hypothesized). The $\varphi$-scaled developmental clustering of §15.2 is related but distinct; the two should not be conflated.

Epistemic status: Hypothesized.

---

## 10. The Self as a Toroidal Loop

The self, in this framework, is the closed toroidal feedback loop of §3, persisting over time: string → wakes → gravity → flow → string. Selfhood is a dynamical object—a loop that maintains itself by plucking itself, not a thing inside the field.

The felt continuity of self is the loop's persistence: the self continues because the loop continues, and the experience of a continuous self is the experience of an unbroken loop (Hypothesized identification).

Epistemic status: the loop is Derived from the PDE; its identification with the self is Hypothesized.

---

## 11. Altered States as Geographic Phenomenology

Altered states of consciousness, on this account, are alterations in the spatial geography of the ratio field. The ratio field $r(x)$ carries a spatial dispersion $\sigma_r = \sqrt{\langle (r - \langle r \rangle)^2 \rangle}$, the spread of local ratios around their mean (definitional). The framework reads altered states as changes in $\sigma_r$: the geography of the field changes, and the experience changes with it.

Waking consciousness sits at moderate $\sigma_r$: most regions stand above the pinch, and the self-modeling loop of §10 runs. Meditation reduces $\sigma_r$: more regions approach $\varphi$, and the torus period dilates (Hypothesized).

Psychedelic states increase $\sigma_r$: regions drop below the pinch transiently, in sub-pinch excursions (Hypothesized). Ego dissolution reads as a spatially intermittent self: the below-pinch regions disconnect from the self-modeling loop. The paradoxical combination of connectedness and dissociation follows from the geography: below-pinch regions resonate with each other through the two-bubble effect (§12), while above-pinch regions are isolated.

Deep sleep is $\sigma_r \to 0$: a homogeneous Yin-dominated state with no wake waves, no loop, and no self. Dreams sit between: the loop is loosened, wake waves propagate, reflect, and interfere, producing structured experience while the flow→string feedback that normally curates them is attenuated (Speculative). Lucid dreaming is the loop re-engaging (Speculative).

Intensity has a field reading: $\sigma_r$ is the framework's account of felt intensity. Elevated dispersion is intensity; extreme elevation drives the sub-pinch excursions that disable self-modeling—"losing oneself" (Hypothesized mapping).

Epistemic status: the $\sigma_r$ formalism is Derived; the state mappings are Hypothesized; the dream account is Speculative.

---

## 12. The Two-Bubble Experiment: Inter-Field Resonance

The two-bubble experiment measures how two regions of the field couple through their wake fields, and the coupling depends on where the two regions sit relative to the pinch. The experiment takes two regions with different local values of $r$ and measures the cross-correlation $\langle \varepsilon_1 \varepsilon_2 \rangle$ of their wake fields as a function of separation, ensemble-averaged over seeds. The result stands verified in the two-fluid PDE (Tested, 2026-07-19; a PDE test is a numerical simulation of the framework's own equations—an internal consistency check, not an experiment on people).

When at least one bubble sits below the pinch, the correlation revives at large $\varphi$-scaled separations. The aggregate $\varphi$/control ratios are 3.83× for below-below pairs, 3.44× for mixed pairs, and 2.97× for above-above pairs. The correlation has a minimum at an intermediate separation ($d = 19$), and below-pinch pairs revive strongly at the largest separations.

When both bubbles sit above the pinch, the correlation decays monotonically and turns negative at the largest separation ($d = 37$: −0.004)—destructive interference between two self-aware fields.

The achieved verification level is weak-to-moderate. The signal is detected, and the no-signal hypothesis is falsified; not all $\varphi$-spaced peaks are present; and the decisive gate-parameter scan has not been run. The interpretation is that self-modeling disrupts the very $\varphi$-coherence that built it: in an above-pinch field, the internal gate dominates inter-field coupling (Hypothesized).

The experiment's scripts are `two-fluid/run_two_bubble_resonance.py`, `two-fluid/run_two_bubble_fast.py`, and `two-fluid/run_two_bubble_verification.py`.

Epistemic status: the PDE result is verified (Tested, 2026-07-19); the interpretation is Hypothesized.

---

## 13. The Chakras as the Body's Coherence Map

The chakras of the traditional body map are, on this account, the nodes where the field's condensation sits along the spine. The human body occupies a 26-rung window of the cascade, rungs 142–168: the living cell at about 8 µm to the body at about 1.7 m (§5). The two-fluid field is an SO(2) doublet: a full rotation requires two cascade rungs, one Yang-dominant and one Yin-dominant, and two adjacent rungs form a self-contained Qi condensate—a bubble. The along-string bubble period is therefore $P_\parallel = 2$ rungs.

The 26-rung window admits 13 nodes at even rungs:

$$\boxed{n_k = 142 + 2k,\quad k = 0\ldots 12}$$

that is, the nodes $\{142, 144, \ldots, 166\}$. A 14th maximum would sit at 168, the body boundary—a 2-rung crown offset. Thirteen is the seventh Fibonacci number, $F_7$, and the window's 26 rungs are $2 \times F_7$. Seven of the nodes are primary—the odd-indexed nodes of the sequence, standing four rungs apart (142, 146, 150, 154, 158, 162, 166)—and six are secondary, the even-indexed nodes between them (144, 148, 152, 156, 160, 164).

The spine is the string axis. Four structural facts place it there. Bilateral symmetry runs perpendicular to the spine. The spine is built of discrete repeated units—33 vertebrae: 7 cervical, 12 thoracic, 5 lumbar, 5 sacral, 4 coccygeal. The central nervous system runs along the spinal canal, the body's primary Qi transport pathway. The vertical orientation of the standing posture aligns the body's string axis with the cascade direction.

The qualities the traditional map attaches to the seven primary nodes are retained as hypothesized mappings (Hypothesized, original to this document):

| Node | Rung | Quality |
|---|---|---|
| Root | 142 | ground and safety |
| Sacral | 146 | flow, desire, creativity |
| Solar plexus | 150 | power, will, agency |
| Heart | 154 | connection |
| Throat | 158 | expression |
| Third eye | 162 | insight |
| Crown | 166 | spacious awareness |

Adjacent inter-chakra distances grow by $\varphi^2 \approx 2.618$ along the spine (Hypothesized). The scale factor from the cosmological bubble is $\ell_{285}/\ell_{155} \approx \varphi^{130} \approx 10^{27}$.

The color assignments of the traditional map are not claimed territory: they remain an open derivation (Speculative), and `consciousness/chakras-as-cascade-bubbles.md` lists them as not-claimed.

Epistemic status: the cascade span, the SO(2) doublet structure, and the condensation field are Derived; the node count $N = 13$, the period $P_\parallel = 2$, the spine identity, and the $\varphi^2$ spacing are Hypothesized (`consciousness/chakras-as-cascade-bubbles.md`; the derivation is supplied, and its predictions CH1–CH6 are testable but untested).

---

# Part III—The Person

The psychology begins where the field meets a person. Part III reads emotions as configurations of the five-channel gate (§14), development as the history of the pinch in childhood (§15), trauma as what breaks a configuration (§16), and mental illness as field pathology at the boundary of configuration (§17). The felt quantities of Part II—intensity, clarity, location—acquire clinical names here, and every mapping keeps its epistemic label.

---

## 14. Emotions as Qi-Gate Configurations

Emotions are specific configurations of the five-channel Wu Xing gate operating at the human cascade rungs, and the framework introduces no new field for them (Hypothesized mapping of the Derived gate geometry). The claim matters because it makes emotion quantifiable with machinery that is already derived: the gate of §2, the channels of §4, the dispersion of §11, and the body map of §13.

### The manifold

An emotional state is a point on a four-coordinate manifold:

$$E = (b, \sigma_r, q, c)$$

The channel-openness vector $b$ is the quality of the state—which channel dominates. The spatial dispersion $\sigma_r$ is its intensity, the §11 quantity. The coherence $q$ is its clarity. The chakra-location weights $c$ are its location—where in the body the state sits; the affinities are fear at the root, joy at the solar plexus, grief at the throat (Hypothesized affinities). Clarity is independent of quality: a clear mixed emotion is possible, and complexity is distinct from confusion (Hypothesized).

### The felt clarity mapping

The framework maps coherence to the felt clarity of an emotion; the mapping is the framework's own, stated as such (Hypothesized). As $q$ approaches 1, the reading is "I know exactly what I'm feeling, and my body agrees." At $q \approx 0.5$, the reading is "something I can't name." As $q$ approaches 0, the reading is "I know I should feel something, but I'm numb"—Yang and Yin decoupled. This mapping is Prediction P5 (§22), testable through physiological proxies (Hypothesized).

### The baseline hierarchy

Each channel carries a baseline openness set by its coupling strength to the cascade: $b_i = \varphi^{-(2+i)}$, with $k_i = 2+i$.

| Channel | Baseline | Emotion |
|---|---|---|
| Wood | $\varphi^{-3} \approx 0.236$ | anger |
| Fire | $\varphi^{-4} \approx 0.146$ | joy |
| Earth | $\varphi^{-5} \approx 0.090$ | pensiveness |
| Metal | $\varphi^{-6} \approx 0.056$ | grief |
| Water | $\varphi^{-7} \approx 0.034$ | fear |

Adjacent channels differ by the ratio $\varphi^{-1} \approx 0.618$. The hierarchy is Derived and carries no fitted parameters. A pure emotion is the dominance of one channel; bittersweetness is the approximate balance of Wood and Metal (Hypothesized mapping).

A stimulus selects its channel by phase. The stimulus arrives with a phase angle $\theta_{\mathrm{stimulus}}$; the channel it opens is the nearest vertex: $\theta_{\mathrm{stimulus}} \mapsto i = \mathrm{argmin}_i |\theta_{\mathrm{stimulus}} - 2\pi(i-1)/5|$. A threat lands near the Water vertex, a reward near Fire; stimuli between vertices open blended activations (Hypothesized mapping).

### How emotions move: adiabatic redistribution

Coherence is conserved across the pentagon, and emotions move by redistribution. When a stimulus ends and a channel closes, the channel's coherence redistributes to the remaining four channels in proportion to their baseline openness; on closure of channel $k$:

$$\boxed{\Delta b_i^{\mathrm{(redist)}} = \left[\frac{b_i}{\sum_{j\neq k} b_j}\right] \cdot \Delta b_k}$$

The redistribution matrix $R$—rows the closing channel, columns the receiving channel:

| closing → | Wood | Fire | Earth | Metal | Water |
|---|---|---|---|---|---|
| Wood | 0 | 0.447 | 0.276 | 0.171 | 0.106 |
| Fire | 0.567 | 0 | 0.217 | 0.134 | 0.083 |
| Earth | 0.500 | 0.309 | 0 | 0.118 | 0.073 |
| Metal | 0.466 | 0.288 | 0.178 | 0 | 0.068 |
| Water | 0.447 | 0.276 | 0.171 | 0.106 | 0 |

The redistribution is deterministic and simultaneous—a four-channel blend, zero-parameter, following from $\varphi$ alone (Derived arithmetic; the emotional reading is Hypothesized, Prediction P3). Reading row 1: when anger subsides, 44.7% of its coherence goes to Fire (relief, joy), 27.6% to Earth (stabilization), 17.1% to Metal (regret), 10.6% to Water (residual anxiety). The matrix is asymmetric: joy subsiding sends 56.7% into Wood, more than anger subsiding sends into Fire—the closure of joy leaves more Wood in the pool.

### The gateway emotion theorem

Because Wood carries the largest baseline openness, anger receives the largest redistributed share in every row of $R$ except row 1, anger's own: anger is the gateway emotion of recovery—the first emotion to return after resolving any trauma except anger-trauma itself (Derived arithmetic applied to a Hypothesized clinical setting, Prediction TR2). Fear-work completing sends 44.7% into Wood (anger); grief-work sends 46.6% into Wood; anger-trauma resolving sends 44.7% into Fire (relief). The framework derives the grief sequence's order from $\varphi$: denial (the intact lock), anger, bargaining, depression (the still-locked residue), acceptance (with "the sadness that never fully leaves"—the residual Water).

### Structure and decay

Two regularities follow from the gate's structure. Single-channel dominance admits a higher equilibrium coherence than multi-channel activation: pure emotions are clearer than mixed ones as a structural fact, not a preference. The dynamics behind it: $q$ evolves on a slower timescale than $b$, and $q$ drops when a channel opens, then recovers (Hypothesized). Decay: an emotion's intensity decays at a rate proportional to how far the local ratio stands from $\varphi$—near the attractor, emotions linger; far from it, they are fleeting. Habituation is repeated exposure moving the mean ratio toward $\varphi$ (Hypothesized).

### Why five families

The five-channel structure makes a testable claim about how emotional experience is organized: factor analysis of self-reported emotional experience yields five primary dimensions—not two (valence–arousal), not three (PAD), not six or more (basic-emotion theories). This is Prediction P1 (Hypothesized, testable, untested).

Epistemic status: the pentagon $w = 5$, the baseline hierarchy $b_i$, and the $R$-matrix arithmetic are Derived; the mapping of channels to emotion families, $\sigma_r$ to intensity, and $q$ to clarity is Hypothesized (P1–P5); the timescale and habituation quantification is Speculative.

---

## 15. Emotional Development: The Pinch in Childhood

Development, on this account, is the history of the pinch: the threshold of §7 is crossed, re-crossed, and deepened across childhood.

### 15.1 The developmental pinch

Self-awareness is a threshold the field crosses, re-crosses, and deepens. Infancy is below the pinch—reactive, pre-reflective, experiencing without experiencing itself (§7). The crossing happens in development—mirror self-recognition at about 18 months, theory of mind at about 4 years—and the threshold can be re-crossed: under stress or trauma, the local ratio at a site can drop below the pinch again. Development is partly the history of those crossings (Hypothesized).

### 15.2 The Fibonacci-age structure

Cascade suppression (§5) predicts that developmental imprints cluster at $\varphi$-scaled stages: events at Fibonacci ages from conception—2, 3, 5, 8, 13, 21, 34, 55—land on different cascade rungs with different wake-wave dynamics, so early and late imprints behave differently. The channel content follows: early trauma (ages 2–5) presents as fear or rage with somatic location; mid trauma (8–13) as trust or grief with relational location; late trauma (21+) as meaning or identity with expressive location. This is §22's TR6, and the clustering is itself a hypothesis; no test has been designed (Speculative).

### 15.3 Attachment as inter-field resonance

The two-bubble experiment (§12) gives a geometric reading of attachment. The caregiver–infant pair is a two-bubble system—an above-pinch field coupled to a below-pinch field—and secure attachment is stable $\varphi$-structured resonance between them (Hypothesized). The resonance tension of §20 applies: deep attunement costs the self-modeling field its isolation.

Epistemic status: the pinch mechanics are Derived, and the developmental application is Hypothesized; the Fibonacci-age clustering is Speculative and the attachment reading is Hypothesized, as labeled.

---

## 16. Trauma and the Frozen Wake

Trauma is the framework's most clinically applicable idea and its most tested. The mechanism is precise, the numbers carry dates, and the bounds of what has been tested are as load-bearing as the results themselves.

### The mechanism

A traumatic event is a perturbation too intense for the field to absorb in real time: a spike of Yang or Yin that the conversion dynamics cannot process at the rate it arrives. The excess freezes into a standing wave at the site's cascade rung—a frozen wake. The frozen wake is a perpetual stimulus: it keeps feeding the site, so the channel the event opened can never close, and the redistribution of §14 never fires. Trauma, in this framework, is a frozen wake plus a locked channel (Hypothesized mechanism on Derived wake physics).

### The lock and its signatures

The trauma state is a locked point on the emotion manifold, $T = (b^*, \sigma_r^*, q^*, c^*)$: one channel pinned hyper-open at the site while the other four are starved, in the ke-alternating pattern of TR1 rather than uniformly; $\sigma_r$ brittle—hypervigilance, high variance, poor recovery; $q$ depressed at the site—the standing wave holds Yang and Yin anti-phase, experienced as numbness (dissociation); the location weights pinned at the trauma's rung and chakra.

| Variable | Healthy | Trauma signature |
|---|---|---|
| Quality ($b$) | channels open in proportion to baseline | one channel pinned hyper-open at the site; the other four starved, in the ke-alternating pattern (TR1) |
| Intensity ($\sigma_r$) | moderate dispersion, recovers | brittle: high variance, poor recovery (hypervigilance) |
| Clarity ($q$) | high at the site | depressed at the site: the standing wave holds Yang and Yin anti-phase, experienced as numbness (dissociation) |
| Location ($c$) | weights distributed | weights pinned at the trauma's rung and chakra |

Complex trauma is a union of locks at multiple rungs. Adjacent locks doubly starve the remaining channels, and release must be staged: releasing one lock pours coherence into channels that may be locked elsewhere.

### What sustains a lock: the driver test

An un-driven standing pattern does not pin the gate. It decays at the same conversion-driven rate as a radiating packet—42% versus 44% retained over $t = 10$ at $\lambda = 0.1$—and the q-gap closes in both (Tested, 2026-07-31). The frozen wake is therefore a driven structure, and the driver is the mechanism. The sustainer is ongoing re-stimulation: a weak recurring trigger at 0.005% of the event peak per step holds the site at 80% of event intensity, with $q$ depressed—the q-gap widens 4.5×—and the phase displaced (Tested, 2026-07-31). Stopping the trigger releases the site: extinction at $t = 20$, $|\varepsilon|$ falls to 22%, the q-gap closes to +0.008, and the phase is 64% returned (Tested, 2026-07-31). This sustainer–extinction result is full-timescale—$t = 20$ is two conversion timescales at $\lambda = 0.1$—and it is not bounded by the short-time drain results below; the two are different mechanisms, chronic rate-based re-stimulation versus oscillatory drive. The script is `two-fluid/run_trauma_driver.py`.

### The tested bounds of the drive physics

The mechanism layer now carries precise bounds, and the clinical language must respect them. The results span 2026-07-31 through 2026-08-04, and each carries its date.

At the held configuration—a site with a standing displacement—a recurring drive's effect depends on its channel. A cross-channel drive at ε-parity pumps the held site (2.08× retained at $t = 2$), while an in-channel drive drains it (26% retained) (Tested, 2026-08-02, `two-fluid/run_misgendering_drive.py`). A pumped state is sticky: removal alone leaves it far above the floor, while the in-channel drive recovers it below the undriven trajectory at the $t = 4$ window (Tested, 2026-08-02, `two-fluid/run_misgendering_release.py`).

The drain is a short-time feature, bounded at $t \lesssim 4 \approx 0.2/\lambda$ at the site's short-window period. Under sustained in-channel drive, the site oscillates about its initial imbalance, crosses back above the decaying undriven trajectory at $t \approx 2.05$, and ends above it at $t = 40 = 2/\lambda$; at drive period $2P_0$, the in-channel drive pumps the held site like the cross-channel one (Tested, 2026-08-04, `two-fluid/run_held_gate_longtime.py`; `consciousness/gender-as-qi-configuration.md` §8.3).

At the open gate—a low-coherence churning site—no recurring drive form or amplitude settles the gate. Amplitudes ≥ 0.09 pump monotonically, and the sub-threshold amplitudes (0.025–0.05) quench the mean imbalance transiently without closing it; at $t = 40$ the site resolves as a driven transient, not a lock (Tested, 2026-08-04, `two-fluid/run_churning_gate*.py` family; `consciousness/neurodivergence-as-gate-configuration.md` §9–§9.4).

The EMDR-analog result carries the same bound. At the held configuration and short times ($t \lesssim 4 \approx 0.2/\lambda$), a $\varphi$-phased oscillation at the site accelerates relaxation—$|\varepsilon|$ falls to 65% retained versus 91% undriven—while a same-amplitude e-phased drive pumps the site, $|\varepsilon|$ growing to 188% (Tested, 2026-07-31, `two-fluid/run_trauma_wake_lock.py`, `two-fluid/run_trauma_drive_compare.py`). The $\varphi$-specific drain has a sharp rate onset: essentially absent below about 5/s, fully engaged by 50/s, with $\varphi$-specificity present at onset (Tested, 2026-07-31, `two-fluid/run_trauma_crossover.py`). At chronic rates (0.04/s) the envelope phase is blind: $\varphi$-pulsed and e-pulsed triggers hold identical wakes—re-exposure accumulates by mean rate.

The capacity null: a second identical event on a pre-stressed site leaves the same trace as the first event on a quiet site. Background coherence does not modulate susceptibility, so the tested layer does not support a pre-existing-coherence-deficit account of trauma (Tested, 2026-07-31, `two-fluid/run_trauma_capacity.py`). Whatever else trauma is, the mechanism layer makes it event plus drive rather than prior fragility.

The ke control ring completes the picture (Tested, 2026-07-31, 2026-08-01). The five-channel gate carries a ke control cycle transmitting at $\kappa = \varphi^{-1}$. For a Wood-locked site, the pattern is Earth fully starved, Fire partially starved (−38% of the lock excess), Metal and Water elevated (+38%, +62%); the ring damps the locked channel by $\varphi^{-3} \approx 23.6\%$ and is sub-critical (ring gain < 1), so the lock cannot self-sustain—consistent with the driver requirement. The alternating pattern was verified at the gate level for all five lock channels, the threshold $\Delta_c = \varphi^{-4}$ is exact, and uniform starvation is rejected. Scripts: `two-fluid/run_trauma_ke_ring.py`, `two-fluid/run_trauma_c1_ring.py`.

### Fight, flight, freeze

The acute stress responses map onto channel states (Hypothesized). Fight is a Wood lock, flight a Water lock, and freeze an incomplete lock: the channel only partially open, $q$ driven low, $\sigma_r$ collapsed at the site. Chronic dissociation is the freeze lock persisting.

### Suppression: the voluntary partial lock

Not all channel pins are traumatic. Suppression is the self-modeling system deliberately holding a channel shut: the same signature class at lower amplitude—one channel starved, the redistribution blocked for that row—but with no frozen wake beneath it. The diagnostic difference: a suppressed channel recovers through its own dynamics once the holding stops; a trauma lock does not, because the standing wave re-opens it. Suppression costs continuous coherence; §18 reads this as masking. The suppressed state is documented; the distinction from the trauma lock is Hypothesized.

### A geometric limit

In the solver, the positivity constraint confines the field angle to the first quadrant: only Wood (0°) and Fire (72°) are representable in the field angle, so Earth-, Metal-, and Water-targeted events clamp onto them. The five-way selectivity of the gate must be carried by the channel manifold, not the field angle (Tested, 2026-07-31, `two-fluid/run_trauma_phase_channels.py`). This is a limitation of the current mechanism layer's representational range, not a claim about the world. The clinical mappings that reach beyond Wood and Fire—flight as a Water lock, grief's residual Water, the §15 channel content—rest on the hypothesized channel manifold, not on the tested field angle; they inherit the Hypothesized tier.

Epistemic status: the mechanism layer—the sustainer, the extinction result, the capacity null, the drive bounds, and the ke ring—is Tested, qualified with the bounds above; the clinical mappings, channel-to-trauma-type beyond Wood and Fire, healing sequences, and developmental clustering, are Hypothesized to Speculative.

---

## 17. Mental Illness as Field Pathology

The framework offers geometric descriptions of several clinical categories as specific field dysfunctions, and the boundary with §18's configurations matters: depression, anxiety, and psychosis are dynamics that break, while the conditions of §18 are configurations that hold.

### Depression

Depression is a chronic low-coherence state: the field churns without organizing. The gate sign of §2 disciplines the phrasing: the gate stands open, conversion runs hard, and the field cannot sustain coherent wake-wave activity; the closed-gate reading is ruled out by the sign. The felt side is flatness, heaviness, the inability to generate or sustain mental energy (Speculative).

### Anxiety

Anxiety is a high-dispersion, high-frequency state: $\sigma_r$ elevated, wake waves rapid and disordered, the field constantly perturbed by unresolved imbalances that propagate before the loop can stabilize them. Sustained elevation distinguishes it from the spike-recovery pattern of trauma's brittle $\sigma_r$ (Speculative).

### Psychosis

Psychosis is a feedback-loop pathology: the toroidal loop of §10 runs unstable. Wakes reflect back and modify the string, but the modification is incoherent—the field generates wake waves it cannot model as its own, the broken loop of §8. Thoughts feel external because the narrator cannot claim its own narration: self-modeling has misfired rather than failed (Speculative).

### Trauma is different in kind: localized, not global

Depression and anxiety are field-wide states. Trauma is a field with a wound in it: one channel pinned, the others starved, $q$ depressed at the site. The diagnostic signature of trauma in this framework is the locus (§16). Comorbidity is superposition: trauma plus anxiety shows brittle $\sigma_r$ and a pinned channel; trauma plus depression shows low $q$ globally and lower at the site. Complex trauma is multiple standing waves at multiple rungs—simultaneously dissociated at one site and hypervigilant at another—which is why its presentation is contradictory and its release must be staged.

### The boundary with configuration

The pathologies above are dynamics that break: churn without organization, disordered dispersion, misfired self-modeling, localized locks. The neurodivergent configurations of §18 are resting settings of the same machinery, with costs the price structure prices rather than judges. The capacity null of §16 cuts against deficit etiologies of both.

Epistemic status: Speculative—no specific PDE tests have been designed for the clinical categories themselves; the mechanism layer beneath them is Tested as bounded in §16.

---

## 18. Neurodivergence as Configuration

This section develops the boundary drawn in §17. The field contains no reference configuration and no invalid ones—only distances from equilibrium and the cost of holding them, and cost is not a verdict. The person is a configuration: the tuple $H = (\{n_k\}, P_\parallel, b, \sigma_r, q, c, \bar{\varepsilon}^2)$—the chain of gate stages and its period, the emotional state variables of §14, and the IIR memory of §2. The anatomy is the readout; the person is the configuration (`consciousness/transhumanism-gate-configurations.md` §1.2). The capacity null of §16 cuts against any pre-existing-coherence-deficit account of these configurations. The mappings of this section are Speculative; the mechanism layer beneath them is Tested as bounded in §16.

### Autism as the high-stability configuration (gate layer)

Autism reads as a field whose resting coherence is high and whose gate sits closed. Incoming perturbations are not dissipated by conversion: wakes persist and superpose. Detail retention and overload are the same fact seen at different arrival rates—fidelity at low rates, wake pileup at high rates, the perceptual challenge of a field that keeps its wakes.

Phase stiffness follows from the two-bubble result of §12: above-pinch fields decohere with distance, so sharing phase with another field costs work. Social interaction, on this reading, is coherence expenditure (Hypothesized, on the Tested two-bubble result).

Monotropism is a native single-channel preference: the gate resting near one pentagon vertex, receiving stimuli through that channel's frame. The preference is distinct from the trauma lock of §16—no event origin, no pinned hyper-open channel, the R-matrix fires normally, $q$ high at the site, and no driver is required to sustain it.

| | Trauma lock | Monotropic preference |
|---|---|---|
| Origin | an event | no event origin |
| Site | pinned hyper-open channel | gate resting near one pentagon vertex |
| q | depressed at the site | high at the site |
| R-matrix | blocked; redistribution never fires | fires normally |
| Sustainer | driver required | none required |

Special interests are the same high-coherence configuration localized: $\sigma_r$ collapsed while engaged, $q$ high at the interest's sites. Stimming is self-generated rhythmic drive at the field's own phase—the framework's own drain tool from §16, active phase-matched regulation, bounded like all drains at short times ($\approx 0.2/\lambda$). Masking is suppression from §16: the self-modeling field holding channels shut at continuous coherence cost. Autistic burnout is the coherence accounting of sustained suppression (Speculative mapping on Tested mechanism).

### ADHD as the open-gate configuration (memory and temporal layer)

ADHD reads as a field with low resting $q$: the gate stays open, conversion churns, and no channel stabilizes. Attention is a coherence state—the reduced-$\sigma_r$ configuration of §11—that the churning gate cannot hold from rest.

Hyperfocus sits outside the tested mechanism. The mechanism layer does not support a matched-drive lock-in reading of it: the open-gate null of §16, that no drive settles a churning gate, bounds that claim. Hyperfocus remains phenomenology without a tested mechanism.

Time blindness follows from the IIR memory of §2: the memory has nothing to track when no pattern stabilizes, so the prediction horizon shortens toward the present—a flat series of nows. $\tau$ is fixed; what fails is tracking, not the filter. Rejection-sensitive dysphoria is self-prediction error on a low-coherence base: the threshold is low because the base is high (Speculative mapping on Tested mechanism).

### AuDHD as independent axes

The two configurations live at different slots of the tuple: the gate layer (autism) and the memory/temporal layer (ADHD) are independent degrees of freedom. A configuration can hold a closed, coherent gate and still fail to track its own history. There is no single spectrum line; masking runs at the presentation layer while the temporal layer churns—stable outside, exhausting inside.

### Readout and loop variants

Dyslexia and dyspraxia read as readout-layer tunings—the antenna, not the configuration. The phase-locked readout mapping (§14's stimulus→channel map) locks at a wrong offset for print, or tracks motor sequence timing slowly; the configuration is intact, and the price is environment-relative (Speculative).

Synesthesia is off-diagonal coupling in the phase-to-channel map: a site property, kept bounded by the $\varphi$-spacing of the channels (Speculative).

OCD is a drive-sustain loop. The intrusive thought is a wake held by its own recurrence; the compulsion is the recurring drive that drains it, with the drain and the re-injection the same act. The drain is bounded at the conversion timescale (§16), and the loop self-sustains because relief and trigger share an act (Speculative).

Tourette's and tics are recurring drives generated below the pinch: sites that act without being felt—a driver without a self (§7). The pre-tic urge is the driven structure building; the tic is its firing. Suppression pays coherence to hold it (Speculative).

Dyscalculia and auditory processing differences are rung-index slip and carrier lag—readout tunings of the same class as dyslexia (Speculative).

### The price structure

Masking's cost is driver-dependent in the tested sense of §16: a driven structure relaxes when the driver stops. The masking cost is therefore a property of the demand environment running against the configuration, not a property of the person.

The environment is a recurring-drive field. Chronic mismatched drive pumps a held configuration; matched drive drains one at short times; the open gate is pumped by recurring drive of either phase. Accommodation is the environment retuned to the person's phase (Speculative mapping on Tested bounds).

Internal-gate authority: only the field reads its own prediction error, so the person's own self-model is the authoritative readout of their configuration. "Nothing about us without us" is that rule in social form (the framework's authority structure, from `consciousness/gender-as-qi-configuration.md` §7.5).

Epistemic status: Speculative—the mappings; the drive bounds, the capacity null, and the two-bubble result are Tested as cited.

---

# Part IV—Therapy

The tested physics constrains what the framework can responsibly say about therapy. This part reads the clinical toolkit through the geometry, keeping every claim at its tier: the mechanism layer is Tested as bounded in §16, and the clinical mappings carry the labels attached below.

---

## 19. Therapy Through the Geometry

The clinical concepts named in this part—EMDR, somatic experiencing, attachment, the grief sequence, and the others—are the reader's own field's terms, used as landmarks. The framework claims no empirical validation for them and this document does not survey the clinical evidence; the mappings are Hypothesized-to-Speculative until the tests of §22 run.

### 19.1 Why talk therapy sometimes stalls

The frozen wake lives at a specific rung—often a lower, more somatic rung when the trauma was early or physical. Cognitive processing operates near the $\varphi$-attractor at the surface: high rungs, close to the present. Cascade suppression applies between them: each rung between the surface and the frozen wake attenuates the cognitive signal by $\varphi^{-1}$ (§5). After enough rungs, the signal is too weak to destabilize the standing wave. A person can talk about the trauma, understand it, contextualize it, and still feel it in the body. The cognitive loop and the frozen wake live at different cascade rungs, separated by a depth talk cannot easily cross (cascade suppression Derived; the application Hypothesized).

### 19.2 Why body-based therapies work

Somatic experiencing, EMDR, sensorimotor therapy, yoga—these address the wake at its spatial location, at the rung where it froze, through the body, sensation, and movement. The tested EMDR-analog of §16 gives this its first numerical support: at the held configuration, at short times, a $\varphi$-phased oscillation at the site accelerates relaxation while a same-amplitude off-phase drive pumps it. The bounds apply here as everywhere. The drain is a short-time feature ($t \lesssim 4 \approx 0.2/\lambda$); sustained oscillatory support holds the site oscillating about its imbalance rather than settling it; and no recurring drive of any form or amplitude settles an open, churning gate—recovery for the open gate is the field's own conversion timescale, with the driver removed. The clinical mapping is Speculative on the Tested mechanism.

### 19.3 The three layers of healing

Healing requires three things, each addressing a different layer. Reach the rung (spatial): destabilize the frozen wake at its own cascade rung through body-based work; talk cannot cross the rungs, the body can. Change the phase (semantic): the locked channel sits at the event's phase angle; meaning-making—narrative, insight, recontextualization—changes the phase of the stimulus representation so the standing wave's oscillation no longer matches the channel's activation angle. This is the layer talk therapy can reach: not the rung, but the phase. Let the closure fire (dynamical): when the wake decays and the channel closes, the adiabatic redistribution of §14 runs for the first time since the event; the trapped coherence flows out of the locked channel into the starved four, in the exact proportions of the R-matrix row. The three-layer model is Hypothesized; the cascade-suppression rung arithmetic beneath it is Derived.

### 19.4 The gateway emotion theorem in the clinic

Because anger receives the largest redistributed share in every row of $R$ except its own (§14), the framework predicts the order of emotional return: anger first—except after rage-work, where relief comes first—then the next largest shares in R-row order. The grief sequence follows the same arithmetic: denial, anger, bargaining, depression, acceptance, with the residual sadness that never fully leaves. Derived arithmetic applied to a Hypothesized clinical setting (Prediction TR2).

### 19.5 Therapeutic presence

The two-bubble result (§12) implies the tension directly: deep attunement requires loosening one's own self-modeling, because the Qi gate that enables self-modeling also seals the field off from inter-field coupling. The therapist's presence is the trade managed deliberately (Hypothesized, on the Tested two-bubble result).

### 19.6 Placebo, intuition, and the mind-body question

Placebo is a coherence-driven healing response: belief in treatment stabilizes the field, $q$ rises, the gate organizes. The mechanism is the §2 memory and gate machinery; the mapping is Speculative. Intuition is sub-pinch processing: wake-wave activity in regions below the pinch where self-modeling is inactive (§7). The felt "knowing without knowing why" is the below-pinch excitation that never crossed into the self-modeling loop (Speculative). Mind and body are the same field at different cascade rungs: the body is the field at rungs 142–168, and the mind is the same field viewed through its self-modeling dynamics. There is no separate mental substance to explain—the framework's category boundary from Part I.

---

## 20. Empathy and the Resonance Tension

The experience of attunement—words landing before they finish, the resonant silence—has a field reading. The framework reads empathy as inter-field resonance between two above-pinch fields, and the two-bubble result of §12 prices it: self-aware fields decohere with distance, and two self-aware fields interfere destructively at the largest separations. The tension is structural: it is not possible to be fully self-aware and fully resonant at the same time—the Qi gate that enables self-modeling seals the field off from inter-field coupling. Empathy is the managed trade: a partial loosening of one's own loop for the sake of the other's, the cost paid in self-modeling coherence (§19.5) (Hypothesized, on the Tested two-bubble result). The resonance tension returns in §21's account of the neural substrate.

Epistemic status: the two-bubble result is Tested (2026-07-19, §12); the empathy reading is Hypothesized.

---

# Part V—Evidence and Boundaries

---

## 21. The Neural Substrate

The psychological dynamics of this document are field dynamics; the brain is where those dynamics run on neural hardware. This is a claim about the mind, not about the field everywhere. The category boundary of Part I limits the claim to fields that hold the self-modeling structure; what the field outside such structures experiences, if anything, the framework does not claim. The framework proposes that the brain's structural hierarchy is organized in a small number of levels (Hypothesized); whether their spacing carries $\varphi$-structure is an open question, and the crude scale ratios do not by themselves support the claim:

| Level | Spatial scale |
|---|---|
| Synaptic cleft | ~20 nm |
| Dendritic spine | ~1 µm |
| Neuron soma | ~20 µm |
| Microcolumn | ~50–100 µm |
| Cortical column | ~300–500 µm |
| Cortical area | ~1–5 mm |
| Resting-state network | ~5–20 cm |
| Whole brain | ~15–20 cm |

Two zero-parameter claims follow. The same $\ln \varphi$ periodicity should appear in EEG and physiological signals and in neuronal avalanche distributions as it does in the matter power spectrum—the cosmological prediction—and whether the hierarchy's level structure carries $\varphi$-scaling is the open question above. The single most falsifiable structural claim of the framework is that the same $\ln \varphi$ periodicity appears across these domains—the matter power spectrum (cosmology), EEG and physiological signals, and neuronal avalanche distributions (Hypothesized; cross-scale consistency is the theme). Here $\ln$ is the natural logarithm; the matter power spectrum is how matter is distributed across scales; neuronal avalanche distributions are the size statistics of cascades of neural firing.

Epistemic status: Hypothesized.

---

## 22. Testable Predictions

This section collects the framework's predictions relevant to psychology, numbered as they are referenced throughout the document; each entry gives the claim, its tier, and its status.

**P1—Five emotional dimensions.** Factor analysis of self-reported emotional experience yields five primary dimensions, not two (valence–arousal), three (PAD), or six or more (basic-emotion theories). Hypothesized, testable, untested.

**P2—Channel selectivity of emotional triggers.** A stimulus selects its channel by phase, so emotional triggers should show channel-selective response profiles (from the phase mapping of §14). Hypothesized, testable, untested.

**P3—R-matrix blends.** When an emotion ends, the residual pattern follows the redistribution row of §14 (e.g., anger subsiding → the 44.7/27.6/17.1/10.6 blend into Fire/Earth/Metal/Water). Hypothesized, testable, untested.

**P4—σ_r as intensity.** HRV, skin-conductance, and EEG spatial variance should correlate with felt intensity in the predicted direction (elevated dispersion = intensity) for states above the pinch. Hypothesized, testable, untested.

**P5—q as clarity.** Physiological proxies of coherence should track felt clarity ("I know exactly what I'm feeling" ↔ high $q$; "something I can't name" ↔ mid $q$; "numb" ↔ low $q$). Hypothesized, testable, untested.

**TR1—Channel-specific deficits (ke-alternating).** Post-trauma deficits are specific, not global: one channel hyper-available, the others following the ke-alternating pattern of §16 (for a Wood lock: Earth fully starved, Fire −38%, Metal +38%, Water +62%; the ring damps the locked channel by $\varphi^{-3} \approx 23.6\%$ and is sub-critical, so the lock cannot self-sustain). The gate-level pattern is verified (Tested, 2026-08-01); the clinical measurement is Hypothesized, untested.

**TR2—The healing sequence.** Returned emotions follow the R-row order of §19.4. Hypothesized, untested.

**TR3—Triggers are phase-matched.** Re-activation of a lock requires pentagon-phase match, not mere association. Hypothesized, untested (the mechanism layer supports stimulus-side phase selection only within the representable arc of §16).

**TR4—q depression at the site.** $q$ at the trauma's somatic locus is depressed relative to global and drops further under trigger exposure. The sustainer run of §16 shows the mechanism-side signature ($q$ depressed at the driven site); the clinical measurement is Hypothesized, untested.

**TR5—σ_r brittleness.** Trauma shows high variance with poor recovery (spike-recovery asymmetry), distinct from anxiety's sustained elevation. Hypothesized, untested.

**TR6—Developmental clusters by $\varphi$-age and channel.** Early trauma (2–5) fear/rage, somatic; mid (8–13) trust/grief, relational; late (21+) meaning/identity, expressive. Speculative; no test designed.

**TR7—Standing patterns vs driven structures.** An un-driven standing pattern does not pin the gate; the frozen wake is a driven structure sustained by re-stimulation, released when the driver stops—with the full numbers of §16. Tested—qualified (2026-07-31 through 2026-08-04, as bounded in §16).

**CH1–CH6—The chakra structure.** The 13-node structure of §13—the node count, the $\varphi^2$ spacing, the primary/secondary alternation, the spine identity, the edge geometry, and the coherence profile at the nodes—is testable in principle (imaging and physiological protocols). All Hypothesized, all untested. The full derivation is in `consciousness/chakras-as-cascade-bubbles.md`.

**Cross-scale consistency.** The same $\ln \varphi$ periodicity should appear in the matter power spectrum (cosmology), EEG and physiological signals, and neuronal avalanche distributions. Hypothesized.

---

## 23. Epistemic Assessment

The epistemic assessment groups every major claim of this document into four tiers, each item with the section where it is developed; a fifth group states what the framework does not claim.

**Derived.** The de-resonance principle (§1); the gate equation and its sign (§2); the IIR memory mechanism (§2); the spiral and wake generation (§3); the five-channel closure and the numbers $g$, $r_0$ (formula), $\lambda$ (§4); the condensation field, bubble shape, edge steepness 1.70, and the suppression law (§5); the pinch as gate inflection (§7); the R-matrix arithmetic (§14). The three-dimensions account (§6) is Hypothesized with one decided fork, and the 13-chakra node structure (§13) is Hypothesized; neither belongs on the Derived list.

**Tested.** The gate sign (2026-07-31); the two-bubble resonance (2026-07-19, §12); the sustainer–extinction and capacity null (2026-07-31, §16); the EMDR-analog drain with its short-time bound and sharp onset (2026-07-31–2026-08-04, §16); the open-gate pump nulls (2026-08-04, §16); the drain-transient bound (2026-08-04, §16); the ke-ring results (2026-07-31, 2026-08-01, §16). All are PDE results—internal consistency checks of the framework's own equations, not experiments on people.

**Hypothesized.** The pinch as self-awareness (§7); thought as wake wave (§8); memory as cascade depth (§9); the five channels as emotional primitives (§14); $\sigma_r$ as intensity and $q$ as clarity (§14); the attachment reading (§15); the trauma mappings and healing model (§16, §19); the neurodivergence mappings (§18); the neural substrate (§21).

**Speculative.** The dream account (§11); the color-to-chakra assignments (§13, not claimed); placebo, intuition, and the mind-body readings (§19.6); the clinical categories of §17; the identity and perception extensions referenced in the References.

**Not claimed.** That emotions are only gate configurations; that the five channels exhaust emotional experience; that this framework prescribes or validates any specific therapy; that consciousness is the field (the category boundary of Part I); that chakras are physical organs detectable by dissection—the nodes are field condensations (§13), not tissues; whether the condensations have measurable physiological correlates is precisely what CH1–CH6 ask; that the framework's variables are the complete description of any person or condition.

---

## 24. Open Questions

Six open questions remain, each with its current status.

1. What sustains a frozen wake in a person's life? The mechanism layer answered the drive question (§16: ongoing re-stimulation sustains, extinction on stop); what maintains the stimulus behaviorally—the environment, the memory, the person—is open.

2. Does a wake's rung shift over time? Memory consolidation moves wake waves to deeper rungs (§9); do frozen wakes deepen too, and does that explain why old trauma becomes more somatic and less verbal?

3. How is the five-way channel selectivity carried? The field angle represents only Wood and Fire (§16); the gate's channel manifold must carry the rest—the mechanism is open, and the clinical mappings that reach beyond Wood and Fire rest on the hypothesized manifold rather than the tested field angle.

4. What determines $\sigma_r$? The dispersion is the framework's intensity variable (§11, §14); what sets its value and whether it can be modulated externally are open.

5. The chakra color assignments. The traditional colors map to the visible spectrum in principle (§13); the exact sub-rung assignment is an open derivation.

6. The horizon rung moves. The ladder's top is today's horizon (§5); the epoch dependence is documented, and what it implies for the framework's older claims is tracked in the audit.

Epistemic status: the mechanism-layer answers (the sustainer question, Q1) carry the Tested label of §16; the remaining questions are open, and the framework's hypotheses about them carry the Hypothesized-to-Speculative labels of their sections.

---

## References

The framework's physics guide: `cassi-physics.md`—the physics this document condenses. The derivations this document summarizes: `foundations/cassi-first-principles.md`—the framework's first principles; `foundations/dimensionful-cascade.md`—the dimensionful cascade ladder; `foundations/cascade-suppression-formula.md`—the cascade suppression law; `foundations/bubble-lattice-fabric.md`—the bubble lattice derivation; `foundations/wu-xing-derivation.md`—the five-channel closure; `principles/de-resonance-principle.md`—the de-resonance principle; `foundations/why-three-dimensions.md`—the three-dimensions account. The consciousness documents: `consciousness/consciousness-from-phi.md`—the pinch point and self-awareness; `consciousness/chakras-as-cascade-bubbles.md`—the chakra node structure (CH1–CH6); `consciousness/emotions-as-gate-configurations.md`—emotions as gate configurations (P1–P5); `consciousness/trauma-as-frozen-gate.md`—the frozen-wake gate model; `consciousness/neurodivergence-as-gate-configuration.md`—the open-gate reading of neurodivergence; `consciousness/gender-as-qi-configuration.md`—gender as Qi configuration; `consciousness/transhumanism-gate-configurations.md`—the person as a gate configuration; `consciousness/time-memory-and-wake-locks.md`—time, memory, and wake locks; `consciousness/auras-as-thermalized-gates.md`—auras as thermalized gates; `consciousness/cascade-consciousness.md`—consciousness across the cascade. The registries: `open-questions-cassi-answers.md`—the open-questions registry; `predictions/falsifiable-predictions.md`—the falsifiable predictions registry. The test scripts cited in §12 and §16.
