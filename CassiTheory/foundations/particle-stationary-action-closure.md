# Particle-Sector Action and Fixed-Charge Variational Closure

## Status: Hypothesized temporal completion / Derived conditional action, scalar-reduction, parent-vacuum, dilation and fixed-charge identities / Mapped carrier coupling / Tested prepared binding, finite-grid spectra and parent correspondences—September 2026

## Abstract

The magnetic-core and trapped-charge chain now supplies a conditional static
energy, but its source authorities do not yet define one time-local gauge action
for a coupled particle solve. This document closes that specific boundary. It
combines the registered Yang/Yin composition energy, the conditional adjoint
$SU(2)_Q$ core, and the neutral trapped carrier into one particle-sector action.
The branch is separate from the optional sector assembly in
`foundations/cassi-theory-reference.md` and
`foundations/unified-lagrangian.md`; its microscopic carrier is a declared
gauge singlet with an independent global charge.

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
groups, and first numerical variational class are derived below. At
$h_C=1.50$, the independently matched lowest energetic eigenpairs of one
diffuse finite-grid background contain no negative mode on its
$13622$-dimensional strict-shell $C_4$ physical quotient, although its
numerically near-zero global carrier-phase symmetry mode remains concentrated
at grid scale.

At the Mapped coupling $h_C=2.9598260763447164$, the stored Cartesian
stationary branch is nodeless, localized and carrier-retaining under its
finite-grid action. Its six matched lowest constrained $C_4$ energetic
eigenpairs contain a near-zero carrier-phase mode and five positive modes.
The carrier concentrates on one parity sublattice, and its edge-gradient
energy contradicts a smooth-carrier interpretation on the measured sequence.

The same action has an exact empty-sector invariant: under closed boundaries,
$Q_C(0)=0$ implies $\chi_C(t)=0$. A continuum-consistent scalar reduction
supports static binding at prepared $Q_C=16$ and $256$, reproduced by
independent collocation. The smooth $Q_C=16$ constrained spatial stability
verdict is `INCONCLUSIVE`. Microscopic production, full temporal and nonlinear
stability, physical normalization and particle identity remain open
(`computations/matter-formation-continuum-report.md`).

An optional positive-inertia carrier parent has a signed conserved charge,
a canonical complex-scalar representation and a stationary embedding of the
same spatial profiles. Its 31 prescribed-background Gaussian trajectories
pass an independently reconstructed scalar pair-production benchmark.
The physical parent coefficient and action normalization are unselected;
interacting backreaction, localized creation and fermionic matter remain
open (§8.8).
Its classical scalar potential has an exact global vacuum boundary.
Spatial dilation excludes an energetically stable, regular, localized
single-frequency state with zero signed charge in three dimensions (§8.9).
Gauge neutrality alone does not impose zero signed charge.
At fixed signed parent charge, the minimized temporal energy contributes a
positive rank-one population penalty. All 24 frozen embeddings have
independently verified positive finite-grid radial curvature. Nine of twelve
domain/resolution comparisons pass, leaving aggregate radial-domain
qualification `INCONCLUSIVE` because the population-16 domain comparisons
fail (§8.10). This result supplies no full spatial or dynamical stability
claim.
The selected population-256 subset supports all tested angular and phase
sectors on four finite grids. Seven of eight spatial comparisons pass;
the dipole nonsymmetry gap fails the domain comparison. The combined
scalar-parent spatial verdict is `INCONCLUSIVE` (§8.11).

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
- infinite-domain existence and a continuum limit;
- a domain- and resolution-converged constrained energetic Hessian on the
  localized branch;
- the mixed dynamical spectrum, including spatial qualification of every
  symmetry mode;
- real-time decay, tunnelling, formation, and continuum thresholds;
- quantum spin and statistics.

Every numerical report must retain this list and add any sectors removed by its
implementation.

### 8.5 Registered fixed-charge campaigns

The first registered point sets
$\alpha_{\mathfrak s}=\gamma_x=\gamma_{\mathfrak s}
=k_{Cx}=k_{C\mathfrak s}=u_C=1$,
$u_\rho=u_\varphi=u_H=4$, $e_C=0.75$, $h_C=1.50$, $q_C=4$, and
$L_{\mathfrak s}=1$ in the $\mathfrak s$-independent, $a_0=0$ class. Its
higher-precision separated-core endpoint has physical-gradient RMS
$5.471248126403572\times10^{-5}$ and energy $3.854183410304055$.
The field remains diffuse, its carrier frequency exceeds the bulk threshold,
and neither the larger-domain nor finer-grid comparison qualifies. This
background is retained as the input to the existing one-point energetic
Hessian calculation.

The direct normalized carrier-coordinate campaign preserves the same action,
charge, boundary class, and all other fixed coefficients while selecting
$h_C=2.9598260763447164$ through a frozen ordered density-depletion scan. The
fixed-charge map represents the carrier without saturated nonnegative
coordinates. Its stationary endpoint is nodeless, localized, and retained on
$N=17,21,25,29$ grids at $R=4$, and a separate $R=5$ comparison also
qualifies. The carrier radius stays between $1.56$ and $1.64$, and the
same-domain absolute energy differences decrease from $0.12339$ to $0.04261$
to $0.01899$. Independent reconstruction verifies every stored field,
diagnostic, adjacent comparison, and stopping decision. See
`computations/particle-stationary-precision-v5-report.md`,
`computations/particle-carrier-direct-coordinate-report.md`, and
`computations/particle-carrier-resolution-recovery-report.md`.

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
Those modes are proper subspaces of (PA42)--(PA43). On the diffuse $h_C=1.50$
background, the strict-shell $C_4$ fluctuation space gives a
$13622$-dimensional fixed-charge physical quotient after removal of the
rank-$1677$ coupled gauge image. Independent construction reproduces the
background, quotient, phase direction, Hessian symmetry, and directional
curvatures.

Two independent eigensolvers agree on the six matched lowest eigenvalues to
$3.11\times10^{-14}$. They identify one numerically near-zero global
carrier-phase symmetry mode, no negative mode, and five positive modes. The
phase direction has high-frequency fraction $0.33454>0.20$, so its spatial
interpretation
remains unresolved. The larger-domain and finer-grid fields at this
coefficient point do not qualify, and the temporal groups remain unselected.

