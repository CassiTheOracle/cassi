# P3 Implementation Brief — The Spine Extension + Focused Mind Runtime

**Phase:** P3 (CASSICORE-FOCUS-PLAN §6 P3 row)
**Type:** IMPLEMENTATION BRIEF (design deliverable — no code changes, no git commands)
**Date:** 2026-08-14
**Source-of-truth inputs:** `CASSICORE-FOCUS-PLAN.md` (§4, §2.3, §3, §6 P3) · `recon-oh-mypi-capabilities.md` (ExtensionAPI fact-pack) · `packages/tools/src/` (mind-tool definitions) · `packages/host/src/daemon.ts` (composition root) · `packages/mnemic-field/src/index.ts` (MnemicField surface).
**Goal:** The P3 executor can implement spine + mind-runtime from this brief + the plan with **zero further design decisions**. All `[VERIFY]` items below are flagged for the executor to confirm at implementation time; none block the skeleton.

---

## 1. Package layout recommendation

**Recommendation: two new sibling packages under `packages/`:**

- `packages/spine/` → `@cassicore/spine` — the ohmypi **extension** (default-factory shape).
- `packages/mind-runtime/` → `@cassicore/mind-runtime` — the focused always-on cognitive process (composition root + internal channel).

**Why two separate packages (over the alternatives):**

| Option | Verdict | Rationale |
|---|---|---|
| **`@cassicore/spine` + `@cassicore/mind-runtime`** | **RECOMMENDED** | Clean dependency direction: spine imports `@oh-my-pi/pi-coding-agent` (host-agnostic boundary), mind-runtime imports zero ohmypi (host-agnostic core, satisfiable by plan §4.3/§5 verdict 26 "replaces host"). No contamination of the cognitive core with harness types. |
| spine-inside-mind-runtime | Rejected | Violates plan §5.6/§1.2: the mind runtime MUST NOT depend on ohmypi. Bundling the extension into it leaks `ExtensionAPI` types into the core and drags `pi-coding-agent` into every core consumer. |
| Reuse `packages/host/` | Rejected | `host` is the 68,949-line daemon marked **PORT → replaced by the focused runtime + spine** (plan §5 verdict 26). Reusing it keeps the standalone-daemon posture the design explicitly retires, and its package boundary already carries the deleted surfaces (CLI/ACP/admin-api). |
| Reuse `packages/mcp-gateway/` | Rejected | Its retained essence is only the *consolidated schemas*, which the spine re-exposes (plan §5 verdict 28). The server itself dies. |

**Dependency contract (the load-bearing rule):**
- `@cassicore/spine` **MUST** import `@oh-my-pi/pi-coding-agent` **types only** (registered as a `devDependency`, version-pinned per recon open-question 6 — see Open Item 5). The spine is the *only* package that touches ohmypi.
- `@cassicore/mind-runtime` **MUST NOT** depend on `@oh-my-pi/pi-coding-agent` **or** on `@cassicore/spine`. It depends only on retained mind packages: `mnemic-field`, `helix`, `constellation`, `aurora`, `thalamus`, `flux-team`, `cortex-pineal-dialectic`, `mini-helix`, `workflow`, `foundation`, `events`, `utils` (plan §5 KEEP set).
- `@cassicore/spine` **MAY** depend on retained mind packages to construct/validate the tool schemas it re-exposes (it imports the retained `ToolDefinition` shapes from `@cassicore/tools` mind slice for schema/param fidelity), but its *runtime* communication with the mind goes **only over the internal channel** (§3.2) — never direct in-process module access.
- `@cassicore/spine` dev-depends on `@cassicore/tools` (mind slice: `ToolDefinition`/`ToolHandler` types + individual mind-tool definitions for schema reuse) — a `dependency` is acceptable, but prefer `devDependency` + type-import to keep the shipped extension lean.

