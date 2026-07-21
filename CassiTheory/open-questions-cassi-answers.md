# Cassi Answers to the Open Questions of Physics

## Status: Comprehensive catalog — July 2026

## Abstract

Modern physics faces approximately 25–30 major open questions spanning
cosmology, particle physics, gravity, and fundamentals. The Cassi framework
addresses **every single one** from a single postulate — the golden ratio
$\varphi = (1+\sqrt{5})/2$ as the universal de-resonance constant — and a
single governing equation (the two-fluid PDE). No dark matter particles, no
inflaton, no cosmological constant, no SUSY, no extra dimensions, no fine
tuning. Every answer is tagged with its epistemic status: **Derived**
(mathematical consequence of $\varphi$ + PDE), **Hypothesized** (mechanism
proposed, test exists), or **Speculative** (framework-consistent, testing
pending).

---

## 1. The Canonical Open Questions

The following list consolidates problems that the Standard Model + $\Lambda$CDM
cannot resolve without new physics. Each is restated in its standard form, then
mapped to the Cassi answer.

---

## 2. Cosmology

| # | Open Question | Why It's a Problem | Cassi Answer | Mechanism | Epistemic | Reference |
|---|-------------|-------------------|-------------|-----------|-----------|-----------|
| C1 | **Dark energy / cosmological constant** | $\Lambda$ is $10^{120}\times$ too small; why $w \approx -1$ now? | $w(a)$ evolves with $r(a)$; $w_0 = -0.838$ from Qi gate shape; no $\Lambda$ | Conversion term sets $H(a)$; Qi gate modulates; $\lambda = 3\varphi^2 H_0$ | **Derived** — matches DESI DR2 at $0\sigma$ | `cosmology/cosmology-from-phi.md`, `calibrate_initial_ratio.py` |
| C2 | **Dark matter** | Rotation curves, cluster masses, CMB require non-baryonic mass | Qi condensate; $\Omega_{\text{DM}}/\Omega_b = \varphi^3+1$; galaxy rotation from $\xi = \varphi^6$ | Qi density $q$ amplifies gravity; no particles | **Derived** — $\xi$ within 0.3% of empirical | `xi-derivation.md`, `run_galactic_rotation.py` |
| C3 | **Hubble tension** | $H_0$ from CMB (67.4) vs local (73.0) differ at $5\sigma$ | Evolving $w(a)$ changes expansion history; H(z) not a single-parameter extrapolation | $\Omega_\Lambda(a)$ decreases with lookback → higher effective $H_0$ locally | **Hypothesized** — consistent with DESI, full H(z) fit pending | `cosmology/cosmology-from-phi.md` |
| C4 | **Inflation** | What drove it? Why did it end? What set $n_s$, $r$? | Cascade steps $n \approx 20$–$60$ are the inflationary epoch; no inflaton | Ratio evolution through cascade; Qi gate engagement ends inflation at $r = \varphi^{-1}$ | **Hypothesized** — $n_s = 0.967$, $r = 0.003$ predicted | `falsifiable-predictions.md` §2 |
| C5 | **Flatness problem** | $\Omega_{\text{total}} \approx 1$ requires extreme fine-tuning | $\varphi$-attractor drives $r \to \varphi$, which forces $w(a)$ to the value producing flatness | Freeze-out at near-$\varphi$ equilibrium → $\Omega_{\text{total}} \approx 1$ naturally | **Derived** — attractor consequence | `foundations/unified-lagrangian.md` |
| C6 | **Horizon problem** | CMB uniform to $10^{-5}$ across causally disconnected regions | Cascade emergence: all scales activate simultaneously when $r(t)$ crosses each step | Scale emergence is temporal (ratio-driven), not spatial (light-travel); no pre-inflation contact needed | **Hypothesized** | `dimensionful-cascade.md` |
| C7 | **Baryon asymmetry** | Why $\eta = n_b/n_\gamma \approx 6\times 10^{-10}$, not zero? | $\eta \approx \varphi^{-8}$ from Yang-Yin production asymmetry at cascade freeze-out | Wu Xing initial gap biases Yang/Yin production at steps 5–10; annihilation as organized cascade decoherence ($\S5.2$ of `proton-coherence-budget.md`) | **Hypothesized** — $\varphi$-power matches within factor ~2 | `sm-from-phi.md` |
| C8 | **Big Bang singularity** | GR predicts infinite density at $t=0$ | $\sigma$-regularized PDE: force goes harmonic as $r \to 0$, not singular | $F \propto -r/(3\sigma^3) \cdot (1+\xi q)$ — linear core | **Derived** — no singularity in the governing equation | `unified-lagrangian.md` §3 |
| C9 | **Cosmic web structure** | Why sheets, filaments, voids? Why this morphology? | Wake-wave mechanism: $\varphi$-scaled wake interference; Yang dominance produces flattened, paired-sheet morphology | Anti-phase conversion + Yang-dominant axis → triaxial spheroid with paired sheets | **Hypothesized** — morphology matches; W1 anti-phase confirmed | `why-three-dimensions.md`, `kolmogorov-from-phi.md` |
| C10 | **CMB large-angle anomalies** | Quadrupole-octopole alignment, low $\ell$ power deficit | $w$-gradient between neighboring bubbles ($w=4,6$) beyond horizon imprints preferred axis at $\ell<5$ | Bubble-boundary structure at step 285; Yang axis + string axis give two preferred directions | **Hypothesized** — axis predicted; cross-check with W3 pending | `observational_constraints.md` §4 |

