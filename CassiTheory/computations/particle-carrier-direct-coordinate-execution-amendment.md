# Particle Carrier Direct-Coordinate Execution Amendment

## Status: Preregistered—September 2026

## Abstract

The canonical direct-coordinate recovery calculation uses the unchanged physical question, action, coefficient scan, source artifacts, grids, optimizer schedule, endpoint conditions, stopping rule, comparison tests, and verdict tree in `computations/particle-carrier-direct-coordinate-prereg.md`. This amendment makes the carrier map conform to the stationary solver's existing callable interface and explicitly applies the already-frozen scalar symmetry projector. The evidentiary execution writes to a fresh output directory.

## 1. Interface defect receipt

The directory `runs/20260902_particle_carrier_direct_coordinate/` is a non-evidentiary execution receipt. Its preflight passed, but the driver stopped while reconstructing the first source and before any optimization block began. The stationary objective calls every field map as `physical_fields(raw, grid, charge)`, while the direct map accepted only `raw` and `grid`. The resulting `TypeError` prevents a physical result or scientific verdict.

The preserved receipts are bound by

| Receipt | SHA-256 |
|---|---|
| `preflight_verification.json` | `5cd893b0f27cbd9c189556ccabbd98b917b13ffd7e8be7ebba92ae91e5b78bc4` |
| `results.json` | `b7ebb2f53e72b343e03a1ae77ea37fc198f1f0bd52a9b278ee707c7970e79f87` |
| `failure.json` | `f16f03104bf5dd62725554d3dd6b1d4243fcd15bd0002d9c433f6309867e509c` |

The partial result has `status: in_progress`, contains no primary arm, and cannot enter the verdict tree.

## 2. Frozen repair

The direct carrier map has the same three-argument interface as the stationary field map. For a requested charge $q>0$, it computes

$$
\widetilde c=M\mathcal P_{C_4}z,
\qquad
c=\sqrt{q}\,
\frac{\widetilde c}{\left[\int \widetilde c^2\,d^3x\right]^{1/2}},
$$

where $M$ is the fixed-shell mask and $\mathcal P_{C_4}$ is the scalar projector already required by the source campaign. For $q=0$, it returns the zero carrier field. The Yang/Yin amplitudes, adjoint field, and spatial connection continue through their original maps with the same requested charge argument.

This repair changes no action term, coefficient, source field, primary order, grid, numerical precision, optimizer setting, stationarity threshold, localization threshold, nodeless condition, comparison tolerance, stopping rule, or scientific verdict. Applying $\mathcal P_{C_4}$ enforces the frozen symmetry class; it does not add a new restriction.

## 3. Canonical execution path

The evidentiary calculation writes only to `runs/20260902_particle_carrier_direct_coordinate_v2/`. Its manifest, preflight, result, verification, and failure schemas use version 2. The occupied interface-failure directory remains unchanged.

The version-2 manifest binds this amendment, the unchanged preregistration, the repaired primary driver, the repaired independent verifier, the source campaign code, the stationary solver and recovery code, both source receipts, and all five source artifacts. A fresh independent preflight must pass before the driver can start.

## References

- `computations/particle-carrier-direct-coordinate-prereg.md`—frozen physical question, numerical protocol, and verdict tree.
- `computations/particle_carrier_direct_coordinate.py`—primary direct-coordinate driver.
- `computations/verify_particle_carrier_direct_coordinate.py`—independent source, artifact, and verdict verifier.
- `computations/particle_stationary_bvp.py`—stationary field-map interface and physical diagnostics.