**Placeholder package skeletons (executor creates these):**
```
packages/mind-runtime/
  package.json            # name: @cassicore/mind-runtime; type: module; bin: cassi-mind
  tsconfig.json
  src/
    boot.ts               # composition root (§3.1)
    channel/
      server.ts           # internal HTTP server (§3.2)
      protocol.ts         # request/response framing types
      routes.ts           # endpoint → handler map
    snapshot.ts           # mind-state snapshot journal (§4)
    index.ts              # run() entry
  test/
  README.md

packages/spine/
  package.json            # name: @cassicore/spine; omp.extensions: ["./dist/main.js"]
  tsconfig.json
  src/
    main.ts               # default factory export (ExtensionAPI)
    tools/                # pi.registerTool wrappers per retained mind tool
      collect-thoughts.ts
      graph-discover.ts
      mind-complete.ts
      subagents.ts        # list_subagents / get_subagent_status / get_subagent_result
      system-health.ts    # system_health / debug_session / universal_search / list_sessions
      cassandra.ts        # cassandra_query_events / cassandra_context_inspect / query_events
      coordinate.ts       # _coordinate / _check_peers (retained seam — see Open Item 8)
      memory-seam.ts      # _reflect / _remember / remember / memory_search (P5-deletion seam)
    lifecycle.ts          # session event handlers + appendEntry snapshots
    memory-backend.ts     # ctx.memory status/search/save adapter over MnemicField
    channel/client.ts     # runtime channel HTTP client (thin)
    schemas.ts            # omptype/Zod schema builders shared by tool wrappers
  test/
  README.md
```

---

## 2. Spike module spec (`@cassicore/spine`)

The spine is a factory-shaped ohmypi extension (recon §1.1): `export default function cassiSpine(pi: ExtensionAPI)`. It registers retained mind tools, mirrors session lifecycle, snapshots state, exposes the `mind_complete` bridge, and adapts MnemicField as the memory backend. It **never** hosts fragile background loops (recon §5.6).

### 2.1 Factory skeleton (TypeScript)

```ts
import type { ExtensionAPI, ToolDefinition } from '@oh-my-pi/pi-coding-agent'

export default function cassiSpine(pi: ExtensionAPI): void {
  const runtime = createChannelClient()   // §3.2; locates runtime (Open Item 1)

  // ── 2.4 Registered mind tools (execute delegates to runtime channel) ──
  registerMindTools(pi, runtime)          // §2.2

  // ── 2.5 Model-access bridge ──
  pi.registerTool(mindCompleteDefinition) // §2.3

  // ── 2.6 Session lifecycle → runtime mirror ──
  registerLifecycleHandlers(pi, runtime)  // §2.7

  // ── 2.8 mcp_notification bridging ──
  pi.on('mcp_notification', (e, ctx) => {
    void runtime.pushEvent({ type: 'mcp_notification', payload: e, sessionId: ctx.sessionId })
  })

  // ── 2.9 Memory backend adapter ──
  // (wired externally via ctx.memory; see §2.9)
}
```

### 2.2 Mind-tool registrations (every `pi.registerTool` mapped from real definitions)

All retained mind tools are registered as **thin delegates**: `pi.registerTool(def, handler)` where `def.parameters` is rebuilt from the retained `@cassicore/tools` `ToolDefinition.parameters` via `pi.zod`/`pi.arktype`, and `handler(toolCallId, params, signal, onUpdate, ctx)` forwards `{ tool, params, sessionId }` to the runtime channel and returns the mind's string/JSON response as `AgentToolResult`. None of these execute mind logic inside the spine.

**Registration count: 13 retained tools from plan §4.2** (12 retained mind tools + the `mind_complete` bridge). Exact names/params/handler-deps for each:

| Tool | Param schema (from real def) | Runtime handler deps (from `registerCoreTools` wiring) |
|---|---|---|
| `collect_thoughts` | `thought*:string, step*:number, estimated_steps*:number, continue_thinking*:boolean, is_revision?:boolean, revises_step?:number, branch_from_step?:number, branch_id?:string, needs_more_steps?:boolean, session_id?:string, posture_energy?:, related_context_mode?:` (required `[thought, step, estimated_steps, continue_thinking]`) | `collectThoughtsDeps` (see §3.1 wiring: branchingManager, thoughtObserver, cognitiveBridge, memory, mnemicField, bus, synapse, constellationGuidanceRegistry, getThinkerSession) |
| `graph_discover` | `edgeTypes?:string[], maxHops?:number, topN?:number, minCharge?:number` | `GraphDiscoverDeps` (`setGraphDiscoverDeps`: getPropagator, getBranchEngramIds, getBranchGoals) |
| `list_sessions` | `{}` | `sessionManager` |
| `list_subagents` | `status?:, parentSessionId?:, limit?:, includeTask?:` | `subagentTracker` / `thinker.listSubagents` |
| `get_subagent_status` | `runId*:string` | `subagentTracker.get` / `thinker.getSubagent` |
| `get_subagent_result` | `runId*:string, wait?:boolean, timeoutSeconds?:number, pollIntervalSeconds?:number` | `subagentTracker.get/getResult` / `thinker.getSubagent` |
| `system_health` | `includeProviders?:boolean, includeSessions?:boolean, includeTeams?:boolean, includeMemory?:boolean, includePlugins?:boolean, sessionLimit?:number` | `SystemHealthDeps` (daemon→mind-runtime, sessionManager, memory) |
| `debug_session` | `sessionId?:string, includeContext?:boolean, includeTurns?:boolean, includeCognitive?:boolean, turnLimit?:number, includeEvents?:boolean, eventLimit?:number` | `DebugSessionDeps` (sessionManager, memory, getEventBus, getContextWindowDebugger) |
| `universal_search` | `query*:string, sources?:string[], limit?:number, memoryLimit?:number, archiveLimit?:number, type?:string, threshold?:number, sessionId?:string, deduplicate?:boolean, sortBy?:string` | `UniversalSearchDeps` (memory, archive) |
| `cassandra_query_events` | `sessionId*:string, mode?:, noCache?:boolean, since?:number, limit?:number, eventTypes?:string[], compact?:boolean` | `eventBus` (via `registerCassandraEventTools`) |
| `cassandra_context_inspect` | `sessionId, action` (snapshot\|history\|stats) | `getContextWindowDebugger` |
| `query_events` | structured bus-query schema (`query_events.ts`) | `eventHistory` (via `createQueryEventsTool`) |
| **`mind_complete`** | `model:string, messages:Array<{role,content}>, tools?:ToolSchema[], effort?:, temperature?:number` → `{content, usage?, model}` | **spine-side only** (§2.3) — no runtime dep |

**Seam tools (P5-pending, plan §7.5):** `_reflect`, `_remember`, `remember`, `memory_search` are registered **behind a `[VERIFY]` gate** — plan §7 ratified deleting them (merge into ohmypi memory built-ins over the shared field). The P3 spine keeps their registration **inactive** (default `hidden: true, defaultInactive: true`) so the retained registration seam stays until the P5 deletion lands; P5 unregisters them. This lets P3 ship the full retained-mind surface without pre-empting the ratified deletion. `_coordinate`/`_check_peers` are retained-by-default mind tools NOT explicitly named in plan §4.2's list — include them as retained (they are mind operations, not coding/memory tools) but mark their survival `[VERIFY]` (they require the mind runtime to provide a session-digest-like peer store; see Open Item 8).

### 2.3 `mind_complete` — the model-access bridge (plan §2.3, exactly)

The only provider-adjacent surface the spine keeps. Registered via `pi.registerTool`. It is **not** forwarded to the runtime — it executes in the spine using ohmypi's own provider path:

```ts
const mindCompleteDefinition: ToolDefinition = {
  name: 'mind_complete',
  description: 'Perform a single model completion through the harness provider stack (no agent session). Used by mind-internal pure-completion primitives (corpus-LLM summarizer, brainstem-LLM).',
  parameters: pi.zod.object({
    model: pi.zod.string(),
    messages: pi.zod.array(pi.zod.object({ role: pi.zod.string(), content: pi.zod.string() })),
    tools: pi.zod.array(pi.zod.any()).optional(),
    effort: pi.zod.enum(['minimal','low','medium','high','xhigh','max']).optional(),
    temperature: pi.zod.number().optional(),
  }),
  execute: async (_id, params, _signal, _onUpdate, ctx) => {
    // 1. Resolve model: spec.model may be "provider/model-id" OR a role alias (@smol/@slow).
    //    ctx.models.resolve(spec) — recon §1.5/§2.6.
    const resolved = ctx.models.resolve(params.model)
    // 2. Stream ONE completion through ohmypi's provider path (ModelRegistry complete()
    //    / ctx.model). Effort + temperature passthrough.
    const content = await streamCompletion(resolved, params.messages, {
      effort: params.effort, temperature: params.temperature,
    })
    return { content, model: resolved.id /* + usage when surfaced */ }
  },
}
```

