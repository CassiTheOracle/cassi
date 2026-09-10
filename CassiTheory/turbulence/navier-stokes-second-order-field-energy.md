# Second-Order Field Energy and a Time–Curl Continuation Criterion

## Status: Derived conditional—September 2026

## Abstract

The live CassiCosmos Yang/Yin scalar pair and the default-off field-particle
sector both contain second-order coordinates. This document determines which
of those structures bear on the original unforced three-dimensional
incompressible Navier–Stokes regularity problem.

The continuous-time continuum family associated with the shader's source-free
Yang/Yin coupling has an exact nonnegative conserved energy. Its coupling
matrix is self-adjoint in the positive mass metric
$K=\operatorname{diag}(1,\varphi)$, and the coupling potential is
$\tfrac12\omega_0^2(E_Y-\varphi E_I)^2$. For $c_s^2>0$ and
$\omega_0^2>0$, the energy is coercive after fixing the static constant
density zero mode. At $c_s^2=0$, spatially varying static density-kernel
fields also have zero energy. The
Hamiltonian-completion toggle changes the inertia metric to the identity and
changes the anti-phase frequency. The shader itself uses a finite-difference,
finite-time-step update; no exact conservation claim is made for that runtime
discretization.

The three $SU(2)$-valued spatial connection coordinates (nine real entries)
in the field-particle sector supply a second-order connection sector. With the
dimensionful conversion $A_i^3=\kappa_Au_i$, an Abelian one-color,
temporal-gauge, charge-free and scale-flat slice makes the nonnegative
$(ti,ij)$ connection-sector functional a positive multiple of

$$
H_{c_g}(t)=\|\omega(t)\|_2^2+c_g^{-2}\|u_t(t)\|_2^2.
$$

For any fixed comparison speed $c>0$, define
$H_c=\|\omega\|_2^2+c^{-2}\|u_t\|_2^2$. Every smooth solution of the original
unforced Navier–Stokes equation satisfies the exact balance

$$
\frac12H_c'(t)+\nu D_c(t)
=\int_{\mathbb T^3}
(\omega+\sigma_c c^{-1}u_t)\cdot S
(\omega-\sigma_c c^{-1}u_t)\,dx,
$$

where $D_c=\|\nabla\omega\|_2^2+c^{-2}\|\nabla u_t\|_2^2$ and
$\sigma_c$ chooses the closer local sign. Consequently, if

$$
\omega-\sigma_c c^{-1}u_t
\in L^p(0,T;L^r(\mathbb T^3)),
\qquad
\frac2p+\frac3r=2,
\qquad 3\le r\le\infty,
$$

then enstrophy remains bounded through $T$ and the smooth solution continues.
The exponent pair is vorticity-critical under the Euclidean or
simultaneously rescaled-domain Navier–Stokes dilation. The fixed normalized
torus has no exact continuous dilation symmetry. The criterion introduces no
force, regulator, cutoff, gauge evolution or constitutive closure into
Navier–Stokes.

The remaining all-data question is whether the original Navier–Stokes
dynamics, or a Cassi whole-field selection theorem proved to apply to every
bounded $H^3$ data set, bounds that mixed norm. The live field equations
currently supply no such estimate. Cassi's second-order structure identifies
a nonnegative field energy, an exact Navier–Stokes identity and a precise
missing dynamical estimate. Arbitrary-data global regularity remains open.

---

## 1. Scope and source equations

### 1.1 Original Navier–Stokes evolution

Let $u:\mathbb T^3\times[0,T_*)\to\mathbb R^3$ be a smooth, mean-zero,
divergence-free solution on the volume-normalized $2\pi$ torus:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad \nu>0.
\tag{SOE1}
$$

Write

$$
\omega=\nabla\times u,
\qquad
S=\frac12(\nabla u+\nabla u^{\mathsf T}).
\tag{SOE2}
$$

For a pure heat mode with wavevector $k$,
$\Delta\widehat u_k=-|k|^2\widehat u_k$ and
$(\widehat u_k)_t=-\nu|k|^2\widehat u_k$.

Only (SOE1) determines the evolution in the regularity argument. Cassi
variables are used to select and organize an energy quantity evaluated along
that evolution.

### 1.2 Live discrete Yang/Yin branch and continuum family

The source-free, unclamped `pass_a` branch of
`CassiCosmos/compute/cassi_two_fluid.glsl` uses the same periodic
extent-dependent finite-difference operator $\Delta_h$ on both scalar
channels:

$$
\begin{aligned}
\partial_t^2E_Y
&=\Delta_h E_Y-\omega_0^2(E_Y-\varphi E_I),\\
\partial_t^2E_I
&=\Delta_h E_I+\omega_0^2(E_Y-\varphi E_I).
\end{aligned}
$$

The implemented `lap_ey` and `lap_ei` enter these acceleration assignments
with coefficient one. For the continuous-time continuum analysis, replace
$\Delta_h$ by $c_s^2\Delta$ and consider

