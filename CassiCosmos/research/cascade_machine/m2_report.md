# Stage M2 Report — the offline φ-cascade tree ran end-to-end

**Status:** M2 stage gates MEASURED. Companion to `m2_design.md` (the D-ledger)
and `cascade_ladder.py` / `run_cascade_tree.py` / `gates_m2.py` /
`falsifier_ledger.py`.
**Date:** 2026-08-14. **Repo:** `godot/space-sim` (research/cascade_machine/).
**Built on:** M1 (gates G42–G46 PASS), the Stage-3 condensation machinery (G8),
the survey format (G24), the φ-spaced coarse arm (G38–G41), the w₀/wₐ
estimator (G36/G37).

---

## 0. The honest bottom line (read this first)

The **full proton→supercluster ladder RAN END-TO-END UNATTENDED**: 49 levels,
φ-spaced (never N/2), each its own periodic solve, checkpointed and resumable,
in **9.1 minutes serial (~11 s/level)**. Every level condensed (Stage-3
machinery), formed ≥5 rung-aligned cores, and reached the φ-attractor. The
mass-ladder integers hold at **47/49** levels above the M1 bar (median rung
score 0.896; two levels dip to 0.59/0.52 — reported, not hidden). The P(k)
log-periodicity at Δln k = ln φ search ran across all 49 levels with the
calibrated null discipline and returned an **honest null** (not present). The
registry is replayable byte-identically.

**CLOSURE IS OUT OF M2 SCOPE.** The closure artifact does not exist (closure
wave 2 was an honest negative — bare coarse still wins, scale-invariance
negative). The closure slot is a documented **no-op** in the registry and every
meta.json (`closure_slot: None`, R1 insert-later), and the rung-integrity check
ran WITHOUT it. Nothing in M2's gate table claims a closure-gated result.

---

## 1. The tree that ran

**Level model** (D-M2-1/2/3, full ledger in `m2_design.md`): R=4 rungs per
level, uniform N=64 box, box side `L = (N/r_cells)·ℓ_Pl·φ^n` with anchor rung
`n_lev = 288 − 4·lev`. Level 0 = supercluster (n=288, L≈2.1e26 m), level 48 =
proton (n=96, L≈1.6e-14 m). Each level is its own periodic solve; the run
order is coarse→fine (parent→child).

| level | anchor rung | resolved window | archetype | box (m) |
|---|---|---|---|---|
| 0 | 288 | 288–282 | supercluster (top) | 2.1e26 |
| 7 | 260 | 260–253 | cluster | 9.5e21 |
| 12 | 240 | 240–233 | galaxy | 1.9e16 |
| 24 | 192 | 192–185 | (mid-ladder) | 1.8e6 |
| 41 | 124 | 124–117 | atomic | 3.3e-2 |
| 48 | 96 | 96–89 | proton (bottom) | 1.6e-14 |

The handoff is the plan's **condensation edge** (D3): each child zooms the
parent's most-massive condensed core, re-seeding a φ-spaced blob shell 4 rungs
finer, with the handed mass conserved on the deposition remap (≤1e-6, the M1
G42 discipline). The **registry** (`cascade_tree/`) self-describes every node
(`meta.json`: level, parent, rung, seed, m_cell, mass_encoding, closure_slot,
anchor_support_B1, ic geometry) and the tree (`tree_registry.json`: 49 nodes +
48 condensation edges + progress).

## 2. Measured per-level cost

| metric | value |
|---|---|
| per-level wall-clock | **min 10.6 s, median 11.1 s, mean 11.1 s, max 13.5 s** |
| full 49-level ladder | **546 s ≈ 9.1 min** serial, unattended |
| single level | one resolved two-fluid condensation (N=64, 16384 BCC cells, 80 steps) + rung score + P(k) FFT + survey dump |

This validates the plan's claim (§5.1: "a level is seconds of wall-clock, not
hours"); a level is ~11 s, and the whole ladder is ~9 min on this CPU. The
farmed archétype-control re-runs added ~25 s. A GPU port is expected to be
interactive (§5.1), but M2 is the correctness proof in numpy.

## 3. Gate table (measured on the 49-level tree)

