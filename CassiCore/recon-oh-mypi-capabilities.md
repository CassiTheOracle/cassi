# ohmypi Capabilities & Extension API — Recon Fact-Pack

**Purpose.** Input to the CassiCore slimming design decision: ohmypi ("Oh My Pi", the agent harness this process runs in) will own PROVIDERS, AGENT SESSIONS, and TOOLS; CassiCore keeps only its cognitive architecture. This report documents, precisely and with doc-grounded quotes, what ohmypi offers in those three domains and what its extension/plugin API allows — so the design can decide what CassiCore can delegate and what it must still self-host.

**Method.** READ-ONLY research over the omp:// documentation set listed in the brief. All API shapes, counts, and "gaps" statements below are grounded in those docs. Everything quoted is verbatim from the referenced doc. Version-dependence and ambiguity are flagged in Section 6.

---

## 1. Extension API surface

### 1.1 What an extension is (factory shape)

From `omp://extensions.md`:

> An extension is a TS/JS module exporting a default factory. Factories may initialize synchronously or return a promise:
> ```ts
> import type { ExtensionAPI } from "@oh-my-pi/pi-coding-agent";
> export default function myExtension(pi: ExtensionAPI) {
>   // register handlers/tools/commands/renderers
> }
> ```

Extensions combine — in one module — event handlers (`pi.on`), LLM-callable tools (`pi.registerTool`), slash commands (`pi.registerCommand`), keyboard shortcuts and flags, custom message rendering, and session/message injection (`sendMessage`, `sendUserMessage`, `appendEntry`).

### 1.2 Manifest / discovery (the `package.json` shape)

From `omp://skills/authoring-extensions.md` and `omp://extension-loading.md`:

```json
{
  "name": "my-omp-extension",
  "omp": {
    "extensions": ["./src/main.ts"]
  }
}
```

- Legacy key `pi.extensions` still accepted.
- Multiple entry points supported: `"extensions": ["./src/safety.ts", "./src/tools.ts"]`.
- An extension package can also bundle sibling capability directories — discovered when loaded through `extensions:` or `--extension/-e` — "its `skills/`, `hooks/pre|post/`, `tools/`, `commands/`, `rules/`, `prompts/`, and `.mcp.json`" (`authoring-extensions.md`).
- Auto-discovery roots (native): `<cwd>/.omp/extensions` and the active agent dir's `extensions/` (default `~/.omp/agent/extensions`).
- Installed-plugin entry resolution accepts `.ts`, `.js`, `.mjs`, `.cjs`; a manifest entry naming a directory resolves `index.ts/.js/.mjs/.cjs`.
- Extension id for disable: `extension-module:<derivedName>` (filename stem).
- **No strict manifest schema** (`plugin-manager-installer-plumbing.md`): "There is no strict schema validation in manager/loader."

### 1.3 Runtime model / lifecycle (per-turn? per-session? event-driven?)

From `omp://extensions.md`:

1. Extensions are imported and their factory functions run (**registration only** — runtime actions like `pi.sendMessage()` at load time throw `ExtensionRuntimeNotInitializedError`).
2. `ExtensionRunner.initialize(...)` wires live actions/contexts for the active mode.
3. Session/agent/tool lifecycle events are emitted to handlers.
4. Every tool execution is wrapped with extension interception (`tool_call` / `tool_result`).

So the invocation model is **event-driven, session-lifetime**: factories run once at session load; the runtime then delivers lifecycle events (`session_start`, `tool_call`, `turn_end`, …) to handlers across the session's life. There is a per-turn agent loop (the `agent_start`/`agent_end`, `turn_start`/`turn_end`, `before_provider_request` events), but the plugin itself is not "called once per turn" — it registers handlers and reacts.

Extensions run **in-process with no sandboxing** (`extension-loading.md`): "Extensions are **not sandboxed** (same process/runtime). They share one `EventBus` and one `ExtensionRuntime` instance."

### 1.4 The ExtensionAPI object — EVERY capability

From `omp://extensions.md` §"1) Registration and actions (`ExtensionAPI`)" — the canonical method surface (**13 core methods**):

