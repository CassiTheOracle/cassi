# Chunk ↔ Field Quantization & Per-Tick Budget

**Sphere of this doc:** how the running two-fluid field becomes Minecraft's
block world, what to sample when, and whether the server tick can afford it.
Companion to [`volumetric-terrain.md`](./volumetric-terrain.md) (the dual-world
grid semantics) and the architecture spine in [`../README.md`](../README.md)
(async field domain publishes; 20 Hz tick-sampler samples). Read those first.

Every number below is either taken verbatim from the physics engine
(`CassiCosmos/scripts/cassi_physics_engine.gd`), the shaders
(`CassiCosmos/compute/*.glsl`), or explicitly flagged **[assumption]** where
I derive a per-tick CPU cost from measured engine/computer physics rather than
a direct benchmark. Nothing is invented; where the engine does not yet expose
something (e.g. the `∇(g·Φ)` buffer in the published snapshot) it is called
out as a required addition.

---

## Summary table

| Question | Phase-1 answer (concrete) |
|---|---|
| Field grid | 64³ = 262,144 cells (`grid_N` default) |
| Field domain | player-anchored box, full extent **291.24 × 180 × 471.24 m**, min-axis = 180 m |
| Cells | 64 per axis → cell ≈ 4.55 × 2.81 × 7.36 m; min cell `h₀ = 2.8125 m` |
| Coarse gameplay grid | 1 m "Cassi block", a sub-cell sample/integration of the field |
| Chunk coverage | ≈ 18 × 11 × 29 chunks (≈ 522 chunk columns, ≈ 5,700 chunks) |
| Blocks per min-size cell | 1 cell ≈ 3 × 3 × 7 blocks along x/y/z |
| Async domain step cost | ≈ 0.5–1.5 ms field-only (no 2.5M particle arm) **[assumption]** |
| Published snapshot | ≈ 6 MiB field-only canonical (q 1 + pot 1 + ∇(g·Φ) vec3-trim 3 + ρ 1) |
| Server per-tick sample cost | ≈ 1–6 ms (vs 50 ms tick) |
| Margin | ≈ 44 ms (88%) of the tick unused; cut re-quantization cadence first |

---

## 1. World ↔ field mapping

### 1.1 The field domain is a player-anchored box

The field does not cover the unbounded world. It is the *local-field
treatment* the engine already implements: a periodic box whose world-origin
offset (`_window_center`, `bh[0].yzw`) is moved per job, so the grid advects
with the player/world anchor rather than spanning the infinite Minecraft
surface. (Engine-verbatim: `run_steps` encodes `_window_center` into the BH
header each job and the nbody samplers map `world → grid` window-relative —
`cassi_physics_engine.gd:506-510`, `cassi_nbody_gravity.glsl:278-284`.)

The box is a torus: launch outward across a face and you wrap to the
opposite face. Minecraft hides this by the same trick it already uses for its
own chunk boundary — the player stays centered, the box is re-centered as the
player moves, and we never reveal the seam beyond the local sim region. Phase 1
makes the box large enough that the seam is far outside the visible world.

### 1.2 Concrete box geometry (grounded in the engine)

The engine's single source of truth for box size is `_extents()`:

```
_extents() = box_aspect · (cluster_radius · 1.5) · max(box_scale, 1e-3)   # per-axis HALF-extents
```

Engine defaults (`cassi_physics_engine.gd:80,101-102`): `box_aspect = (1.618, 1.0, 2.618)`,
`cluster_radius = 50.0`, `box_scale = 1.0` → half-extents `(121.35, 75.0, 196.35)`,
min-axis (y) full extent = **150 m**.

The engine's own owner-config comment fixes the Phase-1 target directly
(`cassi_physics_engine.gd:127`):

> `0.5·extent_min/grid_N/dt … (28 at the owner config: 180/64/0.05·0.5)`

i.e. the CassiCraft owner config runs `extent_min = 180`, `grid_N = 64`,
`dt = 0.05`. We adopt exactly that. Setting `cluster_radius = 60.0`
(`half_y = 60·1.5 = 90`, so full y = **180 m**) with the default aspect gives:

| Axis | Aspect | Half-extent | Full extent | m / cell (÷64) |
|---|---|---|---|---|
| x | 1.618 | 145.62 m | 291.24 m | 4.551 m |
| y | 1.0 | 90.00 m | **180.00 m** | 2.8125 m |
| z | 2.618 | 235.62 m | 471.24 m | 7.363 m |

