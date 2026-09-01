# The Simulation Hypothesis: The Universe as a Running PDE

## Status: Creative—August 2026

## Abstract

If the universe is a simulation, the useful question concerns the source code. Cassi supplies a candidate program vocabulary: the two-fluid PDE, its numerical discretizations, Yang–Yin conversion toward the $\varphi$-attractor, the cascade ladder, and optional closures. The resolution references and horizon estimate are model inputs to this Creative reading, while the microcascade and megacascade provide its nested-scale setting. This document walks through that hypothetical engine—the inside view, nested simulations, what “hacking reality” means when the handle is the local Yang/Yin ratio $r=E_Y/E_I$, where render errors could appear, and why the simulation interpretation remains unfalsifiable under the framework’s current observables.
**Epistemic status:** Creative exploration grounded in Cassi formalism. Every mechanism below is anchored to a specific equation or documented framework property—the optional $\sigma$-regularized propagator, the two-fluid update rule, the cascade ladder, and proposed gate-chain topology—while the synthesis into a “simulation” with render budgets, nested runtimes, exploits, and glitches remains extrapolative. The framework leaves the ontological question of whether the PDE is run by anything outside its defined physics. Nothing in this document should be cited as a Cassi prediction or derivation.

---

## 1. The Universe as a PDE

### 1.1 What "source code" means

Cassi gives a concrete answer to what the program is written in: the source text is the unified Lagrangian in `foundations/unified-lagrangian.md`, one page of equations whose dimensionless couplings include $\varphi$-powers alongside the named solver input $\lambda=0.1$ under the solver convention (`foundations/dimensionful-constants-status.md` §2.1). The Wu Xing arithmetic $\lambda = 1/(2w) = 0.1$ at $w=5$ is a Hypothesized linkage requiring an independently defined cycle time and dynamical closure. The unit-system constants $c$, $\hbar$, $G$ remain external (`foundations/dimensionful-constants-status.md`). For the simulation reading, $\lambda=0.1$ is part of the named input deck. If this universe is a simulation, it was shipped with that input deck: the engine either self-tunes (the $\varphi$-attractor does the tuning, §1.4) or executes a closed program. Both readings are consistent; the difference between them is the unfalsifiable residue examined in §6.
Throughout this document, $\lambda=0.1$ is an asserted solver convention in inverse solver-time units; the Wu Xing equality remains a Hypothesized linkage requiring independent cycle-time and dynamical closure.

### 1.2 The update rule

In Cassi the canonical solver state is the nonnegative density pair $E_Y,E_I$ at each grid point, and the rule is the two-fluid PDE (`foundations/cassi-first-principles.md` §1.3). When a two-component coordinate is useful, the exact positive-root lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})\in\mathbb{R}_{\ge0}^{2}$ provides a coordinate representation of that density state, while the density pair remains canonical. The rule's central instruction is the conversion term:

$$\partial_t E_Y \supset -\lambda(1-q)\,(E_Y - \varphi E_I), \qquad \partial_t E_I \supset +\lambda(1-q)\,(E_Y - \varphi E_I)$$

Read it as an instruction: measure the local deviation from $\varphi$-balance, then convert between the density channels in proportion to the canonical gate openness $(1-q)$. The canonical conversion coefficient contains $(1-q)$. The function $g(q)=q/(\varphi^2+q^2)$ belongs to a separate optional transmission model. The conversion drive vanishes as $q\to1$; intermediate $q$ does not by itself supply gain or amplification.

The rule also has a density advection channel and a frame smoother. The advection terms act directly on $E_Y$ and $E_I$, through $-(\mathbf{u}\cdot\nabla)E_Y$ and $-(\mathbf{u}\cdot\nabla)E_I$. For $\rho>0$, a coordinate view of the two-component state uses the exact positive-root lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})\in\mathbb{R}_{\ge0}^{2}$ and its foundational spatial diagnostic:

