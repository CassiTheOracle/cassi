# Positive Galerkin Remainder Firing Audit

## Status: Pre-registered—September 2026

## Abstract

This schedule exercises the positive branch of the Galerkin enstrophy-remainder observable with a real divergence-free control at a larger, explicitly fixed initial $H^3$ radius. The branch audit complements the fixed-radius exploratory sequence at $R=1$, whose selected arms remain viscously dominated. It records the number of positive-part evaluations, a positive initial remainder, and a nonzero integrated remainder. The audit tests observable sensitivity only; it supplies no cutoff-uniform estimate, trajectory theorem, or global-regularity result.

## 1. Frozen control and observable

Work on the $2π$-periodic torus with unnormalized integrals, viscosity $ν=1/10$, and horizon $T=1/2$. Use the low-mode divergence-free field

$$
 v_b(x,y,z)=(-\sin y,\ 0,\ \sin x+\cos x\sin y).
$$

For cutoff $N=8$, project $v_b$ with the Fourier Leray projector and rescale the projected coefficients to

$$
\|u_{0,N}\|_{H^3}=R=32.
$$

The observable is

$$
I_N(T)=\int_0^T\left(P_N^{\mathrm{str}}(t)-\frac{ν}{2}D_N(t)\right)_+dt,
$$

with the same-state spectral production, direct physical-space strain check, and composite trapezoidal integration used by the fixed-H³ ROCm probe.

The radius $R=32$ is fixed before execution. It is a branch-sensitivity control, not the $R=1$ family used by the exploratory cutoff sequence.

## 2. Run matrix

Execute the following three rows with the ROCm float64 Torch implementation:

1. primary: $N=8$, $M=33$, 1024 RK4 steps;
2. timestep refinement: $N=8$, $M=33$, 2048 RK4 steps;
3. product-grid refinement: $N=8$, $M=49$, 1024 RK4 steps.

At every RK4 state, evaluate the positive-part precondition. The receipt records

$$
N_{\mathrm{attempt}}=\text{steps}+1,
$$

including the initial state.

## 3. Firing and integrity criteria

The audit passes only when all of the following hold:

- every scalar is finite;
- the projected $H^3$ normalization error is at most $10^{-10}$;
- the initial positive remainder satisfies
  $$
  P_N^{\mathrm{str}}(0)-\frac{ν}{2}D_N(0)>0;
  $$
- the primary $I_N(T)$ is strictly positive;
- the positive-part attempt count equals 1025 for the primary row and 2049 for the timestep-refined row;
- the maximum Fourier divergence residual is at most $10^{-10}$;
- direct-versus-spectral production relative error is at most $10^{-9}$ using denominator $\max(1,D_N)$;
- the maximum positive kinetic-energy increment is at most $10^{-9}\max(1,E_N(0))$;
- timestep and product-grid relative changes in $I_N(T)$ are at most $10^{-6}$ using denominator $\max(1,|I_N(T)|)$.

A passing receipt receives the classification `PASS—positive-part firing control only`. Any integrity failure receives `FAIL`. The schedule makes no claim about the $R=1$ cutoff sequence or about arbitrary initial data.

## 4. Interpretation and stopping rule

The schedule stops after the three declared executions. A positive primary integral demonstrates that the observable can fire on a real trajectory and that a zero integral in another arm is a measured non-firing branch rather than an unexecuted conditional. It does not establish a lower bound uniform in the cutoff or initial data.

The fixed-H³ ROCm sequence, its source-bound receipt, and this firing audit remain separate artifacts. The cutoff-uniform Galerkin target, production-relative compensation, active-dose bound, and arbitrary-data global regularity remain unresolved.

## References

- `computations/navier-stokes-galerkin-fixed-h3-rocm-prereg.md`—fixed-radius N-dependent family
- `computations/verify_navier_stokes_galerkin_fixed_h3_rocm.py`—ROCm float64 Galerkin implementation
- `turbulence/navier-stokes-replica-coherence.md` §7.1—conditional Galerkin continuation target