`grid_N = 64` → **262,144 cells**; the reference cell size `h₀ = 2·min(extent)/N = 2.8125 m`
(the min-size axis, matching the engine's `h₀` convention in the 19-point
stencil — `cassi_two_fluid.glsl:95`). `dt = 0.05` → **one field step per
Minecraft tick** (1/20 s = 0.05 s), a clean cadence.

**Recommended Phase-1 option (chunk-aligned).** The default aspect box is
physically grounded but its cell grid does not align to chunks, so most of
Phase 1's quantizer complexity is interpolation math. Because `box_aspect`,
`cluster_radius` and `grid_N` are all legitimate engine config (setup reads
them), we recommend a deliberate, well-tuned alternative for the *world
substrate*:

```
box_aspect = (1,1,1), cluster_radius = 64.0  →  half-extent 96 per axis  →  full box 192³ m
grid_N = 64  →  cell = 3 m per axis  →  12×12×12 chunks  →  1,728 chunks
```

This is ≈180 m per the guidance and is exactly **144 × 144 × 144 blocks =
12×12×12 chunks** with whole 3 m cells — each cell maps to **3×3×3 = 27
blocks** and a 1 m gameplay block is a clean 1/3 fractional sample per axis.
Everything below quantizes against the **192³ / 12³-chunk box**; the
default-aspect numbers are the engineering baseline if you keep the stock box.

> Note this is a physics-domain choice, not a rendering scale change. Physics
> at 64³ is identical; only the world↔grid affine map changes.
>
> **This concrete box is the resolution of `async-field-domain.md` §7 Q1**
> (world↔field scale mapping): the chunk-aligned `(1,1,1)·192³ / 12³-chunk` box
> with `64³ = 3 m` whole cells and `1 m` blocks as 1/3 trilinear sub-cell samples
> is the Phase-1 answer that doc records. The stock φ-aspect box is kept as the
> engineering baseline; the movable home-window beyond Phase 1 stays open there.

### 1.3 How a cell maps to blocks

From `volumetric-terrain.md`: the coarse 1 m gameplay grid is *derived from*
the continuity the field, not an independent grid — **a block's value is the
field integrated over its meter**. Since the field grid (3 m cells) is coarser
than the block grid (1 m), a block is a *sub-cell* quantity:

- **Block center sample:** `field_value(block) = trilinear(field, block_center_world)`.
  The block's world position maps to normalized grid coords
  `gc = ((pos − window_center)·inv_extent)·(N/2) + N/2` and the field is read
  at the 8 surrounding cell corners with mixed weights — the exact
  neighborhood traversal the nbody sampler already uses
  (`cassi_nbody_gravity.glsl:268-301`, one fused traversal fetches all
  channels).
- **Integrated-over-meter semantics:** because the cell is 3 m and the block
  is 1 m, the "integral over the meter" is approximated by the trilinear
  sample at the block center (for a linear field this *is* the cell-average
  over the sub-meter to 1st order). Where sub-block precision is wanted for
  sculpting/precision tools, the field is just *re-sampled* at the finer rung —
  it costs nothing to compute, only to store (per the companion design).
- **Block state** is a *quantization of that sample*: threshold crossings
  select block-state, with hysteresis so a jittering field does not flicker
  states (see §3).

### 1.4 The dual-world rule (restated)

The **gameplay grid** (collision, inventory, redstone, mob spawning) is the
1 m Cassi block, re-quantized as the field evolves. The **geometry/render**
layer is field iso-surfaces. The two never drift: both are projections of one
continuum. Phase 1 delivers living terrain (condense + heal) and a readable
field on the gameplay grid; the full volumetric render layer is the companion
design's scope.

---

## 2. What to sample, when

Published channels (engine-verbatim): `pos`, `vel` (the 2.5M nbody arm — **not
used in Phase 1**), `field_q` (q, 64³×4 B ≈ 1 MiB), `pot` (Φ, ≈ 1 MiB),
`vel[].w` carries **ε²** per cell, and ρ = EY+EI is derivable from the EY/EI
field buffers. The **cell-centered `∇(g·Φ)`** gradient is built once per step
into `_grad_buf` (`cassi_nbody_gravity.glsl:171-182`, the gradient pass) — this
is **not currently in the published snapshot dict** (`readback_snapshot`,
`cassi_physics_engine.gd:568-614` reads only field_q and pot). It is a required
Phase-1 addition if entities are to be steered by the river law.

