# Standard Model—Couplings, Gauge Structure, and CP from φ

## Status: Index—July 2026

## Abstract

Six documents cover the Standard Model's gauge structure, couplings, loop corrections, and flavor sector through the Cassi $\varphi$-fixed point. The isospinor field $\Psi = (\psi_Y, \psi_I)^T$ with equilibrium ratio $\varphi$ fixes the symmetry-breaking chain and supplies the fixed-point imbalance used in the asserted Weinberg boundary; the coupling-normalization mechanism remains Hypothesized. Read `sm-from-phi.md` for the breaking chain, `su2-gauge-extension.md` for the gauge mechanics and closure audit, `sm-radiative-corrections.md` for running, `gut-embedding.md` for unification, and the flavor-sector documents for CP and neutrino masses.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `sm-from-phi.md` | Electroweak breaking, gauge structure, fermion masses | Derived chain; Weinberg boundary asserted |
| 2 | `su2-gauge-extension.md` | Gauge extension of the two-fluid | Derived algebra; coupling boundary asserted |
| 3 | `gut-embedding.md` | SU(5) / SO(10) unification, proton decay | Hypothesized |
| 4 | `cp-violation.md` | CKM phase, Jarlskog invariant, strong CP | Derived |
| 5 | `neutrino-mass.md` | Seesaw scale, neutrino masses | Hypothesized |
| 6 | `sm-radiative-corrections.md` | Loop corrections: RGE, Δα, Δr, m_W, λ | Derived |

## Document Summaries

### `sm-from-phi.md`—Standard Model from φ

The entry point for the directory: it derives the gauge structure $\mathrm{SU}(3)_C \times \mathrm{SU}(2)_L \times \mathrm{U}(1)_Y$ from successive truncations of the continued-fraction expansion of $\varphi$, and records $\sin^2\theta_W = \varphi^{-3} \approx 0.236$ as the fixed-point boundary value. The curvature–orbit normalization attempt and its action-level blocker are in `su2-gauge-extension.md` §3.2.1. The Higgs mechanism gives $m_W/m_Z = \sqrt{1-\varphi^{-3}} \approx 0.874$ before the $\rho$ correction; quark confinement follows from the Qi coherence threshold, and the CKM and Yukawa sectors are documented below.

### `su2-gauge-extension.md`—SU(2) × U(1) Gauge Extension of the Cassi Two-Fluid

Takes the two-fluid's internal $\mathrm{U}(1) \cong \mathrm{SO}(2)$ Yang/Yin rotation and promotes it to an SU(2) isospinor doublet with $\langle\Psi\rangle \propto (\sqrt{\varphi},1)^T$. It derives the neutral mass matrix and records the exact identity $\sin^2\theta_W = \varphi^{-3} \iff (g/g')^2 = 2\varphi$ as an asserted boundary; §3.2.1 tests a curvature–orbit candidate and finds the missing metric and orbit-matching rule. Running and measured-scale comparisons are in `sm-radiative-corrections.md`.

### `sm-radiative-corrections.md`—Standard Model Radiative Corrections from the φ-Boundary

Derives the complete one-loop (plus leading two-loop) radiative-correction program that carries the φ-anchored GUT boundary to the Z-pole: gauge-coupling running with thresholds, the running of $\alpha$ ($\bar\alpha^{-1}(m_Z) = 128.95$ from $\alpha(0) + \Delta\alpha$), the $\Delta r$ master relation and the $W$-mass prediction ($m_W = 80.363$ GeV vs $80.360 \pm 0.011$), the corrected Weinberg-angle running (exact at $\mu_* \approx 233$ GeV, +2.1% at $m_Z$), and the Higgs quartic running (metastable vacuum at $M_{\text{Pl}}$). All numbers are produced by `computations/sm_radiative_corrections.py`. Status: Derived; the φ-boundary residuals ($\alpha_s$ $2\times$, $\alpha_1$/$\alpha_2$ ~25%) are documented as the open content of the framework.

### `gut-embedding.md`—SU(5) / SO(10) GUT Embedding

Explores embedding the three Standard Model gauge groups into a simple group at the φ-fixed point, fixing the unification coupling $\alpha_{\text{GUT}} = \varphi^{-3}/4\pi \approx 1/53$. SM running alone has no common intersection ($\alpha_1=\alpha_2$ at $10^{13}$ GeV, $\alpha_2=\alpha_3$ at $10^{17}$ GeV), so the $M_{\text{GUT}} \approx 2 \times 10^{16}$ GeV anchor of the proton-lifetime prediction requires the cascade's beyond-SM content ($\Delta b = 1.70$). In SU(5) (Georgi–Glashow, one generation in $\bar{\mathbf{5}} \oplus \mathbf{10}$) it predicts the boxed proton lifetime $\boxed{\tau(p \to e^+\pi^0) \approx 4 \times 10^{34}\ \text{yr}}$, just above current Super-K bounds; the SO(10) alternative places one generation plus the right-handed neutrino in the $\mathbf{16}$ spinor, gives the seesaw mechanism its natural home, and pushes the lifetime to $10^{35}$–$10^{36}$ yr. Status: Hypothesized—the unification scale and decay rate remain predictions pending Hyper-Kamiokande.

### `cp-violation.md`—CP Violation from the Golden Ratio

Derives the CKM phase from the Yang/Yin asymmetry: the chiral parameter $\eta = (\varphi-1)/(\varphi+1) = \varphi^{-3}$ breaks CP spontaneously, and unitarity-triangle closure with φ-scaled Wolfenstein elements yields $\delta_{\text{CKM}} = \pi\varphi^{-2} \approx 68.8^\circ$, matching the measured $68^\circ$ within 1%. It maps where naive φ-powers fail: the Jarlskog invariant is not a single φ-power ($\varphi^{-6} \approx 0.056$ is three orders too large) but emerges correctly from the Yukawa determinant, $J_{\text{CP}} \approx \varphi^{-3} \cdot \Delta m_u \Delta m_d / v^6 \approx 3.2 \times 10^{-5}$. For strong CP, φ-alignment forces $\theta = \theta_{\text{QCD}} + \arg\det M_q = 0$ automatically and predicts that no axion exists—a falsifiable null result for ADMX, CAST, IAXO, and MADMAX. Status: Derived.

### `neutrino-mass.md`—Neutrino Mass from φ

Explains the 0.01–0.1 eV neutrino scale via the seesaw mechanism with the right-handed mass fixed by the cascade: $\boxed{M_R = \varphi^{-3} \cdot M_{\text{GUT}} \approx 4.7 \times 10^{15}\ \text{GeV}}$—the SO(10) $B-L$ intermediate scale—with the exponent $n = 3$ counting the three generations. Through the φ-scaled Yukawa hierarchy this gives $m_{\nu,3} \approx 0.013$ eV, $m_{\nu,2} \approx \varphi^{-2} m_{\nu,3} \approx 0.0050$ eV, and $m_{\nu,1} \approx \varphi^{-4} m_{\nu,3} \approx 0.0019$ eV, with solar and atmospheric splittings reproduced at the right order with no free parameters. Status: Hypothesized.

## Cross-References

- `foundations/unified-lagrangian.md`—the unified Cassi Lagrangian from which the SM-from-φ breaking chain descends
- `foundations/xi-derivation.md`—derivation of the gravity coupling $\xi = \varphi^6$, the framework's last free parameter
- `predictions/falsifiable-predictions.md`—the prediction catalog hosting this directory's results ($m_W/m_Z$, $\sin^2\theta_W$, $\delta_{\text{CKM}}$, proton lifetime, neutrino splittings)
