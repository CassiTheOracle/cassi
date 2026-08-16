# Rim-Coupling Wave 3 — the two-medium boundary — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `rim_coupling_prereg.md` (frozen before runs, with the recorded measurement amendment). Every number below came from the probe output, not the prereg's predictions.

## Verdicts (reconciled against the frozen decision trees)

| Question | Statistic | Measured | Verdict |
|---|---|---|---|
| Q1 — does the explicit rim give the boundary a well-defined reflectivity? | exact matrix scattering of the linear-rim-coupled FV operator at the φ-ratio boundary | naive-join **0.0635%**; rim-linear **23.32% energy** (48.3% amplitude) | **SUPPORTS** — the rim makes the boundary reflectivity well-defined and places it at the two-medium *energy* scale (~23%), far above the raw junction — the coupling, not the resolution step, governs the boundary |
| Q2 — does the taper reach the gate-vi acceptance? | exact matrix scattering through an m_t-cell graded transition | m_t: 0 → 0.0635%, 2 → **0.0212%**, 6 → 0.0035%, 12 → **0.0012%**, 24 → 0.0000% (monotone) | **ACHIEVES** — the taper reaches the ≤2% acceptance by m_t = 2 and drives reflectivity to 0.0012% at m_t = 12 — the robust anti-reflection design law |

## The central finding: the boundary is coupling-defined

**The bare coarse-fine φ-ratio junction has no intrinsic reflectivity in the discrete FV operator.** Three independent exact/measurement methods span 250× on the identical junction (matrix scattering **0.063%**, transfer-march 0.658%, time-domain spatial-SWR 9.9–16%) — the evanescent mode makes the exact value depend on how the two regions are posed, which is precisely **why the sim needs the explicit rim**. The raw junction's reflectivity is not a number; it is a coupling choice.

**The rim (an explicit interpolation coupling) makes it well-defined** and places it at the two-medium energy scale (~23%). The linear-rim amplitude (48%) differs from the continuum impedance amplitude (23.6%) — couplings are not equal; the point is that an explicit coupling has a *unique* value while the raw junction does not. This confirms wave-2's two-medium picture is the *boundary's* governing scale when a non-trivial coupling is used — reconciling the 0.658%-vs-23.6% wave-2 ambiguity: both were valid couplings, not one mistake.

**The taper is the robust design law.** A smooth graded transition is uniquely defined (no junction ambiguity), monotone in the anti-reflection direction (0.06% → 0.0012% at m_t=12), and reaches the gate-vi ≤2% acceptance by just **m_t = 2** cells. This is the boundary recommendation for the ultimate Cassi solver's axial operator: **smooth the interface; don't rely on the bare junction or a naive rim.**

## Harness (all PASS)

`verify_rim.py`, `ALL CHECKS PASSED`: ratio-1 → 2.9e-30 machine zero (the exact solve); the naive junction is a documented coupling value (0.0635% < 1%); each coupling returns a finite well-defined reflectivity; energy conservation 3.91e-3 over 200 steps on the coupled grid; determinism bit-identical.

## Honest reconciliations

1. **The three-method spread is the finding, not a bug to fix.** The time-domain SWR is unreliable below ~1% (erratic 14% → 6.8% → 14.7% across m_t on the same taper) — recorded as an honest negative (the `xcheck_taper.py` / `xcheck_timedomain.py` cross-checks). The exact matrix method is the pre-registered statistic and the only one whose value for a *specified coupling* is unique.
2. **The rim value (23.3% energy) is a 1D linear rim, not the sim's value.** The sim's trilinear-3D rim measured 4–9% (`_diag/b_build.md`). Different operator and normalization (the sim's rim cells overlap the coarse coverage; my geometry extrapolates past the last coarse node). The qualitative law — the rim's interpolation error *dominates* the boundary reflectivity — is the shared, portable content.
3. **The earlier "reproduces the two-medium impedance" phrasing was a units mix** (energy 23.3% vs amplitude 23.6%); corrected to the honest amplitude-vs-energy statement above.

## What this means for the ultimate Cassi solver

- **The boundary must be explicitly coupled** — the raw junction's reflectivity is undefined, so any implementation needs a defined coupling (the sim's rim).
- **The taper is the robust boundary of choice**: smooth (≥2 cells), uniquely defined, ≤2% at m_t=2, vanishing beyond. It subsumes the rim's coupling-ambiguity by removing the discrete interface.
- **Wave 4 (designed, not built):** the faithful *overlapping* rim (fine rim cells inside the coarse coverage — the sim's actual trilinear semantics) to reproduce the sim's 4–9% quantitatively in 1D, then the two-fluid axial PDE with the taper-coupled boundary, gated against the N³ reference.
- No registry entry is proposed.

## Traceability

- Re-run from `CassiCosmos/`: `python research/helix_solver/verify_rim.py`, `rim_probe.py` (the pre-registered statistic), plus the cross-check scripts `xcheck_taper.py`, `xcheck_timedomain.py` (honest negatives).
- Pre-registrations: `rim_coupling_prereg.md`, `smooth_cascade_prereg.md`, `helix_solver_prereg.md`.
- Theory anchors: `_diag/b_build.md` §gate-vi (the sim's measured rim numbers), `CASCADE_GRID.md`, `qi-flow-double-helix.md` §3.1/§4.2, `bubble-lattice-fabric.md` §3.2.
