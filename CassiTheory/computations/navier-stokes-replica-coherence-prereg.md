# Replica Coherence and Viscous Compensation: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule tests an exact decomposition of the vorticity-seeded stochastic Cauchy field for the original unforced periodic three-dimensional Navier–Stokes equation. Two independent Brownian replicas recover physical enstrophy through their overlap, while their mean squared disagreement is the trace of the centred same-noise covariance. The covariance obeys a forced positive matrix equation whose source is the vorticity-gradient Gram matrix. Variation of constants turns that source into a retarded palinstrophy occupation, and volume preservation gives a sharp deformation-independent lower bound from the determinant of the gradient Gram matrix.

The schedule distinguishes exact identities from a conditional continuation target. It also tests rank-deficient source frames, periodic shear, homogeneous extension, and an exact periodic Beltrami flow. No Navier–Stokes trajectory integration, singularity search, stochastic-flow simulation, fitted parameter, or Cassi constitutive term is included.

## 1. Equation, domain, and conventions

Work with a smooth mean-zero divergence-free solution on the normalized periodic torus during a compact interval $[0,T_0]$ inside its smooth lifespan:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad
\nu>0.
\tag{RVC1}
$$

Set

$$
\omega=\nabla\times u,
\qquad
L=\nabla u,
\qquad
S=\frac12(L+L^{\mathsf T}),
\qquad
\mathcal L_u=\partial_t+u\cdot\nabla-\nu\Delta.
\tag{RVC2}
$$

The Euclidean enstrophy, palinstrophy, and stretching production are

$$
W(t)=\int_{\mathbb T^3}|\omega|^2dx,
\qquad
D(t)=\int_{\mathbb T^3}|\nabla\omega|^2dx,
\qquad
P(t)=\int_{\mathbb T^3}\omega\cdot S\omega\,dx.
\tag{RVC3}
$$

Thus

$$
W'(t)=2P(t)-2\nu D(t).
\tag{RVC4}
$$

All stochastic identities use a spatially uniform Brownian translation. A single realization is a volume-preserving diffeomorphism, and all differentiations under expectation are restricted to the stated smooth interval.

## 2. Same-noise and independent-replica fields

Let $Y(x,t)$ be the vorticity-seeded stochastic Cauchy field from `turbulence/navier-stokes-active-deformation-occupation.md`:

$$
Y_t(x)=F_t(x)\omega_0(\mathscr A_t(x)),
\qquad
\omega(x,t)=\mathbb E Y_t(x).
\tag{RVC5}
$$

Its same-noise second moment and centred covariance are

$$
M=\mathbb E[YY^{\mathsf T}],
\qquad
R=M-\omega\omega^{\mathsf T}\succeq0.
\tag{RVC6}
$$

Let $Y^{(1)}$ and $Y^{(2)}$ use independent Brownian translations with the same deterministic velocity field and initial datum. Independence gives

$$
K(x,t):=
\mathbb E_{1,2}[Y^{(1)}(x,t)Y^{(2)}(x,t)^{\mathsf T}]
=\omega(x,t)\omega(x,t)^{\mathsf T}.
\tag{RVC7}
$$

Taking traces yields the pointwise replica-overlap and disagreement identities

$$
\mathbb E_{1,2}[Y^{(1)}\cdot Y^{(2)}]=|\omega|^2,
\tag{RVC8}
$$

$$
\frac12\mathbb E_{1,2}|Y^{(1)}-Y^{(2)}|^2
=\operatorname{tr}R.
\tag{RVC9}
$$

Define total seeded occupation and integrated disagreement by

$$
\mathcal E_M(t)=\int_{\mathbb T^3}\operatorname{tr}M\,dx,
\qquad
\mathcal V(t)=\int_{\mathbb T^3}\operatorname{tr}R\,dx.
\tag{RVC10}
$$

Then

$$
\boxed{\mathcal E_M(t)=W(t)+\mathcal V(t).}
\tag{RVC11}
$$

This separates the physical coherent mean from stochastic spread without changing the Navier–Stokes equation.

## 3. Forced covariance and retarded occupation

The common-noise product correction closes the seeded second moment:

$$
\mathcal L_uM=LM+ML^{\mathsf T},
\qquad
M(0)=\omega_0\omega_0^{\mathsf T}.
\tag{RVC12}
$$

The deterministic mean product contains the viscous gradient subtraction. Therefore

