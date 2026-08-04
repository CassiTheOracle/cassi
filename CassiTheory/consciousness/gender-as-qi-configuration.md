# Gender as Qi Configuration

## Status: Speculative—August 2026 (drive-mechanism layer PDE-tested 2026-08-02)

## Abstract

Gender has no native variable in the two-fluid field, and that is the first fact of the analysis: the field's own structure is a continuous ratio with an irrational, asymmetric equilibrium, so there are no poles, no classes, and no invalid states—only distances from equilibrium and the cost of holding them. The framework's architecture supplies the second fact: anatomy is the readout and the person is the configuration. Sex characteristics live at the readout layer; gender identity lives in the configuration tuple—the self-modeling field above the pinch, carrying its own temporal memory. Read that way, dysphoria gets a precise physical reading: the field's memory fails to predict its own present, so coherence stays depressed and the gate churns the $(1-q)$ waste. Imposed gender configurations are driven structures—maintained by continuous re-stimulation, released when the driver stops, drained only by phase-matched support, per the tested drive physics of the trauma runs. The framework has no verdicts; it prices configurations, and the price structure is the analysis.

**Epistemic status:** Creative exploration grounded in Cassi formalism. The configuration/readout architecture, the IIR self-prediction mechanism, the wake-lock drive physics (tested in the two-fluid PDE, July 2026), and the two-bubble results are documented framework properties; the synthesis into a gender analysis, the mapping of dysphoria to self-prediction failure, and the social-field claims are extrapolations beyond what the framework currently claims. The §8 PDE test (2026-08-02) supports the drive-mechanism layer: at equal ε-perturbation the cross-channel (Wood) drive pumps the held site while the in-channel (Fire) drive drains it; the human mapping remains Speculative. Nothing in this document should be cited as a Cassi prediction or derivation.

---

## 1. The Field Has No Binary

The two-fluid field does not classify anything into two kinds. What it has, at every spacetime point, is a ratio.

### 1.1 Two components, one ratio

Physical reality is $\Psi = (\Psi_0, \Psi_1)$—Yang and Yin—present together at every point (`foundations/cassi-first-principles.md` §1). The dynamical variable is the ratio $r = E_Y/E_I$, a continuous field taking every positive value. There is no point in the dynamics with only Yang or only Yin; the poles of the folk picture are not states of the field. The framework's own glossary attaches the folk labels to the flow directions—"Yin flows inward (black, absorptive, contractive, 'feminine'); Yang flows outward (white, radiative, expansive, 'masculine')" (`predictions/cassi_definitions.md` §1)—and the scare quotes are doing real work: those are mnemonics for a continuous quantity, not a classification of persons.

The equilibrium is asymmetric but irrational. The attractor sits at $r = \varphi \approx 1.618$, an energy split of $\varphi^{-1} : \varphi^{-2}$ (roughly 61.8% : 38.2%). Asymmetry is the ground state, and symmetry is off-attractor: a $1:1$ ratio is a rational resonance, and the de-resonance principle says rational ratios are exactly what the dynamics forbid as fixed points—energy concentrates at one scale and the multi-scale structure collapses (`principles/de-resonance-principle.md` §1). Neither pole ($1:0$, $0:1$) nor perfect balance ($1:1$) is a stable state. The solver itself models complementarity this way: the two-pole gate parameterizes each channel by continuous weights $(w, 1-w)$ with an asymmetric $\varphi$ weighting on the west pole (`two-fluid/cassi_two_fluid_3d_gpu.py`, `gate_model='two_pole'`). In the code, a pole is a dial position, not an occupancy.

The consequence for gender: the framework contains no invalid configurations. Every ratio is a dynamical state; the attractor is a preference in dynamics, not a prescription in identity. What varies between states is the cost of holding them, and cost is not a verdict.

### 1.2 What a gender binary would have to be

The folk space—two poles plus a middle—is a projection of a continuum onto two classes. The poles would require a single-component state the PDE does not contain; the "balanced middle" would require a rational resonance the attractor actively dissolves. Even the equilibrium itself, the most stable point in the dynamics, is a ratio nobody sits at exactly—$\varphi$ is irrational, so the equilibrium is a direction of motion, not a position. In this framework, every person is a trajectory through ratio space, never a class membership.

