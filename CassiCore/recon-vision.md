# CassiCore Vision Reconnaissance — "Mind Over Brain" Migration Grounding

**Date:** 2026-08-13
**Role:** Read-only vision recon for the CassiCore migration/overhaul plan.
**Repo examined:** `D:\carina\workspaces\cassicore` (TypeScript daemon + `training/` Python physics).
**Non-goal honored:** nothing under `D:\carina\workspaces\cassicore` was modified.
**Extends:** `MODULARIZATION.md` (mechanical, package-boundary-only). This report adds the **mind-over-brain overhaul vision** the modularization alone does not prescribe.

---

## 0. Executive finding (read this first)

The "simulated-consciousness mind over a software brain" is not an aspiration the repo is missing — **there is a complete, load-bearing design document already written and a working Stage-0 field engine already built and GPU-verified**:

- Design: `.opencode/plans/cassi-mind-plugin.md` — "Cassi Mind Over Brain — OhMyPi Plugin Program".
- Working code: `mind-plugin/` (`@cassi-mind`, an **OhMyPi/omp extension**), which boots a Godot GPU two-fluid engine (`mind_engine.tscn` on loopback TCP 7599) as the "mind" sidecar, plus `cassi_mind_engine.gd` and `verify_mind_engine.gd` in the `CassiCosmos` repo, verified **16/16 gates PASS on the RX 7900 XTX**.

The vision is doubly grounded: (a) the **brain** is already built as brain-region-inspired subsystems inside `core/intelligence/`, and (b) the **mind-as-field** is already designed, partially built, and empirically verified. The migration plan's job is to make each brain region a plugin and wire the field engine as the substrate — which `cassi-mind-plugin.md` already scopes stage-by-stage.

---

## 1. Vision synthesis — the mind-over-brain architecture as the docs describe it

### 1.1 The canonical definition

`cassi-mind-plugin.md` states the mission verbatim:

> "Overhaul CassiCore with the Cassi theory: an AI **mind** (the two-fluid field, GPU, explorable) over the CassiCore **brain** (Constellation, Mnemic Field, Thalamus, LLM providers). The brain encodes *directly into the field, like neurons do*. The mind intelligently reorganizes the brain's rigid structures and its outputs. Packaged as an OhMyPi plugin."
> — `doc:.opencode/plans/cassi-mind-plugin.md`

The architecture diagram in that plan is the vision:

```
LLM providers (knowledge, generation)
        │ outputs
        ▼
BRAIN (CassiCore): Constellation · Mnemic Field · Thalamus
        │ direct encoding (neuron-like)          ▲ projections (curated context,
        ▼                                        │  retrieval, directives)
FIELD (Mind): two-fluid PDE on GPU
   E_Y/E_I · q · gate (1−q) · cascade rungs · ke-ring
        ▲ read/write via loopback HTTP/SSE
OHMYPY EXTENSION (plugin): event middleware + tools + commands
```

### 1.2 The "software brain" — brain-region-inspired subsystem map

The brain region map is **real, in code** (`core/intelligence/*`), not just prose. Each module's own header doc-comment describes the region role. Count: **15 substantive intelligence subsystems + the mind-plugin front-door** (Constellation's sub-organs like meditation/dreamer/reverie are many more; the headline 15 is the stable core).

