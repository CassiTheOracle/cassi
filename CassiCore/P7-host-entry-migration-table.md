# P7 — Entry Surfaces + Thin Host (admin-api · mcp-gateway · commands · workers · providers · host) — Migration Table (Planning Deliverable)

**Sources (READ-ONLY, D:):** `core/admin-api.ts` + `core/admin-api/`, `mcp/` (top-level gateway + `gateway/`),
`commands/`, `workers/`, `core/entry/`, `core/daemon.ts` (158 KB) + `core/daemon/`, `core/cli/`, `core/providers/`
(live only), `core/bridge/`, `core/observability/`, `core/unified/` (live only), `core/ingestion/` (live only),
`core/adapters/` (live only), `core/version.ts`, `bin/`, `scripts/*.ts` (live only) — under
`D:\carina\workspaces\cassicore\`
**Destinations:** `C:\Users\Carina\Workspaces\CassiCore\packages\{admin-api,mcp-gateway,commands,workers,providers,host}\src\`
**Recon:** `C:\Users\Carina\Workspaces\CassiCore\recon-data.json`
**Plan:** `C:\Users\Carina\Workspaces\CassiCore\CASSI-MIND-PLAN.md` §5-P7, §4, §3e (seams registry-discovery /
resolveWorker / admin+mcp route contracts / registerCoreTools / standalone entries), §7 (overhaul handshake)
**Exemplars (house format):** `P1-foundation-migration-table.md`, `P6-runtime-infra-migration-table.md`,
`P5a-…`, `P5b-…`
**Date:** 2026-08-14
**Status:** PLANNING — executor applies rules verbatim in a later wave. Nothing migrated, nothing committed.

> **Constraint honored:** no file under `D:\carina\workspaces\cassicore` is modified (plan §5 line 27). This
> deliverable is the ONLY file written by this drafting pass; it is NOT git-added/committed (a parallel session
> commits in the workspace — this file must stay untracked; read-only on D:).

> **Inbound sweep is EXECUTOR-COMPUTED at P7 preflight.** Workspace state changes until then (landed packages
> re-point their own vendor stubs as their owning packages publish). §3 lists the EXPECTED inbound re-point set
> from the P6 repoint log + the landed vendor trees inspected at drafting; the executor MUST re-verify every
> stub by `grep` at preflight before touching it (§4 checklist). **P6 deferred helix's `vendor/mcp/gateway`
> stub re-point to P7 — that is a headline item of this phase's sweep.**

---

## 1. Scope & boundary decisions (evidence-based; `[OPEN FLAG]` where a default is recommended)

### 1a. The six P7 packages (five plan packages + `@cassicore/providers`) and their source dirs

| package | source dir(s) (D:) | live-set | notes |
|---|---|---|---|
| `@cassicore/admin-api` | `core/admin-api.ts` + `core/admin-api/*` | 55 files | HTTP route contract = package surface; exclude 3 DEAD routes; 1 UNCERTAIN |
| `@cassicore/mcp-gateway` | `mcp/cassicore-gateway.ts`, `mcp/gateway/*`, `mcp/{scip-server,gitnexus-server,serena-server}.*` | 42 files | server-side MCP stdio/HTTP; client-side `core/mcp/*` stayed in P6 `@cassicore/mcp` |
| `@cassicore/commands` | `commands/*` + `core/commands.ts` | 9 files | `core/commands.ts` (`CommandDispatcher`) is host-coupled; see §1b |
| `@cassicore/workers` | `workers/*` | 8 files | `resolveWorker` contract → package-relative; see §1d |
| `@cassicore/providers` | `core/providers/*` (live only) | 18 files | model provider SDK clients; exclude 5 DEAD + 4 UNCERTAIN |
| `@cassicore/host` | `core/entry/*`, `core/daemon.ts`, `core/daemon/*` (live), `core/cli/*`, `bin/*`, `scripts/qwen-renew-accounts.ts` (live), `core/version.ts` | ~34 files (see §2.H) | the THIN host — composes every landed package, wires ports, boots |

**Host-adjacent live files without a P6/home were assigned here with evidence (§1c) — `core/bridge/`,
`core/observability/`, `core/unified/`, `core/ingestion/`, `core/adapters/` live leftovers fold into
`@cassicore/host` `src/vendor/` or a `@cassicore/runtime-extras` (see §1c / §2.H).**

**Total live files migrated in P7: ~166 source files (55 + 42 + 9 + 8 + 18 + ~34), plus host-vendored
integrations.** Exact byte sum is deferrable to the executor (byte counts drift in D: — the overhaul session is
live-editing). The live-set enumerations in §2 are authoritative.

### 1b. `@cassicore/commands` must span `core/commands.ts` (the `CommandDispatcher`) — NOT just `commands/`

The daemon imports `CommandDispatcher` from `./commands.js` (line 19 of `core/daemon.ts`), which resolves to
**`core/commands.ts`** (root core file), NOT `commands/index.ts`. `core/commands.ts` imports from
`../commands/universal-processor.js`, `../commands/cassi-commands.js`, `./tools/interactive-tool-session.js`,
`./event-bus.js`, foundation types. The `commands/` directory (8 files) is the command-module family the
dispatcher consumes. Both are LIVE and **must land in the same package**:

- `core/commands.ts` → `src/commands.ts` (the `CommandDispatcher` class the host instantiates)
- `commands/{index,cassi-commands,cassicore-commands,git-commands,qwen-commands,team-commands,tool-commands,universal-processor}.ts` → `src/commands/*`.

**Live-set: 9 files.**

### 1c. Host-adjacent live files — assignment decision (evidence-first)

| D: path | recon | count | assignment |
|---|---|---|---|
| `core/providers/*` | 5 DEAD / 4 UNCERTAIN / 18 LIVE | 18 | `@cassicore/providers` (P7) — model provider SDK clients |
| `core/bridge/acp/{bin,client,server,translator,types}.ts` + `core/bridge/openai.ts` | 1 UNCERTAIN (`acp/index.ts`) / 6 LIVE | 6 (live) | `@cassicore/host` `src/bridge/*` (`bin.ts` is a standalone entry, §1f). `acp/index.ts` [UNCERTAIN] quarantined. |
| `core/observability/telemetry.ts` | 1 UNCERTAIN | 0 live | quarantine; no observability package needed — host absorbs or it stays in D: |
| `core/unified/*` | 1 DEAD (`types.ts`) / 1 UNCERTAIN (`templates.ts`) | 0 live | nothing to migrate (both excluded) |
| `core/ingestion/*` | 5 DEAD / 2 UNCERTAIN | 0 live | whole subsystem dead — nothing migrates |
| `core/adapters/*` | 3 DEAD | 0 live | whole subsystem dead — nothing migrates |
| `core/version.ts` | LIVE | 1 | `@cassicore/host` (source of `CASSICORE_VERSION` / `CASSICORE_BUILD_STRING`) — resolves P6 Open-4 |
| `scripts/qwen-renew-accounts.ts` | LIVE | 1 | `@cassicore/host` `src/scripts/…` (or a host bin) — the only ALIVE `scripts/*.ts`; imports `ai/src/providers/cassicore/qwen.js` (P8 [ASK]) |

> **`@cassicore/runtime-extras` (P7-SPECIFIC):** if the owner prefers bridge/observability/unified live files be
> a SEPARATE package rather than folded into the host, a `@cassicore/runtime-extras` package is the fallback
> home (Open Flag 6). **Default: fold the bridge live files into `@cassicore/host`** — they are spawn/bind
> integration, exactly the host's job; observability/unified/ingestion/adapters have NO live files to carry.

### 1d. `@cassicore/workers` — `resolveWorker` contract (plan §3e.2)

`core/daemon.ts` resolves channel workers by **relative FS path** then loads via `PluginHost.load({ entryPoint })`:

```ts
// core/daemon.ts:929-935 — the resolveWorker contract
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const resolveWorker = (relPath: string): string | null => {
  const jsPath = path.resolve(__dirname, `${relPath}.js`)
  if (fs.existsSync(jsPath)) return jsPath
  const tsPath = path.resolve(__dirname, `${relPath}.ts`)
  if (fs.existsSync(tsPath)) return tsPath
  return null
}
```

Call sites (all in the channels phase of `start()`): `resolveWorker("../workers/echo-channel")` (line 941),
`resolveWorker("../workers/channels/webchat")` (962), `resolveWorker("../workers/channels/cli")` (989),
`resolveWorker("../workers/channels/telegram")` (1022), `resolveWorker("../workers/channels/opencode")` (1049).

**Package-relative replacement (plan §3e.2):** `@cassicore/host` resolves worker entrypoints by package name —

```ts
resolveWorker('@cassicore/workers/channels/webchat')      // → packages/workers/src/channels/webchat.ts
resolveWorker('@cassicore/workers/channels/cli')          // → packages/workers/src/channels/cli.ts
resolveWorker('@cassicore/workers/echo-channel')          // → packages/workers/src/echo-channel.ts
```

**`PluginHost.load({ entryPoint })` (P6 `@cassicore/plugins` fork-manager) requires a resolvable path.** The host
supplies a `src/vendor/…` resolver that maps `@cassicore/workers/...` package specifiers to the package's compiled
`dist/channels/…` (or `src/` under tsx). Verify the P6 `PluginHost.load` `entryPoint` type accepts a package
specifier string at P7-execution; if it needs a FS path, the host's `resolveWorker` returns `new URL(import.meta.resolve(spec)).pathname`.

**Ghost reference found:** the daemon resolves `"../workers/channels/opencode"` (line 1049) but **no
`workers/channels/opencode.*` file exists** in the D: working tree (only cli, telegram, telegram-common, webchat,
markdown/*, echo-channel). The `resolveWorker` null-return guards it silently. **Do NOT create an opencode worker**
in P7; keep the daemon's guard. The plan §5-P7's "opencode" channel wording is a phantom — the opencode channel
was never a source worker. Record in the workers package DONE.

### 1e. `@cassicore/admin-api` — HTTP route contract (the package's public surface; plan §3e.5)

**Mounting surface (from `core/admin-api.ts`):**

```ts
// core/admin-api.ts:114-119 — route registry the host mounts
export function createAdminApi(daemon: any, logger: ILogger) {
  const runtime = createAdminRuntimeFacade(daemon)
  const unixPath = path.join(os.homedir(), '.cassicore', 'admin.sock')
  const tcpHost = (daemon?.config?.get?.('admin.host', '127.0.0.1')) ?? '127.0.0.1'
  const baseTcpPort = Number(daemon?.config?.get?.('admin.port', 7433)) || 7433
  ...
  async function start() {   // binds Unix socket + TCP server over `handler`
    ... http.createServer(handler) ... .listen(unixPath, ...)
    ... s.listen(tryPort, tcpHost, ...)   // EADDRINUSE → port-scan up
  }
  async function stop() {...}
  return { start, stop, tcpServer, unixServer, tcpPort, unixPath }
}
```

**Dispatch contract (from `handler` at 2285 + the route module headers):**

```ts
// core/admin-api.ts:2285-2288 — routing key is the pathname parts
async function handler(req: http.IncomingMessage, res: http.ServerResponse) {
  const url = new URL(req.url || '', `http://${tcpHost}:${currentTcpPort}`)
  const parts = url.pathname.split('/').filter(Boolean)
  ...
  // per-route dispatch, e.g.:
  () => handleSessionsRoutes({ runtime, logger, sendJSON, parseBody, getFirstUserMessage,
                                getLastUserMessage, tcpHost, currentTcpPort }, req, res, method, pathname, parts),
  () => handleMemoryRoutes({ daemon, logger, sendJSON, parseBody, url, parts }, req, res, method),
  ...
```

**Route-module contract (exemplar `core/admin-api/sessions.ts`):**

```ts
// core/admin-api/sessions.ts
import type { AdminRuntimeFacade } from './runtime.js'
export interface SessionsRoutesDeps { runtime: AdminRuntimeFacade; logger: ILogger;
  sendJSON: ...; parseBody: ...; getFirstUserMessage: ...; getLastUserMessage: ...;
  tcpHost: string; currentTcpPort: number }
export async function handleSessionsRoutes(deps: SessionsRoutesDeps, req, res, method, pathname, parts): Promise<boolean>
```

`createAdminRuntimeFacade(daemon)` (in `core/admin-api/runtime.ts`) is the **host-facade seam** — it wraps the
daemon's `turn-routing.js` helpers (`executeTurn`, `getPreferredTurnEngine`, `cancelTurn`, `ensureLegacySession`,
etc.) into an `AdminRuntimeFacade` the route modules consume. **The package exports the route registry +
`createAdminApi` + the facade; the host mounts it (daemon.ts:3255).** The HTTP route contract = `parts[0]` namespaced
paths (`sessions`, `memory`, `intelligence`, `health`, …) + `method` — this MUST be preserved verbatim.

**Port:** `admin.host` default `127.0.0.1`; `admin.port` default `7433`; Unix socket `~/.cassicore/admin.sock`.
The gateway's `CASSICORE_URL` defaults to `http://localhost:7433` (matches).

### 1f. Standalone process entries (plan §3e.3) — keep their own bin/host spawn

| entry | path (D:) | transport/port | becomes |
|---|---|---|---|
| `core/entry/index.ts` | supervisor (fork `daemon-main` with IPC heartbeat) | fork + IPC | `@cassicore/host` `bin/cassicore` |
| `core/entry/daemon-main.ts` | run `Daemon` directly | — | `@cassicore/host` `src/entry/daemon-main.ts` |
| `core/entry/vindex-loader.ts` | LARQL vindex HTTP sidecar | `127.0.0.1:7434` | `@cassicore/host` bin (`cassi-vindex-loader`) |
| `core/bridge/acp/bin.ts` | ACP agent stdio server | stdio (bin `cassi-acp`) | `@cassicore/host` bin (`cassi-acp`) |
| `core/cli/runtime/background-launcher.cjs` | CLI background worker spawner | spawn + socket | `@cassicore/host` `src/cli/runtime/` |
| `core/entry/code-extractor.ts` | supervisor-context / standalone DB extract | better-sqlite3 | `@cassicore/host` `src/entry/code-extractor.ts` |

**bin mappings to preserve** (verified in D:): `bin/cassicore` → `core/cli/index.ts` (`exec "$TSX" core/cli/index.ts`);
`bin/cassi-acp` → `core/bridge/acp/bin.ts`. After migration the host's `package.json` `bin` entries re-point to the
package's compiled `dist/` (or tsx launcher).

### 1g. Dead/uncertain exclusions per package (recon-data.json, verified)

| package dir | DEAD (excluded) | UNCERTAIN (quarantined) |
|---|---|---|
| `core/admin-api/*` | 3: `activity.ts`, `metrics.ts`, `team-timeline.ts` | 1: `system-prompt.ts` |
| `core/daemon/*` | 4: `boot-channels.ts`, `boot-providers.ts`, `boot-types.ts`, `channel-loader.ts` | 4: `boot-configuration.ts`, `boot-intelligence-pre.ts`, `boot-pipeline-tools.ts`, `intelligence-wiring.ts` |
| `core/providers/*` | 5: `claude-code-bridge/{defer-tool-hook,ephemeral-mcp-server}.mjs`, `openai-compatible-base.js`, `pi-bridge.ts`, `qwen-coder.ts` | 4: `copilot-sdk/index.ts`, `hermes-bridge.ts`, `opencode-go.{js,ts}` |
| `core/bridge/*` | 0 | 1: `acp/index.ts` |
| `core/observability/*` | 0 | 1: `telemetry.ts` |
| `core/unified/*` | 1: `types.ts` | 1: `templates.ts` |
| `core/ingestion/*` | 5 (whole family) | 2: `core/index.ts`, `pipeline/Pipeline.ts` |
| `core/adapters/*` | 3 (whole family) | 0 |
| `mcp/*`, `commands/*`, `workers/*`, `core/entry/*`, `core/cli/*`, `core/version.ts`, `core/daemon.ts`, `core/admin-api.ts`, `core/commands.ts` | 0 | 0 (all LIVE — verified) |

> **`boot-intelligence-pre.ts` / `boot-pipeline-tools.ts` / `intelligence-wiring.ts` / `boot-configuration.ts`
> (UNCERTAIN, live-name-refs):** these carry `@dep` name-string references. **Default: quarantine** — do not import
> until a worker resolves their intent (are they invoked by name from daemon's `start()`?). The P7 host needs
> `boot-intelligence-pre` (registry pre-wiring) and `boot-pipeline-tools` (tools pre-wiring) if daemon calls them by
> string; resolve at preflight. **`boot-intelligence-post.ts` is confirmed LIVE + port-injected** (§5) — keep it.

---

## 2. Live-sets (files to migrate) per package

Recon verdicts are from `recon-data.json`. All listed files are **LIVE** (not in `deadFiles`/`uncertainFiles`,
except where noted). **DEAD files never cross; UNCERTAIN quarantine.**

### 2.A `@cassicore/admin-api` — 55 files (1 root + 54 route modules/tests), ~1.1 MB

**`src/` (depth 0) — 1 file:**

| # | source (D:) | dest (packages/admin-api/src/) | bytes | recon |
|---|---|---|---|---|
| 1 | `core/admin-api.ts` | `admin-api.ts` | 97476 | LIVE (`createAdminApi` — route registry + server mount) |

**`src/routes/` (depth 1, from `core/admin-api/`) — 54 LIVE files** (**excluded: `activity.ts`, `metrics.ts`,
`team-timeline.ts` [DEAD], `system-prompt.ts` [UNCERTAIN]**). Route modules import `./runtime.js` (facade),
`../../types/…`, `node:http`, and the daemon runtime facade. `index.ts` (barrel) + `runtime.ts` (the
`createAdminRuntimeFacade` host-facade) land first in the package. The exact 54-file list (all from the live dir):**

`index.ts`, `runtime.ts`, `turn-routing.ts`, `intelligence.ts`, `blackboard.ts`, `channels.ts`, `chat.ts`,
`code-store.ts`, `config.ts`, `constellation.ts`, `context-repo.ts`, `context.ts`, `cortex.ts`, `cycle-hooks.ts`,
`debug.ts`, `delegation.ts`, `dialectic.ts`, `dmn.ts`, `dreamer.ts`, `events.ts`, `health.ts`, `helix-sessions.ts`,
`helix.ts`, `improvement.ts`, `jobs.ts`, `lamina.ts`, `maintenance.ts`, `mcp.ts`, `meditation.ts`, `memory.ts`,
`model-directive.ts`, `models.ts`, `modules.ts`, `observability.ts`, `orchestration.ts`, `permissions.ts`,
`pineal.ts`, `plugin-api.ts`, `plugins.ts`, `prism.ts`, `prompt-log.ts`, `providers.ts`, `replay.test.ts` (test),
`replay.ts`, `reverie.ts`, `sessions.ts`, `subagents.ts`, `teams.ts`, `thalamus.ts`, `timeline.ts`, `tools.ts`,
`training.ts`, `verification.ts`, `warm-provider.ts` — **54 files = 53 route/flagship `*.ts` + `replay.test.ts`.**

**The 50+ route-module claim in plan §5-P7 is confirmed (53 route modules + the `index.ts`/`runtime.ts` facade).**
Exact byte-per-file enumeration is the executor's re-derivation at preflight (58-file dir − 3 DEAD − 1 UNCERTAIN = 54).

> **`core/admin-api.ts` external deps (the package's rewrite surface):** aggregates to ~90 unique specifiers across
> the 55 files (full list captured at drafting): foundation `types/*` (interfaces, runtime, dialectic, flux-team,
> events, plugin, trace, blackboard-search), `config/system-settings`, `utils/paths`, landed brain-regions
> (intelligence/{mnemic-field,lamina,cortex,thalamus,pineal,reverie,helix,flux-team,embeddings,constellation,
> context-repo} + synapse + context-assembler), P6 packages (plugins, jobs, mcp/registry), providers (live), and
> **host-coupled** `session-store`, `turn-pipeline`, `timeline-store`, `testing/*`, `workspace/loader`, `daemon.js`,
> `scripts/qwen-renew-accounts.js`, `mcp/gateway/index.js`. See §6.A for the rewrite map — the admin-api package is
> the phase's **largest rewrite surface** (par with P6 tools).

### 2.B `@cassicore/mcp-gateway` — 42 files (1 root server + 38 gateway modules + 3 servers)

**`src/` (depth 0) — 4 files:**

| # | source (D:) | dest | bytes | recon |
|---|---|---|---|---|
| 1 | `mcp/cassicore-gateway.ts` | `cassicore-gateway.ts` | 1237 ln | LIVE (MCP server — stdio default, HTTP `--port 3000`) |
| 2 | `mcp/scip-server.ts` | `scip-server.ts` | 358 ln | LIVE |
| 3 | `mcp/gitnexus-server.js` | `gitnexus-server.js` | 38 ln | LIVE |
| 4 | `mcp/serena-server.js` | `serena-server.js` | 34 ln | LIVE |

**`src/gateway/` (depth 1, from `mcp/gateway/`) — 38 files** (0 DEAD, 0 UNCERTAIN — all LIVE): `index.ts`
(barrel, the consolidated-tool surface — see §6.B), `helpers.ts` (`GATEWAY_VERSION`, `fetchWithTimeout`,
`watchViaSSE`), `tool-management.ts` (`executeCassiCoreTool`, `CORE_TOOLS`), plus: agent-tools, annotation-tools,
blackboard-format, config-admin-tools, consolidated-{browser,code,config,context,filesystem,intelligence,memory,
model,session,training,web}-tools, constellation-tools, context-enrichment, context-repo-tools, cortex-tools,
dialectic-tools, do-tool, flux-tools, helix-tools, intelligence-tools (1591 ln — the largest), knowledge-tools,
lamina-tools, memory-tools, model-directive-tools, query-intelligence, resources, self-model-tools,
serena-onboarding, session-tools, tool-aliases, tool-management, training-tools.

> **`index.ts` is the MCP gateway's re-export barrel** (`GATEWAY_VERSION`, `createLogger`, `CORE_TOOLS`,
> `executeCassiCoreTool`, `SESSION_TOOLS`, `MEMORY_TOOLS`, `CONFIG_ADMIN_TOOLS`, …) — this is the surface
> constellation's vendored `mcp-consolidated-tools` port and admin-api's `tools.ts` import re-point TO that owns the
> stubs in P0–P6 packages. Quoted in §6.B.

### 2.C `@cassicore/commands` — 9 files (0 DEAD, 0 UNCERTAIN)

| # | source (D:) | dest | # | source (D:) | dest |
|---|---|---|---|---|---|
| 1 | `core/commands.ts` | `src/commands.ts` (`CommandDispatcher`) | 6 | `commands/team-commands.ts` | `src/commands/team-commands.ts` |
| 2 | `commands/index.ts` | `src/commands/index.ts` | 7 | `commands/tool-commands.ts` | `src/commands/tool-commands.ts` |
| 3 | `commands/cassi-commands.ts` | `src/commands/cassi-commands.ts` | 8 | `commands/universal-processor.ts` | `src/commands/universal-processor.ts` |
| 4 | `commands/cassicore-commands.ts` | `src/commands/cassicore-commands.ts` | 9 | `commands/qwen-commands.ts` | `src/commands/qwen-commands.ts` |
| 5 | `commands/git-commands.ts` | `src/commands/git-commands.ts` | | | |

### 2.D `@cassicore/workers` — 8 files (0 DEAD, 0 UNCERTAIN)

| # | source (D:) | dest | # | source (D:) | dest |
|---|---|---|---|---|---|
| 1 | `workers/echo-channel.ts` | `src/echo-channel.ts` | 5 | `workers/channels/telegram.ts` | `src/channels/telegram.ts` |
| 2 | `workers/channels/cli.ts` | `src/channels/cli.ts` | 6 | `workers/channels/webchat.ts` | `src/channels/webchat.ts` |
| 3 | `workers/channels/markdown/format.ts` | `src/channels/markdown/format.ts` | 7 | `workers/channels/telegram-common.ts` | `src/channels/telegram-common.ts` |
| 4 | `workers/channels/markdown/ir.ts` | `src/channels/markdown/ir.ts` | 8 | `workers/channels/markdown/render.ts` | `src/channels/markdown/render.ts` |

### 2.E `@cassicore/providers` — 18 files (exclude 5 DEAD + 4 UNCERTAIN)

| # | source (D:) (LIVE) | dest | # | source (D:) (LIVE) | dest |
|---|---|---|---|---|---|
| 1 | `core/providers/index.ts` | `src/index.ts` | 11 | `core/providers/copilot-sdk/tool-bridge.ts` | `src/copilot-sdk/tool-bridge.ts` |
| 2 | `core/providers/base.ts` | `src/base.ts` | 12 | `core/providers/copilot-sdk/warm-provider-manager.ts` | `src/copilot-sdk/warm-provider-manager.ts` |
| 3 | `core/providers/budget-tracker.ts` | `src/budget-tracker.ts` | 13 | `core/providers/cost-classifier.ts` | `src/cost-classifier.ts` (**P6 Open-1 home**) |
| 4 | `core/providers/centralized.ts` | `src/centralized.ts` | 14 | `core/providers/github-copilot-loadbalancer.ts` | `src/github-copilot-loadbalancer.ts` |
| 5 | `core/providers/claude-code.ts` | `src/claude-code.ts` | 15 | `core/providers/github-copilot.ts` | `src/github-copilot.ts` |
| 6 | `core/providers/copilot-sdk/client-manager.ts` | `src/copilot-sdk/client-manager.ts` | 16 | `core/providers/qwen-loadbalancer.ts` | `src/qwen-loadbalancer.ts` |
| 7 | `core/providers/copilot-sdk/event-mapper.ts` | `src/copilot-sdk/event-mapper.ts` | 17 | `core/providers/rate-limit-store.ts` | `src/rate-limit-store.ts` |
| 8 | `core/providers/copilot-sdk/finished-tool.ts` | `src/copilot-sdk/finished-tool.ts` | 18 | `core/providers/google-antigravity.ts` | `src/google-antigravity.ts` |
| 9 | `core/providers/copilot-sdk/provider.ts` | `src/copilot-sdk/provider.ts` | | | |
| 10 | `core/providers/model-router.ts` | `src/model-router.ts` | | | |

> **`CostClassifier` (P6 Open-1):** `core/providers/cost-classifier.ts` (self-contained, LIVE) is the RUNTIME dep
> P6's `@cassicore/model-pool` vendored. **P7 resolves it: `@cassicore/providers` owns the canonical impl.** The P6
> model-pool `src/vendor/core/providers/cost-classifier.ts` stub re-points to `@cassicore/providers` (inbound §3).
> Do NOT pull any OpenAI/Anthropic SDK into providers' package export surface beyond what these files already import
> (they wrap SDK calls internally).

### 2.F `@cassicore/host` — ~34 files (THIN host; composes all landed packages; §5 decomposition)

**`src/entry/` (from `core/entry/`) — 5 files (0 DEAD/UNCERTAIN):** `index.ts` (supervisor/dispatch),
`supervisor.ts` (fork+IPC monitor), `daemon-main.ts` (run Daemon directly), `vindex-loader.ts` (sidecar),
`code-extractor.ts`.

**`src/` (from `core/`) — 1 file:** `daemon.ts` (**166 KB — the single heaviest host file**; §5).

**`src/daemon/` (from `core/daemon/`) — LIVE only:** `boot-intelligence-post.ts` (CONFIRMED LIVE — keep + port-inject
§5) and any of `boot-configuration.ts` / `boot-intelligence-pre.ts` / `boot-pipeline-tools.ts` /
`intelligence-wiring.ts` that resolve live at preflight (§1g quarantine rule — **default: exclude all four UNCERTAIN
until intent resolved**). DEAD `boot-{channels,providers,types}.ts` + `channel-loader.ts` never cross.

**`src/cli/` (from `core/cli/`) — 12 files (0 DEAD/UNCERTAIN):** `cassicore.ts`, `index.ts`,
`commands/{boot,log,model,provider}.ts`, `runtime/{args,boot,http,output,process}.ts`,
`runtime/background-launcher.cjs`.

**`src/version.ts`** (from `core/version.ts`) — the `CASSICORE_VERSION` / `CASSICORE_BUILD_STRING` source (resolves
P6 Open-4).

**`src/bridge/` (from `core/bridge/acp/` + `core/bridge/openai.ts`) — 6 LIVE files:** `openai.ts` (createBridge),
`acp/{bin,client,server,translator,types}.ts`. `acp/index.ts` [UNCERTAIN] quarantined.

**`src/scripts/qwen-renew-accounts.ts`** — the single ALIVE `scripts/*.ts` (138 ln; `#!/usr/bin/env tsx`); imports
`ai/src/providers/cassicore/qwen.js` (P8 [ASK] — re-point at P8 or keep as a D:-PATH script; default: host bin,
P8 re-point).

**`bin/` launchers (preserved as `package.json` `bin` entries):** `cassicore` → `src/cli/index.ts`,
`cassi-acp` → `src/bridge/acp/bin.ts`; add `cassi-vindex-loader` → `src/entry/vindex-loader.ts`.

### 2.G `@cassicore/runtime-extras` (OPTIONAL — only if owner rejects folding bridge into host; Open Flag 6)

If requested: `core/bridge/*` live + `core/observability/telemetry.ts` [UNCERTAIN — resolve before inclusion] into
a `@cassicore/runtime-extras`. **Default: no separate package; fold bridge into host, observability has no live
file.**

---

## 3. Inbound sweep — EXPECTED re-point set (executor re-verifies by grep at preflight)

Workspace state changes until P7 runs. Rows below are the P7-owned stubs other landed packages vendored, plus the
P6-deferred items. Each stub whose symbol is now OWNED by a P7 package re-points to `@cassicore/<pkg>`, then deletes.

### 3.a P7-owned re-points (from P0–P6 landed vendor trees, inspected at drafting)

| consumer pkg | vendored stub | symbols | owning P7 pkg | runtime-or-type |
|---|---|---|---|---|
| constellation (pre) | `ports/mcp-consolidated-tools.ts` (standalone port, NOT a vendor copy) | the six consolidated symbols (`getCodeConsolidatedToolSchema`, `executeCodeConsolidatedTool`, …) | `@cassicore/mcp-gateway` | RUNTIME — host wires the port's executors to the real mcp-gateway barrel (no vendor stub to delete; the port's `not connected` throw is replaced by the real impl) |
| constellation (pre) | `ports/workspace-luminance.ts` (port? no — self-contained) | — | — | not an inbound; self-contained helper |
| constellation (pre) | `ports/code-analysis-context.ts` | `prepareContext` | host (`code-analysis` not a P7 pkg) | RUNTIME — host wires real impl (§7) |
| helix (P2) | `vendor/mcp/gateway/index.ts` | gateway barrel | `@cassicore/mcp-gateway` | RUNTIME |
| foundation (P1) | `ports/paths.ts` (setRootResolver home) | `setRootResolver`, `getCassiCoreHome`, `getDataDir` | **`@cassicore/host` calls `setRootResolver`** at boot (§7) — no stub delete, host wires the port | wiring |
| constellation (pre) | `ports/paths.ts` (setDataDirRoot) | `setDataDirRoot` | host calls it at boot (§7) | wiring |
| mnemic-field (P4) | `ports/store.ts` (`onWrite`) | MnemicFieldStore | host wires `onWrite` = overhaul hook target (P4 handshake) | wiring — stays UNOCCUPIED until overhaul encoder |
| foundation/helix/constellation/cognitive-feed (P0–P6) | `vendor/core/tools/{executor,registry,types}.ts`, `vendor/core/model-pool/*`, `vendor/core/utils/*`, `vendor/workflow/*`, `vendor/core/pipeline/*` | P6-owned symbols | `@cassicore/tools` / `model-pool` / `utils` / `workflow` / `pipeline` (ALREADY re-pointed at P6) | — verify none remain |
| helix (P2) | `vendor/mcp/gateway/index.ts` | (the P6 §3.e deferred item) | `@cassicore/mcp-gateway` | RUNTIME — **P6 explicitly deferred this to P7** |
| foundation (P1) | `vendor/core/version.ts` (if vendored) | `CASSICORE_VERSION` | `@cassicore/host` | type/runtime |
| model-pool (P6) | `vendor/core/providers/cost-classifier.ts` | `CostClassifier` | `@cassicore/providers` (P6 Open-1 resolved) | **RUNTIME** |
| mcp (P6) | `vendor/core/version.ts` | `CASSICORE_VERSION` | `@cassicore/host` | type |
| tools (P6) | `vendor/core/version.ts` | `CASSICORE_VERSION` | `@cassicore/host` | type |
| tools (P6) | `vendor/core/{event-history,event-query-parser,event-query-presets,tool-proxy-middleware,session-store,turn-pipeline}.ts` | host-owned modules | `@cassicore/host` (their real homes) | RUNTIME/type |
| pipeline (P6) | `vendor/core/workspace/loader.ts` | `buildSystemPrompt` | `@cassicore/host` (workspace owns no live pkg) | RUNTIME |
| events (P6) | `vendor/core/config/resource-limits.ts` | `DEFAULT_RESOURCE_LIMITS` | `@cassicore/host` (or foundation) — P6 Open-2 | RUNTIME |

### 3.b P7-deferred to P8 (in the expected sweep but owned by LATER phases — do NOT delete in P7)

| consumer | vendored stub | owning package | re-point at |
|---|---|---|---|
| host `src/scripts/qwen-renew-accounts.ts` | imports `ai/src/providers/cassicore/qwen.js` | `@cassicore/ai` | **P8** |
| providers (if any land in P7) | `../../ai/dist/...` provider SDK imports | `@cassicore/ai` | **P8** |

---

## 4. Executor inbound-sweep checklist (verify by `grep` at P7 preflight)

Before starting any P7 import, the executor MUST run this and confirm every EXPECTED stub in §3 exists and no
unexpected one surfaced:

1. `grep -rn "vendor/mcp/gateway" packages/*/src` → expect **helix** ONLY (`vendor/mcp/gateway/index.ts`) — **P6-deferred re-point to `@cassicore/mcp-gateway`.** (Constellation has NO `vendor/mcp/gateway` copy — it uses the `ports/mcp-consolidated-tools.ts` port, re-pointed by host wiring, not a stub delete.) **1 vendor file + the constellation port**, RUNTIME.
2. `grep -rn "vendor/core/providers" packages/*/src` → expect **model-pool** (`cost-classifier`). **1 file** RUNTIME
   (P6 Open-1 resolution).
3. `grep -rn "vendor/core/version" packages/*/src` → expect **mcp** + **tools** (if they vendored `core/version.ts`).
   Re-point to `@cassicore/host`. ≥0–2 files.
4. `grep -rn "vendor/core/session-store\|vendor/core/turn-pipeline\|vendor/core/event-history\|vendor/core/tool-proxy-middleware\|vendor/core/workspace\|vendor/core/config/resource-limits" packages/*/src` → the P6 host-vendored stubs (tools, pipeline, events). Each re-points to `@cassicore/host` (or its real home). ≥5–7 files.
5. `grep -rn "core/commands\|@cassicore/commands" packages/*/src` → expect NO landed package imports CommandDispatcher
   (host-only today) — confirm.
6. `grep -rn "ports/setRootResolver\|ports/paths\|ports/store\|ports/mcp-consolidated\|ports/code-analysis-context\|ports/helix-pipeline\|ports/gaming-mode" packages/*/src` → confirm each port exists so §7 wiring targets resolve (foundation/paths, constellation/{paths,mcp-consolidated,code-analysis-context,gaming-mode,helix-pipeline}, mnemic-field/store).
7. **P6-repoint residuals:** `grep -rn "vendor/core/tools\|vendor/core/model-pool\|vendor/core/utils\|vendor/workflow\|vendor/core/pipeline" packages/*/src` → expect **EMPTY** (P6 swept these). If any remain, they are host-consumed or P6 bugs — resolve before P7.
8. For each stub found, read its exports and confirm the P7 package's landed barrel re-exports the SAME symbol names before deleting (a type-surface mismatch breaks the consumer at compile time).
9. Re-verify D: read-only + HEAD state for every imported path (§4.3 plan); the overhaul session is live-editing `core/intelligence/*` and may have touched `core/daemon.ts` (the P7 handshake §7 of the plan) — re-clone if mid-import changes.

---

## 5. Daemon.ts decomposition strategy — [RECOMMENDATION: (b)-lite]

**`core/daemon.ts` (166 KB) is the single heaviest host file** (plan §5-P7: "do not rewrite its internals, only
rewire its imports to package ports"). Options considered:

- **(a) migrate whole then strip dead imports only** — least work today, but leaves a 166 KB monolith forever; the
  "thin host" goal is unmet and the overhaul's Stage-gates keep targeting a single un-split file.
- **(b) split boot phases into host modules** (bootIntelligencePostPipeline, resolveWorker, admin-api mount, plugin
  host init each become `host/src/*.ts`) — cleanest end-state, but the highest rewrite risk on the live-critical
  boot path (the parallel session at D: depends on `core/daemon.ts` staying functional).
- **(c) minimal:** migrate `daemon.ts` as-is, rewire only imports + the wiring calls to package imports, let the
  overhaul session slim it later.
- **(b)-lite (RECOMMENDED):** **keep `daemon.ts`'s structure (all boot phases stay in the one class), rewrite ONLY
  its imports + the direct wiring calls to package imports, extract nothing new.** The boot-phase functions that
  are ALREADY module-shaped become `host/src/*.ts` only where they are ready: `bootIntelligencePostPipeline` is
  already a port-shaped `deps`-object function (quote below) so it moves to `host/src/daemon/boot-intelligence-post.ts`
  unchanged; `resolveWorker` stays inline in the class (it's 9 lines); the admin-api mount stays a 5-line call
  (`createAdminApi(this, logger)`); plugin-host init stays inline. Do NOT extract boot phases in this migration.

**Justification:**
1. **Preserves the live boot path.** The overhaul session runs Stage-N gates against `core/intelligence/*` and may
   depend on the daemon booting identically. (b)-lite changes ONLY import specifiers + the package-boundary wiring
   calls — the exact P7 mandate (§5-P7: "only rewire its imports to package ports"). Full (b) extraction risks a
   subtle reorder that breaks a Stage gate mid-handshake.
2. **`bootIntelligencePostPipeline` is already a seam.** It takes a `deps: IntelligencePostBootDeps` object
   ({bus, config, logger, intelligence, pipeline, sessions, sessionStore, sessionDigestStore, toolRegistry,
   toolExecutor, pluginHost, …}) — port-injectable as-is into `host/src/daemon/boot-intelligence-post.ts`. The
   registry skip-list + `registry.wire(...)` stays in `daemon.ts` (caller), per the plan: "the skip-list modules are
   manually instantiated in createIntelligence()/bootIntelligencePostPipeline() — those become port-injected as
   well."
3. **The registry-discovery replacement is the host's job, not a daemon split.** (b)-lite lets P7 keep the
   skip-set alongside `createIntelligence(...)` in one place while the package barrels (P5 exports) replace the
   directory-scan (see §5a).
4. **Defer the slimming to the overhaul.** A dedicated slim pass (their plan owns the "field as state of truth"
   transform) can later pull boot phases into `host/src/*` modules behind the now-package-importing daemon. P7's job
   is reachability + port wiring, not refactor.

**Migrated daemon = the composition of already-extracted pieces** — after (b)-lite, `core/daemon.ts` imports only
`@cassicore/*` package specifiers + `@cassicore/host` internal modules (boot-intelligence-post), instantiates
packages, mounts the admin-api route registry, loads channels via the package-relative `resolveWorker`, and boots.
No piece of its logic is duplicated or reordered.

### 5a. Known-hard (a): IntelligenceRegistry discovery contract + reverie skip-set

**Where the registry lives now:** `core/intelligence/base/registry.ts` — this is a **P5 carrier** (the intelligence
base-landing), NOT the host. Per plan §3e.1, P5 owned `core/intelligence/*` and the P5 groups re-export their
`BaseCognitiveModule` subclasses through package barrels. The registry's DISCOVERY (directory scan) is what P7's
host replaces with explicit registration.

**Contract (quoted from `core/intelligence/base/registry.ts`):**

```ts
class IntelligenceRegistry {
  constructor(logger: ILogger)
  registerInstance(module: BaseCognitiveModule): void
  registerClass(ModuleClass: CognitiveModuleConstructor, modelConfig?): BaseCognitiveModule | undefined
  async discover(baseDir: string, skipDirs?: Set<string>): Promise<void>
  wire({ eventBus, memory, provider, config, toolRegistry, toolExecutor }: RegistryDependencies): void
  get(name): BaseCognitiveModule | undefined
  initAll()/startAll()/stopAll()
}
// RegistryDependencies = { eventBus?, memory?, provider?, config?, toolRegistry?, toolExecutor? }
```

**P7 must provide:** the host's `daemon.ts` replaces `await registry.discover(intelligenceDir, skipDirs)` with
explicit package-registry wiring — each landed brain-region package's `index.ts` barrel exports its
`BaseCognitiveModule` subclasses (or a `MODULE_CLASS` marker), and the host calls `registry.registerClass(...)` /
`registry.wire(...)` per package. The `discover`-time skip-set (quoted below) must be mirrored as the explicit
registration list so no module is double-registered:

```ts
// core/daemon.ts:2109-2137 — the registry skip-set (manual-instantiation / duplicate-avoidance list)
const intelligenceDir = join(path.dirname(fileURLToPath(import.meta.url)), 'intelligence')
await registry.discover(intelligenceDir, new Set([
  'base', 'memory', 'continuity', 'recover', 'reflect', 'thinker', 'optimizer',
  'dialectic', 'ai-scientist', 'rule-enforcer', 'subconscious', 'team-orchestrator',
  'triad-team', 'embeddings', 'yang', 'yin', 'synthesizer', 'serenity',
  // self-healer — manually instantiated in createIntelligence() (skip auto-discovery)
  'self-healer',
  // these extend BaseCognitiveModule but are manually created in createIntelligence()
  // + wired with extra deps in bootIntelligencePostPipeline():
  'heart', 'dreamer', 'smart-rules', 'reflex', 'consequence-estimator',
  'trust-ledger', 'permission-oracle',
]))
registry.wire({ eventBus: this.bus, memory: this.intelligence.memory as any,
  provider: registryProvider, config: this.config, toolRegistry, toolExecutor })
```

**The reverie skip-set trap (P5b lesson):** the skip list above is a **hardcoded set of directory names** in
`daemon.ts`, maintained alongside the P5 package exports. When P7 replaces discovery with explicit registration, a
module that P5's package barrel now exports but that is ALSO listed in the skip-set (or vice-versa) will be either
double- or never-registered. **Executor trap:** cross-check the P5b landed barrel exports against BOTH the skip-set
(callers: `createIntelligence()`, `bootIntelligencePostPipeline()`) AND the P5 package `index.ts` barrels before
wiring — the host's explicit registration list must equal (P5 barrel exports) minus (manually-instantiated skip list),
**exactly once**. The P5 table flagged reverie's skip handling; P7 inherits it — re-verify reverie is registered
exactly once at P7 preflight.

### 5b. Known-hard (b): admin-api route contract — quoted (already in §1e)

Server: **`node:http`** (NOT express). `createAdminApi(daemon, logger)` returns `{ start, stop }`; `start()` binds a
**Unix socket** at `~/.cassicore/admin.sock` + a **TCP server** at `admin.host:admin.port` (defaults
`127.0.0.1:7433`, EADDRINUSE port-scan). Routing: the single `handler(req,res)` splits `url.pathname` to `parts` and
dispatches to `handleXxxRoutes({...}, req, res, method, pathname, parts)` by `parts[0]`. WebSocket `/ws` upgrade is
handled in the same server. This exact shape is the package's public surface.

### 5c. Known-hard (c): resolveWorker channel contract — quoted (already in §1d)

### 5d. Known-hard (d): bin/scripts entry points + their paths — quoted (already in §1f)

---

## 6. Rewrite tables

House rules (identical to P6): mirror vendor stubs at `src/vendor/<rel-from-D-repo-root>.ts`; extension preserved
verbatim (`.js` kept; dropped only for `@cassicore/*`); scope rule: REWRITE only foundation/landed/`@cassicore/*`/
vendor escapes on real import statements; global per-specifier replacement.

### 6.A `@cassicore/admin-api` rewrite pairs (largest surface)

**Depth prefixes:** `src/admin-api.ts` (depth 0) → `./vendor/…`-import escape prefix `../vendor/…`? **No — depth 0
files use `../vendor/…`; `src/routes/…` (depth 1) use `../../vendor/…`.** Package specifiers need no prefix.

| class | original specifier(s) | dest |
|---|---|---|
| foundation | `../types/{interfaces,runtime,dialectic,events,plugin,trace,flux-team,blackboard-search}.js`; `../config/system-settings.js`; `../utils/paths.js` | `@cassicore/foundation` |
| landed brain-region | `../intelligence/{mnemic-field,lamina,cortex,thalamus,pineal,reverie,helix,flux-team,embeddings,constellation,context-repo}/*`, `../intelligence/{synapse,context-assembler,smart-compaction}*.js` | `@cassicore/<owning P5 pkg>` (re-point to landed barrel) |
| P6 packages | `../plugins/{plugin-registry,plugin-api,external-clients/*}.js`; `../jobs/job-manager.js`; `../mcp/registry.js` | `@cassicore/plugins` / `@cassicore/jobs` / `@cassicore/mcp` |
| providers (P7) | `../providers/{centralized,copilot-sdk/warm-provider-manager,copilot-sdk/provider}.js` | `@cassicore/providers` |
| mcp-gateway (P7) | `../../mcp/gateway/index.js` (tools.ts) | `@cassicore/mcp-gateway` |
| commands (P7) | `../commands.js` (CommandDispatcher—part of this pkg now) | internal `./commands.js` |
| host VENDOR | `../session-store.js`, `../turn-pipeline.js`, `../timeline-store.js`, `../testing/*`, `../workspace/loader.js`, `../daemon.js` (any accidental), `../../scripts/qwen-renew-accounts.js`, `../tools-api.js` | `../vendor/core/{session-store,turn-pipeline,timeline-store,testing/*,workspace/loader,scripts/qwen-renew-accounts}.ts` (RUNTIME/type per use) — re-point to `@cassicore/host` when host publishes |
| internal | `./runtime.js`, `./turn-routing.js`, `./intelligence.js`, `./<route>.js` cross-siblings | unchanged (same package) |
| builtins/npm | `node:http`, `node:fs/path/os/crypto`, `vitest` | unchanged |

### 6.B `@cassicore/mcp-gateway` rewrite pairs

| class | original specifier(s) | dest |
|---|---|---|
| foundation | `../../types/*` (intelligence, interfaces, events, dialectic) | `@cassicore/foundation` |
| landed brain-region (via gateway `*-tools.ts`) | `../intelligence/{helix,constellation,flux-team,cortex,lamina,memory}/…` → re-point to landed barrels | `@cassicore/<owning pkg>` |
| P6 packages | `../tools/{registry,executor,types}.js`; `../mcp/registry.js`; `../model-pool/index.js` | `@cassicore/tools` / `@cassicore/mcp` / `@cassicore/model-pool` |
| P7 providers | `../providers/*` | `@cassicore/providers` |
| host VENDOR | `../daemon.js`, `../session-store.js`, `../turn-pipeline.js`, `../intelligence/…` | `../vendor/...` (re-point at host publish) |
| npm | `@modelcontextprotocol/sdk`, `node:child_process`, `node:http`, `node:fs/path/os` | unchanged (add dep `@modelcontextprotocol/sdk`) |

### 6.C `@cassicore/commands` rewrite pairs

| class | original | dest |
|---|---|---|
| foundation | `../../types/{interfaces,runtime}.js`; `../event-bus.js` | `@cassicore/foundation` / `@cassicore/events` |
| P6 tools | `./tools/interactive-tool-session.js` (`core/commands.ts`) | `@cassicore/tools` |
| brain-region | `../intelligence/model-routing/index.js` (ModelDirective type) | `@cassicore/<owning pkg>` |
| internal | `../commands/{universal-processor,cassi-commands,…}.js` | unchanged (same package) |

### 6.D `@cassicore/workers` rewrite pairs

| class | original | dest |
|---|---|---|
| foundation | `../types/{interfaces,runtime}.js` | `@cassicore/foundation` |
| P6 events | `../event-bus.js` / `../logger.js` (echo/cli/webchat workers) | `@cassicore/events` |
| P5/P6 tools | `../intelligence/…`, `../tools/…` (worker deps) | `@cassicore/<owning>` |
| npm | `markdown-it` (markdown/format-render), `node:http`, `node:crypto`, `node:path` | unchanged |
| host IPC | `worker-ipc.js` (if workers import the plugin-host IPC protocol) | `@cassicore/plugins` (P6) |

### 6.E `@cassicore/providers` rewrite pairs

| class | original | dest |
|---|---|---|
| foundation | `../../types/{interfaces,runtime}.js` | `@cassicore/foundation` |
| P6 events/model-pool | `../event-bus.js`, `../logger.js`, `../model-pool/*` | `@cassicore/events` / `@cassicore/model-pool` |
| P6 utils | `../utils/{ttl-cache,circuit-breaker,ids,backoff?}.js` | `@cassicore/utils` |
| host VENDOR | `../daemon.js` (CASSICORE_VERSION re-export) | `../vendor/core/version.ts` → re-point `@cassicore/host` |
| internal | `./index.js`, `./base.js`, `./model-router.js`, `./copilot-sdk/*` | unchanged |
| npm | `openai`, `@anthropic-ai/sdk`, `@google/…` (provider SDKs) | unchanged (add deps) — P8 `@cassicore/ai` supplies qwen/openai-compatible |

### 6.F `@cassicore/host` rewrite pairs (per package-import)

The migrated `daemon.ts` import block (§5) becomes: `@cassicore/events` (EventBus, Logger), `@cassicore/foundation`
(Config/system-settings/types), `@cassicore/tools` (ToolExecutor, ToolRegistry, registerCoreTools),
`@cassicore/workflow`, `@cassicore/jobs`, `@cassicore/plugins` (PluginHost, plugin API), `@cassicore/model-pool`,
`@cassicore/mcp`, `@cassicore/pipeline`, `@cassicore/utils`, `@cassicore/providers` (createModelRouter,
createBudgetTracker), landed brain-region packages (intelligence/*, mnemic-field, helix, constellation, flux-team),
`@cassicore/admin-api` (createAdminApi), `@cassicore/mcp-gateway`, `@cassicore/commands`, `@cassicore/workers`
(resolveWorker). Internal host modules (`daemon/boot-intelligence-post.ts`, `entry/*`, `cli/*`, `bridge/*`,
`version.ts`) stay `./…` within the host package.

---

## 7. The P7 wiring matrix — 'final wiring' checklist (exhaustive from landed packages' `src/ports/*.ts`)

For every landed package's exposed port, the host wires it at boot. Ports inventory (read at drafting):

| landed package | port file | surface to wire at boot |
|---|---|---|
| `@cassicore/foundation` | `src/ports/paths.ts` | **`setRootResolver(resolver)`** — host calls at boot with the real `CASSICORE_HOME`/config resolver (replaces `--no-persist` env mutation). Also `getDataDir/getCredentialsDir/getConfigPath/getPidFilePath/getAdminSocketPath` etc. available. |
| `@cassicore/constellation` | `src/ports/paths.ts` | **`setDataDirRoot(root)`** — host sets the data root so Constellation stores share the layout. |
| `@cassicore/constellation` | `src/ports/helix-pipeline.ts` | **`runHelixPipeline(opts)` + `BrainstemMiniHelix`** — P2-wired port lazily delegates to `@cassicore/helix`. Host must provide the real model handles/tool executor/registry/stores (`HelixPipelineOpts.unityHandle/yangHandle/yinHandle/toolExecutor/toolRegistry/store/eventBus/...`) or invocation throws the real helix runtime errors. |
| `@cassicore/constellation` | `src/ports/mcp-consolidated-tools.ts` | **`executeCodeConsolidatedTool/executeFilesystemConsolidatedTool/executeWebConsolidatedTool` + schema getters** — host re-points this port to the real `@cassicore/mcp-gateway` consolidated tool executors (see §3.a; currently `not connected` throw). |
| `@cassicore/constellation` | `src/ports/code-analysis-context.ts` | **`prepareContext(routeTool, opts)`** — host wires a real implementation (git-nexus/code-analysis) or it stays `not connected`. `routeTool` passed so a wired impl can dispatch git/read tools. |
| `@cassicore/constellation` | `src/ports/workspace-luminance.ts` | `extractKeywords/keywordOverlap` — **self-contained, no wiring** (host none needed). |
| `@cassicore/constellation` | `src/ports/gaming-mode.ts` | **`setGamingMode(true/false)`** — host calls when the GPU guard toggles gaming mode; constellation reads `isGamingMode()`. |
| `@cassicore/mnemic-field` | `src/ports/store.ts` | **`store.onWrite` observer** — the MindFieldEncoder hook target. P4 handshake: stays UNOCCUPIED until the overhaul session provides the encoder. Host must NOT wire it to anything in P7 (§4/§7 of the plan). |
| `@cassicore/helix` | (ports via constellation's helix-pipeline) | model runtime (handles/stores) — host provides at constellation's `runHelixPipeline` wiring. |
| `@cassicore/tools` (P6) | `@cassicore/tools` `registerCoreTools` | **host calls `registerCoreTools(toolRegistry, deps)`** with `{memory, sessionManager, sessionStore, bus, logger, getPipeline, subagentTracker, cognitiveToolDeps, peerToolDeps, collectThoughtsDeps, getJobManager, getWorkflow*}` (the daemon.ts:1940 call) — quoted in P6 §1f. |
| `@cassicore/plugins` (P6) | `PluginHost`, `PluginAPI` | **host `new PluginHost(logger)` + `pluginHost.load({id, entryPoint, restartOnCrash, maxRestarts, config})`** per channel worker; `PluginAPI` facade injected with {logger, registry, sessions, context, memory, intelligence, eventBus, toolRegistry}. |
| `@cassicore/events` (P6) | `Logger`/`rootLogger`/`EventBus`/`bus` | host uses the P6 singletons (`new Logger`, `new EventBus`) as the shared substrate. |
| `@cassicore/model-pool` (P6) | `ModelPool` | host instantiates model-pool with provider types; `CostClassifier` now from `@cassicore/providers`. |
| `@cassicore/jobs` (P6) | `JobManager` | host wires job tools' `getJobManager` getter. |
| `@cassicore/workflow` (P6) | `WorkflowEngine/Registry` | host initializes engine+registry+scheduler at boot (daemon already does — rewire imports). |
| `@cassicore/pipeline` (P6) | `TurnPipeline` | host's `getPipeline` getter; session-pipeline vs legacy turn engine selection. |
| `@cassicore/mcp` (P6, client) | `MCPClient`/`MCPRegistry` | host loads configured MCP servers. |
| `@cassicore/utils` (P6) | shared utils | host uses `TTLCache`/`CircuitBreaker` etc. |
| `@cassicore/admin-api` (P7) | `createAdminApi(daemon, logger)` | **host mounts it: `const adminApi = createAdminApi(this, this.logger); await adminApi.start()`** (daemon.ts:3255) — returns `{tcpPort, unixPath}`; host records + health-wires the tcp server. |
| `@cassicore/mcp-gateway` (P7) | `cassicore-gateway.ts` | **host/launcher runs the gateway as a stdio/HTTP server; its `DAEMON_ENTRY` spawn path (now `core/entry/daemon-main.ts`) re-pointed to `@cassicore/host`'s bin; `CASSICORE_URL` default `http://localhost:7433` sets the admin TCP target.** |
| `@cassicore/commands` (P7) | `CommandDispatcher` | host instantiates `new CommandDispatcher(...)` (daemon imports it) with session/interactive-tool deps. |
| `@cassicore/workers` (P7) | individual worker modules | **host `resolveWorker('@cassicore/workers/channels/webchat')` etc.** → `PluginHost.load({entryPoint})` per channel (§1d). OpenCode is a ghost ref — no worker. |
| `@cassicore/providers` (P7) | `createModelRouter`, `createBudgetTracker`, provider classes | host builds providers Map, wires registry, feeds model-pool; `CostClassifier` owns the global default. |
| `@cassicore/host` (P7) | supervisor/fork + CLI | supervisor forks `daemon-main`; CLI (`cassicore`/`cassi-acp`/`vindex-loader` bins) launch subprocess entries; `setRootResolver`/`setDataDirRoot` called first. |

**Boot-phase wiring order (from daemon.ts `start()`, mapped to port calls):** config/root-resolver (foundation+constellation
paths) → createIntelligence (brain-region packages) → PluginHost init → channels (resolveWorker + pluginHost.load) →
providers Map → workflow init → `registerCoreTools` (tools) → registry.discover→explicit registration →
`bootIntelligencePostPipeline(deps)` → admin-api mount → health wire.

---

## 8. Open flags (max 8 — defaults recommended)

1. **[OPEN-1] UNCERTAIN daemon boot files** — `boot-configuration.ts`, `boot-intelligence-pre.ts`,
   `boot-pipeline-tools.ts`, `intelligence-wiring.ts` (live-name-ref 1–4). Default: **quarantine** until a worker
   resolves whether daemon invokes them by string at boot; if live, promote `boot-intelligence-pre`/`boot-pipeline-tools`
   to `@cassicore/host` `src/daemon/`. `boot-intelligence-post.ts` is confirmed live + port-injected regardless.
2. **[OPEN-2] `CostClassifier` home (P6 Open-1 resolves here)** — default: **`@cassicore/providers`** owns
   `cost-classifier.ts`; P6 model-pool's vendored stub re-points to it. `[DECIDE]` if a dedicated `@cassicore/cost`
   separate home is preferred (default no).
3. **[OPEN-3] Host-coupled vendor homes** — `session-store`, `turn-pipeline`, `timeline-store`, `tool-proxy-middleware`,
   `event-history`, `workspace/loader`, `config/resource-limits`, `testing/*` stay vendored in consumer packages and
   re-point to `@cassicore/host` only when the host publishes those own modules. Default: host package exports its
   owned `src/{session-store,turn-pipeline,...}` in P7 so the P6 vendored stubs re-point now. `[VERIFY]` these aren't
   mid-rewire by the overhaul session.
4. **[OPEN-4] `@cassicore/commands` scope** — `core/commands.ts` (`CommandDispatcher`) joins `commands/`. Default: yes
   (evidence: daemon imports it from `./commands.js`, and it imports `commands/universal-processor`). `[DECIDE]` if the
   owner wants CommandDispatcher kept host-internal and only `commands/*` packaged (default no — split breaks the
   dispatcher/dispatched coupling).
5. **[OPEN-5] Overhaul handshake (host wiring)** — plan §7: "package publishes before rewiring" at P7. The overhaul
   session's Stage-N gates target `core/intelligence/*` + possibly `core/daemon.ts`. Confirm they have NOT rewritten
   `core/daemon.ts`, `core/intelligence/base/registry.ts`, or `core/plugins/*` since the P7 temp-clone; if so, swap
   order / re-clone. `[VERIFY]` at execution.
6. **[OPEN-6] `@cassicore/runtime-extras` vs fold-into-host** — default: fold `core/bridge/*` live into
   `@cassicore/host`; `@cassicore/runtime-extras` only if the owner prefers a distinct package. `[DECIDE]`.
7. **[OPEN-7] ghost opencode worker** — `resolveWorker("../workers/channels/opencode")` (daemon:1049) references a
   non-existent file. Default: keep the null-guard, do NOT create the worker; record in DONE. `[VERIFY]` D: hasn't
   added `workers/channels/opencode.*` since scan (the overhaul session may add it).
8. **[OPEN-8] qwen-renew-accounts + provider SDK deps → P8 `@cassicore/ai`** — `scripts/qwen-renew-accounts.ts`
   imports `ai/src/providers/cassicore/qwen.js`; providers wrap `openai`/`@anthropic-ai/sdk` SDKs (P8 owns `ai/`).
   Default: host carries the script now, whole `ai/` stays in D: until P8 ([ASK-USER] §8 Q2); do NOT migrate AI SDKs
   in P7. `[DECIDE]` whether providers' SDK clients become thin wrappers over `@cassicore/ai` at P8.

---

## 9. Executor playbook (P7 later wave — verbatim)

1. **Preflight inbound sweep** — run §4's grep checklist against the CURRENT workspace state; reconcile any diff
   against §3 (P6-deferred `vendor/mcp/gateway` in helix MUST still exist; the P0–P6 P6-package stubs should be gone).
2. Per package, follow §4.3 plan: temp-clone D: (history-only, `--no-checkout`), filter-repo
   `--path core/admin-api` + `--path core/admin-api.ts` (admin-api), `--path mcp` (mcp-gateway), `--path commands` +
   `--path core/commands.ts` (commands), `--path workers` (workers), `--path core/providers` (providers), and for
   host a composite: `--path core/entry` + `--path core/daemon.ts` + `--path core/daemon` + `--path core/cli` +
   `--path core/version.ts` + `--path core/bridge` + `--path scripts/qwen-renew-accounts.ts` + `--path bin` — each with
   `--path-rename` to `packages/<name>/src`, mailmap, fetch `import/<name>`, splice
   (`--allow-unrelated-histories`), ADOPT as import commit. Verify `git log --follow` provenance.
3. **Rewrite-delta commit** — apply the §6 rewrite maps globally-per-specifier; write the host's composite barrel +
   package.json/tsconfig/vitest; write the admin-api route barrel; vendor stubs (§5/§6); resolve the Open Flags.
4. **Port tests** — admin-api route tests + mcp-gateway + commands + workers + providers tests; quarantine
   host-wired suites (those importing `core/daemon.ts`) to `tests/host-wired/` (§6 plan).
5. **Inbound re-point commit(s)** — replace the §3 vendored stubs' consumers with `@cassicore/<pkg>` imports; delete
   each replaced stub. **Order: providers, workers, commands, mcp-gateway, admin-api, THEN host (host is the
   highest-fanout and last to publish)** — so the host's own `@cassicore/*` rewires can import the just-landed
   packages. Defer P8 re-points per §3.b.
6. **Host wiring commit** — apply §5 (b)-lite: rewrite daemon.ts's imports + the §7 port wiring calls to package
   specifiers; keep its structure; extract only `boot-intelligence-post.ts`. Wire `setRootResolver`/`setDataDirRoot`
   first, then the boot order.
7. `npm run typecheck` (`tsc --noEmit`) per package; fix only mechanical path errors. Do NOT run full suites.
8. **Workspace-wide smoke** that boots the host offline (plan §5-P7 DONE): boot `@cassicore/host` against the mounted
   admin-api route registry + all package imports; confirm the supervisor/fork path + a manual
   `--start-stop`/`--exit-after-startup` run boots without the directory-scan (explicit registration) and channels
   resolve via package-relative `resolveWorker`.
9. Confirm `git status` clean; D: untouched; `git log --follow` passes for every migrated tracked file.
10. Commit splits per plan §3c (history import ≠ rewrite delta ≠ inbound re-point ≠ host wiring; never mix).

---

## 10. Response summary (drafting-pass counts — per the task brief)

**Live-set counts per package (source `.ts`/`.js`):**
- `@cassicore/admin-api` — **55** files (1 root `admin-api.ts` + 54 in `admin-api/`), ≈1,096 KB (excl. 3 DEAD: activity,
  metrics, team-timeline; 1 UNCERTAIN: system-prompt)
- `@cassicore/mcp-gateway` — **42** files (4 top-level: cassicore-gateway + scip/gitnexus/serena servers; 38 in
  `gateway/`), ≈3,559 ln+ — 0 DEAD/UNCERTAIN
- `@cassicore/commands` — **9** files (`core/commands.ts` + 8 in `commands/`) — 0 DEAD/UNCERTAIN
- `@cassicore/workers` — **8** files (echo-channel + 7 in channels/markdown) — 0 DEAD/UNCERTAIN
- `@cassicore/providers` — **18** files (excl. 5 DEAD + 4 UNCERTAIN)
- `@cassicore/host` — **~34** files (5 entry + daemon.ts + boot-intelligence-post + 12 cli + version + 6 bridge +
  4 daemon-UNCERTAIN-promoted-if-live + scripts/qwen-renew) — 0 DEAD (host root files all LIVE)
- host-adjacent with 0 live: observability (1 UNCERTAIN), unified (DEAD+UNCERTAIN), ingestion (DEAD+UNCERTAIN),
  adapters (DEAD) — nothing migrates
- **TOTAL live-source ≈ 166 files** (byte sum deferrable; D: drifts with the live session)

**Daemon decomposition recommendation: (b)-lite** — keep `core/daemon.ts`'s structure, rewrite ONLY imports + the
§7 package wiring calls (imports to `@cassicore/*`, `setRootResolver`/`setDataDirRoot` first, `createAdminApi(this,
logger)` mount, `registerCoreTools` deps, explicit registry registration), extract nothing new except the already
port-shaped `bootIntelligencePostPipeline` → `host/src/daemon/boot-intelligence-post.ts`. Defer full phase-splitting
to the overhaul session. Justification: preserves the live boot path for the parallel session, only touches
package-boundary rewiring per the plan's P7 mandate, and gets the final-wiring matrix connected without a risky
refactor of the 166 KB boot file.

**P7 wiring matrix summary:** 25 port seams wired at boot — foundation `setRootResolver`; constellation
`setDataDirRoot` + `helix-pipeline` (real handles) + `mcp-consolidated-tools` (→ mcp-gateway) + `code-analysis-context`
(real impl) + `gaming-mode` (`setGamingMode`); mnemic-field `store.onWrite` (UNOCCUPIED per P4 handshake); tools
`registerCoreTools(deps)`; plugins `PluginHost.load` per channel; admin-api `createAdminApi().start()` (tcp 7433 +
unix sock); mcp-gateway gateway server (DAEMON_ENTRY→host bin, CASSICORE_URL :7433); commands `CommandDispatcher`;
workers `resolveWorker('@cassicore/workers/...')`; providers model-router/budget-tracker; host supervisor/fork +
CLI bins. Full table in §7.

**Expected inbound sweep:** helix `vendor/mcp/gateway` (P6-deferred → `@cassicore/mcp-gateway`, RUNTIME) +
constellation `ports/mcp-consolidated-tools.ts` + `ports/code-analysis-context.ts` (host wires the real impls);
model-pool `vendor/core/providers/cost-classifier` (→ `@cassicore/providers`); mcp + tools `vendor/core/version`
(→ host); tools/pipeline/events host-vendor stubs `session-store/turn-pipeline/event-history/tool-proxy-middleware/
workspace/loader/resource-limits` (→ host); P6 residual `vendor/core/{tools,model-pool,utils,workflow,pipeline}`
expect EMPTY (P6 swept). Deferred to P8: host qwen-renew `ai/src/...` + providers SDK wrappers. Executor re-derives
by grep (§4).

**Open flags:** 8 total (§8) — Open-1 daemon UNCERTAIN quarantines (resolve live-by-name), Open-2 CostClassifier home
(=providers, resolves P6 Open-1), Open-3 host vendor homes, Open-4 commands scope, Open-5 overhaul handshake,
Open-6 runtime-extras vs fold-into-host, Open-7 ghost opencode worker, Open-8 qwen/providers → P8 ai.

---

## P6 turn 3 — execution note (appended 2026-08-14, not user-facing)

Re-points applied this turn (owning packages published):
- tools `vendor/core/event-history.ts` -> `@cassicore/events` (EventHistory runtime
  class added to events as event-history.ts; ulid dep).
- tools `vendor/core/{logger,event-bus,events}/*` (rootLogger/bus/getEventBus/
  getContextWindowDebugger/ContextWindowDebugger) -> `@cassicore/events`.
- utils `vendor/core/logger.ts` (rootLogger in circuit-breaker) -> `@cassicore/events`.
- thalamus `vendor/core/pipeline/turn/overflow.ts` (hasQuestionResult/
  buildToolUseMapFromMessages) -> `@cassicore/pipeline` (barrel now re-exports the
  full overflow surface).

DEFERRED to P7 @cassicore/host (stubs LEFT in place; re-point there):
- tools `vendor/core/{session-store,turn-pipeline,tool-proxy-middleware,event-query-parser,
  event-query-presets}.ts` + `vendor/core/workflow/*` + `vendor/core/jobs/*` (utils/
  workflow/jobs package-internal rewires stay vendored).
- helix `vendor/mcp/gateway/index.ts` -> @cassicore/mcp-gateway (P7).
- model-pool `vendor/core/providers/cost-classifier.ts` -> @cassicore/providers (P7,
  emits P6 Open-1).
- mcp + tools `vendor/core/version.ts` (CASSICORE_VERSION) -> host/version home (P7/P8).

Substrate: foundation KEEPS its local `vendor/core/{tools,model-pool}` type stubs (no
@cassicore/* dep on foundation); documented per plan §5 line 27 ruling.
