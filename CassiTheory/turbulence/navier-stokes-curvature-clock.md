# The Curvature Clock of the Vorticity-Direction Coherence Margin

## Status: Derived exact kinematic identity / Tested on three closed-form controls / Measured on the retained helical tube families to $t=2$—September 2026

## Abstract

The coherence modulus of a tube-like high-vorticity region is its bending radius, with a
pole when the cross-section reaches the axis of curvature
(`turbulence/navier-stokes-tube-curvature-coherence.md`). This document supplies the time
evolution of that modulus. An exact identity for the material derivative of the margin
$\kappa a_n$ splits its rate into a bending-gradient term, a transverse-strain term and an
axial-stretching term, and it closes to round-off on three closed-form incompressible
deformations that realize the three available behaviours: a finite-time pole, exponential
growth, and exact conservation. The same margin is then measured at the vorticity core of
the retained helical tube families over $t\in[0,2]$. The growth is carried by the
transverse-strain term, the margin rises monotonically in all three families, and the
family with the largest margin arrests and reverses below the pole once the retained
resolution becomes marginal. The direction-coherence criterion is conditional and the
measured families do not enforce its hypothesis; arbitrary-data regularity is untouched.

## 1. The kinematic identity

Let $u$ be smooth and divergence-free, $\omega=\nabla\times u$, $\xi=\omega/|\omega|$ on a
tube-like region, $t$ the vorticity direction, and $\kappa=|(\xi\cdot\nabla)\xi|$ the
curvature of the vorticity line through a material point $x(\tau)$. Let $n$ be the
geometric normal of that line, $\ell=t\cdot(\nabla u)t$ the axial stretching, $S$ the
strain tensor and
$a_n=|\omega|^{1/2}\big/(n\cdot\nabla^2|\omega|\,n)^{1/2}$ the transverse width measured
along $n$ from the magnitude Hessian. Then, at the material point,

$$\frac{D}{D\tau}\log(\kappa a_n)\;=\;\underbrace{\frac{n\cdot(\partial_s\nabla u)\,t}{\kappa}}_{\text{bending gradient}}\;+\;\underbrace{2\,n\!\cdot\!Sn}_{\text{transverse strain}}\;-\;\underbrace{2\ell}_{\text{axial stretching}}\tag{KC1}$$

The identity follows from the commuting relation $[D_\tau,\partial_s]=-\ell\,\partial_s$,
the material transport of the tangent $D_\tau t=(\nabla u)t-\ell t$, and
$n\cdot(\text{antisymmetric})n=0$, applied to the pair $(\kappa,a_n)$ carried by the same
geometric normal. It is an identity of the velocity field: it constrains the *rate of the
margin*, and inherits no dynamical content beyond incompressibility.

Equation (KC1) has the structure of a budget. Pure axial stretching with an axisymmetric
core gives $2n\!\cdot\!Sn=2\ell$, so the margin is exactly conserved however strong the
stretching; the margin moves only through strain anisotropy and through the
bending-gradient term, and the finite-time pole is available through that second channel
alone.

## 2. Closed-form controls

Three incompressible deformations of a material curve with a known curvature and a known
normal-direction width test (KC1) in all three regimes
(`computations/navier_stokes_curvature_clock.py`, `--quick` block K).

| Control | Velocity | $\kappa(\tau)$ | $a_n(\tau)$ | margin | rate | measured increment residual |
|---|---|---|---|---|---|---|
| Parabolic bend | $(0,\beta x^2,0)$, $\beta=0.35$ | $2\beta\tau$ | constant $0.25$ | $\to1$ at $\tau_*=1/(2\beta a_n)$ | $1/\tau$ | $5.3\times10^{-16}$ |
| Ring tip, planar strain | $(\alpha x,-\alpha y,0)$, $\alpha=0.3$ | $\propto e^{3\alpha\tau}$ | $\propto e^{\alpha\tau}$ | $\propto e^{4\alpha\tau}$ | $4\alpha=1.2$ | $4.7\times10^{-11}$ |
| Ring, axisymmetric strain | $(\alpha x,-\alpha y,2\alpha z)$, $\alpha=0.3$ | to $0.96$ | to $0.26$ | exactly conserved $0.25$ | $0$ | $3.5\times10^{-11}$ |

