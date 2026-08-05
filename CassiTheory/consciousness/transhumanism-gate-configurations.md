# Transhumanism as Gate Reconfiguration: Augmentation as Changes to the Gate Chain's Topology

## Status: Speculative—July 2026

## Abstract

The Cassi framework describes the human body as a 26-rung gate chain spanning the cascade window from the cell (step 142) to the organism (step 168), with 13 gate stages at $P_\parallel = 2$ rung spacing (`consciousness/chakras-as-cascade-bubbles.md`). This document asks what transhumanism—deliberate augmentation of capability—means in that picture. The answer: augmentation is not wetware replacement but **topological surgery on the gate chain**—adding nodes, changing the along-string spacing, re-tuning the band placement, and re-weighting the emotional configuration the chain instantiates. Each operation carries a stability condition: nodes must sit on condensation maxima, spacing must close full SO(2) cycles, spans must respect the ~10-rung bridge limit, and every added gate enlarges the decoherence surface and the wake-lock risk. The document derives the upgrade menu, the limits (the $\varphi^{n(n+1)/2}$ coherence budget required by longer chains—equivalently a $\varphi^{-n(n+1)/2}$ per-cycle dephasing probability—and the $\mathcal{O}(1)$ vulnerability to organized perturbation), and the failure mode (augmentation as a trauma driver; body horror as sub-pinch topology).

**Epistemic status:** Creative exploration grounded in Cassi formalism. Every mechanism is anchored to a specific equation or documented framework property, but the synthesis into an augmentation program, the specific gate operations, and the identity claims are extrapolations beyond what the framework currently claims. Nothing in this document should be cited as a Cassi prediction or derivation.

---

## 1. The Human as a Gate Configuration

### 1.1 The chain, in field terms

A human is a 26-rung cascade ladder. The dimensionful cascade (`foundations/dimensionful-cascade.md` §3) places the cell at step 142 ($\approx 8~\mu$m) and the body at step 168 ($\approx 1.7$ m): a ratio of $\varphi^{26} \approx 2.7 \times 10^5$, one scale transition per $\varphi$-step (`consciousness/chakras-as-cascade-bubbles.md` §3.2), with the spine as the ladder's string axis (`consciousness/chakras-as-cascade-bubbles.md` §2.2).

On the ladder sits the gate chain. The condensation field $B(x,y,z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z)$ is scale-covariant, producing bubble maxima along the string axis at $P_\parallel = 2$ cascade rungs—one full SO(2) Yang+Yin doublet cycle per node:

$$\boxed{n_k = 142 + 2k, \qquad k = 0, 1, \ldots, 12}$$

thirteen gate stages from root (n=142) to crown (n=166), the body extending two rungs beyond to the boundary at n=168. The count is Fibonacci-structured: $13 = F_7$, $26 = 2 \times F_7$ (§6.2 of the chakra document).

Each gate is a localized Qi condensate: a region where the conversion term

$$\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I)$$

is suppressed by high coherence, so a persistent pattern of imbalance $\varepsilon = E_Y - \varphi E_I$ is held against the attractor; at $q \to 1$ the effective conversion rate vanishes and the pattern is stable (`speculations/qi-computation.md` §1.1).

### 1.2 What the configuration *is*

The human, in field terms, is a tuple: the chain's topology—where the gates sit, how far apart, which cascade window they occupy—plus the field state the chain instantiates. The emotional formalism supplies the state variables—$\mathbf{b}$ (quality), $\sigma_r$ (intensity), $q$ (clarity), $\mathbf{c}$ (location) (`consciousness/emotions-as-gate-configurations.md` §3)—plus the chain parameters and the field's IIR memory $\bar{\varepsilon}^2$, $\tau = \varphi^{-1}$ (`foundations/cassi-first-principles.md` §2.4):

$$\boxed{\mathcal{H} = \bigl(\{n_k\}_{k=0}^{12},\; P_\parallel,\; \mathbf{b},\; \sigma_r,\; q,\; \mathbf{c},\; \bar{\varepsilon}^2\bigr)}$$

