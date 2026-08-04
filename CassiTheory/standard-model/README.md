# Standard Model—Couplings, Gauge Structure, and CP from φ

## Status: Index—July 2026

## Abstract

Six documents derive the Standard Model's gauge structure, couplings, loop corrections, and flavor sector from the Cassi $\varphi$-fixed point: the isospinor two-fluid field $\Psi = (\psi_Y, \psi_I)^T$ with Yang/Yin equilibrium ratio $\varphi$ fixes the symmetry-breaking chain, the Weinberg angle, the Yukawa hierarchy, the CKM phase, and the seesaw scale. The reading path is derivation order—start with `sm-from-phi.md` for the full breaking chain, then `su2-gauge-extension.md` for the gauge mechanics, `sm-radiative-corrections.md` for the loop corrections that connect the φ-boundary to the Z-pole, `gut-embedding.md` for unification, and the two flavor-sector documents `cp-violation.md` and `neutrino-mass.md`. Four documents are Derived (electroweak structure, gauge extension, radiative corrections, CP), two are Hypothesized (GUT embedding, neutrino masses), and each closes with falsifiable predictions cataloged in `predictions/falsifiable-predictions.md`.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `sm-from-phi.md` | Electroweak breaking, gauge structure, fermion masses | Derived |
| 2 | `su2-gauge-extension.md` | Gauge extension of the two-fluid | Derived |
| 3 | `gut-embedding.md` | SU(5) / SO(10) unification, proton decay | Hypothesized |
| 4 | `cp-violation.md` | CKM phase, Jarlskog invariant, strong CP | Derived |
| 5 | `neutrino-mass.md` | Seesaw scale, neutrino masses | Hypothesized |
| 6 | `sm-radiative-corrections.md` | Loop corrections: RGE, Δα, Δr, m_W, λ | Derived |

## Document Summaries

### `sm-from-phi.md`—Standard Model from φ

The entry point for the directory: it derives the gauge structure $\mathrm{SU}(3)_C \times \mathrm{SU}(2)_L \times \mathrm{U}(1)_Y$ from successive truncations of the continued-fraction expansion of $\varphi$, with the Weinberg angle $\sin^2\theta_W = \varphi^{-3} \approx 0.236$ emerging from the VEV asymmetry at the $\varphi$-fixed point. It then runs the Higgs mechanism—the φ-point VEV $v_\phi$, $m_W/m_Z = \sqrt{1 - \varphi^{-3}} \approx 0.874$ against the measured 0.881 (0.878 after the $\rho$ correction), and the quartic $\lambda = 0.1294$ fixed by the measured $m_H$—derives quark confinement from the Qi coherence threshold $Q \lessgtr \varphi^{-1}$ with $\alpha_{\text{GUT}} = \varphi^{-3}/4\pi \approx 1/53$ ($\alpha_s(m_Z) = 0.058$–$0.061$, $2.0\times$ low), and predicts the proton mass $m_p \approx \varphi^3 \Lambda_{\text{QCD}} \approx 847$ MeV within ~10%. Fermion masses follow the Yukawa hierarchy $y_f \propto \varphi^{-n_f}$, with the CKM phase and neutrino sector deferred to `cp-violation.md` and `neutrino-mass.md`; the full SM-from-φ Lagrangian is boxed in §5. Status: Derived.

### `su2-gauge-extension.md`—SU(2) × U(1) Gauge Extension of the Cassi Two-Fluid

Takes the two-fluid's internal $\mathrm{U}(1) \cong \mathrm{SO}(2)$ Yang/Yin rotation—already identified with electromagnetism—and promotes it to an SU(2) isospinor doublet whose norm-squared components are the Yang and Yin energies, the Cassi version of the Higgs doublet with $\langle\Psi\rangle \propto (\sqrt{\varphi}, 1)^T$ at equilibrium. Diagonalizing the neutral mass matrix at the φ-point VEV boxes the first-principles Weinberg angle $\boxed{\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.23607}$, then the gauge-coupling running is derived in `sm-radiative-corrections.md`: the measured running angle crosses $\varphi^{-3}$ at $\mu_* \approx 233$ GeV (the angle runs upward, so there is no GUT-scale boundary value 0.236), the SM couplings have no common intersection, and the φ-boundary gives $\alpha_s(m_Z) = 0.058$–$0.061$, $2.0\times$ below the measured value. The pattern extends to SU(3) color (φ-confinement, proton mass), with $m_t \approx \varphi^{-1} v_0 \approx 152$ GeV. It closes with a falsifiable-prediction table—$m_W/m_Z$, $\sin^2\theta_W$, proton lifetime, $\alpha_s$, and mass ratios, most testable at FCC-ee. Status: Derived.

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
