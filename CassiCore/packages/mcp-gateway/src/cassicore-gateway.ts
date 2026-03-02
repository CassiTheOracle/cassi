#!/usr/bin/env node
/**
 * CassiCore MCP Gateway Server
 * 
 * Exposes CassiCore's tools and capabilities via the Model Context Protocol (MCP).
 * This allows external AI systems (like Qwen-Coder) to use CassiCore's tool ecosystem.
 * 
 * Supports:
 * - stdio transport (for direct IDE integration)
 * - HTTP/SSE transport (for remote connections)
 * 
 * Usage:
 *   node mcp/cassicore-gateway.ts                    # stdio mode (default)
 *   node mcp/cassicore-gateway.ts --http --port 3000 # HTTP mode
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  ListResourcesRequestSchema,
  ReadResourceRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';
import http from 'http';
import { spawn } from 'child_process';

// Configuration
const CASSICORE_URL = process.env.CASSICORE_URL || 'http://localhost:7433';
const GATEWAY_VERSION = '1.0.0';

// Logger that writes to stderr (stdout reserved for MCP protocol)
function log(level: string, message: string, data?: any) {
  const timestamp = new Date().toISOString();
  const logLine = JSON.stringify({ timestamp, level, message, data });
  console.error(logLine);
}

/**
 * Tool definitions - mirror of CassiCore's tool registry
 */
const CASSICORE_TOOLS = [
  {
    name: 'bash',
    description: 'Execute bash commands with timeout and output capture. Use for file operations, running tests, git commands, etc.',
    inputSchema: {
      type: 'object',
      properties: {
        command: {
          type: 'string',
          description: 'The bash command to execute',
        },
        cwd: {
          type: 'string',
          description: 'Working directory for the command (optional, defaults to current)',
        },
        timeout: {
          type: 'number',
          description: 'Timeout in milliseconds (optional, default 30000, max 120000)',
        },
      },
      required: ['command'],
    },
  },
  {
    name: 'read',
    description: 'Read a file from the filesystem. Returns content, size, and metadata.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute or relative path to the file',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'write',
    description: 'Write content to a file. Creates parent directories if needed.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Absolute or relative path to write to',
        },
        content: {
          type: 'string',
          description: 'Content to write to the file',
        },
      },
      required: ['path', 'content'],
    },
  },
  {
    name: 'edit',
    description: 'Edit a file by replacing old text with new text. Fails if old text not found.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the file to edit',
        },
        oldText: {
          type: 'string',
          description: 'Exact text to replace (including whitespace)',
        },
        newText: {
          type: 'string',
          description: 'Replacement text',
        },
      },
      required: ['path', 'oldText', 'newText'],
    },
  },
  {
    name: 'mkdir',
    description: 'Create a directory (recursively if needed).',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to the directory to create',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'delete',
    description: 'Delete a file or directory (recursively).',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to delete',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'exists',
    description: 'Check if a file or directory exists. Returns existence and type.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Path to check',
        },
      },
      required: ['path'],
    },
  },
  {
    name: 'web_fetch',
    description: 'Fetch content from a URL. Returns text content with HTML stripped.',
    inputSchema: {
      type: 'object',
      properties: {
        url: {
          type: 'string',
          description: 'URL to fetch',
        },
        timeoutMs: {
          type: 'number',
          description: 'Timeout in milliseconds (optional, default 30000)',
        },
      },
      required: ['url'],
    },
  },
  {
    name: 'web_search',
    description: 'Search the web for information. Returns search results with titles and snippets.',
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description: 'Search query',
        },
        maxResults: {
          type: 'number',
          description: 'Maximum results to return (optional, default 5)',
        },
      },
      required: ['query'],
    },
  },
];

/**
 * Intelligence Activity Viewer tools — expose CassiCore's cognitive state
 */
const INTELLIGENCE_TOOLS = [
  {
    name: 'cassi_activity',
    description: 'Dashboard of all CassiCore cognitive modules — status, recent activity, injection counts, session health. Use this for a high-level overview of what the intelligence layer is doing.',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for a short narrative summary (default), "full" for a detailed dashboard with tables',
        },
      },
    },
  },
  {
    name: 'cassi_dialectic',
    description: 'View the Yang/Yin/Synthesizer dialectic analysis — recent turns, signal injection history, confidence scores, and synthesis outcomes. Shows how the dialectic trio processes each conversation turn.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to inspect (optional, defaults to most recent active session)',
        },
        limit: {
          type: 'number',
          description: 'Number of recent dialectic turns to show (default 5)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_thinker',
    description: 'View the Thinker module state — adaptive strategy parameters, insight history, ponder/think stats, Phase 3 trigger activity, and self-modification events.',
    inputSchema: {
      type: 'object',
      properties: {
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_subconscious',
    description: 'View the Subconscious module — mental model, consolidated learnings, detected anomalies, signal patterns, and context search stats. Shows what Cassi has internalized about the user and conversation.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to inspect (optional, defaults to most recent active session)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_trace',
    description: 'Forensic trace of a conversation turn — reconstructs what cognitive influences (optimizer, thinker, dialectic, subconscious, session digest) shaped a specific response. Use when asking "why did Cassi say that?"',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID to trace (optional, defaults to most recent active session)',
        },
        turnIndex: {
          type: 'number',
          description: 'Specific turn index to focus on (optional, shows most recent turns if omitted)',
        },
        limit: {
          type: 'number',
          description: 'Number of turns to include in context (default 5)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed forensic data',
        },
      },
    },
  },
  {
    name: 'cassi_effectiveness',
    description: 'Response quality metrics from implicit feedback signals — "Am I helping?" Shows outcome tracking, feedback detection, per-source quality scores, and per-tool reliability.',
    inputSchema: {
      type: 'object',
      properties: {
        sessionId: {
          type: 'string',
          description: 'Session ID for feedback lookup (optional, defaults to most recent active session)',
        },
        windowHours: {
          type: 'number',
          description: 'Time window in hours for source/tool stats (default 24)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed metrics',
        },
      },
    },
  },
  {
    name: 'cassi_budget',
    description: 'Token economy and provider usage — "Where does my attention go?" Shows request counts, error rates, per-provider/model aggregates, and hourly trends. No dollar cost calculation.',
    inputSchema: {
      type: 'object',
      properties: {
        providerId: {
          type: 'string',
          description: 'Filter by provider ID (e.g., "anthropic", "github-copilot")',
        },
        model: {
          type: 'string',
          description: 'Filter by model name',
        },
        hours: {
          type: 'number',
          description: 'Hours of hourly trend data to include (default 24)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed dashboard',
        },
      },
    },
  },
  {
    name: 'cassi_evolution',
    description: 'Self-modification timeline — "Am I changing?" Shows strategy snapshots over time, best strategies per module, dialectic effectiveness scores, and parameter evolution.',
    inputSchema: {
      type: 'object',
      properties: {
        module: {
          type: 'string',
          description: 'Intelligence module name to focus on (e.g., "thinker", "dialectic", "optimizer")',
        },
        limit: {
          type: 'number',
          description: 'Number of history entries to show (default 10)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed timeline',
        },
      },
    },
  },
  {
    name: 'cassi_blindspots',
    description: 'Cross-session pattern detection — "What am I systematically missing?" Shows recurring patterns across sessions, error correlations, and unresolved reflection patterns.',
    inputSchema: {
      type: 'object',
      properties: {
        category: {
          type: 'string',
          description: 'Filter patterns by category',
        },
        minConfidence: {
          type: 'number',
          description: 'Minimum confidence threshold (0-1, default 0)',
        },
        limit: {
          type: 'number',
          description: 'Maximum number of patterns to return (default 10)',
        },
        mode: {
          type: 'string',
          enum: ['brief', 'full'],
          description: 'Output mode: "brief" for narrative summary (default), "full" for detailed patterns',
        },
      },
    },
  },
];
const SERENA_TOOLS = [
  {
    name: 'serena__find_symbol',
    description: 'Find code symbols (functions, classes, variables) by name using semantic understanding.',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to find',
        },
      },
      required: ['symbolName'],
    },
  },
  {
    name: 'serena__read_symbol',
    description: 'Read detailed information about a symbol including its code and documentation.',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to read',
        },
      },
      required: ['symbolName'],
    },
  },
  {
    name: 'serena__find_referencing_symbols',
    description: 'Find all places where a symbol is used (references).',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to find references for',
        },
      },
      required: ['symbolName'],
    },
  },
  {
    name: 'serena__list_files',
    description: 'List files in the codebase with optional filtering.',
    inputSchema: {
      type: 'object',
      properties: {
        path: {
          type: 'string',
          description: 'Directory path to list (optional)',
        },
        pattern: {
          type: 'string',
          description: 'File pattern to match (optional, e.g., "*.ts")',
        },
      },
    },
  },
  {
    name: 'serena__replace_symbol_body',
    description: 'Replace the entire body of a symbol with new code.',
    inputSchema: {
      type: 'object',
      properties: {
        symbolName: {
          type: 'string',
          description: 'Name of the symbol to replace',
        },
        newBody: {
          type: 'string',
          description: 'New code body for the symbol',
        },
      },
      required: ['symbolName', 'newBody'],
    },
  },
];

