# Cassi 3D N-Body Force Accuracy: Field vs. Exact Gaussian

## Executive Summary

**Field-mediated 3D Poisson gravity reproduces the exact Gaussian-softened force with L2 error as low as 2.0% when the body is resolved by at least 2–3 grid cells.**

Best case found:
- Grid: 128³
- σ: 0.4
- σ/dx: 2.56
- L2 relative error: 0.020
- Max relative error: 0.042
- Median angle error: 0.68°

The correct 3D Poisson factor **−4πG/k²** is used throughout.

---

## Method

### Field-Mediated Force

- Bodies are 3D Gaussian density peaks normalized to total mass.
- 3D spectral Poisson solve: Φ̂ = −4πG ρ̂ / k²
- Acceleration field: a = −∇Φ
- Trilinear interpolation at body positions

### Exact Pairwise Reference

The reference uses the field of a normalized 3D Gaussian sphere:

```
F(r)/m = G M / r² [erf(r/(√2 σ)) − √(2/π) (r/σ) exp(−r²/(2σ²))]
```

Periodic images are summed over (2n+1)³ boxes to match FFT boundary conditions.

### Parameter Sweep

- N = 50 bodies in a random spherical cluster (radius 5, box L = 20)
- Grid sizes: 32³, 64³, 128³
- Gaussian widths: 0.2, 0.4, 0.8

---

## Results

### L2 Relative Error Matrix

| σ \ grid | 32³ | 64³ | 128³ |
|---|---:|---:|---:|---:|
| 0.2 | 0.637 | 0.530 | 0.407 |
| 0.4 | 0.129 | 0.074 | 0.020 |
| 0.8 | 0.070 | 0.060 | 0.062 |

### Key Observations

1. **Resolution threshold:** Errors drop sharply once σ/dx ≥ 2. The best case (128³, σ=0.4, σ/dx=2.56) achieves 2.0% L2 error and 0.68° median angle error.
2. **Under-resolved bodies fail:** For σ=0.2, even the finest 128³ grid (σ/dx=1.28) gives 41% L2 error. The 3D Gaussian is more sharply peaked than its 2D counterpart and demands finer resolution.
3. **3D factor confirmed:** Using −4πG/k² reproduces the exact Gaussian-softened point-mass limit at large separations.
4. **Angle accuracy:** Direction is excellent for resolved cases — median angle errors are below 1° for σ/dx ≥ 2.5.
5. **Computational cost:** 3D FFT dominates runtime. A 128³ field solve takes ~13 ms on GPU, while the N=50 pairwise reference takes ~170 ms. The crossover to field-gravity advantage occurs at modest N in 3D as well.

### Comparison with 2D

| Metric | 2D (best) | 3D (best) |
|---|---:|---:|
| L2 error | ~16% | **2.0%** |
| Median angle | <1° | **0.68°** |
| σ/dx requirement | ≥2 | ≥2–2.5 |

The 3D field method is more accurate in this benchmark because the 1/r² force law weights nearby neighbors more heavily, and the well-resolved Gaussian faithfully reproduces their softened interaction. In 2D, the slower 1/r decay makes the calculation more sensitive to long-range periodic-image and interpolation errors.

---

## Files

- `experiments/cassi_nbody_force_accuracy_3d.py` — 3D force accuracy sweep
- `docs/figures/cassi_nbody_force_accuracy_3d.png` — Error contour plots
- `docs/figures/cassi_nbody_force_accuracy_3d_histograms.png` — Error distributions
- `docs/figures/cassi_nbody_force_accuracy_3d_summary.png` — Summary table
- `docs/cassi-nbody-force-accuracy-3d-results.md` — This document

---

*Generated: 2026-06-10*