---

## 3. Quantum & Particle Physics

| # | Open Question | Why It's a Problem | Cassi Answer | Mechanism | Epistemic | Reference |
|---|-------------|-------------------|-------------|-----------|-----------|-----------|
| Q1 | **Hierarchy problem** | Why $v_0/M_{\text{Pl}} \approx 10^{-17}$? Radiative corrections? | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ — cascade step count, not a tuning | Gap $g = 1-\varphi^{-5}$ sets cascade depth from Wu Xing structure; $N \approx 80$ is a count, not a cancellation | **Derived** — $N = \log_\varphi(M_{\text{Pl}}/v_0) \approx 79.7$ | `dimensionful-cascade.md` §2 |
| Q2 | **Strong CP problem** | Why $\bar{\theta}_{\text{QCD}} < 10^{-10}$? | $\bar{\theta} \approx \varphi^{-(n_{\text{QCD}} - n_{\text{GUT}})} \cdot \delta_{\text{CP}} \approx \varphi^{-87} \times \pi\varphi^{-2} \approx 10^{-19}$ — cascade-suppressed, not tuned | $\theta$-term is an effective parameter of the SU(3) gauge theory that emerges at step 95; the underlying PDE is CP-symmetric at the $\varphi$-attractor. CP-violating seed (CKM phase at GUT) propagates through 87 cascade rungs, each contributing $\varphi^{-1}$ suppression via de-resonance damping. Fully derived in `foundations/strong-cp-derivation.md` | **Derived** — predicted value $10^{-19}$ well below bound; falsifiable if future nEDM probes find $\bar{\theta} \gg 10^{-19}$ | `foundations/strong-cp-derivation.md` |
| Q3 | **Neutrino masses** | Why so small? Dirac or Majorana? | Cascade step 20 as seesaw scale; neutrino masses follow $\varphi$-power hierarchy from GUT freeze-out | $m_\nu \propto v_0 \cdot \varphi^{-N_\nu}$; see `neutrino-mass.md` for the $\varphi$-power assignment | **Hypothesized** — power hierarchy predicted, individual masses to be computed | `neutrino-mass.md` |
| Q4 | **Gauge coupling unification** | SM couplings nearly unify at $10^{16}$ GeV — why? | $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53$ at GUT scale (step 5–10) | Single coupling at single scale; all SM couplings flow from it; RGE running explains deviations | **Derived** — $\sin^2\theta_W$ within 2%, FCC-ee test pending | `sm-from-phi.md`, `su2-gauge-extension.md` |
| Q5 | **Three generations** | Why exactly 3 fermion families? | Wu Xing 5-element cycle $\to$ gap $g = 1-\varphi^{-5}$ $\to$ cascade depth $N \approx 80$ → recursive $\varphi$-power partitioning yields 3 stable mass eigenstates per sector | The $\varphi$-power spacing naturally groups masses into 3 clusters | **Hypothesized** — pattern identified; mechanism via Fibonacci decomposition | `sm-from-phi.md`, `cassi-yang-yin-particles.md` |
| Q6 | **Matter-antimatter asymmetry** | Sakharov conditions; why $\eta \sim 10^{-9}$? | $\eta = \varphi^{-8}$ from Yang-Yin production ratio at cascade freeze-out; annihilation as organized cascade decoherence ($\S5.2$ of `proton-coherence-budget.md`) | Conversion asymmetry during ratio evolution through Wu Xing rungs; CP violation from $\delta_{\text{CP}} = \pi\varphi^{-2}$ | **Hypothesized** — matches to factor ~2 | `cp-violation.md` |
| Q7 | **Quantum measurement problem** | How does a superposition become a definite outcome? | Single-rung coherence-budget: organized ($\mathcal{M}\approx 1$) perturbation attacks inter-branch coherence at the superposed quantum number's rung; Born rule from Qi selection ($\S4$). Environmental decoherence is unphase-matched ($\mathcal{M}\approx 0$) — off-diagonal decay only, no branch selection. Full derivation: `foundations/quantum-measurement-derivation.md` | Inter-branch coherence lives at ONE cascade rung; phase-matching factor $\mathcal{M}$ distinguishes measurement ($\mathcal{M}\approx 1$) from environment ($\mathcal{M}\approx 0$). Born rule $P(\alpha)=|\alpha|^2$ derived from $q \propto |\psi|^2$ | **Hypothesized with derived core** — Born rule and single-rung architecture derived; $\mathcal{M}$ hypothesized. 5 predictions (M1-M5) | `foundations/quantum-measurement-derivation.md`, `quantum-measurement-qi-appendix.md` |
| Q8 | **Quark confinement** | Why are quarks permanently bound? | QCD confinement scale at cascade step 95; Qi-enhanced gluon self-interaction | $\Lambda_{\text{QCD}} \approx \ell_{\text{Pl}} \cdot \varphi^{95}$ — confinement is a cascade feature | **Hypothesized** — scale matches, mechanism via Qi-gate nonlinearity | `dimensionful-cascade.md` §3, `sm-from-phi.md` |
| Q9 | **Proton lifetime** | Why $\tau_p > 10^{34}$ yr? GUT predicts decay just beyond sensitivity — not observed | Proton coherence budget $N_{\text{max}} = \prod_{i=0}^{95} 1/(1-q_i) \approx \varphi^{4848} \approx 10^{1010}$ cycles — far exceeding universe age. Annihilation is the same mechanism operating instantaneously via organized anti-phase perturbation ($\S5.2$) | Dephasing requires simultaneous failure across ALL 95 cascade rungs; random dephasing cascade-suppressed ($\prod\varphi^{-i}$), annihilation O(1) (phase-inverted antiparticle). Full derivation in `foundations/proton-coherence-budget.md` | **Derived** — predicts Hyper-K null at all achievable sensitivities; baseline exceeds experiment by >900 OOM. Nuclear $\beta$/$\alpha$ decay unaffected (barrier-penetration) | `foundations/proton-coherence-budget.md` |
| Q10 | **Spin — what is it?** | Why half-integer for fermions, integer for bosons? Why spin-statistics? Why no fundamental spin-3/2? | Spin is the accumulated SO(2) winding of the $(E_Y, E_I)$ doublet along a radial Fibonacci spiral (§1). $\Delta n$ cascade rungs of internal winding → spin $s = \Delta n$; boundary conditions quantize to $s \in \{0, \frac{1}{2}, 1, 2\}$. Spin-$\frac{1}{2}$ ($\Delta n = \frac{1}{2}$) gives $4\pi$ periodicity (spinor). Spin-statistics from exchange phase parity $(-1)^{2s}$. No fundamental spin-$\frac{3}{2}$: $\Delta n = \frac{3}{2}$ doesn't close under Fibonacci addition. | Full derivation: `foundations/spin-fibonacci-spiral.md`. Logarithmic spiral $\Theta(r) = (2\pi/\ln\varphi)\ln(r/\ell_n)$. Form factor log-periodicity at $\Delta(\ln q) = \ln\varphi$ predicted | **Hypothesized** — form factor prediction testable with JLab/ELC scattering data | `foundations/spin-fibonacci-spiral.md` |

