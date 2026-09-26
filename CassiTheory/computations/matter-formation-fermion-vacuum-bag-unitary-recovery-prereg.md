# Unitary Midpoint Recovery: Regulated Spatial Vacuum-to-Bag Formation

## Status: Recovery protocol—September 2026

## Purpose and failure being repaired

The finite-step RK4 update for the occupied negative-energy covariance, paired
with an adaptive DOP853 reconstruction, gives a nonzero scalar centre deficit
in the `static_vacuum` control even though the undeformed vacuum is an exact
stationary solution of the declared finite-box equations. The numerical
failure arises because the non-unitary mode update seeds a normal-ordered
source, and the coupled scalar equation amplifies that seed. This protocol
tests the same finite-box mechanism with a unitary mode update and an
implicit scalar midpoint coupling.

The protocol does not change the action, regulator, pulse amplitudes, grids,
late-window observables, capture thresholds, or physical scope. It replaces
only the time integrator and freezes that replacement before the recovery
run. A positive result remains a conditional regulated radial mechanism; it is
not complete physical matter formation.

## 1. Declared finite-box model

Use the dimensionless action

$$
\mathcal L_{\mathrm{bag}}
:=\frac12\partial_\mu\sigma\,\partial^\mu\sigma
-\frac{\lambda}{4}(\sigma^2-v^2)^2
+\bar\psi(i\gamma^\mu\partial_\mu-g\sigma)\psi,
$$

with $(v,\lambda,g)=(1,\tfrac14,6)$, spherical radius $R=16$, and the
three-dimensional radial $\kappa=-1$ channel. The scalar boundary is
$\sigma(R)=v$ with zero outer scalar velocity. There is no absorber, damping,
trap, external source, clamping, or post-processing energy removal.

The cell-centred spherical finite-volume scalar equation, Hermitian finite-box
Dirac matrix, fixed negative-energy covariance $U_0$, normal-ordered source,
and finite-dimensional normal-ordered energy are exactly those in the
declared parent protocol
`computations/matter-formation-fermion-vacuum-bag-prereg.md`.

At $t=0$ use $U=U_0$, $\pi=0$, and

$$
\sigma_i(0)=v-A\exp\left[-\frac{r_i^2}{2w^2}\right],\qquad w=2.5,
$$

with the frozen amplitudes $A\in\{1.5,2.0\}$ and the declared `G0`, `G1`,
and `G2` grids. Archive all states at $t=0,0.1,\ldots,12$.

## 2. Frozen unitary midpoint update

Let $H_n=H_{-1}(\sigma_n)$ and let $a(\sigma,U)$ be the declared scalar
acceleration including the normal-ordered source when the arm enables it. For
each fixed step $\Delta t$:

1. Evaluate $a_n=a(\sigma_n,U_n)$ and form the predictor
   $$
   \sigma^{\mathrm{pred}}=\sigma_n+\Delta t\,\pi_n
   +\tfrac12\Delta t^2 a_n,\qquad
   \pi^{\mathrm{pred}}=\pi_n+\Delta t a_n.
   $$
2. Perform exactly one fixed-point corrector. Set
   $\sigma_m=(\sigma_n+\sigma^{\mathrm{pred}})/2$, construct
   $H_m=H_{-1}(\sigma_m)$, and set
   $$
   U_m=\exp(-i\Delta t H_m/2)U_n.
   $$
   Evaluate $a_m=a(\sigma_m,U_m)$ and update
   $$
   \pi_{n+1}=\pi_n+\Delta t a_m,\qquad
   \sigma_{n+1}=\sigma_n+\tfrac12\Delta t(\pi_n+\pi_{n+1}).
   $$
3. Re-evaluate the midpoint $\sigma_m=(\sigma_n+\sigma_{n+1})/2$ and advance
   $$
   U_{n+1}=\exp(-i\Delta t H_m)U_n.
   $$

The matrix exponential is the dense SciPy exponential of the declared
Hermitian finite-box matrix. The full and half propagators are reused only
when all grid parameters agree and the midpoint scalar changes by at most
$10^{-12}$ in maximum absolute entry. This cache rule is part of the
integrator, applies to every arm, and is not a static-vacuum branch or a
post-step projection. No orthonormalization, source subtraction beyond the
declared normal ordering, damping, or observable smoothing is applied.

The primary implementation is
`computations/matter_formation_fermion_vacuum_bag_unitary_recovery.py`.
The independent verifier reassembles the finite-box operator, source, energy,
and observables in a separate module and independently reimplements the same
frozen update; it does not import the primary implementation.

## 3. Controls, observables, and stopping rule

Run the declared controls:

- `static_vacuum` on `G1`: $A=0$, full regulated vacuum $U_0$;
- `source_off` on `G1`: $A=1.5$, full covariance, source omitted from the
  scalar equation;
- `zero_covariance` on `G1`: $A=1.5$, $U=0$, source identically zero.

The controls are mandatory. The static control must have late mean centre
deficit at most $10^{-10}$ and late mean pair number at most $10^{-8}$. The
zero-covariance control must have late mode norm and pair number at most
$10^{-8}$. Candidate capture uses the frozen late means, late standard
deviations, energy drift, hole-gap, localization, and adjacent-grid
resolution thresholds. These thresholds are frozen for this recovery.

The candidate decision remains:

- `CAPTURED—conditional regulated radial vacuum-to-bag formation` if at least
  one frozen amplitude passes every candidate, control, resolution, raw-state,
  summary, finite-payload, and provenance check;
- `DOES NOT EMERGE—conditional regulated radial vacuum-to-bag formation` if
  every check passes but neither amplitude is captured;
- `INCONCLUSIVE` if any numerical reconstruction or provenance check fails.

The scientific conclusion is still restricted to the finite-box radial
regulated model. Even `CAPTURED` does not establish continuum
renormalization, all angular sectors, multi-pair dynamics, gravity, physical
units, particle identity, or complete physical matter formation.

## 4. Evidence and integrity

Run the primary first into a new exclusive output directory, then run the
independent verifier into a new exclusive `verification.json`. Preserve both
raw archives and source snapshots. The verifier must reject missing or altered
source identities, omitted arms, wrong shapes, nonfinite arrays, changed raw
states, failed controls, failed resolution, or summary disagreement. The
frozen raw-array tolerances remain the declared maximum absolute tolerance
$5\times10^{-4}$ for each float archive and $2\times10^{-3}$ for each scalar
summary.

The recovery is a numerical repair campaign, not permission to reinterpret a
failed or conditional result as a complete matter solution. If it passes, the
next boundary remains the physical completion requirements in
`foundations/matter-completion-boundary.md`.
