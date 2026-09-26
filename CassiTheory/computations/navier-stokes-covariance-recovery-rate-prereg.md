# Initial-Layer Covariance Recovery Rate: Fixed Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule verifies the integrated coefficient and scaling statement in
`turbulence/navier-stokes-covariance-recovery-rate.md`. The calculation uses the
closed formula for the exact leading determinant coefficient, fixed periodic
quadrature, and the displayed leading-order production and recovery laws. It
records the initial-layer rate boundary without integrating a Navier–Stokes
trajectory or a covariance PDE in time.

## 1. Frozen formulas

Use the normalized $2\pi$-periodic torus and
\[
a=\sin x,\qquad b=\cos x,\qquad c=\sin y,\qquad d=\cos y.
\]
The frozen coefficient is
\[
f(x,y)=d^2\left[(c^2-a^2)^2+4a^2b^2c^2\right]
       +2a^2c^2(a+bc)^2,
\]
so
\[
c_4(x,y)=8\nu^4f(x,y),
\qquad
C_{\mathrm{rec}}(\nu)=6\nu^{4/3}\left\langle f^{1/3}\right\rangle.
\]
The active-control production coefficient is fixed by
\[
\mathcal E_M(t)-\mathcal E_M(0)=\frac12t+O(t^2),
\]
and the determinant-root leading law is
\[
\mathcal K(t)=C_{\mathrm{rec}}(\nu)t^{4/3}+o(t^{4/3}).
\]

## 2. Fixed check inventory

The verifier executes exactly these six checks in order:

1. `CRR1 coefficient formula is nonnegative on fixed torus grids`
2. `CRR2 integrated recovery coefficient is finite and positive`
3. `CRR3 rank-two jet has determinant order four`
4. `CRR4 positive coefficient occupies an open sampled region`
5. `CRR5 active seeded-production coefficient is one half`
6. `CRR6 leading ratio has t^{-1/3} scaling`

The grids are $N\times N$ with $N\in\{32,64,128,256\}$. The quadrature is the
uniform periodic midpoint rule. The coefficient qualification requires every
sampled value to be finite and satisfy
$\min f\ge-10^{-12}$, with $f(\pi/2,0)=1$ to floating tolerance, and
$\langle f^{1/3}\rangle>0$. The reported refinement comparison between $N=128$
and $N=256$ must have relative difference below $10^{-3}$. The exact formula is
the primary result; this comparison supplies a numerical qualification of its
integral.

The rank-order check uses the displayed active-point matrices from the temporal
supplement with symbolic positive $\nu$ and requires the coefficients of powers
$t^0,t^1,t^2,t^3$ to vanish and the $t^4$ coefficient to equal $8\nu^4$.
The production coefficient check requires $2(1/4)=1/2$. The ratio check evaluates
only the frozen leading expressions at
$t\in\{10^{-2},10^{-3},10^{-4}\}$ and requires
$t^{1/3}[\frac12t/(C_{\mathrm{rec}}t^{4/3})]$ to agree across those times within
$10^{-12}$ and the unscaled ratio to increase strictly as $t$ decreases.

## 3. Decision rule and boundary

A nonfinite value, failed exact coefficient, failed refinement threshold, or
failed scaling comparison gives `FAIL`. Six passing checks qualify the integrated
leading coefficient and the $t^{-1/3}$ initial-layer ratio for the fixed control.
The schedule makes no claim about a uniform lower bound, a production-relative
estimate with an occupation term, a generic smooth trajectory, or arbitrary-data
global regularity. Those statements remain `UNRESOLVED`.

## 4. Execution

From the CassiTheory directory, run:

```text
python computations/verify_navier_stokes_covariance_recovery_rate.py
```

The verifier writes a fresh receipt under `runs/` when `--output` is supplied or
when the default output does not already exist. It snapshots the note, this
protocol, the coefficient note, and the verifier. The receipt is local evidence
and remains untracked.

## References

- `turbulence/navier-stokes-covariance-recovery-rate.md`—initial-layer asymptotic and recovery-only rate boundary
- `turbulence/navier-stokes-rank-deficient-temporal-coefficient.md`—exact global coefficient formula
- `turbulence/navier-stokes-rank-deficient-temporal-recovery.md`—active-point covariance time jet
- `turbulence/navier-stokes-rank-deficient-stretching.md`—positive initial stretching identity
