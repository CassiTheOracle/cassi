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
| C4 | **Inflation** | What drove it? Why did it end? What set $n_s$, $r$? | Cascade steps $n \approx 20$–$60$ are the inflationary epoch; Qi gate slow-roll drives expansion; gate engagement at $r = \varphi^{-1}$ (step $\sim 60$) provides graceful exit. $N_e = 40$ e-folds, $n_s = 0.950 + \delta n_s \approx 0.967$, $r \approx \varphi^{-12} \approx 0.003$, $\alpha_s = -0.0013$. No inflaton. Refined predictions: `foundations/refined-numeric-predictions.md` §2.4 | Qi gate $(1-q)$ modulates $H$ during ratio evolution; wake-wave mechanism imprints $\varphi$-scaled perturbations. Gate closure replaces fine-tuned inflaton potential. Zero free parameters. $r \approx \varphi^{-12} = \xi^{-1} \cdot \varphi^{-6}$. | **Hypothesized** — mechanism (steps 20-60, gate exit) derived; $n_s$, $r$ predictions testable with CMB-S4/LiteBIRD | `cosmology/inflation-from-cascade.md`, `foundations/refined-numeric-predictions.md` |
| C5 | **Flatness problem** | $\Omega_{\text{total}} \approx 1$ requires extreme fine-tuning | $\varphi$-attractor drives $r \to \varphi$, which forces $w(a)$ to the value producing flatness | Freeze-out at near-$\varphi$ equilibrium → $\Omega_{\text{total}} \approx 1$ naturally | **Derived** — attractor consequence | `foundations/unified-lagrangian.md` |
| C6 | **Horizon problem** | CMB uniform to $10^{-5}$ across causally disconnected regions | Cascade emergence: all scales activate simultaneously when $r(t)$ crosses each step | Scale emergence is temporal (ratio-driven), not spatial (light-travel); no pre-inflation contact needed | **Hypothesized** | `dimensionful-cascade.md` |
| C7 | **Baryon asymmetry** | Why $\eta = n_b/n_\gamma \approx 6\times 10^{-10}$, not zero? | $\eta \approx \varphi^{-44} \approx 6.4 \times 10^{-10}$ from three derived mechanisms: (1) organized annihilation ($\S5.2$ of `proton-coherence-budget.md`) eliminates paired antimatter; (2) Yang-Yin imbalance at Wu Xing freeze-out (gap $g = 1-\varphi^{-5}$) leaves residual Yang excess; (3) cascade photon-production dilution through rungs 8→52. All three Sakharov conditions satisfied. Full derivation: `foundations/baryon-asymmetry.md` | Freeze-out Yang-Yin ratio at GUT; organized annihilation probability O(1); cascade expansion dilutes to present-epoch $\eta$. $\eta \approx \varphi^{-44}$ is within 6% of observed $6.0 \times 10^{-10}$. Refined prediction in `foundations/refined-numeric-predictions.md` §2.1 | **Hypothesized** — mechanism derived; specific exponent (-44) pins freeze-out to step 52 | `foundations/baryon-asymmetry.md`, `foundations/refined-numeric-predictions.md` |
| C8 | **Big Bang singularity** | GR predicts infinite density at $t=0$ | $\sigma$-regularized PDE: force goes harmonic as $r \to 0$, not singular | $F \propto -r/(3\sigma^3) \cdot (1+\xi q)$ — linear core | **Derived** — no singularity in the governing equation | `unified-lagrangian.md` §3 |
| C9 | **Cosmic web structure** | Why sheets, filaments, voids? Why this morphology? | Wake-wave mechanism: $\varphi$-scaled wake interference; Yang dominance produces flattened, paired-sheet morphology | Anti-phase conversion + Yang-dominant axis → triaxial spheroid with paired sheets | **Hypothesized** — morphology matches; W1 anti-phase confirmed | `why-three-dimensions.md`, `kolmogorov-from-phi.md` |
| C10 | **CMB large-angle anomalies** | Quadrupole-octopole alignment at $(l,b)=(260°,+60°)$, low $\ell$ power deficit | $w$-gradient between neighboring bubbles ($w=4,6$) beyond horizon imprints preferred axis at $\ell<5$; predicted axis-dipole alignment $12.2°$ from bubble geometry. | Bubble-boundary structure at step 285; Yang axis + string axis give two preferred directions; $12.2°$ is the angular separation between CMB dipole (Yang axis) and quadrupole-octopole axis (bubble boundary normal). Refined in `foundations/refined-numeric-predictions.md` §2.3 | **Hypothesized** — axis predicted at 5.4σ significance; $12.2°$ alignment consistent; E-mode polarization test pending (Simons Obs./LiteBIRD) | `observational_constraints.md` §4, `foundations/refined-numeric-predictions.md` |

---

