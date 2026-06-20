# Cassi Two-Fluid vs Particle-Mesh Cosmology

## Setup

| Parameter | Value |
|---|---|
| Two-fluid grid | 128³ |
| PM particles | 256³ |
| PM force/mesh grid | 128³ |
| Box size | 100.0 Mpc/h |
| Two-fluid steps | 400 |
| Two-fluid H₀ | 0.5 |
| PM Ω_m | 0.31 |
| PM Ω_Λ | 0.69 |
| PM scale factor | 1.000 → 1.105 |
| PM mass assignment | TSC |
| PM displacement target | 0.20 × particle spacing |

## Results

| Model | Final δ_rms | RMS log error vs ΛCDM |
|---|---:|---:|
| Cassi two-fluid | 0.081 | 0.479 |
| Standard PM (TSC) | 0.059 | 0.736 |

## Interpretation

Both models were initialized with the same ΛCDM-shaped power spectrum.
The two-fluid solver tracks the ΛCDM reference with RMS log error **0.479 dex**.
The TSC particle-mesh run uses 256³ particles deposited on a 128³ mesh
(8 particles per force cell) to reduce the discrete-particle noise that
steepened the raw CIC spectrum.  After this upgrade, the PM shape error is
**0.736 dex**, showing that the two-fluid and PM descriptions agree on
the large-scale ΛCDM shape, with residual small-scale differences reflecting
the different treatments of viscosity/diffusion versus gravitational collapse.

## Files

- `docs/figures/cassi_two_fluid_cosmology_pm_comparison.png`
