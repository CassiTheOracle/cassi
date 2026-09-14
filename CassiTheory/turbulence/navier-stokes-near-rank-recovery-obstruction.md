# Near-Rank Full-3D Obstruction to Uniform Covariance Recovery

## Status: Derived—September 2026

## Abstract

A full-rank vorticity-gradient source at every positive perturbation does not
make determinant-root recovery uniformly effective. Start from the smooth
rank-deficient periodic control and add a small ABC Beltrami field:
\[
u_\varepsilon=u_b+\varepsilon w,
\qquad 0<\varepsilon\ll1.
\]
Every $u_\varepsilon$ is smooth, periodic, divergence free, and belongs to one
uniformly bounded $H^3$ family. Its initial source is full rank on an open set,
while
\[
A_\varepsilon:=\left\langle
|\det\nabla\omega_\varepsilon(0)|^{2/3}\right\rangle
\sim A_*\varepsilon^{2/3},
\qquad A_*>0.
\]
The initial seeded stretching production remains exactly $1/4$. Therefore the
accumulated covariance volume starts as
\[
\mathcal K_\varepsilon(t)=6\nu A_\varepsilon t+o(t),
\]
while the seeded occupation increment starts as $t/2+O(t^2)$. The
recovery-only ratio has coefficient $(12\nu A_\varepsilon)^{-1}$ and becomes
unbounded as $\varepsilon\downarrow0$.

Thus no finite recovery-only constant controlled by viscosity and a uniform
initial $H^3$ bound can hold, even after restricting to smooth data whose
initial vorticity-gradient source is full rank almost everywhere. A
production-relative estimate with an occupation or signed-cancellation term
remains the active theorem target; arbitrary-data global regularity remains
**UNRESOLVED**.

## 1. Admissible near-rank family

Work on the normalized $2\pi$-periodic three-torus. Let
\[
u_b(x,y,z)=\bigl(-\sin y,\ 0,\ \sin x+\cos x\sin y\bigr)
\]
and let $w$ be the ABC Beltrami field
\[
w(x,y,z)=\bigl(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x\bigr).
\]
Set
\[
u_\varepsilon=u_b+\varepsilon w,
\qquad 0<\varepsilon\le\varepsilon_0,
\qquad \varepsilon_0=\frac1{10}.
\tag{NR1}
\]
Each summand is a finite trigonometric polynomial with zero mean and zero
divergence, so the family is smooth, periodic, mean zero and divergence free.
The Sobolev triangle inequality gives the uniform bound
\[
\|u_\varepsilon\|_{H^3}
\le\|u_b\|_{H^3}+\varepsilon_0\|w\|_{H^3}=:R_*.
\tag{NR2}
\]
For each member, use the local smooth Navier–Stokes solution with initial data
$u_\varepsilon$. The argument below uses only its initial spatial jets and the
standard smooth short-time expansion.

The base vorticity and the Beltrami perturbation satisfy
\[
\omega_b=\nabla\times u_b
=\bigl(\cos x\cos y,\ \sin x\sin y-\cos x,\ \cos y\bigr),
\qquad
\nabla\times w=w.
\tag{NR3}
\]
Thus
\[
\omega_\varepsilon=\omega_b+\varepsilon w,
\qquad
J_\varepsilon:=\nabla\omega_\varepsilon
=J_b+\varepsilon J_w.
\tag{NR4}
\]

## 2. Full-rank source with a vanishing determinant scale

Write
\[
a=\sin x,\quad b=\cos x,\quad c=\sin y,\quad d=\cos y,
\qquad s=\sin z,\quad r=\cos z.
\]
Direct differentiation gives
\[
J_b=
\begin{pmatrix}
-ad&-bc&0\\
a+bc&ad&0\\
0&-c&0
\end{pmatrix},
\qquad
J_w=
\begin{pmatrix}
0&-c&r\\
b&0&-s\\
-a&d&0
\end{pmatrix}.
\tag{NR5}
\]
Their determinant polynomial is
\[
\det J_\varepsilon=\varepsilon g+\varepsilon^2h+\varepsilon^3k,
\tag{NR6}
\]
where
\[
\begin{aligned}
g&=c\bigl(ad\,s-(a+bc)r\bigr),\\
h&=a^2d r+a c^2s-a b c s-a s+b c d r+(a d-b c)r,\\
k&=-a c s+b d r.
\end{aligned}
\tag{NR7}
\]
The leading function $g$ is not identically zero; for example,
$g(\pi/2,\pi/4,\pi/2)=1/2$. At the same witness,
\[
\det J_\varepsilon
=\frac{\varepsilon}{2}-\frac{\varepsilon^2}{2}
-\frac{\varepsilon^3}{\sqrt2}>0
\qquad (0<\varepsilon\le1/10).
\tag{NR7a}
\]
Continuity gives a positive open region. For every member of the declared
family, $\det J_\varepsilon$ is a nonzero real-analytic function, so its zero
set has measure zero. The source
\[
Q_\varepsilon=J_\varepsilon J_\varepsilon^{\mathsf T}
\]
is full rank almost everywhere for these perturbations.

Define
\[
A_\varepsilon=\left\langle|\det J_\varepsilon|^{2/3}\right\rangle,
\qquad
A_*=\left\langle|g|^{2/3}\right\rangle.
\tag{NR8}
\]
The bounded trigonometric polynomials in (NR6) and dominated convergence give
\[
\boxed{
\varepsilon^{-2/3}A_\varepsilon
=\left\langle|g+\varepsilon h+\varepsilon^2k|^{2/3}\right\rangle
\longrightarrow A_*>0.}
\tag{NR9}
\]
Hence the full-rank source determinant scale collapses like
$\varepsilon^{2/3}$ while the data remain in the fixed ball $R_*$.

