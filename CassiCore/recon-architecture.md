# CassiCore Architecture Reconnaissance (for cassi-mind migration)

**Date:** 2026-08-13
**Repo:** `D:\carina\workspaces\cassicore` (TypeScript ESM monorepo, Node ≥ 20, daemon-based agent runtime)
**Mode:** Read-only architecture inventory + liveness classification. Nothing under the repo was modified.

---

## 1. Method & Definitions

Liveness was computed by two passes over all TS/JS source files (excluding `node_modules`, `dist`, `target`, `.git`, `.next`, `build`, `out`, cache dirs):

1. **Static import BFS** from every runtime entry root (see §3). Relative imports (`./`, `../`) were resolved with `.js→.ts` suffix swapping and `index` resolution, following the repo's ESM convention (`import … from './x.js'` where source is `x.ts`).
2. **Mechanism-aware overrides** — three non-import wiring patterns were detected and marked ALIVE:
   - `IntelligenceRegistry.discover()` (directory scan + dynamic `import()` of `core/intelligence/<dir>/index.ts` BaseCognitiveModule subclasses) — see §4.1.
   - `resolveWorker("../workers/channels/<name>")` string-path worker loading in `daemon.ts` (webchat, cli, telegram, opencode channels).
   - Standalone **process entry** files (vindex-loader sidecar HTTP :7434, ACP bridge bin, background-launcher, umap-worker, backfill-worker).

**Classification:**
- **ALIVE** — reachable from a runtime entry via import/string-path/mechanism.
- **DEAD** — unreachable via every detected mechanism; the debt-cleanup candidate.
- **UNCERTAIN** — not import-reachable but referenced by a **live** file via a name/path string (e.g. `@dep callers:` markers, `resolveWorker`, config path). Verify intent before deleting.
- **TEST** — `*.test.ts` / `*.spec.ts` / under `__tests__` / `tests/` (reachable by the test runner glob, not by import graph; **not** counted as runtime debt).
- **ALIVE-standalone** — a package or subprocess that is itself a live entry, but whose consumers live *outside* the import graph (external host apps, CLI tooling, per-agent runtimes).

**Caveats / known BFS limits:**
- `webui/` uses Next.js path alias `@/…` (130 alias imports) that a relative-import BFS cannot resolve → its *internal* files classify as DEAD/UNCERTAIN only because of the alias, NOT because they are dead. The package is a live, built (`webui/.next` exists) standalone app.
- `integrations/*` are launched by external runtimes (Claude Code hooks/proxy, Hermes MCP, OpenCode plugin), not imported by `core/` → their liveness is external, not graph-internal.
- `scripts/*` are manually-invoked tooling (release, CI-hook, migration, bench) wired via `package.json`, not the daemon import graph.
- `hermes-tools/`, `bin/`, `packages/larql/` contain **no hand-written TS/JS** (Python / shell / Rust respectively); they are separate-language subsystems with their own entry files.

---

## 2. Quick Counts (compact summary)

| Metric | Value |
|---|---|
| Subsystems inventoried | 17 top-level (core, types, workers, mcp, commands, integrations, packages/larql, cassi-tui, webui, prism, ai, cassi-watch, hermes-tools, bin, scripts, mind-plugin, tests) |
| Source files (TS/JS, excl. build/cache) | 1,497 |
| Files reachable from daemon runtime (import BFS + mechanism) | **857** |
| Subsystems **ALIVE** (fully import-reachable) | **6** — `workers`, `mcp`, `commands`, `cassi-watch`, `mind-plugin` (`core` is ALIVE-trunk w/ dead leaves) |
| Subsystems **ALIVE-standalone** (own external entry) | **5** — `integrations`, `webui`, `scripts`, `hermes-tools`, `bin` (+ `ai`, `cassi-tui`, `prism`, `packages/larql` valid standalone) |
| Subsystems **MIXED** (alive trunk + dead/uncertain leaves) | **5** — `core`, `types`, `ai`, `cassi-tui`, `prism` |
| Subsystems **DEAD** (no live reach; standalone-only) | 0 as packages (dead is leaf-level only) |
| **DEAD** files (non-test) | **207 files ≈ 1,901 KB** (≈ 806 KB in `core`+`types` = the real debt; remainder is webui-alias/scripts/config noise) |
| **UNCERTAIN** files (non-test) | 66 files ≈ 447 KB |
| **TEST** files | 307 files ≈ 3,300 KB |
| Biggest file | `ai/src/models.generated.ts` — 325 KB |

