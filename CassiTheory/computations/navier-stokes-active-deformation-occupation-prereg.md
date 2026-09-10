# Active Deformation Occupation for Navier–Stokes: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule tests a vorticity-seeded second moment of the Constantin–Iyer stochastic Cauchy field. The moment satisfies a closed deterministic matrix advection–diffusion equation, dominates the Euclidean enstrophy by covariance positivity, and has an exact label-space representation as an exponential strain occupation along stochastic trajectories seeded by the initial vorticity. Its integrated growth depends only on the anisotropic part of the seeded orientation distribution. The controls separate this active quantity from full deformation, identify the scale-critical cumulative dose required of a cascade argument, and test the obstruction to deriving that dose from the energy-class strain norm alone. The execution is symbolic and finite-dimensional. Arbitrary-data regularity requires a separate uniform bound on the active cumulative dose.

## 1. Equation, domain, and conventions

Work with a smooth mean-zero solution of the unforced incompressible Navier–Stokes equation on the normalized $2\pi$ torus:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad
\nu>0.
\tag{ADO1}
$$

Put

$$
\omega=\nabla\times u,
\qquad
L=\nabla u,
\qquad
S=\frac12(L+L^{\mathsf T}),
\qquad
\mathcal L_u=\partial_t+u\cdot\nabla-\nu\Delta.
\tag{ADO2}
$$

The gradient convention is $L_{ij}=\partial_j u_i$, so

$$
\mathcal L_u\omega=L\omega,
\qquad
\frac12\frac d{dt}W+\nu D=P,
\tag{ADO3}
$$

where

$$
W=\|\omega\|_2^2,
\qquad
D=\|\nabla\omega\|_2^2,
\qquad
P=\int_{\mathbb T^3}\omega\cdot S\omega\,dx.
\tag{ADO4}
$$

All spatial integrals use normalized volume. Stochastic identities are restricted to compact intervals $[0,\tau]\subset[0,T_*)$ on which the periodic solution and initial datum are smooth. These hypotheses supply a smooth volume-preserving stochastic flow, finite deformation moments, differentiation under expectation, Fubini, and mean-zero Itô integrals.

Every normalized identity, probability measure, and Rayleigh quotient below is
stated for $W(0)>0$. A smooth mean-zero divergence-free datum with $W(0)=0$
is the zero solution and continues trivially; set $\Gamma_M=0$ for that
separate case when reading the all-data estimate (ADO18).

## 2. Vorticity-seeded stochastic covariance

Let $X_t(a)$ be the Constantin–Iyer stochastic flow and $\mathscr A_t=X_t^{-1}$ its spatial inverse:

$$
dX_t(a)=u(X_t(a),t)\,dt+\sqrt{2\nu}\,dB_t,
\qquad X_0(a)=a.
\tag{ADO5}
$$

Define the Eulerian forward deformation, sampled initial vorticity, and random Cauchy field

$$
F_t(x)=\bigl(\nabla_aX_t\bigr)(\mathscr A_t(x)),
\qquad
V_t(x)=\omega_0(\mathscr A_t(x)),
\qquad
Y_t(x)=F_t(x)V_t(x).
\tag{ADO6}
$$

Every realization preserves volume, $\det F_t=1$, and the stochastic Cauchy formula is

$$
\boxed{\omega(x,t)=\mathbb E[Y_t(x)].}
\tag{ADO7}
$$

The Eulerian Cauchy field satisfies the common-noise Itô equation

$$
dY+\bigl(u\cdot\nabla Y-LY\bigr)dt
-\nu\Delta Y\,dt
+\sqrt{2\nu}\sum_k\partial_kY\,dB_t^k=0.
\tag{ADO8}
$$

Define the vorticity-seeded second moment and centred covariance

$$
M=\mathbb E[YY^{\mathsf T}],
\qquad
R=M-\omega\omega^{\mathsf T}.
\tag{ADO9}
$$

The common translational noise closes the second-moment equation:

$$
\boxed{
\mathcal L_uM=LM+ML^{\mathsf T},
\qquad
M(x,0)=\omega_0(x)\omega_0(x)^{\mathsf T}.}
\tag{ADO10}
$$

The product rule for $\omega\omega^{\mathsf T}$ then gives

$$
\boxed{
\mathcal L_uR=LR+RL^{\mathsf T}
+2\nu\sum_k(\partial_k\omega)(\partial_k\omega)^{\mathsf T},
\qquad R(x,0)=0.}
\tag{ADO11}
$$

At every $(x,t)$,

$$
M-\omega\omega^{\mathsf T}
=\mathbb E\bigl[(Y-\mathbb EY)(Y-\mathbb EY)^{\mathsf T}\bigr]
\succeq0.
\tag{ADO12}
$$

Thus the seeded moment retains both the squared mean Cauchy field and its stochastic spread.

## 3. Active envelope and continuation reduction

Define

$$
\mathcal E_M(t)=\int_{\mathbb T^3}\operatorname{tr}M(x,t)\,dx.
\tag{ADO13}
$$

Taking the trace of (ADO12) and integrating gives the pointwise and global bounds

$$
|\omega|^2\le\operatorname{tr}M,
\qquad
\boxed{W(t)\le\mathcal E_M(t).}
\tag{ADO14}
$$

Periodic integration of (ADO10), incompressibility, and symmetry of $M$ give

