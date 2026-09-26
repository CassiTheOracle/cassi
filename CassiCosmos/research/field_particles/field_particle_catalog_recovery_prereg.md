# Field-Particle Catalog Recovery Preregistration

## Status: Frozen—September 2, 2026

## 1. Question

Can a derived particle catalog identify localized carrier bodies without
promoting the seed's grid-scale carrier-density alternation into hundreds of
spurious objects, while remaining observational and unable to alter canonical
field evolution?

## 2. Frozen readout

The catalog is derived from the canonical carrier density
$|\chi_C|^2$ as follows:

1. Form a clipped $3\times3\times3$ box average of carrier density at every
   grid cell.
2. Mark core cells whose averaged density is at least 5% of the averaged peak.
3. Build six-neighbor connected core components.
4. Discard one-cell components as unresolved grid-scale peaks.
5. Assign every raw carrier-density cell to its nearest retained core center.
6. Compute charge, center, RMS radius, current-derived velocity, energy share,
   peak density, and core-cell count from canonical state. The catalog is never
   fed back into the field update.

The existing empty-density cutoff remains `1e-10` in integrated carrier charge.
No field equation, coefficient, timestep, or RK4 path changes.

## 3. Registered controls

The next windowed run of `res://scenes/verify_field_particles.tscn` adds these
checks while retaining every existing FP0–FP9 gate:

- pinned seed catalog contains exactly one object;
- the single object carries the complete seed charge within `2e-5` relative;
- repeated reads and clear/reconstruct cycles are byte-identical;
- catalog reads leave the next canonical field state byte-identical;
- stationary final catalog contains exactly one object;
- vacuum catalog is empty before and after its numerical control;
- boosted initial and final catalogs contain exactly one object;
- a readout-only two-Gaussian carrier control produces exactly two objects,
  total catalog charge matches direct carrier integration within `2e-5`, and
  the two centers lie on opposite sides of the selected axis.

The two-Gaussian control uses the runtime vacuum for every non-carrier field,
centers at $x=\pm1.5$, width $\sigma=0.45$, equal real carrier amplitudes, zero
velocities, and the existing fixed boundary vacuum shell. It is restored to the
pinned seed before any dynamics measurement.

## 4. Decision rule

`PASS—FIELD-PARTICLE CATALOG RECOVERY` requires every registered catalog check,
all prior identity/dynamics controls, and the independent NumPy verifier to
pass in one windowed arm. Any failure gives
`FAIL—FIELD-PARTICLE CATALOG RECOVERY`. Results are recorded before production
integration changes.
