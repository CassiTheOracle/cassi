# Particle Carrier Direct-Coordinate Recovery

## Status: Preregistered—September 2026

## Abstract

This campaign asks whether the compact carrier profiles already produced by the
static particle action become genuine fixed-charge stationary points when the
carrier is optimized in a nonsaturating coordinate. The completed localization
scan shows that stronger density-depletion binding contracts and retains the
carrier, but the positive softplus coordinate suppresses its optimizer gradient
before the physical carrier equation is solved. The new calculation keeps the
action, coefficients, charge, grids, symmetry class, physical stationarity
statistic, localization thresholds, and coefficient order fixed while replacing
only that coordinate map.

A successful result establishes a nodeless finite-grid stationary branch and
tests whether its measured scale reproduces on the declared larger domain and
finer grid. It cannot identify a physical carrier, derive the selected coupling,
prove continuum existence, establish unrestricted stability, or determine
particle quantum numbers.

## 1. Registered numerical obstruction

The source scan evaluates five couplings between
$h_C=2.9598260763447164$ and $h_C=8.879478229034149$. Every terminal artifact
has a carrier radius below half the box, an outer carrier fraction below
$10^{-3}$, a multiplier below $0.73$, and density depletion above $0.10$. None
reaches the required physical-gradient RMS of $1.20\times10^{-4}$, so the scan
has the independently verified verdict
`INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION`.

The physical residual is concentrated in the carrier field. At
$h_C=4.439739114517074$, the raw optimizer-gradient RMS is
$1.162635735826771\times10^{-8}$ while the fixed-charge physical-gradient RMS
is $1.472178156554608\times10^{-2}$. The artifact contains exact zeros at
$3286$ of $3375$ interior carrier cells, and $138$ of those cells have negative
projected carrier residual. The endpoint therefore has feasible directions that
lower the energy even when the carrier is interpreted as nonnegative.

The source coordinate is

$$
c(w)=\sqrt{q_C}\,
\frac{M\operatorname{softplus}(w)}
{\left[\int M\operatorname{softplus}(w)^2\,d^3x\right]^{1/2}}.
$$

Its Jacobian contains $\operatorname{sigmoid}(w)$, which approaches zero with
the carrier tail. The small raw gradient is consequently not evidence for a
small physical first variation.

## 2. Frozen intervention

The campaign replaces the carrier map with

$$
c(z)=\sqrt{q_C}\,
\frac{Mz}{\left[\int (Mz)^2\,d^3x\right]^{1/2}}.
$$

The shell mask $M$, fixed charge $q_C=4$, volume quadrature, and all other field
maps remain unchanged. The direct map is invariant under the global sign
$z\mapsto-z$ and has no softplus saturation on small tails. Its sole null
direction is radial rescaling of $z$, which the charge normalization removes
from the physical first-variation statistic.

The direct coordinate permits signed intermediate iterates. A terminal carrier
is admitted to the nodeless branch only after orienting its global sign so that
$\int c\,d^3x\ge0$ and checking

$$
\frac{\int [\min(c,0)]^2\,d^3x}{q_C}\le10^{-12}.
$$

This negative-norm fraction is a physical endpoint condition. The stationarity
statistic remains the unrestricted fixed-charge tangent residual, so a field
cannot pass by resting on a pointwise positivity boundary.

No action term, coefficient, charge, grid, finite-difference operator,
quadrature, boundary value, $C_4$ projector, gauge statistic, flux statistic,
localization threshold, comparison tolerance, or scientific verdict is changed.

## 3. Immutable source chain

The coefficient scan result receipt is
`runs/20260902_particle_carrier_localization/results.json`, with SHA-256
`5a90e405d9d6851a1e445633adc0523de9c94d64e9ed27c139f177f92432a2d0`.
Its independent verification receipt has SHA-256
`f30f95e71ab8a66b6aac1fd84001dba82771257a3ead73e200fd32c85eb5d4ad`
and contains no mismatches.

Each coupling starts from its own terminal artifact in that receipt:

| Scan order | $h_C$ | Source artifact | SHA-256 |
|---:|---:|---|---|
| 1 | $2.9598260763447164$ | `fields_primary_half_reference_block04.npz` | `9f9c37cd75d0b6ccbe427c2afaa10aa8659c9cb532868cbe41183a11bddfea83` |
| 2 | $4.439739114517074$ | `fields_primary_three_quarters_reference_block04.npz` | `534bbe5a6ce04b7ad36975a97e507388b15a2fe7533312a81ee1e15202c742b5` |
| 3 | $5.919652152689433$ | `fields_primary_reference_block04.npz` | `fea3d1dc1e40817d65b68c13edd52f18e163ef6ca0cc0e48ce05932f99fde8d2` |
| 4 | $7.399565190861791$ | `fields_primary_five_quarters_reference_block04.npz` | `3241d9b5ee33765a867073231c0cd55f614e7b33ade41a3c0fa2e622fa3f8232` |
| 5 | $8.879478229034149$ | `fields_primary_three_halves_reference_block04.npz` | `262e5bb08c15a26970f7095b1477ac9d782c9fba864a41ced498b003ec7f44d7` |

Each physical artifact is converted exactly into the direct coordinate by
copying its saved carrier field into $z$ and retaining the canonical preimages
of the Yang/Yin amplitudes, adjoint field, and spatial connection. The direct
map must reproduce every source field within a maximum relative infinity error
of $5\times10^{-12}$ before an optimization begins.

Every coupling retains its own source. No endpoint from a stronger value seeds
a weaker value, and no direct-coordinate endpoint seeds another primary arm.
No random number generator is used.

## 4. Frozen coefficients and order

All static coefficients other than the scanned value remain fixed at

$$
\begin{aligned}
&\alpha_{\mathfrak s}=1,\quad u_\rho=4,\quad u_\varphi=4,
\quad \gamma_x=\gamma_{\mathfrak s}=1,\quad u_H=4,\\
&k_{Cx}=k_{C\mathfrak s}=1,\quad e_C=0.75,\quad u_C=1,
\quad q_C=4,\quad L_{\mathfrak s}=1,\quad \xi_{\rm gf}=1.
\end{aligned}
$$

The five $h_C$ values and their ascending order are exactly those in Section 3.
Each is evaluated until it qualifies numerically or consumes its block limit.
A numerically unresolved arm is recorded and the scan proceeds. The first
qualified arm satisfying the nodeless and localization conditions is selected,
and no stronger primary runs. If no arm is selected, all five values must be
attempted.

## 5. Frozen optimization and endpoint conditions

Each primary source runs at most eight fresh strong-Wolfe L-BFGS blocks. Every
block uses `max_iter=880`, `max_eval=1100`, `history_size=20`,
`tolerance_grad=1e-10`, and `tolerance_change=1e-12`. A block resets the
L-BFGS history and preserves the accepted physical endpoint from the preceding
block.

A primary endpoint qualifies numerically only when it has finite fields and
diagnostics and satisfies all of the following conditions:

1. relative charge error is at most $5\times10^{-12}$ and the fixed-boundary
   residual is at most $10^{-12}$;
2. unrestricted fixed-charge physical-gradient RMS is at most
   $1.20\times10^{-4}$ and the cutoff virial is at most $0.08$;
3. gauge-divergence RMS is at most $0.02$ and the gauge-fixing energy fraction
   is at most $0.01$;
4. outer flux RMS is at most $0.05$ and the absolute outer magnetic number is at
   most $10^{-10}$.

A numerically qualified endpoint enters the nodeless localized branch only when
its oriented negative-norm fraction is at most $10^{-12}$, its outer carrier
fraction is at most $10^{-3}$, its carrier radius is smaller than $R/2$, its
carrier multiplier is below $0.73$, and its maximum Yang/Yin density depletion
is at least $0.10$.

Optimization stops at the first numerically qualified block for each coupling.
A qualified shape failure proceeds to the next frozen coupling. An unqualified
arm also proceeds after its eighth block. The primary scan stops at the first
nodeless localized endpoint or after all five values have been attempted.

Every block writes its physical fields, byte-stream hash, coefficient vector,
parameterization name, optimizer history, physical energy decomposition,
physical first variation, virial response, charge, boundary values, gauge
measures, flux, carrier geometry, density depletion, multiplier, and
negative-norm fraction. Raw coordinate gradients remain execution diagnostics;
they do not control endpoint selection.

## 6. Larger-domain and finer-grid test

