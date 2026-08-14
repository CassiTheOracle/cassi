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
| `foundations/cassi-first-principles.md` | Derived PDE and Qi definition; Asserted single-channel gate input | Two-fluid PDE in the density fields $E_Y = \Psi_0^2$, $E_I = \Psi_1^2$; Qi coherence; conversion openness and gate-status audit; winding rate $d\theta/dt = \lambda(1-q)\rho\varepsilon/(E_Y^2+E_I^2)$ solver-measured (§2.6, `two-fluid/run_winding_rate_probe.py`), exact relaxation winding bounded $|\delta n| \le 0.162$ rungs; the density-plane angle $\theta = \mathrm{atan2}(E_I, E_Y)$ reconciles the density-field convention with the amplitude-plane doublet phase |
| `foundations/unified-lagrangian.md` | Derived | Single Lagrangian; gravity as $q = 0$ Poisson limit; $\sigma$-regularization |
| `foundations/phi_attractor_synthesis.md` | Derived (attractor synthesis) / Calibrated ($\xi$ pin) / Mapped ($\alpha_{\text{halo}} = 0.7$ nominal—ledger) | $r \to \varphi$ attractor synthesis across regimes |
| `foundations/wu-xing-derivation.md` | Derived (w = 5, gap, r₀; single input: coherence postulate—verified 2026-08-11) / Calibrated (w₀ via the DESI-anchored coupling form—ledger) | $w = 5$ derived (coherence criterion over all $w$: only $\{1,2,3,5\}$; pentagon geometry); $\lambda = 1/(2w) = 0.1$ (`cassi-physics.md`) |
| `foundations/wu-xing-cycle-structure.md` | Derived (cycle geometry, coupling, ring algebra) / Tested (ke ring PDE 2026-07-31, WX1 gate level 2026-08-01) / Hypothesized (affinity gradient, clinical profile) | Two coherent 5-cycles (sheng/ke); control-ring algebra; 5↔13 chakra partition |
| `foundations/xi-derivation.md` | Derived conditional on the quadratic-coupling input (imbalance inverse-square) / Calibrated empirical pin (MW anchor—ledger) | $\xi = \varphi^6 = (\pi/\rho)^{-2}$; saturation ceiling $\varphi^3 G$ |
| `foundations/quark-confinement.md` | Derived (tube extensivity + cell quantization; $\kappa = 2\pi$ conditional on the pitch convention + winding reading; inputs: gate saturation, one-cell quantization) | QCD at step 95; saturated-gate flux tube $E(r) = \mu r$, $\mu = 2\pi(M_{\text{Pl}}/\varphi^{95})^2 = 0.1836$ GeV² (+2.0% vs measured); $P_{\text{break}} \approx \varphi^{-4506}$ |
| `foundations/proton-coherence-budget.md` | Derivation (rung exponent Mapped—ledger; per-rung $q_i$ profile Hypothesized) | Proton lifetime $\sim \varphi^{4506}$ cycles; annihilation pathway |
| `foundations/sector-coupling-derivation.md` | Derived conditional on $\delta = 3$ (rung identity $77 = 154/2 = 80-3$) with Hypothesized coefficient (v₀ input Calibrated, N_pde normalization Mapped—ledger) | Dirac↔two-fluid sector-coupling scale $\kappa_s = \varphi^{-6}/v_0^2 = M_{\text{Pl}}^{-2}\varphi^{154}$ (0.92 TeV$^{-2}$; $\kappa_s^{-1/2} \approx 1.04$ TeV) |
| `foundations/bubble-edge-geometry.md` | Derived geometry and threshold relation conditional on asserted gate | Edge steepness $1.70\times$ (Derived); threshold relation conditional on $g(q)$; CMB axis $12.2°$ (magnitude $2\pi/\varphi^7 = 12.40°$ Derived; direction Calibrated; boundary mechanism Hypothesized, orientation fitted to measured axis); radial ring ladder §3 (matter rings $r_k = \ell_n\varphi^{-k}$, voids at $\varphi^{-(k+\frac12)}$, ~10 rings from $N = \ln100/\ln\varphi = 9.570$, cascade connection REDUCES) **Derived conditional**, with the radial-reading inference flagged |
| `foundations/wa-pentagon-gate.md` | Derived ($\xi = \varphi^6$) / Hypothesized (5-channel) | $w_a = +0.012$ via $\xi$: $2.7\sigma$ baseline; with the ratified coupling $1.25\sigma$ (B2, unstable); the stable realization (10/12): pure-Λ window fit $(-1, 0)$, $4.17\sigma$/$2.61\sigma$; 5-channel shift Hypothesized (ODE pending) |
| `principles/de-resonance-principle.md` | Derived | Why $\varphi$ is the attractor (maximally irrational) |
| `principles/v0-hierarchy-problem.md` | Derived (step count, per registry Q1); 5.3% residual open | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ as step count (Q1) |
| `standard-model/sm-from-phi.md` | Derived chain/algebra; Weinberg boundary asserted | Gauge-chain truncation, $\sin^2\theta_W = \varphi^{-3}$ boundary, Yukawa and CKM sector |
| `standard-model/sm-radiative-corrections.md` | Derived | Loop corrections from the φ-boundary: RGE, Δα, Δr → m_W, λ running; residuals ($\alpha_s$ $2\times$, $\alpha_1$/$\alpha_2$ ~25%) open |
| `standard-model/su2-gauge-extension.md` | Derived gauge algebra/mass matrix; coupling boundary asserted | SU(2) gauge extension, neutral mass matrix, curvature–orbit closure audit |
| `standard-model/cp-violation.md` | Derived (δ_CKM Mapped—ledger; Jarlskog invariant not reproduced) | CKM phase $\pi\varphi^{-2}$ |
| `particles/cassi-yang-yin-particles.md` | Derived | Particles as standing-wave interference; atomic $Z = 1$–$10$ |
| `particles/dft-benchmarks.md` | Derived | DFT benchmark comparisons |
| `cosmology/cosmology-from-phi.md` | Derived formation/structure / Hypothesized baryogenesis / Mapped $\eta$ / conditional DM base / Calibrated $w_0$ form | $w_0=-0.87$ baseline; $\eta$ exponent and DM ratio tension remain open |
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
| `foundations/quantum-measurement-derivation.md` | Derivation (Born rule Derived from coherent-field statistics; outcome basis open; $\mathcal{M}$ Hypothesized, Q7) | Born rule from Poisson first-absorption; phase-matching factor $\mathcal{M}$ |
| `foundations/spin-fibonacci-spiral.md` | Derivation (Derived conditional on the doublet postulate + pitch convention + equilibrium ratio + minimal-span principle; particle mapping Hypothesized, Q10) | Spin from the Yang/Yin doublet half-angle ($s = \Delta n/2$, minimal span $\Delta n = 1$ → $s = 1/2$; no fundamental 3/2—decomposition); $P_\parallel = 2$ unified convention; form-factor periodicity |
| `foundations/baryon-asymmetry.md` | Hypothesized mechanism / Mapped $\eta$ exponent; freeze-out endpoint open | $\eta \approx \varphi^{-44}$, within 6% numerically; rate-based $\Gamma/H=1$ test yields no post-seed freeze-out |
| `foundations/refined-numeric-predictions.md` | Active derivation (C10 magnitude Derived / direction Calibrated / boundary Hypothesized—ecliptic-degeneracy audit) | Numeric predictions for the 19 Hypothesized questions; C10 $12.2°$ magnitude closure, data-calibrated direction, and unselected boundary projection |
| `foundations/three-generations.md` | Hypothesized (mechanism) / Derived (2+1 counting under the propagation-channel postulate) / Mapped (rung placements—ledger) | $N_{\text{gen}} = 3 = 2$ predecessor channels + 1 direct rung (Q5) |
| `foundations/dimensionful-constants-status.md` | Hypothesized ($c$, $\hbar$, $G$ external) / Mapped (fitted exponents—ledger) | $c$, $\hbar$, $G$ external; $N = 292$ epoch-dependent horizon rung (F5) |
| `foundations/microcascade-mirror.md` | Hypothesized | Bidirectional cascade extension |
| `foundations/rung-offset-mechanism.md` | Derived quantization, Hypothesized selection, Empirical catalog (μ/Jψ placements Mapped—38-state scan, ledger) | δn as two-fluid phase lag (analytic $A_0$, $B_0$); pool-cell mode quantization; sector edges at half-rungs; uniform 38-state baseline; §7 winding bound $|\delta n| \le 0.162$ rungs splits relaxation winding from parity offsets |
| `foundations/phi-rg-formalism.md` | Hypothesized | RG flow under $\varphi$-spacing |
| `foundations/spiral-dynamics.md` | Hypothesized | Hubble, gravity, $c$ as spiral geometry projections |
| `foundations/why-three-dimensions.md` | Hypothesis with One Decided Fork (W1: anti-phase confirmed) | Three dimensions from the Frenet-Serret frame (G5); d = 3 supported conditionally on the three postulates (2026-08) |
| `foundations/qi-flow-double-helix.md` | Derived (Qi as phase current; axial inter-scale flow; $P_\parallel = 2$ cycle) / Hypothesized (double-helix identification) | Yin–Yang–Qi triad; $J = \rho\nabla\theta$; $J_z$ as inter-scale flow; double helix as axial phase winding (lattice-stack record), not transverse filaments (TS1–TS4) |
| `standard-model/gut-embedding.md` | Hypothesized | GUT embedding |
| `standard-model/neutrino-mass.md` | Hypothesized | Neutrino mass structure |
| `gravity/quantum-gravity.md` | Derived conditional on the noise–signal identification + $d = 3$ ($\sigma = \ell_{\text{Pl}}/\varphi^3$, G1) / Hypothesized (two-fluid quantization, G2) | $\sigma$-regularized S-matrix; $\delta = 3$ from the Planck-core noise–signal crossover; black-hole information (G2) |
| `cosmology/inflation-from-cascade.md` | Derivation (mechanism Hypothesized, C4; r exponent Mapped—ledger) | Steps 20–60 as inflation; $r = 12/N_e^2 = 0.0075$ (Mapped window $N_e = 40$), $n_s$ |
| `cosmology/desi-lattice-averaging.md` | Hypothesized | Lattice powder lines in $P(k)$; variance suppression; $D_A(z)$ wiggle bound |
| `consciousness/chakras-as-cascade-bubbles.md` | Hypothesized | 13 chakras as cascade bubbles |
| `consciousness/consciousness-from-phi.md` | Plausible Hypothesis with Actionable PDE Test | Consciousness as Qi-gate dynamics; two-bubble test (M1) |
| `consciousness/emotions-as-gate-configurations.md` | Hypothesized | Emotions as gate configurations |
| `consciousness/trauma-as-frozen-gate.md` | Tested—null pinning, drive effect supported (2026-07-31) / Speculative (clinical) | Trauma as a frozen Qi gate |
| `consciousness/two-strand-qi-neuroscience.md` | Hypothesized (strand geometry) / Speculative (neural mapping) | Two-strand Qi condensate; centerline/separation decomposition; strand modes; NS1–NS4 PDE statuses (lock-timescale nulls, 2026-08-06); lattice-stack retention measured in the PDE (2026-08-07); NS8–NS11 stacking-grounded protocols |
| `hypotheses/nuclear-magic-numbers.md` | Hypothesized | Fibonacci sub-channel closure at steps 80–95 |
| `hypotheses/hoyle-state-nucleosynthesis.md` | Hypothesized | Cascade rung resonance at the $^3\alpha$ threshold |
| `hypotheses/exoplanet-phi-spacing.md` | Hypothesized | Disk mechanism = the bubble-shell ring ladder ($r_k = R\varphi^{-k}$, Derived conditional); DSHARP gap-ratio test SUPPORTS at 3.86$\sigma$ (Prediction 53); period-ratio prediction $\varphi^{3/2}$ unchanged; channel reading: disk gas is the coherence-coupled channel (carries the spacing), the orbital/matter channel is where the signal is not expected (Prediction 54) |
| `foundations/qi-as-spatial-spacing-signal.md` | Derived conditional (phase/coherence structure) / Hypothesized (channel-transmission claim) | Qi is the spatial-spacing signal: coherence ripples differently than it moves; the condensation clumping is the lattice (φ-clump spacing: measured single-mode null, sim—no φ-ladder in the sim's free dynamics; radial-only k-shell, per-axis unrun); the ring ladder is a phase ladder; matter carries the spacing only through coherence-coupled channels (gas/condensate), not gravity-dominated matter channels (orbital dynamics)—resolving P53 SUPPORTS (coherence channel) vs P54 INDETERMINATE (matter channel) as consistent |
| `hypotheses/neural-criticality.md` | Hypothesized | Cascade PDE at neural scales |
| `hypotheses/muscle-cascade-lattice.md` | Hypothesized | Muscle ladder as bubble lattice (rungs 142–168) |
| `hypotheses/two-strand-five-channel-matter-organization.md` | Hypothesized—August 2026 (trace-graph algebra Derived; PDE gate suite Tested: TS1–TS4 null at lock timescale, TS5 5-fold coincident projection passed, TS6 twist persistence/no generation, TS7 two-sector bound; binding/interlace/matter-scale roles Open) | One condensate, two strands, five channel traces; SO(2)/five-sector/P_parallel clocks; Z2×Z5 trace graph; first probe: separation persisted (characterization only), near-in-phase Δθ, NS4 morphology null, traces Wood/Fire-limited; TS6 twist probe: half-twist persisted (Tw 0.500→0.499), zero-twist arm null; TS1–TS5 lock suite (t=40): pair escapes (d 9.90→15.73), d→0 limit not recovered, mode not centerline-fixed, central q above flank q, 5-fold co… |
| `hypotheses/gravity-from-flow.md` | Hypothesized—August 2026 | The river law: gravity as the gradient of the flow-modulated chord $G_{\text{eff}} = G(\pi/\rho)(1+(\varphi^{6}-1)qf)$; sign question resolved ($\Pi\nabla\Phi$ sign-following; point-particle attraction is the $-[1+(\varphi^{6}-1)q]$ convention); object $C = -\nabla\cdot J$ confirmed with the linear response $dU/U = -36.05\kappa$ (magnitude falsified 192×; $\kappa$ unfitted); surge form undetermined; boundary measured $\lambda_{\text{gate}} = 0.0224$ ($\lambda/4$ rejected); C2 open (interior instability); P3 parity-odd channel LIVE at $\chi = \varphi^{-1}$ ($\chi$ asserted); P4 rung-sum inconclusive (reduction confirmed) |
| `speculations/qi-computation.md` | Hypothesized (information budget) / Speculative (gate set, Wu Xing logic, cascade clock, brain mapping) | Stored information $I = k_B q\ln\varphi$ as the entropy deficit (coherence IS information); per-rung quantum $\log_2\varphi \approx 0.694$ bits; Landauer row $\Delta q = \ln2/\ln\varphi \approx 1.44$; gate set and Wu Xing logic remain extrapolations |
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
| `predictions/falsifiable-predictions.md` | 54-prediction catalog |
| `predictions/cassi_definitions.md` | Framework glossary |
| `foundations/cassi-theory-reference.md` | Compact framework reference |
| `foundations/deriving-remaining-gaps.md` | Four gap assessments—one narrowed, one open, one identified, one empirical |
| `particles/matter-organization.md` | Synthesis (claims keep source tiers)—forces on the cascade, lattice pools, n/p/e trio |
| `cosmology/sigma8-computational-plan.md` | Plan (Hypothesized; doctrine 2026-08-07: reading P-A operative, IC $r_0 = 0.0472$; the truth campaign's measured rows: mechanism +29.7% (D-insensitive), total −20.5% (D=0.001 campaign) / −22.9% (D=0 doctrine default, brief 63 — the totals carry the diffusion) (doctrine-IC, resolution-converged); the settlement rows −16.6%/−15.2%; the "~5%" target Mapped) |
| `audit.md` | Self-critical prediction-vs-experiment audit |
| `cassi-physics.md` | Physics guide: lattice, cascade, predictions |
| `UNIFICATION.md` | Plan (speculative architecture; grounded present-state map) | Cross-repo unification proposal: the field as the shared substrate across CassiCore, Cassi AI, the theory, and the space-sim |
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
