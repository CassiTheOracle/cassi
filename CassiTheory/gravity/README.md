# Gravity—Quantum Gravity and Analytical Three-Body Results

## Status: Index—September 2026

## Abstract

This directory develops a $\sigma$-regularized free-propagator candidate and
the point-particle reduction of the optional Qi-weighted force law.
`quantum-gravity.md` separates the Derived-conditional regulator identities
from the Hypothesized interacting quantization and composite excitation.
`three-body-analytical.md` derives well-separated-blob ODEs under the displayed
PDE force convention. The canonical $+\nabla\Phi$ branch with
$\Phi=-G\sum_iM_i/|\mathbf{x}-\mathbf{X}_i|$ gives outward acceleration for
positive $\alpha_j$; an attractive or metric branch requires a separate
Hypothesized closure. The internal coupling-magnitude coefficient varies with
blob state and density, but a body-dependent physical response requires a
matter-state map. `foundations/quantum-free-fall-correspondence.md` supplies
the low-energy matter-wave boundary. Read the free-propagator analysis, the
reduction assessment, and then that correspondence boundary.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `quantum-gravity.md` | Quantum gravity | Derived conditional / Hypothesized |
| 2 | `three-body-analytical.md` | Celestial mechanics | Derived (reduction) / Hypothesized (attractive branch) |

## Document Summaries

### `quantum-gravity.md`—$\sigma$-Regularized Two-Fluid Quantum Gravity

The candidate uses
$\sigma=\ell_{\text{Pl}}/\varphi^3$ as a Gaussian factor in a free Euclidean
propagator. The Hypothesized composite sector uses
$\omega_k^2=k^2+\omega_0^2(1-e^{-k^2\sigma^2})$ with
$\omega_0=M_{\text{Pl}}$. Its low-$k$ speed ratio
$\sqrt{1+\varphi^{-6}}\approx1.0275$ is rejected as an observed
astrophysical-graviton dispersion by GW170817
([arXiv:1710.05834](https://arxiv.org/abs/1710.05834)); at high $k$ the
dispersion approaches $\omega\sim k$ and supplies no energy cap. The Gaussian
makes the displayed radial Euclidean one-loop prototype UV convergent for a
declared nonzero infrared cutoff. It does not establish all-order finiteness,
renormalizability, Lorentzian unitarity, black-hole information retention, or
a Page curve because the interacting vertices, contour prescription, and
covariant horizon solution remain open. The composite-graviton identification
and curved-spacetime predictions remain Hypothesized.
Under the standard unsubtracted positive scalar spectral interpretation,
the nonzero-$\sigma$ Gaussian is excluded: $xG_E(x)$ decreases, whereas
every nonnegative spectral measure makes it nondecreasing (§3.1).
The exact kernel identity, sign and $\sigma=0$ control pass QFC4 and an
independent calculation. A gauge-fixed auxiliary or regulator-only
interpretation needs separately qualified physical observables; the result
is not a general interacting-unitarity theorem.

### `three-body-analytical.md`—The Three-Body Problem in Two-Fluid Gravity

Reduces the dimensionless Cassi two-fluid PDE, with solver normalization
$\rho_\star=1$, to point-particle ODEs for well-separated Gaussian blobs.
Physical-density variables restore
$q=\rho^2/(\rho^2+\varphi^{-2}\rho_\star^2+\varepsilon^2)$. The boxed
equation has the state-dependent internal coefficient
$\alpha_j[1+(\varphi^6-1)q_j]G$ and evolving mass and signed Yang-imbalance
$\alpha_j=\Pi_j/M_j$. At the reference-density point on the composition line,
$q_j\approx0.873$ and the coefficient magnitude is about $3.73G$; at the
dilute endpoint it approaches $0.236G$. These are formal state-space values,
not measured Newton constants or body-response ratios. The displayed
$+\nabla\Phi$ convention is outward for positive $\alpha_j$. The algebraic
reduction, fixed-point proof, and 24-dimensional phase-space count are
Derived; a physical attractive or metric branch and matter-state map remain
Hypothesized.

## Cross-References

- `predictions/falsifiable-predictions.md`—the 56-entry prediction catalog; the optional gravity extension's GW-speed branch is undetermined without a covariant wave equation, its breathing-mode entry is Hypothesized, and the implemented low-$k$ dispersion is rejected by the GW170817 speed bound in `audit.md` §3
- `foundations/quantum-free-fall-correspondence.md`—conditional phase and source/test separation; physical-$q$ bounds and information loss; forty-three material, gravity, clock, apparatus and interacting-quantum closure requirements; independent QFC1–QFC4 receipts
- `open-questions-cassi-answers.md`—the 42-entry epistemic registry (quantum-gravity cites G2, the Page curve question)
- `foundations/cassi-first-principles.md`—first-principles foundation for the two-fluid quantization
- `foundations/dimensionful-cascade.md`—the cascade ladder that anchors the dimensionful cascade and the $\sigma$ separation scale
- `foundations/cascade-suppression-formula.md`—per-rung coherence $q_i = 1 - \varphi^{-i-\delta}$ used for the black-hole capacity bound
- `foundations/dimensionful-constants-status.md`—where quantum-gravity routes the remaining gaps ($\lambda$, $c$, $\hbar$, $G$)
- `foundations/bubble-lattice-fabric.md`—the bubble/void checkerboard that becomes the $\sigma$-regularized harmonic regime
- `foundations/unified-lagrangian.md`—source of the curved-background two-fluid Lagrangian for the Page-curve program