This tuple, evolved under the two-fluid PDE, is the configuration. The anatomy is the readout: the brain is the antenna through which the field couples to the world, and the felt self is the field above the pinch $r > \varphi^{-1}$, where it becomes an object to itself (`consciousness/consciousness-from-phi.md` §2, §2.1).

The consequence for transhumanism is immediate: **wetware swaps retune the readout; the person is the chain topology and the state tuple.** A prosthetic limb, a neural implant, or a pharmacological cocktail retunes the antenna; a modification that leaves the tuple untouched changes nothing essential; one that changes it is gate surgery.

---

## 2. The Upgrade Menu

Every proposed enhancement is one of three operations on the chain: add a node, change the spacing, or re-tune the band placement. Each has a stability condition inherited from the gate-chain physics and a characteristic failure mode.

### 2.1 Add a node

Insert a gate stage at a new rung $n'$ inside or adjacent to the window. Three stability conditions:

1. **The node must sit on a condensation maximum.** A gate is a bubble; bubbles condense only where the along-string field $B(0,0,z) = \cos(2\pi z/P_\parallel)$ is near $+1$ (`consciousness/chakras-as-cascade-bubbles.md` §4.1). An off-lattice insertion lands in a void: $q \to 0$, the gate structurally open with nothing coherent to convert—permanent churn, noise without capability.

2. **The node must be at least one full doublet cycle from its neighbors.** The minimal coherent unit is $P_\parallel = 2$ rungs—one complete SO(2) rotation, one Yang-dominant plus one Yin-dominant rung (§5.1 of the chakra document); a node at 1-rung spacing spans half a rotation with unbalanced conversion. The 14th condensation maximum would sit at $n = 168$, the body boundary (§6.1 of the chakra document); forcing a node inside the window instead requires 1-rung spacing—half a doublet cycle with unbalanced conversion (§5.1).

3. **The node must lie within one bridge length of a neighbor.** A single gate bridges at most ~10 rungs before cascade suppression attenuates the signal below the coherence floor, $\varphi^{-10} \approx 0.008$ (`foundations/bubble-lattice-fabric.md` §3.3, `speculations/cascade-infrastructure.md` §1.1).

The window admits exactly 13 nodes at $P_\parallel = 2$; the next Fibonacci count, $F_8 = 21$, needs 42 rungs—anchored at the crown its root falls below the cellular floor at n=126 (§6.2 of the chakra document). Node count is Fibonacci-capped at 13.

### 2.2 Change the spacing

Re-grid the chain from $P_\parallel = 2$ to another spacing. Stability conditions:

1. **Spacing must close an integer number of doublet cycles: $P_\parallel = 2k$.** Odd rung spacing leaves half-rotated doublets that cannot hold $q$ at maximum; the 7 primary chakras are the $P_\parallel = 4$ sub-lattice (§6.3, §9.3 of the chakra document), and the 5↔13 partition of `foundations/wu-xing-cycle-structure.md` §3.1 describes exactly these two granularities.

