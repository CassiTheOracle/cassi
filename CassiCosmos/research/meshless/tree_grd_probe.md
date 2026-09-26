# tree_grd_probe — global-RD tree-gravity isolation ladder

**Date:** 2026-08-13 · **Probe:** `scenes/tree_grd_probe.tscn` + `scripts/tree_grd_probe.gd`
**Run:** windowed Godot 4.7 on the GLOBAL RenderingDevice (`RenderingServer.get_rendering_device()`, NOT `create_local_device`), AMD RX 7900 XTX, Vulkan 1.4.349 (Forward+).
**Raw log:** `_diag/tree_grd_probe.log`.

## Question

The sim's tree-gravity compute chain (`compute/cassi_tree_build.glsl` modes
10/9/7/1/5/8/6 + `compute/cassi_tree_gravity.glsl`) is dispatched INSIDE the
frame's compute list from `cassi_sim.gd _run_physics_steps →
_dispatch_tree_gravity`, yet after 60+ settled frames the build counters come
back driver-zeroed — even the one-group modes 9/10 never land — while:
- the **identical** shaders run correctly on a LOCAL RD (verify scenes),
- the sim's **other** global-RD shaders (voronoi, JFA, poisson) DO execute
  from the same call site.

This probe pins down which ingredient stops the tree shader on the GLOBAL RD.

## Probe construction

A plain `Node` script acquires the global RD once, loads ONLY
`cassi_tree_build.glsl` (plus `cassi_voronoi_cells.glsl` as the F control),
and walks an isolation ladder. Every rung records a fresh compute list, ends
it, awaits `RenderingServer.frame_post_draw`, then reads back through the
self-stalling `buffer_get_data` path — exactly the readback that previously
proved a CPU-seeded value lands (trustworthy; the ladder's sentinels use that
same path). Each rung uses its OWN freshly-zeroed sentinel buffer so rungs
cannot contaminate each other.

## Ladder results

| rung | what was dispatched | set bound | sentinel | verdict |
|------|---------------------|-----------|----------|---------|
| A    | build mode 9 in `_ready`, ONE list | minimal (binding 8 only) | ctr[0]=1? | **FAIL** ctr[0]=0 |
| B    | build mode 9 in `_ready`, ONE list | NONE | ctr[0]=1? | **FAIL** ctr[0]=0 |
| C    | build mode 9 from `_process` (frame 5) | minimal (binding 8 only) | ctr[0]=1? | **FAIL** ctr[0]=0 |
| D    | build mode 9 in `_ready`, ONE list | **FULL (bindings 0–13)** | ctr[0]=1? | **PASS** ctr[0]=1 |
| E    | build mode 9 + cells mode 7 in ONE list | FULL | ctr[0]=1? | **PASS** ctr[0]=1 |
| F    | **control** voronoi mode 7 (reset) in one list | FULL voronoi | vol[0]→0? | **PASS** vol[0]=0 |
| G    | **supp.** sim opening: mode 10 → mode 9, one list | FULL | ctr[0]=1? | **PASS** ctr[0]=1 |

Every rung printed its sentinel verdict to the log (pasted in the run record
below). The first failing rung is **A**.

## Isolated ingredient

The FIRST failing rung (A) exposes the Godot-ism directly. When the tree
build shader is dispatched with anything less than its **complete uniform
set**, Godot refuses it and the dispatch never executes:

- `uniform_set_create` with a partial set (even just `binding 8 = counters`,
  which mode 9 actually needs) **errors**:
  > `All the shader bindings for the given set must be covered by the uniforms
  > provided. Binding (0), set (0) was not provided.` (rendering_device.cpp:4405)
- A dispatch bound to an invalid / absent set then **errors and silently
  no-ops**, leaving the counters pristine:
  > `Uniforms were never supplied for set (0) at the time of drawing, which
  > are required by the pipeline.` (rendering_device.cpp:6845) — and the
  buffer reads back 0.

Rungs A / B / C all fail for this ONE reason (a partial set can't even be
created, so its dispatch no-ops; B has no set at all). **The tree build
shader declares ALL of set-0 bindings 0–13, so Godot mandates a complete
14-binding set for any dispatch of that pipeline.**

The ladder also PROVES the converse and it is decisive:

- **Rung D PASS** — with the complete 14-binding set, mode 9 of the SAME
  `cassi_tree_build.glsl` on the SAME GLOBAL RD, in a single frame list,
  lands `ctr[0]=1`.
- **Rung G PASS** — the sim's EXACT opening (`mode 10 ROOT_SEED` then
  `mode 9 CTR_RESET`, full set, one list, barrier between) also lands
  `ctr[0]=1`.
- **Rung F PASS** — the probe structure itself is sound (a known-working
  shader lands through it).

So the tree build shader and its basic global-RD dispatch mechanics are **not
broken**. The simulator's in-sim no-op is therefore NOT a shader / PC-size /
set-size / group-count problem (those are all disproven by D/E/G) — the
isolated Godot-ism is the mandatory full-set coverage, and the sim's symptom
shape (pristine zeroed counters, no GPU execution, no shader error) matches a
**silent short-circuit or a stale/incomplete set** on the sim side rather than
a GPU execution failure.

## Minimal fix recommendation for cassi_sim.gd (design-only — NOT edited)

`_dispatch_tree_gravity` guards on
`_ml_tree_nsrc > 0 and _tree_build_pipe.is_valid() and _tree_grav_pipe.is_valid()
and _ml_ready` and returns WITHOUT recording any GPU pass when any is false.
With the GPU path proving fine (D/E/G), the likeliest in-sim ingredient is
that this gate is silently false at dispatch time (`_ml_ready == false`, or a
pipe/`_ml_tree_nsrc` check), so the whole chain — including modes 9/10 — is
never recorded and the counters stay driver-zeroed with no error. Recommend:

1. **Make the gate loud.** If the tree arm is enabled but `_dispatch_tree_gravity`
   returns early, print WHICH guard failed. A silent `return` is the one
   configuration that reproduces "pristine zeroed counters, no dispatch, no
   GPU error" while the GPU path itself works (rung D/G).
2. **Guard `_us_tree_build` creation.** Confirm `uniform_set_create` for the
   tree build shader returned a valid RID and covers bindings 0–13
   (0,1,2,3,4,5,6,7,8,9,10,11,12,13 — it already does). If it is ever allowed
   to be created partially or on a stale pipeline, the dispatch will silent-
   no-op exactly like rungs A/B/C. Log an error if `_us_tree_build.is_valid()`
   is false before dispatching.
3. **Cross-check `_ml_ready` ordering.** The tree chain is dispatched only when
   `meshless_mode and meshless_gravity and _ml_ready`. Verify `_ml_ready` is
   actually set true before the first physics `_process` that enables the arm
   (the meshless arm flips `_ml_ready` after a CPU seed; a race where the tree
   arm is queried before the meshless arm reports ready yields the no-op).
4. No shader-side change is warranted — the ladder proves `cassi_tree_build.glsl`
   executes correctly on the global RD when given its complete set.

## Run record (`_diag/tree_grd_probe.log`)

```
Godot Engine v4.7.stable.official.5b4e0cb0f
Vulkan 1.4.349 - Forward+ - Using Device #0: AMD - AMD Radeon RX 7900 XTX

