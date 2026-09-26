# @cassicore/aurora

Cognitive-state and subspace-reasoning subsystem extracted from CassiCore with
git-history preservation.

Migrated from `core/intelligence/aurora/` (D: read-only source). **Explicitly
wired** — `class Aurora` is NOT a `BaseCognitiveModule` subclass (it is not
registry-discovered). The daemon wires it via `createIntelligence()` and calls
`aurora.setModelProvider(...)`, `(__loadVindex)`, `setMnemicField`.

## What it does

- **Cognitive state** — builds a unified awareness from model knowledge + memory
  (`MentalState`, feature narrative, reasoning-momentum tracking).
- **Self-model knowledge** — embeddings-driven self-knowledge store
  (`self-model-knowledge`), concept self-awareness, inference tracing, self-narrative.
- **Claustrum** — subspace reasoning: `Claustrum` + `ClaustrumRecorder`, state
  projection, coherence checking, provenance-driven counterfactual engine.
- **Persistence** — several `better-sqlite3` stores under foundation's `getDataDir()`.
- **Gating / refusal / welfare** — saturation detector, diversity floor, refusal
  channel, welfare aggregator, event journal, gap detector, auto-scheduler.

## Host wiring

Explicit — the daemon type-checks against `aurora?: import('./aurora/index.js').Aurora`
and manually wires provider/vindex/mnemic-field. The package `index.ts` preserves
the full exported surface: `class Aurora`, `Claustrum`, `StateProjector`,
`LarqlKnowledgeProvider`, `AuroraPersistence`, `GapDetector`, `CoherenceChecker`,
`ReverieReasoningObserver`, `SubstrateModificationAudit`, `CassiSpecChannel`,
`OverlayLayer`, `EventJournal`, `WelfareAggregator`, `TraceReplayEngine`,
`SaturationDetector`, `DiversityFloor`, `SelfNarrativeRenderer`, `RefusalChannel`,
`CounterfactualEngine` + the `export type` groups (lines 109-233 of the source barrel).

## Dependencies

- `@cassicore/foundation` — `ILogger`, `getDataDir`, phrase prototypes.
- `@cassicore/mnemic-field` — `Cortex`, `MnemicField`, engram types, affect helpers.
- `@cassicore/constellation` — `ClaustrumInsightSink`, `ObserverInsight` (type).
- `better-sqlite3` — persistence stores.
- `cassi-larql` (optional peer) — N-API addon for `larql-provider`; Aurora boots
  without a vindex (graceful no-addon path).

## Vendor stubs

- `vendor/core/intelligence/memory-bridge/{portal-bridge,resonant-affect,dream-engine}.ts`
  — type-only stubs (`PortalBridge`, `ResonantAffectSignal`, `DreamDiscovery`);
  re-point to `@cassicore/*-memory-bridge` when those land.
- `vendor/core/intelligence/embeddings/embedding-service.ts` — **runtime** faithful
  copy (`getEmbeddingService`); re-point to `@cassicore/embeddings`.
