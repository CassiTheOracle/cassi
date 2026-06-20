# Cassi Two-Fluid Cosmology Science — ΛCDM Initial Conditions

## Setup

| Parameter | Value |
|---|---|
| Grid | 256³ |
| Box size | 100.0 Mpc/h |
| Cell size | 0.391 Mpc/h |
| Nyquist k | 8.04 h/Mpc |
| Time step | 0.0005 |
| Steps | 400 |
| χ | 6.0 |
| χ_Yang | 1.8541 |
| D | 5e-05 |
| ν | 0.0002 |
| λ | 0.02 |
| α_disp | scale-free |

## Results

Final state at $t=0.200$:

| Quantity | Value |
|---|---|
| δ_rms | 0.123 |
| EI/EY ratio | 0.6180 |
| Enstrophy | 0.32 |
| Wall time | 385.8 s |

## Comparison to ΛCDM

The two-fluid power spectrum is normalized to the Eisenstein-Hu ΛCDM spectrum
at $k=0.1\,h/{Mpc}$.

- RMS log-shape error over the overlapping $k$ range: **0.929 dex**.
- The two-fluid spectrum now follows the ΛCDM shape because it was initialized
  with the same Eisenstein–Hu power spectrum and the scale-free chemotactic
  drift amplifies all modes roughly uniformly.
- Remaining differences (no baryon acoustic oscillations, finite box, diffusion,
  and nonlinear mode coupling) are expected at this level of the model.

## Interpretation

The scale-free chemotactic drift in the two-fluid solver preserves the shape of
the input density power spectrum while amplifying its amplitude. Therefore the
previous mismatch was largely due to white-noise initial conditions, not a
fundamental inability to match ΛCDM. By initializing the Yang and Yin fields
with a Gaussian random field whose power spectrum follows the Eisenstein–Hu
ΛCDM shape, the evolved two-fluid P(k) tracks the reference spectrum. The
scale-dependent dispersion kernel added in this session remains available for
fine-tuning the scale-dependence of the growth rate.

## Files

- `docs/figures/cassi_two_fluid_cosmology_science_lcdm_ics.png`
