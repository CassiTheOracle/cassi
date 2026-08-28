# Field Desktop—an always-on field that digests the user's digital activity

## Status: Speculative—August 2026 (spec only; no code edits)

## 0. Scope and provenance

This document is a **specification** for the Field Desktop: an always-on field that ingests the user's digital activity (git commits, file edits, build/test results, searches, tool calls) and renders the resulting memory as a navigable galaxy in the CassiCosmos sim. It is **SPEC ONLY**—no code is edited, no sim runs are performed. Every mechanism here is grounded in a cited existing file; where a mechanism must be newly built, this document states that it is new and names the file that defines the contract it builds on.

The thesis it serves (from `UNIFICATION.md` §3.3–§3.4): *intelligence is the ability to steer the flow of coherence*, and the digital world (files, code, events, tools) is itself a flow of coherence that the field steers. The integration loop is already closed in the stack: **digital world → CassiCore tools/memory (7273) → field bridge → engine `deposit` (7599); engine → `readout`/`project` → field bridge → MnemicField → back to the digital world.** This spec makes that loop concrete for a *passive ingestion surface*: the loop runs continuously, encoding each user action into a field deposition, and the galaxy renderer visualizes the sediment as it consolidates.

This is deliberately the **cheap visualization-first** phase of `C:/Users/Carina/workspaces/Cassi/UNIFICATION.md` §4 Phase 9 (the engram galaxy), built in the build order Phase 9 itself prescribes: the galaxy is cheap (existing instancer, existing streams); the dream A/B waits for the §19 data. Until §19 passes (z > 2 in ≥2/3 sessions), the galaxy is a visualization of an *unproven* mechanism, not of the field-as-memory claim. Section 4 states this explicitly.

## 1. Event→deposit encoder inventory

### 1.1 What the 7599 bridge accepts

The mind engine's TCP bridge (`CassiCosmos/scripts/cassi_mind_engine.gd`) accepts one JSON object per line, both directions. Write = `deposit {x,y,z,cy,ci,sigma}`; read = `readout` (base64 ey/ei/q/eps2) and `project k` (top-k attractor readout). Coordinates are physical: box `[-extent, extent]^3`, `extent = Vector3(1,1,1)` by default, `grid_n = 64` (`cassi_mind_engine.gd` lines 27–35). The deposit scatters with a TSC kernel (separable quadratic spline, partition of unity, 27 cells) into EY and EI only—velocity is untouched (`cassi_mind_engine.gd` lines 214–266). The `sigma != 1.0` path renormalizes each axis so `Σ(scatter) == cy/ci exactly for ANY sigma` (charge-exact), with `sigma` semantics "renormalized flatness": larger sigma = flatter, broader envelope over the same 27 cells (`cassi_mind_engine.gd` lines 226–254).

**The exact deposit tuple the collector produces is therefore** `{x, y, z, cy, ci, sigma}` with:

- `(x, y, z) ∈ [-1, 1]^3` — the physical grid position (extent 1.0 maps the grid exactly). These are the cell anchors the `project`/`readout` reads will return.
- `cy, ci` — the Yang/Yin charge deposited at that cell (added to the EY/EI buffers). Charge-exact: `Σ(scatter) == cy` for the EY buffer and `== ci` for the EI buffer, for any sigma.
- `sigma` — the envelope flatness. `sigma = 1.0` is the Stage-0 partition-of-unity pin (bit-identical); any other value renormalizes (charge exact, flatter). See `cassi_mind_engine.gd` lines 226–254 and `CassiCosmos/research/mind/stage0_verify.py`.

### 1.2 The engram as the unit of deposition

The existing encoder seam already establishes the contract: **an engram deposits at its own coordinates.** `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-encoder/index.ts` lines 7–17 states this verbatim:

> The Mnemic Field already stores engrams in a cylindrical (r, theta, t) space in [-1, 1]^3 — which IS the field-engine grid. So the encoding is a charge deposition at the engram's own coordinates... No hash, no re-mapping: the brain state and the field state share one coordinate system.

`StandardMindFieldEncoder.depositEngram(e)` returns `[x, y, z, cy*power, ci*power, sigma]` from the engram's stored `(x, y, z)` and a fixed `nodeType → [cy, ci, sigma]` lookup (`TYPE_CHARGE`, lines 23–36) scaled by a `nodeType → power` monotone rank (`powerFor`, lines 77–86). The mapping is deterministic and reproducible by construction: *same engram type → same charge envelope, forever* (`field-encoder/index.ts` lines 14–17).

