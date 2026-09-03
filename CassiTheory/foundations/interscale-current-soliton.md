# Interscale Yang/Yin Current and the Conditional Soliton Pinch

## Status: Hypothesized action and Wilson-link extension / Derived conditional endpoint, first-order source-action, Wilson-transport, localization, smooth-core, confinement, and carrier-support boundaries / Tested one-point Q2-qualified primary background—September 2026

## Abstract

This document develops one explicit extension of the Cassi Yang/Yin field in
which scale becomes a dynamical coordinate. The extension introduces a complex
Yang/Yin doublet

$$
\Psi(\mathbf x,\mathfrak s,t)
=
\begin{pmatrix}\psi_Y\\[2pt]\psi_I\end{pmatrix},
\qquad
\mathfrak s=\log_\varphi\!\left(\frac{\ell}{\ell_\star}\right),
$$

and derives a continuity law with a distinct interscale current
$J_{\mathfrak s}$. This current is separate from the canonical density-plane
diagnostic $\mathbf J_d$ in `foundations/qi-flow-double-helix.md`.

Within the declared action, total density can enter or leave an observed scale
window through its two scale boundaries. Oppositely charged Yang and Yin phases
support a gauge-invariant relative counterflow. A mixed curvature
$G_{i\mathfrak s}$ can then contribute a radial force when an interscale gauge
current is present. An inward force is conditional on source sign, boundary
conditions, and a positive static response. The positive action by itself does
not generate a universal attractive term or guarantee a soliton.

A finite localized object requires short-distance support in addition to any
pinch. A charged endpoint section supplies one coherent, gauge-covariant
turning realization; its separately declared Wilson-link extension supplies
conditional inter-vertex transport; and a one-way Markov channel supplies an
open alternative
(`foundations/endpoint-link-and-localization-boundary.md`). These endpoint
choices generate no positive $1/R$ core term required by the reduced Derrick
profile. In the smooth unexcised zero-Chern sector there is no finite
stationary radius. An imposed point-core Chern sector supplies the exact
exterior coefficient
$\mathcal B_G=2\pi N_G^2\int d\mathfrak s/e_x^2$. An auxiliary adjoint
$SU(2)_Q$ branch smooths the local core and matches this coefficient. The
registered nonzero fundamental condensate removes the isolated magnetic sector
and confines its flux; the resulting finite net-zero string pair has no
finite-separation minimum in the registered asymptotic energy
(`foundations/nonabelian-magnetic-core-boundary.md`).

The neutral carrier branch in `foundations/core-trapped-charge-support.md`
supplies an exact conserved $Q_C$ and a conditional inverse-length term
$A_C/L$. The reduced pair has one finite root with positive length curvature
when $A_C>C_Q$, the carrier remains below its bulk threshold, and the root lies
beyond core overlap. The separate source-free temporal branch in
`foundations/particle-stationary-action-closure.md` combines this static sector
with the auxiliary adjoint core, derives Gauss's law, and defines the coupled
fixed-$Q_C$ stationary functional. Its registered coefficient point has a
Q2-qualified finite-grid primary background. The selected field fails
localization and carrier retention, and every domain plus high-resolution arm
fails Q2. Its second-order charged-field kinetics are separate from the
first-order interscale action derived here, whose direct local gauging carries
an unavoidable nonzero-condensate Gauss source.

The transverse carrier mode, dimensional normalization, physical calibration,
scale metric, conversion mechanism, compact boundary data, localized
domain-and-resolution-qualified field solution, constrained spectrum, and
particle-sector map remain open. In particular,
$\varphi$ fixes the energy-minimizing Yang/Yin composition and its counterflow
factor; it does not determine the carrier coefficients, gauge coupling, or any
SI scale.

---

## 1. Relation to the canonical Cassi field

### 1.1 The present canonical state

The canonical two-fluid field evolves two real densities,

$$
E_Y(\mathbf x,t),\qquad E_I(\mathbf x,t),
$$

with total density $\rho=E_Y+E_I$, conversion residual
$\varepsilon=E_Y-\varphi E_I$, and scalar coherence gate $q$. The optional
quantity

$$
\mathbf J_d=(E_Y^2+E_I^2)\nabla\theta_d
$$

is a current-like diagnostic in the density plane. It has no scale-coordinate
index and supplies no transport between cascade steps. The real-density
conversion system also has no persistent complex phase degree of freedom.

The construction below adds both ingredients. It is a separate Hypothesized
sector rather than a reinterpretation of $\mathbf J_d$.

### 1.2 Declared scope

The candidate model addresses four questions:

1. What state can carry density across a continuous scale coordinate?
2. What continuity law distinguishes spatial transport from scale transport?
3. Under what conditions can Yang/Yin counterflow source a mixed-curvature
   pinch?
4. What additional support and topology are required for a finite object?

It does not identify a Standard Model particle, derive a compact phase, select
a helix pitch, or reproduce the canonical dissipative conversion law. Those
remain separate physical assignments.

---

## 2. Scale coordinate, state, and action

### 2.1 Coordinate convention

Define the dimensionless continuous scale coordinate

$$
\boxed{\mathfrak s
=\log_\varphi\!\left(\frac{\ell}{\ell_\star}\right)},
\qquad
\boxed{\ell=\ell_\star\varphi^{\mathfrak s}}.
$$

Integer $\mathfrak s=n$ recovers the discrete geometric sequence. The reference
length $\ell_\star$ fixes the coordinate origin. The transformation

$$
\ell_\star' = \ell_\star\varphi^a,
\qquad
\mathfrak s'=\mathfrak s-a
$$

leaves every physical length unchanged. Choosing
$\ell_\star=\ell_{\mathrm{Pl}}$ is an external-anchor convention consistent
with `foundations/dimensionful-constants-status.md`.

The symbol $\mathfrak s$ avoids collision with the Cassi regularization length
$\sigma_{\mathrm{reg}}$.

### 2.2 Complex Yang/Yin doublet

Write

$$
\psi_Y
=\sqrt\rho\cos\frac\beta2\,
 e^{i(\Theta-\vartheta/2)},
\qquad
\psi_I
=\sqrt\rho\sin\frac\beta2\,
 e^{i(\Theta+\vartheta/2)}.
$$

Then

$$
E_Y=|\psi_Y|^2=\rho\cos^2\frac\beta2,
\qquad
E_I=|\psi_I|^2=\rho\sin^2\frac\beta2,
$$

and

$$
\frac{E_Y-E_I}{E_Y+E_I}=\cos\beta.
$$

At the energy-minimizing composition $E_Y/E_I=\varphi$,

$$
\boxed{\cos\beta_\varphi
=\frac{\varphi-1}{\varphi+1}=\varphi^{-3}},
\qquad
\boxed{\sin^2\beta_\varphi=4\varphi^{-3}}.
$$

These are exact golden-ratio identities.

### 2.3 Relative connection

For $A\in\{1,2,3,\mathfrak s\}$, assign opposite relative charges:

