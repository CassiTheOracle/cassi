# Qi Computation: Information Processing as Yang-Yin Gate Dynamics

## Status: Hypothesized (aggregate information-budget application and conditional device/transport mappings) / Speculative (gate-set universality, Wu Xing logic, cascade clock, brain mapping, predictions)—August 2026

## Abstract

Conventional computation processes bits—discrete, binary symbols stored in physically distinct memory cells and manipulated by sequential logic gates. In the Cassi framework, the definitions document a local information bookkeeping quantity $I_{\mathrm{cell}} = k_B\,q\ln\varphi$ associated with one normalized coherence cell. A device or region must aggregate that quantity over cells or rungs, $I_\Omega = k_B\ln\varphi\sum_{i\in\Omega}q_i$, because one bounded $q$ cell carries less than one bit. The canonical two-fluid PDE supplies density conversion with openness $(1-q)$; $g(q)$ is a separate asserted optional transmission multiplier. This document builds a Speculative model of computation on those conventions and on the field dynamics. Gate I/O is written in the canonical densities $E_Y,E_I$; the positive-root lift $\Psi^{(+)}$ appears only for coordinate diagnostics. The Wu Xing pentagon, cascade clocks, nested runtimes, and device interpretations remain extrapolations beyond the solver.

**Epistemic status:** The local information convention and its flow expression are used here as a **Hypothesized** bookkeeping application. The Landauer row is a dimensionless aggregate $q$-budget mapping, not a proof that the canonical PDE supplies an irreversible physical cost or an energy-dissipation law. The function $g(q)$ is an **Asserted** optional transmission multiplier, while $\tau=\varphi^{-1}$ is a solver timescale convention. The gate set (WRITE/ERASE/TRANSFER), Wu Xing logic, cascade clock hierarchy, and neural mapping remain **Speculative/Creative** extrapolations. Nothing in this document claims an established Cassi prediction for a computable machine.

---

## 1. Information as Organized Density Patterns

### 1.1 What a bit is, in the field

In conventional computing, a bit is a physical system with two distinguishable states—a voltage above or below a threshold, a magnetic domain oriented up or down. The bit's physical implementation is arbitrary as long as the states are reliably distinguishable.

In this speculative application, the definitions document maps local Qi coherence to an information bookkeeping quantity: the entropy proxy is $S_{\mathrm{cell}}=-q\,k_B\ln\varphi$, and the corresponding entropy deficit relative to $q=0$ is

$$S_{\mathrm{cell}}=-q\,k_B\ln\varphi,\qquad I_{\mathrm{cell}}=S_{\mathrm{cell}}(q{=}0)-S_{\mathrm{cell}}(q)=+q\,k_B\ln\varphi.$$

A normalized cell at coherence $q$ therefore carries the convention-level amount $I_{\mathrm{cell}}=k_B\,q\ln\varphi$; this is a local budget, not a whole-device capacity. For a region $\Omega$ with cells or rungs indexed by $i$, define the aggregate dimensionless coherence budget

$$Q_\Omega\equiv\sum_{i\in\Omega}q_i,\qquad I_\Omega=k_B\,Q_\Omega\ln\varphi.$$

The canonical density residual is $\varepsilon=E_Y-\varphi E_I$. In the conversion-only sector of the two-fluid PDE,

$$\left.\frac{\partial\varepsilon}{\partial t}\right|_{\mathrm{conv}}=-\lambda(1-q)(1+\varphi)\,\varepsilon.$$

If the asserted optional transmission multiplier $g(q)=q/(\varphi^2+q^2)$ is adopted, a conditional model may multiply the right-hand side by $g(q)$; the canonical conversion coefficient contains $(1-q)$ only. At $q\to1$, conversion changes an existing density pattern slowly, but high $q$ does not itself create order or supply a formation mechanism. Advection, diffusion, sources, and any device closure determine whether a pattern forms or persists.

The entropy statement is a convention-level mapping: higher $q$ lowers the proxy $S_{\mathrm{cell}}$ and raises the local bookkeeping stock, while the conversion channel is simultaneously suppressed. No thermodynamic monotonicity theorem or physical energy cost follows without an additional closure.

### 1.2 Information capacity

Information capacity is bounded locally by the coherence scalar and scales regionally with the number of available cells or rungs:

