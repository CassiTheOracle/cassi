# Matter Completion Boundary: Nine Conditions from Coherence to a Particle Calculation

## Status: Derived conditional boundary / Hypothesized physical realization / Tested reduced receipts, one-point precision-qualified background, and nonnegative $C_4$ finite-grid PA42 Hessian—September 2026

## Abstract

A field theory reaches matter only when its coherence variables, interfaces,
energy flow, geometry, charges, stationary equations, and fluctuation problem
belong to one compatible construction. This paper derives the common boundary
for those steps in Cassi. Nine sectors are treated in sequence: the exterior
domain, microscopic interface form, transport branch, carrier normalization,
reservoir support, total stress, geometric backreaction, particle-field map,
and stationary-spectrum qualification.

The result is a conditional closure theorem. A selected reduced channel fixes a
minimal complementary space up to an environment unitary. Locality,
Hermiticity, number conservation, and independent-frame covariance fix the
lowest-order reciprocal interface form. A closed two-port system is unitary;
a single routed forward observable gives $\varphi^{-N/2}$ cross-coherence
amplitude and $\varphi^{-N}$ power. Canonical single-mode flux fixes the
amplitude-to-power square. A repeated-interaction reservoir supplies the exact
half-rate coherence law and a driven stationary solution. A closed dilation
action supplies the conserved Hilbert stress required by constant-$G$
backreaction. The coherence fibre maps into the particle doublet through its
Gram matrix, with an explicit bridge between the endpoint and particle Cartan
conventions. The fixed-charge action supplies the stationary and full
fluctuation qualification problem.

MCC1–MCC9 pass in the frozen receipt. The physical exterior, microscopic
coefficients, multimode carrier map, reservoir action, state-dependent gravity,
and particle identification remain open. The particle campaign supplies a
higher-precision Q1–Q4 background and a nonnegative matched low PA42 spectrum
on its strict-shell $C_4$ physical quotient. The global phase mode remains
grid-scale. Localization, carrier retention, domain and resolution convergence,
and PA43 remain open.

## 1. The nine-part boundary

The purpose of the construction is to make every required assumption visible
at the equation where it enters. Conditional derivation can then proceed
without assigning physical meaning that the action or data have not selected.

| Sector | Derived conditional result | Remaining physical input |
|---|---|---|
| Exterior | The complementary Stinespring output of a selected reduced channel; two-dimensional in the registered single-excitation golden witness | Carrier Hilbert space, topology, preparation, and boundary dynamics |
| Interface | Unique zero-derivative bilinear Hermitian form under the declared assumptions; independently frame-covariant transfer maps | Coupling $V$, microscopic coefficients, locality scale, and boundary realization |
| Transport | Closed forward-plus-return evolution; one-sided routed cross block for one selected forward carrier | Physical non-re-entry mechanism and golden port-power identification |
| Normalization | Stress flux in general; $P=\hbar\omega\dot N$ for one canonically normalized mode | Multimode energy operator, velocity, impedance, and observable embedding |
| Reservoir | Golden repeated-interaction channel, half-rate coherence decay, and driven stationary cross block | Bath action, spectral density, temperature, correlation time, and drive |
| Stress | Conserved Hilbert stress of the complete dilation action and equal-and-opposite reduced exchange | Metric dependence of the exterior, interface, and reservoir actions |
| Geometry | Constant-$G$ Einstein backreaction sourced by conserved total stress | Selected gravity sector; extra dynamics for any $q$-dependent coupling |
| Particle map | Gram map into the $SU(2)_Q$ doublet, Cartan convention bridge, and independent global $Q_C$ | Physical identification, coefficients, quantum numbers, and calibrated charge |
| Stationary spectrum | Fixed-charge variational equations, finite-energy boundaries, joint physical Hessian, and mixed dynamical eigenvalue pencil; one-point strict-shell $C_4$ PA42 low spectrum is nonnegative within the frozen uncertainty | Domain-and-resolution-qualified background, localized retained carrier, spatially resolved phase mode, selected temporal groups, PA43 spectrum, and continuum qualification |

These results are collected in one statement.