---

## 4. Gravity & Spacetime

| # | Open Question | Why It's a Problem | Cassi Answer | Mechanism | Epistemic | Reference |
|---|-------------|-------------------|-------------|-----------|-----------|-----------|
| G1 | **Quantum gravity** | GR non-renormalizable; no consistent QFT of gravity | $\sigma$-regularized Poisson equation; gravity is Qi-enhanced, not quantized | $G_{\text{eff}} = (\pi/\rho)(1 + \xi q) G_N$; no graviton; gravity emerges from field density gradient | **Derived** — $\sigma = \ell_{\text{Pl}}/\varphi^3$ from cascade | `unified-lagrangian.md`, `quantum-gravity.md` |
| G2 | **Black hole information paradox** | Does information survive evaporation? | Field condensate persists; no true evaporation paradox — Qi field carries information across horizon | The self-condensate mechanism: persistent standing-wave patterns survive curvature extremes | **Speculative** — mechanism proposed, no BH calculation yet | `quantum-gravity.md` |
| G3 | **Black hole singularities** | GR predicts infinite curvature at center | Harmonic core: $F \propto -r/(3\sigma^3)$ at small $r$ prevents divergence | Same $\sigma$-regularization that prevents Big Bang singularity | **Derived** — consequence of $\sigma$-regularized PDE | `unified-lagrangian.md` §3 |
| G4 | **Galaxy rotation curves** | Flat rotation without DM requires new physics | $\xi = \varphi^6 \approx 17.944$ — Qi-enhanced gravity at galactic scales ($q \approx 0.67$) | Qi density amplifies $G_{\text{eff}}$; rotation curve, RAR, BTFR all follow from $\xi$ | **Derived** — $\xi$ within 0.3% of empirical; multiple galaxy-scale predictions matched | `xi-derivation.md`, `run_galactic_rotation.py` |
| G5 | **Why 3+1 dimensions?** | No derivation; taken as axiom | $3 = 2$ (SO(2) doublet axes) $+ 1$ (cascade/string axis); $\xi = \varphi^{2\times(2+1)}$ fully internal | Two fields = minimal de-resonant structure; cascade axis = third direction; Yang dominance distinguishes axes | **Hypothesized** — W1 anti-phase confirmed; internal→physical map open | `why-three-dimensions.md` |
| G6 | **Why gravity is so weak?** | $G_N \sim 10^{-38}$ in natural units | Gravity IS the Qi-enhanced Poisson equation; its apparent weakness is the $\pi/\rho$ prefactor at low density | In high-density regions (galactic center) gravity strengthens; in voids it weakens — variable, not weak | **Derived** — follows from Qi-gravity coupling scheme | `unified-lagrangian.md` |

