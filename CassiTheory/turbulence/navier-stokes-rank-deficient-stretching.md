# Active Stretching with Rank-Deficient Vorticity Gradients

## Status: Derived conditional—September 2026

## Abstract

A smooth periodic two-and-a-half-dimensional Navier–Stokes control has
strictly positive initial vortex-stretching production while its vorticity
gradient has rank two and zero determinant. The control is
\[
u_0(x,y,z)=\bigl(-\sin y,\ 0,\ \sin x+\cos x\sin y\bigr)
\]
on the normalized $2\pi$-periodic three-torus. Direct differentiation gives
$\det\nabla\omega_0=\det Q_{\omega_0}=0$, a rank-two source witness, and
\[
\left\langle\omega_0\cdot S_0\omega_0\right\rangle=\frac14>0.
\]

The datum belongs to the invariant two-and-a-half-dimensional class. Its
horizontal velocity follows two-dimensional Navier–Stokes and its vertical
velocity is a passive scalar, so the vorticity remains independent of $z$ for
every smooth time and the instantaneous source determinant remains zero. The
The full initial vorticity transport terms—advection, reaction, and diffusion—are
checked explicitly. The control is globally smooth through the standard
two-dimensional reduction.

This result places a boundary on the instantaneous determinant recovery route:
positive vortex stretching can coexist with a rank-deficient vorticity-gradient
source. It leaves temporal accumulation of transported source ranges,
production-relative recovery, and arbitrary-data global regularity
**UNRESOLVED**.

## 1. Equation and normalization

Work on
\[
\mathbb T^3=(\mathbb R/2\pi\mathbb Z)^3
\]
with normalized average
\[
\langle f\rangle=(2\pi)^{-3}\int_{\mathbb T^3}f(x,y,z)\,dx\,dy\,dz.
\]
The unforced incompressible Navier–Stokes equation is
\[
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad \nu>0.
\tag{1}
\]
Use
\[
\omega=\nabla\times u,
\qquad
L=\nabla u,
\qquad
S=\frac12(L+L^{\mathsf T}),
\qquad
Q_\omega=(\nabla\omega)(\nabla\omega)^{\mathsf T}.
\tag{2}
\]

## 2. The fixed periodic control

Set
\[
\theta(x,y)=\sin x+\cos x\sin y,
\qquad
u_0(x,y,z)=\bigl(-\sin y,\ 0,\ \theta(x,y)\bigr).
\tag{3}
\]
The velocity is smooth, periodic, mean zero, and divergence free. Its
vorticity is
\[
\omega_0=\nabla\times u_0
=\bigl(\cos x\cos y,\ \sin x\sin y-\cos x,\ \cos y\bigr).
\tag{4}
\]
The gradient of this vorticity is
\[
J_0=\nabla\omega_0
=
\begin{pmatrix}
-\sin x\cos y&-\cos x\sin y&0\\
\sin x+\cos x\sin y&\sin x\cos y&0\\
0&-\sin y&0
\end{pmatrix}.
\tag{5}
\]

## 3. Full initial vorticity compatibility

For the fixed field, the initial velocity gradient, strain, advective
vorticity term, reaction term, and vorticity Laplacian are
\[
L_0=\nabla u_0=
\begin{pmatrix}
0&-\cos y&0\\
0&0&0\\
\cos x-\sin x\sin y&\cos x\cos y&0
\end{pmatrix},
\tag{6}
\]
\[
S_0=\frac12(L_0+L_0^{\mathsf T}),
\tag{7}
\]
\[
(u_0\cdot\nabla)\omega_0
=
\begin{pmatrix}
\sin x\sin y\cos y\\
-(\sin x+\cos x\sin y)\sin y\\
0
\end{pmatrix},
\tag{8}
\]
\[
L_0\omega_0
=
\begin{pmatrix}
(\cos x-\sin x\sin y)\cos y\\0\\0
\end{pmatrix},
\qquad
\Delta\omega_0
=
\begin{pmatrix}
-2\cos x\cos y\\
-2\sin x\sin y+\cos x\\
-\cos y
\end{pmatrix}.
\tag{9}
\]
Taking the curl of the Navier–Stokes momentum equation gives the full initial
vorticity equation
\[
\partial_t\omega\big|_{t=0}
=-(u_0\cdot\nabla)\omega_0+L_0\omega_0+\nu\Delta\omega_0.
\tag{10}
\]
The pressure gradient is absent at this stage because its curl is zero. The
verification also computes
\[
\nabla\times\bigl(-(u_0\cdot\nabla)u_0+\nu\Delta u_0\bigr)
\]
and checks equality with the right-hand side of (10). Thus the control is
checked as a velocity datum with the complete vorticity transport structure,
not as an independently prescribed vorticity field.

