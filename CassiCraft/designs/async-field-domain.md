# Async Field Domain + Tick-Sampler Module Architecture

**Question under design:** how the Cassi two-fluid field — a heavy, continuous,
asynchronous physics computation — is rehosted as a Minecraft-mod subsystem, and
how the 20 Hz server tick consumes it without ever blocking on it (or being
touched by it).

This is the load-bearing seams document for the whole CassiCraft overhaul. The
*vision* (README) and the *terrain representation* (volumetric-terrain.md) both
assume one thing this document supplies: the exact contract between the physics
domain thread and the game-server thread that makes it safe for the world to be
*epiphenomenal* to a field that runs on a thread the server does not control.

The physics engine already exists and was deliberately decoupled from its host
(Godot) to be rehostable. Its Threading contract, publish model, and readback
byte-layouts are the source of truth here. Every claim below that cites an
engine method (`start_threaded()`, `submit_steps()`, `readback_snapshot()`,
… ) reflects the real API of `cassi_physics_engine.gd`.

---

## 1. Module boundaries

Four modules, one dependency direction: **tick-sampler and world-writer read
the domain; the world-writer mutates Minecraft world state; the domain never
touches server-owned structures.**

```
┌─ Field domain (JVM worker thread) ───────────────┐
│  ported engine core (physics only; touches       │
│  NOTHING outside itself)                         │
└─────────────┬── publish (cadence, not per tick)  │
              │
┌─────────────▼────────────────────────────────────┐
│ Tick-sampler (server thread, 20 Hz, read-only)   │
│  freshest publish → chunk/mob/vehicle intent     │
└─────────────┬── intent queues                     │
┌─────────────▼────────────────────────────────────┐
│ World-writer (server thread, the ONLY mutator)   │
│  applies intent → real chunks/entities/vehicles  │
└──────────────────────────────────────────────────┘
```

| Module | Owns | May do | Never does |
|---|---|---|---|
| **Field domain** | the engine instance, its worker thread, its GPU/CPU buffers, the publish snapshot | run the PDE/meshless/tree chain; publish immutable snapshots on cadence | touch any Minecraft class, any `ServerWorld`, `Chunk`, `Entity`, or transaction |
| **Publish contract** | the wire format between domain and sampler (an *interface*, in this table but not a module that owns state) | — | — |
| **Tick-sampler** | reading the freshest publish; deriving *intent*: chunk↔field quantization, entity/mob/item steering, rigid-body vehicle forces | allocate and read field arrays on the server thread | mutate world state directly |
| **World-writer** | all mutation of Minecraft world state | apply sampler intent to real chunks/entities/vehicles | read the domain after startup (it consumes sampler-derived intent, never the raw field) |

**Dependency direction is acyclic and enforced by module boundaries, not by
discipline:** the domain has no import of any Minecraft symbol, so the two
directions are literally inexpressible in the wrong order. The sampler and
world-writer run on the server thread and are the *only* modules that see a
`ServerWorld`. The domain thread and the server thread interoperate only
through the publish payload.

### Why the domain is "the ported engine core"

The engine's own header documents its decoupling contract: it "touches NOTHING
outside itself: no class_name, no globals, no renderer access," and every member
is `_`-prefixed or class-local so it is safe to instantiate in any host. Its
threading contract is the model we keep:

- A local compute device is **created ON the worker thread** that uses it.
- Shader/SPIR-V resource loading runs on the **main thread** and is passed into
  the worker (`cfg.spirv`), because such loading is not thread-safe.
