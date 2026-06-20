# Cassi Two-Fluid Cosmology: H₀ Sweep

Grid: 128³, box: 100.0 Mpc/h, steps: 400, dt: 0.0005

## Setup

| H₀ | χ | χ_Yang | D | ν | λ | a₀ |
|---|---|---|---|---|---|---|---|
| 0.00 | 6.0 | 1.8541 | 5e-05 | 0.0002 | 0.02 | 1.0 |
| 0.25 | 6.0 | 1.8541 | 5e-05 | 0.0002 | 0.02 | 1.0 |
| 0.50 | 6.0 | 1.8541 | 5e-05 | 0.0002 | 0.02 | 1.0 |
| 1.00 | 6.0 | 1.8541 | 5e-05 | 0.0002 | 0.02 | 1.0 |
| 2.00 | 6.0 | 1.8541 | 5e-05 | 0.0002 | 0.02 | 1.0 |

## Results

| H₀ | Final a | Final δ_rms | Final enstrophy | RMS log error vs ΛCDM |
|---|---:|---:|---:|---:|
| 0.00 | 1.000 | 0.124 | 0.079 | 0.467 |
| 0.25 | 1.051 | 0.122 | 0.078 | 0.471 |
| 0.50 | 1.105 | 0.121 | 0.077 | 0.475 |
| 1.00 | 1.221 | 0.117 | 0.075 | 0.485 |
| 2.00 | 1.492 | 0.113 | 0.072 | 0.503 |

## Interpretation

Higher H₀ increases the Hubble drag and weakens comoving gradients, slowing structure formation. The shape fidelity to ΛCDM is largely preserved because the scale-free drift does not alter the shape of the input power spectrum.

## Files

- `docs/figures/cassi_two_fluid_cosmology_h0_sweep.png`
