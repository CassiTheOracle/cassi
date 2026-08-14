#!/usr/bin/env npx tsx
/**
 * CassiCore MCP Server for Claude Code
 *
 * Bridges Claude Code to CassiCore's intelligence layer via MCP protocol.
 * Provides tools for memory, blackboard, agent orchestration, intelligence
 * introspection, and proactive context management.
 *
 * Architecture:
 *   Claude Code <--stdio/MCP--> This Server <--HTTP--> CassiCore Daemon
 *
 * Session IDs are prefixed with "cc:" to distinguish from OpenCode sessions.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import * as bridge from "./bridge.js";



let currentSessionId = `cc:${Date.now().toString(36)}`;

function ccSessionId(id?: string): string {
  return id ?? currentSessionId;
}

let lastWorkingStatePost = 0;
const WORKING_STATE_COOLDOWN = 15_000;

async function postWorkingState(): Promise<void> {
  const now = Date.now();
  if (now - lastWorkingStatePost < WORKING_STATE_COOLDOWN) return;
  lastWorkingStatePost = now;

  const sid = ccSessionId();
  bridge.kvSet(`working-state:${sid}`, {
    sessionId: sid,
    timestamp: now,
    mode: "working",
    focusTopic: "",
    activeFiles: [],
    topConsumers: [],
    collapseCandidates: [],
    chunkCount: 0,
  });
}



const server = new McpServer({
  name: "cassicore",
  version: "0.1.0",
});



server.tool(
  "cassi_enrich",
  "Fetch enriched context from CassiCore: cognitive signals (thinker insights, dialectic analysis, subconscious patterns), relevant memories, and session history. Call this at the start of complex tasks to get CassiCore's intelligence layer working for you.",
  {
    query: z.string().optional().describe("Optional query to focus the enrichment on a specific topic"),
    include: z.enum(["all", "cognitive", "memory", "context"]).optional().describe("What to include (default: all)"),
  },
  async ({ query, include }) => {
    const sid = ccSessionId();
    const parts: string[] = [];
    const includeAll = !include || include === "all";

    // Cognitive signals
    if (includeAll || include === "cognitive") {
      const ctx = await bridge.fetchContext();
      if (ctx) {
        if (ctx.insight) parts.push(`## Thinker Insight\n${ctx.insight}`);
        if (ctx.learnings?.length) {
          parts.push(`## Subconscious Patterns\n${ctx.learnings.slice(0, 5).map(l =>
            `- **${l.clusterLabel}**: ${l.summary}${l.occurrences ? ` (${l.occurrences}x)` : ""}`
          ).join("\n")}`);
        }
        const dialectic = ctx.dialecticLatest?.[sid];
        if (dialectic?.hasSignal && dialectic.signal) {
          parts.push(`## Dialectic Signal\n**${dialectic.signal.type}** (${(dialectic.signal.confidence * 100).toFixed(0)}% confidence)\n${dialectic.signal.content}`);
        }
        if (ctx.anomalies?.length) {
          const recent = ctx.anomalies.filter(a => Date.now() - a.detectedAt < 300_000);
          if (recent.length) {
            parts.push(`## Active Anomalies\n${recent.map(a => `- **${a.type}** [${a.severity}]: ${a.summary}`).join("\n")}`);
          }
        }
        if (ctx.teams?.active?.length) {
          parts.push(`## Active Teams\n${ctx.teams.active.map(t =>
            `- **${t.name ?? t.id}** [${t.status}] ${t.progress?.pctComplete ?? "?"}% — ${t.goal}`
          ).join("\n")}`);
        }
      }

      // Direct cognitive injections
      const injections = await bridge.inject(sid);
      for (const signal of injections) {
        if (!parts.some(p => signal.length > 50 && p.includes(signal.slice(0, 50)))) {
          parts.push(signal);
        }
      }
    }

    // Memory search (MnemicField-powered)
    if ((includeAll || include === "memory") && query) {
      const hits = await bridge.mnemicRetrieve(query, 5);
      if (hits.length) {
        parts.push(`## Relevant Memories\n${hits.map((h: any) =>
          `- [${h.nodeType}] ${(h.content ?? '').slice(0, 300)}`
        ).join("\n")}`);
      }
    }

    if (parts.length === 0) return { content: [{ type: "text", text: "CassiCore has no signals to report. The daemon may not be running — check with `cassi_intelligence`." }] };

    postWorkingState().catch(() => {});
    return { content: [{ type: "text", text: parts.join("\n\n") }] };
  },
);



server.tool(
  "cassi_memory",
  "Memory operations backed by MnemicField — vector search, graph traversal, and persistent storage. Prefer 'retrieve' for semantic understanding; use 'search' for exact text matches.",
  {
    action: z.enum([
      "search", "store", "retrieve", "universal_search",
      "graph_search", "graph_traverse",
      "kv_get", "kv_set", "kv_del",
      "archive_get", "archive_search", "stats", "delete",
    ]).describe("Action to perform"),
    // Search / retrieve
    query: z.string().optional().describe("Search query"),
    limit: z.number().optional().describe("Max results (default: 10)"),
    nodeType: z.string().optional().describe("Filter by engram type: fact, episode, decision, pattern, outcome, etc."),
    // Store
    content: z.string().optional().describe("Content to store"),
    tags: z.array(z.string()).optional().describe("Tags for categorization"),
    key: z.string().optional().describe("Unique key/identifier"),
    // Graph
    engramId: z.string().optional().describe("Starting engram ID for graph traversal"),
    edgeType: z.string().optional().describe("Synapse edge type filter: spawned_from, part_of, supports, contradicts, etc."),
    direction: z.enum(["in", "out", "both"]).optional().describe("Traversal direction (default: both)"),
    maxDepth: z.number().optional().describe("Max graph hop depth (default: 3, max: 5)"),
    // KV
    value: z.string().optional().describe("KV value as JSON string (for kv_set)"),
    ttl: z.number().optional().describe("TTL in seconds (for kv_set)"),
    // Archive
    id: z.string().optional().describe("Memory/engram ID"),
    sessionId: z.string().optional().describe("Session ID for archive search"),
  },
  async ({ action, query, content, tags, key, value, ttl, limit,
           nodeType, engramId, edgeType, direction, maxDepth, id, sessionId }) => {
    switch (action) {
      // MnemicField retrieve (kindling — vector + semantic)
      case "retrieve": {
        if (!query) return { content: [{ type: "text", text: "Query required." }] };
        const hits = await bridge.mnemicRetrieve(query, limit ?? 10, { sessionId, nodeType });
        if (!hits.length) {
          // Fall back to text search
          const textHits = await bridge.mnemicSearch(query, limit ?? 10);
          if (!textHits.length) return { content: [{ type: "text", text: "No results found." }] };
          return { content: [{ type: "text", text: `Text matches for "${query}":\n${textHits.map((h: any, i: number) =>
            `[${i + 1}] ${h.nodeType} (${(h.score * 100).toFixed(0)}%) ${h.content.slice(0, 400)}`
          ).join('\n')}` }] };
        }
        return { content: [{ type: "text", text: `Results for "${query}":\n${hits.map((h: any, i: number) =>
          `[${i + 1}] ${h.nodeType} (${(h.score * 100).toFixed(0)}%)\n    ${h.content.slice(0, 400)}`
        ).join('\n')}` }] };
      }

      
      case "universal_search": {
        if (!query) return { content: [{ type: "text", text: "Query required." }] };
        const hits = await bridge.mnemicUniversalSearch(query, limit ?? 10);
        if (!hits.length) return { content: [{ type: "text", text: "No results found." }] };
        return { content: [{ type: "text", text: `[${hits.length}] results for "${query}":\n${hits.map((h: any, i: number) =>
          `[${i + 1}] ${h.nodeType} ${(h.score * 100).toFixed(0)}%\n    ${h.content.slice(0, 400)}`
        ).join('\n')}` }] };
      }

      
      case "search": {
        if (!query) return { content: [{ type: "text", text: "Query required." }] };
        // Try MnemicField search first, fall back to legacy memory
        try {
          const hits = await bridge.mnemicSearch(query, limit ?? 10, nodeType);
          if (hits.length) {
            return { content: [{ type: "text", text: `[${hits.length}] results for "${query}":\n${hits.map((h: any, i: number) =>
              `[${i + 1}] ${h.nodeType} ${(h.score * 100).toFixed(0)}%\n    ${h.content.slice(0, 400)}`
            ).join('\n')}` }] };
          }
        } catch { /* fall through */ }
        // Legacy fallback
        const results = await bridge.memorySearch(query, limit ?? 5);
        if (!results.length) return { content: [{ type: "text", text: "No memories found." }] };
        return { content: [{ type: "text", text: results.map((r: any) =>
          `- ${r.content ?? r.entry?.content ?? JSON.stringify(r)}`
        ).join("\n") }] };
      }

      
      case "store": {
        if (!content) return { content: [{ type: "text", text: "Content required." }] };
        if (key) {
          // Keyed storage: use KV with MnemicField metadata
          bridge.kvSet(key, { content, tags, storedAt: Date.now(), _mnemic: true });
          return { content: [{ type: "text", text: `Stored key: ${key}` }] };
        }
        // Use MnemicField-native store when available, fall back to legacy
        try {
          const id = await bridge.mnemicStore(content, nodeType ?? 'fact', tags);
          return { content: [{ type: "text", text: `Stored memory: ${id} (nodeType: ${nodeType ?? 'fact'})` }] };
        } catch {
          const id = await bridge.memoryStore(content, tags);
          return { content: [{ type: "text", text: `Stored memory: ${id}` }] };
        }
      }

      
      case "graph_search": {
        if (!engramId) return { content: [{ type: "text", text: "engramId required." }] };
        const result = await bridge.mnemicGraphSearch(engramId, {
          maxDepth: maxDepth ?? 3,
          edgeTypes: edgeType ? [edgeType] : undefined,
        });
        if (!result?.nodes?.length) return { content: [{ type: "text", text: `No graph neighbors found for ${engramId}.` }] };
        const lines = [`Graph from ${engramId} (${result.nodes.length} nodes, ${result.edges?.length ?? 0} edges, depth ${result.maxDepth}):`];
        for (const n of result.nodes) {
          lines.push(`  [d${n.depth}] ${n.nodeType}: ${n.content.slice(0, 200)}`);
        }
        return { content: [{ type: "text", text: lines.join('\n') }] };
      }

      
      case "graph_traverse": {
        if (!engramId) return { content: [{ type: "text", text: "engramId required." }] };
        const synapses = await bridge.mnemicGetSynapses(engramId, {
          edgeType, direction: direction ?? 'both', limit: limit ?? 20,
        });
        if (!synapses.length) return { content: [{ type: "text", text: `No synapses for ${engramId}.` }] };
        const lines = [`Synapses for ${engramId}:`];
        for (const s of synapses) {
          lines.push(`  ${s.edgeType}: ${s.sourceId.slice(0, 12)} → ${s.targetId.slice(0, 12)} (w:${s.weight?.toFixed(2) ?? '?'})`);
        }
        return { content: [{ type: "text", text: lines.join('\n') }] };
      }

      
      case "kv_get": {
        if (!key) return { content: [{ type: "text", text: "Key required." }] };
        const val = await bridge.kvGet(key);
        return { content: [{ type: "text", text: val ? JSON.stringify(val, null, 2) : "Key not found." }] };
      }
      case "kv_set": {
        if (!key) return { content: [{ type: "text", text: "Key required." }] };
        let parsed: unknown;
        try { parsed = value ? JSON.parse(value) : null; } catch { parsed = value; }
        const entry: any = { value: parsed };
        if (ttl) entry.ttl = ttl;
        bridge.kvSet(key, entry);
        return { content: [{ type: "text", text: `Set ${key}` }] };
      }
      case "kv_del": {
        if (!key) return { content: [{ type: "text", text: "Key required." }] };
        bridge.kvSet(key, null);  // daemon DELETE endpoint handles null = delete
        return { content: [{ type: "text", text: `Deleted ${key}` }] };
      }

      
      case "archive_get": {
        if (!id) return { content: [{ type: "text", text: "ID required." }] };
        try {
          const engram = await bridge.mnemicGetEngram(id);
          if (!engram || !engram.id) {
            return { content: [{ type: "text", text: `Not found: ${id}` }] };
          }
          const lines = [
            `Engram ${engram.id}:`,
            `  type: ${engram.nodeType}  potentiation: ${engram.potentiation ?? 0}`,
            `  tags: ${(engram.tags ?? []).join(', ') || '(none)'}`,
            `  provenance: ${engram.provenance ?? '(none)'}`,
            `  created: ${engram.createdAt ?? '(unknown)'}`,
            `  content: ${(engram.content ?? '').slice(0, 2000)}`,
          ];
          return { content: [{ type: "text", text: lines.join('\n') }] };
        } catch {
          return { content: [{ type: "text", text: `Not found: ${id}` }] };
        }
      }
      case "archive_search": {
        if (!query) return { content: [{ type: "text", text: "Query required." }] };
        const hits = await bridge.mnemicSearch(query, limit ?? 10);
        if (!hits.length) return { content: [{ type: "text", text: "No archive matches." }] };
        return { content: [{ type: "text", text: hits.map((h: any, i: number) =>
          `[${i + 1}] ${h.nodeType} ${h.id} (${(h.score * 100).toFixed(0)}%)\n    ${(h.content ?? '').slice(0, 300)}`
        ).join('\n') }] };
      }

      
      case "stats": {
        try {
          const stats = await bridge.mnemicStats();
          const lines = [`MnemicField: ${stats?.engramCount ?? '?'} engrams, ${stats?.synapseCount ?? '?'} synapses`];
          if (stats?.nucleiCount) lines.push(`  nuclei: ${stats.nucleiCount}`);
          if (stats?.avgPotentiation) lines.push(`  avg potentiation: ${stats.avgPotentiation.toFixed(3)}`);
          return { content: [{ type: "text", text: lines.join('\n') }] };
        } catch {
          return { content: [{ type: "text", text: "MnemicField stats unavailable." }] };
        }
      }

      
      case "delete": {
        if (!id) return { content: [{ type: "text", text: "ID required." }] };
        await bridge.send("DELETE", `/memory/${encodeURIComponent(id)}`);
        return { content: [{ type: "text", text: `Deleted ${id}` }] };
      }

      default:
        return { content: [{ type: "text", text: `Unknown action: ${action}` }] };
    }
  },
);



