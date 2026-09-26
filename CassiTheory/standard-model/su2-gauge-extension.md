# SU(2) × U(1) Gauge Extension of the Cassi Two-Fluid

## Status: Derived SU(2) gauge algebra and mass matrix; Hypothesized density-to-isospinor, chiral/flavor observation map and coupling-normalization candidate with asserted Weinberg boundary; Mapped conditional CKM phase—August 2026

## Abstract

The canonical two-fluid state is the pair of real nonnegative densities
$E_Y$ and $E_I$, with $\rho=E_Y+E_I$ and
$\varepsilon=E_Y-\varphi E_I$, evolving under a gated rank-one relaxation.
The SU(2) gauge algebra and mass matrix below are Derived for an additional
complex isospinor sector. Mapping $(E_Y,E_I)$ into that sector, assigning a
compact U(1) or SO(2) representation, a conserved electromagnetic current,
chiral or handed matter, or inter-rung transport is **Hypothesized** additional
structure. The exact identity
$\sin^2\theta_W = 1/(1+2\varphi) = \varphi^{-3}
\iff (g/g')^2 = 2\varphi$ is an asserted boundary condition; §3.2.1 tests the
strongest curvature-orbit normalization candidate and identifies the missing
action-level bridge. The mass ratio $m_W/m_Z = \sqrt{1-\varphi^{-3}} \approx
0.874$—2.1% and 0.82% from the Z-pole values, testable at FCC-ee at
$>100\sigma$ under the quoted projected precision. The document sets out the
neutral-boson mass matrix and a conditional SU(3) color extension. Its
$\varphi$-scaled fermion hierarchy and CKM phase are conditional
particle-sector claims requiring a **Hypothesized** complex/chiral/flavor
observation map; the phase candidate is **Mapped** against the SM value and is
not a canonical density derivation. The RG running from the GUT scale is
derived in `standard-model/sm-radiative-corrections.md`: the measured
running angle crosses $\varphi^{-3}$ at $\mu_* \approx 233$ GeV, the
$\varphi$-boundary $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi) \approx 1/53$
does not unify the SM couplings (no common intersection exists in the SM),
and $\alpha_s$ runs to 0.058–0.061 at $m_Z$, $2.0\times$ below the measured
value.

## 1. The SU(2) Isospinor Doublet

The canonical two-fluid state is a pair of real nonnegative densities
$(E_Y,E_I)$. Its conversion sector conserves
$\rho=E_Y+E_I$ and relaxes
$\varepsilon=E_Y-\varphi E_I$ through the gated rank-one law
$\partial_tE_Y|_{\mathrm{conv}}=-\lambda(1-q)\varepsilon$,
$\partial_tE_I|_{\mathrm{conv}}=+\lambda(1-q)\varepsilon$. The local
density-plane diagnostics
$$
\theta_d=\operatorname{atan2}(E_I,E_Y),\qquad
J_{d,z}=E_Y\,\partial_zE_I-E_I\,\partial_zE_Y
       =\rho_{\mathrm{plane}}^2\partial_z\theta_d,\qquad
\rho_{\mathrm{plane}}^2=E_Y^2+E_I^2
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
with a chosen spatial projection. They do not add a compact phase, chirality,
handedness, or inter-rung current. Transport between
$\ell_n$ and $\ell_{n+1}$ requires a separate **Hypothesized** constitutive
law with an added flux or boundary term
(`foundations/qi-flow-double-helix.md` §2).

**Derived gauge algebra.** The electroweak construction below uses an
additional complex SU(2) isospinor on which the standard
SU(2)$_L \times$ U(1)$_Y$ algebra acts:

$$
\Psi = \begin{pmatrix} \psi_1 \\ \psi_2 \end{pmatrix}
$$

**Hypothesized density-to-isospinor map:** if this additional field sector is
introduced, impose the conditional constitutive identification