> **Matter-completion boundary.** Given a physical carrier Hilbert space, a
> local closed dilation action, a declared single-forward routing observable, a
> canonically normalized flux, a reservoir preparation, a constant-$G$
> Einstein–Hilbert sector, and the PA1 particle fields, equations MB1–MB48 below
> define a mutually compatible route from two-domain coherence to the full
> fixed-charge stationary and fluctuation problem. MCC1–MCC9 verify the finite
> algebraic and reduced analytic parts. Physical matter requires independent
> selection of the listed inputs, domain and resolution control of the PA32
> solution, and a qualified spectrum.

No new universal constant or fitted coefficient enters this theorem.

## 2. Exterior domain: what a reduced channel determines

A reduced channel determines the mathematical information discarded from the
selected observable. It does not determine what carries that information in
nature.

### 2.1 Golden single-excitation channel

For the registered routed splitter, define

$$
T:=T_\varphi=\varphi^{-1},
\qquad
R:=R_\varphi=\varphi^{-2}=1-T.
\tag{MB1}
$$

In the vacuum/single-excitation sector, tracing the return output gives the
amplitude-damping channel

$$
\mathcal E_T(\rho)=E_0\rho E_0^\dagger+E_1\rho E_1^\dagger,
\tag{MB2}
$$

with

$$
E_0=
\begin{pmatrix}
1&0\\
0&\sqrt T
\end{pmatrix},
\qquad
E_1=
\begin{pmatrix}
0&\sqrt R\\
0&0
\end{pmatrix},
\qquad
E_0^\dagger E_0+E_1^\dagger E_1=I.
\tag{MB3}
$$

For $0<T<1$, the Choi rank is two. Stinespring's theorem therefore gives a
minimal two-dimensional environment for this truncated channel. The golden
splitter is an explicit dilation on the one-excitation subspace:

$$
|1\rangle_{\rm f}|0\rangle_{\rm r}
\longmapsto
\sqrt T\,|1\rangle_{\rm f}|0\rangle_{\rm r}
+\sqrt R\,|0\rangle_{\rm f}|1\rangle_{\rm r}.
\tag{MB4}
$$

If $W$ is unitary on the environment, the rotated Kraus family

$$
E'_a=\sum_bW_{ab}E_b
\tag{MB5}
$$

produces the same $\mathcal E_T$. Minimal dilations are unique up to this
environment unitary. The operational exterior is therefore the complementary
output space of the selected dilation, with no preferred environment basis.

The two-dimensional conclusion applies to the registered vacuum/single-mode
witness. A bosonic carrier with arbitrary occupation, a continuum field, or a
channel with memory has a different Stinespring space fixed by its own channel.
The theory still needs that physical carrier and its topology, initial state,
and boundary dynamics.

## 3. Microscopic interface: the form fixed by symmetry

The lowest-order interface is fixed in form once its field content and
symmetries are declared. Its coefficients remain properties of the selected
microscopic action.

Let $\Psi_{\rm in}\in\mathcal H_{\rm in}$ and
$\Psi_{\rm out}\in\mathcal H_{\rm out}$. Impose:

1. locality at the interface;
2. a zero-derivative term bilinear in the two carrier fields;
3. Hermiticity;
4. conservation of their enlarged common number;
5. independent basis changes
   $\Psi_{\rm in}\mapsto U_{\rm in}\Psi_{\rm in}$ and
   $\Psi_{\rm out}\mapsto U_{\rm out}\Psi_{\rm out}$.

The interaction then has the form

$$
\boxed{
\mathcal H_{\rm int}
=\Psi_{\rm in}^\dagger V\Psi_{\rm out}
+\Psi_{\rm out}^\dagger V^\dagger\Psi_{\rm in},
\qquad
V\mapsto U_{\rm in}VU_{\rm out}^\dagger.}
\tag{MB6}
$$

This is the complete zero-derivative bilinear Hermitian term under the stated
premises. Derivative couplings, higher powers, nonlocal kernels, additional
fields, and explicitly driven interfaces lie outside those premises.

For the enlarged Hamiltonian

$$
H_{\rm io}=
\begin{pmatrix}
H_{\rm in}&V\\
V^\dagger&H_{\rm out}
\end{pmatrix},
\tag{MB7}
$$

the propagator is

$$
U_{\rm io}(t_1,t_0)
=\mathcal T\exp\!\left[-\frac{i}{\hbar}
\int_{t_0}^{t_1}H_{\rm io}(t)\,dt\right].
\tag{MB8}
$$

