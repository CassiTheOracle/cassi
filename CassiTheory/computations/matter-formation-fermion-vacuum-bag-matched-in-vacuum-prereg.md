# Matched In-Vacuum Recovery: Regulated Spatial Vacuum-to-Bag Formation

## Status: New recovery protocol—September 2026

## Purpose and failed requirement

The unitary midpoint recovery removes the finite-step vacuum drift, but its
candidate pair number and scalar deformation are not grid converged. On the
three declared grids, the $A=1.5$ late pair means are $4.4741$, $12.7387$ and
$25.1690$, and the $A=2.0$ means are $4.9819$, $8.0182$ and $20.4527$. This
protocol addresses the measured resolution failure by changing the declared
initial quantum state, not by changing a threshold or selecting a favorable
grid.

The scalar pulse is initialized as before. On each amplitude and grid, the
fermionic state is instead the exact finite-box negative-energy vacuum of the
same initial scalar profile. The state therefore contains no instantaneous
mass-quench mismatch at $t=0$. The scalar then evolves autonomously and the
fermion covariance is propagated with the source-bound unitary midpoint update.
A positive result remains a conditional regulated radial mechanism. It is not
complete physical matter formation.

## 1. Declared finite-box action

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

The finite-volume scalar equation, Hermitian finite-box Dirac matrix, and
radial stencil are unchanged from
`computations/matter-formation-fermion-vacuum-bag-prereg.md`.

For amplitude $A$ define the declared initial scalar profile

$$
\sigma_i(r)=v-A\exp\!\left[-\frac{r^2}{2w^2}\right],\qquad w=2.5.
$$

On each grid construct

$$
H_i=H_{-1}(\sigma_i),
$$

and let $U_i$ contain all normalized negative-energy eigenvectors of $H_i$.
The initial state is the exact regulated in-vacuum

$$
U(0)=U_i,\qquad \pi(0)=0.
$$

This is a declared finite-box density operator/state prescription; it is not
a continuum renormalized vacuum and does not supply a physical particle map.

## 2. Matched normal ordering and energy

Let $b_i(r)$ be the radial density of $U_i$ and let
$s_i^{(0)}=\Delta r\,b_i/V_i$ be its cell source. The scalar force uses
normal ordering relative to this same state:

$$
 s_{\mathrm{NO},i}(r_j)
 =\frac{\sum_a(|U_{ja}|^2-|U_{N+j,a}|^2)-b_i(r_j)}{4\pi r_j^2}.
$$

The regulated energy used in every receipt is

$$
\begin{aligned}
E_{\mathrm{NO},i}={}&E_\sigma[\sigma,\pi]
+\Delta r\,\operatorname{Re}\operatorname{Tr}
 \left(U^\dagger H_{-1}(\sigma)U-U_i^\dagger H_iU_i\right)\\
&-g\sum_j V_j s_i^{(0)}(r_j)\,[\sigma_j-\sigma_{i,j}].
\end{aligned}
$$

The reference in the counterterm is the same initial profile used to define
$H_i$. At $t=0$ the fermionic contribution and its counterterm both vanish,
so the initial energy is the scalar pulse energy. The source and energy use the
same $U_i$ on every candidate arm and on the controls.

## 3. Frozen unitary update and observables

Use exactly one self-consistent implicit midpoint correction per fixed step.
With $H_m=H_{-1}((\sigma_n+\sigma_{n+1})/2)$,

$$
U_m=\exp(-i\Delta t H_m/2)U_n,
\qquad
U_{n+1}=\exp(-i\Delta t H_m)U_n,
$$

with the scalar predictor/corrector equations in
`computations/matter-formation-fermion-vacuum-bag-unitary-recovery-prereg.md`.
The exponential cache tolerance is $10^{-12}$ in maximum midpoint-scalar
entry and applies identically to every arm.

The regulated excitation observable uses the positive-energy projector
$P_{i,+}$ of the same initial Hamiltonian $H_i$:

$$
N_{\mathrm{pair},i}=\operatorname{Tr}(P_{i,+}UU^\dagger).
$$

The radial density, core probability $P_{4,i}$, RMS radius $R_i$, centre
deficit, outer scalar-energy fraction, energy drift, particle/hole gap, and
late-window standard deviations use the same definitions and thresholds as
the unitary recovery. This is an in-vacuum excitation observable for the
regulated action; it is not asserted to be the physical particle number.

Use $A\in\{1.5,2.0\}$, grids `G0`, `G1`, and `G2`, and archive every state at
$t=0,0.1,\ldots,12$. Keep the existing late window $8\le t\le12$ and all
candidate thresholds unchanged:

- late mean pair number at least $0.02$;
- late mean core probability at least $0.50$;
- late RMS radius at most $5$;
- late pair-number standard deviation at most $0.10$;
- late RMS standard deviation at most $0.75$;
- mean centre deficit at least $0.05$;
- outer scalar-energy fraction below $0.20$;
- relative energy drift at most $5\times10^{-3}$;
- particle/hole gap at most $0.10$;
- every adjacent-grid difference in the four registered observables at most
  $0.15$.

## 4. Controls and decision rule

Run the same mandatory controls on `G1`:

- `static_vacuum`: $A=0$, $H_i=H_{-1}(v)$, full matched vacuum;
- `source_off`: $A=1.5$, matched in-vacuum, source omitted from the scalar
  equation;
- `zero_covariance`: $A=1.5$, modes set identically to zero and source zero.

The static control must have late centre deficit at most $10^{-10}$ and late
pair number at most $10^{-8}$. The zero-covariance control must have late mode
norm and pair number at most $10^{-8}$. The independent reconstruction must
also pass all raw-array, summary, finite-payload, source-identity, archive,
control, and resolution checks.

The verdict is:

- `CAPTURED—conditional matched-in-vacuum regulated radial formation` if at
  least one amplitude passes every candidate and numerical check;
- `DOES NOT EMERGE—conditional matched-in-vacuum regulated radial formation`
  if all checks pass but neither amplitude captures;
- `INCONCLUSIVE` if any numerical reconstruction, control, or provenance check
  fails.

Regardless of the result, `complete_physical_matter_formation` remains false.
A positive result would still lack continuum renormalization, all angular
sectors, physical units, a canonical Cassi action, nonlinear infinite-domain
stability, and a derived particle identity.

## 5. Evidence contract

The primary is
`computations/matter_formation_fermion_vacuum_bag_matched_in_vacuum.py`.
The independent verifier is
`computations/verify_matter_formation_fermion_vacuum_bag_matched_in_vacuum.py`.
Neither imports the other. The primary runs first into the fresh output

`runs/20260913_matter_formation_fermion_vacuum_bag_matched_in_vacuum/`

and the verifier runs into the fresh output

`runs/20260913_matter_formation_fermion_vacuum_bag_matched_in_vacuum_verification/`.

Both receipts preserve source snapshots and all raw arrays. The verifier must
independently construct $H_i$, $U_i$, the matched source and counterterm,
the unitary midpoint update, every observable, and the frozen predicates.
Existing source files and receipts are immutable inputs; a failure receives a
new diagnosis and does not authorize changing this protocol after execution.

This protocol tests one specific resolution repair: removing the sudden
state/background mismatch while retaining the same action, finite-energy
scalar pulse, reciprocal backreaction, and no external drive. It does not
claim that a finite-box matched in-vacuum is the missing continuum quantum
completion.
