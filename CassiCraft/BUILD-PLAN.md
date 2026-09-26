# CassiCraft Build Plan

The concrete, buildable implementation plan for the CassiCraft mod. This is the
bridge between the settled design corpus (`designs/`, 198 docs — **read-only,
never re-designed here**) and a running Minecraft mod. Everything below composes
the corpus's architecture seams, ports the physics engine's real API, and is
grounded in the current (2026) Minecraft modding landscape with every version
claim checked against a vendor page. Any number I could not verify is flagged
`[assumption]`.

The architecture is _not_ up for debate. It is the four-module seam of
[`async-field-domain.md`](./designs/async-field-domain.md), the 64³ / 192³ box and
tick budget of [`chunk-field-quantization.md`](./designs/chunk-field-quantization.md),
the dual-world grid semantics of [`volumetric-terrain.md`](./designs/volumetric-terrain.md),
and the ten-step build-order of [`corpus-map.md`](./designs/corpus-map.md) §4.
This plan says _how_ to build that, with real toolchain numbers.

---

## 1. Executive summary

**What the mod is.** Minecraft as the observation + interaction surface of a
running Cassi universe. A two-fluid PDE field (the ported `CassiCosmos` engine
core) runs as an **asynchronous JVM worker thread**, publishing immutable field
snapshots on a cadence; the synchronous server tick **samples** the freshest
snapshot and turns it into terrain, entity steering, and — later — every other
corpus mechanic. The world never blocks on the physics; the physics never waits
on the tick. Blocks, mobs, and weather are *epiphenomena* of one law, never
second systems.

**The seam, in one line.** Async field domain *publishes* ≀ tick-sampler
*reads* → intent → world-writer *mutates* (the only mutator). The dependency
direction is enforced by the type system: the domain imports **no** Minecraft
symbol.

**The recommended stack (exact, current as of 2026-08-15):**

| Layer | Choice | Version (checked) | Source |
|---|---|---|---|
| Minecraft | Java Edition **26.2** (current release; 26.3 incoming Q3 2026) | 26.1 (Mar 24 2026), 26.2 (Jun 16 2026), 26.3 (snapshots) | minecraft.wiki Java Edition 26.1/26.2/26.3 |
| Mod loader | **Fabric** (Fabric Loader + Fabric API) | Loader ≥ 0.18.4, Fabric API for 26.x | fabricmc.net 26.1 post; docs.fabricmc.net 26.2 |
| Build tool | **Fabric Loom** (`net.fabricmc.fabric-loom`), **Gradle 9.4.0** | Loom 1.15+ (26.1+ non-obfuscated), Gradle 9.4.0 | fabricmc.net 26.1 post; docs.fabricmc.net/develop/loom |
| Java | **25** (toolchain `JavaLanguageVersion.of(25)`) | Java 25 minimum for 26.1+ | fabricmc.net 26.1 post; neoforged.net 26.1 release |
| Mappings | **Mojang official** (26.1 is the first unobfuscated release; no remap, no Yarn) | official names now shipped | fabricmc.net 26.1 post |

**Why Java Edition 26.2 + Fabric, and why this is a lucky moment.** 26.1 is
Mojang's first **unobfuscated** Minecraft release (`fabricmc.net/2026/03/14/261.html`).
The entire remapping layer — Loom remap, Yarn, `modImplementation` — is gone.
A mod's `build.gradle` now uses `implementation` / `jar`, exactly like a normal
Java project, and every symbol is named with Mojang's own names. This is the
largest toolchain simplification since Forge, and it materially de-risks the
engine port (section 3) because there is no obfuscation transform to fight.
Fabric is the cleanest host for the plan's needs: a lightweight API with events
for server tick / block / dimension (section 5, 7), first-class background
threading support, and a modular API that stays out of the way of a custom
compute thread. NeoForge (MDG 2.0.141 / Gradle 9.1+) is a fully viable runner-up
with the same Java 25 / unobfuscated world — the recommendation is Fabric for
its smaller surface and server-friendly API, not because NeoForge is broken.

**The Phase-1 milestone (Step 1).** The **living-terrain demo**: a running
64³ two-fluid field over a **192³ m / 12×12×12-chunk** player-anchored box whose
iso-surfaces *become* the world's blocks. Condense (`ρ ≥ τ_c` → solid) and heal
(mining perturbs local ρ/ε² and the medium reorganizes) inside the ≈ 1–6 ms/tick
sample budget. The field *is* the terrain; the demo proves the seam end to end.

---

## 2. Project structure