| # | Capability | Signature (as documented) | Purpose |
|---|---|---|---|
| 1 | `on` | `on(event, handler)` | Register an event handler for any lifecycle/tool/prompt event |
| 2 | `registerTool` | `registerTool(ToolDefinition)` | Register an LLM-callable tool (omptype/Zod/TypeBox parameter schema) |
| 3 | `registerCommand` | `registerCommand(name, { description, handler })` | Register a `/` slash command (user-invoked) |
| 4 | `registerShortcut` | `registerShortcut(...)` | Register a keyboard shortcut |
| 5 | `registerFlag` | `registerFlag(...)` | Register a CLI/flag toggle |
| 6 | `registerMessageRenderer` | `registerMessageRenderer("my-type", (message, { expanded }, theme) => Component)` | Render custom messages in the TUI |
| 7 | `registerAssistantThinkingRenderer` | `registerAssistantThinkingRenderer((context, theme) => Container)` | Add display-only UI below each thinking block |
| 8 | `setLabel` / `getFlag` | `setLabel("Safety + Utilities")`; `getFlag(...)` | Label grouping / read flags |
| 9 | `sendMessage` | `sendMessage(message, { deliverAs, triggerTurn })` | Inject a message into the session (steer / followUp / nextTurn) |
| 10 | `sendUserMessage` | `sendUserMessage(content, { deliverAs })` | Inject a *user*-attributed prompt into the session |
| 11 | `appendEntry` | `appendEntry("com.example.state", data)` | Persist opaque non-LLM state into the session log (`custom` entry) |
| 12 | `exec` | `exec(command, args, options?)` | Run a shell command (also present on `CustomToolAPI`) |
| 13 | `registerProvider` | `registerProvider(...)` | Register a model provider / stream handler / custom OAuth provider (see §2) |

**Tool-set control:** `getActiveTools()`, `getAllTools()`, `setActiveTools(...)`.

**Command introspection:** `getCommands()`.

**Session identity control:** `getSessionName()`, `setSessionName(name)`.

**Model/behavior control:** `setModel(...)`, `getThinkingLevel()`, `setThinkingLevel(...)`.

**Per-family service tier:** `getServiceTiers()` (detached snapshot), `setServiceTier(family, tier)` — `family ∈ {openai, anthropic, google}`; tier values `auto|default|flex|scale|priority` (OpenAI), `priority` (Anthropic), `flex|priority` (Google).

**Event bus:** `events` (shared event bus).

**Non-method exposed members:**
- `pi.logger` — shared file logger
- `pi.arktype` — the omptype `type(...)` schema builder
- `pi.zod` — Zod-compatible builder backed by omptype
- `pi.typebox` — legacy TypeBox-compatible shim
- `pi.pi` — package exports (`@oh-my-pi/pi-coding-agent`)

**Count:** **13 functional methods + 1 event bus + 5 injected helper members** on the `ExtensionAPI` object. (The docs group some as "methods" which I have enumerated as 13; plugin authors can consume ~18 distinct surface items including the helpers.) Event handler count is far higher — see §1.5.

### 1.5 Handler context (`ExtensionContext`) — what a plugin accesses about its session

Every handler and tool `execute` receives `ctx` with:

- `ui` / `hasUI` — interactive UI surface + whether present
- `cwd` — current working directory
- `sessionManager` (**read-only**) — session/tree access (`getBranch()`, `getSessionFile()`, `getSessionName()`, appends, etc.)
- `modelRegistry`, `model` — provider/model access
- `models` — read-only model query facade: `list()`, `current()`, `resolve(spec)`, `family(model)`
- `localProtocolOptions` — calling-session `local://` root mapping for external tool bridges
- `getContextUsage()` — token/context usage
- `getAsyncJobSnapshot()` — session async-job snapshot or `null`
- `compact(...)` — request compaction
- `isIdle()`, `hasPendingMessages()`, `abort()`
- `shutdown()`
- `getSystemPrompt()`
- `memory` — "optional structured memory runtime — status/search/save across the configured backend" (**only when a memory backend is configured**; see §5 gap)
- `setInterval(fn, ms, ...args)` / `setTimeout(...)` / `clearTimer(handle)` — **managed timers** (raw `setInterval`/`setTimeout` that throw will tear down the whole session, uncaughtException)