$$
D_A\psi_Y
=\left(\partial_A-\frac{i g_Q}{2}B_A\right)\psi_Y,
\qquad
D_A\psi_I
=\left(\partial_A+\frac{i g_Q}{2}B_A\right)\psi_I.
$$

Under the time-independent transformation

$$
\psi_Y\to e^{+i g_Q\alpha/2}\psi_Y,
\qquad
\psi_I\to e^{-i g_Q\alpha/2}\psi_I,
\qquad
B_A\to B_A+\partial_A\alpha,
$$

the relative phase transforms as
$\vartheta\to\vartheta-g_Q\alpha$. The invariant relative one-form is

$$
\boxed{c_A=\partial_A\vartheta+g_QB_A}.
$$

The mixed curvature is

$$
\boxed{G_{i\mathfrak s}
=\partial_iB_{\mathfrak s}-\partial_{\mathfrak s}B_i},
$$

alongside $G_{ij}=\partial_iB_j-\partial_jB_i$.

### 2.4 Minimal conservative action

Choose a flat measure $d\mathfrak s$ and normalize
$\rho=\Psi^\dagger\Psi$ as number density per $d\mathfrak s$. The candidate
action is

$$
S=\int dt\,d^3x\,d\mathfrak s
\left[
\frac{i\hbar}{2}
\left(\Psi^\dagger\partial_t\Psi
-(\partial_t\Psi)^\dagger\Psi\right)
-\mathcal H
\right],
$$

with

$$
\begin{aligned}
\mathcal H={}&
\frac{K_x}{2}|D_i\Psi|^2
+\frac{K_{\mathfrak s}}{2}|D_{\mathfrak s}\Psi|^2\\
&+\frac{\lambda_\rho}{4}(\rho-\rho_0)^2
+\frac{\lambda_\varphi}{2}(E_Y-\varphi E_I)^2\\
&+\frac{1}{4\mu_x}G_{ij}G_{ij}
+\frac{1}{2\mu_m}G_{i\mathfrak s}G_{i\mathfrak s}.
\end{aligned}
$$

All displayed stiffnesses are positive in the stable static sector. This is a
spatial-and-scale connection with a first-order matter time term. Promoting the
same term to a time-dependent local gauge symmetry gives the fundamental
condensate a nonzero Gauss source; a source-free homogeneous vacuum is therefore
obstructed. The separate branch in
`foundations/particle-stationary-action-closure.md` uses second-order covariant
time kinetics for the charged fields, positive temporal curvatures, and an
explicit Gauss constraint while retaining this document's static energy.

### 2.5 Units under the flat-density convention

Let $[\mathfrak s]=1$, $[x]=L$, $[t]=T$, $[g_Q]=1$, and
$[\Psi]=L^{-3/2}$. Then

| Quantity | Units |
|---|---|
| $\mathcal H$ | $\hbar T^{-1}L^{-3}$ |
| $B_i$ | $L^{-1}$ |
| $B_{\mathfrak s}$ | $1$ |
| $G_{ij}$ | $L^{-2}$ |
| $G_{i\mathfrak s}$ | $L^{-1}$ |
| $K_x$ | $\hbar L^2/T$ |
| $K_{\mathfrak s}$ | $\hbar/T$ |
| $\lambda_\rho,\lambda_\varphi$ | $\hbar L^3/T$ |
| $\rho_0$ | $L^{-3}$ |
| $\mu_x$ | $T/(\hbar L)$ |
| $\mu_m$ | $TL/\hbar$ |

A nonrelativistic carrier interpretation would identify

$$
K_x=\frac{\hbar^2}{m_c}.
$$

The carrier inertia $m_c$ is an external physical input; the action does not
derive it.

---

## 3. Exact interscale continuity

### 3.1 Species currents

Define

$$
a_A=\partial_A\Theta,
\qquad
\nu_{Y,A}=a_A-\frac{c_A}{2},
\qquad
\nu_{I,A}=a_A+\frac{c_A}{2}.
$$

The number currents are

$$
\mathbf j_Y=\frac{K_x}{\hbar}E_Y\boldsymbol\nu_Y,
\qquad
\mathbf j_I=\frac{K_x}{\hbar}E_I\boldsymbol\nu_I,
$$

and the distinct scale currents are

$$
J_{Y,\mathfrak s}
=\frac{K_{\mathfrak s}}{\hbar}E_Y\nu_{Y,\mathfrak s},
\qquad
J_{I,\mathfrak s}
=\frac{K_{\mathfrak s}}{\hbar}E_I\nu_{I,\mathfrak s}.
$$

Their units differ:

$$
[\mathbf j_a]=L^{-2}T^{-1},
\qquad
[J_{a,\mathfrak s}]=L^{-3}T^{-1}.
$$

The independent global phase symmetries give

$$
\boxed{
\partial_tE_a+\nabla\cdot\mathbf j_a
+\partial_{\mathfrak s}J_{a,\mathfrak s}=0,
\qquad a\in\{Y,I\}.}
$$

Summing them gives

$$
\boxed{
\partial_t\rho+\nabla\cdot\mathbf j
+\partial_{\mathfrak s}J_{\mathfrak s}=0,}
$$

where $\mathbf j=\mathbf j_Y+\mathbf j_I$ and
$J_{\mathfrak s}=J_{Y,\mathfrak s}+J_{I,\mathfrak s}$.

### 3.2 Observed scale window

For an observed window
$\mathfrak s_-\le\mathfrak s\le\mathfrak s_+$, define

$$
\rho_{\mathrm{obs}}(\mathbf x,t)
=\int_{\mathfrak s_-}^{\mathfrak s_+}
\rho(\mathbf x,\mathfrak s,t)\,d\mathfrak s.
$$

Integration gives

$$
\boxed{
\partial_t\rho_{\mathrm{obs}}
+\nabla\cdot\mathbf j_{\mathrm{obs}}
=J_{\mathfrak s}(\mathfrak s_-)
-J_{\mathfrak s}(\mathfrak s_+).}
$$

An apparent source in one scale band can therefore be conservative transport
in the full $(\mathbf x,\mathfrak s)$ state. Conservation in the integrated
three-dimensional system requires vanishing or balanced scale-boundary flux.

### 3.3 Discrete cascade form

A nearest-neighbor discretization uses a relative-phase link $U_n$:

$$
H_{\mathfrak s}
=\frac{K_{\mathfrak s}}{2}
\sum_n\|\Psi_{n+1}-U_n\Psi_n\|^2.
$$

The link current

$$
\boxed{
J_{n+1/2}
=\frac{K_{\mathfrak s}}{\hbar}
\operatorname{Im}
\left(\Psi_n^\dagger U_n^\dagger\Psi_{n+1}\right)}
$$

obeys

$$
\dot\rho_n+\nabla\cdot\mathbf j_n
=J_{n-1/2}-J_{n+1/2}.
$$

This supplies a concrete distinction between transfer on a connected scale
graph and a spatial density-plane diagnostic.

---

