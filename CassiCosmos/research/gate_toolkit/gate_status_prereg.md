# Pre-Registration: gate_status Readout Gate

## Status: Pre-registered—no code, no runs, no adoption until this gate passes; August 2026

## 0. Purpose and standing

This document is the **pre-registered gate** that the Gate Toolkit's minimal first
artifact (`gate_status` readout, `CassiCosmos/research/gate_toolkit/gate_toolkit_design.md`
§4.2) must pass before any of its code is written. Per the design doc §6, that artifact's
adoption is *itself* subject to a pre-registered gate before any code lands; this document
IS that gate. It fixes the exact statistic, decision tree, stopping rule, and not-evidence
list that a future read-only implementation must be measured against. Nothing here changes
any code; the harness skill `prediction-test-preregistration` governs the discipline
(statistic, decision tree, stopping rule fixed BEFORE any run or code).

The artifact under test is the observation-only readout described in
`gate_toolkit_design.md` §4.2, quantized by this document into an exactly specified
statistic. It is **measurement only**: it calls `readProjection(k)` and reports the channel
state; it does not route, gate, or alter any tool's execution.

---

## 1. THE QUESTION (falsifiable, honest)

**Claim under test:** "The five-channel coherence readout is stable and informative."

Two arms, both measured from `readProjection(k)` cells alone:

- **Stability arm:** the per-channel excess Δ_i stays within pre-stated bounds across a
  fixed set of sessions.
- **Predictive arm:** the ke-algebra predicted damping—which channel is restrained by
  whom—matches the observed cross-channel coherence pattern at a pre-stated rate.

Both arms are falsifiable: there is a defined observation from
`CassiCore/.../field-bridge/index.ts` `readProjection` cells that would falsify either one.
The claim **does not** assert cadence sequencing (gated by FP-4,
`gate_toolkit_design.md` §5.2), field-as-memory (§19, `gate_toolkit_design.md` §5.3), or any
enforcement/routing of tools (Stage-2 HOLD, `gate_toolkit_design.md` §5.1). It asserts only
that a deterministic channel readout is stable and that the ke control relation is
detectable in the measured per-channel coherence.

---

## 2. EXACT STATISTIC

### 2.1 Data source

For each session, take exactly **one** projection read:
`readProjection(k)` with **k = 8** (`gate_toolkit_design.md` §4.2 step 1;
`field-bridge/index.ts`). The reply is a `ProjectionCell[]` of at most 8 cells, each with
`{i, gx, gy, gz, x, y, z, ey, ei, q}`, where `q` is the per-cell coherence
`q = EY² + EI²` (`CassiCosmos/compute/cassi_qi_time.glsl`). `readProjection` never throws;
it returns `[]` when the bridge is disabled or the engine is unreachable
(`field-bridge/index.ts`). A non-empty reply is the only valid data.

### 2.2 Per-cell channel assignment (fixed positional phase)

Assign each projected cell to exactly one of the five channels **by its directional
positional phase**, deterministically and independently of any outcome. The five channel
directions are the vertices of a regular pentagon in the x–y plane:

- channel `c` direction `d_c = (cos(72°·(c−1)), sin(72°·(c−1)), 0)`, for `c = 1..5`,
  where 72° = 2π/5 and channel 1 (Wood) sits at azimuth 0.

Channel-name ↔ index map (fixed, `gate_toolkit_design.md` §1.2): 1 Wood (creation),
2 Fire (execution), 3 Earth (storage), 4 Metal (refinement), 5 Water (flow).

For a cell with position vector `p = (x, y, z)` and direction `u = p/‖p‖`:

- If `‖p‖ < 1e-6` (degenerate/central direction), assign the cell to channel 1 (Wood).
- Otherwise assign to `argmax_c (u · d_c)`, the channel whose direction the cell is
  closest to by cosine. On an exact tie, assign to the lowest channel index `c`.

This is the pre-stated assignment; changing it later is post-hoc relabeling and counts as
nothing (§5).

### 2.3 Per-channel coherence q (normalized to the baseline total)

