# Forward Adaptive Metric: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule tests a forward-parabolic version of the positive metric developed in `computations/navier-stokes-adaptive-metric-prereg.md`. A scalar gauge projects the metric-diffusion work away from the vorticity energy while retaining forward diffusion of the metric. The calculation fixes the exact energy law, positive-definiteness mechanism, determinant inequality, an extensional control, and a smooth periodic local-strain control. Uniform lower coercivity remains the decision boundary for an arbitrary-data regularity result.

## 1. Equation and conventions

Use the normalized periodic Navier–Stokes conventions of the parent protocol:

$$
D_t\omega=A\omega+\nu\Delta\omega,
\qquad A=\nabla u,
\qquad \nabla\cdot u=0,
\qquad \nu>0.
$$

For a smooth symmetric matrix field $H(x,t)$, prescribe the forward equation

$$
D_tH+A^{\mathsf T}H+HA-\nu\Delta H=0,
\qquad H(x,0)=I.
\tag{FM1}
$$

This is a forward parabolic system with a congruence-form reaction. It preserves symmetry and positive definiteness through the smooth interval.

Define

$$
Z_H(t)=\int\omega^{\mathsf T}H\omega\,dx,
\qquad
J_H(t)=\int\omega^{\mathsf T}\Delta H\,\omega\,dx,
\qquad
c_H(t)=\frac{J_H(t)}{Z_H(t)}
\tag{FM2}
$$

when $Z_H>0$. Let the scalar gauge $\beta(t)>0$ solve

