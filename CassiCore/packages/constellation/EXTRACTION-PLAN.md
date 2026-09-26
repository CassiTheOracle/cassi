# @cassicore/constellation — Extraction Plan (Decision + Migration)

**Source:** `D:\carina\workspaces\cassicore\core\intelligence\constellation\` (87 `.ts` files, ~2.5 MB)
**Destination:** `C:\Users\Carina\workspaces\Cassi\CassiCore\Constellation\src\`
**Recon:** `D:\carina\workspaces\cassicore\.opencode\plans\constellation-extraction-recon.md`
**Date:** 2026-08-13
**Phase status:** DESIGN COMPLETE — executable. Source files are NOT yet copied (that is a later parallel wave).

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified. Every rewrite rule
> below is applied only to the **copied** files under `src/`.

---

## NPM / builtin dependency list (verified against source)

Runtime `package.json` deps — exactly what the extracted code needs:

| dep | consumers | type |
|---|---|---|
| `better-sqlite3` | constellation-analyzer, constellation-store, meditation/meditation-store (+ inline `import('better-sqlite3').Database` in self-edit-store) | runtime |
| `uuid` | corpus-reflection-processor, self-edit-store (`v4` / `uuidv4`) | runtime |

Plus **Node builtins** (no dep needed): `node:fs`, `node:path`, `node:child_process`, `node:fs/promises`,
`crypto` (`randomBytes`), `node:util`/`node:os` (used by vendored utils). `vitest` is a **dev** dep only
(test file). **No `zod`** — confirmed by grep; no zod imports in any constellation file.

---

## Part A — External runtime dependency decision table

Every runtime external target from recon §2, judged in place. Columns: source path · used symbols ·
decision (VENDOR → dest, or PORT → port file) · rationale · risk.

### A1. Node builtins + npm (always UNCHANGED — they stay `node:*` / npm package imports)

| source | used symbols | decision | rationale | risk |
|---|---|---|---|---|
| `node:fs` | `existsSync, mkdirSync, rmSync, readFileSync, appendFileSync, fs` | UNCHANGED | builtin | none |
| `node:path` | `join, resolve, path` | UNCHANGED | builtin | none |
| `node:child_process` | `execSync, type ExecSyncOptions` | UNCHANGED | builtin | none |
| `node:fs/promises` | `readFile (as fsReadFile)` | UNCHANGED | builtin | none |
| `crypto` | `randomBytes` (decomposition-tracker) | UNCHANGED | builtin | none |
| `better-sqlite3` | `Database` (default) | UNCHANGED | npm dep; runtime | **ohmypi:** swap to `bun:sqlite` later at the store seam |
| `uuid` | `v4` | UNCHANGED | npm dep; runtime | low |
| `vitest` | `describe, it, expect` | dev-only | test runner | **ohmypi:** `bun:test` later |

### A2. VENDOR decisions (copy file + transitive type-only deps into `src/vendor/`)

| source path | used symbols | decision → dest | rationale (transitive weight) | risk |
|---|---|---|---|---|
| `base/cognitive-module.ts` | `BaseCognitiveModule` (extends) | VENDOR → `vendor/base/cognitive-module.ts` | Class is extended by `meditation/index.ts` and needs its full runtime surface; its runtime deps (`model-config.ts` → `config/system-settings.ts`, `inference.ts`) are all self-contained (builtins + types). No daemon code pulled. | med |
| `base/model-config.ts` | (transitive of cognitive-module) | VENDOR → `vendor/base/model-config.ts` | Runtime value `MODEL_DEFAULTS` from system-settings + type-only. Self-contained. | low |
| `base/inference.ts` | (transitive of cognitive-module) | VENDOR → `vendor/base/inference.ts` | Type-only imports (`IProvider/ICompletionOpts`); self-contained helper. | low |
| `config/system-settings.ts` | `MODEL_DEFAULTS` | VENDOR → `vendor/config/system-settings.ts` | Self-contained (env access only, no imports). Shared by 8 dirs → foundation candidate (MODULARIZATION §d), vendored here as the transport. | low |
| `phrase-prototypes.ts` | `CORPUS_BRANCH_RELATION_PHRASES, DIALECTIC_TYPE_PHRASES, DIALECTIC_QUALITY_PHRASES, DEVIATION_REASON_PHRASES` (+ others re-exported) | VENDOR → `vendor/phrase-prototypes.ts` | Fully self-contained (only type `PhrasePrototypeSet`). | low |
| `embeddings/embedding-service.ts` | `getEmbeddingService` (+ type `EmbeddingService`) | VENDOR → `vendor/embeddings/embedding-service.ts` | Deps only `crypto`/`fs`/`path` + `ILogger` type. Self-contained singleton. | low |
| `flux-team/blackboard.ts` | `Blackboard` class + types `Blackboard`, `BlackboardSummary` | VENDOR → `vendor/flux-team/blackboard.ts` | Runtime dep `blackboard-search.ts` (self-contained, no imports) + `crypto` + type-only `types/flux-team.js`, `types/blackboard-search.js`. Deep only via type stubs → VENDOR the cluster. | med (needs `blackboard-search` + 2 type stubs) |
| `flux-team/blackboard-search.ts` | (transitive of blackboard) | VENDOR → `vendor/flux-team/blackboard-search.ts` | No imports. | low |
| `thalamus/cross-session-index.ts` | `CrossSessionTopicIndex` | VENDOR → `vendor/thalamus/cross-session-index.ts` | Runtime used in pipeline; imports only type `ILogger`, `EmbeddingService`, `TopicSummary` + no runtime deps. Self-contained. | low |
| `helix/observer-activity-scheduler.ts` | `ObserverActivityScheduler` + types `ObserverActivityConfig`, `ObserverFireReason` | VENDOR → `vendor/helix/observer-activity-scheduler.ts` | No imports. Fully self-contained. | low |
| `mnemic-field/graph-attn-propagator.ts` | `GraphAttnPropagator` + type `PropagatedEngram` | VENDOR → `vendor/mnemic-field/graph-attn-propagator.ts` | Runtime import = `SYNAPSE_PROPAGATION` from `mnemic-field/types.ts` (self-contained). ++ type `Cortex`, `Engram`, `MnemicSynapse`, `SynapseType`. Carry `mnemic-field/types.ts`. | med (needs types stub) |
| `mini-helix/mini-helix-runner.ts` | `createMiniHelixSession` | VENDOR → `vendor/mini-helix/mini-helix-runner.ts` | Runtime dep `mini-helix-types.ts` (self-contained, type-only imports) for `MINI_HELIX_DEFAULTS`. Runs LLM via injected deps (type-only `ModelHandle`/`Message`) — no process/driver code pulled. | med |
| `mini-helix/mini-helix-types.ts` | (transitive) `MiniHelixSession` etc. + runtime `MINI_HELIX_DEFAULTS` | VENDOR → `vendor/mini-helix/mini-helix-types.ts` | Type-only imports. Self-contained. | low |
| `code-analysis/specificity-scorer.ts` | `scoreSpecificity` | VENDOR → `vendor/code-analysis/specificity-scorer.ts` | Only type-only imports (`SpecificityScore`, `SpecificitySignal`, `ContextFeedbackTracker`). No runtime deps. | low |
| `tools/implementations/graph-discover.ts` | `setGraphDiscoverDeps` | VENDOR → `vendor/tools/implementations/graph-discover.ts` | Imports only type `ToolDefinition`/`ToolHandler` (core/tools/types) + type `GraphAttnPropagator`. Self-contained DI setter. | low |
| `workflow/builder.ts` | `createWorkflow` (+ `createStep`, `WorkflowBuilder`) | VENDOR → `vendor/workflow/builder.ts` | No imports at all. | low |
| `workflow/steps.ts` | `helixBranch, corpusAssessStep, corpusDirectiveStep` (+ types) | VENDOR → `vendor/workflow/steps.ts` | Only type import `types/workflow.js`. Self-contained. | low |
| `workflow/templates.ts` | `featureImplementation` | VENDOR → `vendor/workflow/templates.ts` | Runtime imports `builder.js` + `steps.js` (both vendored), type `types/workflow.js`. Self-contained cluster. | low |
| `shared/posture-store.ts` | `getBaseIdentity` (+ type `PostureName`) | VENDOR → `vendor/shared/posture-store.ts` | Self-contained (only local const prompt strings). | low |

### A3. VENDOR type stubs (TYPE-ONLY — mirror original paths under `src/vendor/`, hold the type surface constellation uses)

All of these were verified as type-only (via `import type`, `export type`, or used solely as types). They never
exist at runtime in constellation. Per recon, `ILogger`/`IEventBus` (56 files) and `helix/brainstem-types`
(12 files) are the two highest-value stubs.

| source path | symbols used | decision → stub dest |
|---|---|---|
| `types/interfaces.js` | `ILogger, IEventBus, IConfig, IntelligenceModule, WiringDependencies` | VENDOR stub → `vendor/types/interfaces.ts` |
| `types/intelligence.js` | `IMemory, SearchResult` | VENDOR stub → `vendor/types/intelligence.ts` |
| `types/model-routing.js` | `IModelDirective, RoutingTier` | VENDOR stub → `vendor/types/model-routing.ts` |
| `types/runtime.js` | `ThinkingLevel; Message, ContentBlock, CompletionChunk, CompletionOpts, IProvider` | VENDOR stub → `vendor/types/runtime.ts` |
| `types/workflow.js` | `WorkflowDefinition, WorkflowStep, WorkflowRun` | VENDOR stub → `vendor/types/workflow.ts` |
| `types/flux-team.js` | `BlackboardState, Report, BlackboardChannel, BlackboardEntry` | VENDOR stub → `vendor/types/flux-team.ts` |
| `helix/brainstem-types.js` | `BrainstemAnnotation, BrainstemDeps, SharedTreeReader, WorkUnitAnnotation, DetectedPattern, GuidanceUrgency, CognitiveModel, BrainstemContextSources` | VENDOR stub → `vendor/helix/brainstem-types.ts` |
| `helix/brainstem.js` | `HelixBrainstem` (type) | VENDOR stub → `vendor/helix/brainstem.ts` |
| `helix/helix-store.js` | `HelixStore` | VENDOR stub → `vendor/helix/helix-store.ts` |
| `helix/helix-synapse.js` | `HelixSynapse, SynapseBroadcast, SynapseRollingSlice` | VENDOR stub → `vendor/helix/helix-synapse.ts` |
| `helix/types.js` | `HelixResult` | VENDOR stub → `vendor/helix/types.ts` |
| `helix/unified-session.js` | `HelixResult, HelixSession, HelixSessionConfig` | VENDOR stub → `vendor/helix/unified-session.ts` |
| `helix/dialectic-channel.js` | `ConvergencePoint, UnresolvedTension` | VENDOR stub → `vendor/helix/dialectic-channel.ts` |
| `helix/work-types.js` | `WorkUnit` | VENDOR stub → `vendor/helix/work-types.ts` |
| `mnemic-field/index.js` | `MnemicField, Engram, SpikeCreate, MnemicRetrievalHit` (types) | VENDOR stub → `vendor/mnemic-field/index.ts` |
| `mnemic-field/types.js` | `SynapseType, Engram, EngramType, Affect` (+ transitive `Engram`, `MnemicSynapse` for graph-attn) | VENDOR (faithful types + `SYNAPSE_PROPAGATION` runtime const) → `vendor/mnemic-field/types.ts` |
| `mnemic-field/edge-relators.js` | `PhrasePrototypeSet` (type) | VENDOR stub → `vendor/mnemic-field/edge-relators.ts` |
| `mnemic-field/self-model/self-model-field.js` | `SelfModelField` | VENDOR stub → `vendor/mnemic-field/self-model/self-model-field.ts` |
| `mnemic-field/self-model/inter-field-bridge.js` | `InterFieldBridge` | VENDOR stub → `vendor/mnemic-field/self-model/inter-field-bridge.ts` |
| `workspace/index.js` | `GlobalWorkspace, CognitiveSignal` (types) | VENDOR stub → `vendor/workspace/index.ts` |
| `workspace/global-workspace.js` | `GlobalWorkspace` | VENDOR stub → `vendor/workspace/global-workspace.ts` |
| `workspace/cognitive-signal.js` | `CognitiveSignal, SignalType` (+ types) | VENDOR stub → `vendor/workspace/cognitive-signal.ts` |
| `code-analysis/types.js` | `PreparedContext, PrepareContextOptions` | VENDOR stub → `vendor/code-analysis/types.ts` |
| `code-analysis/feedback-tracker.js` | `ContextFeedbackTracker` (inline type) | VENDOR stub → `vendor/code-analysis/feedback-tracker.ts` |
| `embeddings/embedding-service.js` (type) | `EmbeddingService` type (in orchestrator + cross-session-index) | covered by runtime vendor in A2 |
| `thalamus/index.js` | `ThalamusModule` | VENDOR stub → `vendor/thalamus/index.ts` |
| `tools/executor.js` | `ToolExecutor` | VENDOR stub → `vendor/tools/executor.ts` |
| `tools/registry.js` | `ToolRegistry` | VENDOR stub → `vendor/tools/registry.ts` |
| `tools/implementations/collect-thoughts.js` | `ConstellationGuidanceProvider` | VENDOR stub → `vendor/tools/implementations/collect-thoughts.ts` |
| `model-pool/types.js` | `ModelHandle, ModelCompletionOpts` | VENDOR stub → `vendor/model-pool/types.ts` |
| `model-pool/index.js` | `ModelPool` | VENDOR stub → `vendor/model-pool/index.ts` |
| `cortex/index.js` | `CorticalField` | VENDOR stub → `vendor/cortex/index.ts` |
| `aurora/index.js` | `Aurora` | VENDOR stub → `vendor/aurora/index.ts` |
| `lamina/index.js` | `LaminaField` | VENDOR stub → `vendor/lamina/index.ts` |
| `subconscious/types.js` | `Observation, Anomaly` | VENDOR stub → `vendor/subconscious/types.ts` |
| `context-distiller.js` | `ContextDistiller` (injected) | VENDOR stub → `vendor/context-distiller.ts` |
| `module-session-registry.js` | `ModuleSessionRegistry` (injected) | VENDOR stub → `vendor/module-session-registry.ts` |
| `context-repo/projection.js` (inline type) | (projection type) | VENDOR stub → `vendor/context-repo/projection.ts` |
| `reasoning-bank/index.js` (inline type) | (reasoning bank type) | VENDOR stub → `vendor/reasoning-bank/index.ts` |
| `workflow/engine.js` (inline type) | (workflow engine type) | VENDOR stub → `vendor/workflow/engine.ts` |

> **Inline type-expression note:** constellation uses inline `import('…')` type expressions in several
> files (`constellation-pipeline.ts`, `constellation-orchestrator.ts`, `meditation/index.ts`). These are
> TYPE-ONLY and must be rewritten to the same vendored paths (covered by the migration table rows).

### A4. PORT decisions (define minimal interface in `src/ports/<name>.ts` + default impl)

The port file is the ONLY seam between the module and the CassiCore daemon/host. Ports are self-contained
TypeScript (compile against `src/ports/types.ts`-local types + builtins only — no CassiCore imports).

| source path | used symbols | decision → port file | rationale (transitive weight) | risk |
|---|---|---|---|---|
| `helix/helix-pipeline.js` | `runHelixPipeline` | PORT → `src/ports/helix-pipeline.ts` | `runHelixPipeline` drives the full helix pipeline (work-stream, coordinator, posture-runner, brainstem, synapse, conductor, telemetry, abort). Pulling it drags ~dozens of daemon-critical runtime modules. It is the deep orchestration seam — port it. Default: `throw new Error('helix-pipeline not connected')`. | HIGH (pipeline uses it as the core reactor) |
| `helix/brainstem-mini-helix.js` | `BrainstemMiniHelix` (class) | PORT → `src/ports/helix-pipeline.ts` (same port exposes `BrainstemMiniHelix`) | `BrainstemMiniHelix` imports `brainstem-tools` + `createMiniHelixSession` → deep helix + mini-helix runtime machinery. Fold into the helix-pipeline port as an interface + default `not connected`. | HIGH |
| `code-analysis/context-assembler.js` | `prepareContext` | PORT → `src/ports/code-analysis-context.ts` | Imports `gitnexus-bridge.ts` which spawns `git` subprocesses (`exec`/`execSync`, `child_process`) and does background index refresh. Real code-analysis integration — not appropriate to vendor standalone. Default: `throw new Error('code-analysis-context not connected')`. | MED (fast-decomposer needs a real impl to be useful) |
| `utils/paths.js` | `getDataDir` (+ `getCassiCoreHome`) | PORT → `src/ports/paths.ts` | Hardcodes `~/.cassicore`. Parameterize: port exposes `getDataDir(customRoot?)`/`setDataDirRoot()` + default `~/.cassicore`. Default impl is functional. Future ohmypi adaptation = inject data root. | LOW (default preserves current home) |
| `gaming-mode.js` | `isGamingMode` | PORT → `src/ports/gaming-mode.ts` | Imports `rootLogger` from `../logger.js` (deep daemon). Constellation only reads the flag. Port = `isGamingMode(): boolean` (returns false) + `setGamingMode(active, auto?)` no-op/in-memory default. Functional. | LOW |
| `workspace/luminance.js` | `extractKeywords, keywordOverlap` | PORT → `src/ports/workspace-luminance.ts` | Imports `cognitive-signal.js` (runtime consts + types) + type `WorkspaceMemory` — the whole workspace signal system. The two used fns are pure stateless keyword helpers; port them directly (self-contained). | LOW |
| `mcp/gateway/index.js` | `getCodeConsolidatedToolSchema, getFilesystemConsolidatedToolSchema, WEB_CONSOLIDATED_TOOL, executeCodeConsolidatedTool, executeFilesystemConsolidatedTool, executeWebConsolidatedTool` | PORT → `src/ports/mcp-consolidated-tools.ts` | `mcp/gateway/index.js` re-exports the ENTIRE MCP tool router (30+ `*-tools.js` modules → daemon). Deep. Port covers exactly the 6 symbols solo-runner uses (schema getters + executors + `WEB_CONSOLIDATED_TOOL`). Default: throw `not connected` (and schema getters return minimal tool-schema objects). | MED (solo-runner's consolidated execution stops working standalone) |

**Deferred-neutral type-only targets (no decision needed — vendor type stubs, never runtime):**
`types/interfaces`, `types/intelligence`, `types/model-routing`, `types/runtime`, `types/workflow`,
`types/flux-team`, `helix/*` types, `mnemic-field/*` types, `workspace/*` types, `tools/executor`,
`tools/registry`, `model-pool/*`, `cortex/index`, `aurora/index`, `lamina/index`, `thalamus/index`,
`subconscious/types`, `context-distiller`, `module-session-registry`, `context-repo/projection`,
`reasoning-bank/index`, `workflow/engine` → all VENDOR type stubs (A3).

### Counts (runtime external targets)

- **VENDOR (runtime):** 15 — cognitive-module (+model-config, +inference), system-settings, phrase-prototypes,
  embedding-service, blackboard (+blackboard-search), cross-session-index, observer-activity-scheduler,
  graph-attn-propagator (+mnemic-field/types runtime), mini-helix-runner (+mini-helix-types), specificity-scorer,
  graph-discover, workflow{builder,steps,templates}, posture-store.
- **PORT:** 7 — helix-pipeline (≈ brainstem-mini-helix), code-analysis-context, paths, gaming-mode,
  workspace-luminance, mcp-consolidated-tools.
- **VENDOR (type stubs):** ~43 type-only targets.
- **UNCHANGED:** 5 node builtins + 2 npm (`better-sqlite3`, `uuid`) + vitest (dev).

> **Every runtime dependency was classified.** There is no unresolved dependency (see reply summary).

---

## Part B — Per-file migration table (mechanical rewrite rules)

**Mirror rule.** Each file `X.ts` under the constellation dir lands at `src/<same-subdir>/X.ts` (subdirs:
none/root, `corpus/`, `locus/`, `meditation/`, `strategies/`, `topology/`, `consolidation/`). Root files →
`src/X.ts`; subdir files → `src/<subdir>/X.ts`.

**Depth rule.** Because the copied hierarchy is identical, an external import from a **root** file becomes
`./vendor/…` / `./ports/….js`; from a **subdir** file becomes `../vendor/…` / `../ports/….js`.

**Rewrite rules (apply to copied files only).**
- Every specifier listed below under a file's row is replaced with the target shown.
- **DO NOT touch** node builtins, npm packages (`better-sqlite3`, `uuid`, `vitest`, `crypto`), internal
  constellation imports (`./…`, `../…` that stay inside `src/`), and — critically — **string/comment
  content** that merely resembles imports (e.g. `planned`/`assigned`/`in-progress` in
  `decomposition-tracker.ts`, the `from './topology/index.js'` Usage example in `topology/index.ts`
  docstring). Apply edits only to actual `import`/`import type`/`from '…'` / `import('…')` statements.
- Inline `import('…')` type expressions on listed targets are rewritten identically (their row covers them).

### Root files

| source | dest | import rewrites (original → new) |
|---|---|---|
| `blackboard-bridge.ts` | `src/blackboard-bridge.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `blackboard-bridge.ts` | `src/blackboard-bridge.ts` | `../../../types/flux-team.js` → `./vendor/types/flux-team.js` |
| `cluster-observer-layer.ts` | `src/cluster-observer-layer.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `cluster-observer-layer.ts` | `src/cluster-observer-layer.ts` | `../../../types/runtime.js` → `./vendor/types/runtime.js`<br>
| `cluster-observer-layer.ts` | `src/cluster-observer-layer.ts` | `../helix/helix-synapse.js` → `./vendor/helix/helix-synapse.js`<br>
| `cluster-observer-layer.ts` | `src/cluster-observer-layer.ts` | `../thalamus/cross-session-index.js` → `./vendor/thalamus/cross-session-index.js`<br>
| `cluster-observer-layer.ts` | `src/cluster-observer-layer.ts` | `../helix/observer-activity-scheduler.js` → `./vendor/helix/observer-activity-scheduler.js` |
| `constellation-analyzer.ts` | `src/constellation-analyzer.ts` | `../../utils/paths.js` → `./ports/paths.js` |
| `constellation-injection.ts` | `src/constellation-injection.ts` | (no external imports — internal-only) |
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../../../types/model-routing.js` → `./vendor/types/model-routing.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../../model-pool/index.js` → `./vendor/model-pool/index.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../../tools/executor.js` → `./vendor/tools/executor.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../../tools/registry.js` → `./vendor/tools/registry.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../helix/helix-store.js` → `./vendor/helix/helix-store.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../context-distiller.js` → `./vendor/context-distiller.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../module-session-registry.js` → `./vendor/module-session-registry.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../../../types/intelligence.js` → `./vendor/types/intelligence.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../embeddings/embedding-service.js` → `./vendor/embeddings/embedding-service.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../reasoning-bank/index.js` → `./vendor/reasoning-bank/index.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../workspace/index.js` → `./vendor/workspace/index.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../lamina/index.js` → `./vendor/lamina/index.js`<br>
| `constellation-orchestrator.ts` | `src/constellation-orchestrator.ts` | `../../workflow/engine.js` → `./vendor/workflow/engine.js` |
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../../model-pool/types.js` → `./vendor/model-pool/types.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../../tools/executor.js` → `./vendor/tools/executor.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../../tools/registry.js` → `./vendor/tools/registry.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../helix/helix-store.js` → `./vendor/helix/helix-store.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../helix/types.js` → `./vendor/helix/types.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../helix/brainstem-types.js` → `./vendor/helix/brainstem-types.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../helix/brainstem.js` → `./vendor/helix/brainstem.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../helix/helix-synapse.js` → `./vendor/helix/helix-synapse.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../helix/brainstem-mini-helix.js` → `./ports/helix-pipeline.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../helix/helix-pipeline.js` → `./ports/helix-pipeline.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../flux-team/blackboard.js` → `./vendor/flux-team/blackboard.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../mnemic-field/graph-attn-propagator.js` → `./vendor/mnemic-field/graph-attn-propagator.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../../tools/implementations/graph-discover.js` → `./vendor/tools/implementations/graph-discover.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../../../types/intelligence.js` → `./vendor/types/intelligence.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../embeddings/embedding-service.js` → `./vendor/embeddings/embedding-service.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../thalamus/cross-session-index.js` → `./vendor/thalamus/cross-session-index.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../code-analysis/specificity-scorer.js` → `./vendor/code-analysis/specificity-scorer.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../reasoning-bank/index.js` → `./vendor/reasoning-bank/index.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../code-analysis/feedback-tracker.js` → `./vendor/code-analysis/feedback-tracker.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../lamina/index.js` → `./vendor/lamina/index.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../workspace/index.js` → `./vendor/workspace/index.js`<br>
| `constellation-pipeline.ts` | `src/constellation-pipeline.ts` | `../../workflow/engine.js` → `./vendor/workflow/engine.js` |
| `constellation-store.ts` | `src/constellation-store.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `constellation-store.ts` | `src/constellation-store.ts` | `../../utils/paths.js` → `./ports/paths.js` |
| `corpus-mini-helix.ts` | `src/corpus-mini-helix.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `corpus-mini-helix.ts` | `src/corpus-mini-helix.ts` | `../mini-helix/mini-helix-runner.js` → `./vendor/mini-helix/mini-helix-runner.js`<br>
| `corpus-mini-helix.ts` | `src/corpus-mini-helix.ts` | `../mini-helix/mini-helix-types.js` → `./vendor/mini-helix/mini-helix-types.js` |
| `corpus-observer-layer.ts` | `src/corpus-observer-layer.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `corpus-observer-layer.ts` | `src/corpus-observer-layer.ts` | `../../../types/runtime.js` → `./vendor/types/runtime.js`<br>
| `corpus-observer-layer.ts` | `src/corpus-observer-layer.ts` | `../helix/helix-synapse.js` → `./vendor/helix/helix-synapse.js`<br>
| `corpus-observer-layer.ts` | `src/corpus-observer-layer.ts` | `../thalamus/cross-session-index.js` → `./vendor/thalamus/cross-session-index.js`<br>
| `corpus-observer-layer.ts` | `src/corpus-observer-layer.ts` | `../helix/observer-activity-scheduler.js` → `./vendor/helix/observer-activity-scheduler.js` |
| `corpus-reflection-processor.ts` | `src/corpus-reflection-processor.ts` | `../subconscious/types.js` → `./vendor/subconscious/types.js`<br>
| `corpus-reflection-processor.ts` | `src/corpus-reflection-processor.ts` | `../helix/brainstem-types.js` → `./vendor/helix/brainstem-types.js`<br>
| `corpus-reflection-processor.ts` | `src/corpus-reflection-processor.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `corpus-strategy-registry.ts` | `src/corpus-strategy-registry.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `corpus-tools.ts` | `src/corpus-tools.ts` | `../helix/brainstem-types.js` → `./vendor/helix/brainstem-types.js`<br>
| `corpus-tools.ts` | `src/corpus-tools.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `corpus-tools.ts` | `src/corpus-tools.ts` | `../../../types/intelligence.js` → `./vendor/types/intelligence.js`<br>
| `corpus-tools.ts` | `src/corpus-tools.ts` | `../mini-helix/mini-helix-types.js` → `./vendor/mini-helix/mini-helix-types.js`<br>
| `corpus-tools.ts` | `src/corpus-tools.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js` |
| `corpus-tree.ts` | `src/corpus-tree.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `corpus-tree.ts` | `src/corpus-tree.ts` | `../helix/brainstem-types.js` → `./vendor/helix/brainstem-types.js` |
| `corpus-types.ts` | `src/corpus-types.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `corpus-types.ts` | `src/corpus-types.ts` | `../helix/brainstem-types.js` → `./vendor/helix/brainstem-types.js`<br>
| `corpus-types.ts` | `src/corpus-types.ts` | `../../../types/workflow.js` → `./vendor/types/workflow.js`<br>
| `corpus-types.ts` | `src/corpus-types.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js`<br>
| `corpus-types.ts` | `src/corpus-types.ts` | `../../../types/intelligence.js` → `./vendor/types/intelligence.js`<br>
| `corpus-types.ts` | `src/corpus-types.ts` | `../workspace/index.js` → `./vendor/workspace/index.js` |
| `corpus.ts` | `src/corpus.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `corpus.ts` | `src/corpus.ts` | `../helix/brainstem-types.js` → `./vendor/helix/brainstem-types.js` |
| `cross-helix-dialectic.ts` | `src/cross-helix-dialectic.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `cross-helix-dialectic.ts` | `src/cross-helix-dialectic.ts` | `../helix/brainstem.js` → `./vendor/helix/brainstem.js`<br>
| `cross-helix-dialectic.ts` | `src/cross-helix-dialectic.ts` | `../phrase-prototypes.js` → `./vendor/phrase-prototypes.js`<br>
| `cross-helix-dialectic.ts` | `src/cross-helix-dialectic.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js` |
| `decomposition-tracker.ts` | `src/decomposition-tracker.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `decomposition-tracker.ts` | `src/decomposition-tracker.ts` | `../phrase-prototypes.js` → `./vendor/phrase-prototypes.js`<br>
| `decomposition-tracker.ts` | `src/decomposition-tracker.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js`<br>
| `decomposition-tracker.ts` | `src/decomposition-tracker.ts` | **⚠ do NOT rewrite `planned`/`assigned`/`in-progress` (string content).** |
| `decomposition-workflow.ts` | `src/decomposition-workflow.ts` | `../../workflow/builder.js` → `./vendor/workflow/builder.js`<br>
| `decomposition-workflow.ts` | `src/decomposition-workflow.ts` | `../../workflow/steps.js` → `./vendor/workflow/steps.js`<br>
| `decomposition-workflow.ts` | `src/decomposition-workflow.ts` | `../../workflow/templates.js` → `./vendor/workflow/templates.js`<br>
| `decomposition-workflow.ts` | `src/decomposition-workflow.ts` | `../../../types/workflow.js` → `./vendor/types/workflow.js`<br>
| `decomposition-workflow.ts` | `src/decomposition-workflow.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `fast-decomposer.ts` | `src/fast-decomposer.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `fast-decomposer.ts` | `src/fast-decomposer.ts` | `../../../types/intelligence.js` → `./vendor/types/intelligence.js`<br>
| `fast-decomposer.ts` | `src/fast-decomposer.ts` | `../code-analysis/types.js` → `./vendor/code-analysis/types.js`<br>
| `fast-decomposer.ts` | `src/fast-decomposer.ts` | `../code-analysis/context-assembler.js` → `./ports/code-analysis-context.js` |
| `flex-posture.ts` | `src/flex-posture.ts` | `../shared/posture-store.js` → `./vendor/shared/posture-store.js` |
| `graph-coordinator.ts` | `src/graph-coordinator.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js`<br>
| `graph-coordinator.ts` | `src/graph-coordinator.ts` | `../mnemic-field/types.js` → `./vendor/mnemic-field/types.js`<br>
| `graph-coordinator.ts` | `src/graph-coordinator.ts` | `../mnemic-field/graph-attn-propagator.js` → `./vendor/mnemic-field/graph-attn-propagator.js`<br>
| `graph-coordinator.ts` | `src/graph-coordinator.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `guidance-provider.ts` | `src/guidance-provider.ts` | `../../tools/implementations/collect-thoughts.js` → `./vendor/tools/implementations/collect-thoughts.js`<br>
| `guidance-provider.ts` | `src/guidance-provider.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `helix-goal-lamina.ts` | `src/helix-goal-lamina.ts` | `../lamina/index.js` → `./vendor/lamina/index.js`<br>
| `helix-goal-lamina.ts` | `src/helix-goal-lamina.ts` | `../workspace/global-workspace.js` → `./vendor/workspace/global-workspace.js`<br>
| `helix-goal-lamina.ts` | `src/helix-goal-lamina.ts` | `../workspace/cognitive-signal.js` → `./vendor/workspace/cognitive-signal.js` |
| `index.ts` | `src/index.ts` | (no external imports — internal-only) |
| `memory-injection.ts` | `src/memory-injection.ts` | `../../../types/intelligence.js` → `./vendor/types/intelligence.js`<br>
| `memory-injection.ts` | `src/memory-injection.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js`<br>
| `memory-injection.ts` | `src/memory-injection.ts` | `../mnemic-field/graph-attn-propagator.js` → `./vendor/mnemic-field/graph-attn-propagator.js`<br>
| `memory-injection.ts` | `src/memory-injection.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `observer-branch-state.ts` | `src/observer-branch-state.ts` | `../helix/work-types.js` → `./vendor/helix/work-types.js`<br>
| `observer-branch-state.ts` | `src/observer-branch-state.ts` | `../helix/brainstem-types.js` → `./vendor/helix/brainstem-types.js` |
| `observer-broadcast-dedupe.ts` | `src/observer-broadcast-dedupe.ts` | (no external imports — internal-only) |
| `observer-memory-bridge.test.ts` | `src/observer-memory-bridge.test.ts` | (no external imports — internal-only) |
| `observer-memory-bridge.ts` | `src/observer-memory-bridge.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `self-edit-store.ts` | `src/self-edit-store.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `self-edit-types.ts` | `src/self-edit-types.ts` | (no external imports — internal-only) |
| `signal-pattern-digest.ts` | `src/signal-pattern-digest.ts` | `../workspace/cognitive-signal.js` → `./vendor/workspace/cognitive-signal.js` |
| `templates.ts` | `src/templates.ts` | `../../../types/model-routing.js` → `./vendor/types/model-routing.js` |
| `territory-bridge.ts` | `src/territory-bridge.ts` | `../workspace/cognitive-signal.js` → `./vendor/workspace/cognitive-signal.js`<br>
| `territory-bridge.ts` | `src/territory-bridge.ts` | `../workspace/global-workspace.js` → `./vendor/workspace/global-workspace.js`<br>
| `territory-bridge.ts` | `src/territory-bridge.ts` | `../mnemic-field/edge-relators.js` → `./vendor/mnemic-field/edge-relators.js`<br>
| `territory-bridge.ts` | `src/territory-bridge.ts` | `../mnemic-field/index.js` → `./vendor/mnemic-field/index.js`<br>
| `territory-bridge.ts` | `src/territory-bridge.ts` | `../workspace/luminance.js` → `./ports/workspace-luminance.js` |
| `types.ts` | `src/types.ts` | `../helix/dialectic-channel.js` → `./vendor/helix/dialectic-channel.js`<br>
| `types.ts` | `src/types.ts` | `../../../types/flux-team.js` → `./vendor/types/flux-team.js`<br>
| `types.ts` | `src/types.ts` | `../../../types/model-routing.js` → `./vendor/types/model-routing.js`<br>
| `types.ts` | `src/types.ts` | `../helix/helix-pipeline.js` → `./ports/helix-pipeline.js` |
| `unified-cell.ts` | `src/unified-cell.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js`<br>
| `unified-cell.ts` | `src/unified-cell.ts` | `../helix/unified-session.js` → `./vendor/helix/unified-session.js`<br>
| `unified-cell.ts` | `src/unified-cell.ts` | `../flux-team/blackboard.js` → `./vendor/flux-team/blackboard.js`<br>
| `unified-cell.ts` | `src/unified-cell.ts` | `../../../types/flux-team.js` → `./vendor/types/flux-team.js` |
| `worktree-isolation.ts` | `src/worktree-isolation.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
| `worktree-manager.ts` | `src/worktree-manager.ts` | `../../../types/interfaces.js` → `./vendor/types/interfaces.js` |
### `consolidation//`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `consolidation/index.ts` | `src/consolidation/index.ts` | (no external imports — internal-only) |
| `consolidation/outcome-consolidator.ts` | `src/consolidation/outcome-consolidator.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `consolidation/outcome-consolidator.ts` | `src/consolidation/outcome-consolidator.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js`<br>
| `consolidation/outcome-consolidator.ts` | `src/consolidation/outcome-consolidator.ts` | `../../mnemic-field/types.js` → `../vendor/mnemic-field/types.js` |
### `corpus//`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `corpus/corpus-external.ts` | `src/corpus/corpus-external.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `corpus/corpus-external.ts` | `src/corpus/corpus-external.ts` | `../../helix/brainstem-types.js` → `../vendor/helix/brainstem-types.js` |
| `corpus/corpus-patterns.ts` | `src/corpus/corpus-patterns.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `corpus/corpus-patterns.ts` | `src/corpus/corpus-patterns.ts` | `../../phrase-prototypes.js` → `../vendor/phrase-prototypes.js`<br>
| `corpus/corpus-patterns.ts` | `src/corpus/corpus-patterns.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js` |
| `corpus/corpus-utils.ts` | `src/corpus/corpus-utils.ts` | `../../helix/brainstem-types.js` → `../vendor/helix/brainstem-types.js` |
### `locus//`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `locus/constellation-memory.ts` | `src/locus/constellation-memory.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `locus/graph-attention-bridge.ts` | `src/locus/graph-attention-bridge.ts` | `../../workspace/global-workspace.js` → `../vendor/workspace/global-workspace.js`<br>
| `locus/graph-attention-bridge.ts` | `src/locus/graph-attention-bridge.ts` | `../../mnemic-field/types.js` → `../vendor/mnemic-field/types.js`<br>
| `locus/graph-attention-bridge.ts` | `src/locus/graph-attention-bridge.ts` | `../../mnemic-field/graph-attn-propagator.js` → `../vendor/mnemic-field/graph-attn-propagator.js`<br>
| `locus/graph-attention-bridge.ts` | `src/locus/graph-attention-bridge.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `locus/index.ts` | `src/locus/index.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `locus/kindling-engine.ts` | `src/locus/kindling-engine.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `locus/locus-types.ts` | `src/locus/locus-types.ts` | (no external imports — internal-only) |
| `locus/memory-types.ts` | `src/locus/memory-types.ts` | (no external imports — internal-only) |
| `locus/mnemic-locus-memory-persistence.ts` | `src/locus/mnemic-locus-memory-persistence.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js`<br>
| `locus/mnemic-locus-memory-persistence.ts` | `src/locus/mnemic-locus-memory-persistence.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `locus/radiance.ts` | `src/locus/radiance.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `locus/spark-extractor.ts` | `src/locus/spark-extractor.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
### `meditation//`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `meditation/corpus-prompt-library.ts` | `src/meditation/corpus-prompt-library.ts` | (no external imports — internal-only) |
| `meditation/corpus-synthesis.ts` | `src/meditation/corpus-synthesis.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/corpus-synthesis.ts` | `src/meditation/corpus-synthesis.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js`<br>
| `meditation/corpus-synthesis.ts` | `src/meditation/corpus-synthesis.ts` | `../../mnemic-field/types.js` → `../vendor/mnemic-field/types.js` |
| `meditation/evaluation-runner.ts` | `src/meditation/evaluation-runner.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `meditation/field-health.ts` | `src/meditation/field-health.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js`<br>
| `meditation/field-health.ts` | `src/meditation/field-health.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `meditation/focused-seeding.ts` | `src/meditation/focused-seeding.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/focused-seeding.ts` | `src/meditation/focused-seeding.ts` | `../../mini-helix/mini-helix-types.js` → `../vendor/mini-helix/mini-helix-types.js`<br>
| `meditation/focused-seeding.ts` | `src/meditation/focused-seeding.ts` | `../../mini-helix/mini-helix-runner.js` → `../vendor/mini-helix/mini-helix-runner.js`<br>
| `meditation/focused-seeding.ts` | `src/meditation/focused-seeding.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js`<br>
| `meditation/focused-seeding.ts` | `src/meditation/focused-seeding.ts` | `../../../../types/intelligence.js` → `../vendor/types/intelligence.js` |
| `meditation/index.ts` | `src/meditation/index.ts` | `../../base/cognitive-module.js` → `../vendor/base/cognitive-module.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../../config/system-settings.js` → `../vendor/config/system-settings.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../gaming-mode.js` → `../ports/gaming-mode.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../mini-helix/mini-helix-types.js` → `../vendor/mini-helix/mini-helix-types.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../mnemic-field/self-model/self-model-field.js` → `../vendor/mnemic-field/self-model/self-model-field.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../mnemic-field/self-model/inter-field-bridge.js` → `../vendor/mnemic-field/self-model/inter-field-bridge.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../cortex/index.js` → `../vendor/cortex/index.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../thalamus/index.js` → `../vendor/thalamus/index.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../aurora/index.js` → `../vendor/aurora/index.js`<br>
| `meditation/index.ts` | `src/meditation/index.ts` | `../../context-repo/projection.js` → `../vendor/context-repo/projection.js` |
| `meditation/meditation-events.ts` | `src/meditation/meditation-events.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `meditation/meditation-feedback.ts` | `src/meditation/meditation-feedback.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/meditation-feedback.ts` | `src/meditation/meditation-feedback.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js` |
| `meditation/meditation-store.ts` | `src/meditation/meditation-store.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/meditation-store.ts` | `src/meditation/meditation-store.ts` | `../../../utils/paths.js` → `../ports/paths.js` |
| `meditation/meta-evaluation-runner.ts` | `src/meditation/meta-evaluation-runner.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `meditation/mnemic-bridge.ts` | `src/meditation/mnemic-bridge.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/mnemic-bridge.ts` | `src/meditation/mnemic-bridge.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js`<br>
| `meditation/mnemic-bridge.ts` | `src/meditation/mnemic-bridge.ts` | `../../helix/brainstem-types.js` → `../vendor/helix/brainstem-types.js` |
| `meditation/organizing-synthesis.ts` | `src/meditation/organizing-synthesis.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/organizing-synthesis.ts` | `src/meditation/organizing-synthesis.ts` | `../../mnemic-field/index.js` → `../vendor/mnemic-field/index.js` |
| `meditation/self-awareness-detector.ts` | `src/meditation/self-awareness-detector.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/self-awareness-detector.ts` | `src/meditation/self-awareness-detector.ts` | `../../helix/brainstem-types.js` → `../vendor/helix/brainstem-types.js` |
| `meditation/self-modeling-synthesis.ts` | `src/meditation/self-modeling-synthesis.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/self-modeling-synthesis.ts` | `src/meditation/self-modeling-synthesis.ts` | `../../mnemic-field/self-model/self-model-field.js` → `../vendor/mnemic-field/self-model/self-model-field.js`<br>
| `meditation/self-modeling-synthesis.ts` | `src/meditation/self-modeling-synthesis.ts` | `../../mnemic-field/self-model/inter-field-bridge.js` → `../vendor/mnemic-field/self-model/inter-field-bridge.js` |
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../../../types/runtime.js` → `../vendor/types/runtime.js`<br>
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../../model-pool/types.js` → `../vendor/model-pool/types.js`<br>
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../../tools/executor.js` → `../vendor/tools/executor.js`<br>
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../../tools/registry.js` → `../vendor/tools/registry.js`<br>
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../thalamus/index.js` → `../vendor/thalamus/index.js`<br>
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../../../mcp/gateway/index.js` → `../ports/mcp-consolidated-tools.js`<br>
| `meditation/solo-runner.ts` | `src/meditation/solo-runner.ts` | `../../thalamus/cross-session-index.js` → `../vendor/thalamus/cross-session-index.js` |
| `meditation/styles.ts` | `src/meditation/styles.ts` | `../../mnemic-field/types.js` → `../vendor/mnemic-field/types.js` |
| `meditation/thompson.ts` | `src/meditation/thompson.ts` | (no external imports — internal-only) |
| `meditation/types.ts` | `src/meditation/types.ts` | `../../../../types/model-routing.js` → `../vendor/types/model-routing.js` |
### `strategies//`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `strategies/cascade-recovery.ts` | `src/strategies/cascade-recovery.ts` | `../../../workflow/builder.js` → `../vendor/workflow/builder.js`<br>
| `strategies/cascade-recovery.ts` | `src/strategies/cascade-recovery.ts` | `../../../workflow/steps.js` → `../vendor/workflow/steps.js`<br>
| `strategies/cascade-recovery.ts` | `src/strategies/cascade-recovery.ts` | `../../../../types/workflow.js` → `../vendor/types/workflow.js` |
| `strategies/conflict-resolution.ts` | `src/strategies/conflict-resolution.ts` | `../../../workflow/builder.js` → `../vendor/workflow/builder.js`<br>
| `strategies/conflict-resolution.ts` | `src/strategies/conflict-resolution.ts` | `../../../workflow/steps.js` → `../vendor/workflow/steps.js`<br>
| `strategies/conflict-resolution.ts` | `src/strategies/conflict-resolution.ts` | `../../../../types/workflow.js` → `../vendor/types/workflow.js` |
| `strategies/convergence-synthesis.ts` | `src/strategies/convergence-synthesis.ts` | `../../../workflow/builder.js` → `../vendor/workflow/builder.js`<br>
| `strategies/convergence-synthesis.ts` | `src/strategies/convergence-synthesis.ts` | `../../../workflow/steps.js` → `../vendor/workflow/steps.js`<br>
| `strategies/convergence-synthesis.ts` | `src/strategies/convergence-synthesis.ts` | `../../../../types/workflow.js` → `../vendor/types/workflow.js` |
| `strategies/divergence.ts` | `src/strategies/divergence.ts` | `../../../workflow/builder.js` → `../vendor/workflow/builder.js`<br>
| `strategies/divergence.ts` | `src/strategies/divergence.ts` | `../../../workflow/steps.js` → `../vendor/workflow/steps.js`<br>
| `strategies/divergence.ts` | `src/strategies/divergence.ts` | `../../../../types/workflow.js` → `../vendor/types/workflow.js` |
| `strategies/index.ts` | `src/strategies/index.ts` | (no external imports — internal-only) |
| `strategies/redundancy.ts` | `src/strategies/redundancy.ts` | `../../../workflow/builder.js` → `../vendor/workflow/builder.js`<br>
| `strategies/redundancy.ts` | `src/strategies/redundancy.ts` | `../../../workflow/steps.js` → `../vendor/workflow/steps.js`<br>
| `strategies/redundancy.ts` | `src/strategies/redundancy.ts` | `../../../../types/workflow.js` → `../vendor/types/workflow.js` |
| `strategies/resource-imbalance.ts` | `src/strategies/resource-imbalance.ts` | `../../../workflow/builder.js` → `../vendor/workflow/builder.js`<br>
| `strategies/resource-imbalance.ts` | `src/strategies/resource-imbalance.ts` | `../../../workflow/steps.js` → `../vendor/workflow/steps.js`<br>
| `strategies/resource-imbalance.ts` | `src/strategies/resource-imbalance.ts` | `../../../../types/workflow.js` → `../vendor/types/workflow.js` |
| `strategies/stuck-redecomposition.ts` | `src/strategies/stuck-redecomposition.ts` | `../../../workflow/builder.js` → `../vendor/workflow/builder.js`<br>
| `strategies/stuck-redecomposition.ts` | `src/strategies/stuck-redecomposition.ts` | `../../../workflow/steps.js` → `../vendor/workflow/steps.js`<br>
| `strategies/stuck-redecomposition.ts` | `src/strategies/stuck-redecomposition.ts` | `../../../../types/workflow.js` → `../vendor/types/workflow.js` |
### `topology//`

| source | dest | import rewrites (original → new) |
|---|---|---|
| `topology/brainstem-bridge.ts` | `src/topology/brainstem-bridge.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `topology/brainstem-bridge.ts` | `src/topology/brainstem-bridge.ts` | `../../helix/brainstem-types.js` → `../vendor/helix/brainstem-types.js` |
| `topology/cluster-tracker.ts` | `src/topology/cluster-tracker.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `topology/embedding-cache.ts` | `src/topology/embedding-cache.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `topology/embedding-cache.ts` | `src/topology/embedding-cache.ts` | `../../embeddings/embedding-service.js` → `../vendor/embeddings/embedding-service.js` |
| `topology/gravity-engine.ts` | `src/topology/gravity-engine.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `topology/gravity-engine.ts` | `src/topology/gravity-engine.ts` | `../../embeddings/embedding-service.js` → `../vendor/embeddings/embedding-service.js` |
| `topology/index.ts` | `src/topology/index.ts` | (no external imports — internal-only) |
| `topology/link-manager.ts` | `src/topology/link-manager.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js` |
| `topology/topology-context-bridge.ts` | `src/topology/topology-context-bridge.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `topology/topology-context-bridge.ts` | `src/topology/topology-context-bridge.ts` | `../../workspace/index.js` → `../vendor/workspace/index.js` |
| `topology/topology-graph.ts` | `src/topology/topology-graph.ts` | `../../../../types/interfaces.js` → `../vendor/types/interfaces.js`<br>
| `topology/topology-graph.ts` | `src/topology/topology-graph.ts` | `../../embeddings/embedding-service.js` → `../vendor/embeddings/embedding-service.js` |
| `topology/topology-types.ts` | `src/topology/topology-types.ts` | (no external imports — internal-only) |

> **Files not listed** have zero external imports (verified) and are copied verbatim with no rewrites —
> these are the rows marked `(no external imports — internal-only)` below:
> `strategies/index.ts`, `locus/locus-types.ts`, `locus/memory-types.ts`, `consolidation/index.ts`,
> `observer-broadcast-dedupe.ts`, `self-edit-types.ts`, `observer-memory-bridge.test.ts`,
> `index.ts`, `constellation-injection.ts`, `meditation/corpus-prompt-library.ts`, `meditation/thompson.ts`,
> `topology/topology-types.ts`, `topology/index.ts`.

> **`src/index.ts` convention:** when the copy wave runs, the constellation `index.ts` row below **REPLACES**
> this package's placeholder `src/index.ts` barrel. The copied `index.ts` is internal-only (it has no external
> imports) and becomes the package entry point. Its internal `./…` re-imports resolve within `src/`. If a public
> barrel is still desired later, it belongs in `src/index.ts` AFTER the constellation barrel, or as a wrapper that
> re-export the constellation symbols by name.



## Part C — Executor-playbook (worker runs this verbatim)

1. Copy the 87 files (excluding `.bak`/`.patch`/`.md`) from
   `D:\carina\workspaces\cassicore\core\intelligence\constellation\` into `src/` mirroring subdirs.
   Keep `.ts` extension and `.js` import extensions exactly as in source.
2. For each file, apply ONLY the rewrite pairs shown in its Part B row (sed-like, `import`/`import type`
   lines and inline `import('…')` type expressions). Do not touch builtins/npm/internal/string/comment
   matches.
3. Copy the **VENDOR runtime** files (A2) from source into `src/vendor/<area>/<file>.ts` verbatim
   (faithful copies — no field trimming), and adjust THEIR OWN transitive import specifiers to vendor
   paths using the same Part A/A3 mapping (e.g. `cognitive-module.ts` re-imports `./model-config.js`
   which stays `./vendor/base/model-config.js` once relocated).
4. Write the **VENDOR type stubs** (A3) at `src/vendor/<area>/<file>.ts` holding the exact type surface
   constellation uses. Stubs are self-contained; `vendor/types/interfaces.ts` defines `ILogger`/`IEventBus`
   (+ `IConfig`, `IntelligenceModule`, `WiringDependencies`) with a self-contained
   `RuntimeEvent`/`EventType`/`EventOf`/`Unsubscribe` minimal shim (the full CassiCore `events.js`
   federation lives in the daemon — a future foundation-package concern).
5. Write the **ports** (A4) at `src/ports/<name>.ts`.
6. Write `src/index.ts` placeholder barrel (see below).
7. `npm run typecheck` (`tsc --noEmit`). Fix only mechanical path errors; do not refactor behavior.
8. Do NOT `npm install`, do NOT run tests, do NOT commit.

---

## Part D — Port interfaces (contracts the host must supply)

Each port is self-contained and compiles alone. Default impls throw `not connected` for
daemon-integration ports; functional for cheap in-memory/fs-backed ones.

| port | interface surface | default impl |
|---|---|---|
| `helix-pipeline.ts` | `runHelixPipeline(opts): Promise<HelixResult>`; `BrainstemMiniHelix` interface (matching used members) | throw `new Error('[constellation] helix-pipeline not connected — wire runHelixPipeline in the host')` |
| `code-analysis-context.ts` | `prepareContext(opts: PrepareContextOptions): Promise<PreparedContext>` | throw `not connected` |
| `paths.ts` | `getDataDir(): string`; `setDataDirRoot(root?: string): void`; `getCassiCoreHome(root?): string` | functional: `~/.cassicore` default + injectable root |
| `gaming-mode.ts` | `isGamingMode(): boolean`; `setGamingMode(active: boolean, auto?: boolean): void` | functional in-memory flag (false default) |
| `workspace-luminance.ts` | `extractKeywords(text: string): Set<string>`; `keywordOverlap(a: Set<string>, b: Set<string>): number` | functional (self-contained stop-word impl) |
| `mcp-consolidated-tools.ts` | `getCodeConsolidatedToolSchema(fs: boolean): {name;description;input_schema}`; `getFilesystemConsolidatedToolSchema(fs): same`; `WEB_CONSOLIDATED_TOOL`; `executeCodeConsolidatedTool(input, log, routeTool)`; `executeFilesystemConsolidatedTool(input, log, routeTool)`; `executeWebConsolidatedTool(baseUrl, input, log, routeTool)` | schema getters return minimal tool-schema objects; executors throw `not connected` |

---

## Part E — Reference docs

- Recon: `D:\carina\workspaces\cassicore\.opencode\plans\constellation-extraction-recon.md`
- Blueprint: `C:\Users\Carina\workspaces\Cassi\CassiCore\MODULARIZATION.md`

---

## Part F — Deviations from source (documented repairs)

`src/corpus.ts` and `src/corpus-types.ts` are NOT byte-identical to their CassiCore
originals modulo imports. The source `corpus.ts` references a set of Corpus class
members that are **never declared** on the class, and `corpus-types.ts` declares
snapshot fields the implementation does not populate. The extraction worker added
faithful implementations so the standalone package (and the source constellation
subsystem, which is mid-refactor and already broken in CassiCore) typechecks.

Every change below is a **genuine latent defect repair** — each builds a member that
the original code references but does not declare, so the original would fail to
compile (or emit an object missing interface-required fields). None are gratuitous:
each is consumed either by the original `corpus.ts` itself or by already-extracted
sibling modules (`constellation-pipeline.ts`, `constellation-injection.ts`,
`constellation-orchestrator.ts`, `corpus-observer-layer.ts`, `constellation-store.ts`).

### 1. `externalState` getter (was referenced, never declared)

The original references `this.externalState.assumed` in three places but never
declares `externalState`. Repaired as a read-only getter backed by the protocol's
authoritative state:

```ts
// before — original: `this.externalState` used at lines 255, 353, 817, never declared
// after — extracted:
private get externalState(): ExternalCorpusState {
  return this.externalProtocol.getState()
}
```

### 2. `getExternalSnapshotInternal()` (was referenced, never declared)

The original hands `getExternalSnapshot: () => this.getExternalSnapshotInternal()`
to the `ExternalCorpusProtocol` constructor (line 208), but the method is never
defined. Repaired as a faithful snapshot of tree + branch assessments + pending
spawn requests + recent interventions.

### 3. `sendDirectiveInternal()` (was referenced, never declared)

The original passes `sendDirective: (directive) => this.sendDirectiveInternal(directive)`
to the protocol (line 212), but the method is never defined. Repaired to dispatch
via the existing internal `sendDirective`, stamping `timestamp`.

### 4. `stopHeartbeatMonitor()` (was referenced, never declared on Corpus)

The original calls `this.stopHeartbeatMonitor()` on shutdown (line 258). The method
exists only on `ExternalCorpusProtocol` / `corpus-external.ts`, not on the `Corpus`
class. Repaired as a Corpus-side delegation to the protocol's heartbeat cleanup.

### 5. `queueSpawnForExternalDecision()` (was referenced, never declared)

The original calls `this.queueSpawnForExternalDecision({...})` when an external agent
holds the Corpus role (line 354), but the method is never defined. Repaired to queue
the spawn request on the protocol (`queueSpawnRequest`).

### 6. `locusMemoryPersistence` field + `getLocusMemoryPersistence()` (referenced by siblings)

`constellation-pipeline.ts` and `constellation-store.ts` read
`corpus.getLocusMemoryPersistence()`. The original Corpus never provided it. The
worker hoisted `deps.store?.getLocusMemoryPersistence()` out of the `Locus`
constructor into a private field, wired it at construction, and exposed a getter.

### 7. Public external-assumption surface (consumed by siblings)

`isExternallyAssumed()`, `getExternalState()`, `getExternalSnapshot()` are called by
`constellation-injection.ts`, `constellation-orchestrator.ts`, and
`constellation-pipeline.ts`. The original Corpus class never declared them; repaired
to delegate to the protocol state / `getExternalSnapshotInternal()`.

### 8. Locus read surface (consumed by siblings)

`getLocusSnapshot()` and `getLocusMemories()` are called by `constellation-injection.ts`
and `constellation-pipeline.ts`. Repaired to return the Locus snapshot / all memory
entries when the locus layer is enabled, else `undefined`.

### 9. `getSignalPatternDigest()` (consumed by siblings; standalone shim)

`constellation-pipeline.ts` and `corpus-observer-layer.ts` call
`corpus.getSignalPatternDigest()`. The standalone `Corpus` does not maintain a
signal-pattern buffer, so this returns `undefined` (the observer treats `undefined`
as "no digest"). **This is an explicitly non-functional shim**, kept only to satisfy
the already-extracted observer/pipeline surface; behavior in a real host comes from
the daemon's signal-pattern digest.

### 10. `setCorpusObserverActive()` (consumed by siblings; acknowledgment nop)

`constellation-pipeline.ts` calls it to signal that the CorpusObserverLayer owns
cross-Helix LLM analysis. The standalone `Corpus` reads nothing further from the
flag, so it is a lightweight in-memory acknowledgment (nop).

### 11–12. Progress-snapshot completeness (interface/impl mismatch)

`CorpusProgressSnapshot` already declares `llmHealthState` and `llmConsecFailures`
in the original `corpus-types.ts`, but the original `getProgressSnapshot()` never set
them. The worker populates both (`llmHealthState: this.llmHealthy ? 'primary' :
'rule_based'`, `llmConsecFailures: this.llmFailureCount`) and adds an optional
`llmFailureCount?: number` to the snapshot interface to carry the field the original
implementation already emitted.

### Net verdict

No changes in `src/corpus.ts` / `src/corpus-types.ts` beyond (a) import rewrites and
(b) the repairs above. All repairs are genuine — the source `corpus.ts` does not
typecheck in isolation and the constellation subsystem is broken mid-refactor in
CassiCore. Reverting any single repair breaks compilation of the standalone package.

