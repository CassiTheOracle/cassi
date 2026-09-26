# BH field channel (stage 1) — PRE-REGISTRATION

## Status: Pre-registration — written BEFORE any run of `verify_bh_dynamics.gd`; governs the stage-1 gate set

**Date:** 2026-09-15 · **Workstream:** BH sector / field channel (`BH_DYNAMICS_PLAN.md`)
**Probe:** `CassiCosmos/scripts/verify_bh_dynamics.gd` + `CassiCosmos/scenes/verify_bh_dynamics.tscn` (new files, the only execution path this document governs)
**Receipt:** `res://_diag/bh_dynamics/bh_dynamics_receipt.json`
**Run:** `<Godot 4.7.1 mono console exe> --path . res://scenes/verify_bh_dynamics.tscn` (windowed; this rig has no headless RenderingDevice)

Every bound below is **derived from the source before the run** (fixed-point deposit arithmetic, fp32 rounding, the deposit's documented clamp, the KDK integrator's own algebra) — none of them is a measured number, and none may be widened after a run. Where a bound is an *estimate* of a floating-point artifact, its derivation is stated and the estimate's headroom over the artifact is recorded.

---

## 0. The claim being tested

Stage 1 of `BH_DYNAMICS_PLAN.md` §1 makes the BH sector a **field source and a test body**:

1. **Source.** A BH's mass enters the SAME fixed-point accumulator the particles write (`cassi_bh_deposit.glsl` → `_mass_density_fix`), before the same convert, on the base lattice and on the dual (Yin/Yang) lattice. ρ, Φ and ∇(g·Φ) therefore carry the BH's mass with no second source path and no unit conversion.
2. **Test body.** BH motion is not a second force model: `cassi_bh_finalize.glsl` mirrors the particle arm's cached-acc KDK leapfrog expression for expression and samples the same ∇(g·Φ) through the shared include (`cassi_river_force_common.glslinc`, `river_acc_at`). Planted on a **massless** particle's (p, v), a BH's trajectory must therefore agree with that particle's **bit for bit** — not "closely".
3. **Conserved transfer.** A swallow moves mass AND momentum: the accretion pass adds `pos.w` and `pos.w·vel` to the BH's record and to a pending book; the finalize folds the impulse in the momentum-conserving form `v ← (v·(M − ΔM) + Σm·v)/M` and zeroes the book. A step with no swallow performs **no arithmetic on v at all** (which is what makes claim 2 exact rather than approximate).
4. **Anti-double-count.** While the channel is live the analytic point term is written OFF by construction (`bh[3].x = 0`): the BH's own gravity reaches the particles through the field, never twice.
5. **Default-off.** With `bh_field_channel = false` the new shaders are never loaded, no set/pipeline is created, and no new write happens on any live buffer — the legacy path is bit-identical.

### 0.1 What this pre-registration does NOT claim (scope boundary)

- **No formation.** BH birth (σ-core nucleation, host seeding policy) is stage 3 (`BH_DYNAMICS_PLAN.md` §2) and is out of scope here; the probe plants records directly. While the channel is live the legacy condensation scan is skipped, and that skip is a *scope statement*, not a tested behaviour.
- **No PDE-mediated BH physics.** The probe runs with `freeze_field = true`, so the two-fluid PDE never runs: the measured force is the deposit → Poisson → ∇(g·Φ) chain alone. Whether a BH's own source feeds back into the two-fluid dynamics is not measured here.
- **No production-mass claim.** The deposit's per-cell clamp (BH1's second half) is characterised, not asserted to be irrelevant in production.
- **No site/gridless coverage.** The channel is inert in the gridless/site chain by construction (its own force path); that is a host-predicate check, not a GPU measurement.
- **No claim about `verify_core`.** The production gate is a separate, subsequent run.

---

## 1. Frozen probe configuration