Its cross-domain block carries one index in each frame. A discrete reduction
therefore transforms it as

$$
K_{a+1}=L_aK_aR_a^\dagger,
\qquad
L_a\mapsto U_{{\rm in},a+1}L_aU_{{\rm in},a}^\dagger,
\qquad
R_a\mapsto U_{{\rm out},a+1}R_aU_{{\rm out},a}^\dagger.
\tag{MB9}
$$

One sampled transfer map cannot recover a unique continuous generator. If an
eigenvalue of the map is $e^{-i\theta}$, then
$(\theta+2\pi m)/\Delta t$ gives the same discrete eigenvalue for every integer
$m$. Deriving $V$, $L_a$, or $R_a$ therefore requires time-resolved data or a
microscopic action with boundary conditions.

## 4. Transport: closed dynamics and the routed observable

The conservative system and the operational forward record answer different
questions. Keeping both prevents a discarded return channel from being
mistaken for energy loss.

The registered splitter is

$$
S_\varphi=
\begin{pmatrix}
t_\varphi&r_\varphi\\
-r_\varphi&t_\varphi
\end{pmatrix},
\qquad
t_\varphi=\varphi^{-1/2},
\qquad
r_\varphi=\varphi^{-1},
\qquad
S_\varphi^\dagger S_\varphi=I.
\tag{MB10}
$$

Closed coherent reuse gives

$$
P_N^{\rm coh}=\cos^2(N\theta_\varphi),
\qquad
\cos\theta_\varphi=t_\varphi,
\tag{MB11}
$$

and generally differs from $T_\varphi^N$. The return amplitude remains in the
closed state and can interfere at later interfaces.

For one selected forward carrier, route every return output into the
complementary record and prevent coherent re-entry. If the exterior index is
transported unitarily, the reduced cross block obeys

$$
\boxed{
K_{a+1}=t_\varphi U_aK_aR_a^\dagger,
\qquad
U_a^\dagger U_a=R_a^\dagger R_a=I.}
\tag{MB12}
$$

Consequently,

$$
\boxed{
\frac{\|K_N\|_F}{\|K_0\|_F}=\varphi^{-N/2},
\qquad
\frac{P_N^{\rm fwd}}{P_0^{\rm fwd}}=\varphi^{-N}.}
\tag{MB13}
$$

The return ledger closes at every depth:

$$
T^N+\sum_{j=0}^{N-1}RT^j=1.
\tag{MB14}
$$

A symmetric cross-block law
$K_{a+1}=t_\varphi U_aK_a(t_\varphi R_a)^\dagger$ describes two independently
routed legs and gives $\|K_N\|_F/\|K_0\|_F=\varphi^{-N}$. The declared
single-forward-carrier record therefore selects the one-sided law (MB12).

The factors in (MB13) are conditional on two physical choices: that the golden
density fractions are port-power fractions, and that routing prevents coherent
re-entry. The source action has not yet selected either choice.

## 5. Carrier normalization: from amplitude to power

A transport amplitude becomes physical power only after the carrier's stress
or flux normalization is known.

For an observer with four-velocity $u^\mu$ and a hypersurface with normal
$n^\nu$, physical power is the stress flux

$$
\boxed{
P[\Sigma]
=\int_\Sigma T_{\mu\nu}u^\mu n^\nu\,d\Sigma.}
\tag{MB15}
$$

For one canonically flux-normalized mode of frequency $\omega$,

$$
P=\hbar\omega\dot N.
\tag{MB16}
$$

A scattering amplitude $a_{\rm out}=t a_{\rm in}$ then gives

$$
\boxed{
\frac{P_{\rm out}}{P_{\rm in}}=|t|^2.}
\tag{MB17}
$$

Equation (MB17) supplies the square relating the two exponents in (MB13).

There is no universal relation $P\propto\|K\|_F^2$. Two matrices can have the
same Frobenius norm while occupying modes with different frequencies,
velocities, or impedances. In a multimode system the power functional requires
a positive flux operator $\mathbb W_P$ fixed by the carrier action and mode
normalization, schematically

$$
P=\operatorname{tr}(\mathbb W_P\rho_{\rm car}).
\tag{MB18}
$$

