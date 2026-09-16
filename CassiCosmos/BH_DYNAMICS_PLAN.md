# BH_DYNAMICS_PLAN — Black Holes Inside the Field Channel

**Status:** DESIGN + STAGE 1 IMPLEMENTED, RUNTIME VERDICT **FAIL** (24/29 gates: five
failing gates in four categories) — the verdict is honest and diagnostic, not a scaffold
report. Receipt
`_diag/bh_dynamics/bh_dynamics_receipt.json`; run command and the frozen bounds are in
`research/bh_dynamics/BH_DYNAMICS_PREREG.md`, whose §3/§3b record every failure with the
measurement behind it. The failing gates and what they mean:

- **BH4 (self-force) — measured with the dual lattice on.** A centred M = 200 BH feels
  `|Δv| = 2.37e-8` on the base lattice and **`0.0599` with `dual_grid` on — 5.76× the
  d = 4 mutual kick**: the dual-lattice average puts the plant on the flank of its own
  half-cell-shifted well and the self-term does not cancel. `dual_grid` now defaults
  **off** in the engine and in `cassi_sim.gd`, so the shipped configuration is the base
  lattice; the toggle stays for explicit dual experiments.
- **BH3f / BH5b (equal-and-opposite).** Two equal BHs at ±4 receive `+0.007770` and
  `−0.009391` — 21% off, and the pair's common component is a real `−0.006668`/step drift.
  The deposited source is not reflection-exact at this phase (the trailing node of one
  kernel holds `ρ = 0.4225` where its mirror holds `0.0`); mechanism not isolated.
- **BH2b / BH2e (momentum transfer).** The swallow's ledger and book are exact
  (`BH2a`/`BH2c`/`BH2d`), the transfer's residual is `1.28e-3` and **confined to the forced
  direction** (x `1.28e-3`, z `8.0e-5`). Unresolved, not excused, and the directional
  residual is a clue rather than a diagnosis: accretion and finalize run at §2.87, *before*
  the particle KDK at step 3, so neither the planted velocities nor any post-step read is
  the buffer state the accretion actually consumed — the fold's input instant is not
  observable from outside the step. Settling it needs the pending book read immediately
  before the finalize dispatch (a partial-dispatch entry point; stage 2).

What *is* verified: BH mass conservation and the 606.8148 clamp ceiling, the swallow ledger,
the law parity (BH = a massless test body, **bit-exact** through 64 steps), monotone
approach, the channel-off inertness set, the parity of the analytic point term, and
role-following of the finalize's field binding. Three defects found on the way and fixed:
a legacy BH-integrate dispatch that let 256 workgroups race one record (`age` read 7
instead of 6); a probe-side mis-wired readback; and the finalize's set 0 being welded to
the base field role, so under the pp two-fluid chain (whose ping-pong flips
`_field_role_b`) the BH would have sampled a role the particles were not sampling — now
role-matched, with **BH3g** as the gate that catches it (it fails against the pre-fix
binding, passes with the fix). See prereg §3a/§3b.
**Repo:** `CassiCosmos` (engine `scripts/cassi_physics_engine.gd`, shaders `compute/`)
**Date:** 2026-09-15
**Anchors:** `CassiTheory/hypotheses/gravity-from-flow.md` §4.2 (the conditional
BH sector), `CASCADE_GRID.md` §3 (the dual lattice the channel must respect),
`MACHINE_PLAN.md` §3.4 (the BH rung of the matter ladder),
`research/sound_coherence_note.md` (the gapless ρ → c_s = h0/dt merge-timescale
reading).

---

## 0. The defect this closes

The BH sector today is a **bolt-on in the particle force sum**: BH records live in
`bh[4..33]` of the `BHData` header buffer, and the only force they exert is the
analytic softened-Newtonian point sum `bh_point_gravity()` (`cassi_nbody_gravity.glsl`,
call sites 756 / 819 / 885, plus the site twin at `cassi_site_nbody.glsl:545`),
gated by `bh[3].x > 0.5` in *any* gravity mode. Three consequences:

1. **The BH is not a source of the field.** Its mass never enters the fixed-point
   deposit that builds ρ, so it contributes nothing to Φ, to ∇(g·Φ), to the PDE
   source, or to the coherence readouts. A BH is invisible to the field and to
   every field consumer (tree arm, occupancy, observatory, sound).
2. **The BH is not a body of the field.** `cassi_bh_integrate.glsl` moves it by
   `pos += vel·dt` and nothing ever writes `vel` — the record's velocity is dead
   memory. BHs cannot orbit, cannot be captured, cannot be pushed.
3. **BH mass grows by a rule that is not a conservation law.** `mass += acc_rate·q·cell_vol`
   is parameter growth (the retired "expiry" arm zeroed mass outright).

The field channel removes the bolt-on: the BH becomes a **mass source in the same
deposit** and a **test body of the same river law**, with every mass and momentum
transfer written into an account.

---

## 1. What the channel is (Fork 1, stage 1)

One sentence: **the BH deposits into the particle accumulator and is accelerated
by the particle law.**

```
                  ┌──────────────────────── particle chain (unchanged) ───────┐
 clear(ρ,fix) → TSC deposit(pos.w) → convert → Poisson → ∇(g·Φ) → KDK(nbody)
                  │                    ▲                                     │
                  └─ BH deposit(bh.M) ─┘                                     │
                                     BH accretion ──► BH finalize ◄───────────┘
                                     (swallow: mass+momentum)   (KDK on the sampled ∇(g·Φ))
```

Mechanisms, in dispatch order (river modes 0/3/4, no tree gravity, `N_particles ≥ 0`):

| # | Mechanism | Shader | Notes |
|---|---|---|---|
| 1 | BH mass → fixed-point accumulator | `cassi_bh_deposit.glsl` (new) | One thread per record slot (15). The SAME TSC 27-cell kernel and the SAME `fix[]` digit-sum accumulator the particles write, before the same convert. Deposits exactly `bh[base].w` in units of the particle mass `pos.w`. Runs for the base lattice and, when `dual_grid`, for the shifted lattice with the same offset the dual particle deposit uses. Runs at `N_particles = 0` (BH-only). |
| 2 | Analytic term suppressed | `cassi_nbody_gravity.glsl` | In channel mode the host writes `bh[3].x = 0.0` at every writer site. `bh[3].x` keeps its documented meaning ("analytic point-gravity gate"); no ABI change and no reader changes. |
| 3 | Accretion with a momentum book | `cassi_bh_accretion.glsl` (edit) | A swallowed particle's mass goes to `bh[base].w` (as today) and its momentum `pos.w·vel[i]` is atomically added to `BHDyn` slot `b`. Gated by the accretion PC's spare float (index 3) so the legacy path writes nothing new. |
| 4 | BH motion | `cassi_bh_finalize.glsl` (new) | Replaces the legacy integrate dispatch. Per active slot: `P = ΣDyn`, `M = bh[base].w`, `v = P/M`, `a = river_force(sample_fields(pos))`, `v += a·dt`, `pos += v·dt`, then re-book `ΣDyn = v·M`. The BH samples the **identical** `∇(g·Φ)` + π/ρ + `G_N` the particles sample through the shared include. |
| 5 | q-growth retired while live | — | The legacy `cassi_bh_integrate` dispatch is skipped in channel mode, so `acc_rate·q·cell_vol` never runs. `bh_max_age` expiry stays available in the legacy arm only. |

### 1.1 One definition of the law

`compute/cassi_river_force_common.glslinc` (new) holds the sampler and the force
assembly that both consumers use: `idx3_coarse`, `sample_coarse_grad`, `idx3`,
`FieldSmp`, `sample_fields`, `river_pi_over_rho_clamped`, `river_field_acc_common`,
and `river_acc_at(wp)` — the last being the whole law at one world point
(sample → π/ρ clamp → assemble), which is what the BH finalize calls for both of
its per-step evaluations. The nbody river arm keeps its telemetry-instrumented
`chord_g_from` and calls the common assembly; the BH finalize calls `river_acc_at`
without telemetry. The includer supplies the names the include's functions
reference (`pc` with `N_f/phi/xi/gravity_mode`, `bh[]`, and the buffers
`ey/ei/fvel/grad/g2/cgrad`), so the extractor stays bit-identical for the particle
path (same expressions, same order, same mix trees) and the BH cannot drift into a
second law.