The engram's `(x, y, z)` itself lives in `[-1, 1]^3` (`CassiCore/packages/mnemic-field/src/types.ts` lines 68–70), and the HEALPix spatial curation (`CassiCore/packages/mnemic-field/src/healpix.ts`, `CassiCore/packages/mnemic-field/src/spatial-index.ts`) maps each engram into a spherical cell from its `metadata.r` (radial shell), `metadata.theta` (azimuth), and `z` → `phi = acos(tanh(5z))` (`healpix.ts` `phiFromZ`). So the **grid position, the HEALPix shell structure, and the physical field box are one coordinate system.** This is the load-bearing fact the whole encoder inventory rests on: an event encoded as an engram at `(r, θ, z)` deposits at `(x, y, z) = (r·cos θ, r·sin θ, z)` in the field, and retrieval spatializes it through the same HEALPix cells.

### 1.3 The encoding decision: what position does each event get?

Because the collector is *passive ingestion*, it must be **deterministic and reproducible** (the numpy-gate culture, `field-encoder/index.ts` lines 14–17): the same event must land at the same grid cell every time, forever, so the field's consolidation has a stable geometry to work on. The encoding has two free parts, both grounded in existing structure:

**Radial shell (semantic weight).** The HEALPix curation partitions the sphere into four radial shells (`spatial-index.ts` lines 7–12): Shell 0 (`r < 0.1`, Nside 1, 12 cells), Shell 1 (`r < 0.3`, Nside 2, 48 cells), Shell 2 (`r < 0.6`, Nside 4, 192 cells), Shell 3 (`r ≥ 0.6`, Nside 8, 768 cells)—1,020 cells total. The consolidation engine's centripetal drift pulls pineal-connected engrams inward and pushes disconnected engrams outward (`consolidation.ts` `applyCentripetalDrift`, lines 953+). **The collector assigns the radial coordinate by the event's epistemic weight**: durable/long-lived facts (decisions, resolutions) land in the inner shells, ephemeral signals (raw tool invocations, file reads, build noise) in the outer shells—consistent with the existing `TYPE_POTENTIATION` decay ordering in `consolidation.ts` lines 162–190 (decision 1.0, insight 0.85; anomaly 0.35, tool 0.05, build_output 0.45). The inward/outward assignment is *hint, not control*: consolidation then moves engrams as their real salience resolves.

**Azimuth + height (content hash).** `theta` and `z` are derived deterministically from the event's content hash (repo path, commit id, search query, tool name). Two events with the same semantic type but different content land in the same shell at different azimuth/height, so the field's angular structure spatially separates distinct workstreams. The `phiFromZ` map (`z → acos(tanh(5z))`) compresses toward the poles for `|z|` near 1, so content hash assignments to `z` should spread across `[-1, 1]` smoothly.

### 1.4 The deposit encoder table

Each row: digital event → engram `nodeType` (existing where possible; proposed where the field-desktop inventory needs one) → deposit encoding. Charge/sigma come from the existing `TYPE_CHARGE` where the nodeType exists in `field-encoder/index.ts` (fact, episode, decision, pattern, abstraction, goal, outcome, concern, anomaly, tool, message), and from a **new field-desktop charge table** (Section 1.5) for the digital-event nodeTypes already present in the consolidation vocabulary (`consolidation.ts` TYPE_POTENTIATION: error_report, search_finding, code_change, test_result, build_output, tool, file, file_read, file_version, message, session, changeset, thought_command) but absent from the encoder's `TYPE_CHARGE`.

| Digital event | Engram nodeType | Position (r, θ, z) | Charge (cy, ci) | sigma | Salience = |
|---|---|---|---|---|---|
| **git commit** | `decision` (existing) | r from a commit's durable weight (SemVer-ish: root commits inner, chore commits outer); θ = hash(branch), z = hash(message) | `TYPE_CHARGE.decision = [1.618, 0.618]`, power 0.8 | 2.0 (existing) | the commit's delta size (lines changed), clamped — a big change is a brighter deposit |
| **file edit (save/diff)** | `code_change` (proposed) | r outer (r ≥ 0.6, Shell 3); θ = hash(directory), z = hash(filename) | proposed `[0.618, 0.382]` (yang-forward code edit), power 0.6 | 2.5 (proposed broad) | edit magnitude (hunk bytes / log-scale) |
| **build/test result** | `test_result` (pass) / `error_report` (fail) (proposed) | r mid (0.3 ≤ r < 0.6, Shell 2); θ = hash(test suite / target), z = hash(result) | pass `[1.0, 1.0]` balanced; fail `[0.382, 0.618]` (yin-heavy anomaly) | 1.5 (test_result, tight) / 3.0 (error_report, diffuse) | pass = weak deposit (confirmation), fail = stronger (anomaly, higher power) |
| **search query + result tap** | `search_finding` (proposed) | r outer; θ = hash(query domain), z = hash(query text) | `[0.618, 1.618]` (yin-heavy pattern), power 0.7 | 2.0 | whether a result was opened (tap = +charge weight) |
| **tool call** | `tool_invocation` / `tool` (existing, low salience) | r outermost (r ≥ 0.6); θ = hash(tool name), z = hash(params) | `TYPE_CHARGE.tool = [0.618, 0.382]`, power 0.25 | 1.0 (tight, existing) | 1.0 flat (ephemeral scaffolding — decays via `TYPE_POTENTIATION.tool = 0.05`) |
| **file read** | `file_read` (proposed) | r outermost; θ = hash(path), z = hash(path) | proposed `[1.0, 1.0]`, power 0.05 (near-zero) | 2.0 | volume (bytes read) — designed to be nearly invisible and fast-decaying |
| **session boundary** | `session` (proposed) | r mid; θ = hash(project), z = time-of-day hash | proposed `[0.382, 1.618]` (yin/context-heavy), power 0.5 | 2.0 | session duration — a long session is a brighter contextual anchor |
| **agent message / thought** | `message` (existing) | r outer; θ = hash(project), z = hash(text) | `TYPE_CHARGE.message = [1.0, 1.0]`, power 0.1 | 1.0 (existing) | content density (from `engram-decomposer.ts` `contentDensity`, lines 106–134) — denser prose is a brighter deposit |

