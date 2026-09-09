# Turbulence—Spectra and Navier–Stokes Geometry

## Status: Index—September 2026

## Abstract

This directory contains the framework's turbulence sector: a conditional
two-fluid spectral analysis that separates the inherited Navier–Stokes
$-5/3$ kinetic-energy spectrum from optional Cassi closures. The source
$E_\varepsilon(k)$, scale-dependent gravity factor, and Qi-quality spectrum
$q(k)$ are conditional diagnostics; their optional closure forms are
Hypothesized, and each test must state its assumptions and retain its receipt.
The directory therefore records which ingredients are inherited, which are
optional model choices, and which claims remain unestablished.

The Navier–Stokes analyses develop exact critical-norm transfer identities,
heat-correction estimates, and filtered stress dynamics. Their explicit
initial-data controls delimit scalar-energy and local-geometric closure
arguments. Arbitrary-data regularity and a Cassi current-to-momentum
constitutive map remain open.

## 1. Document index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `turbulence/kolmogorov-from-phi.md` | Turbulence spectra from the two-fluid PDE | Derived conditional / Hypothesized closures |
| 2 | `turbulence/navier-stokes-transfer-boundary.md` | Critical transfer, cubic heat correction, and coercivity | Derived identities and obstructions / conditional small-data estimates |
| 3 | `turbulence/navier-stokes-stress-geometry.md` | Exact stress evolution and helical covariance conditions | Derived filtered identities / Hypothesized geometric closure |
| 4 | `turbulence/navier-stokes-depletion-dynamics.md` | Exact fine-scale transfer response, matter binding and exterior-memory comparison | Derived filtered identities and instantaneous obstructions / Conditional continuation estimate |

## 2. Document summaries

### 2.1 Conditional Kolmogorov spectrum

The source document separates the inherited incompressible Navier–Stokes
kinetic-energy spectrum from the optional $q$-gated turbulence closure. Its
$k_\varphi$, $E_\varepsilon(k)$, gravity-factor, and $q(k)$ expressions are
conditional diagnostics: their rates, regimes, slopes, and amplitudes depend
on declared gate, flux, shell-averaging, and gravity-coupling assumptions.

### 2.2 Critical transfer and coercivity

`turbulence/navier-stokes-transfer-boundary.md` derives the signed all-scale
budget and a cubic heat correction. A phase-tuned family has unbounded
positive critical norm on one corrected-energy level set. The quartic
remainder has both signs; standard estimates close the small-data regime.

### 2.3 Filtered stress geometry

`turbulence/navier-stokes-stress-geometry.md` retains pressure correlations,
third moments, and viscous terms in the exact stress and strain equations.
It states the assumptions behind a helical covariance model and an
all-scale anisotropy estimate, with fixed controls for local isotropy,
helix deformation, surrounding strain, and scale dependence.

### 2.4 Fine-scale transfer and matter binding

`turbulence/navier-stokes-depletion-dynamics.md` isolates a kinetic-energy-controlled
coarse contribution while retaining full stress in the fine contribution.
The averaged fine transfer can increase from zero, and a fixed multiscale
control exceeds viscous-only absorption. A data-controlled cumulative
estimate remains open. The matter comparison distinguishes qualified
loaded-core redistribution from the positive constrained energy that
establishes conditional unwound binding.
The exterior-memory comparison retains the initial exterior state and the
operator assumptions needed for a controlled response; the corresponding
nonlinear Navier–Stokes estimate remains unproved.

## References

- `foundations/xi-derivation.md`—first-principles derivation of the Qi-gravity coupling $\xi = \varphi^6$ used in the velocity equation
- `foundations/bubble-edge-geometry.md` §1.2—condensation-vs-diffusion balance used as a conditional analogy
- `cassi-physics.md`—the two-fluid PDE as written in the core physics document
- `predictions/falsifiable-predictions.md`—registered prediction catalog; the break-scale test remains prospective unless explicitly registered
- `computations/navier_stokes_stress_geometry_prereg.md`—fixed fixtures, numerical tolerances, and decision rules
- `computations/verify_navier_stokes_transfer.py`—exact finite-Fourier transfer verification
- `computations/verify_navier_stokes_stress_geometry.py`—symbolic geometry checks and independent Fourier quadrature
- `computations/navier-stokes-depletion-prereg.md`—fixed instantaneous-response and absorption controls
- `computations/verify_navier_stokes_depletion.py`—exact fine-transfer algebra and independent FFT/quadrature reconstruction
- `field-experience/probe-outcome-ledger.md`—measured classifications and evidence paths
