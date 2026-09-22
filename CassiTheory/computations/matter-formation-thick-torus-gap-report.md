# Thick-torus charged wound carrier: exact-metric cross-section

## Status: measurement — 2026-09-22

The registered protocol `computations/matter-formation-thick-torus-gap-prereg.md` has not been
invoked. Its relaxation stage does not reach the registered stationarity gate, so the single
invocation is retained and no branch of §6 is issued. This report records the exact-metric
measurements that were taken, the mechanism they expose, the two pre-invocation protocol
corrections, and the concrete obstacle that remains.

## 1. What was asked

The wound-loop phase reduced the charged carrier loop to a one-dimensional cross-section on a
straight tube and found that its stationary radius lies inside the tube core
(`foundations/loop-to-bubble-projection-theorem.md` §9.45). The thick-torus phase asks the same
question with the cross-section relaxed in the exact toroidal metric: does the charged wound
carrier have an interior stationary radius with positive radius curvature, an admissible
cross-section, and a mass below the dilute charged threshold?

The exact toroidal cross-section energy is the registered functional of §2 of the protocol on a
disk of radius $a_{\max}=0.9R$ with metric factor $g(a,\varphi)=1+a\cos\varphi/R$ and measure
$d\mu=a\,g\,da\,d\varphi$. The total carrier norm is $N=2\pi R\,n$; the reported mass is
$M(R,n;Q)=2\pi R\,E_{\rm tor}(R,n)+Q^2/(8\pi a Rn)$.

## 2. The axisymmetric lift is not the minimum

The transported trial of §9.45 lifts the flat tube profile onto the torus axisymmetrically.
Evaluating the exact functional at that configuration and at the same profile translated to
polar position $(a_0,\varphi_0)$ of the disk, at $R=8$, $n=5$, on the $200\times32$ scan grid:

| $a_0$ | $\varphi_0=0$ | $\varphi_0=\pi/2$ | $\varphi_0=\pi$ |
|---|---|---|---|
| 0.0 | 22.2141 | 22.2141 | 22.2141 |
| 1.0 | 22.5257 | 22.2106 | 21.9447 |
| 2.0 | 22.8605 | 22.1972 | 21.7410 |
| 3.0 | 23.2179 | 22.1818 | **21.6532** |
| 4.0 | 23.7043 | 22.2569 | 21.8032 |
| 5.0 | 25.7392 | 23.6387 | 22.8155 |
| 6.0 | 43.7738 | 38.3527 | 30.2324 |

The axisymmetric configuration is therefore not the relaxed cross-section. The energy falls by
$0.56$ (2.5%) when the carrier moves off the axis toward $\varphi=\pi$, and it rises on the
$\varphi=0$ side at every displacement. The pre-run prediction of §4 of the protocol placed the
carrier on the wide side; the measurement places it on the narrow side.

The mechanism is a competition between two terms of the functional. The gradient energy carries
the metric factor $g$ and is cheapest where $g$ is smallest, which is the pinched inner side. The
quartic self-energy is cheapest where the local measure $a\,g$ is largest, which is the outer
equator. At $R=8$ the gradient term wins at moderate $a_0$, and the balance sits at
$a_0\approx3$ on the narrow side. At $R=5$ the pinching is stronger and the carrier sits further
out in $a$: the relaxed trial there reaches $E_{\rm tor}=9.468$ at $n=2$, against the registered
flat-tube value $E_\perp(2)=9.4893129939$ recomputed here at the registered resolution
(stationarity residual $2\times10^{-13}$), so the curvature geometry lowers that cross-section by
$0.2\%$. The mass and quartic terms do not carry the metric factor, which is why the $R=5$ gain is
small while the $R=8$ positional gain reaches $2.5\%$.

This is a value statement, not a stationarity statement: every entry above is an exact evaluation
of the registered functional at an admissible configuration, so each is an upper bound on the
constrained minimum. The bound $2\pi R\,E_{\rm tor}=1088.4$ at $R=8$, $n=5$ already lies
$2.5\%$ below the $Q=128$ dilute threshold $1115.878$.

## 3. The relaxation does not close

Constrained relaxation at fixed population was attempted with three independent globalization
strategies on the registered grids:

| strategy | merit | outcome at $(8,5)$ |
|---|---|---|
| Levenberg–Marquardt, Sherman–Morrison tangential step, anchored multiplier | energy | stalls near $10^{-1}$ |
| projected L-BFGS-B (population re-enforced every evaluation) | energy | reaches $10^{-3}$–$10^{-2}$ |
| damped bordered Newton with shift escalation | bordered residual | floor at $5\times10^{-3}$ |

The best states reached are $E_{\rm tor}=20.89$ at $(R,n)=(8,5)$ with residual $5.1\times10^{-3}$,
$a_{99}=6.25$, outer-decile fraction $3.9\times10^{-4}$, and $E_{\rm tor}=9.468$ at $(5,2)$ with
residual $1.6\times10^{-3}$, $a_{99}=4.04$ against the admissibility bound $0.85R=4.25$. The
registered gate is $10^{-9}$.

The primary program runs end to end. On a deliberately shrunken schedule ($R\in\{5,7,8\}$,
$n\in\{2,5\}$, one charge, $60\times16$ scan grid, 30 polish iterations) it executes every stage —
validation, scan, refinement, summaries, stored profiles, constrained spectrum, resolution
controls, mutation control, winding controls, classification — and returns 12 of its 16 checks,
with the four failures being exactly the solver-dependent ones (`solve_convergence`,
`grid_resolution`, `spectrum_resolution`, `validation_transported_feasibility`). Four
implementation defects were found and fixed by that run: the two-dimensional state carry between
radii resampled a one-dimensional profile, the sparse tangent basis mis-indexed its columns, the
stored-profile and spectrum stages read profiles that scan rows do not carry, and the mutation
control rebuilt the section without the stored radial extent.

