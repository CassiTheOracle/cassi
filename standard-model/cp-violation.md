# CP Violation from the Golden Ratio

## Status: Hypothesized particle-sector CP/chiral map; Mapped $\delta_{\text{CKM}}$ and strong-CP span; Yukawa-determinant $J_{\text{CP}}$ candidate dimensionally incomplete—August 2026

## Abstract

The canonical Cassi state contains two real, nonnegative density components,
$E_Y$ and $E_I$. Their fixed-point ratio $E_Y/E_I=\varphi$ and density
imbalance $\eta_{\mathrm{dens}}=(E_Y-E_I)/(E_Y+E_I)=\varphi^{-3}$ are scalar
density diagnostics, not an intrinsic CP-violating order parameter. A
**Hypothesized** particle-sector extension may supply additional
complex/spinor structure and an explicit observation map in which this
imbalance is represented by a chiral bookkeeping parameter; only within that
extension does the conditional CKM candidate
$\delta_{\text{CKM}}=\pi\varphi^{-2}\approx68.8^\circ$ have a chiral
interpretation. It remains **Mapped** against the measured value. The
Jarlskog invariant is not reproduced by the current $\varphi$-scaled
Yukawa-determinant candidate: its displayed normalization is dimensionally
incomplete, so no numerical $J_{\text{CP}}$ prediction is retained (§4.2).
The Standard Model fit is $J_{\text{CP}}\approx3.2\times10^{-5}$. Strong CP
retains a conditional cascade estimate only under a separately specified
**Hypothesized constitutive transport extension**:
$\bar\theta=\pi\varphi^{-83.4}\approx1.2\times10^{-17}$ (span ~81 rungs from
the GUT anchor; `foundations/strong-cp-derivation.md`). The conditional
construction introduces no axion field.

---

## 1. The Problem

The Standard Model contains exactly one CP-violating phase in the quark sector:
the complex phase $\delta_{\text{CKM}}$ in the Cabibbo-Kobayashi-Maskawa (CKM)
matrix. Its measured value is:

$$\delta_{\text{CKM}} \approx 68^\circ \quad (\text{SM fit, PDG 2024})$$

No symmetry or first-principles argument within the SM predicts this value. It
is an input parameter. The question: does the golden ratio $\varphi$ determine
$\delta_{\text{CKM}}$, and if so, through what mechanism?

---

## 2. Cassi Mechanism for CP Violation

### 2.1 Yang/Yin Density Imbalance and a Conditional CP Map

The canonical Cassi state contains two real, nonnegative density components,
$E_Y$ and $E_I$. Writing

$$
\rho = E_Y + E_I, \qquad \varepsilon = E_Y - \varphi E_I,
$$

the gated rank-one conversion relaxes the local density deviation
$\varepsilon$ while conserving $\rho$. The fixed-point ratio

$$\frac{E_Y}{E_I} = \varphi > 1$$

is therefore a real density relation. It does not by itself define a CP
transformation, a chiral representation, or a CP-violating order parameter.
The positive-root lift $\Psi_0=\sqrt{E_Y}$, $\Psi_1=\sqrt{E_I}$ and its
density-plane angle/current can be useful local diagnostics, but they do not
add an independent compact phase, chirality, or inter-rung transport law.

A **Hypothesized** particle-sector extension may supply an additional
complex/spinor doublet $\Psi_{\mathrm p}=(\psi_Y,\psi_I)^T$, a
constitutive map $E_a\leftrightarrow\psi_a^\dagger\psi_a$, and chiral
projectors

$$
P_Y \equiv P_R = \frac{1+\gamma^5}{2}, \qquad
P_I \equiv P_L = \frac{1-\gamma^5}{2}.
$$

Identifying Yang with right-handed and Yin with left-handed is part of that
**Hypothesized** extension only; it is not a property of the canonical
densities. Within the extension, the standard chiral CP relation may be used:

$$\psi_L \xrightarrow{CP} i\gamma^0\gamma^2\psi_R^*.$$

The relation supplies the particle-sector transformation once the extra
spinor/complex structure and observation map have been specified. It does not
turn $E_Y\neq E_I$ into an intrinsic CP order parameter.

### 2.2 Conditional Chiral Observation Parameter

The fixed-point densities still define the scalar imbalance

$$
\eta_{\mathrm{dens}}\equiv\eta =
\frac{E_Y - E_I}{E_Y + E_I}
= \frac{\varphi - 1}{\varphi + 1}
= \varphi^{-3} \approx 0.236.
$$

