# Wave 7 — the 3D σ-relaxation time trace — REPORT

**Date:** 2026-08-15 · **Pre-registration:** `triaxial3d_relax_prereg.md` (frozen before the
run). Every number below came from `triaxial3d_relax_probe.py` live output.

## Verdict

**Mixed / non-monotonic relaxation — the transverse ratio converges toward φ, the axial
(string) ratio does not reach φ² before the bubble decays.**

Under the frozen decision tree the outcome is `mixed/non-monotonic` (it is neither clean
relaxation toward the doctrine, nor toward the sim record, nor an ≈flat settled
over-drive). The refined two-component reading — the actual physics:

| ratio (φ-arm, round seed) | 600 steps | 1400 steps (peak) | 2400 steps | doctrine | sim record |
|---|---|---|---|---|---|
| **σ_x/σ_y** (Yang/Yin, transverse) | 2.227 | 2.677 | **1.871** | φ = 1.618 | 1.422 |
| **σ_x/σ_z** (Yang/string, axial) | 3.251 | 5.501 | **4.442** | φ² = 2.618 | 2.510 |
| peak/peak0 | 0.35 | 0.30 | **0.19** (falling) | | |

The symmetric control stays at **1.000 / 1.000** throughout (t=200,1200,2400) — the
3D operator + round seed remain unbiased; the relaxation signal is real, not a drift
artifact.

## What this tells us

1. **The transverse (Yang-Yin) ratio converges toward the doctrine's φ.** σ_x/σ_y rises
   to a 2.68 peak around step 1400, then relaxes monotonically downward: 2.68 → 2.54 →
   2.05 → 2.02 → 1.95 → **1.87 at 2400** — a clear late-time trend toward φ = 1.618. The
   in-plane oblate-transverse shape is converging on the doctrine anchor.

2. **The axial (string) ratio heavily over-drives and does not reach φ² (nor the sim's
   2.510).** σ_x/σ_z rises steeply to 5.50 and relaxes only to 4.44 at 2400 — still 1.82
   above φ² (and 1.93 above the sim record). The downwards relaxation is real but slow,
   and the bubble's amplitude decays concurrently (peak/peak0 0.19 and falling toward the
   pre-registered 10% floor), so the far-future σ_x/σ_z becomes noise before it could
   plausibly reach 2.6. **The operator drives the string-axis compression much harder than
   the doctrine predicts.**

3. **The wave-6 over-shoot is partly transient.** The σ_x/σ_y over-shoot (2.23 → peaks
   2.68 → 1.87) is a short-run transient that relaxes toward φ. The σ_x/σ_z over-drive is
   *not* resolved on these timescales.

## Honest conclusion for the program

- The **in-plane oblate shape** (σ_x/σ_y → φ) is converging — a positive for the
  oblate-triaxial direction.
- The **string-axis compression** (σ_x/σ_z) is **too strong** at these scales: it peaks
  near 5.5 and only relaxes to 4.4, well past the doctrine's φ² = 2.618 and even the
  sim's 2.510. Either the operator's z-weight (h_z = φ⁻¹) needs reconsideration, or the
  sim's longer evolution / its boundary conditions (this solver is periodic in all three
  axes; the sim's string is "bounded") supply the missing relaxation. That is the
  decision-relevant open thread.
- **Not an engine upgrade.** This is a measurement (as pre-registered); it does not
  change the engine and does not yet justify one. Worth noting: the sim's z-boundary is
  NOT periodic (the string is bounded) whereas this probe is periodic in z — a genuine
  representation gap that could be exactly why the axial over-drive persists here. A
  wave-8 with a z-bounded (non-periodic) boundary is the natural test of that hypothesis.

## Determinism / harness

- Gated: the 2400-step φ-arm re-run is bitwise identical.
- Amplitude floor: peak/peak0 was 0.188 at 2400 — still above the 10% pre-registered
  floor, so the trace is valid (not flagged AMBIENT-DECAY), but the margin is closing and
  the late-time σ_x/σ_z is read as strengthening-decay-limited.

## Traceability

- Re-run from `CassiCosmos/`: `python research/helix_solver/triaxial3d_relax_probe.py`
  (~193 s, deterministic).
- Files: `triaxial3d_relax_prereg.md`, `triaxial3d_relax_probe.py` (new, under
  `research/helix_solver/`).
- Machinery: `triaxial3d.py` (wave 6) / the GLSL `lap_ey_at` stencil; doctrine
  `bubble-edge-geometry.md` §2.3; sim record `string_bubble_cascade.py` (1.422, 2.510).
- Prior: wave-6 (`triaxial3d_report.md`) over-shoot 2.227/3.251; the round-seed
  correction.

---

## Dated correction (2026-08-15, wave 8)

**The "transverse converges to φ, axial over-drives" interpretation is tied to the wrong
aspect and the boundary-hypothesis was wrong.** (1) The wave-7 φ-arm used the bubble-shaped
aspect h=(φ,1,φ⁻¹); the **sim's actual operator** is h=(φ,1,φ²) (cell sizes from the box
extents, `cassi_two_fluid.glsl`), fully periodic. On that operator the bubble is
**z-STRETCHED**, not z-bounded: σ_x/σ_z = 0.329, σ_x/σ_y = 0.842 at t=2400 — the opposite of
the wave-7 (φ,1,φ⁻¹) trace (which gave 1.871/4.442). (2) The wave-7 hypothesis that the
probe was "periodic-z while the sim is bounded-z" is **withdrawn** — the shader wraps every
axis with `% N`, so the sim is periodic in z too; there is no boundary gap. The relaxation
trace is a real result but for the (φ,1,φ⁻¹) aspect only, and it does not describe the sim's
operator. The doctrine's oblate 2.510 must come from the source feed / cluster geometry /
gravity sector, not the operator. See `triaxial3d_simop_corr_report.md` (wave 8).