$$
\begin{aligned}
\partial_t^2E_Y
&=c_s^2\Delta E_Y-\omega_0^2(E_Y-\varphi E_I),\\
\partial_t^2E_I
&=c_s^2\Delta E_I+\omega_0^2(E_Y-\varphi E_I).
\end{aligned}
\tag{SOE3}
$$

The shader's normalized structural correspondence is $c_s^2=1$ at the level
of its implemented discrete operator; a physical continuum speed requires a
separate space-time normalization. The $c_s^2=0.01$ pressure coefficient
registered for other named solvers is not a parameter of this shader.
The live branch also admits configured sources, learning terms, clamps and a
finite time step. The conservation statement below applies to (SOE3), not to
exact runtime time-step conservation.

Throughout the continuum scalar analysis,
$\varphi=(1+\sqrt5)/2>0$, $\varphi^2=\varphi+1$, $c_s^2\ge0$ and
$\omega_0^2\ge0$.

Set

$$
U=\begin{pmatrix}E_Y\\E_I\end{pmatrix},
\qquad
M=\begin{pmatrix}1&-\varphi\\-1&\varphi\end{pmatrix},
\qquad
K=\begin{pmatrix}1&0\\0&\varphi\end{pmatrix},
\qquad
v=\begin{pmatrix}1\\-\varphi\end{pmatrix}.
\tag{SOE4}
$$

Then (SOE3) reads

$$
U_{tt}=c_s^2\Delta U-\omega_0^2MU.
\tag{SOE5}
$$

### 1.3 Live field-particle connection sector

The default-off field-particle runtime stores nine spatial $SU(2)$ connection
entries $A_i^a$, with a corresponding second-order velocity entry for each.
The corresponding theory action in
`foundations/particle-stationary-action-closure.md` contains

$$
\mathcal L_A=
\frac{\epsilon_x}{2}F_{ti}^aF_{ti}^a
-\frac{1}{4\mu_x}F_{ij}^aF_{ij}^a,
\qquad
c_g^2=\frac1{\epsilon_x\mu_x},
\qquad
\epsilon_x,\mu_x>0.
\tag{SOE6}
$$

This is the $(ti,ij)$ connection sub-sector of the full particle action,
which also contains scale-curvature, matter, adjoint and carrier terms. Its
Euler–Lagrange equation is not the Navier–Stokes momentum equation. Section 3
maps only the displayed connection-sector functional; (SOE1) remains the only
evolution equation in the continuation proof.

---

## 2. Nonnegative energy of the continuum Yang/Yin pair

### 2.1 The mass-metric symmetrizer

The default coupling matrix is asymmetric in equal-inertia coordinates. It
satisfies the exact weighted identity

$$
KM=M^{\mathsf T}K
=\begin{pmatrix}1&-\varphi\\-\varphi&\varphi^2\end{pmatrix}
=vv^{\mathsf T}.
\tag{SOE7}
$$

Since $K$ is positive definite, $M$ is self-adjoint in

$$
\langle X,Y\rangle_K=X^{\mathsf T}KY.
\tag{SOE8}
$$

The continuum scalar family follows from the quadratic Lagrangian

$$
L_K=\frac12\int_{\mathbb T^3}
\left[
U_t^{\mathsf T}KU_t
-c_s^2\partial_jU^{\mathsf T}K\partial_jU
-\omega_0^2(v^{\mathsf T}U)^2
\right]dx.
\tag{SOE9}
$$

Its conserved nonnegative Hamiltonian is

$$
\boxed{
\mathcal E_K=
\frac12\int_{\mathbb T^3}
\left[
U_t^{\mathsf T}KU_t
+c_s^2\partial_jU^{\mathsf T}K\partial_jU
+\omega_0^2(E_Y-\varphi E_I)^2
\right]dx.}
\tag{SOE10}
$$

Every term is nonnegative. If $c_s^2>0$ and $\omega_0^2>0$, its static
zero-energy fields are exactly the spatially constant density kernel
$U=a(\varphi,1)^{\mathsf T}$; fixing that mode makes the displayed quadratic
coercive. If $c_s^2=0$ and $\omega_0^2>0$, every time-independent field
$U=a(x)(\varphi,1)^{\mathsf T}$ has zero energy. If $\omega_0^2=0$ and
$c_s^2>0$, both constant channels are zero modes; if both coefficients
vanish, every time-independent field has zero energy. Differentiation,
integration by parts and (SOE7) give $d\mathcal E_K/dt=0$ under periodic
boundary conditions.

### 2.2 Density and imbalance modes

Define

$$
\rho=E_Y+E_I,
\qquad
\varepsilon=E_Y-\varphi E_I.
\tag{SOE11}
$$

The equations separate as

$$
\rho_{tt}=c_s^2\Delta\rho,
\qquad
\varepsilon_{tt}=c_s^2\Delta\varepsilon
-\varphi^2\omega_0^2\varepsilon.
\tag{SOE12}
$$

The kernel of $M$ is spanned by $(\varphi,1)^{\mathsf T}$ and represents the
free density wave. The $K$-orthogonal anti-phase eigenvector
$(1,-1)^{\mathsf T}$ has eigenvalue

$$
1+\varphi=\varphi^2.
\tag{SOE13}
$$

