# Particle-Sector Action and Fixed-Charge Variational Closure

## Status: Hypothesized source-free temporal completion / Derived gauge, Gauss, stationary, and variational boundaries / Tested one-point Q2-qualified primary background—September 2026

## Abstract

The magnetic-core and trapped-charge chain now supplies a conditional static
energy, but its source authorities do not yet define one time-local gauge action
for a coupled particle solve. This document closes that specific boundary. It
combines the registered Yang/Yin composition energy, the conditional adjoint
$SU(2)_Q$ core, and the neutral trapped carrier into one particle-sector action.
The branch excludes the optional Dirac projection and the dimensionally
incomplete mixing ansatz in `foundations/cassi-theory-reference.md` and
`foundations/unified-lagrangian.md`.

Gauging the registered first-order Yang/Yin time term produces a nonzero
$SU(2)_Q$ charge density in every nonzero fundamental condensate. A source-free
homogeneous vacuum therefore cannot satisfy Gauss's law in that completion.
The minimal source-free branch used here assigns second-order covariant temporal
kinetics to the $SU(2)_Q$-charged Yang/Yin and adjoint fields, retains the neutral
carrier's first-order global-$U(1)_C$ term, and supplies temporal gauge
curvatures. The resulting action is invariant under time-dependent local
$SU(2)_Q$, has an explicit Gauss constraint, and reduces to the registered
static energy when the charged fields are time independent and
$\mathcal A_0^a=0$.

The fixed-$Q_C$ stationary functional, coupled Euler equations, boundary
inventory, source-unit dimensions, normalization-invariant dimensionless
groups, and first numerical variational class are derived below. At the
registered coefficient point, canonical-preimage continuation produces an
independently verified Q2-qualified primary background in the finite-grid
$C_4$ class. Domain and resolution convergence, localization, mass, radius,
spectrum, lifetime, and particle identification remain open. The numerical
receipt is recorded in
`computations/particle-stationary-q2-recovery-report.md`.

---

## 1. Scope and source ledger

### 1.1 Included fields

The particle branch lives on

$$
\mathcal M_P=\mathbb R_t\times\mathbb R_x^3\times I_{\mathfrak s},
\qquad d\mu_P=dt\,d^3x\,d\mathfrak s,
\tag{PA1}
$$

with dimensionless flat scale coordinate $\mathfrak s$. Its fields are

| Field | Representation | Role |
|---|---|---|
| $\Psi=(\psi_Y,\psi_I)^T$ | fundamental of conditional $SU(2)_Q$ | Yang/Yin density and composition |
| $\Phi^a$ | adjoint of $SU(2)_Q$ | smooth magnetic core and composition orientation |
| $\mathcal A_M^a$, $M\in\{0,1,2,3,\mathfrak s\}$ | $SU(2)_Q$ connection | spatial, scale, and temporal gauge transport |
| $\chi_C$ | $SU(2)_Q$ neutral, global $U(1)_C$ charge one | core-trapped fixed charge |

The gauge-invariant Yang/Yin scalars remain

$$
\rho=\Psi^\dagger\Psi,
\qquad
S^a=\Psi^\dagger\sigma^a\Psi,
\qquad
\Delta_\varphi
=\frac12\left[(1-\varphi)\rho
+(1+\varphi)\frac{\Phi^aS^a}{v_Q}\right].
\tag{PA2}
$$

The vacuum conditions are $\rho=\rho_0$, $\Delta_\varphi=0$,
$\Phi^a\Phi^a=v_Q^2$, $\chi_C=0$, and vanishing covariant gradients and
curvatures.

### 1.2 Included authorities

The static terms are taken from:

- `foundations/interscale-current-soliton.md` for $\Psi$, $\rho$, the
  $\varphi$-composition potential, and spatial/scale stiffnesses;
- `foundations/nonabelian-magnetic-core-boundary.md` for the conditional
  adjoint core, non-Abelian gauge energy, and covariant composition scalar;
- `foundations/core-trapped-charge-support.md` for the neutral carrier,
  global $U(1)_C$, depletion trap, and fixed-charge support reduction.

The present action is an optional particle-sector branch. It does not promote
$SU(2)_Q$ to the Standard Model gauge group, does not repair the canonical
amplitude-field mixing ansatz, and does not identify the carrier charge with
electric charge, baryon number, or lepton number.

### 1.3 Excluded sectors

The first boundary-value problem excludes:

- Dirac, electroweak, QCD, and gravitational fields;
- endpoint fields $\Upsilon_\pm$ and imposed scale-circuit winding;
- a physical electromagnetic $U(1)$;
- nonzero net magnetic charge at the outer spatial boundary;
- calibrated particle masses, radii, or decay rates.

These exclusions define the calculation rather than approximating those
sectors as zero contributions to a claimed physical particle.

---

## 2. The first-order Gauss obstruction

### 2.1 Pauli identity