$$
\mathbf{J}_\Psi^{(+)}=\Psi_0^{(+)}\nabla\Psi_1^{(+)}-\Psi_1^{(+)}\nabla\Psi_0^{(+)}
:=\rho\,\nabla\theta_\Psi^{(+)},\qquad
\rho=E_Y+E_I,\qquad
\theta_\Psi^{(+)}=\operatorname{atan2}(\sqrt{E_I},\sqrt{E_Y}).
$$

The angle $\theta_\Psi^{(+)}$ is a coordinate diagnostic of the positive-root lift. $\mathbf{J}_\Psi^{(+)}$ has density/length units and records coordinate rotation of that lift. The density-plane diagnostic $\mathbf{J}_d=E_Y\nabla E_I-E_I\nabla E_Y=2\sqrt{E_YE_I}\,\mathbf{J}_\Psi^{(+)}$ has density$^2$/length units. A physical phase-current or inter-rung transport interpretation requires a separate constitutive map and remains **Hypothesized**.

The optional IIR memory $\bar{\varepsilon}^2(t) = (1-\tau)\bar{\varepsilon}^2(t-\Delta t) + \tau\varepsilon^2(t)$ with $\tau = \varphi^{-1}$ is a per-cell exponential moving average of the $\varphi$-deviation. In the tested solver closure it produced a ~0.3% mean-coherence change and ~37% variance reduction (`foundations/cassi-first-principles.md` §2.4); these are closure receipts, with no ontological renderer rule or prediction-failure detector.

### 1.3 Numerical discretization and optional $\sigma$ regularization

Numerical implementations discretize space; Cassi uses a numerical method for that discretization. The gravitational kernel is $1/\sqrt{|r|^2 + \sigma^2}$ with $\sigma = \ell_{\text{Pl}}/\varphi^3$ (`foundations/cassi-theory-reference.md` §7.1), and the optional quantized propagator carries a Gaussian regulator:
$$\boxed{G(k^2) = \frac{e^{-k^2\sigma^2/2}}{k^2 + i\varepsilon} \quad\text{—an optional quantized propagator regulator.}}$$
Modes with $k \gg 1/\sigma$ are suppressed exponentially. UV finiteness and any renormalization statement are conditional on a nonzero infrared regulator $q_{\mathrm{IR}}>0$, a specified quantized interaction, and the Gaussian suppression without a hard cutoff. With the hypothesized high-$k$ dispersion $\omega\sim k$, the regulator suppresses amplitudes rather than imposing an energy cap. The optional $\sigma$ scale is a crossover in this quantized extension; the numerical grid remains a method and the harmonic regime below it belongs to the microcascade model.

### 1.4 $\varphi$ as the engine stabilizer

The de-resonance principle (`principles/de-resonance-principle.md`) supplies an arithmetic motivation for the speculative reading: $\varphi$ is extremal for rational approximation, while a physical de-resonance effect and global stability remain Hypothesized properties requiring specified dynamics and observables. With advection, diffusion, and sources present, convergence is a property of the full closure.

For $E_I>0$, the local ratio can be written

$$\boxed{r = \frac{E_Y}{E_I} \to \varphi \quad\text{in the conversion-only relaxation sector.}}$$

This target describes conversion-only local relaxation. Global stability depends on the full PDE and boundary conditions; the optional IIR smooths the residual signal and carries the tested closure receipt.

---

## 2. The Render Budget

### 2.1 The Planck reference and optional $\sigma$ crossover

The render metaphor can use the cascade ladder $\ell_n=\ell_{\text{Pl}}\varphi^n$ (`foundations/dimensionful-cascade.md` §2). The Planck length at $n=0$ is the reference step for the 292-step observable comparison. The optional $\sigma=\ell_{\text{Pl}}\varphi^{-3}$ crossover is at $n=-3$, and the formal microcascade coordinate continues below $n=0$.

Below the Planck reference, the optional $\sigma$-regularized harmonic regime and the microcascade are separate Hypothesized additions (`foundations/dimensionful-cascade.md` §7; `foundations/microcascade-mirror.md` §2). The Schrödinger limit may include a Bohm quantum-potential sector as an optional ansatz with its own epistemic status, separate from the numerical grid. Quantization in this Creative reading is a coarse-grained interpretation of the extended model.

