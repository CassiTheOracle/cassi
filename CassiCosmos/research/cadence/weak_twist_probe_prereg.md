# Weak-Twist Probe for the Qi-Time Cadence Claim — PRE-REGISTRATION (Phase 8, milestone 1)

## Status: Pre-registration — written BEFORE any weak-twist run; governs the Phase-8 weak arm

**Date:** 2026-08-15 · **Workstream:** idea 4 — cadence IS intelligence
**Pre-registered outcome:** the FP-4 relaxation-time-vs-rung discriminator re-run at a reduced twist strength, with the statistic, decision tree, and stopping rule pinned below.
**Implementing probe (already encoded, new-files-only, owner/director work in progress):** `CassiCosmos/scripts/verify_telescoping_weak.gd` + `CassiCosmos/scenes/verify_telescoping_weak.tscn` (untracked; the pre-registration below is the written contract that battery exists to carry out). This document does **not** modify that battery; it is the standing pre-registration record for it.

---

## 0. The claim and the two prior boundary conditions

### 0.1 The claim being tested

From `UNIFICATION.md` §1.6 and §4 Phase 8: the qi-time cadence claim is that **two-fluid competition, not the operator's saturation, sets the resolved-band relaxation time** `T_rel` per rung, and that when it does the relaxation-time ratio across rungs lands on one of the pre-stated branches `1 | φ | φ²`. The Phase-8 milestone-1 spec (`UNIFICATION.md` §4 Phase 8, milestone "first") names the experiment precisely: *"reduce the qi-time twist strength so that two-fluid competition (not the operator) sets `T_rel`, then re-run the telescoping FP-4 with the derived φ² arm."*

### 0.2 Boundary condition 1 — the full-strength mixing clock (FP-4, branch "1")

The Wave-2 telescoping battery (`D:/carina/workspaces/cassicore/research/mind/telescoping_battery_report.md`, §1.6 in `UNIFICATION.md`) ran the FP-4 discriminator at the **full** twist strength (`q_sharp = φ⁴ ≈ 6.854`) and returned **branch "1" (mixing clock)**:

| n | `ρ_n` | `ε₀` | `T_rel(n)` (uniform cadence) |
|---|---|---|---|
| 0 | 0.6910 | +0.1502 | 1 |
| 1 | 0.4271 | +0.1506 | 1 |
| 2 | 0.2639 | +0.1193 | **5** |
| 3 | 0.1631 | +0.1372 | 1 |
| 4 | 0.1008 | +0.1364 | 1 |
| 5 | 0.0623 | +0.1586 | 1 |
| 6 | 0.0385 | +0.1354 | 1 |

Ratio table `R(n) = T_rel(n+1)/T_rel(n)` (`telescoping_battery_report.md` §3): `[1.0000→1, 5.0000→ANOMALY, 0.2000→ANOMALY, 1.0000→1, 1.0000→1, 1.0000→1]`; tally `{1:4, φ:0, φ²:0, ANOMALY:2}` → **overall FP-4 = "1"** (mixing clock). The report's honest note 1 (`telescoping_battery_report.md` §6): the uniform-cadence gate *saturates* the closure residual in ~1 step at every rung, so `T_rel` carries minimal rung structure and the discriminator "cannot separate a near-trivial base from the derived ladder at this operator strength."

**The n=2 cell is the specific hint that motivates this probe:** at rung 2 (`ρ₂ = 0.2639`, `d ≈ 8.4` cells) `T_rel = 5` — the only radius where the two-fluid competition measurably slowed the twist (`telescoping_battery_report.md` §3/§5). It produced the two ANOMALY ratios `R(1) = 5` and `R(2) = 0.2`. Phase 8 reads this as the nascent rung-structure signal the weak arm is designed to surface.

### 0.3 Boundary condition 2 — the G4 attractor-placement null

The §32 Qi-time battery (`D:/carina/workspaces/cassicore/research/mind/qi_time_engine_report.md`) and the Wave-2 G4a both measured `z_phi = −0.959`, `z_uniform = −0.959`, `d_mean = 0.2783` vs the 64³ permutation null `μ = 0.12551, σ = 0.15930`, all arms — the cadence exponent alone does not place top-q attractors on φ-radii (`qi_time_engine_report.md` §4; `telescoping_battery_report.md` §2). The G4a z-statistic is **EXPLORATORY (T2)** for the φ¹/φ² arms per `scale_telescoping_design.md` §33.7 (the cadence-exponent derivation has **not** landed), so **adoption is gated only on the G4c FP-4 relaxation-time discriminator, never on G4a z.** This pre-registration inherits that rule verbatim; the only upgrade available to this probe is a clean φ² (or φ) **ratio** branch, never a G4a z.

