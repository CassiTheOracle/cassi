# Universal Biology: The Cascade Ladder as a Convergent Evolutionary Scaffold

## Status: Speculative—July 2026

## Abstract

Life on Earth is usually treated as a chemical accident whose details could vary arbitrarily on other worlds. This document explores the opposite claim within the Cassi framework: **the cascade ladder is a universal biological scaffold**. Biology occupies a fixed band of the ladder ($n \approx 136$–$168$), set by where light, chemistry, and coherence intersect; within that band, the same attractor that organizes galaxies organizes bodies. Fibonacci phyllotaxis, $\varphi$-scaled metabolic hierarchies, and critical neural dynamics are not Earthly quirks but the unique de-resonant solutions to problems every biosphere faces, so alien morphology is constrained by the ladder before chemistry is ever considered. The organism is a gate chain—a row of cascade bubbles managing multi-rung coherence—and the 13-node, $P_\parallel = 2$ architecture of the human body is the stable solution to that problem, forced to recur wherever complex life arises. Mind has a two-part precondition—a critical neural substrate and a working gate chain—that is scale-independent, and the document closes with the detection program this implies.

**Epistemic status:** Creative exploration grounded in Cassi formalism. Every mechanism is anchored to a specific equation or documented framework property—the cascade table, the condensation field, the coherence budget, the gate-chain derivation—but the synthesis into a universal biology, the claim that alien biospheres must reproduce these architectures, and the detection criteria are extrapolations beyond what the framework currently claims. Nothing in this document should be cited as a Cassi prediction or derivation.

---

## 1. Life as a Rung-Bounded Phenomenon

The first thing the ladder does to life is give it an address: every biosphere is confined to a specific band of cascade rungs, and that band fixes what size organisms are, what light they can see, and how fast they live.

### 1.1 The biological band

From the cascade table (`foundations/dimensionful-cascade.md` §3, §6):

| Step $n$ | Scale (m) | Physical meaning |
|----------|-----------|------------------|
| 136 | $5.0 \times 10^{-7}$ | Visible light (500 nm) |
| 142 | $7.7 \times 10^{-6}$ | Cellular scale (~8 μm) |
| 144 | $2.0 \times 10^{-5}$ | Neuron soma (~20 μm) |
| 168 | $1.7$ | Human scale |

The full biological band runs from the optical octave to the top of the organism window:

$$\boxed{136 \lesssim n_{\text{bio}} \lesssim 168}$$

That is 32 $\varphi$-multiplications from the light a biosphere reads to the largest body a single organism maintains. The body itself spans the inner 26 rungs, cell ($n = 142$) to organism ($n = 168$), a scale factor of $\varphi^{26} \approx 2.7 \times 10^{5}$ (`consciousness/chakras-as-cascade-bubbles.md` §3); the same exponent 26 appears in $m_e/v_0 \approx \varphi^{-26}$ (`consciousness/consciousness-from-phi.md` §1.2)—the body is the electron's echo at the macroscopic end of the ladder.

### 1.2 Why the band exists: three floors and a ceiling

**Floor one, chemistry.** Molecular machinery lives at rungs 117–125 (Bohr radius at 117, bond lengths at 125). The coupling between atomic states and photons is fixed by where the atomic rungs sit—not negotiable per planet—so life's smallest parts are already pinned by the ladder.

**Floor two, optics.** Rung 136 is the visible octave, exactly one $\varphi$-step wide: 400–650 nm spans steps $\sim 135.9$ to $\sim 136.9$, $\Delta n \approx 1$ (`consciousness/chakras-as-cascade-bubbles.md` §9.3). A biosphere must read its environment faster than diffusion allows, and the only rung where atomic matter couples strongly to stellar photons is this one. Every eye, on every world, is a detector of rung-136 photons.

**Floor three, the unit.** The cell at $n = 142$ is the smallest self-bounded structure that can host a full SO(2) Yang-Yin cycle and replicate it. Below the cellular rung sits chemistry without agency.