## 4. Co-flow, counterflow, and the $\varphi$ ratio

### 4.1 Phase energy and total current

For either spatial or scale direction, with $K_A=K_x$ or
$K_{\mathfrak s}$,

$$
\mathcal H_{\mathrm{phase},A}
=\frac{K_A}{2}
\left[
E_Y\left(a_A-\frac{c_A}{2}\right)^2
+E_I\left(a_A+\frac{c_A}{2}\right)^2
\right].
$$

Equivalently,

$$
\mathcal H_{\mathrm{phase},A}
=\frac{K_A\rho}{2}
\left(a_A^2-\cos\beta\,a_Ac_A+\frac{c_A^2}{4}\right).
$$

The total number current is

$$
\boxed{
j_A
=\frac{K_A\rho}{\hbar}
\left(a_A-\frac{\cos\beta}{2}c_A\right).}
$$

The relative gauge-charge current is

$$
\boxed{
\mathcal I_A
=\frac{g_Q}{2}(j_{Y,A}-j_{I,A})
=\frac{g_QK_A\rho}{2\hbar}
\left(\cos\beta\,a_A-\frac{c_A}{2}\right).}
$$

### 4.2 Zero total number flow

Local minimization over the common phase, when globally integrable, gives

$$
a_A=\frac{\cos\beta}{2}c_A,
$$

which is equivalent to $j_A=0$. The species currents then satisfy

$$
j_{Y,A}=-j_{I,A},
\qquad
\frac{\nu_{I,A}}{\nu_{Y,A}}=-\frac{E_Y}{E_I}.
$$

At $E_Y/E_I=\varphi$,

$$
\boxed{\frac{\nu_{I,A}}{\nu_{Y,A}}=-\varphi.}
$$

The number countercurrent

$$
j_A^{(-)}\equiv j_{I,A}-j_{Y,A}
$$

becomes

$$
\boxed{
j_A^{(-)}
=\frac{K_A\rho}{2\hbar}\sin^2\beta\,c_A,}
$$

and at the $\varphi$ composition,

$$
\boxed{
j_A^{(-)}
=\frac{2K_A\rho}{\hbar\varphi^3}c_A.}
$$

This is the exact counterflow factor supplied by the candidate action.

### 4.3 Other zero-current conditions

The phrase “zero flow” must name the conserved current:

- $j_A=0$ gives equal-and-opposite number currents and the
  $-\varphi$ phase-gradient ratio above.
- $\mathcal I_A=0$ gives equal co-directed species currents and
  $c_A=2\cos\beta\,a_A$.
- $c_A=0$ is a shared-phase branch with
  $j_Y/j_I=E_Y/E_I=\varphi$ at the selected composition.

A positive $+\varphi$ current ratio therefore belongs to a co-flow or separately
postulated phase convention. It is not the zero-number-flow countercurrent.

### 4.4 The composition potential supplies no conversion

The term

$$
V_\varphi
=\frac{\lambda_\varphi}{2}(E_Y-\varphi E_I)^2
$$

has its energy minimum at $E_Y/E_I=\varphi$, but it is independent of both
phases. The action consequently conserves the integrated Yang and Yin numbers
separately. Homogeneous evolution changes phase frequencies while preserving
the initial composition.

Relaxation toward the ratio requires an explicit reaction, species-mixing
sector, or open-system bath. With the opposite local charges used here, a
linear $\psi_Y^*\psi_I$ conversion needs an additional charged link or
Stueckelberg field to remain gauge invariant. The canonical rank-one
dissipative conversion law remains a separate sector.

### 4.5 Planck-to-proton closed scale circuit

Choose the external anchor $\ell_\star=\ell_{\mathrm{Pl}}$ and terminate the
scale interval at the proton's reduced Compton wavelength:

$$
\mathfrak s_p
:=\log_\varphi\!\left(\frac{\lambda_p}{\ell_{\mathrm{Pl}}}\right),
\qquad
\lambda_p:=\frac{\hbar}{m_pc},
\qquad
\boxed{\mathfrak s_p=91.4616}.
$$

The endpoint value is Mapped from the measured proton mass and remains
unselected by the interscale action.

A closed current can nevertheless be expressed without sending net number
density out of the scale window. Use the Yang component as the outward rail
from $\mathfrak s=0$ to $\mathfrak s=\mathfrak s_p$ and the Yin component as
the return rail. In the stationary interior, set

$$
\boxed{
J_{Y,\mathfrak s}=+\mathcal J_Q,
\qquad
J_{I,\mathfrak s}=-\mathcal J_Q.}
$$

Then

$$
J_{\mathfrak s}
=J_{Y,\mathfrak s}+J_{I,\mathfrak s}=0,
$$

while the relative Yang/Yin current is

$$
\boxed{
J_Q
:=\frac{J_{Y,\mathfrak s}-J_{I,\mathfrak s}}{2}
=\mathcal J_Q,
\qquad
\mathcal I_{\mathfrak s}=g_QJ_Q.}
$$

The term circulating Qi current designates this relative Yang/Yin phase current
on the doubled scale interval. The scalar coherence diagnostic $q$ remains a
local diagnostic without its own continuity equation.

The rails must turn into one another at both endpoints. Introduce a Yang source
$\Gamma$ and an equal Yin sink:

$$
\partial_tE_Y+\partial_{\mathfrak s}J_{Y,\mathfrak s}=\Gamma,
\qquad
\partial_tE_I+\partial_{\mathfrak s}J_{I,\mathfrak s}=-\Gamma.
$$

The stationary circuit requires

$$
\boxed{
\Gamma(\mathfrak s)
=\mathcal J_Q
\left[
\delta(\mathfrak s)
-\delta(\mathfrak s-\mathfrak s_p)
\right].}
$$

At the Planck endpoint, Yin turns into Yang. At the proton endpoint, Yang turns
into Yin. The total source vanishes after summing the species and after
integrating over the full interval.

One local realization is a pair of endpoint mixing terms

$$
\mathcal H_{\mathrm{turn}}
:=-2\sum_{b\in\{0,p\}}
\kappa_b\,\delta(\mathfrak s-\mathfrak s_b)
\sqrt{E_YE_I}\,
\cos(\vartheta-\alpha_b),
$$

with $\mathfrak s_0=0$ and $\mathfrak s_p$ as above. With the displayed sign
convention, each term supplies

$$
\Gamma_b
:=-\frac{2\kappa_b}{\hbar}
\sqrt{E_YE_I}\,
\sin(\vartheta-\alpha_b)\,
\delta(\mathfrak s-\mathfrak s_b).
$$

The boundary phases $\alpha_b$ must transform with the relative gauge symmetry,
or arise from dynamical charged endpoint fields. Treating them as fixed
numbers explicitly breaks that symmetry. The conservative bulk action omits
the endpoint sector, which must be supplied as additional physics.

