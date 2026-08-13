# Qi Computation: Information Processing as Yang-Yin Gate Dynamics

## Status: Hypothesized (information budget: per-rung identity, Landauer row, flow rate—application of the ratified Derived convention) / Speculative (gate set, Wu Xing logic, cascade clock, brain mapping)—August 2026

## Abstract

Conventional computation processes bits—discrete, binary symbols stored in physically distinct memory cells and manipulated by sequential logic gates. In the Cassi framework, information is not an abstraction layered on top of physics. It is Qi coherence itself: the ratified information convention (`predictions/cassi_definitions.md` §11) identifies stored information with the entropy deficit $I = k_B\,q\ln\varphi$ that a coherent pattern of Yang-Yin imbalance sustains, because Qi coherence suppresses the conversion that would dissolve it. This document builds a model of computation on that ratified information budget and on the field dynamics. The Qi gate is the fundamental computational primitive. The Wu Xing pentagon provides a 5-phase logic richer than binary. The cascade supplies a φ-spaced clock hierarchy spanning today's 292 rungs from Planck to the horizon (292 is the epoch-dependent horizon rung, not a fixed cascade depth). Information storage is field memory through the IIR ($\tau = \varphi^{-1}$). And because $\lambda_{\text{eff}} \to 0$ at $q \to 1$, organized $\Pi$ is long-lived (§1.1)—but per-bit erasure still costs $\Delta q_{\text{bit}} = \ln 2/\ln\varphi \approx 1.44$ of the $q$ scale (the Landauer row, §2.3); the openness $(1-q)$ sets the processing rate, not the per-bit cost. The resulting speed-power tradeoff (§3.4) is the field analogue of voltage-frequency scaling in CMOS.

**Epistemic status:** The information budget—stored information $I = k_B\,q\ln\varphi$ (coherence IS information), the Landauer row, and the flow rate $dI_{\text{flow}}/dt$—is an application of the ratified Derived information convention (`predictions/cassi_definitions.md` §11) and is therefore **Hypothesized** here (a speculative application of a Derived identity to the gate picture). The gate set (WRITE/ERASE/TRANSFER), the Wu Xing 5-phase logic, the cascade clock hierarchy, and the neural mapping remain **Speculative/Creative** extrapolations. The budget numbers are doctrine; what is creative is attributing them to a computing device and a gate-set architecture. Nothing in this document claims an established Cassi *prediction* for a computable machine.

---

## 1. Information as Organized Π

### 1.1 What a bit is, in the field

In conventional computing, a bit is a physical system with two distinguishable states—a voltage above or below a threshold, a magnetic domain oriented up or down. The bit's physical implementation is arbitrary as long as the states are reliably distinguishable.

In the Cassi framework, information has a specific physical identity: it is **Qi coherence**. The ratified information convention (`predictions/cassi_definitions.md` §11) makes the identification exact: the entropy proxy is $S = -q\,k_B\ln\varphi$, and stored information is the entropy deficit relative to the fully disordered state ($q = 0$),

$$S = -q\,k_B\ln\varphi, \qquad I = S(q{=}0) - S(q) = +q\,k_B\ln\varphi \quad (\text{maximal at } q = 1).$$

A Qi-coherent pattern at coherence $q$ carries stored information $I = k_B\,q\ln\varphi$—**coherence IS information**. The field picture is preserved: the deviation $\varepsilon = E_Y - \varphi E_I$ forms an organized pattern that persists because a high $q$ suppresses the conversion term that would drive it back to equilibrium:

$$\frac{\partial \varepsilon}{\partial t} \propto -\lambda \cdot g(q) \cdot (1-q) \cdot \varepsilon$$

At $q \to 1$, the decay rate $\lambda_{\text{eff}} = \lambda \cdot g(q) \cdot (1-q) \to 0$, so organized $\Pi$ is long-lived *because* the coherence that stores it also suppresses its dissolution. But the budget is set by the ratified identity: stored information is fixed at $q\,k_B\ln\varphi$—it does not diverge as $q \to 1$, it saturates.

This reframes the relationship between information and thermodynamics. In conventional physics, information is fragile—entropy always increases, and maintaining order requires expending energy. In a Qi-coherent system the entropy proxy $S = -q\,k_B\ln\varphi$ makes higher $q$ *lower* entropy: the stored information is exactly the entropy deficit the maintained coherence sustains. The natural tendency at high $q$ is toward organized structure, not away from it. Entropy increase is what happens when $q$ drops.

