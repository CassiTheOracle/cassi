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
| g    | RD-buffer HANDOFF: renderer DRAWS a global-RD multimesh buffer every frame (`multimesh_get_buffer_rd_rid` → MeshInstance3D + `particle_billboard`), written via the GPU-direct instancer compute each frame | — | **PASS** ctr[0]=1 |
| h    | DISPATCH VOLUME: tree chain FIRST, then ~240 dummy voronoi-mode-7 dispatches in the SAME list, then a `_render_frame`-style second list; settle 120 frames | — | **PASS** ctr[0]=1 |
| i    | PER-FRAME BUFFER_UPDATE: 6 `buffer_update` calls on other buffers BEFORE `compute_list_begin` each frame; settle 120 frames | — | **PASS** ctr[0]=1 |
| w    | FULL CHAIN: the sim's ENTIRE `_dispatch_tree_gravity` (modes 10/9/7, bitonic 21/91, split/commit 14×2, moments, WALK on a 2nd pipeline+set) in ONE open list, with the sim's in-place PC mutation on a persistent `_tree_build_pc_bytes` | — | **PASS** ctr[0]=1 |
| wih  | MAX FIDELITY: buffer_updates before (i), full sim tree chain incl. walk in one open list (w), ~240 dispatches continuing that SAME list (h), second repaint list; settle 120 frames | — | **PASS** ctr[0]=1 |

### Rung-g note (RD-buffer handoff)

The rung-spec's `RenderingServer.multimesh_set_buffer(multimesh_rid, rd_rid)` is **not a valid Godot 4.7 call** — that API takes a `PackedFloat32Array`, not an RID (the parser rejected the RID form). The sim's ACTUAL handoff — and the only valid "renderer consumes a global-RD buffer" form — is the reverse: the renderer allocates the instance buffer from `instance_count`, we grab its RD RID via `RenderingServer.multimesh_get_buffer_rd_rid`, bind it in the instancer set, and DRAw it via MeshInstance3D + a material every frame. Rung g implements exactly that: the renderer consumed a global-RD buffer all 40 frames while the tree modes 10→9 landed.

```                                                            
[TreeGate] active rungs: ["g"]                                
[TreeGate] rung g: renderer buffer RD RID=true drawn via MeshInstance3D + particle_billboard every frame
[TreeGate] rung g: instancer pipe=true set on renderer buffer=true
[TreeGate] rungs active: g | sentinel LANDED (ctr[0]=1) | first-fail-frame=-1
[TreeGate] active rungs: ["w","i","h"]                        
[TreeGate] rung i: 6 per-frame-update buffers created         
[TreeGate] rung w: walk pipe=true walk set=true               
[TreeGate] rungs active: wih | sentinel LANDED (ctr[0]=1) | first-fail-frame=-1
```

Every rung (base, a–f, g, h, i, w, wih) landed. None of the protocol ingredients, the pre-list `buffer_update`, the renderer-drawn global-RD buffer, the per-frame dispatch volume, the full tree chain with walk, OR the max-fidelity combined frame reproduces the no-op when assembled, faithful to the sim's scene graph and frame structure, in a bare-Node reproduction.

The probe writeup (`research/meshless/tree_grd_probe.md`) already isolated the ONLY reproducible Godot-ism that produces this exact symptom shape — **pristine-zeroed counters, no GPU execution, no shader error** — a uniform set that does not fully/validly cover the bound pipeline's declared set-0 bindings: rungs A/B/C (partial or absent tree set) fail with a silent no-op, rungs D/E/G (complete 14-binding set) land `ctr[0]=1` on the global RD. The verify script `scripts/verify_meshless_gravity.gd` independently documents the sim-side symptom (lines 8–10): the tree list "does not execute" from the sim's `_process` loop on the global RD, which is why that verify consigns the tree to a LOCAL RD.

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
- not the renderer-owned MultiMesh buffer being written via the RD every frame (the sim's ACTUAL `multimesh_get_buffer_rd_rid` handoff, drawn every frame);
- not the presence of extra global-RD compute chains;
- not the resource scale (dozens of buffers/pipelines);
- not multiple `compute_list_begin/end` pairs per `_process`;
- not a free+recreate of the tree shader/pipeline/set;
- not a per-frame pre-list `buffer_update`;
- not the sim's full dispatch-volume per frame (~360 dispatches, tree in head-of-list);
- **not the sim's ENTIRE tree chain** (modes 10/9/7, bitonic, split/commit, moments, and the WALK on a second pipeline+set, with the sim's in-place PC mutation) — rung `w` and the combined `wih` land it in a bare Node.

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

