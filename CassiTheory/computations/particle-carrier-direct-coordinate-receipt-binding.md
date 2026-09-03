# Particle Carrier Direct-Coordinate Receipt Binding

## Status: Verified—September 2026

## Abstract

Downstream calculations must bind the exact bytes at the canonical direct-coordinate result and verification paths. Their SHA-256 values are fixed here together with the scientific fields that make the receipts admissible. This binding changes no field, diagnostic, threshold, comparison, or verdict.

## 1. Canonical byte hashes

| Receipt | SHA-256 |
|---|---|
| `runs/20260902_particle_carrier_direct_coordinate_v2/results.json` | `59f39d6e565ab24faab705094ea5ee1001d7ab3939d8a923db091dc903e44c73` |
| `runs/20260902_particle_carrier_direct_coordinate_v2/verification.json` | `b858d05df7db577896f6f5ff325efba2922d90cc9359c9a7264631ad1c314629` |

The result has schema `cassi.particle-carrier-direct-coordinate.results.v2`, status `complete`, manifest SHA-256 `d602e50f0a8d9a4c8f306930017d92101b797d695daaf3315a79a423c6f20f77`, and verdict `EMERGES—FINITE-GRID LOCALIZED RETAINED BRANCH ONLY`.

The independent verification has schema `cassi.particle-carrier-direct-coordinate.verification.v2`, `pass: true`, an empty mismatch list, the same manifest hash, and the same scientific verdict.

## 2. Terminal artifact bindings

The primary artifact remains `fields_primary_half_reference_block01.npz`, SHA-256 `c32beb4ee7bc7746a4fc18b63bc04ef7db12cc18505c9bee8ce2d298ddc25837`. The larger-domain artifact remains `fields_comparison_D_block01.npz`, SHA-256 `54ea983bb78783f2e0619851741f47167a2c9d6fb08757ce70361b0d1369c460`. The finer-grid artifact remains `fields_comparison_H_block01.npz`, SHA-256 `8aa65f3c08167c902660f9e8d09c0ce921d43c7f0af152b31aae79db6875810f`.

Any downstream preflight must recompute the physical diagnostics from these arrays rather than trust the JSON summaries alone.

## References

- `computations/particle-carrier-direct-coordinate-report.md`—scientific interpretation and measured values.
- `computations/verify_particle_carrier_direct_coordinate.py`—independent source and terminal-field verifier.
- `computations/particle-carrier-resolution-recovery-prereg.md`—downstream refined-grid question.