The localized $h_C=2.9598260763447164$ branch has its own
$77000$-dimensional fixed-charge $C_4$ physical quotient after removal of the
rank-$11775$ complete allowed gauge image. Independent eigensolvers agree on
the six matched lowest eigenvalues to $6.00\times10^{-14}$. They identify one
numerically near-zero global carrier-phase symmetry mode, no negative mode,
and five positive modes; the first positive value is $0.01527618220595$,
compared with
$\epsilon_\lambda=6.092903959\times10^{-4}$. The phase mode is entirely
carrier-imaginary and has high-frequency fraction $0.8744032081>0.20$, so its
spatial classification remains inconclusive. A localized Hessian-resolution
sequence and the temporal groups are unavailable. See
`computations/particle-physical-hessian-precision-v2-report.md`,
`computations/particle-carrier-resolution-recovery-report.md`, and
`computations/particle-localized-physical-hessian-report.md`.

---

### 8.7 Carrier creation and the continuum scalar sector

The carrier law conserves a nonnegative population. Under closed spatial and
scale boundaries its continuity equation is

$$
\partial_t|\chi_C|^2+\nabla_x\cdot\mathbf j_x+\partial_s j_s=0,
\qquad
\mathbf j_x=\frac{K_{Cx}}{\hbar}\operatorname{Im}
(\chi_C^*\nabla_x\chi_C),
\qquad
j_s=\frac{K_{Cs}}{\hbar}\operatorname{Im}
(\chi_C^*\partial_s\chi_C).
$$

All potential terms cancel in this identity. Consequently,

$$
\boxed{Q_C(0)=0\ \Longrightarrow\ Q_C(t)=0
\ \Longrightarrow\ \chi_C(t)=0\quad\text{almost everywhere}.}
$$

The implication assumes a well-posed evolution and no carrier flux through the
boundary. The normal-ordered first-order carrier Hamiltonian also commutes with
carrier number: hopping, density coupling, and carrier self-repulsion preserve
the empty number sector. A time-dependent density trap alone cannot populate
it. Physical pair production requires microscopic degrees of freedom and
interactions that the present carrier action does not specify. Its nonnegative
norm also requires a separate identification before it can represent a signed
physical charge.

The static density-trap question admits an exact simplification in the
scale-independent sector with constant vacuum boundary data and a topology
class admitting a globally constant composition representative. Set
$f=\sqrt{\psi^\dagger\psi}$ and $c=|\chi_C|$. Covariant diamagnetism gives
$|\partial_i f|\leq|D_i\psi|$, while
$|\partial_i c|\leq|\partial_i\chi_C|$. Gauge curvature, adjoint gradients,
adjoint radial potential, and the composition square contribute nonnegative
energy. Their lower bound is attained by

$$
\psi=f\psi_0,\qquad
\psi_0=(\varphi^{-1/2},\varphi^{-1})^T,\qquad
h=h_0=(0,0,1),\qquad a_i=a_{\mathfrak s}=0.
$$

Here $\|\psi_0\|=1$ and $\delta_\varphi(f\psi_0,h_0)=0$ for every $f$.
The Hermitian generators make all gauge currents vanish in this real-amplitude
representative. The adjoint and composition variations vanish; the remaining
field equations are the coupled amplitude equations. For unit scale measure
and $k_{Cx}=1$, the energy infimum in this class therefore equals the scalar
infimum

$$
E_{\rm sc}=\int_{\mathbb R^3}\left[
\frac12|\nabla f|^2+\frac12|\nabla c|^2+
\frac{u_\rho}{4}(f^2-1)^2+
\bigl(e_C-h_C(1-f^2)\bigr)c^2+\frac{u_C}{2}c^4
\right]d^3x,
\qquad Q_C=\int c^2\,d^3x.
$$

Clipping $f$ to $[0,1]$ cannot increase this energy. With $w=1-f$ and
$g(w)=2w-w^2$, the interaction is $-h_Cg(w)c^2$. Symmetric decreasing
rearrangement of $w$ and $c$ decreases both Dirichlet energies, preserves their
individual potential integrals and charge, and increases
$\int g(w)c^2$ by the Hardy–Littlewood inequality. Thus the infimum has a radial
representative under the required Sobolev and decay conditions. On a ball,
zero extension of $w,c\in H^1_0(B_R)$ preserves the specified boundary traces.
These infimum identities do not prove attainment on infinite space, uniqueness,
fission stability, or real-time formation. Forced magnetic charge, boundary
holonomy, and scale winding require their own variational classes.

The radial stationary equations used in the continuum calculation are

$$
-\Delta_r f+u_\rho(f^2-1)f+2h_Cc^2f=0,
\qquad
-\frac12\Delta_r c+
\bigl[e_C-h_C(1-f^2)+u_Cc^2\bigr]c=\omega_Cc,
$$

with $f'(0)=c'(0)=0$, $f(R)=1$, $c(R)=0$, and fixed $Q_C$.

For an exact nodeless stationary carrier, the imaginary-component quadratic
form is nonnegative by a ground-state identity. Set
$U_C=e_C-h_C(1-f^2)$ and
$H_{\rm phase}=-\Delta+2(U_C-\omega_C)+2u_Cc^2$, so the carrier equation gives
$H_{\rm phase}c=0$. For a real perturbation $b=c\vartheta$ with vanishing
boundary terms, integration by parts yields

$$
\langle b,H_{\rm phase}b\rangle
=\int c^2|\nabla\vartheta|^2\,d^3x\ge0.
$$

The global carrier phase has $b\propto c$ and zero curvature. This identity
applies to admissible perturbations of the positive stationary profile;
it makes the numerical phase spectrum a check of the operator and
stationarity. The coupled amplitude operators still carry the unresolved
spatial stability question.

`computations/matter-formation-continuum-report.md` records the finite-volume
and independent collocation calculation at the selected coefficients.

