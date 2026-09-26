# Adaptive Positive Metrics for Vortex Stretching: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule tests whether a positive time-dependent metric can convert three-dimensional Navier–Stokes vortex stretching into a coercive energy estimate. It fixes the finite-dimensional Lyapunov identity, a scalar enstrophy weight, the covariance flow used by CassiFI, the spatially varying metric balance, and a terminal-value adjoint metric. The controls distinguish exact cancellation from uniform control of the Euclidean vorticity norm. The execution covers symbolic identities and fixed smooth data; full Navier–Stokes trajectory integration lies outside its scope.

## 1. Equation, domain, and conventions

Work with a smooth mean-zero solution of the unforced incompressible Navier–Stokes equation on the normalized $2\pi$ torus:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad \nabla\cdot u=0,
\qquad \nu>0.
$$

Put

$$
\omega=\nabla\times u,
\qquad A=\nabla u,
\qquad S=\frac12(A+A^{\mathsf T}),
\qquad D_t=\partial_t+u\cdot\nabla.
$$

The vorticity equation and Euclidean enstrophy balance are

$$
D_t\omega=A\omega+\nu\Delta\omega,
$$

$$
\frac12\frac d{dt}W+\nu D=P,
\qquad
W=\|\omega\|_2^2,
\quad D=\|\nabla\omega\|_2^2,
\quad P=\int\omega\cdot S\omega\,dx.
$$

Spatial integrals use normalized volume. Matrix inequalities use the Euclidean order on symmetric matrices.

## 2. Positive branch metric

For a finite-dimensional branch $z'=L(t)z+r(t)$ and a differentiable symmetric positive-definite matrix $M(t)$, define

$$
E_M=\frac12z^{\mathsf T}Mz.
$$

The fixed product rule is