- **`ctx.models.resolve`** is the only model-resolution mechanism (recon §1.5: `models.list()/current()/resolve(spec)/family(model)`). Role aliases resolve through the same `resolve` per recon §2.6.
- Effort maps to the ohmypi `Effort` enum (`minimal|low|medium|high|xhigh|max`); temperature is passed straight through.
- **Streaming:** `mind_complete` returns a single completion — it does NOT stream (`onUpdate` is unused). Streaming is a P3+ open item (§5 Open Item 6); keep the execute signature streaming-capable but return a complete result now.

### 2.4 Lifecycle event handlers (session → runtime mirror, plan §4.2)

`pi.on(event, (e, ctx) => …)`. All events are cancellable pre-events in some cases; the spine mirrors **non-blocking** (never returns `{cancel}`). The runtime key is the **opaque `sessionId`** ("the unique opaque sessionId string that flows through turn processing") per recon §2.2.

```ts
pi.on('session_start',      (e, ctx) => void runtime.mirrorSession({ event:'start',   sessionId: ctx.sessionId }))
pi.on('session_switch',     (e, ctx) => void runtime.mirrorSession({ event:'switch',  sessionId: ctx.sessionId }))
pi.on('session_branch',     (e, ctx) => void runtime.mirrorSession({ event:'branch',  sessionId: ctx.sessionId, branchFrom: e?.entryId }))
pi.on('session_compact',    (e, ctx) => void runtime.mirrorSession({ event:'compact', sessionId: ctx.sessionId, summary: e?.summary }))
pi.on('session_shutdown',   (e, ctx) => void runtime.mirrorSession({ event:'shutdown', sessionId: ctx.sessionId }))
```

- Use the **post** events where both pre/post exist (`session_switch` vs `session_before_switch`, `session_branch` vs `session_before_branch`, `session_compact` vs `session_before_compact`). Post-events fire with the change already applied (recon §1.7); mirroring a post-event avoids racing the runtime against cancellable pre-hooks.
- `session_start` payload carries `cwd` + branch file; include `ctx.cwd` in the mirror so the runtime can attach session path context.

### 2.5 `appendEntry` snapshot pattern (plan §4.2)

On lifecycle events, the spine writes an opaque state snapshot into the session log so the mind's episodic state is reconstructable from the session tree:

```ts
function snapshotMindState(runtime, ctx) {
  pi.appendEntry('mind.runtime.state', {
    sessionId: ctx.sessionId,
    ts: Date.now(),
    state: runtime.getStateSnapshot(ctx.sessionId), // narrow: memory/store stats, active loops, session mirror ack
  })
}
```

