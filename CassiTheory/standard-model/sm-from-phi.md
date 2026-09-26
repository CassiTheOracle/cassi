# Standard Model from $\varphi$

## Status: Derived standard gauge-chain algebra; Hypothesized density-to-isospinor lift, inter-rung transport law, particle/gauge confinement extension, and electroweak coupling mechanism with asserted Weinberg boundary; Mapped conditional CKM phase candidate—August 2026

## Abstract

The Standard Model's gauge-chain structure is organized by the Cassi golden
ratio $\varphi$: its continued fraction supplies an ordering for the chain
labels, while the generator counts use standard Lie-algebra dimensions. The
weak-angle identity
$\sin^2\theta_W = \varphi^{-3} \approx 0.236$ is used as an asserted boundary
condition. The coupling ratio $(g/g')^2 = 2\varphi$ has a tested curvature–orbit
candidate, whose missing action-level normalization bridge is documented in
`standard-model/su2-gauge-extension.md` §3.2.1 and
`computations/weinberg_coupling_origin_audit.py`. Within this extended gauge
sector, the document describes the symmetry-breaking chain and the
**Hypothesized** Higgs construction, treats quark confinement through a
separate **Hypothesized** particle/gauge Qi extension of the canonical density
state, and records the CKM phase as a **Mapped**, conditional candidate.
The table below records comparisons and conditional predictions with their
current epistemic boundaries.

---

## 1. The Breaking Chain

The canonical Cassi input is a pair of real nonnegative density fields
$(E_Y,E_I)$. Define
$$
\rho=E_Y+E_I,\qquad \varepsilon=E_Y-\varphi E_I.
$$
$$
q=\frac{\rho^2}{\rho^2+\varphi^{-2}+\varepsilon^2}.
$$
The conversion contribution is the gated rank-one relaxation
$$
\left.\partial_tE_Y\right|_{\mathrm{conv}}=-\lambda(1-q)\varepsilon,\qquad
\left.\partial_tE_I\right|_{\mathrm{conv}}=+\lambda(1-q)\varepsilon,
$$
which conserves $\rho$ while relaxing $\varepsilon$ toward the fixed ratio
$E_Y=\varphi E_I$. The local diagnostics are
$$
\theta_d=\operatorname{atan2}(E_I,E_Y),\qquad
J_{d,z}=E_Y\,\partial_zE_I-E_I\,\partial_zE_Y
       =\rho_{\mathrm{plane}}^2\partial_z\theta_d,\qquad
\rho_{\mathrm{plane}}^2=E_Y^2+E_I^2.
$$
A positive-root real lift
$\Psi_0^{(+)}=\sqrt{E_Y}$, $\Psi_1^{(+)}=\sqrt{E_I}$ can be used for the
local amplitude-plane diagnostic
$$
\theta_\Psi^{(+)}=\operatorname{atan2}(\Psi_1^{(+)},\Psi_0^{(+)}),\qquad
\mathbf J_\Psi^{(+)}
=\Psi_0^{(+)}\nabla\Psi_1^{(+)}
 -\Psi_1^{(+)}\nabla\Psi_0^{(+)}
=\rho\,\nabla\theta_\Psi^{(+)}.
$$
These density-plane and amplitude-plane quantities are local diagnostics
along a chosen grid direction. They do not add a compact phase, chirality,
handedness, or inter-rung current.
An inter-rung transport law connecting
$\ell_n$ to $\ell_{n+1}$ is a separate **Hypothesized** constitutive
extension requiring an added flux or boundary term; it is not supplied by the
canonical conversion dynamics
(`foundations/qi-flow-double-helix.md` §1–2).

**Derived gauge-chain sector.** Once the additional isospinor and gauge fields
are posited as a **Hypothesized** particle-sector extension, the gauge-chain
structure retained here is:

```
SU(4) ──→ SU(3)_C × U(1)_B-L ──→ SU(3)_C × SU(2)_L × U(1)_Y ──→ U(1)_EM
```

The grand-unified embedding of this chain—SU(5) and SO(10) completions,
GUT-scale proton decay—is developed in `standard-model/gut-embedding.md`.

### 1.1 Generator Counting and $\varphi$-Organization

The continued fraction expansion organizes the chain labels:

$$\varphi = 1 + \frac{1}{1 + \frac{1}{1 + \frac{1}{1 + \ddots}}} = [1; 1, 1, 1, \ldots]$$

The successive labels are $(4,3,2,1)$, while the generator counts use the
standard Lie-algebra dimensions, including
$\dim\mathfrak{su}(N)=N^2-1$:

- **SU(4):** $N_{\text{gen}}=\dim\mathfrak{su}(4)=4^2-1=15$, the parent
  algebra in the retained chain.

- **SU(3):** $N_{\text{gen}}=\dim\mathfrak{su}(3)=3^2-1=8$, the color
  algebra in the first breaking product.

- **SU(2):** $N_{\text{gen}}=\dim\mathfrak{su}(2)=2^2-1=3$, the weak
  isospin algebra.

- **U(1):** 1 generator, the standard dimension of the abelian algebra.

Thus the retained gauge structure
$\text{SU}(3) \times \text{SU}(2) \times \text{U}(1)$ uses standard
Lie-algebra dimensions organized by the successive $\varphi$-chain labels.

### 1.2 The Mixing Angle

The fixed-point imbalance supplies the exact algebraic value used for the
Weinberg boundary:

$$\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.236$$

$$\cos^2\theta_W = 1 - \varphi^{-3} \approx 0.764$$

**Comparison with experiment:**

| Quantity | $\varphi$-Prediction | Measured (Z-pole) | Ratio |
|----------|--------------------------|-------------------|-------|
| $\sin^2\theta_W$ | $\varphi^{-3} \approx 0.236$ | 0.23122 | +2.1% (at $\mu_* = 233$ GeV, exact) |
| $\cos^2\theta_W$ | 0.764 | 0.769 | 0.993 |

The boundary identity is
$\sin^2\theta_W = 1/(1+2\varphi) \iff \tan^2\theta_W = 1/(2\varphi)
\iff (g/g')^2 = 2\varphi$ (exact $\varphi$-algebra, verified in `computations/weinberg_phi_identity.py`).

The VEV asymmetry enters the complete $(W^1,W^2,W^3,B)$ matrix through
$a=2\sqrt{\varphi}/(\varphi+1)$ and $\kappa=\varphi^{-3}$, with
$a^2+\kappa^2=1$. The spectrum contains a massless photon and the physical
angle remains the diagonal coupling ratio; the full calculation is in
`standard-model/su2-gauge-extension.md` §3.1 and
`computations/weinberg_phi_identity.py`. A curvature–orbit normalization
attempt derives $2\varphi$ only after adding a field-space metric and an
orbit-matching rule absent from the action (§3.2.1). The coupling boundary
therefore remains asserted; its blocking step is the action-level mechanism
fixing $g'^2 = g^2/(2\varphi)$.

The weak mixing angle runs **upward** with energy (toward the unification
value $3/8$), so the $\varphi$-point value is realized not at the GUT scale but about
one e-fold above the Z-pole ($\ln(233/91.2) \approx 0.94$): the MS-bar running
angle crosses $\varphi^{-3}$ at $\mu_* \approx 233$ GeV, a Calibrated scale
(`standard-model/sm-radiative-corrections.md` §3.4). At $m_Z$ itself the
prediction sits 2.1% above the measured 0.23122. The full derivation of the
running, the threshold corrections, and the residual is in
`standard-model/sm-radiative-corrections.md` §3–4.

---

## 2. The Higgs Mechanism in the Hypothesized $\varphi$-Extension

### 2.1 Vacuum Expectation Value

Within the **Hypothesized** isospinor lift from §1, the Higgs field is identified
with the isospinor's norm and Yang/Yin imbalance. The effective vacuum
expectation value (VEV) is:

$$v = \sqrt{\langle\rho_{\text{tot}}\rangle} \cdot \frac{r - 1}{r + 1}$$

where $r = \langle|\psi_Y|^2\rangle / \langle|\psi_I|^2\rangle$.

At the $\varphi$-fixed point $r = \varphi$:

$$v_\varphi = \sqrt{\langle\rho_{\text{tot}}\rangle} \cdot \frac{\varphi - 1}{\varphi + 1}
        = \sqrt{\langle\rho_{\text{tot}}\rangle} \cdot \frac{\varphi^{-1}}{\varphi + 1}
        = \sqrt{\langle\rho_{\text{tot}}\rangle} \cdot \varphi^{-3}$$

Since $\varphi^{-1} = \varphi - 1$, this gives $v_\varphi$ proportional to
the extension field magnitude times the $\varphi$-fraction.

### 2.2 W and Z Masses

The gauge boson masses arise from the covariant derivative acting on the VEV:

$$m_W = \frac{g v}{2}, \qquad m_Z = \frac{\sqrt{g^2 + g'^2} \, v}{2}$$

With $\sin^2\theta_W = \varphi^{-3}$ from the asserted boundary assignment:

$$\frac{m_W}{m_Z} = \sqrt{1 - \varphi^{-3}} \approx 0.874$$

**Comparison with experiment:** The measured ratio $80.36/91.19 \approx
0.8813$ differs from the $\varphi$-tree value 0.8740 by $-0.82\%$. The leading
radiative correction—the top-loop $\rho$ parameter—raises the tree ratio to
$m_W/m_Z = 0.8740\sqrt{1+\Delta\rho} = 0.8781$ ($m_W = 80.07$ GeV), halving
the gap to $-0.36\%$. The residual traces to the 2.1% Weinberg-angle offset
($\varphi^{-3}$ vs 0.2312 at $m_Z$). A projected FCC-ee precision study is
described in `standard-model/sm-radiative-corrections.md` §5.

### 2.3 The Higgs Mass

The quartic coupling determined by the measured Higgs mass is
$\lambda=m_H^2/(2v^2)=0.1294$ at $m_Z$ (with $v=246.22$ GeV from
$G_F$). The local one-loop run with running $y_t$ gives
$\lambda(10^{10}\,\text{GeV})=0.0008$ and
$\lambda(M_{\text{Pl}})=-0.0116$; using pole $y_t$ gives
$\lambda(M_{\text{Pl}})=-0.0729$. A separate NNLO Standard Model reference
reports $\lambda(M_{\text{Pl}})=-0.011$ (Degrassi et al. 2012). The
metastability assessment is input-sensitive, and these are standard-SM
comparisons for the Cassi cascade rather than a $\varphi$-derived stability
prediction (`standard-model/sm-radiative-corrections.md` §6).

The quartic formula $\lambda_\varphi=(\varphi^{-2}/2)(g^2/8)$ does not
reproduce the measured mass: it gives $\lambda=0.0101$, i.e. $m_H=35$ GeV.
The Higgs mass is an input to the radiative-correction program. Conditional
structural candidates remain open: the Wu-Xing quartic gives 122.4 GeV
(−2.3%), while the $\lambda(M_{\text{Pl}})=0$ stability line gives 129.0 GeV
at one loop and 129.2 GeV in the NNLO reference, both above 125.25 GeV.
The two-fluid eigenmodes give 198.1/169.2 GeV and simple pooling gives
182.5–184.8 GeV, so neither construction supplies the measured mass. Three
sub-0.1% candidates (top-Yukawa chain 0.001%, Wu-Xing+$\varphi^{-3}/5$
0.02%, $m_t\varphi^{-2/3}$ 0.04%) await mechanisms.

---

## 3. Quark Confinement: Hypothesized Qi Extension

### 3.1 Confinement Criterion in the Hypothesized Extension

The canonical solver state is the real density pair $(E_Y,E_I)$ with
$\rho$, $\varepsilon$, and the conversion gate $q$ defined in §1. A separate
**Hypothesized** particle/gauge extension may introduce a complex amplitude
through the explicit map

$$
\Psi_{\mathrm p}(x)=
\begin{pmatrix}
\sqrt{E_Y(x)}e^{i\chi_Y(x)}\\
\sqrt{E_I(x)}e^{i\chi_I(x)}
\end{pmatrix},
\qquad
\mathcal{M}:(E_Y,E_I,\chi_Y,\chi_I)\mapsto\Psi_{\mathrm p},
$$

where the added phases $\chi_Y,\chi_I$ and the normalization are extension
data. In that declared normalization, define the distinct coherence metric

$$Q_\Psi=|\Psi_{\mathrm p}|^2\cdot|\varepsilon|^2.$$

The scalar $Q_\Psi$ belongs to this **Hypothesized** extension; it is distinct
from the canonical gate $q$. Within the extension only, the following
threshold is a conditional criterion to be tested for the SU(3) color sector:

$$Q_\Psi < \varphi^{-1} \quad \Longrightarrow \quad
\text{Asymptotic freedom (deconfinement)}$$
$$Q_\Psi > \varphi^{-1} \quad \Longrightarrow \quad
\text{Confinement}.$$

The scale dependence of $Q_\Psi$ requires an extension map
$\mathcal{M}_\mu$ and an action-level normalization; the canonical conversion
dynamics supply neither. The threshold and any associated condensate
interpretation therefore remain **Hypothesized** extension claims.

### 3.2 The Running Coupling

The β-function for SU(3):

$$\beta(\alpha_s) = \frac{d\alpha_s}{d\ln\mu} = -\frac{b_0}{2\pi}\alpha_s^2 + \mathcal{O}(\alpha_s^3)$$

where $b_0 = 11 - 2n_f/3$. For $n_f = 6$ active flavors, $b_0 = 7$.

The asserted $\varphi$ boundary assigns the GUT-scale coupling:

$$\alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi} \approx \frac{0.236}{4\pi} \approx 0.0188 \approx \frac{1}{53}$$

Running to $M_Z \approx 91.2\ \text{GeV}$ with $M_{\text{GUT}} \approx 10^{16}\ \text{GeV}$:

$$\alpha_s(M_Z) = \frac{\alpha_{\text{GUT}}}{1 - \frac{b_0}{2\pi}\alpha_{\text{GUT}}\ln(M_{\text{GUT}}/M_Z)} \approx 0.058$$

(one loop; 0.061 with two-loop QCD). This is $2.0\times$ below the measured
$\alpha_s(M_Z) = 0.118$—the documented deficit that requires $\Delta b = 1.70$
of beyond-SM colored content between $M_Z$ and $M_{\text{GUT}}$
(`parameter-inventory.md` §4.4; `standard-model/sm-radiative-corrections.md`
§3.2).

### 3.3 Proton mass scale comparison

The conventional QCD scale is obtained after threshold matching and
higher-order running. With the $n_f=6$ one-loop coefficient $b_0=7$ used
above, direct inversion of the displayed one-loop relation gives

$$
\Lambda_{\text{1-loop},\,n_f=6}
\approx M_Z\exp\!\left(-\frac{2\pi}{b_0\alpha_s(M_Z)}\right)
\approx45\ \text{MeV}.
$$

The conventional phenomenological value
$\Lambda_{\text{QCD}}\approx200\ \text{MeV}$ used in the proton comparison is
an external threshold-matched scale, not the output of this $n_f=6$ one-loop
expression. The measured ratio is $m_p/\Lambda_{\text{QCD}}\approx4.69$. A
nearby $\varphi$-ladder comparison is

$$
m_p \stackrel{\text{comparison}}{\approx}
\varphi^3\Lambda_{\text{QCD}}
\approx4.236\times200\ \text{MeV}\approx847\ \text{MeV},
$$

which leaves a residual of about 10% against the measured proton mass. This
uses the external QCD scale and is not a proton-mass prediction or derivation.
The ledger assigns the proton mass class **E** and leaves its mass mechanism
open; QCD kinetic, gluon, and trace-anomaly contributions are not decomposed by
the $\varphi$ bookkeeping.

---

## 4. Fermion Masses and the CKM Matrix

### 4.1 Yukawa Hierarchy from $\varphi$-Powers

The Yukawa couplings, which generate fermion masses after electroweak symmetry
breaking, can be organized by a $\varphi$-powered reference hierarchy:

$$y_f \propto \varphi^{-n_f}$$

where $n_f$ is the generation index (0 for first generation, 1 for second, etc.).
The simple values below are reference $\varphi$-scales rather than a closed mass
derivation:

| Particle | $\varphi$-Pattern | Reference $\varphi$-Scale | Observed Mass |
|----------|------------------|--------------------------|---------------|
| $m_e$ | $m_0$ | reference | $0.511\ \text{MeV}$ |
| $m_\mu$ | $\varphi^{-1} m_0$ | $0.316\ \text{MeV}$ | $105.7\ \text{MeV}$ |
| $m_\tau$ | $\varphi^{-2} m_0$ | $0.195\ \text{MeV}$ | $1777\ \text{MeV}$ |

The muon and tau masses differ substantially from the simple $\varphi$-power
scaling; generation-dependent factors are required, while their Cassi
realization remains **Hypothesized**.

Within the selected Wu-Xing construction, the exact algebraic gap is
**Derived** conditional on that construction:

$$g=1-\varphi^{-5},\qquad
y_t=1-\varphi^{-10}=2g-g^2.$$

The b/τ Yukawas sit at half-rungs 8.5/9.5 below the top
(+1.0% / +0.5%); their two-step survival and the density-to-isospinor/chiral
lift remain **Hypothesized** mechanism targets, with the PDE derivation open
(`standard-model/sm-radiative-corrections.md` §6.3).

### 4.2 CKM Matrix from $\varphi$-Angles

The CKM matrix follows the Wolfenstein hierarchy $|V_{us}| \sim \lambda$,
$|V_{cb}| \sim \lambda^2$, $|V_{ub}| \sim \lambda^3$ with $\lambda \approx
0.225$. The nearest $\varphi$ match is $\lambda \approx \varphi^{-3}
\approx 0.236$ ($5\%$ off), suggesting running or mixing corrections.
The live CP-violation analysis classifies the phase candidate as **Mapped** and
conditional on the **Hypothesized** particle-sector observation/gauge extension:

$$\delta_{\text{CKM}} = \pi\varphi^{-2}\approx 1.199\ \text{rad}$$

(`standard-model/cp-violation.md` §3.1–3.2). The candidate's status depends on
the added complex/chiral map and the empirical selection documented there.

### 4.3 Neutrino Masses

Neutrino masses come from the seesaw mechanism, $m_\nu = y_\nu^2 v_0^2 / M_R$,
with the right-handed neutrino at cascade step 20, $M_R \approx 10^{14}\ \text{GeV}$
(`foundations/dimensionful-cascade.md`). Two naive $\varphi$-powers (one for
$y_\nu$, one for $M_R$) would leave a degenerate two-parameter family. The
cascade RGE + PMNS computation (`computations/cascade_rge_pmns.py`) selects a
Mapped candidate within the declared compressed-seesaw/Fibonacci ansatz by
matching the observed mass-squared ratio: the span partitions into Fibonacci
sub-rungs with offsets $\Delta_1 = 1.00$ and $\Delta_2 = 1.75$ rungs, giving
the spectrum

$$m_1 = 0.00356\ \text{eV},\qquad m_2 = 0.00931\ \text{eV},\qquad m_3 = 0.05019\ \text{eV}$$

(normal ordering, no sterile neutrino). The PMNS angle relations printed by
the computation are conditional coefficient-free candidates within its
conversion-Jacobian ansatz, not outputs of the canonical two-density solver.
The full derivation is in
`foundations/neutrino-masses.md`; the pedagogical primer is
`standard-model/neutrino-mass.md`.

## 5. Conditional particle/gauge action

Within the **Hypothesized** isospinor and gauge extension, a compact
Standard-Model-like action can be written in Cassi notation. The fields in
this section are extension fields; the canonical state remains the real
density pair in §1.

$$\boxed{\mathcal{L}_{\mathrm{ext}} = \bar{\Psi} (i\gamma^\mu D_\mu - m) \Psi
        - \frac{1}{4} F_{\mu\nu} F^{\mu\nu}
        + \mathcal{L}_{H\text{-breaking}}}$$

### 5.1 Gauge Sector

$$-\frac{1}{4} F_{\mu\nu}^a F^{a\mu\nu}
  -\frac{1}{4} B_{\mu\nu} B^{\mu\nu}
  -\frac{1}{4} G_{\mu\nu}^A G^{A\mu\nu}$$

where $F^a_{\mu\nu}$ for SU(2), $B_{\mu\nu}$ for U(1)_Y, and
$G^A_{\mu\nu}$ for SU(3). The coupling constants satisfy:
$$\frac{g'}{g} = \tan\theta_W = \sqrt{\frac{\varphi^{-3}}{1-\varphi^{-3}}} \approx 0.556,
\qquad \sin^2\theta_W = \varphi^{-3}$$

$$g_s^2 = 4\pi\alpha_s(\mu), \qquad \alpha_s(\mu) = \frac{\alpha_{\text{GUT}}}{1 + \frac{b_0}{2\pi}\alpha_{\text{GUT}}\ln\frac{\mu}{\mu_{\text{GUT}}}}$$

### 5.2 Fermion Kinetic Sector

$$\bar{\Psi} i\gamma^\mu D_\mu \Psi = \bar{\Psi}_L i\gamma^\mu (\partial_\mu
  - i\frac{g}{2} W_\mu^a \tau^a - i\frac{g'}{2} B_\mu Y) \Psi_L
  + \bar{\Psi}_R i\gamma^\mu (\partial_\mu - i g' B_\mu Y) \Psi_R$$

where $\Psi_L$ transforms as an SU(2) doublet, $\Psi_R$ as SU(2) singlets,
and $\tau^a$ are the Pauli matrices acting in isospin space.

### 5.3 Conditional Higgs-breaking sector

The optional symmetry-breaking sector at the $\varphi$-point is

$$\mathcal{L}_{H\text{-breaking}} =
  (D_\mu\Phi_H)^\dagger D^\mu\Phi_H
  - \lambda_H\left(|\Phi_H|^2 - v_\varphi^2\right)^2
  - \bar{\Psi}_f y_f \Phi_H \Psi_f + \text{h.c.}$$

where:

- $\Phi_H$ is the **Hypothesized** Higgs doublet identified with the
  isospinor extension
- $v_\varphi$ is the extension VEV at the $\varphi$ fixed point
- $\lambda_H = (\varphi^{-2}/2)(g^2/8)$ is a selected conditional quartic
  coupling
- $y_f \propto \varphi^{-n_f}$ are reference Yukawa couplings

### 5.4 Hypothesized Qi Coherence Extension

The canonical conversion dynamics use the gate $q$ defined in §1. A separate
particle/gauge extension may promote the mapped quantity $Q_\Psi$ from §3.1
to an additional coherence field and add the action-level ansatz

$$\mathcal{L}_{\mathrm{Qi,ext}} = \frac{1}{2}(\partial_\mu Q_\Psi)^2
  - \frac{\varphi}{2}Q_\Psi^2\cdot\operatorname{tr}(F_{\mu\nu}F^{\mu\nu})
  - \frac{1}{\varphi^{-1}}(Q_\Psi-\varphi^{-1})
    \bar{\Psi}_{\mathrm p}\Psi_{\mathrm p}.$$

This term is **Hypothesized** and depends on the declared map $\mathcal{M}$ and
normalization in §3.1. Its threshold interpretation is the conditional
criterion stated there; it supplies no additional canonical confinement law
for the real density pair or its gate $q$.

---

## 6. Summary of $\varphi$-Comparisons and Conditional Predictions

| Observable | $\varphi$-Prediction | Experiment | Notes |
|-----------|---------------------|------------|-------|
| $\sin^2\theta_W$ (at $m_Z$) | $\varphi^{-3} \approx 0.236$ | 0.23122 | +2.1%; exact at $\mu_* = 233$ GeV (running is upward, not downward) |
| $m_W/m_Z$ | $\sqrt{1-\varphi^{-3}} \approx 0.874$; 0.878 with $\rho$-correction | 0.8813 | −0.36% after radiative corrections; projected FCC-ee test under the quoted precision |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi) \approx 1/53$ | no SM unification point | $\alpha_1=\alpha_2$ at $10^{13}$ GeV ($\alpha^{-1}\approx 42$); $\alpha_2=\alpha_3$ at $10^{17}$ GeV |
| $\alpha_s(M_Z)$ | 0.058 (1-loop); 0.061 (2-loop) | 0.118 | $2.0\times$ low; $\Delta b = 1.70$ beyond-SM content required |
| $m_H$ | input ($\lambda = 0.1294$); $\lambda_\varphi$ formula gives 35 GeV | 125.2 GeV | not derived; vacuum metastable at $M_{\text{Pl}}$ |
| $m_p$ | comparison $\varphi^3 \cdot \Lambda_{\text{QCD}}$ | 938 MeV | $\sim10\%$ residual using measured $\Lambda_{\text{QCD}}$; mass class E, not derived |
| $|V_{us}|$ | $\varphi^{-3} \approx 0.236$ (nearest $\varphi$ power) | 0.225 | $5\%$ off; mixing corrections needed |
| $m_{\nu_3}$ | $0.05019\ \text{eV}$ (cascade RGE + PMNS) | 0.050 | See `foundations/neutrino-masses.md` |

The listed $\varphi$ comparisons range from sub-percent residuals to the
factor-of-two $\alpha_s$ deficit; they do not establish a common derivation of
the Standard Model parameters. The loop equations are Derived from Standard
Model inputs (`standard-model/sm-radiative-corrections.md`), while the
boundary assignments and particle-sector lifts retain the statuses stated
above. The residual discrepancies—$\alpha_s$ $2\times$ low,
$\alpha_1$/$\alpha_2$ ~25% weak, and $\sin^2\theta_W$ 2.1% high at $m_Z$—
remain open completion targets. The exact relation
$g=1-\varphi^{-5}$ is **Derived** conditional on the selected Wu-Xing
construction. The density-to-isospinor/chiral lift and two-step b/τ Yukawa
survival remain **Hypothesized** mechanism targets. The CKM phase candidate
retains its Mapped, conditional status, while the Qi confinement criterion is
restricted to the Hypothesized particle/gauge extension in §3.1; neither is a
canonical two-density prediction.

## References

- `standard-model/sm-radiative-corrections.md`—full derivation of the loop corrections
- `standard-model/cp-violation.md`—CKM phase and Jarlskog invariant
- `standard-model/gut-embedding.md`—SU(5)/SO(10) embedding, proton decay
- `standard-model/neutrino-mass.md`—seesaw primer and canonical spectrum
- `foundations/neutrino-masses.md`—canonical neutrino spectrum (cascade RGE + PMNS)
- `foundations/dimensionful-cascade.md`—cascade rung anchors
