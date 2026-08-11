# Foundations—First Principles and the φ-Cascade Machinery

## Status: Index—July 2026

## Abstract

This directory holds the load-bearing derivations of the Cassi framework: the dimensionful cascade $\ell_n = \ell_{\text{Pl}} \times \varphi^n$ and the cascade suppression law $\mathcal{D} = \varphi^{-N}$ (the two wedge documents), the assembled unified Lagrangian and the two-fluid first principles behind it, and the derivation family—spin, the Qi-gravity coupling $\xi = \varphi^6$, the Wu Xing number $w = 5$, proton stability, measurement, strong CP, confinement, generations, neutrino masses, baryon asymmetry, and the bubble-lattice geometry that structures every rung. Reading order: start with `dimensionful-cascade.md` and `cascade-suppression-formula.md`, then `unified-lagrangian.md` and `cassi-first-principles.md` (with `cassi-theory-reference.md` as the compact map), then the structural-constant derivations, the spiral-dynamics family, the coherence-budget derivations, the particle-physics derivations, the bubble geometry, and finally the numeric-refinement and gap-closing documents. Epistemic tiers below are taken verbatim from each document's own Status header: most are Derived or Derivation, a smaller set (dimensionful constants, φ-RG, spiral dynamics, three generations, microcascade) are Hypothesized, and none are Speculative.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `dimensionful-cascade.md` | Scales from φ | Derived |
| 2 | `cascade-suppression-formula.md` | Universal attenuation law | Derived |
| 3 | `unified-lagrangian.md` | Assembled Lagrangian | Derived |
| 4 | `cassi-first-principles.md` | Postulate and two-fluid PDE | Derived PDE; asserted single-channel g(q) input |
| 5 | `cassi-theory-reference.md` | Compact framework reference | Reference |
| 6 | `xi-derivation.md` | Qi-gravity coupling | Derived conditional on the quadratic-coupling input |
| 7 | `why-three-dimensions.md` | Spatial dimension count | Hypothesis |
| 8 | `wu-xing-derivation.md` | Wu Xing number $w = 5$ | Derived (single input: coherence postulate) |
| 9 | `dimensionful-constants-status.md` | $c$, $\hbar$, $G$ status | Hypothesized |
| 10 | `phi-rg-formalism.md` | φ as RG fixed point | Hypothesized |
| 11 | `spiral-dynamics.md` | Hubble, gravity, $c$ from spiral | Hypothesized |
| 12 | `spin-fibonacci-spiral.md` | Spin as spiral winding | Derivation |
| 13 | `phi_attractor_synthesis.md` | Analytical N-body paths | Derived |
| 14 | `wa-pentagon-gate.md` | $w_a$ sign tension | Derived / Hypothesized |
| 15 | `proton-coherence-budget.md` | Proton stability | Derivation |
| 16 | `quantum-measurement-derivation.md` | Born rule | Derivation |
| 17 | `strong-cp-derivation.md` | Strong CP | Derivation |
| 18 | `quark-confinement.md` | Confinement | Derived (tube extensivity + cell quantization) |
| 19 | `three-generations.md` | Generation count | Hypothesized |
| 20 | `neutrino-masses.md` | Neutrino spectrum | Derivation |
| 21 | `baryon-asymmetry.md` | Baryogenesis | Derived |
| 22 | `bubble-lattice-fabric.md` | Universal lattice | Derived (structural) |
| 23 | `bubble-edge-geometry.md` | Condensation boundary | Derived geometry; threshold conditional on asserted gate |
| 24 | `microcascade-mirror.md` | Sub-Planckian ladder | Hypothesized |
| 25 | `refined-numeric-predictions.md` | Pinned φ-powers | Active derivation |
| 26 | `deriving-remaining-gaps.md` | Residual parameters | Resolved / narrowed |
| 27 | `sector-coupling-derivation.md` | Dirac↔two-fluid sector coupling | Derived conditional on $\delta = 3$ (rung identity) w/ Hypothesized coefficient |
| 28 | `wake-geometry.md` | Wake geometry | Derived (structural) |
| 29 | `rung-offset-mechanism.md` | Rung offsets δn | Hypothesized mechanism, Empirical catalog |
| 30 | `wu-xing-cycle-structure.md` | Wu Xing cycles, ring algebra | Derived / Tested / Hypothesized |

## Document Summaries

### `dimensionful-cascade.md`—The Dimensionful Cascade: All Physical Scales from $\varphi$

The wedge document. The two-fluid framework has exactly one dimensionful constant—the Planck length $\ell_{\text{Pl}}$—and every physical scale is a $\varphi$-power of it:

$$\boxed{\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}}$$

for integer $n$ from 0 (Planck) to 292 (today's horizon rung). The exponent is the freeze-out point of the $\varphi$-attractor dynamics, so the cascade table ($n = 80$ electroweak, 95 QCD, 117 Bohr, 267 Milky Way, 292 horizon rung) is a catalogue of dynamical thresholds, not fitted points. Includes the consistency check $v_0/M_{\text{Pl}} = g\,\varphi^{-N}$ with $N \approx 80$ matching observation within 5.3%, and the extension notes to the megacascade and microcascade. Status: Derived.

### `cascade-suppression-formula.md`—The Cascade Suppression Formula: $\varphi^{-N}$ as the Universal Attenuation Law

The second wedge. Any quantity originating at cascade rung $m$ and observed at rung $n$ is attenuated by the product of per-rung damping factors:

$$\boxed{\mathcal{D}_{m \to n} = \prod_{i=m}^{n-1} d_i}$$

with two regimes derived once from the two-fluid PDE: signal propagation ($d_i \approx \varphi^{-1}$, so $\mathcal{D} = \varphi^{-N}$, linear in span—CP violation, the hierarchy, neutrino masses) and coherence maintenance ($d_i = 1 - q_i = \varphi^{-i-\delta}$, so $\mathcal{D} = \varphi^{-n(n+1)/2}$, quadratic in depth—proton stability, anything needing simultaneous coherence across all supporting rungs). Every "hierarchy" or "stability" puzzle in physics becomes an instance of this single formula. Status: Derived.

### `unified-lagrangian.md`—The Cassi Unified Lagrangian

Assembles every sector into a single object,

$$\boxed{\mathcal{L}_{\text{Cassi}} = \mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}}}$$

with dimensionless couplings expressed as $\varphi$-powers, the derived conversion rate $\lambda = 1/(2w) = 0.1$, and three external dimensionful constants ($c$, $\hbar$, $G$). The two-fluid core is a paired-real SO(2) doublet with the $\varphi$-attractor potential $(\lambda/2)(\Psi_0^2 - \varphi\Psi_1^2)^2$, a Bohm quantum potential, and the Qi diagnostics; the Dirac sector emerges from the doublet through chiral projectors, and gravity couples through $G_{\text{eff}} = G(\pi/\rho)(1 + (\varphi^{6}-1)q)$ with $\xi = \varphi^6$. The Standard Model section records the asserted boundary $\sin^2\theta_W = \varphi^{-3} \approx 0.236$ and the mixing-sector terms; its coupling-normalization blocker is in `standard-model/su2-gauge-extension.md` §3.2.1. Status: Derived assembly; Weinberg boundary asserted.

### `cassi-first-principles.md`—Cassi First Principles

States the postulate:

$$\boxed{\varphi = \frac{1 + \sqrt{5}}{2} \approx 1.618033989}$$

as the universal scale-separation constant, with every coupling, mass ratio, and cosmological parameter a $\varphi$-power and zero free parameters. Builds the two-fluid picture—the Yang/Yin doublet, energy densities $\rho = \Psi_0^2 + \Psi_1^2$, the Yang fraction $\pi/\rho$, the attractor potential $V_{\text{attr}} = (\lambda/2)(\Psi_0^2 - \varphi\Psi_1^2)^2$—and derives the fixed-point imbalance $\pi/\rho = \varphi^{-3} \approx 0.236$ (the Yang fraction at equilibrium is $\varphi^{-1}$; label Mapped, ledger row 500) that reappears in cosmology, particle physics, and gravity, plus Qi as coherence from asymmetry. Ends with the four-pillar validation status against observational data. Status: Derived.

### `cassi-theory-reference.md`—The Cassi Framework (Compact Reference)

The audited compact reference: one document restating the postulate, the two-fluid PDE, Qi coherence ($q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$), the Qi gate with its sign convention (conversion runs hard when $q \to 0$; the gate determines $w(a)$), the cascade, and the framework constants—$G_{\text{eff}} = G(\pi/\rho)(1 + (\varphi^{6}-1)q)$ with $\xi = \varphi^6$, the asserted boundary $\sin^2\theta_W = \varphi^{-3}$, and the three spatial dimensions as the spiral's Frenet–Serret frame. The gate sign is established by the PDE tests in `consciousness/trauma-as-frozen-gate.md` §10.4. Use it as the map before reading the individual derivations. Status: Reference.

### `xi-derivation.md`—Derivation of $\xi = \varphi^6$: The Last Free Parameter

