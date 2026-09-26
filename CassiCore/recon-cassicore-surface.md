# CassiCore Standalone Surface Recon — slim-down fact-pack

**Purpose.** Feed the decision to slim CassiCore so that ohmypi owns PROVIDERS, AGENT SESSIONS, and TOOLS, leaving CassiCore as a focused cognitive mind. Part 1 inventories what CassiCore currently owns in those three domains; Part 2 extracts the minimal interface the mind modules actually need (the seam surface); Part 3 classifies the whole standalone surface (MIND vs STANDALONE-SURFACE vs BRIDGE) and ends with the deletion/delegation/keep recommendation. Read-only — no repo was modified.

All paths relative to `C:\Users\Carina\workspaces\Cassi\CassiCore\packages` unless noted. Sizes = source `.ts` files/lines (vendor stubs included). Test counts from `MIGRATION-STATUS.md §2` (all green).

---

## Part 1 — Current ownership inventory

### 1.1 PROVIDERS domain (`providers`, `ai`, `model-pool`)

#### `@cassicore/providers` — 18 src files, 7,250 lines; 6 test files, 2,326 lines (120 tests)

Owes: **model-provider SDK clients** + routing/budget/rate-limit orchestration. Exposed surface (from `src/index.ts`):

| Export | One-line purpose |
|---|---|
| `createProviders(config, logger, {centralized, bus})` | Build the provider `Map` from config/env: github-copilot (HTTP), copilot-sdk, kimi-coding, alibaba-coding, opencode-go, google-antigravity, qwen (load-balanced), openrouter, z-ai, deepseek, claude-code (spawn). Wraps all in `CentralizedProvider` when `centralized` (dedup, rate limit, metrics, error-cooldown). |
| `CentralizedProvider` / `wrapProvidersWithCentralized` | Centralized request tracking, rate limiting, dedup per session, event emission. |
| `ModelRouter` / `getModelRouter` / `createModelRouter` | Budget-aware provider/model routing (purpose → model). |
| `BudgetTracker` / `getBudgetTracker` / `createBudgetTracker` / `DEFAULT_PROVIDER_BUDGETS` | Provider budget tracking; `wire(bus)` + `loadFromDisk()`. |
| `CostClassifier` / `getCostClassifier` / `DEFAULT_COST_RULES` (also `RequestCost`, `CostRule`) | Canonical cost classifier. |
| `ClaudeCodeProvider` | Spawns the claude-code CLI as a provider. |
| `GitHubCopilotProvider`, `GitHubCopilotLoadBalancer` | Copilot HTTP provider + multi-account round-robin LB. |
| `GoogleAntigravityProvider` | Antigravity HTTP provider. |
| `QwenLoadBalancer` / `createQwenLoadBalancer` / `QwenAccount` | Qwen multi-account load balancer (reads `~/.cassicore/qwen-accounts.json`). |
| `RateLimitStore` | SQLite (`better-sqlite3`) adaptive learned-rate-limit persistence. |
| `initCopilotSdkProvider(...)` | Async boot of the `@github/copilot-sdk` CLI-bridged provider; `bridgeToolsToSdk` binds the tool registry into the SDK. |
| `copilot-sdk/` (5 files) | `client-manager`, `provider`, `warm-provider-manager`, `event-mapper`, `finished-tool`, `tool-bridge` — the github-copilot-sdk integration. |
| `listProviderConfigKeys` | For admin-api provider routes. |
| `CopilotSdkProvider`, `WarmProviderManager` | Re-exported for admin-api warm-provider route. |
| `base.ts` | `BaseProvider` abstract. |
| `model-router.ts`, `budget-tracker.ts`, `cost-classifier.ts`, `centralized.ts`, `rate-limit-store.ts` | The orchestration layer. |

Additional SDK-client sources: `claude-code.ts`, `github-copilot.ts`, `github-copilot-loadbalancer.ts`, `google-antigravity.ts`, `qwen-loadbalancer.ts`, `copilot-sdk/*`. **Uses `better-sqlite3` for the rate-limit store** and wraps `@github/copilot-sdk`. Qwen OAuth comes from `@cassicore/ai` (`QwenProvider`, `QwenOAuthCredentials`).

**Consumers** (grep `@cassicore/providers` outside `providers/`): only 3 non-test surfaces:
- `host/src/daemon.ts` — `createBudgetTracker`, `createModelRouter` (imports at top), `createProviders` (dynamic), `RateLimitStore` (dynamic), `BudgetTracker`/`ModelRouter` types.
- `admin-api/src/routes/providers.ts` — `listProviderConfigKeys`; `admin-api/src/routes/warm-provider.ts` — `CopilotSdkProvider` (type) + `WarmProviderManager`.
- `model-pool/src/billing-models.ts` — `CostClassifier`, `RequestCost`.

**No mind package imports `@cassicore/providers` directly.** The mind never touches providers; the daemon boots providers and hands the *handles* to the mind.

#### `@cassicore/ai` — 51 src files, 26,981 lines; 1 test file, 385 lines (36 tests)

Forked from **pi-ai**. Owes: the unified SDK/provider layer. Direct exports: `createProviders` (its own), `MODELS`/`models.generated.ts` (338 KB registry), provider classes (`QwenProvider`, `KimiCodingProvider`, `AlibabaCodingProvider`, `DeepSeekProvider`, `OpenCodeGoProvider`, `OpenRouterProvider`, `ZaiProvider` under `providers/cassicore/`), OAuth utilities (`utils/oauth/*` — anthropic, github-copilot, google-antigravity, google-gemini-cli, openai-codex, pkce), plus generic pi-ai providers (anthropic, openai-completions, google, etc.).

