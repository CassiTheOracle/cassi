# The Cassi Unified Lagrangian

## Status: Hypothesized—August 2026

## Abstract

The canonical Cassi state is the real-density pair $E_Y,E_I\ge 0$ with $\rho=E_Y+E_I$, $\varepsilon=E_Y-\varphi E_I$, canonical gated coherence $q$, and rank-one conversion. This document records a formal action assembly around that core and lists optional sector extensions. The Dirac/particle link—including chiral projectors, particle/antiparticle labels, and any phase or propagation interpretation—is a **Hypothesized** conditional extension; it is not part of the canonical two-fluid derivation. The complex-field/NLS particle construction is likewise conditional. General relativity, Standard Model gauge/Higgs/Yukawa terms, and cross-couplings retain their individual statuses. Structural dimensionless couplings are expressed as $\varphi$-powers or two-fluid inputs where specified; the solver normalization $\lambda = 0.1$ is conventional, and the three dimensionful constants ($c$, $\hbar$, $G$) remain external.

$$
\boxed{\mathcal{L}_{\text{Cassi}} = \mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}}}
$$
The displayed sum is an optional extended-action bookkeeping identity. The canonical two-fluid sector is read through the real-density state and its gated rank-one conversion; $\mathcal{L}_{\text{D}}$, projection terms, and particle-linked portions of $\mathcal{L}_{\text{SM}}$ and $\mathcal{L}_{\text{mix}}$ require the conditional extension.
The q-gated rank-one expression is the selected canonical/theory form. In the
implementation, `TwoFluid3DGPU.rhs` uses ungated $-\lambda\varepsilon$;
`ExpandingTwoFluid3DGPU` defaults to `qi_gate=False` and applies $(1-q)$ only
when `qi_gate=True`. Record `lambda`, `qi_gate`, `gate_model`, and `qi_memory`
with any q-gated receipt.

*Dimensionless couplings are expressed as combinations of $\varphi$ and the
two-fluid inputs; the closed subset carries derived origins, while the
Weinberg coupling boundary remains asserted. The solver-family conversion
parameter defaults to $\lambda=0.02$ in `TwoFluid3DGPU`; $\lambda=0.1$ is a
named experiment convention only where explicitly passed. The relation
$\lambda=1/(2w)$ with $w=5$ is a **Hypothesized** Wu Xing linkage requiring
an independently defined cycle time and dynamical closure. Three external
dimensionful constants ($c$, $\hbar$, $G$) remain external—see
`foundations/dimensionful-constants-status.md`.*

---

## 0. Constants

The listed structural dimensionless parameters are $\varphi$-powers where
specified. The `TwoFluid3DGPU` constructor defaults to $\lambda=0.02$ for
the canonical conversion parameter; $\lambda=0.1$ is a named experiment
convention only where explicitly passed:

| Symbol | Value | Derivation |
|--------|-------|-----------|
| $\varphi = (1+\sqrt{5})/2$ | $1.618033989$ | Golden ratio (mathematical constant) |
| $\varphi^{-1}$ | $0.618033989$ | $= \varphi - 1$ |
| $\varphi^{-2}$ | $0.381966011$ | $= 1 - \varphi^{-1}$ |
| $\alpha_0 = \varphi^{-3}$ | $0.236067978$ | $= (\varphi-1)/(\varphi+1)$—fixed-point imbalance (the Yang fraction is $\varphi^{-1}$; label Mapped, ledger row 500) |
| $\xi=\varphi^{6}$ | $17.94427191$ | $= \varphi^5 + \varphi^4$—exact algebraic identity; physical Qi-gravity coupling identification Calibrated/conditional (Milky Way anchor, ledger row 498) |
| $\varphi^{4}$ | $6.854101966$ | Four-interaction scale |
| $\varphi^{5}$ | $11.09016994$ | Wu Xing cycle scale |
| $\lambda$ | $0.02$ (`TwoFluid3DGPU` default); $0.1$ when explicitly passed | PDE conversion-rate parameter; $\lambda=1/(2w)$ with $w=5$ is a **Hypothesized** Wu Xing linkage requiring independent cycle-time/dynamical closure |
| $G$, $c$, $\hbar$ |—| External dimensionful constants (set $\ell_{\text{Pl}} = \sqrt{\hbar G / c^3}$) |
| $A_B$, $\omega_Y$ |—| Breath coupling and frequency: external dimensionful, unset (the localization—21, Hypothesized; the composite reading, 21 §2.4, would eliminate them) |
| $\hbar = c = 1$ |—| Natural units throughout |

---

## 1. Two-Fluid Core $\mathcal{L}_{\text{TF}}$

The canonical state is the real-density pair $E_Y,E_I\ge 0$, with $\rho=E_Y+E_I$, the signed density imbalance $\pi\equiv E_Y-E_I$, and $\varepsilon=E_Y-\varphi E_I$. Thus $\rho$ and $\pi$ have energy-density units, while $\pi/\rho$ is dimensionless. The thermodynamic pressure is denoted $P_{\mathrm{TF}}$ and is the isotropic spatial stress, with the same units as $\rho$; a gradient-conjugate quantity is separately $\boldsymbol{\Pi}_{\alpha}\equiv\partial\mathcal{L}_{\mathrm{TF}}/\partial(\nabla\Psi_\alpha)$. The formal real components $\Psi_\alpha$ in this action are a positive-root lift where needed for density expressions. The canonical conversion is gated rank-one relaxation; it is not an SO(2) generator and supplies no complex phase or propagation direction. The amplitude-action lift adds kinetic, gradient, potential, and the optional QP term described in §1.3; the canonical density PDE is represented by the density variables and gated rank-one conversion.

### 1.1 Kinetic and Gradient Terms

$$
\mathcal{L}_{\text{kin}} = \frac{1}{2}(\partial_\mu\Psi_\alpha)(\partial^\mu\Psi_\alpha)
- \frac{\kappa_4}{2}(\nabla^2\Psi_\alpha)(\nabla^2\Psi_\alpha)
$$

