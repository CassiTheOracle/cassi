# Active Stretching with Rank-Deficient Vorticity Gradients: Fixed Control

## Status: Pre-registered—September 2026

## Abstract

This schedule qualifies a smooth periodic initial control whose vorticity-gradient
source is rank deficient while its initial vortex-stretching production is
strictly positive. The control is a two-and-a-half-dimensional periodic field
on the normalized three-torus. Its local Navier–Stokes evolution remains in the
invariant two-and-a-half-dimensional class: the horizontal velocity solves the
two-dimensional Navier–Stokes equation and the vertical velocity is a passive
scalar. Consequently the vorticity is independent of the third coordinate at
every smooth time, so the instantaneous source determinant vanishes throughout
the class.

The schedule checks the explicit velocity, its curl, the full vorticity
transport identity at the initial time, the rank defect, a rank-two witness, and
the exact positive initial stretching average. It does not integrate a generic
Navier–Stokes trajectory, simulate Brownian paths, evaluate the accumulated
rank-recovery functional, or infer global regularity. The result concerns the
boundary of the instantaneous determinant route; temporal accumulation of
transported source ranges remains a separate question.

## 1. Equation and normalization

Work on
\[
\mathbb T^3=(\mathbb R/2\pi\mathbb Z)^3
\]
with normalized spatial average
\[
\langle f\rangle=(2\pi)^{-3}\int_{\mathbb T^3}f(x,y,z)\,dx\,dy\,dz.
\]
The unforced incompressible Navier–Stokes equation is
\[
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad \nu>0.
\tag{RDS1}
\]
Write
\[
\omega=\nabla\times u,
\qquad
L=\nabla u,
\qquad
S=\frac12(L+L^{\mathsf T}),
\qquad
J=\nabla\omega,
\qquad
Q_\omega=JJ^{\mathsf T}.
\]

## 2. Fixed control and its compatible evolution

Set
\[
\theta(x,y)=\sin x+\cos x\sin y,
\qquad
u_0(x,y,z)=\bigl(-\sin y,\ 0,\ \theta(x,y)\bigr).
\tag{RDS2}
\]
The field is smooth, periodic, and mean zero. Its horizontal part is a
periodic two-dimensional shear and its third component is a scalar depending
on the horizontal coordinates.

The invariant two-and-a-half-dimensional class has the form
\[
u(x,y,z,t)=\bigl(v_1(x,y,t),v_2(x,y,t),\vartheta(x,y,t)\bigr),
\qquad
\partial_z v=\partial_z\vartheta=0,
\]
with
\[
\partial_tv+v\cdot\nabla_hv=-\nabla_hp+\nu\Delta_hv,
\qquad \nabla_h\cdot v=0,
\]
\[
\partial_t\vartheta+v\cdot\nabla_h\vartheta=\nu\Delta_h\vartheta.
\tag{RDS3}
\]
The pressure is chosen independent of $z$. Smooth local uniqueness preserves
this class; the two-dimensional Navier–Stokes/passive-scalar system is smooth
for every finite time for smooth data. No closed-form formula for
$(v,\vartheta)$ after $t=0$ is used by the schedule.

At every smooth time in this class,
\[
\omega=(\partial_y\vartheta,-\partial_x\vartheta,
\partial_xv_2-\partial_yv_1),
\qquad
\partial_z\omega=0,
\qquad
\det\nabla\omega=0,
\qquad
\det Q_\omega=0.
\tag{RDS4}
\]

## 3. Full initial-time vorticity compatibility