This identity is a density-plane diagnostic. If the **Hypothesized**
particle-sector map in §2.1 additionally sets
$\eta_{\mathrm{chiral}}\equiv\eta_{\mathrm{dens}}$, the same number can be
used as a chiral observation parameter; that identification is not derived
from the canonical two-fluid state.

The same value appears as the Weinberg angle only through the asserted
boundary condition $\sin^2\theta_W = 1/(1+2\varphi) = \varphi^{-3}$—the
coupling-ratio identity $(g/g')^2 = 2\varphi$, realized at $\mu_* = 233$ GeV
(Calibrated, ledger row 490). The shared value $\varphi^{-3}$ is a boundary
assignment, not a derived identity between the conditional particle-sector CP
map and electroweak mixing (`standard-model/su2-gauge-extension.md` §3.2).

---

## 3. Conditional CKM Phase from $\varphi$

The central question is whether the Mapped particle-sector candidate
$\delta_{\text{CKM}}$ can be organized from $\varphi$-scaled sector inputs.

### 3.1 Direct $\varphi$-Power Candidates

Several naive mappings suggest themselves:

| Formula | Value | Matches $\sim 68^\circ$? |
|---------|-------|--------------------------|
| $\pi - \arccos(\varphi^{-1}) \approx 180^\circ - 51.8^\circ$ | $128^\circ$ | No |
| $\pi \cdot \varphi^{-3} \approx 180^\circ \times 0.236$ | $42.5^\circ$ | No |
| $2\pi \cdot \varphi^{-3} \approx 360^\circ \times 0.236$ | $85^\circ$ | Close ($\sim 25\%$ off) |
| $\pi \cdot \varphi^{-2} \approx 180^\circ \times 0.382$ | $68.8^\circ$ | **Yes** |
The last entry, $\delta_{\text{CKM}} = \pi\varphi^{-2} \approx 68.8^\circ$,
matches the repository's $\sim69.2^\circ$ anchor at the percent level. The
PDG 2024 fit quoted in §3.2 is $65.55^\circ\pm1.55^\circ$, so the comparison
depends on which experimental anchor is used. Under the Hypothesized
particle-sector map, this is the cataloged Cassi candidate. The CKM magnitudes
enter through the standard Wolfenstein parameterization; the conditional
$\varphi$ comparison below concerns only its Cabibbo-scale parameter $\lambda$,
while $A$, $\bar\rho$, and $\bar\eta$ remain separate inputs. Its Mapped status
is detailed in §3.2.

### 3.2 Conditional Yukawa-hierarchy context for the phase
Direct $\varphi$-powers fail for $\delta_{\text{CKM}}$ because the CKM phase is a
sector-level quantity associated with the unitary rotation that diagonalises
the $\varphi$-scaled Yukawa matrices. This document does not derive that
rotation or an exact $\varphi$-to-Yukawa map. The conditional candidate uses the
standard Wolfenstein hierarchy

$$
|V_{us}| \simeq \lambda,\qquad
|V_{cb}| \simeq A\lambda^2,\qquad
|V_{ub}| \simeq A\lambda^3\sqrt{\bar\rho^2+\bar\eta^2},
\qquad \lambda \approx 0.225.
$$

The nearest integer $\varphi$-ladder candidate for this Cabibbo-scale
parameter is $\lambda \approx \varphi^{-3} \approx 0.236$, which is
$\approx 4.9\%$ high relative to $0.225$. This comparison applies to
$\lambda$ itself; $A$, $\bar\rho$, and $\bar\eta$ are separate Wolfenstein
inputs, and the comparison is not a derivation of any of them.

The value $\delta_{\text{CKM}} = \pi\varphi^{-2} \approx 68.8^\circ$ is
**Mapped** (Fit-Status Ledger row 482): it was selected from a four-candidate
$\varphi$-search ($\pi-\arccos(\varphi^{-1}) = 128^\circ$;
$\pi\varphi^{-3} = 42.5^\circ$; $2\pi\varphi^{-3} = 85^\circ$;
$\pi\varphi^{-2} = 68.8^\circ$) against the measured CKM phase (repo anchor
$\sim 69.2^\circ \pm 3.0^\circ$; PDG 2024 $65.55^\circ \pm 1.55^\circ$).
No unitarity-triangle closure calculation is shown in this document, and the
triangle's closure depends on the side magnitudes (it cannot determine the
phase "independently" of them); the Yukawa-diagonalization origin is not
derived here. See the Jarlskog invariant analysis in Section 4.

## 4. The Jarlskog Invariant

The Jarlskog invariant $J_{\text{CP}}$ measures the intrinsic CP violation in
the CKM matrix, independent of phase conventions:

$$J_{\text{CP}} = \operatorname{Im}(V_{us} V_{cb} V_{ub}^* V_{cs}^*)$$

