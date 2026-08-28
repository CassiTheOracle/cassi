# @cassicore/training-trust-ledger

Training warehousing + trust ledger extracted from CassiCore (history-preserved)
into a standalone TypeScript ESM package. Owns **training** (`TrainingWarehouse`
ingest/read/store/tag + background tagger worker) and **trust-ledger**
(`TrustLedger` BaseCognitiveModule with a vendored TTL cache).

## Status

Migrated at **P5 Group B** of the cassi-mind plan. Live code (10 files under `src/`
across `training/` and `trust-ledger/`) carries its cassicore git history via an
import splice. Rewiring applied:

1. **`@cassicore/foundation`** — the shared substrate (`ILogger`,
   `BaseCognitiveModule`).
2. **`@cassicore/flux-team`** — landed P3 package: training-tagger's
   `GlobalBlackboardRegistry` type re-points to the real package.
3. **`src/vendor/**`** — a faithful **runtime stub** for `core/utils/ttl-cache`
   (`TTLCache` + `createTTLCache`, a pure in-memory cache used by TrustLedger).

### Vendor stubs — repoint log

The authoritative mapping of every `src/vendor/**` stub to its owning
`@cassicore/*` package is **`P5b-group-b-migration-table.md §C3.1`**. The only
vendored symbol is `TTLCache` (runtime; re-points to `@cassicore/utils` at P6).

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # ported vitest suite (host-wired excluded)
```

Ports that require a daemon runtime live under `tests/host-wired/` and are not
counted in `npm test`.
