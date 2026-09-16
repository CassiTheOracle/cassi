# Low-Band and High-Band Split of Vortex-Stretching Production

## Status: Pre-registered—September 2026

## Abstract

The helical stress test fixes which finite helical families develop positive
vortex-stretching production, and its scope statement leaves one analytic
obligation: any continuation route through the active-dose criterion needs an
initial-data-controlled bound on the accumulated strain norm, and any route
through the direction-coherence criterion needs a bound on the strain that
acts on a vortex core from a distance. This schedule measures the split of
the stretching production between two wavenumber bands of the strain: the low
band $|k|\le k_c$ and the high band $|k|>k_c$. The declared question is
whether positive production is carried by the low band across the stressed
helical families or whether the high band already produces it.

Fourier bands are not a Biot–Savart near-field/far-field decomposition. The
low band contains every large-scale strain component, including components
the dynamics generated, and the near/far reading is only a declared heuristic
label for the two bands. The schedule evolves the original unforced equation
in a Fourier–Galerkin truncation, records both bands at two declared cutoffs,
and freezes the classification rules before execution. A verdict of
`SUPPORTS` records a finite-family pattern of low-band dominance;
`CONTRADICTS` records that the high band alone carries the production.
Neither verdict supplies a cutoff-uniform estimate or a regularity theorem.

## 1. Equation, budget, and the band split

Work on the $2\pi$-periodic torus with unnormalized integrals, viscosity
$\nu=1/10$, and horizon $T=1/2$:

$$
\partial_tu+(u\cdot\nabla)u=-\nabla p+\nu\Delta u,
\qquad \nabla\cdot u=0,
$$

$$
\omega=\nabla\times u,\qquad
S=\tfrac12(\nabla u+\nabla u^{\mathsf T}),\qquad
P(t)=\int\omega\cdot S\omega\,dx.
$$

For a declared cutoff $k_c$, split the strain by wavenumber band,

$$
S_{\mathrm{low}}=\mathbb P_{\le k_c}S,\qquad
S_{\mathrm{high}}=\mathbb P_{>k_c}S,\qquad
P_{\mathrm{low}}(t)=\int\omega\cdot S_{\mathrm{low}}\omega\,dx,\qquad
P_{\mathrm{high}}(t)=\int\omega\cdot S_{\mathrm{high}}\omega\,dx,
$$

so that $P=P_{\mathrm{low}}+P_{\mathrm{high}}$ exactly at every state. The
projections act on each strain Fourier component by its wavenumber magnitude
$|k|$.

The heuristic reading of the two bands is that low-wavenumber strain acts on
a vortex core through the smooth far field of the Biot–Savart kernel, while
the high band contains near-field contributions at scales below the cutoff.
That reading is a declared label, not a decomposition of the kernel: the low
band also contains large-scale components that the trajectory itself
generated, and the record does not attribute any band to a spatial support.

Record the accumulated integrals

$$
I_{\mathrm{low},+}(T)=\int_0^T\max(P_{\mathrm{low}},0)\,dt,\qquad
I_{\mathrm{high},+}(T)=\int_0^T\max(P_{\mathrm{high}},0)\,dt,
$$

and the fractions
$r_{\mathrm{high}}=I_{\mathrm{high},+}(T)/\max(I_P(T),10^{-12})$ and
$r_{\mathrm{low}}=I_{\mathrm{low},+}(T)/\max(I_P(T),10^{-12})$, with
$I_P(T)=\int_0^TP_+dt$.

Two cutoffs are declared: $k_c=2$ and $k_c=4$. Both are evaluated from the
same trajectories. A classification is reported only when both cutoffs agree;
otherwise the schedule reports `INCONCLUSIVE` and records the disagreement.

## 2. Initial-data families

Every family is rescaled after Fourier projection to $K(0)=\tfrac12\|u\|_2^2=1$.
The families are the six declared below.