For one nonzero complex fundamental doublet, the Pauli bilinear obeys

$$
S^aS^a=(\Psi^\dagger\Psi)^2=\rho^2.
\tag{PA3}
$$

Therefore $\Psi^\dagger T^a\Psi=S^a/2$, with $T^a=\sigma^a/2$, has magnitude
$\rho/2$. No nonzero fundamental condensate is neutral under all three local
$SU(2)_Q$ generators.

### 2.2 Covariantizing the registered first-order term

The direct local-gauge completion of the registered first-order time term would
be

$$
\mathcal L_{\Psi,t}^{(1)}
=\frac{i\hbar}{2}
\left[\Psi^\dagger D_t\Psi-(D_t\Psi)^\dagger\Psi\right],
\qquad
D_t\Psi=(\partial_t-i g_Q\mathcal A_0^aT^a)\Psi.
\tag{PA4}
$$

Its dependence on $\mathcal A_0^a$ is

$$
\mathcal L_{\Psi,t}^{(1)}
=\frac{i\hbar}{2}
\left(\Psi^\dagger\partial_t\Psi
-\partial_t\Psi^\dagger\Psi\right)
+\hbar g_Q\mathcal A_0^a\Psi^\dagger T^a\Psi.
\tag{PA5}
$$

Once temporal gauge curvature is dynamical, variation with respect to
$\mathcal A_0^a$ gives a Gauss source proportional to
$\hbar g_Q\Psi^\dagger T^a\Psi$. In a homogeneous static vacuum the electric
curvatures vanish, whereas

$$
\left\|
\hbar g_Q
\left(\Psi_0^\dagger T^a\Psi_0\right)_{a=1}^{3}
\right\|_2
=\frac{\hbar g_Q\rho_0}{2}>0.
\tag{PA6}
$$

Thus the source-free first-order completion has no finite-energy homogeneous
vacuum with $\rho_0>0$. A compensating charged background could cancel this
source, but that background would be additional field content with its own
conservation and boundary ledger. Keeping the gauge field purely static would
avoid Gauss's law while leaving time-local gauge transformations undefined.

The particle branch selects the remaining minimal source-free option:
second-order covariant temporal kinetics for the charged condensate and adjoint
fields. This selection changes the Yang/Yin temporal dynamics and leaves the
first-order interscale-current action as a separate conditional branch.

---

## 3. Time-dependent local gauge completion

### 3.1 Transformations and covariant objects

For arbitrary smooth $U(t,\mathbf x,\mathfrak s)\in SU(2)_Q$,

$$
\begin{aligned}
\Psi'&=U\Psi,
\\
\Phi'&=R(U)\Phi,
\\
\mathcal A_M'&=U\mathcal A_MU^{-1}
-\frac{i}{g_Q}(\partial_MU)U^{-1},
\\
\chi_C'&=\chi_C,
\qquad M\in\{t,1,2,3,\mathfrak s\}.
\end{aligned}
\tag{PA7}
$$

Here $\mathcal A_M=\mathcal A_M^aT^a$ and $R(U)$ is the adjoint rotation. Define

$$
\begin{aligned}
D_M\Psi&=(\partial_M-i g_Q\mathcal A_M)\Psi,
\\
(D_M\Phi)^a&=\partial_M\Phi^a
+g_Q\epsilon^{abc}\mathcal A_M^b\Phi^c,
\\
\mathcal F_{MN}^a
&=\partial_M\mathcal A_N^a-\partial_N\mathcal A_M^a
+g_Q\epsilon^{abc}\mathcal A_M^b\mathcal A_N^c.
\end{aligned}
\tag{PA8}
$$

Then $D_M\Psi\mapsto U D_M\Psi$, $D_M\Phi\mapsto R(U)D_M\Phi$, and
$\mathcal F_{MN}\mapsto R(U)\mathcal F_{MN}$ for temporal, spatial, and scale
indices alike.

The carrier retains an independent global symmetry

$$
\chi_C\mapsto e^{i\alpha_C}\chi_C,
\qquad \alpha_C=\text{constant}.
\tag{PA9}
$$

### 3.2 Complete conditional action

The source-free particle-sector action is

$$
S_P=\int_{\mathcal M_P}d\mu_P\,\mathcal L_P,
\tag{PA10}
$$

with

$$
\begin{aligned}
\mathcal L_P={}&
\frac{C_\Psi}{2}(D_t\Psi)^\dagger D_t\Psi
+\frac{C_\Phi}{2}(D_t\Phi)^a(D_t\Phi)^a
\\
&+\frac{\epsilon_x}{2}\mathcal F_{ti}^a\mathcal F_{ti}^a
+\frac{\epsilon_{\mathfrak s}}{2}
\mathcal F_{t\mathfrak s}^a\mathcal F_{t\mathfrak s}^a
\\
&+\frac{i\hbar}{2}
\left(\chi_C^*\partial_t\chi_C
-\partial_t\chi_C^*\chi_C\right)
-\mathcal H_P,
\end{aligned}
\tag{PA11}
$$