Three readings matter. The parabolic bend is a smooth incompressible flow whose margin
reaches exactly one in finite time—measured $1.000000000000$ at the predicted
$\tau_*=5.714286$—so the pole is a property of the kinematic budget, not a formal
boundary. The ring tip realizes the exponential regime with the exact coefficient $4\alpha$,
the transverse-strain term supplying $+0.3$ and the stretching term $+0.3$ against a
vanishing bending gradient. The axisymmetric ring is the exact neutral case: the measured
rate is $3.5\times10^{-11}$ while $\kappa$ and $a_n$ individually move by $4\%$, so the
budget's cancellation is genuine rather than a case of both factors standing still. All
three margins reproduce their closed forms to $3.7\times10^{-16}$, and the stored rates
reproduce the assembled right-hand side of (KC1) to $3.3\times10^{-16}$.

## 3. The retained tube families over $t\in[0,\tfrac12]$

The margin is measured at the vorticity core of the three retained helical tube families of
`turbulence/navier-stokes-helical-dynamic-depletion.md`—$N=16$, grid $6N+1$, cutoff $16$,
$\nu=1/10$, the retained Fourier–Galerkin integrator—over the clock horizon.

| Family | seeded helix curvature | measured $\kappa(0)$ | margin $0\to\tfrac12$ | near-field coherence coefficient |
|---|---|---|---|---|
| `helix_wide` | $0.48$ | $0.4855$ | $0.2394\to0.2858$ | $1.1182\ldots1.3120$ |
| `helix_narrow` | $0.48$ | $0.4811$ | $0.1203\to0.1938$ | $0.9597\ldots1.3371$ |
| `helix_tight_pitch` | $1.20$ | $1.2377$ | $0.3160\to0.5306$ | $0.5886\ldots0.8524$ |

The measured core curvature anchors to the seeded helix within $3\%$ in all three families,
so the tube geometry the families were built to carry is the geometry measured. The margin
rises in every family, and the near-field coherence coefficient—the ratio of the measured
direction variation across one grid step to the local rotation $\kappa\,\Delta s$—sits
between $0.59$ and $1.34$ across the three families, the tight-pitch tube carrying the
lowest value. That is the value the tube carries by construction:
for a vortex tube $\xi=t$, so $\Gamma=\kappa$ and $\rho=1/\kappa$, and the near-field
product $\Gamma\rho$ equals one exactly, which is the critical coefficient of
`turbulence/navier-stokes-stress-geometry.md`.

## 4. The saturation window $t\in[0,2]$

`computations/navier_stokes_curvature_clock_saturation.py` integrates the same three
families over four times the clock horizon at an identical step and records the same raw
local tensors at nine checkpoints.

| Family | margin $0\to2$ | peak | last rate | decay classification | projected limit | tail above $\lvert k\rvert=8$ |
|---|---|---|---|---|---|---|
| `helix_wide` | $0.2394\to0.3836$ | $0.3836$ | $+0.061$ | non-monotone | $\infty$ | $3.5\times10^{-5}$ |
| `helix_narrow` | $0.1203\to0.3221$ | $0.3221$ | $+0.075$ | non-monotone | $1.17$ | $4.2\times10^{-2}$ |
| `helix_tight_pitch` | $0.3160\to0.6928$ | $0.6935$ at $t=1.75$ | $-0.003$ | turnover | $0.693$ | $3.7\times10^{-1}$ |

The rate series of the tight-pitch family reads
$0.467,\ 0.391,\ 0.328,\ 0.180,\ 0.053,\ 0.080,\ 0.010,\ -0.003$: monotone deceleration
followed by an arrest and a reversal below the pole. The projected limits are geometric tail
sums of the last rate, not bounds; the wide family's last three rates are not monotone, so
its projection is not finite, and the narrow family's projection exceeds one.

The term decomposition names the mechanism. At the checkpoints where the margin moves, the
bending-gradient term of (KC1) is negative in all three families
($-0.003$ to $-0.029$), the axial-stretching term is negative
($-0.001$ to $-0.007$), and the transverse-strain term is positive and dominant
($+0.002$ to $+0.062$). The margin's growth is driven by the transverse width $a_n$, which
grows by a factor $1.6$ in the wide family and $2.4$ in the tight-pitch family, while the
core curvature stays within $3\%$ of its seeded value in the two wide families and falls
by $10\%$ in the tight-pitch family. All three terms decay together as the core widens, so
the rate approaches zero from above. The route to the pole that the parabolic control
realizes—curvature growing at fixed width—is not the route these solutions take.