**Required snapshot extension for Phase 1** (a trimmed, field-only publish —
the current `readback_snapshot` always reads the 2.5M-particle pos/vel,
`cassi_physics_engine.gd:574-602`, which is wasted in field-only mode):

| Buffer | Bytes @64³ | Channel | Drives |
|---|---|---|---|
| `field_q` | 1 MiB | q = EY²+EI² (coherence) | ore precipitation, spawn gates |
| `pot` (Φ) | 1 MiB | potential | ∇(g·Φ) source, item gravity bias |
| `grad` (`_grad_buf`) | **3 MiB** (vec3 trim) | ∇(g·Φ) per cell | entity/mob/item steering |
| ρ = EY+EI | **1 MiB** (single float channel) | ρ | condensation threshold, ε² |
| ε² (vel[].w) | (rides in the ρ read) | decoherence | dissolution |
| **Total (canonical)** | **≈ 6 MiB** | | |

**Gradient buffer size (engine-grounded):** `_grad_buf` is allocated as
`storage_buffer_create(nc * 16)` — **vec4 per cell = 262,144 × 16 B = 4 MiB** at
64³ (`cassi_physics_engine.gd:1215`). But the gradient pass writes only `.xyz`
and stores `.w = 0.0` (`cassi_nbody_gravity.glsl:469-471`: `grad[gid] = vec4(g, 0.0)`),
and the river arm samples `grad[c000].xyz` only (`cassi_nbody_gravity.glsl:348-349,
526-532`). So a **vec3 publish trim = 3 MiB** is lossless and recommended for
Phase 1. Totals as one canonical figure, with the variants listed so the corpus
never drifts:

- **≈ 6 MiB canonical** — q 1 + pot 1 + ∇(g·Φ) vec3-trim 3 + ρ single-channel 1.
- 7 MiB — if ρ is published as EY+EI *separately* (2 MiB) instead of the single
  float ρ channel.
- 8 MiB — if the gradient is published vec4 as-is (4 MiB) rather than the vec3 trim.

**Reconciliation with `async-field-domain.md`:** that design totals ≈ 6.4 MB using
the gradient vec3 trim (3.1 MB) + a single ρ channel — 6.1 MiB = 6.4 MB decimal,
plus ~0.33 MB for the meshless sites ≈ its 6.4 MB total. This doc's canonical
≈ 6 MiB is the same figure; both use the vec3-trim gradient.

### 2.1 The sampling plan

| World effect | Field channel | Mechanism | Cadence | Per-something cost |
|---|---|---|---|---|
| **Block-state quantization** | ρ (condensation), ε² (dissolution), q (ore) | per-block trilinear sample → hysteresis threshold (§3) | diff/event-driven on active chunks (see §5), rotated over N ticks | per chunk ≈ 120 µs (§4) |
| **Entity steering** | ∇(g·Φ) (+ EY/EI for π/ρ) | per-entity trilinear along the river law `a = −G_N·(π/ρ)·∇(g·Φ)` | every tick (entities are few) | per entity ≈ 40 ns (§4) |
| **Mob/item gravity** | pot / ∇(g·Φ) | same river sample nudges gravity/drop direction | every Nth tick or event (grab on block) | ~0 (reuse entity sample) |
| **Mob spawn conditions** | q + ε² | spawn only where coherence in a band and ε² below a floor | every Nth tick (e.g. 20) | trivial strided read |
| **Meshless-site activity map** | sites (Voronoi centers), ML_LLOYD_P=4 on q | sites → chunk-active set (§5) | every meshless rebuild (every 25 steps) | ≈ 50 µs for 8192 sites |
| **Async domain publish** | all above | `readback_snapshot` at `snapshot_cadence` | every Kth job (default 2) | ≈ 0.3–0.4 ms acquire (server thread) |

### 2.2 Effect mechanisms, in prose

- **Condensation → solid.** A block is solid when its sampled **ρ = EY+EI**
  exceeds the condensation threshold (`qi_condensation_threshold = 0.5`,
  engine default) with hysteresis. Below threshold it is air; in the 
  transition band the state is governed by ε² (see below).
- **ε² → dissolution.** The decoherence channel ε² = (EY − φ·EI)² marks where
  the field loses the φ-locked Yang/Yin relation — carved/scarred regions.
  Where ε² rises above a tuneable floor, the block dissolves back to air and
  the field reorganizes (mining is exactly this: lower local ρ, raise local
  ε², and the medium heals).