where every new temporal coefficient is positive. The static Hamiltonian
density is

$$
\begin{aligned}
\mathcal H_P={}&
\frac{K_x}{2}(D_i\Psi)^\dagger D_i\Psi
+\frac{K_{\mathfrak s}}{2}(D_{\mathfrak s}\Psi)^\dagger D_{\mathfrak s}\Psi
+\frac{\lambda_\rho}{4}(\rho-\rho_0)^2
+\frac{\lambda_\varphi}{2}\Delta_\varphi^2
\\
&+\frac{1}{4\mu_x}\mathcal F_{ij}^a\mathcal F_{ij}^a
+\frac{1}{2\mu_{\mathfrak s}}\mathcal F_{i\mathfrak s}^a
\mathcal F_{i\mathfrak s}^a
\\
&+\frac{1}{2\mu_x}(D_i\Phi)^a(D_i\Phi)^a
+\frac{1}{2\mu_{\mathfrak s}}(D_{\mathfrak s}\Phi)^a
(D_{\mathfrak s}\Phi)^a
+\frac{\lambda_H}{4}(\Phi^a\Phi^a-v_Q^2)^2
\\
&+\frac{K_{Cx}}{2}|\nabla\chi_C|^2
+\frac{K_{C\mathfrak s}}{2}|\partial_{\mathfrak s}\chi_C|^2
\\
&+\left[\varepsilon_{C,\mathrm{out}}
-\eta_C(\rho_0-\rho)\right]|\chi_C|^2
+\frac{\lambda_C}{2}|\chi_C|^4.
\end{aligned}
\tag{PA12}
$$

All spatial terms come from the three included authorities. The temporal terms
are the new Hypothesized completion. The action contains no
$\overline\psi\Psi$ mixing term.

### 3.3 Source-unit dimensions

With $[\Psi]=[\chi_C]=L^{-3/2}$, $[\Phi]=[\mathcal A_i]=L^{-1}$,
$[\mathcal A_{\mathfrak s}]=1$, $[\mathcal A_0]=T^{-1}$, dimensionless $g_Q$
and $\mathfrak s$, every Lagrangian-density term has dimension
$\hbar T^{-1}L^{-3}$. The new coefficients require

$$
[C_\Psi]=\hbar T,
\qquad
[C_\Phi]=[\epsilon_x]=\hbar T L^{-1},
\qquad
[\epsilon_{\mathfrak s}]=\hbar T L^{-3}.
\tag{PA13}
$$

The static source-unit dimensions remain those registered in
`foundations/interscale-current-soliton.md`,
`foundations/nonabelian-magnetic-core-boundary.md`, and
`foundations/core-trapped-charge-support.md`.

### 3.4 Energy and boundedness

The conserved classical energy is the spatial integral of the four positive
temporal quadratic terms plus $\mathcal H_P$. The carrier's first-order term
contributes to its symplectic structure rather than to the energy. For positive
$K$'s, $\mu$'s, $C$'s, $\epsilon$'s, $\lambda_\rho$, $\lambda_\varphi$,
$\lambda_C$, and nonnegative $\lambda_H$, the derivative and quartic sectors
are nonnegative. The depletion coupling can make the carrier quadratic
coefficient negative inside a core, while $\lambda_C>0$ keeps the carrier
potential bounded below for $\rho\geq0$.

---

## 4. Gauss constraint

### 4.1 Temporal variation

Variation of $S_P$ with respect to $\mathcal A_0^a$ gives

$$
\epsilon_x(D_i\mathcal F_{ti})^a
+\epsilon_{\mathfrak s}(D_{\mathfrak s}
\mathcal F_{t\mathfrak s})^a
=q_\Psi^a+q_\Phi^a,
\tag{PA14}
$$

where

$$
\begin{aligned}
q_\Psi^a
&=C_\Psi g_Q\,
\operatorname{Im}\!\left[\Psi^\dagger T^aD_t\Psi\right],
\\
q_\Phi^a
&=-C_\Phi g_Q\,
\left(\Phi\times D_t\Phi\right)^a.
\end{aligned}
\tag{PA15}
$$

The neutral carrier contributes no $SU(2)_Q$ source. Equations (PA14) and
(PA15) transform covariantly in the adjoint representation.

### 4.2 Static Gauss-compatible sector

For

$$
\partial_t\Psi=0,
\qquad
\partial_t\Phi=0,
\qquad
\mathcal A_0^a=0,
\tag{PA16}
$$

all temporal curvatures and both charge densities in (PA15) vanish. Gauss's law
is then satisfied identically for arbitrary static spatial profiles. The
carrier may still have the stationary phase

$$
\chi_C(t,\mathbf x,\mathfrak s)
=e^{-i\omega_Ct}\chi(\mathbf x,\mathfrak s)
\tag{PA17}
$$

