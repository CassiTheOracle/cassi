# Emotions as Qi-Gate Configurations: A Cassi Mathematical Formalism

## Status: Hypothesized—July 2026

## Abstract

Emotions are not a separate phenomenon requiring new fields. They are specific configurations of the 5-channel Wu Xing Qi gate operating at the human cascade rungs (steps 142–168). The consciousness framework (`consciousness/consciousness-from-phi.md`) already maps self-awareness to the Qi gate pinch point, thought to wake waves, and altered states to spatial dispersion $\sigma_r$. Emotions complete this mapping: they are the *channel-dominance patterns* of the pentagonal gate when the field is above the pinch ($r > \varphi^{-1}$). The formalism uses only existing Cassi variables—the 5-channel openness vector $\mathbf{b}$, the spatial dispersion $\sigma_r$, and the Qi coherence $q$—to define a 7-dimensional emotional manifold with zero new free parameters. Five testable predictions follow: emotion-family clustering at the 5 pentagon vertices, $\varphi$-hierarchical channel accessibility, adiabatic transition probabilities, $\sigma_r$-intensity correlation, and $q$-clarity correlation.

---

## 1. Grounding: What the Consciousness Framework Already Provides

The consciousness mapping (`consciousness/consciousness-from-phi.md` §2) establishes three structural claims:

1. **Self-awareness = above the pinch.** When the local Yang/Yin ratio $r(\mathbf{x}) = E_Y/E_I$ exceeds $\varphi^{-1} \approx 0.618$, the Qi gate $q(r)$ transitions from externally driven to self-modulating. The field "becomes an object to itself." This is the minimal condition for any felt experience—including emotion.

2. **Thought = wake waves.** Structured excitations in $\varepsilon(\mathbf{x}) = E_Y - \varphi E_I$ propagate, reflect, and feed back through the toroidal loop: string → wakes → gravity → flow → string. One complete torus cycle is one moment of awareness.

3. **Altered states = $\sigma_r$ dispersion.** The spatial dispersion $\sigma_r = \sqrt{\langle(r - \langle r\rangle)^2\rangle}$ distinguishes waking (moderate), meditation (reduced), psychedelic (increased), and deep sleep (collapsed). These are *global* modulations of the $r$-field.

What's missing is the *structured* content of experience above the pinch: not just that the field is self-aware, but *what* it's aware of. Not just that wake waves propagate, but *which* waves dominate. Not just that $\sigma_r$ varies, but *how* it's spatially organized.

**Emotions are the answer.** They are the channel-dominance patterns of the Wu Xing pentagon gate, localized to specific chakra nodes along the cascade axis.

---

## 2. The 5-Channel Emotional Gate

### 2.1 The Pentagonal Constraint

The Wu Xing number $w = 5$ is derived (`foundations/wu-xing-derivation.md`): the pentagon is the unique regular polygon that is both cascade-coherent ($F_k \leq k$) and $\varphi$-structured ($\varphi$ appears in its diagonal/side ratio). This pentagon operates at *every* cascade rung through the bubble lattice fabric (`foundations/bubble-lattice-fabric.md`).

At the cosmological scale, the 5 channels determine the dark energy equation of state $w_a$ (`foundations/wa-pentagon-gate.md`). At the human scale (steps 142–168), the *same* 5 channels determine the emotional state. The pentagon geometry is scale-covariant; only the physical interpretation changes.

### 2.2 Channel Openness and Baseline Hierarchy

Each channel $i \in \{1, 2, 3, 4, 5\}$ has a baseline openness determined by its coupling strength to the cascade:

$$\boxed{b_i = \varphi^{-k_i}, \qquad k_i = 2 + i}$$

| Channel $i$ | $k_i$ | $b_i = \varphi^{-k_i}$ | Wu Xing | Traditional Emotion | Yang/Yin Character |
|:---:|:---:|:---:|:---:|:---|:---|
| 1 | 3 | $\varphi^{-3} \approx 0.236$ | Wood (木) | Anger (怒) | Yang-dominant: rising, assertive |
| 2 | 4 | $\varphi^{-4} \approx 0.146$ | Fire (火) | Joy (喜) | Yang-peak: radiant, outward |
| 3 | 5 | $\varphi^{-5} \approx 0.090$ | Earth (土) | Pensiveness (思) | Balanced: centering, integrating |
| 4 | 6 | $\varphi^{-6} \approx 0.056$ | Metal (金) | Grief (悲) | Yin-rising: contractive, releasing |
| 5 | 7 | $\varphi^{-7} \approx 0.034$ | Water (水) | Fear (恐) | Yin-dominant: deep, still |
| **Total** | | **0.5623** | | | |