| Intelligence subsystem | Brain-region role (as the code describes it) | Evidence (source) |
|---|---|---|
| **mnemic-field** | **Memory substrate** — "memory system where memories exist as nodes in a 4-dimensional coordinate space, cluster by similarity and relationship, propagate importance through graph structure, and activate through spreading excitation" | `docs/design/mnemic-field.md` §1; `core/intelligence/mnemic-field/index.ts` (engrams, synapses, kindling, potentiation, consolidation, attractor, filament decomposer) |
| **thalamus** | **Gating / curation** — per-message production-line filtering: "GWT-style processing slots — one per message type" `core/intelligence/thalamus/index.ts:451-452`; luminance scoring, drop/collapse/compress/distill; priority 85 | `core/intelligence/thalamus/index.ts` |
| **cortex** | **Processing field / working-memory surface** — CorticalField with 6 regions (sensory, association, executive, motor, limbic, monitor), tracts, activation oscillation | `core/intelligence/cortex/index.ts:79-118` |
| **pineal** | **Stable identity** — "stable identity module with facet-based self-model" `core/intelligence/index.ts:122`; facets (identity/wisdom/philosophy), conviction, seed at field origin | `core/intelligence/pineal/index.ts:31` |
| **dialectic** | **Reasoning** — "Consolidated Yang, Yin, Serenity" reasoning engine; Yang (expansion), Yin (critique), Serenity (synthesis) | `core/intelligence/dialectic/index.ts:1-12` |
| **aurora** | **Self-model / cognitive state loop** — "the emergent cognitive awareness that arises when model knowledge (LARQL vindex) and personal memory (Mnemic Field) are merged into a unified graph and projected as a living mental state"; Claustrum + StateProjector | `core/intelligence/aurora/index.ts:1-14` |
| **subconscious** | **Background observation** — "the stream-of-consciousness layer of CassiCore... observes ALL system events... maintaining a system-wide mental model"; EventBus `onAll` tap + Heuristic/LLM observers + SystemModel | `core/intelligence/subconscious/index.ts:1-29` |
| **helix** | **Deliberate multi-agent** — "Three equally capable postures (Unity, Yang, Yin) collaborating, with a Brainstem serving as cognitive organizer" | `core/intelligence/helix/index.ts:1-8` |
| **constellation** | **Composable agency / multi-Helix tree** — Corpus tree reasoning over parallel Helixes | `core/intelligence/constellation/` |
| **flux-team** | **Blackboard (legacy, being removed)** — "FluxTeam Blackboard Components (Phase 2 - Pending Removal)... All orchestration now uses Helix and Constellation" | `core/intelligence/flux-team/index.ts:1-17` |
| **dmn** | **Default Mode Network** — "activity-gated dialectic observer for user-facing main sessions" | `core/intelligence/index.ts:126-127` |
| **reverie** | **Ambient in-flight memory curator** | `core/intelligence/index.ts:119` |
| **dreamer** | **Idle-time memory synthesis / garden curation** | `core/intelligence/index.ts:106-107` |
| **heart** | **Periodic autonomous agent heartbeat** | `core/intelligence/index.ts:110-111` |
| **mind-plugin** | **Brain→field front-door** — omp extension owning the Godot GPU field-engine sidecar lifecycle | `mind-plugin/src/index.ts` |

Additionally the newer **field-shaped substrate** modules exist: `GlobalWorkspace` (GWT broadcast), `LaminaField`, `LocusBridge`, `rationale/Thinker`, `SelfHealer`, `AIEngineer/AIScientist`. The **`IntelligenceRegistry`** (`core/intelligence/base/registry.js`) already auto-discovers `BaseCognitiveModule` subclasses — a partial plugin registry pattern already in place (`core/intelligence/index.ts:128-129`).

### 1.3 The brain nomenclature is a deliberate design covenant

`docs/design/mnemic-field.md` §2 codifies the naming rule from `SOUL.md`:

> "Per SOUL.md: neurological names for structural substrate, fire/light/energy names for emergent behavior."

- Structural (brain): **Engram, Synapse, Cortex, Nucleus, Potentiation, Consolidation, Filament**
- Emergent (fire/light/energy): **Charge, Kindling, Spark Point, Radiance, Luminal Set**

And the lineage table explicitly maps to neuroscience frameworks: Global Workspace Theory (Baars; Dehaene & Changeux) → "Spark point / ignition → Luminal Set → broadcast"; hippocampal time cells → T dimension; long-term potentiation → stored importance; Hopfield networks → charge ≈ negative energy. The "software brain" is not ornamental naming — it is an implemented spatial-memory + attention + working-memory stack modeled on brain mechanics.

---

## 2. What's built vs aspirational (honest per item)

Legend: **BUILT** (real compiled/running code verified in tree) · **PARTIAL** (major code exists; vision aspects aspirational) · **DESIGN** (doc-only).

