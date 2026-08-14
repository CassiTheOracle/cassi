# `@cassicore/tools` — Mind / DELEGATE split manifest (P2)

**Phase:** CASSICORE-FOCUS §6 P2 (input to P3 spine + P4/P5 cutover).
**Source of truth:** `CASSICORE-FOCUS-PLAN.md` §5 verdict #20 (tools **SPLIT**),
§3.3 (mind-tool redundancy boundary), §4.2 (spine registers retained mind tools),
§6 P2/P3 rows; `packages/tools/src/ports/README.md` (P1 manifest — the retained
tool/model seam).

---

## Bottom line for P3/P4

- **MIND slice (retained):** the mind-tool handlers + the tool **TYPE** surface
  (`ToolExecutor`, `ToolRegistry`, `ToolDefinition`, `ToolExecutionContext`,
  `InteractiveToolSession`) survive. P3's spine re-registers the retained mind
  tools via `pi.registerTool`; the retained *type* imports make mind packages
  compile against a seam.
- **CODING slice (DELEGATE):** the coding/browser/background tools are ohmypi
  built-ins (shell, file I/O, web, tests, jobs). They stay wired by the host
  today (`registerCoreTools`); at P4/P5 ohmypi owns them and they die.
- **This phase:** this manifest only. No physical file moves, no behavior change
  (moves risk the shared `registerCoreTools` registration index; the manifest is
  the deliverable). `registerCoreTools` keeps its exact runtime behavior.

---

## 0. The retained type surface (survives P4/P5; where it lives, who imports)

| Symbol | Module | Consumers (today) |
|---|---|---|
| `ToolDefinition` (+ `ToolParamSchema`/`ToolParamProperty`/`ToolCategory`/`ToolCall`/`ToolResult`/`ToolHandler`) | `packages/tools/src/types.ts` (dist `types`) | helix, constellation, flux-team, mcp-gateway, admin-api, cognitive-feed, host (all import via `@cassicore/tools` barrel) |
| `ToolExecutionContext` | `packages/tools/src/types.ts` | every handler + helix/brainstem types (retained: `sessionId`, `workingDir`, `allowedPaths`, `networkAllowlist`, `logger`, `registry`, `_codeStore`, `_globalBlackboardRegistry`, `_cortex`, `_memory`, `artifactNamespace`, `sessionType`, `teamId`) |
| `ToolExecutor` (class) | `packages/tools/src/executor.ts` (barrel export) | host turn-pipeline, mcp, pipeline, providers |
| `ToolRegistry` (class, `ToolListOptions`) | `packages/tools/src/registry.ts` (barrel export) | host, helix, mcp, workflow, pipeline |
| `InteractiveToolSession` (+ `isPrompt`/`extractText`/`splitForTelegram`, `ParamSchema`/`PromptResult`/`ExecutionResult`/`SessionResult`) | `packages/tools/src/interactive-tool-session.ts` (barrel export) | `cognitive-feed` (runtime), `commands` |
| `CoreToolDeps` (the retained dep-injection seam) | `packages/tools/src/implementations/index.ts` | host daemon (`packages/host/src/daemon.ts:1889` `registerCoreTools(toolRegistry, {...})`) |

`executor.ts` also owns permission-oracle / trust-ledger / reliability / hooks —
the **safety/reliability** seam the retained mind tools rely on. At P4 it stays a
retained *runner* over whatever tool registry ohmypi exposes; the coding-tool
handlers it dispatches become ohmypi built-ins.

---

## 1. MIND slice — retained; spine re-registers at P3 (`pi.registerTool`)

> P3 needs the **registration function** the spine mirrors. Today ALL tools are
> registered by one function **`registerCoreTools(registry, deps)`** in
> `packages/tools/src/implementations/index.ts`
> (`CoreToolDeps` = the retained dep-injection seam). At P3, split the retained
> mind tools out into a **`registerMindTools(registry, mindDeps)`** that the
> spine mirrors exactly — registering ONLY the tools listed below. Do NOT change
> `registerCoreTools`' runtime behavior now; the split is a P3 spine-side concern.

Mind-tool handler dep wiring (the retained seam P3 must preserve):
| Dep group | Deps key on `CoreToolDeps` | Files |
|---|---|---|
| collect-thoughts | `collectThoughtsDeps` | `implementations/collect-thoughts.ts` |
| graph-discover | `setGraphDiscoverDeps` (runtime re-point by constellation-pipeline) | `implementations/graph-discover.ts` |
| cognitive (_reflect/_remember) | `cognitiveToolDeps` | `implementations/cognitive-tools.ts` |
| peer (_coordinate/_check_peers) | `peerToolDeps` | `implementations/peer-coordination.ts` |

