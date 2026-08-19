# Phase 3 — The Steering Loop: Pre-registration

## Status: Plan — pre-registered (2026-08-15), before any run

This document fixes the statistic, decision tree, and stopping rule for the
Phase-3 steering loop **before any steering run executes**. It is the pre-file
the plan requires (UNIFICATION.md §4 Phase 3; WORKING-WITH-THE-AI.md §2.4 / §2.3
discipline). No claim below is a measurement; every run's verdict lands in the
ledger appended to this file after `tools/field_steer.py` runs.

## 0. Context asserted, not argued

- The field is the computation; intelligence is the operator that steers the
  flow of coherence (WORKING-WITH-THE-AI.md §0).
- Read = readout/project; write = deposit (`cassi_mind_engine.gd` bridge, port
  7599). Coherence density per cell `q = EY² + EI²`; disequilibrium
  `ε² = (EY − φ·EI)²` (mind-engine `compute_readout`).
- Two measured negatives bound every steering design and are the baselines to
  beat (section 5):
  - **G34** — per-step pointwise injection degrades the integrated attractor
    ~10× (UNIFICATION §5.1, §4 Phase 4).
  - **FP-4 (G4c)** — at current twist strength the base field is a mixing
    clock; a loop that fires every step injects into noise (UNIFICATION §4
    Phase 8, Phase 3 Risk).
  - **Stage 5 REJECT** — the error-minimizer lost to predict-unchanged
    (floor 0.5571). Steering over prediction is the winning posture.
- Pre-registration discipline: statistic, decision tree, stopping rule fixed
  before any run; fresh solver per arm; no post-hoc tuning; NaN-loud-fail
  (WORKING-WITH-THE-AI.md §2.3).

## 1. Artifact under test

`CassiCosmos/tools/field_steer.py` — a Python controller over the mind-engine
bridge that closes the minimal loop: `readout` → predict (persistence baseline)
→ `deposit` the decided delta (TSC scatter at the target attractor), on a
**φ-cadence injection schedule (NOT per-step)**, with a strength ramp from 0 and
a hard stop on divergence.

The predictor is **persistence only** (predict-next = current, plus a
clearly-labeled steering policy — see §7). No CassiAI code is imported; nothing
from `CassiAI/` is used or referenced by the workstream.

## 2. Primary statistic: steering efficacy (increment framing)

Let a measurement window span `R` full readouts (one per cadence rung), indexed
`r = 1..R`, with `r = 0` the post-IC baseline readout.

Per readout `r` we compute, over the target attractor region `A` (a ball of
radius `r_A` cells around the target cell `T`, default `r_A = 1` — the TSC
27-cell stencil footprint), the target coherence

```
Q_A(r) = Σ_{i ∈ A} q_i(r),    q_i = ey_i² + ei_i²
```

where `ey_i, ei_i` are the decoded readout fields (x-major flat index
`i = gx·N·N + gy·N + gz`).

Define the **steered delta** (target coherence gained between rung readouts):

```
ΔQ_steered(r) = Q_A(r) − Q_A(r−1)
```

and the **injected charge** (the coherence we wrote in during that interval —
the steering cost):

```
Δdeposit(r) = Σ_{deposits in interval r} ( |cy| + |ci| )
```

**Primary statistic — total target coherence built beyond doing-nothing:**

```
G_cad = Σ_{r=1..R} ΔQ_steered(r)        (the steering arm's build)
G_0   = Σ_{r=1..R} ΔQ_0(r)              (control build, no injection)
σ_ΔQ  = std( ΔQ_steered(r) )            (margin across the arm's valid rungs)
```

**Secondary statistic — per-unit leverage (dimensionless):**

```
S = Σ ΔQ_steered / ( Σ Δdeposit + ε_charge ),   ε_charge = 1e-9
```

the total target coherence bought per unit of injected coherence. S is
dimensionless (both numerator and denominator are coherence charge in the same
units). This is the increment framing that won Stage 5b (steering over
prediction): a candidate is judged by how much target coherence it builds **on
top of the do-nothing / predict-unchanged floor** (`G_cad − G_0`), and whether
it does so with positive per-unit leverage (`S`).

Interpretation under the leverage principle (§6): steering *with* the φ-attractor
should give S > 1 (the field amplifies the nudge); steering *against* it, or
per-step injection into the mixing clock, should give S < 1 or ≈ 0.