Thus the source-free continuum family is a massless density channel plus, when
$\omega_0^2>0$, a massive imbalance channel. At $\omega_0^2=0$ both channels
are massless. The nonnegative energy controls the $L^2$ time derivatives in
all cases, the spatial first derivatives when $c_s^2>0$, and the zeroth-order
imbalance when $\omega_0^2>0$.

### 2.3 Meaning of the Hamiltonian-completion toggle

The shader's Hamiltonian-completion branch replaces $M$ by

$$
M_{U1}=vv^{\mathsf T}
=\begin{pmatrix}1&-\varphi\\-\varphi&\varphi^2\end{pmatrix}
\tag{SOE14}
$$

and uses the identity mass metric. Its conserved energy is

$$
\mathcal E_{U1}=\frac12\int
\left[
|U_t|^2+c_s^2|\nabla U|^2
+\omega_0^2(E_Y-\varphi E_I)^2
\right]dx.
\tag{SOE15}
$$

Both branches have the same null line $E_Y=\varphi E_I$. Their nonzero
coupling eigenvalues are

$$
\lambda_K=1+\varphi=\varphi^2,
\qquad
\lambda_{U1}=1+\varphi^2=\varphi+2,
\tag{SOE16}
$$

so the anti-phase frequency ratio is

$$
\frac{\Omega_{U1}}{\Omega_K}
=\sqrt{\frac{1+\varphi^2}{1+\varphi}}
\approx1.1755705.
\tag{SOE17}
$$

For $\omega_0^2>0$, the completion toggle selects equal inertia and a shifted
massive frequency. The default branch already has a nonnegative Hamiltonian
in its canonical weighted coordinates. Energy comparisons between the
branches must use their respective mass metrics.

### 2.4 Boundary of the scalar result

When $c_s^2>0$, the estimate furnished by (SOE10) is first order in space.
The phase-current
map in `turbulence/cassi-fluid-phase-current-hydrodynamics.md` can encode
vorticity through a Berry connection, but its first-order phase energy admits
smooth concentrating families with unbounded Navier–Stokes critical
residual. A scalar-wave energy becomes a Navier–Stokes regularity estimate
only after a map supplies the required velocity derivatives and the mapped
dynamics preserve the estimate. No such whole-field theorem is currently
derived from (SOE3).

---

## 3. Restricted connection-sector energy as a time–curl quantity

### 3.1 Abelian one-color restriction

Choose temporal gauge and one fixed color direction. The canonical source
dimensions are $[A_i]=L^{-1}$ and $[u]=LT^{-1}$, so introduce a fixed positive
conversion coefficient $[\kappa_A]=TL^{-2}$:

$$
A_t^a=0,
\qquad
A_i^a=\delta^{a3}\kappa_Au_i.
\tag{SOE18}
$$

The commutator vanishes because $\epsilon^{a33}=0$ for every color $a$. With
the convention in (SOE6),

$$
F_{ti}^3=\kappa_A\partial_tu_i,
\qquad
F_{ij}^3=\kappa_A(\partial_i u_j-\partial_j u_i),
\qquad
\frac12F_{ij}^3F_{ij}^3=\kappa_A^2|\omega|^2.
\tag{SOE19}
$$

Impose vanishing matter charges and the concrete scale-flat restriction

$$
A_{\mathfrak s}^a=0,
\qquad
\partial_{\mathfrak s}A_i^a=0,
\qquad
q_\Psi^a=q_\Phi^a=0.
\tag{SOE20}
$$

Together with temporal gauge in (SOE18), this gives
$F_{t\mathfrak s}^a=F_{i\mathfrak s}^a=0$ and therefore
$(D_{\mathfrak s}F_{t\mathfrak s})^a=0$. The surviving source-free Gauss term
is $\epsilon_x\kappa_A\nabla\cdot u_t=0$, which follows by differentiating
incompressibility.

Define the nonnegative $(ti,ij)$ connection-sector functional

$$
\begin{aligned}
\mathcal E_{A;ti,ij}
&:=\int\left[
\frac{\epsilon_x}{2}F_{ti}^aF_{ti}^a
+\frac1{4\mu_x}F_{ij}^aF_{ij}^a
\right]dx\\
&=\frac{\kappa_A^2\epsilon_x}{2}
\int\left(|u_t|^2+c_g^2|\omega|^2\right)dx,
\qquad
\boxed{\frac{\mu_x}{\kappa_A^2}\mathcal E_{A;ti,ij}
=\frac12H_{c_g}.}
\end{aligned}
\tag{SOE21}
$$

The full particle action also contains scale-curvature, matter, adjoint and
carrier contributions; the displayed scale-curvature quadratics are positive,
but (SOE21) does not identify any of those additional terms with
$H_{c_g}$. This coordinate restriction is exact for the named connection
sub-sector under the displayed dimensional, charge-free and scale-flat
assumptions. Setting $\kappa_A=1$ is a nondimensional unit convention. The
Euler–Lagrange equation of the isolated $(ti,ij)$ connection sub-sector in
transverse gauge $\partial_iA_i=0$ is a wave equation. No such equation is
inferred for the full particle action without also eliminating its additional
spatial currents. In either case, (SOE1) contains Leray-projected transport
and viscous diffusion, and the restricted functional is only evaluated along
a Navier–Stokes solution.