2. **Wider spacing weakens coupling; narrower spacing creates cross-talk.** Adjacent gates couple through shared rungs and the wake-wave field between them: close $\varphi$-separated pairs correlate strongly while above-pinch pairs decohere at distance (`consciousness/consciousness-from-phi.md` §3.3). Packed below $P_\parallel = 2$, the chain becomes mutually perturbing condensates—each node a perpetual stimulus to its neighbor (§5's failure mode). Spread beyond $P_\parallel = 4$, it loses coupling faster than it gains isolation.

3. **The manifold's resolution tracks the spacing.** The localization vector $\mathbf{c}$ has one weight per node, so coarse-graining from 13 to 7 nodes halves the spatial resolution of feeling. The quality space is untouched—$\mathbf{b}$ lives on the pentagon.

### 2.3 Re-tune the band placement

Shift the whole chain up or down the cascade—the root toward the microcascade, the crown toward the social and planetary rungs. Stability conditions:

1. **Shifts proceed in bridge-length steps, never jumps:** each gate moves at most ~10 rungs and stays within bridge range of its neighbors (`speculations/cascade-infrastructure.md` §1.1). A gap is an unsupported pattern—the field above it decoheres (§4.2).

2. **The endpoints must remain condensation maxima.** A chain whose endpoints sit in voids has no anchor and drifts with the ambient field.

3. **The cost is asymmetric in direction.** Descending multiplies the decoherence surface by the deep-rung factors, the largest in the cascade: per-rung dephasing at the bottom of the stack is $1 - q_0 = \varphi^{-3} \approx 0.236$, against $\varphi^{-171} \approx 10^{-36}$ at the top (`foundations/proton-coherence-budget.md` §1, §3). Ascending is cheap in coherence terms but rescales the physics the nodes couple to—$G_{\text{eff}} = (\pi/\rho)(1 + (\varphi^{6}-1)q)G$, $\xi = \varphi^6$ (`consciousness/chakras-as-cascade-bubbles.md` §7.3)—and the wake-wave environment; the megacascade above n=292 (`foundations/microcascade-mirror.md`) is the direction the cascade already flows.

### 2.4 The menu, summarized

| Operation | Field operation | Stability condition | Failure mode |
|---|---|---|---|
| Add a node | Insert a gate stage at $n'$ | On a condensation maximum; $\geq P_\parallel = 2$ from neighbors; within one bridge (~10 rungs) | Off-lattice void node: permanent low-$q$ churn |
| Change spacing | Re-grid to $P_\parallel = 2k$ | Even spacing (integer SO(2) cycles); $2 \leq P_\parallel \leq 4$ within the window | Sub-cycle spacing: half-rotated doublets, cross-talk |
| Re-tune band | Shift the window in $n$ | Bridge-length steps; endpoints on maxima | Gap: unsupported pattern decoheres; deep descent: surface blows up |

One item is absent from the menu: **new channels.** The pentagon is derived—$w = 5$ is the unique cascade-coherent, $\varphi$-structured count (`foundations/wu-xing-derivation.md`). Augmentation reweights the five channels; it does not add a sixth.

---

## 3. Superpowers as Stable Configurations

The upgrade menu is topology; the payoff is state. Which "powers" are stable points of the chain's dynamics, and which are excluded by the framework's limits?

### 3.1 What the emotional manifold admits

The state space is $\mathcal{E} = (\mathbf{b}, \sigma_r, q, \mathbf{c})$ (`consciousness/emotions-as-gate-configurations.md` §3). Its stable points:

- **Pure channel dominance.** The pentagon vertices are the only quality attractors: $\mathbf{b} \propto \mathbf{e}_i$ at baseline openness $b_i = \varphi^{-(2+i)}$ (§2.2 of the emotions document). Anger, joy, pensiveness, grief, fear—five pure states, no others (prediction P1).
- **Mixed states with high $q$.** Multi-channel configurations are stable but harder to hold at high coherence: Yang and Yin must phase-align across several rotational angles at once (§4.3 of the emotions document).
- **Reduced $\sigma_r$.** Attention stabilization is a documented state class (`consciousness/consciousness-from-phi.md` §2.3), and the same variable measures emotional intensity.
- **Ke-ring bounded states.** The control cycle transmits at $\kappa = \varphi^{-1}$ and restrains each channel's target, so the pentagon admits bounded oscillatory regimes (`foundations/wu-xing-cycle-structure.md` §2): a chain that runs its control ring has built-in regulation.
- **$\varphi$-proximity.** Near the attractor, decay is slow: deeply held configurations persist (§4.4 of the emotions document). The "authentic self" is the field resting at $r \to \varphi$.

That is the complete menu. Everything else in the wishlist is a combination of these or is excluded by the limits below.

### 3.2 What the math actually grants

Three capabilities are real configurations:

1. **Sustained high $q$ across the chain** is augmented cognition. At $q \to 1$, erasure costs $E_{\text{erase}} \propto (1-q) \to 0$ (`speculations/qi-computation.md` §2.3), persistent $\Pi$ patterns store without decay (§5.2), and the φ-spaced clock hierarchy integrates the stages (§4). Perfect recall and near-lossless processing are the same configuration, and it is the one contemplative practice has been training for—raising $q$ at the chakra nodes (`speculations/cascade-infrastructure.md` §1.2).

2. **$\sigma_r$ discipline** is attention as a maintained configuration. Collapsing the dispersion stabilizes the toroidal self-modeling loop; the torus period dilates, and the chain processes slower, deeper, with less noise (§2.3 of the consciousness document).

3. **$R$-matrix fluency** is emotional regulation made deterministic. The adiabatic redistribution matrix $R_{ij}$ governs every emotional transition (§4.2 of the emotions document); a chain that runs its redistributions to completion has clean aftereffects—anger resolving into the exact 44.7% joy / 27.6% pensiveness / 17.1% grief / 10.6% fear blend. The gateway-emotion theorem (`consciousness/trauma-as-frozen-gate.md` §5.2) fixes the return order: in every resolution except rage-work itself, the first returning channel is Wood.

### 3.3 What the limits exclude

The classic wishlist fails on four documented grounds:

- **The bridge limit kills cross-scale powers.** Flight, telekinesis, weather control—any capability coupling the body to distant rungs (n≈95 QCD, n≈220 AU) requires chained gates across spans a single gate cannot bridge (`foundations/bubble-lattice-fabric.md` §3.3).
- **The coherence budget kills immunity.** Stability against *random* dephasing is $N_{\max} = \varphi^{n(n+1)/2}$—astronomically large at the human scale ($\approx \varphi^{14196} \approx 10^{2967}$ cycles, `foundations/proton-coherence-budget.md` §7). But organized, phase-matched perturbation with $\mathcal{M} \approx 1$ has probability $\mathcal{O}(1)$ at the targeted rung, independent of cascade depth (`foundations/quantum-measurement-derivation.md` §3). The only defenses are φ-detuned boundaries that refuse coupling—the shield domain of `speculations/creative-extensions/coherence-warfare.md`.
- **The attractor taxes everything else.** Holding a configuration far from $r = \varphi$ requires continuous work against $V_{\text{attr}} = (\lambda/2)(\Psi_0^2 - \varphi\Psi_1^2)^2$ (`foundations/cassi-first-principles.md`); powers that live far from equilibrium are paid for at the conversion rate, and the payment shows up as §5's failure modes.
- **The pinch excludes unknowable powers.** Self-modeling exists only above $r = \varphi^{-1}$ (`consciousness/consciousness-from-phi.md` §2.1); a sub-pinch configuration acts without self-awareness by construction—the overwhelm regime, a driver rather than an augmentation.

---

## 4. Augmentation Limits

Three limits bound the entire program: the bridge length, the decoherence surface, and the quadratic coherence cost.

### 4.1 The bridge limit

A single Qi gate bridges at most ~10 cascade rungs; beyond that, cascade suppression attenuates the signal below the coherence floor,

$$\boxed{\varphi^{-10} \approx 0.008}$$

(`foundations/bubble-lattice-fabric.md` §3.3). The human chain is comfortably inside—26 rungs across 13 gates—and each stage harvests from the ~10 rungs of its own microcascade: the root reaches n≈132, the crown the body boundary (`speculations/cascade-infrastructure.md` §1.2). Every augmentation connecting distant rungs must be a chain of stages within bridge length of each other.

### 4.2 More gates is a larger decoherence surface

Every gate is an interface between the chain and the ambient field—a place where phase noise can enter and where organized perturbation can land. The per-cycle decoherence probability is the per-site factor $(1 - q_i)\,\mathcal{M}_i$ (`foundations/quantum-measurement-derivation.md` §3.1), compounded over the chain's coherence-bearing sites (cf. `foundations/proton-coherence-budget.md` §2):

$$P = \prod_i (1 - q_i)\,\mathcal{M}_i$$

Adding a gate adds a factor to the product and an attack surface: a site where a phase-matched perturbation operates at $\mathcal{O}(1)$ probability. In the language of `speculations/creative-extensions/coherence-warfare.md`, the vulnerability budget grows with node count in both the random and the organized channels.

### 4.3 The quadratic cost of a longer chain

The coherence budget of a condensed pattern is quadratic in the pattern's highest rung (`foundations/proton-coherence-budget.md` §3):

$$\boxed{N_{\max}(n) = \varphi^{\,n(n+1)/2}}$$

The body-scale pattern at n=168 has $N_{\max} \approx \varphi^{14196} \approx 10^{2967}$—functionally eternal against random dephasing. The limit that matters is the *marginal* rung: adding one rung of pattern height at rung $n$ multiplies the budget by $\varphi^{n}$—at the human scale, $\varphi^{168} \approx 10^{35}$. A longer chain is not a linear extension, and the cheapest rungs to add are at the top, where the pattern stops being a body. Descent into the microcascade is dominated by the deep-rung factors ($1 - q_0 = \varphi^{-3}$), the largest in the product; the cheap upward direction is where the chain becomes infrastructure rather than a person (`speculations/cascade-infrastructure.md` §4).

---

## 5. The Failure Mode: Augmentation as Wake-Lock

### 5.1 New gates are new stimulus sites

The trauma formalism identifies the failure of an emotional configuration: a perturbation exceeding the field's processing capacity freezes into a standing wave at the rung where it struck; the standing wave becomes a perpetual stimulus, the channel it opened never closes, and the resolving redistribution never fires. The locked state is

$$\mathcal{T} = (\mathbf{b}^*, \sigma_r^*, q^*, \mathbf{c}^*), \qquad \text{with } R \text{ frozen at } \mathbf{c}^*$$

(`consciousness/trauma-as-frozen-gate.md` §2.1): one channel pinned hyper-open, the others starved in the ke-alternating pattern (`foundations/wu-xing-cycle-structure.md` §2), local $q$ depressed, $\sigma_r$ brittle.

The augmentation connection is direct: **every added gate is a new site where an event can exceed processing capacity.** A node that begins self-stimulating—a pulsed implant, a perpetual input feed—is a driver, and the PDE tests are explicit that the lock is sustained by exactly that: ongoing re-stimulation holds a site at 80% of event intensity, and stopping the trigger releases it (§10.5 of the trauma document, `two-fluid/run_trauma_driver.py`). An augmentation that cannot stop stimulating itself is a trauma machine by construction: a perpetual stimulus pins a channel, and the pinned channel is the trauma signature.

### 5.2 Body horror, in field terms

Body horror is, in this framework, the *topology of the chain gone pathological*:

1. **Orphan gates.** Nodes inserted off the condensation lattice never condense; they sit in voids at $q \to 0$, the gate structurally open with nothing coherent to convert (§2.1): the part of the body always churning, never quiet—present but incoherent.

2. **Sub-pinch sites.** A node whose local $r$ stays below $r = \varphi^{-1}$ never joins the self-modeling loop (`consciousness/consciousness-from-phi.md` §2.1); it acts without being felt, a driver without a self. The uncanny quality of the modified part is literal—a field region operating pre-reflectively inside a post-pinch person. Integration is the crossing of the pinch at the site; failure to cross is dissociation by geometry.

3. **Over-bridge spans.** An augmentation spanning more than ~10 rungs without intermediate gates leaves an unsupported pattern above the gap; cascade suppression cuts the signal at $\varphi^{-10}$ (§4.1). Installed but undrivable—the horror of the device that works and does nothing.

4. **Wake-locked old configurations.** Wake-lock is a frozen gate preserving an old field configuration (`consciousness/trauma-as-frozen-gate.md`, `two-fluid/run_trauma_wake_lock.py`). When the wetware changes but the configuration does not, the old body schema persists as a standing wave: the phantom limb, the field pattern that outlives its anatomy. Radical augmentation *is* a wake-lock risk for the pre-augmentation self—the old configuration does not dissolve; it freezes.

5. **$G_{\text{eff}}$ pinching.** High-$q$ regions gravitationally self-reinforce through $G_{\text{eff}} = (\pi/\rho)(1 + (\varphi^{6}-1)q)G$ (`consciousness/chakras-as-cascade-bubbles.md` §7.3); a dense cluster of coherent implants becomes a local gravity well that concentrates coherence into itself and starves the surrounding chain—an augmentation that eats its host's field.

The common thread: horror is the *unintegrated* modification—the node below the pinch, off the lattice, beyond the bridge, or locked to an old configuration. The healthy state is simply the integrated one.

### 5.3 The integration protocol

The healing formalism supplies the rules: reach the rung (operate at the wake's own scale), change the phase (de-tune the stimulus from the locked channel), let the closure fire (run the $R$-matrix) (§5.1 of the trauma document). The PDE layer adds the quantitative tools: a φ-phased oscillation at period $\varphi \cdot P_0$ dissolves the lock at the held configuration at short times (t ≲ 4 ≈ 0.2/λ, `consciousness/gender-as-qi-configuration.md` §8.3) while a non-φ drive at the same amplitude pumps it (§10.4), and extinction follows from stopping the driver (§10.5). These are stability conditions of the same kind as §2's: every node must sit on a condensation maximum at even spacing within bridge range, must cross the pinch during integration (joining the self-modeling loop), must have a driver that is removable by design—self-stimulating nodes are prohibited outright—and integration should be driven at φ-structured periods, the drive removed once the configuration holds. A chain that violates these fails dynamically—it locks.

---

## 6. Uploading and Identity

### 6.1 What a mind is, in field terms

The person is the configuration $\mathcal{H}$ of §1.2 under time evolution, bound together by the self-modeling loop (string → wakes → gravity → flow → string; one torus cycle is one moment of awareness, `consciousness/consciousness-from-phi.md` §1.3, §2.2). Identity is the coherence string: the phase relations along the chain, the persistent $\Pi$ patterns the gates hold, and the IIR tail $\bar{\varepsilon}^2$ carrying the field's history (`speculations/qi-computation.md` §5). The brain is the antenna; the pattern is the message.

### 6.2 The copy problem

Uploading proposes to copy the coherence string into a new substrate. The framework's own primitives make the copy questionable at three independent levels:

1. **Reading is an interaction.** A readout of the full continuous field state is an organized perturbation at the pattern's rungs, and organized perturbation with $\mathcal{M} \approx 1$ collapses the configuration with $\mathcal{O}(1)$ probability per interaction (`foundations/quantum-measurement-derivation.md` §3.2). You cannot read the state without selecting a branch of it; the copy inherits a branch, not the state (random noise with $\mathcal{M} \approx 0$ selects nothing, §3.1).

2. **Coherence is relational.** $q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$ is defined against the local field, so a copy in a new location has a new ambient field, a new $G_{\text{eff}}$ environment, a new wake-wave structure—the same recipe under different boundary conditions.

3. **The memory is a time integral.** The IIR average is a weighted sum of the field's entire past (`foundations/cassi-first-principles.md` §2.4); a copy's filter starts at baseline. Whatever identity is carried by history—and the trauma formalism insists history is carried, in the frozen wakes and phase structure (`consciousness/trauma-as-frozen-gate.md`)—is what a copy cannot receive.

The levels compound: the copy is a new condensation with new coherence, new history, and a collapsed branch of the original's state. The two-bubble result adds the social fact: above-pinch configurations decohere with distance—self-aware fields do not φ-resonate (`consciousness/consciousness-from-phi.md` §3.3). Copies do not sync.

### 6.3 What persists

The transferable content is the configurational: $\mathbf{b}$, $\mathbf{c}$, the phase relations along the chain—the *relations*, not the field that instantiates them. These are, in principle, the WRITE and TRANSFER operations of `speculations/qi-computation.md` §2.2: organized patterns can be written into a prepared field and propagated through high-$q$ media. What cannot transfer is $q$ (environment-relative), the IIR tail (history), and the wake-wave structure (position-dependent). The transferable part is the recipe; the non-transferable part is the run.

### 6.4 The identity claim

The framework's answer to the upload question is structural:

$$\boxed{\text{Uploading copies the recipe. The person is the run.}}$$

Identity is the trajectory of a configuration under the attractor—the $\varphi$-driven history from formation through every modification made in place. Trajectories through the same attractor converge in ratio but diverge in configuration; two runs of the same recipe separate immediately and never rejoin. Continuity is preserved by *in-place* gate surgery—modifying the chain while the IIR memory runs and $r(t)$ continues—not by re-instantiation, which starts a new run with a new history. What ends a person is the driver structure—the metabolic and environmental flows feeding the configuration—which augmentation can retune but never replace with a copy.

---

## References

- `foundations/cassi-theory-reference.md`—compact framework reference: two-fluid PDE, Qi gate, cascade ladder, coherence suppression
- `foundations/dimensionful-cascade.md`—292-step cascade table, human window at steps 142–168
- `foundations/cassi-first-principles.md`—governing PDE, $\varphi$-attractor, IIR memory with $\tau = \varphi^{-1}$
- `foundations/proton-coherence-budget.md`—$N_{\max} = \varphi^{n(n+1)/2}$, per-rung dephasing, body-pattern budget
- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$, organized vs random perturbation, $\mathcal{O}(1)$ collapse
- `foundations/bubble-lattice-fabric.md`—universal condensation field, scale covariance, 10-rung nesting depth
- `foundations/cascade-suppression-formula.md`—signal attenuation $\varphi^{-N}$, coherence maintenance $\varphi^{-n(n+1)/2}$
- `foundations/bubble-edge-geometry.md`—condensation field derivation, checkerboard lattice, $\theta_{\text{cond}}$
- `foundations/wu-xing-derivation.md`—$w = 5$ uniqueness, pentagon geometry
- `foundations/wu-xing-cycle-structure.md`—sheng and ke cycles, the 5↔13 partition
- `foundations/wa-pentagon-gate.md`—5-channel gate model, adiabatic redistribution
- `foundations/microcascade-mirror.md`—bidirectional cascade extension
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational, the attractor as ground state
- `consciousness/chakras-as-cascade-bubbles.md`—13-node derivation, $P_\parallel = 2$, gate chain geometry, $G_{\text{eff}}$ self-reinforcement
- `consciousness/emotions-as-gate-configurations.md`—emotional manifold $(\mathbf{b}, \sigma_r, q, \mathbf{c})$, pentagon channels, $R$-matrix
- `consciousness/trauma-as-frozen-gate.md`—wake-lock formalism, locked channel, φ-phased drive, PDE tests
- `consciousness/consciousness-from-phi.md`—pinch point, wake waves, $\sigma_r$ states, two-bubble resonance
- `speculations/qi-computation.md`—WRITE/ERASE/TRANSFER, persistent $\Pi$ patterns, φ-spaced clocks, the brain as Qi computer
- `speculations/cascade-infrastructure.md`—gate chain topology, 10-rung bridge limit, human chain as 26-rung stage
- `speculations/creative-extensions/coherence-warfare.md`—attack and shield taxonomy (organized vs random perturbation, phase-matching, φ-detuned boundaries)
- `consciousness/cascade-consciousness.md`—field perception and the cascade nervous system
- `hypotheses/muscle-cascade-lattice.md`—the body as a living cascade ladder
- `two-fluid/run_trauma_wake_lock.py`—PDE test script for standing waves, drivers, and φ-phased relaxation