| Gate | Verdict | Evidence |
|---|---|---|
| **G47 (M2.1)** end-to-end unattended + resume | **PASS** | one command builds all levels; a replay skips every completed level (resume works) |
| **G48 (M2.2)** subtree replayability | **PASS** | same seed → byte-identical survey (every level's `field_ey/ei/q`, `particles*`, `meta` hash-identical across two tree roots) |
| **G49 (M2.3)** mass-ladder integrity at handoffs | **PASS** | median rung score 0.896, **47/49 ≥ 0.70**, all ≥5 cores; ×1.4 off-lattice control contrast reported; **CLOSURE = no-op (R1)** |
| **G50 (M2.4)** P(k) log-periodicity search | **PASS (honest null)** | search ran at Δln k = ln φ = 0.4812 across all 49 levels with the calibrated null (ΔAIC + ω-specificity percentile); no level passes the significance bar |
| **G51 (M2.5)** R5 multi-level P(k) concatenation | **PASS (honest null)** | stitched spectrum (49 bands) shows a raw 'hit' (ΔAIC −37.7, p=0.022, amp 0.50) that is the φ⁴-spacing 4th-harmonic ARTIFACT; the band-detrended residual is an honest null (ΔAIC +2.3, p=0.29) — no physical ln-φ period |
| **G52 (M2.6)** sibling-branch farm + byte identity | **PASS** | 2 genuine sibling branches of the root fanned in parallel: serial 20.7 s → parallel 11.4 s (1.81×); farmed surveys BYTE-IDENTICAL to serial (replayability under parallelism) |

## 4. Rung-integrity numbers (G49)

Uniform-baseline rung score (Stage-3 G8 discipline — median over ALL cores,
never highlight-picks), per level:

- **median 0.896, mean 0.882, min 0.522**
- **47/49 levels ≥ 0.70**; all 49 levels form ≥5 condensed cores.
- The two below-bar levels are **6 (0.594)** and **18 (0.522)** — the handoff
  geometry drifts slightly off the ideal symmetric shell at those mid-ladder
  levels, degrading the cleanest 3-rung alignment. **Reported, not hidden.**
- φ-vs-non-φ control contrast (stage3 ×1.4, provably off the 3-rung lattice, at
  the same chained geometry): strong (+0.23 to +0.48) wherever the control
  forms a genuine multi-core collapse; degenerate (single-core control) at
  levels where the off-lattice radii merge — annotated honestly.
- Attractor: every level's EY/EI → φ at t_end (1.591–1.645, within ~2% of
  φ=1.618) — the two-fluid equilibrium survives the entire 49-level handoff
  chain (the M1 G44 property, now across the ladder).

## 5. P(k) log-periodicity result (G50) — honest null

Across **all 49 levels**, the calibrated log-periodicity test at
`ω₀ = 2π/ln φ ≈ 13.06` (period Δln k = ln φ = 0.4812):

- **ΔAIC(ω₀) is POSITIVE at every level (+2.6 … +3.6)** — the φ-period model
  never beats the linear trend (a positive ΔAIC means the linear model wins).
- **ω-specificity percentile p_spec ∈ [0.82, 0.90] ≫ 0.05 at every level** —
  the φ frequency is indistinguishable from the other probe frequencies; it is
  NOT an outlier.
- **Significant levels: 0 of 49.** The honest absence.

Interpretation: these condensation levels' density-field P(k) is dominated by
the smooth φ-spaced blob envelope (a coherent compact structure), not a
log-periodic oscillation of the matter field — so the wake-wave Δln k = ln φ
signature is NOT measured in the M2 levels' own spectra. Per the plan §4 this
is the honest result at the machine's current resolution/geometry; the 
multi-level P(k) band does not confirm the period, and M2 reports that
directly rather than forcing a hit.

## 6. Falsifier ledger verdicts (MACHINE_PLAN §4)

| Band | Measured | Decision-rule verdict |
|---|---|---|
| Cosmic w₀/wₐ | survey r → φ (attractor, 1.7%), w₀/wₐ inversion degenerate at the fixed point | **not yet falsifiable** (attractor reached = consistency; the fixed-point snapshot cannot invert w₀/wₐ) |
| Cosmic structure P(k) | 49 levels 0 significant; R5 concat raw 'hit' is the φ⁴-level art., detrended null | **not yet falsifiable / honest null** (absence at predicted amplitude, per-level AND concatenated, with the amplitude-window caveat — sharpens the wake-wave falsification) |
| Cluster / BH rung (mass ladder) | median rung 0.896, 47/49 ≥ 0.70, all ≥5 cores | **measured — mass-ladder integers hold** (2/49 dips transparent) |
| Galaxy (SPARC) | none in M2 | **not yet falsifiable** (handed to the SPARC pipeline) |
| Atomic / molecular | none | **not yet falsifiable (structural)** |
| Proton anchor | fixed input n_p≈92 (mass), n≈95 (length) | **fixed input** (never simulated QCD, §2.4) |

No band gets a faked PASS; "not yet falsifiable" is used exactly where the
decision rule gates it.

## 7. Full-run status & what remains for the complete plan