### 1.6 Command context (`ExtensionCommandContext`)

Command handlers additionally get session-control methods: `waitForIdle()`, `newSession(...)`, `switchSession(...)`, `branch(entryId)`, `navigateTree(targetId, { summarize })`, `reload()`.

### 1.7 Event surface (the full catalog)

**Session lifecycle:** `session_start`, `session_before_switch`/`session_switch`, `session_before_branch`/`session_branch`, `session_before_compact`/`session.compacting`/`session_compact`, `session_before_tree`/`session_tree`, `session_shutdown`. Cancellable pre-events return `{ cancel?: boolean }` (and richer payloads for branch/compact/tree).

**Prompt & turn lifecycle:** `input`, `before_agent_start`, `before_provider_request` (may REPLACE provider request payload), `after_provider_response`, `context` (may replace messages), `agent_start`/`agent_end`, `session_stop` (may continue with additionalContext, max 8 continuations), `turn_start`/`turn_end`, `message_start`/`message_update`/`message_end`.

**Tool lifecycle:** `tool_call` (pre-exec; may `block` or revise `input`), `tool_result` (post-exec; may patch content/details/isError), `tool_execution_start/update/end`, `tool_approval_requested`/`tool_approval_resolved`.

**Reliability/runtime:** `auto_compaction_start/end`, `auto_retry_start/end`, `ttsr_triggered`, `todo_reminder`, `goal_updated`, `credential_disabled`.

**MCP notifications:** `mcp_notification` — every JSON-RPC notification from a connected MCP server; lets plugins bridge a push-capable MCP into a session steer via `pi.sendUserMessage`.

**User command interception:** `user_bash`, `user_python` (override with `{ result }`).

**Not wired:** `resources_discover` exists in types/runner but "there are no `AgentSession` callsites invoking it" (`extensions.md`).

### 1.8 Tool registration details (`ToolDefinition`)

`registerTool` takes `ToolDefinition`; `parameters` accepts omptype schemas (Zod builder). Current `execute` signature:

```ts
execute(toolCallId, params, signal, onUpdate, ctx): Promise<AgentToolResult>
```

`ToolDefinition` supports fields: `name`, `label`, `description`, `parameters`, `hidden`, `defaultInactive`, `loadMode` (`"discoverable"` default | `"essential"`), `deferrable`, `approval` (`"read" | "write" | "exec"`, default `"exec"`), `strict`, `mcpServerName`, `mcpToolName`, `renderCall`, `renderResult`, plus an `onSession(event, ctx)` lifecycle callback.

A shadowing built-in tool can delegate to the **native** implementation via `ctx.invokeTool?<TDetails>(params, options)` (same-name delegation only).

### 1.9 MCP server registration / `.mcp.json`

A plugin **cannot programmatically register an MCP server through `ExtensionAPI`**; there is no `pi.registerMCP()`. MCP comes in via **config discovery** (`.mcp.json`, `.omp/mcp.json`, `~/.omp/agent/mcp.json`, Claude/Codex/VSCode roots, and plugin sibling roots) — an extension package may bundle a `.mcp.json` that the `omp-plugins`/`claude-plugins` discovery provider scans when the package is enabled. So "MCP server registration by plugin" = ship a `.mcp.json` in the package's conventional sibling dir; ohmypi connects it and surfaces its servers as `mcp__<server>_<tool>` tools. See §4.

### 1.10 Constraints/pitfalls

- Runtime actions unavailable during load (throw `ExtensionRuntimeNotInitializedError`).
- `tool_call` handler throws → tool blocked (fail-closed).
- Command name conflicts with built-ins → skipped with diagnostic.
- Reserved shortcuts ignored: `ctrl+c/d/z/k/p/l/o/t/g/q`, `alt+m`, `shift+tab`, `shift+ctrl+p`, `alt+enter`, `escape`, `enter`.
- Extensions vs hooks vs custom-tools: **extension** is the unified superset; **hook** is legacy; **custom-tool** is tool-focused modules that get adapted and also pass through extension interception.

