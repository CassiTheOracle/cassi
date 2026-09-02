# Yin–Yang–Qi Open Dynamical Geometry

## Status: Hypothesized integrated open-system geometry / Derived exact diagonal reduction, positivity-preserving conversion flow, covariance, ledger closure, and conditional coherence-support boundary—September 2026

## Abstract

Cassi has one canonical local state and several conditional geometric extensions. The canonical variables are the nonnegative Yang and Yin densities $E_Y,E_I$ and the bounded scalar Qi diagnostic $q(E_Y,E_I)$. The geometric completion places those densities on the diagonal of a positive Hermitian fibre, adds an optional off-diagonal coherence $c$, transports relative phase with a conditional $U(1)_Q$ connection, and closes the scale graph through endpoint sectors. These elements form an explicit **open-system effective closure**. They do not yet arise from one microscopic action.

This paper assembles the existing sectors without merging their epistemic status. The state-dependent two-jump conversion law is a nonlinear pointwise Lindblad-form vector field. Its trajectories preserve the positive cone by a monotone time reparametrization of a fixed linear GKSL flow, while its diagonal entries reproduce the canonical $q$-gated PDE exactly. A new conditional boundary follows: for finite density and $\lambda>0$, the minimal undriven conversion lift has a strictly positive transverse-coherence decay rate, so a stationary phase-bearing state requires a coherent source, protected sector, boundary or transport influx, modified reservoir, or different lift. The endpoint and Wilson sectors close number and relative-charge ledgers conditionally. Physical force still requires a complete Noether stress, and dynamical geometry still requires backreaction equations sourced by the full field-plus-reservoir stress. The separate local-$SU(2)_Q$ fixed-charge particle action remains a downstream branch pending an explicit interface with the Abelian first-order graph sector.

## 1. Scope and Source Boundary

The purpose of this synthesis is to state the smallest dynamical system supported by the present Cassi record and to identify the equation that must supply persistent coherence.

### 1.1 Canonical sector

The canonical state consists of

$$
E_Y\ge0,
\qquad
E_I\ge0,
$$

with

$$
\rho:=E_Y+E_I,
\qquad
\varepsilon:=E_Y-\varphi E_I,
$$

and

$$
\boxed{
q(E_Y,E_I)
:=
\frac{\rho^2}
{\rho^2+\varphi^{-2}+\varepsilon^2}.}
\tag{DG1}
$$

The canonical zero-noise conversion block is

$$
\boxed{
\begin{aligned}
\dot E_Y\big|_{\rm conv}
&=-\lambda(1-q)(E_Y-\varphi E_I),\\
\dot E_I\big|_{\rm conv}
&=+\lambda(1-q)(E_Y-\varphi E_I).
\end{aligned}}
\tag{DG2}
$$

These equations and the scalar $q$ are the authority. The optional positive-root amplitude $\Psi^{(+)}=(\sqrt{E_Y},\sqrt{E_I})$ is a derived coordinate lift and adds no independent canonical degree of freedom.

### 1.2 Conditional geometric sectors

The following structures are compatible extensions with separate physical assumptions:

- the positive Hermitian coherence fibre $\Gamma\in\operatorname{Herm}_2^+$;
- the off-diagonal coherence $c$;
- the complex Yang/Yin doublet $\Psi$;
- the relative-$U(1)_Q$ connection $B_A$;
- the cross-glued two-rail scale graph;
- charged endpoint sections $\Upsilon_\pm$;
- the finite Wilson-link hopping extension;
- the affine bubble observation map.

The scalar $q$, off-diagonal $c$, connection $B_A$, curvature $G_{AB}$, and scale current $J_Q$ describe distinct quantities. Identifying them as different manifestations of one microscopic Qi field remains Hypothesized.

### 1.3 Separate particle branch

`foundations/particle-stationary-action-closure.md` uses a local $SU(2)_Q$ gauge sector, second-order charged-field time derivatives, a neutral fixed-$Q_C$ carrier, and its own Gauss closure. The Abelian graph action in `foundations/geometric-manifold-completion.md` uses a first-order complex doublet and relative $U(1)_Q$ connection. No interface currently identifies their fields, charges, temporal symplectic structures, or stress tensors.

The fixed-charge particle functional therefore remains a downstream alternative boundary-value problem. At its registered coefficient point, all twelve primary/domain arms fail Q2. That numerical result establishes no qualified solution at the tested point; global existence remains open.

