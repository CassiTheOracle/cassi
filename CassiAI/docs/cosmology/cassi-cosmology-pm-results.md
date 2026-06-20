# Cassi Cosmological Particle-Mesh Simulation

## Overview

First cosmological-scale 3D N-body simulation using the particle-mesh (PM)
method in comoving coordinates.

**Parameters**
| Parameter | Value |
|---|---|
| Box size | 200.0 Mpc/h |
| Particles | 256³ = 16,777,216 |
| PM grid | 256³ |
| Ω_m | 0.3 |
| Ω_Λ | 0.7 |
| Initial scale factor | 0.0199 (z=49.25) |
| Final scale factor | 1.0000 (z=0.00) |
| Steps | 100 |
| Power spectrum | P(k) ∝ k^{-2.4} with small-scale cutoff |
| ICs | Zel'dovich approximation |

## Results

At z=0.00:
- RMS overdensity: 1.0887
- Peak P(k): 6.030e+03 (Mpc/h)³
- Mean density check: 0.315511 (target Ω_m = 0.3)

### Performance

- Wall time: 37.9 s for 100 steps
- Per-step time: 379.5 ms
- GPU memory: ~6 GB peak (16.7M particles + 256³ grid + FFT workspace)

### Scaling Notes

On the 24 GB Radeon RX 7900 XTX, this run used roughly 25% of available VRAM.
The practical ceiling with this pure PM code is approximately:

| Limit | Estimate |
|---|---|
| Particles | ~50–100M (512³–640³) |
| PM grid | 512³ (would require ~4× memory) |
| Box size | 500+ Mpc/h |
| Runtime | ~ minutes for 100 steps |

For billion-particle cosmological volumes, a tree-PM or AMR code on a cluster
is required; this single-GPU PM code captures the correct large-scale physics
up to ~100 Mpc/h resolution.

### Key Observations

1. **Structure formation:** Density projections show the emergence of filaments,
   clusters, and voids as the universe evolves.
2. **Power spectrum growth:** P(k) grows with time on all resolved scales,
   with more power at small k (large scales) initially shifting toward smaller
   scales as collapse proceeds.
3. **Mass conservation:** Mean density remains close to Ω_m throughout the run.
4. **Nonlinearity:** δ_rms reaches 1.09 at z=0, indicating mildly nonlinear
   structure formation in this 200 Mpc/h volume.

## Files

- `experiments/cassi_cosmology_pm.py` — Cosmological PM simulation
- `docs/figures/cassi_cosmology_pm_projections.png` — Density projections
- `docs/figures/cassi_cosmology_pm_slices.png` — Density slices
- `docs/figures/cassi_cosmology_pm_power_spectrum.png` — Power spectra
- `docs/cassi-cosmology-pm-results.md` — This document

---

*Generated: 2026-06-10*
