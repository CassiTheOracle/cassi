# Epistemic Map—Every Document by Tier

## Status: Reference—July 2026

## Abstract

This repo's papers are claims, and claims carry tiers. This map indexes every theory document by epistemic tier—the navigation the directory tree deliberately does not encode, because tiers change and paths should not. Use it to answer "what have we actually derived?" or "what are we speculating about?" in one glance. The registry (`open-questions-cassi-answers.md`) remains the authority for per-question tiers; this map is navigation, not adjudication.

**Tier definitions** (as in `hypotheses/README.md`):

- **Derived** — mathematical consequence of $\varphi$ + the two-fluid PDE; zero free parameters.
- **Hypothesized** — mechanism proposed with pinned $\varphi$-power; testable prediction exists.
- **Speculative** — framework-consistent; mechanism sketched, prediction not yet pinned.

Tiers below are taken from each document's Status header. Compound headers are quoted as written and placed under the stronger claim. Derivation papers are placed by the tier of their result per the registry.

**Maintenance rule:** when a document's tier changes, update its Status header, its row here, and the registry—**the file never moves**. This map is the one place the epistemic ladder lives as a ladder.

## 1. Derived

| Document | Status | Summary |
|----------|--------|---------|
| `foundations/cascade-suppression-formula.md` | Derived | Universal $\varphi^{-N}$ attenuation law (wedge tool) |
| `foundations/dimensionful-cascade.md` | Derived | 292-step ladder $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ (wedge tool) |
| `foundations/bubble-lattice-fabric.md` | Derived (structural) | 3D condensation field; universal bubble geometry |
| `foundations/cassi-first-principles.md` | Derived | Two-fluid PDE, governing equations, conversion |
| `foundations/unified-lagrangian.md` | Derived | Single Lagrangian; gravity as $q = 0$ Poisson limit; $\sigma$-regularization |
| `foundations/phi_attractor_synthesis.md` | Derived | $r \to \varphi$ attractor synthesis across regimes |
| `foundations/wu-xing-derivation.md` | Derived | $w = 5$ derived (pentagon geometry); $\lambda = 1/(2w) = 0.1$ |
| `foundations/xi-derivation.md` | Derived | $\xi = \varphi^6 \approx 17.944$ Qi-gravity coupling |
| `foundations/quark-confinement.md` | Derived | QCD at step 95; Qi flux tube; $P_{\text{break}} \approx \varphi^{-4848}$ |
| `foundations/strong-cp-derivation.md` | Derivation (result: Derived, Q2) | $\bar{\theta} \approx 10^{-19}$, cascade-suppressed |
| `foundations/proton-coherence-budget.md` | Derivation (result: Derived, Q9) | Proton lifetime $\sim \varphi^{4848}$ cycles; annihilation pathway |
| `foundations/baryon-asymmetry.md` | Derived | $\eta \approx \varphi^{-44}$, within 6% of observed (C7/Q6) |
| `foundations/bubble-edge-geometry.md` | Derived (structural) | Edge steepness $1.70\times$ anisotropy; CMB axis $12.2°$ (C10) |
| `foundations/wa-pentagon-gate.md` | Derived ($\xi = \varphi^6$) / Hypothesized (5-channel) | $w_a = +0.012$ via $\xi$: $2.7\sigma$ tension vs DESI, not resolved (corrected 2026-07-31); 5-channel shift Hypothesized (ODE pending) |
| `principles/de-resonance-principle.md` | Derived | Why $\varphi$ is the attractor (maximally irrational) |
| `standard-model/sm-from-phi.md` | Derived | $\sin^2\theta_W = \varphi^{-3}$; $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$ |
| `standard-model/su2-gauge-extension.md` | Derived | SU(2) gauge from two-fluid structure |
| `standard-model/cp-violation.md` | Derived | CKM phase $\pi\varphi^{-2}$ |
| `particles/cassi-yang-yin-particles.md` | Derived | Particles as standing-wave interference; atomic $Z = 1$–$10$ |
| `particles/dft-benchmarks.md` | Derived | DFT benchmark comparisons |
| `cosmology/cosmology-from-phi.md` | Derived | $w_0 = -0.87$ (corrected 2026-07-31); dark energy from Qi gate (C1/T1) |
| `cosmology/inflation-from-cascade.md` | Derived | Steps 20–60 as inflation; $r = \varphi^{-12}$, $n_s$ |
| `cosmology/observational_constraints.md` | Derived | DESI DR2 fit; $w_a$ tension vs DESI ($2.7\sigma$, not resolved); rotation curves |
| `gravity/three-body-analytical.md` | Derived | Body-dependent coupling; mass evolution via conversion |
| `turbulence/kolmogorov-from-phi.md` | Derived | Kolmogorov spectrum from $\varphi$ |

