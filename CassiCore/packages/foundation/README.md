# @cassicore/foundation

The **shared substrate** extracted from CassiCore into a standalone TypeScript ESM package —
the single package every later `@cassicore/*` module imports instead of re-vendoring the common
types, settings, phrase sets, and module base class (see `../MODULARIZATION.md`).

## What this package ships

- **`types/`** — the complete live `types/*` surface (19 files) that the whole D: repo types
  against: `interfaces.ts` (the `IEventBus`/`ILogger`/`IConfig`/`IntelligenceModule` set),
  `events.ts`, `runtime.ts`, `model-routing.ts`, `flux-team.ts`, `cassi-agent.ts`, and more.
- **`config/`** — `MODEL_DEFAULTS` / `SYSTEM_SETTINGS` (self-contained).
- **`phrases/`** — the phrase sets (`phrase-prototypes.ts`).
- **`base/`** — `BaseCognitiveModule` (the abstract base `IntelligenceRegistry.discover()` scans
  for), `ModuleModelConfig`, `DEFAULT_MODULE_MODEL_CONFIG`, and the `infer`/`inferJSON` helpers.
- **`ports/paths.ts`** — a parameterized CassiCore-root/data-dir port: `getDataDir()`/`getCassiCoreHome()`
  default to the current `~/.cassicore` resolution order, and a resolver can be injected via
  `setRootResolver()`.
- **`vendor/`** — **type stubs only** (no runtime). Faithful type-surface placeholders for
  external (non-live-set) targets consumed by the migrated files. Each resolves to a real
  `@cassicore/*` package in a later phase, at which point the import is re-pointed and the stub
  deleted (see the Repoint log in `P1-foundation-migration-table.md`).

## Build / test

```bash
npm install            # installs better-sqlite3 (runtime); typescript, vitest (dev)
npm run typecheck      # tsc --noEmit            → 0 errors
npm run build          # tsc → dist/
npm test               # vitest run
```

> **P1 test note:** per the migration table, P1 carries no standalone test files for these types.
> There is deliberately no test suite yet; P1's DONE criterion is the package building and
> type-checking clean so downstream packages (P2+) can build against it.
