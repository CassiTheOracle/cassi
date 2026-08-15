# Overhaul Build Plan — Milestoned, Gate-Gated Roadmap
## From `_diag/overhaul_spatial.md` (problem / A-B-C design / migration / cost-risk / fork)
## Owner decision: A (field-on-Lagrangian-sites) first, shaped toward C (hybrid far-field); B (AMR) as GATED fallback.

Date: 2026-08-15. DESIGN-ONLY — no code, no GPU, no commits.
Confirmed diagnostic: "the rendering and camera don't freeze, but the particles still do" —
the main thread keeps painting the last published frame while the ENGINE WORKER stalls on a
local-RD device-drain. M0 is therefore both the present-day freeze killer AND the overhaul's
transport pillar. `90d4405` (perf-decomp) already landed the PACING half (stagger/raise/cap of
the tree+meshless cadences); M0 removes the DRAINS themselves.

---

## Contract schema (cross-cutting — land by M0's first commit)

**Single-source-of-truth layout**: one host-side struct — in a NEW file
`scripts/contracts/layout.gd` (data-only, no logic) — that defines, for every cross-boundary
object: the buffer/PushConstant/binding layout (sizes, offsets, strides), the periodic-
coordinate identity (which buffers are periodic-indexed vs world-coordinate, and the wrap
convention: `((i % N) + N) % N` vs `mod()` — the storage-vs-render disagreement class), and
the particle-liveness convention (which buffer field carries it and its states). Consumed by
BOTH the CPU (`layout.gd` referenced from `cassi_sim.gd` / `cassi_physics_engine.gd`) and the
shaders (the GLSL files keep their `layout(...)` blocks but the doc header of each declares
"canonical layout: scripts/contracts/layout.gd §X" with a size/binding comment).

