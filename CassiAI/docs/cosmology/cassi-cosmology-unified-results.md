# Cassi Cosmology: Unified Simulation Results

## Overview

All four extensions of the unified Cassi cosmology Lagrangian were run with the
same engine:

$$
S[\delta] = \frac{3}{2}\Omega_m \Big[ \delta + \alpha_\text{yin} \cdot s(\delta) \Big]
$$

with an effective Yang/dark-energy modulation

$$
S[\delta] \to S[\delta] \cdot \left[ 1 + \frac{\Lambda_\varphi}{2}
\left(1 + \sin\!\left(\frac{2\pi a}{a_\varphi}\right)\right) \right]
$$

and a scale-dependent dispersion kernel

$$
\hat{\psi}_k = - \frac{\hat{S}_k}{v_0^2 \left(\frac{k}{k_0}\right)^{2(\alpha_\text{disp}-1)} k^2}
$$

| Parameter | Value |
|---|---|
| Box size | 100.0 Mpc/h |
| Particles | 64³ = 262,144 |
| PM grid | 64³ |
| Steps | 100 |

## Results at z = 0

| Mode | δ_rms | Peak P(k) | Yang mass fraction |
|---|---:|---:|---:|
| Combined: $\alpha_\text{disp}=1-1/\varphi$, relative Yin $\alpha=1.0$ | 1.492 | 2.860e+03 | 0.853 |
| Dark Energy / Yang: $\Lambda_\varphi=1.0$, $a_\varphi=\varphi^{-1}$ | 0.966 | 7.965e+03 | 0.740 |
| Holographic Bound: $\eta=0.004$, $\beta=1.0$ | 0.938 | 1.572e+04 | 0.734 |

## Modes

1. **Standard PM** — baseline α_disp = 1, no Yin, no Yang, no holographic bound.
2. **Combined** — α_disp = 1 - 1/φ together with relative Yin α_yin = 1.0.
   Scale-dependent gravity (enhanced small-scale coupling) competes with
   entropic information pressure that softens collapsed cores.
3. **Dark Energy / Yang** — Yang oscillation with Λ_φ = 1.0 and
   a_φ = φ^{-1} ≈ 0.618, modulating the effective gravitational strength.
4. **Holographic Bound** — Gaussian smoothing triggered when field information
   exceeds η · grid_pm^{2/3} with η = 0.004.

## Key Observations

- The **combined** mode shows how two Cassi mechanisms compete: enhanced
  small-scale gravity drives more clustering, while relative Yin entropy
  softens the cores; the net result is a more extreme cosmic web.
- The **Yang oscillation** modulates the effective source strength at a φ-set
  period, leaving large-scale growth mostly intact but changing the timing of
  collapse.
- The **holographic bound** smooths the density field once its information
  content exceeds the area-scaled bound, producing a small-scale suppression
  that strengthens as structure forms.
- All effects are derived from a single Lagrangian (see
  `docs/cassi-cosmology-unified-lagrangian.md`).

## Files

- `experiments/cassi_cosmology_unified.py` — Unified simulation engine
- `docs/cassi-cosmology-unified-lagrangian.md` — Derivation of the master action
- `docs/cassi-cosmology-unified-combined-results.md`
- `docs/cassi-cosmology-unified-dark_energy-results.md`
- `docs/cassi-cosmology-unified-holographic-results.md`
- `docs/figures/cassi_cosmology_unified_*.png`

---

*Generated: 2026-06-10*
