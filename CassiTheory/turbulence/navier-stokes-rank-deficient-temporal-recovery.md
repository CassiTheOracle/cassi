# Temporal Covariance Rank Recovery in an Active Rank-Deficient Control

## Status: Conditional exact result—September 2026

## Abstract

The published rank-deficient control
[`navier-stokes-rank-deficient-stretching.md`](navier-stokes-rank-deficient-stretching.md)
has positive initial vortex-stretching production while
$\det Q_\omega(t)=0$ throughout its smooth two-and-a-half-dimensional
Navier–Stokes evolution. This supplement asks the distinct temporal question:
can the seeded covariance $R$ recover the missing direction even when the
instantaneous source $Q_\omega$ never has full rank?

Differentiating the exact covariance PDE at $t=0$ gives a positive third-direction
coefficient at the active point $(x,y)=(\pi/2,0)$. Specifically,
\[
\det\!\left(tR_t(0)+\frac{t^2}{2}R_{tt}(0)\right)
=8\nu^4t^4+O(t^5),
\qquad \nu>0.
\]
Thus the covariance has a local temporal rank-recovery mechanism for this
control, separate from instantaneous determinant recovery. The result is a
finite exact time-jet calculation, not a uniform estimate and not a solution
of the three-dimensional global-regularity problem.

## 1. Bound control and exact covariance law

The supplement binds the published control and its seven-check receipt; that
bundle is not modified here. The control is
\[
u_0(x,y,z)=\bigl(-\sin y,\ 0,\ \sin x+\cos x\sin y\bigr).
\]
Its vorticity-gradient source is
\[
Q_\omega=(\nabla\omega)(\nabla\omega)^{\mathsf T},
\]
with $\det Q_\omega(t)=0$ throughout the invariant 2.5D class. The seeded
covariance obeys the exact equation
\[
\mathcal L_uR=LR+RL^{\mathsf T}+2\nu Q_\omega,
\qquad R(0)=0,
\tag{TR1}
\]
where
\[
\mathcal L_u=\partial_t+u\cdot\nabla-\nu\Delta,
\qquad L=\nabla u.
\tag{TR2}
\]
This source-time law is the covariance PDE already used in the replica
analysis; the supplement does not replace it with a trajectory approximation.

## 2. Initial covariance jets

The initial vorticity derivative is taken from the full curl-vorticity equation,
including advection, strain reaction, and diffusion:
\[
\omega_t(0)=-(u_0\cdot\nabla)\omega_0+L_0\omega_0+\nu\Delta\omega_0.
\tag{TR3}
\]
Writing $Q_0=Q_\omega(0)$ and
\[
Q_t(0)=\bigl(\nabla\omega_t(0)\bigr)(\nabla\omega_0)^{\mathsf T}
+\bigl(\nabla\omega_0\bigr)\bigl(\nabla\omega_t(0)\bigr)^{\mathsf T},
\]
differentiation of (TR1) at the zero initial covariance gives
\[
R_1:=R_t(0)=2\nu Q_0,
\tag{TR4}
\]
\[
R_2:=R_{tt}(0)
=-u_0\cdot\nabla R_1+\nu\Delta R_1
+L_0R_1+R_1L_0^{\mathsf T}+2\nu Q_t(0).
\tag{TR5}
\]
The frozen second-order Taylor polynomial is
\[
R_{\mathrm{jet}}(t)=tR_1+\frac{t^2}{2}R_2.
\tag{TR6}
\]

## 3. Active-point calculation

At $p=(x,y)=(\pi/2,0)$, the source and first jet are
\[
Q_0(p)=
\begin{pmatrix}1&-1&0\\-1&2&0\\0&0&0\end{pmatrix},
\qquad
R_1(p)=
\begin{pmatrix}2\nu&-2\nu&0\\-2\nu&4\nu&0\\0&0&0\end{pmatrix}.
\tag{TR7}
\]
The exact second jet from (TR5) is
\[
R_2(p)=
\begin{pmatrix}
8\nu(1-2\nu)&2\nu(6\nu-5)&0\\
2\nu(6\nu-5)&4\nu(1-6\nu)&0\\
0&0&4\nu^2
\end{pmatrix}.
\tag{TR8}
\]
Consequently,
\[
\det R_{\mathrm{jet}}(t)
=8\nu^4t^4+O(t^5).
\tag{TR9}
\]
The $2\times2$ leading block of $R_1(p)$ is positive definite, while the
third diagonal direction first appears as
$\tfrac12(R_2)_{33}t^2=2\nu^2t^2$. Therefore the exact smooth covariance is
positive definite at $p$ for sufficiently small $t>0$, and by continuity on a
spatial neighborhood of $p$. This is a local consequence of the exact
covariance PDE and the displayed time jet.

## 4. Result and boundary

The calculation supports temporal covariance rank recovery for this active
rank-deficient control:

- instantaneous source rank remains at most two;
- initial stretching production is positive, as established by the bound note;
- the covariance's transported/source-time accumulation acquires a third
  direction at second time-jet order;
- no Brownian-path simulation or generic trajectory integration is used.

This does not prove that the determinant-root envelope has a useful uniform
lower bound, nor does it control the production term
$\int S:M$. A production-relative inequality, a bound uniform over an initial
$H^3$ ball, and arbitrary-data global regularity remain `UNRESOLVED`. The
positive coefficient is a control-specific local witness and must not be
promoted to a general continuation estimate.

## 5. Evidence

The standalone verifier
`computations/verify_navier_stokes_rank_deficient_temporal_recovery.py`
checks the exact first and second covariance jets, their active-point matrices,
and the $8\nu^4$ determinant coefficient. Its receipt binds this supplement,
the frozen preregistration, the verifier, and the published rank-deficient
control note. A separate seven-check receipt covers the base-control checks.


## 6. Sources

- `turbulence/navier-stokes-rank-deficient-stretching.md`—published active
  control, vorticity compatibility, positive stretching, and invariant 2.5D
  determinant boundary
- `turbulence/navier-stokes-replica-coherence.md`—seeded covariance equation and
  source-time accumulation
- `computations/navier-stokes-rank-deficient-temporal-recovery-prereg.md`—
  frozen supplement schedule
