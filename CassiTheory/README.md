# CassiTheory: Foundations for a Reality Simulator and Field AGI

**CassiTheory is the foundational theory repository for the Cassi project, whose two construction goals are a reality simulator and field-based artificial general intelligence.**

Cassi asks whether one evolving field substrate can organize both physical structure and intelligent action. This repository develops the laws, mathematical language, executable models, and evidence discipline needed to answer that question. Its scope spans fundamental physics, cosmology, complex systems, mind, and agency; every claim carries an epistemic status so that scope and evidential strength remain separate.

## The Cassi project

The broader project turns the same field proposal toward two coupled engineering programs:

1. **Reality simulation.** Build an executable, intervenable, multiscale field model in which matter, forces, geometry, and large-scale structure can be tested as dynamics of one substrate.
2. **Field-based artificial general intelligence.** Build an embodied system in which sensing, memory, prospective modeling, attention, action selection, and learning are causal processes of the evolving field itself.

Here, *reality simulator* names the engineering scope of the physical model. It carries no claim that the observed universe is a simulation. *Field AGI* names an architectural target: the field is the computational state and steering medium, while software around it supplies interfaces, measurement, and experimental control.

The active repositories divide the work by responsibility:

| Repository | Responsibility |
|---|---|
| `CassiTheory` | The laws: derivations, epistemic registries, reference solvers, experiments, and falsifiable predictions |
| `CassiCosmos` | The substrate: a live GPU field engine and reality-simulation workbench |
| `CassiCore` | The integration loop: orchestration, memory, tools, and bridges into the field |
| `CassiAI` | Read-only archive of predecessor neural-field architectures and lessons |

The live GPU substrate, field bridges, reference solvers, epistemic registries,
and preregistered probe chain exist today. A complete cross-domain physical
closure and an embodied prospective-agent loop remain open construction goals.

CassiTheory is where a proposed mechanism becomes explicit enough to implement, intervene on, measure, reject, or adopt.

## One shared field substrate

The framework begins with two nonnegative, reference-normalized density components conventionally named Yang and Yin:

$$
E_Y \ge 0,\qquad E_I \ge 0,\qquad
\rho = E_Y + E_I,\qquad
\varepsilon = E_Y-\varphi E_I.
$$

The canonical conversion term conserves total density $\rho$ and relaxes the local composition toward the declared fixed-point line

$$
\frac{E_Y}{E_I}=\varphi,
\qquad
\varphi=\frac{1+\sqrt5}{2}\approx1.618033989,
$$

under the stated solver assumptions. The selected theory form multiplies the
conversion by $(1-q)$; solver runs apply this form only when the gate is
enabled. The scalar Qi diagnostic is

$$
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}.
$$

The rational form of $q$ and its bare $\varphi^{-2}$ floor are Asserted
constitutive choices under the reference normalization; the bounds and
reference-state arithmetic are Derived conditional on that definition. The
scalar $q$ is bounded coherence bookkeeping. In the selected q-gated mode,
$(1-q)$ supplies the conversion gate.
Optional derived currents and phase coordinates can extend the diagnostics,
but physical transport or compact-phase interpretations require separately
declared constitutive dynamics. The full definitions and equations live in
`foundations/cassi-first-principles.md`.

The continued-fraction extremality of $\varphi$ is a Derived number-theory result. Its proposed physical role as a scale-separation target that resists resonant locking is Hypothesized and must be evaluated under explicit dynamics and comparison controls. The reference density and the dimensionful constants $c$, $\hbar$, and $G$ remain external inputs. Yang and Yin are neutral component names in the canonical PDE; expansive and contractive readings are phenomenological mappings unless a specific model supplies those dynamics.

The carrier-creation and continuum calculation makes the particle boundary
explicit. The first-order action preserves an exactly empty carrier sector,
and its stored Cartesian localized sequence is dominated by odd-even
ultraviolet structure. A continuum-consistent scalar calculation gives
independently reproduced static self-binding at prepared $Q_C=16$ and $256$;
the tested $Q_C=4$ profiles spread and $Q_C=64$ remains numerically
inconclusive. The smooth $Q_C=16$ constrained spectra contain no resolved
negative mode on the measured grids, but the frozen combined stability
verdict is `INCONCLUSIVE`. A source-independent localized production
mechanism, particle identity and physical normalization remain open
(`computations/matter-formation-continuum-report.md`).
An optional positive-inertia scalar parent has independently verified
Gaussian pair correspondence and finite-grid charged radial support.
Its selected population-256 angular and phase sectors support on four
grids, but one of eight spatial comparisons fails; combined scalar-parent
spatial qualification remains `INCONCLUSIVE`. Physical normalization,
interacting creation and particle quantum numbers remain unselected.
Matching one external vacuum mass, speed and internal generator unit
leaves a family of scalar normalizations. At the fixed coefficients, the
additional scalar core-cell assignment is contradicted. The proposed
Dirac chiral-scalar density map also has independently checked positivity
and Hermiticity obstructions, so its physical coupling remains open
(`computations/matter-formation-continuum-report.md` §12).