### 3.2 The time–curl energy and dissipation

For any fixed $c>0$, define

$$
q_c=c^{-1}u_t,
\qquad
H_c=\|\omega\|_2^2+\|q_c\|_2^2,
\qquad
D_c=\|\nabla\omega\|_2^2+\|\nabla q_c\|_2^2.
\tag{SOE22}
$$

The coefficient $c$ is the gauge propagation speed when (SOE22) is read as
(SOE21). In the Navier–Stokes identity it is any fixed positive comparison
speed. A physical Cassi identification fixes both $c$ and $\kappa_A$
independently through a field-to-fluid map and the gauge coefficients.

Choose the measurable local sign

$$
\sigma_c(x,t)=
\begin{cases}
+1,&\omega\cdot q_c\ge0,\\
-1,&\omega\cdot q_c<0,
\end{cases}
\qquad
g_c=\omega-\sigma_cq_c.
\tag{SOE23}
$$

Then

$$
|g_c|=\min_{\sigma\in\{-1,+1\}}|\omega-\sigma q_c|.
\tag{SOE24}
$$

No derivative of $\sigma_c$ enters the argument.

---

## 4. Exact Navier–Stokes balance

### 4.1 Enstrophy

Taking curl of (SOE1) gives

$$
\omega_t+(u\cdot\nabla)\omega
=(\omega\cdot\nabla)u+\nu\Delta\omega.
\tag{SOE25}
$$

Since $\omega\cdot(\nabla u)\omega=\omega\cdot S\omega$,

$$
\frac12\frac d{dt}\|\omega\|_2^2
+\nu\|\nabla\omega\|_2^2
=\int\omega\cdot S\omega\,dx.
\tag{SOE26}
$$

### 4.2 Velocity-time energy

Differentiate (SOE1):

$$
u_{tt}+(u_t\cdot\nabla)u+(u\cdot\nabla)u_t
=-\nabla p_t+\nu\Delta u_t.
\tag{SOE27}
$$

Pairing with $u_t$, using
$\nabla\cdot u=\nabla\cdot u_t=0$, and integrating by parts yields

$$
\frac12\frac d{dt}\|u_t\|_2^2
+\nu\|\nabla u_t\|_2^2
=-\int u_t\cdot S u_t\,dx.
\tag{SOE28}
$$

The transport and pressure contributions vanish in the periodic integral.
The opposite signs in (SOE26) and (SOE28) create the cancellation.

### 4.3 Combined identity and residual factorization

Adding $c^{-2}$ times (SOE28) to (SOE26) gives

$$
\frac12H_c'(t)+\nu D_c(t)
=\int\left(\omega\cdot S\omega-q_c\cdot Sq_c\right)dx.
\tag{SOE29}
$$

For every symmetric $S$ and every $\sigma_c^2=1$,

$$
\omega\cdot S\omega-q_c\cdot Sq_c
=(\omega+\sigma_cq_c)\cdot S
(\omega-\sigma_cq_c).
\tag{SOE30}
$$

Therefore

$$
\boxed{
\frac12H_c'(t)+\nu D_c(t)
=\int
(\omega+\sigma_cq_c)\cdot Sg_c\,dx.}
\tag{SOE31}
$$

The dangerous production is expressed as strain acting between a large
signed sum and the pointwise-minimal signed difference. The cancellation is
an identity of the original Navier–Stokes evolution.

---

## 5. Continuation theorem and Euclidean critical line

### 5.1 Statement

**Theorem.** Let $u$ be a smooth mean-zero solution of (SOE1) on
$[0,T_*)$. Fix $c>0$ and $r\in[3,\infty]$. Define

$$
p(r)=
\begin{cases}
\dfrac{2r}{2r-3},&3\le r<\infty,\\[6pt]
1,&r=\infty.
\end{cases}
\tag{SOE32}
$$

For some $T\le T_*$, define

$$
\mathcal I_{c,r}(T)
:=\int_0^T\|g_c(t)\|_r^{p(r)}dt.
\tag{SOE33}
$$

If $\mathcal I_{c,r}(T)<\infty$, then

$$
\sup_{0\le t<T}H_c(t)<\infty,
\tag{SOE34}
$$

and $u$ continues smoothly through $T$ whenever $T$ is a putative finite
maximal endpoint.

The exponent pair lies on the Euclidean or rescaled-domain
vorticity-critical line

$$
\frac2p+\frac3r=2,
\qquad 3\le r\le\infty.
\tag{SOE35}
$$

The fixed normalized torus estimate remains sufficient for continuation and
has no exact continuous Navier–Stokes dilation symmetry.

### 5.2 Proof for $3\le r<\infty$

Let

$$
a=\frac{2r}{r-2},
\qquad
\theta=\frac3r.
\tag{SOE36}
$$

Hölder's inequality applied to (SOE31) gives