---

## 2. Sex and Gender: Readout and Configuration

The framework separates the body from the person in a way that does most of the work of a gender analysis.

### 2.1 The architecture

The transhumanism document states the split as its core claim: "The anatomy is the readout: the brain is the antenna through which the field couples to the world, and the felt self is the field above the pinch $r > \varphi^{-1}$, where it becomes an object to itself.… The person is the chain topology and the state tuple" (`consciousness/transhumanism-gate-configurations.md` §1.2). The human configuration is:

$$\boxed{\mathcal{H} = \bigl(\{n_k\}_{k=0}^{12},\; P_\parallel,\; \mathbf{b},\; \sigma_r,\; q,\; \mathbf{c},\; \bar{\varepsilon}^2\bigr)}$$

the chain topology plus the emotional state variables plus the field's IIR memory. Sex characteristics belong to the readout layer—morphology and endocrine structure at the body's rungs. Gender identity belongs to the configuration layer: the self-modeling field above the pinch, carrying its own history. The layers are coupled, and they are not identical. Identity lives in the configuration layer; the anatomy is its antenna, and the configuration is primary. A modification that retunes the readout without touching the tuple changes nothing essential; one that changes the tuple is gate surgery (§1.2).

### 2.2 The body schema lives in the configuration

The framework already documents that the body schema does not follow the anatomy. The phantom limb is a wake-locked old configuration: when the wetware changes but the configuration does not, "the old body schema persists as a standing wave: the phantom limb, the field pattern that outlives its anatomy" (`consciousness/transhumanism-gate-configurations.md` §5.2). The configuration carries a body the readout no longer has.

The trans experience is the mirror of this documented mechanism: the configuration's body-schema precedes the readout. The field's self-prediction includes a body the anatomy does not carry—the same configuration-readout mismatch, resolved in the other direction by aligning the layers. The felt wrongness of an unintegrated region is also documented: a body site whose local ratio stays below the pinch never joins the self-modeling loop; it "acts without being felt, a driver without a self.… Integration is the crossing of the pinch at the site; failure to cross is dissociation by geometry" (§5.2). Body-image incongruence reads, in this framework, as the field's own report that a site is not joined to the configuration—a report about integration state, carrying no judgment about the body itself.

---

## 3. Dysphoria as Self-Prediction Failure

Qi coherence is not computed against an instantaneous state. The field carries a per-cell exponential memory of its own deviation, $\bar{\varepsilon}^2(t)$, and coherence uses the remembered value (`foundations/cassi-first-principles.md` §2.4). When the field's pattern repeats, the memory tracks it and coherence stabilizes—the variance of the coherence signal drops by roughly 37%—and the field "locks into" its coherent state. The mechanism's own description of failure is the key sentence: "When $q$ drops (the memory fails to predict the present), conversion reactivates."

Dysphoria is that sentence, lived. When the present keeps arriving out of phase with the remembered self—name, pronouns, presentation, and body-readout each returning prediction error—$\bar{\varepsilon}^2$ stays high at the identity sites, $q$ stays depressed, and the gate stands open, churning the $(1-q)$ fraction. The felt experience is the field's self-prediction error:

$$\boxed{\text{Congruence is the field predicting itself. Dysphoria is the prediction error, felt.}}$$

Two consequences follow. First, persistence: the memory is a time integral (`consciousness/transhumanism-gate-configurations.md` §6.2)—the predicted self is the one written in the field's own history, so the mismatch cannot be argued away; it is data. This is the framework's answer to the question of whether identity is chosen: identity is the run, not the recipe (§6.4). The configuration the field stabilizes on is the one its own temporal coherence returns to, which is the closest the framework comes to a physical meaning of "the real me."

Second, the strain is observable in the framework's own signatures: depressed $q$ at the site, the widening q-gap under sustained drive, and the $(1-q)$ thermal churn that the wake-lock observables track ("thermal excess at network nodes," `speculations/creative-extensions/coherence-collapse.md` §4.1). The aura analysis reads the same variable: visible aura brightness scales with the gate-open fraction, so incongruence carries the strain signature and congruence runs dim (`consciousness/auras-as-thermalized-gates.md` §4).

