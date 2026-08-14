# @cassicore/helix

Helix orchestration subsystem extracted from CassiCore (history-preserved) into a
standalone TypeScript ESM package. Owns the helix posture runners, brainstem,
dialectic channel, work stream, pipeline, telemetry, and the store/journal layers.

## Status

Migrated at **P2** of the cassi-mind plan. Live code (35 files under `src/`) carries its
cassicore git history via an import splice. Two kinds of import rewiring were applied:

1. **`@cassicore/foundation`** — the shared substrate (types, phrase-prototypes,
   `BaseCognitiveModule`, `getDataDir`). Helix imports it as a real package dependency.
2. **`src/vendor/**`** — faithful **type stubs** for runtime subsystems not yet migrated
   (constellation, mini-helix, mnemic-field, aurora, lamina, workspace, thalamus,
   flux-team, cassi-agent, tools, model-pool, utils). These are placeholders; each
   resolves to a real `@cassicore/*` package in a later phase and is then deleted.

### Vendor stubs — repoint log

The authoritative mapping of every `src/vendor/**` stub to its owning `@cassicore/*`
package and re-point phase is the **`P2-helix-migration-table.md §3.1`** (committed at
the workspace root alongside the scaffold). Three vendored symbols are runtime
functions, not type-only:

- `composeSystemPrompt` (`vendor/core/intelligence/shared/posture-store.ts`) and
  `estimateTokens` (`vendor/core/intelligence/shared/token-estimation.ts`) are
  **exact pure copies** of the D: originals — they run, and are self-contained.
- `createMiniHelixSession` (`vendor/core/intelligence/mini-helix/mini-helix-runner.ts`)
  is a **throwing stub** (`not connected`) until `@cassicore/mini-helix` lands at P3.

Do **not** vendor duplicates of foundation symbols: everything helix consumes from the
shared substrate is re-exported by `@cassicore/foundation`'s barrel.

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # ported vitest suite (host-wired excluded)
npm run test:host-wired  # quarantine suite; needs a mounted host
```

Ports that require a daemon runtime (e.g. `helix-wiring.test.ts`) live under
`tests/host-wired/` and are not counted in `npm test`.
