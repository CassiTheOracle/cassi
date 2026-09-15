# Fixed-H³ Adversarial Galerkin Remainder: Exploratory Probe

## Status: Pre-registered—September 2026

## Abstract

This schedule measures the positive Galerkin enstrophy remainder for an initial-data family whose high-frequency content changes with the Fourier cutoff while the projected initial $H^3$ norm is held fixed. The family contains two exact noncoplanar high-frequency triads and a fixed low-mode control. The statistic, normalization, cutoff sequence, numerical checks, and stopping rule are fixed before trajectory execution. The output is a finite-data falsification diagnostic for candidate cutoff-uniform bounds; it supplies no bound, singularity classification, or global-regularity result.

## 1. Objective and scope

For a fixed viscosity, horizon, and initial-data radius, test whether a cutoff-dependent family can produce growth in the integrated positive enstrophy remainder while remaining inside one projected $H^3$ ball. The primary observable is

$$
I_N(T)=
\int_0^T\left(P_N^{\mathrm{str}}(t)-\frac{ν}{2}D_N(t)\right)_+dt.
$$

The frozen parameter values are

$$
ν=\frac1{10},\qquad T=\frac12,
\qquad R=1,
\qquad N\in\{8,16,32\}.
$$

The target quantity is the unnormalized $I_N(T)$. For comparison at the same $T$ and $R$, also report

$$
\widehat I_N=\frac{I_N(T)}{TR^3}.
$$

The denominator is fixed independently of $N$ and is a display normalization only. It is not a proposed Navier–Stokes scaling law.

## 2. Galerkin equation and observable

Work on the $2π$-periodic torus with unnormalized integrals. Let

$$
Λ_N=\{k∈ℤ^3:0<|k|_2≤N\}.
$$

For real coefficients,

$$
\widehat u_N(-k)=\overline{\widehat u_N(k)},
$$

and the divergence-free Galerkin evolution is

$$
∂_t\widehat u_N(k)
=-ν|k|^2\widehat u_N(k)
-Π_k\widehat{(u_N·∇)u_N}(k),
$$

with

$$
Π_k=I-\frac{kk^{\mathsf T}}{|k|^2}.
$$

Use an odd primary product grid $M=4N+1$ and a refined product grid $M=6N+1$. The retained field has coordinate wave numbers bounded by $N$, so the quadratic product is alias-free on both grids.

With $V=(2π)^3$, define

$$
W_N=V\sum_k|\widehat ω_N(k)|^2,
\qquad
D_N=V\sum_k|k|^2|\widehat ω_N(k)|^2.
$$

The strain production is evaluated from the same-state Galerkin right-hand side:

$$
P_N^{\mathrm{str}}
=\frac12\frac{dW_N}{dt}+νD_N.
$$

At the five fixed fractions $t/T∈\{0,1/4,1/2,3/4,1\}$, independently reconstruct $u_N$, $ω_N$, and

$$
S_N=\frac12(∇u_N+∇u_N^{\mathsf T})
$$

on the product grid and compare

$$
\int_{\mathbb T^3}ω_N·S_Nω_N\,dx
$$

with the spectral production. Integrate $(P_N^{\mathrm{str}}-νD_N/2)_+$ by the composite trapezoidal rule on every primary RK4 step.

## 3. Fixed initial-data family

The low-mode field is

$$
 v_b(x,y,z)=(-\sin y,\ 0,\ \sin x+\cos x\sin y).
$$

For each even cutoff $N$, set $h=N/2$ and use the five wave vectors

$$
\begin{aligned}
 k_1&=(h,0,0),& k_2&=(0,h,0),& k_3&=(-h,-h,0),\\
 k_4&=(0,0,h),& k_5&=(0,-h,-h).
\end{aligned}
$$

They contain the exact zero-sum triads

$$
 k_1+k_2+k_3=0,
\qquad
 k_2+k_4+k_5=0,
$$

and their union has rank three. Every listed wave vector satisfies $|k_j|_2≤N$.

Let

$$
A_N(x)=\sum_{j=1}^5\frac1{|k_j|_2}
\left(a_j\cos(k_j·x)+b_j\sin(k_j·x)\right),
$$

with the fixed coefficient table

$$
\begin{array}{c|c|c}
 j&a_j&b_j\\ \hline