Retained mind tools (name → file → registration today):
| Tool | File | Registered via |
|---|---|---|
| `collect_thoughts` | `implementations/collect-thoughts.ts` (`collectThoughtsDefinition`, `makeCollectThoughtsHandler`) | `deps.collectThoughtsDeps` (`§264`) |
| `graph_discover` | `implementations/graph-discover.ts` (`graphDiscoverDefinition`, `graphDiscoverHandler`) | `deps.cognitiveToolDeps` block (`§250`) |
| `_reflect` | `implementations/cognitive-tools.ts` (`reflectDefinition`, `makeReflectHandler`) | `deps.cognitiveToolDeps` (`§248`) |
| `_remember` | `implementations/cognitive-tools.ts` (`cognitiveRememberDefinition`, `makeCognitiveRememberHandler`) | `deps.cognitiveToolDeps` (`§249`) |
| `_coordinate` | `implementations/peer-coordination.ts` (`coordinateDefinition`, `makeCoordinateHandler`) | `deps.peerToolDeps` (`§257`) |
| `_check_peers` | `implementations/peer-coordination.ts` (`checkPeersDefinition`, `makeCheckPeersHandler`) | `deps.peerToolDeps` (`§258`) |
| `list_sessions` | inline in `implementations/index.ts` (`§163`) | always (inline def/handler; uses `deps.sessionManager`) |
| `list_subagents` | `implementations/list-subagents.ts` (`listSubagentsDefinition`, `makeListSubagentsHandler`) | `deps.subagentTracker`/thinker (`§209`) |
| `get_subagent_status` | `implementations/get-subagent-status.ts` | `deps.subagentTracker`/thinker |
| `get_subagent_result` | `implementations/get-subagent-result.ts` | `deps.subagentTracker`/thinker |
| `system_health` | `implementations/system-health.ts` (`systemHealthDefinition`, `makeSystemHealthHandler`) | always (`§283`) |
| `debug_session` | `implementations/debug-session.ts` | `deps.sessionManager`/`deps.memory` (`§292`) |
| `universal_search` | `implementations/universal-search.ts` | `deps.memory` (`§302`) |
| `cassandra_query_events` | `implementations/cassandra-event.ts` (`cassandraQueryEventsDef`, `makeCassandraQueryEventsHandler`) | `registerCassandraEventTools` (`§272`) |

**Test files (mind slice):** retained tests live under `packages/tools/tests/host-wired/`
(quarantined from the default run — they exercise the retained handlers):
`cognitive-tools.test.ts`, `collect-thoughts.test.ts`, `tool-executor.test.ts`,
`tool-presentation.test.ts`. Plus shared `tool-registry.test.ts` /
`interactive-tool-session.test.ts` (retained type surface).

**Redundancy note (P5):** per focus-plan §3.3/§7.5, `_reflect`/`_remember`/`remember`
merge into ohmypi memory built-ins over the shared MnemicField once the memory
backend lands, and are DELETED. Their registration seam (`cognitiveToolDeps`) is
kept until then.

---

## 2. DELEGATE slice — ohmypi replaces at P4/P5

Coding / browser / background tools that ohmypi owns natively
(shell, file I/O, web, test runner, jobs, workflow).

