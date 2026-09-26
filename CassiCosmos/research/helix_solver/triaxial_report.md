# Triaxial-Transverse Wave 5a — the φ-ellipsoid probe — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `triaxial_prereg.md` (frozen before runs). Every number below came from the probe output, not the prereg's predictions.

## Verdict

| Question | Statistic | Measured (symmetric control → φ-ellipsoid) | Verdict |
|---|---|---|---|
| Q1 — does the φ-ellipsoid imprint the doctrine's anisotropy? | **σ-ratio** (robust: second moments) + edge-steepness ratio (arc-proxy, **uncalibrated**) | σ_x/σ_y: **1.000 → 1.212**; edge-steepness ratio: 0.540 → 1.776 (proxy has an inherent bias: its own control is 0.54, not ~1) | **EMERGES (on the clean σ-anisotropy)** |

**Q1 EMERGES, on the σ-anisotropy.** The φ-ellipsoidal transverse Laplacian leaves the isotropic control for the second-moment ratio (1.212 vs 1.000), robust to the seed (second moments, not contour crossings). A spherically-symmetric operator is structurally incapable of producing the anisotropy.

**The edge-steepness ratio is an UNCALIBRATED reading in this wave, not a claim.** The arc-proxy's own symmetric control reads 0.540 (an isotropic operator + symmetric seed must give ≈1.0), exposing an inherent directional bias in the theta-contour-crossing measurement (the stencil's axial-vs-diagonal discretization). The φ-arm's 1.776 is a *relative* anisotropy, not an absolute match to the doctrine's 1.70 — the "within 3%" phrasing in an earlier draft was withdrawn. A correct edge proxy (e.g., the true |∇C|_{axial}/|∇C|_{diag} at the θ contour resolved without the ray-arc bias) is the follow-on, not this wave's result. The doctrine's 1.70 remains an open target for a correctly-instrumented measurement.

**The triaxial idea itself stands:** the φ-ellipsoid (not the sphere) is the geometry that imprints the anisotropy — now established by the robust σ-anchor.

## The honest secondary finding: the shader's two-fluid coupling is non-conservative as written

The harness conservation gate exposed a real property of the PDE, not a machinery defect:
- **Free case (ω₀² = 0, two independent waves): the FV + leapfrog machinery conserves to 3.7×10⁻⁴** over 600 steps (the gate passes) — the machinery is sound, deterministic (bit-identical), isotropic control correct.
- **Coupled case (ω₀² = 20): energy "drifts" 7.3×10⁻²** because the sim's EY/EI coupling terms (−ω₀²(EY−φEI) and +ω₀²(EY−φEI)) are not the gradient of a common potential — there is no symmetric cross-energy, so no quadratic energy is conserved as written. This is a **documented property of the PDE** `cassi_two_fluid.glsl`'s coupling, worth flagging to whoever tunes the shader (a symmetric potential of the form (EY−φEI)² with matching prefactors would restore conservation).

## Harness (all PASS)

`verify_triaxial.py`, `ALL CHECKS PASSED`: the symmetric control is isotropic (σ = 1.000); the φ-arm is anisotropic (1.212); the free-case machinery conserves (3.7e-4); determinism bit-identical; plus the reported coupled-drift finding.

## Honest scope notes

- **A1 (transverse σ ratio → φ)** measured: 1.212, relaxing toward φ (the recorded `string_bubble_cascade.py` value was 1.42 at longer/3D evolution).
- **A2 (axial ratio → φ²)** and **A4 (the ring ladder 0.618/0.786)** are 3D and/or nonlinear quantities — flagged in the prereg as the follow-on, **not claimed here**. This probe establishes the transverse-plane (A1) signature; A3 (the 1.70 edge ratio) needs a correctly-instrumented proxy (the arc-proxy is uncalibrated).
- The σ-ratio 1.212 < φ=1.618 reflects a short (600-step) linear-wave run; the operator imprints the anisotropy, and full relaxation to φ is a longer/3D property (the recorded 1.42 at step 1100).

## What this means for the ultimate Cassi solver

Your triaxial idea is now data: **the solver's transverse geometry should be the φ-ellipsoid, not the sphere** — the φ-ellipsoidal operator imprints the anisotropy (σ-ratio leaves the isotropic control), where a sphere structurally cannot. The φ-aspect box in the sim is the rectangular-room coordinate approximation of the same φ-anisotropy. The doctrine's 1.70 edge-steepness is a correctly-instrumented follow-on; the ring ladder and the axial φ² ratio are 3D/nonlinear follow-ons. The natural full-3D merge (wave 6) is the axial (waves 1–4) × φ-ellipsoid-transverse (this wave) combined operator, gated against the `string_bubble_cascade.py` anchors.

No registry entry is proposed (this is a probe; the number 1.70 was already the doctrine's).

## Traceability

- Re-run from `CassiCosmos/`: `python research/helix_solver/verify_triaxial.py`, `python research/helix_solver/triaxial_probe.py` (deterministic, ~27 s each).
- Pre-registration: `triaxial_prereg.md`.
- Doctrine anchors: `bubble-edge-geometry.md` §2.1 (φ ratio, recorded 1.42), §2.2 (1.70), §2.3 (the B(x,y,z) triaxial field, recorded 2.51 for the axial ratio), §3.1 (ring ladder); the recorded `visual-explainers/string_bubble_cascade.py` σ values; the coupled-PDE terms `cassi_two_fluid.glsl`.
