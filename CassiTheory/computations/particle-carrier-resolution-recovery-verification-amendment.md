# Particle Carrier Resolution-Recovery Verification Amendment

## Status: Preregistered—September 2026

## Abstract

The carrier-resolution calculation completed both frozen refinements and produced a decreasing sequence of adjacent energy differences. Its first final verification nevertheless reported four schema mismatches caused by two receipt-shape assumptions rather than by any physical or numerical disagreement. This amendment freezes the exact schema repair and requires a fresh preflight, a fresh deterministic execution, and a fresh independent verification before the calculation can carry a scientific verdict.

## 1. Verification-defect receipt

The preserved directory `runs/20260902_particle_carrier_resolution_recovery_verifier_defect/` records a non-evidentiary execution. Both refinements reached physically stationary, nodeless, localized endpoints in their first continuation blocks, and the independent reconstruction reproduced the physical diagnostics, branch conditions, adjacent comparisons, energy-difference contraction, and strongest decision-tree outcome. Final verification still failed because the verifier required a different receipt shape in four places.

The first receipt mismatch came from two optimizer-coordinate gradient values retained alongside the physical source diagnostics. Those values do not enter physical stationarity, localization, nodelessness, adjacent-grid comparison, energy contraction, or the verdict. The independent verifier correctly recomputed the physical diagnostic subset but then compared that subset against the unfiltered source receipt as an exact key set.

The second receipt mismatch came from looking for the analytic-seed conversion under `reconstruction`. The established direct-coordinate arm schema stores the same conversion under `source_reconstruction`. The conversion receipt exists for both refinements and records both the relative and absolute direct-map round trips; the verifier addressed the wrong key.

The preserved files are bound by

| Receipt | SHA-256 |
|---|---|
| `preflight_verification.json` | `66faa9c77ffd017bedf808cdf088605fb1f20a7b0c7876c8d98c9eb1a20fb636` |
| `results.json` | `6de99fc827c94d651eeab325485d2bc9e8a64f0a9d14573f7b1e50c2c334b5d7` |
| `verification.json` | `09261972e6d6b57d25952a2ada2643fd68aad63d3978081d214ec4dd864eae77` |
| `fields_resolution_X1_block01.npz` | `c75a4255da2008a90268fcda83fcdbdca5a8386f9f580f854737668b664e8393` |
| `fields_resolution_X2_block01.npz` | `db42c53c5ca0f5a984fc2614168198417f95b289911904596b96cd4c5e8988c0` |

The failed verification receipt has `pass: false`, four mismatches, and the scientific verdict `INCONCLUSIVE—NUMERICAL EXECUTION OR VERIFICATION`. It remains a debugging record and cannot support a physical claim.

## 2. Frozen schema repair

The primary receipt now stores only the independently reproducible physical diagnostic subset for each inherited source level. The optimizer-coordinate gradient values remain in the immutable direct-coordinate source result, where they belong, but are not copied into the resolution campaign's physical source receipt.

The independent verifier now reads the analytic-seed conversion from `source_reconstruction`, matching the established direct-coordinate arm schema. It continues to require the registered parameterization, deterministic separated-core basin, relative round-trip tolerance, absolute round-trip tolerance, and passing round-trip flags.

No action term, coefficient, selected branch, source artifact, grid, seed, optimizer setting, continuation budget, physical-stationarity threshold, localization threshold, nodeless condition, comparison statistic, tolerance, stopping rule, or decision-tree branch changes under this amendment.

## 3. Canonical rerun

The non-evidentiary directory is moved intact before the canonical path is reused. The amended manifest binds this document and the repaired primary and independent-verification code. A new independent preflight must pass against that manifest, after which both deterministic refinement arms must run again from their analytic seeds. The final independent receipt must report zero mismatches before the frozen decision tree supplies a scientific verdict.

## References

- `computations/particle-carrier-resolution-recovery-prereg.md`—frozen physical question, refinement schedule, comparison statistics, and verdict tree.
- `computations/particle_carrier_resolution_recovery.py`—primary deterministic refinement driver and physical source receipt.
- `computations/verify_particle_carrier_resolution_recovery.py`—independent artifact, diagnostic, branch, comparison, and verdict verifier.
- `computations/particle-carrier-direct-coordinate-report.md`—source branch and its finite-grid numerical boundary.
