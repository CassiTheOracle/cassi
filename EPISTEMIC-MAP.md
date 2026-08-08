# Epistemic Map—Every Document by Tier

## Status: Reference—August 2026

## Abstract

This repo's papers are claims, and claims carry tiers. This map indexes every theory document by epistemic tier—the navigation the directory tree deliberately does not encode, because tiers change and paths should not. Use it to answer "what have we actually derived?" or "what are we speculating about?" in one glance. The registry (`open-questions-cassi-answers.md`) remains the authority for per-question tiers; this map is navigation, not adjudication.

**Tier definitions** (as in `hypotheses/README.md`):

- **Derived**—a priori mathematical consequence of $\varphi$ + the two-fluid PDE; zero fitted or anchored constants.
- **Calibrated**—framework form with the constant's value anchored to a stated observation; downstream claims using the pinned value inherit the anchor.
- **Mapped**—placement (rung, exponent, offset, candidate, normalization) selected or fitted to data; the fit is recorded in the Fit-Status Ledger (`parameter-inventory.md` §10).
- **Hypothesized**—mechanism proposed with pinned $\varphi$-power; testable prediction exists.
- **Speculative**—framework-consistent; mechanism sketched, prediction not yet pinned.
- **Creative**—exploration, not a claim (`speculations/creative-extensions/`); exempt from the evidential ladder.

Reference / Index / Synthesis / Plan / Registry / Catalog are genres, not
epistemic tiers; "Tested" is a verification marker that attaches to a tier and
never upgrades one. The former "near-Derived" label is retired—use the honest
tier.

Tiers below are taken from each document's Status header. Compound headers are quoted as written and placed under the stronger claim. Derivation papers are placed by the tier of their result per the registry.

**Maintenance rule:** when a document's tier changes, update its Status header, its row here, and the registry—**the file never moves**. This map is the one place the epistemic ladder lives as a ladder.

## 1. Derived