**Consumers** (src only): `@cassicore/providers` (re-exports the CassiCore provider classes + `QwenProvider`/`QwenOAuthCredentials` into its barrel; `qwen-loadbalancer.ts` imports `QwenProvider`), and `@cassicore/model-pool/src/model-capabilities.ts` (reads `MODELS` registry for token/capability detection). **No mind package imports `@cassicore/ai`** — it is a pure provider-layer dependency, previously P8-deferred (vendored type stubs remain in host/admin-api until re-pointed). This is the strongest delegate candidate.

#### `@cassicore/model-pool` — 8 src files, 3,045 lines; 1 test file, 540 lines (32 tests)

Owes the **model acquisition layer**: `ModelPool` (acquire/release, fallback chains, budget scopes), `ModelHandle`/`ModelHandleImpl`, `FallbackManager`, `BudgetManager`, `CapabilityCache`, `ModelCapabilitiesFetcher`, `BillingModel`, `ModelCapabilities`/`BudgetScope`/`BudgetLimits`/`PoolEvent` types. Pulls **no** provider SDKs — only foundation types, `@cassicore/utils` (TTLCache, CircuitBreaker), `@cassicore/providers` (`CostClassifier`), and `@cassicore/ai` (model registry).

**Consumers** (mind-heavy — this is the real seam):
- `helix` — `ModelPool` (type), `ModelHandle` (type), `ModelCompletionOpts` (type), via `@cassicore/model-pool` and `/types`.
- `constellation` — `ModelPool` (type), `ModelHandle`/`ModelCompletionOpts` (type) from `/types`; acquires via `modelPool.acquire(...)` in a handleFactory.
- `mini-helix` — `ModelHandle`, `ModelCompletionOpts` (type) from `/types`.
- `host/src/daemon.ts` — instantiates the Helix/Constellation `ModelPool` (`new ModelPool({...})`), `setProviders(providers)`, acquires corpus/brainstem handles.
- `foundation/src/vendor/core/model-pool/types.ts` — vendored type stub (re-pointed to `@cassicore/model-pool` at P6, the runtime `ModelPool` module type lives here).

### 1.2 AGENT-SESSIONS domain (`pipeline`, `admin-api`, `host`)

There are **two session systems**, plus mind-internal per-package session state.

#### (a) `@cassicore/pipeline` — 19 src files, 5,124 lines; 2 tests

The newer, package-ized session pipeline. Exposed: `SessionManager`, `SQLiteSessionStore`/`MemorySessionStore`, `createSessionManager`, `SessionPipeline`/`createSessionPipeline`, `TurnHandler`, `ContextWindow`, `MessageBuilder`, `ToolLoop`, `IntelligenceLayer`/`BackgroundProcessor`, plus the session/turn types (`SessionState`, `TurnRequest`, `TurnResult`, etc.). Session persistence is **SQLite via `better-sqlite3`** at `~/.cassicore/system-state.db` (`SQLiteStore.createDefaultSQLiteStore`/`SessionPipeline.initialize`).

`SessionPipeline` (**user-facing chat session infra**, not mind-internal): 
- `processMessage(channelId, senderId, content)` — get-or-create session by channel+sender.
- `processTurn(sessionId, content, opts)` — get-or-create **by a stable sessionId**; the header comment names "HeartModule, ThinkerModule, subagent spawning, and the CassiCoreExecutionBackend" as the callers that pass a stable session ID.
- `requestCancel`, `getSessionManager`, `getIntelligenceLayer`, `getTurnHandler`, `setGlobalWorkspace` (GWT), `injectOnNextTurn`.

**Consumers of `@cassicore/pipeline`:** `host/src/daemon.ts` (instantiates `SessionPipeline` at line 2598 for the admin-api `/sessions`+`/chat` routes and the autonomous-loop backend), `host/src/vendor/core/{session-manager,turn-pipeline}.ts`, `thalamus/src/{classifier,compressor,distiller,drop-receipt,index,scorer,slots/*}.ts` (imports the *tool/pipeline types* for slot classification: `isWriteTool`/`isReadTool`/`isShellTool`/`shortenPath`), `admin-api/src/routes/sessions.ts` (uses the SessionPipeline session id resolver).

#### (b) host's vendored session machinery (the ACTIVE daemon system)

`host/src/vendor/core/`: `session-manager.ts` (660 lines), `session-store.ts` (411 — SQLite `~/.cassicore/data/sessions.db`), `session-bridge.ts` (392), `turn-pipeline.ts` (1,411). The daemon uses these as `this.sessions`/`this.pipeline` for the legacy primary session router + CLI/telegram channels. `SessionStore.open(logger)` opens the SQLite DB; `createSessionManager(logger, systemPrompt, sessionStore, defaultModel, thinking)` (daemon line 1838); the daemon also wires a MnemicField replay bridge over `SessionStore` (line 1563) and a `SessionDigestStore`.

#### (c) admin-api session routes

From `admin-api/src/routes/` (54 route modules, 17,554 lines):
- **`sessions.ts`** (33.5 KB) — `/sessions/:id/turn` (non-streaming + SSE), session list/get, delete, etc.; dispatches into the `SessionPipeline` when `runtime.preferredTurnEngine() === 'session-pipeline'`, else the vendored TurnPipeline.
- **`helix-sessions.ts`** — `/helix-sessions` — Helix session journal/store (`getSharedHelixJournal`, `getSharedHelixSessionStore`).
- **`turn-routing.ts`** — session-pipeline session-id resolution for `/sessions`.
- **`chat.ts`** — `/chat/:sessionId/stream`, `/chat/:sessionId`.
- **`replay.ts`** — `/replay/session/:id`, `/replay/run/:id`, `/session-summary/:id`, `/legacy-sessions[..]` (MnemicField event replay).

