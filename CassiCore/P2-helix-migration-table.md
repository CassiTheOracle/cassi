# P2 — `@cassicore/helix` — Migration Table (Planning Deliverable)

**Source (READ-ONLY):** `D:\carina\workspaces\cassicore\core\intelligence\helix\`
**Destination:** `C:\Users\Carina\workspaces\Cassi\CassiCore\packages\helix\src\`
**Recon:** `C:\Users\Carina\workspaces\Cassi\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\workspaces\Cassi\CassiCore\CASSI-MIND-PLAN.md` §5-P2, §4
**Exemplar (house format):** `C:\Users\Carina\workspaces\Cassi\CassiCore\P1-foundation-migration-table.md`
**Date:** 2026-08-13
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the only file written by this drafting pass; it is NOT git-added/committed (a parallel
> session is committing in the workspace — this file must stay untracked).

> **Key difference from P1 (handled explicitly):** helix's files import the P1-migrated shared substrate via
> `../../../types/*.js` and `core/utils/paths.js`/`base/cognitive-module.js`/`phrase-prototypes.js`. In the
> destination these become **`@cassicore/foundation` package imports** — NOT `vendor/` stubs and NOT relative
> paths. `@cassicore/foundation` does **NOT yet exist on disk** (P1 is executing right now); the executor wires
> the import only AFTER P1 lands, and MUST verify the foundation barrel exports every symbol helix consumes
> (§2.2 symbol map, with `[VERIFY]` markers). Everything NOT owned by foundation (sibling brain-region dirs,
> model-pool, tools, utils-abort, shared) becomes a `vendor/` type stub per the house pattern, re-pointed to the
> real `@cassicore/*` package when P3/P4/P5/P6 land (repoint log §3.1).

---

## 1. Live-set (files to migrate)

Source dir `core/intelligence/helix/` contains **43 files, 0 subdirectories** (verified via directory listing).
Recon verdicts below are from `recon-data.json` (`deadFiles` / `uncertainFiles`). **7 are DEAD (excluded), 1 is
UNCERTAIN (context-curator, quarantine default), 35 are LIVE.** The `mini-helix/index.ts` UNCERTAIN item in the
task brief belongs to `core/intelligence/mini-helix/` — a SIBLING dir owned by P3, NOT inside the helix dir; it is
out of P2 scope (see Open Flag 1).

### 1.1 LIVE files (35)

| # | source path (D:) | dest path (packages/helix/src/) | size | recon verdict |
|---|---|---|---|---|
| 1 | `brainstem.ts` | `brainstem.ts` | 117.7 KB | LIVE |
| 2 | `helix-posture-runner.ts` | `helix-posture-runner.ts` | 107.0 KB | LIVE |
| 3 | `work-stream.ts` | `work-stream.ts` | 41.4 KB | LIVE |
| 4 | `helix-pipeline.ts` | `helix-pipeline.ts` | 37.4 KB | LIVE |
| 5 | `dialectic-channel.ts` | `dialectic-channel.ts` | 35.6 KB | LIVE |
| 6 | `helix-store.ts` | `helix-store.ts` | 34.6 KB | LIVE |
| 7 | `context-chunk-index.ts` | `context-chunk-index.ts` | 29.5 KB | LIVE |
| 8 | `helix-synapse.ts` | `helix-synapse.ts` | 25.4 KB | LIVE |
| 9 | `brainstem-tools.ts` | `brainstem-tools.ts` | 22.5 KB | LIVE |
| 10 | `brainstem-types.ts` | `brainstem-types.ts` | 22.4 KB | LIVE |
| 11 | `index.ts` | `index.ts` | 20.3 KB | LIVE |
| 12 | `helix-tools.ts` | `helix-tools.ts` | 19.5 KB | LIVE (verified — not in recon dead/uncertain; imported by `helix-posture-runner.ts` + `index.ts`) |
| 13 | `helix-conductor.ts` | `helix-conductor.ts` | 18.4 KB | LIVE |
| 14 | `types.ts` | `types.ts` | 13.9 KB | LIVE |
| 15 | `helix-coordinator.ts` | `helix-coordinator.ts` | 13.3 KB | LIVE |
| 16 | `helix-locus.ts` | `helix-locus.ts` | 13.1 KB | LIVE |
| 17 | `helix-telemetry.ts` | `helix-telemetry.ts` | 10.0 KB | LIVE |
| 18 | `helix-journal.ts` | `helix-journal.ts` | 9.6 KB | LIVE |
| 19 | `testlock.ts` | `testlock.ts` | 9.2 KB | LIVE |
| 20 | `brainstem-mini-helix.ts` | `brainstem-mini-helix.ts` | 9.3 KB | LIVE |
| 21 | `drift-detector.ts` | `drift-detector.ts` | 8.6 KB | LIVE |
| 22 | `dialectic-report-manager.ts` | `dialectic-report-manager.ts` | 8.3 KB | LIVE |
| 23 | `helix-mnemic-bridge.ts` | `helix-mnemic-bridge.ts` | 8.3 KB | LIVE |
| 24 | `work-types.ts` | `work-types.ts` | 7.8 KB | LIVE |
| 25 | `dialectic-tools.ts` | `dialectic-tools.ts` | 7.7 KB | LIVE |
| 26 | `plan-tools.ts` | `plan-tools.ts` | 7.4 KB | LIVE |
| 27 | `posture-module.ts` | `posture-module.ts` | 6.6 KB | LIVE |
| 28 | `observer-activity-scheduler.ts` | `observer-activity-scheduler.ts` | 6.5 KB | LIVE |
| 29 | `helix-session-store.ts` | `helix-session-store.ts` | 6.5 KB | LIVE |
| 30 | `report-tools.ts` | `report-tools.ts` | 6.5 KB | LIVE |
| 31 | `helix-quiescence.ts` | `helix-quiescence.ts` | 6.2 KB | LIVE |
| 32 | `helix-postures.ts` | `helix-postures.ts` | 5.3 KB | LIVE |
| 33 | `helix-mentor-tools.ts` | `helix-mentor-tools.ts` | 4.9 KB | LIVE |
| 34 | `inactivity-watchdog.ts` | `inactivity-watchdog.ts` | 4.2 KB | LIVE |
| 35 | `helix-metrics.ts` | `helix-metrics.ts` | 1.4 KB | LIVE |

**Live-set count: 35 LIVE files (~718 KB total with the UNCERTAIN; live-only ≈ 706 KB).**

### 1.2 UNCERTAIN (do NOT migrate until a worker resolves intent — plan §3a default: quarantine)

| source path (D:) | size | recon why | verify note |
|---|---|---|---|
| `context-curator.ts` | 12.4 KB | `live-name-ref:3` | **Quarantine default.** It is explicitly listed in `tsconfig.json` `exclude: ["core/intelligence/helix/context-curator.ts", …]`, so it does not even compile with the repo build. No helix file imports it (grep of the 36-file set shows no `./context-curator.js` importer; the only `context-curator` importers repo-wide are in the unrelated `core/intelligence/locus-bridge/` module). Its imports are minimal (`./work-types.js` + `node:module`) so it would migrate cleanly IF intended live — but absent any live caller AND explicit tsconfig exclusion, treat as dead. **Default: exclude from P2; record in the debt baseline.** See Open Flag 2. |

### 1.3 Explicitly EXCLUDED (DEAD — do not migrate)

Confirmed in `recon-data.json deadFiles`:

| source path (D:) | size |
|---|---|
| `helix-archive-promotion.ts` | 6.23 KB |
| `helix-recovery.ts` | 4.27 KB |
| `helix-replay.ts` | 5.68 KB |
| `helix-validator.ts` | 17.26 KB |
| `mentor-utils.ts` | 1.7 KB |
| `test-mentor.ts` | 0.13 KB |
| `unified-session.ts` | 22.44 KB |

> **Scope note — no `mini-helix/` subdir exists inside helix.** `ls core/intelligence/helix` = 43 files / 0 dirs.
> `brainstem-mini-helix.ts` (row 20) is a file, not a dir. The plan's UNCERTAIN `core/intelligence/mini-helix/index.ts`
> is a separate sibling directory under `core/intelligence/` owned by **P3** — out of P2 scope.

---

## 2. Rewrite table (mechanical string-substitution pairs)

**Mirror rule for vendor type stubs.** Every external (non-foundation, non-helix) target is reproduced as a
**type stub at `src/vendor/<rel-path-from-D-repo-root>.ts`** (faithful type surface, no runtime), exactly the
Constellation A3 / P1 pattern. Because all 36 helix files land FLAT at `src/` (one level, no subdirs), the vendor
prefix is uniformly **`../vendor/...`** from every migrated file.

**Foundation rule (P2-specific).** Every import resolving to the P1 shared substrate → **`@cassicore/foundation`**
(named import of the symbol(s) helix uses from that foundation module; the executor verifies each symbol is in
the foundation public barrel). This is the headline difference from P1: these are NOT vendored, NOT relative.

**Extension rule.** Source keeps `.js` import specifiers verbatim; only the specifier is rewritten (extension
preserved). For the `@cassicore/foundation` replacement, the `.js` extension is dropped (package specifier).

**Scope rule (what changes vs what stays).**
- **DO NOT touch** Node builtins (`node:fs`, `node:path`, `node:crypto`, `node:module`, inline
  `node:fs/promises`/`node:path` in `index.ts`), npm packages (`better-sqlite3`), and internal imports that remain
  valid after relocation (all `./X.js` siblings — the FLAT layout keeps every helix-internal import unchanged).
- **REWRITE** (a) every P1-foundation import → `@cassicore/foundation`, and (b) every import resolving OUTSIDE
  the P2 live-set + outside foundation → `../vendor/<rel-from-D-repo-root>.js` stub.
- Apply only to actual `import` / `import type` / re-export / inline `import('…')` statements — NOT to
  string/comment content resembling imports (several files carry `// REMOVED: Blackboard import` comments and
  commented-out blackboard imports — leave them as comments untouched).
- Inline `import('…')` type expressions on listed targets are rewritten identically.

### 2.1 Foundation rewrite pairs (→ `@cassicore/foundation`)

All 8 unique specifiers rewrite to the package; the consumed symbol set per pair is in parentheses.

| original specifier | dest specifier | consumed by (source files) |
|---|---|---|
| `../../../types/interfaces.js` | `@cassicore/foundation` | brainstem, brainstem-mini-helix, brainstem-tools, brainstem-types, context-chunk-index, dialectic-channel, drift-detector, helix-conductor, helix-coordinator, helix-journal, helix-locus, helix-metrics, helix-mnemic-bridge, helix-pipeline, helix-posture-runner, helix-quiescence, helix-session-store, helix-store, helix-synapse, helix-telemetry, index, posture-module, work-stream |
| `../../../types/runtime.js` | `@cassicore/foundation` | context-chunk-index, dialectic-tools, helix-mentor-tools, helix-posture-runner, helix-synapse, helix-tools, plan-tools, report-tools |
| `../../../types/model-routing.js` | `@cassicore/foundation` | helix-pipeline, helix-posture-runner, index |
| `../../../types/flux-team.js` | `@cassicore/foundation` | dialectic-report-manager, helix-store (types: `BlackboardState`, `Report`, …) |
| `../../../types/cassi-agent.js` | `@cassicore/foundation` | helix-posture-runner (`InferenceResult`, `ParsedToolCall`) |
| `../phrase-prototypes.js` | `@cassicore/foundation` | brainstem (`WORK_UNIT_ANNOTATION_PHRASES`, `DRIFT_TYPE_PHRASES`) |
| `../base/cognitive-module.js` | `@cassicore/foundation` | posture-module (`BaseCognitiveModule`) |
| `../../utils/paths.js` | `@cassicore/foundation` | helix-journal, helix-session-store, helix-store (`getDataDir`) |

> **Symbol map — [VERIFY] against the real foundation barrel before rewiring.** The destination foundation package
> is mid-P1. Every symbol helix imports from the above modules is expected on foundation's surface (P1 ships all
> 19 types + `BaseCognitiveModule` + `phrase-prototypes` + `ports/paths`); all are named exports already present in
> the source modules, so the P1 import-splice carries them verbatim. The executor MUST re-check against the landed
> foundation `src/index.ts` barrel — any symbol absent is a `[VERIFY]` that must be resolved (add to foundation
> barrel or else vendor a local type) BEFORE committing the helix rewrite. None are expected to be missing, but
> `getDataDir` comes from `ports/paths.ts` (P1 ports seam) — confirm it is re-exported at package top level.

### 2.2 Vendor stub rewrite pairs (→ `../vendor/<rel-from-D-repo-root>.js`)

Every unique external target. Source files landing flat at `src/` all use the same `../vendor/...` prefix.

| original specifier | dest specifier | consumed by (extract of symbols below) |
|---|---|---|
| `../constellation/corpus-types.js` | `../vendor/core/intelligence/constellation/corpus-types.js` | brainstem, brainstem-mini-helix, brainstem-tools, brainstem-types (`CorpusDirective`, `BranchDigest`, `BranchApproach`, `TopicContribution`, `ICorpusTree`, `TopicNode`, …) |
| `../constellation/helix-goal-lamina.js` | `../vendor/core/intelligence/constellation/helix-goal-lamina.js` | helix-conductor (`appendCoordinationLine`) |
| `../constellation/observer-memory-bridge.js` | `../vendor/core/intelligence/constellation/observer-memory-bridge.js` | helix-synapse (`ObserverMemoryBridge`, `extractConceptHints`, `priorityToConfidence`, `ObserverMemorySource`) |
| `../constellation/observer-broadcast-dedupe.js` | `../vendor/core/intelligence/constellation/observer-broadcast-dedupe.js` | helix-synapse (`BroadcastDedupe`, `normalizeForDedupe`) |
| `../mini-helix/mini-helix-types.js` | `../vendor/core/intelligence/mini-helix/mini-helix-types.js` | brainstem-mini-helix, brainstem-tools (`MiniHelixTool`, `MiniHelixToolDef`, `MiniHelixToolResult`, `MiniHelixSession`, `MiniHelixDeps`, `MiniHelixConfig`) |
| `../mini-helix/mini-helix-runner.js` | `../vendor/core/intelligence/mini-helix/mini-helix-runner.js` | brainstem-mini-helix (`createMiniHelixSession`) |
| `../mnemic-field/index.js` | `../vendor/core/intelligence/mnemic-field/index.js` | brainstem, helix-conductor, helix-mnemic-bridge (`MnemicField`) |
| `../mnemic-field/types.js` | `../vendor/core/intelligence/mnemic-field/types.js` | helix-mnemic-bridge (`EngramType`, `SynapseType`) |
| `../aurora/index.js` | `../vendor/core/intelligence/aurora/index.js` | helix-conductor (`Aurora`) |
| `../lamina/index.js` | `../vendor/core/intelligence/lamina/index.js` | helix-conductor (`LaminaField`) |
| `../workspace/index.js` | `../vendor/core/intelligence/workspace/index.js` | helix-conductor, helix-locus, posture-module, types.ts (`CognitiveSignal`, `GlobalWorkspace`, `SignalType`) |
| `../thought-observer.js` | `../vendor/core/intelligence/thought-observer.js` | brainstem-types (`CognitiveSignal`) |
| `../context-distiller.js` | `../vendor/core/intelligence/context-distiller.js` | index.ts (`ContextDistiller`) |
| `../cassi-agent/context-budget-coordinator.js` | `../vendor/core/intelligence/cassi-agent/context-budget-coordinator.js` | helix-pipeline (`ContextBudgetCoordinator`) |
| `../module-session-registry.js` | `../vendor/core/intelligence/module-session-registry.js` | index.ts (`ModuleSessionRegistry`) |
| `../thalamus/index.js` | `../vendor/core/intelligence/thalamus/index.js` | index.ts (inline), helix-pipeline (inline) (`ThalamusModule`) |
| `../thalamus/cross-session-index.js` | `../vendor/core/intelligence/thalamus/cross-session-index.js` | helix-synapse, helix-pipeline (inline) (`CrossSessionTopicIndex`) |
| `../../model-pool/types.js` | `../vendor/core/model-pool/types.js` | helix-pipeline, helix-posture-runner (`ModelHandle`) |
| `../../model-pool/index.js` | `../vendor/core/model-pool/index.js` | index.ts (`ModelPool`) |
| `../../tools/executor.js` | `../vendor/core/tools/executor.js` | helix-pipeline, helix-posture-runner, index.ts (`ToolExecutor`) |
| `../../tools/registry.js` | `../vendor/core/tools/registry.js` | helix-pipeline, helix-posture-runner, index.ts (`ToolRegistry`) |
| `../flux-team/plan-handler.js` | `../vendor/core/intelligence/flux-team/plan-handler.js` | helix-pipeline, helix-posture-runner (`PlanHandler`) |
| `../flux-team/blackboard.js` | `../vendor/core/intelligence/flux-team/blackboard.js` | helix-posture-runner, work-types (`Blackboard`) |
| `../../utils/abort.js` | `../vendor/core/utils/abort.js` | helix-pipeline (`signalPromise`) |
| `../shared/token-estimation.js` | `../vendor/core/intelligence/shared/token-estimation.js` | context-chunk-index, helix-posture-runner (`estimateTokens`) |
| `../shared/posture-store.js` | `../vendor/core/intelligence/shared/posture-store.js` | helix-postures (`composeSystemPrompt`) |

> **Helix-internal imports (all `./X.js` siblings) are UNCHANGED** — the flat dest layout keeps them valid:
> `./work-types.js`, `./brainstem-types.js`, `./brainstem-tools.js`, `./helix-journal.js`, `./helix-locus.js`,
> `./helix-session-store.js`, `./helix-trials…` etc. **0 relocated-internal pairs** exist (no helix subdir to cross).

### 2.3 Rewrite-pair tally by class

- **Foundation (`@cassicore/foundation`): 8 unique pairs.**
- **Vendor type-stub (`../vendor/...`): 26 unique pairs.**
- **Internal (unchanged `./X.js`): 0 rewrite pairs** (all stay valid under flat layout).
- **Relocated-internal: 0** (no helix subdirs).
- **npm/builtin (unchanged): 0** (`node:fs, node:path, node:crypto, node:module, better-sqlite3` + inline builtins).
- **Total rewrite pairs: 34.** (Global per-specifier replacement — several specifiers occur across MANY files,
  e.g. `../../../types/interfaces.js` in 23 files; each is a per-file global replace, not first-match.)

---

## 3. Destination layout proposal

```
packages/helix/
  package.json                     # name: "@cassicore/helix", type: module, deps: @cassicore/foundation, better-sqlite3
  tsconfig.json                    # rootDir src/ outDir dist/ declaration true (mirror Cyclic template)
  vitest.config.ts                 # ported helix tests
  src/
    index.ts                       # entry barrel: createHelix, runHelixPipeline, HelixPostureRunner(+HelixAgentSession alias),
                                   #   posture presets, tool sets, TestLock, BrainstemMiniHelix, HELIX_MODEL_SLOTS (see §4a)
    brainstem.ts  brainstem-tools.ts  brainstem-types.ts  brainstem-mini-helix.ts
    helix-pipeline.ts  helix-posture-runner.ts  helix-coordinator.ts  helix-conductor.ts
    helix-store.ts  helix-synapse.ts  helix-journal.ts  helix-locus.ts  helix-quiescence.ts
    helix-telemetry.ts  helix-metrics.ts  helix-session-store.ts  helix-mnemic-bridge.ts
    helix-tools.ts  helix-tools-sets (flat)  work-stream.ts  work-types.ts  types.ts
    dialectic-channel.ts  dialectic-tools.ts  dialectic-report-manager.ts
    posture-module.ts  helix-postures.ts  plan-tools.ts  report-tools.ts  helix-mentor-tools.ts
    observer-activity-scheduler.ts  inactivity-watchdog.ts  drift-detector.ts  testlock.ts
    context-chunk-index.ts
    vendor/                        # type stubs ONLY (no runtime) — mirror original D: rel-paths (see §3.1)
      core/
        model-pool/types.ts        # ModelHandle            (helix-pipeline, helix-posture-runner)
        model-pool/index.ts        # ModelPool              (index.ts)
        tools/executor.ts          # ToolExecutor           (helix-pipeline, helix-posture-runner, index.ts)
        tools/registry.ts          # ToolRegistry           (helix-pipeline, helix-posture-runner, index.ts)
        utils/abort.ts             # signalPromise          (helix-pipeline)
        intelligence/
          constellation/
            corpus-types.ts        # CorpusDirective, BranchDigest, BranchApproach, TopicContribution, ICorpusTree, TopicNode
            helix-goal-lamina.ts   # appendCoordinationLine
            observer-memory-bridge.ts   # ObserverMemoryBridge, extractConceptHints, priorityToConfidence, ObserverMemorySource
            observer-broadcast-dedupe.ts  # BroadcastDedupe, normalizeForDedupe
          mini-helix/
            mini-helix-types.ts    # MiniHelixTool, MiniHelixToolDef, MiniHelixToolResult, MiniHelixSession, MiniHelixDeps, MiniHelixConfig
            mini-helix-runner.ts   # createMiniHelixSession (runtime fn stub — see note)
          mnemic-field/
            index.ts               # MnemicField (type surface)
            types.ts               # EngramType, SynapseType
          aurora/index.ts          # Aurora
          lamina/index.ts          # LaminaField
          workspace/index.ts       # CognitiveSignal, GlobalWorkspace, SignalType
          thought-observer.ts      # CognitiveSignal
          context-distiller.ts     # ContextDistiller
          cassi-agent/context-budget-coordinator.ts  # ContextBudgetCoordinator
          module-session-registry.ts  # ModuleSessionRegistry
          thalamus/index.ts        # ThalamusModule
          thalamus/cross-session-index.ts  # CrossSessionTopicIndex
          flux-team/plan-handler.ts  # PlanHandler
          flux-team/blackboard.ts    # Blackboard
          shared/token-estimation.ts  # estimateTokens
          shared/posture-store.ts     # composeSystemPrompt
```

**Internal-import consequences (all satisfied by the layout):**
- All 36 live files land FLAT at `src/`, so every `./X.js` helix-internal import stays valid unchanged.
- Foundation imports → `@cassicore/foundation` package specifier (after P1 lands).
- Vendor stubs are always one `../vendor/...` hop from any migrated file (uniform prefix).

> **`createMiniHelixSession` and `composeSystemPrompt`/`estimateTokens` are RUNTIME functions, not type-only.** The
> house vendor stub carries the faithful TYPE surface; where helix calls a runtime function (mini-helix-runner's
> `createMiniHelixSession`, posture-store's `composeSystemPrompt`, token-estimation's `estimateTokens`), the stub
> must either re-export a self-contained faithful implementation OR the executor must confirm the local behavior is
> only used by helix in a way a throw/implant stub satisfies for the build. Default: implement `composeSystemPrompt`
> and `estimateTokens` as exact-copy small functions in the stub (they are pure, no host deps); `createMiniHelixSession`
> lands when P3 `@cassicore/mini-helix` publishes. Mark `[VERIFY]` at execution — these are the only three non-type
> vendored symbols.

### 3.1 Repoint log (vendor stub → owning package)

The 26 `vendor/` type stubs are P2 placeholders. Each resolves to a REAL `@cassicore/*` package in a later phase; at
that phase the owning package's exports replace the stub (imports re-pointed from `../vendor/...` to
`@cassicore/<package>`), then the stub is deleted.

| vendor stub (`src/vendor/...`) | exported symbols (helix consumers) | owning package | re-point at |
|---|---|---|---|
| `core/intelligence/flux-team/plan-handler.ts` | `PlanHandler` | `@cassicore/flux-team` | P3 |
| `core/intelligence/flux-team/blackboard.ts` | `Blackboard` | `@cassicore/flux-team` | P3 |
| `core/intelligence/mini-helix/mini-helix-types.ts` | `MiniHelixTool/…/MiniHelixConfig` | `@cassicore/mini-helix` | P3 |
| `core/intelligence/mini-helix/mini-helix-runner.ts` | `createMiniHelixSession` | `@cassicore/mini-helix` | P3 |
| `core/intelligence/mnemic-field/index.ts` | `MnemicField` | `@cassicore/mnemic-field` | P4 |
| `core/intelligence/mnemic-field/types.ts` | `EngramType, SynapseType` | `@cassicore/mnemic-field` | P4 |
| `core/intelligence/workspace/index.ts` | `CognitiveSignal, GlobalWorkspace, SignalType` | `@cassicore/lamina` (workspace) | P5 |
| `core/intelligence/constellation/corpus-types.ts` | `CorpusDirective, BranchDigest, …` | `@cassicore/constellation` | P5 (or P0 retro) |
| `core/intelligence/constellation/helix-goal-lamina.ts` | `appendCoordinationLine` | `@cassicore/constellation` | P5 |
| `core/intelligence/constellation/observer-memory-bridge.ts` | `ObserverMemoryBridge, …` | `@cassicore/constellation` | P5 |
| `core/intelligence/constellation/observer-broadcast-dedupe.ts` | `BroadcastDedupe, normalizeForDedupe` | `@cassicore/constellation` | P5 |
| `core/intelligence/aurora/index.ts` | `Aurora` | `@cassicore/aurora` (grouped) | P5 |
| `core/intelligence/lamina/index.ts` | `LaminaField` | `@cassicore/lamina` | P5 |
| `core/intelligence/thought-observer.ts` | `CognitiveSignal` | `@cassicore/reflective` (or owning observer pkg) | P5 |
| `core/intelligence/context-distiller.ts` | `ContextDistiller` | `@cassicore/reflective` (or host-wired pkg) | P5 |
| `core/intelligence/cassi-agent/context-budget-coordinator.ts` | `ContextBudgetCoordinator` | `@cassicore/cassi-agent` (grouped) | P5 |
| `core/intelligence/module-session-registry.ts` | `ModuleSessionRegistry` | `@cassicore/workspace` | P5 |
| `core/intelligence/thalamus/index.ts` | `ThalamusModule` | `@cassicore/thalamus` | P5 |
| `core/intelligence/thalamus/cross-session-index.ts` | `CrossSessionTopicIndex` | `@cassicore/thalamus` | P5 |
| `core/intelligence/shared/token-estimation.ts` | `estimateTokens` | `@cassicore/embeddings` (or utils) | P5/P6 |
| `core/intelligence/shared/posture-store.ts` | `composeSystemPrompt` | `@cassicore/embeddings` / workspace | P5 |
| `core/model-pool/types.ts` | `ModelHandle` | `@cassicore/model-pool` | P6 |
| `core/model-pool/index.ts` | `ModelPool` | `@cassicore/model-pool` | P6 |
| `core/tools/executor.ts` | `ToolExecutor` | `@cassicore/tools` | P6 |
| `core/tools/registry.ts` | `ToolRegistry` | `@cassicore/tools` | P6 |
| `core/utils/abort.ts` | `signalPromise` | `@cassicore/utils` | P6 |

> **Cross-package precedent (plan §5-P2):** the FIRST inter-package wiring lands at P2 — constellation's
> helix-pipeline port must consume the REAL `runHelixPipeline` from `@cassicore/helix`, not a vendored stub. That is
> the validate-the-inter-package-port step for P3+. The `constellation/...` and `mini-helix/...` stubs above are
> candidates to be wired directly instead of vendored if the owning package lands before helix needs its stub
> resolved — confirm ordering at P2-execution (see Open Flag 3).

---

## 4. Known-hard items

### 4a. Helix entry / discovery surface — what `helix/index.ts` exports and who discovers it

`src/index.ts` (20.3 KB) is a **function-and-orchestrator barrel, NOT a `BaseCognitiveModule` subclass**. It exports:

- `createHelix(logger: ILogger, eventBus?: IEventBus, modelPool?: ModelPool): HelixOrchestrator` — the entry factory.
- `HelixOrchestrator` interface: `project(opts: HelixProjectOpts): Promise<HelixResult>`, `cancel(id): boolean`,
  `getActiveSessions()`, `getActiveProgress(id)`, `setModelPool/setToolRegistry/setToolExecutor/setStore/
  setModelDirective/setContextDistiller/setModuleRegistry/setThalamus`, `getHealth()`.
- Re-exports: posture types + `UNITY/YANG/YIN/…_POSTURE` presets, `HELIX_POSTURES`, `ALL_{UNITY,YANG,YIN,MENTOR}_TOOLS`,
  `isHelixMetaTool`, `getHelixToolSchemas`, `*_TESTLOCK_TOOLS`/`TESTLOCK_TOOL_NAMES`, `HelixPostureRunner`
  (+ deprecated `HelixAgentSession` alias), **`runHelixPipeline`** + `HelixPipelineOpts`, `TestLock` + its types,
  `HELIX_MODEL_SLOTS`, `BrainstemMiniHelix`, `createBrainstemTools`/`buildBrainstemSystemPrompt`.

**Discovery contract — P7 note:** The @dep header on `createHelix` records callers
`createIntelligence (core/intelligence/index.ts)` + `helix-wiring.test.ts (tests/helix-wiring.test.ts)`. Helix is
**NOT** registry-discovered via the `IntelligenceRegistry` directory-scan used by `BaseCognitiveModule` subclasses
(dfn §3e.1): helix is an orchestrator wired **explicitly** by the host's `createIntelligence()`/`bootIntelligencePostPipeline()`
(analogous to the registry's "skip-list" manual instantiation). Only `posture-module.ts` extends `BaseCognitiveModule`
(imported from foundation) — that is a per-session posture helper, not the registered intelligence module. For the
P7 host: preserve `createHelix`'s exact signature + the `HelixOrchestrator` method surface, and keep
`runHelixPipeline` exported both from `@cassicore/helix` AND wireable into `@cassicore/constellation`'s helix-pipeline
port (the P2 validation criterion). **Do NOT rewrite the barrel's export names** — the constellation port and
`createIntelligence` type against them.

### 4b. `runHelixPipeline` signature and return (the constellation port expects this exact shape)

From `helix-pipeline.ts` (verbatim signature + key members):

```ts
export async function runHelixPipeline(opts: HelixPipelineOpts): Promise<HelixResult>
export interface HelixPipelineOpts {
  goal: string
  context?: string
  sessionId: string
  jobId?: string
  logger: ILogger
  timeoutMs?: number
  unityHandle: ModelHandle        // each posture gets a model handle from the pool
  yangHandle: ModelHandle
  yinHandle: ModelHandle
  mentorHandle?: ModelHandle      // @deprecated — retained for backward compat, ignored
  toolExecutor?: ToolExecutor
  toolRegistry?: ToolRegistry
  store?: HelixStore
  eventBus?: IEventBus
  planHandler?: PlanHandler       // REMOVED-from-use (Blackboard deprecated); field retained
  modelDirective?: IModelDirective
  handleFactory?: (config: ModelConfig) => Promise<ModelHandle>
  onCancelRegistered?/onWorkStreamCreated?/onDialecticChannelCreated?/onCoordinatorCreated?/onBrainstemCreated?/onSynapseCreated?: cb
  onWorkUnit?: (wu: WorkUnit, iteration: number) => void
  artifactNamespace?  sessionType?  teamId?  moduleDebugSessionId?
  thalamus?: import('../thalamus/index.js').ThalamusModule
  crossSessionIndex?: import('../thalamus/cross-session-index.js').CrossSessionTopicIndex
  constellationId?: string
  // + LaminaField wiring members (conductor/posture-runners write to the helix-goal lamina)
}
```

`HelixResult` (from `types.ts`) returns: `unitySummary?/yangSummary?/yinSummary?/mentorSynthesis?`, mentor
recommendation (`'proceed'|'proceed-with-caution'|'revise'|'reject'`) + confidence, `unityConclusion/yangConclusion/
yinConclusion/mentorConclusion` (required), `convergencePoints: ConvergencePoint[]`, `unresolvedTensions:
UnresolvedTension[]`, per-posture `*KeyPoints?/*Confidence?/*RemainingRisks?`, `qualityScore?`,
`remainingIssues?`, `filesModified?: Array<{path,action,summary}>`, `tokensUsed/iterationCounts/toolCallCounts:
{unity,yang,yin,mentor}`, `dialecticStats` (5 fields), `pipelineStats` (3 fields), `durationMs: number`,
`error?: string`, `completionStatus: HelixCompletionStatus`, `autoReport?: AutoReportSection[]`,
`metrics?: HelixMetricsSnapshot`, `brainstem?: BrainstemResult`, `report?: Report` (flux-team),
`sessionState?: { plan; report }`.

**Port/rewrite implication:** `runHelixPipeline` and `HelixResult`/`HelixPipelineOpts` must be exported unchanged
from `src/helix-pipeline.ts` and re-exported from `src/index.ts`; `HelixCompletionStatus`/`ConvergencePoint`/
`UnresolvedTension`/`AutoReportSection` are defined in helix's own `types.ts`/`brainstem-types.ts`/`dialectic-channel.ts`
(they migrate with helix). The only external types the signature references are `ModelHandle`/`ModelPool`
(vendor→P6 model-pool), `ToolExecutor`/`ToolRegistry` (vendor→P6 tools), `PlanHandler` (vendor→P3 flux-team),
`ThalamusModule`/`CrossSessionTopicIndex` (vendor→P5 thalamus), `IModelDirective`/`ModelConfig` (foundation),
`ILogger`/`IEventBus` (foundation), `Report` (foundation flux-team). **The constellation helix port must match this
exact shape (goal/context/sessionId/logger/handles/stores/callbacks/opts) or the P2 inter-package validation fails.**

### 4c. Subprocess / worker entries — NONE in helix (port isolation note)

Grep across the 43 helix files for `require.main|import.meta.url ===|process.argv[1]|mainModule|child_process|
worker_threads|#!|\.fork\(` → **no matches**. Helix is **pure libraries**; there are no standalone process/bin
entries to port-isolate at P2. The standalone process entries elsewhere (e.g. `mnemic-field/umap-worker.cjs`,
`backfill-worker.ts`) belong to P4, not helix. The only host-side/wired surface helix touches is **side-effect
SQLite stores**: `helix-journal.ts`, `helix-session-store.ts`, `helix-store.ts` each open `better-sqlite3` (schema
versions 1/1/7) and write under `getDataDir()` from foundation's `ports/paths`. Those SSOT stores are the seam the
host (or P6 `@cassicore/events`/persistence) can replace; for P2 they keep `better-sqlite3` as a helix npm dep and
read the data dir via `@cassicore/foundation`'s `getDataDir`. No fork/IPC entrypoints exist in helix.

### 4d. Largest files and their dominant imports

- **`brainstem.ts` (117.7 KB, largest):** foundation (`ILogger`/`IEventBus`, `phrase-prototypes` →
  `WORK_UNIT_ANNOTATION_PHRASES`/`DRIFT_TYPE_PHRASES`) + vendor (`constellation/corpus-types`, `mnemic-field/index`)
  + internal (`brainstem-types`, `work-types`). 2 foundation specs + 2 vendor specs; the rest is 3.2k lines of logic.
- **`helix-posture-runner.ts` (107.0 KB):** foundation (`interfaces`, `runtime`, `model-routing`, `cassi-agent`) +
  vendor (`model-pool/types`, `tools/executor`, `tools/registry`, `flux-team/plan-handler`, `flux-team/blackboard`,
  `shared/token-estimation`) + internal (`work-stream`, `work-types`, `dialectic-channel`, `helix-coordinator`,
  `helix-store`, `helix-tools`, `brainstem`, `posture-module`, `types`, `drift-detector`, `testlock`). 4+6 vendor/foundation.
- **`helix-pipeline.ts` (37.4 KB):** foundation (`interfaces`, `model-routing`) + vendor (`model-pool/types`,
  `tools/executor`, `tools/registry`, `flux-team/plan-handler`, `cassi-agent/context-budget-coordinator`,
  `utils/abort`) + internal (work-stream, dialectic-channel, helix-coordinator, helix-posture-runner,
  context-chunk-index, helix-postures, types, brainstem, brainstem-types, helix-synapse, helix-store).
- **`work-stream.ts` (41.4 KB):** foundation (`IEventBus`) + internal (`work-types`). Simplest of the big four.
- **`dialectic-channel.ts` (35.6 KB) / `helix-store.ts` (34.6 KB):** dialectic-channel = foundation `IEventBus` +
  internal `dialectic-report-manager`; helix-store = foundation (`interfaces`, `flux-team`) + `node:fs/path` +
  `better-sqlite3` + `getDataDir` (foundation).

Highest-frequency rewrite: `../../../types/interfaces.js` (appears in **23** of 35 files) and `../../../types/runtime.js`
(8). These are the same module → `@cassicore/foundation` fused rewrite; the executor does a global per-file replace.

---

## 5. Open flags (max 8)

1. **`mini-helix/index.ts` is NOT in helix scope.** The task brief's "mini-helix/index (verify)" UNCERTAIN refers to
   `core/intelligence/mini-helix/index.ts` — a sibling dir under `core/intelligence/` owned by **P3**, and there is
   NO `mini-helix/` subdir inside the helix dir. **Default: out of P2 scope entirely; record in P3's exclude list.**
   The only helix-local mini-helix artifact is the FILE `brainstem-mini-helix.ts` (LIVE, migrated).
2. **`context-curator.ts` (UNCERTAIN): quarantine or migrate?** It is `tsconfig.json`-excluded (`exclude:
   ["core/intelligence/helix/context-curator.ts", …]`), has NO live importer in the 36-file set, and imports only
   `./work-types.js` + `node:module` (would migrate cleanly IF live). Per plan §3a default: quarantine, do not
   import until a worker resolves intent from the referencing live file (there is none). **Default: EXCLUDE from P2
   and record in the P0 debt baseline; delete from helix's tsconfig exclusion becomes moot once the file is dropped.**
3. **Cross-package wiring at P2 (constellation → helix port).** Plan §5-P2 makes P2 the inter-package precedent:
   `@cassicore/constellation` must resolve THE REAL `runHelixPipeline` from `@cassicore/helix` (not a vendored stub),
   and — symmetrically — helix's `constellation/...` and `mini-helix/...` vendor stubs would resolve to
   `@cassicore/constellation` (P0-retro/existing) and `@cassicore/mini-helix` (P3) instead. **Default: wire
   constellation→helix real; keep mini-helix/constellation stubs local (delete at their owning phase via the repoint
   log) unless the owning package lands before P2-execution.**
4. **`@cassicore/foundation` does not exist yet (P1 in flight).** The 8 foundation rewrite pairs target a package that
   lands minutes/commits after this table. The 34-pair rewrite and `npm run typecheck` MUST run only after the P1
   foundation commit is present and its barrel re-exports every consumed symbol (interfaces, runtime, model-routing,
   flux-team, cassi-agent, phrase-prototypes, base/cognitive-module, ports/paths `getDataDir`). **Default: sequence
   P2's rewrite-delta commit strictly after P1's package lands; re-verify the foundation barrel before P2 typecheck.**
5. **Three vendored symbols are RUNTIME functions, not type-only** (`createMiniHelixSession` — mini-helix-runner;
   `composeSystemPrompt` — shared/posture-store; `estimateTokens` — shared/token-estimation). A bare `throw` type stub
   breaks helix at runtime if any code path calls these. **Default: port `composeSystemPrompt` and `estimateTokens`
   as exact-copy self-contained functions into the vendor stubs (pure, no host deps); for `createMiniHelixSession`,
   keep a faithful stub and confirm at P2-execution whether helix's call path is exercised in tests/ports, else land
   the real import from `@cassicore/mini-helix` at P3.** Mark `[VERIFY]`.
6. **`better-sqlite3` + data-dir seam.** Three helix stores (`helix-journal`, `helix-session-store`, `helix-store`)
   are `better-sqlite3` SSOT stores with schema versions 1/1/7, writing under foundation's `ports/paths getDataDir()`.
   **Default: add `better-sqlite3` as a helix npm dep (matches P1 decision) and read the data dir via
   `@cassicore/foundation`'s `getDataDir`; leave the store internals untouched** (no host-wiring until P6/P7 decides
   whether an events/persistence package owns them). Flag if a P6/P7 persistence port should replace these stores.
7. **`helix-tools.ts` status verified LIVE.** It is not in recon `deadFiles`/`uncertainFiles` and is imported by
   `helix-posture-runner.ts` and `index.ts` (live). The task asked to "verify" — done: **migrate it.** Its only
   external import is `../../../types/runtime.js` (→ foundation) plus internal `dialectic-tools/plan-tools/
   report-tools/helix-mentor-tools`; its `SHARE_FINDING_TOOL/CHALLENGE_TOOL/CONCEDE_TOOL/SIGNAL_CONCLUSION_TOOL` come
   from the internal `dialectic-tools.ts`. **Default: migrate as LIVE.**
8. **Ported test surface.** Plan §5-P2 ports `tests/core/intelligence/helix/**` + `helix-*.test.ts` live-target
   matches. `helix-wiring.test.ts` is the @dep caller of `createHelix` — **Default: port it as a host-wired test**
   (`tests/host-wired/` quarantine per plan §6) because it needs a mounted runtime; do not count it in P2's passing
   total. Report actual ported-vs-quarantined vitest counts with P2 DONE.

---

## 6. Executor playbook (P2 later wave — verbatim, mirrors P1 §6)

1. Copy the **35 LIVE files** (table §1.1) from their exact source paths in `core/intelligence/helix/` into
   `src/` mirroring the dest (flat — same file names, `.ts` extensions, `.js` import specifiers exactly). Do NOT copy
   the 7 DEAD (§1.3) or `context-curator.ts` (UNCERTAIN — quarantine default, §1.2 / Open Flag 2).
2. Apply the rewrite pairs of §2 per file — a **GLOBAL replace per specifier (some occur across MANY files — e.g.
   `../../../types/interfaces.js` in 23 files; replace EVERY occurrence in every file, not first-match)**.
   - 8 foundation pairs → `@cassicore/foundation` (only after P1's package lands — Open Flag 4).
   - 26 vendor pairs → `../vendor/<rel-from-D-repo-root>.js` (§2.2).
   - Do NOT touch builtins (`node:fs/path/crypto/module`), npm (`better-sqlite3`), or internal `./X.js` sibling
     imports. Leave `// REMOVED: Blackboard…` comments and commented-out blackboard imports untouched.
3. Write the **26 vendor type stubs** at `src/vendor/...` per §3.1 (exact exported type surface per consumer;
   stubs self-contained — builtin/foundation types only). For the 3 RUNTIME functions (Open Flag 5) provide a faithful
   implementation or confirmed-safe stub: `composeSystemPrompt` + `estimateTokens` as exact pure copies,
   `createMiniHelixSession` as a placeholder to be replaced at P3.
4. If `context-curator.ts` is later resolved LIVE (unlikely — see Open Flag 2), add it as a 36th file with only
   `./work-types.js` + `node:module` rewrites (no vendor/foundation changes).
5. Write `src/index.ts` from `index.ts` preserving ALL export names (see §4a), including the deprecated
   `HelixPostureRunner as HelixAgentSession` alias and `HELIX_MODEL_SLOTS`. Re-export `runHelixPipeline` +
   `HelixPipelineOpts` + `HelixResult` unchanged (§4b).
6. Write `package.json` (`@cassicore/helix`, deps `@cassicore/foundation` + `better-sqlite3`), tsconfig (rootDir
   src/outDir dist/declaration true), vitest.config.ts. Port `tests/core/intelligence/helix/**` + live
   `helix-*.test.ts` from §5-P2; move `helix-wiring.test.ts` to `tests/host-wired/` with the host-wired config
   (already present in the workspace) — Open Flag 8.
7. `npm run typecheck` (`tsc --noEmit`); fix ONLY mechanical path errors. Then `npm test` for the ported suite (skip
   project-wide suites, per the worker contract). Validate the P2 inter-package criterion: `@cassicore/constellation`
   resolves the REAL `runHelixPipeline` from `@cassicore/helix` (Open Flag 3).
8. Do NOT `npm install` beyond noting the `better-sqlite3` dep, do NOT run full tests, do NOT commit to D:.
   Split commits per plan §3c: (1) history-splice import commit, (2) rewrite-delta commit (this table + ports +
   vendor + package.json). Verify `git log --follow` before the rewrite commit.

### Files with no external or relocated imports (copy verbatim, zero rewrites)
`inactivity-watchdog.ts` (no imports), `observer-activity-scheduler.ts` (no imports — local `SchedulerLogger`
interface), `testlock.ts` (`node:crypto` only). All other 32 live files carry ≥1 rewrite pair (foundation and/or
vendor). `work-stream.ts`'s only external is foundation `IEventBus`; `work-types.ts`'s only external is the vendored
`flux-team/blackboard`; `helix-tools.ts`'s only external is foundation `runtime`.