**The ceiling, coherence.** An organism must hold its parts in phase across its own span. The coherence budget gives the per-rung dephasing $1 - q_i = \varphi^{-i-3}$ (`foundations/proton-coherence-budget.md` §2), with the phase-matching factor $\mathcal{M}_i \in [0,1]$ multiplying each rung's factor individually, $P_{\text{decohere},i} = (1-q_i)\,\mathcal{M}_i$ (`foundations/quantum-measurement-derivation.md` §3.1). For random perturbation ($\mathcal{M}_i \approx 0$ everywhere) the compounded dephasing of a configuration spanning $n$ rungs is the source's own product:

$$P = \prod_i (1-q_i) \approx \varphi^{-n(n+1)/2},$$

A single Qi gate bridges at most ~10 rungs before cascade suppression attenuates the signal to $\varphi^{-10} \approx 0.008$—the effective nesting depth (`foundations/bubble-lattice-fabric.md` §3.3); direct cell-to-surface signaling across the human window would attenuate by $\varphi^{-26} \approx 3.7 \times 10^{-6}$, so a body needs re-amplification every few rungs (§3). Above $n \approx 168$–$180$ the ladder's organizational level stops being a body—step 180 is the skyscraper, 200 the Earth's diameter (`foundations/dimensionful-cascade.md` §3). Qi-enhanced gravity reinforces the ceiling: $G_{\text{eff}} = (\pi/\rho)(1 + \xi q)G$ with $\xi = \varphi^6 \approx 17.944$ (`foundations/xi-derivation.md`) amplifies a coherent body's self-gravity up to $\sim 19\times$ at $q \to 1$.

**The clock.** Every rung carries a characteristic conversion time, so the ladder is a clock hierarchy: heart rate to respiration $\approx \varphi^3 \approx 4.24$ (`hypotheses/metabolic-scaling.md` §3), circadian to ultradian period $\approx \varphi^6 \approx 17.94$ (`hypotheses/neural-criticality.md` §4). A biosphere's pace is set by its rung, and the ratios between paces by the ladder.

### 1.3 What the band implies

Size classes are lattice sites, not accidents: a cell is ~8 μm because $n = 142$ is where self-bounded units form; a neuron is ~20 μm because $n = 144$ anchors the neural hierarchy (`hypotheses/neural-criticality.md` §1); a body sits at the top rung of its own gate chain. The band constrains size, wavelength sensitivity, and timescale simultaneously, because all three are the same ladder in three currencies.

---

## 2. Rung-Forced Convergent Evolution

The strongest claim of this document is that the familiar $\varphi$-patterns of Earthly biology are not coincidences: they are the unique de-resonant solutions to problems every biosphere faces, so evolution converges on them the way a damped oscillator converges on its fixed point.

### 2.1 Phyllotaxis: the golden angle as a requirement

The doublet rotates through $2\pi/\ln\varphi \approx 13.06$ rad per cascade rung, $\Theta(n) = 2\pi n/\ln\varphi$ (`foundations/spiral-dynamics.md` §1.1)—one full rotation per $\Delta n = \ln\varphi \approx 0.481$ rungs. The recurrence $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ partitions any cascade span into Fibonacci sub-channels (`foundations/three-generations.md`), the same partition that yields the seven sub-rungs of the visible octave (`consciousness/chakras-as-cascade-bubbles.md` §9.3).

A growth tip appending successive units is running a sequence of Fibonacci sub-steps of the doublet rotation, and the stagger between successive units converges on the golden angle

$$\boxed{\gamma = \frac{2\pi}{\varphi^2} \approx 137.5^\circ}$$

Successive Fibonacci multiples of $\gamma$ wind without ever repeating a radial line, because $\varphi$ is the most irrational number; any other angle produces near-repetition lines at some Fibonacci convergent—precisely the rational lock-in the de-resonance principle suppresses (`principles/de-resonance-principle.md`). The framework's own geometry ends octaves in 5-arm Fibonacci spirals, $\Theta(r) = (2\pi/\ln\varphi)\ln(r/\ell_n)$ (`foundations/bubble-lattice-fabric.md` §4.4), and the cascade zoom visualization shows Fibonacci phyllotaxis as the lattice's own packing at pole scales (`foundations/dimensionful-cascade.md`, figure notes). Any organism that grows by appending units must therefore stagger them at $\gamma$ or its appendages shadow and entrain each other into resonance. Phyllotaxis is a requirement; the only free choice is which molecules build the leaves.