$$\boxed{I_{\mathrm{cell}}=k_B\,q\ln\varphi}\qquad\text{and}\qquad
\boxed{I_\Omega=k_B\ln\varphi\sum_{i\in\Omega}q_i}.$$

The per-cell maximum is $\ln\varphi\approx0.4812$ nats, or $\log_2\varphi\approx0.6942$ bits per $k_B$ unit. A single cell therefore carries less than one bit even at $q=1$. A one-bit aggregate requires

$$Q_\Omega\ge\frac{\ln2}{\ln\varphi}\approx1.4404.$$

Because every local $q_i$ is bounded by $0\le q_i\le1$, that budget requires at least two fully coherent cells or rungs, or more generally $N_\Omega\bar q_\Omega\ge1.4404$. The value $1.4404$ is an aggregate budget in dimensionless $q$-cell/rung units; it is not a permissible single-cell $\Delta q$.

Spatial mode density therefore matters by determining how many cells or rungs a pattern occupies, while $q_i$ supplies each cell's normalized coherence stock. This is the information convention used by the speculative device model, not a derived hardware capacity law.

The openness $(1-q)$ belongs to the flow, not the stored stock. Per normalized cell, the convention-level information-flow proxy is

$$\frac{dI_{\mathrm{flow,cell}}}{dt}=\lambda(1-q)\,k_B\ln\varphi.$$

For a region, an aggregate proxy is obtained by summing the cell rates. These expressions do not by themselves specify a physical throughput, transport mechanism, or energy conversion.

---

## 2. The Gate as a Computational Primitive

### 2.1 Yang-Yin conversion as a nonlinear transform

The conversion term in the two-fluid PDE is the fundamental operation on the field:

$$\partial_t E_Y \supset -\lambda(1-q)(E_Y - \varphi E_I)$$

$$\partial_t E_I \supset +\lambda(1-q)(E_Y - \varphi E_I)$$

Given an input canonical density state $(E_Y^{\mathrm{in}},E_I^{\mathrm{in}})$ at time $t$, the conversion sector evolves the densities for a duration $\Delta t$ to produce $(E_Y^{\mathrm{out}},E_I^{\mathrm{out}})$. If a two-component coordinate is useful, apply the exact positive-root lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ after the density update; this lift is a coordinate representation of the density state. This is a continuous state-dependent transformation—an analogy to a transistor, not a derived hardware primitive.

The gate has three useful regimes, but only the $(1-q)$ coefficient is canonical:

| Regime | $q$ | Canonical conversion coefficient | Optional $g(q)(1-q)$ | Interpretation |
|---|---|---|---|---|
| **Idle** | $q \to 1$ | $\to 0$ | $\to 0$ | Conversion is suppressed; an existing density pattern changes slowly through this channel. |
| **Optional active** | $q \approx 0.46$ | $\approx 0.54$ | Maximum ($\approx 0.088$) | The asserted $g$-weighted transmission proxy peaks here; canonical conversion remains governed by $(1-q)$. |
| **Low-coherence** | $q \to 0$ | $\to 1$ | $\to 0$ | Canonical conversion is maximally open, while the optional $g$ multiplier vanishes. |

The function $g(q)=q/(\varphi^2+q^2)$ is an **Asserted** optional transmission multiplier. At $q\to0$, $g(q)$ vanishes but the canonical conversion term still carries $(1-q)\to1$; at $q\to1$, the canonical openness vanishes. If the optional multiplier is adopted, the product $g(q)(1-q)$ peaks near $q\approx0.46$.

The state-dependent coefficient can support a computational analogy, but claims that intermediate $q$ supplies gain, amplification, or a transistor-like response are **Speculative**. The canonical PDE supplies density relaxation; a universal logic law would require an added device model.

### 2.2 A proposed gate vocabulary

The following operations are a Speculative instruction vocabulary, not a canonical or established universal gate set:

**WRITE (Yang injection):** Apply a specified organized perturbation that produces a local density change such as $\delta E_Y>0$ at position $\mathbf{x}$. This is the field analogue of setting a bit to 1. A coupling condition such as $\mathcal{M}\approx1$ is a Hypothesized application of the phase-matching model, not a guaranteed input channel.