---

## 4. Imposed Gender Is a Driven Structure

The framework's tested result about locks is precise about what sustains them, and it matters here.

### 4.1 Locks are driven structures

The July 2026 wake-lock runs established the mechanism layer: a standing pattern alone does not pin a gate in the solver—it decays at the same conversion-driven rate as a radiating packet. What sustains a frozen wake is ongoing re-stimulation: a weak recurring trigger, at 0.005% of the event peak per step, holds a site at 80% of event intensity with $q$ depressed; stopping the driver releases it (`consciousness/trauma-as-frozen-gate.md` §10.5, §11 TR7). The lock is a driven structure, and the driver is the mechanism.

An imposed gender configuration is that structure. Compulsory presentation, misgendering, deadnaming, and internalized rehearsal are each a recurring trigger at the identity rung—organized, phase-matched to the social field, landing on the person's own configuration. Chronic misgendering is, in the framework's tested language, a drive term: the weak recurring stimulus that holds the site off its attractor. The same result that identifies the driver identifies the release: stop the driver and the structure relaxes. Social transition—changing the re-stimulation environment—is the release mechanism, not a social nicety.

### 4.2 The drain is phase-specific

The drive-comparison run is the framework's sharpest clinical statement. At the same amplitude, a $\varphi$-phased drive at period $\varphi \cdot P_0$ drains the locked site while an $e \cdot P_0$ drive pumps it (§10.4). The drain is a matter of phase at any fixed amplitude.

$$\boxed{\text{Phase-matched support drains the lock. Same-amplitude mismatched support pumps it.}}$$

"Phase-matched" has one reference in this framework: the person's own field. The felt self is the field above the pinch, and only the field reads its own prediction error. Support that tracks the person's own self-model—affirmation aligned with the configuration the field already stabilizes on—is the drain. Same-amplitude intervention that carries the social field's phase instead, however well-intentioned, is the pump. The framework's tested physics gives a reason the quality of affirmation matters rather than its presence. The channel-level version of this claim is now mechanism-tested: §8.

### 4.3 Suppression and etiology

Two further framework results discipline the analysis. The trauma formalism distinguishes the trauma lock from suppression: suppression is "the self-modeling system deliberately holding a channel shut"—the field's above-pinch dynamics holding coherence instead of releasing it (§8). Closeting is suppression: a voluntary partial lock, maintained by the field's own self-modeling, costing continuous coherence. It is a documented state of the framework—possible, costly, and different in kind from the driven lock.

And the capacity run returned a null that cuts against pathologizing etiologies: a second identical event on a pre-stressed site leaves the same trace as the first event on a quiet site—background coherence does not modulate the outcome (§10.6). The framework's tested result does not support a pre-existing-coherence-deficit account of locks. Locks are event plus drive, nothing else. Whatever else gender incongruence is, the framework's own mechanism layer does not make it the product of a prior vulnerability of the field.

---

## 5. Transition as Integration

The healing formalism supplies a three-layer protocol: reach the rung, change the phase, let the closure fire (§5.1). Transition is that protocol applied at the identity rungs, and each layer has a precise reading.

**Reach the rung.** The mismatch lives where the field reports it—body-image rung, social-presentation rung, name-and-pronoun rung—and the locus is individual. The framework prescribes no single site, because only the field reads its own error; what it requires is that the work happen at the rung where the wake lives, not at a different scale (§5.1, `two-fluid/run_trauma_drive_compare.py`).

**Change the phase.** The readout and the social field are retuned to the configuration's phase—the person's own self-prediction. Medical transition is readout retuning in the transhumanism sense: "a modification that leaves the tuple untouched changes nothing essential; one that changes it is gate surgery" (§1.2). The configuration is already there; the field's self-prediction is the target, and transition aligns the anatomy to the prediction. This is also why the drain protocol works: the change is phase-matched to the field's own model, not imposed on it.