because it is neutral under $SU(2)_Q$.

This is the stationary sector used by the first boundary-value problem. A
time-dependent charged Yang/Yin or adjoint excitation requires solving
(PA14) for $\mathcal A_0^a$.

---

## 5. Fixed-charge stationary functional

### 5.1 Exact carrier charge

The global symmetry (PA9) gives

$$
Q_C=\int_{\mathbb R^3\times I_{\mathfrak s}}
|\chi|^2\,d^3x\,d\mathfrak s,
\qquad
\frac{dQ_C}{dt}=0
\tag{PA18}
$$

under closed or no-flux boundaries. At fixed $Q_C$, stationary configurations
are critical points of

$$
\mathscr F_{\omega_C}
=E_P-\hbar\omega_CQ_C,
\qquad
\delta\mathscr F_{\omega_C}=0,
\tag{PA19}
$$

with $\omega_C$ adjusted until (PA18) equals the declared target.

### 5.2 Matter equations

Define the Hermitian composition operator

$$
M_\Phi
=\frac12\left[(1-\varphi)\mathbf 1
+(1+\varphi)\frac{\Phi^a\sigma^a}{v_Q}\right],
\qquad
\frac{\partial\Delta_\varphi}{\partial\Psi^\dagger}
=M_\Phi\Psi.
\tag{PA20}
$$

Variation with respect to $\Psi^\dagger$ gives

$$
\begin{aligned}
0={}&-\frac{K_x}{2}D_iD_i\Psi
-\frac{K_{\mathfrak s}}{2}D_{\mathfrak s}D_{\mathfrak s}\Psi
\\
&+\left[
\frac{\lambda_\rho}{2}(\rho-\rho_0)
+\eta_C|\chi|^2
\right]\Psi
+\lambda_\varphi\Delta_\varphi M_\Phi\Psi.
\end{aligned}
\tag{PA21}
$$

Variation with respect to $\Phi^a$ gives

$$
\begin{aligned}
0={}&-\frac{1}{\mu_x}(D_iD_i\Phi)^a
-\frac{1}{\mu_{\mathfrak s}}
(D_{\mathfrak s}D_{\mathfrak s}\Phi)^a
\\
&+\lambda_H(\Phi^b\Phi^b-v_Q^2)\Phi^a
+\frac{\lambda_\varphi(1+\varphi)}{2v_Q}
\Delta_\varphi S^a.
\end{aligned}
\tag{PA22}
$$

The carrier equation is

$$
\begin{aligned}
\hbar\omega_C\chi={}&
-\frac{K_{Cx}}{2}\nabla^2\chi
-\frac{K_{C\mathfrak s}}{2}\partial_{\mathfrak s}^2\chi
\\
&+\left[
\varepsilon_{C,\mathrm{out}}
-\eta_C(\rho_0-\rho)
+\lambda_C|\chi|^2
\right]\chi.
\end{aligned}
\tag{PA23}
$$

Equations (PA21)--(PA23) contain the carrier backreaction through
$\eta_C|\chi|^2\Psi$ and the self-consistent density-depletion trap through
$\rho=\Psi^\dagger\Psi$.

### 5.3 Static gauge equations

Define

$$
\begin{aligned}
\mathcal J_i^a={}&
 g_QK_x\operatorname{Im}
 (\Psi^\dagger T^aD_i\Psi)
-\frac{g_Q}{\mu_x}(\Phi\times D_i\Phi)^a,
\\
\mathcal J_{\mathfrak s}^a={}&
 g_QK_{\mathfrak s}\operatorname{Im}
 (\Psi^\dagger T^aD_{\mathfrak s}\Psi)
-\frac{g_Q}{\mu_{\mathfrak s}}
(\Phi\times D_{\mathfrak s}\Phi)^a.
\end{aligned}
\tag{PA24}
$$

The spatial and scale connection equations are

$$
\frac{1}{\mu_x}(D_j\mathcal F_{ji})^a
-\frac{1}{\mu_{\mathfrak s}}
(D_{\mathfrak s}\mathcal F_{i\mathfrak s})^a
+\mathcal J_i^a=0,
\tag{PA25}
$$

and

$$
\frac{1}{\mu_{\mathfrak s}}
(D_i\mathcal F_{i\mathfrak s})^a
+\mathcal J_{\mathfrak s}^a=0.
\tag{PA26}
$$

A numerical implementation must add a declared gauge condition or solve these
equations on the gauge quotient. Gauge drift cannot be counted as a physical
zero or unstable mode.

---

## 6. Boundary inventory

### 6.1 Spatial infinity

The first particle class has zero net magnetic charge. In a fixed asymptotic
unitary gauge,

