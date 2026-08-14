# Hermes Agent -- CassiCore Integration

Single MCP bridge that gives Hermes access to CassiCore's Thalamus context curator, MnemicField memory, Constellation/Helix orchestration, and ModelDirective routing. Also reads Hermes' state.db directly for session enumeration.

## Quick Start

```bash
# 1. Install dependencies
cd /home/valerie/workspaces/cassicore/integrations/hermes-agent
npm install

# 2. Add to Hermes as an MCP server
hermes mcp add cassicore-hermes \
  --command npx \
  --args tsx /home/valerie/workspaces/cassicore/integrations/hermes-agent/src/server.ts

# 3. Install the lifecycle plugin
mkdir -p ~/.hermes/plugins/cassicore
cp plugin/* ~/.hermes/plugins/cassicore/

# 4. Install the context engine (optional -- for Thalamus-managed context)
mkdir -p ~/.hermes/hermes-agent/plugins/context_engine/cassicore
cp context_engine/* ~/.hermes/hermes-agent/plugins/context_engine/cassicore/
# Then set in config.yaml: context.engine: cassicore

# 5. Verify
hermes mcp list
# Expected: cassicore-hermes -- 24 tools
```

## Architecture

```
Hermes Agent
  |
  |-- Plugin: ~/.hermes/plugins/cassicore/*.py
  |     on_session_start -> POST /events/ingest + /cortex/signal
  |     on_session_end   -> POST /events/ingest
  |     post_tool_call   -> POST /events/ingest (tool:round-complete)
  |
  |-- MCP: cassicore-hermes (stdio, 24 tools)
  |     Reads: ~/.hermes/state.db (SQLite, direct)
  |     Calls: CassiCore daemon at http://localhost:7433
  |
  |-- Context Engine: plugins/context_engine/cassicore/
        compress(messages) -> POST /context/curate -> returns curated messages

CassiCore Daemon (port 7433)
  |-- Thalamus -- context scoring/compression/distillation
  |-- MnemicField -- persistent memory, cross-session patterns
  |-- Constellation -- multi-Helix tree orchestration
  |-- Helix -- three-posture collaborative sessions
  |-- ModelDirective -- tier-based provider routing
  |-- Cortex -- working memory signals
  |-- Lamina -- session-scoped context
```

## 24 Tools

### Session (read Hermes state.db directly)
| Tool | When to call |
|---|---|
| hermes_sessions_list | See what past sessions exist |
| hermes_session_get | Continue a prior conversation |
| hermes_session_search | Find where something was discussed |
| hermes_session_prune | Free disk space |
| hermes_session_resume | Bring a past session into CassiCore focus |
| hermes_session_active | Check what is currently running |

### Curation (Thalamus)
| Tool | When to call |
|---|---|
| hermes_context_curate | Before a long LLM call -- let Thalamus score/compress/distill |
| hermes_context_health | When context feels full -- check pressure |
| hermes_context_map | See what survived curation and why |
| hermes_context_why | Investigate why a message was dropped |
| hermes_context_pin | Protect critical context from being dropped |
| hermes_context_recall | Recover dropped information |

### Cognitive (MnemicField + Aurora)
| Tool | When to call |
|---|---|
| hermes_cognitive_enrich | Get CassiCore's full intelligence layer |
| hermes_memory_retrieve | Semantic search across past sessions |
| hermes_memory_store | Persist an important discovery |
| hermes_memory_graph | Explore memory relationships |
| hermes_self_model | Understand CassiCore architecture |

### Orchestration (Constellation + Helix)
| Tool | When to call |
|---|---|
| hermes_constellation_start | Large tasks -- spawn parallel Helix workers |
| hermes_constellation_watch | Wait for Constellation to finish |
| hermes_constellation_steer | Guide a running Constellation |
| hermes_helix_start | Focused tasks -- three equally capable agents collaborate |
| hermes_helix_watch | Wait for Helix to finish |

### Routing (ModelDirective)
| Tool | When to call |
|---|---|
| hermes_model_tier | Switch to cheap tier for background work |
| hermes_model_tiers | See available tiers and their model mappings |

## Config

The MCP server reads these environment variables:

- CASSICORE_URL -- CassiCore daemon URL (default: http://localhost:7433)
- HERMES_STATE_DB -- Path to Hermes state.db (default: ~/.hermes/state.db)

## Context Window Management

When the CassiCore context engine is active (context.engine: cassicore),
Hermes sends every compression-eligible turn's messages to the Thalamus:

1. Hermes builds the full message array
2. should_compress() returns true when tokens exceed 60% of context
3. compress() POSTs messages to /context/curate
4. Thalamus: scores (6-axis luminance), compresses tool results,
   distills large outputs, detects intent spans, assembles by threshold
5. Curated messages are returned to Hermes verbatim

This is the same curation pipeline that OpenCode uses.