### 1.2 The BH is a test body: the particle arm's integrator, mirrored

A BH is not "accelerated by the field" in its own integration scheme. It runs the
particle arm's cached-acc KDK leapfrog, expression for expression
(`cassi_nbody_gravity.glsl` §Cached-acc KDK):

```
v½ = v + a_prev·dt/2 ;  p′ = p + v½·dt ;  a′ = F(p′) ;  v′ = v½ + a′·dt/2
```

with `a′` cached in `_bh_acc_buf` (one vec4 per slot) for the next step's first
half-kick. `pc.pass_mode > 0.5` is the **seed step** — the live predicate's rising
edge, or a fresh `plant_bh` — where no `a_prev` exists yet: the pass evaluates the
warm-up term `F(p)` itself, first, in the same dispatch, exactly as the particle
arm's one-time `pass_mode == 2` warm-up does. Both consumers therefore evaluate
the same gradients in the same step (nothing writes the field between the BH
finalize and the particle pass), so **a BH planted on a massless test particle's
(p, v) follows that particle's trajectory to the last bit** — the claim BH3 tests.

The BH's record `vel` is the live velocity (the finalize writes it every step).
Momentum enters through a **pending** account: `cassi_bh_accretion.glsl`
atomicAdds `(m·v, m)` into `_bh_dyn_buf[slot]`; the finalize folds it
momentum-conservingly, only when something was swallowed,

```
v ← (v·(M − ΔM) + Σm·v) / M        (ΔM = the book's w lane, M the post-swallow mass)
```

and then zeroes the book. A step with **no** swallow performs no arithmetic on `v`
at all — which is what makes the parity claim exact rather than approximate — and
the book can never go stale because nothing in it outlives one finalize. A planted
BH is written by the host (`plant_bh(slot, pos, mass, vel)`), which clears the
pending book and arms the seed step.

### 1.3 Anti-double-count

A BH's pull reaches a particle through exactly one of two routes, never both:
`bh[3].x = 0.0` kills the analytic route on every dispatch that runs in channel
mode, and the field route carries the BH's mass because the deposit ran. The
finalize is the sole route by which the BH itself accelerates — the analytic term
never acted on the BH (it is a particle-pass term), so there is nothing to
subtract. The engine's live predicate is

`black_holes_enabled ∧ bh_field_channel ∧ ¬gridless_physics ∧ ¬(meshless_mode ∧ meshless_gravity) ∧ gravity_mode ∈ {0,3,4}`

— outside it, the channel is inert (no deposit, no finalize, no momentum writes)
and the legacy chain runs untouched.

### 1.4 Ledger

| Account | Before | After |
|---|---|---|
| Particle live mass `Σ pos.w` | `Σ m_i` | `Σ m_i − Σ swallowed` |
| BH mass `Σ bh[base].w` | `Σ M_j` | `Σ M_j + Σ swallowed` (deposit adds no mass of its own) |
| Particle momentum `Σ m_i v_i` | `Σ P_i` | `Σ P_i − Σ swallowed` |
| BH momentum `Σ M_j v_j` | `Σ M_j v_j` | `Σ M_j v_j + Σ swallowed` (the pending book carries it into `v`) |
| Field Σρ (grid) | particles only | particles + BHs (one TSC copy of each, partition of unity) |

Nothing is created or destroyed on the particle+BH ledger by the deposit the
channel adds. The field is an *external* account for the ledger's purposes: it
carries force work (`∫ −a·v` through ∇(g·Φ)) and is recorded, not balanced.

