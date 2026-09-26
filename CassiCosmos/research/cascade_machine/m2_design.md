# Stage M2 — N-Level Offline φ-Cascade Tree (parent → child chain)

**Status:** Design + runnable orchestrator (`run_cascade_tree.py`), gate harness
(`gates_m2.py`), falsifier ledger (`falsifier_ledger.py`). Built on the M1
two-level prototype (gates G42–G46 PASS).
**Repo:** `godot/space-sim` (research/cascade_machine/ — OFFLINE numpy, no
.gd/.glsl edits; the sim battery is untouched).
**Date:** 2026-08-14
**Companion:** `m2_report.md` (the measured tree, per-level costs, gate table).

M2 = the N-level offline cascade tree: a ladder of short, each-own-periodic-solve
levels, φ-spaced (never N/2), parent levels condensing via Stage-3 machinery and
children ingesting the parent survey dirs as ICs. It generalizes the M1
two-level handoff (D3, D4) into a 49-level chain that runs END-TO-END unattended
with checkpoint/resume, a replayable registry, rung-integrity at every handoff,
a per-band falsifier ledger, and a calibrated P(k) log-periodicity search.

---

## 1. The level model (the measured ladder) and the D-ledger

### 1.1 Rung math and the honest level count

The physical reach (theory table §1.1, `dimensionful-cascade.md` §3) is
proton n=95 → supercluster n=288 = **193 φ-rungs**, verified:
`log_φ(ℓ_sc/ℓ_proton) = log_φ(2.5e25 / 1.3e-15) = 192.8 ≈ 193`.

**D-M2-1 — 4 rungs per level, 49 levels.** Each level advances `R = 4` rungs:
the child's box is `φ⁴` finer (`L_child = L_parent / φ⁴`), so its resolved band
sits 4 rungs lower on the absolute ladder while re-resolving the parent's
finest rung (1-rung band overlap — the M1 handoff principle). `⌈193/4⌉ = 49`
levels cover the reach. The plan's "~51 levels" (§1.2) derives from its own
354-rung figure (`354/7 ≈ 50.6`), which §8 is explicit is the machine's *own
spec* — the physical reach is 193 rungs, so 49 is the honest count. This is a
spec choice, reported transparently, not a silent change.

**D-M2-2 — uniform N=64 fixed box** (plan D6). The level's box side is the only
thing that changes; the structure radii (in units of the cell) are the SAME
φ-spaced band at every level (`R_CELLS = [7.68, 4.74, 2.94]` cells = stage3's
{1.2, 0.74, 0.46} at h=0.15625). Because the two-fluid PDE is scale-invariant
(φ-anchored), a level at box L reproduces the stage3 condensation verbatim, and
the rung anchor `n = log_φ(ℓ_struct/ℓ_Pl)` is what advances with L.

### 1.2 Level boxes and the run order

The chain is run **coarse→fine** (the M1 parent→child direction): level 0 =
supercluster (largest box, n=288), descending to the finest (proton band,
n≈96) at level 48. Each level's anchor rung `n_lev = 288 − 4·lev`, box
`L = (N/r_cells_max)·ℓ_Pl·φ^n` (so the 7.68-cell structure sits at rung n).

| level | rung anchor | window | box (m) | archetype |
|---|---|---|---|---|
| 0 | 288 | 288–282 | 2.1e26 | supercluster (top) |
| 7 | 260 | 260–253 | 9.5e21 | cluster |
| 12 | 240 | 240–233 | 1.9e16 | galaxy |
| 24 | 192 | 192–185 | 1.8e6 | molecular? (mid-ladder) |
| 41 | 124 | 124–117 | 3.3e-2 | atomic |
| 48 | 96 | 96–89 | 1.6e-14 | proton (bottom) |

Every level is its **own periodic solve** on its own box (multigrid §(c));
no patch, no coarse-supplied BCs. The φ-spacing (φ⁴ ratio between boxes) is
gcd-decorrelated and never N/2 — the de-resonance inherited from G38–G41.