**ERASE (gated conversion):** Use the canonical conversion sector at position $\mathbf{x}$ to relax the residual $\varepsilon=E_Y-\varphi E_I$ toward zero. The attractor is $E_Y=\varphi E_I$, and conversion redistributes the two densities while conserving their conversion-sector sum. Temporarily reducing $q$ raises the canonical coefficient $(1-q)$, but treating that maneuver as a controllable reset protocol is Hypothesized.

**TRANSFER (conditional lift diagnostic):** A proposed transfer operation may monitor the exact positive-root lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ and its coordinate diagnostic

$$
\mathbf{J}_\Psi^{(+)}
=\Psi_0^{(+)}\nabla\Psi_1^{(+)}
-\Psi_1^{(+)}\nabla\Psi_0^{(+)}
=\rho\nabla\theta_\Psi^{(+)}.
$$
Here $\rho=E_Y+E_I$ and $\theta_\Psi^{(+)}=\operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y})$ are the polar coordinates of the positive-root lift.

$\mathbf{J}_\Psi^{(+)}$ is a coordinate diagnostic of the positive-root lift. Assigning it a physical-current or pattern-transport interpretation requires a separately specified constitutive transport law, shared advection field, or activated potential-relative drift; that extension remains **Hypothesized**.

The three labels are useful for the simulation metaphor, but their computational universality and any Boolean-circuit compilation remain **Speculative** applications beyond the two-fluid PDE.

### 2.3 The cost of each operation

The information convention supplies a dimensionless bookkeeping budget for a normalized cell or aggregate region; it does not assign a proven physical cost to each gate operation.

**ERASE—the aggregate Landauer row.** For a region $\Omega$, one bit corresponds to an aggregate coherence budget

$$\Delta Q_{\mathrm{bit}}=\frac{\ln2}{\ln\varphi}\approx1.4404\qquad\text{(dimensionless $q$-cell/rung units)}.$$

This is the same number as the information-convention mapping in `predictions/cassi_definitions.md` §11. Because $0\le q_i\le1$, it cannot be supplied by one cell; at least two fully coherent cells or rungs are needed, and a real device would require $N_\Omega\bar q_\Omega\ge1.4404$. The row is not a single-cell $\Delta q$ and does not prove an irreversible field operation.

Standard thermodynamics states that erasing one bit dissipates $E=k_BT\ln2$ into a reservoir. In this document, applying that analogy to density conversion is **Hypothesized**: the canonical PDE relaxes $\varepsilon$ toward the $\varphi$-line but supplies no logical-state map, reservoir, or theorem that the operation is irreversible. A physical energy cost requires an additional constitutive and thermodynamic closure.

**WRITE and conditional TRANSFER—the flow budget.** The per-cell information-flow proxy remains

$$\frac{dI_{\mathrm{flow,cell}}}{dt}=\lambda(1-q)\,k_B\ln\varphi.$$

An aggregate device proxy is the sum of these rates over its cells or rungs. High $q$ stores more convention-level information per cell while suppressing conversion, so a model may associate it with slower processing; this is not a universal throughput law. At $q\approx0.46$, the optional $g(q)(1-q)$ proxy is maximal, whereas canonical $(1-q)$ is largest as $q\to0$. The optional expression $P_{\mathrm{conv}}=\omega_0 g(q)(1-q)\rho_0$ (`speculations/superconductivity-as-qi-coherence.md` §1.3) is a conditional model input, not a mechanical driver established by the canonical PDE.

---

## 3. Wu Xing 5-Phase Logic

### 3.1 The pentagon as a state machine

The Wu Xing pentagon (`foundations/wu-xing-derivation.md` §4) has five vertices—Wood, Fire, Earth, Metal, Water—with two transition cycles:

- **Generation ($\rightarrow$):** Wood $\rightarrow$ Fire $\rightarrow$ Earth $\rightarrow$ Metal $\rightarrow$ Water $\rightarrow$ Wood. Each step feeds the next; the cycle is constructive and phase-coherent.
- **Control ($\dashrightarrow$):** Wood $\dashrightarrow$ Earth $\dashrightarrow$ Water $\dashrightarrow$ Fire $\dashrightarrow$ Metal $\dashrightarrow$ Wood. Each step restrains the next; the cycle is regulative.

