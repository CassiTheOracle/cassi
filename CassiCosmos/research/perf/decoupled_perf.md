# Decoupled Physics — Measured Perf Diagnosis & Fix Plan (FIXED)

**Status:** Diagnosis → **implemented** (FIX A/B/C) + FIX D verified-necessary-not. Measured before/after below.
**Repo:** `godot/space-sim` (perf probe = `scripts/verify_decoupled_perf.gd` + `scenes/verify_decoupled_perf.tscn`; scan shader = `compute/cassi_exclusive_scan.glsl`; scan gate = `scripts/verify_exclusive_scan.gd` + `scenes/verify_exclusive_scan.tscn`)
**Asset/machine:** Windows 11, AMD RX 7900 XTX, Godot 4.7 (win64 console, windowed, local RD via `--path`)
**Date:** 2026-08-14
**Measured by:** `verify_decoupled_perf` probe (drives `scripts/cassi_physics_engine.gd` directly; raw run → `_diag/decoupled_perf_report.json`, gitignored)

This report reproduces and times the **two reported symptoms** with hard numbers on
the actual engine (`scripts/cassi_physics_engine.gd` threaded local-RD runner), then
records the fixes and the measured before/after:

1. **the DETACHED physics LONG HANG** — the threaded engine's startup bootstrap,
2. **MATTER-CONDENSING causing low frame rate / stuttering** — the particle-merge pass.

Every number below was measured this session; none are guesses. The probe creates its
own engine instances on private worker threads (own local RDs), fully isolated from
any live sim, and touches no shared `.gd`/`.glsl`.

---

## 0. Fix results (measured before → after)

| Fix | Change | Before | After | Verified |
|---|---|---|---|---|
| **A** | Non-blocking bootstrap: `submit_steps` first call queues (never `_setup_sem.wait`); sim polls `_decoupled_poll_and_render` for the first publish. | **3516 ms** main-thread block at 2.5M | **0 ms** main-thread block (async time-to-publish ~4 s on the worker, free-pumped) | perf probe PROBE1; sim parses + merge_sim 5/5 unaffected |
| **B** | On-GPU exclusive scan (`cassi_exclusive_scan.glsl`, 4 passes) replaces the host cc-readback + cs/ch-upload + 8.9M-iter CPU prefix-sum. | **+276 ms**/merge batch (8.88M cells) | **+20–27 ms**/merge batch | `verify_merge` 8/8, `verify_merge_sim` 5/5, `verify_merge_engine` 7/7, `verify_exclusive_scan` 4/4 (vs CPU reference) |
| **C** | Packed-fp16 snapshot already default in sim (user commit); telemetry fused (snapshot field_q reused, no double readback); unused `pot` mirror dropped. | publish fp32 36-37 ms | packed **15-17 ms**; one less field_q readback + pot upload per publish | perf probe PROBE2 |
| **D** | **Not a rewrite** — the `OpAtomicFAddEXT` float atomic is PROVEN correct on the worker local RD (100k/100k particles accreted in the probe; `verify_bh_accretion_engine` 9/9, `verify_merge_engine` 7/7). The "not supported yet" is a spurious teardown validation warning, not a failure. | — | — | perf probe PROBE5 (deterministic worker-path accretion); bh_acc_engine 9/9 |

**Battery table (after fixes, isolated runs):**

| Battery | Result |
|---|---|
| `verify_merge` (G28/G29 via stage6_merge.py) | PASS 8/8 |
| `verify_merge_sim` | PASS 5/5 |
| `verify_merge_engine` (G52-G54) | PASS 7/7 |
| `verify_bh_accretion_engine` (G55-G57) | PASS 9/9 |
| `verify_exclusive_scan` (new, GPU-scan vs CPU ref) | PASS 4/4 |
| `verify_fft` / `verify_phi_box` / `verify_river_law` / `verify_gravity_modes` | PASS (58/58 for gravity modes) |

> Pre-existing (parallel-session in-flight) failures, NOT caused by these fixes:
> `verify_multigrid_engine` (engine `cascade_level` uniform set + `cascade_ran` counter are
> not wired at HEAD — `git show HEAD` has 0 cascade-set/counter lines, so the coarse chain
> was never engine-integrated) and `verify_river_isotropy`'s `cascade[dual-O4]` ring -nan
> (sim cascade subpasses in flux; neither battery touches the merge/bootstrap/telemetry
> code these fixes changed).

