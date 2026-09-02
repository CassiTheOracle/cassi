# Higher-order local/FMM tree-control preregistration

Date frozen: 2026-08-31
Status: frozen before the corrected-control implementation or run
Predecessor: `research/meshless/gravity_fmm_local_prereg.md`

## 1. Why a second registered run is required

The first G73 run is frozen at
`_diag/gravity_fmm_local_result.json`, SHA-256
`7db051faeab1985e990662b89308ab80b7502cdfcf21d388cc8b6257a3b4515f`, with
verdict `INCONCLUSIVE`.

Its all-source direct control compared a leaf-level monopole pair sum with the
GPU Barnes-Hut result. That is not an identity for this force law: accepted
internal nodes use aggregate `W^(2/3)` density-aware softening and quadrupoles,
whereas the pair sum uses each source's `w^(2/3)` and no accepted-node
quadrupole. The observed control mismatch therefore does not diagnose the
source gather or the registered local reconstruction.

G73 remains immutable and inconclusive. This document registers one corrected
control before a second run.

## 2. Frozen input and reconstruction

Use the same input receipt and SHA-256 fixed by G73.

The reconstruction is unchanged:

- exact build-mode-7 source weights;
- owner by nearest site;
- 256 nearest sources evaluated directly;
- 48 nearest site-gradient fit samples;
- coordinates scaled by the first excluded-source distance;
- Cartesian harmonic potential expansions at orders 1 through 5;
- no tuning from G73;
- all G73 fidelity, geometry, rank, and conditioning thresholds unchanged.

The primary candidate remains order 5. Its work proxy remains 291 source or
expansion terms per target.

## 3. Corrected tree control

Use the existing `stage5_fmm.BHOctree` with the receipt's `leaf_cap`, `eps2`,
`max_levels`, and `theta`, and with `density_aware=True`. Evaluate the same 32
integer-rounded, linearly spaced particle indices used by G73 with
`quad=True`.

The prototype does not reproduce the production shader's traversal-order force
cap. The control therefore detects any material activation of that cap in this
receipt; a mismatch is not waived.

The corrected tree control passes only when:

- every compared value is finite;
- median relative vector error is at most `0.01`;
- opposite-direction fraction is exactly `0`.

The p99 relative error is recorded but not gated, matching the existing G30
control convention.

## 4. G74 interpretation and stopping rule

Run the corrected experiment exactly once and write
`_diag/gravity_fmm_local_result_v2.json`.

- `SUPPORTS HIGHER-ORDER` only if all controls are valid, order 5 passes every
  frozen fidelity gate, order 1 fails at least one gate, and order 5 median and
  p99 errors are each at most 80% of order 1.
- `LOW-ORDER SUFFICIENT` if all controls are valid and order 1 passes every
  frozen fidelity gate.
- `DOES NOT SUPPORT` if all controls are valid but order 5 fails any frozen
  fidelity gate or either required 20% improvement is absent.
- `INCONCLUSIVE` if the corrected tree control, geometry, rank, conditioning,
  or finiteness checks fail.

This experiment does not authorize production adoption or claim measured
runtime performance.