The tight-pitch family carries more than a third of its enstrophy above $\lvert k\rvert=8$
at late times, against the declared reporting threshold of $5\times10^{-2}$, so its
turnover is quoted with that qualification; the wide and narrow families stay resolved
($3.5\times10^{-5}$ and $4.2\times10^{-2}$) and are still climbing at $t=2$ at rates
$0.061$ and $0.075$, one order of magnitude below their initial rates.

## 5. What the clock settles

The identity (KC1) is exact and is verified at round-off on three closed-form controls that
exercise all three of its available behaviours, including a smooth incompressible flow whose
margin reaches the pole in finite time. The pole is therefore a real dynamical hazard of the
kinematic budget and not a formality of the geometric inequality.

On the retained tube families, the measured margin grows monotonically, is carried by
transverse strain rather than by bending, and saturates through the widening of the vorticity
core rather than through the growth of its curvature. The hypothesis of the
direction-coherence criterion is thus not enforced by these families' own dynamics: the
criterion remains conditional, and a global argument has to supply the cap on
$\kappa a_n$ that the flow does not supply for itself. What this program now measures is the
size of that uncapped growth—rates and term balances with explicit coefficients—rather than
a bound on it. The unresolved obligations are unchanged: arbitrary-data regularity, and a
bound on the coherence modulus (Equation (9) of
`turbulence/navier-stokes-tube-curvature-coherence.md`) for finite time from general smooth
data.

## 6. Evidence

| Check | Result |
|---|---|
| (KC1) increments against the analytic integrals, three controls | $5.3\times10^{-16}$, $4.7\times10^{-11}$, $3.5\times10^{-11}$ |
| Margin against the closed forms, three controls | $3.3\times10^{-16}$, $3.4\times10^{-11}$, $3.7\times10^{-11}$ |
| Stored increments against an independent quadrature | worst $2.5\times10^{-13}$ |
| Pole reached in finite time by the parabolic bend | margin $1.000000000000$ at $t=5.714286$ |
| Window margin below the pole, all families | largest $0.693468$ over nine checkpoints |
| Independent verifier, clock receipt | $125$ checks, $0$ failures; mutation control fires |
| Independent verifier, saturation receipt | $34$ checks, $0$ failures; mutation control fires |

The receipts are `runs/20260921_curvature_clock/curvature_clock_receipt.json` and
`runs/20260921_curvature_clock_saturation/curvature_clock_saturation_receipt.json`.
`computations/verify_navier_stokes_curvature_clock.py` rebuilds every derived number from
the stored raw tensors with its own algebra and checks the controls against closed forms
re-derived inside the verifier;
`computations/verify_navier_stokes_curvature_clock_saturation.py` rebuilds the rate series,
the decay classification and the projection from the stored margins and anchors the
window's initial checkpoint against the clock receipt.

## References

- P. Constantin and C. Fefferman, “Direction of vorticity and the problem of global regularity for the Navier–Stokes equations,” *Indiana University Mathematics Journal* **42** (1993), 775–789, DOI `10.1512/iumj.1993.42.42034`—conditional direction-coherence continuation criterion
- `turbulence/navier-stokes-tube-curvature-coherence.md`—the coherence modulus of a tube-like region, its identification with the bending radius, and the pole at $\kappa a_{\rm out}\to1$
- `turbulence/navier-stokes-stress-geometry.md`—filtered stress geometry and the critical coherence coefficient
- `turbulence/navier-stokes-helical-dynamic-depletion.md`—the retained coherent helical tube families and their measured positive production
- `computations/navier-stokes-curvature-clock-prereg.md`, `computations/navier_stokes_curvature_clock.py`, `computations/verify_navier_stokes_curvature_clock.py`—the clock protocol, its producer and its independent verifier
- `computations/navier-stokes-curvature-clock-saturation-prereg.md`, `computations/navier_stokes_curvature_clock_saturation.py`, `computations/verify_navier_stokes_curvature_clock_saturation.py`—the saturation window, its producer and its independent verifier