server.tool(
  "cassi_blackboard",
  "Read and write to CassiCore's shared blackboards. Blackboards are persistent shared memory spaces with channels (findings, concerns, decisions, artifacts, requests, bugs).",
  {
    action: z.enum(["read", "post", "search"]).describe("Action to perform"),
    name: z.string().describe("Board name (e.g., 'bugs', 'contributing-todos', 'session-handoff')"),
    channel: z.string().optional().describe("Channel: findings, concerns, decisions, artifacts, requests, bugs"),
    content: z.string().optional().describe("Content to post (for post action)"),
    tags: z.array(z.string()).optional().describe("Tags for the post"),
    priority: z.enum(["low", "medium", "high"]).optional().describe("Priority (default: medium)"),
    pattern: z.string().optional().describe("Search pattern (for search action)"),
  },
  async ({ action, name, channel, content, tags, priority, pattern }) => {
    switch (action) {
      case "read": {
        const result = await bridge.blackboardRead(name, channel);
        if (!result) return { content: [{ type: "text", text: `Board '${name}' not found or empty.` }] };
        return { content: [{ type: "text", text: typeof result === "string" ? result : JSON.stringify(result, null, 2) }] };
      }
      case "post": {
        if (!content || !channel) return { content: [{ type: "text", text: "Content and channel required for post." }] };
        await bridge.blackboardPost(name, content, channel, "claude-code", tags ?? [], priority ?? "medium");
        return { content: [{ type: "text", text: `Posted to ${name}/${channel}` }] };
      }
      case "search": {
        const result = await bridge.blackboardSearch(pattern ?? "");
        if (!result) return { content: [{ type: "text", text: "No results." }] };
        return { content: [{ type: "text", text: typeof result === "string" ? result : JSON.stringify(result, null, 2) }] };
      }
    }
  },
);



