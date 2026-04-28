# CassiCore Integration for opencode

In-process plugin that connects opencode to the CassiCore daemon. Provides parity with the [claude-code integration](../claude-code/), but uses opencode's native plugin hooks instead of the three-process (proxy + hook server + MCP) setup that claude-code requires.

## Architecture

A single ES module loaded by opencode at startup. Communicates with the CassiCore daemon over the admin Unix socket (`~/.cassicore/admin.sock`) with a TCP fallback (`127.0.0.1:7433`).

```
┌──────────┐  experimental.chat.system.transform → Aurora narrative injection
│ opencode │  chat.message                       → user prompt → cortex/lamina/mnemic + Aurora observe
│          │  tool.execute.before/after          → tool tracking + round-complete pairing
│          │  session.turn.complete              → emit turn:end + token-based pressure
│          │  experimental.session.compacting    → checkpoint + handoff
│          │  session.compaction.complete        → recovery context (next turn)
│          │  event (session.*, message.*)       → lifecycle journalling
└────┬─────┘
     │ HTTP over Unix socket
┌────▼─────┐
│ CassiCore│  Aurora · Cortex · Mnemic Field · Lamina · Reverie · Helix journal
│  daemon  │  Memory · Blackboard · KV · Constellation · Knowledge Field
└──────────┘
```

CassiCore tools (`cassi_enrich`, `cassi_memory`, `cassi_agent`, etc.) are exposed via the existing CassiCore MCP gateway — configure that in opencode separately if you want tool access.

## Install

```bash
./install.sh
```

This symlinks `src/cassicore.mjs` into `~/.config/opencode/plugins/cassicore.mjs` and removes the legacy `cassicore-footprint.mjs` (the new plugin supersedes it). Re-run after pulling updates.

Then restart opencode and verify:

```bash
curl --unix-socket ~/.cassicore/admin.sock http://localhost/health
```

## Optional: MCP gateway for CassiCore tools

To give opencode access to the full CassiCore tool suite (cassi_memory, cassi_agent, etc.), add the existing gateway to your opencode `mcp` configuration. Example for `~/.config/opencode/opencode.json`:

```json
{
  "mcp": {
    "cassicore": {
      "type": "local",
      "command": ["npx", "tsx", "/home/valerie/workspaces/cassicore/mcp/cassicore-gateway.ts"]
    }
  }
}
```

This is the same gateway the claude-code integration uses — single source of truth for CassiCore tools across both editors.

## Parity Matrix

| Capability | claude-code mechanism | opencode plugin equivalent | Status |
|---|---|---|---|
| System prompt injection | API proxy rewrites prompt | `experimental.chat.system.transform` | ✓ |
| Aurora narrative shipped on every turn | Proxy injects `<aurora>` block | Same hook, same block | ✓ |
| Aurora seeded at session start | `auroraObserve` in SessionStart handler | `recordSessionStart` | ✓ |
| Aurora observes user prompts | Hook server UserPromptSubmit | `chat.message` | ✓ |
| Aurora observes assistant responses | Not in claude-code (no access) | `event: message.completed` | ✓ (better) |
| User prompt → cortex / lamina / mnemic / reverie | Hook server | `chat.message` | ✓ |
| Tool call recording | Hook server PreToolUse / PostToolUse | `tool.execute.before/after` | ✓ |
| Tool round-complete pairing | `emitToolRound` after PostToolUse | Same, in `recordToolResult` | ✓ |
| Canonical `turn:start` event | `emitTurnStart` | Same, in `recordUserPrompt` | ✓ |
| Canonical `turn:end` event | `emitTurnEnd` | Same, in `recordTurnComplete` | ✓ |
| Pressure-tier classification | Estimated from transcript size | Computed from real token counts | ✓ (more accurate) |
| Pressure warnings | Injected via additionalContext | Injected via `<cassicore-context>` block | ✓ |
| Pre-compaction checkpoint + handoff | `saveCheckpoint` + `kvSet` | Same in `recordPreCompact` | ✓ |
| Post-compaction recovery context | `buildRecoveryContext` injected on PostCompact | `meta.postCompaction` flag → next system transform | ✓ |
| Active file tracking | from `tool_input.file_path` | Same, from `output.args.filePath` | ✓ |
| Working state persistence | `kvSet("working-state:...")` | Same | ✓ |
| Session lifecycle (start/end/error) | Hook server | `event` hook | ✓ |
| Session anomaly tracking | n/a | `event: session.error` | ✓ (better) |
| Subagent journalling | Hook server SubagentStart / SubagentStop | `recordAgentStart/StopIfNeeded` via `agent` field | ✓ |
| Permission requests logged | n/a | `permission.ask` | ✓ (better) |
| Workspace context enrichment | `workspaceEnrich` on UserPromptSubmit | Same in `recordUserPrompt` | ✓ |
| Context indexing | `bridge.index` | `indexMessages` | ✓ |
| MCP tool suite | Configured via `~/.claude/settings.json` | Configured via `~/.config/opencode/opencode.json` mcp section | manual |

The opencode plugin gains three things claude-code doesn't have:

1. **Real token counts for pressure** — `session.turn.complete` provides actual `tokens.input/output` and `model.limit.context`, so pressure tiers reflect reality instead of a transcript-size heuristic.
2. **Assistant message observation** — `event: message.completed` gives us the assistant's response text. We feed it back into Aurora for next-turn cognitive state. claude-code has no equivalent because the hook server doesn't see assistant text.
3. **Permission request tracking** — `permission.ask` is an opencode-only hook that lets us log permission events as cortex anomalies.

## Files

```
integrations/opencode/
  src/
    cassicore.mjs    # The plugin (single ES module, no build step)
  install.sh         # Symlinks plugin into ~/.config/opencode/plugins/
  README.md          # This file
```

## Verification

After installing and restarting opencode, tail the CassiCore daemon log:

```bash
tail -f ~/.cassicore/daemon.log | grep -i opencode
```

You should see `session_start`, `user_message`, `tool_call_start`, `turn:start`, `turn:end` etc. as you use opencode.

Inspect Aurora's mental state:

```bash
curl --unix-socket ~/.cassicore/admin.sock http://localhost/intelligence/aurora/serialize | jq -r .context
```

This returns the same narrative that gets injected into opencode's system prompt.

## Troubleshooting

**Plugin not loading:** Make sure the symlink exists at `~/.config/opencode/plugins/cassicore.mjs` and that opencode's `opencode.json` doesn't explicitly exclude it. Restart opencode.

**No Aurora context appearing:** Check daemon health — `curl --unix-socket ~/.cassicore/admin.sock http://localhost/health`. The plugin silently no-ops when CassiCore is unreachable (this is intentional — opencode keeps working).

**Double-recorded events:** You probably have both `cassicore.mjs` and `cassicore-footprint.mjs` installed. Re-run `install.sh` — it removes the legacy file.

**High latency on first turn:** Aurora's narrative serialization is cached for 2 seconds and re-fetched on session start, user prompts, assistant messages, and post-compact. The first call after daemon startup may take ~500ms while Aurora builds its initial graph; subsequent calls are sub-100ms.