## 3. Aliveness constraint (requirement for any valid measurement)

A measurement window is **valid** only if all of the following hold for **every**
readout in the window:

- **A1 NaN guard:** every decoded `ey`, `ei`, `q`, `eps2` array is all-finite.
  Any non-finite element ⇒ NaN-loud-fail, **HARD STOP** of the whole run
  (arm counts INVALID, boundary condition recorded).
- **A2 Qi/aliveness floor:** `q_mean(r) ≥ q_floor · q_mean(0)`, where
  `q_mean(0)` is the post-IC baseline q_mean. This is "the field is kept alive"
  (irreducible Qi, bounded away from the dead/zero state).
- **A3 π-saturation bound:** `π_sat_frac(r) ≤ π_sat_max`, where
  `π_sat_frac(r) = (1/N³) · #{cells : q_i(r) ≥ q_sat}` is the fraction of cells
  whose coherence saturates past a healthy upper bound. A blow-up is recorded
  as a boundary condition, not counted as a steering effect.

Defaults (set in the script, stated here so the doc and code agree):
`q_floor = 0.05`, `q_sat = 100.0`, `π_sat_max = 1e-6`.

## 4. Stopping rule (fixed before any run)

- **Hard stop on NaN** (A1) at any point ⇒ run aborts, arm INVALID, boundary
  condition logged. This is the NaN-loud-fail convention.
- **Aliveness violation:** A2 or A3 fails on **two consecutive** cadence rungs
  ⇒ arm INVALID (boundary condition logged), run continues to next arm. One
  isolated violation is flagged and the rung excluded from S (logged).
- **No adaptive stopping on S.** The run executes a fixed number `R = --rungs`
  cadence rungs (default 8). A run is only a valid measurement if it completes
  `R` valid rungs (≥ 6 rungs must be valid; otherwise the arm is INVALID and
  reported as an infrastructure/boundary negative, not a verdict).
- Budget: a run executes at most `N_max = --steps` global steps (default 2000).
  If the step budget is exhausted before `R` rungs complete, the arm is
  INVALID (under-budget), reported honestly.

## 5. Pre-registered arms and the baselines to beat

Arms run in order, each on a **fresh cleared solver** (fresh-solver-per-arm
discipline). Strength ramps from 0.

1. **Arm 0 — control, `--strength 0`:** IC deposits only (the pre-registered
   seed IC, below), then cadence windows with **no steering deposits**. This is
   the do-nothing / predict-unchanged reference. Yields the null build `G_0`
   (the field's drift baseline; every rung `Δdeposit = 0`, so it has no
   per-unit `S`).
2. **Arm 1 — cadence steering, `--strength 0.1`:** the Phase-3 loop with the
   φ-cadence injector at 0.1×.
3. **Arm 2 — cadence steering, `--strength 0.25`.**
4. **Arm 3 — cadence steering, `--strength 0.5`.**
5. **Arm 4 — cadence steering, `--strength 1.0`.**
6. **Arm 5 — per-step steering reference (bounded, `--per-step`, small window):**
   the same loop but injecting every step. This reproduces G34's regime as the
   empirical baseline the cadence arm must beat. Bounded to a short window
   (`--steps` reduced) to cap cost, and pre-registered as the reference, not a
   primary target.

Baselines imported (not re-measured as a precondition): G34's ~10× integrated
attractor degradation under per-step injection; FP-4's mixing-clock finding at
current twist strength. Arm 5 re-measures the first within this loop; the
cadence arms are the candidate remedy.

## 6. Steering policy and the leverage principle

Two-mode policy (selected by `--mode`):

- **Yang — converge (default):** steer coherence toward a target attractor.
  At each cadence rung, deposit a small charge at the target cell `T` in the
  **φ-attractor ratio** `cy = φ·ci` — the ratio at which the conversion term
  `(EY − φ·EI)` vanishes (the dormant ratio, verify_mind_engine Gate A), so the
  injection builds target coherence *without* injecting disequilibrium. The
  charge is scaled by the coherence deficit and the strength: inject
  `λ = clamp(strength · deficit / (1+φ), 0, λ_max)` with `cy = λ·φ, ci = λ`,
  `λ_max = 1.0`. This is steering **with** the φ-attractor.