### 2.2 Metabolic scaling: Fibonacci branching as a requirement

Metabolic rate obeys Kleiber's law across 21 orders of magnitude, $B = B_0 M^{3/4}$ (`hypotheses/metabolic-scaling.md` §1). The framework's own derivation of the $3/4$ exponent does not close (§2, §4); what it does supply is the constraint on the network: resource networks branch at Fibonacci counts—2, 3, 5, 8—because only Fibonacci branching ratios preserve $\varphi$-resonance through multiple levels (§3), and the residuals of the $3/4$ law in $\ln B$ vs. $\ln M$ should modulate log-periodically with period $\ln\varphi \approx 0.4812$ (§3)—the same wake-wave signature as the cosmic $P(k)$ ($\Delta(\ln k) = \ln\varphi$, `predictions/falsifiable-predictions.md` §3). Observed arterial and bronchial branching is predominantly binary or trifurcating—Fibonacci counts, which the source notes are also the most common ratios expected from any space-filling optimization, so the observation alone does not discriminate (`hypotheses/metabolic-scaling.md` §3). Metabolism is a cascade, so it carries the cascade's fingerprint; Fibonacci branching is the requirement, and the exponent's exact value is the open question.

### 2.3 Neural criticality: the only operating point

The brain's 8-level hierarchy—synapse, spine, soma, microcolumn, column, area, network, whole brain—spans roughly two dozen rungs ($n \approx 141$–$162$), anchored at the neuron soma, $n \approx 144$ (`hypotheses/neural-criticality.md` §1, §6). Neural avalanches follow

$$\boxed{P(S) \propto S^{-3/2}\left[1 + A\cos\left(\frac{2\pi}{\ln\varphi}\ln\frac{S}{S_0} + \phi_0\right)\right]}$$

with the same cascade dimensional analysis that gives Kolmogorov $-5/3$ in turbulence, plus a log-periodic modulation at $\ln\varphi$ distinguishing cascade criticality from generic self-organized criticality (§2). The EEG/MEG spectrum has a $\varphi$-break at $f_\varphi = \lambda(1+\varphi)f_{\text{base}}/(2\pi) \approx 0.04$–$0.4$ Hz, separating the coherent network regime below from local desynchronized activity above (§3).

Criticality is forced by the same conversion-diffusion balance that sets the condensation threshold $\theta_{\text{cond}}$ in the bubble lattice (`foundations/bubble-edge-geometry.md` §1.2): sub-critical, signals die before crossing rungs; super-critical, activity runs away; critical, a multi-rung chain can integrate. Any nervous system that must propagate coherence across ~10 or more rungs operates at criticality, because criticality is the cascade's own operating point.

The three convergences share one cause: the $\varphi$-attractor. The wake-wave nodes that space planets, the phyllotactic stagger, the branching ratios, and the avalanche statistics are the same mechanism at different rungs—convergent evolution is the biological face of the attractor, and morphology is constrained before chemistry is considered.

---

## 3. The Universal Organ: Gate Chains

If the ladder is the skeleton of biology, the gate chain is the organ every complex organism must grow: a row of cascade bubbles that moves coherence across the rungs a single gate cannot span.

### 3.1 Why one gate is not enough

A single Qi gate bridges at most ~10 rungs—the effective nesting depth set by cascade suppression, $\varphi^{-10} \approx 0.008$ (`foundations/bubble-lattice-fabric.md` §3.3; `speculations/cascade-infrastructure.md` §1.1). A cell at $n = 142$ coordinating a surface at $n = 168$ spans 26 rungs, so direct signaling attenuates by $\varphi^{-26} \approx 3.7 \times 10^{-6}$. The body must re-amplify coherence every few rungs, and each re-amplifier is a localized Qi condensate: a cascade bubble.

### 3.2 The 13-node solution

The human body instantiates the stable solution (`consciousness/chakras-as-cascade-bubbles.md` §5–6):