---

## 2. Providers — how a plugin calls models

### 2.1 The provider abstraction

From `omp://providers.md`:

> A **provider** is the account or backend namespace, such as `anthropic`, `openai`, `google`, or `ollama`. A **model** is a concrete model under that provider, selected as `provider/model-id`, such as `anthropic/claude-opus-4-6`.

Models are selected as `provider/model-id`. A model is **available** only when: (1) its provider is not in `disabledProviders`, and (2) the provider is **keyless** (implicit local, or `auth: none`) **or** has resolvable credentials.

Catalog assembly order (`providers.md`): bundled catalog → `~/.omp/agent/models.yml` custom entries → runtime-discovered models (local engines, discovery-enabled gateways) → **providers/models registered by extensions**.

### 2.2 secrets / API keys (from `secrets.md`)

Two distinct surfaces, both relevant:

1. **Credential resolution** (`providers.md`/`models.md` `AuthStorage.getApiKey` order): runtime override (`--api-key`) → `models.yml` provider `apiKey` → stored OAuth credential (with refresh) → login-sourced stored key → provider env var / `.env` → other stored key → `models.yml` fallback resolver. Stored credentials live in `~/.omp/agent/agent.db` (or auth-broker snapshot). Logins are provider-scoped; `/login`, `/logout`, and `omp auth-broker login` are the flows.
2. **Secrets obfuscation** (`secrets.md`): when `secrets.enabled: true`, configured secrets (`~/.omp/agent/secrets.yml`, `<cwd>/.omp/secrets.yml`, marker-like env vars) are replaced with reversible `$$HASH$$` placeholders before provider-visible text leaves the process; placeholders are restored in model-authored tool arguments before execution and for local display/resume. This is separate from credential storage.

### 2.3 Can plugins register NEW providers?

**Yes.** From `extensions.md`: `pi.registerProvider`. From `models.md` §"Extension provider registration":

> Extensions can register providers at runtime (`pi.registerProvider(...)`), including:
> - model replacement/append for a provider
> - custom stream handler registration for new API IDs
> - custom OAuth provider registration

`adding-a-provider.md` confirms the runtime path: "A `ProviderDefinition` may also be registered at runtime by an extension via `registerOAuthProvider` (the `AuthStorage.login` dispatcher handles built-ins and extensions through the same path)."

Scope caveat (`adding-a-provider.md`): a provider that **reuses an existing wire API** (`openai-completions`, `anthropic-messages`, `google-generative-ai`, …) is the documented common case. Adding a **new wire protocol** ("a new `KnownApi`") is a separate task touching `stream.ts` dispatch, `api-registry.ts`, and catalog `types.ts`. Plugin-registered providers still respect `disabledProviders`, keyless/auth-none handling, and per-provider `models.yml` overrides.

### 2.4 Streaming + tool-calling support level

Deep. `provider-compat-reference.md` catalogues per-provider tool handling across five native families (Anthropic, OpenAI Completions, OpenAI Responses, Google/Vertex, Amazon Bedrock), each with schema normalizers, streaming shapes, call-id rules, and result encodings. Additional **text-based in-band tool-call dialects** (`src/dialect/`) exist for hosts lacking native tool APIs: `harmony`, `gemini`, `qwen3`, `deepseek`, `kimi`, `glm`, `gemma`, `hermes`, `minimax`, `xml`, `anthropic`. Reasoning levels map through an `Effort` enum (`minimal|low|medium|high|xhigh|max`) with per-provider wire encoding. Forced tool choice supports `auto|none|required|any|{type:"function",name}|{type:"tool",name}|{type:"computer"}` with per-provider downgrade/emulation.