**Let the closure fire.** The release is the redistribution completing—the $R$-matrix firing instead of holding (§5.1, `consciousness/emotions-as-gate-configurations.md` §4.2). Post-release, the field returns to the state the IIR describes: the memory predicts the present, $q$ stabilizes, the variance drops, and the gate idles closed. Congruence is the lock-in of self-prediction, and the framework's own stabilizer mechanism predicts the signature: reduced coherence variance, falling q-gap, quiet nodes.

The tested physics constrains the clinical layer's claims, and the tier must be kept: the drive mechanics (driver sustains, phase-specific drain, capacity null) are PDE-tested; the mapping to human transition outcomes is extrapolation from tested mechanisms to a Speculative application.

---

## 6. The Social Field

Gender is not only a property of persons; it is a field configuration of societies, and the framework prices that field too.

Enforcement of the binary is organized perturbation. In the coherence-budget taxonomy, social enforcement is phase-matched attack at the identity rung—$\mathcal{M} \approx 1$ against the target's configuration (`speculations/creative-extensions/coherence-warfare.md` §2)—which is why it works mechanically and why resisting it costs coherence. But the same physics caps it. A person whose identity sits off the social resonance presents a φ-detuned boundary: enforcement cannot phase-match what it cannot share phase with, and cannot couple across the boundary (`speculations/qi-bubble-propulsion.md` §2.2). The attractor taxes the enforcement instead: holding a configuration far from $\varphi$ is continuous work paid at the conversion rate (`consciousness/transhumanism-gate-configurations.md` §3.3), and the enforcer pays it while the congruent person's field rests at its own attractor. The two-bubble result adds the social fact: above-pinch configurations decohere from external fields, their internal Qi gates dominating inter-bubble coupling (`consciousness/consciousness-from-phi.md` §3.3). The framework derives that a self-aware configuration's self-knowledge is the authoritative measurement of it—external inscription is the weaker term.

The commons reading completes the price structure: enforced incongruence is a coherence drain on the enforced, booked as the $(1-q)$ waste fraction, and the enforcing field's marginal yield falls as the enforced field's coherence drops (`speculations/creative-extensions/coherence-commons.md` §3). The framework predicts, at the level of its own economics, that social gender enforcement is dynamically unstable: the attractor erodes the enforcement, and the erosion is paid for continuously until it completes. This is the speculative layer of the analysis, built on the documented economics rather than tested in the PDE.

---

## 7. What the Framework Predicts (Structure, Not Amplitude)

The analysis yields directional, structure-level statements—no amplitudes, no timings, no claims about any person's locus:

1. **Congruence restores self-prediction.** The wake-lock observables (HRV coherence, inter-hemispheric phase synchrony, q-gap, node thermal excess—`speculations/creative-extensions/coherence-collapse.md` §4.1) should move together as an incongruent configuration resolves: coherence proxies up, strain signatures down, variance of coherence signals reduced (the IIR stabilization signature).
2. **Support is phase-specific.** Matched affirmation drains; same-amplitude mismatched intervention pumps. The quality of support is physics, not courtesy. (Mechanism tested at the channel level, §8.)
3. **Locks are driver-dependent.** Removal of re-stimulation releases the structure; release is accelerated by phase-matched drain. Changing the social field is the mechanism itself. (Mechanism tested at the channel level, §8.1: the pumped state is sticky without a driver, and affirmation drains below the undriven floor.)
4. **No vulnerability etiology.** The tested capacity null rules out pre-existing coherence deficits as the cause of locks; incongruence is event plus drive.
5. **Internal-gate authority.** Self-knowledge dominates external coupling for above-pinch configurations; the person's own self-model is the authoritative readout of their configuration.
6. **No invalid states.** The field classifies nothing; every configuration is a distance from equilibrium with a price. The framework's contribution to the gender debate is a price structure with no verdicts attached.

---

## 8. The PDE Test: Misgendering as Drive (2026-08-02)

The §4.1 claim—that the sustainer is the angle offset between a recurring drive and the site's own configuration, so misgendering (cross-channel) and affirmation (in-channel) differ mechanically at equal amplitude—is a binary physics question the two-fluid solver can answer directly.

