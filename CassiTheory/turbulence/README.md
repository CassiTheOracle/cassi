# Turbulence—Conditional Kolmogorov Spectrum Analysis

## Status: Index—August 2026

## Abstract

This directory contains the framework's turbulence sector: a conditional
two-fluid spectral analysis that separates the inherited Navier–Stokes
$-5/3$ kinetic-energy spectrum from optional Cassi closures. The source
$E_\varepsilon(k)$, scale-dependent gravity factor, and Qi-quality spectrum
$q(k)$ are conditional diagnostics; their optional closure forms are
Hypothesized, and each test must state its assumptions and retain its receipt.
The directory therefore records which ingredients are inherited, which are
optional model choices, and which claims remain unestablished.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `kolmogorov-from-phi.md` | Turbulence spectra from the two-fluid PDE | Derived conditional / Hypothesized closures |

## Document Summaries

### `kolmogorov-from-phi.md`—The Kolmogorov −5/3 Spectrum in Cassi: Derivation and Conditional Tests

The source document separates the inherited incompressible Navier–Stokes
kinetic-energy spectrum from the optional $q$-gated turbulence closure. Its
$k_\varphi$, $E_\varepsilon(k)$, gravity-factor, and $q(k)$ expressions are
conditional diagnostics: their rates, regimes, slopes, and amplitudes depend
on declared gate, flux, shell-averaging, and gravity-coupling assumptions.

## Cross-References

- `foundations/xi-derivation.md`—first-principles derivation of the Qi-gravity coupling $\xi = \varphi^6$ used in the velocity equation
- `foundations/bubble-edge-geometry.md` §1.2—condensation-vs-diffusion balance used as a conditional analogy
- `cassi-physics.md`—the two-fluid PDE as written in the core physics document
- `predictions/falsifiable-predictions.md`—registered prediction catalog; the break-scale test remains prospective unless explicitly registered