**Biggest 5 files:** `ai/src/models.generated.ts` (325 KB), `core/intelligence/thalamus/index.ts` (185 KB), `core/intelligence/mnemic-field/index.ts` (166 KB), `core/daemon.ts` (158 KB), `core/intelligence/constellation/constellation-pipeline.ts` (137 KB).

---

## 3. Runtime Entry Roots (the reachable set's seeds)

| # | Entry | Role |
|---|---|---|
| 1 | `core/entry/index.ts` | Source `bin/cassicore` launcher → supervisor |
| 2 | `core/entry/supervisor.ts` | Forks `daemon-main.ts`, IPC heartbeat, crash-restart |
| 3 | `core/entry/daemon-main.ts` | Actual daemon process entry (fork target) |
| 4 | `core/daemon.ts` | **The 158 KB `Daemon` class** — heavy dynamic wiring (see §4). Root of `core` runtime reach. |
| 5 | `core/admin-api.ts` / `core/admin-api/index.ts` | Admin HTTP API (REST registry) |
| 6 | `core/cli/index.ts` / `cassicore.ts` | `cassicore` / `cassi` CLI commands |
| 7 | `mcp/cassicore-gateway.ts`, `mcp/gateway/*`, `mcp/scip-server.ts`, `mcp/gitnexus-server.js`, `mcp/serena-server.js` | MCP gateway servers (stdio/HTTP) |
| 8 | `workers/echo-channel.ts` + `workers/channels/*` | Channel worker processes (loaded by daemon via `resolveWorker`) |
| 9 | `commands/index.ts` + `commands/*.ts` | Command dispatchers (imported by core) |
| 10 | `bin/cassicore`, `bin/cassi-acp` | Shell launchers |
| 11 | Standalone package entries | `ai/src/index.ts`+cli, `cassi-tui/src/index.tsx`, `cassi-watch/src/index.tsx`, `prism/src/main.tsx`, `webui/src/app/*`, `mind-plugin/src/index.ts` |
| 12 | **Standalone process entries** | `core/entry/vindex-loader.ts` (sidecar HTTP :7434), `core/bridge/acp/bin.ts`, `core/cli/runtime/background-launcher.cjs`, `core/intelligence/mnemic-field/umap-worker.cjs`, `.../backfill-worker.ts` |

---

## 4. Liveness Mechanisms beyond static imports (critical for the planner)

### 4.1 `IntelligenceRegistry` auto-discovery
`core/intelligence/base/registry.ts` does a **runtime directory scan** of `core/intelligence/*` and dynamically `import()`s any `<dir>/index.js`/`index.ts` that exports a `BaseCognitiveModule` subclass. `daemon.ts:2032` invokes `discover()` with an explicit skip set:

```
base memory continuity recover reflect thinker optimizer dialectic
ai-scientist rule-enforcer subconscious team-orchestrator triad-team
embeddings yang yin synthesizer serenity self-healer heart dreamer
smart-rules reflex consequence-estimator trust-ledger permission-oracle
```

**Every non-skipped `core/intelligence/<dir>/index.ts` extending `BaseCognitiveModule` is ALIVE at runtime even with zero static importers.** Verified live-module dirs that static BFS alone would miss: `cognitive-feed`, `error-learner`, `pineal`, `reverie`, `meditation` (nested). Modules in the skip list are instead manually instantiated in `createIntelligence()` / `bootIntelligencePostPipeline()` (static wiring → already import-reachable).