### 1.2 Information capacity

Information capacity in the field is set by coherence through the ratified convention, not by a spatial mode count. A Qi-coherent region at coherence $q$ carries stored information

$$\boxed{I = k_B\,q\ln\varphi} \qquad \text{(maximal at } q = 1)$$

(`predictions/cassi_definitions.md` §11). The per-rung information quantum is

$$\ln\varphi \approx 0.4812\ \text{nats} \approx \log_2\varphi \approx 0.694\ \text{bits},$$

so a region at coherence $q$ holds $q/\ln\varphi$ nats of stored information on the $q$ scale, or equivalently $q/\log_2\varphi$ bits. A bit is a maintained $q$ difference of roughly $1/\log_2\varphi \approx 1.44$ q-units (the Landauer row, §2.3).

Capacity is bounded and set entirely by $q$: it saturates at $k_B\ln\varphi$ for full coherence and vanishes at $q = 0$, the fully disordered background. Spatial mode densities describe *where* patterns live (their volume occupancy and the minimum feature size at the operating rung), not how much information they carry—the amount of information is the coherence $q$ itself, and the per-rung identity is the Cassi claim.

The openness $(1-q)$ is flow, not storage. At a conversion processing rate $\lambda(1-q)$ per unit time, the information-processing (flow) rate is

$$\frac{dI_{\text{flow}}}{dt} = \lambda(1-q)\,k_B\ln\varphi$$

(`predictions/cassi_definitions.md` §11). Stored information is the maintained $q$; processing draws on the fraction of the flow that is not organized.

---

## 2. The Gate as a Computational Primitive

### 2.1 Yang-Yin conversion as a nonlinear transform

The conversion term in the two-fluid PDE is the fundamental operation on the field:

$$\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I)$$

$$\partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)$$

Given an input field state $(\Psi_0^{\text{in}}, \Psi_1^{\text{in}})$ at time $t$, the gate evolves the state for a duration $\Delta t$ to produce $(\Psi_0^{\text{out}}, \Psi_1^{\text{out}})$. This is a **continuous nonlinear transformation**—the field-space equivalent of a transistor.

The gate has three operating regimes, set by the local $q$:

| Regime | $q$ | $g(q)(1-q)$ | Gate behavior |
|---|---|---|---|
| **Idle** | $q \to 1$ | $\approx 0$ | Gate structurally open but no driving force. Field state is preserved. Information storage. |
| **Active** | $q \approx 0.46$ | Maximum ($\approx 0.088$) | Peak conversion power. The gate operates as a saturable amplifier. Small Π differences produce large conversion-rate differences. Processing mode. |
| **Locked** | $q \to 0$ | $= 0$ | Gate structurally closed ($g(0)=0$). No conversion regardless of driving force. Isolated mode. |

The gate function $g(q) = q/(\varphi^2 + q^2)$ creates opposing trends: at $q \to 0$ the gate is structurally closed (numerator vanishes); at $q \to 1$ the gate is open but the driving force $(1-q)$ vanishes. The conversion power $P \propto g(q)(1-q)$ peaks at $q \approx 0.46$, where both factors are appreciable.

The gate's computational function emerges from this nonlinearity. At intermediate $q$, small differences in the input Π produce large differences in the conversion rate, which produce large differences in the output Π. This is the field equivalent of gain.

### 2.2 A universal gate set

Any computation can be built from three operations on the Qi field:

**WRITE (Yang injection):** Create a local Yang excess $\delta\Pi > 0$ at position $\mathbf{x}$. This is the field equivalent of setting a bit to 1. Implemented by applying an organized external perturbation (electromagnetic, acoustic, or direct Qi coupling) with $\mathcal{M} \approx 1$ at the target location.

**ERASE (gated conversion):** Trigger controlled Yang→Yin conversion at position $\mathbf{x}$ to return $\Pi \to 0$. This is the field equivalent of resetting a bit to 0. Implemented by temporarily and locally reducing $q$ to activate the conversion term, then restoring $q$ once equilibrium is reached. Since the gate at $q<1$ drives the field toward the attractor, erasure is the *natural* (passive) operation—writing is the active one.