Derives the Qi-gravity coupling, calibrated empirically to $\xi \approx 18$ from the Milky Way rotation curve, as exactly

$$\boxed{\xi = \varphi^6 = \left(\frac{\pi}{\rho}\right)^{-2} = (\varphi^{-3})^{-2} \approx 17.944}$$

The exponent 6 is the inverse-square of the fixed-point imbalance: $\pi/\rho = (\varphi-1)/(\varphi+1) = \varphi^{-3}$ follows from the attractor ($E_Y = \varphi E_I$), and the $-2$ is the quadratic degree of the gravitational coupling. The saturation ceiling $G_{\text{eff,max}} = \varphi^3 G$ matches the dwarf-spheroidal M/L bound. The older reading (2 field components × 3 spatial dimensions) survives as a secondary geometric reading; the 3 remains conditional on the candidate derivation in `why-three-dimensions.md`. Status: Derived conditional on the quadratic-coupling input / Calibrated empirical pin.

### `why-three-dimensions.md`—Why Three Dimensions: The Spiral's Three Directions

Removes the last imported integer by overdetermination: the string's trajectory through field space is the Fibonacci spiral, and a space curve's Frenet-Serret frame supplies exactly three orthogonal directions; four further framework-internal routes (Lucas, attractor, noise–signal, rung-clock) close on $d = 3$ independently (verified 2026-08-11, `computations/why_three_dimensions_frenet.py`):

$$\boxed{\text{Three spatial dimensions} = \{\mathbf{T}, \mathbf{N}, \mathbf{B}\}}$$

so $\xi = \varphi^{2 \times 3}$ needs no accounting for the 3. The $\varphi$-determined geometry gives the universe-bubble a triaxial spheroid shape whose internal morphology is a testable fork—single central sheet vs. paired sheets flanking a central void—decided in favor of the anti-phase paired sheets by the W1 experiment, with further tests in large-scale structure morphology and the CMB axis. Status: Hypothesis with one decided fork (W1: anti-phase confirmed).

### `wu-xing-derivation.md`—Wu Xing Number $w = 5$: Derivation from Cascade Dynamics

Derives the number of elements in the primordial generation/control cycle from a single physical input. The coherence criterion applied to ALL cycle sizes at once — a $w$-step cycle closes only if its accumulated phase error $E(w) = w\min_p|\varphi - p/w|$ stays at or below the cascade signal $\varphi^{-w}$ — selects exactly $\{1, 2, 3, 5\}$: continued-fraction optimality (Hurwitz) makes the Fibonacci denominators the only candidates, the exact identity $|F_k\varphi - F_{k+1}| = \varphi^{-k}$ evaluates them, and $w = 5$ passes at equality (verified exhaustively to $w = 2000$); $\varphi$-geometry eliminates $w < 5$ (the pentagon is the minimal regular polygon containing $\varphi$). The intersection is uniquely

$$\boxed{w = 5}$$

giving the primordial gap $g = 1 - \varphi^{-5} \approx 0.9098$ and the initial Yang-Yin ratio $r_0 = \varphi^{-5}/(2 - \varphi^{-5}) \approx 0.047$—Yin-dominated by a factor of $\sim 21$. Status: Derived.

### `dimensionful-constants-status.md`—Dimensionful Constants: Derivation Status of $c$, $\hbar$, and $G$

Catalogues what is derivable and what is structural. Every dimensionless parameter is now derived, including the PDE conversion rate $\lambda = 1/(2w) = 0.1$ once $w = 5$ is known, and the geometric mechanism for $c$ is closed as

$$\boxed{c \propto \lambda \cdot \ell_{\text{Pl}}}$$

The numerical values of $c$, $\hbar$, $G$ individually cannot follow from a dimensionless constant: one anchor $\ell_{\text{Pl}} = \sqrt{\hbar G/c^3}$ determines one combination, which is a structural limitation shared by any theory with a single dimensionful anchor. The document states this boundary explicitly, without claiming more. Status: Hypothesized.

### `phi-rg-formalism.md`—The Golden Ratio as a Renormalization Group Fixed Point

Formalizes the $\varphi$-spaced hierarchy as a discrete Wilsonian renormalization group with scale factor $b = \varphi$:

$$\boxed{\mathcal{R}_\varphi[\mathcal{L}_k] = \mathcal{L}_{k/\varphi}}$$