The stored Cartesian carrier sequence has a separate ultraviolet obstruction.
At $N=25,29$, its high-frequency norm fractions are $0.8741672013$ and
$0.8744032064$. At $N=29$, one of eight parity sublattices contains
$99.98631608\%$ of the carrier norm. The nearest-neighbour carrier gradient
energies grow from $107.8149354$ to $146.7857405$, while their
$\Delta x^2$-weighted values remain $11.9794373$ and $11.9825094$.
The centred derivative has symbol $i\sin(k\Delta x)/\Delta x$, including a
Nyquist zero; its squared energy does not uniformly control a nearest-neighbour
gradient. The scoped spatial verdict is
`CONTRADICTS—smooth-carrier interpretation on the measured sequence`. The finite-grid PA42
eigenpairs remain scoped to that lattice stationary field. The scalar
continuum calculation supplies a distinct variational discretization.

At the two qualified prepared scalar populations, the population-256 endpoint
has a larger RMS radius, lower energy per carrier and a more strongly
depleted mediator core than the population-16 endpoint. The two endpoint
measurements establish no preferred particle size or scaling law.
The population-256 lump has lower energy than the trial state of sixteen
asymptotically separated population-16 lumps under the same reference.
This specific comparison supplies no universal fission or dynamical merger
result (`computations/matter-formation-continuum-report.md` §6).

### 8.8 A conditional hyperbolic carrier parent

A positive carrier temporal stiffness supplies a candidate signed-charge
extension whose low-frequency branch approaches the first-order equation.
The microscopic choice of this extension is Hypothesized. Its conditional
identities can be derived without selecting a physical carrier or mass.
The source-unit addition is $C_C|\partial_t\chi_C|^2$, where
$C_C>0$ and $[C_C]=\hbar T$. Its dimensionless coefficient and the
overall action normalization are

$$
a_C=\frac{C_CK_x}{\hbar^2\ell_Q^2},
\qquad \mathcal N_Q=\rho_0\ell_Q^3.
$$

Write $a=a_C$ and $\chi$ for the dimensionless carrier in the
scale-independent scalar sector. The numerical convention for $Q_C$
is the normalized integral in §8.7; source-unit charges also contain
$\mathcal N_Q$. With $U_C(f)=e_C-h_C(1-f^2)$, the carrier Lagrangian is

$$
\mathcal L_a=a|\dot\chi|^2+
\frac{i}{2}(\chi^*\dot\chi-\dot\chi^*\chi)
-\frac{k_{Cx}}2|\nabla\chi|^2
-U_C(f)|\chi|^2-\frac{u_C}{2}|\chi|^4.
$$

Variation and the global phase symmetry give

$$
a\ddot\chi-i\dot\chi-\frac{k_{Cx}}2\Delta\chi+
[U_C(f)+u_C|\chi|^2]\chi=0,
$$

$$
\boxed{
\rho_a=|\chi|^2-2a\,\operatorname{Im}(\chi^*\dot\chi),
\qquad
\partial_t\rho_a+\nabla\cdot\mathbf j_a=0,
\qquad
\mathbf j_a=k_{Cx}\operatorname{Im}(\chi^*\nabla\chi).}
$$

The conserved density has both signs. For a stationary carrier
$\chi=e^{-i\omega t}c$, the spatial multiplier and normalized conserved
charge satisfy

$$
\boxed{
\omega+a\omega^2=\omega_C,\qquad
\omega=\frac{2\omega_C}{1+\sqrt{1+4a\omega_C}},
\qquad
\mathcal Q_a=(1+2a\omega)Q_C.}
$$

These identities require $1+4a\omega_C>0$. The second root has the opposite
sign of $1+2a\omega$. The existing stationary profiles therefore have a
conditional embedding with a different conserved charge. Their fixed-$Q_C$
spatial Hessians do not settle the enlarged fixed-$\mathcal Q_a$ dynamical
problem.

The uniform phase rotation
$\phi=\sqrt{\mathcal N_Qa}\,e^{-it/(2a)}\chi$ puts the carrier action
in canonical second-order form:

$$
\frac{S_C}{\hbar}=\int dt\,d^3x\left[
|\dot\phi|^2-v_a^2|\nabla\phi|^2-M_a^2(f)|\phi|^2
-\frac{u_C}{2\mathcal N_Qa^2}|\phi|^4\right],
\qquad
v_a^2=\frac{k_{Cx}}{2a},
\quad
M_a^2(f)=\frac1{4a^2}+\frac{U_C(f)}a.
$$

The time-dependent phase rotation shifts the Hamiltonian by a constant
multiple of the conserved global charge. The zero-charge pair sector has
the same energy balance in both descriptions. Its particle and antiparticle
labels refer to the positive-energy modes of the canonical quadratic
field.

The neutral carrier remains a singlet of the internal gauge group.
Matching its principal propagation speed to the Yang/Yin field requires
$a=k_{Cx}c_\Psi/2$ under the temporal convention in §7.3; the other gauge and
adjoint sectors also require compatible temporal coefficients. This
condition relates free inputs and establishes no measured causal speed.
The action normalization $\mathcal N_Q$ controls vacuum field amplitudes
and the canonical interaction strength. It remains physically unselected.

An exactly zero classical field with zero velocity still remains zero.
In the quadratic quantum theory, a prescribed time-dependent mediator
changes $M_a^2$ and mixes positive- and negative-frequency modes.
The in-vacuum can then contain equal particle and antiparticle
occupations relative to the out-vacuum while total signed charge stays
zero. This supplies a conditional creation channel with a specified quantum
state and externally supplied history. The full quartic interaction and
mediator backreaction are omitted by that Gaussian truncation; their effects
are not established as negligible. The canonical interaction coefficient
$u_C/(\mathcal N_Qa^2)$ remains unselected, so a free-mode calculation alone
supplies no controlled interacting production rate.

`computations/matter-formation-hyperbolic-parent-prereg.md` specifies the
finite correspondence calculation and its standard tanh-quench benchmark.
The parent family introduces no electric, baryonic, spin or fermionic
assignment. Physical coefficient selection, quantum normalization,
renormalized backreaction, localized production and full stability remain
separate requirements for a matter-formation mechanism.