| Document | Status | Summary |
|----------|--------|---------|
| `foundations/cascade-suppression-formula.md` | Derived | Universal $\varphi^{-N}$ attenuation law (wedge tool) |
| `foundations/dimensionful-cascade.md` | Derived | 292-step ladder $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ (wedge tool) |
| `foundations/wake-geometry.md` | Derived (structural) with Hypothesized closure imprint | Wake geometry: $\Lambda_Y + \Lambda_I = \ell_{n+1}$ closure; envelope checkerboard; closure ladder; $N_\infty \approx 294.2$ (292–296) |
| `foundations/bubble-lattice-fabric.md` | Derived (structural) | 3D condensation field; universal bubble geometry |
| `foundations/cassi-first-principles.md` | Derived | Two-fluid PDE, governing equations, conversion |
| `foundations/unified-lagrangian.md` | Derived | Single Lagrangian; gravity as $q = 0$ Poisson limit; $\sigma$-regularization |
| `foundations/phi_attractor_synthesis.md` | Derived (attractor synthesis) / Calibrated ($\xi$ pin) / Mapped ($\alpha_{\text{halo}} = 0.7$ nominal—ledger) | $r \to \varphi$ attractor synthesis across regimes |
| `foundations/wu-xing-derivation.md` | Derived (w = 5, gap, r₀) / Calibrated (w₀ via the DESI-anchored coupling form—ledger) | $w = 5$ derived (pentagon geometry); $\lambda = 1/(2w) = 0.1$ (`cassi-physics.md`) |
| `foundations/wu-xing-cycle-structure.md` | Derived (cycle geometry, coupling, ring algebra) / Tested (ke ring PDE 2026-07-31, WX1 gate level 2026-08-01) / Hypothesized (affinity gradient, clinical profile) | Two coherent 5-cycles (sheng/ke); control-ring algebra; 5↔13 chakra partition |
| `foundations/xi-derivation.md` | Derived rung identity / Calibrated empirical pin (MW anchor—ledger) | $\xi = \varphi^6 \approx 17.944$ Qi-gravity coupling |
| `foundations/quark-confinement.md` | Derived | QCD at step 95; Qi flux tube; $P_{\text{break}} \approx \varphi^{-4506}$ |
| `foundations/proton-coherence-budget.md` | Derivation (rung exponent Mapped—ledger; per-rung $q_i$ profile Hypothesized) | Proton lifetime $\sim \varphi^{4506}$ cycles; annihilation pathway |
| `foundations/sector-coupling-derivation.md` | Derived scale with Hypothesized coefficient (v₀ input Calibrated, N_pde normalization Mapped—ledger) | Dirac↔two-fluid sector-coupling scale $\kappa_s = \varphi^{-6}/v_0^2$ (0.92 TeV$^{-2}$; $\kappa_s^{-1/2} \approx 1.04$ TeV) |
| `foundations/bubble-edge-geometry.md` | Derived (structural) | Edge steepness $1.70\times$ (Derived); CMB axis $12.2°$ (measured—Calibrated; boundary mechanism Hypothesized, post-hoc) |
| `foundations/wa-pentagon-gate.md` | Derived ($\xi = \varphi^6$) / Hypothesized (5-channel) | $w_a = +0.012$ via $\xi$: $2.7\sigma$ baseline; with the ratified coupling $1.25\sigma$ (B2, unstable); the stable realization (10/12): pure-Λ window fit $(-1, 0)$, $4.17\sigma$/$2.61\sigma$; 5-channel shift Hypothesized (ODE pending) |
| `principles/de-resonance-principle.md` | Derived | Why $\varphi$ is the attractor (maximally irrational) |
| `principles/v0-hierarchy-problem.md` | Derived (step count, per registry Q1); 5.3% residual open | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ as step count (Q1) |
| `standard-model/sm-from-phi.md` | Derived | $\sin^2\theta_W = \varphi^{-3}$; $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$ |
| `standard-model/sm-radiative-corrections.md` | Derived | Loop corrections from the φ-boundary: RGE, Δα, Δr → m_W, λ running; residuals ($\alpha_s$ $2\times$, $\alpha_1$/$\alpha_2$ ~25%) open |
| `standard-model/su2-gauge-extension.md` | Derived | SU(2) gauge from two-fluid structure |
| `standard-model/cp-violation.md` | Derived (δ_CKM Mapped—ledger; Jarlskog invariant not reproduced) | CKM phase $\pi\varphi^{-2}$ |
| `particles/cassi-yang-yin-particles.md` | Derived | Particles as standing-wave interference; atomic $Z = 1$–$10$ |
| `particles/dft-benchmarks.md` | Derived | DFT benchmark comparisons |
| `cosmology/cosmology-from-phi.md` | Derived | $w_0 = -0.87$; dark energy from Qi gate (C1/T1) |
| `gravity/three-body-analytical.md` | Derived | Body-dependent coupling; mass evolution via conversion |
| `turbulence/kolmogorov-from-phi.md` | Derived | Kolmogorov spectrum from $\varphi$ |

## 2. Calibrated

| Document | Status | Summary |
|----------|--------|---------|
| `cosmology/observational_constraints.md` | Calibrated ($w_0$ coupling form, $\xi$ pin—ledger) / Mapped ($\alpha_{\text{halo}}$ nominal, halo $q$—ledger) | DESI DR2 fit; $w_a$ tension $2.7\sigma$ baseline; $1.25\sigma$ (B2, unstable) and pure-Λ $(-1, 0)$ at $2.61\sigma$ (stable realization—10/12) with the ratified coupling; rotation curves |

## 3. Mapped

| Document | Status | Summary |
|----------|--------|---------|
| `foundations/strong-cp-derivation.md` | Derivation (span Mapped: GUT-seed anchor and δ_CP per ledger; θ̄ ≈ 1.2×10⁻¹⁷) | $\bar{\theta} \approx 1.2 \times 10^{-17}$, cascade-suppressed |

## 4. Hypothesized