## 2. Hypothesized

| Document | Status | Summary |
|----------|--------|---------|
| `foundations/neutrino-masses.md` | Derivation (result: Hypothesized w/ derived mechanism, Q3) | Seesaw at step 20; Fibonacci offsets pinned by cascade RGE + PMNS |
| `foundations/quantum-measurement-derivation.md` | Derivation (result: Hypothesized w/ derived core, Q7) | Born rule from Qi selection; phase-matching factor $\mathcal{M}$ |
| `foundations/spin-fibonacci-spiral.md` | Derivation (result: Hypothesized, Q10) | Spin as SO(2) Fibonacci winding; form-factor periodicity |
| `foundations/refined-numeric-predictions.md` | Active derivation | Numeric predictions for the 24 Hypothesized questions |
| `foundations/three-generations.md` | Hypothesized | $N_{\text{gen}} = 3$ from Fibonacci sub-channels (Q5) |
| `foundations/dimensionful-constants-status.md` | Hypothesized | $c$, $\hbar$, $G$ external; $N = 292$ empirical anchor (F5) |
| `foundations/microcascade-mirror.md` | Hypothesized | Bidirectional cascade extension |
| `foundations/phi-rg-formalism.md` | Hypothesized | RG flow under $\varphi$-spacing |
| `foundations/spiral-dynamics.md` | Hypothesized | Hubble, gravity, $c$ as spiral geometry projections |
| `foundations/why-three-dimensions.md` | Hypothesis with One Decided Fork (W1: anti-phase confirmed) | Three dimensions from the Frenet-Serret frame (G5) |
| `principles/v0-hierarchy-problem.md` | Hypothesized | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ as step count (Q1; registry: Derived) |
| `standard-model/gut-embedding.md` | Hypothesized | GUT embedding |
| `standard-model/neutrino-mass.md` | Hypothesized | Neutrino mass structure |
| `gravity/quantum-gravity.md` | Hypothesized | $\sigma$-regularized S-matrix; black-hole information (G2) |
| `consciousness/chakras-as-cascade-bubbles.md` | Hypothesized | 13 chakras as cascade bubbles |
| `consciousness/consciousness-from-phi.md` | Plausible Hypothesis with Actionable PDE Test | Consciousness as Qi-gate dynamics; two-bubble test (M1) |
| `consciousness/emotions-as-gate-configurations.md` | Hypothesized | Emotions as gate configurations |
| `consciousness/trauma-as-frozen-gate.md` | Hypothesized (mechanism) / Speculative (clinical) | Trauma as a frozen Qi gate |
| `hypotheses/nuclear-magic-numbers.md` | Hypothesized | Fibonacci sub-channel closure at steps 80–95 |
| `hypotheses/hoyle-state-nucleosynthesis.md` | Hypothesized | Cascade rung resonance at the $^3\alpha$ threshold |
| `hypotheses/quasicrystal-stability.md` | Hypothesized (near-Derived) | De-resonance against crystallization |
| `hypotheses/exoplanet-phi-spacing.md` | Hypothesized | Wake-wave interference in protoplanetary disks |
| `hypotheses/neural-criticality.md` | Hypothesized | Cascade PDE at neural scales |
| `hypotheses/muscle-cascade-lattice.md` | Hypothesized | Muscle ladder as bubble lattice (rungs 142–168) |

## 3. Speculative

