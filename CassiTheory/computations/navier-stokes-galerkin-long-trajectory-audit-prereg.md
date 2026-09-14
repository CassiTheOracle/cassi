# Independent Direct-Convolution Audit of the Galerkin Remainder

## Status: Pre-registered—September 2026

## Abstract

This schedule independently recomputes a representative part of the longer-horizon
finite-mode Galerkin measurement with full signed Fourier modes and an explicit
mode-by-mode convolution. The audit fixes the normalization connecting the
continuous torus quantities to an odd-grid DFT, checks the orthogonal Leray
projector, and compares the direct convolution with the saved production receipt.
Timestep, product-grid, and cutoff controls are included before execution.

The audit is a deterministic finite-mode calculation for fixed controls, viscosity,
horizon, and cutoffs. Its receipt may support the reproducibility of the sampled
trajectory values at that scope. It does not establish a cutoff-uniform estimate,
a stochastic-flow bound, a continuum limit, or global Navier–Stokes regularity.
No fit, extrapolation, or supremum estimate is permitted.

## 1. Frozen discrete normalization

Work on
\[
\mathbb T^3=(\mathbb R/2\pi\mathbb Z)^3,
\qquad V=(2\pi)^3,
\qquad \nu=0.1,
\qquad T=\frac12.
\]
For an odd grid size $M$, let
\[
\mathcal K_M=\left\{-\frac{M-1}{2},\ldots,\frac{M-1}{2}\right\}^3,
\qquad x_j=\frac{2\pi}{M}j,
\quad j\in\{0,\ldots,M-1\}^3.
\]
The forward and inverse discrete Fourier conventions are
\[
\widehat f_M(k)=\frac1{M^3}\sum_j f(x_j)e^{-ik\cdot x_j},
\qquad
f(x_j)=\sum_{k\in\mathcal K_M}\widehat f_M(k)e^{ik\cdot x_j}.
\]
For a real field, the signed coefficients satisfy
$\widehat f_M(-k)=\overline{\widehat f_M(k)}$. If only the nonnegative
$k_z$ half-spectrum is stored, the Parseval weight is
\[
w_M(k_z)=
\begin{cases}
1,&k_z=0,\\
2,&k_z>0,
\end{cases}
\]
with no Nyquist plane because $M$ is odd. Thus, for real vector fields,
\[
\frac{V}{M^3}\sum_j f(x_j)\cdot g(x_j)
=V\sum_{k\in\mathcal K_M}\widehat f_M(k)\cdot\overline{\widehat g_M(k)}
=V\sum_{k_z\ge0}w_M(k_z)\widehat f_M(k)\cdot\overline{\widehat g_M(k)}.
\]
The audit stores the full signed sum; the production receipt stores the last
half-spectrum form.

For $k\ne0$, the Leray matrix is
\[
\Pi_k=I-\frac{kk^{\mathsf T}}{|k|^2},
\qquad \Pi_0=0.
\]
It is an orthogonal projector: $\Pi_k^{\mathsf T}=\Pi_k$,
$\Pi_k^2=\Pi_k$, and $k^{\mathsf T}\Pi_k=0$. The shell projector is
$\mathbf 1_{0<|k|\le N}\Pi_k$.

For the full signed coefficient array of a zero-mean velocity field supported in
$\Lambda_N=\{k\in\mathbb Z^3:0<|k|\le N\}$, the audit evaluates the nonlinear term
by the explicit convolution
\[
\widehat{(u\cdot\nabla)u}_i(k)
=i\sum_{\substack{p,q\in\Lambda_N\\p+q=k}}
\left(\widehat u(p)\cdot q\right)\widehat u_i(q).
\]
The evolved coefficients therefore obey
\[
\partial_t\widehat u_N(k)
=-\nu|k|^2\widehat u_N(k)
-\Pi_k\widehat{(u_N\cdot\nabla)u_N}(k),
\qquad k\in\Lambda_N.
\]
This is the same projected Galerkin equation as the production measurement,
written without a physical-space product or a rotational-form implementation.
The identity
$\mathbb P_N((u\cdot\nabla)u)=\mathbb P_N(\omega\times u)$
for divergence-free fields explains the rotational implementation in the
production verifier, while the explicit convolution is the independent
implementation used by the audit.

Every retained coordinate frequency is at most $N$. A quadratic right-hand-side
product has coordinate support at most $2N$, and the direct strain observable is
cubic with coordinate support at most $3N$. Hence $M=4N+1$ and $M=6N+1$ make both
quadratic evolution and cubic checkpoint quadrature alias-free. The $M=6N+1$
execution is a spatial-product control, not a new continuum approximation.

