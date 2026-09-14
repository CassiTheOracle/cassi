# Initial-Layer Rate Boundary for Covariance Recovery

## Status: Derived—September 2026

## Abstract

The accumulated covariance determinant grows more slowly than the first-order
seeded stretching on the published rank-deficient periodic control. Using the
exact covariance time jet and its globally nonnegative determinant coefficient,
the spatially integrated determinant-root functional satisfies
\[
\mathcal K(t)=C_{\mathrm{rec}}(\nu)t^{4/3}+o(t^{4/3}),
\qquad C_{\mathrm{rec}}(\nu)>0,
\]
while the seeded occupation increases by
\[
\mathcal E_M(t)-\mathcal E_M(0)=\frac12t+O(t^2).
\]
Consequently, the production increment divided by recovered covariance volume
diverges like $t^{-1/3}$ as $t\downarrow0$. A finite recovery-only coefficient cannot
control this initial layer. The full production-relative continuation target must
retain an additional occupation or signed-cancellation term; its data-uniform
bound remains open.

## 1. Setting and continuation target

Work on the normalized $2\pi$-periodic torus with the smooth unforced
Navier–Stokes control
\[
u_0(x,y,z)=\bigl(-\sin y,\ 0,\ \sin x+\cos x\sin y\bigr),
\qquad \nu>0.
\]
The control is independent of $z$ and belongs to the globally smooth
two-and-a-half-dimensional class described in
`turbulence/navier-stokes-rank-deficient-stretching.md`.

Let $R$ be the seeded covariance and $M=R+\omega\omega^{\mathsf T}$, with
\[
(\partial_t+u\cdot\nabla-\nu\Delta)R
=L R+R L^{\mathsf T}+2\nu Q_\omega,
\qquad R(0)=0,
\]
where $L=\nabla u$ and
$Q_\omega=(\nabla\omega)(\nabla\omega)^{\mathsf T}$. Use normalized spatial
averages throughout:
\[
\mathcal E_M(t)=\left\langle\operatorname{tr}M(t)\right\rangle,
\qquad
\mathcal K(t)=3\left\langle(\det R(t))^{1/3}\right\rangle.
\]
These are the volume-normalized versions of the seeded occupation and recovered
covariance volume in `turbulence/navier-stokes-replica-coherence.md`.

The exact source-bound identity is
\[
\mathcal E_M'(t)=2\left\langle S:M\right\rangle,
\qquad S=\frac12(L+L^{\mathsf T}).
\]
A recovery-only continuation estimate would seek a finite constant, controlled by
$\nu$ and the initial-data size, that bounds the positive occupation increment by
$\mathcal K(t)$ over every time in the smooth interval. The initial layer fixes a
necessary rate for any such proposal.

## 2. Uniform determinant order

Write $R_j=\partial_t^jR|_{t=0}$. Smoothness of this fixed control and its
linear covariance equation give the uniform expansion
\[
R(t)=tR_1+\frac{t^2}{2}R_2+O_{C^0(\mathbb T^3)}(t^3).
\]
The initial vorticity gradient has a zero third spatial column, so
$\det R_1=0$ at every point. Determinant multilinearity therefore gives
\[
\det R(t)=t^4c_4(x,y)+O_{C^0(\mathbb T^3)}(t^5),
\tag{CRR1}
\]
where $c_4$ is the coefficient obtained from the first two covariance jets.
The order follows because every determinant term contains at least one
second-jet factor after the rank-two first-jet contribution is removed.

The global coefficient calculation in
`turbulence/navier-stokes-rank-deficient-temporal-coefficient.md` gives
\[
c_4(x,y)=8\nu^4 f(x,y),
\]
with
\[
\begin{aligned}
f(x,y)={}&d^2\left[(c^2-a^2)^2+4a^2b^2c^2\right]
       +2a^2c^2(a+bc)^2,\\
&a=\sin x,\quad b=\cos x,\quad c=\sin y,\quad d=\cos y.
\end{aligned}
\tag{CRR2}
\]
Every term in (CRR2) is nonnegative, and $f(\pi/2,0)=1$. Thus $c_4\ge0$
everywhere and is positive on a nonempty open region.

Because $R$ is a covariance, it is positive semidefinite and
$\det R(t)\ge0$. Divide (CRR1) by $t^4$ and take the continuous cube root:
\[
\frac{(\det R(t))^{1/3}}{t^{4/3}}
\longrightarrow c_4^{1/3}
\qquad\text{pointwise as }t\downarrow0.
\]
The uniform remainder in (CRR1) bounds the left side by a constant independent
of small $t$. Dominated convergence consequently yields
\[
\begin{aligned}
\mathcal K(t)
&=3t^{4/3}\left\langle c_4^{1/3}\right\rangle+o(t^{4/3})\\
&=\underbrace{6\nu^{4/3}\left\langle f^{1/3}\right\rangle}_{C_{\mathrm{rec}}(\nu)>0}
  t^{4/3}+o(t^{4/3}).
\end{aligned}
\tag{CRR3}
\]
The coefficient in (CRR3) is strictly positive because $f$ is positive on an
open set.

## 3. First-order seeded stretching

