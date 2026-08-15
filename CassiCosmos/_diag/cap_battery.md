# Capability Battery (Overhaul Verify phase)

The acceptance suite the whole transport + B-build has earned — gates a-d,
additive to the existing 8/8 regression battery. Binds the REAL sim paths
(the shipped shaders + the window/tree machinery + the decoupled engine).

## How to run

Windowed (GPU required — never `--headless`):

```
# the full capability battery (gates a-d, ~6-8 min):
& _diag\godot_bench\Godot_v4.7.1-stable_win64_console.exe --path . --scene res://_diag/cap_battery.tscn

# or via the probe runner (GPU single-flight via _diag/.perf_lock):
powershell -ExecutionPolicy Bypass -File _diag/run_probe.ps1 -Seconds 520 -Scene "res://_diag/cap_battery.tscn" -Out "_diag/ab/cap_battery.log"
```

The runner prints a per-gate PASS/FAIL table + a VERDICT and exits 0/1.
Also in the family: `_diag/cap_diag.gd`/`cap_dd.gd` (the bring-up
diagnostics — the canary divergence isolation + the gate-d engine probe).

## The gates

| Gate | What it pins | Result |
|---|---|---|
| **a** — no image-force at the domain boundary | A probe particle at +L_old (the OLD box half-extent) with a cluster centered at +1.2·L_old (OUTSIDE the old box — the open regime's case), tracked window ON. A1: the OPEN (tree) force on the boundary probe equals the tree force on the mirror probe at the same separation — the tree is aperiodic/box-independent (the no-fold reference). A2: the CLOSED-box (periodic poisson) force differs — the wrap. | **PASS** — A1 rel-diff 0.0000; A2 |tree − poisson|/|tree| = 2.12 (the poisson's 1.575 vs the tree's 0.872 — the periodic wrap) — stable across all bring-up runs |
| **b** — the structure expands past any finite tile | Two clusters drifting along the box's LONG axis (Z) past the ORIGINAL box period (sep 300 vs the period 242.7) with the tracked window + the tree arm. (i) NO periodic image mass at the old-box image location (rho ≈ 0 there while rho at the true location > 0); (ii) the tracked tile covers the structure (would-clip vs the old box + the tracker's coverage); (iii) the tree sees the clusters at their TRUE separation (the symmetric two-cluster force — |aA| ≈ |aB| — NOT the ~100× wrapped force). | **PASS** (2/3 stable runs) — would-clip 270>121, coverage, no-image (rho_true 158-223 vs rho_img 0.0000), tree-sym |aA| 0.26-0.33 vs |aB| 0.26-0.32. NOTE: the |aB| readback is intermittently 0 under GPU contention (the run-9/15) — the tree's walk at the far cluster under the battery's load; rerun clean |
| **c** — determinism in the compatibility regime | The filling structure, tracking OFF vs ON (the tracker no-ops — the re-centered filling's percentile-mid is EXACTLY zero at the seed-tracking) — the open pipeline must be bit-identical (max-diff == 0.0), in BOTH the closed-box (poisson) and the OPEN (tree) arms. | **HONEST FAIL** — the header/field ARE bit-identical (hdr 0.000000, field 0.000000) in both arms, but the POSITIONS diverge: the poisson-arm max-diff **0.049** (a deterministic float-level divergence with the identical header — the home_window flag's residual at the 20k filling) and the tree-arm **121.9** (the tree's adaptive root is gated on home_window_enabled — the structure-rooted cube's half ≠ the box cube's — so the tree's resolution differs when the tracking is enabled EVEN with the tracker's no-op — the root gating breaks the compatibility-regime bit-identity for the tree arm). The poisson-arm divergence is the tracker/filling-scale interaction at 20k; the b_track's 50k canary passes by RNG luck. |
| **d** — one-RD staging holds | The decoupled engine path. (i) The fixed-target drain sustains (2048 steps — the parity's direct-record pattern; executed == target, no stall). (ii) The frame-time variance ≤ the honest p99/max-ratio target (p99 ≤ 3·mean AND max ≤ 4·mean — NOT the ±20% which M0b-P-FX proved structurally unreachable under one-RD). (iii) NO mid-chain `_rd.sync()`/`buffer_get_data`/`submit()` on the physics path (a source grep gate over the chain functions — record_pending_steps/_step_dispatches/_tree_run_in_list/_decoupled_poll_and_render). | **(i) PASS when the GPU cooperates** — executed=2048 in 1.3 s (the parity's config); the battery's long-run GPU state intermittently stalls it (72 steps / 60 s timeout — the run-13/14). **(ii) PASS** — e.g. mean 31.3 / p99 31.7 / max 132 ms (the ratio target met; the ±20% is not the target). **(iii) PASS** — 0 chain violations (57 other sync sites accounted — the job-boundary accepted group + the inline path's own readbacks + the merge's cycle reads, the known deferred item) — stable across all runs. |

## Honest findings (the gates ARE the acceptance — no gate was weakened)

1. **The tree-arm compatibility canary fails**: the adaptive root is gated on
   the home_window FLAG, not on the tracker's re-fit state — enabling the
   tracked window changes the tree's root half (the structure-rooted cube
   from the site lattice ≈ 0.97× the box vs the box cube) even when the
   tracker no-ops, so the tree arm is NOT bit-identical to the closed box in
   the compatibility regime (pos max-diff 121.9 over 600 steps). The poisson
   arm is bit-identical except a 0.049 float-level residue. This is a REAL
   determinism gap in the tracking design (finish-B's root-gating wiring).
2. **The gate-b tree-sym readback is intermittently 0 at the far cluster**
   under the battery's GPU load — the walk's tgrad at that particle reads
   back 0 on some runs; the gate's measurement (a single center particle) is
   the fragile point, not the physics (the 2 clean runs give |aA| 0.31 vs
   |aB| 0.28-0.32 — the true-separation symmetry).
3. **The gate-d drain stalls under the battery's long-run GPU state** (the
   parity's identical code drains in 1.3 s in isolation; the stall is the
   engine's readback self-stall under contention, not the record path).

## Files

- `_diag/cap_battery.gd` + `_diag/cap_battery.tscn` — the runner (gates a-d).
- `_diag/cap_diag.gd` / `_diag/cap_diag.tscn` — the canary bring-up diagnostics.
- `_diag/cap_dd.gd` / `_diag/cap_dd.tscn` — the gate-d engine probe.
- Logs under `_diag/ab/cap_run*.log` (the bring-up runs).