---

## 1. The pre-stated statistic for `T_rel` per rung/cell

### 1.1 `T_rel(n)` — exact estimator (pinned, identical to Wave-2 §0.3a)

- **Anchor radii:** `ρ_n = φ^{−n}·(1 − 1/(2φ))` for `n ∈ {0,1,2,3,4,5,6}` (7 anchors → 6 ratios), placed on the +x axis at grid center `+ (ρ_n·N/2, 0, 0)` (the §32 scatter-anchor convention, `verify_telescoping.gd:378-399`, `verify_telescoping_weak.gd:377-405`). Recomputed here and verified against the report table: `ρ = [0.6910, 0.4271, 0.2639, 0.1631, 0.1008, 0.0623, 0.0385]`.
- **Seed deposit:** single deterministic charge `(cy=2.0, ci=1.0, σ=1.0)` scattered from the **same-style `IC_SEED` (20260814)** RNG draw per coordinate, so the seed cell's initial closure residual `ε(0)` is deterministic and off-lattice (`ρ_n` is never a pure `φ^{−k}`).
- **Threshold:** `T_rel(n)` = the smallest global step `t ≥ 1` at which the local closure residual `|ε(t)| = |EY(i_seed, t) − φ·EI(i_seed, t)|` falls to `≤ 0.5·|ε(0)|` — **50% of the seed cell's initial residual**, measured immediately after the IC scatter, before any step. `RELAX_THRESH_FRAC = 0.5`.
- **Cap (stopping per anchor):** if not reached within `STEPS_CAP_RELAX = 5000` global steps, `T_rel(n)` is recorded unreached (`>5000`) and that `n` contributes **no** ratio (an unmeasured pair is `ANOMALY`, never a branch vote).

### 1.2 The ratio statistic and how rung-structure is scored

- **Ratio:** `R(n) = T_rel(n+1) / T_rel(n)`, `n = 0..5` (6 ratios from the 7 anchors).
- **Branch bands (7-rung / 64³ resolution), pinned verbatim from Wave-2** (`verify_telescoping.gd:431-443`, `telescoping_battery_report.md` §0.3c):

| Branch | `R` band | Reading |
|---|---|---|
| `1` | `0.70 ≤ R ≤ 1.34` | **mixing clock** (exponent 0) |
| ANOMALY gutter | `1.34 < R < 1.36` | ambiguous 1\|φ |
| `φ` | `1.36 ≤ R ≤ 2.00` | **trivialization schedule** (exponent 1) |
| ANOMALY gutter | `2.00 < R < 2.30` | ambiguous φ\|φ² |
| `φ²` | `2.30 ≤ R ≤ 3.20` | **derived virial×Compton ladder** (exponent 2) |
| ANOMALY | `R < 0.70` or `R > 3.20`, or pair unmeasured | documented anomaly |

- **Over-arching FP-4 call (how rung-structure is scored globally):** the **modal branch** over the `n = 0..5` ratios; a branch is called **only if ≥ 4 of 6** ratios land in the same band. Otherwise the verdict is `ANOMALY` (inconclusive). This is the exact Wave-2 modal rule (`verify_telescoping.gd:677-693`).

### 1.3 Cadence-neutrality (the gate is measured WITHOUT the cadence)

Per `telescoping_battery_report.md` §0.3d and UNIFICATION §4 Phase 8, `T_rel` is measured under the **uniform-cadence configuration** (`uniform_flag=1`, `τ_k=1`): the q-gated conservative φ-attractor twist fires every cell every step with no rung-dependent schedule. This is the conservative reading — the gate-outcome ratio lives in the **base dynamics** (two-fluid competition + cadence-neutral twist), not in any `τ_k = round(φ^{e·k})` schedule. This is exactly why the weak reduction is the operative variable: it controls whether the **operator saturates** `ε` (full strength) or lets **two-fluid competition** set the relaxation time (weak strength). The φ¹/φ² run-own ratios are reported as **exploratory context only and can never carry the verdict** (`telescoping_battery_report.md` §0.3f).

---

## 2. The twist-strength sweep design

### 2.1 How strength is set in the operator