/**
 * Execute a tool via CassiCore daemon
 */
async function executeCassiCoreTool(toolName: string, args: any): Promise<any> {
  log('info', 'Executing CassiCore tool', { tool: toolName, args });

  // Map tool names to CassiCore API endpoints
  const endpointMap: Record<string, string> = {
    bash: '/tools/bash',
    read: '/tools/read',
    write: '/tools/write',
    edit: '/tools/edit',
    mkdir: '/tools/mkdir',
    delete: '/tools/delete',
    exists: '/fs/exists',
    web_fetch: '/tools/web_fetch',
    web_search: '/tools/web_search',
  };

  const endpoint = endpointMap[toolName];
  if (!endpoint) {
    throw new Error(`Unknown tool: ${toolName}`);
  }

  const url = `${CASSICORE_URL}${endpoint}`;
  
  // Determine HTTP method based on tool
  const readTools = ['read', 'exists'];
  const method = readTools.includes(toolName) ? 'GET' : 'POST';

  try {
    let response;
    
    if (method === 'GET') {
      const queryParams = new URLSearchParams(args).toString();
      response = await fetch(`${url}?${queryParams}`, {
        method: 'GET',
      });
    } else {
      response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(args),
      });
    }

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`CassiCore error: ${error}`);
    }

    return await response.json();
  } catch (error: any) {
    log('error', 'Tool execution failed', { tool: toolName, error: error.message });
    throw error;
  }
}

/**
 * Execute Serena tool (if Serena MCP server is available)
 */
async function executeSerenaTool(toolName: string, args: any): Promise<any> {
  log('info', 'Executing Serena tool', { tool: toolName, args });
  
  // Serena has its own MCP server - this is a proxy
  // In practice, Qwen-Coder would connect directly to serena-server.js
  throw new Error('Serena tools should be accessed directly via serena-server.js MCP');
}

// ═══════════════════════════════════════════════════════════════════════════════
// Intelligence Tool Execution & Markdown Formatters
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * Helper to fetch JSON from an admin API endpoint
 */