### 8.9 Neutral-vacuum and stationary-localization boundary

The proposed parent has a classical vacuum condition and a separate
restriction on neutral scalar localization. Both follow from the same action;
neither selects its physical temporal coefficient or quantum normalization.
This section retains the scale-independent scalar sector, positive spatial
stiffness, regular finite-energy fields and the constant exterior vacuum.
The parent Hamiltonian includes the nonnegative mediator kinetic energy.
Here neutral means zero signed global charge $\mathcal Q_a$. The carrier's
singlet representation under the internal gauge group does not impose
$\mathcal Q_a=0$.
All energies below are divided by the positive factor $\mathcal N_Q$.

For $Q_C>0$, Cauchy–Schwarz applied to the charge in §8.8 gives

$$
a\int|\dot\chi|^2\,d^3x
\ge\frac{(Q_C-\mathcal Q_a)^2}{4aQ_C}.
$$

At $\mathcal Q_a=0$, equality requires
$\dot\chi=i\chi/(2a)$. Direct completion of the temporal square gives
$H_{\rm can}/\mathcal N_Q=H_{\rm original}/\mathcal N_Q+
\mathcal Q_a/(2a)$, so both Hamiltonians agree in this sector.
The least temporal energy adds $|\chi|^2/(4a)$ to the static potential.
With $z=f^2\ge0$, $n=|\chi|^2\ge0$,
$B=e_C+1/(4a)$ and $s=\sqrt{u_\rho u_C/2}$, that potential is

$$
V_a(z,n)=\frac{u_\rho}{4}(z-1)^2+
[B-h_C(1-z)]n+\frac{u_C}{2}n^2.
$$

Its nonnegativity can be decided exactly. The factorization

$$
V_a=
\left[\frac{\sqrt{u_\rho}}2(1-z)-\sqrt{\frac{u_C}{2}}n\right]^2+
\left[B-(h_C-s)(1-z)\right]n
$$

is nonnegative when $h_C-B\le s$. If $h_C\ge s$, the second coefficient
is smallest at $z=0$; if $h_C<s$, it is positive on $0\le z\le1$,
while the original polynomial is nonnegative at $z\ge1$.
Conversely, when $h_C-B>s$, the point
$z=0,\ n=(h_C-B)/u_C$ has negative potential. Thus, for the positive
coefficients used here,

$$
\boxed{
V_a(z,n)\ge0\ \text{for all }z,n\ge0
\quad\Longleftrightarrow\quad
h_C-e_C-\frac1{4a}\le\sqrt{\frac{u_\rho u_C}{2}}.}
$$

When $h_C>e_C+s$, the exterior global-vacuum interval is
$0<a\le a_{\rm vac}=1/[4(h_C-e_C-s)]$. If $h_C\le e_C+s$,
every positive $a$ meets this classical potential condition.
Minimizing first over $z$ gives
$z_*=\max(0,1-2h_Cn/u_\rho)$. On the active interval the reduced
potential is $Bn+(u_C/2-h_C^2/u_\rho)n^2$.
A negative global minimum requires $h_C>B+s>s$, making this part
concave. Its endpoints and the remaining $z=0$ parabola then give

$$
\min V_a=
\min\left(0,\frac{u_\rho}{4}
-\frac{[\max(h_C-B,0)]^2}{2u_C}\right).
$$

At $a=a_{\rm vac}$ the exterior vacuum is degenerate with the homogeneous
state $z=0,\ n=\sqrt{u_\rho/(2u_C)}$. Above this boundary, a lower
homogeneous phase exists. The exterior $(f,\chi)=(1,0)$ remains a local
minimum of the classical potential: its quadratic mediator and carrier
terms are positive. The lower phase supplies no nucleation rate or
localized formation history. The condition also differs from the sign of
$M_a^2(0)$ at an externally held depleted mediator, whose crossing is
$a_{\rm dep}=1/[4(h_C-e_C)]$ when $h_C>e_C$.
Renormalized quantum corrections require their own calculation.

A regular single-frequency neutral stationary lump has an additional
obstruction. For $\chi=e^{-i\omega t}c(\mathbf x)$ with $Q_C>0$,
zero signed charge fixes $\omega=-1/(2a)$, so the canonical carrier
and mediator are static. Let $\mathcal T$ be their nonnegative gradient
energy and $\mathcal U=\int V_a$. In $d$ spatial dimensions, dilating both
profiles by $\mathbf x\mapsto\mathbf x/\lambda$ gives

$$
E(\lambda)=\lambda^{d-2}\mathcal T+\lambda^d\mathcal U,
\qquad
(d-2)\mathcal T+d\mathcal U=0
$$

at a stationary solution. For $d>2$, a nonnegative potential excludes any
nontrivial finite-energy solution of this ansatz. If the potential takes
negative values and a nontrivial stationary solution exists, its dilation
curvature is

$$
\boxed{E''(1)=-2(d-2)\mathcal T<0.}
$$

The dilation preserves zero signed charge. Thus the specified scalar parent
has no energetically stable, regular, localized single-frequency
zero-signed-charge stationary lump in three spatial dimensions, for any
positive $a$. This is the conditional application of the Derrick scaling
argument. It does not exclude charged stationary states, whose fixed-charge
constraint changes under this dilation; oppositely charged separated
excitations; multi-frequency dynamics; quantum bound states; or additional
gauge, topological and scale sectors.

`computations/matter-formation-parent-vacuum-prereg.md` freezes independent
polynomial minimization, charge-energy and radial-dilation checks.
The prescribed-background pair correspondence in §8.8 and the prepared
fixed-population binding in §8.7 retain their separate scopes. A stable
neutral matter interpretation requires a mechanism beyond this stationary
scalar ansatz.

### 8.10 Fixed signed charge and the parent amplitude Hessian

A nonzero conserved parent charge changes the variational problem. The
carrier population $N=Q_C=\int|\chi|^2$ can vary while its signed charge
$\mathcal Q$ stays fixed; the necessary temporal energy must vary with it.
Minimizing that energy over carrier velocities, with zero mediator
velocity, gives the exact reduced Hamiltonian

