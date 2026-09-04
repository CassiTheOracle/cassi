# Field-Particle Zero-Time Identity Recovery Result

## Status: PASS—September 2, 2026

## 1. Registered run

The first execution after freezing
`field_particle_identity_recovery_prereg.md` added only the registered
zero-time canonical-copy branch. The nonzero-time RK4 equations, five-point
Hamiltonian derivative, unit experimental temporal coefficients, seed,
controls, and thresholds were unchanged.

The windowed Godot arm completed with exit code 0. The zero-time dispatch
changed zero bytes, and the independent verifier accepted the requested state
as byte-identical to the pinned seed.

## 2. Measured controls

| Quantity | Registered limit | Measured |
|---|---:|---:|
| Zero-time state difference | 0 bytes | 0 bytes |
| Charge drift | `2e-3` | `4.8971096e-7` |
| Carrier-density RMS drift | `2e-3` | `8.3092300e-7` |
| Charged-field RMS drift | `5e-3` | `1.7767397e-8` |
| PA12 energy drift | `5e-3` | `2.0455729e-8` |
| Final outer carrier fraction | `2e-4` | `1.0708168e-4` |
| Carrier phase rate | within 20% of `omega_C` | `0.0034170290` |
| Final Gauss RMS | `2e-3` | `7.7171872e-7` |
| Vacuum maximum residual | `2e-6` | `8.4936613e-11` |
| Boost displacement | positive | `0.0374414470` |
| Boost retained charge | at least `0.99` | `0.9999999596` |

The independent NumPy reconstruction passed source/runtime identity, charge,
center, localization, physical energy (`1.525187855385`), and all twelve
selected Hamiltonian-gradient comparisons. The stationary GPU evolution took
749 ms and the boost evolution took 479 ms; the complete arm, including CPU
reconstruction, completed in 24.0 s.

## 3. Verdict

**PASS—FIELD-PARTICLE IDENTITY RECOVERY.**

The pinned localized carrier now has an exact import path, a complete PA12
Hamiltonian derivative, coupled RK4 field evolution, bounded stationary and
vacuum controls, directed boosted motion, and exact zero-time identity. The
unit temporal coefficients remain an experimental runtime normalization and do
not select PA43.