For the fixed datum, direct differentiation gives
\[
\omega_0=\nabla\times u_0
=\bigl(\cos x\cos y,\ \sin x\sin y-\cos x,\ \cos y\bigr),
\tag{RDS5}
\]
\[
J_0=\nabla\omega_0
=
\begin{pmatrix}
-\sin x\cos y&-\cos x\sin y&0\\
\sin x+\cos x\sin y&\sin x\cos y&0\\
0&-\sin y&0
\end{pmatrix}.
\]
The initial Navier–Stokes vorticity equation, including advection, reaction,
and diffusion, is
\[
\partial_t\omega\big|_{t=0}
=-(u_0\cdot\nabla)\omega_0+L_0\omega_0+\nu\Delta\omega_0.
\tag{RDS6}
\]
The pressure gradient has disappeared only after taking the curl. The
verifier compares the displayed right-hand side with the curl of the full
initial momentum right-hand side, retaining $u_0\cdot\nabla\omega_0$,
$L_0\omega_0$, and $\nu\Delta\omega_0$ as separate exact terms.

## 4. Rank defect and active stretching

The third column of $J_0$ is zero, so its determinant and the source
 determinant vanish. At $(x,y)=(\pi/2,0)$, the first two columns have rank two:
\[
J_0(\pi/2,0)=
\begin{pmatrix}-1&0&0\\1&1&0\\0&0&0\end{pmatrix},
\qquad
Q_\omega(\pi/2,0)
=\begin{pmatrix}1&-1&0\\-1&2&0\\0&0&0\end{pmatrix}.
\tag{RDS7}
\]

The initial strain is
\[
S_0=
\begin{pmatrix}
0&-\frac12\cos y&\frac12(\cos x-\sin x\sin y)\\
-\frac12\cos y&0&\frac12\cos x\cos y\\
\frac12(\cos x-\sin x\sin y)&\frac12\cos x\cos y&0
\end{pmatrix}.
\]
Its stretching density is
\[
\omega_0\cdot S_0\omega_0
=\cos^2x\cos^2y
-\sin x\sin y\cos x\cos^2y,
\]
so
\[
\boxed{\langle\omega_0\cdot S_0\omega_0\rangle=\frac14>0.}
\tag{RDS8}
\]
The invariant evolution from §2 retains $\det\nabla\omega(t)=0$ and hence
$J(t)=\langle|\det\nabla\omega(t)|^{2/3}\rangle=0$ for every smooth time,
while the fixed initial control has positive stretching production.

## 5. Fixed verification inventory

The verifier must execute exactly seven checks with these ordered names:

1. `RD1 mean-zero divergence-free control`
2. `RD2 curl reconstruction`
3. `RD3 full vorticity transport identity`
4. `RD4 rank-deficient source determinant`
5. `RD5 generic rank-two source witness`
6. `RD6 positive initial stretching average`
7. `RD7 invariant 2.5D determinant boundary`

## 6. Decision tree

1. If any fixed exact check fails, classify the run `FAIL` and propagate no
   control result.
2. If all seven checks pass, classify the explicit control as
   `SUPPORTS initial-control validity` and
   `SUPPORTS active stretching with a rank-deficient instantaneous source`.
3. Classify the universal premise that positive stretching requires a positive
   instantaneous determinant source as `CONTRADICTS`.
4. Keep temporal rank accumulation for the covariance $R$, any production-
   relative recovery inequality, and arbitrary-data global regularity
   `UNRESOLVED`.
5. The invariant-class statement and finite-time smoothness are analytical
   properties of the two-dimensional Navier–Stokes/passive-scalar reduction;
   the verifier does not replace those arguments with a trajectory simulation.

## 7. Evidence boundary

The schedule checks exact finite trigonometric identities at the initial time
and the structural third-coordinate invariance of the explicit class. It does
not estimate the magnitude of the accumulated covariance, prove a lower bound
for the determinant-root envelope, establish a singularity, or provide a
continuation theorem. The control shows that the instantaneous full-rank source
functional can vanish along an active stretching trajectory; it makes no claim
about the sharper source-time Gramian, which may recover rank through transported
ranges.

## 8. Sources

- `turbulence/navier-stokes-replica-coherence.md`—instantaneous determinant
  recovery, accumulated source-time Gramian, and production-relative target
- `turbulence/navier-stokes-vorticity-quotient.md`—rank-deficient shear and
  covariance-quotient boundary
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the
  three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—
  stochastic Cauchy vorticity representation