The charged section $\Upsilon_v$ in
`foundations/endpoint-link-and-localization-boundary.md` supplies this
transformation dynamically. Its coherent critical current gives
$\kappa_v|\Upsilon_v|\geq
K_{\mathfrak s}|\Delta_m|/(2\varphi^{3/2}\mathfrak s_p)$ in the uniform
circuit state. A one-way Lindblad alternative gives
$\gamma_-/\gamma_+=\varphi$ while damping undriven endpoint coherence.
Under the separate Hypothesized Yang/Yin species-port identification, the same
frozen endpoint background gives the Hermitian rail-rail Hessian
$\Lambda_{\mathrm{link},v}=2\kappa_v|\Upsilon_v|M(\alpha_v)$. A dressed
quarter-turn phase and selected coupling ratio realize the declared golden
two-port matrix at one $k_\star$. Combining that match with current capacity
and positive fixed-amplitude phase stiffness gives the conditional bound
$k_\star>0.0964640362$ for the unbiased proton branch. First-order
source-action elimination of endpoint fluctuations from EL9 gives the Nambu
Schur response with covariance under constant relative-frame rotations in
`foundations/endpoint-link-and-localization-boundary.md` §3.9. The second-order
fixed-$Q_C$ particle action is a separate temporal sector. The separately
frozen AR1–AR6 receipt passes; the DR receipt remains `FAIL` because its DR5
endpoint block has the opposite source-action sign. The endpoint-response
normalization is
$\mathcal I_{\mathrm{link},v}=-2\Gamma_v$, where $\Gamma_v$ is the Yang
source coefficient and $g_Q\Gamma_v$ is its gauge-weighted source. A closed
homogeneous conservative time-harmonic endpoint extremum has zero coherent
conversion current. For stationary spatial structure,
$\nabla\cdot\mathbf J_{\Upsilon,v}=\Gamma_v$ and
$\int_\Omega\Gamma_vd^3x=\oint_{\partial\Omega}
\mathbf J_{\Upsilon,v}\cdot d\mathbf S$. Spatial endpoint flux therefore
supports local source-and-sink conversion in a closed domain, while a uniform
nonzero circuit source requires boundary flux or inter-vertex endpoint
transport. The separately declared Wilson coupling
$-t_\Upsilon(\Upsilon_+^*\mathcal W_{+\leftarrow-}\Upsilon_-+\mathrm{c.c.})$
supplies one conservative channel with
$I_{-\to+}=\mathcal J_Q$ on the stationary circuit and capacity
$I_c=2t_\Upsilon u_-u_+/\hbar$. Its scale-edge charge current completes the
relative-charge ledger. An open or driven channel, a non-harmonic state, or a
larger coupled background supplies other possible branches. The endpoint
potential, physical background, microscopic origin and value of $t_\Upsilon$,
local scale-bulk completion, damping mechanism, trace normalization, and full
coupled spectrum remain unselected.

For a compact closed circuit, define the gauge-invariant accumulated phase

$$
\boxed{
\Delta_m
:=\int_0^{\mathfrak s_p}
\left(\nu_{Y,\mathfrak s}-\nu_{I,\mathfrak s}\right)
d\mathfrak s
=2\pi m-\delta_{\mathrm{end}},
\qquad m\in\mathbb Z,}
$$

where $\delta_{\mathrm{end}}$ contains the two turning phases. The connection
holonomy is already included in the invariant velocities
$\nu_{Y,\mathfrak s}$ and $\nu_{I,\mathfrak s}$.

For uniform density, uniform composition, and zero total number current, the
$\varphi$ composition gives

$$
E_Y=\frac{\rho}{\varphi},
\qquad
E_I=\frac{\rho}{\varphi^2},
$$

and the exact stationary solution is

$$
\boxed{
\nu_{Y,\mathfrak s}
=\frac{\Delta_m}{\varphi^2\mathfrak s_p},
\qquad
\nu_{I,\mathfrak s}
=-\frac{\Delta_m}{\varphi\mathfrak s_p},}
$$

so that $\nu_I/\nu_Y=-\varphi$. The circulating current and integrated phase
energy per spatial volume are

$$
\boxed{
\mathcal J_{Q,m}
=\frac{K_{\mathfrak s}\rho}
{\hbar\varphi^3\mathfrak s_p}\,\Delta_m,}
$$

$$
\boxed{
\mathscr E_{\mathrm{circ},m}
:=\int_0^{\mathfrak s_p}
\mathcal H_{\mathrm{phase},\mathfrak s}\,d\mathfrak s
=\frac{K_{\mathfrak s}\rho}
{2\varphi^3\mathfrak s_p}\,\Delta_m^2.}
$$

For the lowest unbiased sector, $m=1$ and $\delta_{\mathrm{end}}=0$,

$$
\frac{\hbar\mathcal J_{Q,1}}{K_{\mathfrak s}\rho}
=\frac{2\pi}{\varphi^3\mathfrak s_p}
=0.0162173,
$$

$$
\frac{\mathscr E_{\mathrm{circ},1}}
{K_{\mathfrak s}\rho}
=\frac{2\pi^2}{\varphi^3\mathfrak s_p}
=0.0509481.
$$

At fixed winding, the circulation energy falls as $1/\mathfrak s_p$, so a
finite proton endpoint requires another term. A minimal scale-tension closure
has the form

$$
\mathscr E_{\mathrm{sel}}(\mathfrak s_p)
:=\mathcal T_{\mathfrak s}\mathfrak s_p
+\frac{K_{\mathfrak s}\rho\Delta_m^2}
{2\varphi^3\mathfrak s_p}
+\mathscr E_{\mathrm{end}},
$$

which, for endpoint energy independent of $\mathfrak s_p$, has

$$
\boxed{
\mathfrak s_\star
=|\Delta_m|
\sqrt{\frac{K_{\mathfrak s}\rho}
{2\varphi^3\mathcal T_{\mathfrak s}}}.}
$$

Selecting the observed proton endpoint in the unbiased $m=1$ sector would
require

$$
\boxed{
\frac{\mathcal T_{\mathfrak s}}{K_{\mathfrak s}\rho}
=\frac{2\pi^2}{\varphi^3\mathfrak s_p^2}
=5.57043\times10^{-4}.}
$$

This value is a required closure ratio with no current $\varphi$ derivation.

The current does provide a concrete pinch route. Although the number currents
cancel, their relative charges add:

$$
f_r^{(\mathrm{mixed})}
=\hbar g_Q\mathcal J_QG_{r\mathfrak s}.
$$

A same-sign mixed-curvature response can therefore pinch the spatial profile
without draining total density along the scale coordinate. A proton candidate
would be a self-consistent solution in which the endpoint turners, relative
current, mixed curvature, spatial core, and scale tension all close together.

Changing the circulation sector requires a phase slip, an endpoint conversion
event, or a zero of one condensate. This supplies a possible stability
mechanism. A decay rate additionally requires the endpoint dynamics,
fluctuation action, and physical proton quantum numbers. The proton mass,
lifetime, electric charge, color, and spin remain open.

The arithmetic identities and normalized coefficients are checked by
`computations/planck_proton_scale_current_check.py`.

