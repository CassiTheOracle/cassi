# Particle Carrier Localization Campaign Report

## Status: Tested—September 2026

## Abstract

Increasing the carrier-to-density coupling changes the registered diffuse
finite-grid state into compact, strongly retained carrier profiles across the
entire frozen scan. Every terminal profile satisfies the four measured shape
conditions: small outer-shell norm, radius below half the box, carrier
multiplier below the exterior threshold with its declared buffer, and deep
Yang/Yin density depletion. None reaches the required physical first-variation
precision, so no profile is accepted as a stationary localized branch.

The primary and independent verifier therefore return

$$
\boxed{\mathrm{INCONCLUSIVE\text{—}NUMERICAL\ EXECUTION\ OR\ VERIFICATION}}.
$$

The failed physical-stationarity condition is dominated by the carrier sector.
Softplus saturation suppresses optimizer gradients where the carrier tail
approaches zero and is a demonstrated contributor to that obstruction.
Positive carrier cells also retain a measurable residual, so the coordinate
map is not established as the sole cause. A direct normalized carrier
coordinate supplies the discriminating calculation and supports a distinct
localized, retained branch at the weakest scanned coupling; this coefficient
scan remains immutable as its source and diagnostic record.

## 1. Physical question

The campaign tests whether stronger density-depletion binding can overcome the
measured carrier gradient and self-repulsion costs in the registered static
action. At fixed charge, the exterior coefficient $e_C$ contributes the
constant $e_Cq_C$ and cannot alter the stationary field or the retention
margin. The scanned coefficient $h_C$ appears directly in the shape equation
through

$$
\widehat\omega_C-e_C
=\frac{E_{\nabla c}+u_C\int c^4\,d^3x
-h_C\int(1-\rho)c^2\,d^3x}{q_C}.
$$

The source state gives a frozen-field reference value
$h_{C,\rm ref}=5.919652152689433$ for the buffered condition
$\widehat\omega_C<0.73$. The campaign evaluates five declared multiples from
$0.5h_{C,\rm ref}$ through $1.5h_{C,\rm ref}$, with every arm reconstructed
from the same independently verified source artifact.

## 2. Verified scan result

All five coupling values produce terminal profiles whose measured carrier
radius, outer fraction, retention margin, and density depletion satisfy the
registered physical shape conditions. The weakest scanned coupling already
contracts the carrier radius from $2.5682251401285114$ to
$1.5606906519512618$ and lowers the outer fraction from
$0.015485205450071305$ to $0.0005072257731181344$. Its carrier multiplier moves
from $0.9619139451720476$ to $-0.0447908440646424$.

The compact shapes cannot be treated as stationary solutions because their
fixed-charge physical first variations remain above
$1.20\times10^{-4}$. The independently recomputed terminal values are:

| $h_C$ | Physical-gradient RMS | Cutoff virial | $\widehat\omega_C$ | Carrier radius | Outer carrier fraction | Maximum density depletion |
|---:|---:|---:|---:|---:|---:|---:|
| $2.9598260763447164$ | $6.081862190733707\times10^{-4}$ | $1.102453487619545\times10^{-3}$ | $-0.0447908440646424$ | $1.560690651951262$ | $5.072257731181344\times10^{-4}$ | $0.9862638581423362$ |
| $4.439739114517074$ | $1.472178156554608\times10^{-2}$ | $6.784053972260694\times10^{-2}$ | $-1.418282990767377$ | $1.382470270219112$ | $7.970085440015845\times10^{-12}$ | $0.9984850048125602$ |
| $5.919652152689433$ | $1.348526548165907\times10^{-2}$ | $9.465123452136480\times10^{-2}$ | $-2.939267867627875$ | $1.373261609805596$ | $1.153138298669564\times10^{-12}$ | $0.9996485650585444$ |
| $7.399565190861791$ | $1.043811476246302\times10^{-3}$ | $1.303671162100859\times10^{-3}$ | $-4.442096319844612$ | $1.357843619600499$ | $3.825946889681749\times10^{-6}$ | $0.9998785452776588$ |
| $8.879478229034149$ | $1.660589140993482\times10^{-3}$ | $1.073059659535245\times10^{-3}$ | $-5.927375538429561$ | $1.353165354145900$ | $6.727915330164126\times10^{-7}$ | $0.9999462408897863$ |

Each arm runs all four permitted continuation blocks because none reaches the
physical-gradient threshold. No primary is selected, and the larger-domain and
finer-grid calculations do not run under the frozen stopping rule. The result
therefore supplies neither a positive localized branch nor a negative statement
about the declared coupling interval.

## 3. Why the optimizer stopped before the physical field

The terminal optimizer-coordinate gradients are much smaller than the physical
carrier residuals. At $h_C=4.439739114517074$, the raw-gradient RMS is
$1.162635735826771\times10^{-8}$ while the physical-gradient RMS is
$1.472178156554608\times10^{-2}$. At
$h_C=5.919652152689433$, the corresponding values are
$1.392447915134940\times10^{-8}$ and
$1.348526548165907\times10^{-2}$. These separations exceed six orders of
magnitude at the two middle scan points.

The source implementation writes the carrier as

$$
c=\sqrt{q_C}\,
\frac{M\,\operatorname{softplus}(w)}
{\left[\int M\,\operatorname{softplus}(w)^2\,d^3x\right]^{1/2}},
$$

