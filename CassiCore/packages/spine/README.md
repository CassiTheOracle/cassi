# @cassicore/spine

The ohmypi **extension ('spine')** that bridges the focused CassiCore mind runtime
(`@cassicore/mind-runtime`) into ohmypi. It is the only package that touches ohmypi;
it is small, event-driven, and never hosts fragile background loops (recon §5.6).

## Dependency rule

- `@cassicore/spine` dev-depends on `@oh-my-pi/pi-coding-agent` **17.3.4** (pinned per
  brief Open Item 5) and the retained `@cassicore/tools` (mind-tool definitions for
  schema fidelity) + `@cassicore/mind-runtime` (channel types + client).
- **`[SPINE-TYPES]` shim:** all spine source imports from `src/oh-my-pi-types.ts` (a
  faithful minimal type shim of the ohmypi surface it uses), **never** the real package
  root — because `@oh-my-pi/pi-coding-agent`'s root module pulls a native allocator that
  fails to load headlessly in plain CI/vitest. The shim is transcribed 1:1 from the
  inspected 17.3.4 `dist/types/**` signatures (ExtensionAPI, ToolDefinition,
  ExtensionContext, session events, memory backend). If an environment CAN load the real
  package, its devDep types break the typecheck on API drift.

## What the factory does (`export default function cassiSpine(pi)`)

1. **Connect to the mind runtime** over the loopback channel. `CASSI_MIND_URL` wins;
   else auto-spectral `cassi-mind` (detached) and health-probe (Open Item 1). The
   auto-spawn is best-effort — runtime liveness is the supervisor's concern (Open Item 4).
2. **Retained mind tools** — thin delegates (plan §4.2). For each retained tool the
   parameter schema is rebuilt from the retained `@cassicore/tools` definition and
   `execute` forwards `{tool, params, sessionId}` to the runtime (`/v1/tools/execute`),
   mapping the returned string to `AgentToolResult.content`.
3. **`mind_complete`** — the model-access bridge (plan §2.3). Resolves `model` via
   `ctx.models.resolve`, then streams ONE completion through an injectable transport
   (P3 default: a clear "transport not wired" error; the P4 cutover wires ohmypi's
   provider stream. [VERIFY: ohmypi's raw-completion primitive — plan §2.2 fallback].)
4. **Session lifecycle → runtime mirror** (plan §4.2): `session_start/switch/branch/
   compact/shutdown` → `/v1/session/mirror`; plus `appendEntry('mind.runtime.state', …)`
   episodic snapshots (plan §2.5).
5. **`mcp_notification` bridging** (plan §4.2 / verdict 29): pushes each MCP notification
   into the mind via `/v1/events/push`.
6. **Memory backend adapter** (`MnemicMemoryBackend`, plan §3): status/search/save
   proxying `/v1/memory/*` to the shared MnemicField.

## Registered tools

**Visible retained (12)** — `collect_thoughts`, `graph_discover`, `list_sessions`,
`list_subagents`, `get_subagent_status`, `get_subagent_result`, `system_health`,
`debug_session`, `universal_search`, `cassandra_query_events`,
`cassandra_context_inspect`, `query_events` — plus **`mind_complete`** (13 total, plan §4.2).

**Hidden seam (6, `hidden: true, defaultInactive: true`)** — `_reflect`, `_remember`,
`_coordinate`, `_check_peers`, `remember`, `memory_search` — the P5-deletion seam kept
registered-inactive until the ratified deletion lands (§7.5 / DELEGATE-SURFACE §1).

## [VERIFY] / open items resolved

- **`ctx.memory` wiring** — impossible in-process: `ctx.memory` is a READ-ONLY
  `MemoryRuntimeContext`; `MemoryBackendId` is a closed union. The adapter implements
  the runtime-context shape; ohmypi backend resolution must register it (documented in
  `src/memory-backend.ts`).
- **`mind_complete` transport** — P3 default is a documented "transport not wired" error;
  the P4 cutover wires the real ohmypi provider stream (or routes through task-agents).
- **`session_branch` / `session_compact` payloads** carry `entryId` / `summary` opaquely
  and are mirrored as `branchFrom` / `summary`.
- **Native-load CI constraint** — see `[SPINE-TYPES]` above.

## Tests

Vitest, node environment, `pool: forks`. **No live ohmypi** — the `ExtensionAPI` is
stubbed (`test/stub-pi.ts`) and the runtime channel client is stubbed. Covers:
registered tools (names/schemas/hidden flags, execute delegation, mind_complete
model-resolve + effort/temperature passthrough), lifecycle→mirror + appendEntry
snapshots + mcp_notification push, and the memory-backend adapter proxy.