---

## 5. Mixed curvature and the conditional pinch

### 5.1 Static field equations

With the source convention above, static variation gives, up to the global
orientation convention for $B_A$,

$$
\frac{1}{\mu_x}\partial_jG_{ji}
-\frac{1}{\mu_m}\partial_{\mathfrak s}G_{i\mathfrak s}
+\hbar\mathcal I_i=0,
$$

and

$$
\frac{1}{\mu_m}\partial_iG_{i\mathfrak s}
+\hbar\mathcal I_{\mathfrak s}=0.
$$

The static spatial force density contains

$$
\boxed{
f_i
=\hbar\mathcal I_jG_{ij}
+\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s}.}
$$

Thus

$$
\boxed{
f_i^{(\mathrm{mixed})}
=\hbar\mathcal I_{\mathfrak s}G_{i\mathfrak s}}
$$

is one term in the force, rather than a complete force law. The factor $\hbar$
and the gauge-charge normalization are required by the declared units.

The gauge-source current $\mathcal I_{\mathfrak s}$ and the Noether
spatial-momentum flux $T_{i\mathfrak s}$ are separate objects. The exact
scale-window momentum ledger and a reciprocal stress realization are derived
in `foundations/interscale-stress-attenuation-boundary.md`. Identifying the
mixed-curvature term with an attenuated physical stress requires the
time-completed action, a constitutive map between these currents, and a
specified return channel. The routed $\varphi^{-N}$ branch in that document
applies to a quadratic forward flux under non-re-entry boundary conditions.

### 5.2 Conditional inward sign

Consider a static sector with $B_i=0$, weak variation in $\mathfrak s$, and a
localized same-sign scale-current source. Then

$$
G_{r\mathfrak s}=\partial_rB_{\mathfrak s}.
$$

For a positive elliptic response, a centrally concentrated positive source
produces a positive $B_{\mathfrak s}$ that decreases outward. Hence
$\partial_rB_{\mathfrak s}<0$, and a same-sign local
$\mathcal I_{\mathfrak s}$ gives

$$
f_r^{(\mathrm{mixed})}<0.
$$

The force points inward under these sign and boundary assumptions. Opposite
source signs, nonlocal scale structure, other curvature components, or a
nonpositive response can change the result. The model therefore supplies a
pinch channel, not a universal attraction theorem.

### 5.3 London screening

After local minimization of the common phase,

$$
\mathcal H_{\mathrm{phase},A}^{\min}
=\frac{K_A}{2}\frac{E_YE_I}{\rho}c_A^2
=\frac{K_A\rho\sin^2\beta}{8}c_A^2.
$$

The corresponding London coefficients are

$$
M_i^2
=g_Q^2K_x\frac{E_YE_I}{\rho}
=\frac{g_Q^2K_x\rho\sin^2\beta}{4},
$$

$$
M_{\mathfrak s}^2
=g_Q^2K_{\mathfrak s}\frac{E_YE_I}{\rho}
=\frac{g_Q^2K_{\mathfrak s}\rho\sin^2\beta}{4}.
$$

For a transverse spatial mode with scale wave number $p$, the positive static
operator is

$$
\frac{k^2}{\mu_x}
+\frac{p^2}{\mu_m}
+M_i^2.
$$

The physical inverse penetration length is

$$
\kappa_x^2
=\mu_x\left(M_i^2+\frac{p^2}{\mu_m}\right).
$$

For a scale component varying in physical space,

$$
\kappa_{\mathfrak s}^2=\mu_mM_{\mathfrak s}^2.
$$

These local London expressions require positive coefficients, nonzero Yang and
Yin condensates, and an integrable common-phase minimizer. Winding or boundary
constraints can prevent the local minimizer from being realized globally.

---

## 6. Core widths and coefficient identifiability

### 6.1 Linearized healing widths

Around $\rho=\rho_0$ and $\beta=\beta_\varphi$, with zero background phase
gradients, the spatial widths are

$$
\boxed{\xi_{\rho,x}^2
=\frac{K_x}{2\lambda_\rho\rho_0}},
\qquad
\boxed{\xi_{\beta,x}^2
=\frac{K_x}{4\varphi\lambda_\varphi\rho_0}}.
$$

Along the dimensionless scale coordinate,

$$
\xi_{\rho,\mathfrak s}^2
=\frac{K_{\mathfrak s}}{2\lambda_\rho\rho_0},
\qquad
\xi_{\beta,\mathfrak s}^2
=\frac{K_{\mathfrak s}}{4\varphi\lambda_\varphi\rho_0}.
$$

The latter are widths in $\mathfrak s$ units. A physical length requires an
independently declared scale metric.

The condensation-energy density between $\rho=0$ and $\rho=\rho_0$ is

$$
\epsilon_{\mathrm{cond}}
=\frac{\lambda_\rho\rho_0^2}{4}
=\frac{K_x\rho_0}{8\xi_{\rho,x}^2}.
$$

If one additionally imposes equal radial and composition widths,
$\xi_{\rho,x}=\xi_{\beta,x}$, then

$$
\boxed{\frac{\lambda_\varphi}{\lambda_\rho}
=\frac{1}{2\varphi}.}
$$

This ratio follows from the equal-width closure. The action itself does not
select that closure.

### 6.2 Gauge normalization redundancy

The rescaling

$$
B_A' = aB_A,
\qquad
g_Q'=\frac{g_Q}{a},
\qquad
\mu_x'=a^2\mu_x,
\qquad
\mu_m'=a^2\mu_m
$$

leaves the matter derivatives and gauge energy invariant. Consequently,
$g_Q$, $\mu_x$, and $\mu_m$ are not separately identifiable inside this
isolated sector. The invariant combinations are

$$
\boxed{e_x^2=g_Q^2\mu_x},
\qquad
\boxed{e_m^2=g_Q^2\mu_m},
$$

and their products with $K_A\rho$ in penetration lengths. A physical flux
normalization or coupling to an independently calibrated field is needed to
separate them.

---

## 7. Finite radius: pinch versus support

### 7.1 Conditional Derrick profile

For a fixed three-dimensional profile under $\mathbf x\to R\mathbf y$,
ordinary gradient energy scales as $R$, a fixed-flux or four-derivative core
term scales as $1/R$, and bulk potential energy scales as $R^3$. A reduced
energy can therefore be written

$$
\boxed{E(R)=\mathcal A R
+\frac{\mathcal B-\mathcal D}{R}
+\mathcal C R^3.}
$$

Here $\mathcal D/R$ is an effective attractive contribution supplied by an
additional source elimination or interaction model. The positive action in
§2.4 does not independently derive $\mathcal D$.

Let $\mathcal Q=\mathcal B-\mathcal D$. For $\mathcal C\ne0$, stationarity
gives

$$
\boxed{
R_\star^2
=\frac{-\mathcal A
+\sqrt{\mathcal A^2+12\mathcal C\mathcal Q}}
{6\mathcal C}.}
$$

