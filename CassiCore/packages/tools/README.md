# @cassicore/tools

Tool registry, executor, safety/reliability wrappers, presentation, scout, the
Hermes MCP client, and the 30+ core tool implementations (`registerCoreTools`)
extracted from CassiCore (history-preserved) into a standalone TypeScript ESM
package.

## Status

Migrated at **P6 turn 1** of the cassi-mind plan. Live code (46 files under
`src/` across the top-level, `implementations/`, and `hooks/`) carries its
cassicore git history via an import splice from `cassicore HEAD@d63358da`.
Rewiring applied:

1. **`@cassicore/foundation`** — the shared substrate (`ILogger`, `IEventBus`,
   `IMemory`, `ISessionManager`, `Session`, `Message`, `EventQuery`,
   collect-thoughts + workflow types, `getRepoRoot` paths port,
   `MODEL_DEFAULTS`/`getModelSpec`).
2. **landed brain-region packages** — `CorticalField`/`SignalType` from
   `@cassicore/cortex-pineal-dialectic` (type), `TrustLedger` from
   `@cassicore/training-trust-ledger` (type), `GraphAttnPropagator` from
   `@cassicore/mnemic-field` (type).
3. **`src/vendor/**`** — faithful stubs for subsystems not yet migrated:
   - `core/logger.ts` / `core/event-bus.ts` (`rootLogger`, `bus`) and a
     minimal `core/events` surface (`getEventBus`, `getContextWindowDebugger`,
     `ContextWindowDebugger`) — **RUNTIME verbatim copies**; owned by
     `@cassicore/events` (P6 turn 3), re-pointed there.
   - `core/utils/{ttl-cache,ids}.ts` (`TTLCache`, `generateShortId`,
     `generateReadableId`) — RUNTIME; owned by `@cassicore/utils` (P6).
   - `core/intelligence/permission-oracle/types.ts` (`resolveToolDomain`) —
     RUNTIME pure function; owned by `@cassicore/training-trust-ledger` (P5).
   - `core/mcp/{client,types}.ts` (`MCPClient`, `MCPServerConfig`) — faithful
     local vendored copy (the `@cassicore/mcp` package was deleted at P5; the
     coding-tool machinery kept only this in-package copy). `vybit.ts`
     instantiates `MCPClient` only when the vybit tool is invoked.
   - `core/intelligence/{thought-observer,cognitive-bridge,branching-conversation,
     synapse,thinker}/*` — **type stubs** (Open-6 default: vendor faithful stubs
     when the owning P5 package doesn't yet export the symbol).
   - `core/version.ts` (`CASSICORE_VERSION`) — faithful pure-constant (avoids
     execSync); home `[OPEN]` (Open-4).
   - host-side seams (`core/event-history`, `core/event-query-parser`,
     `core/event-query-presets`, `core/tool-proxy-middleware`,
     `core/session-store`, `core/turn-pipeline`) — **placeholders** until P7
     (the host packages own them).

The **`registerCoreTools(registry, deps)`** contract and the
`ToolRegistry`/`ToolExecutor`/`ToolDefinition`/`ToolHandler`/
`ToolExecutionContext`/`ToolCategory` types are exported from the packager
barrel `src/index.ts` (the source `core/tools` dir has no barrel; the packager
writes it). `ToolRegistry` is an explicit-registration Map (no directory scan);
tool "auto-discovery" is the `registerCoreTools` bulk entry + the `list_tools`
meta-tool.

## Notes

- `@cassicore/events`, `@cassicore/utils`, `@cassicore/workflow` are retained
  packages; this package vendors the surfaces it consumes and re-points as each
  publishes (tools is the highest-fanout package, so this re-point is its own
  commit). The former `@cassicore/mcp` and `@cassicore/jobs` packages were
  **deleted** at P5 (coding-tool MCP/job-manager machinery now lives as local
  vendored `vendor/core/{mcp,jobs}` copies, not as package deps).
- DEAD (`activity-tools`, `edit-file`, `read-file-benchmark`, `skill`) and
  UNCERTAIN (`lsp-tool`, `peer-coordination-tools`, `think`) implementation
  files are quarantined and do not cross; the `implementations/` `.md` docs are
  excluded.