where $M$ fixes the outer shell to zero. Its Jacobian contains
$\operatorname{sigmoid}(w)$. When the optimized tail drives $w$ far below
zero, a nonzero physical residual is multiplied by a vanishing coordinate
Jacobian before L-BFGS sees it.

A post-result decomposition recomputes the fixed-charge physical residual from
each hash-bound terminal artifact. The carrier component accounts for the
failure at every coupling. At the weakest value its carrier residual RMS is
$2.506940106768746\times10^{-3}$, while the real Yang/Yin amplitude residual is
$2.661224339370644\times10^{-5}$. At the two middle values the carrier residual
RMS values are $0.06069946038892926$ and $0.05560117396641451$, while all other
field components are below $3.2\times10^{-7}$ RMS.

The two middle artifacts contain exact floating-point zeros at $3286$ of the
$3375$ interior carrier cells. A nonnegative-field Karush–Kuhn–Tucker check does
not rescue these endpoints: $138$ zero cells have negative projected carrier
residuals, so increasing the carrier there supplies feasible descent
directions. Their constrained residual RMS values remain
$0.06069946038892926$ and $0.05560117396641451$.

The reproducible residual decomposition is implemented in
`computations/analyze_particle_carrier_localization_residual.py`. It consumes
the completed result and verification hashes, checks every terminal NPZ hash,
and reproduces each reported aggregate physical-gradient RMS before separating
its field components. This diagnostic does not alter the frozen campaign
verdict.

## 4. Independent verification and evidence

The preflight verifier reports zero mismatches before execution. The final
verifier loads every field artifact with `allow_pickle=False`, uses an explicit
$h_C$ argument in both its NumPy energy and PyTorch first-variation
implementations, checks the complete remaining coefficient vector, and
reconstructs the frozen candidate order and stopping rule. It reports zero
mismatches across all five terminal artifacts.

The evidence hashes are:

| Evidence | SHA-256 |
|---|---|
| campaign manifest | `34eb13a8286261285dcd9ea84e7275cc8069965d81b5fcb59bcfd1fd36cb969b` |
| preflight receipt | `8f26fb82812664266f6d80cb359b7d0fc53a403057a1af3f27de633a256cf97c` |
| primary result receipt | `5a90e405d9d6851a1e445633adc0523de9c94d64e9ed27c139f177f92432a2d0` |
| independent verification receipt | `f30f95e71ab8a66b6aac1fd84001dba82771257a3ead73e200fd32c85eb5d4ad` |

The execution commands are:

```text
python computations/verify_particle_carrier_localization.py --preflight
python computations/particle_carrier_localization.py
python computations/verify_particle_carrier_localization.py
python computations/analyze_particle_carrier_localization_residual.py
```

The campaign runs on the registered ROCm device in deterministic `float64`
arithmetic with `CUDA_VISIBLE_DEVICES=0`,
`PYTORCH_HIP_ALLOC_CONF=expandable_segments:True`, and `HSA_ENABLE_SDMA=0`.
The evidence directories are
`runs/20260902_particle_carrier_localization/` and
`runs/20260902_particle_carrier_localization_residual_analysis/`.

## 5. Scientific boundary and resolved numerical intervention

The scan shows that density-depletion binding can produce compact carrier
profiles within the static action, including a buffered multiplier and a small
outer norm at the weakest tested increase. This statement concerns measured
shapes along incomplete softplus-coordinate optimization paths. None of the
five scan endpoints qualifies as a stationary localized branch because its
physical carrier first variation remains above the frozen threshold.

The direct shell-masked carrier coordinate normalized to $q_C$ keeps the
functional, field class, source artifacts, charge, grids, coupling value, and
physical-stationarity statistic fixed while removing the singular tail
suppression. At $h_C=2.9598260763447164$, that calculation reaches a physically
stationary, nodeless, localized, carrier-retaining endpoint. Independent
refinements support the same branch on four same-domain grids and one
larger-domain grid; the two finest adjacent comparisons pass their frozen
tolerances, and the absolute energy drift contracts twice.

The result remains finite-grid and coefficient-selected. The localized
branch's constrained Hessian, continuum existence, unrestricted symmetry,
topology-changing competitors, spatially resolved phase mode, mixed temporal
spectrum, decay channels, lifetime, physical carrier identity, units, spin,
and statistics remain open.

## References

- `computations/particle-carrier-localization-prereg.md`—frozen physical
  question, coupling grid, optimization schedule, and verdict tree.
- `computations/particle_carrier_localization.py`—primary coupling scan.
- `computations/verify_particle_carrier_localization.py`—independent
  coefficient-aware verifier.
- `computations/analyze_particle_carrier_localization_residual.py`—post-result
  decomposition of the physical first variation.
- `computations/particle-carrier-direct-coordinate-report.md`—direct normalized
  carrier recovery, larger-domain control, and mapped coefficient.
- `computations/particle-carrier-resolution-recovery-report.md`—independently
  verified same-domain refinements and finite-grid resolution verdict.
- `computations/particle-stationary-precision-v5-report.md`—hash-bound source
  stationary field.
- `foundations/core-trapped-charge-support.md`—carrier binding and retention
  conditions.
- `foundations/particle-stationary-action-closure.md`—static functional and
  fixed-charge variational boundary.
- `foundations/matter-completion-boundary.md`—remaining conditions for a
  physical matter claim.