This fourth-order term belongs only to the optional positive-root
amplitude/action lift. Here $\kappa_4$ is its hyperdiffusion coefficient,
unrelated to the canonical solver's $\nu$, which denotes velocity viscosity.
The index $\alpha \in \{0,1\}$ labels the two real components used by the
formal lift. In Fourier space, this becomes:

$$
\mathcal{L}_{\text{kin}} = \frac{1}{2}\hat\Psi_\alpha^\dagger\left(\omega^2 - k^2 - \kappa_4 k^4\right)\hat\Psi_\alpha
$$

### 1.2 Nonlinear Self-Interaction

$$
\mathcal{L}_{\text{nl}} = -\frac{g}{4}|\Psi|^4 - \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2
$$

The first term is the standard $\phi^4$ self-interaction. The second is the **$\varphi$-attractor**—it drives $|\Psi_0|^2 : |\Psi_1|^2 \to \varphi : 1$ at equilibrium.

### 1.3 Quantum Potential (optional amplitude-action closure—Derived conditional/Hypothesized—August 2026)

The Bohm-like expression below belongs to the optional amplitude-action lift.
It is **Derived conditional** on choosing this amplitude closure and
**Hypothesized** as a physical extension; the canonical density PDE is stated
directly in $E_Y,E_I$ and does not contain this operator. Because the
expression carries a free component index, it is an indexed operator term,
not a scalar Lagrangian density:

$$
\mathcal{Q}_{\mathrm{QP},\alpha}
=-\frac{\hbar^2}{2m^2}\frac{\nabla^2\rho^\beta}{\rho^\beta}\Psi_\alpha,
\qquad
\rho\equiv E_Y+E_I=\Psi_0^2+\Psi_1^2\ \text{under the formal lift},\qquad
\beta=\frac{\varphi^{-1}}{2}\approx0.309.
$$

An additional contraction or scalar completion would be required before
including this operator in a scalar action. In the classical limit
($\hbar\to0$), it vanishes.

### 1.4 Breath Modulation (optional conditional extension—Hypothesized—August 2026)

$$
\mathcal{L}_{\text{breath}} = A_B \cdot B(x,t) \cdot \frac{1}{2}|\Psi(x,t)|^2
$$

Within this optional extension, $B(x,t) = \frac{1}{2}\big(\sin\theta_Y(x,t) + \sin\theta_I(x,t)\big)$ is a local dual-frequency breath field, with the phases carried by each region's own clock:

$$
\dot\theta_{Y,I}(x,t) = 2\pi\,\omega_{Y,I}\,\mathcal{R}(x,t), \qquad \mathcal{R}(x,t) \equiv \frac{1-q(x,t)}{1-q_0}, \qquad (1-q_0) = \varphi^{-2}/3, \qquad \omega_I = \varphi^{-1}\omega_Y
$$