Define
\[
\widehat\omega_N(k)=ik\times\widehat u_N(k),
\qquad
W_N=V\sum_k|\widehat\omega_N(k)|^2,
\qquad
D_N=V\sum_k|k|^2|\widehat\omega_N(k)|^2,
\]
and, using the same Galerkin right-hand side,
\[
P_N^{\mathrm{str}}
=\frac12\frac{dW_N}{dt}+\nu D_N,
\qquad
\frac{dW_N}{dt}
=2V\operatorname{Re}\sum_k
\overline{\widehat\omega_N(k)}\cdot
\widehat{\partial_t\omega_N}(k).
\]
The sampled remainder and integral are
\[
\mathfrak m_N(t)=P_N^{\mathrm{str}}(t)-\frac\nu2D_N(t),
\qquad
I_N(T)=\int_0^T(\mathfrak m_N(t))_+\,dt.
\]
At a fixed exact Galerkin state, the signed Parseval sum, the half-spectrum
weighted sum, the direct convolution, and an alias-free grid product represent
the same torus quantities up to roundoff. The RK4 state and composite-trapezoid
integral are numerical approximations, so the audit records timestep changes as
an error diagnostic. A finite cutoff sequence remains descriptive.

## 2. Relation to the Galerkin target

The target in the paper is
\[
\sup_{\substack{N\ge1\\\|u_{0,N}\|_{H^3}\le R_0}}
I_N(T)\le M_{\mathrm{Gal}}(\nu,T,R_0).
\]
The audit evaluates one deterministic value for each fixed tuple
$(u_{0,N},N,\nu,T)$ and compares the independently computed value with the
corresponding saved production row. It does not replace the supremum by a sample,
and no regression or extrapolation in $N$, $T$, or the initial datum is allowed.
The receipt therefore carries evidence about implementation agreement and these
finite trajectories only.

The variables in this audit are deterministic Galerkin quantities. They are not
the stochastic Cauchy replicas, the covariance $R$, the active occupation $M$,
or the recovery and compensation functionals $\mathcal K$ and $\mathcal G$.
Agreement here does not supply a stochastic-flow estimate or the missing
production-relative bound.

## 3. Controls and fixed schedule

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
\qquad
u_{0.1}=u_b+10^{-1}u_{\mathrm{ABC}}.
\]
The audit uses exact signed Fourier coefficients for these analytic controls and
never obtains the initial state by importing the production verifier.

The fixed execution matrix is:

1. **Long recomputation:** all four controls at $N=2$, $T=1/2$, and 2048 RK4
   steps. Record $I_N(T)$, peak positive remainder, initial and final enstrophy,
   maximum positive kinetic-energy increment, divergence residual, and direct
   convolution production at the five checkpoint fractions.
2. **Timestep control:** `rank_two` and `near_rank` at $N=2$ with 4096 steps,
   compared with the 2048-step rows using the denominator
   $\max(1,|I_N(T)|)$.
3. **Product-grid control:** at every long-recomputation checkpoint for all four
   controls, reconstruct the state on $M=9$ and $M=13$ and compare the grid
   integral of $\omega\cdot S\omega$ with an independent signed triple
   convolution. The maximum relative discrepancy uses denominator
   $\max(1,|P_N^{\mathrm{str}}|)$.
4. **Truncation witness:** run `rank_two` and `near_rank` at $N=2$ and $N=4$
   for 512 RK4 steps over the same horizon. Record both cutoff values and their
   difference without imposing a convergence or monotonicity claim.

The long recomputation is compared with the rows in
`runs/navier_stokes_galerkin_long_trajectory_probe_20260914/verification.json`.
The audit does not overwrite that receipt or its frozen protocol.

## 4. Acceptance rules and evidence boundary

The audit is `PASS` only if:

- the computed shell projectors satisfy symmetry and idempotence to $10^{-14}$
  and annihilate their wave numbers to $10^{-14}$;
- every state and observable is finite;
- the explicit convolution state remains divergence-free to $10^{-12}$;
- the signed triple-convolution production agrees with the same-state
  enstrophy-derivative production to $10^{-10}\max(1,D_N)$ at all
  long-recomputation checkpoints;
- the maximum positive kinetic-energy increment is at most
  $10^{-10}\max(1,E(0))$;
- the shear and ABC long-recomputation production residuals are at most
  $10^{-9}\max(1,D_N(0))$;
- each long-recomputation $I_N(T)$ agrees with its saved production row to
  $10^{-8}\max(1,|I_N(T)|)$;
- the timestep-refined relative changes are at most $10^{-6}$; and
- the maximum grid-to-triple-convolution relative discrepancy is at most
  $10^{-10}$.

The $N=2$ versus $N=4$ rows are a finite truncation witness. Their values are
recorded and checked for finiteness only; neither stability nor growth is promoted
to a cutoff statement. A failed audit identifies a reproducibility or numerical
issue at the declared scope and does not alter the theorem status.

The executable records SHA-256 hashes for this protocol, itself, and the saved
production receipt, together with all rows and check details. Generated receipts
remain untracked.

Run from the CassiTheory directory:

```text
python computations/verify_navier_stokes_galerkin_long_trajectory_audit.py
```

## References

- `turbulence/navier-stokes-replica-coherence.md` §7.1—cutoff-uniform Galerkin target and finite-cutoff baseline
- `computations/navier-stokes-galerkin-long-trajectory-prereg.md`—frozen 48-run production schedule
- `computations/verify_navier_stokes_galerkin_long_trajectory.py`—production half-spectrum trajectory verifier
- `turbulence/navier-stokes-near-rank-recovery-obstruction.md`—near-rank control family