async function fetchIntelligence(path: string, params?: Record<string, string>): Promise<any> {
  const url = new URL(path, CASSICORE_URL);
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null) url.searchParams.set(k, v);
    }
  }
  const response = await fetch(url.toString());
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Admin API error (${response.status}): ${text}`);
  }
  return response.json();
}

/**
 * Resolve the most recent active session ID
 */
async function resolveSessionId(sessionId?: string): Promise<string | undefined> {
  if (sessionId) return sessionId;
  try {
    const data = await fetchIntelligence('/sessions');
    const sessions = data?.sessions;
    if (Array.isArray(sessions) && sessions.length > 0) {
      const sorted = sessions.sort((a: any, b: any) => (b.lastActiveAt || 0) - (a.lastActiveAt || 0));
      return sorted[0]?.id;
    }
  } catch {
    // Sessions endpoint may not be available
  }
  return undefined;
}

/**
 * Format cassi_activity output
 */
async function formatActivity(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const data = await fetchIntelligence('/intelligence/activity');

  if (mode === 'brief') {
    const lines: string[] = ['## CassiCore Activity Brief\n'];
    
    const moduleCount = data.modules?.length || 0;
    lines.push(`**${moduleCount} modules active**`);

    // Thinker
    if (data.thinker?.stats) {
      const ts = data.thinker.stats;
      lines.push(`**Thinker**: ${ts.totalInsights || 0} insights generated, ${ts.turnsProcessed || 0} turns processed`);
    }

    // Dialectic
    if (data.dialectic) {
      const d = data.dialectic;
      lines.push(`**Dialectic**: ${d.totalTurns || 0} turns analyzed, ${d.signalsInjected || 0} signals injected (avg confidence: ${(d.avgConfidence || 0).toFixed(2)})`);
    }

    // Archive
    if (data.archive) {
      lines.push(`**Archive**: ${data.archive.totalEntries || 0} entries (${Object.keys(data.archive.byType || {}).length} types)`);
    }

    // Memory
    if (data.memory) {
      const totalMem = Object.values(data.memory).reduce((sum: number, v: any) => sum + (typeof v === 'number' ? v : 0), 0);
      lines.push(`**Memory**: ${totalMem} items stored`);
    }

    // Reflect
    if (data.reflect?.unresolvedPatterns?.length) {
      lines.push(`**Reflect**: ${data.reflect.unresolvedPatterns.length} unresolved patterns`);
    }

    // Optimizer
    const healthKeys = Object.keys(data.optimizer?.sessionHealth || {});
    if (healthKeys.length > 0) {
      lines.push(`**Optimizer**: tracking ${healthKeys.length} session(s)`);
    }

    // AI Scientist
    if (data.aiScientist?.recentStudies?.length) {
      lines.push(`**AI Scientist**: ${data.aiScientist.recentStudies.length} recent studies`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## CassiCore Activity Dashboard\n'];
  
  // Module table
  lines.push('### Modules\n');
  lines.push('| Module | Priority | Status |');
  lines.push('|--------|----------|--------|');
  for (const m of (data.modules || [])) {
    lines.push(`| ${m.name} | ${m.priority} | ${m.status} |`);
  }

  // Thinker section
  if (data.thinker?.stats) {
    lines.push('\n### Thinker\n');
    const ts = data.thinker.stats;
    for (const [k, v] of Object.entries(ts)) {
      lines.push(`- **${k}**: ${v}`);
    }
    if (data.thinker.strategy) {
      lines.push('\n**Current Strategy**:');
      lines.push('```json');
      lines.push(JSON.stringify(data.thinker.strategy, null, 2));
      lines.push('```');
    }
  }

  // Dialectic section
  if (data.dialectic) {
    lines.push('\n### Dialectic (Most Recent Session)\n');
    for (const [k, v] of Object.entries(data.dialectic)) {
      lines.push(`- **${k}**: ${typeof v === 'number' ? (Number.isInteger(v) ? v : (v as number).toFixed(3)) : v}`);
    }
  }

  // Archive section
  if (data.archive) {
    lines.push('\n### Archive\n');
    lines.push(`- **Total entries**: ${data.archive.totalEntries || 0}`);
    lines.push(`- **Avg importance**: ${(data.archive.avgImportance || 0).toFixed(3)}`);
    lines.push(`- **Thinking blocks**: ${data.archive.thinkingBlocksCount || 0}`);
    lines.push(`- **Linked entries**: ${data.archive.linkedEntriesCount || 0}`);
    if (data.archive.byType) {
      lines.push('\n**By Type**:');
      for (const [type, count] of Object.entries(data.archive.byType)) {
        lines.push(`  - ${type}: ${count}`);
      }
    }
  }

  // Reflect section
  if (data.reflect?.unresolvedPatterns?.length) {
    lines.push('\n### Reflect — Unresolved Patterns\n');
    for (const p of data.reflect.unresolvedPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}**: ${p.occurrences || 1} occurrences`);
    }
  }

  // Optimizer section
  if (Object.keys(data.optimizer?.sessionHealth || {}).length > 0) {
    lines.push('\n### Optimizer — Session Health\n');
    lines.push('| Session | Health Score | Status |');
    lines.push('|---------|-------------|--------|');
    for (const [sid, health] of Object.entries(data.optimizer.sessionHealth)) {
      const h = health as any;
      lines.push(`| ${sid.slice(0, 12)}... | ${h.score?.toFixed(2) ?? 'N/A'} | ${h.status ?? 'unknown'} |`);
    }
  }

  // AI Scientist section
  if (data.aiScientist?.recentStudies?.length) {
    lines.push('\n### AI Scientist — Recent Studies\n');
    for (const study of data.aiScientist.recentStudies) {
      lines.push(`- **${study.title || 'Untitled'}** (confidence: ${(study.confidence || 0).toFixed(2)})`);
      if (study.conclusions) lines.push(`  ${study.conclusions.slice(0, 150)}${study.conclusions.length > 150 ? '...' : ''}`);
    }
  }

  // Memory section
  if (data.memory) {
    lines.push('\n### Memory\n');
    for (const [k, v] of Object.entries(data.memory)) {
      lines.push(`- **${k}**: ${v}`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_dialectic output
 */
async function formatDialectic(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const limit = args?.limit || 5;
  const sessionId = await resolveSessionId(args?.sessionId);

  if (!sessionId) {
    return '## Dialectic\n\nNo active session found. Provide a `sessionId` parameter or start a conversation first.';
  }

  const [historyData, statsData] = await Promise.all([
    fetchIntelligence(`/dialectic/${sessionId}/history`, { limit: String(limit) }),
    fetchIntelligence(`/dialectic/${sessionId}/stats`).catch(() => null),
  ]);

  const history = historyData?.history || historyData?.turns || historyData || [];
  const stats = statsData?.stats || statsData;

  if (mode === 'brief') {
    const lines: string[] = [`## Dialectic Brief (session: ${sessionId.slice(0, 12)}...)\n`];

    if (stats) {
      lines.push(`**${stats.totalTurns || 0}** turns analyzed | **${stats.signalsInjected || 0}** signals injected | avg confidence: **${(stats.avgConfidence || 0).toFixed(2)}**`);
    }

    const recent = Array.isArray(history) ? history.slice(0, 3) : [];
    if (recent.length > 0) {
      lines.push('\n**Recent Analysis**:');
      for (const turn of recent) {
        const yang = turn.yang_output || turn.yangOutput;
        const synth = turn.synthesizer_output || turn.synthesizerOutput;
        const injected = turn.signal_injected ?? turn.signalInjected;
        const yangSummary = typeof yang === 'string' ? yang.slice(0, 80) : (yang?.observation || yang?.summary || JSON.stringify(yang)).slice(0, 80);
        lines.push(`- ${injected ? '[INJECTED]' : '[observed]'} ${yangSummary}${yangSummary.length >= 80 ? '...' : ''}`);
      }
    } else {
      lines.push('\nNo dialectic turns recorded for this session yet.');
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = [`## Dialectic Dashboard (session: ${sessionId.slice(0, 12)}...)\n`];

  // Stats table
  if (stats) {
    lines.push('### Statistics\n');
    for (const [k, v] of Object.entries(stats)) {
      lines.push(`- **${k}**: ${typeof v === 'number' ? (Number.isInteger(v) ? v : (v as number).toFixed(3)) : v}`);
    }
  }

  // Turn history
  const turns = Array.isArray(history) ? history : [];
  if (turns.length > 0) {
    lines.push(`\n### Recent Turns (${turns.length})\n`);
    for (let i = 0; i < turns.length; i++) {
      const turn = turns[i];
      const yang = turn.yang_output || turn.yangOutput;
      const yin = turn.yin_output || turn.yinOutput;
      const synth = turn.synthesizer_output || turn.synthesizerOutput;
      const injected = turn.signal_injected ?? turn.signalInjected;
      const latency = turn.total_latency_ms ?? turn.totalLatencyMs;

      lines.push(`#### Turn ${i + 1} ${injected ? '(SIGNAL INJECTED)' : ''}`);
      if (latency) lines.push(`*Latency: ${latency}ms*\n`);

      // Yang
      lines.push('**Yang (Creative Observer)**:');
      if (typeof yang === 'object' && yang !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(yang, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${yang || 'N/A'}`);
      }

      // Yin
      lines.push('\n**Yin (Critical Analyst)**:');
      if (typeof yin === 'object' && yin !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(yin, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${yin || 'N/A'}`);
      }

      // Synthesizer
      lines.push('\n**Synthesizer (Serenity)**:');
      if (typeof synth === 'object' && synth !== null) {
        lines.push('```json');
        lines.push(JSON.stringify(synth, null, 2));
        lines.push('```');
      } else {
        lines.push(`> ${synth || 'N/A'}`);
      }
      lines.push('');
    }
  } else {
    lines.push('\nNo dialectic turns recorded for this session.');
  }

  return lines.join('\n');
}

/**
 * Format cassi_thinker output
 */
async function formatThinker(args: any): Promise<string> {
  const mode = args?.mode || 'brief';

  const [statsData, strategyData, insightData] = await Promise.all([
    fetchIntelligence('/intelligence/thinker/stats').catch(() => null),
    fetchIntelligence('/intelligence/thinker/strategy').catch(() => null),
    fetchIntelligence('/intelligence/thinker/insight-history').catch(() => null),
  ]);

  const stats = statsData?.stats || statsData;
  const strategy = strategyData?.strategy || strategyData;
  const insights = insightData?.history || insightData?.insights || insightData;

  if (mode === 'brief') {
    const lines: string[] = ['## Thinker Brief\n'];

    if (stats) {
      lines.push(`**${stats.totalInsights || stats.insightCount || 0}** insights | **${stats.turnsProcessed || stats.turnCount || 0}** turns processed | enabled: **${stats.enabled ?? 'unknown'}**`);
    } else {
      lines.push('*Thinker stats not available*');
    }

    if (strategy) {
      const s = typeof strategy === 'string' ? JSON.parse(strategy) : strategy;
      lines.push(`\n**Strategy**: ponder interval ${s.ponderIntervalMs || s.ponderInterval || 'default'}ms, trigger sensitivity ${(s.triggerSensitivity || 0).toFixed(2)}`);
    }

    if (Array.isArray(insights) && insights.length > 0) {
      lines.push(`\n**Latest Insight** (${new Date(insights[0].timestamp || insights[0].createdAt || Date.now()).toLocaleString()}):`);
      const content = insights[0].content || insights[0].insight || JSON.stringify(insights[0]);
      lines.push(`> ${content.slice(0, 200)}${content.length > 200 ? '...' : ''}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Thinker Dashboard\n'];

  // Stats
  if (stats) {
    lines.push('### Runtime Stats\n');
    for (const [k, v] of Object.entries(stats)) {
      lines.push(`- **${k}**: ${v}`);
    }
  }

  // Strategy
  if (strategy) {
    lines.push('\n### Adaptive Strategy\n');
    const s = typeof strategy === 'string' ? JSON.parse(strategy) : strategy;
    lines.push('```json');
    lines.push(JSON.stringify(s, null, 2));
    lines.push('```');
  }

  // Insight History
  if (Array.isArray(insights) && insights.length > 0) {
    lines.push(`\n### Insight History (${insights.length} entries)\n`);
    for (const insight of insights.slice(0, 10)) {
      const content = insight.content || insight.insight || JSON.stringify(insight);
      const ts = insight.timestamp || insight.createdAt;
      const feedback = insight.feedbackScore ?? insight.feedback;
      lines.push(`#### ${ts ? new Date(ts).toLocaleString() : 'Unknown time'} ${feedback !== undefined ? `(feedback: ${feedback})` : ''}`);
      lines.push(`${content}\n`);
    }
  } else {
    lines.push('\n*No insight history available.*');
  }

  return lines.join('\n');
}

/**
 * Format cassi_subconscious output
 */
async function formatSubconscious(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(args?.sessionId);

  const params: Record<string, string> = {};
  if (sessionId) params.sessionId = sessionId;

  const [debugData, learningsData, statsData, anomaliesData] = await Promise.all([
    fetchIntelligence('/intelligence/subconscious/debug', params).catch(() => null),
    fetchIntelligence('/intelligence/subconscious/learnings').catch(() => null),
    fetchIntelligence('/intelligence/subconscious/stats').catch(() => null),
    fetchIntelligence('/intelligence/subconscious/anomalies').catch(() => null),
  ]);

  const debug = debugData;
  const learnings = learningsData?.learnings || learningsData;
  const stats = statsData?.stats || statsData;
  const anomalies = anomaliesData?.anomalies || anomaliesData;

  if (mode === 'brief') {
    const lines: string[] = ['## Subconscious Brief\n'];

    if (stats) {
      lines.push(`**${stats.totalLearnings || 0}** learnings | **${stats.totalAnomalies || 0}** anomalies | **${stats.totalPatterns || 0}** patterns | avg confidence: **${(stats.avgConfidence || 0).toFixed(2)}**`);
    }

    // Mental model summary from debug
    if (debug?.mentalModel) {
      const model = debug.mentalModel;
      lines.push(`\n**Mental Model**: phase=${model.conversationPhase || 'unknown'}, intent=${model.userIntent || 'unknown'}, complexity=${model.complexity || 'unknown'}`);
    }

    // Recent signals
    if (debug?.recentSignals?.length) {
      lines.push(`\n**Recent Signals** (${debug.recentSignals.length}):`);
      for (const sig of debug.recentSignals.slice(0, 3)) {
        lines.push(`- [${sig.type || 'signal'}] ${(sig.description || sig.content || JSON.stringify(sig)).slice(0, 100)}`);
      }
    }

    // Anomalies summary
    if (Array.isArray(anomalies) && anomalies.length > 0) {
      const unacked = anomalies.filter((a: any) => !a.acknowledged);
      if (unacked.length > 0) {
        lines.push(`\n**${unacked.length} unacknowledged anomalies** detected`);
      }
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = [`## Subconscious Dashboard${sessionId ? ` (session: ${sessionId.slice(0, 12)}...)` : ''}\n`];

  // Stats
  if (stats) {
    lines.push('### Statistics\n');
    for (const [k, v] of Object.entries(stats)) {
      lines.push(`- **${k}**: ${typeof v === 'number' ? (Number.isInteger(v) ? v : (v as number).toFixed(3)) : v}`);
    }
  }

  // Mental Model
  if (debug?.mentalModel) {
    lines.push('\n### Mental Model\n');
    lines.push('```json');
    lines.push(JSON.stringify(debug.mentalModel, null, 2));
    lines.push('```');
  }

  // Context
  if (debug?.context) {
    lines.push('\n### Current Context\n');
    lines.push('```json');
    lines.push(JSON.stringify(debug.context, null, 2));
    lines.push('```');
  }

  // Recent Signals
  if (debug?.recentSignals?.length) {
    lines.push(`\n### Recent Signals (${debug.recentSignals.length})\n`);
    for (const sig of debug.recentSignals) {
      lines.push(`- **[${sig.type || 'signal'}]** ${sig.description || sig.content || JSON.stringify(sig)}`);
    }
  }

  // Learnings
  if (Array.isArray(learnings) && learnings.length > 0) {
    lines.push(`\n### Consolidated Learnings (${learnings.length})\n`);
    for (const learning of learnings.slice(0, 20)) {
      if (typeof learning === 'string') {
        lines.push(`- ${learning}`);
      } else {
        lines.push(`- **${learning.category || 'general'}**: ${learning.content || learning.description || JSON.stringify(learning)}`);
      }
    }
  }

  // Anomalies
  if (Array.isArray(anomalies) && anomalies.length > 0) {
    lines.push(`\n### Anomalies (${anomalies.length})\n`);
    lines.push('| ID | Type | Description | Acknowledged |');
    lines.push('|----|------|-------------|-------------|');
    for (const a of anomalies) {
      lines.push(`| ${(a.id || '?').slice(0, 8)} | ${a.type || '?'} | ${(a.description || '').slice(0, 60)} | ${a.acknowledged ? 'Yes' : 'No'} |`);
    }
  }

  // Enhanced Search Stats (if present in debug)
  if (debug?.searchStats || debug?.stats) {
    lines.push('\n### Search Stats\n');
    const ss = debug.searchStats || debug.stats;
    for (const [k, v] of Object.entries(ss)) {
      lines.push(`- **${k}**: ${v}`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_trace output — forensic turn reconstruction
 */
async function formatTrace(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(args?.sessionId);
  if (!sessionId) {
    return '## Trace\n\nNo active session found. Provide a sessionId parameter.';
  }

  const params: Record<string, string> = { sessionId };
  if (args?.turnIndex !== undefined) params.turnIndex = String(args.turnIndex);
  if (args?.limit) params.limit = String(args.limit);

  const data = await fetchIntelligence('/intelligence/trace', params);

  if (mode === 'brief') {
    const lines: string[] = ['## Turn Trace (Brief)\n'];
    lines.push(`**Session**: \`${sessionId.slice(0, 12)}...\`\n`);

    // Continuity — recent turns
    const turns = data.continuity?.turns || [];
    if (turns.length > 0) {
      const latest = turns[turns.length - 1];
      lines.push(`**Latest turn**: ${latest.role} at ${new Date(latest.timestamp).toLocaleTimeString()} (${latest.content?.slice(0, 80)}...)`);
      lines.push(`**Turn context**: ${turns.length} turn(s) in window`);
    } else {
      lines.push('**No turn data** available for this session');
    }

    // Injections
    const injections = data.injections || [];
    if (injections.length > 0) {
      const sources = [...new Set(injections.map((i: any) => i.metadata?.source || i.category || 'unknown'))];
      lines.push(`**Injections**: ${injections.length} from ${sources.join(', ')}`);
    } else {
      lines.push('**Injections**: none recorded (ledger may not have been active)');
    }

    // Dialectic
    if (data.dialectic && data.dialectic.length > 0) {
      const latest = data.dialectic[data.dialectic.length - 1];
      lines.push(`**Dialectic**: last analysis at ${new Date(latest.timestamp || latest.created_at).toLocaleTimeString()} — ${latest.synthesis?.slice(0, 100) || 'no synthesis'}...`);
    }

    // Reflect patterns
    if (data.reflectPatterns?.length) {
      lines.push(`**Active patterns**: ${data.reflectPatterns.length} unresolved reflection pattern(s) may have influenced response`);
    }

    // Mental model
    if (data.mentalModel) {
      lines.push(`**Mental model**: active for this session`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Turn Trace (Full Forensic)\n'];
  lines.push(`**Session**: \`${sessionId}\`  `);
  lines.push(`**Timestamp**: ${new Date(data.timestamp).toISOString()}\n`);

  // Continuity turns
  const turns = data.continuity?.turns || [];
  if (turns.length > 0) {
    lines.push('### Conversation Context\n');
    lines.push(`Total turns in window: ${data.continuity?.totalTurns || turns.length}\n`);
    lines.push('| # | Role | Time | Content (preview) |');
    lines.push('|---|------|------|--------------------|');
    turns.forEach((t: any, i: number) => {
      const time = new Date(t.timestamp).toLocaleTimeString();
      const preview = (t.content || '').replace(/\|/g, '\\|').slice(0, 60);
      lines.push(`| ${i} | ${t.role} | ${time} | ${preview}... |`);
    });
  }

  // Injection ledger
  const injections = data.injections || [];
  if (injections.length > 0) {
    lines.push('\n### Injection Ledger\n');
    lines.push('| Source | Time | Content (preview) |');
    lines.push('|--------|------|--------------------|');
    for (const inj of injections) {
      const source = inj.metadata?.source || inj.category || 'unknown';
      const time = inj.metadata?.turnTimestamp ? new Date(inj.metadata.turnTimestamp).toLocaleTimeString() : 'N/A';
      const preview = (inj.content || '').replace(/\|/g, '\\|').slice(0, 80);
      lines.push(`| ${source} | ${time} | ${preview}... |`);
    }
  } else {
    lines.push('\n### Injection Ledger\n');
    lines.push('No injection records found. The injection ledger persists entries from optimizer, thinker, dialectic, subconscious, and session digest modules.');
  }

  // Dialectic analysis
  if (data.dialectic && data.dialectic.length > 0) {
    lines.push('\n### Dialectic Analysis\n');
    for (const d of data.dialectic) {
      lines.push(`**Turn** at ${new Date(d.timestamp || d.created_at).toLocaleTimeString()}:`);
      if (d.yang) lines.push(`- **Yang**: ${d.yang.slice(0, 150)}...`);
      if (d.yin) lines.push(`- **Yin**: ${d.yin.slice(0, 150)}...`);
      if (d.synthesis) lines.push(`- **Synthesis**: ${d.synthesis.slice(0, 150)}...`);
      if (d.confidence !== undefined) lines.push(`- **Confidence**: ${(d.confidence * 100).toFixed(0)}%`);
      lines.push('');
    }
  }

  // Reflect patterns
  if (data.reflectPatterns?.length) {
    lines.push('\n### Active Reflection Patterns\n');
    for (const p of data.reflectPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}** (${p.occurrences || 1}x): ${p.description || p.evidence || 'no description'}`);
    }
  }

  // Archive context
  if (data.archiveContext?.length) {
    lines.push('\n### Archive Context\n');
    for (const a of data.archiveContext) {
      lines.push(`- [${a.type}] ${(a.content || '').slice(0, 120)}...`);
    }
  }

  // Mental model
  if (data.mentalModel) {
    lines.push('\n### Mental Model State\n');
    lines.push('```json');
    lines.push(JSON.stringify(data.mentalModel, null, 2).slice(0, 500));
    lines.push('```');
  }

  return lines.join('\n');
}

/**
 * Format cassi_effectiveness output — outcome tracking metrics
 */
async function formatEffectiveness(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const sessionId = await resolveSessionId(args?.sessionId);
  const windowMs = ((args?.windowHours || 24) * 60 * 60_000).toString();

  const [statsData, feedbackData] = await Promise.all([
    fetchIntelligence('/intelligence/outcomes/stats').catch(() => null),
    sessionId
      ? fetchIntelligence('/intelligence/outcomes/feedback', { sessionId, limit: '10' }).catch(() => null)
      : Promise.resolve(null),
  ]);

  const stats = statsData || {};
  const feedback = feedbackData?.feedback || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Effectiveness Brief\n'];

    if (!statsData) {
      lines.push('OutcomeTracker not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Total feedback detected**: ${stats.totalFeedbackDetected || 0}`);
    lines.push(`**Outcomes recorded**: ${stats.totalOutcomesRecorded || 0} insights, ${stats.totalToolOutcomesRecorded || 0} tools`);
    lines.push(`**Sessions tracked**: ${stats.trackedSessions || 0}`);
    lines.push(`**Pending**: ${stats.pendingFeedback || 0} feedback, ${stats.pendingToolOutcomes || 0} tool outcomes`);

    if (feedback.length > 0) {
      const positive = feedback.filter((f: any) => f.sentiment === 'positive' || f.score > 0).length;
      const negative = feedback.filter((f: any) => f.sentiment === 'negative' || f.score < 0).length;
      lines.push(`\n**Recent feedback** (${sessionId?.slice(0, 12)}...): ${positive} positive, ${negative} negative out of ${feedback.length}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Effectiveness Dashboard\n'];

  // Stats overview
  lines.push('### Aggregate Stats\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  // Recent feedback
  if (feedback.length > 0) {
    lines.push(`\n### Recent Feedback (${sessionId?.slice(0, 12)}...)\n`);
    lines.push('| Sentiment | Score | Signal | Timestamp |');
    lines.push('|-----------|-------|--------|-----------|');
    for (const f of feedback) {
      const time = f.timestamp ? new Date(f.timestamp).toLocaleTimeString() : 'N/A';
      lines.push(`| ${f.sentiment || 'neutral'} | ${f.score ?? 'N/A'} | ${(f.signal || f.content || '').slice(0, 60)} | ${time} |`);
    }
  }

  // Source stats for common sources
  const sources = ['thinker', 'dialectic', 'subconscious', 'optimizer'];
  const sourceResults = await Promise.all(
    sources.map(s => fetchIntelligence(`/intelligence/outcomes/sources/${s}`, { windowMs }).catch(() => null))
  );
  const hasSourceData = sourceResults.some(r => r?.stats);
  if (hasSourceData) {
    lines.push('\n### Per-Source Quality\n');
    lines.push('| Source | Total | Avg Score | Positive Rate | Negative Rate |');
    lines.push('|--------|-------|-----------|---------------|---------------|');
    sources.forEach((s, i) => {
      const st = sourceResults[i]?.stats;
      if (st) {
        lines.push(`| ${s} | ${st.totalOutcomes} | ${st.avgScore?.toFixed(2) ?? 'N/A'} | ${(st.positiveRate * 100).toFixed(0)}% | ${(st.negativeRate * 100).toFixed(0)}% |`);
      }
    });
  }

  return lines.join('\n');
}

/**
 * Format cassi_budget output — provider usage metrics
 */
async function formatBudget(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const opts: Record<string, string> = {};
  if (args?.providerId) opts.providerId = args.providerId;
  if (args?.model) opts.model = args.model;
  const hours = args?.hours || 24;

  const [statsData, aggregateData, hourlyData] = await Promise.all([
    fetchIntelligence('/intelligence/profiler/stats').catch(() => null),
    fetchIntelligence('/intelligence/profiler/aggregate', opts).catch(() => null),
    fetchIntelligence('/intelligence/profiler/hourly', { ...opts, hours: String(hours) }).catch(() => null),
  ]);

  const stats = statsData || {};
  const aggregate = aggregateData?.aggregate || [];
  const hourly = hourlyData?.hourly || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Budget Brief\n'];

    if (!statsData) {
      lines.push('ProviderProfiler not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Total requests**: ${stats.totalRequestsRecorded || 0} (${stats.totalErrors || 0} errors)`);
    lines.push(`**Inflight**: ${stats.inflightRequests || 0} | **Pending records**: ${stats.pendingRecords || 0}`);

    if (aggregate.length > 0) {
      lines.push('\n**Provider breakdown**:');
      for (const a of aggregate.slice(0, 5)) {
        const errPct = a.totalRequests > 0 ? ((a.errorCount / a.totalRequests) * 100).toFixed(1) : '0';
        lines.push(`- **${a.providerId}/${a.model}**: ${a.totalRequests} req, ${a.totalTokens || 0} tokens, ${errPct}% errors, avg ${a.avgDurationMs?.toFixed(0) || '?'}ms`);
      }
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Budget Dashboard\n'];

  // Aggregate stats
  lines.push('### Overview\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  // Per-provider aggregate
  if (aggregate.length > 0) {
    lines.push('\n### Provider Aggregate\n');
    lines.push('| Provider | Model | Requests | Tokens | Errors | Avg Duration |');
    lines.push('|----------|-------|----------|--------|--------|-------------|');
    for (const a of aggregate) {
      lines.push(`| ${a.providerId} | ${a.model || 'all'} | ${a.totalRequests} | ${a.totalTokens || 0} | ${a.errorCount || 0} | ${a.avgDurationMs?.toFixed(0) || 'N/A'}ms |`);
    }
  }

  // Hourly trends
  if (hourly.length > 0) {
    lines.push(`\n### Hourly Trends (last ${hours}h)\n`);
    lines.push('| Hour | Requests | Tokens | Errors | Avg Duration |');
    lines.push('|------|----------|--------|--------|-------------|');
    for (const h of hourly.slice(-12)) {
      lines.push(`| ${h.hour || h.hourBucket} | ${h.requests || h.totalRequests} | ${h.tokens || h.totalTokens || 0} | ${h.errors || h.errorCount || 0} | ${h.avgDurationMs?.toFixed(0) || 'N/A'}ms |`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_evolution output — strategy self-modification timeline
 */
async function formatEvolution(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const limit = args?.limit || 10;
  const module = args?.module;

  const [statsData, dialecticEffData] = await Promise.all([
    fetchIntelligence('/intelligence/strategy/stats').catch(() => null),
    fetchIntelligence('/intelligence/strategy/dialectic-effectiveness', { limit: String(limit) }).catch(() => null),
  ]);

  // Strategy history and best require a module name
  let historyData: any = null;
  let bestData: any = null;
  if (module) {
    [historyData, bestData] = await Promise.all([
      fetchIntelligence('/intelligence/strategy/history', { module, limit: String(limit) }).catch(() => null),
      fetchIntelligence('/intelligence/strategy/best', { module }).catch(() => null),
    ]);
  }

  const stats = statsData || {};
  const effectiveness = dialecticEffData?.effectiveness || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Evolution Brief\n'];

    if (!statsData) {
      lines.push('StrategyTracker not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Strategy snapshots**: ${stats.totalSnapshotsRecorded || 0}`);
    lines.push(`**Evaluations**: ${stats.totalEvaluations || 0}`);
    lines.push(`**Pending**: ${stats.pendingChanges || 0} changes, ${stats.pendingSignals || 0} signals`);

    if (bestData?.strategy) {
      const best = bestData.strategy;
      lines.push(`\n**Best strategy for \`${module}\`**: score ${best.score?.toFixed(3) ?? 'N/A'} (${new Date(best.timestamp || best.created_at).toLocaleDateString()})`);
    } else if (module) {
      lines.push(`\nNo best strategy found for \`${module}\`.`);
    } else {
      lines.push('\nProvide a `module` parameter (e.g., "thinker", "dialectic") to see strategy history.');
    }

    if (effectiveness.length > 0) {
      const avgEff = effectiveness.reduce((sum: number, e: any) => sum + (e.effectivenessScore || 0), 0) / effectiveness.length;
      lines.push(`**Dialectic effectiveness**: avg ${(avgEff * 100).toFixed(1)}% across ${effectiveness.length} sessions`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Evolution Dashboard\n'];

  // Stats
  lines.push('### Overview\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  for (const [k, v] of Object.entries(stats)) {
    lines.push(`| ${k} | ${v} |`);
  }

  // Strategy history for module
  const history = historyData?.history || [];
  if (history.length > 0) {
    lines.push(`\n### Strategy History: \`${module}\`\n`);
    lines.push('| Date | Score | Config (preview) |');
    lines.push('|------|-------|------------------|');
    for (const h of history) {
      const date = new Date(h.timestamp || h.created_at).toLocaleString();
      const config = (typeof h.configJson === 'string' ? h.configJson : JSON.stringify(h.configJson || {})).slice(0, 80);
      lines.push(`| ${date} | ${h.score?.toFixed(3) ?? 'N/A'} | ${config}... |`);
    }
  } else if (module) {
    lines.push(`\n### Strategy History: \`${module}\`\n`);
    lines.push('No history found for this module.');
  }

  // Best strategy
  if (bestData?.strategy) {
    lines.push(`\n### Best Strategy: \`${module}\`\n`);
    lines.push('```json');
    lines.push(JSON.stringify(bestData.strategy, null, 2));
    lines.push('```');
  }

  // Dialectic effectiveness
  if (effectiveness.length > 0) {
    lines.push('\n### Dialectic Session Effectiveness\n');
    lines.push('| Session | Effectiveness | Turns | Signals Injected |');
    lines.push('|---------|--------------|-------|-----------------|');
    for (const e of effectiveness) {
      lines.push(`| ${(e.sessionId || '').slice(0, 12)}... | ${((e.effectivenessScore || 0) * 100).toFixed(1)}% | ${e.totalTurns || 'N/A'} | ${e.signalsInjected || 'N/A'} |`);
    }
  }

  return lines.join('\n');
}

/**
 * Format cassi_blindspots output — cross-session pattern detection
 */
async function formatBlindspots(args: any): Promise<string> {
  const mode = args?.mode || 'brief';
  const opts: Record<string, string> = {};
  if (args?.category) opts.category = args.category;
  if (args?.minConfidence !== undefined) opts.minConfidence = String(args.minConfidence);
  opts.limit = String(args?.limit || 10);

  const [statsData, patternsData, reflectData] = await Promise.all([
    fetchIntelligence('/intelligence/correlator/stats').catch(() => null),
    fetchIntelligence('/intelligence/correlator/patterns', opts).catch(() => null),
    fetchIntelligence('/intelligence/activity').then(d => d?.reflect?.unresolvedPatterns).catch(() => null),
  ]);

  const stats = statsData || {};
  const patterns = patternsData?.patterns || [];
  const unresolvedPatterns = reflectData || [];

  if (mode === 'brief') {
    const lines: string[] = ['## Blindspots Brief\n'];

    if (!statsData) {
      lines.push('CrossSessionCorrelator not initialized or no data available.');
      return lines.join('\n');
    }

    lines.push(`**Patterns detected**: ${stats.totalPatternsDetected || 0} (${stats.storedPatterns || 0} stored)`);

    // Category breakdown
    if (stats.byCategory && Object.keys(stats.byCategory).length > 0) {
      const categories = Object.entries(stats.byCategory).sort((a: any, b: any) => b[1] - a[1]);
      lines.push(`**Categories**: ${categories.map(([k, v]) => `${k}(${v})`).join(', ')}`);
    }

    // Top patterns
    if (patterns.length > 0) {
      lines.push(`\n**Top ${Math.min(patterns.length, 3)} patterns**:`);
      for (const p of patterns.slice(0, 3)) {
        lines.push(`- [${p.category || 'uncategorized'}] ${(p.description || p.pattern || '').slice(0, 100)} (confidence: ${((p.confidence || 0) * 100).toFixed(0)}%)`);
      }
    }

    // Unresolved reflection patterns
    if (unresolvedPatterns.length > 0) {
      lines.push(`\n**Unresolved reflection patterns**: ${unresolvedPatterns.length}`);
    }

    return lines.join('\n');
  }

  // Full mode
  const lines: string[] = ['## Blindspots Dashboard\n'];

  // Stats
  lines.push('### Cross-Session Correlator Stats\n');
  lines.push('| Metric | Value |');
  lines.push('|--------|-------|');
  lines.push(`| Total patterns detected | ${stats.totalPatternsDetected || 0} |`);
  lines.push(`| Stored patterns | ${stats.storedPatterns || 0} |`);
  lines.push(`| Last run | ${stats.lastRunAt ? new Date(stats.lastRunAt).toLocaleString() : 'never'} |`);

  if (stats.byCategory && Object.keys(stats.byCategory).length > 0) {
    lines.push('\n**By Category**:');
    for (const [cat, count] of Object.entries(stats.byCategory)) {
      lines.push(`- ${cat}: ${count}`);
    }
  }

  // Cross-session patterns
  if (patterns.length > 0) {
    lines.push('\n### Detected Patterns\n');
    lines.push('| Category | Confidence | Description |');
    lines.push('|----------|------------|-------------|');
    for (const p of patterns) {
      lines.push(`| ${p.category || 'uncategorized'} | ${((p.confidence || 0) * 100).toFixed(0)}% | ${(p.description || p.pattern || '').slice(0, 100)} |`);
    }

    // Show full details for top patterns
    lines.push('\n### Pattern Details\n');
    for (const p of patterns.slice(0, 5)) {
      lines.push(`#### ${p.category || 'Pattern'} (${((p.confidence || 0) * 100).toFixed(0)}% confidence)\n`);
      lines.push(`- **Key**: ${p.correlationKey || 'N/A'}`);
      lines.push(`- **Description**: ${p.description || p.pattern || 'N/A'}`);
      if (p.evidence) lines.push(`- **Evidence**: ${typeof p.evidence === 'string' ? p.evidence.slice(0, 200) : JSON.stringify(p.evidence).slice(0, 200)}`);
      if (p.sessionIds) lines.push(`- **Sessions**: ${Array.isArray(p.sessionIds) ? p.sessionIds.length : 'N/A'}`);
      lines.push('');
    }
  }

  // Unresolved reflection patterns
  if (unresolvedPatterns.length > 0) {
    lines.push('\n### Unresolved Reflection Patterns\n');
    lines.push('These error/concern patterns from the Reflect module remain unresolved:\n');
    for (const p of unresolvedPatterns) {
      lines.push(`- **${p.pattern || p.category || 'unknown'}** (${p.occurrences || 1}x): ${p.description || p.evidence || 'no description'}`);
    }
  }

  return lines.join('\n');
}

/**
 * Execute an intelligence tool — routes to the appropriate formatter
 */
async function executeIntelligenceTool(toolName: string, args: any): Promise<string> {
  log('info', 'Executing intelligence tool', { tool: toolName, args });

  const formatters: Record<string, (args: any) => Promise<string>> = {
    cassi_activity: formatActivity,
    cassi_dialectic: formatDialectic,
    cassi_thinker: formatThinker,
    cassi_subconscious: formatSubconscious,
    cassi_trace: formatTrace,
    cassi_effectiveness: formatEffectiveness,
    cassi_budget: formatBudget,
    cassi_evolution: formatEvolution,
    cassi_blindspots: formatBlindspots,
  };

  const formatter = formatters[toolName];
  if (!formatter) {
    throw new Error(`Unknown intelligence tool: ${toolName}`);
  }

  try {
    return await formatter(args);
  } catch (error: any) {
    log('error', 'Intelligence tool failed', { tool: toolName, error: error.message });
    return `## Error\n\nFailed to execute ${toolName}: ${error.message}\n\nMake sure the CassiCore daemon is running.`;
  }
}

/**
 * Create MCP Server
 */
function createServer() {
  const server = new Server(
    {
      name: 'cassicore-gateway',
      version: GATEWAY_VERSION,
    },
    {
      capabilities: {
        tools: {},
        resources: {},
      },
    }
  );

  // List available tools
  server.setRequestHandler(ListToolsRequestSchema, async () => {
    return {
      tools: [...CASSICORE_TOOLS, ...INTELLIGENCE_TOOLS, ...SERENA_TOOLS],
    };
  });

  // Handle tool calls
  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    
    log('info', 'Tool call received', { tool: name, args });
    
    try {
      let result;
      
      if (name.startsWith('serena__')) {
        result = await executeSerenaTool(name, args);
      } else if (name.startsWith('cassi_')) {
        // Intelligence tools return markdown directly
        const markdown = await executeIntelligenceTool(name, args);
        return {
          content: [
            {
              type: 'text',
              text: markdown,
            },
          ],
        };
      } else {
        result = await executeCassiCoreTool(name, args);
      }

      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    } catch (error: any) {
      log('error', 'Tool execution failed', { tool: name, error: error.message });
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({ error: error.message }, null, 2),
          },
        ],
        isError: true,
      };
    }
  });

  // List resources (files/directories accessible)
  server.setRequestHandler(ListResourcesRequestSchema, async () => {
    return {
      resources: [
        {
          uri: 'cassicore://health',
          name: 'CassiCore Health Status',
          mimeType: 'application/json',
          description: 'Current health and status of CassiCore daemon',
        },
      ],
    };
  });

  // Read resources
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;
    
    if (uri === 'cassicore://health') {
      try {
        const response = await fetch(`${CASSICORE_URL}/health`);
        const health = await response.json();
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify(health, null, 2),
            },
          ],
        };
      } catch (error: any) {
        return {
          contents: [
            {
              uri,
              mimeType: 'application/json',
              text: JSON.stringify({ status: 'error', error: error.message }),
            },
          ],
        };
      }
    }
    
    throw new Error(`Unknown resource: ${uri}`);
  });

  return server;
}

/**
 * Start with stdio transport (default for MCP)
 */
async function startStdio() {
  log('info', 'Starting CassiCore MCP Gateway (stdio mode)', { url: CASSICORE_URL });
  
  const server = createServer();
  const transport = new StdioServerTransport();
  
  await server.connect(transport);
  
  log('info', 'CassiCore MCP Gateway connected and ready');
}

/**
 * Start with HTTP/SSE transport (for remote connections)
 */
async function startHttp(port: number) {
  log('info', 'Starting CassiCore MCP Gateway (HTTP mode)', { port, url: CASSICORE_URL });
  
  const server = createServer();
  
  // Create HTTP server for SSE transport
  const httpServer = http.createServer(async (req, res) => {
    const url = new URL(req.url || '/', `http://localhost:${port}`);
    
    // Health endpoint
    if (url.pathname === '/health') {
      try {
        const cassiHealth = await fetch(`${CASSICORE_URL}/health`);
        const cassiStatus = await cassiHealth.json();
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'ok',
          gateway: 'cassicore-mcp-gateway',
          version: GATEWAY_VERSION,
          cassicore: cassiStatus,
        }));
      } catch (error: any) {
        res.writeHead(503, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({
          status: 'error',
          error: error.message,
        }));
      }
      return;
    }
    
    // Tools endpoint (REST API)
    if (url.pathname === '/tools' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify([...CASSICORE_TOOLS, ...INTELLIGENCE_TOOLS, ...SERENA_TOOLS]));
      return;
    }
    
    // Execute endpoint (REST API)
    if (url.pathname === '/tools/execute' && req.method === 'POST') {
      let body = '';
      req.on('data', chunk => body += chunk);
      req.on('end', async () => {
        try {
          const { tool, args } = JSON.parse(body);
          const result = await executeCassiCoreTool(tool, args);
          res.writeHead(200, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify(result));
        } catch (error: any) {
          res.writeHead(500, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: error.message }));
        }
      });
      return;
    }
    
    res.writeHead(404);
    res.end('Not found');
  });
  
  httpServer.listen(port, () => {
    log('info', `HTTP server listening on port ${port}`);
  });
}

/**
 * Main entry point
 */
async function main() {
  const args = process.argv.slice(2);
  const httpMode = args.includes('--http');
  const portArg = args.find(arg => arg.startsWith('--port='));
  const port = portArg ? parseInt(portArg.split('=')[1], 10) : 3000;
  
  // Validate CassiCore connection
  try {
    const healthCheck = await fetch(`${CASSICORE_URL}/health`);
    if (!healthCheck.ok) {
      throw new Error('CassiCore health check failed');
    }
    log('info', 'CassiCore daemon connection verified');
  } catch (error: any) {
    log('error', 'Failed to connect to CassiCore daemon', { 
      url: CASSICORE_URL, 
      error: error.message 
    });
    log('warn', 'Make sure CassiCore is running: cassicore daemon');
    // Continue anyway - connection might succeed later
  }
  
  if (httpMode) {
    await startHttp(port);
  } else {
    await startStdio();
  }
}

main().catch((error) => {
  log('error', 'Gateway failed to start', { error: error.message });
  process.exit(1);
});