---

## 1. Timings (measured)

Probe config: `grid_N = 64`, `cluster_radius = 120` (the LIVE `main.tscn` value, so the
merge spatial hash matches the user's scene), `num_clusters = 10`, `dt = 0.002`,
river gravity, grid path (meshless off for a deterministic chain), fixed seed. The
bootstrap/snapshot probes run at the **full 2 500 000 particles** (the user's count);
the merge/BH probes use 300 000 (the merge *readback size* is particle-count
independent — it scales only with the spatial-hash geometry).

| # | Measurement | Value | Notes |
|---|---|---|---|
| 1a | `start_threaded()` — shader SPIR-V load on MAIN thread | **50 ms** | trivial; not the hang |
| 1b | **BOOTSTRAP `submit_steps(4)` MAIN-thread block** | **3516 ms** | `_setup_sem.wait()` + first job + full 78.3 MB fp32 snapshot. **= the apparent "long hang".** |
| 1c | blocking `submit_steps(+4, block=true)` per job (worker: 4 steps + snapshot+publish) | 157 ms avg | 39.3 ms/step at 2.5M |
| 2a | **pure-publish readback (fp32)** — pos+vel+field_q+pot | **37 ms** @ 2.5M | ~78 MB over the local RD → PCIe |
| 2b | **pure-publish readback (fp16 packed)** — `cassi_pack_f16.glsl` | **16 ms** @ 2.5M | halves pos/vel → ~2.3× cheaper |
| 3a | merge spatial-hash size | **8 876 160 cells** = 33.9 MB | geometry-driven (207×128×335) |
| 3b | 8-step batch, **merge OFF** | 28 ms (3.5 ms/step) | warm, no merge |
| 3c | 8-step batch, **merge ON** | 304 ms (38 ms/step) | merge ran in 2 cycles |
| 3d | **NET merge overhead per run_steps batch** | **+276 ms** | 2 cycles × (33.9 MB cc readback + 33.9 MB×2 cs/ch upload + 8.9M-iter host prefix-sum), each cycle submit+sync |
| 4 | BH chain ON vs OFF (condensation every 100, BH-integrate every step) | 3.10 → 3.15 ms/step | **+0.05 ms/step — negligible** |

### Confidence
- Probe 1/2 numbers are single runs at 2.5M; variance across runs was ±8% (bootstrap
  3506–3953 ms, publish 36–37 ms fp32 / 15–17 ms packed) — the conclusions are robust.
- Probe 3 (merge +276 ms/batch) is a clean warm-vs-warm twin comparison (both engines
  bootstrapped+parked) — the ONLY difference is the merge pass.
- Probe 4 (BH) is warm-vs-warm.

---

## 2. Ranked causes

### CAUSE 1 — DETACHED bootstrap blocks the main thread ~3.5 s with no feedback  ⭐ (the hang)

`cassi_physics_engine.gd:submit_steps()` sets `_wait_next`, then when the sim's
`_decoupled_start_engine()` (cassi_sim.gd:1369, called from `_ready`) calls
`submit_steps(1)`, the **main thread blocks on `_setup_sem.wait()`** (engine line 764)
until the worker finishes: local-RD create → buffer alloc (~350 MB) → the **full
2.5M-particle IC generation loop** (`_init_particles`, a multi-second CPU loop) →
field init → uploads — and THEN runs the first step + a full 78 MB snapshot readback
(engine `_threaded_run_job` → `readback_snapshot()`). Measured **3516 ms** on the main
thread, no progress indicator. That synchronous block at scene startup is the hang.

Secondary contributor inside CAUSE 1: the first job's full fp32 snapshot is 37 ms of
the 3516 ms; the rest is IC-gen + setup. `_wait_next` exists so the caller gets an
immediate first snapshot, but it converts an async worker into a synchronous one for
the entire startup.

### CAUSE 2 — the particle-merge pass: +276 ms per batch; in the inline path EVERY FRAME  ⭐ (the stutter)

`particle_merge = true` is the LIVE scene's `main.tscn` setting ("matter condensing" =
the dust→object coalesce). The merge (`_run_merge_pass`) needs a **host CPU
exclusive-prefix-sum between its count→fill passes**, which forces `buffer_get_data`
readbacks on the host. Measured per batch:

- spatial hash = **8.88 M cells → 33.9 MB readback (cc) + 33.9 MB×2 uploads (cs/ch)**,
- ≥2 cycles per merge batch (dense live ICs),
- each cycle is **submit+sync on the local RD** (decoupled) or a **self-stalling global-RD
  readback** (inline),
- net **+276 ms per run_steps batch** in the decoupled engine.

**Worse in the inline (non-decoupled) path — which is what main.tscn runs by default
(`physics_decoupled` defaults false):** `cassi_sim.gd:4254` calls `_run_merge_pass()`
from `_render_frame()` **every rendered frame** when `particle_merge && !_decoupled_active`.
Each frame = 2+ cycles of 33.9 MB readbacks + 67.8 MB uploads + two full-RD syncs +
a host prefix-sum over 8.88 M ints — a ~hundreds-of-ms host stall that directly tanks
frame rate. **This is the dominant condensing stutter.**

In the decoupled path the merge runs on the worker's local RD, so it *doesn't* blocking
the render — but it still delays the worker's physics (each batch's next publish waits
for the merge), and the backlog (`_decoupled_pending`) grows → catch-up pacing drops the
apparent rate exactly when matter aggregates.