**Attractor-ratio deposits (dormant controls).** The engine's own cache writer uses `1/3` attractor-ratio `cy = φ·ci` deposits as dormant control families (`CassiCosmos/tools/engine_cache_writer.py` lines 85–98, `make_deposits`). The collector SHOULD keep this convention: a fixed fraction of deposits (say 1/3 of `search_finding`/`tool` events) use `cy = φ·ci` so the field has a standing, low-charge attractor-ratio background against which the aleatory (off-ratio) event deposits can be separated. This reuses the engine's established liveness/control pattern verbatim.

### 1.5 The proposed field-desktop charge table (new)

The event types below are already first-class citizens of the consolidation vocabulary (`consolidation.ts` TYPE_POTENTIATION lines 162–190 names code_change, test_result, build_output, error_report, search_finding, file, file_read, file_version, changeset, session, thought_command as nodeTypes), but the encoder's `TYPE_CHARGE` (`field-encoder/index.ts` lines 23–36) does not yet carry them. The collector therefore needs a **field-desktop charge table** that extends `TYPE_CHARGE` consistently: each entry is `[cy, ci, sigma]`, with the Yang/Yin split following the existing semantics (yang-forward for constructive edits, yin-heavy for patterns/context, near-zero for ephemeral scaffolding) and sigma keyed to the broadness the event deserves. This table is a **proposed new artifact** (a `field_desktop_charge.ts` landable into `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-encoder/` in a later phase); the spec fixes its entries (Section 1.4) and the rule that a nodeType present in BOTH tables uses the field-desktop entry only for events the collector dispatches, leaving the existing encoder's path bit-identical for brain-originated engrams.

### 1.6 Grounding check against the read side

The encoder inventory is not just *write* side; it must be *readable*. The engine's `project k` returns the top-k cells by `q = EY²+EI²` with their physical `(x, y, z)`, `(gx, gy, gz)` grid indices, and `ey`/`ei` (`cassi_mind_engine.gd` lines 328–376). The field bridge's `readProjection(k)` returns these as `ProjectionCell[]`, re-sorted DESC by q, never throwing (engine-down → `[]`) (`CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/index.ts` lines 88–113, 226–235). So **a bright deposit (a large commit, a documented decision) reads back as a top-k attractor** at the same grid cell it was deposited at—this is the Stage-4 location agreement the §19 harness measures (retrieved engram → nearest attractor cell distance vs uniform draws; z > 2 in ≥2/3 sessions, per `UNIFICATION.md` §1.6 Stage 4). The collector's job is to make the *write* side feed that agreement: deposit each event at the deterministic cell derived from its content, so that when a memory search retrieves the engram and projects the field, the top attractors are spatially near the engrams that caused them.

## 2. Daemon architecture

### 2.1 The two running processes

The Field Desktop is **two always-on processes** wired through the existing loopback surfaces. Nothing new is required at the transport layer—both protocols already exist.