| Knob | Value | Why |
|---|---|---|
| `grid_N` | 64 | power of two, smallest supported; the Poisson FFT and the TSC deposit are exercised |
| box | cube, half-extent 37.5 (`cluster_radius` 25, `box_aspect` 1,1,1) | fixed cell size h = 75/64 = 1.171875 |
| `dt` | 0.02 | the particle arm's default order; |v|dt ≪ h over the arms' step counts |
| field | **uniform** EY = 0.6, EI = 0.5, written after setup | π/ρ = 0.1/1.1 = 0.0909… is a *known constant everywhere*, so the force comes from the planted masses alone and the parity gate compares like with like. (`ρ < 1e-6 → 0` guard not triggered; the clamp ceiling 0.72 not reached.) |
| gravity | `gravity_mode = 0` (river), dual lattice **on** (the engine default) | production's own law; the dual average lives inside `sample_fields`, so both consumers inherit it |
| `freeze_field` | true | the PDE is out of scope (§0.1) |
| `qi_condensation_threshold` | raised far above the field's q | the condensation scan can only run every 100th step; every arm is shorter — belt-and-braces determinism |
| `bh_acc_rate`, `bh_max_age` | 0.0 | the legacy q-growth and expiry are the *legacy* path's; the channel retires them, and arm BH6 needs a bit-stable record |
| `black_holes_enabled` | true in every arm | the flag the channel hangs off |
| `+bh_field_channel` | live arms true, BH6 arm false | the toggle under test |
| `+bh_accretion`, `bh_accretion_radius` | off in the parity/ledger arms; on with R_acc = 0.5 in the momentum arm | isolate the two mechanisms |
| test-particle mass | **0.0** | the deposit returns on `mass <= 0.0` and the accretion pass returns on `p.w <= 0.0`, while the nbody integrator does *not* skip the particle: a mass-0 test particle is integrated and deposits nothing. This is what makes BH3 an exact claim instead of a 1e-6 one. |
| planting | `plant_bh(slot, pos, mass)` / direct `buffer_update` of `_pos_buf`/`_vel_buf`, **before the engine's first step** | the particle arm's `_grav_warmup` fires on step 1; a mid-run plant would leave `acc[i]` stale and would not be comparable |

**Plant discipline (both arms):** all positions and velocities are planted before `run_steps(1)`; the BH's seed step (warm-up evaluation + complete KDK, `pc.pass_mode = 1`) fires on the same step, so step 1 is a complete KDK step for both consumers.

---

## 2. The gates

Statistics are read back with `buffer_get_data` and decoded in float64. Every gate prints its statistic and its bound; the receipt carries the numbers.

### BH1 — source ledger (the BH's mass reaches ρ, once, on both lattices)

| # | Configuration | Statistic | Bound | Derivation of the bound |
|---|---|---|---|---|
| BH1a | BH-only engine (`N_particles = 0`), records M = 200 + 100 | `Σρ / 300` | **1 ± 1e-5** | TSC is a partition of unity; each contribution is `round(m·w·2^-24)`-exact and the fixed-point sum is exact per cell, so the only error is the rounding of 27 per-particle weight products (≤ 0.5 count each) plus the fp32 divider: ≤ 3·2^-24 + 27·2^-25/300 ≈ 2.4e-7 relative. |
| BH1b | same, single record M = 600 | `Σρ / 600` | **1 ± 1e-5** | 600 is below the clamp ceiling (§BH1d). |
| BH1c | same, single record M = 700 | `Σρ` | **660.6875 ± 0.007** | *Prediction, not a tolerance:* a record at the world origin maps to `gc = (0)·(32/37.5) + 32 = 32.0` exactly → f = 0 on every axis → weights (0.125, 0.75, 0.125) → centre-cell contribution `round(700·0.421875·2^24) = 4 954 521 600`, above the shader's per-cell clamp `2^32 − 256 = 4 294 967 040`. Loss = 659 554 560/2^24 = **39.3125**. Every other cell's largest weight is `0.75²·0.125 = 0.0703125` → 8.3e8, unclamped. Σρ = 700 − 39.3125 = **660.6875** (ratio 0.9438392857…). |
| BH1d | (derived ceiling, recorded) | `m* = clamp/(0.75³·2^24)` | **606.8148…** | `4294967040/(0.421875·16777216)`. Masses below this cannot clamp on any lattice offset. Recorded as the channel's source ceiling. |
| BH1e | same config, `dual_grid = true` | `Σρ / M` | **1 ± 1e-5** | the dual chain re-uses the same fix buffer after its own clear; the BH deposit is dispatched there too, so the last lattice's ρ must still carry the full planted mass. |
| BH1f | live channel | `bh[3].x` (header float 48) | **== 0.0 exactly** | the anti-double-count is host-written, so it must be exactly zero, not small. |