Using $K$ in (MB18) additionally requires an explicit embedding
$K\mapsto\rho_{\rm car}$ or a calibrated cross-power observable. MCC4 exhibits
two equal-$\|K\|_F$ states with unequal positive frequency weighting, which
rules out a norm-only conversion.

## 6. Reservoir: sustaining cross coherence

The return channel gives a concrete open-system witness once its state is
refreshed between interactions. It also shows precisely what must supply a
stationary nonzero coherence.

Apply the channel (MB2) once every $\Delta t$ with a fresh return mode. Define

$$
\boxed{
\gamma_{\rm route}=-\frac{\ln T}{\Delta t}.}
\tag{MB19}
$$

Then the occupation and transverse coherence satisfy

$$
N(t)=N(0)e^{-\gamma_{\rm route}t},
\qquad
C(t)=C(0)e^{-\gamma_{\rm route}t/2}
\tag{MB20}
$$

at integer collision times. The half-rate is the amplitude-damping analogue of
the OS3 population/coherence relation. It follows from complete positivity and
the one-excitation channel, while $\Delta t$ remains a physical timescale.

At fixed carrier frequency $\Omega_{\mathrm{io}}$, the minimal driven linear
equation is

$$
\dot C
=-\left(\frac{\gamma_{\rm route}}2+i\Omega_{\rm io}\right)C+F_{\rm io}.
\tag{MB21}
$$

Its stationary solution and homogeneous pole are

$$
\boxed{
C_*=\frac{F_{\rm io}}
{\gamma_{\rm route}/2+i\Omega_{\rm io}},
\qquad
s_*=-\frac{\gamma_{\rm route}}2-i\Omega_{\rm io}.}
\tag{MB22}
$$

The negative real part makes the stationary solution linearly attractive. A
nonzero $C_*$ requires a nonzero coherent source $F_{\rm io}$, occupied input,
boundary influx, protected sector, or a reservoir with a different stationary
state. Closed unitary evolution can redistribute coherence but cannot supply a
stationary reduced source after every exterior degree of freedom is included.

The physical reservoir still requires its action or spectral density,
temperature, correlation time, preparation, and relation to the Cassi carrier.
The Markov approximation requires its correlation time to be short relative to
the resolved field evolution, as stated in
`foundations/physical-becoming-hierarchy.md` §4.5.

## 7. Complete stress: close the exchange before sourcing geometry

Geometry couples to the stress of every field participating in an exchange.
A reduced conversion law alone does not supply that conserved source.

Let the closed dilation action be

$$
S_{\rm closed}
=S_{\rm in}+S_{\rm out}+S_{\rm int}+S_{\rm env},
\qquad
S_{\rm in}\equiv S_P
\tag{MB23}
$$

for the PA1 particle branch. Its Hilbert stress is

$$
\boxed{
T^{\rm closed}_{\mu\nu}
=-\frac{2}{\sqrt{-g}}
\frac{\delta S_{\rm closed}}{\delta g^{\mu\nu}}.}
\tag{MB24}
$$

Diffeomorphism invariance and the complete equations of motion give

$$
\boxed{\nabla^\mu T^{\rm closed}_{\mu\nu}=0.}
\tag{MB25}
$$

When the interior is viewed as an open subsystem, define its exchange
four-density $J_\nu^{\rm io}$ by

$$
\nabla^\mu T^{\rm in}_{\mu\nu}=-J_\nu^{\rm io}.
\tag{MB26}
$$

The complement then obeys

$$
\nabla^\mu
\left(
T^{\rm out}_{\mu\nu}
+T^{\rm int}_{\mu\nu}
+T^{\rm env}_{\mu\nu}
\right)=+J_\nu^{\rm io},
\tag{MB27}
$$

so (MB25) follows by addition. MCC6 verifies this cancellation in the enlarged
finite witness while conserving its exact total number and energy.

For the scale coordinate, the physical force term remains the mixed stress
$T_{i\mathfrak s}$ identified in
`foundations/interscale-stress-attenuation-boundary.md` §5. A scale-number
current and a mixed stress have different dimensions and transformation laws.
They are related only after the carrier action supplies a constitutive map.