### 2.1 Decision: one mod jar, internal packages — not a multi-module Gradle build

**Recommendation: a single Fabric mod jar with strictly-enforced internal
packages, no Gradle subprojects.** Reasons:

- **The four-module seam is a compile-time boundary, not a runtime/jvm boundary.**
  The corpus's dependency rule ("the domain imports NO Minecraft symbol") is
  *inexpressible in the wrong order* only if the module boundaries are visible
  to the compiler. That is exactly what Gradle's `sourceSets` give you without
  the complexity of subprojects: split `main` (the Minecraft-free domain) from
  a `domain` package that has no `net.minecraft` on its classpath.
- **Loom multi-project is workable but not free.** The Loom docs explicitly
  warn that multi-project needs `namedElements` configurations and split
  source-set wiring (`docs.fabricmc.net/develop/loom`, §"Depending on
  Subprojects"). For one mod shipping one jar, that overhead buys nothing we
  need — a Gradle build is invisible to Minecraft by design; only the jar and
  the `fabric.mod.json` matter.
- **The OpenCL upgrade path stays intact.** `async-field-domain.md` §6 models
  the CPU solver as an *adapter* behind the same publish contract as the future
  OpenCL backend. That is a factory-selected `implements` boundary inside one
  module — it does not need a separate Gradle project, and the `domain` package
  never sees the backend concrete type.
- **A Fabric `include` dependency covers the real third-party need.** Only
  `lwjgl-opencl` + natives (for the future GPU backend) and a JVector/JOML
  dependency need bundling; Loom's `include` configuration does that.

The **dependency direction is enforced** by two mechanisms, not discipline:
(a) the `domain` source set compiles without `minecraft` on its classpath, and
(b) the domain's public API exposes only a plain-Java `FieldSnapshot` record
and `FieldJob` — no Minecraft type can cross it.

### 2.2 Directory tree

```
CassiCraft/                      # the mod repo root (this file, README, designs/)
├── build.gradle                 # Loom 1.15, Gradle 9.4.0, Java 25
├── gradle.properties            # minecraft_version=26.2, fabric versions, mod id
├── settings.gradle
├── src/main/java/dev/cassicraft/
│   ├── CassiCraft.java          # ModInitializer/entrypoint — only startup wiring
│   ├── client/                  # client-side only (BERs, later field render)
│   │   └── FieldVisualizerClient.java   # BlockEntityRenderer / deferred (sec 6)
│   ├── domain/                  # ══ MODULE 1: FIELD DOMAIN — NO Minecraft imports ══
│   │   ├── engine/              # the ported engine core (sec 3)
│   │   │   ├── TwoFluidSolver.java      # passA/passB leapfrog (cassi_two_fluid.glsl)
│   │   │   ├── SpectralPoisson.java     # fused Stockham FFT (cassi_poisson.glsl)
│   │   │   ├── GradientPass.java        # ∇(g·Φ) _grad_buf (cassi_nbody_gravity.glsl)
│   │   │   ├── RiverForce.java          # a = −G_N·(π/ρ)·∇(g·Φ) (chord_g_from)
│   │   │   ├── EngineJob.java           # {executed, step_count, t, window_center}
│   │   │   └── EngineBackend.java       # adapter iface (CPU today, OpenCL later)
│   │   ├── snapshot/            # the publish wire format (sec 4)
│   │   │   ├── FieldSnapshot.java       # immutable record, ≈ 6 MiB
│   │   │   ├── SnapshotPublisher.java   # latest-wins handoff (the seam)
│   │   │   └── MeshlessSites.java       # 8192 sites → chunk-activity map
│   │   └── thread/
│   │       ├── CassiFieldThread.java    # owns solver + poll loop (sec 3.3)
│   │       └── KernelLoader.java        # main-thread kernel/resource load
│   ├── game/                    # ══ MODULES 2+3: TICK-SAMPLER + WORLD-WRITER ══
│   │   ├── sampler/             # reads freshest snapshot → intent
│   │   │   ├── TickSampler.java         # server-tick entry (sec 5)
│   │   │   ├── Quantizer.java           # chunk↔field quantization, 1 m blocks
│   │   │   ├── EntitySteerer.java       # river-law intent per entity
│   │   │   └── ActivityScheduler.java   # meshless sites → active chunks
│   │   └── writer/              # ══ MODULE 4: THE ONLY MUTATOR ══
│   │       ├── WorldWriter.java         # applies intent to ServerLevel
│   │       ├── BlockQuanta.java         # hysteresis threshold quantization
│   │       └── DirtyChunkIntents.java   # re-quantization scheduler (sec 5.3)
│   ├── block/                   # BlockEntity + BlockState (phase 2 custom blocks)
│   │   └── CassiBlockEntity.java
│   └── mixin/                   # mixin classes (sec 7) — thin, event-backed
│       └── ServerLevelBlockEventMixin.java
├── src/main/resources/
│   ├── fabric.mod.json          # mod id, entrypoints, depends: fabric-api
│   └── cassicraft.accesswidener   # only if a mixin needs a private field
└── src/main/java/domain/        # if split sourceSet: pure-Java domain <-> no MC
```

**The one wrinkle worth calling out:** in Loom's modern layout the `domain`
package lives under `src/main` but is kept Minecraft-free by *discipline plus a
shadow-sourceSet*. The simplest enforceable split is a dedicated Gradle
`sourceSet` (e.g. `src/domain`) whose compile classpath omits `minecraft`; the
Loom doc's `clientImplementation` split-source-set machinery shows the pattern.
If that proves noisy, the fallback is a single `domain` package reviewed by a
grep gate (`git grep 'net.minecraft' src/main/java/.../domain` in CI). Either
way the rule is absolute: **a `domain` class may not reference a Minecraft
type.**

---

## 3. The engine port

### 3.1 What the engine actually is (read, not re-derived)

The source of truth is `CassiCosmos/scripts/cassi_physics_engine.gd` (2720
lines) and `CassiCosmos/compute/*.glsl`. The key port facts, named from the real
file:

- **The two-fluid PDE** (`compute/cassi_two_fluid.glsl`): a 3D finite-difference
  leapfrog. Two passes per step — `pass_a()` (read `ey/ei/vel/rho`, compute new
  field into a non-aliasing `scr` double-buffer) and `pass_b()` (copy `scr` →
  canonical `ey/ei/q/vel`). Equations verbatim:
  `∂²EY/∂t² = c²·∇²EY − ω₀²·(EY−φ·EI)`, `∂²EI/∂t² = c²·∇²EI + ω₀²·(EY−φ·EI)`.
  The Laplacian is the **19-point anisotropic stencil** (`lap_ey_at` /
  `lap_ei_at`) with per-axis weights from `h_i = 2·extent_i/N`, `h₀ =
  2·min(extent)/N` — deterministic, fp32-exact at unit aspect. `pass_b`
  recomputes `q = EY²+EI²` and `ε² = (EY−φ·EI)²` into `vel[].w`.
- **The spectral Poisson** (`compute/cassi_poisson.glsl`): `∇²Φ = ρ_mass`,
  `Φ̂ = −ρ̂/k²`, `k=0` nulled. A hand-rolled **fused Stockham** complex FFT,
  6 dispatches per solve (`clear → load+x → fft(y) → fft(z) → [kspace+inv-z] →
  ifft(y) → ifft(x)`), the real part of the buffer holds Φ afterward.
- **The gradient pass** (`compute/cassi_nbody_gravity.glsl`): builds the
  cell-centered `∇(g·Φ)` into the `_grad_buf` (vec4/cell, `.xyz` = gradient,
  `.w` = 0 — a 4 MiB allocation of which only 3 MiB is useful: the vec3 publish
  trim). Second-order central differences by default (`gradient_order = 2`).
- **The river law** (`cassi_nbody_gravity.glsl:520-532`): `river_field_acc_smp`
  returns `a = −G_N·(π/ρ)·∇(g·Φ)`, where `π/ρ` comes from `chord_g_from()`
  clamped to `[0, 0.72]` with a `ρ < 1e-6` guard.
- **The config** (engine `config` var block): `grid_N = 64`, `dt = 0.001`
  default but the **CassiCraft owner config pins `dt = 0.05`** (one field step
  per tick), `cluster_radius = 60` / `box_aspect = (1,1,1)` for the 192³ m
  Phase-1 box (see `chunk-field-quantization.md` §1.2), `ω₀² = 20.0`,
  `φ⁶ = 17.94427191`, `φ⁻² = 0.3819660112501051`, `qi_condensation_threshold =
  0.5`, the `π/ρ` clamp `0.72`, `τ_c = 0.5`, `q ≈ 0.947`.
- **The meshless arm** (8192 sites, `ML_N1 = 16`, `ML_REBUILD = 25`, `ML_LLOYD_P =
  4`) — the phase-1 **activity scheduler**, not a physics need. Phase 1 drops
  the 2.5M-particle nbody arm entirely.

### 3.2 What to port first (this is the ordering)

1. **`TwoFluidSolver`** — the `pass_a`/`pass_b` leapfrog + 19-point stencil on a
   flat `float[]` grid. This is the heart; it is O(N³) and pure arithmetic, a
   mechanical port. Must reproduce `q` and `ε²` exactly.
2. **`SpectralPoisson`** — the fused Stockham FFT (radix-2, N = 64). The
   JVector library (`net.jvectors:jvector`) provides a vectorized FFT path; or
   keep the hand-rolled Stockham for bit-fidelity. This is the one piece where
   "rehost the shader" is real work, because FFT code is delicate — see port
   drift risk (section 8).
3. **`GradientPass`** — the second-order central-difference `∇(g·Φ)` into the
   trim buffer (3 MiB).
4. **`RiverForce`** — `chord_g_from` + `a = −G_N·(π/ρ)·∇(g·Φ)` for the
   entity/mob/item steer (step 4 of the build order).
5. **`MeshlessSites` + `ActivityScheduler`** — the 8192-site JFA/Lloyd rebuild
   every 25 steps → the active-chunk bitmap (the load map). Phase 1 can start
   with a simpler radial-hotness fallback and add the sites once the seam is
   steady.

**Do NOT port** in Phase 1: the 2.5M-particle nbody arm, `mass_deposit` /
`particle_merge`, the BH accretion chain, the tree-gravity mode-5 seam, OR the
GLSL rendering shaders. `chunk-field-quantization.md` §4.1 is explicit: keep
the two-fluid PDE, the Poisson, the gradient pass, and the meshless sites; drop
the particle readback. The field-only mode targets ≈ 0.5–1.5 ms/step.

### 3.3 The threading contract ported to the JVM

The engine's threading header is the model we keep (`cassi_physics_engine.gd`
header + `start_threaded` / `stop_threaded` / `shutdown`). Ported to the JVM:

| Engine (GDScript) | JVM port | Contract |
|---|---|---|
| `create_local_rendering_device()` **on the worker** | the worker thread **owns** the `CassiFieldThread` + solver + buffers | a compute device/solver is created on the thread that uses it |
| SPIR-V pre-loaded on **main thread**, passed via `cfg.spirv` | `KernelLoader` loads/compiles kernels **on the main thread**, hands ready kernels/sources to the worker in its startup config | resource loading is not thread-safe; the worker never opens sources itself |
| `start_threaded(cfg)` | `CassiFieldThread.start(cfg)` | worker spawned once at world load |
| `stop_threaded()` joins; exit path runs `shutdown()` | `CassiFieldThread.close()` — explicit, joins the worker, `close()` on the worker | **never** a finalizer/GC hook |
| `shutdown()` (never `free()`, which the host shadows) | explicit `close()` | the corpus's name for it; keep `shutdown` off the GC path |
| `_res_mutex` / `poll()` / `_consume_latest()` latest-wins | `SnapshotPublisher` with a simple volatile latest-reference + monotonic generation | the immutable handoff (section 4) |
| per-job step budget `JOB_STEP_CAP = 64`, `snapshot_cadence = 2` | the worker drains a bounded run of steps per job, publishes on cadence | a coalesced backlog drains in bounded slices, never a monster chain |

