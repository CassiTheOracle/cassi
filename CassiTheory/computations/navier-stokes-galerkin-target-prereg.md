# Galerkin Endpoint Target: Frozen Control Verification

## Status: Pre-registered—September 2026

## Abstract

This schedule checks the finite-mode controls surrounding the cutoff-uniform
Galerkin endpoint target in `turbulence/navier-stokes-replica-coherence.md`
§7.1. The target quantity is the positive critical remainder
$\left(P_N^{\mathrm{str}}-\nu D_N/2\right)_+$ whose time integral would give a
cutoff-independent enstrophy bound and the Prodi–Serrin restart passage. The
schedule freezes the normalization, the spectral data, the viscosity, the
near-rank family, and the Euclidean scaling test before execution.

The controls include a rank-deficient heat flow, the periodic ABC Beltrami heat
flow, a rank-two positive-production datum, and its full-dimensional
near-rank perturbations. They establish the signs, source ranks, finite-mode
admissibility, Sobolev-family bound, and critical scaling of the endpoint
integrand at the initial time. They supply finite-dimensional control evidence;
the time-integrated cutoff-uniform estimate and arbitrary-data regularity stay
unresolved.

## 1. Frozen target and normalization

Work on the $L$-periodic torus with $L=2\pi$. For a divergence-free Fourier
Galerkin solution $u_N$, write

$$
W_N(t)=\|\omega_N(t)\|_2^2,
\qquad
D_N(t)=\|\nabla\omega_N(t)\|_2^2,
\qquad
P_N^{\mathrm{str}}(t)=\int_{\mathbb T^3}
\omega_N\cdot S_N\omega_N\,dx.
$$

The frozen endpoint integrand is

$$
\mathfrak m_N(t)=P_N^{\mathrm{str}}(t)-\frac{\nu}{2}D_N(t),
\qquad
\nu=\frac1{10}.
\tag{GTC1}
$$

The Galerkin theorem target is

$$
\boxed{
\sup_{N\ge1}\sup_{\|u_{0,N}\|_{H^3}\le R_0}
\int_0^T\bigl(\mathfrak m_N(t)\bigr)_+\,dt<\infty.}
\tag{GTC2}
$$

The schedule evaluates $\mathfrak m_N(0)$ for finite trigonometric data. The
midpoint grid has $N_g=64$ points in each coordinate. The unitary FFT uses
physical wave numbers $k=2\pi\,\mathrm{fftfreq}(N_g, d/L_g)$ on a domain of
side length $L_g$; the Leray projector retains $0<|k|\le N$.

For a finite-mode field, the recorded grid Sobolev quantity is

$$
\|u\|_{H^3,N_g}^2
:=\int_{\mathbb T^3}\sum_{i=1}^3
(1+|k|^2)^3|\widehat u_i(k)|^2\,dx.
\tag{GTC3}
$$

All integrals use the midpoint cell volume. The acceptance tolerance for
normalized reconstruction, divergence, and production identities is
$10^{-10}$. Scaling ratios use relative tolerance $2\times10^{-10}$.

## 2. Frozen control data

The rank-deficient heat control is

$$
 u^{\mathrm{sh}}(x,y,z,t)=e^{-4\nu t}\sin(2y)e_1.
\tag{GTC4}
$$

The periodic ABC control is

$$
 u^{\mathrm{ABC}}(x,y,z,t)=e^{-\nu t}
(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x).
\tag{GTC5}
$$

For the positive-production and near-rank controls, set

$$
 u_b=(-\sin y,\ 0,\ \sin x+\cos x\sin y),
\tag{GTC6}
$$

$$
 w=(\sin z+\cos y,\ \sin x+\cos z,\ \sin y+\cos x),
\qquad
 u_\varepsilon=u_b+\varepsilon w,
\tag{GTC7}
$$

with

$$
\varepsilon\in
\left\{10^{-1},10^{-2},10^{-3},10^{-4}\right\}.
\tag{GTC8}
$$

The base and near-rank fields are evaluated at $t=0$ with Fourier cutoff
$N=2$. The shear uses cutoff $N=2$, and the ABC field uses cutoff $N=1$.
The scaling control uses $\lambda=3$, the domain $L/\lambda$, amplitude
$\lambda$, and cutoff $2\lambda$.

The exact base production identity is

$$
\left\langle\omega_b\cdot S_b\omega_b\right\rangle=\frac14,
\qquad
\left\langle\cdot\right\rangle=(2\pi)^{-3}\int_{\mathbb T^3}\cdot\,dx.
\tag{GTC9}
$$