with the discrete beta function $\beta_\varphi(g) = [g(k/\varphi) - g(k)]/\ln\varphi$, recovering the continuous beta function in the limit $\varphi \to 1^+$. The critical coupling $\boxed{\alpha_c = \varphi^{-1}}$ is the unique stable fixed point of the flow, and the SM $\varphi$-power predictions ($\sin^2\theta_W$, $\alpha_{\text{GUT}}$, $\xi = \varphi^6$) are IR values of trajectories from it. The de-resonance principle gains a field-theoretic foundation: $\varphi$'s maximal irrationality ensures the flow never hits a rational resonance. Status: Hypothesized.

### `spiral-dynamics.md`—Spiral Dynamics: Hubble, Gravity, and $c$ from Fibonacci Spiral Geometry

Reads cosmic expansion, gravitational attraction, and the speed of light as three projections of the single Fibonacci spiral traced by the $(E_Y, E_I)$ doublet, $\Theta(n) = \Theta_0 + (2\pi/\ln\varphi)\,n$—one full turn per cascade rung. Expansion is the spiral's unwinding rate, with $H \approx (\lambda\ln\varphi/2\pi)(1-q)$ near equilibrium and the general form $H = (\lambda/3)(\varphi-r)(1+r)/r + \lambda\varphi^{-2}/3$ (the 1/3 is the isotropic dimension factor $1/d$ at $d = 3$—Derived, `cosmology/cosmology-from-phi.md` §1; the $\lambda\varphi^{-2}$ rate asserted); gravity is gradient descent along the spiral toward coherence; $c$ is the scale-invariant product of conversion rate and coherence wavelength; gravitational strength runs as $\alpha_G(n) \sim \varphi^{-2n}$. Status: Hypothesized.

### `spin-fibonacci-spiral.md`—Spin as Fibonacci Spiral Winding: The SO(2) Doublet Fractal

Spin is the accumulated SO(2) winding of the $(E_Y, E_I)$ doublet along the radial logarithmic spiral

$$\boxed{\Theta(r) = \Theta_0 + \frac{2\pi}{\ln\varphi} \cdot \ln\!\left(\frac{r}{\ell_n}\right)}$$

The total rotation divided by $2\pi$ is the spin, $\boxed{s = \Delta\Theta/2\pi = \Delta n}$, and standing-wave boundary conditions quantize the winding to spin-0 (no winding), 1/2 (half-turn), 1 (full turn, gauge boson), and 2 (two turns, graviton); spin-statistics emerge from the parity of the winding number. The nested spirals across all supporting rungs form a self-similar Fibonacci fractal, and the falsifiable imprint is a $\ln\varphi$-periodic modulation of particle form factors $F(q^2)$ testable in scattering data. Status: Derivation.

### `phi_attractor_synthesis.md`—φ-Attractor Steady States and the Analytical Three-Body Problem in Cassi Gravity

Explores whether the Cassi N-body solver—Gaussian-softened, $\varphi$-damped ($d = \varphi^{-1}$ velocity updates), with Qi-enhanced gravity $G_{\text{eff}}/G = (\pi/\rho)(1 + (\varphi^{6}-1)q)$—admits analytical results, and develops nine interconnected paths. Key outputs: the asymptotic half-mass radius $R_\infty(d) = R_{\min} + \Delta R \exp(-\gamma_0\, d/(1-d)\, T)$, Qi-hydrostatic equilibrium disproven for damped systems, cold-collapse virial decay with time constant $\tau_Q = dt/(2|\ln d|)$, and the Cassi perihelion precession

$$\boxed{\Delta\phi_{\text{Cassi}} = -\sqrt{2\pi}\left(\frac{\sigma}{a}\right)^3 \frac{1 + e^2/4}{(1 - e^2)^3} \quad \text{[rad/orbit]}}$$

retrograde, opposite to the prograde GR precession, and a discriminating test between the softened-Qi theory and GR. Status: Derived.

### `wa-pentagon-gate.md`—The $w_a$ Sign Tension: 5-Channel Pentagonal Gate

Resolves the dark-energy equation-of-state tension. The bare two-fluid prediction $w_a = +0.44$ sits $2.5\sigma$ from DESI DR2 ($-0.51 \pm 0.38$), but including the already-verified Qi-gravity coupling in the expansion rate,

$$\boxed{H_{\text{eff}} = H_{\text{bare}} \,\sqrt{1 + (\varphi^{6}-1)q(r)}}$$