| Document | Status | Summary |
|----------|--------|---------|
| `foundations/neutrino-masses.md` | Derivation (offsets Mapped—ledger; result Hypothesized, Q3) | Seesaw at step 20; Fibonacci offsets pinned by cascade RGE + PMNS |
| `foundations/quantum-measurement-derivation.md` | Derivation (result: Hypothesized w/ derived core, Q7) | Born rule from Qi selection; phase-matching factor $\mathcal{M}$ |
| `foundations/spin-fibonacci-spiral.md` | Derivation (result: Hypothesized, Q10) | Spin as SO(2) Fibonacci winding; form-factor periodicity |
| `foundations/baryon-asymmetry.md` | Derivation (mechanism Hypothesized, C7/Q6; η exponent Mapped—ledger) | $\eta \approx \varphi^{-44}$, within 6% of observed (C7/Q6) |
| `foundations/refined-numeric-predictions.md` | Active derivation (C10 CMB axis: Calibrated angle / Hypothesized mechanism—2026-08) | Numeric predictions for the 24 Hypothesized questions; C10 $12.2°$ measured (calibrated from data vectors), boundary mechanism post-hoc |
| `foundations/three-generations.md` | Hypothesized (mechanism) / Mapped (rung placements—ledger) | $N_{\text{gen}} = 3$ from Fibonacci sub-channels (Q5) |
| `foundations/dimensionful-constants-status.md` | Hypothesized ($c$, $\hbar$, $G$ external) / Mapped (fitted exponents—ledger) | $c$, $\hbar$, $G$ external; $N = 292$ epoch-dependent horizon rung (F5) |
| `foundations/microcascade-mirror.md` | Hypothesized | Bidirectional cascade extension |
| `foundations/rung-offset-mechanism.md` | Derived quantization, Hypothesized selection, Empirical catalog (μ/Jψ placements Mapped—38-state scan, ledger) | δn as two-fluid phase lag (analytic $A_0$, $B_0$); pool-cell mode quantization; sector edges at half-rungs; uniform 38-state baseline |
| `foundations/phi-rg-formalism.md` | Hypothesized | RG flow under $\varphi$-spacing |
| `foundations/spiral-dynamics.md` | Hypothesized | Hubble, gravity, $c$ as spiral geometry projections |
| `foundations/why-three-dimensions.md` | Hypothesis with One Decided Fork (W1: anti-phase confirmed) | Three dimensions from the Frenet-Serret frame (G5); d = 3 supported conditionally on the three postulates (2026-08) |
| `standard-model/gut-embedding.md` | Hypothesized | GUT embedding |
| `standard-model/neutrino-mass.md` | Hypothesized | Neutrino mass structure |
| `gravity/quantum-gravity.md` | Derived (σ-regularization, G1) / Hypothesized (two-fluid quantization, G2) | $\sigma$-regularized S-matrix; black-hole information (G2) |
| `cosmology/inflation-from-cascade.md` | Derivation (mechanism Hypothesized, C4; r exponent Mapped—ledger) | Steps 20–60 as inflation; $r = \varphi^{-12}$, $n_s$ |
| `cosmology/desi-lattice-averaging.md` | Hypothesized | Lattice powder lines in $P(k)$; variance suppression; $D_A(z)$ wiggle bound |
| `consciousness/chakras-as-cascade-bubbles.md` | Hypothesized | 13 chakras as cascade bubbles |
| `consciousness/consciousness-from-phi.md` | Plausible Hypothesis with Actionable PDE Test | Consciousness as Qi-gate dynamics; two-bubble test (M1) |
| `consciousness/emotions-as-gate-configurations.md` | Hypothesized | Emotions as gate configurations |
| `consciousness/trauma-as-frozen-gate.md` | Tested—null pinning, drive effect supported (2026-07-31) / Speculative (clinical) | Trauma as a frozen Qi gate |
| `consciousness/two-strand-qi-neuroscience.md` | Hypothesized (strand geometry) / Speculative (neural mapping) | Two-strand Qi condensate; centerline/separation decomposition; strand modes; NS1–NS4 PDE statuses (lock-timescale nulls, 2026-08-06); lattice-stack retention measured in the PDE (2026-08-07); NS8–NS11 stacking-grounded protocols |
| `hypotheses/nuclear-magic-numbers.md` | Hypothesized | Fibonacci sub-channel closure at steps 80–95 |
| `hypotheses/hoyle-state-nucleosynthesis.md` | Hypothesized | Cascade rung resonance at the $^3\alpha$ threshold |
| `hypotheses/exoplanet-phi-spacing.md` | Hypothesized | Wake-wave interference in protoplanetary disks |
| `hypotheses/neural-criticality.md` | Hypothesized | Cascade PDE at neural scales |
| `hypotheses/muscle-cascade-lattice.md` | Hypothesized | Muscle ladder as bubble lattice (rungs 142–168) |
| `hypotheses/two-strand-five-channel-matter-organization.md` | Hypothesized—August 2026 (trace-graph algebra Derived; PDE gate suite Tested: TS1–TS4 null at lock timescale, TS5 5-fold coincident projection passed, TS6 twist persistence/no generation, TS7 two-sector bound; binding/interlace/matter-scale roles Open) | One condensate, two strands, five channel traces; SO(2)/five-sector/P_parallel clocks; Z2×Z5 trace graph; first probe: separation persisted (characterization only), near-in-phase Δθ, NS4 morphology null, traces Wood/Fire-limited; TS6 twist probe: half-twist persisted (Tw 0.500→0.499), zero-twist arm null; TS1–TS5 lock suite (t=40): pair escapes (d 9.90→15.73), d→0 limit not recovered, mode not centerline-fixed, central q above flank q, 5-fold coincident joint projection realized |
| `demystifying-the-cosmos/PSR-J1101-6101.md` | Hypothesized—August 2026 | Lighthouse pulsar: wake-pair trail/filament, high PD as high $q$, radio ⊥ vs X-ray ∥ as rung stratification; prediction 48 (log-periodic PA) |
| `demystifying-the-cosmos/NGC-5128.md` | Hypothesized—August 2026 | Centaurus A: parallelogram dust band as projected lattice trace (cascade r-field), S-shape as wake wrap, merger as anti-phase meeting; tests: φ-spaced wake rings (pred. 44), 1.70× edge anisotropy (pred. 38) |