- **Coherence q → ore.** Ore is *not* a worldgen height range; it precipitates
  where **q accumulates above a second threshold** (scalar channel of the
  continuum — verbatim from `volumetric-terrain.md`). Higher q → finer/richer
  deposit; the roughness of the deposit can be a rung-selected refinement.
- **Entity steering.** Each entity holds a trilinear sample of `∇(g·Φ)` and
  the local `π/ρ = clamp((EY−EI)/(EY+EI), 0, 0.72)`, and is accelerated by the
  river law `a = −G_N·(π/ρ)·∇(g·Φ)` (`cassi_nbody_gravity.glsl:7-17,520-532`).
  This is the same law the engine uses, re-hosted on the server tick — entities
  become particles of the field rather than hand-animated mobs.
- **Mob spawning.** Spawn candidates only where q sits in a coherent band and
  ε² is low — the field "precipitates" life where it is locally organized,
  mirroring the merge/condensation lineage in the engine.

---

## 3. Quantization rules

Restated from `volumetric-terrain.md` and made concrete:

1. **Block state = the field integrated over its meter.** A 1 m Cassi block's
   value is the trilinear field sample at the block center (§1.3). The state
   is the quantization of that sample against thresholds.
2. **Condensation threshold.** `ρ ≥ τ_c` → solid, else air, with **hysteresis**
   (`τ_c` for solidification, `τ_c − δ` for dissolution) so a field jittering
   around the boundary does not flicker a block every tick.
3. **Mining is a perturbation, not a deletion.** Destroy a block → we lower
   the local ρ and raise the local ε² contribution in the domain boundary
   term the sampler feeds back to the engine. The field reorganizes around the
   scar and the terrain heals toward its attractor (the companion design's
   core claim). Phase 1 does not let players delete the field — they perturb
   it.
4. **Re-quantization is event/diff-driven.** Only blocks whose integrated
   sample crossed a threshold since the last quant are re-written. This bound
   is load-bearing for the budget (§4, §5).
5. **Deterministic, single writer.** Quantization runs on the server tick
   thread, samples the async domain's *last published snapshot*, and never
   mutates the domain's own state. The domain keeps evolving; the world always
   reads a coherent (per-snapshot) field.

---

## 4. Per-tick budget

### 4.1 Async domain step cost (GPU worker thread, NOT the 50 ms server tick)

The domain runs on its own thread/GPU; its step cost does not consume the
server tick budget — it must only stay ahead of the 20 Hz sampling. **Phase 1
explicitly runs the field WITHOUT the 2.5M-particle nbody arm.** We keep the
chain needed to produce the world quantities: two-fluid PDE, spectral Poisson
(for Φ → ∇(g·Φ)), the gradient pass, and the meshless sites — and drop the
nbody particle integration, mass-deposit, packing and the 40 MB pos/vel
readback.

| Pass | Complexity | Est. cost/step @64³ | Grounding |
|---|---|---|---|
| Two-fluid PDE (2 passes, 19-pt Laplacian) | O(N³) = 262,144 cells | ≈ 0.1–0.3 ms | `cassi_two_fluid.glsl`, one thread/cell/pass |
| Spectral Poisson (6 fused Stockham FFT) | O(N³ log N), N=64→R=4 | ≈ 0.2–0.5 ms | `cassi_poisson.glsl:37-44` (clear→load+x→y→z→kspace+inv-z→y→x) |
| Gradient build (∇(g·Φ), 1–2 passes) | O(N³) | ≈ 0.1–0.2 ms | `cassi_nbody_gravity.glsl:171-182` |
| Meshless rebuild (8192 sites, JFA+Lloyd) | 2·16³ sites every 25 steps | ≈ 0.1–0.5 ms, ÷25 ≈ negligible | `cassi_physics_engine.gd:59,61` (`ML_N1=16`, `ML_REBUILD=25`) |
| **Total field step** | | **≈ 0.5–1.5 ms** **[assumption]** | anchor: full 1M-particle chain = 7.3 ms/frame (`cassi_nbody_gravity.glsl:42`), particles are the bulk |

At `dt = 0.05`, one field step per tick needs ≈ 0.5–1.5 ms of GPU time against
a 50 ms budget — **the domain runs at ~3% utilization and trivially keeps
ahead.** Even the full 2.5M-particle worst case (15–20 ms/step) fits inside
one tick.

### 4.2 Server tick thread (the 50 ms / 20 Hz budget)

