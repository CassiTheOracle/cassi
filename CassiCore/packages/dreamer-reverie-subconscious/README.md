# @cassicore/dreamer-reverie-subconscious

Reflective cognition subsystems extracted from CassiCore (history-preserved) into a
standalone TypeScript ESM package. Owns the **dreamer** (offline dream cycles),
**reverie** (slow-path insights + retrieval labeling), and **subconscious**
(anomaly / system-model observers) modules.

## Status

Migrated at **P5 Group B** of the cassi-mind plan. Live code (17 files under `src/`
across `dreamer/`, `reverie/`, `subconscious/`) carries its cassicore git history via
an import splice. Two kinds of import rewiring were applied:

1. **`@cassicore/foundation`** — the shared substrate (types, system-settings,
   `BaseCognitiveModule`). Foundation specifiers became the real package.
2. **`@cassicore/mnemic-field`** / **`@cassicore/lamina-locus-bridge`** — landed
   packages: reverie's `MnemicField`/`Engram`/`cosineSimilarity` and
   `LaminaField` type imports re-point to the real packages.
3. **`src/vendor/**`** — faithful type stubs (and a few runtime stubs) for
   subsystems not yet migrated (`reasoning-bank`, `runtime/audit`, `cortex`,
   `module-session-registry`, `session-digest`, `gaming-mode`).

### Vendor stubs — repoint log

The authoritative mapping of every `src/vendor/**` stub to its owning
`@cassicore/*` package and re-point phase is **`P5b-group-b-migration-table.md
§A3.2`** (committed at the workspace root alongside the scaffold). Vendored
**runtime** symbols (not type-only) are:

- `withStep` / `resolveProvenance` / `currentStep` — AsyncLocalStorage attribution
  from `core/runtime/audit/step-context.ts` (faithful self-contained copy).
- `isGamingMode` — the gaming-mode in-memory flag (faithful, self-contained;
  the `rootLogger` dependency is replaced by a minimal local no-op logger).

`reasoning-bank`, `cortex`, `module-session-registry`, `session-digest` are
type-only stubs used as injected/field types; `AuditStore` is carried as a type
in source (it is never instantiated by this package — only `withStep` and friends
are called at runtime).

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # ported vitest suite (host-wired excluded)
```

Ports that require a daemon runtime live under `tests/host-wired/` and are not
counted in `npm test`.
