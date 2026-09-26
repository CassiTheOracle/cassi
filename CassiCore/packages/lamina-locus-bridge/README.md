# @cassicore/lamina-locus-bridge

Lamina field + locus bridge extracted from CassiCore (history-preserved) into a
standalone TypeScript ESM package. Owns **lamina** (`LaminaField`/`LaminaStore`,
the persistent provenance-attributed lamina with SQLite backing) and
**locus-bridge** (`LocusBridge` context curator / history scorer / spark
extractor / window assembler).

## Status

Migrated at **P5 Group B** of the cassi-mind plan. Live code (12 files under `src/`
across `lamina/` and `locus-bridge/`) carries its cassicore git history via an
import splice. Rewiring applied:

1. **`@cassicore/foundation`** — the shared substrate (`ILogger`, `getDataDir`).
2. **`src/vendor/**`** — faithful type stubs and **runtime stubs** for subsystems
   not yet migrated (`runtime/audit`, `intelligence/utils/prefixed-id`,
   `intelligence/pineal/types`).

### Vendor stubs — repoint log

The authoritative mapping of every `src/vendor/**` stub to its owning
`@cassicore/*` package is **`P5b-group-b-migration-table.md §B3.1`**. Vendored
**runtime** symbols (faithful self-contained copies, not throws):

- `AuditStore` (better-sqlite3 ledger), `withStep`/`resolveProvenance` (the
  AsyncLocalStorage attribution helpers), and the audit types — from
  `core/runtime/audit/*`.
- `prefixedId` — the timestamp+random+monotonic id generator.

`pineal/types` is a type-only stub (`Domain`/`Facet` used by `pineal-bridge`).

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # ported vitest suite (host-wired excluded)
```

Ports that require a daemon runtime live under `tests/host-wired/` and are not
counted in `npm test`.