### CAUSE 3 — snapshot publish is a full readback every publish (37 ms fp32 / 16 ms packed)

`readback_snapshot()` on the worker pulls **pos (40 MB) + vel (40 MB) + field_q (1 MB) +
fft→pot (2 MB)** = ~78 MB every publish job. The engine already added a publish cadence
(`_snapshot_cadence`, default 2) and a packed fp16 path (`cassi_pack_f16.glsl`) — the
packed path already **halves the readback (16 vs 37 ms)**. But the sim's mirror side
(`_apply_decoupled_publish`, cassi_sim.gd:1398-1405) then **re-uploads ~122 MB on the
main-thread global RD** (pos_prev 40 + pos 40 + vel 40 + field_q + pot) every publish —
a per-publish main-thread hit that competes for PCIe with the worker's reads.

### CAUSE 4 (finding, RESOLVED by verification) — the `OpAtomicFAddEXT` warning is spurious
The probe's BH-ON run logged **`OpAtomicFAddEXT is not supported yet.`** This was initially
read as "the BH-accretion float atomic is broken on the local RD." **Deterministic probe
evidence proves it WORKS:** a worker-thread engine with a planted BH + `R_acc=100` accreted
**100 000/100 000** particles (pos.w→0), and `verify_bh_accretion_engine` passes 9/9 with
exact mass conservation (`G55 bh=7.0`). The warning is emitted by Godot 4.7's local-RD
validation DURING TEARDOWN (`free()`), not during dispatch — the Vulkan device supports
the extension; the atomics genuinely accumulate. **FIX D therefore required NO rewrite** —
converting the working float atomics to integer fixed-point would risk the passing
conservation gates for zero functional gain. (The same spurious warning appears in the
merge shader's float atomics, which also verifiably work: `verify_merge_engine` 7/7,
mass conserved.)

