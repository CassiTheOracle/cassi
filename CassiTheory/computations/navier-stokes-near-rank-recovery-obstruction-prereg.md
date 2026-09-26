# Near-Rank Covariance Recovery Obstruction: Fixed Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule verifies the near-rank family in
`turbulence/navier-stokes-near-rank-recovery-obstruction.md`. It checks
admissibility, the exact source determinant polynomial, the torus production
identity, the $\varepsilon^{2/3}$ determinant scale, and the resulting
unbounded recovery-only coefficient. The schedule uses exact symbolic
trigonometric algebra and fixed three-dimensional quadrature. It invokes no
trajectory integration and makes no arbitrary-data regularity claim.

## 1. Frozen family and formulas

On the normalized $2\pi$-periodic torus, use
\[
u_b=(-\sin y,0,\sin x+\cos x\sin y),
\]
\[
w=(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x),
\qquad
u_\varepsilon=u_b+\varepsilon w,
\qquad 0<\varepsilon\le1/10.
\]
The frozen vorticity-gradient matrices are
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
\end{pmatrix},
\]
with $a=\sin x$, $b=\cos x$, $c=\sin y$, $d=\cos y$,
$s=\sin z$, and $r=\cos z$. The determinant polynomial is
\[
\det(J_b+\varepsilon J_w)=\varepsilon g+\varepsilon^2h+\varepsilon^3k,
\]
with the $g,h,k$ expressions in (NR7). The fixed production polynomial is
\[
\left\langle\omega_\varepsilon\cdot S_\varepsilon\omega_\varepsilon\right\rangle
=1/4.
\]

## 2. Fixed check inventory

The verifier executes exactly these seven checks in order:

1. `NR1 perturbation is periodic, mean-zero, divergence-free`
2. `NR2 determinant polynomial matches g, h, k`
3. `NR3 production polynomial averages to one quarter`
4. `NR4 leading determinant function is positive on an open set`
5. `NR5 determinant scale converges as epsilon^(2/3)`
6. `NR6 full-rank source yields linear covariance volume`
7. `NR7 recovery-only coefficient is unbounded on bounded family`

The exact checks use SymPy. The numerical checks use an $N^3$ periodic midpoint
quadrature with $N=32$ and
$\varepsilon\in\{10^{-1},10^{-2},10^{-3},10^{-4}\}$. The scale check requires
finite values, a nonzero sampled determinant fraction, and relative agreement
below $3\times10^{-2}$ between the smallest-$\varepsilon$ scaled integral and
the sampled $\langle|g|^{2/3}\rangle$. The full-rank covariance check uses
$\det(2\nu Q)^{1/3}=2\nu|\det J|^{2/3}$ for positive $\nu$ and checks the
factor $3$ in $\mathcal K=3\langle(\det R)^{1/3}\rangle$.

The family check verifies the symbolic divergence identity and the displayed
witness
\[
g(\pi/2,\pi/4,\pi/2)=1/2,
\qquad
\det J_\varepsilon
=\varepsilon/2-\varepsilon^2/2-\varepsilon^3/\sqrt2>0
\]
for the declared epsilon range. The production check requires the exact
coefficient vector $(1/4,0,0,0)$ after torus integration in powers of
$\varepsilon$. The recovery-only ratio check uses
$C_\varepsilon=(12\nu A_\varepsilon)^{-1}$ at $\nu=0.7$ and requires strict
growth as $\varepsilon$ decreases, with the smallest epsilon coefficient at
least ten times the largest epsilon coefficient in the fixed set.

## 3. Decision rule and boundary

A failed symbolic identity, nonfinite quadrature value, insufficient scale
agreement, or non-growing recovery coefficient gives `FAIL`. Seven passing
checks qualify the near-rank determinant-scale obstruction for the declared
family. The schedule records a uniform Sobolev-family bound by the triangle
inequality; it does not compute an $H^3$ norm numerically. Production-relative
occupation coefficients, signed-cancellation estimates, and arbitrary-data
global regularity remain `UNRESOLVED`.

## 4. Execution

From the CassiTheory directory, run:

```text
python computations/verify_navier_stokes_near_rank_recovery_obstruction.py
```

The verifier writes a fresh source-bound receipt under `runs/` when `--output`
is supplied or when the default output is absent. The receipt remains local and
untracked.

## References

- `turbulence/navier-stokes-near-rank-recovery-obstruction.md`—near-rank family and recovery-only obstruction
- `turbulence/navier-stokes-covariance-recovery-rate.md`—active-control rate boundary
- `turbulence/navier-stokes-rank-deficient-stretching.md`—base control and positive stretching identity
- `turbulence/navier-stokes-rank-deficient-temporal-coefficient.md`—covariance determinant coefficient context
