# CASSICORE-FOCUS — The Focused CassiCore Design

**Root:** `C:\Users\Carina\Workspaces\CassiCore\`
**Type:** DESIGN deliverable + P6 execution record.
**Date:** 2026-08-14
**Status:** RATIFIED (owner 2026-08-14) — P6 surface removal DONE (4 UI apps + 3 external bridges deleted).
**Companion inputs:**
- `recon-oh-mypi-capabilities.md` — ohmypi fact-pack (ExtensionAPI, providers, sessions, tools, gaps).
- `recon-cassicore-surface.md` — CassiCore standalone-surface inventory, seam surface, Part 3 classification.
- `MIGRATION-STATUS.md` — 38 landed packages, test counts, host↔tools/mcp cycle, handoff points.

---

## 0. Executive summary — the decision in one paragraph

The owner's directive is correct and the recon evidence supports it: ohmypi owns PROVIDERS, AGENT SESSIONS, and TOOLS; CassiCore becomes a **focused cognitive mind** — not a standalone daemon. The concrete shape is **hybrid**: a thin ohmypi **extension ("spine")** that registers the mind's tools and bridges lifecycle events, wrapping a **focused mind runtime** that owns the always-on cognitive state (mnemic-field store, orchestration state machines, background loops). **Model access is the pivotal decision**: mind-internal reasoning loops do NOT keep a private provider stack — they run as ohmypi task sub-agents (option A-primary), with a **model-call bridge tool** (option B) as the in-process fallback for the few loops that need raw completions without a full agent turn. **MnemicField becomes ohmypi's memory backend** — the "ohmypi handles memory session, CassiCore IS the memory" play. **38 packages → 24 keep/port, 4 delegate, 5 delete, 3 bridge, 2 split-verdict** (exact counts and per-package verdicts in §5). All deletions are clean history-preserving commits because the workspace git already carries the full history.

---

## 1. Run-model choice — hybrid (the "spine" + focused runtime)

### 1.1 The three candidate models

| Model | What it is | Always-on runtime | Orchestrator layer | Memory wiring |
|---|---|---|---|---|
| (A) External sidecar MCP server | CassiCore runs as its own process exposing an MCP **server** that ohmypi connects to | Yes (own process) | Self-hosted (daemon stays) | Self-hosted |
| (B) In-process ohmypi extension only | Everything lives inside one ohmypi extension; the mind is a plugin library | **No** — recon gap §5.1/§5.6 | None — layered on task/hub | Optional `ctx.memory` |
| **(C) Hybrid (chosen)** | Thin ohmypi extension ("spine") + focused mind runtime for the always-on parts | Yes (focused runtime) | Mind runtime owns orchestration state machines | MnemicField as memory backend |

### 1.2 Why the hybrid wins — the evidence

The recon fact-pack is explicit about what ohmypi cannot host:

> **Gap §5.1:** "Long-running / persistent background daemons. Extensions run in-process, no sandboxing; managed timers (`ctx.setInterval`) are `unref`'d and cleared on `session_shutdown`. There is no plugin-owned, process-independent background service."

> **Gap §5.6:** "Long-lived process-lifetime guarantees. The plugin runtime has no process-isolation; a raw timer/async throw can crash the whole session (`uncaughtException`). So plugins must not host fragile/reliable background runtime."

This kills option (B) as a *standalone* host for the cognitive runtime: the mind's whole point is persistent field state (MnemicField's SQLite+LMDB store), background consolidation/kindling loops, and a durable orchestration layer. Pure (B) would tear the field down every session shutdown and crash the whole ohmypi session on any cognitive async throw. **The spine must never own the fragile cognitive runtime** — that is exactly what recon §5.6 warns against.

But option (A) — full external sidecar MCP server — is also wrong, for a different reason. It preserves the standalone-daemon posture the owner explicitly retired. The MCP gateway (43 files/17,004 lines) exists only because CassiCore was a self-contained daemon; making the mind a *server* recreates the daemon's boot/supervisor/HTTP-wiring burden in a new coat. And recon §4.4/§6.1 shows ohmypi's MCP role is **client-only** — there is no documented `mcp-server` mode for ohmypi to connect to, so the mind-as-server would be talking to a harness that is not built to be a client of it. [VERIFY: ohmypi `mcp-server` mode absence — see its recon §6.1; confirmed against docs read, not exhaustively.]

**The hybrid splits the difference cleanly:**

- **The spine** is an ohmypi extension (factory shape, `recon §1.1`). It is *not* the cognitive engine — it is the *mouth and ears*: it registers the mind's LLM-callable tools, reacts to session lifecycle events, and bridges them into the mind runtime. It is small, event-driven, and never hosts fragile background loops (so `§5.6`'s crash risk is bounded to the spine itself, not the field).
- **The focused mind runtime** is the always-on cognitive process. It owns MnemicField (open SQLite+LMDB field), orchestration state machines (helix/constellation posture runners), and background loops (consolidation, kindling, reprojection). It is process-independent — satisfying `§5.1`'s "must be spawned/run outside ohmypi."

The bridge between them: the mind runtime is a **localhost service** (a focused, slimmed version of the daemon's composition root — see §4), and the spine talks to it over a narrow internal channel (loopback HTTP, mirroring today's gateway→daemon `http://localhost:7433` pattern, but with the standalone surface removed). [VERIFY: internal loopback channel choice — the recon documents today's gateway uses `localhost:7433`; the exact channel (HTTP vs stdio RPC) is [ASK-5]-adjacent, defaulting to a thin localhost HTTP service.]