Within this optional extension, every region breathes on its own rung-clock
(the gate openness $(1-q)(x)$; the rung-advancement rate
$dn/dt\approx(\lambda/2\pi)(1-q)$, `foundations/spiral-dynamics.md` §2.1;
the arrow's stiffness, `consciousness/time-memory-and-wake-locks.md` §6).
The homogeneous limit $q(x,t)=q_0$ recovers the global form $B(t)$ exactly,
and $B$ has zero time mean by construction. Because the coupling contains
$B(x,t)|\Psi(x,t)|^2$, the coupled response can correlate with $B$; net
energy density and stress/backreaction therefore require solving the coupled
system and are not derived from the zero mean alone. $A_B$ and $\omega_Y$
remain external dimensionful constants, unset (21 §1.2); the alternative
H-clock normalization $\mathcal{R}=H(x)/\bar H$ is an open variant, locked to
the rung-clock at $r=\varphi$ by the clock identity
(`foundations/spiral-dynamics.md` §2.2) and differing off it (12 §1.5).

### 1.5 Optional Qi Coherent-Power Diagnostic (formal current lift—Derived conditional/Hypothesized)
The canonical dynamical state is the density pair $(E_Y,E_I)$, and $q$ is the derived scalar coherence diagnostic from $\rho$ and $\varepsilon$. The positive-root lift may define the optional bookkeeping pair $\mathbf{Q}_{\mathrm{lift}}=(\rho,J_\Psi)$ (theory-reference §2.4); it is not a canonical state variable or an independent field. The optional construction below is a distinct coherent-power diagnostic, with its first component defined only in the $\varepsilon^2\to0$ equilibrium limit.

$$
\mathbf{Q}_{\mathrm{pow}} = (E_{\mathrm{pow}}, J_\Psi), \quad
E_{\mathrm{pow}} = q\,M_{\mathrm{Qi}}\quad(\varepsilon^2\to0), \quad
M_{\mathrm{Qi}} \equiv \rho^2 = (\Psi_0^2 + \Psi_1^2)^2, \quad
J_\Psi = \Psi_0 \nabla\Psi_1 - \Psi_1 \nabla\Psi_0
$$

The canonical Qi coherence is computed from the local density state (theory-reference §2.4):
$q = \rho^2/(\rho^2 + \varphi^{-2} + \varepsilon^2)$ with
$\varepsilon = E_Y-\varphi E_I$, $\rho=E_Y+E_I$, and
$M_{\mathrm{Qi}}\equiv\rho^2$ as the solver's field power.
The formal lift uses $E_Y=\Psi_0^2$ and $E_I=\Psi_1^2$ where those real roots are introduced; it does not add a phase, chirality, or propagation sector. At the $\varphi$-equilibrium
($\varepsilon \to 0$) the coherence reduces to
$q = M_{\mathrm{Qi}}/(M_{\mathrm{Qi}} + \varphi^{-2})$, so

$$
E_{\mathrm{pow}} = \frac{M_{\mathrm{Qi}}^2}{M_{\mathrm{Qi}} + \varphi^{-2}}
 = \frac{\rho^4}{\rho^2 + \varphi^{-2}}
 = q\,M_{\mathrm{Qi}}
\qquad (\varepsilon^2 \to 0)
$$

The coherent fraction of the field power is verified numerically (`computations/q_form_inventory_check.py`). The displayed $J_\Psi$ is a formal real-field current lift; the canonical density equations use the gated rank-one conversion and do not require this current.
Here “gated rank-one conversion” denotes the selected canonical/theory form or
the optional `ExpandingTwoFluid3DGPU(qi_gate=True)` mode; the base
`TwoFluid3DGPU.rhs` and expanding default are ungated.
The optional positive-root lift bookkeeping pair uses the bare density as magnitude, $\mathbf{Q}_{\mathrm{lift}} = (\rho, J_\Psi)$; the optional diagnostic above uses the equilibrium-gated power $E_{\mathrm{pow}}=q\,M_{\mathrm{Qi}}=q\rho^2$ only at $\varepsilon^2\to0$.
These are optional coherent-power diagnostics of the two-fluid density state, not canonical state variables.
Cross-sector coupling through $\mathcal{L}_{\text{mix}}$ belongs to the optional extended action.

### 1.6 Formal Two-Fluid Action Lift

The displayed action lift includes the canonical real-component terms and the
optional breath extension. The componentwise quantum-potential operator from
§1.3 is not included in this scalar action; it remains an optional operator
ansatz until a scalar contraction or completion is declared. The optional
amplitude-lift coefficient $\kappa_4$ remains distinct from the canonical
solver's $\nu$, which denotes velocity viscosity.

The implementation distinction remains: q-gated conversion is optional
(`ExpandingTwoFluid3DGPU(qi_gate=True)`), while the base and default-off paths
are ungated.

$$
\boxed{
\begin{aligned}
\mathcal{L}_{\text{TF}}
&= \frac{1}{2}(\partial_\mu\Psi_\alpha)(\partial^\mu\Psi_\alpha)
   - \frac{\kappa_4}{2}(\nabla^2\Psi_\alpha)(\nabla^2\Psi_\alpha) \\
&\quad - \frac{g}{4}|\Psi|^4
   - \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2 \\
&\quad + \underbrace{A_B B(x,t)\frac{1}{2}|\Psi|^2}_{\text{optional breath extension}}
\end{aligned}}
$$

---

## 2. Optional Dirac/Particle Extension $\mathcal{L}_{\text{D}}$ (Hypothesized—August 2026)

An optional conditional extension adds the Dirac 4-spinor $\psi$ as quantum matter. Its Lagrangian is the standard Dirac action with a proposed Yang/Yin projection term; this sector is external to the canonical density derivation.

### 2.1 Dirac Kinetic and Mass Terms

$$
\mathcal{L}_{\text{D}} = \bar\psi(i\gamma^\mu\partial_\mu - m)\psi
$$

where $\gamma^\mu$ are the Dirac gamma matrices satisfying $\{\gamma^\mu, \gamma^\nu\} = 2\eta^{\mu\nu}$.

### 2.2 Yang/Yin Density Mapping

Within the optional extension, a proposed formal, unnormalized connection between the Dirac spinor and the two-fluid uses **Yang/Yin density operators**. In natural units $[\bar\psi\hat P\psi]=[M]^3$ while $[\Psi_\alpha^2]=[M]^2$; no dimensionful bridge scale is specified, so this correspondence does not define a dimensionally complete field identification or action:

$$
E_Y \overset{\mathrm{formal}}{\longleftrightarrow} \bar\psi\,\hat{P}_Y\,\psi,\qquad
E_I \overset{\mathrm{formal}}{\longleftrightarrow} \bar\psi\,\hat{P}_I\,\psi
$$

Within this extension, $\hat{P}_Y$ and $\hat{P}_I$ are projection operators assigned to the 4-spinor. Right-moving/particle-like and left-moving/anti-particle-like labels, together with the chiral representation, are extension assumptions; the canonical density equations contain no such labels.

$$
\hat{P}_Y = \frac{1+\gamma^5}{2},\qquad
\hat{P}_I = \frac{1-\gamma^5}{2}
$$

Within this optional extension, one may represent the two-fluid densities by the following **formal chiral projection correspondence**; the missing bridge scale remains an explicit dimensional-closure blocker:

$$
\boxed{\Psi_0^2 \overset{\mathrm{formal}}{\longleftrightarrow} \bar\psi\frac{1+\gamma^5}{2}\psi,\qquad
\Psi_1^2 \overset{\mathrm{formal}}{\longleftrightarrow} \bar\psi\frac{1-\gamma^5}{2}\psi}
$$

Within this extension, the condition $E_Y/E_I = \varphi$ supplies the proposed $\varphi$-VEV mapping.

### 2.3 φ-Damping

Within the optional extension, the Dirac evolution includes $\varphi$-damped dynamics:

$$
\mathcal{L}_{\text{D,damp}} = -\frac{\varphi^{-1}}{2}(\bar\psi\psi)\cdot\rho
$$

Under the optional density mapping, $\rho=E_Y+E_I=\Psi_0^2+\Psi_1^2$, so this coupling uses the same two-fluid density as the canonical state. It remains a formal source ansatz only; without a specified dimensionful bridge scale, it does not close a dimensionally complete Dirac action.

### 2.4 Full Dirac Lagrangian

$$
\boxed{\mathcal{L}_{\text{D}} = \bar\psi(i\gamma^\mu\partial_\mu - m)\psi
- \frac{\varphi^{-1}}{2}(\bar\psi\psi)\cdot\rho
+ \bar\psi\left(\hat{P}_Y\Psi_0^2 + \hat{P}_I\Psi_1^2\right)\psi}
$$

Because the bridge scale is unspecified, the displayed damping and projection terms are formal ansätze; $\mathcal{L}_{\text{D}}$ is not a dimensionally complete physical action.

---

## 3. GR/Gravity Sector $\mathcal{L}_{\text{GR}}$

Gravity is an optional Einstein–Hilbert extension with a candidate
Qi-modified effective Newton constant; the physical Qi-gravity interpretation
is **Calibrated/conditional**. The action below is a formal frozen-background
or locally constant-$G_{\text{eff}}$ ansatz, not a complete variable-coupling
covariant action.

### 3.1 Einstein-Hilbert Term

$$
\mathcal{L}_{\text{EH}} = \frac{R}{16\pi G_{\text{eff}}}
$$

where $R$ is the Ricci scalar and $g=\det(g_{\mu\nu})$. The invariant
$\sqrt{-g}$ factor is supplied once by the action measure in §6. If
$F\equiv1/G_{\text{eff}}$ varies in spacetime, varying
$\int d^4x\sqrt{-g}\,F R$ adds
$(g_{\mu\nu}\Box-\nabla_\mu\nabla_\nu)F$ and implicit
metric-dependence terms. A scalar-tensor completion or explicit
exchange terms would be required for a variable coupling; an Einstein
equation containing only $G_{\text{eff}}T_{\mu\nu}$ with separate
Bianchi conservation is not derived here.

### 3.2 Candidate Qi-Modified Newton Constant (Calibrated/conditional interpretation)

The candidate effective Newton constant is parameterized by the local scalar Qi coherence and the canonical density imbalance:

$$
\boxed{G_{\text{eff}} = G \cdot \frac{\pi}{\rho} \cdot (1 + (\varphi^{6}-1)q)}
$$
Because $[\pi]=[\rho]$, the ratio $\pi/\rho$ is dimensionless and $[G_{\text{eff}}]=[G]$; $P_{\mathrm{TF}}$ enters stress and thermodynamic relations separately.

where:
- $G$ is the bare Newton constant (set by the Planck scale)
- $\pi\equiv E_Y-E_I$ is the signed Yang/Yin density imbalance. It has the same energy-density units as $\rho$, and at the $\varphi$-attractor $\pi/\rho=\varphi^{-3}$
- $q$ is the canonical Qi quality (coherence)
  $q=\rho^2/(\rho^2+\varphi^{-2}+\varepsilon^2)$, with
  $\varepsilon=E_Y-\varphi E_I$ and $\rho=E_Y+E_I$. For $\rho>0$, setting
  $s\equiv\pi/\rho\in[-1,1]$ gives
  $\varepsilon/\rho=(\varphi^2s-\varphi^{-1})/2$ and
  $q(\rho,s)=\left[1+\left((\varphi^2s-\varphi^{-1})/2\right)^2+
  \varphi^{-2}/\rho^2\right]^{-1}$. In physical energy-density variables,
  $q=\rho_{\mathrm{phys}}^2/(\rho_{\mathrm{phys}}^2+
  \varphi^{-2}\rho_*^2+\varepsilon_{\mathrm{phys}}^2)$ with external
  $\rho_*$. At $\varepsilon=0$, the equilibrium form is
  $q_{\mathrm{eq}}=\rho^2/(\rho^2+\varphi^{-2})$; the optional
  $M_{\mathrm{Qi}}=\rho^2=(\Psi_0^2+\Psi_1^2)^2$ power notation agrees only
  on that equilibrium slice, not as an independent canonical state field.
- $P_{\mathrm{TF}}$ is the two-fluid thermodynamic pressure, the isotropic spatial stress with the same energy-density units as $\rho$. The gradient derivative belongs to $\boldsymbol{\Pi}_{\alpha}\equiv\partial\mathcal{L}_{\mathrm{TF}}/\partial(\nabla\Psi_\alpha)$
- $\xi\equiv\varphi^6\approx17.944$ is an exact algebraic coefficient identity; identifying it with the physical Qi-gravity coupling is Calibrated/conditional (Milky Way anchor, ledger row 498)
At the fixed point $s=\varphi^{-3}$ and reference density $\rho=\varphi$,
$q_{\mathrm{eq}}=0.872677996$ and
$G_{\mathrm{eff}}=3.726779962\,G$. On that fixed-composition line,
$q\to0$ and $G_{\mathrm{eff}}\to\varphi^{-3}G$ as $\rho\to0$, while
$q\to1$ and $G_{\mathrm{eff}}\to\varphi^3G$ only as $\rho\to\infty$.
The formal $\varphi^6$ endpoint ratio requires this density-asymptotic
fixed-composition interpretation; $q$ is not an independent variable at
fixed finite $(\rho,s)$. Since $G_{\mathrm{eff}}$ is undefined at $\pi=0$
and changes sign for $\pi<0$, attractive Newtonian/GR behavior requires an
additional **Hypothesized** sign/force closure.

### 3.3 $\xi = \varphi^6$ Identity and Scope

With the canonical attractor identity $\alpha_0\equiv(\pi/\rho)_{\varphi\text{-attractor}}=\varphi^{-3}$, define the dimensionless coefficient $\xi\equiv\alpha_0^{-2}$. The algebraic identity is exact:

$$
\boxed{\xi = \alpha_0^{-2} = \varphi^6 = \varphi^5 + \varphi^4 \approx 17.944}
$$

The use of this coefficient as the physical Qi-gravity coupling is Calibrated/conditional: the quadratic-coupling input supplies the physical interpretation, and the Milky Way anchor supplies its calibration (ledger row 498). The $2 \times 3 = 6$ count is a secondary **Hypothesized** geometric interpretation—two real field components and three spatial/frame directions, conditional on the adopted $d=3$ geometry. It organizes a possible reading of the exponent; it does not derive the physical $\xi$ or establish the Qi-gravity identification.

### 3.4 Energy-Momentum Tensor

$$
T_{\mu\nu} = \frac{2}{\sqrt{-g}}\frac{\delta S_{\text{matter}}}{\delta g^{\mu\nu}}
$$

The extended-action matter tensor includes the canonical two-fluid contribution together with optional Dirac and gauge contributions:

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

### 3.5 Einstein-Hilbert Density

With the invariant measure supplied by the action integral, the gravity-sector
Lagrangian scalar is

$$
\boxed{\mathcal{L}_{\text{GR}} = \frac{R}{16\pi G_{\text{eff}}}.}
$$

The matter densities already reside in $\mathcal{L}_{\text{TF}}$,
$\mathcal{L}_{\text{D}}$, and $\mathcal{L}_{\text{SM}}$. Their metric variation
defines $T_{\mu\nu}$ in §3.4; a stress-tensor trace is not added again as an
independent matter Lagrangian.

---

## 4. SM Gauge Sector $\mathcal{L}_{\text{SM}}$ (optional conditional extension—Hypothesized—August 2026)

The Standard Model gauge group SU(3)$_C \times$ SU(2)$_L \times$ U(1)$_Y$ is listed through the Cassi $\varphi$-structure. In the optional gauge extension, the Higgs doublet is the SU(2) isospinor $\Psi = (\psi_1, \psi_2)^T$ whose norms are identified with the two-fluid densities: $|\psi_1|^2 = \Psi_0^2$, $|\psi_2|^2 = \Psi_1^2$. The canonical density state does not itself supply this isospinor identification.

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

The framework assigns the gauge couplings at the chosen GUT normalization:

$$
\begin{aligned}
g_s^2 &\equiv 4\pi\alpha_{\text{GUT}},\\
g^2 &= g'^2 \cdot \frac{1-\varphi^{-3}}{\varphi^{-3}}.
\end{aligned}
$$

The first line defines the SU(3) normalization at the GUT scale. The second line fixes $(g/g')^2 = 2\varphi$ as a boundary input. The current action
contains independent SU(2) and U(1) kinetic coefficients and supplies no
relative-normalization mechanism; the curvature–orbit candidate and its
blockers are in `standard-model/su2-gauge-extension.md` §3.2.1.

The corresponding tree-level angle is

$$
\boxed{\sin^2\theta_W = \frac{\varphi-1}{\varphi+1} = \varphi^{-3} \approx 0.236}.
$$

The measured running angle crosses this value at $\mu_* \approx 233$ GeV; at
$m_Z$ the prediction sits 2.1% above the measured 0.23122. The running angle
increases with energy, so the $\mu_*$ crossing and the chosen GUT coupling
assignment are distinct statements (`standard-model/sm-radiative-corrections.md` §3.3).

### 4.3 Covariant Derivative (Fermion Sector)

$$
D_\mu = \partial_\mu - ig_s\frac{\lambda^A}{2}G_\mu^A
- ig\frac{\tau^a}{2}W_\mu^a
- ig'Y B_\mu
$$

### 4.4 Higgs/Isospinor Sector (optional conditional extension—Hypothesized—August 2026)

Within the optional gauge extension, the Higgs doublet is the SU(2) isospinor $\Psi = (\psi_1, \psi_2)^T$:

$$
\mathcal{L}_{\text{Higgs}} = |D_\mu\Psi|^2
- \lambda_\phi\left(|\Psi|^2 - \frac{v_0^2}{2}\right)^2
$$

Within this extension, the $\varphi$-equilibrium VEV is:

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

**Conditional extension prediction:** FCC-ee will measure this to $>100\sigma$.

### 4.5 SU(3) Color

Within the optional gauge extension, the color field is a tripled extension of the fermion/isospinor sector:

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

### 4.6 Yukawa Sector (optional conditional extension—Hypothesized—August 2026)

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

The algebraic $\xi$ identity and its Calibrated/conditional Qi-gravity interpretation are separated here from the optional Dirac/gauge projections. The Dirac and gauge projections require the conditional extension.

### 5.1 Qi-Gravity Coupling (Calibrated/conditional identification)

Within that Calibrated/conditional physical interpretation, the two-fluid's coherent energy motivates the following **schematic candidate coupling for action bookkeeping**:

$$
\boxed{\mathcal{L}_{qG}^{\mathrm{cand}} = \frac{\xi q}{16\pi G}\,R},\qquad
\xi = \varphi^6
$$

This display is not an algebraic replacement for the phenomenological $G_{\text{eff}}$ of Section 3.2. Adding it directly to the Einstein-Hilbert term would produce an inverse-gravity coefficient proportional to $(1+\xi q)/G$, whereas Section 3.2 defines $G_{\text{eff}}=G\cdot(\pi/\rho)\cdot(1+\xi q)$; these forms are not equivalent without an explicit normalization, sign choice, and density bridge. A complete covariant action therefore remains conditional on those inputs.

### 5.2 Dirac → Two-Fluid Projection (optional conditional extension—Hypothesized—August 2026)

Within the optional extension, the Dirac spinor's chiral densities are proposed as sources for the two-fluid:

$$
\boxed{\mathcal{L}_{\text{D→TF}} = \frac{\kappa_s}{2}\left(\bar\psi\frac{1+\gamma^5}{2}\psi - \Psi_0^2\right)^2
+ \frac{\kappa_s}{2}\left(\bar\psi\frac{1-\gamma^5}{2}\psi - \Psi_1^2\right)^2}
$$

The optional ansatz remains a dimensionally incomplete **Hypothesized** ansatz: each bracket subtracts a spinor density of dimension $[M]^3$ from a condensate square of dimension $[M]^2$. No physical $\kappa_s$ or equilibration timescale follows until a sourced, ledgered normalization makes the projection homogeneous.

### 5.3 Gauge → Two-Fluid Coupling

Within the optional gauge extension, the Higgs/isospinor doublet is identified with the two-fluid's SU(2) representation. The covariant derivative then links the gauge and two-fluid sectors:

$$
\mathcal{L}_{G→\text{TF}} = |D_\mu\Psi|^2 - |\partial_\mu\Psi|^2
$$

This optional term subtracts the pure kinetic contribution already represented in $\mathcal{L}_{\text{TF}}$ and supplies the gauge-covariant kinetic term.

### 5.4 Wu Xing Cycle (optional Hypothesized/conditional PDE lift)

The five-element coefficient formulas below are retained from the PDE formalism as an optional lift. Their Wu Xing interpretation and insertion into an action are **Hypothesized/conditional**; they are not part of canonical $\mathcal{L}_{\text{TF}}$.

| Coefficient | Value | Role in optional lift |
|------------|-------|------|
| $K_{fw} = \varphi^{-1}$ | $0.618$ | Water damps Fire (coherence suppresses turbulence) |
| $K_{fm} = \lambda\varphi^2$ | $0.262$ | Fire melts Metal (turbulence reduces conversion) |
| $K_{md} = 3\varphi^2$ | $7.85$ | Metal cuts Wood (conversion suppresses structure) |
| $H_{\text{empty}} = \lambda\varphi^{-2}/3$ |—| Candidate cosmological baseline—the factor $1/3$ is algebraically **Derived conditional on the assumed spatial dimension $d=3$** (`cosmology/cosmology-from-phi.md` §1); the separate $d=3$ geometry construction is Hypothesized and the assumption is not derived from canonical conversion; the $\lambda\varphi^{-2}$ rate uses the selected solver-family parameter (constructor default $\lambda=0.02$; $\lambda=0.1$ only when explicitly passed); any physical $H_{\text{empty}}$ linkage is **Hypothesized/conditional** |

Within this optional PDE lift, these coefficients act on source terms associated with $\mathcal{L}_{\text{TF}}$; canonical $\mathcal{L}_{\text{TF}}$ contains no five-element cycle interpretation.

### 5.5 Full Mixing Lagrangian

$$
\boxed{
\begin{aligned}
\mathcal{L}_{\text{mix}} &=
\frac{\xi q}{16\pi G}R \\
&\quad + \frac{\kappa_s}{2}\sum_{\pm}\left(\bar\psi\frac{1\pm\gamma^5}{2}\psi - \Psi_{0,1}^2\right)^2 \\
&\quad + \left(|D_\mu\Psi|^2 - |\partial_\mu\Psi|^2\right)
\end{aligned}}
$$
The $\kappa_s$ term in this full mixing form inherits the dimensional defect in §5.2. The $\xi q R/G$ term is the same schematic candidate from §5.1, not an algebraic replacement for the phenomenological $G_{\text{eff}}$. Both remain optional **Hypothesized** structures; no physical $\kappa_s$ or equilibration timescale is established without a sourced, ledgered normalization, and the covariant gravity action requires the normalization/sign/density bridge stated in §5.1.

---

## 6. Optional Extended Cassi Action (Hypothesized—August 2026)

$$
\boxed{
S_{\text{Cassi}} = \int d^4x\sqrt{-g}\,
\big(\mathcal{L}_{\text{TF}} + \mathcal{L}_{\text{D}} + \mathcal{L}_{\text{GR}} + \mathcal{L}_{\text{SM}} + \mathcal{L}_{\text{mix}}\big)
}
$$

This displayed sum is optional bookkeeping, not a complete action: the Dirac density mapping and projection/damping terms retain the unspecified dimensionful bridge identified in §2.2.

### 6.1 Compact Form

In compact notation, the optional extended action is:

$$
\boxed{
\begin{aligned}
\mathcal{L}_{\text{Cassi}}
&= \underbrace{\frac{1}{2}(\partial\Psi)^2 - \frac{g}{4}|\Psi|^4
   - \frac{\lambda}{2}(\Psi_0^2 - \varphi\Psi_1^2)^2}_{\text{Two-fluid core}} \\
&\quad + \underbrace{A_B B(x,t)|\Psi|^2}_{\text{optional breath extension}} \\
&\quad + \underbrace{\bar\psi(i\gamma^\mu\partial_\mu - m)\psi
   - \frac{\varphi^{-1}}{2}(\bar\psi\psi)\cdot\rho}_{\text{Dirac matter—optional extension}} \\
&\quad + \underbrace{\frac{1}{16\pi G_{\text{eff}}}R}_{\text{Gravity}} \\
&\quad + \underbrace{-\frac{1}{4g_s^2}G^2 - \frac{1}{4g^2}W^2
   - \frac{1}{4g'^2}B^2}_{\text{Gauge kinetic—listed extension}} \\
&\quad + \underbrace{|D_\mu\Psi|^2
   - \lambda_\phi(|\Psi|^2 - v_0^2/2)^2
   - y_f\bar\psi_f\Psi\psi_f'}_{\text{Higgs + Yukawa—optional extension}} \\
&\quad + \underbrace{\frac{\kappa_s}{2}\sum_{\pm}
   \left(\bar\psi P_{\pm}\psi - \Psi_{0,1}^2\right)^2}_{\text{Sector coupling—optional extension}}
\end{aligned}}
$$

The componentwise quantum-potential operator from §1.3 is omitted here for the
same reason as in §1.6: it remains an optional ansatz pending a declared scalar
contraction or completion. This compact action repeats the optional
sector-coupling ansatz and its dimensional blocker; no physical $\kappa_s$ or
equilibration timescale is established from the displayed term.

### 6.2 Subsector Actions

The table separates the canonical two-fluid core from optional Dirac, gauge, and mixing extensions; each reference documents the corresponding sector:

| Sector | Action | Document |
|--------|--------|----------|
| Two-fluid core | $S_{\text{TF}} = \int\mathcal{L}_{\text{TF}}$ | `foundations/cassi-first-principles.md` |
| Dirac matter (optional extension) | $S_{\text{D}} = \int\mathcal{L}_{\text{D}}$ | `two-fluid/cassi_dirac_bridge.py`, `particles/cassi-yang-yin-particles.md` |
| Gravity | $S_{\text{GR}} = \int\mathcal{L}_{\text{GR}}$ | `foundations/xi-derivation.md`, `(external—see archive/theory/qi-fluid-formalism.md in physics repo)` |
| SM gauge | $S_{\text{SM}} = \int\mathcal{L}_{\text{SM}}$ | `standard-model/su2-gauge-extension.md`, `standard-model/sm-from-phi.md` |
| Mixing | $S_{\text{mix}} = \int\mathcal{L}_{\text{mix}}$ | This document |
The following coupled equations belong to the optional extended action and its
amplitude-action lift; the canonical solver is stated in the real-density
variables $E_Y,E_I$ with gated rank-one conversion and omits the optional QP
term unless that closure is adopted. These equations do not add phase,
chirality, or propagation to the canonical density state.
The q-gated rank-one wording here denotes the selected canonical/theory form;
the base implementation and `ExpandingTwoFluid3DGPU(qi_gate=False)` default
use ungated conversion, with the gate applied only when explicitly enabled.

### 7.1 Formal two-fluid equation in the action lift

The componentwise QP contribution shown in this formal equation is an
additional optional operator ansatz; without the scalar completion stated in
§1.6, it is not an Euler–Lagrange equation of the boxed scalar $\mathcal{L}_{\text{TF}}$.

$$
\partial^2\Psi_\alpha + \kappa_4\nabla^4\Psi_\alpha
+ g|\Psi|^2\Psi_\alpha + 2\lambda(\Psi_0^2 - \varphi\Psi_1^2)\frac{\partial}{\partial\Psi_\alpha}(\Psi_0^2 - \varphi\Psi_1^2) \\
+ \frac{\hbar^2}{2m^2}\nabla^2\left(\frac{\nabla^2 \rho^\beta}{\rho^\beta}\right)\Psi_\alpha
:= A_B B(x,t)\Psi_\alpha + J_\alpha^{\text{gauge}} + J_\alpha^{\text{Dirac}}
$$

### 7.2 Dirac Equation (optional conditional extension)

$$
(i\gamma^\mu D_\mu - m)\psi - \frac{\varphi^{-1}}{2}\rho\psi
+ \kappa_s\left(\bar\psi P_{\pm}\psi - \Psi_{0,1}^2\right)P_{\pm}\psi = 0
$$
This formal equation inherits the dimensionally incomplete projection in §5.2; it does not establish a physical $\kappa_s$ or an equilibration timescale until a sourced normalization makes the brackets homogeneous.

### 7.3 Einstein Equation (conditional Qi-gravity interpretation)

$$
G_{\mu\nu} = 8\pi G_{\text{eff}}\,T_{\mu\nu},
\qquad G_{\text{eff}} = G\cdot\frac{\pi}{\rho}\cdot(1+(\varphi^{6}-1)q)
$$

### 7.4 Gauge Field Equations (optional gauge extension)

$$
D_\mu F^{\mu\nu} = g^2 J^{\nu},\qquad
D_\mu G^{\mu\nu} = g_s^2 J^{\nu}_s,\qquad
\partial_\mu B^{\mu\nu} = g'^2 J^{\nu}_Y
$$

Within the optional fermion and Higgs extension, the currents come from the covariant derivatives.

---

## Dimensionless Parameter Status

The action assembly contains a mixture of canonical-core, conditional-extension, asserted, calibrated, and mapped dimensionless quantities; the three dimensionful constants ($c$, $\hbar$, $G$) are external (see `foundations/dimensionful-constants-status.md`).

| Quantity | Expression | Value | Status |
|----------|-----------|-------|--------|
| $\varphi$ | $(1+\sqrt{5})/2$ | $1.618033989$ | Mathematical constant |
| $\varphi^{-1}$ | $1/\varphi$ | $0.618033989$ | Derived |
| $\varphi^{-2}$ | $1/\varphi^2$ | $0.381966011$ | Derived |
| $\alpha_0 = \varphi^{-3}$ | $(\varphi-1)/(\varphi+1)$ | $0.236067978$ | Derived (fixed-point imbalance; VEV asymmetry; the "Yang fraction" label is Mapped—ledger row 500) |
| $\xi$ | $\varphi^6 = \varphi^5 + \varphi^4$ | $17.94427191$ | **Exact identity** $\xi=\alpha_0^{-2}$; physical Qi-gravity identification **Calibrated/conditional** (Milky Way anchor, ledger row 498) |
| $\sin^2\theta_W$ | $\varphi^{-3}$ | $0.236$ (at $\mu_* = 233$ GeV; +2.1% at $m_Z$) | Asserted boundary within optional gauge extension (realized at $\mu_*$; Calibrated—ledger row 490) |
| $\alpha_{\text{GUT}}$ | $\varphi^{-3}/(4\pi)$ | $1/53$ | **Asserted/conditional within optional gauge extension**; running requires the stated particle-content and threshold inputs |
| $m_W/m_Z$ | $\sqrt{1-\varphi^{-3}}$ | $0.874$ | **Conditional extension prediction** |
| $H_{\text{empty}}$ | $\lambda\varphi^{-2}/3$ |—| Candidate cosmological baseline—the factor $1/3$ is algebraically **Derived conditional on the assumed spatial dimension $d=3$** (`cosmology/cosmology-from-phi.md` §1); the separate $d=3$ geometry construction is Hypothesized and the assumption is not derived from canonical conversion; the $\lambda\varphi^{-2}$ rate uses the selected solver-family parameter (constructor default $\lambda=0.02$; $\lambda=0.1$ only when explicitly passed); any physical $H_{\text{empty}}$ linkage is **Hypothesized/conditional** |
| $K_{fw}$ | $\varphi^{-1}$ | $0.618$ | **Derived arithmetic; Wu Xing/PDE role Hypothesized/conditional optional lift** |
| $K_{md}$ | $3\varphi^2$ | $7.85$ | **Derived arithmetic; Wu Xing/PDE role Hypothesized/conditional optional lift** |
| $\kappa_s$ | $\kappa_{s,\mathrm{scale}}=\varphi^{-6}/v_0^2$ | $0.92$ TeV$^{-2}$ (formal $C=1$ candidate) | **Derived conditional scale arithmetic; the optional projection is dimensionally incomplete, so no physical $\kappa_s$ or equilibration timescale is established; coefficient Hypothesized** |
| $\lambda$ | $0.02$ (`TwoFluid3DGPU` default); $0.1$ when explicitly passed | PDE conversion-rate parameter; $\lambda=1/(2w)$ with $w=5$ is a **Hypothesized** Wu Xing linkage requiring independent cycle-time/dynamical closure | **Asserted default; named experiment convention; Hypothesized linkage** |
| $G_{\text{eff}}$ | $G\cdot(\pi/\rho)\cdot(1+(\varphi^{6}-1)q)$ |—| **Calibrated/conditional Qi-gravity interpretation**; $\pi/\rho$ and $q$ are dimensionless canonical inputs, with the physical scale anchored by ledger row 498 |

**The closed algebraic subset is fixed by the named $\varphi$ and two-fluid
inputs together with the selected solver-family parameters; the
`TwoFluid3DGPU` default is $\lambda=0.02$, while $\lambda=0.1$ is a named
experiment convention only where explicitly passed. The physical
Qi-gravity interpretation of $\xi$ and $G_{\text{eff}}$ remains
Calibrated/conditional, while asserted boundaries and calibrated anchors
retain their ledger status.**

---

## 9. $\varphi$-Scale Bookkeeping (proposed)

The action records a proposed $\varphi$-scale bookkeeping pattern. For each sector, any component/dimension assignment carries its own epistemic scope:

$$
\text{coupling} \propto \varphi^{N_f - N_b}
$$

where $N_f$ counts field degrees of freedom and $N_b$ counts background "binding" factors. This pattern is listed for the canonical core and for the optional extensions:

- Two-fluid core: 2 fields $\times$ 1 component = $\varphi^{2}$ → $\varphi^{-1}$ damping
- Dirac sector (optional extension): 4 spinor components × 3 generations = $\varphi^{12}$ → $\varphi^{-11}$ seesaw
- Gravity: the $2\times3$ field-component/frame-direction count is a secondary **Hypothesized** geometric reading of $\varphi^6$, conditional on $d=3$; it does not derive the physical $\xi$
- Gauge sector (optional extension): SU(2) has three generators, while the relative U(1) normalization required for $\sin^2\theta_W = \varphi^{-3}$ remains an asserted boundary; the curvature–orbit candidate is tested in `standard-model/su2-gauge-extension.md` §3.2.1.

The continued fraction $\varphi = [1;1,1,1,\ldots]$ and its truncations supply the arithmetic $\varphi$-power vocabulary used in these assignments; sector-specific origins and tiers remain as stated above.

---

## 10. Summary

The Cassi action assembly records the canonical real-density two-fluid core together with optional quantum-matter, gauge, and mixing extensions. Its dimensionless entries are powers of $\varphi$ or derived rational factors with individual status labels; the Weinberg coupling boundary remains asserted, and the three dimensionful constants ($c$, $\hbar$, $G$) are external.

The following observables retain their listed statuses, with the gauge-sector entries belonging to the optional conditional extension:

The optional Dirac↔two-fluid projection remains a dimensionally incomplete **Hypothesized** ansatz; its coefficient-free scale candidate does not establish a physical $\kappa_s$ or equilibration timescale.

| Observable | Cassi | SM | Detectable at |
|-----------|-------|-----|---------------|
| $m_W/m_Z$ | $0.874$ tree; $0.878$ with $\rho$ correction | $0.881$ | FCC-ee ($>100\sigma$) |
| $\sin^2\theta_W$ at $m_Z$ | $0.236$ ($\varphi^{-3}$; exact at $\mu_* = 233$ GeV) | $0.23122$ | FCC-ee |
| $\alpha_s(m_Z)$ | $0.058$–$0.061$ | $0.118$ | LHC precision ($\Delta b = 1.70$) |
| $M_{\text{GUT}}$ | $2 \times 10^{16}$ GeV (with beyond-SM content) | no SM intersection | Proton lifetime |
| $m_W$ | $80.07$ GeV | $80.360$ GeV | FCC-ee (0.5 MeV) |
| $G_{\text{eff}}$ boost | $(1+(\varphi^{6}-1)q)\times$ α-free ceiling; halo regime $\alpha_{\text{halo}}(1+(\varphi^{6}-1)q) \approx 9.0\times$ | $1\times$ | Galaxy rotation (Calibrated/conditional Qi-gravity interpretation) |

---

## References

- `foundations/cassi-first-principles.md`—two-fluid postulate, Qi coherence, the four pillars
- `foundations/xi-derivation.md`—$\xi = \varphi^6$ as the imbalance inverse-square identity, with the physical Qi-gravity pin Calibrated/conditional
- `foundations/wu-xing-derivation.md`—$w=5$ uniqueness; the
  $\lambda=1/(2w)$ relation is a Hypothesized linkage, while the
  `TwoFluid3DGPU` default $\lambda=0.02$ and named $\lambda=0.1$ experiment
  convention remain solver parameter choices
- `foundations/dimensionful-constants-status.md`—external dimensionful constants, parameter accounting
- `standard-model/su2-gauge-extension.md`—SM gauge sector, Weinberg angle
- `standard-model/sm-from-phi.md`—Standard Model couplings from $\varphi$
- `particles/cassi-yang-yin-particles.md`—optional Hypothesized complex-field/NLS particle-interference extension and its conditional Dirac mapping
- `two-fluid/cassi_two_fluid_3d_gpu.py`—PDE solver implementing the two-fluid core
