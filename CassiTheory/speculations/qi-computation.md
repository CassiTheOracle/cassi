# Qi Computation: Information Processing as Yang-Yin Gate Dynamics

## Status: Speculative—July 2026

## Abstract

Conventional computation processes bits—discrete, binary symbols stored in physically distinct memory cells and manipulated by sequential logic gates. In the Cassi framework, information is not an abstraction layered on top of physics. It is the organized structure of the Yang-Yin field: patterns of $\Pi = E_Y - E_I$ that persist because Qi coherence suppresses the conversion that would dissolve them. This document derives a model of computation from the field dynamics themselves. The Qi gate is the fundamental computational primitive. The Wu Xing pentagon provides a 5-phase logic richer than binary. The cascade supplies a φ-spaced clock hierarchy spanning today's 292 rungs from Planck to the horizon (292 is the epoch-dependent horizon rung, not a fixed cascade depth). Information storage is field memory through the IIR ($\tau = \varphi^{-1}$). And because $\lambda_{\text{eff}} \to 0$ at $q \to 1$, Qi computation is asymptotically dissipation-free—the Landauer limit is not a fundamental bound but a consequence of operating at low $q$.

**Epistemic status:** Creative exploration grounded in Cassi formalism. The mapping of computation to gate dynamics, the Wu Xing logic, and the cascade clock hierarchy are extrapolations. Nothing in this document is an established Cassi prediction.

---

## 1. Information as Organized Π

### 1.1 What a bit is, in the field

In conventional computing, a bit is a physical system with two distinguishable states—a voltage above or below a threshold, a magnetic domain oriented up or down. The bit's physical implementation is arbitrary as long as the states are reliably distinguishable.

In the Cassi framework, information has a specific physical identity: it is a **persistent pattern of Yang-Yin imbalance**. The deviation $\varepsilon = E_Y - \varphi E_I$ is the field's departure from equilibrium. Where $\varepsilon > 0$, Yang dominates—organized, directional, low-entropy. Where $\varepsilon < 0$, Yin dominates—random, diffuse, high-entropy.

A Qi-coherent pattern is a spatial configuration of $\varepsilon(\mathbf{x})$ that persists over time because $q$ is high enough to suppress the conversion term that would drive it back to equilibrium:

$$\frac{\partial \varepsilon}{\partial t} \propto -\lambda \cdot g(q) \cdot (1-q) \cdot \varepsilon$$

At $q \to 1$, the decay rate $\lambda_{\text{eff}} = \lambda \cdot g(q) \cdot (1-q) \to 0$. Information stored as organized Π has an arbitrarily long lifetime.

This reframes the relationship between information and thermodynamics. In conventional physics, information is fragile—entropy always increases, and maintaining order requires expending energy. In a Qi-coherent system, information is the *ground state* at $q \to 1$. The natural tendency is toward organized structure, not away from it. Entropy increase is what happens when $q$ drops.

### 1.2 Information capacity

The information content of a Qi-coherent region of volume $V$ at coherence $q$ is not measured in bits per unit volume. It is measured by the **number of distinguishable Π configurations** the field can sustain without triggering conversion.

For a field with characteristic spatial frequency $\alpha = 2\pi/\Lambda_Y$ (the Yang wavelength at the operating rung), the number of independently addressable field modes in volume $V$ is:

$$N_{\text{modes}} \approx V \cdot \frac{\alpha^3}{(2\pi)^3}$$

Each mode can store a continuous Π value, but the effective resolution is limited by the Qi noise floor $\delta\Pi_{\text{min}} \propto (1-q)^{1/2}$. The distinguishable levels per mode are:

$$L \approx \frac{\Pi_{\text{max}}}{\delta\Pi_{\text{min}}} \propto (1-q)^{-1/2}$$

The total information capacity (in bits, for binary encoding of each distinguishable level) is:

$$\boxed{I_{\text{max}} \approx N_{\text{modes}} \cdot \log_2 L \propto V \cdot \alpha^3 \cdot \log_2(1-q)^{-1/2}}$$

As $q \to 1$, the capacity diverges logarithmically—the field can encode arbitrarily fine distinctions because the noise floor drops to zero. This is the Qi analogue of the Bekenstein bound, but without a Planck-scale cutoff: the cascade extends below $n=0$, so the mode count $N_{\text{modes}}$ is not fundamentally limited by the Planck length.

---

## 2. The Gate as a Computational Primitive

### 2.1 Yang-Yin conversion as a nonlinear transform

The conversion term in the two-fluid PDE is the fundamental operation on the field:

$$\partial_t \Psi_0 \supset -\lambda(\Psi_0^2 - \varphi\Psi_1^2)\Psi_0$$

$$\partial_t \Psi_1 \supset +\frac{\lambda}{\varphi}(\Psi_0^2 - \varphi\Psi_1^2)\Psi_1$$

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