#### (d) mind-internal session state (stays)

- **helix** — Helix session store/journal (per-helix state, blackboards), `helix-store.ts`.
- **constellation** — `constellation-store.ts` + `ConstellationStore` (its own session model).
- **mini-helix** — mini-helix session/turns inside `mini-helix-runner`.
- All coordinate via `module-session-registry` (a shared registry pattern vendored into several mind packages).

**Classification:** the daemon TurnPipeline + the SessionPipeline (`/sessions`, `/chat`, autonomous-loop backend) are **user-facing session infra** — delegate candidates (ohmypi owns agent sessions). Helix/constellation/mini-helix session stores are **mind-internal** — stay.

### 1.3 TOOLS domain (`tools`, `mcp`, `mcp-gateway`, `commands`)

#### `@cassicore/tools` — 73 src files (35 impl), 17,200 lines; 9 test files, 3,366 lines (39 tests)

Owes: `ToolRegistry`, `ToolExecutor`, the tool type system (`ToolDefinition`, `ToolHandler`, `ToolExecutionContext`, `ToolCategory`, `ToolCall`/`ToolResult`), safety/reliability wrappers (`createSafeToolExecutor`, `ToolReliabilityTracker`, `validateToolInput`), presentation, `Scout`, `InteractiveToolSession`, `ExternalHookRunner`, `HermesMcpClient`/`HermesTools`, and `registerCoreTools(registry, deps)` registering the core toolset.

**Tool implementations (`src/implementations/`) with purpose + CODING vs MIND:**

| File | Tool(s) | Type |
|---|---|---|
| `shell-exec.ts` | `shell_exec` | CODING (shell) |
| `cassi-shell.ts` | `cassi_shell` | CODING (unified shell) |
| `read-file.ts` / `read-files.ts` | `read_file`, `read_files` | CODING (file) |
| `write-file.ts` | `write_file` | CODING (file) |
| `web-fetch.ts` / `web-search.ts` | `web_fetch`, `web_search` | CODING (network) |
| `todo-write.ts` | `todo_write` | CODING (task tracking) |
| `run-tests.ts` | `run_tests` | CODING (vitest) |
| `desktop-vision.ts` | `desktop_vision` | CODING (KDE window capture) |
| `vybit.ts` + `vybit-loop.ts` + `vybit-bug-ingest.ts` | `vybit*` | CODING (visual browser editing) |
| `run-background.ts` / `check-job.ts` / `wait-job.ts` | `run_background`, `check_job`, `wait_job` | CODING/infra (jobs) |
| `workflow.ts` | `workflow` | CODING/infra (workflow engine) |
| `collect-thoughts.ts` | `collect_thoughts` | **MIND** (structured thinking → ThoughtObserver/CognitiveBridge/memory; branching+revision) |
| `graph-discover.ts` | `graph_discover` | **MIND** (neural-graph discovery over mnemic-field/constellation) |
| `cognitive-tools.ts` | `_reflect`, `_remember` | **MIND** (free-tool-loop cognitive signal routing) |
| `peer-coordination.ts` | `_coordinate`, `_check_peers` | **MIND** (cross-session signal/broadcast/shared-note/link-brain) |
| `memory-search.ts` | `remember` | **MIND** (memory search) |
| `query-events.ts` | `query_events` | MIND/events |
| `cassandra-event.ts` | `cassandra_query_events` | MIND/events (state|history) |
| `list-tools.ts` | `list_tools` | MIND/meta (progressive discovery) |
| `list-subagents.ts`/`get-subagent-status.ts`/`get-subagent-result.ts` | `list_subagents`, `get_subagent_status`, `get_subagent_result` | MIND (subagent inspection via Thinker) |
| `spawn-subagent.ts`/`spawn-subagent-impl.ts` | spawn fn (disabled for direct use — routed through Thinker) | MIND |
| `system-health.ts` | `system_health` | MIND/ops |
| `debug-session.ts` | `debug_session` | MIND/ops |
| `universal-search.ts` | `universal_search` | MIND/ops |
| `context-window-tools.ts` | `cassandra_context_inspect` | MIND/ops |
| `index.ts` | `registerCoreTools` + inline `list_sessions` | — |

**Coding tools (ohmypi already owns these: bash/file/edit):** `shell_exec`, `cassi_shell`, `read_file`, `read_files`, `write_file`, `web_fetch`, `web_search`, `todo_write`, `run_tests`, `desktop_vision`, `vybit`. **Mind-specific:** `collect_thoughts`, `graph_discover`, `_reflect`, `_remember`, `_coordinate`, `_check_peers`, `remember`, `list_sessions`, `list_subagents`, `get_subagent_status`, `get_subagent_result`, `system_health`, `debug_session`, `universal_search`, `cassandra_query_events`, `cassandra_context_inspect`.

**Mind consumers:** `helix`, `constellation`, `cognitive-feed`, `mini-helix` import `@cassicore/tools` (almost entirely **types**: `ToolExecutor`/`ToolRegistry` as injected deps; `cognitive-feed` imports runtime `InteractiveToolSession` + type `ToolDefinition`). See Part 2. Note `helm`/`constellation` never construct a registry/executor — the daemon does and injects via `setToolExecutor`.

