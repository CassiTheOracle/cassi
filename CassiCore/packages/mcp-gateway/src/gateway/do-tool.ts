#!/usr/bin/env node
/**
 * do-tool.ts — `cassi_do` meta-wrapper tool + `cassi_enrich` context tool
 *
 * `cassi_do`:     Executes any registered gateway tool and wraps its result with
 *                 enriched context from CassiCore (memories, archive, session history).
 *
 * `cassi_enrich`: Returns context enrichment only (no delegated tool call).
 *                 Designed to be called with the user's message at the start of
 *                 every turn so the agent has full cognitive context.
 *
 * Both tools share context-fetching logic via context-enrichment.ts.
 */

import { fetchAndFormatContext, type ContextLimits } from './context-enrichment.js';
import type { ILogger } from '../../types/interfaces.js';

// ─── Types ───────────────────────────────────────────────────────────────────

/** MCP tool response shape (matches what routeToolCall returns) */
type McpToolResponse = {
  content: Array<{ type: 'text'; text: string }>;
  isError?: true;
};

/**
 * Injected routing callback — avoids circular imports and duplication of
 * the routing table. Provided by cassicore-gateway.ts when invoking executeDoTool.
 */
export type ToolRouter = (
  name: string,
  args: unknown
) => Promise<McpToolResponse>;

// ─── Tool Definitions ─────────────────────────────────────────────────────────

export const DO_TOOLS = [
  {
    name: 'do',
    description: `Call any registered tool and receive its result wrapped with enriched context from CassiCore — relevant memories and past conversations retrieved automatically in parallel.

Use this when you want tool output that is automatically grounded in Cassi's memory. For example:
  - do("bash", { command: "git log" })           → git output + remembered git workflow patterns
  - do("read", { path: "core/session.ts" })       → file content + remembered context about that file
  - do("cassi_memory_search", { query: "auth" })  → memory results + related archive conversations

The tool parameter accepts both the raw registered name ("bash") and the prefixed form you see in the tool list ("cassi_bash") — one cassi_ prefix is stripped automatically.

Context is fetched in parallel with the delegated tool call, so latency equals max(tool_time, context_time) rather than their sum. Set memory_limit=0, archive_limit=0, or index_limit=0 to skip any source.`,
    inputSchema: {
      type: 'object',
      properties: {
        tool: {
          type: 'string',
          description:
            'Registered tool name to call (e.g. "bash", "cassi_bash", "cassi_memory_search"). One leading cassi_ prefix is stripped automatically.',
        },
        input: {
          type: 'object',
          description: 'Input arguments for the delegated tool.',
        },
        context_query: {
          type: 'string',
          description:
            'Override the auto-derived query used to search memories and archive. If omitted, derived from the tool name and the first meaningful input field (command, query, goal, path, message, etc.).',
        },
        memory_limit: {
          type: 'number',
          description: 'Max memory results to include (default: 5, 0 = skip memory context).',
        },
        archive_limit: {
          type: 'number',
          description: 'Max archive results to include (default: 5, 0 = skip archive context).',
        },
        index_limit: {
          type: 'number',
          description:
            'Max session history results to include (default: 10, 0 = skip). Returns paragraph-level and block-level excerpts from indexed past sessions, centered on the matched text.',
        },
      },
      required: ['tool', 'input'],
    },
  },
];

