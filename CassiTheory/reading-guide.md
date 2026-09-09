# Cassi: Reading Guide and Table of Contents

## Status: Synthesis—September 2026

## Abstract

This document is the complete table of contents of the repository, plus curated reading paths for different kinds of readers. The repository is organized as a document graph: the wedge derivations live in `foundations/`, domain papers in `standard-model/`, `gravity/`, `cosmology/`, `consciousness/`, `turbulence/`, and `particles/` apply them as one-liners, the three master registries at the root track questions, parameters, and predictions, and the code in `two-fluid/`, `computations/`, `experiments/`, and `visual-explainers/` supports every claim. Section 4 is the full inventory; sections 2, 3, and 5 are the reading paths, the registry guide, and the code map.

## 1. The shape of the repository

The repository is a document graph, not a flat pile. `foundations/` holds the principal derivations—the dimensionful cascade and the cascade suppression formula are the wedge documents, and the derivation family built on them. The domain directories apply the wedges to one sector each: `standard-model/` and `particles/` for particle physics, `gravity/` for gravitation, `cosmology/` for the universe, `consciousness/` for the mind, `turbulence/` for fluid behavior, and `principles/` for the cross-cutting rules that govern how $\varphi$ enters everywhere.

- `foundations/`—the wedges and the derivation family (start here as a physicist)
- Domain papers—each applies the wedges to its sector
- Three master registries at the root—questions, parameters, predictions
- `audit.md`—the empirical status of every claim
- Code—`two-fluid/`, `computations/`, `experiments/`, `visual-explainers/`

The three master registries at the root are `open-questions-cassi-answers.md` (which open question of physics the framework addresses, and at what tier), `parameter-inventory.md` (how every parameter is classified), and `predictions/falsifiable-predictions.md` (what should be observed, where, and when). `audit.md` tracks the prediction-versus-experiment status of every claim. Every paper carries a `## Status:` line stating its epistemic tier and date; the tiers are defined in `open-questions-cassi-answers.md` §Epistemic Tiers and indexed repo-wide in `EPISTEMIC-MAP.md`. Numerical claims are checked against cited code or source receipts where available, with runnable paths retained for the computational results.

## 2. Reading paths

Seven paths in; pick the one that matches you.

### The newcomer (no physics background)

Start with the pitch for the origin story, take the plain-language physics guide, learn the vocabulary, and only then browse the predictions.

`README.md` → `cassi-physics.md` §1–3 → `predictions/cassi_definitions.md` (the glossary) → `open-questions-cassi-answers.md` (the Cassi Primer section, plain language) → `predictions/falsifiable-predictions.md` (browse).

### The physicist

Read the physics guide in full, then follow `foundations/README.md`, which prescribes the order: `foundations/dimensionful-cascade.md`, `foundations/cascade-suppression-formula.md`, then the derivation family. The domain applications come next, and the audit last.

`cassi-physics.md` → `foundations/README.md` (order: `foundations/dimensionful-cascade.md`, `foundations/cascade-suppression-formula.md`, then the derivation family) → `standard-model/sm-from-phi.md` → `foundations/quantum-free-fall-correspondence.md` → `gravity/quantum-gravity.md` → `cosmology/cosmology-from-phi.md` → `predictions/falsifiable-predictions.md` → `audit.md`.

### The psychologist, therapist, or mind-curious

The psychology guide is the entry point; the consciousness directory then builds from field physics to specific configurations of the gate.

`README.md` (the origin story) → `cassi-psychology.md` → `consciousness/README.md` → `consciousness/chakras-as-cascade-bubbles.md` → `consciousness/trauma-as-frozen-gate.md` → `consciousness/emotions-as-gate-configurations.md` → `consciousness/gender-as-qi-configuration.md` → `consciousness/neurodivergence-as-gate-configuration.md`.

### The field-intelligence builder

Start with the program criterion, then move from the canonical substrate to the causal state hierarchy and the current probe ledger.

`README.md` §The field-AGI program → `foundations/cassi-first-principles.md` → `foundations/physical-becoming-hierarchy.md` → `foundations/qi-flow-double-helix.md` → `field-experience/probe-outcome-ledger.md`.

### The matter and particle builder

Follow the coherence geometry into the endpoint, support, particle action, and
nine-part qualification boundary. The Cartesian reports establish their
finite-grid results. The continuum report tests the carrier's parity structure,
derives the empty-sector creation obstruction, records independently
reproduced smooth density trapping at selected prepared charges, and closes
with a Mapped conditional baryon benchmark plus a failed complete-mechanism
adjudication.

The separate massive bubble-lattice comparison is indexed in
`foundations/matter-completion-boundary.md` §14 and detailed in
`computations/matter-formation-continuum-report.md` §32. It adds an
$O(4)$ orientation field on $S^3$ and maps the pion, nucleon and Delta mass
references to a massive-model calibration. Its six target-bearing out-of-fit
diagnostics all contradict their inherited thresholds. The added action has
conditional conserved stress and isospin current but no canonical Cassi
stress exchange; its finite-site configuration space
$(S^3)^{N_s}$ is simply connected, so continuum degree and odd
Finkelstein–Rubinstein exchange are not enforced. Quantum state selection,
renormalization and physical particle identity remain open. The degree-zero
excitation returns `DOES NOT EMERGE` through $T=4$ under a qualified
signed-preimage calculation. The geometric controls and numerical comparisons
pass, but no retained sample contains a resolved degree-$+1$/degree-$-1$ pair
for all 16 regular values. This verdict is confined to the supplied action,
impulse and sampled interval. Physical matter formation remains
Hypothesized/Open.

`foundations/yin-yang-qi-dynamical-geometry.md` §7.4 →
`foundations/interscale-stress-attenuation-boundary.md` →
`foundations/endpoint-link-and-localization-boundary.md` →
`foundations/core-trapped-charge-support.md` →
`foundations/particle-stationary-action-closure.md` →
`foundations/matter-completion-boundary.md` →
`computations/matter_completion_boundary_report.md` →
`computations/particle-stationary-bvp-report.md` →
`computations/particle-stationary-q2-recovery-report.md` →
`computations/particle-stationary-precision-v5-report.md` →
`computations/particle-physical-hessian-precision-v2-report.md` →
`computations/particle-carrier-direct-coordinate-report.md` →
`computations/particle-carrier-resolution-recovery-report.md` →
`computations/particle-localized-physical-hessian-report.md` →
`computations/matter-formation-continuum-report.md`.

An optional positive-inertia carrier parent has a signed charge and a
Gaussian particle–antiparticle channel.
Its 31 prescribed-background trajectories pass a standard scalar
mass-quench correspondence check. The parent coefficient and quantum action
normalization remain unselected; the scalar-parent normalization family
is Derived conditional, with numerical consistency checks, and interacting localized formation is open
(`foundations/particle-stationary-action-closure.md` §8.8;
`computations/matter-formation-continuum-report.md` §§8, 12).
The classical parent-vacuum condition and the restriction on neutral
stationary localization follow in
`foundations/particle-stationary-action-closure.md` §8.9. In three dimensions
this scalar ansatz cannot have an energetically stable regular localized
single-frequency state with zero signed charge; this condition differs from
the carrier's gauge neutrality.
The signed-charge radial Hessian and its independent calculation follow in
§8.10 and `computations/matter-formation-continuum-report.md` §10.
All 24 frozen embeddings have positive finite-grid radial curvature, but
the population-16 domain comparisons fail; aggregate radial-domain
qualification is `INCONCLUSIVE`. Population 256 meets its measured radial
comparisons, with full dynamics and physical particle identity still open.
The remaining scalar angular and phase calculation follows in §8.11 and
report §11. All four selected population-256 grids support those sectors.
Seven of eight spatial comparisons pass; the dipole nonsymmetry gap fails
its domain comparison, leaving combined scalar-parent spatial qualification
`INCONCLUSIVE`. The conditional continuum identities require assumptions
that the sampled profiles do not establish.

The normalization campaign in `computations/matter-formation-continuum-report.md`
§12 gives three admissible scalar-parent normalizations
($a=1/64,1/32,1/16$) with the same external vacuum scalar mass
$0.511\ \mathrm{MeV}$, speed $c$, and one unit of internal scalar $U(1)$
generator, while the core lengths differ:
$(2.23505,1.61542,1.19022)\times10^{-12}\ \mathrm m$,
respectively. These are numerical consistency checks on Derived conditional
one-mass normalization nonuniqueness; electron and electromagnetic identity remain unestablished.
The selected scalar electron-core assignment is `CONTRADICTS`; the
chiral-scalar map also fails because $B_R=L^\dagger R$ and
$B_L=R^\dagger L=B_R^*$; the displayed projection terms are dimensionally
mismatched and generically non-Hermitian. The inherited scalar-parent spatial
result remains `INCONCLUSIVE` with seven of eight comparisons passing.

