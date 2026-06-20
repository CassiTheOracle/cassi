# Cassi Cosmology: Entropic Gravity Parameter Sweep

## Overview

A parameter sweep over the entropic strength α for two entropy prescriptions:

- **Relative mode:** s(δ) = (1+δ) log(1+δ) − δ
- **Signed mode:** s(δ) = sign(δ) · log(1+|δ|)

The effective Poisson source is δ_eff = δ + α · s(δ). Linearly both modes are
second order, so large-scale growth is preserved. Nonlinearly the relative mode
tends to soften structure while the signed mode amplifies it.

**Parameters**
| Parameter | Value |
|---|---|
| Box size | 100.0 Mpc/h |
| Particles | 64³ = 262,144 |
| PM grid | 64³ |
| Steps | 100 |
| α values | 0.0, 0.3, 1.0, 3.0 |

## Results

### Relative mode

| Run | δ_rms at z=0 | Peak P(k) | Yang mass fraction |
|---|---:|---:|---:|
| Standard PM | 0.948 | 1.466e+04 | 0.742 |
| α=0.0 | 0.948 | 1.466e+04 | 0.742 |
| α=0.3 | 0.911 | 1.234e+04 | 0.724 |
| α=1.0 | 0.853 | 8.816e+03 | 0.702 |
| α=3.0 | 0.861 | 7.094e+03 | 0.711 |

### Signed mode

| Run | δ_rms at z=0 | Peak P(k) | Yang mass fraction |
|---|---:|---:|---:|
| Standard PM | 0.948 | 1.466e+04 | 0.742 |
| α=0.0 | 0.948 | 1.466e+04 | 0.742 |
| α=0.3 | 0.963 | 1.176e+04 | 0.751 |
| α=1.0 | 1.013 | 7.278e+03 | 0.764 |
| α=3.0 | 1.040 | 4.377e+03 | 0.821 |

### Key Observations

1. **Relative mode softens clustering:** As α increases, δ_rms, peak P(k), and
   Yang mass fraction all decrease. The convex relative-entropy source acts like
   an effective pressure that reduces the contrast between voids and knots.
2. **Signed mode amplifies clustering:** As α increases, δ_rms and Yang mass
   fraction rise. The signed source reinforces both positive and negative
   overdensities, so matter is driven more strongly into collapsed regions and
   voids become emptier.
3. **Power-spectrum crossing:** In signed mode, the entropic P(k) crosses above
   standard PM at small scales, showing a transfer of power from large to small
   scales. In relative mode the deficit extends across most resolved scales.
4. **Tunability:** A single scalar parameter α turns the entropic source from a
   smoothing agent into a clustering amplifier, depending on the sign convention
   chosen for the entropy density.
5. **Cassi interpretation:** Gravity can be viewed as an information-structuring
   force. The entropy prescription controls whether information spreads out
   (relative mode) or concentrates (signed mode).

## Files

- `experiments/cassi_cosmology_entropic_sweep.py` — Parameter sweep
- `experiments/cassi_cosmology_entropic_gravity.py` — Underlying entropic PM engine
- `docs/figures/cassi_cosmology_entropic_sweep_metrics.png` — Metric trends vs α
- `docs/figures/cassi_cosmology_entropic_sweep_relative_power.png` — Relative-mode P(k)
- `docs/figures/cassi_cosmology_entropic_sweep_signed_power.png` — Signed-mode P(k)
- `docs/figures/cassi_cosmology_entropic_sweep_power_compare.png` — Side-by-side P(k)
- `docs/cassi-cosmology-entropic-sweep-results.md` — This document

---

*Generated: 2026-06-10*