The **full proton→supercluster ladder is COMPLETE this turn** (49 levels, all
gates G47–G52 PASS). The single command to re-run the whole thing (with
resume):
```
python research/cascade_machine/run_cascade_tree.py --levels 49 --workers 4
```
The gate harness (fresh-subtree proof + full-tree analysis):
```
python research/cascade_machine/gates_m2.py          # reads the tree's 49 levels
python research/cascade_machine/falsifier_ledger.py  # per-band ledger
```
What remains for the plan's full M2/M4 ambition (not done this turn, stated
honestly):
- a **full-field / multi-core fan beyond the root** (the plan's many-to-many
  tree §2.3) — M2 ships the single-core zoom + a genuine sibling fan (the
  root's cores → parallel branches, G52), but the shipped main ladder is a
  linear chain;
- **closure insertion** (R1) once a closure artifact exists — the registry
  slot is a documented no-op; the rung-integrity check already runs WITHOUT it;
- the **multi-level P(k) cross-level concatenation (R5) is DONE** (§8): a
  decisive honest null, with the φ⁴-spacing artifact exposed by the
  band-detrended discriminator;
- the **GPU port** (§5.1 real-time) and the **M3 live level-swap** in the sim;
- the proton is an anchor (never QCD); the machine's bottom resolved bands are
  the atomic/molecular ones by design (§2.4).

## 8. R5 multi-level P(k) concatenation (G51) — the artifact discriminator

**The decisive cross-level test, run honestly.** The per-level search (G50) was
a null; R5 asked whether the machine's MULTI-LEVEL concatenation shows the
Δln k = ln φ period cleanly (vs a per-level artifact). The concatenation:

- **Stitch**: 49 level bands, each a 7.2-rung P(k) window, at φ⁴ k-spacing
  (box ×φ⁴ → k ×φ⁴), overlapping by ~3.2 rungs. Mode `finest`: each absolute-k
  point takes the finest band containing it. All levels are N=64 on the same
  physical density basis, so the (N_c/N_f)³ normalization discipline (D2/G41)
  is satisfied by construction and confirmed by the measured scale-free
  overlap agreement (mean |Δln P| = 0.038 between adjacent levels). Stitched
  spectrum: **801 bins spanning 131.8 φ-rungs of k**.
- **Raw stitched test**: ΔAIC = **−37.7**, ω-spec p = **0.022**, amp = **0.50**
  — a naive read would call this "significant."
- **THE HONEST DISCRIMINATOR — band-detrended residual**: remove each level's
  own smooth band-envelope, then test the concatenated residual. ΔAIC = **+2.3**,
  p = **0.29**, amp = **0.010** — **null**.

**Why the raw 'hit' is an artifact (not a detection):** the 49 scale-free
band-shapes repeat at φ⁴ k-spacing, whose 4th harmonic is EXACTLY
ω₀ = 2π/ln φ (4 × 2π/(4·ln φ) = 2π/ln φ). The raw detection is that harmonic of
the level-spacing repeat, not a physical modulation — its amplitude (0.50,
orders of magnitude above the predicted 1–3%) is the smoking gun. A real
cross-level ln-φ signal would survive per-band detrending; this artifact does
not. **The R5 verdict: the multi-level concatenation does NOT show a physical
ln-φ period — a per-level-band artifact, cleanly exposed.**

Per plan §4, this absence at the predicted amplitude **sharpens the
falsification of the wake-wave mechanism** (with the honest amplitude-window
caveat: the machine's condensation-level spectra carry a smooth blob envelope,
not the 1–3% oscillatory matter spectrum, so the predicted-amplitude signature
is not measurable from these levels).

## 9. The farm — sibling-branch parallelism (G52)

The shipped chain is a linear 1-child ladder, so the **widest genuine sibling
fan** is at the ROOT (plan §2.3: one parent may form several child seeds). The
farm gate builds the root, then fans its condensed cores into `K=2` sibling
child branches (each zooming a different parent core into its own φ⁴-finer
box), runs them **in parallel**, and byte-compares against the **serial**
reference of the same siblings.

| metric | value |
|---|---|
| sibling branches fanned | 2 (children of the same root) |
| serial wall-clock | 20.7 s |
| parallel (2 workers) | 11.4 s |
| **speedup** | **1.81×** (near-linear for 2 siblings; real overhead) |
| farmed surveys byte-identical to serial | **True** (same seeds) |

The replayability contract (G24 discipline) **holds under parallelism**: the
farmed sibling surveys are byte-identical to the serial ones. This is the D5
contract exercised on genuine siblings — parallelism ACROSS the tree, never
inside a single level's solve.
