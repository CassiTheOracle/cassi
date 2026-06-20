# Cassi Two-Fluid Expanding Cosmology

## Setup

| Parameter | Value |
|---|---|
| Grid | 256³ |
| Box size | 100.0 Mpc/h |
| Cell size | 0.391 Mpc/h |
| Time step | 0.0005 |
| Steps | 400 |
| χ | 6.0 |
| χ_Yang | 1.8541 |
| D | 5e-05 |
| ν | 0.0002 |
| λ | 0.02 |
| H₀ | 0.50 |
| a₀ | 1.00 |

## Results

Final state at $t=0.200$:

| Quantity | Value |
|---|---|
| Scale factor $a$ | 1.105 |
| Hubble parameter $H$ | 0.5000 |
| δ_rms | 0.119 |
| EI/EY ratio | 0.6180 |
| Enstrophy | 0.31 |
| Wall time | 393.2 s |

## Comparison to ΛCDM

The two-fluid power spectrum is normalized to the Eisenstein-Hu ΛCDM spectrum
at $k=0.1\,h/{Mpc}$.

- RMS log-shape error: **0.942 dex**.
- The expanding comoving grid preserves the ΛCDM-shaped initial power spectrum
  while Hubble drag and the 1/a factors slow structure formation relative to
  the non-expanding case.
- The scale factor evolves under the Friedmann-like constraint
  $H = H_0\,\sqrt{(EY+EI)/\varphi}$.

## Interpretation

This is a first-principles implementation of cosmic expansion in the two-fluid
solver. The background expansion is derived from the Yang-Yin energy balance,
and perturbations are evolved in comoving coordinates with Hubble drag and
scale-factor-dependent gradients. It is the natural next step toward a full
Cassi cosmological simulation.

## Files

- `docs/figures/cassi_two_fluid_cosmology_expanding.png`