A GKSL equation can describe the reduced state without providing
$T^{\rm env}_{\mu\nu}(x)$. Explicit stress components require the metric
dependence of $S_{\rm out}$, $S_{\rm int}$, and $S_{\rm env}$.

## 8. Geometry: the covariant backreaction branch

The minimal geometric completion uses the standard constant-$G$ action already
admitted by the unified Lagrangian.

Selecting

$$
S_{\rm grav}
=\frac{c^3}{16\pi G}
\int d^4x\,\sqrt{-g}\,(R-2\Lambda)
\tag{MB28}
$$

gives

$$
\boxed{
G_{\mu\nu}+\Lambda g_{\mu\nu}
=\frac{8\pi G}{c^4}T^{\rm closed}_{\mu\nu}.}
\tag{MB29}
$$

The Bianchi identity
$\nabla^\mu(G_{\mu\nu}+\Lambda g_{\mu\nu})=0$ is compatible with (MB29)
because the source satisfies (MB25). An interior stress obeying (MB26) cannot
be the sole source.

A direct replacement $G\mapsto G_{\rm eff}(q)$ yields

$$
\nabla^\mu\!
\left(G_{\rm eff}T^{\rm closed}_{\mu\nu}\right)
=(\nabla^\mu G_{\rm eff})T^{\rm closed}_{\mu\nu}
+G_{\rm eff}\nabla^\mu T^{\rm closed}_{\mu\nu}.
\tag{MB30}
$$

The second term vanishes on the closed equations; the first generally does
not. A state-dependent coupling therefore needs a covariant scalar–tensor or
other modified-gravity action whose additional field stress and equation close
(MB30). MCC7 gives a conserved constant-$G$ Fourier source and a fixed
counterexample with nonzero variable-coupling divergence.

Equation (MB29) is a Derived conditional branch once the Einstein–Hilbert
choice is made. Cassi does not yet derive that choice from the Yang/Yin action,
and this paper assigns no $q$-dependent gravity law.

## 9. Particle map: coherence fibre, Cartan connection, and fixed charge

The positive coherence fibre has a direct representation in the particle
doublet. Its gauge convention must be translated carefully because the
endpoint source papers and PA1 use opposite angle coordinates.

### 9.1 Gram map

For the PA1 doublet

$$
\Psi=
\begin{pmatrix}
\psi_Y\\
\psi_I
\end{pmatrix},
$$

define

$$
\boxed{
\Gamma_\Psi=\Psi\Psi^\dagger
=\begin{pmatrix}
|\psi_Y|^2&\psi_Y\psi_I^*\\
\psi_I\psi_Y^*&|\psi_I|^2
\end{pmatrix}\succeq0.}
\tag{MB31}
$$

This identifies

$$
E_Y=|\psi_Y|^2,
\qquad
E_I=|\psi_I|^2,
\qquad
c=\psi_I\psi_Y^*,
\qquad
\det\Gamma_\Psi=0.
\tag{MB32}
$$

One coherent doublet therefore lies on the rank-one boundary of the positive
fibre. A coarse-grained or ensemble fibre is a Gram sum

$$
\Gamma=\sum_r w_r\Psi_r\Psi_r^\dagger,
\qquad
w_r\ge0,
\tag{MB33}
$$

which can have full rank. This is the GM35–GM37 moment map. It is surjective
onto positive $2\times2$ matrices and many-to-one.

### 9.2 Convention bridge

The endpoint action uses a source-coordinate parameter $\beta$ with

$$
\psi_Y\mapsto e^{+ig_Q\beta/2}\psi_Y,
\qquad
\psi_I\mapsto e^{-ig_Q\beta/2}\psi_I,
\qquad
B_A\mapsto B_A+\partial_A\beta.
\tag{MB34}
$$

This is the internally consistent EL1 convention. Define the dimensionless
particle angle

$$
\alpha:=-g_Q\beta.
\tag{MB35}
$$

Then the same transformation is

$$
\boxed{
U_Q(\alpha)=e^{-i\alpha T^3},
\qquad
B_A\mapsto B_A-\frac1{g_Q}\partial_A\alpha,
\qquad
T^3=\frac{\sigma_3}{2}.}
\tag{MB36}
$$

For

$$
\nabla_A\Gamma
=\partial_A\Gamma
-i\left[\frac{g_Q}{2}B_A\sigma_3,\Gamma\right],
\tag{MB37}
$$