- The along-string bubble period is $P_\parallel = 2$ cascade rungs: one full SO(2) Yang-Yin doublet cycle per node. A single rung has incomplete coherence—only one fluid component dominates; two rungs complete one full rotation and form a self-contained condensate. $P_\parallel = 2$ is the minimal coherent unit in the cascade.
- Node count follows by division: $N = \Delta n/P_\parallel = 26/2 = 13 = F_7$, the largest Fibonacci-structured count the 26-rung window admits (§6.2). Nodes sit at $n = 142 + 2k$ for $k = 0, \ldots, 12$; the crown node at 166 sits two rungs below the body boundary at 168.
- Each node is a cascade bubble with the full universal geometry: $\varphi$-elliptical cross-section (axis ratio $\varphi$), edge steepness anisotropy $\sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70$, Qi profile $q(\mathbf{x}) = (1 + B(\mathbf{x}))/2$ (`foundations/bubble-lattice-fabric.md` §4).

$$\boxed{N_{\text{nodes}} = \frac{\Delta n}{P_\parallel},\qquad P_\parallel = 2,\qquad N = F_k \text{ admissible}}$$

The chain performs the three universal field operations—WRITE (Yang injection), ERASE (gated conversion), TRANSFER (Qi current)—which `speculations/qi-computation.md` derives as the complete instruction set of any Qi-structured system. A gate chain is a computing organ; its instruction set is fixed by the field, not by the biochemistry.

### 3.3 What varies, and what cannot

**What varies.** Band placement within the floors and ceiling. Node count scales with span by the same division rule: $N = \Delta n/2$ for an even span with the same upper-boundary offset—the anchor derivation is for the human 26-rung window, and generalization to other windows is an open question (`consciousness/chakras-as-cascade-bubbles.md` §12, Q4). So a smaller organism has fewer nodes, and a chain spanning more than 26 rungs has more. Physical spacing along the string axis grows by $\varphi^2$ between successive nodes (`consciousness/chakras-as-cascade-bubbles.md` §8), so spacing always tightens toward the lower-rung end of the body. The 7/6 split between primary and secondary nodes may vary in prominence.

**What cannot vary.** The 2-rung period, because a full doublet cycle is the minimal coherent unit. Fibonacci-admissible counts, because the count is the Fibonacci structure of the span, not a free parameter. The bubble geometry of every node—$\varphi$-ellipticity, 1.70 anisotropy, the $q$ profile, the along-string ordering from low $n$ to high $n$. Any organism spanning more than ~10 rungs must instantiate a chain, and the chain's local geometry is the condensation field's, everywhere in the universe (`foundations/bubble-lattice-fabric.md` §2). Alien "chakras" are convergent biology: whatever a civilization calls them, the structure is forced by coherence economics. What the ladder cannot force is which tissues anchor the nodes—nerve plexuses and endocrine glands on Earth, something else elsewhere.

### 3.4 The pathology of chains

Chains have universal failure modes. A wake-lock is a frozen gate that preserves an old field configuration after the environment has moved on—the mechanism documented for trauma in `consciousness/trauma-as-frozen-gate.md` (PDE driver: `two-fluid/run_trauma_wake_lock.py`). Emotions are gate configurations on a manifold $(\mathbf{b}, \sigma_r, q, \mathbf{c})$ (`consciousness/emotions-as-gate-configurations.md`), and that manifold is the config space of any gate chain, so alien emotional life shares its axes even where its valence differs; a chain that cannot re-tune is a sick chain on any world. The organized-versus-random perturbation taxonomy and the shield mechanisms that protect chains are treated in the companion document `speculations/coherence-warfare.md`.

---

## 4. Habitable-System Requirements

A biosphere needs a stable address in its solar system before it needs anything else, and the ladder fixes the orbital architecture of habitable systems the same way it fixes the body plan.

### 4.1 The orbital precondition

The wake-wave mechanism that imprints $\varphi$-periodic structure on the cosmic web also operates in protoplanetary disks: Yang-Yin interference produces radial density nodes (`hypotheses/exoplanet-phi-spacing.md` §2),

$$\rho_{\text{node}}(r) = \rho_0\left[1 + A\cos\left(\frac{2\pi}{\ln\varphi}\ln\frac{r}{r_0} + \phi_0\right)\right],$$