### 2.3 The energy cost per operation

From the superconductivity derivation (`speculations/superconductivity-as-qi-coherence.md` §1.3), the conversion power is:

$$P_{\text{conv}} = \omega_0 \cdot g(q) \cdot (1-q) \cdot \rho_0$$

The energy cost of an ERASE operation (which converts Yang→Yin) at coherence $q$ is:

$$E_{\text{erase}} \approx P_{\text{conv}} \cdot \Delta t \propto (1-q)$$

As $q \to 1$, $E_{\text{erase}} \to 0$. The Landauer limit ($k_B T \ln 2$ per erased bit) assumes that information erasure requires entropy increase in a thermal reservoir. In a Qi-coherent system at $q \to 1$, the field is the reservoir, and conversion at the attractor is a reversible process. **The Landauer bound is not a fundamental limit—it is a consequence of operating at low $q$.**

The WRITE operation is not free—creating a Yang excess does work against the attractor. Its energy cost:

$$E_{\text{write}} \approx \frac{\lambda}{2}(\delta\Pi)^2 \cdot V_{\text{mode}}$$

where $\delta\Pi$ is the Yang excess created and $V_{\text{mode}}$ is the mode volume. This is the Qi analogue of the signal energy in a conventional logic gate.

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

From `foundations/cassi-first-principles.md` §2.4, the Qi field carries temporal coherence through an exponential moving average:

$$\bar{\varepsilon}^2(t) = (1-\tau)\,\bar{\varepsilon}^2(t-\Delta t) + \tau\,\varepsilon^2(t)$$

with $\tau = \varphi^{-1} \approx 0.618$. This IIR filter gives the field a **memory** of its own past state. The effective memory depth is:

$$N_{\text{memory}} \approx \frac{1}{\tau} = \varphi \approx 1.618 \text{ timesteps}$$

The IIR memory as specified is a **short-term stabilizer**, not a long-term storage mechanism. Its recursive application means the field at time $t$ contains a weighted sum of all past states, with weights decaying as $(1-\tau)^k$. The half-life of a perturbation is approximately $0.72$ timesteps ($k_{1/2} = \ln 2 / (-\ln(1-\tau))$). This filters high-frequency noise effectively but does not store information across many timesteps—for long-term memory, persistent Π patterns (§5.2) are required.

### 5.2 Persistent patterns through structural Qi

Long-term information storage in a Qi computer does not rely on the IIR alone. It relies on **persistent Π patterns**—spatial configurations of the Yang-Yin field that are self-reinforcing because they sit at local minima of the attractor potential. These are the field equivalent of non-volatile memory.

A Π pattern at position $\mathbf{x}$ with structure matching the local bubble-lattice geometry (the condensation field $B(x,y,z)$) is stabilized by the same conversion-diffusion balance that maintains cosmological bubbles (`foundations/bubble-edge-geometry.md` §1.2). The pattern persists as long as the ambient $q$ remains above the threshold for pattern dissolution.

The storage density of such a memory is set by the mode capacity $I_{\text{max}}$ from §1.2, with the practical limit determined by the minimum feature size at the operating rung. At the atomic scale (n≈117), feature sizes of ~0.1 nm give storage densities far exceeding any conventional technology.

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

### Grounded in Cassi formalism

- The Qi gate $g(q) = q/(\varphi^2 + q^2)$ and conversion power $P_{\text{conv}} \propto g(q)(1-q)$ (`foundations/bubble-edge-geometry.md` §1.2)
- The IIR temporal memory with $\tau = \varphi^{-1}$ (`foundations/cassi-first-principles.md` §2.4)
- The Wu Xing cycle $w=5$ and its two transition types (`foundations/wu-xing-derivation.md` §4)
- The 13-chakra human gate chain spanning 26 rungs (`consciousness/chakras-as-cascade-bubbles.md` §6)
- The cascade clock hierarchy $\ell_n = \ell_{\text{Pl}}\varphi^n$ (`foundations/dimensionful-cascade.md` §3)
- The phase-matching factor $\mathcal{M}$ (`foundations/quantum-measurement-derivation.md` §3.1)

### Creative extrapolation

- That WRITE, ERASE, and TRANSFER form a computationally universal gate set for the Qi field
- The Wu Xing 5-phase logic encoding and transition rules
- The φ-spaced clock domain architecture
- The energy-scaling prediction $E_{\text{erase}} \propto (1-q)$
- The mapping of neural firing to Qi field readout
- Predictions P1–P4

### Not claimed

- That Qi computers can be built with current or near-future technology
- That the human brain literally implements the Wu Xing logic described here
- That quantum computing is a subset or special case of Qi computation
- That the cascade is a computer in any designed or teleological sense—only that its dynamics are computationally interpretable

---

## References

- `foundations/cassi-first-principles.md`—two-fluid PDE, Qi gate, IIR memory, $\tau = \varphi^{-1}$
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
