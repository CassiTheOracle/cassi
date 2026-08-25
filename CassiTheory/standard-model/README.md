# Standard Model—Couplings, Gauge Structure, and CP from φ

## Status: Index—August 2026

## Abstract

Six documents cover the Standard Model's gauge structure, couplings, loop
corrections, and flavor sector through the Cassi $\varphi$-fixed point. The
canonical state remains the real-density pair $E_Y,E_I$; an additional
isospinor/gauge extension organizes the conditional symmetry-breaking chain
and supplies the asserted Weinberg boundary. The coupling-normalization
mechanism remains Hypothesized. Read `sm-from-phi.md` for the breaking chain,
`su2-gauge-extension.md` for the gauge mechanics and closure audit,
`sm-radiative-corrections.md` for running, `gut-embedding.md` for unification,
and the flavor-sector documents for CP and neutrino masses.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `sm-from-phi.md` | Electroweak breaking, gauge structure, fermion masses | Derived chain; Weinberg boundary asserted |
| 2 | `su2-gauge-extension.md` | Gauge extension of the two-fluid | Derived algebra; coupling boundary asserted |
| 3 | `gut-embedding.md` | SU(5) / SO(10) unification, proton decay | Hypothesized |
| 4 | `cp-violation.md` | CKM phase, Jarlskog invariant, strong CP | Hypothesized particle-sector CP/chiral map; Mapped $\delta_{\text{CKM}}$ and strong-CP span |
| 5 | `neutrino-mass.md` | Seesaw scale, neutrino masses | Hypothesized |
| 6 | `sm-radiative-corrections.md` | Loop corrections: RGE, Δα, Δr, m_W, λ | Derived |

## Document Summaries

### `sm-from-phi.md`—Standard Model from φ

The entry point for the directory: it records the conditional gauge structure
$\mathrm{SU}(3)_C \times \mathrm{SU}(2)_L \times \mathrm{U}(1)_Y$ organized by
successive truncations of the continued-fraction expansion of $\varphi$, and
records $\sin^2\theta_W=\varphi^{-3}\approx0.236$ as the fixed-point boundary
value. The curvature–orbit normalization attempt and its action-level blocker
are in `su2-gauge-extension.md` §3.2.1. The conditional Higgs construction
gives $m_W/m_Z=\sqrt{1-\varphi^{-3}}\approx0.874$ before the $\rho$ correction;
quark confinement uses a conditional Qi coherence threshold, and the CKM and
Yukawa sectors are documented below.

### `su2-gauge-extension.md`—SU(2) × U(1) Gauge Extension of the Cassi Two-Fluid

Treats the canonical state as the real-density pair $(E_Y,E_I)$ and records
the SU(2) gauge algebra and neutral mass matrix for an additional complex
isospinor sector. Mapping $(E_Y,E_I)$ into that sector and assigning a
compact $\mathrm{U}(1)\cong\mathrm{SO}(2)$ representation are **Hypothesized**
additional structures; within that extension,
$\langle\Psi\rangle\propto(\sqrt{\varphi},1)^T$ and the exact identity
$\sin^2\theta_W=\varphi^{-3}\iff(g/g')^2=2\varphi$ are recorded as an
asserted boundary. Section §3.2.1 tests a curvature–orbit candidate and finds
the missing metric and orbit-matching rule. Running and measured-scale
comparisons are in `sm-radiative-corrections.md`.

### `sm-radiative-corrections.md`—Standard Model Radiative Corrections from the φ-Boundary

Derives the complete one-loop (plus leading two-loop) radiative-correction
program that carries the $\varphi$-anchored inputs to the Z-pole:
gauge-coupling running with thresholds, the running of $\alpha$
($\bar\alpha^{-1}(m_Z)=128.95$ from $\alpha(0)+\Delta\alpha$), the $\Delta r$
master relation and the $W$-mass output ($m_W=80.363$ GeV versus
$80.360\pm0.011$), the Weinberg-angle running (exact at
$\mu_*\approx233$ GeV, +2.1% at $m_Z$), and input-sensitive Higgs quartic
running. Local outputs come from `computations/sm_radiative_corrections.py`;
the external NNLO comparison and the $\varphi$-boundary residuals
($\alpha_s$ $2\times$, $\alpha_1$/$\alpha_2$ ~25%) retain their documented
status.

### `gut-embedding.md`—SU(5) / SO(10) GUT Embedding

Explores conditional SU(5) / SO(10) embeddings of the Standard Model gauge
groups at the $\varphi$-fixed point. SM running alone has no common
intersection ($\alpha_1=\alpha_2$ at $10^{13}$ GeV,
$\alpha_2=\alpha_3$ at $10^{17}$ GeV), so the
$M_{\text{GUT}}\approx2\times10^{16}$ GeV anchor of the conditional
proton-lifetime estimate requires beyond-SM content ($\Delta b=1.70$). The
SU(5) estimate is $\tau(p\to e^+\pi^0)\approx1.3\times10^{37}\ \text{yr}$;
SO(10) adds the right-handed neutrino in the $\mathbf{16}$ and changes the
unification and proton-decay assumptions.

### `cp-violation.md`—CP Violation from the Golden Ratio

Treats the canonical $E_Y,E_I$ pair as real densities: $\eta_{\mathrm{dens}}=(\varphi-1)/(\varphi+1)=\varphi^{-3}$ is a density diagnostic with no intrinsic CP/chiral transformation law. A **Hypothesized** particle-sector complex/spinor observation map may use this scalar as a chiral bookkeeping parameter; within that conditional map, the ledgered CKM candidate $\delta_{\text{CKM}}=\pi\varphi^{-2}\approx68.8^\circ$ matches the measured $68^\circ$ within 1% (**Mapped**). The current Yukawa-determinant discussion identifies its normalization as dimensionally incomplete and retains no numerical $J_{\text{CP}}$ prediction; the strong-CP cascade estimate and no-axion null inherit the conditional Mapped CKM seed.

### `neutrino-mass.md`—Neutrino Mass from φ

Explains the seesaw scale with the right-handed neutrino at cascade step 20,
$M_R\approx10^{14}\ \text{GeV}$, and presents the canonical Fibonacci
cascade-partition spectrum
$m_1=0.00356$, $m_2=0.00931$, $m_3=0.05019\ \text{eV}$ (normal ordering,
no sterile neutrino). The full derivation lives in
`foundations/neutrino-masses.md`; `standard-model/neutrino-mass.md` is the
pedagogical entry point. Status: Hypothesized.

## Cross-References

- `foundations/unified-lagrangian.md`—the unified Cassi Lagrangian from which the SM-from-φ breaking chain descends
- `foundations/xi-derivation.md`—derivation of the gravity coupling $\xi = \varphi^6$, the framework's last free parameter
- `predictions/falsifiable-predictions.md`—the prediction catalog hosting this directory's results ($m_W/m_Z$, $\sin^2\theta_W$, $\delta_{\text{CKM}}$, proton lifetime, neutrino splittings)