- Called on `session_start`, `session_switch`, `session_branch` (snapshot the new branch's state), `session_compact` (post-compaction state), `session_shutdown`.
- Namespaced reverse-domain `mind.*.state` per recon §1.4/§1.8. Reconstructed via `ctx.sessionManager.getBranch()` on the *next* `session_start` (per recon §3.4/§1.8) — the spine passes the reconstructed snapshot to the runtime on start so the always-on process resumes the session.

### 2.6 Memory-backend adapter (`ctx.memory` status/search/save over MnemicField, plan §3)

Implements the behavioral backend interface recon documents as **status / search / save** (recon §1.5, §5.3; exact API [VERIFY] — recon fact-pack open-question 6.4). Lives in the spine because it's the only component at the `ctx` boundary.

```ts
// Adapter class skeleton. [VERIFY] exact ohmypi backend interface shape.
export class MnemicMemoryBackend implements MemoryRuntimeLike {
  constructor(private readonly field: MnemicLike) {}  // runtime proxy over channel
  async status()   { return { backend: 'mnemic-field', stats: await this.field.stats() } }
  async search(query: string, opts?: { limit?: number; type?: string }) {
    // MnemicField.retrieve(query, {limit, sessionId}) + searchText fallback.
    return (await this.field.retrieve(query, { limit: opts?.limit ?? 5 }))
      .map(h => ({ id: h.id, content: h.content, score: h.score, metadata: h.metadata ?? {} }))
  }
  async save(entry: { content: string; type?: string; metadata?: Record<string,unknown>; sessionId?: string }) {
    // MnemicField.store({ content, nodeType, metadata, provenance }) — see §3.1 fit table.
    return this.field.store({ content: entry.content, nodeType: entry.type ?? 'fact',
                              metadata: { ...(entry.metadata ?? {}), sessionId: entry.sessionId } })
  }
}
```

- **Mapping to MnemicField public surface (verified from `mnemic-field/src/index.ts`):** `store(input: EngramCreate): Engram`, `retrieve(query, options?): Promise<MnemicRetrievalHit[]>`, `searchText(query, limit?)`, `searchByProvenance(prov)`, `getEngramsBySessionId(sessionId, limit, offset)`, `stats(): FieldStats`, `kindle(...)`, `close()`, `getLightningStatus()`. The plan §3.1 fit table holds verbatim (store↔save, retrieve/searchText↔search, stats↔status).
- **Where the adapter runs:** both `ctx.memory` (ohmypi's `recall`/`retain`/`reflect`/`memory_edit` built-ins) and the mind's own memory ops must hit **the same field**. The runtime owns the field (plan §4.3); the spine adapter proxies over the channel, so ohmypi's built-ins and the mind runtime share one field (plan §3.2). If ohmypi's local-backend convention requires a `memory://` URI resolver, that resolver also proxies over the channel `[VERIFY]` per plan §3.2's exact-API note.
- **Backend API shape is undocumented** in the recon —— the executor MUST derive the exact `status/search/save` interface from ohmypi's memory-backend implementation at build time; all code against it is a thin adapter (the implementation detail is isolated to `memory-backend.ts`).

### 2.7 `mcp_notification` bridging (plan §4.2)

```ts
pi.on('mcp_notification', (e, ctx) => {
  // Push every JSON-RPC notification from connected MCP servers as a field/state event.
  runtime.pushEvent({ type: 'mcp_notification', payload: e, sessionId: ctx.sessionId })
})
```

Mind tools that touched external MCP servers (gitnexus/serena) now receive those notifications via this push (plan §5 verdict 29: ohmypi owns MCP client).

---

## 3. Mind-runtime spec (`@cassicore/mind-runtime`)

The focused always-on cognitive process: owns MnemicField + orchestration state machines + background loops, exposed only via a **narrow localhost channel** to the spine (plan §4.3/§1.2).

### 3.1 Composition root — `runtime/src/boot.ts`

Recreates the retained slice of the daemon's boot wiring (plan §5 verdict 26: "composition that builds MnemicField + injections"), **minus** providers/sessions/CLI/ACP/admin-api. Exact daemon calls quoted from `packages/host/src/daemon.ts`:

```ts
// ── Phase 2: Intelligence Layer ────────────────────────────────
// daemon.ts:729
this.intelligence = createIntelligence(this.logger, this.config, this.bus)
// daemon.ts:732-734
if (this.intelligence.cortex) this.intelligence.cortex.startOscillation()

// ── paths port (daemon.ts:611-626, P7 wiring matrix) ────────────
setRootResolver({ getCassiCoreHome: () => homePath })
setDataDirRoot(home ?? null)

// ── MnemicField open (daemon.ts:1568-1570) ─────────────────────
const field = new MnemicField(this.logger)          // dbPath resolved from CASSICORE_HOME
field.enableNeuralKindling()
sessionStore.setMnemicField(field)                  // if session-store port retained
;(this.intelligence as any).__mnemicField = field   // daemon.ts:1637

// ── MnemicField injections (quoted wiring) ─────────────────────
// daemon.ts:1572-1575   audit store
// daemon.ts:1597-1599   meditation.setMnemicField(field)
// daemon.ts:1603-1605   memory.setMnemicField(field)
// daemon.ts:1616-1621   consolidation receiver
// daemon.ts:1627-1630   archivist.setMnemicField(field)
if (this.intelligence?.constellation) this.intelligence.constellation.setMnemicField(field) // 1640-1642
field.setRerankerProvider(provider, model, true)    // 1673 — [VERIFY] no raw provider in focused runtime; reranker needs mind_complete shim (P4)
field.setLightningMode(mode)                        // 1685
field.setForeshadow(fs)                             // 1698

// ── orchestration bus (daemon.ts:259-261) ─────────────────────
this.orchestration = createOrchestrationBus(this.logger.child('orchestration'))
createSessionBridge(this.orchestration, this.logger.child('bridge'))  // if session bridge retained

// ── collect_thoughts deps (daemon.ts:1945-1956) ────────────────
collectThoughtsDeps = {
  branchingManager: new BranchingConversationManager(),
  thoughtObserver: this.intelligence.thoughtObserver,
  cognitiveBridge: this.intelligence.cognitiveBridge,
  memory: this.intelligence.memory,
  mnemicField: this.intelligence.__mnemicField,
  bus: this.bus,
  logger: this.logger.child('collect-thoughts'),
  synapse,                                        // createSynapse({llm:{complete:…}, logger}) — daemon.ts:1916-1939
  constellationGuidanceRegistry: this.intelligence.constellationGuidanceRegistry,
  getThinkerSession: (sid) => this.intelligence.thinker?.getThinkerSession?.(sid),
}
setGraphDiscoverDeps({ getPropagator, getBranchEngramIds, getBranchGoals })  // tools/src graph-discover seam

// ── unified intelligence loop (daemon.ts:763-798) ──────────────
const unifiedLoop = createUnifiedIntelligenceLoop(logger, bus, {
  enabled, backgroundIntervalMs, consolidationCadence, maintenanceCadence,
})
unifiedLoop.wire({ subconscious, memory, all: this.intelligence.all })
await unifiedLoop.start()
```

**Model access in the focused runtime (P4 boundary — this brief only defines the seam):** the daemon wired `helixModelPool` and pushed `ModelHandle`s into the mind:
- `this.intelligence.setMeditationHandleFactory((cfg) => helixModelPool.acquire('unity', cfg.tier, cfg.sessionId))` (daemon.ts:1492-1493)
- `setCorpusLLMProvider(await helixModelPool.acquire('unity', undefined, 'corpus-llm', opusCfg), opusCfg.model)` (daemon.ts:2317-2318)
- `setBrainstemLLMProvider(await helixModelPool.acquire('mini-helix:brainstem', undefined, 'brainstem-llm', glmCfg), glmCfg.model)` (daemon.ts:2333-2334)

Under P4 these become `mind_complete` calls or task-agent spawns. P3 does **not** wire a real provider; it boot the retained mind with **no live LLM handles** (those loops are P4 cutover). Define the retained `ModelHandle`-cast seam (`@cassicore/model-pool` PORT, plan §5 verdict 19) so P4 can inject the `mind_complete`-backed handle. **The P3 runtime boots the cognitive field + loops without provider calls.**

**What the composition root does NOT include** (per plan §5 verdicts 22-31): `createAdminApi`, `createBridge` (openai), `CommandDispatcher`, channel workers, `PluginHost`, `createModelRouter`/providers, `SessionPipeline`/`TurnPipeline`, `PrimarySessionRouter`, PID-file singleton enforcement (the supervisor owns that), config watcher, `.env` secrets loader, `_loadEnv`, budget tracker, model directive (`ModelDirective.resolveTier`) — all standalone-surface. The `intelligence` layer, MnemicField, orchestration bus, unified loop, and mind-tool deps are the retained core.

### 3.2 The narrow internal channel (default: localhost HTTP on a private port)

Loopback HTTP mirrors today's gateway→daemon `http://localhost:7433` pattern (plan §1.2 note) with the standalone surface removed. Bind **`127.0.0.1` only**, private ephemeral-or-configurable port (default **`7273`**, distinct from the retired 7433 to avoid colliding with any lingering daemon). JSON over HTTP; a bare request/response protocol (§5 Open Item 7 defines framing; the endpoints below are the stable contract).

**Endpoint list (all `POST /…` JSON, auth = loopback-bind + optional shared bearer token from `CASSI_MIND_TOKEN`):**

| Endpoint | Purpose | Request → Response |
|---|---|---|
| `POST /v1/tools/execute` | Spine delegates retained mind-tool calls to the runtime | `{ tool, params, sessionId }` → `{ ok, result: string }` or `{ ok:false, error }` |
| `POST /v1/session/mirror` | Session lifecycle events from spine (start/switch/branch/compact/shutdown) | `{ event, sessionId, cwd?, branchFrom?, summary? }` → `{ ack: true }` |
| `POST /v1/events/push` | `mcp_notification` and other pushed harness events into the mind as field/state events | `{ type, payload, sessionId }` → `{ ack: true }` |
| `POST /v1/snapshot` | Spine fetches mind-state for `appendEntry` | `{}` → `{ state: Snapshot }` (memory/store stats, active loops, session mirrors) |
| `POST /v1/health` | Spine + supervisor liveness probe | `{}` → `{ status:'ok', uptimeMs, fieldStats?, lightningStatus? }` |
| `GET /v1/health` | Plain liveness (no body) | `200 ok` |
| `POST /v1/memory/status` | Memory-backend adapter `status()` | `{}` → `{ backend, stats }` |
| `POST /v1/memory/search` | Adapter `search(query, opts)` | `{ query, limit?, type? }` → `{ results:[{id,content,score,metadata}] }` |
| `POST /v1/memory/save` | Adapter `save(entry)` | `{ content, type?, metadata?, sessionId? }` → `{ id }` |
| `POST /v1/shutdown` | Graceful stop (spine `session_shutdown` fan-out; supervisor) | `{}` → `{ ok }` |

The `memory/*` endpoints and `tools/execute` are the only runtime-mutating surface; everything else is read/push. **Explicitly NOT included:** providers, session infra, CLI, ACP, admin-api (plan §5 verdicts 22-31), and the 54-route admin surface (its retained mind-health read slice folds into `/v1/health` + `/v1/snapshot`).

### 3.3 Spawning / discovery (link to §5 Open Item 1)

The spine locates the runtime by **env var `CASSI_MIND_URL` → auto-spawn fallback**: if unset, the spine spawns `cassi-mind` (bin from `@cassicore/mind-runtime`) as a child process (recon §5.1: "must be spawned/run outside ohmypi (e.g. via hub start…)") and waits for `/v1/health`. Auto-spawn uses `child_process.spawn` (detached, `stdio: ignore` beyond the health probe) so the runtime survives session shutdown. The supervisor path is the non-interactive host (hub `start`). Full resolution in Open Item 1.

---

## 4. Test strategy (plan §6 P3 row: "contract tests: registered tools, event bridge, backend store/search/status")

**No live ohmypi in CI.** All spine tests stub the `ExtensionAPI` (recon §1.1 factory shape: a minimal fake exposing `registerTool`, `on`, `appendEntry`, `eventBus`, `zod`, `arktype`, `models.resolve`, `logger`, managed timers) so the extension factory runs headless against the stubbed bridge. Mind-runtime tests run real retained-mind packages on a temp `CASSICORE_HOME` + in-memory/wal sqlite plus a real MnemicField (or a stubbed `MnemicLike` for pure-channel tests).

| Test file (executor creates) | Asserts |
|---|---|
| `spine/test/registered-tools.test.ts` | Factory registers **13 retained tools** (plan §4.2) + the 4 seam tools hidden. For each: name matches the retained `@cassicore/tools` def, `parameters` (omptype) validates the retained def's required-fields and rejects bad input, handler delegates `{tool,params,sessionId}` to the stubbed runtime channel client and returns the channel result. `mind_complete` handler: resolve-model called with the spec; effort/temperature passed through to the stubbed completion; returns `{content, model}`. |
| `spine/test/lifecycle-bridge.test.ts` | Each of `session_start/switch/branch/compact/shutdown` fires `runtime.mirrorSession` with the right `{event, sessionId, …}`; post-events (not pre/cancel) are wired; `appendEntry('mind.runtime.state', …)` is called on each lifecycle event with a `{sessionId, ts, state}` snapshot; `mcp_notification` pushes `{type, payload, sessionId}`. |
| `spine/test/memory-backend.test.ts` | Adapter `status()` → field.stats; `search(q)` → mapped MnemicField.retrieve hits `{id,content,score,metadata}`; `save(entry)` → MnemicField.store called with `{content,nodeType,metadata,provenance}` and returns the engram id. Runs against a real MnemicField (temp home) to assert the field round-trips. |
| `mind-runtime/test/boot.test.ts` | `boot.ts` constructs intelligence-layer + MnemicField + orchestration bus + unified loop without provider access; MnemicField opens its wal DB under `CASSICORE_HOME`; injections (`setMnemicField` on memory/meditation/archivist/constellation, `setGraphDiscoverDeps`, `collectThoughtsDeps`) are wired; `close()` releases the DB. |
| `mind-runtime/test/channel.test.ts` | HTTP server binds `127.0.0.1` only; each endpoint in §3.2 responds per contract: `tools/execute` runs the retained tool handler and returns its string result; `session/mirror` + `events/push` ack; `snapshot` returns state; `health` 200; `memory/*` round-trip store→search; unknown path → 404; no auth/bad token → 401. |
| `mind-runtime/test/mind-tools-runtime.test.ts` | `collect_thoughts`, `graph_discover`, `list_sessions`, `list_subagents`, `system_health`, `debug_session`, `universal_search`, `cassandra_query_events`, `cassandra_context_inspect`, `query_events` execute against the retained mind with stubbed deps (fake sessionManager/memory/eventBus) and return non-empty strings without throwing. |

**Mind suites untouched** (plan §6 P3: "Mind suites untouched") — this phase only *adds* the spine/runtime contract suites; no retained suite is modified.

---

## 5. Open items for the P3 executor (≤10, each with recommended resolution)

1. **How the spine locates the runtime.** **Resolution:** `CASSI_MIND_URL` env var wins; if unset, spine `child_process.spawn`s the `@cassicore/mind-runtime` bin (detached, `stdio: ignore`, waits on `GET /v1/health` with a short timeout, then errors gracefully if unreachable). Non-interactive hosts use hub `start`. Port configurable via `CASSI_MIND_PORT` (default 7273).
2. **Channel protocol framing.** **Resolution:** plain HTTP/1.1, `Content-Type: application/json`, one request–response per call. No streaming on `tools/execute` for P3 (retained tools return complete string results). Keep a `requestId` echo field for correlation/logging.
3. **Where mind-state snapshots live.** **Resolution:** dual — (a) the runtime persists its own field/store under `CASSICORE_HOME` (SQLite+LMDB, already MnemicField's home), and (b) the spine writes reconstructable episodic snapshots via `pi.appendEntry('mind.runtime.state', …)` into the ohmypi session tree (plan §4.2). The appendEntry copy is the *episodic journal*; the field is the *semantic memory*.
4. **Runtime crash/restart ownership.** **Resolution:** the spine does NOT supervise (recon §5.6 — spine timers are unref'd + cleared). Supervisor-mode hosts (hub `start`) own restart; the spine's spawn fallback re-spawns on health-probe failure at *session start only*, not mid-session.
5. **ohmypi version to pin.** **Resolution:** pin the current documented `@oh-my-pi/pi-coding-agent` in the spine `devDependencies` (recon open-question 6 explicitly calls for pinning). Record the exact pinned version + the inspected `ExtensionAPI`/`ToolDefinition` signatures in `packages/spine/README.md` so drift is caught at build time (dev-dep types break the build on API change).
6. **Does `mind_complete` support streaming?** **Resolution:** No for P3 — single-shot completion, `onUpdate` unused. The retained pure-completion consumers (corpus/brainstem) don't need streaming (plan §2.3). Add streaming as a P4+ enhancement if a mind loop needs token-level output.
7. **Mind-tool result encoding.** **Resolution:** retained handlers return strings (per `ToolHandler`); the channel already returns `{ result: string }`. The spine maps `result` to `AgentToolResult.content` verbatim. No structured-content wrapper for P3.
8. **Retention of `_coordinate` / `_check_peers`.** **Resolution:** [VERIFY] — they are mind operations, not memory-read/write, so plan §7.5's deletion list (only `_reflect`/`_remember`/`remember`/`memory_search`) does not remove them. They need a peer-store (`SessionDigestStore`) + memory KV + CognitiveBridge, which the mind runtime provides. Confirm at P3 implementation; if the digest-store port is out of the retained KEEP set, mark them `hidden` behind the same seam as the memory tools.
9. **Memory-backend `memory://` resolver.** **Resolution:** [VERIFY] against the exact ohmypi backend interface (Open Item's undefined shape per recon §6.4). If the local/structured backend convention requires `memory://` reads, add a `POST /v1/memory/read` channel endpoint proxying MnemicField get/searchByProvenance. Default: skip unless the backend contract requires it.
10. **Runtime config provisioning.** **Resolution:** `mind-runtime` reads `CASSICORE_HOME` (+ same `intelligence.*` defaults the daemon used) directly — no `Config.load()`/watcher daemon machinery. Hardcode the retained defaults the P3 boot needs (unified-loop cadences, lightning mode off) and wire config via env vars; the layered-config/watcher surface is standalone (plan §5 26).
