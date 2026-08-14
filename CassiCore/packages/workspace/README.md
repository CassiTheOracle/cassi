# @cassicore/workspace

Global Workspace (GWT / blackboard successor) + radiance loop + code-analysis
tooling extracted from CassiCore (history-preserved) into a standalone
TypeScript ESM package.

## Status

Migrated at **P5 Group B** of the cassi-mind plan. Live code (22 files under
`src/` across `workspace/` and `code-analysis/`) carries its cassicore git
history via an import splice. Rewiring applied:

1. **`@cassicore/foundation`** — the shared substrate (`ILogger`, `IEventBus`).
   `GlobalWorkspace` is explicitly wired (not registry-discovered) and injected
   into constellation via `setGlobalWorkspace` at P7.
2. **`src/vendor/**`** — faithful stubs for subsystems not yet migrated:
   `core/intelligence/cortex/index.ts` (`CorticalField`, type) and
   `core/intelligence/constellation/meditation/solo-runner.ts`
   (`runSoloExplorer` RUNTIME — a dynamic `import()` inside radiance-loop's
   `setHandleFactory`; `ToolCallResult` type). The `runSoloExplorer` vendor is a
   real bounded loop (not a throw); it re-points to `@cassicore/constellation`
   at P7 when the constellation barrel expands.

### Vendor stubs — repoint log

Authoritative mapping of every `src/vendor/**` stub to its owning
`@cassicore/*` package: **`P5b-group-b-migration-table.md §D3.1`**.
- `core/intelligence/cortex/index.ts` → `@cassicore/cortex` (P5-A)
- `core/intelligence/constellation/meditation/solo-runner.ts` →
  `@cassicore/constellation` (P7, Open Flag 6)

`code-analysis` is batch tooling (git/schema via `node:child_process` +
`better-sqlite3`) — library usage, no subprocess entries.

## Development

```sh
npm run typecheck   # tsc --noEmit
npm run build       # emit dist/
npm test            # ported vitest suite (host-wired excluded)
```

Ports that require a daemon runtime live under `tests/host-wired/` and are not
counted in `npm test`.