shifts the prediction to $+0.10$ ($1.6\sigma$); the 5-channel pentagonal gate (channel openness $b_i = \varphi^{-k_i}$, $k_i = 2 + i$) and Wu Xing control-release add secondary negative shifts, bringing the combined prediction to $\boxed{w_a^{\text{pred}} \approx [-0.05, +0.10]}$, within $1.4\sigma$ of DESI. Four independent checks ($\lambda$-independence, gate-$\alpha$-independence, spatial-boost falsification, structural-mode decay) rule out numerical artifacts in the bare sign. Status: Derived ($\xi = \varphi^6$) / Hypothesized (5-channel).

### `proton-coherence-budget.md`—Proton Coherence Budget: Derivation of $N_{\text{max}}$

A condensed standing wave at cascade step $n = 91.5$ ($\log_\varphi(\lambda_p/\ell_{\text{Pl}}) = 91.46$) is not an isolated structure: its coherence is maintained by the entire cascade from Planck to its own rung, and dephasing requires the simultaneous loss of coherence at all $n$ supporting rungs. The coherence budget is the product of per-rung survival probabilities,

$$\boxed{N_{\text{max}} = \prod_{i=0}^{n} \frac{1}{1-q_i} \approx \varphi^{\,n(n+1)/2}}$$

giving $N_{\text{max}} \approx \varphi^{4228} \approx 10^{884}$ cycles ($\varphi^{4506} \approx 10^{942}$ with the Planck-scale $\sigma$-regularization included). The proton's effective lifetime exceeds the age of the observable universe by roughly 900 orders of magnitude—proton decay is not observed because the universe is not remotely old enough. Status: Derivation.

### `quantum-measurement-derivation.md`—Quantum Measurement as Organized Cascade Perturbation

Applies the coherence budget to measurement. A superposition's branches share every cascade rung except the one of the superposed observable, so inter-branch coherence is a single-rung phenomenon; organized perturbation phase-matched to that rung collapses it with $\mathcal{O}(1)$ probability per interaction, while random perturbation (environmental decoherence) at the same rung only damps off-diagonal terms and selects no outcome. The Born rule then follows from Qi density with no collapse postulate:

$$\boxed{P(\alpha) = \frac{q_\alpha}{q_\alpha + q_\beta} = \frac{|\alpha|^2}{|\alpha|^2 + |\beta|^2}}$$

The same coherence-budget machinery that stabilizes the proton for $\sim 10^{910}$ years explains why collapse happens at all. Status: Derivation.

### `strong-cp-derivation.md`—Strong CP: Why $\bar{\theta} \approx 0$ from Cascade De-Resonance

The QCD $\theta$-term arises as an effective parameter of the SU(3) theory that emerges from the two-fluid PDE at cascade step 95, and the $\varphi$-attractor fixed point is CP-symmetric. Any CP-violating departure originating at the GUT scale (n ≈ 13.3) is cascade-suppressed over the ~81 rungs to the QCD scale:

$$\boxed{\bar{\theta} \approx \varphi^{-81.4} \times \pi\varphi^{-2} = \pi\varphi^{-83.4} \approx 1.2 \times 10^{-17}}$$

~7 orders of magnitude below the experimental bound of $10^{-10}$. The span is Mapped (its GUT-seed anchor and $\delta_{\text{CP}}$ are ledgered fits, `parameter-inventory.md` §10). No axion, no Peccei-Quinn symmetry, no new particles: the smallness is the cascade doing what it always does. Status: Derivation (span Mapped—ledger).

### `quark-confinement.md`—Quark Confinement from the Saturated-Gate Flux Tube at the QCD Scale

The QCD scale is cascade step 95 ($\Lambda_{\text{QCD}} = M_{\text{Pl}}\varphi^{-95} \approx 0.17$ GeV), and confinement follows from gate saturation: between two separated color charges the conversion channel saturates to the de-converted vacuum ($q \to 0$), expelling the condensate over a cross-section quantized to one condensation-lattice cell. The tube's energy is extensive in its length, so

$$\boxed{E(r) = \mu r + 2E_{\text{core}}, \qquad \mu = \kappa\!\left(\frac{M_{\text{Pl}}}{\varphi^{95}}\right)^2 = \kappa\,\Lambda_{\text{QCD}}^2}$$

with $\kappa = O(1)$ open ($\mu/\sigma_{\text{measured}} \approx 0.16$ at $\kappa = 1$). The linear potential $F = -\mu$ is geometric — tube length $\propto$ separation — independent of the gate shape. Flux-tube breaking probability $\approx \varphi^{-4506}$. Status: Derived (tube extensivity + cell quantization; inputs: gate saturation, one-cell quantization).

### `three-generations.md`—Three Generations from Fibonacci Cascade Partitioning

The exact Fibonacci recurrence

