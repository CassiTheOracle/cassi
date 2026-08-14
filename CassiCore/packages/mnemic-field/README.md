# @cassicore/mnemic-field

The Mnemic Field memory subsystem extracted from CassiCore — the engram + synaptic
store, kindling/consolidation engines, spatial index, self-model and knowledge
fields, and the Lightning indexer-training cluster. Standalone TypeScript ESM
module.

**Status:** LIVE (P4 landed). Imports resolve to `@cassicore/foundation` for the
shared substrate (`ILogger`, `IProvider`, `IEventBus`, `getDataDir`,
phrase-prototypes) and to this package's own `src/vendor/` stub tree for the
sibling intelligence modules (embeddings, reranker, field-encoder, dream-engine,
aurora, cortex, reverie) that are owned by later phases (P5+).

## Coordination note (overhaul session)

The overhaul session is RE-WIRING Mnemic Field into a journal with
`MindFieldEncoder` hooks at store/update/delete/connect/spike/consolidate.

**Agreed default (boundary-first):** this package lands FIRST. The overhaul
session will add their journal hooks behind our **store port** LATER. The
`MindFieldEncoder` type is vendored here as a **type stub**
(`src/vendor/core/intelligence/field-encoder/types.ts`) — **no journal hooks are
implemented in P4**. `src/ports/store.ts` exposes the forward-looking
`MnemicFieldStore` interface with an unoccupied `onWrite` observer seam for that
future handshake. **Do not wire `onWrite` to anything until the overhaul session
provides the encoder — the seam is left deliberately unoccupied.**

## Native / peer dependencies

- `better-sqlite3` + `lmdb` — the SQLite (and optional LMDB) store backends.
  `feature-index-lmdb.ts` (LIVE) requires `lmdb`; the constructor falls back to
  the SQLite `FeatureIndex` when LMDB open throws (index.ts:632-638), so the
  LMDB path is optional at runtime.
- `cassi-larql` — **optional peerDependency** (the Rust nested repo; the native
  `index.node` N-API addon). NOT shipped by this package. `backfill-worker.ts`
  resolves it package-relatively via `createRequire(import.meta.url)`; the host
  (or the D: daemon at P7) provides it. The backfill path is not exercised by the
  ported suite.

## Tests

Ported tests live in `tests/` (counted in `npm test`). `tests/host-wired/` holds
quarantined tests that depend on the overhaul session's `field-encoder` runtime
(`field-encoder.test.ts`) and cannot run until those packages land.

### Inbound re-point log

Publishing `@cassicore/mnemic-field` replaces every mnemic-field vendor stub in
the workspace packages (foundation `core/intelligence/mnemic-field/edge-relators.ts`,
helix `mnemic-field/{index,types}.ts`, constellation `vendor/mnemic-field/*`) with
real `@cassicore/mnemic-field` imports. Those stubs are DELETED; consumers import
this package.
