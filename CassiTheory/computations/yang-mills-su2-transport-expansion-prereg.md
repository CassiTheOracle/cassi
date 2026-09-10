# Local SU(2) Conditional Transport Expansion

## Status: Frozen confirmatory diagnostic—September 2026

## Abstract

This protocol fixes a finite weak-field calculation for the conditional transport cost of a two-plaquette SU(2) strip. It calibrates the order-one Gaussian kinematic score and computes its first compact-group correction in a rescaled exponential chart. The calculation is a local chart diagnostic for a declared bare Wilson conditional law. The exact interacting Yang–Mills vacuum, chart complement, thermodynamic limit and continuum mass gap require separate estimates.

## 1. Declared conditional law and normalization

Let

\[
U_u(q):=\exp\!\left(\frac{i\sqrt u}{2}q\cdot\sigma\right),
\qquad u>0,
\]

where $q\in\mathbb R^3$ remains in a fixed tame exponential chart. Let $V=U_u(v)$ be the coarse link, $R=U_u(r)$ the vertical link, and $Z=U_u(z)$ the fixed boundary staple. With $\chi(U)=\tfrac12\operatorname{Tr}U$, define the finite conditional law

\[
p_{u,v,z}(R)\,dR
:=Z_{u,v,z}^{-1}
\exp\!\left\{\frac{\kappa}{u}\bigl[\chi(VR)+\chi(ZR)\bigr]\right\}\,dR,
\qquad \kappa>0,
\]

with normalized SU(2) Haar measure $dR$. The block is a two-plaquette Wilson strip with fixed staples. Its compact conditional law is the declared control. No identification with the exact vacuum density $\Omega^2dU$ is made by this protocol.

The weak-field expansion is performed only after the rescaling $V=U_u(v)$, $Z=U_u(z)$, $R=U_u(r)$. The inverse vertical Dirichlet generator is conjugated by the same rescaling:

\[
\widetilde{\mathcal L}_u:=u\,\mathcal L_{SU(2),u},
\]

and the coarse tangent norm is the rescaled group metric at $V$. At $V=I$, the coordinate vectors $e_1,e_2,e_3$ have unit coarse norm at leading order.

## 2. Frozen chart expansion

For fixed $q,r$ in the chart,

\[
1-\chi\bigl(U_u(q)U_u(r)\bigr)
=
\frac u8|q+r|^2
-u^2 A(q,r)+O(u^3),
\]

where

\[
A(q,r):=
\frac{|q|^4+|r|^4}{384}
+\frac{|q|^2|r|^2}{64}
+\frac{(q\cdot r)(|q|^2+|r|^2)}{96}.
\]

The exponential-coordinate Haar Jacobian is

\[
J_u(r)=\left[\frac{\sin(\sqrt u|r|/2)}{\sqrt u|r|/2}\right]^2
=1-\frac u{12}|r|^2+O(u^2).
\]

Set $v=0$ and write $y=r+z/2$. The leading conditional Gaussian is

\[
\nu_{0,z}(dy)\propto
\exp\!\left(-\frac\kappa4|y|^2\right)dy,
\qquad
\operatorname{Cov}_{\nu_{0,z}}(y)=\frac2\kappa I_3.
\]

The rescaled vertical inverse-generator problem uses

\[
\mathcal L_0=-\Delta_y+\frac\kappa2y\cdot\nabla_y.
\]

For a unit coarse tangent $\xi$, the leading score and its Poisson solution are

\[
s_{0,z,\xi}=-\frac\kappa4\,\xi\cdot y,
\qquad
w_{0,z,\xi}=-\frac12\,\xi\cdot y,
\qquad
\mathcal L_0w_{0,z,\xi}=s_{0,z,\xi}.
\]

Therefore the leading conditional transport cost is

\[
\Theta_0^2(z,\xi)
:=\left\langle s_{0,z,\xi},\mathcal L_0^{-1}s_{0,z,\xi}\right\rangle
=\mathbb E_{\nu_{0,z}}|\nabla w_{0,z,\xi}|^2
=\frac14.
\]

This value is the local strip realization of the order-one Gaussian kinematic term. It uses the coarse-tangent unit norm and the rescaled vertical Dirichlet generator.

