# tree_sim_gate — fresh-eyes isolation of the sim-scene tree-gravity global-RD no-op

**Date:** 2026-08-13 · **Gate:** `scenes/tree_sim_gate.tscn` + `scripts/tree_sim_gate.gd`
**Run:** windowed Godot 4.7 (non-Mono console exe, `Godot_v4.7-stable_win64_console.exe`) on the GLOBAL RenderingDevice (`RenderingServer.get_rendering_device()`), AMD RX 7900 XTX, Vulkan 1.4.349 (Forward+). Raw logs: `_diag/tree_sim_gate_{base,a,ab,abc,abcd,abcde,abcdef,p}.log`.

## Question

The bare-Node probe (`scripts/tree_grd_probe.gd` rung G: `mode 10 ROOT_SEED → mode 9 CTR_RESET`, complete 14-binding set, one compute list, self-stall readback) lands `ctr[0]=1` on the global RD from `_process`. Inside the sim (`cassi_sim.gd`, `meshless_mode + meshless_gravity`, dispatched from `_run_physics_steps → _dispatch_tree_gravity` in the frame's compute list) the **identical** modes 9/10 do NOT execute: the counters buffer stays driver-zeroed across 60–120 settled frames, no GPU/shader error, all loud guards pass, for every construction tried (real buffers, dummy buffers, minimal PC, fresh shader/pipeline/set, fresh SPIR-V import, standalone short list).

Task: find the ingredient that blocks it. Protocol order: SUSPECT 0 (await in the dispatch path), SUSPECT 1 (RID lifetime / reachable free-recreate), then the addition ladder.

## SUSPECT 0 — awaits in the dispatch path: ELIMINATED

`grep await scripts/cassi_sim.gd` and `scripts/sim_ui.gd` → **zero matches**. There is no coroutine suspension anywhere in the sim code, so no compute list can be abandoned/interleaved by a `compute_list_begin … await … compute_list_end` boundary. Ruled out.

## Addition ladder (all rungs cumulatively, each a fresh windowed run + sentinel readback)

Starting point: the WORKING probe rung-G construction (modes 10→9, full 14-binding set, one list) in a bare Node. Ingredients added one at a time; every run's sentinel `ctr[0]==1` printed per frame + a final verdict line.

| rung | ingredient added (sim replica) | breakdown rung | sentinel |
|------|-------------------------------|----------------|----------|
| —    | baseline: probe rung-G construction, bare Node | — | **PASS** ctr[0]=1 (all 40 frames) |
| a    | MeshInstance3D + MultiMesh (renderer DR buffer, `multimesh_get_buffer_rd_rid`) written every frame by the GPU-direct instancer (`cassi_instancer.glsl`, 128-byte PC) | — | **PASS** ctr[0]=1 |
| ab   | + Camera3D + DirectionalLight3D + WorldEnvironment nodes | — | **PASS** ctr[0]=1 |
| abc  | + one extra trivial compute chain/frame (`cassi_voronoi_cells` mode 7, complete 16-binding set) | — | **PASS** ctr[0]=1 |
| abcd | + ~40 storage buffers + ~15 extra pipelines at startup (resource scale) | — | **PASS** ctr[0]=1 |
| abcde | + TWO `compute_list_begin/end` pairs per `_process` (list interleave: tree list, then instancer list, then voronoi list) | — | **PASS** ctr[0]=1 |
| abcdef | + free+recreate tree shader/pipeline/set every 30 frames while dispatching every frame (the sim's `_shaders_ready` retry pattern) | — | **PASS** ctr[0]=1 |
| p    | + per-frame global-RD `buffer_update` immediately before `compute_list_begin` (sim's bh-header pattern, `_run_physics_steps` line 771) | — | **PASS** ctr[0]=1 |

Every rung landed. None of the six protocol ingredients (a–f) nor the pre-list `buffer_update` reproduces the no-op when assembled, faithful to the sim's scene graph and frame structure, in a bare-Node reproduction.

Key log lines (representative; full verdicts in `_diag/tree_sim_gate_*.log`):

```
[TreeGate] active rungs: ["(none)"]          → base run
[TreeGate] tree-build pipeline valid=true
[TreeGate] tree set valid=true
[TreeGate] === ladder verdict ===
frame   1  ctr[0]=1  PASS
... (40 frames, all PASS)
[TreeGate] rungs active: base | sentinel LANDED (ctr[0]=1) | first-fail-frame=-1
```

```
[TreeGate] active rungs: ["a","b","c","d","e","f"]
[TreeGate] rung a: MultiMesh instance buffer RD RID valid=true
[TreeGate] rung a: instancer pipe valid=true set valid=true pc bytes=128
[TreeGate] rung d: 40 buffers, 15 extra pipelines created
[TreeGate] rung f frame 30: free+recreate tree pipe/set
[TreeGate] rungs active: abcdef | sentinel LANDED (ctr[0]=1) | first-fail-frame=-1
```

## SUSPECT 1 — RID lifetime / reachable free-recreate: gated, not the persistent trigger

- The `_shaders_ready` retry (`cassi_sim.gd` `_process` lines 723–727: `_free_shaders()` + `_setup_shaders()` every 30 frames) is **gated on `not _shaders_ready`** — it can only run before the sim declares itself ready. Once `_shaders_ready` is true the retry cannot fire.
- `reinit()` (lines 3408+) frees + recreates uniform sets AND buffers and is reachable from `sim_ui.gd` (meshless toggle, φ box, grid/particle spin, R key). It is a *transient* trigger, not a *persistent* one: the observed failure persists across 60–120 settled frames with no UI action, so a one-shot reinit does not explain it.
- My rung `f` reproduced the free+recreate pattern (every 30 frames, while dispatching every frame) and it **landed** — the pattern alone is exonerated.

## Why the ladder exhausts: the discriminator is inside cassi_sim.gd's own set/pipeline, not the scene

The controlled negative result above is decisive for what the no-op is **not**:

- not the scene node graph (Camera/Light/WorldEnvironment);
- not the renderer-owned MultiMesh buffer being written via the RD every frame;
- not the presence of extra global-RD compute chains;
- not the resource scale (dozens of buffers/pipelines);
- not multiple `compute_list_begin/end` pairs per `_process`;
- not a free+recreate of the tree shader/pipeline/set;
- not a per-frame pre-list `buffer_update`.

The probe writeup (`research/meshless/tree_grd_probe.md`) already isolated the ONLY reproducible Godot-ism that produces this exact symptom shape — **pristine-zeroed counters, no GPU execution, no shader error** — a uniform set that does not fully/validly cover the bound pipeline's declared set-0 bindings: rungs A/B/C (partial or absent tree set) fail with a silent no-op, rungs D/E/G (complete 14-binding set) land `ctr[0]=1` on the global RD. The verify script `scripts/verify_meshless_gravity.gd` independently documents the sim-side symptom (lines 8–10): the tree list "does not execute" from the sim's `_process` loop on the global RD, which is why that verify consigns the tree to a LOCAL RD.

## LAST STANDING HYPOTHESIS (ladder exhausted)

**The sim's tree-arm dispatch is recorded with a `_us_tree_build` uniform set that the global RD does not treat as a complete, valid, live binding against the bound `_tree_build_pipe` at dispatch time — triggering Godot's silent no-op (probe rungs A/B/C).** The precise in-sim trigger is inside `cassi_sim.gd`'s own set/pipeline lifecycle or one of the 14 bound buffer RIDs being (or becoming) invalid at dispatch; the bare-Node probe and this gate cannot exhibit it because they build a guaranteed-fresh, fully-covered set and the sim's private runtime state is not reachable from an external scene.

Evidence that eliminates the alternatives:
- SUSPECT 0 (await): eliminated by grep — no awaits anywhere.
- Scene-composition ingredients a–f: eliminated by the gate (all land).
- Pre-list `buffer_update`: eliminated by rung `p`.
- A one-shot reinit: does not explain a failure persistent across 120 settled frames.
- The shaders themselves: exonerated by probe rungs D/E/G and the local-RD verify (11963 nodes, correct walk).

Evidence that supports it:
- The sim-side symptom (pristine counts, no error) is byte-for-byte the incomplete/stale-set no-op signature the probe already isolated.
- `_shaders_ready` is the only thing standing between "arm dispatches" and "arm silently skipped"; its AND-chain includes `_us_tree_build.is_valid()`/`_us_tree_grav.is_valid()` (a *valid* RID can still reference a freed/partial set — `RID.is_valid()` stays true for freed RIDs, so the guard can pass while the set is stale). This is precisely the class of failure the probe's A/B/C mechanism names.

## Minimal fix recommendation (design-only — NO file edited)

**File:** `scripts/cassi_sim.gd`

**Region:** `_dispatch_tree_gravity` (guards, ~lines 2862–2913) + `_cache_uniform_sets` (tree-set creation, ~lines 1360–1370).

**Change:** make the tree arm's dispatch provably complete-and-live before recording ANY GPU pass, and make the guard path loud:

1. **Re-read the set's bookkeeping at dispatch, don't trust `is_valid()`.** Before binding, assert every bound-buffer RID in `_us_tree_build` is valid (`_ml_tree_src … _ml_tree_ctr, _ml_sites, _ml_psi_y, _ml_psi_i, _ml_vol, _mass_density_buf`) and that `_us_tree_build` was created against the SAME `_tree_build_shader` RID that built `_tree_build_pipe`. If any buffer or the shader-RID pair mismatches, `push_error` with the offending RID/binding and **skip** (don't dispatch into a guaranteed no-op). This converts the silent failure into a named one.

2. **Never inline `uniform_set_create` against a possibly-stale shader.** Have `_dispatch_tree_gravity` verify the set's shader RID or rebuild it defensively before dispatch, rather than assuming `_ready`-time creation is still live when `reinit()`/retry has churned the resource graph.

3. **Guard `_us_tree_build` / `_us_tree_grav` unconditionally.** The current `_shaders_ready` short-circuit (`_us_tree_build.is_valid() or not _ml_need_tree()`) can pass while the set is freed-but-valid-RID; replace the `is_valid()` checks with the full new completeness check so the arm cannot be "ready" with a silent-no-op set.

No shader-side change is warranted — the ladder and the verify both prove `cassi_tree_build.glsl` executes correctly on the global RD when given its complete, live set.

## Files created (committed with `git add -f`)

- `scenes/tree_sim_gate.tscn`
- `scripts/tree_sim_gate.gd`
- `research/meshless/tree_sim_gate.md`