In the proposed logic mapping, a computational state would be the current Wu Xing phase assigned to a field location. A transition would be a gate operation that advances that assigned phase by one vertex along either the generation or control cycle; the canonical solver itself evolves $(E_Y,E_I)$, not a Wu Xing phase variable.

### 3.2 Encoding

Under this speculative encoding, five phases have a maximum uniform-code
information content of $\log_2 5 \approx 2.32$ bits per Wu Xing "digit" (a
*wu*). A physical or nonuniform code need not attain this maximum. One wu
carries more than two binary bits. The
pentagon could supply a proposed transition-validity check:

The 5 vertices × 4 proposed transitions (generation forward, generation backward, control forward, control backward) = 20 candidate operations. An operation outside these paths would be labeled a phase error in this model, but detection requires a physical state readout and geometry-enforcing device; the canonical PDE does not provide zero-overhead error correction.

### 3.3 Computation by phase advance

A computation in Wu Xing logic is a sequence of pentagon-phase advances. An addition of two numbers, for instance, might involve:

1. Encode operands as Wu Xing phase vectors
2. Align phases via control-cycle adjustments (Earth restrains Water, etc.)
3. Advance through the generation cycle a number of steps equal to the carry value
4. Read out the result as the final phase configuration

The specific mapping of arithmetic to Wu Xing transitions is an open design problem—this is the Qi equivalent of designing an instruction set architecture.

### 3.4 Physical implementation

A Wu Xing logic device is a conditional material mapping, not a consequence of the pentagon geometry. A quasicrystalline implementation would first have to define how the five-element doping pattern maps onto the canonical density state $(E_Y,E_I)$ and how an external perturbation couples to a selected transition. The phase-matching factor $\mathcal{M}$ and any such material response remain **Hypothesized**.

For an isolated conversion residual, the canonical relaxation timescale is

$$t_{\varepsilon,\mathrm{conv}}\sim\frac{1}{\lambda(1-q)(1+\varphi)}.$$

If the asserted optional multiplier $g(q)$ is adopted in a conditional transmission model, one may instead write

$$t_{\varepsilon,\mathrm{conv}}^{(g)}\sim\frac{1}{\lambda g(q)(1-q)(1+\varphi)}.$$

The optional $g(q)(1-q)$ factor is nonmonotonic and largest near $q\approx0.46$,
but this does not establish a maximum clock speed for the canonical PDE. At
$q\to1$, conversion is suppressed; at $q\to0$, canonical conversion is most
open while the optional $g$ factor vanishes. Any speed-power tradeoff or energy
interpretation remains **Speculative/Hypothesized** and requires a device
closure.

---

## 4. The Cascade as a Clock Hierarchy

### 4.1 φ-spaced clock domains

Every cascade rung has a characteristic timescale:

$$t_n = \frac{\ell_n}{c} = \frac{\ell_{\text{Pl}} \cdot \varphi^n}{c}$$

The ratio of timescales between adjacent rungs is:

$$\frac{t_{n+1}}{t_n} = \varphi \approx 1.618$$

The proposed cascade-spanning computer would assign **$\varphi$-spaced clock domains**: each rung would operate at its assigned frequency, with the rung above running $\varphi$ times slower and integrating output from the rung below. This is a clock architecture imposed on the ladder, not a timing law of the canonical PDE.

