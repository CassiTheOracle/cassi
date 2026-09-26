# Field-Particle Runtime Verification Summary

## Status: PASS—September 2, 2026

## 1. Standalone field contract

The post-integration windowed run of
`res://scenes/verify_field_particles.tscn` completed 55 checks with zero
failures and exited 0 in 22.5 seconds. It retained:

- exact pinned source import and zero-time byte identity;
- complete PA12 spatial Hamiltonian and selected five-point derivative checks;
- bounded 64-step stationary RK4 evolution;
- exact and numerically evolved vacuum controls;
- directed boosted motion with charge retention;
- deterministic one-object and two-object observational catalogs;
- zero legacy deposit, KDK, accretion, and merge calls;
- independent NumPy reconstruction of energy and twelve gradient samples.

## 2. Production integration contract

The windowed `res://scenes/verify_field_particle_integration.tscn` run passed
PI0–PI9 and exited 0 in 15.3 seconds. It verified the real shared-RD `CassiSim`
path, sole field-authoritative stepping, publish-boundary proxy reconstruction,
complete canonical snapshots, explicit unmapped gravity, visible rendering, and
clean shutdown. Detailed measurements are in
`research/field_particles/field_particle_integration_report.md`.

## 3. Default-off regression contract

The unchanged full runner was launched headless; every child arm remained
windowed and serial. It completed in 283 seconds with:

```text
[Battery] 40/40 PASS (total 283 s)
[Battery] runner exiting (exit code 0)
```

This is the current repository battery size. The result covers the default
site-native universe, raster and meshless gravity, merge and accretion,
rendering and UI, mind/field intelligence, snapshots, tree refit, rotation,
and the pinned river-isotropy anchors. No existing arm was added, removed, or
weakened for the field-particle mode.

## 4. Result boundary

**PASS—FIELD-PARTICLE RUNTIME VERIFICATION.**

This establishes a working default-off field-authoritative runtime and a clean
legacy regression. It does not select PA43 temporal coefficients or identify a
carrier's physical mass, spin, spectrum, lifetime, or gravitational coupling.
Those remain theory and measurement problems rather than runtime defaults.
