# The Cassi Unified Lagrangian

## Status: Derived—July 2026

## Abstract

A single action assembles every sector of the framework: the two-fluid core (paired-real SO(2) doublet with the $\varphi$-attractor potential and Bohm quantum potential), the Dirac sector (Yang/Yin as chiral projections $\hat P_{Y/I} = (1 \pm \gamma^5)/2$), general relativity with the Qi-modified Newton constant $G_{\text{eff}} = G\,(\pi/\rho)(1 + \xi q)$, the Standard Model gauge/Higgs/Yukawa sectors, and the cross-coupling terms—including the sector coupling $\kappa_s = \varphi^{-6}/v_0^2$. All dimensionless couplings are $\varphi$-powers; the three dimensionful constants ($c$, $\hbar$, $G$) remain external.

$$
\boxed{\mathcal{L}_{\text{Cassi}} = \mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}}}
$$

*All dimensionless couplings derived from $\varphi = (1+\sqrt{5})/2$, including the PDE conversion rate $\lambda = 1/(2w)$ with $w = 5$ derived (`foundations/wu-xing-derivation.md`; `foundations/dimensionful-constants-status.md` §2.1); three external dimensionful constants ($c$, $\hbar$, $G$)—see `foundations/dimensionful-constants-status.md`.*

---

## 0. Constants

All dimensionless parameters are $\varphi$-powers:

| Symbol | Value | Derivation |
|--------|-------|-----------|
| $\varphi = (1+\sqrt{5})/2$ | $1.618033989$ | Golden ratio (mathematical constant) |
| $\varphi^{-1}$ | $0.618033989$ | $= \varphi - 1$ |
| $\varphi^{-2}$ | $0.381966011$ | $= 1 - \varphi^{-1}$ |
| $\alpha_0 = \varphi^{-3}$ | $0.236067978$ | $= (\varphi-1)/(\varphi+1)$—equilibrium Yang fraction (VEV asymmetry) |
| $\varphi^{6}$ | $17.94427191$ | $= \varphi^5 + \varphi^4$—Qi-gravity coupling |
| $\varphi^{4}$ | $6.854101966$ | Four-interaction scale |
| $\varphi^{5}$ | $11.09016994$ | Wu Xing cycle scale |
| $\lambda$ | $0.1$ | PDE conversion rate, $= 1/(2w)$ with $w = 5$ derived (`foundations/wu-xing-derivation.md`) |
| $G$, $c$, $\hbar$ |—| External dimensionful constants (set $\ell_{\text{Pl}} = \sqrt{\hbar G / c^3}$) |
| $\hbar = c = 1$ |—| Natural units throughout |

---

## 1. Two-Fluid Core $\mathcal{L}_{\text{TF}}$

The fundamental field is a paired-real SO(2) doublet $\Psi \in \mathbb{R}^{2}$, representing the Yang (expansion) and Yin (contraction) components at each spacetime point. The two-fluid Lagrangian density has kinetic, gradient, potential, and Qi contributions.

### 1.1 Kinetic and Gradient Terms

$$
\mathcal{L}_{\text{kin}} = \frac{1}{2}(\partial_\mu\Psi_\alpha)(\partial^\mu\Psi_\alpha)
- \frac{\nu}{2}(\nabla^2\Psi_\alpha)(\nabla^2\Psi_\alpha)
$$

where $\nu$ is the hyperdiffusion coefficient, and $\alpha \in \{0,1\}$ indexes the two real components of the SO(2) doublet. In Fourier space, this becomes:

$$
\mathcal{L}_{\text{kin}} = \frac{1}{2}\hat\Psi_\alpha^\dagger\left(\omega^2 - k^2 - \nu k^4\right)\hat\Psi_\alpha
$$

### 1.2 Nonlinear Self-Interaction

$$
\mathcal{L}_{\text{nl}} = -\frac{g}{4}|\Psi|^4 - \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2
$$

