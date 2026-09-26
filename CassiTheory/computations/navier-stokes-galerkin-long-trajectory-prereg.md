# Longer-Horizon Galerkin Trajectory Remainder: Fixed Probe

## Status: Pre-registered—September 2026

## Abstract

This schedule extends the finite-mode trajectory measurement for the Galerkin
endpoint remainder from a short initial interval to a longer fixed interval:
\[
\mathfrak m_N(t)=P_N^{\mathrm{str}}(t)-\frac{\nu}{2}D_N(t),
\qquad
I_N(T)=\int_0^T(\mathfrak m_N(t))_+\,dt.
\]
It tests whether the positive trajectory remainder remains numerically
controlled when the integration window is doubled and the cutoff reaches
$N=16$. The run remains a finite-mode measurement for four fixed smooth
controls. It does not prove a cutoff-uniform estimate, integrate arbitrary
initial data, or establish Navier–Stokes regularity.

## 1. Frozen equations and observable

Work on
\[
\mathbb T^3=(\mathbb R/2\pi\mathbb Z)^3,
\qquad \nu=\frac1{10},
\qquad T=\frac12.
\]
For the Fourier coefficients
\[
u_N(x,t)=\sum_{k\in\mathbb Z^3}\widehat u_N(k,t)e^{ik\cdot x},
\qquad
\widehat u_N(-k)=\overline{\widehat u_N(k)},
\]
evolve the zero-mean divergence-free Galerkin equation on
\[
\Lambda_N=\{k\in\mathbb Z^3:0<|k|_2\le N\},
\]
with
\[
\partial_t\widehat u_N(k)
=-\nu|k|^2\widehat u_N(k)
-\Pi_k\,\widehat{(u_N\cdot\nabla)u_N}(k),
\qquad
\Pi_k=I-\frac{kk^{\mathsf T}}{|k|^2}.
\]

Products are evaluated on an odd $M^3$ periodic grid with $M=4N+1$. Every
retained coordinate wave number has magnitude at most $N$, so a quadratic
product has coordinate magnitude at most $2N$ and the grid has no quadratic
aliasing. The grid-refined execution uses $M=6N+1$.

Use unnormalized torus integrals with $V=(2\pi)^3$:
\[
W_N=V\sum_k|\widehat\omega_N(k)|^2,
\qquad
D_N=V\sum_k|k|^2|\widehat\omega_N(k)|^2.
\]
At each saved state, evaluate the primary strain-production observable from
the same-state Galerkin right-hand side:
\[
P_N^{\mathrm{str}}
=\frac12\frac{dW_N}{dt}+\nu D_N,
\qquad
\frac{dW_N}{dt}
=2V\operatorname{Re}\sum_k
\overline{\widehat\omega_N(k)}\widehat{\partial_t\omega_N}(k).
\]
At the five fixed checkpoint fractions
$t/T\in\{0,1/4,1/2,3/4,1\}$, independently reconstruct
\[
\omega_N=\nabla\times u_N,
\qquad
S_N=\frac12(\nabla u_N+\nabla u_N^{\mathsf T})
\]
on the product grid and evaluate
$\int_{\mathbb T^3}\omega_N\cdot S_N\omega_N\,dx$. The direct value must
agree with the same-state spectral value before the spectral time history is
used. Define
\[
\mathfrak m_N=P_N^{\mathrm{str}}-\frac{\nu}{2}D_N,
\qquad
I_N(T)=\int_0^T(\mathfrak m_N(t))_+\,dt,
\]
with the composite trapezoidal rule on every primary RK4 step.

## 2. Frozen controls and run matrix

Use the four zero-mean divergence-free controls
\[
u^{\mathrm{sh}}=(-\sin(2y),0,0),
\]
\[
u_{\mathrm{ABC}}
=(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x),
\]
\[
u_b=(-\sin y,0,\sin x+\cos x\sin y),
\]
\[
u_{0.1}=u_b+10^{-1}u_{\mathrm{ABC}}.
\]
The shear and ABC rows are exact heat-flow controls. The $u_b$ and $u_{0.1}$
rows are evolved as nonlinear Galerkin trajectories.

Use the cutoff set
\[
N\in\{2,4,8,16\}.
\]
For every control and cutoff, run:

1. primary RK4 with 2048 equal steps over $[0,T]$ and $M=4N+1$;
2. timestep refinement with 4096 steps at the same cutoff and grid;
3. product-grid refinement with 2048 steps and $M=6N+1$.

The complete matrix has $4\times4\times3=48$ executions. The $N=16$
product grids have $M=65$ and are part of the declared primary/refinement
contract; they are not optional stress tests.

## 3. Measurements and acceptance rules

Record for every execution:

1. $I_N(T)$ and $\max_{0\le t\le T}(\mathfrak m_N(t))_+$;
2. $W_N(0)$, $W_N(T)$, and the maximum positive kinetic-energy increment;
3. the maximum Fourier divergence residual over all states;
4. direct strain production at all five checkpoints, its maximum absolute value,
   and direct-versus-spectral discrepancy;
5. the relative change in $I_N(T)$ under timestep halving;
6. the relative change in $I_N(T)$ under product-grid refinement;
7. the cutoff sequence $I_2(T),I_4(T),I_8(T),I_{16}(T)$ for each control.

A run fails if any state or observable is nonfinite, if the divergence residual
exceeds $10^{-10}$, if the maximum positive kinetic-energy increment exceeds
$10^{-9}\max(1,E(0))$, or if direct and spectral production differ by more
than $10^{-9}\max(1,D_N(t))$ at a checkpoint. The shear and ABC direct
production residual fails above $10^{-9}\max(1,D_N(0))$. Timestep and grid
refinement fail above relative change $10^{-6}$, with denominator
$\max(1,|I_N(T)|)$.

The cutoff sequence is descriptive evidence rather than a theorem gate. A
positive or growing sequence does not witness a singularity, and a stable
sequence at these four cutoffs does not prove a bound as $N\to\infty$.

The overall result is `PASS` for this finite probe only when every declared
execution satisfies the state, checkpoint, conservation, and refinement
checks. The receipt classification is
`SUPPORTS—longer-horizon finite-mode trajectory measurement only` when all
checks pass. The Galerkin target (68g), production-relative compensation, and
arbitrary-data global regularity remain `UNRESOLVED` under every outcome.

## 4. Independent implementation and evidence boundary

The executable must contain its own Fourier reconstruction, Leray projection,
quadratic product, RK4 stepper, and observable calculation. It must not import
the short-time trajectory verifier or the endpoint-control verifier. The
implementation records the protocol and executable SHA-256 hashes, the full
48-run matrix, all measured values, and the cutoff sequence.

The run tests one fixed viscosity, one finite horizon, four analytic controls,
and four finite cutoffs. It supplies no estimate uniform in cutoff, no result
for arbitrary $H^3$ data, no stochastic-flow integration, and no continuation
or regularity theorem.

Run from the CassiTheory directory:

```text
python computations/verify_navier_stokes_galerkin_long_trajectory.py
```

The verifier writes a fresh local receipt under `runs/` when `--output` is
provided or when its default output path is absent. Generated receipts remain
untracked.

## References

- `computations/navier-stokes-galerkin-trajectory-prereg.md`—short-time trajectory observable and reconstruction conventions
- `computations/navier-stokes-galerkin-target-prereg.md`—finite-mode endpoint target and initial controls
- `turbulence/navier-stokes-replica-coherence.md` §7.1—Galerkin continuation target (68g)
- `turbulence/navier-stokes-near-rank-recovery-obstruction.md`—bounded near-rank family and positive endpoint production