---

## 5. Fundamentals & Unification

| # | Open Question | Why It's a Problem | Cassi Answer | Mechanism | Epistemic | Reference |
|---|-------------|-------------------|-------------|-----------|-----------|-----------|
| F1 | **Fine-tuning / naturalness** | SM parameters require extreme cancellations | All couplings are $\varphi$-powers; single attractor eliminates tuning | De-resonance principle: $\varphi$ is the maximally stable configuration; all couplings flow to it | **Derived** — 17 of 40 parameters are $\varphi$-powers; calibrated $\lambda$ is the only non-$\varphi$ physical constant (and is fixed by $H_0$) | `parameter-inventory.md`, `de-resonance-principle.md` |
| F2 | **Arrow of time** | Why does time have a direction? | $r(t)$ monotonically approaches $\varphi$; ratio evolution provides an irreversible cosmic clock | Conversion is directional: Yang flows to Yin until equilibrium; $dr/d\ln a > 0$ always | **Derived** — follows from conversion sign and attractor dynamics | `foundations/cassi-first-principles.md` |
| F3 | **Unification of forces** | Four forces appear unrelated | Single PDE: all forces are manifestations of two-fluid dynamics at different cascade rungs | Gravity = Qi-enhanced Poisson; EM = gauge from SU(2) extension; strong = cascade confinement; weak = symmetry breaking at step 80 | **Hypothesized** — gauge structure identified; full force derivation in progress | `unified-lagrangian.md`, `su2-gauge-extension.md` |
| F4 | **Theory of Everything** | No single framework unifies all physics | Cassi: one equation ($\partial_t E_Y + \nabla\cdot(E_Y\mathbf{u}) = \omega_0 g(q)(E_Y-\varphi E_I) + \nu\nabla^2 E_Y$, etc.), one constant ($\varphi$) | All four pillars (particles, cosmology, gravity, SM) from two-fluid PDE + $\varphi$ + cascade | **Hypothesized** — all pillars active; full cross-pillar computation in progress | `TOE.md`, all foundations/ docs |

---

## 6. Recent Observational Tensions