| Rung $n$ | Scale | $t_n$ (seconds) | Clock domain | Computational role |
|---|---|---|---|---|
| 0 | Planck | $5.4 \times 10^{-44}$ | Quantum noise floor | Not directly accessible; sets the $\sigma$-regularized baseline |
| 95 | QCD | $3.85 \times 10^{-24}$ | Nuclear | Ultrafast parallel processing; immense parallelism in nuclear volume |
| 117 | Atomic | $1.52 \times 10^{-19}$ | Electronic | Conventional electronics operates here; single-rung domain |
| 136 | Visible light | $1.43 \times 10^{-15}$ | Optical | Photonic computation; inter-chip communication |
| 150 | Sub-millimeter ($\ell_{150} \approx 3.6\times10^{-4}$ m; cellular scale is rung 142) | $1.2 \times 10^{-12}$ | Biological | Cellular signal processing; ~GHz effective clock |
| 168 | Human | $6.94 \times 10^{-9}$ | Neural | Conscious experience; ~100 MHz effective clock for integrated percepts |
| 200 | Planetary | $3.38 \times 10^{-2}$ | Geophysical | Mantle convection timescale; ~Hz planetary "thought" |
| 250 | Interstellar ($\ell_{250} \approx 2.9\times10^{17}$ m) | $9.6 \times 10^{8}$ (~30 yr) | Galactic | ~decades; stellar gate processing |
| 291.54 | Observed present horizon estimate | $4.57 \times 10^{17}$ (about 14.5 Gyr) | Cosmic | Horizon-scale light-travel time; distinct from the 13.8 Gyr age estimate |
| 292 | Integer ladder rung adjacent to the present horizon | $5.7 \times 10^{17}$ (~18.1 Gyr) | Nominal cosmic | A ladder reference scale, not the present age |

### 4.2 Hierarchical integration

In the proposed architecture, the gate-chain topology (from `speculations/cascade-infrastructure.md` §1.1) would provide an integration mechanism. Each gate stage (spanning ~10 rungs) would receive partially processed density patterns from the stage below, perform its proposed computation at its assigned timescale, and pass an integrated result upward. The topology alone does not specify those couplings.

This is not merely parallel processing in the proposed architecture. The same density state $(E_Y,E_I)$ can be coarse-grained at different rungs, but a rule that each rung simultaneously computes an independent representation is a Speculative cascade interpretation. The Planck-scale, human-scale, and cosmic-scale processing roles listed here are model assignments, not consequences of the canonical PDE.

### 4.3 The cascade as a naturally occurring computer

The proposed computational reading treats the universe as a
$\varphi$-structured, nested field processor whose continuous horizon estimate
is near $n\approx291.54$; integer rung $292$ is a neighboring ladder scale.
The canonical conversion coefficient is more open at low $q$ and suppressed at
high $q$; calling those regimes noisy, irreversible, reversible, or
Landauer-bound requires additional dynamical and thermodynamic closures. The
consciousness interpretation is likewise speculative.

---

## 5. Field-as-Memory

### 5.1 The IIR as a storage mechanism

The optional solver closure carries temporal coherence through a per-cell exponential moving average of the density residual $\varepsilon$ (`foundations/qi-flow-double-helix.md`; kernel identity in `foundations/cassi-first-principles.md` §2.4):

$$\bar{\varepsilon}^2(t) = (1-\tau)\,\bar{\varepsilon}^2(t-\Delta t) + \tau\,\varepsilon^2(t)$$

With $\tau=\varphi^{-1}$ the IIR coefficient is an **Asserted solver convention**, not a derived natural physical timescale. The kernel identity

$$w_k = \tau(1-\tau)^k = \varphi^{-1}\varphi^{-2k} = \varphi^{-(2k+1)}, \qquad k \ge 0,$$

Under this solver convention, the normalized kernel has an e-folding of
$1/\ln(\varphi^2)\approx1.04$ steps and total weight
$\sum_{k=0}^{\infty}w_k=1$, while its unnormalized factors satisfy
$\sum_{k=0}^{\infty}\varphi^{-2k}=\varphi$. It can be described as a
**one-rung diagnostic memory** with effective depth
$N_{\text{memory}}\approx1/\tau=\varphi\approx1.618$ timesteps; this is a
property of the chosen closure, not a universal field-memory law.

This is a **short-term stabilizer** in the optional solver closure, not a long-term store. Its recursive application weights past states as $(1-\tau)^k$; the half-life of a perturbation is approximately $0.72$ timesteps ($k_{1/2}=\ln2/[-\ln(1-\tau)]$). It filters high-frequency noise effectively but does not store information across many timesteps; long-term storage would require persistent density patterns and an additional stability mechanism.

### 5.2 Persistent patterns through structural Qi

Long-term information storage in the proposed Qi computer would not rely on the IIR alone. It would require **persistent density patterns**—spatial configurations of $(E_Y,E_I)$ maintained by a specified balance of conversion, advection, diffusion, sources, and boundary conditions. The canonical fact that high $q$ suppresses conversion does not by itself make a pattern self-reinforcing or place it at a local minimum of a physical attractor potential.

