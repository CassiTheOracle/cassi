# @cassicore/pipeline

Agent conversation pipeline extracted from CassiCore `core/pipeline/*`.
History-preserved import splice.

## Surface

- `adapter/SessionPipeline.ts` — the pipeline entry (depends on the workspace
  `buildSystemPrompt` — vendored placeholder pending `@cassicore/workspace` at
  P7 host).
- `intelligence/BackgroundProcessor.ts` + `IntelligenceLayer.ts`.
- `session/SessionManager.ts` + `session/stores/{MemoryStore,SQLiteStore}.ts`.
- `turn/ContextWindow.ts`, `MessageBuilder.ts`, `ToolLoop.ts`, `TurnHandler.ts`,
  `overflow.ts`.

`ToolLoop.ts` consumes `@cassicore/embeddings` (`CHARS_PER_TOKEN`) and
`@cassicore/thalamus/classifier` (`isWriteTool`/`isReadTool`/`isShellTool`/
`shortenPath`); `SQLiteStore` uses `better-sqlite3`.

## Vendored

- `src/vendor/core/workspace/loader.ts` — `buildSystemPrompt` (runtime), the
  `core/workspace/loader.js` seam. Re-pointed to `@cassicore/workspace`/host at
  P7.

Depends on `@cassicore/foundation`, `@cassicore/embeddings`,
`@cassicore/thalamus`, `better-sqlite3`.