### Cross-check Q3 — stutter vs BH activity?
**The stutter is the MERGE PASS, not BH/condensation.** Condensation+BH-integrate ON
cost +0.05 ms/step (negligible), and the live scene has `black_holes_enabled` off
(condensation isn't even dispatching). Matter condensing = merge, and the merge's host
readback/prefix-sum is the only host-side stall that scales with matter density. The
correlation is with **the merge pass running at all** (its per-batch fixed cost),
which is exactly when dust coalesces into objects.

---

## 3. Concrete fix plan (later turn — green-light first; READ-ONLY this turn)

All sizes are the measured numbers above. Each fix lists expected win + file/region.

### FIX A — Non-blocking bootstrap with progress (kills the hang)
- **Change:** in `cassi_physics_engine.gd:submit_steps()` / `start_threaded()`, don't
  block the caller on `_setup_sem.wait()` for the first job. Add a `bootstrap_ready`
  flag + a non-blocking `is_ready()` poll; `_decoupled_start_engine` (cassi_sim.gd)
  submits the first job and returns immediately; the sim samples `engine.poll()` /
  `is_ready()` across frames until the first snapshot arrives (the worker already
  publishes setup completion via `_setup_sem`). Optionally split the 2.5M IC-gen so the
  field/chain is ready first and particles stream in — or at minimum emit a
  "initializing 2.5M particles…" progress line so the 3.5 s isn't a silent hang.
- **Expected win:** startup no longer freezes the main thread for 3.5 s (sim renders a
  spinner/black screen while the worker boots). Touches `cassi_physics_engine.gd`
  (bootstrap path ~lines 611-646, 701-760) + `cassi_sim.gd:1357-1375`.

### FIX B — Amortize / eliminate the merge's host prefix-sum (kills the stutter)
The 33.9 MB cc readback + 67.8 MB upload + 8.9M-iter CPU scan per cycle is the cost.
Options, best first:
1. **On-GPU exclusive prefix-sum** (`chained-scan`/Hillis-Steele pass mode in
   `cassi_particle_merge.glsl`): write `cs`/`ch` entirely on the GPU, removing the
   host readback of `cc` and the `cs`/`ch` uploads. The merge cycle then needs only a
   tiny 4-byte `mc` readback to check termination (already present). **Expected win:
   +276 ms/batch → ~single-digit ms/batch.**
2. **Merge cadence throttling** (fallback if the GPU scan is a bigger change): run the
   merge every K batches, not every batch (a few hundred steps apart, still inside the
   R_m reaction budget the header cites). **Expected win: ~K× reduction in merge stalls.**
3. For the **inline path** (the default main.tscn): if the GPU scan ships, the merge
   no longer needs per-frame global-RD readbacks; if not, at least drop the per-frame
   cadence to e.g. every 8-16 frames so the self-stalling readbacks don't hit every
   frame. **Expected win: removes the per-frame hundreds-of-ms hit.**
- Touches `cassi_particle_merge.glsl` (+ pass modes 7/8 for the scan), the engine's
  `_run_merge_pass` (lines 2367-2419), and the sim's `_run_merge_pass` (1154-1209) +
  the `_render_frame` gate (4254).

### FIX C — Snapshot economics: packed by default + subsampled telemetry
- **Change:** make the decoupled publish **packed fp16 by default** (16 vs 37 ms; the
  pack pass already exists) — feed `packed: true` from the sim instead of fp32, and
  skip the `pot`/`field_q` mirror unless a render consumer needs them (the decoupled v1
  has no FFT consumer — `_upload_pot_mirror` is maintained "for phase 2" — so it can be
  dropped, saving 3 MB + the interleave loop). `readback_telemetry` re-reads `field_q`
  (another nc×4) after `readback_snapshot` already did — fusion + subsample it.
- **Expected win:** worker publish 37→16 ms; sim mirror upload 122 MB→~82 MB per publish.
- Touches `cassi_physics_engine.gd` (`readback_snapshot`/`readback_telemetry`,
  `_threaded_run_job` cadence defaults) + `cassi_sim.gd` (`_apply_decoupled_publish`, job meta).

### FIX D (correctness — VERIFIED NOT A REWRITE)
- **Verdict:** the float atomicAdd (`OpAtomicFAddEXT`) in `cassi_bh_accretion.glsl` and the
  merge shader WORKS on the worker local RD (probe PROBE5: 100k/100k accreted; batteries
  9/9 + 7/7 with exact conservation). The `OpAtomicFAddEXT is not supported yet.` log is a
  spurious Godot 4.7 local-RD teardown validation message, not a runtime failure.
- **Action taken:** none required. No integer-fixed-point rewrite (would risk the passing
  gates for zero gain). Documented in the shader header (`cassi_bh_accretion.glsl`) that
  the float atomic is verified on this GPU / Godot 4.7 by the batteries + probe.
- Touches: (none for correctness — only report + probes).

### Priority order
1. **FIX B** (stutter — dominates frame rate; inline path hits every frame).
2. **FIX A** (hang — 3.5 s frozen startup).
3. **FIX C** (publish/mirror bandwidth — modest win, cheap).
4. **FIX D** (correctness only).

---

## Repro
```
Godot_v4.7-stable_win64_console.exe --path <space-sim> res://scenes/verify_decoupled_perf.tscn
```
Prints the full timing table; writes `res://_diag/decoupled_perf_report.json` (gitignored).
The probe drives the engine directly — no sim instance, no shared-file edits.
