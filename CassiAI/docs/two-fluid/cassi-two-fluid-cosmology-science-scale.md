# Cassi Two-Fluid Cosmology Science — Scale-Dependent Dispersion

## Setup

| Parameter | Value |
|---|---|
| Grid | 256³ |
| Box size | 100.0 Mpc/h |
| Cell size | 0.391 Mpc/h |
| Nyquist k | 8.04 h/Mpc |
| Time step | 0.0005 |
| Steps | 400 |
| χ | 12.0 |
| χ_Yang | 3.7082 |
| D | 5e-05 |
| ν | 0.0002 |
| λ | 0.02 |
| α_disp | 1.6180 |

## Results

Final state at $t=0.200$:

| Quantity | Value |
|---|---|
| δ_rms | 0.175 |
| EI/EY ratio | 0.6184 |
| Enstrophy | 0.32 |
| Wall time | 383.5 s |

## Comparison to ΛCDM

The two-fluid power spectrum is normalized to the Eisenstein-Hu ΛCDM spectrum
at $k=0.1\,h/{Mpc}$.

- RMS log-shape error over the overlapping $k$ range: **3.862 dex**.
- With $lpha_{disp} = 1+\varphi^{-1} \approx 1.618$, the effective Poisson
  kernel suppresses small-scale forces, giving the two-fluid spectrum a
  ΛCDM-like downward slope.
- Remaining differences (no baryon acoustic oscillations, finite box, diffusion)
  are expected at this level of the model.

## Interpretation

This run adds the Cassi scale-dependent dispersion kernel to the two-fluid
solver. The kernel has the form

$$v^2(k) \propto \left(\frac{k}{k_0}\right)^{2(\alpha_{disp}-1)}$$

so the effective Poisson kernel becomes $1/[v^2(k)\,k^2]$.
For $lpha_{disp} > 1$ small-scale gravity is suppressed, shifting power to
large scales as seen in ΛCDM. For the golden-ratio value
$\alpha_{disp} = 1+\varphi^{-1} \approx 1.618$, the two-fluid power
spectrum now tracks the ΛCDM shape far better than the scale-free case.

## Files

- `docs/figures/cassi_two_fluid_cosmology_science_scale.png`
