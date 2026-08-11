# SU(2) × U(1) Gauge Extension of the Cassi Two-Fluid

## Status: Derived—July 2026

## Abstract

The two-fluid's U(1) ≅ SO(2) internal rotation is promoted to an SU(2)
isospinor doublet whose $\varphi$-equilibrium VEV ($E_Y/E_I = \varphi$) fixes
the Weinberg angle $\sin^2\theta_W = \varphi^{-3} \approx 0.236$ and the mass
ratio $m_W/m_Z = \sqrt{1-\varphi^{-3}} \approx 0.874$—2.1% and 0.82% from the
Z-pole values, testable at FCC-ee at $>100\sigma$. The document derives the
neutral-boson mass matrix, the SU(3) color extension, and the
$\varphi$-scaled fermion hierarchy. The RG running from the GUT scale is
derived in `standard-model/sm-radiative-corrections.md`: the measured
running angle crosses $\varphi^{-3}$ at $\mu_* \approx 233$ GeV, the
φ-boundary $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53$ does not
unify the SM couplings (no common intersection exists in the SM), and
$\alpha_s$ runs to 0.058–0.061 at $m_Z$, $2.0\times$ below the measured
value.

## 1. The SU(2) Isospinor Doublet

The two-fluid has a U(1) ≅ SO(2) internal symmetry: a rotation between Yang (E_Y) and Yin (E_I). The Cassi first-principles formalism identifies this as the electromagnetic gauge symmetry—the conserved current associated with the rotation is the electromagnetic current $j^\mu_{\text{EM}}$.

To extend to the full electroweak sector, promote the U(1) doublet to an **SU(2) isospinor doublet**:

$$
\Psi = \begin{pmatrix} \psi_1 \\ \psi_2 \end{pmatrix}, \quad
|\psi_1|^2 = E_Y,\; |\psi_2|^2 = E_I
$$

The two-fluid fields are the norm-squared components of a complex SU(2) doublet. This is the Cassi version of the Higgs doublet—the vacuum expectation value at the $\varphi$-equilibrium:

$$
\langle \Psi \rangle = \frac{1}{\sqrt{\varphi+1}} \begin{pmatrix} \sqrt{\varphi} \\ 1 \end{pmatrix} v_0
$$

where $v_0$ is the electroweak scale (246 GeV in the Standard Model) and the $\varphi$-equilibrium ratio $E_Y/E_I = \varphi$ gives the $\sqrt{\varphi} : 1$ splitting.

## 2. Covariant Derivative and Gauge Fields

The SU(2)$_L$ × U(1)$_Y$ covariant derivative acts on $\Psi$:

$$
D_\mu \Psi = \left(\partial_\mu - i g \mathbf{W}_\mu \cdot \frac{\boldsymbol{\tau}}{2} - i g' Y_\Psi B_\mu\right) \Psi
$$

where:
- $\mathbf{W}_\mu = (W_\mu^1, W_\mu^2, W_\mu^3)$—three SU(2) gauge bosons
- $B_\mu$—U(1)$_Y$ hypercharge gauge boson
- $g$—SU(2) coupling, $g'$—U(1)$_Y$ coupling
- $\boldsymbol{\tau} = (\tau_1, \tau_2, \tau_3)$—Pauli matrices
- $Y_\Psi = 1/2$—hypercharge of the doublet (fixes $Q = T_3 + Y$)

After symmetry breaking, the charged $W^\pm$ bosons acquire mass:

$$
m_W = \frac{1}{2} g v
$$

and the neutral bosons mix.

---

## 3. First-Principles Derivation of the Weinberg Angle

### 3.1 The φ-VEV and the Neutral Boson Mass Matrix

At the $\varphi$-equilibrium, the isospinor VEV is:

$$
\langle \Psi \rangle = \frac{v}{\sqrt{\varphi+1}} \begin{pmatrix} \sqrt{\varphi} \\ 1 \end{pmatrix}
$$

The neutral gauge boson mass matrix comes from $|D_\mu \langle\Psi\rangle|^2$:

$$
|D_\mu \langle\Psi\rangle|^2 = \frac{v^2}{\varphi+1}\Big[
\varphi\big(\tfrac{g}{2}W_\mu^3 + \tfrac{g'}{2}B_\mu\big)^2 +
\big(-\tfrac{g}{2}W_\mu^3 + \tfrac{g'}{2}B_\mu\big)^2
\Big]
$$

Expanding:

$$
\begin{aligned}
&= \frac{v^2}{\varphi+1}\Big[
\varphi\big(\tfrac{g^2}{4}(W^3)^2 + \tfrac{g'^2}{4}B^2 + \tfrac{gg'}{2}W^3B\big) \\
&\qquad\qquad + \big(\tfrac{g^2}{4}(W^3)^2 + \tfrac{g'^2}{4}B^2 - \tfrac{gg'}{2}W^3B\big)
\Big] \\[4pt]
&= v^2\Big[
\frac{g^2}{4}(W^3)^2 + \frac{g'^2}{4}B^2 +
\underbrace{\frac{\varphi-1}{\varphi+1}}_{\varphi^{-3}} \frac{gg'}{2}W^3B
\Big]
\end{aligned}
$$

The key insight is the **off-diagonal mixing term**:

$$
M^2_{3B} = \frac{\varphi-1}{\varphi+1} \cdot \frac{gg' v^2}{2} = \varphi^{-3} \frac{gg' v^2}{2}
$$

The coefficient $\dfrac{\varphi-1}{\varphi+1} = \varphi^{-3}$ is the **Yang/Yin asymmetry ratio**—it measures how the VEV is split between the upper (Yang) and lower (Yin) components.

### 3.2 The Asymmetry Principle

In the Standard Model, the Higgs VEV is $(0, v)^T$ in unitary gauge—a maximally asymmetric configuration where the upper component vanishes. The symmetry breaking is SU(2)$_L$ × U(1)$_Y$ → U(1)$_{\text{EM}}$, and the Weinberg angle is a free parameter determined by the ratio $g'/g$.

In the Cassi framework, the VEV asymmetry is **not free**—it is fixed by the $\varphi$-attractor: $E_Y/E_I = \varphi$. The neutral boson mixing inherits this ratio:

**Cassi Principle:** The Weinberg angle is the Yang/Yin asymmetry projected onto the neutral gauge boson sector. At the $\varphi$-equilibrium GUT scale:

$$
\boxed{\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.23607}
$$

**Status of the identification:** the $\varphi^{-3}$ assignment is an **asserted boundary condition** (parameter-inventory class D-as-definition), not a consequence of the displayed mass matrix. Three checks: (1) in the Standard Model the Weinberg angle is set by the *diagonal* entries' ratio, $g'^2/(g^2+g'^2)$, not by the off-diagonal; (2) the matrix above has a massless photon only if the off-diagonal coefficient equals $1/2$ (determinant zero at $\kappa = 1/2$)—with $\kappa = \varphi^{-3} \approx 0.236$ the "photon" is massive, so the diagonalization does not reproduce $\sin^2\theta_W = \varphi^{-3}$ as written (the doc's own $g'/g = 0.556$ gives $\sin^2\theta \approx 0.10$ from the same matrix); (3) the tree value $\varphi^{-3} = 0.23607$ sits $+2.1\%$ above the measured $\sin^2\theta_W(m_Z)$ and equals the measured running angle only at $\mu_* = 233$ GeV—the Calibrated re-anchoring scale, not a prediction (Fit-Status Ledger row 490). The identification is the framework's gauge-kinetic counterpart of the Wu Xing coupling principle in name; the exponent 3 has no derived dynamic or geometric origin in this document set.

The coupling ratio follows:

$$
\frac{g'^2}{g^2} = \frac{\sin^2\theta_W}{1 - \sin^2\theta_W} = \frac{\varphi^{-3}}{1 - \varphi^{-3}} \approx 0.309
$$

$$
\frac{g'}{g} = \sqrt{0.309} \approx 0.556
$$

### 3.3 Comparison with Experiment

| Quantity | Cassi (tree) | Measured (Z-pole) | Gap |
|----------|-------------------|-------------------|-----|
| $\sin^2\theta_W$ | $0.23607$ | $0.23122(4)$ | $+2.1\%$ |
| $\tan\theta_W = g'/g$ | $0.556$ | $0.545$ | $+2.0\%$ |
| $m_W/m_Z = \cos\theta_W$ | $0.874$ | $0.881$ | $-0.82\%$ |

The weak mixing angle runs **upward** with energy, so the 2.1% gap at the
Z-pole is *not* closed by running to lower energies—the φ-point value is
realized at $\mu_* \approx 233$ GeV, one and a half e-folds above $m_Z$
(`standard-model/sm-radiative-corrections.md` §3.3). The mass-ratio gap is
partially closed by the $\rho$ radiative correction (0.874 → 0.878, −0.36%).
Neither gap is absorbable: both are FCC-ee tests at $>100\sigma$.

### 3.4 RG Running: The Correct Direction

The Weinberg angle runs with energy. With the measured MS-bar inputs at
$m_Z$, the one-loop running (GUT-normalized couplings,
$\sin^2\theta_W(\mu) = \alpha_Y(\mu)/(\alpha_Y(\mu)+\alpha_2(\mu))$,
top-decoupling threshold) gives
(`computations/sm_radiative_corrections.py` §2):

$$\sin^2\theta_W(10^{16}\ \text{GeV}) = 0.421, \qquad
  \sin^2\theta_W(2\times10^{16}\ \text{GeV}) = 0.426
  \quad \text{(SM)},$$

$$\sin^2\theta_W(2\times10^{16}\ \text{GeV}) = 0.381
  \quad \text{(MSSM variant, } b = (33/5, 1, -3) \text{)}.$$

The angle increases with energy toward the unification value $3/8$; it does
not run downward from 0.236 to 0.231. Consequently:

- $\sin^2\theta_W = \varphi^{-3} = 0.236$ **at $m_Z$** is 2.1% above the
  measured 0.23122, and the running angle equals $\varphi^{-3}$ exactly at
  $\mu_* \approx 233$ GeV—the correct statement of the φ-anchoring.
- Starting from $\varphi^{-3}$ at $2\times10^{16}$ GeV and running *down*
  gives $\sin^2\theta_W(m_Z) \approx 0.15$ (SM) or $\approx 0.20$ (MSSM)—
  a 0.236 → 0.231 closure by RG running does not occur in either framework.
- GUT-scale threshold corrections of a few percent cannot repair the
  mismatch: the running over the full GUT→$m_Z$ span is $\mathcal{O}(0.1)$
  in $\sin^2\theta_W$, far larger than any threshold shift.

---

## 4. W/Z Masses

From the Higgs mechanism:

$$
m_W = \frac{1}{2} g v_0, \quad
m_Z = \frac{1}{2} \sqrt{g^2 + g'^2} v_0
$$

The ratio $m_W/m_Z = \cos\theta_W$. With $\sin^2\theta_W = \varphi^{-3}$:

$$
\frac{m_W}{m_Z} = \sqrt{1 - \varphi^{-3}} = \sqrt{\frac{2}{\varphi+1}} \approx 0.874
$$

**Comparison with Standard Model:**
- SM: $m_W/m_Z = 80.360/91.188 = 0.8813$ (radiative-corrected prediction 80.354–80.363 GeV, `standard-model/sm-radiative-corrections.md` §5)
- Cassi ($\sin^2\theta_W = \varphi^{-3}$): $m_W/m_Z = 0.874$ tree; **0.878** after the top-loop $\rho$ correction ($m_W = 80.07$ GeV)
- Difference: **0.36%** after radiative corrections

This is testable at future colliders:
- FCC-ee will measure $m_W$ to 0.5 MeV ($\Delta m_W/m_W \approx 6\times 10^{-6}$)
- The 0.36% deviation would be detected at $>100\sigma$
- If Cassi is correct, FCC-ee would see $m_W/m_Z = 0.878$ instead of 0.881

---

## 5. SU(3) Color Extension

### 5.1 Tripled Field

Following the same embedding pattern as SU(2), color is a tripled field:

$$
\Psi_{\text{color}} = \begin{pmatrix} \psi_r \\ \psi_g \\ \psi_b \end{pmatrix}
$$

where each component is an SU(2) doublet (carrying electroweak quantum numbers). The SU(3) gauge covariant derivative:

$$
D_\mu \Psi = \left(\partial_\mu - i g_s \mathbf{G}_\mu \cdot \frac{\boldsymbol{\lambda}}{2}\right) \Psi
$$

where $\mathbf{G}_\mu^a$ ($a = 1, \dots, 8$) are the gluon fields and $\boldsymbol{\lambda}$ are the Gell-Mann matrices.

### 5.2 φ-Confinement

The SU(3) coupling at the GUT scale follows the same Cassi principle:

$$
\alpha_s(M_{\text{GUT}}) = \alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi} \approx \frac{1}{53}
$$

Running to low energies gives confinement. The Landau pole (where $\alpha_s$ diverges) occurs at:

$$
\Lambda_{\text{QCD}} = M_{\text{GUT}} \cdot \exp\!\left(-\frac{2\pi}{b_0 \alpha_s(M_{\text{GUT}})}\right)
$$

With $b_0 = 7$ (6 active flavors, SM running) and $\alpha_s(M_{\text{GUT}}) = 1/53$:

$$
\Lambda_{\text{QCD}} \approx 2 \times 10^{16} \cdot \exp\!\left(-\frac{2\pi}{7 \cdot 1/53}\right)
= 2 \times 10^{16} \cdot \exp(-47.6) \approx 0.3\ \text{MeV}
$$

The $\Lambda_{\text{QCD}}$ estimate here uses the $\alpha_s$-at-$M_{\text{GUT}}$
form of the pole condition; the equivalent Z-pole statement is the running
coupling itself (`standard-model/sm-radiative-corrections.md` §3.2):

| Running scheme | $\alpha_s(m_Z)$ predicted | vs measured 0.1180 |
|:--------------|:--------------------------|:-------------------|
| 1-loop SM ($n_f=6$, thresholds) | 0.058 | $2.0\times$ low |
| 2-loop QCD + thresholds | 0.061 | $1.9\times$ low |

**Cassi prediction for $\alpha_s(m_Z)$:** the φ-boundary coupling
$\alpha_s = \varphi^{-3}/(4\pi)$ runs to $\alpha_s(m_Z) \approx 0.058$–$0.061$,
$2.0\times$ below the measured 0.118. Closing the gap requires
$\Delta b = 1.70$ of beyond-SM colored content between $m_Z$ and
$M_{\text{GUT}}$ (vector-like quark doublet at the cascade Fibonacci
precursor; `computations/cascade_gut_ew_rge.py`). Two-loop running and
threshold corrections shift the prediction by a few percent—they do not
close a factor of two.

### 5.3 Proton Mass from φ

The QCD scale $\Lambda_{\text{QCD}}$ determines the proton mass via dimensional transmutation:

$$
m_p \approx 3 \Lambda_{\text{QCD}} \quad \text{(up to chiral corrections)}
$$

The φ-boundary running ($\alpha_s(m_Z) = 0.058$–$0.061$, §5.2) gives a
$\Lambda_{\text{QCD}}$ two orders of magnitude below 200 MeV—the same
$2.0\times$ $\alpha_s$ deficit expressed in the scale. The standard
derivation $m_p \approx 938$ MeV uses the *measured* $\Lambda_{\text{QCD}}
\approx 200$ MeV as input (E-class, `parameter-inventory.md` §4); the
φ-scaled estimate $m_p \approx \varphi^3\Lambda_{\text{QCD}} \approx 847$ MeV
follows from that input, not from the GUT boundary.

---

## 6. Running Coupling Constants

### 6.1 Gauge Coupling Unification at $M_{\text{GUT}}$

In the Standard Model the three couplings do **not** meet at a single point
(`computations/sm_radiative_corrections.py` §2): running the measured Z-pole
values up gives $\alpha_1 = \alpha_2$ at $\mu \approx 10^{13}$ GeV
($\alpha^{-1} = 42.4$) and $\alpha_2 = \alpha_3$ at $\mu \approx 10^{17}$ GeV
($\alpha^{-1} = 47.1$). The φ-boundary value $\alpha_{\text{GUT}} =
\varphi^{-3}/4\pi \approx 1/53$ is not realized by any SM coupling at any
scale below $M_{\text{Pl}}$, and the common value 1/53 at $2\times10^{16}$ GeV
claimed in earlier sections is not a property of the SM running. Unification
in Cassi therefore requires beyond-SM content—the same $\Delta b = 1.70$
deficit that rescues $\alpha_s$—or a non-minimal embedding
(`standard-model/gut-embedding.md`).

### 6.2 One-Loop RGEs

The one-loop running for the three gauge couplings:

$$
\frac{d\alpha_i^{-1}}{d\ln\mu} = -\frac{b_i}{2\pi}
$$

where for the Standard Model (including the Higgs doublet):
- U(1)$_Y$: $b_Y = -41/10$ (non-SUSY) or $b_Y = -11$ (MSSM)
- SU(2)$_L$: $b_2 = 19/6$ (non-SUSY) or $b_2 = 1$ (MSSM)
- SU(3)$_c$: $b_3 = 7$ (non-SUSY, $n_f=6$) or $b_3 = -3$ (MSSM)

The running from $M_{\text{GUT}}$ to $m_Z$ at one loop (φ-boundary
$\alpha_i(M_{\text{GUT}}) = \varphi^{-3}/4\pi$ at $10^{16}$ GeV, top-decoupling
threshold):

| Coupling | $M_{\text{GUT}}$ (Cassi) | $m_Z$ (1-loop SM) | Measured |
|:---------|:------------------------|:------------------|:---------|
| $\alpha_1^{-1}$ | 53.2 | 74.3 | 59.0 |
| $\alpha_2^{-1}$ | 53.2 | 36.9 | 29.6 |
| $\alpha_3^{-1}$ | 53.2 | 17.3 | 8.47 |

The φ-boundary does **not** unify at $m_Z$: $\alpha_1$ and $\alpha_2$ come
out ~25% weak and $\alpha_3$ $2.0\times$ weak (the documented $\Delta b =
1.70$ deficit).

### 6.3 Cassi RGE Prediction for $M_{\text{GUT}}$

Running $\alpha_2$ from $m_Z$ up to the value $\alpha_2^{-1} = 53$ requires
$\ln(M_{\text{GUT}}/m_Z) = (2\pi/b_2)(53 - \alpha_2^{-1}(m_Z)) \approx 45.7$,
i.e. $\mu \approx 1.3\times10^{21}$ GeV—**above the Planck scale**. The
φ-boundary weak coupling is not realized at any sub-Planck scale in the SM.

The intersections that do exist (from the measured inputs) are:

$$
\alpha_1 = \alpha_2: \mu = 1.0\times10^{13}\ \text{GeV} \quad (\alpha^{-1} = 42.4),
$$

$$
\alpha_2 = \alpha_3: \mu = 1.0\times10^{17}\ \text{GeV} \quad (\alpha^{-1} = 47.1),
$$

with $\alpha_1$ missing the $\alpha_2 = \alpha_3$ crossing by ~23%. This is
the classic SM non-unification pattern, and it is the quantitative statement
that replaces the earlier "one-loop estimates" paragraph: GUT-scale
thresholds cannot move a 23% gap.

---

## 7. Fermion Mass Hierarchy

In the Standard Model, fermion masses come from Yukawa couplings to the Higgs. In Cassi, the Yukawa couplings are $\varphi$-scaled:

$$
y_f = y_0 \cdot \varphi^{-n_f}
$$

where $n_f$ is a "generation number" ($n=1,2,3$ for the three generations). This gives the mass hierarchy:

| Generation | $n_f$ | $m_f \propto \varphi^{-n}$ | Ratio | Example |
|-----------|-------|---------------------------|-------|--------|
| 1 (up/down) | 3 | $\varphi^{-3} \approx 0.236$ | 1 | $m_u \sim 2$ MeV |
| 2 (charm/strange) | 2 | $\varphi^{-2} \approx 0.382$ | $\times 1.6$ | $m_c \sim 1.3$ GeV |
| 3 (top/bottom) | 1 | $\varphi^{-1} \approx 0.618$ | $\times 2.6$ | $m_t \sim 173$ GeV |

The top quark mass (173 GeV) $\approx \varphi^{-1} \cdot v_0 \approx 0.618 \times 246 \approx 152$ GeV—within 14% of the experimental value.

---

## 8. Summary of Falsifiable Predictions

### Direct Electroweak (FCC-ee testable)

| Observable | SM Value | Cassi Prediction | Deviation | FCC-ee Sensitivity |
|-----------|---------|-----------------|-----------|-------------------|
| $m_W/m_Z$ | 0.8813 | **0.878** (tree 0.874 + $\rho$ correction) | $-0.36\%$ | $>100\sigma$ |
| $m_W$ | 80.360 GeV | **80.07 GeV** | $-0.36\%$ | 0.5 MeV |
| $\sin^2\theta_W$ at $m_Z$ | 0.23122 | **0.236** ($\varphi^{-3}$; exact at $\mu_* = 233$ GeV) | $+2.1\%$ | $3\times10^{-5}$ |

### GUT Scale (Proton decay testable)

| Observable | SM Running | Cassi Boundary |
|-----------|-----------|----------------|
| Unification | $\alpha_1=\alpha_2$ at $10^{13}$ GeV ($\alpha^{-1}\approx 42$); $\alpha_2=\alpha_3$ at $10^{17}$ GeV—no common point | $\alpha_{\text{GUT}} = 1/53$ not realized by any SM coupling below $M_{\text{Pl}}$; requires $\Delta b = 1.70$ beyond-SM content |
| $\alpha_{\text{GUT}}$ | $\sim 1/42$–$1/47$ (partial intersections) | $1/53$ |
| $p \to e^+\pi^0$ lifetime |—| Near Hyper-K reach **if** the beyond-SM content raises $M_{\text{GUT}}$ to $\sim 10^{16}$ GeV (see `standard-model/gut-embedding.md`) |

### Strong Coupling (LHC testable)

| Observable | Measured | Cassi Prediction | Status |
|-----------|---------|-----------------|--------|
| $\alpha_s(m_Z)$ | 0.118 | **0.058–0.061** (1-/2-loop) | $2.0\times$ low; $\Delta b = 1.70$ required |
| $\Lambda_{\text{QCD}}$ | 200 MeV | order-of-magnitude low from φ-boundary | Same deficit |
| $m_p$ | 938 MeV | $\varphi^3 \cdot \Lambda_{\text{QCD}} = 847$ MeV (measured $\Lambda$ input) | Within 10% |

### Hadron Spectrum (Lattice testable)

| Observable | Measured | Cassi ($\varphi$-scaled) | Deviation |
|-----------|---------|-------------------------|-----------|
| $m_t / v_0$ | 0.703 | **0.618** ($\varphi^{-1}$) | $-12\%$ |
| $m_b / m_t$ | 0.025 | **0.031** ($\varphi^{-2}/\varphi^{-1} = \varphi^{-1}$) | $+24\%$ |
| $m_c / m_t$ | 0.0075 | **0.0088** ($\varphi^{-3}/\varphi^{-1} = \varphi^{-2}$) | $+17\%$ |

---

## 9. Open Questions

### 9.1 GUT Group

The Cassi framework embeds SU(3) × SU(2) × U(1) without a unifying GUT group. The natural extension is to SU(5) or SO(10), where the $\varphi$-scaling of couplings at $M_{\text{GUT}}$ provides the symmetry breaking pattern. This would predict the proton decay rate and the GUT-scale Higgs sector. See `standard-model/gut-embedding.md` for the full embedding analysis and proton-decay predictions.

### 9.2 Neutrino Mass

The seesaw mechanism gives neutrino masses:

$$
m_\nu \approx \frac{y_\nu^2 v_0^2}{M_R}
$$

with the right-handed neutrino at cascade step 20, $M_R \approx 10^{14}\ \text{GeV}$. The spectrum follows from the Fibonacci cascade partition of the seesaw span: $m_1 = 0.00356$, $m_2 = 0.00931$, $m_3 = 0.05019\ \text{eV}$ (normal ordering). See `foundations/neutrino-masses.md` and the primer `standard-model/neutrino-mass.md`.

### 9.3 CP Violation

The CKM phase $\delta_{\text{CKM}} \approx 68^\circ$ in the SM. In the Cassi
framework, the $\phi$-scaled CKM element hierarchy ($|V_{us}| \approx
\varphi^{-3} \approx 0.236$, $5\%$ off from the observed $0.225$;
$|V_{cb}| \approx 0.041$ and $|V_{ub}| \approx 0.004$ follow the Wolfenstein
hierarchy $|V_{cb}| \sim \lambda^2$, $|V_{ub}| \sim \lambda^3$ with
$\lambda \approx \varphi^{-3}$) closes via the unitarity triangle to give:

$$\delta_{\text{CKM}} = \pi\phi^{-2} \approx 68.7^\circ$$

This matches the SM value within $<1\%$ and is the Cassi prediction for the CP
phase. The CKM hierarchy likely requires additional flavor structure beyond a
single $\phi$-power. See `standard-model/cp-violation.md` for the full derivation.

## References

- `standard-model/sm-radiative-corrections.md`—full derivation of the loop corrections
- `standard-model/cp-violation.md`—CKM phase derivation
- `standard-model/gut-embedding.md`—SU(5)/SO(10) embedding, proton decay
- `standard-model/neutrino-mass.md`—seesaw primer and canonical spectrum
- `foundations/neutrino-masses.md`—Fibonacci cascade-partition derivation
- `foundations/dimensionful-cascade.md`—GUT rung anchors