### 1.3 The parent→child edge (D3) — the handoff

**D-M2-4 — the child is a single-core zoom.** The child reads the parent's
survey dir, takes the parent's MOST-MASSIVE condensed core, and seeds a
φ-spaced blob shell centered on that core's child-frame position (the M1 map:
`child_coord = (parent_coord − parent_centre)·φ^R + child_centre  mod box`).
The handed core MASS is conserved on the deposition remap (≤1e-6, M1 G42):
the child's amplitude `A_cons = m_handed/(κ·B2)` with `κ = m_handed/(A_parent·B1)`
and B1/B2 the parent/child anchor-gaussian supports. The child then RUNS at the
physical amplitude `A = 0.5` (the two-fluid strength), so the structure gates
are not distorted.

**Mass encoding (honest overflow fix).** At supercluster scale the absolute
core masses are ~1e77 — absolute values overflow float32, the survey format's
width (M1 `particles_mass.raw` is float32 LE). M2 stores the **dimensionless
mass-ladder rung** `n = log_φ(m/m_cell)` in `particles_mass.raw` (bounded, the
honest cascade quantity), with `m_cell` and `mass_encoding` in meta.json so
absolute mass reconstructs as `m_cell·φ^n`. This is the honest overflow-free
carrier of the exact same physics. (`survey_read.py` G24 does not read
`particles_mass.raw`; G24's byte contract is on `field_ey.raw` etc., unchanged.)

**D-M2-5 — CLOSURE IS OUT OF M2 SCOPE.** The closure artifact does not exist
(closure wave 2 was an honest negative: bare coarse still wins, scale-invariance
negative). The closure slot is a **documented no-op in the registry** (R1
insert-later), and M2's rung-integrity check runs WITHOUT it. Stated explicitly
so nobody reads a closure-gated result where there is none.

### 1.4 The tree registry (D6 / plan §2.3)

The tree is persisted as a directory registry under `cascade_tree/`:
`tree_registry.json` (nodes + condensation edges + progress + status) and one
`level_<i>_r<n>/` node dir per level holding the byte-exact survey
(`field_ey/ei/q.raw`, `particles.raw`, `particles_mass.raw`, `meta.json` with
`level:`/`parent:`/`rung_anchor`/`seed`/`closure_slot`) plus `run_state.json`
(checkpoint), `rung_score.json`, `pk.json`. The tree is offline-first (no node
depends on another's in-memory state) — replayable and auditable.

### 1.5 D-M2-7 — the CFL time-step homothety (measured, load-bearing)

The M1/stage3 reference (box L=10, dt=0.005, 80 steps) is the identity of the
ladder. But at FINER boxes (L<10) a FIXED dt violates the two-fluid wave CFL:
`ω_max·dt ∝ N/L` grows as the box shrinks, and levels below ~n=168 exploded
(fields → ±∞, r_end→negative, 0–1 cores — measured in the first full run at
levels 34–36). The honest fix is the time-step homothety of the scale-free
ladder: the resolved band is identical in cells at every level, so the same
*number of structure-crossing times* is covered by scaling `dt ∝ L`:

```
dt_lev = DT × min(1.0, L/10)      # DT = 0.005 at the L=10 reference
```

- For L ≥ 10 (coarse levels 0→~30) dt is capped at the reference: the breathing/
  restoring term bounds it from above, and the wave CFL is trivially safe.
- For L < 10 (fine levels, including the proton end) dt shrinks with L, holding
  `ω_max·dt` constant so the SAME resolved band stays stable. Measured: levels
  34–48 now run at 5–6 cores, r_end→φ (1.591, 1.7% off the attractor), rung
  scores 0.81–0.91, instead of exploding.

This is a numerical-stability necessity of the scale-free ladder, not a physics
fudge — a level resolves its own formation epoch (D-M2-3); the physical time
covered scales with the level's size, exactly as the plan's "formation epoch"
model requires.

---

## 2. The gates (G47–G50) and what they measure

| Gate | Acceptance | Disciplines reused |
|---|---|---|
| **G47 (M2.1)** | tree runs end-to-end unattended (one command) AND checkpoint/resume works (replay skips completed levels) | M1 orchestrator pattern |
| **G48 (M2.2)** | any subtree re-run under the same seed → byte-identical survey output | G24 byte discipline |
| **G49 (M2.3)** | mass-ladder integers survive every level (uniform-baseline rung_score ≥ 0.70 AND ≥3 cores; φ arm beats a non-φ control by >+0.10) — run WITHOUT the closure slot | Stage-3 G8 uniform baseline |
| **G50 (M2.4)** | P(k) log-periodicity search at Δln k = ln φ across levels, calibrated null (linear cos/sin basis, ω-specificity percentile); honest presence-or-absence | logperiodicity-test-calibration |

### 2.1 The rung-integrity statistic (G49)

`rung_score` is the Stage-3 G8 statistic verbatim: the offset-invariant median
distance of `(log_φ(m/m_cell) − n_min)/3` from integers over **ALL** formed
cores — a **uniform baseline**, never a highlight-pick. M2 requires
`rung_score ≥ 0.70` (the M1 G43 bar) AND `≥ 3` cores at every level, plus a
same-level non-φ control (same total excitation mass, random log-uniform
radii) whose score must fall > 0.10 below the φ arm.

### 2.2 The P(k) log-periodicity test (G50)

For each level, radial-average the density field's power spectrum into 1D
P(k); test for log-periodic modulation at `ω₀ = 2π/ln φ ≈ 13.06` in the linear
cos/sin basis (NO phase search — honest 2 oscillation params), and report the
**ω-specificity percentile** `p = P(ΔAIC(ω) ≤ ΔAIC(ω₀))` over a grid of other
fixed frequencies. A real signal requires `ΔAIC < −2` AND `p < 0.05`. This is
the calibration from the logperiodicity-test-calibration skill, reused, not
reinvented — it catches the "smooth U-shaped data fits ANY fixed frequency"
trap.

### 2.3 The farm (D5) and checkpointing

Parallelism is **across the tree** (sibling branches), never inside a single
level's solve (the PDE is one box). The orchestrator exposes a real
`farm()` executor over independent whole-level nodes and demonstrates it on
genuine sibling nodes (the archetype rung-control re-runs), reporting the
measured wall-clock with N workers. Checkpoint/resume: each node writes
`run_state.json` with a `done` flag; a killed run resumes by skipping done
levels. The build order is a strict dependency DAG (child → parent must exist).

---

## 3. Honest limits (M2)

- **NumPy prototype, no GPU.** Same honesty as M1: the correct proof is the
  handoff/ladder/cascade, not the performance path. The GPU port is later.
- **Single-core zoom.** Each child zooms ONE parent core (the most massive).
  A multi-core / full-field fan (the plan's many-to-many tree §2.3) is the
  farm-capable extension; M2's farm executor is the machinery, exercised over
  genuine sibling nodes, but the shipped tree is a chain (a valid degenerate
  tree, offline-first §2.3).
- **The 1.3–1.7 ring-anisotropy floor** (both levels, r=13–30) is NOT fixed by
  the ladder (multigrid Honest-limits); nothing converts it into a spurious
  rung "hit" — the uniform-baseline nulls (§8) keep the ledger honest.
- **P(k) honest null.** The M2 levels' density-field P(k) is dominated by the
  smooth φ-spaced blob envelope; the calibrated log-periodicity search reports
  the honest measured ΔAIC + ω-specificity per level (a null is a result, not
  a failure).
- **Closure slot no-op.** The rung-integrity gate runs WITHOUT the closure;
  R1's transfer test is future work, gated after a closure artifact exists.
- **The 51-vs-49 level count** reconciliation is §1.1's D-M2-1; the ladder
  covers the FULL 193-rung proton→supercluster reach.