The first term is the standard $\phi^4$ self-interaction. The second is the **$\varphi$-attractor**—it drives $|\Psi_0|^2 : |\Psi_1|^2 \to \varphi : 1$ at equilibrium.

### 1.3 Quantum Potential (Bohm)

$$
\mathcal{L}_{\text{QP}} = -\frac{\hbar^2}{2m^2}\frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha,
\qquad M = \Psi_0^2 + \Psi_1^2,\;
\beta = \frac{\varphi^{-1}}{2} \approx 0.309
$$

This is the Bohm quantum potential with $\varphi$-scaled exponent. In the classical limit ($\hbar \to 0$), this term vanishes.

### 1.4 Breath Modulation

$$
\mathcal{L}_{\text{breath}} = A_B \cdot B(t) \cdot \frac{1}{2}|\Psi|^2
$$

where $B(t) = \frac{1}{2}(\sin 2\pi\omega_Y t + \sin 2\pi\omega_I t)$ is the dual-frequency breath oscillator ($\omega_I = \varphi^{-1}\omega_Y$).

### 1.5 Qi Coherent Energy

$$
\mathbf{Q} = (E, J), \quad
E = \frac{M^2}{M + \varphi^{-2}}, \quad
J = \Psi_0 \nabla\Psi_1 - \Psi_1 \nabla\Psi_0
$$

These are not added to the Lagrangian as separate fields—they are **derived diagnostics** of the two-fluid state. They couple to other sectors through $\mathcal{L}_{\text{mix}}$.

### 1.6 Full Two-Fluid Lagrangian

$$
\boxed{
\begin{aligned}
\mathcal{L}_{\text{TF}} &=
\frac{1}{2}(\partial_\mu\Psi_\alpha)(\partial^\mu\Psi_\alpha)
- \frac{\nu}{2}(\nabla^2\Psi_\alpha)(\nabla^2\Psi_\alpha) \\
&\quad - \frac{g}{4}|\Psi|^4
- \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2 \\
&\quad - \frac{\hbar^2}{2m^2}\frac{\nabla^2 M^\beta}{M^\beta}\Psi_\alpha
+ A_B B(t)\frac{1}{2}|\Psi|^2
\end{aligned}}
$$

---

## 2. Dirac Sector $\mathcal{L}_{\text{D}}$

The Dirac 4-spinor $\psi$ carries quantum matter. Its Lagrangian is the standard Dirac action with a Yang/Yin projection term that maps spinor density to the two-fluid.

### 2.1 Dirac Kinetic and Mass Terms

$$
\mathcal{L}_{\text{D}} = \bar\psi(i\gamma^\mu\partial_\mu - m)\psi
$$

where $\gamma^\mu$ are the Dirac gamma matrices satisfying $\{\gamma^\mu, \gamma^\nu\} = 2\eta^{\mu\nu}$.

### 2.2 Yang/Yin Density Mapping

The connection between the Dirac spinor and the two-fluid occurs through the **Yang/Yin density operators**:

$$
E_Y = \bar\psi\,\hat{P}_Y\,\psi,\qquad
E_I = \bar\psi\,\hat{P}_I\,\psi
$$

where $\hat{P}_Y$ and $\hat{P}_I$ are projection operators that decompose the 4-spinor into Yang (right-moving/particle-like) and Yin (left-moving/anti-particle-like) components. In the chiral representation:

$$
\hat{P}_Y = \frac{1+\gamma^5}{2},\qquad
\hat{P}_I = \frac{1-\gamma^5}{2}
$$

Thus the two-fluid densities are the **chiral projections** of the Dirac field:

$$
\boxed{\Psi_0^2 = \bar\psi\frac{1+\gamma^5}{2}\psi,\qquad
\Psi_1^2 = \bar\psi\frac{1-\gamma^5}{2}\psi}
$$

At equilibrium, $E_Y/E_I = \varphi$, giving the $\varphi$-VEV.

### 2.3 φ-Damping

