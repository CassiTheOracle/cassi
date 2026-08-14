# P5-A — `@cassicore/thalamus` + `@cassicore/aurora` + `@cassicore/cortex-pineal-dialectic` + `@cassicore/cognitive-feed` — Migration Table (Planning Deliverable)

**Sources (READ-ONLY, D:):** `core/intelligence/{thalamus,aurora,cortex,pineal,dialectic,cognitive-feed}/`
**Destinations:** `C:\Users\Carina\Workspaces\CassiCore\packages\{thalamus,aurora,cortex-pineal-dialectic,cognitive-feed}\src\`
**Recon:** `C:\Users\Carina\Workspaces\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\Workspaces\CassiCore\CASSI-MIND-PLAN.md` §5-P5, §4, §7
**Exemplars (house format):** `P1-foundation-migration-table.md`, `P2-helix-migration-table.md`, `P3-flux-team-mini-helix-migration-table.md`, `P4-mnemic-field-migration-table.md`
**Date:** 2026-08-13
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the ONLY file written by this drafting pass; it is NOT git-added/committed (a parallel session
> is committing in the workspace — this file must stay untracked).

> **Grouping correction (evidence):** the plan's P5 table groups `@cassicore/aurora` as `aurora/*` *+*
> `core/intelligence/self-model/*`. **No top-level `core/intelligence/self-model/` directory exists** (verified:
> the only `self-model` dir under `core/intelligence/` is `mnemic-field/self-model/`, owned by P4). Aurora's
> self-model cluster is **internal to `aurora/`** (`self-model-knowledge.ts`, `concept-self-awareness.ts`,
> `inference-trace.ts`, `self-narrative-renderer.ts`; `mnemic-steering-bridge.ts` is DEAD). So `@cassicore/aurora` =
> `aurora/*` **alone** (42 live files, including its self-model files). See Open Flag 1.

---

## 0. Phase summary

| package | source dirs | live-set | DEAD excluded | UNCERTAIN | dest layout | registry contract |
|---|---|---|---|---|---|---|
| `@cassicore/thalamus` | `thalamus/*` | **17** | 0 | 0 | `src/` + `src/slots/` (mirror) | **registry-discovered** — `ThalamusModule extends BaseCognitiveModule` (name=`thalamus`, priority=85) |
| `@cassicore/aurora` | `aurora/*` (self-model cluster is internal) | **42** | 9 | 0 | `src/` + `src/{composition,calibration,projection,coherence-detector}/` (mirror) | **explicit** — `class Aurora` (NOT BaseCognitiveModule); wired via `createIntelligence()` |
| `@cassicore/cortex-pineal-dialectic` | `cortex/*` + `pineal/*` + `dialectic/*` | **26** (9+8+9) | 3 (1+1+1) | 0 | `src/cortex/` + `src/pineal/` + `src/dialectic/` (three mirrored subdirs) | **mixed** — `PinealModule` registry-discovered; `CorticalField` + `DialecticSystem` explicit |
| `@cassicore/cognitive-feed` | `cognitive-feed/*` | **14** | 0 | 0 | `src/` (flat) | **registry-discovered** — `CognitiveFeedModule extends BaseCognitiveModule` (name=`cognitive-feed`, priority=5) |
| **P5-A total** | | **99** | **12** | 0 | | |

**DEAD file tally (all confirmed in `recon-data.json deadFiles`):** aurora 9 (`affect-calibration`, `affect-probes/v1`,
`affect-signature-store`, `claustrum-snapshot`, `coherence-detector/probe-set`, `fine-tune-gating`,
`mnemic-steering-bridge`, `nla-bridge`, `welfare-probe-set`); cortex 1 (`blackboard-adapter`); dialectic 1
(`parallel-processor`); pineal 1 (`projection`). **Zero P5-A files appear in `recon-data.json uncertainFiles`.**

> **No `self-model` file crosses in any package** except aurora's internal self-model files (LIVE). `mnemic-field/self-model/*`
> stays in `@cassicore/mnemic-field` (P4). `context-repo/projection.ts` (a **different** P5 sibling, in constellation's
> vendor tree) is NOT a P5-A file — see the inbound sweep note in §4.

---

# PART A — `@cassicore/thalamus`

**Source:** `core/intelligence/thalamus/` (11 top-level + `slots/` 6 = 17 live files). **0 DEAD, 0 UNCERTAIN.**
`gate-ab.test.ts` (Stage-2 A/B test) ports to `tests/` (host-wired — see §6 Open Flag 8).

## A1. Live-set (17)

Top-level `src/*.ts` (11): `index.ts` (184.99 KB — biggest), `gate-composite.ts`, `compressor.ts`, `distiller.ts`,
`types.ts`, `classifier.ts`, `scorer.ts`, `drop-receipt.ts`, `thalamus-store.ts`, `cross-session-index.ts` (14.9 KB),
`temporal.ts`.
`src/slots/*.ts` (6, depth 1): `index.ts`, `user-slot.ts`, `tool-result-slot.ts`, `tool-call-slot.ts`, `system-slot.ts`,
`assistant-slot.ts`.

**Discovery surface — `ThalamusModule` (`index.ts:442`, verbatim):**
```ts
export class ThalamusModule extends BaseCognitiveModule {
  readonly name = 'thalamus'
  readonly priority = 85
```
`thalamus/index.ts` also imports `BaseCognitiveModule` from `../base/cognitive-module.js`, `CorticalField` from
`../cortex/index.js`, `MnemicField`/`EngramCreate`/`ExpertKind`/`MnemicRetrievalHit`/`cosineSimilarity`/
`SentenceFeature`/`scoreSentencesByOverlap`/`SelfModelField` from `../mnemic-field/**`, `LocusBridge` from
`../locus-bridge/index.js`, `SIGNAL_TYPE_PHRASES`/`EPISTEMIC_SHIFT_PHRASES`/`WORK_UNIT_ANNOTATION_PHRASES` from
`../phrase-prototypes.js`. **Not in the daemon registry skip-set (daemon.ts:2033-2051)** → auto-discovered by
`IntelligenceRegistry.discover()`. **P7 note:** the package `index.ts` MUST keep `export class ThalamusModule` (the
scanner's prototype-chain walk to `BaseCognitiveModule` from foundation), plus re-export `CrossSessionTopicIndex`
(cross-session-index) and the slot/scorer surface the host and helix re-point to.

## A2. Rewrite table (thalamus — per-depth prefixes)

All 17 files land mirroring source. Vendor prefix: **top-level `./vendor/…`, depth-1 `slots/` → `../vendor/…`**.
Foundation + sibling published packages → package specifiers (no relative prefix). Internal `./X.js`/`../` mirrored.

| original specifier | dest | class | consumers (symbols) |
|---|---|---|---|
| `../../../types/interfaces.js` (depth 0) **and** `../../../types/interfaces.js` (slots use same 3-up) | `@cassicore/foundation` | foundation | index, compressor, cross-session-index, distiller, scorer, thalamus-store, drop-receipt? (via scorer/types) — `ILogger`, interfaces. **Only `interfaces` is imported by thalamus.** |
| `../base/cognitive-module.js` | `@cassicore/foundation` | foundation | index (`BaseCognitiveModule`) |
| `../phrase-prototypes.js` | `@cassicore/foundation` | foundation | index, scorer (`SIGNAL_TYPE_PHRASES`, `EPISTEMIC_SHIFT_PHRASES`, `WORK_UNIT_ANNOTATION_PHRASES`) |
| `../../utils/paths.js` | `@cassicore/foundation` | foundation | thalamus-store (`getDataDir`) |
| `../cortex/index.js` | `@cassicore/cortex-pineal-dialectic` | same-phase sibling | index (`CorticalField` — type) |
| `../mnemic-field/index.js` | `@cassicore/mnemic-field` | P4 published | index, scorer (`MnemicField`) |
| `../mnemic-field/types.js` | `@cassicore/mnemic-field` | P4 published | index, types (`EngramCreate`, `ExpertKind`, `MnemicRetrievalHit`) |
| `../mnemic-field/cortex.js` | `@cassicore/mnemic-field` | P4 published | index (`cosineSimilarity` — **RUNTIME**) |
| `../mnemic-field/engram-decomposer.js` | `@cassicore/mnemic-field` | P4 published | index (`scoreSentencesByOverlap` RUNTIME, `SentenceFeature` type) |
| `../mnemic-field/self-model/self-model-field.js` | `@cassicore/mnemic-field` | P4 published | index (`SelfModelField` — type) |
| `../locus-bridge/index.js` (index) **and** `../locus-bridge/types.js` (types) | `./vendor/core/intelligence/locus-bridge/{index,types}.js` | vendor→`@cassicore/lamina` | index (`LocusBridge`), types (`BridgeFocus`) — type |
| `../workspace/cognitive-signal.js` (scorer, gate-composite, all 6 slots) | `./vendor/core/intelligence/workspace/cognitive-signal.js` (top-level) / `../vendor/…` (slots) | vendor→`@cassicore/workspace` | `SystemLuminanceScore`, `CognitiveSignal` — type |
| `../embeddings/embedding-service.js` | `./vendor/core/intelligence/embeddings/embedding-service.js` | vendor→`@cassicore/embeddings` | cross-session-index (`EmbeddingService` — type) |
| `../embeddings/reranker-service.js` | `./vendor/core/intelligence/embeddings/reranker-service.js` | vendor→`@cassicore/embeddings` | compressor, distiller (`getRerankerService` — **RUNTIME**) |
| `../../pipeline/turn/overflow.js` (classifier, compressor, distiller, drop-receipt, scorer, tool-result-slot, user-slot) | top-level `./vendor/core/pipeline/turn/overflow.js` / slots `../vendor/…` | vendor→`@cassicore/pipeline` | `hasQuestionResult`, `buildToolUseMapFromMessages` — **RUNTIME** |
| `./types.js`, `./classifier.js`, `./scorer.js`, `./gate-composite.js`, `./compressor.js`, `./distiller.js`, `./temporal.js`, `./thalamus-store.js`, `./slots/index.js` | unchanged (internal, mirrored) | internal | all top-level ↔ slots |
| slots `../types.js`, `../scorer.js`, `../classifier.js` | unchanged (internal, mirrored) | internal | slots → top-level |
| `node:crypto`, `node:fs`, `node:path` | unchanged | builtin | index, thalamus-store |
| `better-sqlite3` | unchanged (npm dep) | npm | thalamus-store |

### A2.1 Rewrite-pair tally (thalamus)
- **Foundation (`@cassicore/foundation`): 4** unique targets (interfaces, base/cognitive-module, phrase-prototypes, utils/paths).
- **Same-phase sibling (`@cassicore/cortex-pineal-dialectic`): 1** (`../cortex/index.js` → package).
- **P4 published (`@cassicore/mnemic-field`): 5** (index, types, cortex, engram-decomposer, self-model/self-model-field).
- **Vendor stub: 5 unique targets** (locus-bridge/{index,types}, workspace/cognitive-signal, embeddings/{embedding-service,reranker-service}, pipeline/turn/overflow) — 2 are RUNTIME (`getRerankerService`, overflow helpers), 3 type-only.
- **Internal (unchanged, mirrored): 0 rewrite pairs** (all `./` + `../` preserved).
- **Builtins/npm (unchanged): 0.**
- **Total rewrite pairs (thalamus): 15 unique targets.**

> **RUNTIME vendor stubs (P2 Open Flag-5 / P4 Open Flag-8 pattern):** `getRerankerService` (compressor/distiller
> call it) and `hasQuestionResult`/`buildToolUseMapFromMessages` (pipeline/turn/overflow.js — called by classifier,
> compressor, distiller, drop-receipt, scorer, tool-result-slot, user-slot) must be **faithful self-contained copies**,
> not `throw` stubs. Re-point to `@cassicore/embeddings` + `@cassicore/pipeline` at P6 via the repoint log.

---

# PART B — `@cassicore/aurora`

**Source:** `core/intelligence/aurora/` (51 non-test source files = **42 LIVE + 9 DEAD**). **0 UNCERTAIN.**
Self-model cluster is **internal** (no separate dir). Many `.test.ts` files port to `tests/`.

## B1. Live-set (42)

Top-level `src/*.ts` (28 LIVE): `index.ts` (97.85 KB — 2nd biggest), `larql-provider.ts` (61.53 KB),
`self-model-knowledge.ts`, `concept-self-awareness.ts`, `inference-trace.ts`, `self-narrative-renderer.ts`,
`types.ts`, `claustrum.ts`, `state-projector.ts`, `coherence-checker.ts`, `reverie-reasoning-observer.ts`,
`persistence.ts`, `overlay-layer.ts`, `prism.ts`, `meditation-seeder.ts`, `counterfactual-engine.ts`,
`cassi-spec-channel.ts`, `diversity-floor.ts`, `claustrum-recorder.ts`, `auto-scheduler.ts`,
`modification-chain-audit.ts`, `gap-detector.ts`, `saturation-detector.ts`, `trace-replay.ts`,
`trace-replay-types.ts`, `welfare-aggregator.ts`, `event-journal.ts`, `refusal-channel.ts`.

`src/{composition,calibration,projection,coherence-detector}/` (14 LIVE, depth 1):
- `composition/` (5): `store.ts`, `types.ts`, `rule-evaluator.ts`, `parser.ts`, `predicate.ts`
- `calibration/` (4): `manager.ts`, `store.ts`, `drift.ts`, `types.ts`
- `projection/` (2): `vector-projection.ts`, `active-gate-annotation.ts`
- `coherence-detector/` (3): `index.ts`, `types.ts`, `gate-weights.ts` (**`probe-set.ts` DEAD, excluded**)

**DEAD (excluded, 9):** `fine-tune-gating.ts`, `mnemic-steering-bridge.ts`, `nla-bridge.ts`, `affect-calibration.ts`,
`affect-probes/v1.ts`, `affect-signature-store.ts`, `claustrum-snapshot.ts`, `coherence-detector/probe-set.ts`,
`welfare-probe-set.ts`.

**Discovery surface — `class Aurora` (`index.ts:234`, verbatim) — NOT a BaseCognitiveModule subclass:**
```ts
export class Aurora {
  private logger: ILogger
  private claustrum: Claustrum
  private projector: StateProjector
```
**Explicitly wired** (daemon.ts: line 30 `createIntelligence`; daemon calls `this.intelligence.aurora.setModelProvider(...)`,
`(__loadVindex)`, `setMnemicField`). **Not in registry skip-set and not registry-scanned** (no BaseCognitiveModule
subclass in `aurora/index.ts`). **P7 note:** the package `index.ts` keeps `export class Aurora` + the full sibling
re-export list (Claustrum, StateProjector, LarqlKnowledgeProvider, AuroraPersistence, GapDetector, CoherenceChecker,
ReverieReasoningObserver, SubstrateModificationAudit, CassiSpecChannel, OverlayLayer, EventJournal, WelfareAggregator,
TraceReplayEngine, SaturationDetector, DiversityFloor, SelfNarrativeRenderer, RefusalChannel, CounterfactualEngine + all
`export type` groups — lines 109-233). The daemon and `intelligence/index.ts` type against `aurora?: import('./aurora/index.js').Aurora`.

## B2. Rewrite table (aurora — per-depth prefixes)

Mirror source subdirs. Vendor prefix: **top-level `./vendor/…`, depth-1 subdirs `../vendor/…`**.

| original specifier | dest | class | consumers |
|---|---|---|---|
| `../../../types/interfaces.js` (top) **and** `../../../../types/interfaces.js` (subdirs) | `@cassicore/foundation` | foundation | ~30 files (`ILogger`) |
| `../../utils/paths.js` (top) **and** `../../../utils/paths.js` (subdirs) | `@cassicore/foundation` | foundation | index, persistence, cassi-spec-channel, auto-scheduler, gap-detector, event-journal, modification-chain-audit (`getDataDir`) |
| `../phrase-prototypes.js` | `@cassicore/foundation` | foundation | coherence-checker, reverie-reasoning-observer (`COHERENCE_MISMATCH_PHRASES`, `REVERIE_HAS_INSIGHT_PHRASES`) |
| `../mnemic-field/cortex.js` | `@cassicore/mnemic-field` | P4 | index, claustrum (`Cortex` — type) |
| `../mnemic-field/types.js` (top) **and** `../../mnemic-field/types.js` (subdirs) | `@cassicore/mnemic-field` | P4 | index, types, larql-provider, claustrum, prism, counterfactual-engine, self-model-knowledge, composition/parser+predicate+types (`Affect`, `AffectLabel`, `EngramType`, `SynapseType`, `Engram`, `ResonantAffectSignal`…) |
| `../mnemic-field/affect.js` (top) **and** `../../mnemic-field/affect.js` (subdirs) | `@cassicore/mnemic-field` | P4 | larql-provider, counterfactual-engine (`affectSimilarity`, `resolveLabel` — **RUNTIME**) |
| `../mnemic-field/index.js` (top) **and** `../../mnemic-field/index.js` (subdirs) | `@cassicore/mnemic-field` | P4 | coherence-checker, reverie-reasoning-observer, self-model-knowledge, index (`MnemicField` — type) |
| `../constellation/observer-memory-bridge.js` | `@cassicore/constellation` | P0 existing | claustrum (`ClaustrumInsightSink`, `ObserverInsight` — type) |
| `../memory-bridge/portal-bridge.js`, `../memory-bridge/resonant-affect.js`, `../memory-bridge/dream-engine.js` | `./vendor/core/intelligence/memory-bridge/{portal-bridge,resonant-affect,dream-engine}.js` | vendor→`@cassicore/*-memory-bridge` (P5 TBD) | index, types, claustrum (`PortalBridge`, `ResonantAffectSignal`, `DreamDiscovery` — type) |
| `../embeddings/embedding-service.js` (self-model-knowledge) | `./vendor/core/intelligence/embeddings/embedding-service.js` | vendor→`@cassicore/embeddings` | `getEmbeddingService` — **RUNTIME** |
| `../embeddings/reranker-service.js` | `./vendor/core/intelligence/embeddings/reranker-service.js` | vendor→`@cassicore/embeddings` | (if any aurora file calls it — check at exec) — **RUNTIME** |
| `./types.js` + all `./X.js` top-level siblings + `./projection/*`, `./calibration/*`, `./composition/*`, `./coherence-detector/*`, and `../X.js` from subdirs | unchanged (internal, mirrored) | internal | intra-aurora |
| `node:path`, `node:fs` (`node:fs`/`node:fs/promises`), `node:crypto`, `module` (`createRequire`) | unchanged | builtin | many |
| `better-sqlite3` | unchanged (npm dep) | npm | prism, persistence, auto-scheduler, gap-detector, event-journal, refusal-channel, modification-chain-audit, composition/store, calibration/store |

### B2.1 Rewrite-pair tally (aurora)
- **Foundation: 3** (interfaces, utils/paths, phrase-prototypes).
- **P4 published (`@cassicore/mnemic-field`): 4** (cortex, types, affect, index).
- **Existing (`@cassicore/constellation`): 1** (observer-memory-bridge).
- **Vendor stub: 5 unique targets** (memory-bridge/{portal-bridge,resonant-affect,dream-engine}, embeddings/{embedding-service,reranker-service}) — 2 RUNTIME (`getEmbeddingService`, `getRerankerService`), 3 type-only.
- **Internal (unchanged, mirrored): 0 rewrite pairs. Builtins/npm: 0.**
- **Total rewrite pairs (aurora): 13 unique targets.**

> **Dominant imports — `aurora/index.ts` (97.85 KB):** foundation (`interfaces`, `utils/paths`) + P4 mnemic-field
> (`cortex`, `types`, `index`) + `constellation/observer-memory-bridge` + `memory-bridge/{portal-bridge,resonant-affect,dream-engine}`
> + ~24 internal `./X.js` siblings + `node:path`. ~26 import specifiers; the external set is small. `larql-provider.ts`
> (61.53 KB): foundation `interfaces` + P4 mnemic-field (`types`, `affect`) + internal (`types`, `claustrum-recorder`,
> `overlay-layer`, `projection/vector-projection`) + `module` (createRequire).

---

# PART C — `@cassicore/cortex-pineal-dialectic`

**Sources:** `core/intelligence/{cortex,pineal,dialectic}/`. **26 LIVE** (cortex 9, pineal 8, dialectic 9).
**3 DEAD** (cortex `blackboard-adapter`, pineal `projection`, dialectic `parallel-processor`). **0 UNCERTAIN.**

> **One package, not split — rationale (plan §5-P5 "field-processing cluster"):** the three dirs share the
> "six-region field surface" (CorticalField ↔ pineal identity/facets ↔ dialectic reasoning). Cortex is a pure library
> (no BaseCognitiveModule); pineal is a registry-discovered identity module; dialectic is an explicitly-wired system.
> Combined size ~330 KB across 26 files is squarely in package range; the plan's `@cassicore/cortex` grouping
> (cortex+pineal+dialectic) is adopted with the "pineal-dialectic" name for clarity. **No split needed.** The only intra-package
> cross-cluster edge is dialectic→cortex (`../cortex/index.js`), which stays valid under the mirrored-subdir layout.

## C1. Live-set

`src/cortex/` (9): `index.ts` (19.8 KB), `types.ts`, `tract.ts`, `mnemic-bridge.ts`, `region.ts`, `session.ts`, `signal.ts`, `commissure.ts`, `dynamics.ts`. **DEAD: `blackboard-adapter.ts`.**

`src/pineal/` (8): `facet.ts`, `index.ts` (10.2 KB), `store.ts` (13.5 KB), `types.ts`, `skill-parser.ts`, `skill-loader.ts`, `seed.ts`, `assembler.ts`. **DEAD: `projection.ts`.**

`src/dialectic/` (9): `consolidated-processor.ts` (22.8 KB), `index.ts` (29.4 KB), `dialectic-voice-base.ts`, `serenity.ts` (26.3 KB), `yin.ts`, `yang.ts`, `prompt-templates.ts`, `thought-formatter.ts`, `engine.ts` (24.7 KB). **DEAD: `parallel-processor.ts`.** *(`DIALECTIC_OPTIMIZATION.md` is a doc, not code — do NOT migrate.)*

> **Cortex/pineal/dialectic naming-collision note:** `types/dialectic.ts` + `types/dialectic-engine.ts` are LIVE type
> files ALREADY migrated to **`@cassicore/foundation` in P1** (P1 rows 10-11). This phase migrates the **RUNTIME dialectic
> module dir** (`core/intelligence/dialectic/*`), whose files import `../../../types/dialectic.js` / `dialectic-engine.js`
> → `@cassicore/foundation`. **Do not conflate:** foundation owns the type files; this package owns the runtime
> observers/engine.

**Discovery surfaces (mixed — quoting all three):**
```ts
// pineal/index.ts:31 — registry-discovered
export class PinealModule extends BaseCognitiveModule { readonly name = 'pineal'; readonly priority = 90 }
// cortex/index.ts:79 — explicit (library; NOT BaseCognitiveModule); daemon calls:
//   this.intelligence.cortex.startOscillation() / .setAffectRegister() / .setConsolidationCallback()
export class CorticalField { readonly sensory: Region; readonly association: Region; readonly executive: Region }
// dialectic/index.ts:159 — explicit (skip-set daemon.ts:2033 'dialectic'; implements IDialecticSystem, NOT BaseCognitiveModule)
export class DialecticSystem implements IDialecticSystem { readonly name = 'dialectic' }
export const createDialecticSystem = (logger, config?) => new DialecticSystem(logger, config)
```
**P7 note:** package `index.ts` re-exports `PinealModule`, `CorticalField` (+ cortex submodule re-exports `Region`,
`TractEngine`, `CortexSession`, `Commissure`, `createConsolidationBridge`, `signalToEngram`, `oscillate`, and the
create/signal helpers — cortex preserves its full barrel), `DialecticSystem`/`createDialecticSystem` + dialectic voice
factories (`createYangObserver`, `createYinObserver`, `createSerenity`, `DialecticEngine`/`createEngine`,
`formatDialecticAsThoughts`), and the pineal/facet/skill surface. Preserve every export name (constellation/helix/
daemon/admin-api type against them).

## C2. Rewrite table (cortex-pineal-dialectic — per-depth prefixes)

All 26 files land at **depth 1** under `src/{cortex,pineal,dialectic}/`. Vendor prefix is uniformly **`../vendor/…`**
from every file. Foundation + published sibling packages → package specifiers.

| original specifier | dest | class | consumers |
|---|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | foundation | cortex/index, pineal/{assembler,facet,index,skill-loader,skill-parser,store}, dialectic/{consolidated-processor,dialectic-voice-base,engine,index,serenity,yang,yin} (`ILogger`, `IEventBus`) |
| `../../../types/runtime.js` | `@cassicore/foundation` | foundation | dialectic/{consolidated-processor,dialectic-voice-base,engine,index,serenity,yang,yin} (`IProvider`) |
| `../../../types/dialectic.js` | `@cassicore/foundation` | foundation | dialectic/{consolidated-processor,engine,index,serenity,yang,yin,parallel-processor(dead)} + thought-formatter? — `IDialecticSystem`, `DialecticResult`, `YangOutput`, `YinOutput`, `ISerenity`, `IYangObserver`, `IYinObserver`… |
| `../../../types/dialectic-engine.js` | `@cassicore/foundation` | foundation | dialectic/thought-formatter (`DialecticStructuredResult`) |
| `../../../types/intelligence.js` | `@cassicore/foundation` | foundation | dialectic/{consolidated-processor,index,parallel-processor(dead)} (`IMemory`) |
| `../../../types/flux-team.js` | `@cassicore/foundation` | foundation | dialectic/index (`BlackboardChannel`) |
| `../../config/system-settings.js` | `@cassicore/foundation` | foundation | dialectic/{serenity,yang,yin} (`getModelSpec`) |
| `../base/cognitive-module.js` (pineal) | `@cassicore/foundation` | foundation | pineal/index (`BaseCognitiveModule`) |
| `../../utils/paths.js` (pineal store) | `@cassicore/foundation` | foundation | pineal/store (`getDataDir`) |
| `../mnemic-field/types.js` | `@cassicore/mnemic-field` | P4 published | cortex/{index,mnemic-bridge,types}, pineal/facet (`Affect`, `AffectLabel`, `EngramType`, `Engram`, `ConsolidationTarget`…) |
| `../mnemic-field/affect.js` (cortex) | `@cassicore/mnemic-field` | P4 published | cortex/index (`AffectRegister` — type) |
| `../mnemic-field/index.js` | `@cassicore/mnemic-field` | P4 published | cortex/index, pineal/{facet,index} (`MnemicField` — type) |
| `../flux-team/global-blackboard-registry.js` | `@cassicore/flux-team` | P3 published | dialectic/index (`GlobalBlackboardRegistry` — type) |
| `../cortex/index.js` (dialectic) | **unchanged** — `../cortex/index.js` (intra-package, mirrored `src/dialectic/` → `src/cortex/`) | internal cross-cluster | dialectic/index (`CorticalField` — type) |
| `../module-session-registry.js` | `../vendor/core/intelligence/module-session-registry.js` | vendor→`@cassicore/workspace` | dialectic/{consolidated-processor,dialectic-voice-base,index} (`ModuleSessionRegistry` — type) |
| `../shared/posture-store.js` | `../vendor/core/intelligence/shared/posture-store.js` | vendor→`@cassicore/workspace` | dialectic/{serenity,yang,yin} (`composeSystemPrompt` — **RUNTIME**) |
| `../../utils/activity-timeout.js` | `../vendor/core/utils/activity-timeout.js` | vendor→`@cassicore/utils` | dialectic/dialectic-voice-base (`ActivityTimeout` — **RUNTIME**) |
| `./types.js`, `./region.js`, `./tract.js`, `./signal.js`, `./session.js`, `./dynamics.js`, `./commissure.js`, `./mnemic-bridge.js` (cortex) | unchanged (internal, mirrored) | internal | cortex |
| pineal `./store.js`, `./facet.js`, `./skill-loader.js`, `./skill-parser.js`, `./seed.js`, `./types.js`, `./index.js` | unchanged | internal | pineal |
| dialectic `./yang.js`, `./yin.js`, `./serenity.js`, `./engine.js`, `./thought-formatter.js`, `./prompt-templates.js`, `./dialectic-voice-base.js`, `./consolidated-processor.js` | unchanged | internal | dialectic |
| `node:fs`, `node:path`, `node:crypto` | unchanged | builtin | pineal/{store,skill-parser}, dialectic/index |
| `better-sqlite3` | unchanged (npm dep) | npm | pineal/store, dialectic/index |

### C2.1 Rewrite-pair tally (cortex-pineal-dialectic)
- **Foundation: 10** unique targets (interfaces, runtime, dialectic, dialectic-engine, intelligence, flux-team, config/system-settings, base/cognitive-module, utils/paths).
- **P4 published (`@cassicore/mnemic-field`): 3** (types, affect, index).
- **P3 published (`@cassicore/flux-team`): 1** (global-blackboard-registry).
- **Vendor stub: 3 unique targets** (module-session-registry, shared/posture-store, utils/activity-timeout) — 2 RUNTIME (`composeSystemPrompt`, `ActivityTimeout`), 1 type.
- **Internal cross-cluster (unchanged): 1** (dialectic `../cortex/index.js` — free under mirrored layout). **Internal same-dir: 0 rewrite pairs.**
- **Builtins/npm: 0.**
- **Total rewrite pairs (cortex-pineal-dialectic): 17 unique targets.**

---

# PART D — `@cassicore/cognitive-feed`

**Source:** `core/intelligence/cognitive-feed/` (**14 LIVE, 0 DEAD, 0 UNCERTAIN**). Flat `src/`.

## D1. Live-set (14)

`src/*.ts` (all top-level, flat): `index.ts` (45.1 KB), `message-formatter.ts` (65.2 KB — the plan's "message-formatter
65 KB"), `window-manager.ts` (27.9 KB), `event-curator.ts` (24.6 KB), `delivery-batcher.ts` (15.7 KB),
`general-chat-handler.ts` (13.8 KB), `module-chat-handler.ts` (12.8 KB), `telegram-client.ts` (9.6 KB),
`rate-limiter.ts` (8.5 KB), `event-accumulator.ts` (7.9 KB), `topic-manager.ts` (7.4 KB), `steering-handler.ts` (6.7 KB),
`delivery-types.ts` (4.9 KB), `message-tracker.ts` (3.2 KB).

**Discovery surface — `CognitiveFeedModule` (`index.ts:132`, verbatim):**
```ts
export class CognitiveFeedModule extends BaseCognitiveModule {
  readonly name = 'cognitive-feed'
  readonly priority = 5 // Low priority — observation only, runs after everything else
```
**Not in the daemon registry skip-set → registry-discovered.** **P7 note:** package `index.ts` keeps
`export class CognitiveFeedModule` + re-export the handler/tools surface the host wires.

## D2. Rewrite table (cognitive-feed — flat `./vendor/…` prefix)

| original specifier | dest | class | consumers |
|---|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | foundation | index, delivery-batcher, event-accumulator, topic-manager, steering-handler, rate-limiter, module-chat-handler, general-chat-handler, telegram-client, window-manager (`ILogger`) |
| `../../../types/events.js` | `@cassicore/foundation` | foundation | index, event-curator, message-formatter (`RuntimeEvent`) |
| `../base/cognitive-module.js` | `@cassicore/foundation` | foundation | index (`BaseCognitiveModule`) |
| `../../tools/interactive-tool-session.js` | `./vendor/core/tools/interactive-tool-session.js` | vendor→`@cassicore/tools` (P6) | index (`InteractiveToolSession`, `splitForTelegram`, `ToolDefinition` — **RUNTIME**) |
| `../module-session-registry.js` | `./vendor/core/intelligence/module-session-registry.js` | vendor→`@cassicore/workspace` | module-chat-handler (`ModuleSessionRegistry`, `ModuleRegistration` — type) |
| `./telegram-client.js`, `./topic-manager.js`, `./event-curator.js`, `./message-formatter.js`, `./message-tracker.js`, `./steering-handler.js`, `./general-chat-handler.js`, `./module-chat-handler.js`, `./rate-limiter.js`, `./event-accumulator.js`, `./delivery-batcher.js`, `./window-manager.js`, `./delivery-types.js` | unchanged (internal, flat) | internal | all siblings |
| `node:os`, `node:path`, `node:fs`, `node:fs/promises` | unchanged | builtin | topic-manager, window-manager, general-chat-handler |

### D2.1 Rewrite-pair tally (cognitive-feed)
- **Foundation: 3** (interfaces, events, base/cognitive-module).
- **Vendor stub: 2 unique targets** (tools/interactive-tool-session — **RUNTIME**; module-session-registry — type).
- **Internal (flat, unchanged): 0 rewrite pairs. Builtins: 0.**
- **Total rewrite pairs (cognitive-feed): 5 unique targets.**

> **RUNTIME vendor stub:** `InteractiveToolSession`/`splitForTelegram`/`ToolDefinition` (tools/interactive-tool-session.js)
> are called by `CognitiveFeedModule` at runtime → **faithful self-contained copy**, re-point to `@cassicore/tools` at P6.

---

## 3. Destination layout proposal (4 packages)

```
packages/thalamus/
  package.json        # name "@cassicore/thalamus", type module, deps: @cassicore/foundation, @cassicore/mnemic-field,
                      #   @cassicore/cortex-pineal-dialectic, better-sqlite3
  tsconfig.json  vitest.config.ts
  src/
    index.ts          # ThalamusModule (BaseCognitiveModule subclass — registry contract) + barrel
    gate-composite.ts  compressor.ts  distiller.ts  types.ts  classifier.ts  scorer.ts
    drop-receipt.ts  thalamus-store.ts  cross-session-index.ts  temporal.ts
    slots/ index.ts  user-slot.ts  tool-result-slot.ts  tool-call-slot.ts  system-slot.ts  assistant-slot.ts
    vendor/ core/ pipeline/turn/overflow.js              # RUNTIME (hasQuestionResult, buildToolUseMapFromMessages)
                intelligence/ embeddings/{reranker-service,embedding-service}.js   # reranker RUNTIME
                              locus-bridge/{index,types}.js                        # type
                              workspace/cognitive-signal.js                        # type

packages/aurora/
  package.json        # name "@cassicore/aurora", type module, deps: @cassicore/foundation, @cassicore/mnemic-field,
                      #   @cassicore/constellation, better-sqlite3
  src/
    index.ts          # class Aurora + full sibling re-export barrel (lines 109-233)
    larql-provider.ts  self-model-knowledge.ts  concept-self-awareness.ts  inference-trace.ts  self-narrative-renderer.ts
    types.ts  claustrum.ts  state-projector.ts  coherence-checker.ts  reverie-reasoning-observer.ts  persistence.ts
    overlay-layer.ts  prism.ts  meditation-seeder.ts  counterfactual-engine.ts  cassi-spec-channel.ts  diversity-floor.ts
    claustrum-recorder.ts  auto-scheduler.ts  modification-chain-audit.ts  gap-detector.ts  saturation-detector.ts
    trace-replay.ts  trace-replay-types.ts  welfare-aggregator.ts  event-journal.ts  refusal-channel.ts
    composition/ store.ts  types.ts  rule-evaluator.ts  parser.ts  predicate.ts
    calibration/ manager.ts  store.ts  drift.ts  types.ts
    projection/ vector-projection.ts  active-gate-annotation.ts
    coherence-detector/ index.ts  types.ts  gate-weights.ts
    vendor/ core/ intelligence/ memory-bridge/{portal-bridge,resonant-affect,dream-engine}.js   # type
                                embeddings/{embedding-service,reranker-service}.js              # RUNTIME

packages/cortex-pineal-dialectic/
  package.json        # name "@cassicore/cortex-pineal-dialectic", type module, deps: @cassicore/foundation,
                      #   @cassicore/mnemic-field, @cassicore/flux-team, better-sqlite3
  src/
    index.ts          # re-export PinealModule, CorticalField+barrel, DialecticSystem/createDialecticSystem + voices
    cortex/ index.ts  types.ts  tract.ts  mnemic-bridge.ts  region.ts  session.ts  signal.ts  commissure.ts  dynamics.ts
    pineal/  index.ts  facet.ts  store.ts  types.ts  skill-parser.ts  skill-loader.ts  seed.ts  assembler.ts
    dialectic/ index.ts  consolidated-processor.ts  dialectic-voice-base.ts  serenity.ts  yin.ts  yang.ts
               prompt-templates.ts  thought-formatter.ts  engine.ts
    vendor/ core/ intelligence/module-session-registry.js        # type
                              shared/posture-store.js            # RUNTIME composeSystemPrompt
                    utils/activity-timeout.js                    # RUNTIME ActivityTimeout

packages/cognitive-feed/
  package.json        # name "@cassicore/cognitive-feed", type module, deps: @cassicore/foundation
  src/
    index.ts          # CognitiveFeedModule (BaseCognitiveModule subclass — registry contract) + barrel
    message-formatter.ts  window-manager.ts  event-curator.ts  telegram-client.ts  topic-manager.ts
    steering-handler.ts  rate-limiter.ts  message-tracker.ts  module-chat-handler.ts  general-chat-handler.ts
    delivery-batcher.ts  delivery-types.ts  event-accumulator.ts
    vendor/ core/ tools/interactive-tool-session.js              # RUNTIME
                intelligence/module-session-registry.js          # type
```

**Internal-import consequences (all satisfied by the mirrored/flat layouts):**
- `thalamus` top-level ↔ `slots/` both use `../types.js`/`./types.js` etc. — valid under mirror. `slots/index.js` exported
  from `thalamus/index.ts` via `./slots/index.js` unchanged.
- `aurora` subdirs use `../types.js`, `../../mnemic-field/…` — mirrored (subdirs at depth 1 keep `../` and `../../` intact).
- `cortex-pineal-dialectic` dialectic's `../cortex/index.js` resolves to `src/cortex/index.js` (same package).
- `cognitive-feed` flat — every `./X.js` sibling unchanged.

---

## 4. Inbound-stub sweep (P5-A repoint-inbound) — workspace packages, NOT D:

Grepped every `packages/*/src/vendor/` for stubs shadowing P5-A dirs. **Three owner packages hold such stubs: `helix`,
`constellation`; `foundation` has NONE.** (`flux-team`, `mini-helix` have none either.) All re-point to `@cassicore/*` at
this phase and are deleted.

### 4.1 helix (`packages/helix/src/vendor/core/intelligence/`)
| helix stub | exported symbols (consumers) | re-point to |
|---|---|---|
| `aurora/index.ts` | `Aurora` — helix-conductor:42, helix-pipeline:64, helix-posture-runner:42 | `@cassicore/aurora` |
| `thalamus/index.ts` | `ThalamusModule` — helix-pipeline:125 (inline), helix-posture-runner:229 (inline), index.ts:149/177/265 | `@cassicore/thalamus` |
| `thalamus/cross-session-index.ts` | `CrossSessionTopicIndex` — helix-pipeline:128, helix-posture-runner:231, helix-synapse:4 | `@cassicore/thalamus` |

### 4.2 constellation (`packages/constellation/src/vendor/`)
| constellation stub | exported symbols (consumers) | re-point to |
|---|---|---|
| `aurora/index.ts` | `Aurora` — meditation/index:56 | `@cassicore/aurora` |
| `cortex/index.ts` | `CorticalField` — meditation/index:53 | `@cassicore/cortex-pineal-dialectic` |
| `thalamus/index.ts` | `ThalamusModule` — meditation/index:55, solo-runner:17 | `@cassicore/thalamus` |
| `thalamus/cross-session-index.ts` | `CrossSessionTopicIndex` — cluster-observer-layer:5, constellation-pipeline:71 (**value**), corpus-observer-layer:5, solo-runner:61 (inline) | `@cassicore/thalamus` |
| `thalamus/types.ts` | **no src consumer found** (present in vendor tree, unreferenced) — verify before deletion (Open Flag 7) | delete (or `@cassicore/thalamus`) |

### 4.3 `context-repo/projection.ts` — NOT a P5-A file
`constellation/src/vendor/context-repo/projection.ts` (`EngramLike`, consumed by `meditation/index.ts:149`) is a
**different P5 sibling** (`core/intelligence/context-repo/`), NOT `pineal/projection.ts` (which is DEAD) nor any P5-A
dir. **Out of this phase's repoint scope** — record for the P5 context-repo/auxiliary grouping.

> **Inbound-repoint is a REQUIRED P5-A executor task** (mirrors P4 §3.1 / Open Flag 7): 8 stub files across helix (3) +
> constellation (5) → 3 packages (`@cassicore/thalamus`, `@cassicore/aurora`, `@cassicore/cortex-pineal-dialectic`) +
> 1 verify (thalamus/types). Sequence: publish the three packages → swap each consumer's imports → delete stubs →
> re-typecheck helix + constellation. **`cognitive-feed` has NO inbound stubs in any package** (no package imports it).

---

## 5. Known-hard items

### 5a. Registry-discovery contract vs explicit wiring (the P5 P7-note)
Two of the four packages are registry-discovered (`thalamus`, `cognitive-feed` + `PinealModule` inside the
cortex-pineal-dialectic package); `Aurora`/`CorticalField`/`DialecticSystem` are explicit. Every package's `src/index.ts`
MUST preserve its exact exported surface so `IntelligenceRegistry.discover()` (which loads `<dir>/index.ts` and walks the
prototype chain to `BaseCognitiveModule` from foundation) and the daemon's `createIntelligence()`/`bootIntelligencePostPipeline()`
manual wiring both keep working unchanged. **Do NOT rename/reroute `ThalamusModule`, `PinealModule`, `CognitiveFeedModule`,
`Aurora`, `CorticalField`, `DialecticSystem`.** The scanner only auto-discovers registry packages when the overhaul session's
P7 host swaps the directory-scan for explicit wiring — per plan §3e.1.

### 5b. RUNTIME vendor stubs (must be faithful copies, not `throw`)
From all four packages: `overflow.js` `hasQuestionResult`/`buildToolUseMapFromMessages` (thalamus), `getRerankerService`/
`getEmbeddingService` (thalamus/aurora), `composeSystemPrompt` (dialectic), `ActivityTimeout` (dialectic),
`InteractiveToolSession`/`splitForTelegram` (cognitive-feed). These are called on live code paths; a bare `throw` breaks
build/runtime. **Default: port exact self-contained copies** into the vendor stubs; re-point to the owning packages via the
repoint log (`@cassicore/pipeline`, `@cassicore/embeddings`, `@cassicore/workspace`, `@cassicore/utils`, `@cassicore/tools`).

### 5c. `better-sqlite3` + data-dir seam
Stores in every package open `better-sqlite3` and write under foundation's `ports/paths getDataDir()`: `thalamus-store.ts`
(schema v3), `pineal/store.ts` (`system-state.db`), `dialectic/index.ts`, and 7 aurora stores (prism, persistence,
auto-scheduler, gap-detector, event-journal, refusal-channel, modification-chain-audit + composition/store + calibration/store).
**Add `better-sqlite3` as an npm dep to each package; read the data dir via `@cassicore/foundation`'s `getDataDir`** — do not
change store internals (P6/P7 persistence port decision is out of scope).

### 5d. `larql-provider.ts` native need (`createRequire(import.meta.url)`)
`aurora/larql-provider.ts` uses `createRequire` to load the `cassi-larql` N-API addon (`node_modules/cassi-larql/index.node`).
Plan §4.6 does NOT migrate `packages/larql`. **Default: make `cassi-larql` a documented peerDependency** (or resolve
package-relatively with a clear error), same as P4 Open Flag-3 handling of `cassi-larql`. Mark `[VERIFY]` the provider's
graceful path when the addon is absent (Aurora must still boot without vindex).

### 5e. Largest files and dominant imports
- **`thalamus/index.ts` (184.99 KB):** foundation (`interfaces`, `base/cognitive-module`, `phrase-prototypes`),
  `@cassicore/cortex-pineal-dialectic` (`CorticalField`), `@cassicore/mnemic-field` (`index`, `types`, `cortex`/`cosineSimilarity`,
  `engram-decomposer`, `self-model/self-model-field`), `@cassicore/lamina` (`LocusBridge`, via repoint), internal
  (`./scorer,./gate-composite,./compressor,./distiller,./temporal,./slots/index,./classifier,./thalamus-store`), `node:crypto`.
- **`aurora/index.ts` (97.85 KB):** foundation (`interfaces`, `utils/paths`), `@cassicore/mnemic-field` (`cortex`, `types`,
  `index`), `@cassicore/constellation` (`observer-memory-bridge`), `memory-bridge/{portal-bridge,resonant-affect,dream-engine}`
  (vendor→P5), ~24 internal `./X.js` siblings, `node:path`.
- **`larql-provider.ts` (61.53 KB) / `message-formatter.ts` (65.2 KB, cognitive-feed):** larql-provider = foundation +
  mnemic-field + internal + `module`; message-formatter = foundation `events` + internal (`event-curator`, `window-manager`) —
  message-formatter is a pure formatter, zero external runtime.

---

## 6. Open flags (max 8 — defaults recommended)

1. **`self-model` grouping correction — aurora/* only, no `core/intelligence/self-model`.** The plan's `@cassicore/aurora`
   scope listed `aurora/* + core/intelligence/self-model/*`. That dir does NOT exist; aurora's self-model cluster is internal.
   **Default: `@cassicore/aurora = aurora/*` (42 files) as spec'd here.** `mnemic-field/self-model/*` stays P4.
   `[VERIFY]` the overhaul session hasn't created a top-level `core/intelligence/self-model` since recon.
2. **`@cassicore/cortex-pineal-dialectic` combined package vs the plan's `@cassicore/cortex`.** The plan table names the
   package `@cassicore/cortex` (cortex + pineal + dialectic). I propose the clearer combined name
   `@cassicore/cortex-pineal-dialectic`; the boundary (three runtime dirs, one package) is unchanged. **Default: adopt the
   descriptive name** (or keep `@cassicore/cortex` if consumers/inbound-repoint tables already reference it — confirm once).
3. **Dialectic's `composeSystemPrompt` (shared/posture-store) + `ActivityTimeout` are RUNTIME vendored symbols (Open-Flag-5
   pattern).** Both are called on live dialectic paths. **Default: port exact self-contained copies** into
   `vendor/core/intelligence/shared/posture-store.js` and `vendor/core/utils/activity-timeout.js`; re-point to
   `@cassicore/workspace` (P5 other group) and `@cassicore/utils` (P6). `[VERIFY]` the copied impls match source at execution.
4. **`thalamus` `utils/paths getDataDir` + `better-sqlite3` + `pipeline/turn/overflow` are host/pipeline seams.** 
   `thalamus-store.ts` opens `better-sqlite3` (schema v3) under `getDataDir()`; classifier/scorer/distiller call the
   `pipeline/turn/overflow` helpers. **Default: keep `better-sqlite3` as a thal dep + foundation `getDataDir`; port overflow.js
   as a faithful runtime copy (re-point to `@cassicore/pipeline` at P6).** Flag if the P6 pipeline package should own overflow.
5. **`larql-provider.ts` native addon (Open Flag 5d).** `@cassicore/aurora` needs `cassi-larql` (N-API, not migrated, plan §4.6).
   **Default: peerDependency + package-relative resolution + graceful fallback** (Aurora runs without vindex — confirmed
   daemon.ts:310-320 handles absent vindex). `[VERIFY]` the provider's no-addon path.
6. **`gate-ab.test.ts` (thalamus) is host-wired.** It imports `../workspace/cognitive-signal.js` (a future-package seam) +
   `./scorer` + `./gate-composite`. **Default: port to `tests/host-wired/` quarantine** (plan §6) until `@cassicore/workspace`
   lands, then re-point; count as quarantined, not passing. Report actual ported-vs-quarantined vitest counts with P5-A DONE.
7. **`constellation/src/vendor/thalamus/types.ts` stub appears unreferenced.** No `src` consumer imports `vendor/thalamus/types.js`
   (only the index + cross-session-index stubs are consumed; `types` is present in the constellation vendor tree).
   **Default: inspect before deletion** — if genuinely unreferenced, delete it during the inbound re-point; if used via a
   path the grep missed, re-point to `@cassicore/thalamus`. `[VERIFY]` at execution.
8. **Test surface for the four packages.** Recon lists `tests/core/intelligence/aurora/**`, `cortex/**`, `pineal/**`,
   `dialectic/**`, `subconscious/**`, `embeddings/**` + cognitive-feed as the ported test trees (plan §5-P5). Aurora carries
   a large in-dir `.test.ts` set (persistence, overlay-layer, prism, meditation-seeder, counterfactual-engine, cassi-spec,
   claustrum, coherence-checker, diversity-floor, coherence-detector, larql-provider, calibration, projection, auto-scheduler,
   saturation-detector, trace-replay, welfare-aggregator, refusal-channel, modification-chain-audit, event-journal, gap-detector,
   self-narrative-renderer, etc.) plus `tests/**` outside. **Default: port self-contained in-dir tests into each package's
   `tests/` (they mock loggers, self-contained); host-wired ones (importing `core/daemon`/admin/mcp/workspace seams) to
   `tests/host-wired/`.** `dialectic` is skip-set-wired and its tests that need a mounted provider → host-wired. Report actual
   counts per package (plan §6).

---

## §7. Executor playbook (P5-A later wave — verbatim, mirrors P1–P4 §6)

1. **History import (four independent packages — sequence separately, same phase).** For each package temp-clone D:
   (`git clone --no-checkout --no-local`) and run filter-repo with its path set + `--path-rename` to `packages/<name>/src`:
   - `--path core/intelligence/thalamus --path-rename core/intelligence/thalamus:packages/thalamus/src`
   - `--path core/intelligence/aurora --path-rename core/intelligence/aurora:packages/aurora/src`
   - `--path core/intelligence/cortex --path core/intelligence/pineal --path core/intelligence/dialectic
     --path-rename core/intelligence/cortex:packages/cortex-pineal-dialectic/src/cortex
     --path-rename core/intelligence/pineal:packages/cortex-pineal-dialectic/src/pineal
     --path-rename core/intelligence/dialectic:packages/cortex-pineal-dialectic/src/dialectic`
     (`--path` matched in one filter-repo pass keeps a single shared history fragment → one import commit; the three
     renames + `--mailmap` mirror P4 §6 step 1. **Alternative:** three separate filter-repo runs if a single fragment is
     unwieldy — any order, one commit each.)
   - `--path core/intelligence/cognitive-feed --path-rename core/intelligence/cognitive-feed:packages/cognitive-feed/src`
   Fetch + splice (add/add, take `--theirs` for conflicted import files), verify `git log --follow`, commit each import.
   **NEVER merge a stale fragment — re-verify the D: paths have not moved/been rewired (plan §3d; the overhaul session is live).**
2. **Copy the LIVE files** per Part A–D into the dest trees mirroring source subdirs (`.ts` extensions, `.js` import
   specifiers verbatim). **Do NOT copy the 12 DEAD** (§0 tally); **do NOT copy `DIALECTIC_OPTIMIZATION.md`** (doc) or
   `gate-ab.test.ts`/aurora `.test.ts` files into `src/`.
3. **Apply the rewrite pairs per file — a GLOBAL replace per specifier, with the DEPTH-CORRECT prefix per file (P2/P4
   lesson (a) — no bulk sed).**
   - **thalamus:** 4 foundation → `@cassicore/foundation`; 1 → `@cassicore/cortex-pineal-dialectic`; 5 → `@cassicore/mnemic-field`;
     5 vendor (top-level `./vendor/…`, slots `../vendor/…`).
   - **aurora:** 3 foundation; 4 → `@cassicore/mnemic-field`; 1 → `@cassicore/constellation`; 5 vendor (per-depth).
   - **cortex-pineal-dialectic:** 10 foundation; 3 → `@cassicore/mnemic-field`; 1 → `@cassicore/flux-team`; 3 vendor
     (`../vendor/…` uniform — all depth 1). Note dialectic `../cortex/index.js` stays (internal cross-cluster, mirrored).
   - **cognitive-feed:** 3 foundation; 2 vendor (`./vendor/…` flat).
   - Only after each owning package's `@cassicore/*` dep is present (foundation/P4-mnemic-field/P3-flux-team/P0-constellation
     are all already published; `@cassicore/cortex-pineal-dialectic` publish BEFORE `@cassicore/thalamus` typechecks — Open Flag 2
     ordering). Do NOT touch builtins/npm/internal `./X.js`/`../X.js`.
4. **Write the vendor stubs** per §3 trees. Type-only stubs = faithful type surface. **RUNTIME stubs (Open Flags 3/5b) =
   exact-copy self-contained ports**: `pipeline/turn/overflow.js`, `embeddings/{reranker,embedding}-service.js`,
   `shared/posture-store.js`, `utils/activity-timeout.js`, `tools/interactive-tool-session.js`. Do NOT wire the
   `field-encoder`/`memory-bridge` journal hooks (overhaul coordination, plan §7) — type stubs only for memory-bridge.
5. **Write each `src/index.ts` preserving ALL export names** (§A1/B1/C1/D1 discovery surfaces). Do NOT rename any export.
6. **Package scaffold** per package: `package.json` (`@cassicore/<name>`, `type: module`, deps per §3, incl. `better-sqlite3`;
   aurora peerDeps note for `cassi-larql` — Open Flag 5), tsconfig (rootDir src/outDir dist/declaration true), vitest.config.ts,
   `.gitignore` (no README needed unless a source DEPRECATED marker exists — **none of the P5-A dirs are deprecated-in-source**).
7. **Inbound re-point (§4, REQUIRED).** After `@cassicore/thalamus` + `@cassicore/aurora` + `@cassicore/cortex-pineal-dialectic`
   land: re-point helix's 3 stubs + constellation's 5 stubs → the real packages; delete the stubs; delete
   `constellation/src/vendor/thalamus/types.ts` if unreferenced (Open Flag 7); re-typecheck helix + constellation.
   cognitive-feed has NO inbound stubs.
8. **Tests.** Port in-dir + `tests/**` self-contained suites per package (Open Flag 8); `gate-ab.test.ts` + host-wired
   suites → `tests/host-wired/` quarantine. Report actual ported-vs-quarantined vitest counts per package.
9. `npm run typecheck` (`tsc --noEmit`) in each package + the 2 re-pointed consumers; fix ONLY mechanical path errors. Then
   `npm test` for each ported suite (skip project-wide suites). Do NOT `npm install` beyond noting deps; do NOT commit to D:.
10. **Commit discipline (plan §3c):** per package, (1) history-splice import commit, (2) rewrite-delta commit (this table +
    vendor + package.json + barrels), (3) inbound re-point commit(s) across helix/constellation. Keep import/rewrite/re-point
    in SEPARATE commits; verify `git log --follow` before each rewrite commit. Do NOT commit to D:; workspace push is handled
    by the session owner (parallel sessions commit there — leave this file untracked).

### Files with no external or relocated imports (copy verbatim, zero rewrites — prelim, verify at exec)
`thalamus/temporal.ts`, `thalamus/types.ts`, `aurora/{diversity-floor,welfare-aggregator,saturation-detector,event-journal,
refusal-channel,self-narrative-renderer,concept-self-awareness,overlay-layer,trace-replay-types}.ts`, `cortex/{types,signal,
tract,region,session,commissure,dynamics}.ts`, `pineal/{seed,types}.ts`, `cognitive-feed/{message-formatter,event-accumulator}.ts`
(likely; `message-formatter` imports foundation `events` + internal, so verify). Confirm each against the §2 tables at execution.

---

## §8. Reply summary (for the session owner)

- **Live-set counts (99 migrated + 12 DEAD-excluded, 0 uncertain):**
  - `@cassicore/thalamus`: **17** (11 top-level + 6 `slots/`); 0 DEAD; `gate-ab.test.ts` → host-wired.
  - `@cassicore/aurora`: **42** (28 top-level + 14 in `composition/calibration/projection/coherence-detector`); **9 DEAD**
    (incl. `mnemic-steering-bridge` — the dead self-model file); **self-model cluster is internal** (grouping corrected).
  - `@cassicore/cortex-pineal-dialectic`: **26** (cortex 9 + pineal 8 + dialectic 9); **3 DEAD** (`cortex/blackboard-adapter`,
    `pineal/projection`, `dialectic/parallel-processor`).
  - `@cassicore/cognitive-feed`: **14**; 0 DEAD.
- **Rewrite-pair totals by class (unique targets; global per-specifier replace at exec):**
  - foundation (`@cassicore/foundation`): **20** (thalamus 4 · aurora 3 · cortex-pineal-dialectic 10 · cognitive-feed 3).
  - same-phase sibling real package (`@cassicore/cortex-pineal-dialectic`): **1** (thalamus `../cortex`).
  - published-package real imports (non-foundation): `@cassicore/mnemic-field` **12** (5+4+3) · `@cassicore/constellation` **1**
    (aurora observer-memory-bridge) · `@cassicore/flux-team` **1** (dialectic global-blackboard-registry).
  - vendor stub (`./vendor/` or `../vendor/` per depth): **15** (thalamus 5 · aurora 5 · cpd 3 · cognitive-feed 2) — **7 RUNTIME**
    (overflow, reranker, embedding, composeSystemPrompt, ActivityTimeout, interactive-tool-session) + **8 type**.
  - internal cross-cluster (unchanged, mirrored `../cortex/`): **1**. internal same-dir: **0**. builtins/npm: **0**.
  - **Total unique rewrite-target pairs: 51** (20+1+12+1+1+15+1).
- **Dest layouts:** four package trees in §3 (thalamus `src/`+`slots/`; aurora `src/`+4 subdirs; cpd `src/{cortex,pineal,dialectic}/`;
  cognitive-feed flat `src/`). Per-depth vendor prefixes: §2.
- **Inbound-stub sweep (repoint-inbound P5-A):** **8 stub files across 2 owner packages** → 3 real packages. **helix** (3):
  `aurora/index` (3 consumer files), `thalamus/index` (4 consumers), `thalamus/cross-session-index` (3 consumers).
  **constellation** (5): `aurora/index` (1), `cortex/index` (1), `thalamus/index` (2), `thalamus/cross-session-index` (4),
  `thalamus/types` (**unreferenced — verify/delete**). **foundation/flux-team/mini-helix: none.** **cognitive-feed: none.**
  `context-repo/projection.ts` in constellation is a DIFFERENT P5 sibling, not P5-A.
- **Open flags (8, defaults recommended):** §6 — (1) aurora=self-model-internal grouping correction, (2) cpd package name,
  (3) dialectic runtime vendor stubs, (4) thal storage/pipeline seams, (5) larql native peer dep, (6) gate-ab host-wired test,
  (7) constellation `thalamus/types.ts` unreferenced stub, (8) test surface / host-wired split.