A separate positive spinor component map has an exact chiral-current
interpretation. Its closed Dirac evolution does not reproduce the canonical
population conversion. With the specified minimal conversion channel, a
nonzero Dirac mass moves the stationary ratio below $\varphi$, and the
channel permits leakage from the positive-energy one-particle subspace.
These independently verified finite-dimensional results leave physical
energy-density normalization, a reservoir interaction and a controlled
quantum reduction open (`foundations/sector-coupling-derivation.md`
§§1.5–1.6; `computations/matter-formation-continuum-report.md` §13).

A separately specified real scalar can excite fermion pairs from a
declared vacuum while receiving reciprocal feedback. Independent
full-covariance and Bloch-vector calculations agree on 32 analytic
quench/pulse rows and six retained trajectories, with all 1,185 checks
passing. The finest closed trajectory reaches occupation $0.5729566253$
per spin with relative energy error $5.6211\times10^{-5}$ and second-order
time convergence. The source, spinor field, coefficients and finite-mode
subtraction are supplied assumptions; physical Cassi matching,
continuum renormalization and localized matter formation remain open
(`computations/matter-formation-continuum-report.md` §14).

The continuum calculation narrows this model's scope. Sudden mass
changes and square pulses produce ultraviolet-divergent excitation
energy. A specified static subtraction is verified, while compatible
initial states and dynamical renormalization remain required. The
unchanged coupling excludes two-body binding in the leading
nonrelativistic Yukawa approximation. The collective local-density Yukawa
functional is separately qualified to have no subthreshold bound state under
its stated mass-depleting and vacuum-prescription assumptions; relativistic
and other many-body localization remain outside these restrictions
(`computations/matter-formation-continuum-report.md` §§15.6–15.7).

The specified local static one-loop energy has positive reference
curvature but no global lower bound. A verified negative bulk-energy
witness makes a widening neutral trial bubble energetically
unbounded below. The full nonlocal quantum model and metastable
localized states require separate work
(`computations/matter-formation-continuum-report.md` §16).

The compact-target and relative-orientation checks sharpen that boundary. An
independently supplied compact $SU(2)_{\rm top}$ field qualifies radial
stationarity and energetic stability. A smooth pointwise map of the two
canonical densities has zero degree density. In the optional phase-bearing
gauge sector, the physical relative target is an $S^2$ at fixed nonzero norms.
Joint gauge cancellation leaves a nonconstant relative texture as independent
field information, and the induced screening scale is comparable to the
predicted stationary size. Every exact hard-norm nonzero-Hopf adjoint in the
stated soft-action domain has a negative amplitude variation, and the included
hard Finkelstein–Rubinstein loops contract there. Amplitude-relaxed
metastability remains open (`computations/matter-formation-continuum-report.md`
§§18–20).

The supplied scalar temporal parent also has an excited periodic mediator
orbit with exact carrier Floquet growth, a faster independently reproduced
spatial mediator instability and local separation of prepared opposite
carrier charge. Exactly empty carrier data remain invariant. The frozen
nonlinear plane-symmetric comparison returns `INCONCLUSIVE`; a post-hoc
period-sampled diagnostic identifies phase aliasing while leaving that verdict
unchanged (`computations/matter-formation-continuum-report.md` §§25–28).

Scalar and Dirac parents produce the same measured slow carrier equation while
retaining different spin and statistics. The inverse map from the registered
observables to a microscopic theory is many-to-one. Complete matter formation
therefore still requires one canonical action, a quantum-state rule, physical
normalization, infinite-domain localization and stability, localized
real-time forming evolution and an observable particle discriminator
(`computations/matter-formation-continuum-report.md` §29;
`foundations/matter-completion-boundary.md` §12).


## The reality-simulation program

