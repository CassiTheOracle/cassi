# Vorticity-Covariance Quotient

## Status: Derived—September 2026

## Abstract

The vorticity-seeded replica covariance supplies a local normalized quotient
whose reaction stretching cancels exactly. On any smooth cylinder where the
covariance is positive definite, the Mahalanobis quantity
\[
z_R=\omega^{\mathsf T}R^{-1}\omega
\]
obeys a parabolic identity consisting of two nonpositive terms: a covariant
spatial square and the covariance-source quadratic form. The corresponding
seeded second moment \(M=R+\omega\omega^{\mathsf T}\) has a source-free matrix
law, and its normalized mean quotient is bounded by one.

The quotient has a sharp initial-layer boundary. For the periodic ABC Beltrami
heat flow, \(Q_\omega=I\) at the origin at time zero, so
\(R=2\nu tI+O(t^2)\) and \(z_R=3/(2\nu t)+O(1)\). Its unweighted time
integral therefore diverges even on this globally smooth control. Rank-one
shear and zero-source affine branches retain the degenerate covariance
cases. The result identifies a normalized local law and excludes the raw
unweighted quotient as a uniform continuation coefficient; the all-data
regularity estimate remains open.

## 1. Local Navier–Stokes setting

Work on the normalized periodic torus with a smooth mean-zero divergence-free
solution during its smooth interval:

\[
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad
\nabla\cdot u=0,
\qquad
\omega=\nabla\times u,
\qquad
\nu>0.
\tag{1}
\]

Set

\[
L=\nabla u,
\qquad
\mathcal L_u=\partial_t+u\cdot\nabla-\nu\Delta.
\tag{2}
\]

Use the vorticity-seeded covariance from the stochastic Cauchy field:

\[
M=\mathbb E[YY^{\mathsf T}],
\qquad
R=M-\omega\omega^{\mathsf T}\succeq0.
\tag{3}
\]

The exact equations are

\[
\mathcal L_u\omega=L\omega,
\tag{4}
\]

\[
\mathcal L_uR=LR+RL^{\mathsf T}+2\nu Q_\omega,
\qquad
Q_\omega=(\nabla\omega)(\nabla\omega)^{\mathsf T}.
\tag{5}
\]

These identities hold on every compact smooth cylinder covered by the
stochastic Cauchy representation. Since \(R(0)=0\), the inverse construction
below is stated only where \(R\succ0\).

## 2. Inverse-covariance quotient

Let

\[
r=R^{-1},
\qquad
z_R=\omega^{\mathsf T}r\omega,
\qquad
B_k=\partial_k\omega-(\partial_kR)r\omega.
\tag{6}
\]

The inverse rule for the backward parabolic operator is

\[
\mathcal L_ur
=-r(\mathcal L_uR)r
-2\nu\sum_{k=1}^3r(\partial_kR)r(\partial_kR)r.
\tag{7}
\]

The second term is the matrix chain-rule contribution from the Laplacian.
Applying the product rule to \(\omega^{\mathsf T}r\omega\), using (4) and
(5), cancels the reaction matrix:

\[
\begin{aligned}
\mathcal L_uz_R
={}&-2\nu\,\omega^{\mathsf T}rQ_\omega r\omega\\
&-2\nu\sum_{k=1}^3
\left(\partial_k\omega-(\partial_kR)r\omega\right)^{\mathsf T}
 r
\left(\partial_k\omega-(\partial_kR)r\omega\right).
\end{aligned}
\tag{8}
\]

Thus

\[
\boxed{\mathcal L_uz_R\le0.}
\tag{9}
\]

On a periodic cylinder whose covariance remains uniformly positive definite,
the parabolic maximum principle gives
\[
\sup_xz_R(x,t)\le\sup_xz_R(x,s),
\qquad s<t.
\tag{10}
\]
This is a local normalized statement. Its starting value can be singular when
the covariance emerges from \(R(0)=0\), and the positive-definite hypothesis
can fail on rank-deficient source histories.

## 3. Seeded second moment and bounded mean quotient

Define

\[
M=R+\omega\omega^{\mathsf T}.
\tag{11}
\]
The product rule applied to (4) gives
\[
\mathcal L_u(\omega\omega^{\mathsf T})
=L\omega\omega^{\mathsf T}
+\omega\omega^{\mathsf T}L^{\mathsf T}
-2\nu Q_\omega.
\tag{12}
\]
Adding (5) cancels the source:

\[
\boxed{\mathcal L_uM=LM+ML^{\mathsf T}.}
\tag{13}
\]

Where \(M\succ0\), put

\[
z_M=\omega^{\mathsf T}M^{-1}\omega.
\tag{14}
\]
Because \(M-\omega\omega^{\mathsf T}=R\succeq0\), the rank-one update
inequality gives

