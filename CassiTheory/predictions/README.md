# Predictions—The Falsifiable Catalog and Framework Glossary

## Status: Index—July 2026

## Abstract

This directory holds the two master registries of the Cassi framework: the 54-entry catalog of falsifiable predictions with per-entry input accounting and epistemic status, grouped by experimental frontier, and the glossary's 15 core sections of framework symbols and definitions plus its Epistemic Tiers section. `cassi_definitions.md` is where a new reader learns what $E_Y$, $E_I$, $q$, $\xi = \varphi^6$, and the $\varphi$-attractor mean; `falsifiable-predictions.md` is where every quantitative claim of the framework is listed with its test, current status, and detection timeline. Ordered alphabetically, which is also the natural reading path: glossary first, catalog second.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `cassi_definitions.md` | Framework glossary | Reference |
| 2 | `falsifiable-predictions.md` | Falsifiable prediction catalog | Reference |

## Document Summaries

### `cassi_definitions.md`—Cassi Framework: Definitions

The framework's compact reference glossary, organized into 15 core sections from Fundamentals through Unification to Code & Implementation, followed by Epistemic Tiers. It treats $E_Y,E_I\ge0$ as the canonical nonnegative Yang/Yin square densities; when an amplitude coordinate is useful, the exact positive-root coordinate lift $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ supplies amplitude-plane diagnostics without independent signs or a compact-phase identification. Spatial motion is supplied by the shared advection field and any named potential-relative drift. The labels expansive/radiative and contractive/absorptive remain phenomenological or coordinate mnemonics.

The canonical coherence is $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon_{\mathrm{eff}}^2)$ with $\rho=E_Y+E_I$ and $\varepsilon=E_Y-\varphi E_I$; the rational form and bare $\varphi^{-2}$ floor are a **C / Asserted** constitutive definition in dimensionless/reference-normalized solver variables, while the bounds and stated reference value are **Derived conditional** on that definition and normalization. If $E_Y,E_I$ denote physical energy densities, an external reference density $\rho_*$ is required, equivalently $\tilde\rho=\rho/\rho_*$ and $\tilde\varepsilon_{\mathrm{eff}}=\varepsilon_{\mathrm{eff}}/\rho_*$; no $\rho_*$ scale is derived or counted. By default $\varepsilon_{\mathrm{eff}}^2=\varepsilon^2$, while the optional `qi_memory` switch uses $\bar{\varepsilon}^2$. A change of density units must rescale the reference term consistently; otherwise the numerical value of $q$ changes. The glossary distinguishes $\theta_\Psi$, $\theta_d$, and $\Theta_S=2\theta_\Psi\pmod{2\pi}$. $J_\Psi$ is the foundational amplitude-plane spatial current (field$^2$/length), while $J_d$ is the density-plane diagnostic (density$^2$/length); a named projection does not by itself create transport between cascade rungs or scales. |

Canonical conversion is a rank-one density-plane relaxation that conserves $\rho$, with eigenvalues $0$ and $-\lambda(1-q)(1+\varphi)$, rather than an $SO(2)$ rotation. The named C-class/framework convention $\lambda=0.1$ is an asserted inverse-time normalization/timescale; the implementation class default is $\lambda=0.02$. The relation $\lambda=1/(2w)$ is a Hypothesized Wu Xing linkage. The map $\delta n_{\mathrm{map}}=\Delta\theta_d/(2\pi)$ and any fixed per-rung phase or pitch are Hypothesized coordinate/geometric assignments. Four directional populations are a conditional kinetic extension after choosing an oriented axis, not a canonical four-field adoption or an extra spacetime dimension; $g(q)=q/(\varphi^2+q^2)$ remains an asserted single-channel transmission input.

### `falsifiable-predictions.md`—Cassi Falsifiable Predictions

The framework's central quantitative catalog: 54 numbered predictions with per-entry input accounting and epistemic status. Some are parameter-free structural consequences of $\varphi = (1+\sqrt{5})/2$ and the two-fluid PDE; others are conditional on stated conventions or inputs, Mapped or Calibrated to data, or Hypothesized mechanisms, including the asserted C-class/framework normalization $\lambda=0.1$ where named calculations select it (the implementation class default is $\lambda=0.02$). The predictions are grouped by experimental frontier (FCC-ee electroweak, CMB-S4/LiteBIRD primordial cosmology, cosmic surveys, gravity, collider and decay physics, chakra biophysics, and a universal scale-invariant edge-steepness prediction). The headline tests include $m_W/m_Z = 0.878$ (0.36% below the SM after the $\rho$ radiative correction), $\Delta(\ln k)=\ln\varphi\approx0.4812$ log-periodic $P(k)$, a $1.70\times$ edge anisotropy at any condensate boundary, the $\varphi^2$ inter-node spacing ratio of the chakra lattice, and the dark-energy equation of state ($w_0\approx-0.87$, $w_a\approx+0.012$).

## Cross-References

- `open-questions-cassi-answers.md`—the 42-entry epistemic registry
- `parameter-inventory.md`—parameter registry
- `audit.md`—prediction vs experiment audit with margins of error
- `standard-model/sm-from-phi.md`—SM couplings from $\varphi$ (cited by §1)
- `cosmology/cosmology-from-phi.md`—inflation, baryogenesis, dark matter from $\varphi$ (cited by §2)
- `foundations/xi-derivation.md`—first-principles derivation of $\xi = \varphi^6$
- `foundations/bubble-lattice-fabric.md`—the condensation lattice behind §8's boundary anisotropy