$$
\frac{\beta'}{\beta}=-2\nu c_H,
\qquad \beta(0)=1,
\tag{FM3}
$$

and put $G=\beta H$. The zero-vorticity solution is handled with $G=H$ and $c_H=0$.

## 2. Exact projected-defect identity

The rescaled metric satisfies

$$
D_tG+A^{\mathsf T}G+GA-\nu\Delta G+2\nu c_HG=0.
\tag{FM4}
$$

Its defect in the general spatial metric balance is

$$
\mathcal R_G
:=D_tG+A^{\mathsf T}G+GA+\nu\Delta G
=2\nu(\Delta G-c_HG).
\tag{FM5}
$$

Since $\Delta G=\beta\Delta H$,

$$
\int\omega^{\mathsf T}\mathcal R_G\omega\,dx
=2\nu\beta(J_H-c_HZ_H)=0.
\tag{FM6}
$$

Therefore

$$
\boxed{
\frac12\frac d{dt}\int\omega^{\mathsf T}G\omega\,dx
+\nu\sum_k\int
(\partial_k\omega)^{\mathsf T}G(\partial_k\omega)\,dx
=0.}
\tag{FM7}
$$

This gives exact forward adaptive cancellation along every smooth solution for which the metric construction exists.

## 3. Positivity and determinant

The reaction in (FM1) has the form $-A^{\mathsf T}H-HA$. Congruence evolution preserves positive definiteness, and forward diffusion averages positive matrices. The scalar gauge is positive by (FM3), so $G\succ0$ through the smooth interval.

The determinant of $H$ obeys

$$
(D_t-\nu\Delta)\log\det H
=\nu\sum_k
\operatorname{tr}
\left[
(H^{-1}\partial_kH)^2
\right]
\ge0.
\tag{FM8}
$$

The matrix inside each trace is similar to the square of the symmetric matrix $H^{-1/2}(\partial_kH)H^{-1/2}$. The periodic minimum principle and $H(0)=I$ give

$$
\det H(x,t)\ge1.
\tag{FM9}
$$

This product bound permits one eigenvalue to decrease while another increases.
The executable schedule below checks the algebraic substitutions and fixed controls. Positive-definite propagation for the general matrix PDE and the minimum-principle step in (FM9) are analytical consequences of the smooth-interval equation; the verifier does not integrate a generic matrix-field trajectory.

## 4. Extensional control

For the spatially homogeneous trace-free generator

$$
A_a=\operatorname{diag}(a,-a,0),
\qquad a>0,
\tag{FM10}
$$

(FM1) gives

$$
H_a(t)=\operatorname{diag}(e^{-2at},e^{2at},1).
\tag{FM11}
$$

Here $\Delta H_a=0$, $c_H=0$, $\beta=1$, and $G=H_a$. Its determinant stays one while

$$
\lambda_{\min}(G)=e^{-2at}\longrightarrow0.
\tag{FM12}
$$

The weighted energy is constant for $z'=A_az$, so the metric absorbs physical stretching through loss of its least eigenvalue.

## 5. Smooth periodic local-strain control

Use the smooth mean-zero divergence-free datum

$$
u_c(x,y,z)=(\sin y,\sin z,\sin x).
\tag{FM13}
$$

At the origin,

$$
S_c(0)=\frac12
\begin{pmatrix}
0&1&1\\
1&0&1\\
1&1&0
\end{pmatrix},
\qquad
\operatorname{spec}S_c(0)=\left\{1,-\frac12,-\frac12\right\}.
\tag{FM14}
$$

Since $H(0)=I$ is spatially constant, (FM1) gives

$$
\partial_tH(0,0)=-2S_c(0),
\qquad
\operatorname{spec}\partial_tH(0,0)=\{-2,1,1\}.
\tag{FM15}
$$

The least metric eigenvalue therefore begins decreasing along a smooth admissible strain direction.

## 6. Coercivity boundary

Equation (FM7) yields Euclidean enstrophy control if one proves

$$
\inf_{0\le t<\min(T,T_*)}
\operatorname*{ess\,inf}_{x\in\mathbb T^3}
\lambda_{\min}G(x,t)
\ge m(\nu,T,R)>0,
\qquad R=\|u_0\|_{H^3},
\tag{FM16}
$$

uniformly over every smooth divergence-free datum with $R$ bounded. Indeed,

$$
\|\omega(t)\|_2^2
\le m(\nu,T,R)^{-1}
\int\omega^{\mathsf T}G\omega\,dx
\le m(\nu,T,R)^{-1}\|\omega_0\|_2^2.
\tag{FM17}
$$

The determinant inequality (FM9) alone does not imply (FM16), as (FM11) shows. Standard matrix maximum-principle estimates introduce the accumulated positive strain and scalar gauge; the fixed schedule contains no data-controlled estimate for those terms.

## 7. Fixed verification inventory

The verifier executes exactly 16 checks.

1. the forward metric residual (FM1) for the extensional control;
2. symmetry of the extensional metric;
3. positive definiteness of the extensional metric;
4. the determinant identity for the extensional metric;
5. collapse of its least eigenvalue;
6. vanishing $J_H$, $c_H$, and scalar-gauge rate in the homogeneous control;
7. the rescaled metric equation (FM4);
8. the defect formula (FM5);
9. the projected-work cancellation (FM6);
10. weighted-energy invariance for an arbitrary extensional state;
11. the spatial log-determinant chain rule used in (FM8) for a fixed nonconstant diagonal positive metric;
12. positivity of that fixed diagonal metric's determinant source;
13. divergence-free and mean-zero properties of (FM13);
14. the exact strain matrix (FM14);
15. the strain and initial metric-derivative spectra (FM14)–(FM15);
16. the norm-equivalence implication (FM17) on a fixed positive metric control.

All equalities reduce symbolically to zero. Positivity and limiting statements use exact factorization, explicit spectra, or symbolic limits. Any failed check or inventory mismatch gives `FAIL`; implementation errors give `ERROR` and may be repaired without changing the equations, controls, count, or decision rules.

## 8. Decision rules

1. **Forward exact cancellation:** `SUPPORTS` only if all 16 checks pass.
2. **Positive-definite metric propagation:** `SUPPORTS` the analytic smooth-interval maximum-principle claim if the congruence/diffusion form and fixed positive controls pass. The executable checks are spot checks rather than a generic matrix-PDE integration.
3. **Uniform lower coercivity from positivity and determinant:** `CONTRADICTS` if the exact extensional control has determinant one and least eigenvalue tending to zero. This is a finite-dimensional algebraic control, not a Navier–Stokes trajectory; it excludes deduction from those metric properties alone.
4. **Arbitrary-data Navier–Stokes regularity:** `UNRESOLVED` unless (FM16) is derived from the original equation with the displayed data dependence.

## 9. Execution and evidence

Run from the repository root:

```bash
python computations/verify_navier_stokes_forward_adaptive_metric.py
```

The script writes an immutable source-bound receipt beneath `runs/navier_stokes_forward_adaptive_metric/`. Generated evidence remains local and is indexed through `BROKEN_REFS.md` after qualification.

## References

- `computations/navier-stokes-adaptive-metric-prereg.md`—parent metric balance, covariance controls, and terminal adjoint construction.
- `turbulence/navier-stokes-stress-geometry.md`—smooth periodic strain control and local strain freedom.
- `turbulence/navier-stokes-strain-departure.md`—current arbitrary-data regularity target.
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the 3-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—positive stochastic flow representation of viscous transport.