**One honest, named divergence.** The corpus's `async-field-domain.md` (§2, §5)
cites the engine's *older* job-loop API — `submit_steps(target, block=)`,
`poll()`, `_consume_latest()`, `_res_gen` / `_consumed_gen`, the mutex handoff —
as "the source of truth." The **current** `cassi_physics_engine.gd` (2026-08-15)
has migrated to a **one-RD decoupled mode** (the `M0b-P` comments): the worker's
job loop is *gone* ("died in M0b-P"), and `start_threaded` now only does the
CPU-side setup on the worker while the render thread records chains directly.
**The JVM mod must therefore re-create the job-loop / publish / latest-wins
machinery the corpus describes** — it is *not* in the current engine file. This
is not a contradiction of the architecture (the corpus needs that seam regardless
of how the Godot host drives the engine); it is exactly the port-drift risk
section 8 names, and the plan's `SnapshotPublisher` / `EngineJob` classes are
where that machinery lives on the JVM side.

---

## 4. The publish wire format

### 4.1 The payload (byte-accurate to the corpus, sized ≈ 6 MiB)

An immutable `FieldSnapshot` record, populated by the worker off to the side in
full, then handed off atomically. From `chunk-field-quantization.md` §2 (canonical
≈ 6 MiB):

| Channel | Size @64³ | Type | Source (engine) | Drives |
|---|---|---|---|---|
| `q` | 1 MiB | `float[]` 262,144 | `field_q` (pass_b) | ore precipitation, spawn gates |
| `pot` (Φ) | 1 MiB | `float[]` 262,144 | `_fft_buf` real part | ∇(g·Φ) source, item gravity |
| `grad` ∇(g·Φ) | 3 MiB | `float[][3]` vec3 trim | `_grad_buf` `.xyz` | entity/mob/item steering |
| `rho` (ρ) | 1 MiB | `float[]` | `EY+EI` (single channel) | condensation threshold, ε² |
| **total** | **≈ 6 MiB** | | | |

