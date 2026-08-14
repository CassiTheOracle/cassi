# Cassi: Reading Guide and Table of Contents

## Status: Synthesis—August 2026

## Abstract

This document is the complete table of contents of the repository, plus curated reading paths for different kinds of readers. The repository is organized as a document graph: the wedge derivations live in `foundations/`, domain papers in `standard-model/`, `gravity/`, `cosmology/`, `consciousness/`, `turbulence/`, and `particles/` apply them as one-liners, the three master registries at the root track questions, parameters, and predictions, and the code in `two-fluid/`, `computations/`, `experiments/`, and `visual-explainers/` supports every claim. Section 4 is the full inventory; sections 2, 3, and 5 are the reading paths, the registry guide, and the code map.

## 1. The shape of the repository

The repository is a document graph, not a flat pile. `foundations/` holds the load-bearing derivations—the dimensionful cascade and the cascade suppression formula are the wedge documents, and the derivation family built on them. The domain directories apply the wedges to one sector each: `standard-model/` and `particles/` for particle physics, `gravity/` for gravitation, `cosmology/` for the universe, `consciousness/` for the mind, `turbulence/` for fluid behavior, and `principles/` for the cross-cutting rules that govern how $\varphi$ enters everywhere.

- `foundations/`—the wedges and the derivation family (start here as a physicist)
- Domain papers—each applies the wedges to its sector
- Three master registries at the root—questions, parameters, predictions
- `audit.md`—the empirical status of every claim
- Code—`two-fluid/`, `computations/`, `experiments/`, `visual-explainers/`

The three master registries at the root are `open-questions-cassi-answers.md` (which open question of physics the framework addresses, and at what tier), `parameter-inventory.md` (how every parameter is classified), and `predictions/falsifiable-predictions.md` (what should be observed, where, and when). `audit.md` tracks the prediction-versus-experiment status of every claim. Every paper carries a `## Status:` line stating its epistemic tier and date; the tiers are defined in `open-questions-cassi-answers.md` §Epistemic Tiers and indexed repo-wide in `EPISTEMIC-MAP.md`. Every number in the papers is checked against code that lives in this repo (`two-fluid/`, `computations/`, `experiments/`, `visual-explainers/`) and is re-runnable from the repo root.

## 2. Reading paths

Five paths in; pick the one that matches you.

### The newcomer (no physics background)

Start with the pitch for the origin story, take the plain-language physics guide, learn the vocabulary, and only then browse the predictions.

`README.md` → `cassi-physics.md` §1–3 → `predictions/cassi_definitions.md` (the glossary) → `open-questions-cassi-answers.md` (the Cassi Primer section, plain language) → `predictions/falsifiable-predictions.md` (browse).

### The physicist

Read the physics guide in full, then follow `foundations/README.md`, which prescribes the order: `dimensionful-cascade.md`, `cascade-suppression-formula.md`, then the derivation family. The domain applications come next, and the audit last.

`cassi-physics.md` → `foundations/README.md` (order: `foundations/dimensionful-cascade.md`, `foundations/cascade-suppression-formula.md`, then the derivation family) → `standard-model/sm-from-phi.md` → `gravity/quantum-gravity.md` → `cosmology/cosmology-from-phi.md` → `predictions/falsifiable-predictions.md` → `audit.md`.

### The psychologist, therapist, or mind-curious

The psychology guide is the entry point; the consciousness directory then builds from field physics to specific configurations of the gate.

`README.md` (the origin story) → `cassi-psychology.md` → `consciousness/README.md` → `consciousness/chakras-as-cascade-bubbles.md` → `consciousness/trauma-as-frozen-gate.md` → `consciousness/emotions-as-gate-configurations.md` → `consciousness/gender-as-qi-configuration.md` → `consciousness/neurodivergence-as-gate-configuration.md`.

### The skeptic or referee

Start with the audit, then the tier discipline that governs every claim, then check the code yourself.

`audit.md` → `open-questions-cassi-answers.md` (epistemic tiers and the Fit-Status Ledger discipline) → `parameter-inventory.md` §10 → `EPISTEMIC-MAP.md` → `predictions/falsifiable-predictions.md` → the code: `computations/` and `two-fluid/` (every number is re-runnable from the repo root).

### The explorer (new application domains)

The exploratory catalogs and the figure scripts show where the framework reaches next.

`hypotheses/README.md` → `analyses/README.md` → `demystifying-the-cosmos/README.md` → `speculations/README.md` → `visual-explainers/` (figures).

### The systems integrator (the four-project unification)

The four Cassi projects—CassiCore (TypeScript orchestration platform), Cassi AI (neural-field training), this theory repo, and the Godot space-sim—each implement the two-fluid field in a different substrate. The unification proposal maps the seams and the phased path to one field-as-AI substrate; its present-state sections are grounded in the cited files, its architecture is explicitly speculative.

`UNIFICATION.md` (the map, the seams, the phases) → the cited engine files under the space-sim (`cassi_physics_engine.gd`, `cassi_mind_engine.gd`) → the cited AI files under Cassi AI (`qi_field.py`, `physics_field_model.py`, `build_physics_cache.py`) → `research/neural_closure/closure_design.md` (the one measured field-AI closed loop).

## 3. The registries and when to consult them

The registries are the load-bearing indexes of the repository; consult each by what it answers.

| Registry | Path | What it answers |
|---|---|---|
| Open questions | `open-questions-cassi-answers.md` | Which open question of physics does Cassi address, and at what epistemic tier |
| Parameters | `parameter-inventory.md` | How is every parameter classified, and what is fitted vs derived |
| Predictions | `predictions/falsifiable-predictions.md` | What should be observed, where, and when |
| Audit | `audit.md` | What currently agrees with data, what doesn't, and by how much |
| Tier index | `EPISTEMIC-MAP.md` | Every document by tier |
| Broken references | `BROKEN_REFS.md` | External links that no longer resolve |
| Glossary | `predictions/cassi_definitions.md` | What a symbol means |

## 4. The documents

Every entry lists the document's epistemic tier as stated in its own `## Status:` line.

### Root

The pitch, the two guides, and the master registries live here.