Migrations MUST account for this: a plugin packaging effort that moves `core/intelligence/*` must preserve or replace the directory-scan registration contract.

### 4.2 Daemon string-path worker loading
`daemon.ts:957-1048` loads channel workers via `resolveWorker("../workers/channels/{webchat,cli,telegram,opencode}")` (runtime file resolution). `core/daemon/channel-loader.ts` also enumerates the same paths. These workers are **runtime loads, not imports** — they are live.

### 4.3 External-host adapters (integrations)
`integrations/claude-code/`, `hermes-agent/`, `opencode/` are **separate processes/packages launched by external hosts**, each with its own entry:
- `integrations/claude-code/src/proxy.ts` (HTTP :7435 intercept proxy) + `hook-server.ts` + `hook-command.cjs` (invoked by `~/.claude/settings.json` hooks). Package scripts `start:proxy`, `start:hooks`, `start:all`.
- `integrations/hermes-agent/src/server.ts` (MCP server registered into Hermes).
- `integrations/opencode/src/cassicore.mjs` (single-file plugin symlinked to `~/.config/opencode/plugins/` by `install.sh`).

These are live external adapters, **not** dead code — but they are prime *standalone-plugin-package* migration candidates (already package-shaped).

### 4.4 Path-alias frontends (webui)
`webui` is a Next.js app (`webui/src`, `@/` alias resolved in `webui/tsconfig.json`), own `package.json`, built `.next/`. `webui/observatory` is a separate Vite app under `webui/observatory/` (own `main.ts`). Internal liveness is not computable without alias resolution; treat the whole `webui` tree as a live standalone package.