- **Yin — stay-alive:** Qi-budget conservation. When `q_mean` drops below the
  floor, deposit a small *diffuse* scatter (large `sigma`, spreading the charge,
  φ-attractor ratio) to hold the floor; otherwise inject nothing. Keeps the
  field alive without driving it.

**Leverage principle:** steer with the φ-attractor, never against. Every
injection uses the attractor ratio (conversion term ≈ 0) so the field's own
dynamics do the amplification; injecting against the attractor (off-ratio) is
excluded because Gate B's off-ratio evolution is a known mixing oscillator, not
a controllable direction.

**Attention/probe policy:**

- **Readout:** a full `readout` only at cadence rungs (the expensive
  262144-cell decode). Between rungs, only lightweight `state` and `project k`
  (default `k = 8`) reads are used.
- **Deposit:** the target cell `T` for the Yang mode is the top-k project cell
  (the strongest existing attractor), or an explicit `--target-x/y/z` if given.
- **Readout cadence:** proposed from the qi-time rungs — the full-readout steps
  are `s_r = round(φ^r)` on the global step counter, injection intervals
  `τ_r = round(φ^r)` per the `cassi_qi_time.glsl` rung cadence (`τ_k = round(φ^k)`,
  `K = 7` default rungs, but only up to the pre-registered `R` full readouts).

## 7. Predictor

**Persistence baseline only, clearly labeled.** `predict(next) = current_frame`
(the predict-unchanged reference — the floor that Stage 5's REJECT was measured
against). The steering deposit is the policy output (§6), applied on cadence.
The script does **not** use CassiAI's QiField/FluidCord or any neural update;
there is no separate learned surrogate of the field in Phase 3. This keeps the
Phase-3 milestone honest: it measures whether the *loop and cadence discipline*
itself steer coherence, not whether a particular model predicts well.

## 8. Decision tree (pre-stated)

Applied per arm, top to bottom; first satisfied branch wins.

- **D0 — connection/infrastructure:** `ping`, `clear`, and the IC deposit must
  reply `ok`; charge-exact gate on the post-IC first frame must hold
  (`|Σ(ey+ei) − Σ(cy+ci)| / max(Σ|cy+ci|, 1) ≤ 1e-3`). Fail ⇒ arm INVALID
  (infrastructure), report, do not count.
- **D1 — aliveness abort:** A1 NaN ⇒ HARD STOP (whole run); A2/A3 over 2
  consecutive rungs ⇒ arm INVALID. Either records a boundary condition.
  A run with fewer than 6 valid rungs and any injection is INVALID
  (under-budget), reported honestly.
- **D2 — cadence-versus-control (SUPPORT):** `G_cad > G_0 + 2·σ_ΔQ` AND
  `S > 1.0` (positive per-unit leverage) on the arm. SUPPORT is declared only if
  it holds on arm ≥ 2 (strength ≥ 0.25) — the low-strength arm's margin is
  informative but not the bar.
- **D3 — no-leverage NULL:** `G_cad ≤ G_0 + 2·σ_ΔQ` OR `S ≤ 1.0` at the best
  valid strength ⇒ the steering arm fails to beat the do-nothing /
  predict-unchanged floor or carries no positive leverage. Honest negative
  deliverable.
- **D4 — G34 reproduction (REGRESSION):** the cadence arm's target attractor
  collapses ~10× relative to control (`Q_A(end) ≤ ε_A ≈ 0` while control is
  healthy), OR Arm 5 (per-step reference) reproduces the ~10× degradation ⇒
  cadence regularization insufficient; G34's floor stands. Honest negative.
- **D5 — alive-but-not-steering (HOLD):** aliveness satisfied but `S ≤ 0`
  (the loop keeps the field alive but does not yet steer coherence). Neither a
  SUPPORT nor a clean NULL; recorded as HOLD.

The control arm (`G_0`) is the do-nothing reference: no steering deposits
(`Δdeposit = 0` on every rung), so it reports `G_0 = Σ ΔQ_0` and has no
per-unit `S`. The active arms are judged relative to `G_0 + 2·σ_ΔQ` so a
drifting control cannot inflate a candidate.

## 9. IC and determinism

- Seeded IC: `--seed` (default 20260815), `--ic-deposits` (default 10) deposits
  as `engine_cache_writer.make_deposits` (1/3 attractor-ratio, 2/3 off-ratio,
  mixed sigma) — reused, not re-specified, so the IC matches the Phase-1 writer.