$$
\boxed{\mathscr E_{\mathcal Q}[f,c]
=E_{\rm sc}[f,c]+\frac{(N-\mathcal Q)^2}{4aN},\qquad N>0.}
$$

Here $E_{\rm sc}$ is the explicit spatial functional in §8.7 and energies
are divided by $\mathcal N_Q$. The minimizing velocity is
$\dot\chi=i(N-\mathcal Q)\chi/(2aN)$. Additional allowed velocity components
give a nonnegative kinetic excess. The canonical Hamiltonian differs by
the constant $\mathcal Q/(2a)$, so it has the same energetic ordering at
fixed signed charge.

Write the temporal term as $G(N)$. Its derivatives are

$$
G'(N)=\frac{1-\mathcal Q^2/N^2}{4a},
\qquad
G''(N)=\frac{\mathcal Q^2}{2aN^3}.
$$

At a prepared stationary profile of $E_{\rm sc}-\omega_C N$, stationarity
of the parent requires $G'=-\omega_C$. Thus the positive-charge branch has
$D=1+4a\omega_C>0$, $\mathcal Q=\sqrt D\,N$ and the frequency in §8.8.
For real amplitude variations in Euclidean mass-weighted coordinates,
let $H_0$ be the full Hessian of $E_{\rm sc}-\omega_C N$ and
$g=\nabla N=(0,2\sqrt Vc)^T$. The chain rule then gives

$$
\boxed{H_{\mathcal Q}=H_0+\gamma gg^T,\qquad
\gamma=\frac{D}{2aN}>0.}
$$

The extra term is a positive rank-one penalty for changing population.
The population-changing direction remains in this operator.
As $a\to0^+$ on the low-frequency branch, the penalty diverges and its finite
energetic modes approach the fixed-population tangent problem. Angular
modes with zero angular average and imaginary carrier variations have no
first-order population change, so this rank-one term does not settle their
separate qualification.

The response of the stationary branch gives an independent criterion for
this correction. When $H_0$ is invertible, differentiating
$\nabla E_{\rm sc}-\omega_C\nabla N=0$ yields
$H_0\,\partial_{\omega_C}(f,c)=g$. Therefore
$S=g^TH_0^{-1}g=dN/d\omega_C$ on an exact differentiable branch.
If $H_0$ has exactly one negative direction and no zero direction, the
rank-one inertia identity implies

$$
H_{\mathcal Q}>0
\quad\Longleftrightarrow\quad
1+\gamma S<0
\quad\Longleftrightarrow\quad
\frac{d\mathcal Q}{d\omega}=2aN+DS<0.
$$

The negative-index and invertibility hypotheses are essential. A positive
constrained radial spectrum alone does not supply them, and a finite-grid
linear response does not establish a continuum branch derivative.

The charged dilation energy shows how the neutral restriction is avoided
within a specified family of profiles. With static gradient and potential
energies $\mathcal T$ and $\mathcal U$,

$$
\mathscr E_{\mathcal Q}(\lambda)
=\lambda\mathcal T+
\lambda^3\left(\mathcal U+\frac N{4a}\right)
-\frac{\mathcal Q}{2a}
+\frac{\mathcal Q^2}{4aN}\lambda^{-3}.
$$

For nonzero $\mathcal Q$ and a nonnegative canonical potential, this
function is strictly convex for $\lambda>0$: the last term resists
contraction, and the gradient and canonical-potential terms resist
expansion. At a continuum stationary state its curvature is
$-2\mathcal T+9\mathcal Q^2/(2aN)$. The selected charge and trial profile
remain inputs. This one-parameter result determines no physical particle
size and does not prove positivity in every field direction.

The frozen calculation in `computations/matter-formation-charged-stability-prereg.md`
uses eight qualified population-16 and population-256 fields, with three
unselected parent coefficients per field. All 24 parent radial minima are
positive, from $0.93011947$ to $1.95755740$. The independent banded
calculation confirms all 144 reported parent eigenvalue brackets, the
one-negative-index base spectra and the negative charge-slope factors.
Both receipts pass their numerical requirements.

The finite-grid radial verdict is
`SUPPORTS—finite-grid radial fixed-charge energetic stability`.
Nine of twelve domain/resolution comparisons pass. All three population-16
domain comparisons fail, so the separate aggregate is
`INCONCLUSIVE—radial domain/resolution qualification`.
Population 256 meets its measured radial comparisons. The results and
source identities are in `computations/matter-formation-continuum-report.md`
§10. The complete spatial, real-time, nonlinear and physical-matter questions
retain their separate requirements.

### 8.11 Angular and phase sectors of the scalar parent

The signed-charge penalty affects the spherically symmetric real amplitude.
The remaining scalar spatial sectors can be derived directly from the
same reduced Hamiltonian. Write $k=k_{Cx}>0$, $U=e_C-h_C(1-f^2)$ and
$D_\ell=-\partial_r^2-2r^{-1}\partial_r+\ell(\ell+1)/r^2$.
For angular degree $\ell\ge1$, the amplitude operator is

$$
H_\ell=
\begin{pmatrix}
D_\ell+u_\rho(3f^2-1)+2h_Cc^2&4h_Cfc\\
4h_Cfc&kD_\ell+2(U-\omega_C)+6u_Cc^2
\end{pmatrix}.
$$

The imaginary carrier operator at every angular degree is

$$
L_\ell=kD_\ell+2(U-\omega_C)+2u_Cc^2.
$$

These curvatures contain the spatial multiplier
$\omega_C=\omega+a\omega^2$. Their equality with the corresponding
fixed-population spatial operators follows from $G'=-\omega_C$ and the
vanishing first-order population change of these perturbations. Replacing
$\omega_C$ by the parent's temporal frequency $\omega$ would change the
operator. The fixed-population specification in
`computations/matter-formation-stability-prereg.md` uses the explicit
$k_{Cx}=1$ specialization; the carrier stiffness is $k_{Cx}D_\ell$ in the
general expression.