export const ENRICH_TOOLS = [
  {
    name: 'enrich',
    description: `Fetch CassiCore context enrichment for a query — returns relevant memories, archived conversations, and session history WITHOUT calling any tool.

MANDATORY: Call this at the start of EVERY user turn with the user's message as the query. This surfaces past decisions, stored knowledge, user preferences, and conversation history that are critical for informed responses.

The same context enrichment that cassi_do applies to tool results, but standalone. Returns a formatted markdown block with results from three sources:
  - Memory store (stored facts, preferences, insights)
  - Archive (past conversations, tool calls, patterns, dialectic outputs)
  - Session history (indexed past session excerpts with paragraph-level granularity)

If no relevant context is found, returns a brief "no context" message.`,
    inputSchema: {
      type: 'object',
      properties: {
        query: {
          type: 'string',
          description:
            'The search query — typically the user\'s full message. Can also be a focused topic or question.',
        },
        memory_limit: {
          type: 'number',
          description: 'Max memory results (default: 5, 0 = skip).',
        },
        archive_limit: {
          type: 'number',
          description: 'Max archive results (default: 5, 0 = skip).',
        },
        index_limit: {
          type: 'number',
          description: 'Max session history results (default: 10, 0 = skip).',
        },
      },
      required: ['query'],
    },
  },
];

export const DO_TOOL_NAMES = new Set(DO_TOOLS.map(t => t.name));
export const ENRICH_TOOL_NAMES = new Set(ENRICH_TOOLS.map(t => t.name));

export function getDoTools(): Array<{
  name: string;
  description: string;
  inputSchema: Record<string, unknown>;
}> {
  return [...DO_TOOLS, ...ENRICH_TOOLS];
}

// ─── Query Derivation ─────────────────────────────────────────────────────────

/**
 * Strip one leading "cassi_" prefix so callers can pass either the registered
 * name or the prefixed name they see in OpenCode's tool list.
 */
export function normalizeToolName(name: string): string {
  return name.startsWith('cassi_') ? name.slice('cassi_'.length) : name;
}

/**
 * Derive a context query from the tool name and its input arguments.
 * Checks priority fields in order; uses the first non-empty string value.
 */
function deriveContextQuery(rawToolName: string, input: unknown): string {
  const baseName = normalizeToolName(rawToolName);
  const parts: string[] = [baseName];

  if (input && typeof input === 'object') {
    const PRIORITY_FIELDS = [
      'query',
      'goal',
      'command',
      'message',
      'content',
      'path',
      'target',
      'prompt',
      'text',
    ];
    for (const field of PRIORITY_FIELDS) {
      const val = (input as Record<string, unknown>)[field];
      if (typeof val === 'string' && val.trim().length > 0) {
        parts.push(val.trim().slice(0, 150));
        break;
      }
    }
  }

  return parts.join(' ');
}

// ─── Enrich Executor ──────────────────────────────────────────────────────────

/**
 * Execute the `enrich` tool — context-only enrichment (no delegated tool call).
 *
 * @param baseUrl  CassiCore admin API base URL
 * @param args     Tool call arguments from the MCP caller
 * @param logger   Child logger for structured output
 */
export async function executeEnrichTool(
  baseUrl: string,
  args: unknown,
  logger: ILogger
): Promise<McpToolResponse> {
  const a = args as any;

  const query: string = a?.query ?? '';
  if (!query.trim()) {
    return {
      content: [{ type: 'text', text: 'No query provided — nothing to enrich.' }],
    };
  }

  const limits: ContextLimits = {
    memoryLimit: a?.memory_limit ?? 5,
    archiveLimit: a?.archive_limit ?? 5,
    indexLimit: a?.index_limit ?? 10,
  };

  logger.info('executeEnrichTool', { query, ...limits });

  const result = await fetchAndFormatContext(baseUrl, query, limits);

  if (!result.hasContext) {
    return {
      content: [
        {
          type: 'text',
          text: `## Cassi Context\n> No relevant context found for: \`${query}\`\n\nNo matching memories, archive entries, or session history. Proceeding without historical context.`,
        },
      ],
    };
  }

  return {
    content: [{ type: 'text', text: result.markdown }],
  };
}

// ─── Do Executor ──────────────────────────────────────────────────────────────

/**
 * Execute the `do` meta-wrapper tool.
 *
 * @param baseUrl   CassiCore admin API base URL
 * @param args      Tool call arguments from the MCP caller
 * @param logger    Child logger for structured output
 * @param routeTool Injected routing callback from the gateway — avoids
 *                  circular imports by delegating routing back to the caller
 */