1. **Beltrami control.**
   $$
   u_B=(\sin z,\cos z,0),\qquad \omega_B=u_B.
   $$
   The field is a single curl eigenmode, so the nonlinear term is a pressure
   gradient, the trajectory is the exact heat flow, and $P(t)=0$
   analytically in every band.

2. **Wide helical tube.** Centerline radius $a_c=3/4$, winding $m=1$, tube
   radius $r=1/2$.

3. **Narrow helical tube.** Same centerline, $r=1/4$.

4. **Tight-pitch helical tube.** $a_c=3/4$, $r=1/4$, $m=4$, pitch $\pi/2$
   per turn.

5. **Two-scale tubes.** A wide $a_c=3/4$, $m=1$, $r=1/2$ tube and a
   separated narrow $a_c=3/8$, $m=4$, $r=1/4$ tube of common handedness.

6. **Opposite-handed tubes.** Two separated $r=1/4$ tubes with
   $a_c=3/4$, $|m|=3$, and centerline windings $m=+3$ and $m=-3$.

The family geometry is the retained construction of
`computations/verify_navier_stokes_helical_dynamic_depletion.py`; the new
verifier loads that construction so the initial fields are identical to the
retained helical matrix. The tube seed is proportional to a Gaussian
vorticity profile around the centerline times its tangent, and the Leray
projection supplies the exact divergence-free initial vorticity in the
retained Fourier space. Raw and projected divergence residuals,
normalization, helicity, and Fourier support are retained in the receipt.

## 3. Run matrix

For every case execute a primary run at each $N\in\{16,32\}$ with product
grid $M=6N+1$ and 1024 equal RK4 steps over $[0,T]$ in float64. For every
case at $N=32$ execute a timestep refinement with 2048 steps at the same
grid. The matrix contains 12 primary runs and 6 refined runs: 18 declared
executions. Checkpoints occur at $t/T\in\{0,1/4,1/2,3/4,1\}$; the band
diagnostics are evaluated at every accepted state.

The truncation retains $|k|\le N$ on the $M=6N+1$ product grid, so both
declared cutoffs lie strictly inside the retained band at every grid: the
$N=16$ run retains $|k|\le16$ on its $M=97$ grid, and the $N=32$ run retains
$|k|\le32$ on $M=193$.

## 4. Recorded observables

At every accepted state record

$$
P,\ \ P_{\mathrm{low}},\ \ P_{\mathrm{high}},\ \
E=\tfrac12\int|\omega|^2dx,\ \ G=\tfrac12\int|\nabla\omega|^2dx,\ \
K=\tfrac12\int|u|^2dx,\ \ \|\omega\|_{L^\infty},\ \ \|S\|_{L^\infty(\mathrm{op})},
$$

and at every checkpoint also the band alignments

$$
A_{\mathrm{low}}(t)=\frac{\int\omega\cdot S_{\mathrm{low}}\omega\,dx}
{\int|\omega|\,|S_{\mathrm{low}}\omega|\,dx},\qquad
A_{\mathrm{high}}(t)=\frac{\int\omega\cdot S_{\mathrm{high}}\omega\,dx}
{\int|\omega|\,|S_{\mathrm{high}}\omega|\,dx},
$$

with a declared zero-denominator marker. Record the accumulated strain dose

$$
\mathcal D_S(T)=\int_0^T\|S(t)\|_{L^\infty(\mathrm{op})}\,dt
$$

for the declared horizon, and the retained helicity fraction $H/C$ when
$C>0$.

## 5. Integrity and decision rules

The finite execution passes its numerical integrity checks only when:

- every recorded scalar is finite;
- projected kinetic normalization error is at most $10^{-10}$;
- Fourier divergence residual is at most $10^{-10}$;
- the band identity $P-P_{\mathrm{low}}-P_{\mathrm{high}}=0$ holds to
  relative error at most $10^{-10}$ at every accepted state using denominator
  $\max(1,|P|)$;