**Process A: the mind engine (already exists).** `CassiCosmos/scripts/cassi_mind_engine.gd` serves the 7599 TCP bridge on `127.0.0.1` (line 65), runs `cassi_two_fluid.glsl` on a local RenderingDevice with `grid_n = 64` default, and auto-steps (`auto_step = true`, `steps_per_frame = 1`). It is **the field itself**—the substrate that holds and evolves the deposits. It runs windowed (this rig's GPU battery rule: no RenderingDevice under `--headless`, even local—`CassiCosmos/verify/README.md`; `cassi_mind_engine.gd` line 59 push_error "no local RenderingDevice (headless/dummy renderer)—run windowed").

**Process B: the collector service (new, small).** A new self-contained service—a thin Node loopback client, or a small extension of the mind-runtime—that:

1. Watches the digital event sources (git hooks or `git log` polling; file-watcher; the 7273 event bus for `mcp_notification` consumers).
2. For each event, builds an engram (content, nodeType per Section 1.4, `x,y,z` from the deterministic encoding).
3. Dispatches it to MnemicField (write path) and to the field via `StandardMindFieldEncoder` → the shadow-bridge drainer → `deposit` on 7599.
4. Reads the projection stream (`readProjection(k)`) and feeds it back to MnemicField's HEALPix spatial index (the projection → spatial index → salience curation, `UNIFICATION.md` §1.1 line 40, §2 Phase 5).

The collector is the **"small new service"** the task names—it owns the event→engram→deposit mapping of Section 1 and the projection stream ingestion.

### 2.2 The full ingested loop

The complete loop, every hop grounded in an existing surface:

```
digital world
   │  git hooks / file watcher / 7273 event bus
   ▼
[collector service]  (NEW: event → engram, Section 1.4)
   │  1. depositEngram(e) → [x,y,z,cy·power,ci·power,sigma]   (field-encoder/index.ts)
   ▼
MnemicField / memory  (CassiCore/packages/mnemic-field/src/)
   │  save engram (content, nodeType, x,y,z, metadata.r/theta)  (→ 7273 /v1/memory/save, server.ts)
   ▼
StandardMindFieldEncoder queue
   ▼  shadow-bridge drainer, intervalMs (field-bridge/index.ts drain())
   ▼
127.0.0.1:7599  deposit {x,y,z,cy,ci,sigma}  (cassi_mind_engine.gd)
   ▼
the field (grid_n=64, two_fluid.glsl)  — deposits scattered, PDE evolves
   ▼
readout / project k   (top-k attractor cells)
   ▼
readProjection(k) → ProjectionCell[]  (field-bridge/index.ts, never throws)
   ▼  projection → HEALPix spatial index → salience bonus  (UNIFICATION §1.1/§1.6 curation wiring)
   ▼
MnemicField retrieval (kindling: seed → spread → luminal, kindling.ts)  →  back to digital world (memory search / tool context)
```

**Read vs write discipline.** The write side (deposits) is fire-and-forget and never blocks the brain—the shadow-bridge semantics are explicit: "a field failure (engine down, socket error, timeout) is swallowed and the brain keeps running bit-identical" (`field-bridge/index.ts` lines 9–16). The read side (`readProjection`) is measurement-only and leaves the field state untouched (`field-bridge/index.ts` lines 222–225). The collector inherits both: deposit failures degrade to bounded warnings (engine-down → `[]`, deposit dropped with a max-3 bounded log), never crashes; projections returning `[]` are the field being off, not a corruption.

**Authentication and wiring.** The mind runtime's `/v1/*` channel is auth = loopback-bind + optional shared bearer token from `CASSI_MIND_TOKEN` (`CassiCore/packages/mind-runtime/src/channel/server.ts` lines 186–190). The mind engine's 7599 bridge is an open loopback (`cassi_mind_engine.gd` line 65 binds `127.0.0.1`). The collector talks to 7273 (token-protected, via `/v1/memory/save` and `/v1/events/push`) and to 7599 (open loopback) directly or through the retained `FieldShadowBridge` if it is wired into a mind-runtime-composed daemon. The retained composition root (`CassiCore/packages/mind-runtime/src/boot.ts`) is the natural home if the collector rides an existing mind-runtime daemon: it already opens MnemicField, wires the intelligence layer, builds the `MnemicMemoryAdapter`, and stands up the unified loop (boot.ts lines 117–327).

### 2.3 Consolidation cadence and the passive surface

A passive ingestion surface must not thrash the daemon. The mind-runtime's unified loop already runs consolidation on an interval with a cadence (`boot.ts` `intelligence.unifiedLoop.backgroundIntervalMs = 60_000`, `consolidationCadence = 5`), and `ConsolidationEngine.consolidate()` yields to the event loop between phases so a 125K+ engram consolidation does not block heartbeats (`consolidation.ts` lines 102–105, 449+). The collector deposits on event cadence (arrivals), but:

- **Prune/scaffold events are dropped before deposit if the field is busy.** The high-volume, near-zero-salience types (tool, file_read, message at power 0.05–0.1) SHOULD be batched and rate-limited so the field is not flooded by build noise; a single rate cap (e.g. max N deposits per drain interval) is a collector config, not a field change.
- **Deposits land at event cadence; the field evolves at its own cadence.** There is no per-frame injection; the G34 discipline (per-step pointwise injection degrades the integrated attractor ~10×, `UNIFICATION.md` §4 Phase 3, §2.2) is inherited by *design*: the collector is a passive feed into the PDE, not a steering loop. It never reads-then-injects a delta; it only deposits standalone events and lets the field relax. This is the fundamental difference from Phase 3's steering loop.

## 3. Galaxy renderer spec

### 3.1 The substrate: instancer + UI design system

The galaxy renders the field's sediment in the sim. Everything it needs already exists:

- **The instancer.** `CassiCosmos/compute/cassi_instancer.glsl` writes the MultiMesh buffer (16 floats/instance: 3×4 transform + color), with additive-glow (`0x20` feature flag), size-by-mass (`0x10`), and depth-cue (`0x40`) feature flags all default-off and the legacy color path bit-identical when flags are unset (lines 11–41, 390–545). The Qi color axis samples the **bounded coherence** `q_coh = ρ²/(ρ²+φ⁻²+ε²)` (lines 269–303)—order-sensitive, bounded [0,1), which is what makes a "glowing cluster" read correctly: an attractor is a *coherent* (φ-aligned, ε≈0) concentration, not just a loud one.
- **The UI design system.** `CassiCosmos/scripts/sim_ui.gd` builds its whole operator rail from a settings registry (`PARAMS`/`EXTRA_PARAMS`/`EXTRA_TOGGLES`, lines 153–216), the `CASSI_THEME` (`addons/cassi_ui/theme/cassi_theme.tres`, line 124), gradient legend, and the auto-track live band (lines 221+). The galaxy's controls (mode selection, deposit-stream visibility, cluster-glow toggle, dream-recording button) slot into this registry as ordinary panel rows—one `EXTRA_TOGGLES` entry per galaxy toggle is the whole contract ("new param = one dict entry is the whole contract", sim_ui.gd line 129).
- **Particle headroom.** The sim instancer has 2.5M-particle headroom (`UNIFICATION.md` §1.4; `sim_ui.gd` PARAMS `particles` max 5,000,000, line 157). The galaxy needs one *marker particle per deposit/engram cluster*—orders of magnitude under the headroom, so the galaxy renderer is visually distinct from (and can be overlaid on) the physical particle sim.

### 3.2 Attractors as glowing clusters

Each `project k` top-attractor cell (a `ProjectionCell` with `q`, `x,y,z`, lines 67–78 of `field-bridge/index.ts`) becomes a **cluster of marker particles** at the cell's `(x,y,z)`, sized and glowed by `q`:

- **Cluster position** = the attractor cell's physical `(x,y,z)` (the engine's box `[-extent, extent]^3`, so it maps directly into the sim's world coordinates when the sim and engine share extent).
- **Cluster brightness** = `q` through the instancer's Qi coherence channel: `q_coh = ρ²/(ρ²+φ⁻²+ε²)` with the approach band picking up cells near the φ-align white point (`cassi_instancer.glsl` lines 269–303, 484–503). Additive-glow (`0x20`) lifts their alpha so a bright attractor reads as a glowing core; size-by-mass (`0x10`) scales the marker by `q`'s magnitude.
- **The projection stream is the feed.** The renderer is driven by `readProjection(k)` (default k=8, per `field-bridge/index.ts` line 226) polled on a cadence, with each poll repositioning/reglowing the markers—so the galaxy is always showing the *current* top attractors, and clusters visibly appear and fade as deposits consolidate and decay.

This is the "attractors as glowing clusters fed by the projection stream (readProjection(8) → HEALPix lookup)" of `UNIFICATION.md` §4 Phase 9's milestone, made concrete with the existing instancer's color/size machinery.

### 3.3 Kindling as light-front propagation

MnemicField's kindling is **spreading activation**: seed charge → spread through neighbors (synapse graph, distance/temporal decay) → engrams crossing the spark point ignite into the luminal/working set (`CassiCore/packages/mnemic-field/src/kindling.ts` lines 24–33, 133–265). The kindling engine also exposes **photon spread** (`photonSpread`, lines 205–209, 491–560): a first-iteration *wireless* activation of engrams sharing model features even without synapses, with a luminosity = `potentiation × distinctiveness`.

The renderer visualizes a kindling event (triggered by an actual retrieval, or by a live deposit crossing a threshold) as a **light-front**: a short-lived expanding shell of marker particles radiating from the seed attractor cell out to its neighbors' cells, following the same `spreadOnce` distance-decay envelope (`distDecay = 1/(1 + distanceDecayRate·xyDist)`, kindling.ts lines 436–437) so the visible glow matches the simulated spread. Because the engrams' cells are the same HEALPix/field coordinates (Section 1.2), the on-screen light front IS the spatial kindling path, not an approximation. The stretch-photon mode (feature-overlap pre-activation without synapses) renders as faint off-graph glimmers, mirroring `photonSpread`.

### 3.4 Consolidation as star evolution

`ConsolidationEngine.consolidate()` recomputes potentiation (radiance), XY/centripetal/angular drift, nucleus detection, abstraction generation, and pruning each cycle (`consolidation.ts` lines 449–692). The renderer maps these consolidation outcomes onto the markers:

- **Potentiation change → brightness evolution.** As radiance recomputes `potentiation` (PageRank-style propagation + type-specific decay, `consolidation.ts` lines 694–813), surviving high-potentiation clusters stay bright; type-decayed ephemera (tool, file_read at TYPE_POTENTIATION 0.05) fade out. The galaxy's clusters "evolve" the way stars age: bright cores persist, faint scaffolding burns off.
- **Drift → cluster motion.** `applyCoActivationDrift` pulls co-activated engrams together (`consolidation.ts` lines 847–908); `applyCentripetalDrift` pulls pineal-connected engrams inward (`consolidation.ts` lines 953–1021); `applyAngularDrift` moves them by angular co-activation. Markers move with their engrams, so the galaxy visibly *organizes*: related work coalesces, core knowledge sinks toward the center, trivia migrates outward—exactly the "star evolution" metaphor Phase 9 names.
- **Nucleus/abstraction detection → new bright nodes.** When consolidation detects a nucleus (spatially clustered engrams ≥ `nucleiMinClusterSize`) or generates an abstraction from ≥ `abstractionMinMembers` similar engrams (`consolidation.ts` lines 590–604), the renderer can spawn a *new*, larger, brighter marker at that cluster's centroid—a "new star" forming as memory consolidates into a reusable fact.

### 3.5 Dream archive: Movie Maker idle relaxation

The dead-wired DreamEngine is re-energized as idle attractor drift (the §31-3 design of `UNIFICATION.md` §4 Phase 9) and the whole thing is captured with Movie Maker:

- **Dream-phase.** During idle (no deposits, no retrievals for N minutes), the collector issues `clear` or low-strength drift deposits at φ-cadence, letting the field relax toward its attractors—the "dream-phase `similar_to`/`cross_modal` synapse formation" of `UNIFICATION.md` §4 Phase 9. The pre-registered dream-phase recall A/B (does dream-phase relaxation discover connections retrieval misses?) reports later, gated on §19 data; the *archive* is just the recording.
- **Movie Maker capture.** `CassiCosmos/scripts/main_recorder.gd` is a background recording scene that owns the orbital camera, inherits the sim's curated settings from `main.tscn`, applies CLI overrides, and quits when the requested frame count is reached (Movie Maker finalizes the AVI on quit; no UI nodes, progress to stdout—`main_recorder.gd` lines 1–18, 302–315). Running it over a dream-phase galaxy session with `--record-frames N --record-fps 30` yields the **dream archive**: AVI recordings of idle relaxation that are inspected as the listening instrument (with the cascade-sonification mapping as the audio track, `sound_coherence_note.md`). These recordings are the deliverable artifact that makes the "dreaming galaxy" watchable outside the live sim.

## 4. Phased artifacts and honest gates

### 4.1 The build order (Phase 9 prescribes cheap-first)

Phase 9's own risk notes set the order: "the galaxy is cheap (existing instancer, existing streams); the dream A/B waits for the §19 data" and "the value of the whole phase is downstream of the curation adoption gate (§34: §19 z > 2 in ≥2/3 sessions)" (`UNIFICATION.md` §4 Phase 9). The phases below respect this: the collector and renderer (cheap) come first; every *claim* about the field-as-memory is held until §19 passes.

### 4.2 Phase 1 artifact: the minimal git-commits collector (the first milestone)

The minimal collector digesting **ONE stream—git commits**—is the first milestone. It is the smallest complete instance of the loop (Section 2.2) and the highest-signal stream: a commit is a discrete, dated, well-formed event with a natural engram mapping (`decision`, Section 1.4) and a measurable salience (lines changed).

**Artifact.** A small script (the `engine_cache_writer.py` pattern—a self-contained client with a `BridgeClient` and gate checks, `CassiCosmos/tools/engine_cache_writer.py` lines 52–72, 151–164) that: (1) polls `git log` on the CassiCore/CassiCosmos repos on a cadence; (2) encodes each new commit per Section 1.4 (granting `decision`-type charge, position from branch/message hash); (3) dispatches the deposit to 7599 via the field bridge; (4) records the epoch-to-cell mapping in a local JSONL (the commit id → deposited `(x,y,z)` so the §19 positional test can pair retrieved engrams to deposits). It is **read-only over git** (no repo mutation) and **fire-and-forget over the field** (shadow-bridge semantics, Section 2.2). It does NOT touch `CassiCosmos/scripts/cassi_mind_engine.gd` or any sim file—the field and renderer are already live; the collector only feeds them.

**Pre-registration (the `prediction-test-preregistration` pattern).** Before any collection run, §0 of the milestone report fixes, in writing:

- **Prediction (quoted).** A commit deposited at deterministic cell `(x,y,z)` (from its content hash) and later retrieved produces a Stage-4 nearest-attractor agreement that is *not distinguishable from a commit deposited at a uniform-random cell*—i.e. the deterministic placement is a *precondition* for the field-as-memory claim, not itself the claim. The measurable target is: `z_agreement(commit) > 2`, where `z_agreement` is the Stage-4 statistic defined below.
- **Statistic (exact estimator).** For each retrieved commit-engram over the collection window, `d = min over projected top-k attractor cells of spatial distance(engram cell, attractor cell)` in the quantized 64³ lattice; the statistic is `z = (null_mean − obs_mean) / null_sd` over all retrieved commits, where the null is the distribution of `d` for 1000 uniform draws on the 64³ lattice (the §19 positional-agreement harness definition, `UNIFICATION.md` §1.6 Stage 4 — adopted verbatim so the milestone shares the §34 metric).
- **Decision tree.** `ADOPT placement` = `z > 2` in ≥2/3 of weekly collection sessions (the §19 threshold, reused). `NULL placement` = `z ≤ 2` in ≥2/3 of sessions — the deterministic placement adds nothing spatial, and the section's honest-negative status is recorded. `INCONCLUSIVE` = fewer than 2/3 of sessions clear EITHER band, or the epoch-to-cell mapping JSONL is missing/corrupt (a failed control), or the engine was down for >50% of a session (no field structure formed to measure).
- **Stopping rule.** Fixed: collect across K sessions (K ≥ 3, each a full working week of commits on the watched repos); ONE analysis pass; no sequential testing, no post-hoc cuts on sessions or commits; the epoch-to-cell journal is the immutable pairing record. The rule is fixed before the first commit is collected.

The milestone's verdict is **"the deterministic commit placement is (or is not) spatially retrievable in the field"** — NOT "memory is a galaxy." The galaxy renders regardless; what is claimed is only whether the placement survived into the projection topology.

### 4.3 Phase 2 artifact: the full-event collector + galaxy renderer

With the git stream measured, the collector widens to the full Section 1.4 inventory (file edits, build/test results, searches, tool calls, sessions, messages) and the galaxy renderer lands behind the sim UI registry (Section 3). This phase is ~all cheap, existing-surface work: the encoders, the drainer, the instancer, the theme, Movie Maker all exist. Two mode toggles are added as `EXTRA_TOGGLES` rows (`sim_ui.gd` lines 209–216 pattern): **"Field galaxy"** (overlay markers on/off) and **"Dream record"** (start/stop a `main_recorder.gd`-style dream archive capture). Nothing in this phase changes the field or the brain's behavior—it is visualization of the collector's sediment.

### 4.4 What is NOT claimed until §19 passes (explicit)

Until `CassiTheory`-governed §19/§34 passes (`z > 2` in ≥2/3 sessions), the following claims are **explicitly NOT made** by this spec or by any collection/render milestone:

- **NOT "the field is memory."** The galaxy is a visualization of an *unproven mechanism* until the §19 positional-agreement harness shows field structure tracks retrieval structure (`UNIFICATION.md` §4 Phase 9 risk). The galaxy's glowing clusters reflect *deposits*, not proven memory traces.
- **NOT "retrieval is improved by the field."** The projection stream feeds MnemicField's HEALPix salience bonus (`UNIFICATION.md` §1.6 curation wiring), but no claim that the bonus improves end-to-end retrieval is made until the dream-phase recall A/B (gated on §19 data) measures it.
- **NOT a steering loop.** The collector is passive ingestion. It does not read-then-inject; it never performs per-step pointwise injection (the G34-degrading pattern, `UNIFICATION.md` §5.1). If anyone extends it toward steering, that is Phase 3's territory, pre-registered separately and cadence-gated.
- **NOT a φ-cadence schedule.** No claim that the field's observed dynamics are φ-structured; the base field was measured as a mixing clock at current twist strength (G4c FP-4, `UNIFICATION.md` §1.6). The galaxy shows coherence, not a validated clock.
- **NOT digital-world "understanding."** The deposit encoder maps events to cells deterministically; it does not claim the field *knows* what files/code/events mean. It digests and spatially organizes the flow—which, under the thesis, is the substrate intelligence steers—but the steering claim is the program's, downstream of the honest gates.

### 4.5 Honest negatives are deliverables

Per the program's discipline (`UNIFICATION.md` §1.6 and §5), each milestone's report carries its honest-negative branch as a first-class outcome, not a failure: a NULL placement in Phase 1 is a valid deliverable that closes the "deterministic placement aids retrieval" question at measured cost; the galaxy still renders, and the field-as-memory claim simply remains un-adopted until §19. The spec's build order is deliberately structured so a negative at any phase costs visualization time, not doctrine.

## 5. Risks and explicit caveats

1. **The galaxy visualizes an unproven mechanism until §19.** Section 4.4 is the load-bearing caveat; every milestone's report must re-state it. Phase 9's build order exists precisely so the cheap visualization precedes (and funds) the gated dream A/B.
2. **Placement determinism vs. consolidation drift.** The collector deposits at deterministic cells; consolidation then *moves* engrams (co-activation, centripetal, angular drift—Section 3.4). The Phase-1 statistic must define "retrieved engram cell" off the *post-consolidation* position (the `project` readout), not the original deposit, or it measures the encoder, not the field. This is a control check, not a confound—specified in §4.2's statistics.
3. **Two coordinate systems must stay aligned.** The encoder's engram `(x,y,z) ∈ [-1,1]³` (the field-engine grid) maps to the sim's world when the sim and engine share `extent`. If the sim's box drives to a different extent (a `box_scale`/`box_aspect` reinit, `sim_ui.gd` EXTRA_PARAMS lines 201), the galaxy markers must transform with it or they will not overlay the physical particles. The renderer's cluster positions come from the engine's `project` `(x,y,z)` directly, so this is an overlay-mapping concern, not a data concern.
4. **Deposit flood from passive ingestion.** High-volume near-zero-salience types (tool, file_read, message) can swamp the field if unthrottled. The rate cap (Section 2.3) is a collector config; it must be pre-registered with the same discipline as any other knob so it cannot become a post-hoc selection (dropping "noisy" sessions to hit a threshold).
5. **The σ and ε conventions travel with the ledger.** Two ε conventions (theory ε = EY−φEI vs AI ε = ψ−P[ψ]) and two q conventions (field q = EY²+EI² vs AI Q = surprise) are open (UNIFICATION §5.3). The encoder table fixes its charges deterministically; any port that changes a σ contract or a z threshold must re-run the host-wired suites (UNIFICATION §5.7 port discipline) or it silently invalidates the §19 ledger.

## References

- `C:/Users/Carina/workspaces/Cassi/UNIFICATION.md` §3.4 (AI I/O is field probing), §4 Phase 9 (the engram galaxy), §1.6 (Stage 4/§19, Stage 3-wiring, ledger), §5 (risk notebook)
- `CassiCore/packages/mnemic-field/src/attractor.ts` — three-pole attention, radial boost, sigma
- `CassiCore/packages/mnemic-field/src/engram-decomposer.ts` — density decomposition
- `CassiCore/packages/mnemic-field/src/consolidation.ts` — consolidation engine, TYPE_POTENTIATION, drift/potentiation
- `CassiCore/packages/mnemic-field/src/kindling.ts` — spreading activation, photon spread, spark point
- `CassiCore/packages/mnemic-field/src/healpix.ts` — HEALPix shell/cell assignment, phiFromZ
- `CassiCore/packages/mnemic-field/src/spatial-index.ts` — 1,020-cell HEALPix spatial index
- `CassiCore/packages/mnemic-field/src/types.ts` — engram `(x,y,z)`, TYPE_POTENTIATION, SYNAPSE_PROPAGATION
- `CassiCore/packages/mind-runtime/src/channel/server.ts` — the 7273 loopback channel (10 endpoints, bearer token)
- `CassiCore/packages/mind-runtime/src/boot.ts` — the retained composition root (MnemicField + unified loop)
- `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-bridge/index.ts` — `FieldShadowBridge`, `readProjection(k)`, `ProjectionCell`, shadow semantics
- `CassiCore/packages/mind-runtime/src/vendor/core/intelligence/field-encoder/index.ts` — `StandardMindFieldEncoder`, `TYPE_CHARGE`, `depositEngram`
- `CassiCosmos/scripts/cassi_mind_engine.gd` — the 7599 TCP bridge (`deposit`/`readout`/`project`), TSC scatter, grid_n=64
- `CassiCosmos/tools/engine_cache_writer.py` — the landed writer/collector pattern (BridgeClient, gates, seeded families)
- `CassiCosmos/scripts/sim_ui.gd` — the UI design system (settings registry, theme, gradient legend, auto-track)
- `CassiCosmos/compute/cassi_instancer.glsl` — the particle instancer (Qi coherence channel, glow/size/depth flags)
- `CassiCosmos/scripts/main_recorder.gd` — the Movie Maker background recording scene
- `CassiCosmos/verify/README.md` — the GPU battery rule (windowed, no `--headless`)