For

$$
\mathcal A>0,
\qquad
\mathcal C>0,
\qquad
\mathcal Q>0,
$$

this is a strict minimum. If $\mathcal C=0$,

$$
\boxed{R_\star=\sqrt{\frac{\mathcal Q}{\mathcal A}}}
$$

requires $\mathcal A,\mathcal Q>0$. When $\mathcal Q\le0$, the reduced profile
has no small-$R$ barrier; when $\mathcal C<0$, it has a large-$R$ instability.

The stability condition

$$
\boxed{\mathcal B>\mathcal D}
$$

states the central result: pinch can compress a localized state, while a
stronger flux/core sector must prevent collapse.

The explicit endpoint completions do not supply $\mathcal B$. With
$\mathcal B=0$ and $\mathcal D\geq0$, the derivative is
$E'(R)=\mathcal A+\mathcal D/R^2+3\mathcal C R^2>0$ for positive
$\mathcal A$ and nonnegative $\mathcal C$. The smooth zero-Chern endpoint
sector therefore has no finite Derrick radius.

For an imposed point-core Chern sector, the source gauge term gives

$$
\boxed{
\mathcal B_G
=2\pi N_G^2
\int_{I_{\mathfrak s}}\frac{d\mathfrak s}{e_x^2},
\qquad e_x^2=g_Q^2\mu_x.}
$$

The point branch satisfies the reduced support condition only when
$\mathcal B_G>\mathcal D$. The same action cannot resolve the Abelian magnetic
core, and its charged nonzero condensate makes an isolated point-flux state
infinite in energy. The exterior coefficient and completion boundary are
derived in `foundations/point-core-flux-sector.md`.

### 7.2 Conditional loop minimum

A thin loop with tension $\mathcal T_\star$, compact winding $W$, and phase
stiffness $K_\parallel$ has the reduced energy

$$
E_{\mathrm{loop}}(L)
=\mathcal T_\star L
+\frac{2\pi^2K_\parallel W^2}{L}.
$$

For positive coefficients and a retained nonzero winding,

$$
\boxed{L_\star
=\sqrt{\frac{2\pi^2K_\parallel W^2}{\mathcal T_\star}}.}
$$

The loop geometry, compact winding, tension, and $K_\parallel$ are supplied
inputs in this conditional reduction.

---

## 8. Topology and literal pinch-off

### 8.1 Pure projective curvature

For the normalized doublet

$$
z=
\begin{pmatrix}
\cos(\beta/2)e^{-i\vartheta/2}\\
\sin(\beta/2)e^{+i\vartheta/2}
\end{pmatrix},
$$

the pure $CP^1$ pullback is

$$
\boxed{f_0
=\frac12\sin\beta\,d\beta\wedge d\vartheta}
$$

up to orientation. It is decomposable, so

$$
\boxed{f_0\wedge f_0=0.}
$$

The horizontal gauged form obtained by replacing $d\vartheta$ with
$c=d\vartheta+g_QB$ is also decomposable. A generic Berry curvature containing
an independent term proportional to $G=dB$ need not satisfy this identity.
The result therefore belongs specifically to the pure projective form.

### 8.2 How topology can change

A smooth normalized map with $\rho>0$ and fixed boundary data remains in one
homotopy sector as $\mathfrak s$ changes. Literal detachment requires at least
one of the following:

1. **Amplitude-zero neck:** $\rho=0$ permits a phase slip or reconnection.
2. **Boundary transfer:** topological charge crosses the spatial or scale
   boundary.
3. **Nonsmooth event:** a defect or singular patch enters the description.
4. **Independent connection event:** a gauge bundle with curvature $G$ carries
   the change; locally $d(B\wedge G)=G\wedge G$.

A picture of a smooth tube narrowing into a detached object therefore omits a
necessary event unless one of these mechanisms is specified.

### 8.3 Conditional flux quantization

On a closed curve where both condensates remain nonzero, single-valued phases
give integer windings $n_Y,n_I$. Finite-energy Meissner conditions give

$$
\oint\nu_Y\cdot d\boldsymbol\ell
=2\pi n_Y-\frac{g_Q}{2}\Phi_B=0,
$$

$$
\oint\nu_I\cdot d\boldsymbol\ell
=2\pi n_I+\frac{g_Q}{2}\Phi_B=0.
$$

Hence

$$
\boxed{
\Phi_B=\frac{4\pi n_Y}{g_Q}
=-\frac{4\pi n_I}{g_Q},
\qquad n_I=-n_Y.}
$$

For the composite relative phase
$m=n_I-n_Y=-2n_Y$,

$$
\Phi_B=-\frac{2\pi m}{g_Q}.
$$

The even-$m$ restriction here follows from requiring both half-charged
condensates to be nonzero and individually current-free. A model with a
fundamental charge-$g_Q$ composite order parameter has a different primitive
normalization. Compact gauge structure, nonzero boundary condensate, and
finite-energy asymptotics are all required. A Wilson loop on a torus without
these conditions can have continuous holonomy.

For the full coherence fibre, state-only projective winding can contract
through the Bloch-ball interior. The independent compact connection admits the
first Chern candidate
$N_G=(g_Q/4\pi)\int_\Sigma G$, but
$H^2(\mathbb R^3\times S^1_{\mathfrak s};\mathbb Z)=0$ on the smooth
unexcised object base. A nonzero integer sector requires an excised point or
line, boundary flux, or different spatial topology
(`foundations/endpoint-link-and-localization-boundary.md` §5).

---

## 9. Scale measure and embedding choices

### 9.1 Flat density per $d\mathfrak s$

The action in §2.4 declares

$$
N=\int d^3x\,d\mathfrak s\,|\Psi|^2.
$$

Under a nonlinear coordinate change
$\mathfrak s'=f(\mathfrak s)$ with
$J=d\mathfrak s'/d\mathfrak s>0$, number invariance requires

$$
\Psi'=\frac{\Psi}{\sqrt J},
\qquad
\rho'=\frac{\rho}{J},
\qquad
B_{\mathfrak s}'=\frac{B_{\mathfrak s}}{J}.
$$

