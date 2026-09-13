# Vorticity-Covariance Quotient: Fixed Analytical Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule verifies a normalized quotient built from the vorticity-seeded
replica covariance in the original periodic three-dimensional incompressible
Navier–Stokes equation. On a smooth cylinder where the covariance is positive
definite, the quotient
\[
z_R=\omega^{\mathsf T}R^{-1}\omega
\]
has an exact covariant diffusion identity. The reaction matrix cancels, the
remaining terms are nonpositive squares, and the source contributes a second
nonpositive quadratic form. The seeded second moment
\(M=R+\omega\omega^{\mathsf T}\) has the corresponding source-free matrix
law, and its normalized mean quotient is bounded by one.

The schedule also tests the boundary of this route. An exact ABC Beltrami heat
flow has \(Q_\omega(0)=I\), so \(R(t)=2\nu tI+O(t^2)\) at the origin and
\(z_R(t)\sim3/(2\nu t)\). Thus an unweighted time integral of \(z_R\) diverges
on a smooth control. Rank-one shear and zero-source affine controls retain the
singular and degenerate branches. The result is a derived quotient identity
and a precise obstruction to using its raw value as a uniform continuation
coefficient; it is not a global-regularity proof.

## 1. Equation and local domain

Use the normalized periodic torus while a smooth mean-zero divergence-free
solution exists:

\[
\mathcal L_u=\partial_t+u\cdot\nabla-\nu\Delta,
\qquad L=\nabla u,
\qquad \omega=\nabla\times u,
\qquad \nu>0.
\]

The vorticity and replica covariance equations are

\[
\mathcal L_u\omega=L\omega,
\qquad
\mathcal L_uR=LR+RL^{\mathsf T}+2\nu Q_\omega,
\qquad
Q_\omega=(\nabla\omega)(\nabla\omega)^{\mathsf T}.
\tag{1}
\]

All inverse-covariance statements are local in a smooth cylinder on which
\(R(x,t)\succ0\). The initial condition of the replica covariance is
\(R(0)=0\), so the quotient is not assigned a value on the initial slice or
on a spatially degenerate branch.

## 2. Fixed analytical targets

For \(r=R^{-1}\), define

\[
z_R=\omega^{\mathsf T}r\omega,
\qquad
B_k=\partial_k\omega-(\partial_kR)r\omega.
\tag{2}
\]

The fixed identity is

\[
\boxed{
\mathcal L_u z_R
=-2\nu\sum_k B_k^{\mathsf T}rB_k
-2\nu\,\omega^{\mathsf T}rQ_\omega r\omega.}
\tag{3}
\]

The matrix reaction cancels because
\(\mathcal L_uR=LR+RL^{\mathsf T}+2\nu Q_\omega\) and
\(\mathcal L_u\omega=L\omega\). The inverse rule used in the calculation is

\[
\mathcal L_u r
=-r(\mathcal L_uR)r
-2\nu\sum_k r(\partial_kR)r(\partial_kR)r.
\tag{4}
\]

The seeded second moment obeys

\[
M=R+\omega\omega^{\mathsf T},
\qquad
\mathcal L_uM=LM+ML^{\mathsf T}.
\tag{5}
\]

Where \(M\succ0\), set \(z_M=\omega^{\mathsf T}M^{-1}\omega\). Positivity
of \(R=M-\omega\omega^{\mathsf T}\) gives

\[
0\le z_M\le1,
\qquad
z_M=\frac{z_R}{1+z_R}
\quad(R\succ0).
\tag{6}
\]

The same calculation with \(M\) gives a single covariant square:

\[
\mathcal L_u z_M
=-2\nu\sum_k
\left(\partial_k\omega-(\partial_kM)M^{-1}\omega\right)^{\mathsf T}
M^{-1}
\left(\partial_k\omega-(\partial_kM)M^{-1}\omega\right).
\tag{7}
\]

The quotient identity is a local normalized statement. It does not bound
\(\operatorname{tr}M\), \(W\), or the positive stretching production by
itself.

## 3. Fixed controls and obstruction

The verifier evaluates the following exact controls and algebraic branches.

1. A two-dimensional symbolic matrix field with explicit \(w(x)\), \(R(x)\),
   \(L\), and \(Q=w_xw_x^{\mathsf T}\), with time derivatives assigned by
   (1), checks (3) including the spatial covariant square.
2. A constant reaction matrix check isolates cancellation of \(L\) in the
   quotient derivative.
3. The same symbolic field checks the source cancellation in (5).
4. A fixed positive-definite rational matrix checks \(0<z_M<1\) and (6).
5. The periodic ABC field
   \[
   v=(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x)
   \]
   satisfies \(\nabla\times v=v\), and at the origin
   \[
   \omega_0=(1,1,1),
   \qquad
   Q_\omega(0)=I.
   \]
   Hence \(R(t)=2\nu tI+O(t^2)\) and
   \[
   z_R(0,t)=\frac{3}{2\nu t}+O(1).
   \tag{8}
   \]
   The integral of the leading reciprocal-time term diverges.
6. Periodic shear has a rank-one \(Q_\omega\) and vanishing determinant
   source. A homogeneous extensional matrix branch has \(Q_\omega=0\) and
   \(R=0\), so the inverse quotient is undefined there.

The ABC asymptotic is a smooth-control obstruction to any proof that requires
\(z_R\in L^1(0,T)\) without a time weight or an initial-layer subtraction.
It leaves open weighted quotients and estimates tied to the full covariance
and active vorticity, which require separate bounds.

## 4. Fixed check inventory

The verifier records exactly thirteen checks:

- `RQV1 local inverse-covariance quotient identity`
- `RQV2 covariant-square positivity`
- `RQV3 reaction cancellation`
- `RQV4 seeded second-moment source cancellation`
- `RQV5 normalized mean quotient bound`
- `RQV6 Sherman–Morrison quotient relation`
- `RQV7 ABC Beltrami origin geometry`
- `RQV8 ABC covariance initial jet`
- `RQV9 ABC reciprocal-time quotient obstruction`
- `RQV10 periodic shear rank-one source`
- `RQV11 affine zero-source degeneration`
- `RQV12 protocol tags and inventory`
- `RQV13 note anchors and unresolved scope`

The fixed classification is **PASS** only when every exact identity, control,
and source-binding check passes. The scientific result remains limited to the
local quotient identity, the bounded normalized mean quotient, and the
explicit reciprocal-time obstruction. A uniform initial-data estimate and
arbitrary-data global regularity remain **UNRESOLVED**.

## 5. Sources and evidence

The source note is
`turbulence/navier-stokes-vorticity-quotient.md`. The parent replica equation
and covariance convention are in
`turbulence/navier-stokes-replica-coherence.md`; the related covariance-inverse
weighted law is in `turbulence/navier-stokes-deformation-covariance.md`.

From the CassiTheory root, run:

```
python computations/verify_navier_stokes_vorticity_quotient.py \
  --output runs/navier_stokes_vorticity_quotient_20260913/verification.json
```

The verifier binds raw SHA-256 identities for this protocol, the source note,
and its own source. Generated receipts remain local and untracked.