$$
\boxed{
\mathcal E_M'(t)=2\int_{\mathbb T^3}S:M\,dx.}
\tag{ADO15}
$$

For a nonzero datum, covariance positivity gives $\mathcal E_M>0$. Define the active seeded production rate

$$
\Gamma_M(t)=
\frac{\displaystyle\int_{\mathbb T^3}S:M\,dx}
{\displaystyle\mathcal E_M(t)}.
\tag{ADO16}
$$

Since $\mathcal E_M(0)=W(0)$,

$$
\boxed{
\frac{\mathcal E_M(t)}{W(0)}
=\exp\left(2\int_0^t\Gamma_M(s)\,ds\right)
\le
\exp\left(2\int_0^t(\Gamma_M(s))_+\,ds\right).}
\tag{ADO17}
$$

Consequently, with the zero solution treated by the convention above, the uniform all-data estimate

$$
\boxed{
\int_0^{\min(T,T_*)}(\Gamma_M(t))_+\,dt
\le B_M(\nu,T,R)<\infty}
\tag{ADO18}
$$

for every nonzero smooth mean-zero divergence-free datum with $\|u_0\|_{H^3}\le R$, together with the trivial zero datum, implies a uniform enstrophy bound through (ADO14)–(ADO17), hence continuation through $T$ by the periodic $H^1$ restart criterion. Finite-time loss of regularity forces $\mathcal E_M$ to diverge along an endpoint sequence and forces the positive cumulative dose in (ADO18) to diverge.

Under the Euclidean Navier–Stokes rescaling, the normalized moment $\mathcal E_M/W(0)$ and the integrated dose $\int\Gamma_Mdt$ have zero scaling exponent. The rescaling changes the period of a fixed torus. This records scale-critical dimensional behavior; the normalized torus has no corresponding continuous rescaling symmetry.

## 4. Orientation anisotropy and alignment

Write

$$
m=\operatorname{tr}M.
\tag{ADO19}
$$

Where $m>0$, define

$$
N=\frac M m,
\qquad
Q=N-\frac13I,
\qquad
\theta=\sqrt{\frac32}\,\|Q\|_{\mathrm F}.
\tag{ADO20}
$$

The matrix $N$ is positive semidefinite with trace one. If its eigenvalues are $p_i\ge0$ with $\sum_ip_i=1$, then

$$

\|Q\|_{\mathrm F}^2=\sum_ip_i^2-\frac13\le\frac23,
\qquad
0\le\theta\le1.
\tag{ADO21}
$$

Here and below, $|S|=\|S\|_{\mathrm F}$ and
$|Q|=\|Q\|_{\mathrm F}$.

Since $\operatorname{tr}S=0$,

$$
S:M=mS:Q.
\tag{ADO22}
$$

Where $|S|\theta>0$, put

$$
\chi=\frac{S:Q}{|S|\,|Q|}\in[-1,1],
\tag{ADO23}
$$

and set $\chi=0$ where $|S|\theta=0$. Equations (ADO16) and (ADO20)–(ADO23) give

$$
\boxed{
\Gamma_M(t)=
\sqrt{\frac23}\,
\frac{\displaystyle\int m\,|S|\,\theta\,\chi\,dx}
{\displaystyle\int m\,dx}.}
\tag{ADO24}
$$

Only anisotropic orientation mass aligned with strain contributes. An isotropic seeded moment, $M=(m/3)I$, has $\theta=0$ and zero instantaneous production for every trace-free strain.

## 5. Label-space occupation identity

For each realization, volume preservation and the change of variables $x=X_t(a)$ give

$$
\mathcal E_M(t)
=
\int_{\mathbb T^3}
\mathbb E\left|
\nabla_aX_t(a)\,\omega_0(a)
\right|^2da.
\tag{ADO25}
$$

For $\omega_0(a)\ne0$, define

$$
J_t(a)=\nabla_aX_t(a)\,\omega_0(a),
\qquad
n_t(a)=\frac{J_t(a)}{|J_t(a)|},
\qquad
n_0(a)=:\widehat\omega_0(a)=\frac{\omega_0(a)}{|\omega_0(a)|}.
\tag{ADO26}
$$

Along each stochastic trajectory,

$$
\frac d{dt}J_t=L(X_t,t)J_t,
\qquad
\frac d{dt}n_t=(I-n_tn_t^{\mathsf T})L(X_t,t)n_t,
\tag{ADO27}
$$

and

$$
\frac d{dt}\log|J_t|
=n_t^{\mathsf T}S(X_t,t)n_t
=: \sigma_t.
\tag{ADO28}
$$

Let $d\mu_0(a)=|\omega_0(a)|^2da/W(0)$. Then

$$
\boxed{
\frac{\mathcal E_M(t)}{W(0)}
=
\mathbb E_{\mu_0,B}
\exp\left(2\int_0^t\sigma_s\,ds\right).}
\tag{ADO29}
$$

This is an initial-data-conditioned strain occupation. Differentiating its logarithm gives (ADO16) as the exponentially tilted mean of the instantaneous directional strain:

$$
\Gamma_M(t)=
\frac{
\mathbb E_{\mu_0,B}
\left[\sigma_t\exp\left(2\int_0^t\sigma_sds\right)\right]}
{
\mathbb E_{\mu_0,B}
\exp\left(2\int_0^t\sigma_sds\right)}.
\tag{ADO30}
$$

A path with sustained positive directional strain receives increasing weight in (ADO30). Equations (ADO24) and (ADO30) are Eulerian and Lagrangian forms of the same selection effect.

## 6. Relation to the deformation-covariance quotient

Let $C=\mathbb E[FF^{\mathsf T}]$, $G_C=C^{-1}$, and

$$
Z_C=\int\omega^{\mathsf T}G_C\omega\,dx,
\qquad
\mathfrak A_C=\frac W{Z_C},
\qquad
\mathfrak B_C=
\frac{\displaystyle\int\omega^{\mathsf T}C\omega\,dx}{W}.
\tag{ADO31}
$$

For every positive definite $C$ and vector $v$,

$$
(v^{\mathsf T}v)^2
\le(v^{\mathsf T}Cv)(v^{\mathsf T}C^{-1}v).
\tag{ADO32}
$$

Pointwise application followed by Cauchy–Schwarz in space gives

$$
\boxed{
\mathfrak A_C(t)
\le\mathfrak B_C(t)
\le\|\lambda_{\max}(C(t,\cdot))\|_{L^\infty}.}
\tag{ADO33}
$$

The middle quotient weights the direct deformation only in the current vorticity direction. It is sharper than the full operator bound, while (ADO25)–(ADO30) supply the initial-data-conditioned envelope selected for the continuation reduction.

In an eigenbasis of $C$, with eigenvalues $c_i>0$ and $a_i=v_i^2$, the algebraic gap in (ADO32) is

$$
(v^{\mathsf T}Cv)(v^{\mathsf T}C^{-1}v)
-(v^{\mathsf T}v)^2
=
\sum_{i<j}a_ia_j\frac{(c_i-c_j)^2}{c_ic_j}\ge0.
\tag{ADO34}
$$

## 7. Khasminskii comparison and energy-class boundary

The exact orientation process in (ADO27) yields the positive envelope

$$
\frac{\mathcal E_M(t)}{W(0)}
\le
\mathbb E_{\mu_0,B}
\exp\left(2\int_0^t(\sigma_s)_+ds\right).
\tag{ADO35}
$$

For an interval $I_j=[t_{j-1},t_j]$, let $\mathscr R_s$ be the phase-space support reachable at time $s$ from the initial pairs $(a,n_0(a))$ under (ADO5) and (ADO27), and define

$$
\kappa_j=
\sup_{\substack{s\in I_j\\(x,n)\in\mathscr R_s}}
\mathbb E_{s,x,n}
\int_s^{t_j}2\bigl(n_r^{\mathsf T}S(X_r,r)n_r\bigr)_+dr.
\tag{ADO36}
$$

The Markov property and Khasminskii series give

$$
\boxed{
\kappa_j<1\ \text{for every }j
\quad\Longrightarrow\quad
\sup_{t\le t_N}
\frac{\mathcal E_M(t)}{W(0)}
\le\prod_{j=1}^N\frac1{1-\kappa_j}.}
\tag{ADO37}
$$

The full strain envelope replaces the reachable directional integrand by $\lambda_+(S)=\max\{\lambda_{\max}(S),0\}$. Denote its larger dose by $\overline\kappa_j$, so $\kappa_j\le\overline\kappa_j$. For the divergence-free drift, the Nash heat-kernel estimate gives, for $1<p\le\infty$, $3/2<q\le\infty$, and $\alpha=3/(2q)$,

$$
\overline\kappa_j
\le
C_{p,q,\mathbb T}
\left[
\Delta_j^{1-1/p}
+\nu^{-\alpha}
\Delta_j^{1-1/p-\alpha}
\right]
\|\lambda_+(S)\|_{L^p(I_j;L^q)},
\tag{ADO38}
$$

provided

$$
\frac1p+\frac{3}{2q}<1
\quad\Longleftrightarrow\quad
\frac2p+\frac3q<2.
\tag{ADO39}
$$

At equality, direct Lorentz control applies for finite $1<p<\infty$ and $3/2<q<\infty$ through $L_t^{p,1}L_x^q$. The endpoint $(p,q)=(\infty,3/2)$ is excluded: its $\tau^{-1}$ kernel is nonintegrable and has no nontrivial $L_t^{\infty,1}$ refinement. The separate endpoint $(p,q)=(1,\infty)$ is controlled directly by $\int\|\lambda_+(S)\|_\infty dt$.

The kinetic-energy law supplies $S\in L_t^2L_x^2$. This pair satisfies

$$
\frac2p+\frac3q=\frac52>2,
\tag{ADO40}
$$

and therefore lies beyond the Kato scaling range in (ADO39). A scalar parabolic pulse makes the generic obstruction explicit. In a local torus chart, set

$$
s_r(t,x)=r^{-5/2}\chi(t/r^2)\psi(x/r),
\tag{ADO41}
$$

for fixed nonnegative smooth bumps $\chi$ and $\psi$. Then

$$
\|s_r\|_{L_{t,x}^2}^2
\asymp r^{-5}r^2r^3\asymp1,
\tag{ADO42}
$$

while a Brownian path that remains in the positive core for a time comparable to $r^2$ accumulates dose

$$
\int s_r\,dt\asymp r^{-5/2}r^2=r^{-1/2}\longrightarrow\infty.
\tag{ADO43}
$$

Brownian scaling gives that core event a positive probability independent of $r$, so this family of exponential moments is unbounded as $r\downarrow0$. Each fixed smooth $s_r$ has a finite moment. The family is a scalar heat-kernel obstruction to a uniform $L^2_{t,x}$-only estimate. It is not a Navier–Stokes trajectory and does not classify estimates using self-consistency, incompressibility, pressure, or the reachable orientation set.

## 8. Cascade-level implication

For a sequence of disjoint cascade-level intervals $I_j$, put

$$
\delta_j=\int_{I_j}(\Gamma_M(t))_+dt.
\tag{ADO44}
$$

Equation (ADO17) gives the sufficient condition

$$
\sum_{j=0}^\infty\delta_j<\infty.
\tag{ADO45}
$$

Geometric scale placement alone does not imply (ADO45). If the active dose stays bounded below, $\delta_j\ge c>0$, the series diverges even when the spatial scales are geometric. A quantitative decorrelation law such as

$$
\delta_j\le C\varphi^{-\varepsilon j},
\qquad \varepsilon>0,
\tag{ADO46}
$$

instead gives

$$
\sum_{j=0}^\infty\delta_j
\le\frac C{1-\varphi^{-\varepsilon}}<\infty.
\tag{ADO47}
$$

For this active-dose continuation route, a whole-cascade Cassi selection theorem bearing on arbitrary-data regularity must therefore produce a summable bound on active directional dose, orientation anisotropy, or strain alignment. A fixed geometric scale ratio supplies no such decay by itself.

## 9. Fixed controls

### 9.1 Local algebraic homogeneous extension

Use the trace-free local matrix model

$$
L_a=S_a=\operatorname{diag}(a,-a,0),
\qquad a>0,
\qquad
F_a(t)=\operatorname{diag}(e^{at},e^{-at},1),
\tag{ADO48}
$$

with the prescribed vector seed $e_1$. Per unit label volume,

$$
M_a(t)=e^{2at}e_1e_1^{\mathsf T},
\qquad
\frac{\mathcal E_M(t)}{W(0)}=e^{2at},
\qquad
\Gamma_M=a.
\tag{ADO49}
$$

The orientation remains $e_1$ and the strain occupation in (ADO29) is exact. The normalized anisotropy is $\theta=1$. This control shows local algebraic sharpness and excludes a bound from trace-free deformation or volume preservation alone. The affine velocity $u=L_ax$ has zero curl, so the prescribed seed is not its vorticity; on $\mathbb R^3$ the constant seed also gives infinite global $W(0)$ and $\mathcal E_M$. The control is neither periodic nor a Navier–Stokes solution.

### 9.2 Periodic shear heat flow

Use the exact periodic solution

$$
u_s(y,t)=b e^{-\lambda t}\sin(ny)e_1,
\qquad
\lambda=\nu n^2,
\qquad n\in\mathbb N.
\tag{ADO50}
$$

Its vorticity is

$$
\omega_s=-bn e^{-\lambda t}\cos(ny)e_3.
\tag{ADO51}
$$

The deformation acts only in the $e_1$–$e_2$ plane, so

$$
\nabla_aX_t(a)e_3=e_3,
\qquad
\sigma_t=0
\tag{ADO52}
$$

for every trajectory seeded in the vorticity direction. Volume preservation gives

$$
\mathcal E_M(t)=W(0),
\qquad
\Gamma_M=0,
\qquad
W(t)=e^{-2\lambda t}W(0).
\tag{ADO53}
$$

Thus the active envelope remains one while unseeded in-plane deformation can be large. The inequality in (ADO14) is strict for $t>0$ because stochastic phase averaging produces viscous cancellation in the mean.

### 9.3 Two-dimensional embedded flow

For a two-dimensional incompressible flow embedded in three dimensions, $\omega_0=\zeta_0e_3$ and $\nabla_aX_te_3=e_3$. Hence

$$
\mathcal E_M(t)=W(0),
\qquad
\Gamma_M=0,
\qquad
W(t)\le W(0).
\tag{ADO54}
$$

This control recovers the absence of vortex stretching and tests the dimension-specific reduction.

## 10. Fixed verification inventory

The verifier must execute exactly 40 fixed algebraic and control checks.

### 10.1 Seeded closure and spread—eight checks

1. the symbolic common-noise product correction has the Laplacian form entering (ADO10);
2. the fixed identity initialization $F_0=I$, $V_0=\omega_0$ gives $M(0)=\omega_0\omega_0^{\mathsf T}$;
3. the sample mean used by the finite-ensemble covariance fixture is computed correctly;
4. direct symbolic differentiation in one spatial coordinate gives the negative $2\nu\partial_k\omega\,\partial_k\omega^{\mathsf T}$ product-rule term;
5. subtracting the independently differentiated moment and mean-product diffusion terms gives the positive one-coordinate source in (ADO11), whose sum over $k$ is the displayed source;
6. the fixed identity initialization gives $R(0)=0$;
7. the fixed finite ensemble satisfies $R\succeq0$;
8. the general trace reaction is $2S:M$ and contains no antisymmetric contribution.

### 10.2 Active envelope and occupation—eight checks

9. the general eigenbasis factorization (ADO34);
10. a fixed two-cell quadrature satisfies the integrated inequality $\mathfrak A_C\le\mathfrak B_C$;
11. the same fixed quadrature satisfies $\mathfrak B_C\le\lambda_{\max}(C)$;
12. a fixed volume-preserving linear map satisfies the Eulerian-to-label integrand identity in (ADO25);
13. the general norm equation in (ADO28);
14. a fixed unit direction satisfies the normalized orientation equation in (ADO27);
15. a constant-strain scalar control satisfies the exponential occupation identity in (ADO29);
16. a two-rate scalar control verifies that logarithmic differentiation gives the tilted production in (ADO30).

### 10.3 Anisotropy and scaling—six checks

17. $Q$ is trace free;
18. the eigenvalue identity and simplex upper bound in (ADO21);
19. $S:M=mS:Q$ for trace-free $S$;
20. the general Frobenius Lagrange identity underlying the alignment bound in (ADO24);
21. isotropic seeded covariance gives zero strain production;
22. the formal Euclidean scaling exponents of $\mathcal E_M/W(0)$ and $\int\Gamma_Mdt$ vanish, with the fixed-torus qualification stated in §3.

### 10.4 Exact controls—ten checks

23. $\operatorname{tr}L_a=0$ in the local algebraic control;
24. the local homogeneous deformation solves $F_a'=L_aF_a$;
25. its seeded moment solves the reaction part of (ADO10);
26. its per-unit-volume envelope ratio equals $e^{2at}$;
27. its per-unit-volume production rate equals $a$;
28. its normalized orientation anisotropy equals one;
29. direct differentiation gives zero convection and the heat equation for the periodic shear;
30. direct differentiation gives the shear vorticity in (ADO51);
31. the shear-form deformation matrix fixes $e_3$ and gives the unit moment ratio;
32. a general embedded two-dimensional block deformation fixes $e_3$ and its block strain has zero active production.

### 10.5 Kato and cascade boundary—eight checks

33. the finite geometric-series identity holds and a fixed $\kappa=2/5$ limit is $5/3$;
34. doubling the heat-kernel exponent condition gives (ADO39);
35. the formal Euclidean scaling exponent of $L_t^pL_x^q$ strain vanishes at $2/p+3/q=2$;
36. $(p,q)=(2,2)$ gives the exponent $5/2$ in (ADO40);
37. the pulse $L^2_{t,x}$ exponent in (ADO42) is zero;
38. the pulse-dose family has exponent $-1/2$ in (ADO43);
39. the fixed $\varphi^{-j}$ geometric upper dose sums to $\varphi^2$;
40. a positive constant dose over infinitely many cascade levels diverges.

## 11. Decision tree

The verifier writes a source-bound JSON receipt with the following classifications.

1. If any fixed symbolic, exact-control, scaling, inventory, or source-integrity check fails, classify the run **FAIL** and do not propagate a mathematical result.
2. If all 40 checks pass, classify their fixed symbolic components as **SUPPORTS** for the analytically derived seeded common-noise closure, Jensen envelope, active occupation identity, orientation decomposition, and continuation reduction. This classification does not replace the conditional analytical arguments.
3. If checks 37–38 pass, classify a generic estimate of the active exponential occupation from the energy-class $L^2_{t,x}$ strain norm alone **CONTRADICTS**. This classification concerns scalar parabolic control and makes no Navier–Stokes trajectory claim.
4. If checks 39–40 pass, classify geometric cascade spacing alone as a source of summable active dose **CONTRADICTS**.
5. Keep a uniform bound in (ADO18), self-consistent control of reachable orientations, and arbitrary-data Navier–Stokes regularity **UNRESOLVED**.

The selected receipt path is

`runs/navier_stokes_active_deformation_occupation/verification.json`,

with adjacent `verification.inputs.json` and `verification.sources/`. The receipt must bind raw SHA-256 identities for `turbulence/navier-stokes-active-deformation-occupation.md`, this fixed protocol, and the verifier. Generated evidence remains local and untracked.

## 12. Evidence boundary

The schedule checks general polynomial identities, explicitly labelled finite fixtures, local algebraic controls, formal scaling exponents, and the declared decision logic. S1, S4–S5, S8, A1, A5, C1–C5 and X7–X8 check general symbolic or directly differentiated components; S2–S3, S6–S7, A2–A4, A6–A8, X1–X6 and X9–X10 are fixed finite or local controls; K1–K8 check the stated series and exponent arithmetic. The schedule does not execute a Navier–Stokes trajectory, a stochastic-flow simulation, a matrix-PDE integration, a singularity search, or a whole-cascade Cassi dynamics. The common-noise closure, covariance positivity, Khasminskii implication, heat-kernel comparison, endpoint Lorentz statement, Brownian core-event argument, and continuation step are conditional analytical arguments under the stated hypotheses and standard cited estimates, outside executable scope.

No physical parameter, numbered open question, empirical prediction, or field-to-fluid constitutive law is introduced or reclassified.

## Sources

- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the three-dimensional incompressible Navier–Stokes equations](https://web.math.princeton.edu/~const/ci.pdf)—stochastic flow, volume preservation, and Cauchy formula.
- P. Constantin and G. Iyer, [A stochastic-Lagrangian approach to the Navier–Stokes equations in domains with boundary](https://web.math.princeton.edu/~const/gic31110.pdf)—random-characteristic formulation and vorticity transport context.
- J. Nash, *Continuity of solutions of parabolic and elliptic equations*, American Journal of Mathematics **80** (1958), 931–954—drift-independent heat-kernel scale used in the Kato comparison.
- G. Seregin, L. Silvestre, V. Šverák, and A. Zlatoš, [On divergence-free drifts](https://arxiv.org/abs/1010.6025)—parabolic estimates and the critical boundary for divergence-free advection.
- `turbulence/navier-stokes-deformation-covariance.md`—unseeded covariance-inverse identity and active quotient compared in §6.
- T. Mahithitarmmatorn, [Exact mean–covariance dynamics of the Weber field in the stochastic Lagrangian representation of the 3D Navier–Stokes equations](https://arxiv.org/abs/2608.16915)—closed common-noise covariance calculus and current stochastic-flow regularity boundary.