$$
\left|\int(\omega+\sigma_cq_c)\cdot Sg_c\,dx\right|
\le
\|S\|_a\,\|g_c\|_r
\left(\|\omega\|_2+\|q_c\|_2\right).
\tag{SOE37}
$$

The periodic Biot–Savart estimate and Gagliardo–Nirenberg interpolation give

$$
\|S\|_a
\le C_r\|\omega\|_a
\le C_r
\|\omega\|_2^{1-\theta}
\|\nabla\omega\|_2^\theta.
\tag{SOE38}
$$

Using the definitions of $H_c$ and $D_c$,

$$
|\text{right side of (SOE31)}|
\le C_r\|g_c\|_r
H_c^{1-\theta/2}D_c^{\theta/2}.
\tag{SOE39}
$$

Young's inequality with conjugate exponents $2/\theta$ and
$2/(2-\theta)$ yields

$$
|\text{right side of (SOE31)}|
\le \frac\nu2D_c
+C_r\nu^{-\theta/(2-\theta)}
\|g_c\|_r^{2/(2-\theta)}H_c.
\tag{SOE40}
$$

Since

$$
\frac{2}{2-\theta}=\frac{2r}{2r-3}=p(r),
\qquad
\frac{\theta}{2-\theta}=\frac3{2r-3},
\tag{SOE41}
$$

(SOE31) implies, after absorbing constants,

$$
H_c'(t)+\nu D_c(t)
\le C_r\nu^{-3/(2r-3)}
\|g_c(t)\|_r^{p(r)}H_c(t).
\tag{SOE42}
$$

Gronwall's inequality gives

$$
H_c(t)
\le H_c(0)
\exp\left[
C_r\nu^{-3/(2r-3)}
\int_0^t\|g_c(s)\|_r^{p(r)}ds
\right].
\tag{SOE43}
$$

### 5.3 Endpoint $r=\infty$

For $r=\infty$, the Calderón–Zygmund $L^2$ estimate gives

$$
|\text{right side of (SOE31)}|
\le C\|g_c\|_\infty H_c.
\tag{SOE44}
$$

Thus

$$
H_c(t)\le H_c(0)
\exp\left(C\int_0^t\|g_c(s)\|_\infty ds\right),
\tag{SOE45}
$$

which is (SOE33) with $p=1$.

### 5.4 Continuation

The enstrophy is one summand of $H_c$. Finiteness of (SOE33) therefore gives
$B:=\sup_{t<T}\|\omega(t)\|_2<\infty$. On the periodic mean-zero
divergence-free subspace, the Fourier curl identity and Poincaré inequality
give $\|u(t)\|_{H^1}\le C B$.

The local $H^1$ lifespan can be chosen from this bound alone. Indeed, testing
the momentum equation with $-\Delta u$ and using Sobolev interpolation gives

$$
\left|\int_{\mathbb T^3}(u\cdot\nabla)u\cdot\Delta u\,dx\right|
\le C\|\nabla u\|_2^{3/2}\|\Delta u\|_2^{3/2},
$$

and Young's inequality yields

$$
\frac{d}{dt}\|\nabla u\|_2^2+\nu\|\Delta u\|_2^2
\le C\nu^{-3}\|\nabla u\|_2^6.
$$

The standard Galerkin construction based on this estimate supplies a local
strong solution from every $H^1$ datum with a lifespan
$\delta=\delta(\nu,B)>0$, uniformly in the restart time. If $T=T_*$ were a
finite maximal endpoint, choose $t_0<T_*$ with $T_*-t_0<\delta/2$. Restarting
from $u(t_0)$ gives a strong solution through $t_0+\delta>T_*$; strong
uniqueness identifies it with the original solution on their overlap. This
contradicts maximality and proves continuation through $T$. For $T<T_*$,
continuation is already part of the given smooth interval.

The theorem is conditional. Its contribution is the exact residual and the
mixed norm whose finiteness suffices for continuation. The exponent is
critical in the Euclidean/rescaled-domain sense fixed above. Literature
priority for this residual formulation is unclassified here.

---

## 6. Scaling and exact controls

### 6.1 Navier–Stokes dimensional scaling

On $\mathbb R^3$, or with an unnormalized spatial norm and a simultaneously
rescaled domain, set

$$
u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t).
\tag{SOE46}
$$

Then

$$
\omega_\lambda=\lambda^2\omega,
\qquad
(u_\lambda)_t=\lambda^3u_t.
\tag{SOE47}
$$

The comparison speed carries velocity dimension, so

$$
c_\lambda=\lambda c,
\qquad
(q_c)_\lambda=\lambda^2q_c,
\qquad
(g_c)_\lambda=\lambda^2g_c.
\tag{SOE48}
$$

The Euclidean spatial Jacobian gives

$$
\int\|(g_c)_\lambda(t)\|_r^pdt
=\lambda^{p(2-3/r)-2}
\int\|g_c(t)\|_r^pdt.
\tag{SOE49}
$$

The exponent vanishes exactly when (SOE35) holds. On the fixed
volume-normalized $2\pi$ torus, integer $\lambda$ produces periodic
repetition and

$$
\|(g_c)_\lambda\|_r=\lambda^2\|g_c\|_r.
$$