A density pattern at position $\mathbf{x}$ that matches a hypothesized bubble-lattice geometry (the condensation field $B(x,y,z)$) may be modeled using the conversion-diffusion balance discussed in `foundations/bubble-edge-geometry.md` §1.2. Whether that balance stabilizes a memory, and for how long, is an application hypothesis rather than a solver result.

The information bookkeeping for such a memory is per cell and aggregates as $I_\Omega=k_B\ln\varphi\sum_iq_i$ (§1.2); the spatial density of stored bits therefore depends on the number and size of available cells as well as their coherence. At the atomic scale (n≈117), the proposed ~0.1 nm feature size is a device assumption, not a capacity derived from $q$ alone.

### 5.3 Memory and processing are the same thing

In a von Neumann architecture, memory and processing are physically separate. In the proposed Qi architecture, the same density field may serve as both medium and state: computation is time evolution, recall is observation, the IIR supplies short-term temporal integration, and persistent density patterns would supply long-term storage if their stability closure exists.

This is a Speculative architecture. Readout, addressing, transport, and the energy cost of accessing memory are not supplied by the canonical PDE; no zero-cost memory theorem follows.

---

## 6. The Brain as a Qi Computer

### 6.1 The 13-chakra gate chain

The human body is assigned a 26-rung span from cellular ($n=142$) to the
organism boundary ($n=168$), with 13 chakra nodes at $P_\parallel=2$ rung
spacing (`consciousness/chakras-as-cascade-bubbles.md` §6). The nodes occupy
$n=142,144,\ldots,166$; $n=168$ is the boundary rather than a chakra node.
Treating each chakra as a gate stage that anchors coherence and couples to
neighboring stages is a **Hypothesized** anatomical mapping.

In the proposed computational reading, the chakra chain is a 13-stage node
sequence across that 26-rung span. The root node ($n=142$) is assigned a
cellular timescale of approximately $39$ THz, while the crown node ($n=166$)
is assigned an organism-scale timescale of order $100$ MHz. Intermediate
feature-extraction roles are **Speculative** and require a neural
coupling/readout model.

### 6.2 The binding problem as a conditional field mapping

In the Qi framework's speculative reading, the visual cortex, prefrontal cortex, and brainstem may be modeled as density-pattern subsystems of one two-fluid medium. That shared substrate does not by itself solve the binding problem: cross-location and cross-rung integration require a coupling, advection, and readout model that this document does not derive.

The model further supposes that changes in $q$ could correlate with changes in integration, but high $q$ only suppresses the canonical conversion channel; it is not a general coherence-across-rungs law. Meditation, flow, fatigue, distraction, and trauma mappings remain **Hypothesized** applications.

### 6.3 Neural firing as surface expression

Action potentials—the binary spikes that neuroscientists measure—could be treated as a surface readout of a proposed Qi gate model. A neuron would fire when a specified local observable of $(E_Y,E_I)$ or $\varepsilon$ crosses a threshold. The threshold map, the neural coupling, and the claim that continuous density dynamics supply the processing are **Hypothesized**, not canonical solver behavior.

This model could explain noisy single-neuron signals alongside coherent population statistics only after a neural measurement and coupling model is supplied. The correlations are not established to reside in an unobserved field rather than in the spike trains themselves.

---

## 7. Comparison with Known Paradigms

| Property | Classical (CMOS) | Quantum | Neuromorphic | **Qi Computation** |
|---|---|---|---|---|
| State variable | Voltage (binary) | Qubit amplitude (continuous, probabilistic) | Spike rate (analog) | Canonical density pair $(E_Y,E_I)$; optional positive-root lift coordinate |
| Logic primitive | NAND gate | Unitary gate (e.g., CNOT) | Synaptic weight | Gated density conversion; proposed instruction vocabulary |
| Information representation | Bits (0/1) | Qubits ($\alpha|0\rangle + \beta|1\rangle$) | Spike timing | Local/aggregate $q$ budget or Wu Xing phase mapping (Speculative) |
| Memory | Separate (SRAM/DRAM) | Fragile (decoherence) | Distributed (synaptic weights) | IIR diagnostic plus persistent density patterns (Hypothesized) |
| Energy per operation | ~$10^{-15}$ J (typical CMOS switching scale, not the Landauer limit) | ~$10^{-12}$ J (cooling-dominated) | ~$10^{-12}$ J (spike) | No canonical energy-per-operation law; conversion coefficient $(1-q)$ only |
| Error correction | Explicit (ECC, parity) | Explicit (surface codes) | Implicit (redundancy) | Proposed Wu Xing geometry (Speculative) |
| Clock | Global | Gate-level | Asynchronous | Proposed $\varphi$-spaced cascade domains |
| Parallelism | Moderate (multicore) | Massive (Hilbert space) | Massive (neural population) | Proposed nested processing across rungs |
| Decoherence | Not applicable | The central problem | Tolerated (stochastic) | Conversion is suppressed at high $q$; no complete decoherence law |