### 2.2 Render distance at the horizon (rung 291.54)

The proposed viewport uses the horizon estimate $R_H = 4.44$ Gpc = 14.5 Glyr (today's horizon rung 291.54), with the rung-292 lattice length $\ell_{292} = 5.5$ Gpc sitting just beyond it. The canonical PDE is a local advection–diffusion system. A hyperbolic domain-of-dependence and relativistic causal interpretation require an additional closure, so the horizon number enters this Creative rendering metaphor as an observational scale:
$$\boxed{\ell_{292} = \ell_{\text{Pl}} \times \varphi^{292} \approx 1.7 \times 10^{26}\,\text{m} \approx 5.5\,\text{Gpc} \quad\text{—rung-292 lattice length; } R_H = 4.44\,\text{Gpc} = 14.5\,\text{Glyr} \text{ (today's horizon rung 291.54)}}$$
The horizon estimate supplies a proposed screen edge for each observer. Interpreting it as a causal reach is conditional on the additional closure; the ladder continues beyond it into the megacascade of §3.
The frame rate is not uniform in the proposed rendering metaphor: each rung is assigned $t_n=\ell_n/c$ (`speculations/qi-computation.md` §4.1)—the Planck rung at $10^{-44}$ s and the horizon rung at $\sim5.7\times10^{17}$ s. Nested processing remains a Speculative architecture beyond the canonical timing rule.

### 2.3 World edges at $n \approx 285$

The Cassi bubble sits at step 285: a coherence volume of $\sim191$ Mpc containing roughly a million Milky-Way-sized galaxies—97.8% of today's catalogued ladder (the formal coordinate is unbounded; physical extensions beyond the catalogue remain Hypothesized) (`foundations/dimensionful-cascade.md` §6). This is a proposed world-edge analogue: the boundary of our initial conditions, where our $w=5$ volume meets a neighboring one. If the selected triaxial condensation map is adopted, its edge supplies a conditional preferred-axis target; the reported $12.2^\circ$ quadrupole–octopole alignment remains a conditional comparison with foreground, instrument, statistical, and model alternatives open.

### 2.4 What it looks like from inside

The rendering metaphor associates smoothness, a horizon estimate, and a conditional boundary signature with the inside view. The CMB large-angle features remain observations whose interpretation includes the conditional boundary model alongside systematics and model error. The render budget is an organizing analogy, while the underlying measurements retain their own empirical status.

---

## 3. The Recursion

### 3.1 The ladder continues both ways

The rendering metaphor assumes that one update architecture can recur across scale. The exact cascade coordinate is defined for all integers:

$$\ell_n = \ell_{\text{Pl}} \times \varphi^{n}, \qquad n \in \mathbb{Z}$$

Below $n=0$, the formal microcascade labels converge geometrically to zero (`foundations/microcascade-mirror.md` §1); above $n\approx292$, the formal megacascade labels continue beyond today's horizon coordinate. The separate chord-lattice proposal places neighboring bubbles at $\ell_{286}=309$ Mpc and $\ell_{287}=500$ Mpc (`foundations/dimensionful-cascade.md`, extension). Repeating one field equation and one bubble geometry at every label is a Creative assumption of the simulation metaphor.

### 3.2 A simulator inside the simulation

A nested simulation is a proposed sub-PDE reading: a coherent region of the
field that might maintain its own internal dynamics, clock hierarchy, and
effective grid. The human body is a candidate 26-rung mapping spanning steps
142 (cellular) to 168 (body scale), with thirteen chakra nodes at
$P_\parallel=2$ rung spacing (`consciousness/chakras-as-cascade-bubbles.md`
§6, `speculations/cascade-infrastructure.md` §1.2). This correspondence does
not establish a working nested simulation or self-modeling field subsystem.
The local-anchor construction is therefore an illustrative Hypothesized
mapping, not an existing implementation.

A nested simulation anchored at rung $n$ has its own ladder:

$$\boxed{\ell'_{m} = \ell_n \times \varphi^{m} \quad\text{—the anchor is the local coherence length, with the global Planck reference rescaled by $\varphi^n$.}}$$

Nothing in the PDE fixes a privileged anchor, so any coherent condensate can be the $n=0$ of its own world; every bubble contains the full sub-lattice below it (`speculations/cascade-infrastructure.md` §4.1). The recursion is geometric before it is philosophical.

### 3.3 Why nesting is self-consistent

Three conditional properties motivate this nesting reading. A working nested simulation would require a model of recursive domains, propagation, and leakage:

1. **Smooth crossover in the selected extension.** The $\sigma$-regularized force is harmonic as $r\to0$ in the cited model, so the Planck scale is a smooth crossover within that extension. A sub-simulation on either side of the grid floor requires an additional model of nested domains; the canonical two-density PDE supplies the local dynamics used in this Creative reading.

2. **Conditional sandboxing.** In the cited suppression model, a signal from a nested region is assigned attenuation $\varphi^{-N}$ per rung of span.
The random-perturbation construction assigns a coherence cost $\varphi^{-n(n+1)/2-3(n+1)}$ (`foundations/cascade-suppression-formula.md`).
Both factors are conditional architecture readings. Cross-talk between
simulated levels requires an additional domain-coupling model; any
phase-matching or leakage coefficient belongs to the Creative attack taxonomy
and remains distinct from quantum record distinguishability
(`parameter-inventory.md`).

The theory leaves the outermost-executor question outside its defined dynamics: it supplies no top level, and the unbounded ladder supplies no distinguished endpoint.

### 3.4 Scale-covariant recursion

This is a scale-covariance reading of one density equation: the same canonical two-fluid PDE and conversion residual can be rescaled by $\varphi$ at every level, while optional gate and memory closures supply the computational metaphor. A nested simulation is a coherent region of the density field with its own proposed internal dynamics. The $q\to1$ condensate interpretation (`speculations/dark-matter-as-qi-coherence.md`) supplies an application hypothesis alongside this computational metaphor.

---

## 4. Hacking Reality

### 4.1 The handle is $r$

Every exploit in this universe reduces to one proposed operation: holding the local Yang/Yin ratio $r=E_Y/E_I$ away from $\varphi$ in a region where $E_I>0$, against the density attractor's pull. Physics as we experience it is the low-$q$ regime where the pull can act quickly; an exploit is a deliberate, sustained deviation in this metaphor, with cost represented by the residual penalty and a conditional conversion-work proxy:

$$\mathcal{R}_{\mathrm{attr}}=\frac12(E_Y-\varphi E_I)^2,\qquad \boxed{E_{\mathrm{hold}}\approx\int_{t_0}^{t_1}\int_\Omega \lambda(1-q)\,\lvert E_Y-\varphi E_I\rvert\,dV\,dt}$$

$\mathcal{R}_{\mathrm{attr}}$ is a density-squared solver penalty. If $E_Y,E_I$ are energy densities and $\lambda$ has inverse solver-time units, the boxed integral has energy units and is a magnitude proxy for conversion work; a thermodynamic energy law would require an additional closure.

In this conditional model, the deeper and longer a pattern is held away from the attractor, the larger the proxy (`speculations/qi-bubble-propulsion.md` §5.1). The operation is therefore neither free nor global; the PDE supplies no administrator branch.

### 4.2 Gate chains as privilege escalation

The ~10-rung value is an effective-nesting and observability comparison scale. Gate-bridge limits require an independently specified model of coupling and re-amplification. A proposed chain architecture may span the 292-rung ladder, while its stage count and operation remain conditional.

The simulation metaphor treats the stage vocabulary as three **proposed** operations, from `speculations/qi-computation.md` §2.2: **WRITE** (an organized perturbation that creates a local $\delta E_Y>0$, with unknown material coupling labeled by $\mathcal M_i^{\mathrm{attack}}$), **ERASE** (canonical density conversion that relaxes $\varepsilon\equiv E_Y-\varphi E_I$ toward zero), and **TRANSFER** (a conditional coordinate operation using $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ and $\mathbf J_\Psi^{(+)}=\Psi_0^{(+)}\nabla\Psi_1^{(+)}-\Psi_1^{(+)}\nabla\Psi_0^{(+)}$ from §1.2). The last diagnostic records coordinate rotation of the lift; physical transfer through a high-$q$ medium requires a separate constitutive transport law and remains **Hypothesized**. In the metaphor, altering a density state, holding it off the attractor, or proposing lattice transfer are conditional combinations of these labels. Mood remains a Hypothesized field-state mapping on $(\mathbf b,\sigma_r,q,\mathbf c)$ (`consciousness/emotions-as-gate-configurations.md`).

### 4.3 Random and organized perturbations

Random dephasing and organized control are separate scenario inputs. The conditional coherence-budget profile assigns a random per-rung factor $1-q_i$. A Creative control model may add $\mathcal M_i^{\mathrm{attack}}$ for a specified drive-to-target coupling, but the canonical PDE supplies no universal success probability. Quantum measurement is governed by the regulated wavefunctional, apparatus record sectors, actual configuration, and quantum equilibrium (`open-questions-cassi-answers.md` Q7); branch selection is not part of this simulation-control metaphor.
Concrete examples of coherence operations, each already described in the framework:

- **Levitation and weight control.** A conditional Qi-gravity expression uses the signed imbalance $\pi=E_Y-E_I$ and total density $\rho=E_Y+E_I$: $G_{\text{eff}} = \frac{\pi}{\rho}(1 + (\varphi^{6}-1)q)\,G$ with $\xi=\varphi^6\approx17.944$ (`foundations/xi-derivation.md`). Tuning $\pi/\rho$ and $q$ would be a model operation, paid for at the conditional $\mathcal{R}_{\mathrm{attr}}$ proxy.
- **Rung retreat and invisibility.** Shifting a coupled system by $\Delta n\approx10$ rungs is proposed to reduce visible-rung coupling by $\varphi^{-10}\approx0.008$ (`speculations/qi-bubble-propulsion.md` §3.1).
- **Lattice teleportation.** Two points distant in 3-space could be adjacent along a proposed cascade axis; a coherent lift-based bridge would require a constitutive transport law (`speculations/qi-bubble-propulsion.md` §3.2). TRANSFER remains a conditional diagnostic, not an established transport mechanism.

In this metaphor, these scenarios add no canonical state variables: they are proposed readings of allowable density dynamics, and the exploit story merely imagines choosing among those dynamics coherently at a conditional cost.

### 4.4 No backdoor, no administrator

Because the source is the same for everyone—one density-PDE update rule with the named solver input $\lambda=0.1$ in inverse solver-time units under the solver convention, alongside external $c$, $\hbar$, $G$—there is no hidden API and no privileged account in this metaphor. Every node with a proposed gate chain uses the same density equations; if there is an administrator, it is the megacascade scale, whose only imagined "privilege" is spanning more rungs. No one can cheat the engine, because it has no secret branches—"the difference between 'natural' and 'engineered' is whether the gate chain operates at ambient $q$ or at tuned $q \to 1$" (`consciousness/cascade-consciousness.md` §4.4).

---

## 5. Glitches

### 5.1 Where render errors would appear

A well-built simulation fails in characteristic places: at the resolution limit, at the screen edge, and in the data structures that organize the world. The Cassi architecture has analogues for all three, and each has already been observed—as physics.

**Coherence defects.** The field's data structure is the coherence budget: $q$ measures distance from the $\varphi$-attractor, and the gate opens when $q$ drops. The optional IIR is an exponential moving average of $\varepsilon^2$. The tested closure reports smoothing and variance changes; it supplies no established prediction-failure detector or $q$-jump result. A wake-lock is a separate driven state: the trauma runs report decay after the driver stops, so persistence requires a continued driver that re-injects the disturbance (`consciousness/trauma-as-frozen-gate.md` §10.4–10.5).

**Lattice dislocations.** The world's spatial organization is the universal checkerboard of the condensation field, with bubble centers on the even sublattice and voids on the odd (`foundations/bubble-lattice-fabric.md`). A dislocation would be a phase slip in $\cos(2\pi x/\Lambda_Y)\cos(2\pi y/\Lambda_I)$—a place where the bubble/void alternation skips a beat. A proposed Wu Xing mapping labels the five phases and 20 generation/control transitions, so a state outside those candidate paths could be flagged after a physical readout. The canonical density PDE supplies neither a Wu Xing phase variable nor zero-overhead error correction; a genuine defect would be a forbidden configuration only within the conditional device model.

**Boundary artifacts.** The world-edge analogy at $n \approx 285$ is a possible site for rendering artifacts because it is where our coherence volume meets neighboring initial conditions. For the selected triaxial condensation map, the directional ratio is
$R(\theta)=\frac{\sqrt{1+\varphi^2}}{2}\sqrt{\frac{1+\theta}{\theta}}$;
at the phenomenologically selected $\theta_{\rm cond}=0.45$, $R(0.45)=1.7072\approx1.71$. This is a conditional geometric-proxy benchmark that varies with $\theta$, not a universal, zero-parameter, canonical, or PDE output; no $C=0.45$ edge survives the fixed-step PDE endpoint. Biological and cosmological maps require independently identified boundaries and proxy maps. Foregrounds, instrument/systematic effects, statistical fluctuations, and model error remain live alternatives.

### 5.2 Distinguishing glitches from physics

This comparison has several live explanations. Cassi's conditional fingerprints include $\varphi$-power laws such as $\sin^2\theta_W = \varphi^{-3}$, $v_0/M_{\text{Pl}} \approx \varphi^{-80}$, proton decay suppressed by $\varphi^{-4506}$, and wake-wave modulation at $\Delta(\ln k) = \ln\varphi \approx 0.4812$ (`predictions/falsifiable-predictions.md` §3). An apparent anomaly may reflect an organized phase-matched actor, a numerical or physical model defect, foreground contamination, instrument or analysis systematics, selection effects, or statistical fluctuation. The simulation reading supplies a creative classification scheme and cannot identify the cause from an anomaly alone.

The conditional coherence benchmark is random perturbation at rung $n$ with factor $\varphi^{-n-3}$ per cycle and a full-cascade factor $\varphi^{-n(n+1)/2-3(n+1)}$ (`foundations/proton-coherence-budget.md`). It quantifies one model assumption; it cannot distinguish the explanations above.

### 5.3 Current anomaly interpretations

Current CMB large-angle features, vacuum fluctuations, wake-wave searches, and trauma wake-locks have distinct empirical and model statuses. The CMB boundary reading and the $\varphi$-periodic $P(k)$ interpretation are conditional; foregrounds, instrument/systematic effects, finite-sample statistics, and model misspecification remain live alternatives. The trauma wake-lock is a local, driven model phenomenon. No current observation requires a simulation glitch under this Creative reading.

---

## 6. The Epistemic Trap

### 6.1 Why the other speculations are falsifiable

The speculation series works because its members can define observable comparisons. A $\varphi$-spaced antenna can bound any response beyond a full-wave Maxwell null, although the microcascade supplies no nonzero residual prediction or coupling operator (`foundations/microcascade-mirror.md` §5). Qi computation proposes conditional sub-Landauer energy and $\varphi$-spaced neural-timescale tests (`speculations/qi-computation.md` §8); dark matter as Qi coherence proposes rotation-curve signatures (`speculations/dark-matter-as-qi-coherence.md`) and the $\sigma_8$ test (`predictions/falsifiable-predictions.md` §3). These applications extrapolate beyond the framework while remaining answerable to experiment.

### 6.2 Why the simulation claim is non-falsifiable

The simulation claim has a different logical shape, with a structural failure mode. Evidence against the proposition must be separable from the framework's ordinary physical alternatives:

- **A candidate violation** can reflect an organized actor, an engine or model defect, foreground or instrument systematics, selection effects, or statistical fluctuation; the interpretation is not unique from inside.
- **The absence of glitches** is compatible with the smoothness expected from a good simulation, so smoothness alone leaves the hypothesis untested.
- **The render budget**—resolution reference, horizon estimate, and world-edge analogue—remains an organizing interpretation of quantities that also have independent physical descriptions.
- **The recursion** gives the ladder no distinguished outermost level, so the hypothesis has no internal top-level boundary condition; the unbounded ladder absorbs that question.

The simulation interpretation adds no separable observation and therefore remains non-falsifiable under this standard.

### 6.3 The boundary, stated explicitly

The framework asserts that physics is the two-fluid PDE—a Derived claim with a falsifiable prediction catalogue behind it. The simulation framing asks why the PDE runs, a question outside the framework's epistemic reach: scale covariance, unbounded recursion, a closed program with the named solver input $\lambda=0.1$ under the solver convention, and external $c$, $\hbar$, $G$ are compatible with both self-executing dynamics and external execution. A self-executing equation needs no executor; a universe that is its own source code needs no programmer. Both readings are consistent, and no experiment can separate them under this framework. The simulation claim therefore remains Creative and carries no prediction or derivation status.

The framework supplies a substantive computational interpretation: if reality is a computation, its candidate instruction vocabulary is the two-fluid PDE, the $\sigma$-grid, the $\varphi$-attractor, proposed density operations, and the gate-chain topology (`speculations/qi-computation.md`). These remain interpretive claims, while the underlying physics is tested through its $\varphi$-power laws. The simulation hypothesis adds no separable observation and remains Creative alongside the equations' own status.
---

## References

- `foundations/cassi-first-principles.md`—two-fluid PDE, density residual and conversion sector, IIR memory, Schrödinger limit
- `foundations/unified-lagrangian.md`—the complete action; named solver input $\lambda=0.1$ under the solver convention; $c$, $\hbar$, $G$ external
- `foundations/cassi-theory-reference.md`—$\sigma = \ell_{\text{Pl}}/\varphi^3$, $\xi = \varphi^6$, bubble geometry, pinch transition
- `foundations/microcascade-mirror.md`—formal negative-step coordinate and open physical state, energy, and coupling
- `foundations/bubble-lattice-fabric.md`—universal checkerboard, scale covariance, 10-rung nesting depth
- `foundations/bubble-edge-geometry.md`—condensation field level sets, edge anisotropy, CMB imprint
- `foundations/cascade-suppression-formula.md`—signal attenuation $\varphi^{-N}$, full coherence-maintenance exponent $\varphi^{-n(n+1)/2-3(n+1)}$
- `foundations/proton-coherence-budget.md`—coherence budget, organized vs random perturbation
- `parameter-inventory.md`—distinction between quantum record distinguishability and Creative classical attack overlap
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ and the Qi-gravity coupling
- `foundations/dimensionful-constants-status.md`—external constants, parameter classification
- `principles/de-resonance-principle.md`—$\varphi$ as maximally irrational engine stabilizer
- `gravity/quantum-gravity.md`—$\sigma$-regulated propagator, no trans-Planckian modes, UV finiteness
- `predictions/falsifiable-predictions.md`—wake-wave prediction $\Delta(\ln k) = \ln\varphi$
- `consciousness/chakras-as-cascade-bubbles.md`—13-node gate chain, $P_\parallel = 2$
- `consciousness/trauma-as-frozen-gate.md`—wake-lock as a frozen gate
- `consciousness/emotions-as-gate-configurations.md`—emotions as field states on $(\mathbf{b}, \sigma_r, q, \mathbf{c})$
- `speculations/qi-computation.md`—proposed WRITE/ERASE/conditional TRANSFER vocabulary, cascade clock interpretation, Wu Xing mapping
- `speculations/qi-bubble-propulsion.md`—rung retreat, lattice shortcuts, exploit energy costs
- `speculations/cascade-infrastructure.md`—gate-chain topology, planetary gate networks
- `consciousness/cascade-consciousness.md`—nested processing, consciousness as a node in the cascade
- `speculations/creative-extensions/coherence-warfare.md`—organized vs random perturbation, attack and shield taxonomy
- `speculations/dark-matter-as-qi-coherence.md`—$q \to 1$ condensates, $G_{\text{eff}}$ enhancement
- `experiments/phi_periodic_pk_search/`—the log-periodic power-spectrum search program