Note (`toolconv/pi-native.md`): `pi-native` is **not** a textual tool-call dialect — it is a lossless transport (`POST /v1/pi/stream`) where tool calls remain canonical pi-ai `ToolCall` content blocks. "There is no `<call:NAME>` grammar, parser, renderer, or `PI_DIALECT=pi-native` value in the current implementation." Pipeline note: this doc set's own agent loop runs two tool-call conventions — the general agent loop and the model "no native tools → in-band dialect" streams.

### 2.5 Local models support

**Yes, extensively.** Built-in keyless local engines: `ollama` (`http://127.0.0.1:11434`, keyless), `llama.cpp` (`http://127.0.0.1:8080`, keyless unless a key is stored), `lm-studio` (`http://127.0.0.1:1234/v1`, keyless) — all auto-discovered when running. Also `vllm` and generic OpenAI-compatible discovery (`discovery.type: openai-models-list`). Custom keyless local providers via `models.yml` with `auth: none`. Remote compaction can POST to local endpoints (`llama.cpp`/`vLLM` acting as remote compactors). Mnemopi's memory backend supports local embeddings and FTS-only mode.

### 2.6 Provider summarization

A plugin calls models by (a) reading/selecting models via `ctx.models` (`list()`, `current()`, `resolve(spec)`, `family(model)`) or the SDK `ModelRegistry`, (b) letting the agent loop dispatch through the configured provider, and (c) `setModel`/role aliases (`@smol`, `@slow`, …). Credentials are resolved automatically through the auth chain; a plugin does not manage raw API keys for built-in providers. Plugin-registered providers can glue custom auth (including `registerOAuthProvider`).

---

## 3. Agent sessions

### 3.1 Session identity / persistence

Sessions are append-only JSONL files, one JSON object per line, under `~/.omp/agent/sessions/<encoded-cwd>/<timestamp>_<sessionId>.jsonl` (`session.md`). Header `SessionHeader` carries `id`, `timestamp`, `cwd`, `title`, `titleSource`, `additionalDirectories`, `previousSessionFiles`, `providerPromptCacheKey`, `parentSession`. Current session **version 3** with migrations v1→v2→v3. Entries are a typed union (`message`, `model_change`, `service_tier_change`, `thinking_level_change`, `compaction`, `branch_summary`, `reset_boundary`, `custom`, `custom_message`, `label`, `title_change`, `ttsr_injection`, `credential_pin`, `session_init`, `mode_change`).

**Storage abstractions:** `FileSessionStorage` (default), `MemorySessionStorage` (in-memory), `IndexedSessionStorage` (Redis/SQL-backed remote). Session methods: `SessionManager.create/open/continueRecent/forkFrom` (persistent), `.inMemory()` (non-persistent). `session.subscribe(...)` for event streaming; `session.prompt(text, options)` is the primary entry point; `sendUserMessage`, `steer`, `followUp`, `sendCustomMessage`, `abort()`.

### 3.2 Session tree / forks / resume / export (summary)

- **Tree:** the model is "append-only tree + mutable leaf pointer" — every append is a child of the current `leafId`; `branch(entryId)` moves only the leaf; `resetLeaf()` creates a new root; `branchWithSummary()` appends a `branch_summary`.
- **Forks:** `/fork` creates a new session file (`parentSession` set, prompt-cache key inherited); `--fork <id|path>`; `SessionManager.createBranchedSession(leafId)`.
- **Resume:** `/resume [id|@claude|@codex]`, `--resume`, `--continue`, `SessionManager.continueRecent()`. Cross-project re-rooting (moveTo) supported.
- **Export/share:** `/export [--themes] [path]` (HTML), `--export <session.jsonl>`, `/dump` (text + temp JSON sidecar), `/share` (e2e-encrypted AES-256-GCM snapshot; gist or share server).
- **Compaction** (`compaction.md`): rewrites old history to a summary on the branch; strategies `context-full`, `handoff`, `shake`, `snapcompact` (bitmap archival). Entries are `compaction`/`branch_summary`. Plugins hook via `session_before_compact` (cancel or supply custom `CompactionResult`), `session.compacting` (override prompt/context/preserveData), `session_compact`.
- **Clear/fresh:** `/clear` appends `reset_boundary`; `/fresh` rotates provider stream state without clearing conversation; `/new`/`/drop` new/delete sessions.