A selected primary is tested at the same coefficient vector on the larger
$(R,N,\Delta x)=(5,21,0.5)$ grid and the finer
$(R,N,\Delta x)=(4,21,0.4)$ grid. Each comparison starts independently from the
deterministic `separated_core` analytic seed. The analytic carrier field is
copied into the direct normalized coordinate before optimization.

Each comparison runs the registered 800-step Adam plus 120-iteration L-BFGS
initialization, followed by at most eight continuation blocks with the settings
in Section 5. Both grids must independently satisfy the numerical, nodeless,
and localization conditions.

A comparison passes when physical energy agrees with the primary within $5\%$,
core length within $0.75$, carrier multiplier within $0.10$, and carrier radius
within $10\%$. Absolute carrier radii are compared because every admitted field
has outer carrier fraction below $1\%$.

## 7. Independent verification

The independent verifier is
`computations/verify_particle_carrier_direct_coordinate.py`. It does not import
the primary driver. Before execution it checks every manifest hash, the prior
result and verification receipts, all five source artifact hashes and schemas,
the full coefficient vectors, source diagnostics, source localization shapes,
direct-coordinate round trips, candidate order, optimization limits, and a
fresh output path.

After execution the verifier loads every artifact with `allow_pickle=False` and
independently recomputes its physical energy, unrestricted fixed-charge first
variation, virial response, boundary values, gauge measures, magnetic flux,
carrier geometry, density depletion, multiplier, and oriented negative-norm
fraction. The verifier reconstructs the first allowed selected coupling, both
grid comparisons, and the scientific verdict. It also checks that the
hash-bound primary implementation declares the direct normalized coordinate for
every optimizer block.

Primary and independent scalar values must satisfy

$$
|x_{\rm primary}-x_{\rm independent}|
\le10^{-8}+10^{-6}|x_{\rm independent}|.
$$

Exact booleans, strings, dimensions, candidate order, coefficient values,
parameterization names, and hashes must match exactly. The comparison tolerance
does not alter any physical threshold.

## 8. Verdict tree

A clean nodeless localized primary with matching larger-domain and finer-grid
states receives
`EMERGES—DOMAIN-AND-RESOLUTION-MATCHED LOCALIZED RETAINED BRANCH`.

A clean nodeless localized primary whose completed comparison states miss a
localization or matching condition receives
`EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY`.

Five numerically qualified primary negatives receive
`DOES NOT EMERGE—NO NODELESS LOCALIZED RETAINED PRIMARY IN FROZEN BRACKET`.

A missing or changed source, an incomplete scan, any numerical qualification
failure without a selected primary, an unqualified comparison grid, an
artifact mismatch, or an independent-verification mismatch receives
`INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION`.

## 9. Scientific boundary

A domain-and-resolution-matched result supplies the background for a separately
preregistered physical-quotient and low-spectrum calculation at the selected
coefficient vector. That calculation must reproduce a spatially resolved global
phase mode and a nonnegative low spectrum on the comparison grids before a
mixed temporal-spectrum campaign begins.

A finite-grid-only result requires a spatial recovery campaign around the
selected coefficient. A negative result shows that the direct-coordinate
recovery does not find a nodeless localized stationary point in the five frozen
source basins. Every result leaves physical carrier identity, dimensional
calibration, continuum existence, unrestricted deformations, topology-changing
competitors, temporal stability, lifetime, spin, and statistics open.

## References

- `computations/particle-carrier-localization-report.md`—source coefficient
  scan, physical shape measurements, and coordinate-saturation diagnosis.
- `computations/particle_carrier_localization.py`—source optimizer and artifact
  writer.
- `computations/verify_particle_carrier_localization.py`—independent
  coefficient-aware source verifier.
- `computations/analyze_particle_carrier_localization_residual.py`—source
  physical-residual decomposition.
- `computations/particle_stationary_bvp.py`—static action, field maps, and
  physical diagnostics.
- `computations/particle_stationary_q2_recovery_v2.py`—canonical reconstruction
  and continuation engine.
- `foundations/core-trapped-charge-support.md`—carrier binding and retention
  conditions.
- `foundations/particle-stationary-action-closure.md`—fixed-charge variational
  and fluctuation boundaries.
- `foundations/matter-completion-boundary.md`—remaining conditions for a
  physical matter claim.