$$
E_M'
=\frac12z^{\mathsf T}
\left(M'+L^{\mathsf T}M+ML\right)z
+z^{\mathsf T}Mr.
\tag{AM1}
$$

For the homogeneous branch, exact cancellation for every state requires the differential Lyapunov equation

$$
M'+L^{\mathsf T}M+ML=0.
\tag{AM2}
$$

If $\Phi'=L\Phi$ and $\Phi(0)=I$, its solution is

$$
M(t)=\Phi(t)^{-\mathsf T}M(0)\Phi(t)^{-1}.
\tag{AM3}
$$

The fixed extensional control is

$$
L_a=\operatorname{diag}(a,-a,0),
\qquad a>0,
\qquad M(0)=I.
\tag{AM4}
$$

Then $M=\operatorname{diag}(e^{-2at},e^{2at},1)$, so exact cancellation preserves the weighted energy while its least eigenvalue decays and its condition number grows. A time-independent positive symmetrizer cannot cancel the expanding eigenvector because

$$
e_1^{\mathsf T}(L_a^{\mathsf T}M+ML_a)e_1=2aM_{11}>0.
\tag{AM5}
$$

## 3. Scalar enstrophy weight

For $W>0$, let $a_s(t)>0$ satisfy

$$
\frac{a_s'}{a_s}=-\frac{2P}{W}.
\tag{AM6}
$$

The exact weighted balance is

$$
\frac12(a_sW)'=-\nu a_sD.
\tag{AM7}
$$

Exact cancellation therefore exists for every smooth interval with positive enstrophy. Euclidean control additionally requires a data-controlled lower bound for $a_s$. If $m\le a_s\le M$ on $[0,T]$, then for every $0\le s\le t\le T$ the signed normalized production obeys

$$
\int_s^t\frac{P}{W}\,dr
=\frac12\log\frac{a_s(s)}{a_s(t)}
\le\frac12\log\frac{M}{m}.
\tag{AM8}
$$

This does not bound the positive part by itself: negative normalized production can cancel positive normalized production in the signed integral.

$$
u_*(x,y,z)
=(0,1,1)\cos x+(1,0,1)\cos y+(1,-1,1)\sin(x+y).
\tag{AM9}
$$

In the normalized convention its fixed targets are

$$
W_*=5,
\qquad P_*=\frac12,
\qquad
\left.\frac{a_s'}{a_s}\right|_{u_*}=-\frac15.
\tag{AM10}
$$

## 4. CassiFI covariance control

The CassiFI variational field uses the fixed-observation covariance flow

$$
\Sigma'=xx^{\mathsf T}+\lambda I-\Sigma,
\qquad \lambda>0,
\tag{AM11}
$$

whose precision is $M=\Sigma^{-1}$. Its declared spectral bounds assume $\|x\|\le R$. To test the same law on an expanding live state, fix

$$
x(t)=e^{at}e_1,
\qquad \Sigma(0)=\lambda I.
\tag{AM12}
$$

The exact solution is

$$
\Sigma(t)=\operatorname{diag}
\left(
\lambda+\frac{e^{2at}-e^{-t}}{2a+1},
\lambda,
\lambda
\right).
\tag{AM13}
$$

The precision-weighted state remains bounded,

$$
\lim_{t\to\infty}x^{\mathsf T}\Sigma^{-1}x=2a+1,
\tag{AM14}
$$

while $\lambda_{\min}(\Sigma^{-1})\to0$. The normalized observation $\widehat x=e_1$ instead gives

$$
\widehat\Sigma(t)=\operatorname{diag}
(\lambda+1-e^{-t},\lambda,\lambda),
\tag{AM15}
$$

which remains spectrally bounded while the omitted physical amplitude $\|x(t)\|$ grows. These controls test the two available ways to satisfy the observation bound.

## 5. Spatial metric balance

Let $G(x,t)=G(x,t)^{\mathsf T}\succ0$ be smooth and periodic, and define

$$
\mathcal E_G=\frac12\int\omega^{\mathsf T}G\omega\,dx,
\qquad
\mathcal D_G=\sum_k\int
(\partial_k\omega)^{\mathsf T}G(\partial_k\omega)\,dx.
$$

The fixed identity is

$$
\mathcal E_G'+\nu\mathcal D_G
=
\frac12\int\omega^{\mathsf T}
\left(D_tG+A^{\mathsf T}G+GA+\nu\Delta G\right)
\omega\,dx.
\tag{AM16}
$$

The term in parentheses is the metric defect

$$
\mathcal R_G=D_tG+A^{\mathsf T}G+GA+\nu\Delta G.
\tag{AM17}
$$

For material cancellation without the $\nu\Delta G$ term, integration by parts leaves the curvature contribution

$$
\frac{\nu}{2}\int\omega^{\mathsf T}\Delta G\,\omega\,dx,
\tag{AM18}
$$

which has both signs. The fixed one-dimensional periodic control uses the divergence-free field

$$
\omega=(0,\sin x,0),
\qquad G_{\pm}=\operatorname{diag}(2,2\pm\epsilon\cos2x,2),
\qquad 0<\epsilon<2.
\tag{AM19}
$$

Exact viscous cancellation requires $\mathcal R_G=0$. In forward time this equation contains $-\nu\Delta G$ on the solved right-hand side; the natural well-posed formulation prescribes terminal data.

For a general metric, define

$$
\rho_G(t)=\left\|
\lambda_{\max}^{+}
\left(G^{-1/2}\mathcal R_GG^{-1/2}\right)
\right\|_{L^\infty_x}.
\tag{AM20}
$$
Here $\lambda_{\max}^{+}(B):=\max\{\lambda_{\max}(B),0\}$ for symmetric $B$.

If $mI\preceq G\preceq MI$ and $\int_0^T\rho_G(t)dt<\infty$, then

$$
\mathcal E_G(t)
\le\mathcal E_G(0)
\exp\left(\int_0^t\rho_G(s)ds\right),
\qquad
\|\omega(t)\|_2^2\le\frac{2}{m}\mathcal E_G(t).
\tag{AM21}
$$

## 6. Terminal adjoint metric

For each terminal time $\tau$ inside a smooth interval, prescribe

$$
D_tG_\tau+A^{\mathsf T}G_\tau+G_\tau A+\nu\Delta G_\tau=0,
\qquad G_\tau(\tau)=I,
\tag{AM22}
$$

and solve backward from $\tau$. Reverse time gives a forward parabolic matrix equation. Its stochastic-conjugation representation preserves positive definiteness. Equation (AM16) yields

$$
\boxed{
\frac12\|\omega(\tau)\|_2^2
+\nu\int_0^\tau\mathcal D_{G_\tau}(t)dt
=
\frac12\int\omega_0^{\mathsf T}G_\tau(0)\omega_0\,dx.}
\tag{AM23}
$$

The finite-dimensional terminal control for (AM4) is

$$
G_\tau(t)=
\operatorname{diag}
\left(e^{2a(\tau-t)},e^{-2a(\tau-t)},1\right).
\tag{AM24}
$$

It satisfies the endpoint identity exactly while $\lambda_{\max}(G_\tau(0))=e^{2a\tau}$.

The all-data proof target is a bound

$$
\sup_{0<\tau<\min(T,T_*)}
\int\omega_0^{\mathsf T}G_\tau(0)\omega_0\,dx
\le C(\nu,T,R),
\qquad
R=\|u_0\|_{H^3},
\tag{AM25}
$$

for every smooth divergence-free datum with $R$ bounded. Equation (AM23) would then bound enstrophy uniformly through the maximal smooth interval.

## 7. Fixed verification inventory

The verifier must execute exactly 32 substantive checks.

### 7.1 Branch metric—seven checks

1. the product-rule identity (AM1);
2. the Lyapunov residual for (AM3)–(AM4);
3. weighted-energy invariance for an arbitrary initial vector;
4. determinant preservation for the extensional metric;
5. the least-eigenvalue formula;
6. the condition-number formula;
7. the positive fixed-symmetrizer production (AM5).

### 7.2 Scalar weight—seven checks

1. the weighted balance (AM7);
2. the constant-rate weight ODE;
3. its exponential solution;
4. the integrated signed-production identity;
5. the signed interval ceiling under finite metric coercivity;
6. divergence-free and mean-zero properties of (AM9);
7. the exact tuple $(W_*,P_*,a_s'/a_s)=(5,1/2,-1/5)$.

### 7.3 Covariance adaptation—seven checks

1. the initial covariance;
2. the covariance ODE residual;
3. positive definiteness;
4. the precision-weighted limit (AM14);
5. precision lower-bound collapse;
6. condition-number growth;
7. bounded normalized covariance together with unbounded omitted amplitude.

### 7.4 Spatial metric—six checks

1. the periodic diffusion integration-by-parts identity;
2. positive curvature work for $G_+$;
3. negative curvature work for $G_-$;
4. the material-cancellation residual (AM18);
5. exact removal of curvature by (AM22);
6. the Rayleigh and norm-equivalence steps in (AM21).

### 7.5 Terminal metric—five checks

1. the terminal metric ODE;
2. the terminal condition;
3. positive definiteness;
4. the endpoint energy identity;
5. exponential growth of the initial terminal-metric norm.

All symbolic equalities must reduce exactly to zero. Positivity and limiting claims must be established symbolically. No tolerance-based classification is allowed. The receipt records formulas, source hashes, software versions, all checks, and the three classifications below.
The general balance (AM16) and the positive-definite terminal construction are analytical identities. The executable spatial checks use the fixed divergence-free one-dimensional field, and the terminal checks use the extensional control. A `SUPPORTS` classification records agreement between those controls and the displayed derivation; it is not a generic matrix-PDE integration.

## 8. Decision rules

The classifications are fixed before execution.
1. **Exact adaptive cancellation:** `SUPPORTS` only if every branch, scalar, spatial, and terminal identity passes.
2. **Uniform coercivity from the fixed algebraic controls:** `CONTRADICTS` if exact extensional cancellation loses its lower metric bound and the covariance control either assumes bounded live amplitude or omits that amplitude. This classifies unrestricted strain-history and covariance algebra, not a Navier–Stokes-specific estimate. Any missing control gives `INCONCLUSIVE`.
3. **Arbitrary-data Navier–Stokes regularity:** `UNRESOLVED` unless (AM25) is proved from the original equation with constants depending only on $\nu$, $T$, and $R$. The scheduled controls cannot upgrade this classification.

Any failed exact check gives overall `FAIL`. The script must exit nonzero on `FAIL` or an inventory mismatch. Implementation failure gives `ERROR`; repairs may restore the fixed schedule without changing its equations, controls, count, or decision rules.

## 9. Execution and evidence

Run from the repository root:

```bash
python computations/verify_navier_stokes_adaptive_metric.py
```

The script writes a fresh source-bound receipt beneath `runs/navier_stokes_adaptive_metric/`, snapshots the protocol and verifier, and rejects an existing output path. Generated evidence remains local and is indexed through `BROKEN_REFS.md` after qualification.

## References

- `turbulence/navier-stokes-strain-departure.md`—current arbitrary-data critical estimate and smooth periodic controls.
- `turbulence/navier-stokes-stress-geometry.md`—strain freedom, covariance dynamics, and conditional geometric estimates.
- `turbulence/navier-stokes-second-order-field-energy.md`—positive Cassi field symmetrizer and time–curl continuation criterion.
- `CassiFI/cassi_variational_field.py` in the unified workspace—bounded covariance adaptation law and declared observation bound.
- C. Fefferman, [Existence and smoothness of the Navier–Stokes equation](https://www.claymath.org/wp-content/uploads/2022/06/navierstokes.pdf)—official domains, data, and regularity problem.
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the 3-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—stochastic flow representation of viscous transport and stretching.
- E. Miller, [A regularity criterion for the Navier–Stokes equation involving only the middle eigenvalue of the strain tensor](https://arxiv.org/abs/1710.05569)—strain-eigenvalue continuation criterion.
- E. Miller, [On the interaction of strain and vorticity for solutions of the Navier–Stokes equation](https://arxiv.org/abs/2407.02691)—strain–vorticity orthogonality and conditional regularity criteria.
