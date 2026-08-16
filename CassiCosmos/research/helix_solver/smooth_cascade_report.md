# Smooth-Cascade Wave 2 — the axial design law — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `smooth_cascade_prereg.md` (frozen before runs). Every number below came from the probe scripts, not the prereg's predictions.

## Verdicts (reconciled against the frozen decision trees)

| Question | Statistic | Measured | Verdict |
|---|---|---|---|
| Q1 — the design law | exact single-node/taper reflectivity of the FV Helmholtz, γ(m) across a φ-rung | m=0: **0.6580%**, m=2: 0.2289%, m=3: 0.0246%, m=6: 0.0066%, m=12: **0.0018%**, m=24: 0.0006% (monotone from m=2; m=1 ≡ m=0 exactly, a 1-cell taper = the single node) | **SUPPORTS** — the graded-index taper cancels reflection far below the ≤2% target; **design law m\* = 0 cells per rung** for interior transport |
| Q2 — cascade preservation under subdivision | per-rung group-velocity factor \|sin q/q\| at rung boundaries | m=1 and m=12 are **bit-identical**: 0.9003, 0.7518, 0.4302, 0.0000 (rungs 0–3) | **EMERGES** — the self-resolving window is exactly scale-invariant under subdivision; the fix for transport does not touch the cascade |

## The central finding (corrects wave 1)

**Wave-1's 23.61% Q1 CONTRADICTS was measuring the wrong quantity.** It used the two-semi-infinite-medium acoustic-impedance formula γ = |(r−1)/(r+1)| — correct for a genuine coarse-fine *patch boundary*, but NOT for the φ-grid's *interior*, where every cell junction is a **single node** of the finite-volume operator. A single-node spacing step is a localized point-scatterer reflecting O(Δh²) at long wavelength: the exact FV scattering gives the bare φ-ratio single node at **0.658%** (far more transparent than the two-medium picture). The raw φ-shelled grid's interior was already under the gate-vi acceptance — **no rim is needed inside the cascade grid.**

The taper then acts as the anti-reflection coating: γ falls 0.658% → 0.229% (m=2) → 0.0018% (m=12) → 0.0006% (m=24), a graded-index cancellation of ~10⁴× vs the naive 12-independent-steps bound (γ=1.83e-5 vs 2.41e-1). The 23.6% two-medium case — and the gate-vi interpolated rim that fixes it — is a *boundary* problem (the sim's coarse-fine patch edge), which wave 3 measures.

## Harness (all PASS)

`verify_smooth.py`, `ALL CHECKS PASSED`: rung-lattice preservation exact (0.0 deviation — the taper subdivides, never moves, z_k = z₀φ^k); taper per-cell ratio φ^(1/12) exact (1.040916); the scattering march is self-consistent (ratio-1 → 1.6e-30 machine zero; m=1 ≡ m=0; m=2 halves with cancellation); energy conservation 1.33e-3 over 200 steps; determinism bit-identical.

## Honest reconciliations

1. **Q2 rung-3 group factor: 0.0000 here vs 0.055 in wave 1.** Both are readouts of the same collapse. Wave 1 evaluated |sin q/q| continuously (q=3.33 at rung 3 → 0.055); `per_rung_group` here clips to 0.0 past q=π. The collapse is identical; only the plotting convention differs. The load-bearing fact — the factors are bit-identical between m=1 and m=12 — is exact.
2. **m\* = 0** is the honest answer to the pre-registered "how many cells per rung": for interior single-node transport, zero — the raw φ-grid already passes. The taper's value is at genuine two-medium boundaries (wave 3), not the interior.
3. **The 23.6% is not deleted, it is relabeled:** it governs the two-medium *boundary*, where the interpolated rim (the sim's gate-vi machinery) is the coupling. Wave 3 measures rim-coupled coarse-fine transmission in the cascade geometry.

## What this means for the ultimate Cassi solver

- The **axial cascade grid is solved for the interior**: φ-ratio single nodes are near-transparent (0.658%); no subdivision or rim is required for interior wave transport.
- The **cascade structure is scale-invariant**: subdividing to smooth the grid leaves the per-rung coherence window bit-identical, so there is no resolution-smoothness trade-off to navigate.
- The **remaining open question** is the genuine coarse-fine *boundary*: the sim's φ-ratio patch edge (the two-medium 23.6% case) and whether the gate-vi interpolated rim pulls it under 2% in the cascade geometry — wave 3.

## Next wave (designed, not built)

- **Wave 3: the two-medium rim.** Build the coarse-fine patch boundary (a real change of region, not a single node) in the cascade geometry with the gate-vi interpolated-ghost rim; measure the rim-coupled reflectivity vs the uncoupled 23.6% and the taper-rim combination; target ≤2%. This is the sim's actual coarse-fine coupling mapped to the axial operator.
- **Wave 3b:** the two-fluid PDE's transverse (per-shell) Laplacian + the axial operator, gate-iv-style fidelity vs the N³ reference before any adoption.
- No registry entry is proposed.

## Traceability

- Re-run from `CassiCosmos/`: `python research/helix_solver/verify_smooth.py` and `python research/helix_solver/smooth_probe.py` (deterministic). Wave-1: `verify_phi_grid.py`, `wave_probe.py`.
- Pre-registrations: `smooth_cascade_prereg.md` (with the recorded wave-1 Q1 correction), `helix_solver_prereg.md` (wave 1).
- Theory anchors unchanged from wave 1: `qi-flow-double-helix.md` §3.1/§4.2, `bubble-lattice-fabric.md` §3.2, `CASCADE_GRID.md` §2/§3, `two-strand-five-channel-matter-organization.md` §3.8/§3.13.