The three methods stop in the same place, which locates the obstacle in the problem rather than in
one optimizer. The carrier position in the disk is a nearly flat direction of the energy: the
flat-tube functional is exactly translation invariant, and the toroidal metric breaks that
invariance only through the $\kappa a$ dependence of $g$, so the curvature along the position mode
is small compared with the stiff $O(10^2)$ curvature of the profile itself. A residual of
$10^{-9}$ along such a mode demands a position accurate to roughly $10^{-9}/\lambda$ in field
units, which is far below the resolution at which the discrete functional resolves the mode. The
registered residual gate is therefore not attainable by descent on this functional as discretized,
and the honest reading is that the gate as written is the wrong instrument for a functional with an
exact flat direction.

## 4. Pre-invocation corrections to the protocol

Both corrections were found while implementing the protocol and before any invocation; both are
recorded in the protocol as revision 2.

1. **Mass convention.** §2 wrote $M=E_{\rm tor}+Q^2/(8\pi aRn)$ while §2's transported reference
   $M^{\rm red}=2\pi R\,E_\perp(n)+\pi K_{Cx}w^2n\eta/R+Q^2/(8\pi aRn)$ is a total energy. The two
   differ by the loop length $2\pi R$, and the comparison against the dilute threshold
   $\Omega_\infty|Q|$ is only meaningful in the total convention. The registered mass is now
   $M=2\pi R\,E_{\rm tor}+Q^2/(8\pi aRn)$ with $E_{\rm tor}$ the cross-section energy per unit
   length, which is what the geometry module returns.
2. **Validation comparisons.** The flat validation compared a per-unit-length energy against
   $E_\perp$ after dividing by $2\pi R$, and the transported-feasibility check compared a
   per-unit-length energy against the total reference. Both now compare like with like.

The transported reference itself is unchanged and reproduces its frozen value
$2\pi\cdot8\cdot E_\perp(5)+\pi\cdot5\cdot\eta/8=1116.5976135848036$ with $E_\perp(5)=22.174477188390953$
and $\eta=1.0118788464248585$.

## 5. What is retained

The measurement of §2 stands on its own: in the exact toroidal metric the charged wound carrier's
cross-section does not sit on the tube axis, it migrates toward the pinched inner side, and the
direction is opposite to the pre-run prediction. The relaxed-trial mass at $R=8$, $n=5$ is already
below the $Q=128$ dilute threshold, so the binding question is whether a *stationary* state with a
comparable cross-section exists, which is exactly what the protocol's interior-radius and
curvature tests would decide.

The remaining obstacle is stationarity: the relaxer floors at $10^{-3}$ and does not reach the
registered gate (§5a). Two routes could close it: replace the bordered residual gate with a gate on
the energy along the constrained manifold plus a separately declared stationarity test on the
position mode, or quotient the position mode out of the variational problem by fixing the carrier's
first moment and relaxing only the shape. The second route keeps the registered functional and grid
untouched and makes the stationarity system non-degenerate if the position mode is the cause.

## 5a. Solver diagnosis

A diagnostic pass was run after this report was first written. It changes what is known about the
obstacle, and it retracts one claim that a defective check had supported.

*The geometry module is exact.* A central-difference audit of the module's own energy/gradient pair
agrees to $10^{-8}$ relative on the registered $200\times32$ section, including at warped states
with $c<0$ and $f>1$. The registered functional and its derivatives are what they claim to be, and
the energy contains no field-dependent kink (its only clamp, $\max(g,10^{-12})$, is on the metric,
which does not depend on the fields).

*A retracted finding.* An earlier check reported that the objective and the gradient handed to
L-BFGS-B disagreed by $1$--$25\%$ relative. That measurement was an artefact of dividing by a
directional derivative that is itself near zero: against the correct scale ($|\text{fd}-g\cdot d|$
divided by $|g|$, not by $|\text{fd}|$) every variant of the Stage A pair agrees to $10^{-3}$ or
better. The inconsistency claim is withdrawn; the pairing was never the cause of the stall.

*The pinning probe does not discriminate.* Penalising the carrier's first moments leaves the free
bordered residual large, but a pin holds the state away from the free minimum by construction, so
that residual measures the pin's own force. The position-mode hypothesis is neither confirmed nor
falsified by that run; discriminating it requires sweeping the pin *position* and asking whether the
free residual can be driven down at any of them.

*What is established.* Stage A floors at $3.5\times10^{-3}$--$1.8\times10^{-2}$ in every variant
tried — projected descent on the re-anchored bordered gradient, projected descent on the exact
derivative of $E(f,\gamma c)$ including the rescale's Jacobian, an augmented Lagrangian on $N-n$,
and a restart loop with a gradient-driven stopping rule — and every one terminates with a
line-search failure rather than a gradient criterion. The constraint itself is satisfied to machine
precision throughout, and the bordered Newton polish does not close the gap. The obstacle is a
property of the relaxation scheme, not of the functional, and the next diagnostic is a
finite-difference audit *at the stalled point* rather than at a random one.

The two routes named in §5 remain the way to close the stationarity requirement. The protocol was
not invoked, and no verdict is issued.

## 6. Boundaries

The result is a finite-grid evaluation and relaxation of one registered functional in the
conditional scalar sector. `yang_mills_identification`, `continuum_gauge_construction`, and
`charge_quantization` remain `UNRESOLVED`; `clay_verdict` is `null`. No branch of §6 of the
protocol is issued, because the protocol was not invoked. The independent verifier
(`computations/verify_matter_formation_thick_torus_gap.py`) is written, self-tested on eight
checks, and has not been run against a receipt, because no receipt exists.