$$
\begin{aligned}
\Psi&\longrightarrow\Psi_0,
&\Psi_0^\dagger\Psi_0&=\rho_0,
&\Delta_\varphi(\Psi_0,\Phi_0)&=0,
\\
\Phi^a&\longrightarrow v_Q\delta^{a3},
&\mathcal F_{MN}^a&\longrightarrow0,
&\chi&\longrightarrow0.
\end{aligned}
\tag{PA27}
$$

Gauge-equivalent pure-gauge representatives are admissible. Gauge
transformations used in the variational quotient approach the identity at the
outer boundary after the representative is fixed.

The same outer data admit separated-core, merged-core, closed-loop, carrier-lump,
and delocalized basins. The monopole and antimonopole are initialization
features rather than independently fixed boundary charges.

### 6.2 Scale boundaries

For a finite interval $I_{\mathfrak s}=[\mathfrak s_-,\mathfrak s_+]$, the
first class uses covariant no-flux conditions

$$
D_{\mathfrak s}\Psi=0,
\qquad
D_{\mathfrak s}\Phi=0,
\qquad
\mathcal F_{i\mathfrak s}=0,
\qquad
\partial_{\mathfrak s}\chi=0
\quad\text{at }\mathfrak s_\pm.
\tag{PA28}
$$

The temporal completion also requires
$\mathcal F_{t\mathfrak s}=0$ at these boundaries. Periodic scale data define a
separate class. Endpoint sources and fixed scale winding are absent from both.

### 6.3 Numerical outer boundary

A finite cylinder or box of characteristic radius $R$ approximates spatial
infinity. Every reported solution must show that its energy, charge, carrier
decay rate, core separation, and boundary flux converge as $R$ increases.

---

## 7. Nondimensional stationary problem

### 7.1 Scales and fields

Choose the normalization-invariant vector-core length and condensate energy
scale

$$
\ell_Q=\frac{1}{g_Qv_Q},
\qquad
\mathcal H_Q=\frac{K_x\rho_0}{\ell_Q^2},
\qquad
E_Q=K_x\rho_0\ell_Q.
\tag{PA29}
$$

Define

$$
\widehat x^i=\frac{x^i}{\ell_Q},
\quad
\psi=\frac{\Psi}{\sqrt{\rho_0}},
\quad
h^a=\frac{\Phi^a}{v_Q},
\quad
c=\frac{\chi}{\sqrt{\rho_0}},
\quad
 a_i^a=g_Q\ell_Q\mathcal A_i^a,
\quad
 a_{\mathfrak s}^a=g_Q\mathcal A_{\mathfrak s}^a.
\tag{PA30}
$$

Let $\widehat D_i=\partial_{\widehat i}-ia_i^aT^a$,
$D_{\mathfrak s}=\partial_{\mathfrak s}-ia_{\mathfrak s}^aT^a$,
$f_{ij}^a=g_Q\ell_Q^2\mathcal F_{ij}^a$, and
$f_{i\mathfrak s}^a=g_Q\ell_Q\mathcal F_{i\mathfrak s}^a$. The dimensionless
composition scalar is

$$
\delta_\varphi
=\frac12\left[(1-\varphi)|\psi|^2
+(1+\varphi)h^a\psi^\dagger\sigma^a\psi\right].
\tag{PA31}
$$

### 7.2 Dimensionless energy

With $\widehat E=E_P/E_Q$,

$$
\begin{aligned}
\widehat E=\int d^3\widehat x\,d\mathfrak s\,\Bigg\{&
\frac12|\widehat D_i\psi|^2
+\frac{\alpha_{\mathfrak s}}{2}|D_{\mathfrak s}\psi|^2
+\frac{u_\rho}{4}(|\psi|^2-1)^2
+\frac{u_\varphi}{2}\delta_\varphi^2
\\
&+\frac{\gamma_x}{4}f_{ij}^af_{ij}^a
+\frac{\gamma_{\mathfrak s}}{2}
f_{i\mathfrak s}^af_{i\mathfrak s}^a
\\
&+\frac{\gamma_x}{2}(\widehat D_ih)^a(\widehat D_ih)^a
+\frac{\gamma_{\mathfrak s}}{2}
(D_{\mathfrak s}h)^a(D_{\mathfrak s}h)^a
+\frac{u_H}{4}(h^ah^a-1)^2
\\
&+\frac{k_{Cx}}{2}|\widehat\nabla c|^2
+\frac{k_{C\mathfrak s}}{2}|\partial_{\mathfrak s}c|^2
\\
&+\left[e_C-h_C(1-|\psi|^2)\right]|c|^2
+\frac{u_C}{2}|c|^4
\Bigg\}.
\end{aligned}
\tag{PA32}
$$

The independent static groups are

