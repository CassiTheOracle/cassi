# Cassi Two-Fluid Cosmology: φ-Equilibrium Approach

Grid: 128³, box: 100.0 Mpc/h, steps: 400, dt: 0.0005, H0=0.5, a0=1.0

## Setup

| Parameter | Value |
|---|---|
| χ | 6.0 |
| χ_Yang | 1.8541 |
| D | 5e-05 |
| ν | 0.0002 |
| λ | 0.02 |
| H0 | 0.5 |
| a0 | 1.0 |

## Initial Yin/Yang ratios tested

| Initial EI/EY | Initial EY mean | Initial EI mean | Final EI/EY | Final a |
|---|---:|---:|---:|---:|
| 0.3000 | 1.2446 | 0.3734 | 0.3027 | 1.105 |
| 0.5000 | 1.0787 | 0.5393 | 0.5011 | 1.105 |
| 0.6180 | 1.0000 | 0.6180 | 0.6180 | 1.105 |
| 1.0000 | 0.8090 | 0.8090 | 0.9951 | 1.105 |
| 1.6180 | 0.6180 | 1.0000 | 1.6013 | 1.105 |

## Interpretation

The conversion term pushes every initial Yin/Yang ratio in the direction of the golden-ratio equilibrium EI/EY = φ⁻¹ ≈ 0.6180. With λ = 0.02 the approach is slow over t = 0.2, but the sign is correct: ratios below equilibrium rise slightly, and ratios above it fall slightly. Because the Hubble parameter in this implementation is set by the total comoving energy density, expansion continues as de Sitter-like regardless of the ratio, while the φ-equilibrium controls the relative abundance of dark-energy-like Yang and matter-like Yin. A larger λ or longer runtime would accelerate convergence to φ⁻¹.

## Files

- `docs/figures/cassi_two_fluid_cosmology_phi_equilibrium.png`