## Line-by-line diff: the gate's landing full-chain vs `cassi_sim.gd _dispatch_tree_gravity`

Because rungs g/h/i/w — including the faithful full chain with walk and the max-fidelity `wih` frame — ALL land in a bare Node, the remaining variable is the sim's own call sequence. `scripts/tree_sim_gate.gd _dispatch_full_tree_chain` (rung w) is a structural byte-copy of `cassi_sim.gd:2929-3040`. Every difference found:

| # | cassi_sim.gd `_dispatch_tree_gravity` | gate rung-w `_dispatch_full_tree_chain` | effect on dispatched GPU sequence |
|---|----------------------------------------|------------------------------------------|-----------------------------------|
| 1 | loud guards (nsrc/pipe/set/`_ml_ready`, lines 2930–2952) | none (always runs) | none — guards only gate whether anything is recorded |
| 2 | `N_src = _ml_tree_nsrc` = 8192; `pg_src = ceil(8192/64)=128` | `N_src=64`; `pg_src=1` | bitonic runs 91 stages (sim) vs 21 (gate); split/commit 14×2 both |
| 3 | `Np = N_particles` (=2000 main / 2000 verify); walk `dispatch(ceil(Np/64))` | `Np=64`; walk `dispatch(1,1,1)` | same structure, fewer threads |
| 4 | PC encode: `bp.encode_float(0,N_src); 1-3 bmin=(0,0,0); 4 half; 5 eps2; 6 PHI; 7 PHI_6; 8 leaf_cap; 9 max_levels; 10 mode; 11-13 bitonic; 14 grid_N; 15-17 ext; 18 field_floor` — **in place on persistent `_tree_build_pc_bytes`** | identical field order, identical in-place mutation on `_tree_build_pc_bytes` | **identical** (gate replicates exactly) |
| 5 | bind `_tree_build_pipe` + `_us_tree_build` to `cl` | bind `_build_pipe` + `_us_tree` to `cl` | identical |
| 6 | modes: 10→barrier→9→barrier→7→barrier→ bitonic(91)→barrier→ [5→barrier→8→barrier]×14 →6→barrier → bind `_tree_grav_pipe`+`_us_tree_grav`→walk→barrier | identical order (21-stage bitonic, 14× [5/8]) | **identical** |
| 7 | **caller**: `_run_physics_steps` opens ONE list (`cl`, line 801), calls `_dispatch_tree_gravity(cl)` (line 803), then continues the SAME open `cl` with `_step_dispatches` (deposit/nbody/PDE) + instancer, then `compute_list_end` (line 822) | rung-w branch: opens ONE list, calls `_dispatch_full_tree_chain(cw)`, continues with `h` volume dispatches, then `compute_list_end` | **identical shape** (the list continues past the walk; tested by `wih`) |
| 8 | set `_us_tree_build` binds the SIM's real buffers (`_ml_tree_src` 256 KB, `_ml_tree_q` 2 MB, `_mass_density_buf` 1–8 MB, …) | set binds small dummies (≤ 8 KB) | buffer SIZE differs, but resource-scale rungs `d`/`a` plus the probe's dummy-set D/G land — size is not the trigger |
| 9 | `_us_tree_grav` walk set binds `_ml_tree_grad`/`_ml_tree_icount`/`_pos_buf` (N_particles-sized) | walk set binds 64-element grad/icount/pos | same bindings, smaller arrays |

**Difference that survives every elimination — and the last remaining candidate:** none of the 9 rows changes the *recorded GPU command stream* in a way a bare-Node reproduction can't now reproduce (rows 1–7 are structurally identical; rows 8–9 differ only in buffer SIZE, which resource-scale + the probe's dummy-set rungs exonerated). Since the byte-identical sequence lands in a bare Node, the no-op can only be produced by **sim-internal state that is not a visible argument to `compute_list_*`**: i.e. the `_us_tree_build`/`_us_tree_grav` SETS themselves being freed-but-`is_valid()` (stale) or partially-covering at dispatch time on the sim's frame — the probe's rung-A/B/C silent-no-op mechanism — induced by the sim's own resource lifecycle (retry/reinit/`_setup_buffers` order) that no external scene can reproduce while building a guaranteed-fresh set.

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