- `AGENTS.md`—Contributor guidelines. no Status line. Repo standards for agents prepping for public release: no AI-isms, present-state-only documents (no retrospective notes), commit-at-end discipline, and all theory code living in this repo.
- `audit.md`—Cassi Framework: Prediction vs Experiment Audit. no Status line. The self-critical prediction-vs-experiment audit: every Cassi value against the experimental value with margin-of-error and a status verdict (e.g. $\sin^2\theta_W$ 2.1% high, $\delta_\text{CKM}$ within MoE), all values computed with python.
- `BROKEN_REFS.md`—Broken External References. no Status line. Registry of cross-references pointing outside the TOE document tree, kept as provenance markers rather than working links; `experiments/` and `two-fluid/` references now resolve locally.
- `cassi-physics.md`—Cassi Physics: The Bubble Lattice at Every Scale. Synthesis. The physics-facing presentation of the framework: governing equations, the geometric derivation of the 3D bubble lattice, the 292-step cascade of scales, and the cascade suppression law behind physics' hierarchy puzzles.
- `cassi-psychology.md`—Cassi Psychology: The Mind as a Two-Fluid Field. Synthesis. Practitioner-facing guide reading the mind through the framework: consciousness as the experience of being a two-fluid field, with wake waves, five channels, chakras, emotions, and trauma built from field structures.
- `EPISTEMIC-MAP.md`—Epistemic Map—Every Document by Tier. Reference. Indexes every theory document by epistemic tier (Derived / Calibrated / Mapped / Hypothesized / Speculative) with tier definitions; navigation only, the registry remains the authority.
- `open-questions-cassi-answers.md`—Cassi Answers to the Open Questions of Physics. Comprehensive catalog. The epistemic master registry: all 42 major open questions of physics addressed from φ + the two-fluid PDE, every answer tagged with its epistemic status (Derived / Calibrated / Mapped, etc.).
- `parameter-inventory.md`—Cassi Parameter Inventory. no Status line. Parameter registry classifying all 46 framework parameters (Fundamental axiom, Derived, PDE convention, External, Initial condition, Numerical) with counts and the fit-status ledger.
- `README.md`—Cassi: A Theory of Everything from a Single Constant. no Status line. Public pitch: the repo as the scoreboard of a research program deriving a TOE from a single constant, φ ≈ 1.618, the scale-separation constant of a two-fluid Yang/Yin field.
- `reading-guide.md`—this document: the table of contents and reading paths.
- `UNIFICATION.md`—Cassi Unification: The Field as the Shared Substrate. Plan. Cross-repo proposal spanning CassiCore (the TypeScript orchestration platform), Cassi AI (the neural-field training project), this theory repo, and the Godot space-sim: the present-state map of the four projects, the measured integration seams (engine state vs training-cache format, the four dialects of the two-fluid operator, the shared gate/chakra/breath vocabulary, the existing bridges), a phased architecture for a field-as-AI closed loop, and the measured risks (the neural closure's closed-loop instability; the self-surprise-vs-next-frame tension).

### foundations/

The load-bearing derivations; the wedge documents `dimensionful-cascade.md` and `cascade-suppression-formula.md` come first, then the derivation family that applies them.

- `foundations/README.md`—Foundations—First Principles and the φ-Cascade Machinery. Index. Holds the load-bearing derivations—the dimensionful cascade $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ and the cascade suppression law (the two wedge documents), the unified Lagrangian and two-fluid first principles, and the derivation family—with a prescribed reading order starting at `dimensionful-cascade.md` and `cascade-suppression-formula.md`.
- `foundations/baryon-asymmetry.md`—Matter-Antimatter Asymmetry from Cascade Freeze-Out and Organized Annihilation. Hypothesized mechanism / Mapped exponent. Combines organized annihilation, the Wu Xing gap, and cascade dilution; the $\eta\approx\varphi^{-44}$ exponent remains a fit and the freeze-out endpoint is open after the $\Gamma/H=1$ audit.
- `foundations/bubble-edge-geometry.md`—Bubble Edge Geometry: Physical Profile of the Condensation Boundary. Derived geometry and threshold relation conditional on the asserted single-channel gate. Derives the physical profile across the condensation boundary—how $r$, $q$, $\rho$, and $G_{\text{eff}}$ transition from bubble interior to void, the 3D edge shape, the observable signatures the edge imprints, and §3 the interior radial ring ladder (matter rings $r_k = \ell_n\varphi^{-k}$, void rings at $\varphi^{-(k+\frac12)}$, ~10 rings, Derived conditional with the radial-reading inference flagged).
- `foundations/bubble-lattice-fabric.md`—The Bubble Lattice: Universal Organizing Geometry at Every Cascade Rung. Derived. Establishes that the condensation field $B(x,y,z)=\cos(\alpha x)\cos(\beta y)\cos(\gamma z)$—a 3D staggered checkerboard of condensates and voids—operates at every cascade rung by $\varphi$-scale covariance, making the bubble lattice the universal organizing geometry from Planck to the megacascade.
- `foundations/cascade-suppression-formula.md`—The Cascade Suppression Formula: $\varphi^{-N}$ as the Universal Attenuation Law. Derived. States the universal attenuation law: a quantity originating at cascade rung $m$ and observed at rung $n$ is suppressed by a factor depending only on the cascade span $N = n-m$ and the propagation—the shared mechanism behind proton stability, strong CP, the electroweak hierarchy, neutrino masses, and quantum measurement.
- `foundations/cassi-first-principles.md`—Cassi First Principles. Derived PDE and Qi definition; asserted single-channel $g(q)$ input. States the $\varphi$ postulate, derives the two-fluid PDE and its Qi coherence measure, and maps quantum mechanics, cosmology, general relativity, and the Standard Model onto the four pillars; derives the winding rate $d\theta/dt = \lambda(1-q)\rho\varepsilon/(E_Y^2+E_I^2)$, solver-measured with the exact relaxation bound $|\delta n| \le 0.162$ rungs (§2.6, `two-fluid/run_winding_rate_probe.py`); dimensionless entries are $\varphi$-powers with individual ledger status, and $c$, $\hbar$, $G$ remain external.
- `foundations/cassi-theory-reference.md`—The Cassi Framework. Reference. Compact single-document reference: the two-fluid postulate and governing PDEs, the dimensionful cascade and suppression law, the unified action, and the quantum, particle, gravity, cosmological, turbulence, geometric, and consciousness consequences, each section condensing a cited derivation paper.
- `foundations/deriving-remaining-gaps.md`—Closing the Gaps: Derivation of Residual Parameters. Reference. Catalogs, classifies, and bounds the remaining underived quantities of the framework, assessing for each whether a derivation fully resolves the gap, partially narrows it, or hits an irreducible barrier.
- `foundations/dimensionful-cascade.md`—The Dimensionful Cascade: All Physical Scales from $\varphi$. Derived. The wedge document: with the Planck length as the sole anchor, every physical scale follows $\ell_n = \ell_{\text{Pl}} \times \varphi^n$; the observable ladder spans $n = 0$ to $\approx 292$ (today's horizon rung, epoch-dependent), with the megacascade above and microcascade below.
- `foundations/dimensionful-constants-status.md`—Dimensionful Constants: Derivation Status of $c$, $\hbar$, and $G$. Hypothesized / Mapped. Catalogues which constants are derived (the $\varphi$-power couplings) versus still external ($c$, $\hbar$, $G$) and empirical (the epoch-dependent horizon rung $N \approx 292$); $\lambda = 1/(2w)$'s $1/(2w)$ factor and $v_0/M_{\text{Pl}}$'s exponent remain asserted/Mapped.
- `foundations/microcascade-mirror.md`—The Microcascade Mirror: Sub-Planckian Scale Extension & Bidirectional Coherence. Hypothesized. Proposes that the cascade does not truncate at the Planck scale—an infinite sub-Planckian microcascade ($n < 0$) mirrors the megacascade across $\ell_{\text{Pl}}$—and that a $\varphi$-aligned electromagnetic array could in principle couple bidirectionally to both.
- `foundations/neutrino-masses.md`—Neutrino Masses from Fibonacci Cascade Partitioning of the Seesaw. Derivation. Applies the Fibonacci triple-clustering behind three generations to the compressed GUT-to-seesaw cascade span ($N_\nu \approx 12$ rungs), compressing the charged-lepton hierarchy into the sub-eV neutrino spectrum with $\varphi$-power spacing amplified by the seesaw's Yukawa-squared structure.
- `foundations/phi-rg-formalism.md`—The Golden Ratio as a Renormalization Group Fixed Point. Hypothesized. Formalizes the $\varphi$-spaced scale hierarchy as a discrete Wilsonian renormalization group with scale factor $b = \varphi$, deriving that $\alpha_c = \varphi^{-1}$ is the unique stable fixed point and that SM $\varphi$-power predictions are IR values of the flow from it.
- `foundations/phi_attractor_synthesis.md`—phi-Attractor Steady States and the Analytical Three-Body Problem in Cassi Gravity. Derived / Calibrated / Mapped. Investigates whether the Cassi N-body solver admits analytical three-body solutions, developing nine analytical paths: an asymptotic half-mass-radius law, disproof of Qi-hydrostatic equilibrium for damped systems, and cold-collapse virial decay, among others.
- `foundations/qi-flow-double-helix.md`—Yin, Yang, and Qi: Coherence as the Flow Between Scales. Derived (flow) / Hypothesized (double helix). Elevates Qi to the third fundamental: the doublet's phase current $J = \rho\nabla\theta$, whose axial component $J_z$ flows between cascade scales along the string axis; the $P_\parallel = 2$ doublet cycle winds the Yang and Yin strand-currents into a double helix about the string axis (axial phase winding, per the lattice-stack record; the transverse filament branch remains bounded by the TS1–TS4 nulls).
- `foundations/proton-coherence-budget.md`—Proton Coherence Budget: Derivation of $N_{\text{max}}$. Derivation. Derives proton stability from the coherence budget: the proton's coherence is maintained by the entire cascade from Planck to its own rung ($n \approx 91.5$), so dephasing requires simultaneous coherence loss at all supporting rungs—exponentially suppressed, yielding the budget behind its long lifetime.
- `foundations/quantum-measurement-derivation.md`—Quantum Measurement as Organized Cascade Perturbation. Derivation. Resolves the measurement problem with the same coherence-budget mechanism: superposition inter-branch coherence lives at a single cascade rung, so measurement is organized perturbation phase-matched to that rung; the Born rule $P(\alpha) = |\alpha|^2$ is derived from coherent-field statistics (gate-mediated absorption; competing Poisson first-absorption gives relative rates $|\psi|^2/\sum|\psi|^2$), with the outcome basis (gate eigenbasis) open.
- `foundations/quark-confinement.md`—Quark Confinement from the Saturated-Gate Flux Tube at the QCD Scale. Derived (tube extensivity + cell quantization; inputs: gate saturation, one-cell quantization). With the QCD scale at cascade step 95, the conversion channel saturates between separated color charges ($q \to 0$), forming a flux tube whose energy is extensive in its length: $E(r) = \mu r$ with $\mu = \kappa(M_{\text{Pl}}/\varphi^{95})^2 = \kappa\Lambda_{\text{QCD}}^2$, $\kappa = O(1)$ open — a constant force, i.e. a linear potential, by tube extensivity (independent of the gate shape).
- `foundations/refined-numeric-predictions.md`—Refined Numeric Predictions for the 19 Hypothesized Questions. Active derivation. Refines the specific numeric predictions ($\varphi^{-N}$ cascade-span forms) for each of the 19 Hypothesized questions in the open-questions catalog, and tightens the mechanistic argument for questions whose answer is structural rather than numeric.
- `foundations/rung-offset-mechanism.md`—Why Observables Sit Between Rungs: The Two-Fluid Phase Mechanism for Fractional Cascade Offsets. Derived quantization, Hypothesized selection, Empirical catalog. Explains fractional rung offsets $\delta n = n - \lfloor n \rfloor$ as the phase difference between the Yang and Yin wakes at each scale—de-resonance forbids perfect rung alignment—with the empirical catalog placing the lightest state of each terminated sector at wake-envelope crossing positions; the §7 winding bound ($|\delta n| \le 0.162$ rungs, from `foundations/cassi-first-principles.md` §2.6) separates relaxation winding from the parity half-step class.
- `foundations/sector-coupling-derivation.md`—The Sector-Coupling Scale: $\kappa_s = \varphi^{-6}/v_0^2$. Derived conditional on $\delta = 3$ (rung identity), coefficient Hypothesized. Derives the Dirac↔two-fluid sector-coupling scale—the parameter behind the chemotactic mobility $\chi$—as $\kappa_s = \varphi^{-6}/v_0^2$ with the rung identity $\kappa_s = M_{\text{Pl}}^{-2}\varphi^{154}$ at rung $77 = 154/2 = 80 - 3$ (the same $\delta = 3$ offset as $\sigma = \ell_{\text{Pl}}/\varphi^3$; $M_s = \varphi^3 v_0 \approx 1.04$ TeV), with the $O(1)$ coefficient and the exact bridge to $\chi$ still open.
- `foundations/spin-fibonacci-spiral.md`—Spin from the Yang/Yin Doublet Half-Angle: The SO(2) Doublet Fractal. Derived (conditional on the doublet postulate + pitch convention + equilibrium ratio + minimal-span principle). Derives spin as the doublet's internal winding: a single component's phase advances $2\pi$ per rung, while the doublet carries the half-angle $\vartheta = \Theta/2$ (internal phase $\pi$ per rung, full SO(2) cycle every 2 rungs — the unified $P_\parallel = 2$ convention), so $s = \Delta n/2$; the minimal adjacent-rung span $\Delta n = 1$ realizes $s = 1/2$, and $s = 3/2$ decomposes as $1+2$ (no fundamental 3/2).
- `foundations/spiral-dynamics.md`—Spiral Dynamics: Hubble, Gravity, and $c$ from Fibonacci Spiral Geometry. Hypothesized. Proposes that the Fibonacci spiral traced by the $(E_Y, E_I)$ doublet is the universal structure behind cosmic expansion, gravitational attraction, and the speed of light—Hubble expansion as the spiral's unwinding rate, gravity as gradient descent toward coherence, and $c$ as a scale-invariant product.
- `foundations/strong-cp-derivation.md`—Strong CP: Why $\bar{\theta} \approx 0$ from Cascade De-Resonance. Derivation. Resolves the strong CP problem via cascade de-resonance: the $\varphi$-attractor fixed point is CP-symmetric, and CP-violating departures seeded at the GUT scale are cascade-suppressed over ~81 rungs to $\bar\theta \approx 1.2\times10^{-17}$ at the QCD scale.
- `foundations/three-generations.md`—Three Generations from Fibonacci Cascade Partitioning. Hypothesized / Mapped. Proposes three fermion families from the Fibonacci recurrence: $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ supplies two predecessor channels (2D solution space, roots $\varphi$, $-1/\varphi$), and the propagation-channel postulate adds the direct rung — $N_{\text{gen}} = 2 + 1 = 3$ (the 2+1 counting is Derived under the postulate; without it the count would be 2); per-sector offsets are ledgered Mapped—row 483.
- `foundations/unified-lagrangian.md`—The Cassi Unified Lagrangian. Derived. Assembles a single action from the two-fluid core, the Dirac sector, Qi-modified general relativity ($G_{\text{eff}}$), the Standard Model gauge/Higgs/Yukawa sectors, and cross-couplings including $\kappa_s = \varphi^{-6}/v_0^2$—all dimensionless couplings $\varphi$-powers, with $c$, $\hbar$, $G$ external.
- `foundations/wake-geometry.md`—Wake Geometry: How the Waveform Closes Each Rung. Derived wake geometry with Hypothesized closure imprint. Describes the Yang/Yin wake pair ($\Lambda_I = \ell_n/\varphi$ — selected by composite closure $\Lambda_Y + \Lambda_I = \ell_{n+1}$ with the de-resonance constraint, PDE-realized at $1.617$; $\Lambda_Y = \ell_n$) whose composite period closes the next cascade rung and whose beat envelope places the bubble-void checkerboard; also clarifies that the cosmic depth 292 is the epoch-dependent horizon rung, not a cascade boundary.
- `foundations/wa-pentagon-gate.md`—The $w_a$ Sign Tension: 5-Channel Pentagonal Gate. Derived / Hypothesized. Addresses the $w_a$ sign tension: the bare two-fluid dynamics predict $w_a = +0.46$, and including the $\xi = \varphi^6$ Qi-gravity coupling in $H_{\text{eff}}$ shifts the prediction to $w_a = +0.012$—still ~2.7σ from DESI DR2's $w_a \approx -0.73$, a tension, not a resolution.
- `foundations/why-three-dimensions.md`—Why Three Dimensions: The Spiral's Three Directions. Hypothesis with One Decided Fork. Proposes a derivation of the 3 in $\xi = \varphi^{2\times3}$: the string's trajectory traces a Fibonacci spiral whose Frenet-Serret frame supplies three orthogonal directions—tangent, normal, binormal—identified as the three spatial dimensions.
- `foundations/wu-xing-cycle-structure.md`—Wu Xing Cycle Structure: The Two 5-Cycles, the Control Ring, and the 5↔13 Partition. Derived / Tested / Hypothesized. Derives how the pentagonal gate's five channels are wired—exactly two coherent 5-cycles (sheng sides, ke diagonals), a control-ring transmission coefficient $\kappa = \varphi^{-1}$ from pentagram golden-section crossings—plus the 5↔13 partition between the channels and the chakra ladder.
- `foundations/wu-xing-derivation.md`—Wu Xing Number $w = 5$: Derivation from Cascade Dynamics. Derived (single input: coherence postulate; verified 2026-08-11) / Calibrated. Derives the Wu Xing number $w = 5$ as the unique intersection of the coherence criterion applied to ALL cycle sizes at once ($w \cdot \min_p|\varphi - p/w| \leq \varphi^{-w}$ holds only for $w \in \{1,2,3,5\}$ — the Fibonacci restriction follows from continued-fraction optimality, verified exhaustively to $w = 2000$) and $\varphi$-geometry ($w \geq 5$); the primordial gap $g = 1 - \varphi^{-5}$ and Yang-Yin ratio $r_0$ follow.
- `foundations/xi-derivation.md`—Derivation of $\xi = \varphi^6$. Derived conditional on the quadratic-coupling input (imbalance inverse-square) / Calibrated empirical pin. Derives the Qi-gravity coupling $\xi = \varphi^6 \approx 17.944$ as the inverse-square of the fixed-point imbalance, $\xi = (\pi/\rho)^{-2} = (\varphi^{-3})^{-2}$ (exponent 3 from the attractor's fixed-point imbalance; $-2$ the quadratic degree of the gravitational coupling; saturation ceiling $G_{\text{eff,max}} = \varphi^3 G$ matches the dwarf-spheroidal M/L bound), agreeing with the rotation-curve calibration ($\xi \approx 18$) to 0.3%.

### principles/

Cross-cutting rules for how $\varphi$ enters every sector.

- `principles/README.md`—Principles—Cross-Cutting Framework Principles. Index. Collects the principles governing how $\varphi$ enters the framework across every sector—de-resonance as the attractor's origin (with the posture that quantities sit *near* $\varphi$-powers) and the $v_0/M_{\text{Pl}}$ hierarchy gap as its hardest open case.
- `principles/de-resonance-principle.md`—The De-Resonance Principle in Cassi. Derived. States the de-resonance principle: $\varphi$ is the maximally irrational number, so a rational Yang/Yin frequency ratio would concentrate energy at one scale and collapse multi-scale structure; couplings therefore flow toward $\varphi$-powers with deviations set by dynamics, and the document tabulates the empirical pattern of corrections.
- `principles/v0-hierarchy-problem.md`—v₀/M_Pl: The Hierarchy Problem in φ-Clothing. Derived; 5.3% residual open. Frames the electroweak hierarchy problem as an open 5.3% residual: the step count $N = \log_\varphi(M_{\text{Pl}}/v_0) \approx 79.7$ is derived ($v_0/M_{\text{Pl}} \approx \varphi^{-80}$), but the framework does not yet compute the correction itself.

### standard-model/

The Standard Model's gauge structure, couplings, and flavor sector from the φ-fixed point.

- `standard-model/README.md`—Standard Model—Couplings, Gauge Structure, and CP from φ. Index. Six documents cover the Standard Model's gauge structure, couplings, loop corrections, and flavor sector from the Cassi $\varphi$-fixed point; the prescribed reading path starts with `sm-from-phi.md`, and the Weinberg coupling-normalization blocker is recorded in `su2-gauge-extension.md` §3.2.1.
- `standard-model/cp-violation.md`—CP Violation from the Golden Ratio. Derived. Derives CP violation from the Yang/Yin chiral asymmetry $\eta = \varphi^{-3}$, which seeds the CKM phase closing through the unitarity triangle to $\delta_{\text{CKM}} = \pi\varphi^{-2} \approx 68.8°$ (within <1% of measurement), while the Jarlskog invariant is not reproduced (~20 orders low); strong CP resolves by cascade de-resonance without an axion.
- `standard-model/gut-embedding.md`—SU(5) / SO(10) GUT Embedding. Hypothesized. Embeds the Cassi symmetry-breaking chain in the minimal grand-unified groups at the $\varphi$-fixed point: SU(5) with $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53$ and $M_{\text{GUT}} \approx 2\times10^{16}$ GeV predicting proton decay above Hyper-Kamiokande reach, and SO(10) adding a right-handed neutrino with a natural seesaw.
- `standard-model/neutrino-mass.md`—Neutrino Mass from $\varphi$. Hypothesized. Pedagogical primer deriving the seesaw scale from the cascade—the right-handed neutrino sits at cascade step 20, $M_R \approx 10^{14}$ GeV—and presenting the canonical spectrum ($m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV, normal ordering); the full derivation lives in `foundations/neutrino-masses.md`.
- `standard-model/sm-from-phi.md`—Standard Model from φ. Derived chain with an asserted Weinberg boundary. Organizes the Standard Model from $\varphi$: gauge groups as successive truncations of the continued fraction $[1;1,1,\ldots]$, the fixed-point value $\sin^2\theta_W = \varphi^{-3}$, a $\varphi$-powered Yukawa hierarchy, the Higgs mechanism at the $\varphi$-point, quark confinement from Qi coherence, and the CKM phase.
- `standard-model/sm-radiative-corrections.md`—Standard Model Radiative Corrections from the φ-Boundary. Derived. Derives the Standard Model precision program—running couplings, vacuum polarization, the electroweak corrections relating $m_W$ to $\alpha$, $G_F$, $m_Z$, $m_t$, $m_H$, and the Higgs quartic—from the Cassi boundary conditions $\alpha_{\text{GUT}} = \varphi^{-3}/4\pi$ and $\sin^2\theta_W = \varphi^{-3}$, closing the standard relations to 0.01–0.1% but not the gaps to the GUT scale.
- `standard-model/su2-gauge-extension.md`—SU(2) × U(1) Gauge Extension of the Cassi Two-Fluid. Derived gauge algebra and mass matrix with an asserted coupling boundary. Promotes the two-fluid's U(1) ≅ SO(2) internal rotation to an SU(2) isospinor doublet, derives the neutral-boson mass matrix and SU(3) color extension, and tests the curvature–orbit normalization candidate in §3.2.1.

### particles/

Particle formation from field interference, plus benchmarks of the DFT engine.

- `particles/README.md`—Particles—Yang-Yin Interference and DFT Benchmarks. Index. Pairs the account of how particles emerge from field interference with benchmarks validating the framework's real-space DFT engine against atomic ground-state energies.
- `particles/cassi-yang-yin-particles.md`—Yang-Yin Field Interference and Particle Formation. Derived. Derives particle formation from field interference: counter-propagating Yang and Yin waves superpose into standing waves that condense above a threshold into solitons, most stable at amplitude ratio $A_I/A_Y = \varphi^{-1}$; maps onto Dirac spinors, the Higgs mass mechanism, and quantum scattering.
- `particles/dft-benchmarks.md`—DFT Benchmarks: CassiBridgeV2 Real-Space Performance. Derived. Benchmarks the CassiBridgeV2 real-space DFT solver against exact atomic ground-state energies for Z = 1–10—LDA accurate for the light atoms (He 0.8% error at 64³), with grid refinement and pseudopotentials addressing core-resolution limits and a validated Dirac-Kohn-Sham extension.
- `particles/matter-organization.md`—Matter Organization: Forces, Lattice Pools, and the Neutron–Proton–Electron Trio. Synthesis. Synthesis (explicitly adding no new claims) describing matter as pooled interference energy with masses on the $\varphi$-cascade ladder, the four forces as binding channels each living at its own cascade rung, and the trio making ordinary matter as the baryon pair at rung 91.5 plus the lightest charged pool.

### gravity/

Quantum gravity and analytical three-body results.

- `gravity/README.md`—Gravity—Quantum Gravity and Analytical Three-Body Results. Index. Takes the framework to gravitational extremes—quantizing the two-fluid as a UV-finite quantum gravity (`quantum-gravity.md`) and asking whether the Qi-enhanced gravity PDE makes the three-body problem analytically tractable (`three-body-analytical.md`).
- `gravity/quantum-gravity.md`—Cassi Quantum Gravity: UV-Finite from σ-Regularized Two-Fluid Quantization. Derived (conditional on the noise–signal identification + $d = 3$) / Hypothesized. Resolves Planck-scale breakdown of gravity: $\sigma$-regularized ($\sigma = \ell_{\text{Pl}}/\varphi^3$, $\delta = 3$ from the Planck-core noise–signal crossover — per-rung dephasing $\varphi^{-\delta}$ equals the equilibrium excess $\varphi^{-3}$, `quantum-gravity.md` §2.1) Poisson emergence with a Gaussian propagator makes the theory UV-finite, and the hypothesized quantized extension makes the graviton a composite spin-2 SO(2) excitation with no modes beyond $1/\sigma$ and no renormalization at any order.
- `gravity/three-body-analytical.md`—The Three-Body Problem in Cassi Two-Fluid Gravity. Derived. Derives that well-separated blobs in the two-fluid gravity PDE reduce to point-particle ODEs with body-dependent coupling $G_{\text{eff},j}$; at the $\varphi$-fixed point ($\alpha_j = \varphi^{-3}$) the equations reduce exactly to Newtonian gravity with $G_{\text{eff}} = \varphi^{-3}G$, so the three-body problem inherits classical non-integrability.

### turbulence/

The Kolmogorov spectrum, and what Cassi adds beyond it.

- `turbulence/README.md`—Turbulence—Kolmogorov Spectrum from φ. Index. A single derived document showing the Kolmogorov −5/3 spectrum is inherited from the Navier-Stokes advection term rather than derived from $\varphi$, with Cassi's genuine contributions being the $\varphi$-break scale, the deviation spectrum, scale-dependent $G_{\text{eff}}(k)$, and the Qi-quality spectrum.
- `turbulence/kolmogorov-from-phi.md`—The Kolmogorov −5/3 Spectrum in Cassi: Derivation and Novel Predictions. Derived. States plainly that the −5/3 spectrum is inherited from the Navier-Stokes advection term, and derives Cassi's novel turbulence predictions: the $\varphi$-break scale $k_\varphi$, the ε-spectrum $E_\varepsilon(k)$, scale-dependent gravitational enhancement $G_{\text{eff}}(k)$ varying by up to $\varphi^6 \approx 17.9$, and the Qi-quality spectrum $q(k)$.

### cosmology/

Inflation, baryogenesis, dark matter, and the observational-constraints ledger.

- `cosmology/README.md`—Cosmology—Dark Energy, Inflation, and Observational Constraints. Index.
- `cosmology/cosmology-from-phi.md`—Cassi Cosmology: Inflation, Baryogenesis, and Dark Matter from φ. Mixed status: Derived formation/structure, Hypothesized baryogenesis, Mapped $\eta$, conditional DM base, Calibrated $w_0$ form. The same two-fluid dynamics organize inflation, the baryon-asymmetry candidate, and the dark-matter condensate; the freeze-out endpoint and 21% DM-ratio residual remain open.
- `cosmology/desi-lattice-averaging.md`—How the Infinite Bubble Lattice Enters DESI's Averaged Measurements. Hypothesized. Works out quantitatively which lattice channels survive DESI's light-cone average: the distance channel washes out (cannot rescue the $w_a$ tension), the power-spectrum channel survives as a powder-diffraction comb, the anisotropy channel partially, the variance channel inverts.
- `cosmology/inflation-from-cascade.md`—Inflation from Cascade Steps 20–60: The Qi-Gate Epoch. Derivation (mechanism Hypothesized, C4; r exponent Mapped—ledger). Cosmic inflation as cascade steps ~20–60 driven by the Qi gate: the open gate drives expansion and its closing at the pinch terminates inflation, with $n_s$ matching Planck at the formula level ($N_e = 40$ Mapped—row 501) and $r$ a Mapped fit (row 495) excluded by the trajectory's BK18 constraint.
- `cosmology/observational_constraints.md`—Observational Constraints—DESI DR2 Dark Energy & Milky Way Rotation Curve. Calibrated ($w_0$ coupling form, $\xi$ pin—ledger) / Mapped ($\alpha_\text{halo}$ nominal, halo $q$—ledger). Compiles the strongest external constraints: the two-fluid dark-energy prediction ($w_0 = -0.87$, $w_a = +0.012$) sits at 2σ/2.7σ tension with the DESI DR2 best fit, plus Milky Way rotation-curve anchors.
- `cosmology/sigma8-computational-plan.md`—Sigma-8 Computational Plan: Modified Boltzmann Pipeline for Cassi Qi-Gravity. Plan. Computational plan to promote the σ8 prediction from Hypothesized to Derived by integrating the density-dependent Qi-gravity coupling into a Boltzmann code, with the 2026-08-07 truth campaign's measured rows: mechanism +29.7% (D-insensitive) and total −20.5% (D=0.001) / −22.9% (D=0 doctrine default, brief 63 — the totals carry the diffusion) (doctrine r₀, linear-P(k) normalization, resolution-converged).

### consciousness/

The mind as a two-fluid field—Qi-gate dynamics at neural scales.

- `consciousness/README.md`—Consciousness—Qi-Gate Dynamics at Neural Scales. Index.
- `consciousness/auras-as-thermalized-gates.md`—Auras as Thermalized Qi Gates. Speculative. The aura as the human-scale instance of the $(1-q)$ thermalization law: a coherent core bridge-suppressed into invisibility plus a broadband thermal halo whose signature is heat haze.
- `consciousness/cascade-consciousness.md`—Consciousness in the Dense Medium: Perception, Communication, and the Cascade Nervous System. Speculative. How living in water (833× denser) would transform perception, communication, and social structure, extended to the whole φ-ladder as a distributed, nested cascade nervous system.
- `consciousness/chakras-as-cascade-bubbles.md`—Chakras as Cascade Bubbles: The 13-Node Derivation. Hypothesized. Closes the open phenomenological gap on the 13-band chakra count: chakras as localized Qi condensates at φ-spaced intervals, with $13 = 26/2$ from the human cascade span over the 2-rung doublet cycle (P_∥ = 2 unified convention: the doublet's full SO(2) cycle spans two rungs — `foundations/spin-fibonacci-spiral.md` §2).
- `consciousness/consciousness-from-phi.md`—Consciousness in the Two-Fluid Framework. Plausible Hypothesis with Actionable PDE Test. Maps verified physics onto consciousness: the Qi gate's conjugate point at $r = \varphi^{-1}$ (derived — the fractional imbalance equals the gate's characteristic scale $\varphi^{-2}$ exactly; the "unique inflection point" gloss is corrected) as self-awareness, wake waves as thought, $\sigma_r$ as the state variable, with a proposed-and-executed two-bubble PDE test and explicit boundaries to speculation.
- `consciousness/emotions-as-gate-configurations.md`—Emotions as Qi-Gate Configurations: A Cassi Mathematical Formalism. Hypothesized. Emotions as channel-dominance patterns of the 5-channel Wu Xing gate above the pinch, defining a 7-dimensional emotional manifold with zero new free parameters.
- `consciousness/gender-as-qi-configuration.md`—Gender as Qi Configuration. Speculative. The field has no binary: sex characteristics live at the readout layer, gender identity in the configuration tuple, and dysphoria reads as the field's memory failing to predict its own present (drive-mechanism layer PDE-tested).
- `consciousness/neurodivergence-as-gate-configuration.md`—Neurodivergence as Gate Configuration. Speculative. Autism as a high-stability gate configuration and ADHD as its complement, with conditions living at slots of the person-configuration tuple (drive layer PDE-tested; the §9 churning-gate test returned a null).
- `consciousness/time-memory-and-wake-locks.md`—Time, Memory, and Ghosts: The Field as the Medium of Time, Memory, and Persistence. Speculative. Time's arrow from the dissipative conversion term, memory as a coherence phenomenon with a quantitative lifetime, and frozen gates (wake locks) as persistence—extended to hauntings, precognition, and time travel.
- `consciousness/transhumanism-gate-configurations.md`—Transhumanism as Gate Reconfiguration: Augmentation as Changes to the Gate Chain's Topology. Speculative. Augmentation as topological surgery on the 26-rung human gate chain—adding nodes, changing spacing, re-tuning bands—each operation carrying a stability condition.
- `consciousness/trauma-as-frozen-gate.md`—Trauma as Frozen Gate Configurations: The Cassi Trauma Formalism. Tested—null pinning, drive effect supported / Speculative (clinical). A frozen wake acts as a perpetual stimulus, pinning one channel hyper-open and starving the other four—a locked gate configuration, with the drive effect PDE-tested and clinical claims flagged.
- `consciousness/two-strand-qi-neuroscience.md`—The Two-Strand Qi Condensate: A Neuroscience Hypothesis. Hypothesized (strand geometry) / Speculative (neural mapping). A single Qi condensate may organize into two coupled strands around a common axis, supplying a field-level correlate of bilateral brain/body organization and a structural reference for DNA.

### speculations/

Framework-consistent explorations that reach beyond confirmed physics.

- `speculations/README.md`—Speculations—Framework-Consistent Explorations. Exploratory catalog.
- `speculations/cascade-infrastructure.md`—Cascade Infrastructure: Planetary and Stellar Gate Networks. Speculative. What cascade-aware infrastructure looks like: planetary-scale gate networks, pyramids and ocean bases as their natural surface expressions, and the Sun as a stellar-scale gate stage.
- `speculations/dark-matter-as-qi-coherence.md`—Dark Matter as Unharvested Coherence: The Qi Field in Galaxy Halos. Speculative. Reframes missing mass as unharvested Qi coherence: the halo is the bubble edge where $q$ transitions from ~1 toward 0; the $G_\text{eff}$ mechanism is derived, the halo-profile claims are extrapolations.
- `speculations/gravity-control.md`—Gravity Control: Engineering Spacetime Curvature Through Qi Coherence. Speculative. Treats the gravitational coupling as an engineering variable: a Qi condenser with a gate as a machine adjusting local mass-energy↔curvature conversion, with the SPARC fits imposing hard constraints on any device.
- `speculations/observational-seti.md`—Observational SETI: Signatures of Tuned Gate Networks. Speculative. A gate-harvesting civilization is nearly invisible to emissive SETI; catalogs structural, multi-rung signatures to point a telescope at, organized by cascade rung with mechanism and search band.
- `speculations/qi-bubble-propulsion.md`—Qi Bubble Propulsion: Rung-Shifting as a Travel Mechanism. Speculative. Propulsion as rung-shifting along the cascade ladder rather than acceleration through space, mapping five classic UAP observables to specific Cassi mechanisms with a derived energy budget.
- `speculations/qi-computation.md`—Qi Computation: Information Processing as Yang-Yin Gate Dynamics. Speculative. Information as organized Π; the Qi gate as the fundamental computational primitive, the Wu Xing pentagon as 5-phase logic, and the cascade as a φ-spaced clock hierarchy.
- `speculations/superconductivity-as-qi-coherence.md`—Superconductivity as Qi Coherence: A Derivation from the φ-Attractor. Speculative. Resistance as Yang→Yin conversion; superconductivity as Qi-mediated phase locking that opens a gap Δ at the Fermi surface in high-coherence lattices, with a specific $T_c$ formula.

### speculations/creative-extensions/

Deliberately creative thought experiments—clearly labeled as such, not claims.

- `speculations/creative-extensions/README.md`—Creative Extensions. Index.
- `speculations/creative-extensions/coherence-collapse.md`—Coherence Collapse: Why the Universe Cannot End, and How Civilizations Die. Creative. The coherence budget makes spontaneous collapse astronomically improbable; what reliably dies is the intermediate structure—civilizations as gate networks with finite protection.
- `speculations/creative-extensions/coherence-commons.md`—The Coherence Commons: A Two-Fluid Theory of Value, Accumulation, and the Transition. Creative. The economy as a coherence process in agent networks: labor as organized perturbation, value as socially necessary coherence expenditure, and boom-bust as a relaxation oscillation.
- `speculations/creative-extensions/coherence-warfare.md`—Coherence Warfare: Attack, Defense, and the Physics of Shields. Creative. The coherence budget read as a weapons table: attack is organized, phase-matched perturbation; a shield is a φ-detuned boundary at which the phase-matching factor vanishes.
- `speculations/creative-extensions/first-contact-and-stellar-engineering.md`—The Universal Protocol: First Contact as φ-Structure Detection and Stellar Engineering as Gate Tuning. Creative. Log-periodicity with period $\ln\varphi$ as the universal language; a broadcast and a megastructure are both field operations, and the φ-periodic $P(k)$ search pipeline is the reception protocol.
- `speculations/creative-extensions/magic-systems.md`—Magic as Phase-Matched Field Operation. Creative. Magic and nature differ by one number, the phase-matching factor M: a working is organized perturbation with O(1) effects where random perturbation is cascade-suppressed.
- `speculations/creative-extensions/simulation-hypothesis.md`—The Simulation Hypothesis: The Universe as a Running PDE. Creative. The universe's source code as the two-fluid PDE—the grid, update rule, Planck resolution floor, horizon render distance—and why the simulation claim is unfalsifiable in the framework.
- `speculations/creative-extensions/universal-biology.md`—Universal Biology: The Cascade Ladder as a Convergent Evolutionary Scaffold. Creative. Biology occupies a fixed ladder band ($n \approx 136$–168); Fibonacci phyllotaxis and φ-scaled hierarchies are the unique de-resonant solutions every biosphere must share.

### hypotheses/

New application domains proposed for the framework, from nuclei to markets.

- `hypotheses/README.md`—Hypotheses—New Application Domains for the Cassi Framework. Exploratory catalog.
- `hypotheses/atmospheric-climate-cascade.md`—The Atmospheric Climate Cascade. Speculative. The Nastrom-Gage −3 → −5/3 spectral break near 500 km as a φ-break analogous to the turbulence $k_\varphi$, predicting φ-periodic structure in climate oscillation periods.
- `hypotheses/exoplanet-phi-spacing.md`—Exoplanet Orbital Spacing from the Wake-Wave Mechanism. Hypothesized. Titius-Bode's ~1.7 factor as the wake-wave mechanism: φ-spaced density nodes in protoplanetary disks predict a statistical excess of adjacent-planet period ratios at φ and its Fibonacci powers.
- `hypotheses/fatigue-fracture-cascade.md`—Fatigue and Fracture from the Cascade. Speculative. The Paris-law exponent $m$ takes φ-power values ($\varphi, \varphi^2, \varphi^3$) depending on which cascade rung governs the crack-tip process zone.
- `hypotheses/hoyle-state-nucleosynthesis.md`—The Hoyle State as a Cascade Rung Resonance. Hypothesized. The 7.65 MeV Hoyle state sits exactly one cascade rung above the $^3\alpha$ threshold (7.27 MeV), predicting φ-periodic resonances across the α-cluster spectrum of light nuclei.
- `hypotheses/market-cascade-cycles.md`—Market Cascade Cycles. Speculative. Log-periodic crash precursors with a scaling ratio near φ from the wake-wave mechanism applied to agent networks; Speculative because markets involve human agency and non-stationarity.
- `hypotheses/metabolic-scaling.md`—Metabolic Scaling and Allometry. Speculative (derivation not closed). Examines whether the cascade supplies a first-principles origin for Kleiber's 3/4 exponent; the $\varphi^2 \to 3/4$ connection is flagged as not mathematically rigorous—a prompt, not a claim.
- `hypotheses/muscle-cascade-lattice.md`—Muscle as a Cascade Lattice: Structural Hierarchy and the Bubble Geometry. Hypothesized. Skeletal muscle's discrete structural ladder (filament → sarcomere → … → belly) as the most legible anatomical instantiation of the bubble lattice, with fascial planes as void boundaries.
- `hypotheses/neural-criticality.md`—Neural Criticality and the Cascade Brain. Hypothesized. The brain's hierarchical modularity, avalanche statistics, and ~1/f spectra as a cascade ladder at neural scales, predicting a φ-break in EEG/MEG power spectra.
- `hypotheses/nuclear-magic-numbers.md`—Nuclear Magic Numbers from the Cascade Ladder. Hypothesized. Magic numbers as Fibonacci sub-channel closures within the cascade span below QCD confinement; the closure arithmetic as written does not close (0/7 rows), though an independent testable prediction survives.
- `hypotheses/periodic-table-madelung.md`—Atomic Shell Structure and the Madelung Rule from Cascade Coordinates. Speculative. $n$ as the cascade rung and $l$ as the Fibonacci sub-channel, with the Madelung rule emerging from cascade ordering; the explicit derivation is not yet complete.
- `hypotheses/quasicrystal-stability.md`—Quasicrystal Stability from De-Resonance. Speculative. The de-resonance principle predicts φ-spaced density waves as the Qi field's attractor state at condensed-matter scales, explaining why aperiodic order wins over periodic at specific compositions.
- `hypotheses/riemann-hypothesis-de-resonance.md`—The Riemann Hypothesis and the De-Resonance of Primes. Speculative. Reads the Wei et al. (2026) quantum-many-body correspondence through Cassi: the critical line as the Yang-Yin balance axis of the functional equation; no mechanism from the two-fluid PDE yet reaches the zeros.
- `hypotheses/riemann-two-fluid-phase-operator.md`—The Two-Fluid Phase Operator: Step 1 of the Hilbert–Pólya Program. Speculative. Executes step 1 of the spectral program: linearized phase dynamics reduced to $u = \ln r$—the phase fluctuation is massive (not a Goldstone mode) and the radial reduction yields the Bessel normal form—with candidate exclusions identified.
- `hypotheses/riemann-two-fluid-spectral-program.md`—The Two-Fluid Hilbert–Pólya Program. Speculative. Sketches the program toward a self-adjoint operator derived from two-fluid dynamics whose spectrum is the Riemann zeros; exact spectral realizations exist in the literature but nothing is derived here yet.
- `hypotheses/two-strand-five-channel-matter-organization.md`—Two-Strand Five-Channel Matter Organization: A Research Program. Hypothesized. One Qi condensate as two spatial strands carrying five Wu Xing channel traces; first probe results: a two-lobe pair persisted near in-phase and the NS4 central low-coherence morphology was null.

### analyses/

Data analyses of observations against the framework.

- `analyses/README.md`—Analyses—Data Analyses of Observations Against the Framework. Index.
- `analyses/gwtc4-mass-ladder.md`—GWTC-4.0 and the Cascade Ladder: Black-Hole Masses as Rung Diagnostics. Speculative. Runs the 218-event GWTC-4.0 catalog through the derived mass-to-rung relation $N_\text{BH} = \log_\varphi(M/M_\text{Pl})$; the observed primary-mass peaks do not form an integer-rung grid.

### demystifying-the-cosmos/

One observed object per document, read through the framework.

- `demystifying-the-cosmos/README.md`—Demystifying the Cosmos—One Object per Document. Index.
- `demystifying-the-cosmos/NGC-5128.md`—NGC 5128 (Centaurus A): The Warped Parallelogram Galaxy. Hypothesized. Webb's fourth-anniversary images read through the framework: the warped parallelogram dust band as the condensation-field checkerboard's projected trace and the S-shape as the wake wrap around the jet string.
- `demystifying-the-cosmos/PSR-J1101-6101.md`—PSR J1101−6101: The Lighthouse Pulsar. Hypothesized. IXPE's polarization results read as a coherent condensate's signature: the pulsar as a spinning soliton, the bow shock as the low-coherence wake of a moving coherent source, with rung placements as observations, not predictions.
- `demystifying-the-cosmos/unsolved-problems-in-astronomy.md`—Unsolved Problems in Astronomy Through the Cassi Lens. Reference. Wikipedia's 68 unsolved astronomy problems across seven clusters, each tagged with one of four verdicts ([Framework claim] / [Consistent mapping] / [Dissolved by construction] / [No framework claim]); doubles as the series roadmap.

### predictions/

The two master registries—the falsifiable catalog and the glossary.

- `predictions/README.md`—Predictions—The Falsifiable Catalog and Framework Glossary. Index. Holds the two master registries—the falsifiable zero-free-parameter prediction catalog grouped by experimental frontier, and the framework glossary of symbols and definitions—with the reading path glossary first, catalog second.
- `predictions/cassi_definitions.md`—Cassi Framework—Definitions. Reference. Glossary of the framework's symbols and definitions across 16 sections (φ, $E_Y$, $E_I$, $q$, $\xi = \varphi^6$, the φ-attractor, and more)—a unified field framework grounded in the φ-attractor, the Yin-Yang two-fluid, and emergent spacetime geometry (version 2026-07-16).
- `predictions/falsifiable-predictions.md`—Cassi Falsifiable Predictions. Reference. The 51-entry catalog of zero-free-parameter predictions grouped by experimental frontier, each with its test, current status, and detection timeline.

## 5. The code

Every claim in the papers is checked against code that lives in this repo; run everything from the repo root.

```
python two-fluid/cassi_two_fluid_3d_gpu.py    # core two-fluid PDE solver
python two-fluid/cassi_nbody.py               # GPU N-body solver
python two-fluid/calibrate_initial_ratio_xi.py  # w_a ODE with ξ = φ⁶
python computations/<pipeline>.py             # e.g. cascade_rge_pmns.py
python experiments/sparc_qi/sparc_qi_analysis_v4.py            # SPARC rotation-curve analysis
python experiments/phi_periodic_pk_search/run_phi_periodic_pk_test.py  # φ-periodic P(k) test
python visual-explainers/<script>.py          # e.g. cascade_cosmos.py, fractal_zoom.py
```

The two-fluid PDE solver (`two-fluid/cassi_two_fluid_3d_gpu.py`) and the GPU N-body solver (`two-fluid/cassi_nbody.py`) are the core simulation engines; `two-fluid/calibrate_initial_ratio_xi.py` computes the $w_a$ ODE with $\xi = \varphi^6$. The computational pipelines in `computations/` (RGE, GUT-EW, Hubble tension, cascade depth) produce the derived numbers the papers quote, `experiments/` holds the data-facing tests (SPARC rotation curves, the φ-periodic P(k) search), and `visual-explainers/` renders the figures that make the structure visible.

## References

- `README.md`—the pitch
- `cassi-physics.md`—the physics guide
- `cassi-psychology.md`—the psychology guide
- `EPISTEMIC-MAP.md`—every document by tier