| Tool(s) | File(s) | Registered via (`registerCoreTools`) | ohmypi equivalent |
|---|---|---|---|
| `shell_exec` | `implementations/shell-exec.ts` (`shellExecDefinition`, `shellExecHandler`) | `§113` | ohmypi shell/bash built-in |
| `cassi_shell` | `implementations/cassi-shell.ts` (`cassiShellDefinition`, `cassiShellHandler`, `setCassiShellDeps`) | `§116` | ohmypi shell |
| `read_file` | `implementations/read-file.ts` (`readFileDefinition`, `readFileHandler`) | `§131` | ohmypi `read`/`read_file` |
| `read_files` | `implementations/read-files.ts` | `§132` | ohmypi read |
| `write_file` | `implementations/write-file.ts` (`writeFileDefinition`, `writeFileHandler`, `commitSessionChangeset`/`discardSessionChangeset`) | `§133` | ohmypi `write`/`edit` |
| `web_fetch` | `implementations/web-fetch.ts` | `§145` | ohmypi `web_search`/fetch |
| `web_search` | `implementations/web-search.ts` | `§146` | ohmypi `web_search` |
| `todo_write` | `implementations/todo-write.ts` | `§136` | ohmypi `todo_write` |
| `run_tests` | `implementations/run-tests.ts` (`runTestsDefinition`, `runTestsHandler`) | `§149` | ohmypi test runner |
| `vybit` (+ `vybit-loop`, `vybit-bug-ingest` deps) | `implementations/vybit.ts`, `vybit-loop.ts`, `vybit-bug-ingest.ts` | `§142` | browser-edit built-in |
| `desktop_vision` | `implementations/desktop-vision.ts` | `§139` | ohmypi desktop/vision |
| `run_background` / `check_job` / `wait_job` | `implementations/run-background.ts`, `check-job.ts`, `wait-job.ts` | `§152-156` (needs `deps.getJobManager`) | ohmypi `task`/`hub` background jobs (replaces `@cassicore/jobs` DELEGATE §25) |
| `workflow` | `implementations/workflow.ts` (`workflowDefinition`, `makeWorkflowHandler`) | `§313` (needs `deps.getWorkflowEngine`) | retained `@cassicore/workflow` engine, ohmypi can own scheduling |
| `scout` | `packages/tools/src/scout.ts` (`Scout`, `getScout`) | barrel (not a registered tool; a CLI/engine) | ohmypi scout/exploration |
| hermes tools | `packages/tools/src/hermes-tools.ts` (`HERMES_TOOL_DEFINITIONS`, `registerHermesTools`) | barrel; registered by host | ohmypi ecosystem (hermes bridges DELETED @ §36) |
| hermes MCP client | `packages/tools/src/hermes-mcp-client.ts` (`HermesMcpClient`, `getHermesMcpClient`, `shutdownHermesMcpClient`) | barrel; host wires | ohmypi MCP client |

**Test files (delegate slice):** `packages/tools/tests/host-wired/read-file-tool.test.ts`,
`read-file-tool-v2.test.ts` (file I/O), and the coding-tool portions exercised in
`tool-executor.test.ts`/`tool-presentation.test.ts`. None are in the default run
(host-wired); the coding-slice suites die at P4/P5 with their tools.

**External consumers (none import delegate impls by subpath — verified P2):**
`grep` for `implementations/{shell-exec,cassi-shell,read-file,read-files,write-file,
web-fetch,web-search,todo-write,run-tests,desktop-vision,run-background,check-job,
wait-job}` outside `packages/tools/src` → zero. Delegate tools are reached only via
`registerCoreTools`/the barrel's `implementations` re-export, then dispatched at
runtime by `ToolExecutor`. The retained TYPE surface that `host`/`pipeline`/
`providers`/`mcp` import (`ToolExecutor`, `ToolRegistry`, `ToolDefinition`,
`ToolExecutionContext`) is what keeps them compiling against the culled toolset.

---

## 3. What stays wired by the host today (do NOT break)

The 17 host tests and every retained mind suite depend on the **current**
`registerCoreTools` registering the FULL toolset (mind + coding). This phase
changes nothing at runtime: all 35 implementation files remain, `executor.ts`
resolves/executes them, and the barrel re-exports stay. The host's daemon
(`packages/host/src/daemon.ts`) and vendored intelligence modules keep importing
`@cassicore/tools` exactly as before.

Zero-import guard to preserve: no retained mind package may import a DELEGATE
tool module by path — retained packages import only `ToolExecutor`/`ToolRegistry`/
`ToolDefinition`/`ToolExecutionContext`/`InteractiveToolSession` (+ retained mind
handler types) from the barrel.

---

## 4. P3/P4 executor checklist

1. **P3 (spine):** define `registerMindTools(registry, mindDeps)` mirroring ONLY
   the §1 retained tools + retained type surface; spine calls it via
   `pi.registerTool`. `registerCoreTools` stays as-is until P4.
2. **P3 (memory):** wire `ctx.memory` (recall/retain/reflect/memory_edit) to the
   MnemicField backend; keep `collect_thoughts`/`graph_discover` (cognitive ops).
3. **P4/P5:** delete the §2 coding-tool files + their `host-wired` tests; keep the
   retained type surface so mind code still compiles. ohmypi built-ins cover the
   coding slice; `run_background`/`jobs` → ohmypi `task`/`hub`.
4. **P5:** delete `_reflect`/`_remember`/`remember`/`memory_search` after the
   memory backend lands (per §3.3 decision).

**Test impact (P2):** none — tools 39 still green; coding-slice suites untouched
(they stay quarantined in host-wired).
