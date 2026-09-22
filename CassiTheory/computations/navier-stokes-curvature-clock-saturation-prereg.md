# Saturation Window of the Vorticity-Direction Coherence Margin

**Status:** frozen pre-registration, 2026-09-21.

Companion to `computations/navier-stokes-curvature-clock-prereg.md`. The clock
protocol measured the margin $\kappa a_n$ of the vorticity-direction coherence
tube over $t\in[0,\tfrac12]$: it grows monotonically in all three declared tube
families while its rate decelerates. The clock protocol's stopping rule forbids
extending that horizon, so the saturation question is declared here as a
separate, self-contained protocol.

## 1. Question

Does the coherence margin of the retained helical tube families saturate below
the pole $\kappa a_n=1$, and at what level? The clock run leaves two open
readings: the margin may keep climbing to the pole, or the deceleration may be
the approach to a finite limit. This protocol decides between them over a horizon
four times longer.

## 2. Frozen protocol

- The same three declared families (`helix_wide`, `helix_narrow`,
  `helix_tight_pitch`), the same initial states, the same box (`N = 16`,
  grid $6N+1$, cutoff $16$), the same viscosity $\nu=1/10$ and the same step
  $\Delta t = 1/2/1024$.
- Horizon $T = 2$, i.e. $4096$ RK4 steps on the same $97^3$ grid. This is four
  times the clock horizon at an identical step.
- Checkpoints at $t = 0,\;1/8,\;1/4,\;3/8,\;1/2,\;5/8,\;3/4,\;7/8,\;1$ (scaled by
  $T$): nine samples.
- At every checkpoint the same raw local tensors are stored at the vorticity
  core ($\omega$, $\nabla u$, $\nabla\omega$, $\nabla|\omega|$,
  $\nabla^2|\omega|$, $\nabla^2u$) so the independent verifier rebuilds
  $\kappa$, $a_n$, the identity terms and the neighbour coherence coefficients
  with its own algebra.
- New measured series: the margin rate
  $r_i=(m_{i+1}-m_i)/\Delta t$ between consecutive checkpoints, and the
  geometric decay factor $\rho=(r_{\text{last}}/r_{n-3})^{1/3}$ over the last
  three intervals.
- New projection: $m_\infty = m_{\text{last}} + r_{\text{last}}\,\Delta t\,
  \rho/(1-\rho)$ for $\rho<1$. This is a *projection* of a geometric tail, not a
  bound, and is labelled as such wherever it is quoted.
- New resolution diagnostic: the fraction of enstrophy carried by modes with
  $|k| > 8$ (half the cutoff) at every checkpoint.

## 3. Decision rules

1. **E1 integrity.** Divergence residual, kinetic-energy increment and state
   normalization error stay at their clock-run levels for every checkpoint of
   every family; otherwise the trajectory is reported as not integrated.
2. **E2 pole.** The margin is reported at every checkpoint. If it stays below 1
   for all nine checkpoints, the coherence support of these families does not
   close over $t\in[0,2]$. If any checkpoint reaches or exceeds 1, the pole is
   reached and that outcome is reported as such.
3. **E3 deceleration.** The rate series is reported in full. Deceleration is
   established only if the last three rates are non-increasing; the factor
   $\rho$ is reported in either case.
4. **E4 projected limit.** The projection $m_\infty$ is reported for each
   family. The projection is declared consistent with saturation below the pole
   only when $\rho<1$ and $m_\infty<1$; every other outcome, including a
   projection that exceeds 1, is reported as measured.
5. **Resolution.** A family whose enstrophy tail exceeds $5\times10^{-2}$ at any
   checkpoint is reported as under-resolved at that checkpoint, and its
   late-time numbers are quoted with that qualification.

## 4. Stopping rule

All three families are integrated once at the declared parameters. No rerun with
adjusted parameters, no further extension of the horizon, and no additional
family are admitted after the run. Negative, inconclusive and failed outcomes
are retained and reported. The verifier recomputes every number from the stored
raw tensors, reproduces the content digest, and includes a mutation control that
perturbs one stored tensor component and requires at least one check to fail.
