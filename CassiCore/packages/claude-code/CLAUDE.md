# CassiCore Integration for Claude Code

CassiCore is a local AI daemon providing intelligence services: a parallel Thinker (persistent reasoning partner), dialectic analysis (Yang/Yin synthesis), subconscious pattern detection, persistent memory, shared blackboards, and multi-agent orchestration.

## Architecture

The integration has three components:

1. **Multi-Provider API Proxy** (port 7435) — intercepts Claude Code's API requests, routes them to the correct provider (z.ai, Anthropic direct, etc.) based on model name, injects CassiCore intelligence into the system prompt, and tracks token usage
2. **MCP Server** (stdio) — provides the full CassiCore tool suite (code intelligence, memory, blackboard, agents, etc.)
3. **Hook Server** (port 7434) — injects cognitive context into Claude Code's transcript on each turn

### Why three layers?

| Layer | What it controls | How |
|-------|-----------------|-----|
| API Proxy | What the **model** sees & **where** requests go | Rewrites the system prompt, routes to the correct provider based on model name |
| MCP Server | What **tools** are available | Exposes CassiCore's tools via MCP protocol |
| Hook Server | What **Claude Code** adds to the transcript | Returns `additionalContext` on each hook event |

The proxy gives us context modification — hooks can only add context, not modify or remove it.

## Multi-Provider Routing

The proxy dynamically routes API requests to different providers based on the requested model:

| Model Pattern | Provider | Description |
|---------------|----------|-------------|
| `claude-*` | Anthropic | All Claude models → Anthropic direct |
| `glm-*` | z.ai | All GLM models → z.ai gateway |
| `*` (default) | z.ai | Catch-all fallback |

### Route Resolution (Hybrid)

Routes are resolved with a 3-tier fallback:

1. **CassiCore daemon** — If the daemon is running, queries its `ModelDirective` for live tier→provider mappings. This means adding a new provider in CassiCore's config automatically updates the proxy.
2. **routes.json** — A `routes.json` file next to the proxy can define custom pattern→provider rules.
3. **Defaults** — `claude-*` → Anthropic, `glm-*` → z.ai, `*` → z.ai.

### Provider Configuration

Provider credentials are managed in `.env` (not in `~/.claude/settings.json`):

```env
Z_AI_API_KEY=your-z-ai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key  # optional
```

The proxy auto-migrates `~/.claude/settings.json` on startup to:
- Remove hardcoded `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_DEFAULT_*`, `API_TIMEOUT_MS`
- Set `ANTHROPIC_BASE_URL=http://localhost:7435` (pointing to the proxy)

### Circuit Breaker

If a provider fails 3 consecutive times, the circuit breaker opens and requests are routed to the next available provider. After 60 seconds, the circuit half-opens to allow a probe request.

## Available MCP Tools

The integration uses the main CassiCore MCP gateway, providing the full tool suite:

| Tool | Purpose |
|------|---------|
| `cassi_enrich` | Fetch cognitive signals, memories, and context on demand |
| `cassi_memory` | Search/store persistent memories, KV operations |
| `cassi_blackboard` | Read/write shared blackboards |
| `cassi_agent` | Launch Constellation multi-agent orchestration |
| `cassi_intelligence` | Introspect CassiCore modules |
| `cassi_session` | View active CassiCore sessions |
| `cassi_code` | Code intelligence — query, impact, dead code, hotspots |
| `cassi_file` | Filesystem operations |
| `cassi_browser` | Browser automation |
| `cassi_web` | Web search and fetch |
| `cassi_config` | Runtime configuration |
| `cassi_model` | Model/provider routing |
| `cassi_artifact` | File sharing and artifact versioning |
| `cassi_training` | Training data pipeline |

## When to Use Tools

- **Start of complex tasks**: Call `cassi_enrich` to get additional context
- **Multi-step work**: Post progress to `cassi_blackboard` as you go
- **Persistent knowledge**: Use `cassi_memory` across sessions
- **Large tasks**: Use `cassi_agent` to delegate parallel work
- **Code understanding**: Use `cassi_code` for impact analysis and knowledge graph queries