### 3.3 Sub-agents (task) & the agent hub

- **`task` tool** (`tools/task.md` / `task-agent-discovery.md`): spawns one subagent, or a `tasks[]` batch. Custom agents from `~/.omp/agent/agents/*.md`, `.omp/agents/*.md`, extension-package `agents/`, marketplace plugins, plus bundled (`scout`, `designer`, `reviewer`, `security-reviewer`, `librarian`, `task`, `sonic`). Model priority: `task.agentModelOverrides` → agent frontmatter `model` → parent's model. Lifecycle: `running | idle | parked | aborted`; idle agents park after `task.agentIdleTtlMs` (default 7 min) and revive via messaging/`hub`. Output under `agent://<id>`, transcript `history://<id>`, nested `agent://<id>/<child>`.
- **Agent Hub** (`agent-hub.md`): TUI to watch/steer/kill/revive subagents; discovers parked agents from persisted artifacts on resume. Advisor transcripts appear as read-only rows.
- **SDK subagent options** (`sdk.md`): `outputSchema`, `outputSchemaMode`, `requireYieldTool`, `taskDepth`, `parentTaskPrefix` for orchestrators.

### 3.4 What a plugin can access about ITS OWN session

Via `ctx` (§1.5): `sessionManager` (**read-only**), `cwd`, `modelRegistry`/`model`/`models`, `localProtocolOptions`, `getContextUsage()`, `getAsyncJobSnapshot()`, `compact()`, `isIdle()`, `hasPendingMessages()`, `abort()`, `shutdown()`, `getSystemPrompt()`, `memory` (optional). State persistence via `pi.appendEntry("com.example.state", data)` (namespaced, reverse-domain), reconstructed from `ctx.sessionManager.getBranch()` on `session_start`/`session_branch`/`session_tree`.

### 3.5 How the outer runtime invokes plugins (lifecycle recap)

Plugins are **factory-loaded at session start, then event-driven for the session's lifetime** — no per-turn synchronous callback by default; the agent loop emits lifecycle events (`before_provider_request`, `agent_start/end`, `turn_start/end`, `tool_call/result`, `session_stop`) that handlers react to, including mutating provider context at `context`/`before_provider_request`/`tool_call`. Per-session registration happens in `registerTool`/`registerCommand`/`on`. Timers via managed `ctx.setInterval`/`setTimeout` for background work.

---

## 4. Tools

### 4.1 Built-in tool set (names + one-line purpose)

From `tools/*.md` and the SDK `BUILTIN_TOOLS`/`createTools` surface. Canonical built-ins include (one-line purposes):

| Tool | Purpose (one line) |
|---|---|
| `read` | Read files, directories, archives, SQLite DBs, internal URLs, images, documents, and web URLs through one `path` string (with `:selector` grammar). |
| `write` | Create/overwrite a file, writable internal resource, archive entry, SQLite row, or merge-conflict resolution. |
| `bash` | Execute a shell command in the session workspace, with optional PTY or background-job handling. |
| `task` | Spawn subagents — one per call or a `tasks[]` batch (with `context` for batch) — optionally backgrounded. |
| `hub` | Agent coordination: peer messaging, background-job control, supervised long-running processes; job `list`/`send`/`wait`/`cancel`. |
| `grep` | Regex search over files/internal URLs. |
| `glob` | Glob files/directories/path-backed internal URLs. |
| `edit` | Single-file string replacement with fuzzy whitespace matching (the surgical edit tool). |
| `eval` | Run one step of code in a persistent kernel (Python/JS). |
| `computer` | Host desktop control (windows, screenshots, native input, OS accessibility trees). |
| `ask` | Prompt the interactive user for option-picker or free-form answers (headless sessions never get it). |
| `ast_grep` | Structural AST code search via native ast-grep (disabled by default; `astGrep.enabled = false`). |
| `ast_edit` | AST-aware rewrites/codemods. |
| `yield` | Subagent/worker terminal-result submission (hidden by default, opt-in unless required). |
| `inspect_image` | Vision-model image analysis. (exposed indirectly) |
| `web_search` | Web search via the virtual `xd://` device. |
| `lsp` | Language-server symbol-aware intelligence (xref, rename, diagnostics). |
| memory tools | `recall`, `retain`, `reflect`, `memory_edit` (Mnemopi backend only), plus `learn` (autolearn opt-in). |

