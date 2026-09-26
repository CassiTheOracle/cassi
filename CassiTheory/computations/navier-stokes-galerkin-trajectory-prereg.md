# Short-Time Galerkin Trajectory Remainder: Fixed Probe

## Status: Pre-registered—September 2026

## Abstract

This schedule evolves the exact finite-dimensional Fourier-Galerkin equations for a
small set of smooth periodic controls and measures the time history of the
critical remainder
\[
\mathfrak m_N(t)=P_N^{\mathrm{str}}(t)-\frac{\nu}{2}D_N(t).
\]
It is the first trajectory-level probe attached to the endpoint-control schedule
in `computations/navier-stokes-galerkin-target-prereg.md`. The run tests finite
cutoffs, timestep refinement, and pseudo-spectral reconstruction. It does not
prove a cutoff-uniform bound, integrate arbitrary initial data, or claim
Navier–Stokes regularity.

## 1. Frozen equations and Fourier convention

Work on
\[
\mathbb T^3=(\mathbb R/2\pi\mathbb Z)^3,
\qquad \nu=\frac1{10},
\qquad T=\frac14.
\]
Use Fourier coefficients defined by
\[
u_N(x,t)=\sum_{k\in\mathbb Z^3}\widehat u_N(k,t)e^{ik\cdot x},
\qquad
\widehat u_N(-k)=\overline{\widehat u_N(k)}.
\]
The divergence-free Galerkin shell is
\[
\Lambda_N=\{k\in\mathbb Z^3:0<|k|_2\le N\},
\]
and the zero mode is fixed to zero. For $k\ne0$, the Leray matrix is
\[
\Pi_k=I-\frac{kk^{\mathsf T}}{|k|^2}.
\]
The evolved coefficients satisfy
\[
\partial_t\widehat u_N(k)
=-\nu|k|^2\widehat u_N(k)
-\Pi_k\,\widehat{(u_N\cdot\nabla)u_N}(k),
\qquad k\in\Lambda_N.
\]
The initial field is the exact trigonometric datum projected into $\Lambda_N$;
the projection is checked rather than assumed.

Products are evaluated on an odd $M^3$ uniform periodic grid using
\[
M=4N+1.
\]
Integer wave numbers are reconstructed as
`fftfreq(M) * M` in each axis. Since every retained component has coordinate
magnitude at most $N$, a quadratic product has coordinate magnitude at most
$2N$, while $M/2>2N$; extracting the shell after the product is therefore an
alias-free realization of the quadratic Galerkin coefficient. A grid-refinement
control repeats the primary run with $M=6N+1$.

The recorded unnormalized torus observables use $V=(2\pi)^3$:
\[
W_N=V\sum_k|\widehat\omega_N(k)|^2,
\qquad
D_N=V\sum_k|k|^2|\widehat\omega_N(k)|^2.
\]
At each saved state, the primary production observable is evaluated from the
same spectral right-hand side using the Galerkin enstrophy identity
\[
P_N^{\mathrm{str}}=\frac12\frac{dW_N}{dt}+\nu D_N,
\qquad
\frac{dW_N}{dt}
=2V\,\operatorname{Re}\sum_k
\overline{\widehat\omega_N(k)}
\widehat{\partial_t\omega_N}(k).
\]
At the five fixed times $t/T\in\{0,1/4,1/2,3/4,1\}$, an independent
physical-space calculation reconstructs $\omega_N$ and
$S_N=(\nabla u_N+\nabla u_N^{\mathsf T})/2$ on the same product grid and
evaluates $\int_{\mathbb T^3}\omega_N\cdot S_N\omega_N\,dx$. The direct and
spectral values must agree before the spectral observable is used for the
time integral. The endpoint remainder is
\[
\mathfrak m_N=P_N^{\mathrm{str}}-\frac{\nu}{2}D_N.
\]
The primary integrated observable is
\[
I_N(T)=\int_0^T(\mathfrak m_N(t))_+\,dt,
\]
computed by the composite trapezoidal rule on every RK4 step.

## 2. Frozen controls and resolution schedule

Use these zero-mean divergence-free initial data:
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
The shear and ABC fields are exact heat-flow controls. The $u_b$ and $u_{0.1}$
rows are nonlinear Galerkin trajectories; no exact-flow formula is assumed for
them.

Run every control at
\[
N\in\{2,4,8\},
\]
with RK4 and primary step count $1024$ over $[0,T]$. Repeat every control at
the same cutoff with $2048$ steps. Repeat the $1024$-step run at $M=6N+1$.
The initial endpoint check uses the same $P_N^{\mathrm{str}}(0)$ and $D_N(0)$
convention as (GTC1), and requires the rank-two and near-rank rows to have
$\mathfrak m_N(0)>0$.

## 3. Fixed measurements and acceptance rules

Record, for every control, cutoff, grid, and timestep:

1. $I_N(T)$ and $\max_{0\le t\le T}(\mathfrak m_N(t))_+$;
2. $W_N(0)$, $W_N(T)$, and the maximum positive increment of kinetic energy;
3. the maximum Fourier divergence residual
   $\max_{t,k}|k\cdot\widehat u_N(k,t)|$;
4. the maximum absolute direct-strain production and the maximum direct-versus-
   spectral production discrepancy at the five checkpoints;
5. the maximum relative change in $I_N(T)$ under timestep halving;
6. the maximum relative change in $I_N(T)$ under $M=4N+1\to6N+1$.

A run fails if any state or observable is nonfinite, if the divergence residual
 exceeds $10^{-10}$, if kinetic energy has a positive increment larger than
 $10^{-9}\max(1,E(0))$, if the direct and spectral production values differ by
 more than $10^{-9}\max(1,D_N(t))$ at any checkpoint, or if the direct
 shear/ABC production residual exceeds $10^{-9}\max(1,D_N(0))$. The refinement
 checks fail above relative change $10^{-6}$, using denominator
 $\max(1,|I_N(T)|)$. These are numerical qualification bounds, not estimates
 uniform in $N$.

The result is `PASS` for the finite probe only when all prescribed runs and
controls satisfy these checks. A positive and finite $I_N(T)$ for $u_b$ or
$u_{0.1}$ is recorded as a trajectory measurement; it is not a singularity
witness. The theorem target (68g), production-relative compensation, and
arbitrary-data global regularity remain `UNRESOLVED` under every outcome.

## 4. Evidence boundary and output

The implementation must contain its own Fourier reconstruction, Leray
projection, quadratic product, RK4 stepper, and observable calculation. It must
not import or copy the endpoint-control verifier or a temporary exploratory
script. The receipt records the protocol and executable source hashes, the
complete run matrix, and the measured values. A source-bound receipt is valid
only for the exact source bytes listed in its manifest.

Run from the CassiTheory directory:

```text
python computations/verify_navier_stokes_galerkin_trajectory.py
```

The verifier writes a fresh local receipt under `runs/` when `--output` is
provided or when its default output path is absent. Generated receipts remain
untracked.

## References

- `computations/navier-stokes-galerkin-target-prereg.md`—endpoint remainder definition and finite-mode controls
- `turbulence/navier-stokes-replica-coherence.md` §7.1—Galerkin continuation target (68g)
- `turbulence/navier-stokes-near-rank-recovery-obstruction.md`—bounded near-rank family and positive endpoint production
- `turbulence/navier-stokes-rank-deficient-stretching.md`—rank-deficient periodic control