$$
\begin{aligned}
\alpha_{\mathfrak s}&=\frac{K_{\mathfrak s}\ell_Q^2}{K_x},
&u_\rho&=\frac{\lambda_\rho\rho_0\ell_Q^2}{K_x},
&u_\varphi&=\frac{\lambda_\varphi\rho_0\ell_Q^2}{K_x},
\\
\gamma_x&=\frac{v_Q^2}{\mu_xK_x\rho_0},
&\gamma_{\mathfrak s}&=
\frac{1}{\mu_{\mathfrak s}g_Q^2K_x\rho_0},
&u_H&=\frac{\lambda_Hv_Q^2}{g_Q^2K_x\rho_0},
\\
k_{Cx}&=\frac{K_{Cx}}{K_x},
&k_{C\mathfrak s}&=\frac{K_{C\mathfrak s}\ell_Q^2}{K_x},
&e_C&=\frac{\varepsilon_{C,\mathrm{out}}\ell_Q^2}{K_x},
\\
h_C&=\frac{\eta_C\rho_0\ell_Q^2}{K_x},
&u_C&=\frac{\lambda_C\rho_0\ell_Q^2}{K_x}.
\end{aligned}
\tag{PA33}
$$

The dimensionless charge, multiplier, domain size, and scale-interval length are

$$
q_C=\frac{Q_C}{\rho_0\ell_Q^3}
=\int|c|^2d^3\widehat x\,d\mathfrak s,
\qquad
\widehat\omega_C=\frac{\hbar\omega_C\ell_Q^2}{K_x},
\qquad
\widehat R=\frac{R}{\ell_Q},
\qquad
L_{\mathfrak s}=\mathfrak s_+-\mathfrak s_-.
\tag{PA34}
$$

The dimensionless stationary functional is
$\widehat E-\widehat\omega_Cq_C$.

### 7.3 Temporal groups

Using $t_Q=\hbar\ell_Q^2/K_x$, the temporal completion introduces

$$
\begin{aligned}
c_\Psi&=\frac{C_\Psi K_x}{\hbar^2\ell_Q^2},
\\
c_\Phi&=\frac{C_\Phi v_Q^2K_x}
{\hbar^2\rho_0\ell_Q^2},
\\
e_{tx}&=\frac{\epsilon_xv_Q^2K_x}
{\hbar^2\rho_0\ell_Q^2},
\\
e_{t\mathfrak s}&=
\frac{\epsilon_{\mathfrak s}v_Q^2K_x}
{\hbar^2\rho_0}.
\end{aligned}
\tag{PA35}
$$

These groups affect dynamics and fluctuation frequencies. They do not enter the
static Gauss-compatible functional (PA32).

### 7.4 Gauge-normalization invariance

Under the source-unit redundancy

$$
\mathcal A_M\mapsto a\mathcal A_M,
\quad
\Phi\mapsto a\Phi,
\quad
g_Q\mapsto\frac{g_Q}{a},
\quad
\mu_{x,\mathfrak s}\mapsto a^2\mu_{x,\mathfrak s},
\quad
v_Q\mapsto av_Q,
\quad
\lambda_H\mapsto\frac{\lambda_H}{a^4},
\tag{PA36}
$$

one also has

$$
C_\Phi\mapsto\frac{C_\Phi}{a^2},
\qquad
\epsilon_x\mapsto\frac{\epsilon_x}{a^2},
\qquad
\epsilon_{\mathfrak s}\mapsto
\frac{\epsilon_{\mathfrak s}}{a^2},
\qquad
C_\Psi\mapsto C_\Psi.
\tag{PA37}
$$

Equations (PA29) and every group in (PA33)--(PA35) are invariant. A numerical
parameter point must therefore be stated through these groups rather than a
normalization-dependent tuple of $g_Q$, $v_Q$, $\mu$, and $\lambda_H$.

---

## 8. First numerical variational class

### 8.1 Declared class

For finite spatial domain $\Omega_R$, no-flux scale interval, fixed charge, and
a chosen gauge condition, define

$$
\mathcal V_{R,\mathfrak s}^{\mathrm{ax}}(q_C)
=\left\{
(\psi,h,a_i,a_{\mathfrak s},c)
\ \middle|\
\begin{array}{l}
\text{axisymmetric finite-energy representatives of (PA32)},\\
\text{boundary data (PA27)--(PA28)},\\
\int|c|^2=q_C,\quad N_G^{\mathrm{outer}}=0
\end{array}
\right\}/\mathcal G_0,
\tag{PA38}
$$

where $\mathcal G_0$ contains gauge transformations that approach the identity
at the fixed outer representative. A solver may use a smaller explicit ansatz
only if every removed degree of freedom is listed.

### 8.2 Required initialization basins

The first experiment must minimize the same functional and parameter point from
at least:

1. separated confined-core data;
2. merged-core data;
3. closed-loop data when represented by the numerical ansatz;
4. carrier-lump data;
5. a delocalized low-amplitude carrier control;
6. one split-charge or multicore seed.

The finite set does not exhaust the field space. Its admissible conclusion is
an ordering among the converged basins represented inside
$\mathcal V_{R,\mathfrak s}^{\mathrm{ax}}(q_C)$.