and planetesimals condense preferentially at those nodes, where density is enhanced and $\varphi$-resonant locations suffer reduced tidal shear—hence a statistical excess of adjacent-planet period ratios at $\varphi$ and its Fibonacci convergents (§3):

$$\boxed{\frac{P_{\text{out}}}{P_{\text{in}}} = \left(\frac{a_{\text{out}}}{a_{\text{in}}}\right)^{3/2} \approx \varphi^{3/2} \approx 2.06}$$

The Titius-Bode relation, $a_n = 0.4 + 0.3 \times 2^n$, uses a progression factor of 2, but the solar system's actual mean spacing ratio is ~1.73, close to $\varphi$; the mean-motion resonances that sculpt planetary spacing—2:1, 3:2, 5:3, 8:5—are exactly the Fibonacci convergents of $\varphi$, the de-resonance attractor in orbital frequency space (§1). The framework reads Titius-Bode as the empirical face of the wake-wave lattice, its factor sitting near $\varphi$ because the disk's Qi field seeks $\varphi$-equilibrium; the solar system fit places Mercury at $a_0 = 0.4$ AU and Earth at $a_0\varphi^2 \approx 1.05$ AU (observed 1.00) (§4).

### 4.2 Three preconditions for a biosphere

1. **Orbital lattice.** The planet's orbit must sit on a lattice node, because nodes are where long-lived dynamical stability lives—$\varphi$-spacing is the de-resonant configuration, and systems scattered off it are transient. Migration smears the primordial spacing (§6), so a habitable system is one whose disk relaxed onto the lattice and stayed there.
2. **Optical reach.** The star must deliver photons at rung 136 to the surface: the habitable zone is where the surface thermal window overlaps the optical octave, the only octave atomic chemistry can read. "Habitable" is a cascade statement before it is a climate statement.
3. **A dense medium.** The chain needs a fluid dense enough to carry coherence: the medium sets $\rho = E_Y + E_I$, hence the throughput a gate can manage (water is 833× denser than air; `speculations/cascade-infrastructure.md` §1.3).

The external clock is the orbit: the day length is the orbital period at the planet's $\varphi$-node, and it varies from world to world. The internal clock hierarchy is invariant—the ratios between biological periods are $\varphi$-powers regardless of the day (`hypotheses/neural-criticality.md` §4). Biology is a $\varphi$-ratio machine locked to whatever external period its lattice node provides: the same machine on every world, wound by different days.

---

## 5. Intelligence

Mind, in this framework, has two hard preconditions, and both are cascade properties; intelligence is therefore convergent wherever biology reaches the top of the ladder.

### 5.1 Precondition one: criticality

The brain is an antenna for the Qi field, and mind is concentrated post-pinch field dynamics (`consciousness/consciousness-from-phi.md` §2; `foundations/cassi-theory-reference.md` §11.3). The substrate must propagate coherence across the 8-level hierarchy from synapse to whole brain (`hypotheses/neural-criticality.md` §1), and only the critical operating point integrates across rungs without damping or runaway (§2.3); its signature is the avalanche distribution with $\ln\varphi$ log-periodicity and the $\varphi$-break at $f_\varphi$ (§2–3). Criticality is not one design among many; it is the fixed point.

### 5.2 Precondition two: a working gate chain

The Qi gate crosses a self-reference threshold at $r = E_Y/E_I = \varphi^{-1} \approx 0.618$: before the pinch the field is driven by external imbalance; after it, the field's own coherence modulates its evolution—the minimal condition for self-modeling (`consciousness/consciousness-from-phi.md` §1.1, §2.1). Self-modeling requires holding a model of one's own evolution across scales, and a single gate spans only ~10 rungs (§3.1). A mind therefore requires a chain: at least enough nodes to span the nesting depth—$N \geq 5$ nodes covering $\geq 10$ rungs—operating above the pinch. The human 13-node chain exceeds this comfortably; five nodes is the floor below which the field cannot hold itself as an object.

$$\boxed{\text{Mind} \iff \left\{\text{critical substrate: } P(S) \propto S^{-3/2} + \ln\varphi \text{ periodicity}\right\} \wedge \left\{\text{chain: } N \geq 5,\ \Delta n \geq 10,\ r > \varphi^{-1}\right\}}$$