## 5. Speculative

| Document | Status | Summary |
|----------|--------|---------|
| `analyses/gwtc4-mass-ladder.md` | Speculative—August 2026 | GWTC-4.0 peaks mapped to rungs; integer-rung test; ringdown null |
| `hypotheses/quasicrystal-stability.md` | Speculative | De-resonance against crystallization |
| `consciousness/cascade-consciousness.md` | Speculative | Medium-dependent perception; cascade nervous system |
| `consciousness/auras-as-thermalized-gates.md` | Speculative | Aura as the $(1-q)$ thermalization boundary layer; heat-haze optics |
| `consciousness/time-memory-and-wake-locks.md` | Speculative | Arrow of time from conversion; ghosts as wake-locks |
| `consciousness/transhumanism-gate-configurations.md` | Speculative | Augmentation as gate-chain topology surgery; identity as the run |
| `consciousness/gender-as-qi-configuration.md` | Speculative | Identity as configuration; anatomy as readout; dysphoria as self-prediction failure |
| `consciousness/neurodivergence-as-gate-configuration.md` | Speculative—August 2026 (drive-mechanism layer PDE-tested 2026-08-04) | Autism/ADHD as gate configurations; readout and loop variants; wake-pileup overload; churning-gate attention |
| `speculations/dark-matter-as-qi-coherence.md` | Speculative | Halos as unharvested coherence; bubble edge at $n \approx 267$ |
| `speculations/superconductivity-as-qi-coherence.md` | Speculative | Resistance as Yang→Yin conversion; Qi-gap |
| `speculations/qi-computation.md` | Speculative | Qi gate as computational primitive; Wu Xing logic |
| `speculations/qi-bubble-propulsion.md` | Speculative | Rung-shifting as a travel mechanism |
| `speculations/cascade-infrastructure.md` | Speculative | Planetary and stellar gate networks |
| `speculations/observational-seti.md` | Speculative | Structural (non-emissive) SETI signatures |
| `speculations/gravity-control.md` | Speculative | $G_{\text{eff}}$ as an engineering dial; Qi condenser devices |
| `hypotheses/periodic-table-madelung.md` | Speculative | $n$ and $l$ as cascade coordinates |
| `hypotheses/atmospheric-climate-cascade.md` | Speculative | $\varphi$-break in the atmospheric energy spectrum |
| `hypotheses/fatigue-fracture-cascade.md` | Speculative | $\sigma$-regularized crack tip; Paris law |
| `hypotheses/market-cascade-cycles.md` | Speculative | Wake-wave in information propagation networks |
| `hypotheses/metabolic-scaling.md` | Speculative (derivation not closed) | $\varphi$-derived fractal dimension for resource networks |
| `hypotheses/riemann-hypothesis-de-resonance.md` | Speculative—August 2026 | RH as no-resonance in primes; ζ-zero φ-test null |
| `hypotheses/riemann-two-fluid-spectral-program.md` | Speculative—August 2026 | Scale-operator candidate; minimal-fluctuation probes |
| `hypotheses/riemann-two-fluid-phase-operator.md` | Speculative—August 2026 | Step 1 done: Bessel scale operator; linear spectra fail R-vM; Γ-phase boundary identified |