### 8.3 Decision quantities

For every converged basin $b$, record

$$
\mathcal R_b=
\left(
\widehat E_b,
q_{C,b},
\widehat\omega_{C,b},
L_b,
R_{C,b},
\|\delta\widehat E\|,
\mathcal V_b,
\Phi_{\partial\Omega,b}
\right),
\tag{PA39}
$$

where $\mathcal V_b$ is a declared virial residual and
$\Phi_{\partial\Omega,b}$ is the outer flux residual. The carrier-retention
condition is

$$
\widehat\omega_{C,b}<e_C,
\tag{PA40}
$$

and a measured basin ordering must be written as

$$
\widehat E_{b_*}
<\min_{b\in\mathcal B_{\mathrm{tested}}\setminus\{b_*\}}
\widehat E_b
\quad\text{within the declared class and tolerances}.
\tag{PA41}
$$

It cannot be promoted to an unrestricted global-minimum statement.

### 8.4 Unresolved sectors

The first class leaves unresolved:

- non-axisymmetric deformations and knots;
- arbitrary multicore and fragmented-charge configurations;
- higher scale and transverse modes omitted by a reduced ansatz;
- topology-changing paths outside the represented basins;
- infinite-domain existence;
- the full fixed-charge, gauge-quotiented Hessian and mixed dynamical spectrum;
- real-time decay, tunnelling, and continuum thresholds;
- quantum spin and statistics.

Every numerical report must retain this list and add any sectors removed by its
implementation.

### 8.5 Registered fixed-charge campaigns

The first registered point sets
$\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
=k_{Cx}=k_{C\mathfrak s}=u_C=1$,
$u_\rho=u_\varphi=u_H=4$, $e_C=0.75$, $h_C=1.50$, $q_C=4$, and
$L_{\mathfrak s}=1$ in the $\mathfrak s$-independent, $a_0=0$ class.
The primary and domain grids are $(R,N)=(4,17)$ and $(5,21)$.

Canonical-preimage continuation preserves the action, coefficient point,
charge, grids, seeds, field class, projectors, diagnostics, and gate
thresholds. Five structural primary arms pass Q1–Q4. The frozen
lowest-energy rule selects `P:separated_core`, with
physical gradient RMS $1.93697\times10^{-4}$ and cutoff virial
$1.89101\times10^{-3}$ against the Q2 ceilings $3\times10^{-4}$ and $0.08$.
The primary and independent verifier both return
`PASS—Q2-QUALIFIED PRIMARY BACKGROUND`.

Every domain arm and the selected high-resolution arm fails Q2, so the
stronger domain-and-resolution qualification fails. The selected field also
has $R_C=2.56816>R/2$, outer carrier fraction $0.0154769>10^{-3}$, and
$\widehat\omega_C=0.961914>e_C=0.75$. It therefore supplies a finite-grid
stationary background without establishing localization or carrier retention.
The primary energy selection is not a domain-stable basin ordering. The
complete receipts are recorded in
`computations/particle-stationary-bvp-report.md` and
`computations/particle-stationary-q2-recovery-report.md`.

### 8.6 Full constrained fluctuation qualification

A qualified stationary background determines one joint perturbation space
$\mathcal V_Q$ satisfying the linearized fixed-charge, Gauss, boundary, and
gauge conditions. If $P_{\rm phys}$ is the orthogonal projector onto that
space, the physical energetic Hessian is

$$
\mathbb K_Q^{(2)}
:=
P_{\rm phys}\,
\delta^2\!\left(\widehat E-\widehat\omega_Cq_C\right)
P_{\rm phys}\big|_{\mathcal V_Q}.
\tag{PA42}
$$

When separately constructed charge and gauge projectors commute,
$P_{\rm phys}=P_QP_{\rm gf}$; otherwise the joint constraint space must be
constructed directly. Energetic stability requires no negative physical
eigenvalue, with every zero mode assigned to an exact symmetry or removed
gauge direction.

The action has second-order temporal terms for the charged fields and a
first-order term for the neutral carrier. Its full linearization is therefore
the mixed pencil

$$
\boxed{
\mathbb P_Q(\omega)
=\mathbb K_Q^{(2)}
-i\omega\mathbb G_Q
-\omega^2\mathbb M_Q,}
\tag{PA43}
$$

where $\mathbb M_Q$ follows from the positive charged-field temporal
coefficients and $\mathbb G_Q$ contains the carrier symplectic term and any
gyroscopic mixing. For the convention $e^{-i\omega t}$, a qualified isolated
solution requires no mode with $\operatorname{Im}\omega>0$, no undeclared
Jordan growth, and converged discrete and continuum spectra.