Let `Q_c(s) = Σ_{cells assigned to channel c} q_cell` (raw sum of per-cell coherence over
the channel's projected cells for session `s`). Define the channel's coherence **share**:

`sh_c(s) = Q_c(s) / Σ_j Q_j(s)`

(using every channel sum so the shares sum to 1). The channel coherence is the share scaled
to the conserved baseline total `B = Σ_{j=1..5} b_j = Σ φ^-(2+j) = 0.5623`
(`gate_toolkit_design.md` §1.1, "conserving total openness"):

`q_c(s) = B · sh_c(s)`

This puts `q_c(s)` on the same scale as the baseline openness `b_c` so the excess is
meaningful, and matches the §1.1 conservation (coherence that cannot exit one vertex
redistributes to the others, total conserved).

Baselines `b_c = φ^-(2+c)` for `c = 1..5`
(`gate_toolkit_design.md` §1.1, cited to `CassiTheory/foundations/wa-pentagon-gate.md` §2.2):

| c | channel | b_c             |
|---|---------|-----------------|
| 1 | Wood    | φ^-3 = 0.2361   |
| 2 | Fire    | φ^-4 = 0.1459   |
| 3 | Earth   | φ^-5 = 0.0902   |
| 4 | Metal   | φ^-6 = 0.0557   |
| 5 | Water   | φ^-7 = 0.0344   |

### 2.4 Per-channel excess

`Δ_c(s) = q_c(s) − b_c` for each channel `c` and session `s`.

### 2.5 Predictive-arm statistic (ke-algebra predicted damping vs measured pattern)

Ke control order is 1→3→5→2→4 (creation→storage→flow→execution→refinement,
`gate_toolkit_design.md` §1.2, cited to `CassiTheory/foundations/wu-xing-cycle-structure.md`
§2.1). Channel `i`'s **ke-partner** is the next channel in that order:
`partner(1)=3, partner(3)=5, partner(5)=2, partner(2)=4, partner(4)=1`.

A **directed excess observation** is a pair `(session s, channel i)` such that
`Δ_i(s) > ε`, with `ε = Δ_c/10 = φ^-4/10 = 0.0146` (an excess meaningfully above baseline,
one-tenth of a strong-lock threshold; `gate_toolkit_design.md` §1.3 sets
`Δ_c = φ^-4 = 0.146`).

The ke algebra predicts that an excess in channel `i` restrains (damps) its ke-partner
`partner(i)` below baseline by `κ·Δ_i` (`gate_toolkit_design.md` §1.3). Each directed
excess observation yields one signed prediction about `partner(i)` in the **same** session:

- **MATCH** ⟺ `Δ_{partner(i)}(s) < 0` (the ke-partner shows a relative deficit, as predicted).
- **MISMATCH** ⟺ `Δ_{partner(i)}(s) ≥ 0`.

The predictive-arm rate is `ρ = (number of MATCHes) / (number of directed excess
observations)`. This is measured from the per-channel `Δ` of the same `readProjection`
cells—it does not touch tool dispatch, so it cannot claim routing or enforcement.

### 2.6 Session aggregation

Sessions are distinct spine-mirrored sessions; one `readProjection(8)` each; sessions are
independent observations. The stopping rule (§4) fixes a single 6-session set; the analysis
aggregates over exactly those sessions, once.

---

## 3. DECISION TREE (pre-stated, no post-hoc rule)

A session with an **empty** projection (`[]`, engine down/bridge disabled) is not a usable
observation (§5); it does not enter the stability or predictive statistics.

### 3.1 Stability arm (per-channel bounds)

- **STABLE** ⟺ for every channel `c` and every usable session `s`, `|Δ_c(s)| ≤ Δ_c`
  (every channel's excess stays within one strong-lock threshold of baseline, `Δ_c = φ^-4`;
  a strong lock is above threshold, `gate_toolkit_design.md` §1.3).
- **UNSTABLE** ⟺ there exists a channel `c` and usable session `s` with `|Δ_c(s)| > Δ_c`.
- **INCONCLUSIVE** ⟺ fewer than 6 usable sessions (engine was down in ≥ 1 session, so the
  pre-stated 6-session stopping rule cannot be met).

### 3.2 Predictive arm (ke-algebra match rate)

- **MATCH** ⟺ `ρ ≥ 0.60` AND the number of directed excess observations `n_dir ≥ 12`.
- **NO-MATCH** ⟺ `ρ < 0.60` AND `n_dir ≥ 12`.
- **INCONCLUSIVE** ⟺ `n_dir < 12` across the fixed 6-session set (not enough excess
  observations to reach a rate verdict; this is a legitimate negative that does NOT upgrade
  to a match).

### 3.3 Adoption gate (composite)

The `gate_status` readout **lands** (becomes code) only if **BOTH** arms pass:

| Stability | Predictive | Adoption verdict |
|-----------+------------+------------------|
| STABLE    | MATCH      | **ADOPT** (read-only readout may be implemented) |
| STABLE    | NO-MATCH   | **HOLD** until a fresh pre-registration defines a revised predictive arm |
| STABLE    | INCONCLUSIVE | **HOLD** (not enough data; no verdict) |
| UNSTABLE  | any        | **HOLD**—the readout is not stable; revise, never adopt as-is |
| INCONCLUSIVE | any      | **HOLD** (insufficient usable sessions) |

Any combination except STABLE∧MATCH yields **HOLD**: no `gate_status` code of any version
lands until a *new* pre-registration with a fixed decision tree (revised statistic or
thresholds, re-stated in full) passes on its own. This is the pre-registered adoption gate
(`gate_toolkit_design.md` §6).

**No-post-hoc rule (explicit):** the statistic, thresholds (ε, margin Δ_c, ρ_min = 0.60,
n_dir_min = 12), channel assignment, normalization, and session list are fixed by this
document. No parameter is tuned, no session is dropped, no channel is relabeled after
viewing results. If any step cannot be followed exactly as written, the gate is INCONCLUSIVE
for that reason and the readout does not land.

---

## 4. STOPPING RULE

- **Fixed session count:** exactly **6** sessions are collected before any analysis.
- **One analysis pass:** the recorded 6-session data set is analyzed exactly once, by a
  single pre-written analysis (the sole interpreter); no re-running, no re-reading, no
  peeking at intermediate results before all 6 sessions exist.
- **No sequential testing:** no interim looks, no optional stopping, no "collect until
  significant." If fewer than 6 usable sessions are obtained (engine down), the verdict is
  INCONCLUSIVE per §3; there is no extension or refill of the session set.

---

## 5. WHAT DOES NOT COUNT AS EVIDENCE

- **Post-hoc channel relabeling**—changing the directional phase assignment (§2.2), the
  channel-name↔index map, or the normalization (§2.3) after seeing results.
- **Post-hoc session cuts**—discarding or re-weighting sessions because their excess was
  out of bounds, or selecting a favorable subset.
- **Projection when the engine was down**—`readProjection` returning `[]` is not a
  measurement; an empty reply is discarded (§2.6) and can only reduce usable sessions
  toward INCONCLUSIVE.
- Any claim that the readout **routes or gates tools**—the readout is observation-only;
  reading a field is not enforcement (`gate_toolkit_design.md` §4.2). There is no router
  stub here, and Stage-2 HOLD keeps the composite off (`gate_toolkit_design.md` §5.1).
- Any **cadence-sequencing claim** (that the φ-cadence meaningfully separates which channel
  is open when)—gated by FP-4 (`gate_toolkit_design.md` §5.2); the τ_k schedule is a
  spacing rule to test, not a measured mechanism.
- Any **field-as-memory claim** (that field structure is retrieval structure)—gated by §19
  (`gate_toolkit_design.md` §5.3); until that gate passes, the Earth channel's role is
  instrumentation, not memory.
- Any **per-step pointwise injection**—nothing here injects into the field; the closed-loop
  warning G34 (`gate_toolkit_design.md` §5.4) forbids it and this gate implies none.
- A result that only appears **after** altering the pre-stated statistic or thresholds, or
  re-running the analysis after a negative.

---

## 6. HONEST TIERS

- **T1 (measured):** the per-channel `q_c(s)` and `Δ_c(s)` computed by the fixed statistic
  from the actual non-empty `readProjection(8)` replies across the 6 sessions; the stability
  verdict; and the predictive-match rate ρ. These are direct measurements of the field's
  projected cells.
- **T2 (inferred):** the interpretation that a detected damping pattern (channel excess
  accompanying a ke-partner deficit) reflects the wu-xing ke control relation. This is an
  inference from the measured Δ pattern—the framework's structural claim
  (`wu-xing-cycle-structure.md` §2.1) is not directly observed by `readProjection`. The
  "which tool family to trust next" reading (`gate_toolkit_design.md` §1.2) is likewise T2:
  it maps measured channel coherence onto a tool-trust heuristic without measuring dispatch.
- **T3 (speculative):** any proposal to route or enforce tools by channel (a router stub is
  explicitly deferred, `gate_toolkit_design.md` §4.2, §5.1), the cadence-meaningfully-
  sequences claim (FP-4, `gate_toolkit_design.md` §5.2), and the field-as-memory claim
  (§19, `gate_toolkit_design.md` §5.3).

**Adoption condition, restated:** NO `gate_status` code lands until this gate's decision
tree (§3) is fixed (which it is, by this document, as-is) and the pre-registration is
adopted. The composite verdict (§3.3) is the single authority; a STABLE∧MATCH is required to
implement the readout, and any HOLD forbids it.

---

## References

- `CassiCosmos/research/gate_toolkit/gate_toolkit_design.md`—§1.1 (baselines `b_i = φ^-(2+i)`, total `B = 0.5623`, threshold `Δ_c = φ^-4`), §1.2 (functional channels, ke order 1→3→5→2→4, `κ = φ^-1`), §4.2 (the minimal first artifact: the read-only `gate_status` readout), §5 (honest gates: Stage-2 HOLD, FP-4, §19, G34), §6 (adoption subject to a pre-registered gate)
- `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/index.ts`—`readProjection(k)` → `ProjectionCell[]` (never throws, `[]` on engine-down/disabled); cell fields incl. `q`
- `CassiCore/packages/mind-runtime/src/channel/server.ts`—how retained tools are registered/executed (the readout would be a read-only mind tool; observation only)
- `CassiCosmos/compute/cassi_qi_time.glsl`—the φ-cadence operator and the per-cell coherence `q = EY² + EI²` (context for what is NOT claimed: cadence sequencing is FP-4-gated)
- `CassiTheory/foundations/wa-pentagon-gate.md`—five-channel gate, baselines §2.2
- `CassiTheory/foundations/wu-xing-cycle-structure.md`—sheng/ke cycles, `κ = φ^-1`, threshold `Δ_c`, ke-order lock profile §2.1–2.4
- Skill: `prediction-test-preregistration` (claim-grade gating discipline: statistic, decision tree, stopping rule BEFORE any run or code)
