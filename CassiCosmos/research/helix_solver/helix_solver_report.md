# Helix Solver Wave 1 — the φ-shelled axial grid probe — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `helix_solver_prereg.md` (frozen before any run). Every number below came from the probe scripts, not the prereg's predictions.

## Verdicts (reconciled against the prereg's frozen decision trees)

| Question | Statistic | Measured | Verdict |
|---|---|---|---|
| Q1 — single-interface reflectivity | acoustic-impedance mismatch γ = (1/h_c − 1/h_f)/(1/h_c + 1/h_f) at the φ-ratio interface | **γ = 23.61%** (h_c = 0.618, h_f = 0.382) | **CONTRADICTS** raw-interface transparency — a φ-ratio interface reflects ~24% of a coarse-resolved incident wave; a full-span cascade grid requires the ghost-cell/rim coupling (the gate-vi machinery) |
| Q2 — the self-resolving window | discrete group-velocity factor \|sin q/q\| per shell | φ-grid: 0.900 → 0.752 → 0.430 → **0.055** (rungs 0–3), the hard Nyquist wall at q ≈ π then death; uniform: 0.900 at every rung | **EMERGES** — the φ-grid carries a ~4-rung self-resolving window as its own dispersion property; the uniform grid has no wall |

**Reported per-rung group-factor ratio (rung 0 → 3):** 0.0615. The theory's $\varphi^{-1} = 0.618$ is **compared, not claimed** — the grid's resolution-transport suppression is a different amplitude than the coherence-transfer suppression (`cascade-suppression-formula.md`), and no registry entry is made.

## What the harness pinned (all PASS)

The harness gates (`verify_phi_grid.py`, `ALL CHECKS PASSED`) establish the probe's validity:
- φ-ratio exact: `z_{k+1}/z_k = φ` to 1.8e-15; the uniform arm spans `[1.0, φ⁷]`, finer than the φ-arm's finest spacing.
- The finite-volume operator is symmetric under the cell-volume mass (|AᵀM − MA| = 2.2e-16) and reproduces the smooth-residual (A sin z = −sin z) in the resolved interior.
- Energy conservation: uniform 6.7e-5, φ 1.8e-3 over 200 steps (the symplectic order — bounded, no secular leak).
- Determinism: two runs bit-identical.

## The central finding (a real, reusable fact)

**On a φ-spaced grid, the classic 3-point non-equidistant centered second-difference is not symmetric (`|A − Aᵀ| = O(1)`, measured 2.0 at K=8), so it has no conserved discrete energy.** The wave equation on a strongly non-uniform grid must use the **finite-volume Laplacian** `A = −M⁻¹BᵀWB` (edge incidence B, edge weights W = diag(1/h_k), cell volumes M), with the M-weighted leapfrog and the conserved energy `E = ½(vᵀMv + c²(Bu)ᵀWu)`. This is the mandatory discretization for any φ-shelled cascade solver — the centered stencil's failure is prescriptive for wave 2.

## The honest negatives (deliverables, not failures)

1. **The localized-wave probe is ill-posed on the φ-grid.** A fixed-wavelength Gaussian is sub-cell at the coarse end and absurdly over-resolved at the fine end of a single span (spacing varies φ⁷ ≈ 29×). The first redesigned probe's `c_fit` was garbage (0.44 vs the analytic 1.0) and its per-band amplitude readback conflated the pulse passing different bands at different times. The corrected probe is the deterministic dispersion-structure measurement (Q2) and the local impedance measurement (Q1) — no time-stepping.
2. **Q1 CONTRADICTS raw transparency.** The per-interface ~24% reflection is the honest cost of the φ-spacing ratio; it is why wave 2 must couple shells with the gate-vi ghost-cell/rim scheme rather than a naive coordinate jump.

## What this means for the ultimate Cassi solver

- The **axial (string/cascade) grid CAN be the φ-shelled slice** — Q2 EMERGES proves the grid itself breeds the cascade's per-scale coherence window (the self-resolving band), which is the theory's nested-sub-lattice structure made numerical.
- But raw φ-spaced shells **cannot be the transport channel without rim coupling** (Q1) — the shells must be joined like gate-vi's coarse-fine patches, not naively stacked.
- And the solver **must use the finite-volume Laplacian**, not the centered stencil — the non-conservation finding applies to any implementation.

## Next wave (designed, not built)

- **Wave 2: the rim-coupled φ-shell axial operator.** Use the gate-vi ghost-cell machinery at each φ-interface; re-measure the per-rung transmission with the rim in place; target: push the per-interface reflectivity from 23.6% toward the gate-vi ≤2% acceptance.
- **Wave 2b: the two-fluid PDE on the φ-shell stack** — the transverse finite-volume Laplacian on each shell + the rim-coupled axial operator, measured against the N³ reference (gate-iv discipline) before any adoption.
- No registry entry is proposed on this wave.

## Traceability

- All numbers: re-run `python research/helix_solver/verify_phi_grid.py` and `python research/helix_solver/wave_probe.py` from `CassiCosmos/` (deterministic).
- Pre-registration: `helix_solver_prereg.md` (with the two disclosed amendments: harness tolerances/CFL; the stencil swap to the finite-volume operator).
- Theory anchors: `CassiTheory/foundations/qi-flow-double-helix.md` §3.1 (string axis = cascade direction), §4.2 (planar degeneracy at P_∥ = 2); `CassiTheory/foundations/bubble-lattice-fabric.md` §3.2 (the ring ladder, tiered inference); `CassiCosmos/CASCADE_GRID.md` §2/§3 (the measured golden-offset negative); `CassiTheory/hypotheses/two-strand-five-channel-matter-organization.md` §3.8/§3.13 (the π-anti-phase and helix records, cited not re-measured).