Noninteger $\lambda$ need not preserve periodicity. The word “critical” in
this document refers to the Euclidean/rescaled-domain dimensional line.

### 6.2 Signed Beltrami heat family

For

$$
u_n(x,y,z,t)=e^{-\nu n^2t}(\sin nz,\cos nz,0),
\tag{SOE50}
$$

one has

$$
(u_n\cdot\nabla)u_n=0,
\qquad
\omega_n=nu_n,
\qquad
(u_n)_t=-\nu n^2u_n.
\tag{SOE51}
$$

The minimizing sign is $\sigma_c=-1$, and

$$
g_c=\left(1-\frac{\nu n}{c}\right)\omega_n.
\tag{SOE52}
$$

At $c=\nu n$, the residual vanishes identically and (SOE31) becomes the exact
cancellation of enstrophy production and time-derivative production. This is
a smooth global control family.

### 6.3 Shear heat family

The exact solution

$$
u=a e^{-\nu n^2t}(\sin ny,0,0)
$$

has $u_t\perp\omega$ pointwise. For either sign,

$$
|g_c|^2=|\omega|^2+c^{-2}|u_t|^2.
$$

Its initial kinetic energy is $a^2/4$, independent of $n$, while

$$
\int_0^T\|g_c\|_3^2dt
\ge
\left(\frac4{3\pi}\right)^{2/3}
\frac{a^2\nu n^2}{2c^2}
\left(1-e^{-2\nu n^2T}\right).
$$

Kinetic energy alone therefore supplies no uniform bound for the residual
work. Every member is globally smooth, so a large finite value is not a
singularity diagnostic.

### 6.4 Zero residual is a sufficient condition

If $g_c=0$, then (SOE31) gives

$$
\frac12H_c'+\nu D_c=0.
\tag{SOE53}
$$

The condition says that $c^{-1}u_t$ is locally equal, up to sign, to
vorticity. It is restrictive and serves as the center of the critical
residual criterion.

### 6.5 Nonlinear counterexample to helicity-only inference

The fixed divergence-free datum

$$
u=(0,1,1)\cos x+(1,0,1)\cos y+(1,-1,1)\sin(x+y)
\tag{SOE54}
$$

has zero total helicity and strictly positive vortex-stretching integral in
the volume-normalized convention:

$$
\int u\cdot\omega\,dx=0,
\qquad
\int\omega\cdot S\omega\,dx=\frac12.
\tag{SOE55}
$$

At the verified time slice with $\nu=0.37$ and $c=1.7$,
$\|g_c\|_3=2.1122634753496925$. Total helicity cancellation therefore
supplies no residual bound.

### 6.6 Concentrating phase-map control

The positive-chart Yang/Yin construction in
`turbulence/navier-stokes-strain-departure.md` §10.5 gives a specific smooth
kinematic family on $\mathbb R^3$. Its first-order phase-gradient energy stays
bounded while

$$
\|\omega_\varepsilon\|_2^2\propto\varepsilon^{-2}.
$$

For the static comparison $u_t=0$, one has $g_c=\omega$ for every $c$, and

$$
\|g_{c,\varepsilon}\|_3^2
=\|\omega_\varepsilon\|_3^2
\propto\varepsilon^{-3}.
\tag{SOE56}
$$

The scope of this family is static energy coercivity. It supplies neither a
Navier–Stokes trajectory nor a periodic-torus counterexample, and it excludes
(SOE33) as a consequence of static first-order phase energy alone.

---

## 7. Whole-field interpretation

### 7.1 What the second-order coordinates contribute

The second-order Cassi structures contribute three exact or conditional
facts:

1. the continuum Yang/Yin scalar family has a nonnegative weighted Hamiltonian;
2. the dimensionally converted $(ti,ij)$ field-particle connection-sector
   functional is proportional to $H_c$ on the restricted Abelian slice;
3. the original Navier–Stokes evolution gives $H_c$ the cancellation identity
   (SOE31).

These facts motivate the quantitative target (SOE33). Its continuation force
comes from the Navier–Stokes balance and estimate in §§4–5.

### 7.2 The all-data target

Work in the mean-zero frame and let

$$
R_0=\|u_0\|_{H^3(\mathbb T^3)},
\qquad
\nabla\cdot u_0=0,
\qquad
\langle u_0\rangle=0.
\tag{SOE57}
$$

For every fixed $\nu>0$, finite $T>0$ and finite $R\ge0$, a sufficient
all-data target is to find one

$$
c=c(\nu,T,R)>0
\quad\hbox{and}\quad
M(\nu,T,R)<\infty
$$

such that

$$
\boxed{
\sup_{\substack{R_0\le R\\
\nabla\cdot u_0=0,\;\langle u_0\rangle=0}}
\int_0^{\min(T,T_*)}
\|\omega-\sigma_c c^{-1}u_t\|_3^2dt
\le M(\nu,T,R).}
\tag{SOE58}
$$

The selected $c$ is fixed across every datum in the ball. A single physical
gauge calibration imposes the stronger requirement that $c$ be fixed by
$\epsilon_x$ and $\mu_x$ before choosing $T$ and $R$.