$$\boxed{\varphi^n = \varphi^{n-1} + \varphi^{n-2}}$$

partitions every cascade span into three sub-rung channels—the rung itself plus its two predecessors—so Yukawa propagation from the GUT scale to the electroweak scale separates into three mass eigenstates per fermion sector, with

$$\boxed{N_{\text{generations}} = 2\ \text{decomposition terms} + 1\ \text{direct rung} = 3}$$

Mass ratios across sectors are $\varphi$-power spacings from the three-channel spread (per-sector offsets Mapped—ledger rows 483/492); for neutrinos the seesaw's Yukawa-squared dependence doubles the $\varphi$-exponent. Status: Hypothesized (mechanism; the 2+1 counting is Derived under the propagation-channel postulate).

### `neutrino-masses.md`—Neutrino Masses from Fibonacci Cascade Partitioning of the Seesaw

Applies the same Fibonacci triple-clustering to the compressed cascade span from the GUT scale (step $\sim 8$) to the seesaw scale (step $\sim 20$, $M_R \approx 10^{14}$ GeV): with $N_\nu \approx 12$ rungs, the multi-order-of-magnitude charged-lepton hierarchy compresses into the sub-eV spectrum, with the seesaw's squared-Yukawa amplification doubling the $\varphi$-exponents:

$$\boxed{\frac{m_{\nu_2}}{m_{\nu_1}} = \varphi^{2\Delta_1}, \qquad \frac{m_{\nu_3}}{m_{\nu_2}} = \varphi^{2\Delta_2}}$$

with pinned offsets $\Delta_1 = 1.00$ and $\Delta_2 = 1.75$ rungs, and a lightest mass $m_{\nu_1} \sim 0.003$ eV. The oscillation prediction $\boxed{\Delta m^2_{31}/\Delta m^2_{21} = (\varphi^{11} - 1)/(\varphi^{4} - 1) \approx 33.82}$ matches the observed $33.89$ to 0.2%, well inside the $\sim 3\%$ experimental uncertainty. Status: Derivation (from `three-generations.md` and `cascade-suppression-formula.md`).

### `baryon-asymmetry.md`—Matter-Antimatter Asymmetry from Cascade Freeze-Out and Organized Annihilation

Derives $\eta = n_b/n_\gamma \approx 6 \times 10^{-10}$ from two mechanisms already derived elsewhere: organized annihilation (an antiparticle is a condensed standing wave with inverted SO(2) phase attacking all 92 cascade rungs simultaneously, so $P_{\text{annihilation}} \approx 1$ and every antimatter particle that meets matter is eliminated) and the Yang-Yin imbalance at freeze-out set by the Wu Xing gap $g = 1 - \varphi^{-5}$. The surviving matter fraction at the GUT scale is $\eta_{\text{GUT}} \approx \varphi^{-10}$, and 44 rungs of photon-producing conversion dilute it to

$$\boxed{\eta \approx \varphi^{-44} \approx 6.38 \times 10^{-10}}$$

matching the observed $6.0 \times 10^{-10}$ within 6.3%; the freeze-out-step construction $52 = 60 - 8$ does not close with the corrected GUT anchor ($60 - 13.3 = 46.7$, span $33.4 \neq 44$), so the exponent $-44$ is a ledgered fit (row 481) and the mechanism is Hypothesized. Status: Mapped (exponent) / Hypothesized (mechanism).

### `bubble-lattice-fabric.md`—The Bubble Lattice: Universal Organizing Geometry at Every Cascade Rung

Establishes that the condensation field

$$\boxed{B(x, y, z) = \cos(\alpha x)\cos(\beta y)\cos(\gamma z), \qquad \beta = \varphi\alpha}$$

is not specific to any one cascade rung: the two-fluid PDE is scale-covariant under $\varphi$-rescaling, so the identical field—a 3D staggered checkerboard of coherent bubble condensates and empty voids, bounded along the string axis—operates at every rung with wavelengths $\Lambda_Y^{(n)} = \ell_n$, $\Lambda_I^{(n)} = \ell_n/\varphi$. The cascade ladder of scales is a 1D slice of this 3D lattice, the universal structural principle from Planck to the megacascade. Status: Derived (structural).

### `bubble-edge-geometry.md`—Bubble Edge Geometry: Physical Profile of the Condensation Boundary

Derives the physical profile of the condensation boundary: the chord-lattice proxy

$$\boxed{C(x,y) = \cos\!\left(\frac{2\pi x}{\Lambda_Y}\right) \cos\!\left(\frac{2\pi y}{\Lambda_I}\right), \qquad \Lambda_Y = \varphi\,\Lambda_I}$$