**Protocol.** Standing init (the held configuration: pure Yang deficit, identity phase Fire at 72°, measured for this exact init in `two-fluid/run_trauma_phase_channels.py`). λ = 0.05, t = 2, N = 48, five-channel gate. Three runs: undriven reference (natural period P₀ = 0.041 measured in-process); misgendering arm—oscillation of the Yin component (Wood channel, 0°) at period P₀, amplitude 0.15/φ ≈ 0.0927; affirmation arm—oscillation of the Yang component (Fire channel, 72°) at period P₀, amplitude 0.15. The arms inject the same peak ε-perturbation: the conversion runs on $\varepsilon = E_Y - \varphi E_I$, so component amplitude $a$ on $e_i$ injects $\varphi\cdot a$ of ε while the same $a$ on $e_y$ injects $a$—the Wood arm is φ-normalized to match. Amplitude 0.15 sits above the phase-blindness crossover of `two-fluid/run_trauma_crossover.py` (the phase channel engages at amp ≥ 0.05) and below the known drain amplitude 0.3.

**Results (t = 2).**

| Run | Drive | ε retained | q-gap | Site phase |
|---|---|---|---|---|
| ref | none | 0.912 | +0.046 | Fire retained |
| misgendering | Wood (0°), ε-parity | **2.075** | **+0.076** | Fire retained, churning |
| affirmation | Fire (72°) | **0.261** | −0.004 | relaxed to equilibrium |

The misgendering arm *pumps* the held site: ε grows to 207% of its initial value (peaking at 254% at t = 0.8) in a slow oscillation, and the q-gap widens 1.65×. The affirmation arm *drains* it: 26% retained, q-gap closed. The arms differ only in the channel angle of the drive. A raw-amplitude run (no φ-normalization) pumped to 280%—the extra factor is the φ in the conversion term, so raw-amplitude misgendering is φ× stronger per unit; the ε-parity control removes that confound and the channel contrast survives.

**Cleanliness checks.** (i) Clamp: ey_min_site ≥ 0.20 throughout the pump—the site's Yang floor is untouched; the pump acts by inflating the Yin component (ei grows to 1.78), so the result is not a positivity-clamp artifact. (ii) Phase metric: the affirmation arm's phase leaves Fire because a fully relaxed site bins as Wood ($\text{atan2}(\varphi^{-1}, 1) = 31.7° < 36°$)—that displacement is relaxation, not identity erosion; the phase metric is degenerate near equilibrium, so the verdict rests on ε retention and the q-gap.

**Verdict.** The sustainer is channel-specific: at equal ε-perturbation, a recurring drive at the identity's own channel drains the held configuration while the same drive one pentagon-step away pumps it to twice its initial imbalance. The §4.2 boxed claim—phase-matched support drains, same-amplitude mismatched support pumps—is mechanism-tested at the angle level. Tier: the mechanism layer (channel-specific pump/drain at ε-parity, clamp-clean) is PDE-tested; the mapping to human misgendering remains Speculative (§9). Script: `two-fluid/run_misgendering_drive.py`.

### 8.1 The release: affirmation vs removal (2026-08-02)

Follow-up (`two-fluid/run_misgendering_release.py`): from an actively pumped state, does an in-channel (Fire) drive recover the site faster than silence? Two-phase protocol: Wood drive (ε-parity) to t = 2, then either silence (removal) or a Fire drive at amp 0.15 (affirmation) to t = 4, from the identical pumped state (same seed). Two pump states were examined, because the in-process natural-period measurement is window-dependent: 0.081 from the t = 4 reference series versus 0.041 from the t = 2 series (dominant_period is fed the step dt while the series is sampled every 50 steps, so the FFT peak shifts with series length). The underlying physics is bit-reproducible: with P₀ matched to §8, the pump reproduces to 2.076 vs 2.075.