At time zero, $R(0)=0$, hence $M(0)=\omega_0\omega_0^{\mathsf T}$. The exact
active-control calculation gives
\[
\left\langle S_0:M_0\right\rangle
=\left\langle\omega_0\cdot S_0\omega_0\right\rangle
=\frac14.
\tag{CRR4}
\]
The smooth covariance and Navier–Stokes fields give a Taylor expansion of the
seeded occupation:
\[
\mathcal E_M(t)-\mathcal E_M(0)
=2\int_0^t\left\langle S:M\right\rangle ds
=\frac12t+O(t^2).
\tag{CRR5}
\]
Combining (CRR3) and (CRR5) gives the sharp initial-layer ratio
\[
\boxed{
\frac{\mathcal E_M(t)-\mathcal E_M(0)}{\mathcal K(t)}
=\frac{1}{12\nu^{4/3}\langle f^{1/3}\rangle}
 t^{-1/3}(1+o(1))
\longrightarrow+\infty.}
\tag{CRR6}
\]

## 4. Consequence for recovery estimates

Equation (CRR6) rules out every estimate of the form
\[
\mathcal E_M(t)-\mathcal E_M(0)\le C\mathcal K(t)
\]
with a finite $C$ valid for all sufficiently small positive times on this one
fixed smooth datum. The same conclusion holds when $C$ is allowed to depend on
$\nu$ and the datum's finite $H^3$ norm. A time-dependent recovery coefficient
in an inequality of this form must satisfy the necessary local growth
$a(t)\gtrsim t^{-1/3}$ along this control. That singularity is locally integrable,
so (CRR6) specifies a rate boundary rather than excluding every time-weighted
recovery formulation.

The result also separates two roles of the accumulated determinant root. It
certifies full covariance rank on an open set at positive time, while its volume
enters at order $t^{4/3}$ and the seeded stretching enters at order $t$. The
recovered volume therefore cannot supply the complete first-order compensation
budget by itself.

The production-relative target in
`turbulence/navier-stokes-replica-coherence.md` retains an occupation term, for
example
\[
2\int_0^t\left\langle S:M\right\rangle ds\le
\theta\mathcal K(t)+2\int_0^t a(s)\mathcal H(s)\,ds+2\int_0^t b(s)\,ds,
\qquad 0\le\theta<1,
\]
where $\mathcal H$ is the residual envelope defined in
`turbulence/navier-stokes-replica-coherence.md`, and $a$ and $b$ are
nonnegative measurable functions. The unresolved step is a bound on $a$ and
$b$ that depends only on the initial $H^3$ ball, viscosity, and finite horizon
for every smooth periodic three-dimensional datum.

## 5. Scope

This is an exact short-time result for one globally smooth periodic control. It
uses the published global sign of the local determinant coefficient, uniform
smooth Taylor expansion, and the exact seeded occupation identity. It contains no
trajectory integration and no numerical time evolution.

The quantifiers required for the Clay regularity problem remain separate: for
every $R_0<\infty$, $T<\infty$, and $\nu>0$, a continuation proof would need a
bound uniform over every smooth mean-zero divergence-free three-dimensional
$u_0$ with $\|u_0\|_{H^3}\le R_0$, valid for every
$0\le t<\min(T,T_*)$. The rate boundary above constrains the form of a covariance
proof; it supplies no such data-uniform bound. Arbitrary-data global regularity
remains **UNRESOLVED**.

## 6. Evidence

The coefficient $c_4$ and its nonnegative representation are derived and checked
in `turbulence/navier-stokes-rank-deficient-temporal-coefficient.md` with
`computations/verify_navier_stokes_rank_deficient_temporal_coefficient.py`. The
active-control stretching identity is established in
`turbulence/navier-stokes-rank-deficient-stretching.md`. Equations (CRR1)–(CRR6)
then follow from determinant multilinearity, covariance positivity, dominated
convergence, and smooth-time Taylor expansion.

The fixed six-check schedule is
`computations/navier-stokes-covariance-recovery-rate-prereg.md`; its independent
quadrature and exact active-point verifier is
`computations/verify_navier_stokes_covariance_recovery_rate.py`. The final receipt
passes **6 of 6 checks** at
`runs/navier_stokes_covariance_recovery_rate_final2_20260913/verification.json` and
records the positive integrated coefficient, determinant order, and
$t^{-1/3}$ leading-ratio boundary. The receipt and source snapshots remain local
and untracked.

## References

- `turbulence/navier-stokes-rank-deficient-stretching.md`—periodic active control, positive initial stretching, and invariant two-and-a-half-dimensional class
- `turbulence/navier-stokes-rank-deficient-temporal-recovery.md`—first two covariance jets and active-point determinant coefficient
- `turbulence/navier-stokes-rank-deficient-temporal-coefficient.md`—global nonnegative coefficient and positive open region
- `turbulence/navier-stokes-replica-coherence.md`—seeded covariance, accumulated determinant-root envelope, and conditional continuation target
- `computations/verify_navier_stokes_rank_deficient_temporal_coefficient.py`—exact source-bound coefficient verifier
- `computations/navier-stokes-covariance-recovery-rate-prereg.md`—fixed six-check integrated-rate verification schedule
- `computations/verify_navier_stokes_covariance_recovery_rate.py`—independent integrated-rate and active-point verifier
