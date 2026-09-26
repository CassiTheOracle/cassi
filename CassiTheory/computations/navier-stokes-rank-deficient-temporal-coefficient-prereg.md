# Global Sign of the Temporal Determinant Coefficient: Fixed Supplement

## Status: Pre-registered—September 2026

## Abstract

This supplement adds one algebraic question to the active rank-deficient control
and its temporal covariance time-jet calculation: what is the sign of the first
nonzero determinant coefficient over the whole periodic $(x,y)$ torus?
The schedule constructs the vorticity-gradient source from explicit source
vectors, differentiates the exact covariance equation at $t=0$, extracts the
$t^4$ coefficient, and reduces it to a sum of squares.

The frozen target is
\[
c_4(x,y)=8\nu^4 f(x,y),
\]
where, with $a=\sin x$, $b=\cos x$, $c=\sin y$, and $d=\cos y$,
\[
f=d^2\left[(c^2-a^2)^2+4a^2b^2c^2\right]
+2a^2c^2(a+bc)^2.
\]
Thus $c_4\ge0$ everywhere and $c_4>0$ on an open set, while the coefficient
can vanish on an explicit lower-dimensional set. This is a global sign result
for the leading local time-jet coefficient, not a global lower bound for the
exact covariance or a continuation estimate.

## 1. Bound controls and source-vector convention

The schedule binds the active periodic control
\[
u_0(x,y,z)=\bigl(-\sin y,\ 0,\ \sin x+\cos x\sin y\bigr)
\]
and the temporal time-jet supplement
`turbulence/navier-stokes-rank-deficient-temporal-recovery.md`. The seven-check
rank-deficient control note is also bound as an unchanged source.

Write
\[
g_k=\partial_k\omega_0\in\mathbb R^3,
\qquad
Q_0=\sum_{k=1}^3g_kg_k^{\mathsf T}
=(\nabla\omega_0)(\nabla\omega_0)^{\mathsf T}.
\tag{GCS1}
\]
For this control, $g_3=0$. Let
\[
n=g_1\times g_2.
\tag{GCS2}
\]
Then $\operatorname{adj}(Q_0)=nn^{\mathsf T}$, including the rank-deficient
case.

## 2. Frozen covariance jet and determinant extraction

Use the exact covariance equation and the full initial vorticity transport law
from the temporal supplement:
\[
R_1=R_t(0)=2\nu Q_0,
\tag{GCS3}
\]
\[
R_2=R_{tt}(0)
=-u_0\cdot\nabla R_1+\nu\Delta R_1
+L_0R_1+R_1L_0^{\mathsf T}+2\nu Q_t(0).
\tag{GCS4}
\]
The frozen polynomial is
\[
R_{\mathrm{jet}}(t)=tR_1+\frac{t^2}{2}R_2.
\tag{GCS5}
\]
Since $R_1=2\nu Q_0$ has rank at most two,
\[
\begin{aligned}
\det R_{\mathrm{jet}}(t)
&=c_4(x,y)t^4+O(t^5),\\
c_4(x,y)
&=\frac12\operatorname{tr}\!\left[\operatorname{adj}(R_1)R_2\right]
=2\nu^2 n^{\mathsf T}R_2n.
\end{aligned}
\tag{GCS6}
\]
The verifier computes the determinant coefficient directly from the Taylor
polynomial and independently compares it with the adjugate contraction.

## 3. Frozen global reduction

The exact trigonometric reduction target is
\[
\boxed{
 c_4(x,y)=8\nu^4\left
a^4c^6-a^4c^4+a^4d^6+4a^3bc^3+2a^2c^2-c^6+c^4
\right).}
\tag{GCS7}
\]
Using $a^2+b^2=1$ and $c^2+d^2=1$, the bracket is exactly
\[
\boxed{
 f=d^2\left[(c^2-a^2)^2+4a^2b^2c^2\right]
+2a^2c^2(a+bc)^2.}
\tag{GCS8}
\]
Every term in (GCS8) is nonnegative. At $(x,y)=(\pi/2,0)$, $f=1$, so the
coefficient is strictly positive there and, by continuity, on a nonempty open
set.

The sum-of-squares form supplies explicit zero branches. If $d\ne0$, the
first bracket can vanish only when $c^2=a^2$ and $abc=0$; the candidate
branch compatible with the unit-circle constraints is $a=c=0$. If $d=0$,
then $c=\pm1$ and the second term vanishes on the branches $a=0$ or
$a+bc=0$. The verifier checks exact identities at representatives of these
branches and positive witnesses away from them; it does not claim a quantified
if-and-only-if zero-set theorem.
\[
\boxed{
\mathcal B
:=\{a=c=0\}
\cup
\{d=0,\ a=0\}
\cup
\{d=0,\ a+bc=0\}.}
\tag{GCS9}
\]

## 4. Fixed verification inventory

The supplement verifier must execute exactly six checks with these ordered names:

1. `GC1 source-vector outer products and dimensions`
2. `GC2 full transport and covariance-jet symmetry`
3. `GC3 adjugate determinant-coefficient identity`
4. `GC4 global trigonometric coefficient reduction`
5. `GC5 sum-of-squares and nonnegativity structure`
6. `GC6 branch identities and positive-region witnesses`

## 5. Decision tree and evidence boundary

1. Any failed exact check classifies this schedule `FAIL`.
2. Six passing checks classify the global leading-coefficient identity as
   `SUPPORTS` and the existence of a positive open coefficient region as
   `SUPPORTS`.
3. The coefficient's nonnegativity does not classify the exact determinant as
   positive at every point or every time. The branch targets in (GCS9) are
   checked only through the representatives and identities specified in GC6.
4. A uniform determinant-root lower bound, a production-relative estimate, and
   arbitrary-data Navier–Stokes global regularity remain `UNRESOLVED`.
5. The schedule runs no stochastic paths, no generic trajectory, and no
   covariance-PDE time integration beyond the exact initial jet.

## 6. Sources

- `turbulence/navier-stokes-rank-deficient-stretching.md`—active control,
  vorticity compatibility, and invariant 2.5D determinant boundary
- `turbulence/navier-stokes-rank-deficient-temporal-recovery.md`—exact initial
  covariance jets and active-point temporal rank witness
- `turbulence/navier-stokes-replica-coherence.md`—seeded covariance equation and
  accumulated source-time Gramian
- P. Constantin and G. Iyer, [A stochastic Lagrangian representation of the
  three-dimensional incompressible Navier–Stokes equations](https://arxiv.org/abs/math/0511067)—
  stochastic Cauchy vorticity representation
