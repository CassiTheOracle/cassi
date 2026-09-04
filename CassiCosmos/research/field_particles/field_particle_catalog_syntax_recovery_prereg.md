# Field-Particle Catalog Syntax Recovery Preregistration

## Status: Frozen—September 2, 2026

## 1. Change

Add explicit `int` types to the two-Gaussian control's flattened cell and state
base indices, and an explicit `float` type to its direct integrated charge.
No executable expression, catalog algorithm, field equation, control value,
threshold, or acceptance rule changes.

## 2. Registered run and decision

Run `res://scenes/verify_field_particles.tscn` windowed from a clean supervised
process. `PASS—FIELD-PARTICLE CATALOG SYNTAX RECOVERY` requires the scene to
parse, exit within 240 seconds, pass every catalog check frozen in
`field_particle_catalog_recovery_prereg.md`, pass all prior FP0–FP9 checks, and
pass the independent NumPy verifier. Any failure gives
`FAIL—FIELD-PARTICLE CATALOG SYNTAX RECOVERY` and is recorded before further
implementation changes.