### BH2 — conserved transfer (mass **and** momentum)

Configuration: single centred BH M = 200 at the origin; 8 particles at x = ±0.05, ±0.10, ±0.15, ±0.20 (masses 1, 1, 2, 2, 3, 3, 4, 4 — each ± pair sharing its mass, so the cloud is mirror-symmetric and its field gradient at the origin is a rounding-level residual), velocities `v_i = (0.1·(i+1), 0, 0.3)` for i = 0..7; accretion on with R_acc = 0.5 (every particle is within 0.2); one step.

| # | Statistic | Bound | Derivation |
|---|---|---|---|
| BH2a | BH mass after the step vs `M + Σm` (Σm = 20, M_total = 220) | **≤ 1e-4 absolute** | the accretion is a single `atomicAdd` of `pos.w` per particle: exact in fp32 for these magnitudes (the sum 200+1..4 is representable). |
| BH2b | `V` vs `Σ m·v / M_total` = **(11.0, 0, 6.0)/220 = (0.05, 0, 0.027272727…)** | **≤ 1e-3 relative** | v₀ = 0, so the fold reduces to `P/M`: one rounding (≤ 2^-24) plus the *atomic* accumulation order of Σm·v (free at the ulp level by construction) plus the field's residual kick at the origin (≤ the BH4 residual, ~1e-6 of the mutual scale — 1e-3 leaves ≥ 10³ headroom and still fails an O(1) mis-weighting). |
| BH2c | the pending book after the step | **== 0.0 exactly (all four lanes)** | the finalize zeroes it; a residual means a fold left state behind, which would be re-applied next step. |
| BH2d | every swallowed particle | `pos.w == 0.0` | the swallow's own ledger. |

### BH3 — law parity: a BH *is* a test body (exact)

Configuration: two equal BHs (M = 200) at (∓4, 0, 0) and a **massless** test particle planted at each BH's position with v = 0; accretion off; dual on; 1 step, then 64 further steps (the pair arm continues).

| # | Statistic | Bound |
|---|---|---|
| BH3a | per BH, per component: `dv_BH − dv_test` | **== 0.0 exactly** (primary) |
| BH3b | the same residual, either BH, after **64** steps | **== 0.0 exactly** |
| BH3c | trajectory: `pos_BH − pos_test` | **== 0.0 exactly** |

*Exactness is the claim, not a convenience:* the same expression (`river_acc_at`) on the same inputs (same position, same buffers, same field state — nothing writes the field between the BH finalize and the particle KDK in a step) with the same integrator (cached-acc KDK, both seeded on step 1) must produce the same fp32 bits.

**Decision rule if a residual is non-zero (pre-committed):** the residual is inspected before anything is widened.
- If it is **≤ 2^-22 relative, sign- and magnitude-stable across steps** (the signature of a compiler contracting an FMA differently in the two shader modules), the gate reads **PASS(1ULP)**, and the measured bound is recorded in the receipt and the plan as the *measured* parity bound.
- If it is **larger, or grows with step count, or differs between the two BHs**, the gate reads **FAIL** — a growing difference means the integrator or the sampler differs, which is exactly what this gate exists to catch. No tolerance widening is permitted after the run.

