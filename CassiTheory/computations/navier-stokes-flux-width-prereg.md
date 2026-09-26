# The Material Transport of the Flux-Based Tube Width

**Status:** frozen pre-registration, 2026-09-22.

Companion to `computations/navier-stokes-curvature-clock-prereg.md` and
`computations/navier-stokes-curvature-budget-prereg.md`. Both measured the margin
$\kappa a_n$ with a Hessian proxy $a_n$ for the tube width, and both recorded that
the proxy's own transport carries the normal curvature of $|\omega|$. The note
`turbulence/navier-stokes-tube-curvature-coherence.md` replaces the proxy with the
flux-based width, whose transport is closed. This protocol measures that closure on
the retained helical families, on one carried trajectory per family.

## 1. The identities under test

Let $\omega$ be the vorticity, $\xi=\omega/|\omega|$, $\ell=\xi\cdot(\nabla u)\xi$,
and let $P(\tau)$ be a material parallelogram spanned by two vectors obeying
$D_\tau v=(\nabla u)v$, centred on a Lagrangian tracer released at the field's
vorticity core. Write $\Gamma=\int_{P}\omega\cdot N\,dA$ for the vorticity flux
through $P$ and

$$a^2=\frac{\Gamma}{\pi\,|\omega|}, \qquad \kappa a \ \text{the margin} \tag{FW1}$$

with both $\Gamma$ and $|\omega|$ read at the carried tracer. The flux of a
divergence-free vorticity field through a material surface is conserved up to
viscosity, and the local enstrophy identity fixes the magnitude rate:

$$\frac{D_\tau\Gamma}{\Gamma}=\nu\frac{\int_P\Delta\omega\cdot N\,dA}{\Gamma},
\qquad D_\tau\log|\omega|=\ell+\nu\frac{\omega\cdot\Delta\omega}{|\omega|^2}
\tag{FW2}$$

Their combination is the width law, exact up to the profile spread $S$ of the patch
mean against the core reading:

$$D_\tau\log a=-\tfrac12\ell+S, \qquad
S=\tfrac12\nu\left(\frac{\int_P\Delta\omega\cdot N\,dA}{\Gamma}
-\frac{\omega\cdot\Delta\omega}{|\omega|^2}\right) \tag{FW3}$$

The curvature of the vortex line obeys, with
$V=\nu\,[\Delta\omega-\xi\,(\omega\cdot\Delta\omega)/|\omega|]/|\omega|$ and
$\kappa n=(\xi\cdot\nabla)\xi$,

$$D_\tau\log\kappa=\frac{n\cdot(\xi\cdot\nabla\nabla u)\xi}{\kappa}+n\!\cdot\!Sn
-2\ell+\frac{n\!\cdot\![(V\cdot\nabla)\xi+(\xi\cdot\nabla)V]}{\kappa} \tag{FW4}$$

so the margin's rate is the sum of (FW3) and (FW4), and with
$\|\nabla^2u\|$, $\|\nabla u\|$ the operator norms of the Hessian and the gradient,

$$\left|D_\tau(\kappa a)\right|\le a\|\nabla^2u\|
+\tfrac72\kappa a\|\nabla u\|+a\left|\text{viscous}\right| \tag{FW5}$$

Every quantity in (FW1)–(FW5) is a local quantity of the velocity field, read from
the raw tensors the retained clock already evaluates, plus the flux through the
carried patch.

## 2. The declared schedule

Cutoff $16$ on a $97^3$ lattice (the clock's retained shell), $\nu=0.1$, horizon
$0.5$, $1024$ steps, the three retained families `helix_wide`, `helix_narrow`,
`helix_tight_pitch` with the clock's initial states. The tracer is released at the
field's vorticity core at $\tau=0$ and carried by RK4 in the budget's stage
convention; the patch is released perpendicular to $\xi$ with side
$6\times$ the core's own Hessian width, so it spans the tube rather than sampling a
point inside it. The flux is a $3$-point Gauss quadrature per patch direction,
sampled every $4$ steps. One control repeats `helix_wide` at span $9$.

The patch side is a convention only if the patch spans the tube: below the core
width the flux is $|\omega|$ times the patch area and (FW1) reduces to
$\sqrt{A_\perp/\pi}$, independent of the field. The declared span avoids that
degenerate reading.

## 3. Decision tree

The instrument is checked first: **D0** the derivative blocks reproduce the
spectral grid derivatives, **D0b** the frame reader reproduces the retained
clock reader, **D1** the point evaluator reproduces the grid velocity, **D2** the
patch quadrature is converged at the declared order.

The measurement then tests the three integrated material statements, each
comparing the change of a carried quantity against the integral of its own
closed-form rate, and the margin bound sample by sample:

| rule | statement | tolerance |
|---|---|---|
| D3 | (FW4), curvature transport with the viscous bracket | $10^{-2}$ |
| D4 | (FW2) left, the flux lemma | $2\times10^{-2}$ |
| D5 | (FW2) right, the enstrophy identity | $2\times10^{-2}$ |
| D6 | (FW3) after removing the measured spread $S$ | $10^{-2}$ |
| D7 | (FW5), the weighted critical-norm bound | ratio $<1$ |
| D8 | (FW1) at span $9$ against span $6$ | $10^{-2}$ |
| D9 | D6's residual across sampling spacings $4,2,1$ | $10^{-2}$, spread $<10^{-6}$ |

The verdicts:

- **H1** every rule passes: the flux width's material transport is closed on the
  declared families, and the deviation from the ideal $-\ell/2$ law is the
  viscous profile spread, sized in the receipt.
- **H0** D3–D6 fail: the object or its measurement needs revision; the failing
  residuals are reported and no transport claim is made.
- **H2** D3–D6 pass but D7 or D8 fails: the closure holds and the margin bound or
  the span independence does not; both are reported as separate findings.

## 4. Stopping rule

One invocation of this schedule, one receipt, no re-runs. A design probe ran
before the freeze on the same families to validate the instrument and to size the
tolerances above from measured residuals: the derivative blocks to $2.6\times10^{-16}$,
the frame reader against the retained clock reader to $3.9\times10^{-15}$, the
quadrature to $3\times10^{-9}$, the curvature residual to $2.6\times10^{-3}$, the flux
residual to $6.6\times10^{-3}$, the enstrophy residual to $1.1\times10^{-3}$, the
spread-removed width residual to $2.7\times10^{-3}$, and the bound ratio to $0.245$.
The probe is disclosed here because it fixed the tolerances; its numbers are not
the measurement. The first invocation's receipt is frozen at
`runs/20260922_flux_width`, and the independent verifier
`computations/verify_navier_stokes_flux_width.py` re-derives every reading from the
stored values, reproduces the content digest, and includes a mutation control that
perturbs one stored value and requires at least one check to fail.

## 5. Scope

The measurement is of the declared families on the declared lattice and horizon.
It is a statement about the material transport of a flux-based width and its
viscous profile spread. It is not a statement about arbitrary data, and the
regularity of the three-dimensional Navier-Stokes equations remains unresolved.