Qi computation occupies a proposed position among these paradigms. It is not quantum—there is no claim here of superposition or entanglement. It is not classical in the model's information representation—local density configurations and aggregate coherence budgets replace discrete bits. It is not neuromorphic—the canonical field dynamics are not simplified neuron models. Calling it a fourth paradigm is a **Speculative** organizing metaphor, not a classification derived from the PDE.

---

## 8. Unregistered Candidate Tests
The four tests below are candidate observables proposed by this document. The prediction registry contains no corresponding entries or IDs.

### P1 (unregistered candidate test): Conditional operation-cost scaling in high-$q$ materials

In a conditional device model, if switching energy is mapped to the canonical conversion openness or to the optional $g(q)(1-q)$ transmission proxy, a Qi-coherent material could show a non-monotonic operation-cost trend across $q$. Measure switching energy against independently estimated coherence.
The Landauer comparison $k_BT\ln2\approx2.9\times10^{-21}$ J at $T=300$ K is a **Speculative/Hypothesized** device mapping. This candidate test has no prediction-catalog ID.

### P2 (unregistered candidate test): $\varphi$-periodic structure in neural information processing

The documented neural hierarchy and rung placements are conditional inputs to this proposed test. Measure intrinsic timescales across the stated neural levels and test whether ratios cluster near $\varphi$. The value of $\varphi$ fixes the candidate ratio, but the hierarchy, level assignments, placements, and measurement protocol are additional assumptions; this candidate test has no prediction-catalog ID.

### P3 (unregistered candidate test): Wu Xing 5-phase logic realizable in quasicrystals

If a material mapping from five-element doping to the canonical density channels can be independently specified, a quasicrystalline electronic circuit could be tested for five conductance states and the 20 generation/control transitions. Fabricate a nanoscale device (for example, Al-Pd-Re with controlled dopants) and measure its I–V characteristics under the proposed Qi-coherent conditions. The five-state and transition claims remain a **Speculative** device extrapolation, and this candidate test has no prediction-catalog ID.

### P4 (unregistered candidate test): Conditional information persistence in Qi-structured materials

If a device closure makes a density pattern's decay rate proportional to the conversion openness, an organized pattern written into a high-$q$ material could persist longer through this channel. Measure charge or spin-pattern decay in matched samples. High $q$ suppresses canonical conversion, while a lifetime enhancement beyond thermal relaxation requires specifying the other channels and the energy/measurement model; this candidate test is **Speculative/Hypothesized** and has no prediction-catalog ID.

---

### Framework definitions used as inputs

- The definitions document supplies the local bookkeeping convention $I_{\mathrm{cell}}=k_Bq\ln\varphi$, the aggregate budget $I_\Omega=k_B\ln\varphi\sum_iq_i$, the entropy proxy $S_{\mathrm{cell}}=-q\,k_B\ln\varphi$, and the per-cell flow proxy $dI_{\mathrm{flow,cell}}/dt=\lambda(1-q)k_B\ln\varphi$ (`predictions/cassi_definitions.md` §11). This document treats their device interpretation as **Hypothesized**.
- The canonical solver uses nonnegative density variables $E_Y,E_I$, the conversion residual $\varepsilon=E_Y-\varphi E_I$, and the conversion coefficient $(1-q)$ (`foundations/cassi-first-principles.md` §§1–2).
- The cascade ladder $\ell_n=\ell_{\mathrm{Pl}}\varphi^n$ is a documented scale convention (`foundations/dimensionful-cascade.md` §3); interpreting it as a clock hierarchy is addressed below as a Speculative model.