- Fresh solver per arm: `clear` then IC deposits, then the arm's own run.
- Determinism: the mind engine's two-pass PDE is 1-ULP deterministic
  (cassi_mind_engine.gd double-buffer comment); the same seed reproduces the
  same IC. Each arm is a fresh solver, so arms do not share state.

## 10. Gates in `field_steer.py` (offline --self-test and online)

- **G1 charge-exact:** post-IC first-frame charge match ≤ 1e-3 rel err.
- **G2 finite:** every decoded readout all-finite (NaN-loud-fail).
- **G3 shape:** decoded readout length == `grid_n³` (auto-detected as
  `round(len^{1/3})`).
- **G4 liveness telemetry:** `q_mean`, `π_sat_frac`, `max_eps2` recorded each
  rung; dormancy/boundary flagged, not silently dropped.
- **GS steering guard:** `total_injected > 0` in any non-control arm; a
  no-injection steering arm is a bug (recorded INVALID).

## 11. Report contents (each run appends a ledger row to this file)

Arm, strength, mode, seed, `R` valid rungs, per-rung `(step, tau, q_mean,
π_sat_frac, max_eps2, ΔQ_steered, Δdeposit, S_rung)`, aggregate `G_cad`,
`G_0` control, leverage `S`, `σ_ΔQ`, verdict branch (D0–D5), boundary
conditions (NaN/aliveness), target cell. Raw telemetry is printed and, with
`--ledger`, a row is appended to this file. Honest negatives are recorded as
verdicts, not swept.

## 12. What this pre-registration does NOT claim

No prior measurement. No claim that the loop "works" — the statistic, tree, and
stopping rule are set so a NULL or REGRESSION is a valid, recorded deliverable.
No change to the 30-arm verify battery or any shader; `field_steer.py` is a
bridge client and changes nothing in the engine.

---

## Ledger (appended after each run)

_Runs recorded below._
### Run 2026-08-15T07:38:38Z — strength 0.0 mode yang cadence phi seed 20260815

- verdict: **CONTROL** (branch -) — strength 0 reference
- G0 (control) = -0.5905; G_cad = -0.5905; S (leverage) = n/a; sigma_dq = 0.1089
- injected = 0; q_mean0 = 0.0001303; target = (13, 14, 23)
- boundary: none
- per-rung: [{"r": 1, "step": 1, "tau": 1, "q_mean": 0.00013002722698729485, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.6520156860351562, "Q_A": 1.261567234992981, "dQ": -0.0004978179931640625, "injected": 0, "S_rung": -497817.99316406244, "alive": true}, {"r": 2, "step": 3, "tau": 2, "q_mean": 0.0001289343781536445, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.5803616046905518, "Q_A": 1.2598261833190918, "dQ": -0.0017410516738891602, "injected": 0, "S_rung": -1741051.6738891602, "alive": true}, {"r": 3, "step": 6, "tau": 3, "q_mean": 0.00012618640903383493, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.4004149436950684, "Q_A": 1.2553575038909912, "dQ": -0.004468679428100586, "injected": 0, "S_rung": -4468679.428100586, "alive": true}, {"r": 4, "step": 10, "tau": 4, "q_mean": 0.00012067217903677374, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.040414571762085, "Q_A": 1.2459607124328613, "dQ": -0.009396791458129883, "injected": 0, "S_rung": -9396791.458129883, "alive": true}, {"r": 5, "step": 17, "tau": 7, "q_mean": 0.00010734016541391611, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.177652359008789, "Q_A": 1.2202562093734741, "dQ": -0.025704503059387207, "injected": 0, "S_rung": -25704503.059387207, "alive": true}, {"r": 6, "step": 28, "tau": 11, "q_mean": 8.435657946392894e-05, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.7391960024833679, "Q_A": 1.1572989225387573, "dQ": -0.0629572868347168, "injected": 0, "S_rung": -62957286.83471679, "alive": true}, {"r": 7, "step": 46, "tau": 18, "q_mean": 7.000042387517169e-05, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.160933718085289, "Q_A": 1.0030617713928223, "dQ": -0.15423715114593506, "injected": 0, "S_rung": -154237151.14593506, "alive": true}, {"r": 8, "step": 75, "tau": 29, "q_mean": 9.994914580602199e-05, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.414639711380005, "Q_A": 0.6715372800827026, "dQ": -0.33152449131011963, "injected": 0, "S_rung": -331524491.3101196, "alive": true}]

