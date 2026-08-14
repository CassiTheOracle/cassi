# @cassicore/mini-helix

Mini-Helix lightweight single-posture agent sessions for Constellation infrastructure
components (Corpus, Brainstem), extracted from CassiCore (history-preserved) into a
standalone TypeScript ESM package. Owns the `MiniHelixRunner`
(`createMiniHelixSession` factory) and the `MiniHelix*` type surface + `MINI_HELIX_DEFAULTS`.

## Status

Migrated at **P3** of the cassi-mind plan. The 3 live files under `src/` carry their
cassicore git history via an import splice. Import rewiring applied:

1. **`@cassicore/foundation`** — the shared substrate (runtime + interface types).
   The runner and types import `ILogger`/`IEventBus` and the runtime `Message`/
   `ContentBlock`/`CompletionChunk`/`CompletionOpts` surface from the P1 foundation package.
2. **`src/vendor/**`** — a single **type-only** stub:
   `src/vendor/core/model-pool/types.ts` (`ModelHandle`, `ModelCompletionOpts`). Mini-helix
   uses `ModelHandle` only as a type (it acquires handles via `handleFactory` and calls
   `stream`/`release`/reads `provider`/`model`). It re-points to `@cassicore/model-pool` at P6.

### Consumer repoint

Publishing `@cassicore/mini-helix` replaces helix's (P2) vendored
`mini-helix/` runner/types stubs: helix now imports `createMiniHelixSession` and the
`MiniHelix*` types from this package. Constellation (Corpus + meditation) also wires via
this package's exports.

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # ported vitest suite (host-wired excluded)
npm run test:host-wired  # quarantine suite; needs a host/other packages mounted
```