### BH3d — anti-vacuity control (the parity gate must be able to fail)

A dead channel would make BH3a pass trivially (0 == 0). Two structural checks pin that the arm carries a real, correctly-signed force:

| # | Statistic | Bound |
|---|---|---|
| BH3e | `dv_BH.x` for the BH at x = −4 / at x = +4 | **> 0 / < 0** (each BH is kicked toward the other) |
| BH3f | `|dv_BH0 + dv_BH1| / |dv_BH0|` (equal masses, mirror-symmetric plant) | **≤ 1e-4** (a rounding-level residual: the deposit is exactly mirror-symmetric in fixed-point integers, but the FFT Poisson and the gradient stencil are not exactly mirror-antisymmetric; 1e-4 is ≥ 100× the expected 64³ asymmetry and still fails any systematic asymmetry) |
| BH3g | `|dv_BH|` | **> 0** strictly, and recorded |

### BH4 — self-force bound

Configuration: one centred BH (M = 200), nothing else, one step. The grid-symmetric point is where the BH's own well's gradient must cancel.

| # | Statistic | Bound | Derivation |
|---|---|---|---|
| BH4 | `|Δv_self| / |Δv_mutual at D = 4|` (the mutual kick is BH3's) | **≤ 1e-3** | The residual at the symmetric point is the discretisation's own asymmetry: ≈ 1e-6 relative in |∇S| (FFT + stencil), amplified by the scale ratio `D/h = 4/1.171875 = 3.41` → estimate ≈ 3.4e-6. The gate sits ~300× above that estimate and ~100× below a genuine self-force defect (which is O(1) of the mutual scale). |

### BH5 — the pair moves through the field as a pair

| # | Statistic | Bound |
|---|---|---|
| BH5a | separation `|p0 − p1|` over 32 steps | **monotone non-increasing** (slack 1e-9) and `sep_final < sep_0` |
| BH5b | one-step slope identity: `(sep_1 − sep_0)` vs `−|Δv_pair|·dt` (BH3's measured per-BH kick, same config) | **≤ 5% of the predicted magnitude** |

*Derivation of BH5b:* from v = 0, both BHs take `v_half = a(p₀)·dt/2`; the separation therefore closes by `(v_half,0 − v_half,1)·dt = −2·a(p₀)·dt²/2 = −a(p₀)·dt²`, while BH3's measured one-step `Δv` is `(a(p₀) + a(p₁))·dt/2 = a(p₀)·dt·(1 + O(dt²))` → `sep_1 − sep_0 = −|Δv|·dt` to `O(dt²)`. Two independent receipts (a velocity kick and a position change) must agree. `a(p₀)` and `a(p₁)` are evaluated as an average, so the residual is bounded by the field's curvature over the step, `≈ dt²·|∇a|/|a| ≈ 1e-3`; 5% is deliberate headroom.

### BH6 — default-off (bit-identity of the legacy path)

Configuration: `bh_field_channel = false`, one centred BH (M = 200), `N_particles = 0`, `bh_accretion = false`, `bh_acc_rate = 0`, `bh_max_age = 0`, one step.

| # | Statistic | Bound | Note |
|---|---|---|---|
| BH6a | `Σρ` | **== 0.0 exactly** | no particle deposit (N = 0) and no BH deposit: the cleared ρ stays empty. |
| BH6b | `bh[3].x` (header float 48) | **== 1.0 exactly** | the analytic point term is ON when the channel is off. |
| BH6c | record floats 0..6 (pos, mass, vel) after the step | **bit-identical** to the plant | v = 0 and no self-force ⇒ `pos += v·dt` is a no-op; mass is untouched (`bh_acc_rate = 0`). |
| BH6d | record float 7 (age) | **== planted age + 1.0** | the legacy integrate still runs — the channel *replaces* it, it does not disable it. Derived from `cassi_bh_integrate.glsl` (`age += 1.0`). |
| BH6e | `_bh_dep_pipe`, `_us_bh_dep_0`, `_bh_fin_pipe`, `_us_bh_fin_0` | **all invalid** | the new shaders must not even be loaded. |
| BH6f | `_bh_dyn_buf`, `_bh_acc_buf` | **all zeros** | no new write reaches the live buffers. |
| BH6g | `bh_field_channel_live()` with the toggle ON but mode 1 / mode 2 / mode 5 (tree) | **false** in all three | the predicate is host state: no GPU run needed. |

---

## 3. Decision tree and stopping rule

1. **One run** of the probe. Every gate is reported with its statistic; the receipt is the record.
2. **All gates pass** → stage 1 is verified at this scope; the plan's mechanism table gains the measured numbers (BH3's parity bound, BH4's ratio, BH5's slope residual, BH1d's ceiling), and `verify_core.tscn` is run once to confirm default-off bit-identity (a separate, independent contract).
3. **Any FAIL** → the run is a FAIL and is reported as such (honest negatives are deliverables). Triage order: (a) re-read the receipt's numbers, (b) re-read the source path the gate covers, (c) *then* fix the defect and re-run. Widening a bound to make a gate pass is **not** an available move; a bound may only be widened if the derivation itself was wrong, and then the correction is written into this document before the re-run.
4. **Non-determinism ceiling:** every gate here is deterministic *except* the atomic accumulation order inside Σm·v (BH2b) and any FFT rounding asymmetry (BH3f). Both are covered by pre-stated bounds; a run-to-run change of *verdict* on those two gates would itself be a finding (the bounds sit ≥ 100× above the artifact).
5. **Stopping:** the probe is not re-run to fish for a pass. At most one re-run per *defect* fixed, with the fix named in the receipt's context.

---

## 3a. Run 1 — harness FAIL (recorded before run 2)

Run 1 executed every gate but is **void as evidence**: the harness, not the
engine, failed. Three defects, all in `scripts/verify_bh_dynamics.gd` or the
legacy path it mirrors, were diagnosed from the run log
(`res://_diag/bh_dynamics/probe_run.log`, no receipt was written) and fixed
before run 2, under §3.3(c):

1. **GDScript has no `%e`.** Fourteen gate messages used `%.3e`/`%.6e`/`%.8e`;
   an unsupported conversion does not raise, it returns the *raw template*, so
   BH2b, BH3a/b/c/f, BH4 and BH5b printed `%.3e` where their numbers belong.
   The pass/fail booleans were computed from the real numbers and are consistent
   (BH3a/b read PASS, BH3c/f, BH4 and BH5b read FAIL **without their statistics**
   — unusable either way). Fixed by routing all scientific notation through
   `String.num_scientific` (`_sci`), so run 2 carries the numbers.
2. **`RenderingDevice.free_rendering_device()` does not exist in 4.7.** The
   error aborted `_finish` before `quit()`, so the process never exited (the run
   reached its last gate in ~60 s and then spun until killed at the harness's
   15-minute ceiling). Fixed to `_rd.free()`, the idiom the retained probes use;
   the engine never owned the device (`owns_rd = false` at every site), so
   there is no double free.
3. **A pre-existing race in the legacy BH integrate's dispatch.** The grid arm
   dispatched `cassi_bh_integrate` (local_size 64, `slot = gl_GlobalInvocationID.x`,
   `slot >= 15` return) as `(wg, wg, wg)` workgroups, where `wg = ceil(grid_N/4)`
   is the *cell* convention (4³ cells per 64-thread group) — 16³ workgroups at
   N = 64, of which 16² = 256 race on each of the 15 slots. `pos/vel/mass` writes
   are write-identical so the race is inert there, but `age += 1` is not
   idempotent: BH6d measured **5 → 7 in one step**. The site twin
   (`cassi_site_bh_integrate`, same shader shape) already dispatches `1,1,1`, so
   the grid arm is fixed to that shape. BH6d's `age == planted + 1` claim is
   unchanged by this — it now *gates the fix*.

Also recorded from run 1 (not gates, but evidence the harness is live):
BH0 PASS (local RD acquired); the N = 0 deposit set is valid (the `max(N,1)`
buffer fix); BH1a–f PASS with the ceiling prediction landing at
`Σρ = 660.68748` against the derived `660.6875` (loss 39.31252); BH2a/c/d PASS;
BH3a/b PASS (bit-identical step-1 and 64-step `Δv`); BH5a PASS (8.0 → 6.94129,
monotone); BH6a/b/c/e/f/g PASS. Nothing in run 1 contradicts the design; the
numbers above are not claims, because a void run's PASSes carry no weight.

---

## 3b. Run 2 diagnostics — what is fixed, what stands as a FAIL

Run 2 was a clean run (all 27 gates executed, receipt written, 1.45 s): **22 PASS,
5 FAIL**. Diagnosis of the five, from the run's own numbers plus a throwaway
GPU diagnostic (windowed, `--script`, since removed; raw logs under
`_diag/bh_dynamics/`):

1. **BH3c was mis-wired in the probe** — it compared the BH's *position*
   (`bh[0..2]`) against the particle *velocity* buffer, so its `|Δp| ≈ 4.04` is a
   position against a velocity, not a trajectory divergence. Its intended
   statistic is position-vs-position; the readback is corrected in run 3. This is
   the only change to a gate's *plumbing*.
2. **BH2b's statistic compares against the wrong velocities and includes the
   BH's own field kick.** Two measured effects, both from the control run (same
   plant, same field, accretion off, one step):
   - *The book folds the swallow-instant velocities, not the planted ones.* The
     particle at `x = +0.05` is planted with `v = (0.1, 0, 0.3)` and reads
     `(0.08843, ·, 0.29938)` after one step in the BH's well; the same ratios
     appear on the swallowed (dead) particles in the accretion run. So
     `Σm·v_planted` is not the momentum the fold is handed.
   - *The record also carries `a·dt`.* The finalize folds the impulse and
     *then* takes its KDK step, so the post-step velocity is `fold + a·dt`; the
     measured `a·dt` for this plant is `8.4e-4` in x.
   Run 3 adds **BH2e** = `V − a·dt` against the momentum built from the control's
   surviving particles over the final mass. Measured (run 4): `rel = 1.28e-3`,
   still above the 1e-3 bound, and the residual is **confined to the direction
   the force acts in** — x: `1.28e-3`, z (unforced): `8.0e-5`. That directional
   residual is a clue, not a diagnosis. The chain-order audit locates the
   obstruction: accretion and finalize run at step section 2.87, *before* the
   particle KDK at step 3, so the buffer state the accretion consumed is neither
   the planted velocities nor any post-step read — no measurement made from
   outside the step can be the fold's input. The shader's claim ("accounted to
   fp32 rounding") is about the momentum it is actually handed, and this probe
   cannot yet observe that quantity. **Left unresolved, not excused**: the gate
   keeps its bound and FAILs in run 6. Settling it needs the pending book
   read immediately before the finalize dispatch, which the probe cannot do
   without a partial-dispatch entry point on the engine (a stage-2 item).
   BH2b itself stays in the gate list unchanged — its FAIL stands.
3. **BH3f/BH5b's derivation assumed a reflection-exact deposit.** Measured: two
   equal BHs at ±4 (dual off) receive `Δv0.x = +0.007770`,
   `Δv1.x = −0.009391` — equal-and-opposite to 21%, not to the FFT-rounding 1e-4
   the bound assumed. The source density itself is not reflection-exact at this
   phase: on the x-line through the wells, the trailing node of one kernel holds
   `ρ = 0.4225` while the mirror node of the other holds `0.0`. **The mechanism is
   not isolated** (the range-reduced fixed-point digit atomics are a candidate,
   not a finding), so this is recorded as a measured property of the deposited
   source on this fixture, and both gates keep their frozen bounds and **FAIL**.
4. **BH4's bound assumed a single lattice.** Measured with the frozen fixture
   except for the dual flag: a centred M = 200 BH feels `|Δv| = 2.37e-8` on the
   base lattice (the pre-registered derivation's floor) and **`0.0599` with the
   dual lattice on — 5.76× the §2/BH4 reference kick**. `dual_grid` defaults true
   in both `cassi_physics_engine.gd` and `cassi_sim.gd`, so this is the
   *production* configuration, not a fixture artifact: on the dual lattice the
   sampled field is the average of the base well and a half-cell-shifted copy of
   it, the plant sits on the shifted well's flank, and the self-term does not
   cancel. BH4 keeps its frozen bound and **FAILS**; the base-lattice number is
   recorded as `bh4_self_base_lattice` in the receipt.

5. **The finalize's set 0 was welded to the base field role.** Audit of the live
   chain order (deposit → PDE → base gradient → dual gradient → **accretion →
   finalize** → particle KDK, all barrier-separated) found `_us_bh_fin_0` bound
   statically to `_field_ey/_field_ei/_field_vel`, while _field_role_b — flipped
   by the pp two-fluid chain — makes the particle arm sample `_field_pp_*` on
   alternate steps. The BH would then sample a role the particles are not
   sampling. Fixed with role-matched sets `_us_bh_fin_0_a/_b` selected by
   `_active_bh_fin_field_set()`, mirroring `_active_nbody_field_set()`; the
   gradient bindings are shared by both roles and are unchanged. Run 5 adds
   **BH3g**, a selector/firing regression test: it forces role B and requires
   parity to stay exact *and* the kick to differ from the base-role kick. Both
   halves matter — in this fixture the pp role's buffers are unwritten, so the
   role-B field is zero and the gate does **not** validate nonzero role-B field
   contents; what it validates is that the finalize follows the role at all.
   Firing test: against the pre-fix static binding BH3g reads
   `|Δv_BH − Δv_test| = 5.374e-3` (FAIL); with the fix, `0` (PASS). This defect was reachable only in the pp-chain configuration; the
   default grid two-fluid path never flips the role, which is why the probe's
   earlier runs could not see it.

None of this reopens the tests it corrects: the chain-order audit also confirms
the placement the design requires (finalize after *all* gradient passes, with
barriers before accretion and after the finalize), `bh_field_channel_live()`
already excludes the site/meshless paths, `plant_bh` clears the pending book
rather than seeding it, and `_bh_dyn_buf`/`_bh_acc_buf` sit in the free-RID and
handle-reset lists.

No bound is widened anywhere. **Run log.** run 1: invalid harness (no receipt). run 2: `checks=27
failures=5`. run 3/4: BH2e added, `checks=28 failures=5`. run 5: BH3g added,
`checks=27 failures=5` (incomplete — BH6e/BH6f raised on the renamed set symbol, which is
why the probe's own arm must be re-run, not just edited). **run 6 (final): `checks=29
failures=5`, no script errors.** The five failures are BH2b, BH2e, BH3f, BH5b, BH4. **BH2b/BH2e stay unresolved**:
the measured residual is confined to the direction the force acts in, and the
fold's input instant is not observable from any post-step read — the chain order
shows accretion and finalize run *before* the particle KDK, so neither the
planted velocities nor the control's post-step ones are the buffer state the
accretion reads. Settling it needs a read of `dyn` immediately before the
finalize dispatch, i.e. a partial-dispatch entry point (a stage-2 item).

---

## 4. Planned evidence class

- BH1, BH2, BH6: **T1** — exact ledgers and bit-comparisons against planted values, deterministic.
- BH3: **T1** — bit-parity between two consumers of one law (the strongest form of a parity claim available without a second implementation).
- BH4, BH5: **T2** — measured residuals against pre-stated, derivation-backed bounds; the numbers are the deliverable, the bounds are the contract.

*Registered before execution; the probe script's gates, bounds and plant discipline are frozen to this document.*
