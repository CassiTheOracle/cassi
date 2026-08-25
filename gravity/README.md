# Gravity—Quantum Gravity and Analytical Three-Body Results

## Status: Index—August 2026

## Abstract

This directory takes the Cassi two-fluid framework to the gravitational extremes: proposing a Hypothesized UV-finite quantization of the two-fluid and asking whether the Qi-enhanced two-fluid gravity PDE admits a useful point-particle reduction. `quantum-gravity.md` develops the Hypothesized two-fluid quantization on top of the Derived-conditional $\sigma$-regularized classical layer; `three-body-analytical.md` derives the well-separated-blob ODEs under the displayed PDE force convention. Its canonical $+\nabla\Phi$ branch with $\Phi = -G\sum_i M_i/|\mathbf{x}-\mathbf{X}_i|$ gives outward acceleration for positive $\alpha_j$; an attractive/orbital branch is a separate Hypothesized sign-changing extension. At the $\varphi$-fixed point the coupling remains body- and density-dependent, while the dilute-limit coupling magnitude is $\varphi^{-3}G$ with the same outward sign. The algebraic reduction and fixed-point identities are Derived; the attractive branch is Hypothesized. Read in alphabetical order: the pillar first, then its analytical assessment.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `quantum-gravity.md` | Quantum gravity | Derived conditional / Hypothesized |
| 2 | `three-body-analytical.md` | Celestial mechanics | Derived (reduction) / Hypothesized (attractive branch) |

## Document Summaries

### `quantum-gravity.md`—$\sigma$-Regularized Two-Fluid Quantum Gravity

Quantizes the two real Yang/Yin density components with the fundamental separation scale $\boxed{\sigma = \ell_{\text{Pl}}/\varphi^3 \approx 1.93\times 10^{-20}\ \text{GeV}^{-1} \approx 3.82\times 10^{-36}\ \text{m}}$ as a Gaussian regulator in the propagator. The Hypothesized quantized composite sector may use an optional SO(2) extension, separate from the canonical real-density PDE; its implemented probe uses $\omega_k^2 = k^2 + \omega_0^2(1-e^{-k^2\sigma^2})$ with $\omega_0 = M_{\text{Pl}}$, so $1/\sigma = \varphi^3M_{\text{Pl}}$ is a suppression scale rather than a hard mode-energy cutoff. At $k \ll 1/\sigma$, $\omega/k \to \sqrt{1+\varphi^{-6}} \approx 1.0275$; at $k=1/\sigma$, $\omega \approx 4.31\,M_{\text{Pl}}$ and $c_{\text{eff}}\approx 1.0030$; at $k \gg 1/\sigma$, $\omega\sim k$ with Gaussian amplitude suppression and no energy cap. **GW170817 rejection:** the low-$k$ group speed $c_{\text{eff}}/c\to\sqrt{1+\varphi^{-6}}\approx1.0275$ exceeds the Abbott et al. upper bound $+7\times10^{-16}$ by $>3.9\times10^{13}$, so this dispersion is rejected as an astrophysical graviton signal; it is viable only if modified to recover $c$ or decoupled from observed GWs. For the displayed Gaussian propagator, loop integrals are UV-finite at all orders once an IR cutoff $q_{\text{IR}}>0$ is supplied; the quantized interaction and its IR completion remain unspecified, so the no-renormalization statement is conditional. The probe reports an illustrative approximately 11% correction to $G$ at the $\sigma$ scale. For black holes, the Hypothesized $\sigma$-regulated S-matrix mechanism is intended to preserve unitarity; it derives an interior coherence capacity $\mathcal{C}_{\text{BH}}\sim\varphi^{N_{\text{BH}}+1}\sim M/M_{\text{Pl}}$, with the Bekenstein-Hawking correspondence still open, while the full Page curve and horizon-level demonstration await a curved-spacetime two-fluid PDE solver. Epistemic tier: Hypothesized—the quantized sector, curved-spacetime predictions, and headline observational signatures remain untested.

### `three-body-analytical.md`—The Three-Body Problem in Two-Fluid Gravity

Reduces the Cassi two-fluid PDE (continuity, momentum, Poisson, and the Qi gate with canonical variables $\rho=E_Y+E_I$, $\varepsilon=E_Y-\varphi E_I$, $\pi=E_Y-E_I$, and $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$) to point-particle ODEs for well-separated Gaussian blobs, with the boxed equation of motion $\boxed{\ddot{\mathbf{X}}_j=+G\,\alpha_j(1+(\varphi^6-1)q_j)\sum_{i\neq j}M_i(\mathbf{X}_j-\mathbf{X}_i)/|\mathbf{X}_j-\mathbf{X}_i|^3}$ and mass and signed Yang-imbalance $\alpha_j=\Pi_j/M_j$ as dynamical variables. Here the displayed $+\nabla\Phi$ convention is outward for positive $\alpha_j$. At the $\varphi$-fixed point $\alpha_j=\varphi^{-3}$, each blob carries equilibrium coherence $q_j=q_{\text{eq}}(\rho_j)=\rho_j^2/(\rho_j^2+\varphi^{-2})$ (approximately 0.873 at the reference density), giving $G_{\text{eff},j}=\varphi^{-3}(1+(\varphi^6-1)q_{\text{eq}}(\rho_j))G\approx3.73\,G$; in the dilute fixed point $(\rho_j\to0,\ q_j\to0)$ the coupling magnitude is $\varphi^{-3}G\approx0.236\,G$, but its sign remains outward. The algebraic reduction, fixed-point proof, and 24-dimensional phase-space count are Derived; attractive/orbital dynamics require a separate Hypothesized sign-changing force extension.

## Cross-References

- `predictions/falsifiable-predictions.md`—the 56-entry prediction catalog; the optional gravity extension's GW-speed entry is now undetermined (no covariant wave equation) and its breathing-mode entry is Hypothesized (requires metric-perturbation derivation), while the historical GW170817 probe is recorded as rejected in `audit.md` §3
- `open-questions-cassi-answers.md`—the 42-entry epistemic registry (quantum-gravity cites G2, the Page curve question)
- `foundations/cassi-first-principles.md`—first-principles foundation for the two-fluid quantization
- `foundations/dimensionful-cascade.md`—the cascade ladder that anchors the dimensionful cascade and the $\sigma$ separation scale
- `foundations/cascade-suppression-formula.md`—per-rung coherence $q_i = 1 - \varphi^{-i-\delta}$ used for the black-hole capacity bound
- `foundations/dimensionful-constants-status.md`—where quantum-gravity routes the remaining gaps ($\lambda$, $c$, $\hbar$, $G$)
- `foundations/bubble-lattice-fabric.md`—the bubble/void checkerboard that becomes the $\sigma$-regularized harmonic regime
- `foundations/unified-lagrangian.md`—source of the curved-background two-fluid Lagrangian for the Page-curve program