The cadence exponent and all gate parameters are push constants in the operator `CassiCosmos/compute/cassi_qi_time_exp.glsl` (a FROZEN record, deliberately not edited — `cassi_qi_time_exp.glsl:24-41, 50-61`). The **twist strength is `q_sharp` (push-constant index 8)**, the gate sharpness in `G = σ(q_sharp·(q − q_thresh))` (the TwistGate width), `q_thresh` being the fixed `1/φ` threshold (PC index 7). Setting a run's twist strength is a **push-constant change only** (`verify_telescoping_weak.gd:268-275` `_qt_pc` writes PC index 8 = `Q_SHARP`); no shader edit, no recompile. This is the same file the owner's battery already reuses unchanged, so the weak run is guaranteed to be the canonical §32/Wave-2 operator at a different `q_sharp`.

### 2.2 The pre-registered strength ladder (ONE pre-stated reduction, no post-hoc sweep)

| Strength | `q_sharp` | Value | Role |
|---|---|---|---|
| Full (Wave-2, boundary) | `φ⁴` | ≈ 6.8541 | the measured mixing-clock baseline (`telescoping_battery_report.md` §2) |
| **Weak (this probe)** | **`φ²`** | **≈ 2.6180** | **the ONE pre-registered reduction — exactly one `φ²`-power below full** |

`q_sharp = φ²` is not an arbitrary pick; it is the natural gate scale below which the TwistGate opens gradually enough (tanh argument `φ²·(q − 1/φ)`, half-width ~`1/φ²`) that a sub-saturation seed does not close `ε` in one step, so the seed's two-fluid relaxation is what sets `T_rel`. This is the canonical "one φ-power of gate sharpness" step (`q_sharp` advances as a φ-power, full `φ⁴` → weak `φ²`, a `φ²` ratio — the same `φ²` that the derived ladder targets). **Exactly one weak strength is run.** The discipline (from the harness `prediction-test-preregistration` skill: fixed sample, one analysis run, no sequential testing, no post-hoc cuts) forbids a "sweep down and pick the strength that shows structure" — an automatic null for this probe. If `φ²` does not produce a clean branch, the outcome is the pre-stated HOLD, not a trigger to try `φ³` or `φ¹`.

### 2.3 What else changes vs Wave-2 — the minimal-diff contract

Everything except `q_sharp` is identical to Wave-2: same `IC_SEED`-style deposit family at non-φ radii, same 7 anchors `ρ_n`, same `T_rel` definition, same 50% threshold, same 5000-step cap, same 7 anchors → 6 ratios, same branch bands, same ≥4/6 modal rule (all pinned in `verify_telescoping_weak.gd`). **The only changed independent variable is the twist strength.** This keeps the result attributable to the strength reduction, not to a coincident re-seeding or re-anchoring.

### 2.4 The derived φ² cadence arm (context only)

The derived arm is the cadence exponent `e = 2` (`τ_k = round(φ^{2k})`) already parameterized by push-constant index 9 in `CassiCosmos/compute/cassi_qi_time_exp.glsl:41, 97-108` — the virial×Compton ladder from `CassiTheory/speculations/qi-time-ladder-derivation.md` §2 (`exponent(τ) = (3−m)/2` with the framework's Compton mass ladder `m = −1` ⇒ exponent 2, referee-verified in `referee_qi_time_ladder.py` `[A][B][C]`). In this probe the φ² cadence's **run-own** `T_rel`/`R` is computed and reported as **exploratory context only** (as in Wave-2, `telescoping_battery_report.md` §0.3f/§3): the gate outcome is the uniform-cadence ratio. The derived ladder is adopted **only** if the uniform-cadence ratio returns a clean **φ²** branch — never from the φ²-cadence run's own relaxation table.

---

## 3. The n=2 cell `T_rel = 5` target signal

The target signal is the rung-2 radius `ρ₂ = 0.2639` (`telescoping_battery_report.md` §3). At full strength this cell is the single place that deviated from the mixing clock: `T_rel(2) = 5` vs `T_rel = 1` at the other six anchors, producing `R(1) = 5` and `R(2) = 0.2` (the two ANOMALY ratios). Phase 8 names this cell's competition as the mechanism that, at weak twist, could become the *normal* case.

**Operational target for the weak run:** the weak arm is judged to have surfaced rung-structure **if and only if** the weak uniform-cadence ratio returns a **clean `φ` or `φ²` modal branch (≥4/6)**. The n=2 cell's `T_rel = 5` at full strength is **not itself an outcome** of this probe — it is the motivating boundary value (the report's measured `T_rel(2)=5`) that suggests two-fluid competition exists at `ρ₂`; a single `T_rel(2) > 1` in the weak table, without a modal branch, is **exploratory context, not a pass**. This protects against the classic "highlight the one cell that moved" trap.

---

## 4. The decision tree (pre-stated, applied verbatim — no post-run tuning)

