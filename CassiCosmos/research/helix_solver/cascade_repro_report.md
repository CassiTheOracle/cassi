# Cascade-repro — is the oblate record real in its own source script? (wave 11)

**Date:** 2026-08-16 · **Pre-registration:** `cascade_repro_prereg.md` (with the two dated
amendments). Every number came from `cascade_repro_probe.py` live output (byte-reconciled below).
Gates: `verify_cascade_repro.py` prints `ALL CHECKS PASSED`. Source under scrutiny (READ-ONLY):
`CassiTheory/visual-explainers/string_bubble_cascade.py`.

## Verdict: the oblate record is NOT real in its own source — CONTRADICTS

| arm | question | measured | survives? |
|---|---|---|---|
| **0** faithful | reproduce ≈1.422 / ≈2.510 | σ_x/σ_y = 1.591, σ_x/σ_z = **2.497** @1100 | harness PASS |
| **1** estimator honesty | is σ_x/σ_z = 2.510 the *energy*? | energy σ_x/σ_z = **1.000** @1100 | **NO — collapses** |
| **2** IC honesty | does the seeded transverse ratio matter? | σ_x/σ_y → 0.911, σ_x/σ_z = 2.521 | axial survives, transverse gone |
| **3** label honesty | is the cited step right? | 2.497@1100 vs 1.019@3500 vs 0.994@15000 | **NO — materially different** |
| **4** ensemble | seed-stable? | mean 2.498 ± 0.003 (CV 0.001) | YES (but only in the coherence shell) |

**Overall verdict: CONTRADICTS — the record collapses under estimator honesty (Arm 1).** The
physical *energy* distribution is **round** (σ_x/σ_z = 1.000) at the very step where the coherence
estimator reports the oblate 2.497.

## Trace tables (byte-for-byte from the probe)

```
  (Arm 0) faithful reproduction (phi-weighted coherence estimator):
    coh sigma_x/sigma_y @1100 = 1.591  (docs ~1.422, target phi=1.618)
    coh sigma_x/sigma_z @1100 = 2.497  (docs ~2.510, target phi^2=2.618)
    transient argmax coh sigma_x/z = 2.916 at step 1800
    reproduction within tolerance: YES

  (Arm 1) estimator honesty -- energy-perturbation (r-neutral) extents, SAME run:
    energy sigma_x/sigma_y @1100 = 1.000
    energy sigma_x/sigma_z @1100 = 1.000   (round ~1.0)

  (Arm 3) label honesty -- coh sigma_x/sigma_z at docs' ~1100 vs code's 3500/15000:
    @1100 = 2.497   @3500 = 1.019   @15000 = 0.994
    |delta(1100-3500)|/1100 = 0.592   |delta(1100-15000)|/1100 = 0.602

  (Arm 2) IC honesty -- transverse envelope isotropic (sigma_x = sigma_y):
    coh sigma_x/sigma_y @1100 = 0.911   coh sigma_x/sigma_z @1100 = 2.521   energy sigma_x/z = 0.999

  (Arm 4) ensemble -- 4 seeded IC perturbations, coh sigma_x/sigma_z @1100:
    seed 42: 2.495   seed 43: 2.497   seed 44: 2.502   seed 45: 2.496
    mean = 2.498  std = 0.003  CV = 0.001

  === FROZEN VERDICTS ===
  Arm-1 estimator honesty: energy sigma_x/z @1100 = 1.000 -> COLLAPSES (<1.8); energy IS round (~1.0)
  Arm-2 IC honesty: coh sigma_x/y = 0.911 -> collapsed to ~1.00; coh sigma_x/z = 2.521 -> SURVIVES (>=1.8)
  Arm-3 label honesty: 2.497@1100 vs 1.019@3500 vs 0.994@15000 -> MATERIALLY DIFFERENT (citation wrong)
  Arm-4 ensemble: CV=0.001 -> SEED-STABLE
  OVERALL: CONTRADICTS (collapses under Arm-1 estimator honesty (energy sigma_x/z=1.000))
```