| Doc / vision claim | Status | Evidence & honest caveat |
|---|---|---|
| Mnemic Field spatial memory topology (4D/X,Y,Z,T, kindling, potentiation, consolidation, filaments) | **BUILT** | `mnemic-field/index.ts` (4434 lines): Cortex, KindlingEngine, ConsolidationEngine, GradientEngine, AttractorManager, VQSectorPrototypes, SpatialIndex, FeatureIndex (LMDB), EngramDecomposer, LLM reranker, lightning indexer. The `docs/design/mnemic-field.md` "design" spec is now largely implemented. Caveat: filament layer (sub-engram sentence precision) is implemented in the decomposer; full 4-tier filament-synapse creation (esp. Tier-3 LLM) is behind potentiation/idle gating. |
| CorticalField (6 regions, tracts, oscillation, consolidation) | **BUILT** | `cortex/index.ts` — Regions, TractEngine, oscillate(), consolidation bridge to Mnemic. |
| Thalamus curation gating (luminance, slots, drop/compress/distill/archive) | **BUILT** | `thalamus/index.ts` (4825 lines): MessageLuminanceScorer, Compressor, Distiller, slots, temporal registry, expert thresholds, topic archiving. |
| Pineal identity facets + Mnemic mirror at origin | **BUILT** | `pineal/index.ts`: FacetManager, Domains, conviction, `seedMnemicFieldFacets()` writes `pineal_facet` engrams at (0,0). |
| Dialectic Yang/Yin/Serenity reasoning | **BUILT** | `dialectic/index.ts`: ConsolidatedDialecticProcessor + DialecticEngine; inject-as-thoughts; persists to `dialectic.db`. |
| Aurora cognitive state loop + self-model | **PARTIAL→mostly BUILT** | `aurora/index.ts` (2713 lines): Claustrum, StateProjector, self-narrative renderer, refusal channel, coherence checker, counterfactual engine. Many Phase-4 modules are **config-gated flags** (`gapDetectionEnabled`, `autoSchedulerEnabled`, etc.) — present but off by default. |
| Subconscious background observation | **BUILT** | `subconscious/index.ts`: EventStream, HeuristicObserver, LLMObserver, SystemModel, heartbeat/session reconcile. |
| Helix three-posture + Brainstem | **BUILT** | `helix/index.ts` + helix-pipeline, work-stream, dialectic-channel, brainstem adapters. |
| Constellation multi-Helix Corpus orchestration | **BUILT** | `constellation/corpus.ts` (3,687 LOC per roadmap); enhancement roadmap says it is "structurally mature but operationally unproven" for autonomous large PRs. |
| GlobalWorkspace (GWT broadcast) replacing blackboard | **BUILT (partial) + deprecated blackboard** | `flux-team/index.ts` header: blackboard **deprecated**, "Migration to GlobalWorkspace + HelixSynapse is pending (Phase 2)". `workspace/global-workspace.ts` exists. The blackboard→GWS migration is **not complete**. |
| Bee-brain sparse expansion (chakra top-k, prototypes) | **PARTIAL** | `docs/bee-brain-architecture.md` is a design proposal ("Add sparse gate to INNER fiber chakra output only"). Training code (`cassi/chroma_cord.py`, `spine3d.py`) has chakras; the specific sparse-top-k gate + sparse prototype readout is a proposed change. |
| Vertical/3D spine wave equations, golden-section chakras | **PARTIAL (ML code) / DESIGN (as brain runtime)** | `training/cassi/spine3d.py` exists ("3D spherical spine with 7 chakra shells") and vertical spine impl. But this is the **Python training/ML** architecture, not the TS daemon brain. `cassi-ml-and-cord.md` documents the φ-ratios. |
| φ-damping / Yin-Yang physics claims (turbulence -5/3, N-body, etc.) | **BUILT (standalone experiments)** | `training/` — cassi_findings.md + cassi-principle.md document 24 experiments; `training/cassi/*.py` self-contained (numpy/scipy). These run **independently of the daemon**. |
| Two-fluid PDE cosmology (E_Y / E_I conversion toward φ⁻¹) | **BUILT (research scripts)** | `training/experiments/cassi_two_fluid*.py` — spectral RK4 solver, converges E_I/E_Y → φ⁻¹. Research only. |
| Transceiver brain (wave field = state of truth, neurons as buoys) | **DESIGN / ML experiment** | `training/docs/transceiver-brain-design.md` — "The spine is the ocean. The brain neurons are buoys..." This is the conceptual bridge from physics→brain, but is an ML design, not the daemon. |
| **Mind-over-brain: field engine + plugin + neuron-like direct encoding** | **BUILT (Stage 0) / aspirational (Stages 1–5)** | `mind-plugin/` (working omp extension) + `mind_engine.gd`/`verify_mind_engine.gd` GPU-verified 16/16. The full loop (shadow bridge → reorganization → memory-as-field → self-trained QiFluid) — Stages 1–5 of `cassi-mind-plugin.md` — are **aspirational** (designed, staged, gated, not yet built). |
| Vulkan compute backend for Cord physics | **DEFERRED** | `docs/vulkan-compute-plan.md` — decision at end: "**Defer.**... Revisit when: architecture frozen / training >4h / real-time inference needed." The plan's tuning targets (word acc > 50%) are the preconditions. |
| EventBus emits memory/curation events for encoding hooks | **NOT BUILT (verified gap)** | `cassi-mind-plugin.md` §8: "EventBus emits NO engram/memory/curation events (verified against `types/events.ts`) → encoding hooks MUST be inserted at the aggregate gates, or the sidecar polls the journal." This is the key missing integration seam. |