Plus the sparse non-grid records: `MeshlessSites` (8192 × ~10 floats ≈ 328 KB,
halved under fp16) and a small `bodies` list (condensed objects, sparse at
Phase-1 scale). The ε² channel **rides in the ρ read** (single float per cell),
per the corpus's canonical form. The gradient is published as the **vec3 trim**
(3 MiB, lossless) — the vec4/EY+EI-separate variants (7/8 MiB) are noted but not
Phase-1 targets.

The steady-state record also carries the engine job meta: `{executed,
step_count, t, window_center, generation}` so the sampler knows the domain is
alive and how far it has advanced — the corpus's "tick-only publish."

### 4.2 Cadence and the sampler's read contract

- **Publish cadence = every Kth job** (corpus's `snapshot_cadence = 2` default;
  with `dt = 0.05` and one step per Minecraft tick, a full snapshot every
  2 ticks → ~10 Hz, comfortably inside the 20 Hz sampling need). Light
  `{executed, step_count, t}` updates every job so the sampler always sees liveness.
- **Immutable, latest-wins.** The worker builds a *fresh* snapshot each publish;
  it never mutates a published buffer. Under a tiny lock (or a volatile write of
  the full reference — arrays are final inside an immutable record, so a single
  `volatile` reference handoff is sufficient and correct), it stores
  `latestSnapshot` with a monotonic `generation`.
- **The sampler reads with no lock held** (it owns the reference), and observes
  **only the freshest unconsumed** generation — it drops stale ones
  (`_consumed_gen` semantics). **The read never blocks**: `SnapshotPublisher.freshest()`
  is a volatile load. This is the corpus §5.1 immutable-snapshot handoff, and the
  *only* cross-thread data structure in the entire mod.
- **Memory churn (corpus Q2).** A 6 MiB alloc per publish on the worker is fine;
  the server thread *reads* it, it does not copy. Pooled/double-buffered handoff
  is the implementation note the corpus records (`async-field-domain.md` §7 Q2) —
  Phase 1 starts with fresh allocs per publish and measures GC pressure before
  optimizing.

---

## 5. Tick integration

### 5.1 Where the tick-sampler hooks

The sampler runs on the **server thread at 20 Hz**. Fabric's `ServerLifecycleEvents`
and the per-tick `ServerTickEvents.SERVER_END_SERVER_TICK` (or the START variant)
are the hook — the plan registers the sampler there, no mixin required for the
tick itself (Fabric API covers it; see section 7). The sampler:

1. Pulls `SnapshotPublisher.freshest()` (volatile, never blocks).
2. Runs the quantizer (Nth-tick cadence) and entity steerer (every tick) —
   see §5.3.
3. Emits *intent* (a small ordered list of "mutations to attempt") into a queue.
4. The **world-writer** — the only module that sees a `ServerLevel` and the only
   mutator — applies that intent via normal `Level.setBlock` /
   entity position/velocity calls through the vanilla server machinery.

### 5.2 The per-tick budget table (against the 50 ms tick)

From `chunk-field-quantization.md` §4.2, all on the synchronous tick and all
memory-bound reads + trivial per-element math:

| Stage | Cost estimate | Grounding |
|---|---|---|
| Snapshot acquire (≈ 6 MiB) | ≈ 0.3–0.4 ms | memory-bound, ~20 GB/s realistic core bandwidth |
| Meshless sites → active-chunk map | ≈ 50 µs (8192 sites) | 8192 sites into a 1728-chunk bitmap |
| Block re-quantization (active/dirty only) | ≈ 0.5–5 ms | §5.3; bounded by scheduler, never the full volume |
| Per-entity trilinear (river law) | ≈ 40 ns × N | 8-corner read + mix, same as the GPU sampler |
| Mob spawn / item-gravity re-use | ≈ 0 | rides the entity-sample path |
| **Total per tick** | **≈ 1–6 ms** | vs 50 ms → ≈ 12% used, **≈ 44 ms (88%) free** |

