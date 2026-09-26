# @cassicore/thalamus

Message curation subsystem extracted from CassiCore with git-history preservation.

Migrated from `core/intelligence/thalamus/` (D: read-only source). Registry-discovered:
`ThalamusModule extends BaseCognitiveModule` (name `thalamus`, priority 85).

## What it does

- **Message curation** — `MessageLuminanceScorer` scores each message across six
  luminance axes (novelty, urgency, relevance, source-credibility,
  cognitive-resonance, strategic-importance) and assembles a context-window-budgeted
  curated view of the session.
- **Compression / distillation** — reranker-driven tool-result compression and chunk
  distillation keep long sessions within the context window.
- **Slots** — per-message-type processing (`user`, `tool_call`, `tool_result`,
  `assistant`, `system`) with metadata attachment and budget-aware assembly.
- **Cross-session topic memory** — `CrossSessionTopicIndex` archives summarized topic
  clusters across sessions.

## Host wiring

The module is **registry-discovered** — the host (daemon's `IntelligenceRegistry.discover()`)
loads `src/index.ts` and walks the prototype chain to `BaseCognitiveModule` from
`@cassicore/foundation`. The package `index.ts` preserves the full exported surface
(`ThalamusModule`, `CrossSessionTopicIndex`, and the slot/scorer surface) so host
wiring and prior inbound consumers keep working unchanged.

## Dependencies

- `@cassicore/foundation` — `ILogger`, `BaseCognitiveModule`, phrase prototypes, `getDataDir`.
- `@cassicore/mnemic-field` — `MnemicField` and engram/memory types and helpers.
- `better-sqlite3` — `thalamus-store` (schema v3) under foundation's `getDataDir()`.

## Vendor stubs

Several cross-subsystem imports are vendored (re-pointed to their owning published
packages via the repoint log as they land):

- `vendor/core/intelligence/{locus-bridge,workspace,embeddings,aurora,cortex,pineal}/` —
  type-only stubs for `LocusBridge`, `CognitiveSignal`, `EmbeddingService`, and the
  turn-2 siblings (`CorticalField`, `FacetManager`, `PinealAssembler`, `Aurora`).
- The former `vendor/core/pipeline/turn/overflow.js` runtime copy is gone — the
  overflow/classification helpers (`hasQuestionResult`,
  `buildToolUseMapFromMessages`) moved to **`@cassicore/utils`** at P5 (the
  `@cassicore/pipeline` package was deleted). `getRerankerService` remains a faithful
  local vendored copy at `vendor/core/intelligence/embeddings/reranker-service.js`.