1&(0,1,1)&(0,1,-1)\\
2&(1,0,1)&(1,0,-1)\\
3&(1,-1,1)&(1,1,0)\\
4&(1,1,0)&(1,-1,0)\\
5&(1,0,1)&(1,0,-1)
\end{array}
$$

and define the high-frequency field

$$
 w_N=∇×A_N.
$$

The curl construction supplies the analytic divergence-free constraint. The implementation still applies the Fourier Leray projector and records the residual.

Use three fixed arms:

1. $v_b$ (base);
2. $w_N$ (high);
3. $v_b+w_N$ (combined).

For each arm, project its Fourier coefficients onto $Λ_N$, then normalize the projected field to the same radius:

$$
 u_{0,N}=R\frac{Π_Nv}{\|Π_Nv\|_{H^3}},
$$

where the projected Fourier norm is

$$
\|u\|_{H^3}^2
=V\sum_{0<|k|_2≤N}(1+|k|_2^2)^3|\widehat u(k)|^2.
$$

The post-projection norm is the contract quantity. Record the pre-projection norm, post-projection norm, $L^2$ norm, enstrophy, palinstrophy, support, and maximum modewise divergence residual for every arm and cutoff. No amplitude search, parameter fitting, or post hoc arm selection is permitted.

## 4. Run matrix

For each of the three arms and each $N∈\{8,16,32\}$, execute:

1. primary RK4 with 1024 equal steps over $[0,T]$ and $M=4N+1$;
2. timestep refinement with 2048 steps at the same cutoff and grid;
3. product-grid refinement with 1024 steps and $M=6N+1$.

The complete matrix contains $3×3×3=27$ executions. The high-frequency family and the fixed base arm share the same numerical schedule.

## 5. Recorded checks and stopping rule

Record for every execution:

1. $I_N(T)$, $\widehat I_N$, and the maximum positive remainder;
2. projected and unprojected $H^3$ norms and the normalization error;
3. initial and final energy, enstrophy, palinstrophy, and the maximum positive kinetic-energy increment;
4. maximum Fourier divergence residual;
5. support bounds and the modewise high-field transversality residual;
6. direct strain production at all five checkpoints;
7. direct-versus-spectral production discrepancy;
8. timestep and product-grid relative changes in $I_N(T)$;
9. the sequences $I_8(T),I_{16}(T),I_{32}(T)$ separately for each arm.

Integrity thresholds are fixed before execution:

- every recorded scalar is finite;
- post-projection $H^3$ normalization error is at most $10^{-10}$;
- divergence and modewise transversality residuals are at most $10^{-10}$;
- direct-versus-spectral production relative error is at most $10^{-9}$ using denominator $\max(1,D_N)$;
- the maximum positive kinetic-energy increment is at most $10^{-9}\max(1,E_N(0))$;
- timestep and product-grid relative changes use denominator $\max(1,|I_N(T)|)$ and are at most $10^{-6}$.

The schedule stops after the declared 27 executions and their refinements. A failed integrity check gives `FAIL` for the finite probe. Passing all checks gives the classification `INCONCLUSIVE—fixed-H³ exploratory sequence`; the observed cutoff sequence is retained as descriptive evidence. Growth across three doublings is a diagnostic and is not converted into a claim of divergence. Bounded values are not converted into a cutoff-uniform theorem.

## 6. Evidence boundary

The statistic tests a family of projected initial data in one fixed $H^3$ ball at one viscosity and one finite horizon. It supplies no estimate uniform over the full $H^3$ ball, no statement about $N→∞$, no singularity construction, and no continuation theorem. The local estimate

$$
I_N(τ)≤8C_4τR^3
$$

is used only on its local interval $τ≤(2C_4R)^{-1}$ and is not extrapolated through the prescribed horizon.

The cutoff-uniform Galerkin bound, active-dose bound, production-relative compensation, and arbitrary-data global regularity remain unresolved under every finite outcome of this schedule.

## References

- `computations/navier-stokes-galerkin-long-trajectory-prereg.md`—fixed-control Galerkin observable and grid conventions
- `turbulence/navier-stokes-replica-coherence.md` §7.1—Galerkin continuation target and local estimate
- `turbulence/navier-stokes-coherence-dose-criterion.md`—conditional active-dose continuation criterion
- `turbulence/navier-stokes-covariance-recovery-rate.md`—initial-layer boundary for determinant recovery