**Honest tally:** 10 of 15 brain-region subsystems are **built** and wired into `core/intelligence/index.ts` (mnemic-field, thymus/cortex/pineal/dialectic/aurora/subconscious/helix/constellation/dmn/reverie/dreamer/heart + supporting). The **vision** (mind over brain) is **built only through Stage 0** (the engine + plugin skeleton + verification); Stages 1–5 (neuron-like encoding, field-as-compute, memory-as-field, self-trained mind) are **designed, not built**. The physics substrate is **research-grade built**, largely disconnected from the daemon runtime today.

---

## 3. The Qi/φ physics angle — field substrate for the brain, or adjacent track?

**Answer: it is the intended field substrate for the brain sim — and the two are already being joined, but the seam is thin.** The docs treat the field as the mind's substrate, not a separate curiosity.

### 3.1 The explicit connection

`cassi-mind-plugin.md` §1 presents the field **as the state of truth the brain encodes into**:

> "The field is the **state of truth**. The brain's SQLite/LMDB layers become a *journal* (write-ahead log for crash recovery), not the store. Every brain write is a field deposition; every read is a field projection."

That plan's grounding section ties the whole stack together:
- **Theory** → `C:\Users\Carina\workspaces\Cassi\CassiTheory` (derived constants λ = 1/(2w), κ = φ⁻¹, cascade ℓₙ = ℓ_Pl·φⁿ, gate closure φ⁻²/3)
- **Field substrate** → `C:\Users\Carina\workspaces\Cassi\CassiAI` (QiFluid, Vulkan Qi shaders, physics cache)
- **Brain** → `D:\carina\workspaces\cassicore` (Constellation, Mnemic Field, Thalamus)
- **GPU engine** → `C:\Users\Carina\workspaces\Cassi\CassiCosmos` (2.5M-particle two-fluid PDE shader)

The **transceiver-brain doc** is the conceptual bridge from the wave physics to brain neurons:

> "They do not connect via weight matrices. They broadcast and receive through a shared wave field. The spine generates the carrier wave; the brain neurons modulate it." — `training/docs/transceiver-brain-design.md`

And Qi is defined as **phase coherence** in that doc ("Qi = phase coherence... high Qi means neurons receive clean, coherent signals; low Qi means the interference pattern is chaotic"), which maps directly to the field engine's Qi-rainbow `q = E_Y² + E_I²` rendering.