Other built-ins referenced by the docs include `debug`, `article-ish` internal URLs, `memory://`, `skill://`, task/mcp/xdev devices. The docs explicitly name the **canonical essential built-ins** in `custom-tools.md`: "`read`, `write`, `bash`, `edit`, `glob`, `computer`, `eval`, `task`, `hub`, `learn`, and `manage_skill`" default to `loadMode: "essential"` so wrappers don't demote them. SDK options: `toolNames`, `restrictToolNames`, `requireYieldTool`, `createTools(...)`, `BUILTIN_TOOLS`.

### 4.2 How a plugin defines custom tools — schema format

**Two equivalent paths:**

1. **`pi.registerTool(ToolDefinition)`** (extension) or
2. **`CustomToolFactory`** (`custom-tools.md`): a module exporting a factory `(pi) => CustomTool | CustomTool[]`, with `parameters` built via `pi.zod` (Zod-compatible omptype), `pi.arktype` (native omptype `type(...)`), or `pi.typebox` (legacy shim).

The underlying schema type is **omptype** (`omp://omptype-guide.md`): an ArkType-compatible validator with a lazy JIT runtime. "Internal schemas use `@oh-my-pi/omptype` — an ArkType-compatible validator with a lazy JIT runtime." At the provider boundary those schemas convert to JSON Schema: "omptype = a callable function with `.toJsonSchema` and `.assert` methods; **JSON Schema = a plain object**." So the wire/validation format is structured JSON Schema (generated from omptype), NOT freeform JSON Schema at authoring time — plugin authors use the omptype (or Zod/TypeBox-backed) builder.

### 4.3 Tool-calling conventions across providers (toolconv)

Native tool calling is canonical pi-ai `ToolCall` content blocks in `Context`/`AssistantMessageEvent`; per-provider wire normalization lives in `provider-compat-reference.md` (streaming shapes, call-id rules, result encodings, strict schemas). For non-native hosts, in-band text dialects (`harmony`, `gemini`, `qwen3`, `deepseek`, `kimi`, `glm`, `gemma`, `hermes`, `minimax`, `xml`, `anthropic`) render tool inventory into the prompt and parse streamed text back into calls. `pi-native` (auth-gateway transport) keeps canonical types losslessly; it is NOT a text dialect.

### 4.4 MCP

**Can a plugin run an MCP server?** Yes, by shipping a `.mcp.json` in the plugin's conventional sibling root (or configuring one); ohmypi's `MCPManager` connects and bridges servers as `mcp__<server>_<tool>` tools. Server config supports `stdio` (default), `http` (Streamable HTTP), `sse` (legacy 2024-11-05). Live updates via `/mcp reload` → `disconnectAll` + rediscover + `session.refreshMCPTools`. OAuth cred injection managed by ohmypi.

**Can ohmypi expose ITSELF as an MCP server?** Not from the docs read — there is no documented surface where ohmypi runs an MCP *server* for others to connect to. Its MCP role is client-only (connects to MCP servers). The obverse integration surfaces are: (a) the **RPC protocol** (`omp://rpc.md`) — ohmypi runs as a newline-delimited JSONRPC server over stdio (`omp --mode rpc`), letting an external host drive sessions and even supply **host-owned tools** (`set_host_tools` → `host_tool_call` round-trip) and **host-owned URI schemes** (`set_host_uri_schemes` → `host_uri_request`) — and (b) the **SDK** (`@oh-my-pi/pi-coding-agent` in-process embedding). These are the documented "host embedding" surfaces, not MCP-server mode. (Marked as a version/open question: no `mcp-server` mode doc was found.)

---