## 4. Rank-deficient source

The third column of $J_0$ vanishes identically. Therefore
\[
\det J_0=0,
\qquad
\det Q_{\omega_0}=\det(J_0J_0^{\mathsf T})=0.
\tag{11}
\]
The defect is exactly rank two at the point $(x,y)=(\pi/2,0)$:
\[
J_0(\pi/2,0)=
\begin{pmatrix}
-1&0&0\\
1&1&0\\
0&0&0
\end{pmatrix},
\qquad
Q_{\omega_0}(\pi/2,0)=
\begin{pmatrix}
1&-1&0\\
-1&2&0\\
0&0&0
\end{pmatrix}.
\tag{12}
\]
The displayed $2\times2$ minor is nonzero, so the rank-two source is a
realized generic branch rather than a zero-gradient specialization.

## 5. Positive initial vortex stretching

The initial stretching density simplifies to
\[
\omega_0\cdot S_0\omega_0
=\cos^2x\cos^2y
-\sin x\sin y\cos x\cos^2y.
\tag{13}
\]
The second term has zero torus average, while the first has average $1/4$.
Consequently,
\[
\boxed{\left\langle\omega_0\cdot S_0\omega_0\right\rangle=\frac14>0.}
\tag{14}
\]
The initial enstrophy derivative is therefore
\[
\frac12W'(0)=
\left\langle\omega_0\cdot S_0\omega_0\right\rangle
-\nu\left\langle|\nabla\omega_0|^2\right\rangle
=\frac14-\nu D_0,
\tag{15}
\]
where the stretching contribution is strictly positive independently of
whether the net derivative is positive for a selected viscosity.

## 6. Invariant two-and-a-half-dimensional evolution

The general class
\[
u(x,y,z,t)=\bigl(v_1(x,y,t),v_2(x,y,t),\vartheta(x,y,t)\bigr)
\]
with $\partial_zv=\partial_z\vartheta=0$ reduces to
\[
\partial_tv+v\cdot\nabla_hv=-\nabla_hp+\nu\Delta_hv,
\qquad \nabla_h\cdot v=0,
\tag{16}
\]
\[
\partial_t\vartheta+v\cdot\nabla_h\vartheta=\nu\Delta_h\vartheta.
\tag{17}
\]
The vorticity is
\[
\omega=(\partial_y\vartheta,-\partial_x\vartheta,
\partial_xv_2-\partial_yv_1),
\qquad \partial_z\omega=0.
\tag{18}
\]
Smooth uniqueness preserves the class. The two-dimensional velocity equation is
globally smooth for smooth data, and the passive scalar equation preserves
smoothness on every finite interval. Thus the control supplies a globally
smooth Navier–Stokes class with
\[
\mathcal J(t):=
\left\langle|\det\nabla\omega(t)|^{2/3}\right\rangle=0
\qquad\text{for every }t\ge0.
\tag{19}
\]

## 7. Consequence for determinant recovery

The instantaneous determinant lower bound in the replica-coherence program
uses $\mathcal J(t)$. Equation (19) makes that lower bound identically zero
throughout this active two-and-a-half-dimensional class, even though (14)
shows positive vortex-stretching production at the initial time. Hence a proof
that positive stretching forces a positive instantaneous full-rank source is
excluded by an admissible smooth periodic control.

The sharper accumulated covariance functional can still gain rank through
transported source ranges at different times. This control does not evaluate
that temporal Gramian or classify the production-relative inequality. It
establishes the narrower boundary: instantaneous source determinant recovery
cannot by itself account for all active stretching. Uniform production-relative
recovery, a data-controlled bound on the recovered envelope, and arbitrary-data
global regularity remain **UNRESOLVED**.

## 8. Verification evidence

The fixed schedule is
`computations/navier-stokes-rank-deficient-stretching-prereg.md`. The source-
bound executable is
`computations/verify_navier_stokes_rank_deficient_stretching.py`. It checks the
seven exact items in that schedule. Generated receipts remain local and
untracked.

## References

- `turbulence/navier-stokes-replica-coherence.md`—instantaneous determinant
  recovery, accumulated source-time Gramian, and production-relative target
- `turbulence/navier-stokes-vorticity-quotient.md`—rank-deficient shear and
  covariance-quotient boundary
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the
  three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—
  stochastic Cauchy vorticity representation