## 6. Creative Extensions (speculations/creative-extensions/)

Just-for-fun applications of the framework's logic; exempt from the evidential tier system by design.

| Document | Status | Summary |
|----------|--------|---------|
| `speculations/creative-extensions/coherence-warfare.md` | Creative | Coherence budget as weapons table; φ-detuned shields; mutual assured incoherence |
| `speculations/creative-extensions/universal-biology.md` | Creative | Cascade ladder as convergent evolutionary scaffold |
| `speculations/creative-extensions/magic-systems.md` | Creative | Magic as phase-matched field operation |
| `speculations/creative-extensions/coherence-commons.md` | Creative | Two-fluid theory of value; equality theorem; the transition to the commons |
| `speculations/creative-extensions/coherence-collapse.md` | Creative | Attractor self-healing; civilization death modes |
| `speculations/creative-extensions/first-contact-and-stellar-engineering.md` | Creative | $\ln\varphi$ protocol; stars as gate chains |
| `speculations/creative-extensions/simulation-hypothesis.md` | Creative | Two-fluid PDE as source code; nested universes |

## 7. Reference & Cross-Cutting

Documents that are not claims: registries, catalogs, explainers, and plans.

| Document | Role |
|----------|------|
| `open-questions-cassi-answers.md` | Epistemic registry (42 questions, tier authority) |
| `parameter-inventory.md` | Parameter registry (~46 parameters) |
| `predictions/falsifiable-predictions.md` | 50-prediction catalog |
| `predictions/cassi_definitions.md` | Framework glossary |
| `foundations/cassi-theory-reference.md` | Compact framework reference |
| `foundations/deriving-remaining-gaps.md` | Four gap assessments—one narrowed, one open, one identified, one empirical |
| `particles/matter-organization.md` | Synthesis (claims keep source tiers)—forces on the cascade, lattice pools, n/p/e trio |
| `cosmology/sigma8-computational-plan.md` | Plan (Hypothesized; doctrine 2026-08-07: reading P-A operative, IC $r_0 = 0.0472$; the truth campaign's measured rows: mechanism +29.7%, total −20.5% (doctrine-IC, resolution-converged); the settlement rows −16.6%/−15.2%; the "~5%" target Mapped) |
| `audit.md` | Self-critical prediction-vs-experiment audit |
| `cassi-physics.md` | Physics guide: lattice, cascade, predictions |
| `cassi-psychology.md` | Psychology-focused guide (consciousness, emotion, trauma, therapy) |
| `analyses/README.md` | Analysis index (data analyses against the framework) |
| `demystifying-the-cosmos/README.md` | Demystifying index (one doc per observed object, codename-named) |
| `demystifying-the-cosmos/unsolved-problems-in-astronomy.md` | Unsolved-problems survey: Wikipedia list → framework stances + series roadmap |
| `hypotheses/README.md` | Hypothesis catalog + quality bar |
| `speculations/README.md` | Speculation index + boundary with `hypotheses/` |

Repo meta-docs (`README.md`, `AGENTS.md`, `BROKEN_REFS.md`) are not claims and are not indexed.

Theory code (PDE solvers, pipelines, experiments, visual explainers) lives in `experiments/`, `two-fluid/`, `computations/`, and `visual-explainers/`; each script is cited from the paper that uses it.

## References

- `open-questions-cassi-answers.md`—epistemic registry (tier authority)
- `hypotheses/README.md`—quality bar and tier definitions
- `audit.md`—known tensions and past errors
- `predictions/falsifiable-predictions.md`—the prediction catalog