server.tool(
  "cassi_agent",
  "Launch and manage multi-agent work through CassiCore's Constellation orchestration. Use for complex multi-step tasks that benefit from parallel agent execution.",
  {
    type: z.enum(["constellation"]).describe("Agent type (constellation for multi-agent orchestration)"),
    action: z.enum(["project", "watch", "steer"]).describe("project: start new work, watch: check progress, steer: send guidance"),
    goal: z.string().optional().describe("Goal description (for project action)"),
    sessionId: z.string().optional().describe("Session ID to watch/steer"),
    message: z.string().optional().describe("Guidance message (for steer action)"),
    template: z.enum(["standard", "implementation", "research", "review", "minimal"]).optional().describe("Work template"),
  },
  async ({ type, action, goal, sessionId, message, template }) => {
    if (type !== "constellation") return { content: [{ type: "text", text: "Only constellation type is supported." }] };

    const params: Record<string, unknown> = {};
    if (goal) params.goal = goal;
    if (sessionId) params.sessionId = sessionId;
    if (message) params.message = message;
    if (template) params.template = template;

    const result = await bridge.agentConstellation(action, params);
    if (!result) return { content: [{ type: "text", text: "Agent operation failed. Is CassiCore running?" }] };
    return { content: [{ type: "text", text: typeof result === "string" ? result : JSON.stringify(result, null, 2) }] };
  },
);