\[
\boxed{0\le z_M\le1.}
\tag{15}
\]

When \(R\succ0\), the matrix determinant lemma or
Sherman–Morrison formula gives

\[
\boxed{z_M=\frac{z_R}{1+z_R}.}
\tag{16}
\]

The same inverse-covariance calculation using (13) gives

\[
\mathcal L_uz_M
=-2\nu\sum_{k=1}^3
\left(\partial_k\omega-(\partial_kM)M^{-1}\omega\right)^{\mathsf T}
M^{-1}
\left(\partial_k\omega-(\partial_kM)M^{-1}\omega\right)\le0.
\tag{17}
\]
The bounded normalized mean quotient records covariance positivity. It does
not bound \(\operatorname{tr}M\), the enstrophy \(W=\int|\omega|^2dx\), or the
stretching production \(P=\int\omega\cdot S\omega\,dx\).

## 4. Exact controls and the initial-layer obstruction

### 4.1 ABC Beltrami heat flow

On the \(2\pi\)-periodic torus use

\[
v=(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x),
\qquad
u(x,t)=e^{-\nu t}v.
\tag{18}
\]
Here \(\nabla\times v=v\), \(\Delta v=-v\), and the field is a smooth
unforced Navier–Stokes solution. At the origin,

\[
\omega(0,0)=v(0)=(1,1,1),
\qquad
\nabla\omega(0,0)=
\begin{pmatrix}
0&0&1\\
1&0&0\\
0&1&0
\end{pmatrix},
\qquad
Q_\omega(0,0)=I.
\tag{19}
\]

Since \(R(0)=0\), equation (5) gives
\[
R(0,t)=2\nu tI+O(t^2)
\tag{20}
\]
at the origin. Therefore

\[
z_R(0,t)
=\omega(0,0)^{\mathsf T}(2\nu tI)^{-1}\omega(0,0)+O(1)
=\frac{3}{2\nu t}+O(1).
\tag{21}
\]
Consequently,
\[
\int_0^\varepsilon z_R(0,t)\,dt=+\infty
\tag{22}
\]
for every \(\varepsilon>0\). The field itself remains smooth; the divergence
comes from initializing an inverse of a covariance that starts at zero.

### 4.2 Periodic shear

For
\[
u_n(y,t)=e^{-\nu n^2t}\sin(ny)e_1,
\qquad
\omega_n(y,t)=-n e^{-\nu n^2t}\cos(ny)e_3,
\tag{23}
\]
the vorticity gradient has one nonzero row and one nonzero spatial
column. Thus \(Q_\omega\) has rank one and \(\det Q_\omega=0\). The inverse
quotient is unavailable on the unseeded covariance branch, while the exact
flow remains smooth and has zero vortex-stretching production.

### 4.3 Zero-source affine branch

A trace-free homogeneous extensional matrix \(L\) with spatially constant
vorticity gradient has \(Q_\omega=0\). Starting from \(R=0\), equation (5)
leaves \(R=0\), so the inverse quotient is undefined. This branch separates
matrix stretching from covariance generation and prevents a proof from
assuming positive definiteness without a source condition.

## 5. Consequence for continuation searches

The quotient identity provides a maximum-principle route after a positive-
definite covariance has formed. It can support a continuation argument only
with an additional estimate controlling the initial layer, the degenerate
source branches, and the production term in a way that also bounds the full
seeded occupation. The ABC control rules out the direct requirement
\(z_R\in L^1(0,T)\) from time zero.

A weighted quotient, an initial-layer subtraction, or a direct estimate for
\(M\) could still be useful. Each requires a separate data-controlled bound.
The quotient identity therefore sharpens the active covariance program while
leaving the uniform all-data estimate and arbitrary-data global regularity
**UNRESOLVED**.

## 6. Verification evidence

The fixed schedule is
`computations/navier-stokes-vorticity-quotient-prereg.md`. The executable is
`computations/verify_navier_stokes_vorticity_quotient.py`. It checks the exact
local quotient algebra, the seeded source cancellation, the bounded mean
quotient, the ABC initial layer, rank-one shear, and zero-source degeneration.
Generated receipts remain local and untracked.

## References

- `turbulence/navier-stokes-replica-coherence.md`—vorticity-seeded covariance equation, accumulated spread, and continuation envelope
- `turbulence/navier-stokes-deformation-covariance.md`—covariance-inverse weighted law and data-conditioned deformation quotient
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—stochastic Cauchy vorticity representation
- J. Serrin, [On the interior regularity of weak solutions of Navier–Stokes equations](https://link.springer.com/article/10.1007/BF00253344)—periodic continuation criterion