## 3. Frozen first-order coefficient

Include the order-$u$ Wilson action, Haar Jacobian and group-metric corrections in the conjugated conditional generator. For fixed $z$ and unit $\xi$, expand the complete normalized cost

\[
\Theta_u^2(z,\xi)
:=
\left\langle
s_{u,z,\xi},
\widetilde{\mathcal L}_{u,z}^{-1}s_{u,z,\xi}
\right\rangle_{\nu_{u,z}}
=\frac14+u\,c_1(\kappa,z,\xi)+O(u^2).
\]

The frozen coefficient is

\[
\boxed{
 c_1(\kappa,z,\xi)
 =-\frac1{4\kappa}
 +\frac{|z|^2-(z\cdot\xi)^2}{64}.
}
\]

The first term includes the compact metric and conditional-law correction at identity boundary. The second term records the transverse rescaled boundary dependence. The coefficient is evaluated at the fixed coarse point $V=I$; the full operator theorem would additionally require the essential supremum over coarse $V$ and all admissible boundary data.

## 4. Fixed schedule

Use exactly

\[
\kappa\in\left\{\frac12,1,2,4\right\},
\]

\[
z\in\{(0,0,0),(1,0,0),(1,1,0),(0,1,2)\},
\]

and

\[
\xi\in\{e_1,e_2,e_3\}.
\]

The Cartesian product contains exactly 48 rows. For every row, the primary calculation must record:

1. $\Theta_0^2$;
2. the Poisson perturbation contribution;
3. the vertical metric contribution;
4. $c_1$ and the closed-form target;
5. finite-value assertions for every intermediate scalar.

The primary tolerance for the 48 algebraic rows is $10^{-11}$ in absolute error. The independent reconstruction tolerance is $10^{-10}$.

A fixed-boundary scaling control records the formal substitution

\[
z=\alpha/\sqrt u,
\qquad
U_u(z)=\exp\!\left(\frac{i}{2}\alpha\cdot\sigma\right),
\]

for any nonzero transverse component of $\alpha$. The boundary term in $u c_1$ then remains order one, showing that the tame-chart expansion supplies no uniform full-holonomy boundary estimate. This row is a chart-uniformity diagnostic, not a statement about the exact Yang–Mills spectrum.

## 5. Decision rule

- `PASS_LOCAL`: all 48 rows reproduce $\Theta_0^2=1/4$ and the frozen $c_1$ formula at the stated tolerance.
- `REJECT_CHART_UNIFORMITY`: the fixed compact-boundary scaling control shows that $z=\alpha/\sqrt u$ leaves the tame chart and makes the first correction non-small. A full-holonomy proof therefore needs a separate chart-complement estimate or a different representation.
- `UNRESOLVED_EXACT_VACUUM`: the local strip calculation supplies no estimate for the exact $\Omega^2dU$ conditional law, its boundary-uniform density comparison, global recovery Gramian or continuum limit.

The local result cannot be promoted to the Yang–Mills mass gap. The next theorem-level obligations remain the exact conditional Poincaré estimate (YM29), the recovery lower bound and score upper bound (YM170), and the margin condition (YM151).

## 6. Evidence

Primary verifier:

`computations/verify_yang_mills_su2_transport_expansion.py`

Independent reconstruction:

`computations/verify_yang_mills_su2_transport_expansion_independent.mjs`

Primary receipt:

`runs/yang_mills_su2_transport_expansion/verification.json`

Independent receipt:

`runs/yang_mills_su2_transport_expansion/verification-independent.json`

Both receipts bind the protocol and their own source bytes by SHA-256. The independent receipt also binds the primary source and primary receipt. Generated receipts are local evidence for this finite diagnostic and do not establish an interacting-vacuum theorem.

## References

- `foundations/loop-to-bubble-projection-theorem.md` §§9.20–9.22—conditional score, Poisson transport, recovery Gramian and exact-vacuum obligations.
- `computations/yang-mills-transport-score-prereg.md`—Gaussian controls and scale-margin recurrence.
- `computations/yang-mills-vacuum-block-prereg.md`—exact-vacuum block target and weak-field chart limitations.