### Run 2026-08-15T07:38:46Z — strength 0.1 mode yang cadence phi seed 20260815

- verdict: **NULL** (branch D3) — G_cad 13.49 <= G0+2sig 1.881 or S 0.895 <= 1
- G0 (control) = -0.5905; G_cad = 13.49; S (leverage) = 0.8947; sigma_dq = 1.236
- injected = 15.08; q_mean0 = 0.0001303; target = (13, 14, 23)
- boundary: none
- per-rung: [{"r": 1, "step": 1, "tau": 1, "q_mean": 0.0001565553538966924, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.6520156860351562, "Q_A": 2.1300747394561768, "dQ": 0.8680096864700317, "injected": 2.573793494701386, "S_rung": 0.3372491570349311, "alive": true}, {"r": 2, "step": 3, "tau": 2, "q_mean": 0.00020959536777809262, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.5803616046905518, "Q_A": 3.899956226348877, "dQ": 1.7698814868927002, "injected": 2.4869925260543826, "S_rung": 0.711655330022491, "alive": true}, {"r": 3, "step": 6, "tau": 3, "q_mean": 0.00028204938280396163, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.4004149436950684, "Q_A": 6.356339454650879, "dQ": 2.456383228302002, "injected": 2.310004377365112, "S_rung": 1.063367347859252, "alive": true}, {"r": 4, "step": 10, "tau": 4, "q_mean": 0.0003635718021541834, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.040414571762085, "Q_A": 9.19477367401123, "dQ": 2.8384342193603516, "injected": 2.0643660545349123, "S_rung": 1.3749665245294065, "alive": true}, {"r": 5, "step": 17, "tau": 7, "q_mean": 0.00043817819096148014, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.177652359008789, "Q_A": 12.045659065246582, "dQ": 2.8508853912353516, "injected": 1.7805226325988768, "S_rung": 1.6011508862845274, "alive": true}, {"r": 6, "step": 28, "tau": 11, "q_mean": 0.0004917777259834111, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.7391960024833679, "Q_A": 14.48536491394043, "dQ": 2.4397058486938477, "injected": 1.4954340934753418, "S_rung": 1.6314365570093752, "alive": true}, {"r": 7, "step": 46, "tau": 18, "q_mean": 0.0005232943221926689, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.160933718085289, "Q_A": 15.819683074951172, "dQ": 1.3343181610107422, "injected": 1.2514635086059571, "S_rung": 1.0662062072405765, "alive": true}, {"r": 8, "step": 75, "tau": 29, "q_mean": 0.0005324539379216731, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.414639711380005, "Q_A": 14.754693031311035, "dQ": -1.0649900436401367, "injected": 1.1180316925048828, "S_rung": -0.9525580095624039, "alive": true}]

### Run 2026-08-15T07:38:54Z — strength 0.25 mode yang cadence phi seed 20260815

- verdict: **SUPPORT** (branch D2) — G_cad 19.51 > G0+2sig 3.971 and S 1.073 > 1
- G0 (control) = -0.5905; G_cad = 19.51; S (leverage) = 1.0729; sigma_dq = 2.281
- injected = 18.19; q_mean0 = 0.0001303; target = (13, 14, 23)
- boundary: none
- per-rung: [{"r": 1, "step": 1, "tau": 1, "q_mean": 0.00015727398567833006, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.6520156860351562, "Q_A": 2.1535956859588623, "dQ": 0.8915306329727173, "injected": 2.618033988749895, "S_rung": 0.3405343997838703, "alive": true}, {"r": 2, "step": 3, "tau": 2, "q_mean": 0.00021446938626468182, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.5803616046905518, "Q_A": 4.0594587326049805, "dQ": 1.9058630466461182, "injected": 2.618033988749895, "S_rung": 0.7279749059163908, "alive": true}, {"r": 3, "step": 6, "tau": 3, "q_mean": 0.00030086698825471103, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.4004149436950684, "Q_A": 6.972095966339111, "dQ": 2.912637233734131, "injected": 2.618033988749895, "S_rung": 1.1125284263879662, "alive": true}, {"r": 4, "step": 10, "tau": 4, "q_mean": 0.0004148258303757757, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.040414571762085, "Q_A": 10.87183666229248, "dQ": 3.899740695953369, "injected": 2.618033988749895, "S_rung": 1.4895683985430175, "alive": true}, {"r": 5, "step": 17, "tau": 7, "q_mean": 0.0005486689042299986, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.177652359008789, "Q_A": 15.660682678222656, "dQ": 4.788846015930176, "injected": 2.618033988749895, "S_rung": 1.8291764111958067, "alive": true}, {"r": 6, "step": 28, "tau": 11, "q_mean": 0.0006921917083673179, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.7391960024833679, "Q_A": 21.041221618652344, "dQ": 5.3805389404296875, "injected": 2.618033988749895, "S_rung": 2.055182997451795, "alive": true}, {"r": 7, "step": 46, "tau": 18, "q_mean": 0.0007444513030350208, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.160933718085289, "Q_A": 23.048614501953125, "dQ": 2.0073928833007812, "injected": 1.489694595336914, "S_rung": 1.3475197463858577, "alive": true}, {"r": 8, "step": 75, "tau": 29, "q_mean": 0.000717359536793083, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.414639711380005, "Q_A": 20.77423095703125, "dQ": -2.274383544921875, "injected": 0.9878463745117188, "S_rung": -2.3023656345816694, "alive": true}]

