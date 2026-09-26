# P6 — Runtime Infra Packages (tools · model-pool · workflow · jobs · events · mcp · plugins · pipeline · utils) — Migration Table (Planning Deliverable)

**Sources (READ-ONLY, D:):** `core/tools/`, `core/model-pool/`, `core/workflow/`, `core/jobs/`, `core/events/`,
`core/mcp/`, `core/plugins/` (+ `core/plugin-host.ts`), `core/pipeline/`, `core/utils/` — under
`D:\carina\workspaces\cassicore\`
**Destinations:** `C:\Users\Carina\workspaces\Cassi\CassiCore\packages\{tools,model-pool,workflow,jobs,events,mcp,plugins,pipeline,utils}\src\`
**Recon:** `C:\Users\Carina\workspaces\Cassi\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\workspaces\Cassi\CassiCore\CASSI-MIND-PLAN.md` §5-P6, §4, §3e.1/§3e.4 (registry + registerCoreTools seams)
**Exemplars (house format):** `P1-foundation-migration-table.md`, `P2-helix-migration-table.md`,
`P3-flux-team-mini-helix-migration-table.md`, `P4-mnemic-field-migration-table.md`, `P5a-…`, `P5b-…`
**Date:** 2026-08-14
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the ONLY file written by this drafting pass; it is NOT git-added/committed (a parallel session
> commits in the workspace — this file must stay untracked; read-only on D:).

> **Inbound sweep is EXECUTOR-COMPUTED at P6 preflight.** Workspace state changes until then (landed packages
> re-point their own vendor stubs as their owning packages publish). §3 lists the EXPECTED inbound re-point set
> from the P1–P5 repoint logs + the landed vendor trees inspected at drafting; the executor MUST re-verify every
> stub by `grep` at preflight before touching it (§4 checklist).

---

## 1. Scope & boundary decisions (evidence-based; `[OPEN FLAG]` where a default is recommended)

### 1a. The nine packages and their source dirs

| package | source dir(s) (D:) | live-set | notes |
|---|---|---|---|
| `@cassicore/tools` | `core/tools/*` | 46 files | registry + executor + safety + `implementations/index.ts` (registerCoreTools) |
| `@cassicore/model-pool` | `core/model-pool/*` | 8 files | exclude `templates.ts` (DEAD) |
| `@cassicore/workflow` | `core/workflow/*` | 13 files | depends on foundation `types/workflow.ts` |
| `@cassicore/jobs` | `core/jobs/*` | 2 files | |
| `@cassicore/events` | `core/events/*` + `core/logger.ts` + `core/event-bus.ts` | 7 files | **P1 ASK-2 resolved** — see §1c |
| `@cassicore/mcp` | `core/mcp/*` | 4 files | **client-side** MCP; see §1d |
| `@cassicore/plugins` | `core/plugins/*` + `core/plugin-host.ts` | 8 files | **host side**; see §1e |
| `@cassicore/pipeline` | `core/pipeline/*` | 17 files | |
| `@cassicore/utils` | `core/utils/*` | 7 files | `paths.ts` already in foundation — see §1b |

**Total live files migrated in P6: 112 files, ≈1,053.6 KB of `.ts` source.**

### 1b. `core/utils/paths.ts` is NOT part of `@cassicore/utils` (already in foundation, P1)

`core/utils/paths.ts` was migrated to `@cassicore/foundation` `src/ports/paths.ts` in P1 (parameterized root
resolver). It is excluded from the `@cassicore/utils` live-set here. It is NOT in `deadFiles` — it is simply
owned elsewhere already. `@cassicore/utils` ships the 7 remaining live files only (§2.E). Consumers re-point
their `utils/paths` imports to `@cassicore/foundation` (the paths port), NOT to `@cassicore/utils`.

### 1c. `@cassicore/events` owns the logger + event-bus runtime defaults (P1 ASK-2 resolution)

P1's **[ASK-2]** (§5-P1, resolved "interface-only in P1, P6 provides default impls") lands definitively here:
- `core/logger.ts` → `src/logger.ts`: `Logger implements ILogger` + `rootLogger` singleton + file transport.
  Imports only Node builtins (`node:fs/os/path`) + foundation types (`types/events.js` → `LogLevel`,
  `types/interfaces.js` → `ILogger`, `types/runtime.js` → `Message`). **Self-contained; depends on foundation only.**
- `core/event-bus.ts` → `src/event-bus.ts`: `EventBus implements IEventBus` + `bus` singleton (ring-buffer).
  Imports `rootLogger` (from `./logger.js`) + foundation types (`types/events.js`, `types/interfaces.js`).
- `core/events/{index,event-api,event-types,cassandra-event-client,context-window-debug}.ts` → `src/events/*`:
  the event protocol/API + Cassandra client + context-window debugger. `event-api.ts` imports
  `core/config/resource-limits.js` (see §5c).

This is the single shared substrate every P0–P7 module imports for `ILogger`/`IEventBus` DEFAULT impls. The
`Logger`/`rootLogger`/`EventBus`/`bus` export names MUST be preserved verbatim (they are re-exported by
`core/events/index.ts` and consumed repo-wide).

### 1d. `core/mcp` vs `mcp/gateway` boundary (decided)

- **`@cassicore/mcp` (this phase) = `core/mcp/*`** — the **client-side** MCP integration: `MCPClient`
  (speaks to EXTERNAL MCP servers via `@modelcontextprotocol/sdk`), `MCPRegistry`, types, `index.ts` barrel.
- **`mcp/cassicore-gateway.ts` + `mcp/gateway/*` → `@cassicore/mcp-gateway` (P7)** — the **server-side**
  stdio/HTTP gateway exposing CassiCore's own tools to MCP clients.
- `core/mcp/index.ts` is `[UNCERTAIN]` in recon (live-name-ref:4) but is the canonical barrel (exports
  `MCPClient`, `MCPRegistry`, types) and is import-reachable by live files (`core/tools/implementations/vybit.ts`
  imports `MCPClient` from `core/mcp/client.js`). **Resolved: migrate it as the `@cassicore/mcp` package barrel.**
- **Known-hard (c):** `core/mcp/client.ts` imports `CASSICORE_VERSION` from `../daemon.js`. The canonical
  constant lives in `core/version.ts` (`CASSICORE_VERSION`, pure). Re-point to a vendored `core/version`
  stub (or a future `@cassicore/version` home) — NOT into the 158 KB daemon. See §5e + Open Flag 4.

### 1e. `@cassicore/plugins` = `core/plugins/*` + `core/plugin-host.ts` (host-side seam)

**Critical discovery:** `plugin-host.ts` lives at **`core/plugin-host.ts`, NOT `core/plugins/plugin-host.ts`**
(plan §5-P6 lists "core/plugins/* (the host side: plugin-host.ts, plugin-registry.ts, plugin-api.ts,
client-sdk.ts)" — the four files are split across two D: locations). The `@cassicore/plugins` package spans:
- `core/plugins/{index,client-sdk,plugin-api,plugin-registry}.ts` + `core/plugins/external-clients/{index,curator,types}.ts`
- `core/plugin-host.ts` → `src/plugin-host.ts` (the `PluginHost implements IPluginHost` fork-based worker manager)

This is the **ohmypi-relevant seam** (§1f) and the surface the overhaul session's mind-plugin consumes. Its
surfaces are quoted in §5f. The plan's `[VERIFY]` (Appendix B-3) that "the `ExtensionAPI`-shaped
client-sdk/plugin-api must stay exactly as the other session expects" is addressed in Open Flag 5.

### 1f. Registry & `registerCoreTools` contracts (P7 notes)

**`registerCoreTools` (the tools-registry seam contract, plan §3e.4 / §5-P6):** defined in
`core/tools/implementations/index.ts`:

```ts
export interface CoreToolDeps {
  memory?: IMemory                       // foundation types/intelligence
  sessionManager?: ISessionManager       // foundation types/runtime
  sessionStore?: SessionStore            // core/session-store (host, P7)
  bus?: IEventBus                        // foundation
  logger?: ILogger                       // foundation
  getPipeline?: () => TurnPipeline       // core/turn-pipeline (host, P7)
  subagentTracker?: { list/get/getByParent/getResult }
  eventHistory?: EventHistory            // core/event-history (host, P7)
  cognitiveToolDeps?: CognitiveToolDeps  // impl-internal
  peerToolDeps?: PeerToolDeps            // impl-internal
  getJobManager?: () => import('core/jobs/job-manager.js').JobManager | undefined
  collectThoughtsDeps?: CollectThoughtsDeps
  getWorkflowEngine?: () => import('core/workflow/engine.js').WorkflowEngine | null
  getWorkflowDefinitions?: () => Map<string, workflow.WorkflowDefinition>
  getWorkflowStore?: () => import('core/workflow/persistence.js').WorkflowStore | null
  getWorkflowDefStore?: () => import('core/workflow/definition-store.js').WorkflowDefinitionStore | null
}
export function registerCoreTools(registry: ToolRegistry, deps: CoreToolDeps): void
```
It registers 30+ tools across shell, file-I/O, task-tracking, desktop-vision, network, tests, background jobs,
memory, subagent inspection, event-query, cognitive (_reflect/_remember), peer-coordination (_coordinate/
_check_peers), collect-thoughts, cassandra-event, system-health, debug-session, universal-search, workflow, and
context-window debug tools. Many registrations are CONDITIONAL on optional deps (e.g. job tools only if
`deps.getJobManager`). **P7 note:** `@cassicore/tools` must keep `registerCoreTools(registry, deps)`'s exact
signature stable so P5-Packages/P7 admin-api/mcp can register against it. The `getJobManager`/`getWorkflow*`
lazy-getter types are `@cassicore/jobs` / `@cassicore/workflow`; the in-memory `core/events` singletons
(`getEventBus`, `getContextWindowDebugger`) are `@cassicore/events`.

**`ToolRegistry` auto-discovery contract:** `class ToolRegistry` exposes exactly `register(definition, handler)`,
`get(name)`, `list(options)` — a plain Map (no directory scan, no reflection). Tool "auto-discovery" is the
explicit `registerCoreTools` bulk-entry + the `list_tools` meta-tool (runtime discovery), NOT a scan. **P7 note
(plan §3e.1):** the DIRECTORY-SCAN auto-discovery replacing happens at the *IntelligenceRegistry*
(`core/intelligence/base/registry.ts`) level, which is host-side (P7) and NOT part of any P6 package. The tools
registry stays explicit-registration; `@cassicore/plugins`' `PluginAPI` also forwards tool registration
(`toolRegistry.register`) so plugins register tools through the same explicit path.

### 1g. Dead/uncertain exclusions per package (recon-data.json, verified)

| package dir | DEAD (excluded) | UNCERTAIN (quarantined) |
|---|---|---|
| `core/tools/*` | 10: `executor.instrumented.ts`, `instrumentation.ts`, `permission-gate.ts`, `resolver.ts`, `serena-types.ts`, `tool-selector.ts`, `implementations/{activity-tools,edit-file,read-file-benchmark,skill}.ts` | 6: `hermes-bridge.ts`, `read-tools.ts`, `serena-mcp-client.ts`, `implementations/{lsp-tool,peer-coordination-tools,think}.ts` |
| `core/utils/*` | 7: `atomic-fs.ts`, `error-logging.ts`, `format.ts`, `parse-structured-response.ts`, `persistence-metrics.ts`, `resume-tokens.ts`, `truncation.ts` | 2: `backoff.ts`, `session-serializer.ts` |
| `core/model-pool/*` | 1: `templates.ts` | 0 |
| `core/daemon/*` | 4: `boot-channels.ts`, `boot-providers.ts`, `boot-types.ts`, `channel-loader.ts` | 4 (host-side, P7): `boot-configuration.ts`, `boot-intelligence-pre.ts`, `boot-pipeline-tools.ts`, `intelligence-wiring.ts` |
| `core/workflow|jobs|events(except index)|mcp(except index)|plugins|pipeline` | 0 | 0 |
| `core/events/index.ts` | — | 0 (barrel, LIVE) |
| `core/mcp/index.ts` | — | **1 → RESOLVED LIVE** (§1d) |

> `core/daemon/*` is **NOT a P6 package** (it is `@cassicore/host`, P7). Its 4 DEAD + 4 UNCERTAIN files are
> recorded here only to close the phase's exclusion baseline (they never cross in P6).
> `core/config/resource-limits.ts` is LIVE and consumed only by `core/events/event-api.ts` → vendored in
> `@cassicore/events` (§5c), not a standalone P6 package.

---

## 2. Live-sets (files to migrate) per package

Recon verdicts are from `recon-data.json` (`deadFiles`/`uncertainFiles`). All listed files are **LIVE** (not in
either list, except where noted). **DEAD files never cross; UNCERTAIN quarantine** (do not import until resolved).

### 2.A `@cassicore/tools` — 46 files (11 top-level + 35 implementations), 487,645 B

**`src/*.ts` (depth 1) — 10 files** (top-level, minus DEAD/UNCERTAIN; no `core/tools/index.ts` exists — barrel written by packager):

| # | source (D:) | dest (packages/tools/src/) | bytes | recon |
|---|---|---|---|---|
| 1 | `core/tools/types.ts` | `types.ts` | 4034 | LIVE (ToolDefinition/ToolHandler/ToolExecutionContext/ToolRegistry types) |
| 2 | `core/tools/registry.ts` | `registry.ts` | 4972 | LIVE (`ToolRegistry` — the registerCoreTools target) |
| 3 | `core/tools/executor.ts` | `executor.ts` | 28201 | LIVE (`ToolExecutor`) |
| 4 | `core/tools/safety.ts` | `safety.ts` | 9289 | LIVE |
| 5 | `core/tools/reliability.ts` | `reliability.ts` | 9934 | LIVE |
| 6 | `core/tools/presentation.ts` | `presentation.ts` | 6458 | LIVE |
| 7 | `core/tools/scout.ts` | `scout.ts` | 12699 | LIVE |
| 8 | `core/tools/hermes-mcp-client.ts` | `hermes-mcp-client.ts` | 8501 | LIVE (plan §3a.3: keep) |
| 9 | `core/tools/hermes-tools.ts` | `hermes-tools.ts` | 14382 | LIVE (plan §3a.3: keep) |
| 10 | `core/tools/interactive-tool-session.ts` | `interactive-tool-session.ts` | 10681 | LIVE (zero imports — self-contained) |

**`src/hooks/external-hook-runner.ts` (depth 2) — 1 file** (row 11, 7105 B, LIVE).

**`src/implementations/*.ts` (depth 2) — 35 files** (DEAD exclusions: activity-tools, edit-file,
read-file-benchmark, skill; UNCERTAIN quarantine: lsp-tool, peer-coordination-tools, think):

| # | file | bytes | # | file | bytes |
|---|---|---|---|---|---|
| 12 | `index.ts` (registerCoreTools) | 14149 | 30 | `peer-coordination.ts` | 17463 |
| 13 | `cassandra-event.ts` | 9338 | 31 | `query-events.ts` | 14421 |
| 14 | `cassi-shell.ts` | 8859 | 32 | `read-file.ts` | 12627 |
| 15 | `check-job.ts` | 1711 | 33 | `read-files.ts` | 2241 |
| 16 | `cognitive-tools.ts` | 10170 | 34 | `run-background.ts` | 3071 |
| 17 | `collect-thoughts.ts` | 29056 | 35 | `run-tests.ts` | 8065 |
| 18 | `context-window-tools.ts` | 10027 | 36 | `shell-exec.ts` | 2835 |
| 19 | `debug-session.ts` | 14253 | 37 | `spawn-subagent-impl.ts` | 8961 |
| 20 | `desktop-vision.ts` | 20281 | 38 | `spawn-subagent.ts` | 3279 |
| 21 | `get-subagent-result.ts` | 5621 | 39 | `system-health.ts` | 8032 |
| 22 | `get-subagent-status.ts` | 5507 | 40 | `todo-write.ts` | 9912 |
| 23 | `graph-discover.ts` | 4680 | 41 | `universal-search.ts` | 12018 |
| 24 | `list-subagents.ts` | 4844 | 42 | `vybit-bug-ingest.ts` | 20301 |
| 25 | `list-tools.ts` | 2807 | 43 | `vybit-loop.ts` | 18137 |
| 26 | `memory-search.ts` | 6588 | 44 | `vybit.ts` | 26634 |
| 27 | `wait-job.ts` | 2018 | 45 | `web-fetch.ts` | 10237 |
| 28 | `web-search.ts` | 7506 | 46 | `workflow.ts` | 16408 |
| 29 | `write-file.ts` | 19332 | | | |

**Live-set: 46 files.**

> The 3 `.md` files in `core/tools/implementations/` (CASSANDRA_TOOLS_OPTIMIZATION.md, READ_FILE_OPTIMIZATION.md,
> TOOLS_OPTIMIZATION_SUMMARY.md) are docs, not code — exclude from history import (or port as package docs if the
> owner wants them, under a `[DECIDE]`; default: exclude).

### 2.B `@cassicore/model-pool` — 8 files, 90,623 B (exclude `templates.ts` DEAD)

| # | source (D:) | dest | bytes | recon |
|---|---|---|---|---|
| 1 | `core/model-pool/types.ts` | `types.ts` | 9829 | LIVE |
| 2 | `core/model-pool/index.ts` | `index.ts` | 14536 | LIVE (`ModelPool` class — barrel) |
| 3 | `core/model-pool/model-handle.ts` | `model-handle.ts` | 8836 | LIVE |
| 4 | `core/model-pool/fallback-manager.ts` | `fallback-manager.ts` | 17491 | LIVE |
| 5 | `core/model-pool/budget-manager.ts` | `budget-manager.ts` | 11079 | LIVE |
| 6 | `core/model-pool/billing-models.ts` | `billing-models.ts` | 13412 | LIVE |
| 7 | `core/model-pool/capability-cache.ts` | `capability-cache.ts` | 9483 | LIVE |
| 8 | `core/model-pool/model-capabilities.ts` | `model-capabilities.ts` | 5957 | LIVE |

Test to port: `core/model-pool/fallback-manager.test.ts` (17,467 B) → `tests/fallback-manager.test.ts`.

> **Provider-deps answer (known-hard b):** `@cassicore/model-pool` pulls **NONE** of the OpenAI/Anthropic/etc.
> client SDKs. It depends only on: `IProvider` **TYPE** from foundation `types/runtime.js`; `CostClassifier` from
> `core/providers/cost-classifier.ts` (**RUNTIME** — `billing-models.ts` imports it); `TTLCache` +
> `CircuitBreaker` from `core/utils` (`@cassicore/utils`); foundation `ILogger`/`IEventBus`. The provider client
> SDKs live in `ai/` (P8) and never enter model-pool. `CostClassifier` (self-contained: no imports, pure) → vendor
> stub in `@cassicore/model-pool`, re-pointed at P7/P8 when `@cassicore/ai` (or a cost-classifier home) publishes
> the canonical impl. See §5b + Open Flag 1.

### 2.C `@cassicore/workflow` — 13 files, 151,943 B (0 DEAD, 0 UNCERTAIN)

| # | source (D:) | dest | bytes | # | source | dest | bytes |
|---|---|---|---|---|---|---|---|
| 1 | `core/workflow/index.ts` | `index.ts` | 3124 | 8 | `core/workflow/registry.ts` | `registry.ts` | 2240 |
| 2 | `core/workflow/engine.ts` | `engine.ts` | 29524 | 9 | `core/workflow/scheduler.ts` | `scheduler.ts` | 14235 |
| 3 | `core/workflow/builder.ts` | `builder.ts` | 13675 | 10 | `core/workflow/state-machine.ts` | `state-machine.ts` | 9807 |
| 4 | `core/workflow/definition-store.ts` | `definition-store.ts` | 10683 | 11 | `core/workflow/steps.ts` | `steps.ts` | 19212 |
| 5 | `core/workflow/persistence.ts` | `persistence.ts` | 10790 | 12 | `core/workflow/templates.ts` | `templates.ts` | 15441 |
| 6 | `core/workflow/adapters.ts` | `adapters.ts` | 5270 | 13 | `core/workflow/trigger-store.ts` | `trigger-store.ts` | 12776 |
| 7 | `core/workflow/events.ts` | `events.ts` | 5166 | | | | |

All files land at depth 1 (`src/<file>.ts`).

> **`types/workflow.ts` already in foundation (P1).** Every workflow file imports `../../types/workflow.js` →
> `@cassicore/foundation` (package specifier). No re-vendoring of the workflow types.

### 2.D `@cassicore/jobs` — 2 files, 15,168 B (0 DEAD, 0 UNCERTAIN)

| # | source (D:) | dest | bytes |
|---|---|---|---|
| 1 | `core/jobs/job-manager.ts` | `job-manager.ts` | 12170 |
| 2 | `core/jobs/types.ts` | `types.ts` | 2998 |

### 2.E `@cassicore/utils` — 7 files, 28,920 B (exclude `paths.ts`→foundation; exclude 7 DEAD + 2 UNCERTAIN)

| # | source (D:) | dest | bytes |
|---|---|---|---|
| 1 | `core/utils/abort.ts` | `abort.ts` | 854 (`signalPromise`, `throwIfAborted`) |
| 2 | `core/utils/activity-timeout.ts` | `activity-timeout.ts` | 3836 |
| 3 | `core/utils/cached-value.ts` | `cached-value.ts` | 3923 |
| 4 | `core/utils/circuit-breaker.ts` | `circuit-breaker.ts` | 9256 |
| 5 | `core/utils/ids.ts` | `ids.ts` | 1657 |
| 6 | `core/utils/math.ts` | `math.ts` | 3016 |
| 7 | `core/utils/ttl-cache.ts` | `ttl-cache.ts` | 6378 |

**UNCERTAIN quarantine:** `backoff.ts`, `session-serializer.ts` (do not import until resolved — plan §3a.8 /
Appendix B-8). **DEAD:** atomic-fs, error-logging, format, parse-structured-response, persistence-metrics,
resume-tokens, truncation.

### 2.F `@cassicore/events` — 7 files, 84,953 B (runtime defaults + event protocol)

| # | source (D:) | dest | bytes |
|---|---|---|---|
| 1 | `core/events/index.ts` | `index.ts` | 1925 (barrel — re-exports bus + protocol types/classes) |
| 2 | `core/events/event-types.ts` | `events/event-types.ts` | 3767 |
| 3 | `core/events/event-api.ts` | `events/event-api.ts` | 20407 |
| 4 | `core/events/cassandra-event-client.ts` | `events/cassandra-event-client.ts` | 17201 |
| 5 | `core/events/context-window-debug.ts` | `events/context-window-debug.ts` | 10255 |
| 6 | `core/logger.ts` | `logger.ts` | 19940 (runtime `Logger`/`rootLogger`) |
| 7 | `core/event-bus.ts` | `event-bus.ts` | 11458 (runtime `EventBus`/`bus`) |

All at depth 1 except the 4 `events/` submodule files at depth 2 (cross-sibling `./event-types.js` etc. stay
internal). **0 DEAD, 0 UNCERTAIN** (the only UNCERTAIN was `core/mcp/index.ts`, not events).

### 2.G `@cassicore/mcp` — 4 files, 12,883 B

| # | source (D:) | dest | bytes |
|---|---|---|---|
| 1 | `core/mcp/index.ts` | `index.ts` | 184 (barrel; UNCERTAIN→RESOLVED live) |
| 2 | `core/mcp/client.ts` | `client.ts` | 4508 (`MCPClient`) |
| 3 | `core/mcp/registry.ts` | `registry.ts` | 6646 (`MCPRegistry`) |
| 4 | `core/mcp/types.ts` | `types.ts` | 1545 |

### 2.H `@cassicore/plugins` — 8 files, 73,994 B (host side incl. `core/plugin-host.ts`)

| # | source (D:) | dest | bytes |
|---|---|---|---|
| 1 | `core/plugins/index.ts` | `index.ts` | 639 (barrel) |
| 2 | `core/plugins/client-sdk.ts` | `client-sdk.ts` | 16244 (`CassiCoreClient`) |
| 3 | `core/plugins/plugin-api.ts` | `plugin-api.ts` | 20374 (`PluginAPI`) |
| 4 | `core/plugins/plugin-registry.ts` | `plugin-registry.ts` | 5682 (`PluginRegistry`) |
| 5 | `core/plugin-host.ts` | `plugin-host.ts` | 18594 (`PluginHost implements IPluginHost`) |
| 6 | `core/plugins/external-clients/index.ts` | `external-clients/index.ts` | 711 |
| 7 | `core/plugins/external-clients/curator.ts` | `external-clients/curator.ts` | 9678 |
| 8 | `core/plugins/external-clients/types.ts` | `external-clients/types.ts` | 2072 |

**0 DEAD, 0 UNCERTAIN.** (Plan §3a.1 lists `core/plugins` under the intelligence registry seam but these are
the host-side plugin files — no recon exclusion applies.)

### 2.I `@cassicore/pipeline` — 17 files, 132,803 B (excl. 1 test)

| # | source (D:) | dest | bytes |
|---|---|---|---|
| 1 | `core/pipeline/index.ts` | `index.ts` | 1732 (barrel) |
| 2 | `core/pipeline/adapter/index.ts` | `adapter/index.ts` | 252 |
| 3 | `core/pipeline/adapter/SessionPipeline.ts` | `adapter/SessionPipeline.ts` | 26630 |
| 4 | `core/pipeline/intelligence/index.ts` | `intelligence/index.ts` | 523 |
| 5 | `core/pipeline/intelligence/BackgroundProcessor.ts` | `intelligence/BackgroundProcessor.ts` | 6823 |
| 6 | `core/pipeline/intelligence/IntelligenceLayer.ts` | `intelligence/IntelligenceLayer.ts` | 8535 |
| 7 | `core/pipeline/session/index.ts` | `session/index.ts` | 1021 |
| 8 | `core/pipeline/session/SessionManager.ts` | `session/SessionManager.ts` | 10291 |
| 9 | `core/pipeline/session/types.ts` | `session/types.ts` | 7133 |
| 10 | `core/pipeline/session/stores/MemoryStore.ts` | `session/stores/MemoryStore.ts` | 3404 |
| 11 | `core/pipeline/session/stores/SQLiteStore.ts` | `session/stores/SQLiteStore.ts` | 9003 |
| 12 | `core/pipeline/turn/index.ts` | `turn/index.ts` | 854 |
| 13 | `core/pipeline/turn/ContextWindow.ts` | `turn/ContextWindow.ts` | 8818 |
| 14 | `core/pipeline/turn/MessageBuilder.ts` | `turn/MessageBuilder.ts` | 6354 |
| 15 | `core/pipeline/turn/overflow.ts` | `turn/overflow.ts` | 7953 |
| 16 | `core/pipeline/turn/ToolLoop.ts` | `turn/ToolLoop.ts` | 22533 |
| 17 | `core/pipeline/turn/TurnHandler.ts` | `turn/TurnHandler.ts` | 10944 |

Test to port: `core/pipeline/session/__tests__/SessionManager.test.ts` → `tests/`. **0 DEAD, 0 UNCERTAIN.**

---

## 3. Inbound sweep — EXPECTED re-point set (executor re-verifies by grep at preflight)

**Workspace state changes until P6 runs; the executor MUST re-derive this by grep before acting.** The list
below is the set implied by the P1–P5 repoint logs and the landed vendor trees inspected at drafting. Each row
is a vendored `src/vendor/<rel>` stub whose symbol(s) are now OWNED by a P6 package; the consumer's import is
re-pointed from `../vendor/...` to `@cassicore/<package>`, then the stub is **deleted**.

### 3.a Owned by `@cassicore/tools`

| consumer pkg | vendored stub | symbols | runtime-or-type |
|---|---|---|---|
| foundation (P1) | `vendor/core/tools/executor.ts` | `ToolExecutor` | type |
| foundation (P1) | `vendor/core/tools/registry.ts` | `ToolRegistry` | type |
| helix (P2) | `vendor/core/tools/executor.ts` | `ToolExecutor` (helix-pipeline, brainstem-types, posture-runner, index) | type |
| helix (P2) | `vendor/core/tools/registry.ts` | `ToolRegistry` | type |
| helix (P2) | `vendor/core/tools/types.ts` | `ToolDefinition`, `ToolHandler`, `ToolExecutionContext` | type |
| constellation (pre) | `vendor/tools/executor.ts` | `ToolExecutor` (constellation-orchestrator) | type |
| constellation (pre) | `vendor/tools/registry.ts` | `ToolRegistry` | type |
| constellation (pre) | `vendor/tools/types.ts` | `ToolDefinition`/`ToolCategory`/`ToolHandler` | type |
| constellation (pre) | `vendor/tools/implementations/collect-thoughts.ts` | `registerCollectThoughtsTool`-style impl | **RUNTIME** |
| constellation (pre) | `vendor/tools/implementations/graph-discover.ts` | graph-discover impl | **RUNTIME** |
| cognitive-feed (P5) | `vendor/core/tools/interactive-tool-session.ts` | `InteractiveToolSession` | **RUNTIME** |

### 3.b Owned by `@cassicore/model-pool`

| consumer pkg | vendored stub | symbols | runtime-or-type |
|---|---|---|---|
| foundation (P1) | `vendor/core/model-pool/types.ts` | `ModelHandle`, `ModelConfig` | type |
| helix (P2) | `vendor/core/model-pool/types.ts` | `ModelHandle`, `ModelConfig` | type |
| helix (P2) | `vendor/core/model-pool/index.ts` | `ModelPool` | **RUNTIME** |
| constellation (pre) | `vendor/model-pool/types.ts` | model-pool types | type |
| constellation (pre) | `vendor/model-pool/index.ts` | `ModelPool` | **RUNTIME** |
| mini-helix (P3) | `vendor/core/model-pool/types.ts` | model-pool types | type |

### 3.c Owned by `@cassicore/utils`

| consumer pkg | vendored stub | symbols | runtime-or-type |
|---|---|---|---|
| helix (P2) | `vendor/core/utils/abort.ts` | `signalPromise` | **RUNTIME** (brief-called "runtime-copied in helix's vendor") |
| helix (P2) | `vendor/core/utils/activity-timeout.ts` | `ActivityTimeout` | **RUNTIME** |
| mnemic-field (P4) | `vendor/core/utils/math.ts` | `clamp`, `lerp`, `remap` | **RUNTIME** (brief-called "runtime-copied in mnemic-field's vendor") |
| cortex-pineal-dialectic (P5) | `vendor/core/utils/activity-timeout.ts` | `ActivityTimeout` | **RUNTIME** |

> **Note:** `@cassicore/utils` ALSO resolves runtime imports directly in landed packages (not via vendor): e.g.
> `@cassicore/tools` executor imports `core/utils/ttl-cache.js`, model-pool imports `utils/{ttl-cache,circuit-breaker}`,
> `core/tools/implementations/*` import `utils/ids.js`. Those become `@cassicore/utils` package imports at *their own
> package's rewrite* (part of the P6 export surface), not inbound sweep. The inbound sweep is ONLY the
> already-vendored stubs being replaced.

### 3.d Owned by `@cassicore/workflow` / `@cassicore/pipeline` (inbound stubs from landed packages)

| consumer pkg | vendored stub | symbols | runtime-or-type |
|---|---|---|---|
| constellation (pre) | `vendor/workflow/builder.ts` | `WorkflowBuilder`, `createWorkflow`, `createStep` | **RUNTIME** |
| constellation (pre) | `vendor/workflow/engine.ts` | `WorkflowEngine`, `SuspendSignal` | **RUNTIME** |
| constellation (pre) | `vendor/workflow/steps.ts` | workflow step factories | **RUNTIME** |
| constellation (pre) | `vendor/workflow/templates.ts` | workflow template factories | **RUNTIME** |
| thalamus (P5) | `vendor/core/pipeline/turn/overflow.ts` | `ContextOverflowError`, `isOverflowError`, `reclassifyAsOverflow`, `stripToolFiller`, `hasQuestionResult`, `buildToolUseMapFromMessages` | **RUNTIME** |

> **`@cassicore/events`, `@cassicore/jobs`, `@cassicore/plugins` have NO inbound re-points** — no landed package
> vendored `core/events`, `core/jobs`, or `core/plugins` stubs (verified: `find packages -path '*/vendor/*' …`
> across all landed packages returned nothing for events/jobs/plugins). They are fresh packages. Their
> consumers (P7 host, mcp-gateway) bind at P7.

### 3.e P7-deferred (in the expected sweep but owned by LATER phases — do NOT delete in P6)

| consumer pkg | vendored stub | owning package | re-point at |
|---|---|---|---|
| helix (P2) | `vendor/mcp/gateway/index.ts` | `@cassicore/mcp-gateway` (top-level `mcp/gateway/`) | **P7** |

> The brief lists helix's `vendor/mcp/gateway` under the P6 expected sweep, but it mirrors the SERVER-side
> `mcp/gateway/` (P7 `@cassicore/mcp-gateway`), NOT the client-side `@cassicore/mcp` (this phase). It stays
> vendored through P6 and is re-pointed at P7. Flag for the executor: do not delete it in P6; the P6 sweep only
> touches stubs owned by the nine P6 packages.

---

## 4. Executor inbound-sweep checklist (verify by `grep` at P6 preflight)

Before starting any P6 import, the executor MUST run this and confirm every EXPECTED stub in §3 exists and no
unexpected one surfaced:

1. `grep -rn "vendor/core/model-pool" packages/*/src` → expect foundation, helix(×2: types+index), constellation(×2), mini-helix(types). **≥5 files to re-point.**
2. `grep -rn "vendor/core/tools" packages/*/src` → expect foundation(executor+registry), helix(executor+registry+types), constellation(executor+registry+types+implementations/×2), cognitive-feed(interactive-tool-session). **≥11 files.**
3. `grep -rn "vendor/core/utils" packages/*/src` → expect helix(abort+activity-timeout), mnemic-field(math), cortex-pineal-dialectic(activity-timeout). **≥4 files.**
4. `grep -rn "vendor/workflow" packages/*/src` → expect constellation(builder+engine+steps+templates). **≥4 files (RUNTIME).**
5. `grep -rn "vendor/core/pipeline" packages/*/src` → expect thalamus(turn/overflow). **1 file (RUNTIME).**
6. `grep -rn "vendor/mcp/gateway" packages/*/src` → expect helix(gateway/index) — **P7-deferred, DO NOT delete.** Confirm it still exists so P7 can re-point.
7. `grep -rn "vendor/core/events\|vendor/core/jobs\|vendor/core/plugins\|vendor/core/mcp" packages/*/src` → expect **EMPTY** (nothing landed before P6 vendored these).
8. For each stub found by the greps above, read its exports and confirm the P6 package's landed barrel re-exports the SAME symbol names before deleting the stub (a type-surface mismatch breaks the consumer at compile time).
9. Re-verify D: read-only discipline: `git -C <tmp-clone> log -1 --format=%H` for each imported core/* path matches the HEAD state you expect (§4.3 plan).

---

## 5. Known-hard items

### 5a. `@cassicore/tools` is the largest runtime surface; `registerCoreTools` seam stability

Full rewrite inventory (external specifiers by destination class). **Depth rule (P2/P4/P5 lesson):** all
`@cassicore/*` package specifiers are depth-agnostic (no prefix); only local `../vendor/...` stubs are
depth-aware — from `src/<file>.ts` (depth 1) the prefix is `../vendor/…`, from `src/{implementations,hooks}/…`
(depth 2) it is `../../vendor/…`.

**Foundation (`@cassicore/foundation`)** — `types/interfaces.js` (ILogger/IBus), `types/intelligence.js` (IMemory),
`types/runtime.js` (ISessionManager/Session/Message), `types/collect-thoughts.js`, `types/event-query.js`,
`config/system-settings.js` (MODEL_DEFAULTS/getModelSpec), `utils/paths.js` (getRepoRoot → foundation paths port).
Executor verifies each symbol in the landed foundation barrel.

**Landed P6 packages (package specifier):**
- `@cassicore/events`: `../event-bus.js`, `../logger.js` (rootLogger), `../../events/index.js` (getEventBus,
  getContextWindowDebugger), `../../events/context-window-debug.js` (ContextWindowDebugger type).
- `@cassicore/utils`: `utils/ttl-cache.js`, `utils/ids.js`, `utils/circuit-breaker.js`.
- `@cassicore/mcp`: `../../mcp/client.js` (MCPClient), `../../mcp/types.js` (MCPServerConfig) [vybit.ts].
- `@cassicore/jobs` (type): `../../jobs/job-manager.js` (JobManager) [registerCoreTools deps].
- `@cassicore/workflow` (type): `../../workflow/{engine,persistence,definition-store}.js` [registerCoreTools deps].

**Landed brain-region packages (P2–P5):** `../../intelligence/cortex/{index,types}.js` → `@cassicore/cortex-pineal-dialectic`;
`../../intelligence/thought-observer.js` + `../../intelligence/cognitive-bridge.js` → `@cassicore/foundation`? **NO** —
these are P5 siblings, not foundation. Verify how P5 landed them and re-point to the owning P5 package (collect-thoughts/
cognitive-tools/peer-coordination import them; the P5 table/landed exports decide — mark `[VERIFY]` at execution,
default vendor). `../../intelligence/mnemic-field/graph-attn-propagator.js` → `@cassicore/mnemic-field`;
`../../intelligence/{branching-conversation,synapse,thinker,permission-oracle,trust-ledger}/*` → own P5/aux packages
(`[DECIDE]` the exact package name for each; default vendor stub + re-point at owning phase).

**Host-side vendored stubs (P7 — `src/vendor/core/...`):** `event-history.js` (EventHistory), `event-query-parser.js`,
`event-query-presets.js`, `tool-proxy-middleware.js`, `session-store.js` (SessionStore), `turn-pipeline.js`
(TurnPipeline), `version.js` (CASSICORE_VERSION), `daemon.js` (any accidental import — expect none after re-point).
These are host deps that DO NOT cross in P6; faithful type stubs (+ runtime for the pure ones if executed at load).

**Executor ordering within `@cassicore/tools`:** land the package + barrel FIRST, re-point the inbound §3.a stubs
(foundation/helix/constellation/cognitive-feed), THEN the P6 package's own `@cassicore/*` rewires compile. Because
tools is the highest-fanout, its barrel must export `registerCoreTools`, `ToolRegistry`, `ToolExecutor`, the
`ToolDefinition`/`ToolHandler`/`ToolExecutionContext`/`ToolCategory` types, `toolExecutor`, and the impl tool
definitions consumers use.

### 5b. `@cassicore/model-pool` provider deps — `CostClassifier` (core/providers) is the only out-of-package runtime

`billing-models.ts` imports `CostClassifier` from `core/providers/cost-classifier.ts` (RUNTIME, used at model-pool
load to classify request cost). `cost-classifier.ts` is self-contained (zero imports, pure) and LIVE. **Default:
vendor a faithful runtime copy at `@cassicore/model-pool` `src/vendor/core/providers/cost-classifier.ts`
(re-point to `@cassicore/ai` or a cost-classifier home at P7/P8).** Do NOT add any OpenAI/Anthropic SDK — none is
needed (Open Flag 1 / Q).

### 5c. `@cassicore/events` — `core/config/resource-limits` vendoring

`core/events/event-api.ts` imports `DEFAULT_RESOURCE_LIMITS` from `core/config/resource-limits.ts` (LIVE, only
consumer is event-api). `resource-limits.ts` is NOT part of foundation (which ships only `system-settings.ts`) and
NOT a P6 package of its own. **Default: vendor `src/vendor/core/config/resource-limits.ts` in `@cassicore/events`
(faithful runtime copy — self-contained); re-point to foundation if the owner later absorbs resource-limits there.**
Open Flag 2.

### 5d. `@cassicore/pipeline` — `core/workspace/loader.js` dependency

`adapter/SessionPipeline.ts` imports `buildSystemPrompt` from `core/workspace/loader.js`. **`core/workspace/`
(instruction-discovery.ts, loader.ts, paths.ts) is NOT a P6 package** (its owning home is TBD — not in the nine
P6 packages). **Default: vendor a runtime stub `src/vendor/core/workspace/loader.ts` (buildSystemPrompt) in
`@cassicore/pipeline`; re-point at the phase that owns `core/workspace` (P7 host or a `@cassicore/workspace`
package).** Open Flag 3. Also `turn/*` import `core/intelligence/shared/token-estimation.js`
(`@cassicore/embeddings` Part E, landed) and `core/intelligence/thalamus/classifier.js` (`@cassicore/thalamus`,
P5-A) → package specifiers.

### 5e. `@cassicore/mcp` — `CASSICORE_VERSION` source

`core/mcp/client.ts` imports `CASSICORE_VERSION` from `core/daemon.js` (a re-export; the canonical constant is
`core/version.ts`, pure). **Default: re-point `CASSICORE_VERSION` to a vendored `src/vendor/core/version.ts`
(pure constant) in `@cassicore/mcp`; do NOT pull the 158 KB daemon.** Same for `@cassicore/tools`
`hermes-mcp-client.ts` (imports `core/version.js`). The future home of `core/version.ts` is `[OPEN]` (Open Flag 4).

### 5f. `@cassicore/plugins` — the ohmypi-relevant seam (surfaces to preserve verbatim)

This is the surface the overhaul session's mind-plugin consumes (plan §7). Preserve export names + shapes exactly
(foundation `types/plugin.ts` holds the protocol interfaces; the package should re-export OR import them from
`@cassicore/foundation` — those interfaces are already in foundation from P1):

- **`PluginAPI`** (`core/plugins/plugin-api.ts`): `class PluginAPI { constructor(deps: PluginAPIDeps); async handle(registration: PluginRegistration, message: PluginToCore): Promise<PluginAPIResult>; … }`. `PluginAPIDeps` = `{ logger, registry, sessions{…}, context{…}, memory{…}, intelligence{…}, eventBus{on,emit}, toolRegistry?{register} }` — the injected host facade. `PluginAPIResult = { ok, data?, error? }`.
- **`PluginRegistry`**: `class PluginRegistry { … }` (register plugins, track capability/manifest).
- **`CassiCoreClient`** (`client-sdk.ts`): `class CassiCoreClient { constructor(config: CassiCoreClientConfig); … }` — the client SDK (Node `http` to the daemon admin API).
- **`PluginHost`** (`core/plugin-host.ts` → `src/plugin-host.ts`): `class PluginHost implements IPluginHost { constructor(logger: ILogger); async load(manifest: PluginManifest): Promise<void>; … }` — fork-based worker manager (uses `core/worker-ipc.ts` protocol + `bus` from `@cassicore/events`).
- **External-client curator**: `ExternalClientCurator` + `CurationConfig`/`CurationMeta` (imports `@cassicore/thalamus` types).

The `IPluginHost`, `PluginManifest`, `PluginStatus`, `PluginRegistration`, `PluginToCore`, `PluginCapability`
interfaces live in foundation `types/plugin.ts` + `types/interfaces.ts` — the plugins package imports them from
`@cassicore/foundation` (do NOT re-vendor). **The two-session rule (plan §7):** this package must publish before
the overhaul session rewires against it; confirm they have NOT already rewritten `core/plugins/*` or
`core/plugin-host.ts` at P6-execution (Open Flag 5).

### 5g. `core/jobs` is clean (node builtins + foundation only)

`job-manager.ts` uses `node:child_process/fs/path/os` + foundation `IEventBus`/`ILogger` + its own `types.ts`.
No out-of-package runtime dep. `RingBuffer` is defined in `jobs/types.ts`. Simplest package in the phase.

---

## 6. Rewrite tables

House rules (identical to P1/P5): mirror vendor stubs at `src/vendor/<rel-from-D-repo-root>.ts`;
extension preserved verbatim (`.js` specifiers kept; dropped only for `@cassicore/*` package specifiers);
**scope rule**: do NOT touch Node builtins/npm; REWRITE only foundation/landed/`@cassicore/*`/vendor escapes on
actual `import`/`import type`/re-export/inline `import('…')`/`require()` statements (NOT string/comment content);
**global per-specifier replacement** (multiple occurrences — e.g. `../../runtime/audit/index.js` twice).

### 6.A `@cassicore/tools` rewrite pairs

**Depth prefixes:** depth-1 `src/<file>.ts` → vendor prefix `../vendor/…`; depth-2 `src/{implementations,hooks}/…`
→ `../../vendor/…`. Package specifiers (`@cassicore/*`) need no prefix.

| class | original specifier(s) | dest | count/files |
|---|---|---|---|
| **foundation** | `../../types/{interfaces,intelligence,runtime,collect-thoughts,event-query}.js`; `../../config/system-settings.js`; `../../utils/paths.js` | `@cassicore/foundation` | ~12 files |
| **`@cassicore/events`** | `../event-bus.js`; `../logger.js`; `../../events/{index,context-window-debug}.js` | `@cassicore/events` | 6 |
| **`@cassicore/utils`** | `../utils/{ttl-cache,ids,circuit-breaker}.js` | `@cassicore/utils` | 4 |
| **`@cassicore/mcp`** | `../../mcp/{client,types}.js` | `@cassicore/mcp` | 1 |
| **`@cassicore/jobs`** | `../../jobs/job-manager.js` (type) | `@cassicore/jobs` | 1 |
| **`@cassicore/workflow`** | `../../workflow/{engine,persistence,definition-store}.js` (type) | `@cassicore/workflow` | 1 |
| **landed brain-region** | `../../intelligence/{cortex,thought-observer,cognitive-bridge,branching-conversation,synapse,thinker,mnemic-field/graph-attn-propagator,permission-oracle,trust-ledger}/…` | `@cassicore/<pkg>` **or vendor** (`[VERIFY]` owning package) | ~8 |
| **host-side VENDOR** | `../event-history.js`, `../event-query-parser.js`, `../event-query-presets.js`, `../tool-proxy-middleware.js`, `../session-store.js`, `../turn-pipeline.js`, `../version.js` | `(../|../../)vendor/core/{event-history,event-query-parser,event-query-presets,tool-proxy-middleware,session-store,turn-pipeline,version}.ts` | 6 (RUNTIME/type per use) |
| **internal** | `./types.js`, `./registry.js`, `./safety.js`, `./presentation.js`, `./reliability.js`, `./hooks/external-hook-runner.js`, `./implementations/*`, `./[vybit].js` etc. | unchanged | — |
| **builtins/npm** | `node:…`, `@modelcontextprotocol/sdk` (none in tools) | unchanged | — |

> **Tally:** unique external rewrite targets ≈ **25** (foundation ~7 specifiers + 4 P6 packages + ~8 brain-region
> + ~6 host-vendor). Because the impl set is 35 files and many share specifiers, the executor applies per-specifier
> global replacement. Full per-file enumeration is the **executor's re-derived** task at preflight (the impl set is
> stable; read each file's import block against the §6.A map — see §4 step 8).

### 6.B `@cassicore/model-pool` rewrite pairs (all depth 1, `../vendor/…`)

| class | original | dest |
|---|---|---|
| foundation | `../../types/{interfaces,runtime}.js` | `@cassicore/foundation` |
| `@cassicore/utils` | `../utils/{ttl-cache,circuit-breaker}.js` | `@cassicore/utils` |
| provider VENDOR | `../providers/cost-classifier.js` (billing-models) | `../vendor/core/providers/cost-classifier.ts` (runtime) |
| internal | `./types.js`, `./fallback-manager.js`, `./budget-manager.js`, `./capability-cache.js`, `./model-handle.js`, `./model-capabilities.js`, `./billing-models.js` | unchanged |

Rewrite-pair total: **foundation(2) + utils(2) + cost-classifier(1) = 5 unique external targets.**

### 6.C `@cassicore/workflow` rewrite pairs (all depth 1)

| class | original | dest |
|---|---|---|
| foundation | `../../types/workflow.js`; `../../types/interfaces.js`; `../utils/paths.js` (getDataDir) | `@cassicore/foundation` |
| landed brain-region | `../intelligence/{helix,constellation}/*` (adapters.ts); `../tools/executor.js` (adapters.ts) | `@cassicore/helix`, `@cassicore/constellation`, `@cassicore/tools` |
| internal | `./steps.js`, `./builder.js`, `./engine.js`, `./events.js`, `./state-machine.js`, `./persistence.js`, `./definition-store.js`, `./registry.js`, `./scheduler.js`, `./trigger-store.js`, `./templates.js` | unchanged |
| npm | `better-sqlite3` (definition-store, persistence, trigger-store) | unchanged (add dep) |

Rewrite-pair total: **foundation(3) + 3 landed = 6 unique external targets.**

### 6.D `@cassicore/jobs` — 0 external rewrites (foundation + node builtins only). `types/runtime.js`→foundation if present (verified: only `types/interfaces.js`).**

### 6.E `@cassicore/utils` — 1 external rewrite

| class | original | dest |
|---|---|---|
| `@cassicore/events` | `../logger.js` (circuit-breaker.ts → rootLogger) | `@cassicore/events` |
| internal | `./abort.js` (activity-timeout → signalPromise) | unchanged |

Rewrite-pair total: **1 unique external target.**

### 6.F `@cassicore/events` rewrite pairs

| class | original | dest |
|---|---|---|
| foundation | `../types/{events,interfaces,runtime}.js` (logger, event-bus) | `@cassicore/foundation` |
| internal runtime | `./logger.js` (event-bus→rootLogger), `./event-bus.js` (events/*→bus), `../event-bus.js` (events/index) | unchanged (same package now) |
| config VENDOR | `../config/resource-limits.js` (event-api) | `../vendor/core/config/resource-limits.ts` (runtime) |
| npm | `node:http`, `node:events` | unchanged |

Rewrite-pair total: **foundation(3) + resource-limits(1) = 4 unique external targets.**

### 6.G `@cassicore/mcp` rewrite pairs

| class | original | dest |
|---|---|---|
| foundation | `../../types/interfaces.js` (ILogger) | `@cassicore/foundation` |
| `@cassicore/tools` | `../tools/{registry,types}.js` (registry.ts) | `@cassicore/tools` |
| version VENDOR | `CASSICORE_VERSION` from `../daemon.js` (client.ts) | `../vendor/core/version.ts` (runtime — pure constant) |
| npm | `@modelcontextprotocol/sdk` (client.ts) | unchanged (add dep) |

Rewrite-pair total: **foundation(1) + tools(2) + version(1) = 4 unique external targets.**

### 6.H `@cassicore/plugins` rewrite pairs

| class | original | dest |
|---|---|---|
| foundation | `../../types/{plugin,events,interfaces,runtime}.js` | `@cassicore/foundation` |
| `@cassicore/events` | `../core/event-bus.js` (plugin-host→bus) | `@cassicore/events` |
| landed brain-region | `../../intelligence/thalamus/{index,types}.js` (external-clients curator/types) | `@cassicore/thalamus` |
| npm | `node:http`, `node:os`, `node:path`, `node:crypto`, `node:child_process` | unchanged |

Rewrite-pair total: **foundation(4) + events(1) + thalamus(1) = 6 unique external targets.**

### 6.I `@cassicore/pipeline` rewrite pairs (depth varies — `src/…` to `src/{adapter,intelligence,session,turn}/…`)

| class | original | dest |
|---|---|---|
| foundation | `../../../types/{intelligence,interfaces,runtime}.js`; `../../config/system-settings.js` (SessionPipeline) | `@cassicore/foundation` |
| `@cassicore/embeddings` | `../../intelligence/shared/token-estimation.js` (ContextWindow, MessageBuilder, ToolLoop, TurnHandler) | `@cassicore/embeddings` |
| `@cassicore/thalamus` | `../../intelligence/thalamus/classifier.js` (ToolLoop) | `@cassicore/thalamus` |
| workspace VENDOR | `../../workspace/loader.js` (SessionPipeline → buildSystemPrompt) | `../vendor/core/workspace/loader.ts` (runtime) |
| internal | `./session/*`, `./turn/*`, `./intelligence/*`, `./adapter/*`, `./index.js` sub-barrels | unchanged |
| npm | `better-sqlite3` (SQLiteStore), `node:…` | unchanged (add dep) |

Rewrite-pair total: **foundation(3) + embeddings(1) + thalamus(1) + workspace(1) = 6 unique external targets.**

### 6.J Package-level npm dependencies (carry per package.json)

| package | npm deps from source | dev/notes |
|---|---|---|
| `@cassicore/tools` | (none beyond foundation/landed) | `@modelcontextprotocol/sdk` NOT used by core/tools |
| `@cassicore/model-pool` | (none) | |
| `@cassicore/workflow` | `better-sqlite3` | |
| `@cassicore/jobs` | (none) | |
| `@cassicore/events` | (none) | `node:http`, `node:events` builtins |
| `@cassicore/mcp` | `@modelcontextprotocol/sdk` | |
| `@cassicore/plugins` | (none) | |
| `@cassicore/pipeline` | `better-sqlite3` | |
| `@cassicore/utils` | (none) | |

The `@cassicore/*` inter-package deps are npm-workspace links resolved by the root workspaces array
(`packages/*`), matching the landed-package precedent.

---

## 7. Dest layout proposals

```
packages/{tools,model-pool,workflow,jobs,events,mcp,plugins,pipeline,utils}/
  package.json     # name @cassicore/<name>, type module, deps per §6.J
  tsconfig.json    # rootDir src/ outDir dist/ declaration true
  vitest.config.ts # ported tests
  README.md
  src/
    …:             # per §2 live-sets; mirror D: rel-paths under src/
    index.ts       # packager-written where source has no barrel:
                   #   tools (registerCoreTools, ToolRegistry, ToolExecutor, types, impl definitions)
                   #   utils (signalPromise, clamp, lerp, remap, TTLCache, CircuitBreaker, ids, …)
                   #   events (re-export bus + protocol; the source events/index.ts is the base barrel)
    vendor/        # stubs ONLY — mirror D: rel-paths (§5/§6): 
                   #   tools: core/{event-history,event-query-parser,event-query-presets,tool-proxy-middleware,
                   #           session-store,turn-pipeline,version}.ts + intelligence/* (unresolved own-pkg)
                   #   model-pool: core/providers/cost-classifier.ts
                   #   events: core/config/resource-limits.ts
                   #   mcp: core/version.ts
                   #   pipeline: core/workspace/loader.ts
```
> **`@cassicore/tools`, `@cassicore/utils`, `@cassicore/events`, `@cassicore/plugins`, `@cassicore/workflow` have**
> source barrels (`tools` NONE, `utils` NONE, `events`/`plugins`/`workflow`/`model-pool`/`mcp`/`pipeline` DO).
> Packager writes a fresh `index.ts` ONLY where the source dir has none: **tools, utils**.

### 7.1 Repoint log (P6-owning stubs → later phases)

| this-package stub | exported symbols | owning package | re-point at |
|---|---|---|---|
| tools `core/event-history.ts` | `EventHistory` | `@cassicore/host` (or events) | P7 |
| tools `core/event-query-parser.ts`, `core/event-query-presets.ts` | query parser/presets | `@cassicore/host` (or events) | P7 |
| tools `core/tool-proxy-middleware.ts` | `executeToolWithProxy` | `@cassicore/host` | P7 |
| tools `core/session-store.ts`, `core/turn-pipeline.ts` | `SessionStore`, `TurnPipeline` | `@cassicore/host` | P7 |
| tools+mcp `core/version.ts` | `CASSICORE_VERSION` | `@cassicore/version` (TBD) | P7/P8 (`[OPEN]`) |
| tools `core/intelligence/permission-oracle/*` | `PermissionOracle` | `@cassicore/trust` (P5) | P5-A |
| tools `core/intelligence/{branching-conversation,synapse,thinker}/*` | manager/type surfaces | owning P5 pkg | P5-A (`[OPEN]` exact pkg) |
| model-pool `core/providers/cost-classifier.ts` | `CostClassifier` | `@cassicore/ai` (or cost home) | P7/P8 |
| events `core/config/resource-limits.ts` | `DEFAULT_RESOURCE_LIMITS` | foundation (absorbs) | P7 (`[OPEN]`) |
| pipeline `core/workspace/loader.ts` | `buildSystemPrompt` | `@cassicore/workspace`/host | P7 |

---

## 8. Open flags (max 8 — defaults recommended)

1. **[OPEN-1] `CostClassifier` home (model-pool runtime dep).** Default: vendor a faithful runtime copy at
   `@cassicore/model-pool` `src/vendor/core/providers/cost-classifier.ts`; re-point at P7/P8 when `@cassicore/ai`
   (or a dedicated cost-classifier home) publishes the canonical impl. Model-pool pulls NO provider SDKs
   (OpenAI/Anthropic/etc.) — confirmed §5b. `[VERIFY] at execution cost-classifier is still self-contained +
   not moved.`
2. **[OPEN-2] `resource-limits.ts` placement (events dependency).** Default: vendor into `@cassicore/events`.
   If the owner prefers it in foundation (single config home), absorb `core/config/resource-limits.ts` into the
   foundation `config/` surface at P6 and re-point events. Default: vendor now, absorb later at P7 `[DECIDE]`.
3. **[OPEN-3] `core/workspace/*` owning package.** `core/workspace/{loader,instruction-discovery,paths}.ts` is
   NOT a P6 package. Default: `@cassicore/pipeline` vendors `loader.js` (runtime); the real home of
   `core/workspace` is resolved at P7 (host) or a dedicated `@cassicore/workspace`. `[VERIFY]` the overhaul
   session hasn't rewired `core/workspace`.
4. **[OPEN-4] `core/version.ts` home.** `CASSICORE_VERSION`/`CASSICORE_BUILD_STRING` (pure). Needed by
   `@cassicore/tools` (hermes-mcp-client) + `@cassicore/mcp` (client). Default: vendor `src/vendor/core/version.ts`
   in both; consider a tiny `@cassicore/version` package (or fold into foundation) at P7. `[DECIDE]`.
5. **[OPEN-5] `@cassicore/plugins` seam — overhaul handshake.** The plan §7 rule "package publishes before their
   rewiring" applies at P6 for the plugins/plugin-host surface. Confirm before importing that the overhaul session
   has NOT rewritten `core/plugins/*` or `core/plugin-host.ts` (they own the surface; see §5f). `[VERIFY]` at
   execution like the P4 mnemic-field + P7 handshakes.
6. **[OPEN-6] Tools brain-region imports — exact owning package names.** `core/intelligence/{cortex,thought-observer,
   cognitive-bridge,branching-conversation,synapse,thinker,permission-oracle,trust-ledger}/*` consumed by tools
   impls. The P5 groupings may not name each precisely (e.g. thought-observer/cognitive-bridge). Default: re-point
   to the P5-owned package when the landed barrel exports the symbol at execution; else vendor a faithful stub —
   **do NOT leave a `throw` on runtime symbols** (`_reflect`, `_coordinate`, collect-thoughts execute them).`
7. **[OPEN-7] `core/mcp/index.ts` UNCERTAIN resolution.** Confirmed live (barrel, import-reachable) → migrate.
   Record the resolution in the import commit body so future recon runs stop flagging it.
8. **[OPEN-8] `vybit.ts` / `vybit-loop.ts` / `vybit-bug-ingest.ts` external runtime deps.** `vybit.ts` imports the
   client MCP (`@cassicore/mcp`) and `vybit-loop`/`vybit-bug-ingest` import `@cassicore/events` (`getEventBus`).
   Confirm the VyBit loop's `child_process` usage is library-scoped (not a standalone entry) — it is (no
   `require.main`/`import.meta.url` fork) — before treating them as normal library files. `[VERIFY]` at execution.

---

## 9. Executor playbook (P6 later wave — verbatim)

1. **Preflight inbound sweep** — run §4's grep checklist against the CURRENT workspace state; reconcile any
   diff against §3 before proceeding (stale diffs = the landing packages re-pointed early; that's fine, just
   confirm no P6-owned stub remains).
2. Per package, follow §4.3 plan: temp-clone D: (history-only, `--no-checkout`), filter-repo `--path core/<dir>`
   (+ `--path core/plugin-host.ts` for plugins, `--path core/logger.ts` + `--path core/event-bus.ts` for events)
   with `--path-rename` to `packages/<name>/src`, mailmap, fetch `import/<name>`, splice
   (`--allow-unrelated-histories`), ADOPT THE SPLICE as import commit. Verify `git log --follow` provenance.
3. **Rewrite-delta commit** — apply the §6 rewrite maps globally-per-specifier; write packager barrels where
   needed (tools, utils); write vendor stubs (§5/§7); add `package.json`/tsconfig/vitest.
4. **Port tests** — `tests/` for each package (model-pool fallback-manager.test, pipeline SessionManager.test,
   plus any `core/**/__tests__/**` matching owned targets). Quarantine host-wired suites to `tests/host-wired/`
   (§6 plan).
5. **Inbound re-point commit(s)** — replace the §3 vendored stubs' consumers with `@cassicore/<pkg>` imports;
   delete each replaced stub. Do this AFTER the owning package publishes (e.g. tools before workflow? No —
   order: model-pool, utils, events, mcp, jobs, workflow, pipeline, plugins, tools LAST because tools is the
   highest-fanout and the inbound sweep targets its stubs in foundation/helix/constellation/cognitive-feed).
6. `npm run typecheck` (`tsc --noEmit`) per package; fix only mechanical path errors. Do NOT run full suites.
7. Confirm `git status` clean at phase end; D: untouched; `git log --follow` passes for every migrated tracked file.
8. Commit splits per plan §3c (history import ≠ rewrite delta ≠ inbound re-point; never mix).

---

## 10. Response summary (drafting-pass counts — per the task brief)

**Live-set counts per package (source `.ts`):**
- `@cassicore/tools` — **46** files (11 top + 35 impl), 487,645 B
- `@cassicore/model-pool` — **8** files, 90,623 B
- `@cassicore/workflow` — **13** files, 151,943 B
- `@cassicore/jobs` — **2** files, 15,168 B
- `@cassicore/events` — **7** files, 84,953 B (+ vendored `config/resource-limits`)
- `@cassicore/mcp` — **4** files, 12,883 B
- `@cassicore/plugins` — **8** files (incl. `core/plugin-host.ts`), 73,994 B
- `@cassicore/pipeline` — **17** files, 132,803 B
- `@cassicore/utils` — **7** files, 28,920 B (`paths.ts` → foundation)
- **TOTAL: 112 files, ≈1,053.6 KB**

**Rewrite-pair totals by class (unique external specifier targets):**
- tools: **~33** (foundation ~7 specifiers: interfaces/intelligence/runtime/collect-thoughts/event-query/
  system-settings/utils-paths; `@cassicore/events` 3: event-bus, logger, events/index+context-window-debug;
  `@cassicore/utils` 3: ttl-cache, ids, circuit-breaker; `@cassicore/mcp` 2: client, types; `@cassicore/jobs` 1;
  `@cassicore/workflow` 3: engine/persistence/definition-store; brain-region ~7 (cortex, thought-observer,
  cognitive-bridge, branching-conversation, synapse, thinker, permission-oracle, trust-ledger — owning pkg
  `[VERIFY]`, §8 Open-6); host-side vendor 7: event-history, event-query-parser, event-query-presets,
  tool-proxy-middleware, session-store, turn-pipeline, version) — the phase's largest rewrite surface.
- model-pool: 5 · workflow: 6 · jobs: 0 · utils: 1 · events: 4 · mcp: 4 · plugins: 6 · pipeline: 6
- Global + per-file replacement is specifier-based (35-file impl set for tools), so "pairs" above are unique
  specifier targets, not literal file×pair products.

**Expected inbound sweep:** §3 — foundation{tools/executor, tools/registry, model-pool/types},
helix{tools/executor+registry+types, model-pool/types+index, utils/abort+activity-timeout, mcp/gateway(P7-DEFERRED)},
constellation{tools/executor+registry+types+implementations{collect-thoughts,graph-discover}, model-pool/types+index,
workflow{builder,engine,steps,templates}}, mini-helix{model-pool/types}, mnemic-field{utils/math},
cognitive-feed{tools/interactive-tool-session}, cortex-pineal-dialectic{utils/activity-timeout},
thalamus{pipeline/turn/overflow}. No landed package vendored events/jobs/plugins or client-side core/mcp. Executor
re-derives by grep (§4) because workspace state changes until P6.

**Open flags:** 8 total (§8) — Open-1 CostClassifier home, Open-2 resource-limits, Open-3 core/workspace,
Open-4 core/version, Open-5 plugins overhaul handshake, Open-6 tools brain-region owning packages,
Open-7 core/mcp/index UNCERTAIN (resolved), Open-8 vybit runtime deps.