The reality simulator turns theoretical statements into dynamics that can be perturbed and measured. Its target is a field engine that supports local evolution, structure formation, gravity, particles, scale coupling, and cosmological behavior without changing the underlying computational vocabulary at every domain boundary.

`CassiCosmos` runs the live GPU substrate. CassiTheory supplies the canonical two-fluid equations, conditional extensions, reference Python solvers, numerical checks, and domain claims that the engine can test. This separation keeps the evidence legible:

- a derivation states what follows from declared assumptions;
- a solver establishes what those equations do under specified conditions;
- a simulator exposes causal behavior under intervention;
- observation determines the empirical status of the physical mapping.

The physical program advances through measured gates. Visual resemblance can motivate a probe; adoption depends on the declared statistic and controls. Emergent structure in a simulation supports only the mechanism, scale range, and behavior that were actually exercised.

## The field-AGI program

Cassi treats intelligence as organized steering of flow. The design thesis is:

$$
\boxed{\text{Intelligence begins when possible flow becomes part of present flow.}}
$$

A field becomes prospectively intelligent when internally represented possible futures change its present physical trajectory before those futures occur, and when the resulting prediction error changes how it steers next time. The minimal causal loop is:

```text
maintained embodiment
    → boundary-localized sensing
    → structured history and a present self/world state
    → several action-conditioned future flows
    → viability, energy, information, and option evaluation
    → commitment and resource-debited action
    → observed consequences and prediction error
    → memory and plastic change
    → revised future steering
```

The causal criterion includes organized motion, coherence, separable prospective branches, and intervention on later action. Changing a branch must change the selected action, and that action must alter subsequent outcomes. A complete implementation therefore needs a maintained body boundary, an energy reserve and ledger, sensors, effectors, structured memory, a decoupled forward model, competing action possibilities, bounded attention, commitment, and plasticity across multiple timescales.

The canonical two-fluid PDE already supplies material state, shared flow, conversion, diffusion, optional potential coupling, and coherence diagnostics. Prospective branches, internally represented viability, resource-debited actuation, action competition, and learned constitutive change remain mechanisms to build and test. Field-based AGI remains an active construction program; the present solver supplies only part of the required architecture. Phenomenal consciousness remains a separate philosophical and empirical question.

`foundations/physical-becoming-hierarchy.md` gives this program its mathematical contract. It separates microscopic actual physics, mesoscopic open-system dynamics, and agent-level reaction coordinates; embeds the exact canonical conversion in a dissipative operator block; and defines held-out closure, branch-causality, attention, work-debit, learning, and generalization gates. The current field-experience record supplies substrate measurements, while the first complete closed-loop target is a resource-limited Hungry Detour experiment with no-shadow and reactive controls.

## The logic-flow method

Cassi develops through a regulated cycle of expansion and contraction:

```text
observation + lived experience + analogy + philosophy
                         │
                         │ expand
                         ▼
                 candidate mechanisms
                         │
                         │ contract
                         ▼
       variables → dimensions → budgets → equations
                         │
                         ▼
       preregistered simulation and causal intervention
                         │
                         ▼
          support, null, contradiction, or surprise
                         │
                         ▼
               reorganized model and questions
                         └───────────────↺
```

Expansion supplies possibilities. Contraction turns a possibility into a model that can fail. The cycle follows five rules:

1. **Experience can constrain architecture.** Lived experience and observation identify capacities and discriminating behaviors worth explaining. Microscopic identities require independent mathematical and empirical support.
2. **Causal language requires causal roles.** Memory must carry ordered past information into later behavior; attention must reallocate a finite budget; an internal model must predict action-conditioned consequences; a goal must causally influence action from an internally represented future or viability state.
3. **Mathematics carries the commitment.** Every serious mechanism needs state variables, dimensions, evolution laws, source or conservation accounting, stability bounds, and an intervention that can disable or distinguish it.
4. **Measurements govern reorganization.** Statistics, controls, decision trees, and stopping rules are frozen before expensive probes. Nulls, contradictions, and instability return new constraints to the next expansive phase.
5. **Adoption preserves provenance.** A surviving mechanism enters the framework only at the tier and scope its derivation, calibration, fit, or experiment supports.

This is both a research philosophy and an engineering discipline: imagination opens the state space; mathematics and intervention contract it; surprise changes the law of the next search.

## Scientific status and evidence boundaries

CassiTheory is a live theoretical research program. The canonical PDE, gate, and normalization include declared postulates and selected model conventions. Algebraic consequences can be Derived conditional on those inputs; physical identifications require their own evidence.