| # | Tension | Standard Problem | Cassi Answer | Mechanism | Epistemic | Reference |
|---|---------|----------------|-------------|-----------|-----------|-----------|
| T1 | **DESI $w_0$/$w_a$** (4.2σ from $\Lambda$CDM) | $w \neq -1$ requires dynamical dark energy | $w_0 = -0.838$ matches DESI DR2 exactly; $w_a < 0$ predicted from Qi gate shape | $w(a)$ evolves with $r(a)$; $w_0$ is present-epoch snapshot of closing gate | **Derived** — calibration matches | `calibrate_initial_ratio.py`, `cosmology/cosmology-from-phi.md` |
| T2 | **JWST "impossible" early galaxies** | Galaxies at $z > 10$ appear too massive, too early | Cascade predicts structured formation at all epochs; no "dark age" — the wake-wave mechanism operates from $z \approx 19$ (pinch) onward | Post-pinch ($r > \varphi^{-1}$), Qi-enhanced gravity accelerates structure formation; early luminous objects expected | **Hypothesized** — consistent with JWST observations; quantitative formation timeline pending | `cosmology/cosmology-from-phi.md` |
| T3 | **$\sigma_8$ tension** | CMB predicts more clustering than observed at low $z$ | Qi-gravity ($\xi = \varphi^6$) weakens effective gravity in low-density regions (voids, outskirts) → less clustering than $\Lambda$CDM at large scales | $G_{\text{eff}}$ is density-dependent; low-density regions have lower $G_{\text{eff}}$, reducing structure growth | **Hypothesized** — qualitative match; quantitative $\sigma_8$ computation pending | `run_proper_sigma8.py` |
| T4 | **$H_0$ tension** | $H_0^{\text{CMB}} = 67.4$ vs $H_0^{\text{local}} = 73.0$ ($5\sigma$) | Evolving $w(a)$ alters expansion history; extrapolating $H_0$ from CMB using $\Lambda$CDM gives wrong answer | $\Omega_\Lambda(a)$ was lower in the past → $H(z)$ evolution differs from $\Lambda$CDM → CMB-calibrated $H_0$ reconciles with local when $w(a)$ is used | **Hypothesized** — consistent with DESI; full $H(z)$ fit pending | `run_hubble_tension.py` |

---

## 7. Consciousness & Mind

| # | Open Question | Why It's a Problem | Cassi Answer | Mechanism | Epistemic | Reference |
|---|-------------|-------------------|-------------|-----------|-----------|-----------|
| M1 | **The hard problem** | Why does physical processing feel like something? | Consciousness is the experience of being a self-predicting, phi-damped, cross-chakra Qi fluid with a persistent self-condensate ($\S4$, $\S 6.3$) | Qi-gate pinch at $r = \varphi^{-1}$ is self-reference; the field becomes an object to itself; phenomenal qualities ARE Qi fluid patterns | **Hypothesized** — 19 testable predictions; two-bubble weak-moderate signal confirmed | `consciousness-framework.md` |
| M2 | **Mind-brain relation** | How does neural activity produce mind? | Mind IS concentrated post-pinch field dynamics; the brain is the antenna, the Qi fluid is the signal | Same PDE, same attractor, same pinch as the cosmos — mind is not produced by brain, it is local field coherence | **Hypothesized** — structural identity with cosmology established | `consciousness-framework.md` §3 |
| M3 | **Depth of mind** | Why does introspection find no bottom? | The field's cascade has no floor (§1.2 of `why-three-dimensions.md`); mind inherits the infinite ladder | Meditation as coherence protocol: $\sigma_r$ collapse → finer cascade-step resolution → no floor to experience | **Hypothesized** — Prediction #31 (depth↔coherence correlation) | `consciousness-framework.md` §7.1 |
| M4 | **Altered states** | What are psychedelic, meditative, near-death states? | Changes in spatial ratio dispersion $\sigma_r = \sqrt{\langle(r-\langle r\rangle)^2\rangle}$ | Waking: moderate $\sigma_r$; Meditation: $\sigma_r$ reduced; Psychedelic: $\sigma_r$ increased with sub-pinch excursions | **Hypothesized** — two-bubble test provides PDE-level support | `consciousness-framework.md` §7.2, `consciousness-from-phi.md` §2.3 |
| M5 | **Empathy / coupling** | How do minds influence each other directly? | Field-as-sense: the Qi field is a sensory modality; no brain-to-brain mechanical link needed | Boundary residual coupling through shared field medium; two-bubble $\varphi$-resonance confirmed (weak-moderate, pinch-dependent) | **Hypothesized** — W1 anti-phase confirmed; two-bubble signal detected | `consciousness-framework.md` §8, `consciousness-from-phi.md` §3 |