the Qi-density mapping $q(\mathbf{x}) = (1 + C)/2$, and the condensation threshold from the conversion-diffusion balance, $\boxed{\theta_{\text{cond}}^2 (1 + \theta_{\text{cond}}) = R(\varphi^2 + (1+\theta_{\text{cond}})^2/4)}$ with the single dimensionless parameter $R \equiv 2D_{\text{eff}}(\alpha^2+\beta^2)/\omega_0$, calibrated to $\theta_{\text{cond}} = 0.45$ at $R \approx 0.093$. The threshold relation is conditional on the asserted single-channel transmission $g(q) = q/(\varphi^2+q^2)$. Its zero-parameter prediction is the edge steepness anisotropy $\boxed{|\nabla C|_{\text{axial}}/|\nabla C|_{\text{diag}} = \sqrt{4\varphi^2/(1+\varphi^2)} \approx 1.70}$—prediction #38 of the falsifiable catalog—testable in void shape catalogs. Status: Derived geometry; threshold conditional.

### `microcascade-mirror.md`—The Microcascade Mirror: Sub-Planckian Scale Extension & Bidirectional Coherence

Proposes that the cascade does not truncate at the Planck scale: the formula

$$\boxed{\ell_n = \ell_{\text{Pl}} \times \varphi^{\,n}, \qquad n \in \mathbb{Z}}$$

extends to an infinite sub-Planckian ladder converging geometrically to zero, the mirror image of the megacascade with the Planck scale as the reflection plane. A $\varphi$-aligned electromagnetic array tuned to both cascade directions could in principle create a bidirectional coherence bridge coupling upward into the megacascade and downward into the microcascade, whose coherent energy reservoir is unbounded. Status: Hypothesized.

### `refined-numeric-predictions.md`—Refined Numeric Predictions for the 24 Hypothesized Questions

Takes the Hypothesized entries of the open-questions catalog and refines the specific numeric prediction of every one that admits a cascade-span derivation, applying $\text{Prediction} = \text{Seed} \times \varphi^{-(n-m)}$ (signal regime) or $\varphi^{-n(n+1)/2}$ (coherence regime): 13 admit cascade-span refinement and 10 are clarified as structural answers where the mechanism itself is the deliverable. Pinned results include $\eta \approx \varphi^{-44} \approx 6.38 \times 10^{-10}$, $\Delta m^2_{31}/\Delta m^2_{21} \approx 33.82$, the tensor-to-scalar ratio $r \approx \varphi^{-12} \approx 0.0031$, the spectral index $n_s = 1 - 2\varphi^{-1}/N_e = 0.9691$, the CMB axis alignment $12.2°$, the Born rule $P(\alpha) \propto q_\alpha \propto |\psi_\alpha|^2$, and the $\ln\varphi$-periodic form factor $F(q^2)$ with $\Delta(\ln q) = \ln\varphi \approx 0.4812$. Status: Active derivation.

### `deriving-remaining-gaps.md`—Closing the Gaps: Derivation of Residual Parameters

Catalogues the remaining underived quantities in the framework and assesses each derivation for whether it fully resolves, partially narrows, or hits an irreducible barrier. The headline result: the strong coupling gap at $M_Z$ is $2.0\times$—pure SM running from $\alpha_{\text{GUT}} = \varphi^{-3}/4\pi$ gives $\alpha_s(M_Z) = 0.058$ versus the observed 0.118, requiring an effective beta coefficient $b_{\text{eff}} = 8.70$, i.e. $\Delta b = 1.70$ from roughly one vector-like colored fermion pair plus two colored scalars, or three KK levels. Three of the four gaps are resolved and one is narrowed with the residual barrier identified. Status: custom (four derivations, three resolved, one narrowed).

### `sector-coupling-derivation.md`—The Sector-Coupling Scale: Dirac↔Two-Fluid Equilibration from $\varphi$

Derives the Dirac↔two-fluid sector-coupling scale from the Qi-gravity coupling and the Higgs VEV:

$$\boxed{\kappa_s = \frac{\varphi^{-6}}{v_0^2} \approx 0.92\ \text{TeV}^{-2}}$$