**Source ceiling (derived from the deposit's own clamp; gated by BH1c).** The
deposit clamps each per-cell contribution at `2^32 − 256` counts. The TSC kernel's largest weight
product is `0.75³ = 27/64` (a record at a node-aligned point), so a single
depositing mass above

`m* = (2^32 − 256) / (27/64 · 2^24) = 606.8148…`

saturates its own source: with `m = 700` at the world origin the centre cell
clamps and `Σρ = 660.6875` instead of 700. Below `m*` the ledger is exact to the
partition-of-unity rounding. BH masses are therefore a *specified* quantity in
deposit units, not a free one; the probe gates both sides of the boundary.

### 1.5 Toggles, ABI, buffers

- `bh_field_channel` (engine var + cfg key), **default off** ⇒ the new shaders are
  never loaded, the new pipelines are never created, no dispatch is added, no
  header float changes value: the default configuration is bit-identical.
- **No ABI change.** `BHData` keeps 36 vec4s and its current field meanings; the
  momentum gate rides the accretion push constant's unused float (index 3), and
  the finalize's push constant is the nbody's own 15-float layout, pushed verbatim.
- Two new resources, both 15 slots × 16 B: `_bh_dyn_buf` (the **pending** momentum
  account: xyz = `Σm·v`, w = `Σm`) and `_bh_acc_buf` (the cached-acc KDK state).
  Both allocated with `_bh_buf`, both in the shutdown free list.
- `pos/vel/acc` allocate `max(N_particles, 1)` elements so the convert dispatch is
  unconditional — with `N_particles = 0` the old zero-size buffers produced RID()s
  and the whole clear→deposit→convert chain was skipped, which would have made a
  BH-only run deposit into a fix buffer that never reached ρ.

### 1.6 Claim boundary

This is Cassi dynamical closure: a BH is a persistent mass concentration in the
two-fluid medium that sources and responds to the same field as matter. It is
**not** a GR black hole: no horizon, no spin, no ISCO, no emission, no merger
remnant. `FieldVel` is `(∂tEY, ∂tEI, 0, ε²)`, so c_s = h0/dt remains the
merge-only heuristic it always was, and no signal-propagation claim is made here.

---

## 2. Deferred (stated so stage 1 is not read as more than it is)

- **Stage 1b — the twins.** `cassi_sim.gd`'s inline chain and the gridless/site
  arm (`cassi_site_nbody.glsl`, site BH records) mirror the same channel after the
  grid engine's gates pass. Stage 1 wires the engine only.
- **Stage 2 — the σ-core pair arm.** A separate `bh_medium` operator and the
  analytic σ-core pair force, with its own shared fixtures. "BH mass in the
  Poisson source" describes stage 1; stage 2 must not reuse that phrase.
- **Stage 3 — formation.** BHs enter the channel host-seeded. The `gid % 15`
  nucleation slot map and the condensation path stay legacy until the σ-core arm
  defines what a BH *is* in the field.
- **Self-force.** The BH samples its own well. The probe bounds it (BH4) rather
  than hiding it; a corrected kernel is only worth building if the measurement
  says the bound matters at the radii of interest.
- **Emission / horizon / spin / merger.**

---

## 3. Gates (`scenes/verify_bh_dynamics.tscn`, windowed, one at a time)

**The authority is `research/bh_dynamics/BH_DYNAMICS_PREREG.md`** — the statistic,
the derivation-backed bound, the decision tree and the stopping rule for every
gate below were fixed there *before* the probe ran, and none of them may be
widened after a run to make a gate pass. Launched with the console exe, never
`--headless`. Receipt: `res://_diag/bh_dynamics/bh_dynamics_receipt.json`; the
exit code is the contract.

| Gate | Claim | Decision rule (bounds derived in the prereg) |
|---|---|---|
| **BH1** source ledger | A planted BH's mass reaches ρ through the deposit, once, on both lattices — and the deposit's own ceiling is characterised. | BH-only engine (`N_particles = 0`): `Σρ/ΣM == 1 ± 1e-5` for 200+100 and for a single 600; `Σρ == 660.6875 ± 0.007` for 700 (the predicted clamp loss of one `0.75³` cell, i.e. the ceiling `m* = 606.8148`); `Σρ/M == 1 ± 1e-5` with the dual lattice on; header float 48 `== 0.0` exactly while live. |
| **BH2** momentum audit | Swallowing transfers momentum, not just mass. | Single centred BH (self-force-null) + a mirror-symmetric 8-particle cloud with distinct velocities, one step: BH mass `== M + Σm` within 1e-4; `V == Σm·v/M_total` (predicted `(0.05, 0, 0.0272…)`) within 1e-3 relative; the pending book `== 0` exactly afterwards; every swallowed particle `pos.w == 0`. |
| **BH3** law parity | The BH *is* a test body of the river law — the particle arm's own integrator, mirrored. | Two equal BHs at `±4` plus two **massless** test particles at the same points: `|Δv_BH − Δv_test| == 0` bit for bit after step 1 and after 64 steps, and `|Δp| == 0` after 64. Non-zero is a FAIL unless it is ≤ 2^-22 relative with no super-linear growth, which reads PASS(1ULP) with the measured bound recorded. Anti-vacuity controls: each BH kicked toward the other (sign), `|Δv0+Δv1|/|Δv0| ≤ 1e-4`. |
| **BH4** self-force bound | The self-force at a symmetric point is at the discretisation floor. | Single centred BH: `|Δv_self|/|Δv_mutual at 4.0| ≤ 1e-3` (derivation estimate ≈ 3.4e-6; the measured ratio is the deliverable). |
| **BH5** pair dynamics | Two masses attract through the field, and the position change agrees with the independently measured kick. | Separation monotone non-increasing over 64 steps (slack 1e-9) with `sep_final < sep_0`; the first step's `Δsep` matches `−|Δv|·dt` (BH3's own measurement, same config) within 5%. |
| **BH6** default-off | The toggle is additive on every live buffer and dispatch. | Channel OFF: `Σρ == 0` exactly; header float 48 `== 1.0`; pos/mass/vel of a planted record bit-identical after a step while its age advances by exactly 1 (the legacy integrate still runs); the new shaders/pipelines/sets all invalid; `_bh_dyn_buf` and `_bh_acc_buf` all-zero; the predicate false in modes 1/2/5 and under tree gravity and in the gridless chain. Production bit-identity is `verify_core`'s job. |