**Verdict: (C) hybrid. Justification:** the always-on runtime constraint alone rules out pure-extension (B); the owner's "not a standalone daemon" directive plus ohmypi's client-only MCP role rules out external-sidecar (A); the hybrid keeps the mind's process independence where it is load-bearing (field persistence, background loops, orchestration) while pushing all user-facing surface (tools, sessions, providers) into ohmypi where the owner wants it.

---

## 2. Model access — THE pivotal question

### 2.1 The problem stated precisely

The mind's internal reasoning loops currently run through the daemon's `ModelPool`/`ModelHandle`. From `recon-cassicore-surface §2.1`:

> "No mind package imports `@cassicore/providers` or `@cassicore/ai`. The seam is *indirect*: the daemon boots providers, wraps them into a `ModelPool`, and hands the resulting `ModelHandle`/pool to the mind."

The daemon acquires handles and injects them (recon §1.4 quotes): `helixModelPool.acquire('unity', …)` for meditation/corpus, `setCorpusLLMProvider(await helixModelPool.acquire('unity', …, 'corpus-llm', opusCfg))`, `setBrainstemLLMProvider(… acquire('mini-helix:brainstem', …, 'brainstem-llm', glmCfg))`. When ohmypi owns providers, these loops still need completions — but they must come through ohmypi's provider stack + secrets, not a CassiCore-side re-implementation.

### 2.2 The concrete options (with evidence)

**(a) Mind sub-agents run as ohmypi task agents.** The mind orchestrates via `hub`/`task` (spawn/steer/park/revive). Every cognitive loop that needs a completion becomes an agent that ohmypi's own agent loop runs — provider calls flow through ohmypi naturally. Evidence (recon §3.3): ohmypi's task layer supports "spawn, steer, park, revive," lifecycle `running|idle|parked|aborted`, model priority `task.agentModelOverrides → agent frontmatter model → parent's model`, plus SDK `outputSchema`, `taskDepth`, `parentTaskPrefix` "for orchestrators." When the mind *is* a collection of agents, ohmypi handles model selection, credentials, streaming, tool routing.

**(b) Model-call bridge tool registered by the spine.** The spine registers one tool (e.g. `mind_complete`) whose handler performs a completion using ohmypi's own provider path (`ctx.models.resolve(spec)` + the SDK's completion API, or `complete()` through `ModelRegistry`). The mind calls `mind_complete({provider, model, messages, …})` and the spine executes it with ohmypi-managed providers+secrets. Evidence (recon §1.5, §2.6): `ctx.modelRegistry`/`models` give read/select; `setModel`/role aliases exist; "a plugin does not manage raw API keys for built-in providers." This gives the mind a *completion primitive* without a full agent turn.

**(c) Mind keeps a thin provider port the host wires (last resort).** This is the current daemon design kept alive but slimmed — a `ModelHandle`/`IProvider` seam that some external host fills with a provider object. Evidence (recon §2.2): the mind already consumes only the `ModelHandle` surface + foundation `IProvider`; it would mean CassiCore still owns *some* provider-adjacent seam, against the spirit of the directive.

### 2.3 Recommendation

**Primary: (a) task agents.** The vast majority of mind-internal reasoning (helix posture runners, constellation strategies, mini-helix brainstem, cognitive-feed turns) is already *turn-structured* — it wants a model + tools + a session, exactly what an ohmypi agent session provides. Mapping "mind loop" → "ohmypi task agent" is a one-to-one substitution for the current `handle.stream(messages)` calls wrapped in a loop (recon §2.3: `handle.stream`/`handle.release`). The mind keeps its orchestration logic; it launches agents instead of streaming to a handle. This also solves credential secrecy: ohmypi resolves and never exposes keys to CassiCore.