### 4.1 Naive $\varphi$-scaling

The simplest Cassi guess would be a single $\varphi$-power:

$$J_{\text{CP}} \stackrel{?}{\approx} \varphi^{-6} \approx \frac{1}{17.944} \approx 0.056$$

This value exceeds the Standard Model fit by roughly three orders of
magnitude. A nearby ladder value is $\varphi^{-21}\approx4.1\times10^{-5}$,
within 28% of the fit, but that numerical proximity is only a selected
comparison. No $J_{\text{CP}}$ candidate is retained without a dimensionless
normalization and a particle-sector derivation.

### 4.2 Yukawa-determinant candidate: dimensionally incomplete

The Jarlskog invariant is not a $\varphi$-power. A candidate Cassi expression
based on Yukawa mass differences is

$$J_{\text{CP}} \approx \varphi^{-3} \cdot \frac{(m_c - m_u)(m_t - m_c)(m_t - m_u)}{v^6}
                      \cdot \frac{(m_s - m_d)(m_b - m_s)(m_b - m_d)}{v^6}.$$

Here $v \approx 246$ GeV and the quark masses are

$$\begin{aligned}
m_u &\approx 2.2\ \text{MeV}, & m_c &\approx 1.27\ \text{GeV}, & m_t &\approx 173\ \text{GeV} \\
m_d &\approx 4.7\ \text{MeV}, & m_s &\approx 93\ \text{MeV}, & m_b &\approx 4.18\ \text{GeV}.
\end{aligned}$$

The six mass differences in the numerator have dimension $[M]^6$, whereas
the two displayed $v^6$ denominators have dimension $[M]^{12}$. The right
hand side therefore has dimension $[M]^{-6}$, while $J_{\text{CP}}$ is
dimensionless. No additional normalization is specified here to convert this
Yukawa determinant into the CKM invariant, so the expression is dimensionally
incomplete and does not supply a $J_{\text{CP}}$ prediction. The Standard Model
fit remains $J_{\text{CP}}^{\text{SM}}\approx3.2\times10^{-5}$; the CP content
discussed in this paper is the CKM phase $\delta_{\text{CKM}}$.

---

## 5. Strong CP Problem

### 5.1 The Problem

QCD allows a CP-violating term:

$$\mathcal{L}_\theta = \frac{\theta}{32\pi^2} G_{\mu\nu}^a \tilde{G}^{a\mu\nu}$$

Experimental bounds from the neutron electric dipole moment require:

$$|\theta| < 10^{-10}$$

Why is $\theta$ so small? This is the strong CP problem.

### 5.2 Cassi Resolution: Cascade De-Resonance

In the canonical density sector, the $\varphi$-fixed point is a real-density
baseline: $\varphi$ is maximally de-resonant, and the two-fluid attractor
supplies no complex CP phase or CP transformation law. Within the
**Hypothesized** particle-sector map described in §2.1, the only CP-violating
seed is the CKM phase $\delta_{\text{CP}} = \pi\varphi^{-2}$ at the GUT scale.
A numerical transfer estimate from the GUT scale to the QCD scale requires a
separately specified **Hypothesized constitutive extension**: the canonical
two-density PDE and bubble-lattice geometry provide no derived inter-rung
signal-transport law or per-rung attenuation factor.

If that extension postulates transport over the ~81-rung span (n ≈ 94.7; GUT
seed n ≈ 13.3 for $M_{\text{GUT}} \approx 2\times10^{16}$ GeV), with a
per-rung transmission factor $\varphi^{-1}$, then the conditional estimate is

$$\bar\theta \approx \varphi^{-81.4}\,\delta_{\text{CP}} = \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$$

~7 orders of magnitude below the nEDM bound $10^{-10}$. The numerical span
calculation is in `foundations/strong-cp-derivation.md`; the transport premise
and resulting estimate are conditional on the extension. The span inherits
Mapped status from its GUT-seed anchor and $\delta_{\text{CP}}$ ledgered fits,
`parameter-inventory.md` §10.

**The conditional construction introduces no axion field.** Its falsifiable
implication is a null axion search only if the additional particle-sector and
transport assumptions are adopted. An axion discovery would disfavor this
specific strong-CP construction; a null search together with
$|\bar\theta|<10^{-10}$ would remain compatible with it but would not establish
the construction.

### 5.3 Falsifiability

The conditional strong-CP scenario can be tested by combining neutron
electric-dipole-moment bounds with axion searches (ADMX, CAST, IAXO, MADMAX).
The scenario is disfavored by an axion discovery, while a null search does not
by itself distinguish it from other axion-free explanations.

