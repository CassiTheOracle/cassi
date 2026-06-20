# Cassi Two-Fluid Cosmology Science

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

## Results

Final state at $t=0.200$:

| Quantity | Value |
|---|---|
| δ_rms | 0.275 |
| EI/EY ratio | 0.6184 |
| Enstrophy | 0.32 |
| Wall time | 383.1 s |

## Comparison to ΛCDM

The two-fluid power spectrum is normalized to the Eisenstein-Hu ΛCDM spectrum
at $k=0.1\,h/{Mpc}$.

- RMS log-shape error over the overlapping $k$ range: **3.596 dex**.
- The two-fluid spectrum grows with time but has a much flatter shape than
  ΛCDM, which declines toward small scales.
- At small scales ($k\gtrsim 1\,h/{Mpc}$) the two-fluid power is suppressed
  by diffusion/viscosity; at large scales it grows almost uniformly because the
  chemotactic drift is scale-free.

## Interpretation

This is a **proof-of-concept** that the Cassi two-fluid equations can produce a
gravitational collapse signal and a well-defined matter power spectrum in a
physical 100 Mpc/h box. Achieving a ΛCDM-like slope will require a
scale-dependent response — for example, the Cassi scale-dependent dispersion
kernel $v^2(k) \propto (k/k_0)^{2(\alpha_{disp}-1)}$ with
$\alpha_{disp} = 1 - \varphi^{-1} \approx 0.382$, which enhances large-scale
power in the bridge cosmology.

## Files

- `docs/figures/cassi_two_fluid_cosmology_science.png`