export async function executeDoTool(
  baseUrl: string,
  args: unknown,
  logger: ILogger,
  routeTool: ToolRouter
): Promise<McpToolResponse> {
  const a = args as any;

  const rawToolName: string = a?.tool ?? '';
  const toolInput: unknown = a?.input ?? {};
  const contextQuery: string = a?.context_query ?? deriveContextQuery(rawToolName, toolInput);
  const limits: ContextLimits = {
    memoryLimit: a?.memory_limit ?? 5,
    archiveLimit: a?.archive_limit ?? 5,
    indexLimit: a?.index_limit ?? 10,
  };

  // Strip one cassi_ prefix so callers can use the name as shown in OpenCode
  const resolvedToolName = normalizeToolName(rawToolName);

  // Recursion guard — check both before and after normalization
  const selfNames = new Set(['do', 'cassi_do', 'enrich', 'cassi_enrich']);
  if (!resolvedToolName || selfNames.has(rawToolName) || selfNames.has(resolvedToolName)) {
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify({
            error: 'cassi_do cannot call itself or cassi_enrich. Pass a specific tool name.',
          }),
        },
      ],
      isError: true,
    };
  }

  logger.info('executeDoTool', {
    tool: resolvedToolName,
    contextQuery,
    ...limits,
  });

  // ── Parallel execution: delegated tool + context enrichment ───────────────
  const [toolSettled, contextSettled] = await Promise.allSettled([
    routeTool(resolvedToolName, toolInput),
    fetchAndFormatContext(baseUrl, contextQuery, limits),
  ]);

  const contextResult =
    contextSettled.status === 'fulfilled' ? contextSettled.value : null;

  // ── Assemble markdown envelope ────────────────────────────────────────────
  const lines: string[] = [];

  if (contextResult?.hasContext) {
    lines.push(contextResult.markdown);
    lines.push('---');
    lines.push('');
  }

  lines.push(`## Tool Result: \`${resolvedToolName}\``);
  lines.push('');

  const isToolError =
    toolSettled.status === 'rejected' ||
    (toolSettled.status === 'fulfilled' && toolSettled.value?.isError === true);

  if (toolSettled.status === 'rejected') {
    lines.push(`**Error:** ${String(toolSettled.reason)}`);
  } else {
    const resultText =
      toolSettled.value.content
        ?.map((c: { type: string; text: string }) => c.text)
        .join('\n') ?? '';
    lines.push(resultText);
  }

  // ── Guard: cap total output to avoid downstream truncation ───────────────
  // OpenCode silently truncates tool results at ~51200 bytes; we cap earlier
  // and emit a clear diagnostic rather than silently losing content.
  const MAX_OUTPUT_BYTES = 40_000;
  const combined = lines.join('\n');
  const outputBytes = Buffer.byteLength(combined, 'utf8');

  if (outputBytes > MAX_OUTPUT_BYTES) {
    const truncated = combined.slice(0, MAX_OUTPUT_BYTES);
    const overflowKB = Math.round((outputBytes - MAX_OUTPUT_BYTES) / 1024);
    const warning = [
      '',
      '---',
      `⚠️ **cassi_do output capped at ${MAX_OUTPUT_BYTES / 1000}KB** (${overflowKB}KB omitted).`,
      `To read the full result, call \`${resolvedToolName}\` directly without \`cassi_do\`,`,
      `or set \`memory_limit=0 archive_limit=0 index_limit=0\` to reduce context overhead.`,
    ].join('\n');
    return {
      content: [{ type: 'text', text: truncated + warning }],
      ...(isToolError ? { isError: true as const } : {}),
    };
  }

  return {
    content: [{ type: 'text', text: combined }],
    ...(isToolError ? { isError: true as const } : {}),
  };
}