## 4. Files

| File | Change |
|---|---|
| `research/bh_dynamics/BH_DYNAMICS_PREREG.md` | new — the frozen gate bounds, decision tree, stopping rule and scope boundary the probe is judged against |
| `compute/cassi_river_force_common.glslinc` | new — shared sampler, force assembly and `river_acc_at` |
| `compute/cassi_bh_deposit.glsl` | new — TSC deposit of `bh[..].w` into `fix[]` (base + dual) |
| `compute/cassi_bh_finalize.glsl` | new — the BH's mirrored cached-acc KDK, pending-book fold, seed step |
| `compute/cassi_nbody_gravity.glsl` | extract the sampler/assembly to the include (bit-identical) |
| `compute/cassi_bh_accretion.glsl` | add the momentum channel (gated on PC slot 3) |
| `scripts/cassi_physics_engine.gd` | toggle + predicate, `_bh_dyn_buf` + `_bh_acc_buf`, two shaders/pipelines/sets, deposit + finalize dispatches (base and dual), accretion momentum gate, header float 48, min-1 particle buffers, `plant_bh()` |
| `scripts/verify_bh_dynamics.gd`, `scenes/verify_bh_dynamics.tscn` | new probe |
| `verify/README.md` | probe row |
| `scripts/contracts/layout.gd` | accretion PC slot 3 = the momentum channel; `_bh_dyn_buf` = a pending (per-step) account |

The experiment is a *measurement of the frozen design*, not a tuning loop: once
the run lands, the receipt's numbers go into §3 verbatim, and any gate that fails
is reported as a failure with its measured value rather than repaired in place.