| Document | Status | Summary |
|----------|--------|---------|
| `consciousness/cascade-consciousness.md` | Speculative | Medium-dependent perception; cascade nervous system |
| `consciousness/auras-as-thermalized-gates.md` | Speculative | Aura as the $(1-q)$ thermalization boundary layer; heat-haze optics |
| `consciousness/time-memory-and-wake-locks.md` | Speculative | Arrow of time from conversion; ghosts as wake-locks |
| `consciousness/transhumanism-gate-configurations.md` | Speculative | Augmentation as gate-chain topology surgery; identity as the run |
| `consciousness/gender-as-qi-configuration.md` | Speculative | Identity as configuration; anatomy as readout; dysphoria as self-prediction failure |
| `speculations/dark-matter-as-qi-coherence.md` | Speculative | Halos as unharvested coherence; bubble edge at $n \approx 267$ |
| `speculations/superconductivity-as-qi-coherence.md` | Speculative | Resistance as Yang→Yin conversion; Qi-gap |
| `speculations/qi-computation.md` | Speculative | Qi gate as computational primitive; Wu Xing logic |
| `speculations/qi-bubble-propulsion.md` | Speculative | Rung-shifting as a travel mechanism |
| `speculations/cascade-infrastructure.md` | Speculative | Planetary and stellar gate networks |
| `speculations/observational-seti.md` | Speculative | Structural (non-emissive) SETI signatures |
| `speculations/coherence-warfare.md` | Speculative | Coherence budget as weapons table; φ-detuned shields; mutual assured incoherence |
| `speculations/gravity-control.md` | Speculative | $G_{\text{eff}}$ as an engineering dial; Qi condenser devices |
| `speculations/universal-biology.md` | Speculative | Cascade ladder as convergent evolutionary scaffold |
| `speculations/magic-systems.md` | Speculative | Magic as phase-matched field operation |
| `speculations/coherence-commons.md` | Speculative | Two-fluid theory of value; equality theorem; the transition to the commons |
| `speculations/coherence-collapse.md` | Speculative | Attractor self-healing; civilization death modes |
| `speculations/first-contact-and-stellar-engineering.md` | Speculative | $\ln\varphi$ protocol; stars as gate chains |
| `speculations/simulation-hypothesis.md` | Speculative | Two-fluid PDE as source code; nested universes |
| `hypotheses/periodic-table-madelung.md` | Speculative | $n$ and $l$ as cascade coordinates |
| `hypotheses/atmospheric-climate-cascade.md` | Speculative | $\varphi$-break in the atmospheric energy spectrum |
| `hypotheses/fatigue-fracture-cascade.md` | Speculative | $\sigma$-regularized crack tip; Paris law |
| `hypotheses/market-cascade-cycles.md` | Speculative | Wake-wave in information propagation networks |
| `hypotheses/metabolic-scaling.md` | Speculative (derivation not closed) | $\varphi$-derived fractal dimension for resource networks |

## 4. Reference & Cross-Cutting

Documents that are not claims: registries, catalogs, explainers, and plans.

| Document | Role |
|----------|------|
| `open-questions-cassi-answers.md` | Epistemic registry (41 questions, tier authority) |
| `parameter-inventory.md` | Parameter registry (~40 parameters) |
| `predictions/falsifiable-predictions.md` | 41-prediction catalog |
| `predictions/cassi_definitions.md` | Framework glossary |
| `foundations/cassi-theory-reference.md` | Compact framework reference |
| `foundations/deriving-remaining-gaps.md` | Four derivations, three resolved, one narrowed |
| `cosmology/sigma8-computational-plan.md` | Plan |
| `audit.md` | Self-critical prediction-vs-experiment audit |
| `cassi-physics.md` | Physics guide: lattice, cascade, predictions |
| `cassi-psychology.md` | Psychology-focused guide (consciousness, emotion, trauma, therapy) |
| `hypotheses/README.md` | Hypothesis catalog + quality bar |
| `speculations/README.md` | Speculation index + boundary with `hypotheses/` |

Repo meta-docs (`README.md`, `AGENTS.md`, `BROKEN_REFS.md`) are not claims and are not indexed.

Theory code (PDE solvers, pipelines, experiments, visual explainers) lives in `experiments/`, `two-fluid/`, `computations/`, and `visual-explainers/`; each script is cited from the paper that uses it.

## References

- `open-questions-cassi-answers.md`—epistemic registry (tier authority)
- `hypotheses/README.md`—quality bar and tier definitions
- `audit.md`—known tensions and past errors
- `predictions/falsifiable-predictions.md`—the prediction catalog