Section 14 supplies a separate real-scalar mass-source model with fermion
pair excitation and reciprocal semiclassical feedback. Independent
full-covariance and Bloch-vector calculations agree across all 1,185 checks.
Its state, source and subtraction are supplied inputs, and the calculation is
spatially homogeneous. Sections 15–16 then establish the ultraviolet
divergence of sudden-source excitation, a finite specified static subtraction,
the absence of a two-body bound level by a sufficient trace bound and the
global unboundedness of the specified local static one-loop scalar energy.
These conditional results leave dynamical renormalization, nonlocal quantum
energy and localized fermion formation open.

The collective local-density Yukawa functional is separately qualified to have
no subthreshold bound state under its stated mass-depleting and
vacuum-prescription assumptions (`computations/matter-formation-continuum-report.md`
§§15.6–15.7).


The current endpoint remains conditional. The supplied compact-target field
qualifies radial stationarity and energetic stability as a comparison model.
A smooth pointwise map of the two canonical densities has zero degree density.
The optional phase-bearing gauge sector has a physical relative $S^2$ at fixed
nonzero norms; joint gauge cancellation leaves a nonconstant relative texture
as independent field information, and its screening scale is comparable to
the predicted stationary size. Every exact hard-norm nonzero-Hopf adjoint in
the stated soft-action domain has a negative amplitude variation, and the
included hard Finkelstein–Rubinstein loops contract there. General
amplitude-relaxed metastability remains open
(`computations/matter-formation-continuum-report.md` §§18–20).

Sections 25–27 establish conditional formation dynamics. An excited periodic
scalar mediator has exact carrier Floquet growth and reciprocal seeded
transfer, while its retained spatial perturbation grows about $210.3$ times
faster. Prepared complex carrier data separate opposite local signed
densities with zero total charge. Exactly empty carrier data remain invariant,
and no finite-energy localization result follows from these plane-symmetric
calculations.

Section 28 records the frozen nonlinear verdict as `INCONCLUSIVE` in two
implementations. A post-hoc period-sampled diagnostic identifies phase
aliasing and reproduces the accepted linear rates without changing the
verdict.

`computations/matter-formation-continuum-report.md` §35 and
`foundations/matter-completion-boundary.md` §17 add a finite-time radial
result in the selected positive-inertia scalar action. Initially diffuse
complex-carrier Gaussian clouds with supplied signed charge $\mathcal Q_a=256$ and
widths $w=4,8$ (distinct from prepared population $Q_C=256$), together
with real mediator $f=1$, form a retained charged core inside $r<8$ by $t=48$. Independent RK4 means retain
74.7651% and 56.3735% of the charge during $32\le t\le48$, versus 5.4518%
and 15.3758% in matched $h_C=0$ controls. The all-sample minima are
approximately 74.5968% and 52.0335%, and the maximum central mediator
$f^2$ values are approximately 0.0686678 and 0.1126838. Spatial, domain, time-step and independent-integrator comparisons
pass across all five evolutions. The verdict is
`EMERGES-conditional finite-charge radial condensation`; the action, charge
and normalization are supplied witnesses, and canonical microscopic selection
remains open. For these radiating formed-cloud trajectories, nonradial and
complex-mediator-phase stability, infinite-time survival and particle identity
remain open; the finite-time run does not establish the continuum minimizer
theorem below. Quantum creation from empty carrier data and complete physical matter formation remain outside the calculation.

Section 29 proves the completion problem is non-identifiable from the
registered slow observables: scalar and Dirac parents share the same carrier
equation with different spin and statistics. Complete physical matter
formation and the radiating-cloud interpretation still require a canonical
action, state rule, physical normalization, localized real-time formation and
an observable particle discriminator. The continuum theorem supplies
infinite-domain attainment and minimizer-set stability for its exact
supplied scalar action and energy space.

The supplied scalar action also admits localized continuum energy minimizers.
For the specified positive coefficients and real-mediator/full-complex-carrier
energy space on $\mathbb R^3$, strict binding $I(Q)<\Omega_\infty Q$ gives
attainment and compactness of every minimizing sequence modulo translations and
carrier phase, plus Lyapunov orbital stability of the entire fixed-$Q$
minimizer set under arbitrary small full-energy-space perturbations, including
nonradial perturbations and nearby charges. The verified trial certifies this
inequality for every $Q>Q_{\rm tr}$, with $Q_{\rm tr}\approx149.36022508149227$; at $Q=256$,
$E_{\rm trial}/Q=8.283930463343918<\Omega_\infty=8.717797887081348$.
Here $Q$ is the dimensionless supplied signed charge, distinct from
prepared population $Q_C$; the action uses $a=1/16$, $c_\Psi=1/8$ and
$h_C=2.9598260763447164$. This model-specific minimizer-set theorem leaves
uniqueness, selected-profile stability, asymptotic convergence, and
membership, capture or stability of the radiating clouds in §35 unresolved; it
excludes complex mediator and gauge sectors. Physical action selection, quantum
creation and state, normalization, spin, statistics, particle identity and
physical stability of formed clouds remain open
(`computations/matter-formation-continuum-report.md` §36;
`foundations/matter-completion-boundary.md` §18).

For microscopic selection, report §38 tests finite quantum occupation and
the full spatial rotation algebra. The specified Bose, Fermi and unsaturated
carrier processes agree at one carrier but differ at two. The fully
occupied fermionic state cannot follow the unrestricted canonical drift;
the half-angle scalar operator also cannot represent the full spatial
rotation group. Independent algebra and trajectories qualify these
constraints, while anomaly cancellation retains multiple charge and
field-content choices. Read
`foundations/matter-completion-boundary.md` §19 for their physical scope.


Section 30 adds a normalized complex doublet and leading compact $SU(2)$
chiral action as an explicit conditional colour-neutral baryon model. Its
finite-domain degree-one hedgehog is stationary, and broadened prepared
$B=1$ data relax toward it under conservative radial evolution. The nucleon
and Delta masses map the two action coefficients. Supplied
Finkelstein–Rubinstein and charge rules give conditional spin/statistics and
charge assignments; two of six out-of-fit comparisons support their
thresholds and four contradict the 10-percent criterion. Independent
reconstruction passes all 78 checks. Section 31 applies six requirements to
every accepted construction. The field, action and quantum-state selection
remain supplied, no degree-zero run forms the soliton, continuum all-sector
stability is unproved, and no canonical Cassi particle map follows. The
completion gate is `FAIL`, so the benchmark is retained without calling
physical matter formation solved.


### The skeptic or referee

Start with the audit, then the tier discipline that governs every claim, then check the code yourself.

`audit.md` → `open-questions-cassi-answers.md` (epistemic tiers and the Fit-Status Ledger discipline) → `parameter-inventory.md` §10 → `EPISTEMIC-MAP.md` → `predictions/falsifiable-predictions.md` → the code: `computations/` and `two-fluid/` (every number is re-runnable from the repo root).

### The explorer (new application domains)

The exploratory catalogs and the figure scripts show where the framework reaches next.

`hypotheses/README.md` → `analyses/README.md` → `demystifying-the-cosmos/README.md` → `speculations/README.md` → `visual-explainers/` (figures).

### The social theorist or organizer

Start with the field-materialist account of the person and collective power, then move to the socioeconomic theory and its empirical program.

`consciousness/field-materialism-and-human-development.md` → `speculations/creative-extensions/coherence-commons.md`.

## 3. The registries and when to consult them

The registries are the authoritative indexes of the repository; consult each by what it answers.

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
- `cassi-physics.md`—Cassi Physics: The Bubble Lattice at Every Scale. Synthesis. The physics-facing presentation of the framework: governing equations, the model's conditional 3D bubble-lattice construction (physical $d=3$ identification remains Hypothesized), the 292-step cascade of scales, and the cascade suppression law behind physics' hierarchy puzzles.
- `cassi-psychology.md`—Cassi Psychology: The Mind as a Two-Fluid Field. Synthesis. Practitioner-facing guide reading the mind through the framework: consciousness as the experience of being a two-fluid field, with wake waves, five channels, chakras, emotions, and trauma built from field structures.
- `EPISTEMIC-MAP.md`—Epistemic Map—Every Document by Tier. Reference. Indexes every theory document by epistemic tier (Derived / Calibrated / Mapped / Hypothesized / Speculative) with tier definitions; navigation only, the registry remains the authority.
- `open-questions-cassi-answers.md`—Cassi Answers to the Open Questions of Physics. Comprehensive catalog. The epistemic master registry: all 42 major open questions of physics addressed from φ + the two-fluid PDE, every answer tagged with its epistemic status (Derived / Calibrated / Mapped, etc.).
- `parameter-inventory.md`—Cassi Parameter Inventory. Reference. Parameter registry classifying all 47 framework parameters (1 F + 7 D + 5 C + 10 M + 9 E + 7 I + 8 N: Fundamental axiom, Derived, PDE convention, Mapped, External, Initial condition, Numerical) with the fit-status ledger. The regulated quantum sector introduces no free exponent.
- `README.md`—CassiTheory: Foundations for a Reality Simulator and Field AGI. no Status line. Public project overview: the repository as the scoreboard of a research program organized around the scale-separation constant $\varphi \approx 1.618$ and the two-fluid Yang/Yin field, with named inputs and mixed epistemic accounting.
- `reading-guide.md`—this document: the table of contents and reading paths.