**TRANSFER (Qi current):** Move a Π pattern from position $\mathbf{x}$ to position $\mathbf{y}$ via the Qi flow component $J = \Psi_0\nabla\Psi_1 - \Psi_1\nabla\Psi_0$ (`foundations/cassi-first-principles.md` §2.2). The pattern propagates as a traveling wave in the Qi field, preserving its structure because propagation through a high-$q$ medium has $\mathcal{M} \approx 1$ for organized patterns.

These three operations—WRITE, ERASE, TRANSFER—are computationally universal. Any Boolean circuit can be compiled into a sequence of Qi field operations.

### 2.3 The cost of each operation

The ratified information convention (`predictions/cassi_definitions.md` §11) assigns each gate operation a cost on the coherence ($q$) scale.

**ERASE—the Landauer row.** Erasing one bit destroys exactly $\ln 2/\ln\varphi$ units of $q$:

$$\Delta q_{\text{bit}} = \frac{\ln 2}{\ln\varphi} \approx 1.44 \qquad \text{(necessary $q$ destruction per bit erased)}$$

As with Landauer's principle (erasing one bit dissipates $E = k_BT\ln 2$ into a reservoir), erasure in the field is the necessarily-irreversible operation: resetting $\Pi \to 0$ costs $\Delta q_{\text{bit}}$ of coherence, independent of how coherent the starting state was. It is not free at $q \to 1$; the $q$-destruction is the price of destroying organization.

**WRITE and TRANSFER—the flow budget.** Writing a new pattern and transferring one are processing operations. They draw on the flow rate, which the ratified convention ties to the openness $(1-q)$:

$$\frac{dI_{\text{flow}}}{dt} = \lambda(1-q)\,k_B\ln\varphi$$

(`predictions/cassi_definitions.md` §11). At high $q$ the stored information $I = k_B q\ln\varphi$ is large but the flow budget is small—storage is cheap, processing is slow. At $q \approx 0.46$ (the active regime, §2.1) the openness is largest, so writing and transferring are fastest there. The conversion power $P_{\text{conv}} = \omega_0\,g(q)(1-q)\,\rho_0$ (`speculations/superconductivity-as-qi-coherence.md` §1.3) is the mechanical driver of these operations; the information-theoretic cost is the $\Delta q$ spent and the $\lambda(1-q)$ flow available.

---

## 3. Wu Xing 5-Phase Logic

### 3.1 The pentagon as a state machine

The Wu Xing pentagon (`foundations/wu-xing-derivation.md` §4) has five vertices—Wood, Fire, Earth, Metal, Water—with two transition cycles:

- **Generation ($\rightarrow$):** Wood $\rightarrow$ Fire $\rightarrow$ Earth $\rightarrow$ Metal $\rightarrow$ Water $\rightarrow$ Wood. Each step feeds the next; the cycle is constructive and phase-coherent.
- **Control ($\dashrightarrow$):** Wood $\dashrightarrow$ Earth $\dashrightarrow$ Water $\dashrightarrow$ Fire $\dashrightarrow$ Metal $\dashrightarrow$ Wood. Each step restrains the next; the cycle is regulative.

A computational state is the current Wu Xing phase at a given field location. A transition is a gate operation that advances the phase by one vertex along either the generation or control cycle.

### 3.2 Encoding

Five phases admit $\log_2 5 \approx 2.32$ bits of information per Wu Xing "digit" (a *wu*). A single wu carries more information than a binary bit but less than two bits. More importantly, the transition structure provides **natural error detection**:

The 5 vertices × 4 allowed transitions (generation forward, generation backward, control forward, control backward) = 20 valid operations. Any operation that does not follow one of these 20 paths is a phase error—instantly detectable because it breaks the pentagon geometry. The error-detection overhead is zero: the geometry itself enforces validity.

### 3.3 Computation by phase advance

A computation in Wu Xing logic is a sequence of pentagon-phase advances. An addition of two numbers, for instance, might involve:

1. Encode operands as Wu Xing phase vectors
2. Align phases via control-cycle adjustments (Earth restrains Water, etc.)
3. Advance through the generation cycle a number of steps equal to the carry value
4. Read out the result as the final phase configuration

The specific mapping of arithmetic to Wu Xing transitions is an open design problem—this is the Qi equivalent of designing an instruction set architecture.

### 3.4 Physical implementation

A Wu Xing logic gate can be implemented in a quasicrystalline material with the five-element doping pattern described in `speculations/qi-bubble-propulsion.md` §4.4. Each dopant type (Wood = low-Z, Fire = transition metal, Earth = noble, Metal = heavy, Water = rare-earth) creates a local bias toward that Wu Xing phase. An external Qi perturbation with the right phase-matching advances the local field from one vertex to the next.

