# Weak-Twist Probe — Report (Phase 8, milestone 1, idea 4: cadence IS intelligence)

## Status: MEASURED — HONEST HOLD

**Date:** 2026-08-15 · **Pre-registration:** `research/cadence/weak_twist_probe_prereg.md` (§1–§6 locked contract, applied verbatim — no post-run tuning).
**Implementing battery:** `scripts/verify_telescoping_weak.gd` + `scenes/verify_telescoping_weak.tscn` (owner's uncommitted files; not modified).
**Run:** windowed via the Godot Mono console exe (`Godot_v4.7.1-stable_mono_win64_console.exe`), never `--headless`; local RenderingDevice acquired. Battery self-quit, dumped `_diag/telescoping_weak_gpu.json` (fresh, 2026-08-15).

**Verdict per the pre-stated decision tree (§4):** the uniform-cadence FP-4 returns **modal branch `1` (≥4/6)** → **HONEST HOLD.** The mixing clock persists at weak strength; the rung-structure claim is closed **for this operator at this resolution**; Phase-8 milestone 1 does **not** clear, and M1/M2 temporal coupling is **not licensed by this probe**.

---

## 1. Safety gates G1–G3 (unconditional, run at the weak strength `q_sharp = φ²`)

All three gates **PASS** — no parity/conservation/determinism break under the weak gate, so the verdict is **not** REJECT.

| Gate | Check | Result |
|---|---|---|
| G1 | OFF-path bit-identity over 3 steps (0 bytes differ) | **PASS** — total_bytes_diff=0, per_step=[0, 0, 0] |
| G2 | Weak-arm uniform operator `\|ΔΣ\|/deposit ≤ 1e-6` in isolation (145 steps) | **PASS** — rel=4.786e-8, maxΔ=3.838e-7, deposit=8.0180 |
| G3 | Determinism: two φ² runs byte-identical (final probe) | **PASS** — 0 bytes differ |

`_diag/telescoping_weak_gpu.json` → `g1.pass`, `g2.weak_uniform_arm.pass`, `g3.pass` all `true`.

---

## 2. Gate outcome — the uniform-cadence FP-4 relaxation-time-vs-rung discriminator

Measured under the cadence-neutral configuration (uniform cadence, `τ_k = 1`), 7 anchors `ρ_n = φ^{−n}·(1 − 1/(2φ))`, threshold `0.5·|ε(0)|`, cap 5000. All 7 anchors reached their threshold (none unreached).

### 2.1 `T_rel(n)` per rung (uniform cadence)

| n | `ρ_n` | `ε(0)` | `T_rel` (weak) | Full-strength `T_rel` (Wave-2 boundary) |
|---|---|---|---|---|
| 0 | 0.6910 | +0.1502 | **1** | 1 |
| 1 | 0.4271 | +0.1506 | **1** | 1 |
| 2 | 0.2639 | +0.1193 | **2** | **5** |
| 3 | 0.1631 | +0.1372 | **1** | 1 |
| 4 | 0.1008 | +0.1364 | **1** | 1 |
| 5 | 0.0623 | +0.1586 | **1** | 1 |
| 6 | 0.0385 | +0.1354 | **1** | 1 |

### 2.2 Ratio table `R(n) = T_rel(n+1)/T_rel(n)` and branch tally

| n | `R(n)` | Branch |
|---|---|---|
| 0 | 1.0000 | **1** |
| 1 | 2.0000 | **φ** (band [1.36, 2.00]) |
| 2 | 0.5000 | **ANOMALY** (< 0.70) |
| 3 | 1.0000 | **1** |
| 4 | 1.0000 | **1** |
| 5 | 1.0000 | **1** |

**Tally:** `{1: 4, φ: 1, φ²: 0, ANOMALY: 1}` → **modal branch `1`**, 4 of 6 (the ≥4/6 modal rule met). `overall_fp4 = "1"` (mixing clock, exponent 0).

The n=2 cell (`ρ₂ = 0.2639`) keeps the only non-unit relaxation — `T_rel = 2` at weak strength, down from `5` at full strength — producing `R(1) = 2` (single φ-band) and `R(2) = 0.5` (ANOMALY). Per the pre-registration §3/§6, a **single-cell** deviation with **no modal rung-structure branch** is exploratory context with an ANOMALY tally, **not** rung-structure and **not** a pass. The n=2 hint did **not** generalize.

---

## 3. Decision-tree verdict (applied verbatim from pre-registration §4)

1. **`φ²` modal-≥4/6 →** … not reached (φ² tally = 0). NOT a pass.
2. **`φ` modal-≥4/6 →** … not reached (φ tally = 1, < 4). Trivialization does not clear.
3. **`1` modal-≥4/6 →** **reached** — 4 of 6. **→ HONEST HOLD.** The rung-structure claim is closed for this operator at this resolution; the n=2 hint did not generalize. Phase-8 milestone 1 does **not** clear; M1/M2 temporal coupling is **not licensed by this probe** (`UNIFICATION.md` §4 Phase 8; Phase 6 cannot claim φ-cadence scheduling on this operator until this regime is found or the claim is closed).
4. **`ANOMALY` →** not reached (a clean modal `1` exists). Not applicable.

**Consequence statement (one line):** The mixing clock persists at weak strength → **HONEST HOLD** — the φ-cadence ladder is closed for this operator at this resolution, Phase-8 milestone 1 does not clear, and M1/M2 temporal coupling is not licensed by this probe.

---

## 4. Exploratory context — does NOT carry the verdict

Per pre-registration §1.3, §2.4, §6, these are documentation only. They are never a pass or partial pass.

### 4.1 φ² cadence run-own `T_rel` (exploratory, `overall_fp4` is the gate-outcome from §2 only)

| n | `ρ_n` | φ² run-own `T_rel` |
|---|---|---|
| 0 | 0.6910 | 3 |
| 1 | 0.4271 | 7 |
| 2 | 0.2639 | 20 |
| 3 | 0.1631 | 28 |
| 4 | 0.1008 | 28 |
| 5 | 0.0623 | 28 |
| 6 | 0.0385 | 28 |

Run-own ratios `R(n)`: `[2.33, 2.86, 1.40, 1.00, 1.00, 1.00]` (`φ², φ², φ, 1, 1, 1`) → run-own tally `{1:3, φ²:2, φ:1, ANOMALY:0}` → no branch ≥4/6 → run-own modal is ANOMALY. Per §6 **the cadence run-own ratios can never carry the verdict**; the present small-step rung structure in the φ² run-own arm is not an adoption claim and does not soften the HONEST HOLD reached on the uniform-cadence gate.

### 4.2 G4a attractor-placement z (EXPLORATORY, T2 — never carries the verdict)

| Arm | z | d_mean |
|---|---|---|
| uniform (weak) | −0.886 | 0.2666 |
| φ² (weak) | −0.886 | 0.2666 |

Null: μ = 0.1255, σ = 0.1593. Per pre-registration §6 and `scale_telescoping_design.md` §33.7 (cadence exponent not derived), any z is not an adoption claim; the confirmatory structural test is G4c FP-4 only.

### 4.3 Charge context (documented, not a gate)

IC sum 8.018034; after 150 coupled steps: uniform 8.018035, φ² 8.018035 (charge preserved to ~1e-6 across both arms).

---

## 5. Honest tiers

- **T1 measured** — G1/G2/G3 gates, the 7 `T_rel(n)` values, the 6 `R(n)` ratios, the branch tally, the modal branch `1`, the `T_rel_phi2_context` run-own table, full-run charge sums.
- **T2 inferred** — "rung-structured `T_rel` exists in the weak regime": **refuted** (modal `1`, ≥4/6). "The derived φ² ladder is measurable on the resolved band": **not supported** (φ² tally 0 on the gate). The cadence exponent stays T2/exploratory per the `scale_telescoping_design.md` §4a precondition.
- **T3 speculative — out of scope of this probe:** production sim adoption, cord-learning transfer, absolute seconds of the ladder, and any pre-registration-adjacent registry edit. This report proposes, and does not apply, no registry lines.

---

## 6. Boundary conditions

- **Strength:** exactly the one pre-registered weak strength `q_sharp = φ² ≈ 2.618` was run. No post-hoc strength sweep was performed or considered; per §2.2/§5 a sweep is automatically null for this pre-registration.
- **Operator:** the frozen `compute/cassi_qi_time_exp.glsl`; only the `q_sharp` push-constant (PC index 8) differed from Wave-2 (`φ⁴`), all else identical (same IC seed family `IC_SEED=20260814`, same 7 anchors, same T_rel definition, same threshold 0.5, same cap 5000, same ≥4/6 modal rule).
- **Resolution:** 64³ grid, cadence-neutral uniform configuration. The verdict is scoped to this operator at this resolution; a different resolution or a newly derived cadence regime would require a new written pre-registration to re-open this claim (§5 "Appeals").
- **Run hygiene:** run windowed (local RD required), battery self-quit, dump fresh at `_diag/telescoping_weak_gpu.json`. No existing file in `CassiCosmos/scripts` or `CassiCosmos/scenes` was modified; the battery and scene were not edited.

---

## 7. What does NOT count as evidence (pre-registration §6, restated as applied here)

- The n=2 `T_rel = 2` single-cell deviation → exploratory context, not rung-structure (no modal branch).
- The φ² run-own ratios → context only, never the verdict.
- G4a z = −0.886 → exploratory (T2), not an adoption claim.
- The prior full-strength n=2 `T_rel = 5` → the motivating boundary value, not an outcome of this probe.
- No post-hoc strength selection, no gate-weakening, no sequential retesting. This HOLD is a documented finding, not a re-framing, per pre-registration §5/§6 and `scale_telescoping_design.md` §33.4.