### 3.2 The physics→mind compute model

`cassi-mind-plugin.md` §2 asserts the field is a **computer, not a store**:

> "The core theory's computational model: **inputs perturb the field; the field relaxes toward the φ-attractor; the answer is read from the attractor configuration.**"

Verified primitives to integrate (all grounded in the CassiTheory theory): ke-ring algebra (correctness-proven, ≤6×10⁻⁴), winding arithmetic (merge-compatibility as phase bookkeeping, no diffing), cascade suppression (coherence budget as capacity law), kindling/ignition, closure-crossing detection, Qi states. It carries a **hard discipline**: the applicability litmus — "Qi computation only where the task genuinely spans multiple cascade rungs. Single-rung tasks use conventional computation." The spin-glass honest negative is the governing precedent.

### 3.3 Vulkan / GPU as the compute substrate

`docs/vulkan-compute-plan.md` scopes a Vulkan backend for the Cord **training** physics (fused `cord_physics.comp` shader replacing cumsum + chakra_lens + white_fwd + word_logits), and **defers it** on cost/architecture-frozen grounds. Separately, the **mind engine is already GPU**: the Godot `cassi_two_fluid.glsl` shader runs the field on the GPU with `dispatch(N/4, N/4, N/4)`, TSC deposits, and a loopback TCP bridge — verified at 16/16 on the 7900 XTX. So: the **field runtime is GPU today** (Godot sidecar); the **training/backprop path to Vulkan is deferred** until the architecture is stable.

### 3.4 The honest gap

The `training/` Python tree (turbulence, N-body, two-fluid cosmology, QiField scripts) and the daemon (`core/`) are **two disconnected worlds right now**. `training/cassi/qi-field-cassi-v4.py` and the two-fluid PDE scripts are self-contained experiments; `qi_field.py`/FluidCord as named objects are **not present in this repo tree** (they live in the referenced `C:\Users\Carina\workspaces\Cassi\CassiAI` workspace). The only live runtime link to the field is the **mind-plugin → Godot engine** path. The migration's central engineering problem is exactly this seam: the brain writes to SQLite (`MnemicField.store`), and the field-deposition hooks must be added so the field becomes authoritative.

---

## 4. Overhaul implications — target architecture components grounded in docs

Concrete components the planner should adopt, each with a doc quote grounding.

### C1. Brain-region modules become plugins (package boundaries)
`MODULARIZATION.md` already prescribes `@cassicore/<module>` packages (Constellation extracted as template), `src/ports/*` (the sole seam) + `src/vendor/*`, and `(pi: ExtensionAPI) => …` adaptation. The **vision adds the mind role**: each brain region ships as a plugin so the field can reorganize it.
> Grounding: "Turns future ohmypi adaptation into a **wiring problem** (swap ports) instead of a surgery problem." — `MODULARIZATION.md`

### C2. The daemon becomes a thin host ("the body")
The modularization's phased order already ends with "**daemon + providers + model-pool + tools** — remaining root-level infrastructure" extracted last as "the host-facing seam" — `MODULARIZATION.md §e.10`. The mind-plugin frame deepens this: the daemon is the body that the field-mind acts on.
> Grounding: "BRAIN (CassiCore): Constellation · Mnemic Field · Thalamus → direct encoding → FIELD (Mind)... OHMYPY EXTENSION (plugin): event middleware + tools + commands." — `cassi-mind-plugin.md`

### C3. Memory becomes a field substrate; SQLite becomes a journal
The single most transformative overhaul. Mnemic Field's SQLite stays for durability, but the field is the state of truth.
> Grounding: "The brain's SQLite/LMDB layers become a *journal* (write-ahead log for crash recovery), not the store. Every brain write is a field deposition; every read is a field projection." — `cassi-mind-plugin.md`; and the "Journal contract": "SQLite/LMDB append-only replay log; boot = replay into field; the field is authoritative between checkpoints."