### Run 2026-08-15T07:39:01Z — strength 0.5 mode yang cadence phi seed 20260815

- verdict: **SUPPORT** (branch D2) — G_cad 20.94 > G0+2sig 5.074 and S 1.112 > 1
- G0 (control) = -0.5905; G_cad = 20.94; S (leverage) = 1.1120; sigma_dq = 2.832
- injected = 18.83; q_mean0 = 0.0001303; target = (13, 14, 23)
- boundary: none
- per-rung: [{"r": 1, "step": 1, "tau": 1, "q_mean": 0.00015727398567833006, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.6520156860351562, "Q_A": 2.1535956859588623, "dQ": 0.8915306329727173, "injected": 2.618033988749895, "S_rung": 0.3405343997838703, "alive": true}, {"r": 2, "step": 3, "tau": 2, "q_mean": 0.00021446938626468182, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.5803616046905518, "Q_A": 4.0594587326049805, "dQ": 1.9058630466461182, "injected": 2.618033988749895, "S_rung": 0.7279749059163908, "alive": true}, {"r": 3, "step": 6, "tau": 3, "q_mean": 0.00030086698825471103, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.4004149436950684, "Q_A": 6.972095966339111, "dQ": 2.912637233734131, "injected": 2.618033988749895, "S_rung": 1.1125284263879662, "alive": true}, {"r": 4, "step": 10, "tau": 4, "q_mean": 0.0004148258303757757, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.040414571762085, "Q_A": 10.87183666229248, "dQ": 3.899740695953369, "injected": 2.618033988749895, "S_rung": 1.4895683985430175, "alive": true}, {"r": 5, "step": 17, "tau": 7, "q_mean": 0.0005486689042299986, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.177652359008789, "Q_A": 15.660682678222656, "dQ": 4.788846015930176, "injected": 2.618033988749895, "S_rung": 1.8291764111958067, "alive": true}, {"r": 6, "step": 28, "tau": 11, "q_mean": 0.0006921917083673179, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.7391960024833679, "Q_A": 21.041221618652344, "dQ": 5.3805389404296875, "injected": 2.618033988749895, "S_rung": 2.055182997451795, "alive": true}, {"r": 7, "step": 46, "tau": 18, "q_mean": 0.0008345817914232612, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.160933718085289, "Q_A": 25.995946884155273, "dQ": 4.95472526550293, "injected": 2.618033988749895, "S_rung": 1.8925366465042723, "alive": true}, {"r": 8, "step": 75, "tau": 29, "q_mean": 0.0007610634784214199, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.414639711380005, "Q_A": 22.198204040527344, "dQ": -3.7977428436279297, "injected": 0.5020265579223633, "S_rung": -7.564824576900646, "alive": true}]

### Run 2026-08-15T07:39:11Z — strength 1.0 mode yang cadence phi seed 20260815