#### `@cassicore/mcp` — 5 src files, 433 lines; 0 tests

Owes the **MCP client**: `MCPClient`, `MCPRegistry`, `MCPServerConfig`/`MCPServerStatus`/`MCPConnectionState`/`MCPToolInfo`. Used to connect to *external* MCP servers (gitnexus, serena, duckduckgo). Consumers: `host/src/daemon.ts` (daemon's `mcpRegistry`/health), plus `tools`/`helix` `vendor/core/mcp` stubs re-pointed to it.

#### `@cassicore/mcp-gateway` — 43 src files, 17,004 lines; 2 test files, 594 lines (40 tests; "42-file MCP SERVER" per migration)

Owes the **MCP SERVER** that exposes CassiCore's tools/capabilities. It is a **separate process talking to the daemon over HTTP** (`CASSICORE_URL = http://localhost:7433`, `cassicore-gateway.ts`), supports stdio + HTTP/SSE, **spawns the daemon as a child if not running**, and forwards calls to the daemon's `/tools/execute` endpoint and `cassicore://…` resources. Also contains `scip-server`, `gitnexus-server`, `serena-server`. Consumers: `admin-api/src/routes/tools.ts` (imports `CORE_TOOLS`, `SESSION_TOOLS`, `MEMORY_TOOLS`, `CONFIG_ADMIN_TOOLS`, `FLUX_TOOLS`, `DIALECTIC_TOOLS`, `INTELLIGENCE_TOOLS`, `HELIX_TOOLS`, `MODEL_DIRECTIVE_TOOLS`, `DO_TOOLS`, `ENRICH_TOOLS`, `TRAINING_TOOLS` — for the tools catalog), `helix/src/helix-posture-runner.ts` (imports `getCodeConsolidatedToolSchema`, `WEB_CONsolidated_TOOL`, `BROWSER_CONSOLIDATED_TOOL`, `execute*ConsolidatedTool`).

**Public MCP surface (what an external client gets today):**
- Core: `bash`, `read`, `write`, `edit`, `mkdir`, `delete`, `exists`, `web_fetch`, `web_search`, `todo_write`, `vybit`, `skill_intelligence`, `workflow`.
- Meta: `do` (meta-wrapper + context enrichment), `enrich`, `enrich_feedback`.
- Consolidated domain tools: `agent`, `memory`, `session`, `intelligence`, `artifact`, `code`, `file`, `browser`, `web`, `config`, `model`, `training`, `cortex`, `self_model`, `context` (plus `context_repo`, `lamina`, `annotation`, `knowledge`).
- Domain/legacy tools: `sessions`, `session_detail`, `session_prune`, `session_conversation`, `session_export`, `resolve_ref`, `index_search`, `index_session`, `index_stats`; `memory_store`, `memory_search`, `memory_recent`, `memory_delete`, `memory_kv_*`, `memory_stats`, `archive_*`, `browse`, `universal_search`, `memory_retrieve`; `config_get`, `config_set`, `providers`, `provider_metrics`, `provider_config`; `flux_team`, `flux_run`, `flux_inspect`, `flux_watch`; `dialectic`; `activity`, `thinker`, `subconscious`, `consciousness`, `trace`, `effectiveness`, `budget`, `evolution`, `blindspots`, `snapshot`, `trust`, `consequences`; `helix_project`, `helix_status`, `helix_health`, `helix_jobs`, `helix_watch`, `helix_cancel`, `helix_sessions`, `helix_progress`, `helix_blackboard`; `model_directive`; `training_stats`, `training_search`, `training_objects`, `training_resolve`, `training_labels`, `training_quality`, `training_annotations`, `training_ingest`, `training_tag`, `training_export`.
- Resource URIs: `cassicore://health`, `//config`, `//intelligence/activity`, `//teams/:id/status`, `//sessions/:id/{context,turns}`, `//memory/search`.

#### `@cassicore/commands` — 13 src files, 3,333 lines; 0 tests

Owes `CommandDispatcher` — **slash-command interception for Telegram/Chat/TUI/API/Web/CLI** channels ("Intercepts /commands before they reach the LLM pipeline"). Command modules: `cassi-commands`, `cassicore-commands`, `git-commands`, `qwen-commands`, `team-commands`, `tool-commands`, `universal-processor`. Consumers: `host/src/daemon.ts` (`new CommandDispatcher(logger, sessions, bus)`), `admin-api/src/routes/sessions.ts`. This is **channel/CLI user-facing infra**, not mind.

#### Host ↔ tools/mcp dependency cycle (MIGRATION-STATUS §3.2)

Quoted: *"Host-vendor stub re-points … `tools' vendor/core {session-store,turn-pipeline,tool-proxy-middleware,workspace-loader,resource-limits}` + `mcp/tools vendor/core/version` → `@cassicore/host` … **Deferred:** these re-points introduce a `host ↔ tools|mcp` dependency **cycle** (host already depends on tools/mcp); resolve the cycle first (P8 or a dedicated dep-cleaning pass), then re-point and delete the stubs."* — the host and tools/mcp are tangled; the daemon's tool executor is built from `@cassicore/tools` and injected into the mind, while tools vendor host-side seams.

### 1.4 host/src/daemon.ts wiring of all three domains (quoted)

- **Providers:** `createProviders(this.config, this.logger, { centralized: true, bus: this.bus })` (line 1143); `createBudgetTracker(this.logger, ...)` + `.wire(this.bus)` + `.loadFromDisk()` (1129); `createModelRouter(this.logger, budgetTracker)` (1134); `RateLimitStore.open(this.logger, dataDir)` (1181); `listProviderConfigKeys` (1408+); `new ModelDirective({..., getProviderModels})` (1203).
- **ModelPool (sessions of models):** `new ModelPool({ logger, eventBus, fallbackChains: [...], budgetScopes: [], blockedProviders, allowedModels })` (1443); `helixModelPool.setProviders(providers)` (1470); `helixModelPool.acquire('unity', config.tier, config.sessionId)` used as the meditation/corpus handleFactory (1493, 2317, 2333, 2480).
- **Sessions:** `createSessionManager(this.logger, systemPrompt, sessionStore, defaultModel, configuredThinking)` (1838); `SessionStore.open(this.logger)` (1563); `new SessionPipeline(v2Options)` + `initialize()` (2598); `new TurnPipeline(providers, this.sessions, this.bus, this.logger, memory, orchestration, toolRegistry, toolExecutor)` (2355); `createSessionBridge(this.orchestration, ...)` (261).
- **Tools:** `registerCoreTools(toolRegistry, { memory, sessionManager, sessionStore, bus, logger, getPipeline, subagentTracker, cognitiveToolDeps, peerToolDeps, collectThoughtsDeps, getWorkflowEngine, ... })` (1889); `registerHermesTools(toolRegistry)` (1971); `new ToolExecutor(toolRegistry, { workingDir, allowedPaths, networkAllowlist, logger, _codeStore, _cortex, _memory }, this.bus)` (1987); `toolExecutor.setPermissionOracle(...)` (2002), `.setTrustLedger(...)` (2008), `.setReliabilityTracker(...)` (2013), `.setExternalHooks(...)` (2020).
- **Mind injection:** `intelligence.helix.setModelPool(helixModelPool)` (1474), `.setToolRegistry(toolRegistry)` (2147), `.setToolExecutor(toolExecutor)` (2148); same for `intelligence.constellation` (1482, 2185-2186); `intelligence.meditation.setToolRegistry/Executor` (2269-2270); `setCorpusLLMProvider(await helixModelPool.acquire('unity', undefined, 'corpus-llm', opusCfg))` (2314-2317); `setBrainstemLLMProvider(... acquire('mini-helix:brainstem', ... 'brainstem-llm', glmCfg))` (2330-2333); `bootIntelligencePostPipeline({ ..., handleFactory: helixModelPool ?, toolRegistry, toolExecutor, sessionPipeline, ... })` (2459+).
- **MCP/admin/commands:** `createAdminApi(daemon, logger).start()` (import); `new CommandDispatcher(logger, sessions, bus)` (1844); daemon's `mcpRegistry` drives admin `/mcp`.

---

## Part 2 — What the mind actually needs (the seam surface)

The mind modules (mnemic-field, helix, constellation, aurora, thalamus, flux-team, dreamer, cognitive-feed, cpd, mini-helix, workspace, embeddings, training-trust-ledger) do **not** import providers, ai, or commands. Their real interface surface is a narrow slice of `model-pool` (ModelHandle) + `tools` (executor/registry types) + injected wiring by the daemon. The tables below quote 2–3 representative call sites per consumer.

### 2.1 Providers interface (mind-needs)

**No mind package imports `@cassicore/providers` or `@cassicore/ai`.** The seam is *indirect*: the daemon boots providers, wraps them into a `ModelPool`, and hands the resulting `ModelHandle`/pool to the mind. The mind's only "provider" contract is the foundation-level `IProvider` type and the `ModelHandle` surface from `model-pool`.

| Consumer | Symbols used | Purpose |
|---|---|---|
| (indirect) `host/daemon.ts` | `createProviders`, `ModelPool`, `ModelHandle` | Boots providers, sets pool, acquires corpus/brainstem/meditation handles, injects into mind. |
| foundation `IProvider` | `complete(messages, opts)`, `ping()`, `models` | The provider interface contract the mind's `ModelHandleImpl` satisfies. Owned by `@cassicore/foundation`, **not** providers. |

### 2.2 Sessions interface (mind-needs)

The mind touches only **conceptual session IDs and per-session injection stores** — it does NOT own the persistence or the chat-loop orchestration.

| Consumer | Symbols used | Purpose |
|---|---|---|
| `pipeline/SessionPipeline` (via daemon) | `processTurn(sessionId, ...)`, `requestCancel`, `getContextInjection(sessionId)` | Uses a stable `sessionId` passed down; mind modules (Heart/Thinker/subagent, CassiCoreExecutionBackend) call `processTurn` with a fixed ID. |
| `helix`/`constellation`/`mini-helix` | own `HelixStore`/`ConstellationStore`, `module-session-registry` | Mind-internal session/journal state, keyed by their own session IDs — stays. |
| `thalamus.classifier` / `pipeline types` | `isWriteTool`, `isReadTool`, `isShellTool`, `shortenPath` | Classifies whether a tool result is a write/read/shell for slot handling. Types imported from pipeline, used in mind. |
| `admin-api /sessions`, `/chat` | session id resolution -> SessionPipeline | **User-facing** session HTTP surface (delegate). |

**Bottom line:** mind needs = "a unique opaque `sessionId` string that flows through turn processing, plus mind-owned per-session stores". It does not need SQLite session tables or session lifecycle management.

### 2.3 Tools interface (mind-needs)

| Consumer | Symbols used | Purpose |
|---|---|---|
| `helix/src/helix-posture-runner.ts` | `type ToolExecutor`, `type ToolRegistry`; `this.toolExecutor!.execute(toolCall, this.sessionId)`; `getCodeConsolidatedToolSchema`, `WEB_CONSOLIDATED_TOOL`, `BROWSER_CONSOLIDATED_TOOL`, `execute*ConsolidatedTool` (from `@cassicore/mcp-gateway`) | Executes whatever tool name the LLM requests through the injected executor; uses consolidated code/web/browser schemas for planning. |
| `constellation/src/constellation-orchestrator.ts` / `constellation-pipeline.ts` | `type ToolExecutor`, `type ToolRegistry`, `type ModelPool`; `getEffectivePool().acquire(slot, tier, sessionId, override)` | Type-level deps only; tools/registry injected by daemon, not constructed. |
| `mini-helix/src/mini-helix-runner.ts` | `type ModelHandle`, `type ModelCompletionOpts`; `handle.stream(messages, opts)`; `handle.release()`; `handle.provider`/`handle.model` | Acquires a handle (via handleFactory), streams, releases. |
| `cognitive-feed/src/index.ts` | `InteractiveToolSession`, `splitForTelegram`, `type ToolDefinition`, `type ToolExecutor` | Runtime use of the interactive tool-loop session wrapper for Telegram-curated turns. |
| `helix`/`constellation` brainstem/base-posture-runner | `type ModelHandle`, `ModelCompletionOpts`, `ToolExecutor`, `ToolRegistry` | The posture-runner / CassiAgent interfaces (type-only; injected). |

Mind-package **direct** tool imports are almost universally `type`-only (`ToolExecutor`/`ToolRegistry`/`ToolDefinition`/`ModelHandle`/`ModelCompletionOpts`). Runtime `@cassicore/tools` use = `InteractiveToolSession` (cognitive-feed) and the `graph_discover`/`collect_thoughts` handler wiring (the daemon injects `collectThoughtsDeps`/`peerToolDeps`/`cognitiveToolDeps`). The actual **tool execution** the mind performs is `executor.execute(name, ...)` where `name` is a coding tool (read_file/write_file/shell) or a mind tool — all registered by the daemon.

### Seam surface summary (what must remain for the mind)

1. **`ModelHandle` type + `stream()`/`release()`/`provider`/`model`/`ModelCompletionOpts`** (from `@cassicore/model-pool`) — the single most-used seam; acquired via a daemon-injected `handleFactory`.
2. **`ToolExecutor`/`ToolRegistry`/`ToolDefinition`/`ToolExecutionContext` types** (from `@cassicore/tools`) — injected, never constructed by the mind.
3. **Injected handler deps** for the mind tools: `collectThoughtsDeps`, `graphDiscoverDeps`, `cognitiveToolDeps` (`_reflect`/`_remember`), `peerToolDeps` (`_coordinate`/`_check_peers`) — the *mind tools* themselves.
4. **`InteractiveToolSession`** (cognitive-feed).
5. The **daemon wiring** (host) that acquires model handles and injects executor/registry into each mind module.

Everything else in providers/ai/model-pool full surface (SDK clients, OAuth, budget tracker, rate-limit store, model router, centralized provider, copilot-sdk), the coding tools, the MCP gateway/server/client, the commands dispatcher, the channel workers, and the admin-api HTTP surface are **not** mind-required and are delegation candidates for ohmypi.

---

## Part 3 — The standalone surface inventory (classification)

Decision context: the owner corrected the premise — CassiCore was *deliberately designed as a standalone daemon*, accessed via (a) its MCP gateway server and (b) its admin-api HTTP surface. The new direction: it does not need to be standalone; ohmypi will own providers, agent sessions, and tools. So the question is which of the 16 infra packages are MIND (stay), STANDALONE-SURFACE (delegate / ohmypi replaces), or BRIDGE (external adapters).

Legend: **MIND** = the cognitive mind modules require it (via Part 2 seam). **STANDALONE-SURFACE** = exists only because CassiCore is a self-contained daemon (boot, HTTP, MCP server, provider SDKs, session persistence, tool infra, CLI, command dispatcher, channel workers). **BRIDGE** = adapter to external tools. Sizes = src `.ts` files/lines; test counts from MIGRATION-STATUS §2.

| Package | files/lines | tests | Class | Why | External consumers (outside own pkg, non-vendor) |
|---|---|---|---|---|---|
| `mnemic-field` | (P4) | 89 | **MIND** | Memory field. | host, tools (type), others |
| `helix` | 9 tests/75 | **MIND** | Helix orchestrator. | uses model-pool, tools, mcp, mcp-gateway |
| `constellation` | 25/568 | **MIND** | Constellation. | uses model-pool, tools, workflow |
| `aurora` | 36/698 | **MIND** | Cognitive loop. | |
| `thalamus` | 6/97 | **MIND** | Attention/brain-state. | uses pipeline types |
| `flux-team` | 4/186 | **MIND** | Team blackboard. | |
| `dreamer-reverie-subconscious` | 8/184 | **MIND** | Dreamer/reverie/subconscious. | uses events (vendor audit stubs) |
| `cognitive-feed` | 1/97 | **MIND** | Cognitive feed. | uses tools (InteractiveToolSession) |
| `cortex-pineal-dialectic` | 4/143 | **MIND** | CPD. | |
| `mini-helix` | 1/21 | **MIND** | Mini-Helix. | uses model-pool |
| `workspace` | 1/17 | **MIND** | GlobalWorkspace (GWT), system prompt. | constellation, helix, cognitive-feed, pipeline, mcp-gateway |
| `embeddings` | passWithNoTests | **MIND** | Embeddings. | tools, helix (estimateTokens) |
| `training-trust-ledger` | 2/53 | **MIND** | Training/trust. | tools (type) |
| `lamina-locus-bridge` | 1/8 | **MIND** | Lamina + locus-bridge. | |
| `foundation` | 1/10 | **MIND/substrate** | Shared types/interfaces/paths ports, `IProvider`/`IModelDirective` contract. | everything |
| `events` | passWithNoTests | **MIND/substrate** | EventBus/Logger + session history querying. | tools, providers, plugins, workers, commands, dreamer, lamina, host |
| `utils` | passWithNoTests | **MIND/substrate** | Generic utils (TTLCache, CircuitBreaker, ids). | mnemic-field, helix, cpd, model-pool, providers, training-trust-ledger, host |
| `workflow` | passWithNoTests | MIND (borderline) | WorkflowEngine; heavily used by **constellation** (strategies) and the `workflow` tool. | constellation (many), host, tools |
| `jobs` | passWithNoTests | STANDALONE-SURFACE | JobManager for `run_background`/`check_job`/`wait_job` (daemon-gated). | admin-api `/jobs`, tools |
| `commands` | passWithNoTests | **STANDALONE-SURFACE** | `CommandDispatcher` — slash-commands for channels/CLI/TUI. | host, admin-api |
| `workers` | 2/97 | **STANDALONE-SURFACE** | Channel workers (cli/telegram/webchat/echo) — user-facing input channels. | host (`resolveWorker`) |
| `plugins` | passWithNoTests | **STANDALONE-SURFACE** | PluginHost + plugin API (daemon loads plugins per channel). | host, admin-api |
| `host` | 2/17 | **STANDALONE-SURFACE** | The composition-root daemon: boot, CLI/supervisor, ACP bridge, session+provider+tool wiring. | (everything lands here) |
| `admin-api` | 5/9 | **STANDALONE-SURFACE** | 54 HTTP route modules (17,554 lines) — the daemon's HTTP surface. | — |
| `mcp-gateway` | 2/40 | **STANDALONE-SURFACE** | The MCP **server** (stdio/HTTP) proxying the daemon over HTTP. | admin-api `/tools` catalog, helix (consolidated schemas) |
| `mcp` | passWithNoTests | STANDALONE-SURFACE (borderline) | MCP **client** to external servers (gitnexus/serena/etc.). | host, admin-api |
| `providers` | 5/120 | **STANDALONE-SURFACE / delegate** | Provider SDK clients + routing/budget/rate-limit. | host, admin-api, model-pool(CostClassifier) |
| `ai` | 1/36 | **STANDALONE-SURFACE / delegate** | Provider SDK layer (pi-ai fork), OAuth, model registry. | providers, model-pool |
| `model-pool` | 1/32 | **MIND (surface) / split** | `ModelHandle`/`ModelPool` — the mind's real acquisition seam. | helix, constellation, mini-helix, host |
| `tools` | 6/39 | **SPLIT** (mind-tools stay; coding/infra delegate) | Registry/executor + 30+ tool impls. Mind needs types + mind tools; coding tools are ohmypi's. | helix, constellation, cognitive-feed, admin-api |

**BRIDGE packages** (`integrations/*`, 3 of the 7 standalone apps): `claude-code` (11 src files, 4,197 lines), `hermes-agent` (5 src, 1,508), `opencode` (bare `cassicore.mjs` + install.sh). Plus `tools/src/{hermes-tools.ts, hermes-mcp-client.ts}` (Hermes ACP bridge). These adapt CassiCore *to* external agent tools — distinct from the mind.

### the mcp-gateway PUBLIC surface (what ohmypi must replace)
Listed in §1.3 — an external MCP server exposing `bash/read/write/edit`, `do/enrich`, the 16 consolidated domain tools (`agent, memory, session, intelligence, artifact, code, file, browser, web, config, model, training, cortex, self_model, context` + context_repo/lamina/annotation/knowledge), ~30 legacy domain tool groups (`sessions`, `memory_*`, `config_*`, `flux_*`, `dialectic`, `intelligence/activity|thinker|subconscious|consciousness|…`, `helix_*`, `model_directive`, `training_*`), and `cassicore://` resource URIs. It proxies to `http://localhost:7433` (the daemon's admin API).

### the admin-api ROUTE inventory (what ohmypi must replace — grouped, one line each)
54 route modules under `admin-api/src/routes/` (17,554 lines) + `admin-api.ts` (2,526 lines; Unix socket `~/.cassicore/admin.sock` + TCP `127.0.0.1:7433`):

- **Session/chat:** `sessions` (turn/list/get/delete via SessionPipeline), `chat`, `helix-sessions`, `turn-routing`, `replay` (+ `session-summary`, `legacy-sessions`).
- **Model/providers:** `models`, `providers`, `warm-provider`, `model-directive`.
- **Memory/intelligence:** `memory`, `context`, `context-repo`, `intelligence` (locus-bridge, module state), `thalamus`, `cortex`, `pineal`, `lamina`, `dmn`, `dialectic`, `dreamer`, `reverie`, `blackboard` (+ `lumen`/`dyad` blackboards).
- **Teams/subagents:** `teams`, `subagents`, `delegation`, `flux` (in `teams`/`orchestration`).
- **Tools/MCP/config:** `tools` (tool catalog), `mcp`, `config`, `code-store` (`/code`), `channels`.
- **Observability/ops:** `events`, `prompt-log`, `timeline`, `observability`, `health`, `debug`, `maintenance`, `jobs`, `training`, `verification`, `improvement`.
- **Plugin/extension:** `plugins`, `plugin-api` (`/plugin`), `modules`, `cycle-hooks`, `permissions` (+`trust`/`consequences`), `prism`.
- **Orchestration:** `orchestration`, `runtime`.

---

## Part 4 — Revised recommendation

Strategy: keep a **slim mind** (cognitive packages + their exact interface needs), **delegate** the standalone daemon surface to ohmypi (providers, agent sessions, coding tools, HTTP/MCP), **delete** what no longer earns its keep.

### KEEP-AS-INTERNAL (the mind + its true seam)
- **Mind packages:** `mnemic-field`, `helix`, `constellation`, `aurora`, `thalamus`, `flux-team`, `dreamer-reverie-subconscious`, `cognitive-feed`, `cortex-pineal-dialectic`, `mini-helix`, `workspace`, `embeddings`, `training-trust-ledger`, `lamina-locus-bridge` — the cognitive core. (14 packages, thousands of tests green.)
- **`model-pool`** — keep the **`ModelHandle`/`ModelCompletionOpts` type surface + `ModelPool.acquire/release`**. This is the mind's real provider seam. Rationale: the mind imports `@cassicore/model-pool` directly (helix, constellation, mini-helix) and the daemon acquires handles into it. **Port** to a slimmer surface (drop budget/billing/fallback if ohmypi owns those, or keep as-is). 8 files/3,045 lines, 32 tests.
- **`tools`** — keep the **mind tools + type surface**: `collect_thoughts`, `graph_discover`, `_reflect`, `_remember`, `_coordinate`, `_check_peers`, `remember`, `list_sessions`, `list_subagents`/`get_subagent_status`/`get_subagent_result`, `system_health`, `debug_session`, `universal_search`, `cassandra_query_events`, `desktop_vision`(?), plus `ToolExecutor`/`ToolRegistry`/`ToolDefinition` **types** + `InteractiveToolSession`. **Delegate the CODING tools** (shell_exec, cassi_shell, read_file(s), write_file, web_fetch, web_search, todo_write, run_tests, vybit, run_background/check_job/wait_job, workflow tool) to ohmypi.
- **`foundation`/`events`/`utils`** — shared substrate the whole mind sits on (types, EventBus, utils). Keep. `workflow` — keep (constellation depends on it heavily), but consider slimming to what constellation/host use.

### DELEGATE-SET (ohmypi replaces these — the standalone surface)
- **`providers`** (18 files/7,250; 120 tests) + **`ai`** (51 files/26,981; 36 tests) — **ohmypi owns providers.** No mind package imports them; the daemon boots them and feeds handles to the mind. Biggest win.
- **`host`** (222 files/68,949; 17 tests) — the standalone daemon composition root. Reduce to a "mind host" that exposes the mind's own surface to ohmypi; the boot/supervisor/CLI/ACP-bridge/session-wiring moves out. This is the largest and the core of the standalone model.
- **`admin-api`** (95 files/26,769; 9 tests) — the HTTP surface. ohmypi owns agent sessions; the `/sessions`, `/chat`, `/models`, `/providers`, `/tools` routes move to ohmypi. Mind-health/debug routes (cortex/pineal/thalamus/memory/replay) could stay as a slim internal API or be folded into ohmypi.
- **`mcp-gateway`** (43 files/17,004; 40 tests) + **`mcp`** (5 files/433) — MCP server + client. ohmypi owns tools; the exposed coding-tool MCP surface moves to ohmypi. The mind-tool exposure (collect_thoughts etc.) could stay if mind tools are re-exposed, but the server itself is standalone surface.
- **`commands`** (13 files/3,333) — slash-command dispatcher for channels. ohmypi owns sessions; command interception is user-facing.
- **`workers`** (9 files/3,080; 97 tests) — channel workers (cli/telegram/webchat). User-facing input channels.
- **`plugins`** (8 files/2,298) — plugin host — decision: keep only if ohmypi has no plugin layer, else delegate. Borderline.
- **`jobs`** (3 files/499) — JobManager backs `run_background`; delegate with coding tools.

### DELETE-SET (vanishes)
- **`cassi-tui`** (30), **`cassi-watch`** (12), **`prism`** (24), **`webui`** (134) — standalone apps that exist only as an operator interface to the standalone daemon. If ohmypi is the operator UI, these vanish. (They carry no package-visible tests — passWithNoTests.)
- **`commands`, `workers`** — see above (delegate or delete).

### Top-line recommendation
1. **Keep the 14 mind packages + `model-pool` (ModelHandle surface) + the mind-tool slice of `tools` + `foundation`/`events`/`utils`/`workflow`** — that is "the focused system (the cognitive mind only)".
2. **Delegate to ohmypi:** `providers`, `ai` (provider SDKs), `host`'s provider/session/tool wiring, `admin-api` session/chat/model/tool routes, `mcp-gateway` + `mcp` (tool MCP), `commands`, `workers`, and the **coding tools** in `tools`.
3. **Delete the standalone operator apps** (`cassi-tui`, `cassi-watch`, `prism`, `webui`).
4. **Resolve the host↔tools|mcp cycle first** (MIGRATION-STATUS §3.2) — it's exactly the tangle that makes "slim the mind out" non-trivial; extraction should start there, keeping `ModelHandle` + `ToolExecutor`/`ToolRegistry` types and the mind-tool handlers as the port surface.