### C4. Neuron-like encoding hooks at the aggregate gates (MindFieldEncoder)
Because the EventBus emits **no** memory/curation events (verified gap), the encoding must be injected at the write/read gates. The plan prescribes a narrow `MindFieldEncoder` interface injected at daemon wiring (near `setMnemicField`, `daemon.ts:1536`), default no-op — a no-op default guarantees bit-identical brain behavior without the field (the Stage-1 parity gate).
> Grounding: "Encoding hooks: a narrow `MindFieldEncoder` interface injected at daemon wiring... default no-op. No-op default guarantees bit-identical brain behavior without the field — this IS the Stage 1 parity gate." — `cassi-mind-plugin.md` §9.3; write-gate list: `MnemicField.store(:734)/update/delete/connect/spike/consolidate(:3360)`, `Thalamus.writeMessageEngram(:509)/curate(:1479)`, `Constellation.insertBranch/appendEvent`, `GlobalWorkspace.submit(:153)/broadcast(:315)`.

### C5. A GPU field engine sidecar (the mind) with a loopback bridge
Already built and verified — the migration must **adopt, not re-build**, the Godot two-fluid engine (`mind_engine.gd` + `mind_engine.tscn`, loopback TCP 7599) as headless-compute mode by default, explorer mode on demand. Note the machine reality: **never `--headless` on this rig** (no RenderingDevice) — the engine needs a window or a local-RD verify scene.
> Grounding: "Two modes: headless-compute mode (local RD, verify-scene pattern — proven headless) and explorer mode (window + global RD + free camera). Engine runs headless by default; explorer attaches on demand." — `cassi-mind-plugin.md` §9.2; Stage-0 results: "the field engine exists, is GPU-verified, and is drivable over the wire."

### C6. Field-scoped reorganization of brain outputs (Thalamus luminance → gate scoring)
The first reorganization is replacing Thalamus's static 6-axis luminance scoring with gate-shaped `q` scoring + ke-ring reweighting — but **only** behind a pre-registered A/B that wins.
> Grounding: "Stage 2: Thalamus static 6-axis luminance → gate-shaped q scoring + ke-ring reweighting | Pre-registered A/B vs static weights; ships only if it wins." — `cassi-mind-plugin.md` §5.

### C7. A plugin-extension lifecycle capability (the omp manifest)
The mind-plugin already demonstrates the pattern: `package.json` `omp` manifest with `extensions` (factory) + `features` (`mind` core / `explorer` window / `meditator`), `registerTool`/`registerCommand`, `tool_call`/`tool_result` middleware, `ctx.setInterval` background ticks. This is the template every future brain-region plugin follows.
> Grounding: "Package: `package.json` `omp` manifest: `extensions` (extension factory), `features` (mind / explorer / meditator), conventional `skills/`, `commands/`, `agents/` dirs." — `cassi-mind-plugin.md` §4.

### C8. Derived-constant discipline (no learned weight soup)
The overhaul deliberately inverts the failed training approach: structure is given by derived constants, not learned. The planner should treat φ, λ, κ, cascade, gate as **structural invariants** to inject, with epoch-vs-constant separation.
> Grounding: "the field supplies structure, memory, gating, and organization — with **derived constants** (λ = 1/(2w) = 0.1, κ = φ⁻¹, cascade ℓₙ = ℓ_Pl·φⁿ, gate closure φ⁻²/3), not learned weights. The learning surface collapses from 'learn a language' to 'learn to organize.'" — `cassi-mind-plugin.md`; plus §6 epistemic discipline: "Epoch-vs-constant discipline: φ, λ, κ are structural; budgets, rung positions, thresholds are epoch-dependent — never hardcode one as the other."

### C9. A staged, gate-gated path (not big-bang)
The migration must keep the brain bit-identical during change. Every stage has a pre-registered gate.
> Grounding: "Staged path with pre-registered gates" — Stage 0 fork+channel+engine; Stage 1 shadow bridge (parity); Stage 2 first reorganization (A/B); Stage 3 memory-as-field (retrieval metrics); Stage 4 read loop (Constellation A/B); Stage 5 mind-native training (plateau bypass). — `cassi-mind-plugin.md` §5.