### foundations/

The central derivations; the wedge documents `foundations/dimensionful-cascade.md` and `foundations/cascade-suppression-formula.md` come first, then the derivation family that applies them.

- `foundations/README.md`—Foundations—First Principles and the φ-Cascade Machinery. Index. Holds the central derivations—the dimensionful cascade $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ and the cascade suppression law (the two wedge documents), the unified Lagrangian and two-fluid first principles, and the derivation family—with a prescribed reading order starting at `foundations/dimensionful-cascade.md` and `foundations/cascade-suppression-formula.md`.
- `foundations/baryon-asymmetry.md`—Matter-Antimatter Asymmetry from Cascade Freeze-Out and a Candidate Circuit Interaction. Hypothesized mechanism / Mapped exponent. Combines a candidate particle/antiparticle circuit interaction, the Wu Xing gap, and cascade dilution; the $\eta\approx\varphi^{-44}$ exponent remains a fit, while the reconnection rate and freeze-out endpoint remain open after the $\Gamma/H=1$ audit.
- `foundations/bubble-edge-geometry.md`—Bubble Edge Geometry: Physical Profile of the Condensation Boundary. Derived transverse geometry; Hypothesized axial/radial coordinate assignments; tested radial-ladder realization REJECT. Derives the conditional edge profile and records §3's multiplicative interior ring coordinate. The tested canonical and undriven second-order dynamics do not generate that ladder; a driven second-order control forms additive phase layers, and physical link modulation opens a gap only when supplied separately.
- `foundations/bubble-lattice-fabric.md`—The Bubble Lattice: Universal Organizing Geometry at Every Cascade Rung. Derived transverse geometry; Hypothesized axial/radial coordinate assignments—August 2026. Establishes the condensation field $B(x,y,z)=\cos(\alpha x)\cos(\beta y)\cos(\gamma_n z)$ as a 3D staggered checkerboard organizing geometry; the axial factor, along-string period, dimensionless rung count, and across-rung extension are Hypothesized coordinate assignments, physical $d=3$ identification remains Hypothesized, and the ansatz does not by itself identify a transported inter-rung field.
- `foundations/string-bubble-projective-map.md`—From String Formation to Bubble Boundary. Derived conditional projective geometry, affine shell action, and conversion-only meridional flow; Hypothesized phase dynamics, physical shell identification, and fivefold selector—August 2026. Connects the complex CassiFI doublet, canonical Yin/Yang densities, quadratic condensation boundary, phase-loop geometry, and pentagon/pentagram projections in one $\mathbb{CP}^1$ construction; SB1–SB5 pass independently.
- `foundations/loop-to-bubble-projection-theorem.md`—Loop-to-Bubble Projection Theorem: Shared-Support Counterflow, Coherence, and Scale Separation. Derived conditional projection, bubble map, and population spectrum; Hypothesized microscopic physical identification—August 2026. Four nonnegative Yang/Yin direction populations on one closed loop project exactly to the canonical PDE under common gate and transport assumptions; their species coherence matrix fills the affine bubble volume, its rank-one boundary is the projective shell, and the frozen internal spectrum supplies a zero-mode gap. LB1–LB7 pass; the physical carrier, phase law, scale ratio, and quantum-sector identification remain open.
- `foundations/geometric-manifold-completion.md`—Cassi Geometric Manifold Completion Ansatz. Hypothesized completion; conditional fibre geometry and canonical reduction Derived; carrier coupling Mapped; finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Places the density diameter, coherence ball, projective shell, affine bubble image and scale circuit in one stratified bundle. Its matter boundary distinguishes the ultraviolet Cartesian branch from prepared smooth binding and leaves microscopic production and full stability open.
- `foundations/yin-yang-qi-dynamical-geometry.md`—Yin–Yang–Qi Open Dynamical Geometry. Hypothesized integrated realization; canonical reduction, positivity, covariance and conditional interface ledgers Derived; carrier coupling Mapped; finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Combines canonical populations, coherence fibre and endpoint/Wilson channels. The first-order carrier preserves an empty sector, and the smooth constrained spatial stability result is INCONCLUSIVE.
- `foundations/endpoint-link-and-localization-boundary.md`—Gauge-Covariant Endpoint Closure and the Localization Boundary. Wilson extension Hypothesized; conditional endpoint, transport and minimal-sector no-go results Derived; separate finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Keeps endpoint covariance and support conditions distinct from the ultraviolet Cartesian particle branch, prepared smooth binding and open physical production.
- `foundations/point-core-flux-sector.md`—Quantized Point-Core Flux and the Persistent-Defect Boundary. Conditional exterior support and current-action completion no-go Derived; carrier coupling Mapped; finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Derives the flux coefficient and support inequality, then records the empty-sector invariant, Cartesian ultraviolet limitation and unclosed physical matching.
- `foundations/nonabelian-magnetic-core-boundary.md`—Non-Abelian Magnetic Core and the Confined-Defect Boundary. Auxiliary completion Hypothesized; conditional smooth-core and confinement boundaries Derived; carrier coupling Mapped; finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Examines the adjoint lift, BPS core, condensate confinement and pair collapse. Prepared scalar binding has no established magnetic-pair identity, and its constrained spatial stability remains INCONCLUSIVE.
- `foundations/core-trapped-charge-support.md`—Core-Trapped Noether Charge and the Finite-Composite Boundary. Auxiliary carrier Hypothesized; conditional thin-tube support Derived; coupling Mapped; finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Derives population conservation, retention and inverse-length support. An empty closed carrier sector stays empty; separate smooth binding requires a prepared population.
- `foundations/particle-stationary-action-closure.md`—Particle-Sector Action and Fixed-Charge Variational Closure. Temporal completion Hypothesized; action, scalar-reduction, parent-vacuum, dilation, fixed-charge, formation-dynamics and non-identifiability identities Derived conditionally; carrier coupling and conditional baryon benchmark Mapped; prepared binding, finite-grid spectra, parent correspondences, conditional temporal dynamics and radial baryon relaxation Tested—September 2026. The first-order carrier preserves an empty sector; its Cartesian branch is ultraviolet-dominated, and prepared scalar spatial qualifications remain INCONCLUSIVE. An added compact chiral model supplies a stationary and radially attracting prepared degree-one soliton, a two-mass coefficient map and conditional nucleon/Delta rules. Independent verification passes all 78 checks; canonical selection and degree-zero formation remain open.
- `foundations/matter-completion-boundary.md`—Matter Completion Boundary: Nine Conditions from Coherence to a Particle Calculation. Conditional boundary and microscopic non-identifiability Derived; carrier coupling and conditional baryon benchmark Mapped; physical realization Hypothesized; reduced receipts, prepared binding, finite-grid spectra, parent correspondences and radial baryon relaxation Tested—September 2026. The evidence includes exact empty-sector preservation, ultraviolet and continuum restrictions, scalar parametric amplification, an INCONCLUSIVE nonlinear comparison, a many-to-one microscopic projection and a conditional stationary degree-one baryon endpoint. Six physical requirements remain unmet or partial; the deterministic completion gate returns `FAIL`.
- `foundations/cascade-suppression-formula.md`—The Cascade Suppression Formula: $\varphi^{-N}$ as a conditional attenuation relation. Derived conditional on declared per-rung inputs; the uniform $\varphi^{-1}$ factor is a cascade input, while the coherence-product exponent is algebraic under its declared profile. Signal-map interpretations remain Hypothesized, with applications to proton stability, strong CP, the electroweak hierarchy, neutrino masses, and quantum measurement recorded with their own tiers.
- `foundations/cassi-first-principles.md`—Cassi First Principles. Derived PDE; C / Asserted Qi definition; Asserted single-channel $g(q)$ input—September 2026. States the $\varphi$ postulate and the two-fluid PDE; the rational $q$ gate and its normalization are constitutive choices. Canonical density-plane conversion is rank-one relaxation with conserved $\rho=E_Y+E_I$ and eigenvalues $0$ and $-\lambda(1-q)(1+\varphi)$, rather than an SO(2) rotation. The optional gravity endpoint is a coupling-magnitude identity; a GR or Newtonian interpretation requires a separate metric, matter map, and attractive source closure.
- `foundations/physical-becoming-hierarchy.md`—Physical Becoming: A Causal State Hierarchy for Cassi. Hypothesized architecture / Derived canonical reduction—September 2026. Separates microscopic actual physics, mesoscopic open-system dynamics, and agent-level reaction coordinates; embeds canonical rank-one conversion exactly as a positive-semidefinite gradient flow; defines body, history, shadow, possibility, attention, action, debit, and learning blocks with held-out closure and causal gates; records the conditional quantum-free-fall boundary while leaving Cassi source and response mappings open; leaves phenomenal consciousness as an open bridge.
- `foundations/cassi-theory-reference.md`—The Cassi Framework. Reference. Compact single-document reference: the two-fluid postulate and governing PDEs, the dimensionful cascade and suppression law, the unified action, and the quantum, particle, gravity, cosmological, turbulence, geometric, and consciousness consequences, each section condensing a cited derivation paper.
- `foundations/deriving-remaining-gaps.md`—Closing the Gaps: Derivation of Residual Parameters. Reference. Catalogs, classifies, and bounds the remaining underived quantities of the framework, assessing for each whether a derivation fully resolves the gap, partially narrows it, or hits an irreducible barrier.
- `foundations/dimensionful-cascade.md`—The Dimensionful Cascade: All Physical Scales from $\\varphi$. Derived conditional on the external anchor. The wedge document: with the Planck length as the supplied anchor, the scale coordinate follows $\ell_n=\ell_{\text{Pl}}\varphi^n$; the observable catalogue spans $n=0$ to $\approx292$ (today's horizon coordinate, epoch-dependent), while the formal megacascade and microcascade extensions have no established physical fields.
- `foundations/dimensionful-constants-status.md`—Dimensionful Constants: Derivation Status of $c$, $\hbar$, and $G$. Hypothesized / Mapped. Catalogues which constants are derived (the $\varphi$-power couplings) versus still external ($c$, $\hbar$, $G$) and empirical (the epoch-dependent horizon rung $N \approx 292$); the named C-class/framework convention $\lambda=0.1$ is Asserted, while the implementation class default is $\lambda=0.02$; $\lambda = 1/(2w)$ is a Hypothesized Wu Xing linkage requiring independent cycle-time and dynamical closure; $v_0/M_{\text{Pl}}$'s exponent remains asserted/Mapped.
- `foundations/microcascade-mirror.md`—The Microcascade Coordinate Extension: Sub-Planckian Scale Labels. Hypothesized. Separates the exact negative-step continuation of $\ell_n=\ell_{\text{Pl}}\varphi^n$ from physical sub-Planckian state, coherence, energy, transport, and electromagnetic-coupling assumptions; the canonical $q$ semantics exclude the former infinite-reservoir inference.
- `foundations/interscale-current-soliton.md`—Interscale Yang/Yin Current and the Conditional Soliton Pinch. Action and Wilson extension Hypothesized; conditional current, endpoint, transport and support identities Derived; carrier coupling Mapped; finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Separates the scale-current mechanism from the ultraviolet Cartesian branch and prepared scalar binding. Empty-sector invariance, INCONCLUSIVE smooth constrained spatial stability and physical matching delimit the matter claim.
  Its §12 derives positive collective phase inertia, the constrained
  longitudinal branch and causal exterior memory. Surrounding population
  and correlations enter local initial data; boundary-induced frequency
  gaps remain conditional. The calculation and its physical limits are in
  `computations/matter-formation-continuum-report.md` §37.
- `foundations/interscale-stress-attenuation-boundary.md`—Interscale Stress Transfer and the Attenuation Boundary. Hypothesized physical carrier and Wilson-link coefficient / Derived conditional stress, frozen-link, first-order source-action, stationary spatial-flux, and Wilson-transport boundaries—September 2026. The paper derives scale-windowed force as mixed-stress boundary flux, conservative reciprocal-ladder dispersion, series compliance, and the unitary $S_\Lambda(k)$ family for Hermitian endpoint data. The frozen charged endpoint response passes AR1–AR6; the incompatible DR receipt remains `FAIL`. Every closed homogeneous EL9 extremum has zero coherent current, and closed stationary spatial flux permits only zero-mean endpoint source structure. The separately declared Wilson link closes the homogeneous circuit conditionally, completes the relative-charge ledger, and has finite capacity; IT1–IT6 pass at one normalized point. The routed branch can yield forward quadratic flux $\varphi^{-N}$ under non-reentry. The physical stress carrier, current-to-stress map, $t_\Upsilon$, local scale-bulk completion, nonzero-current background, damping channel, doubled port-flux law, and full coupled spectrum remain open.
- `foundations/neutrino-masses.md`—Neutrino Masses from Fibonacci Cascade Partitioning of the Seesaw. Hypothesized mechanism / Mapped offsets. Applies the Fibonacci triple-clustering behind three generations to the selected mapped coordinate span ($n=8\rightarrow20$), while the physical GUT-to-seesaw interval is about seven rungs; the seesaw's Yukawa-squared structure amplifies the mass-ratio exponents.
- `foundations/phi-rg-formalism.md`—The Golden Ratio as a Renormalization Group Fixed Point. Hypothesized—September 2026. Explores a discrete Wilsonian-RG ansatz with scale factor $b=\varphi$. Its beta function, selection of $\alpha_c=\varphi^{-1}$, Standard Model $\varphi$ charges, and de-resonance interpretation require a microscopic coarse-graining map and independently derived running couplings. The optional Qi-gravity expression is a state-space diagnostic; no momentum-to-field-state map currently makes it a running Newton coupling.
- `foundations/phi_attractor_synthesis.md`—phi-Attractor Steady States and the Analytical Three-Body Problem in Cassi Gravity. Derived / Calibrated / Mapped. Investigates whether the Cassi N-body solver admits analytical three-body solutions, developing nine analytical paths: an asymptotic half-mass-radius law, disproof of Qi-hydrostatic equilibrium for damped systems, and cold-collapse virial decay, among others.
- `foundations/qi-flow-double-helix.md`—Yin, Yang, and Qi: Canonical scalar coherence diagnostic with optional spatial lifts. Derived ($q$ and exact positive-root amplitude-plane/density-plane diagnostics) / Hypothesized (conditional four-channel $\Delta^3$ lift, constitutive map, $P_\parallel=2$, double helix). Defines $J_\Psi=\rho\nabla\theta_\Psi$ and the positive-root density diagnostic $J_d=(E_Y^2+E_I^2)\nabla\theta_d=2\sqrt{E_YE_I}\,J_\Psi$ with distinct units; Qi is a scalar diagnostic with no independent field degree of freedom, and the canonical PDE supplies no compact phase or inter-rung current law. At fixed total, four directional populations occupy a $\Delta^3$ tetrahedron while the canonical densities supply only species marginals, leaving species-direction association and dynamics nonunique.
- `foundations/qi-loop-mass-cascade.md`—Qi-Loop Mass Cascade: Conditional Two-Fluid De-Resonant Rings. Derived conditional counterflow selection and supplied-ring algebra / Tested conditional branches and passive $M_0$ REJECT / Hypothesized physical realization—August 2026. The declared density target conditionally selects $\alpha\to\varphi$ under the explicit current closure, yielding Fibonacci record near-closures; a supplied positive ring Hamiltonian gives a stable branch, while the passive $M_0$ transition candidate gives zero $\varphi$-band sectors and compact-sector transitions, coefficient selection, and unique physical mass selection remain open.
- `foundations/proton-coherence-budget.md`—Proton Coherence Budget and Planck-to-Proton Scale Circuit. Proton coordinate and carrier coupling Mapped; conditional arithmetic and current identities Derived; physical mechanisms Hypothesized; finite-grid spectrum and conditional smooth scalar binding Tested—September 2026. Separates lifetime arithmetic from the two-rail circuit. The Cartesian particle branch has an ultraviolet obstruction; separate prepared smooth binding supplies neither microscopic production nor proton quantum numbers or lifetime.
- `foundations/quantum-measurement-derivation.md`—CassiFI Quantum Dynamics and Measurement. Derived conditional (regulated quantum mechanics and finite carrier projection); Hypothesized (CassiFI and carrier physical identifications)—August 2026. Quantizes the finite metric-bearing CassiFI configuration as a linear wavefunctional and derives centre-of-mass Schrödinger dispersion, configuration-space entanglement, equivariant Born density, one retained apparatus record, and passive unitary scattering. DQ1–DQ9 rejects physical-identification promotion. GQ1–GQ7 adopts a Hypothesized moment-map/Kähler projection architecture. QC1–QC9 adopts a finite carrier reservoir as Hypothesized microphysics and derives its mesoscopic drift, fluctuations, and finite instrument conditionally; the QF1-to-carrier state map remains Open, and the branch is operationally equivalent to ordinary quantum mechanics under the same instrument.
- `foundations/quantum-free-fall-correspondence.md`—Quantum Free Fall as a Cassi Correspondence Boundary. Derived conditional external-potential correspondence / Hypothesized Cassi atomic state, gravity-response, and common-lapse mappings—September 2026. Derives the ideal QGI action, gauge phase, local-acceleration degeneracy, differential response ratio and constant-lapse cancellation. Its physical-$q$ interval, equal-$q$ signed-composition counterexample and coarse-graining mismatch pass independent algebraic checks. Section 11 inventories forty-three material, gravity, clock, apparatus and interacting-quantum closure requirements; §12 records QFC1–QFC4, including the Gaussian physical-covariance obstruction.
- `foundations/quark-confinement.md`—Quark Confinement from the Saturated-Gate Flux Tube at the QCD Scale. Derived (tube extensivity + cell quantization; inputs: gate saturation, one-cell quantization). With the QCD scale at cascade step 95, the conversion channel saturates between separated color charges ($q \to 0$), forming a flux tube whose energy is extensive in its length: $E(r) = \mu r$ with $\mu = \kappa(M_{\text{Pl}}/\varphi^{95})^2 = \kappa\Lambda_{\text{QCD}}^2$, $\kappa = O(1)$ open—a constant force, i.e. a linear potential, by tube extensivity (independent of the gate shape).
- `foundations/refined-numeric-predictions.md`—Refined Numeric Predictions for the 19 Hypothesized Questions. Active derivation. Refines the specific numeric predictions ($\varphi^{-N}$ cascade-span forms) for each of the 19 Hypothesized questions in the open-questions catalog, and tightens the mechanistic argument for questions whose answer is structural rather than numeric.
- `foundations/rung-offset-mechanism.md`—Why Observables Sit Between Rungs: The Two-Fluid Phase Mechanism for Fractional Cascade Offsets. Derived envelope quantization, Hypothesized phase-to-rung mapping and selection, Empirical catalog. Explains the wake-envelope crossing positions and pool-cell quantization; $\delta n$ is a Hypothesized coordinate mapping of a local phase lag, while the exact relaxation-angle bound is $|\Delta\theta_d|\leq\operatorname{atan}(\varphi)\approx1.017$ rad; the empirical catalog places the lightest state of each terminated sector at wake-envelope crossing positions; the mapped $\pm0.162$-rung reading remains distinct from the PDE-derived angle bound.
- `foundations/sector-coupling-derivation.md`—Conditional Sector Scale and the Dirac Density Obstruction. Derived conditional sector and fermionic identities / Tested finite-mode production, continuum and scalar-vacuum restrictions / Calibrated electroweak anchor / Hypothesized physical fermion coupling—September 2026. The $\delta=3$ scale arithmetic leaves physical interactions open. The chiral-scalar projection has dimensional, conjugacy and Hermiticity obstructions. Positive component quadratics give chiral-current densities but fail canonical population closure; the specified massive conversion lift shifts the golden fixed point and permits positive-to-negative-energy transitions. The separate scalar mass-source model has verified finite-mode production and feedback with 1,185 checks. Its continuum witness passes 645 comparisons: sudden excitation is ultraviolet divergent, static subtraction and initial-overlap identities hold, and $B=0.00165786399054<1$ excludes two-body binding in the leading nonrelativistic reduction. The specified local static one-loop energy has positive reference curvature but no global lower bound in 16 algebraic checks. Physical matching, dynamical renormalization, full nonlocal spatial energy, metastability, relativistic and many-body localization remain open (`computations/matter-formation-continuum-report.md` §§14–16).
- `foundations/spin-fibonacci-spiral.md`—Spin from the Yang/Yin Doublet Half-Angle: The amplitude-plane phase coordinate. Derived conditional on the doublet postulate, asserted pitch convention, equilibrium ratio, and minimal-span principle; the phase-to-rung mapping and particle identifications remain Hypothesized. Uses $\theta_\Psi$ and $\Theta_S=2\theta_\Psi\pmod{2\pi}$; $s=\Delta n/2$ and the $P_\parallel=2$ cycle are conditional coordinate conventions, with no fundamental $3/2$ claim under the minimal-span decomposition.
- `foundations/spiral-dynamics.md`—Spiral Dynamics: Hubble, Gravity, and $c$ from Fibonacci Spiral Geometry. Hypothesized. Proposes a coordinate Fibonacci spiral built from the amplitude-plane phase and scale advance as a common structure behind cosmic expansion, gravitational attraction, and the speed of light; the spiral mapping's dynamical interpretation remains Hypothesized.
- `foundations/strong-cp-derivation.md`—Strong CP: Why $\bar{\theta} \approx 0$ from Cascade De-Resonance. Derivation. Resolves the strong CP problem via cascade de-resonance: the $\varphi$-attractor fixed point is CP-symmetric, and CP-violating departures seeded at the GUT scale are cascade-suppressed over ~81 rungs to $\bar\theta \approx 1.2\times10^{-17}$ at the QCD scale.
- `foundations/three-generations.md`—Three Generations from Fibonacci Cascade Partitioning. Hypothesized / Mapped. Proposes three fermion families from the Fibonacci recurrence: $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$ supplies two predecessor channels (2D solution space, roots $\varphi$, $-1/\varphi$), and the propagation-channel postulate adds the direct rung—$N_{\text{gen}} = 2 + 1 = 3$ (the 2+1 counting is Derived under the postulate; without it the count would be 2); per-sector offsets are ledgered Mapped—row 483.
- `foundations/unified-lagrangian.md`—The Cassi Unified Lagrangian. Hypothesized—September 2026. Assembles an optional extended action around the canonical real-density pair and rank-one conversion; dimensionless couplings retain mixed ledger status, with structural $\varphi$-powers alongside asserted normalizations, calibrated anchors, and mapped placements; the named C-class/framework convention $\lambda=0.1$ is Asserted, the implementation class default is $\lambda=0.02$, and $\lambda=1/(2w)$ is a Hypothesized Wu Xing linkage.
  Its §1.7 defines the parameter-free candidate physical-time lapse from the exact relative conversion-clock rate, proves that a constant common lapse cancels from the ideal free-fall phase when duration is expressed in the same physical clock, and records the resolved-contrast CT-2 falsifier.
- `foundations/wa-pentagon-gate.md`—The $w_a$ Sign Tension: 5-Channel Pentagonal Gate. Derived / Hypothesized. Addresses the $w_a$ sign tension: the bare two-fluid dynamics predict $w_a = +0.46$, and including the $\xi = \varphi^6$ Qi-gravity coupling in $H_{\text{eff}}$ shifts the prediction to $w_a = +0.012$—still ~2.7σ from DESI DR2's $w_a \approx -0.73$, a tension, not a resolution.
- `foundations/why-three-dimensions.md`—Why Three Dimensions: The Spiral's Three Directions. Hypothesis with One Supported Fork. Proposes a conditional geometric route to the 3 in $\xi = \varphi^{2\times3}$: a non-degenerate curve has a Frenet-Serret frame with three orthogonal directions, but identifying that frame with physical spatial dimensions and closing $d=3$ remains Hypothesized; W1 anti-phase morphology is supported by the measured branch.
- `foundations/wake-geometry.md`—Wake Geometry: How the Waveform Closes Each Rung. Derived supplied-wave structure; tested conditional second-order realization; Hypothesized physical condensation and closure imprint. Adjacent-rung carriers close the next scale and have exact alternating beat-layer parity; the live second-order channel ratio reaches $\varphi$ only under the supplied $\Omega_*=\varphi^{3/2}\omega_{0,\mathrm{wave}}$ drive, with additive radial spacing and no current endogenous frequency or node-to-link selector.
- `foundations/wu-xing-cycle-structure.md`—Wu Xing Cycle Structure: The Two 5-Cycles, the Control Ring, and the 5↔13 Partition. Derived / Tested / Hypothesized. Derives how the pentagonal gate's five channels are wired—exactly two coherent 5-cycles (sheng sides, ke diagonals), a control-ring transmission coefficient $\kappa = \varphi^{-1}$ from pentagram golden-section crossings—plus the 5↔13 partition between the channels and the chakra ladder.
- `foundations/wu-xing-derivation.md`—Wu Xing Number $w = 5$: Derivation from Cascade Dynamics. Derived (single input: coherence postulate; verified 2026-08-11) / Calibrated. Derives the Wu Xing number $w = 5$ as the unique intersection of the coherence criterion applied to ALL cycle sizes at once ($w \cdot \min_p|\varphi - p/w| \leq \varphi^{-w}$ holds only for $w \in \{1,2,3,5\}$—the Fibonacci restriction follows from continued-fraction optimality, verified exhaustively to $w = 2000$) and $\varphi$-geometry ($w \geq 5$); the primordial gap $g = 1 - \varphi^{-5}$ and Yang-Yin ratio $r_0$ follow.
- `foundations/xi-derivation.md`—Derivation of $\xi = \varphi^6$. Derived conditional on the quadratic-coupling input (imbalance inverse-square) / Calibrated empirical pin. Derives the Qi-gravity coupling $\xi = \varphi^6 \approx 17.944$ as the inverse-square of the fixed-point imbalance, $\xi = (\pi/\rho)^{-2} = (\varphi^{-3})^{-2}$ (exponent 3 from the attractor's fixed-point imbalance; $-2$ the quadratic degree of the gravitational coupling; at the reference state $\rho=\varphi$, $q=0.872677996$, and $G_{\mathrm{eff}}/G=3.726779962$; the $\varphi^3G$ value is the high-density same-composition fixed-$s$ endpoint). The MW pin $\xi\approx18$ remains Calibrated to 0.3%.

### principles/

Cross-cutting rules for how $\varphi$ enters every sector.

- `principles/README.md`—Principles—Cross-Cutting Framework Principles. Index. Collects the principles governing how $\varphi$ enters the framework across every sector—de-resonance as the attractor's origin (with the posture that quantities sit *near* $\varphi$-powers) and the $v_0/M_{\text{Pl}}$ hierarchy gap as its hardest open case.
- `principles/de-resonance-principle.md`—The De-Resonance Principle in Cassi. Derived number-theory and topological identities / Derived conditional counterflow selection / Tested PC1–PC7 and passive $M_0$ REJECT / Hypothesized physical realization—August 2026. The declared density target transfers to $\theta_I'/\theta_Y'\to\varphi$ only under explicit compact-current assumptions; finite winding sectors require phase slips or altered topology to track it, and the passive $M_0$ candidate returns zero $\varphi$-band sectors.
- `principles/v0-hierarchy-problem.md`—v₀/M_Pl: The Hierarchy Problem in φ-Clothing. Mapped; 5.3% residual open. The direct measured-ratio placement is $N_{\mathrm{raw}}=\log_\varphi(M_{\text{Pl}}/v_0)\approx79.89$; the gap-adjusted cascade coordinate is $N_{\mathrm{gap}}=\log_\varphi(gM_{\text{Pl}}/v_0)\approx79.7$ for $g=1-\varphi^{-5}$; both identify nearest rung 80, while the framework does not yet compute the correction itself.

### standard-model/

The Standard Model's gauge structure, couplings, and flavor sector from the φ-fixed point.

- `standard-model/README.md`—Standard Model—Couplings, Gauge Structure, and CP from φ. Index. Six documents cover the Standard Model's gauge structure, couplings, loop corrections, and flavor sector from the Cassi $\varphi$-fixed point; the prescribed reading path starts with `standard-model/sm-from-phi.md`, and the Weinberg coupling-normalization blocker is recorded in `standard-model/su2-gauge-extension.md` §3.2.1.
- `standard-model/cp-violation.md`—CP Violation from the Golden Ratio. Derived. Derives CP violation from the Yang/Yin chiral asymmetry $\eta = \varphi^{-3}$, which seeds the CKM phase closing through the unitarity triangle to $\delta_{\text{CKM}} = \pi\varphi^{-2} \approx 68.8°$ (within <1% of measurement), while the Jarlskog invariant is not reproduced (~20 orders low); strong CP resolves by cascade de-resonance without an axion.
- `standard-model/gut-embedding.md`—SU(5) / SO(10) GUT Embedding. Hypothesized. Embeds the Cassi symmetry-breaking chain in the minimal grand-unified groups at the $\varphi$-fixed point: SU(5) with $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53$ and $M_{\text{GUT}} \approx 2\times10^{16}$ GeV predicting proton decay above Hyper-Kamiokande reach, and SO(10) adding a right-handed neutrino with a natural seesaw.
- `standard-model/neutrino-mass.md`—Neutrino Mass from $\varphi$. Hypothesized. Pedagogical primer deriving the seesaw scale from the cascade—the right-handed neutrino sits at cascade step 20, $M_R \approx 10^{14}$ GeV—and presenting the canonical spectrum ($m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019$ eV, normal ordering); the full derivation lives in `foundations/neutrino-masses.md`.
- `standard-model/sm-from-phi.md`—Standard Model from φ. Derived chain with an asserted Weinberg boundary. Organizes the Standard Model from $\varphi$: gauge groups as successive truncations of the continued fraction $[1;1,1,\ldots]$, the fixed-point value $\sin^2\theta_W = \varphi^{-3}$, a $\varphi$-powered Yukawa hierarchy, the Higgs mechanism at the $\varphi$-point, quark confinement from Qi coherence, and the CKM phase.
- `standard-model/sm-radiative-corrections.md`—Standard Model Radiative Corrections from the φ-Boundary. Derived loop equations; Asserted $\varphi$-boundary inputs; Calibrated $\mu_*$ crossing—August 2026. Derives the Standard Model precision program—running couplings, vacuum polarization, and electroweak corrections—from the asserted Cassi boundary conditions, with a calibrated $\mu_*\approx233$ GeV crossing; standard relations close to 0.01–0.1%, while the gaps to the GUT scale remain.
- `standard-model/su2-gauge-extension.md`—SU(2) × U(1) Gauge Extension of the Cassi Two-Fluid. Derived gauge algebra and mass matrix with an asserted coupling boundary. Extends the two-component field representation to an SU(2) isospinor doublet, derives the neutral-boson mass matrix and SU(3) color extension, and tests the curvature–orbit normalization candidate in §3.2.1; the conversion retains its rank-one relaxation structure while the gauge extension supplies its separate internal algebra.

### particles/

Conditional particle-interference models, matter-formation boundaries and conventional DFT benchmarks.

- `particles/README.md`—Particles—Conditional Interference and DFT Benchmarks. Index. Separates the Hypothesized complex-field particle extension, conventional DFT benchmarks and mixed-tier matter synthesis; none supplies a completed microscopic matter-formation mechanism.
- `particles/cassi-yang-yin-particles.md`—Yang-Yin Field Interference and Particle Formation. Hypothesized. Conditional complex counterpropagating/NLS extension; the canonical real-density equations do not supply chirality or an independent phase.
- `particles/dft-benchmarks.md`—DFT Benchmarks: CassiBridgeV2 Real-Space Performance. Calibrated—August 2026. Compares a conventional real-space DFT implementation with atomic ground-state energies for $Z=1$–$10$; the benchmark does not test Cassi two-fluid condensation.
- `particles/matter-organization.md`—Matter Organization: Forces, Lattice Pools, and the Neutron–Proton–Electron Trio. Derived conditional relations / Mapped scale assignments / Hypothesized physical realization—September 2026. Synthesizes force-channel and mass bookkeeping while retaining each source tier. Its formation boundary distinguishes empty-sector preservation, the ultraviolet Cartesian branch, prepared smooth scalar binding and INCONCLUSIVE constrained spatial stability from physical particle identification.

### gravity/

Quantum gravity and analytical three-body results.

- `gravity/README.md`—Gravity—Quantum Gravity and Analytical Three-Body Results. Index—September 2026. Indexes the $\sigma$-regularized free-propagator candidate, the outward-sign well-separated-blob reduction, and the quantum-free-fall correspondence boundary. A physical attractive or metric branch, atomic state map, and interacting quantum completion remain open.
- `gravity/quantum-gravity.md`—Cassi Quantum Gravity: A $\sigma$-Regularized Two-Fluid Candidate (Free-Propagator Analysis). Derived conditional on the noise–signal identification, cascade-dephasing family and selected $d=3$ domain; Derived conditional obstruction to the Gaussian's standard positive spectral interpretation / Hypothesized two-fluid quantization, composite graviton and interacting completion—September 2026. The nonzero-$\sigma$ Gaussian fails the standard unsubtracted positive physical scalar spectral representation; an auxiliary/regulator interpretation needs separately qualified physical observables. Free damping and the UV-convergent prototype at supplied nonzero infrared cutoff do not establish interacting renormalizability, Lorentzian unitarity, a beta function or horizon physics. Its implemented low-$k$ dispersion is rejected for observed gravitational waves.
- `gravity/three-body-analytical.md`—The Three-Body Problem in Cassi Two-Fluid Gravity. Derived conditional on the selected $d=3$ computational/physical domain and displayed PDE force sign—September 2026. Derives the well-separated-blob point-particle reduction under the displayed outward-sign force convention. Its internal coupling-magnitude coefficient and retained masses vary with blob state; a body-dependent physical response requires a separate matter-state map, and an attractive branch requires a separate force or metric closure.

### turbulence/

Conditional turbulence spectra, exact Navier–Stokes transfer identities, and geometric regularity questions.

- `turbulence/README.md`—Turbulence—Spectra and Navier–Stokes Geometry. Index—September 2026. Covers the conditional spectrum analysis, critical-transfer and coercivity results, filtered stress geometry and quantitative strain departure.
- `turbulence/kolmogorov-from-phi.md`—The Kolmogorov −5/3 Spectrum in Cassi: Derivation and Conditional Tests. Derived conditional / Hypothesized closures—August 2026. The kinetic-energy spectrum is inherited under Navier–Stokes cascade assumptions; the optional break scale, deviation spectrum, gravity factor, and Qi-quality spectrum depend on supplied constitutive and statistical assumptions.
- `turbulence/navier-stokes-transfer-boundary.md`—Navier–Stokes Transfer, Heat Corrections, and Coercivity. Derived identities and obstructions / conditional small-data estimates—September 2026. Gives the positive critical-norm budget, cubic heat correction, signed quartic remainder, and an unbounded corrected-energy level set, with a reproducible full-convolution verifier.
- `turbulence/navier-stokes-stress-geometry.md`—Filtered Stress Geometry in Periodic Incompressible Navier–Stokes. Derived filtered identities / Hypothesized geometric closure—September 2026. Retains third moments, pressure correlations, and viscosity; relates helical tangent covariance to anisotropy and tests local geometric preservation. The all-data regularity estimate remains open.
- `turbulence/navier-stokes-depletion-dynamics.md`—Fine-Scale Transfer Dynamics and the Matter-Binding Comparison. Derived filtered identities and instantaneous obstructions / Conditional continuation estimate—September 2026. Gives an exact strain split with an energy-controlled coarse term, positive averaged fine-transfer production from zero, a viscous-only absorption counterexample, and the unresolved cumulative estimate. Compares loaded-core redistribution and coercive unwound binding with original Navier–Stokes. A separate applicability note on conditional exterior-memory bounds lies outside the frozen matter-comparison scope.
- `turbulence/navier-stokes-strain-departure.md`—Quantitative Departure from Strain Self-Amplification. Derived conditional comparison / Open critical-work control—September 2026. Couples energy and enstrophy to sharpen the departure-or-breakdown deadline, with axisymmetric swirl-free departure supplied by known global regularity. Gives an exact cumulative defect identity and a necessary excess-dose bound; 71 algebraic/quadrature checks pass. Critical-scale production remains uncontrolled.

### cosmology/

Inflation, baryogenesis, dark matter, and the observational-constraints ledger.

- `cosmology/README.md`—Cosmology—Dark Energy, Inflation, and Observational Constraints. Index.
- `cosmology/cosmology-from-phi.md`—Cassi Cosmology: Inflation, Baryogenesis, and Dark Matter from φ. Mixed status: Derived formation/structure, Hypothesized baryogenesis, Mapped $\eta$, conditional DM base, Calibrated $w_0$ form. The same two-fluid dynamics organize inflation, the baryon-asymmetry candidate, and the dark-matter condensate; the freeze-out endpoint and 21% DM-ratio residual remain open.
- `cosmology/desi-lattice-averaging.md`—How the Infinite Bubble Lattice Enters DESI's Averaged Measurements. Hypothesized. Works out quantitatively which lattice channels survive DESI's light-cone average: the distance channel washes out (cannot rescue the $w_a$ tension), the power-spectrum channel survives as a powder-diffraction comb, the anisotropy channel partially, the variance channel inverts.
- `cosmology/inflation-from-cascade.md`—Inflation from Cascade Steps 20–60: The Qi-Gate Epoch. Derivation (mechanism Hypothesized, C4; r exponent Mapped—ledger). Cosmic inflation as cascade steps ~20–60 driven by the Qi gate: the open gate drives expansion and its closing at the pinch terminates inflation, with $n_s$ matching Planck at the formula level ($N_e = 40$ Mapped—row 501) and $r$ a Mapped fit (row 495) excluded by the trajectory's BK18 constraint.
- `cosmology/observational_constraints.md`—Observational Constraints—DESI DR2 Dark Energy & Milky Way Rotation Curve. Calibrated ($w_0$ coupling form, $\xi$ pin—ledger) / Mapped ($\alpha_\text{halo}$ nominal, halo $q$—ledger). Compiles the strongest external constraints: the two-fluid dark-energy prediction ($w_0 = -0.87$, $w_a = +0.012$) sits at 2σ/2.7σ tension with the DESI DR2 best fit, plus Milky Way rotation-curve anchors.
- `cosmology/sigma8-computational-plan.md`—Sigma-8 Computational Plan: Modified Boltzmann Pipeline for Cassi Qi-Gravity. Plan. Computational plan to promote the σ8 prediction from Hypothesized to Derived by integrating the density-dependent Qi-gravity coupling into a Boltzmann code, with the 2026-08-07 truth campaign's measured rows: mechanism +29.7% (D-insensitive) and total −20.5% (D=0.001) / −22.9% (D=0 doctrine default, brief 63—the totals carry the diffusion) (doctrine r₀, linear-P(k) normalization, resolution-converged).

### consciousness/

The mind as a two-fluid field—Qi-gate dynamics at neural scales.

- `consciousness/README.md`—Consciousness—Qi-Gate Dynamics at Neural Scales. Index.
- `consciousness/auras-as-thermalized-gates.md`—Auras as Thermalized Qi Gates. Speculative. The aura as the human-scale instance of the $(1-q)$ thermalization law: a coherent core bridge-suppressed into invisibility plus a broadband thermal halo whose signature is heat haze.
- `consciousness/cascade-consciousness.md`—Consciousness in the Dense Medium: Perception, Communication, and the Cascade Nervous System. Speculative. How living in water (833× denser) would transform perception, communication, and social structure, extended to the whole φ-ladder as a distributed, nested cascade nervous system.
- `consciousness/chakras-as-cascade-bubbles.md`—Chakras as Cascade Bubbles: The 13-Node Derivation. Hypothesized. Closes the open phenomenological gap on the 13-band chakra count: chakras as localized Qi condensates at $\varphi$-spaced intervals, with $13=26/2$ from the human cascade span over the $P_\parallel=2$ coordinate cycle (`foundations/spin-fibonacci-spiral.md` §2); the phase-to-rung and fixed-pitch coordinate readings remain Hypothesized conventions, while the local conversion retains its rank-one relaxation structure.
- `consciousness/consciousness-from-phi.md`—Consciousness in the Two-Fluid Framework. Plausible Hypothesis with Actionable PDE Test. Maps verified physics onto consciousness: the Qi gate's conjugate point at $r = \varphi^{-1}$, where the fractional imbalance equals the gate's characteristic scale $\varphi^{-2}$ exactly, as self-awareness; wake waves as thought, $\sigma_r$ as the state variable, with a proposed-and-executed two-bubble PDE test and explicit boundaries to speculation.
- `consciousness/emotions-as-gate-configurations.md`—Emotions as Qi-Gate Configurations: A Cassi Mathematical Formalism. Hypothesized. Emotions as channel-dominance patterns of the 5-channel Wu Xing gate above the pinch, defining a 7-dimensional emotional manifold whose application parameterization remains Hypothesized.
- `consciousness/gender-as-qi-configuration.md`—Gender as Qi Configuration. Speculative. The field has no binary: sex characteristics live at the readout layer, gender identity in the configuration tuple, and dysphoria reads as the field's memory failing to predict its own present (drive-mechanism layer PDE-tested).
- `consciousness/meditators-taijitu-brain-bubble.md`—The Meditator's Taijitu: The Brain-Bubble, the Spine-String, and the Front-Back Axis Slice. Hypothesized. Proposes an observer-framing model for a front-back slice through a brain-bubble geometry and defines prospective spatial, projection, winding, and anatomy checks; no taijitu field measurement or anatomical coupling is assigned.
- `consciousness/neurodivergence-as-gate-configuration.md`—Neurodivergence as Gate Configuration. Speculative. Autism as a high-stability gate configuration and ADHD as its complement, with conditions living at slots of the person-configuration tuple (drive layer PDE-tested; the §9 churning-gate test returned a null).
- `consciousness/time-memory-and-wake-locks.md`—Time, Memory, and Ghosts: The Field as the Medium of Time, Memory, and Persistence. Speculative. Time's arrow from the dissipative conversion term, memory as a coherence phenomenon with a quantitative lifetime, and frozen gates (wake locks) as persistence—extended to hauntings, precognition, and time travel.
- `consciousness/transhumanism-gate-configurations.md`—Transhumanism as Gate Reconfiguration: Augmentation as Changes to the Gate Chain's Topology. Speculative. Augmentation as topological surgery on the 26-rung human gate chain—adding nodes, changing spacing, re-tuning bands—each operation carrying a stability condition.
- `consciousness/trauma-as-frozen-gate.md`—Trauma as Frozen Gate Configurations: The Cassi Trauma Formalism. Tested—null pinning, drive effect supported / Speculative (clinical). A frozen wake acts as a perpetual stimulus, pinning one channel hyper-open and starving the other four—a locked gate configuration, with the drive effect PDE-tested and clinical claims flagged.
- `consciousness/two-strand-qi-neuroscience.md`—The Two-Strand Qi Condensate: A Neuroscience Hypothesis. Hypothesized (strand geometry) / Speculative (neural mapping). A single Qi condensate may organize into two coupled strands around a common axis, supplying a field-level correlate of bilateral brain/body organization and a structural reference for DNA.
- `consciousness/field-materialism-and-human-development.md`—Cassi Field Materialism: Personhood, Collective Power, and Human Development. Creative—August 2026. Field-materialist foundation for personhood, collective power, and human development; separates physical field description from hypothesized social mechanisms and declared norms.
### speculations/

Framework-consistent explorations that reach beyond confirmed physics.

- `speculations/README.md`—Speculations—Framework-Consistent Explorations. Exploratory catalog.
- `speculations/cascade-infrastructure.md`—Cascade Infrastructure: Planetary and Stellar Gate Networks. Speculative. What cascade-aware infrastructure looks like: planetary-scale gate networks, pyramids and ocean bases as their natural surface expressions, and the Sun as a stellar-scale gate stage.
- `speculations/dark-matter-as-qi-coherence.md`—Dark Matter as Unharvested Coherence: The Qi Field in Galaxy Halos. Speculative. Reframes missing mass as unharvested Qi coherence: the halo is the bubble edge where $q$ transitions from ~1 toward 0; the $G_\text{eff}$ mechanism is derived, the halo-profile claims are extrapolations.
- `speculations/gravity-control.md`—Gravity Control: Engineering Spacetime Curvature Through Qi Coherence. Speculative. Treats the gravitational coupling as an engineering variable: a Qi condenser with a gate as a machine adjusting local mass-energy↔curvature conversion, with the SPARC fits imposing hard constraints on any device.
- `speculations/observational-seti.md`—Observational SETI: Signatures of Tuned Gate Networks. Speculative. A gate-harvesting civilization is nearly invisible to emissive SETI; catalogs structural, multi-rung signatures to point a telescope at, organized by cascade rung with mechanism and search band.
- `speculations/qi-bubble-propulsion.md`—Qi Bubble Propulsion: Rung-Shifting as a Travel Mechanism. Creative. Creative device ansatz for a proposed rung-shifting operation and five UAP observables; the canonical equations supply no rung-shift operator, inertial-decoupling law, hull coupling, or energy source, so no propulsion mechanism or energy budget is derived.
- `speculations/qi-computation.md`—Qi Computation: Information Processing as Yang-Yin Gate Dynamics. Speculative. Information as organized Π; the Qi gate as the fundamental computational primitive, the Wu Xing pentagon as 5-phase logic, and the cascade as a φ-spaced clock hierarchy.
- `speculations/superconductivity-as-qi-coherence.md`—Superconductivity as a Qi-Coherence Hypothesis. Creative. Creative material model with a separate coherence statistic $q_m$ and an underived pairing kernel; canonical $E_Y,E_I,q$ are not electronic variables, and no superconducting gap, transition-temperature formula, or Cassi prediction is established.

### speculations/creative-extensions/

Deliberately creative thought experiments—clearly labeled as such, not claims.

- `speculations/creative-extensions/README.md`—Creative Extensions. Index.
- `speculations/creative-extensions/coherence-collapse.md`—Coherence Collapse: Why the Universe Cannot End, and How Civilizations Die. Creative. The coherence budget makes spontaneous collapse astronomically improbable; what reliably dies is the intermediate structure—civilizations as gate networks with finite protection.
- `speculations/creative-extensions/coherence-commons.md`—The Coherence Commons: A Marxist Field-Materialist Theory of Production, Power, and Human Development. Creative—August 2026. Socioeconomic theory that separates physical analogy, hypothesized social mechanisms, Marxian categories, declared norms, and an operational empirical program; social quantities remain socioeconomic constructs, and commodity value remains Marxian socially necessary abstract labor.
- `speculations/creative-extensions/coherence-warfare.md`—Coherence Warfare: Attack, Defense, and the Physics of Shields. Creative. The coherence budget read as a weapons table: attack is organized, phase-matched perturbation; a shield is a φ-detuned boundary at which the phase-matching factor vanishes.
- `speculations/creative-extensions/first-contact-and-stellar-engineering.md`—The Universal Protocol: First Contact as φ-Structure Detection and Stellar Engineering as Gate Tuning. Creative. Log-periodicity with period $\ln\varphi$ as the universal language; a broadcast and a megastructure are both field operations, and the φ-periodic $P(k)$ search pipeline is the reception protocol.
- `speculations/creative-extensions/magic-systems.md`—Magic as Phase-Matched Field Operation. Creative. Magic and nature differ by one number, the phase-matching factor M: a working is organized perturbation with O(1) effects where random perturbation is cascade-suppressed.
- `speculations/creative-extensions/simulation-hypothesis.md`—The Simulation Hypothesis: The Universe as a Running PDE. Creative. The universe's source code as the two-fluid PDE—the grid, update rule, Planck resolution floor, horizon render distance—and why the simulation claim is unfalsifiable in the framework.
- `speculations/creative-extensions/universal-biology.md`—Universal Biology: The Cascade Ladder as a Convergent Evolutionary Scaffold. Creative. Biology occupies a fixed ladder band ($n \approx 136$–168); Fibonacci phyllotaxis and φ-scaled hierarchies are the unique de-resonant solutions every biosphere must share.

### hypotheses/

New application domains proposed for the framework, from nuclei to markets.

- `hypotheses/README.md`—Hypotheses—New Application Domains for the Cassi Framework. Exploratory catalog.
- `hypotheses/atmospheric-climate-cascade.md`—The Atmospheric Climate Cascade. Speculative. The Nastrom-Gage −3 → −5/3 spectral break near 500 km as a φ-break analogous to the turbulence $k_\varphi$, predicting φ-periodic structure in climate oscillation periods.
- `hypotheses/exoplanet-phi-spacing.md`—Exoplanet Orbital Spacing from the Wake-Wave Mechanism. Hypothesized. A supplied log-radius disk template gives the detached-orbit target $P_{\rm out}/P_{\rm in}=\varphi^{3/2}$; its tested Cassi dynamical realization is `REJECT` because driven phase layers are additive and the other registered arms produce no ladder. The confirmed-catalog Kepler classifier is **INDETERMINATE** and the scientific verdict **INCONCLUSIVE** because the target window overlaps the conventional wide-of-2:1 excess; the disk-gap channel remains pending.
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
- `hypotheses/scalar-time-reparameterization-applications.md`—Scalar Time Reparameterization in Cassi Applications. Derived conditional theorem / Hypothesized common-lapse application. Proves autonomous first-order scalar time-change equivalence; applies the conditions to PDEs, second-order systems, stochastic terms, memory, boundaries, and operator splits; the conversion age is exact on its isolated subflow, while CT-2 tests the universal lapse candidate.
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

- `predictions/README.md`—Predictions—The Falsifiable Catalog and Framework Glossary. Index. Holds the two master registries—the falsifiable prediction catalog with explicit input accounting grouped by experimental frontier, and the framework glossary of symbols and definitions—with the reading path glossary first, catalog second.
- `predictions/cassi_definitions.md`—Cassi Framework—Definitions. Reference. Glossary of the framework's symbols and definitions across 16 sections (φ, $E_Y$, $E_I$, $q$, $\xi = \varphi^6$, the φ-attractor, and more)—a unified field framework grounded in the φ-attractor and the Yin-Yang two-fluid, with emergent spacetime treated as an optional closure.
- `predictions/falsifiable-predictions.md`—Cassi Falsifiable Predictions. Reference. The 56-entry catalog of predictions with explicit input accounting grouped by experimental frontier, each with its test, current status, and detection timeline.

## 5. The code

Every claim in the papers is checked against code that lives in this repo; run everything from the repo root.

```
python two-fluid/cassi_two_fluid_3d_gpu.py    # core two-fluid PDE solver
python two-fluid/cassi_nbody.py               # GPU N-body solver
python two-fluid/calibrate_initial_ratio_xi.py  # w_a ODE with ξ = φ⁶
python computations/<pipeline>.py             # e.g. cascade_rge_pmns.py
python computations/matter_completion_boundary_check.py  # frozen nine-part conditional receipt
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