## Context Management

The API proxy monitors context by tracking actual token usage from API responses. The hook server provides complementary transcript-level pressure warnings.

When context pressure rises:

| Tier | What happens |
|------|-------------|
| warming (50-70%) | Cognitive signals switch to compact mode |
| elevated (70-78%) | Warning injected — consider consolidating |
| high (78-85%) | Warning to collapse old results |
| critical (85-92%) | Suggestion to delegate via Constellation |
| overflow (>92%) | Emergency delegation recommended |

At critical/overflow, save your progress to the blackboard and delegate remaining work:
```
cassi_blackboard({ action: "post", name: "session-handoff", channel: "artifacts", content: "..." })
cassi_agent({ type: "constellation", action: "project", goal: "Continue: <remaining work>" })
```

### Recovering compressed content

When tool results are large, the Thalamus may compress them using a reranker to keep only the most relevant chunks. If you need the full original content, use:

```
cassi_context({ action: "expand", tool_use_id: "toolu_abc123..." })
```

This returns the original uncompressed content from the session cache instantly (no LLM call).

## Blackboard Channels

- `findings` — analysis results, progress
- `concerns` — deferred issues
- `decisions` — choices and rationale
- `artifacts` — generated outputs
- `requests` — things needed from user
- `bugs` — defects found

## Setup

### 1. Start CassiCore daemon:
```bash
cd /home/valerie/workspaces/cassicore
./bin/cassicore boot start
```

### 2. Configure provider credentials:
```bash
cd /home/valerie/workspaces/cassicore/integrations/claude-code
cp .env.example .env
# Edit .env with your API keys (Z_AI_API_KEY, ANTHROPIC_API_KEY, etc.)
```

### 3. Start the API proxy:
```bash
cd /home/valerie/workspaces/cassicore/integrations/claude-code
npx tsx src/proxy.ts &
```
The proxy will automatically migrate `~/.claude/settings.json` to route through it.

### 4. Start the hook server:
```bash
cd /home/valerie/workspaces/cassicore/integrations/claude-code
npx tsx src/hook-server.ts &
```

### 5. Add MCP server to Claude Code settings (`~/.claude/settings.json`):
```json
{
  "mcpServers": {
    "cassicore": {
      "command": "npx",
      "args": ["tsx", "/home/valerie/workspaces/cassicore/mcp/cassicore-gateway.ts"]
    }
  }
}
```

### 6. Add hooks to project settings (`.claude/settings.json` in the project root):

The hooks use a command wrapper (`hook-command.cjs`) that forwards requests to the HTTP hook server. If the hook server isn't running, the wrapper returns `{}` silently — no errors shown to the user.

```json
{
  "hooks": {
    "SessionStart": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 5000 }]
    }],
    "UserPromptSubmit": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 5000 }]
    }],
    "PreToolUse": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 3000 }]
    }],
    "PostToolUse": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 3000 }]
    }],
    "PreCompact": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 10000 }]
    }],
    "PostCompact": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 5000 }]
    }],
    "Stop": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 3000 }]
    }],
    "SubagentStart": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 3000 }]
    }],
    "SubagentStop": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 3000 }]
    }],
    "SessionEnd": [{
      "hooks": [{ "type": "command", "command": "node /home/valerie/workspaces/cassicore/integrations/claude-code/src/hook-command.cjs", "timeout": 3000 }]
    }]
  }
}
```

## Verification

Check that all components are running:
```bash
# API Proxy health (shows provider status)
curl http://localhost:7435/health

# Provider details (health, circuit breaker, request counts)
curl http://localhost:7435/providers

# Routing table (model patterns → providers)
curl http://localhost:7435/providers/routes

# Hook server health
curl http://localhost:7434/health

# CassiCore daemon health
curl --unix-socket ~/.cassicore/admin.sock http://localhost/health
```