server.tool(
  "cassi_intelligence",
  "Introspect CassiCore's intelligence modules: view active module status, token budgets, database schema, trust scores, and context effectiveness metrics.",
  {
    action: z.enum(["activity", "budget", "schema", "trust", "effectiveness"]).describe(
      "activity: module status, budget: token usage, schema: DB introspection, trust: tool reliability, effectiveness: context quality"
    ),
    path: z.string().optional().describe("Path filter for schema action"),
  },
  async ({ action, path }) => {
    const result = await bridge.intelligence(action, path ? { path } : undefined);
    if (!result) return { content: [{ type: "text", text: `Intelligence query failed for action '${action}'.` }] };
    return { content: [{ type: "text", text: typeof result === "string" ? result : JSON.stringify(result, null, 2) }] };
  },
);



server.tool(
  "cassi_session",
  "Manage CassiCore sessions. View active sessions and their status.",
  {
    action: z.enum(["list"]).describe("Action to perform"),
  },
  async ({ action }) => {
    if (action === "list") {
      const sessions = await bridge.sessionList();
      if (!sessions.length) return { content: [{ type: "text", text: "No active sessions." }] };
      return { content: [{ type: "text", text: sessions.map((s: any) =>
        `- **${s.id}** [${s.status}] turns: ${s.turnCount ?? "?"}, topic: ${s.topic ?? "unknown"}`
      ).join("\n") }] };
    }
    return { content: [{ type: "text", text: "Unknown action." }] };
  },
);