- Cleanup is a dedicated method, **`shutdown()`** — never named `free()` (the
  host's GC-freed `free()` is shadowed and would leak the device). On Minecraft
  the analogous constraint applies: the worker thread must not cross any
  classloader/scheduler boundary, and teardown is a worker-side explicit close,
  not a GC hook.

The JVM port keeps the same contract with different machinery: shader/kernel
sources are loaded and compiled on the main thread; the worker thread owns the
compute context and runs the chain; shutdown is an explicit `close()` on the
worker. Phase 1 is CPU-first (see §6) so the "compute context" is a CPU solver
with the same lifecycle.

---

## 2. The publish payload

The publish is **byte-accurate** to the engine's readbacks. The engine's
`readback_snapshot()` returns `{pos, vel, field_q, pot, t, packed}`; the worker
publishes a job result `{executed, step_count, t}` and, on cadence jobs, nests
`snapshot` + `telemetry` (see §2.3). The Minecraft publish reuses those exact
buffers, mapped to the game's needs.

### 2.1 Field grid channels (64³ = 262,144 cells)

| Channel | Engine source | Element type | Bytes (fp32) | Notes |
|---|---|---|---|---|
| `q` (coherence) | `field_q` (`readback_snapshot`) | `float` | 262,144 × 4 = **1.0 MB** | read back `nc * 4` bytes; stays fp32 with or without packaging |
| `ε²` (decoherence) | recomputed in the domain from the ey/ei/vel scratch (the PDE recomputes q and ε² each step) | `float` | 1.0 MB | in the engine ε² is derived, not read back as its own array — the JVM domain may ship it computed from the same scratch, or re-derive on the sampler side from q (cheaper); see open question Q5 |
| `ρ` (density) | `mass_density` / `rho[]` binding of the two-fluid and Poisson shaders | `float` | 1.0 MB | the deposit/convert chain materializes ρ per step |
| `pot` (potential Φ) | `fft` buffer, real part (`readback_snapshot`) | `float` | 1.0 MB | read back as `nc * 8` (vec2) then sliced to fp32 per cell for `pot` |

Alongside the engine-readback channels the vision's spine lists **`∇(gΦ)`
gradient** (written `∇(g·Φ)` throughout this corpus — the canonical form of the
river-law gradient; the two are the same quantity). The engine computes a
cell-centered gradient pass (the `_grad_buf`
`vec4` per cell, `cassi_nbody_gravity.glsl` bindings 7/8, dual-lattice
`_grad_buf2`), consumed by the river arm, not returned by
`readback_snapshot()`. The JVM domain either adds this buffer to its own publish
(vector3 per cell) or exposes it via the same cadence-limited channel. Its cost
(cell × 3 floats ≈ 3.1 MB fp32, or cell × 3 halves ≈ 1.6 MB) is the one
measured decision Q5 surfaces.

### 2.2 Meshless sites and bodies

| Channel | Engine source | Count / bytes |
|---|---|---|
| **Sites** (moving-Voronoi) | the meshless arm; `ML_N1 = 16` → **2·16³ = 8192 sites** at N=64 | site = position + field values (ψ_y, ψ_i, π_y, π_i, gradient) → order 8192 × ~10 floats ≈ 328 KB fp32; halved under fp16 |
| **Condensed bodies** | the merge chain (`particle_merge`): "dust → object → BH"; `pos[].w` carries mass/death | a sparse, small array (tens to hundreds at Phase 1 scale), dominated by the merge record buffers |

The site count is a hard constant from the engine (`ML_N1 := 16`, "2·16³ = 8192
sites at N=64"), not a Phase-1 tuning dial. Bodies are sparse; they get their own
publish record separate from the dense grid, so the sampler does not walk a
262,144-cell array to find `n` moving objects.

### 2.3 The fp16 packed option and the cadence model

`readback_snapshot(packed=true)` halves the pos/vel readback (`N × 8 B` per
array vs `N × 16 B`): word0 = half(x)|half(y)<<16, word1 = half(z)|half(w)<<16,
with `field_q` and `pot` **staying fp32 either way**. On Minecraft the "particles"
are the meshless sites and condensed bodies, so the packed path halves their
arrays. The publish therefore carries a `packed` flag so the consumer picks its
unpacking path (the engine's snapshot dict carries `"packed"`).

**Publish cadence mirrors the engine's `snapshot_cadence`.** In
`_threaded_run_job` the snapshot + telemetry readbacks run every Kth job; a
non-publish job carries **only** `{executed, step_count, t}` and skips the
mirror upload. The first job always publishes (the bootstrap needs the
immediate snapshot), and the sampler consumes the **freshest unconsumed**
publish via `poll()` (which drops stale generations — `_consume_latest`
returns only when `_res_gen > _consumed_gen`, so an idle sampler never sees a
backlog of intermediate states).

So the domain publishes on a **job cadence (every Kth physics job), not per
tick and not per step**. With `JOB_STEP_CAP = 64` and `TREE_JOB_STEP_CAP = 8`,
a coalesced backlog drains over many short bounded-slice jobs; each such job is a
publish candidate. Phase 1 chooses K so that a publish lands on the order of
every server tick-to-few-ticks (see §3.1), with lighter "tick-only" publishes
`{executed, step_count, t}` available every job so the sampler always knows the
domain is alive and how far it has advanced.

The packed publish payload for one full cadence (64³ grid + sites + bodies),
fp16 for the moving arrays:

| Item | fp32 | fp16-packed |
|---|---|---|
| q (262,144 × 4) | 1.0 MB | 1.0 MB (stays fp32) |
| ρ (262,144 × 4) | 1.0 MB | 1.0 MB |
| pot (262,144 × 4) | 1.0 MB | 1.0 MB |
| ∇(gΦ), if published (262,144 × 12 / × 6) | 3.1 MB | 1.6 MB |
| sites (8192 × ~40 B) | ~330 KB | ~165 KB |
| bodies (sparse) | ~KB | ~KB |
| **with ∇**: total | **~6.4 MB** | **~4.8 MB** |
| **without ∇** (recomputed) | **~3.3 MB** | **~3.2 MB** |

A full cadence publish at 6.4 MB even only every Kth job is a real but bounded
read; the 3.3 MB q/ρ/pot baseline is comfortably cheap. The fp16 option mainly
pays off for the site/body arrays and for the grid channels if the sampler
accepts half-precision field reads (Q5).

---

## 3. The tick-sampler design

The sampler runs **on the server thread at 20 Hz** and reads the **freshest
publish** (dropping stale generations). It is a *derivation* stage: it turns a
field snapshot into *intent* — a small, ordered list of "mutations to attempt"
that the world-writer applies. The sampler never mutates.

### 3.1 Cadence: every tick vs every Nth tick vs event-driven

The sampler's consumption cadence is decoupled from the *publish* cadence, and
each derived consumer runs at its own rate:

| Consumer | Cadence | Why |
|---|---|---|
| Domain liveness {executed, step_count, t} | **every tick (20 Hz)** | cheap — the tick-only publish right; keeps the load map alive |
| Field↔chunk quantization | **every Nth tick** (e.g. every 5–10 ticks, ~2–4 Hz for the near field), plus on dirty events | chunk edits are expensive and re-quantization is idempotent; event-driven on player edit/contact overrides the cadence |
| Entity/mob/item steering | **every tick, but only within the active window** (the region around the meshless-site lattice that doubles as the activity map) | physics cost is low per entity; restricting to the active set keeps the 20 Hz budget small |
| Rigid-body vehicles (Phase 2 KSP) | **every tick** in the vehicle's locality, **block=true** synchronously when a player contacts/boards (see §4) | vehicles are the player-touched exception |

The meshless-site lattice is the **region tick map** (README): the moving
Voronoi sites are "where the field is most organized", so near-field, high-cadence
consumers attach to the sites' neighborhood; elsewhere the sampler coasts on the
slow-cadence field means. This makes the physics also the load scheduler.

### 3.2 Chunk ↔ field quantization

This is the sampler's core derivation and it feeds the volumetric-terrain "dual
world" (geometry iso-surfaces + coarse 1 m gameplay grid, both projections of the
same ρ/q continuum). On its cadence the sampler:

1. Bins the publish grid (or evaluates it wherever a coarse gameplay block
   needs a value) into the **coarse 1 m "Cassi block" grid** — each block
   carries the field value integrated over its meter (the layer that keeps
   collision/redstone/inventory playable).
2. Computes iso-surface geometry (Marching Cubes / Dual Contouring) for the
   live render layer only **where activity is high**; far/LOD regions reuse the
   vanilla mesher (per volumetric-terrain.md).
3. Emits a **dirty-chunk intent list** — which coarse and fine cells changed
   value past a threshold since the last quantization — for the world-writer to
   apply.

Quantization is idempotent: re-quantizing an unchanged region is a no-op, so
the every-Nth-tick cadence is safe against drift between the two
representations (the coarse block's value *is* the field integrated over its
meter, so the two "never drift").

### 3.3 Entity / mob / item steering

For each entity in the active window, the sampler reads local q / ρ / pot /
∇(gΦ) from the publish and derives a steering *intent*:

- **Terrain grounding:** a block's local ρ threshold decides supported vs
  airborne (walkable if the coarse block below carries enough matter).
- **Mob/ecology (Phase 3):** the field is the spawn/movement driver — intent is
  "mob X should wander toward coherence ridge / away from decoherence well".
- **Items:** buoyancy/drift from local ρ and pot gradient, pushed as intent.

The sampler emits intent per entity (a lightweight record, e.g. a target
position + steering weight), not a teleport; the world-writer turns it into
velocity/position applied through the normal server tick, so physics never
bypasses Minecraft's own entity rules. Phase 1 keeps mobs on vanilla behavior;
the intent pipe is the unchanged seam Phase 3 fills.

### 3.4 Rigid-body vehicles (the KSP layer)

Vehicles are rigid bodies (six-DOF + angular) integrated by the sampler against
the local pot gradient and field values. For **free-flight** (no player) the
sampler integrates from the freshest publish at its own fixed sub-step,
emitting continuous vehicle intent — the same path as mob steering, just a
larger state. **Contact** (player boarded, or a rocket thrusting under a
player's input) switches to the synchronous loop of §4 for that one vehicle's
locality.

---

## 4. The two fidelity loops

The engine already has two fidelity paths built in — the design reuses them
rather than inventing a third.

### 4.1 The async continuum (heavy, slow) — default

- Driven by `submit_steps(target, block=false)`: the target is **cumulative**,
  newest-replaces-pending, so the server never queues a backlog; steps are
  never silently lost. The sampler consumes via `setup_ready()` / `poll()`.
- Runs at the publish cadence of §2.3; **non-blocking by construction** — the
  server tick never waits on it (this is the whole point of the spine diagram).
- Used for: terrain, chunk quantization, mob/item drift, free-flight vehicles,
  and all of the standing world.

### 4.2 The synchronous path — player-touched mechanics

- `submit_steps(target, block=true)` returns the **fresh publish** for that
  job (`_wait_executed` blocks until a publish with `executed >= target`
  arrives and returns the freshest such publish). The engine's doc calls this
  "the synchronous path".
- On Minecraft this is the **rocket/contact case** (README Phase 2): a player
  boards a vehicle or triggers a coherence-injection rocket, and the outcome
  must reflect the field at a *specific* instant — acceptable to stall a few
  ticks for a physics answer the player is directly feeling.
- **Guardrail:** this path is allowed only for a *bounded locality* (one
  vehicle / one player), gated to rarely fire, and the server thread blocks for
  only as long as the engine's per-job cap dictates (`JOB_STEP_CAP = 64`
  ≈ a short bounded-slice job, not a monster chain). It is the exception that
  proves the async rule: the world's *continuous* state is never read
  synchronously, only a specific player-touched outcome.

When to use which:

| Situation | Loop |
|---|---|
| Terrain condensing/healing, chunk quantization, mobs, free-flight | **async** (cont.)
| Player boards a vehicle / fires a coherence rocket / precision-sculpts with a tool | **sync** for that locality only |
| Everything else | **async** |

---

## 5. Threading hazards and the handoff

### 5.1 The immutable-snapshot handoff

The domain thread and the server thread meet only at the publish boundary. The
engine already serializes that meeting with a mutex: `_res_mutex` guards
`_res_result` / `_res_gen`, and `poll()` / `_consume_latest()` read a
**complete, immutable result** under the lock and hand back a reference the
caller owns. On the JVM port, the same rule holds:

- The worker fills a publish **off to the side, in full**, then publishes it
  under a lock as an **immutable** payload (the arrays are never mutated after
  handoff — the worker builds a fresh one next job; it does not reuse and
  mutate a published buffer).
- The sampler reads the immutable payload with **no lock held** (it owns the
  reference). Because the worker never mutates a published object, the sampler
  needs no read lock and the worker never blocks the server tick.
- Stale-generation dropping (`_consumed_gen` / `_res_gen`) is preserved: the
  sampler observes only a monotonically increasing generation and ignores any
  publish it has already consumed, so a slow server never compounds old states.

This is the *only* cross-thread data structure. There is no shared mutable
physics state, no field array read directly on the server, no domain mutation
of game state.

### 5.2 Server-thread constraints

- **The server tick never blocks on the domain.** The async loop is the norm
  (§4.1); any blocking is confined to the §4.2 guardrailed locality and bounded
  by the job cap.
- **The domain thread never touches server-owned structures.** It holds no
  `ServerWorld`, `Chunk`, `Entity`, or `Level` reference. It cannot even
  *name* them (§1). Feedback *into* the domain (player edits, injections) goes
  **one way**: the sampler collects them and passes them back as inputs to the
  next `submit_steps` (mirroring how the engine's job dict carries
  `window_center`, `home_window`, and consumer-cadence meta into each job) —
  never by the worker reading game state.
- **Class loading / lifecycle:** shader/kernel sources load on the main thread
  before the worker starts (the SPIR-V pre-load constraint, §6); the worker is
  started once at world load via the engine's `start_threaded()` and stopped
  via `stop_threaded()` (which joins the worker; the worker's own exit path
  runs `shutdown()` — frees buffers/pipes and the device **on the worker**,
  never cross-thread `free()` of device resources). Reinit = `stop_threaded()`
  + `start_threaded(new cfg)`.
- **The sampler runs on the mod's own server-dispatched tick**, not inside the
  engine. It allocates its arrays and does quantization work inside its
  budgeted slice, and defers heavy re-mesh intent to the world-writer so it
  never overruns the 20 Hz tick.

---

## 6. The OpenCL upgrade path

Phase 1 is **CPU-first**: the JVM worker thread runs the 64³ PDE + 8192
meshless sites + tree gravity on the CPU. GPU acceleration later via OpenCL,
replacing the CPU solver *behind the same publish contract* — the sampler and
world-writer never know the difference.

The twin constraints that shape this are lifted straight from the engine's
threading contract:

1. **Device creation on the worker:** a local compute device must be created on
   the thread that uses it. The JVM worker creates (and owns) its own OpenCL
   context + command queue, mirroring `_threaded_main`'s `create_local_rendering_device()`.
2. **Kernel-source loading on the main thread:** the engine pre-loads
   `RDShaderFile`s and passes extracted SPIR-V into the worker via `cfg.spirv`
   because resource loading is not thread-safe. The OpenCL port does the same:
   the main thread reads/compiles the `.cl` kernel sources (or pre-builds
   program binaries) and hands the compiled `cl_program`/`cl_kernel` objects to
   the worker in its startup config. Boundary: the worker **never** opens or
   compiles sources itself; it receives ready kernels.

The CPU solver is therefore modeled as an *adapter* implementing the same
internal interface as the future OpenCL command queue: same lifecycle
(start/stop, worker-side device), same job loop (cumulative target,
newest-wins, per-job step caps), same readbacks (the §2 buffers), same publish
handoff. Swapping CPU → OpenCL is a construction-site change (one factory
selects the backend), not a contract change — the publish payload and the
sampler are byte-identical either way.

The `lwjgl-opencl` jar + native libs are not in vanilla's classpath; they must
be bundled as a mod dependency (both Fabric and NeoForge allow this). OpenCL
device probing (vendor/version/queue) happens on the main thread at world load.

---

## 7. Honest open questions and feasibility verdict

### Open questions

- **Q1 — World↔field scale mapping.** **Resolved for Phase 1 in the companion
  doc** (`chunk-field-quantization.md`): it recommends a chunk-aligned Phase-1
  box (`box_aspect=(1,1,1)`, `cluster_radius=64` → 192³ m) with 64³ cells = 3 m
  whole cells → a 12×12×12-chunk footprint, and 1 m blocks sampled as 1/3
  trilinear sub-cell samples — while keeping the stock φ-aspect box as the
  engineering baseline. Open **beyond Phase 1**: how the **movable home-window**
  (`window_center` shipped per job by the engine's slow-cadence COM tracker)
  re-anchors the finite box over the infinite world (the engine already supports
  the movable-window seam, but the relocation policy past the first box is not
  settled). **Owner-by-assignment:** the beyond-Phase-1 relocation policy is
  owned by `world-seams.md` §4.2 (which assigns itself explicitly — anchor-to-
  window, and the approach threshold for flipping the anchor), with
  `resonance-seeds.md` open-Q5 and `field-archaeology.md` §6c#2 depending on it.
  The chain reads both ways.
- **Q2 — Publish memory churn.** A full cadence publish reaches ~6.4 MB
  (with ∇). Buffering and GC-pressure strategy on the server thread (reuse,
  pooled buffers, double-buffer handoff) is an implementation concern the design
  must settle before Phase 1 measurement, not after.
- **Q3 — The `∇(gΦ)` gradient channel.** The engine computes it but
  `readback_snapshot()` does not return it; the JVM domain either extends its
  own publish with the gradient or lets the sampler re-derive it from `pot`.
  Cost: ~3.1 MB fp32 vs a re-derivation. Needs a Phase-1 measurement (Q5).
- **Q4 — Player-return channel.** How player edits / injections round-trip into
  the domain (as job-dict inputs, per §5.2) without letting the server thread
  touch physics state. Mechanical, but the exact input schema and cadence are
  downstream. **Consumers (two-way cross-references below):** the magic system
  (`coherence-magic.md` §5.1), the harvesting/write-back machines
  (`energy-harnessing.md` §2 intro and §0), and the material lab
  (`custom-blocks.md` §2) all build as consumers of this channel; the schema they
  propose (a small per-op record `{op, worldPos, rung, magnitude, sustain}`) is
  the input the seam must carry.
- **Q5 — Half-precision field reads.** `field_q` and `pot` "stay fp32 either
  way" in the engine's packing; only pos/vel are halved. If the sampler wants
  fp16 grid quantization to halve the multi-MB grid channels, it is a *new*
  quantization decision (not an engine capability), with precision side-effects
  on terrain thresholds — measured, not assumed.
- **Q6 — Determinism across backends.** The engine's bit-identical-contract
  discipline (see the two-fluid shader's determinism fix and the "bit-identical
  battery" language) suggests CPU and OpenCL backends should match to a defined
  tolerance for a reproducible demo; the parity standard for the JVM port is
  unwritten.

### Feasibility verdict

- **The async spine is very feasible.** It is not even a new pattern — it is the
  engine's own verified decoupling (worker thread + own device, publish-on-
  cadence, immutable latest-wins handoff) rehosted behind a fresh boundary. The
  server tick reads a publish and never waits; the domain never names a
  Minecraft class. That boundary is expressible in the type system and
  therefore cheap to preserve.
- **The sampler and byte-accurate publish are feasible and low-risk.** The
  cadence model, fp16 packing, stale-generation dropping, and both fidelity
  loops already exist in the engine API; the JVM port carries them over rather
  than inventing them.
- **The long tail is the same as volumetric-terrain:** coupling the *coarse
  1 m gameplay grid* (collision, redstone, inventory) to the field is the hard,
  mostly-design work. But it is downstream of this document — this seam makes
  it possible at all, and it can be built and demoed (Phase 1: living terrain +
  a readability field) without touching that tail.
- **The OpenCL path is feasible** and is the reason the CPU-first Phase 1 is
  worth doing as an adapter: it keeps the publish contract stable while the
  backend swaps underneath.

Overall: **feasible now for Phase 1; the architecture is the deliverable and it
is sound.** The binding risks are the world↔field scale mapping (Q1), the
readback memory strategy (Q2), and the field↔gameplay-grid coupling downstream
— all of them separate designs that this seam unblocks, none of them
contradictions of the async model.
- [`the-between.md`](./the-between.md) — **the un-windowed medium.** §1–§2 there reads
  the field domain + publish (the between the un-windowed medium of); §7 Q1 the
  movable window (the between's placement is window-relative, never a map).
  Reverse pointer: the between is the field's un-windowed medium.
- [`the-midwife.md`](./the-midwife.md) — **the sampler's first tick** §1–§2 the field domain + publish (the first read samples the publish on the first tick). Reverse pointer: the midwife’s first read is the domain’s first bounded sample.
- [`the-crossroads.md`](./the-crossroads.md) — **the fork’s domain.** the async order-band the meeting’s legs compose. Reverse pointer: a crossroads is the async domain’s built fork — a legible meeting of maintained ways.
- [`the-incantation.md`](./the-incantation.md) — **the ordered perturbation.** the async order-band the utterance rides. Reverse pointer: an incantation is an ordered perturbation in the async domain — phase-matched, fully legible.
- [`world-difficulty.md`](./world-difficulty.md) — **the scaled domain.** the async order-band a harsh world’s extremes ride. Reverse pointer: world-difficulty scales the async domain’s extremes.
