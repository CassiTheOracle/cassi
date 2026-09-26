# Field-Particle Catalog Recovery Result

## Status: FAIL—September 2, 2026

## 1. Registered run

The first execution after freezing
`field_particle_catalog_recovery_prereg.md` did not enter the focused contract.
Godot rejected three inferred local declarations in the new two-Gaussian
control at parse time (`cell`, `base`, and `direct_charge`). The empty scene
remained open until it was stopped after 263 seconds, so this run also exceeded
the 240-second arm limit.

No catalog, dynamics, or independent-verifier measurement was produced by this
execution. The earlier identity-recovery measurements remain separate and are
not reused as this run's result.

## 2. Verdict

**FAIL—FIELD-PARTICLE CATALOG RECOVERY.**

The failure is in the verification arm's static typing, before runtime setup.
A registered syntax-only recovery adds explicit `int` and `float` annotations.
The catalog algorithm, synthetic control values, field equations, thresholds,
and decision rule remain unchanged.
