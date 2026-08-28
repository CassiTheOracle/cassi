# P1 — `@cassicore/foundation` — Migration Table (Planning Deliverable)

**Source (READ-ONLY):** `D:\carina\workspaces\cassicore\`
**Destination:** `C:\Users\Carina\workspaces\Cassi\CassiCore\packages\foundation\src\`
**Recon:** `C:\Users\Carina\workspaces\Cassi\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\workspaces\Cassi\CassiCore\CASSI-MIND-PLAN.md` §5-P1, §4
**Date:** 2026-08-13
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the only file written by this drafting pass; it is NOT git-added/committed.

---

## 1. Live-set (files to migrate)

Liveness verdicts are from `recon-data.json` (`deadFiles` / `uncertainFiles`). All 25 files below are
**LIVE** — none appear in `deadFiles` or `uncertainFiles`. `types/` subsystem = 19 alive / 6 dead / 0 uncertain,
consistent with the plan's "19 live" (§3a.8, §5-P1).

| # | source path (D:) | dest path (packages/foundation/src/) | bytes | recon verdict |
|---|---|---|---|---|
| 1 | `types\interfaces.ts` | `types\interfaces.ts` | 7545 | LIVE |
| 2 | `types\runtime.ts` | `types\runtime.ts` | 6602 | LIVE |
| 3 | `types\intelligence.ts` | `types\intelligence.ts` | 10123 | LIVE |
| 4 | `types\model-routing.ts` | `types\model-routing.ts` | 5840 | LIVE |
| 5 | `types\flux-team.ts` | `types\flux-team.ts` | 31874 | LIVE |
| 6 | `types\workflow.ts` | `types\workflow.ts` | 15993 | LIVE |
| 7 | `types\blackboard-search.ts` | `types\blackboard-search.ts` | 9540 | LIVE |
| 8 | `types\cassi-agent.ts` | `types\cassi-agent.ts` | 4274 | LIVE |
| 9 | `types\collect-thoughts.ts` | `types\collect-thoughts.ts` | 7155 | LIVE |
| 10 | `types\dialectic.ts` | `types\dialectic.ts` | 13446 | LIVE |
| 11 | `types\dialectic-engine.ts` | `types\dialectic-engine.ts` | 7115 | LIVE |
| 12 | `types\event-query.ts` | `types\event-query.ts` | 6285 | LIVE |
| 13 | `types\execution-backend.ts` | `types\execution-backend.ts` | 4494 | LIVE |
| 14 | `types\plugin.ts` | `types\plugin.ts` | 13277 | LIVE |
| 15 | `types\replay.ts` | `types\replay.ts` | 1486 | LIVE |
| 16 | `types\session-ref.ts` | `types\session-ref.ts` | 3703 | LIVE |
| 17 | `types\trace.ts` | `types\trace.ts` | 3250 | LIVE |
| 18 | `types\worker-messages.ts` | `types\worker-messages.ts` | 3795 | LIVE |
| 19 | `types\events.ts` | `types\events.ts` | 43060 | LIVE |
| 20 | `core\utils\paths.ts` | `ports\paths.ts` (see §4b) | 3410 | LIVE |
| 21 | `core\config\system-settings.ts` | `config\system-settings.ts` | 20670 | LIVE |
| 22 | `core\intelligence\phrase-prototypes.ts` | `phrases\phrase-prototypes.ts` | 28109 | LIVE |
| 23 | `core\intelligence\base\cognitive-module.ts` | `base\cognitive-module.ts` | 21989 | LIVE |
| 24 | `core\intelligence\base\model-config.ts` | `base\model-config.ts` | 4769 | LIVE |
| 25 | `core\intelligence\base\inference.ts` | `base\inference.ts` | 3074 | LIVE |

**Live-set count: 25 files** (19 `types/*` + 6 core/config/base leaves).

> **Note on `types/events.ts` (row 19):** the plan's §5-P1 bullet enumerates 18 of the 19 live types but
> reads "the 19 live"; `recon-data.json` confirms `types/` = **19 alive / 6 dead / 0 uncertain**. The 19th
> is `types/events.ts` (42.1 KB). It is LIVE, it is NOT excluded, and it is REQUIRED by the highest-fanout
> file `types/interfaces.ts` (`import type { EventType, EventOf, Unsubscribe, RuntimeEvent } from './events.js'`)
> and by `types/event-query.ts`. It MUST be migrated in P1. See [VERIFY-1].

**Explicitly EXCLUDED (DEAD — do not migrate):** `types\log-events.ts`, `types\metadata.ts`,
`types\reasoning-chain.ts`, `types\team-dependencies.ts`, `types\team.ts`, `types\lsp.ts`
(confirmed in `recon-data.json deadFiles` as `{'rel': 'types/…'}` for all six).

**UNCERTAIN:** none among the P1 live-set. (Plan §3a.8 / Appendix B-8 flags `backoff.ts` /
`session-serializer.ts` and `cassi-agent/index` as UNCERTAIN — none are in the P1 scope.)

---

## 2. Rewrite table (mechanical string-substitution pairs)

**Mirror rule for vendor type stubs.** Every external (non-P1-live-set) type-only target is reproduced as a
**type stub at `src/vendor/<rel-path-from-D-repo-root>.ts`** (faithful type surface, no runtime), exactly the
Constellation A3 pattern. All files land at one subdirectory depth under `src/`, so the vendor prefix is
uniformly `../vendor/...` from every migrated file.

**Extension rule.** Source keeps its `.js` import specifiers verbatim (source `.ts` files import `.js`); only the
specifier is rewritten, the extension is preserved exactly as written.

**Scope rule (what changes vs what stays).**
- **DO NOT touch** Node builtins (`node:fs`/`node:path`/`node:os`/`node:url`/`crypto`), npm packages
  (`better-sqlite3`), and internal imports that remain valid after relocation (`./X.js` between sibling files
  in the SAME dest dir, `./model-config.js` within `src/base/`, `./interfaces.js` within `src/types/`, etc.).
- **REWRITE** (a) every import resolving OUTSIDE the P1 live-set (→ `../vendor/...` stub), and
  (b) every P1-live-set import whose RELATIVE path changes because its target moved to a different dest dir
  (e.g. `base/cognitive-module.ts` → `../../../types/interfaces.js` becomes `../../types/interfaces.js`).
- Apply only to actual `import` / `import type` / re-export (`export type {…} from '…'`) / inline
  `import('…')` statements — NOT to string/comment content that resembles imports.
- Inline `import('…')` type expressions on listed targets are rewritten identically.

### 2.1 `src/types/*.ts` (19 files)

All rows preserve `.js` extension. **Type-vendored externals resolve to `../vendor/core/...`.**

| source | dest | import rewrites (original → new) |
|---|---|---|
| `interfaces.ts` | `src/types/interfaces.ts` | `./events.js` → unchanged (internal; both in `src/types/`) |
| `runtime.ts` | `src/types/runtime.ts` | (no imports) |
| `intelligence.ts` | `src/types/intelligence.ts` | `./runtime.js` → unchanged; `./session-ref.js` → unchanged; inline `better-sqlite3` → unchanged (npm — add dep); re-export `export type { DreamerConfig } from '../core/intelligence/dreamer/types.js'` → `../vendor/core/intelligence/dreamer/types.js'` |
| `model-routing.ts` | `src/types/model-routing.ts` | (no imports) |
| `flux-team.ts` | `src/types/flux-team.ts` | (no imports) |
| `workflow.ts` | `src/types/workflow.ts` | `./interfaces.js` → unchanged (internal) |
| `blackboard-search.ts` | `src/types/blackboard-search.ts` | `./flux-team.js` → unchanged (internal) |
| `cassi-agent.ts` | `src/types/cassi-agent.ts` | `./runtime.js` → unchanged (internal); `./interfaces.js` (×2 inline) → unchanged; `./model-routing.js` (×2 inline) → unchanged; <br> `import('../core/model-pool/types.js')` (×2) → `import('../vendor/core/model-pool/types.js')`; <br> `import('../core/tools/executor.js')` → `import('../vendor/core/tools/executor.js')`; <br> `import('../core/tools/registry.js')` → `import('../vendor/core/tools/registry.js')`; <br> `import('../core/intelligence/flux-team/plan-handler.js')` → `import('../vendor/core/intelligence/flux-team/plan-handler.js')`; <br> `import('../core/intelligence/flux-team/blackboard.js')` → `import('../vendor/core/intelligence/flux-team/blackboard.js')` |
| `collect-thoughts.ts` | `src/types/collect-thoughts.ts` | `../core/intelligence/thought-observer.js` → `../vendor/core/intelligence/thought-observer.js`; <br> `../core/intelligence/cognitive-bridge.js` → `../vendor/core/intelligence/cognitive-bridge.js` |
| `dialectic.ts` | `src/types/dialectic.ts` | `./runtime.js` (1 static + 5 inline) → unchanged (internal) |
| `dialectic-engine.ts` | `src/types/dialectic-engine.ts` | `./runtime.js` → unchanged (internal) |
| `event-query.ts` | `src/types/event-query.ts` | `./events.js` → unchanged (internal) |
| `execution-backend.ts` | `src/types/execution-backend.ts` | `./runtime.js` → unchanged (internal) |
| `plugin.ts` | `src/types/plugin.ts` | (no imports) |
| `replay.ts` | `src/types/replay.ts` | `../core/testing/verification/scenario-types.js` → `../vendor/core/testing/verification/scenario-types.js` |
| `session-ref.ts` | `src/types/session-ref.ts` | (no imports) |
| `trace.ts` | `src/types/trace.ts` | (no imports) |
| `worker-messages.ts` | `src/types/worker-messages.ts` | (no imports) |
| `events.ts` | `src/types/events.ts` | `./flux-team.js` → unchanged (internal); <br> `../core/intelligence/thought-observer.js` → `../vendor/core/intelligence/thought-observer.js` |

### 2.2 `src/ports/paths.ts` (from `core/utils/paths.ts`)

| source | dest | import rewrites (original → new) |
|---|---|---|
| `core/utils/paths.ts` | `src/ports/paths.ts` | `node:fs` → unchanged; `node:path` → unchanged; `node:os` → unchanged; `node:url` → unchanged. **No repo-relative imports.** |

### 2.3 `src/config/system-settings.ts`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `core/config/system-settings.ts` | `src/config/system-settings.ts` | **(no imports — fully self-contained)** |

### 2.4 `src/phrases/phrase-prototypes.ts`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `core/intelligence/phrase-prototypes.ts` | `src/phrases/phrase-prototypes.ts` | `./mnemic-field/edge-relators.js` → `../vendor/core/intelligence/mnemic-field/edge-relators.js` (type-only: `PhrasePrototypeSet`) |

### 2.5 `src/base/*.ts`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `core/intelligence/base/cognitive-module.ts` | `src/base/cognitive-module.ts` | `./model-config.js` (lines 29–35, 51, 52) → unchanged (internal); `./inference.js` (36–37) → unchanged (internal); <br> `../../../types/events.js` → `../../types/events.js`; <br> `../../../types/intelligence.js` → `../../types/intelligence.js`; <br> `../../../types/model-routing.js` → `../../types/model-routing.js`; <br> `../../../types/interfaces.js` → `../../types/interfaces.js`; <br> `../../../types/runtime.js` → `../../types/runtime.js`; <br> `../../tools/executor.js` → `../vendor/core/tools/executor.js`; <br> `../../tools/registry.js` → `../vendor/core/tools/registry.js`; <br> `../module-session-registry.js` → `../vendor/core/intelligence/module-session-registry.js`; <br> `../flux-team/global-blackboard-registry.js` → `../vendor/core/intelligence/flux-team/global-blackboard-registry.js`; <br> `../workspace/index.js` → `../vendor/core/intelligence/workspace/index.js` |
| `core/intelligence/base/model-config.ts` | `src/base/model-config.ts` | `../../config/system-settings.js` → `../config/system-settings.js`; <br> `../../../types/interfaces.js` → `../../types/interfaces.js` |
| `core/intelligence/base/inference.ts` | `src/base/inference.ts` | `./model-config.js` → unchanged (internal); <br> `../../../types/runtime.js` → `../../types/runtime.js`; <br> `../../../types/interfaces.js` → `../../types/interfaces.js` |

### 2.6 Files with no external-or-relocated imports (copy verbatim, zero rewrites)

Explicitly: `types/runtime.ts`, `types/model-routing.ts`, `types/flux-team.ts`, `types/plugin.ts`,
`types/session-ref.ts`, `types/trace.ts`, `types/worker-messages.ts`, `core/config/system-settings.ts`,
`core/utils/paths.ts` (ported — see §4b).

### 2.7 Rewrite-pair tally

- **Unique rewrite pairs: 25** (source specifier → dest specifier).
  - `types/intelligence.ts`: 1 · `types/cassi-agent.ts`: 5 · `types/collect-thoughts.ts`: 2 ·
    `types/events.ts`: 1 · `types/replay.ts`: 1 · `base/cognitive-module.ts`: 10 ·
    `base/model-config.ts`: 2 · `base/inference.ts`: 2 · `phrases/phrase-prototypes.ts`: 1.
- **Total substitutions whenever applied: 26** (the `../core/model-pool/types.js` specifier occurs twice in
  `types/cassi-agent.ts`, lines 97 & 107).
- Pairs classified: 15 → vendor type-stub (`../vendor/...`); 10 → relocated-live-set path change (base ↔
  types/config). Builtins + npm + same-dir internals = 0 changes.

---

## 3. Destination layout proposal

```
packages/foundation/
  package.json                     # name: "@cassicore/foundation", type: module, deps: better-sqlite3
  tsconfig.json
  src/
    index.ts                       # public barrel (types + base + config + phrases re-exports)
    types/                         # 19 files — ALL live types in ONE dir, so "./X.js" internal
      interfaces.ts                #   edges among them keep working unchanged
      runtime.ts  intelligence.ts  model-routing.ts  flux-team.ts  workflow.ts
      blackboard-search.ts  cassi-agent.ts  collect-thoughts.ts
      dialectic.ts  dialectic-engine.ts  event-query.ts  execution-backend.ts
      plugin.ts  replay.ts  session-ref.ts  trace.ts  worker-messages.ts  events.ts
    ports/
      paths.ts                     # parameterized data-dir port (see §4b)
    config/
      system-settings.ts           # MODEL_DEFAULTS, SYSTEM_SETTINGS (self-contained)
    phrases/
      phrase-prototypes.ts         # phrase sets (type-only import of a vendored edge-relators stub)
    base/
      cognitive-module.ts          # BaseCognitiveModule (abstract) — registry contract shape
      model-config.ts              # MODEL_DEFAULTS wiring / resolveModelConfigFromJson etc.
      inference.ts                 # infer/inferJSON helpers
    vendor/                        # type stubs ONLY (no runtime) — mirror original D: rel-paths
      core/
        model-pool/types.ts        # ModelHandle, ModelConfig (cassi-agent)
        tools/executor.ts          # ToolExecutor (cassi-agent, cognitive-module)
        tools/registry.ts          # ToolRegistry (cassi-agent, cognitive-module)
        intelligence/
          thought-observer.ts      # CognitiveSignal, SignalKind (collect-thoughts, events)
          cognitive-bridge.ts      # ResonancePattern (collect-thoughts)
          dreamer/types.ts         # DreamerConfig (intelligence re-export)
          module-session-registry.ts   # ModuleSessionRegistry (cognitive-module)
          flux-team/plan-handler.ts    # PlanHandler (cassi-agent)
          flux-team/blackboard.ts      # Blackboard (cassi-agent)
          flux-team/global-blackboard-registry.ts  # GlobalBlackboardRegistry (cognitive-module)
          workspace/index.ts       # GlobalWorkspace, CognitiveSignal, SignalType, WorkspaceResponse (cognitive-module)
          mnemic-field/edge-relators.ts  # PhrasePrototypeSet (phrase-prototypes)
        testing/verification/scenario-types.ts  # ScenarioResult, WorkflowScenario (replay)
```

**Internal-import consequences (all satisfied by the layout):**
- `types/runtime.ts` → `./interfaces.js`, `types/interfaces.ts` → `./events.js`,
  `types/blackboard-search.ts` → `./flux-team.js`, `types/workflow.ts` → `./interfaces.js`,
  `types/intelligence.ts` → `./runtime.js`/`./session-ref.js`, `types/execution-backend.ts` →
  `./runtime.js`, `types/dialectic-engine.ts` → `./runtime.js` — **all stay valid** because all 19 land in
  `src/types/`.
- `base/cognitive-module.ts` → types (`../../types/*.js`) and `config` (`../config/system-settings.js` for
  model-config) resolve with a 2-level `../` prefix from `src/base/`.
- `base/inference.ts` / `base/model-config.ts` → `./model-config.js` / `./inference.js` stay valid (same dir).
- Vendor stubs are always one `../vendor/...` hop from any migrated file (all top-level subdirs).

### 3.1 Repoint log (vendor stub → owning package)

The 11 `vendor/` type stubs are P1 placeholders. Each resolves to a REAL `@cassicore/*` package in a later phase;
at that phase, the owning package's exports replace the stub (imports re-pointed from `../vendor/...` to
`@cassicore/<package>`), then the stub is deleted. P1 imports stay on the local stubs until then.

| vendor stub (`src/vendor/...`) | exported symbols (P1 consumers) | owning package | re-point at |
|---|---|---|---|
| `core/intelligence/flux-team/plan-handler.ts` | `PlanHandler` | `@cassicore/flux-team` | P3 |
| `core/intelligence/flux-team/blackboard.ts` | `Blackboard` | `@cassicore/flux-team` | P3 |
| `core/intelligence/flux-team/global-blackboard-registry.ts` | `GlobalBlackboardRegistry` | `@cassicore/flux-team` | P3 |
| `core/intelligence/mnemic-field/edge-relators.ts` | `PhrasePrototypeSet` | `@cassicore/mnemic-field` | P4 |
| `core/intelligence/workspace/index.ts` | `GlobalWorkspace, CognitiveSignal, SignalType, WorkspaceResponse` | `@cassicore/lamina` (workspace) | P5 |
| `core/intelligence/module-session-registry.ts` | `ModuleSessionRegistry` | `@cassicore/workspace` | P5 |
| `core/intelligence/thought-observer.ts` | `CognitiveSignal, SignalKind` | `@cassicore/reflective` (or owning observer pkg) | P5 |
| `core/intelligence/cognitive-bridge.ts` | `ResonancePattern` | `@cassicore/cortex` (or owning bridge pkg) | P5 |
| `core/intelligence/dreamer/types.ts` | `DreamerConfig` | `@cassicore/reflective` | P5 |
| `core/model-pool/types.ts` | `ModelHandle, ModelConfig` | `@cassicore/model-pool` | P6 |
| `core/tools/executor.ts` | `ToolExecutor` | `@cassicore/tools` | P6 |
| `core/tools/registry.ts` | `ToolRegistry` | `@cassicore/tools` | P6 |
| `core/testing/verification/scenario-types.ts` | `ScenarioResult, WorkflowScenario` | `@cassicore/testing` (or host-wired pkg) | P7/TBD |

> **Exact owning-package names for observer/bridge/dreamer/scenario-types are [VERIFY]** — the plan's P5 groups
> tables (`@cassicore/reflective`, `@cassicore/cortex`) and the P6/P7 test surfaces are the closest anchors; the
> final package may differ. The stub->consumer symbol columns are exact and authoritative.

---

## 4. Known-hard items

### 4a. `types/interfaces.ts` (highest-fanout, 731 core imports)

Foundation ships the FULL `interfaces.ts` (LIVE, 7.5 KB) — do not trim or stub it. It declares
`IEventBus` (line 10), `ILogger` (40), `IConfig` (51), `PluginStatus`/`PluginManifest`/`IPluginHost` (69–108),
`WiringDependencies` (140), `ThinkerDeferredWiring` (164), `IntelligenceModule` (169) — the interface set the
whole repo's modules type against. Because it is the shared substrate (47 dirs consume it), it MUST export the
complete, unchanged surface so P2–P7 modules that `import { ILogger, IEventBus, ... } from '@cassicore/foundation'`
compile against the SAME shapes. Its only import, `./events.js` (→`src/types/events.ts`), is in the live set, so
no external rewrite is needed. **Do not rename or re-home any of its exports.**

### 4b. `utils/paths.ts` → parameterized `ports/paths.ts`

Current surface (`core/utils/paths.ts`, full file read): `getCassiCoreHome()`, `getDataDir()`,
`getCredentialsDir()`, `getArtifactsDir()`, `getConfigPath()`, `getPidFilePath()`, `getAdminSocketPath()`,
`getEnvFilePath()`, `getRepoRoot()`. The plan/§f requires getDataDir/getCassiCoreHome to accept an injected
base dir. Proposed port shape (default behavior preserved; the *current* `~/.cassicore` resolution order is the
default impl):

```ts
// src/ports/paths.ts  (self-contained; Node builtins only)
export interface CassiCoreRootResolver {
  /** root of all CassiCore data, e.g. ~/.cassicore — injectable base dir */
  getCassiCoreHome(): string
}
// default impl — preserves the current resolution order exactly:
//   1. process.env.CASSICORE_HOME  2. process.env.CASSICORE_DATA_DIR  3. path.join(os.homedir(), '.cassicore')
export const envRootResolver: CassiCoreRootResolver = {
  getCassiCoreHome(): string {
    return process.env.CASSICORE_HOME
      || process.env.CASSICORE_DATA_DIR
      || path.join(os.homedir(), '.cassicore')
  }
}
let rootResolver: CassiCoreRootResolver = envRootResolver
export function setRootResolver(r: CassiCoreRootResolver): void { rootResolver = r }
export function getCassiCoreHome(): string { return rootResolver.getCassiCoreHome() }
export function getDataDir(): string { return path.join(getCassiCoreHome(), 'data') }
export function getCredentialsDir(): string { return path.join(getCassiCoreHome(), 'credentials') }
export function getArtifactsDir(): string { return path.join(getCassiCoreHome(), 'artifacts') }
export function getConfigPath(): string { return path.join(getCassiCoreHome(), 'config.json') }
export function getPidFilePath(): string { return path.join(getCassiCoreHome(), 'daemon.pid') }
export function getAdminSocketPath(): string { return path.join(getCassiCoreHome(), 'admin.sock') }
export function getEnvFilePath(): string { return path.join(getCassiCoreHome(), '.env') }
// getRepoRoot(): walks up from this file to the dir whose package.json name is 'cassicore' | '@cassicore/core'
//   NOTE: the original walk-up from core/utils/paths.ts assumes a specific depth; in the port it re-derives
//   from src/ports/ (or dist/ports/). Behavior is "closest ancestor package with the cassicore name or,
//   failing that, two levels up" — keep as-is, update the depth provenance comment.
```

`@cassicore/foundation`'s `ports/paths.ts` is the seam the host (P7, and any module) injects a base dir into via
`setRootResolver`; the default is the exact current behavior. Future consumers import it from the foundation
package (never re-vendor).

> **P7 host note (`getRepoRoot`):** `getRepoRoot` is included in the port as a convenience, but its depth
> walk-up is a heuristic for the standalone package. If the P7 host needs a REAL repo root (D: repo or the
> workspace), it should override it through `CassiCoreRootResolver` (add `getRepoRoot(): string` to the resolver
> interface or inject a custom resolver via `setRootResolver`) rather than rely on the port's two-level fallback.

### 4c. Files importing `better-sqlite3` / `vscode-languageserver-types`

From direct source reads:
- **`better-sqlite3` (npm):** `types\intelligence.ts` line ~? uses an inline `import('better-sqlite3')` type
  expression (`indexEntry`/`SQLite`-shaped type in `IndexEntry`/`IndexStore` surface; it is a TYPE-ONLY inline
  import). Only ONE type-file touches it. **Decision (CONFIRMED): add `better-sqlite3` as a runtime npm dependency
  of `@cassicore/foundation`** (matches the Constellation precedent of keeping `better-sqlite3` as an unchanged npm
  dep), since the type surface feeds `types/intelligence.ts` which later phases consume. It is already a top-level
  dep in the workspace and the type is load-bearing.
- **`vscode-languageserver-types`:** the task brief and the exemplar A2/A3 do NOT list it among P1 live files'
  imports — no P1 source file imports it (verified in the extracted import lists above; `types/lsp.ts`, which
  would reference it, is DEAD and excluded). If any future P1 file needed it, vendor a minimal type shim; today:
  **no action.** Proposed rule for the future: `vscode-languageserver-types` is TYPE-ONLY in every live consumer →
  vendor a trimmed `vendor/vscode-languageserver-types.ts` instead of adding the dep (the repo's real LSP
  subsystem is dead; only type surfaces survive).

### 4d. `CognitiveModule` base-class shape for `IntelligenceRegistry` discovery

`core/intelligence/base/registry.ts` discovery contract (verified):
- Discovers subdirectories under an intelligence dir; for each, loads `<dir>/index.ts` (or `.js`), then
  inspects exports for a **named class extending `BaseCognitiveModule`** (prototype-chain walk to
  `BaseCognitiveModule`). It also accepts an index `default` export.
- Registry constructor-injects dependencies via `wireModule` and calls lifecycle; `registerInstance(module)`.
- The `BaseCognitiveModule` shape (`src/base/cognitive-module.ts` after move) that discovered modules rely on:
  - `abstract class BaseCognitiveModule implements IntelligenceModule`
  - abstract `readonly name: string`; abstract `readonly priority: number`
  - `constructor(logger: ILogger, modelConfig?: Partial<ModuleModelConfig>)`
  - protected fields: `logger, config?, eventBus?, memory?, provider?, toolRegistry?, toolExecutor?,
    modelConfig, modelDirective?, providerResolver?, moduleRegistry?, globalBlackboardRegistry?,
    globalWorkspace?` (ToolRegistry/ToolExecutor/ModuleSessionRegistry/GlobalBlackboardRegistry/GlobalWorkspace
    become the vendored TYPE stubs in P1, so the class compiles standalone; the real wiring lands behind ports in
    later phases).
  - lifecycle `init(): Promise<void>`; status (`ModuleStatus` = created|initializing|running|stopped|error);
    inference helpers `infer`/`inferJSON` (from `./inference.ts`); metrics (`CognitiveModuleMetrics`),
    `_lastRequestId`, `onMeta`.
- **Foundation MUST export `BaseCognitiveModule` + `ModuleModelConfig` + `ModuleStatus` with the SAME export
  names** (the file already re-exports `ModuleModelConfig`; keep `export type { ModuleModelConfig }` and
  `export { DEFAULT_MODULE_MODEL_CONFIG }`). Preserve `export abstract class BaseCognitiveModule` and the exact
  protected-field set so `IntelligenceRegistry.discover()`/P7 wiring keeps working unchanged.

---

## 5. Open flags (max 8)

1. **[VERIFY-1] `types/events.ts` is the 19th live type and must migrate.** The §5-P1 enumeration lists 18
   names but says "19 live"; recon confirms `types/` has 19 alive / 6 dead. `events.ts` is required by
   `interfaces.ts` and `event-query.ts`. Confirm it is intended (it is, by liveness + fanout necessity).
   **Decision (CONFIRMED):** migrate `events.ts`; it is live and load-bearing. No table change.
2. **[ASK-2] Logger/event-bus runtime shim location.** §5-P1 line 225 wants "shared event/logger runtime shims
   (ILogger/IEventBus default impls)" but marks the location [VERIFY]. `events.ts` defines `IEventBus` but no
   in-memory `ILogger`/`IEventBus` DEFAULT impl is among the P1 scope files. Decide: does P1 vendor a functional
   `src/vendor/logger.ts` default (self-contained in-memory logger), or leave logger to P6 `@cassicore/events`
   and ship only the INTERFACE now? Default recommendation: ship interface-only in P1, vendor the in-memory impl
   in P6 — but confirm, because foundation consumers (P2+) will `import { ILogger }` and may need the default.
   **Decision (CONFIRMED):** interface-only in P1. P6 provides default impls. No runtime shim file in P1;
   `src/ports/` gets only `paths.ts`.
3. **[ASK-3] Vendor stubs vs deferred re-point.** The 15 external type-only targets (thought-observer,
   cognitive-bridge, scenario-types, dreamer/types, model-pool/types, tools/executor+registry, plan-handler,
   blackboard, global-blackboard-registry, module-session-registry, workspace/index, edge-relators) become
   `vendor/` stubs in P1. When their real packages land (P4/P5/P6), foundation's stubs are re-pointed to
   `@cassicore/*`. Confirm that keeping them as local type stubs (identical shape to the Constellation A3
   precedent) is acceptable for P1 and that re-pointing is scheduled with the owning phase. Default: yes.
   **Decision (CONFIRMED):** vendor stubs now; schedule re-point to `@cassicore/*` with each owning phase
   (P3/P4/P5/P6). See the **Repoint log** in §3 below.
4. **[VERIFY-4] `registry.ts` intentionally excluded from P1.** `base/registry.ts` (the IntelligenceRegistry)
   is host-side discovery, scoped to P7, so P1 migrates only `cognitive-module` + `model-config` + `inference`.
   Confirm the P1 DONE criterion ("at least one downstream package builds against it") doesn't require the
   registry, and that `Booleans`/`ModuleStatus` marker types stay in `base/cognitive-module.ts`. Default: exclude.
   **Decision (CONFIRMED):** `registry.ts` is P7 host-side. P1 DONE criterion stands without it.
5. **[VERIFY-5] `getRepoRoot` depth assumption in `ports/paths.ts`.** The walk-up loop assumes the file sits at
   `core/utils/` (2 levels) or `dist/core/utils/` — after relocation it sits at `src/ports/` (or `dist/ports/`).
   The port keeps the "closest ancestor named cassicore else two-levels-up" behavior but the provenance comment
   must be updated. Confirm Foundation is not expected to locate the D: repo root via this helper (foundation is
   a standalone package; `getRepoRoot` may be dropped or made injectable). Default: keep with a corrected comment;
   flag if any P1-based code depends on it for a real repo.
   **Decision (CONFIRMED):** keep the walk-up with a corrected provenance comment; the host (P7) may override
   `getRepoRoot` via the port if needed (see P7 host note in §4b).
6. **[ASK-6] Path for `core/utils/paths.ts`.** Proposed: land ONLY at `src/ports/paths.ts` (the parameterized
   port), NOT also at `src/utils/paths.ts`. A future `src/utils/paths.ts` re-export barrel can be added later if a
   P5/P6 consumer wants the legacy name. Confirm the sole `ports/paths.ts` placement.
   **Decision (CONFIRMED):** sole placement at `src/ports/paths.ts`; no `src/utils/` duplicate.
7. **[VERIFY-7] `types/cassi-agent.ts` `../core/model-pool/types.js` inline import count.** It appears twice
   (lines 97, 107) — the executor's sed-like replace must catch ALL occurrences of each vendored specifier
   (they are not single-occurrence). Ensure the rewrite is a global per-file substitution, not first-match.
   **Decision (CONFIRMED):** executor MUST do global per-specifier replacement (made bold in §6 step 2).
8. **[ASK-8] `better-sqlite3` as a foundation dep.** Default is "add the npm dep" because the type surface in
   `types/intelligence.ts` is load-bearing and the workspace already depends on it. If the owner prefers a
   zero-runtime-dep foundation, switch to a minimal `vendor/better-sqlite3.d.ts` shim. Confirm once.
   **Decision (CONFIRMED):** add `better-sqlite3` as a foundation npm dependency.

---

## 6. Executor playbook (P1 later wave — verbatim)

1. Copy the 25 LIVE files (rows 1–25) from their exact source paths into `src/` mirroring the dest paths;
   keep `.ts` extensions and `.js` import specifiers exactly.
2. Apply the rewrite pairs of §2 per file — a **GLOBAL replace per specifier (some occur MULTIPLE times — e.g.
   `../core/model-pool/types.js` appears twice in `types/cassi-agent.ts`; replace EVERY occurrence, not just the
   first)**. Do not touch builtins/npm/same-dir-internal/string/comment matches.
3. Write the 11 vendor type stubs at `src/vendor/...` (hold the exact exported type surface each consumer uses:
   names listed in §3 vendor tree). Stubs are self-contained (builtin types only).
4. Write `src/ports/paths.ts` per §4b (functional default, injectable root resolver).
5. Write `src/index.ts` public barrel (re-export types, `BaseCognitiveModule`, `ModelConfig`/MODEL_DEFAULTS,
   phrase sets, paths port functions).
6. `npm run typecheck` (`tsc --noEmit`); fix only mechanical path errors.
7. Do NOT `npm install` (beyond noting `better-sqlite3` dep), do NOT run full tests, do NOT commit.
8. Split commits per plan §3c: (1) history-splice import commit, (2) rewrite-delta commit (this table +
   ports). Verify `git log --follow` before the rewrite commit.

### Files with no external or relocated imports (copy verbatim, NO rewrites)
`types/runtime.ts`, `types/model-routing.ts`, `types/flux-team.ts`, `types/plugin.ts`, `types/session-ref.ts`,
`types/trace.ts`, `types/worker-messages.ts`, `core/config/system-settings.ts` (self-contained),
`core/utils/paths.ts` (→ parameterized port, §2.2/§4b).