server.tool(
  "context_status",
  "Check the current context health and get recommendations. Since Claude Code doesn't expose direct context metrics, this uses CassiCore's working state and Thinker analysis to provide guidance.",
  {
    sessionId: z.string().optional().describe("Session ID (defaults to current)"),
  },
  async ({ sessionId }) => {
    const sid = ccSessionId(sessionId);
    const parts: string[] = [];

    // Read working state from KV
    const workingState = await bridge.kvGet(`working-state:${sid}`);
    if (workingState) {
      parts.push(`## Working State\n${JSON.stringify(workingState, null, 2)}`);
    }

    // Read any pending Thinker directives
    const directives = await bridge.kvGet(`context-directives:${sid}`);
    if (directives && (directives as any).timestamp) {
      const d = directives as any;
      parts.push(`## Thinker Directives\nReason: ${d.reason}\nCollapse: ${d.collapse?.join(", ") ?? "none"}\nRemove: ${d.remove?.join(", ") ?? "none"}\nPin: ${d.pin?.join(", ") ?? "none"}`);
    }

    // Read checkpoint
    const checkpoint = await bridge.kvGet(`checkpoint:${sid}`);
    if (checkpoint) {
      parts.push(`## Last Checkpoint\n${JSON.stringify(checkpoint, null, 2)}`);
    }

    // Read handoff (if any)
    const handoff = await bridge.kvGet(`handoff:${sid}`);
    if (handoff) {
      parts.push(`## Emergency Handoff\n${JSON.stringify(handoff, null, 2)}`);
    }

    if (parts.length === 0) return { content: [{ type: "text", text: "No context state available. The session may be new or CassiCore may not be tracking it." }] };
    return { content: [{ type: "text", text: parts.join("\n\n") }] };
  },
);



server.resource(
  "cognitive-signals",
  "cassicore://cognitive",
  async (uri) => {
    const ctx = await bridge.fetchContext();
    if (!ctx) return { contents: [{ uri: uri.href, text: "CassiCore unavailable.", mimeType: "text/plain" }] };

    const sid = ccSessionId();
    const parts: string[] = [];

    if (ctx.insight) parts.push(`Thinker: ${ctx.insight}`);
    if (ctx.learnings?.length) {
      parts.push(`Patterns: ${ctx.learnings.slice(0, 3).map(l => l.summary).join("; ")}`);
    }
    const d = ctx.dialecticLatest?.[sid];
    if (d?.hasSignal) parts.push(`Dialectic: ${d.signal?.type} (${(d.signal?.confidence * 100).toFixed(0)}%)`);

    return { contents: [{ uri: uri.href, text: parts.join("\n") || "No active signals.", mimeType: "text/plain" }] };
  },
);



server.resource(
  "context-health",
  "cassicore://health",
  async (uri) => {
    const sid = ccSessionId();
    const state = await bridge.kvGet(`working-state:${sid}`);
    const text = state ? JSON.stringify(state, null, 2) : "No health data available.";
    return { contents: [{ uri: uri.href, text, mimeType: "application/json" }] };
  },
);



async function main() {
  // Verify CassiCore is available
  const isUp = await bridge.available();
  if (!isUp) {
    console.error("Warning: CassiCore daemon is not available. Tools will fail gracefully.");
  }

  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => {
  console.error("Fatal:", err);
  process.exit(1);
});