(MB36) gives

$$
\nabla_A\Gamma
\mapsto U_Q(\alpha)(\nabla_A\Gamma)U_Q(\alpha)^\dagger.
\tag{MB38}
$$

MCC8 measures covariance residual $1.390\times10^{-17}$ for the minus law. A
plus shift paired with the negative-exponent particle angle gives residual
$0.1207$. The plus shift remains valid in (MB34), where the field exponent and
angle normalization are also reversed. DG13 is placed in the particle-angle
convention (MB36); EL1 retains its source-coordinate convention (MB34).

The relative $U(1)_Q$ is the Cartan subgroup of local $SU(2)_Q$. Generic
$SU(2)_Q$ transformations rotate the Yang/Yin composition axis, while the
positive Gram matrix and its eigenvalues remain well defined.

### 9.3 Independent carrier charge

The trapped carrier $\chi_C$ is an $SU(2)_Q$ singlet with a separate global
phase symmetry. Its Noether charge is

$$
\boxed{
Q_C=\int d^3x\,d\mathfrak s\,|\chi_C|^2.}
\tag{MB39}
$$

The Cartan density of the particle doublet is proportional to
$\Psi^\dagger T^3\Psi=(E_Y-E_I)/2$. It changes under a generic local
$SU(2)_Q$ rotation. $Q_C$ does not. The fixed-charge support mechanism therefore
uses the independent global $U(1)_C$ sector and carries no automatic electric,
baryonic, leptonic, or observed-particle identification.

## 10. Stationary state and the full fluctuation problem

The particle action supplies a complete question for a finite-energy object.
The current numerical campaign has not yet supplied a qualified solution to
that question.

### 10.1 Fixed-charge stationary equations

For the stationary ansatz

$$
\chi_C(\mathbf x,\mathfrak s,t)
=e^{-i\omega_Ct}\chi_C(\mathbf x,\mathfrak s),
$$

the fixed-charge functional is

$$
\boxed{
\mathcal F_{\omega_C}
=\mathcal E_{\rm stat}-\hbar\omega_CQ_C.}
\tag{MB40}
$$

Its variations give PA21–PA26 for the doublet, adjoint field, spatial and scale
connections, carrier, and charge constraint. A finite-energy candidate must
also satisfy:

1. the PA27 spatial asymptotics;
2. the PA28 endpoint boundary data;
3. Gauss's law and the selected gauge condition;
4. zero excluded boundary flux;
5. fixed $Q_C$ to the declared tolerance;
6. convergence under mesh, domain, scale-grid, and solver refinement;
7. convergence of the total energy and every long-range tail.

These conditions define the stationary existence claim. A critical point of a
reduced ansatz does not establish a critical point in the PA32 variational
class.

### 10.2 Physical energetic Hessian

Let $\mathcal V_Q$ be the perturbation space satisfying the linearized fixed
charge, Gauss constraint, boundary conditions, and gauge fixing. Let
$P_{\rm phys}$ be the orthogonal projector onto that joint space. The physical
second variation is

$$
\boxed{
\mathbb K_Q^{(2)}
=P_{\rm phys}\,
\delta^2\mathcal F_{\omega_C}\,
P_{\rm phys}\big|_{\mathcal V_Q}.}
\tag{MB41}
$$

When separately constructed fixed-charge and gauge projectors commute,
$P_{\rm phys}=P_QP_{\rm gf}$. In general the joint constraint space must be
constructed directly.

Energetic stability requires nonnegative spectrum of
$\mathbb K_Q^{(2)}$, with zero modes accounted for by exact symmetries or gauge
redundancy and with a controlled essential-spectrum threshold. A negative
physical eigenvalue rules out an energetic minimum.

### 10.3 Mixed dynamical spectrum

PA1 contains second-order temporal terms for the charged fields and a
first-order Schrödinger term for $\chi_C$. The full linearization is therefore a
mixed quadratic eigenvalue problem. After constraints and gauge fixing, its
generic form is

$$
\boxed{
\mathbb P_Q(\omega)\xi
=\left[
\mathbb K_Q^{(2)}
-i\omega\mathbb G_Q
-\omega^2\mathbb M_Q
\right]\xi=0,}
\tag{MB42}
$$