[TreeGrdProbe] global RD acquired: true
[TreeGrdProbe] tree-build pipeline valid=true
[TreeGrdProbe] voronoi-cell pipeline valid=true
ERROR: All the shader bindings for the given set must be covered by the uniforms provided. Binding (0), set (0) was not provided.
   at: uniform_set_create (servers/rendering/rendering_device.cpp:4405)
[TreeGrdProbe] sets: min=false full=true vor=true
ERROR: Uniforms were never supplied for set (0) at the time of drawing, which are required by the pipeline.
   at: compute_list_dispatch (servers/rendering/rendering_device.cpp:6845)
[TreeGrdProbe] RUNG A FAIL | build mode9 in _ready, minimal set | ctr[0]=0 (expect 1) <<FIRST FAILING
ERROR: Uniforms were never supplied for set (0) ... (rendering_device.cpp:6845)
[TreeGrdProbe] RUNG B FAIL | build mode9 in _ready, NO uniform set | ctr[0]=0 (expect 1)
ERROR: Uniforms were never supplied for set (0) ... (rendering_device.cpp:6845)
[TreeGrdProbe] RUNG C FAIL | build mode9 from _process(frame5), minimal set | ctr[0]=0 (expect 1)
[TreeGrdProbe] RUNG D PASS | build mode9, FULL build set (0-13) | ctr[0]=1 (expect 1)
[TreeGrdProbe] RUNG E PASS | build mode9 + cells mode7 in ONE list(same-list) | ctr[0]=1 (expect 1)
[TreeGrdProbe] RUNG F PASS | CONTROL voronoi mode7 reset (vol) | vol[0]=0.0000 (expect ~0)
[TreeGrdProbe] RUNG G PASS | SIM-opening repro mode10->mode9, full set, one list | ctr[0]=1 (expect 1)
[TreeGrdProbe] === ladder summary ===
...
[TreeGrdProbe] first failing rung = 0
```

(The `OpAtomicFAddEXT is not supported yet.` line is a harmless engine note
about an unused extension; the leaked-RID warnings are the probe exiting
without explicit teardown — irrelevant to the verdicts.)