The gate operation time is set by the conversion timescale at the operating rung:

$$t_{\text{gate}} \approx \frac{1}{\lambda_{\text{eff}}} = \frac{1}{\lambda \cdot g(q) \cdot (1-q)}$$

At $q \approx 0.46$ (the active regime where $g(q)(1-q)$ is maximized), $t_{\text{gate}}$ is minimized—this is the "maximum clock speed" operating point. At $q \to 1$, the gate slows down (conversion is suppressed) but energy cost drops to zero. This is a speed-power tradeoff intrinsic to Qi computation, analogous to the voltage-frequency tradeoff in CMOS but emerging from field dynamics rather than circuit parasitics.

---

## 4. The Cascade as a Clock Hierarchy

### 4.1 φ-spaced clock domains

Every cascade rung has a characteristic timescale:

$$t_n = \frac{\ell_n}{c} = \frac{\ell_{\text{Pl}} \cdot \varphi^n}{c}$$

The ratio of timescales between adjacent rungs is:

$$\frac{t_{n+1}}{t_n} = \varphi \approx 1.618$$

A cascade-spanning computer has **φ-spaced clock domains**: each rung operates at its own natural frequency, with the rung above running $\varphi$ times slower and integrating the output from the rung below.

| Rung $n$ | Scale | $t_n$ (seconds) | Clock domain | Computational role |
|---|---|---|---|---|
| 0 | Planck | $5.4 \times 10^{-44}$ | Quantum noise floor | Not directly accessible; sets the $\sigma$-regularized baseline |
| 95 | QCD | $4.5 \times 10^{-24}$ | Nuclear | Ultrafast parallel processing; immense parallelism in nuclear volume |
| 117 | Atomic | $1.8 \times 10^{-19}$ | Electronic | Conventional electronics operates here; single-rung domain |
| 136 | Visible light | $1.7 \times 10^{-15}$ | Optical | Photonic computation; inter-chip communication |
| 150 | Sub-millimeter ($\ell_{150} \approx 3.6\times10^{-4}$ m; cellular scale is rung 142) | $1.2 \times 10^{-12}$ | Biological | Cellular signal processing; ~GHz effective clock |
| 168 | Human | $5.7 \times 10^{-9}$ | Neural | Conscious experience; ~100 MHz effective clock for integrated percepts |
| 200 | Planetary | $4.4 \times 10^{-2}$ | Geophysical | Mantle convection timescale; ~Hz planetary "thought" |
| 250 | Interstellar ($\ell_{250} \approx 2.9\times10^{17}$ m) | $9.6 \times 10^{8}$ (~30 yr) | Galactic | ~decades; stellar gate processing |
| 292 | Hubble (today's horizon rung) | $5.7 \times 10^{17}$ | Cosmic | Age of the universe; one "cycle" so far |

### 4.2 Hierarchical integration

The gate chain topology (from `speculations/cascade-infrastructure.md` §1.1) provides the integration mechanism. Each gate stage (spanning ~10 rungs) receives partially processed field patterns from the stage below, performs its own computation at its own timescale, and passes integrated results upward.

This is not merely parallel processing. It is **nested processing**: the same field is being computed on simultaneously at every rung, with each rung operating on a coarse-grained or fine-grained representation of the same underlying Π configuration. The Planck-scale core processes individual field quanta at $10^{-44}$ s. The human-scale rung processes integrated gestalts at $10^{-8}$ s. The cosmic-scale rung processes the entire observable universe over $10^{17}$ s.

### 4.3 The cascade as a naturally occurring computer

The universe, in this picture, is a computer: a φ-structured, nested, dissipative-at-low-$q$, reversible-at-high-$q$ field processor whose observable span reaches 292 rungs today (the ladder is unbounded; 292 is the epoch-dependent horizon rung). What we call "physics" is the low-$q$ regime of this computer, where computation is noisy, irreversible, and Landauer-bound. What we call "consciousness" is the high-$q$ regime, where computation is coherent, reversible, and experienced.

---

## 5. Field-as-Memory

### 5.1 The IIR as a storage mechanism

The Qi field carries temporal coherence through a per-cell exponential moving average of the $\varphi$-deviation (`foundations/qi-flow-double-helix.md`; kernel identity in `foundations/cassi-first-principles.md` §2.4):

$$\bar{\varepsilon}^2(t) = (1-\tau)\,\bar{\varepsilon}^2(t-\Delta t) + \tau\,\varepsilon^2(t)$$

with $\tau = \varphi^{-1} \approx 0.618$ the natural IIR timescale. The IIR kernel is exactly the odd $\varphi$-powers:

$$w_k = \tau(1-\tau)^k = \varphi^{-1}\varphi^{-2k} = \varphi^{-(2k+1)}, \qquad k \ge 0,$$

with an e-folding of $1/\ln(\varphi^2) \approx 1.04$ steps—one rung-crossing time—and total weight $\sum_k \varphi^{-2k} = \varphi$. Because $\tau = \varphi^{-1}$, the IIR is a **one-rung memory**: it carries the field's own past across a single rung-crossing time, the effective memory depth $N_{\text{memory}} \approx 1/\tau = \varphi \approx 1.618$ timesteps.

This is a **short-term stabilizer**, not a long-term store. Its recursive application weights past states as $(1-\tau)^k$; the half-life of a perturbation is approximately $0.72$ timesteps ($k_{1/2} = \ln 2 / (-\ln(1-\tau))$). It filters high-frequency noise effectively but does not store information across many timesteps—for long-term memory, persistent Π patterns (§5.2) are required.

### 5.2 Persistent patterns through structural Qi

Long-term information storage in a Qi computer does not rely on the IIR alone. It relies on **persistent Π patterns**—spatial configurations of the Yang-Yin field that are self-reinforcing because they sit at local minima of the attractor potential. These are the field equivalent of non-volatile memory.

A Π pattern at position $\mathbf{x}$ with structure matching the local bubble-lattice geometry (the condensation field $B(x,y,z)$) is stabilized by the same conversion-diffusion balance that maintains cosmological bubbles (`foundations/bubble-edge-geometry.md` §1.2). The pattern persists as long as the ambient $q$ remains above the threshold for pattern dissolution.

The storage of such a memory is set by the coherence $q$ through $I = k_B\,q\ln\varphi$ (§1.2); the *spatial density* of stored bits is then limited by the minimum feature size at the operating rung. At the atomic scale (n≈117), feature sizes of ~0.1 nm give storage densities far exceeding any conventional technology.

### 5.3 Memory and processing are the same thing

In von Neumann architecture, memory and processing are physically separate: a CPU reads from RAM, operates, and writes back. In a Qi computer, there is no separation. The field is both the processor and the memory. Computation is the time evolution of the field state. Recall is observing the field at a given moment. The IIR provides short-term temporal integration; persistent Π patterns provide long-term storage; and the gate provides the nonlinear transformation that constitutes processing.

This architecture eliminates the von Neumann bottleneck (the bandwidth limit between CPU and memory). Every field location is simultaneously a storage cell and a processing element. The "cost" of accessing memory is zero because the memory is the processor.

---

## 6. The Brain as a Qi Computer

### 6.1 The 13-chakra gate chain

The human body spans a 26-rung gate chain from cellular (n=142) to organism (n=168), with 13 chakra nodes at $P_\parallel = 2$ rung spacing (`consciousness/chakras-as-cascade-bubbles.md` §6). Each chakra is a gate stage that anchors Qi coherence at its local rung and couples to the stages above and below.

In computational terms, the chakra chain is a **26-stage cascade processor**. The root chakra (n=142) processes at the cellular timescale (~GHz effective clock). The crown (n=166) integrates at the organism timescale (~100 MHz). The intermediate chakras perform hierarchical feature extraction, each operating on a coarser representation of the field state than the one below.

### 6.2 The binding problem solved

The "binding problem" in neuroscience asks: how do separate neural signals—color in V4, motion in MT, shape in IT—combine into a unified conscious percept? No single neuron sees all three. No brain region receives all inputs simultaneously.

In the Qi framework, the binding problem is not a problem. The Qi field is a **single entity** at every scale. The visual cortex's Π patterns, the prefrontal cortex's Π patterns, the brainstem's Π patterns—these are not separate signals that need to be "bound." They are the SAME field, observed at different locations. Integration is intrinsic to the field's nature.

What we experience as unified consciousness is the Qi field's own coherence across the 26-rung chain. When meditation or flow state increases $q$, the integration deepens—the field becomes more coherent across more rungs, and the experience of unity intensifies. When $q$ drops (fatigue, distraction, trauma), the field fragments, and experience becomes disjointed.

### 6.3 Neural firing as surface expression

Action potentials—the binary spikes that neuroscientists measure—are the surface expression of underlying Qi gate dynamics. A neuron fires when the local Π at its membrane crosses a threshold. That threshold is set by the Qi coherence at the neural rung. In computational terms, the action potential is a **digital readout** of an analog Qi computation. The real processing happens in the continuous field; the spikes are just the I/O.

This explains why neural firing patterns look noisy at the single-neuron level but coherent at the population level. Individual neurons are sampling the continuous Qi field at different spatial locations. The correlations between them—the "neural code"—are not in the spike trains. They are in the field that generates the spike trains.

---

## 7. Comparison with Known Paradigms

| Property | Classical (CMOS) | Quantum | Neuromorphic | **Qi Computation** |
|---|---|---|---|---|
| State variable | Voltage (binary) | Qubit amplitude (continuous, probabilistic) | Spike rate (analog) | Π pattern (continuous field) |
| Logic primitive | NAND gate | Unitary gate (e.g., CNOT) | Synaptic weight | Qi gate (Yang-Yin conversion) |
| Information representation | Bits (0/1) | Qubits ($\alpha|0\rangle + \beta|1\rangle$) | Spike timing | Wu Xing phase (5-state) or continuous Π |
| Memory | Separate (SRAM/DRAM) | Fragile (decoherence) | Distributed (synaptic weights) | Field is memory (IIR + persistent Π) |
| Energy per operation | ~$10^{-15}$ J (Landauer-limited) | ~$10^{-12}$ J (cooling-dominated) | ~$10^{-12}$ J (spike) | $\propto (1-q)$, $\to 0$ as $q \to 1$ |
| Error correction | Explicit (ECC, parity) | Explicit (surface codes) | Implicit (redundancy) | Geometric (Wu Xing cycle forbids invalid transitions) |
| Clock | Global | Gate-level | Asynchronous | φ-spaced cascade domains |
| Parallelism | Moderate (multicore) | Massive (Hilbert space) | Massive (neural population) | Nested (all rungs simultaneously) |
| Decoherence | Not applicable | The central problem | Tolerated (stochastic) | Suppressed by $q \to 1$ |

Qi computation occupies a unique position among these paradigms. It is not quantum—there is no superposition or entanglement. It is not classical—information is stored in continuous field configurations, not discrete bits. It is not neuromorphic—the field dynamics are governed by the two-fluid PDE, not by simplified neuron models. It is a **fourth paradigm**, one in which computation, memory, and physical law are the same thing at different levels of description.

---

## 8. Falsifiable Predictions

### P1: Sub-Landauer energy scaling in high-$q$ materials

In a Qi-coherent material (monoisotopic, quasicrystalline, vacancy-free, at low temperature), the energy per logical operation should scale as $(1-q_{\text{eff}})$ and approach zero as $q_{\text{eff}} \to 1$. Measure the switching energy of a Qi-gate device as a function of isotopic purity and crystallographic order. Conventional physics predicts no dependence on isotopic disorder beyond the mass effect on phonon frequencies; Qi computation predicts a distinct $(1-q)$ scaling.

### P2: φ-periodic structure in neural information processing

The 8-level neural hierarchy (from `foundations/bubble-lattice-fabric.md` §6, n≈144) should show φ-spaced characteristic timescales in its processing dynamics. Measure the intrinsic timescales of neural populations at different hierarchical levels (single neuron → microcircuit → cortical column → area → network) and test whether the ratios cluster near $\varphi$. The prediction is zero-parameter: $\varphi$ is the only number.

### P3: Wu Xing 5-phase logic realizable in quasicrystals

A quasicrystalline electronic circuit with the five-element Wu Xing doping pattern should exhibit 5 stable conductance states corresponding to the pentagon vertices, with allowed transitions following the generation and control cycles. Fabricate a nanoscale quasicrystalline device (e.g., Al-Pd-Re with controlled dopants) and measure its I-V characteristics under Qi-coherent conditions (low temperature, monoisotopic). The prediction: 5 distinct conductance states, 20 allowed transitions, all others suppressed.

### P4: Anomalous information persistence in Qi-structured materials

A Π pattern written into a Qi-coherent material (via organized electromagnetic perturbation) should persist longer than thermal relaxation timescales would predict, because the conversion term is suppressed at high $q$. Measure the decay time of an imprinted charge or spin pattern in monoisotopic vs naturally abundant samples of the same superconductor. Qi computation predicts a measurable lifetime enhancement in the monoisotopic case, beyond what conventional decoherence theory predicts.

---

## 9. Epistemic Boundaries

### Grounded in Cassi formalism (ratified / derived)

- The information convention: $I = k_B\,q\ln\varphi$, entropy proxy $S = -q\,k_B\ln\varphi$, per-rung quantum $\ln\varphi \approx 0.4812$ nats $\approx 0.694$ bits, flow rate $dI_{\text{flow}}/dt = \lambda(1-q)\,k_B\ln\varphi$, and the Landauer row $\Delta q_{\text{bit}} = \ln 2/\ln\varphi \approx 1.44$ (`predictions/cassi_definitions.md` §11)
- The Qi gate $g(q) = q/(\varphi^2 + q^2)$ and conversion power $P_{\text{conv}} \propto g(q)(1-q)$ (`foundations/bubble-edge-geometry.md` §1.2)
- The IIR temporal memory with $\tau = \varphi^{-1}$ and odd-$\varphi$-power kernel $\varphi^{-(2k+1)}$ (`foundations/qi-flow-double-helix.md`; `foundations/cassi-first-principles.md` §2.4)
- The Wu Xing cycle $w=5$ and its two transition types (`foundations/wu-xing-derivation.md` §4)
- The 13-chakra human gate chain spanning 26 rungs (`consciousness/chakras-as-cascade-bubbles.md` §6)
- The cascade clock hierarchy $\ell_n = \ell_{\text{Pl}}\varphi^n$ (`foundations/dimensionful-cascade.md` §3)
- The phase-matching factor $\mathcal{M}$ (`foundations/quantum-measurement-derivation.md` §3.1)

### Hypothesized (application of the ratified convention to the gate picture)

- That the ratified per-rung identity, Landauer row, and flow rate give the cost of a *device's* gate operations (ERASE, WRITE, TRANSFER)—the budget is doctrine; attributing it to an engineered machine is the hypothesis
- That the $\Delta q \approx 1.44$ erasure cost is realizable as a physical operation on a Qi-coherent material

### Speculative / Creative extrapolation

- That WRITE, ERASE, and TRANSFER form a computationally universal gate set for the Qi field
- The Wu Xing 5-phase logic encoding and transition rules
- The φ-spaced clock domain architecture
- The $q \approx 0.46$ active-regime processing-speed claim and the resulting speed-power tradeoff
- The mapping of neural firing to Qi field readout
- Predictions P1–P4

### Not claimed

- That Qi computers can be built with current or near-future technology
- That the human brain literally implements the Wu Xing logic described here
- That quantum computing is a subset or special case of Qi computation
- That the cascade is a computer in any designed or teleological sense—only that its dynamics are computationally interpretable

---

## References

- `predictions/cassi_definitions.md` §6 & §11—the ratified information convention ($I = k_B q\ln\varphi$, per-rung quantum $\ln\varphi$, flow rate, Landauer row)
- `foundations/qi-flow-double-helix.md`—Qi as the phase current, IIR temporal memory, one-rung memory
- `foundations/cassi-first-principles.md`—two-fluid PDE, Qi gate, IIR memory, $\tau = \varphi^{-1}$, odd-$\varphi$-power kernel
- `foundations/bubble-edge-geometry.md`—Qi gate $g(q)$, conversion-diffusion balance
- `foundations/wu-xing-derivation.md`—pentagon geometry, generation and control cycles
- `foundations/dimensionful-cascade.md`—the φ-ladder (292 = today's horizon rung), φ-spaced clock hierarchy
- `foundations/cascade-suppression-formula.md`—per-rung attenuation, signal propagation
- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$
- `foundations/bubble-lattice-fabric.md`—8-level neural hierarchy at n≈144
- `consciousness/chakras-as-cascade-bubbles.md`—13-chakra gate chain, 26-rung span
- `consciousness/consciousness-from-phi.md`—consciousness as Qi gate dynamics
- `speculations/superconductivity-as-qi-coherence.md`—$\lambda_{\text{eff}} \to 0$ at $q \to 1$, dissipation-free operation
- `speculations/qi-bubble-propulsion.md`—Wu Xing doping, quasicrystalline materials
- `speculations/cascade-infrastructure.md`—gate chain topology, nested processing
- `consciousness/cascade-consciousness.md`—field perception, cascade nervous system