### Asserted inputs and solver conventions

- $g(q)=q/(\varphi^2+q^2)$ is an **Asserted** optional transmission multiplier. It is not part of the canonical conversion term unless that conditional model is explicitly adopted.
- The IIR coefficient $\tau=\varphi^{-1}$ and its odd-$\varphi$ kernel are **Asserted solver conventions** in the optional `qi_memory` closure, not derived physical cycle times.
- The $\lambda=0.1$ inverse-time normalization is an Asserted solver convention; its $\lambda=1/(2w)$ relation is not used here as a derived rate.

### Hypothesized mappings and conditional extensions

- The aggregate Landauer row $\Delta Q_{\mathrm{bit}}=\ln2/\ln\varphi\approx1.44$ is a dimensionless budget mapping. Assigning it to an irreversible device operation or to a physical energy cost is **Hypothesized**.
- The exact positive-root lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ supplies the coordinate diagnostic $\mathbf J_\Psi^{(+)}$. A physical-current, transport, or inter-rung transfer interpretation requires a separate constitutive map and remains **Hypothesized**.
- The Wu Xing $w=5$ cycle and its two transition types are documented geometry; using them as a 5-state logic encoding or error-correcting instruction set is **Hypothesized/Speculative**.
- The documented 13-node, 26-rung chakra chain is a framework mapping; treating it as a 26-stage computer or neural gate chain is **Hypothesized/Speculative**.
- The phase-matching factor $\mathcal M$ is a model quantity in `foundations/quantum-measurement-derivation.md` §3.1; using it as a material gate-coupling or transfer-success parameter is **Hypothesized**.

### Speculative / Creative extrapolation

- That WRITE, ERASE, and conditional TRANSFER form a computationally universal gate set for the Qi field.
- The Wu Xing logic implementation and error-detection claims.
- The $\varphi$-spaced clock-domain and nested-processing architecture.
- The $q\approx0.46$ optional transmission-speed claim and any speed-power tradeoff.
- The mapping of neural firing, consciousness, or chakra organization to Qi computation.
- Predictions P1–P4.

### Not claimed

- That Qi computers can be built with current or near-future technology.
- That the human brain literally implements the Wu Xing logic described here.
- That quantum computing is a subset or special case of Qi computation.
- That the canonical current diagnostic is a transport current without a constitutive law.
- That the cascade is a computer in any designed or teleological sense—only that its dynamics are computationally interpretable.

---

## References

- `predictions/cassi_definitions.md` §6 & §11—the information bookkeeping convention ($I_{\mathrm{cell}}=k_B q\ln\varphi$, aggregate budget, flow proxy, Landauer row)
- `foundations/qi-flow-double-helix.md`—Qi flow, IIR temporal memory, one-rung diagnostic memory
- `foundations/cassi-first-principles.md`—two-fluid PDE, density residual, conversion sector, IIR memory, $\tau=\varphi^{-1}$, odd-$\varphi$-power kernel
- `foundations/bubble-edge-geometry.md`—optional transmission multiplier $g(q)$, conversion-diffusion balance
- `foundations/wu-xing-derivation.md`—pentagon geometry, generation and control cycles
- `foundations/dimensionful-cascade.md`—the $\varphi$-ladder (292 = today's horizon rung), conditional clock interpretation
- `foundations/cascade-suppression-formula.md`—per-rung attenuation, signal propagation
- `foundations/quantum-measurement-derivation.md`—phase-matching factor $\mathcal{M}$
- `foundations/bubble-lattice-fabric.md`—8-level neural hierarchy at n≈144
- `consciousness/chakras-as-cascade-bubbles.md`—13-chakra gate chain, 26-rung span
- `consciousness/consciousness-from-phi.md`—consciousness as Qi gate dynamics
- `speculations/superconductivity-as-qi-coherence.md`—conditional effective-conversion model and its $q\to1$ limit
- `speculations/qi-bubble-propulsion.md`—Wu Xing doping, quasicrystalline materials
- `speculations/cascade-infrastructure.md`—gate chain topology, nested processing
- `consciousness/cascade-consciousness.md`—field perception, cascade nervous system