- for each band and cutoff, the physical-space band energy agrees with its
  spectral sum by Parseval to relative error at most $10^{-9}$, using
  denominator $\max(1,\sum_k w(k)|\widehat S(k)|_F^2)$ over the band;
- the maximum positive kinetic-energy increment is at most
  $10^{-9}\max(1,K(0))$;
- the kinetic-energy balance residual $|K'(t)+2\nu E(t)|$, with $K'$ formed
  as $\int u\cdot u_t\,dx$ at the accepted state, is at most
  $10^{-9}\max(1,|K'(0)|,2\nu E(0))$ at every accepted state;
- the timestep-refined $N=32$ accumulated integrals change by at most
  $10^{-4}$ using denominator $\max(1,|I|)$;
- the Beltrami control's band productions stay at most $10^{-10}$ in
  absolute value, which the exact heat-flow solution requires.

The declared hypothesis is:

> In the five helical-tube families, the positive vortex-stretching
> production is carried by the low wavenumber band at the declared cutoffs,
> and the high band does not by itself produce positive accumulated
> production.

The classification rules are frozen as follows, applied separately to each
tube family at each cutoff and then combined:

- `CONTRADICTS` if any tube family has $r_{\mathrm{high}}>0.5$ at both
  cutoffs;
- `SUPPORTS` if every tube family has $r_{\mathrm{high}}\le0.1$ and
  $r_{\mathrm{low}}\ge0.5$ at both cutoffs;
- `INCONCLUSIVE` otherwise, including any case where the two cutoffs give
  different classifications.

The classification is evaluated from the $N=32$ primary run of each family and
from no other run. The $N=16$ primary runs repeat the same observables at the
coarser truncation, and the timestep-refined $N=32$ runs supply the
integration integrity check.

The direction-coherence and alignment diagnostics are descriptive. A
cutoff-uniform estimate, a data-controlled bound on $\mathcal D_S(T)$, and
arbitrary-data regularity remain `UNRESOLVED` by this schedule.

## 6. Interpretation boundary

A split of the production into wavenumber bands measures where the
stretching work is done at the declared cutoffs. It does not prove that any
band is controlled by the initial data, and it does not separate the
Biot–Savart far field from large-scale strain components that the dynamics
generated. A `SUPPORTS` verdict records a finite-family pattern of low-band
dominance in the declared truncations at one viscosity and one horizon; it
supplies no conditional continuation statement. A `CONTRADICTS` verdict
records that the high band alone already produces positive stretching work in
the declared families, which removes low-band-only dominance as a
requirement of the positive production.

The schedule stops after the 18 declared executions. Its output supplies no
arbitrary-data continuation theorem, singularity construction, or
constitutive identification beyond the original Navier–Stokes equation.

## 7. Post-execution record

The schedule ran as written, unmodified, from the repository root:

```text
timeout 12000 python computations/verify_navier_stokes_strain_band_split.py
```

The invocation exited 0 after 10711.57 s, completing all 18 declared
executions and writing `runs/navier_stokes_strain_band_split/verification.json`
with `status=PASS` and all 10 integrity checks passed. An earlier invocation of
the same script under a 3300 s bound had reached five of the 18 declarations
and written no receipt; its combined output is retained at
`runs/navier_stokes_strain_band_split/probe.log`, and the completed
invocation's combined output at
`runs/navier_stokes_strain_band_split/probe_completed.log`. That bounded
attempt fixes a linear floor of 11880 s ($3300\times18/5$) for the full
schedule; the completed invocation ran under a 12000 s bound, 120 s above that
floor rather than the factor-of-two headroom the sizing called for, and
finished 1288 s inside the bound. The receipt binds the prereg by hash as it
stood at execution time, when §7 carried only the bounded-attempt record; the
frozen rules of §1–§6 are unchanged from commit `1ab33511`.

The receipt records a declared run count of 18, kinetic normalization
$3.33\times10^{-16}$, Fourier divergence $2.86\times10^{-17}$, band identity
$0$, band Parseval $2.08\times10^{-17}$, a maximum positive kinetic-energy
increment of $0$, an energy-balance ratio of $1.23\times10^{-15}$, a maximum
timestep-refinement change of $4.10\times10^{-7}$ against the frozen
$10^{-4}$ tolerance, and a Beltrami band control of $7.10\times10^{-34}$
against $10^{-10}$.

The classification reads the $N=32$ primary run of each helical-tube family
through the §5 decision rules, with $r_{\mathrm{high}}$ and
$r_{\mathrm{low}}$ as defined in §1:

| Tube family | $r_{\mathrm{high}}$, $k_c=2$ | $r_{\mathrm{low}}$, $k_c=2$ | $r_{\mathrm{high}}$, $k_c=4$ | $r_{\mathrm{low}}$, $k_c=4$ | Family verdict |
|---|---:|---:|---:|---:|---|
| Wide | 0.080289 | 0.919711 | 0.000000 | 1.102017 | SUPPORTS |
| Narrow | 0.493540 | 0.506460 | 0.049856 | 0.986010 | INCONCLUSIVE |
| Tight pitch | 0.874568 | 0.125432 | 0.403669 | 0.596331 | INCONCLUSIVE |
| Two scale | 0.093607 | 0.906393 | 0.000000 | 1.103970 | SUPPORTS |
| Opposite handed | 0.760908 | 0.239092 | 0.008912 | 1.491487 | INCONCLUSIVE |

No tube family meets the `CONTRADICTS` condition, which requires
$r_{\mathrm{high}}>0.5$ at both cutoffs: the tight-pitch family reads
$0.874568$ at $k_c=2$ but falls to $0.403669$ at $k_c=4$, and the
opposite-handed family falls from $0.760908$ to $0.008912$. The `SUPPORTS`
condition, which requires $r_{\mathrm{high}}\le0.1$ and
$r_{\mathrm{low}}\ge0.5$ at both cutoffs for every tube family, holds for the
wide and two-scale families and fails for the narrow, tight-pitch and
opposite-handed families. The overall classification is `INCONCLUSIVE`.

Low-band fractions above one follow from the §1 normalization, which divides
each band by the positive part of the total production; the two fractions are
not required to sum to one. The record establishes a finite-family pattern at
two cutoffs in one truncation pair, one viscosity and one horizon: two of the
five tube families carry low-band dominance at both cutoffs, two place most of
their positive production in the high band at $k_c=2$, and the aggregate rule
returns no classification. No cutoff-uniform estimate, no data-controlled
bound on $\mathcal D_S(T)$ and no continuation statement follows from this
execution.

## References

- `turbulence/navier-stokes-helical-dynamic-depletion.md`—measured signed production, direction variation, and the contradicted sign depletion in the same tube families
- `computations/navier-stokes-helical-dynamic-depletion-prereg.md`—frozen eight-family schedule and the retained trajectory matrix
- `turbulence/navier-stokes-coherence-dose-criterion.md`—active-dose continuation criterion and the operator-norm reduction to the strain-norm integral
- `turbulence/navier-stokes-stress-geometry.md`—Biot–Savart kernel split of the stretching work and the direction-coherence reformulation
- `computations/verify_navier_stokes_galerkin_long_trajectory.py`—Fourier–Galerkin rotational integrator and ROCm implementation
- P. Constantin and C. Fefferman, “Direction of vorticity and the problem of global regularity for the Navier–Stokes equations,” *Indiana University Mathematics Journal* **42** (1993), 775–789—conditional direction-coherence continuation criterion
- D. Buaria, A. Pumir, and E. Bodenschatz, “Self-attenuation of extreme events in Navier–Stokes turbulence,” *Nature Communications* **11** (2020), 5852—measured local strain self-attenuation and Beltramization at extreme vorticity