The reduced CC29 separation mode and CC47 frozen line-density modes give
positive curvature under their stated premises. MCC9 verifies one such point.
Those modes are proper subspaces of (PA42)--(PA43). The selected
`P:separated_core` artifact supplies a Q2-qualified finite-grid background on
which (PA42) can be assembled. The joint constrained Hessian has not been
evaluated, its domain and resolution limits remain unqualified, and the
temporal groups required by (PA43) remain unselected. The complete boundary
and convention map are given in
`foundations/matter-completion-boundary.md` §10.

---

## 9. What is closed and what remains open

| Question | Result |
|---|---|
| Is the optional unified mixing ansatz used? | No; it is outside this branch |
| Does direct first-order local gauging admit a source-free nonzero condensate vacuum? | No, by (PA3)--(PA6) |
| Is a time-dependent local $SU(2)_Q$ transformation defined? | Yes, conditionally, by (PA7)--(PA8) |
| Is the temporal completion gauge invariant and dimensionally homogeneous? | Yes, for the declared coefficients |
| Is Gauss's law explicit? | Yes, (PA14)--(PA15) |
| Does the neutral fixed-charge stationary sector satisfy Gauss's law? | Yes, by (PA16)--(PA17) |
| Are carrier backreaction and the density trap in one variational problem? | Yes, (PA21)--(PA23) |
| Is the stationary problem nondimensionalized without gauge-normalization dials? | Yes, (PA29)--(PA37) |
| Is a numerical coefficient point selected? | Yes for the registered fixed-charge campaign; its physical calibration remains open |
| Does a Q2-qualified finite-grid configuration exist in the registered class? | Yes; five structural primary arms pass Q1–Q4, and the frozen rule selects `P:separated_core` |
| Is any basin the unrestricted global minimum? | Undetermined and not established by finite controls |
| Is the full physical Hessian or mixed dynamical spectrum evaluated? | No; the background is available, but the joint physical projector, Hessian, and temporal pencil remain unevaluated |
| Is a physical particle mass, radius, charge, spin, spectrum, or lifetime obtained? | No |

The action and stationary boundary inventory define the registered
mathematical boundary-value experiment at one dimensionless point.
Canonical-preimage continuation yields the independently verified verdict
`PASS—Q2-QUALIFIED PRIMARY BACKGROUND`. The result establishes stationarity
inside the finite-grid represented class. Localization, carrier retention,
domain and resolution convergence, unrestricted basin ordering, and physical
identification remain open.

---

## 10. Falsification boundary

The analytic closure fails if any of the following is shown:

1. the Pauli identity (PA3) does not imply the first-order vacuum source (PA6)
   under the declared fundamental representation;
2. the action (PA11)--(PA12) fails time-dependent local $SU(2)_Q$ covariance;
3. variation with respect to $\mathcal A_0^a$ does not give (PA14)--(PA15);
4. the static ansatz (PA16)--(PA17) fails Gauss's law;
5. any term in the action has inconsistent source units;
6. the dimensionless energy or groups in (PA29)--(PA35) retain a source-unit
   dimension or gauge-normalization dependence;
7. the coupled stationary equations omit a variation of (PA12).

The current numerical-quality receipt does not falsify the algebra above. It
evaluates the declared optimizer at the tested coefficient point and qualifies
no basin; stronger numerical methods and other coefficient points remain open.

---

## 11. Conclusion

The particle chain now has one explicit conditional action suitable for a
fixed-$Q_C$ stationary solve. The key closure is structural: a source-free
first-order local gauging of the nonzero fundamental condensate is obstructed by
its unavoidable gauge charge, while the selected second-order charged-field
kinetics give a time-local gauge symmetry and a Gauss-compatible static sector.
The neutral carrier remains first order and supplies the exact fixed charge.

The registered one-point campaign executes this variational class, but its
twelve primary/domain arms do not meet the stationary-quality gate. Any
further campaign requires a separately frozen numerical method or coefficient
point; the current receipt supports no basin ordering. Particle masses, radii,
spectra, and lifetimes remain downstream of a converged localized solution.
The stationary and fluctuation qualification operators are explicit in
(PA42)--(PA43), while their evaluation remains downstream of that background.

---

## References

- `foundations/interscale-current-soliton.md`—conditional scale current and soliton-pinch boundary.
- `foundations/nonabelian-magnetic-core-boundary.md`—auxiliary smooth core and confinement boundary.
- `foundations/core-trapped-charge-support.md`—neutral-carrier support and reduced finite-separation theorem.
- `foundations/matter-completion-boundary.md`—nine-part interface and full
  stationary-spectrum qualification boundary.
- `foundations/cassi-theory-reference.md`—particle-sector reference context.
- `foundations/unified-lagrangian.md`—optional conservative-sector bookkeeping.
- `parameter-inventory.md`—coefficient and boundary-data registry.
- `predictions/falsifiable-predictions.md`—particle prediction and evidence registry.
- `computations/particle_action_closure_check.py`—deterministic covariance, source, stationary-variation, unit, and dimensionless-group checker.