## 2. Geometry of the Local State

### 2.1 Positive Hermitian fibre

The minimal coherence extension is

$$
\boxed{
\Gamma
:=
\begin{pmatrix}
E_Y&c^*\\
c&E_I
\end{pmatrix}
\in\operatorname{Herm}_2^+.}
\tag{DG3}
$$

Positivity gives

$$
E_Y\ge0,
\qquad
E_I\ge0,
\qquad
|c|^2\le E_YE_I.
\tag{DG4}
$$

For $\rho>0$,

$$
\widehat\Gamma
:=
\frac{\Gamma}{\rho}
=
\frac12\left(\mathbf1+\mathbf n\cdot\boldsymbol\sigma\right),
\tag{DG5}
$$

where

$$
\boxed{
\mathbf n
=
\frac1\rho
\begin{pmatrix}
2\operatorname{Re}c\\
2\operatorname{Im}c\\
E_Y-E_I
\end{pmatrix},
\qquad
\|\mathbf n\|\le1.}
\tag{DG6}
$$

The cone coordinate $\rho$ describes total density. The longitudinal coordinate

$$
z:=n_z=\frac{E_Y-E_I}{\rho}
\tag{DG7}
$$

describes Yang/Yin composition. The transverse coordinates $(n_x,n_y)$ describe the optional phase-bearing coherence.

The determinant is

$$
\det\Gamma
=E_YE_I-|c|^2
=
\frac{\rho^2}{4}(1-\|\mathbf n\|^2).
\tag{DG8}
$$

The projective shell $\|\mathbf n\|=1$ contains rank-one states. The canonical density sector is the diagonal subcone $c=0$.

### 2.2 The $\varphi$ composition is one latitude

The equilibrium ratio

$$
E_Y=\varphi E_I
$$

is equivalent to

$$
\boxed{z=z_\varphi:=\varphi^{-3}.}
\tag{DG9}
$$

It selects a population latitude. It leaves $\rho$, $|c|$, the transverse phase, spatial profile, scale profile, and topology unselected.

### 2.3 What the scalar $q$ measures

Using

$$
\varepsilon
=
\frac{\rho\varphi^2}{2}(z-z_\varphi),
\tag{DG10}
$$

the canonical diagnostic becomes

$$
\boxed{
q(\rho,z)
=
\frac{\rho^2}
{\rho^2+\varphi^{-2}
+\frac{\rho^2\varphi^4}{4}(z-z_\varphi)^2}.}
\tag{DG11}
$$

It depends on density and composition. It does not depend on $n_x$, $n_y$, $|c|$, the phase of $c$, or $\det\Gamma$.

For fixed $E_Y,E_I$, the two states

$$
\Gamma_{\rm diag}
=
\begin{pmatrix}
E_Y&0\\
0&E_I
\end{pmatrix},
\qquad
\Gamma_{\rm shell}
=
\begin{pmatrix}
E_Y&\sqrt{E_YE_I}\,e^{-i\theta}\\
\sqrt{E_YE_I}\,e^{i\theta}&E_I
\end{pmatrix}
\tag{DG12}
$$

have the same canonical $q$ and different transverse coherence. The scalar $q$ is therefore a density-and-composition gate. The identification of $c$ as a microscopic Qi degree of freedom requires a separate physical postulate and dynamical test.

## 3. The Geometric Stack

The present geometry has six distinct layers.

| Layer | Object | Aspect described | Status |
|---|---|---|---|
| Physical base | $X_4=\mathbb R_t\times M_3$ | where and when the densities evolve | selected background geometry; covariant extension open |
| Scale base | $I_{\mathfrak s}$ or the two-rail graph $G_{\mathfrak s}$ | logarithmic ordering and global scale routing | coordinate Derived; graph Hypothesized |
| State fibre | $\operatorname{Herm}_2^+$ | local density, composition, and optional transverse coherence | Derived compatibility geometry |
| Relative connection | $B_A$ on $U(1)_Q$ | comparison of relative phase between points and scales | Hypothesized physical field |
| Endpoint sectors | $\Upsilon_\pm$ and $\mathcal W_{+\leftarrow-}$ | scale-vertex conversion and conditional return path | Hypothesized coefficients / Derived conditional ledgers |
| Bubble image | $\mathbf X=D\mathbf n$ | affine representation of the normalized state | exact map between declared geometries; physical embedding open |