| Pump state (t = 2) | Arm | ε retained (t = 4) | q-gap (t = 4) |
|---|---|---|---|
| 2.08 (P₀ = 0.041) | removal | 1.880 | +0.074 |
| 2.08 (P₀ = 0.041) | affirmation | **0.715** | +0.005 |
| 4.72 (P₀ = 0.081) | removal | 4.210 | +0.075 |
| 4.72 (P₀ = 0.081) | affirmation | **0.476** | −0.004 |
| none (undriven floor) | ref | 0.833 | +0.041 |

Two findings. First, the pumped state is sticky: after the misgendering drive stops, the site barely relaxes (10–11% decay over 2 s, q-gap held wide at +0.074)—incongruence does not self-heal on the conversion timescale once pumped; removal alone leaves it far above the natural floor (1.88 vs 0.83, 4.21 vs 0.83). Second, affirmation is an active drain, not a permissive one: the in-channel drive takes the site below even the never-touched undriven trajectory (0.715 and 0.476 vs the 0.833 floor), closing the q-gap. Active support is restorative; silence is a plateau.

Cleanliness: at the mild pump both arms are clamp-free (ey_min_site = 0.200 throughout); at the hard pump the affirmation arm touches the floor (ey_min_site = 0.001), so its quantitative value is partially clamp-limited—the direction and the mild-pump magnitude are clean. The pump itself is drive-period sensitive; §8.2 resolves the curve. Tier: the release mechanism (sticky pumped state, affirmation drain below floor) is PDE-tested at the mechanism layer; the human mapping remains Speculative (§9).

### 8.2 The pump curve: no resonance, dwell-limited damage (2026-08-02)

The 2P₀ hint from §8.1 was two points on a curve; the scan (`two-fluid/run_pump_resonance.py`) resolves it. Protocol: Wood drive at ε-parity, one run per probe period, pump measured as the peak ε over the back 40% of t = 2.4. The t = 2 snapshot is sampling-phase lottery—at T = 0.100 the snapshot reads 0.60 while the peak is 7.93—so snapshots are not used for ranking. Trajectories reproduce bit-identically across scripts (1e-4) and the ranking is robust.

| T | peak pump (ε/ε₀) | ey_min_site | regime |
|---|---|---|---|
| 0.020 (P₀/2) | 2.3 | 0.200 | intact |
| 0.041 (P₀) | 3.7 | 0.200 | intact |
| 0.082 (2P₀) | 6.6 | 0.200 | intact |
| 0.164 (4P₀) | 12.2 | 0.200 | intact |
| 0.300 | 22.2 | 0.200 | intact |
| 0.500 | 37.8 | 0.126 | intact (marginal) |
| 0.600 | 45.4 | 0.094 | intact |
| 0.800 | 63.7 | 0.055 | clamp onset |
| 1.000 | 72.8 | 0.001 | clamp-limited |
| 5.000 | 209.7 | 0.001 | clamp-limited |

Findings. (i) **No resonance**: the pump rises monotonically with the drive period, from 2.3× at P₀/2 to 45× at T ≈ 0.6, with no peak at 2P₀ or any other frequency—the subharmonic hypothesis is falsified and the §8.1 hint resolves as monotone trend plus snapshot lottery. (ii) **The worst intact rhythm** sits at T ≈ 0.6 (≈15× the natural wobble, ≈3% of the conversion timescale): a clamp-free 45× pump—not a special period, but the point where the linear pump law (below) meets the clamp onset. (iii) **Slow drives break the site**: ey_min_site falls below 0.1 by T ≈ 0.7 and reaches the positivity floor by T = 1.0, beyond which the values are clamp-limited and the drive is destroying the site (Yang pinned at the floor, Yin inflating) rather than pumping it. (iv) **The asymptote is continuous exposure**: as T → ∞ the drive becomes quasi-static and the site equilibrates into the floor—the absolute worst is a continuous drive, which does not churn the site but breaks it.