**Cut-first under pressure:** drop re-quantization cadence (re-quant every Nth
tick) before anything else — the field moves slower than the tick. Second:
drop the per-entity river sample to every other tick.

### 5.3 World ↔ field quantization and the only-mutator rule

- **Box:** player-anchored, **192³ m = 12×12×12 chunks**, `grid_N = 64` →
  **3 m whole cells**, the grid advecting with the player via the engine's
  `window_center` ship-per-job mechanism (`async-field-domain.md` §7 Q1,
  `chunk-field-quantization.md` §1.2). A **1 m Cassi block is a 1/3 trilinear
  sub-cell sample** of the field (`block_center` world → `gc = ((pos −
  window_center)·inv_extent)·(N/2) + N/2`, 8-corner weighted mix — the exact
  fused traversal the GPU sampler uses, `cassi_nbody_gravity.glsl:268-301`).
- **Block state = quantization with hysteresis.** `ρ ≥ τ_c = 0.5` → solid,
  `ρ < τ_c − δ` → air, so a jittering field never flickers a block every tick.
  ε² above a tuneable floor → dissolution (carved/scarred). `q` above a second
  threshold → ore (a scalar channel, not a worldgen height range).
- **Mining is a perturbation, not a deletion.** Destroying a block lowers local
  ρ / raises local ε² via the **Q4 write-back channel** — the sampler collects
  the edit and passes it back as a job input (mirroring the engine's job-dict
  carrying `window_center` / home-window meta), never by the worker reading game
  state (`async-field-domain.md` §5.2). Phase 1: players perturb, not delete.
- **Deterministic, single writer.** Quantization runs on the server tick,
  samples the last published snapshot, and the *world-writer* is the only thing
  that mutates `ServerLevel`. The stale/immutable contract (§4) is what makes
  this race-free: both the gameplay grid and (later) the render layer sample the
  **same** snapshot, so they cannot drift within it.

---

## 6. Rendering precedent — Phase-1 client scope vs deferred

**Realistic Phase-1 client scope: none of the volumetric render.** The dual-world
design (`volumetric-terrain.md`) always keeps a coarse 1 m gameplay grid for
collision/inventory/redstone; Phase 1 renders that as ordinary Minecraft blocks
(solid where ρ ≥ threshold), so the living terrain is *visible and playable* with
zero custom rendering. The full iso-surface volumetric layer is downstream.

**The eventual path, and why it is deferred but not risky:**

| Future client need | Mechanism (checked) | Precedent / source |
|---|---|---|
| Dynamic block-shape rendering | **BlockEntityRenderer** (submit/render system, `BlockEntityRenderState` + `submit`) | docs.fabricmc.net/develop/blocks/block-entity-renderer (26.2); NeoForge BER doc |
| Field/iso-surface visualization | custom shaders; the corpus's `cassi_field_render.glsl` + volumetric shader are read-only reference for a client `ShaderProgram` | corpus volumetric-terrain.md (Marching Cubes / Dual Contouring) |
| Far LOD / voxel density | chunk meshing scheduler + (later) SVO | Distant Horizons is the mature precedent for LOD voxel meshing |
| GPU compute for the field | **OpenCL** (`lwjgl-opencl` bundled via `include`), swapping the CPU solver behind the same publish contract | async-field-domain.md §6; an OpenCL adapter is the plan's extension point |