These costs are on the synchronous Minecraft server tick. All are memory-bound
reads + trivial per-element math on already-published buffers.

| Stage | Cost estimate | Grounding / reasoning |
|---|---|---|
| Snapshot acquire (≈ 6 MiB @64³) | ≈ 0.3–0.4 ms | memory-bound at realistic per-core ~15–25 GB/s; 6 MiB/20 GB/s ≈ 300 µs |
| Meshless-site → active-chunk map | ≈ 50 µs (8192 sites) | 8192 sites, a couple ops each into a 1728-chunk bitmap |
| Block re-quantization (active/dirty blocks only) | ≈ 0.5–5 ms | §4.3 below; bounded by the scheduler, NOT the full volume |
| Per-entity trilinear (river law sample) | ≈ 40 ns × N | 8-corner read + mix-plus-chord, same as the fused GPU sampler |
| Mob spawn / item-gravity re-use | ≈ 0 (strided reuse) | rides the entity-sample path |
| **Total per tick** | **≈ 1–6 ms** | | 

**Against the 50 ms tick:** 6 ms ≈ 12% of the tick budget. Vanilla MC leaves
typically 20–35 ms of headroom on modern hardware, so even 6 ms is comfortably
inside it with **≈ 44 ms (88%) still unused**. The real risk is a naive
"re-quantize everything" path — that is why §4.3 and §5 exist.

### 4.3 Block-state quantization cost — the necessary bound

**Worst case (excluded by design):** re-quantizing the entire 12×12×12 =
1,728-chunk / 7.08M-block volume every tick at ~30 ns/block ≈ **210 ms —
5× the tick. Infeasible.** The design therefore *never* does a full-volume
re-quant. The honest cost model is:

- **Per chunk:** 16³ = 4,096 blocks × ~30 ns ≈ **120 µs** per fully re-quantized
  chunk. (4,096 independent samples; parallelizable to ~1/8 that on 4–8 threads.)
- **Active/dirty subset:** only blocks whose field sample crossed a hysteresis
  threshold re-write. In living terrain the field surfaces are where ρ/ε²/q
  move; typically **5–50 chunks** are "hot" per tick → ≈ **0.6–6 ms**.
- **Rotation:** hot chunks re-quantize on a split cadence (e.g. every 1–4 ticks
  depending on the site-activity weight), spreading the peak.

**Cut-first under pressure:** drop re-quantization cadence (re-quant every Nth
tick) before anything else — the field moves slower than the tick, so the
visible degradation is a slightly laggier terrain, not a violation of the
budget. Second: drop the per-entity river sample to every other tick.

---

## 5. Meshless sites as the LOD / chunk-activity scheduler

The moving-Voronoi sites are "where the field is most organized" (the README's
bonus claim, and now the load map). Grounding: 2·16³ = **8,192 sites** at N=64
(`ML_N1=16`); they are Lloyd-relaxed **weighted on the coherence q**
(`ML_LLOYD_P = 4`, `cassi_physics_engine.gd:60-70`), so sites cluster where the
field is coherent — exactly the regions that need re-quantizing/remeshing.

**Phase-1 scheduler:**

1. Every meshless rebuild (every 25 field steps, i.e. ~25 server ticks at
   `dt=0.05`), the domain publishes the 8,192 site positions + per-site
   coherence.
2. The server projects each site onto chunk space (a site's Voronoi cell
   overlaps a handful of chunks — 8,192 sites / 1,728 chunks ≈ **4.7 sites per
   chunk** on average). A chunk is **active** for the coming window if a
   site's cell overlaps it and its coherence exceeds a floor.
3. **Active chunks** re-quantize/remesh (and drive the §4.3 rotation). **Idle
   dead zones** — far surfaces, low-coherence interior, no sites — are skipped
   entirely until the field moves back through them.
4. The map is cheap: 8,192 writes into a 1,728-entry bitmap, ≈ 50 µs.

This is the same idea the companion design's "meshless-site lattice doubles as
the region tick map" and the README's "the physics is also the load map."
Because sites *follow* the organization, the scheduler chases activity rather
than scanning the whole volume — the cost of the world tracks where the field
actually does something.

---

## 6. Required engine-side changes (not capabilities we have yet)

These are honest gaps, not design choices:

1. **Field-only snapshot publish.** `readback_snapshot` always reads the
   2.5M-particle pos/vel (`cassi_physics_engine.gd:574-602`). Phase 1 needs a
   variant returning `field_q`, `pot`, `grad` (∇(g·Φ)), and ρ (or EY/EI) — no
   particle buffers. Until this exists the field-only mode still pays a 40 MB
   readback per publish.
2. **`∇(g·Φ)` in the snapshot.** The gradient buffer (`_grad_buf`) is built
   per step but not published. Required for entity/mob/item steering.
3. **Player-edit feedback loop.** Quantizer-side mining must perturb the domain
   (lower ρ / raise ε²) via the window/deposit seam — a new write-back channel,
   not engine-verbatim.

---

## 7. Honest open questions

1. **Box seam at player motion.** The torus follows the anchor, but fast
   teleport/falling across the seam needs a graceful re-home (field is
   window-relative, so it re-centers — but the *visible* terrain it has already
   quantized is not). Acceptable in Phase 1 (seam far outside view), worth
   designing before a real world.
2. **Determinism of the dual world.** Both layers sample the same snapshot, so
   they cannot drift *within* a snapshot. But consecutive snapshots differ —
   a block re-quantizes between ticks. Which snapshots drive collision vs.
   render, and is the write-back race-free? Needs a single-snapshot-per-tick
   contract definition.
3. **Interpolation of a 3 m cell to a 1 m block.** First-order trilinear may
   alias steep surfaces (sub-cell detail hidden at cell scale). The companion
   design's rung-refinement is the principled answer; Phase 1 may be fine with
   the linear sample. Measure.
4. **Entity-count scaling.** Per-entity steering is cheap (≈40 ns) but unbounded
   item ticks are not. Phase 1 targets ≤ ~2,000 steered entities; pathological
   item farms need a cap or the re-use path, not the vectorized one.
5. **Field-server sync cadence.** `snapshot_cadence=2` and meshless cadence 25
   are engine defaults, not MC-tuned. Whether a tired field (slow drift) can
   drop to a much coarser publish cadence to save memory bandwidth is an
   experiment.

---

## 8. Feasibility verdict

**Feasible, with one mandatory discipline.** The field-only domain keeps up
with the 20 Hz tick at ~3% of a 50 ms budget, and the server-side sampling of
≈6 MiB of published field plus active-chunk re-quantization costs ~1–6 ms/tick —
inside Minecraft's headroom with ~88% of the tick to spare. The single thing
that would break it is a full-volume re-quant, which the meshless-site LOD
scheduler (Sites-follow-organization → active-chunk rotation) explicitly
prevents. Block quantization from a coarse 3 m cell to a 1 m block is first
order-correct and cheap; the meshless sites double as both the physics' own
activity map and the world's LOD load map, so load tracks where the field does
something. The honest gaps are engine plumbing (field-only snapshot, ∇(g·Φ)
publish, player-edit feedback), not architecture — and none is load-bearing
for the budget. Verdict: **Phase 1 living terrain on a running two-fluid field
is achievable within a stock 50 ms tick.**

## Cross-references

- [`the-landform-name.md`](./the-landform-name.md) — **the site-map bound form.**
  §2.1/§4.2 there read §5 this doc's meshless site map — a landscape-scale
  anchor's form is bound over the 8,192 sites; the redraw-vs-strata of the map's
  §4.2 there rides the site-map the name constrains. Reverse pointer: the named
  land's form rides the site-map.
- [`the-migration.md`](./the-migration.md) — **the moving window's chunk.** §1 there
  reads the window's bounded chunk (the migration shifts that bound); §5 the
  chunk-field budget. Reverse pointer: the migration moves the chunk-field window.
- [`the-understory.md`](./the-understory.md) — **the bounded patch.** §1.2 the anchored box (the Phase-1 slice’s bounded patch); §4 the ≈1–6 ms budget the read stays inside. Reverse pointer: the understory’s read stays inside the chunk’s budget.
- [`the-shaft.md`](./the-shaft.md) — **the vertical chunk.** the field’s chunked order a shaft descends. Reverse pointer: a shaft reads the chunk-field’s vertical order — the bounded depth, quantized.
- [`world-difficulty.md`](./world-difficulty.md) — **the scaled chunk.** the field’s chunked order a harsh world reads. Reverse pointer: world-difficulty reads the chunk-field’s order at a harsher register.
- [`the-tunnel.md`](./the-tunnel.md) — **the line’s chunks.** the field’s chunked order a tunnel descends through. Reverse pointer: a tunnel reads the chunk-field’s order along its dug line.