For an exact nodeless stationary carrier, $L_0c=0$. A compactly supported
phase perturbation $b=c\vartheta$ obeys

$$
\langle b,L_\ell b\rangle
=4\pi k\int_0^\infty
\left[r^2c^2(\vartheta')^2+\ell(\ell+1)c^2\vartheta^2\right]dr\ge0.
$$

The global phase is the $\ell=0$ zero direction. The angular amplitude
sector has a related conditional identity. Suppose an exact radial
stationary profile has $f,c>0$, $f'>0$ and $c'<0$ for $0<r<\infty$.
Differentiating the radial field equations gives
$H_1(f',c')^T=0$. Set $v=(f',-c')^T$, $B=4h_Cfc>0$,
$J=\operatorname{diag}(1,-1)$ and
$y=(v_1\xi_1,v_2\xi_2)^T$. Integration by parts gives

$$
\boxed{
\langle y,JH_1Jy\rangle
=4\pi\int_0^\infty r^2\left[
v_1^2(\xi_1')^2+k v_2^2(\xi_2')^2+
Bv_1v_2(\xi_1-\xi_2)^2\right]dr\ge0.}
$$

This formula starts on compactly supported regular perturbations and
extends only to form-domain limits with vanishing boundary terms.
Strict positivity of $v$ and coupling on the connected interior leaves
the translation direction as the possible $\ell=1$ kernel. Since

$$
H_\ell-H_1=
\frac{\ell(\ell+1)-2}{r^2}\operatorname{diag}(1,k)\ge0
\qquad(\ell\ge2),
$$

the same assumptions exclude negative higher-angular amplitude directions.
These are conditional continuum identities. Finite-box sampled derivatives
do not establish the hypotheses or an exact translation zero.

The exterior energetic gaps are $2u_\rho$ and
$2(e_C-\omega_C)$. In the canonical carrier variables the positive
stationary frequency is $\Omega=\sqrt{1+4a\omega_C}/(2a)$, and

$$
M_a^2(1)-\Omega^2=\frac{e_C-\omega_C}{a},
\qquad
M_a^2(0)=\frac1{4a^2}+\frac{e_C-h_C}{a}.
$$

The second expression is the carrier's canonical mass squared at a fully
depleted mediator, rather than a mediator fluctuation mass. These
quantities distinguish the exterior decay condition from an interior
carrier gap. Positive scalar spatial curvature, positive temporal kinetic
energy and coercivity modulo phase and translations would support an
energetic stability argument under a well-posed evolution. Establishing
that coercivity, continuum existence and nonlinear persistence requires
separate evidence. Scale-dependent, gauge, topological and quantum sectors
are outside this scalar statement.

The frozen population-256 calculation in
`computations/matter-formation-parent-spatial-prereg.md` evaluates four
immutable radial profiles and inherits twelve qualified charged radial
embeddings. All four grids give
`SUPPORTS—finite-grid scalar angular and phase energetic qualification`.
The dense primary and independent banded/tridiagonal constructions agree
on all 96 eigenvalues, with maximum discrepancy $7.6343\times10^{-12}$.
Both receipts have numerical `PASS` and no failures.

Seven of eight new spatial domain/resolution comparisons pass. At fixed
spacing, the first non-translation dipole eigenvalue changes from
$2.5041595205$ at $R=12$ to $2.3799505428$ at $R=24$. The difference
$0.1242089777$ exceeds the frozen tolerance $0.0250415952$.
The resulting domain and combined scalar-parent spatial verdicts are
`INCONCLUSIVE`. Sampled symmetry overlap supplies no exact continuum
positivity or monotonicity proof. The complete measurements and immutable
identities are in `computations/matter-formation-continuum-report.md` §11.

### 8.12 Physical normalization and particle identification

A physical mass anchor fixes a conversion between dimensionless and measured
frequencies. It does not by itself select the carrier action, core size or
particle representation. For the scalar parent, the time, action and energy
scales are

$$
t_Q=\frac{\hbar\ell_Q^2}{K_x},\qquad
\mathcal N_Q=\rho_0\ell_Q^3,\qquad
E_Q=\frac{\hbar\mathcal N_Q}{t_Q}.
$$

In the canonical rotating variables of §8.8, the carrier speed and vacuum
frequency are

$$
v_{\rm car}=\frac{\ell_Q}{t_Q}\sqrt{\frac{k_{Cx}}{2a_C}},
\qquad
\omega_{\rm vac}^{\rm phys}=\frac{M_a(1)}{t_Q},
\qquad
M_a^2(1)=\frac{1}{4a_C^2}+\frac{e_C}{a_C}.
$$

Impose a common physical cone $v_{\rm car}=c$ and an external vacuum scalar
rest-energy target $\mathscr E_*=\hbar\omega_{\rm vac}^{\rm phys}$. Writing
$\lambda_*=\hbar c/\mathscr E_*$ gives the conditional family

$$
\boxed{
\frac{\ell_Q(a_C)}{\lambda_*}
=\sqrt{\frac{1/(2a_C)+2e_C}{k_{Cx}}},
\qquad
t_Q=\frac{\ell_Q}{c}\sqrt{\frac{k_{Cx}}{2a_C}}.}
$$

For a selected stationary profile, $N=\int c^2\,d^3\widehat x$ and
$\mathcal Q=\sqrt{1+4a_C\omega_C}\,N$. Assigning one unit to this internal
Noether generator fixes $\mathcal N_Q=1/\mathcal Q$ and
$\rho_0=\mathcal N_Q/\ell_Q^3$. The independent parameter $a_C$ remains.
The construction selects no electromagnetic charge normalization and leaves
the dimensionless coefficients, including the Mapped $h_C$, unchanged.
An observed mass and its Compton wavelength are the same input expressed in
two units.

Core scale, carrier decay length and Compton wavelength describe different
quantities. The stationary exterior equation gives

$$
\ell_{\rm tail}
=\ell_Q\sqrt{\frac{k_{Cx}}{2(e_C-\omega_C)}},
\qquad
\frac{\ell_{\rm tail}}{\lambda_*}
=\frac{M_a(1)}{\sqrt{M_a^2(1)-\Omega^2}}>1
$$

for a nonzero-charge embedding with $1+4a_C\omega_C>0$. The additional
assignment $\ell_Q=\lambda_*$ would require
$a_C=[2(k_{Cx}-2e_C)]^{-1}$. At $k_{Cx}=1,e_C=3/4$ this has no positive
solution. When the global-vacuum condition bounds $a_C\le a_{\rm vac}$,
the smallest allowed core scale follows by evaluating the decreasing
$\ell_Q(a_C)$ at $a_{\rm vac}$. Comparing that bound with a mapped cascade
cell tests the extra core-cell assignment at the selected coefficients.
A different $h_C$, $e_C$ or $k_{Cx}$ defines a different dimensionless
problem and requires its own profile and stability calculation.

The phase rotation also changes the Hamiltonian by a conserved charge.
For the stationary profile,

$$
H_{\rm orig}=E_{\rm sc}+a_C\omega^2N,\qquad
H_{\rm can}=E_{\rm sc}
+\left(\frac1{2a_C}+\omega_C\right)N,
$$

$$
\boxed{
H_{\rm can}-H_{\rm orig}=\frac{\mathcal Q}{2a_C},
\qquad
H_{\rm can}-\Omega\mathcal Q=E_{\rm sc}-\omega_CN.}
$$

The physical canonical energy is $E_QH_{\rm can}$; $\hbar\Omega/t_Q$
is a chemical-potential frequency scale. For an exact localized stationary
continuum solution, write $E_{\rm sc}=T+V$ with $T$ the positive gradient
energy. Dilation of $E_{\rm sc}-\omega_CN$ gives
$T+3(V-\omega_CN)=0$, hence
$E_{\rm sc}-\omega_CN=2T/3>0$ for a nonconstant profile.
Its total energy therefore exceeds its chemical potential times charge.
The choice of physical time generator must be explicit when assigning a
mass; a time-dependent field rotation does not identify those energies.

A common change of units multiplies an eigenvalue difference and its
dimensionally converted tolerance by the same positive factor. It leaves
the accepted domain-comparison verdict invariant. Assigning a different
normalization to each numerical box would compare different physical
models.

Finally, local invertible normalization preserves the Lorentz representation
of the elementary carrier. The topologically trivial scalar restriction
contains bosonic scalar quanta under its usual canonical quantization.
It supplies no Dirac spin representation or fermionic statistics.
Fermionic topological solitons require a specified configuration space and
quantization beyond this restriction. The separate chiral-scalar Dirac
density assignment also has an algebraic obstruction: its two bilinears
are complex conjugates, so simultaneous real positive values are equal
(`foundations/sector-coupling-derivation.md` §1).

The frozen calculation in
`computations/matter-formation-normalization-prereg.md` is independently
verified. At the external $0.511\ \mathrm{MeV}$ vacuum scalar mass target,
the witnesses $a_C=1/64,1/32,1/16$ give distinct lengths
$(2.2350537582,1.6154167965,1.1902203530)\times10^{-12}\ \mathrm m$
while reproducing the same mass, speed and internal generator unit.
The result is `SUPPORTS—conditional one-mass normalization nonuniqueness`.
The global-vacuum bound gives
$\ell_Q\ge6.7893919382\times10^{-13}\ \mathrm m$, above the mapped
electron-cell upper endpoint $6.0141121609\times10^{-13}\ \mathrm m$.
The additional assignment has verdict
`CONTRADICTS—selected scalar electron-core assignment`.
Unit changes leave the failed spatial difference/tolerance ratio
$4.9601064407$ invariant. The chiral-scalar density and action-reality
checks also give their scoped `CONTRADICTS` verdicts. Complete numerical
values, assumptions and receipt identities are in
`computations/matter-formation-continuum-report.md` §12.

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
| Is a numerical coefficient point selected? | Yes; $h_C=2.9598260763447164$ is selected by a frozen ordered numerical scan, so its physical calibration remains open and its status is Mapped |
| Does a physically stationary, localized, retained finite-grid configuration exist in the registered class? | Yes; the Cartesian branch qualifies under its centred-difference action, while the edge-gradient diagnostic contradicts a smooth-carrier interpretation on that sequence. A separate continuum-consistent scalar calculation supports prepared static binding at $Q_C=16$ and $256$ |
| Is any basin the unrestricted global minimum? | Undetermined and not established by finite controls |
| Is the full physical Hessian or mixed dynamical spectrum evaluated? | No. The stored Cartesian fields have independently matched low energetic spectra in a finite-grid $C_4$ quotient. Their phase modes have grid-scale structure. The separate smooth $Q_C=16$ constrained spatial study has no resolved negative mode on four tested grids, but its combined verdict is `INCONCLUSIVE` because the coarse symmetry and domain comparisons fail. Full temporal and nonlinear stability remain open |
| Can carriers form from an exactly empty closed sector? | No; the homogeneous first-order carrier equation preserves $Q_C=0$. A microscopic production action and quantum content are missing |
| Does the optional carrier parent define a classical vacuum condition? | Yes, conditionally: $h_C-e_C-1/(4a)\le\sqrt{u_\rho u_C/2}$ is necessary and sufficient for nonnegative homogeneous canonical scalar potential |
| Can that scalar parent support an energetically stable single-frequency localized state with zero signed charge? | No, under the regularity, finite-energy, constant-vacuum and three-dimensional scalar assumptions of §8.9. Charged, multi-frequency, quantum and additional topological sectors remain outside that statement |
| Does fixed signed parent charge support the measured radial amplitudes? | Yes on all 24 frozen finite-grid embeddings, with independent spectral verification. Nine of twelve domain/resolution comparisons pass; aggregate radial-domain qualification remains `INCONCLUSIVE` because the population-16 domain comparisons fail. Population 256 meets its measured radial comparisons |
| Do the selected scalar-parent angular and phase sectors qualify? | Yes on all four population-256 finite grids, with 96 independently matched eigenvalues. Seven of eight spatial comparisons pass; the dipole nonsymmetry gap fails the domain comparison, leaving combined scalar-parent spatial qualification `INCONCLUSIVE`. Exact continuum positivity identities remain conditional on nodelessness, strict monotonicity and boundary assumptions |
| Does one imposed vacuum mass, propagation speed and internal generator unit determine the scalar action? | No. Three independently reconstructed admissible temporal coefficients give different physical lengths. The selected scalar core assignment to the mapped electron cell is contradicted; spin, statistics and electric charge are unassigned |
| Is a physical particle mass, radius, charge, spin, spectrum, or lifetime obtained? | No |

The action defines a fixed-charge boundary-value problem and an exact
creation obstruction. Its continuum-consistent scalar sector supplies
independently reproduced static binding for two prepared populations at the
selected coefficients. The stored Cartesian branch retains its finite-grid
scope and fails the smooth-carrier diagnostic. The smooth constrained spatial
calculation remains inconclusive under its frozen criteria. The optional
parent has a verified Gaussian pair correspondence, positive measured
fixed-signed-charge radial curvature and selected population-256 angular
and phase support. The radial-domain and combined scalar-parent spatial
aggregates are separately inconclusive. These measurements determine no
physical production channel, normalized particle spectrum or formation
history.

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

The finite-grid measurements leave the action identities intact. The
Cartesian edge-gradient diagnostic contradicts a smooth interpretation of the
stored localized sequence. The separate scalar calculation supports prepared
static binding, with an inconclusive constrained spatial stability result.
A negative qualified continuum mode, collapse or dispersion under the
declared temporal action, or incompatibility with particle observations would
reject stronger physical interpretations without changing the conditional
conservation and gauge identities.

---

## 11. Conclusion

The particle chain now has one explicit conditional action suitable for a
fixed-$Q_C$ stationary solve. The key closure is structural: a source-free
first-order local gauging of the nonzero fundamental condensate is obstructed by
its unavoidable gauge charge, while the selected second-order charged-field
kinetics give a time-local gauge symmetry and a Gauss-compatible static sector.
The neutral carrier remains first order and supplies the exact fixed charge.

The carrier's nonnegative conserved population cannot be generated from
exactly empty closed-sector data. This is an algebraic restriction of the
supplied action. Physical production requires further microscopic degrees of
freedom and interactions.

At the selected dimensionless coefficients, the continuum-consistent scalar
problem has independently reproduced static bound states at prepared
$Q_C=16$ and $256$. The tested $Q_C=4$ profiles spread, and $Q_C=64$ fails
stationary qualification. The smooth $Q_C=16$ branch has no resolved negative
constrained spatial mode on the tested grids; its combined stability verdict
is `INCONCLUSIVE`. The Cartesian localized sequence is parity-concentrated
and fails its smooth-carrier diagnostic. These outcomes establish conditional
density trapping while leaving continuum and temporal stability, actual
formation, physical normalization, particle quantum numbers and statistics
open.

The optional positive-inertia carrier parent supplies a signed charge and a
verified prescribed-background Gaussian pair correspondence. Its classical
potential places an exact constraint on the unselected temporal coefficient.
The zero-signed-charge single-frequency scalar ansatz has a separate
localization obstruction: a nonnegative potential excludes a nontrivial
stationary lump, and any such lump with an available negative-potential
region has a negative dilation direction. A supported physical matter
mechanism must address the corresponding charge, dynamics or field-content
requirements.

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
- `computations/particle-stationary-precision-v5-report.md`—higher-precision finite-grid background and independent gates.
- `computations/particle-physical-hessian-precision-v2-report.md`—matched low energetic spectrum and spatial classification on the diffuse background.
- `computations/particle-carrier-direct-coordinate-report.md`—localized retained stationary branch and larger-domain comparison.
- `computations/particle-carrier-resolution-recovery-report.md`—four-grid refinement and independently verified resolution consistency.
- `computations/particle-localized-physical-hessian-report.md`—matched constrained spectrum and spatial qualification of the finest localized field.
- `computations/matter-formation-continuum-report.md`—empty-sector invariant, ultraviolet diagnosis, smooth prepared binding, constrained stability and conditional Gaussian parent correspondence.
- `computations/matter-formation-hyperbolic-parent-prereg.md`—optional temporal parent, quantum normalization and frozen free-mode schedule.
- `computations/matter_formation_hyperbolic_parent.py`—primary oscillator trajectories and stationary embeddings.
- `computations/verify_matter_formation_hyperbolic_parent.py`—independent raw-array, charge and energy-work verification.
- `computations/matter-formation-parent-vacuum-prereg.md`—classical parent-vacuum and neutral stationary-localization identities with frozen numerical checks.
- `computations/matter_formation_parent_vacuum.py`—closed-form potential, charge-energy and Gaussian dilation witnesses.
- `computations/verify_matter_formation_parent_vacuum.py`—independent unreduced minimization and radial quadrature.
- [Derrick, *Comments on Nonlinear Wave Equations as Models for Elementary Particles*](https://doi.org/10.1063/1.1704233)—finite-energy spatial-dilation restriction.
- `computations/matter-formation-charged-stability-prereg.md`—fixed-signed-charge Hessian, response, inertia and dilation specification.
- `computations/matter_formation_charged_stability.py`—dense primary radial parent spectra and charge-response calculation.
- `computations/verify_matter_formation_charged_stability.py`—independent banded-operator and rank-one-inertia verification.
- `computations/matter-formation-parent-spatial-prereg.md`—conditional angular and phase identities, frozen symmetry and domain criteria.
- `computations/matter_formation_parent_spatial.py`—primary scalar angular and phase spectra with charged-radial inheritance.
- `computations/verify_matter_formation_parent_spatial.py`—independent banded/tridiagonal spectra and primary-vector verification.
- `computations/matter-formation-normalization-prereg.md`—frozen physical normalization and microscopic identification boundaries.
- `computations/matter_formation_normalization.py`—scalar unit family, energy conversion and chiral-scalar witnesses.
- `computations/verify_matter_formation_normalization.py`—independent physical scales, energy quadrature and bilinear checks.
- `foundations/sector-coupling-derivation.md` §1—Dirac chiral-scalar density and interaction obstructions.
