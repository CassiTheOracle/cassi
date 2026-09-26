# @cassicore/embeddings

Embedding + reranker services and shared posture/token utilities extracted from
CassiCore (history-preserved) into a standalone TypeScript ESM package.

## Status

Migrated at **P5 Group B** of the cassi-mind plan. Live code (7 files under
`src/` across `embeddings/` and `shared/`) carries its cassicore git history via
an import splice. Rewiring applied:

1. **`@cassicore/foundation`** — the shared substrate (`ILogger`). The
   embedding/reranker services are self-contained HTTP clients (vLLM `/v1/embeddings`
   and zerank `/v1/rerank` / vLLM `/v1/completions`), env-driven (`EMBEDDING_SERVER_URL`,
   `RERANKER_SERVER_URL`, etc.) — the endpoint config stays host-side.
2. **`src/vendor/core/intelligence/gaming-mode.ts`** — faithful runtime copy of
   `isGamingMode` (used by background-worker).
3. **`src/index.ts`** — **packager-written barrel** (the source `embeddings/` dir
   has no `index.ts`; Open Flag 7). Re-exports `getEmbeddingService`,
   `getRerankerService`, `SqliteVectorIndex`/`getVectorIndex`, the
   `embeddings/types` surface, and the shared `composeSystemPrompt`,
   `estimateTokens`/`estimateChars`/`CHARS_PER_TOKEN`.

### Vendor stubs — repoint log / inbound sweep

Authoritative mapping: **`P5b-group-b-migration-table.md §E3.1`**. Helix +
constellation re-point their runtime `shared/posture-store.ts`,
`shared/token-estimation.ts`, and `embeddings/{embedding-service,types}.ts`
stubs to this package (RUNTIME symbols `getEmbeddingService`,
`composeSystemPrompt`, `estimateTokens` come from here).

`background-worker.ts` is a tick class (not a subprocess entry); the daemon holds
it via `getBackgroundEmbeddingWorker()` at P7.

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # vitest suite (host-wired excluded)
```

The embeddings suite has no standalone D: source tests; it is exercised via
constellation (`embedding-cache`) and helix consumers that re-point to it.
