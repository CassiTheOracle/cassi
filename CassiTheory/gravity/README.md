# Gravity—Quantum Gravity and Analytical Three-Body Results

## Status: Index—July 2026

## Abstract

This directory takes the Cassi two-fluid framework to the gravitational extremes: quantizing the two-fluid itself as a UV-finite theory of quantum gravity, and asking whether the Qi-enhanced two-fluid gravity PDE makes the classical three-body problem analytically tractable. `quantum-gravity.md` builds the 4th pillar (composite graviton, no renormalization); `three-body-analytical.md` performs the point-particle reduction and finds that the theory reduces to—but does not improve on—Newtonian gravity at its $\varphi$-fixed point. Read in alphabetical order: the pillar first, then its analytical assessment.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `quantum-gravity.md` | Quantum gravity | Hypothesized |
| 2 | `three-body-analytical.md` | Celestial mechanics | Derived |

## Document Summaries

### `quantum-gravity.md`—$\sigma$-Regularized Two-Fluid Quantum Gravity

Quantizes the paired-real Yang/Yin fields with the fundamental length $\sigma = 1/M_{\text{Pl}}$ as a Gaussian regulator in the propagator, $\boxed{\sigma = 1/M_{\text{Pl}} \approx 8.2\times 10^{-20}\ \text{GeV}^{-1} \approx 1.6\times 10^{-35}\ \text{m}}$. The graviton is a composite SO(2) excitation with modified dispersion $\omega^2 = k^2 e^{k^2\sigma^2/2} + M_{\text{Pl}}^2(1 - e^{-k^2\sigma^2/2})$, which asymptotes to $M_{\text{Pl}}$ so no trans-Planckian modes exist and every loop diagram is UV-finite—Newton's constant runs by less than 1% at the Planck scale and no renormalization is ever needed. On black holes it proves S-matrix unitarity and derives an interior coherence capacity $\mathcal{C}_{\text{BH}} \sim \varphi^{N_{\text{BH}}+1} \sim M^2/M_{\text{Pl}}^2$ consistent with Bekenstein-Hawking entropy, while the Page curve itself awaits a curved-spacetime two-fluid PDE solver that does not yet exist. Epistemic tier: Hypothesized—the mechanism is established, but the headline predictions (breathing graviton mode, $\sigma$-softened singularity) are untested.

### `three-body-analytical.md`—The Three-Body Problem in Two-Fluid Gravity

Reduces the Cassi two-fluid PDE (continuity, momentum, Poisson, and the Qi gate with canonical coherence $q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$) to point-particle ODEs for well-separated Gaussian blobs, with the boxed equation of motion $\boxed{\ddot{\mathbf{X}}_j = -G\,\alpha_{0,j}\,(1+(\varphi^{6}-1)q_j)\sum_{i\neq j} M_i\,(\mathbf{X}_j-\mathbf{X}_i)/|\mathbf{X}_j-\mathbf{X}_i|^3}$ and mass and Yang fraction as dynamical variables. At the $\varphi$-fixed point $\alpha_{0,j} = \varphi^{-3}$ (classical-limit $q \to 0$, per `foundations/cassi-theory-reference.md` §2.6) the Qi enhancement vanishes and the system reduces exactly to Newtonian gravity with $G_{\text{eff}} = \varphi^{-3}G \approx 0.236\,G$—so the Cassi framework does **not** make the three-body problem integrable. What is new: a body-dependent effective gravitational constant off the fixed point, mass redistribution via Yang/Yin conversion and chemotaxis, and a global $\varphi$-attractor manifold that exponentially drives every configuration to Newtonian dynamics while preferring resonant orbits. Epistemic tier: Derived—the reduction, fixed-point proof, and 24-dimensional phase-space count are analytic.

## Cross-References

- `predictions/falsifiable-predictions.md`—the 49-entry prediction catalog (quantum-gravity's falsifiable table: graviton breathing mode, GW dispersion near $M_{\text{Pl}}$, no singularity)
- `open-questions-cassi-answers.md`—the 42-entry epistemic registry (quantum-gravity cites G2, the Page curve question)
- `foundations/cassi-first-principles.md`—first-principles foundation for the two-fluid quantization
- `foundations/dimensionful-cascade.md`—the cascade ladder that anchors $\sigma = 1/M_{\text{Pl}}$ dimensionfully
- `foundations/cascade-suppression-formula.md`—per-rung coherence $q_i = 1 - \varphi^{-i-\delta}$ used for the black-hole capacity bound
- `foundations/dimensionful-constants-status.md`—where quantum-gravity routes the remaining gaps ($\lambda$, $c$, $\hbar$, $G$)
- `foundations/bubble-lattice-fabric.md`—the bubble/void checkerboard that becomes the $\sigma$-regularized harmonic regime
- `foundations/unified-lagrangian.md`—source of the curved-background two-fluid Lagrangian for the Page-curve program