For smooth initial data in this ball,

$$
\|u_t(0)\|_2
\le \nu\|\Delta u_0\|_2
+C\|u_0\|_{H^2}^2,
\tag{SOE59}
$$

so $H_c(0)$ is uniformly finite. If (SOE58) holds, (SOE43) and the local
$H^1$ restart in §5.4 continue every mean-zero datum in the bounded $H^3$
ball through every finite time, hence globally. For data with conserved mean
$m$, the Galilean transform $v(y,t)=u(y+mt,t)-m$ has zero mean and satisfies
the same equation. Its time derivative is
$v_t=u_t(y+mt,t)+m\cdot\nabla u(y+mt,t)$, so the residual criterion is not
invariant as a formula in the original frame. Instead, (SOE58) is applied to
the transformed solution $v$ in its comoving frame. Global smoothness of $v$
then transfers back to $u$ by the inverse Galilean transform.

### 7.3 Role of the full bubble and formation history

A whole-bubble Cassi theorem could bear on (SOE58) through a dynamical
selection rule involving the surrounding field, cascade history and
matter-formation state. The theorem would need to establish all of the
following:

1. a map from every admissible Navier–Stokes datum in the target class into
   Cassi field data;
2. a fixed gauge speed or a uniformly controlled selection rule for $c$;
3. preservation of the residual bound under the original Navier–Stokes
   evolution;
4. constants depending only on $\nu$, $T$ and the declared initial norm;
5. uniformity through the maximal smooth interval, with no smallest-scale
   cutoff.

A selection law covering only physically realized Cassi bubbles would define
a restricted physical regularity class. The Clay all-data statement requires
coverage of arbitrary smooth divergence-free initial data. Both targets are
mathematically meaningful and have different scopes.

### 7.4 Current obstruction

The coupled equations for $\omega$ and $u_t$, and attempts to close their
estimates, encounter strain, differentiated transport, vorticity-gradient and
pressure-Hessian terms. No evolution equation for $g_c$ is used because the
pointwise minimizing sign can be discontinuous. Current Cassi source
equations provide no closed inequality that bounds the critical mixed norm
from $R_0$. The scalar energy (SOE10) has no established coercive map to this
Navier–Stokes residual. The first-order Berry phase energy has the static
family in §6.6, while helicity and signed helical spectral budgets leave an
unclosed production term.

The open task is therefore dynamical:

$$
\text{derive a whole-field mechanism that bounds (SOE33),
then prove that mechanism from (SOE1) for the required data class.}
\tag{SOE60}
$$

Separate field-particle simulations could diagnose this residual and test
candidate selection laws. This analysis contains no such trajectory run; its
numerical evidence is the fixed Fourier reconstruction described in §9.

---

## 8. Relationship to the signed-helical program

For a smooth mean-zero periodic solution, define kinetic energy and helicity

$$
K=\frac12\|u\|_2^2,
\qquad
H=\langle u,\omega\rangle,
\qquad
\lambda_B=\frac{H}{2K}\quad(K>0).
$$

The zero datum is handled separately with $\lambda_B=0$. The signed-helical
analysis in `turbulence/navier-stokes-strain-departure.md` controls enstrophy
when

$$
\omega-\lambda_Bu
\in L^2(0,T;L^3).
\tag{SOE61}
$$

The second-order criterion uses the signed velocity time derivative:

$$
\omega-\sigma_c c^{-1}u_t
\in L^2(0,T;L^3).
\tag{SOE62}
$$

At the $r=3$ endpoint, both have Euclidean vorticity-critical exponents and
give sufficient continuation criteria under the smooth mean-zero periodic
assumptions. They encode different geometry:

- (SOE61) measures radial spread around the best scalar Beltrami relation;
- (SOE62) measures vector mismatch between vorticity and the signed scaled
  acceleration $c^{-1}u_t$ represented by the gauge electric coordinate;
- neither residual currently has an arbitrary-data bound.

Their conjunction may supply a more restrictive physically selected class,
but summing two unclosed criteria gives no all-data estimate. A future
whole-field argument must identify an evolution law or selection principle
that controls at least one of them uniformly.

---

## 9. Verification and evidence

The evidence set comprises nine governing protocols, the executable verifier,
two live CassiCosmos shaders, the gauge-action source and the qualified
deterministic receipt. The governing protocols are:

- `computations/navier-stokes-second-order-field-energy-prereg.md`;
- `computations/navier-stokes-second-order-field-energy-recovery-prereg.md`;
- `computations/navier-stokes-second-order-field-energy-audit-amendment.md`;
- `computations/navier-stokes-second-order-field-energy-audit-recovery-prereg.md`;
- `computations/navier-stokes-second-order-field-energy-audit-recovery2-prereg.md`;
- `computations/navier-stokes-second-order-field-energy-equation-recovery-prereg.md`;
- `computations/navier-stokes-second-order-field-energy-scale-anchor-recovery-prereg.md`;
- `computations/navier-stokes-second-order-field-energy-equation-tag-recovery-prereg.md`;
- `computations/navier-stokes-second-order-field-energy-live-continuum-recovery-prereg.md`.