The perturbation has $\nabla\times w=w$. The near-rank production remains

$$
\left\langle\omega_\varepsilon\cdot S_\varepsilon\omega_\varepsilon\right\rangle
=\frac14
\tag{GTC10}
$$

for every declared $\varepsilon$. The Sobolev family is bounded by

$$
\|u_\varepsilon\|_{H^3}
\le \|u_b\|_{H^3}+10^{-1}\|w\|_{H^3}=:R_*.
\tag{GTC11}
$$

## 3. Fixed check inventory

The verifier executes exactly these eight checks in order:

1. `G1 finite-mode controls survive Leray projection`
2. `G2 rank-deficient heat target vanishes`
3. `G3 ABC Beltrami target vanishes`
4. `G4 rank-two datum has positive endpoint remainder`
5. `G5 near-rank production remains fixed and positive`
6. `G6 near-rank source is sampled full rank with uniform H3 bound`
7. `G7 Euclidean endpoint scaling has critical exponent`
8. `G8 Galerkin enstrophy absorption identity`

`G1` requires every frozen field to have normalized projection and divergence
residual below $10^{-10}$. `G2` requires the exact symbolic shear heat identity,
rank-one source, $P=0$, $D>0$, and $(\mathfrak m)_+=0$. `G3` requires the exact
ABC divergence, curl, heat, and Bernoulli identities, $P=0$, $D=W$, and a
vanishing positive remainder at $\nu=1/10$.

`G4` requires the rank-two source determinant to vanish, normalized production
to equal $1/4$, and $\mathfrak m_b(0)>0$. `G5` requires all four near-rank
production averages to equal $1/4$ within the frozen tolerance and all four
endpoint remainders to remain positive. `G6` requires every positive perturbation
to have a nonzero sampled source determinant on more than half of the midpoint
grid and requires the computed $H^3$ norm to obey (GTC11) within numerical
roundoff. The sampled full-rank statement is a control on the frozen grid; the
analytic almost-everywhere statement is supplied by the near-rank derivation.

`G7` requires the initial $P$, $D$, and $\mathfrak m$ ratios under the declared
Euclidean dilation to equal $\lambda^3$ within relative tolerance. The time
interval transforms as $T\mapsto T/\lambda^2$, so the time-integrated target
has the critical scaling factor $\lambda$. `G8` checks the exact absorption
identity

$$
\left(2P_N^{\mathrm{str}}-2\nu D_N\right)+\nu D_N
=2\left(P_N^{\mathrm{str}}-\frac\nu2D_N\right),
\tag{GTC12}
$$

which is the algebraic step behind the enstrophy estimate from (GTC2).

## 4. Decision rule and evidence boundary

A failed exact identity, nonfinite value, reconstruction residual, sign, rank
fraction, family bound, scaling ratio, or absorption identity gives `FAIL`. Eight
passing checks classify the frozen finite-mode endpoint controls as `SUPPORTS` at
their stated scope.

The receipt keeps the cutoff-uniform time-integrated bound (GTC2), the
production-relative covariance estimate, the signed cross-scale estimate, and
arbitrary-data Navier–Stokes regularity as `UNRESOLVED`. No Galerkin trajectory,
time integral, generic singularity search, stochastic-flow simulation, or
continuum compactness passage is run by this schedule.

## 5. Execution and receipt

From the CassiTheory directory, run:

```text
python computations/verify_navier_stokes_galerkin_target.py
```

The selected source-bound receipt is

```text
runs/navier_stokes_galerkin_endpoint_controls_publication_20260913/verification.json
runs/navier_stokes_galerkin_endpoint_controls_publication_20260913/verification.inputs.json
runs/navier_stokes_galerkin_endpoint_controls_publication_20260913/verification.sources/
```

The receipt binds the paper, this protocol, the near-rank source note, and the
verifier by SHA-256. Generated evidence remains local and untracked.

## References

- `turbulence/navier-stokes-replica-coherence.md`—Galerkin endpoint target and restart passage
- `turbulence/navier-stokes-near-rank-recovery-obstruction.md`—near-rank family and analytic full-rank statement
- `turbulence/navier-stokes-rank-deficient-stretching.md`—rank-deficient periodic control
- J. Leray, *Sur le mouvement d'un liquide visqueux emplissant l'espace*—Galerkin approximation and weak-solution construction
- J. Serrin, [On the interior regularity of weak solutions of the Navier–Stokes equations](https://link.springer.com/article/10.1007/BF00253344)—velocity Prodi–Serrin continuation criterion