$$
|\psi_1|^2 = E_Y,\; |\psi_2|^2 = E_I
$$

Under this **Hypothesized** map, the complex field is the candidate Higgs
doublet. The canonical density pair supplies component magnitudes only; it
does not supply a compact phase, a chiral matter representation, a handed
direction, or an electromagnetic current. The candidate vacuum expectation
value at the $\varphi$-equilibrium is:

$$
\langle \Psi \rangle = \frac{1}{\sqrt{\varphi+1}} \begin{pmatrix} \sqrt{\varphi} \\ 1 \end{pmatrix} v_0
$$

where $v_0$ is the electroweak scale (246 GeV in the Standard Model). Within
this extension, the $\varphi$-equilibrium ratio $E_Y/E_I = \varphi$ is the
VEV input that fixes the $\sqrt{\varphi}:1$ splitting; it is not a compact-group
or chirality property of the canonical densities.

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

## 3. Weinberg-angle identity and neutral mass matrix

### 3.1 The $\varphi$-VEV and the Neutral Boson Mass Matrix

At the $\varphi$-equilibrium, the isospinor VEV is:

$$
\langle \Psi \rangle = \frac{v}{\sqrt{\varphi+1}} \begin{pmatrix} \sqrt{\varphi} \\ 1 \end{pmatrix}
$$

The fixed-point VEV is written in a gauge where both $W^1$ and $W^3$ can mix
with $B$. Let $T_a = \sigma_a/2$, $Y=I_2/2$, and
$n = (\sqrt{\varphi},1)^T/\sqrt{\varphi+1}$. The relevant expectation values are

$$
\langle T_1\rangle_n = \frac{\sqrt{\varphi}}{\varphi+1},
\qquad \langle T_2\rangle_n = 0,
\qquad \langle T_3\rangle_n = \frac{\varphi-1}{2(\varphi+1)}.
$$

Define

$$
a \equiv \frac{2\sqrt{\varphi}}{\varphi+1},
\qquad \kappa \equiv \frac{\varphi-1}{\varphi+1} = \varphi^{-3}.
$$

The complete gauge-boson mass matrix in the $(W^1,W^2,W^3,B)$ basis, in
$v^2/4$ units, is

$$
M^2 = \frac{v^2}{4}
\begin{pmatrix}
g^2 & 0 & 0 & a gg' \\
0 & g^2 & 0 & 0 \\
0 & 0 & g^2 & \kappa gg' \\
a gg' & 0 & \kappa gg' & g'^2
\end{pmatrix}.
$$

The two fixed-point coefficients satisfy

$$
a^2 + \kappa^2
= \frac{4\varphi + (\varphi-1)^2}{(\varphi+1)^2} = 1.
$$

Consequently the spectrum is

$$
\operatorname{spec}(M^2) = \frac{v^2}{4}\{g^2,g^2,0,g^2+g'^2\}.
$$

The photon null vector is proportional to $(g'a,0,g'\kappa,-g)$, and the
orthogonal SU(2) direction $aW^1+\kappa W^3$ mixes with $B$ through the usual
$2\times2$ matrix. The physical angle therefore remains
$\sin^2\theta_W = g'^2/(g^2+g'^2)$. The $\varphi$-VEV rotates the SU(2) axis
that participates in neutral mixing; it supplies no equation for the relative
gauge coupling.

### 3.2 The Weinberg Angle as a Coupling-Ratio Identity

In the Standard Model the Weinberg angle is fixed by the *diagonal* ratio of the neutral mass matrix, $g'^2/(g^2+g'^2)$; the VEV asymmetry does not appear in it. The $\varphi$-anchoring $\sin^2\theta_W = \varphi^{-3}$ is therefore a statement about the *coupling ratio*, not about the rotation of the VEV-weighted matrix, and the two forms are exactly equivalent:

$$
\boxed{\sin^2\theta_W = \varphi^{-3}
\iff \tan^2\theta_W = \frac{g'^2}{g^2} = \frac{\varphi^{-3}}{1-\varphi^{-3}}
= \frac{1}{\varphi^3-1} = \frac{1}{2\varphi}
\iff \left(\frac{g}{g'}\right)^2 = 2\varphi}
$$

The steps use the Fibonacci identity $\varphi^3 = 2\varphi + 1$ (so $\varphi^3 - 1 = 2\varphi$) and the equivalent forms $\varphi^{-3} = 1/(2\varphi+1) = (\varphi-1)/(\varphi+1)$. The boundary condition is thus the coupling-ratio identity $(g/g')^2 = 2\varphi$, equivalently $\sin^2\theta_W = 1/(1+2\varphi)$. Verified numerically (`computations/weinberg_phi_identity.py`): $\varphi^{-3} = 0.236068$, $\tan^2\theta_W = 0.309017 = \varphi^{-1}/2$, $g'/g = \sqrt{1/(2\varphi)} = 0.5559$; the measured Z-pole value $g'/g = \sqrt{0.23122/0.76878} = 0.5484$ sits $+1.36\%$ below it (equivalently $\sin^2\theta_W$ $+2.10\%$ above $0.23122$).

The full matrix in §3.1 supplies the gauge-consistent neutral sector. Since
$a^2+\kappa^2=1$, its spectrum is

$$
\frac{v^2}{4}\{g^2,g^2,0,g^2+g'^2\},
$$

with photon null vector $(g'a,0,g'\kappa,-g)$. The SU(2) direction
$aW^1+\kappa W^3$ is the one that mixes with $B$, and its $2\times2$ matrix
has the usual diagonal coupling ratio. The physical angle remains
$\sin^2\theta_W = g'^2/(g^2+g'^2)$; the VEV orientation supplies the axis
rotation and leaves the relative coupling undetermined. The full calculation
is verified in `computations/weinberg_phi_identity.py`.

**Status: asserted boundary condition; blocking step.** The assignment
$\sin^2\theta_W = \varphi^{-3}$ is exactly equivalent to
$(g/g')^2 = 2\varphi$ at the $\varphi$-boundary. The unified Lagrangian
assigns $g^2 = 2\varphi\,g'^2$ at its chosen normalization; the current action
contains no mechanism relating the two gauge kinetic coefficients. Equal
Wu Xing boundary values would give $g=g'$ and $\sin^2\theta_W=1/2$. The
curvature–orbit candidate in §3.2.1 supplies a conditional route only after
adding a field-space metric and an orbit-matching rule. The relative coupling
normalization remains open.

### 3.2.1 Conditional Curvature–Orbit Closure Attempt

The strongest two-fluid candidate uses the attractor's local restoring stiffness to normalize gauge orbits. Write
$\Delta = \Psi_Y^2 - \varphi\Psi_I^2$ and
$V_{\text{attr}} = \lambda\Delta^2/2$. At the fixed point, the diagonal curvatures are

$$
K_Y = \left.\frac{\partial^2 V_{\text{attr}}}{\partial\Psi_Y^2}\right|_* = 4\lambda\Psi_{Y,*}^2,
\qquad
K_I = \left.\frac{\partial^2 V_{\text{attr}}}{\partial\Psi_I^2}\right|_* = 4\lambda\varphi^2\Psi_{I,*}^2,
\qquad \frac{K_I}{K_Y} = \varphi.
$$

Use $K_r = \operatorname{diag}(1,r)$, $T_a = \sigma_a/2$ for the three SU(2) generators, $Y = I_2/2$, and the normalized fixed-point VEV $\Psi_* \propto (\sqrt{\varphi},1)^T$. The orbit-cost ratio is

$$
R(r) = \frac{\sum_{a=1}^3 (T_a\Psi_*)^\dagger K_r(T_a\Psi_*)}{(Y\Psi_*)^\dagger K_r(Y\Psi_*)}
     = \frac{2+\varphi+r(2\varphi+1)}{\varphi+r}.
$$

The equation $R(r)=2\varphi$ selects $r=\varphi$ exactly. If one adds the matching condition

$$
\frac{S_{\mathrm{SU(2)}}(K_\varphi)}{g^2} = \frac{S_Y(K_\varphi)}{g'^2},
$$

the asserted relation follows: $\boxed{(g/g')^2 = R(\varphi) = 2\varphi}$. This is a useful candidate because its $\varphi$ factor traces to the attractor curvature and its integer factor traces to the SU(2) orbit.

The current action contains the identity field-space metric (`foundations/unified-lagrangian.md` §1.1) and independent gauge coefficients $1/g^2$ and $1/g'^2$ (§4.1). Its attractor potential singles out the Yang/Yin axes, so the SU(2) promotion requires a gauge-fixed or effective-potential interpretation. With the canonical metric, the full-generator ratio is $R(1)=3$; the transverse pair gives 2; other generator or hypercharge normalizations give different values. The action supplies no selection rule for the metric, generator subset, charge normalization, or orbit-matching condition. `computations/weinberg_coupling_origin_audit.py` verifies these counterfactuals. The curvature–orbit route is therefore a **Hypothesized candidate**, not a closure of the asserted boundary.

The full mass matrix resolves the photon null direction for the displayed VEV; the
remaining blocker is the action-level origin of the relative gauge coupling. A
gauge-equivalent choice of VEV orientation gives the usual neutral basis, while
the fixed-point asymmetry remains a field-space orientation.

The coupling ratio follows from the boundary condition:

$$
\frac{g'^2}{g^2} = \frac{\sin^2\theta_W}{1 - \sin^2\theta_W} = \frac{\varphi^{-3}}{1 - \varphi^{-3}} = \frac{1}{2\varphi} \approx 0.309
$$

$$
\frac{g'}{g} = \sqrt{0.309} \approx 0.556
$$

### 3.3 Comparison with Experiment

| Quantity | Cassi (tree) | Measured (Z-pole) | Gap |
|----------|-------------------|-------------------|-----|
| $\sin^2\theta_W$ | $0.23607$ | $0.23122(4)$ | $+2.1\%$ |
| $\tan\theta_W = g'/g$ | $0.556$ | $0.5484$ (from $0.23122$) | $+1.4\%$ |
| $m_W/m_Z = \cos\theta_W$ | $0.874$ | $0.881$ | $-0.82\%$ |

The weak mixing angle runs **upward** with energy, so the 2.1% gap at the
Z-pole is not closed by running to lower energies—the $\varphi$-point value is
realized at $\mu_* \approx 233$ GeV, about one e-fold above $m_Z$
(`standard-model/sm-radiative-corrections.md` §3.3). The mass-ratio gap is
partially closed by the $\rho$ radiative correction (0.874 → 0.878, −0.36%).
Neither discrepancy is absorbed by the displayed tree-level or $\rho$-corrected
relations; both are testable under the quoted FCC-ee precision.

### 3.4 RG Running

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
  $\mu_* \approx 233$ GeV—the correct statement of the $\varphi$-anchoring.
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
## 5. Conditional SU(3) color extension

### 5.1 Conditional tripled field

Within the additional particle-sector extension, color is represented by a
tripled field:

$$
\Psi_{\text{color}} = \begin{pmatrix} \psi_r \\ \psi_g \\ \psi_b \end{pmatrix}
$$

where each component is an SU(2) doublet carrying electroweak quantum
numbers. The SU(3) gauge covariant derivative is

$$
D_\mu \Psi_{\text{color}} =
\left(\partial_\mu - i g_s \mathbf{G}_\mu \cdot
\frac{\boldsymbol{\lambda}}{2}\right)\Psi_{\text{color}},
$$

where $\mathbf{G}_\mu^a$ ($a = 1, \dots, 8$) are the gluon fields and
$\boldsymbol{\lambda}$ are the Gell-Mann matrices. This color sector is not
part of the canonical real-density state.

### 5.2 Conditional QCD running and confinement

The optional SU(3) coupling boundary is

$$
\alpha_s(M_{\text{GUT}}) = \alpha_{\text{GUT}} =
\frac{\varphi^{-3}}{4\pi} \approx \frac{1}{53}.
$$

Running to low energies gives a perturbative scale estimate. The corresponding
pole condition is

$$
\Lambda_{\text{QCD}} = M_{\text{GUT}} \cdot
\exp\!\left(-\frac{2\pi}{b_0\alpha_s(M_{\text{GUT}})}\right).
$$

With $b_0 = 7$ (6 active flavors, SM running) and
$\alpha_s(M_{\text{GUT}})=1/53$:

$$
\Lambda_{\text{QCD}} \approx 2\times10^{16}\cdot
\exp\!\left(-\frac{2\pi}{7\cdot1/53}\right)
:=2\times10^{16}\cdot\exp(-47.6)\approx0.044\ \text{MeV}.
$$

The estimate uses the $\alpha_s$-at-$M_{\text{GUT}}$ pole form; the equivalent
Z-pole running comparison is
(`standard-model/sm-radiative-corrections.md` §3.2):

| Running scheme | $\alpha_s(m_Z)$ from boundary | vs measured 0.1180 |
|:--------------|:------------------------------|:-------------------|
| 1-loop SM ($n_f=6$, thresholds) | 0.058 | $2.0\times$ low |
| 2-loop QCD + thresholds | 0.061 | $1.9\times$ low |

**Boundary comparison for $\alpha_s(m_Z)$:** the $\varphi$-boundary coupling
runs to $\alpha_s(m_Z)\approx0.058$–$0.061$, $2.0\times$ below the measured
0.118. Closing the gap requires $\Delta b=1.70$ of beyond-SM colored content
between $m_Z$ and $M_{\text{GUT}}$; the fit-status ledger records several
incompatible realizations and selects none. Two-loop running and threshold
corrections shift the boundary comparison by a few percent; they do not close
the factor-of-two deficit.

### 5.3 Proton mass scale comparison

The QCD scale enters the proton mass through dimensional transmutation, but
the canonical framework does not derive the nonperturbative mass. The
conventional scale relation

$$
m_p \approx 3\Lambda_{\text{QCD}}\quad\text{(up to chiral corrections)}
$$

uses $\Lambda_{\text{QCD}}\approx200$ MeV as an external scale. The displayed
boundary pole estimate is $\sim0.044$ MeV, roughly four orders of magnitude
below that scale, reflecting the boundary-coupling deficit. A numerical
$\varphi$ comparison,

$$
m_p \stackrel{\text{comparison}}{\approx}
\varphi^3\Lambda_{\text{QCD}}\approx847\ \text{MeV},
$$

uses the measured $\Lambda_{\text{QCD}}$ and is not a proton-mass derivation.
The proton mass remains class **E** in `parameter-inventory.md` §4.

---

## 6. Running Coupling Constants

### 6.1 Gauge Coupling Unification at $M_{\text{GUT}}$

In the Standard Model the three couplings do **not** meet at a single point
(`computations/sm_radiative_corrections.py` §2): running the measured Z-pole
values up gives $\alpha_1 = \alpha_2$ at $\mu \approx 10^{13}$ GeV
($\alpha^{-1} = 42.4$) and $\alpha_2 = \alpha_3$ at $\mu \approx 10^{17}$ GeV
($\alpha^{-1} = 47.1$). The $\varphi$-boundary value
$\alpha_{\text{GUT}}=\varphi^{-3}/4\pi\approx1/53$ is not realized
simultaneously by all three SM couplings at any sub-Planck scale. Individual
couplings can cross $1/53$ at other scales, but a common value $1/53$ at
$2\times10^{16}$ GeV is not an SM-running result. Unification in Cassi
requires beyond-SM content—the same $\Delta b=1.70$ deficit that rescues
$\alpha_s$—or a non-minimal embedding (`standard-model/gut-embedding.md`).

### 6.2 One-Loop RGEs

The one-loop running for the three gauge couplings is

$$
\frac{d\alpha_i^{-1}}{d\ln\mu}=-\frac{b_i}{2\pi}.
$$

For the GUT-normalized $\alpha_1=(5/3)\alpha_Y$, the Standard Model
(including one Higgs doublet) and MSSM coefficients are

- U(1)$_1$: $b_1=41/10$ (SM) or $b_1=33/5$ (MSSM)
- SU(2)$_L$: $b_2=-19/6$ (SM) or $b_2=1$ (MSSM)
- SU(3)$_c$: $b_3=-7$ (SM, $n_f=6$) or $b_3=-3$ (MSSM)

The running from $M_{\text{GUT}}$ to $m_Z$ at one loop ($\varphi$-boundary
$\alpha_i(M_{\text{GUT}})=\varphi^{-3}/4\pi$ at $10^{16}$ GeV, top-decoupling
threshold):

| Coupling | $M_{\text{GUT}}$ (Cassi) | $m_Z$ (1-loop SM) | Measured |
|:---------|:------------------------|:------------------|:---------|
| $\alpha_1^{-1}$ | 53.2 | 74.3 | 59.0 |
| $\alpha_2^{-1}$ | 53.2 | 36.9 | 29.6 |
| $\alpha_3^{-1}$ | 53.2 | 17.3 | 8.47 |

The $\varphi$-boundary does **not** unify at $m_Z$: $\alpha_1$ and
$\alpha_2$ come out ~25% weak and $\alpha_3$ $2.0\times$ weak (the
documented $\Delta b=1.70$ deficit).

### 6.3 Conditional RGE scale comparison


Running $\alpha_2$ from $m_Z$ up to the $\varphi$-boundary value
$\alpha_{\text{GUT}}^{-1}\approx53.2$ uses the SM coefficient
$b_2=-19/6$:

$$
\ln(M_{\text{GUT}}/m_Z)
=-\frac{2\pi}{b_2}\left(53.2-\alpha_2^{-1}(m_Z)\right)
\approx46.8.
$$
i.e. $\mu\approx2.0\times10^{22}$ GeV—well above the Planck scale. The
$\varphi$-boundary weak coupling is not realized at any sub-Planck scale in
the SM.

The intersections that do exist (from the measured inputs) are:

$$
\alpha_1 = \alpha_2: \mu = 1.0\times10^{13}\ \text{GeV} \quad (\alpha^{-1} = 42.4),
$$

$$
\alpha_2 = \alpha_3: \mu = 1.0\times10^{17}\ \text{GeV} \quad (\alpha^{-1} = 47.1),
$$

with $\alpha_1$ missing the $\alpha_2=\alpha_3$ crossing by ~23%. This is
the quantitative SM non-unification result; GUT-scale thresholds cannot move
a 23% gap without additional content.

---

## 7. Fermion Mass Hierarchy

In the Standard Model, fermion masses come from Yukawa couplings to the
Higgs. In the Cassi particle-sector extension, the following $\varphi$-scaled
Yukawa ansatz is **Hypothesized** and is **Mapped** only after an explicit
flavor observation map:

$$
y_f = y_0 \cdot \varphi^{-n_f}
$$

where $n_f$ is a "generation number" ($n=1,2,3$ for the three generations).

| Generation | $n_f$ | $m_f \propto \varphi^{-n}$ | Ratio | Example |
|-----------|-------|---------------------------|-------|--------|
| 1 (up/down) | 3 | $\varphi^{-3} \approx 0.236$ | 1 | $m_u \sim 2$ MeV |
| 2 (charm/strange) | 2 | $\varphi^{-2} \approx 0.382$ | $\times 1.6$ | $m_c \sim 1.3$ GeV |
| 3 (top/bottom) | 1 | $\varphi^{-1} \approx 0.618$ | $\times 2.6$ | $m_t \sim 173$ GeV |

The top quark mass (173 GeV) $\approx \varphi^{-1} \cdot v_0 \approx 0.618
\times 246 \approx 152$ GeV is a Mapped conditional comparison within this
particle-sector map; it is not a canonical density derivation.

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

| Observable | Measured | Boundary or conditional value | Status |
|-----------|---------|-----------------|--------|
| $\alpha_s(m_Z)$ | 0.118 | **0.058–0.061** (1-/2-loop) | $2.0\times$ low; $\Delta b = 1.70$ required |
| $\Lambda_{\text{QCD}}$ | 200 MeV | $\sim0.044$ MeV from the displayed $\varphi$-boundary pole estimate | Roughly four orders low |
| $m_p$ | 938 MeV | $\varphi^3 \cdot \Lambda_{\text{QCD}} = 847$ MeV (measured $\Lambda$ input) | Numerical comparison; mass class E, not derived |

### Hadron Spectrum (Lattice testable)

| Observable | Measured | Cassi conditional particle-sector map | Deviation |
|-----------|---------|-------------------------|-----------|
| $m_t / v_0$ | 0.703 | **0.618** ($\varphi^{-1}$) | $-12\%$ |
| $m_b / m_t$ | 0.025 | **0.031** ($\varphi^{-2}/\varphi^{-1} = \varphi^{-1}$) | $+24\%$ |
| $m_c / m_t$ | 0.0075 | **0.0088** ($\varphi^{-3}/\varphi^{-1} = \varphi^{-2}$) | $+17\%$ |

The hadron-spectrum entries are **Mapped** conditional values from the
Hypothesized particle-sector/flavor observation map; they are not derived from
the canonical density pair.

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

The Standard Model CKM phase is $\delta_{\text{CKM}}\approx68^\circ$. The
canonical density pair and its positive-root diagnostics do not supply an
intrinsic CP phase or chiral representation. A **Hypothesized** complex/chiral
particle-sector extension with an explicit flavor observation map may use the
$\varphi$-scaled CKM element hierarchy:

$$
|V_{us}| \approx \varphi^{-3} \approx 0.236
\quad (5\%\ \text{above the observed }0.225),\qquad
|V_{cb}| \approx 0.041,\qquad |V_{ub}| \approx 0.004,
$$

with $|V_{cb}|\sim\lambda^2$, $|V_{ub}|\sim\lambda^3$, and
$\lambda\approx\varphi^{-3}$. Within that explicit map, the **Mapped**
conditional phase candidate is

$$
\delta_{\text{CKM}}=\pi\varphi^{-2}\approx68.7^\circ.
$$

It matches the SM value within $<1\%$ as a conditional comparison. The
candidate requires additional flavor structure beyond a single
$\varphi$-power and is not a phase derived from the canonical density pair.
See `standard-model/cp-violation.md` for the full conditional analysis.

## References

- `standard-model/sm-radiative-corrections.md`—full derivation of the loop corrections
- `computations/weinberg_phi_identity.py`—full VEV mass matrix, photon null direction, and physical mixing angle
- `computations/weinberg_coupling_origin_audit.py`—curvature–orbit candidate and action-level underdetermination audit
- `standard-model/cp-violation.md`—CKM phase derivation
- `standard-model/gut-embedding.md`—SU(5)/SO(10) embedding, proton decay
- `standard-model/neutrino-mass.md`—seesaw primer and canonical spectrum
- `foundations/neutrino-masses.md`—Fibonacci cascade-partition derivation
- `foundations/dimensionful-cascade.md`—GUT rung anchors