**Fallback: (b) the `mind_complete` bridge tool.** Some cognitive primitives are *not* agent loops — e.g. the corpus-LLM summarizer (a single big completion on a large context, no tools) and the brainstem-LLM (a single completion). Wrapping these in a full agent session is overkill and costs a session-tree entry + subagent lifecycle per call. A single `mind_complete` tool lets the mind do raw completion with ohmypi's providers but without a session. **This is the interface shape:**

```ts
// spine-source model-access bridge (registered via pi.registerTool)
mind_complete(spec: {
  model: string;            // "provider/model-id" or a role alias (@smol/@slow)
  messages: Array<{role, content}>;
  tools?: ToolSchema[];     // optional — rare for pure completions
  effort?: "minimal"|"low"|"medium"|"high"|"xhigh"|"max";
  temperature?: number;
}): { content: string; usage?: {...}; model: string }
```

The spine handler resolves `spec.model` via `ctx.models.resolve`, streams one completion through ohmypi's provider path, and returns the text. **Option (c) is explicitly non-preferred** — it keeps a provider seam CassiCore must explain, test, and secure, for no benefit over (b).

**Which loops use which:** every turn-structured cognitive loop → (a). Pure single-completion primitives (corpus-LLM, brainstem) → (b). No mind package imports `@cassicore/providers`/`@cassicore/ai` after this (§5 deletes them).

---

## 3. Memory — MnemicField as ohmypi's backend; the mind tools' fate

### 3.1 What ohmypi's memory backend interface requires vs what MnemicField provides

Recon §5.3: "Structured memory (`recall`/`retain`/`reflect`/`memory_edit`) exists only when a memory backend is configured (`memory.backend: mnemopi` or `hindsight`)." And `ctx.memory` is "optional structured memory runtime — status/search/save across the configured backend" (recon §1.5). So the backend contract, as documented behaviorally, is **status / search / save** (the recon is explicit this shape is "not fully spelled out" — [VERIFY] exact backend API = `compaction`/memory docs; flagged §6.5 in the fact-pack).

MnemicField provides, from its actual public surface (read from `packages/mnemic-field/src/index.ts`):
- **save:** `store(input: EngramCreate): Engram` — creates an engram with embedding (vindex gate-vectors or vLLM), VQ sector position, HEALPix spatial index, feature index, synapses, decomposition.
- **search:** `retrieve(...)` (spreading-activation kindling), plus `searchText`, `searchByProvenance`, `getEngramsBySessionId`, `querySpatial`, `neighbors`.
- **status:** `stats(): FieldStats`, `getLightningStatus()`, `computeHarmony()`, `getFractalDimension()`.

**Fit: strong.** The three verbs line up one-to-one (store↔save, search/retrieve↔search, stats↔status). MnemicField is richer than required — it adds spatial/synaptic/cognitive structure the backend interface ignores. That's fine: the adapter exposes store/search/status and *the rest of the field stays alive underneath* for the mind.

### 3.2 The "ohmypi IS memory / CassiCore IS the memory" play

The recon confirms memory is **off by default** and **pluggable** (§5.3, §2.5 — "A plugin needing rich cognitive memory must plug its own backend"). Wiring `memory.backend` to a **mnemic-field backend adapter** is the single highest-leverage move in the whole design:

- ohmypi's agent sessions get *the Cassi memory field* — `recall`/`retain`/`reflect`/`memory_edit` (and `learn`) read/write engrams with full cognitive structure.
- The mind and the harness **share one field** — no dual memory (ohmypi's mnemosyne *and* CassiCore's field). This is the "ohmypi handles memory session, CassiCore IS the memory" inversion the directive invites.
- The always-on runtime owns the field lifecycle (open/consolidate/kindle), so the backend is durable across ohmypi sessions and process restarts — closing the recon gap that memory is "off by default" and only session-scoped when a plugin relies on `custom` entries.

**The adapter** lives in the mind runtime / spine and implements the backend interface (status/search/save) over the running `MnemicField`, plus a `memory://` URI resolver if the local-backend convention requires it. [VERIFY: whether the mnemic backend must also expose `memory://` reads and an optional `learn` path — recon §2.5 notes the *local* backend exposes those but structured backends (mnemopi/hindsight) center on recall/retain/reflect/memory_edit.]

### 3.3 Fate of the recall/retain/reflect/remember mind tools

ohmypi already owns `recall`, `retain`, `reflect`, `memory_edit` (recon §4.1). When MnemicField is the backend, those harness built-ins operate on the field. Therefore:

- **`_reflect` / `_remember` / `remember` / `memory_search`** (mind tools, recon §1.3 §1.4) become **redundant** — their function is memory read/write, now owned by ohmypi's built-ins over the shared field. **Delete** (after the adapter lands). Keep the *type/registration* seam (`cognitiveToolDeps` injection) only if a mind loop still calls them by name — [VERIFY] on whether any helix/constellation loop invokes these by tool-name rather than via the backend.
- **`collect_thoughts`** is NOT redundant — it is a structured *cognitive* operation (branching+revision, ThoughtObserver → field), not a memory read/write. **Keep** as a spine-registered mind tool.
- **`graph_discover`** is NOT redundant — it is field-structure discovery (neural-graph over mnemic-field/constellation), not a recall. **Keep.**

The rule: anything that is *literally* "save this string / search for strings" merges into ohmypi's memory built-ins over the shared field; anything that is *a cognitive operation on the field's structure* stays a CassiCore mind tool.

---

## 4. The new shape — concrete

### 4.1 Processes

1. **ohmypi** (the harness) — runs the interactive session(s), owns providers/secrets, the session tree, the coding tools, and hosts the spine extension.
2. **The focused mind runtime** (one always-on process) — owns `MnemicField` (open DB, field cache, consolidation/kindling/reprojection loops), the orchestration state machines (helix/constellation posture runners, flux-team blackboard, aurora loop), and exposes a **narrow localhost surface** to the spine. Spawned/hosted as an external service (recon §5.1: "must be spawned/run outside ohmypi (e.g. via `hub` start…)").
3. **(Optional per [ASK-2]) a slim orchestrator process** — if the mind's orchestration (cohort/team state machines) must outlive any single ohmypi session, it lives inside the focused runtime, not in the extension.

### 4.2 What the spine extension does

- **Registers the mind's LLM-callable tools** via `pi.registerTool` with omptype schemas (`pi.arktype`/`pi.zod`, recon §1.8/§4.2): `collect_thoughts`, `graph_discover`, `mind_complete`, `list_sessions`, `list_subagents`, `get_subagent_status`, `get_subagent_result`, `system_health`, `debug_session`, `universal_search`, `cassandra_query_events`, `cassandra_context_inspect`, `query_events` — the retained mind tools from §5.
- **Session lifecycle → mind session mirroring.** Hooks `session_start`, `session_switch`, `session_branch`, `session_compact`, `session_shutdown` (recon §1.7) and mirrors a mind-session id into the runtime (via the internal channel). `sessionId` is the "unique opaque sessionId string that flows through turn processing" the mind needs (recon §2.2).
- **`mcp_notification` bridging.** Any MCP server notification ohmypi receives is bridged into the mind runtime as a field/state event — recon §1.7 describes `mcp_notification` as the canonical push-bridge, and mind tools today touch external MCP servers (gitnexus/serena, recon-architecture).
- **`appendEntry` for mind state snapshots.** The spine writes `pi.appendEntry("mind.*.state", snapshot)` on lifecycle events so the mind's episodic state is reconstructible from the session tree — using the fact-pack's §1.8 note that extensions "reconstruct from `sessionManager.getBranch()` on `session_start`" — matching the mind's need for a durable per-session journal (recon §2.2: "mind needs = a unique opaque `sessionId` + mind-owned per-session stores").
- **Model-access bridge** (`mind_complete`, §2.3) — the only provider-adjacent surface CassiCore keeps, and it is a *call into ohmypi*, not a CassiCore-provider stack.
- **Memory backend adapter** — implements `ctx.memory` status/search/save over the running MnemicField.

### 4.3 What the mind runtime owns

- **mnemic-field store** — SQLite+LMDB persistence, consolidation, kindling, reprojection, HEALPix spatial index, vindex feature index.
- **Orchestration state machines** — helix/constellation posture runners, flux-team blackboard, gradient/backprop, cortex/pineal/dialectic, aurora loop. These are *orchestrator logic* (recon gap §5.2: ohmypi has "no orchestrator/swarm above subagents"), so the mind layers it on `task`/`hub` — which is exactly what ohmypi's §5.2 allows ("a plugin that wants its own orchestration must layer it on `task`/`hub`"), except the orchestration state lives in the always-on runtime, not the plugin.
- **Background loops** via task agents (launching ohmypi agents for kindling-triggered reasoning, constellation strategies, etc.) and via the runtime's own timers (consolidation/reprojection) — the latter are the runtime's always-on responsibility, not the spine's (spine timers are `unref`'d + cleared, recon §5.1).

### 4.4 How constellation/helix sessions map onto ohmypi sessions

The mind-internal session stores (helix `HelixStore`, constellation `ConstellationStore`, mini-helix, `module-session-registry` — recon §2.2) **stay** as the mind's *state model*. What changes is who drives a *turn*:

| CassiCore today | Focused CassiCore |
|---|---|
| daemon `SessionPipeline`/`TurnPipeline` processes a user turn | ohmypi's agent session processes the turn; spine mirrors `sessionId` into the mind |
| helix/constellation posture runners stream a model | they spawn **ohmypi task agents** (or call `mind_complete`) for completions |
| constellation sub-agents | = ohmypi `hub` sub-agents (task agents the mind spawned); the mind steers/parks/revives them via `hub` (recon §3.3) |
| corpus tree / run tree (cassicore:// sessions, replay) | mirrored via `appendEntry` + the mind runtime's own journal; the append-only session **tree** (ohmypi's) is the *host* of episodic record, while the field (MnemicField) is the *semantic* memory |

**Direct answer:** ohmypi task/hub subagents **are** the constellation subagents — the mind's orchestration logic stays, but the individual agents are ohmypi agents. The ohmypi session tree is the *container* for mirrors; the corpus/field tree is the *content*.

---

## 5. Package verdicts — for all 38 packages

Legend: **KEEP** (mind; stays as-is in the focused runtime) · **PORT** (thin seam — keep the interface slice, drop the standalone surface) · **DELEGATE** (ohmypi replaces; package deleted after the adapter/spine lands) · **DELETE** (vanishes) · **BRIDGE** (external-tool integration).

| # | Package | files/tests | Class | Verdict | Reasoning |
|---|---|---|---|---|---|
| 1 | `mnemic-field` | 6/89 | MIND | **KEEP** | The memory field; now ohmypi's memory backend + the mind runtime's core store. Largest mind asset. |
| 2 | `helix` | 9/75 | MIND | **KEEP** | Helix orchestrator; model-pool/tools become injected types/handles via task-agents/seam. |
| 3 | `constellation` | 25/568 | MIND | **KEEP** | Constellation; orchestrates ohmypi task subagents. |
| 4 | `aurora` | 36/698 | MIND | **KEEP** | Cognitive loop. |
| 5 | `thalamus` | 6/97 | MIND | **KEEP** | Attention/brain-state; the `isWriteTool`/etc. pipeline-type imports → a retained type seam. |
| 6 | `flux-team` | 4/186 | MIND | **KEEP** | Team blackboard state machine. |
| 7 | `dreamer-reverie-subconscious` | 8/184 | MIND | **KEEP** | Dreamer/reverie/subconscious. |
| 8 | `cognitive-feed` | 1/97 | MIND | **KEEP** | Cognitive feed; its `InteractiveToolSession` runtime use → spine/tool-loop seam. |
| 9 | `cortex-pineal-dialectic` | 4/143 | MIND | **KEEP** | CPD. |
| 10 | `mini-helix` | 1/21 | MIND | **KEEP** | Mini-Helix; `ModelHandle.stream` → `mind_complete` or task-agent. |
| 11 | `workspace` | 1/17 | MIND | **KEEP** | GlobalWorkspace/system-prompt; feeds ohmypi the system prompt via spine. |
| 12 | `embeddings` | 0/0 | MIND | **KEEP** | Embeddings; consumed by field (estimateTokens). |
| 13 | `training-trust-ledger` | 2/53 | MIND | **KEEP** | Training/trust. |
| 14 | `lamina-locus-bridge` | 1/8 | MIND | **KEEP** | Lamina + locus-bridge. |
| 15 | `foundation` | 1/10 | MIND/substrate | **KEEP** | Shared types/interfaces/paths, `IProvider`/`IModelDirective` contract. The retained type seam. |
| 16 | `events` | 0/0 | MIND/substrate | **KEEP** | EventBus/Logger. Needed by every retained package. |
| 17 | `utils` | 0/0 | MIND/substrate | **KEEP** | Generic utils (TTLCache, CircuitBreaker). |
| 18 | `workflow` | 0/0 | MIND (borderline) | **KEEP (PORT)** | `WorkflowEngine` is heavily used by constellation (strategies) and the mind's `workflow` tool still wants it. **Port** to what constellation + the retained mind-tool surface use; drop the daemon-gated workflow-`run_background` integration. |
| 19 | `model-pool` | 1/32 | MIND (surface) / split | **PORT** | Keep ONLY `ModelHandle`/`ModelHandleImpl`/`ModelCompletionOpts` types + a shim of `acquire/release` that produces an ohmypi-backed handle (a completion primitive that calls `mind_complete` or spawns a task agent). Drop budget/billing/fallback/centralized — ohmypi owns routing; the retained `ModelHandle` is the *mind's cast* over an ohmypi completion. 8 files/3,045 → ~2 files of types+shim. |
| 20 | `tools` | 3/39 | SPLIT | **SPLIT** | **Mind slice → PORT (spine-registered mind tools + `ToolExecutor`/`ToolRegistry`/`ToolDefinition`/`ToolExecutionContext` types + `InteractiveToolSession`).** CODING tools (`shell_exec`, `cassi_shell`, `read_file(s)`, `write_file`, `web_fetch`, `web_search`, `todo_write`, `run_tests`, `desktop_vision`, `vybit`) → **DELEGATE** (ohmypi own these built-ins; the retained type-only imports make the mind code compile against a seam). |
| 21 | `pipeline` | 1/2 | STANDALONE-SURFACE | **DELEGATE** | `SessionPipeline`/`TurnPipeline` user-facing chat infra → ohmypi sessions. Mind keeps only the *classification* type imports (thalamus `isWriteTool` etc.) — keep those as a tiny retained type surface, not the package. |
| 22 | `commands` | 0/0 | STANDALONE-SURFACE | **DELETE** | Slash-command dispatcher for channels/CLI — ohmypi owns commands. Nothing mind-required. |
| 23 | `workers` | 2/97 | STANDALONE-SURFACE | **DELETE** | Channel workers (cli/telegram/webchat) — user-facing input channels. |
| 24 | `plugins` | 0/0 | STANDALONE-SURFACE | **DELETE** | PluginHost (daemon loads plugins per channel). ohmypi is the extension host now; the retained mind is a *package*, not a plugin host. |
| 25 | `jobs` | 0/0 | STANDALONE-SURFACE | **DELEGATE** | JobManager backs `run_background`/`check_job`/`wait_job` (daemon-gated). Those are coding tools → ohmypi `task`/`hub` background jobs. Delete after. |
| 26 | `host` | 2/17 | STANDALONE-SURFACE | **PORT → replaced by the focused runtime + spine** | The 68,949-line daemon composition root reduces to a **thin mind host** exposing the mind's own surface to the spine (mind tools, memory adapter, internal channel) — NOT the boot/supervisor/CLI/ACP-bridge/session-wiring. The retained slice is the composition that builds `MnemicField` + injections. |
| 27 | `admin-api` | 5/9 | STANDALONE-SURFACE | **DELETE (retain mind-health read slice as PORT)** | 54 HTTP route modules / 17,554 lines. `/sessions`, `/chat`, `/models`, `/providers`, `/tools` → ohmypi owns. Mind-health/debug read routes (`cortex/pineal/thalamus/memory/replay/observability`) → fold into the mind runtime's narrow internal health surface. |
| 28 | `mcp-gateway` | 1/40 | STANDALONE-SURFACE | **PORT → spine** | The 43-file/17,004-line MCP **server** dies as a standalone process. Its retained essence is the *consolidated mind-tool schemas* (helix's `getCodeConsolidatedToolSchema`, etc.) which the spine re-exposes via `pi.registerTool`. The server itself → gone. |
| 29 | `mcp` | 0/0 | STANDALONE-SURFACE (borderline) | **PORT → DELEGATE** | MCP **client** to external servers. ohmypi has native MCP client (`.mcp.json`, `mcp__<server>_<tool>` tools, `mcp_notification` events). Mind-side external-MCP access (gitnexus/serena) → ohmypi's MCP. Drop the package; keep any retained type the mind imports via the spine. |
| 30 | `providers` | 5/120 | STANDALONE/delegate | **DELETE (DELEGATE)** | 7,250-line provider SDK layer. No mind package imports it (recon §2.1). ohmypi owns providers; `CostClassifier` (consumed by model-pool `billing-models.ts`) is dropped with model-pool's budget/billing slice. 120 tests die with the package after the model-pool port. |
| 31 | `ai` | 1/36 | STANDALONE/delegate | **DELETE (DELEGATE)** | 26,981-line pi-ai fork + 338KB model registry + OAuth. Strongest delegate (recon §1.1). No mind import. |
| 32 | `cassi-tui` | 0/0 | STANDALONE app | **[ASK-6] DELETE or demote** | Ink/React TUI — ohmypi has its own TUI. Default: DELETE (standalone demo surface). |
| 33 | `cassi-watch` | 0/0 | STANDALONE app | **[ASK-6] DELETE or demote** | Field-visualization watch app. Could stay as a standalone demo reading the field. |
| 34 | `prism` | 0/0 | STANDALONE app | **[ASK-6] DELETE or demote** | Three.js field visualizer. Could stay as a standalone demo. |
| 35 | `webui` | 0/0 | STANDALONE app | **[ASK-6] DELETE** | Next.js portal + observatory — talks to the dead daemon HTTP surface. Default DELETE (or re-point to mind runtime health if kept). |
| 36 | `claude-code-mcp` | 0/0 | BRIDGE | **DELETE** | External-facing bridge to claude-code CLI. Its role is absorbed by ohmypi's native provider/ecosystem. Recon §4.4/§5: external re-pointing needs owner confirmation — [ASK-6] adjacent. |
| 37 | `hermes-agent-gateway` | 0/0 | BRIDGE | **DELETE (or retain as standalone)** | Hermes ACP bridge — `tools`' `hermes-tools.ts`/`hermes-mcp-client.ts` accompany it. ohmypi has its own ACP/ecosystem. Default DELETE. |
| 38 | `opencode` | 0/0 | BRIDGE | **DELETE** | Bare opencode plugin file. ohmypi ecosystem absorbs. |

### Verdict counts

| Verdict | Count | Packages |
|---|---|---|
| **KEEP** | 18 | 14 mind (1–14) + substrate `foundation`, `events`, `utils` (15–17) + `workflow` (18) |
| **PORT** | 3 | `model-pool` (19), `host`→focused runtime+spine (26), `mcp-gateway` server→ retained consolidated schemas / spine (28) |
| **SPLIT** | 1 | `tools` (20) — mind slice PORT, coding slice DELEGATE |
| **DELEGATE** | 3 | `pipeline` (21), `jobs` (25), `mcp` (29) |
| **DELETE** | 13 | `commands` (22), `workers` (23), `plugins` (24), `admin-api` surface (27, retained mind-health read slice folded into the mind host), `providers` (30), `ai` (31), `cassi-tui` (32), `cassi-watch` (33, [ASK-6]), `prism` (34, [ASK-6]), `webui` (35), bridges `claude-code-mcp`/`hermes-agent-gateway`/`opencode` (36–38) |

Sum = **18 KEEP + 3 PORT + 1 SPLIT + 3 DELEGATE + 13 DELETE = 38.** The focused mind = the 18 KEEP + the retained PORT/SPLIT surfaces (model-pool `ModelHandle` shim, tools mind-slice, thin mind-host/spine, admin mind-health read slice, mcp-gateway consolidated schemas) = **~24 logical packages or slices survive**; everything else is a clean, history-preserving deletion.

### Foundation/events/utils/workflow/jobs/plugins/workers/mcp — explicit reasoning

- **`foundation` / `events` / `utils` / `workflow`:** KEEP (22 of 26 are mind or substrate). Explicit: `foundation` carries `IProvider`/`IModelDirective`/paths — the retained type seam. `events` is the EventBus/Logger every retained package imports (recon Part 1: "everything"). `utils` is transitive dependency (TTLCache etc.). `workflow` is borderline (recon Part 3 marks it borderline) but constellation uses it heavily → PORT (drop daemon-gated `run_background` integration).
- **`jobs` / `plugins` / `workers` / `commands`:** standalone-surface infra. `jobs` → DELEGATE (background jobs = ohmypi `task`/`hub`). `plugins` → DELETE (ohmypi is the extension host; a retained PluginHost is redundant). `workers` → DELETE (ohmypi owns input channels/TUI). `commands` → DELETE (ohmypi owns slash-commands; retained mind tools register via spine, not a CommandDispatcher).
- **`mcp`:** the recon marked it "STANDALONE-SURFACE (borderline)" only because the mind's helix touches external MCP. ohmypi's native MCP client (recon §4.4) supersedes the retained `MCPClient` → DELEGATE, with any retained type re-pointed at the spine.

---

## 6. Migration phasing (5–7 phases, history-preserved)

Constraint from `MIGRATION-STATUS`: "the workspace git already carries everything — deletions are clean commits." No D: edits, no re-running filter-repo. **The `+87` daemon lines and `overhaul` session are untouched** (D: out of scope; `MIGRATION-STATUS §3.3`).

| Phase | Move | Test impact |
|---|---|---|
| **P1 — resolve `host ↔ tools\|mcp` cycle first** | `MIGRATION-STATUS §3.2` demands this before slimming. Re-point host-vendor stubs & delete them, keeping `ModelHandle` + `ToolExecutor`/`ToolRegistry` types + mind-tool handlers as the port surface. | All mind suites still green (no behavior change). |
| **P2 — split `model-pool` + `tools`** | Reduce `model-pool` to the `ModelHandle` cast (+ an ohmypi-backed completion shim). Split `tools`: retain mind-tool handlers + `ToolExecutor`/`Registry`/`Definition` types + `InteractiveToolSession`; quarantine coding-tool files. | `model-pool` 32→~8, `tools` 39 (mind) retained. Moved/deleted suites + tests cleaned. |
| **P3 — the spine + focused runtime, in parallel** | **DONE (2026-08-14).** Built `@cassicore/mind-runtime` (host-agnostic always-on process: MnemicField + retained intelligence composition, 127.0.0.1:7273 channel, memory backend) + `@cassicore/spine` (ohmypi extension: 13 retained/mind tool delegates, `mind_complete`, lifecycle mirror + appendEntry snapshots, mnemonic backend adapter, `[SPINE-TYPES]` shim). Retained-mind seam `registerMindTools` split from `registerCoreTools` (unchanged). | New spine/runtime suites green (22 mind-runtime + 16 spine contract tests); mind suites untouched. |
| **P4 — model-access cutover** | **DONE (2026-08-14).** Slimmed `@cassicore/model-pool` to the retained `ModelHandle` shim + a `mind_complete`-backed acquirer (`createMindCompleteAcquirer`; pool/fallback/budget/billing machinery deleted). Host replaced its provider pool with the acquirer (transitional — completions ride the shim, 'not wired' until P5/P6). Deleted `@cassicore/providers` + `@cassicore/ai`; zero importers remain. | `providers` 120 + `ai` 36 died with deletion; `model-pool` 32 → 10 retained-handle tests. Mind suites (helix 75, constellation 568, mini-helix 21, host 17) green + retained model-pool. |
| **P5 — sessions cutover + memory backend** | ohmypi takes over user sessions; spine mirrors session lifecycle; `ctx.memory` → mnemic backend. Delete `pipeline`/`commands`/`workers`/`plugins`/`jobs`/`mcp`; retire mcp-gateway server, admin-api surface, host daemon surface (retain read-slice). Delete the now-redundant `_reflect`/`_remember`/`remember`/`memory_search` mind tools. | Mind suites: +mnemic-on-memory-backend tests; recall/retain/reflect merge cases moved to harness-level memory suite. Surface-package suites removed. |
| **P6 — bridges + standalone apps** | **DONE (owner-ratified 2026-08-14).** Deleted `claude-code`, `hermes-agent`, `opencode` (role absorbed by ohmypi ecosystem) + `webui` + `cassi-tui`/`cassi-watch`/`prism` (all four UI apps per owner decision). | passWithNoTests packages — no test loss. |
| **P7 — verification + docs** | Zero-import guard: assert no retained mind package imports `@cassicore/providers`/`@cassicore/ai`/`admin-api`/`mcp-gateway`. Update `MIGRATION-STATUS`/`CASSI-MIND-PLAN` to the focused shape. Sweep `recon-*` headers. | Full retained-suite run; the "focus gate" (no standalone imports) is the deliverable's acceptance test. |

**Which suites move vs die:** mind/type suites (helix 75, constellation 568, aurora 698, mnemic 89, + others) **survive** into the focused runtime. Surface suites die with their packages: `providers` 120, `ai` 36, `admin-api` 9, `mcp-gateway` 40, `tools` coding-slice tests. `model-pool` 32 → slimmed. The host 17 (bridge-acp/acp-roundtrip) die unless the mind host retains an ACP bridge — [ASK-6]-adjacent (default: drop, ohmypi owns bridges).

---

## 7. Owner ratification (2026-08-14) — all ASK items resolved

> **RATIFIED (owner).** "Remove all the UI apps and external bridges. Other than that, defaults." Recorded decisions:

1. **Model-access choice — RATIFIED (default).** Mind sub-agents run as **ohmypi task agents** (primary) + a **`mind_complete` bridge tool** (fallback for corpus/brainstem pure completions). Rejected (c): keeping a CassiCore provider seam.
2. **Always-on mind process — RATIFIED (keep).** Keep the mind as its own always-on process (focused runtime, §4.1 process 2). Not fully event-driven.
3. **MnemicField-as-memory-backend — RATIFIED (yes).** Wire `memory.backend` to a mnemic-field adapter so `ctx.memory` (recall/retain/reflect/memory_edit) operates on the Cassi field.
4. **Fate of the standalone operator apps — RATIFIED (DELETE ALL FOUR).** `webui`, `cassi-tui`, `cassi-watch`, `prism` all deleted (owner: "Remove all the UI apps"). No retained standalone demo; retained mind host keeps no ACP/HTTP bridge for them.
5. **Mind-tool redundancy boundary — RATIFIED (default).** Delete `_reflect`/`_remember`/`remember`/`memory_search` (merge into ohmypi memory built-ins over the shared field); keep `collect_thoughts` + `graph_discover` as cognitive operations.
6. **External-bridge fate — RATIFIED (DELETE ALL THREE).** `claude-code` (`@cassicore/claude-code-mcp`), `hermes-agent` (`@cassicore/hermes-agent-gateway`), `opencode` all deleted — role absorbed by ohmypi's native provider/ACP/ecosystem surface.

**P6 executed 2026-08-14 (this file committed with the deletions):** all four UI apps + all three bridges removed from `packages/` (history-preserved in git).

---

<!-- End of CASSICORE-FOCUS-PLAN. Read-only design deliverable; no migrations executed. -->