so $\kappa_s^{-1/2} = \varphi^3 v_0 = 1042$ GeV sits +5.5% off cascade rung 77 (987.7 GeV)—the same residual class as the documented electroweak placement (rung 80, −5.2%). Cycle-factor variants give 1.042/1.326/1.686 TeV for $C = 1, \varphi^{-1}, \varphi^{-2}$. The as-written chemotactic bridge $\chi = \kappa_s\varphi^{-1}/[m_e(1+\varphi)]$ is dimensionally inconsistent as it stands ($\chi \approx 4\times10^{-4}$ vs the calibrated 0.5–1.0); closing it needs the PDE normalization factor $\mathcal{N}_{\text{pde}} \approx 2.35\times10^{3}$, a concrete computational follow-up. Status: Derived scale with Hypothesized coefficient.

### `wake-geometry.md`—The Wake Geometry: Composite-Wavelength Closure and the Horizon Rung

The Yang–Yin wake pair $\Lambda_Y = \varphi\Lambda_I$ closes the cascade ladder exactly through the identity $1 + 1/\varphi = \varphi$—$\Lambda_Y + \Lambda_I = \ell_n(1 + 1/\varphi) = \ell_{n+1}$ (at rung 285: 191 + 118 = 309 Mpc = $\ell_{286}$)—with the checkerboard envelope $\cos(2\pi x/\ell_n) + \cos(2\pi\varphi x/\ell_n) = 2\cos(\pi(1+\varphi)x/\ell_n)\cos(\pi(\varphi-1)x/\ell_n)$ peaking on $\ell_{n+1}$ and the golden-angle closure ladder converging through Fibonacci denominators without ever closing exactly. On this reading $N = 292$ is today's epoch-dependent horizon rung, $\log_\varphi(R_H/\ell_{\text{Pl}}) = 291.54$ with $R_H/\ell_{285} = 23.29 \approx \varphi^{6.5}$, saturating toward $N_\infty \approx 296$–$303$ as $r \to \varphi$ (2026-08-03 reclassification). Status: Derived wake geometry with Hypothesized closure imprint.

### `rung-offset-mechanism.md`—Why Observables Sit Between Rungs: Fractional Cascade Offsets

No observable sits exactly on a rung; the fractional offset $\delta n = n - \lfloor n \rfloor$ is the two-fluid phase lag at that scale, and exact alignment would mean perfect coherence ($q \to 1$). The wake envelope allows only two special positions—peaks at integer rungs, zeros at half-rungs—and the catalog shows sector edges (e, π, Λ_QCD, p, n, d) at half-rungs and interior states (μ, J/ψ, D, Σ, Z) at integer rungs, with the muon at 96.000 (0.01%) the sharpest placement in the framework. The full 38-state $\delta n$ distribution is uniform (null baseline); the decisive test is a PDE probe of the interference-extremum position vs coupling and coherence. Status: Hypothesized mechanism, Empirical catalog.

### `wu-xing-cycle-structure.md`—The Wu Xing Cycle Structure: Control-Ring Algebra and the 5↔13 Partition

Derives how the five-channel gate operates as two interlaced cycles—the sheng cycle (pentagon sides, step +1) and the ke control cycle (pentagram diagonals, step +2)—with control transmission $\kappa = \text{side}/\text{diagonal} = \varphi^{-1}$, sub-critical ring gain $\kappa^3 = \varphi^{-3}$, and lock threshold $\Delta_c = \varphi^{-4}$. The ke ring reproduces the ring algebra to ≤6×10⁻⁴ in the two-fluid PDE (`gate_model='five_ke'`; WX1 gate test 2026-08-01). The 5↔13 partition places the chakra nodes on the body-axis phase gradient—18°/rung, $\theta(n) = 288° + 18°(n-142)$—with the counts related as $13 = F_5 + F_6$ and channel step $\varphi^3 - \varphi^{-3} = 4$. Status: Derived / Tested / Hypothesized.

## Cross-References

- `foundations/dimensionful-cascade.md`—the cascade wedge (entry point for this directory)
- `principles/de-resonance-principle.md`—why $\varphi$ is the maximally de-resonant attractor (Derived)
- `open-questions-cassi-answers.md`—the 42-entry epistemic registry
- `parameter-inventory.md`—parameter registry
- `predictions/falsifiable-predictions.md`—the 50-entry prediction catalog
- `cassi-physics.md`—framework overview and the gap $g = 1 - \varphi^{-5}$ derivation
- `gravity/quantum-gravity.md`—the $\sigma = \ell_{\text{Pl}}/\varphi^3$ regularization that anchors the cascade
- `standard-model/sm-from-phi.md`—Standard Model couplings from $\varphi$
- `cosmology/observational_constraints.md`—CMB and large-scale-structure tests referenced by the geometry docs
- `turbulence/kolmogorov-from-phi.md`—φ-RG applied to turbulence