`Asserted` marks a selected definition, equation form, or convention. Its
mathematical consequences are Derived only conditional on that input.

The repository uses five evidential tiers for public claims, plus **Creative** for exploratory applications outside the evidential ladder:

| Tier | Meaning |
|---|---|
| **Derived** | An a priori consequence of the declared $\varphi$ structure and PDE; every fitted, anchored, or external input retains its own status |
| **Calibrated** | The framework supplies the form and an observation anchors a value |
| **Mapped** | A placement, exponent, offset, or normalization was fitted or selected and is recorded in the Fit-Status Ledger |
| **Hypothesized** | A mechanism is specified with a pinned $\varphi$-power or testable prediction; otherwise it remains Speculative |
| **Speculative** | A framework-consistent extension whose decisive test or mechanism remains open |
| **Creative** | An exploratory application outside the evidential ladder |

The source-of-truth records are:

- `open-questions-cassi-answers.md`—which questions the framework addresses and at what tier;
- `parameter-inventory.md`—every parameter, convention, calibration, fit, initial condition, and numerical control;
- `predictions/falsifiable-predictions.md`—the prediction catalog and test designs;
- `audit.md`—current agreement, tension, and failure against observation;
- `EPISTEMIC-MAP.md`—every theory document indexed by tier;
- `field-experience/probe-outcome-ledger.md`—the frozen outcomes of the current field-experience probe chain.

Negative results are retained as constraints on the next model. They narrow the architecture and prevent a visually suggestive field pattern from acquiring a causal interpretation that its controls did not establish.

## Where to start

Choose the path that matches your question:

| Goal | Reading path |
|---|---|
| Understand the project and core physics | `cassi-physics.md` → `foundations/cassi-first-principles.md` |
| Follow the derivation structure | `foundations/README.md` → `foundations/dimensionful-cascade.md` → `foundations/cascade-suppression-formula.md` |
| Study quantum free fall and the remaining closure requirements | `foundations/quantum-free-fall-correspondence.md` §§9–12 → `foundations/physical-becoming-hierarchy.md` §7.4 → `gravity/quantum-gravity.md` §3.1 |
| Evaluate the evidence | `open-questions-cassi-answers.md` → `audit.md` → `predictions/falsifiable-predictions.md` |
| Study mind and field intelligence | `cassi-psychology.md` → `foundations/qi-flow-double-helix.md` → `field-experience/probe-outcome-ledger.md` |
| Browse the complete document graph | `reading-guide.md` |

`predictions/cassi_definitions.md` is the symbol and vocabulary reference.

## Repository map

| Path | Contents |
|---|---|
| `foundations/` | Canonical field definitions, the cascade wedges, and core derivations |
| `principles/` | Cross-cutting principles, including de-resonance |
| `standard-model/`, `particles/`, `gravity/`, `cosmology/`, `turbulence/` | Domain applications and their calculations |
| `consciousness/` | Hypothesized and speculative mappings from field dynamics to mind and embodied experience |
| `two-fluid/` | Two-fluid PDE, GPU N-body, gate, ODE, and diagnostic solvers |
| `computations/` | Reproducible derivation and verification pipelines |
| `experiments/` | Catalog and observational analyses, controls, and survey tests |
| `field-experience/` | Preregistered finite-field probes, scripts, reports, and the outcome ledger |
| `predictions/` | Falsifiable prediction catalog and framework glossary |
| `analyses/` | Data-facing assessments of specific catalogs and claims |
| `hypotheses/`, `speculations/` | New domains and explicitly lower-tier extensions |
| `visual-explainers/` | Reproducible mathematical figures and animations |

## Executable research

All code that supports CassiTheory claims lives in this repository. Run scripts from the repository root with Python 3. Examples:

```bash
# Compact numerical verification
python computations/verify_planck_crossover.py

# Canonical two-fluid solver in its cosmology mode
python two-fluid/cassi_two_fluid_3d_gpu.py --mode cosmos --N 128

# Spectral particle-mesh N-body solver
python two-fluid/cassi_nbody.py
```

The paper or pre-registration associated with each script defines its inputs, statistic, controls, and interpretation. There is no project-wide test harness: reproducibility comes from direct script execution, retained numerical output, preregistered gates, and synchronized registries.

For the complete inventory and reading paths, continue to `reading-guide.md`. For repository conventions, claim discipline, and contribution rules, read `AGENTS.md`.