## 5. What ohmypi explicitly does NOT provide (gaps)

Plugins/CassiCore must self-host or do without:

1. **Long-running / persistent background daemons.** Extensions run in-process, no sandboxing; managed timers (`ctx.setInterval`) are `unref`'d and cleared on `session_shutdown`. There is no plugin-owned, process-independent background service. Any always-on daemon (a separate CassiCore cognitive runtime) must be spawned/run outside ohmypi (e.g. via `hub` start in `py`/service frames, or a separate process), not hosted inside the plugin. The collab relay and share server are external self-hosted services, not plugin-hosted.
2. **Multi-agent orchestration beyond task/hub subagents.** ohmypi's multi-agent story = one `task`/`hub` subagent layer (spawn, steer, park, revive). There is no higher-level orchestrator, swarm scheduler, or durable "team/cohort" state machine built in; a plugin that wants its own orchestration must layer it on `task`/`hub` or implement its own. (The `hub` `start`/`ps` surfaces do offer process management for services.)
3. **Memory beyond mnemosyne / the local backend.** Structured memory (`recall`/`retain`/`reflect`/`memory_edit`) exists only when a memory backend is configured (`memory.backend: mnemopi` or `hindsight`; local backend exposes `learn` and `memory://` reads but NOT structured `recall`/`retain`/`reflect`/`memory_edit`). Memory is disabled (`off`) by default. `ctx.memory` is "optional." A plugin needing rich cognitive memory must plug its own backend/`memory://` or store via `custom` entries.
4. **Self-persisted plugin state beyond custom session entries / agent artifacts.** A plugin can persist opaque `custom` entries (`pi.appendEntry`) and rebuild from `sessionManager.getBranch()`, but there is no dedicated key-value store for extension-scoped durable state outside the session log. Plugin settings in `omp-plugins.lock.json` are per-plugin config, not arbitrary data stores.
5. **New wire protocols for providers.** `registerProvider` covers providers reusing existing wire APIs (openai-completions, anthropic-messages, …). A brand-new wire `KnownApi` is not a plugin-level capability — it's a codebase change (`stream.ts`, `api-registry.ts`, catalog types).
6. **Long-lived process-lifetime guarantees.** The plugin runtime has no process-isolation; a raw timer/async throw can crash the whole session (`uncaughtException`). So plugins must not host fragile/reliable background runtime.

---

## 6. Open questions (version-dependent / ambiguous)

1. **MCP server mode.** Does any ohmypi version expose the harness itself as an MCP *server* (for an external client to connect) beyond the RPC-protocol and SDK embedding surfaces? The read docs describe a client-only MCP role plus RPC/SDK hosting; no `mcp-server` mode was found.
2. **`resources_discover` latency.** The extension type/runner implement `resources_discover`, but "there are no `AgentSession` callsites invoking it." So plugins relying on resource discovery may be dead code in some builds.
3. **`pi.registerProvider` depth.** The docs describe runtime provider registration (model replace/append, custom stream handler, custom OAuth) but not a full catalog/plugin API signature listing — so "register a *new* wire protocol at runtime" is ambiguous and likely unsupported (see §2.3/§5.5).
4. **`ctx.memory` presence semantics.** "optional structured memory runtime" is conditional on a configured backend; the exact object shape/API when present is not fully spelled out in the extension docs (covered behaviorally in memory/mnemopi docs).
5. **RPC/SDK embedding vs extension for a "host" integration.** The cleanest way for CassiCore (a separate cognitive component) to drive ohmypi — in-process SDK (`createAgentSession`) vs RPC stdio protocol vs an extension — is a design choice the docs support in three ways, but exact recommended split is emergent, not documented as a single contract.
6. **Version pinning of the API surface.** All shapes above reflect the current `@oh-my-pi/pi-coding-agent` docs (extension `ExtensionAPI`, session v3, MCP protocol rev `2025-03-26`). ohmypi is evolving; exact method signatures, event names, `compileOptions`, and plugin-manifest fields may shift across releases. Pin a version before building the CassiCore↔ohmypi bridge.

---
<!-- Report end -->