**The 26.1/26.2 rendering pivot matters here.** 26.1 is the last Minecraft
expected to support OpenGL; 26.2 snapshots add a switchable OpenGL/**Vulkan**
backend, and OpenGL is slated for removal once Vulkan is stable
(`fabricmc.net/2026/03/14/261.html`). The plan therefore keeps the client render
generic (Blaze3D / `BlockEntityRenderer`, which abstracts the backend) and treats
GPU physics acceleration as a *separate OpenCL path that does not touch the
renderer*. The 64³ CPU solver is the Phase-1 deliverable; nothing in the render
deferral blocks the demo.

---

## 7. Mixins vs API — which hooks the plan needs

Fabric's own docs state the principle: "The use of events often substitutes the
use of mixins" (`docs.fabricmc.net/develop/events`). The plan minimizes mixins
— they are the highest-maintenance hooks under Minecraft's rising update cadence
(26.1, 26.2, 26.3+ in one year). The hook map:

| Need | Fabric API hook (checked) | Mixin needed? |
|---|---|---|
| Server tick (sampler, 20 Hz) | `ServerTickEvents.SERVER_END_SERVER_TICK` / START | **No** |
| Client tick (deferred visualizer) | `ClientTickEvents` | No |
| Dimension attributes (biome/cloud tweaks, later) | `DimensionEvents.MODIFY_ATTRIBUTES` (new in 26.1) | No |
| World load/unload (start/stop field thread) | `ServerLifecycleEvents` (world load/unload, server started/stopping) | No |
| Block use / interaction (Weatherglass, tools) | `BlockEvents.USE_ITEM_ON` / `USE_WITHOUT_ITEM`, `ItemEvents.USE_ON` / `USE` (new 26.1) | No |
| Block/creative-tab registration | `BlockColorRegistry`, `RegistryEntry` pattern | No |
| **Block *blowing-up* / mining perturbation write-back** | no direct event for the Q4 feedback channel | **Likely — thin mixin** on `ServerLevel`/block-break |
| **Player-edit → field write-back** (mining perturbs ρ/ε²) | `BeforeBlockBreakCallback` (Fabric API) or a thin mixin | Optional (API likely covers) |
| Deep world-gen override (both-grid coupling) | Dimension/worldgen via datagen + dimension events | Possibly a mixin for the block-state *reader* if hooks fall short |

**The honest guidance:** every Phase-1 hook in the build-order map (server tick,
block use, world load, dimension attributes) is covered by Fabric API events —
the plan can ship Step 1–10 with **at most one or two thin mixins** (the
block-edit/Q4 write-back seam, and possibly the field-driven entity-steer hook
if `ServerLivingEntityEvents` is insufficient). Where a mixin is unavoidable it
is a single small `@Mixin` dispatching into a callback/event — the Fabric docs'
own sheep-shear pattern — so the mixin stays to a handful of lines and is a
contained port target under 26.x version churn. **The custom compute thread is
fully on plan-owned code (no mixin):** `CassiFieldThread` never touches a
forbidden MC class.

---

## 8. The ten-step build order as milestones

Each milestone maps §4 of `corpus-map.md` to the exact docs it composes, the
seam it exercises, and the determinism gate it must clear. **Steps 1–4 are in
the Phase-1 demo** (read-only consumers of the ≈ 6 MiB publish); Step 5 is the
first bounded Q4 write; steps 7–10 extend the same seam. Steps 6, 8, 10 add
strangers/weather/hazard — each still reads, none needs a new engine term.

| # | Milestone | Docs composed | Seam / channels | Phase-1 demo | Determinism gate |
|---|---|---|---|---|---|
| 1 | **The living-terrain demo** | `volumetric-terrain`, `chunk-field-quantization`, `material-regimes` | publish → quantizer → writer | **Yes** | Same field state → same block iso-surfaces, every run (bit-identical q/pot/ρ after N steps from a fixed seed) |
| 2 | **The reader + Weatherglass** | `coherence-magic` §2 (Sense), `field-instruments` §1.4 | sampler reads q/ε²/φ⁻²/ξ | **Yes** | Instrument reads only published channels; same snapshot → same readout |
| 3 | **The Life-Signal read** | `life-signal` §3/§6 | ε²-gradient sign + cadence | **Yes** | Classifier output is a pure function of the snapshot |
| 4 | **The first walk + carry + climb costs** | `the-walk`, `the-carry`, `the-climb` | `a = −G_N·(π/ρ)·∇(g·Φ)`, ~40 ns/entity | **Yes** | Entity steering intent is deterministic per snapshot |
| 5 | **The first practice (stilling / shout)** | `the-stilling` / `the-shout` | Q4 write-back (`{op, worldPos, rung, magnitude, sustain}`) | Phase-1.5 | A Q4 write lands as a bounded, ordered op; replay is identical |
| 6 | **The first stranger read** | `signature-predator` §8, `the-moth` §5b | `R = ρ_signature·τ·M_stability` | gated | Stranger pattern is read, never faced blind; deterministic per snapshot |
| 7 | **The first record** | `schema-that-settles`, `shared-ledger`, `the-archivist` | Q4 op-stream, 44 ms unused tick | gated | Every op books on the settled record; ledger hash converges |
| 8 | **The first weather** | `the-rain` or `the-wind` | `FieldVel`, c_s = h₀/dt | gated | Weather is the envelope read, not a second system |
| 9 | **The first settlement room** | `house-that-steers`, `the-observatory`, `the-shrine` | 192³ box, ξ, q≈0.947 | gated | A held structure's coherence is a deterministic read |
| 10 | **The thin-regime read** | `the-desert` §slice | thin-trough threshold | gated | Hazard layer begins legibly, before the storm |

**The sequencing principle restated:** pure consumers first, Q4 writes second,
mechanics inherit their sources' gates (`corpus-map.md` §4). Nothing in steps
1–10 needs the persistent-Π frontier, per-entity `M` publication, or the
Phase-1.5 material constants — those are the LATER stack, unsequenced here.

**The wage lands quietly inside step 7** (a bounded consumer + Q4 write, same
op-record) and the shaft/incantation ride steps 4/5 — both documented in the
corpus's sequencing note.

---

## 9. Risks & gates

The honest risks, in order of severity, each with its gate:

### 9.1 Port drift from the engine (the live risk)

The current `cassi_physics_engine.gd` no longer contains the job-loop /
publish / latest-wins machinery the corpus's seam describes — the `M0b-P`
one-RD migration removed it (section 3.3). **Gate:** a frozen-port contract —
the JVM `Domain` re-creates the corpus's publish/resume/mutex machinery from
the corpus docs (not from the engine's current one-RD state), and the `domain`
module pins to the *corpus's* canonical numbers (`dt=0.05`, 64³, `τ_c=0.5`,
`q≈0.947`). A parity harness replays N steps from a fixed seed and asserts the
`q/pot/ρ/∇(g·Φ)` outputs match the engine's published reference within the
corpus's determinism tolerance (`async-field-domain.md` §7 Q6 — the CPU ↔ GPU
parity standard is unwritten, so this is a Phase-1 measurement, flagged
`[assumption]` until pinned).

### 9.2 Tick-budget breach

The single bound that breaks Phase 1 is a **full-volume re-quant** (7.08M-block
volume → ~210 ms ≈ 5× the tick; `chunk-field-quantization.md` §4.3). **Gate:**
the meshless-site LOD scheduler (or a radial-hotness fallback) means only
**active/dirty** chunks re-quantize (5–50 hot chunks ≈ 0.6–6 ms), never the full
12³-chunk box. CI asserts per-tick measured sample cost stays ≤ 8 ms with the
cut-first cadence path wired before load.

### 9.3 Thread safety of the publish handoff

The *only* cross-thread structure is `SnapshotPublisher`. **Gate:** the
immutable record + volatile monotonic-generation handoff (section 4.2) is unit-
and stress-tested (a hammer thread publishing while the sampler reads, asserting
no torn snapshot, no stale re-read). The domain thread never holds a `ServerLevel`
— enforced by the source-set compile gate (section 2).

### 9.4 Minecraft version churn

Minecraft now ships 2–3 drops/year (26.1, 26.2, 26.3). **Gate:** the mod pins
**Loom 1.15 + Minecraft 26.2 + Fabric Loader ≥ 0.18.4**, and keeps mixins to a
handful of thin `@Mixin`s dispatching into events — so a version bump is a
small port, not a rewrite. The 26.2 → 26.3 (Q3 2026) jump is expected before
GA; the plan budgets one port pass.

### 9.5 The determinism gate, restated

Every milestone must clear the same bar: **same field state + same channels +
same snapshot → same read, every run.** Concretely, each step ships a
replay/golden assertion — Steps 1–4 hash the published snapshot and the
quantized block states; Step 5 hashes the op stream; steps 6–10 hash their
derived readouts. Nothing is hidden-only; nothing is a roll of the dice
(`corpus-map.md` §1, the through-line).

---

## 10. The recommended next build action

1. Generate the Fabric 26.2 project (Loom 1.15, Java 25, Gradle 9.4.0 via the
   Fabric template generator at `fabricmc.net/develop/template/`) and boot the
   `runServer` / `runClient` to confirm the toolchain.
2. Stand up the `domain` module (source-set gate + `CassiFieldThread` +
   `TwoFluidSolver` + `SpectralPoisson` + `GradientPass` + `RiverForce`) against
   a headless unit harness that replays fixed-seed runs before any Minecraft
   code is written — this is the port-drift control.
3. Wire `SnapshotPublisher` → `TickSampler` → `WorldWriter` on the server tick
   and land **Step 1: the living-terrain demo**.

Every version fact in this plan is grounded in a checked source (Fabric 26.1
announcement, the Loom 26.2 docs, the NeoForge 26.1 release, the Minecraft Wiki
version pages). Numbers the corpus marks as engine-grounded are reproduced
verbatim and cited; the one self-derived CPU-step cost (~0.5–1.5 ms) is flagged
`[assumption]` in the corpus and repeated as such here.