## 3. Initial covariance and production coefficients

Let $R_\varepsilon$ be the seeded covariance with $R_\varepsilon(0)=0$ and
$M_\varepsilon=R_\varepsilon+\omega_\varepsilon\omega_\varepsilon^{\mathsf T}$.
The covariance equation gives
\[
R_\varepsilon(t)=2\nu tQ_\varepsilon+O_{C^0}(t^2).
\tag{NR10}
\]
Since $Q_\varepsilon$ is full rank almost everywhere, continuity of the
cube-root determinant and dominated convergence yield
\[
\begin{aligned}
\mathcal K_\varepsilon(t)
&=3\left\langle(\det R_\varepsilon(t))^{1/3}\right\rangle\\
&=6\nu\left\langle|\det J_\varepsilon|^{2/3}\right\rangle t+o(t)\\
&=6\nu A_\varepsilon t+o(t).
\end{aligned}
\tag{NR11}
\]

Let $S_\varepsilon$ be the initial strain. Exact periodic trigonometric
orthogonality gives the polynomial identity
\[
\boxed{
\left\langle\omega_\varepsilon\cdot S_\varepsilon\omega_\varepsilon\right\rangle
=\frac14
\quad\text{for every }\varepsilon.}
\tag{NR12}
\]
At $t=0$, $R_\varepsilon=0$, so the seeded occupation has
\[
\mathcal E_{M_\varepsilon}(t)-\mathcal E_{M_\varepsilon}(0)
=2\left\langle\omega_\varepsilon\cdot S_\varepsilon\omega_\varepsilon\right\rangle t+O(t^2)
=\frac12t+O(t^2).
\tag{NR13}
\]

## 4. Failure of a uniform recovery-only coefficient

Combining (NR11) and (NR13), each fixed positive perturbation satisfies
\[
\lim_{t\downarrow0}
\frac{\mathcal E_{M_\varepsilon}(t)-\mathcal E_{M_\varepsilon}(0)}
{\mathcal K_\varepsilon(t)}
=\frac{1}{12\nu A_\varepsilon}.
\tag{NR14}
\]
By (NR9),
\[
\boxed{
\frac{1}{12\nu A_\varepsilon}
\sim\frac{1}{12\nu A_*}\varepsilon^{-2/3}
\longrightarrow+\infty.}
\tag{NR15}
\]
Suppose a finite constant $C(\nu,R_*)$ bounded the positive seeded occupation
increment by $C(\nu,R_*)\mathcal K_\varepsilon(t)$ for every smooth datum in
this $H^3$ ball and all sufficiently small positive times. Choose $\varepsilon$
so that the limit in (NR14) exceeds that constant, then choose $t$ in the
corresponding short-time regime. The inequality fails.

This obstruction is stronger than a single exactly rank-deficient control: every
fixed $\varepsilon>0$ has a full-rank source almost everywhere, but the family
has no uniform lower source-determinant scale. A positive determinant at each
member supplies no uniform recovery efficiency.

## 5. Consequence for the continuation target

The failed estimate is the recovery-only form
\[
\mathcal E_M(t)-\mathcal E_M(0)\le C\mathcal K_\varepsilon(t).
\tag{NR16}
\]
The production-relative target retains an occupation term, for example
\[
2\int_0^t\left\langle S:M\right\rangle ds\le
\theta\mathcal K(t)+2\int_0^t a(s)\mathcal H(s)\,ds+2\int_0^t b(s)\,ds,
\qquad 0\le\theta<1.
\tag{NR17}
\]
The near-rank family forces any recovery coefficient that absorbs the leading
occupation through $\mathcal K$ alone to become unbounded as the source loses
its third direction. Uniform integrability of the occupation coefficient,
control of $b$, and arbitrary-data global regularity remain **UNRESOLVED**.

## 6. Scope

This is an initial-time theorem for a uniformly bounded family of smooth
periodic data. It uses exact trigonometric identities, the full-rank initial
source asymptotic, and dominated convergence. It invokes local smooth
Navier–Stokes existence only to interpret the time expansion. It does not
integrate a generic trajectory or establish a production-relative estimate.
The result constrains determinant-only recovery routes while leaving the
occupation and signed-cancellation routes open.

## 7. Evidence

The fixed seven-check schedule is
`computations/navier-stokes-near-rank-recovery-obstruction-prereg.md`. Its
source-bound verifier is
`computations/verify_navier_stokes_near_rank_recovery_obstruction.py`. The final
receipt passes **7 of 7 checks** at
`runs/navier_stokes_near_rank_recovery_obstruction_post_source_cleanup_20260913/verification.json`.

The receipt and source snapshots remain local and untracked.

## References

- `turbulence/navier-stokes-covariance-recovery-rate.md`—active-control initial-layer rate boundary
- `turbulence/navier-stokes-rank-deficient-stretching.md`—base rank-deficient control and positive stretching
- `turbulence/navier-stokes-rank-deficient-temporal-coefficient.md`—temporal determinant coefficient and its global sign
- `turbulence/navier-stokes-replica-coherence.md`—accumulated covariance volume and production-relative continuation target
- `computations/navier-stokes-near-rank-recovery-obstruction-prereg.md`—fixed seven-check near-rank schedule
- `computations/verify_navier_stokes_near_rank_recovery_obstruction.py`—near-rank admissibility, determinant-scaling and ratio verifier