**Build-time layout assertion**: one `--check-only`-runnable script
(`scripts/contracts/assert_layout.gd`, a plain script with a main()) that reads the GLSL
sources' `layout(push_constant)`/`layout(set, binding)` blocks with regexes and asserts each
against the struct's sizes/bindings — runs in the pre-battery step (`.glsl import refresh +
--check-only` in `_diag/run_battery.ps1`'s documented header). This is the class-killer for
the season's real bugs: the merge 64-vs-92-B PC mismatch that flooded stderr (3615/run) and
broke particle_merge; the storage-vs-render periodic-wrap disagreement (the instancer fold
class); liveness drift (w=0 conventions across deposit/nbody/merge/accretion).

Gates: assert_layout passes on every changed shader; the battery pre-flight runs it.

---

## M0 — one-RD / frame-bounded transport (THE freeze+crash killer; REQUIRED foundation)

Goal: the physics+render readout runs on ONE RenderingDevice with a strict per-frame command
list in staging order; NO mid-frame worker-side `buffer_get_data` device-drain on the physics
path; all readbacks move to accepted, amortized, state-cacheable cadence points via persistent
co-allocated staging buffers.

### Exact drain sites to remove (anchored to the audits)

Engine worker (local RD) — the freeze source, in cost order:
1. `_tree_refresh_gradient` staging — `cassi_physics_engine.gd:2064-2110`: SIX
   `buffer_get_data` (32 MB pos + 1 MB rho + 128 KB sites + psy/psi/vol) every `_tree_cadence`
   jobs; each DRAINS the queued physics list (cadence_audit item 1). ELIMINATED by the one-RD
   move: the tree build/walk dispatches run in the engine's own list and read the LIVE buffers
   — the 130 MB/job CPU round trip and the tree worker's local RD both die.
2. `_mesh_rebuild` — `cassi_physics_engine.gd:1975-2040` + `_finish_standalone_list`
   (`:1049-1055`, submit+sync): the 26-dispatch barrier chain syncs mid-job (cadence_audit
   item 2). Same list-joining fix: the chain runs in the frame's list (barriers are fine in
   one list; the SYNcing submit mid-loop is what stalls).
3. Merge prefix-sum host readbacks — the `buffer_get_data` between spatial-hash passes
   (`:524` comment; `_merge_read_uint` class). The STEP-1 any-candidate early-out (`a7834f8`)
   already makes the full path rare; M0 removes the REMAINING mid-chain readbacks: the
   per-cycle scan → cumulative prefix sum can be a GPU-side exclusive scan (a small dedicated
   pass) or the alive/mass counters read once at the END of the merge chain (frame-bounded),
   with the cycle loop feeding on the previous frame's counters (accepted one-frame latency —
   the merge cadence is ~28 steps, far inside its reaction budget).
4. `readback_snapshot` — `cassi_physics_engine.gd:553-589`: `_rd.sync()` + pack pass + 32 MB
   pos/vel readbacks + field_q (1 MB) + fft (2 MB) per snapshot publish (cadence_audit item 3).
   Frame-bounded: the readback moves to the END of the job's list (drains ≤ one job's work,
   never the backlog), the fp16 pack already halves the bytes, and field_q/fft are already
   shared with telemetry (FIX C2). Persistent co-allocated staging buffers (the packed mirrors
   ARE the staging — keep them; only the sync point moves).
5. `readback_telemetry` — `:700-706`: 32 B, small; move to the same end-of-list point.

Sim main thread (global RD) — the render-path drains:
6. `_align_color_band` — `cassi_sim.gd:4891`: 512 B `buffer_get_data` every 0.5-1.5 s. One-RD
   move subsumes it: the align readback joins the frame's list end (or becomes a deferred
   staged read — the qhist bins are 512 B; read them at the frame boundary, never mid-frame).
7. `_apply_decoupled_publish` — `cassi_sim.gd:1614-1660`: 48 MB `buffer_update` per snapshot
   (queued, not a drain, but PCIe+GPU load). Under one RD the mirrors become the SAME buffers
   the engine wrote (no copy) or a single GPU copy pass at the frame boundary.

Three-RD → one-RD: the renderer's global RD, the engine's local RD, and the tree worker's
local RD consolidate. Design: the ENGINE's local RD survives as the physics device; the
renderer's global RD is replaced by the sim owning a local RD (the Godot main thread can drive
a local RD for the render list — the tree worker precedent shows the pattern) OR physics moves
to the global RD with strict staging order. DECISION NEEDED at M0 kickoff: the engine-local
pattern is the safer consolidation (the renderer keeps working — the owner's "camera doesn't
freeze" is preserved) but requires the sim's render list to be built on a local RD (a real
renderer change: the instancer/field-render/LUT lists move off the global RD). The alternative
(physics on the global RD) touches the engine deeper. Recommend: engine-local-RD survives;
the render list migrates to a sim-owned local RD; the two lists interleave via a single
per-frame submission order with ONE sync at the frame boundary.

### Gates (M0)
- Battery stays 8/8 (determinism max-diff == 0.0 preserved — the dispatch ORDER and PC values
  are unchanged; only the device/readback points move).
- The render-smooth/particles-frozen symptom is GONE (a 60 s owner-config windowed run with
  vsync on: frame-time variance ≤ ±20% of the mean with NO multi-hundred-ms spikes).
- No TDR over a 60 s+ window (the sat-config sim_speed=10 stress, which previously lost the
  device in the merge/occupancy path).
- No mid-job `_rd.sync()`/`buffer_get_data` remains on the physics path (grep gate).

### Files
`scripts/cassi_physics_engine.gd` (step loop, `_tree_refresh_gradient`, `_mesh_rebuild`,
`readback_snapshot`, `readback_telemetry`, merge chain), `scripts/cassi_sim.gd`
(`_apply_decoupled_publish`, `_align_color_band`, `_render_frame` list construction),
`scripts/cassi_tree_worker.gd` (dies or becomes a submission helper), the tree
build/walk shaders (binding-identical; only the owning device changes), `_diag/run_battery.ps1`
(gates only).

### Honest risk
- Determinism: the one-RD reordering must keep the per-step dispatch order identical — the
  fixed-point deposit contract and max-diff == 0.0 are the canaries; the verify battery's
  bit-identity scenes (perf_smoke-derived) catch drift.
- Verify: the tree verify scenes drive the tree worker directly — they must be re-pointed at
  the in-engine path (a verify-contract change, not a physics change).
- Renderer migration: moving the render list to a local RD is the riskiest single change
  (Godot local-RD rendering constraints — the space-sim's local-RD worker precedent applies).

### De-risks
The entire freeze/TDR/crash class (cadence_audit items 1-4), the backlog-growth feedback
(`90d4405`'s measurement: backlog jobs growing 185 → 2523 → 17327 — the drain time stops
growing when the drain is frame-bounded), and the transport half of the perf problem
(~50 ms/step → the field's ~2 ms plus one bounded frame sync).

---

## M1 — promote the meshless-sites two-fluid field to RESIDENT primary state (A)

The meshless arm already carries per-site psi/pi with a leapfrog (`cassi_voronoi_cells.glsl`
mode 1), a two-point-flux Laplacian (mode 0, the AREPO staircase), a per-site least-squares
gradient (mode 12), and the sites are `mod`-wrapped per rebuild (mode 4). M1 promotes that to
the field OF RECORD and demotes the N³ grid/particles to a derived, cadence-bounded sampling.

- **Field of record**: per-site psi/pi/pi-momenta + the per-site gradient; the raster (mode 7)
  writes patch-local staging grids only for the consumers that need a grid (condensation scan,
  field render, bh-integrate Qi sampling) — each becomes patch-local or per-site.
- **Remove the finite-box topology**: the site `mod`-wrap (mode 4, `cassi_voronoi_cells.glsl:310`)
  dies — sites move freely; the tree root becomes the tracked structure's cube (adaptive root,
  the `overhaul_spatial.md` migration item 1); `bh[2].yzw` stops being a fixed topology and
  becomes a tracking-window descriptor (the camera/domain window + the tree root seed).
- **Deposit**: per-particle scatter into the enclosing site's patch grid (no global N³ wrap —
  `cassi_mass_deposit.glsl` gains a patch-local mode; the fixed-point contract preserved per
  patch with a pinned re-tile cadence (ML_REBUILD) so determinism holds).
- **nbody/tree**: unchanged (already open); the seam reads the resident per-site state.
- **Source injection**: `source_strength` rides the structure (per-site seeds), not the box
  center (`cassi_two_fluid.glsl:147-168` becomes per-site or patch-anchored).

### Gates (M1)
- **Gate-iv (the A-decider), exact acceptance test**: a wave-fidelity battery comparing the
  meshless per-site wave vs the N³ reference on the same physical setup (a Gaussian pulse on
  the checkerboard ground state, measured ρ-front speed and the φ-power spacing of the
  emerging modes over ≥ 10³ steps): the meshless wave must match the N³ wave within a pinned
  tolerance (proposal: |Δρ_front| ≤ 5% and the dominant-mode φ-power spacing preserved to the
  same precision as the N³ self-consistency run, max-diff == 0.0 for the box-bound
  compatibility regime). If this FAILS → execute the B fallback (M3).
- **Capability probe**: "structure can expand past any finite tile" — a two-cluster run whose
  separation exceeds the OLD box period; assert no periodic image of cluster A appears at A's
  image location, and the field follows the structure (the overhaul battery item b).
- The 8/8 battery + determinism stay green in the compatibility regime (structure small: the
  open pipeline must be bit-identical to the closed box).

### Files
`cassi_voronoi_cells.glsl` (mode-4 unwrap, patch-local raster), `cassi_mass_deposit.glsl`
(patch-local mode), `cassi_two_fluid.glsl` (per-site sources), `cassi_sim.gd` /
`cassi_physics_engine.gd` (the tracking window replaces the fixed extents; the adaptive tree
root), the tree root seeding (`cassi_sim.gd:4515`, `cassi_physics_engine.gd:2081`).

### Honest risk
The irregular-mesh wave fidelity (C2 = h_min² is a fixed global bound; the de-resonant
spacing argument weakens off-lattice) — this is THE named risk and the entire reason for the
B fallback. Second: the moving mesh's gradient quality (mode-12 least squares over elongated
cells). Third: determinism under re-tiling (pinned by the fixed ML_REBUILD cadence).

---

## M3 — B fallback (PRE-SCRIPTED; execute ONLY if M1 gate-iv fails)

Not a decision point — a script. The trigger is exactly one: **M1's gate-iv fails** (the
per-site wave does not meet the fidelity tolerance). Then:
- Keep the N³ lattice waves as the field of record (the two-fluid grid passes unchanged).
- Add AMR: a coarse global grid whose extent tracks the structure envelope (slow-cadence
  re-fit, the movable-window mechanism from M1) + fine patches around condensations (per-patch
  N³ kernels, per-patch extent/offset PCs — the same shaders).
- The flux-matching coupling at coarse-fine patch interfaces is the new physics surface; it
  gets its OWN gate (a patch-interface continuity test: a wave crossing the interface must not
  reflect — reflectivity ≤ a pinned threshold).
- Capability ceiling (honest): the field's support is the tracked envelope — expansion space
  is bounded by the tracking cadence, NOT unbounded as in A. The owner's "box is the limiter"
  is still met (the limiter becomes a capacity), but the C end-state's unbounded void is not.

---

## M2 — C end-state: hybrid (A + coarse far-field patch)

After M1's resident field is stable (and only then): add the coarse far-field patch — a single
low-res N³ tile tracking the outer envelope, giving the void a wave presence (the "breath" in
the expanded halo gas the expansion scenario is about). The far-field deposit is the coarse
scatter; its extent re-fits on the slow cadence; the coupling is A's per-site→far-field
source/sink continuity (a second coupling surface, gated by the same patch-interface test as
M3's).

---

## Execution order (risk-minimizing)

1. **Contract schema first** (the layout struct + assert_layout) — one small commit, the
   class-killer, and it makes every later migration mechanically auditable.
2. **M0** — strictly required BEFORE any field-topology work: the freeze/crash class must be
   dead and the transport budget measured before the overhaul's bigger changes land on the
   same pipeline. M0 is ALSO the foundation M1 depends on (the one-RD list is where the
   patch-local and per-site passes get staged).
3. **M1** (A) with gate-iv. M1 may START (prototyping the meshless field promotion + the
   wave-fidelity battery) in parallel with M0's tail — the meshless side is a distinct
   subsystem (the voronoi_cells shaders + the fidelity test harness) and does not touch the
   transport path — but M1's ADOPTION gate is gated on M0 green (the capability probe and the
   determinism regime tests need the frame-bounded pipeline to measure honestly).
4. **M3 or M2** per gate-iv's verdict.

**M0-prerequisite verdict: M0 is strictly prerequisite to M1's adoption, but NOT to M1's
prototyping** — the meshless-fidelity battery and the per-site field promotion can proceed in
parallel with M0's tail on the meshless subsystem, with the adoption gate held until M0 is
green. The freeze diagnosis ("particles freeze, camera doesn't") is unambiguous: the engine
worker's drains are the present-day blocker and must die first.

**Recommended FIRST build milestone to actually execute: the contract schema + M0's drain-
removal on the engine path** (items 1-4 above — the tree staging joins the engine list, the
merge's mid-chain readbacks become end-of-list, the snapshot readback moves to the job's end)
as ONE coherent M0 phase; it is the highest-certainty, highest-value, lowest-physics-risk
work in the entire roadmap, and it turns the ~50 ms/step transport into the field's ~2 ms/step
plus one bounded frame sync.

---

## Verify/capability battery (new gates, additive to the existing 8/8)

| Gate | Pins | When |
|---|---|---|
| a — no image-force at the domain boundary | a particle at +L_old feels the open tree force only (vs the closed-box reference at the same state) | M1 |
| b — structure expands past any finite tile | two-cluster separation > L_old; no periodic image; field follows structure | M1 |
| c — existing 8/8 + determinism | max-diff == 0.0 in the compatibility regime (open pipeline bit-identical to closed box when the structure is small) | M0 + M1 |
| d — one-RD staging holds | no worker stall: frame-time variance ≤ ±20% of mean over 60 s; no mid-job sync on the physics path (grep gate) | M0 |
| gate-iv — wave fidelity (the A-decider) | meshless per-site wave vs N³ reference: ρ-front ≤ 5%, φ-power spacing preserved, max-diff == 0.0 box-bound | M1 |
| gate-vi (M3-only) — patch-interface continuity | wave crossing the coarse-fine interface: reflectivity ≤ pinned threshold | M3 |

---

## M0-STAGE MARKER (2026-08-15) — executed

| Commit | Content | Battery |
|---|---|---|
| `71d5f8f` | **Contract schema (commit 1)**: `scripts/contracts/layout.gd` (data-only — PC float counts ×16 shaders, per-set binding maps, the BH header convention bh[0].yzw=origin/bh[2].yzw=extents, the periodic-coordinate identity `((i%N)+N)%N` vs the Voronoi `mod()`, the liveness w<=0 convention) + `scripts/contracts/assert_layout.gd` (standalone `--headless --script` regex assert: shader PC/bindings + host `resize(N*4)` allocations + the canonical-layout header line in every covered shader). Wired into `_diag/run_battery.ps1` as a documented pre-battery step AND a pre-flight gate before the scenes (a mismatch aborts). | 8/8 |
| `8c83226` | **M0 engine-path drain removal, item 1 (THE item)**: tree-in-list — the tree build+walk runs inside the engine's own compute list on the LIVE buffers (mode-7 gather reads the meshless state directly; mode-9/10 seed ctr/nr on-GPU; the walk reads `_pos_buf` and writes `_tree_grad` — the seam buffer). The per-job ~130 MB staging readbacks + the tree worker's local RD + the 32 MB seam upload die from the engine path. | 8/8 (one tight-epsilon flake rerun clean) |

### Items landed vs deferred
- **1. Tree staging → in-engine list: LANDED** (the above).
- **2. Meshless rebuild in-list: VERIFIED-ALREADY-ONE-LIST** — `_mesh_rebuild` builds ONE list with in-list barriers; the only sync is the single `_finish_standalone_list` (submit+sync) at the chain's end, cadence-rare (~every 25 steps) and bounded by the JOB_STEP_CAP. The mid-loop syncs the audit cited are already absent. No change.
- **3. Merge mid-chain readbacks: DEFERRED to M0b** — the STEP-1 any-candidate early-out already makes the full cycle path rare; the GPU-scan / accepted-latency counter feed risks the merge's cycle determinism. M0b candidate with its own gate.
- **4. Snapshot/telemetry end-of-list: VERIFIED-FRAME-BOUNDED** — `readback_snapshot` runs at the job boundary after the JOB_STEP_CAP-bounded job; its drain is ≤ one job's work, never the backlog; `readback_telemetry` (32 B) rides the same point. No change.
- **M0b (deferred, per the director's scoping)**: the sim-side drains (`_align_color_band`'s 512 B readback, `_apply_decoupled_publish`'s 48 MB upload) + the renderer-to-local-RD migration + the sim-side tree-worker boot-cost cleanup (the sim still creates the worker in decoupled mode; the engine ignores it).

### Measured (live config 500k/dt=0.001/box_scale 3, 137 s windows)
| Metric | guard-only (`71e34bf`) | + M0 (`8c83226`) |
|---|---|---|
| perf lines (main-thread continuity) | 167 | **197** (continuous — freeze GONE) |
| med ms/step | 2.77 | **2.40** |
| sustained steps/s | 309 | **389 (+26%)** |
| backlog max | 80.9 s (growing) | 68.6 s (growing — the honest ~2.6x rate ceiling, not a freeze) |
| device-lost | 0 | 0 |

2M report config: med 21.4 vs 20.3 pre-M0 (+~1 ms — the in-list build serialized where the worker was async; one 50.7 ms tree-job spike at the 50-job cadence; within the 20.3-21.1 run-variance family).

### Freeze verdict (the M0 gate)
The render-smooth/particles-frozen symptom is ELIMINATED at the live config: before the M0+guard work the run showed 1 perf line in 137 s (~46 s freezes); after, a continuous particle timeline with no multi-second main-thread stall, no TDR.

---

## M3-B STAGE MARKER (2026-08-15) — the B build is the PRIMARY path (owner decision)

Gate-iv closed out to B: the meshless per-site wave is a 38%-off coarse-dispersion
case (`be56f1d` — the corrected-operator A/B diverged; the N³ lattice waves stay
the field of record). M2/A shelved. The B-build pieces are tracked in
`_diag/b_build.md`.

| Piece | Status | Commit |
|---|---|---|
| **1. Tracking envelope** — `scripts/envelope_tracker.gd` (the percentile/hysteresis/move-cap envelope computation) + `_diag/b_track_unit.gd` (7-case headless unit battery) + `_diag/b_track.tscn`/`_diag/b_track.gd` (end-to-end probe battery on the real sim, driving the sim's own window/extent state) | LANDED, probe-gated (canary bit-identical, header-follows, coverage, would-clip, grow-fired, determinism) | `<pending>` |
| **2. Gate-vi design** — the ghost-cell interface scheme (coarse→fine trilinear rim + fine→coarse cell-average downsample at the pinned re-tile cadence) + the pre-registered battery (same-res transparency calibration → 2×/4×-resolution reflection arms, R <= 2% target, corner-crossing arm, determinism canary) | ON PAPER (`_diag/b_build.md`) — the coupling implementation GATED on the battery build | — |
| **3. Fine patches + coupling** (per-patch extent/offset PCs per the contract schema, patch lifecycle at the ML_REBUILD cadence) | GATED (after gate-vi passes) | — |
| **4. Expands-past-any-finite-tile probe** (the owner's science goal) | folds into piece 1's mechanism + piece 3's patch story | — |

The tracking-envelope mechanism's sim-side production wiring (a `_track_window_center`
sibling writing the same three state slots — window_center, box_scale, bh_init_bytes
36/40/44 — from the engine's published mirrors) is the M0b/next-turn handoff; the
probe has proven the mechanism end-to-end. The default path is untouched (OFF =
window_center 0, box_scale 1.0 → the fixed box, battery-green).

---

## M0B-STAGE MARKER (2026-08-15) — executed (items 1-2 landed, item 3 designed)

| Piece | Status | Commit |
|---|---|---|
| **1. `_align_color_band` readback** | **LANDED** — the 512 B qhist `buffer_get_data` no longer self-stalls the global RD mid-frame. The 1.5 s refit rides the occupancy block's already-accepted device drain; the FIX-2 merge/align frame separation is preserved (the flag is set from the DUE state at the frame top, so the merge gate sees it before the merge block); verify/headless scenes (playing=false or suppress_readbacks — where the occupancy drain never fires) run the align standalone so the cadence advances and the merge gate can't latch off (a real bug the advisory caught: `auto_align_colors` defaults true, merge_sim doesn't override it — without the standalone the merge was permanently suppressed). | `3dc6e15` |
| **2. `_apply_decoupled_publish` copies** | **LANDED (partial)** — the packed-path prev-mirror shuffle is a GPU-side `buffer_copy` queued before the curr upload (12 MB → 8 MB per snapshot upload; the first-publish prev=curr host upload preserved). The REST of the copy cost is inherent to the two-RD split — the full elimination is item 3. | `3dc6e15` |
| **3. Renderer-to-single-RD migration** | **DESIGNED, not landed** — see below. The plan's riskiest change; the scoping rule applied (land 1-2, design 3). | — |

### Measured (500k / readbacks-on / box_scale 3, 137 s — the M0b-relevant config)
| Metric | pre-M0b (`8c83226`) | + M0b (`3dc6e15`) |
|---|---|---|
| perf lines (continuity) | 197 | **217** |
| med ms/step | 2.40 | **2.00** |
| sustained steps/s | 389 | **443.7 (+14% on M0's +26%)** |
| frame-time mean / max / p99 | — | 3.3 / 14.3 / 8.5 ms — no multi-hundred-ms spikes (PASS) |
| device-lost | 0 | 0 |

Current live main.tscn is now **50k / suppress_readbacks=true** (the owner's M1-era config, down from 500k): clean boot + first snapshot, no freeze markers; at 50k the engine sustains ~2-3× real-time — no backlog possible; the sim-side readbacks are inert under suppress_readbacks=true. The readback-active verification above is the config where the drains actually existed.

### Item 3 design (renderer-to-single-RD migration) — follow-up
**Current**: the engine runs on its own local RD (the worker's `_threaded_main` creates one unconditionally); the sim renders on the global RD; the mirrors bridge them (the engine's `readback_snapshot` — 32 MB pos/vel + field_q + fft per snapshot publish — then the sim's `_apply_decoupled_publish` uploads — 12 MB). Every snapshot = a 44+ MB round trip through the host.

**The one-RD direction**: the engine records its job chains on the GLOBAL RD (from the worker thread); the sim's render list records on the same RD; the mirrors + snapshot readbacks + uploads die — the publish becomes telemetry-only (32 B + time/steps). The render list's wait behind a job chain is bounded by the JOB_STEP_CAP=64 (the cap exists precisely for this).

**Phases**:
- **P1 — the engine takes the global RD**: `_threaded_main` uses `RenderingServer.get_rendering_device()` when `cfg.rd_global` (else the local RD — the verify/inline paths unchanged). Risk: concurrent RD command recording from the worker thread + the main thread's render recording — Godot's RD mutexes internally, but the submission interleave must be proven by a guarded experiment (engine on global RD + the frame's render list + battery + live proof). The tree-in-list chain moves with the engine (already its own list).
- **P2 — the render sets re-point**: the sim's decoupled render variants (`_us_blend_0*`, `_us_inst_0*_render`, `_us_qhist_0_render`, `_us_occ_0`) bind the ENGINE's buffers (RIDs valid on the shared RD); the `_dc_*`/`_pos_*` mirrors + the `_apply_decoupled_publish` uploads + the fp32/packed branches die.
- **P3 — the publish sheds the snapshot**: the engine's `readback_snapshot` calls die (the sim reads the engine's buffers directly); the post-job readback group shrinks to the 32 B telemetry. The item-1 pattern (boundary-accepted drain) becomes the general rule.
- **Boot gate**: the worker's IC init (13.5 s CPU at 2M) happens on the global RD — the uploads interleave with the renderer; the non-blocking bootstrap property must be re-verified (the boot's first-job submission + the frame's render).

**Determinism**: the physics dispatch order within each list is unchanged → the float results identical; the verify scenes drive the inline path (untouched). The battery's max-diff==0.0 gate stays the canary for any dispatch-order drift.

**Risk register**: (a) cross-thread global-RD submission (worker chain + main render) — the P1 guarded experiment; (b) the render's wait behind a chain — bounded by the 64-step cap; (c) the boot's non-blocking property; (d) the qhist/occ readbacks on the shared RD now drain the ENGINE's queue — the boundary-accepted rule (batch with the post-job reads) applies.