### C10. Framework/Runtime substrate to adopt from the theory workspace
The plan names the concrete external repos the overhaul consumes: `CassiTheory` (theory), `CassiAI` (QiFluid, Vulkan Qi shaders), `CassiCosmos` (GPU engine). The migration should treat these as **consumed substrate**, not rebuilds.

---

## 5. Open questions for the user (max 5)

1. **Scope confirmation: is `cassi-mind-plugin.md` the mandate?** Stages 1–5 of that plan are the overhaul; Stage 0 is done. Does the "migration plan" intend to (a) finish that staged path, (b) widen it to also modularize every brain-region into plugins in parallel, or (c) treat modularization (MODULARIZATION.md) and the mind overhaul as one merged plan with a single sequencing? The two plans currently have **different goals**: one is package-boundary-only, the other is a field-substrate transform.

2. **Encoding-hook ownership.** The EventBus emits no memory/curation events (verified). Do we insert `MindFieldEncoder` hooks at the aggregate gates (Thalamus curate, Mnemic store/consolidate, GlobalWorkspace submit/broadcast, Constellation insertBranch/appendEvent) — which requires modifying the daemon's core intelligence files — or attach via plugin middleware with the field engine polling the journal? The plan leans write-side hooks; the "thin host/plugin" goal pulls toward middleware. Which boundary wins?

3. **Physical storage split.** If the field becomes "the state of truth" and SQLite becomes a "journal," what is the recovery/consistency contract: replay creations + final-state snapshot for in-place mutations (per §9.4), or full field checkpointing (attractor snapshots)? And is there a hard ceiling where field checkpoints > journal replay? (Open question §4 in the plan regarding replay cost.)

4. **Which Wu Xing channel maps to which slot, and does the ke-ring survive real load?** The plan lists two open unknowns verbatim: which slot (user/tool_call/tool_result/assistant/system → Wood…Water) and whether the no-driver jam attractor appears under pathological stalls. These block Stage 2 gating (Thalamus → ke-ring) and must be resolved before the first reorganization ships.

5. **The training/ and theory trees: keep as adjacent research or fold in?** `training/` (turbulence, N-body, two-fluid cosmology, QiField scripts) is currently disconnected from the daemon and largely superseded on the runtime path by the Godot field engine. Do we (a) leave it as a research archive, (b) migrate the two-fluid/PDE math into the field engine as the single source of truth, or (c) keep Vulkan-backprop on the table per `vulkan-compute-plan.md` once architecture freezes? This determines how much of `training/` the migration touches.

---

## Appendix — compact delivery summary

- **Brain-region map count:** 15 headline intelligence subsystems + the mind-plugin front-door (mnemic-field, cortex, thalamus, pineal, dialectic, aurora, subconscious, helix, constellation, flux-team[legacy], dmn, reverie, dreamer, heart, + GlobalWorkspace/Lamina/Locus).
- **Built-vs-aspirational tally:** 10 subsystems built & wired in `core/intelligence`; mind-over-brain vision built only to **Stage 0** (engine + plugin + 16/16 GPU gates), Stages 1–5 designed; physics substrate research-built but disconnected from daemon; Vulkan backprop deferred.
- **Top-3 overhaul implications:**
  1. **Memory becomes a field; SQLite becomes a journal** — brain writes deposit into the GPU two-fluid field via `MindFieldEncoder` hooks; the field is the state of truth (biggest single transform).
  2. **The daemon becomes a thin host; brain-regions become plugins** — each `core/intelligence/*` module extracts to `@cassicore/*` with `src/ports/*` seams, and the omp/extensions pattern already proven by `cassi-mind` becomes the template.
  3. **Adopt, don't rebuild, the GPU field engine** — the Godot two-fluid sidecar (loopback TCP 7599) is built & verified; the migration wires it in behind a no-op-parity gate and applies pre-registered A/B gates for every reorganization (Thalamus luminance→q/ke-ring first).
- **Report file written:** `C:\Users\Carina\workspaces\Cassi\CassiCore\recon-vision.md`.