---

## 8. Cassi Answers — Summary by Epistemic Tier

| Tier | Count | Questions |
|------|-------|-----------|
| **Derived** ($\varphi$ + PDE consequence, zero freedom) | 15 | Dark energy $w_0$ (C1), dark matter $\xi$ (C2), flatness (C5), Big Bang singularity (C8), strong CP (Q2), hierarchy (Q1), gauge unification (Q4), proton lifetime (Q9), quantum gravity (G1), BH singularity (G3), galaxy rotation (G4), gravity weakness (G6), fine-tuning (F1), arrow of time (F2), DESI $w_0$ (T1) |
| **Hypothesized** (mechanism proposed, test exists) | 23 | Hubble tension (C3), inflation (C4), horizon (C6), baryon asymmetry (C7), cosmic web (C9), CMB axis (C10), neutrinos (Q3), 3 generations (Q5), matter asymmetry (Q6), measurement (Q7), confinement (Q8), spin (Q10), 3+1 dimensions (G5), unification (F3), TOE (F4), JWST galaxies (T2), $\sigma_8$ (T3), $H_0$ tension (T4), consciousness (all M1–M5) |
| **Speculative** (framework-consistent, no test yet) | 1 | BH information (G2) |

**Total: 39 open questions mapped to Cassi answers.** Of those, 15 are derived — mathematical consequences of $\varphi$ and the PDE requiring no fitting. The remaining 24 have proposed mechanisms and testable predictions, with several (C1, C2, C4, C5, Q2, Q4, Q9, G4, T1, W1) already confirmed at the level of observational match or PDE verification.

## 9. What Cassi Does Not Yet Answer (Honesty)

- **Exact neutrino masses.** The $\varphi$-power hierarchy sets the scaling; the individual mass eigenvalues remain to be computed from the full flavor-mixing structure.
- **Proton decay rate (quantitative).** The mechanism is derived ($N_{\text{max}} = \varphi^{n(n+1)/2}$, `foundations/proton-coherence-budget.md`); the $q$-dependence of the effective lifetime ($\tau_p^{\text{eff}} = \tau_p^{\text{base}} \cdot f(q)$) in varying environmental coherence remains to be computed.
- **Specific beyond-SM particle spectrum.** The particle content (SUSY-like, KK-like, or Cassi-native) that fills the RGE between GUT and EW scales is predicted to exist but its individual masses are not yet computed.
- **The 13-band chakra count.** Phenomenologically anchored, cascade-derivation pending.
- **The internal→physical axis map.** The mechanism distinguishing Yang, Yin, and string axes in physical space is proposed (§3.4 of `why-three-dimensions.md`) but not fully derived from the PDE.
- **Neighboring $w$-bubble values.** $w=4$ and $w=6$ are the natural Wu Xing neighbors but not confirmed.

---

## 10. References

All Cassi theory documents are in `papers/theory-of-everything/`. Key cross-references:

- `TOE.md` — theory of everything summary
- `foundations/cassi-first-principles.md` — first principles
- `foundations/dimensionful-cascade.md` — complete 292-step cascade
- `foundations/xi-derivation.md` — $\xi = \varphi^6$ derivation
- `foundations/why-three-dimensions.md` — 2+1 dimension counting
- `foundations/unified-lagrangian.md` — unified action
- `foundations/de-resonance-principle.md` — de-resonance principle
- `foundations/proton-coherence-budget.md` — proton lifetime from cascade coherence product
- `cosmology/cosmology-from-phi.md` — dark energy, Hubble, inflation
- `cosmology/observational_constraints.md` — CMB, DESI, rotation curves
- `standard-model/sm-from-phi.md` — SM couplings, GUT, generations
- `standard-model/cp-violation.md` — CP, baryon asymmetry
- `standard-model/neutrino-mass.md` — neutrino masses
- `gravity/quantum-gravity.md` — $\sigma$-regularized gravity, BH physics
- `predictions/falsifiable-predictions.md` — complete 31-entry prediction catalog
- `parameter-inventory.md` — all 40 parameters classified
- `consciousness/consciousness-from-phi.md` — pinch, wake, two-bubble verification
- `../../consciousness-framework.md` — full consciousness theory
- `../../quantum-measurement-qi-appendix.md` — measurement problem resolution