The field currently evolves mainly **on** these geometries. Equations that make the physical metric, scale metric, fibre metric, or bubble embedding respond to the state remain open.

## 4. Conservative Transport Block

The conditional conservative graph action is the Abelian first-order action GM44 in `foundations/geometric-manifold-completion.md` §3.4. Its field content is the complex doublet $\Psi$, the relative connection $B_A$, the physical background metric, and the scale graph.

The relative frame acts as

$$
\Psi\mapsto
\exp\!\left(-\frac{i\alpha}{2}\sigma_3\right)\Psi,
\qquad
B_A\mapsto B_A+\frac1{g_Q}\partial_A\alpha.
\tag{DG13}
$$

On the coherence fibre,

$$
\Gamma\mapsto U_Q\Gamma U_Q^\dagger,
\qquad
U_Q(\alpha)
=
\exp\!\left(-\frac{i\alpha}{2}\sigma_3\right).
\tag{DG14}
$$

The covariant derivative is

$$
\nabla_A^B\Gamma
:=
\partial_A\Gamma
-i\left[\frac{g_Q}{2}B_A\sigma_3,\Gamma\right].
\tag{DG15}
$$

The connection rotates the transverse Bloch coordinates around the composition axis and leaves the diagonal populations invariant. Its curvature

$$
G_{AB}
=
\partial_AB_B-\partial_BB_A
\tag{DG16}
$$

describes relative-phase holonomy. The mixed component $G_{i\mathfrak s}$ is a candidate ingredient in interscale stress. A physical force follows only after a complete action yields a mixed momentum stress $T_{i\mathfrak s}$ and a carrier-to-stress map.

The conservative action supplies covariant spatial and scale currents. It separately conserves Yang and Yin in the bulk and does not generate the canonical irreversible conversion law.

## 5. Canonical Conversion as a Nonlinear Positive-Cone Flow

### 5.1 State-dependent two-jump generator

Define

$$
\gamma_{\rm conv}(\Gamma)
:=
\lambda[1-q(E_Y,E_I)]
\ge0,
\qquad
\lambda\ge0.
\tag{DG17}
$$

and fixed jumps

$$
J_{Y\to I}=|I\rangle\langle Y|,
\qquad
J_{I\to Y}=\sqrt\varphi\,|Y\rangle\langle I|.
\tag{DG18}
$$

Let

$$
\mathcal L_0[\Gamma]
:=
\sum_{a\in\{Y\to I,I\to Y\}}
\left(
J_a\Gamma J_a^\dagger
-
\frac12\{J_a^\dagger J_a,\Gamma\}
\right).
\tag{DG19}
$$

The minimal conversion lift is

$$
\boxed{
\mathcal L_{\rm conv}[\Gamma]
=
\gamma_{\rm conv}(\Gamma)\mathcal L_0[\Gamma].}
\tag{DG20}
$$

At fixed $q$, this is a linear GKSL generator. With the canonical state-dependent $q$, equation (DG20) is a nonlinear vector field and is not itself a linear completely positive map or semigroup.

### 5.2 Positive-cone preservation

Along any solution, define the nondecreasing conversion time