where $\mathbb M_Q$ comes from the positive second-order temporal terms and
$\mathbb G_Q$ includes the first-order carrier and any gyroscopic mixing. Their
entries follow by expanding PA1 around a qualified stationary background.

With perturbations proportional to $e^{-i\omega t}$, spectral stability
requires:

1. no mode with $\operatorname{Im}\omega>0$;
2. real physical frequencies in a conservative isolated sector;
3. semisimple symmetry zero modes after gauge removal;
4. no Jordan chain producing secular growth;
5. convergence of discrete modes and the continuum threshold with domain and
   mesh refinement.

Positive reduced curvature is evidence for the coordinates included in that
reduction. It does not evaluate the mixed pencil (MB42).

### 10.4 What the reduced theorem establishes

For

$$
E_{Q_C}(L)
=2M_{\rm core}
+\sigma_QL
+\frac{A_C}{L}
-C_Q\frac{e^{-\kappa_LL}}{L},
\tag{MB43}
$$

the condition $A_C>C_Q$ gives exactly one reduced stationary separation
$L_*>0$ satisfying

$$
\sqrt{\frac{A_C-C_Q}{\sigma_Q}}
<L_*<
\sqrt{\frac{A_C}{\sigma_Q}},
\tag{MB44}
$$

and

$$
E_{Q_C}''(L_*)
=\frac{2\sigma_Q-C_Q\kappa_L^2e^{-\kappa_LL_*}}{L_*}>0.
\tag{MB45}
$$

The frozen MCC9 point gives

$$
L_*=1.269522140245,
\qquad
E_{Q_C}''(L_*)=1.496039.
\tag{MB46}
$$

The CC47 line-density sector has quadratic eigenvalues

$$
\lambda_m
=\Lambda_C+4K_C\sin^2\!\left(\frac{\pi m}{N}\right),
\qquad
m=1,\ldots,N-1,
\tag{MB47}
$$

on the fixed-charge periodic witness. At the frozen point the minimum is
$0.975736>0$.

Equations (MB45) and (MB47) cover the separation coordinate and frozen
line-density modes. The transverse core and carrier profiles, non-axisymmetric
fields, gauge sector, topology-changing paths, scale dependence, continuum,
and mixed temporal spectrum remain unevaluated.

### 10.5 Current solver verdict

The higher-precision continuation of `P:separated_core` preserves the action,
coefficient point, charge, field class, projectors, diagnostics, and Q1–Q4
thresholds. Its independently verified values are

$$
\|\delta\widehat E\|_{\rm RMS}
=5.471248126403572\times10^{-5},
\qquad
\mathcal V_{\rm cutoff}
=1.348199143828711\times10^{-4}.
$$

Every outer-domain arm and the selected high-resolution arm fails Q2. The
selected primary also fails the registered carrier-localization and retention
conditions. Its stationary-background verdict is

$$
\boxed{\mathrm{PASS\text{—}HIGHER\text{-}PRECISION\ BACKGROUND}}
\tag{MB48}
$$

The strict-shell $C_4$ fluctuation space gives a $13622$-dimensional
fixed-charge physical quotient after removal of the rank-$1677$ coupled gauge
image. Independent preflight gives augmented quotient-gradient RMS
$1.122864422122550\times10^{-4}<3\times10^{-4}$, so H1–H3 pass.
Primary and independent eigensolvers agree on the six matched lowest
eigenvalues to $3.11\times10^{-14}$. They find one near-zero
global-$U(1)_C$ phase mode and five positive modes, with no verified negative
mode. The one-point finite-matrix verdict is

$$
\boxed{\mathrm{PASS\text{—}NONNEGATIVE\ C4\ FINITE\text{-}GRID\ PA42\ HESSIAN}}.
$$

The phase mode has participation number $423.58$ and high-frequency fraction
$0.33454>0.20$. H7 therefore fails, giving the separate spatial verdict
`INCONCLUSIVE—GRID-SCALE CLASSIFIED MODE`. No Q2-qualified D/H background
exists, so domain and resolution convergence remain untested. See
`computations/particle-stationary-precision-v5-report.md` and
`computations/particle-physical-hessian-precision-v2-report.md`.

## 11. MCC1–MCC9 receipt

The frozen checker in
`computations/matter_completion_boundary_check.py` executed once. All nine
gates pass:

