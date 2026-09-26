# Global Sign of the Temporal Covariance Determinant Coefficient

## Status: Derived—September 2026

## Abstract

The active rank-deficient control
[`navier-stokes-rank-deficient-stretching.md`](navier-stokes-rank-deficient-stretching.md)
has an instantaneous vorticity-gradient source of rank at most two. Its seeded
covariance nevertheless develops a missing direction at second time-jet order,
as shown in the temporal supplement
[`navier-stokes-rank-deficient-temporal-recovery.md`](navier-stokes-rank-deficient-temporal-recovery.md).
This note determines the sign of that first nonzero determinant coefficient over
the whole periodic $(x,y)$ torus.

The exact coefficient is
\[
c_4(x,y)=8\nu^4 f(x,y),
\qquad \nu>0,
\]
where, with
\[
a=\sin x,\qquad b=\cos x,\qquad c=\sin y,\qquad d=\cos y,
\]
\[
\boxed{
 f(x,y)=d^2\left[(c^2-a^2)^2+4a^2b^2c^2\right]
 +2a^2c^2(a+bc)^2.}
\]
Thus the leading coefficient is nonnegative everywhere and strictly positive
on a nonempty open set. The SOS form also displays explicit zero branches,
which are recorded below as branch targets. The executable evidence checks
those branch identities and positive witnesses; it does not claim a quantified
if-and-only-if zero-set theorem.
This is a global sign statement for a local-in-time coefficient. It is not a
uniform lower bound for the exact covariance, a production estimate, or a
three-dimensional regularity proof.

## 1. Control and source vectors

The control is
\[
u_0(x,y,z)=\bigl(-\sin y,\ 0,\ \sin x+\cos x\sin y\bigr).
\]
Its initial vorticity is
\[
\omega_0=\bigl(\cos x\cos y,\ \sin x\sin y-\cos x,\ \cos y\bigr),
\]
and its source vectors are
\[
\begin{aligned}
g_1&=\partial_x\omega_0
=\bigl(-\sin x\cos y,\ \sin x+\cos x\sin y,\ 0\bigr),\\
g_2&=\partial_y\omega_0
=\bigl(-\cos x\sin y,\ \sin x\cos y,\ -\sin y\bigr),\\
g_3&=\partial_z\omega_0=0.
\end{aligned}
\]
The source matrix is the explicit outer-product sum
\[
Q_0=\sum_{k=1}^3g_kg_k^{\mathsf T}
=(\nabla\omega_0)(\nabla\omega_0)^{\mathsf T}.
\]
Put
\[
n=g_1\times g_2.
\]
For a $3\times2$ source matrix with columns $g_1,g_2$, the adjugate identity
\[
\operatorname{adj}(Q_0)=nn^{\mathsf T}
\]
holds even when the source is rank deficient.

## 2. Covariance time jet

The exact seeded covariance law is
\[
(\partial_t+u\cdot\nabla-\nu\Delta)R
=LR+RL^{\mathsf T}+2\nu Q_\omega,
\qquad R(0)=0.
\]
The initial vorticity derivative uses the full transport equation
\[
\omega_t(0)=-(u_0\cdot\nabla)\omega_0+L_0\omega_0+\nu\Delta\omega_0.
\]
Writing $R_1=R_t(0)$ and $R_2=R_{tt}(0)$ gives
\[
R_1=2\nu Q_0,
\]
\[
R_2=-u_0\cdot\nabla R_1+\nu\Delta R_1
+L_0R_1+R_1L_0^{\mathsf T}+2\nu Q_t(0).
\]
The frozen polynomial is
\[
R_{\mathrm{jet}}(t)=tR_1+\frac{t^2}{2}R_2.
\]
Because $R_1$ has rank at most two,
\[
\det R_{\mathrm{jet}}(t)=c_4(x,y)t^4+O(t^5),
\]
with
\[
c_4(x,y)
=\frac12\operatorname{tr}\!\left[\operatorname{adj}(R_1)R_2\right]
=2\nu^2n^{\mathsf T}R_2n.
\]

## 3. Exact coefficient reduction

Direct exact differentiation of the covariance law and reduction with
$a^2+b^2=1$ and $c^2+d^2=1$ gives
\[
c_4(x,y)=8\nu^4 f(x,y),
\]
where
\[
f(x,y)=d^2\left[(c^2-a^2)^2+4a^2b^2c^2\right]
+2a^2c^2(a+bc)^2.
\]
The same expression in expanded trigonometric form is
\[
f=a^4c^6-a^4c^4+a^4d^6+4a^3bc^3+2a^2c^2-c^6+c^4.
\]
The two formulas are identical by the unit-circle identities. Each term in
the boxed form is nonnegative, so
\[
\boxed{c_4(x,y)\ge0\quad\text{for all }(x,y)\in\mathbb T^2.}
\]
At $(x,y)=(\pi/2,0)$, $(a,b,c,d)=(1,0,0,1)$ and $f=1$, hence
$c_4=8\nu^4>0$. Continuity gives a nonempty open positive region.

## 4. Zero branches

The sum-of-squares form supplies the following branch targets. If $d\ne0$, the
first bracket can vanish only when $c^2=a^2$ and $abc=0$; the unit-circle
constraints leave $a=c=0$ as the candidate branch. If $d=0$, then $c=\pm1$
and the second term vanishes on the branches $a=0$ or $a+bc=0$:
\[
\mathcal B
:=\{a=c=0\}
\cup\{d=0,\ a=0\}
\cup\{d=0,\ a+bc=0\}.
\]
The displayed reductions are useful branch identities, but this supplement
does not use them as an independently verified if-and-only-if classification.
The complement witnesses used by the verifier are strictly positive.

## 5. Scope

This result refines the temporal rank-recovery control without changing the
instantaneous source conclusion: $\det Q_\omega(t)=0$ remains true throughout
the invariant 2.5D class. It establishes a global sign for one local
time-jet coefficient and records branch targets for that coefficient.

It does not prove a positive lower bound uniform in space, time, viscosity,
or initial data. It does not bound the determinant-root envelope or the
production term $\int S:M$. A production-relative estimate, a uniform
initial-$H^3$ bound, and arbitrary-data Navier–Stokes global regularity remain
`UNRESOLVED`.

## 6. Evidence

The standalone verifier
`computations/verify_navier_stokes_rank_deficient_temporal_coefficient.py`
reconstructs the source vectors as $3\times1$ columns, forms all covariance
terms as $3\times3$ outer products, differentiates the exact initial jet, and
checks the adjugate identity, coefficient reduction, sum-of-squares form,
branch identities, and positive-region witnesses. Its receipt binds this
note, the preregistration, the published active-control note, and the
temporal-recovery supplement.

## 7. Sources

- `turbulence/navier-stokes-rank-deficient-stretching.md`—active periodic
  control and invariant 2.5D determinant boundary
- `turbulence/navier-stokes-rank-deficient-temporal-recovery.md`—exact initial
  covariance time jet and active-point coefficient
- `turbulence/navier-stokes-replica-coherence.md`—seeded covariance equation and
  accumulated source-time Gramian
- `computations/navier-stokes-rank-deficient-temporal-coefficient-prereg.md`—
  fixed global coefficient-sign schedule