$$
\boxed{
\mathcal L_uR=LR+RL^{\mathsf T}+2\nu Q_\omega,
\qquad
R(0)=0,}
\tag{RVC13}
$$

where

$$
Q_\omega=
\sum_{k=1}^3(\partial_k\omega)(\partial_k\omega)^{\mathsf T}
=(\nabla\omega)(\nabla\omega)^{\mathsf T}\succeq0.
\tag{RVC14}
$$

Let $\mathcal U(t,s)$ denote the positive matrix propagator of the homogeneous equation in (RVC12). Variation of constants gives

$$
\boxed{
R(t)=2\nu\int_0^t\mathcal U(t,s)Q_\omega(s)\,ds.}
\tag{RVC15}
$$

For the stochastic flow from $s$ to $t$, write $F_{s,t}(a)=\nabla_aX_{s,t}(a)$. Volume preservation permits the integrated trace form

$$
\boxed{
\mathcal V(t)=
2\nu\int_0^t\int_{\mathbb T^3}
\mathbb E\operatorname{tr}
\left[F_{s,t}(a)Q_\omega(a,s)F_{s,t}(a)^{\mathsf T}\right]
\,da\,ds.}
\tag{RVC16}
$$

Decompose $Q_\omega=\sum_kg_kg_k^{\mathsf T}$ with $g_k=\partial_k\omega$. When $D(s)>0$, define the source probability measure

$$
d\eta_s(a,k)=
\frac{|g_k(a,s)|^2}{D(s)}\,da,
\qquad
\sum_k\int_{\mathbb T^3}d\eta_s(a,k)=1.
\tag{RVC17}
$$

If $n_r$ is the normalized transported source vector and

$$
\sigma_r^{s,a,k}=n_r^{\mathsf T}S(X_{s,r}(a),r)n_r,
\tag{RVC18}
$$

then

$$
|F_{s,t}(a)g_k(a,s)|^2
=|g_k(a,s)|^2
\exp\left(2\int_s^t\sigma_r^{s,a,k}\,dr\right).
\tag{RVC19}
$$

Consequently,

$$
\boxed{
\mathcal V(t)=
2\nu\int_0^tD(s)
\mathbb E_{\eta_s,B}
\exp\left(2\int_s^t\sigma_r^{s,a,k}\,dr\right)ds.}
\tag{RVC20}
$$

The convention for $D(s)=0$ is that the corresponding integrand is zero.

Taking the trace of (RVC13) and integrating also gives