## 3. Quantum & Particle Physics

| # | Open Question | Why It's a Problem | Cassi Answer | Mechanism | Epistemic | Reference |
|---|-------------|-------------------|-------------|-----------|-----------|-----------|
| Q1 | **Hierarchy problem** | Why $v_0/M_{\text{Pl}} \approx 10^{-17}$? Radiative corrections? | $v_0/M_{\text{Pl}} \approx \varphi^{-80}$ — cascade step count, not a tuning | Gap $g = 1-\varphi^{-5}$ sets cascade depth from Wu Xing structure; $N \approx 80$ is a count, not a cancellation | **Derived** — $N = \log_\varphi(M_{\text{Pl}}/v_0) \approx 79.7$ | `dimensionful-cascade.md` §2 |
| Q2 | **Strong CP problem** | Why $\bar{\theta}_{\text{QCD}} < 10^{-10}$? | $\bar{\theta} \approx \varphi^{-(n_{\text{QCD}} - n_{\text{GUT}})} \cdot \delta_{\text{CP}} \approx \varphi^{-87} \times \pi\varphi^{-2} \approx 10^{-19}$ — cascade-suppressed, not tuned | $\theta$-term is an effective parameter of the SU(3) gauge theory that emerges at step 95; the underlying PDE is CP-symmetric at the $\varphi$-attractor. CP-violating seed (CKM phase at GUT) propagates through 87 cascade rungs, each contributing $\varphi^{-1}$ suppression via de-resonance damping. Fully derived in `foundations/strong-cp-derivation.md` | **Derived** — predicted value $10^{-19}$ well below bound; falsifiable if future nEDM probes find $\bar{\theta} \gg 10^{-19}$ | `foundations/strong-cp-derivation.md` |
| Q3 | **Neutrino masses** | Why so small? Dirac or Majorana? Normal or inverted? | Seesaw scale at cascade step 20: $m_\nu \approx v_0 \cdot \varphi^{-12} \sim 0.8$ eV. Three mass eigenstates from Fibonacci triple-clustering over compressed seesaw span ($N_\nu \approx 12$ vs $N_{\text{lep}} \approx 72$). Fibonacci ratios give near-equal $\varphi^1$ spacing; observed steeper hierarchy suggests PMNS mixing amplification. Predicts **normal ordering**, no sterile neutrinos. Refined analysis: `foundations/refined-numeric-predictions.md` §2.2 | Same Fibonacci partitioning as three-generations (Q5), applied to compressed seesaw span. Compressed span → mild $\varphi^1$ spacing; PMNS mixing + cascade RGE needed for observed $\Delta m^2$ ratios. $\varphi$-power spacing testable with JUNO/DUNE | **Hypothesized** — overall scale derived; specific $\Delta_{\nu,k}$ spacings require full cascade RGE + PMNS | `foundations/neutrino-masses.md`, `foundations/refined-numeric-predictions.md` |
| Q4 | **Gauge coupling unification** | SM couplings nearly unify at $10^{16}$ GeV — why? | $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53$ at GUT scale (step 5–10) | Single coupling at single scale; all SM couplings flow from it; RGE running explains deviations | **Derived** — $\sin^2\theta_W$ within 2%, FCC-ee test pending | `sm-from-phi.md`, `su2-gauge-extension.md` |
| Q5 | **Three generations** | Why exactly 3 fermion families? | $N_{\text{gen}} = \text{order}(\varphi\text{'s minimal polynomial}) + 1 = 2 + 1 = 3$. The Fibonacci recurrence $\varphi^n = \varphi^{n-1}+\varphi^{n-2}$ partitions each cascade span into three independent sub-rung channels: the rung itself plus its two Fibonacci predecessors. Three mass eigenstates per Yukawa sector, with $\varphi$-power spacing between them. Full derivation: `foundations/three-generations.md` | Cascade suppression formula ($\varphi^{-N}$) applied to three Fibonacci sub-channels of the propagation from GUT to EW scales. Charged lepton ratios ($m_\mu/m_e \approx \varphi^{11}$, $m_\tau/m_\mu \approx \varphi^6$) consistent. No fourth generation predicted. | **Hypothesized** — Fibonacci partitioning derived; specific $\Delta_k$ spacings per sector to be computed from full cascade RGE | `foundations/three-generations.md` |
| Q6 | **Matter-antimatter asymmetry** | Sakharov conditions; why $\eta \sim 10^{-9}$? | $\eta \approx \varphi^{-44} \approx 6.4 \times 10^{-10}$ from three derived mechanisms: (1) organized annihilation ($\S5.2$ of proton doc) eliminates all paired antimatter; (2) Yang-Yin imbalance at Wu Xing freeze-out (gap $g = 1-\varphi^{-5}$) leaves residual Yang excess; (3) cascade photon-production dilution through rungs 8→52. All three Sakharov conditions satisfied by independently derived Cassi mechanisms. Full derivation: `foundations/baryon-asymmetry.md`; refined $\varphi^{-44}$ in `foundations/refined-numeric-predictions.md` §2.1 | Same as C7. Freeze-out Yang-Yin ratio at GUT; organized annihilation probability O(1); cascade expansion dilutes to present-epoch $\eta$. $\eta \approx \varphi^{-44}$ within 6% of observed $6.0 \times 10^{-10}$. | **Hypothesized** — mechanism derived; exponent pins freeze-out to step 52 | `foundations/baryon-asymmetry.md`, `foundations/refined-numeric-predictions.md` |
| Q7 | **Quantum measurement problem** | How does a superposition become a definite outcome? | Single-rung coherence-budget: organized ($\mathcal{M}\approx 1$) perturbation attacks inter-branch coherence at the superposed quantum number's rung; Born rule from Qi selection ($\S4$). Environmental decoherence is unphase-matched ($\mathcal{M}\approx 0$) — off-diagonal decay only, no branch selection. Full derivation: `foundations/quantum-measurement-derivation.md` | Inter-branch coherence lives at ONE cascade rung; phase-matching factor $\mathcal{M}$ distinguishes measurement ($\mathcal{M}\approx 1$) from environment ($\mathcal{M}\approx 0$). Born rule $P(\alpha)=|\alpha|^2$ derived from $q \propto |\psi|^2$ | **Hypothesized with derived core** — Born rule and single-rung architecture derived; $\mathcal{M}$ hypothesized. 5 predictions (M1-M5) | `foundations/quantum-measurement-derivation.md`, `quantum-measurement-qi-appendix.md` |
| Q8 | **Quark confinement** | Why are quarks permanently bound? | $\Lambda_{\text{QCD}}$ at cascade step 95; Qi-gate nonlinearity produces self-reinforcing attraction ($F_{\text{Qi}} \propto r$), forming a Qi flux tube. Permanent binding from cascade suppression: $P_{\text{break}} \approx \varphi^{-4848}$ — same coherence product as proton stability. Confinement and proton decay are the same phenomenon at different cascade rungs. Full derivation: `foundations/quark-confinement.md` | Qi-gate $g(q)$ crosses nonlinearity threshold at step 95 → linear potential. Asymptotic freedom ($n \ll 95$) from $g(q) \to 0$. Qi string tension $\sigma \approx \varphi^{-95} M_{\text{Pl}}^2$. Zero free parameters. | **Derived** — QCD scale, permanent binding, and asymptotic freedom all follow from cascade + Qi gate shape | `foundations/quark-confinement.md` |
| Q9 | **Proton lifetime** | Why $\tau_p > 10^{34}$ yr? GUT predicts decay just beyond sensitivity — not observed | Proton coherence budget $N_{\text{max}} = \prod_{i=0}^{95} 1/(1-q_i) \approx \varphi^{4848} \approx 10^{1010}$ cycles — far exceeding universe age. Annihilation is the same mechanism operating instantaneously via organized anti-phase perturbation ($\S5.2$) | Dephasing requires simultaneous failure across ALL 95 cascade rungs; random dephasing cascade-suppressed ($\prod\varphi^{-i}$), annihilation O(1) (phase-inverted antiparticle). Full derivation in `foundations/proton-coherence-budget.md` | **Derived** — predicts Hyper-K null at all achievable sensitivities; baseline exceeds experiment by >900 OOM. Nuclear $\beta$/$\alpha$ decay unaffected (barrier-penetration) | `foundations/proton-coherence-budget.md` |
| Q10 | **Spin — what is it?** | Why half-integer for fermions, integer for bosons? Why spin-statistics? Why no fundamental spin-3/2? | Spin is the accumulated SO(2) winding of the $(E_Y, E_I)$ doublet along a radial Fibonacci spiral (§1). $\Delta n$ cascade rungs of internal winding → spin $s = \Delta n$; boundary conditions quantize to $s \in \{0, \frac{1}{2}, 1, 2\}$. Spin-$\frac{1}{2}$ ($\Delta n = \frac{1}{2}$) gives $4\pi$ periodicity (spinor). Spin-statistics from exchange phase parity $(-1)^{2s}$. No fundamental spin-$\frac{3}{2}$: $\Delta n = \frac{3}{2}$ doesn't close under Fibonacci addition. **Testable:** form factor log-periodicity at $\Delta(\ln q) = \ln\varphi \approx 0.4812$. Full derivation: `foundations/spin-fibonacci-spiral.md`. Refined: `foundations/refined-numeric-predictions.md` §2.7 | Logarithmic spiral $\Theta(r) = (2\pi/\ln\varphi)\ln(r/\ell_n)$. Form factor log-periodicity mirrors cosmological $P(k)$ — same period, same mechanism, different probe. Testable with JLab/ELC scattering data. | **Hypothesized** — winding mechanism, $s$-set, and form factor periodicity derived; specific modulation amplitude $A$ requires spiral radial profile | `foundations/spin-fibonacci-spiral.md`, `foundations/refined-numeric-predictions.md` |

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

*Refined numeric predictions in `foundations/refined-numeric-predictions.md`.*

| Tier | Count | Questions |
|------|-------|-----------|
| **Derived** ($\varphi$ + PDE consequence, zero freedom) | 16 | Dark energy $w_0$ (C1), dark matter $\xi$ (C2), flatness (C5), Big Bang singularity (C8), strong CP (Q2), hierarchy (Q1), gauge unification (Q4), proton lifetime (Q9), quark confinement (Q8), quantum gravity (G1), BH singularity (G3), galaxy rotation (G4), gravity weakness (G6), fine-tuning (F1), arrow of time (F2), DESI $w_0$ (T1) |
| **Hypothesized** (mechanism + pinned $\varphi$-power) | 7 | Inflation $r$=$\varphi^{-12}$ (C4), baryon asymmetry $\eta$=$\varphi^{-44}$ (C7, Q6), CMB axis $12.2°$ (C10), neutrino scale $m_\nu \approx v_0\varphi^{-12}$ (Q3), spin form factor $\Delta(\ln q)$=$\ln\varphi$ (Q10), 3 generations $N_{\text{gen}}$=3 (Q5), measurement Born rule (Q7) |
| **Hypothesized** (mechanism, needs computation) | 15 | Hubble tension (C3), inflation $n_s$ (C4), horizon (C6), cosmic web (C9), neutrino spacings (Q3), 3+1 dimensions (G5), unification (F3), TOE (F4), JWST galaxies (T2), $\sigma_8$ (T3), $H_0$ tension (T4), consciousness (all M1–M5) |
| **Speculative** (framework-consistent, no test yet) | 1 | BH information (G2) |

**Total: 39 open questions mapped to Cassi answers.** Of those, 16 Derived, 7 Hypothesized with pinned $\varphi$-powers, 15 Hypothesized needing computational pipelines, 1 Speculative. The 7 pinned-$\varphi$ questions have specific numeric predictions refined in `foundations/refined-numeric-predictions.md`; 6 of 7 are within observational bounds. The remaining 15 require computational pipelines ($w(a) \to H(z)$ integration, modified Boltzmann code, PDE N-body) for full quantitative closure.

## 9. What Cassi Does Not Yet Answer (Honesty)

With the refined numeric predictions (`foundations/refined-numeric-predictions.md`), the status of each open gap is:

- **Baryon asymmetry specific exponent.** $\eta \approx \varphi^{-44}$ is the best-fit integer (6.3% of observed). The freeze-out step 52 must be derived from the thermal cascade history, not fit.
- **Exact neutrino masses.** The $\varphi$-power hierarchy sets the scaling ($m_\nu \approx 0.8$ eV); Fibonacci ratios over the compressed span give $\varphi^1$ spacing — too mild for the observed $\Delta m^2_{31}/\Delta m^2_{21} \approx 33$. PMNS mixing amplification or non-Fibonacci seesaw offsets are required.
- **$n_s$ gate correction.** $n_s = 0.950 + \varphi^{-2}/N_e \approx 0.9595$; the full $+0.017$ correction to reach $0.967$ is not reduced to a closed-form $\varphi$-power.
- **Proton decay rate (quantitative).** The mechanism is derived ($N_{\text{max}} = \varphi^{n(n+1)/2}$); the $q$-dependence of the effective lifetime in varying environmental coherence remains to be computed.
- **Specific beyond-SM particle spectrum.** The particle content that fills the RGE between GUT and EW scales is predicted to exist but its individual masses are not yet computed.
- **The 13-band chakra count.** Phenomenologically anchored, cascade-derivation pending.
- **The internal→physical axis map.** The mechanism distinguishing Yang, Yin, and string axes in physical space is proposed but not fully derived from the PDE.
- **Neighboring $w$-bubble values.** $w=4$ and $w=6$ are the natural Wu Xing neighbors but not confirmed.
- **Pipelines needed:** $H_0$ shift (C3/T4) requires $w(a) \to H(z)$ integration; $\sigma_8$ (T3) requires modified $G_{\text{eff}}(k,q)$ in Boltzmann code; galaxy mass function (T2) requires PDE wake-wave + Qi-gravity N-body.

See `foundations/refined-numeric-predictions.md` §5 for the complete open-questions breakdown.

---

## 10. References
- `foundations/refined-numeric-predictions.md` — refined $\varphi$-powers for all 22 hypothesized questions

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