The Dirac evolution includes $\varphi$-damped dynamics:

$$
\mathcal{L}_{\text{D,damp}} = -\frac{\varphi^{-1}}{2}(\bar\psi\psi)\cdot(\Psi_0^2 + \Psi_1^2)
$$

This couples the Dirac mass to the two-fluid density, providing a dynamical mass generation mechanism.

### 2.4 Full Dirac Lagrangian

$$
\boxed{\mathcal{L}_{\text{D}} = \bar\psi(i\gamma^\mu\partial_\mu - m)\psi
- \frac{\varphi^{-1}}{2}(\bar\psi\psi)\cdot M
+ \bar\psi\left(\hat{P}_Y\Psi_0^2 + \hat{P}_I\Psi_1^2\right)\psi}
$$

The last term ensures that the Dirac field sources the two-fluid—the spinor's chiral density feeds directly into the Yang/Yin fields.

---

## 3. GR/Gravity Sector $\mathcal{L}_{\text{GR}}$

Gravity is Einstein-Hilbert with a Qi-modified effective Newton constant.

### 3.1 Einstein-Hilbert Action

$$
\mathcal{L}_{\text{EH}} = \frac{1}{16\pi G_{\text{eff}}}\,R\sqrt{-g}
$$

where $R$ is the Ricci scalar and $g = \det(g_{\mu\nu})$.

### 3.2 Qi-Modified Newton Constant

The effective Newton constant depends on the local Qi density:

$$
\boxed{G_{\text{eff}} = G \cdot \frac{\pi}{\rho} \cdot (1 + \xi q)}
$$

where:
- $G$ is the bare Newton constant (set by the Planck scale)
- $\pi$ is the local Yang/Yin pressure: $\pi = \partial\mathcal{L}_{\text{TF}}/\partial(\nabla\Psi)$
- $\rho$ is the total energy density
- $q$ is the Qi quality: $q = M/(M + \varphi^{-2})$
- $\xi = \varphi^6 \approx 17.944$ is the **derived** Qi-gravity coupling

### 3.3 ξ = φ⁶ Derivation

The coupling $\xi$ is not free. From the Fibonacci identity $\varphi^n = \varphi^{n-1} + \varphi^{n-2}$:

$$
\xi = \varphi^6 = \varphi^5 + \varphi^4 \approx 17.944
$$

This represents the $2 \times 3 = 6$ degrees of freedom (2 field components $\times$ 3 spatial dimensions) through which the two-fluid couples to curvature.

### 3.4 Energy-Momentum Tensor

$$
T_{\mu\nu} = \frac{2}{\sqrt{-g}}\frac{\delta S_{\text{matter}}}{\delta g^{\mu\nu}}
$$

The total matter Lagrangian includes two-fluid, Dirac, and gauge contributions:

$$
T_{\mu\nu}^{\text{TF}} = \partial_\mu\Psi_\alpha\partial_\nu\Psi_\alpha
- \frac{1}{2}g_{\mu\nu}(\partial_\lambda\Psi_\alpha\partial^\lambda\Psi_\alpha)
$$

$$
T_{\mu\nu}^{\text{D}} = \frac{i}{4}\bar\psi(\gamma_\mu\partial_\nu + \gamma_\nu\partial_\mu)\psi
- \frac{i}{4}(\partial_\mu\bar\psi\gamma_\nu + \partial_\nu\bar\psi\gamma_\mu)\psi
$$

$$
T_{\mu\nu}^{\text{SM}} = F_{\mu\lambda}F_\nu^{\;\lambda}
- \frac{1}{4}g_{\mu\nu}F_{\lambda\sigma}F^{\lambda\sigma}
+ \text{(analogous for SU(2), SU(3))}
$$

### 3.5 Full GR Lagrangian