- verdict: **SUPPORT** (branch D2) — G_cad 22.18 > G0+2sig 4.386 and S 1.148 > 1
- G0 (control) = -0.5905; G_cad = 22.18; S (leverage) = 1.1476; sigma_dq = 2.488
- injected = 19.33; q_mean0 = 0.0001303; target = (13, 14, 23)
- boundary: none
- per-rung: [{"r": 1, "step": 1, "tau": 1, "q_mean": 0.00015727398567833006, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.6520156860351562, "Q_A": 2.1535956859588623, "dQ": 0.8915306329727173, "injected": 2.618033988749895, "S_rung": 0.3405343997838703, "alive": true}, {"r": 2, "step": 3, "tau": 2, "q_mean": 0.00021446938626468182, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.5803616046905518, "Q_A": 4.0594587326049805, "dQ": 1.9058630466461182, "injected": 2.618033988749895, "S_rung": 0.7279749059163908, "alive": true}, {"r": 3, "step": 6, "tau": 3, "q_mean": 0.00030086698825471103, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.4004149436950684, "Q_A": 6.972095966339111, "dQ": 2.912637233734131, "injected": 2.618033988749895, "S_rung": 1.1125284263879662, "alive": true}, {"r": 4, "step": 10, "tau": 4, "q_mean": 0.0004148258303757757, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.040414571762085, "Q_A": 10.87183666229248, "dQ": 3.899740695953369, "injected": 2.618033988749895, "S_rung": 1.4895683985430175, "alive": true}, {"r": 5, "step": 17, "tau": 7, "q_mean": 0.0005486689042299986, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.177652359008789, "Q_A": 15.660682678222656, "dQ": 4.788846015930176, "injected": 2.618033988749895, "S_rung": 1.8291764111958067, "alive": true}, {"r": 6, "step": 28, "tau": 11, "q_mean": 0.0006921917083673179, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.7391960024833679, "Q_A": 21.041221618652344, "dQ": 5.3805389404296875, "injected": 2.618033988749895, "S_rung": 2.055182997451795, "alive": true}, {"r": 7, "step": 46, "tau": 18, "q_mean": 0.0008345817914232612, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 0.160933718085289, "Q_A": 25.995946884155273, "dQ": 4.95472526550293, "injected": 2.618033988749895, "S_rung": 1.8925366465042723, "alive": true}, {"r": 8, "step": 75, "tau": 29, "q_mean": 0.0007992719765752554, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.414639711380005, "Q_A": 23.445850372314453, "dQ": -2.5500965118408203, "injected": 1.0040531158447266, "S_rung": -2.5398023984969975, "alive": true}]

### Run 2026-08-15T07:39:20Z — strength 0.25 mode yang cadence uniform seed 20260815

