# @cassicore/constellation

The **Constellation multi-agent subsystem** extracted from CassiCore into a standalone
TypeScript ESM package. First module of the CassiCore modularization
workstream (see [../MODULARIZATION.md](../MODULARIZATION.md)).

## Status — EXTRACTED, INTEGRATED

- All **87 constellation source files** are copied into `src/` with import rewrites per
  [EXTRACTION-PLAN.md](EXTRACTION-PLAN.md), and the package **type-checks with zero errors**
  (`npm run typecheck`), **builds cleanly** (`npm run build` → `dist/`), and **passes its
  unit-test subset** (`npm test`).
- CassiCore daemon integrations are isolated behind typed **ports** in `src/ports/` (each
  ships a `not connected` default; a host wires the ones it needs).
- Not yet wired into the CassiCore daemon or any ohmypi host.

## Build / test

```bash
npm install          # installs better-sqlite3, uuid (runtime); typescript, vitest (dev)
npm run typecheck    # tsc --noEmit            → 0 errors
npm run build        # tsc → dist/
npm test             # vitest run
```

**`npm test` state (integration):**
- **Passing (16 files, ~375 tests):** `tests/topology-graph`, `topology-graph-critical`,
  `topology-perf`, `embedding-cache`, `embedding-cache-critical`, `fast-decomposer`,
  `locus`, `corpus`, `corpus-enforcement`, `corpus-utils`, `decomposition-tracker`,
  `decomposition-workflow`, `constellation-guidance-provider`,
  `constellation-template-capabilities`, `self-edit`, `signal-pattern-digest`,
  `elevated-patterns-persistence`, plus `src/observer-memory-bridge.test.ts`.
- **Skipped (not ported / broken at load — require daemon wiring not in the package):**
  `corpus-strategy`, `corpus-llm-health`, `helix-goal-lamina`, `helix-tool-allocation`,
  `meditation-cooldown`, `meditation-feedback`, `phrase-prototype-integration`,
  `territory-bridge`, `brainstem-bridge`, `brainstem-enforcement`, and the
  `tests/constellation/topology/{brainstem-bridge,cluster-tracker,embedding-cache,
  gravity-engine,link-manager,topology-graph}` subdir tests. Each imports modules that were
  never extracted (e.g. `thalamus/scorer`, `lamina/lamina-store`,
  `cassi-agent/base-posture-runner`, `runtime/audit`, `workflow` runtime) or hits surviving
  type-stub mismatches in vendored runtime paths. See the integration report.

## Ports concept

The package runs standalone and is plugin-ready. Every bit of CassiCore daemon integration
is isolated behind a **port** in `src/ports/`:

| port | what it replaces | default |
|---|---|---|
| `helix-pipeline` | `runHelixPipeline` + `BrainstemMiniHelix` | real stub class / fn throw `not connected` |
| `code-analysis-context` | `prepareContext` | throws `not connected` |
| `mcp-consolidated-tools` | solo-runner's consolidated MCP tools | schema getters functional; executors throw |
| `paths` | `utils/paths.js` `getDataDir` | functional (`~/.cassicore`, root injectable) |
| `gaming-mode` | `isGamingMode` | functional (in-memory flag) |
| `workspace-luminance` | `extractKeywords` / `keywordOverlap` | functional |

Hosts re-export these from the package barrel (`src/index.ts`, appended ports block).
Future ohmypi adaptation = supplying real implementations at these seams → a **wiring**
problem, not a surgery problem. Other CassiCore units are either **vendored** into
`src/vendor/` (faithful copies) or covered by **type stubs** under `src/vendor/types/` and
`src/vendor/<area>/`.