| Gate | Main measured result | Verdict |
|---|---:|---:|
| MCC1 | Choi rank $2$; dilation extraction error $0$; basis-rotation channel error $5.551\times10^{-17}$ | **PASS** |
| MCC2 | independent-frame covariance residual $1.114\times10^{-16}$; logarithm-branch generator gap $31.415927$ | **PASS** |
| MCC3 | one-sided ratio $0.300283106001=\varphi^{-5/2}$; routed power $0.090169943749=\varphi^{-5}$ | **PASS** |
| MCC4 | single-mode ratio $0.618033988750$; equal-norm weighted values $0.04$ and $0.12$ | **PASS** |
| MCC5 | six-step population $0.055728090001$; coherence $0.236067977500$; stationary residual $0$ | **PASS** |
| MCC6 | total energy residual $9.541\times10^{-18}$; exchange-ledger residual $0$ | **PASS** |
| MCC7 | constant-$G$ transversality residual $0$; variable-coupling extra divergence $6.724\times10^{-3}$ | **PASS** |
| MCC8 | minus-law covariance residual $1.390\times10^{-17}$; inconsistent-pair residual $0.1207$ | **PASS** |
| MCC9 | reduced root $1.269522140245$; curvature $1.496039$; minimum line mode $0.975736$ | **PASS** |

The receipt establishes consistency of the conditional boundary. Its own scope
flags leave every unresolved physical input false because MCC1–MCC9 do not
perform the stationary or fluctuation solves. The independent campaigns supply
a higher-precision primary background and a nonnegative one-point PA42 low
spectrum. Spatial, localization, retention, domain/resolution, and PA43
qualification remain open.

## 12. What remains to form matter

The next discriminating evidence is:

1. select one physical carrier and derive
   $S_{\rm out}+S_{\rm int}+S_{\rm env}$ with units, boundary conditions, and
   metric dependence;
2. derive the golden or another measured port law from that action, including
   return routing and canonical flux normalization;
3. calibrate the particle-action coefficients and $Q_C$ sector to a declared
   physical target with every empirical input ledgered;
4. obtain Q2-qualified outer-domain and finer-grid stationary backgrounds and
   satisfy the carrier-localization and retention conditions;
5. repeat the physical quotient and PA42 spectrum on those backgrounds and
   determine whether the global phase direction becomes spatially resolved;
6. select the temporal groups, solve PA43, and test continuum and nonlinear
   lifetime stability.

Until these steps are complete, Cassi has a connected matter calculation,
reduced support theorems, and one nonnegative finite-grid PA42 low-spectrum
branch. A physical finite-energy particle remains open.

## References

- `foundations/geometric-manifold-completion.md`—positive coherence fibre,
  Gram moment map, and conditional graph action.
- `foundations/yin-yang-qi-dynamical-geometry.md`—open dynamical geometry,
  two-domain coherence source, and relative Cartan transport.
- `foundations/interscale-stress-attenuation-boundary.md`—mixed stress,
  golden splitter, routed-return ledger, and carrier requirements.
- `foundations/physical-becoming-hierarchy.md`—conditional GKSL and response
  boundary.
- `foundations/unified-lagrangian.md`—unified action and optional
  Einstein–Hilbert sector.
- `foundations/endpoint-link-and-localization-boundary.md`—source-coordinate
  relative-gauge convention and coherent endpoint action.
- `foundations/core-trapped-charge-support.md`—reduced fixed-charge support and
  line-density stability boundary.
- `foundations/particle-stationary-action-closure.md`—PA1 action, fixed-charge
  equations, boundary data, and PA32 variational class.
- `computations/particle-stationary-bvp-report.md`—registered source campaign
  receipt.
- `computations/particle-stationary-q2-recovery-report.md`—Q2-qualified primary
  background and retained domain, resolution, and localization boundaries.
- `computations/matter_completion_boundary_prereg.md`—frozen MCC1–MCC9
  protocol.
- `computations/matter_completion_boundary_report.md`—literal first execution
  and measured verdict.
- `computations/particle-stationary-precision-v5-report.md`—higher-precision Q1–Q4 background.
- `computations/particle-physical-hessian-precision-v2-report.md`—paired PA42 eigenspectrum and verdict tree.