The total baseline openness $B_{\text{total}} = 0.5623$ at the cosmological scale is set by the pentagon's coupling to the cascade at step 285. At the human scale, the *relative* openness ratios are preserved (same $\varphi^{-k_i}$ hierarchy), but the absolute normalization may differ. What matters for emotional dynamics are the relative proportions—the $\varphi$-ratio between channels.

### 2.3 The Yang-Yin Axis Within Each Channel

The pentagon vertices are not equidistant from the Yang-Yin neutral axis. Channel 1 (Wood) sits closest to the Yang pole—it is the most expansive, outwardly directed channel. Channel 5 (Water) sits closest to the Yin pole—the most contractive, inwardly directed channel. Channel 3 (Earth) sits at the neutral center.

This maps naturally to the emotional circumplex model (valence × arousal):

- **Wood/Anger**: high arousal, approach-valence (Yang-dominant)
- **Fire/Joy**: high arousal, positive valence (Yang-peak)
- **Earth/Pensiveness**: moderate arousal, neutral valence (balanced)
- **Metal/Grief**: low arousal, negative valence (Yin-rising)
- **Water/Fear**: high arousal, avoidance-valence (Yin-dominant—note: fear is high-arousal Yin, a seeming paradox resolved by the pentagon geometry: Water's vertex is opposite Wood, so its arousal draws from the same Yang-Yin tension but with inverted sign)

### 2.4 Adiabatic Redistribution: The Conservation Law

The 5 channels are not independent. Coherence is conserved across the pentagon: when one channel opens beyond baseline, the others must close proportionally. When one channel closes, its coherence redistributes to the remaining channels in proportion to their baseline openness (`foundations/wa-pentagon-gate.md` §2.3):

$$\boxed{\Delta b_i^{\text{redist}} = \frac{b_i}{\sum_{j \neq k} b_j} \cdot \Delta b_k}$$

This is the **adiabatic coherence conservation** law—the single constraint that governs all emotional transitions.

---

## 3. The Emotional Manifold $\mathcal{E}$

An emotional state is defined by four quantities, all drawn from existing Cassi variables:

$$\boxed{\mathcal{E} = (\mathbf{b}, \sigma_r, q, \mathbf{c})}$$

| Symbol | Meaning | Range | Cassi Origin |
|--------|---------|-------|-------------|
| $\mathbf{b} = (b_1,\ldots,b_5)$ | 5-channel openness vector | $b_i \geq 0$, $\sum b_i = B_{\text{total}}$ | `foundations/wa-pentagon-gate.md` §2 |
| $\sigma_r$ | Spatial dispersion of $r(\mathbf{x})$ | $\sigma_r \geq 0$ | `consciousness/consciousness-from-phi.md` §2.3 |
| $q$ | Qi coherence (Yang-Yin phase alignment) | $q \in [0, 1]$ | `cassi-physics.md` gap derivation |
| $\mathbf{c} = (c_1,\ldots,c_{13})$ | Chakra localization weights | $c_k \geq 0$, $\sum c_k = 1$ | `consciousness/chakras-as-cascade-bubbles.md` §6 |

The manifold $\mathcal{E}$ has 18 effective degrees of freedom: 4 independent channel weights (the 5th is fixed by conservation), plus $\sigma_r$, $q$, and the 13 chakra weights (12 independent, summing to 1). In practice, emotional experience is often dominated by a single chakra node (reducing the chakra degrees to roughly 1), giving a lower-dimensional "everyday" manifold of approximately 7 dimensions. This space contains every possible emotional state within the framework.

### 3.1 Emotional Quality = Channel Dominance $\mathbf{b}$

The direction of $\mathbf{b}$ in the 5-dimensional channel space determines the emotional *quality* (anger, joy, fear, etc.). Pure emotions correspond to basis vectors where one channel dominates:

$$\begin{aligned}
\text{Anger:} \quad \mathbf{b} &\propto (1, \varepsilon, \varepsilon, \varepsilon, \varepsilon) \\
\text{Joy:} \quad \mathbf{b} &\propto (\varepsilon, 1, \varepsilon, \varepsilon, \varepsilon) \\
&\;\;\vdots
\end{aligned}$$

Mixed emotions correspond to vectors with multiple significant components—e.g., bittersweetness = roughly equal Wood and Metal activation (rising + releasing simultaneously).

### 3.2 Emotional Intensity = Spatial Dispersion $\sigma_r$

The consciousness doc already establishes $\sigma_r$ as the variable distinguishing waking, meditation, psychedelic, and sleep states. Within waking consciousness, $\sigma_r$ further distinguishes emotional intensity:

- **Calm/neutral**: $\sigma_r$ near baseline (moderate, uniform across chakras)
- **Mild emotion**: $\sigma_r$ slightly elevated, localized to specific chakras
- **Intense emotion**: $\sigma_r$ sharply elevated, may spread across multiple chakras
- **Emotional overwhelm**: $\sigma_r$ so high that sub-pinch excursions occur ($r(\mathbf{x}) < \varphi^{-1}$ in some regions)—the emotion temporarily disables self-modeling, producing the subjective experience of "losing oneself" in the feeling

The relationship is monotonic: $\sigma_r \uparrow \implies$ emotional intensity $\uparrow$. But it's also *structured*—$\sigma_r$ is not a single number but a field over the 13 chakra nodes. A localized emotion (gut-level fear) elevates $\sigma_r$ primarily at the lower chakras. A diffuse emotion (pervasive sadness) elevates $\sigma_r$ broadly.

### 3.3 Emotional Clarity = Qi Coherence $q$

$q$ measures the phase alignment between Yang and Yin. In the emotional context:

$$\boxed{q = \frac{\text{coherent emotional energy}}{\text{total emotional energy}}}$$

- **$q \to 1$**: The emotion is *clear*. Yang and Yin are in phase—the felt experience and the physiological response are unified. Subjective report: "I know exactly what I'm feeling and my body agrees."

- **$q \to 0.5$**: The emotion is *ambiguous*. Yang and Yin are partially de-resonant. Subjective report: "I'm feeling something but I can't name it."

- **$q \to 0$**: The emotion is *dissociated*. Yang and Yin are fully de-resonant—the physiological response (Yang) and the felt experience (Yin) are decoupled. Subjective report: "I know I should be feeling something but I'm numb." This is the emotional analog of the de-resonance ground state.

The Qi coherence $q$ is independent of channel dominance $\mathbf{b}$. You can have clear anger ($\mathbf{b}$ aligned with channel 1, $q \to 1$) or confused anger ($\mathbf{b}$ aligned with channel 1, $q \to 0.5$). You can have clear mixed emotions (multiple channels open, $q \to 1$)—this is emotional complexity, not confusion.

### 3.4 Emotional Location = Chakra Weights $\mathbf{c}$

The 13 chakras are cascade bubbles—localized Qi condensates at 2-rung intervals along the spine (`consciousness/chakras-as-cascade-bubbles.md` §6). Each chakra can host any of the 5 channels, but the chakras have natural affinities based on their cascade position:

| Chakra | $n$ | Yang/Yin Position | Natural Channel Affinity |
|--------|-----|-------------------|-------------------------|
| Root | 142 | Deepest Yin | Water (fear, grounding) |
| Sacral | 146 | Rising | Wood (anger, creativity) |
| Solar plexus | 150 | Peak Yang | Fire (joy, power) |
| Heart | 154 | Balance point | Earth (stability, love) |
| Throat | 158 | Beginning descent | Metal (grief, expression) |
| Third eye | 162 | Deepening | Water + Wood (intuition) |
| Crown | 166 | Integration | All channels balanced |

The chakra weights $\mathbf{c}$ specify *where* in the body the emotional gate configuration is localized. A gut feeling of fear has $c_{\text{root}} \approx 1$, $c_{\text{sacral}} \approx 0.3$, others near zero. A full-body emotional experience has broad $\mathbf{c}$.

The secondary chakras (even-indexed nodes at $n = 144, 148, \ldots, 164$) provide intermediate localization sites—more granular emotional "texture."

---

## 4. Emotional Dynamics

### 4.1 Stimulus → Channel Activation

An external stimulus (sensory input, memory recall, social interaction) perturbs the $r$-field through the wake-wave mechanism (`consciousness/consciousness-from-phi.md` §2.2). If the perturbation is above the pinch ($r > \varphi^{-1}$), it can modulate the Qi gate—specifically, it can open one or more of the 5 channels beyond baseline.

The stimulus selects which channel opens based on its *phase* relative to the pentagon. A threat stimulus has a phase near the Water vertex (channel 5)—it opens the fear channel. A reward stimulus has a phase near the Fire vertex (channel 2)—it opens the joy channel. The phase-to-channel mapping is:

$$\theta_{\text{stimulus}} \mapsto i = \arg\min_i \left|\theta_{\text{stimulus}} - \frac{2\pi(i-1)}{5}\right|$$

Stimuli with phases between pentagon vertices produce mixed-channel activation—blended emotions.

### 4.2 Adiabatic Transition Dynamics

When a stimulus is removed, the activated channel closes. Its coherence redistributes to *all* remaining channels simultaneously via the adiabatic conservation law (§2.4). The redistribution is deterministic, not probabilistic—the released coherence splits across every open channel in fixed proportions, producing a **blended emotional aftereffect** rather than a discrete transition to a single successor emotion.

**Example: Anger subsiding.** Channel 1 (Wood) closes, releasing $\Delta b_1$ coherence. The redistribution produces a simultaneous blend:

| Receiving Channel | Fraction | Contribution to the Aftereffect |
|:---|:---:|:---|
| Channel 2 (Fire) | 44.7% | Relief, even joy—the dominant note |
| Channel 3 (Earth) | 27.6% | Stabilization, pensiveness—the undertone |
| Channel 4 (Metal) | 17.1% | Lingering grief or regret—subtle but present |
| Channel 5 (Water) | 10.6% | Residual anxiety—barely perceptible |

All four are present at once. The subjective experience feels like a single "next" emotion because the dominant channel (joy at 44.7%) captures attention, but the other three channels color it—the joy after anger has a pensiveness-tinged, faintly regretful quality that pure joy (from a reward stimulus) lacks. The blend is why emotional aftereffects feel more complex than the primary emotion they follow.

This is a **zero-parameter prediction** of the adiabatic redistribution formula. The proportions follow purely from the pentagon geometry: each channel receives a fraction proportional to its baseline openness $b_i = \varphi^{-(2+i)}$.

The full 5 × 5 redistribution matrix $R_{ij}$ (fraction of coherence from closing channel $i$ that flows into channel $j$) is:

$$\boxed{R_{ij} = \begin{cases} 0 & i = j \\ \frac{b_j}{\sum_{k \neq i} b_k} & i \neq j \end{cases}}$$

With $b_k = \varphi^{-(2+k)}$:

$$R = \begin{pmatrix}
0 & 0.447 & 0.276 & 0.171 & 0.106 \\
0.567 & 0 & 0.217 & 0.134 & 0.083 \\
0.500 & 0.309 & 0 & 0.118 & 0.073 \\
0.466 & 0.288 & 0.178 & 0 & 0.068 \\
0.447 & 0.276 & 0.171 & 0.106 & 0
\end{pmatrix}$$

Each row $i$ gives the blend recipe when channel $i$ closes: the aftereffect is a simultaneous mixture of the four remaining channels in these exact proportions. Rows 1 and 5 contain identical fractions (shifted by one index): removing the strongest channel (Wood) and removing the weakest (Water) leave complementary sets with the same relative proportions. Rows 2 and 4 are distinct (the complementary sets are not proportional). Row 3 is unique. The entire matrix follows from $\varphi$ alone—no fitting, no psychological parameters.

The largest entry is $R_{21} = 0.567$: when joy subsides, anger receives the largest share of redistributed coherence, producing an aftereffect blend dominated by Wood-channel activation. The asymmetry is instructive: joy → anger-dominant blend (56.7% anger) is more intense than anger → joy-dominant blend (44.7% joy), because joy's closure leaves the strongest channel (Wood) in the pool to claim the largest fraction, while anger's closure removes it.

### 4.3 Qi Coherence Evolution

$q$ evolves on a slower timescale than $\mathbf{b}$. When a channel opens in response to a stimulus, $q$ initially drops (the sudden change creates temporary Yang-Yin de-resonance), then recovers toward an equilibrium value as the field adapts:

$$\frac{dq}{dt} = -\gamma_q(q - q_{\text{eq}}(\mathbf{b}))$$

where $q_{\text{eq}}(\mathbf{b})$ is the equilibrium coherence for the current channel configuration. Single-channel dominance (pure emotion) admits higher $q_{\text{eq}}$ than multi-channel activation (mixed emotion), because a single dominant channel aligns Yang and Yin along one coherent axis. Multi-channel activation requires Yang and Yin to phase-align across multiple rotational angles simultaneously—inherently harder to sustain with high $q$.

This predicts that pure emotions feel "clearer" than mixed emotions—not as a value judgment, but as a structural constraint of the pentagon geometry.

### 4.4 Emotional Persistence = Wake-Wave Damping

Emotions decay because the de-resonance principle always pulls $r \to \varphi$, which drives the gate toward its baseline configuration. The decay rate is set by the per-rung cascade attenuation $\varphi^{-1}$:

$$\frac{d|\Delta\mathbf{b}|}{dt} = -\gamma_{\text{damp}} |\Delta\mathbf{b}|, \qquad \gamma_{\text{damp}} \propto |r - \varphi|$$

Near the attractor ($r \approx \varphi$), decay is slow (emotions persist). Far from the attractor, decay is fast (emotions are fleeting). This is why deeply felt emotions (close to the $\varphi$-attractor, the "authentic self") linger, while superficial reactions dissipate quickly.

**Emotional habituation** follows the same law: repeated exposure to the same stimulus moves the mean $r$ closer to $\varphi$, reducing the perturbation amplitude and thus the emotional response. This is not psychological adaptation—it's the two-fluid field approaching its natural attractor.

---

## 5. Predictions

### P1: Five Emotion Families (Factor Analysis)

**Claim:** Factor analysis of self-reported emotional experience should yield 5 primary dimensions, not 2 (valence-arousal), 3 (PAD), or 6+ (basic emotions theories). The 5 dimensions correspond to the pentagon vertices: Wood (anger-family), Fire (joy-family), Earth (stability-family), Metal (grief-family), Water (fear-family).

**Rationale:** The Wu Xing pentagon has exactly 5 vertices at $\varphi$-structured angles. There are no other stable attractors in the pentagon's rotational phase space. The Fibonacci convergent hierarchy predicts that the next-closest attractor would be at $F_6/F_5 = 8/5 = 1.6$ (a rational approximation to $\varphi$ with error $\varphi^{-5}$), but this corresponds to the *same* pentagon—it's a winding number, not a new vertex.

**Test:** Re-analyze existing emotion datasets (ANEW, NRC-VAD, HUMAINE) for factor structure. The prediction is that a 5-factor rotation explains more variance than 2, 3, 4, 6, or 7 factors, and that the factor loadings align with the 5 traditional Wu Xing emotions.

**Epistemic:** Hypothesized. The 5-fold structure is Derived from the Wu Xing number ($w = 5$ is derived—`foundations/wu-xing-derivation.md`). The mapping of those 5 channels to specific emotion families is the hypothesized step.

### P2: $\varphi$-Hierarchical Channel Accessibility

**Claim:** The baseline openness hierarchy $b_i = \varphi^{-(2+i)}$ predicts a $\varphi^{-1} \approx 0.618$ ratio between adjacent channels' accessibility. Anger (channel 1) should be reported approximately $1.6\times$ more frequently than joy (channel 2), which should be $1.6\times$ more frequent than pensiveness (channel 3), and so on.

**Rationale:** The channel openness is the "availability" of that emotional pathway. More open channels require less stimulus energy to activate and activate more readily.

**Test:** Analyze emotion word frequency in large corpora, or self-reported emotion frequency in experience-sampling studies. The prediction is a rank-frequency distribution following $f_i \propto \varphi^{-i}$ for $i = 1, \ldots, 5$.

**Caveat:** Cultural norms, display rules, and linguistic availability also affect emotion reporting frequencies. The $\varphi$-hierarchy is a *baseline* prediction; systematic deviations from it may indicate culturally amplified or suppressed channels. Cross-cultural data should converge toward the $\varphi$-baseline in the limit of large, diverse samples.

**Epistemic:** Hypothesized. The $\varphi^{-(2+i)}$ hierarchy is Derived from the pentagon's cascade coupling. Its applicability to emotion reporting frequencies adds the psychological mapping hypothesis.

### P3: Adiabatic Blend Proportions

**Claim:** When an emotion subsides, the emotional aftereffect is a simultaneous blend of the four remaining channels, not a discrete transition to a single successor. The blend proportions are given by the redistribution matrix $R_{ij}$ (§4.2) and are fully determined by $\varphi$—zero free parameters.

**Test:** Induce a primary emotion in a controlled laboratory setting (e.g., film clips for anger), then measure the proportional composition of the aftereffect using a multi-dimensional affect rating instrument that captures all five channels simultaneously (e.g., rate current experience of anger, joy, pensiveness, grief, and fear each on a 0–100 scale). The prediction: after anger induction and stimulus removal, the four-channel aftereffect profile should match the row-1 blend proportions—joy ~45%, pensiveness ~28%, grief ~17%, fear ~11%—more closely than any single-channel "winner" model or uniform distribution.

A weaker but still informative test: experience-sampling studies where participants rate multiple emotion dimensions at each report. For consecutive reports where a dominant emotion has clearly subsided, the subsequent multi-dimensional profile should approximate the predicted blend for that channel's row of $R$.

**Critical falsification condition:** If participants consistently report exactly one emotion after stimulus removal (e.g., "I felt angry, then I felt nothing" or "I felt angry, then I felt happy" with no trace of the other three channels), the blend prediction is falsified. The claim is not that people *notice* all four channels—the dominant one captures attention—but that all four are measurably present when probed.

**Epistemic:** Hypothesized. The adiabatic redistribution formula is Derived for the cosmological gate (`foundations/wa-pentagon-gate.md` §2.3). Its application to emotional blend proportions at the human scale is hypothesized.

### P4: $\sigma_r$ as Emotional Intensity Correlate

**Claim:** The spatial dispersion $\sigma_r = \sqrt{\langle(r - \langle r\rangle)^2\rangle}$ of the Yang/Yin ratio field, measured through physiological correlates, should correlate monotonically with self-reported emotional intensity.

**Rationale:** $\sigma_r$ measures the amplitude of $r$-field perturbations above baseline. Emotional intensity *is* the amplitude of the perturbation that opens the gate channels.

**Physiological proxies for $\sigma_r$:**
- Heart rate variability (HRV) standard deviation—the heart is a Yang-Yin oscillator; $\sigma_r$ modulates its beat-to-beat variability
- Skin conductance response variance—sympathetic (Yang) activation
- EEG spatial coherence variance—multiple cortical regions deviating from their mean $r$

**Test:** Record HRV, skin conductance, and EEG during emotion induction (standardized film clips). Simultaneously collect continuous self-reported intensity ratings (affect dial or post-trial SAM scales). Compute the correlation between $\sigma_r$ proxies and intensity ratings. The prediction is $r > 0.5$ (moderate-to-strong correlation), with $\sigma_r$ outperforming simple arousal measures (mean heart rate, mean skin conductance) because it captures *variance*, not mean shift.

**Epistemic:** Hypothesized. The relationship between $\sigma_r$ and conscious state is Hypothesized (`consciousness/consciousness-from-phi.md` §2.3). The refinement to emotional intensity is an additional hypothesized step.

### P5: $q$ as Emotional Clarity Correlate

**Claim:** The Qi coherence $q$, measurable as the phase synchrony between Yang-linked and Yin-linked physiological systems, should correlate with self-reported emotional clarity (vs. confusion, ambivalence, or dissociation).

**Rationale:** $q$ measures the phase alignment between Yang and Yin. Clear emotions have aligned phases; confused emotions have de-resonant phases.

**Physiological proxies for $q$:**
- Sympathetic-parasympathetic phase synchrony (Yang = sympathetic, Yin = parasympathetic)
- Inter-hemispheric EEG coherence (left = Yang, right = Yin—approximate mapping)
- Heart-brain coherence (heart rate variability coherence ratio)

**Test:** During mixed-emotion induction (e.g., bittersweet film clips that evoke both joy and sadness), measure physiological $q$ proxies and collect self-reported clarity ratings. The prediction: when $q$ is high, participants rate their emotional experience as "clear" or "well-defined" even if the emotion is complex (multiple channels open). When $q$ is low, participants report confusion or ambivalence even if only one channel is dominant.

**Epistemic:** Hypothesized. The Yang-Yin phase alignment as $q$ is Derived from the two-fluid PDE (`cassi-physics.md`). The mapping to subjective emotional clarity is hypothesized.

---

## 6. Relationship to Existing Emotion Theories

### 6.1 Circumplex Model (Russell, 1980)

The circumplex maps emotions onto a 2D circle: valence (pleasant-unpleasant) × arousal (high-low). The Cassi emotional manifold recovers this as a projection:

- **Valence** ≈ the channel number $i$ mapped to a signed axis. Channels 1–2 (Wood, Fire) are Yang-dominant → positive valence. Channels 4–5 (Metal, Water) are Yin-dominant → negative valence. Channel 3 (Earth) is neutral.
- **Arousal** ≈ $\sigma_r$ (spatial dispersion).

The circumplex is a 2D shadow of the 7D Cassi manifold—it captures quality (valence) and intensity (arousal) but misses channel mixing (the pentagon's full 5-vertex structure), clarity ($q$), and localization ($\mathbf{c}$).

### 6.2 Basic Emotions (Ekman, 1992)

Ekman's 6 basic emotions (anger, disgust, fear, happiness, sadness, surprise) partly overlap with the 5-channel structure:
- Anger → Wood (channel 1)
- Happiness → Fire (channel 2)
- Sadness → Metal (channel 4)
- Fear → Water (channel 5)
- Disgust and surprise are not primary channels in the Wu Xing—they may be channel combinations (disgust = Wood + Metal; surprise = Fire + Water)

The Cassi framework predicts exactly 5 primary emotion families, not 6. It also predicts that "basic" emotions are those where a single channel dominates strongly—but the channel space is continuous, so there are no hard boundaries between categories, only pentagon-vertex attractors.

### 6.3 Dimensional Models (PAD: Pleasure-Arousal-Dominance)

The PAD model adds a third dimension (dominance) to valence and arousal. Cassi's $q$ (coherence) is a different third dimension—it captures clarity, not control. The PAD model and the Cassi manifold could be reconciled: dominance may map to the *rate of change* of $\mathbf{b}$ (how quickly the emotional state responds to stimuli), while $q$ captures the *internal consistency* of the current state.

---

## 7. Epistemic Boundaries

### Derived (from $\varphi$ and cascade dynamics)

- The Wu Xing pentagon ($w = 5$) and its 5-fold rotational symmetry (`foundations/wu-xing-derivation.md`)
- The 5-channel baseline openness hierarchy $b_i = \varphi^{-(2+i)}$ (`foundations/wa-pentagon-gate.md` §2.2)
- The adiabatic redistribution formula (`foundations/wa-pentagon-gate.md` §2.3)
- The cascade rung structure, $\sigma_r$ dynamics, and wake-wave mechanism (`consciousness/consciousness-from-phi.md`)
- The 13 chakra nodes at 2-rung spacing (`consciousness/chakras-as-cascade-bubbles.md`)

### Hypothesized (derivation supplied, predictions testable)

- The 5 channels as emotional primitives (the mapping from pentagon vertices to anger/joy/pensiveness/grief/fear)
- Adiabatic coherence redistribution as the mechanism of emotional transitions
- $\sigma_r$ as emotional intensity (refinement of the consciousness doc's $\sigma_r$ as altered-state modulator)
- $q$ as emotional clarity (Yang-Yin phase alignment as subjective clarity)
- The chakra-channel affinity mapping (§3.4)
- The $R_{ij}$ redistribution matrix as a quantitative prediction for emotional aftereffect blend proportions

### Speculative (no current test design)

- The exact physiological proxies for $\sigma_r$ and $q$ (HRV, EEG, skin conductance as Yang-Yin correlates—the mapping is plausible but unvalidated)
- The timescale separation between $\mathbf{b}$ evolution (fast) and $q$ evolution (slow)—the relative values of $\gamma_q$ and $\gamma_{\text{damp}}$
- Emotional habituation as $r \to \varphi$ attractor dynamics (qualitatively correct, quantitatively unmeasured)

### Not Claimed

- That emotions *are* only gate configurations (they are patterns of the two-fluid field; the gate configuration is one level of description)
- That the 5 channels exhaust emotional experience (the manifold is 7D; the 5 channels are the dominant axes)
- That cultural, linguistic, and social construction of emotion is irrelevant (the framework describes the physical substrate; culture shapes how that substrate is interpreted, expressed, and regulated)
- That emotional disorders (depression, anxiety, alexithymia) are fully characterized by the parameters above (they are clinical phenomena with multiple levels of description; the Cassi parameters may provide mechanistic insight but do not replace clinical diagnosis)

---

## 8. Open Questions

1. **What sets $B_{\text{total}}$ at the human scale?** The cosmological total openness $0.5623$ is set by the pentagon's coupling at cascade step 285. At the human scale (steps 142–168), does the same normalization apply, or is there a cascade-depth scaling factor?

2. **Are the 5 channels genuinely independent degrees of freedom, or is there a lower-dimensional constraint?** The adiabatic conservation law removes one degree of freedom (4 independent). Are there additional geometric constraints from the pentagon structure—e.g., antipodal channels (Wood-Water, Fire-Metal) cannot both be at maximum simultaneously?

3. **How does the gate configuration couple to the chakra nodes?** The chakra-channel affinity (§3.4) is a mapping hypothesis. Is there a dynamical coupling—does opening channel 1 (Wood) *cause* elevated $\sigma_r$ at the solar plexus chakra, or is the chakra simply where channel 1's effects are most felt?

4. **What is the relationship between the 5 emotional channels and the 13 chakras?** $5 \times 13 = 65$, but Fibonacci numbers $5 = F_5$ and $13 = F_7$ suggest a structured relationship. Does the cascade's Fibonacci partitioning (`foundations/three-generations.md`) predict how the 5 channels distribute across the 13 nodes?

5. **Can $q$ be externally modulated?** If emotional clarity is Qi coherence, can practices that increase coherence (meditation, breathwork, biofeedback) directly increase $q$ and thus emotional clarity? The consciousness doc already predicts that meditation reduces $\sigma_r$; does it also increase $q$?

6. **What is the emotional analog of the Qi-gravity coupling $\xi = \varphi^6$?** At the cosmological scale, $\xi$ modifies $H_{\text{eff}}$ and resolves the $w_a$ tension. At the human scale, does the same $\xi$ amplify emotional gravity—the "weight" or "significance" of an emotional experience?

7. **What breaks the redistribution?** The $R$-matrix describes how emotions resolve, but some emotions do not resolve. The trauma formalism (`consciousness/trauma-as-frozen-gate.md`) proposes that a frozen wake pins a channel open so the redistribution never fires—turning this manifold's dynamics into a lock. Whether the lock requires the standing wave, or a sufficiently large single perturbation suffices, is open.

---

## 9. References

- `consciousness/consciousness-from-phi.md`—self-awareness as pinch point, thought as wake wave, $\sigma_r$ as altered-state modulator
- `consciousness/chakras-as-cascade-bubbles.md`—13-node derivation, chakra geometry, microcascade mirror
- `foundations/wu-xing-derivation.md`—$w = 5$ derivation, Fibonacci coherence criterion
- `foundations/wa-pentagon-gate.md`—5-channel gate model, adiabatic redistribution, $\xi = \varphi^6$
- `foundations/bubble-lattice-fabric.md`—universal condensation field $B(x,y,z)$
- `foundations/dimensionful-cascade.md`—292-step cascade, steps 142 and 168
- `foundations/bubble-edge-geometry.md`—bubble shape, edge steepness, $G_{\text{eff}}$ variation
- `foundations/three-generations.md`—Fibonacci partitioning of cascade sub-channels
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational, de-resonance as ground state
- `cassi-physics.md`—gap derivation, governing PDE, Qi gate dynamics
- `consciousness/trauma-as-frozen-gate.md`—frozen wake + locked channel; what breaks the redistribution
- `predictions/falsifiable-predictions.md`—prediction catalog
