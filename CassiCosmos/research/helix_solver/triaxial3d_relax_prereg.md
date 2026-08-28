# Wave 7 — the 3D σ-relaxation time trace — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run; governs the wave-7 arms

**Date:** 2026-08-15 (continuation) · **Workstream:** the ultimate-Cassi-solver 3D shape ·
**Pre-registered outcome:** does the wave-6 over-shoot (σ_x/σ_y = 2.227, σ_x/σ_z = 3.251 at
600 steps vs the doctrine φ=1.618, φ²=2.618) **relax toward the doctrine anchors** at
longer times, or is it the settled/intrinsic value?
**Probe (deterministic, numpy, matrix-free):** `triaxial3d_relax_probe.py`.

---

## 0. Why this wave

Wave 6 established that the full-3D oblate-triaxial operator, on a **physically-round**
seed, imprints the doctrine's oblate/z-bounded *direction* but **over-drives the
magnitude** (2.227, 3.251 at 600 steps vs φ=1.618, φ²=2.618). The pre-registered Q1 did
not ACHIEVE as frozen. The decision-relevant next question — which determines whether the
over-shoot is a *short-run transient* or an *intrinsic operator property* — is: how do the
σ-ratios evolve with time? The sim's own record (`string_bubble_cascade.py`, step ~1100)
gives σ_x/σ_y = 1.422, σ_x/σ_z = 2.510 — **below** the doctrine's φ/φ², the *opposite* of
our 600-step over-shoot. If the 3D solver's ratios relax toward (or past) those as time
grows, the over-shoot is a transient and the sim's longer-evolved record is the target.

**Provenance note (2026-08-16):** the 1.422/2.510 values are single-run outputs of `CassiTheory/visual-explainers/string_bubble_cascade.py`, NOT engine measurements — see `research/helix_solver/oblate_provenance_audit.md` (commit 27ad20f) and `oblate_claim_map.md` (15db3c8).

## 1. Frozen setup (reuses the wave-6 machinery, unchanged)

- Operator: the sim's exact 3D 19-point anisotropic periodic Laplacian, matrix-free
  (`triaxial3d.make_lap`, `TwoFluid3D`). φ-arm h = (φ, 1, φ⁻¹); control h = (1,1,1).
- Grid N = 64; dt = 0.02; two-fluid with the half-kick; c=1; ω₀²=20.
- Seed: the **physically-round** 3D Gaussian (wave-6 correction — the honest discriminator).
- **Time trace:** measure σ_x/σ_y, σ_x/σ_z, and peak |EY+EI| at t = 200, 400, …, 2400 steps
  on the φ-arm; the control at t = {200, 1200, 2400} as the isotropy invariant.

## 2. Decision (frozen)

| Verdict | Condition |
|---|---|
| **RELAXES → doctrine** | on the φ-arm, σ_x/σ_y(t) and σ_x/σ_z(t) move monotonically-ish toward φ/φ² over the trace, and the 2400-step reading is closer to φ/φ² than the 600-step reading (in total relative distance) |
| **RELAXES → sim record** | the 2400-step readings approach the sim's recorded 1.422 / 2.510 (±15%), i.e. relax downward past the wave-6 values but settle at (or through) the sim record rather than at φ/φ² |
| **INTRINSIC (over-shoot is settled)** | the ratios stay within ±10% of the 600-step values (2.227/3.251) throughout, or grow — i.e. no relaxation |
| **INCONCLUSIVE** | harness failure, OR the peak amplitude decays below 10% of its initial value before 2400 steps (a decayed bubble's σ moments are noise), OR determinism fails |

A **reported outcome** (any of the above) is the deliverable; the φ-arm/doctrine anchor
itself is not moved by this probe — it records what the operator actually does.

## 3. Harness guard (inline, unconditional)

- The peak |EY+EI| must exceed 10% of its initial value at every reported step, else the
  trace is flagged AMBIENT-DECAY (σ moments unreliable) and the verdict is INCONCLUSIVE.
- Determinism: the 2400-step φ-arm run re-run bitwise identical.

## 4. Number provenance

- Wave-6 values (2.227/3.251 at 600): `triaxial3d_report.md` (reconciled to live output).
- Doctrine anchors: `bubble-edge-geometry.md` §2.3 (φ, φ² per the oblate spheroid axes);
  §2.2 (the 1.70 edge, not the subject here).
- Sim record: `visual-explainers/string_bubble_cascade.py` (1.422, 2.510 at step ~1100).
- Machinery: `triaxial3d.py` (wave 6), the GLSL `lap_ey_at` stencil.

## 5. What does NOT count

- Post-hoc step limits, thresholds, grid, aspect, or seed changes.
- Reading this time-trace as an edge/ring result (a different program thread).
- Claiming this as an engine upgrade — viability is a separate, later question.