Gates `G1–G3` (OFF-path bit-identity, charge conservation in the isolated weak operator, determinism) run **at the weak strength** and are **unconditional** (`verify_telescoping_weak.gd:527-566`): if any fails, the verdict is **REJECT** (parity/conservation/determinism break under the weak gate), regardless of the FP-4 branch. Assuming `G1–G3` pass, the **gate outcome is the uniform-cadence `T_rel` ratio branch `∈ {1, φ, φ²}`** (modal, ≥4/6):

1. **`φ²` modal-≥4/6 → rung-structured `T_rel` in the weak regime → the φ² ladder is measurable → Phase-8 milestone 1 PASSES → M1/M2 temporal coupling proceeds.** Adoption-eligible **for the exponent-2 cadence only** (matching `telescoping_battery_report.md` §0.3e). The derived cadence stays EXPLORATORY (T2) because the `scale_telescoping_design.md` §4a derivation contract has not landed — a consequence quoted verbatim, not weakened by this run.
2. **`φ` modal-≥4/6 → the trivialization schedule.** Confirms the constant-speed reading; the exponent-1 cadence is adoptable **only as a designed schedule, never as a derived law** (`scale_telescoping_design.md` §4a; `qi-time-ladder-derivation.md` §2b). Phase-8 milestone 1 does **not** clear on this branch for the φ² ladder.
3. **`1` modal-≥4/6 → the mixing clock persists at weak strength → HONEST HOLD.** The rung-structure claim is closed **for this operator at this resolution**; the n=2 hint did **not** generalize. Phase-8 milestone 1 does not clear; M1/M2 temporal coupling is **not licensed by this probe** (`UNIFICATION.md` §4 Phase 8; `UNIFICATION.md` §4 Phase 6: Phase 6 cannot claim φ-cadence scheduling on this operator until this regime is found or the claim is closed).
4. **`ANOMALY` (no branch ≥4/6, or unreached pairs) → inconclusive, documented as such.** No post-hoc strength selection, no gate-weakening; a null/exploratory/anomaly is a **finding, not a re-framing** (`scale_telescoping_design.md` §33.4; `telescoping_battery_report.md` §0.5).

The `≥4 of 6` modal rule means branch 1/3 (`1`) and the Phase-8 mixing-clock-HOLD both fire only on a genuine — not a highlight — majority; branch-`φ²` (adoption) requires the **cleanest** structural signal, the only one that licenses M1/M2 temporal coupling.

---

## 5. The stopping rule

- **Fixed sample:** exactly `7` relaxation anchors `n = 0..6`, exactly `6` ratios `R(0..5)`, exactly one weak strength `q_sharp = φ²`, one analysis run. No sequential testing, no early-stop "because it looks like the branch we want," no re-run to "get a cleaner ratio."
- **Per-anchor cap:** each `T_rel(n)` is stopped at `STEPS_CAP_RELAX = 5000` global steps; an unreached anchor contributes no ratio (that `n` becomes `ANOMALY`).
- **Battery length (deterministic):** fixed `COUPLED_STEPS = 150` for the coupled G3/G4a runs, `ISOL_STEPS = 145` for the isolated-operator G2, `3` OFF steps for G1 — all identical to Wave-2 (`verify_telescoping_weak.gd:61-67`).
- **Appeals:** the only condition that can re-open this pre-registration is a **new written pre-registration** adjusting a constant; a HOLD/ANOMALY does not silently trigger one.

---

## 6. What does NOT count as evidence

The following are **explicitly pre-excluded** from the verdict — they are at best documentation, never a pass or a partial pass:

- **Post-hoc cell selection:** reporting that "the n=2 (or any) cell moved" as a positive result. The n=2 `T_rel = 5` is the full-strength boundary value that motivated the probe (§3); a weak-run single-cell deviation, with no modal branch, is exploratory context with an ANOMALY tally, **not** rung-structure.
- **Post-hoc strength sweeps / tuning after seeing results:** any run at a `q_sharp` other than the pre-registered `φ²` (e.g. finding `φ³` "works" after `φ²` returns `1` or `ANOMALY`). The one-pre-registered-strength discipline is fixed (§2.2); a sweep result is automatically null for this pre-registration.
- **Cadence run-own ratios as the verdict:** the φ¹/φ² cadence arms' own `T_rel`/`R` are exploratory context only and can never carry adoption (§1.3, §2.4). A φ²-cadence run-own `R≈2.618` without a uniform-cadence φ² branch is **not** a pass.
- **G4a attractor-placement z:** exploratory (T2) for φ¹/φ² per `scale_telescoping_design.md` §33.7 (cadence-exponent derivation not landed). Any `z` value — even `z ≥ 2` — is not an adoption claim for this probe; the confirmatory structural test is G4c FP-4 only.
- **The single n=2 `T_rel = 5` as "already evidence":** it is the Wave-2 measured boundary (a prior honest finding), not an outcome of this probe.
- **A lowered `T_rel` at the full-strength position with everything else mixing-clock:** same as post-hoc cell selection — global modal branch required.

