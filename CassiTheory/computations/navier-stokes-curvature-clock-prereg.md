# Curvature Clock of the Vorticity-Direction Coherence Margin

## Status: Frozen protocol—September 2026

## 1. Question

`turbulence/navier-stokes-tube-curvature-coherence.md` §6 leaves the time
integrability of the coherence modulus open: the modulus of a tube-like
high-vorticity region is its bending radius $\rho=1/\kappa$, and the failure of
the Constantin–Fefferman direction hypothesis is the pole $\kappa a_{\rm out}\to1$.
This protocol fixes the statistic, the controls and the decision rules for
measuring whether that margin moves in time, and for testing the exact
kinematic identity that governs it.

## 2. Frozen identity

For a smooth incompressible field $u$, a material curve with unit tangent $t$,
curvature $\kappa=|d_st|$, unit normal $n$, stretch rate $\ell=t\cdot(\nabla u)t$,
and $a_n$ the half-extent of the material cross-section along $n$,

$$
\frac{D_t\log(\kappa a_n)}{\text{rate}}
=\frac{n\cdot(\partial_s\nabla u)t}{\kappa}+2\,n\cdot Sn-2\ell .
\tag{KC1}
$$

The three terms are the strain-gradient (bending) channel, the transverse
strain on the normal, and the axial stretch. The protocol tests (KC1) on three
closed-form incompressible deformations whose curvature and width are known in
closed form:

| Control | Velocity | Initial curve | Closed form |
|---|---|---|---|
| KC-A parabolic bend | $(0,\beta x^2,0)$ | line along $x$ through the origin | $\kappa(t)=2\beta t$, $a_n$ constant, pole at $t_*=1/(2\beta a_n(0))$ |
| KC-B ellipse tip | $(\alpha x,-\alpha y,0)$ | circle of radius $R$ in the plane | $\kappa(t)=e^{3\alpha t}/R$, $a_n(t)=a_n(0)e^{\alpha t}$ |
| KC-C axisymmetric ring | $(\alpha x/2,\alpha y/2,-\alpha z)$ | circle of radius $R$ in the plane | $\kappa(t)=e^{-\alpha t/2}/R$, $a_n(t)=a_n(0)e^{\alpha t/2}$ |

KC-C is the classic ring-stretching configuration and carries the predicted
rate exactly zero. The statistic of each control is the logarithmic rate of the
margin $\kappa a_n$, measured by central differences in time, against the
right-hand side of (KC1) assembled from numerical derivatives of the analytic
velocity. The residual tolerance is $10^{-8}$ relative.

## 3. Frozen dynamical matrix

The margin is measured on the retained helical vorticity-tube families of
`computations/navier-stokes-helical-dynamic-depletion-prereg.md`, evolved by the
retained Fourier–Galerkin integrator with the same constants: $\nu=1/10$,
$T=1/2$, 1024 RK4 steps, cutoff $N=16$, grid $M=6N+1$, unit kinetic energy after
projection, checkpoints at $t/T\in\{0,1/4,1/2,3/4,1\}$. Three families:

| Case | tube radius | pitch turns | centerline radius | helix curvature |
|---|---|---|---|---|
| `helix_wide` | 0.5 | 1 | 0.75 | 0.48 |
| `helix_narrow` | 0.25 | 1 | 0.75 | 0.48 |
| `helix_tight_pitch` | 0.25 | 4 | 0.75 | 1.20 |

At each checkpoint the local data are taken at the vorticity core, the grid
point of maximum $|\omega|$:

- the vorticity-line curvature $\kappa=|(\xi\cdot\nabla)\xi|$ with $\xi=\omega/|\omega|$,
- the normal-direction width $a_n=\sqrt{|\omega|\,/\,|n\cdot\nabla^2|\omega|\,n|}$,
- the margin $m=\kappa a_n$,
- the three terms of (KC1) evaluated at the core,
- the finite-displacement coherence coefficient $|\xi(x+r)-\xi(x)|\,/\,(|r|\kappa^{-1})$
  for $r$ one grid cell and $r=a_n$ along $\xi$,
- the integrity observables: kinetic energy, divergence residual, energy-balance
  residual.

The receipt stores the raw local tensors ($\omega$, $\nabla u$, $\nabla\omega$,
$\nabla|\omega|$, $\nabla^2|\omega|$, $\nabla^2u$) at every checkpoint so that
the independent verifier can rebuild every derived number with its own algebra.

## 4. Decision rules

1. **D1 identity.** (KC1) is established only if the measured rate matches the
   assembled right-hand side within $10^{-8}$ relative in all three controls,
   and the KC-C rate is zero within the same tolerance. A failure is reported as
   a failure of the derivation, not absorbed into a tolerance.
2. **D2 margin.** For each tube family, the margin is reported at every
   checkpoint. If the margin stays below 1 at every checkpoint, the tube's
   coherence support does not close over this horizon. If it reaches or exceeds
   1, the pole is reached and the tube-like region has lost its coherence
   support; that outcome is reported as such.
3. **D3 decomposition.** The sign of the measured margin rate is compared with
   the sign of the assembled (KC1) right-hand side at the core. The comparison
   is a diagnostic, not a gate: the vorticity line is not a material curve, so
   the viscous and direction-gradient terms of the direction equation are
   expected to contribute. The measured mismatch is reported.
4. **D4 initial-curvature anchor.** The measured $\kappa$ at $t=0$ is reported
   against the analytic helix curvature of the table above. Agreement within a
   factor of two is required for the pipeline to be declared consistent with the
   seeded geometry; the ratio is reported in either case.

## 5. Stopping rule

All three controls and all three declared trajectories are executed once, at the
declared parameters. No rerun with adjusted parameters, no extension of the
horizon, and no additional family is admitted after the run. Negative,
inconclusive, and failed outcomes are retained and reported. The verifier
recomputes every number from the stored raw tensors and includes a mutation
control that perturbs one stored tensor component and requires at least one
check to fail.