Any ~81-rung signal-transport interpretation is conditional on the separately
specified constitutive extension in §5.2. The canonical bubble-lattice
description does not identify cascade suppression with lattice attenuation or
supply an inter-rung transport law (`foundations/bubble-lattice-fabric.md` §3.3).

---

## 6. Summary of Predictions

| Observable | Naive $\varphi$-Power | Yukawa-Diagonalised Cassi | SM / Experiment |
|-----------|----------------------|--------------------------|-----------------|
| $\delta_{\text{CKM}}$ | $\pi\varphi^{-2} \approx 68.8^\circ$ | $\pi\varphi^{-2} \approx 68.8^\circ$ (conditional particle-sector map; side magnitudes Mapped) | $\sim 68^\circ$ |
| $|V_{us}|$ | $\varphi^{-1} \approx 0.618$ | Wolfenstein $\lambda \approx \varphi^{-3} \approx 0.236$ ($\approx 4.9\%$ high; candidate for $\lambda$ only) | $0.225$ |
| $|V_{cb}|$ | $\varphi^{-2} \approx 0.382$ | Wolfenstein $A\lambda^2$ with $\lambda \approx \varphi^{-3}$ ($A$ separate input) | $0.041$ |
| $|V_{ub}|$ | $\varphi^{-3} \approx 0.236$ | Wolfenstein $A\lambda^3\sqrt{\bar\rho^2+\bar\eta^2}$ with $\lambda \approx \varphi^{-3}$ ($A,\bar\rho,\bar\eta$ separate inputs) | $0.004$ |
| $J_{\text{CP}}$ | $\varphi^{-6} \approx 0.056$ | Yukawa-determinant candidate dimensionally incomplete (§4.2); no numerical $J_{\text{CP}}$ prediction | $3.2 \times 10^{-5}$ |
| Strong CP $\bar\theta$ |—| $\pi\varphi^{-83.4} \approx 1.2\times10^{-17}$ (conditional transport extension; Mapped) | $< 10^{-10}$ |
| Axion |—| No axion field in this conditional construction | Undiscovered |

### Key Takeaways

1. **$\delta_{\text{CKM}} = \pi\varphi^{-2}$ is the cataloged Cassi value**, a
   Mapped selection from a four-candidate $\varphi$-search (ledger §10 row 482),
   accurate to $<1\%$ against the repo's CKM anchor. The particle-sector map
   supplies this conditional phase candidate; the remaining CKM magnitudes use
   the standard Wolfenstein hierarchy with separate inputs $A$, $\bar\rho$, and
   $\bar\eta$. The $\varphi^{-3}$ comparison applies only to the Cabibbo-scale
   parameter $\lambda\approx0.236$, $\approx4.9\%$ high relative to $0.225$.

2. **The current Yukawa-determinant candidate for the Jarlskog invariant is
   dimensionally incomplete**: its six mass differences have dimension
   $[M]^6$, while the displayed denominators contribute $[M]^{12}$, so no
   dimensionless $J_{\text{CP}}$ prediction follows (§4.2). The Standard Model
   fit is $J_{\text{CP}}^{\text{SM}}\approx3.2\times10^{-5}$; the framework's
   CP content discussed here is the CKM phase $\delta_{\text{CKM}}$.

3. **The conditional strong CP construction gives the cascade de-resonance
   estimate without an axion field**—a falsifiable scenario only after the
   particle-sector CKM seed and the additional transport postulate are accepted.

4. The CKM magnitudes are organized by the standard Wolfenstein hierarchy;
   the $\varphi^{-3}$ comparison in this paper applies only to the
   Cabibbo-scale $\lambda$. The canonical two-density/bubble-lattice sector
   supplies no derived inter-rung propagation or lattice-attenuation identity.

The overall picture is conditional. The canonical fixed-point imbalance
$\eta_{\mathrm{dens}}=\varphi^{-3}$ can enter the particle-sector CP map only
after additional complex/spinor structure and an explicit observation map are
specified. The observable quark-sector structure is then carried by the SM
Yukawa matrices and their diagonalisation; the CKM candidate and strong-CP
estimate retain the Mapped statuses stated above.

## References

- `standard-model/sm-from-phi.md`—φ-powered Yukawa and CKM pattern
- `standard-model/su2-gauge-extension.md`—Weinberg angle and gauge structure
- `foundations/strong-cp-derivation.md`—cascade de-resonance, $\bar\theta = \pi\varphi^{-83.4} \approx 1.2\times10^{-17}$
- `foundations/bubble-lattice-fabric.md`—bubble-lattice geometry; the canonical sector supplies no derived inter-rung transport law