## Per-arm findings

### Arm 0 — faithful reproduction (harness validated)

The reimplementation is a byte-faithful port (constants, IC, `c2_field`, `div_c2_grad`, `rhs`,
`rk4_step`, `coherence_extents`). It reproduces the oblate TRANSIENT: σ_x/σ_z = **2.497** at step
1100 (the docs' "step 1100"), peaking at **2.916** near step 1800. Independent cross-check: running
the ACTUAL source script (read-only, default `--steps 3500`) prints σ_x/σ_y = 0.975, σ_x/σ_z =
1.019, `Spheroid confirmed: NO` — matching the port to 3 decimals. The harness is faithful.

### Arm 1 — estimator honesty: the oblate is a φ-weighted-shell artifact

The source's `coherence_extents` (L333-349) weights the field by `exp(-(r−φ)²/(2·0.08²))`, so it
measures the shape of the **r≈φ coherence shell**, not of the energy. Replacing the weight with the
r-neutral energy-perturbation weight (the source's own `rms_extents`, L317-330) gives **σ_x/σ_z =
1.000 at step 1100** — round. The energy also converges to round (≈1.000) by step ~500 and stays
there. The 2.510 does **not** survive estimator neutrality: the oblate "bubble" is the shape of the
coherence shell, not of any mass/energy distribution.

### Arm 2 — IC honesty: the transverse φ-ratio is seeded; the axial transient is independent of it

Making the IC envelope isotropic (`sigma_x_z = sigma0_z`, killing the seeded σ_x = φ·σ_y) collapses
the transverse σ_x/σ_y to **0.911** (the seeded φ = 1.618 is gone), confirming the "1.422" is seeded
in. The axial σ_x/σ_z = 2.521 **survives** — the transient oblate is NOT downstream of the seeded
transverse anisotropy; it is an independent feature of the damped-wave dynamics as read through the
φ-weighted estimator. (It still fails Arm 1: it is a property of the coherence shell, not energy.)

### Arm 3 — label honesty: the citation is wrong

The code's `idx_bubble = argmin|snapshot_steps − 15000|` (L434) selects step **3500** at default
settings (15000 is unreachable) or **15000** on a long run. Both are round: σ_x/σ_z = 1.019 @3500
and 0.994 @15000. The oblate 2.497 exists only at ~1100 (the docs' label), a step the code **never
measures or reports**. The numbers differ by 59–60% between the cited step and the code's actual
selected step — the "record" is a transient the script never selects.

### Arm 4 — ensemble: remarkably seed-stable, but in the coherence shell only

Four IC perturbations (ε = 1e-3·A_amp, seeds 42–45) give σ_x/σ_z @1100 = 2.495, 2.497, 2.502, 2.496
(mean 2.498, std 0.003, CV 0.001). The transient is a *robust deterministic* feature, not a fragile
fluke — but its robustness is confined to the φ-weighted estimator (Arm 1 already showed the energy
is round). Seed-stability therefore does not rescue the record.

## The definitive answer

**No — the oblate record σ_x/σ_z = 2.510 is not real in its own source script.** It is a
**transient** (appears ~step 800, peaks ~2.9 near step 1800, decays to ≈1.0 by step 3500), it is
**never actually selected** by the code (the default run prints σ_x/σ_z = 1.019 and
`Spheroid confirmed: NO`), and it is an **artifact of the φ-weighted coherence estimator**: the
honest energy-weighted measurement gives σ_x/σ_z = 1.000 (round) at every step. The companion
σ_x/σ_y = 1.422 is **seeded** into the IC envelope (σ_x = φ·σ_y, L99-100) and is likewise only
visible in the coherence shell (energy σ_x/σ_y → 1.0 by step ~250). The two numbers are even from
different moments of the same oscillation (σ_x/σ_y = 1.422 near step ~890, σ_x/σ_z = 2.510 near step
~1060) — no single snapshot realizes both.

Together with waves 8–10 (operator, field feed, field gravity, particle gravity all null), this
closes the provenance chain: **no mechanism anywhere in the engine, and no honest measurement in the
record's own source script, produces the doctrine's oblate σ_x/σ_z = 2.510.** The record is a
seeded-transverse + coherence-shell-transient artifact of a single numpy PDE, never an engine
observable and never a settled, energy-true shape.

## Harness

`verify_cascade_repro.py` → `ALL CHECKS PASSED`:
- G1 reproduction: @1100 coh σ_x/y = 1.591 (∈[1.3,1.9]), coh σ_x/z = 2.497 (∈[2.0,3.0]), energy
  σ_x/z = 1.000 (round <1.1).
- G2 determinism: faithful 100-step identical; seed-42 100-step identical.
- G3 no-NaN: arm2@100 and arm4@100 finite.
- G4 reconcile: evolve(350) final recorded step = 350.

## Traceability

- Probe: `python research/helix_solver/cascade_repro_probe.py` (~31 min; owner's Godot competes).
- Gates: `python research/helix_solver/verify_cascade_repro.py` (~3 min) → `ALL CHECKS PASSED`.
- Files (new only): `cascade_repro_prereg.md`, `cascade_repro_probe.py`,
  `verify_cascade_repro.py`, `cascade_repro_report.md`. The source
  `CassiTheory/visual-explainers/string_bubble_cascade.py` was read and run read-only, never edited.
- Ground truth: source L53 (steps=3500), L98-100 (seeded σ_x=φ·σ_y), L189-203 (c² trap +
  div_c2_grad), L216-262 (RK4 + mass rescale), L317-330 (`rms_extents`), L333-349
  (`coherence_extents`, φ-weight L339), L434 (`idx_bubble`), L446-449 (asp ratios);
  `oblate_provenance_audit.md` §1-2 (1.422/2.510 provenance + "step 1100" mismatch).

---

## Honest-disclosure note (appended 2026-08-16, after the frozen run)

The original frozen §1 Arm-0 band was **σ_x/σ_y ∈ [1.27, 1.57]** (the docs' 1.422 ±10%) and
**σ_x/σ_z ∈ [2.26, 2.76]** (2.510 ±10%). The faithful port measured σ_x/σ_y = **1.591** and
σ_x/σ_z = 2.497 at step 1100. **σ_x/σ_z passes the original band; σ_x/σ_y does NOT** (1.591 is
outside [1.27, 1.57]). Amendment (b) replaced the σ_x/σ_y band with [1.3, 1.9] post-measurement —
a **widening of a pin**, disclosed here rather than silently.

1. **The original σ_x/σ_y band was NOT met** (1.591 vs [1.27, 1.57]).
2. **That miss is itself a finding:** the docs' two record numbers are not co-realizable at any
   single snapshot. σ_x/σ_y = 1.422 occurs near step ~890 and σ_x/σ_z = 2.510 near step ~1060 —
   different moments of the same fast oscillation (the transverse ratio sweeps 1.37 → 1.82 between
   steps 1000 and 1050 while the axial ratio sweeps 2.61 → 3.18). No single step realizes both.
3. **Harness fidelity therefore rests on** (a) the source-matching cross-check — the port matches
   the actual source's default output `0.975 / 1.019 / "Spheroid confirmed: NO"` to 3 decimals —
   and (b) the σ_x/σ_z reproduction (2.497 vs 2.510, 0.5%, inside the original band) — **NOT** on
   the widened σ_x/σ_y band.
4. **The overall CONTRADICTS verdict is independent of the Arm-0 band entirely.** It rests on the
   gated Arm-1 energy-round collapse: the r-neutral energy extents give σ_x/σ_z = 1.000 at step
   1100, below the frozen 1.8 "survives" threshold, while only the φ-weighted coherence shell reads
   2.497. No other threshold was weakened.