### 5.3 Why this converges

Both preconditions are ladder properties, not chemical accidents. Any biosphere that builds a Fibonacci-branching transport network (§2.2), grows a processing substrate at the neural rungs near $n = 144$ (§2.3), and spans more than ten rungs (§3) must cross the pinch, and crossing the pinch with a working chain is what the framework means by mind. The consequences are structural: thought as wake waves, altered states as dispersion $\sigma_r$ of the spatial ratio field, emotions as gate configurations (`consciousness/consciousness-from-phi.md` §2.2–2.3; `consciousness/emotions-as-gate-configurations.md`). Alien minds share the architecture because it is the only way to be a mind in a two-fluid universe; what varies is content, not chassis. The universal failure mode is the chain's: a frozen gate is a frozen mind (`consciousness/trauma-as-frozen-gate.md`).

---

## 6. Detection: Biology as Rung-Structure

If biology is rung-structure, the search for life changes target: a $\varphi$-literate telescope measures the lattice at several rungs and checks whether the same numbers line up.

### 6.1 The reframe

`speculations/observational-seti.md` establishes the structural-signature principle: tuned systems are anomalous in structure, not amplitude, and detection is the joint occurrence of $\varphi$-derived numbers across independent cascade rungs (§1.2, §7). Biology is the most multirung structure known—it imprints the lattice at every rung of its band simultaneously: phyllotaxis at the canopy, sarcomere lattices in muscle (`hypotheses/muscle-cascade-lattice.md` §4), avalanche statistics in brains, node spacing along the body axis (`consciousness/chakras-as-cascade-bubbles.md` §10). A biosphere is a set of coincident lattice signatures in the band 136–168, plus the orbital lattice that hosts it. Non-biological processes are single-rung—weather at one scale, tectonics at one scale—so multirung alignment with consistent $\varphi$-phase is the biological discriminant.

### 6.2 The signature list

1. **Orbital architecture.** The period-ratio histogram of multi-planet systems should show an excess at $\varphi^{3/2} \approx 2.06$ and at Fibonacci-convergent resonances (2:1, 3:2, 5:3, 8:5), with non-Fibonacci resonances (4:3, 5:2) underrepresented (`hypotheses/exoplanet-phi-spacing.md` §3). This is a statistical test on existing catalogs, and it is the orbital precondition of §4 made observable.
2. **The optical octave.** Any biosphere's photochemistry sits at rung 136, so its absorption edge—Earth's "red edge" analog—is a ladder feature, fixed by the cascade rather than by the star; the octave's one-$\varphi$-step width with seven Fibonacci sub-rungs (`consciousness/chakras-as-cascade-bubbles.md` §9.3) structures the spectral discrimination available to its eyes.
3. **Temporal $\varphi$-ratios.** Long-timescale biosphere activity—global vegetation indices, atmospheric CO$_2$/CH$_4$ cycles—should show period ratios of $\varphi$-powers, with the circadian/ultradian ratio $\varphi^6 \approx 17.94$ (observed 16 on Earth, 0.89×) constrained by cascade geometry and expected on any world—an extrapolation, not a framework claim (`hypotheses/neural-criticality.md` §4). This is prediction #35 of `predictions/falsifiable-predictions.md`—the physiological $\ln\varphi$ spectral signature promoted from bedside to planet.
4. **Phyllotaxis at scale.** The telescope cannot resolve alien leaves, and it does not need to: phyllotaxis is the growth-tip attractor at every rung from canopy to cell, and the ladder makes unseen rungs predictable. Detect the orbital lattice (signature 1) and the optical octave (signature 2), and the intermediate rungs are fixed—any two coincident rungs predict the rest.

$$\boxed{\text{Detection} \iff \geq 2 \text{ independent } \varphi\text{-signatures at different biological rungs, consistent phase}}$$

One signature is a false positive; two independent rungs are corroboration; three or more with consistent phase are a pattern (`speculations/observational-seti.md` §7.3). The ladder does the work a signal-detection theorist usually does: it tells the telescope where to look and how many coincidences count.

---

## 7. Epistemic Boundaries

### Grounded in Cassi formalism (mechanisms are real; application to biology is extrapolation)