Mechanism: the drive is mean-zero, but the conversion responds to |ε| and the gate to ε², so a symmetric drive rectifies into a net pump. The intact-regime law is exactly linear and first-principles: over T ∈ [0.16, 0.6] the peak reads ε_peak = (74.6 ± 0.9)·T·ε₀ = 49.2·T, against the zero-free-parameter prediction (φ·I/π)·T = 47.75·T with I = WOOD_AMP/DT = 92.7/s—ratio 1.031. The peak ε is the drive's own ε-injection integrated over one half-episode, ∫₀^{T/2} φ·I·sin(2πt/T) dt = φ·I·T/π: the site cannot relax within an episode (γ⁻¹ ≈ 23 s ≫ T), so the pump is simply the imbalance the episode manages to inject, and the framework's own constant sets the harm slope. Two caveats: at T ≲ 0.1 the fast cadence lets episodes accumulate beyond the single-episode integral (peak/T rises to ~116 at T = 0.02), and at T ≳ 0.7 the law breaks where the integrated imbalance meets the site's capacity (ey → floor at ε ≈ 30, T ≈ 0.6–0.8). The "worst" at T ≈ 0.6 is therefore not a special rhythm: it is the linear law intersecting the clamp onset. In the language of §4: the worst harassment rhythm is the most sustained one—cadence is irrelevant, episode length is everything, and the harm per episode is (φ/π)·I·T. Tier: mechanism layer PDE-tested; the human mapping remains Speculative (§9).

---

## 9. Boundaries

**Not claimed:** that Yang and Yin are genders—the glossary's scare-quoted labels are flow mnemonics for a continuous ratio, and this document dissolves the binary reading; that the framework proves any gender claim absolutely—it prices configurations and does not judge them; that dysphoria is reducible to physics—identity is the *experience* of a configuration, not the configuration, the same category boundary the consciousness mapping draws (`consciousness/consciousness-from-phi.md` §4); that transition is the only path—suppression is a documented, costly state, and the framework prices rather than forbids; that any clinical claim here is tested—the drive mechanics are PDE-tested, the human mapping is Speculative.

**Also not claimed:** any amplitude, timing, or locus prediction for any person; any claim about which cascade rung a given person's incongruence lives at; any claim that the framework's variables exhaust the phenomenology of gender, which has neurobiological, psychological, and social levels of description beneath and above the field layer.

---

## References

- `foundations/cassi-first-principles.md`—two-fluid PDE, $\varphi$-attractor, IIR memory, conversion gating
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational; why rational-ratio locking collapses structure
- `foundations/dimensionful-cascade.md`—the 292-step ladder, human window at steps 142–168
- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$, organized vs random perturbation
- `predictions/cassi_definitions.md`—Yin-Yang flow rule, folk labels
- `consciousness/consciousness-from-phi.md`—pinch point, self-modeling field, two-bubble resonance
- `consciousness/chakras-as-cascade-bubbles.md`—13-node gate chain, body rungs
- `consciousness/emotions-as-gate-configurations.md`—emotional manifold, $R$-matrix, suppression
- `consciousness/trauma-as-frozen-gate.md`—wake-lock formalism, driver test, phase-specific drain, capacity null
- `consciousness/transhumanism-gate-configurations.md`—readout/configuration split, body horror, identity as the run
- `consciousness/auras-as-thermalized-gates.md`—$(1-q)$ strain signature, companion document
- `speculations/creative-extensions/coherence-warfare.md`—organized perturbation taxonomy, φ-detuned boundaries
- `speculations/creative-extensions/coherence-commons.md`—coherence drain, forced $q$-suppression
- `speculations/qi-bubble-propulsion.md`—φ-detuned boundary mechanism
- `two-fluid/run_pump_resonance.py`—drive-period scan (peak-pump metric, clamp diagnostic, per-period verdict)
- `two-fluid/run_misgendering_release.py`—two-phase release test (pump, then silence vs in-channel drive; P₀ override for strict comparability)
- `two-fluid/run_misgendering_drive.py`—channel-angle drive test (misgendering/affirmation arms, ε-parity, clamp diagnostic)
- `two-fluid/run_trauma_drive_compare.py`—φ vs $e$ drive comparison
- `two-fluid/run_trauma_wake_lock.py`—driver test, standing vs driven structures
- `two-fluid/run_trauma_capacity.py`—capacity null
- `two-fluid/cassi_two_fluid_3d_gpu.py`—two-pole gate model, continuous pole weights