A compensating half-density connection is then required in
$D_{\mathfrak s'}\Psi'$. With that connection, coefficient bookkeeping gives

$$
K_x'=K_x,
\qquad
K_{\mathfrak s}'=J^2K_{\mathfrak s},
\qquad
\lambda_{\rho,\varphi}'=J\lambda_{\rho,\varphi},
$$

$$
\mu_x'=J\mu_x,
\qquad
\mu_m'=\frac{\mu_m}{J},
\qquad
\rho_0'=\frac{\rho_0}{J}.
$$

Without the half-density connection, derivatives of $J$ generate additional
terms. A nonlinear coordinate change therefore cannot be represented by a
simple physical profile for $K_{\mathfrak s}$ alone.

### 9.2 Scalar field with invariant measure

A different convention starts from a physical coordinate $y$ and invariant
measure

$$
N=\int d^3x\,dy\,|\Psi_y|^2
=\int d^3x\,d\mathfrak s\,h(\mathfrak s)|\Psi_y|^2,
\qquad
h=\frac{dy}{d\mathfrak s}.
$$

If $\Psi_y$ is retained as a scalar and isotropic coefficients $K_4,\mu_4$ are
used in $(\mathbf x,y)$, collecting the $d\mathfrak s$ integrand gives

$$
K_x=hK_4,
\qquad
K_{\mathfrak s}=\frac{K_4}{h},
\qquad
\mu_x=\frac{\mu_4}{h},
\qquad
\mu_m=h\mu_4.
$$

Under this convention,

$$
\mu_xK_x=\mu_mK_{\mathfrak s}=\mu_4K_4
$$

pointwise. The conserved coordinate density is $h|\Psi_y|^2$, rather than
$|\Psi_y|^2$ per $d\mathfrak s$.

For the declared local embedding

$$
y=\ell(\mathfrak s)=\ell_\star\varphi^{\mathfrak s},
\qquad
h=(\ln\varphi)\ell,
$$

constant $K_4$ and $\mu_4$ would give

$$
K_x\propto\varphi^{\mathfrak s},
\qquad
K_{\mathfrak s}\propto\varphi^{-\mathfrak s},
\qquad
\mu_x\propto\varphi^{-\mathfrak s},
\qquad
\mu_m\propto\varphi^{\mathfrak s}.
$$

These relations are bookkeeping inside the scalar/invariant-measure branch.
Rescaling to a density per flat $d\mathfrak s$ generates the half-density terms
of §9.1. Holding $K_x$ constant instead is another constitutive choice and
would require a varying $K_4$.

The current Cassi theory selects neither normalization branch nor a physical
scale metric. No coefficient power law follows from the notation
$\ell=\ell_\star\varphi^{\mathfrak s}$ alone.

---

## 10. Selection scope of $\varphi$

### 10.1 Exact composition geometry

Within this proposal, $\varphi$ fixes

$$
\cos\beta_\varphi=\varphi^{-3},
\qquad
\sin^2\beta_\varphi=4\varphi^{-3},
$$

and therefore the counterflow prefactor

$$
\frac{K_A\rho}{2\hbar}\sin^2\beta_\varphi
=\frac{2K_A\rho}{\hbar\varphi^3}.
$$

It does not fix $g_Q$, $K_A$, $\mu_A$, $\lambda_A$, $\rho_0$, or
$\ell_\star$.

### 10.2 Conditional Fibonacci windings

If both phases are compact, both condensates remain nonzero, mobility is shared,
connection holonomy is restricted, and a zero-number-flow winding condition is
imposed, the irrational phase-gradient ratio $-\varphi$ can be approached by
integer pairs

$$
(n_Y,n_I)=(F_n,-F_{n+1}).
$$

This is the Fibonacci convergent theorem described in
`principles/de-resonance-principle.md`. A continuous connection holonomy can
absorb the mismatch, leaving these pairs unselected by the candidate action.

An illustrative sector cost

$$
E_n\approx A F_{2n+1}+B\varphi^{-2n}
$$

would select approximately

$$
\boxed{
n_\star\approx\frac14
\log_\varphi\!\left(\frac{B\sqrt5}{A\varphi}\right)}.
$$

This example shows that $\varphi$ identifies the convergent sequence while the
stiffness ratio $B/A$ selects a member. The displayed action supplies neither
term, so this is separate model bookkeeping rather than a prediction.

### 10.3 Conditional mass scaling

If one independently supplies the Planck anchor, an identical dimensionless
profile at every scale, and mode energy $E\propto\hbar c/\ell$, then

$$
M_{\mathcal Q,n}
=M_{\mathrm{Pl}}\,\mathcal E_{\mathcal Q}\,\varphi^{-n}.
$$

This is the conditional cascade relation used in
`foundations/qi-loop-mass-cascade.md`. The interscale action contains no $c$,
Planck anchor, selected $n$, or mode-to-particle identification. Its reduced
Derrick energy generally contains mixed $\varphi^n$, $\varphi^{-n}$, and
$\varphi^{3n}$ scalings when coefficients are held fixed.

A particle interpretation also requires spin/statistics, electric charge,
color, chirality, and a sector-selection rule. Topology and a stable radius do
not supply those quantum numbers.

---

## 11. Evidence boundary and present verdict

### 11.1 What existing runs establish

The connected-hierarchy experiment in
`field-experience/toroidal-connected-hierarchy-report.md` establishes
conservative redistribution on an assigned scale graph, contraction, and finer
spatial structure under its declared dynamics. It does not evolve the complex
state $\Psi(\mathbf x,\mathfrak s,t)$ or measure
$J_{\mathfrak s}$, $B_A$, $G_{i\mathfrak s}$, a mixed-curvature force, flux, or
pinch-off topology.

The toroidal coherence-survival experiment in
`field-experience/toroidal-coherence-survival-report.md` did not establish a
stable toroidal realization. It supplies no evidence for the conditional loop
minimum in §7.2.

### 11.2 Result classification

| Result | Present status |
|---|---|
| Scale-coordinate definition and $\varphi$ composition identities | Exact algebra under declared coordinates |
| Species and total continuity; observed-window boundary flux | Derived from the candidate action |
| Co-flow/counterflow decomposition | Derived from the candidate action |
| Separate Yang/Yin conservation and absence of ratio relaxation | Derived from the candidate action |
| Planck-to-proton two-rail current and normalized energy | Derived conditional on the Mapped endpoint, uniform $\varphi$ composition, compact circuit phase, and endpoint bias |
| Cross-glued two-rail metric graph and circuit holonomy | Derived graph geometry under the Hypothesized gauge-covariant flux-unitary endpoint quotient; the physical endpoint fields and scale metric remain open (`foundations/geometric-manifold-completion.md`) |
| Endpoint conversion, inter-vertex transport, scale tension, and proton selection | Coherent charged, Wilson-dressed transport, and one-way open endpoint realizations are Derived conditionally on their declared actions; their couplings, potentials, absolute rates, scale tension, local scale-bulk completion, and proton selection remain Hypothesized or open |
| Healing widths and local London coefficients | Derived conditional linearization |
| Inward mixed-curvature force | Conditional on source sign, response, and restricted field sector |
| Finite Derrick radius and loop length | No finite radius in the minimal smooth zero-Chern endpoint sector; point-core flux gives $\mathcal B_G=2\pi N_G^2\int d\mathfrak s/e_x^2$ and requires $\mathcal B_G>\mathcal D$; an auxiliary adjoint $SU(2)_Q$ core matches that exterior, while the registered condensate confines flux and gives no persistent pair by itself; a neutral fixed-$Q_C$ carrier gives one conditional reduced separation under its support, retention, and matching inequalities; full loop existence remains unestablished |
| Temporal gauge and Gauss sector | Direct local gauging of the first-order interscale term is source-free Gauss-obstructed for the nonzero fundamental condensate; a separate conditional second-order particle branch supplies time-dependent local $SU(2)_Q$, positive temporal curvatures, and a Gauss-compatible static sector |
| Pure $CP^1$ obstruction and flux quantization | Projective charge contracts in the full coherence ball; an independent first Chern number requires a closed two-cycle absent from the smooth unexcised base; point excision retains a singular or externally completed core |
| Scale-metric coefficient profiles | Convention-dependent; no selected branch |
| Fibonacci winding sector and mass law | Separate conditional extensions |
| Particle identification | Open |

The physical-space stationary endpoint-flux result belongs to
`foundations/endpoint-link-and-localization-boundary.md` §3.10. Its SF1–SF6
receipt is recorded in `computations/endpoint_spatial_flux_report.md`. This
paper uses it only as the declared endpoint-sector boundary; the scale-coordinate
circuit derivation above does not reproduce that physical-space calculation.

No numbered prediction is added to
`predictions/falsifiable-predictions.md`. A nonzero prediction requires a
selected normalization, coefficient set, boundary state, coupling to an
observable, and a solution that actually realizes the localized sector.

### 11.3 Present conclusion

The smallest consistent interscale extension is a complex Yang/Yin field with
a separately named scale current. It yields a conservative scale-window source
law and an exact relative counterflow structure. Mixed curvature can provide an
inward contribution under specified static conditions. The registered fields
alone leave the finite composite unsupported, and literal pinch-off requires a
topology-changing event. The auxiliary neutral carrier supplies one
conditional reduced support branch.

On the finite Planck-to-proton interval, equal-and-opposite Yang/Yin currents
form a closed relative-current circuit with no net scale-number leakage. A
charge-$-g_Q$ endpoint section realizes coherent turning with a finite current
capacity. A one-way open endpoint channel closes the populations with the
conditional rate ratio $\gamma_-/\gamma_+=\varphi$ and damps transverse
coherence.

The completion ansatz in
`foundations/geometric-manifold-completion.md` realizes the circuit as a
two-edge metric graph with $b_1=1$ and keeps conservative transport separate
from mesoscopic conversion. The normalized full fibre is contractible, and the
smooth object base carries no first Chern sector. The endpoint completions add
no positive $1/R$ core support, so the minimal sector has no finite Derrick
radius. Point excision and fixed Chern flux give the conditional coefficient
$\mathcal B_G=2\pi N_G^2\int d\mathfrak s/e_x^2$ and require
$\mathcal B_G>\mathcal D$. The auxiliary adjoint $SU(2)_Q$ branch supplies a
regular local core in its decoupled sector and matches the exterior
coefficient. Coupling the registered nonzero condensate removes the isolated
magnetic sector and confines flux. A finite monopole-antimonopole tube is
conditional, and its positive tension plus attractive screened tail gives no
finite-separation minimum in the registered branch.

The core-trapped carrier gives a unique reduced separation when $A_C>C_Q$ and
its independent retention and scale-separation inequalities hold. A bound
transverse carrier mode, the full backreacted stationary composite, scale
tension, endpoint physical normalization, particle quantum numbers, and
winding-changing rate remain unselected.


The mechanism is mathematically coherent at the stated level and physically
Hypothesized. Its free coefficients and normalization choices carry the missing
physics. The golden ratio organizes the composition and possible compact
winding approximants; it does not replace those inputs.

---

## References

- `foundations/qi-flow-double-helix.md`—canonical real-density state and spatial diagnostic currents
- `foundations/unified-lagrangian.md`—current Cassi action and open-system conversion boundary
- `foundations/point-core-flux-sector.md`—quantized point-core exterior energy
  and current-action completion boundary
- `foundations/nonabelian-magnetic-core-boundary.md`—auxiliary smooth core,
  condensate confinement, and persistent-composite boundary
- `computations/magnetic_core_completion_check.py`—BPS profile, matching,
  London, and pair-slope checker
- `foundations/core-trapped-charge-support.md`—conditional conserved-charge
  support, carrier retention, and reduced finite-separation theorem
- `computations/core_trapped_charge_check.py`—support-root, curvature,
  localization, and source-unit checker
- `foundations/particle-stationary-action-closure.md`—conditional source-free
  temporal action, Gauss constraint, fixed-charge stationary equations, and
  variational boundary
- `computations/particle_action_closure_check.py`—fundamental and adjoint covariance, temporal matter-source and static gauge-current signs, fixed-charge algebraic variation, source units, and dimensionless-group invariance checker
- `computations/particle-stationary-bvp-report.md`—registered one-point campaign receipt and numerical-quality verdict
- `foundations/microcascade-mirror.md`—formal negative-step scale coordinate and energy boundary
- `foundations/dimensionful-cascade.md`—external-anchor cascade parameterization
- `foundations/dimensionful-constants-status.md`—status of $c$, $\hbar$, $G$, and SI anchors
- `foundations/qi-loop-mass-cascade.md`—conditional loop tension and inverse-scale mass bookkeeping
- `foundations/proton-coherence-budget.md` §10—proton-facing statement of the distinct scale-circuit candidate
- `computations/planck_proton_scale_current_check.py`—Planck-to-proton current, energy, and scale-tension identities
- `foundations/geometric-manifold-completion.md`—two-rail metric-graph closure, positive coherence fibre, and separate open-system conversion block
- `foundations/endpoint-link-and-localization-boundary.md`—charged coherent
  endpoint, Wilson-link transport, one-way open alternative, full-fibre
  invariant classification, and minimal-sector localization boundary
- `computations/endpoint_spatial_flux_prereg.md`—frozen stationary
  spatial-flux, zero-mode, covariance, and gradient-cost criteria
- `computations/endpoint_spatial_flux_check.py`—passing SF1–SF6 analytic and
  Fourier receipt
- `computations/endpoint_spatial_flux_report.md`—first-execution output,
  closed-domain obstruction, and conditional spatial-flux boundary
- `computations/endpoint_intervertex_transport_prereg.md`—frozen IT1–IT6
  covariance, endpoint-ledger, capacity, and control criteria
- `computations/endpoint_intervertex_transport_check.py`—passing IT1–IT6
  deterministic receipt
- `computations/endpoint_intervertex_transport_report.md`—IT1–IT6
  Wilson-covariance, vertex-ledger, capacity, and phase-curvature receipt
- `foundations/spin-fibonacci-spiral.md`—optional compact phase, half-angle, and winding structure
- `principles/de-resonance-principle.md`—Fibonacci convergents under compact-current assumptions
- `particles/cassi-yang-yin-particles.md`—complex two-component field precedent
- `field-experience/toroidal-connected-hierarchy-report.md`—measured connected-hierarchy redistribution
- `field-experience/toroidal-coherence-survival-report.md`—toroidal stability result
- `foundations/interscale-stress-attenuation-boundary.md`—Noether momentum-window ledger, reciprocal scale stress, and routed-flux attenuation boundary
- `computations/interscale_stress_attenuation_check.py`—stress and transfer-algebra checker