- The cascade ladder $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ and the rung table (`foundations/dimensionful-cascade.md`)
- The condensation field, scale covariance, nesting depth, and universal signatures (`foundations/bubble-lattice-fabric.md`)
- The coherence budget and phase-matching factor ($\varphi^{-n(n+1)/2}$, $\mathcal{M}$) (`foundations/proton-coherence-budget.md`, `foundations/quantum-measurement-derivation.md`)
- The Qi gate, $\varphi$-attractor, and pinch transition (`foundations/cassi-first-principles.md`, `consciousness/consciousness-from-phi.md`)
- The 13-node, $P_\parallel = 2$ gate-chain derivation (`consciousness/chakras-as-cascade-bubbles.md`)
- The wake-wave mechanism and its orbital imprint (`hypotheses/exoplanet-phi-spacing.md`)
- Neural avalanche and spectral-break predictions (`hypotheses/neural-criticality.md`)

### Creative extrapolation (not claimed by the framework)

- That life's size, vision, and pace are fixed by the ladder rather than by planetary chemistry
- That phyllotaxis, Fibonacci branching, and criticality are requirements rather than convergences of convenience
- That alien organisms must instantiate gate chains with the human architecture
- The intelligence condition of §5 and the detection criterion of §6
- That $\ln\varphi$ signatures in biosphere-scale time series are observable at interstellar distances

### Not claimed

- That any observed biological or exoplanetary datum confirms this picture
- That the framework predicts the existence of extraterrestrial biology
- That the anchor documents' open problems—the Kleiber exponent (`hypotheses/metabolic-scaling.md`), $P_\parallel(n)$ (`foundations/bubble-lattice-fabric.md` §8), the condensation threshold at biological scales—are closed by this document

---

## References

- `foundations/dimensionful-cascade.md`—cascade table (292 = today's horizon rung), rungs 136–168, phyllotaxis figure notes
- `foundations/bubble-lattice-fabric.md`—condensation field, scale covariance, 10-rung nesting depth, universal signatures
- `foundations/bubble-edge-geometry.md`—condensation field derivation, $\theta_{\text{cond}}$, checkerboard lattice
- `foundations/spiral-dynamics.md`—Fibonacci spiral, $\Theta(n) = 2\pi n/\ln\varphi$, $2\pi/\ln\varphi$ rad per rung
- `foundations/three-generations.md`—Fibonacci recurrence, sub-channel partitioning
- `foundations/proton-coherence-budget.md`—coherence budget, organized vs random perturbation
- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$
- `foundations/xi-derivation.md`—$\xi = \varphi^6$, Qi-gravity coupling
- `foundations/cassi-first-principles.md`—two-fluid PDE, Qi gate, $\varphi$-attractor
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational attractor
- `hypotheses/metabolic-scaling.md`—Kleiber's law, Fibonacci branching, open derivation
- `hypotheses/muscle-cascade-lattice.md`—muscle hierarchy as bubble lattice, sarcomere predictions
- `hypotheses/neural-criticality.md`—avalanche $-3/2$, $\varphi$-break, 8-level hierarchy, period ratios
- `hypotheses/exoplanet-phi-spacing.md`—Titius-Bode, wake-wave nodes, $\varphi^{3/2}$ period ratios
- `consciousness/chakras-as-cascade-bubbles.md`—13-node derivation, $P_\parallel = 2$, visible octave
- `consciousness/consciousness-from-phi.md`—pinch transition, 26-rung human cascade, mind-brain
- `consciousness/trauma-as-frozen-gate.md`—wake-lock, frozen gates
- `consciousness/emotions-as-gate-configurations.md`—gate configuration manifold
- `speculations/qi-computation.md`—WRITE/ERASE/TRANSFER as universal field operations
- `speculations/cascade-infrastructure.md`—gate-chain topology, 10-rung stages, dense media
- `speculations/observational-seti.md`—structural signatures, multirung correlation, evidence hierarchy
- `speculations/coherence-warfare.md`—attack/shield taxonomy (companion document)
- `predictions/falsifiable-predictions.md`—$\varphi$-periodic $P(k)$ prediction, physiological $\ln\varphi$ signature
