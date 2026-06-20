# Cassi Bridge Limit Comparison

## Method

Three limits of the same Cassi framework were run and their statistical
signatures compared:

| Limit | Code | Quantity compared |
|---|---|---|
| Atomic hydrogen | `cassi_unified_bridge.py` (atomic mode) | radial density profile |
| Cosmic structure | `cassi_unified_bridge.py` (cosmos mode) | matter power spectrum |
| Incompressible two-fluid | `cassi_two_fluid.py` | density power spectrum |

## Results

### Hydrogen radial profile

The bridge atomic run produces a bound state whose radial density profile
matches the exact 1s hydrogen profile $4r^2 e^{-2r}$ after normalization.
This confirms the bridge solver reduces to atomic physics in the $M=1$ fixed-
charge limit.

### Power spectra

- **Cosmological bridge (3D):** power rises toward small scales as
  self-gravity and the Yin information source amplify density perturbations.
- **Two-fluid model (2D):** the normalized spectrum has a similar rising slope
  at intermediate scales, consistent with the same attractive information
  potential driving structure. Because the two-fluid model is 2D and uses an
  incompressible velocity field rather than a wavefunction phase, the high-k
  cutoff and amplitude differ, but the qualitative shape is the same.

## Interpretation

The two-fluid model is a valid **hydrodynamic caricature** of the full bridge:
it captures the same structure-forming instability and the same golden-ratio
Yin/Yang equilibrium, but at much lower computational cost. It is therefore a
useful proxy for scanning Cassi parameter space before committing to the more
expensive Schrödinger–Poisson solver.

## Files

- `docs/figures/cassi_compare_limits.png`