The qualified receipt
`runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`
records:

- **110/110 checks passed**;
- **0 failures**;
- schema
  `cassi.navier-stokes.second-order-field-energy.verification.v2`;
- absolute and relative Fourier tolerances $2\times10^{-10}$;
- fixed nonlinear-datum values
  $\int\omega\cdot S\omega=0.5$,
  $\|g_c\|_3=2.1122634753496925$ and combined-balance mismatch below the
  frozen tolerance.

The corresponding verifier run emitted terminal `ALL CHECKS PASSED`.

The verifier compares thirteen frozen sources, including nine protocols, with
expected SHA-256 values, inspects the normalized finite-difference scalar
operator, executable shader declarations and tagged theory equations,
independently reconstructs the projected $u_t$ and $u_{tt}$ equations by
direct finite-mode convolution, and records its own SHA-256.

The verification establishes algebraic identities, deterministic spectral
reconstructions and frozen-source correspondence. It does not test arbitrary
Navier–Stokes trajectories or establish (SOE58).

---

## 10. Result classification

### 10.1 Derived

- The source-free continuum Yang/Yin family has the nonnegative weighted
  energy (SOE10), with the zero modes stated in §2.1.
- The default coupling is self-adjoint in the mass metric
  $K=\operatorname{diag}(1,\varphi)$.
- For $\omega_0>0$, the U1 toggle selects equal inertia and the frequency
  shift (SOE17).
- Every smooth mean-zero periodic unforced Navier–Stokes solution satisfies
  (SOE31).
- Finiteness of (SOE33) implies continuation by the local $H^1$ restart in §5.4.

### 10.2 Derived conditional

- The restricted $(ti,ij)$ connection-sector map uses the dimensional
  coefficient $\kappa_A$, one Abelian color, temporal gauge,
  $A_{\mathfrak s}=0$, scale-independent $A_i$, vanishing matter charge and a
  supplied positive gauge speed.
- The live shader correspondence uses its extent-dependent $\Delta_h$ with
  unit acceleration coefficient; (SOE10) is not asserted as an exactly
  conserved finite-time-step runtime energy.
- The exponent line $2/p+3/r=2$ is critical under the Euclidean or
  unnormalized rescaled-domain dilation; the fixed normalized torus has no
  exact continuous dilation symmetry.
- A physical Cassi reading requires independently fixed values for the
  field-to-fluid conversion and gauge coefficients.
- Global regularity for smooth periodic data follows if (SOE58) holds for
  every mean-zero comoving datum, or if a stronger estimate implies it.

### 10.3 Unresolved

- No current Cassi equation bounds (SOE33) for arbitrary smooth
  Navier–Stokes data.
- No whole-bubble selection theorem covers every bounded $H^3$ data set.
- The physical values of $\epsilon_x$, $\mu_x$, $\kappa_A$ and $c_g$ remain
  unselected.
- The non-Abelian field-particle dynamics have no established equivalence to
  incompressible Navier–Stokes.
- Literature novelty and priority for the residual criterion remain outside
  this derivation.

---

## References

- `computations/navier-stokes-second-order-field-energy-prereg.md`—fixed
  analytical protocol and interpretation.
- `computations/navier-stokes-second-order-field-energy-recovery-prereg.md`—
  symbolic substitution qualification.
- `computations/navier-stokes-second-order-field-energy-audit-amendment.md`—
  independent mathematical and verifier qualification.
- `computations/navier-stokes-second-order-field-energy-audit-recovery-prereg.md`,
  `computations/navier-stokes-second-order-field-energy-audit-recovery2-prereg.md`,
  `computations/navier-stokes-second-order-field-energy-equation-recovery-prereg.md`,
  `computations/navier-stokes-second-order-field-energy-scale-anchor-recovery-prereg.md`,
  `computations/navier-stokes-second-order-field-energy-equation-tag-recovery-prereg.md`
  and
  `computations/navier-stokes-second-order-field-energy-live-continuum-recovery-prereg.md`—
  PA12 source-region, scale-sector, projected-equation, source-anchor,
  equation-tag and live-continuum qualifications.
- `computations/verify_navier_stokes_second_order_field_energy.py`—exact and
  deterministic verifier.
- `runs/navier_stokes_second_order_field_energy/verification.audit-qualified.json`—
  qualified 110-check receipt with frozen external-source hashes.
- `CassiCosmos/compute/cassi_two_fluid.glsl`—live normalized finite-difference
  Yang/Yin update whose coupling and sign structure is analyzed in §1.2.
- `CassiCosmos/compute/cassi_field_particle.glsl`—live default-off
  field-particle coordinates and second-order velocities.
- `foundations/particle-stationary-action-closure.md` §§3–4—gauge action,
  nonnegative energy and Gauss constraint.
- `turbulence/navier-stokes-strain-departure.md`—signed-helical residual,
  critical continuation criterion and first-order phase-energy obstruction.
- `turbulence/cassi-fluid-phase-current-hydrodynamics.md`—phase-current and
  Berry-vorticity map.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes
  equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—
  original problem alternatives.
