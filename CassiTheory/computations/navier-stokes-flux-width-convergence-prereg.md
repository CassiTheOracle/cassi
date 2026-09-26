# The Flux-Based Tube Width at a Converged Patch Quadrature

**Status:** frozen pre-registration, 2026-09-22.

Companion to `computations/navier-stokes-flux-width-prereg.md`, whose first
invocation at `runs/20260922_flux_width` measured the closure of the flux-based
width and returned no promoted claim: its instrument did not pass. The patch
quadrature at order $3$ is not converged on the live states, the frame reader's
residual of $6.9\times10^{-10}$ is round-off in a ratio that the declared tolerance
was tighter than, and a patch at span $9$ measures a different object from one at
span $6$. This is a fresh protocol for the same identities at a corrected
instrument, not an amendment: the earlier receipt stands as its own measurement.

## 1. The identities under test

Unchanged from `computations/navier-stokes-flux-width-prereg.md` §1. With
$\xi=\omega/|\omega|$, $\ell=\xi\cdot(\nabla u)\xi$, $\Gamma$ the vorticity flux
through a material parallelogram carried with the tracer, and
$a^2=\Gamma/(\pi|\omega|)$,

$$D_\tau\log a=-\tfrac12\ell+S,\qquad
S=\tfrac12\nu\left(\frac{\int_P\Delta\omega\cdot N\,dA}{\Gamma}
-\frac{\omega\cdot\Delta\omega}{|\omega|^2}\right) \tag{C1}$$

$$D_\tau\log\kappa=\frac{n\cdot(\xi\cdot\nabla\nabla u)\xi}{\kappa}+n\!\cdot\!Sn
-2\ell+\frac{n\!\cdot\![(V\cdot\nabla)\xi+(\xi\cdot\nabla)V]}{\kappa} \tag{C2}$$

$$\left|D_\tau(\kappa a)\right|\le a\|\nabla^2u\|+\tfrac72\kappa a\|\nabla u\|
+a\left|\text{viscous}\right| \tag{C3}$$

The flux lemma and the enstrophy identity are (FW2) of the earlier protocol.

## 2. The declared schedule

Cutoff $16$ on a $97^3$ lattice, $\nu=0.1$, horizon $0.5$, $1024$ steps, the three
retained families `helix_wide`, `helix_narrow`, `helix_tight_pitch`, the tracer
released at the vorticity core and carried by RK4 in the budget's stage
convention, the patch released perpendicular to $\xi$ with side $6\times$ the
core's own Hessian width, sampled every $4$ steps. Two changes from the earlier
protocol, both of the instrument:

- the patch flux is a **six**-point Gauss quadrature per patch direction, against
  order $3$ before, and the convergence check reads the declared order and the next
  against order $8$;
- the frame-reader tolerance is $10^{-8}$, sized for round-off in a ratio rather
  than for the derivative blocks' own round-off.

One control repeats `helix_wide` at span $4$, so that both the declared patch and
the control contain the tube: a patch below the tube's own width reads its area
rather than its flux, and a patch far above it reads the surroundings.

## 3. Decision tree

The instrument is checked first: **D0** the derivative blocks against the spectral
grid derivatives, **D0b** the frame reader against the retained clock reader,
**D1** the point evaluator against the grid velocity, **D2** the patch quadrature
converged at the declared order on the family's own release state.

| rule | statement | tolerance |
|---|---|---|
| D3 | (C2), curvature transport with the viscous bracket | $10^{-2}$ |
| D4 | the flux lemma | $2\times10^{-2}$ |
| D5 | the enstrophy identity | $2\times10^{-2}$ |
| D6 | (C1) after removing the measured spread $S$ | $10^{-2}$ |
| D7 | (C3), the weighted critical-norm bound | ratio $<1$ |
| D8 | (C1) at span $4$ against span $6$ | $10^{-2}$ |
| D9 | D6's residual across sampling spacings $4,2,1$ | $10^{-2}$, spread $<10^{-6}$ |

The verdicts:

- **H1** every rule passes: the flux width's material transport is closed on the
  declared families at a converged quadrature, and the deviation from the ideal
  $-\ell/2$ law is the viscous profile spread, sized in the receipt.
- **H2** the closure rules pass and a control rule does not: both are reported as
  separate findings.
- **H0** the closure rules fail: the object or its measurement needs revision.
- **No claim** if an instrument rule fails: the closure rules are reported as
  measured and not promoted.

## 4. Stopping rule

One invocation, one receipt, no re-runs. The tolerances are the earlier protocol's,
which the earlier invocation's residuals support: the curvature transport closes to
$2.6\times10^{-3}$, the flux lemma to $6.6\times10^{-3}$, the enstrophy identity to
$1.1\times10^{-3}$, the spread-removed width law to $2.7\times10^{-3}$, and the bound
ratio reaches $0.245$ there. The corrected instrument is expected to lower the
quadrature contribution rather than the identity residuals. The receipt is frozen at
`runs/20260922_flux_width_converged`; `computations/verify_navier_stokes_flux_width.py`
re-derives every reading from the stored values and reproduces the content digest
against the schema of this protocol.

## 5. Scope

The measurement is of the declared families on the declared lattice and horizon. It
is a statement about the material transport of a flux-based width and its viscous
profile spread. It is not a statement about arbitrary data, and the regularity of
the three-dimensional Navier-Stokes equations remains unresolved.
