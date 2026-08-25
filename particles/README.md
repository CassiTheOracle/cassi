# Particles—Conditional Interference and DFT Benchmarks

## Status: Index—August 2026

## Abstract

This directory separates the canonical real-density two-fluid solver from two downstream records. The canonical state uses the real densities $E_Y,E_I\ge 0$, with $\rho=E_Y+E_I$, $\varepsilon=E_Y-\varphi E_I$, the gated coherence $q$, and rank-one conversion. Its equations contain no built-in complex phase, chirality, right/left propagation, compact coordinate, or nonlinear Schrödinger (NLS) sector. `cassi-yang-yin-particles.md` records a **Hypothesized** conditional extension that adds complex counterpropagating fields and NLS self-focusing as a particle-interference model. `dft-benchmarks.md` records conventional LDA/PBE/Dirac-Kohn-Sham reference-energy benchmarks; those measurements validate the numerical implementation and atomic comparisons only. `matter-organization.md` keeps the independent cascade bookkeeping alongside explicit boundaries for the conditional particle extension.

## Document Index

| # | Document | Domain | Epistemic |
|---|----------|--------|-----------|
| 1 | `cassi-yang-yin-particles.md` | Conditional particle-interference extension | Hypothesized |
| 2 | `dft-benchmarks.md` | Conventional computational chemistry benchmark | Calibrated |
| 3 | `matter-organization.md` | Matter organization and cascade bookkeeping | Synthesis |

## Document Summaries

### `cassi-yang-yin-particles.md`—Conditional Yang-Yin Interference Extension

States a conditional complex-field/NLS construction in which Yang and Yin
components carry opposite spatial phase signs in a selected ansatz, form an
interference pattern, and self-focus into soliton-like structures. The
construction adds complex phase, a chosen one-dimensional coordinate,
counterpropagating trial modes, NLS dynamics, and the selected amplitude ratio
$A_I/A_Y=\varphi^{-1}$ beyond the canonical $E_Y,E_I$ density equations. It
supplies no chirality operator; a chiral interpretation remains an optional
additional sector. These statements carry **Hypothesized** status and do not
describe supplied canonical dynamics.

### `matter-organization.md`—Matter Organization: Forces, Lattice Pools, and the Neutron–Proton–Electron Trio

Synthesis (August 2026) of force-channel and cascade bookkeeping, including gravity, GUT, sector, electroweak, and QCD rung assignments; the 38-state mass catalog; lattice node/void bookkeeping; and the proton, neutron, and electron placements. The particle-pooling, standing-wave, wake-phase, propagation, and soliton readings are identified as conditional **Hypothesized** extension content, while independent empirical and mapped cascade results retain their stated tiers.

### `dft-benchmarks.md`—DFT Benchmarks: CassiBridgeV2 Real-Space Performance

Benchmarks conventional real-space LDA/PBE and Dirac-Kohn-Sham implementations against exact atomic reference energies for $Z=1$–$10$. The measured errors, grid-refinement behavior, pseudopotential comparison, and DiracBridge values establish the behavior of those numerical implementations and their atomic reference comparisons. They do not establish the canonical two-fluid equations or the particle-emergence hypothesis.

## Cross-References

- `foundations/cassi-first-principles.md`—canonical two-fluid densities, Qi coherence, and gated rank-one conversion
- `foundations/dimensionful-cascade.md`—the cascade ladder used for scale bookkeeping
- `foundations/cascade-suppression-formula.md`—the coherence budget used in stability bookkeeping
- `predictions/falsifiable-predictions.md`—the prediction catalog and its epistemic boundaries