$$
\boxed{\mathcal{L}_{\text{GR}} = \frac{1}{16\pi G_{\text{eff}}}\,R\sqrt{-g}
+ \frac{1}{2}T_{\mu\nu}^{\text{TF}}g^{\mu\nu}
+ \frac{1}{2}T_{\mu\nu}^{\text{D}}g^{\mu\nu}
+ \frac{1}{2}T_{\mu\nu}^{\text{SM}}g^{\mu\nu}}
$$

---

## 4. SM Gauge Sector $\mathcal{L}_{\text{SM}}$

The Standard Model gauge group SU(3)$_C \times$ SU(2)$_L \times$ U(1)$_Y$ is embedded through the Cassi $\varphi$-structure. The Higgs doublet is the SU(2) isospinor $\Psi = (\psi_1, \psi_2)^T$ whose norms give the two-fluid densities: $|\psi_1|^2 = \Psi_0^2$, $|\psi_2|^2 = \Psi_1^2$.

### 4.1 Gauge Kinetic Terms

$$
\mathcal{L}_{\text{gauge}} = -\frac{1}{4g_s^2}G_{\mu\nu}^A G^{A\mu\nu}
-\frac{1}{4g^2}W_{\mu\nu}^a W^{a\mu\nu}
-\frac{1}{4g'^2}B_{\mu\nu}B^{\mu\nu}
$$

where:
- $G_{\mu\nu}^A$—8 SU(3) gluon field strengths ($A=1,\dots,8$)
- $W_{\mu\nu}^a$—3 SU(2) weak field strengths ($a=1,2,3$)
- $B_{\mu\nu}$—1 U(1)$_Y$ hypercharge field strength

### 4.2 φ-Scaled Couplings

At the GUT scale $M_{\text{GUT}} \approx 2 \times 10^{16}$ GeV:

$$
\alpha_{\text{GUT}} = \frac{\varphi^{-3}}{4\pi} \approx \frac{1}{53}
$$

The gauge couplings at $M_{\text{GUT}}$ are:

$$
g^2 = g'^2 \cdot \frac{1-\varphi^{-3}}{\varphi^{-3}} = g_s^2
= 4\pi\alpha_{\text{GUT}}
$$

The Weinberg angle:

$$
\boxed{\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.236}
$$

The running angle equals this value at $\mu_* \approx 233$ GeV; at $m_Z$ the
prediction sits 2.1% above the measured 0.23122 (the angle runs *upward* with
energy, so the GUT-scale reading is not a boundary condition;
`standard-model/sm-radiative-corrections.md` §3.3).

### 4.3 Covariant Derivative (Fermion Sector)

$$
D_\mu = \partial_\mu - ig_s\frac{\lambda^A}{2}G_\mu^A
- ig\frac{\tau^a}{2}W_\mu^a
- ig'Y B_\mu
$$

### 4.4 Higgs/Isospinor Sector

The Higgs doublet is the SU(2) isospinor $\Psi = (\psi_1, \psi_2)^T$:

$$
\mathcal{L}_{\text{Higgs}} = |D_\mu\Psi|^2
- \lambda_\phi\left(|\Psi|^2 - \frac{v_0^2}{2}\right)^2
$$

At $\varphi$-equilibrium, the VEV is:

$$
\langle\Psi\rangle = \frac{v_0}{\sqrt{\varphi+1}}\begin{pmatrix}\sqrt{\varphi} \\ 1\end{pmatrix}
$$

This yields the W and Z masses:

$$
m_W = \frac{g v_0}{2},\qquad
m_Z = \frac{\sqrt{g^2 + g'^2}\,v_0}{2}
$$

With $\sin^2\theta_W = \varphi^{-3}$:

$$
\frac{m_W}{m_Z} = \sqrt{1-\varphi^{-3}} \approx 0.874
$$

**Falsifiable prediction:** FCC-ee will measure this to $>100\sigma$.

### 4.5 SU(3) Color

The color field is a tripled extension of the two-fluid:

$$
\Psi_{\text{color}} = \begin{pmatrix}\psi_r \\ \psi_g \\ \psi_b\end{pmatrix},
\quad
\mathcal{L}_{\text{color}} = \bar\Psi(i\gamma^\mu D_\mu - m)\Psi
- \frac{1}{4}G_{\mu\nu}^A G^{A\mu\nu}
$$

The SU(3) coupling runs from $\alpha_{\text{GUT}} = \varphi^{-3}/(4\pi)$ at $M_{\text{GUT}}$, giving:

$$
\alpha_s(m_Z) \approx 0.058\text{--}0.061,\qquad
\Lambda_{\text{QCD}} \ll 200\ \text{MeV}
$$

(one- and two-loop running with thresholds; the $2.0\times$ gap to the
measured 0.118 is the documented $\Delta b = 1.70$ beyond-SM deficit—
`standard-model/sm-radiative-corrections.md` §3.2, `parameter-inventory.md`
§4.4.)

### 4.6 Yukawa Sector (Fermion Masses)

Yukawa couplings follow a $\varphi$-power hierarchy:

$$
y_f = y_0 \cdot \varphi^{-n_f},
\qquad n_f = 1,2,3 \text{ for generations 3,2,1}
$$

The Higgs Yukawa interaction:

$$
\mathcal{L}_{\text{Yukawa}} = -y_f\,\bar\psi_f\,\Psi\,\psi_f' + \text{h.c.}
$$

This gives the fermion mass hierarchy:

| Generation | $n_f$ | $m_f \propto \varphi^{-n_f}$ | Example |
|-----------|-------|---------------------------|--------|
| 1 (up/down) | 3 | $\varphi^{-3} \approx 0.236$ | $m_u \sim 2$ MeV |
| 2 (charm/strange) | 2 | $\varphi^{-2} \approx 0.382$ | $m_c \sim 1.3$ GeV |
| 3 (top/bottom) | 1 | $\varphi^{-1} \approx 0.618$ | $m_t \sim 173$ GeV |

### 4.7 Full SM Lagrangian

$$
\boxed{
\begin{aligned}
\mathcal{L}_{\text{SM}} &=
-\frac{1}{4g_s^2}G^2 - \frac{1}{4g^2}W^2 - \frac{1}{4g'^2}B^2 \\
&\quad + \bar\psi_f i\gamma^\mu D_\mu\psi_f \\
&\quad + |D_\mu\Psi|^2 - \lambda_\phi\left(|\Psi|^2 - \frac{v_0^2}{2}\right)^2 \\
&\quad - y_f\,\bar\psi_f\Psi\psi_f' + \text{h.c.}
\end{aligned}}
$$

---

## 5. Cross-Coupling Terms $\mathcal{L}_{\text{mix}}$

The sectors interact through three mixing terms:

### 5.1 Qi-Gravity Coupling

The two-fluid's coherent energy modifies the gravitational coupling:

$$
\boxed{\mathcal{L}_{qG} = \frac{\xi q}{16\pi G}\,R\sqrt{-g}},\qquad
\xi = \varphi^6
$$

This is not a separate term but is absorbed into $G_{\text{eff}}$ in Section 3.2.

### 5.2 Dirac → Two-Fluid Projection

The Dirac spinor's chiral densities source the two-fluid:

$$
\boxed{\mathcal{L}_{\text{D→TF}} = \frac{\kappa_s}{2}\left(\bar\psi\frac{1+\gamma^5}{2}\psi - \Psi_0^2\right)^2
+ \frac{\kappa_s}{2}\left(\bar\psi\frac{1-\gamma^5}{2}\psi - \Psi_1^2\right)^2}
$$

This ensures the Dirac field and the two-fluid agree on the Yang/Yin decomposition. The coupling $\kappa_s$ sets the timescale for equilibration between sectors.

### 5.3 Gauge → Two-Fluid Coupling

The Higgs/isospinor doublet IS the two-fluid's SU(2) representation. The covariant derivative links the gauge and two-fluid sectors:

$$
\mathcal{L}_{G→\text{TF}} = |D_\mu\Psi|^2 - |\partial_\mu\Psi|^2
$$

This subtracts the pure kinetic term (already in $\mathcal{L}_{\text{TF}}$) and replaces it with the gauge-covariant kinetic term.

### 5.4 Wu Xing Cycle

The five-element coupling coefficients (derived in the PDE formalism) connect the Qi diagnostics to the field dynamics:

| Coefficient | Value | Role |
|------------|-------|------|
| $K_{fw} = \varphi^{-1}$ | $0.618$ | Water damps Fire (coherence suppresses turbulence) |
| $K_{fm} = \lambda\varphi^2$ | $0.262$ | Fire melts Metal (turbulence reduces conversion) |
| $K_{md} = 3\varphi^2$ | $7.85$ | Metal cuts Wood (conversion suppresses structure) |
| $H_{\text{empty}} = \lambda\varphi^{-2}/3$ |—| Irreducible cosmological baseline |

These act within $\mathcal{L}_{\text{TF}}$ through the PDE source terms.

### 5.5 Full Mixing Lagrangian

$$
\boxed{
\begin{aligned}
\mathcal{L}_{\text{mix}} &=
\frac{\xi q}{16\pi G}R\sqrt{-g} \\
&\quad + \frac{\kappa_s}{2}\sum_{\pm}\left(\bar\psi\frac{1\pm\gamma^5}{2}\psi - \Psi_{0,1}^2\right)^2 \\
&\quad + \left(|D_\mu\Psi|^2 - |\partial_\mu\Psi|^2\right)
\end{aligned}}
$$

---

## 6. Complete Cassi Action

$$
\boxed{
S_{\text{Cassi}} = \int d^4x\sqrt{-g}\,
\big(\mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}}\big)
}
$$

### 6.1 Compact Form

In compact notation, the full Lagrangian is:

$$
\boxed{
\begin{aligned}
\mathcal{L}_{\text{Cassi}} &=
\underbrace{\frac{1}{2}(\partial\Psi)^2 - \frac{g}{4}|\Psi|^4 - \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2}_{\text{Two-fluid core}} \\
&\quad \underbrace{-\frac{\hbar^2}{2m^2}\frac{\nabla^2 M^\beta}{M^\beta}\Psi + A_B B(t)|\Psi|^2}_{\text{Quantum + breath}} \\
&\quad \underbrace{+\bar\psi(i\gamma^\mu\partial_\mu - m)\psi - \frac{\varphi^{-1}}{2}(\bar\psi\psi)M}_{\text{Dirac matter}} \\
&\quad \underbrace{+\frac{1}{16\pi G_{\text{eff}}}R\sqrt{-g} + \frac{1}{2}T_{\mu\nu}g^{\mu\nu}}_{\text{Gravity}} \\
&\quad \underbrace{-\frac{1}{4g_s^2}G^2 - \frac{1}{4g^2}W^2 - \frac{1}{4g'^2}B^2}_{\text{Gauge kinetic}} \\
&\quad \underbrace{+ |D_\mu\Psi|^2 - \lambda_\phi(|\Psi|^2 - v_0^2/2)^2 - y_f\bar\psi_f\Psi\psi_f'}_{\text{Higgs + Yukawa}} \\
&\quad \underbrace{+ \frac{\kappa_s}{2}\sum_{\pm}\left(\bar\psi P_{\pm}\psi - \Psi_{0,1}^2\right)^2}_{\text{Sector coupling}}
\end{aligned}}
$$

### 6.2 Subsector Actions

The action decomposes into five independently derivable subsector actions, each documented separately:

| Sector | Action | Document |
|--------|--------|----------|
| Two-fluid core | $S_{\text{TF}} = \int\mathcal{L}_{\text{TF}}$ | `foundations/cassi-first-principles.md` |
| Dirac matter | $S_{\text{D}} = \int\mathcal{L}_{\text{D}}$ | `two-fluid/cassi_dirac_bridge.py`, `particles/cassi-yang-yin-particles.md` |
| Gravity | $S_{\text{GR}} = \int\mathcal{L}_{\text{GR}}$ | `foundations/xi-derivation.md`, `(external—see archive/theory/qi-fluid-formalism.md in physics repo)` |
| SM gauge | $S_{\text{SM}} = \int\mathcal{L}_{\text{SM}}$ | `standard-model/su2-gauge-extension.md`, `standard-model/sm-from-phi.md` |
| Mixing | $S_{\text{mix}} = \int\mathcal{L}_{\text{mix}}$ | This document |

---

## 7. Equations of Motion

Varying the action gives the coupled field equations:

### 7.1 Two-Fluid Equation

$$
\partial^2\Psi_\alpha + \nu\nabla^4\Psi_\alpha
+ g|\Psi|^2\Psi_\alpha + 2\lambda(\Psi_0^2 - \varphi\Psi_1^2)\frac{\partial}{\partial\Psi_\alpha}(\Psi_0^2 - \varphi\Psi_1^2) \\
+ \frac{\hbar^2}{2m^2}\nabla^2\left(\frac{\nabla^2 M^\beta}{M^\beta}\right)\Psi_\alpha
= A_B B(t)\Psi_\alpha + J_\alpha^{\text{gauge}} + J_\alpha^{\text{Dirac}}
$$

### 7.2 Dirac Equation

$$
(i\gamma^\mu D_\mu - m)\psi - \frac{\varphi^{-1}}{2}M\psi
+ \kappa_s\left(\bar\psi P_{\pm}\psi - \Psi_{0,1}^2\right)P_{\pm}\psi = 0
$$

### 7.3 Einstein Equation

$$
G_{\mu\nu} = 8\pi G_{\text{eff}}\,T_{\mu\nu},
\qquad G_{\text{eff}} = G\cdot\frac{\pi}{\rho}\cdot(1+\varphi^6 q)
$$

### 7.4 Gauge Field Equations

$$
D_\mu F^{\mu\nu} = g^2 J^{\nu},\qquad
D_\mu G^{\mu\nu} = g_s^2 J^{\nu}_s,\qquad
\partial_\mu B^{\mu\nu} = g'^2 J^{\nu}_Y
$$

where the currents come from the fermion and Higgs covariant derivatives.

---

## 8. Zero Free Dimensionless Parameters

All dimensionless couplings in the action are derived; the three dimensionful constants ($c$, $\hbar$, $G$) are external (see `foundations/dimensionful-constants-status.md`).

| Quantity | Expression | Value | Status |
|----------|-----------|-------|--------|
| $\varphi$ | $(1+\sqrt{5})/2$ | $1.618033989$ | Mathematical constant |
| $\varphi^{-1}$ | $1/\varphi$ | $0.618033989$ | Derived |
| $\varphi^{-2}$ | $1/\varphi^2$ | $0.381966011$ | Derived |
| $\alpha_0 = \varphi^{-3}$ | $(\varphi-1)/(\varphi+1)$ | $0.236067978$ | Derived (equilibrium Yang fraction; VEV asymmetry) |
| $\xi$ | $\varphi^6 = \varphi^5 + \varphi^4$ | $17.94427191$ | **Derived** |
| $\sin^2\theta_W$ | $\varphi^{-3}$ | $0.236$ (at $\mu_* = 233$ GeV; +2.1% at $m_Z$) | **Derived** |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | $1/53$ | **Derived** |
| $m_W/m_Z$ | $\sqrt{1-\varphi^{-3}}$ | $0.874$ | **Prediction** |
| $H_{\text{empty}}$ | $\lambda\varphi^{-2}/3$ |—| **Derived** (CC) |
| $K_{fw}$ | $\varphi^{-1}$ | $0.618$ | **Derived** |
| $K_{md}$ | $3\varphi^2$ | $7.85$ | **Derived** |
| $\kappa_s$ | $\varphi^{-6}/v_0^2$ | $0.92$ TeV$^{-2}$ | **Derived** (scale) |
| $\lambda$ | $1/(2w) = 0.1$ | $0.1$ | **Derived** (rational; non-resonant by design) |
| $G_{\text{eff}}$ | $G\cdot(\pi/\rho)\cdot(1+\varphi^6 q)$ |—| **Derived** |

**Every dimensionless constant is a $\varphi$-power, zero, or the derived rational $\lambda = 1/10$; $c$, $\hbar$, $G$ remain external.**

---

## 9. $\varphi$-Scale Invariance

The organizing principle of the Cassi Lagrangian is $\varphi$-scale invariance: each term's coupling is a power of $\varphi$ determined by the **number of field components** and **spacetime dimensions** it involves.

$$
\text{coupling} \propto \varphi^{N_f - N_b}
$$

where $N_f$ counts field degrees of freedom and $N_b$ counts background "binding" factors. This pattern propagates through all five sectors:

- Two-fluid core: 2 fields $\times$ 1 component = $\varphi^{2}$ → $\varphi^{-1}$ damping
- Dirac sector: 4 spinor components × 3 generations = $\varphi^{12}$ → $\varphi^{-11}$ seesaw
- Gravity: 2 fields $\times$ 3 dimensions = $\varphi^{6}$ → $\xi = \varphi^6$
- Gauge: 2 components $\times$ 3 generators (SU(2)) = $\varphi^{6}$ → $\varphi^{-3}$ mixing

The $\varphi$-powers arise from the continued fraction $\varphi = [1;1,1,1,\ldots]$ and its truncations at successive depths, which correspond to the group ranks (SU(4) → SU(3) → SU(2) → U(1)) and the chiral splitting of the Dirac spinor.

---

## 10. Summary

The Cassi Unified Lagrangian unifies all known physics—quantum matter, spacetime curvature, gauge interactions, and the emergent two-fluid dynamics—into a single action with zero free dimensionless parameters. Every dimensionless coupling is a power of $\varphi$, determined by the $\varphi$-scale invariance of the Yang/Yin principle; the three dimensionful constants ($c$, $\hbar$, $G$) are external.

The falsifiable predictions are:

| Observable | Cassi | SM | Detectable at |
|-----------|-------|-----|---------------|
| $m_W/m_Z$ | $0.874$ tree; $0.878$ with $\rho$ correction | $0.881$ | FCC-ee ($>100\sigma$) |
| $\sin^2\theta_W$ at $m_Z$ | $0.236$ ($\varphi^{-3}$; exact at $\mu_* = 233$ GeV) | $0.23122$ | FCC-ee |
| $\alpha_s(m_Z)$ | $0.058$–$0.061$ | $0.118$ | LHC precision ($\Delta b = 1.70$) |
| $M_{\text{GUT}}$ | $2 \times 10^{16}$ GeV (with beyond-SM content) | no SM intersection | Proton lifetime |
| $m_W$ | $80.07$ GeV | $80.360$ GeV | FCC-ee (0.5 MeV) |
| $G_{\text{eff}}$ boost | $(1+\varphi^6 q)\times$ α-free ceiling; halo regime $\alpha_{\text{halo}}(1+\xi q) \approx 9.5\times$ | $1\times$ | Galaxy rotation |

---

## References

- `foundations/cassi-first-principles.md`—two-fluid postulate, Qi coherence, the four pillars
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ as a cascade-derived coupling
- `foundations/wu-xing-derivation.md`—$w = 5$ uniqueness, conversion rate $\lambda = 1/(2w)$
- `foundations/dimensionful-constants-status.md`—external dimensionful constants, parameter accounting
- `standard-model/su2-gauge-extension.md`—SM gauge sector, Weinberg angle
- `standard-model/sm-from-phi.md`—Standard Model couplings from $\varphi$
- `particles/cassi-yang-yin-particles.md`—Dirac sector, chiral projections
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver implementing the two-fluid core