$$
\boxed{
\mathcal V'(t)=2\int_{\mathbb T^3}S:R\,dx+2\nu D(t).}
\tag{RVC21}
$$

Thus viscous palinstrophy is a positive source of replica disagreement, while later strain may amplify or reduce the accumulated covariance trace.

## 4. Global coherence budget

For $W>0$ and $\mathcal V>0$, define

$$
\alpha(t)=\frac{P(t)}{W(t)},
\qquad
\beta(t)=
\frac{\int S:R\,dx}{\mathcal V(t)},
\qquad
c(t)=\frac{W(t)}{\mathcal E_M(t)}.
\tag{RVC22}
$$

At zero denominators use the continuous limiting identities. Since $R\succeq0$,

$$
0\le c(t)\le1,
\qquad
1-c(t)=\frac{\mathcal V(t)}{\mathcal E_M(t)}.
\tag{RVC23}
$$

The active seeded rate from the parent result is

$$
\Gamma_M(t)=
\frac{\int S:M\,dx}{\mathcal E_M(t)}.
\tag{RVC24}
$$

Since $M=\omega\omega^{\mathsf T}+R$,

$$
\boxed{
\Gamma_M=c\alpha+(1-c)\beta.}
\tag{RVC25}
$$

Combining (RVC4), (RVC21), and (RVC25) yields the exact coherence-share equation

$$
\boxed{
c'=2c(1-c)(\alpha-\beta)
-\frac{2\nu D}{\mathcal E_M}.}
\tag{RVC26}
$$

On any interval where $W>0$ and $\mathcal E_M>0$, equivalently where $c>0$, division of (RVC26) by $c=W/\mathcal E_M$ gives

$$
\boxed{
\frac d{dt}\log c
=2(1-c)(\alpha-\beta)-\frac{2\nu D}{W}.}
$$

The first term is the relative strain-selection advantage of coherent vorticity over stochastic disagreement. The second term transfers coherent share into replica disagreement. Initially,

$$
c(0)=1,
\qquad
c'(0)=-\frac{2\nu D(0)}{W(0)}
\quad\text{when }W(0)>0.
\tag{RVC27}
$$

On intervals where both shares are positive, the odds obey

$$
\boxed{
\frac12\frac d{dt}\log\frac{W}{\mathcal V}
=\alpha-\beta
-\nu D\left(\frac1W+\frac1{\mathcal V}\right).}
\tag{RVC28}
$$

The total seeded occupation satisfies

$$
\mathcal E_M(t)=W(0)
\exp\left(2\int_0^t\Gamma_M(s)ds\right).
\tag{RVC29}
$$

Equations (RVC11) and (RVC20) therefore give the positive-minus-positive representation

$$
\boxed{
W(t)=W(0)
\exp\left(2\int_0^t\Gamma_M(s)ds\right)
-2\nu\int_0^tD(s)
\mathbb E_{\eta_s,B}
\exp\left(2\int_s^t\sigma_r^{s,a,k}dr\right)ds.}
\tag{RVC30}
$$

This is an exact fluctuation-production balance for stretched vorticity. It extends the scalar fluctuation-dissipation interpretation by retaining the matrix stretching of each viscous source.

## 5. Sharp volume-preserving compensation

For any $F\in SL(3)$ and symmetric positive definite $Q$,

$$
\det(FQF^{\mathsf T})=\det Q.
\tag{RVC31}
$$

The arithmetic-geometric mean inequality for the three eigenvalues of $FQF^{\mathsf T}$ gives

$$
\boxed{
\operatorname{tr}(FQF^{\mathsf T})
\ge3(\det Q)^{1/3}.}
\tag{RVC32}
$$

The constant is sharp. For

$$
F_*(Q)=(\det Q)^{1/6}Q^{-1/2},
\tag{RVC33}
$$

one has

$$
\det F_*=1,
\qquad
F_*QF_*^{\mathsf T}=(\det Q)^{1/3}I.
\tag{RVC34}
$$

Define the full-rank vorticity-mixing functional

$$
J(t)=\int_{\mathbb T^3}(\det Q_\omega)^{1/3}dx
=\int_{\mathbb T^3}|\det\nabla\omega|^{2/3}dx.
\tag{RVC35}
$$

Applying (RVC32) inside (RVC16) gives the deformation-independent lower bound

$$
\boxed{
\mathcal V(t)\ge6\nu\int_0^tJ(s)ds.}
\tag{RVC36}
$$

This bound is optimal using only $Q$ and the constraint $\det F=1$. For rank-two data

$$
Q_2=\operatorname{diag}(q_1,q_2,0),
\qquad
F_\varepsilon^{(2)}=
\operatorname{diag}(\varepsilon,\varepsilon,\varepsilon^{-2}),
\tag{RVC37}
$$

one has $\det F_\varepsilon^{(2)}=1$ and

$$
\operatorname{tr}
(F_\varepsilon^{(2)}Q_2F_\varepsilon^{(2)\mathsf T})
=\varepsilon^2(q_1+q_2)\longrightarrow0.
\tag{RVC38}
$$

For rank-one data

$$
Q_1=\operatorname{diag}(q_1,0,0),
\qquad
F_\varepsilon^{(1)}=
\operatorname{diag}(\varepsilon,\varepsilon^{-1/2},\varepsilon^{-1/2}),
\tag{RVC39}
$$

one similarly obtains

$$
\operatorname{tr}
(F_\varepsilon^{(1)}Q_1F_\varepsilon^{(1)\mathsf T})
=q_1\varepsilon^2\longrightarrow0.
\tag{RVC40}
$$

Additional dynamical information is therefore required for a positive deformation-independent rank-one or rank-two source bound.

## 6. Compensated continuation target

Define

$$
\mathcal G(t)=
\mathcal E_M(t)-6\nu\int_0^tJ(s)ds.
\tag{RVC41}
$$

Equations (RVC11) and (RVC36) imply

$$
0\le W(t)\le\mathcal G(t)\le\mathcal E_M(t).
\tag{RVC42}
$$

Fix $\nu>0$, finite $T>0$, and finite data-ball radius $R_0\ge0$. A sufficient all-data condition is

$$
\boxed{
\sup_{\substack{
 u_0\in C^\infty,\ \nabla\cdot u_0=0,\ \int u_0=0\\
 \|u_0\|_{H^3}\le R_0}}
\ \sup_{0\le t<\min(T,T_*)}
\mathcal G(t)
\le C_G(\nu,T,R_0)<\infty.}
\tag{RVC43}
$$

Under (RVC43), enstrophy stays bounded and the standard periodic $H^1$ restart continues the solution through $T$. Finite-time loss of smoothness would force $\mathcal G$ to become unbounded along an endpoint sequence. The bound in (RVC43) permits the certified full-rank part of viscous replica disagreement to compensate growth in $\mathcal E_M$; its derivation from independently controlled Navier–Stokes quantities remains open.

## 7. Scaling and exact controls

### 7.1 Navier–Stokes scaling

Under the Euclidean scaling

$$
u_\lambda(x,t)=\lambda u(\lambda x,\lambda^2t),
\qquad
\omega_\lambda(x,t)=\lambda^2\omega(\lambda x,\lambda^2t),
\tag{RVC44}
$$

$W$, $\mathcal E_M$, $\mathcal V$, and $\nu\int Jdt$ all have scaling exponent one. Therefore $c$, $\mathcal V/\mathcal E_M$, and $(\nu/W(0))\int Jdt$ have zero exponent. On a fixed torus this records dimensional criticality; the scaling changes the spatial period.

### 7.2 Periodic shear heat flow

For

$$
u_n(y,t)=e^{-\nu n^2t}\sin(ny)e_1,
\qquad
\omega_n=-n e^{-\nu n^2t}\cos(ny)e_3,
\tag{RVC45}
$$

$Q_{\omega_n}$ has rank one and $J=0$. The stochastic Cauchy vector remains in the $e_3$ direction, so the volume-normalized identities are

$$
\mathcal E_M(t)=W(0),
\qquad
W(t)=W(0)e^{-2\nu n^2t},
\qquad
\mathcal V(t)=W(0)(1-e^{-2\nu n^2t}).
\tag{RVC46}
$$

Thus the determinant lower bound can vanish while the exact replica disagreement records viscous decay.

### 7.3 Homogeneous extension

For the local algebraic control

$$
F_a(t)=\operatorname{diag}(e^{at},e^{-at},1),
\qquad
Y_0=e_1,
\tag{RVC47}
$$

all replicas coincide, $R=0$, $c=1$, and

$$
\mathcal E_M(t)=W(t)=e^{2at}W(0).
\tag{RVC48}
$$

Spatially uniform volume-preserving stretching creates no replica disagreement. This affine control lies outside the periodic finite-energy Navier–Stokes class and isolates the algebraic boundary.

### 7.4 Exact periodic Beltrami flow

On the $2\pi$-periodic torus, let

$$
u_{\mathrm{ABC}}(x,y,z)=
(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x).
\tag{RVC49}
$$

It satisfies

$$
\nabla\cdot u_{\mathrm{ABC}}=0,
\qquad
\nabla\times u_{\mathrm{ABC}}=u_{\mathrm{ABC}},
\qquad
\Delta u_{\mathrm{ABC}}=-u_{\mathrm{ABC}}.
\tag{RVC50}
$$

Hence $u(t)=e^{-\nu t}u_{\mathrm{ABC}}$ with the corresponding Bernoulli pressure is an exact smooth unforced Navier–Stokes solution. Its vorticity-gradient determinant is

$$
\det\nabla\omega(t)
=e^{-3\nu t}
\left(
\cos x\cos y\cos z-
\sin x\sin y\sin z
\right).
\tag{RVC51}
$$

It follows that

$$
J(t)=e^{-2\nu t}J(0),
\qquad
J(0)>0.
\tag{RVC52}
$$

This control establishes that the full-rank compensation functional is nonzero for a genuine three-dimensional periodic solution.

## 8. Fixed verification inventory

The verifier must execute exactly 40 checks with the following ordered names.

### 8.1 Replica and covariance—eight checks

1. `R1 finite independent-replica outer product`
2. `R2 finite independent-replica scalar overlap`
3. `R3 replica disagreement variance identity`
4. `R4 centred covariance Gram identity`
5. `R5 common-noise Laplacian product closure`
6. `R6 independent-noise cross-variation separation`
7. `R7 deterministic mean-product gradient source`
8. `R8 centred covariance source and initial value`

### 8.2 Duhamel and occupation—eight checks

9. `D1 trace-free propagator determinant`
10. `D2 constant-matrix Duhamel residual`
11. `D3 gradient-frame trace expansion`
12. `D4 directional amplitude growth identity`
13. `D5 source probability normalization`
14. `D6 scalar covariance integrating factor`
15. `D7 integrated variance trace balance`
16. `D8 positive-minus-positive enstrophy identity`

### 8.3 Coherence budget—eight checks

17. `C1 total occupation decomposition`
18. `C2 strain-rate mixture identity`
19. `C3 coherence replicator-diffusion identity`
20. `C4 initial coherence derivative`
21. `C5 logarithmic coherence budget`—verify the displayed $\log c$ identity on intervals with $W>0$ and $\mathcal E_M>0$
22. `C6 coherent-to-spread odds identity`
23. `C7 coherence share complement`
24. `C8 compensated upper-gap identity`

### 8.4 Volume-preserving optimization—eight checks

25. `S1 determinant transport identity`
26. `S2 sharp optimizer unit determinant`
27. `S3 sharp optimizer isotropic image`
28. `S4 sharp optimizer trace value`
29. `S5 rank-two collapse unit determinant`
30. `S6 rank-two collapse trace limit`
31. `S7 rank-one collapse unit determinant`
32. `S8 rank-one collapse trace limit`

### 8.5 Scaling and exact controls—eight checks

33. `X1 gradient Gram determinant square`
34. `X2 full-rank compensation factor`
35. `X3 Navier-Stokes scaling exponents`
36. `X4 periodic shear rank defect`
37. `X5 periodic shear replica budget`
38. `X6 homogeneous extension no disagreement`
39. `X7 ABC divergence curl and heat identities`
40. `X8 ABC gradient determinant and decay`

## 9. Decision tree

1. If any fixed symbolic, exact-control, inventory, scaling, or source-integrity check fails, classify the run `FAIL` and propagate no mathematical result.
2. If all 40 checks pass, classify the independent-replica identities, forced covariance/Duhamel law, coherence-share equation, and sharp full-rank lower bound as `SUPPORTS` at their stated analytical scope.
3. If the rank-one and rank-two collapse controls pass, classify deformation-independent positive compensation from volume preservation alone for singular source frames as `CONTRADICTS`.
4. Keep the uniform bound (RVC43), any route deriving it from initial $H^3$ data, and arbitrary-data Navier–Stokes regularity `UNRESOLVED`.
5. Keep a physical Cassi field-to-vorticity identification, a $\varphi$-controlled compensation rate, and whole-cascade Cassi dynamics outside the result.
6. The selected receipt path is `runs/navier_stokes_replica_coherence_20260910_qualified/verification.json`, with adjacent `verification.inputs.json` and `verification.sources/`. It must bind raw SHA-256 identities for `turbulence/navier-stokes-replica-coherence.md`, this protocol, and the verifier. Generated evidence remains local and untracked.

## 10. Evidence boundary

The schedule checks finite-replica algebra, general one-coordinate product differentiation, general matrix and scalar identities, fixed constant-matrix propagators, exact determinant and collapse formulas, formal scaling exponents, and exact shear, homogeneous, and ABC controls. The common-noise stochastic representation, matrix variation-of-constants formula, positivity of the matrix propagator, source-oriented occupation formula, arithmetic-geometric mean inequality, $H^1$ restart implication, and smooth stochastic-flow existence are conditional analytical arguments under the displayed hypotheses and cited standard results. They remain outside executable scope.

The verifier runs no Navier–Stokes trajectory, stochastic-flow simulation, matrix-PDE integration, singularity search, Monte Carlo estimate, or Cassi whole-cascade dynamics. No physical parameter, empirical prediction, numbered open question, or field-to-fluid constitutive law is introduced or reclassified.

## 11. Sources

- `turbulence/navier-stokes-active-deformation-occupation.md`—seeded common-noise covariance and active directional occupation
- `turbulence/navier-stokes-deformation-covariance.md`—stochastic deformation covariance and endpoint regression
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—volume-preserving stochastic flow and Cauchy representation
- G. Iyer and J. Mattingly, [A stochastic-Lagrangian particle system for the Navier–Stokes equations](https://arxiv.org/abs/0803.1222)—independent stochastic-flow replicas and finite-ensemble approximation
- T. D. Drivas and G. L. Eyink, [A Lagrangian fluctuation-dissipation relation for scalar turbulence, I](https://arxiv.org/abs/1606.00729)—scalar stochastic fluctuation-dissipation framework
- G. L. Eyink, A. Gupta, and T. Zaki, [Stochastic Lagrangian Dynamics of Vorticity. I. General Theory](https://arxiv.org/abs/1912.06677)—stochastic Cauchy invariants and their variance