- verdict: **SUPPORT** (branch D2) — G_cad 25.65 > G0+2sig 3.639 and S 1.437 > 1
- G0 (control) = -0.05633; G_cad = 25.65; S (leverage) = 1.4373; sigma_dq = 1.848
- injected = 17.85; q_mean0 = 0.0001303; target = (13, 14, 23)
- boundary: none
- per-rung: [{"r": 1, "step": 1, "tau": 1, "q_mean": 0.00015727398567833006, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.6520156860351562, "Q_A": 2.1535956859588623, "dQ": 0.8915306329727173, "injected": 2.618033988749895, "S_rung": 0.3405343997838703, "alive": true}, {"r": 2, "step": 2, "tau": 1, "q_mean": 0.00021512024977710098, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.6211910247802734, "Q_A": 4.061376571655273, "dQ": 1.9077808856964111, "injected": 2.618033988749895, "S_rung": 0.7287074552486509, "alive": true}, {"r": 3, "step": 3, "tau": 1, "q_mean": 0.0003038623253814876, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.5803616046905518, "Q_A": 6.984717845916748, "dQ": 2.9233412742614746, "injected": 2.618033988749895, "S_rung": 1.1166170060524552, "alive": true}, {"r": 4, "step": 4, "tau": 1, "q_mean": 0.0004234742955304682, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.529757261276245, "Q_A": 10.922654151916504, "dQ": 3.937936305999756, "injected": 2.618033988749895, "S_rung": 1.5041578233597002, "alive": true}, {"r": 5, "step": 5, "tau": 1, "q_mean": 0.0005739227053709328, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.4696624279022217, "Q_A": 15.87394905090332, "dQ": 4.951294898986816, "injected": 2.618033988749895, "S_rung": 1.8912263630889865, "alive": true}, {"r": 6, "step": 6, "tau": 1, "q_mean": 0.0007551666931249201, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.4004149436950684, "Q_A": 21.83709144592285, "dQ": 5.963142395019531, "injected": 2.618033988749895, "S_rung": 2.277717715142009, "alive": true}, {"r": 7, "step": 7, "tau": 1, "q_mean": 0.0008550001075491309, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.3224048614501953, "Q_A": 25.14055824279785, "dQ": 3.303466796875, "injected": 1.290727138519287, "S_rung": 2.5593843177921505, "alive": true}, {"r": 8, "step": 8, "tau": 1, "q_mean": 0.0008915275102481246, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.236070156097412, "Q_A": 26.376590728759766, "dQ": 1.236032485961914, "injected": 0.46486043930053705, "S_rung": 2.6589324052219605, "alive": true}, {"r": 9, "step": 9, "tau": 1, "q_mean": 0.0009025337058119476, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.1418967247009277, "Q_A": 26.78128433227539, "dQ": 0.404693603515625, "injected": 0.1558523178100586, "S_rung": 2.5966479626490764, "alive": true}, {"r": 10, "step": 10, "tau": 1, "q_mean": 0.0009048556676134467, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 3.040414571762085, "Q_A": 26.905282974243164, "dQ": 0.12399864196777344, "injected": 0.054678916931152344, "S_rung": 2.2677596581494726, "alive": true}, {"r": 11, "step": 11, "tau": 1, "q_mean": 0.000904357002582401, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.9321937561035156, "Q_A": 26.940187454223633, "dQ": 0.03490447998046875, "injected": 0.023679256439208984, "S_rung": 1.4740530417446989, "alive": true}, {"r": 12, "step": 12, "tau": 1, "q_mean": 0.0009029227076098323, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.817842960357666, "Q_A": 26.947370529174805, "dQ": 0.007183074951171875, "injected": 0.014953136444091797, "S_rung": 0.4803724608565324, "alive": true}, {"r": 13, "step": 13, "tau": 1, "q_mean": 0.0009011471993289888, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.6980059146881104, "Q_A": 26.94598388671875, "dQ": -0.0013866424560546875, "injected": 0.013157367706298828, "S_rung": -0.10538904794694307, "alive": true}, {"r": 14, "step": 14, "tau": 1, "q_mean": 0.0008992211660370231, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.5733559131622314, "Q_A": 26.941957473754883, "dQ": -0.0040264129638671875, "injected": 0.0135040283203125, "S_rung": -0.2981638418079096, "alive": true}, {"r": 15, "step": 15, "tau": 1, "q_mean": 0.0008972107898443937, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.444594621658325, "Q_A": 26.937118530273438, "dQ": -0.0048389434814453125, "injected": 0.014510631561279297, "S_rung": -0.3334757319838323, "alive": true}, {"r": 16, "step": 16, "tau": 1, "q_mean": 0.0008951435447670519, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.312445640563965, "Q_A": 26.932022094726562, "dQ": -0.005096435546875, "injected": 0.015720367431640625, "S_rung": -0.324193157000728, "alive": true}, {"r": 17, "step": 17, "tau": 1, "q_mean": 0.0008930359035730362, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.177652359008789, "Q_A": 26.926862716674805, "dQ": -0.0051593780517578125, "injected": 0.016994476318359375, "S_rung": -0.30359147025813693, "alive": true}, {"r": 18, "step": 18, "tau": 1, "q_mean": 0.0008908997988328338, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 2.0409727096557617, "Q_A": 26.921680450439453, "dQ": -0.0051822662353515625, "injected": 0.018284320831298828, "S_rung": -0.28342678315295344, "alive": true}, {"r": 19, "step": 19, "tau": 1, "q_mean": 0.000888747104909271, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 1.9031755924224854, "Q_A": 26.916492462158203, "dQ": -0.00518798828125, "injected": 0.01957988739013672, "S_rung": -0.2649651746139983, "alive": true}, {"r": 20, "step": 20, "tau": 1, "q_mean": 0.0008865890558809042, "q_mean0": 0.00013034199946559966, "pi_sat_frac": 0.0, "max_eps2": 1.7650357484817505, "Q_A": 26.91130828857422, "dQ": -0.005184173583984375, "injected": 0.02087688446044922, "S_rung": -0.2483212279018775, "alive": true}]