### 4.5 Legacy/duplicate subsystems inside `core` (important migration discoveries)
- **`core/providers/qwen-coder.ts`, `core/providers/openai-compatible-base.js`, `pi-bridge.ts`** are **not** wired into `providers/index.ts`, which imports providers from **`../../ai/dist/providers/cassicore/index.js`** (the `ai` package's built output). These `core/providers` files are **legacy duplicates** of provider logic now living in `ai/` — DEAD.
- **`core/daemon/boot-*.ts`, `channel-loader.ts`, `intelligence-wiring.ts`** — a **former boot-phase orchestration** that `daemon.ts` has since bypassed by wiring directly. All carry `@dep callers: …` self-markers and have zero static importers → DEAD (superseded). Exception: `boot-intelligence-post.ts` IS imported and live.
- **`core/lsp/*`** (index, client, server, language, launch, types) — only importer is `core/tools/implementations/lsp-tool.ts`, which is itself **not** registered in `registerCoreTools()` → whole **LSP subsystem is DEAD**.
- **`core/tools/implementations/{edit-file,activity-tools,read-file-benchmark,skill,lsp-tool}.ts`** — not registered in `registerCoreTools` (which imports 30+ other tool modules) → DEAD. `executor.instrumented.ts` is a documented no-op stub ("backward compatibility while tracing is disabled").
- **`core/adapters/*`, `core/ingestion/*`** — engram/ingestion legacy; not wired → DEAD.
- **`core/hierarchy-bridge.ts`** (socket-based cell bus) — no live importer → DEAD (superseded by in-process wiring).

---

## 5. Subsystem Inventory (files · KB · status · consumers · deps · purpose · entry)

> Consumers/deps shown as **top-3**. `consumers` = which subsystem imports it; `ext deps` = its top external/bare-import targets. `A/D/U/T` = ALIVE/DEAD/UNCERTAIN/TEST file counts.

### 5.1 `core/` — 872 files · 10,771 KB · **MIXED** (A679 D100 U39 T54)
Central daemon runtime. Entry: `core/entry/*`, `core/daemon.ts`, `core/admin-api.ts`, `core/cli/*`. Alive trunk; ~100 dead leaves (listed in §7). Consumers: `types(10)`, `mcp(5)`, `workers(5)`. Ext deps: `node:path(131)`, `node:fs(128)`, `better-sqlite3(73)`.
- **`core/intelligence/`** — largest sub-family (~5,000 KB): helix, mnemic-field, constellation, aurora, thalamus, cortex, dialectic, etc. Entries: each subdir's `index.ts` (registry + static). Heaviest files in repo live here.
- **`core/admin-api/`** — REST route registry (50+ route modules: memory, sessions, constellation, intelligence, …). Consumed via `core/admin-api/index.ts` + `admin-api.ts`; dynamically route-dispatched. `core/admin-api/activity.ts`, `metrics.ts`, `team-timeline.ts` are DEAD (unregistered routes).
- **`core/tools/`** — tool executor + registry + ~40 implementations. `executor.ts`, `registry.ts`, `safety.ts`, `implementations/index.ts` (registerCoreTools) live. Several implementations dead (see §4.5).
- **`core/workflow/`** — engine, registry, store, scheduler, steps, templates — ALIVE (imported by daemon for workflow execution).
- **`core/model-pool/`** — capacity/fallback manager — ALIVE (core reach) except `templates.ts` DEAD.
- **`core/daemon/`** — boot wiring: `boot-intelligence-post.ts` ALIVE; `boot-{providers,channels,configuration,intelligence-pre}.ts`, `boot-types.ts`, `channel-loader.ts`, `intelligence-wiring.ts` DEAD (superseded).
- **`core/events/`**, **`core/jobs/`**, **`core/lsp/`** (LSP dead), **`core/mcp/`**, **`core/observability/`** (telemetry DEAD), **`core/plugins/`**, **`core/pipeline/`**, **`core/providers/`** (see §4.5), **`core/entry/`** (vindex-loader = standalone sidecar).
- **`core/adapters/`**, **`core/deploy/`**, **`core/ingestion/`** — whole families DEAD.

### 5.2 `types/` — 25 files · 254 KB · **MIXED** (A19 D6 U0 T0)
Shared type definitions. Consumers: `core(731)`, `mcp(34)`, `workers(4)`. Ext dep: `better-sqlite3(1)`, `vscode-languageserver-types(1)`.
DEAD: `log-events.ts`, `metadata.ts`, `reasoning-chain.ts`, `team-dependencies.ts` (+2 — `unified/types`-adjacent?) — unreferenced by any live module.

### 5.3 `workers/` — 8 files · 87 KB · **ALIVE** (A8)
Channel worker processes loaded by daemon via `resolveWorker` (cli, webchat, telegram, opencode + markdown/format pipeline). Entries: each channel file is a worker entry. Ext deps: `markdown-it(1)`, `http(1)`, `node:crypto(1)`.

### 5.4 `mcp/` — 42 files · 567 KB · **ALIVE** (A42)
MCP gateway. Entries: `mcp/cassicore-gateway.ts`, `mcp/gateway/*` (agent-tools, intelligence-tools, …), `scip-server.ts`, `gitnexus-server.js`, `serena-server.js`. Consumers: `core(3)`. Ext deps: `@modelcontextprotocol(6)`, `child_process(3)`.

### 5.5 `commands/` — 8 files · 76 KB · **ALIVE** (A8)
`cassi-commands.ts`, `cassicore-commands.ts`, `git-commands.ts`, `qwen-commands.ts`, `team-commands.ts`, `tool-commands.ts`, `universal-processor.ts`, `index.ts`. Consumers: `core(3)`. Entry: `commands/index.ts`.

### 5.6 `ai/` — 43 files · 672 KB · **MIXED** (A42 D0 U1)
Standalone npm package (`main: ./dist/index.js`). **Provider canonical home** — `core/providers/index.ts` imports providers from `../../ai/dist/providers/cassicore/index.js`. Entries: `ai/src/index.ts`, `ai/src/cli.ts`. Ext deps: `openai(9)`, `@google(4)`, `@sinclair(3)`.

### 5.7 `cassi-tui/` — 28 files · 129 KB · **MIXED** (A27 D0 U1)
Standalone ~~INK~~ TUI (`bin cassi` → `dist/index.js`). Entry: `cassi-tui/src/index.tsx`. Ext deps: `react(21)`, `ink(15)`, `ink-spinner(3)`.

### 5.8 `cassi-watch/` — 10 files · 45 KB · **ALIVE** (A10)
Standalone watch CLI (`bin cassicore-watch`). Entry: `cassi-watch/src/index.tsx`. Ext deps: `react(8)`, `ink(8)`, `node:http(1)`.

### 5.9 `webui/` — 117 files · 551 KB · **ALIVE-standalone** (internal alias-unresolved)
Next.js app + `webui/observatory` (Vite). Own package, `@/` alias (BFS-internal DEAD/UNCERTAIN are alias artifacts). Ext deps: `@(126)`, `react(44)`, `next(29)`.

### 5.10 `prism/` — 19 files · 26 KB · **MIXED** (A17 D2)
Standalone Vite/three.js app (`type: module`). Entry: `prism/src/main.tsx`. Ext deps: `@react-three(7)`, `react(6)`, `three(3)`. (Distinct from `core/intelligence/aurora/prism.ts` — the internal affect-store, which is ALIVE.)

### 5.11 `integrations/` — 21 files · 274 KB · **ALIVE-standalone** (external hosts)
`claude-code/` (proxy+hooks, plan docs, .env), `hermes-agent/` (MCP server), `opencode/` (plugin). Each launched by external runtime; see §4.3. Ext deps: `node:fs(7)`, `node:http(5)`, `node:os(5)`. Prime standalone-plugin migration candidates.

### 5.12 `packages/larql/` — **Rust workspace** (0 hand-written TS outside build)
Huge `target/` build dir (89 GB incl. `target/*`). Crate entries: `packages/larql/crates/larql-cli/src/main.rs`, `larql-inference`, `larql-vindex`, `larql-compute`. Interop to CassiCore via the `core/entry/vindex-loader.ts` sidecar + N-API. **Not a TS subsystem** — a native/vindex backend.

### 5.13 `cassi-watch` (done), `hermes-tools/` — **Python** (0 TS/JS)
`bridge.py`, `hermes_cli/`, `browser_supervisor.py`, `model_tools.py`, `approval.py`, `hermes_state.py` (124 KB). Launched from `core/tools/hermes-bridge.ts`/`hermes-mcp-client.ts` via subprocess (`bridge.py`). Live external Python subsystem.

### 5.14 `bin/` — 2 files · 1 KB
`cassicore` (→ `core/entry/index.ts`), `cassi-acp` (→ ACP bridge). Shell launchers. ALIVE (root `package.json` bin).

### 5.15 `scripts/` — 29 files (TS/JS) · 299 KB · **ALIVE-tooling**
Manual/CI scripts: `release.ts`, `generate-deps.ts`, `check-contributing.ts`, `check-commit-msg.ts`, `migrate-dialectic.ts`, `install-git-hooks.js`, `smoke-subconscious.ts`, `fluid-field/experiment-*.mjs`, `restructure/migrate.ts`, etc. Invoked via `package.json` scripts — not daemon-graph. Ext deps: `fs(12)`, `module(11)`, `node:fs(8)`.

### 5.16 `mind-plugin/` — 2 files · 9 KB · **ALIVE** (A2)
New migration plugin scaffold (created 1h before recon). Entry: `mind-plugin/src/index.ts` + `mind-client.ts`. Ext dep: `node:net(1)`.

### 5.17 `tests/` — 273 files · 3,139 KB · TEST (253 files) + 15 dead infra + 5 uncertain
Vitest suites (main scope: `tests/**`), plus `tests/fixtures/`, `tests/helpers/`, `tests/smoke.ts`, `tests/spike-*.ts` (diagnostics). Not runtime debt.

---

## 6. Execution / Entry-Adapter Boundaries (seams)

| Subsystem | Entry / adapter file(s) | Boundary type |
|---|---|---|
| core daemon | `core/entry/index.ts → supervisor.ts → daemon-main.ts → daemon.ts` | process fork/IPC |
| core admin | `core/admin-api.ts` + `core/admin-api/index.ts` (REST route registry) | HTTP |
| core cli | `core/cli/index.ts`, `cassicore.ts`, `cli/commands/*` | CLI |
| core bridge | `core/bridge/openai.ts` (OpenAI translation); `core/bridge/acp/client|server|bin.ts` | protocol bridge |
| core sidecar | `core/entry/vindex-loader.ts` (HTTP :7434) | standalone subprocess |
| lsp | `core/lsp/index.ts` | DEAD (type-only) |
| mcp gateway | `mcp/cassicore-gateway.ts`, `mcp/gateway/{agent-tools,intelligence-tools,…}.ts`, `scip-server.ts`, `gitnexus-server.js`, `serena-server.js` | MCP stdio/HTTP |
| workers/channels | `workers/channels/{cli,webchat,telegram,opencode}.ts` (via `resolveWorker`) | subprocess worker |
| commands | `commands/index.ts` | in-process dispatcher |
| ai | `ai/src/index.ts`, `ai/src/cli.ts`, `ai/src/providers/cassicore/index.ts` | npm package |
| cassi-tui / cassi-watch | `src/index.tsx` (bin `cassi`/`cassicore-watch`) | npm CLI |
| webui | `webui/src/app/*` (Next), `webui/observatory/src/main.ts` | web app |
| prism | `prism/src/main.tsx` | Vite app |
| integrations | `claude-code/src/{proxy,hook-server,hook-command}.cjs/ts`, `hermes-agent/src/server.ts`, `opencode/src/cassicore.mjs` | external-host adapters |
| plugins | `core/plugins/plugin-host.ts`, `plugin-registry.ts`, `plugin-api.ts`, `client-sdk.ts` | plugin host (dynamic manifest entrypoint) |

**Key seam** the migration must preserve: `mcp/gateway/*.ts` and `core/admin-api/*.ts` are HTTP/route adapters that dispatch to `core/intelligence/*` and `core/tools/*` through the daemon runtime facade (`admin-api/runtime.ts`, `intelligence.ts`). Plugins should expose the same route/tool contract.

---

## 7. DEAD Files (debt-cleanup candidate list)

### 7.1 Core dead (the real debt) — 100 files · **745.9 KB**

Boot/wiring (superseded): `core/daemon/boot-providers.ts`(22.5), `boot-channels.ts`(2.8), `boot-types.ts`(7.5), `boot-configuration.ts`→UNCERTAIN, `boot-intelligence-pre.ts`→UNCERTAIN, `boot-pipeline-tools.ts`→UNCERTAIN `channel-loader.ts`(7.4), `core/daemon/intelligence-wiring.ts`→UNCERTAIN.
LSP (whole subsystem): `core/lsp/{index,client,server,language,launch,types}.ts` (18.1/11.2/6.8/3.3/3.6/4.4).
Providers (legacy dup of `ai/`): `core/providers/qwen-coder.ts`(9.2), `openai-compatible-base.js`(29.4), `pi-bridge.ts`(3.0), `claude-code-bridge/{defer-tool-hook,ephemeral-mcp-server}.mjs`.
Tools (unregistered): `core/tools/implementations/{edit-file,activity-tools,read-file-benchmark,skill,lsp-tool}.ts`(5.4/14.9/5.4/6.4/6.9), `tools/instrumentation.ts`(4.5), `permission-gate.ts`(3.8), `resolver.ts`(3.1), `tool-selector.ts`(4.9), `executor.instrumented.ts`(6.0), `serena-types.ts`(2.2).
Intelligence (dead leaves): `aurora/{fine-tune-gating,mnemic-steering-bridge,nla-bridge,affect-calibration,affect-probes/v1,affect-signature-store,claustrum-snapshot,coherence-detector/probe-set,welfare-probe-set}.ts`(1.9/7.8/3.7/5.0/5.6/6.0/12.7/5.3/4.9 KB), `branching-conversation/{decision-tree,middleware,session-store}.ts`(9.2/7.7/11.1), `budget-monitor.ts`(8.7), `constellation/{unified-cell,corpus-reflection-processor,corpus-strategy-registry,decomposition-workflow,self-edit-store,self-edit-types,signal-pattern-digest,territory-bridge}.ts` + `constellation/strategies/*`(8 files, ~42 KB), `cortex/blackboard-adapter.ts`(2.7), `dialectic/parallel-processor.ts`(16.3), `goal-tree.ts`(13.5), `helix/{helix-archive-promotion,helix-recovery,helix-replay,helix-validator,mentor-utils,test-mentor,unified-session}.ts`(~57 KB), `improvement/{hypothesis-scenario-bridge,llm-scenario-generator}.ts`(9.7/14.3), `memory-bridge/memory-delta-injector.ts`(20.0), `mnemic-field/{backfill-runner,feature-backfill,feature-migrate-to-lmdb,segmentation}.ts`(4.1/5.5/2.9/0), `pineal/projection.ts`(2.5), `session-activity-store.ts`(20.9), `session-result-store.ts`(14.3), `cognitive-feed/index.ts`→ALIVE (registry), `code-vault/index.ts`→UNCERTAIN.
Adapters/ingestion/deploy (whole families): `core/adapters/{cli,file,http}/*Adapter.ts`(8.8/6.6/8.1), `core/ingestion/**`(PromptIngestionEngine, BaseAdapter, AdapterRegistry, PromptEnvelope, Pipeline, types — ~13 KB), `core/deploy/*`(DockerBuilder 6.6, K8sGenerator 6.8, index 0.3).
Admin/api: `core/admin-api/{activity,metrics,team-timeline}.ts`(9.6/3.2/1.9).
Other core: `core/hierarchy-bridge.ts`(18.5), `core/config-validator.ts`(8.9), `core/self-analysis.ts`(8.8), `core/context-snapshot-store.ts`→UNCERTAIN, `core/model-pool/templates.ts`(10.6), `core/utils/{atomic-fs,error-logging,format,parse-structured-response,persistence-metrics,resume-tokens,truncation}.ts`(~22 KB), `core/unified/{types,templates}.ts`(10.2/12.2→templates UNCERTAIN), `core/observability/telemetry.ts`→UNCERTAIN.

→ **Full machine-generated path+KB list is in `recon-data.json` (`d.deadFiles`).**

### 7.2 Types dead — 6 files · 60.2 KB
`types/log-events.ts`(3.4), `metadata.ts`(9.6), `reasoning-chain.ts`(24.2), `team-dependencies.ts`(10.3), +2 (see `recon-data.json`).

### 7.3 Dead in other subsystems (mostly BFS-artifact / config — verify, do not auto-delete)
- `webui/` 85 DEAD + 30 UNCERTAIN — **alias-`@/` artifacts**, package is live. Exclude from debt.
- `integrations/` 14 DEAD — external-host adapters are live externally. Exclude (these are *migration* targets, not deletions).
- `scripts/` 27 DEAD — manual tooling; individual scripts may be archived but are not runtime debt.
- `prism/` 2 DEAD — `vite-env.d.ts`(0.3), `vite.config.ts`(0.4) config; trivial.
- `extra_tests` 15 non-test DEAD — test fixtures/helpers/spikes.

**True cleanup debt ≈ 206 KB (`scripts/flu`) + webui artifact noise + ~806 KB core+types.** The defensible first-trunk deletion set is §7.1 (core) + §7.2 (types) ≈ **806 KB across 106 files**.

---

## 8. Biggest 25 Files in the Repo (heaviest modules — planner watchlist)

| KB | Path |
|---|---|
| 325.3 | `ai/src/models.generated.ts` |
| 185.0 | `core/intelligence/thalamus/index.ts` |
| 166.1 | `core/intelligence/mnemic-field/index.ts` |
| 158.2 | `core/daemon.ts` |
| 137.1 | `core/intelligence/constellation/constellation-pipeline.ts` |
| 132.2 | `core/intelligence/constellation/corpus.ts` |
| 124.0 | `core/admin-api/memory.ts` |
| 117.7 | `core/intelligence/helix/brainstem.ts` |
| 107.0 | `core/intelligence/helix/helix-posture-runner.ts` |
| 97.9 | `core/intelligence/aurora/index.ts` |
| 95.2 | `core/admin-api.ts` |
| 94.1 | `core/intelligence/constellation/meditation/meditation-store.ts` |
| 76.6 | `core/intelligence/mnemic-field/consolidation.ts` |
| 74.5 | `core/intelligence/mnemic-field/cortex.ts` |
| 71.4 | `core/intelligence/constellation/constellation-store.ts` |
| 67.1 | `webui/src/components/ui/icon/custom-icons.tsx` |
| 66.3 | `core/intelligence/flux-team/blackboard.ts` |
| 65.3 | `core/intelligence/cognitive-feed/message-formatter.ts` |
| 65.2 | `mcp/gateway/intelligence-tools.ts` |
| 63.1 | `core/intelligence/flux-team/blackboard-tools.ts` |
| 61.5 | `core/intelligence/aurora/larql-provider.ts` |
| 57.9 | `core/intelligence/constellation/meditation/index.ts` |
| 56.9 | `core/intelligence/constellation/meditation/organizing-synthesis.ts` |
| 56.3 | `core/intelligence/shared/posture-store.ts` |
| 56.0 | `integrations/opencode/src/cassicore.mjs` |

Note: `packages/larql/target/**` (build output, ~89 GB) and `data/**`/`vindexes/**` are excluded (not source).

---

## 9. Planner Recommendations (from the liveness evidence)

1. **Delete-first candidates** (safe): §7.1 core dead (~746 KB) + §7.2 types dead (~60 KB) — 106 files, no static/name/process reference. Verify UNCERTAIN (39 core files, ~236 KB) before deleting — they carry `@dep callers:`/config references.
2. **Standalone-plugin targets** (already package-shaped, live): `ai/`, `cassi-tui/`, `cassi-watch/`, `prism/`, `mind-plugin/`, `integrations/{claude-code,hermes-agent,opencode}/`, `webui/`.
3. **Subsystem carve-outs needing contract preservation**: `core/intelligence/*` (registry auto-discovery + createIntelligence manual wiring), `core/tools/*` (registerCoreTools tool-registry contract), `core/admin-api/*` + `mcp/gateway/*` (route/tool HTTP seams).
4. **Provider canonicalization**: `ai/src/providers/cassicore/*` is the live provider home; `core/providers/{qwen-coder,openai-compatible-base,pi-bridge}.ts/js` are dead duplicates — remove and confirm `ai` exports supply qwen/openai-compatible.
5. **Dead whole subsystems worth confirming as intentional removal**: `core/lsp/`, `core/ingestion/`, `core/adapters/`, `core/deploy/`, `core/hierarchy-bridge.ts`, the daemon boot-phase orchestrators, `core/tools/implementations/{edit-file,activity-tools,read-file-benchmark,skill,lsp-tool}`.

---

*Report generated from `recon-data.json` (machine-readable per-file classification: `d.deadFiles`, `d.uncertainFiles`, `d.subsystems`, `d.biggest`, `d.boundaries`) written alongside this report. Analysis script: `recon-analysis2.cjs` (rerun to refresh).*