$$
\tau(t)
:=
\int_0^t\gamma_{\rm conv}(\Gamma(t'))\,dt'.
\tag{DG21}
$$

Where $\gamma_{\rm conv}>0$,

$$
\frac{d\Gamma}{d\tau}
=
\mathcal L_0[\Gamma].
\tag{DG22}
$$

The $\tau$-flow is the completely positive trace-preserving semigroup generated by $\mathcal L_0$. Equation (DG20) follows the same orbits with state-dependent speed. Therefore the nonlinear conversion flow preserves the positive cone and trace. A zero rate freezes the trajectory without leaving the cone.

This time-reparametrization statement is specific to the scalar factorization in (DG20). A more general state-dependent jump operator would require a separate positivity proof.

### 5.3 Exact diagonal and transverse reduction

Direct evaluation gives

$$
\boxed{
\mathcal L_{\rm conv}[\Gamma]
=
\gamma_{\rm conv}
\begin{pmatrix}
-(E_Y-\varphi E_I)&-\frac{\varphi^2}{2}c^*\\
-\frac{\varphi^2}{2}c&E_Y-\varphi E_I
\end{pmatrix}.}
\tag{DG23}
$$

Hence

$$
\operatorname{tr}\mathcal L_{\rm conv}=0,
\tag{DG24}
$$

and the diagonal entries reproduce (DG2) exactly. The optional transverse coordinate obeys

$$
\boxed{
\dot c\big|_{\rm conv}
=-\gamma_c c,
\qquad
\gamma_c
:=
\frac{\varphi^2}{2}\lambda(1-q).}
\tag{DG25}
$$

The normalized composition satisfies

$$
\boxed{
\dot z\big|_{\rm conv}
=-\gamma_\varepsilon(z-z_\varphi),
\qquad
\gamma_\varepsilon
:=
\varphi^2\lambda(1-q)
=2\gamma_c.}
\tag{DG26}
$$

The half-rate relation is a property of this two-jump lift. It is not fixed by the canonical diagonal PDE alone.

### 5.4 Relative-frame covariance

The jumps acquire opposite phases under $U_Q$:

$$
U_QJ_{Y\to I}U_Q^\dagger=e^{+i\alpha}J_{Y\to I},
\qquad
U_QJ_{I\to Y}U_Q^\dagger=e^{-i\alpha}J_{I\to Y}.
\tag{DG27}
$$

Their dissipators are phase independent, while $q$ is unchanged because the diagonal populations are unchanged. Therefore

$$
\boxed{
\mathcal L_{\rm conv}[U_Q\Gamma U_Q^\dagger]
=
U_Q\mathcal L_{\rm conv}[\Gamma]U_Q^\dagger.}
\tag{DG28}
$$

This is constant relative-frame covariance. Time-dependent covariance belongs to the conservative temporal connection.

## 6. The Integrated Open Dynamical Equation

The current sectors assemble into the effective matrix balance

$$
\boxed{
\nabla_t^B\Gamma
+
\nabla_i^B\mathcal J^i
+
\nabla_{\mathfrak s}^B\mathcal J^{\mathfrak s}
=
\mathcal L_{\rm conv}[\Gamma]
+
\mathcal L_{\rm end}[\Gamma]
+
\Xi.}
\tag{DG29}
$$

The terms retain separate provenance:

- $\mathcal J^i$ and $\mathcal J^{\mathfrak s}$ belong to the conditional conservative action;
- $\mathcal L_{\rm conv}$ is the nonlinear reduced conversion flow (DG20);
- $\mathcal L_{\rm end}$ collects resolved scale-vertex channels;
- $\Xi$ represents a declared bath, noise, or unresolved source after its normalization and stochastic convention are selected.

Equation (DG29) is an open-system field equation. It is not the Euler–Lagrange equation of one landed microscopic action. A microscopic completion must include explicit reservoir degrees of freedom and reproduce (DG20), the selected noise, and the positivity boundary after reduction while retaining the conservative currents.

Taking the trace gives the total-density ledger

$$
\partial_t\rho
+
\nabla_i\operatorname{tr}\mathcal J^i
+
\partial_{\mathfrak s}\operatorname{tr}\mathcal J^{\mathfrak s}
=
\operatorname{tr}\mathcal L_{\rm end}
+
\operatorname{tr}\Xi,
\tag{DG30}
$$

because $\operatorname{tr}\mathcal L_{\rm conv}=0$.

The relative component is obtained by contracting with $\sigma_3$. Its local source is the Yang-to-Yin conversion, while the conservative relative connection supplies its covariant transport. This is the precise interface between canonical population relaxation and conditional gauge geometry.

## 7. Exact Finite-Density Coherence-Support Boundary

### 7.1 Strict finite-density decay in the minimal lift

For every finite state,

$$
1-q
=
\frac{\varphi^{-2}+\varepsilon^2}
{\rho^2+\varphi^{-2}+\varepsilon^2}
>0.
\tag{DG31}
$$

If $\lambda>0$, then

$$
\gamma_c>0.
\tag{DG32}
$$

Equation (DG25) gives

$$
\boxed{
\frac{d}{dt}|c|^2\bigg|_{\rm conv}
=-2\gamma_c|c|^2
=-\varphi^2\lambda(1-q)|c|^2.}
\tag{DG33}
$$

Therefore an undriven homogeneous stationary state of the minimal conversion lift satisfies

$$
\boxed{c=0}
\tag{DG34}
$$

at finite density when $\lambda>0$.

This is a conditional support obstruction. It applies to the minimal lift with no transverse source, protection, boundary influx, or modified reservoir. It does not establish nonexistence in the full open equation (DG29).

### 7.2 Bounded-density decay estimate

Suppose the conversion-only trajectory remains bounded by

$$
0\le\rho(t)\le\rho_{\max}<\infty.
\tag{DG35}
$$

Equation (DG31) implies

$$
1-q
\ge
\frac{\varphi^{-2}}
{\rho_{\max}^2+\varphi^{-2}}.
\tag{DG36}
$$

Thus

$$
\gamma_c
\ge
\frac{\lambda}
{2(\rho_{\max}^2+\varphi^{-2})},
\tag{DG37}
$$

and

$$
\boxed{
|c(t)|^2
\le
|c(0)|^2
\exp\!\left[
-\frac{\lambda t}
{\rho_{\max}^2+\varphi^{-2}}
\right].}
\tag{DG38}
$$

This estimate gives a quantitative target for any coherence-supporting completion.

### 7.3 Required transverse support

Collect all coherent Hamiltonian torque, boundary influx, endpoint injection, and reservoir engineering that can do real work on the transverse component into $S_c$. The local transverse equation has the schematic form

$$
D_t^Bc
+
\nabla_iJ_c^i
+
\partial_{\mathfrak s}J_c^{\mathfrak s}
=
S_c-\gamma_cc.
\tag{DG39}
$$

For a stationary closed domain in which the conservative transport terms contribute only boundary flux to the real coherence-norm balance,

$$
\boxed{
\int\gamma_c|c|^2
=
\operatorname{Re}\int c^*S_c.}
\tag{DG40}
$$

A nonzero stationary $c$ therefore requires positive transverse support. If $\gamma_c\ge\gamma_{c,\min}>0$, Cauchy–Schwarz gives the necessary bound

$$
\boxed{
\|S_c\|_2
\ge
\gamma_{c,\min}\|c\|_2.}
\tag{DG41}
$$

Equation (DG41) does not select the source. It specifies the minimum role that the missing mechanism must perform.

## 8. Endpoint and Wilson Closure

The registered rail-source orientation is

$$
\Gamma_-:=+\mathcal J_Q,
\qquad
\Gamma_+:=-\mathcal J_Q.
\tag{DG42}
$$

The EL9 endpoint equations with the separately declared Wilson transport are

$$
\boxed{
\begin{aligned}
\partial_tn_-+\nabla\cdot\mathbf J_{\Upsilon,-}
&=\Gamma_- - I_{-\to+},\\
\partial_tn_++\nabla\cdot\mathbf J_{\Upsilon,+}
&=\Gamma_+ + I_{-\to+}.
\end{aligned}}
\tag{DG43}
$$

Their sum is

$$
\partial_t(n_-+n_+)
+
\nabla\cdot(\mathbf J_{\Upsilon,-}+\mathbf J_{\Upsilon,+})
=
\Gamma_-+\Gamma_+=0.
\tag{DG44}
$$

The transport $I_{-\to+}$ cancels from the total endpoint-number ledger. Each rail-to-endpoint source cancels locally in the relative-charge ledger because the rail and endpoint sections carry opposite relative charge. The Wilson edge carries the oriented charge current associated with the endpoint number it moves.

For a homogeneous stationary circuit,

$$
\boxed{I_{-\to+}=\mathcal J_Q}
\tag{DG45}
$$

closes both endpoint equations, subject to

$$
|\mathcal J_Q|
\le
I_c
=
\frac{2t_\Upsilon u_-u_+}{\hbar}.
\tag{DG46}
$$

The coefficient $t_\Upsilon$, endpoint amplitudes, and local scale-bulk mediator remain unselected. EL9 alone contains no $D_{\mathfrak s}\Upsilon$ transport term.

## 9. Stress and Geometry Backreaction

### 9.1 Number flow is distinct from momentum flow

The currents in (DG29) carry density or relative charge. Physical force requires a momentum balance

$$
\partial_t p_i
+
\nabla_jT_i{}^j
+
\partial_{\mathfrak s}T_i{}^{\mathfrak s}
=
f_i^{\rm ext}.
\tag{DG47}
$$

The scale-window force is

$$
F_i^{(\mathfrak s)}
=
\int_Vd^3x
\left[
T_{i\mathfrak s}(\mathfrak s_-)
-
T_{i\mathfrak s}(\mathfrak s_+)
\right].
\tag{DG48}
$$

A relation between $J_Q$ and $T_{i\mathfrak s}$ requires a constitutive carrier map. The conversion, endpoint, and Wilson number ledgers do not supply that map.

### 9.2 Conservative and reservoir stress

For the conservative sector, a metric variation can define

$$
T_{AB}^{\rm cons}
:=-\frac{2}{\sqrt{|g|}}
\frac{\delta S_{\rm cons}}
{\delta g^{AB}}.
\tag{DG49}
$$

An open-system reduction exchanges energy and momentum with its reservoir. A geometry equation must therefore use the total stress of the conservative fields, endpoint sectors, and whatever bath produces $\mathcal L_{\rm conv}$ and $\Xi$.

The missing backreaction has the schematic form

$$
\boxed{
\mathcal E_{AB}[g,\text{scale geometry}]
=
\text{total field-plus-reservoir stress}.}
\tag{DG50}
$$

Neither the geometric operator $\mathcal E_{AB}$ nor the total stress is selected by the current theory. Equation (DG50) is a requirement, not a landed field equation.

### 9.3 Qi-gate lapse boundary

The canonical conversion fixes only the product

$$
K(q)N(q)=1-q,
\tag{DG51}
$$

where $K$ is an intrinsic kinetic factor and $N=d\tau/dt$ is a candidate lapse. The canonical PDE does not select whether $q$ changes internal kinetics, local clock rate, or both. A physical clock observable or covariant action is required to choose the split.

## 10. What the Current Geometry Describes

The present roles can be stated without merging the variables:

| Quantity | Aspect described |
|---|---|
| $E_Y,E_I$ | canonical local populations |
| $\rho$ | total density and cone radius |
| $\varepsilon$ or $z-z_\varphi$ | displacement from the $\varphi$ composition |
| $q$ | bounded density-and-composition diagnostic that gates conversion |
| $c$ | optional transverse coherence in the positive Hermitian lift |
| $B_A$ | optional relative-phase comparison connection |
| $G_{AB}$ | optional relative-connection curvature |
| $J_Q$ | relative-charge flow through the scale sector |
| $\mathbf J_{\Upsilon,v}$ | endpoint number flow through physical space |
| $I_{-\to+}$ | endpoint number transport between scale vertices |
| $T_{i\mathfrak s}$ | mixed spatial momentum flux through scale |
| $\mathbf X=D\mathbf n$ | affine observation image of normalized coherence state |

The hypothesis that $c$, $B_A$, $G_{AB}$, and $J_Q$ are successive manifestations of one microscopic Qi degree of freedom remains open. The scalar $q$ does not establish that identification.

## 11. Minimal Testable Boundary-Value Problem

The next field calculation should use the smallest sector that can test persistent coherence without importing the separate $SU(2)_Q$ particle action.

### 11.1 Unknowns

On a selected physical domain and the Abelian two-rail scale graph, solve for

$$
\Gamma(x,\mathfrak s),
\qquad
B_A(x,\mathfrak s),
\qquad
\Upsilon_\pm(x),
\qquad
S_c(x,\mathfrak s),
\tag{DG52}
$$

where $S_c$ must be derived from a declared coherent field, boundary condition, or reservoir sector. It cannot be fitted after the solution is inspected.

### 11.2 Equations

The stationary problem must contain:

1. the matrix balance (DG29) with $\partial_t\Gamma=0$;
2. the conservative gauge equation derived from GM44;
3. the endpoint equations (DG43);
4. the Wilson capacity condition (DG46) when the finite edge is retained;
5. the source normalization and noise convention when $\Xi\ne0$;
6. the coherence-support budget (DG40);
7. finite-energy or finite-open-system-flux boundary conditions.

### 11.3 Qualification gates

A candidate qualifies only if it satisfies all of the following:

1. $\Gamma\succeq0$ everywhere;
2. the canonical diagonal reduction is recovered when $c$ and the conditional connection sector are disabled;
3. total density, endpoint number, and relative charge close with every boundary flux included;
4. the nonzero transverse coherence is supported by an identified term satisfying (DG40);
5. the conservative and bath energy/momentum ledgers are explicit;
6. the full linearized open-system spectrum has no unaccounted growing mode;
7. direct time evolution preserves the state for the declared observation window;
8. any matter interpretation states a finite energy, radius, charge, and measurable observable.

This is an open-system stationary problem. It is not an extremization of one conservative energy unless the reservoir is promoted to explicit dynamical fields.

## 12. Interface Requirements for a Microscopic Particle Branch

A future connection to the fixed-charge local-$SU(2)_Q$ particle action requires all of the following:

1. an explicit embedding or reduction relating the Abelian relative connection to the local $SU(2)_Q$ connection;
2. a map between first-order graph symplectic structure and second-order charged-field time dynamics;
3. a charge map relating rail/endpoint relative charge to the fixed carrier charge $Q_C$;
4. one shared stress tensor and geometry source;
5. compatible boundary conditions and gauge constraints;
6. a reservoir reduction reproducing (DG2) without violating the particle Gauss law.

Absent those maps, the two sectors remain separate conditional branches.

## 13. Derived, Hypothesized, and Open Results

The frozen DG1–DG7 receipt returns **PASS**. The universal finite-state $q$
bound and the strict undriven-coherence sign follow from the exact
factorization in §§5 and 7; the deterministic checker supplies the registered
implementation witness. See
`computations/dynamical_geometry_closure_report.md`.

| Statement | Status |
|---|---|
| Canonical $E_Y,E_I,q$ conversion law | **Derived PDE / Asserted $q$ constitutive input** |
| Positive Hermitian state geometry and Bloch decomposition | **Derived conditional geometry** |
| Nonlinear pointwise Lindblad-form lift (DG20) | **Hypothesized off-diagonal lift / Derived exact diagonal reduction** |
| Positive-cone preservation by time reparametrization | **Derived within the declared lift** |
| $\gamma_c=\gamma_\varepsilon/2$ | **Derived within the declared lift** |
| Strict finite-density decay of undriven $c$ | **Derived conditional boundary** |
| Coherence-support budget (DG40) | **Derived conditional stationary identity** |
| Relative-$U(1)_Q$ connection and graph currents | **Hypothesized physical sector / Derived covariance algebra** |
| Endpoint spatial flux and Wilson ledgers | **Derived conditional conservation / Hypothesized physical coefficients** |
| One microscopic action producing all sectors | **Open** |
| Complete Noether stress and geometry backreaction | **Open** |
| Local scale-bulk endpoint mediator | **Open** |
| Interface to the local-$SU(2)_Q$ fixed-charge particle branch | **Open** |
| Qualified stationary matter solution | **Not established** |

## 14. Conclusion

The present Cassi geometry supports one explicit open-system organization:

$$
\text{canonical populations and }q
\quad+
\quad
\text{conditional coherence fibre and currents}
\quad+
\quad
\text{endpoint channels}
\quad+
\quad
\text{declared reservoir terms}.
$$

The scalar $q$ controls the speed of canonical composition relaxation. The optional off-diagonal $c$ describes transverse coherence in the positive Hermitian lift. The relative connection transports its phase frame, while endpoint and Wilson channels close conditional number and charge ledgers. These roles are compatible and remain physically distinct.

Putting the existing sectors together produces a specific requirement: finite-density transverse coherence decays in the undriven minimal conversion lift. A phase-bearing stationary object therefore needs an identified support term whose real coherence injection balances the positive decay budget. The microscopic source of that term, the total stress sourcing geometry, and the interface to a qualified particle branch are the next derivation targets.

## References

- `foundations/cassi-first-principles.md`—canonical Yin/Yang densities, scalar $q$, and gated conversion.
- `foundations/physical-becoming-hierarchy.md`—gradient-flow and reduced Markov-bath boundary.
- `foundations/geometric-manifold-completion.md`—positive coherence fibre, relative-$U(1)_Q$ graph action, and matrix continuity ansatz.
- `foundations/interscale-current-soliton.md`—conditional scale-current and circuit geometry.
- `foundations/interscale-stress-attenuation-boundary.md`—mixed momentum stress and force boundary.
- `foundations/endpoint-link-and-localization-boundary.md`—endpoint continuity, spatial flux, and Wilson transport.
- `foundations/particle-stationary-action-closure.md`—separate fixed-charge local-$SU(2)_Q$ particle branch.
- `computations/dynamical_geometry_closure_prereg.md`—frozen DG1–DG7 reduction and ledger criteria.
- `computations/dynamical_geometry_closure_report.md`—DG1–DG7 analytic proof,
  first-execution receipt, and scoped PASS verdict.