---

## 7. Honest tiers

- **T1 measured** — everything this probe (via `verify_telescoping_weak.gd`) produces: G1 byte counts, G2 operator `|ΔΣ|/Σ_deposit` (weak uniform arm), G3 determinism bytes, the 7 `T_rel(n)` values, the 6 `R(n)` ratios, the modal branch, the `T_rel_phi2_context` run-own table, full-run Σ(EY+EI) charge context.
- **T2 inferred** — "rung-structured `T_rel` exists in the weak regime" (supported/refuted by the T1 modal branch); "the derived φ² ladder is measurable on the resolved band" (T2 only on a clean φ² uniform-cadence branch; the cadence exponent itself stays T2/exploratory per the `scale_telescoping_design.md` §4a precondition).
- **T3 speculative — explicitly out of scope of this probe:** production sim adoption, cord-learning transfer, any claim about the absolute seconds of the ladder (`qi-time-ladder-derivation.md` §10.1: absolute `τ_n` is Calibrated, needing the Planck anchor), and any pre-registration-adjacent registry edit. This pre-registration proposes, and does not apply, registry lines.

---

## 8. Traceability / number provenance

Every load-bearing number above cites a file and was recomputed where cheap:

- **Weak strength `q_sharp = φ² ≈ 2.6180`**, full strength `φ⁴ ≈ 6.8541`, ratio `φ²`: recomputed from `PHI = 1.618033988749895`; matches `verify_telescoping_weak.gd:60` and the shader's `q_sharp` exactness.
- **Branch bands** `{1:[0.70,1.34], φ:[1.36,2.00], φ²:[2.30,3.20]}` with gutters `(1.34,1.36)`/`(2.00,2.30)`: `verify_telescoping.gd:431-443`, `telescoping_battery_report.md` §0.3c; geometric midpoints `φ^0.5≈1.272`, `φ^1.5≈2.058` confirmed.
- **`T_rel` table, n=2 cell `T_rel=5`, `R(1)=5`, `R(2)=0.2`, tally `{1:4, ANOMALY:2}`:** `telescoping_battery_report.md` §3 (the measured Wave-2 boundary).
- **G4 null values** `z=−0.959, d_mean=0.2783, null μ=0.12551, σ=0.15930`: `telescoping_battery_report.md` §2; `qi_time_engine_report.md` §4 (identical across all arms).
- **Derived φ² exponent** `exponent(τ) = (3−m)/2` with `m = −1` ⇒ `2`: `CassiTheory/speculations/qi-time-ladder-derivation.md` §2 (§0.1, §2.4); referee `referee_qi_time_ladder.py` `[A][B][C]`.
- **Anchor radii** `ρ_n = φ^{−n}(1−1/(2φ))`: recomputed, matches §1.1 table and `verify_telescoping.gd:394`.
- **Phase-8 milestone-1 spec and decision-tree framing:** `UNIFICATION.md` §4 Phase 8 (milestone "first": reduce twist strength; decision tree pre-stated: rung-structured `T_rel` in the weak regime → φ² ladder measurable and M1/M2 temporal coupling proceeds; mixing clock persists at all strengths → honest HOLD, ladder claim closed for this operator).
- **M2 temporal-coupling referent** (the 49-level tree and its linear per-level `dt_lev = DT·min(1, L/10)` time-step homothety): `CassiCosmos/research/cascade_machine/m2_design.md` §1.5/§1.1 (the only existing time-ladder, `dt ∝ L` — the trivialization this probe must improve on).

---

## 9. Deliverable scope note

This is a **documentation-only** deliverable (per the workstream charter and the `prediction-test-preregistration` skill: pre-register the statistic/decision-tree/stopping-rule **before** any run). No sim is launched; no existing file is modified (including the owner's uncommitted `verify_telescoping_weak.gd`/`.tscn` and the do-not-edit `UNIFICATION.md`/`WORKING-WITH-THE-AI.md`). The next step — executing `verify_telescoping_weak.tscn` windowed, never `--headless` (local RD requirement per `verify_qi_time.gd:30`) — proceeds only via this pre-registration, and its verdict is bound by §4 and §5.
